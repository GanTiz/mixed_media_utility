from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io import naming, project_layout


def _v2_manifest_with_rush(rush_id: str = "rush-001", fps_target: float = 24.0) -> dict:
    return {
        "schema_version": "2.0",
        "project_id": "example-001",
        "rushes": [{"rush_id": rush_id, "source_path": "scans/rush-001.mp4"}],
        "lots": [{"lot_id": "lot-001", "rush_id": rush_id, "state": "extraction"}],
        "artifacts": {"frames_dir": "extract-frames/", "outputs_dir": "outputs/"},
        "color": {"target_colorspace": "rec709"},
        "video": {"fps_source": fps_target, "fps_target": fps_target},
        "reconstruction": {"template_id": "template-a4-16x9", "patch_preset_id": "patch-preset-mvp"},
    }


def test_rush_dir_slug_formats_integer_fps_without_decimal() -> None:
    assert project_layout.rush_dir_slug("rush-001", 24.0) == "rush-001_24"


def test_rush_dir_slug_renders_fractional_fps_like_format_fps_short() -> None:
    """ARB-3 (decisions-2026-08-03.md, decision 2): the directory fragment and
    the file name fragment must agree on every target rate. This test replaces
    `test_rush_dir_slug_keeps_fractional_fps`, which locked the pre-arbitration
    value `rush-001_23.976`."""
    assert project_layout.rush_dir_slug("rush-001", 23.976) == "rush-001_23p976"
    assert project_layout.rush_dir_slug("rush-001", 12.5) == "rush-001_12p5"


def test_rush_dir_slug_fps_fragment_equals_format_fps_short_on_every_rate() -> None:
    for fps in (24, 24.0, 25, 30, 12.5, 23.976, 29.97):
        assert project_layout.rush_dir_slug("rush-001", fps) == f"rush-001_{naming.format_fps_short(fps)}"


def test_rush_dir_slug_never_contains_a_dot() -> None:
    """A dot violates the `^[A-Za-z0-9_-]+$` pattern the schema imposes on
    identifiers, so no slug may ever carry one (story 3.1, piege 2)."""
    for fps in (12.5, 23.976, 29.97, 59.94):
        assert "." not in project_layout.rush_dir_slug("rush-001", fps)


def test_frames_dir_and_output_frames_dir_are_namespaced_by_rush_and_fps(tmp_path: Path) -> None:
    frames = project_layout.extract_frames_dir(tmp_path, "rush-001", 24.0)
    output_frames = project_layout.scan_frames_dir(tmp_path, "rush-001", 24.0)

    # Story 11.14 : le vocabulaire d'Egan sur les deux dossiers.
    assert frames == tmp_path / "extract-frames" / "rush-001_24"
    assert output_frames == tmp_path / "frames-scannees" / "rush-001_24"


def test_ensure_project_layout_clean_creation_without_manifest(tmp_path: Path) -> None:
    created = project_layout.ensure_project_layout(tmp_path)

    for name in ("scans", "planches", "logs", "versions"):
        assert (tmp_path / name).is_dir()
    assert not (tmp_path / "frames").exists()
    assert not (tmp_path / "output-frames").exists()
    # `versions/` y est depuis la story 5.22 (`EPIC5-ARB-81`): le dossier des
    # artefacts versionnes du projet, d'abord `versions/calibration/` (les
    # profils de calibration par chaine). L'ajout est additif et idempotent.
    assert set(created) == {"scans", "planches", "logs", "versions"}


def test_ensure_project_layout_creates_per_rush_frame_dirs_from_manifest(tmp_path: Path) -> None:
    manifest = _v2_manifest_with_rush()

    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert (tmp_path / "extract-frames" / "rush-001_24").is_dir()
    assert (tmp_path / "frames-scannees" / "rush-001_24").is_dir()
    assert (tmp_path / "scans").is_dir()
    assert (tmp_path / "planches").is_dir()
    assert (tmp_path / "logs").is_dir()
    # inputs/ is no longer a mandatory hypothesis for the source rush (AC 2).
    assert not (tmp_path / "inputs").exists()


