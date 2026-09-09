"""Story 11.4e, **lot A** -- le socle de coeur de la declaration d'un rush.

Ce banc mesure l'AC 1 et elle seule : un point d'entree de coeur qui declare un
rush dans un projet ouvert **sans l'extraire**. Ni la CLI (lot B) ni l'ecran
TUI (lot C) ne sont dans son perimetre.

Les trois arbitrages qu'il tient, tranches par Egan le 2026-09-01 :

* `EPIC11-ARB-145` -- **une cadence source inconnue REFUSE la declaration.**
  Pas de declaration a l'aveugle : la cadence source entre dans l'identite du
  lot et dans son nom de dossier, et un rush declare sans elle produirait une
  entree qu'aucune extraction ulterieure ne pourrait rattacher. Le refus est
  **nomme** dans la table publiee du coeur ;
* `EPIC11-ARB-146` -- **le `rush_id` reste DERIVE du nom de fichier**, jamais
  choisi, et la derivation est **reutilisee** (`normalize_identifier`, puis
  `rush_identity_conflict` / `disambiguated_rush_id`). Une seconde redaction
  divergerait, et l'ecart ne se verrait que sur un manifeste ;
* `EPIC11-ARB-147` -- **un rush deja declare mene a un REFUS SEC, une seule
  issue.** `EPIC11-ARB-89` ne s'applique pas : il gouverne une ecriture qui
  passerait PAR-DESSUS une sortie existante, et ici rien n'est ecrit ni
  detruit. Son **volet symetrique** est obligatoire : un rush homonyme que le
  coeur juge DISTINCT ne passe **jamais** par ce refus -- `EPIC11-ARB-9` le
  resout tout seul par un identifiant leve, et c'est un **succes**.

**Ce banc ne fige AUCUN critere d'identite de rush**, et c'est une consigne
d'Egan du 2026-09-01, arrivee pendant le lot. Le comparateur actuel
(`rush_identity_conflict`) ne regarde que le **nom du dossier parent seul**,
alors que le manifeste porte deja le chemin complet resolu : deux fichiers
homonymes poses dans `03_tournage_mai/hd/` et `04_tournage_juin/hd/` ont tous
deux `source_parent = "hd"`, sont donc declares en conflit a tort, et se
voient suffixer tous deux `...-hd` -- la collision n'est meme pas levee. Le
critere futur n'est pas tranche (chemin complet, ou criteres techniques :
duree, timecode de depart, cadence, resolution). Les tests d'identite sont
donc formules sur le **comportement** -- « deux rushes que le coeur juge
distincts recoivent deux identifiants distincts » --, jamais sur **par quoi**
il les juge, et par **substitution** du comparateur la ou la delegation est ce
qui compte. Quand deux sources doivent etre distinguables, elles different par
leur chemin complet ET par leurs caracteristiques techniques, de sorte que
l'enonce reste vrai sous les deux criteres candidats.

Six sections, une par tache du lot, et six formes de mesure differentes :

* `A1` -- la **signature de producteur**, mesuree a l'introspection et a l'arbre
  syntaxique : aucun `args`, aucun `print`, aucun code de sortie rendu, aucun
  import de `cli`. Chaque frontiere negative porte son **volet symetrique** --
  le meme detecteur applique a un module qui, lui, imprime -- sans quoi elle
  pourrait etre verte par vacuite ;
* `A2` -- la derivation **reutilisee** : egalite avec l'appel direct de
  `normalize_identifier`, et frontiere negative sur toute seconde redaction
  (aucun `re.sub`, aucun `unicodedata`, aucun `.replace` dans le module neuf) ;
* `A3` -- l'entree `rushes[]`, mesuree par **egalite d'ensembles exacts** entre
  « declare puis extrait » et « extrait directement », et `lots[]` inchange
  avec son volet symetrique ;
* `A4` -- la **table publiee** : les motifs reellement leves forment un ensemble
  **EXACTEMENT** egal a la table, dans les deux sens ;
* `A5` -- le refus **sec**, son issue unique, et son volet symetrique ;
* `A6` -- l'**ordre** des trois etapes, mesure par sondes horodatees posees sur
  le module (jamais par lecture du code), et l'absence d'ecriture mesuree aux
  **inodes**, au **`st_mtime_ns`** et par un **temoin** -- jamais par un
  condensat, qu'une reecriture identique laisserait vert.

Regle des fabriques de `CLAUDE.md`, point **2 bis** compris : le manifeste des
sections qui parcourent `rushes[]` porte **trois** rushes **distinguables**
(trois noms, trois dossiers parents, trois cadences), et la cible est en
**deuxieme sur trois** -- ni premiere ni derniere. La position se verifie sur
`manifest["rushes"]`, **la liste que le code parcourt** dans
`build_rush_declaration_manifest`, jamais sur celle qu'une fabrique aurait
ecrite ailleurs.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import declaration_de_rush, extraction, video_metadata
from mixed_media_utility.io import naming
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="binaires ffmpeg/ffprobe absents du PATH",
)

#: Le rush reel du banc : 125 frames a 25 im/s, 1920x1080. Il n'est **pas** en
#: Git LFS (236 ko committes en clair), donc ce banc est mesurable dans un
#: conteneur neuf sans `git lfs pull`.
RUSH_REEL = REPO_ROOT / "tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps.mp4"

#: Un second rush reel, de resolution differente : il sert partout ou deux
#: rushes doivent etre **distinguables** autrement que par leur nom.
#:
#: **Il ne suffit plus depuis `EPIC11-ARB-230`, et la mesure le dit** : les
#: quatre fixtures de synthese portent toutes 125 frames, 25/1 et aucun
#: timecode de depart -- elles ne different que par leur RESOLUTION, qui n'est
#: pas un critere d'identite du rush. Deux d'entre elles sous le meme nom sont
#: donc le **meme rush** pour le produit, et c'est correct.
RUSH_REEL_BIS = REPO_ROOT / "tests/fixtures/rushes/rush_test_4x3_1080x1436_25fps.mp4"

#: Le rush qui diverge sur un critere d'**identite** : meme resolution et meme
#: cadence que `RUSH_REEL`, mais **50 frames** contre 125. C'est le multicam
#: ordinaire d'`EPIC11-ARB-9` -- deux prises differentes --, et c'est le seul
#: montage qui fait encore jouer la separation silencieuse depuis
#: `EPIC11-ARB-230`. 7 Ko, en git ordinaire comme ses quatre soeurs.
RUSH_REEL_AUTRE_DUREE = (
    REPO_ROOT / "tests/fixtures/rushes/rush_test_16x9_1920x1080_25fps_50img.mp4"
)

#: Un binaire qui n'existe pas. Le passer est ce qui rend la section `A6`
#: capable de mesurer un **ordre** sans lire une ligne de code : si une garde
#: bon marche ne precedait pas le probe, l'exception rendue serait
#: `FfprobeNotFoundError` et non le refus nomme.
FFPROBE_ABSENT = "mmu-ffprobe-qui-n-existe-pas"


class JournalMuet:
    """Un logger minimal : le point d'entree en exige un, on n'en lit rien."""

    def __init__(self) -> None:
        self.lignes: list[str] = []

    def info(self, message, *args, **kwargs) -> None:
        self.lignes.append(str(message) % args if args else str(message))

    warning = error = debug = info


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


#: Les trois rushes de la fabrique, **distinguables sur quatre axes** : nom,
#: chemin complet, dossier parent, cadence. Un remplissage uniforme rendrait
#: invisible tout appariement positionnel inverse (defaut `M33` de la 5.6).
#:
#: Les quatre axes divergent **ensemble**, a dessein : le critere d'identite
#: d'un rush est en cours de reexamen (le comparateur actuel ne regarde que le
#: nom du dossier parent, et declare a tort en conflit deux fichiers homonymes
#: poses dans `.../hd/` et `.../hd/`). Une fabrique qui ne divergerait que sur
#: l'axe d'aujourd'hui deviendrait fausse le jour ou le critere change.
#:
#: **Les DUREES sont posees depuis `EPIC11-ARB-230`** (2026-09-05), et ce n'est
#: pas un enrichissement de confort : le dossier ayant cesse d'etre un critere
#: d'identite, une entree qui ne declare **aucune** duree rend les trois
#: criteres restants non verifiables -- donc jamais divergents -- et le coeur
#: la juge alors identique a n'importe quel homonyme. La fabrique d'avant
#: mesurait donc, sans le dire, le cas des manifestes ANCIENS. Ce cas-la est
#: reel et il a son propre test (`test_ARB230_une_entree_SANS_duree_ne_se_
#: separe_plus_toute_seule`) ; il n'a rien a faire dans la fabrique par
#: defaut, ou il rendait muettes toutes les mesures de separation.
TROIS_RUSHES = (
    {"rush_id": "avant", "source_name": "avant.mov", "source_parent": "Z-CAM",
     "source_path": "/rushes/tournage-avril/Z-CAM/avant.mov",
     "fps_source": 24.0, "fps_source_exact": "24/1",
     "source_frame_count": 480, "source_frame_count_is_exact": True},
    {"rush_id": "cible", "source_name": "cible.mov", "source_parent": "A-CAM",
     "source_path": "/rushes/tournage-mai/A-CAM/cible.mov",
     "fps_source": 25.0, "fps_source_exact": "25/1",
     "source_frame_count": 125, "source_frame_count_is_exact": True},
    {"rush_id": "apres", "source_name": "apres.mov", "source_parent": "B-CAM",
     "source_path": "/rushes/tournage-juin/B-CAM/apres.mov",
     "fps_source": 30.0, "fps_source_exact": "30/1",
     "source_frame_count": 900, "source_frame_count_is_exact": True},
)

#: L'index de la cible dans `manifest["rushes"]`, **la liste que le code
#: parcourt**. Deuxieme sur trois : ni premiere (un `find` fautif qui rend
#: toujours le premier element se demasque) ni derniere (une boucle qui casse
#: au lieu de continuer se demasque, point 2 bis du 2026-08-30).
INDEX_DE_LA_CIBLE = 1


def manifeste_a_trois_rushes(
    dossier: Path,
    *,
    project_id: str = "projet-a",
    rushes=TROIS_RUSHES,
) -> Path:
    """Un `project.json` portant trois rushes distinguables, cible au milieu."""
    chemin = manifeste_vierge(dossier, project_id)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu["rushes"] = [dict(rush) for rush in rushes]
    chemin.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    return chemin


def copie_du_rush(dossier: Path, nom: str, source: Path = RUSH_REEL) -> Path:
    """Une copie nommee du rush reel, dans le dossier voulu."""
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom
    shutil.copyfile(source, cible)
    return cible


def fichier_qui_n_est_pas_une_video(dossier: Path, nom: str = "faux.mov") -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    chemin.write_bytes(b"ce fichier n'est pas une video, et c'est voulu")
    return chemin


def rushes_du_manifeste(manifest_path: Path) -> list[dict]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))["rushes"]


def entree_du_rush(manifest_path: Path, rush_id: str) -> dict:
    for rush in rushes_du_manifeste(manifest_path):
        if rush["rush_id"] == rush_id:
            return rush
    raise AssertionError(f"rush {rush_id!r} absent du manifeste")


class Temoin:
    """Inodes, `st_mtime_ns` et un temoin depose -- **jamais un condensat**.

    Un condensat ne prouve rien ici : la fabrique est deterministe, donc une
    reecriture rend exactement les memes octets et le laisse vert a tort
    (`CLAUDE.md`, 2026-08-30). Ce qu'on mesure est l'**identite du fichier** et
    la survie d'un fichier tiers depose dans le dossier vise -- une reecriture
    par temporaire + `os.replace` change l'inode, une reecriture en place
    change la `st_mtime_ns`, et un nettoyage du dossier emporte le temoin.
    """

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        stat = manifest_path.stat()
        self.inode = stat.st_ino
        self.mtime_ns = stat.st_mtime_ns
        self.temoin = manifest_path.parent / "temoin-de-la-mesure.txt"
        self.temoin.write_text("ne doit pas disparaitre", encoding="utf-8")
        self.temoin_inode = self.temoin.stat().st_ino
        # Le temoin est depose AVANT la mesure : sa mtime ne doit pas non plus
        # entrer en collision de seconde avec celle du manifeste.
        time.sleep(0.01)

    def intact(self) -> bool:
        stat = self.manifest_path.stat()
        return (
            stat.st_ino == self.inode
            and stat.st_mtime_ns == self.mtime_ns
            and self.temoin.is_file()
            and self.temoin.stat().st_ino == self.temoin_inode
        )


def source_du_module(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def arbre_du_module(module) -> ast.Module:
    return ast.parse(source_du_module(module))


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


# ---------------------------------------------------------------------------
# A1 -- la signature de producteur
# ---------------------------------------------------------------------------


def test_A1_le_point_d_entree_a_une_signature_de_producteur():
    """Parametres **nommes**, aucun objet `args` (AC 1.1).

    C'est tout le motif du lot A : la TUI a interdiction d'importer `cli`
    (`EPIC11-ARB-67`), donc un point d'entree qui lirait un `argparse.Namespace`
    serait inutilisable par elle.
    """
    import inspect

    signature = inspect.signature(declaration_de_rush.declarer_un_rush)
    assert "args" not in signature.parameters

    positionnels = [
        nom
        for nom, parametre in signature.parameters.items()
        if parametre.kind
        in (parametre.POSITIONAL_ONLY, parametre.POSITIONAL_OR_KEYWORD)
    ]
    assert positionnels == [], (
        "un producteur de coeur ne prend que des parametres nommes: "
        f"{positionnels!r} sont positionnels"
    )
    assert {"project_dir", "video_path", "logger"} <= set(signature.parameters)


def test_A1_le_module_n_imprime_pas_ne_sort_pas_et_n_importe_pas_cli():
    """Frontiere negative de l'AC 1.1, mesuree a l'arbre syntaxique."""
    arbre = arbre_du_module(declaration_de_rush)
    appels = noms_appeles(arbre)
    importes = modules_importes(arbre)

    assert "print" not in appels
    assert "exit" not in appels
    assert not any("cli" == m or m.endswith(".cli") for m in importes), importes
    assert "sys" not in importes
    assert "stderr" not in source_du_module(declaration_de_rush)


def test_A1_volet_symetrique_les_memes_detecteurs_voient_ce_qu_ils_cherchent():
    """Sans ce volet, le test precedent pourrait etre vrai par vacuite.

    Un detecteur casse -- un `noms_appeles` qui rendrait toujours l'ensemble
    vide, un `modules_importes` muet -- rendrait le test precedent vert sur
    n'importe quel module. On l'applique donc a `cli.py`, qui imprime, sort et
    importe, et il **doit** y trouver les trois.
    """
    from mixed_media_utility import cli

    arbre = arbre_du_module(cli)
    assert "print" in noms_appeles(arbre)
    assert "sys" in modules_importes(arbre)


def test_A1_le_point_d_entree_leve_et_rend_un_objet_jamais_un_code(tmp_path):
    """Il **leve** sur un refus et **rend** un objet sur un succes (AC 1.1)."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert not isinstance(issue, int)
    assert issue.rush_id == "prise01"
    assert issue.manifest_path == manifeste

    with pytest.raises(declaration_de_rush.RefusDeDeclaration):
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )


