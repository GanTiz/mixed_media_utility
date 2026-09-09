# -*- coding: utf-8 -*-
"""Banc du coeur de l'INVENTAIRE de projet (story 11.11, lot A -- AC 1).

**Ce que ce banc ferme.** Rien dans le depot ne montrait ce qu'un projet
CONTIENT : les ecrans de liste montrent ce qu'ils vont consommer, et une
planche produite n'est l'entree d'aucun atelier. Deux ecarts en decoulaient,
tous deux invisibles :

* un objet **declare au manifeste et absent du disque** (AC 1.3) -- un master
  efface a la main, une planche renommee. L'operateur croit avoir libere ce
  qu'il n'a pas libere ;
* un objet **present sur le disque et declare nulle part** (AC 1.4) -- ce que
  laisse un nettoyage manuel interrompu, celui du 2026-08-27 qui a detruit des
  frames irrecuperables. **C'est le vrai livrable de ce lot.**

**La fabrique, et pourquoi elle est ce qu'elle est** (`CLAUDE.md`, regle des
fabriques, payee trois fois d'affilee) :

* **trois** rushes, **trois** lots, et la cible est **au milieu** des deux
  listes que le code parcourt -- `manifest["rushes"]` et `manifest["lots"]`.
  Un `find` fautif qui rendrait toujours la premiere entree, ou un `break`
  premature, ne se demasque pas autrement ;
* **trois** masters sur le lot cible, dont **celui du milieu** est declare et
  absent ; **trois** tirages, de trois rangs de version differents ;
* **aucune valeur uniforme** : chaque fichier de la fabrique porte une taille
  distincte de toutes les autres, et chaque somme partielle est distincte de
  toute autre. Une fabrique a poids uniformes rendrait invisible toute erreur
  d'appariement entre un noeud et son emplacement -- le mutant `M33` de la
  story 5.6, mot pour mot ;
* les objets **orphelins** portent le prefixe d'un rush qui n'existe pas
  (`r-bis`), choisi pour qu'ils tombent **au milieu** de chacune des listes que
  le code balaie. **Trois autres tombent en TETE ou en QUEUE, et c'est une
  mesure qui l'a exige** : le 2026-09-03, un mutant qui saute la derniere
  entree de chaque listing (`sorted(...)[:-1]`) a **survecu** a un banc dont
  tous les orphelins etaient au milieu -- les entrees sautees etaient alors
  toutes declarees, donc invisibles. Une cible au milieu demasque un `find`
  fautif ; elle ne demasque pas un balayage tronque. Les deux modes de panne
  demandent deux poses, et `r-aaa`, `z-zzz` et `scan-zz-oublie` sont la
  seconde.

:func:`test_A_la_FABRIQUE_tient_ce_que_les_AC_exigent` mesure tout cela plutot
que de le promettre : une fabrique devenue mono-element ou uniforme rendrait la
moitie de ce banc verte pour rien.

**Les frontieres negatives portent chacune leur volet symetrique** : la meme
mesure appliquee a un module fabrique qui viole la regle DOIT mordre. Sans lui,
une garde qui ne regarderait plus rien serait verte -- le seul mode de panne
qu'une frontiere negative ne voit pas d'elle-meme.

**Ce que ce banc ne mesure pas, dit plutot que tu** : le cout du parcours de
disque sur un projet reel (Q1 de la fiche) est mesure a part, par un banc de
chronometrage qui ne vit pas ici -- un test de duree est un test qui rougit sur
une machine chargee.
"""
from __future__ import annotations

import ast
import inspect
import json
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "src") not in sys.path:
    sys.path.insert(0, str(RACINE / "src"))
# Le lecteur d'AST du depot, **repris et non recopie** : deux predicats pour un
# seul interdit divergeraient, et c'est le module couvert par le plus laxiste
# des deux qui passerait (`tests/unit/tui/outils_frontiere.py`, story 11.0).
if str(RACINE / "tests" / "unit" / "tui") not in sys.path:
    sys.path.insert(0, str(RACINE / "tests" / "unit" / "tui"))

from outils_frontiere import chaines_de_code, identifiants  # noqa: E402

from mixed_media_utility import page_templates, project_inventory  # noqa: E402
from mixed_media_utility import project_maintenance  # noqa: E402
from mixed_media_utility.io import naming, project_layout, version_ranks  # noqa: E402
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME  # noqa: E402

SOURCES = RACINE / "src" / "mixed_media_utility"
MODULE_DE_COEUR = SOURCES / "project_inventory.py"

# ---------------------------------------------------------------------------
# La fabrique
# ---------------------------------------------------------------------------

PROJET = "demo"
GABARIT = page_templates.TEMPLATE_A4_PORTRAIT_2F

#: Les trois rushes, dans l'ordre ou le manifeste les ecrit. La CIBLE est au
#: MILIEU, ni premiere ni derniere.
RUSH_TETE, RUSH_CIBLE, RUSH_QUEUE = "r-alpha", "r-cible", "r-omega"
TROIS_RUSHES = (RUSH_TETE, RUSH_CIBLE, RUSH_QUEUE)

#: Le rush FANTOME : il ne figure dans aucun manifeste, et tout ce qui porte
#: son nom sur le disque est un orphelin (AC 1.4). Son identifiant est choisi
#: pour trier **entre** `r-alpha` et `r-cible` : les orphelins tombent ainsi au
#: milieu de chaque liste de dossiers que le code balaie.
RUSH_FANTOME = "r-bis"

#: Les deux fantomes de BORD, poses apres qu'un mutant a survecu (voir le
#: docstring de module) : `r-aaa` trie en TETE de `frames/` et de `planches/`,
#: `z-zzz` en QUEUE de `output-frames/` et de `outputs/`. Un balayage tronque
#: d'un cote ou de l'autre les perd, et l'egalite d'ensembles rougit.
RUSH_FANTOME_TETE = "r-aaa"
RUSH_FANTOME_QUEUE = "z-zzz"

CADENCES = {RUSH_TETE: 25.0, RUSH_CIBLE: 12.5, RUSH_QUEUE: 5.0,
            RUSH_FANTOME: 10.0, RUSH_FANTOME_TETE: 8.0, RUSH_FANTOME_QUEUE: 6.0}

#: Tailles de fichier, toutes distinctes, et dont **aucune somme partielle** ne
#: coincide avec une autre : c'est ce qui fait qu'un noeud apparie au mauvais
#: emplacement rougit au lieu de passer.
OCTETS_FRAME = {RUSH_TETE: 101, RUSH_CIBLE: 211, RUSH_QUEUE: 0}
CARDINAL_FRAMES = {RUSH_TETE: 3, RUSH_CIBLE: 5, RUSH_QUEUE: 0}
OCTETS_FRAME_SCANNEE = {RUSH_TETE: 53, RUSH_QUEUE: 59}
CARDINAL_FRAMES_SCANNEES = {RUSH_TETE: 2, RUSH_QUEUE: 1}

#: **Le lot scanne de rang 2 du lot cible** (story 11.14, `EPIC11-ARB-105` :
#: rescanner avec un profil ameliore est une VERSION). Il est ecrit sur le
#: disque et attribue EXPLICITEMENT a `scan-cible-a` par
#: `reconstructions[].output_frames_dir`. Ses valeurs sont distinctes de
#: toutes les autres : une fabrique uniforme rendrait invisible un appariement
#: inverse entre un scan et son lot scanne.
CARDINAL_FRAMES_SCANNEES_V2 = 4
OCTETS_FRAME_SCANNEE_V2 = 67

#: **Le cardinal que le MANIFESTE promet, volontairement faux.** Cinq frames
#: sont ecrites, neuf sont declarees : un inventaire qui lirait
#: `expected_frame_count` au lieu de compter les fichiers rendrait 9, et c'est
#: exactement l'estimation que l'AC 1.2 interdit.
CARDINAL_PROMIS_AU_MANIFESTE = 9

#: Les TROIS masters du lot cible, dans l'ordre du manifeste. Celui du MILIEU
#: est declare et **jamais ecrit** : c'est la cible de l'AC 1.3.
TROIS_MASTERS = (
    ("prores_422", 1009),
    ("prores_hq", None),      # declare, absent du disque
    ("prores_444", 3023),
)
MASTER_ABSENT = TROIS_MASTERS[1][0]

#: Les TROIS tirages du lot cible : trois rangs de version distincts, lus par
#: `naming.rang_du_fragment_de_version` et jamais decoupes a la main.
TROIS_PLANCHES = ((None, 701), (2, 809), (3, 907))

#: Les scans du lot cible -- DEUX slugs, parce qu'un lot rescanne depuis deux
#: slugs en a deux (`EPIC11-ARB-109`) et qu'une filiation qui n'en rendrait
#: qu'un laisserait des images derriere.
SCANS_DE_LA_CIBLE = (("scan-cible-a", 2, 73), ("scan-cible-b", 1, 79))
SCAN_DE_TETE = ("scan-zulu", 1, 71)

#: Le libelle de chaine de scan est choisi pour que le nom du PDF de
#: calibration tombe **au milieu** de `planches/` : sans quoi le test qui mesure
#: son exclusion viserait le premier ou le dernier fichier de la liste.
CHAINE_DE_SCAN = "r c atelier"

#: Les cinq orphelins, et leurs poids -- tous distincts des poids declares.
OCTETS_ORPHELINS = {
    "frames": (2, 1201),
    "frames_scannees": (1, 1301),
    "master": 1401,
    "planche": 1501,
    "scan": (3, 1601),
    # Les trois orphelins de BORD, chacun avec son poids propre.
    "frames_en_tete": (2, 1901),
    "planche_en_tete": 2003,
    "frames_scannees_en_queue": (1, 2101),
    "master_en_queue": 2203,
    "scan_en_queue": (2, 2309),
}
SLUG_SCAN_ORPHELIN = "scan-oublie"
SLUG_SCAN_ORPHELIN_QUEUE = "scan-zz-oublie"

#: Un fichier de travail du POC dans `outputs/` : il ne porte pas le marqueur
#: de master, il n'est donc pas un objet de cet inventaire.
FICHIER_DU_POC = "scan_frame_0001.tiff"
OCTETS_DU_POC = 1801
OCTETS_CALIBRATION = 1701


def _ecrire(chemin: Path, octets: int) -> Path:
    """Ecrire un fichier de `octets` octets, dossiers parents compris."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"x" * octets)
    return chemin


def _timecode(index: int) -> str:
    return f"00:00:00:{index:02d}"


def _lot_id(rush: str) -> str:
    return naming.build_lot_id(rush, CADENCES[rush])


def _slug(rush: str) -> str:
    return project_layout.rush_dir_slug(rush, CADENCES[rush])


def _nom_de_master(rush: str, profil: str) -> str:
    return naming.build_master_filename(
        lot_id=_lot_id(rush), profile_id=profil, container="mov")


def _nom_de_planche(rush: str, rang: int | None) -> str:
    return naming.build_sheets_pdf_filename(
        PROJET, rush, _lot_id(rush), rang, template_id=GABARIT)


def _frames(projet: Path, rush: str, cardinal: int, octets: int) -> None:
    dossier = project_layout.extract_frames_dir(projet, rush, CADENCES[rush])
    dossier.mkdir(parents=True, exist_ok=True)
    for index in range(cardinal):
        _ecrire(
            dossier / naming.build_extracted_frame_filename(
                rush, CADENCES[rush], _timecode(index)),
            octets)


def _frames_scannees(projet: Path, rush: str, cardinal: int, octets: int,
                     rang: int | None = None) -> None:
    dossier = project_layout.scan_frames_dir(
        projet, rush, CADENCES[rush], version_rank=rang)
    dossier.mkdir(parents=True, exist_ok=True)
    for index in range(cardinal):
        _ecrire(
            dossier / naming.build_scan_frame_filename(
                rush, CADENCES[rush], _timecode(index)),
            octets)


def _dossier_de_scan(projet: Path, slug: str, cardinal: int, octets: int) -> None:
    dossier = project_layout.scan_lot_dir(projet, slug)
    dossier.mkdir(parents=True, exist_ok=True)
    for index in range(cardinal):
        _ecrire(dossier / f"page_{index:03d}.tiff", octets)


def fabriquer_le_projet(tmp_path: Path) -> Path:
    """Un projet a trois rushes, cible au milieu, et cinq orphelins.

    Ce que la fabrique pose, et pour quel AC :

    * `r-alpha` (tete) -- frames presentes, frames scannees presentes, un
      master, un tirage, un dossier de scan. Le cas nominal ;
    * `r-cible` (MILIEU) -- frames presentes ; `output_frames_dir` **declare et
      absent** (AC 1.3, au niveau dossier) ; trois masters dont **celui du
      milieu** declare et absent (AC 1.3, au niveau fichier) ; trois tirages
      presents ; deux dossiers de scan ;
    * `r-omega` (queue) -- un dossier de frames **existant et VIDE**. C'est le
      contre-exemple de l'AC 1.3 : il pese zero et il EXISTE, la ou le dossier
      absent de `r-cible` pese zero et n'existe pas. Les confondre est
      precisement ce que l'AC interdit ;
    * cinq objets du rush **fantome** `r-bis`, declares nulle part (AC 1.4) ;
    * deux fichiers qui ne sont PAS des objets de cet inventaire : une page de
      calibration dans `planches/` et un fichier de travail du POC dans
      `outputs/`.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)

    # --- ce qui est declare ET pose -----------------------------------------
    for rush in TROIS_RUSHES:
        _frames(projet, rush, CARDINAL_FRAMES[rush], OCTETS_FRAME[rush])
    for rush in (RUSH_TETE, RUSH_QUEUE):
        _frames_scannees(projet, rush, CARDINAL_FRAMES_SCANNEES[rush],
                         OCTETS_FRAME_SCANNEE[rush])
    # Le lot scanne de RANG 2 du lot cible : ecrit sur le disque et attribue
    # explicitement a `scan-cible-a` par le registre des reconstructions.
    _frames_scannees(projet, RUSH_CIBLE, CARDINAL_FRAMES_SCANNEES_V2,
                     OCTETS_FRAME_SCANNEE_V2, rang=2)

    outputs = project_layout.outputs_dir(projet)
    _ecrire(outputs / _nom_de_master(RUSH_TETE, "prores_422"), 401)
    for profil, octets in TROIS_MASTERS:
        if octets is not None:
            _ecrire(outputs / _nom_de_master(RUSH_CIBLE, profil), octets)

    patches = projet / project_layout.PLANCHES_DIRNAME
    _ecrire(patches / _nom_de_planche(RUSH_TETE, None), 601)
    for rang, octets in TROIS_PLANCHES:
        _ecrire(patches / _nom_de_planche(RUSH_CIBLE, rang), octets)

    for slug, cardinal, octets in (SCAN_DE_TETE, *SCANS_DE_LA_CIBLE):
        _dossier_de_scan(projet, slug, cardinal, octets)

    # --- ce qui n'est declare nulle part (AC 1.4) ---------------------------
    cardinal, octets = OCTETS_ORPHELINS["frames"]
    _frames(projet, RUSH_FANTOME, cardinal, octets)
    cardinal, octets = OCTETS_ORPHELINS["frames_scannees"]
    _frames_scannees(projet, RUSH_FANTOME, cardinal, octets)
    _ecrire(outputs / _nom_de_master(RUSH_FANTOME, "prores_hq"),
            OCTETS_ORPHELINS["master"])
    _ecrire(patches / _nom_de_planche(RUSH_FANTOME, None),
            OCTETS_ORPHELINS["planche"])
    cardinal, octets = OCTETS_ORPHELINS["scan"]
    _dossier_de_scan(projet, SLUG_SCAN_ORPHELIN, cardinal, octets)

    # Les trois orphelins de BORD : tete de `frames/` et de `planches/`, queue de
    # `output-frames/`, de `outputs/` et de `scans/`.
    cardinal, octets = OCTETS_ORPHELINS["frames_en_tete"]
    _frames(projet, RUSH_FANTOME_TETE, cardinal, octets)
    _ecrire(patches / _nom_de_planche(RUSH_FANTOME_TETE, None),
            OCTETS_ORPHELINS["planche_en_tete"])
    cardinal, octets = OCTETS_ORPHELINS["frames_scannees_en_queue"]
    _frames_scannees(projet, RUSH_FANTOME_QUEUE, cardinal, octets)
    _ecrire(outputs / _nom_de_master(RUSH_FANTOME_QUEUE, "prores_hq"),
            OCTETS_ORPHELINS["master_en_queue"])
    cardinal, octets = OCTETS_ORPHELINS["scan_en_queue"]
    _dossier_de_scan(projet, SLUG_SCAN_ORPHELIN_QUEUE, cardinal, octets)

    # --- ce qui n'est pas un objet de cet inventaire ------------------------
    _ecrire(patches / naming.build_calibration_pdf_filename(PROJET, CHAINE_DE_SCAN),
            OCTETS_CALIBRATION)
    _ecrire(outputs / FICHIER_DU_POC, OCTETS_DU_POC)

    ecrire_le_manifeste(projet, manifeste_nominal())
    return projet


