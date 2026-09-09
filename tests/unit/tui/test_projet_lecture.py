# -*- coding: utf-8 -*-
"""Le modele pur du palier 1 (story 11.3, task 1 -- AC 2, 3, 4).

Trois calculs, et les trois portent un piege deja paye dans ce depot : un
compteur pris sur le premier element, un `find` qui rend toujours le premier, et
une condition derivee d'une collection vide. La regle des fabriques est donc
appliquee collection par collection -- **au moins trois elements distinguables,
et la cible jamais en premiere ni en derniere position**.
"""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import encode
from mixed_media_utility.io.manifest import LOT_STATES
from mixed_media_utility.tui import projet_lecture


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def lot(lot_id: str, etat: str = "extraction", confirme: str | None = None,
        masters: int = 0, dossier: str | None = None) -> dict:
    """Un lot du manifest, aux valeurs **distinguables** par construction.

    `dossier` porte `output_frames_dir`. Il est **facultatif et absent par
    defaut** parce que c'est l'etat reel d'un lot recree depuis des payloads --
    le cas qui ouvrait `Exports` a tort avant la story 11.8.
    """
    entree = {"lot_id": lot_id, "state": etat,
              "encoded_masters": [{"path": f"outputs/{lot_id}_{n}.mov"}
                                  for n in range(masters)]}
    if dossier is not None:
        entree["output_frames_dir"] = dossier
    if confirme is not None:
        entree["confirmation"] = {"mode": "interactif",
                                  "unknown_color_accepted": False,
                                  "confirmed_at": confirme}
    return entree


def projet(tmp_path, lots) -> tuple:
    """Une racine de projet ou les dossiers declares **existent**.

    Sans elle, la condition d'`Exports` ne se mesure pas : depuis la story
    11.8, elle est le verdict du coeur, et ce verdict porte sur la matiere --
    un `output_frames_dir` declare **et present** -- autant que sur l'etat.
    """
    racine = tmp_path / "projet"
    racine.mkdir(exist_ok=True)
    for entree in lots:
        declare = entree.get("output_frames_dir")
        if declare:
            (racine / declare).mkdir(parents=True, exist_ok=True)
    return racine, manifeste(lots)


def manifeste(lots=(), rushes=2) -> dict:
    return {"schema_version": "2.1", "project_id": "p",
            "rushes": [{"rush_id": f"r{n}"} for n in range(rushes)],
            "lots": list(lots), "artifacts": {}, "color": {}, "video": {},
            "reconstruction": {}}


# ---------------------------------------------------------------------------
# AC 4 -- les compteurs
# ---------------------------------------------------------------------------

def test_les_masters_sont_la_SOMME_sur_tous_les_lots(tmp_path):
    """AC 4.2, et c'est la mesure qui compte.

    **Plusieurs lots portent des masters, et un n'en porte aucun** : un compte
    pris sur `lots[0]` serait juste tant qu'un seul lot en porte, ce qu'une
    fixture mono-lot ne demasque jamais. Le lot sans master est place **au
    milieu**, si bien qu'un `sum` qui s'arreterait au premier zero rougirait.
    """
    document = manifeste([
        lot("a", masters=2),
        lot("b", masters=0),
        lot("c", masters=3),
    ])
    compteurs = projet_lecture.compter(document)
    assert compteurs.masters == 5
    assert compteurs.lots == 3
    assert compteurs.rushes == 2


def test_un_projet_vide_rend_ZERO_et_non_une_chaine_vide():
    """AC 4.3 : « jamais une ligne vide »."""
    rendu = projet_lecture.compter(manifeste(rushes=0)).rendu()
    assert rendu == "0 rush · 0 lot · 0 master"


def test_les_accords_suivent_le_nombre():
    rendu = projet_lecture.compter(manifeste([lot("a")], rushes=3)).rendu()
    assert rendu == "3 rushes · 1 lot · 0 master"


def test_un_manifeste_illisible_ne_fait_pas_tomber_les_compteurs():
    assert projet_lecture.compter(None).rendu() == "0 rush · 0 lot · 0 master"