# ---------------------------------------------------------------------------
# A2 -- la derivation du rush_id, REUTILISEE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nom_de_fichier",
    ["prise01.mov", "Prise 01 (ete).mov", "A_B-C.mov", "  espaces  .mov"],
)
def test_A2_le_rush_id_est_exactement_celui_de_normalize_identifier(
    tmp_path, nom_de_fichier
):
    """AC 1.2 : derive par le chemin deja ecrit, jamais par une seconde redaction."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", nom_de_fichier)

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    attendu = naming.normalize_identifier(
        Path(nom_de_fichier).stem, label="le nom du fichier source"
    )
    assert issue.rush_id == attendu
    assert issue.rush_id_derive == attendu


def test_A2_le_module_n_ecrit_aucune_seconde_derivation():
    """Frontiere negative d'`EPIC11-ARB-146` : corps appele, jamais reecrit.

    Le module **appelle** les trois fonctions existantes et ne porte aucun des
    outils avec lesquels on en ecrirait une seconde -- pas de `re`, pas
    d'`unicodedata`, pas de `.replace`, pas de `.lower`. Une seconde redaction
    divergerait au premier ajustement de la convention, et l'ecart ne se
    verrait que sur un manifeste.
    """
    arbre = arbre_du_module(declaration_de_rush)
    appels = noms_appeles(arbre)
    importes = modules_importes(arbre)

    assert {
        "normalize_identifier",
        "rush_identity_conflict",
        "disambiguated_rush_id",
    } <= appels

    assert "re" not in importes
    assert "unicodedata" not in importes
    assert appels & {"sub", "replace", "lower", "casefold", "translate"} == set()


def test_A2_volet_symetrique_la_derivation_vit_bien_ailleurs():
    """Le meme detecteur, applique la ou la derivation est ecrite, la trouve."""
    arbre = arbre_du_module(naming)
    assert modules_importes(arbre) & {"re", "unicodedata"}


def test_A2_deux_rushes_juges_DISTINCTS_recoivent_deux_identifiants_distincts(
    tmp_path,
):
    """AC 1.2 et `EPIC11-ARB-9` : deux rushes distincts, aucun ecrasement.

    **Ce test ne dit pas PAR QUOI le coeur juge deux rushes distincts**, et
    c'est delibere. Le critere d'identite est en cours de reexamen : au
    2026-09-01, `rush_identity_conflict` compare le **nom du dossier parent
    seul**, ce qui declare a tort en conflit deux fichiers homonymes poses dans
    `03_tournage_mai/hd/` et `04_tournage_juin/hd/` -- et les suffixe alors
    tous deux `...-hd`, sans lever la collision. Egan hesite entre le chemin
    complet et des criteres techniques (duree, timecode, cadence, resolution).
    Un test qui figerait « le dossier parent » ici deviendrait un obstacle a la
    correction plutot qu'une garde.

    Ce qui est mesure est donc le **comportement** : deux rushes que le coeur
    juge distincts recoivent deux identifiants distincts, et le premier n'est
    pas ecrase.

    **Le critere a ete tranche depuis, et la fixture a du suivre**
    (`EPIC11-ARB-230`, 2026-09-05) : ce sont le nom, la duree, la cadence et le
    timecode initial, et eux seuls. Les deux sources choisies divergent donc
    par leur **duree** -- 125 frames contre 50 --, ce qui est le multicam
    ordinaire d'`EPIC11-ARB-9`. Deux resolutions differentes ne suffiraient
    plus : la resolution n'est pas un critere d'identite, et les quatre
    fixtures de synthese portent toutes 125 frames a 25/1.

    La cible est en **deuxieme position sur trois** dans `manifest["rushes"]`,
    la liste que `build_rush_declaration_manifest` parcourt.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_a_trois_rushes(projet)
    assert rushes_du_manifeste(manifeste)[INDEX_DE_LA_CIBLE]["rush_id"] == "cible"

    video = copie_du_rush(tmp_path / "tournage-juin" / "hd", "cible.mov",
                          RUSH_REEL_AUTRE_DUREE)
    avant = rushes_du_manifeste(manifeste)

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert issue.rush_id_derive == "cible"
    assert issue.rush_id != issue.rush_id_derive
    assert issue.homonymie_levee is True

    apres = rushes_du_manifeste(manifeste)
    # Ensemble EXACT, jamais une inclusion : une assertion positive laisserait
    # passer toute divergence supplementaire.
    assert {rush["rush_id"] for rush in apres} == {
        "avant", "cible", "apres", issue.rush_id
    }
    # Et les trois entrees preexistantes sont intactes, dans leur ordre.
    assert apres[: len(avant)] == avant


def test_A2_l_identifiant_leve_est_CALCULE_par_le_coeur_jamais_recopie(tmp_path):
    """`EPIC11-ARB-146` : le module **delegue**, il ne calcule rien lui-meme.

    Mesure par **substitution** plutot que par egalite avec une valeur
    attendue : on remplace `disambiguated_rush_id` par un temoin, et
    l'identifiant rendu doit etre celui du temoin. C'est ce qui rend ce test
    insensible au critere d'identite -- il mesure que le calcul vit a **un
    seul endroit**, sans dire ce que ce calcul vaut. Un module qui recopierait
    la regle rendrait sa propre valeur et rougirait ici.
    """
    projet = tmp_path / "projet-a"
    manifeste_a_trois_rushes(projet)
    # La duree, et non la resolution : `EPIC11-ARB-230` a retire le dossier des
    # criteres, et la resolution n'en a jamais fait partie.
    video = copie_du_rush(tmp_path / "tournage-juin" / "hd", "cible.mov",
                          RUSH_REEL_AUTRE_DUREE)

    vus: list[tuple] = []

    def temoin(rush_id, source_parent):
        vus.append((rush_id, source_parent))
        return "identifiant-du-temoin"

    original = declaration_de_rush.disambiguated_rush_id
    declaration_de_rush.disambiguated_rush_id = temoin
    try:
        issue = declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    finally:
        declaration_de_rush.disambiguated_rush_id = original

    assert issue.rush_id == "identifiant-du-temoin"
    assert len(vus) == 1
    assert vus[0][0] == "cible"


def test_A2_le_JUGEMENT_d_identite_est_delegue_lui_aussi(tmp_path):
    """Meme geste sur `rush_identity_conflict` : le critere n'est pas ici.

    Le module ne decide **jamais** lui-meme si deux rushes sont le meme : il
    pose la question au coeur et agit sur la reponse. Ce test le mesure dans
    les deux regimes -- une reponse « conflit » leve un identifiant distinct,
    une reponse « pas de conflit » n'en leve aucun --, sans jamais dire ce qui
    fonde la reponse. C'est ce qui permettra de changer le critere sans
    toucher a ce banc.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "quelque-part", "prise01.mov")

    original = declaration_de_rush.rush_identity_conflict
    # Le double porte le mot-cle `mesures` : depuis `EPIC11-ARB-230`, le
    # module pose la question APRES le probe et transmet ce qu'il a mesure.
    declaration_de_rush.rush_identity_conflict = (
        lambda rushes, rush_id, source_parent, *, mesures=None: None
    )
    try:
        sans_conflit = declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    finally:
        declaration_de_rush.rush_identity_conflict = original

    assert sans_conflit.rush_id == sans_conflit.rush_id_derive == "prise01"
    assert sans_conflit.homonymie_levee is False

    autre = copie_du_rush(tmp_path / "ailleurs", "prise01.mov",
                          RUSH_REEL_AUTRE_DUREE)

    # **Reconciliation de la liaison du 2026-09-05.** Le double rendait un
    # `dict` -- le contrat de `rush_identity_conflict` sur la branche d'origine.
    # Depuis `d244c307` (note 5 de la relecture d'Egan du 2026-09-01), la
    # fonction rend un `ConflitIdentiteRush` et l'entree homonyme vit sous
    # `.entree`. Le double est donc **construit avec la vraie classe du coeur**,
    # jamais avec un objet de facade : c'est ce qui fait que ce test rougira
    # encore le jour ou le verdict changera de forme une troisieme fois, au lieu
    # de figer un contrat perime dans le banc.
    verdict = extraction.comparer_identite_rush(
        extraction.CriteresIdentiteRush(source_parent="ailleurs-declare"),
        extraction.CriteresIdentiteRush(source_parent="ailleurs"),
    )
    declaration_de_rush.rush_identity_conflict = (
        lambda rushes, rush_id, source_parent, *,
        mesures=None: extraction.ConflitIdentiteRush(
            entree={"rush_id": rush_id},
            declares=verdict.declares,
            mesures=verdict.mesures,
            divergents=verdict.divergents,
            concordants=verdict.concordants,
            non_verifiables=verdict.non_verifiables,
        )
    )
    try:
        avec_conflit = declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=autre, logger=JournalMuet()
        )
    finally:
        declaration_de_rush.rush_identity_conflict = original

    assert avec_conflit.homonymie_levee is True
    assert avec_conflit.rush_id != avec_conflit.rush_id_derive == "prise01"


# ---------------------------------------------------------------------------
# A3 -- l'entree rushes[] SEULE
# ---------------------------------------------------------------------------


@requires_ffmpeg
def test_A3_l_entree_declaree_est_celle_qu_une_extraction_ecrirait(tmp_path):
    """AC 1.3, mesure par egalite d'**ensembles exacts**, pas par inclusion.

    Deux projets de meme nom -- le `project_id` en derive --, le meme fichier
    source. A gauche on declare puis on extrait ; a droite on extrait
    directement. Les deux entrees `rushes[]` doivent etre identiques, cle pour
    cle et valeur pour valeur : sans quoi une declaration prealable changerait
    ce qu'un projet raconte de sa source.
    """
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    gauche = tmp_path / "g" / "projet-a"
    droite = tmp_path / "d" / "projet-a"
    manifeste_gauche = manifeste_vierge(gauche)
    manifeste_droite = manifeste_vierge(droite)

    declaration_de_rush.declarer_un_rush(
        project_dir=gauche, video_path=video, logger=JournalMuet()
    )
    entree_apres_declaration = entree_du_rush(manifeste_gauche, "prise01")

    for projet in (gauche, droite):
        extraction.run_extraction(
            project_dir=projet,
            video_path=video,
            fps_target=1.0,
            consent_granted=True,
            unknown_color_accepted=True,
            logger=JournalMuet(),
        )

    a_gauche = entree_du_rush(manifeste_gauche, "prise01")
    a_droite = entree_du_rush(manifeste_droite, "prise01")

    assert set(a_gauche) == set(a_droite)
    assert a_gauche == a_droite

    # Et la declaration seule ecrivait deja EXACTEMENT le meme jeu de cles :
    # c'est ce qui rend la declaration utile a une TUI qui affiche un rush
    # avant toute extraction.
    assert set(entree_apres_declaration) == set(a_droite)
    assert entree_apres_declaration == a_droite


def test_A3_la_declaration_ne_cree_aucun_lot(tmp_path):
    """AC 1.4, frontiere negative : `lots[]` est inchange, liste entiere."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    contenu["lots"] = [
        {"lot_id": "autre_24", "rush_id": "avant"},
        {"lot_id": "autre_25", "rush_id": "apres"},
        {"lot_id": "autre_30", "rush_id": "encore"},
    ]
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
    lots_avant = contenu["lots"]

    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    apres = json.loads(manifeste.read_text(encoding="utf-8"))
    assert apres["lots"] == lots_avant


@requires_ffmpeg
def test_A3_volet_symetrique_une_extraction_ajoute_bien_un_lot(tmp_path):
    """Sans ce volet, la frontiere precedente serait verte sur un manifeste
    qu'on aurait cesse d'ecrire du tout."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert json.loads(manifeste.read_text(encoding="utf-8"))["lots"] == []

    extraction.run_extraction(
        project_dir=projet,
        video_path=video,
        fps_target=1.0,
        consent_granted=True,
        unknown_color_accepted=True,
        logger=JournalMuet(),
    )
    lots = json.loads(manifeste.read_text(encoding="utf-8"))["lots"]
    assert [lot["lot_id"] for lot in lots] == ["prise01_1"]


def test_A3_le_module_ne_passe_pas_par_persist_extraction():
    """Tache A3 : `persist_extraction` exige un `ExtractionRecord` complet."""
    appels = noms_appeles(arbre_du_module(declaration_de_rush))
    assert "persist_extraction" not in appels
    assert "persist_rush_declaration" in appels


def test_A3_volet_symetrique_l_extraction_y_passe_toujours():
    assert "persist_extraction" in noms_appeles(arbre_du_module(extraction))


def test_A3_aucune_frame_n_est_ecrite(tmp_path):
    """AC 1.5 : rien sous le dossier projet hors le manifeste."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    fichiers = {
        chemin.relative_to(projet).as_posix()
        for chemin in projet.rglob("*")
        if chemin.is_file()
    }
    assert fichiers == {MANIFEST_FILENAME}