def manifeste_nominal() -> dict:
    """Le manifeste de la fabrique -- l'ordre des listes EST le contrat."""
    lots = []
    for rush in TROIS_RUSHES:
        lot = {
            "lot_id": _lot_id(rush),
            "rush_id": rush,
            "fps_target": CADENCES[rush],
            "expected_frame_count": CARDINAL_PROMIS_AU_MANIFESTE,
            "frames_dir": f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{_slug(rush)}",
        }
        if rush in (RUSH_TETE, RUSH_QUEUE):
            lot["output_frames_dir"] = (
                f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(rush)}")
        lots.append(lot)

    tete, cible, _queue = lots
    tete["encoded_masters"] = [{
        "path": f"{project_layout.OUTPUTS_DIRNAME}/"
                f"{_nom_de_master(RUSH_TETE, 'prores_422')}",
        "profile_id": "prores_422"}]
    tete["sheets_pdfs"] = [{
        "path": f"{project_layout.PLANCHES_DIRNAME}/"
                f"{_nom_de_planche(RUSH_TETE, None)}"}]
    # **TETE -- la DEDUCTION** : un seul scan, un seul `output_frames_dir` non
    # attribue, donc un seul parent possible. Ce n'est pas une devinette.
    tete["reconstructions"] = [{"ingest_slug": SCAN_DE_TETE[0]}]

    # `output_frames_dir` DECLARE et jamais cree : AC 1.3 au niveau dossier.
    cible["output_frames_dir"] = (
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_CIBLE)}")
    cible["encoded_masters"] = [
        {"path": f"{project_layout.OUTPUTS_DIRNAME}/"
                 f"{_nom_de_master(RUSH_CIBLE, profil)}",
         "profile_id": profil}
        for profil, _octets in TROIS_MASTERS
    ]
    cible["sheets_pdfs"] = [
        {"path": f"{project_layout.PLANCHES_DIRNAME}/"
                 f"{_nom_de_planche(RUSH_CIBLE, rang)}"}
        for rang, _octets in TROIS_PLANCHES
    ]
    # **MILIEU -- les deux autres regimes a la fois.** Le premier scan porte
    # son `output_frames_dir` EXPLICITEMENT (`EPIC11-ARB-105`) : son lot
    # scanne de rang 2 pend de lui. Le `output_frames_dir` de tete du lot,
    # lui, n'est attribue par personne et le lot a DEUX scans : aucun parent
    # n'est deductible, il reste donc sous son lot plutot que d'etre devine --
    # `EPIC11-ARB-90`, « la filiation existe, en sens inverse et differee.
    # Reste ouvert. »
    cible["reconstructions"] = [
        {"ingest_slug": SCANS_DE_LA_CIBLE[0][0],
         "output_frames_dir": f"{project_layout.SCAN_FRAMES_DIRNAME}/"
                              f"{_slug(RUSH_CIBLE)}_v2"},
        {"ingest_slug": SCANS_DE_LA_CIBLE[1][0]},
    ]

    return {
        "schema_version": "2.1",
        "project_id": PROJET,
        "rushes": [{"rush_id": rush} for rush in TROIS_RUSHES],
        "lots": lots,
    }


def ecrire_le_manifeste(projet: Path, manifeste: dict) -> None:
    (projet / MANIFEST_FILENAME).write_text(
        json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def projet(tmp_path):
    return fabriquer_le_projet(tmp_path)


# ---------------------------------------------------------------------------
# Lecture de l'arbre -- des helpers de banc, jamais de seconde recette
# ---------------------------------------------------------------------------


def rush_nomme(inventaire, nom):
    return next(r for r in inventaire.rushes if r.nom == nom)


def lot_du_rush(inventaire, nom):
    return lots_du_rush(inventaire, nom)[0]


def lots_du_rush(inventaire, nom):
    """Les lots d'un rush -- depuis `EPIC11-ARB-244`, ses enfants ne sont QUE
    des lots.

    `EPIC11-ARB-219` en avait fait, une journee durant, les lots ET leurs
    scans freres ; `EPIC11-ARB-244` a renvoye le scan sous le lot qu'il
    reproduit. La lecture est donc redevenue celle d'avant, et
    :func:`scans_PENDUS_AU_RUSH` en mesure la moitie negative."""
    return enfants_par_nature(rush_nomme(inventaire, nom),
                              project_inventory.NATURE_LOT)


def scans_du_lot(inventaire, nom):
    """Les scans du lot du rush `nom` -- `EPIC11-ARB-244`, « le scan est le
    fils du lot qu'il reproduit ».

    Les fabriques de ce banc donnent UN lot par rush ; ce helper lit donc le
    lot du rush plutot que d'inventer une seconde recette d'appariement."""
    return enfants_par_nature(lot_du_rush(inventaire, nom),
                              project_inventory.NATURE_SCAN)


def scans_PENDUS_AU_RUSH(inventaire, nom):
    """**Frontiere negative d'`EPIC11-ARB-244`** : toujours vide.

    Un scan qui serait a la fois sous le rush ET sous le lot compterait son
    poids DEUX fois, et un test qui ne verifierait que sa presence sous le lot
    resterait vert. C'est la panne exacte que la version d'avant
    (`EPIC11-ARB-219`) mesurait dans l'autre sens ; la mesure ne se perd pas,
    elle se retourne."""
    return enfants_par_nature(rush_nomme(inventaire, nom),
                              project_inventory.NATURE_SCAN)


def scan_nomme(inventaire, rush, slug):
    return next(s for s in scans_du_lot(inventaire, rush) if s.nom == slug)


def enfants_par_nature(noeud, nature):
    return [enfant for enfant in noeud.enfants if enfant.nature == nature]


def un_enfant(noeud, nature):
    lus = enfants_par_nature(noeud, nature)
    assert len(lus) == 1, [(e.nature, e.nom) for e in noeud.enfants]
    return lus[0]


# ===========================================================================
# La fabrique elle-meme -- anti-vacuite de tout ce qui suit
# ===========================================================================


def test_A_la_FABRIQUE_tient_ce_que_les_AC_exigent(projet):
    """Trois rushes distinguables, cible au MILIEU, aucune valeur uniforme.

    Le mode de panne que ce test ferme est celui que `CLAUDE.md` a paye trois
    fois : une fabrique mono-element, ou a valeurs uniformes, rend invisible
    toute erreur d'appariement, et une cible en premiere position ne demasque
    aucun `find` fautif. **La position se verifie sur la liste que le CODE
    parcourt** -- `inventaire.rushes` --, jamais sur celle que la fabrique
    croit ecrire.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)

    noms = [rush.nom for rush in inventaire.rushes]
    assert len(noms) == 3 and len(set(noms)) == 3, noms
    rang = noms.index(RUSH_CIBLE)
    assert 0 < rang < len(noms) - 1, noms

    poids = [rush.poids_total for rush in inventaire.rushes]
    assert len(set(poids)) == len(poids), poids

    cible = lot_du_rush(inventaire, RUSH_CIBLE)
    masters = enfants_par_nature(cible, project_inventory.NATURE_MASTER)
    assert len(masters) == 3, [m.nom for m in masters]
    absents = [index for index, master in enumerate(masters)
               if master.etat == project_inventory.ETAT_DECLARE_ABSENT]
    assert absents == [1], [(m.nom, m.etat) for m in masters]

    planches = enfants_par_nature(cible, project_inventory.NATURE_PLANCHE)
    assert len(planches) == 3, [p.nom for p in planches]
    assert len({p.rang for p in planches}) == 3, [(p.nom, p.rang) for p in planches]
    assert len({p.poids for p in planches}) == 3, [(p.nom, p.poids) for p in planches]

    # Les orphelins tombent au MILIEU des listes que le code balaie, jamais en
    # tete ni en queue -- sans quoi un balayage qui sauterait la premiere ou la
    # derniere entree resterait vert.
    for dossier in (project_layout.EXTRACT_FRAMES_DIRNAME,
                    project_layout.SCAN_FRAMES_DIRNAME):
        listee = sorted(chemin.name for chemin in (projet / dossier).iterdir())
        index = listee.index(_slug(RUSH_FANTOME))
        assert 0 < index < len(listee) - 1, (dossier, listee)

    listee = sorted(chemin.name
                    for chemin in (projet / project_layout.PLANCHES_DIRNAME).iterdir())
    index = listee.index(_nom_de_planche(RUSH_FANTOME, None))
    assert 0 < index < len(listee) - 1, listee
    calibration = naming.build_calibration_pdf_filename(PROJET, CHAINE_DE_SCAN)
    index = listee.index(calibration)
    assert 0 < index < len(listee) - 1, listee


def test_A_les_orphelins_occupent_la_TETE_et_la_QUEUE_des_listings_balayes(projet):
    """**Ce qu'une cible au milieu ne peut pas voir**, et une mesure l'a prouve.

    Le 2026-09-03, un mutant qui saute la derniere entree de chaque listing --
    `sorted(...)[:-1]` dans le balayage des orphelins -- a **survecu** au banc :
    tous les orphelins etaient au milieu, donc les entrees sautees etaient
    toutes des objets DECLARES, invisibles a l'ecart. Le mutant symetrique
    (`[1:]`) n'etait attrape que par hasard, par un autre test.

    La regle des fabriques demande une cible au milieu, et elle a raison : c'est
    ce qui demasque un `find` qui rendrait toujours la premiere entree. Mais un
    balayage TRONQUE est un autre mode de panne, et il faut une pose a chaque
    bord. Ce test tient cette pose : si un orphelin cessait d'etre en tete ou en
    queue de son listing, l'egalite d'ensembles de l'AC 1.4 redeviendrait verte
    sur un balayage tronque.
    """
    def listing_des_dossiers(nom):
        return sorted(chemin.name for chemin in (projet / nom).iterdir()
                      if chemin.is_dir())

    def listing_des_fichiers(nom):
        return sorted(chemin.name for chemin in (projet / nom).iterdir()
                      if chemin.is_file())

    en_tete = (
        (listing_des_dossiers(project_layout.EXTRACT_FRAMES_DIRNAME),
         _slug(RUSH_FANTOME_TETE)),
        (listing_des_fichiers(project_layout.PLANCHES_DIRNAME),
         _nom_de_planche(RUSH_FANTOME_TETE, None)),
    )
    for listee, orphelin in en_tete:
        assert listee.index(orphelin) == 0, (orphelin, listee)

    en_queue = (
        (listing_des_dossiers(project_layout.SCAN_FRAMES_DIRNAME),
         _slug(RUSH_FANTOME_QUEUE)),
        (listing_des_fichiers(project_layout.OUTPUTS_DIRNAME),
         _nom_de_master(RUSH_FANTOME_QUEUE, "prores_hq")),
        (listing_des_dossiers(project_layout.SCANS_DIRNAME),
         SLUG_SCAN_ORPHELIN_QUEUE),
    )
    for listee, orphelin in en_queue:
        assert listee.index(orphelin) == len(listee) - 1, (orphelin, listee)


# ===========================================================================
# A1 -- la signature de producteur (AC 1.1)
# ===========================================================================


def test_A1_la_SIGNATURE_est_EXACTEMENT_celle_d_un_producteur():
    """AC 1.1 : aucun `args`, aucun mot-cle de commodite, un seul parametre.

    L'ensemble EXACT et non l'appartenance : « il prend bien `project_dir` »
    resterait vrai le jour ou un `verbose=` ou un `logger=` s'y ajouterait,
    c'est-a-dire le jour ou la signature cesserait d'etre celle d'un producteur.
    """
    signature = inspect.signature(project_inventory.inventorier_le_projet)
    assert set(signature.parameters) == {"project_dir"}, list(signature.parameters)
    parametre = signature.parameters["project_dir"]
    assert parametre.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parametre.default is inspect.Parameter.empty
    assert signature.return_annotation == "InventaireDuProjet"


@pytest.mark.parametrize(
    "interdit", ("print", "stdout", "stderr", "input", "stdin", "getpass", "readline"))
def test_A1_le_module_n_ECRIT_ni_ne_LIT_le_terminal(interdit):
    """AC 1.1 : « aucun `print` », mesure sur le SOURCE donc sur TOUS les chemins.

    Un banc d'execution ne mesure que les chemins qu'il exerce : l'injection
    ciblee de la story 11.4b a montre qu'un `print` pose sur le chemin de REFUS
    survivait au banc du noyau, qui deroulait le chemin nominal. Sous `textual`,
    une ligne imprimee tombe **sous** l'ecran dessine et un `stdin` bloquant
    gele l'interface entiere (`EPIC7-ARB-106`).
    """
    assert MODULE_DE_COEUR.is_file(), MODULE_DE_COEUR
    assert interdit not in identifiants(MODULE_DE_COEUR), interdit


@pytest.mark.parametrize(
    "interdit", ("print", "stdout", "stderr", "input", "stdin", "getpass", "readline"))
def test_A1_la_mesure_du_terminal_MORD_sur_un_module_fautif(tmp_path, interdit):
    """Volet symetrique, sur les SEPT noms et pas seulement le premier.

    Le module fabrique porte le nom interdit dans son docstring **et** dans son
    code : une mesure qui lirait le texte mordrait deja sur le docstring, et
    serait donc inapplicable a un depot dont les docstrings expliquent
    precisement ces interdits.
    """
    fautif = tmp_path / "coeur_bavard.py"
    fautif.write_text(
        f'"""Un docstring qui parle de {interdit} sans jamais s\'en servir."""\n'
        "import sys\n"
        "def agir(message):\n"
        f"    return {interdit}\n",
        encoding="utf-8")
    assert interdit in identifiants(fautif), interdit

    innocent = tmp_path / "coeur_muet.py"
    innocent.write_text(
        f'"""Ce module explique pourquoi il n\'emploie pas {interdit}."""\n'
        f"# Encore un commentaire qui nomme {interdit}.\n"
        f"MOTIF = 'voir la frontiere sur {interdit}'\n",
        encoding="utf-8")
    assert interdit not in identifiants(innocent), "la prose n'est pas un usage"


# ===========================================================================
# A2 -- l'arbre, les noms, les poids et les cardinaux (AC 1.1, AC 1.2)
# ===========================================================================


def test_A2_l_arbre_est_rushes_puis_lots_puis_SCANS_ENFANTS_DU_LOT(projet):
    """**`EPIC11-ARB-244`** : « Le scan est le fils du lot qu'il reproduit. Le
    lot scanne est bien le fils du scan. »

    **Ce que ce test mesurait la veille**, et qui a ete RETOURNE plutot que
    retire : sous `EPIC11-ARB-219` il s'appelait
    `..._l_arbre_est_rushes_puis_LOTS_ET_SCANS_freres` et affirmait
    l'inverse -- le rush portait lots ET scans, et « le scan n'est PLUS un
    enfant du lot » etait sa frontiere negative. Les deux moities ont juste
    change de cote : la frontiere negative porte desormais sur le RUSH.

    L'ensemble EXACT des natures a chaque niveau, avec la difference
    symetrique en message : « le lot porte bien des masters » resterait vrai le
    jour ou une nature disparaitrait, et le jour ou une de plus apparaitrait.

    **Frontiere negative de l'arbitrage** : le scan n'est PLUS un enfant du
    rush. Un test qui se contenterait de verifier qu'il est enfant du lot
    resterait vert s'il etait aux deux endroits a la fois -- c'est-a-dire si le
    poids du projet etait compte deux fois.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)

    assert {rush.nature for rush in inventaire.rushes} == {
        project_inventory.NATURE_RUSH}
    cible = rush_nomme(inventaire, RUSH_CIBLE)
    natures_du_rush = {enfant.nature for enfant in cible.enfants}
    assert natures_du_rush == {project_inventory.NATURE_LOT}
    # **La frontiere negative** : plus AUCUN scan pendu au rush. Sur les TROIS
    # rushes, pas seulement sur la cible -- un balayage tronque qui ne
    # regarderait que le premier ou le dernier passerait.
    for rush in TROIS_RUSHES:
        assert scans_PENDUS_AU_RUSH(inventaire, rush) == [], (
            f"{rush} : le scan est fils du LOT depuis `EPIC11-ARB-244`")

    lot = lot_du_rush(inventaire, RUSH_CIBLE)
    natures = {enfant.nature for enfant in lot.enfants}
    attendues = {
        project_inventory.NATURE_FRAMES_EXTRAITES,
        project_inventory.NATURE_MASTER,
        project_inventory.NATURE_PLANCHE,
        project_inventory.NATURE_SCAN,
        # Le lot scanne SANS scan deductible : deux scans, aucune attribution.
        project_inventory.NATURE_LOT_SCANNE,
    }
    assert natures == attendues, sorted(natures ^ attendues)

    # **L'ORDRE des enfants du lot**, celui que `_enfants_du_lot` documente :
    # frames, masters, planches, puis les scans -- c'est la maquette validee
    # `E6-1e-projet-inventaire-filiation` qui pose les scans APRES les trois
    # autres groupes, et c'est le seul point d'ordre qu'`EPIC11-ARB-244` avait
    # a trancher --, et en QUEUE le lot scanne sans parent deductible. Que la
    # maquette place les planches avant les masters n'entre pas ici : l'ecran
    # regroupe par nature avant d'afficher, et ce qui se voit de l'ordre rendu
    # ici est l'ordre AU SEIN d'un groupe. La liste
    # est asserted ENTIERE : un ordre permute et un balayage tronque d'un
    # element en queue sont deux modes de panne differents, et une egalite de
    # listes les attrape tous les deux -- un `in` ou un ensemble, non.
    assert [enfant.nature for enfant in lot.enfants] == (
        [project_inventory.NATURE_FRAMES_EXTRAITES]
        + [project_inventory.NATURE_MASTER] * len(TROIS_MASTERS)
        + [project_inventory.NATURE_PLANCHE] * len(TROIS_PLANCHES)
        + [project_inventory.NATURE_SCAN] * len(SCANS_DE_LA_CIBLE)
        + [project_inventory.NATURE_LOT_SCANNE]
    ), [(e.nature, e.nom) for e in lot.enfants]

    # Et sous le scan qui le declare : un lot scanne, puis ses frames.
    scan_a = scan_nomme(inventaire, RUSH_CIBLE, SCANS_DE_LA_CIBLE[0][0])
    lot_scanne = un_enfant(scan_a, project_inventory.NATURE_LOT_SCANNE)
    frames = un_enfant(lot_scanne, project_inventory.NATURE_FRAMES_SCANNEES)
    assert lot_scanne.chemin is None, "un noeud de regroupement n'a pas de chemin"
    assert lot_scanne.poids == 0
    assert lot_scanne.rang == 2, "le rang de la passe de rescan, lu du nom"
    assert frames.chemin == (
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_CIBLE)}_v2")
    assert frames.fichiers == CARDINAL_FRAMES_SCANNEES_V2
    assert frames.poids == CARDINAL_FRAMES_SCANNEES_V2 * OCTETS_FRAME_SCANNEE_V2

    # Le SECOND scan du meme lot n'en porte aucun : rien ne le lui attribue.
    scan_b = scan_nomme(inventaire, RUSH_CIBLE, SCANS_DE_LA_CIBLE[1][0])
    assert enfants_par_nature(scan_b, project_inventory.NATURE_LOT_SCANNE) == []

    # TETE -- la DEDUCTION : un seul scan, donc un seul parent possible.
    scan_de_tete = scan_nomme(inventaire, RUSH_TETE, SCAN_DE_TETE[0])
    deduit = un_enfant(scan_de_tete, project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(deduit, project_inventory.NATURE_FRAMES_SCANNEES).chemin == (
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_TETE)}")
    assert enfants_par_nature(
        lot_du_rush(inventaire, RUSH_TETE),
        project_inventory.NATURE_LOT_SCANNE) == []

    # QUEUE -- aucun scan du tout : le lot scanne reste sous son lot plutot
    # que de disparaitre de l'arbre.
    assert scans_du_lot(inventaire, RUSH_QUEUE) == []
    sans_scan = un_enfant(lot_du_rush(inventaire, RUSH_QUEUE),
                          project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(sans_scan, project_inventory.NATURE_FRAMES_SCANNEES).chemin == (
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_QUEUE)}")


def test_A2_l_ordre_des_rushes_et_des_lots_est_celui_DU_MANIFESTE(projet):
    """Jamais trie : l'ordre du manifeste porte une information que le tri
    detruirait -- meme motif que l'historique de reconstruction
    (`EPIC11-ARB-109`, « quelle passe a suivi laquelle »)."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    assert [rush.nom for rush in inventaire.rushes] == list(TROIS_RUSHES)
    assert [lot.nom for rush in TROIS_RUSHES
            for lot in lots_du_rush(inventaire, rush)] == [
        _lot_id(rush) for rush in TROIS_RUSHES]
    # Les scans du lot cible, dans l'ordre de `reconstructions[]` -- et ils se
    # lisent SOUS LE LOT depuis `EPIC11-ARB-244`, plus sous le rush.
    assert [scan.nom for scan in scans_du_lot(inventaire, RUSH_CIBLE)] == [
        slug for slug, _c, _o in SCANS_DE_LA_CIBLE]