def test_ensure_project_layout_is_idempotent(tmp_path: Path) -> None:
    manifest = _v2_manifest_with_rush()

    project_layout.ensure_project_layout(tmp_path, manifest=manifest)
    marker = tmp_path / "extract-frames" / "rush-001_24" / "keep.txt"
    marker.write_text("already-extracted-frame-placeholder", encoding="utf-8")

    # Re-running must not raise and must not remove or alter existing content.
    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "already-extracted-frame-placeholder"


def test_ensure_project_layout_completes_partially_present_project(tmp_path: Path) -> None:
    (tmp_path / "scans").mkdir(parents=True)
    (tmp_path / "frames" / "rush-001_24").mkdir(parents=True)

    manifest = _v2_manifest_with_rush()
    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert (tmp_path / "scans").is_dir()
    assert (tmp_path / "planches").is_dir()
    assert (tmp_path / "logs").is_dir()
    # Le lot etait DEJA ecrit sous `frames/` : il y reste, rien n'est
    # renomme (`EPIC11-ARB-171`). Ses frames scannees, elles, n'existaient pas
    # -- elles prennent donc le nom neuf.
    assert (tmp_path / "frames" / "rush-001_24").is_dir()
    assert not (tmp_path / "extract-frames").exists()
    assert (tmp_path / "frames-scannees" / "rush-001_24").is_dir()
    assert not (tmp_path / "output-frames").exists()


def test_ensure_project_layout_ignores_rushes_without_fps_target(tmp_path: Path) -> None:
    manifest = _v2_manifest_with_rush()
    del manifest["video"]["fps_target"]

    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert not (tmp_path / "frames").exists()
    assert not (tmp_path / "output-frames").exists()
    assert not (tmp_path / "extract-frames").exists()
    assert not (tmp_path / "frames-scannees").exists()


# --- v2.1: une cadence cible par lot (decisions-2026-08-04.md) ---------------------


def _v2_1_manifest(*lots: tuple[str, str, float]) -> dict:
    """Manifest v2.1 a partir de triplets (lot_id, rush_id, fps_target)."""
    rush_ids = sorted({rush_id for _, rush_id, _ in lots})
    return {
        "schema_version": "2.1",
        "project_id": "example-001",
        "rushes": [{"rush_id": rush_id, "fps_source": 30.0} for rush_id in rush_ids],
        "lots": [
            {"lot_id": lot_id, "rush_id": rush_id, "state": "extraction", "fps_target": fps}
            for lot_id, rush_id, fps in lots
        ],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }


def test_ensure_project_layout_creates_one_dir_per_lot_not_per_rush(tmp_path: Path) -> None:
    manifest = _v2_1_manifest(
        ("rush-001_3", "rush-001", 3.0),
        ("rush-001_5", "rush-001", 5.0),
        ("rush-001_12p5", "rush-001", 12.5),
    )

    created = project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    for slug in ("rush-001_3", "rush-001_5", "rush-001_12p5"):
        assert (tmp_path / "extract-frames" / slug).is_dir()
        assert (tmp_path / "frames-scannees" / slug).is_dir()
        assert created[f"extract-frames:{slug}"] == tmp_path / "extract-frames" / slug
        assert created[f"frames-scannees:{slug}"] == tmp_path / "frames-scannees" / slug


def test_ensure_project_layout_handles_several_rushes(tmp_path: Path) -> None:
    manifest = _v2_1_manifest(
        ("rush-001_5", "rush-001", 5.0),
        ("rush-002_5", "rush-002", 5.0),
    )

    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert (tmp_path / "extract-frames" / "rush-001_5").is_dir()
    assert (tmp_path / "extract-frames" / "rush-002_5").is_dir()


def test_ensure_project_layout_still_reads_a_v2_0_project_level_rate(tmp_path: Path) -> None:
    """Repli transitionnel: un manifest v2.0 n'a pas de lots[].fps_target."""
    project_layout.ensure_project_layout(tmp_path, manifest=_v2_manifest_with_rush())

    assert (tmp_path / "extract-frames" / "rush-001_24").is_dir()


