# -*- coding: utf-8 -*-
"""Story 11.7, lot C -- `E5-0`, le menu de l'atelier Pdf et sa porte (AC 3).

**Ce banc et lui seul mesure le lot C.** La regle de decoupage de la fiche est
stricte et elle a ete payee trois fois sur ce depot : « aucun lot ne partage un
fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier -- le commit `82e64de`
du 2026-08-30 a embarque ~200 lignes du lot voisin sous un message qui parlait
d'autre chose, alors que les deux agents appliquaient la regle a la lettre.

**Regle des fabriques** (`CLAUDE.md`), appliquee ici a ses quatre points, et il
y a **deux** boucles a couvrir, pas une :

1. **trois lots au moins, la cible AU MILIEU** -- `dernier_tirage` et `compter`
   parcourent tous deux `lots[]`. Une cible en tete laisse vivre un `lots[0]`,
   une cible en queue laisse vivre un `continue` -> `break` ;
2. **trois tirages dans le lot cible, la cible AU MILIEU** -- l'inventaire est
   la seconde boucle, et elle est **triee par chemin** a l'ecriture. Le tirage
   attendu est donc le `_v2`, ni le premier de la liste triee, ni le dernier ;
3. **des valeurs distinguables** : trois cardinaux de tirages differents (1, 3,
   2), trois gabarits differents, trois paginations differentes (4, 7, 1). Un
   remplissage uniforme rendrait toute permutation invisible ;
4. **la position se verifie sur la liste que le CODE parcourt** -- ici
   `lots[]` du manifeste et `sheets_pdfs[]` du lot, pas sur l'ordre dans lequel
   la fabrique ecrit ses fichiers.

**Rien n'est tape a la main de ce que le produit sait construire** : le nom du
tirage attendu sort de `io.naming.build_sheets_pdf_filename`, sa pagination de
`pdf_composition.page_count_du_lot`, son cardinal d'emplacements du registre des
gabarits. Une valeur recopiee coinciderait le jour ou elle est ecrite et
divergerait sans qu'aucune etape n'echoue.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import page_templates, pdf_composition
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import naming, pdf_manifest
from mixed_media_utility.tui import atelier_pdf, jetons, projet_lecture
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle,
    chaine_du_produit,
)
from mixed_media_utility.tui.atelier_scan import EntreeDeMenu
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)

from outils_frontiere import chaines_de_code, identifiants

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le plancher de `EPIC11-ARB-21`, et la zone ecrivable qui s'en deduit.
PLANCHER = (80, 24)
UTILE = jetons.largeur_utile(PLANCHER[0])

#: Le nom du projet de la fabrique. C'est celui des maquettes -- le pied de
#: `E5-0` porte `projet_demo_plan-04_25_8f-pay_v3.pdf` --, ce qui permet de
#: confronter le rendu au dessin sans inventer d'identifiant.
PROJET = "projet_demo"

#: Les trois lots de la fabrique, **dans l'ordre du manifeste**. La cible est le
#: second des trois : ni le premier, ni le dernier.
LOT_PREMIER = "rush_a_5"
LOT_CIBLE = "plan-04_25"
LOT_DERNIER = "rush_c_2"

#: Le rang de la cible dans la liste que le code parcourt. En constante parce
#: que trois tests l'asseyent, et parce qu'un banc qui le recopierait a trois
#: endroits laisserait passer un decalage a la premiere reecriture.
RANG_DE_LA_CIBLE = 1

#: Le rang du tirage attendu, **au milieu** des trois tirages du lot cible une
#: fois l'inventaire trie par chemin (`...8f-pay.pdf`, `..._v2.pdf`,
#: `..._v3.pdf`). Il vaut 2, alors que l'inventaire en compte 3 et que la ligne
#: d'eau du lot vaut 3 : un pied qui rendrait `len(inventaire)`, le rang maximal
#: ou la ligne d'eau afficherait `tirage 3` et se demasque.
RANG_DU_TIRAGE_ATTENDU = 2

#: Les cardinaux de tirages des trois lots. **Trois valeurs differentes**, et
#: leur somme (6) ne coincide ni avec celle du premier lot (1) ni avec celle du
#: dernier (2) : le bandeau ne peut pas etre juste par accident.
TIRAGES_PAR_LOT = {LOT_PREMIER: 1, LOT_CIBLE: 3, LOT_DERNIER: 2}

#: Les dates de derniere ecriture posees sur les fichiers, en secondes depuis
#: l'epoque. La plus recente est celle du tirage attendu ; les autres sont
#: **echelonnees** pour qu'aucune egalite ne rende le tri ambigu.
QUAND_ANCIEN = 1_756_000_000.0
QUAND_ATTENDU = 1_756_900_000.0

#: Ce que le pied doit annoncer comme mise en page. Le gabarit du lot cible est
#: celui de la maquette `E5-0` (`tpl-a4-paysage-8f-v2`), et les deux autres lots
#: en portent d'autres : un pied qui lirait le gabarit du mauvais lot se voit.
GABARITS = {LOT_PREMIER: "tpl-a4-portrait-2f-v2",
            LOT_CIBLE: "tpl-a4-paysage-8f-v2",
            LOT_DERNIER: "tpl-a4-portrait-4f-v2"}


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _rush(rush_id: str) -> dict:
    return {"rush_id": rush_id, "source_name": f"{rush_id}.mov",
            "fps_source": 25.0, "fps_source_exact": "25/1",
            "resolution_source": {"width": 1920, "height": 1080}}


def _lot(lot_id: str, rush_id: str, *, fps_target: float, exact: str,
         frames_source: int, etat: str,
         output_frames_dir: str | None = None) -> dict:
    """Un lot **paginable** : la selection se recalcule depuis le seul manifeste.

    Les trois champs qui le permettent -- `fps_source_exact` du rush,
    `fps_target_exact` et `source_frame_count` du lot -- sont ceux
    qu'`extraction_manifest.recompute_lot_selection` exige. Sans eux le pied
    n'annoncerait aucun cardinal de pages, ce qui est un autre regime, mesure
    a part.
    """
    entree = {"lot_id": lot_id, "rush_id": rush_id, "state": etat,
              "fps_target": fps_target, "fps_target_exact": exact,
              "timecode_base_fps": "25/1",
              "template_id": GABARITS[lot_id],
              "patch_preset_id": "patches-17-v4",
              "gamut_map_id": "gamut-map-none-1",
              "expected_frame_count": frames_source,
              "frames_dir": f"frames/{lot_id}",
              "source_frame_count": frames_source,
              "source_frame_count_is_exact": True,
              "rounding_policy": "floor"}
    if output_frames_dir is not None:
        entree["output_frames_dir"] = output_frames_dir
    return entree


def _manifeste() -> dict:
    """Trois lots distinguables, la cible **au milieu**.

    Le premier lot est **encodable** : c'est ce qui rend l'entree *Exports* du
    menu des ateliers **disponible**, donc mesurable sur la branche par defaut
    d'`entrer()` (AC 3.1). Sans lui, `Exports` serait conditionnee et resterait
    sur le menu au lieu d'atteindre l'ecran « pas encore » -- la branche que ce
    banc doit voir en ensemble exact de un.

    **L'etat ne suffit plus depuis la story 11.8** : le juge est le coeur
    (`encode.list_encodable_lots`), et son critere porte aussi sur un
    `output_frames_dir` declare et present. Le lot le declare, et `_projet` le
    cree.
    """
    return {
        "schema_version": "2.1",
        "project_id": PROJET,
        "created": "2026-08-26T00:00:00Z",
        "rushes": [_rush("rush_a"), _rush("plan-04"), _rush("rush_c")],
        "lots": [
            _lot(LOT_PREMIER, "rush_a", fps_target=5.0, exact="5/1",
                 frames_source=40, etat="encode",
                 output_frames_dir=f"output-frames/{LOT_PREMIER}"),
            _lot(LOT_CIBLE, "plan-04", fps_target=12.5, exact="25/2",
                 frames_source=100, etat=pdf_manifest.PDF_LOT_STATE),
            _lot(LOT_DERNIER, "rush_c", fps_target=2.0, exact="2/1",
                 frames_source=50, etat=pdf_manifest.PDF_LOT_STATE),
        ],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "bt709"},
        "video": {}, "reconstruction": {},
    }


def _nom_de_tirage(lot_id: str, rush_id: str, rang: int | None) -> str:
    """Le nom du tirage, **construit par le coeur** et jamais tape (AC 3.7).

    `EPIC11-ARB-171` : le nom porte la mise en page, derivee du `template_id`.
    Ecrire `projet_demo_plan-04_25_8f-pay_v3.pdf` en litteral ici ferait un banc
    qui reste vert le jour ou la convention change -- c'est-a-dire un banc qui
    ne mesure plus le produit mais sa copie.
    """
    return naming.build_sheets_pdf_filename(
        PROJET, rush_id, lot_id, rang, template_id=GABARITS[lot_id])


def _rush_du_lot(manifeste: dict, lot_id: str) -> str:
    for lot in manifeste["lots"]:
        if lot["lot_id"] == lot_id:
            return lot["rush_id"]
    raise AssertionError(lot_id)


def _rangs_du_lot(lot_id: str) -> list[int | None]:
    """Les rangs des tirages d'un lot : `None` (origine), puis 2, puis 3...

    Le rang d'origine n'ecrit **aucun** fragment de nom et ne s'ecrit pas au
    manifeste : c'est son absence qui le dit.
    """
    cardinal = TIRAGES_PAR_LOT[lot_id]
    return [None] + list(range(2, cardinal + 1))


def _poser_les_tirages(dossier: Path, manifeste: dict,
                       *, sur_le_disque: bool = True) -> dict:
    """Declarer les tirages au manifeste, et poser leurs fichiers.

    `sur_le_disque=False` est le **volet symetrique** de la date : l'inventaire
    est le meme, aucun fichier n'existe, et le pied doit alors nommer le tirage
    **sans** son segment de date plutot que d'en inventer une.
    """
    (dossier / "planches").mkdir(parents=True, exist_ok=True)
    for lot in manifeste["lots"]:
        inventaire = []
        for rang in _rangs_du_lot(lot["lot_id"]):
            nom = _nom_de_tirage(lot["lot_id"], lot["rush_id"], rang)
            chemin = f"planches/{nom}"
            entree = {pdf_manifest.SHEETS_INVENTORY_KEY: chemin}
            if rang is not None:
                entree["version_rank"] = rang
            inventaire.append(entree)
            if not sur_le_disque:
                continue
            (dossier / chemin).write_bytes(b"%PDF-1.4\n")
            recent = (lot["lot_id"] == LOT_CIBLE
                      and rang == RANG_DU_TIRAGE_ATTENDU)
            quand = QUAND_ATTENDU if recent else QUAND_ANCIEN
            os.utime(dossier / chemin, (quand, quand))
        # L'inventaire est TRIE PAR CHEMIN a l'ecriture, comme le coeur le fait
        # (`_merge_sheets_inventory`) : la fabrique doit rendre la liste que le
        # code parcourt, pas l'ordre dans lequel elle l'a construite.
        lot[pdf_manifest.SHEETS_INVENTORY_FIELD] = sorted(
            inventaire, key=lambda e: e[pdf_manifest.SHEETS_INVENTORY_KEY])
        lot[pdf_manifest.SHEETS_WATERMARK_FIELD] = TIRAGES_PAR_LOT[lot["lot_id"]]
    return manifeste


def _projet(tmp_path, *, avec_tirages: bool = True,
            sur_le_disque: bool = True) -> Path:
    """Un projet reel, cree par le coeur, dont on pose le manifeste."""
    chemin = creer_projet(tmp_path, PROJET).chemin
    manifeste = _manifeste()
    if avec_tirages:
        _poser_les_tirages(chemin, manifeste, sur_le_disque=sur_le_disque)
    (chemin / "project.json").write_text(json.dumps(manifeste),
                                         encoding="utf-8")
    for lot in manifeste["lots"]:
        declare = lot.get("output_frames_dir")
        if declare:
            (chemin / declare).mkdir(parents=True, exist_ok=True)
    return chemin


def _app(ecran, **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=PROJET), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _rendu(ecran, ascii_seul: bool) -> list[str]:
    return [jetons.ajuster(ligne, UTILE, ascii_seul)
            for ligne in ecran.lignes()]


# ---------------------------------------------------------------------------
# AC 3.1 -- la porte : `Pdf` cesse de mener a `EcranPasEncore`
# ---------------------------------------------------------------------------

def test_l_entree_Pdf_du_menu_des_ateliers_monte_bien_E5_0(tmp_path, banc):
    """AC 3.1. Le quatrieme atelier avait une porte qui ne menait nulle part.

    Mesure sur la chaine du **produit**, jamais sur un montage de banc : c'est
    la difference entre « l'ecran existe » et « le produit y mene », et le depot
    a paye sept fois la seconde (`test_rappels_cables.py` les nomme une a une).
    """
    projet = _projet(tmp_path)
    chaine = chaine_du_produit()

    async def scenario(pilote):
        chaine.ouvrir(projet)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in chaine.menu.entrees}
        chaine.menu.entrer(entrees[projet_lecture.PDF])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(chaine.app, scenario)
    assert isinstance(ecran, atelier_pdf.EcranPdfMenu), type(ecran).__name__
    assert not isinstance(ecran, EcranPasEncore)


def test_la_branche_par_defaut_d_entrer_est_un_ensemble_EXACT_et_il_est_VIDE(
        tmp_path, banc):
    """AC 3.1 : plus AUCUNE entree du menu ne tombe dans la branche par defaut.

    **Ensemble exact, jamais une assertion positive prise atelier par
    atelier** : une branche mal placee qui renverrait `Pdf` a l'ecran « pas
    encore » serait invisible a « `Exports` ne mene plus a `EcranPasEncore` »,
    qui resterait vrai. Ce qui se mesure est « l'ensemble des entrees qui y
    menent est **exactement** vide ».

    Il valait `{Exports}` jusqu'au 2026-09-03 ; le lot B5 de la story 11.8 a
    cable le dernier atelier, et c'est **ce volet-ci** qui le dit -- le
    ramener a `{Exports}` demain ferait rougir, ce qu'une assertion positive
    ne ferait pas.
    """
    projet = _projet(tmp_path)

    def ou_mene(nom: str) -> str:
        chaine = chaine_du_produit()

        async def scenario(pilote):
            chaine.ouvrir(projet)
            await pilote.pause()
            entrees = {entree.nom: entree for entree in chaine.menu.entrees}
            chaine.menu.entrer(entrees[nom])
            await pilote.pause()
            return type(pilote.app.screen).__name__

        return banc(chaine.app, scenario)

    par_defaut = {nom for nom in projet_lecture.ATELIERS + (projet_lecture.PROJET,)
                  if ou_mene(nom) == EcranPasEncore.__name__}
    assert par_defaut == set(), par_defaut


def test_l_atelier_Pdf_est_INJECTE_par_la_chaine_du_PRODUIT(tmp_path, banc):
    """AC 3.1, l'autre moitie : le produit n'a pas de version degradee.

    `ChaineReelle` accepte l'atelier en rappel -- c'est ce qui la rend mesurable
    sans disque --, mais `chaine_du_produit` l'injecte **toujours**. Une chaine
    construite sans lui NOMME ce qui manque plutot que de rester muette, et ce
    sont ces deux branches qui doivent etre distinguables.
    """
    projet = _projet(tmp_path)
    assert chaine_du_produit()._ouvrir_l_atelier_pdf is \
        atelier_pdf.ouvrir_l_atelier_pdf

    sans = ChaineReelle()

    async def scenario(pilote):
        sans.ouvrir(projet)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in sans.menu.entrees}
        sans.menu.entrer(entrees[projet_lecture.PDF])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(sans.app, scenario)
    assert isinstance(ecran, EcranPasEncore)
    assert projet_lecture.PDF in ecran.ce_qui_manque


# ---------------------------------------------------------------------------
# AC 3.2 -- deux entrees, et l'invariant de l'entree non construite
# ---------------------------------------------------------------------------

def test_le_menu_porte_EXACTEMENT_deux_entrees(tmp_path):
    """AC 3.2, en ensemble exact des couples `(cle, nom)`.

    `EPIC11-ARB-28`, verbatim : « **Tout atelier qui a plus d'une entree
    commence par un menu d'atelier** ». Une entree de plus ou de moins change
    ce que l'arbitrage dit de cet atelier ; un ensemble exact le voit, une
    appartenance non.
    """
    assert {(entree.cle, entree.nom) for entree in atelier_pdf.ENTREES_DU_MENU} == {
        (atelier_pdf.CLE_DE_LA_COMPOSITION, "Composer des planches"),
        (atelier_pdf.CLE_DE_LA_MIRE, "Planche de calibration"),
    }
    assert len(atelier_pdf.ENTREES_DU_MENU) == 2


def test_le_curseur_part_sur_le_PARCOURS_PRINCIPAL(tmp_path, banc):
    """AC 3.2 : l'ordre est celui de la chaine de travail, pas l'alphabet."""
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    assert ecran.entrees[ecran.curseur].cle == atelier_pdf.CLE_DE_LA_COMPOSITION


def test_une_entree_NON_construite_doit_dire_QUAND_elle_arrive():
    """AC 3.2, l'invariant importe avec `EntreeDeMenu` -- **les deux branches**.

    « Sans la date, on ne distingue pas "pas encore fait" de "abandonne" ». Le
    volet symetrique est la seconde assertion : une classe qui refuserait TOUTE
    entree rendrait le premier `raises` vert sans rien mesurer.
    """
    with pytest.raises(ValueError):
        EntreeDeMenu("x", "Nom", "Phrase", construite=False)
    assert EntreeDeMenu("x", "Nom", "Phrase", construite=False,
                        quand="demain").quand == "demain"


@pytest.mark.parametrize("rang", [0, 1])
def test_les_DEUX_entrees_du_menu_MENENT_QUELQUE_PART(tmp_path, banc, rang):
    """AC 3.2 : « une touche qui ne fait rien et ne dit rien est
    indistinguable d'un clavier casse ».

    Les deux entrees, une par ligne : une mesure sur la seule premiere laisserait
    la seconde muette, et c'est exactement la forme du finding `K3`.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        ecran.curseur = rang
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    monte = _monte(app, scenario, banc)
    assert isinstance(monte, EcranPasEncore)
    assert monte.ce_qui_manque == atelier_pdf.ENTREES_DU_MENU[rang].nom
    assert monte.quand == atelier_pdf.QUAND_L_ATELIER_PDF