def test_A3_ffmpeg_n_est_jamais_appele_et_ffprobe_l_est_une_seule_fois(tmp_path):
    """AC 1.5, comptage reel sur des binaires-temoins, pas sur le code.

    Le `PATH` de l'appel ne porte que deux scripts : un `ffmpeg` qui compte et
    echoue -- son seul appel ferait rougir --, et un `ffprobe` qui compte puis
    delegue au vrai. Le volet symetrique est dans le meme test : `ffprobe` doit
    etre appele **exactement une fois**, sans quoi le zero de `ffmpeg` ne
    prouverait que l'inertie du chemin.
    """
    vrai_ffprobe = shutil.which("ffprobe")
    if vrai_ffprobe is None:
        pytest.skip("ffprobe absent du PATH")

    bacs = tmp_path / "bin"
    bacs.mkdir()
    compteur = tmp_path / "compteur"
    compteur.mkdir()

    (bacs / "ffmpeg").write_text(
        f'#!/bin/sh\necho x >> "{compteur}/ffmpeg"\nexit 1\n', encoding="utf-8"
    )
    (bacs / "ffprobe").write_text(
        f'#!/bin/sh\necho x >> "{compteur}/ffprobe"\nexec "{vrai_ffprobe}" "$@"\n',
        encoding="utf-8",
    )
    for nom in ("ffmpeg", "ffprobe"):
        (bacs / nom).chmod(0o755)

    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    ancien_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(bacs)
    try:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    finally:
        os.environ["PATH"] = ancien_path

    appels_ffmpeg = (compteur / "ffmpeg").read_text().count("x") if (
        compteur / "ffmpeg"
    ).is_file() else 0
    appels_ffprobe = (compteur / "ffprobe").read_text().count("x") if (
        compteur / "ffprobe"
    ).is_file() else 0

    assert appels_ffmpeg == 0
    assert appels_ffprobe == 1


# ---------------------------------------------------------------------------
# A4 -- la table de refus publiee
# ---------------------------------------------------------------------------


def refus_de(fonction) -> declaration_de_rush.RefusDeDeclaration:
    with pytest.raises(declaration_de_rush.RefusDeDeclaration) as capture:
        fonction()
    return capture.value


def probe_sans_cadence(*args, **kwargs):
    """Un probe ffprobe qui declare `0/0` : cadence source indeterminee."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "0/0",
                "avg_frame_rate": "0/0",
                "duration": "5.0",
                "nb_frames": "125",
            }
        ],
        "format": {},
    }


def probe_sans_corroboration(*args, **kwargs):
    """Cadence annoncee, mais ni duree ni cardinal : elle est inverifiable."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "25/1",
                "avg_frame_rate": "25/1",
            }
        ],
        "format": {},
    }


def cinq_refus(tmp_path, monkeypatch) -> dict[str, str]:
    """Declencher les cinq refus de l'AC 1.6 et rendre {cas: motif}."""
    journal = JournalMuet()
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    motifs: dict[str, str] = {}

    motifs["projet_sans_manifeste"] = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=tmp_path / "projet-absent",
            video_path=video,
            logger=journal,
        )
    ).motif

    motifs["fichier_introuvable"] = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=tmp_path / "A-CAM" / "jamais-vu.mov",
            logger=journal,
        )
    ).motif

    motifs["chemin_non_fichier"] = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=tmp_path / "A-CAM", logger=journal
        )
    ).motif

    pas_une_video = fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM")
    motifs["source_non_qualifiee"] = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=pas_une_video, logger=journal
        )
    ).motif

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=journal
    )
    motifs["rush_deja_declare"] = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=journal
        )
    ).motif

    return motifs


def test_A4_les_motifs_leves_forment_EXACTEMENT_la_table_publiee(
    tmp_path, monkeypatch
):
    """AC 1.6 : ensemble **exact**, dans les deux sens, jamais une inclusion.

    Une assertion positive (« ce motif est dans la table ») laisserait passer
    un motif publie que rien ne leve -- une surface morte -- comme un motif
    leve qui n'est pas publie -- un refus anonyme devant l'operateur.
    """
    motifs = cinq_refus(tmp_path, monkeypatch)
    assert set(motifs.values()) == set(declaration_de_rush.MOTIFS_DE_REFUS)
    assert len(motifs) == len(declaration_de_rush.MOTIFS_DE_REFUS) == 5


def test_A4_la_cadence_inconnue_est_un_refus_nomme(tmp_path, monkeypatch):
    """`EPIC11-ARB-145` : pas de declaration a l'aveugle."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata, "probe_media", probe_sans_cadence
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )
    assert refus.motif == declaration_de_rush.MOTIF_SOURCE_NON_QUALIFIEE
    assert "cadence" in str(refus).lower()


def test_A4_la_cadence_inverifiable_est_le_meme_refus_nomme(tmp_path, monkeypatch):
    """`EPIC11-ARB-145` encore : une cadence annoncee mais non corroborable.

    C'est le regime `ARB-6` de l'extraction, applique au meme titre : declarer
    un rush que l'outil refusera ensuite d'extraire serait promettre ce qu'on
    ne tient pas.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata, "probe_media", probe_sans_corroboration
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )
    assert refus.motif == declaration_de_rush.MOTIF_SOURCE_NON_QUALIFIEE


def test_A4_volet_symetrique_le_meme_rush_passe_quand_la_cadence_est_lisible(
    tmp_path,
):
    """Sans ce volet, les deux refus ci-dessus pourraient venir du fichier."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert issue.fps_source == 25.0


def test_A4_la_table_des_codes_de_sortie_est_lue_jamais_recopiee():
    """AC 2.2 en amont : le coeur publie la table, l'enveloppe la lira.

    `ffprobe` absent n'est **pas** un des cinq refus metier -- c'est un
    prerequis externe manquant, et il porte le meme code `2` que dans
    `extraction.CODES_DE_SORTIE`. La table le dit ; personne ne le redige.
    """
    table = dict(declaration_de_rush.CODES_DE_SORTIE)
    assert table[declaration_de_rush.RefusDeDeclaration] == (
        declaration_de_rush.CODE_ERREUR
    )
    assert table[video_metadata.FfprobeNotFoundError] == (
        declaration_de_rush.CODE_PREREQUIS_ABSENT
    )
    assert declaration_de_rush.CODE_PREREQUIS_ABSENT == (
        extraction.CODE_PREREQUIS_ABSENT
    )
    assert declaration_de_rush.CODE_ERREUR == extraction.CODE_ERREUR

    refus = declaration_de_rush.RefusDeDeclaration(
        "peu importe",
        motif=declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE,
        issues=("relire",),
    )
    assert declaration_de_rush.code_de_sortie(refus) == 1
    assert (
        declaration_de_rush.code_de_sortie(
            video_metadata.FfprobeNotFoundError("absent")
        )
        == 2
    )
    assert declaration_de_rush.code_de_sortie(ValueError("inconnue")) is None


def test_A4_ffprobe_absent_est_un_prerequis_nomme_jamais_une_trace_nue(tmp_path):
    """La seule dependance externe du lot A reste **nommee** quand elle manque."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    with pytest.raises(video_metadata.FfprobeNotFoundError) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=video,
            logger=JournalMuet(),
            ffprobe_binary=FFPROBE_ABSENT,
        )
    assert FFPROBE_ABSENT in str(capture.value)
    assert declaration_de_rush.code_de_sortie(capture.value) == 2


def test_A4_REFUS_DU_COEUR_couvre_tout_ce_que_le_coeur_leve(tmp_path, monkeypatch):
    """Le tuple publie attrape les cinq refus, et il est **lu** par la table."""
    motifs = cinq_refus(tmp_path, monkeypatch)
    assert len(motifs) == 5
    assert declaration_de_rush.RefusDeDeclaration in (
        declaration_de_rush.REFUS_DU_COEUR
    )
    assert set(declaration_de_rush.REFUS_DU_COEUR) <= {
        classe for classe, _ in declaration_de_rush.CODES_DE_SORTIE
    }


# ---------------------------------------------------------------------------
# A5 -- le refus SEC et son volet symetrique
# ---------------------------------------------------------------------------


def test_A5_un_rush_deja_declare_est_un_refus_a_TROIS_issues(tmp_path):
    """`EPIC11-ARB-231` (Egan, 2026-09-05, verbatim : « Une 3e sortie sur
    l'ecran ») : relinker, declarer separement, annuler.

    **Ce test disait l'inverse jusqu'au 2026-09-05.** Il mesurait
    `len(refus.issues) == 1`, sur la foi d'`EPIC11-ARB-147` (« refus SEC, une
    seule issue »), et il a ete ecrit par ce banc a l'AC 1.7. `EPIC11-ARB-231`
    **supersede `ARB-147` sur ce point precis** -- il tient sur tout le reste,
    rien n'est ecrit et rien n'est modifie. Le motif qu'`ARB-147` invoquait --
    « choisir entre deux facons de ne rien faire » -- est tombe avec
    `EPIC11-ARB-230` : deux des trois issues FONT quelque chose.

    L'AC 1.7 de la fiche porte encore « une seule issue » : l'ecart est
    **nomme** au registre de la story, une AC ne se reecrit pas pour absorber
    un arbitrage.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert len(refus.issues) == 3
    assert refus.issues == declaration_de_rush.ISSUES_PAR_MOTIF[refus.motif]
    # Les trois sorties d'`EPIC11-ARB-231`, dans l'ordre : l'ordre porte la
    # recommandation, et un ensemble ne le mesurerait pas.
    assert "relink" in refus.issues[0]
    assert "--force-distinct" in refus.issues[1]
    assert "annuler" in refus.issues[2].lower()


def test_A5_le_refus_ne_propose_aucune_issue_DESTRUCTRICE(tmp_path):
    """Volet symetrique du precedent, et c'est le critere d'`EPIC11-ARB-89`.

    **Ce test mesurait `"--" not in message` jusqu'au 2026-09-05**, sur la foi
    du refus sec. `EPIC11-ARB-232` exige desormais le contraire :
    `--force-distinct` doit etre **cite dans le message de refus**. Ce qui
    reste vrai, et qui est ce qu'`ARB-89` gouverne reellement, c'est
    qu'**aucune issue ne detruit** : `--force-distinct` ajoute une seconde
    entree, il n'ecrase pas la premiere -- et l'arbitrage a ecarte
    `--overwrite` nommement pour cette raison.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )
    message = str(refus)
    assert "--force-distinct" in message, message
    for mot in ("ecraser", "ecrasement", "--nouvelle-version", "--overwrite",
                "--ecrasement-conscient", "--force "):
        assert mot not in message.lower(), message
    for issue in refus.issues:
        for mot in ("ecraser", "--overwrite", "--nouvelle-version"):
            assert mot not in issue.lower(), issue


def test_A5_volet_symetrique_un_rush_juge_DISTINCT_ne_refuse_JAMAIS(tmp_path):
    """Le cas qui ressemblait a un conflit **est un succes** (`EPIC11-ARB-9`).

    Sans ce volet, le refus sec pourrait avaler le cas multicamera nominal --
    deux fichiers homonymes venus de deux endroits differents -- et le banc
    resterait vert.

    **Le critere d'identite est tranche depuis `EPIC11-ARB-230`** : les deux
    sources divergent par leur DUREE (125 frames contre 50), qui en est un.
    Deux resolutions differentes ne suffiraient plus -- la resolution n'entre
    pas dans l'identite d'un rush, et c'est ce que ce test mesurait avant le
    2026-09-05 sans que rien ne le dise.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)

    premier = copie_du_rush(tmp_path / "tournage-mai" / "hd", "prise01.mov")
    second = copie_du_rush(
        tmp_path / "tournage-juin" / "sd", "prise01.mov", RUSH_REEL_AUTRE_DUREE
    )

    un = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=premier, logger=JournalMuet()
    )
    deux = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=second, logger=JournalMuet()
    )

    assert deux.homonymie_levee is True
    assert {rush["rush_id"] for rush in rushes_du_manifeste(manifeste)} == {
        un.rush_id, deux.rush_id
    }
    # Les deux rushes sont bien DISTINCTS : chacun porte sa propre resolution,
    # donc aucun n'a ecrase l'autre.
    # Les deux rushes sont bien DISTINCTS : chacun porte sa propre duree, qui
    # est le critere sur lequel le coeur les a separes.
    a = entree_du_rush(manifeste, un.rush_id)["source_frame_count"]
    b = entree_du_rush(manifeste, deux.rush_id)["source_frame_count"]
    assert (a, b) == (125, 50)
    # Et la separation est un SUCCES constate, pas un forcage de l'operateur.
    assert deux.separation_forcee is False


def test_A5_le_refus_sec_ne_mord_que_le_rush_juge_IDENTIQUE(tmp_path):
    """Redeclarer **le meme fichier au meme endroit** : refus sec.

    Les quatre criteres d'`EPIC11-ARB-230` coincident trivialement -- c'est le
    meme fichier au meme endroit --, et c'est le seul refus qui reste **bon
    marche** : aucune mesure ne pourrait le renverser.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    premier = copie_du_rush(tmp_path / "tournage-mai" / "hd", "prise01.mov")
    second = copie_du_rush(
        tmp_path / "tournage-juin" / "sd", "prise01.mov", RUSH_REEL_AUTRE_DUREE
    )

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=premier, logger=JournalMuet()
    )
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=second, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=second, logger=JournalMuet()
        )
    )
    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE


def test_A5_chaque_motif_publie_a_ses_issues_et_elles_sont_non_vides():
    """`ISSUES_PAR_MOTIF` couvre EXACTEMENT les motifs publies."""
    assert set(declaration_de_rush.ISSUES_PAR_MOTIF) == set(
        declaration_de_rush.MOTIFS_DE_REFUS
    )
    for motif, issues in declaration_de_rush.ISSUES_PAR_MOTIF.items():
        assert issues, motif
        assert all(isinstance(issue, str) and issue for issue in issues), motif


