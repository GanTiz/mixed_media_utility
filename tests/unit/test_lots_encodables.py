# -*- coding: utf-8 -*-
"""Story 11.8, lot B2 -- l'enumeration des lots encodables (AC 3.1 a 3.5).

Le coeur savait **admettre** un lot (`check_lot_admission`) ; il ne savait pas
**lister** ceux qui le sont. Faute de quoi la TUI en jugeait elle-meme, sur une
table d'etats a elle, et se trompait **dans les deux sens a la fois** :

* **trop strict** -- un lot a l'etat `scan` portant ses frames est encodable par
  le coeur, et la TUI ne le comptait pas. Sur le seul lot du projet, l'entree
  `Exports` se fermait sur « aucun lot reconstruit » alors qu'`mmu encode`
  passe. Ce n'est pas une hypothese de banc : `projects/projet_demo` du depot
  porte **un** lot, et il est a l'etat `scan` ;
* **trop laxiste** -- un lot recree depuis des payloads porte
  `io/reconstruction.DEFAULT_LOT_STATE`, c'est-a-dire `reconstruction`, **sans**
  `output_frames_dir`. La TUI ouvrait, le coeur refusait par
  `ENCODE_OUTPUT_DIR_NOT_DECLARED` -- le motif d'existence de la garde, ecrit
  dans sa propre docstring.

**La regle des fabriques gouverne ce fichier** (`CLAUDE.md`, point 2 bis). La
fabrique porte **trois** lots aux valeurs distinguables, la cible **au milieu**,
et le lot qui la precede est **refuse** : un mutant `continue` -> `break` rend
alors la liste vide, la ou une fabrique a deux lots (cible en second, donc aussi
en dernier) ne l'aurait pas vu.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import encode as encode_module  # noqa: E402
from mixed_media_utility.io.manifest import LOT_STATES  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques -- trois lots, cible au milieu, deux etats distincts au moins
# ---------------------------------------------------------------------------

#: Le lot vise, et il n'est ni le premier ni le dernier de la fabrique.
CIBLE = "rush-002_25fps_2"

#: Ce qui le precede : l'erreur **trop laxiste**, celle que la TUI laissait
#: passer. Son identifiant **prefixe** celui de la cible, de sorte qu'un
#: appariement de prefixe ne se confondrait pas avec une egalite (defaut mesure
#: sur `test_encode_manifest.py`).
LAXISTE = "rush-002_25fps_2-a1b2c3d4"

#: Ce qui le suit : l'etat est en **amont** de `MINIMUM_LOT_STATE`, la matiere
#: est pourtant la. Un critere qui ne regarderait que le dossier l'admettrait.
TROP_TOT = "rush-001_12p5fps_1"


def lot(lot_id: str, etat: str, dossier: str | None = None,
        cardinal: int | None = None) -> dict:
    """Un lot du manifest, aux valeurs **distinguables** par construction.

    Le cardinal attendu differe d'un lot a l'autre : une fabrique uniforme ne
    demasquerait pas une inversion d'appariement entre un lot et ce qu'on lui
    attribue.
    """
    entree: dict = {"lot_id": lot_id, "state": etat,
                    "expected_frame_count": cardinal}
    if dossier is not None:
        entree["output_frames_dir"] = dossier
    return entree


def manifeste(lots) -> dict:
    return {"schema_version": "2.1", "project_id": "p",
            "rushes": [], "lots": list(lots), "artifacts": {}, "color": {},
            "video": {}, "reconstruction": {}}


def projet(tmp_path: Path, lots) -> tuple[Path, dict]:
    """Une racine de projet et son manifest, dossiers declares **crees**.

    Un lot qui declare un dossier voit ce dossier exister : c'est ce qui rend
    les trois volets du critere separement falsifiables -- pour mesurer
    l'absence du dossier, un test l'efface explicitement.
    """
    racine = tmp_path / "projet"
    racine.mkdir(exist_ok=True)
    for entree in lots:
        declare = entree.get("output_frames_dir")
        if declare:
            (racine / declare).mkdir(parents=True, exist_ok=True)
    return racine, manifeste(lots)


def trois_lots(tmp_path: Path) -> tuple[Path, dict]:
    """La fabrique de reference : trois lots, deux etats distincts, cible au
    milieu, et un lot **refuse avant elle**."""
    return projet(tmp_path, [
        lot(LAXISTE, "reconstruction", dossier=None, cardinal=11),
        lot(CIBLE, "scan", dossier=f"output-frames/{CIBLE}", cardinal=22),
        lot(TROP_TOT, "pdf", dossier=f"output-frames/{TROP_TOT}", cardinal=33),
    ])


def ids(admis) -> list[str]:
    return [entree.lot.get("lot_id") for entree in admis]


# ---------------------------------------------------------------------------
# AC 3.5 -- la fabrique elle-meme, mesuree avant ce qu'elle sert a mesurer
# ---------------------------------------------------------------------------

def test_la_fabrique_tient_la_regle_des_FABRIQUES(tmp_path):
    """AC 3.5. **La fabrique se mesure**, sinon la regle n'est qu'une intention.

    Trois elements, la cible strictement au milieu, au moins deux etats
    distincts, et des cardinaux tous differents. Le point 2 bis est explicite :
    une cible en seconde position sur deux elements est **aussi** la derniere,
    et les deux formes y sont indiscernables.
    """
    _, document = trois_lots(tmp_path)
    lots = document["lots"]
    assert len(lots) >= 3, lots
    rang = [entree["lot_id"] for entree in lots].index(CIBLE)
    assert 0 < rang < len(lots) - 1, rang
    assert len({entree["state"] for entree in lots}) >= 2, lots
    cardinaux = [entree["expected_frame_count"] for entree in lots]
    assert len(set(cardinaux)) == len(cardinaux), cardinaux


# ---------------------------------------------------------------------------
# AC 3.1 -- le meme critere, et il est APPELE et non recopie
# ---------------------------------------------------------------------------

def test_l_enumeration_rend_EXACTEMENT_le_lot_que_la_garde_admet(tmp_path):
    """AC 3.1, et l'assertion est une **egalite d'ensemble**.

    « Ce lot est liste » ne mesure rien ; « l'ensemble des lots listes est
    exactement {cible} » mesure l'admission **et** son unicite -- une assertion
    positive laisserait passer toute admission supplementaire.
    """
    racine, document = trois_lots(tmp_path)
    assert ids(encode_module.list_encodable_lots(document, racine)) == [CIBLE]


def test_le_verdict_de_l_enumeration_est_CELUI_DE_LA_GARDE_lot_par_lot(tmp_path):
    """AC 3.1 -- confrontation, jamais relecture.

    Les deux chemins sont compares **lot par lot** sur une fabrique qui couvre
    les quatre issues de la garde : admis, etat trop tot, dossier non declare,
    dossier absent. Un critere recopie qui divergerait sur une seule des quatre
    fait rougir ici, quel que soit le sens de la divergence.
    """
    racine, document = projet(tmp_path, [
        lot(LAXISTE, "reconstruction", dossier=None, cardinal=11),
        lot(CIBLE, "scan", dossier=f"output-frames/{CIBLE}", cardinal=22),
        lot(TROP_TOT, "pdf", dossier=f"output-frames/{TROP_TOT}", cardinal=33),
        lot("rush-003_efface", "encode", dossier="output-frames/efface",
            cardinal=44),
    ])
    (racine / "output-frames" / "efface").rmdir()

    par_la_garde = []
    for entree in document["lots"]:
        try:
            encode_module.check_lot_admission(entree, racine)
        except encode_module.EncodeDecisionError:
            continue
        par_la_garde.append(entree["lot_id"])

    assert ids(encode_module.list_encodable_lots(document, racine)) \
        == par_la_garde == [CIBLE]


def test_l_enumeration_n_ecrit_AUCUN_critere_a_elle(tmp_path):
    """AC 3.1, frontiere **negative** sur le source de la fonction.

    Elle appelle la garde et ne la reecrit pas : son corps ne compare rien a un
    etat de lot, ne nomme pas `output_frames_dir`, et **cite**
    `check_lot_admission`. Aucun test de comportement ne verrait revenir une
    seconde redaction qui, ce jour-la, dirait la meme chose que la premiere --
    c'est le mode de panne exact que cette story ferme, et il ne se voit qu'au
    source.
    """
    import ast
    import inspect

    arbre = ast.parse(inspect.getsource(encode_module.list_encodable_lots))
    corps = [noeud for noeud in ast.walk(arbre)
             if not isinstance(noeud, ast.Expr)
             or not isinstance(getattr(noeud, "value", None), ast.Constant)]
    litteraux = {noeud.value for noeud in ast.walk(ast.Module(body=corps,
                                                             type_ignores=[]))
                 if isinstance(noeud, ast.Constant)
                 and isinstance(noeud.value, str)}
    assert litteraux & set(LOT_STATES) == set(), litteraux
    assert "output_frames_dir" not in litteraux, litteraux
    appels = {noeud.func.id for noeud in ast.walk(arbre)
              if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)}
    assert "check_lot_admission" in appels, appels


# ---------------------------------------------------------------------------
# AC 3.2 -- l'erreur TROP LAXISTE
# ---------------------------------------------------------------------------

def test_un_lot_reconstruction_SANS_output_frames_dir_n_est_PAS_liste(tmp_path):
    """AC 3.2 -- le cas nominal d'un projet recree depuis les payloads.

    Son etat est **superieur** a `MINIMUM_LOT_STATE` : une garde d'etat seule
    l'admet, et c'est precisement ce que la TUI faisait.
    """
    racine, document = trois_lots(tmp_path)
    assert LAXISTE not in ids(encode_module.list_encodable_lots(document, racine))


def test_le_MEME_lot_devient_liste_des_qu_il_porte_ses_frames(tmp_path):
    """AC 3.2, **volet symetrique**. Sans lui, une enumeration qui ne rendrait
    jamais rien serait verte au test precedent.

    Seul le dossier change : meme identifiant, meme etat. Ce qui exclut le lot
    est donc bien la matiere, et non son etat.
    """
    racine, document = projet(tmp_path, [
        lot("rush-000_amont", "extraction", cardinal=5),
        lot(LAXISTE, "reconstruction", dossier=f"output-frames/{LAXISTE}",
            cardinal=11),
        lot(TROP_TOT, "pdf", dossier=f"output-frames/{TROP_TOT}", cardinal=33),
    ])
    assert ids(encode_module.list_encodable_lots(document, racine)) == [LAXISTE]


def test_un_dossier_DECLARE_mais_ABSENT_ne_suffit_pas(tmp_path):
    """AC 3.2, troisieme volet du critere. La declaration n'est pas la
    presence, et `ENCODE_OUTPUT_DIR_ABSENT` existe pour les distinguer."""
    racine, document = trois_lots(tmp_path)
    (racine / "output-frames" / CIBLE).rmdir()
    assert ids(encode_module.list_encodable_lots(document, racine)) == []


# ---------------------------------------------------------------------------
# AC 3.3 -- l'erreur TROP STRICT
# ---------------------------------------------------------------------------

def test_un_lot_a_l_etat_scan_AVEC_son_dossier_EST_liste(tmp_path):
    """AC 3.3 -- l'etat `scan` **est** le plancher, et la TUI le refusait.

    Le plancher est lu de `MINIMUM_LOT_STATE`, jamais recopie : le mutant `>=`
    -> `>` de la table de la story fait sortir ce lot exact de la liste.
    """
    racine, document = trois_lots(tmp_path)
    assert encode_module.MINIMUM_LOT_STATE == \
        document["lots"][1]["state"], "la fabrique doit viser le plancher"
    assert CIBLE in ids(encode_module.list_encodable_lots(document, racine))


@pytest.mark.parametrize("etat", LOT_STATES)
def test_le_plancher_d_etat_est_celui_du_COEUR_pour_les_cinq_etats(etat, tmp_path):
    """AC 3.3, balayage complet de la machine a etats.

    L'attendu se **derive** de `LOT_STATES` et de `MINIMUM_LOT_STATE` au lieu
    d'etre recopie : un etat ajoute au coeur entre dans cette mesure sans
    qu'on y touche. La cible reste au milieu de trois lots.
    """
    attendu = LOT_STATES.index(etat) >= LOT_STATES.index(
        encode_module.MINIMUM_LOT_STATE)
    racine, document = projet(tmp_path, [
        lot(LAXISTE, "reconstruction", dossier=None, cardinal=11),
        lot(CIBLE, etat, dossier=f"output-frames/{CIBLE}", cardinal=22),
        lot(TROP_TOT, "extraction", dossier=f"output-frames/{TROP_TOT}",
            cardinal=33),
    ])
    assert (CIBLE in ids(encode_module.list_encodable_lots(document, racine))) \
        is attendu


# ---------------------------------------------------------------------------
# La boucle, et les deux mutants de terminaison
# ---------------------------------------------------------------------------

def test_un_refus_n_ARRETE_PAS_la_passe(tmp_path):
    """Mutant `continue` -> `break` : le premier lot de la fabrique est refuse,
    donc un arret sur refus rend une liste **vide** au lieu de la cible.

    C'est le point 2 bis de la regle des fabriques, litteralement : une fabrique
    a deux elements ne separe pas « la cible est en second » de « la cible est
    en dernier », et ce mutant y survit.
    """
    racine, document = trois_lots(tmp_path)
    assert document["lots"][0]["lot_id"] == LAXISTE, "un refus doit ouvrir"
    assert ids(encode_module.list_encodable_lots(document, racine)) == [CIBLE]


def test_une_admission_n_ARRETE_PAS_la_passe_non_plus(tmp_path):
    """Mutant symetrique -- un `break` apres la premiere admission.

    Deux lots admis encadrent un refus, et l'ordre rendu est celui du
    **manifest** : les identifiants sont choisis pour que l'ordre alphabetique
    en differe, de sorte qu'un `sorted` glisse dans l'enumeration rougisse.
    """
    racine, document = projet(tmp_path, [
        lot("zulu-001", "encode", dossier="output-frames/zulu", cardinal=7),
        lot(LAXISTE, "reconstruction", dossier=None, cardinal=11),
        lot("alpha-002", "scan", dossier="output-frames/alpha", cardinal=13),
    ])
    rendus = ids(encode_module.list_encodable_lots(document, racine))
    assert rendus == ["zulu-001", "alpha-002"], rendus
    assert rendus != sorted(rendus), "l'ordre du manifest, jamais un tri"


# ---------------------------------------------------------------------------
# Ce que l'enumeration rend, et ce qu'elle encaisse
# ---------------------------------------------------------------------------

def test_le_dossier_rendu_est_CELUI_QUE_LA_GARDE_resout(tmp_path):
    """Le chemin part avec le lot : l'appelant n'a pas a recomposer
    `racine / output_frames_dir`, ce qui serait une seconde redaction de la
    convention de chemin."""
    racine, document = trois_lots(tmp_path)
    (admis,) = encode_module.list_encodable_lots(document, racine)
    assert admis.output_frames_dir == encode_module.check_lot_admission(
        document["lots"][1], racine)
    assert admis.output_frames_dir == racine / "output-frames" / CIBLE
    assert admis.output_frames_dir.is_dir()


def test_le_lot_rendu_est_L_ENTREE_DU_MANIFEST_elle_meme(tmp_path):
    """Pas une copie appauvrie : l'ecran de designation lira le cardinal, la
    cadence et l'etat sur ce qu'on lui rend."""
    racine, document = trois_lots(tmp_path)
    (admis,) = encode_module.list_encodable_lots(document, racine)
    assert admis.lot is document["lots"][1]
    assert admis.lot["expected_frame_count"] == 22


def test_une_racine_donnee_en_CHAINE_est_acceptee(tmp_path):
    """La TUI porte parfois le dossier en `str` -- refuser la aurait fait
    recomposer un `Path` chez l'appelant."""
    racine, document = trois_lots(tmp_path)
    assert ids(encode_module.list_encodable_lots(document, str(racine))) == [CIBLE]


@pytest.mark.parametrize("document", [
    {}, {"lots": None}, {"lots": []}, {"lots": ["une chaine", 12, None]},
])
def test_un_manifest_sans_lots_LISIBLES_rend_une_liste_vide(document, tmp_path):
    """Elle ne leve jamais : le menu doit s'ouvrir sur un document casse et
    dire ce qu'il ne sait pas, plutot que de tomber."""
    assert encode_module.list_encodable_lots(document, tmp_path) == []


def test_les_entrees_ILLISIBLES_sont_sautees_sans_emporter_les_autres(tmp_path):
    """Une entree non-mapping au **milieu** : un `for` qui tomberait dessus
    perdrait le lot qui la suit."""
    racine, document = trois_lots(tmp_path)
    document["lots"].insert(1, "ceci n'est pas un lot")
    assert ids(encode_module.list_encodable_lots(document, racine)) == [CIBLE]