def test_AC1_2_le_poids_et_le_cardinal_sont_MESURES_et_JAMAIS_estimes(projet):
    """AC 1.2, et le manifeste ment expres.

    Le lot cible declare `expected_frame_count = 9` et porte **cinq** frames de
    211 octets. Un inventaire qui lirait le cardinal au manifeste, ou qui
    estimerait le poids par « cardinal x taille moyenne », rendrait 9 : c'est
    exactement l'estimation que l'AC interdit, et c'est l'ecart entre le promis
    et le pose que l'operateur a besoin de voir.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    frames = un_enfant(lot_du_rush(inventaire, RUSH_CIBLE),
                       project_inventory.NATURE_FRAMES_EXTRAITES)

    assert frames.fichiers == CARDINAL_FRAMES[RUSH_CIBLE]
    assert frames.fichiers != CARDINAL_PROMIS_AU_MANIFESTE
    assert frames.poids == CARDINAL_FRAMES[RUSH_CIBLE] * OCTETS_FRAME[RUSH_CIBLE]


def test_AC1_2_le_poids_d_un_noeud_REPLIE_est_la_somme_de_ses_DESCENDANTS(projet):
    """AC 1.2, et c'est ce qu'un ecran affiche sur un lot replie (AC 2.2).

    Mesure sur le rush du MILIEU : un `poids_total` qui rendrait le poids du
    premier enfant, ou celui du noeud seul, passerait sur un arbre a un seul
    niveau ou a un seul enfant.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    lot = lot_du_rush(inventaire, RUSH_CIBLE)

    # **Le scan est de nouveau sous le lot** (`EPIC11-ARB-244`) : son poids
    # compte dans le lot, et le rush n'ajoute plus rien par-dessus. La veille,
    # sous `EPIC11-ARB-219`, ce test asserted deux totaux DIFFERENTS -- le lot
    # sans ses scans, le rush avec. Les deux moities restent mesurees, et
    # c'est leur EGALITE qui porte desormais l'arbitrage : un scan compte
    # deux fois -- une sous le lot, une sous le rush -- ferait grossir le
    # rush au-dela du lot, et c'est exactement la panne de double comptage
    # que la frontiere negative du test A2 interdit par ailleurs.
    poids_propre_du_lot = (
        CARDINAL_FRAMES[RUSH_CIBLE] * OCTETS_FRAME[RUSH_CIBLE]
        + sum(octets for _profil, octets in TROIS_MASTERS if octets is not None)
        + sum(octets for _rang, octets in TROIS_PLANCHES)
    )
    poids_des_scans = sum(
        cardinal * octets for _slug, cardinal, octets in SCANS_DE_LA_CIBLE)
    poids_du_lot_scanne = CARDINAL_FRAMES_SCANNEES_V2 * OCTETS_FRAME_SCANNEE_V2
    attendu_du_lot = poids_propre_du_lot + poids_des_scans + poids_du_lot_scanne

    assert lot.poids_total == attendu_du_lot
    assert lot.poids == 0, "un noeud de regroupement ne porte aucun octet en propre"
    # Les scans PESENT, et pour de bon : sans cette inegalite, l'egalite
    # ci-dessus serait aussi tenue par un arbre qui les aurait tous perdus.
    assert poids_des_scans > 0 and poids_du_lot_scanne > 0
    assert lot.poids_total > poids_propre_du_lot
    assert rush_nomme(inventaire, RUSH_CIBLE).poids_total == attendu_du_lot, (
        "le rush n'a qu'un lot : il ne peut rien porter de plus que lui")


def test_AC1_2_le_poids_TOTAL_du_projet_est_la_somme_de_TOUS_les_noeuds(projet):
    """Orphelins COMPRIS : ils occupent bel et bien le disque, et un total qui
    les exclurait ne correspondrait a rien de ce que l'operateur voit."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    assert inventaire.poids_total == sum(
        noeud.poids for noeud in inventaire.parcourir())
    assert inventaire.poids_total > sum(
        rush.poids_total for rush in inventaire.rushes), (
            "les orphelins pesent, et le total doit le dire")
    assert inventaire.fichiers_total == sum(
        noeud.fichiers for noeud in inventaire.parcourir())


def test_A2_les_NOMS_sont_ceux_du_NOMMAGE_du_depot_et_non_recomposes(projet):
    """AC 1.1 (tache A2) : les noms rendus sont ceux qu'`io.naming` produit.

    Confrontation nom a nom sur les trois familles qui ont chacune leur
    fabrique -- lot, master, tirage. Un inventaire qui recomposerait un nom
    ferait diverger l'affichage du disque au premier ajustement de convention,
    et `EPIC11-ARB-171` en a change une le 2026-09-02.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    lot = lot_du_rush(inventaire, RUSH_CIBLE)

    assert lot.nom == naming.build_lot_id(RUSH_CIBLE, CADENCES[RUSH_CIBLE])
    assert [m.nom for m in enfants_par_nature(lot, project_inventory.NATURE_MASTER)] == [
        naming.build_master_filename(
            lot_id=lot.nom, profile_id=profil, container="mov")
        for profil, _octets in TROIS_MASTERS]
    assert [p.nom for p in enfants_par_nature(lot, project_inventory.NATURE_PLANCHE)] == [
        naming.build_sheets_pdf_filename(
            PROJET, RUSH_CIBLE, lot.nom, rang, template_id=GABARIT)
        for rang, _octets in TROIS_PLANCHES]


def test_A2_le_RANG_de_version_est_lu_par_la_recette_UNIQUE_du_depot(projet):
    """`io/version_ranks.py` porte la regle « ecrite une fois pour tous », et
    `naming.rang_du_fragment_de_version` en est le lecteur. Trois rangs
    distincts sur les trois tirages : un rang toujours rendu a l'origine
    passerait sur une fabrique mono-rang."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    planches = enfants_par_nature(lot_du_rush(inventaire, RUSH_CIBLE),
                                  project_inventory.NATURE_PLANCHE)
    attendus = [version_ranks.RANG_ORIGINE if rang is None else rang
                for rang, _octets in TROIS_PLANCHES]
    assert [p.rang for p in planches] == attendus


def test_A2_un_LIEN_symbolique_pese_ZERO_et_compte_pour_UN(projet):
    """Documente plutot que subi : supprimer un lien ne libere pas les octets de
    sa cible, et les compter ferait annoncer un gain que la suppression ne
    rendrait pas."""
    dossier = project_layout.extract_frames_dir(projet, RUSH_CIBLE, CADENCES[RUSH_CIBLE])
    cible = next(iter(sorted(dossier.iterdir())))
    (dossier / "lien.tiff").symlink_to(cible)

    inventaire = project_inventory.inventorier_le_projet(projet)
    frames = un_enfant(lot_du_rush(inventaire, RUSH_CIBLE),
                       project_inventory.NATURE_FRAMES_EXTRAITES)
    assert frames.fichiers == CARDINAL_FRAMES[RUSH_CIBLE] + 1
    assert frames.poids == CARDINAL_FRAMES[RUSH_CIBLE] * OCTETS_FRAME[RUSH_CIBLE]


# ===========================================================================
# A3 -- les deux ecarts, et ils sont symetriques (AC 1.3 et AC 1.4)
# ===========================================================================


def test_AC1_3_un_objet_DECLARE_et_ABSENT_du_disque_est_NOMME(projet):
    """AC 1.3 : le master du MILIEU est declare et jamais ecrit.

    Il est **nomme** avec le chemin qu'il promet : le taire ferait croire a
    l'operateur qu'il a libere ce qu'il n'a pas libere. Meme exigence que
    `fichiers_attendus_absents` du coeur de suppression, et pour le meme motif.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    masters = enfants_par_nature(lot_du_rush(inventaire, RUSH_CIBLE),
                                 project_inventory.NATURE_MASTER)

    etats = {m.nom: m.etat for m in masters}
    absent = _nom_de_master(RUSH_CIBLE, MASTER_ABSENT)
    assert etats[absent] == project_inventory.ETAT_DECLARE_ABSENT, etats
    assert {nom for nom, etat in etats.items()
            if etat == project_inventory.ETAT_DECLARE_ABSENT} == {absent}, etats

    noeud = next(m for m in masters if m.nom == absent)
    assert noeud.chemin == f"{project_layout.OUTPUTS_DIRNAME}/{absent}"
    assert (projet / noeud.chemin).exists() is False