# ---------------------------------------------------------------------------
# A6 -- l'ordre des gardes et les mesures d'ecriture
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cas",
    ["projet_sans_manifeste", "fichier_introuvable", "chemin_non_fichier",
     "rush_deja_declare"],
)
def test_A6_les_gardes_bon_marche_precedent_toutes_le_probe(tmp_path, cas):
    """AC 1.8, mesure d'**ordre** sans un seul sous-processus.

    On passe un binaire ffprobe qui n'existe pas. Si une garde bon marche ne
    precedait pas le probe, l'exception rendue serait `FfprobeNotFoundError`
    et non le refus nomme -- c'est le meme geste que la section `V1.1` de la
    story 11.4c.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    if cas == "rush_deja_declare":
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )

    cibles = {
        "projet_sans_manifeste": (tmp_path / "projet-absent", video),
        "fichier_introuvable": (projet, tmp_path / "A-CAM" / "jamais-vu.mov"),
        "chemin_non_fichier": (projet, tmp_path / "A-CAM"),
        "rush_deja_declare": (projet, video),
    }
    dossier, chemin = cibles[cas]

    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=dossier,
            video_path=chemin,
            logger=JournalMuet(),
            ffprobe_binary=FFPROBE_ABSENT,
        )
    )
    assert refus.motif == cas


def test_A6_volet_symetrique_le_binaire_absent_mord_bien_quand_on_l_atteint(
    tmp_path,
):
    """Sans ce volet, les quatre verts ci-dessus seraient vrais par vacuite."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    with pytest.raises(video_metadata.FfprobeNotFoundError):
        declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=video,
            logger=JournalMuet(),
            ffprobe_binary=FFPROBE_ABSENT,
        )


def test_A6_l_ordre_des_trois_etapes_est_mesure_par_sondes_horodatees(tmp_path):
    """AC 1.8 : gardes bon marche, **puis** probe, **puis** ecriture.

    Trois sondes posees sur le module lui-meme, jamais une lecture du code : ce
    qui est mesure est l'ordre des appels reels.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    horodatages: dict[str, int] = {}

    def sonde(nom, fonction):
        def enveloppe(*args, **kwargs):
            horodatages[nom] = time.perf_counter_ns()
            return fonction(*args, **kwargs)

        return enveloppe

    originaux = {
        "gardes": declaration_de_rush._gardes_bon_marche,
        "probe": declaration_de_rush._qualifier_la_source,
        "ecriture": declaration_de_rush.persist_rush_declaration,
    }
    for nom, fonction in originaux.items():
        cible = {
            "gardes": "_gardes_bon_marche",
            "probe": "_qualifier_la_source",
            "ecriture": "persist_rush_declaration",
        }[nom]
        setattr(declaration_de_rush, cible, sonde(nom, fonction))
    try:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    finally:
        for nom, fonction in originaux.items():
            cible = {
                "gardes": "_gardes_bon_marche",
                "probe": "_qualifier_la_source",
                "ecriture": "persist_rush_declaration",
            }[nom]
            setattr(declaration_de_rush, cible, fonction)

    assert set(horodatages) == {"gardes", "probe", "ecriture"}
    assert horodatages["gardes"] < horodatages["probe"] < horodatages["ecriture"]


def test_A6_un_refus_de_source_n_atteint_jamais_l_ecriture(tmp_path):
    """AC 1.8 : le probe precede l'ecriture, mesure par l'absence de l'appel."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    pas_une_video = fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM")

    appels: list[str] = []
    original = declaration_de_rush.persist_rush_declaration

    def espion(*args, **kwargs):
        appels.append("ecriture")
        return original(*args, **kwargs)

    declaration_de_rush.persist_rush_declaration = espion
    try:
        with pytest.raises(declaration_de_rush.RefusDeDeclaration):
            declaration_de_rush.declarer_un_rush(
                project_dir=projet, video_path=pas_une_video, logger=JournalMuet()
            )
    finally:
        declaration_de_rush.persist_rush_declaration = original

    assert appels == []


@pytest.mark.parametrize(
    "cas",
    ["fichier_introuvable", "chemin_non_fichier", "source_non_qualifiee",
     "rush_deja_declare"],
)
def test_A6_aucun_refus_n_ecrit_le_manifeste(tmp_path, cas):
    """AC 1.9, mesure aux **inodes**, au `st_mtime_ns` et par un **temoin**.

    Jamais par un condensat : la fabrique est deterministe, donc une reecriture
    rendrait exactement les memes octets.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    if cas == "rush_deja_declare":
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )

    cibles = {
        "fichier_introuvable": tmp_path / "A-CAM" / "jamais-vu.mov",
        "chemin_non_fichier": tmp_path / "A-CAM",
        "source_non_qualifiee": fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM"),
        "rush_deja_declare": video,
    }

    temoin = Temoin(manifeste)
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=cibles[cas], logger=JournalMuet()
        )
    )
    assert refus.motif == cas
    assert temoin.intact()


def test_A6_volet_symetrique_un_succes_change_bien_le_manifeste(tmp_path):
    """Sans ce volet, la mesure precedente serait verte sur un chemin mort."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    temoin = Temoin(manifeste)
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert not temoin.intact()
    # Et l'ecriture est bien atomique : l'inode change (temporaire + replace),
    # aucun temporaire ne reste.
    assert manifeste.stat().st_ino != temoin.inode
    restes = [
        chemin.name
        for chemin in projet.iterdir()
        if chemin.name.startswith(f".{MANIFEST_FILENAME}")
    ]
    assert restes == []


def test_A6_un_manifeste_illisible_refuse_sans_rien_ecrire(tmp_path):
    """Un `project.json` tronque ne remonte jamais en trace JSON nue."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    manifeste.write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    temoin = Temoin(manifeste)
    with pytest.raises(Exception) as capture:
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    assert not isinstance(capture.value, json.JSONDecodeError)
    assert temoin.intact()


# ---------------------------------------------------------------------------
# Fermeture des survivants de la campagne de mutation du lot A
#
# Trois mutants sur trente ont survecu au banc ci-dessus. Chacun ferme un trou
# de mesure reel, et chacun a ete **reinjecte** pour verifier que le test ecrit
# ici le fait rougir (`politique-revue-et-mutation-testing.md`, section 6.2 :
# un finding n'est clos que si son mutant, remis en place, rougit).
# ---------------------------------------------------------------------------


def test_M01_un_projet_ABSENT_et_un_projet_ILLISIBLE_ne_disent_pas_la_meme_chose(
    tmp_path,
):
    """Survivant `M01` : la garde `is_file()` retiree laissait le meme motif.

    En retirant `if not manifest_path.is_file()`, `load_manifest` echoue sur le
    fichier absent et le refus retombe -- avec le **meme motif** -- dans la
    branche « manifeste illisible ». Le motif ne suffit donc pas a mesurer
    cette garde : ce qui change est ce que l'operateur lit. « Aucun projet
    ouvert ici » et « restaurer une copie saine du project.json » sont deux
    consignes differentes, et la seconde envoie chercher un fichier a reparer
    la ou il n'y en a jamais eu.
    """
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    sans_projet = tmp_path / "pas-un-projet"
    sans_projet.mkdir()
    absent = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=sans_projet, video_path=video, logger=JournalMuet()
        )
    )

    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    manifeste.write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    illisible = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )

    assert absent.motif == illisible.motif == (
        declaration_de_rush.MOTIF_PROJET_SANS_MANIFESTE
    )
    assert str(absent) != str(illisible)
    assert "n'y porte pas de" in str(absent)
    assert "restaurer" not in str(absent).lower()
    # Volet symetrique : le refus du manifeste illisible, lui, DOIT le dire.
    assert "restaurer" in str(illisible).lower()


def probe_avec_timecode(*args, **kwargs):
    """Un probe qui porte un timecode de depart, ce que les fixtures n'ont pas.

    Les quatre rushes de `tests/fixtures/rushes/` sont des `testsrc` sans piste
    `tmcd` : aucun d'eux ne porte de timecode de depart. C'est ce qui a fait
    survivre le mutant `M19` -- un champ toujours absent est indiscernable d'un
    champ jamais ecrit.
    """
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "25/1",
                "avg_frame_rate": "25/1",
                "duration": "5.0",
                "nb_frames": "125",
            },
            {
                "codec_type": "data",
                "codec_tag_string": "tmcd",
                "tags": {"timecode": "10:00:00:00"},
            },
        ],
        "format": {},
    }


def test_M19_le_timecode_de_depart_atteint_le_manifeste(tmp_path, monkeypatch):
    """Survivant `M19` : `source_start_timecode` n'etait mesure sur aucun rush.

    Le timecode de depart voyage jusqu'aux noms de fichiers et au payload QR :
    le perdre au moment de la declaration produirait, apres extraction, une
    entree de rush muette la ou la source parle.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata, "probe_media", probe_avec_timecode
    )
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert entree_du_rush(manifeste, "prise01")["source_start_timecode"] == (
        "10:00:00:00"
    )


def test_M19_volet_symetrique_une_source_sans_timecode_omet_le_champ(tmp_path):
    """L'absence est encodee **positivement** : le champ est omis, jamais `null`."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert "source_start_timecode" not in entree_du_rush(manifeste, "prise01")


def test_M28_la_fusion_met_a_jour_EN_PLACE_et_ne_duplique_jamais():
    """Survivant `M28` : `break` -> `continue` ajoutait un doublon, sans etre vu.

    La branche de mise a jour en place de `build_rush_declaration_manifest`
    n'est **jamais atteinte** par `declarer_un_rush` -- le refus sec
    d'`EPIC11-ARB-147` tombe avant. Elle appartient pourtant au contrat de la
    fonction publiee, au meme titre que celle de `build_extraction_manifest`,
    et personne ne la mesurait : un `break` mue en `continue` laissait le banc
    entierement vert tout en ecrivant **deux** entrees pour le meme `rush_id`.

    La cible est en **deuxieme position sur trois** dans la liste que la
    fonction parcourt : ni premiere -- un `find` qui rend toujours le premier
    element se demasque --, ni derniere -- une terminaison de boucle fautive se
    demasque (point 2 bis du 2026-08-30).
    """
    from mixed_media_utility.io.extraction_manifest import (
        RushRecord,
        build_rush_declaration_manifest,
    )

    existant = {
        "schema_version": "2.1",
        "project_id": "projet-a",
        "created": "2026-09-01T00:00:00Z",
        "rushes": [dict(rush) for rush in TROIS_RUSHES],
        "lots": [],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }
    assert existant["rushes"][INDEX_DE_LA_CIBLE]["rush_id"] == "cible"

    record = RushRecord(
        rush_id="cible",
        source_name="cible.mov",
        fps_source=50.0,
        source_width=4096,
        source_height=2160,
        source_fields={},
        source_parent="A-CAM",
    )
    fusionne = build_rush_declaration_manifest(existant, "projet-a", record)
    rushes = fusionne["rushes"]

    assert [rush["rush_id"] for rush in rushes] == ["avant", "cible", "apres"]
    assert rushes[INDEX_DE_LA_CIBLE]["fps_source"] == 50.0
    assert rushes[INDEX_DE_LA_CIBLE]["resolution_source"] == {
        "width": 4096,
        "height": 2160,
    }
    # Les deux voisins sont intacts, valeur pour valeur : la fusion est sans
    # perte et ne touche qu'une entree.
    assert rushes[0] == TROIS_RUSHES[0]
    assert rushes[2] == TROIS_RUSHES[2]
    # Et `lots[]` n'a pas bouge : declarer n'extrait pas.
    assert fusionne["lots"] == []


def test_M28_volet_symetrique_un_rush_INCONNU_est_bien_ajoute_en_queue():
    """Sans ce volet, la mesure precedente serait verte sur une fonction qui
    n'ajouterait plus jamais rien."""
    from mixed_media_utility.io.extraction_manifest import (
        RushRecord,
        build_rush_declaration_manifest,
    )

    existant = {
        "schema_version": "2.1",
        "project_id": "projet-a",
        "created": "2026-09-01T00:00:00Z",
        "rushes": [dict(rush) for rush in TROIS_RUSHES],
        "lots": [],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }
    record = RushRecord(
        rush_id="neuf",
        source_name="neuf.mov",
        fps_source=48.0,
        source_width=1920,
        source_height=1080,
        source_fields={},
    )
    rushes = build_rush_declaration_manifest(existant, "projet-a", record)["rushes"]
    assert [rush["rush_id"] for rush in rushes] == [
        "avant", "cible", "apres", "neuf"
    ]