def test_lire_manifeste_ne_leve_jamais(tmp_path):
    assert projet_lecture.lire_manifeste(tmp_path / "nulle_part") is None
    (tmp_path / "project.json").write_text("{ casse", encoding="utf-8")
    assert projet_lecture.lire_manifeste(tmp_path) is None


# ---------------------------------------------------------------------------
# AC 2 -- les conditions des entrees
# ---------------------------------------------------------------------------

def test_les_cinq_entrees_sont_TOUJOURS_rendues():
    """AC 2.1 : « un operateur doit pouvoir voir ce qui existe avant de savoir
    qu'il n'y a pas acces »."""
    for document in (manifeste(), manifeste([lot("a")]), None):
        noms = [entree.nom for entree in projet_lecture.entrees(document)]
        assert noms == ["Extraction", "Pdf", "Scan", "Exports", "Projet"], noms


def test_l_ordre_est_celui_du_FLUX_comme_dans_la_GUI():
    """AC 1.1. **L'ordre est compare a la sequence**, pas seulement la presence.

    **Nom, docstring et assertion ont change ensemble le 2026-09-06**, sur
    retour terrain d'Egan (« remonter l'atelier [PDF] dans la liste AVANT scan
    (ordre logique) »). Ce test s'appelait
    `test_l_ordre_est_celui_de_la_CHAINE_DE_PRODUCTION` et asserait
    `Scan < Pdf < Exports` ; son motif reste **entierement valable** -- « une
    assertion d'appartenance serait verte sur l'ordre inverse » --, seule sa
    conclusion change. La propriete mesuree reste donc un ordre STRICT, jamais
    une appartenance.

    L'ecart delibere avec la GUI est ferme : l'ordre du menu est desormais
    celui de `gui/coquille.ORDRE_ATELIERS`, et c'est
    `test_frontiere_ordre_des_ateliers.py` qui confronte les deux.
    """
    noms = [e.nom for e in projet_lecture.entrees(manifeste())]
    assert noms[:4] == list(projet_lecture.ATELIERS)
    assert noms.index("Pdf") < noms.index("Scan") < noms.index("Exports")


def test_un_projet_vide_conditionne_Pdf_et_Exports_seulement():
    """AC 2.2, et l'ecart nomme avec `EXPERIENCE.md` sur Scan."""
    par_nom = {e.nom: e for e in projet_lecture.entrees(manifeste())}
    assert par_nom["Pdf"].condition is not None
    assert par_nom["Exports"].condition is not None
    assert par_nom["Extraction"].disponible
    assert par_nom["Scan"].disponible
    assert par_nom["Projet"].disponible


def test_un_lot_non_reconstruit_ouvre_Pdf_mais_PAS_Exports(tmp_path):
    """La distinction qui compte : `Pdf` liste les lots, `Exports` liste les
    lots **encodables**. Une condition unique sur `len(lots)` ouvrirait
    Exports sur un projet ou aucun lot ne l'est."""
    racine, document = projet(tmp_path, [
        lot("a", etat="extraction", dossier="output-frames/a"),
        lot("b", etat="pdf", dossier="output-frames/b"),
    ])
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert par_nom["Pdf"].disponible
    assert not par_nom["Exports"].disponible


def test_un_lot_SCAN_avec_ses_frames_OUVRE_Exports(tmp_path):
    """Story 11.8, AC 3.3 -- l'erreur **trop stricte**, et elle etait livree.

    Ce lot est encodable : `mmu encode` passe dessus. La table
    `ETATS_RECONSTRUITS` ne comptait pourtant que `reconstruction` et `encode`,
    si bien que l'entree se fermait sur « aucun lot reconstruit » pendant que
    la ligne de commande, elle, encodait. Ce n'est pas un cas de banc :
    `projects/projet_demo` porte **un** lot, et il est a l'etat `scan`.

    La cible est en **deuxieme** position sur trois : ni premiere -- un `find`
    qui rendrait `lots[0]` resterait vert --, ni derniere -- un arret de boucle
    sur le premier refus aussi.
    """
    racine, document = projet(tmp_path, [
        lot("a", etat="extraction"),
        lot("b", etat="scan", dossier="output-frames/b"),
        lot("c", etat="pdf", dossier="output-frames/c"),
    ])
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert par_nom["Exports"].disponible