def test_AC1_3_un_dossier_VIDE_n_est_PAS_confondu_avec_un_dossier_ABSENT(projet):
    """**AC 1.3, le coeur de l'exigence** : « jamais confondu avec un objet de
    poids zero ».

    Les deux noeuds pesent zero et comptent zero fichier. Un seul des deux est
    une perte : le dossier de frames de `r-omega` EXISTE et il est vide -- une
    extraction qui n'a rien produit --, le dossier de frames scannees de
    `r-cible` est declare et EFFACE. Un inventaire qui ne rendrait que le poids
    les rendrait indiscernables, et l'operateur ne saurait pas lequel des deux
    reconstruire.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    vide = un_enfant(lot_du_rush(inventaire, RUSH_QUEUE),
                     project_inventory.NATURE_FRAMES_EXTRAITES)
    efface = un_enfant(
        un_enfant(lot_du_rush(inventaire, RUSH_CIBLE),
                  project_inventory.NATURE_LOT_SCANNE),
        project_inventory.NATURE_FRAMES_SCANNEES)

    assert (vide.poids, vide.fichiers) == (0, 0)
    assert (efface.poids, efface.fichiers) == (0, 0)
    assert vide.etat == project_inventory.ETAT_PRESENT
    assert efface.etat == project_inventory.ETAT_DECLARE_ABSENT
    assert vide.etat != efface.etat, "les deux pesent zero, un seul est une perte"


def test_AC1_4_l_ensemble_des_objets_PRESENTS_et_NON_DECLARES_est_EXACTEMENT_celui_la(
        projet):
    """**AC 1.4, le vrai livrable du lot.**

    Cinq objets du rush fantome, un par emplacement de l'arborescence v2. La
    mesure est une **egalite d'ensembles** avec la difference symetrique en
    message : « les frames orphelines sont vues » resterait vrai le jour ou les
    quatre autres familles cesseraient de l'etre, et le jour ou la page de
    calibration se mettrait a compter pour un orphelin.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    trouves = {(orphelin.nature, orphelin.chemin)
               for orphelin in inventaire.orphelins}
    attendus = {
        (project_inventory.NATURE_FRAMES_EXTRAITES,
         f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{_slug(RUSH_FANTOME)}"),
        (project_inventory.NATURE_FRAMES_SCANNEES,
         f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_FANTOME)}"),
        (project_inventory.NATURE_MASTER,
         f"{project_layout.OUTPUTS_DIRNAME}/"
         f"{_nom_de_master(RUSH_FANTOME, 'prores_hq')}"),
        (project_inventory.NATURE_PLANCHE,
         f"{project_layout.PLANCHES_DIRNAME}/{_nom_de_planche(RUSH_FANTOME, None)}"),
        (project_inventory.NATURE_SCAN,
         f"{project_layout.SCANS_DIRNAME}/{SLUG_SCAN_ORPHELIN}"),
        # Les trois de BORD -- sans eux, un balayage tronque reste vert.
        (project_inventory.NATURE_FRAMES_EXTRAITES,
         f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{_slug(RUSH_FANTOME_TETE)}"),
        (project_inventory.NATURE_PLANCHE,
         f"{project_layout.PLANCHES_DIRNAME}/"
         f"{_nom_de_planche(RUSH_FANTOME_TETE, None)}"),
        (project_inventory.NATURE_FRAMES_SCANNEES,
         f"{project_layout.SCAN_FRAMES_DIRNAME}/{_slug(RUSH_FANTOME_QUEUE)}"),
        (project_inventory.NATURE_MASTER,
         f"{project_layout.OUTPUTS_DIRNAME}/"
         f"{_nom_de_master(RUSH_FANTOME_QUEUE, 'prores_hq')}"),
        (project_inventory.NATURE_SCAN,
         f"{project_layout.SCANS_DIRNAME}/{SLUG_SCAN_ORPHELIN_QUEUE}"),
    }
    assert trouves == attendus, sorted(trouves ^ attendus)
    assert {orphelin.etat for orphelin in inventaire.orphelins} == {
        project_inventory.ETAT_NON_DECLARE}


def test_AC1_4_un_orphelin_porte_son_POIDS_MESURE_comme_les_autres(projet):
    """Un orphelin qu'on ne pese pas ne se supprime pas en connaissance de
    cause : c'est justement lui qui occupe le disque pour rien."""
    inventaire = project_inventory.inventorier_le_projet(projet)

    par_chemin = {o.chemin: o for o in inventaire.orphelins}

    cardinal, octets = OCTETS_ORPHELINS["frames"]
    frames = par_chemin[f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{_slug(RUSH_FANTOME)}"]
    assert (frames.poids, frames.fichiers) == (cardinal * octets, cardinal)

    cardinal, octets = OCTETS_ORPHELINS["scan"]
    scan = par_chemin[f"{project_layout.SCANS_DIRNAME}/{SLUG_SCAN_ORPHELIN}"]
    assert (scan.poids, scan.fichiers) == (cardinal * octets, cardinal)

    master = par_chemin[
        f"{project_layout.OUTPUTS_DIRNAME}/"
        f"{_nom_de_master(RUSH_FANTOME, 'prores_hq')}"]
    assert (master.poids, master.fichiers) == (OCTETS_ORPHELINS["master"], 1)


def test_AC1_4_un_lot_RETIRE_du_manifeste_laisse_ses_objets_en_ORPHELINS(projet):
    """Le scenario reel : un nettoyage manuel interrompu.

    On retire le lot cible du manifeste **sans** toucher au disque -- ce que
    fait un `git rm` a moitie, ou une edition a la main. Tout ce que ce lot
    portait doit basculer dans l'ecart, et rien ne le montrait avant cette
    story.

    La mesure porte sur le lot du MILIEU : un balayage qui sauterait la
    premiere ou la derniere entree resterait vert sur les deux autres.
    """
    manifeste = manifeste_nominal()
    manifeste["lots"] = [lot for lot in manifeste["lots"]
                         if lot["lot_id"] != _lot_id(RUSH_CIBLE)]
    ecrire_le_manifeste(projet, manifeste)

    inventaire = project_inventory.inventorier_le_projet(projet)
    chemins = {orphelin.chemin for orphelin in inventaire.orphelins}

    assert f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{_slug(RUSH_CIBLE)}" in chemins
    for rang, _octets in TROIS_PLANCHES:
        assert (f"{project_layout.PLANCHES_DIRNAME}/"
                f"{_nom_de_planche(RUSH_CIBLE, rang)}") in chemins
    for slug, _cardinal, _octets in SCANS_DE_LA_CIBLE:
        assert f"{project_layout.SCANS_DIRNAME}/{slug}" in chemins
    # Et le rush, lui, reste declare : il n'a plus aucun lot.
    assert rush_nomme(inventaire, RUSH_CIBLE).enfants == ()


def test_AC1_4_une_page_de_CALIBRATION_n_est_PAS_un_orphelin_mais_un_PDF_libre_OUI(
        projet):
    """L'exclusion **et** son volet symetrique, dans le meme test.

    `planches/` est partage entre les tirages et les pages de calibration. Une
    page de calibration n'appartient a aucun lot et n'est declaree par aucun
    inventaire : la compter ferait montrer un faux orphelin a **tout** projet
    calibre. Sans le volet symetrique, un filtre devenu trop large -- « aucun
    fichier de `planches/` n'est un orphelin » -- serait vert ici.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    noms = {orphelin.nom for orphelin in inventaire.orphelins}

    calibration = naming.build_calibration_pdf_filename(PROJET, CHAINE_DE_SCAN)
    assert calibration.endswith(naming.CALIBRATION_PDF_SUFFIX)
    assert calibration not in noms, noms
    assert (projet / project_layout.PLANCHES_DIRNAME / calibration).is_file()
    assert _nom_de_planche(RUSH_FANTOME, None) in noms, noms


def test_AC1_4_un_fichier_de_travail_du_POC_n_est_PAS_un_master_mais_un_MMU_OUI(
        projet):
    """Meme forme, sur `outputs/`, qui est partage lui aussi.

    Le chemin POC `poc process-scan` y ecrit des `scan_frame_*`, et
    `detection.aruco` les y supprime : ce ne sont pas des objets de cet
    inventaire. Le marqueur de master est **lu du nommage**
    (`naming.MASTER_FILENAME_MARKER`), jamais recopie ici.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    noms = {orphelin.nom for orphelin in inventaire.orphelins}

    assert naming.MASTER_FILENAME_MARKER not in FICHIER_DU_POC
    assert FICHIER_DU_POC not in noms, noms
    assert (projet / project_layout.OUTPUTS_DIRNAME / FICHIER_DU_POC).is_file()
    orphelin = _nom_de_master(RUSH_FANTOME, "prores_hq")
    assert naming.MASTER_FILENAME_MARKER in orphelin
    assert orphelin in noms, noms


def test_AC1_4_un_lot_dont_le_RUSH_n_est_pas_declare_reste_VISIBLE(projet):
    """Le seul ecart INTERNE au manifeste, dit plutot que tu.

    Un lot dont le `rush_id` ne figure dans aucune entree de `rushes[]`
    disparaitrait de l'arbre entier si on le rattachait a un rush inexistant :
    ses objets ne seraient ni dans l'arbre (pas de parent) ni parmi les
    orphelins (ils sont declares). Il recoit donc son rush, marque non declare
    et pose **apres** les rushes declares.
    """
    manifeste = manifeste_nominal()
    manifeste["rushes"] = [rush for rush in manifeste["rushes"]
                           if rush["rush_id"] != RUSH_CIBLE]
    ecrire_le_manifeste(projet, manifeste)

    inventaire = project_inventory.inventorier_le_projet(projet)
    assert [rush.nom for rush in inventaire.rushes] == [
        RUSH_TETE, RUSH_QUEUE, RUSH_CIBLE]
    orphelin = rush_nomme(inventaire, RUSH_CIBLE)
    assert orphelin.etat == project_inventory.ETAT_NON_DECLARE
    assert [lot.nom for lot in lots_du_rush(inventaire, RUSH_CIBLE)] == [
        _lot_id(RUSH_CIBLE)]
    # Ses scans le suivent, **par son LOT** (`EPIC11-ARB-244`) : un rush non
    # declare n'ampute pas la branche. La veille, sous `EPIC11-ARB-219`, ils
    # etaient ses enfants directs -- c'est le seul mot qui change ici.
    assert [scan.nom for scan in scans_du_lot(inventaire, RUSH_CIBLE)] == [
        slug for slug, _c, _o in SCANS_DE_LA_CIBLE]
    assert scans_PENDUS_AU_RUSH(inventaire, RUSH_CIBLE) == []


# ===========================================================================
# L'ACCORD avec `project_maintenance` -- une filiation, un lieu
# ===========================================================================


def test_A2_la_FILIATION_est_EXACTEMENT_celle_que_la_SUPPRESSION_lit(projet):
    """`EPIC11-ARB-108` : « il n'y a pas de mecanisme different par objet ».

    L'inventaire lit la filiation d'un lot par les fonctions de
    `project_maintenance` plutot que d'en rediger une seconde -- « deux copies
    d'une meme regle divergent au premier ajustement » (story 11.6). Ce test
    confronte les deux lectures sur le lot du MILIEU : les annexes que
    l'inventaire montre sont **exactement** celles que
    `remove_project_element(dry_run=True)` supprimerait ou signalerait absentes.

    La comparaison porte sur les annexes (masters et tirages) et sur les
    dossiers de scan, pas sur les frames : le rapport de suppression enumere
    les frames **fichier par fichier**, la ou l'inventaire rend leur dossier.
    Les deux cardinaux sont confrontes a la place.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    lot = lot_du_rush(inventaire, RUSH_CIBLE)
    rapport = project_maintenance.remove_project_element(
        projet, lot_id=_lot_id(RUSH_CIBLE))
    assert rapport.dry_run is True and rapport.supprime is False

    frames = un_enfant(lot, project_inventory.NATURE_FRAMES_EXTRAITES)
    # Le rapport porte une liste PLATE depuis `EPIC11-ARB-199` (story 11.13) :
    # ce test n'a jamais eu besoin du classement par nature, il n'en tirait
    # qu'un ensemble de chemins.
    tous = set(rapport.fichiers_a_supprimer)
    sous_les_frames = {chemin for chemin in tous
                       if chemin.startswith(f"{frames.chemin}/")}
    assert len(sous_les_frames) == frames.fichiers

    annexes_de_l_inventaire = {
        enfant.chemin for enfant in lot.enfants
        if enfant.nature in (project_inventory.NATURE_MASTER,
                             project_inventory.NATURE_PLANCHE)}
    annexes_du_rapport = (tous - sous_les_frames) | set(
        rapport.fichiers_attendus_absents)
    assert annexes_de_l_inventaire == annexes_du_rapport, sorted(
        annexes_de_l_inventaire ^ annexes_du_rapport)

    # **Les scans sont enfants du lot** (`EPIC11-ARB-244`) : ils se lisent sur
    # le LOT, comme les masters et les tirages -- c'est-a-dire au meme endroit
    # que la SUPPRESSION les lit, qui les a toujours rattaches au lot
    # (`_scans_du_lot` de `project_maintenance`). La filiation que la
    # suppression suit n'a jamais change ; c'est l'inventaire qui s'en etait
    # ecarte une journee sous `EPIC11-ARB-219`, et l'egalite ci-dessous le
    # mesure.
    scans_de_l_inventaire = {
        enfant.chemin
        for enfant in scans_du_lot(inventaire, RUSH_CIBLE)
        if enfant.etat == project_inventory.ETAT_PRESENT}
    assert scans_de_l_inventaire == set(rapport.dossiers_de_scan), sorted(
        scans_de_l_inventaire ^ set(rapport.dossiers_de_scan))


def test_A2_les_HUIT_natures_de_l_inventaire_sont_CELLES_DU_VOCABULAIRE():
    """`project_inventory.NATURE_*` est un HOMONYME sans rapport avec git.

    **Story 11.14** : la table adopte le vocabulaire d'Egan
    (`EPIC11-ARB-214`, `EPIC11-ARB-220`). `frames_rescannees` -- un mot qui
    n'etait celui de personne -- devient `frames_scannees`, et le lot scanne
    devient un OBJET a part entiere. Le litteral ci-dessous est donc le
    vocabulaire tranche, ecrit a la main pour qu'un renommage silencieux de la
    table rougisse ici.

    La story 11.13 (`EPIC11-ARB-199`) retire les trois `NATURE_*` de
    `project_maintenance` -- pointeur LFS, fichier local suivi par git,
    donnees non suivies. Celles-ci nomment des objets de projet et ne
    concernent en rien le suivi par git : elles ne bougent pas, et aucun banc
    ne le mesurait (`grep -rn 'project_inventory.NATURES' tests/` ne rendait
    rien avant ce test).

    **Litteral ecrit A LA MAIN, confronte au tuple publie.** Comparer `NATURES`
    a lui-meme, ou a `__all__` qui en derive, serait le test tautologique que
    la campagne de la 5.9 a trouve sur la constante centrale de la calibration
    (CLAUDE.md, regle 5).

    **Difference symetrique et non inclusion** : une inclusion laisserait
    passer une nature de trop exactement comme une nature perdue.
    """
    attendues = ("rush", "lot", "frames_extraites", "master", "planche",
                 "scan", "lot_scanne", "frames_scannees")
    assert set(project_inventory.NATURES) == set(attendues), sorted(
        set(project_inventory.NATURES) ^ set(attendues))
    # L'ORDRE aussi : le tuple est publie, un consommateur peut en dependre.
    assert project_inventory.NATURES == attendues
    # Et chaque constante nommee porte bien la valeur attendue -- le tuple
    # pourrait etre juste alors qu'une constante aurait ete renommee.
    assert project_inventory.NATURE_RUSH == "rush"
    assert project_inventory.NATURE_LOT == "lot"
    assert project_inventory.NATURE_FRAMES_EXTRAITES == "frames_extraites"
    assert project_inventory.NATURE_MASTER == "master"
    assert project_inventory.NATURE_PLANCHE == "planche"
    assert project_inventory.NATURE_SCAN == "scan"
    assert project_inventory.NATURE_LOT_SCANNE == "lot_scanne"
    assert project_inventory.NATURE_FRAMES_SCANNEES == "frames_scannees"


def test_A2_l_ensemble_EXACT_des_lectures_empruntees_a_project_maintenance():
    """Ce que cet inventaire emprunte, et rien de plus.

    Une egalite et non une appartenance : le jour ou une sixieme fonction
    privee serait empruntee -- ou ou l'une de celles-ci serait recopiee sur
    place --, ce test le dit. C'est la seule mesure qui empeche l'emprunt de
    devenir une seconde redaction par accretion.
    """
    arbre = ast.parse(MODULE_DE_COEUR.read_text(encoding="utf-8"))
    empruntes = {
        alias.name
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.ImportFrom)
        and (noeud.module or "").endswith("project_maintenance")
        for alias in noeud.names
    }
    attendus = {"ProjectMaintenanceError", "_Declares", "_masters_declares",
                "_planche_pdf_declaree", "_scans_du_lot", "_sous_le_projet"}
    assert empruntes == attendus, sorted(empruntes ^ attendus)
    for nom in attendus:
        assert hasattr(project_maintenance, nom), nom


# ===========================================================================
# A4 -- la table de refus publiee, mesuree DANS LES DEUX SENS (AC 1.6)
# ===========================================================================


def _projet_sans_dossier(tmp_path):
    return tmp_path / "aucun-projet"


def _projet_sans_manifeste(tmp_path):
    dossier = tmp_path / "vide"
    dossier.mkdir()
    return dossier


def _manifeste_illisible(tmp_path):
    dossier = tmp_path / "casse"
    dossier.mkdir()
    (dossier / MANIFEST_FILENAME).write_text("{ ceci n'est pas du json",
                                             encoding="utf-8")
    return dossier


def _manifeste_incoherent(tmp_path):
    dossier = tmp_path / "incoherent"
    dossier.mkdir()
    (dossier / MANIFEST_FILENAME).write_text(
        json.dumps({"project_id": PROJET, "lots": {"pas": "une liste"}}),
        encoding="utf-8")
    return dossier


def _chemin_declare_hors_du_projet(tmp_path):
    dossier = tmp_path / "evasion"
    dossier.mkdir()
    (dossier / MANIFEST_FILENAME).write_text(
        json.dumps({
            "project_id": PROJET,
            "rushes": [{"rush_id": RUSH_CIBLE}],
            "lots": [{"lot_id": "L", "rush_id": RUSH_CIBLE,
                      "frames_dir": "../../ailleurs"}]}),
        encoding="utf-8")
    return dossier


#: Un scenario par entree de la table, et le refus qu'il DOIT lever. La table
#: se mesure **dans les deux sens** : chaque entree est reellement levable
#: (ci-dessous), et l'ensemble des refus levables ne deborde pas la table
#: (:func:`test_AC1_6_l_ensemble_des_refus_LEVABLES_est_EXACTEMENT_la_table`).
SCENARIOS_DE_REFUS = {
    project_inventory.ProjetIntrouvable: _projet_sans_dossier,
    project_inventory.ManifesteIntrouvable: _projet_sans_manifeste,
    project_inventory.ManifesteIllisible: _manifeste_illisible,
    project_inventory.ManifesteIncoherent: _manifeste_incoherent,
    project_maintenance.ProjectMaintenanceError: _chemin_declare_hors_du_projet,
}


@pytest.mark.parametrize("refus", list(SCENARIOS_DE_REFUS),
                         ids=lambda classe: classe.__name__)
def test_AC1_6_chaque_refus_de_la_table_est_REELLEMENT_levable(tmp_path, refus):
    """Premier sens : une table qui nomme un refus qu'aucun chemin ne leve est
    un vocabulaire mort, et un ecran qui l'afficherait ne le montrerait jamais.

    `type(...) is refus` et non `isinstance` : une hierarchie qui ferait
    remonter la sous-classe la plus generale passerait sinon pour chacune de
    ses filles, et la table ne distinguerait plus rien.
    """
    with pytest.raises(project_inventory.REFUS_DU_COEUR) as leve:
        project_inventory.inventorier_le_projet(SCENARIOS_DE_REFUS[refus](tmp_path))
    assert type(leve.value) is refus, type(leve.value)
    assert str(leve.value), "un refus sans motif n'offre aucune issue"


def test_AC1_6_l_ensemble_des_refus_LEVABLES_est_EXACTEMENT_la_table(tmp_path):
    """Second sens : l'ensemble mesure, jamais l'appartenance.

    « Chacun de ces cinq refus se leve » resterait vrai le jour ou un sixieme
    refus non publie s'ajouterait au module -- et la TUI, qui ne peut pas
    importer `cli` et lit donc cette table, ne saurait pas l'attraper.
    """
    leves = set()
    for refus, scenario in SCENARIOS_DE_REFUS.items():
        with pytest.raises(Exception) as attrape:  # noqa: PT011 -- on MESURE la classe
            project_inventory.inventorier_le_projet(scenario(tmp_path))
        leves.add(type(attrape.value))
    table = set(project_inventory.REFUS_DU_COEUR)
    assert leves == table, sorted(
        classe.__name__ for classe in leves ^ table)


def test_AC1_6_les_classes_que_le_module_LEVE_sont_EXACTEMENT_les_siennes():
    """La table publie ce qu'un appelant doit attraper, pas ce que ce fichier
    ecrit -- et l'ecart entre les deux se mesure au lieu de se supposer.

    Lecture a l'AST de tous les `raise` du module : les quatre refus propres y
    sont, et **rien d'autre**. `ProjectMaintenanceError` n'y figure pas parce
    qu'elle **traverse** depuis la filiation empruntee -- exactement comme
    `scan_detect.REFUS_DU_COEUR` publie les refus de `scan_ingest`.
    """
    arbre = ast.parse(MODULE_DE_COEUR.read_text(encoding="utf-8"))
    leves = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Raise) or noeud.exc is None:
            continue
        cible = noeud.exc.func if isinstance(noeud.exc, ast.Call) else noeud.exc
        leves.add(getattr(cible, "id", None) or getattr(cible, "attr", None))

    propres = {classe.__name__ for classe in project_inventory.REFUS_DU_COEUR
               if issubclass(classe, project_inventory.InventaireError)}
    assert leves == propres, sorted(leves ^ propres)
    assert project_maintenance.ProjectMaintenanceError.__name__ not in leves
    assert project_maintenance.ProjectMaintenanceError in project_inventory.REFUS_DU_COEUR


def test_AC1_6_la_lecture_des_raise_MORD_sur_un_module_fautif(tmp_path):
    """Volet symetrique : la mesure ci-dessus regarde bien quelque chose.

    Sans lui, un `ast.Raise` mal lu -- un nom de champ change, un `walk`
    casse -- rendrait l'ensemble des classes levees VIDE, donc l'egalite
    ci-dessus fausse... ou vraie, le jour ou le module cesserait de lever quoi
    que ce soit. Les deux formes sont mesurees : la prose qui nomme une classe
    sans la lever ne compte pas, le `raise` compte.
    """
    def leves(source: str) -> set[str]:
        arbre = ast.parse(source)
        trouves = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Raise) and noeud.exc is not None:
                cible = (noeud.exc.func if isinstance(noeud.exc, ast.Call)
                         else noeud.exc)
                trouves.add(getattr(cible, "id", None)
                            or getattr(cible, "attr", None))
        return trouves

    assert leves(
        '"""Ce module parle de RefusInvente sans jamais le lever."""\n'
        "MOTIF = 'RefusInvente'\n") == set()
    assert leves("class RefusInvente(RuntimeError): pass\n"
                 "def agir():\n"
                 "    raise RefusInvente('motif')\n") == {"RefusInvente"}


def test_AC1_6_la_table_est_NON_VIDE_et_ne_porte_que_des_exceptions():
    """Une table vide attraperait tout de la meme facon : rien.

    Et `pytest.raises(TABLE)` exige des classes d'exception -- une entree qui
    n'en serait pas ferait rougir les tests ci-dessus pour une raison qui n'est
    pas la leur.
    """
    assert project_inventory.REFUS_DU_COEUR, "volet symetrique : la table est vide"
    for classe in project_inventory.REFUS_DU_COEUR:
        assert isinstance(classe, type) and issubclass(classe, BaseException), classe


# ===========================================================================
# A5 -- la frontiere `cli`, et son volet symetrique (AC 1.5)
# ===========================================================================


def _appelle_cli(chemin: Path) -> list[str]:
    """Les noms par lesquels ce module referencerait `cli.py`.

    Le predicat est celui de `tests/unit/tui/test_frontiere_cli.py`, mot pour
    mot : un import `mixed_media_utility.cli`, un `from ... import cli`, ou un
    acces d'attribut `.cli`. Le reprendre a l'identique est delibere -- deux
    predicats pour un seul interdit divergeraient, et c'est le module non
    couvert par le plus strict des deux qui passerait.
    """
    noms = identifiants(chemin)
    return sorted(n for n in noms if n == "cli" or n.endswith(".cli"))


def test_AC1_5_le_module_de_coeur_n_appelle_JAMAIS_cli():
    """AC 1.5 (`EPIC11-ARB-67`) : la TUI a interdiction d'importer `cli`, donc
    ce point d'entree doit etre atteignable sans lui.

    Les fonctions de `cli.py` impriment sur `stderr` et rendent un code retour :
    les appeler depuis une TUI enverrait des lignes **sous** l'ecran dessine, et
    rendrait un entier la ou l'interface a besoin d'un document ou d'un refus
    nomme.
    """
    assert _appelle_cli(MODULE_DE_COEUR) == []


def test_AC1_5_la_mesure_de_la_frontiere_cli_MORD_sur_un_module_fautif(tmp_path):
    """AC 1.5, volet symetrique, sur les QUATRE formes de violation.

    Et la prose innocente au milieu : une garde qui grepperait le texte
    declarerait fautif un module sur son seul docstring -- celui de ce
    module-ci nomme `cli` pour dire qu'il ne l'appelle pas -- et serait donc
    inapplicable au depot reel.
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        '"""Ce module parle de cli.py et de mixed_media_utility.cli sans les'
        ' appeler."""\n'
        "MESSAGE = 'voir cli.py pour le detail'\n",
        encoding="utf-8")
    assert _appelle_cli(innocent) == [], "la prose n'est pas un appel"

    for source in (
        "from mixed_media_utility import cli\n",
        "import mixed_media_utility.cli\n",
        "from mixed_media_utility import cli as noyau\nnoyau.scan_command(None)\n",
        "import mixed_media_utility as mmu\nmmu.cli.scan_command(None)\n",
    ):
        fautif = tmp_path / "fautif.py"
        fautif.write_text(source, encoding="utf-8")
        assert _appelle_cli(fautif) != [], source


def _importer_dans_un_processus_neuf(programme: str):
    """Derouler `programme` dans un interpreteur neuf, `src/` au chemin.

    Un sous-processus et non le banc : ici, `cli` est deja importe par d'autres
    tests du dossier, et `sys.modules` ne dirait plus rien.
    """
    return subprocess.run(
        [sys.executable, "-c", programme],
        cwd=str(RACINE), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(RACINE / "src")})