def test_A3_le_project_id_du_manifeste_fait_foi_meme_si_le_dossier_est_renomme(
    tmp_path,
):
    """Declarer un rush ne rebaptise **jamais** un projet.

    Le `project_id` est celui que le manifeste porte, verbatim -- y compris
    quand le dossier a ete renomme depuis. `run_extraction`, lui, le DERIVE du
    nom du dossier et refuse quand les deux divergent : appliquer la meme regle
    ici rendrait un projet indeclrable apres un simple renommage de dossier,
    alors qu'aucune identite n'est en jeu -- on ajoute une entree, on n'ecrit
    pas une identite de projet.
    """
    projet = tmp_path / "dossier-renomme-depuis"
    manifeste = manifeste_vierge(projet, project_id="identite-d-origine")
    video = copie_du_rush(tmp_path / "quelque-part", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    ecrit = json.loads(manifeste.read_text(encoding="utf-8"))
    assert ecrit["project_id"] == "identite-d-origine"


def test_A3_volet_symetrique_un_manifeste_MUET_derive_le_project_id_du_dossier(
    tmp_path,
):
    """Le repli, et il est mesure : sans lui la branche serait morte.

    Un manifeste ancien qui ne porterait pas `project_id` -- le schema l'exige
    a l'ecriture, jamais a la lecture -- doit quand meme pouvoir recevoir un
    rush. La derivation est alors celle du coeur, appelee et non recopiee,
    exactement comme dans `run_extraction`.
    """
    projet = tmp_path / "projet-sans-identite"
    manifeste = manifeste_vierge(projet)
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    del contenu["project_id"]
    manifeste.write_text(json.dumps(contenu, indent=2), encoding="utf-8")

    video = copie_du_rush(tmp_path / "quelque-part", "prise01.mov")
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    ecrit = json.loads(manifeste.read_text(encoding="utf-8"))
    assert ecrit["project_id"] == naming.normalize_identifier(
        projet.name, label="le nom du dossier projet"
    )


# ---------------------------------------------------------------------------
# LIAISON du 2026-09-05 -- la duree, critere d'identite depuis `d244c307`
# ---------------------------------------------------------------------------
#
# Ces quatre tests n'existaient pas sur la branche d'origine du lot A, et ils
# ne pouvaient pas y exister : `_build_rush_entry` n'ecrivait pas encore le
# cardinal source. Le commit `d244c307` (note 5 de la relecture d'Egan du
# 2026-09-01) en a fait un critere d'identite du rush, stocke sur l'entree
# PRECISEMENT pour qu'un rush declare et pas encore extrait le porte.
#
# La liaison a donc du trancher ce que la declaration ecrit, elle qui ne paie
# jamais `-count_frames` (AC 1.5 : un seul `ffprobe`). La regle retenue, et ces
# tests la tiennent : **le cardinal ne s'ecrit que corrobore, et il s'omet
# sinon**. Ecrire une estimation la ferait diverger du comptage exact qu'une
# extraction ulterieure poserait, c'est-a-dire fabriquer un faux conflit
# d'identite sur le critere que la note 5 vient d'ajouter.


def _probe(*, nb_frames: str | None, duration: str | None):
    """Un probe de synthese dont on choisit la duree et le cardinal declares.

    Les quatre rushes de `tests/fixtures/rushes/` corroborent tous leur
    `nb_frames` : aucun d'eux ne peut mesurer le regime NON corrobore, qui est
    justement celui ou la declaration doit se taire. Meme motif que
    `probe_avec_timecode`, pose pour le survivant `M19`.
    """
    flux = {
        "codec_type": "video",
        "codec_name": "h264",
        "pix_fmt": "yuv420p",
        "width": 1920,
        "height": 1080,
        "r_frame_rate": "25/1",
        "avg_frame_rate": "25/1",
    }
    if duration is not None:
        flux["duration"] = duration
    if nb_frames is not None:
        flux["nb_frames"] = nb_frames
    return lambda *args, **kwargs: {"streams": [flux], "format": {}}


def test_L1_une_duree_CORROBOREE_atteint_le_manifeste(tmp_path, monkeypatch):
    """Le cardinal declare et confirme par la duree est ecrit, et dit exact."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata,
        "probe_media",
        _probe(nb_frames="125", duration="5.0"),
    )
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    entree = entree_du_rush(manifeste, "prise01")
    assert entree["source_frame_count"] == 125
    assert entree["source_frame_count_is_exact"] is True


@pytest.mark.parametrize(
    "nb_frames, duration, cas",
    [
        ("999", "5.0", "les deux se contredisent de plus d'une frame"),
        (None, "5.0", "aucun nb_frames declare"),
        ("125", None, "aucune duree de flux pour corroborer"),
    ],
)
def test_L1_volet_symetrique_une_duree_NON_corroboree_OMET_les_deux_champs(
    tmp_path, monkeypatch, nb_frames, duration, cas
):
    """L'absence est encodee **positivement** : omission, jamais `0`.

    Trois regimes distincts de non-corroboration, et aucun ne doit ecrire. Un
    `int(... or 0)` defensif affirmerait un flux vide ; une estimation ecrite
    sans le dire ferait diverger la declaration du comptage exact d'une
    extraction ulterieure.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata,
        "probe_media",
        _probe(nb_frames=nb_frames, duration=duration),
    )
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    entree = entree_du_rush(manifeste, "prise01")
    assert "source_frame_count" not in entree, cas
    assert "source_frame_count_is_exact" not in entree, cas


@pytest.mark.parametrize(
    "nb_frames, duration", [("125", "5.0"), ("999", "5.0"), (None, "5.0")]
)
def test_L2_le_drapeau_d_exactitude_ne_voyage_JAMAIS_seul(
    tmp_path, monkeypatch, nb_frames, duration
):
    """Les deux champs sont presents ensemble, ou absents ensemble.

    Frontiere de COMPOSITION : chacune des deux mesures precedentes reste verte
    si l'on n'ecrit qu'un des deux champs. Un
    `source_frame_count_is_exact` seul ne qualifie rien, et un cardinal sans son
    drapeau ferait passer une estimation pour un comptage.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    monkeypatch.setattr(
        declaration_de_rush.video_metadata,
        "probe_media",
        _probe(nb_frames=nb_frames, duration=duration),
    )
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    entree = entree_du_rush(manifeste, "prise01")
    assert ("source_frame_count" in entree) == (
        "source_frame_count_is_exact" in entree
    )


def test_L4_le_critere_de_corroboration_est_LU_du_coeur_jamais_recopie(tmp_path):
    """`cardinal_corrobore` a **une seule** redaction dans le depot.

    Frontiere negative, doublee de son volet symetrique : le module de
    declaration n'ecrit nulle part le « a une frame pres », et
    `resolve_source_frame_count` -- l'autre appelant, celui qui a le droit de
    payer un `-count_frames` -- passe par la meme fonction. Deux redactions
    divergeraient, et l'ecart ne se verrait que sur un manifeste deja ecrit.
    """
    source = Path(declaration_de_rush.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    appels = {
        noeud.func.id
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
    }
    assert "cardinal_corrobore" in appels

    # Le critere lui-meme n'est pas ici : aucune comparaison de la duree au
    # cardinal, aucune tolerance recopiee.
    assert "limit_denominator" not in source
    assert "<= 1" not in source

    # Volet symetrique : l'autre appelant du coeur lit la MEME fonction.
    coeur = Path(extraction.__file__).read_text(encoding="utf-8")
    corps = next(
        noeud
        for noeud in ast.walk(ast.parse(coeur))
        if isinstance(noeud, ast.FunctionDef)
        and noeud.name == "resolve_source_frame_count"
    )
    appels_du_coeur = {
        n.func.id
        for n in ast.walk(corps)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "cardinal_corrobore" in appels_du_coeur


# ---------------------------------------------------------------------------
# C1 -- les DEUX temps de la declaration (dette `C-1`, `EPIC11-ARB-4`)
# ---------------------------------------------------------------------------
#
# `EPIC11-ARB-4` est verbatim « obligatoire pour toute commande qui ecrit », et
# une declaration ecrit `project.json`. L'ecran `Ajouter un rush` doit donc
# montrer un panneau **chiffre** -- resolution, cadence, cardinal de frames --
# avant que l'operateur valide, et ces chiffres n'existent qu'apres le probe.
# La coupure se fait ENTRE l'etape 2 et l'etape 3, jamais ailleurs
# (`EPIC5-ARB-34`).
#
# Ce que ces tests mesurent, et qu'aucune relecture ne verrait : que le temps 1
# ne touche AUCUN octet, que le probe reste paye **une seule fois pour les deux
# temps** (AC 1.5), et que `declarer_un_rush` est **exactement** la composition
# -- la seule facon de savoir que la CLI et l'ecran ecriront la meme chose.


#: Un probe de synthese parametre. Le meme geste que la section `L4` : les
#: rushes reels du depot corroborent tous leur `nb_frames`, donc le regime
#: « cardinal non corrobore » ne se mesure que sur une source fabriquee.
def probe_parametre(*, nb_frames=None, duree=None, fps="25/1",
                    largeur=1920, hauteur=1080, timecode=None):
    flux = {
        "codec_type": "video",
        "width": largeur,
        "height": hauteur,
        "r_frame_rate": fps,
        "avg_frame_rate": fps,
    }
    if nb_frames is not None:
        flux["nb_frames"] = str(nb_frames)
    if duree is not None:
        flux["duration"] = str(duree)
    if timecode is not None:
        flux["tags"] = {"timecode": timecode}

    def probe(*args, **kwargs):
        return {"streams": [flux], "format": {}}

    return probe


def test_C1_preparer_une_declaration_ne_touche_AUCUN_octet_du_projet(tmp_path):
    """Temps 1 : gardes et probe, **rien d'ecrit** (`EPIC11-ARB-4`).

    Mesure aux **inodes**, au `st_mtime_ns` et par un temoin depose -- jamais
    par un condensat, qu'une reecriture identique laisserait vert. C'est le
    geste exact de la section `A6`, applique au point d'entree neuf.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    temoin = Temoin(manifeste)

    preparee = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert temoin.intact(), "le temps 1 a touche le projet"
    assert rushes_du_manifeste(manifeste) == []
    assert preparee.rush_id == "prise01"


def test_C1_volet_symetrique_le_temps_2_ecrit_bien(tmp_path):
    """Sans ce volet, le test precedent serait vrai d'un temps 1 qui ne fait
    rien du tout -- et d'un temps 2 qui n'ecrirait rien non plus."""
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    temoin = Temoin(manifeste)

    preparee = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    issue = declaration_de_rush.ecrire_la_declaration(
        preparee, logger=JournalMuet()
    )

    assert not temoin.intact()
    assert [rush["rush_id"] for rush in rushes_du_manifeste(manifeste)] == [
        "prise01"
    ]
    assert issue.rush_id == "prise01"


def test_C1_la_preparation_porte_les_CHIFFRES_que_le_panneau_exige(tmp_path):
    """AC 3.3 : le `rush_id` propose, le chemin retenu, la cadence source et le
    cardinal de frames **mesures par le probe**, plus la resolution que la
    maquette `E2-1e` dessine (`1920 x 1080`).

    Les valeurs sont confrontees au rush REEL du depot, pas a une fabrique :
    une mesure de synthese mesure la synthese (`CLAUDE.md`, 2026-09-02).
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    preparee = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert preparee.rush_id == "prise01"
    assert preparee.rush_id_derive == "prise01"
    assert preparee.homonymie_levee is False
    assert preparee.source_name == "prise01.mov"
    assert preparee.source_path == str(video.resolve())
    assert preparee.source_parent == "A-CAM"
    assert preparee.fps_source == 25.0
    assert (preparee.source_width, preparee.source_height) == (1920, 1080)
    assert preparee.cardinal_de_frames == 125
    assert preparee.manifest_path == projet / MANIFEST_FILENAME
    assert preparee.project_id == "projet-a"

    # **Aucune ligne de cout disque** : une declaration n'ecrit aucune image, et
    # un champ de cout a `0` serait un chiffre faux (`DESIGN.md` §3, AC 3.3).
    champs = {champ.name for champ in dataclasses.fields(preparee)}
    assert not any("cout" in nom or "disque" in nom or "octets" in nom
                   for nom in champs), champs


def test_C1_un_cardinal_NON_corrobore_vaut_None_et_JAMAIS_zero(
    tmp_path, monkeypatch
):
    """`DESIGN.md` §3 : un champ non mesure est **omis**, jamais rendu `0`.

    Le panneau chiffre est ce qui rend ce point observable : l'ecran doit
    pouvoir distinguer « 125 frames » de « on ne sait pas », et un `0` les
    confondrait. C'est le second etat de la ligne `Resolution` de `E2-1e`, que
    la dette `C-3` signale comme non dessine.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    # Cadence annoncee et duree declaree -- donc corroborable --, mais un
    # `nb_frames` qui contredit la duree : le cardinal n'est pas corrobore.
    monkeypatch.setattr(
        video_metadata, "probe_media",
        probe_parametre(nb_frames=9999, duree=5.0),
    )
    preparee = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert preparee.cardinal_de_frames is None

    # Volet symetrique : la MEME fabrique, un `nb_frames` que la duree
    # corrobore, et le cardinal sort.
    monkeypatch.setattr(
        video_metadata, "probe_media",
        probe_parametre(nb_frames=125, duree=5.0),
    )
    corroboree = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert corroboree.cardinal_de_frames == 125


def test_C1_la_DUREE_survit_a_l_absence_du_cardinal(tmp_path, monkeypatch):
    """La duree ne suit PAS le sort du cardinal, et c'est ce qui tient `E2-1i`.

    Le point est logique avant d'etre un affichage : la duree du flux est la
    grandeur qui sert a **tenter** la corroboration du cardinal
    (`extraction.cardinal_corrobore` la lit), donc elle est necessairement
    connue a l'instant meme ou la corroboration echoue. Un champ qui
    disparaitrait avec le cardinal serait un champ qui s'efface au seul moment
    ou on en a besoin.

    Les deux cas sont joues sur la MEME fabrique, et les deux durees
    **different** (5,0 s contre 12,0 s) : deux valeurs egales rendraient ce
    banc vert meme si la duree etait recopiee d'ailleurs.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    # Cardinal NON corrobore -- et la duree, elle, est bien la.
    monkeypatch.setattr(
        video_metadata, "probe_media",
        probe_parametre(nb_frames=9999, duree=5.0),
    )
    sans_cardinal = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert sans_cardinal.cardinal_de_frames is None
    assert sans_cardinal.duree_source_secondes == 5.0

    # Volet symetrique : cardinal corrobore, AUTRE duree. Le champ suit le
    # probe et non une constante.
    monkeypatch.setattr(
        video_metadata, "probe_media",
        probe_parametre(nb_frames=300, duree=12.0),
    )
    avec_cardinal = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    assert avec_cardinal.cardinal_de_frames == 300
    assert avec_cardinal.duree_source_secondes == 12.0


def test_C1_ffprobe_est_appele_UNE_seule_fois_pour_les_DEUX_temps(tmp_path):
    """AC 1.5, et c'est tout le motif du decoupage.

    Les deux contournements que le lot C a nommes plutot que d'en prendre un
    etaient un second `ffprobe` depuis la TUI et une seconde redaction de la
    qualification dans `tui/`. Ce test mesure que le premier est inutile : les
    chiffres du panneau viennent du **meme** probe que l'ecriture.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    appels: list[tuple] = []
    original = video_metadata.probe_media

    def compteur(*args, **kwargs):
        appels.append((args, kwargs))
        return original(*args, **kwargs)

    video_metadata.probe_media = compteur
    try:
        preparee = declaration_de_rush.preparer_une_declaration(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
        declaration_de_rush.ecrire_la_declaration(preparee, logger=JournalMuet())
    finally:
        video_metadata.probe_media = original

    assert len(appels) == 1, appels

    # Volet symetrique : le compteur voit bien ce qu'il compte.
    assert appels[0][0][0] == str(video)


def test_C1_declarer_un_rush_est_EXACTEMENT_la_composition_des_deux_temps(
    tmp_path,
):
    """Le contrat du point d'entree historique n'a pas bouge (dette `C-1`).

    Deux projets jumeaux, le meme rush : l'un declare en un appel, l'autre en
    deux temps. Les entrees `rushes[]` doivent etre **egales**, sans quoi la
    CLI et l'ecran ecriraient deux choses differentes -- et l'ecart ne se
    verrait que sur un manifeste.
    """
    en_un_temps = tmp_path / "un-temps"
    en_deux_temps = tmp_path / "deux-temps"
    manifeste_a = manifeste_vierge(en_un_temps, "projet-jumeau")
    manifeste_b = manifeste_vierge(en_deux_temps, "projet-jumeau")
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    direct = declaration_de_rush.declarer_un_rush(
        project_dir=en_un_temps, video_path=video, logger=JournalMuet()
    )
    compose = declaration_de_rush.ecrire_la_declaration(
        declaration_de_rush.preparer_une_declaration(
            project_dir=en_deux_temps, video_path=video, logger=JournalMuet()
        ),
        logger=JournalMuet(),
    )

    assert rushes_du_manifeste(manifeste_a) == rushes_du_manifeste(manifeste_b)
    assert direct.entree == compose.entree
    for champ in ("rush_id", "rush_id_derive", "homonymie_levee",
                  "source_parent", "source_name", "source_path", "fps_source"):
        assert getattr(direct, champ) == getattr(compose, champ), champ


def test_C1_le_contrat_de_declarer_un_rush_n_a_pas_bouge_d_un_mot_cle():
    """Frontiere d'ensemble EXACT : `mmu project add-rush` l'appelle tel quel.

    Une retouche du banc de comportement d'`add-rush` serait un signal
    d'alarme, pas un ajustement. Ce test rougit avant lui.
    """
    import inspect

    signature = inspect.signature(declaration_de_rush.declarer_un_rush)
    # `force_distinct` est entre le 2026-09-05 (`EPIC11-ARB-232`) : la seconde
    # issue du refus de conflit, portee jusqu'au coeur. Elle vaut `False` par
    # defaut, donc tout appelant d'avant garde son comportement mot pour mot.
    assert set(signature.parameters) == {
        "project_dir", "video_path", "logger", "ffprobe_binary",
        "force_distinct",
    }
    assert signature.parameters["force_distinct"].default is False
    assert all(
        parametre.kind is parametre.KEYWORD_ONLY
        for parametre in signature.parameters.values()
    )

    # Le temps 1 porte le MEME ensemble : un ecran n'a rien de plus a fournir
    # qu'une ligne de commande.
    temps_1 = inspect.signature(declaration_de_rush.preparer_une_declaration)
    assert set(temps_1.parameters) == set(signature.parameters)


@pytest.mark.parametrize(
    "cas",
    ["projet_sans_manifeste", "fichier_introuvable", "chemin_non_fichier",
     "source_non_qualifiee", "rush_deja_declare"],
)
def test_C1_les_CINQ_refus_tombent_au_TEMPS_1(tmp_path, cas):
    """Aucun jugement ne survit au temps 1 : l'ecran les voit tous **avant**
    d'avoir propose quoi que ce soit a l'operateur."""
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    pas_une_video = fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM")

    if cas == "rush_deja_declare":
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )

    cibles = {
        "projet_sans_manifeste": (tmp_path / "projet-absent", video),
        "fichier_introuvable": (projet, tmp_path / "A-CAM" / "jamais-vu.mov"),
        "chemin_non_fichier": (projet, tmp_path / "A-CAM"),
        "source_non_qualifiee": (projet, pas_une_video),
        "rush_deja_declare": (projet, video),
    }
    dossier, chemin = cibles[cas]

    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=dossier, video_path=chemin, logger=JournalMuet()
        )
    )
    assert refus.motif == cas