def test_l_entree_CABLEE_ne_passe_plus_par_l_ecran_pas_encore(tmp_path, banc):
    """Volet symetrique du test precedent : le rappel injecte est **appele**.

    Sans lui, une implementation qui enverrait les deux entrees a
    `EcranPasEncore` quoi qu'il arrive serait verte.
    """
    vues = []
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path), entrer=vues.append)
    app = _app(ecran)

    async def scenario(pilote):
        ecran.curseur = 1
        ecran.traiter("enter")
        await pilote.pause()
        return type(pilote.app.screen).__name__

    vu = _monte(app, scenario, banc)
    assert vu == atelier_pdf.EcranPdfMenu.__name__
    assert [entree.cle for entree in vues] == [atelier_pdf.CLE_DE_LA_MIRE]


# ---------------------------------------------------------------------------
# AC 3.3 -- aucun terme de nos documents de decision a l'ecran
# ---------------------------------------------------------------------------

#: Les termes qu'`EPIC11-ARB-28` interdit a l'ecran, verbatim de l'arbitrage.
TERMES_INTERDITS = ("parcours a part", "parcours à part", "palier",
                    "feuille cli", "point de jugement")


def _maquettes_e5() -> list[Path]:
    racine = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "maquettes")
    return sorted(racine.glob("E5-*.txt"))