def test_AC1_5_une_INTERFACE_atteint_l_inventaire_SANS_charger_cli():
    """AC 1.5 par un import REEL, et non par lecture de source.

    La frontiere de source ne voit que le module lui-meme ; celle-ci voit toute
    la fermeture transitive de ses imports. Un module de coeur qui n'appelle
    pas `cli` mais qui importerait un module qui l'appelle rendrait la premiere
    verte et celle-ci rouge.
    """
    acheve = _importer_dans_un_processus_neuf(
        "import sys\n"
        "from mixed_media_utility import project_inventory\n"
        "assert callable(project_inventory.inventorier_le_projet)\n"
        "charges = sorted(m for m in sys.modules\n"
        "                 if m.startswith('mixed_media_utility'))\n"
        "assert 'mixed_media_utility.cli' not in charges, charges\n"
        "assert not [m for m in charges if '.tui' in m or '.gui' in m], charges\n"
        "sys.stderr.write('ok')\n")
    assert acheve.returncode == 0, acheve.stderr
    assert acheve.stderr.strip().endswith("ok")


def test_AC1_5_le_module_qui_A_LE_DROIT_d_importer_cli_l_IMPORTE_BIEN():
    """**Volet symetrique de la sonde ci-dessus**, et il n'est pas decoratif.

    La sonde precedente cherche le nom `mixed_media_utility.cli` dans
    `sys.modules`. Si ce nom etait faux -- un module renomme, une faute de
    frappe --, elle serait verte pour toujours **sans rien mesurer**. Celui-ci
    montre que le meme montage VOIT bel et bien `cli` quand elle est chargee :
    c'est la seule chose qui rend la mesure precedente concluante.

    `cli.py` est la troisieme interface du depot, et c'est elle qui a le droit
    d'importer -- et d'etre importee. Elle atteint le meme point d'entree de
    coeur : le contrat est « la TUI **peut**, pas la TUI **doit** ».
    """
    acheve = _importer_dans_un_processus_neuf(
        "import sys\n"
        "from mixed_media_utility import cli\n"
        "charges = sorted(m for m in sys.modules\n"
        "                 if m.startswith('mixed_media_utility'))\n"
        "assert 'mixed_media_utility.cli' in charges, charges\n"
        "sys.stderr.write('ok')\n")
    assert acheve.returncode == 0, acheve.stderr
    assert acheve.stderr.strip().endswith("ok")


# ===========================================================================
# A2 (frontiere) -- aucun nom de l'arborescence n'est un LITTERAL du module
# ===========================================================================

#: Les fragments dont le depot est PROPRIETAIRE, chacun lu de sa source unique.
#: Les recopier ici serait ecrire une seconde convention -- ce que le depot a
#: paye sur la borne de `CANONICAL_ID_MAX_LENGTH`, recopiee dans une prose qui
#: a perime.
FRAGMENTS_A_LIRE_ET_NON_A_ECRIRE = (
    project_layout.EXTRACT_FRAMES_DIRNAME,
    project_layout.SCAN_FRAMES_DIRNAME,
    project_layout.SCANS_DIRNAME,
    project_layout.PLANCHES_DIRNAME,
    project_layout.OUTPUTS_DIRNAME,
    project_layout.VERSIONS_DIRNAME,
    project_layout.LOGS_DIRNAME,
    naming.MASTER_FILENAME_MARKER,
    naming.CALIBRATION_PDF_SUFFIX,
    naming.LEGACY_SHEETS_MARKER,
    naming.SCAN_FRAME_PREFIX,
    naming.EXTRACTED_FRAME_SUFFIX,
    MANIFEST_FILENAME,
)


@pytest.mark.parametrize("fragment", FRAGMENTS_A_LIRE_ET_NON_A_ECRIRE)
def test_A2_aucun_nom_de_l_arborescence_n_est_un_LITTERAL_du_module(fragment):
    """Tache A2 : « les NOMS se lisent d'`io.naming`, jamais reconstruits ».

    Mesure sur les chaines du CODE, docstrings exclus : la prose de ce module
    explique justement de quels dossiers il parle, et un grep de texte y
    mordrait.

    **Ce que cette mesure ne voit pas, dit plutot que tu** : une composition par
    morceaux (`f"{racine}fra" + "mes"`) lui echappe. C'est le prix d'une mesure
    de forme ; ce qu'elle attrape est le geste ordinaire, qui est de retaper la
    chaine.
    """
    litteraux = chaines_de_code(MODULE_DE_COEUR)
    assert fragment not in litteraux, (
        f"{fragment!r} est recopie dans le code au lieu d'etre lu de sa source")


def test_A2_le_module_ne_COMPOSE_aucun_chemin_a_la_main():
    """Second volet de la meme frontiere : aucun separateur de chemin.

    Un litteral portant `/` ou `\\` est la signature d'un chemin assemble a la
    main -- exactement ce que `io.project_layout` existe pour empecher
    (« eviter que l'appelant recompose `project_dir / "outputs"` a la main, ce
    qui redoublerait la constante »).
    """
    fautifs = [litteral for litteral in chaines_de_code(MODULE_DE_COEUR)
               if "/" in litteral or "\\" in litteral]
    assert fautifs == [], fautifs


def test_A2_la_mesure_des_LITTERAUX_MORD_sur_un_module_fautif(tmp_path):
    """Volet symetrique : `chaines_de_code` voit le code et pas la prose.

    Sans lui, un lecteur devenu muet rendrait les quatorze frontieres ci-dessus
    vertes en ne mesurant plus rien.
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        f'"""Ce module explique le dossier {project_layout.EXTRACT_FRAMES_DIRNAME}."""\n'
        f"# Encore un commentaire qui nomme {project_layout.EXTRACT_FRAMES_DIRNAME}.\n"
        "from mixed_media_utility.io import project_layout\n"
        "RACINE = project_layout.EXTRACT_FRAMES_DIRNAME\n",
        encoding="utf-8")
    assert project_layout.EXTRACT_FRAMES_DIRNAME not in chaines_de_code(innocent)

    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        '"""Un module qui retape la convention."""\n'
        f"RACINE = {project_layout.EXTRACT_FRAMES_DIRNAME!r}\n"
        f"CHEMIN = {'a/b'!r}\n",
        encoding="utf-8")
    litteraux = chaines_de_code(fautif)
    assert project_layout.EXTRACT_FRAMES_DIRNAME in litteraux
    assert [x for x in litteraux if "/" in x] == ["a/b"]


# ===========================================================================
# Story 11.14, lot B2 -- le vocabulaire est ecrit UNE fois, et il est mesure
# ===========================================================================


def _constantes_de_module(chemin: Path) -> dict[str, str]:
    """Les constantes de niveau MODULE de `chemin` qui valent une chaine.

    Niveau module seulement : une variable locale porte une valeur de passage,
    elle ne REDIGE pas un vocabulaire. C'est la lecon du premier faux depart du
    lot A, qui comptait `frames_ecrites` et `total_frames` parmi les noms du
    vocabulaire et rendait 331 noms pour `lot`.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouvees: dict[str, str] = {}
    for noeud in arbre.body:
        cibles: list[ast.expr] = []
        if isinstance(noeud, ast.Assign):
            cibles = list(noeud.targets)
        elif isinstance(noeud, ast.AnnAssign):
            cibles = [noeud.target]
        valeur = getattr(noeud, "value", None)
        if not isinstance(valeur, ast.Constant) or not isinstance(valeur.value, str):
            continue
        for cible in cibles:
            if isinstance(cible, ast.Name):
                trouvees[cible.id] = valeur.value
    return trouvees


#: **Ce qui porte la MEME chaine sans REDIGER une nature d'objet**, nomme un
#: par un avec son motif. Le mot `scan` designe ici tantot un etat de lot,
#: tantot une provenance, tantot un nom de champ de formulaire : ce sont des
#: homonymes, pas un second vocabulaire.
HOMONYMES_NOMMES = {
    ("src/mixed_media_utility/encode.py", "MINIMUM_LOT_STATE"):
        "un ETAT de lot au manifeste, pas une nature d'objet",
    ("src/mixed_media_utility/io/reconstruction.py", "ORIGIN_SCAN"):
        "une PROVENANCE de reconstruction",
    ("src/mixed_media_utility/io/scan_manifest.py", "SCAN_LOT_STATE"):
        "le meme etat de lot que ci-dessus, du cote qui l'ecrit",
    ("src/mixed_media_utility/scan_previz.py", "SCAN_PREVIZ_KIND"):
        "un genre de previsualisation",
    ("src/mixed_media_utility/tui/atelier_scan_calibrate.py", "CHAMP_SCAN"):
        "un nom de CHAMP de formulaire TUI",
    ("src/mixed_media_utility/tui/atelier_scan_completion.py", "CHAMP_LOT"):
        "un nom de CHAMP de formulaire TUI",
    # **Celui-la EST un second vocabulaire d'objets, et il est HORS PERIMETRE.**
    # `gui/` attend la reponse a `Q6` (story 11.14, « Ce que cette story NE fait
    # PAS ») : Egan a nomme « la CLI et la TUI ». Il est nomme ici plutot que tu,
    # et le jour ou `Q6` repond, ces quatre lignes partent avec lui.
    ("src/mixed_media_utility/gui/modele_chutier.py", "TYPE_RUSH"):
        "RACCORD Q6 -- second vocabulaire d'objets dans `gui/`, hors perimetre",
    ("src/mixed_media_utility/gui/modele_chutier.py", "TYPE_LOT"):
        "RACCORD Q6 -- idem",
    ("src/mixed_media_utility/gui/modele_chutier.py", "TYPE_PLANCHE"):
        "RACCORD Q6 -- idem",
    ("src/mixed_media_utility/gui/modele_chutier.py", "TYPE_SCAN"):
        "RACCORD Q6 -- idem",
}


def test_AC1_2_la_table_des_HOMONYMES_ne_couvre_que_ce_qui_EXISTE():
    """**Volet symetrique de la frontiere ci-dessous**, et il n'est pas
    decoratif : une exception qui survit a la disparition de son motif est un
    trou permanent dans la frontiere. Le jour ou `Q6` sortira `gui/` du
    perimetre, ces lignes-la devront partir, et ce test le dira.
    """
    perimees = [
        cle for cle in HOMONYMES_NOMMES
        if _constantes_de_module(RACINE / cle[0]).get(cle[1]) not in
        set(project_inventory.NATURES)
    ]
    assert perimees == [], perimees


def test_AC1_2_frontiere_negative_AUCUN_autre_module_ne_REDIGE_une_nature():
    """**AC 1.2** -- « une interface le LIT, elle ne le REDIGE pas ».

    La frontiere porte sur les VALEURS publiees : un module de `src/` qui
    declarerait une constante valant `"lot_scanne"` ou `"frames_scannees"`
    aurait ouvert un second registre, et les deux divergeraient au premier
    ajout -- le defaut exact que la story 11.6 a paye sur la table des refus de
    `scan_detect`.

    Elle ne compare PAS des noms de constantes : `gui/modele_zone_tampon.py`
    porte lui aussi un tuple `NATURES`, celui des natures de FICHIER d'une zone
    tampon (`dossier`, `pdf`, `image`, `etrangere`). C'est un homonyme, ses
    valeurs sont disjointes de celles-ci, et une frontiere par nom de constante
    l'aurait attrape a tort tout en laissant passer une redaction faite sous un
    autre nom.

    **Les exceptions sont NOMMEES ici, une par une, avec leur motif** (AC 6.1 :
    « celles qui ne designent pas un des sept objets en sortent, AVEC la liste
    de ce qui sort »). Une exception par module aurait laisse passer la
    prochaine ; une exception globale n'aurait rien mesure du tout.
    """
    valeurs = set(project_inventory.NATURES)
    fautifs: list[str] = []
    for module in sorted((RACINE / "src").rglob("*.py")):
        if module == MODULE_DE_COEUR:
            continue
        relatif = module.relative_to(RACINE).as_posix()
        for nom, valeur in _constantes_de_module(module).items():
            if valeur not in valeurs:
                continue
            if (relatif, nom) in HOMONYMES_NOMMES:
                continue
            fautifs.append(f"{relatif}: {nom} = {valeur!r}")
    assert fautifs == [], fautifs


def test_AC1_4_les_natures_PRODUITES_sont_EXACTEMENT_celles_de_la_table(projet):
    """**AC 1.4, mesuree dans les DEUX sens.**

    Une inclusion ne suffirait pas, et les deux moities attrapent deux pannes
    differentes :

    * une nature produite et absente de la table, c'est un vocabulaire ecrit
      ailleurs -- ce que l'AC 1.2 interdit ;
    * une nature declaree et jamais produite, c'est une **surface morte** : le
      depot a paye exactement cela le 2026-08-31, quatre champs de ligne d'eau
      declares au schema, lus par un resolveur, ecrits par aucun chemin.

    La fabrique est donc tenue de produire les HUIT, orphelins compris.
    """
    inventaire = project_inventory.inventorier_le_projet(projet)
    produites = {noeud.nature for noeud in inventaire.parcourir()}
    attendues = set(project_inventory.NATURES)
    assert produites == attendues, sorted(produites ^ attendues)


# ===========================================================================
# Story 11.14, lot B3 -- la granularite du LOT SCANNE, cote suppression
#
# Ce banc-ci porte les mesures de `project_maintenance` que le lot B ajoute :
# `tests/unit/test_suppression_element_de_projet.py` appartient au lot C, et
# deux lots ne partagent jamais un fichier de banc (fiche 11.14, « Jamais deux
# lots sur un meme fichier de banc »). Le module est deja importe ici, et ce
# fichier confronte deja les deux lectures d'une meme filiation.
# ===========================================================================


#: **Quatre rangs, quatre poids distincts, et la cible se pose a chaque bord.**
#: Une famille a un seul rang ne demasque ni un `find` qui rend toujours le
#: premier, ni un balayage tronque (`CLAUDE.md`, regle des fabriques, point 4).
RANGS_DU_LOT_SCANNE = (1, 2, 3, 4)