# ---------------------------------------------------------------------------
# Story 11.14, lot B1 -- le vocabulaire d'Egan sur les dossiers de frames
# (`EPIC11-ARB-214`, `EPIC11-ARB-220` pour les chaines, `EPIC11-ARB-171` pour
# la migration qu'elles n'imposent pas).
# ---------------------------------------------------------------------------

import ast
import pytest


def test_les_deux_dossiers_de_frames_portent_le_vocabulaire_d_egan() -> None:
    """Les chaines exactes de `Q1`, fermee le 2026-09-04.

    Un lot est un ensemble de frames extraites par `extract` -- d'ou
    `extract-frames/`, en symetrie avec la commande qui les produit. Un scan
    reproduit un lot scanne, fait de frames scannees -- d'ou
    `frames-scannees/`. Les deux valeurs sont ecrites ici parce que ce sont
    elles que la ligne de commande, la TUI et les manifestes citeront.
    """
    assert project_layout.EXTRACT_FRAMES_DIRNAME == "extract-frames"
    assert project_layout.SCAN_FRAMES_DIRNAME == "frames-scannees"


def test_les_deux_noms_d_avant_survivent_comme_constantes_RECONNUES() -> None:
    """Patron exact de `LEGACY_SOURCES_DIRNAME` (`EPIC11-ARB-171`).

    Le nom d'avant ne disparait pas : il est **reconnu**, pour qu'un projet
    deja sur le disque continue d'etre lu. Il n'est simplement plus jamais
    ecrit -- c'est ce que mesurent les deux frontieres negatives ci-dessous.
    """
    assert project_layout.LEGACY_FRAMES_DIRNAME == "frames"
    assert project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME == "output-frames"


def _modules_de_src() -> list[Path]:
    """Tous les modules Python de `src/`, tries -- lus, jamais recopies."""
    return sorted((REPO_ROOT / "src").rglob("*.py"))


def _compositions_de_chemin(module: Path, litteral: str) -> list[int]:
    """Les lignes de `module` qui composent un CHEMIN a partir de `litteral`.

    On ne compte pas toute occurrence de la chaine : `"frames"` est aussi une
    cle de manifeste et un mot d'affichage, et une frontiere qui les melerait
    ne mesurerait rien. Ce qui est interdit, c'est de **composer un
    emplacement** avec le nom d'avant -- donc un `Path(...) / "frames"`, un
    `x / "frames"` ou un `Path("frames")`. C'est le meme critere pour les deux
    noms retires, et il se lit a l'AST plutot que par un `grep` de texte.
    """
    arbre = ast.parse(module.read_text(encoding="utf-8"))

    def est_le_litteral(noeud: ast.AST) -> bool:
        return (isinstance(noeud, ast.Constant)
                and isinstance(noeud.value, str)
                and noeud.value == litteral)

    lignes: list[int] = []
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div)
                and (est_le_litteral(noeud.left) or est_le_litteral(noeud.right))):
            lignes.append(noeud.lineno)
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id in {"Path", "PurePosixPath", "PureWindowsPath"}):
            lignes.extend(
                noeud.lineno for argument in noeud.args if est_le_litteral(argument))
    return sorted(set(lignes))


#: Les exceptions sont NOMMEES dans le test, jamais reléguées en commentaire
#: (AC 2.3). `codec_profiles` compose `<dossier>/frames` comme prefixe du
#: fichier de liste `concat` de ffmpeg : c'est un nom de FICHIER de travail
#: dans un dossier quelconque, pas le dossier de frames d'un projet.
_EXCEPTIONS_NOMMEES = {
    ("codec_profiles.py", "frames"),
}


def _violations(litteral: str) -> list[str]:
    """Les modules de `src/` qui composent un chemin avec le nom retire."""
    trouves: list[str] = []
    for module in _modules_de_src():
        if module.name == "project_layout.py":
            # Le module qui RECONNAIT le nom est le seul autorise a le porter.
            continue
        if (module.name, litteral) in _EXCEPTIONS_NOMMEES:
            continue
        for ligne in _compositions_de_chemin(module, litteral):
            trouves.append(f"{module.relative_to(REPO_ROOT)}:{ligne}")
    return trouves