def _ecran_de_la_maquette(chemin: Path) -> list[str]:
    """Les lignes du CADRE, notes exclues.

    L'arbitrage porte sur ce qui **s'affiche**, et les notes qui suivent le
    cadre sont la conversation entre Egan et la fiche, pas l'ecran. Les
    confondre ferait rougir une maquette parce qu'une note explique pourquoi un
    mot a ete retire -- c'est le meme piege que le docstring de `jetons.py`,
    qui explique ce qu'il n'importe pas.
    """
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    fin = next(rang for rang, ligne in enumerate(lignes)
               if ligne.startswith("└"))
    return lignes[:fin + 1]


def _modules_de_l_atelier() -> list[Path]:
    """Les NEUF modules de l'atelier, et non le seul module du menu.

    L'AC 11.3 et `EPIC11-ARB-28` portent sur `tui/atelier_pdf*.py`. Cette
    mesure n'a longtemps balaye qu'`atelier_pdf.py` -- **un module sur neuf**,
    trouve par la couche 3 de la revue du 2026-09-02. La propriete etait vraie
    partout ; elle n'etait mesuree nulle part ailleurs, ce qui est exactement
    la difference que ce depot passe son temps a payer.
    """
    dossier = Path(atelier_pdf.__file__).resolve().parent
    return sorted(dossier.glob("atelier_pdf*.py"))