def test_C1_le_TEMPS_2_ne_porte_AUCUN_jugement(tmp_path):
    """Frontiere negative : pas un `_refus` dans le corps de l'ecriture.

    C'est ce qui donne son sens au panneau. Un refus qui tomberait apres la
    validation de l'operateur serait un refus arrive trop tard -- l'ecran
    aurait promis une ecriture qu'il ne tient pas.
    """
    arbre = arbre_du_module(declaration_de_rush)
    corps = {
        noeud.name: noeud
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.FunctionDef)
    }
    assert "_refus" not in noms_appeles(corps["ecrire_la_declaration"])

    # Volet symetrique, sans lequel le test serait vert sur un detecteur casse :
    # les deux etapes du temps 1 en portent, elles.
    assert "_refus" in noms_appeles(corps["_gardes_bon_marche"])
    assert "_refus" in noms_appeles(corps["_qualifier_la_source"])
    # `_identite_du_rush` s'est scindee le 2026-09-05 (`EPIC11-ARB-230`) : le
    # verdict d'identite ne peut plus tomber avant le probe. Les DEUX moities
    # portent un refus, et les deux sont au temps 1.
    assert "_refus_de_rush_deja_declare" in noms_appeles(
        corps["_identite_provisoire"])
    assert "_refus_de_rush_deja_declare" in noms_appeles(
        corps["_trancher_l_identite"])


def test_C1_la_preparation_porte_le_RECORD_qui_sera_ecrit(tmp_path):
    """`Apercu.manifeste` rend « ce qui sera ecrit » comme un objet et non
    comme une promesse ; `DeclarationPreparee.record` fait de meme.

    Mesure par confrontation a ce qui atterrit reellement au manifeste, jamais
    par relecture du code.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    preparee = declaration_de_rush.preparer_une_declaration(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    record = preparee.record
    declaration_de_rush.ecrire_la_declaration(preparee, logger=JournalMuet())

    entree = entree_du_rush(manifeste, "prise01")
    assert entree["rush_id"] == record.rush_id
    assert entree["source_name"] == record.source_name
    assert entree["source_parent"] == record.source_parent
    assert entree["source_path"] == record.source_path
    assert entree["source_frame_count"] == record.source_frame_count
    assert float(entree["fps_source"]) == float(record.fps_source)


# ---------------------------------------------------------------------------
# C2 -- le refus porte sa PREUVE (dette `C-2`, `EPIC11-ARB-148`)
# ---------------------------------------------------------------------------
#
# `EPIC11-ARB-148` demande qu'un ecran de refus dise **sur quoi** la machine a
# juge deux rushes identiques. `RefusDeDeclaration` ne portait que `motif` et
# `issues` : l'AC 3.6 etait impossible depuis l'exception seule, et la
# contourner en relisant le manifeste depuis la TUI aurait pose une seconde
# source de verite pour la meme comparaison.
#
# **Regle des fabriques, les quatre points.** Le manifeste porte trois rushes
# distinguables (nom, dossier, cadence, duree, timecode) et la cible est placee
# successivement en TETE, au MILIEU et en QUEUE : un balayage qui rendrait
# toujours le premier element, comme un balayage qui sauterait la derniere
# entree, sont deux modes de panne differents et aucun test au milieu ne les
# demasque tous les deux.


#: Trois rushes portant les QUATRE criteres d'identite, tous distincts. La
#: fabrique `TROIS_RUSHES` ne porte ni duree ni timecode : la preuve qu'un
#: ecran doit montrer serait alors partout `None`, et le test resterait vert
#: sur une partition vide.
TROIS_RUSHES_COMPLETS = (
    {"rush_id": "avant", "source_name": "avant.mov", "source_parent": "Z-CAM",
     "source_path": "/rushes/tournage-avril/Z-CAM/avant.mov",
     "fps_source": 24.0, "fps_source_exact": "24/1",
     "source_frame_count": 480, "source_frame_count_is_exact": True,
     "source_start_timecode": "01:00:00:00"},
    {"rush_id": "cible", "source_name": "cible.mov", "source_parent": "A-CAM",
     "source_path": "/rushes/tournage-mai/A-CAM/cible.mov",
     "fps_source": 25.0, "fps_source_exact": "25/1",
     "source_frame_count": 125, "source_frame_count_is_exact": True,
     "source_start_timecode": "02:00:00:00"},
    {"rush_id": "apres", "source_name": "apres.mov", "source_parent": "B-CAM",
     "source_path": "/rushes/tournage-juin/B-CAM/apres.mov",
     "fps_source": 30.0, "fps_source_exact": "30/1",
     "source_frame_count": 900, "source_frame_count_is_exact": True,
     "source_start_timecode": "03:00:00:00"},
)


def _rushes_avec_la_cible_en(position: str):
    """Les trois rushes complets, la cible en tete / au milieu / en queue."""
    cible = next(r for r in TROIS_RUSHES_COMPLETS if r["rush_id"] == "cible")
    autres = [r for r in TROIS_RUSHES_COMPLETS if r["rush_id"] != "cible"]
    return {
        "tete": (cible, *autres),
        "milieu": (autres[0], cible, autres[1]),
        "queue": (*autres, cible),
    }[position]


def _refus_sec_sur(tmp_path, position: str):
    """Declencher le refus sec sur un manifeste ou la cible est a `position`.

    Le fichier designe vit dans `A-CAM`, comme l'entree `cible` : les dossiers
    parents CONCORDENT, donc `EPIC11-ARB-9` ne leve aucune homonymie et le
    refus sec d'`EPIC11-ARB-147` est bien celui qu'on mesure.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_a_trois_rushes(
        projet, rushes=_rushes_avec_la_cible_en(position)
    )
    video = copie_du_rush(tmp_path / "A-CAM", "cible.mov")
    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )
    return refus, manifeste


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_C2_l_entree_bloquante_est_trouvee_a_CHAQUE_position(tmp_path, position):
    """Point 4 de la regle des fabriques : tete **et** queue, pas seulement le
    milieu.

    Un `find` fautif qui rend toujours le premier element se demasque au milieu
    et en queue ; un balayage tronque qui saute la derniere entree ne se
    demasque **qu'**en queue -- c'est le mutant survivant du lot A de la 11.11,
    et il est de la meme famille.
    """
    refus, _ = _refus_sec_sur(tmp_path, position)

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert refus.rush_id == "cible"
    assert refus.entree is not None
    # L'entree rendue est bien **celle qui bloque**, pas une voisine : elle est
    # identifiee par ses valeurs propres, distinctes des deux autres.
    assert refus.entree["rush_id"] == "cible"
    assert refus.entree["source_name"] == "cible.mov"
    assert refus.entree["source_frame_count"] == 125
    assert refus.entree["source_start_timecode"] == "02:00:00:00"
    assert refus.entree["fps_source_exact"] == "25/1"


def test_C2_le_refus_NOMME_le_fichier_designe_jamais_l_identifiant(tmp_path):
    """`EPIC11-ARB-153` : l'ecran montre le VRAI nom du fichier, accents et
    espaces compris, et non l'identifiant derive.

    Le fichier est nomme de facon que les deux ne puissent pas etre confondus :
    si le refus portait le `rush_id`, l'assertion tomberait.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "Prise 01 - Ete.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )

    assert refus.source_name == "Prise 01 - Ete.mov"
    assert refus.rush_id == naming.normalize_identifier(
        "Prise 01 - Ete", label="le nom du fichier source"
    )
    assert refus.source_name != refus.rush_id


def test_C2_la_preuve_PARTITIONNE_exactement_les_criteres_compares(tmp_path):
    """`EPIC11-ARB-148` : les trois listes couvrent `CRITERES_IDENTITE_RUSH`
    **exactement** -- ni recouvrement, ni oubli.

    Ensemble exact et somme des cardinaux, dans les deux sens : une assertion
    d'appartenance laisserait passer un critere compte deux fois. La liste est
    lue de la constante, jamais recopiee : `EPIC11-ARB-230` l'a fait passer de
    quatre a trois le 2026-09-05, et ce test-ci n'avait pas a bouger pour ca.
    """
    refus, _ = _refus_sec_sur(tmp_path, "milieu")
    preuve = refus.criteres
    assert preuve is not None

    trois = (preuve.divergents, preuve.concordants, preuve.non_verifiables)
    reunion = set().union(*trois)
    assert reunion == set(extraction.CRITERES_IDENTITE_RUSH)
    assert sum(len(liste) for liste in trois) == len(
        extraction.CRITERES_IDENTITE_RUSH
    )
    # Le dossier n'y est PLUS : il n'est pas compare, donc il ne peut tomber
    # dans aucune des trois cases. Une preuve qui le montrerait ferait croire
    # a l'operateur qu'il a pese.
    assert extraction.CRITERE_DE_DERNIER_RECOURS not in reunion

    # Rien ne DIVERGE -- c'est un refus qui constate une identite, pas un
    # conflit : `en_conflit` doit etre faux, sinon le verdict dirait l'inverse
    # de ce que le refus dit.
    assert preuve.divergents == ()
    assert preuve.en_conflit is False

    # **Le cote mesure est REEL depuis `EPIC11-ARB-230`**, et c'est ce qui
    # rend l'arbitrage applicable : la cadence et la duree du fichier designe
    # sont mesurees et concordent. Le timecode initial reste non verifiable --
    # la fixture n'en declare pas --, donc il est **dit** plutot qu'invente.
    assert preuve.concordants == ("fps_source_exact", "source_frame_count")
    assert preuve.non_verifiables == ("source_start_timecode",)


def test_C2_la_preuve_porte_les_valeurs_DECLAREES_et_MESUREES(tmp_path):
    """Les deux cotes, et c'est ce que `E2-1f` affiche.

    **Le cote mesure etait vide jusqu'au 2026-09-05** : le refus tombait avant
    le probe, donc les trois criteres sortaient en `non_verifiables` et
    l'ecran n'avait qu'une colonne. `EPIC11-ARB-230` l'a rendu obligatoire --
    le dossier ne separant plus, un verdict prononce avant la mesure ne
    compare plus rien. C'est aussi ce que la section « Ce qui n'est pas
    tranche ici » du document d'arbitrage laissait ouvert ; l'arbitrage l'a
    tranche par sa propre promesse sur le multicam.
    """
    refus, _ = _refus_sec_sur(tmp_path, "queue")
    declares = refus.criteres.declares

    assert declares.source_parent == "A-CAM"
    assert declares.fps_source_exact == "25/1"
    assert declares.source_frame_count == 125
    assert declares.source_start_timecode == "02:00:00:00"

    mesures = refus.criteres.mesures
    assert mesures.source_parent == "A-CAM"
    assert mesures.fps_source_exact == "25/1"
    assert mesures.source_frame_count == 125
    # La fixture ne declare aucun timecode : une absence se DIT, elle ne se
    # substitue jamais par `00:00:00:00`.
    assert mesures.source_start_timecode is None


def test_C2_le_refus_BON_MARCHE_ne_mesure_rien_et_le_DIT(tmp_path):
    """Volet symetrique : le seul refus qui ne paie pas de probe.

    Quand l'operateur redesigne le fichier **deja enregistre a ce chemin**,
    aucune mesure ne pourrait changer le verdict -- les quatre criteres
    seraient ceux de ce fichier des deux cotes -- et rien ne pourrait etre
    separe, le suffixe d'`EPIC11-ARB-9` derivant du meme dossier. Le refus
    tombe donc a l'etape 1, `EPIC5-ARB-34` tenu, et sa preuve declare les
    trois criteres **non verifiables** plutot que d'inventer des chiffres.

    Mesure d'ORDRE, sans lecture du code : un binaire ffprobe qui n'existe pas.
    Si ce refus payait un probe, l'exception serait `FfprobeNotFoundError`.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=projet,
            video_path=video,
            logger=JournalMuet(),
            ffprobe_binary=FFPROBE_ABSENT,
        )
    )

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert refus.criteres is not None
    assert set(refus.criteres.non_verifiables) == set(
        extraction.CRITERES_IDENTITE_RUSH)
    assert refus.criteres.divergents == ()
    assert refus.criteres.concordants == ()