def test_frontiere_negative_aucun_chemin_ne_compose_output_frames() -> None:
    """AC 2.3, pour `output-frames` SEUL -- une frontiere par nom retire.

    Une frontiere globale sur les deux noms serait verte des que le premier
    est couvert : c'est exactement le defaut que la fiche interdit.
    """
    assert _violations("output-frames") == []


def test_frontiere_negative_aucun_chemin_ne_compose_frames() -> None:
    """AC 2.3, pour `frames` SEUL -- l'autre moitie de la frontiere.

    **Elle a ete ecrite ROUGE, en `xfail(strict=True)`**, parce que `cli.py`
    composait encore `project_dir / "frames"` sur le chemin POC et
    n'appartenait pas au lot B. Le lot C a ferme ce chemin le jour meme
    (`0e9b2ceb4`), la frontiere est passee en `XPASS(strict)` -- donc en ECHEC
    -- et le marqueur est parti. C'est exactement ce que `strict=True` sert a
    obtenir : un raccord qui se referme se SIGNALE, au lieu de rester vert en
    silence avec sa raison perimee.
    """
    assert _violations("frames") == []


def test_un_projet_NEUF_ne_porte_plus_aucun_des_deux_dossiers_d_avant(
    tmp_path: Path,
) -> None:
    """Frontiere negative de l'arborescence REELLEMENT creee (demande d'Egan).

    Un test positif sur `extract-frames/` ne verrait jamais **revenir**
    l'ancien dossier a cote du neuf : c'est le sens de la frontiere negative,
    et c'est la seule forme qui attrape une regression d'ecriture.
    """
    manifest = _v2_1_manifest(
        ("rush-001_3", "rush-001", 3.0),
        ("rush-002_12p5", "rush-002", 12.5),
    )

    project_layout.ensure_project_layout(tmp_path, manifest=manifest)

    assert not (tmp_path / "frames").exists()
    assert not (tmp_path / "output-frames").exists()
    assert (tmp_path / "extract-frames" / "rush-001_3").is_dir()
    assert (tmp_path / "frames-scannees" / "rush-002_12p5").is_dir()


@pytest.mark.parametrize("position", (0, 1, 2))
def test_volet_symetrique_un_lot_deja_ecrit_a_l_ancien_nom_reste_LU(
    tmp_path: Path, position: int
) -> None:
    """AC 2.4 -- l'ancien dossier est toujours trouve, a CHAQUE BORD.

    La fabrique produit **trois lots distinguables** (cadences differentes,
    donc slugs differents) et la cible est posee en tete, au milieu **et** en
    queue : un `find` fautif se demasque au milieu, un balayage tronque ne se
    demasque qu'aux bords (`CLAUDE.md`, point 4 de la regle des fabriques).
    """
    lots = (
        ("rush-001_3", "rush-001", 3.0),
        ("rush-001_5", "rush-001", 5.0),
        ("rush-001_12p5", "rush-001", 12.5),
    )
    slugs = [slug for slug, _, _ in lots]
    vise = slugs[position]

    # Le lot vise existe DEJA a l'ancien nom, les deux autres n'existent pas.
    (tmp_path / "frames" / vise).mkdir(parents=True)
    (tmp_path / "output-frames" / vise).mkdir(parents=True)

    project_layout.ensure_project_layout(tmp_path, manifest=_v2_1_manifest(*lots))

    # Le lot deja ecrit garde SON dossier : rien n'est renomme, et aucun
    # jumeau au nom neuf n'apparait a cote (ce serait scinder le lot en deux).
    assert (tmp_path / "frames" / vise).is_dir()
    assert not (tmp_path / "extract-frames" / vise).exists()
    assert (tmp_path / "output-frames" / vise).is_dir()
    assert not (tmp_path / "frames-scannees" / vise).exists()

    # Les deux autres, eux, sont ecrits au nom NEUF.
    for autre in (s for s in slugs if s != vise):
        assert (tmp_path / "extract-frames" / autre).is_dir()
        assert (tmp_path / "frames-scannees" / autre).is_dir()