def test_un_lot_RECONSTRUCTION_sans_frames_ne_l_ouvre_PAS(tmp_path):
    """Story 11.8, AC 3.2 -- l'erreur **trop laxiste**, symetrique de la
    precedente.

    Un lot recree depuis des payloads porte `io/reconstruction`.`
    DEFAULT_LOT_STATE`, c'est-a-dire `reconstruction`, **sans**
    `output_frames_dir`. La TUI ouvrait l'entree, et le coeur refusait par
    `ENCODE_OUTPUT_DIR_NOT_DECLARED` : l'operateur traversait l'atelier pour
    tomber sur un refus que le menu pouvait annoncer.
    """
    racine, document = projet(tmp_path, [
        lot("a", etat="extraction"),
        lot("b", etat="reconstruction"),
        lot("c", etat="encode"),
    ])
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert not par_nom["Exports"].disponible


def test_un_dossier_DECLARE_mais_absent_du_disque_ne_l_ouvre_PAS(tmp_path):
    """Le troisieme volet du critere du coeur. Declarer n'est pas porter : le
    lot annonce ses frames, le dossier n'existe pas."""
    document = manifeste([lot("b", etat="reconstruction",
                              dossier="output-frames/b")])
    racine = tmp_path / "projet"
    racine.mkdir()
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert not par_nom["Exports"].disponible


def test_la_condition_d_Exports_est_LE_VERDICT_DU_COEUR(tmp_path):
    """`EPIC11-ARB-30`, mesure par **confrontation** et non par relecture.

    Sur la meme fabrique, la disponibilite de l'entree et l'enumeration du
    coeur disent la meme chose. C'est ce qui remplace l'ancienne mesure « les
    etats sont lus du vocabulaire du coeur » : la TUI ne lit plus un
    vocabulaire, elle lit un **verdict**. Un critere recopie qui divergerait
    d'un seul lot fait rougir ici.
    """
    racine, document = projet(tmp_path, [
        lot("a", etat="reconstruction"),
        lot("b", etat="scan", dossier="output-frames/b"),
        lot("c", etat="pdf", dossier="output-frames/c"),
    ])
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    admis = encode.list_encodable_lots(document, racine)
    assert [entree.lot["lot_id"] for entree in admis] == ["b"]
    assert par_nom["Exports"].disponible is bool(admis)


def test_un_etat_INVENTE_n_ouvre_pas_Exports(tmp_path):
    """Volet symetrique conserve de l'ancienne mesure : un etat hors
    `LOT_STATES` n'ouvre rien, meme avec ses frames sur le disque."""
    assert "etat_invente" not in LOT_STATES
    racine, document = projet(tmp_path, [
        lot("a", etat="etat_invente", dossier="output-frames/a")])
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert not par_nom["Exports"].disponible


def test_SANS_dossier_de_projet_Exports_reste_ferme(tmp_path):
    """Le critere du coeur porte sur la matiere : juger sans racine, ce serait
    juger sur l'etat -- c'est-a-dire reecrire la table qu'on retire.

    Le meme document, avec sa racine, ouvre l'entree : c'est le volet
    symetrique, sans lequel une condition toujours fermee serait verte.
    """
    racine, document = projet(tmp_path, [
        lot("a", etat="extraction"),
        lot("b", etat="scan", dossier="output-frames/b"),
        lot("c", etat="pdf", dossier="output-frames/c"),
    ])
    sans = {e.nom: e for e in projet_lecture.entrees(document)}
    avec = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert not sans["Exports"].disponible
    assert avec["Exports"].disponible


def test_une_condition_dit_OU_OBTENIR_ce_qui_manque():
    """AC 2.3 : « elle nomme ce qui manque **et ou l'obtenir** ». Une phrase
    qui dirait seulement « indisponible » laisserait l'operateur sans geste."""
    par_nom = {e.nom: e for e in projet_lecture.entrees(manifeste())}
    for nom in ("Pdf", "Exports"):
        condition = par_nom[nom].condition
        assert any(mot in condition for mot in ("Extraction", "Scan")), condition


def test_chaque_entree_porte_une_PHRASE():
    """AC 1.3 : jamais son seul nom."""
    for entree in projet_lecture.entrees(manifeste()):
        assert entree.phrase, entree.nom
        assert entree.phrase != entree.nom


