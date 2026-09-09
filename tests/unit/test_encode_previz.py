"""Tests du contrat de donnees de previz d'encodage (story 6.4).

Quatrieme jumelle de `test_extraction_previz.py` (3.5), `test_pdf_previz.py`
(4.9) et `test_scan_previz.py` (5.8): purete AST du module **et** du socle,
enveloppe `previz-1` reprise telle quelle avec `kind = "encode"`, projection
verbatim de la decision de 6.1, serialisation canonique deterministe, empreinte
de peremption, vocabulaire ferme.

Deux exigences structurent ce fichier, et elles ne se remplacent pas.

**Des sentinelles incoherentes** pour les tests unitaires: les entrees sont des
objets structurels (`SimpleNamespace`) faconnes comme les vrais producteurs, et
volontairement faux entre eux -- un verdict qui annonce 13 frames trouvees sur
une sequence qui en porte 3, une cadence qui ne colle pas au timecode, une
resolution sans rapport avec la source. Si le module recalculait quoi que ce
soit, la sentinelle serait corrigee au lieu d'etre transportee.

**Contre le vrai producteur** pour la confrontation: `encode` est importe
**ici**, jamais par le module -- il tire `subprocess` par transitivite. C'est le
test qui confronte les deux vocabulaires litteraux caractere par caractere, et
qui projette de vraies instances de `TargetResolution`, `TimecodePlan` et
`CompletenessVerdict`, de sorte qu'un renommage de champ chez 6.1 fasse tomber
ces tests au lieu de laisser casser le premier consommateur reel.

Regle des fabriques du `CLAUDE.md`: :func:`make_frames` produit **trois** frames
distinguables (rangs, chemins, timecodes et drapeau de mire tous differents), et
la frame visee par les tests d'appariement est placee **ailleurs qu'en premiere
position**. Une previz d'encodage projette une sequence ordonnee, c'est-a-dire
exactement la structure ou le mutant `M33` de 5.6 est passe inapercu sous 165
tests verts. La reserve de 6.1 (son AC 19) est tenue par
:func:`test_le_lot_d_une_seule_frame_est_projete`: c'est la borne basse **reelle**
du depot (`rush_test_235_1920x817_25fps_1-81a74b3c`, `expected_frame_count: 1`),
et c'est le cas ou une sequence ordonnee degenere en n'ayant plus d'ordre
observable.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import encode, encode_previz, previz_common, video_metadata
from mixed_media_utility.encode_previz import (
    build_encode_previz,
    encode_previz_to_json_dict,
)
from mixed_media_utility.io.manifest import _iter_absolute_path_violations

MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "encode_previz.py"
COMMON_MODULE_PATH = REPO_ROOT / "src" / "mixed_media_utility" / "previz_common.py"

GENERATED_AT = "2026-08-11T12:00:00Z"

EPE = encode_previz.EncodePrevizError


# ---------------------------------------------------------------------------
# Fabriques structurelles: des sentinelles volontairement incoherentes
# ---------------------------------------------------------------------------
#
# Aucune de ces valeurs n'est plausible ensemble: un verdict qui annonce 13
# frames trouvees pour une sequence qui en porte 3, une cadence de 12,5 images
# par seconde avec des timecodes a 25, une resolution de sortie plus grande que
# la source sur un des axes. C'est le point: le document doit les transporter
# telles quelles.


def make_frame(rank, name, timecode, synthetic=False):
    return SimpleNamespace(
        output_rank=rank,
        frame_path_relative=f"frames/lot-a/{name}",
        frame_timecode=timecode,
        synthetic=synthetic,
    )


def make_frames():
    """Trois frames **distinguables**, et la mire n'est pas la premiere.

    Regle des fabriques: des valeurs differentes, jamais un remplissage
    uniforme. Une permutation ne se voit que si les elements different, et un
    `find` fautif qui rend toujours le premier element ne se demasque que si la
    cible est ailleurs -- ici la seule mire est en **deuxieme** position.
    """
    return [
        make_frame(0, "f000.tif", "01:00:00:00"),
        make_frame(1, "f001.tif", "01:00:00:01", synthetic=True),
        make_frame(2, "f002.tif", "01:00:00:02"),
    ]


def make_resolution(**overrides):
    resolution = SimpleNamespace(
        requested="hd1080",
        origin="defaut",
        resolution_id="hd1080",
        size=(1920, 1080),
    )
    for key, value in overrides.items():
        setattr(resolution, key, value)
    return resolution


#: Les **trois** combinaisons de timecode que `encode.plan_timecode` produit
#: litteralement, et il n'y en a pas d'autre (lecture de `encode.py:1290-1320`):
#:
#: * `complet` -- le lot porte `timecode_base_fps` et le depart est exprimable
#:   dans la base du master: les trois champs sont poses;
#: * `hors base du master` -- le depart est legal dans sa base source et
#:   n'existe pas dans celle du master: `emitted` est `None` **alors que**
#:   `base_rate` et `manifest_value` sont poses. C'est le cas que le module
#:   nomme dans son propre vocabulaire (`TIMECODE_DE_DEPART_HORS_BASE_DU_
#:   MASTER`) et que son producteur emet en toutes lettres;
#: * `aucun timecode reinjecte` -- le lot ne porte pas `timecode_base_fps` (lot
#:   ne du scan) ou n'a aucun depart: les trois champs sont `None`.
#:
#: La combinaison symetrique (`emitted` pose, `base_rate` absent) n'est **pas**
#: constructible par le producteur: `emitted` est calcule a partir de
#: `base_rate`, donc il n'existe jamais sans lui. Elle est neanmoins admise par
#: le protocole structurel, et :func:`test_the_timecode_fields_are_omitted_one_by_one`
#: la couvre a ce titre.
#:
#: Regle des fabriques du `CLAUDE.md`, appliquee a un **triplet** plutot qu'a
#: une collection: une fabrique qui remplit ses trois champs ou les annule tous
#: les trois rend invisible toute erreur d'appariement entre eux -- neuvieme
#: occurrence de la meme regle, trouvee par mutation et par aucun test. Quatre
#: mutants survivaient a 202 tests verts en conditionnant un champ a un autre,
#: dont un qui faisait disparaitre la base de validation de l'**empreinte de
#: decision** dans le cas ci-dessus, rendant deux lots a bases differentes
#: indistinguables.
TIMECODE_CASES = {
    "complet": {},
    "hors base du master": {"emitted": None},
    "aucun timecode reinjecte": {
        "emitted": None,
        "manifest_value": None,
        "base_rate": None,
    },
}


def make_timecode(cas="complet", **overrides):
    """Un `TimecodePlan` structurel, dans l'une des combinaisons reelles.

    Les trois valeurs par defaut sont **distinctes deux a deux**: deux valeurs
    qui coincident sur toutes les fixtures cachent une interversion.
    """
    plan = SimpleNamespace(
        # Volontairement incoherent avec `fps_target_exact` ("25/2"): un depart
        # a 25 images sur un master a 12,5. Le document le transporte.
        emitted="01:00:00:00",
        # **Different** de `emitted`, et jamais un remplissage uniforme: 6.1
        # exprime le depart dans la base du master, si bien que la valeur lue au
        # manifest et la valeur emise ne coincident pas toujours.
        manifest_value="00:59:59:12",
        base_rate="25/1",
    )
    for key, value in TIMECODE_CASES[cas].items():
        setattr(plan, key, value)
    for key, value in overrides.items():
        setattr(plan, key, value)
    return plan


def make_verdict(**overrides):
    verdict = SimpleNamespace(
        # 13 trouvees pour 3 frames dans la sequence: si le module recomptait,
        # cette valeur serait corrigee.
        expected=13,
        found=13,
        synthetic_present=("f001.tif",),
        synthetic_missing=("f009.tif",),
        missing_pages=(4, 7),
        complete=False,
    )
    for key, value in overrides.items():
        setattr(verdict, key, value)
    return verdict


def build(**overrides):
    """Un document `planned` complet, sur les sentinelles ci-dessus."""
    arguments = dict(
        generated_at_utc=GENERATED_AT,
        project_id="proj-a",
        lot_id="lot-a",
        profile_id="prores_hq",
        container="mov",
        lot_state="scan",
        resolution=make_resolution(),
        source_size=(3307, 1860),
        frames=make_frames(),
        exact_frame_rate="25/2",
        timecode=make_timecode(),
        timecode_reliability="reliable",
        verdict=make_verdict(),
        container_tags={"project_id": "proj-a", "lot_id": "lot-a"},
        master_path_relative="outputs/lot-a_prores_hq.mov",
        estimated_bytes=1234567,
        nonconforming_files=("intrus.txt",),
        empty_files=("f003.tif",),
        declared_bounds=("01:00:00:00", "01:00:00:12"),
        encode_warnings=(
            encode_previz.APPROXIMATION_SRGB_TAGUEE_REC709,
            encode_previz.LOT_INCOMPLET_ASSUME,
        ),
    )
    arguments.update(overrides)
    return build_encode_previz(**arguments)


def build_refused(**overrides):
    arguments = dict(
        generated_at_utc=GENERATED_AT,
        project_id="proj-a",
        lot_id="lot-a",
        profile_id="prores_hq",
        container="mov",
        state=encode_previz.ENCODE_PREVIZ_STATE_REFUSED,
        refusal_code="TIRAGES_MULTIPLES",
        refused_candidates=(
            "lot-a-t1 (etat scan, cardinal attendu 13, ...)",
            "lot-a-t2 (etat scan, cardinal attendu 5, ...)",
        ),
    )
    arguments.update(overrides)
    return build_encode_previz(**arguments)


def rendered(previz):
    return previz_common.canonical_json(encode_previz_to_json_dict(previz))


def decision_of(previz):
    return encode_previz_to_json_dict(previz)["fingerprints"]["decision"]


# ---------------------------------------------------------------------------
# AC 14: purete verrouillee par analyse AST, socle compris
# ---------------------------------------------------------------------------

ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    # `copy` est de la bibliotheque standard et strictement pur: il sert a rendre
    # les tags de conteneur par copie profonde, pour que le document dit « gele »
    # le soit reellement (regression reelle du 2026-08-05 chez 3.5).
    "copy",
    "dataclasses",
    "typing",
}
ALLOWED_RELATIVE_IMPORTS = {"previz_common"}

# `__import__` et `compile` fermes aussi (revue 4.9): un import dynamique
# contournerait la liste blanche sans produire de noeud Import. `compile` n'est
# interdit qu'en nom nu: `re.compile` est legitime et n'a rien du builtin.
FORBIDDEN_CALL_NAMES = {
    "open",
    "print",
    "input",
    "exec",
    "eval",
    "__import__",
    "compile",
}
FORBIDDEN_ATTR_CALL_NAMES = FORBIDDEN_CALL_NAMES - {"compile"}

FORBIDDEN_MODULES = {
    "subprocess",
    "cv2",
    "PIL",
    "numpy",
    "pathlib",
    "argparse",
    "os",
    "sys",
    "shutil",
    "jsonschema",
    "requests",
    "tkinter",
    "PySide6",
    "PyQt5",
    "PyQt6",
    "wx",
    "kivy",
    "reportlab",
    "ffmpeg",
    "pypdfium2",
}

# Liste blanche du socle, propre a lui: `re`, `json`, `hashlib` et `datetime` y
# sont legitimes -- ce sont la recette de canonicalisation, l'empreinte et la
# validation d'horodatage.
COMMON_ALLOWED_ABSOLUTE_IMPORTS = {
    "__future__",
    "datetime",
    "hashlib",
    "json",
    "re",
    "typing",
}
COMMON_ALLOWED_RELATIVE_IMPORTS = {
    "codec_profiles",
    "source_confirmation",
    # Ajoute par `main` (`52c0db3`) : les gardes `bool`-avant-`int`
    # passent toutes par `numeric_guards`. La liaison garde les deux
    # cotes plutot que d'en perdre un.
    "numeric_guards",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _import_offenders(path: Path, absolute: set[str], relative: set[str]) -> list[str]:
    offenders = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in absolute:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if (node.module or "") not in relative:
                    offenders.append(f".{node.module}")
            elif (node.module or "") not in absolute:
                offenders.append(node.module or "")
    return offenders


def test_module_imports_are_whitelisted() -> None:
    assert (
        _import_offenders(
            MODULE_PATH, ALLOWED_ABSOLUTE_IMPORTS, ALLOWED_RELATIVE_IMPORTS
        )
        == []
    )


def test_the_shared_previz_module_is_pure_too() -> None:
    """Quatrieme copie d'une couverture deja tenue depuis 5.8, et c'est voulu.

    Les tests AST des quatre jumelles n'inspectent que les imports **directs** de
    leur propre fichier: si `previz_common` importait `cv2`, les quatre
    resteraient verts tout en ne garantissant plus rien. Le mandat du
    `deferred-work.md` est d'elargir **sa propre** liste blanche au module
    commun; ce test le tient, sans surestimer sa nouveaute.
    """
    assert (
        _import_offenders(
            COMMON_MODULE_PATH,
            COMMON_ALLOWED_ABSOLUTE_IMPORTS,
            COMMON_ALLOWED_RELATIVE_IMPORTS,
        )
        == []
    )


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_calls_no_io_primitive(path: Path) -> None:
    offenders = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALL_NAMES:
                offenders.append((func.id, node.lineno))
            if (
                isinstance(func, ast.Attribute)
                and func.attr in FORBIDDEN_ATTR_CALL_NAMES
            ):
                offenders.append((func.attr, node.lineno))
    assert offenders == []


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_references_no_forbidden_module(path: Path) -> None:
    referenced = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            referenced.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            referenced.add((node.module or "").split(".")[0])
    assert referenced & FORBIDDEN_MODULES == set()


@pytest.mark.parametrize("path", [MODULE_PATH, COMMON_MODULE_PATH])
def test_module_never_touches_the_io_package(path: Path) -> None:
    """Le detecteur de chemins absolus existe (`io/manifest`) et c'est le test
    qui l'importe, jamais le module (AC 9)."""
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert not (node.module or "").startswith("io")


def test_module_never_imports_its_producer_nor_the_manifest_writer() -> None:
    """Le typage structurel n'est pas un confort: c'est ce qui tient l'AC 14.

    `encode` tire `subprocess` par transitivite (via `codec_profiles`), et
    `io/encode_manifest` est le perimetre de 6.5, que cette story ne projette
    pas. Un import de complaisance -- ne serait-ce que pour lire une constante de
    vocabulaire -- ferait entrer le lanceur d'encodage dans un contrat de
    donnees.
    """
    forbidden = {
        "encode",
        "encode_manifest",
        "codec_profiles",
        "video_metadata",
        "scan_output_frames",
        "cli",
    }
    imported = set()
    for node in ast.walk(_tree(MODULE_PATH)):
        if isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[-1])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[-1] for alias in node.names)
    assert imported & forbidden == set()