def _projet_a_plusieurs_lots_scannes(
    tmp_path: Path, racine: str, rangs=RANGS_DU_LOT_SCANNE
) -> Path:
    """Un projet dont le lot `L` porte plusieurs lots scannes, sous `racine`.

    `racine` est le NOM DE DOSSIER employe : le nom neuf ou celui d'avant. Le
    meme projet fabrique des deux cotes est ce qui rend le volet symetrique de
    l'AC 2.4 mesurable -- sans lui, la frontiere negative serait satisfaite par
    un code qui ne lirait plus rien.

    Les octets different d'un rang a l'autre : un remplissage uniforme
    laisserait passer une suppression qui viserait le mauvais rang.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    for rang in rangs:
        suffixe = "" if rang == 1 else f"_v{rang}"
        dossier = projet / racine / f"L{suffixe}"
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(b"x" * (100 + rang))
    manifeste = {
        "schema_version": "2.1",
        "project_id": "p",
        "rushes": [{"rush_id": "R"}],
        "lots": [{"lot_id": "L", "rush_id": "R", "fps_target": 25.0,
                  "output_frames_dir": f"{racine}/L"}],
    }
    (projet / MANIFEST_FILENAME).write_text(
        json.dumps(manifeste), encoding="utf-8")
    return projet


@pytest.mark.parametrize(
    "racine", ("frames-scannees", "output-frames"),
    ids=("nom-neuf", "nom-d-avant"))
@pytest.mark.parametrize("rang", RANGS_DU_LOT_SCANNE)
def test_B3_la_granularite_du_LOT_SCANNE_trouve_les_DEUX_racines(
    tmp_path, racine, rang
):
    """**AC 2.4 au niveau de la SUPPRESSION**, et a chaque bord de la famille.

    Un projet ecrit sous le nom d'avant reste supprimable : c'est la moitie
    symetrique de la frontiere negative de `test_project_layout`. Sans elle,
    « le nom d'avant n'est plus jamais ecrit » serait tenu par un outil qui ne
    saurait plus rien retirer des projets deja sur le disque -- exactement la
    panne qu'`EPIC11-ARB-171` existe pour eviter.

    Le rang vise parcourt les quatre : en tete (1), au milieu (2, 3) et en
    queue (4).
    """
    projet = _projet_a_plusieurs_lots_scannes(tmp_path, racine)
    suffixe = "" if rang == 1 else f"_v{rang}"

    rapport = project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, lot_scanne=True, version=rang)

    assert rapport.supprime is True
    assert not (projet / racine / f"L{suffixe}").exists()
    # Les trois autres sont INTACTS : une suppression qui viserait le premier
    # rang de la liste passerait sur une famille a un seul element.
    for autre in RANGS_DU_LOT_SCANNE:
        if autre == rang:
            continue
        reste = "" if autre == 1 else f"_v{autre}"
        assert (projet / racine / f"L{reste}" / "f.tiff").read_bytes() == \
            b"x" * (100 + autre)


@pytest.mark.parametrize(
    "racine", ("frames-scannees", "output-frames"),
    ids=("nom-neuf", "nom-d-avant"))
def test_B3_la_LIGNE_D_EAU_du_lot_scanne_est_ECRITE_au_RETRAIT(tmp_path, racine):
    """**AC 5.3** -- « un test mesure l'ECRITURE du champ, pas sa declaration ».

    C'est le defaut exact que les trois couches de la revue du 2026-08-31 ont
    trouve sur quatre des cinq champs de ligne d'eau du depot : declares au
    schema, lus par un resolveur, **ecrits par aucun chemin**. Un champ muet en
    ecriture retourne l'arbitrage en silence -- retirer le rang le plus haut
    rendrait ce rang PAR DEFAUT et sans demande, l'inverse d'`EPIC11-ARB-92`.

    Le nom de la CLE ne bouge pas (`EPIC11-ARB-221`, arbitrage d'Egan du
    2026-09-04 : les cles du manifeste sont gelees, seules les surfaces
    changent). C'est bien son ECRITURE qui est mesuree, pas son orthographe.
    """
    projet = _projet_a_plusieurs_lots_scannes(tmp_path, racine)

    project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, lot_scanne=True, version=4)

    lot = json.loads(
        (projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))["lots"][0]
    assert lot[project_maintenance.OUTPUT_FRAMES_WATERMARK_FIELD] == 4, (
        "la ligne d'eau reste POSEE sans demande explicite : la deduire du "
        "plus haut rang restant reviendrait a liberer en silence")


@pytest.mark.parametrize(
    "racine", ("frames-scannees", "output-frames"),
    ids=("nom-neuf", "nom-d-avant"))
def test_B3_la_LIBERATION_explicite_fait_REDESCENDRE_la_ligne_d_eau(
    tmp_path, racine
):
    """Le pendant du precedent : le rang ne se rend QUE sur demande, et en
    queue (`EPIC11-ARB-92`, point 3). Sans ce volet, le test ci-dessus serait
    satisfait par un code qui poserait la ligne et ne la baisserait jamais.
    """
    projet = _projet_a_plusieurs_lots_scannes(tmp_path, racine)

    rapport = project_maintenance.remove_project_element(
        projet, lot_id="L", dry_run=False, lot_scanne=True, version=4,
        liberer_le_rang=True)

    assert rapport.rang_libere is True
    lot = json.loads(
        (projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))["lots"][0]
    assert lot[project_maintenance.OUTPUT_FRAMES_WATERMARK_FIELD] == 3


def test_B3_liberer_un_rang_du_MILIEU_reste_refuse(tmp_path):
    """Un rang ne se rend qu'en QUEUE : le refus est nomme, jamais un blocage
    sec (`EPIC11-ARB-89`), et il porte le mot de l'objet."""
    projet = _projet_a_plusieurs_lots_scannes(tmp_path, "frames-scannees")

    with pytest.raises(project_maintenance.ProjectMaintenanceError) as refus:
        project_maintenance.remove_project_element(
            projet, lot_id="L", dry_run=False, lot_scanne=True, version=2,
            liberer_le_rang=True)

    assert "lot scanne" in str(refus.value)
    assert "Aucune suppression n'a eu lieu." in str(refus.value)
    # Rien n'a bouge : un refus qui aurait deja supprime serait le pire des cas.
    assert (projet / "frames-scannees" / "L_v2" / "f.tiff").is_file()


def test_B3_un_rang_ABSENT_de_la_famille_est_refuse_avec_la_liste(tmp_path):
    """Le refus NOMME les rangs presents -- une issue, jamais un blocage sec.

    Il porte aussi le vocabulaire tranche : c'est l'exigence mesurable
    qu'`EPIC11-ARB-220` attache au retrait pur (« Attention a bien modifier les
    aides ! »), et un message de refus est une aide.
    """
    projet = _projet_a_plusieurs_lots_scannes(
        tmp_path, "frames-scannees", rangs=(1, 2))

    with pytest.raises(project_maintenance.ProjectMaintenanceError) as refus:
        project_maintenance.remove_project_element(
            projet, lot_id="L", dry_run=False, lot_scanne=True, version=4)

    message = str(refus.value)
    assert "lot scanne" in message
    assert "rescannees" not in message, (
        "le mot d'avant n'est celui de personne : ni le disque, ni le "
        "manifeste, ni Egan")
    assert "[1, 2]" in message or "1, 2" in message


# ===========================================================================
# Story 11.14, lot B4 -- un manifeste a l'ANCIENNE forme reste lisible
# ===========================================================================


#: **Ecrit EN DUR, et c'est l'exigence de l'AC 3.4.** Une fixture regeneree
#: porterait la forme NEUVE et le test serait tautologique : il mesurerait que
#: le code relit ce qu'il vient d'ecrire. Ce document-ci est fige a la main,
#: dans la forme qu'un projet ecrit AVANT la story 11.14 porte sur le disque
#: d'Egan -- `frames/` et `output-frames/` dans les VALEURS de chemin.
#:
#: Les CLES, elles, sont celles d'aujourd'hui : `EPIC11-ARB-221` (Egan,
#: 2026-09-04) gele les cles du manifeste et ne change que les surfaces. Ce
#: n'est donc pas un manifeste d'une autre version de schema -- c'est le meme
#: schema, avec les chemins d'avant.
MANIFESTE_A_L_ANCIENNE_FORME = """{
  "schema_version": "2.1",
  "project_id": "vieux-projet",
  "rushes": [{"rush_id": "rush-001"}],
  "lots": [
    {
      "lot_id": "rush-001_25",
      "rush_id": "rush-001",
      "fps_target": 25.0,
      "frames_dir": "frames/rush-001_25",
      "output_frames_dir": "output-frames/rush-001_25",
      "reconstructions": [
        {
          "ingest_slug": "scan-vieux",
          "output_frames_dir": "output-frames/rush-001_25_v2"
        }
      ]
    }
  ]
}"""


def _projet_a_l_ancienne_forme(tmp_path: Path) -> Path:
    """Le projet que le manifeste fige ci-dessus decrit, ecrit a l'ancien nom.

    Les cardinaux et les poids sont tous distincts : un appariement inverse
    entre les trois dossiers rendrait un total juste avec les mauvais noeuds si
    deux d'entre eux se ressemblaient.
    """
    projet = tmp_path / "vieux"
    projet.mkdir(parents=True)
    (projet / MANIFEST_FILENAME).write_text(
        MANIFESTE_A_L_ANCIENNE_FORME, encoding="utf-8")
    for relatif, cardinal, octets in (
        ("frames/rush-001_25", 3, 11),
        ("output-frames/rush-001_25", 2, 23),
        ("output-frames/rush-001_25_v2", 5, 37),
        ("scans/scan-vieux", 4, 41),
    ):
        dossier = projet / relatif
        dossier.mkdir(parents=True)
        for index in range(cardinal):
            (dossier / f"p{index:03d}.tiff").write_bytes(b"x" * octets)
    return projet


def test_B4_un_manifeste_a_l_ANCIENNE_forme_est_LU_en_entier(tmp_path):
    """**AC 3.4** -- « un projet portant l'ancien dossier est TOUJOURS lu ».

    Volet symetrique des frontieres negatives du lot B1 : sans lui, « le nom
    d'avant n'est plus jamais ecrit » serait tenu par un inventaire qui ne
    saurait plus rien lire. Les deux moities se mesurent, jamais une seule.

    Et rien n'est declare ORPHELIN : un projet parfaitement declare qui
    ressortirait en orphelins serait la panne inverse, celle qui ferait
    proposer a l'operateur de supprimer ce qu'il vient d'ecrire.
    """
    projet = _projet_a_l_ancienne_forme(tmp_path)

    inventaire = project_inventory.inventorier_le_projet(projet)

    assert inventaire.orphelins == (), [
        (o.nature, o.chemin) for o in inventaire.orphelins]
    lot = lot_du_rush(inventaire, "rush-001")
    extraites = un_enfant(lot, project_inventory.NATURE_FRAMES_EXTRAITES)
    assert extraites.chemin == "frames/rush-001_25"
    assert (extraites.fichiers, extraites.poids) == (3, 3 * 11)

    # Le lot scanne de rang 2 est attribue EXPLICITEMENT par le registre ; le
    # `output_frames_dir` de tete, lui, n'a qu'un seul scan possible, donc il
    # est DEDUIT. Les deux pendent bien du scan -- filiation d'`EPIC11-ARB-219`
    # qu'`EPIC11-ARB-244` laisse INTACTE ; seul le parent du scan a change, et
    # c'est le LOT qui le porte maintenant, plus le rush.
    scan = un_enfant(lot, project_inventory.NATURE_SCAN)
    assert scans_PENDUS_AU_RUSH(inventaire, "rush-001") == []
    assert scan.chemin == "scans/scan-vieux"
    lots_scannes = enfants_par_nature(scan, project_inventory.NATURE_LOT_SCANNE)
    par_chemin = {
        un_enfant(ls, project_inventory.NATURE_FRAMES_SCANNEES).chemin: ls
        for ls in lots_scannes}
    assert set(par_chemin) == {"output-frames/rush-001_25_v2"}
    assert par_chemin["output-frames/rush-001_25_v2"].rang == 2

    # Celui de tete n'etant pas attribue et le lot ayant DEJA un scan porteur,
    # il reste sous son lot plutot que d'etre devine.
    reste = un_enfant(lot, project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(
        reste, project_inventory.NATURE_FRAMES_SCANNEES).chemin == (
            "output-frames/rush-001_25")

    # Le poids TOTAL du projet compte bien les quatre dossiers, une seule fois.
    assert inventaire.poids_total == 3 * 11 + 2 * 23 + 5 * 37 + 4 * 41


def test_B4_un_manifeste_a_l_ANCIENNE_forme_reste_SUPPRIMABLE(tmp_path):
    """Le meme volet, cote suppression : un vieux projet garde ses issues.

    Un refus ici serait le blocage sec qu'`EPIC11-ARB-89` interdit -- et il
    renverrait Egan au `rm -rf` manuel que cette commande existe pour fermer.
    """
    projet = _projet_a_l_ancienne_forme(tmp_path)

    rapport = project_maintenance.remove_project_element(
        projet, lot_id="rush-001_25", dry_run=False, lot_scanne=True, version=2)

    assert rapport.supprime is True
    assert not (projet / "output-frames" / "rush-001_25_v2").exists()
    # Le jeu d'origine du meme lot est INTACT : la famille est bien bornee.
    assert (projet / "output-frames" / "rush-001_25" / "p000.tiff").is_file()
    lot = json.loads(
        (projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))["lots"][0]
    assert lot[project_maintenance.OUTPUT_FRAMES_WATERMARK_FIELD] == 2


def test_B4_le_meme_projet_a_la_forme_NEUVE_rend_le_MEME_arbre(tmp_path):
    """**Anti-vacuite du precedent.** Sans ce controle, les deux tests d'avant
    passeraient sur un code qui traiterait `output-frames/` comme un nom
    quelconque et n'aurait rien reconnu du tout : c'est le chemin declare qui
    fait le travail, pas la reconnaissance.

    Ici les deux formes sont confrontees a **structure egale** -- memes
    natures, memes cardinaux, memes poids --, seuls les chemins differant.
    """
    ancien = _projet_a_l_ancienne_forme(tmp_path / "a")
    neuf = tmp_path / "b" / "neuf"
    neuf.mkdir(parents=True)
    (neuf / MANIFEST_FILENAME).write_text(
        MANIFESTE_A_L_ANCIENNE_FORME
        .replace('"frames/', '"extract-frames/')
        .replace('"output-frames/', '"frames-scannees/'),
        encoding="utf-8")
    for relatif, cardinal, octets in (
        ("extract-frames/rush-001_25", 3, 11),
        ("frames-scannees/rush-001_25", 2, 23),
        ("frames-scannees/rush-001_25_v2", 5, 37),
        ("scans/scan-vieux", 4, 41),
    ):
        dossier = neuf / relatif
        dossier.mkdir(parents=True)
        for index in range(cardinal):
            (dossier / f"p{index:03d}.tiff").write_bytes(b"x" * octets)

    def signature(projet):
        inventaire = project_inventory.inventorier_le_projet(projet)
        return [(n.nature, n.etat, n.fichiers, n.poids, n.rang)
                for n in inventaire.parcourir()]

    assert signature(ancien) == signature(neuf)


@pytest.mark.parametrize(
    "racine, nature_attendue",
    (("frames", "frames_extraites"), ("output-frames", "frames_scannees")),
)
@pytest.mark.parametrize("position", ("tete", "milieu", "queue"))
def test_B4_un_ORPHELIN_sous_la_racine_d_AVANT_est_TROUVE(
    tmp_path, racine, nature_attendue, position
):
    """**AC 2.4, sur le chemin des orphelins** -- et il est le plus facile a
    oublier : c'est le seul ou personne ne declare rien, donc le seul ou aucun
    chemin du manifeste ne vient rattraper une racine non balayee.

    La cible est posee a CHAQUE BORD du listing, en plus du milieu : un
    balayage tronque (`[1:]` ou `[:-1]`) est un autre mode de panne qu'une
    cible au milieu ne demasque pas -- mesure du 2026-09-03, `CLAUDE.md`.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / MANIFEST_FILENAME).write_text(
        json.dumps({"schema_version": "2.1", "project_id": "p",
                    "rushes": [], "lots": []}), encoding="utf-8")
    # Trois dossiers distinguables ; le vise trie en tete, au milieu ou en
    # queue selon le parametre, sous la racine d'AVANT.
    noms = {"tete": ("a-vise", "m-autre", "z-autre"),
            "milieu": ("a-autre", "m-vise", "z-autre"),
            "queue": ("a-autre", "m-autre", "z-vise")}[position]
    for index, nom in enumerate(noms):
        dossier = projet / racine / nom
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(b"x" * (7 + index))

    inventaire = project_inventory.inventorier_le_projet(projet)

    trouves = {(o.nature, o.chemin) for o in inventaire.orphelins}
    assert trouves == {(nature_attendue, f"{racine}/{nom}") for nom in noms}, (
        sorted(trouves))


# **`test_B3_le_nom_NEUF_du_mot_cle_PRIME_sur_le_raccord_transitoire` a ete
# RETIRE avec le raccord qu'il gardait** (2026-09-04, revue 11.14 couche 1,
# finding `T1`). Il mesurait que `frames_scannees=` primait sur `frames=`
# quand les deux etaient donnes ; `frames=` n'existe plus, donc la question ne
# se pose plus. Le retrait pur est desormais mesure du cote de la SIGNATURE,
# dans `test_suppression_element_de_projet.py`
# (`test_la_SIGNATURE_du_coeur_ne_porte_AUCUN_mot_cle_RETIRE`) -- la ou vivent
# deja les trois volets CLI d'`EPIC11-ARB-220`.


# ===========================================================================
# Story 11.14, fermeture de la revue -- couche 2, findings C1 et C2
#
# **Le fil commun des quatre survivants, et il retourne la regle des
# fabriques contre elle-meme.** Les gardes non mesurees de
# `project_inventory` ne se franchissent QUE lorsqu'une valeur se REPETE (le
# meme chemin declare deux fois) ou qu'une collection depasse un element. Or
# le point 1 de la regle -- « toute fabrique de collection produit au moins
# deux elements DISTINGUABLES » -- est tenu a la lettre partout dans ce banc,
# et c'est exactement ce qui EMPECHE d'atteindre ces branches : une fabrique
# qui distingue toujours ses valeurs ne mesure rien d'un code qui existe pour
# reconcilier deux valeurs egales.
#
# La sortie n'est pas d'assouplir le point 1 -- il a ete paye trois fois --
# mais de lui ajouter son symetrique : **le doublon s'ecrit EN PLUS des
# elements distincts, jamais a leur place.** Les fabriques ci-dessous portent
# donc les deux a la fois, et chaque test le mesure.
# ===========================================================================


def _projet_a_registre_DICTE(
    tmp_path: Path,
    *,
    registre: tuple[tuple[str, str | None], ...],
    tete: str | None,
    dossiers: tuple[tuple[str, int, int], ...],
    scans: tuple[tuple[str, int, int], ...],
) -> tuple[Path, int]:
    """Un projet a UN lot, dont le registre de reconstructions est DICTE.

    Rend `(projet, poids ecrit sur le disque)`. Le second terme est la mesure
    de reference du finding `C1` : il ne depend que de ce qui est **ecrit**,
    jamais de ce que le manifeste declare. Un inventaire qui compterait un
    dossier deux fois rendrait donc un total STRICTEMENT superieur -- c'est
    le nombre meme que le module existe pour produire.

    * `registre` -- les couples `(ingest_slug, output_frames_dir | None)` de
      `lots[].reconstructions`, dans l'ordre d'ecriture. Un `None` laisse la
      cle absente : c'est un scan qui ne revendique aucun lot scanne, la
      forme d'avant `EPIC11-ARB-105` ;
    * `tete` -- le `lots[].output_frames_dir` de tete, celui de la derniere
      passe, que le manifeste n'attribue a personne ;
    * `dossiers` et `scans` -- ce qui est reellement pose sur le disque, avec
      pour chacun un cardinal et un poids par fichier qui lui sont propres.

    **Aucune valeur uniforme, et aucune somme partielle qui en recouvre une
    autre** : un noeud apparie au mauvais emplacement rougit au lieu de
    passer. `_scans_du_lot` lisant les slugs DANS L'ORDRE du registre, cet
    ordre est le contrat de tout ce qui suit.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)

    poids_du_disque = 0
    for nom, cardinal, octets in dossiers:
        dossier = projet / project_layout.SCAN_FRAMES_DIRNAME / nom
        dossier.mkdir(parents=True)
        for index in range(cardinal):
            _ecrire(dossier / f"f{index:03d}.tiff", octets)
        poids_du_disque += cardinal * octets
    for slug, cardinal, octets in scans:
        dossier = projet / project_layout.SCANS_DIRNAME / slug
        dossier.mkdir(parents=True)
        for index in range(cardinal):
            _ecrire(dossier / f"p{index:03d}.tiff", octets)
        poids_du_disque += cardinal * octets

    lot: dict = {"lot_id": "L", "rush_id": "R", "fps_target": 25.0}
    if tete is not None:
        lot["output_frames_dir"] = tete
    lot["reconstructions"] = [
        {"ingest_slug": slug} if chemin is None
        else {"ingest_slug": slug, "output_frames_dir": chemin}
        for slug, chemin in registre
    ]
    ecrire_le_manifeste(projet, {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}], "lots": [lot]})
    return projet, poids_du_disque