def _entrees_de_tout(chemin: Path) -> set[str]:
    """Les chaines qui ne sont que des noms exportes par `__all__`.

    Un `__all__` porte des **identifiants**, pas du texte affiche :
    `"PALIER_DE_LA_MIRE"` y est le nom d'une constante, jamais un mot qui
    atteint l'ecran. Les compter ferait rougir la frontiere sur une chaine que
    personne ne lit -- un faux positif qui, laisse en place, ferait desactiver
    la mesure entiere.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        if not any(isinstance(c, ast.Name) and c.id == "__all__"
                   for c in noeud.targets):
            continue
        for element in ast.walk(noeud.value):
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                noms.add(element.value)
    return noms


def test_aucun_terme_de_nos_documents_de_decision_ne_S_AFFICHE(tmp_path):
    """AC 3.3 et 11.3, `EPIC11-ARB-28` -- **zero** occurrence, code et maquettes.

    La mesure porte sur les chaines du CODE (docstrings exclus, par l'arbre
    syntaxique) : un module qui explique dans sa prose pourquoi il n'ecrit pas
    « palier » ne doit pas se faire prendre par sa propre explication. Les
    entrees d'`__all__` sont exclues pour le meme motif : ce sont des noms,
    pas du texte.
    """
    for module in _modules_de_l_atelier():
        exportes = _entrees_de_tout(module)
        for texte in chaines_de_code(module):
            if texte in exportes:
                continue
            for terme in TERMES_INTERDITS:
                assert terme not in texte.lower(), (module.name, terme, texte)
    for maquette in _maquettes_e5():
        ecran = "\n".join(_ecran_de_la_maquette(maquette)).lower()
        for terme in TERMES_INTERDITS:
            assert terme not in ecran, (maquette.name, terme)


def test_la_frontiere_des_TERMES_INTERDITS_balaie_les_NEUF_modules():
    """L'ensemble balaye est **exactement** celui que l'AC nomme.

    Une appartenance (« `atelier_pdf.py` est dedans ») laisserait passer un
    dixieme module ajoute demain sans mesure. C'est le defaut que la couche 3 a
    trouve, a l'envers : la frontiere balayait un seul module et personne ne
    pouvait le voir depuis le test.
    """
    assert {m.name for m in _modules_de_l_atelier()} == {
        "atelier_pdf.py",
        "atelier_pdf_calibration.py",
        "atelier_pdf_confirmation.py",
        "atelier_pdf_execution.py",
        "atelier_pdf_lots.py",
        "atelier_pdf_parcours.py",
        "atelier_pdf_reglages.py",
        "atelier_pdf_resultat.py",
        "atelier_pdf_versions.py",
    }


def test_l_exclusion_des_entrees_de_TOUT_ne_masque_QUE_des_noms():
    """L'exception est nommee **et** unique, pas seulement permise.

    Exclure `__all__` est legitime -- on y ecrit des identifiants, pas du texte
    affiche --, mais une exclusion non bornee finit par avaler un vrai defaut :
    il suffirait qu'un jour une chaine affichee porte le meme texte qu'un nom
    exporte. On mesure donc l'ensemble EXACT des entrees d'`__all__` qui
    portent un terme interdit, et il vaut une seule chose.
    """
    masques: set[str] = set()
    for module in _modules_de_l_atelier():
        for nom in _entrees_de_tout(module):
            if any(terme in nom.lower() for terme in TERMES_INTERDITS):
                masques.add(nom)
    assert masques == {"PALIER_DE_LA_MIRE"}


def test_la_mesure_des_TERMES_INTERDITS_a_bien_un_objet(tmp_path):
    """Volet symetrique : la mesure ci-dessus n'est pas vide par accident.

    Les seize maquettes `E5-*` doivent exister et porter du texte, et la mesure
    doit savoir rougir -- sans quoi une frontiere negative posee sur un dossier
    vide serait verte sans rien mesurer.
    """
    maquettes = _maquettes_e5()
    assert len(maquettes) >= 16, [m.name for m in maquettes]
    for maquette in maquettes:
        assert _ecran_de_la_maquette(maquette), maquette.name
    faux = "\n".join(["┌", "│ le palier Projet", "└"]).lower()
    assert any(terme in faux for terme in TERMES_INTERDITS)


# ---------------------------------------------------------------------------
# AC 3.4 et 3.7 -- le pied : le dernier tirage produit
# ---------------------------------------------------------------------------

def test_la_fabrique_place_bien_la_cible_AU_MILIEU_des_deux_boucles(tmp_path):
    """La regle des fabriques, mesuree sur la fabrique elle-meme.

    Un banc dont la fabrique deriverait -- deux lots au lieu de trois, cible en
    tete -- resterait vert en ne mesurant plus rien. Les deux boucles sont
    nommees : `lots[]`, et l'inventaire du lot cible **trie par chemin**.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    lots = manifeste["lots"]
    assert len(lots) == 3
    assert lots[RANG_DE_LA_CIBLE]["lot_id"] == LOT_CIBLE
    assert 0 < RANG_DE_LA_CIBLE < len(lots) - 1

    inventaire = lots[RANG_DE_LA_CIBLE][pdf_manifest.SHEETS_INVENTORY_FIELD]
    assert len(inventaire) == 3
    rangs = [entree.get("version_rank") for entree in inventaire]
    assert rangs == [None, 2, 3]
    attendu = rangs.index(RANG_DU_TIRAGE_ATTENDU)
    assert 0 < attendu < len(inventaire) - 1, rangs