# ---------------------------------------------------------------------------
# AC 3 -- la derniere extraction confirmee (`EPIC11-ARB-44`)
# ---------------------------------------------------------------------------

def test_la_cible_n_est_NI_LA_PREMIERE_NI_LA_DERNIERE_du_tableau():
    """AC 3.5, et c'est litteralement le mutant `M25` de la story 5.7.

    `lots[]` porte l'ordre de **premiere creation** : `lots[-1]` serait juste
    tant que la derniere entree se trouve etre la plus recente, et `lots[0]`
    tant que c'est la premiere. La cible est donc **au milieu**, avec des dates
    distinguables des deux cotes.
    """
    document = manifeste([
        lot("premier", etat="pdf", confirme="2026-08-01T10:00:00Z"),
        lot("le_bon", etat="scan", confirme="2026-08-25T16:46:05Z"),
        lot("dernier", etat="extraction", confirme="2026-08-10T09:00:00Z"),
    ])
    derniere = projet_lecture.derniere_extraction(document)
    assert derniere.lot == "le_bon"
    assert derniere.quand == "2026-08-25T16:46:05Z"
    assert derniere.etape == "scan"


def test_un_lot_SANS_confirmation_est_saute_sans_faire_tomber():
    """AC 3.6 : le champ n'est pas dans le `required` du schema, et les lots
    venus du scan n'en portent pas."""
    document = manifeste([
        lot("sans_confirmation"),
        lot("avec", confirme="2026-08-25T16:46:05Z"),
        lot("autre_sans"),
    ])
    assert projet_lecture.derniere_extraction(document).lot == "avec"


def test_aucune_extraction_confirmee_rend_un_resultat_VIDE_et_non_une_erreur():
    """AC 3.4 : l'ecran dira « aucune extraction confirmee dans ce projet »."""
    for document in (manifeste(), manifeste([lot("a")]), None):
        derniere = projet_lecture.derniere_extraction(document)
        assert not derniere.existe
        assert derniere.lot is None


def test_un_confirmed_at_vide_ou_non_texte_est_saute():
    """Volet defensif : le schema garantit la forme, un document edite a la
    main ne la garantit pas."""
    document = manifeste([
        {"lot_id": "vide", "confirmation": {"confirmed_at": ""}},
        {"lot_id": "nombre", "confirmation": {"confirmed_at": 42}},
        lot("bon", confirme="2026-08-25T16:46:05Z"),
    ])
    assert projet_lecture.derniere_extraction(document).lot == "bon"


def test_la_confirmation_qui_n_est_pas_un_objet_ne_leve_pas():
    document = manifeste([{"lot_id": "x", "confirmation": "pas un objet"}])
    assert not projet_lecture.derniere_extraction(document).existe


def test_l_etape_est_lue_du_vocabulaire_du_coeur_et_non_inventee():
    """AC 3.3 : `LOT_STATES` est une **etape de chaine**, pas un verdict."""
    document = manifeste([lot("a", etat="pdf", confirme="2026-08-25T16:46:05Z")])
    assert projet_lecture.derniere_extraction(document).etape in LOT_STATES


@pytest.mark.parametrize("horodatage, attendu", [
    ("2026-08-25T16:46:05Z", "25/08 16:46"),
    ("2026-08-06T08:43:29Z", "06/08 08:43"),
])
def test_la_date_est_rendue_a_la_forme_des_maquettes(horodatage, attendu):
    assert projet_lecture.date_lisible(horodatage) == attendu


def test_un_horodatage_illisible_est_rendu_TEL_QUEL():
    """Il vient du coeur : le reecrire serait le paraphraser, et le faire
    disparaitre serait pire encore."""
    assert projet_lecture.date_lisible("pas une date") == "pas une date"


# ---------------------------------------------------------------------------
# Frontiere de lot
# ---------------------------------------------------------------------------

def test_le_modele_pur_n_importe_ni_textual_ni_la_coque():
    import ast

    arbre = ast.parse(Path(projet_lecture.__file__).read_text(encoding="utf-8"))
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            racines.add((noeud.module or "").split(".")[0])
    assert "textual" not in racines, racines
    assert "coque" not in racines, racines
