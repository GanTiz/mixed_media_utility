"""Story 11.4e, **lot B** -- `mmu project add-rush`, l'enveloppe de la CLI.

Ce banc mesure l'AC 2 et elle seule. Le socle de coeur (AC 1) est mesure par
`tests/unit/test_declaration_de_rush.py`, l'ecran TUI (AC 3) par le lot C :
aucun des deux n'est dans le perimetre de ce fichier, et aucun des deux ne
partage un banc avec lui (`CLAUDE.md`, troisieme occurrence du 2026-08-30 --
un fichier de banc partage entre deux lots simultanes est un point de
contention au meme titre que `sprint-status.yaml`).

**Ce que le lot B ajoute au depot, en une phrase** : une surface de plus, et
jamais un appelant qui en fait plus. `EPIC11-ARB-131` a fait naitre un point
d'entree de coeur (`declaration_de_rush.declarer_un_rush`) ; il lui manquait la
commande qui l'appelle depuis un terminal. Tout ce que cette commande ajoute
appartient a un terminal et a rien d'autre : un sous-parseur, des phrases
imprimees, un code de sortie. Le jugement, lui, reste entier dans le coeur.

Les cinq mesures de ce banc, et la forme de chacune :

* `B1` -- **l'enveloppe est pure**. L'ensemble EXACT des options du
  sous-parseur (pas « `--fps` est absent » : l'ensemble entier, faute de quoi
  toute option supplementaire passerait), l'ensemble EXACT des mots-cles
  transmis au coeur, et deux frontieres negatives portant chacune leur volet
  symetrique -- l'enveloppe ne rejoue aucune regle de derivation, et ne porte
  aucun litteral entier ;
* `B2` -- **le code de sortie est LU de la table du coeur, par identite**. Le
  banc n'ecrit nulle part une seconde table : il **parcourt**
  `declaration_de_rush.CODES_DE_SORTIE` et exige de la commande le code que la
  table nomme. Une table recopiee ici mesurerait la recopie, pas la lecture ;
* `AC 2.3` -- le refus « rush deja declare » **dit pourquoi il refuse**, en une
  issue **unique**, et ne propose **aucun drapeau de contournement** : il n'y a
  rien a contourner (`EPIC11-ARB-147`). Ensembles exacts des deux cotes, et
  volet symetrique sur le detecteur de drapeaux ;
* `AC 2.4` -- sur un rush deja declare, **rien n'est modifie, point**. Mesure
  aux **inodes**, au **`st_mtime_ns`** et par un **temoin** depose dans le
  dossier projet -- jamais par un condensat, qu'une reecriture identique
  laisserait vert (`CLAUDE.md`, 2026-08-30). Volet symetrique obligatoire : une
  declaration qui REUSSIT change bel et bien le manifeste, sans quoi la mesure
  serait verte sur une commande qui ne fait rien du tout ;
* `B3` -- la **frontiere AST** du module de coeur neuf (AC 2.5) : ni `cli`, ni
  `print`, ni `sys.stderr`. Chaque detecteur est exerce sur `cli.py`, qui lui
  fait bel et bien les trois -- une frontiere negative sans volet symetrique
  est vraie par vacuite.

**Regle des fabriques** (`CLAUDE.md`, point 2 bis compris). Deux collections
sont parcourues par le code sous mesure, et les deux portent **trois** elements
**distinguables**, cible **au milieu** :

* `manifest["rushes"]`, parcourue par le coeur pour juger si le rush est deja
  declare : trois rushes de trois noms, trois dossiers et trois cadences, la
  cible en **deuxieme sur trois** ;
* les **issues** d'un refus, parcourues par la boucle d'impression de
  l'enveloppe : la table publiee n'en porte qu'une par motif aujourd'hui, donc
  le test qui mesure la boucle **substitue** un refus a trois issues
  distinguables, cible au milieu. Sans lui, un `issues[0]` ou un `break`
  resterait invisible tant que la table reste mono-element.

La position se verifie a chaque fois sur la liste que **le code parcourt**, et
non sur celle qu'une fabrique aurait ecrite ailleurs.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import shutil
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import cli, declaration_de_rush, extraction, video_metadata
from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME

#: Le rush reel du banc : 125 frames a 25 im/s, 1920x1080. Il n'est **pas** en
#: Git LFS (236 ko committes en clair), donc ce banc est mesurable dans un
#: conteneur neuf sans `git lfs pull`. Un banc de commande qui reclamerait une
#: fixture LFS serait inmesurable la ou il compte le plus.
RUSH_REEL = REPO_ROOT / "tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps.mp4"

#: Le rush qui diverge sur un critere d'**identite** -- 50 frames contre 125,
#: meme cadence et meme resolution. Depuis `EPIC11-ARB-230`, c'est le seul
#: montage qui fait encore jouer la separation silencieuse d'`EPIC11-ARB-9` :
#: la resolution n'entre pas dans l'identite d'un rush, et le dossier n'y entre
#: plus. 7 Ko, en git ordinaire comme sa soeur.
RUSH_REEL_AUTRE_DUREE = (
    REPO_ROOT / "tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps_50img.mp4"
)

requires_ffprobe = pytest.mark.skipif(
    shutil.which("ffprobe") is None,
    reason="binaire ffprobe absent du PATH",
)

#: Le motif d'un drapeau de ligne de commande. Il sert deux fois, et c'est ce
#: qui le rend digne de confiance : a mesurer qu'un refus n'en propose aucun
#: (AC 2.3), et a mesurer que l'aide du sous-parseur en propose bien -- le volet
#: symetrique, sans lequel le premier serait vrai par vacuite.
MOTIF_DE_DRAPEAU = re.compile(r"--[a-zA-Z][a-zA-Z0-9-]*")


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def manifeste_vierge(dossier: Path, project_id: str = "projet-a") -> Path:
    """Un `project.json` v2.1 valide, sans aucun rush ni aucun lot."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / MANIFEST_FILENAME
    chemin.write_text(
        json.dumps(
            {
                "schema_version": "2.1",
                "project_id": project_id,
                "created": "2026-09-01T00:00:00Z",
                "rushes": [],
                "lots": [],
                "artifacts": {},
                "color": {},
                "video": {},
                "reconstruction": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return chemin


#: Deux rushes de garde, **distinguables** du rush vise et l'un de l'autre sur
#: quatre axes -- nom, chemin complet, dossier parent, cadence. Un remplissage
#: uniforme rendrait invisible tout appariement positionnel inverse (defaut
#: `M33` de la story 5.6).
RUSH_AVANT = {
    "rush_id": "avant", "source_name": "avant.mov", "source_parent": "Z-CAM",
    "source_path": "/rushes/tournage-avril/Z-CAM/avant.mov",
    "fps_source": 24.0, "fps_source_exact": "24/1",
}
RUSH_APRES = {
    "rush_id": "apres", "source_name": "apres.mov", "source_parent": "B-CAM",
    "source_path": "/rushes/tournage-juin/B-CAM/apres.mov",
    "fps_source": 30.0, "fps_source_exact": "30/1",
}

#: L'index de la cible dans `manifest["rushes"]`, **la liste que le coeur
#: parcourt** pour juger « ce rush est-il deja declare ». Deuxieme sur trois :
#: ni premiere (un `find` fautif qui rend toujours le premier element se
#: demasque) ni derniere (une boucle qui casse au lieu de continuer se
#: demasque, point 2 bis du 2026-08-30).
INDEX_DE_LA_CIBLE = 1


def projet_ou_le_rush_est_DEJA_declare(dossier: Path, video: Path) -> Path:
    """Un projet dont `rushes[]` porte trois entrees, la cible **au milieu**.

    L'entree visee est celle que le coeur derivera de `video` : elle porte le
    `rush_id` derive du nom du fichier, sans quoi le refus mesure ne serait pas
    celui qu'on croit.
    """
    from mixed_media_utility.io.naming import normalize_identifier

    chemin = manifeste_vierge(dossier)
    cible = {
        "rush_id": normalize_identifier(video.stem, label="le nom du fichier source"),
        "source_name": video.name,
        "source_parent": video.parent.name,
        "source_path": str(video.resolve()),
        "fps_source": 25.0,
        "fps_source_exact": "25/1",
        # **La duree est posee depuis `EPIC11-ARB-230`** : le dossier ayant
        # cesse d'etre un critere d'identite, une entree qui n'en declare
        # aucune rend les trois criteres restants non verifiables. La fabrique
        # decrirait alors un manifeste ANCIEN sans le dire, et toutes les
        # mesures de separation deviendraient muettes. 125 frames, c'est
        # exactement ce que `RUSH_REEL` porte.
        "source_frame_count": 125,
        "source_frame_count_is_exact": True,
    }
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    rushes = [dict(RUSH_AVANT), dict(RUSH_APRES)]
    rushes.insert(INDEX_DE_LA_CIBLE, cible)
    contenu["rushes"] = rushes
    chemin.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    assert contenu["rushes"][INDEX_DE_LA_CIBLE] is rushes[INDEX_DE_LA_CIBLE]
    assert len(rushes) == 3 and INDEX_DE_LA_CIBLE == 1, (
        "la cible doit etre ni premiere ni derniere de la liste que le code parcourt"
    )
    return chemin


def copie_du_rush(dossier: Path, nom: str, source: Path = RUSH_REEL) -> Path:
    """Une copie nommee du rush reel, dans le dossier voulu."""
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom
    shutil.copyfile(source, cible)
    return cible


class Temoin:
    """Inodes, `st_mtime_ns` et un temoin depose -- **jamais un condensat**.

    Un condensat ne prouve rien ici : la fabrique est deterministe, donc une
    reecriture rend exactement les memes octets et le laisse vert a tort
    (`CLAUDE.md`, 2026-08-30). Ce qui se mesure est l'**identite du fichier**
    (l'inode change des qu'une ecriture atomique passe par un temporaire suivi
    d'un `os.replace`), sa **date de modification en nanosecondes** (une
    reecriture en place la change) et la survie d'un fichier tiers depose dans
    le dossier vise (un nettoyage du dossier l'emporte).
    """

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        stat = manifest_path.stat()
        self.inode = stat.st_ino
        self.mtime_ns = stat.st_mtime_ns
        self.temoin = manifest_path.parent / "temoin-de-la-mesure.txt"
        self.temoin.write_text("ne doit pas disparaitre", encoding="utf-8")
        self.temoin_inode = self.temoin.stat().st_ino
        self.contenu_du_dossier = {
            chemin.name for chemin in manifest_path.parent.iterdir()
        }
        # Le temoin est depose AVANT la mesure : sa mtime ne doit pas entrer en
        # collision de seconde avec celle du manifeste.
        time.sleep(0.01)

    def manifeste_intact(self) -> bool:
        stat = self.manifest_path.stat()
        return stat.st_ino == self.inode and stat.st_mtime_ns == self.mtime_ns

    def temoin_intact(self) -> bool:
        return self.temoin.is_file() and self.temoin.stat().st_ino == self.temoin_inode

    def dossier_inchange(self) -> bool:
        return {
            chemin.name for chemin in self.manifest_path.parent.iterdir()
        } == self.contenu_du_dossier


def lancer(projet: Path, video: Path, *options: str) -> int:
    """`mmu project add-rush`, appelee comme la ligne de commande l'appelle.

    `options` porte les drapeaux supplementaires -- `--force-distinct`
    (`EPIC11-ARB-232`) est le seul aujourd'hui. Elles s'ajoutent APRES les deux
    designations, comme un operateur les taperait.
    """
    return cli.main(
        ["project", "add-rush", "--project", str(projet), "--video", str(video),
         *options]
    )


def aide_du_sous_parseur(capsys) -> str:
    """La sortie de `project add-rush --help`, telle qu'argparse la rend."""
    with pytest.raises(SystemExit) as sortie:
        cli.main(["project", "add-rush", "--help"])
    assert sortie.value.code == 0
    return capsys.readouterr().out


def options_du_sous_parseur(capsys) -> set[str]:
    return set(MOTIF_DE_DRAPEAU.findall(aide_du_sous_parseur(capsys)))


def rushes_du_manifeste(manifest_path: Path) -> list[dict]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))["rushes"]


# --- outillage AST, partage par B1 et B3 -----------------------------------


def source_du_module(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def noms_appeles(arbre: ast.AST) -> set[str]:
    """L'ensemble des noms de fonctions appelees dans l'arbre, `f` et `a.f`."""
    appels: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        if isinstance(cible, ast.Name):
            appels.add(cible.id)
        elif isinstance(cible, ast.Attribute):
            appels.add(cible.attr)
    return appels


def modules_importes(arbre: ast.AST) -> set[str]:
    importes: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                importes.add(alias.name)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ""
            importes.add(base)
            for alias in noeud.names:
                importes.add(f"{base}.{alias.name}" if base else alias.name)
    return importes


def arbre_de_la_fonction(fonction) -> ast.AST:
    """L'arbre syntaxique du corps d'une fonction, isole du reste du module."""
    return ast.parse(textwrap.dedent(inspect.getsource(fonction)))


def entiers_litteraux(arbre: ast.AST) -> set[int]:
    """Les litteraux entiers de l'arbre, hors booleens (`True` est un `int`)."""
    return {
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, int)
        and not isinstance(noeud.value, bool)
    }


# ---------------------------------------------------------------------------
# B1 -- le sous-parseur sous `project`, enveloppe pure (AC 2.1)
# ---------------------------------------------------------------------------


def test_B1_la_commande_est_une_sous_commande_de_project(tmp_path, capsys):
    """AC 2.1 : elle vit sous `project`, et le parseur la connait.

    `cli.py:4492-4495` dit deja le motif du porte-nom : « `project` est le
    porte-nom naturel des gestes de maintenance d'arborescence, et d'autres
    suivront ». Celui-ci est l'un d'eux.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    appels: list[dict] = []

    def compter(**kwargs):
        appels.append(kwargs)
        raise declaration_de_rush.RefusDeDeclaration(
            "arret de la mesure",
            motif=declaration_de_rush.MOTIF_FICHIER_INTROUVABLE,
            issues=declaration_de_rush.ISSUES_PAR_MOTIF[
                declaration_de_rush.MOTIF_FICHIER_INTROUVABLE
            ],
        )

    original = declaration_de_rush.declarer_un_rush
    declaration_de_rush.declarer_un_rush = compter
    try:
        lancer(projet, video)
    finally:
        declaration_de_rush.declarer_un_rush = original

    assert len(appels) == 1, "la sous-commande n'a pas atteint le coeur"


def test_B1_l_ensemble_des_options_est_EXACTEMENT_project_et_video(capsys):
    """AC 2.1 : `--project` et le fichier video, **aucune option de cadence**.

    L'assertion porte sur l'ensemble ENTIER, jamais sur l'absence de `--fps` :
    « une assertion positive laisse passer toute divergence supplementaire »
    (`CLAUDE.md`, 2026-08-30). Une option de cadence ajoutee demain ferait
    rougir ; une option de nom aussi (`EPIC11-ARB-146` : le `rush_id` est
    derive, jamais choisi).

    **`--force-distinct` est entree le 2026-09-05** (`EPIC11-ARB-232`, formule
    par Egan). Ce test disait « --project et --video, et deux exactement » sur
    la foi du refus sec d'`EPIC11-ARB-147` ; `EPIC11-ARB-231` a donne trois
    issues a ce refus, et la seconde -- « c'est un autre rush, le declarer
    separement » -- n'a pas d'ecran en ligne de commande. Ce n'est pas un
    drapeau de contournement d'ecrasement : il n'ecrase rien, il declare une
    SECONDE entree, et c'est pour cela qu'`--overwrite` a ete ecarte nommement.
    """
    assert options_du_sous_parseur(capsys) == {
        "--help", "--project", "--video", "--force-distinct"}


#: Ce que CHACUNE des deux aides de `project add-rush` doit dire, et ce qu'elle
#: ne doit plus dire (`EPIC11-ARB-233`). Deux entrees et non une : la reecriture
#: a porte sur les deux aides, et une fabrique a un seul element rendrait
#: invisible une reecriture qui n'aurait touche que l'une des deux.
#:
#: Les interdits sont les mots de la redaction d'AVANT, pris verbatim -- « un
#: suffixe derive du dossier parent » sur `--video`, « leve par le suffixe de
#: son dossier parent » sur `--force-distinct`. Ce ne sont donc pas des
#: interdits inventes : ils sont ce que le mutant de `F11` reinjecte.
AIDES_ATTENDUES = {
    "--video": {
        "exiges": ("suffixe de RANG", "prise01-2", "EPIC11-ARB-233",
                   "EPIC11-ARB-9"),
        "interdits": ("dossier parent", "suffixe derive"),
    },
    "--force-distinct": {
        "exiges": ("leve par un rang", "prise01-2", "prise01-3",
                   "EPIC11-ARB-233"),
        "interdits": ("dossier parent", "suffixe de son dossier"),
    },
}


def bloc_d_aide(capsys, option: str) -> str:
    """L'aide d'UNE option, isolee du reste de `add-rush --help`.

    La ligne d'usage est jetee -- elle repete les noms d'options sans leur
    prose --, puis le corps est coupe sur les drapeaux. Les retours a la ligne
    d'argparse sont ecrases : une phrase repliee sur deux lignes reste une
    phrase, et un test qui chercherait « dossier parent » sans cela serait vert
    par accident de mise en page.
    """
    corps = " ".join(aide_du_sous_parseur(capsys).split())
    corps = corps.split("options:", 1)[1]
    if option == "--video":
        bloc = corps.split("--video VIDEO", 1)[1].split("--force-distinct", 1)[0]
    else:
        bloc = corps.split("--force-distinct", 1)[1]
    # Garde d'inventaire : une decoupe qui rendrait le vide ferait passer tous
    # les interdits ci-dessous sans rien mesurer.
    assert len(bloc.split()) > 20, (option, bloc)
    return bloc


@pytest.mark.parametrize("option", sorted(AIDES_ATTENDUES))
def test_AC21_l_aide_DIT_que_le_suffixe_est_un_RANG_et_plus_un_DOSSIER(
    capsys, option
):
    """AC 2.1 : ce que l'aide DIT est tenu, pas seulement ce qu'elle PARSE.

    Finding `F11` de la revue 11.4e. `EPIC11-ARB-233` a reecrit les deux aides
    de `project add-rush` -- le suffixe d'homonymie est un **rang**, plus un
    dossier parent -- et **rien** ne le tenait : remises verbatim a leur
    redaction d'avant, **157 puis 67 tests restaient verts**, la frontiere
    `test_conformite_sorties_nommees` comprise, qui ne mesure que le PARSING.
    Le groupe `cli.py` du diff (+14 lignes de prose d'aide) est aussi le seul
    qu'aucune des trois couches n'a mute : le trou et son constat coincident.

    **Ce test ne touche pas au texte de l'AC 2.1**, qui reste ce qu'il est ;
    il mesure l'ecart que le registre nomme, du cote du produit.

    Les deux volets, et il faut les deux : un volet POSITIF seul laisserait
    passer une aide qui dirait les deux choses a la fois -- le rang ajoute,
    le dossier parent jamais retire --, ce qui est exactement l'etat qu'un
    correctif incomplet produit.
    """
    bloc = bloc_d_aide(capsys, option)
    attendu = AIDES_ATTENDUES[option]
    for exige in attendu["exiges"]:
        assert exige in bloc, (option, exige, bloc)
    for interdit in attendu["interdits"]:
        assert interdit not in bloc, (option, interdit, bloc)


def test_AC21_volet_symetrique_les_interdits_sont_CHERCHABLES_dans_ce_bloc(
    capsys,
):
    """Sans lui, le volet negatif ci-dessus pourrait etre inerte.

    Le precedent du depot : « un test ecrit expres pour fermer un finding
    portait une assertion inerte -- le chemin qu'il affirmait nommer portait
    deja l'identifiant ». Ici le risque symetrique est une decoupe qui viserait
    le mauvais bloc : `dossier parent` serait absent de n'importe quoi.

    Ce test verifie donc que le bloc decoupe est bien l'aide de l'option, en y
    cherchant un mot qui n'appartient qu'a elle, et que le mot `dossier` -- le
    radical des interdits -- est bien un mot que ces blocs SAVENT porter : il
    est present dans l'aide de `--project`, decoupee par le meme outil.
    """
    corps = " ".join(aide_du_sous_parseur(capsys).split())
    corps = corps.split("options:", 1)[1]
    bloc_projet = corps.split("--project PROJECT", 1)[1].split("--video", 1)[0]
    assert "Dossier projet existant" in bloc_projet
    assert "dossier" in bloc_projet.lower()

    assert "Fichier video a declarer" in bloc_d_aide(capsys, "--video")
    assert "Declarer un SECOND rush" in bloc_d_aide(capsys, "--force-distinct")


def test_B1_l_ensemble_des_mots_cles_transmis_au_coeur_est_EXACT(tmp_path):
    """AC 2.2 : l'enveloppe passe ce que l'operateur a designe, et rien de plus.

    Frontiere d'ensemble EXACT, du meme geste que celle du lot H de la 11.6 :
    le jour ou un parametre de nom apparaitrait dans l'appel -- ce qu'interdit
    `EPIC11-ARB-146` --, ce test rougirait.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    vus: list[dict] = []

    def espion(**kwargs):
        vus.append(kwargs)
        raise declaration_de_rush.RefusDeDeclaration(
            "arret de la mesure",
            motif=declaration_de_rush.MOTIF_FICHIER_INTROUVABLE,
            issues=("issue de la mesure",),
        )

    original = declaration_de_rush.declarer_un_rush
    declaration_de_rush.declarer_un_rush = espion
    try:
        lancer(projet, video)
    finally:
        declaration_de_rush.declarer_un_rush = original

    assert set(vus[0]) == {
        "project_dir", "video_path", "logger", "force_distinct"}
    # L'enveloppe TRANSMET le drapeau, elle ne l'interprete pas : la valeur
    # passee est celle du namespace, sans defaut redige une seconde fois.
    assert vus[0]["force_distinct"] is False
    assert Path(vus[0]["project_dir"]) == projet
    assert Path(vus[0]["video_path"]) == video


def test_B1_l_enveloppe_ne_REJOUE_aucune_regle_du_coeur():
    """Frontiere negative : aucune derivation, aucune lecture de manifeste ici.

    « Enveloppe pure » se mesure : la commande ne doit ni deriver un `rush_id`,
    ni lever une homonymie, ni qualifier une source, ni persister une entree.
    Chacun de ces gestes existe **une seule fois**, dans le coeur, et une
    seconde redaction divergerait sans que rien ne le dise (`EPIC11-ARB-146`).
    """
    # Les gestes que le COEUR fait lui-meme, et l'enveloppe jamais.
    interdits_du_coeur = {
        "normalize_identifier",
        "rush_identity_conflict",
        "disambiguated_rush_id",
        "qualify_source",
        "probe_media",
        "persist_rush_declaration",
    }
    # Et le geste que le coeur delegue lui-meme a `io/` -- l'enveloppe n'a pas
    # davantage le droit de le rejouer, et son volet symetrique se prend donc
    # la ou il vit reellement.
    interdits_de_io = {"build_rush_declaration_manifest"}
    interdits = interdits_du_coeur | interdits_de_io

    appels_de_l_enveloppe = noms_appeles(
        arbre_de_la_fonction(cli.project_add_rush_command)
    )
    assert not (interdits & appels_de_l_enveloppe), (
        f"l'enveloppe rejoue une regle du coeur: "
        f"{sorted(interdits & appels_de_l_enveloppe)}"
    )

    # Volet symetrique : le meme detecteur, applique aux modules qui ont le
    # DROIT de faire ces gestes, les trouve tous. Sans lui, la frontiere
    # ci-dessus serait verte sur un detecteur casse -- ou sur un nom mal
    # orthographie, ce qui revient au meme.
    appels_du_coeur = noms_appeles(ast.parse(source_du_module(declaration_de_rush)))
    assert interdits_du_coeur <= appels_du_coeur, (
        "le detecteur ne voit pas ces appels la ou ils sont: "
        f"{sorted(interdits_du_coeur - appels_du_coeur)}"
    )
    appels_de_io = noms_appeles(ast.parse(source_du_module(extraction_manifest)))
    assert interdits_de_io <= appels_de_io, (
        "le detecteur ne voit pas ces appels la ou ils sont: "
        f"{sorted(interdits_de_io - appels_de_io)}"
    )


def test_B1_l_enveloppe_ne_porte_AUCUN_litteral_entier():
    """Frontiere negative de B2, vue depuis le code : aucun code ecrit ici.

    Un code de sortie **lu** de la table du coeur ne laisse aucun entier dans
    le corps de l'enveloppe. C'est la forme mesurable de « jamais redige une
    seconde fois » : un `return 1` ajoute demain ferait rougir, la ou une
    relecture ne l'aurait pas vu.
    """
    assert entiers_litteraux(arbre_de_la_fonction(cli.project_add_rush_command)) == set()

    # Volet symetrique : le meme detecteur, sur une commande qui ecrit bel et
    # bien ses codes en clair (`project_remove_command` rend `1` et `130`).
    # Sans lui, un detecteur qui ne trouverait jamais rien serait vert.
    assert entiers_litteraux(arbre_de_la_fonction(cli.project_remove_command)), (
        "le detecteur d'entiers litteraux ne trouve rien la ou il y en a"
    )


@pytest.mark.parametrize("manquante", ["--project", "--video"])
def test_B1_les_deux_options_sont_REQUISES(tmp_path, manquante):
    """Une option omise est refusee par argparse, jamais acceptee a `None`.

    Sans cette mesure, `required=False` pose par megarde sur l'une des deux
    laisserait `mmu project add-rush --project P` partir avec `args.video` a
    `None`, puis mourir sur un `Path(None)` -- une trace Python devant
    l'operateur, la ou argparse rend un refus nomme et le code `2`.

    Volet symetrique : l'invocation **complete**, elle, atteint bien le coeur.
    C'est le test `test_B1_la_commande_est_une_sous_commande_de_project`
    ci-dessus, sans lequel ce refus-ci serait vrai sur un parseur qui refuse
    tout.
    """
    arguments = {
        "--project": str(tmp_path / "projet"),
        "--video": str(tmp_path / "cible.mp4"),
    }
    del arguments[manquante]
    with pytest.raises(SystemExit) as sortie:
        cli.main(
            ["project", "add-rush", *[m for cle, v in arguments.items() for m in (cle, v)]]
        )
    assert sortie.value.code == 2


@pytest.mark.parametrize(
    "abregee, entiere",
    [("--pro", "--project"), ("--vid", "--video")],
)
def test_B1_aucune_abreviation_d_option_n_est_acceptee(tmp_path, abregee, entiere):
    """Grammaire coherente avec son frere `remove` (`EPIC11-ARB-220`, `-224`).

    `argparse` accepte par defaut toute abreviation non ambigue, et un
    sous-parseur **n'herite pas** du drapeau de son parent -- c'est ce que le
    commentaire de `project remove` dit deja, en toutes lettres. Mesure du
    2026-09-05, avant correction : `mmu project add-rush --pro P --v V` etait
    ACCEPTE tandis que `mmu project remove --pro P` etait refuse. Deux
    sous-commandes du meme parseur `project`, deux grammaires -- exactement
    l'incoherence qu'`EPIC11-ARB-224` ferme ailleurs.

    Le defaut ne mord pas aujourd'hui, et c'est ce qui le rend dangereux : le
    motif d'`EPIC11-ARB-220` est qu'une abreviation acceptee reste **invisible**
    jusqu'au jour ou un nom neuf prolonge un nom retire, et ce jour-la le refus
    bruyant sur lequel tout le fichier compte a deja cesse d'exister.

    **Les deux options sont parametrees, tete ET queue** (`CLAUDE.md`, point 4
    des fabriques) : l'ensemble n'en porte que deux, donc `--pro` est la cible
    de tete et `--vid` celle de queue. Une seule des deux mesuree laisserait
    l'autre ouverte -- c'est la lacune exacte que le mutant `M09` avait ouverte
    sur `required=True`, dans ce meme sous-parseur.

    Volet symetrique, dans le meme test : le nom **entier** passe le parseur et
    atteint le coeur, qui refuse pour un motif metier (`SystemExit` ne monte
    pas, un code de sortie est rendu). Sans lui, ce refus-ci serait vrai sur un
    parseur qui refuse tout, ce que le mutant `M09` a deja montre possible.
    """
    arguments = {
        "--project": str(tmp_path / "projet-absent"),
        "--video": str(tmp_path / "cible-absente.mp4"),
    }

    abrege = [
        mot
        for cle, valeur in arguments.items()
        for mot in ((abregee if cle == entiere else cle), valeur)
    ]
    with pytest.raises(SystemExit) as sortie:
        cli.main(["project", "add-rush", *abrege])
    assert sortie.value.code == 2, (
        f"l'abreviation {abregee} a ete acceptee: `project add-rush` n'a pas la "
        f"grammaire de son frere `project remove`"
    )

    entier = [mot for cle, valeur in arguments.items() for mot in (cle, valeur)]
    code = cli.main(["project", "add-rush", *entier])
    motif = declaration_de_rush.MOTIF_PROJET_SANS_MANIFESTE
    attendu = declaration_de_rush.code_de_sortie(
        declaration_de_rush.RefusDeDeclaration(
            "sonde du volet symetrique",
            motif=motif,
            issues=declaration_de_rush.ISSUES_PAR_MOTIF[motif],
        )
    )
    assert code == attendu, (
        "le nom entier ne franchit plus le parseur: le refus ci-dessus serait "
        "vrai sur une commande qui refuse tout"
    )


# ---------------------------------------------------------------------------
# B2 -- le code de sortie, LU de la table du coeur (AC 2.2)
# ---------------------------------------------------------------------------


def _instance(classe: type[BaseException]) -> BaseException:
    """Une instance de chaque classe de la table du coeur.

    `RefusDeDeclaration` exige `motif` et `issues` : ils sont pris dans la
    table publiee, jamais inventes.
    """
    if classe is declaration_de_rush.RefusDeDeclaration:
        motif = declaration_de_rush.MOTIF_SOURCE_NON_QUALIFIEE
        return declaration_de_rush.RefusDeDeclaration(
            "panne fabriquee pour la mesure",
            motif=motif,
            issues=declaration_de_rush.ISSUES_PAR_MOTIF[motif],
        )
    return classe("panne fabriquee pour la mesure")


@pytest.mark.parametrize(
    "classe, attendu",
    declaration_de_rush.CODES_DE_SORTIE,
    ids=[classe.__name__ for classe, _ in declaration_de_rush.CODES_DE_SORTIE],
)
def test_B2_la_commande_rend_le_code_que_la_table_du_coeur_nomme(
    monkeypatch, tmp_path, classe, attendu
):
    """AC 2.2, **par identite** : la table parcourue EST celle du coeur.

    Ce test ne recopie aucune correspondance. Il **parcourt**
    `declaration_de_rush.CODES_DE_SORTIE` : une entree ajoutee au coeur est
    mesuree ici sans qu'une ligne bouge, et une entree dont la CLI rendrait un
    autre code rougit. Une table recopiee dans ce banc mesurerait la recopie.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    def refuser(**_kwargs):
        raise _instance(classe)

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    assert lancer(projet, video) == attendu


def test_B2_ce_que_la_table_ne_nomme_PAS_remonte(monkeypatch, tmp_path):
    """Un bug de programmation ne sort pas deguise en refus metier.

    C'est la meme garde qu'`extract` (`EPIC11-ARB-75`) : `except Exception`
    sans elle transformerait n'importe quelle panne en « Erreur: ... » avec le
    code d'un refus, et la panne disparaitrait des journaux.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    class PanneInconnue(Exception):
        pass

    def refuser(**_kwargs):
        raise PanneInconnue("bug de programmation")

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    assert declaration_de_rush.code_de_sortie(PanneInconnue("bug")) is None
    with pytest.raises(PanneInconnue):
        lancer(projet, video)


def test_B2_un_sous_type_recoit_le_code_de_SON_entree_et_pas_de_la_premiere(
    monkeypatch, tmp_path
):
    """La recherche rend la premiere entree qui correspond, pas la premiere ligne.

    La cible est un sous-type de `FfprobeNotFoundError`, qui est la **cinquieme**
    entree et le **seul** code `2` de la table : une recherche qui rendrait
    toujours la premiere ligne rendrait `1`, et le prerequis externe manquant
    deviendrait indiscernable d'un refus metier.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    class BinaireIntrouvable(video_metadata.FfprobeNotFoundError):
        pass

    def refuser(**_kwargs):
        raise BinaireIntrouvable("ffprobe absent du PATH")

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    assert lancer(projet, video) == declaration_de_rush.CODE_PREREQUIS_ABSENT
    assert declaration_de_rush.CODE_PREREQUIS_ABSENT != declaration_de_rush.CODE_ERREUR


def test_B2_l_interruption_clavier_n_a_ni_prefixe_erreur_ni_trace(
    monkeypatch, tmp_path, capsys
):
    """`Ctrl+C` : le code d'interruption de la chaine, et un message propre.

    `KeyboardInterrupt` n'est **pas** dans la table du coeur, et c'est
    delibere -- comme dans `scan_write.CODES_DE_SORTIE` : la garde `AR2` reste
    chez l'appelant, qui porte son propre message. Le code, lui, reste celui de
    la chaine (`extraction.CODE_INTERRUPTION`), **lu** et non reecrit.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    def interrompre(**_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", interrompre)
    assert lancer(projet, video) == extraction.CODE_INTERRUPTION

    sortie = capsys.readouterr()
    assert "Interruption clavier" in sortie.out
    assert "Erreur:" not in sortie.err
    assert "Traceback" not in sortie.err


def test_B2_le_motif_du_coeur_est_imprime_VERBATIM(monkeypatch, tmp_path, capsys):
    """AC 2.2 : `str(exc)`, prefixe et jamais recompose.

    Le texte attendu n'est pas recopie dans ce banc : il est **celui de
    l'exception levee**, ce qui mesure la transmission plutot qu'une phrase.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    refus = _instance(declaration_de_rush.RefusDeDeclaration)

    def refuser(**_kwargs):
        raise refus

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    lancer(projet, video)
    assert f"Erreur: {refus}" in capsys.readouterr().err


def test_B2_le_filet_OSError_reformule_l_acces_disque(monkeypatch, tmp_path, capsys):
    """La seule entree dont le message n'est pas verbatim, et c'est mesure.

    Meme geste qu'`extract_command` depuis la revue du 2026-08-05 : disque
    plein ou projet en lecture seule sont des pannes ordinaires, et « No space
    left on device » seul n'est pas actionnable. La distinguer est aussi ce qui
    rend l'ordre de la table observable -- l'appelant a besoin de savoir
    **quelle** entree a repondu, pas seulement de son code.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    def refuser(**_kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    assert lancer(projet, video) == declaration_de_rush.CODE_ERREUR
    erreur = capsys.readouterr().err
    assert "No space left on device" in erreur
    assert "espace disponible" in erreur


@requires_ffprobe
def test_B2_le_succes_rend_le_code_du_coeur_et_declare_le_rush(tmp_path, capsys):
    """Le chemin nominal, de bout en bout, sur un rush REEL.

    Il n'est pas la que pour le code `0` : c'est lui qui garantit que les
    frontieres negatives de ce banc ne sont pas vertes sur une commande qui ne
    ferait rien.
    """
    projet = tmp_path / "projet"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    assert lancer(projet, video) == declaration_de_rush.CODE_SUCCES

    rushes = rushes_du_manifeste(manifeste)
    assert [rush["rush_id"] for rush in rushes] == ["cible"]
    assert rushes[0]["source_name"] == "cible.mp4"
    assert json.loads(manifeste.read_text(encoding="utf-8"))["lots"] == []

    compte_rendu = capsys.readouterr().out
    assert "cible.mp4" in compte_rendu
    # **Une** phrase, et une seule : c'est le volet symetrique du regime
    # d'homonymie ci-dessous, ou la seconde phrase apparait. Sans ce cardinal
    # des deux cotes, une seconde phrase toujours imprimee -- ou jamais --
    # serait indiscernable.
    assert len([ligne for ligne in compte_rendu.splitlines() if ligne.strip()]) == 1


# ---------------------------------------------------------------------------
# AC 2.3 -- le refus sec : une issue unique, aucun drapeau de contournement
# ---------------------------------------------------------------------------


@requires_ffprobe
def test_AC23_le_refus_DIT_POURQUOI_il_refuse(tmp_path, capsys):
    """`EPIC11-ARB-147` : le refus nomme son motif, pas un code.

    Le texte attendu est celui que le **coeur** produit dans les memes
    conditions : le banc l'obtient en appelant le coeur, puis exige que la
    commande l'ait imprime. Recopier la phrase ici mesurerait la recopie.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")
    projet_ou_le_rush_est_DEJA_declare(projet, video)

    import logging

    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as leve:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=video,
            logger=logging.getLogger("mesure-du-banc-lot-b"),
        )
    assert leve.value.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE

    assert lancer(projet, video) == declaration_de_rush.CODE_ERREUR
    assert f"Erreur: {leve.value}" in capsys.readouterr().err


@requires_ffprobe
def test_AC23_l_ensemble_des_issues_imprimees_est_EXACTEMENT_celui_du_coeur(
    tmp_path, capsys
):
    """**TROIS** issues, et ce sont celles de la table publiee.

    Ensemble EXACT dans les deux sens : ni une issue de moins, ni une de plus.

    **Renverse le 2026-09-05.** Ce test exigeait `len(attendues) == 1` sur la
    foi d'`EPIC11-ARB-147` ; `EPIC11-ARB-231` le supersede sur ce point precis
    (Egan, verbatim : « Une 3e sortie sur l'ecran »). Le cardinal se lit de la
    table du coeur et jamais d'un litteral ecrit ici -- c'est ce qui a permis
    a l'arbitrage de traverser sans une seconde redaction.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")
    projet_ou_le_rush_est_DEJA_declare(projet, video)

    lancer(projet, video)
    lignes = capsys.readouterr().err.splitlines()
    imprimees = {
        ligne.split("Issue:", 1)[1].strip()
        for ligne in lignes
        if ligne.strip().startswith("Issue:")
    }
    attendues = set(
        declaration_de_rush.ISSUES_PAR_MOTIF[
            declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
        ]
    )
    assert imprimees == attendues
    assert len(attendues) == 3, (
        "EPIC11-ARB-231: relinker, declarer separement, annuler")

    # **Le CONTENU des issues, et pas seulement leur cardinal** -- mutant `M20`
    # mesure : vider la citation de la table (`--force-distinct` remplace par
    # une paraphrase) laissait ce banc VERT, parce que les deux cotes de
    # l'egalite lisent la meme table et parce que le MESSAGE, lui, cite encore
    # le drapeau. Un operateur lit les deux ; une frontiere qui n'en mesure
    # qu'un laisse l'autre se vider en silence.
    #
    # `EPIC11-ARB-232` engage la citation dans le refus, et la cloture
    # d'`EPIC11-ARB-224` exige qu'elle soit TAPABLE : c'est la forme entre
    # accents graves qui est mesuree, jamais le mot seul.
    citantes = [issue for issue in imprimees
                if "`mmu project add-rush" in issue
                and "--force-distinct`" in issue]
    assert len(citantes) == 1, imprimees
    relinkantes = [issue for issue in imprimees if "`mmu relink" in issue]
    assert len(relinkantes) == 1, imprimees


@requires_ffprobe
def test_AC23_le_refus_ne_propose_AUCUN_drapeau_DESTRUCTEUR(tmp_path, capsys):
    """**Renverse le 2026-09-05 par `EPIC11-ARB-232`.**

    Ce test exigeait `MOTIF_DE_DRAPEAU.findall(erreur) == []` -- aucun drapeau
    du tout, refus sec. L'arbitrage exige desormais l'inverse :
    `--force-distinct` doit etre **cite dans le message de refus**. Ce qui
    reste, et qui est le critere reel d'`EPIC11-ARB-89`, c'est qu'aucun
    drapeau **destructeur** n'y figure -- `--overwrite` a ete ecarte nommement
    par l'arbitrage, « il dit ecraser et ferait ici l'inverse ».

    L'ensemble des drapeaux cites est mesure **par identite**, jamais par
    absence : un drapeau de plus, quel qu'il soit, fait rougir.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")
    projet_ou_le_rush_est_DEJA_declare(projet, video)

    lancer(projet, video)
    erreur = capsys.readouterr().err
    assert set(MOTIF_DE_DRAPEAU.findall(erreur)) == {
        "--project", "--rush", "--video", "--force-distinct"}, erreur
    assert not (
        set(MOTIF_DE_DRAPEAU.findall(erreur))
        & {"--overwrite", "--nouvelle-version", "--ecrasement-conscient",
           "--force"}
    ), erreur

    assert "--project" in options_du_sous_parseur(capsys)


def test_AC23_la_boucle_d_issues_les_imprime_TOUTES_et_dans_l_ordre(
    monkeypatch, tmp_path, capsys
):
    """Fabrique a **trois** issues distinguables, cible **au milieu**.

    La table publiee n'en porte qu'une par motif aujourd'hui : un `issues[0]`,
    un `issues[-1]` ou un `break` y serait parfaitement invisible. La liste que
    le code parcourt est celle du refus, donc c'est elle qui porte trois
    elements -- ni premiere ni derniere position pour la cible (point 2 bis du
    2026-08-30).
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    trois = ("issue-avant", "issue-CIBLE", "issue-apres")

    def refuser(**_kwargs):
        raise declaration_de_rush.RefusDeDeclaration(
            "refus a trois issues, fabrique pour la mesure",
            motif=declaration_de_rush.MOTIF_SOURCE_NON_QUALIFIEE,
            issues=trois,
        )

    monkeypatch.setattr(declaration_de_rush, "declarer_un_rush", refuser)
    lancer(projet, video)

    imprimees = [
        ligne.split("Issue:", 1)[1].strip()
        for ligne in capsys.readouterr().err.splitlines()
        if ligne.strip().startswith("Issue:")
    ]
    assert imprimees == list(trois)


@requires_ffprobe
def test_AC23_le_refus_nomme_le_fichier_TEL_QUE_L_OPERATEUR_L_A_DESIGNE(
    tmp_path, capsys
):
    """`EPIC11-ARB-153` cote CLI : le vrai nom du fichier, pas l'identifiant.

    Le fichier porte des espaces et des accents, de sorte que le `rush_id`
    derive en **differe** : c'est ce qui rend la mesure non vacante. Sans cet
    ecart, nommer l'un ou l'autre serait indiscernable.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "Prise 3 ete.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)

    derive = rushes_du_manifeste(manifeste)[INDEX_DE_LA_CIBLE]["rush_id"]
    assert derive != video.name, "la fixture ne distingue pas les deux noms"

    lancer(projet, video)
    assert str(video) in capsys.readouterr().err


@requires_ffprobe
def test_AC23_volet_symetrique_un_homonyme_d_un_AUTRE_dossier_REUSSIT(
    tmp_path, capsys
):
    """`EPIC11-ARB-147`, sa moitie : ce cas-la ne passe **jamais** par le refus.

    « Deux rushes homonymes dans deux dossiers differents sont deux rushes
    distincts, et le coeur les separe **sans poser de question** par un suffixe
    derive du dossier parent (`EPIC11-ARB-9`). Ce n'est pas un refus a deux
    issues, c'est un **succes**. » Sans ce volet, la mesure du refus sec serait
    verte sur une commande qui refuserait tous les homonymes.

    Le banc ne recopie **pas** la regle du suffixe : il exige que les trois
    entrees d'origine soient intactes, qu'il y en ait exactement une de plus,
    et que son identifiant differe de celui qui etait deja pris. La regle du
    suffixe vit dans le coeur, et une recopie ici divergerait.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "A-CAM", "cible.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)

    # **L'entree deja declaree decrit un AUTRE rush, et c'est sa DUREE qui le
    # dit depuis `EPIC11-ARB-230`.** Ce banc ne changeait ici que le dossier
    # parent, ce qui suffisait avant le 2026-09-05 : le dossier ne separe plus
    # rien, et ce cas-la est desormais le refus de conflit -- il a son propre
    # test. Ce qui reste un SUCCES est le multicam ordinaire, deux prises de
    # durees differentes, et c'est ce qu'`EPIC11-ARB-9` subordonne sans
    # annuler.
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_parent"] = "B-CAM"
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_path"] = "/rushes/B-CAM/cible.mp4"
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_frame_count"] = 999
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_frame_count_is_exact"] = True
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    avant = contenu["rushes"]

    assert lancer(projet, video) == declaration_de_rush.CODE_SUCCES

    apres = rushes_du_manifeste(manifeste)
    assert apres[: len(avant)] == avant, "une entree deja declaree a ete touchee"
    assert len(apres) == len(avant) + 1
    assert apres[-1]["rush_id"] not in {rush["rush_id"] for rush in avant}

    sortie = capsys.readouterr().out
    lignes = [ligne for ligne in sortie.splitlines() if ligne.strip()]
    assert len(lignes) == 2, (
        "une homonymie levee est un succes qui se DIT: l'operateur se retrouve "
        "sinon devant un identifiant qu'il n'a pas demande"
    )
    assert "A-CAM" in sortie, "la phrase ne nomme pas le dossier qui distingue"


# ---------------------------------------------------------------------------
# AC 2.4 -- rien n'est modifie, et aucun drapeau ne le demanderait
# ---------------------------------------------------------------------------


@requires_ffprobe
def test_AC24_un_rush_deja_declare_ne_modifie_RIEN(tmp_path):
    """Inodes, `st_mtime_ns` et temoin -- **jamais un condensat**.

    Le manifeste de ce banc est deterministe : une reecriture a l'identique
    rendrait exactement les memes octets, et un condensat serait vert a tort
    (defaut deja paye le 2026-08-30). Ce qui se mesure ici est l'identite du
    fichier, sa date de modification en nanosecondes, la survie d'un temoin
    depose dans le dossier vise, et l'ensemble EXACT du contenu du dossier --
    l'enveloppe ne cree meme pas l'arborescence de journal, faute de quoi un
    refus laisserait des dossiers derriere lui.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)
    avant = rushes_du_manifeste(manifeste)
    temoin = Temoin(manifeste)

    assert lancer(projet, video) == declaration_de_rush.CODE_ERREUR

    assert temoin.manifeste_intact(), "le project.json a ete reecrit"
    assert temoin.temoin_intact(), "le dossier projet a ete nettoye"
    assert temoin.dossier_inchange(), "le dossier projet a gagne un fichier"
    assert rushes_du_manifeste(manifeste) == avant


@requires_ffprobe
def test_AC24_volet_symetrique_une_declaration_qui_REUSSIT_change_le_manifeste(
    tmp_path,
):
    """Sans ce volet, la mesure ci-dessus serait verte sur une commande inerte.

    Meme temoin, meme mesure, regime oppose : le manifeste doit changer
    d'inode -- l'ecriture est atomique, temporaire puis `os.replace` -- et
    gagner exactement un rush.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")
    manifeste = manifeste_vierge(projet)
    temoin = Temoin(manifeste)

    assert lancer(projet, video) == declaration_de_rush.CODE_SUCCES

    assert not temoin.manifeste_intact(), (
        "le detecteur d'ecriture ne voit rien la ou une ecriture a eu lieu"
    )
    assert temoin.temoin_intact()
    assert len(rushes_du_manifeste(manifeste)) == 1


def test_AC24_aucun_drapeau_ne_permet_de_MODIFIER_l_entree_existante(capsys):
    """L'AC 2.4, tenue par son critere plutot que par sa forme.

    L'AC 2.4 disait « sans le drapeau qui le demande » jusqu'au 2026-09-01,
    puis « il n'y a **aucun drapeau** » apres correction. `EPIC11-ARB-232` en
    ajoute un le 2026-09-05, et l'ecart est **nomme** au registre de la story
    plutot qu'absorbe : `--force-distinct` ne DEMANDE pas de modifier l'entree
    existante, il declare une SECONDE entree. Ce que l'AC protege -- aucune
    ecriture par-dessus -- est intact, et c'est ce que ce test mesure
    desormais : l'ensemble exact des options, et l'absence de tout drapeau
    d'ecrasement. Le volet de comportement est
    `test_ARB232_force_distinct_ne_touche_PAS_l_entree_existante`.
    """
    options = options_du_sous_parseur(capsys)
    assert options == {"--help", "--project", "--video", "--force-distinct"}
    assert not (
        options
        & {"--force", "--overwrite", "--nouvelle-version", "--ecrasement-conscient"}
    )


# ---------------------------------------------------------------------------
# B3 -- la frontiere AST du module de coeur neuf (AC 2.5)
# ---------------------------------------------------------------------------


def test_B3_le_module_de_coeur_n_importe_ni_cli_ni_sys(tmp_path):
    """AC 2.5, verifie **explicitement** sur le module neuf, jamais suppose.

    C'est la frontiere posee par l'AC 1.5 de la 11.4b, rejouee ici parce que
    l'AC 2.5 l'exige du module que le lot A vient d'ecrire : la TUI a
    interdiction d'importer `cli` (`EPIC11-ARB-67`), et un coeur qui
    l'importerait la lui ferait importer par la bande.
    """
    importes = modules_importes(ast.parse(source_du_module(declaration_de_rush)))
    assert not any(nom == "cli" or nom.endswith(".cli") for nom in importes), importes
    assert "sys" not in importes

    # Volet symetrique : `cli.py`, lui, importe `sys` -- le detecteur voit donc
    # bien ce qu'il cherche. Une frontiere negative sans ce volet est vraie par
    # vacuite.
    assert "sys" in modules_importes(ast.parse(source_du_module(cli)))


def test_B3_le_module_de_coeur_n_appelle_jamais_print():
    """AC 2.5 : le coeur **leve** et **rend**, il n'imprime pas.

    Un coeur qui imprimerait ecrirait sur un flux que la TUI possede : sous une
    boucle d'evenements, une ligne imprimee au milieu d'un ecran le detruit.
    """
    assert "print" not in noms_appeles(ast.parse(source_du_module(declaration_de_rush)))

    # Volet symetrique : l'enveloppe, elle, imprime -- c'est son role entier.
    assert "print" in noms_appeles(arbre_de_la_fonction(cli.project_add_rush_command))


def test_B3_le_module_de_coeur_ne_nomme_JAMAIS_stderr():
    """AC 2.5 : ni `print`, ni `sys.stderr` -- la mesure porte sur les deux.

    Le detecteur est textuel a dessein : `sys.stderr` peut arriver par un
    import de `sys` (que le test precedent ferme), mais aussi par un
    `from sys import stderr` ou par un objet passe en parametre. Le texte les
    attrape tous les trois.
    """
    assert "stderr" not in source_du_module(declaration_de_rush)

    # Volet symetrique : `cli.py` en est plein, et c'est sa place.
    assert "stderr" in source_du_module(cli)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-232` -- `--force-distinct`, cite dans le refus et qui FAIT
# ---------------------------------------------------------------------------
#
# La cloture d'`EPIC11-ARB-224` a pose la regle : une commande nommee dans un
# refus doit etre **tapable**, doit **parser**, et doit **changer quelque
# chose**. Les deux premiers volets sont tenus par
# `tests/unit/test_conformite_sorties_nommees.py`, qui balaie toutes les
# chaines des sources et rejoue chaque citation contre le VRAI parseur. Le
# troisieme volet y est restreint a `project remove` : il se mesure donc ici,
# sur la commande que ce banc possede.


@requires_ffprobe
def test_ARB232_la_commande_CITEE_dans_le_refus_est_celle_qu_on_peut_TAPER(
    tmp_path, capsys
):
    """Le refus cite la ligne avec les valeurs REELLES : elle se recopie.

    On la relit dans la sortie d'erreur et on la **rejoue** telle quelle, sans
    en reecrire un mot -- une ligne refabriquee par le banc mesurerait le banc.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "B", "cible.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)

    # L'entree declaree decrit le MEME rush venu d'un AUTRE dossier : c'est le
    # conflit d'`EPIC11-ARB-230`, et son refus est celui qui cite le drapeau.
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_parent"] = "A"
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_path"] = "/rushes/A/cible.mp4"
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    avant = contenu["rushes"]

    assert lancer(projet, video) == declaration_de_rush.CODE_ERREUR
    erreur = capsys.readouterr().err

    citee = re.search(r"`mmu (project add-rush [^`]*--force-distinct)`", erreur)
    assert citee, erreur
    argv = citee.group(1).split()
    assert argv[-1] == "--force-distinct"

    # Rejeu de la citation, mot pour mot : elle doit ABOUTIR.
    assert cli.main(argv) == declaration_de_rush.CODE_SUCCES

    apres = rushes_du_manifeste(manifeste)
    assert apres[: len(avant)] == avant, "une entree existante a ete touchee"
    assert len(apres) == len(avant) + 1
    assert apres[-1]["rush_id"] not in {rush["rush_id"] for rush in avant}


@requires_ffprobe
def test_ARB232_volet_symetrique_SANS_le_drapeau_la_meme_ligne_REFUSE(
    tmp_path, capsys
):
    """Sans lui, le rejeu ci-dessus serait vert sur un drapeau qui ne fait rien.

    Un drapeau accepte par le parseur puis ignore par le coeur est exactement
    le « reste inerte » que le depot retire depuis le 2026-08-17, et c'est le
    second etage du defaut `C1-02`.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "B", "cible.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)

    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_parent"] = "A"
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_path"] = "/rushes/A/cible.mp4"
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    avant = contenu["rushes"]

    assert lancer(projet, video) == declaration_de_rush.CODE_ERREUR
    capsys.readouterr()
    assert rushes_du_manifeste(manifeste) == avant

    # Le MEME appel, le drapeau en plus : il change le verdict.
    assert lancer(projet, video, "--force-distinct") == (
        declaration_de_rush.CODE_SUCCES)
    assert len(rushes_du_manifeste(manifeste)) == len(avant) + 1


def test_ARB232_aucune_ABREVIATION_du_drapeau_n_est_acceptee(tmp_path, capsys):
    """`allow_abbrev=False` couvre le drapeau neuf, comme les deux autres.

    Mutant `M19` de la story 11.4e, lot B : sans ce drapeau sur le
    sous-parseur, `--force-dist` serait ACCEPTE. Le motif d'`EPIC11-ARB-220`
    mord a retardement -- une abreviation acceptee ne se paie qu'au renommage
    suivant, quand il est trop tard pour qu'argparse refuse bruyamment.
    """
    projet = tmp_path / "projet"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "rushes", "cible.mp4")

    with pytest.raises(SystemExit) as sortie:
        lancer(projet, video, "--force-dist")
    assert sortie.value.code == 2
    assert "unrecognized arguments: --force-dist" in capsys.readouterr().err


@requires_ffprobe
def test_ARB232_le_compte_rendu_DISTINGUE_forcage_et_separation_constatee(
    tmp_path, capsys
):
    """Deux succes, deux phrases : l'operateur doit savoir QUI a tranche.

    Une separation constatee sur une divergence technique (`EPIC11-ARB-9`) et
    une separation **demandee** (`EPIC11-ARB-232`) levent toutes deux une
    homonymie. Les dire de la meme facon laisserait croire que la machine a su
    distinguer deux rushes qu'elle juge identiques -- c'est le contraire de ce
    que `EPIC11-ARB-230` etablit.
    """
    projet = tmp_path / "projet"
    video = copie_du_rush(tmp_path / "B", "cible.mp4")
    manifeste = projet_ou_le_rush_est_DEJA_declare(projet, video)

    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_parent"] = "A"
    contenu["rushes"][INDEX_DE_LA_CIBLE]["source_path"] = "/rushes/A/cible.mp4"
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")

    assert lancer(projet, video, "--force-distinct") == (
        declaration_de_rush.CODE_SUCCES)
    forcee = capsys.readouterr().out
    assert "--force-distinct" in forcee
    assert "SEPAREMENT" in forcee

    # Volet symetrique : une separation CONSTATEE ne parle pas de forcage. La
    # duree diverge, donc `EPIC11-ARB-9` joue tout seul.
    autre = copie_du_rush(tmp_path / "C", "cible.mp4", RUSH_REEL_AUTRE_DUREE)
    assert lancer(projet, autre) == declaration_de_rush.CODE_SUCCES
    constatee = capsys.readouterr().out
    assert "--force-distinct" not in constatee
    assert "critere technique" in constatee