def test_le_pied_nomme_le_DERNIER_tirage_produit(tmp_path):
    """AC 3.4 et 3.7 : nom, date, pages, rang, gabarit.

    Le nom attendu est **construit par le coeur** ; le cardinal de pages est
    **recalcule** par le chemin de l'impression. Aucun des deux n'est un
    litteral, et c'est ce qui fait que ce banc mesure le produit et non sa
    copie.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    tirage = atelier_pdf.dernier_tirage(manifeste, dossier)

    attendu = _nom_de_tirage(LOT_CIBLE, _rush_du_lot(manifeste, LOT_CIBLE),
                             RANG_DU_TIRAGE_ATTENDU)
    emplacements = page_templates.get_template(GABARITS[LOT_CIBLE]).frames_per_page
    pages = pdf_composition.page_count_du_lot(manifeste, LOT_CIBLE,
                                              frames_per_page=emplacements)

    assert tirage.nom == attendu
    assert tirage.lot_id == LOT_CIBLE
    assert tirage.rang == RANG_DU_TIRAGE_ATTENDU
    assert tirage.pages == pages
    assert tirage.gabarit == GABARITS[LOT_CIBLE]
    assert tirage.quand is not None


def test_le_pied_ne_prend_ni_le_PREMIER_ni_le_DERNIER_lot(tmp_path):
    """AC 3.4, le volet qui nomme les deux mutants.

    Les noms des tirages des deux lots voisins sont construits ici et l'on
    mesure qu'aucun ne sort : un `lots[0]` et un `lots[-1]` rendraient chacun
    l'un d'eux, et ils sont indiscernables d'un balayage correct sur une
    fabrique a deux lots.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    nom = atelier_pdf.dernier_tirage(manifeste, dossier).nom

    for lot_id in (LOT_PREMIER, LOT_DERNIER):
        rush = _rush_du_lot(manifeste, lot_id)
        for rang in _rangs_du_lot(lot_id):
            assert nom != _nom_de_tirage(lot_id, rush, rang), lot_id


def test_le_RANG_du_pied_est_LU_et_jamais_deduit_du_cardinal(tmp_path):
    """AC 3.4 et `EPIC11-ARB-92` : « il ne faut pas rendre le rang ».

    Le lot cible porte **trois** tirages et une ligne d'eau a 3, tandis que le
    tirage attendu est au rang **2**. Un pied qui rendrait le cardinal de
    l'inventaire, le rang maximal ou la ligne d'eau afficherait `tirage 3`.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    lot = manifeste["lots"][RANG_DE_LA_CIBLE]

    assert lot[pdf_manifest.SHEETS_WATERMARK_FIELD] != RANG_DU_TIRAGE_ATTENDU
    assert len(lot[pdf_manifest.SHEETS_INVENTORY_FIELD]) != RANG_DU_TIRAGE_ATTENDU
    assert atelier_pdf.dernier_tirage(manifeste, dossier).rang == \
        RANG_DU_TIRAGE_ATTENDU


def test_un_tirage_D_ORIGINE_est_dit_par_un_MOT_et_non_par_un_NUMERO(tmp_path):
    """AC 3.4 et `EPIC11-ARB-92` : la TUI **affiche** le rang, elle ne le rend pas.

    L'inventaire n'ecrit le rang qu'a partir du second tirage (`minimum: 2` au
    schema) ; un tirage d'origine n'en porte donc aucun, et le pied n'en invente
    pas. Ecrire `tirage 1` supposerait de connaitre le numero du premier rang,
    c'est-a-dire de recopier une valeur qui vit au coeur -- et le paquet `tui/`
    n'a meme pas le droit d'en nommer la constante (frontiere de la 11.6).

    **Les deux volets** : ici l'origine, et le pied nominal ci-dessus pour un
    rang declare. Un rendu qui dirait toujours `tirage d'origine` serait vert
    ici et rouge la-bas, et reciproquement.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    # Ne garder, dans le lot cible, QUE le tirage d'origine -- celui que la
    # fabrique ecrit sans `version_rank`.
    lot = manifeste["lots"][RANG_DE_LA_CIBLE]
    lot[pdf_manifest.SHEETS_INVENTORY_FIELD] = [
        entree for entree in lot[pdf_manifest.SHEETS_INVENTORY_FIELD]
        if "version_rank" not in entree]
    for autre in manifeste["lots"]:
        if autre is not lot:
            autre[pdf_manifest.SHEETS_INVENTORY_FIELD] = []

    tirage = atelier_pdf.dernier_tirage(manifeste, dossier)
    ligne = atelier_pdf.lignes_du_pied(tirage)[1]

    assert tirage.rang is None
    assert tirage.nom == _nom_de_tirage(LOT_CIBLE,
                                        _rush_du_lot(manifeste, LOT_CIBLE), None)
    assert ligne.endswith(atelier_pdf.MENTION_DU_TIRAGE_D_ORIGINE)
    # Frontiere negative : aucun numero de rang n'a ete invente. Le volet
    # symetrique est que la ligne porte bien, elle, les chiffres qu'elle SAIT --
    # sans quoi une ligne vide passerait ce test.
    assert atelier_pdf.MENTION_DU_RANG.format(rang=1) not in ligne
    assert str(tirage.pages) in ligne


def test_un_projet_SANS_AUCUN_tirage_le_DIT(tmp_path):
    """AC 3.4 : « jamais une ligne vide ni un `0` »."""
    dossier = _projet(tmp_path, avec_tirages=False)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    tirage = atelier_pdf.dernier_tirage(manifeste, dossier)

    assert not tirage.existe
    lignes = atelier_pdf.lignes_du_pied(tirage)
    assert len(lignes) == 1
    assert atelier_pdf.PIED_SANS_TIRAGE in lignes[0]
    assert lignes[0].strip() != ""
    assert "0" not in lignes[0]


def test_la_DATE_disparait_quand_le_fichier_ne_repond_pas(tmp_path):
    """AC 3.4, et les deux volets.

    Le manifeste ne porte **aucun** signal d'horloge pour un tirage -- son
    idempotence est verifiee octet a octet --, la date vient donc du fichier. Un
    tirage declare dont le fichier a ete renomme a la main est **le cas meme**
    que l'inventaire existe pour couvrir : il reste nomme, et c'est le segment
    de date qui part.
    """
    absent = json.loads(
        (_projet(tmp_path / "absent", sur_le_disque=False) / "project.json")
        .read_text(encoding="utf-8"))
    present_dossier = _projet(tmp_path / "present")
    present = json.loads(
        (present_dossier / "project.json").read_text(encoding="utf-8"))

    sans = atelier_pdf.dernier_tirage(absent, tmp_path / "absent")
    avec = atelier_pdf.dernier_tirage(present, present_dossier)

    assert sans.existe and sans.quand is None
    assert avec.quand is not None
    ligne_sans = atelier_pdf.lignes_du_pied(sans)[1]
    ligne_avec = atelier_pdf.lignes_du_pied(avec)[1]
    assert ligne_sans.strip().startswith(f"{sans.pages} ")
    assert ligne_avec.strip().startswith(avec.quand)