def _sous(nom: str) -> str:
    """Le chemin declare d'un dossier de frames scannees, jamais compose a la
    main : le nom de la racine se lit dans `project_layout`."""
    return f"{project_layout.SCAN_FRAMES_DIRNAME}/{nom}"


def _frames_scannees_de_l_arbre(inventaire) -> list[str]:
    """Les chemins de TOUS les noeuds `frames_scannees`, **avec doublons**.

    C'est le point du finding `C1` : un ensemble (`set`) rendrait le double
    comptage invisible, puisque les deux occurrences portent le meme chemin.
    La liste, elle, le montre -- et le cardinal la mesure.
    """
    return [noeud.chemin for noeud in inventaire.parcourir()
            if noeud.nature == project_inventory.NATURE_FRAMES_SCANNEES]


# ---------------------------------------------------------------------------
# C1-a -- la deduplication TETE / REGISTRE, et elle protege le NOMINAL
# ---------------------------------------------------------------------------

def test_C1_le_meme_chemin_en_TETE_et_au_REGISTRE_n_est_compte_QU_UNE_FOIS(
    tmp_path,
):
    """**Le regime NOMINAL**, celui que l'outil ecrit lui-meme.

    `io/scan_manifest.py` pose `lot["output_frames_dir"]` **puis passe cette
    meme valeur** a `_fusionner_l_historique_de_reconstruction`, qui l'ecrit
    dans l'entree du registre. Tete et entree sont donc IDENTIQUES dans tout
    manifeste que l'outil produit : la deduplication par chemin de
    `_frames_scannees_declarees` n'est pas une precaution de bord, c'est le
    seul mecanisme qui empeche chaque lot scanne d'etre compte deux fois.

    Mutant reinjecte pour fermer ce finding (`and tete not in vus` retire) :
    le lot scanne apparait DEUX fois dans l'arbre et le poids du projet
    double. Avant ce test, `293 passed` ; apres, il rougit.

    La fabrique porte le doublon **en plus** de deux chemins distincts et de
    deux scans distinguables : sans eux, l'egalite de listes ci-dessous
    serait tenue par un code qui n'aurait rien lu du tout.
    """
    projet, poids_du_disque = _projet_a_registre_DICTE(
        tmp_path,
        # `scan-a` revendique le dossier d'origine ; la TETE porte LE MEME
        # chemin. `scan-b` en revendique un autre, distinct : le doublon
        # s'ajoute aux elements distincts, il ne les remplace pas.
        registre=(("scan-a", _sous("L")), ("scan-b", _sous("L_v2"))),
        tete=_sous("L"),
        dossiers=(("L", 2, 23), ("L_v2", 5, 37)),
        scans=(("scan-a", 4, 11), ("scan-b", 3, 13)))

    inventaire = project_inventory.inventorier_le_projet(projet)

    # 1. Le POIDS -- le nombre que ce module existe pour rendre.
    assert poids_du_disque == 2 * 23 + 5 * 37 + 4 * 11 + 3 * 13
    assert inventaire.poids_total == poids_du_disque, (
        "le poids du projet ne peut pas depasser ce qui est ecrit sur le "
        "disque : un dossier compte deux fois le doublerait")

    # 2. L'ARBRE -- chaque dossier declare y figure EXACTEMENT une fois.
    lus = _frames_scannees_de_l_arbre(inventaire)
    assert sorted(lus) == [_sous("L"), _sous("L_v2")], lus

    # 3. La FILIATION -- et elle est ce qu'`EPIC11-ARB-244` exige : le scan
    #    se lit sous le LOT, et le lot scanne sous le scan.
    lot = lot_du_rush(inventaire, "R")
    assert enfants_par_nature(lot, project_inventory.NATURE_LOT_SCANNE) == [], (
        "la tete etant deja portee par `scan-a`, rien ne reste sous le lot")
    for slug, attendu in (("scan-a", _sous("L")), ("scan-b", _sous("L_v2"))):
        scanne = un_enfant(scan_nomme(inventaire, "R", slug),
                           project_inventory.NATURE_LOT_SCANNE)
        assert un_enfant(
            scanne, project_inventory.NATURE_FRAMES_SCANNEES).chemin == attendu


# ---------------------------------------------------------------------------
# C1-b -- la deduplication A L'INTERIEUR du registre
# ---------------------------------------------------------------------------