def test_C2_le_verdict_est_DELEGUE_au_coeur_jamais_recopie(tmp_path):
    """`EPIC11-ARB-108`, « un mecanisme, un lieu ».

    Mesure par **substitution** : on remplace le comparateur du coeur dans le
    module et on verifie que c'est bien SON verdict qui voyage. Une seconde
    redaction de la comparaison rendrait ce test rouge.
    """
    sentinelle = extraction.ConflitIdentiteRush(
        entree={},
        declares=extraction.CriteresIdentiteRush(source_parent="sentinelle"),
        mesures=extraction.CriteresIdentiteRush(source_parent="sentinelle"),
        divergents=(),
        concordants=("source_parent",),
        non_verifiables=(),
    )
    vus: list[tuple] = []

    def espion(declares, mesures):
        vus.append((declares, mesures))
        return sentinelle

    original = declaration_de_rush.comparer_identite_rush
    declaration_de_rush.comparer_identite_rush = espion
    try:
        refus, _ = _refus_sec_sur(tmp_path, "milieu")
    finally:
        declaration_de_rush.comparer_identite_rush = original

    assert len(vus) == 1, vus
    assert refus.criteres.declares is sentinelle.declares
    assert refus.criteres.concordants == ("source_parent",)
    # L'entree bloquante y est posee par l'appelant, comme
    # `rush_identity_conflict` le fait pour le cas divergent.
    assert refus.criteres.entree["rush_id"] == "cible"

    # Frontiere negative : la comparaison n'est pas re-redigee ici.
    source = source_du_module(declaration_de_rush)
    assert "CRITERES_IDENTITE_RUSH" not in source
    assert "divergents.append" not in source


@pytest.mark.parametrize(
    "cas",
    ["projet_sans_manifeste", "fichier_introuvable", "chemin_non_fichier",
     "source_non_qualifiee", "rush_deja_declare"],
)
def test_C2_les_CINQ_refus_portent_le_nom_du_fichier_designe(tmp_path, cas):
    """Un ecran doit pouvoir nommer ce qu'il refuse, quel que soit le motif.

    C'est aussi ce que la dette `B-1` reproche a l'enveloppe CLI : elle imprime
    `args.video` verbatim, donc une chaine vide rend une ligne vide. Le coeur,
    lui, porte desormais le nom resolu.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    pas_une_video = fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM")

    if cas == "rush_deja_declare":
        declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )

    cibles = {
        "projet_sans_manifeste": (tmp_path / "projet-absent", video,
                                  "prise01.mov"),
        "fichier_introuvable": (projet, tmp_path / "A-CAM" / "jamais-vu.mov",
                                "jamais-vu.mov"),
        "chemin_non_fichier": (projet, tmp_path / "A-CAM", "A-CAM"),
        "source_non_qualifiee": (projet, pas_une_video, "faux.mov"),
        "rush_deja_declare": (projet, video, "prise01.mov"),
    }
    dossier, chemin, attendu = cibles[cas]

    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=dossier, video_path=chemin, logger=JournalMuet()
        )
    )
    assert refus.motif == cas
    assert refus.source_name == attendu


@pytest.mark.parametrize(
    "cas",
    ["projet_sans_manifeste", "fichier_introuvable", "chemin_non_fichier",
     "source_non_qualifiee"],
)
def test_C2_volet_symetrique_seul_le_refus_SEC_porte_une_preuve(tmp_path, cas):
    """Les quatre autres refus ne comparent rien : leur preuve est `None`.

    Sans ce volet, un `criteres` pose partout par defaut rendrait le test de
    partition vert sans que la preuve soit celle du bon refus.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")
    pas_une_video = fichier_qui_n_est_pas_une_video(tmp_path / "A-CAM")

    cibles = {
        "projet_sans_manifeste": (tmp_path / "projet-absent", video),
        "fichier_introuvable": (projet, tmp_path / "A-CAM" / "jamais-vu.mov"),
        "chemin_non_fichier": (projet, tmp_path / "A-CAM"),
        "source_non_qualifiee": (projet, pas_une_video),
    }
    dossier, chemin = cibles[cas]

    refus = refus_de(
        lambda: declaration_de_rush.preparer_une_declaration(
            project_dir=dossier, video_path=chemin, logger=JournalMuet()
        )
    )
    assert refus.rush_id is None
    assert refus.entree is None
    assert refus.criteres is None


def test_C2_expliquer_n_ajoute_AUCUNE_issue_mais_ARB_231_en_ajoute_DEUX(tmp_path):
    """**Renverse le 2026-09-05 par `EPIC11-ARB-231`, et c'etait annonce.**

    Ce test mesurait `len(refus.issues) == 1` et « tous les motifs ont une
    issue » : c'etait la frontiere qui interdisait une seconde issue au refus
    sec (`EPIC11-ARB-147`), et le mutant `M20` de la campagne du lot C1
    fermait precisement cette porte. Le document d'arbitrage du 2026-09-05 la
    nomme comme devant rougir, « et c'est le comportement voulu ».

    **Ce que la dette `C-2` a pose reste vrai, et c'est ce que ce test mesure
    encore** : *expliquer* n'ajoute aucune issue. Les quatre attributs neufs
    de `RefusDeDeclaration` -- `source_name`, `rush_id`, `entree`,
    `criteres` -- ne changent pas le cardinal des issues ; ce qui l'a change
    est un arbitrage produit, et lui seul. La mesure est donc reformulee :
    les issues du refus sont **exactement** celles de la table publiee, et les
    quatre autres motifs en portent toujours **une**.
    """
    refus, _ = _refus_sec_sur(tmp_path, "tete")

    assert len(refus.issues) == 3
    assert refus.issues == declaration_de_rush.ISSUES_PAR_MOTIF[
        declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    ]
    assert len(declaration_de_rush.ISSUES_PAR_MOTIF) == 5
    # Les QUATRE autres refus n'ont pas bouge : `EPIC11-ARB-231` porte sur le
    # conflit d'identite, pas sur les refus qui ne comparent rien. Sans ce
    # volet, une issue ajoutee partout passerait pour l'arbitrage.
    autres = {
        motif: issues
        for motif, issues in declaration_de_rush.ISSUES_PAR_MOTIF.items()
        if motif != declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    }
    assert len(autres) == 4
    assert all(len(issues) == 1 for issues in autres.values()), autres


def test_C2_la_signature_d_AVANT_reste_constructible(tmp_path):
    """Les quatre attributs sont optionnels, et c'est mesure plutot que promis.

    `tests/unit/test_project_add_rush_command.py` construit un
    `RefusDeDeclaration` a la main pour substituer le coeur : la faire rougir
    en ajoutant un parametre obligatoire aurait ete une retouche de banc de
    comportement, c'est-a-dire un signal d'alarme.
    """
    refus = declaration_de_rush.RefusDeDeclaration(
        "arret de la mesure",
        motif=declaration_de_rush.MOTIF_FICHIER_INTROUVABLE,
        issues=("issue de la mesure",),
    )
    assert refus.source_name is None
    assert refus.rush_id is None
    assert refus.entree is None
    assert refus.criteres is None