def test_les_PAGES_disparaissent_quand_le_manifeste_ne_se_pagine_plus(tmp_path):
    """AC 3.4 : un segment qu'on ne sait pas remplir part, il ne ment pas.

    Le volet symetrique est deja porte par le test du pied nominal, qui asserte
    un cardinal **egal a celui du coeur** : sans lui, un `None` systematique
    serait vert ici.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    # Retirer la cadence source du rush rend la selection non recalculable :
    # c'est le refus nomme `VERIFY_SELECTION_NOT_RECOMPUTED` du coeur.
    for rush in manifeste["rushes"]:
        rush.pop("fps_source_exact", None)
        rush.pop("fps_source", None)

    tirage = atelier_pdf.dernier_tirage(manifeste, dossier)
    assert tirage.existe and tirage.pages is None
    ligne = atelier_pdf.lignes_du_pied(tirage)[1]
    assert "page" not in ligne
    assert atelier_pdf.MENTION_DU_RANG.format(
        rang=RANG_DU_TIRAGE_ATTENDU) in ligne


def test_le_pied_rendu_est_CELUI_DE_LA_MAQUETTE(tmp_path, banc):
    """AC 3.4 : les trois lignes, a la colonne pres.

    La colonne des valeurs et celle des deux lignes de suite sont **derivees**
    de `LARGEUR_DU_LIBELLE_DU_PIED` ; le test les recompose depuis la meme
    constante plutot que d'epingler un nombre de blancs, qui serait la valeur
    du code recopiee dans son banc.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(encoding="utf-8"))
    tirage = atelier_pdf.dernier_tirage(manifeste, dossier)
    lignes = atelier_pdf.lignes_du_pied(tirage)

    colonne = 5 + atelier_pdf.LARGEUR_DU_LIBELLE_DU_PIED
    assert len(lignes) == 3
    assert lignes[0].startswith("     " + atelier_pdf.LIBELLE_DU_PIED)
    assert lignes[0][colonne:] == tirage.nom
    assert lignes[1][:colonne].strip() == ""
    assert lignes[1][colonne:] == atelier_pdf.SEPARATEUR_DU_PIED.join(
        (tirage.quand, f"{tirage.pages} pages",
         atelier_pdf.MENTION_DU_RANG.format(rang=tirage.rang)))
    assert lignes[2][colonne:] == tirage.gabarit


# ---------------------------------------------------------------------------
# AC 3.5 -- le bandeau : deux mesures, une seule lecture
# ---------------------------------------------------------------------------

def test_le_bandeau_porte_les_lots_et_la_SOMME_des_tirages(tmp_path, banc):
    """AC 3.5 : la somme sur **tous** les lots, jamais celle du premier.

    Les trois lots portent 1, 3 et 2 tirages : la somme (6) ne coincide avec
    aucun compte partiel, si bien qu'un `lots[0]`, un `lots[-1]` ou un
    `break` premature se voient dans le chiffre affiche.
    """
    dossier = _projet(tmp_path)
    ecran = atelier_pdf.EcranPdfMenu(dossier)
    app = _app(ecran)

    async def scenario(pilote):
        return ecran.bandeau(PLANCHER[0]), ecran.comptes

    bandeau, comptes = _monte(app, scenario, banc)
    total = sum(TIRAGES_PAR_LOT.values())
    assert comptes.lots == len(TIRAGES_PAR_LOT)
    assert comptes.tirages == total
    assert total not in set(TIRAGES_PAR_LOT.values())
    assert bandeau.endswith(f"{len(TIRAGES_PAR_LOT)} lots · {total} "
                            "tirages produits")


def test_le_bandeau_d_un_projet_VIDE_dit_zero_plutot_que_rien(tmp_path, banc):
    """AC 3.5 : « jamais une chaine vide »."""
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path, avec_tirages=False))
    app = _app(ecran)

    async def scenario(pilote):
        return ecran.comptes.rendu()

    assert _monte(app, scenario, banc) == "3 lots · 0 tirage produit"


def test_les_accords_du_bandeau_au_singulier_et_au_pluriel():
    """AC 3.5 : le nom **et** son participe s'accordent, zero compris."""
    assert atelier_pdf.ComptesDuPdf(1, 1).rendu() == "1 lot · 1 tirage produit"
    assert atelier_pdf.ComptesDuPdf(0, 0).rendu() == "0 lot · 0 tirage produit"
    assert atelier_pdf.ComptesDuPdf(5, 3).rendu() == \
        "5 lots · 3 tirages produits"


def test_le_manifeste_est_lu_UNE_SEULE_fois_par_visite(tmp_path, banc,
                                                       monkeypatch):
    """AC 3.5 : « deux mesures derivees du seul manifest deja lu ».

    Relire pour le second compte donnerait deux etats potentiellement
    differents d'un projet qu'un autre processus peut ecrire entre-temps -- et
    le bandeau contredirait alors son propre pied. La seconde moitie du test
    est le volet symetrique : **revenir** sur le menu relit, sans quoi une
    generation ne se verrait jamais au retour (defaut `V2-M2`).
    """
    dossier = _projet(tmp_path)
    lectures = []
    vraie = projet_lecture.lire_manifeste
    monkeypatch.setattr(
        projet_lecture, "lire_manifeste",
        lambda chemin: (lectures.append(chemin), vraie(chemin))[1])

    ecran = atelier_pdf.EcranPdfMenu(dossier)
    app = _app(ecran)

    async def scenario(pilote):
        # Le compte part de l'ecran DEJA monte : la construction et l'arrivee
        # sur le palier ont chacune leur lecture, et ce qui se mesure ici est
        # ce que le DESSIN coute, pas le montage.
        depart = len(lectures)
        ecran.rafraichir()
        ecran.rafraichir()
        apres_dessins = len(lectures) - depart
        ecran.reprendre()
        return apres_dessins, len(lectures) - depart

    apres_dessins, apres_retour = _monte(app, scenario, banc)
    assert apres_dessins == 0, lectures
    assert apres_retour == 1, lectures