def test_C1_DEUX_entrees_du_registre_sur_le_MEME_dossier_ne_le_comptent_QU_UNE_FOIS(
    tmp_path,
):
    """Deux passes de rescan **ecrivant au meme endroit**, et c'est atteignable.

    `_fusionner_l_historique_de_reconstruction` deduplique par entree
    ENTIERE (`if entree not in anterieures`) : deux entrees de slugs
    DIFFERENTS pointant le meme `output_frames_dir` ne sont pas egales, donc
    les deux sont conservees. Le regime est celui d'un lot rescanne depuis un
    second scan sans consommer de rang neuf -- c'est-a-dire un `--overwrite`,
    l'issue meme qu'`EPIC11-ARB-89` exige d'offrir.

    Mutant reinjecte pour fermer ce finding (`or chemin in vus` retire) :
    `frames-scannees/L_v2` est compte sous `scan-a` **et** sous `scan-b`.

    Les trois slugs sont distinguables et le troisieme porte un chemin
    distinct : la repetition s'ajoute a des valeurs distinctes.
    """
    projet, poids_du_disque = _projet_a_registre_DICTE(
        tmp_path,
        registre=(("scan-a", _sous("L_v2")),
                  ("scan-b", _sous("L_v2")),   # LA MEME VALEUR, autre slug
                  ("scan-c", _sous("L_v3"))),
        tete=_sous("L"),
        dossiers=(("L", 2, 23), ("L_v2", 5, 37), ("L_v3", 3, 41)),
        scans=(("scan-a", 4, 11), ("scan-b", 3, 13), ("scan-c", 2, 17)))

    inventaire = project_inventory.inventorier_le_projet(projet)

    assert poids_du_disque == (2 * 23 + 5 * 37 + 3 * 41
                               + 4 * 11 + 3 * 13 + 2 * 17)
    assert inventaire.poids_total == poids_du_disque, (
        "deux entrees de registre sur le meme dossier ne le posent qu'une "
        "fois sur le disque : elles ne peuvent pas le peser deux fois")

    lus = _frames_scannees_de_l_arbre(inventaire)
    assert sorted(lus) == [_sous("L"), _sous("L_v2"), _sous("L_v3")], lus

    # La PREMIERE entree garde le dossier -- l'ordre du registre est le
    # contrat (`EPIC11-ARB-109`), et le second scan n'en herite pas.
    premier = un_enfant(scan_nomme(inventaire, "R", "scan-a"),
                        project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(
        premier, project_inventory.NATURE_FRAMES_SCANNEES).chemin == _sous("L_v2")
    assert enfants_par_nature(
        scan_nomme(inventaire, "R", "scan-b"),
        project_inventory.NATURE_LOT_SCANNE) == []
    # Et la tete, que personne ne revendique, reste sous SON LOT : trois
    # scans, donc aucun parent deductible (`EPIC11-ARB-90`).
    reste = un_enfant(lot_du_rush(inventaire, "R"),
                      project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(
        reste, project_inventory.NATURE_FRAMES_SCANNEES).chemin == _sous("L")


# ---------------------------------------------------------------------------
# C2 -- l'appariement positionnel de la DEDUCTION du parent
# ---------------------------------------------------------------------------

#: Les TROIS scans de la fabrique de `C2`, distinguables par leur cardinal et
#: par leur poids. Trois, et non deux : avec deux scans, le scan de tete est
#: aussi celui de queue des qu'on en retire un, et un appariement positionnel
#: ne se distingue plus d'un autre.
TROIS_SCANS_DU_LOT = (("scan-a", 4, 11), ("scan-b", 3, 13), ("scan-c", 2, 17))


@pytest.mark.parametrize("attribue", (0, 1, 2), ids=("tete", "milieu", "queue"))
def test_C2_avec_PLUSIEURS_scans_le_lot_scanne_NON_ATTRIBUE_reste_sous_son_LOT(
    tmp_path, attribue,
):
    """**`EPIC11-ARB-90` mesure** : la filiation ne se DEVINE pas.

    La docstring de `_scans_et_lots_scannes` l'ecrit mot pour mot -- « le lot
    en a plusieurs, ou aucun : le lot scanne reste alors sous son LOT » --
    et rien ne le mesurait. Deux mutants y survivaient :

    * `len(scans) == 1` -> `len(scans) >= 1` : le lot scanne non attribue est
      range **sous un scan**, c'est-a-dire devine par ressemblance ;
    * compose avec `scans[0]` -> `scans[-1]` : c'est **quel** scan l'adopte
      qui change, un appariement positionnel de collection.

    **La regle des fabriques au complet, parce qu'aucun de ses points ne
    suffit seul ici.** Trois scans DISTINGUABLES (point 1) ; la cible
    attribuee parcourt les trois positions (point 2) ; et elle passe par la
    TETE et par la QUEUE (point 4) -- ce n'est pas du zele : la garde
    `scans[0].name not in par_slug` neutralise le premier mutant quand la
    cible est en tete, et la garde symetrique neutralise le second quand elle
    est en queue. **Une seule position ne peut pas tuer les deux.**
    """
    projet, poids_du_disque = _projet_a_registre_DICTE(
        tmp_path,
        # Un seul scan revendique un dossier ; les deux autres n'en
        # revendiquent aucun (forme d'avant `EPIC11-ARB-105`).
        registre=tuple(
            (slug, _sous("L_v2") if rang == attribue else None)
            for rang, (slug, _c, _o) in enumerate(TROIS_SCANS_DU_LOT)),
        tete=_sous("L"),
        dossiers=(("L", 2, 23), ("L_v2", 5, 37)),
        scans=TROIS_SCANS_DU_LOT)

    inventaire = project_inventory.inventorier_le_projet(projet)

    assert inventaire.poids_total == poids_du_disque
    assert _frames_scannees_de_l_arbre(inventaire).count(_sous("L")) == 1

    # 1. La tete NON ATTRIBUEE reste sous son lot -- et nulle part ailleurs.
    reste = un_enfant(lot_du_rush(inventaire, "R"),
                      project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(
        reste, project_inventory.NATURE_FRAMES_SCANNEES).chemin == _sous("L")

    # 2. AUCUN scan ne la porte -- la moitie que les deux mutants franchissent,
    #    l'un par la tete de la liste, l'autre par sa queue.
    for rang, (slug, _c, _o) in enumerate(TROIS_SCANS_DU_LOT):
        portes = [
            un_enfant(scanne, project_inventory.NATURE_FRAMES_SCANNEES).chemin
            for scanne in enfants_par_nature(
                scan_nomme(inventaire, "R", slug),
                project_inventory.NATURE_LOT_SCANNE)]
        assert portes == ([_sous("L_v2")] if rang == attribue else []), (
            f"{slug} (position {rang}) porte {portes}")


def test_C2_avec_UN_SEUL_scan_la_deduction_a_bien_LIEU(tmp_path):
    """**Volet symetrique, et sans lui le test ci-dessus serait vide.**

    « Aucun scan ne porte le lot scanne non attribue » est tenu a la
    perfection par un code qui n'attacherait plus jamais rien. Ce test mesure
    l'autre moitie de la meme phrase de la docstring : « le lot n'a qu'UN
    seul scan : il n'y a alors qu'un parent possible, et le rattacher n'est
    pas une devinette mais une DEDUCTION ».
    """
    projet, poids_du_disque = _projet_a_registre_DICTE(
        tmp_path,
        registre=(("scan-a", None),),
        tete=_sous("L"),
        dossiers=(("L", 2, 23),),
        scans=(("scan-a", 4, 11),))

    inventaire = project_inventory.inventorier_le_projet(projet)

    assert inventaire.poids_total == poids_du_disque
    assert enfants_par_nature(
        lot_du_rush(inventaire, "R"),
        project_inventory.NATURE_LOT_SCANNE) == [], (
            "un seul parent possible : le lot scanne pend du scan")
    scanne = un_enfant(scan_nomme(inventaire, "R", "scan-a"),
                       project_inventory.NATURE_LOT_SCANNE)
    assert un_enfant(
        scanne, project_inventory.NATURE_FRAMES_SCANNEES).chemin == _sous("L")


# ===========================================================================
# C3 -- l'APPARIEMENT scan / LOT, le mode de panne qu'`EPIC11-ARB-244` CREE
# ===========================================================================
#
# **Ce banc n'aurait rien mesure la veille, et c'est le propos.** Sous
# `EPIC11-ARB-219`, tous les scans d'un rush arrivaient dans le meme sac --
# `noeuds_de_scan[rush_id]` -- et etaient poses a cote des lots : QUEL lot
# avait produit QUEL scan n'etait porte par aucune arete, donc aucun mauvais
# appariement n'etait possible. `EPIC11-ARB-244` cree cette arete, et avec
# elle son mode de panne : un scan range sous le mauvais lot.
#
# Toutes les fabriques du banc ci-dessus posent **un seul lot par rush** :
# elles sont donc structurellement aveugles a cet appariement -- un coeur qui
# donnerait tous les scans du rush a son PREMIER lot les tiendrait toutes
# vertes. C'est la regle des fabriques du depot, point 1 (« au moins deux
# elements distinguables ») portee au niveau du LOT, la ou elle n'etait tenue
# qu'au niveau du scan.

#: Les TROIS lots du rush `R`, et ce que chacun porte. Aucune valeur uniforme
#: nulle part : le cardinal et le poids par fichier sont propres a chaque
#: dossier et a chaque scan, si bien qu'un noeud apparie au mauvais lot rougit
#: sur un NOMBRE au lieu de passer. Trois lots, et non deux, parce qu'avec
#: deux le lot de tete est aussi celui de queue des qu'on en retire un, et
#: qu'un appariement positionnel ne se distingue alors plus d'un autre --
#: c'est le motif deja ecrit sur `TROIS_SCANS_DU_LOT`.
#:
#: Le lot du MILIEU n'a qu'un scan la ou ceux des BORDS en ont deux : c'est ce
#: qui separe un appariement permute d'un balayage tronque. Un coeur qui
#: sauterait la derniere entree de chaque registre ne perdrait rien sur le
#: milieu et perdrait un scan a chaque bord.
_LotDeBanc = tuple[str, int, int, tuple[tuple[str, int, int], ...]]

TROIS_LOTS_D_UN_RUSH: tuple[_LotDeBanc, ...] = (
    # (lot_id, cardinal de frames, octets par frame, scans du lot)
    ("L-tete",   2, 101, (("scan-tete-a", 2, 11), ("scan-tete-b", 3, 13))),
    ("L-milieu", 3, 103, (("scan-milieu", 4, 17),)),
    ("L-queue",  4, 107, (("scan-queue-a", 5, 19), ("scan-queue-b", 6, 23))),
)


def _projet_a_TROIS_LOTS_dans_UN_rush(tmp_path: Path) -> tuple[Path, int]:
    """Un rush portant TROIS lots, chacun avec ses propres scans.

    Rend `(projet, poids ecrit sur le disque)`. Comme
    :func:`_projet_a_registre_DICTE`, le second terme ne depend que de ce qui
    est **ecrit** : un scan compte sous deux lots rendrait un total
    strictement superieur.

    Aucun `output_frames_dir` n'est declare : ce banc mesure l'appariement
    scan / lot et rien d'autre, et un lot scanne y ajouterait un niveau dont
    la deduction du parent est deja mesuree ailleurs (`C2`).
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)

    poids_du_disque = 0
    lots: list[dict] = []
    for lot_id, cardinal, octets, scans in TROIS_LOTS_D_UN_RUSH:
        frames = projet / project_layout.EXTRACT_FRAMES_DIRNAME / lot_id
        for index in range(cardinal):
            _ecrire(frames / f"f{index:03d}.tiff", octets)
        poids_du_disque += cardinal * octets
        for slug, pages, octets_page in scans:
            dossier = projet / project_layout.SCANS_DIRNAME / slug
            for index in range(pages):
                _ecrire(dossier / f"p{index:03d}.tiff", octets_page)
            poids_du_disque += pages * octets_page
        lots.append({
            "lot_id": lot_id,
            "rush_id": "R",
            "fps_target": 25.0,
            "frames_dir": f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{lot_id}",
            "reconstructions": [{"ingest_slug": slug} for slug, _p, _o in scans],
        })

    ecrire_le_manifeste(projet, {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}], "lots": lots})
    return projet, poids_du_disque


def test_C3_chaque_scan_pend_de_SON_lot_et_pas_d_un_AUTRE_lot_du_rush(tmp_path):
    """**`EPIC11-ARB-244` mesure au niveau du LOT** : « le scan est le fils du
    lot qu'il reproduit » -- de CE lot-la, pas d'un lot du meme rush.

    Les trois modes de panne que ce test separe, et aucun autre test du banc
    ne les voit puisque toutes les autres fabriques n'ont qu'un lot par rush :

    * **tous les scans au meme lot** (le premier, ou le dernier) : l'egalite
      de listes rougit sur les deux autres lots ;
    * **appariement permute** -- le lot de tete recoit les scans de queue et
      reciproquement : les slugs different, et les POIDS aussi, si bien que la
      panne se voit deux fois ;
    * **balayage tronque du registre** -- la derniere entree de chaque lot est
      sautee : le milieu, qui n'a qu'un scan, le perd entierement ; les deux
      bords, qui en ont deux, perdent le second. Une cible au milieu seule ne
      demasque pas ce mode-la (point 4 de la regle des fabriques).
    """
    projet, poids_du_disque = _projet_a_TROIS_LOTS_dans_UN_rush(tmp_path)

    inventaire = project_inventory.inventorier_le_projet(projet)

    # 0. Le rush porte ses TROIS lots, dans l'ordre du manifeste, et AUCUN
    #    scan en direct -- la frontiere negative de l'arbitrage.
    assert [lot.nom for lot in lots_du_rush(inventaire, "R")] == [
        lot_id for lot_id, _c, _o, _s in TROIS_LOTS_D_UN_RUSH]
    assert scans_PENDUS_AU_RUSH(inventaire, "R") == []

    # 1. L'APPARIEMENT, lot par lot et dans l'ordre du registre.
    par_lot = {lot.nom: lot for lot in lots_du_rush(inventaire, "R")}
    for lot_id, _cardinal, _octets, scans in TROIS_LOTS_D_UN_RUSH:
        lus = enfants_par_nature(par_lot[lot_id],
                                 project_inventory.NATURE_SCAN)
        assert [scan.nom for scan in lus] == [slug for slug, _p, _o in scans], (
            f"{lot_id} porte {[s.nom for s in lus]}")
        # Et ce sont bien les DOSSIERS de ces scans-la, pas des homonymes :
        # le poids de chacun est propre a son slug.
        assert [(scan.fichiers, scan.poids) for scan in lus] == [
            (pages, pages * octets) for _slug, pages, octets in scans]

    # 2. Le POIDS de chaque lot, et les trois DIFFERENT deux a deux : une
    #    somme qui melangerait les lots tiendrait une egalite mais pas trois.
    poids_attendus = {
        lot_id: cardinal * octets + sum(p * o for _s, p, o in scans)
        for lot_id, cardinal, octets, scans in TROIS_LOTS_D_UN_RUSH
    }
    assert len(set(poids_attendus.values())) == 3, (
        "la fabrique elle-meme doit rester distinguable")
    assert {lot_id: par_lot[lot_id].poids_total
            for lot_id in poids_attendus} == poids_attendus

    # 3. Le TOTAL -- aucun scan compte deux fois, aucun perdu.
    assert inventaire.poids_total == poids_du_disque
    assert inventaire.orphelins == (), [
        (o.nature, o.chemin) for o in inventaire.orphelins]


# ---------------------------------------------------------------------------
# `EPIC11-ARB-225` -- le balayage des orphelins lit LES DEUX racines
#
# « Une garde de repli fait VARIER le drapeau dont elle depend » (`CLAUDE.md`,
# 2026-09-06). Le drapeau est l'arborescence du projet, et il a TROIS etats :
# ANCIEN (`patches/` seul), NEUF (`planches/` seul), MIXTE. La fabrique du haut
# de ce fichier ne joue que le neuf ; elle mesurerait la moitie du produit.
#
# Le mode de panne est nomme : sous une racine unique, les planches d'un projet
# ancien sont INVISIBLES a l'inventaire. C'est litteralement le defaut `E2-1`
# qu'`EPIC11-ARB-225` designe comme « le precedent a NE PAS refaire ».
# ---------------------------------------------------------------------------

#: **QUATRE planches distinguables** -- des tailles differentes, pas un
#: remplissage uniforme : une permutation ou un balayage tronque ne se voient
#: pas autrement (regle des fabriques, points 1 et 4).
PLANCHES_DE_LA_MIXITE = (
    ("aaa_planches.pdf", 111),
    ("mmm_planches_v2.pdf", 222),
    ("ttt_planches_v3.pdf", 333),
    ("zzz_planches_v4.pdf", 444),
)


def _projet_a_deux_racines(tmp_path, dossiers: tuple[str, ...]):
    """Un projet nu dont les quatre planches se repartissent sur `dossiers`.

    A tour de role : avec deux dossiers, la cible de TETE tombe dans le
    premier et celle de QUEUE dans le second, donc a chaque bord de l'ordre
    dans lequel le code parcourt ses racines.
    """
    projet = tmp_path / "projet-mixte"
    projet.mkdir(parents=True, exist_ok=True)
    for nom in dossiers:
        (projet / nom).mkdir(parents=True, exist_ok=True)
    for rang, (nom, octets) in enumerate(PLANCHES_DE_LA_MIXITE):
        _ecrire(projet / dossiers[rang % len(dossiers)] / nom, octets)
    ecrire_le_manifeste(projet, {"schema_version": "2.1",
                                 "project_id": PROJET, "rushes": [], "lots": []})
    return projet


@pytest.mark.parametrize("dossiers,etat", (
    (("patches",), "projet ANCIEN"),
    (("planches",), "projet NEUF"),
    (("planches", "patches"), "projet MIXTE"),
    (("patches", "planches"), "projet MIXTE, l'autre repartition"),
))
def test_les_planches_ORPHELINES_sortent_des_DEUX_racines(
        tmp_path, dossiers, etat):
    """Les quatre planches sont vues, quel que soit l'etat de l'arborescence.

    Le cardinal est EXACT et les poids sont confrontes un a un : un balayage
    qui rendrait le bon nombre depuis la mauvaise racine passerait un simple
    compte, pas une egalite d'ensemble.
    """
    projet = _projet_a_deux_racines(tmp_path, dossiers)

    inventaire = project_inventory.inventorier_le_projet(projet)
    planches = [o for o in inventaire.orphelins if o.nature == project_inventory.NATURE_PLANCHE]

    assert {(o.nom, o.poids) for o in planches} == set(PLANCHES_DE_LA_MIXITE), etat
    assert {o.chemin for o in planches} == {
        f"{dossiers[rang % len(dossiers)]}/{nom}"
        for rang, (nom, _octets) in enumerate(PLANCHES_DE_LA_MIXITE)
    }, etat


def test_un_projet_ANCIEN_sans_le_repli_ne_montrerait_AUCUNE_planche(tmp_path):
    """Le volet qui chiffre ce que la racine unique COUTAIT.

    Sans la seconde racine, l'inventaire d'un projet ancien annonce **zero**
    orphelin sur un dossier qui en porte quatre -- et c'est le pire des
    verdicts : l'operateur conclut que rien ne traine et efface le projet.
    """
    projet = _projet_a_deux_racines(tmp_path, ("patches",))
    assert not (projet / "planches").exists()

    inventaire = project_inventory.inventorier_le_projet(projet)

    assert len([o for o in inventaire.orphelins
                if o.nature == project_inventory.NATURE_PLANCHE]) == len(PLANCHES_DE_LA_MIXITE)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-260` -- un fichier CACHE n'est pas un objet du projet
# ---------------------------------------------------------------------------
#
# **Le regime est reel, et c'est celui d'Egan le 2026-09-06.** Son export
# ProRes/DNxHD a echoue et a laisse sur son disque
# `.TEST_FILE_7p5_mmu_dnxhr_hqx.mov.2624-0d2c0cbf1e1c.mov` -- un fichier
# d'attente d'ecriture atomique, CONSERVE EXPRES pour diagnostic. Ce nom porte
# `MASTER_FILENAME_MARKER`, donc `_orphelins` l'inventoriait comme un master non
# declare : il ne se greffait sur rien, il atterrissait en queue d'arbre sans
# lot parent, et le seul geste possible dessus menait au mur « Retirer un master
# seul du projet / Cet ecran n'existe pas encore ». Deux causes empilees sur le
# meme objet, dont celle-ci est la racine.
#
# **Regle des fabriques, ses quatre points, et ce qu'ils mordent ici** : quatre
# noms caches, aux **quatre emplacements balayes** et de **poids tous
# distincts** ; le volet qui compte n'est pas qu'ils disparaissent -- un filtre
# trop large les ferait disparaitre aussi -- mais que **rien d'autre** ne
# disparaisse avec eux, et l'egalite d'ensemble le mesure en TETE comme en
# QUEUE. Un filtre ecrit `sorted(...)[1:]` sur une liste ou le cache est
# toujours premier passerait le premier volet et tomberait sur le second.

#: Le nom exact du fichier d'attente rencontre par Egan, poids distinct de tous
#: les poids de la fabrique. Il n'est PAS recompose ici : c'est celui du
#: rapport, verbatim, et c'est ce qui fait que ce test mesure son cas.
ATTENTE_D_EGAN = ".TEST_FILE_7p5_mmu_dnxhr_hqx.mov.2624-0d2c0cbf1e1c.mov"
OCTETS_DES_CACHES = {
    "master": 3101,
    "planche": 3203,
    "dossier_de_scan": 3307,
    "dossier_de_frames": 3409,
}


def _semer_des_noms_caches(projet: Path) -> None:
    """Quatre entrees cachees, une par emplacement que `_orphelins` balaie.

    Deux fichiers et deux DOSSIERS : le filtre porte sur les deux listeurs, et
    n'en mesurer qu'un laisserait l'autre libre de reintroduire le defaut.
    """
    _ecrire(projet / project_layout.OUTPUTS_DIRNAME / ATTENTE_D_EGAN,
            OCTETS_DES_CACHES["master"])
    racine_des_planches = project_layout.racines_de_planches(projet)[0]
    _ecrire(racine_des_planches / ".planche-en-cours.pdf",
            OCTETS_DES_CACHES["planche"])
    _ecrire(projet / project_layout.SCANS_DIRNAME / ".scan-en-cours" / "p1.tiff",
            OCTETS_DES_CACHES["dossier_de_scan"])
    racine_des_frames = project_layout.racines_de_frames_extraites(projet)[0]
    _ecrire(racine_des_frames / ".frames-en-cours" / "f1.tiff",
            OCTETS_DES_CACHES["dossier_de_frames"])


def test_un_fichier_d_ATTENTE_d_ecriture_n_est_PAS_un_master_orphelin(projet):
    """Le cas d'Egan, pris par son nom reel.

    **Le volet negatif seul ne dirait rien** : un inventaire qui ne rendrait
    plus AUCUN orphelin le passerait. C'est pourquoi le master orphelin
    legitime de la fabrique est mesure **present** dans la meme assertion --
    la partition est ce qui compte, pas l'absence.
    """
    avant = project_inventory.inventorier_le_projet(projet)
    _semer_des_noms_caches(projet)
    apres = project_inventory.inventorier_le_projet(projet)

    noms = {o.nom for o in apres.orphelins}
    assert ATTENTE_D_EGAN not in noms, "le fichier d'attente est inventorie"
    assert _nom_de_master(RUSH_FANTOME, "prores_hq") in noms, (
        "le master orphelin LEGITIME a disparu avec lui")
    assert {(o.nature, o.chemin, o.poids) for o in apres.orphelins} == {
        (o.nature, o.chemin, o.poids) for o in avant.orphelins}


def test_les_noms_CACHES_des_QUATRE_emplacements_sont_tous_ecartes(projet):
    """Fichiers **et** dossiers, aux quatre racines balayees.

    Une seule des deux fonctions de listage filtree laisserait l'autre montrer
    ses caches, et le defaut serait alors reintroduit par le premier
    emplacement qu'on ajoute au balayage.
    """
    _semer_des_noms_caches(projet)
    inventaire = project_inventory.inventorier_le_projet(projet)

    caches = [o for o in inventaire.orphelins if o.nom.startswith(".")]
    assert caches == [], [o.chemin for o in caches]
    assert not any(o.poids in OCTETS_DES_CACHES.values()
                   for o in inventaire.orphelins), (
        "un cache passe sous un autre nom : le poids le trahit")


def test_le_filtre_des_CACHES_ne_TRONQUE_ni_la_tete_ni_la_QUEUE(projet):
    """Le mutant du 2026-09-03, transpose : un filtre qui coupe un BORD.

    **Mesure de mordance, faite plutot que supposee** (2026-09-06). Le mutant
    `[:-1]` sur `_fichiers_immediats` -- « un balayage qui saute la derniere
    entree de chaque listing d'orphelins », celui-la meme que `CLAUDE.md` nomme
    au point 4 de la regle des fabriques -- fait rougir ce test, et il le fait
    **avec** les orphelins caches en place, c'est-a-dire dans le regime que ce
    banc introduit.

    **Ce qu'il ne mord PAS, dit plutot que tu** : le mutant `[1:]`. Un nom cache
    trie toujours en tete (`.` precede toute lettre), si bien qu'une troncature
    de tete mange le cache et laisse l'orphelin legitime -- ce test reste vert.
    Ce mutant-la est tue par les bancs de bord qui existaient avant celui-ci
    (`…l_ensemble_des_objets_PRESENTS_et_NON_DECLARES…`,
    `…les_planches_ORPHELINES_sortent_des_DEUX_racines`), verifie en le posant.
    """
    _semer_des_noms_caches(projet)
    inventaire = project_inventory.inventorier_le_projet(projet)
    noms = {o.nom for o in inventaire.orphelins}

    # La TETE de chaque listing, celle que le cache precede desormais.
    assert _nom_de_master(RUSH_FANTOME, "prores_hq") in noms
    assert _nom_de_planche(RUSH_FANTOME_TETE, None) in noms
    # La QUEUE, que seul un filtre par slicing ferait tomber.
    assert _nom_de_master(RUSH_FANTOME_QUEUE, "prores_hq") in noms
    assert SLUG_SCAN_ORPHELIN_QUEUE in noms


def test_le_POIDS_du_projet_ne_compte_PAS_ce_qui_est_cache(projet):
    """Un fichier d'attente pese sur le disque et n'est pas un objet du projet.

    Le volet chiffre du meme fait : le total est **identique** avant et apres
    la semaille, alors que 13 020 octets ont ete ecrits. Sans lui, un filtre
    qui masquerait l'objet mais garderait son poids ferait un total que rien
    dans l'arbre n'explique.
    """
    avant = project_inventory.inventorier_le_projet(projet)
    _semer_des_noms_caches(projet)
    apres = project_inventory.inventorier_le_projet(projet)

    assert sum(OCTETS_DES_CACHES.values()) > 0
    assert apres.poids_total == avant.poids_total
    assert apres.fichiers_total == avant.fichiers_total