def test_encode_really_pulls_subprocess_transitively() -> None:
    """Le motif du test precedent est **mesure**, pas suppose.

    Sans cette confrontation, la liste d'interdits ci-dessus serait une opinion:
    on interdirait `encode` « au cas ou ». Il tire bien `codec_profiles`, qui
    importe `subprocess`.
    """
    encode_imports = set()
    for node in ast.walk(
        _tree(REPO_ROOT / "src" / "mixed_media_utility" / "encode.py")
    ):
        if isinstance(node, ast.ImportFrom):
            encode_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            encode_imports.update(alias.name for alias in node.names)
    assert "codec_profiles" in encode_imports
    profiles_imports = set()
    for node in ast.walk(
        _tree(REPO_ROOT / "src" / "mixed_media_utility" / "codec_profiles.py")
    ):
        if isinstance(node, ast.Import):
            profiles_imports.update(alias.name for alias in node.names)
    assert "subprocess" in profiles_imports


def test_requirements_gain_no_dependency_from_this_story() -> None:
    """Une dependance ajoutee ici serait le signal d'une preemption d'Epic 7."""
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    packages = {
        line.split("==")[0].split(">=")[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert packages == {
        "ffmpeg-python",
        # `EPIC11-ARB-253` / `-254` (2026-09-06) : deux RENOMMAGES, pas deux
        # ajouts, portes ici le 2026-09-07 par `5635d70a` qui a aligne
        # `requirements.txt` sur `pyproject.toml`.
        # `opencv-contrib-python` -> `opencv-python-headless` : les roues
        # non-headless lient leur binaire a douze bibliotheques systeme
        # graphiques absentes d'une machine vierge, et `import cv2` y echoue sur
        # `libGL.so.1` avant la premiere ligne du produit. Les 51 symboles
        # `cv2.*` employes par `src/` ont ete testes un a un contre la roue
        # non-contrib, aucun ne manque -- l'ArUco a quitte `contrib` pour
        # `objdetect` en 4.7.
        # `pyside6` -> `pyside6-essentials` : le metapaquet tirait 401 Mo
        # d'Addons (dont un Chromium complet pour QtWebEngine) qu'aucun fichier
        # du depot n'importe.
        # L'ensemble reste epingle en egalite STRICTE : une dependance
        # reellement AJOUTEE continue de faire rougir ce test.
        "opencv-python-headless",
        "numpy",
        "pillow",
        "reportlab",
        "pypdfium2",
        "jsonschema",
        # AJOUTE PAR LA STORY 8.10, et porte ici au triage de la revue 8.12 le
        # 2026-09-08 -- il aurait du l'etre dans le meme mouvement. `pyyaml`
        # entre dans `requirements.txt` parce que
        # `tests/unit/test_politique_lfs.py` lit les workflows sur le YAML
        # ANALYSE et que sa lecture ne doit plus pouvoir SAUTER : elle gardait,
        # derriere un `importorskip`, la politique dont l'oubli a sature le
        # quota LFS de 10 Go en deux jours.
        #
        # Ce n'est donc PAS une preemption d'Epic 7, ce que cette frontiere
        # existe pour attraper -- c'est une dependance de BANC, ajoutee
        # deliberement et documentee a sa ligne. L'ensemble epingle se deplace
        # DELIBEREMENT, jamais par accommodation d'un rouge.
        "pyyaml",
        # Reconciliation 11/EPIC11-ARB-250 (2026-09-06) : `segno` est l'ajout
        # MANDATE par l'arbitrage qui sort l'ENCODAGE QR d'OpenCV. Meme regime
        # que `pyside6` / `pytest-qt` en 2026-08-24 et `textual` en 2026-08-28 :
        # l'ensemble reste epingle en egalite STRICTE, pour que toute dependance
        # future non mandatee continue de faire rougir ce test. Le module previz
        # de cette fiche n'importe pas `segno` (verrou AST de purete ci-dessus)
        # -- `qr_codes.py` est le seul module de `src/` a l'importer, et
        # `test_encodeur_qr_segno.py` le mesure.
        #
        # Le motif, parce qu'une reconciliation sans motif est une tolerance
        # muette : la ligne 4.10/4.11 d'OpenCV ENCODE un symbole malforme
        # au-dela de la version 7, illisible par tout lecteur. Le plancher de
        # version qui aurait ferme le defaut sortait macOS 12 x86_64 de la
        # compatibilite (4.10.0.84 est la derniere roue `macosx_12_0_x86_64`) ;
        # `segno` publie une roue `py3-none-any` et n'exclut personne.
        "segno",
        "pytest",
        # Reconciliation 7.0 (2026-08-24): pyside6 et pytest-qt sont les deux
        # ajouts MANDATES par la story 7.0 (socle GUI -- sa fiche les specifie
        # nommement, AC 1). L'Epic 7 n'est plus une preemption a interdire mais
        # un developpement en cours. L'ensemble reste epingle en egalite
        # stricte ; l'intention et la docstring sont intactes (meme geste que
        # la reconciliation de test_scan_previz.py par la story 5.26).
        "pyside6-essentials",
        "pytest-qt",
        # Reconciliation 5.x/11.0 (2026-08-28) : `textual` est l'ajout
        # MANDATE par la story 11.0 (socle TUI, AC 6.2 le specifie nommement,
        # epingle par serie majeure comme les autres lignes). Meme regime que
        # `pyside6` / `pytest-qt` en 2026-08-24 : l'ensemble reste epingle en
        # egalite STRICTE, pour que toute dependance future non mandatee
        # continue de faire rougir ce test. Le module previz de cette fiche
        # n'importe toujours aucun des trois (verrou AST de purete ci-dessus).
        #
        # **Et ce jour est arrive** : la liaison du 2026-09-01 amene le paquet
        # `tui/` sur cette branche. La phrase precedente annoncait « ce banc
        # rougira si l'un vient sans l'autre » -- il a rougi, sur les trois
        # bancs previz a la fois, exactement comme elle le promettait. La ligne
        # revient donc, et `requirements.txt` la porte deja.
        "textual",
    }


# ---------------------------------------------------------------------------
# AC 5: une previz n'autorise rien -- les trois tests du motif 3.5
# ---------------------------------------------------------------------------

#: Les noms de la couche qui **lance** un encodage. Ils appartiennent a 6.0 et
#: 6.1; ce module ne doit en citer aucun, ni en import, ni en attribut, ni en
#: nom nu.
LAUNCHING_LAYER_NAMES = {
    "run_encode",
    "build_encode_command",
    "execute_plan",
    "plan_encode",
    "reserve_master_path",
    "prepare_output_directory",
    "sweep_encode_residues",
    "check_output_destination",
    "EncodeCommandResult",
    "subprocess",
}

LAUNCH_PREFIXES = (
    "run",
    "launch",
    "start",
    "execute",
    "confirm",
    "approve",
    "authorize",
    "trigger",
    "persist",
    "save",
    "write",
    "apply",
    "validate_",
)

#: Prefixes verifies sur les **fonctions** seulement, motif de `RELAUNCH_
#: PREFIXES` en 5.8: en constante ils seraient des noms de domaine legitimes.
#:
#: Le mot `encode` **nu** ne peut pas y figurer, et la mesure est simple: la
#: regle de nommage de la famille impose `encode_previz_to_json_dict`
#: (`previz_to_json_dict` en 3.5, `pdf_previz_to_json_dict` en 4.9,
#: `scan_previz_to_json_dict` en 5.8), donc l'interdire interdirait le nom que la
#: famille exige. Ce sont les **verbes de lancement** qui sont fermes, pas le mot
#: du domaine.
RELAUNCH_PREFIXES = (
    "encode_lot",
    "encode_master",
    "encode_sequence",
    "reencode",
    "transcode",
    "mux",
    "ffmpeg",
    "ffprobe",
    "probe",
)


def test_module_never_references_the_launching_layer_of_stories_6_0_and_6_1() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = _tree(MODULE_PATH)
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            referenced.update(alias.name for alias in node.names)
    assert referenced & LAUNCHING_LAYER_NAMES == set()
    # Textuellement aussi: une chaine `"run_encode"` passee a un dispatcher
    # echapperait a l'AST.
    for banned in ("run_encode", "build_encode_command", "subprocess.run"):
        assert banned not in source


def test_module_exposes_no_launch_function() -> None:
    public_names = [
        node.name
        for node in ast.walk(_tree(MODULE_PATH))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert set(public_names) <= set(encode_previz.__all__)
    for name in public_names + list(encode_previz.__all__):
        assert not name.lower().startswith(LAUNCH_PREFIXES), name
    for name in public_names:
        assert not name.lower().startswith(RELAUNCH_PREFIXES), name


def test_document_carries_no_consent_and_no_trigger() -> None:
    """Le document ne porte pas la reponse au `--yes` de 6.1, ni `--overwrite`.

    `EncodePlan` porte bien `overwrite`, et il **n'entre pas** au document: c'est
    un consentement, et il se rejoue integralement au lancement quelle que soit
    la fraicheur de ce document.
    """
    text = rendered(build())
    for banned in (
        "granted",
        "consent",
        "confirmed",
        "approved",
        "authorize",
        "overwrite",
        "accept",
        "yes",
    ):
        assert banned not in text
    assert "overwrite" not in MODULE_PATH.read_text(encoding="utf-8").replace(
        "« overwrite »", ""
    ).replace("EncodePlan.overwrite", "")


def test_the_builder_refuses_an_unknown_keyword_such_as_overwrite() -> None:
    """Le consentement n'a pas de porte d'entree, meme mal nommee."""
    with pytest.raises(TypeError):
        build(overwrite=True)


# ---------------------------------------------------------------------------
# AC 1: l'enveloppe vient du socle, integralement
# ---------------------------------------------------------------------------


def test_envelope_comes_from_the_shared_module() -> None:
    document = encode_previz_to_json_dict(build())
    assert list(document)[:4] == list(previz_common.ENVELOPE_FIELDS)
    assert document["previz_schema_version"] == previz_common.PREVIZ_SCHEMA_VERSION
    assert document["previz_schema_version"] == "previz-1"
    assert document["kind"] == "encode"
    assert document["state"] == previz_common.PREVIZ_STATE_PLANNED == "planned"


def test_nothing_of_the_shared_module_is_redeclared() -> None:
    """Rien du socle n'est redeclare: le point de la jonction de 5.8."""
    assigned = {
        target.id
        for node in ast.walk(_tree(MODULE_PATH))
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in ast.walk(_tree(MODULE_PATH))
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    defined = {
        node.name
        for node in ast.walk(_tree(MODULE_PATH))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in previz_common.__all__:
        if name == "PREVIZ_SCHEMA_VERSION":
            continue
        assert name not in defined, name
        # `ENCODE_PREVIZ_STATE_PLANNED` **assigne** `PREVIZ_STATE_PLANNED`, il ne
        # le redeclare pas: c'est l'alias que 4.9 a pose (`PDF_PREVIZ_STATE_
        # PLANNED = PREVIZ_STATE_PLANNED`).
        assert name not in assigned, name


def test_envelope_head_is_called_with_the_document_values_not_the_constants() -> None:
    """Un document fige sous une autre version se rend tel qu'il a ete construit."""
    previz = build()
    ancien = encode_previz.EncodePreviz(
        previz_schema_version="previz-0",
        kind=previz.kind,
        state=previz.state,
        generated_at_utc=previz.generated_at_utc,
        subject=previz.subject,
        warnings=previz.warnings,
        plan=previz.plan,
        fingerprints=previz.fingerprints,
    )
    assert encode_previz_to_json_dict(ancien)["previz_schema_version"] == "previz-0"


def test_envelope_head_requires_its_schema_version() -> None:
    """Le parametre est obligatoire et sans defaut (revue 5.8, couche 1 F2)."""
    with pytest.raises(TypeError):
        previz_common.envelope_head(
            kind="encode", state="planned", generated_at_utc=GENERATED_AT
        )


# ---------------------------------------------------------------------------
# AC 15: le durcissement d'enveloppe, tranche **ici** plutot qu'au socle
# ---------------------------------------------------------------------------


def test_the_shared_envelope_head_still_lies_and_that_is_measured() -> None:
    """La mesure du finding differe, refaite sur le depot livre.

    Elle est conservee parce que la story tranche de **ne pas** durcir le socle
    (une modification de socle imposerait un `error_type` obligatoire a quatre
    sites d'appel dans trois modules livres, et un `error_type` par defaut
    repeterait le defaut que la revue 5.8 F2 a ferme sur `schema_version`). Le
    trou est donc ferme **au niveau de ce document**, et ce test dit exactement
    ce qui reste ouvert au socle.
    """
    menteur = previz_common.envelope_head(
        kind=None, state=42, generated_at_utc=[], schema_version="previz-1"
    )
    assert menteur == {
        "previz_schema_version": "previz-1",
        "kind": None,
        "state": 42,
        "generated_at_utc": [],
    }
    assert previz_common.canonical_json(menteur) == (
        '{"generated_at_utc":[],"kind":null,"previz_schema_version":"previz-1",'
        '"state":42}'
    )


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("previz_schema_version", None),
        ("previz_schema_version", ""),
        # Truthy mais **pas** une chaine: sans le `isinstance`, ces trois-la
        # traversent le durcissement et ne sont rattrapes par aucune garde
        # d'aval -- `previz_schema_version` n'en a pas, et un horodatage en
        # liste sort tel quel de `envelope_head`.
        ("previz_schema_version", 42),
        ("generated_at_utc", ["2026-08-11T12:00:00Z"]),
        ("generated_at_utc", 20260811),
        ("kind", None),
        ("kind", 42),
        ("state", 42),
        ("state", ""),
        ("generated_at_utc", []),
        ("generated_at_utc", None),
    ],
)
def test_a_hand_built_document_cannot_carry_a_lying_envelope(champ, valeur) -> None:
    """Le chemin est joignable sans le builder: c'est le motif de la story 7.4."""
    previz = build()
    champs = dict(
        previz_schema_version=previz.previz_schema_version,
        kind=previz.kind,
        state=previz.state,
        generated_at_utc=previz.generated_at_utc,
        subject=previz.subject,
        warnings=previz.warnings,
        plan=previz.plan,
        fingerprints=previz.fingerprints,
    )
    champs[champ] = valeur
    with pytest.raises(EPE):
        encode_previz.EncodePreviz(**champs)


def test_a_hand_built_document_cannot_carry_a_lying_timestamp() -> None:
    """Le champ de **fraicheur** est celui ou mentir coute le plus cher.

    Le durcissement d'enveloppe se contentait ici d'une « chaine non vide »,
    alors que toute la comparaison a l'heure courante et tout le mecanisme de
    peremption dependent de ce champ: `generated_at_utc="pasunedate"` traversait
    le chemin « document edite hors builder » que ce durcissement existe pour
    fermer.
    """
    previz = build()
    for menteur in ("pasunedate", "2026-08-11 12:00:00", "2026-02-30T25:61:61Z"):
        with pytest.raises(EPE):
            encode_previz.EncodePreviz(
                previz_schema_version=previz.previz_schema_version,
                kind=previz.kind,
                state=previz.state,
                generated_at_utc=menteur,
                subject=previz.subject,
                warnings=previz.warnings,
                plan=previz.plan,
                fingerprints=previz.fingerprints,
            )


def test_a_hand_built_document_cannot_carry_an_unknown_refusal_code() -> None:
    """Le vocabulaire ferme vaut aussi hors du builder: un document edite
    pouvait porter un motif que 6.1 ne connait pas, et l'interface l'aurait
    affiche tel quel."""
    refuse = build_refused()
    with pytest.raises(EPE, match="Motif de refus"):
        encode_previz.EncodePreviz(
            previz_schema_version=refuse.previz_schema_version,
            kind=refuse.kind,
            state="refused",
            generated_at_utc=refuse.generated_at_utc,
            subject=refuse.subject,
            warnings=refuse.warnings,
            refusal=encode_previz.EncodePrevizRefusal(code="N_IMPORTE_QUOI"),
        )


def test_a_hand_built_document_cannot_carry_a_broken_subject_or_an_empty_plan() -> None:
    """Deux cas que le builder refuse et que le chemin direct laissait passer.

    Un `subject` absent explosait a la **serialisation**, en `AttributeError`
    nue, hors de la hierarchie promise; un plan a sequence vide se rendait avec
    `"sequence": []`, c'est-a-dire en annoncant un encodage sans image que 6.1
    refuse (`DOSSIER_DE_LOT_VIDE`) avant meme d'avoir un plan.
    """
    previz = build()
    with pytest.raises(EPE, match="subject"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
            subject=None,
            warnings=previz.warnings,
            plan=previz.plan,
            fingerprints=previz.fingerprints,
        )
    with pytest.raises(EPE, match="sans sequence"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=dataclasses.replace(previz.plan, sequence=()),
            fingerprints=previz.fingerprints,
        )


def test_a_hand_built_document_cannot_carry_a_foreign_kind() -> None:
    previz = build()
    with pytest.raises(EPE):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind="scan",
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=previz.plan,
            fingerprints=previz.fingerprints,
        )


# ---------------------------------------------------------------------------
# AC 6 (revision 3): le vocabulaire est FRANCOPHONE, parce que son producteur
# l'est -- confronte caractere par caractere au vrai tuple
# ---------------------------------------------------------------------------


def test_the_warning_vocabulary_mirrors_its_producer_character_for_character() -> None:
    assert (
        encode_previz.ENCODE_PREVIZ_WARNING_CODES == encode.ENCODE_INFORMATIONAL_CODES
    )
    for mine, theirs in zip(
        encode_previz.ENCODE_PREVIZ_WARNING_CODES, encode.ENCODE_INFORMATIONAL_CODES
    ):
        assert list(mine) == list(theirs)


def test_the_refusal_vocabulary_mirrors_its_producer_character_for_character() -> None:
    assert encode_previz.ENCODE_PREVIZ_REFUSAL_CODES == encode.ENCODE_REFUSAL_CODES
    for mine, theirs in zip(
        encode_previz.ENCODE_PREVIZ_REFUSAL_CODES, encode.ENCODE_REFUSAL_CODES
    ):
        assert list(mine) == list(theirs)


def test_the_two_vocabularies_are_disjoint_and_cover_the_producer() -> None:
    """Un refus remplace le plan, un constat l'accompagne: jamais le meme seau."""
    warnings = set(encode_previz.ENCODE_PREVIZ_WARNING_CODES)
    refusals = set(encode_previz.ENCODE_PREVIZ_REFUSAL_CODES)
    assert warnings & refusals == set()
    assert warnings | refusals == set(encode.ENCODE_CODES)
    assert len(encode_previz.ENCODE_PREVIZ_WARNING_CODES) == len(warnings) == 12
    # 29 depuis la story 6.6 (2026-08-13): + CADENCE_SOURCE_MANQUANTE,
    # CADENCE_SOURCE_REDONDANTE, puis MAINTIEN_DE_FRAME_NON_POSITIF,
    # QUEUE_DE_LOT_INEXPLOITABLE (revue en trois couches). **30 depuis la
    # liaison du 2026-09-01** : `RANGS_DE_MASTER_EPUISES` (`EPIC11-ARB-89`,
    # versionnage des masters), que `main` avait pose au producteur sans son
    # miroir -- ce cardinal ecrit en clair est exactement ce qui l'a nomme.
    # **31 depuis la story 11.8** : `VERSION_ET_ECRASEMENT_COMBINES`
    # (`EPIC11-ARB-89`, AC 4.1), pose au producteur ET ici dans le meme diff.
    # **32 depuis la story 6.8** (`EPIC11-ARB-190`) : `RECONSTRUCTION_INCONNUE`,
    # pose lui aussi au producteur ET ici dans le meme diff. Ce cardinal ecrit
    # en clair est ce qui OBLIGE a le dire : c'est lui qui a nomme l'oubli du
    # miroir a la liaison du 2026-09-01, et le monter est le geste attendu, pas
    # un contournement.
    assert len(encode_previz.ENCODE_PREVIZ_REFUSAL_CODES) == len(refusals) == 32


def test_the_vocabulary_is_francophone_where_the_family_spelled_english() -> None:
    """Le bornage « famille anglophone » de la premiere redaction est faux ici.

    Les trois jumelles nomment le lot troue `LOT_INCOMPLETE`; le producteur de
    celle-ci ecrit `LOT_INCOMPLET`, et c'est **son** orthographe qui vaut. Le
    document ne doit pas porter deux orthographes du meme fait.
    """
    assert "LOT_INCOMPLET" in encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    assert "LOT_INCOMPLETE" not in encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    assert "LOT_INCOMPLETE" not in encode_previz.ENCODE_PREVIZ_WARNING_CODES
    assert (
        "CARDINAL_ATTENDU_INDETERMINABLE"
        in encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    )
    assert (
        "EXPECTED_FRAME_COUNT_INDETERMINABLE"
        not in encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    )
    # Le seul code anglais du lot vient bien du producteur, deja inconsistant.
    assert (
        "HETEROGENEOUS_FRAME_SHAPES" in encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    )


#: Les deux seuls caracteres hors ASCII que la famille s'autorise, et c'est
#: **mesure** plutot que decrete: les cinq modules de la famille en portent
#: (`previz_common`, les trois jumelles et celui-ci), et la regle du `CLAUDE.md`
#: porte sur les **accents** -- « les fichiers de story sont rediges en ASCII
#: (sans accents), comme les identifiants, codes et fixtures ». Un guillemet
#: typographique n'est pas un accent: il ne se lit dans aucun identifiant, dans
#: aucun code et dans aucune fixture, seulement dans la prose des docstrings.
#:
#: La premiere redaction de ce test refusait tout caractere hors ASCII: il etait
#: donc plus strict que la convention reelle du depot, et le durcir aurait
#: impose a ce module une regle qu'aucune de ses trois jumelles ne tient. Le
#: choix est l'alignement, et l'exception est bornee a deux caracteres nommes.
GUILLEMETS_DE_LA_FAMILLE = {"«", "»"}


def test_the_module_carries_no_accent_anywhere() -> None:
    """Code, identifiants, codes et fixtures en ASCII sans accents.

    Motif: survivre a une console `cp1252`, ou un accent mal encode rend un
    message de refus illisible au moment ou il compte.
    """
    for path in (MODULE_PATH, Path(__file__)):
        texte = path.read_text(encoding="utf-8")
        intrus = sorted(
            {c for c in texte if ord(c) > 127} - GUILLEMETS_DE_LA_FAMILLE
        )
        assert intrus == [], (path.name, intrus)


def test_the_two_tolerated_characters_are_the_ones_the_family_already_uses() -> None:
    """L'exception ci-dessus est mesuree sur le depot, pas decretee.

    Sans ce test, la tolerance serait une porte ouverte que rien ne borne: on
    pourrait y glisser n'importe quel caractere en pretendant que « la famille
    le fait ».
    """
    familles = [
        REPO_ROOT / "src" / "mixed_media_utility" / nom
        for nom in (
            "previz_common.py",
            "extraction_previz.py",
            "pdf_previz.py",
            "scan_previz.py",
        )
    ]
    for path in familles:
        texte = path.read_text(encoding="utf-8")
        assert GUILLEMETS_DE_LA_FAMILLE <= {c for c in texte if ord(c) > 127}
    # Et aucun identifiant, aucune valeur de code, aucune cle de document n'en
    # porte: la tolerance ne concerne que la prose.
    for code in (
        encode_previz.ENCODE_PREVIZ_WARNING_CODES
        + encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
        + encode_previz.DECISION_FINGERPRINT_FIELDS
        + encode_previz.SEQUENCE_FRAME_DIGEST_FIELDS
        + encode_previz.ENCODE_PREVIZ_STATES
        + tuple(encode_previz.__all__)
    ):
        assert code.isascii(), code
    assert rendered(build()).isascii()


# ---------------------------------------------------------------------------
# AC 7 (revision 3): la previz ne deduit RIEN -- l'exception a la purete
# d'emission est fermee, pas recopiee une quatrieme fois
# ---------------------------------------------------------------------------


def test_no_warning_code_is_ever_emitted_by_the_module_itself() -> None:
    """Aucun code du vocabulaire n'est produit ici: tout est transporte.

    Le producteur emet deja le fait de l'incompletude sous **deux** codes et sous
    son orthographe. En deduire un troisieme, anglophone, poserait deux
    orthographes du meme fait dans un seul document.
    """
    document = encode_previz_to_json_dict(build(encode_warnings=()))
    assert document["warnings"] == {"encode": []}
    # Un lot troue, des mires presentes, des fichiers ecartes: rien n'en sort.
    document = encode_previz_to_json_dict(
        build(
            encode_warnings=(),
            verdict=make_verdict(expected=13, found=3, complete=False),
            nonconforming_files=("a.txt", "b.txt"),
            empty_files=("c.tif",),
        )
    )
    assert document["warnings"] == {"encode": []}
    assert document["plan"]["completeness"]["complete"] is False


def test_the_previz_family_of_warnings_does_not_exist() -> None:
    """Un seau sans emetteur possible est une branche morte, et cet epic en a
    deja paye deux."""
    document = encode_previz_to_json_dict(build())
    assert set(document["warnings"]) == {"encode"}
    assert "previz" not in document["warnings"]
    assert set(encode_previz.EncodePrevizWarnings().__dict__) == {"encode"}


# ---------------------------------------------------------------------------
# AC 8: transport verbatim, sans deduplication, sans tri, vocabulaire ferme
# ---------------------------------------------------------------------------


def test_warnings_are_transported_verbatim_in_order_without_deduplication() -> None:
    codes = (
        encode_previz.LOT_INCOMPLET_ASSUME,
        encode_previz.APPROXIMATION_SRGB_TAGUEE_REC709,
        encode_previz.LOT_INCOMPLET_ASSUME,
        encode_previz.FRAMES_SYNTHETIQUES_PRESENTES,
    )
    document = encode_previz_to_json_dict(build(encode_warnings=codes))
    assert document["warnings"]["encode"] == list(codes)
    # Ni trie...
    assert document["warnings"]["encode"] != sorted(codes)
    # ...ni dedoublonne.
    assert len(document["warnings"]["encode"]) == 4


def test_a_code_outside_the_closed_vocabulary_is_refused() -> None:
    with pytest.raises(EPE, match="inconnu"):
        build(encode_warnings=("PAS_UN_CODE",))


def test_a_refusal_code_is_not_a_warning_code() -> None:
    """Un `planned` qui porterait « MASTER_DEJA_PRESENT » annoncerait un encodage
    que 6.1 vient de refuser."""
    with pytest.raises(EPE):
        build(encode_warnings=("MASTER_DEJA_PRESENT",))


def test_require_known_codes_explodes_a_string_character_by_character() -> None:
    """La mesure du socle, qui justifie la garde de ce module."""
    assert previz_common.require_known_codes(
        "AB", ("A", "B"), label="x", error_type=ValueError
    ) == ("A", "B")


def test_a_string_passed_instead_of_a_tuple_is_refused() -> None:
    """Sans cette garde, le document porterait des codes d'un caractere."""
    with pytest.raises(EPE, match="pas une chaine"):
        build(encode_warnings="LOT_INCOMPLET_ASSUME")


@pytest.mark.parametrize(
    "argument",
    ["nonconforming_files", "empty_files", "frames"],
)
def test_a_string_is_refused_wherever_a_sequence_is_expected(argument) -> None:
    with pytest.raises(EPE, match="chaine"):
        build(**{argument: "abc"})


def test_an_unordered_collection_is_refused() -> None:
    """L'ordre d'iteration d'un `set` depend de la graine de hachage."""
    with pytest.raises(EPE, match="ordonnee"):
        build(encode_warnings={encode_previz.LOT_INCOMPLET_ASSUME})


#: Les sept portes qui recoivent une collection de l'appelant. La garde de
#: collection **ordonnee** etait ecrite sur quatre d'entre elles et absente des
#: trois autres; le test la mesure sur les sept a la fois, pour qu'ajouter une
#: porte sans sa garde fasse tomber ce test plutot que d'attendre une revue.
COLLECTIONS_ORDONNEES = {
    "encode_warnings": {"encode_warnings": {"LOT_INCOMPLET_ASSUME"}},
    "nonconforming_files": {"nonconforming_files": {"a.txt", "b.txt"}},
    "empty_files": {"empty_files": {"a.tif", "b.tif"}},
    "verdict.missing_pages": {"verdict": make_verdict(missing_pages={4, 7})},
    "verdict.synthetic_present": {
        "verdict": make_verdict(synthetic_present={"f001.tif", "f004.tif"})
    },
    "frames": {"frames": iter(make_frames())},
    "source_size": {"source_size": {1920, 1080}},
    "resolution.size": {"resolution": make_resolution(size={1920, 1080})},
    "declared_bounds": {"declared_bounds": {"01:00:00:00", "01:00:00:12"}},
}


@pytest.mark.parametrize("porte", sorted(COLLECTIONS_ORDONNEES))
def test_an_unordered_collection_is_refused_at_every_door(porte) -> None:
    """La meme garde, aux neuf portes, et la mesure est la meme partout.

    `tuple({1, 1080})` rend `(1080, 1)` ou `(1, 1080)` selon la graine de
    hachage du processus: une demande `1x1080` publiait un master `1080x1` un
    processus sur deux, et deux bornes de lot ressortaient interverties une fois
    sur deux -- fabriquant le diagnostic `BORNES_DE_LOT_DIVERGENTES` que le
    module dit ne pas vouloir effacer.
    """
    with pytest.raises(EPE, match="ordonnee"):
        build(**COLLECTIONS_ORDONNEES[porte])


@pytest.mark.parametrize(
    "entree, motif",
    [
        ({"source_size": "ab"}, "pas une chaine"),
        ({"resolution": make_resolution(size="ab")}, "pas une chaine"),
        ({"verdict": make_verdict(missing_pages="47")}, "pas une chaine"),
        ({"declared_bounds": "01:00:00:00"}, "pas une chaine"),
        ({"frames": "abc"}, "pas une chaine"),
        ({"nonconforming_files": "abc"}, "pas une chaine"),
        ({"empty_files": "abc"}, "pas une chaine"),
        ({"encode_warnings": "LOT_INCOMPLET_ASSUME"}, "pas une chaine"),
        ({"verdict": make_verdict(synthetic_present="abc")}, "pas une chaine"),
    ],
)
def test_a_string_is_refused_at_every_door_that_expects_a_collection(
    entree, motif
) -> None:
    """Et le refus dit **pourquoi**, pas seulement qu'il refuse.

    Une chaine est une `Sequence`: sans garde dediee, elle traverse le controle
    d'ordre et s'explose caractere par caractere, si bien que le refus qui suit
    parle d'un entier ou d'un cardinal au lieu de nommer la faute. Asserter le
    message est ce qui distingue les deux.
    """
    with pytest.raises(EPE, match=motif):
        build(**entree)


# ---------------------------------------------------------------------------
# AC 4: projection, jamais calcul -- les sentinelles ressortent verbatim
# ---------------------------------------------------------------------------


def test_an_incoherent_frame_rate_and_timecode_come_out_verbatim() -> None:
    """Un depart a 25 images sur un master a 12,5: si le module recalculait quoi
    que ce soit, la sentinelle serait corrigee au lieu d'etre transportee."""
    document = encode_previz_to_json_dict(build())["plan"]
    assert document["fps_target_exact"] == "25/2"
    assert document["timecode"]["base_rate"] == "25/1"
    assert document["timecode"]["emitted"] == "01:00:00:00"
    # La valeur lue au manifest n'est pas celle qui sera emise, et les deux ne
    # s'echangent pas: c'est le depart **emis** qui entre dans l'empreinte.
    assert document["timecode"]["manifest_value"] == "00:59:59:12"


def test_the_verdict_is_never_confronted_to_the_length_of_the_sequence() -> None:
    """Recompter « pour verifier » ferait diverger la previz de la production."""
    document = encode_previz_to_json_dict(build())["plan"]
    assert document["completeness"]["found"] == 13
    assert document["completeness"]["expected"] == 13
    assert len(document["sequence"]) == 3
    # Et le verdict `complete` reste celui du producteur, meme faux.
    assert document["completeness"]["complete"] is False


def test_the_two_families_of_discarded_files_are_never_merged() -> None:
    """Un nom non conforme au lot et un fichier de 0 octet sont deux faits
    distincts: 6.1 les separe, et une interversion ferait lire l'un pour
    l'autre."""
    document = encode_previz_to_json_dict(build())["plan"]
    assert document["discarded"] == {
        "nonconforming_files": ["intrus.txt"],
        "empty_files": ["f003.tif"],
    }


def test_the_two_registers_of_synthetic_frames_are_never_merged() -> None:
    """« Le disque fait foi pour la presence, le manifest pour la nature »: un
    nom au registre sans fichier est un **trou**, pas une mire. Les intervertir
    ferait passer un trou pour une mire et l'inverse."""
    document = encode_previz_to_json_dict(build())["plan"]["completeness"]
    assert document["synthetic_present"] == ["f001.tif"]
    assert document["synthetic_missing"] == ["f009.tif"]


def test_the_resolution_is_never_confronted_to_the_source() -> None:
    document = encode_previz_to_json_dict(
        build(
            resolution=make_resolution(
                requested="7680x4320", origin="personnalisee",
                resolution_id=None, size=(7680, 4320),
            )
        )
    )["plan"]
    assert document["resolution"]["width_px"] == 7680
    assert document["source_size"]["width_px"] == 3307
    assert "resolution_id" not in document["resolution"]


def test_the_declared_bounds_are_never_reconciled_with_the_sequence() -> None:
    """Leur divergence est precisement ce que 6.1 nomme
    (`BORNES_DE_LOT_DIVERGENTES`); la corriger ici effacerait le diagnostic."""
    document = encode_previz_to_json_dict(
        build(declared_bounds=("23:59:59:23", "00:00:00:00"))
    )["plan"]
    assert document["declared_bounds"] == {
        "first_frame_timecode": "23:59:59:23",
        "last_frame_timecode": "00:00:00:00",
    }
    assert [frame["frame_timecode"] for frame in document["sequence"]] == [
        "01:00:00:00",
        "01:00:00:01",
        "01:00:00:02",
    ]


def test_the_sequence_is_never_resorted() -> None:
    """L'ordre est une entree de decision: c'est celui du master."""
    melange = [
        make_frame(2, "f002.tif", "01:00:00:02"),
        make_frame(0, "f000.tif", "01:00:00:00"),
        make_frame(1, "f001.tif", "01:00:00:01", synthetic=True),
    ]
    document = encode_previz_to_json_dict(build(frames=melange))["plan"]
    assert [frame["output_rank"] for frame in document["sequence"]] == [2, 0, 1]


def test_the_frame_rate_is_rendered_in_num_den_form_from_a_float() -> None:
    """Exception nommee de la cadence, et elle est obligatoire.

    Sans elle, un flottant entrerait verbatim au document **et** dans
    l'empreinte, et deux recettes produiraient deux empreintes pour la meme
    cadence.
    """
    document = encode_previz_to_json_dict(
        build(exact_frame_rate=None, fps_target=12.5)
    )["plan"]
    assert document["fps_target_exact"] == "25/2"
    assert previz_common.exact_rate(29.97, error_type=ValueError) == "30000/1001"
    ntsc = encode_previz_to_json_dict(
        build(exact_frame_rate=None, fps_target=29.97)
    )["plan"]
    assert ntsc["fps_target_exact"] == "30000/1001"


def test_the_canonical_frame_rate_is_what_enters_the_fingerprint() -> None:
    depuis_flottant = build(exact_frame_rate=None, fps_target=12.5)
    depuis_chaine = build(exact_frame_rate="25/2")
    assert decision_of(depuis_flottant) == decision_of(depuis_chaine)
    # Et une autre cadence donne une autre empreinte: l'egalite ci-dessus n'est
    # pas vraie par vacuite.
    assert decision_of(build(exact_frame_rate="25/1")) != decision_of(depuis_chaine)


@pytest.mark.parametrize(
    "ecriture",
    ["30", "banane", " 25/1 ", "0/1", "-25/1", "25/0", "29.97", "25/2/1", "/2", "25/",
     "\u0662\u0665/1"],
)
def test_a_frame_rate_that_is_not_a_reduced_ratio_is_refused(ecriture) -> None:
    """La forme canonique est **unique**, et c'est la seule exception nommee du
    module.

    Mesure du defaut ferme ici: `build(exact_frame_rate="30")` et
    `build(fps_target=30.0)` decrivaient la meme cadence sous deux empreintes
    differentes -- litteralement le scenario que la docstring du module dit
    vouloir empecher, « un consommateur qui les compare conclurait a tort a une
    peremption ». `"banane"`, `"25/0"` et `"0/1"` entraient egalement au
    document **et** dans l'empreinte sans un mot.
    """
    with pytest.raises(EPE):
        build(exact_frame_rate=ecriture)


def test_two_writings_of_the_same_cadence_render_the_same_fingerprint() -> None:
    """Le pendant positif du test ci-dessus: la forme est **ramenee**, pas
    seulement refusee."""
    reduite = build(exact_frame_rate="25/1")
    assert (
        encode_previz_to_json_dict(build(exact_frame_rate="50/2"))["plan"][
            "fps_target_exact"
        ]
        == "25/1"
    )
    assert decision_of(build(exact_frame_rate="50/2")) == decision_of(reduite)
    assert decision_of(build(exact_frame_rate=None, fps_target=25.0)) == decision_of(
        reduite
    )
    # Idempotence sur ce que 6.1 produit reellement: aucune valeur du producteur
    # n'est changee par le detour.
    for cadence in ("25/1", "25/2", "30000/1001", "24000/1001", "1/1", "120/1"):
        assert (
            encode_previz_to_json_dict(build(exact_frame_rate=cadence))["plan"][
                "fps_target_exact"
            ]
            == cadence
        )


def test_a_decimal_string_is_refused_on_both_frame_rate_paths() -> None:
    """L'ecart mesure de `codec_profiles`, rendu inatteignable depuis ici.

    `codec_profiles.exact_frame_rate("29.97")` rend `2997/100` alors que le meme
    flottant rend `30000/1001`: la branche `str` du socle ne passe pas par le
    recalage NTSC. L'ecart appartient a `codec_profiles` et n'est pas resorbe
    ici -- il est ferme a l'entree, une ecriture decimale n'etant acceptee
    d'aucun cote.
    """
    assert previz_common.exact_rate("29.97", error_type=ValueError) == "2997/100"
    assert previz_common.exact_rate(29.97, error_type=ValueError) == "30000/1001"
    with pytest.raises(EPE, match="cadence rationnelle"):
        build(exact_frame_rate="29.97")
    with pytest.raises(EPE, match="doit etre un nombre"):
        build(exact_frame_rate=None, fps_target="29.97")
    with pytest.raises(EPE, match="doit etre un nombre"):
        build(exact_frame_rate=None, fps_target=True)


def test_supplying_both_frame_rate_forms_is_refused() -> None:
    with pytest.raises(EPE, match="exclusifs"):
        build(exact_frame_rate="25/2", fps_target=12.5)


def test_supplying_no_frame_rate_at_all_is_refused() -> None:
    with pytest.raises(EPE, match="cadence"):
        build(exact_frame_rate=None, fps_target=None)


def test_an_unusable_frame_rate_lands_in_the_module_hierarchy() -> None:
    with pytest.raises(EPE, match="Cadence inexploitable"):
        build(exact_frame_rate=None, fps_target=float("nan"))


# ---------------------------------------------------------------------------
# AC 2: la canonicalisation n'honore aucun `error_type`
# ---------------------------------------------------------------------------


def test_canonical_json_leaves_the_promised_hierarchy_and_that_is_measured() -> None:
    with pytest.raises(ValueError):
        previz_common.canonical_json({"fps": float("nan")})
    with pytest.raises(TypeError):
        previz_common.canonical_json({"x": object()})
    cyclique: dict = {}
    cyclique["self"] = cyclique
    with pytest.raises(ValueError):
        previz_common.canonical_json(cyclique)
    # LA PROFONDEUR SE CHERCHE, elle ne s'ecrit pas -- le detail et la mesure
    # des trois versions vivent sur `_dictionnaire_TROP_PROFOND`, qui sert les
    # TROIS bancs a qui `3000` avait ete recopie.
    with pytest.raises(RecursionError):
        previz_common.canonical_json(_dictionnaire_TROP_PROFOND())


def test_a_non_serializable_container_tag_is_refused_in_the_hierarchy() -> None:
    with pytest.raises(EPE, match="canonicalisable"):
        build(container_tags={"x": object()})


def test_a_nan_container_tag_is_refused_in_the_hierarchy() -> None:
    """`json.loads` accepte `NaN` a la lecture d'une sonde ffprobe, et la valeur
    traverse ensuite le rapport sans jamais etre retypee."""
    with pytest.raises(EPE, match="canonicalisable"):
        build(container_tags={"frame_rate": float("nan")})


def test_a_cyclic_container_tag_is_refused_in_the_hierarchy() -> None:
    cyclique: dict = {"lot_id": "lot-a"}
    cyclique["self"] = cyclique
    with pytest.raises(EPE, match="canonicalisable"):
        build(container_tags=cyclique)


#: Les profondeurs essayees, dans l'ordre, par `_dictionnaire_TROP_PROFOND`.
#: `3000` etait vrai de Python 3.11 et faux de 3.12 et 3.13, ou la limite de
#: l'encodeur C a ete relevee -- mesure du 2026-09-08, meme machine : 3.11 rompt
#: des 1 000 niveaux, 3.12 et 3.13 a 10 000. Le plafond de 100 000 existe pour
#: qu'une version future qui reculerait encore la limite soit couverte, et
#: l'absence de rupture est une ERREUR nommee plutot qu'un banc vert.
PROFONDEURS_ESSAYEES = (1_000, 10_000, 100_000)

_profondeur_qui_rompt: int | None = None


def _dictionnaire_TROP_PROFOND() -> dict:
    """Un dictionnaire assez profond pour rompre l'encodeur JSON de CETTE version.

    Ecrit une fois pour les trois bancs qui en ont besoin : chacun portait la
    meme constante `3000`, et le premier run de CI joue ailleurs qu'en 3.11 les
    a tous les trois trouves faux -- `DID NOT RAISE RecursionError`. Une
    constante recopiee trois fois se corrige trois fois, ou pas du tout.

    Ce que les trois bancs veulent etablir n'est pas un SEUIL mais une
    PROPAGATION : `RecursionError` remonte au lieu d'etre avalee. La profondeur
    se cherche donc, elle ne s'ecrit pas.
    """
    global _profondeur_qui_rompt
    if _profondeur_qui_rompt is None:
        for niveaux in PROFONDEURS_ESSAYEES:
            if _rompt_a(niveaux):
                _profondeur_qui_rompt = niveaux
                break
        else:
            raise AssertionError(
                "aucune des profondeurs essayees "
                f"{PROFONDEURS_ESSAYEES} ne fait rompre `canonical_json` sur "
                f"Python {sys.version.split()[0]} : le banc ne mesure plus la "
                "propagation qu'il annonce")
    return _empile(_profondeur_qui_rompt)


def _empile(niveaux: int) -> dict:
    profond: dict = {}
    courant = profond
    for _ in range(niveaux):
        courant["n"] = {}
        courant = courant["n"]
    return profond


def _rompt_a(niveaux: int) -> bool:
    try:
        previz_common.canonical_json(_empile(niveaux))
    except RecursionError:
        return True
    return False


def test_la_profondeur_qui_rompt_est_CHERCHEE_et_non_ECRITE() -> None:
    """Le temoin du helper ci-dessus, sans lequel il pourrait rendre n'importe quoi.

    Deux faits mesures : la profondeur trouvee rompt REELLEMENT, et une
    profondeur dix fois moindre ne rompt PAS -- ce second volet est ce qui
    etablit que la recherche trouve une FRONTIERE et non le premier essai venu.
    """
    _dictionnaire_TROP_PROFOND()
    assert _profondeur_qui_rompt in PROFONDEURS_ESSAYEES
    assert _rompt_a(_profondeur_qui_rompt)
    assert not _rompt_a(_profondeur_qui_rompt // 10)


def test_a_too_deep_container_tag_is_refused_in_the_hierarchy() -> None:
    """`RecursionError` n'est ni un `ValueError` ni un `TypeError`: sans elle
    dans le tuple attrape, elle sortirait de la hierarchie."""
    with pytest.raises(EPE, match="canonicalisable"):
        build(container_tags=_dictionnaire_TROP_PROFOND())


@pytest.mark.parametrize(
    "payload",
    [
        {"x": object()},
        {"fps": float("nan")},
        {"fps": float("inf")},
    ],
)
def test_the_fingerprint_guard_covers_its_three_families_of_exception(payload) -> None:
    """La garde symetrique de la precedente: elle protege ce que le module
    **scelle**, l'autre ce qu'il **transporte**.

    Le payload d'empreinte est aujourd'hui integralement garde en amont -- que
    des chaines et des entiers passes par `_require_text` et `_require_int` --,
    donc cette branche est **defensive**: aucune entree de `build_encode_previz`
    ne l'atteint. Elle est testee en direct plutot que par une entree fabriquee
    qui n'existe pas, parce qu'un test qui ne visite pas la branche ne pinne
    rien. Ce qui la rend due: `fingerprint_of` canonicalise, donc elle leve
    `TypeError`, `ValueError` **et** `RecursionError`, dont deux sortent de la
    hierarchie promise. Reduire le tuple attrape a l'une des trois rendrait le
    module menteur sur sa propre hierarchie.
    """
    with pytest.raises(EPE, match="canonicalisable"):
        encode_previz._fingerprint_of(payload, "empreinte de test")


def test_the_fingerprint_guard_covers_recursion_too() -> None:
    with pytest.raises(EPE, match="canonicalisable"):
        encode_previz._fingerprint_of(_dictionnaire_TROP_PROFOND(),
                                      "empreinte de test")


def test_a_fingerprint_guard_failure_is_not_a_bare_exception() -> None:
    """Le point de l'AC 2: un appelant qui attrape la hierarchie du module doit
    attraper **ca**, et pas un `ValueError` nu venu de `json`."""
    try:
        encode_previz._fingerprint_of({"fps": float("nan")}, "empreinte de test")
    except Exception as erreur:  # noqa: BLE001 -- c'est le type qui est teste
        assert type(erreur) is EPE
        assert isinstance(erreur.__cause__, ValueError)
    else:
        pytest.fail("la garde n'a rien leve")


def test_every_refusal_of_this_module_is_a_value_error() -> None:
    """Un appelant generique qui attrape `ValueError` attrape tout."""
    assert issubclass(EPE, ValueError)
    with pytest.raises(ValueError):
        build(container_tags={"x": object()})


@pytest.mark.parametrize("cle", [1, True, 2.5, None, ("a", "b")])
def test_a_container_tag_key_that_is_not_a_string_is_refused(cle) -> None:
    """`json.dumps` coerce toute cle scalaire en chaine **sans le dire**.

    Mesure du defaut ferme: `container_tags={1: "a"}` rendait un dictionnaire a
    cle `int` dont la forme canonique etait `{"1":"a"}` -- la forme rendue et la
    forme scellee divergeaient sur le type de la cle, une valeur incoherente ne
    ressortait pas incoherente mais **corrigee**, et le document promettait
    « aucun objet Python non JSON » en portant une cle qui n'en est pas une.
    6.1 declare `container_tags: dict[str, str]`: la garde est sans effet
    observable pour le producteur reel.
    """
    with pytest.raises(EPE, match="cles chaines"):
        build(container_tags={cle: "a"})


def test_container_tags_must_be_a_mapping() -> None:
    with pytest.raises(EPE, match="dictionnaire"):
        build(container_tags=[("a", "b")])


# ---------------------------------------------------------------------------
# AC 11 / AC 12: serialiseur a nom distinct, deepcopy, champ optionnel omis
# ---------------------------------------------------------------------------


def test_the_serializer_name_is_distinct_from_its_three_twins() -> None:
    from mixed_media_utility import extraction_previz, pdf_previz, scan_previz

    noms = {
        extraction_previz.previz_to_json_dict.__name__,
        pdf_previz.pdf_previz_to_json_dict.__name__,
        scan_previz.scan_previz_to_json_dict.__name__,
        encode_previz_to_json_dict.__name__,
    }
    assert len(noms) == 4
    assert "encode_previz_to_json_dict" in noms


def test_muter_le_document_rendu_ne_touche_pas_le_previz_gele() -> None:
    """`dict(...)` ne recopie que le premier niveau -- regression du 2026-08-05.

    Sans la copie profonde, muter un sous-dict du document rendu mutait l'objet
    dit « gele », deux appels ne rendaient plus le meme JSON, et l'empreinte ne
    correspondait plus a son propre contenu.
    """
    source = {"lot_id": "lot-a", "imbrique": {"project_id": "proj-a"}}
    previz = build(container_tags=source)
    premier = encode_previz_to_json_dict(previz)
    premier["plan"]["container_tags"]["imbrique"]["intrus"] = "mutation"
    second = encode_previz_to_json_dict(previz)
    assert second["plan"]["container_tags"] == {
        "lot_id": "lot-a",
        "imbrique": {"project_id": "proj-a"},
    }
    assert second != premier


def test_mutating_the_source_dictionary_after_construction_changes_nothing() -> None:
    """Le document est fige **a la construction**, pas seulement a la
    serialisation.

    Le nom de ce test disait deja cela; son assertion disait l'inverse, et la
    mesure lui donnait raison -- le plan conservait une **reference vivante** au
    dictionnaire de l'appelant. Les deux copies profondes ne se remplacent pas:
    celle de la construction protege le document de son producteur, celle de la
    serialisation protege le document de son consommateur.
    """
    source = {"lot_id": "lot-a", "imbrique": {"project_id": "proj-a"}}
    previz = build(container_tags=source)
    rendu_avant = rendered(previz)
    source["imbrique"]["intrus"] = "mutation"
    assert rendered(previz) == rendu_avant
    assert previz.plan.container_tags is not source
    assert previz.plan.container_tags == {
        "lot_id": "lot-a",
        "imbrique": {"project_id": "proj-a"},
    }


def test_the_canonicalization_guard_cannot_be_defeated_after_construction() -> None:
    """La garde de l'AC 2 ne valait qu'a l'instant de la construction.

    Mesure du defaut ferme: un appelant qui gardait son dictionnaire et y
    posait un `NaN` **apres** le `build` faisait lever a
    `canonical_json(encode_previz_to_json_dict(p))` un `ValueError` **nu** --
    exactement le mode de defaillance que `_require_canonicalizable` documente
    (« l'explosion arrive chez le consommateur qui canonicalise le document,
    loin de l'entree fautive et hors de la hierarchie promise »), simplement
    decale d'un instant.
    """
    source = {"fps": 1.0}
    previz = build(container_tags=source)
    source["fps"] = float("nan")
    assert rendered(previz) == rendered(build(container_tags={"fps": 1.0}))


@pytest.mark.parametrize(
    "argument, absent",
    [
        ({"resolution": make_resolution(resolution_id=None)}, ("plan", "resolution", "resolution_id")),
    ],
)
def test_an_optional_field_is_omitted_never_null(argument, absent) -> None:
    document = encode_previz_to_json_dict(build(**argument))
    courant = document
    for cle in absent[:-1]:
        courant = courant[cle]
    assert absent[-1] not in courant
    assert "null" not in previz_common.canonical_json(courant)


def test_the_timecode_fields_are_omitted_when_absent() -> None:
    """`emitted` vaut `None` dans deux cas nommes par 6.1: pas de
    `timecode_base_fps`, ou depart hors base du master."""
    document = encode_previz_to_json_dict(
        build(
            timecode=make_timecode("aucun timecode reinjecte")
        )
    )["plan"]["timecode"]
    assert document == {"reliability": "reliable"}
    assert "emitted" not in document
    assert "base_rate" not in document


def test_a_start_out_of_the_master_base_keeps_its_base_and_its_manifest_value() -> None:
    """Le cas que le producteur emet **litteralement** (`encode.py:1305-1312`).

    `emitted` est `None`, `base_rate` et `manifest_value` sont poses: les trois
    champs sont dissocies, et c'est la seule fixture qui les dissocie. Sans
    elle, conditionner le rendu de l'un a la presence de l'autre ne se voyait
    pas -- le document perdait la base de validation et la valeur lue au
    manifest dans le cas exact ou l'interface a le plus besoin de les montrer.
    """
    document = encode_previz_to_json_dict(
        build(timecode=make_timecode("hors base du master"))
    )["plan"]["timecode"]
    assert document == {
        "reliability": "reliable",
        "manifest_value": "00:59:59:12",
        "base_rate": "25/1",
    }
    assert "emitted" not in document


@pytest.mark.parametrize(
    "absent",
    ["emitted", "manifest_value", "base_rate"],
)
def test_the_timecode_fields_are_omitted_one_by_one(absent) -> None:
    """Chaque champ s'omet **seul**, sans entrainer les deux autres.

    La combinaison `base_rate=None` avec un `emitted` pose n'est pas
    productible par 6.1 -- `emitted` se calcule depuis `base_rate` --, mais le
    protocole structurel l'admet et le document doit la rendre telle quelle
    plutot que d'inventer une regle de solidarite entre trois champs
    transportes verbatim.
    """
    document = encode_previz_to_json_dict(
        build(timecode=make_timecode(**{absent: None}))
    )["plan"]["timecode"]
    assert absent not in document
    for autre in ("emitted", "manifest_value", "base_rate"):
        if autre != absent:
            assert autre in document


def test_an_indeterminable_expected_count_is_omitted() -> None:
    document = encode_previz_to_json_dict(
        build(verdict=make_verdict(expected=None))
    )["plan"]["completeness"]
    assert "expected" not in document
    assert document["found"] == 13


def test_declared_bounds_are_omitted_as_a_whole_when_the_lot_declares_none() -> None:
    """Un lot ne du scan ne porte aucune borne; un objet vide serait une section
    morte."""
    document = encode_previz_to_json_dict(build(declared_bounds=(None, None)))["plan"]
    assert "declared_bounds" not in document
    partiel = encode_previz_to_json_dict(
        build(declared_bounds=(None, "01:00:00:12"))
    )["plan"]
    assert partiel["declared_bounds"] == {"last_frame_timecode": "01:00:00:12"}


def test_the_document_never_carries_a_json_null_anywhere() -> None:
    """Regle cardinale, tenue sur le document entier et dans les trois etats."""
    for previz in (
        build(),
        build(state="encoded", encoded_bytes=987654321),
        build(
            timecode=make_timecode("aucun timecode reinjecte"),
            verdict=make_verdict(expected=None),
            declared_bounds=(None, None),
            resolution=make_resolution(resolution_id=None),
        ),
        build_refused(),
        build_refused(refused_candidates=()),
    ):
        assert "null" not in rendered(previz)


def test_the_synthetic_flag_is_unconditional_false_included() -> None:
    """L'exception de 5.8 (EPIC5-ARB-8) s'applique ici aussi.

    Un drapeau absent se relit « vraie frame », et l'interface montrerait une
    mire « FRAME MANQUANTE » comme un plan du film.
    """
    sequence = encode_previz_to_json_dict(build())["plan"]["sequence"]
    assert [frame["synthetic"] for frame in sequence] == [False, True, False]
    for frame in sequence:
        assert "synthetic" in frame


def test_a_missing_synthetic_flag_is_refused_rather_than_coerced() -> None:
    """`bool(None)` vaut `False`: un producteur qui omet le drapeau verrait sa
    mire rendue « vraie frame »."""
    frames = make_frames()
    frames[1].synthetic = None
    with pytest.raises(EPE, match="booleen"):
        build(frames=frames)
    frames[1].synthetic = 1
    with pytest.raises(EPE, match="booleen"):
        build(frames=frames)


# ---------------------------------------------------------------------------
# AC 9: aucun pixel, chemins relatifs seulement
# ---------------------------------------------------------------------------


def test_the_whole_document_carries_no_absolute_path() -> None:
    """Le detecteur existe deja dans `io/manifest`, et c'est le test qui
    l'importe."""
    for previz in (build(), build_refused()):
        assert _iter_absolute_path_violations(encode_previz_to_json_dict(previz)) == []


@pytest.mark.parametrize(
    "chemin",
    ["/abs/outputs/m.mov", "C:\\outputs\\m.mov", "../ailleurs/m.mov"],
)
def test_an_absolute_or_escaping_master_path_is_refused(chemin) -> None:
    with pytest.raises(EPE):
        build(master_path_relative=chemin)


@pytest.mark.parametrize(
    "chemin",
    ["/abs/f001.tif", "C:\\frames\\f001.tif", "../f001.tif"],
)
def test_an_absolute_or_escaping_frame_path_is_refused(chemin) -> None:
    """La frame visee est en **deuxieme** position: un appariement fautif qui ne
    regarderait que la premiere ne se demasque pas autrement."""
    frames = make_frames()
    frames[1] = SimpleNamespace(
        output_rank=1,
        frame_path_relative=chemin,
        frame_timecode="01:00:00:01",
        synthetic=True,
    )
    with pytest.raises(EPE):
        build(frames=frames)


def test_the_module_never_checks_that_a_file_exists() -> None:
    """Un chemin relatif qui ne designe rien produit un document valide."""
    document = encode_previz_to_json_dict(
        build(master_path_relative="outputs/n_existe_pas.mov")
    )
    assert document["plan"]["master_path_relative"] == "outputs/n_existe_pas.mov"


def test_the_document_carries_no_pixel() -> None:
    texte = rendered(build())
    for banned in ("base64", "data:image", "\\u0000"):
        assert banned not in texte


# ---------------------------------------------------------------------------
# AC 10: empreinte de fraicheur -- entrees de decision seules
# ---------------------------------------------------------------------------


def test_the_fingerprint_payload_matches_its_exported_constant() -> None:
    payload = encode_previz._decision_fingerprint_payload(
        build().subject, build().plan
    )
    assert tuple(sorted(payload)) == encode_previz.DECISION_FINGERPRINT_FIELDS
    assert encode_previz.DECISION_FINGERPRINT_FIELDS == tuple(
        sorted(encode_previz.DECISION_FINGERPRINT_FIELDS)
    )
    for champ in encode_previz.DECISION_FINGERPRINT_OPTIONAL_FIELDS:
        assert champ in encode_previz.DECISION_FINGERPRINT_FIELDS
    # Les deux constantes sont **epinglees** en litteraux. Sans cela, elargir la
    # liste des optionnels jusqu'a couvrir tous les champs desarmerait le
    # garde-fou de contrat sans qu'aucune assertion ne bouge: la garde ne
    # signalerait plus jamais un champ manquant, et l'AC serait tenue par
    # vacuite.
    assert encode_previz.DECISION_FINGERPRINT_FIELDS == (
        "fps_target_exact",
        "lot_id",
        "lot_state",
        "profile_id",
        "resolution_height_px",
        "resolution_width_px",
        "sequence_digest",
        "timecode_base_rate",
        "timecode_start",
    )
    assert encode_previz.DECISION_FINGERPRINT_OPTIONAL_FIELDS == (
        "timecode_base_rate",
        "timecode_start",
    )
    assert encode_previz.SEQUENCE_FRAME_DIGEST_FIELDS == (
        "frame_path_relative",
        "frame_timecode",
        "output_rank",
    )


def test_the_sequence_digest_entry_matches_its_exported_constant() -> None:
    entree = encode_previz._sequence_frame_digest_entry(build().plan.sequence[1])
    assert tuple(sorted(entree)) == encode_previz.SEQUENCE_FRAME_DIGEST_FIELDS
    assert "synthetic" not in entree


def test_the_fingerprint_is_stable_across_two_identical_builds() -> None:
    assert decision_of(build()) == decision_of(build())
    assert decision_of(build()).startswith(previz_common.FINGERPRINT_PREFIX)
    assert previz_common.is_complete_fingerprint(decision_of(build()))


DECISION_CHANGES = {
    "lot_id": {"lot_id": "lot-b"},
    "profile_id": {"profile_id": "dnxhr_hq"},
    "lot_state": {"lot_state": "encode"},
    "fps_target_exact": {"exact_frame_rate": "24/1"},
    "resolution_width_px": {
        "resolution": make_resolution(size=(3840, 1080), resolution_id=None)
    },
    "resolution_height_px": {
        "resolution": make_resolution(size=(1920, 2160), resolution_id=None)
    },
    "timecode_start": {"timecode": make_timecode(emitted="02:00:00:00")},
    "timecode_base_rate": {"timecode": make_timecode(base_rate="24/1")},
    "sequence_digest": {
        "frames": [
            make_frame(0, "f000.tif", "01:00:00:00"),
            make_frame(1, "f001.tif", "01:00:00:01", synthetic=True),
            make_frame(2, "f007.tif", "01:00:00:02"),
        ]
    },
}


@pytest.mark.parametrize("champ", sorted(DECISION_CHANGES))
def test_the_fingerprint_is_sensitive_to_each_decision_entry_one_by_one(champ) -> None:
    """« En omettre une entree de decision declarerait a jour un encodage qui ne
    l'est plus » -- precedent des bornes de 3.7."""
    assert champ in encode_previz.DECISION_FINGERPRINT_FIELDS
    assert decision_of(build(**DECISION_CHANGES[champ])) != decision_of(build())


def test_every_declared_decision_field_has_a_falsifier() -> None:
    """Aucun champ du tuple n'echappe au test ci-dessus: sans cette
    confrontation, ajouter un champ a la constante sans le faire varier laisserait
    l'AC vraie par vacuite."""
    assert set(DECISION_CHANGES) == set(encode_previz.DECISION_FINGERPRINT_FIELDS)


CONSTATATION_CHANGES = {
    "chemin du master": {"master_path_relative": "outputs/autre.mov"},
    "fiabilite du timecode": {"timecode_reliability": "best_effort"},
    "valeur de timecode au manifest": {
        "timecode": make_timecode(manifest_value="09:00:00:00")
    },
    "verdict de completude": {
        "verdict": make_verdict(found=3, expected=3, complete=True)
    },
    "nombre de mires": {
        "verdict": make_verdict(
            synthetic_present=("f001.tif", "f004.tif"), synthetic_missing=()
        )
    },
    "index de page manquants": {"verdict": make_verdict(missing_pages=())},
    "avertissements": {
        "encode_warnings": (encode_previz.RESIDUS_D_ENCODAGE_BALAYES,)
    },
    "estimation de taille": {"estimated_bytes": 42},
    "fichiers ecartes": {"nonconforming_files": (), "empty_files": ()},
    "bornes declarees": {"declared_bounds": (None, None)},
    "tags de conteneur": {"container_tags": {"autre": "valeur"}},
    "resolution demandee": {
        "resolution": make_resolution(requested="1920x1080", origin="personnalisee")
    },
    "identifiant de resolution": {
        "resolution": make_resolution(resolution_id=None)
    },
    "conteneur": {"container": "mp4"},
    "projet": {"project_id": "proj-b"},
    "drapeau de mire": {
        "frames": [
            make_frame(0, "f000.tif", "01:00:00:00", synthetic=True),
            make_frame(1, "f001.tif", "01:00:00:01", synthetic=False),
            make_frame(2, "f002.tif", "01:00:00:02", synthetic=True),
        ]
    },
    "horodatage": {"generated_at_utc": "2026-08-12T09:30:00Z"},
}


@pytest.mark.parametrize("quoi", sorted(CONSTATATION_CHANGES))
def test_the_fingerprint_is_insensitive_to_each_constatation(quoi) -> None:
    """« Y ajouter une constatation rendrait l'empreinte sensible a ce qui ne
    decide rien et signalerait des peremptions imaginaires »."""
    modifie = build(**CONSTATATION_CHANGES[quoi])
    assert decision_of(modifie) == decision_of(build())
    # ...et la modification est bien arrivee dans le document: sans cette
    # seconde assertion, l'egalite ci-dessus serait vraie par vacuite.
    assert rendered(modifie) != rendered(build())


def test_the_sequence_enters_the_fingerprint_through_its_sub_digest() -> None:
    """Un tuple de noms de champs scalaires ne peut pas porter une collection."""
    assert "sequence_digest" in encode_previz.DECISION_FINGERPRINT_FIELDS
    payload = encode_previz._decision_fingerprint_payload(
        build().subject, build().plan
    )
    assert payload["sequence_digest"].startswith(previz_common.FINGERPRINT_PREFIX)
    assert payload["sequence_digest"] != decision_of(build())


def test_a_frame_added_removed_or_reordered_changes_the_fingerprint() -> None:
    base = build()
    frames = make_frames()

    ajoutee = frames + [make_frame(3, "f003.tif", "01:00:00:03")]
    assert decision_of(build(frames=ajoutee)) != decision_of(base)

    retiree = frames[:2]
    assert decision_of(build(frames=retiree)) != decision_of(base)

    # **Reordonnee**: exactement les memes trois frames, dans un autre ordre.
    # C'est le cas que le mutant M33 de 5.6 avait traverse.
    reordonnee = [frames[2], frames[0], frames[1]]
    assert sorted(f.frame_path_relative for f in reordonnee) == sorted(
        f.frame_path_relative for f in frames
    )
    assert decision_of(build(frames=reordonnee)) != decision_of(base)


def test_the_sub_digest_is_a_list_not_a_set() -> None:
    """Deux frames identiques ne se fondent pas en une."""
    doublon = [
        make_frame(0, "f000.tif", "01:00:00:00"),
        make_frame(0, "f000.tif", "01:00:00:00"),
    ]
    unique = [make_frame(0, "f000.tif", "01:00:00:00")]
    assert decision_of(build(frames=doublon)) != decision_of(build(frames=unique))


def test_the_optional_fingerprint_fields_are_omitted_not_nulled() -> None:
    """Motif de 3.5: l'empreinte d'un lot sans timecode reste identique a ce
    qu'elle serait si le champ n'existait pas."""
    sans_timecode = build(
        timecode=make_timecode("aucun timecode reinjecte")
    )
    payload = encode_previz._decision_fingerprint_payload(
        sans_timecode.subject, sans_timecode.plan
    )
    assert "timecode_start" not in payload
    assert "timecode_base_rate" not in payload
    attendu = previz_common.fingerprint_of(payload)
    assert decision_of(sans_timecode) == attendu
    # Et la variante `None`-ecrite donnerait une **autre** empreinte: l'omission
    # n'est pas cosmetique.
    avec_null = dict(payload, timecode_start=None, timecode_base_rate=None)
    assert previz_common.fingerprint_of(avec_null) != attendu


def test_the_two_optional_fingerprint_fields_are_omitted_independently() -> None:
    """Le cas dissocie: `emitted` absent, `base_rate` **present**.

    Les deux champs sont omis independamment l'un de l'autre, et l'empreinte est
    pinnee au champ pres. Sans cette assertion, conditionner l'un a l'autre
    faisait disparaitre `timecode_base_rate` de l'empreinte de decision dans le
    cas exact que le producteur emet: deux lots a bases de validation
    differentes rendaient alors la **meme** empreinte, et l'interface aurait
    declare a jour un encodage qui ne l'est plus.
    """
    hors_base = build(timecode=make_timecode("hors base du master"))
    payload = encode_previz._decision_fingerprint_payload(
        hors_base.subject, hors_base.plan
    )
    assert payload["timecode_base_rate"] == "25/1"
    assert "timecode_start" not in payload
    assert decision_of(hors_base) == previz_common.fingerprint_of(payload)
    # La base de validation decide toujours, meme sans depart emis.
    autre_base = build(
        timecode=make_timecode("hors base du master", base_rate="24/1")
    )
    assert decision_of(autre_base) != decision_of(hors_base)
    # Et la valeur lue au manifest reste une constatation, meme dans ce cas.
    autre_manifest = build(
        timecode=make_timecode("hors base du master", manifest_value="09:00:00:00")
    )
    assert decision_of(autre_manifest) == decision_of(hors_base)
    assert rendered(autre_manifest) != rendered(hors_base)


def test_a_fingerprint_payload_diverging_from_its_constant_is_refused() -> None:
    entree = dict(
        encode_previz._sequence_frame_digest_entry(build().plan.sequence[0])
    )
    entree.pop("frame_timecode")
    with pytest.raises(EPE, match="diverge"):
        encode_previz._check_fingerprint_contract(
            entree,
            encode_previz.SEQUENCE_FRAME_DIGEST_FIELDS,
            (),
            "SEQUENCE_FRAME_DIGEST_FIELDS",
        )
    with pytest.raises(EPE, match="diverge"):
        encode_previz._check_fingerprint_contract(
            {"intrus": 1, **entree},
            encode_previz.SEQUENCE_FRAME_DIGEST_FIELDS,
            (),
            "SEQUENCE_FRAME_DIGEST_FIELDS",
        )


def test_fingerprints_of_different_scopes_are_never_comparable() -> None:
    """Le prefixe est partage, la recette non."""
    previz = build()
    payload = encode_previz._decision_fingerprint_payload(previz.subject, previz.plan)
    assert payload["sequence_digest"] != decision_of(previz)
    assert decision_of(previz).startswith(previz_common.FINGERPRINT_PREFIX)
    assert payload["sequence_digest"].startswith(previz_common.FINGERPRINT_PREFIX)


# ---------------------------------------------------------------------------
# AC 3: trois etats, dont `refused`
# ---------------------------------------------------------------------------


def test_the_three_states_are_the_closed_vocabulary() -> None:
    assert encode_previz.ENCODE_PREVIZ_STATES == ("planned", "encoded", "refused")
    assert encode_previz.ENCODE_PREVIZ_STATE_PLANNED == previz_common.PREVIZ_STATE_PLANNED


def test_an_unknown_state_is_refused() -> None:
    with pytest.raises(EPE, match="Etat de previz inconnu"):
        build(state="rendered")


def test_an_unknown_state_is_refused_before_any_projection() -> None:
    """La garde d'etat passe **avant** tout le reste, et l'ordre compte.

    Sans elle en tete du constructeur, un etat inconnu traverse la projection et
    ressort sous le premier champ manquant -- « lot_state est obligatoire en
    etat 'rendered' » --, c'est-a-dire un diagnostic qui parle d'un champ absent
    pour un etat qui n'existe pas. La garde du document (`__post_init__`) est le
    dernier filet, pas le premier: elle ne se declenche qu'apres que tout a ete
    projete.
    """
    with pytest.raises(EPE, match="Etat de previz inconnu"):
        build_encode_previz(
            generated_at_utc=GENERATED_AT,
            project_id="proj-a",
            lot_id="lot-a",
            profile_id="prores_hq",
            container="mov",
            state="rendered",
        )


def test_a_refused_document_carries_its_motive_and_its_candidates() -> None:
    document = encode_previz_to_json_dict(build_refused())
    assert document["state"] == "refused"
    assert document["refusal"]["code"] == "TIRAGES_MULTIPLES"
    assert len(document["refusal"]["candidates"]) == 2
    assert "plan" not in document
    assert "fingerprints" not in document
    # L'identite reste: le profil est resolu par 6.1 avant toute garde.
    assert document["subject"] == {
        "project_id": "proj-a",
        "lot_id": "lot-a",
        "profile_id": "prores_hq",
        "container": "mov",
    }


def test_the_refused_candidates_are_transported_verbatim_in_order() -> None:
    """Meme regime que les avertissements: ni tri, ni deduplication, ni ordre
    recompose.

    Ce sont les lignes de `describe_lot_candidate` que l'operateur vient de lire
    dans la sortie CLI; les reordonner ferait dire au document autre chose que
    ce que la commande a affiche. Un cardinal ne mesure rien ici -- inverser la
    liste laisse `len` inchange.
    """
    candidats = (
        "lot-a-t2 (etat scan, cardinal attendu 5, ...)",
        "lot-a-t1 (etat scan, cardinal attendu 13, ...)",
        "lot-a-t2 (etat scan, cardinal attendu 5, ...)",
    )
    document = encode_previz_to_json_dict(
        build_refused(refused_candidates=candidats)
    )
    assert document["refusal"]["candidates"] == list(candidats)
    # Non trie: l'ordre verse n'est pas l'ordre alphabetique.
    assert document["refusal"]["candidates"] != sorted(candidats)
    # Non dedoublonne: le doublon dit qu'un candidat a ete nomme deux fois.
    assert len(document["refusal"]["candidates"]) == 3


def test_a_candidate_that_is_not_text_is_refused() -> None:
    """Sans la garde, une chaine passee au lieu d'un tuple serait explosee
    caractere par caractere et le document porterait des candidats d'une
    lettre."""
    with pytest.raises(EPE, match="pas une chaine"):
        build_refused(refused_candidates="lot-a-t1")
    with pytest.raises(EPE, match="ordonnee"):
        build_refused(refused_candidates={"lot-a-t1", "lot-a-t2"})
    with pytest.raises(EPE, match="chaine non vide"):
        build_refused(refused_candidates=("lot-a-t1", 42))


def test_a_refused_document_carries_its_warnings() -> None:
    """Les constats de 6.1 accompagnent aussi un refus.

    `plan_encode` en emet avant de refuser -- fichiers ecartes, noms non
    conformes -- et les perdre priverait l'interface de ce qui explique le
    refus. Le seau est le meme dans les trois etats.
    """
    document = encode_previz_to_json_dict(
        build_refused(
            encode_warnings=(
                encode_previz.NOMS_NON_CONFORMES,
                encode_previz.FICHIERS_VIDES_ECARTES,
                encode_previz.NOMS_NON_CONFORMES,
            )
        )
    )
    assert document["warnings"] == {
        "encode": [
            "NOMS_NON_CONFORMES",
            "FICHIERS_VIDES_ECARTES",
            "NOMS_NON_CONFORMES",
        ]
    }


def test_a_refused_document_without_a_motive_is_refused() -> None:
    with pytest.raises(EPE, match="refusal_code est obligatoire"):
        build_refused(refusal_code=None)


def test_a_motive_outside_the_refusal_vocabulary_is_refused() -> None:
    with pytest.raises(EPE, match="Motif de refus"):
        build_refused(refusal_code="PAS_UN_REFUS")


def test_an_informational_code_is_not_a_refusal_motive() -> None:
    with pytest.raises(EPE, match="Motif de refus"):
        build_refused(refusal_code=encode_previz.LOT_INCOMPLET_ASSUME)


def test_a_motive_outside_the_refused_state_is_refused() -> None:
    with pytest.raises(EPE, match="n'a de sens qu'en etat"):
        build(refusal_code="TIRAGES_MULTIPLES")
    with pytest.raises(EPE, match="n'a de sens qu'en etat"):
        build(refused_candidates=("lot-a-t1",))


@pytest.mark.parametrize(
    "argument, valeur",
    [
        ("lot_state", "scan"),
        ("resolution", make_resolution()),
        ("source_size", (3307, 1860)),
        ("frames", make_frames()),
        ("exact_frame_rate", "25/2"),
        ("fps_target", 12.5),
        ("timecode", make_timecode()),
        ("timecode_reliability", "reliable"),
        ("verdict", make_verdict()),
        ("container_tags", {"a": "b"}),
        ("master_path_relative", "outputs/m.mov"),
        ("estimated_bytes", 1),
        ("encoded_bytes", 1),
        ("nonconforming_files", ("a.txt",)),
        ("empty_files", ("b.tif",)),
        ("declared_bounds", ("01:00:00:00", None)),
        ("timecode_reliability_vocabulary", ("reliable",)),
    ],
)
def test_a_refused_document_carries_no_element_of_plan(argument, valeur) -> None:
    """Aucune exception de refus de 6.1 ne transporte d'`EncodePlan`: publier un
    plan sous un refus annoncerait un encodage que 6.1 vient de refuser."""
    with pytest.raises(EPE, match="n'a pas de sens en etat"):
        build_refused(**{argument: valeur})


@pytest.mark.parametrize(
    "argument, valeur",
    [
        ("lot_state", ""),
        ("timecode_reliability", ""),
        ("master_path_relative", ""),
        ("estimated_bytes", 0),
        ("encoded_bytes", 0),
        ("container_tags", {}),
        ("declared_bounds", (None, "")),
    ],
)
def test_a_falsy_element_of_plan_is_still_refused(argument, valeur) -> None:
    """« Fourni » veut dire **pose**, pas « vrai ».

    Un `estimated_bytes=0`, un `container_tags={}` ou un `lot_state=""` sont des
    valeurs que l'appelant a ecrites: les laisser passer sous un refus ferait
    entrer du materiel de plan dans un document qui annonce qu'aucun encodage
    n'aura lieu. La parametrisation nominale n'employant que des valeurs vraies,
    rien ne mesurait la difference entre « pose » et « vrai ».
    """
    with pytest.raises(EPE, match="n'a pas de sens en etat"):
        build_refused(**{argument: valeur})


@pytest.mark.parametrize(
    "argument, valeur",
    [
        ("frames", []),
        ("nonconforming_files", ()),
        ("empty_files", []),
        ("declared_bounds", (None, None)),
        ("refused_candidates", ()),
    ],
)
def test_the_default_of_a_sequence_argument_is_not_supplied_material(
    argument, valeur
) -> None:
    """Le pendant du test ci-dessus, et il est necessaire.

    Les arguments de sequence ont `()` pour defaut: y voir du materiel fourni
    ferait refuser **tout** document `refused`, y compris celui que 6.1 produit
    reellement. Les deux tests bornent la semantique de « fourni » des deux
    cotes, sur le regime de defaut de chaque argument.
    """
    assert (
        encode_previz_to_json_dict(build_refused(**{argument: valeur}))["state"]
        == "refused"
    )


@pytest.mark.parametrize(
    "argument",
    [
        "lot_state",
        "resolution",
        "source_size",
        "timecode",
        "timecode_reliability",
        "verdict",
        "container_tags",
        "master_path_relative",
        "estimated_bytes",
    ],
)
def test_a_planned_document_requires_every_element_of_plan(argument) -> None:
    with pytest.raises(EPE, match="obligatoire"):
        build(**{argument: None})


def test_a_planned_document_requires_a_non_empty_sequence() -> None:
    with pytest.raises(EPE, match="vide"):
        build(frames=())


def test_an_unsettled_resolution_is_refused() -> None:
    """`native` non arretee: `settle_resolution` ramene toute demande sur une
    geometrie definitive avant de nommer le master."""
    with pytest.raises(EPE, match="arretee"):
        build(
            resolution=make_resolution(
                requested="native", origin="native", resolution_id=None, size=None
            )
        )


def test_encoded_bytes_is_mandatory_in_the_encoded_state_and_forbidden_elsewhere() -> None:
    document = encode_previz_to_json_dict(
        build(state="encoded", encoded_bytes=987654321)
    )
    assert document["state"] == "encoded"
    assert document["plan"]["encoded_bytes"] == 987654321
    with pytest.raises(EPE, match="encoded_bytes est obligatoire"):
        build(state="encoded")
    with pytest.raises(EPE, match="n'a pas de sens"):
        build(encoded_bytes=1)


def test_the_estimated_size_is_a_majorant_carried_next_to_the_real_one() -> None:
    """Question 2, tranchee dans le code de 6.1: oui, mais jamais optimiste.
    Elle est **fournie** par l'appelant, jamais recalculee ici."""
    document = encode_previz_to_json_dict(
        build(state="encoded", encoded_bytes=1, estimated_bytes=999999)
    )["plan"]
    assert document["estimated_bytes"] == 999999
    assert document["encoded_bytes"] == 1
    # Aucune confrontation: une estimation plus petite que le reel passe aussi.
    autre = encode_previz_to_json_dict(
        build(state="encoded", encoded_bytes=999999, estimated_bytes=1)
    )["plan"]
    assert autre["estimated_bytes"] == 1


def test_a_hand_built_document_cannot_mix_a_plan_and_a_refusal() -> None:
    previz = build()
    refuse = build_refused()
    with pytest.raises(EPE, match="ne porte aucun plan"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="refused",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=previz.plan,
            refusal=refuse.refusal,
        )


def test_a_hand_built_document_cannot_separate_the_plan_from_its_fingerprint() -> None:
    previz = build()
    with pytest.raises(EPE, match="accompagne le plan"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=previz.plan,
            fingerprints=None,
        )
    with pytest.raises(EPE, match="accompagne le plan"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="refused",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            refusal=build_refused().refusal,
            fingerprints=previz.fingerprints,
        )


def test_a_hand_built_refused_document_without_a_motive_is_refused() -> None:
    """La garde du builder n'est pas la garde du document.

    `_refusal_section` rattrape l'appelant du constructeur; la story 7.4, elle,
    edite des documents et ne repasse pas forcement par lui.
    """
    previz = build()
    with pytest.raises(EPE, match="porte le motif du refus"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="refused",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
        )


def test_a_hand_built_document_cannot_carry_a_motive_outside_the_refused_state() -> None:
    previz = build()
    with pytest.raises(EPE, match="n'a de sens qu'en etat"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="planned",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=previz.plan,
            fingerprints=previz.fingerprints,
            refusal=build_refused().refusal,
        )


def test_a_hand_built_document_cannot_carry_an_unknown_state() -> None:
    """Meme motif: le vocabulaire d'etats est ferme **au niveau du document**,
    pas seulement a l'entree du constructeur."""
    previz = build()
    with pytest.raises(EPE, match="Etat de previz inconnu"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="rendered",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
            plan=previz.plan,
            fingerprints=previz.fingerprints,
        )


def test_a_hand_built_planned_document_without_plan_is_refused() -> None:
    previz = build()
    with pytest.raises(EPE, match="porte le plan"):
        encode_previz.EncodePreviz(
            previz_schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state="planned",
            generated_at_utc=previz.generated_at_utc,
            subject=previz.subject,
            warnings=previz.warnings,
        )


# ---------------------------------------------------------------------------
# AC 13: la fiabilite du timecode par profil, transportee verbatim
# ---------------------------------------------------------------------------


def test_the_timecode_reliability_is_transported_verbatim_from_the_catalogue() -> None:
    reliability = video_metadata.TECHNICAL_METADATA_MATRIX["timecode"]["reliability"]
    assert reliability["prores_hq"] == "reliable"
    assert reliability["h264_delivery"] == "best_effort"
    for profile_id, declaree in reliability.items():
        document = encode_previz_to_json_dict(
            build(profile_id=profile_id, timecode_reliability=declaree)
        )
        assert document["plan"]["timecode"]["reliability"] == declaree


def test_the_reliability_vocabulary_can_be_versed_by_the_caller() -> None:
    """Troisieme voie de 5.8: le controle passe du temps de test au temps de
    construction, sans import ni copie de vocabulaire."""
    vocabulaire = sorted(
        set(video_metadata.TECHNICAL_METADATA_MATRIX["timecode"]["reliability"].values())
    )
    assert vocabulaire == ["best_effort", "reliable"]
    document = encode_previz_to_json_dict(
        build(timecode_reliability_vocabulary=vocabulaire)
    )
    assert document["plan"]["timecode"]["reliability"] == "reliable"
    with pytest.raises(EPE, match="hors du vocabulaire"):
        build(
            timecode_reliability="tres_fiable",
            timecode_reliability_vocabulary=vocabulaire,
        )
    # Sans vocabulaire verse, rien n'est controle: le regime par defaut est
    # exactement celui des jumelles.
    assert (
        encode_previz_to_json_dict(build(timecode_reliability="tres_fiable"))["plan"][
            "timecode"
        ]["reliability"]
        == "tres_fiable"
    )


def test_the_versed_vocabulary_is_read_as_an_ordered_sequence() -> None:
    """Le vocabulaire verse passe par la meme garde que les autres collections.

    Sans elle, une chaine y serait exploseee caractere par caractere -- le
    vocabulaire `"reliable"` deviendrait huit lettres -- et le refus qui suit
    parlerait d'une valeur hors vocabulaire au lieu de nommer la faute.
    """
    with pytest.raises(EPE, match="pas une chaine"):
        build(timecode_reliability_vocabulary="reliable")
    with pytest.raises(EPE, match="ordonnee"):
        build(timecode_reliability_vocabulary={"reliable", "best_effort"})


def test_the_reliability_is_a_constatation_outside_the_fingerprint() -> None:
    """Propriete constante du catalogue indexee par `profile_id`: elle ne decide
    rien."""
    assert "timecode_reliability" not in encode_previz.DECISION_FINGERPRINT_FIELDS
    assert decision_of(build(timecode_reliability="best_effort")) == decision_of(build())


# ---------------------------------------------------------------------------
# Regle des fabriques et borne basse reelle du depot
# ---------------------------------------------------------------------------


def test_le_lot_d_une_seule_frame_est_projete() -> None:
    """Borne basse **reelle** du depot: `rush_test_235_1920x817_25fps_1-81a74b3c`
    porte `expected_frame_count: 1`. C'est le cas ou une sequence ordonnee
    degenere en n'ayant plus d'ordre observable, et il doit passer."""
    document = encode_previz_to_json_dict(
        build(
            frames=[make_frame(0, "f000.tif", "01:00:00:00")],
            verdict=make_verdict(
                expected=1,
                found=1,
                complete=True,
                synthetic_present=(),
                synthetic_missing=(),
                missing_pages=(),
            ),
        )
    )["plan"]
    assert len(document["sequence"]) == 1
    assert document["completeness"]["complete"] is True
    assert document["sequence"][0]["synthetic"] is False


def test_the_target_frame_is_never_the_first_one() -> None:
    """Un appariement positionnel fautif qui rendrait toujours le premier
    element ne se demasque pas autrement (mutants M25 de 5.7, M33 de 5.6)."""
    frames = make_frames()
    frames[2] = make_frame(2, "cible.tif", "01:00:00:99", synthetic=True)
    sequence = encode_previz_to_json_dict(build(frames=frames))["plan"]["sequence"]
    assert sequence[2]["frame_path_relative"] == "frames/lot-a/cible.tif"
    assert sequence[2]["frame_timecode"] == "01:00:00:99"
    assert sequence[2]["synthetic"] is True
    assert sequence[0]["frame_path_relative"] == "frames/lot-a/f000.tif"


def test_the_factory_produces_distinguishable_elements() -> None:
    """Garde-fou de la regle elle-meme: un remplissage uniforme rendrait
    invisible toute erreur d'appariement."""
    frames = make_frames()
    assert len({f.frame_path_relative for f in frames}) == len(frames)
    assert len({f.frame_timecode for f in frames}) == len(frames)
    assert len({f.output_rank for f in frames}) == len(frames)
    assert len({f.synthetic for f in frames}) == 2


# ---------------------------------------------------------------------------
# La prose normative de la docstring, confrontee au code
# ---------------------------------------------------------------------------
#
# Muter de la prose n'est pas l'usage, et le motif est celui de la famille `T`
# de la campagne de 6.5: la revue y a trouve **trois** documents affirmant une
# chose que le code ne faisait pas. Un enonce faux ne coute rien tant que
# personne ne le lit, et cher a la story suivante qui le reprend pour argent
# comptant -- c'est exactement ce qui a rendu la revision 3 de cette story
# necessaire. Les deux enonces que ce module pose comme normatifs sont donc
# tenus ici.


def test_the_docstring_does_not_promise_a_previz_family_of_warnings() -> None:
    docstring = encode_previz.__doc__ or ""
    assert "il n'y a donc pas de famille `previz` dans `warnings`" in docstring
    assert "previz" not in encode_previz_to_json_dict(build())["warnings"]


def test_the_docstring_says_francophone_and_the_vocabulary_is() -> None:
    docstring = encode_previz.__doc__ or ""
    assert "Le vocabulaire de cette previz est FRANCOPHONE" in docstring
    tous = (
        encode_previz.ENCODE_PREVIZ_WARNING_CODES
        + encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    )
    # Mesure, pas opinion: un seul code anglais dans les 42 (37 + 4 depuis la
    # story 6.6, + `RANGS_DE_MASTER_EPUISES` a la liaison du 2026-09-01), et
    # c'est celui que le producteur porte deja
    # (`HETEROGENEOUS_FRAME_SHAPES`). Le code neuf est francophone : il ne
    # change donc que le cardinal, jamais ce que ce test mesure vraiment.
    anglais = [code for code in tous if code == "HETEROGENEOUS_FRAME_SHAPES"]
    assert len(anglais) == 1
    # 43 avec `VERSION_ET_ECRASEMENT_COMBINES` (story 11.8), 44 avec
    # `RECONSTRUCTION_INCONNUE` (story 6.8). Le code neuf est FRANCOPHONE : il
    # ne bouge donc que ce cardinal, jamais la propriete que ce test mesure --
    # le comptage des codes anglais reste a UN, et il reste le meme.
    assert len(tous) == 44
    for code in tous:
        if code in anglais:
            continue
        assert code in encode.ENCODE_CODES


# ---------------------------------------------------------------------------
# Serialisation canonique et gel du contrat
# ---------------------------------------------------------------------------


def test_two_builds_render_the_same_bytes() -> None:
    assert rendered(build()) == rendered(build())
    assert rendered(build_refused()) == rendered(build_refused())


#: Fixture canonique **figee en dur**, octet pour octet, comme chez les trois
#: jumelles (`test_scan_previz.py:819`, `test_pdf_previz.py:294`). Tout
#: renommage de cle du document rendu casse ce test, et l'empreinte gelee casse
#: aussi si la recette ou les champs de decision bougent.
#:
#: Elle etait auparavant declaree, annoncee « gel octet pour octet du contrat »
#: -- et **lue par aucune assertion**, sa valeur ne correspondant d'ailleurs pas
#: au document reel. Vingt-deux renommages de cle avaient ete joues contre la
#: suite: vingt etaient tues **incidemment**, par des tests qui lisent la cle
#: pour une autre raison, et deux passaient -- dont `plan.lot_state`, qui est
#: une entree de decision scellee par l'empreinte. Un gel partiel ne gele pas un
#: contrat: il gele ce que d'autres tests regardent deja.
FROZEN_CANONICAL_FIXTURE = (
    '{"fingerprints":{"decision":"sha256-v1:65db822e068dc4da0ccf9d8b5'
    '66db03b0133d37b08422eda7abdf71cb9316c87"},"generated_at_utc":"20'
    '26-08-11T12:00:00Z","kind":"encode","plan":{"completeness":{"com'
    'plete":false,"expected":13,"found":13,"missing_pages":[4,7],"syn'
    'thetic_missing":["f009.tif"],"synthetic_present":["f001.tif"]},"'
    'container_tags":{"lot_id":"lot-a","project_id":"proj-a"},"declar'
    'ed_bounds":{"first_frame_timecode":"01:00:00:00","last_frame_tim'
    'ecode":"01:00:00:12"},"discarded":{"empty_files":["f003.tif"],"n'
    'onconforming_files":["intrus.txt"]},"estimated_bytes":1234567,"f'
    'ps_target_exact":"25/2","lot_state":"scan","master_path_relative'
    '":"outputs/lot-a_prores_hq.mov","resolution":{"height_px":1080,"'
    'origin":"defaut","requested":"hd1080","resolution_id":"hd1080","'
    'width_px":1920},"sequence":[{"frame_path_relative":"frames/lot-a'
    '/f000.tif","frame_timecode":"01:00:00:00","output_rank":0,"synth'
    'etic":false},{"frame_path_relative":"frames/lot-a/f001.tif","fra'
    'me_timecode":"01:00:00:01","output_rank":1,"synthetic":true},{"f'
    'rame_path_relative":"frames/lot-a/f002.tif","frame_timecode":"01'
    ':00:00:02","output_rank":2,"synthetic":false}],"source_size":{"h'
    'eight_px":1860,"width_px":3307},"timecode":{"base_rate":"25/1","'
    'emitted":"01:00:00:00","manifest_value":"00:59:59:12","reliabili'
    'ty":"reliable"}},"previz_schema_version":"previz-1","state":"pla'
    'nned","subject":{"container":"mov","lot_id":"lot-a","profile_id"'
    ':"prores_hq","project_id":"proj-a"},"warnings":{"encode":["APPRO'
    'XIMATION_SRGB_TAGUEE_REC709","LOT_INCOMPLET_ASSUME"]}}'
)

#: Le document `refused` a sa propre forme -- une section `refusal` de premier
#: niveau, ni `plan` ni `fingerprints`, et un seau d'avertissements **present**
#: meme vide. Le geler separement est necessaire: aucun de ses champs n'apparait
#: dans la fixture ci-dessus.
FROZEN_CANONICAL_REFUSAL_FIXTURE = (
    '{"generated_at_utc":"2026-08-11T12:00:00Z","kind":"encode","prev'
    'iz_schema_version":"previz-1","refusal":{"candidates":["lot-a-t1'
    ' (etat scan, cardinal attendu 13, ...)","lot-a-t2 (etat scan, ca'
    'rdinal attendu 5, ...)"],"code":"TIRAGES_MULTIPLES"},"state":"re'
    'fused","subject":{"container":"mov","lot_id":"lot-a","profile_id'
    '":"prores_hq","project_id":"proj-a"},"warnings":{"encode":[]}}'
)


def test_the_canonical_form_is_frozen() -> None:
    """Le gel octet pour octet du contrat, dans les deux formes du document."""
    assert rendered(build()) == FROZEN_CANONICAL_FIXTURE
    assert rendered(build_refused()) == FROZEN_CANONICAL_REFUSAL_FIXTURE
    document = rendered(build())
    # Et la **forme** canonique elle-meme: cles triees, aucun espace, ASCII.
    assert " " not in document
    assert document == document.encode("ascii").decode("ascii")


def test_the_json_document_carries_only_json_types() -> None:
    def visiter(valeur):
        if isinstance(valeur, dict):
            for cle, sous in valeur.items():
                assert isinstance(cle, str)
                visiter(sous)
        elif isinstance(valeur, list):
            for sous in valeur:
                visiter(sous)
        else:
            assert isinstance(valeur, (str, int, float, bool)) or valeur is None

    visiter(encode_previz_to_json_dict(build()))
    visiter(encode_previz_to_json_dict(build_refused()))
    # Et sur le seul sous-dictionnaire **libre** du document, la ou l'assertion
    # etait vraie par vacuite: les tags de `build()` n'ont que des cles et des
    # valeurs chaines, si bien que la visite ne rencontrait aucun type douteux.
    visiter(
        encode_previz_to_json_dict(
            build(
                container_tags={
                    "entier": 1,
                    "flottant": 1.5,
                    "booleen": True,
                    "liste": [1, "deux"],
                    "imbrique": {"cle": None},
                }
            )
        )
    )


# ---------------------------------------------------------------------------
# Gardes de type et entrees malformees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argument",
    ["project_id", "lot_id", "profile_id", "container"],
)
def test_an_empty_identity_field_is_refused(argument) -> None:
    with pytest.raises(EPE):
        build(**{argument: ""})
    with pytest.raises(EPE):
        build(**{argument: None})


def test_a_boolean_never_passes_for_a_cardinal() -> None:
    """`isinstance(True, int)` vaut vrai en Python: la garde vit dans le socle."""
    with pytest.raises(EPE, match="entier"):
        build(estimated_bytes=True)
    with pytest.raises(EPE, match="entier"):
        build(verdict=make_verdict(found=True))


def test_a_negative_cardinal_is_refused() -> None:
    with pytest.raises(EPE, match="cardinal"):
        build(estimated_bytes=-1)
    with pytest.raises(EPE, match="cardinal"):
        build(verdict=make_verdict(expected=-1))
    with pytest.raises(EPE, match="cardinal"):
        build(verdict=make_verdict(found=-1))
    # Le poids **reel** du master est un cardinal comme les autres: un fichier
    # de taille negative n'existe pas, et l'annoncer serait le seul mensonge que
    # l'etat `encoded` puisse commettre.
    with pytest.raises(EPE, match="cardinal"):
        build(state="encoded", encoded_bytes=-1)


@pytest.mark.parametrize(
    "entree",
    [
        {"lot_state": ""},
        {"timecode_reliability": ""},
        {"exact_frame_rate": ""},
        {"container": ""},
        {"resolution": make_resolution(origin="")},
        {"resolution": make_resolution(requested="")},
        {"timecode": make_timecode(manifest_value="")},
        {"verdict": make_verdict(synthetic_present=("",))},
    ],
)
def test_an_empty_string_is_refused_wherever_text_is_expected(entree) -> None:
    """`str(...)` a la place de la garde passe inapercu tant qu'aucun test ne
    verse la chaine vide.

    `lot_state` n'est pas un champ decoratif: c'est une **entree de decision**
    scellee par l'empreinte, et deux documents dont l'un porte un etat vide
    doivent se distinguer par un refus, pas par une empreinte.
    """
    with pytest.raises(EPE):
        build(**entree)


def test_a_non_boolean_completeness_verdict_is_refused() -> None:
    with pytest.raises(EPE, match="booleen"):
        build(verdict=make_verdict(complete="oui"))


@pytest.mark.parametrize("taille", [(0, 1080), (1920, -1), (1920,), (1920, 1080, 3), "1920x1080"])
def test_a_malformed_geometry_is_refused(taille) -> None:
    with pytest.raises(EPE):
        build(source_size=taille)


def test_a_structurally_incomplete_producer_lands_in_the_hierarchy() -> None:
    """Un champ absent chez un producteur doit tomber dans la garde, pas se
    relire « rien »."""
    incomplet = SimpleNamespace(requested="hd1080", origin="defaut")
    with pytest.raises(EPE, match="structurellement incomplete"):
        build(resolution=incomplet)
    with pytest.raises(EPE, match="structurellement incomplete"):
        build(timecode=SimpleNamespace(emitted="01:00:00:00"))
    with pytest.raises(EPE, match="structurellement incomplete"):
        build(verdict=SimpleNamespace(expected=1, found=1))
    frames = make_frames()
    frames[1] = SimpleNamespace(output_rank=1, frame_timecode="01:00:00:01")
    with pytest.raises(EPE, match="structurellement incomplete"):
        build(frames=frames)


def test_a_producer_field_that_explodes_lands_in_the_hierarchy_too() -> None:
    """Le second type retraduit par le filet, et il a un emetteur reel.

    Le typage est **structurel**: lire un attribut execute le code du
    producteur, et un champ calcule qui explose remonte l'exception de ce
    producteur -- ici un `TypeError`, que l'appelant Epic 7 n'attraperait pas en
    ecrivant `except EncodePrevizError`. Les deux types du filet ont ainsi un
    emetteur nomme et exerce; `IndexError` et `KeyError` n'en avaient aucun et
    ont ete retires.
    """

    class ResolutionQuiExplose:
        requested = "hd1080"
        origin = "defaut"
        resolution_id = None

        @property
        def size(self):
            raise TypeError("champ calcule casse chez le producteur")

    with pytest.raises(EPE, match="structurellement incomplete"):
        build(resolution=ResolutionQuiExplose())


def test_the_error_net_of_the_builder_carries_no_type_without_an_emitter() -> None:
    """La liste des types retraduits est **epinglee**.

    Cet epic a deja paye deux branches sans emetteur possible. Elargir ce filet
    sans exhiber l'entree qui l'atteint fait tomber ce test, plutot que
    d'attendre une campagne de mutation.
    """
    source = MODULE_PATH.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    filets = [
        handler
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Try)
        for handler in noeud.handlers
        if isinstance(handler.type, ast.Tuple)
        and any(
            isinstance(element, ast.Name) and element.id == "AttributeError"
            for element in handler.type.elts
        )
    ]
    assert len(filets) == 1
    assert [element.id for element in filets[0].type.elts] == [
        "AttributeError",
        "TypeError",
    ]


def test_a_malformed_timestamp_is_refused_before_any_projection() -> None:
    """Motif de `test_an_unknown_state_is_refused_before_any_projection`.

    Le durcissement d'enveloppe rattrape un horodatage menteur en fin de course
    et avec le meme message: sans une mesure d'**ordre**, retirer la
    normalisation du constructeur ne se verrait plus. Or l'ordre compte des que
    l'entree porte deux fautes -- le refus rendu serait celui d'un autre champ,
    et l'appelant corrigerait le mauvais.
    """
    with pytest.raises(EPE, match="horodatage UTC"):
        build_encode_previz(
            generated_at_utc="pasunedate",
            project_id="proj-a",
            lot_id="lot-a",
            profile_id="prores_hq",
            container="mov",
            lot_state="scan",
            resolution=make_resolution(),
            source_size=(3307, 1860),
            frames=make_frames(),
            exact_frame_rate="25/2",
            timecode=make_timecode(),
            timecode_reliability="reliable",
            verdict=make_verdict(),
            container_tags={},
            master_path_relative="outputs/m.mov",
            # Seconde faute, volontaire et refusee **plus tard** dans le
            # pipeline: c'est elle qui rend l'ordre observable.
            estimated_bytes=-1,
        )


def test_a_malformed_timestamp_is_refused() -> None:
    with pytest.raises(EPE, match="horodatage UTC"):
        build(generated_at_utc="2026-08-11 12:00:00")
    with pytest.raises(EPE, match="horodatage UTC"):
        build(generated_at_utc=GENERATED_AT + "\n")
    with pytest.raises(EPE, match="aucun instant reel"):
        build(generated_at_utc="2026-02-30T25:61:61Z")


def test_declared_bounds_of_the_wrong_shape_are_refused() -> None:
    with pytest.raises(EPE, match="2 composantes"):
        build(declared_bounds=("01:00:00:00",))
    # Trois bornes: sans le refus **exact**, un triplet etait silencieusement
    # tronque a ses deux premiers elements et la troisieme valeur disparaissait
    # du document sans un mot.
    with pytest.raises(EPE, match="2 composantes"):
        build(declared_bounds=("01:00:00:00", "01:00:00:12", "01:00:00:24"))
    with pytest.raises(EPE, match="pas une chaine"):
        build(declared_bounds="01:00:00:00")


def test_a_frame_without_a_timecode_is_refused() -> None:
    """Le timecode d'une frame est obligatoire, jamais optionnel.

    Il entre dans le **sous-condensat de sequence**: le rendre optionnel y
    ferait entrer un `None`, poserait un `"frame_timecode": null` au document --
    contre la regle cardinale du projet -- et scellerait une empreinte sur une
    valeur absente.
    """
    frames = make_frames()
    frames[2].frame_timecode = None
    with pytest.raises(EPE, match="chaine non vide"):
        build(frames=frames)


def test_a_rank_and_a_page_index_are_positional_never_measures() -> None:
    """Ils sont transportes **verbatim**, domaine compris.

    La garde de cardinal vit sur ce que le document annonce comme une mesure --
    une taille en octets, un cardinal de frames -- et pas sur ce qu'il annonce
    comme une **position**. Un rang ou un index de page negatif est une entree
    incoherente de 6.1, et la regle cardinale du module est qu'une entree
    incoherente ressorte incoherente: la corriger ou la refuser ici ferait
    diverger la previz de ce que la production fera, et masquerait le defaut
    chez son producteur.
    """
    frames = make_frames()
    frames[2].output_rank = -1
    document = encode_previz_to_json_dict(build(frames=frames))["plan"]
    assert [frame["output_rank"] for frame in document["sequence"]] == [0, 1, -1]
    verdict = encode_previz_to_json_dict(
        build(verdict=make_verdict(missing_pages=(-3, 0)))
    )["plan"]["completeness"]
    assert verdict["missing_pages"] == [-3, 0]


def test_missing_pages_are_page_indexes_never_timecodes() -> None:
    """Le piege exact que 6.1 a paye d'un bloquant: une page absente ne laisse
    aucun slot, donc aucun timecode n'est recalculable pour elle."""
    with pytest.raises(EPE, match="entier"):
        build(verdict=make_verdict(missing_pages=("01:00:00:04",)))
    document = encode_previz_to_json_dict(build())["plan"]["completeness"]
    assert document["missing_pages"] == [4, 7]


# ---------------------------------------------------------------------------
# Confrontation aux vrais producteurs de 6.1
# ---------------------------------------------------------------------------


def test_the_document_projects_the_real_dataclasses_of_story_6_1() -> None:
    """Un renommage de champ chez 6.1 fait tomber ce test, au lieu de laisser
    casser le premier consommateur reel en `AttributeError` brute."""
    resolution = encode.settle_resolution(
        encode.resolve_output_resolution(None), (3307, 1860)
    )
    timecode = encode.TimecodePlan(
        emitted="01:00:00:00", manifest_value="01:00:00:00", base_rate="25/1"
    )
    verdict = encode.CompletenessVerdict(
        expected=3,
        found=3,
        synthetic_present=("f001.tif",),
        synthetic_missing=(),
        missing_pages=(),
        complete=True,
    )
    document = encode_previz_to_json_dict(
        build(resolution=resolution, timecode=timecode, verdict=verdict)
    )["plan"]
    assert document["resolution"] == {
        "requested": "hd1080",
        "origin": "defaut",
        "width_px": 1920,
        "height_px": 1080,
        "resolution_id": "hd1080",
    }
    assert document["completeness"]["complete"] is True
    assert document["timecode"]["base_rate"] == "25/1"


def test_the_four_origins_of_a_real_target_resolution_are_transported() -> None:
    """`origin` a **quatre** valeurs, pas un booleen « vient du defaut »."""
    origines = set()
    for demande, source in (
        (None, (3307, 1860)),
        ("uhd2160", (3307, 1860)),
        ("native", (3307, 1860)),
        ("1000x1000", (3307, 1860)),
    ):
        resolution = encode.settle_resolution(
            encode.resolve_output_resolution(demande), source
        )
        document = encode_previz_to_json_dict(build(resolution=resolution))["plan"]
        origines.add(document["resolution"]["origin"])
    assert origines == {"defaut", "registre", "native", "personnalisee"}


def test_a_real_plan_findings_tuple_is_accepted_verbatim() -> None:
    """Tout ce que 6.1 verse dans `findings` appartient au vocabulaire d'ici."""
    document = encode_previz_to_json_dict(
        build(encode_warnings=encode.ENCODE_INFORMATIONAL_CODES)
    )
    assert document["warnings"]["encode"] == list(encode.ENCODE_INFORMATIONAL_CODES)


def test_every_refusal_code_of_story_6_1_can_be_projected() -> None:
    for code in encode.ENCODE_REFUSAL_CODES:
        document = encode_previz_to_json_dict(build_refused(refusal_code=code))
        assert document["refusal"]["code"] == code