@pytest.mark.parametrize("position", (0, 1, 2))
def test_les_resolveurs_rendent_le_dossier_d_avant_quand_il_existe(
    tmp_path: Path, position: int
) -> None:
    """Le volet symetrique au niveau du RESOLVEUR, et non du createur.

    Sans lui, la frontiere negative serait satisfaite par un code qui n'irait
    plus jamais lire ce qui est deja sur le disque.
    """
    cadences = (3.0, 5.0, 12.5)
    vise = cadences[position]
    slug = project_layout.rush_dir_slug("rush-001", vise)
    (tmp_path / "frames" / slug).mkdir(parents=True)
    (tmp_path / "output-frames" / slug).mkdir(parents=True)

    for cadence in cadences:
        attendu_extrait = (tmp_path / "frames" if cadence == vise
                           else tmp_path / "extract-frames")
        attendu_scanne = (tmp_path / "output-frames" if cadence == vise
                          else tmp_path / "frames-scannees")
        autre_slug = project_layout.rush_dir_slug("rush-001", cadence)
        assert project_layout.extract_frames_dir(tmp_path, "rush-001", cadence) \
            == attendu_extrait / autre_slug
        assert project_layout.scan_frames_dir(tmp_path, "rush-001", cadence) \
            == attendu_scanne / autre_slug


def test_les_racines_a_LIRE_portent_la_neuve_puis_l_ancienne_si_elle_existe(
    tmp_path: Path,
) -> None:
    """Ce que l'inventaire et la suppression parcourent (AC 2.4).

    L'ordre compte : la racine neuve d'abord, l'ancienne ensuite. Un lot
    present des deux cotes -- ce que rien n'ecrit mais qu'une main peut
    fabriquer -- est alors lu par son dossier NEUF, jamais deux fois.
    """
    assert project_layout.racines_de_frames_extraites(tmp_path) == (
        tmp_path / "extract-frames",
    )
    assert project_layout.racines_de_frames_scannees(tmp_path) == (
        tmp_path / "frames-scannees",
    )

    (tmp_path / "frames").mkdir()
    (tmp_path / "output-frames").mkdir()

    assert project_layout.racines_de_frames_extraites(tmp_path) == (
        tmp_path / "extract-frames", tmp_path / "frames",
    )
    assert project_layout.racines_de_frames_scannees(tmp_path) == (
        tmp_path / "frames-scannees", tmp_path / "output-frames",
    )


@pytest.mark.parametrize(
    "slug", ("", None, 2, ".", "..", "a/b", "../x", "/tmp/x", "C:/x", "x\\y"))
def test_la_garde_de_slug_couvre_AUSSI_les_frames_extraites(
    tmp_path: Path, slug: str
) -> None:
    """**Mutant `M12` reinjecte, et il a survecu a la premiere passe.**

    La garde de slug existait pour les seules frames scannees ; le lot B1 l'a
    factorisee (`_valider_le_slug`) et l'a donc etendue au pendant neuf
    `extract_frames_dir_from_slug`. Cette surface-la n'etait couverte par aucun
    banc :
    `test_scan_output_frames.py` tient la moitie scannee et rien ne tenait
    l'autre. Une garde qu'aucun test ne mesure est une garde qu'un
    raffinement retire sans bruit.

    Le motif est celui de la docstring du module : `Path("/proj") /
    "extract-frames" / "/tmp/x"` vaut `/tmp/x` -- pathlib abandonne la partie
    gauche devant un composant absolu --, et un slug portant `a/b/c` produit
    une arborescence ou l'`encode` ne cherchera jamais le lot.
    """
    with pytest.raises(ValueError):
        project_layout.extract_frames_dir_from_slug(tmp_path, slug)