def test_C2_l_entree_rendue_est_une_COPIE_de_la_structure_VIVANTE(tmp_path):
    """Un ecran qui recevrait la structure vivante du manifeste pourrait la
    modifier sans le vouloir.

    **Mesure par retenue de la structure chargee, et non par relecture du
    fichier** : le fichier n'est de toute facon jamais reecrit sur ce chemin,
    donc le comparer ne prouve rien -- c'est le mutant `M12` de la campagne du
    lot C1, qui a survecu a la premiere redaction de ce test pour exactement
    cette raison. On tient le dictionnaire que `load_manifest` a rendu, et on
    mesure l'identite d'objet, puis la non-propagation d'une mutation.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_a_trois_rushes(
        projet, rushes=_rushes_avec_la_cible_en("milieu")
    )
    video = copie_du_rush(tmp_path / "A-CAM", "cible.mov")

    tenu: dict = {}
    original = declaration_de_rush.load_manifest

    def espion(chemin):
        charge = original(chemin)
        tenu["manifeste"] = charge
        return charge

    declaration_de_rush.load_manifest = espion
    try:
        refus = refus_de(
            lambda: declaration_de_rush.preparer_une_declaration(
                project_dir=projet, video_path=video, logger=JournalMuet()
            )
        )
    finally:
        declaration_de_rush.load_manifest = original

    vivante = next(
        rush for rush in tenu["manifeste"]["rushes"] if rush["rush_id"] == "cible"
    )
    assert refus.entree is not vivante
    assert refus.criteres.entree is not vivante

    refus.entree["source_name"] = "saccage.mov"
    refus.criteres.entree["source_frame_count"] = 1

    assert vivante["source_name"] == "cible.mov"
    assert vivante["source_frame_count"] == 125
    # Et le fichier non plus, evidemment -- mais c'est la mesure faible.
    assert entree_du_rush(manifeste, "cible")["source_name"] == "cible.mov"


def test_C1_le_TEMPS_2_relit_l_identifiant_REELLEMENT_ECRIT(tmp_path):
    """`EPIC11-ARB-9` : le rush ecrit porte l'identifiant **leve**, pas le
    derive -- et c'est celui-la que l'entree rendue doit decrire.

    Mutant `M8` de la campagne du lot C1 : `ecrire_la_declaration` relisant
    `rush_id_derive` au lieu de `rush_id` **survivait**, parce que l'entree
    derivee existe elle aussi au manifeste -- c'est justement celle qui a
    provoque l'homonymie. Le `rush_id` rendu restait bon et le champ `entree`
    decrivait le mauvais rush : un ecran qui affiche l'entree apres coup aurait
    montre le rush du voisin.

    La cible est en **queue** de `manifest["rushes"]` -- un rush declare
    s'ajoute toujours en fin de liste --, donc ni premiere ni au milieu.
    """
    projet = tmp_path / "projet-a"
    manifeste = manifeste_a_trois_rushes(
        projet,
        rushes=(
            {"rush_id": "avant", "source_name": "avant.mov",
             "source_parent": "Z-CAM", "fps_source": 24.0,
             "fps_source_exact": "24/1"},
            # **La duree diverge, et c'est ce qui fait jouer `EPIC11-ARB-9`
            # depuis `EPIC11-ARB-230`** : le dossier ne separe plus, donc une
            # entree qui ne differerait que par lui menerait au refus de
            # conflit et ce test ne mesurerait plus rien.
            {"rush_id": "prise01", "source_name": "prise01.mov",
             "source_parent": "B-CAM", "fps_source": 25.0,
             "fps_source_exact": "25/1", "source_frame_count": 999,
             "source_frame_count_is_exact": True},
            {"rush_id": "apres", "source_name": "apres.mov",
             "source_parent": "Y-CAM", "fps_source": 30.0,
             "fps_source_exact": "30/1"},
        ),
    )
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert issue.homonymie_levee is True
    assert issue.rush_id != issue.rush_id_derive
    assert issue.entree["rush_id"] == issue.rush_id
    assert issue.entree["source_parent"] == "A-CAM"
    # Volet symetrique : l'entree homonyme d'origine est intacte, et c'est bien
    # elle qu'un `rush_id_derive` fautif ferait rendre.
    ancienne = entree_du_rush(manifeste, "prise01")
    assert ancienne["source_parent"] == "B-CAM"
    assert issue.entree is not ancienne
    assert [rush["rush_id"] for rush in rushes_du_manifeste(manifeste)][-1] == (
        issue.rush_id
    )


# ---------------------------------------------------------------------------
# ARB-230 / ARB-231 / ARB-232 -- un rush identique est un conflit, quel que
# soit son dossier
# ---------------------------------------------------------------------------
#
# Les trois arbitrages du 2026-09-05
# (`decisions-2026-09-05-epic11-arb-230-a-232-conflit-de-rush-et-relink.md`),
# et la mesure de terrain qui les a ouverts : deux copies du MEME fichier dans
# `A/prise01.mp4` et `B/prise01.mp4` etaient declarees `prise01` puis
# `prise01-B`, **sans une question**, alors que 26 frames / 25/1 / 00:00:00:00
# des deux cotes disaient que c'etait le meme rush.
#
# **Regle des fabriques, les quatre points.** Le manifeste porte trois rushes
# distinguables et la cible est placee successivement en TETE, au MILIEU et en
# QUEUE : un balayage qui rendrait toujours le premier element et un balayage
# qui sauterait la derniere entree sont deux modes de panne differents, et
# aucun test au milieu ne les demasque tous les deux (point 4, 2026-09-03).


#: Trois rushes dont la cible decrit EXACTEMENT `RUSH_REEL` -- 125 frames a
#: 25/1 -- mais depuis un AUTRE dossier. C'est le montage d'`EPIC11-ARB-230` :
#: les criteres d'identite coincident, seul le dossier differe.
#:
#: Les deux voisines divergent des trois criteres **et** entre elles : une
#: comparaison qui s'apparierait par position rendrait un verdict faux et
#: visible, et un remplissage uniforme le cacherait (defaut `M33` de la 5.6).
TROIS_RUSHES_DONT_LA_CIBLE_EST_LE_MEME_RUSH = (
    {"rush_id": "avant", "source_name": "avant.mov", "source_parent": "Z-CAM",
     "source_path": "/rushes/tournage-avril/Z-CAM/avant.mov",
     "fps_source": 24.0, "fps_source_exact": "24/1",
     "source_frame_count": 480, "source_frame_count_is_exact": True,
     "source_start_timecode": "01:00:00:00"},
    {"rush_id": "prise01", "source_name": "prise01.mov", "source_parent": "A",
     "source_path": "/rushes/tournage-mai/A/prise01.mov",
     "fps_source": 25.0, "fps_source_exact": "25/1",
     "source_frame_count": 125, "source_frame_count_is_exact": True},
    {"rush_id": "apres", "source_name": "apres.mov", "source_parent": "Y-CAM",
     "source_path": "/rushes/tournage-juin/Y-CAM/apres.mov",
     "fps_source": 30.0, "fps_source_exact": "30/1",
     "source_frame_count": 900, "source_frame_count_is_exact": True,
     "source_start_timecode": "03:00:00:00"},
)


def _manifeste_avec_la_cible_en(dossier: Path, position: str) -> Path:
    """Le manifeste ci-dessus, la cible en tete / au milieu / en queue."""
    trois = TROIS_RUSHES_DONT_LA_CIBLE_EST_LE_MEME_RUSH
    cible = next(r for r in trois if r["rush_id"] == "prise01")
    voisines = [r for r in trois if r["rush_id"] != "prise01"]
    ordre = {
        "tete": (cible, *voisines),
        "milieu": (voisines[0], cible, voisines[1]),
        "queue": (*voisines, cible),
    }[position]
    return manifeste_a_trois_rushes(dossier, rushes=ordre)


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_ARB230_le_meme_rush_dans_un_AUTRE_dossier_est_un_CONFLIT(
    tmp_path, position
):
    """`EPIC11-ARB-230`, choix d'Egan : « Non, il ne separe plus ».

    Le fichier designe vit dans `B` et l'entree declaree vient de `A` : le
    **seul** ecart est le dossier. Avant le 2026-09-05, ce cas etait un succes
    silencieux qui suffixait `prise01-B` ; il est desormais le refus de
    conflit, avec ses trois issues.
    """
    projet = tmp_path / "projet-a"
    manifeste = _manifeste_avec_la_cible_en(projet, position)
    avant = rushes_du_manifeste(manifeste)
    video = copie_du_rush(tmp_path / "B", "prise01.mov")

    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert refus.rush_id == "prise01"
    # L'entree rendue est bien **celle qui bloque**, identifiee par ses valeurs
    # propres et non par sa position : c'est le mutant `M8` du lot C1, ou
    # `entree` decrivait le rush du voisin.
    assert refus.entree["source_parent"] == "A"
    assert refus.entree["source_frame_count"] == 125
    # Et rien n'a ete ecrit : le refus arrive avant l'ecriture, toujours.
    assert rushes_du_manifeste(manifeste) == avant


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_ARB230_volet_symetrique_une_DUREE_differente_separe_toujours(
    tmp_path, position
):
    """`EPIC11-ARB-9` est **subordonne, pas annule**.

    Sans ce volet, le precedent serait vert sur un coeur qui refuserait TOUS
    les homonymes -- ce qui casserait le multicam ordinaire, celui pour lequel
    `ARB-9` avait ete ecrit. Le fichier designe porte 50 frames la ou l'entree
    en declare 125 : deux prises differentes, separees **sans question**.
    """
    projet = tmp_path / "projet-a"
    manifeste = _manifeste_avec_la_cible_en(projet, position)
    avant = rushes_du_manifeste(manifeste)
    video = copie_du_rush(tmp_path / "B", "prise01.mov", RUSH_REEL_AUTRE_DUREE)

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert issue.homonymie_levee is True
    assert issue.separation_forcee is False, (
        "c'est le coeur qui a juge, pas l'operateur"
    )
    assert issue.rush_id_derive == "prise01"
    assert issue.rush_id != "prise01"
    assert issue.entree["source_frame_count"] == 50
    # Les trois entrees d'origine sont intactes, dans leur ordre, et la
    # nouvelle s'ajoute en queue.
    apres = rushes_du_manifeste(manifeste)
    assert len(apres) == 4
    assert apres[:3] == avant
    assert apres[-1]["rush_id"] == issue.rush_id


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_ARB230_la_separation_tient_meme_quand_le_DOSSIER_concorde(
    tmp_path, position
):
    """Le volet qui manquait, et un mutant l'a exige.

    `test_ARB230_volet_symetrique_une_DUREE_differente_separe_toujours` place
    le fichier dans `B` alors que l'entree declare `A` : la duree **et** le
    dossier divergent tous les deux, donc le succes s'explique aussi bien par
    l'un que par l'autre. Mutant `M5` mesure : remplacer
    `rush_identity_conflict(..., mesures=mesures)` par l'appel AVEUGLE -- le
    regime degrade, ou le dossier separe encore -- laissait ce banc VERT. Le
    module aurait pu cesser de transmettre sa mesure sans que rien ne sonne,
    et `EPIC11-ARB-230` aurait ete defait par la porte de derriere.

    Ici le fichier vit dans `A`, comme l'entree declaree. Le dossier concorde,
    donc **seule** la duree peut expliquer la separation.
    """
    projet = tmp_path / "projet-a"
    manifeste = _manifeste_avec_la_cible_en(projet, position)
    video = copie_du_rush(tmp_path / "A", "prise01.mov", RUSH_REEL_AUTRE_DUREE)
    assert video.parent.name == entree_du_rush(manifeste, "prise01")[
        "source_parent"], "la fixture ne fait plus concorder les dossiers"

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )

    assert issue.homonymie_levee is True
    assert issue.separation_forcee is False
    assert issue.entree["source_frame_count"] == 50


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_ARB230_volet_symetrique_meme_dossier_et_meme_duree_REFUSE(
    tmp_path, position
):
    """Sans lui, le precedent serait vert sur un coeur qui separerait tout.

    Meme dossier, meme duree : rien ne diverge, c'est le meme rush.
    """
    projet = tmp_path / "projet-a"
    _manifeste_avec_la_cible_en(projet, position)
    video = copie_du_rush(tmp_path / "A", "prise01.mov")

    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )
    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE


def test_ARB230_une_entree_SANS_duree_ne_se_separe_plus_toute_seule(tmp_path):
    """Ce que l'arbitrage coute aux manifestes ANCIENS, dit plutot que tu.

    Une entree ecrite avant que la duree n'entre dans le manifeste ne declare
    ni cardinal ni timecode : les trois criteres restants sont **non
    verifiables**, donc jamais divergents, donc le coeur la juge identique a
    tout homonyme. Elle ne se separe plus toute seule -- elle mene au refus de
    conflit, dont la premiere issue est le **relink**, ce qui est exactement le
    geste juste pour une entree qu'on n'a pas de quoi departager.

    Ce n'est pas un defaut : c'est le refus de deviner. Mais ce n'est pas le
    comportement d'avant le 2026-09-05, et le taire ferait passer une
    regression pour une intention.
    """
    projet = tmp_path / "projet-a"
    manifeste_a_trois_rushes(
        projet,
        rushes=(
            {"rush_id": "avant", "source_name": "avant.mov",
             "source_parent": "Z-CAM", "fps_source": 24.0,
             "fps_source_exact": "24/1"},
            # L'entree ANCIENNE : aucune duree, aucun timecode.
            {"rush_id": "prise01", "source_name": "prise01.mov",
             "source_parent": "A-CAM", "fps_source": 25.0,
             "fps_source_exact": "25/1"},
            {"rush_id": "apres", "source_name": "apres.mov",
             "source_parent": "Y-CAM", "fps_source": 30.0,
             "fps_source_exact": "30/1"},
        ),
    )
    video = copie_du_rush(tmp_path / "B-CAM", "prise01.mov")

    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet()
        )
    )

    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    # La preuve DIT que rien n'etait comparable : elle n'invente aucun chiffre.
    assert set(refus.criteres.non_verifiables) == {
        "source_frame_count", "source_start_timecode"}
    assert refus.criteres.concordants == ("fps_source_exact",)
    assert refus.criteres.divergents == ()
    # Et l'issue qui va avec est offerte : le relink, en premiere position.
    assert "relink" in refus.issues[0]


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_ARB232_force_distinct_declare_une_SECONDE_entree(tmp_path, position):
    """`EPIC11-ARB-232` : la seconde issue du refus, et elle FAIT ce qu'elle dit.

    La cloture d'`EPIC11-ARB-224` a pose qu'une commande citee dans un refus
    doit etre tapable, doit parser, et doit **changer quelque chose**. C'est
    le troisieme volet, mesure ici sur le coeur : le drapeau produit une
    entree de plus, portant un identifiant leve.
    """
    projet = tmp_path / "projet-a"
    manifeste = _manifeste_avec_la_cible_en(projet, position)
    avant = rushes_du_manifeste(manifeste)
    video = copie_du_rush(tmp_path / "B", "prise01.mov")

    issue = declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )

    assert issue.homonymie_levee is True
    assert issue.separation_forcee is True, (
        "c'est l'operateur qui a tranche, pas le coeur : les confondre dirait "
        "que la machine a su distinguer deux rushes qu'elle juge identiques"
    )
    assert issue.rush_id_derive == "prise01"
    assert issue.rush_id != "prise01"

    apres = rushes_du_manifeste(manifeste)
    assert len(apres) == len(avant) + 1
    assert apres[:len(avant)] == avant, "une entree existante a ete touchee"
    assert apres[-1]["rush_id"] == issue.rush_id


def test_ARB232_force_distinct_ne_touche_PAS_l_entree_existante(tmp_path):
    """Volet symetrique d'`EPIC11-ARB-89` : forcer n'est jamais ecraser.

    `--overwrite` a ete ecarte nommement par l'arbitrage -- « il dit ecraser et
    ferait ici l'inverse ». La mesure porte sur l'**identite du fichier** et sur
    un temoin, jamais sur un condensat : la fabrique est deterministe, donc une
    reecriture a l'identique laisserait un condensat vert a tort.
    """
    projet = tmp_path / "projet-a"
    _manifeste_avec_la_cible_en(projet, "milieu")
    video = copie_du_rush(tmp_path / "B", "prise01.mov")

    avant = entree_du_rush(projet / MANIFEST_FILENAME, "prise01")
    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet(),
        force_distinct=True,
    )
    apres = entree_du_rush(projet / MANIFEST_FILENAME, "prise01")
    assert apres == avant


def test_ARB232_force_distinct_sur_le_MEME_fichier_refuse_QUAND_MEME(tmp_path):
    """Le seul cas ou forcer ne peut rien : le fichier deja enregistre ICI.

    Le suffixe d'`EPIC11-ARB-9` derive du dossier parent, qui est le meme :
    forcer produirait deux entrees pointant sur le **meme chemin absolu**,
    c'est-a-dire un doublon plutot qu'une distinction. Le refus tombe donc, et
    il tombe **sans probe** -- aucune mesure ne pourrait le renverser.
    """
    projet = tmp_path / "projet-a"
    manifeste_vierge(projet)
    video = copie_du_rush(tmp_path / "A-CAM", "prise01.mov")

    declaration_de_rush.declarer_un_rush(
        project_dir=projet, video_path=video, logger=JournalMuet()
    )
    refus = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet, video_path=video, logger=JournalMuet(),
            force_distinct=True, ffprobe_binary=FFPROBE_ABSENT,
        )
    )
    assert refus.motif == declaration_de_rush.MOTIF_RUSH_DEJA_DECLARE
    assert len(rushes_du_manifeste(projet / MANIFEST_FILENAME)) == 1


def test_ARB233_forcer_DEUX_FOIS_depuis_le_MEME_dossier_ne_bloque_plus(tmp_path):
    """**Renverse le 2026-09-05 par `EPIC11-ARB-233`, et c'est son objet meme.**

    Ce test s'appelait `test_ARB232_un_SUFFIXE_deja_pris_cesse_de_citer_force_
    distinct` et mesurait l'inverse : le suffixe valant le **dossier parent**,
    forcer deux fois depuis le meme dossier rendait exactement le meme nom,
    donc exactement le meme refus, et le message cessait alors de citer
    `--force-distinct` pour renvoyer a un renommage manuel. Egan a tranche que
    cette sortie n'en est pas une -- « Refuser en proposant d'inventer un nom
    [...] n'est pas une issue, c'est une corvee manuelle » (`EPIC11-ARB-104`).

    Le suffixe etant un RANG, la premisse a disparu : le deuxieme forcage rend
    `prise01-2`, le troisieme `prise01-3`, et il n'y a plus de refus a mesurer.
    Ce que le banc garde de l'ancien, c'est sa **question** -- une issue citee
    doit changer quelque chose --, avec la reponse d'aujourd'hui : elle change
    quelque chose a chaque fois.

    Le regime « la citation disparait » n'a pas disparu pour autant ; il s'est
    deplace aux **98 rangs consommes**, et il est mesure par
    `tests/unit/test_rang_de_desambiguisation.py` (section D3).
    """
    projet = tmp_path / "projet-a"
    manifeste = _manifeste_avec_la_cible_en(projet, "queue")
    avant = rushes_du_manifeste(manifeste)

    # Deux fichiers DISTINCTS, dans le MEME dossier : c'est le montage qui
    # bloquait, l'ancien suffixe ne pouvant rendre qu'une valeur par dossier.
    premier = declaration_de_rush.declarer_un_rush(
        project_dir=projet,
        video_path=copie_du_rush(tmp_path / "B", "prise01.mov"),
        logger=JournalMuet(), force_distinct=True,
    )
    second = declaration_de_rush.declarer_un_rush(
        project_dir=projet,
        video_path=copie_du_rush(tmp_path / "B" / "carte-2", "prise01.mov"),
        logger=JournalMuet(), force_distinct=True,
    )

    assert (premier.rush_id, second.rush_id) == ("prise01-2", "prise01-3")
    apres = rushes_du_manifeste(manifeste)
    assert apres[: len(avant)] == avant, "une entree existante a ete touchee"
    assert len(apres) == len(avant) + 2

    # Volet symetrique : le refus SANS drapeau cite toujours la commande
    # tapable, sur un troisieme homonyme. Sans lui, ce test serait vert sur un
    # coeur qui aurait cesse de refuser quoi que ce soit.
    troisieme = refus_de(
        lambda: declaration_de_rush.declarer_un_rush(
            project_dir=projet,
            video_path=copie_du_rush(tmp_path / "C", "prise01.mov"),
            logger=JournalMuet(),
        )
    )
    assert "`mmu project add-rush" in str(troisieme)
    assert "--force-distinct`" in str(troisieme)
