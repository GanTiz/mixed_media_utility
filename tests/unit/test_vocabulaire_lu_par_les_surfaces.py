# -*- coding: utf-8 -*-
"""Story 11.14, AC 1.3 -- le vocabulaire publie est-il ATTEINT ?

**Ce que ce banc mesure, et pourquoi il n'existait pas.** La story 11.14 publie
huit natures et leur table dans `project_inventory`, sous une docstring qui
dit : « une interface le LIT, elle ne le REDIGE pas ». La revue du 2026-09-04,
couche 3 (*acceptance auditor*), a mesure que **c'etait faux** : un balayage AST
de tout `src/` ne trouvait AUCUN import de `project_inventory` hors du module
lui-meme -- seulement une mention en commentaire. Le vocabulaire publie
n'atteignait donc aucune surface, ce qui est **exactement le mode de panne que
l'AC 1.3 nomme** (« sinon 1.2 serait satisfaite par une surface qui n'affiche
rien »).

La consequence etait deja visible et mesuree : sur `mmu project remove --lot L
--lot-scanne --version 2`, le coeur rendait « element 'L (lot scanne v2)' » et
`cli.py` repondait, **dans le meme ecran**, « les jeux de frames scannees
posterieurs ». Deux mots pour un objet, la ou `EPIC11-ARB-223` a tranche « lot
scanne, partout ».

**Pourquoi ce banc ne compte PAS les imports.** Une frontiere qui compterait
les `import project_inventory` serait verte des qu'un module en importe un
symbole quelconque, y compris sans jamais s'en servir pour ce qu'il affiche.
Ce qui doit se mesurer, c'est que le **libelle rendu a l'operateur DERIVE de la
table** -- donc qu'il SUIT la table quand elle change. Les deux moities sont
ici, et aucune ne se deduit de l'autre :

1. :func:`test_AC1_3_le_libelle_RENDU_par_la_CLI_est_celui_de_la_TABLE` --
   statique, et elle porte sur les **deux producteurs** de l'ecran : la ligne
   d'apercu vient du coeur (`project_maintenance._FamilleVersionnee`), la ligne
   du rang vient de `cli.py`. Une divergence entre eux rougit ici ;
2. :func:`test_AC1_3_le_libelle_rendu_SUIT_la_table_quand_elle_CHANGE` --
   dynamique : la table est remplacee par un temoin et l'ecran doit le porter.
   C'est la seule des deux qui distingue un libelle **lu** d'un libelle
   **recopie**, puisqu'un litteral fige reste vrai tant que la table ne bouge
   pas. C'est aussi ce qui manquait : la couverture existait cote CLI, mais
   elle **epinglait le mot faux**
   (`test_le_message_du_rang_est_au_PLURIEL_correct` assertait « jeux de frames
   scannees posterieurs »).

**Ce que ce banc NE mesure pas, dit plutot que tu :**

* le coeur `project_maintenance` ne peut pas **importer** la table : c'est
  `project_inventory` qui importe `project_maintenance` (six noms, mesures a
  l'ensemble exact par `test_A2_l_ensemble_EXACT_des_lectures_empruntees...`),
  et l'inverse ferait un cycle. Son libelle reste donc un litteral, **lie a la
  table par la mesure** (1) plutot que par un import. Le fermer autrement
  demanderait de descendre le vocabulaire sous les deux modules, ce qui n'est
  pas un geste de revue ;
* il ne balaye pas `tui/` : deux autres agents y travaillent, et son volet de
  l'AC 1.3 a son propre banc
  (`tests/unit/tui/test_vocabulaire_de_la_tui.py`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mixed_media_utility import project_inventory
from mixed_media_utility.io import project_layout


# ---------------------------------------------------------------------------
# La fabrique -- QUATRE lots scannes distinguables, et la cible a CHAQUE BORD
# ---------------------------------------------------------------------------

#: **Quatre rangs, quatre cardinaux DISTINCTS** (regle des fabriques, points 1
#: a 4). Un remplissage uniforme rendrait invisible une erreur d'appariement,
#: et une cible toujours au milieu ne demasque pas un balayage tronque : les
#: tests ci-dessous visent donc la TETE (1), le MILIEU (2) et la QUEUE (4).
RANGS_DU_LOT_SCANNE = (1, 2, 3, 4)

#: Le cardinal de fichiers de chaque rang -- distinct rang par rang, pour qu'un
#: dossier lu a la place d'un autre se voie.
CARDINAL_PAR_RANG = {rang: rang for rang in RANGS_DU_LOT_SCANNE}


def _racine_des_lots_scannes(projet: Path) -> Path:
    """La racine des frames scannees, LUE de `io/project_layout`.

    Jamais composee a la main : `project_layout` est le seul lieu du depot ou
    ces noms sont ecrits, et le seul qui connaisse la cohabitation du nom neuf
    et de celui d'avant (`EPIC11-ARB-222`). La frontiere
    `test_aucun_banc_GARDE_ne_compose_un_nom_de_dossier_a_la_main` a rougi sur
    la premiere redaction de cette fabrique, qui ecrivait le litteral.
    """
    return projet / project_layout.SCAN_FRAMES_DIRNAME


def _projet_a_quatre_lots_scannes(tmp_path: Path) -> Path:
    """Un projet dont le lot `L` porte QUATRE lots scannes, plus des voisins.

    Le lot vise n'est pas le premier du manifeste (`AVANT` le precede), et un
    lot voisin porte lui aussi des lots scannes : un `find` qui rendrait le
    premier lot venu, ou qui melangerait les familles, se voit.
    """
    lot = {
        "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
        "output_frames_dir": f"{project_layout.SCAN_FRAMES_DIRNAME}/L",
        "encoded_masters": [
            {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
            {"path": "outputs/L_mmu_prores_422_v2.mov",
             "profile_id": "prores_422", "version_rank": 2},
            {"path": "outputs/L_mmu_prores_422_v3.mov",
             "profile_id": "prores_422", "version_rank": 3},
        ],
        # Trois PLANCHES, pour que le mot de `--planche` se mesure comme les
        # trois autres : `Q5` est fermee depuis `EPIC11-ARB-224` (« "--tirage"
        # n'est pas un mot de vocabulaire. C'est "planche". »), donc cette
        # cible entre dans la table du vocabulaire au lieu d'en etre exclue.
        "sheets_pdfs": [
            {"path": "outputs/p_planches.pdf"},
            {"path": "outputs/p_planches_v2.pdf", "version_rank": 2},
            {"path": "outputs/p_planches_v3.pdf", "version_rank": 3},
        ],
        "reconstructions": [
            {"ingest_slug": "S"}, {"ingest_slug": "S_v2"}, {"ingest_slug": "S_v3"},
        ],
    }
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R0"}, {"rush_id": "R"}],
        "lots": [
            {"lot_id": "AVANT", "rush_id": "R0"},
            lot,
            {"lot_id": "APRES", "rush_id": "R0"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")

    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in lot["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")
    for entree in lot["sheets_pdfs"]:
        (projet / entree["path"]).write_bytes(b"pdf")
    for slug in ("S", "S_v2", "S_v3"):
        dossier = projet / project_layout.SCANS_DIRNAME / slug
        dossier.mkdir(parents=True)
        (dossier / "p.tiff").write_bytes(b"page")

    for rang in RANGS_DU_LOT_SCANNE:
        nom = "L" if rang == 1 else f"L_v{rang}"
        dossier = _racine_des_lots_scannes(projet) / nom
        dossier.mkdir(parents=True)
        for index in range(CARDINAL_PAR_RANG[rang]):
            (dossier / f"f{index}.tiff").write_bytes(b"frame")
    # Un lot scanne du VOISIN : il ne doit jamais compter dans la famille de L.
    voisin = _racine_des_lots_scannes(projet) / "APRES"
    voisin.mkdir(parents=True)
    (voisin / "f0.tiff").write_bytes(b"frame")
    return projet


def test_la_fabrique_porte_bien_QUATRE_rangs_aux_cardinaux_DISTINCTS(tmp_path):
    """**Volet symetrique de la fabrique**, et il n'est pas decoratif.

    Les tests de bord ci-dessous visent les rangs 1, 2 et 4. Si la fabrique
    n'en ecrivait que deux -- une troncature, un `range` mal borne --, ils
    resteraient verts en cessant de mesurer les bords : c'est le mode de panne
    exact que ce depot a paye quatre fois sur cette story. On mesure donc
    l'ENSEMBLE des dossiers ecrits et leurs cardinaux, pas leur nombre.
    """
    projet = _projet_a_quatre_lots_scannes(tmp_path)
    racine = _racine_des_lots_scannes(projet)
    ecrits = {chemin.name: len(list(chemin.iterdir()))
              for chemin in racine.iterdir()}
    assert ecrits == {"L": 1, "L_v2": 2, "L_v3": 3, "L_v4": 4, "APRES": 1}, ecrits


def _jouer_la_suppression(projet: Path, *arguments: str) -> None:
    """Joue `mmu project remove` en apercu (dry-run) et exige son succes.

    L'ecran se lit ensuite par `capsys` : ces bancs mesurent ce qui SORT, pas
    une valeur de retour -- une commande qui rendrait `0` en n'imprimant rien
    passerait un test de code de sortie.
    """
    from mixed_media_utility import cli

    code = cli.main(["project", "remove", "--project", str(projet), *arguments])
    assert code == 0, code


# ---------------------------------------------------------------------------
# La table publiee, mesuree dans les deux sens
# ---------------------------------------------------------------------------


def test_AC1_3_la_table_des_LIBELLES_couvre_EXACTEMENT_les_natures():
    """Une egalite d'ensembles, jamais une inclusion.

    Les deux moities attrapent deux pannes differentes, et c'est la lecon de
    l'AC 1.4 transposee ici : une nature sans libelle est une surface qui ne
    peut rien afficher ; un libelle sans nature est une surface MORTE -- le
    defaut du 2026-08-31, quatre champs de ligne d'eau declares et ecrits par
    aucun chemin.
    """
    natures = set(project_inventory.NATURES)
    libelles = set(project_inventory.LIBELLES_DES_NATURES)
    assert libelles == natures, sorted(libelles ^ natures)


@pytest.mark.parametrize("nature", project_inventory.NATURES)
def test_AC1_3_le_SINGULIER_derive_de_l_IDENTIFIANT_de_la_nature(nature):
    """Le singulier est la nature dont les soulignes sont des espaces.

    C'est ce qui empeche un TROISIEME mot d'entrer par la table elle-meme :
    « jeu de frames scannees » ne derive d'aucune des huit natures, et le jour
    ou quelqu'un l'ecrirait ici, ce test le dirait. Meme geste que
    `test_le_mot_de_la_TUI_est_celui_de_la_NATURE_publiee_par_le_coeur`.
    """
    singulier, _pluriel = project_inventory.libelles_de_nature(nature)
    assert singulier == nature.replace("_", " ")


def test_AC1_3_le_PLURIEL_n_est_pas_partout_le_SINGULIER():
    """Volet symetrique du precedent : sans lui, une table qui rendrait deux
    fois le singulier serait verte partout.

    Six natures sur huit ont un pluriel DISTINCT ; les deux natures de CONTENU
    (« frames extraites », « frames scannees ») sont invariables parce que le
    mot l'est. On mesure les deux ensembles, pas leur cardinal.
    """
    distincts = {nature for nature, (s, p)
                 in project_inventory.LIBELLES_DES_NATURES.items() if s != p}
    invariables = set(project_inventory.NATURES) - distincts
    assert invariables == {project_inventory.NATURE_FRAMES_EXTRAITES,
                           project_inventory.NATURE_FRAMES_SCANNEES}, invariables
    # Et le pluriel n'est jamais un simple `singulier + "s"` sur un GROUPE
    # nominal : c'est le defaut « les jeu de framess posterieurs ».
    singulier, pluriel = project_inventory.libelles_de_nature(
        project_inventory.NATURE_LOT_SCANNE)
    assert pluriel != f"{singulier}s"


# ---------------------------------------------------------------------------
# AC 1.3 -- le libelle RENDU derive de la table
# ---------------------------------------------------------------------------

#: Les QUATRE cibles fines de `project remove`, avec la nature qu'elles
#: designent.
#:
#: **`--planche` y est entree le 2026-09-05, et son absence etait nommee.**
#: Cette table portait trois lignes et disait : « `--tirage` n'y est PAS [...]
#: `Q5` (planche / tirage) est ouverte, la nature publiee s'appelle `planche`
#: et l'option `tirage`. Les lier trancherait `Q5` en silence. » `Q5` est
#: tranchee -- Egan, verbatim : « "--tirage" n'est pas un mot de vocabulaire.
#: C'est "planche". » --, donc la cible rejoint les trois autres et son mot se
#: LIT de la table comme le leur.
#:
#: `EPIC11-ARB-224` : on designe un objet par les ARGUMENTS QUI L'ONT PRODUIT.
#: Un master se retrouve par son profil d'encodage, jamais par un chemin.
CIBLES_DU_VOCABULAIRE = (
    ("master", ("--master", "--profile", "prores_422", "--version", "3"),
     project_inventory.NATURE_MASTER),
    ("planche", ("--planche", "--version", "3"),
     project_inventory.NATURE_PLANCHE),
    ("scan", ("--scan", "S", "--version", "3"),
     project_inventory.NATURE_SCAN),
    ("lot scanne", ("--lot-scanne", "--version", "2"),
     project_inventory.NATURE_LOT_SCANNE),
)


@pytest.mark.parametrize("nom,argv,nature", CIBLES_DU_VOCABULAIRE)
def test_AC1_3_le_libelle_RENDU_par_la_CLI_est_celui_de_la_TABLE(
    tmp_path, capsys, nom, argv, nature
):
    """**La moitie statique**, et elle porte sur les DEUX producteurs de
    l'ecran : la ligne d'apercu vient du coeur, la ligne du rang de `cli.py`.

    C'est ce qui lie `project_maintenance` a la table sans lui demander un
    import qui serait un cycle : le jour ou son `_FamilleVersionnee(nom=...)`
    dirait un autre mot que celui de la table, ce test rougirait.
    """
    projet = _projet_a_quatre_lots_scannes(tmp_path)
    singulier, _pluriel = project_inventory.libelles_de_nature(nature)
    _jouer_la_suppression(projet, "--lot", "L", *argv)
    rendu = capsys.readouterr().out

    lignes_d_apercu = [l for l in rendu.splitlines() if l.startswith("Apercu:")]
    assert lignes_d_apercu, rendu
    assert singulier in lignes_d_apercu[0], (
        f"le COEUR ne nomme pas {nature!r} par son libelle publie "
        f"{singulier!r} : {lignes_d_apercu[0]!r}")

    lignes_du_rang = [l for l in rendu.splitlines() if "rang" in l.lower()]
    assert lignes_du_rang, rendu
    assert any(singulier in ligne for ligne in lignes_du_rang), (
        f"la CLI ne nomme pas {nature!r} par son libelle publie "
        f"{singulier!r} : {lignes_du_rang!r}")


@pytest.mark.parametrize("nom,argv,nature", CIBLES_DU_VOCABULAIRE)
def test_AC1_3_le_libelle_rendu_SUIT_la_table_quand_elle_CHANGE(
    tmp_path, capsys, monkeypatch, nom, argv, nature
):
    """**La moitie qui distingue un libelle LU d'un libelle RECOPIE.**

    Un litteral fige dans `cli.py` reste vrai tant que la table ne bouge pas :
    aucune assertion statique ne le demasque. On remplace donc la table par un
    temoin -- un mot qui n'est celui d'aucun objet du depot -- et l'ecran doit
    le porter. Si `cli.py` redigeait son mot, le temoin serait absent.

    C'est litteralement l'AC 1.3 (« chaque surface qui affiche une nature la
    LIT de cette table »), mesuree sur ce qui sort plutot que sur un import.
    """
    temoin_singulier = f"objet-temoin-{nom.replace(' ', '-')}"
    temoin_pluriel = f"{temoin_singulier}-au-pluriel"
    table = dict(project_inventory.LIBELLES_DES_NATURES)
    table[nature] = (temoin_singulier, temoin_pluriel)
    monkeypatch.setattr(project_inventory, "LIBELLES_DES_NATURES", table)

    projet = _projet_a_quatre_lots_scannes(tmp_path)
    _jouer_la_suppression(projet, "--lot", "L", *argv)
    rendu = capsys.readouterr().out

    lignes_du_rang = [l for l in rendu.splitlines() if "rang" in l.lower()]
    assert any(temoin_singulier in ligne for ligne in lignes_du_rang), (
        f"la CLI n'a pas SUIVI la table pour {nature!r} : elle REDIGE son mot "
        f"au lieu de le lire.\n{rendu}")


@pytest.mark.parametrize("rang,bord", [(1, "tete"), (2, "milieu"), (4, "queue")])
def test_AC1_3_le_mot_du_lot_scanne_tient_a_CHAQUE_BORD_de_la_famille(
    tmp_path, capsys, rang, bord
):
    """Regle des fabriques, point 4 -- en TETE, au MILIEU et en QUEUE.

    Le mot ne depend pas du rang, et c'est justement ce qui doit etre mesure :
    le message de rang de `cli.py` a PLUSIEURS branches, et les trois bords
    n'en traversent pas la meme -- les rangs 1 et 2 rendent « le rang reste
    CONSOMME: un lot scanne posterieur existe », le rang 4 rend « Ce lot
    scanne est le DERNIER a date ». Chacune ecrit le mot pour son compte :
    viser un seul rang aurait ferme une branche et laisse l'autre.
    """
    projet = _projet_a_quatre_lots_scannes(tmp_path)
    singulier, pluriel = project_inventory.libelles_de_nature(
        project_inventory.NATURE_LOT_SCANNE)
    _jouer_la_suppression(projet, "--lot", "L", "--lot-scanne",
                          "--version", str(rang))
    rendu = capsys.readouterr().out

    lignes_du_rang = [l for l in rendu.splitlines() if "rang" in l.lower()]
    assert lignes_du_rang, rendu
    assert any(singulier in ligne or pluriel in ligne
               for ligne in lignes_du_rang), (bord, lignes_du_rang)


def test_AC1_3_le_COEUR_et_la_CLI_disent_le_MEME_mot_dans_le_MEME_ecran(
    tmp_path, capsys
):
    """**Le finding F2, mesure sur la sortie qui l'a revele.**

    `EPIC11-ARB-223`, verbatim : « Lot scanne, partout ». L'ecran de
    `--lot-scanne` portait « lot scanne » (coeur) et « jeux de frames
    scannees » (`cli.py`) a deux lignes d'ecart. Le controle negatif porte sur
    le mot RETIRE -- un troisieme nom pour le meme objet --, pas seulement sur
    la presence du bon : une assertion positive seule resterait verte le jour
    ou les deux mots cohabiteraient a nouveau.
    """
    projet = _projet_a_quatre_lots_scannes(tmp_path)
    singulier, pluriel = project_inventory.libelles_de_nature(
        project_inventory.NATURE_LOT_SCANNE)
    _jouer_la_suppression(projet, "--lot", "L", "--lot-scanne", "--version", "2")
    rendu = capsys.readouterr().out

    assert f"({singulier} v2)" in rendu, rendu
    assert pluriel in rendu, rendu
    # Le TROISIEME mot, retire par `EPIC11-ARB-223`, n'est plus dans l'ecran.
    assert "jeu de frames scannees" not in rendu, rendu
    assert "jeux de frames scannees" not in rendu, rendu
