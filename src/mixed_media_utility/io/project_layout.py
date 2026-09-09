"""Target v2 project directory layout helpers.

Story 2.5 defines the v2 arborescence contract (see
ARCHITECTURE_DETAILED.md sections 3, 4 and 9, and
_bmad-output/planning-artifacts/epics.md Story 2.5): a project must clearly
distinguish source rushes, extracted frames, scans, reconstructed frames,
printable PDF artifacts, logs and the manifest. The source rush directory
(`inputs/`, kept as a transitional alias for the story 1.1 POC baseline) is
no longer a mandatory hypothesis of the target contract: extracted and
reconstructed frames are namespaced per rush and target fps instead
(`extract-frames/<rush_id>_<fps_target>/`,
`frames-scannees/<rush_id>_<fps_target>/`; les noms d'avant `frames/` et
`output-frames/` restent RECONNUS, story 11.14),
independently of where (or whether) a local source copy lives.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .naming import (
    bounds_suffix,
    format_fps_short,
    format_version_suffix,
    valider_nom_court_de_cadence,
)

# Top-level directories always present in a v2 project, regardless of what a
# given manifest describes (AC 1).

#: Dossier des frames **extraites** du rush par `extract` (story 11.14,
#: `EPIC11-ARB-214` et `EPIC11-ARB-220`). Le mot est celui d'Egan -- « un lot
#: est un ensemble de frames extraites depuis le rush source avec extract » --
#: et il est en symetrie avec la commande qui les produit. Le nom d'avant,
#: `frames`, ne disait pas DE QUOI il s'agissait : le depot employait le meme
#: mot generique pour le contenu d'un lot et pour celui d'un lot scanne.
EXTRACT_FRAMES_DIRNAME = "extract-frames"

#: Dossier des frames **scannees**, c'est-a-dire du lot scanne reproduit
#: depuis un scan (meme arbitrage). Le nom d'avant, `output-frames`, nommait
#: une SORTIE -- ce que tout dossier produit est -- au lieu de nommer l'objet.
SCAN_FRAMES_DIRNAME = "frames-scannees"

#: **Reconnu, JAMAIS ecrit** (`EPIC11-ARB-171`, patron de
#: `LEGACY_SOURCES_DIRNAME` ci-dessous et de `naming.LEGACY_SHEETS_MARKER`).
#: Aucun dossier deja ecrit sur un disque n'est renomme : un projet qui porte
#: `frames/<slug>` continue d'etre lu la, et c'est ce dossier-la que les
#: resolveurs rendent. Seuls les lots NEUFS prennent le nom neuf.
LEGACY_FRAMES_DIRNAME = "frames"

#: Meme statut que le precedent, pour les frames scannees.
LEGACY_OUTPUT_FRAMES_DIRNAME = "output-frames"

#: **RACCORD TRANSITOIRE, story 11.14.** Ces deux alias portent la valeur
#: NEUVE et existent seulement parce que le renommage traverse des modules
#: qui n'appartiennent pas au lot B (`cli.py`, `scan_output_frames.py`,
#: `io/extraction_manifest.py`, `tui/`, `gui/`). Les retirer avant que les
#: lots C, D et E aient porte les noms neufs casserait leur import, donc la
#: branche entiere. Ils ne portent AUCUN litteral du nom d'avant : la
#: frontiere negative de l'AC 2.3 reste donc vraie pendant la transition.
FRAMES_DIRNAME = EXTRACT_FRAMES_DIRNAME
OUTPUT_FRAMES_DIRNAME = SCAN_FRAMES_DIRNAME

SCANS_DIRNAME = "scans"

#: Dossier des **planches** -- les tirages PDF d'un lot et la page de mire
#: (`EPIC11-ARB-225`, Egan le 2026-09-05 : « `patches/` doit devenir
#: `planches/` »). Le nom d'avant, `patches`, disait les **pastilles** de la
#: mire et non l'objet imprime : le depot employait le meme mot pour le
#: dossier et pour le vocabulaire de colorimetrie, qui n'ont aucun rapport.
PLANCHES_DIRNAME = "planches"

#: **Reconnu, JAMAIS ecrit pour un objet NEUF** -- meme patron que
#: `LEGACY_FRAMES_DIRNAME` ci-dessus (`EPIC11-ARB-171`). Aucun dossier deja
#: pose sur un disque n'est renomme et aucune migration n'est demandee a
#: l'operateur (arbitrage d'Egan du 2026-09-06, choix A : « lire les deux,
#: ecrire planches »). Une planche deja ecrite la continue d'y etre lue, et
#: d'y etre REECRITE -- voir `chemin_de_planche`.
LEGACY_PATCHES_DIRNAME = "patches"

LOGS_DIRNAME = "logs"

#: Dossier des masters video produits par `encode` (story 6.1).
#:
#: Le nom existait deja **en dur** a deux endroits de `cli.py` (la liste des
#: sous-dossiers du POC et le chemin de `poc process-scan`), et le champ
#: `artifacts.outputs_dir` est declare au schema depuis la story 2.2 sans avoir
#: jamais eu de producteur. La constante est donc nommee **une seule fois** dans
#: le depot, exactement comme `SCAN_FRAMES_DIRNAME` l'exige deja pour sa
#: voisine: doubler la chaine litterale est le defaut que ce module existe pour
#: fermer.
#:
#: Cohabitation a connaitre, relevee en revue de la story 6.1 et non tue: le
#: chemin POC `poc process-scan` ecrit des frames dans ce meme dossier et
#: `detection.aruco.extract_scan_frames` y **supprime** les fichiers
#: `scan_frame_*` a suffixe TIFF/PNG. Aucune collision avec un master
#: `<lot_id>_mmu_<profile_id>.<conteneur>` -- verifie -- mais les masters de
#: production et les frames du POC vivent bien au meme endroit.
OUTPUTS_DIRNAME = "outputs"

#: Dossier `versions/` de l'arborescence projet (story 5.22, `EPIC5-ARB-81`):
#: les **artefacts versionnes du projet** y vivent, un sous-dossier par
#: famille. Le premier est `versions/calibration/`, les profils de calibration
#: par chaine de scan. L'ajout est additif a `ensure_project_layout`: un projet
#: existant le recoit au prochain passage, sans casse.
VERSIONS_DIRNAME = "versions"

# Transitional alias for the story 1.1 POC baseline, where the source rush
# copy lives under `inputs/`. The v2 contract does not make this directory
# mandatory (AC 2); it is kept here only as a recognized name for partially
# reconstructed or legacy projects, not created by `ensure_project_layout`.
LEGACY_SOURCES_DIRNAME = "inputs"

# Base subdirectories created unconditionally by `ensure_project_layout`.
BASE_SUBDIRS = (SCANS_DIRNAME, PLANCHES_DIRNAME, LOGS_DIRNAME, VERSIONS_DIRNAME)


def rush_dir_slug(
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    fps_short_name: str | None = None,
    version_rank: int | None = None,
) -> str:
    """Return the `<rush_id>_<fps-cible>` slug namespacing per-rush frame dirs.

    The fps fragment is produced by `io.naming.format_fps_short`, the single
    reference for rendering an fps value into a path component: the directory
    name and the extracted frame file names must agree on every target rate
    (`rush-001_12p5/` alongside `rush-001_12p5_00-00-00-00.tiff`). Before the
    2026-08-03 arbitration (ARB-3, `decisions-2026-08-03.md` decision 2) this
    helper rendered a fractional rate as `rush-001_12.5`, which diverged from
    `format_fps_short` and made non-integer target rates unreachable from the
    `extract` command even though story 3.2 supports them exactly. The dot was
    also incompatible with the `^[A-Za-z0-9_-]+$` pattern the manifest schema
    imposes on identifiers.

    Depuis la story 3.7, une extraction bornee par timecodes ajoute le
    condensat de `naming.bounds_suffix`, exactement le fragment que
    `naming.build_lot_id` ajoute de son cote: le dossier d'un extrait
    (`rush-001_3-a1b2c3d4/`) ne peut donc jamais etre celui de l'extraction
    complete (`rush-001_3/`), ni celui d'un autre extrait du meme rush a la
    meme cadence. Sans cela, deux lots d'identifiants distincts pointeraient
    vers un dossier unique.

    Depuis la story 11.4 (lot P, `EPIC11-ARB-62`), le mot-cle optionnel
    `fps_short_name` remplace le fragment de cadence par le nom court **deja
    calcule** la ou la cadence etait encore une `Fraction` exacte
    (`tui.cadences.nom_court_de_cadence`) : `rush_01_25s3` au lieu de
    `rush_01_8p333333333333334`. C'est le pendant EXACT du mot-cle de meme nom
    de `naming.build_lot_id`, et il existe pour cette seule raison : sans lui,
    un lot nomme par la convention `_25s3` porterait un nom de dossier issu de
    `format_fps_short`, donc divergent de son identifiant -- ce qu'ARB-3
    interdit. Le defaut de `None` reprend le chemin d'avant au caractere pres.

    Depuis la story 5.29 (`EPIC11-ARB-89`), le mot-cle optionnel
    `version_rank` ajoute le fragment `_v<rang>` **apres** le suffixe de
    bornes, produit par `naming.format_version_suffix` -- le meme fragment
    que celui que `naming.build_lot_id` place dans l'identifiant quand il
    recoit le meme mot-cle (ARB-3, encore). Le refus de longueur, s'il y en a
    un, appartient a `build_lot_id`: cette fonction ne raccourcit jamais son
    slug, donc rien n'y refuse d'entree -- l'appelant qui a obtenu un
    `lot_id` sans erreur peut toujours en deriver ce slug.
    """
    suffix = bounds_suffix(source_in_timecode, source_out_timecode)
    # `fps_short_name` absent, c'est le chemin d'avant la story 11.4 et il est
    # inchange au caractere pres : tout appelant qui ne passe pas de nom court
    # obtient exactement le slug qu'il obtenait.
    #
    # Present, c'est le MEME fragment que celui que `naming.build_lot_id`
    # place dans l'identifiant de lot quand il recoit le meme mot-cle, et
    # c'est la seule chose qui compte ici : ARB-3 (`decisions-2026-08-03.md`,
    # decision 2) interdit verbatim que « le nom de dossier de lot et
    # l'identifiant de lot » divergent. Un banc mesure les DEUX chaines
    # produites plutot que le fait qu'elles appellent la meme fonction : un
    # cablage identique peut produire deux noms differents.
    #
    # La garde n'est pas decorative : le slug devient un COMPOSANT DE CHEMIN,
    # et un nom court portant `/` ou `..` ecrirait hors du dossier de frames.
    # C'est le meme motif que la garde de `derive_lot_dir_slug` sur le
    # `lot_id` venu d'un QR (`scan_output_frames.py`), paye a la revue du
    # 2026-08-08 sur un TIFF ecrit hors du dossier projet.
    if fps_short_name is None:
        fragment = format_fps_short(fps_target)
    else:
        fragment = valider_nom_court_de_cadence(fps_short_name)
    slug = f"{rush_id}_{fragment}"
    if suffix is not None:
        slug = f"{slug}-{suffix}"
    if version_rank is not None:
        slug = f"{slug}{format_version_suffix(version_rank)}"
    return slug


def _valider_le_slug(slug: str) -> str:
    """La garde d'un slug de dossier de lot : un UNIQUE composant, relatif.

    Ecrite une fois pour les deux familles de frames. C'est la derniere garde
    avant la concatenation, et elle n'est pas theorique : le slug d'un lot
    borne est le `lot_id` du QR, c'est-a-dire une valeur lue sur du papier
    scanne. `Path("/proj") / "frames-scannees" / "/tmp/x"` vaut `/tmp/x` --
    pathlib abandonne la partie gauche devant un composant absolu --, et un
    slug portant `a/b/c` produit une arborescence imbriquee ou l'`encode` ne
    cherchera jamais le lot.
    """
    if not isinstance(slug, str) or not slug:
        raise ValueError(
            f"Slug de dossier de sortie invalide: {slug!r}. Une chaine non vide "
            "est attendue."
        )
    if (
        slug in (".", "..")
        or PurePosixPath(slug).parts != (slug,)
        or PureWindowsPath(slug).parts != (slug,)
    ):
        raise ValueError(
            f"Slug de dossier de sortie invalide: {slug!r}. Un slug est un "
            "unique composant de nom, relatif: ni separateur de chemin, ni "
            "remontee, ni chemin absolu, ni lettre de lecteur. Sans cette "
            "garde, les frames du lot atterrissent hors du dossier projet ou "
            "sous une arborescence ou l'encode ne les cherchera pas."
        )
    return slug


def _racines(project_dir: str | Path, neuf: str, ancien: str) -> tuple[Path, ...]:
    """Les racines a LIRE : la neuve d'abord, l'ancienne ensuite si elle existe.

    L'ordre porte la regle : un slug present des deux cotes -- ce que rien
    n'ecrit, mais qu'une main peut fabriquer -- est lu par son dossier NEUF, et
    jamais deux fois. La racine d'avant n'est rendue que si elle existe
    reellement, pour qu'un parcours ne compte pas un emplacement absent.
    """
    project_dir = Path(project_dir)
    racines = [project_dir / neuf]
    if (project_dir / ancien).is_dir():
        racines.append(project_dir / ancien)
    return tuple(racines)


def racines_de_frames_extraites(project_dir: str | Path) -> tuple[Path, ...]:
    """Les racines ou vivent des frames extraites (`EPIC11-ARB-171`).

    Publiee parce que l'inventaire et la suppression **parcourent** ces
    racines : sans elle, chacun recomposerait la sienne et l'un des deux
    oublierait l'ancienne au premier ajustement -- la seconde verite que ce
    module existe pour empecher.
    """
    return _racines(project_dir, EXTRACT_FRAMES_DIRNAME, LEGACY_FRAMES_DIRNAME)


def racines_de_frames_scannees(project_dir: str | Path) -> tuple[Path, ...]:
    """Les racines ou vivent des frames scannees. Pendant exact de la voisine."""
    return _racines(project_dir, SCAN_FRAMES_DIRNAME, LEGACY_OUTPUT_FRAMES_DIRNAME)


def racines_de_planches(project_dir: str | Path) -> tuple[Path, ...]:
    """Les racines ou vivent des planches (`EPIC11-ARB-225`).

    Pendant exact des deux voisines, et publiee pour le meme motif : le
    balayage des orphelins, la suppression d'un lot et le calcul de la ligne
    d'eau des tirages **parcourent** ces racines. Chacun recomposant la
    sienne, l'un des trois oublierait celle d'avant au premier ajustement --
    et c'est le defaut `E2-1` deja paye une fois : un lecteur qui n'interroge
    qu'une racine rend un rang DEJA CONSOMME.
    """
    return _racines(project_dir, PLANCHES_DIRNAME, LEGACY_PATCHES_DIRNAME)


def chemin_de_planche(project_dir: str | Path, nom: str) -> Path:
    """Le chemin de CETTE planche : celui d'avant si le fichier y est deja.

    Pendant FICHIER de `_dossier_de_lot`, et la meme regle qu'`EPIC11-ARB-171`
    pose pour les lots : « on ecrit le nom neuf, on RECONNAIT l'ancien, on ne
    renomme rien de ce qui est deja sur un disque ». Un projet neuf n'a rien
    sous `patches/`, donc toute planche neuve va sous `planches/` -- le nom
    d'avant n'est jamais ecrit pour un objet qui n'existait pas.

    **Pourquoi la resolution est par FICHIER et non par dossier**, et ce que
    la variante par dossier casserait : `makepdf` refuse d'ecraser un tirage
    present (`EPIC11-ARB-89`) en interrogeant `output_path.exists()`. Viser
    `planches/<nom>` en aveugle sur un projet ancien rendrait ce refus muet --
    le fichier de meme nom vit sous `patches/` --, et l'operateur qui consent
    a un ecrasement obtiendrait un DOUBLON silencieux au lieu d'un
    remplacement. C'est exactement la destruction sans issue nommee que
    l'arbitrage existe pour fermer, retournee en duplication sans issue
    nommee.
    """
    project_dir = Path(project_dir)
    deja_ecrite = project_dir / LEGACY_PATCHES_DIRNAME / nom
    if deja_ecrite.is_file():
        return deja_ecrite
    return project_dir / PLANCHES_DIRNAME / nom


def dossier_de_planches(project_dir: str | Path) -> Path:
    """L'unique dossier a MONTRER a l'operateur, celui qui porte les planches.

    Distincte de `racines_de_planches`, qui rend TOUT ce qu'il faut lire :
    ici on doit designer **un** emplacement -- la ligne `Destination` d'un
    cartouche, le dossier que la TUI ouvre au bureau. Rendre le neuf en
    aveugle ouvrirait un dossier VIDE sur un projet ancien, puisque
    `ensure_project_layout` cree desormais `planches/` a cote du `patches/`
    qui, lui, porte les fichiers.

    Ce qui gagne quand les deux existent et portent tous deux des fichiers :
    le **neuf**, dans le meme ordre que `_racines`. Une seule verite d'ordre
    dans le module, pas deux.
    """
    racines = racines_de_planches(project_dir)
    for racine in racines:
        try:
            if any(entree.is_file() for entree in racine.iterdir()):
                return racine
        except OSError:
            # Un dossier illisible n'est pas un dossier vide : on passe au
            # suivant plutot que de lever depuis une fonction d'affichage.
            continue
    return racines[0]


def _dossier_de_lot(
    project_dir: str | Path, slug: str, neuf: str, ancien: str
) -> Path:
    """Le dossier de CE lot : celui d'avant s'il existe deja, le neuf sinon.

    C'est la traduction litterale d'`EPIC11-ARB-171` -- « on ecrit le nom neuf,
    on RECONNAIT l'ancien, on ne renomme rien de ce qui est deja sur un
    disque » -- et la resolution est faite **par lot**, pas par racine. Le
    faire par racine ferait porter le nom d'avant a un lot neuf simplement
    parce qu'un lot ancien vit dans le meme projet ; le faire par lot garde
    chaque lot d'un seul tenant, ce qui est la seule propriete qui compte : un
    lot scinde entre deux racines serait a moitie invisible pour `encode`.
    """
    project_dir = Path(project_dir)
    _valider_le_slug(slug)
    deja_ecrit = project_dir / ancien / slug
    if deja_ecrit.is_dir():
        return deja_ecrit
    return project_dir / neuf / slug


def extract_frames_dir_from_slug(project_dir: str | Path, slug: str) -> Path:
    """Rendre le dossier de frames extraites d'un slug **deja resolu**.

    Pendant exact de `scan_frames_dir_from_slug`, et il manquait : un
    appelant qui detient le slug devait recomposer
    `project_dir / EXTRACT_FRAMES_DIRNAME / slug` a la main, donc court-circuiter
    la reconnaissance du nom d'avant.

    **Le nom porte `extract` et non `frames` seul** (story 11.14) : `frames`
    ne dit pas de quel objet il parle, et le releve du lot A comptait bien ce
    nom-la parmi les AMBIGUS le jour ou il a ete ecrit. Un nom neuf qui entre
    dans la liste que la story existe pour vider est une faute qu'il faut
    corriger sur-le-champ, pas reporter.
    """
    return _dossier_de_lot(
        project_dir, slug, EXTRACT_FRAMES_DIRNAME, LEGACY_FRAMES_DIRNAME)


def extract_frames_dir(
    project_dir: str | Path,
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    fps_short_name: str | None = None,
    version_rank: int | None = None,
) -> Path:
    """Return the extracted-frames directory for `rush_id` at `fps_target` (AC 1).

    `fps_short_name` et, depuis la story 5.29, `version_rank` sont
    **transmis tels quels** a `rush_dir_slug` : cette fonction ne compose
    aucun nom, elle assemble un chemin. Les laisser hors de la signature
    obligerait l'appelant qui veut la convention `_25s3` ou une nouvelle
    version a recomposer le slug lui-meme, c'est-a-dire a en ecrire une
    seconde recette -- exactement ce que ce module existe pour empecher.
    """
    return extract_frames_dir_from_slug(
        project_dir,
        rush_dir_slug(
            rush_id,
            fps_target,
            source_in_timecode=source_in_timecode,
            source_out_timecode=source_out_timecode,
            fps_short_name=fps_short_name,
            version_rank=version_rank,
        ),
    )


def scan_frames_dir(
    project_dir: str | Path,
    rush_id: str,
    fps_target: float | int,
    *,
    source_in_timecode: str | None = None,
    source_out_timecode: str | None = None,
    fps_short_name: str | None = None,
    version_rank: int | None = None,
) -> Path:
    """Return the reconstructed/rescanned frames directory for `rush_id` at `fps_target` (AC 1).

    Meme transmission que `extract_frames_dir`, et pour la meme raison : `frames/` et
    `frames-scannees/` d'un meme lot portent le MEME slug, et un mot-cle offert
    a l'un mais pas a l'autre ferait porter deux noms aux deux moities d'un
    meme lot.

    **`version_rank` est arrive ici APRES son jumeau, et l'ecart etait un
    defaut** (story 5.29, revue Opus du 2026-08-30) : la story avait offert le
    mot-cle a `extract_frames_dir` sans le donner a cette fonction, c'est-a-dire
    exactement ce que le paragraphe ci-dessus interdit -- les images
    rescannees d'une version 2 visaient le dossier de sortie du lot
    d'origine. Le defaut etait ecrit noir sur blanc dans cette docstring
    avant d'etre commis.
    """
    return scan_frames_dir_from_slug(
        project_dir,
        rush_dir_slug(
            rush_id,
            fps_target,
            source_in_timecode=source_in_timecode,
            source_out_timecode=source_out_timecode,
            fps_short_name=fps_short_name,
            version_rank=version_rank,
        ),
    )


def scan_frames_dir_from_slug(project_dir: str | Path, slug: str) -> Path:
    """Rendre `frames-scannees/<slug>/` a partir d'un slug **deja resolu**.

    Ajoute par la story 5.6. La chaine scan ne dispose pas toujours des bornes
    du lot: elles ne sont ni dans le payload QR ni deductibles d'un scan, si
    bien que `scan_frames_dir` -- qui recalcule le slug depuis
    `(rush_id, fps_target, bornes)` -- ne peut pas etre appelee pour un lot
    borne. Le slug, lui, se derive du QR seul (voir
    `scan_output_frames.derive_lot_dir_slug`), et c'est cette porte-la qu'il
    lui faut.

    L'existence de ce point d'entree evite surtout que l'appelant recompose
    le chemin a la main: le nom du dossier reste nomme une seule fois dans le
    depot, et la reconnaissance du nom d'avant (`EPIC11-ARB-171`) vit au meme
    endroit -- un appelant qui recomposerait la court-circuiterait.

    La garde de slug vit dans `_valider_le_slug`, partagee avec la famille des
    frames extraites. Les deux gardes du depot (`_relative_posix`,
    `_iter_absolute_path_violations`) font bien leur travail, mais elles
    s'appliquent au chemin **publie**, donc apres que l'octet est sur le disque
    (revue du 2026-08-08).
    """
    return _dossier_de_lot(
        project_dir, slug, SCAN_FRAMES_DIRNAME, LEGACY_OUTPUT_FRAMES_DIRNAME)


def est_strictement_sous_le_projet(
    project_dir: str | Path, candidat: str | Path
) -> bool:
    """`candidat` resout-il **strictement a l'interieur** de `project_dir` ?

    Ecrit ici, et une seule fois, parce que le depot a paye cette famille
    **trois** fois : `scan_frames_dir_from_slug` ci-dessus (« `Path("/proj") /
    "output-frames" / "/tmp/x"` vaut `/tmp/x` -- pathlib abandonne la partie
    gauche »), `project_maintenance._sous_le_projet` (l'incident du 2026-08-27,
    un fichier hors projet REELLEMENT detruit), et la story 6.8 (`R4` de sa
    revue, 2026-09-03 : un `scan_frames_dir` absolu faisait sortir un
    `ValueError` nu de `plan_encode`, et `"../hors-projet"` construisait un plan
    sur des frames etrangeres au projet). Les deux premieres redactions
    existaient deja quand la troisieme est arrivee : le lecteur neuf n'avait
    aucune des deux, et rien ne pouvait le lui dire.

    **On teste le RESULTAT, jamais la FORME du chemin declare**, et c'est la
    seule formulation qui ferme d'un coup les trois evasions mesurees par la
    revue du 2026-08-30 : une remontee ``"../../ailleurs"`` (que
    `is_absolute()` rend `False`), un **lien symbolique** de dossier (dont
    aucun composant n'est suspect), et ``"C:/Windows/..."`` (absolu sur la
    plateforme Windows que le NFR1 cible, relatif pour `PurePosixPath`).

    **Strictement**, et l'admettre etait un defaut : la racine du projet
    elle-meme est refusee, sans quoi un champ valant ``"."``, ``""`` ou
    ``"frames/.."`` designe le dossier projet entier.

    Ne rattrape **aucune** erreur de resolution : un `OSError` (boucle de liens,
    chemin trop long) traverse, l'appelant seul sachant en quel refus le
    traduire.
    """
    return Path(project_dir).resolve() in Path(candidat).resolve().parents


def outputs_dir(project_dir: str | Path) -> Path:
    """Rendre `outputs/`, dossier des masters video du projet (story 6.1).

    Ce helper existe pour la meme raison que `scan_frames_dir_from_slug`:
    eviter que l'appelant recompose `project_dir / "outputs"` a la main, ce qui
    redoublerait la constante et ferait diverger les deux ecritures au premier
    ajustement. Il ne cree rien -- `encode` a besoin de distinguer "le dossier
    n'existe pas encore" de "un **fichier** occupe cet emplacement", et un
    `mkdir` cache ici rendrait la seconde panne en `FileExistsError` nu.
    """
    return Path(project_dir) / OUTPUTS_DIRNAME


def scan_lot_dir(
    project_dir: str | Path, ingest_slug: str, version_rank: int | None = None
) -> Path:
    """Rendre le dossier canonique du lot de scan `scans/<slug>/` (story 5.1).

    Meme forme que `extract_frames_dir` et `scan_frames_dir`, a une difference de
    nature pres qu'il faut garder en tete: le segment terminal n'est **pas** une
    identite metier. A l'ingestion, le `lot_id` du lot n'est pas connu -- il est
    porte par le QR, que seule la story 5.2 decode. Le segment est donc un
    **slug operateur**: le nom du dossier fourni, ou une valeur declaree. D'ou
    l'absence de `rush_dir_slug` ici, et le nom du parametre.

    **`version_rank` versionne le scan** (`EPIC11-ARB-104`, Egan 2026-08-31 :
    « TOUT objet doit pouvoir etre ecrase ou versionne »). Motif, dans les
    mots d'Egan : on reprend une planche imprimee, on ajoute un point rouge
    dans un coin, on rescanne -- le contenu a change, l'identite non. Sans
    rang, l'outil refusait en proposant d'inventer un autre slug ou de vider
    le dossier : deux corvees manuelles, dont l'une detruit la version d'avant.

    Meme convention de suffixe que partout (`_v2`..`_v99`, `EPIC11-ARB-88`).
    """
    if version_rank is not None:
        from .naming import format_version_suffix

        return (Path(project_dir) / SCANS_DIRNAME
                / f"{ingest_slug}{format_version_suffix(version_rank)}")
    return Path(project_dir) / SCANS_DIRNAME / ingest_slug


def base_layout_dirs(project_dir: str | Path) -> dict[str, Path]:
    """Return the always-present v2 top-level directories, keyed by name."""
    project_dir = Path(project_dir)
    return {name: project_dir / name for name in BASE_SUBDIRS}


#: (rush_id, fps_target, source_in_timecode, source_out_timecode, version_rank)
_LotDirKey = tuple[str, "float | int", "str | None", "str | None", "int | None"]


def _iter_rush_fps_pairs(manifest: dict[str, Any]) -> list[_LotDirKey]:
    """Extract the per-lot keys used to namespace per-rush frame dirs.

    Since the v2.1 restructuring (`decisions-2026-08-04.md`), the target frame
    rate is a property of the **lot**: the pairs are read from `lots[]`, so a
    project holding several rushes, and several target rates per rush, yields
    one directory per lot instead of one shared rate for the whole project.

    Depuis la story 3.7, la cle porte aussi les **bornes** du lot
    (`lots[].source_in_timecode` / `source_out_timecode`), pour la meme raison:
    elles font partie de son nom de dossier. Sans elles, `ensure_project_layout`
    recreerait le dossier **non borne** d'un lot borne, c'est-a-dire un dossier
    vide qui n'appartient a aucun lot, a cote du vrai.

    Depuis la story 5.29, la cle porte aussi `lots[].version_rank`, pour la
    raison **identique** -- et le defaut avait bel et bien ete commis avant
    d'etre trouve en revue : sans lui, un projet dont le seul lot est une
    version 2 se voyait recreer le dossier de la version 1 a chaque appel,
    vide, tandis que le dossier reel du lot n'etait jamais cree.

    Transitional fallback for v2.0 manifests, which have no `lots[].fps_target`
    at all: `manifest["video"]["fps_target"]` is applied to every declared
    rush, exactly as before -- sans bornes, puisqu'un manifest v2.0 est par
    construction anterieur a la story 3.7. Rushes are skipped when no target
    rate can be resolved, since no frame directory can be derived.
    """
    keys: list[_LotDirKey] = []
    seen: set[_LotDirKey] = set()
    for lot in manifest.get("lots") or []:
        if not isinstance(lot, dict):
            continue
        rush_id = lot.get("rush_id")
        fps_target = lot.get("fps_target")
        if not rush_id or fps_target is None:
            continue
        rang = lot.get("version_rank")
        key = (
            rush_id,
            fps_target,
            lot.get("source_in_timecode"),
            lot.get("source_out_timecode"),
            rang if isinstance(rang, int) and not isinstance(rang, bool) else None,
        )
        if key not in seen:
            seen.add(key)
            keys.append(key)
    if keys:
        return keys

    # Repli v2.0: une seule cadence cible pour tout le projet.
    video = manifest.get("video")
    fps_target = video.get("fps_target") if isinstance(video, dict) else None
    if fps_target is None:
        return []

    for rush in manifest.get("rushes") or []:
        rush_id = rush.get("rush_id")
        if not rush_id:
            continue
        keys.append((rush_id, fps_target, None, None, None))
    return keys


def ensure_project_layout(
    project_dir: str | Path,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Create (idempotently) the v2 project arborescence and return the created paths.

    Cree toujours les quatre dossiers de base -- `scans/`, `planches/`,
    `logs/` et `versions/` (AC 1). La redaction d'avant en annoncait
    TROIS, `versions/` etant absent de la liste alors qu'il est dans
    `BASE_SUBDIRS` depuis la story 5.22 : la docstring disait moins que le
    code, et un lecteur qui s'y fiait cherchait un producteur inexistant
    pour ce dossier. `patches/` y est devenu `planches/`
    (`EPIC11-ARB-225`) ;
    when `manifest` declares lots carrying a `fps_target` (or, for a v2.0
    manifest, rushes plus a project-level `video.fps_target`), also creates
    the per-lot `extract-frames/<rush>_<fps>/` and
    `frames-scannees/<rush>_<fps>/` directories (AC 3), or the directories
    already written under the names of before, which are recognized and never
    renamed (`EPIC11-ARB-171`, story 11.14). Safe to call repeatedly on an existing or
    partially-present project directory: existing directories and their
    contents are left untouched (AC 4).
    """
    project_dir = Path(project_dir)
    created: dict[str, Path] = {}

    for name, path in base_layout_dirs(project_dir).items():
        path.mkdir(parents=True, exist_ok=True)
        created[name] = path

    if manifest is not None:
        for rush_id, fps_target, in_timecode, out_timecode, rang in _iter_rush_fps_pairs(
            manifest
        ):
            bornes = {
                "source_in_timecode": in_timecode,
                "source_out_timecode": out_timecode,
                "version_rank": rang,
            }
            frames_path = extract_frames_dir(project_dir, rush_id, fps_target, **bornes)
            output_frames_path = scan_frames_dir(
                project_dir, rush_id, fps_target, **bornes
            )
            frames_path.mkdir(parents=True, exist_ok=True)
            output_frames_path.mkdir(parents=True, exist_ok=True)
            # Cle indexee par le slug complet, pas par le seul `rush_id`: un
            # meme rush peut avoir plusieurs lots a des cadences differentes,
            # et une cle par rush en ecraserait tous sauf un.
            slug = rush_dir_slug(rush_id, fps_target, **bornes)
            created[f"{EXTRACT_FRAMES_DIRNAME}:{slug}"] = frames_path
            created[f"{SCAN_FRAMES_DIRNAME}:{slug}"] = output_frames_path

    return created