def test_la_garde_de_slug_LAISSE_PASSER_un_slug_ordinaire(tmp_path: Path) -> None:
    """Volet symetrique : sans lui, la garde ci-dessus serait tenue par une
    fonction qui refuserait TOUT, et le refus n'aurait plus de sens."""
    assert project_layout.extract_frames_dir_from_slug(tmp_path, "rush-001_25") == (
        tmp_path / "extract-frames" / "rush-001_25")


# ---------------------------------------------------------------------------
# `EPIC11-ARB-225` -- `patches/` devient `planches/`
#
# Le renommage suit le patron d'`EPIC11-ARB-171` : on ECRIT le nom neuf, on
# RECONNAIT celui d'avant, on ne renomme rien de ce qui est deja sur un disque
# et on ne demande AUCUN geste a l'operateur (arbitrage d'Egan du 2026-09-06,
# choix A : « lire les deux, ecrire planches ; je peux m'arranger pour que cela
# n'arrive jamais »). Les trois bancs ci-dessous sont les pendants exacts de
# ceux du dossier des frames, plus haut dans ce fichier.
# ---------------------------------------------------------------------------


def test_le_dossier_des_planches_porte_le_vocabulaire_d_egan() -> None:
    """La chaine exacte d'`EPIC11-ARB-225`, verbatim d'Egan.

    « `patches/` doit devenir `planches/` ». La valeur est ecrite ici parce que
    c'est elle que la ligne de commande, la TUI, les manifestes et la
    documentation citeront -- et parce qu'un banc qui la lirait de la constante
    serait tautologique.
    """
    assert project_layout.PLANCHES_DIRNAME == "planches"


def test_le_nom_d_avant_survit_comme_constante_RECONNUE() -> None:
    """Patron exact de `LEGACY_FRAMES_DIRNAME` (`EPIC11-ARB-171`).

    Le nom d'avant ne disparait pas : il est **reconnu**, pour qu'un projet
    deja pose sur un disque continue d'etre lu sans qu'on demande une
    migration. Il n'est simplement plus jamais ecrit pour un objet NEUF --
    c'est ce que mesure la frontiere negative ci-dessous.
    """
    assert project_layout.LEGACY_PATCHES_DIRNAME == "patches"


def test_un_projet_NEUF_porte_planches_et_JAMAIS_le_dossier_d_avant(
    tmp_path: Path,
) -> None:
    """Frontiere negative de l'arborescence REELLEMENT creee.

    Un test positif sur `planches/` ne verrait jamais **revenir** `patches/` a
    cote du neuf : c'est le sens de la frontiere negative, et la seule forme
    qui attrape une regression d'ecriture.
    """
    cree = project_layout.ensure_project_layout(tmp_path)

    assert (tmp_path / "planches").is_dir()
    assert not (tmp_path / "patches").exists()
    assert "planches" in cree
    assert "patches" not in cree


def test_frontiere_negative_aucun_chemin_ne_compose_patches() -> None:
    """AC de frontiere, pour `patches` SEUL -- une frontiere par nom retire.

    **Elle porte sur la COMPOSITION DE CHEMIN a l'AST**, jamais sur un `grep`
    de texte, et c'est ce qui la rend possible ici : `patches` est un
    **homonyme**. Le mot designe aussi les **pastilles de couleur** de la mire
    -- `pdf_previz` en fait une cle de manifeste GELEE par `EPIC11-ARB-221`,
    `patch_presets` en fait des identifiants de registre (`patches-17-v4`),
    `color_calibration` en fait des valeurs serialisees
    (`FAILURE_PATCHES_NOT_FOUND`). Un `sed` sur l'arbre les corromprait en
    silence ; `_compositions_de_chemin` ne voit que `x / "patches"` et
    `Path("patches")`, donc aucun d'eux.

    L'exception est NOMMEE, jamais un seuil : `cli.py` compose encore le
    chemin de la planche du POC sous le nom d'avant, et il le fait par
    `LEGACY_PATCHES_DIRNAME` -- donc sans litteral, donc invisible a cette
    frontiere. Si un jour il repassait au litteral, elle rougirait.
    """
    assert _violations("patches") == []