# ---------------------------------------------------------------------------
# Le dessin : grille, repli ASCII, curseur
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_menu_tient_le_plancher_80x24(tmp_path, banc, ascii_seul):
    """`EPIC11-ARB-21` : 80 colonnes, dans les **deux** regimes.

    Un repli ASCII peut **allonger** un texte -- `·` rend `.`, `⏎` rend
    `Entree` --, si bien qu'une ligne calee juste en UTF-8 deborde une fois
    repliee. Mesurer un seul regime laisse passer exactement cette famille.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran, ascii_seul=ascii_seul)

    async def scenario(pilote):
        return _rendu(ecran, ascii_seul), ecran.bandeau(PLANCHER[0])

    lignes, bandeau = _monte(app, scenario, banc)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= UTILE, ligne
    assert jetons.colonnes(bandeau) <= UTILE
    assert jetons.colonnes(
        jetons.replier_ascii(atelier_pdf.RACCOURCIS_PDF_MENU)) <= UTILE
    # Le corps, la ligne d'etat et la ligne de raccourcis tiennent dans la
    # hauteur du plancher : le chrome prend sept lignes des vingt-quatre.
    assert len(lignes) <= PLANCHER[1] - 7, len(lignes)


def test_le_haut_de_l_ecran_est_CELUI_DE_LA_MAQUETTE(tmp_path, banc):
    """Le titre, les deux entrees et leur filet, **verbatim de `E5-0`**.

    Ces lignes-la ne dependent d'aucun projet : elles se confrontent donc au
    dessin valide, ligne pour ligne, plutot qu'a une paraphrase. Les lignes du
    pied dependent du manifeste et sont mesurees a part.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        return _rendu(ecran, False)

    lignes = _monte(app, scenario, banc)
    maquette = _ecran_de_la_maquette(
        next(m for m in _maquettes_e5() if m.name.startswith("E5-0")))
    # Le cadre pose une colonne de marge de chaque cote : le contenu est
    # `ligne[2:-2]`, ce que `jetons.ajuster` produit deja cale a droite.
    attendues = [ligne[2:-2].rstrip() for ligne in maquette[4:13]]
    assert [ligne.rstrip() for ligne in lignes[:9]] == attendues


@pytest.mark.parametrize("rang", [0, 1])
def test_le_curseur_peint_les_DEUX_lignes_de_son_entree(tmp_path, banc, rang):
    """`EPIC11-ARB-125` : une ligne de continuation ne porte aucun glyphe.

    Elle est donc **donnee** au colorisateur, jamais reconnue par motif. Les
    deux entrees sont mesurees : une entree dont seule la premiere serait
    peinte est exactement la note n°1 du 2026-09-01 sur cette maquette.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        ecran.curseur = rang
        return ecran.rangs_du_curseur(), _rendu(ecran, False)

    rangs, lignes = _monte(app, scenario, banc)
    assert len(rangs) == 2, rangs
    assert lignes[rangs[0]].lstrip().startswith("▸")
    assert not lignes[rangs[1]].lstrip().startswith("▸")
    assert atelier_pdf.ENTREES_DU_MENU[rang].nom in lignes[rangs[0]]


def test_la_ligne_d_etat_du_menu_ne_porte_RIEN(tmp_path, banc):
    """`EPIC11-ARB-56` : aucune touche, aucun conseil, aucun motif de conception.

    Ce menu n'a aucune mesure a dire ; sa ligne d'etat reste donc vide. Le volet
    symetrique est la seconde assertion : la ligne de raccourcis, elle, existe
    et n'a pas fui vers la ligne d'etat.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        ecran.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(str(ecran.query_one("#etat").content))

    etat = _monte(app, scenario, banc)
    assert etat.strip() == "", etat
    assert atelier_pdf.RACCOURCIS_PDF_MENU.strip() != ""


@pytest.mark.parametrize("touche", ["c", "p", "C", "1"])
def test_aucune_LETTRE_ne_navigue_dans_ce_menu(tmp_path, banc, touche):
    """`EPIC11-ARB-45` et `-126`, verbatim : « **Fleche seule !** C'est
    uniquement dans les listes a cocher qu'on trouve les deux. »

    Le volet symetrique est la seconde moitie : les fleches, elles, bougent.
    """
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        avant = ecran.curseur
        pris = ecran.traiter(touche, touche)
        apres_lettre = ecran.curseur
        ecran.traiter("down")
        return avant, pris, apres_lettre, ecran.curseur

    avant, pris, apres_lettre, apres_fleche = _monte(app, scenario, banc)
    assert pris is False
    assert apres_lettre == avant
    assert apres_fleche == avant + 1


def test_le_curseur_ne_sort_pas_de_la_liste(tmp_path, banc):
    """Les deux bornes, jamais une seule : `↑` en tete et `↓` en queue."""
    ecran = atelier_pdf.EcranPdfMenu(_projet(tmp_path))
    app = _app(ecran)

    async def scenario(pilote):
        ecran.traiter("up")
        en_tete = ecran.curseur
        for _ in range(5):
            ecran.traiter("down")
        return en_tete, ecran.curseur

    en_tete, en_queue = _monte(app, scenario, banc)
    assert en_tete == 0
    assert en_queue == len(atelier_pdf.ENTREES_DU_MENU) - 1


# ---------------------------------------------------------------------------
# Frontieres AST -- la TUI n'invente ni rang ni domination
# ---------------------------------------------------------------------------

#: Les fonctions du coeur qui **calculent** un rang de TIRAGE. `EPIC11-ARB-92`,
#: verbatim d'Egan : « il ne faut pas rendre le rang » -- la TUI l'affiche, elle
#: ne le derive pas.
#:
#: **Cette table est le COMPLEMENT de celle de la story 11.6**
#: (`test_versionnage_du_scan_en_tui.VOCABULAIRE_DES_RANGS`), pas sa copie :
#: celle-la couvre le vocabulaire generique et celui du scan -- `prochain_rang`,
#: `ligne_d_eau`, `RANG_ORIGINE`, `format_version_suffix`... -- et **ignore
#: entierement le tirage**, qui n'existait pas quand elle a ete ecrite. Redire
#: ses mots ici en ferait une seconde redaction qui divergerait au premier
#: renommage ; l'intersection des deux tables est donc **vide** par construction,
#: et un test le mesure.
CALCULS_DE_RANG = ("resolve_sheets_version_rank", "sheets_version_watermark",
                   "_rangs_sur_le_disque", "_rangs_declares",
                   "rangs_liberables", "est_en_queue")

#: Le vocabulaire de la domination des mises en page (lot B8). Il est **interdit
#: de DEFINITION** dans `tui/`, jamais d'appel : la TUI consomme le calcul du
#: coeur -- c'est tout l'objet d'`EPIC11-ARB-154`, « calcule par le produit et
#: JAMAIS RECOPIE » --, et un ecran de reglages a le droit de l'appeler. Ce
#: qu'on ferme est la **seconde redaction**, pas la consommation.
CALCULS_DE_DOMINATION = ("bilan_de_domination", "dominants_des_mises_en_page",
                         "mesurer_les_mises_en_page", "domine",
                         "surface_de_dessin_mm")


def _definitions(chemin: Path) -> set[str]:
    """Le lecteur PUBLIE de l'outillage, jamais une seconde redaction.

    Il a d'abord ete ecrit ici ; la couche 3 de la revue de la 11.11 a montre
    que la frontiere d'`EPIC11-ARB-23` avait besoin du meme lecteur et ne
    l'avait pas -- une classe definie et jamais citee lui etait invisible. Un
    lecteur d'AST qui existe en deux exemplaires divergera au premier des
    deux qui gagne un cas.
    """
    from outils_frontiere import definitions

    return definitions(chemin)


