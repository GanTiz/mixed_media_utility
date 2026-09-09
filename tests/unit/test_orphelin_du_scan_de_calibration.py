# -*- coding: utf-8 -*-
"""Banc du LOT I : le scan de la page de calibration compte-t-il pour un orphelin ?

**Le constat de terrain, verbatim** (Egan, 2026-09-06,
`_bmad-output/implementation-artifacts/260906_Epic-11-retours-terrain.md`,
section « Gestion des medias (projet) ») :

    « Le scan de la page de calibration apparaît en non déclaré alors que je
    l'ai importé au projet »

**Ce que ce banc etablit, et il l'etablit sur le RASTER REEL du depot** --
`tests/fixtures/scans/Page calibration HP ENVY La Seyne.pdf`, une mire
reellement imprimee puis reellement numerisee, plus deux scans de planches
reels a cote d'elle. `CLAUDE.md` l'exige : « une fixture de synthese mesure la
synthese ; elle ne devient une mesure du produit que confrontee a un artefact
de terrain », et la regle a deja ete payee dans les deux sens.

Trois faits, mesures et non supposes :

1. **le defaut existe** -- apres une calibration REELLE et REUSSIE, le dossier
   `scans/<mire>/` figure dans `inventaire.orphelins` avec
   `nature='scan', etat='non_declare'`, exactement comme un lot de planches
   jamais reconstruit ;
2. **il ne se refermera jamais tout seul**, et c'est ce qui le distingue du
   cas que le docstring d'`_orphelins` decrit : la filiation d'un scan de
   planches est *differee* -- elle nait a la reconstruction --, tandis qu'une
   mire ne sera **jamais** reconstruite en lot. Le faux orphelin est donc
   permanent, sur tout projet calibre ;
3. **rien sur le disque ne le reconnait.** C'est la mesure qui tranche le lot,
   et :func:`test_apres_une_calibration_REELLE_rien_sur_le_disque_ne_nomme_le_dossier_de_scan`
   la porte : ni le manifeste, ni le profil de `versions/calibration/`, ni le
   contenu du dossier de scan ne nomment ce dossier. Il n'y a donc **aucune
   reconnaissance fiable a ecrire dans `project_inventory`** sans qu'un
   marqueur soit d'abord ecrit ailleurs -- c'est-a-dire dans du coeur.

**Pourquoi une reconnaissance approchee serait PIRE que le faux orphelin.**
Ecarter un vrai lot de planches par erreur rendrait invisibles des images qui
pesent sur le disque, ce qui est exactement le sujet de la story qui a cree cet
inventaire. « On n'arrete jamais un process par ressemblance, toujours par
identite » (`CLAUDE.md`, regle 6) vaut ici mot pour mot : ni le cardinal de
pages, ni l'absence d'`ingest.json`, ni un fragment de nom ne sont une
identite. La dette est donc nommee plutot que devinee --
`deferred-work.md`, entree `LOT-I-1`.

**L'asymetrie que ce banc epingle.** `_orphelins` ecarte deja le **PDF** de
mire de `planches/`, par son suffixe (`naming.CALIBRATION_PDF_SUFFIX`), avec ce
motif ecrit noir sur blanc : « sans quoi tout projet calibre montrerait un faux
orphelin ». Le meme raisonnement n'est pas applique a l'autre bout de la
chaine : la mire qu'on IMPRIME est ecartee, la mire qu'on REIMPORTE ne l'est
pas. :func:`test_le_PDF_de_mire_lui_est_bien_ecarte_de_planches` mesure la
moitie qui marche, pour que l'ecart soit lisible d'un seul banc.

**La fabrique, et pourquoi elle est ce qu'elle est** (`CLAUDE.md`, regle des
fabriques, quatre points, payee quatre fois) :

* **trois** dossiers sous `scans/`, jamais un seul : un banc mono-dossier ne
  demasquerait aucun filtre trop large ;
* les trois sont **distinguables** et d'aucune valeur uniforme -- trois rasters
  reels differents, donc trois poids differents, mesures par
  :func:`test_A_la_FABRIQUE_tient_ce_que_la_regle_des_fabriques_exige` ;
* la mire est posee **en TETE, AU MILIEU et EN QUEUE** du listing trie
  (:data:`POSITIONS_DE_LA_MIRE`). Le point 4 de la regle a ete pose le
  2026-09-03 sur un mutant survivant qui sautait la **derniere** entree de
  chaque listing d'orphelins -- c'est-a-dire exactement la fonction que ce banc
  mesure. Une cible au milieu demasque un `find` fautif ; elle ne demasque pas
  un balayage tronque ;
* le **symetrique est obligatoire** : deux lots de planches REELS, qui doivent
  rester orphelins a chaque position. Sans lui, un filtre qui ecarterait tout
  resterait vert.

**Ce que ce banc NE mesure pas, dit plutot que tu :**

* **il mesure desormais le correctif** (`EPIC11-ARB-262`, 2026-09-07) : le
  profil DECLARE son dossier de scan (`scan_dir`), et l'inventaire lit cette
  declaration. Les quatre bancs qui mesuraient l'absence de marqueur -- dont
  l'`xfail(strict=True)` qui a ramene un lecteur ici en rougissant -- sont
  RETOURNES et non retires : ils mesurent la moitie qui marche, plus les deux
  moities qu'un correctif hatif casserait (le scan doit rester VISIBLE, et un
  profil sans le champ ne doit ecarter personne) ;
* il ne mesure pas la surface TUI de l'inventaire
  (`tui/projet_inventaire.py`), qui appartient a un autre lot ;
* il ne mesure qu'**un** parcours d'entree, celui de `calibrer_la_chaine`. Une
  mire importee par `mmu scan` puis basculee vers la calibration
  (`EPIC5-ARB-92`) laisse en plus un `ingest.json` -- ce que
  :func:`test_le_dossier_de_la_mire_ne_porte_meme_pas_de_rapport_d_ingestion`
  releve sans le couvrir.

**Les quatre sections ajoutees le 2026-09-07, et le finding que chacune ferme.**
La revue en trois couches a trouve cinq defauts `critique` sur l'appariement du
champ `scan_dir` ; quatre se ferment ici, deux se nomment :

* **E -- `B1`, ferme.** `_validate_scan_dir` acceptait CINQ ecritures d'un meme
  dossier qui ne s'appariaient a rien -- `'.'`, `'./scans/x'`, `'scans/x/'`,
  `'scans//x'`, `'scans/./x'` --, si bien que la barre oblique finale, **un seul
  caractere**, ramenait le faux orphelin sur un profil que la garde venait de
  declarer valide. Le manque etait une NORMALISATION et non un refus de plus, et
  c'est une mesure qui l'a tranche : la garde n'est appelee que par
  `write_profile`, jamais par le chemin de lecture ;
* **F -- `B4`, ferme.** La fabrique de `calibrations` etait MONO-ELEMENT : le
  mutant « seul le PREMIER scan declare est reconnu » survivait a 57 tests.
  Deux mires declarees, distinguables, aux DEUX bords du listing trie ;
* **G -- `B5`, ferme.** La garde `objet.nature == NATURE_SCAN` ne faisait varier
  aucun de ses drapeaux -- la retirer survivait a 57 tests --, alors qu'elle
  ferme un regime atteignable : un `scan_dir` valant `'extract-frames/lot-a'`,
  que la garde d'ecriture ACCEPTE. Le drapeau varie desormais dans le banc ;
* **H -- `B2` et `B6`, NOMMES et non fermes.** La declaration porte sur le LOT
  et non sur la page de mire (de vraies planches perdent leur mention « non
  declare »), et l'appariement est une identite et non une ascendance (un
  `scan_dir` a deux crans sous `scans/` ne s'apparie a aucun noeud). Les deux
  sont mesures sur le parcours reel, pour que la question se pose sur des
  chiffres -- `deferred-work.md`, entree `ARB262-N1`.

**LA CAMPAGNE DE MUTATION, avec ses rouges NOMMES** (2026-09-07, dans un
`git worktree` isole -- une couche de revue a deja vu un rouge fantome cause par
les mutations d'un autre agent dans l'arbre partage ; restauration depuis une
copie prise AVANT la mutation, jamais par `git checkout --`). Sept mutants
reinjectes, **sept morts, zero survivant** :

======================================  ======  ==================================
mutant                                  issue   rouges
======================================  ======  ==================================
lecture SANS normalisation              MORT    `..._QUATRE_ECRITURES_...` x4
garde SANS le 5e refus                  MORT    `..._NE_NOMME_AUCUN_DOSSIER_...` x4
`not calibrations and ...` (`B4`)       MORT    `..._DEUX_mires_..._DEUX_BORDS`,
                                                `..._DEUX_mires_..._poids_...`
garde de NATURE retiree (`B5`)          MORT    `..._NOMME_UN_DOSSIER_DE_FRAMES_...`
appariement par ASCENDANCE (`B2`)       MORT    `test_B2_..._range_par_DATE_...`
redaction A sans segment nommant        MORT    `..._DEUX_REDACTIONS_..._CONSTRUITE`
redaction B refuse TOUT deux-points     MORT    `..._DEUX_REDACTIONS_..._CONSTRUITE`
======================================  ======  ==================================

Les deux derniers vivent dans `tests/unit/test_identite_du_scan.py`. Le mutant
« ascendance » est le seul qui ne ferme pas un defaut : il MESURE le choix laisse
ouvert par `ARB262-N1`, et c'est ce qui empeche l'ascendance d'entrer par
inadvertance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "src") not in sys.path:
    sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import (project_inventory, scan_calibrate,  # noqa: E402
                                 scan_ingest)
from mixed_media_utility.io import (calibration_profile, naming,  # noqa: E402
                                    project_layout)
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME  # noqa: E402

# ---------------------------------------------------------------------------
# Les rasters REELS, et la sonde qui refuse de se substituer a eux
# ---------------------------------------------------------------------------

FIXTURES = RACINE / "tests" / "fixtures" / "scans"

#: La mire REELLE : une page de calibration imprimee sur HP ENVY 4520 puis
#: numerisee. Son QR porte le libelle de chaine `hp envy 4520 tiff 600 dpi auto
#: corr off`, et sa calibration reussit -- 130 pastilles lues, 130 retenues.
MIRE_REELLE = FIXTURES / "Page calibration HP ENVY La Seyne.pdf"

#: Les deux lots de planches REELS, poses a cote de la mire. Ce sont eux le
#: SYMETRIQUE : ils doivent rester orphelins quoi qu'il arrive a la mire.
PLANCHES_REELLES = (
    FIXTURES / "Scan 4f heteroclytes.pdf",
    FIXTURES / "Scan chendj 8f.pdf",
)

#: Taille en deca de laquelle un fichier suivi par LFS est un POINTEUR et non
#: son contenu (`CLAUDE.md`, sonde de session : un pointeur vaut 133 octets et
#: ne leve aucune erreur -- le banc echoue plus loin, sur un message de
#: decodage incomprehensible).
TAILLE_MINIMALE_D_UN_RASTER = 500

#: Le dpi **declare** de ces numerisations. Il n'est pas mesure sur le fichier :
#: c'est une saisie de l'operateur, et il entre dans l'identite de chaine.
DPI_DECLARE = 300

#: Les slugs d'ingestion, choisis pour que le tri par nom de `_sous_dossiers`
#: place la mire a la position voulue **entre** les deux lots de planches.
#: `'0'` (0x30) trie avant `'a'`, et `'zz'` apres `'z-'` (0x2D).
SLUG_PLANCHES_EN_TETE = "a-planches-4f"
SLUG_PLANCHES_EN_QUEUE = "z-planches-8f"

#: Les TROIS positions de la cible, et c'est le point 4 de la regle des
#: fabriques : en tete, au milieu, en queue. Un balayage tronque d'un bord ou de
#: l'autre perd la mire sans qu'aucune cible du milieu ne le voie.
POSITIONS_DE_LA_MIRE = {
    "tete": "0-mire",
    "milieu": "m-mire",
    "queue": "zz-mire",
}


def _exiger_le_raster(chemin: Path) -> Path:
    """Le raster reel, ou un refus qui NOMME la reparation.

    **Une fixture manquante bloque, elle ne se substitue pas** -- meme geste
    que `test_aller_retour_nominal_sur_le_rush_reel`. Le pointeur LFS est
    nomme a part parce qu'il ne leve rien de lui-meme : sans cette sonde, le
    banc mourrait bien plus loin sur un message de decodage, et la reparation
    (`git lfs checkout`, jamais `git lfs pull`) ne serait pas dans le message.
    """
    assert chemin.is_file(), (
        f"raster de terrain absent : {chemin}. La mesure de ce lot porte sur "
        "un artefact reel et ne se substitue pas par du synthetique."
    )
    taille = chemin.stat().st_size
    assert taille >= TAILLE_MINIMALE_D_UN_RASTER, (
        f"{chemin} vaut {taille} octets : c'est un POINTEUR LFS, pas le "
        "raster. Reparation : `git lfs checkout` (jamais `git lfs pull`, qui "
        "repaierait une bande passante deja payee)."
    )
    return chemin


# ---------------------------------------------------------------------------
# La fabrique
# ---------------------------------------------------------------------------


def _projet_nu(racine: Path) -> Path:
    """Un projet v2 ouvert et vide : aucun rush, aucun lot, l'arbre en place."""
    projet = racine / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    (projet / MANIFEST_FILENAME).write_text(
        json.dumps({"schema_version": 2, "project_id": "demo",
                    "rushes": [], "lots": []}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    project_layout.ensure_project_layout(projet)
    return projet


def _ingerer(projet: Path, source: Path, slug: str):
    """Ingerer un raster reel sous un slug impose. Rend le rapport."""
    return scan_ingest.ingest_scan_lot(
        projet, _exiger_le_raster(source), dpi=DPI_DECLARE, ingest_slug=slug)


def fabriquer_le_projet(racine: Path, slug_de_la_mire: str) -> Path:
    """Trois scans REELS sous `scans/`, la mire au rang demande.

    Les trois sont distinguables par construction -- trois fichiers de terrain
    differents, donc trois poids differents --, et c'est ce que la regle des
    fabriques exige : « des valeurs differentes, pas un remplissage uniforme ;
    une permutation ne se voit que si les elements different ».

    La mire est seulement **ingeree** ici, pas calibree : le faux orphelin
    naît de l'ingestion, la calibration ne fait que le rendre permanent. La
    calibration REELLE, elle, vit dans :func:`projet_calibre`, qui coute trois
    secondes et n'est montee qu'une fois.
    """
    projet = _projet_nu(racine)
    _ingerer(projet, PLANCHES_REELLES[0], SLUG_PLANCHES_EN_TETE)
    _ingerer(projet, MIRE_REELLE, slug_de_la_mire)
    _ingerer(projet, PLANCHES_REELLES[1], SLUG_PLANCHES_EN_QUEUE)
    return projet


@pytest.fixture(scope="module")
def projet_au_milieu(tmp_path_factory) -> Path:
    """La fabrique nominale : la mire AU MILIEU des deux lots de planches."""
    return fabriquer_le_projet(
        tmp_path_factory.mktemp("milieu"), POSITIONS_DE_LA_MIRE["milieu"])


@pytest.fixture(scope="module")
def projet_calibre(tmp_path_factory) -> tuple[Path, object]:
    """Le parcours d'Egan, joue en entier sur le raster reel.

    `scan_calibrate.calibrer_la_chaine` ingere, detecte, ajuste et consigne :
    c'est **le** point d'entree de coeur de `scan ... calibrate`
    (`EPIC11-ARB-129`) et celui que la TUI appelle
    (`tui/atelier_scan_calibrate.py`). A la sortie, le projet est calibre pour
    de bon -- la mire n'a plus aucune raison d'etre rescannee.
    """
    projet = _projet_nu(tmp_path_factory.mktemp("calibre"))
    _ingerer(projet, PLANCHES_REELLES[0], SLUG_PLANCHES_EN_TETE)
    _ingerer(projet, PLANCHES_REELLES[1], SLUG_PLANCHES_EN_QUEUE)
    consigne = scan_calibrate.calibrer_la_chaine(
        projet, _exiger_le_raster(MIRE_REELLE), dpi=DPI_DECLARE)
    return projet, consigne


# ---------------------------------------------------------------------------
# Lecture de l'inventaire -- des helpers de banc, jamais une seconde recette
# ---------------------------------------------------------------------------


def scans_orphelins(projet: Path) -> list[str]:
    """Les NOMS des dossiers de `scans/` que l'inventaire declare orphelins."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    return [objet.nom for objet in inventaire.orphelins
            if objet.nature == project_inventory.NATURE_SCAN]


def orphelin_nomme(projet: Path, nom: str):
    """L'objet orphelin de ce nom, ou `None` -- jamais une levee."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    return next((objet for objet in inventaire.orphelins if objet.nom == nom), None)


# ---------------------------------------------------------------------------
# A -- la fabrique se mesure, elle ne se promet pas
# ---------------------------------------------------------------------------


def test_A_la_FABRIQUE_tient_ce_que_la_regle_des_fabriques_exige(
    projet_au_milieu: Path,
) -> None:
    """Trois dossiers, distinguables, cible au milieu (`CLAUDE.md`, points 1 a 3).

    Sans cette mesure, une fabrique devenue mono-dossier ou a poids uniformes
    rendrait la moitie de ce banc verte pour rien -- c'est le defaut que la
    regle des fabriques existe pour fermer, paye trois fois d'affilee sur les
    stories 5.6, 5.7 et 5.8.
    """
    dossiers = sorted(
        chemin.name
        for chemin in (projet_au_milieu / project_layout.SCANS_DIRNAME).iterdir()
        if chemin.is_dir())
    assert dossiers == [SLUG_PLANCHES_EN_TETE,
                        POSITIONS_DE_LA_MIRE["milieu"],
                        SLUG_PLANCHES_EN_QUEUE], dossiers

    inventaire = project_inventory.inventorier_le_projet(projet_au_milieu)
    poids = {objet.nom: objet.poids for objet in inventaire.orphelins
             if objet.nature == project_inventory.NATURE_SCAN}
    assert len(poids) == 3, poids
    assert len(set(poids.values())) == 3, (
        "les trois scans pesent la meme chose : la fabrique est UNIFORME, et "
        f"une permutation ne s'y verrait pas -- {poids}")


# ---------------------------------------------------------------------------
# B -- LA REPRODUCTION, sur le parcours reel et en entier
# ---------------------------------------------------------------------------


def test_la_calibration_REELLE_reussit_sur_le_raster_de_terrain(
    projet_calibre: tuple[Path, object],
) -> None:
    """Le prealable de toute la suite : la mire du depot calibre pour de vrai.

    Sans ce controle, un banc rouge plus bas pourrait s'expliquer par une mire
    illisible plutot que par le defaut vise. Les cardinaux sont ceux mesures le
    2026-09-07 sur ce raster : 130 pastilles lues, 130 retenues.
    """
    projet, consigne = projet_calibre
    assert Path(consigne.profile_path).is_file(), consigne
    assert consigne.lot_correction.read_patch_count == 130
    assert consigne.lot_correction.retained_patch_count == 130
    profils = sorted(
        (projet / calibration_profile.VERSIONS_DIRNAME
         / calibration_profile.CALIBRATION_DIRNAME).glob("*.json"))
    assert len(profils) == 1, profils


def scans_declares_par_un_profil(projet: Path) -> list[str]:
    """Les NOMS des dossiers de `scans/` qu'un profil de calibration declare."""
    inventaire = project_inventory.inventorier_le_projet(projet)
    return [objet.nom for objet in inventaire.calibrations
            if objet.nature == project_inventory.NATURE_SCAN]


def test_le_scan_de_la_mire_N_APPARAIT_PLUS_en_orphelin(
    projet_calibre: tuple[Path, object],
) -> None:
    """Le constat de terrain, FERME (`EPIC11-ARB-262`, tranche le 2026-09-07).

    « Le scan de la page de calibration apparaît en non déclaré alors que je
    l'ai importé au projet. » Il ne l'est plus : le profil ecrit par la
    calibration NOMME le dossier de scan dont il est issu (`scan_dir`), et
    `_orphelins` lit cette declaration.

    **Ce test etait un `xfail(strict=True)` jusqu'au 2026-09-07**, et c'est ce
    marqueur qui a ramene un lecteur ici le jour ou la dette s'est fermee :
    ecrire le champ le faisait passer `XPASS(strict)`, donc ROUGIR. Il est
    retourne en assertion positive dans le meme mouvement, comme la dette
    `LOT-I-1` l'annoncait.
    """
    projet, _ = projet_calibre
    assert MIRE_REELLE.stem not in scans_orphelins(projet)


def test_le_scan_de_la_mire_est_DECLARE_et_PRESENT_plutot_qu_ecarte(
    projet_calibre: tuple[Path, object],
) -> None:
    """L'autre moitie de l'arbitrage, et sans elle la premiere serait un RECUL.

    L'issue (A) a ete prise contre (B) et (C) parce qu'elle rend le scan
    **declare et rattache**, pas invisible : « des octets qui pesent sur le
    disque et qu'aucun ecran ne montre » est exactement le defaut que
    l'inventaire existe pour fermer. Sortir la mire des orphelins SANS la
    reposer ailleurs l'aurait produit.

    Le poids et le cardinal sont donc mesures ici, non nuls : ce sont ceux du
    raster reel recopie par l'ingestion.
    """
    projet, _ = projet_calibre
    assert MIRE_REELLE.stem in scans_declares_par_un_profil(projet)
    inventaire = project_inventory.inventorier_le_projet(projet)
    mire = next(objet for objet in inventaire.calibrations
                if objet.nom == MIRE_REELLE.stem)
    assert mire.etat == project_inventory.ETAT_PRESENT
    assert mire.nature == project_inventory.NATURE_SCAN
    assert mire.poids > 0, mire
    assert mire.fichiers >= 1, mire
    # Elle compte toujours dans les deux totaux du projet : `parcourir` la
    # traverse, donc `poids_total` et `objets_total` la portent.
    assert mire in list(inventaire.parcourir())
    assert inventaire.poids_total >= mire.poids


def test_les_DEUX_lots_de_planches_restent_orphelins(
    projet_calibre: tuple[Path, object],
) -> None:
    """Le SYMETRIQUE, et c'est lui qui refuse un correctif qui ecarterait trop.

    Un filtre qui prendrait la mire par ressemblance -- un fragment de nom,
    l'absence d'`ingest.json`, une page unique -- emporterait aussi un vrai lot
    de planches. Les deux lots REELS poses de part et d'autre de la mire sont
    donc mesures a chaque bord : ils restent orphelins, et ils ne rejoignent
    JAMAIS la famille des scans declares.
    """
    projet, _ = projet_calibre
    orphelins = scans_orphelins(projet)
    declares = scans_declares_par_un_profil(projet)
    for slug in (SLUG_PLANCHES_EN_TETE, SLUG_PLANCHES_EN_QUEUE):
        assert slug in orphelins, orphelins
        assert slug not in declares, declares
    assert declares == [MIRE_REELLE.stem], declares


def test_un_profil_SANS_scan_dir_laisse_le_faux_orphelin_ouvert(
    projet_calibre: tuple[Path, object], tmp_path: Path,
) -> None:
    """Ce que l'arbitrage NE repare pas, mesure plutot que promis.

    « Les projets **déjà** calibrés — dont celui d'Egan — resteront faux. » Un
    profil ecrit avant le 2026-09-07 ne porte pas `scan_dir` : rien ne relie
    retroactivement un dossier de scan a un profil, et le faux orphelin ne se
    fermera qu'a la prochaine recalibration.

    La mesure retire le champ du profil du projet calibre -- recopie dans un
    projet jetable, l'original ne bouge pas -- et constate que la mire revient
    en orphelin. C'est aussi la garde de retrocompatibilite : un profil sans le
    champ ne DOIT pas ecarter un dossier au hasard.
    """
    import shutil
    projet, consigne = projet_calibre
    copie = tmp_path / "avant"
    shutil.copytree(projet, copie)
    profil = copie / Path(consigne.profile_path).relative_to(projet)
    document = json.loads(profil.read_text(encoding="utf-8"))
    assert document.pop(calibration_profile.SCAN_DIR_FIELD, None), document
    profil.write_text(json.dumps(document, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    assert MIRE_REELLE.stem in scans_orphelins(copie)
    assert scans_declares_par_un_profil(copie) == []


def test_le_profil_ecrit_NOMME_le_dossier_de_scan_en_relatif_POSIX(
    projet_calibre: tuple[Path, object],
) -> None:
    """La frontiere du 2026-09-07, **retournee** : le profil porte le chemin.

    Elle etait negative jusque-la -- « aucun champ du profil ne nomme un
    dossier de scan » -- et c'est ce qui la rendait utile : elle a rougi le jour
    du correctif et a dit ou il etait. Elle mesure desormais les trois
    proprietes du champ, parce que chacune ferme une panne differente :

    * il vaut le dossier REELLEMENT employe par l'ingestion, jamais recompose
      d'un slug suppose ;
    * il est **relatif** au projet -- un chemin absolu casserait l'invariant de
      portabilite v2, le profil etant recopie dans le manifeste ;
    * il est **POSIX** : `_relatif` rend des `/`, et un antislash ne
      s'apparierait a rien.
    """
    projet, consigne = projet_calibre
    document = json.loads(Path(consigne.profile_path).read_text(encoding="utf-8"))
    attendu = f"{project_layout.SCANS_DIRNAME}/{MIRE_REELLE.stem}"
    assert document[calibration_profile.SCAN_DIR_FIELD] == attendu, document
    assert (projet / attendu).is_dir()
    assert not attendu.startswith("/") and "\\" not in attendu
    # Le pendant, pour que la mesure ne soit pas celle d'un projet vide.
    assert document["chain_id"] == consigne.chain_id
    assert document["source_page_id"], document


def test_la_declaration_se_LIT_du_profil_et_ne_se_devine_d_aucun_nom(
    projet_calibre: tuple[Path, object], tmp_path: Path,
) -> None:
    """`CLAUDE.md`, regle 6 : par identite, jamais par ressemblance.

    Le contre-exemple est celui qui aurait casse les trois heuristiques
    ecartees par la dette : un dossier de scan **renomme a la main**. Le profil
    continue de nommer l'ancien chemin, qui n'existe plus ; le nouveau n'est
    declare par personne. L'inventaire doit donc rendre le nouveau dossier
    ORPHELIN et ne declarer aucun scan -- et surtout pas rattacher le dossier
    renomme au profil parce qu'il « ressemble ».
    """
    import shutil
    projet, _ = projet_calibre
    copie = tmp_path / "renomme"
    shutil.copytree(projet, copie)
    scans = copie / project_layout.SCANS_DIRNAME
    (scans / MIRE_REELLE.stem).rename(scans / "autre-nom-de-mire")
    assert "autre-nom-de-mire" in scans_orphelins(copie)
    assert scans_declares_par_un_profil(copie) == []


def test_le_dossier_de_la_mire_ne_porte_meme_pas_de_rapport_d_ingestion(
    projet_calibre: tuple[Path, object],
) -> None:
    """Le troisieme releve, et il ferme la deuxieme piste du brief.

    `calibrer_la_chaine` n'ecrit **pas** `ingest.json` : les deux seuls sites
    du depot qui appellent `scan_ingest.ecrire_le_rapport` sont
    `cli.py` (commande `scan`) et `scan_detect.py` (commande `scan detect`). Le
    dossier de la mire ne porte donc que la copie de son PDF.

    **L'absence d'`ingest.json` n'est PAS une identite pour autant**, et c'est
    pourquoi elle ne devient pas un filtre : un dossier depose a la main sous
    `scans/` par l'operateur n'en porte pas davantage, et celui-la est un vrai
    orphelin -- des octets sur le disque qu'aucun ecran ne montre, c'est-a-dire
    le sujet meme de la story. Ecarter sur cette absence rendrait invisible ce
    que l'inventaire existe pour montrer.
    """
    projet, _ = projet_calibre
    dossier = projet / project_layout.SCANS_DIRNAME / MIRE_REELLE.stem
    presents = sorted(chemin.name for chemin in dossier.iterdir())
    assert presents == [MIRE_REELLE.name], presents
    assert not (dossier / scan_ingest.INGEST_DOCUMENT_FILENAME).exists()


# ---------------------------------------------------------------------------
# C -- LES TROIS BORDS, et le symetrique a chacun d'eux
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("position", sorted(POSITIONS_DE_LA_MIRE))
def test_les_lots_de_planches_REELS_restent_orphelins_a_CHAQUE_BORD(
    tmp_path: Path, position: str,
) -> None:
    """**Le symetrique obligatoire**, joue en tete, au milieu et en queue.

    C'est le banc qui mordrait si un correctif ecartait trop large : deux lots
    de planches REELS -- 4 frames et 8 frames, deux rasters de terrain -- qui
    doivent figurer parmi les orphelins quelle que soit la place de la mire
    dans le listing trie.

    Le point 4 de la regle des fabriques est la raison des trois positions :
    le 2026-09-03, un mutant qui sautait la **derniere** entree de chaque
    listing d'orphelins a survecu a un banc dont toutes les cibles etaient au
    milieu. Une cible au milieu demasque un `find` fautif ; elle ne demasque
    pas un balayage tronque.
    """
    projet = fabriquer_le_projet(tmp_path, POSITIONS_DE_LA_MIRE[position])
    trouves = scans_orphelins(projet)
    assert SLUG_PLANCHES_EN_TETE in trouves, (position, trouves)
    assert SLUG_PLANCHES_EN_QUEUE in trouves, (position, trouves)


@pytest.mark.parametrize("position", sorted(POSITIONS_DE_LA_MIRE))
def test_les_TROIS_scans_sont_vus_a_chaque_position(
    tmp_path: Path, position: str,
) -> None:
    """L'egalite d'ENSEMBLES, pas un cardinal (`CLAUDE.md`, « on compare des listes »).

    Deux cardinaux egaux peuvent recouvrir deux ensembles differents : un scan
    perdu et un scan de trop s'annulent dans un compteur. C'est l'egalite qui
    attrape un balayage tronque a l'un ou l'autre bord, et c'est elle qui devra
    etre relue -- une entree en moins -- le jour ou la dette LOT-I-1 se
    fermera.
    """
    slug_mire = POSITIONS_DE_LA_MIRE[position]
    projet = fabriquer_le_projet(tmp_path, slug_mire)
    assert set(scans_orphelins(projet)) == {
        SLUG_PLANCHES_EN_TETE, slug_mire, SLUG_PLANCHES_EN_QUEUE}


# ---------------------------------------------------------------------------
# D -- l'asymetrie, epinglee : la moitie qui MARCHE deja
# ---------------------------------------------------------------------------


def test_le_PDF_de_mire_lui_est_bien_ecarte_de_planches(tmp_path: Path) -> None:
    """L'autre bout de la chaine, et il fonctionne depuis toujours.

    `_orphelins` ecarte le PDF de mire de `planches/` par son suffixe, avec ce
    motif : « sans quoi tout projet calibre montrerait un faux orphelin ». Ce
    banc le mesure a cote du defaut, pour que l'asymetrie soit lisible d'un seul
    fichier : la mire qu'on IMPRIME est ecartee, la mire qu'on REIMPORTE ne
    l'est pas, et c'est le meme raisonnement qui vaut aux deux bouts.

    Le symetrique est dans le meme test : un PDF de planches ordinaire, pose
    dans le meme dossier, reste orphelin. Sans lui, un filtre qui ecarterait
    tout `planches/` serait vert.
    """
    projet = _projet_nu(tmp_path)
    planches = projet / project_layout.PLANCHES_DIRNAME
    planches.mkdir(parents=True, exist_ok=True)
    nom_de_mire = naming.build_calibration_pdf_filename("demo", "hp envy 4520")
    (planches / nom_de_mire).write_bytes(b"x" * 101)
    (planches / "demo_r-alpha_planches.pdf").write_bytes(b"y" * 211)

    inventaire = project_inventory.inventorier_le_projet(projet)
    noms = {objet.nom for objet in inventaire.orphelins
            if objet.nature == project_inventory.NATURE_PLANCHE}
    assert nom_de_mire.endswith(naming.CALIBRATION_PDF_SUFFIX)
    assert nom_de_mire not in noms, (
        "le PDF de mire est devenu un orphelin : la moitie qui marchait a "
        f"regresse -- {sorted(noms)}")
    assert "demo_r-alpha_planches.pdf" in noms, sorted(noms)


# ---------------------------------------------------------------------------
# E -- `B1` : le dossier declare est NORMALISE avant d'etre apparie
# ---------------------------------------------------------------------------

#: Les quatre ecritures d'un MEME dossier que la garde d'ecriture laissait passer et
#: qui ne s'appariaient a rien. Elles ne sont pas des curiosites de banc : chacune est
#: ce que produit un operateur qui recopie un chemin depuis un terminal, un explorateur
#: de fichiers ou un autre projet. La barre oblique finale est **un seul caractere**, et
#: elle suffisait a ramener le faux orphelin qu'`EPIC11-ARB-262` ferme -- sur un profil
#: que `_validate_scan_dir` venait de declarer valide.
DECORATIONS_DU_MEME_DOSSIER = {
    "prefixe point-barre": "./{}",
    "barre finale": "{}/",
    "double barre": "scans//{segment}",
    "segment point": "scans/./{segment}",
}

#: Ce qui, une fois normalise, ne nomme AUCUN dossier : le dossier projet lui-meme.
#: Ce n'est pas la meme chose qu'un champ vide, et c'est toute la difference -- un
#: champ absent ou vide dit « aucune declaration n'a ete faite », ce qui est le cas
#: legitime de tout profil ecrit avant le 2026-09-07 ; celui-ci dit « je declare » et
#: ne declare rien.
FORMES_QUI_NE_NOMMENT_RIEN = (".", "./", ".//.", "././")


def _dossier_declare_par_le_profil(projet: Path, consigne) -> str:
    """La valeur que la calibration reelle a ecrite, relue du fichier."""
    document = json.loads(Path(consigne.profile_path).read_text(encoding="utf-8"))
    return document[calibration_profile.SCAN_DIR_FIELD]


def _reecrire_le_dossier_declare(projet: Path, consigne, racine: Path,
                                 valeur: str) -> Path:
    """Une COPIE du projet calibre dont le profil declare `valeur`.

    L'original ne bouge pas : la fixture est de portee module, et une mesure qui
    mute son socle ferait dependre les bancs de leur ordre.
    """
    import shutil
    copie = racine / "copie"
    shutil.copytree(projet, copie)
    profil = copie / Path(consigne.profile_path).relative_to(projet)
    document = json.loads(profil.read_text(encoding="utf-8"))
    document[calibration_profile.SCAN_DIR_FIELD] = valeur
    profil.write_text(json.dumps(document, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    return copie


@pytest.mark.parametrize("decoration", sorted(DECORATIONS_DU_MEME_DOSSIER))
def test_les_QUATRE_ECRITURES_du_meme_dossier_declarent_le_meme_scan(
    projet_calibre: tuple[Path, object], tmp_path: Path, decoration: str,
) -> None:
    """`B1`, ferme : la normalisation apparie, la garde ne suffisait pas.

    **Le manque etait une NORMALISATION, pas un refus de plus**, et c'est une
    mesure qui l'a tranche plutot qu'un gout : `_validate_scan_dir` n'est appelee
    que par `write_profile`. Le chemin de LECTURE
    (`dossiers_de_scan_declares` -> `_orphelins`) ne la traverse jamais. Un refus
    supplementaire n'aurait donc rien ferme d'un profil deja sur le disque --
    edite a la main, ecrit par une version anterieure, recopie d'un autre projet --
    alors que la normalisation apparie les cinq ecritures du meme dossier a
    l'unique noeud qui le porte.

    Le temoin negatif est le banc qui suit : ce qui ne nomme aucun dossier ne
    declare toujours rien. Sans lui, « la normalisation avale tout » expliquerait
    aussi bien ce vert.
    """
    projet, consigne = projet_calibre
    declare = _dossier_declare_par_le_profil(projet, consigne)
    segment = declare.split("/", 1)[1]
    valeur = DECORATIONS_DU_MEME_DOSSIER[decoration].format(declare, segment=segment)
    assert valeur != declare, valeur

    copie = _reecrire_le_dossier_declare(projet, consigne, tmp_path, valeur)
    assert scans_declares_par_un_profil(copie) == [MIRE_REELLE.stem], (
        f"{valeur!r} ecrit le meme dossier que {declare!r} et ne le declare pas")
    assert MIRE_REELLE.stem not in scans_orphelins(copie)
    # Le symetrique dans le meme banc : les deux lots de planches REELS ne sont
    # pas avales au passage. Une normalisation trop large les emporterait.
    assert set(scans_orphelins(copie)) == {SLUG_PLANCHES_EN_TETE,
                                           SLUG_PLANCHES_EN_QUEUE}


@pytest.mark.parametrize("valeur", FORMES_QUI_NE_NOMMENT_RIEN)
def test_un_scan_dir_qui_NE_NOMME_AUCUN_DOSSIER_ne_declare_rien(
    projet_calibre: tuple[Path, object], tmp_path: Path, valeur: str,
) -> None:
    """Le residu que la normalisation ne repare pas, et il est REFUSE a l'ecriture.

    `'.'` designe le dossier projet, qui n'est aucun objet de l'inventaire. Le
    normaliser rend la chaine vide -- « ne declare rien » --, et c'est la seule
    reponse honnete : l'apparier a un dossier de `scans/` quelconque serait une
    ressemblance, et l'apparier a tous les ferait disparaitre l'inventaire entier.

    Les deux moities sont mesurees ensemble parce qu'une seule mentirait :
    l'ecriture le REFUSE (personne ne produit ce profil-la par le produit), et la
    lecture d'un fichier qui le porterait quand meme laisse le scan orphelin
    (personne n'ecarte un dossier au hasard).
    """
    projet, consigne = projet_calibre
    with pytest.raises(calibration_profile.ProfileValidationError):
        calibration_profile._validate_scan_dir(
            {calibration_profile.SCAN_DIR_FIELD: valeur})

    copie = _reecrire_le_dossier_declare(projet, consigne, tmp_path, valeur)
    assert scans_declares_par_un_profil(copie) == []
    assert MIRE_REELLE.stem in scans_orphelins(copie)


def test_la_garde_d_ECRITURE_accepte_ce_que_la_normalisation_rattrape(
    projet_calibre: tuple[Path, object],
) -> None:
    """La garde et la lecture disent la MEME chose, et c'est ce qui les lie.

    Une garde qui refuserait les quatre decorations rendrait la normalisation
    inutile ; une garde qui accepterait `'.'` rendrait la lecture muette. Les deux
    sens sont donc mesures ici, sur les valeurs exactes des deux bancs ci-dessus,
    plutot que declares dans un docstring.
    """
    projet, consigne = projet_calibre
    declare = _dossier_declare_par_le_profil(projet, consigne)
    segment = declare.split("/", 1)[1]
    for gabarit in DECORATIONS_DU_MEME_DOSSIER.values():
        valeur = gabarit.format(declare, segment=segment)
        calibration_profile._validate_scan_dir(
            {calibration_profile.SCAN_DIR_FIELD: valeur})
        assert calibration_profile.normaliser_le_dossier_de_scan(valeur) == declare
    # L'absence et le vide restent acceptees : elles disent « aucune declaration »,
    # ce qui est le cas de tout profil ecrit avant le 2026-09-07.
    calibration_profile._validate_scan_dir({})
    calibration_profile._validate_scan_dir(
        {calibration_profile.SCAN_DIR_FIELD: ""})
    # Et les quatre refus d'origine tiennent toujours, chacun pour son motif.
    for refusee in ("/var/scans", "C:/scans", "../dehors", "scans\\mire"):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile._validate_scan_dir(
                {calibration_profile.SCAN_DIR_FIELD: refusee})
        assert calibration_profile.normaliser_le_dossier_de_scan(refusee) in (
            "", refusee), refusee


# ---------------------------------------------------------------------------
# F -- `B4` : DEUX mires declarees, distinguables, aux DEUX bords
# ---------------------------------------------------------------------------

#: Le slug de la SECONDE mire declaree. Trie en queue (`'z'` apres les majuscules
#: et apres `'a'`/`'z-'`), la premiere -- le dossier de la mire reelle, qui commence
#: par `'P'` -- etant en tete. La regle des fabriques, point 4 : une cible au milieu
#: demasque un `find` fautif, elle ne demasque pas un balayage tronque.
SLUG_DE_LA_SECONDE_MIRE = "zz-mire-seconde-chaine"


@pytest.fixture(scope="module")
def projet_a_deux_mires(projet_calibre, tmp_path_factory) -> Path:
    """Le projet calibre, plus un SECOND dossier de mire declare par un SECOND profil.

    **Pourquoi deux, et pourquoi ce banc existe** (finding `B4` de la revue du
    2026-09-07) : toutes les fabriques de ce fichier ne posaient qu'**une** mire, et
    le mutant `if (not calibrations) and objet.nature == ...` -- « seul le PREMIER
    scan declare est reconnu » -- survivait a 57 tests. C'est la regle des fabriques
    mot pour mot, quatrieme paiement.

    **Le regime est reel, il n'est pas invente pour le banc** : `EPIC11-ARB-105`
    tranche que rescanner avec un profil ameliore est une VERSION, et deux chaines
    distinctes -- deux scanners, deux cadences -- produisent chacune leur dossier de
    mire declare.

    **Ce que la fabrique fait a la main, et il faut le dire** : le depot ne porte
    qu'un seul raster de mire reel. Le second dossier declare est donc **pose**, avec
    son profil, plutot que calibre : deux copies du raster reel, sous deux noms de
    page -- une numerisation recto/verso. C'est la LECTURE de deux declarations que
    le mutant attaque, et c'est elle que ce montage mesure. La calibration reelle,
    elle, reste mesuree par la section B.

    Les quatre dossiers sont distinguables par construction -- cardinaux et poids
    tous differents --, ce que
    :func:`test_F_la_FABRIQUE_A_DEUX_MIRES_tient_la_regle_des_fabriques` mesure.
    """
    import shutil
    projet, consigne = projet_calibre
    copie = tmp_path_factory.mktemp("deux-mires") / "projet"
    shutil.copytree(projet, copie)

    seconde = copie / project_layout.SCANS_DIRNAME / SLUG_DE_LA_SECONDE_MIRE
    seconde.mkdir(parents=True)
    for nom in ("recto.pdf", "verso.pdf"):
        shutil.copy2(_exiger_le_raster(MIRE_REELLE), seconde / nom)

    document = json.loads(
        Path(consigne.profile_path).read_text(encoding="utf-8"))
    document.pop(calibration_profile.LABEL_FIELD, None)
    document["chain_id"] = "600-pdf-0d0d0d0d0d0d"
    document[calibration_profile.SCAN_DIR_FIELD] = (
        f"{project_layout.SCANS_DIRNAME}/{SLUG_DE_LA_SECONDE_MIRE}")
    # Par `write_profile`, jamais par un `json.dump` : c'est le chemin d'ecriture
    # du produit, donc la garde de forme est traversee pour de vrai.
    calibration_profile.write_profile(copie, document)
    return copie


def test_F_la_FABRIQUE_A_DEUX_MIRES_tient_la_regle_des_fabriques(
    projet_a_deux_mires: Path,
) -> None:
    """Quatre dossiers, tous distinguables, deux profils. Mesure, pas promesse.

    Sans elle, une fabrique redevenue mono-mire ou a poids uniformes rendrait les
    bancs qui suivent verts pour rien -- le defaut exact que la regle des fabriques
    existe pour fermer, paye sur 5.6, 5.7, 5.8 puis 11.11.
    """
    inventaire = project_inventory.inventorier_le_projet(projet_a_deux_mires)
    scans = [objet for objet in inventaire.parcourir()
             if objet.nature == project_inventory.NATURE_SCAN]
    assert len(scans) == 4, [objet.nom for objet in scans]
    assert len({objet.poids for objet in scans}) == 4, (
        "les dossiers de scan pesent la meme chose : la fabrique est UNIFORME -- "
        f"{[(objet.nom, objet.poids) for objet in scans]}")
    profils = sorted(
        chemin.name for chemin, _ in
        calibration_profile.documents_de_calibration(projet_a_deux_mires))
    assert len(profils) == 2, profils
    assert len(calibration_profile.dossiers_de_scan_declares(
        projet_a_deux_mires)) == 2


def test_les_DEUX_mires_declarees_sont_reconnues_aux_DEUX_BORDS(
    projet_a_deux_mires: Path,
) -> None:
    """`B4`, ferme : la reconnaissance ne s'arrete pas a la premiere.

    C'est l'egalite d'ENSEMBLES qui est exigee, jamais un cardinal : « deux
    cardinaux egaux peuvent recouvrir deux ensembles differents ». Et les deux
    cibles sont aux deux bords du listing trie -- la mire reelle en tete (`'P'`),
    la seconde en queue (`'zz-'`) --, si bien qu'un balayage tronque de l'un ou
    l'autre cote perd une declaration.
    """
    declares = scans_declares_par_un_profil(projet_a_deux_mires)
    assert set(declares) == {MIRE_REELLE.stem, SLUG_DE_LA_SECONDE_MIRE}, declares
    # Le SYMETRIQUE, dans le meme banc : les deux lots de planches reels, poses
    # entre les deux mires, restent orphelins.
    assert set(scans_orphelins(projet_a_deux_mires)) == {
        SLUG_PLANCHES_EN_TETE, SLUG_PLANCHES_EN_QUEUE}


def test_les_DEUX_mires_declarees_gardent_leur_poids_et_leur_cardinal(
    projet_a_deux_mires: Path,
) -> None:
    """L'autre moitie d'`EPIC11-ARB-262`, exigee des DEUX declarees.

    Un correctif qui reconnaitrait la seconde mire en la vidant de sa mesure --
    poids nul, cardinal nul -- serait le remede pire que le mal que l'arbitrage
    ecarte : des octets qui pesent sur le disque et qu'aucun ecran ne montre.
    """
    inventaire = project_inventory.inventorier_le_projet(projet_a_deux_mires)
    mires = {objet.nom: objet for objet in inventaire.calibrations}
    assert set(mires) == {MIRE_REELLE.stem, SLUG_DE_LA_SECONDE_MIRE}
    for nom, mire in sorted(mires.items()):
        assert mire.etat == project_inventory.ETAT_PRESENT, nom
        assert mire.poids > 0, nom
        assert mire.fichiers >= 1, nom
        assert mire in list(inventaire.parcourir()), nom
    assert mires[SLUG_DE_LA_SECONDE_MIRE].fichiers == 2
    assert mires[MIRE_REELLE.stem].fichiers == 1


# ---------------------------------------------------------------------------
# G -- `B5` : la garde de NATURE, avec son drapeau FAIT VARIER
# ---------------------------------------------------------------------------


def test_un_scan_dir_qui_NOMME_UN_DOSSIER_DE_FRAMES_ne_declare_rien(
    tmp_path: Path,
) -> None:
    """`B5`, ferme : la garde de nature porte, et elle est desormais mesuree.

    `_orphelins` exige `objet.nature == NATURE_SCAN` avant d'apparier. Retirer
    cette garde SURVIVAIT a 57 tests : aucun banc ne faisait varier la nature de
    l'objet apparie, si bien qu'une garde correcte se serait fait retirer au
    premier nettoyage comme du code mort (`CLAUDE.md`, « une garde qui ne fait
    varier aucun de ses drapeaux ne mesure qu'un seul chemin »).

    **Le regime qu'elle ferme est atteignable** : `scan_dir` est relatif au
    PROJET, pas a `scans/`, et `_validate_scan_dir` accepte donc
    `'extract-frames/lot-a'` -- chemin relatif POSIX parfaitement bien forme. Sans
    la garde, ce profil ferait basculer un dossier de FRAMES orphelin dans la
    famille « calibrations » avec `ETAT_PRESENT`, c'est-a-dire ferait perdre la
    mention « non declare » a des images qui pesent sur le disque.

    Les deux valeurs du drapeau sont jouees dans le meme banc : un dossier de
    frames et un dossier de scan, tous deux declares par le meme profil.
    """
    projet = _projet_nu(tmp_path)
    racines = project_layout.racines_de_frames_extraites(projet)
    assert racines, "aucune racine de frames extraites : la fabrique ne mesure rien"
    racine = racines[0]
    (racine / "lot-a").mkdir(parents=True, exist_ok=True)
    (racine / "lot-a" / "f0001.png").write_bytes(b"x" * 97)
    scans = projet / project_layout.SCANS_DIRNAME
    (scans / "mire").mkdir(parents=True, exist_ok=True)
    (scans / "mire" / "page.pdf").write_bytes(b"y" * 211)

    dossier_de_frames = f"{racine.name}/lot-a"
    # La garde d'ECRITURE l'accepte : c'est bien un chemin relatif POSIX. C'est ce
    # qui rend la garde de nature necessaire plutot que decorative.
    calibration_profile._validate_scan_dir(
        {calibration_profile.SCAN_DIR_FIELD: dossier_de_frames})

    dossier = (projet / calibration_profile.VERSIONS_DIRNAME
               / calibration_profile.CALIBRATION_DIRNAME)
    dossier.mkdir(parents=True, exist_ok=True)
    for radical, declare in (("a-frames", dossier_de_frames),
                             ("z-scan", f"{project_layout.SCANS_DIRNAME}/mire")):
        (dossier / f"{radical}.json").write_text(
            json.dumps({"chain_id": radical,
                        calibration_profile.SCAN_DIR_FIELD: declare}),
            encoding="utf-8")

    inventaire = project_inventory.inventorier_le_projet(projet)
    # Le drapeau a VARIE : le dossier de scan est declare, celui de frames non.
    assert [objet.nom for objet in inventaire.calibrations] == ["mire"]
    frames = [objet for objet in inventaire.orphelins
              if objet.nature == project_inventory.NATURE_FRAMES_EXTRAITES]
    assert [objet.nom for objet in frames] == ["lot-a"], frames
    assert frames[0].etat == project_inventory.ETAT_NON_DECLARE
    assert dossier_de_frames not in [objet.chemin
                                     for objet in inventaire.calibrations]


# ---------------------------------------------------------------------------
# H -- ce que l'appariement NE COUVRE PAS, mesure plutot que tu
# ---------------------------------------------------------------------------
#
# Les deux bancs ci-dessous ne mesurent pas un correctif : ils EPINGLENT la
# portee reelle d'`EPIC11-ARB-262`, findings `B2` et `B6` de la revue du
# 2026-09-07. C'est la moitie que le diff d'origine ne disait pas alors qu'il
# disait tout le reste, et le geste du depot est de la nommer -- « un "ce que ca
# ne couvre pas" dit plutot que tu », avec son banc de bord. Ils rougissent le
# jour ou le comportement change, ce qui est exactement ce qu'on veut d'une
# tolerance nommee : elle ne derive pas en silence.
#
# L'arbitrage produit qui les fermerait appartient a Egan : `deferred-work.md`,
# entree `ARB262-N1`, qui porte les deux sorties chiffrees.


@pytest.fixture(scope="module")
def pile_melangee(tmp_path_factory) -> tuple[Path, Path]:
    """Une pile REELLE qui porte la mire ET de vraies planches.

    C'est ce qu'un operateur produit en passant sa pile entiere au chargeur
    automatique. Le raster est celui du depot, jamais une synthese : « une
    fixture de synthese peut fabriquer une panne que le terrain n'a PAS ».
    """
    import shutil
    base = tmp_path_factory.mktemp("pile")
    projet = _projet_nu(base)
    pile = base / "pile_melangee"
    pile.mkdir()
    shutil.copy2(_exiger_le_raster(MIRE_REELLE), pile / "0-mire.pdf")
    shutil.copy2(_exiger_le_raster(PLANCHES_REELLES[0]), pile / "1-planches.pdf")
    return projet, pile


def test_B6_est_FERME_a_la_source_la_pile_melangee_est_REFUSEE(
    pile_melangee: tuple[Path, Path],
) -> None:
    """`B6` **fermee** le 2026-09-07 par `EPIC11-ARB-266`, et non plus toleree.

    > **Ce banc mesurait la TOLERANCE, il mesure desormais sa FERMETURE.** Sa
    > redaction d'avant epinglait le regime : « un lot qui porte la mire et de
    > vraies planches passe en entier dans `calibrations` [...] et ces
    > planches-la ne sont plus annoncees "non declare" ». C'etait vrai, et c'est
    > la mesure qu'Egan a lue avant de trancher. Elle a rougi a la course de
    > cloture du meme jour -- exactement comme une frontiere doit rougir quand
    > le comportement qu'elle epingle change.

    Egan, verbatim : « Refuser comme le parcours classique. » Le parcours `scan`
    refusait deja cette pile depuis `EPIC5-ARB-86` ; `calibrate` l'acceptait,
    consignait le profil, n'ecrivait aucune frame, et declarait le dossier
    ENTIER. C'est l'erreur qui coute le plus cher des deux : elle **cache** un
    oubli reel au lieu d'en inventer un.

    **Rien n'est ecrit sur le disque** : le refus tombe avant toute ecriture, et
    ce test le mesure plutot que de le supposer -- un refus qui laisserait un
    profil derriere lui serait le pire des deux mondes.
    """
    projet, pile = pile_melangee
    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate.calibrer_la_chaine(projet, pile, dpi=DPI_DECLARE)

    assert leve.value.motif == scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION
    assert list(calibration_profile.documents_de_calibration(projet)) == [], (
        "un refus a laisse un profil derriere lui")

    # **Le volet symetrique, et il porte le sens du refus** : les planches
    # restent annoncees « non declare », ce qui est vrai -- rien ne les declare.
    # C'est exactement ce que la tolerance `B6` cachait.
    inventaire = project_inventory.inventorier_le_projet(projet)
    assert list(inventaire.calibrations) == []


@pytest.fixture(scope="module")
def projet_range_par_date(tmp_path_factory) -> tuple[Path, object]:
    """Une calibration REELLE sur une mire deja rangee a DEUX crans sous `scans/`.

    `scan_ingest._est_un_dossier_de_lot` accepte n'importe quelle profondeur sous
    `scans/`, et le commentaire de `ScanIngestReport.scans_dir` nomme lui-meme
    `scans/<date>/<lot>/` comme un cas d'usage paye sur le terrain. L'ingestion se
    fait donc EN PLACE, et le champ ecrit porte reellement deux crans.
    """
    projet = _projet_nu(tmp_path_factory.mktemp("par-date"))
    profond = projet / project_layout.SCANS_DIRNAME / "2026" / "janvier"
    profond.mkdir(parents=True)
    (profond / "mire.pdf").write_bytes(
        _exiger_le_raster(MIRE_REELLE).read_bytes())
    consigne = scan_calibrate.calibrer_la_chaine(projet, profond, dpi=DPI_DECLARE)
    return projet, consigne


def test_B2_un_dossier_range_par_DATE_garde_son_faux_orphelin(
    projet_range_par_date: tuple[Path, object],
) -> None:
    """`B2`, tolerance NOMMEE : l'appariement est une identite, jamais une ascendance.

    Le produit ecrit bien `scan_dir = 'scans/2026/janvier'` -- c'est mesure
    ci-dessous, sur le parcours entier et le raster reel --, mais `_orphelins` ne
    construit d'objet que pour les sous-dossiers **immediats** de `scans/`. Le
    noeud qui existe est `scans/2026`, et il n'est pas le dossier declare. Celui
    qui range ses scans par date recalibre donc et garde son faux orphelin.

    **L'apparier par ascendance a ete MESURE puis ECARTE**, plutot que juge :
    le noeud `scans/2026` porte l'annee ENTIERE. Le rattacher au profil ferait
    passer douze mois de planches en `calibrations` avec `ETAT_PRESENT` --
    c'est-a-dire le regime de `B6` multiplie par le nombre de lots de l'annee, et
    l'inverse exact de ce que l'inventaire existe pour montrer. « On n'arrete
    jamais un process par ressemblance, toujours par identite » : un noeud qui
    *contient* le dossier declare n'est pas le dossier declare.

    Le choix appartient a Egan et n'est pas tranche ici. Ce banc tient la mesure
    pour que la question se pose sur des chiffres et que le comportement ne derive
    pas en silence.
    """
    projet, consigne = projet_range_par_date
    document = json.loads(Path(consigne.profile_path).read_text(encoding="utf-8"))
    declare = document[calibration_profile.SCAN_DIR_FIELD]
    assert declare == f"{project_layout.SCANS_DIRNAME}/2026/janvier", declare
    assert (projet / declare).is_dir()
    # La normalisation ne change rien ici : la valeur est deja canonique. Ce n'est
    # donc pas la famille de `B1`, et les confondre ferait chercher au mauvais
    # endroit.
    assert calibration_profile.normaliser_le_dossier_de_scan(declare) == declare
    assert calibration_profile.dossiers_de_scan_declares(projet) == {declare}

    inventaire = project_inventory.inventorier_le_projet(projet)
    assert [objet.chemin for objet in inventaire.calibrations] == []
    assert [objet.chemin for objet in inventaire.orphelins
            if objet.nature == project_inventory.NATURE_SCAN] == [
                f"{project_layout.SCANS_DIRNAME}/2026"]

    # Le pendant, dans le meme banc : a UN cran, le meme parcours declare. Sans
    # lui, « rien ne se declare jamais » expliquerait aussi bien ce rouge.
    assert MIRE_REELLE.stem not in [objet.nom for objet in inventaire.calibrations]