def test_les_racines_de_planches_portent_la_neuve_puis_celle_d_avant(
    tmp_path: Path,
) -> None:
    """Pendant exact de `racines_de_frames_scannees` (voir plus haut).

    L'ordre porte la regle : la racine neuve d'abord, celle d'avant ensuite, et
    seulement si elle existe reellement -- sans quoi un parcours compterait un
    emplacement absent.
    """
    assert project_layout.racines_de_planches(tmp_path) == (
        tmp_path / "planches",
    )

    (tmp_path / "patches").mkdir()

    assert project_layout.racines_de_planches(tmp_path) == (
        tmp_path / "planches", tmp_path / "patches",
    )


# --- `chemin_de_planche` : le drapeau du dossier VARIE dans les deux sens ----
#
# « Une garde de repli fait VARIER le drapeau dont elle depend » (`CLAUDE.md`,
# 2026-09-06). Ici le drapeau est l'arborescence du projet, et il a **trois**
# etats, pas deux : projet ANCIEN (`patches/` seul), projet NEUF (`planches/`
# seul) et projet MIXTE. Un banc qui ne jouerait que le neuf mesurerait la
# moitie du produit et l'annoncerait vert.

@pytest.mark.parametrize("dossiers,attendu", (
    ((), "planches"),                      # rien : le neuf, par defaut
    (("planches",), "planches"),           # projet NEUF
    (("patches",), "patches"),             # projet ANCIEN : la ou le fichier est
    (("planches", "patches"), "patches"),  # MIXTE : la ou le fichier est
))
def test_chemin_de_planche_rend_le_dossier_ou_le_fichier_est_DEJA(
    tmp_path: Path, dossiers: tuple[str, ...], attendu: str
) -> None:
    """La resolution est par FICHIER, et c'est ce qui la rend juste.

    Dans les deux derniers cas le fichier vit sous le nom d'avant : c'est LUI
    qui est rendu, y compris quand `planches/` existe a cote (cas MIXTE, celui
    qu'`ensure_project_layout` fabrique des qu'il passe sur un projet ancien).
    Rendre le neuf la rendrait muet le refus d'ecrasement de `makepdf`
    (`EPIC11-ARB-89`) : l'operateur qui consent a un remplacement obtiendrait
    un DOUBLON, l'ancien restant en place.
    """
    for nom in dossiers:
        (tmp_path / nom).mkdir()
    if "patches" in dossiers:
        (tmp_path / "patches" / "demo_planches.pdf").write_bytes(b"%PDF-1.4")

    assert project_layout.chemin_de_planche(tmp_path, "demo_planches.pdf") == (
        tmp_path / attendu / "demo_planches.pdf")


def test_chemin_de_planche_rend_le_NEUF_pour_une_planche_qui_n_existe_PAS(
    tmp_path: Path,
) -> None:
    """Volet symetrique du precedent, et c'est lui qui porte « on ecrit le neuf ».

    Sans lui, le banc ci-dessus serait tenu par une fonction qui rendrait
    TOUJOURS le dossier d'avant des qu'il existe -- ce qui ecrirait
    eternellement sous le nom retire dans tout projet ancien.
    """
    (tmp_path / "patches").mkdir()
    (tmp_path / "patches" / "une_autre_planches.pdf").write_bytes(b"%PDF-1.4")

    assert project_layout.chemin_de_planche(tmp_path, "neuve_planches.pdf") == (
        tmp_path / "planches" / "neuve_planches.pdf")