def _appeles(chemin: Path) -> set[str]:
    """Les noms qui sont APPELES : `f(...)` et `mod.f(...)`, jamais un simple lu."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    appeles = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        if isinstance(noeud.func, ast.Name):
            appeles.add(noeud.func.id)
        elif isinstance(noeud.func, ast.Attribute):
            appeles.add(noeud.func.attr)
    return appeles


def test_aucun_module_de_la_TUI_ne_CALCULE_un_rang(sources_tui):
    """`EPIC11-ARB-92` : le rang est **affiche**, jamais recalcule.

    Le mode de panne que ca ferme est le pire du versionnage : deux feuilles de
    papier differentes portant le meme « tirage N ». Une fois l'encre seche,
    aucun fichier ne rattrape cela.

    **La mesure porte sur la DEFINITION et sur l'APPEL, jamais sur la simple
    lecture d'un attribut** -- meme distinction que
    :data:`CALCULS_DE_DOMINATION` juste en dessous, et pour le meme motif : « ce
    qu'on ferme est la seconde redaction, pas la consommation ».

    **Ce qui l'a fait bouger, le 2026-09-05, avec la story 11.11.** Le coeur
    nomme un CHAMP de `RapportSuppression` d'apres une FONCTION de
    `io.version_ranks` : `rangs_liberables` est les deux a la fois. Un ecran qui
    affiche `plan.rapport.rangs_liberables` **consomme** le calcul du coeur --
    c'est litteralement ce qu'`EPIC11-ARB-92` demande --, et la version
    precedente le comptait comme une redaction parce qu'`identifiants()` rend
    l'`attr` d'un `ast.Attribute` sans savoir s'il est appele.

    Le raffinement ne perd **aucune dent**, et c'est verifiable plutot que
    plausible : on ne peut pas recalculer un rang sans appeler quelque chose,
    tandis qu'un affichage n'appelle rien. Le volet symetrique juste en dessous
    le mesure sur un module fautif de synthese, parce qu'une frontiere qu'on
    assouplit sans montrer qu'elle mord encore n'est plus une frontiere.
    """
    for chemin in sources_tui:
        vus = _appeles(chemin) | _definitions(chemin)
        assert not (vus & set(CALCULS_DE_RANG)), (
            chemin.name, sorted(vus & set(CALCULS_DE_RANG)))


def test_la_mesure_du_CALCUL_de_rang_MORD_sur_un_module_fautif(tmp_path):
    """Le volet symetrique du raffinement ci-dessus. **Trois regimes.**

    Sans lui, l'assouplissement du 2026-09-05 serait invisible : la frontiere
    resterait verte sur un module qui APPELLE la regle des rangs, et personne ne
    le saurait avant d'avoir imprime deux feuilles portant le meme tirage.
    """
    fautif_appel = tmp_path / "fautif_appel.py"
    fautif_appel.write_text(
        "from ..io import version_ranks\n"
        "def afficher(rangs, manifeste):\n"
        "    return version_ranks.rangs_liberables(manifeste)\n",
        encoding="utf-8")
    fautif_nu = tmp_path / "fautif_nu.py"
    fautif_nu.write_text(
        "from ..io.version_ranks import est_en_queue\n"
        "def afficher(objet):\n"
        "    return est_en_queue(objet)\n",
        encoding="utf-8")
    sage = tmp_path / "sage.py"
    sage.write_text(
        "def afficher(rapport):\n"
        "    return rapport.rangs_liberables\n",
        encoding="utf-8")

    for fautif in (fautif_appel, fautif_nu):
        vus = _appeles(fautif) | _definitions(fautif)
        assert vus & set(CALCULS_DE_RANG), (
            f"{fautif.name} APPELLE la regle des rangs et la frontiere ne le "
            "voit pas : elle ne mesure plus rien")

    vus = _appeles(sage) | _definitions(sage)
    assert not (vus & set(CALCULS_DE_RANG)), (
        "un module qui se contente d'AFFICHER un champ du rapport du coeur ne "
        "redige aucune regle de rang -- c'est ce qu'`EPIC11-ARB-92` demande")


def test_aucun_module_de_la_TUI_ne_REDIGE_une_domination(sources_tui):
    """`EPIC11-ARB-154` : le calcul vit au coeur, la TUI l'appelle.

    C'est une frontiere de **definition** et non d'appel, et la nuance est
    volontaire : interdire l'appel interdirait a l'ecran de reglages de
    consommer le lot B8, c'est-a-dire l'inverse de ce que l'arbitrage demande.
    """
    for chemin in sources_tui:
        definies = _definitions(chemin) & set(CALCULS_DE_DOMINATION)
        assert not definies, (chemin.name, sorted(definies))


def test_cette_frontiere_de_RANG_ne_recopie_pas_celle_de_la_11_6():
    """Les deux tables sont **disjointes** : complement, jamais copie.

    Sans cette mesure, un mot pourrait vivre dans les deux et diverger a la
    premiere reecriture -- l'une des deux frontieres cesserait alors de mesurer
    ce qu'elle croit, sans que rien ne rougisse.
    """
    from test_versionnage_du_scan_en_tui import VOCABULAIRE_DES_RANGS

    commun = set(CALCULS_DE_RANG) & set(VOCABULAIRE_DES_RANGS)
    assert commun == set(), sorted(commun)


def test_les_DEUX_frontieres_ci_dessus_ont_bien_un_OBJET():
    """Volet symetrique des deux frontieres : elles savent trouver leur cible.

    Une frontiere negative dont le vocabulaire ne designerait plus rien serait
    verte sans rien mesurer -- « une frontiere qui ne trouve plus son objet est
    verte pour la mauvaise raison ». On mesure donc que les deux tables
    **existent** dans les modules de coeur qui les possedent.
    """
    coeur = Path(pdf_composition.__file__)
    rangs = identifiants(coeur) | _definitions(coeur)
    assert set(CALCULS_DE_RANG) & rangs, sorted(rangs)

    gabarits = Path(page_templates.__file__)
    assert set(CALCULS_DE_DOMINATION) <= _definitions(gabarits), sorted(
        set(CALCULS_DE_DOMINATION) - _definitions(gabarits))


def test_le_module_de_l_atelier_Pdf_n_importe_JAMAIS_cli(tmp_path):
    """Frontiere de la story 11.4b, rejouee sur le module neuf.

    Le volet symetrique est la seconde assertion : le module importe bien du
    coeur, donc la mesure regarde un fichier qui a des imports.
    """
    module = Path(atelier_pdf.__file__)
    noms = identifiants(module)
    assert "cli" not in noms
    assert not any(nom.endswith(".cli") for nom in noms), sorted(noms)
    assert {"pdf_manifest", "projet_lecture"} <= noms, sorted(noms)