@pytest.mark.parametrize("position", (0, 1, 2))
def test_une_planche_deja_ecrite_sous_le_nom_d_avant_est_retrouvee_a_CHAQUE_BORD(
    tmp_path: Path, position: int
) -> None:
    """Regle des fabriques, points 1, 2 et 4 : TROIS planches distinguables.

    La cible est posee en TETE, au milieu **et** en QUEUE. « La cible au milieu
    demasque un `find` fautif ; elle ne demasque pas un balayage tronque »
    (`CLAUDE.md`, 2026-09-03) -- et le mode de panne vise ici en est un :
    `project_inventory` balaie un listing de planches orphelines, et un
    balayage qui sauterait la derniere entree resterait vert sur une cible
    centrale.
    """
    noms = ("aaa_planches.pdf", "mmm_planches_v2.pdf", "zzz_planches_v3.pdf")
    (tmp_path / "patches").mkdir()
    (tmp_path / "planches").mkdir()
    for rang, nom in enumerate(noms):
        # Les deux non-cibles vivent sous le nom NEUF, la cible sous celui
        # d'avant : un remplissage uniforme ne distinguerait pas les deux.
        dossier = "patches" if rang == position else "planches"
        (tmp_path / dossier / nom).write_bytes(b"%PDF-1.4" + bytes([rang]))

    for rang, nom in enumerate(noms):
        attendu = "patches" if rang == position else "planches"
        assert project_layout.chemin_de_planche(tmp_path, nom) == (
            tmp_path / attendu / nom), (nom, position)


# --- `dossier_de_planches` : l'unique emplacement A MONTRER -----------------

@pytest.mark.parametrize("dossiers,peuples,attendu", (
    ((), (), "planches"),                                     # projet vierge
    (("planches",), ("planches",), "planches"),               # projet NEUF
    (("patches",), ("patches",), "patches"),                  # projet ANCIEN
    (("planches", "patches"), ("patches",), "patches"),       # MIXTE, neuf VIDE
    (("planches", "patches"), ("planches", "patches"),
     "planches"),                                             # MIXTE, les deux
    (("planches", "patches"), (), "planches"),                # MIXTE, tous vides
))
def test_dossier_de_planches_montre_celui_qui_PORTE_les_planches(
    tmp_path: Path, dossiers: tuple[str, ...], peuples: tuple[str, ...],
    attendu: str,
) -> None:
    """Le cas MIXTE au dossier NEUF VIDE est le seul qui compte vraiment.

    Il n'est pas theorique : `ensure_project_layout` cree desormais `planches/`
    a chaque passage, y compris sur un projet ancien dont toutes les planches
    vivent sous `patches/`. Rendre le neuf en aveugle enverrait l'operateur --
    « Ouvrir le dossier », ligne `Destination` d'un cartouche -- dans un
    dossier vide, en lui disant que ses fichiers y sont.

    Quand les DEUX portent des fichiers, c'est le NEUF qui gagne : meme ordre
    que `_racines`, une seule verite d'ordre dans le module.
    """
    for nom in dossiers:
        (tmp_path / nom).mkdir()
    for rang, nom in enumerate(peuples):
        # Des contenus DISTINGUABLES : un remplissage uniforme ne dirait pas
        # laquelle des deux racines a ete rendue.
        (tmp_path / nom / f"{nom}_planches.pdf").write_bytes(
            b"%PDF-1.4" + bytes([rang]))

    assert project_layout.dossier_de_planches(tmp_path) == tmp_path / attendu


def test_VERSIONS_DIRNAME_n_est_declare_qu_UNE_fois_dans_le_depot() -> None:
    """`EPIC11-ARB-225`, point 6 : le litteral double se ferme.

    `io/calibration_profile.py` portait sa propre chaine `"versions"` a cote de
    celle de ce module -- exactement le defaut que `project_layout` existe pour
    fermer, et que son commentaire d'`OUTPUTS_DIRNAME` enonce mot pour mot.
    Deux declarations, c'est un renommage qui n'en deplace qu'une et rien qui
    rougisse.

    La mesure est une **identite d'objet** et non une egalite de valeur : deux
    litteraux egaux passeraient une egalite, et c'est precisement l'etat
    d'avant.
    """
    from mixed_media_utility.io import calibration_profile

    assert calibration_profile.VERSIONS_DIRNAME is project_layout.VERSIONS_DIRNAME

    litteraux = [
        f"{module.relative_to(REPO_ROOT)}:{ligne}"
        for module in _modules_de_src()
        if module.name != "project_layout.py"
        for ligne in _compositions_de_chemin(module, "versions")
    ]
    assert litteraux == []
