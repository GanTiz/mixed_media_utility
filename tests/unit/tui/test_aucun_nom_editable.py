# -*- coding: utf-8 -*-
"""Story 11.4e, lots G et H -- `EPIC11-ARB-141` : plus AUCUN nom editable.

**Un retrait ne se mesure que par une frontiere NEGATIVE.** Aucun test positif
ne verra revenir un champ de saisie : c'est pour cela que ce banc existe, et
c'est la seule chose qu'il fait. Sans lui, un champ revient a la prochaine
maquette -- ce que ce depot paie chaque fois qu'il retire sans mesurer.

L'arbitrage, verbatim d'Egan (2026-09-01) : « On retire l'edition des noms
PARTOUT ou elle ne peut pas etre effective. On la laisse uniquement la ou on
sait la cabler. » Le critere n'est pas l'intention, c'est le **cablage** : si le
point d'entree de coeur ne porte pas de parametre ou le nom puisse aller, le
champ se retire.

Ce que ce banc mesure, en quatre couches
----------------------------------------
1. **la borne reste LUE** (`tui.noms.LIMITE` **est**
   `io.naming.CANONICAL_ID_MAX_LENGTH`). C'est le seul risque nomme du lot G :
   les quatre tests d'AC 2.4 vivaient dans `test_noms_editables.py`, que le lot
   retire, et ils sont **portes ici avant** que le fichier parte. Ils ne
   recopient plus le nombre nulle part -- pas meme dans un nom de test : la
   fiche de la 11.4d avait releve un `assert LIMITE == 48` recopiant la borne
   juste sous la frontiere censee l'interdire ;
2. **le cablage n'existe pas, donc le champ n'existe pas.** L'ensemble ferme
   des points d'entree de coeur SANS parametre de nom est mesure sur les
   signatures reelles ; tant qu'il n'est pas vide, aucun module de la TUI ne
   fabrique de champ de nom. Le jour ou le coeur gagne le parametre, cette
   frontiere rougit et **force la reprise plutot que l'oubli** : c'est ce qui
   rend le report reversible sans dette cachee ;
3. **les noms DERIVES restent montres.** `E2-3` et `E3-6` sont les ecrans de
   **jugement** des deux ateliers : on leur retire un mode, pas leur raison
   d'etre. Un retrait qui emporterait les noms rendrait le panneau muet sur ce
   qu'il va ecrire, c'est-a-dire contraire a `EPIC11-ARB-4` ;
4. **rien n'annonce plus une touche inerte** -- ni la ligne d'etat du produit,
   ni la maquette qui la valide.

La regle des fabriques, appliquee ici
-------------------------------------
Les deux fabriques produisent **trois** lots distinguables, et les assertions
portent sur la liste **entiere et ordonnee** : la cible est en tete, au milieu
ET en queue. Une cible au milieu demasque un `find` fautif ; elle ne demasque
pas un balayage tronque, qui est un autre mode de panne (point 4 de la regle,
pose le 2026-09-03 sur un mutant survivant de la 11.11).
"""
from __future__ import annotations

import ast
import inspect
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import extraction, scan_write
from mixed_media_utility.io.naming import CANONICAL_ID_MAX_LENGTH
from mixed_media_utility.tui import atelier_extraction_ecriture as extraction_tui
from mixed_media_utility.tui import atelier_scan_confirmation as scan_tui
from mixed_media_utility.tui import noms as module_noms

import test_atelier_extraction_ecriture as fabriques_extraction
import test_atelier_scan_confirmation as fabriques_scan
from outils_frontiere import constantes_entieres

#: La racine des maquettes relues. Une maquette qui montrerait encore un champ
#: d'edition se relirait comme **validee** : c'est le defaut paye a la vague 3,
#: et le lot H existe pour lui.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")


# ===========================================================================
# 1 -- La borne RESTE, et elle reste LUE (AC 2.4, portee depuis
#      `test_noms_editables.py` que le lot G retire)
# ===========================================================================

def test_la_limite_de_la_tui_EST_celle_du_coeur():
    """L'invariant est l'IDENTITE, jamais la valeur.

    `tui.noms.LIMITE` **est** l'objet du coeur, et non un entier qui lui
    ressemble aujourd'hui. La distinction n'est pas theorique : la borne a valu
    48, puis 64 sur `main` le 2026-08-28, puis 48 de nouveau avec un
    `LEGACY_ID_MAX_LENGTH` en lecture seule (`EPIC11-ARB-110`). Une assertion
    sur la valeur rougirait a chacune de ces bascules **legitimes**.
    """
    assert module_noms.LIMITE is CANONICAL_ID_MAX_LENGTH
    assert isinstance(module_noms.LIMITE, int) and module_noms.LIMITE > 0


def test_le_litteral_de_la_borne_n_apparait_nulle_part_ailleurs_dans_la_tui(
        sources_tui):
    """AC 2.4, frontiere : comptage a zero hors du point d'import.

    La mesure porte sur les **constantes entieres du code**, pas sur le texte :
    un nombre dans une phrase d'explication n'est pas une limite recopiee, et
    une garde qui les confondrait se ferait affaiblir a la premiere prose.

    **Le nombre lui-meme n'est pas ecrit ici** : il est lu du coeur, comme le
    produit le lit. Un banc qui graverait la borne pour mesurer qu'on ne la
    grave pas serait sa propre contre-mesure.
    """
    point_d_import = module_noms.__file__
    coupables = {chemin.name: [valeur for valeur in constantes_entieres(chemin)
                               if valeur == CANONICAL_ID_MAX_LENGTH]
                 for chemin in sources_tui
                 if str(chemin) != str(point_d_import)}
    assert not any(coupables.values()), coupables


def test_le_point_d_import_ne_recopie_pas_non_plus_le_nombre():
    """Meme au point d'import : la limite est un ALIAS, pas une copie."""
    assert CANONICAL_ID_MAX_LENGTH not in constantes_entieres(
        module_noms.__file__)


def test_la_mesure_du_litteral_MORD_sur_un_module_fautif(tmp_path):
    """AC 2.4, volet symetrique.

    Sans lui, un detecteur casse -- qui ne lirait aucune constante -- serait
    vert sur tout le paquet.
    """
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text(
        f'"""Un docstring qui parle de {CANONICAL_ID_MAX_LENGTH} caracteres."""\n'
        f"LIMITE = {CANONICAL_ID_MAX_LENGTH}\n", encoding="utf-8")
    assert CANONICAL_ID_MAX_LENGTH in constantes_entieres(chemin)


# ===========================================================================
# 2 -- LA frontiere du lot G : pas de cablage, donc pas de champ
# ===========================================================================

#: Ce qui, dans le nom d'un parametre, designerait une place ou un nom
#: d'operateur pourrait aller. Large a dessein : la frontiere doit rougir sur
#: `nom_du_lot` comme sur `lot_name` ou `ingest_slug`.
MOTIF_D_UN_PARAMETRE_DE_NOM = re.compile(r"nom|name|slug|libell|label|intitul",
                                         re.IGNORECASE)

#: L'ensemble **FERME** des points d'entree de coeur qui n'ont, au
#: `baseline_commit`, aucune place ou recevoir un nom d'operateur. C'est la
#: mesure qui a fait trancher `EPIC11-ARB-141` -- 16 mots-cles d'un cote, 14 de
#: l'autre, aucun parametre de nom -- et c'est elle qui rend le retrait
#: **reversible** : le jour ou l'un des deux gagne ce parametre, le test
#: ci-dessous rougit et force la reprise du champ plutot que son oubli.
POINTS_D_ENTREE_SANS_PARAMETRE_DE_NOM = (
    ("extraction.run_extraction", extraction.run_extraction),
    ("scan_write.ecrire_depuis_le_document", scan_write.ecrire_depuis_le_document),
)

#: Les modules de la TUI qui portent encore le **modele** d'edition, et le
#: motif de chacun. Ensemble **EXACT** : il rougit aussi bien sur un
#: importateur neuf que sur un nettoyage -- et c'est le second cas qui est
#: attendu, `execution.py` devant perdre son mode d'edition le jour ou son
#: proprietaire le retirera (verse a `deferred-work.md`).
MODULES_QUI_IMPORTENT_ENCORE_LE_MODELE = {
    # L'ecran partage par les quatre ateliers. Il porte le mode d'edition
    # lui-meme -- `Tab`, `_traiter_en_edition`, `RACCOURCIS_EDITION_DES_NOMS` --
    # et aucun atelier ne l'atteint plus. La carcasse est **morte**, pas
    # dangereuse : sans `ModeleNoms` peuple, `traiter("tab")` rend `False`.
    "execution.py",
    # Les deux ateliers deja passes sous `EPIC11-ARB-141` (stories 11.7 et
    # 11.8). Ils passent un modele **vide** explicitement plutot que de ne rien
    # passer ; l'Extraction et le Scan, eux, ne l'importent plus du tout.
    "atelier_pdf_confirmation.py",
    "atelier_exports_confirmation.py",
}


def champs_de_nom_fabriques(chemin) -> list[str]:
    """Les appels qui FABRIQUENT un champ de nom editable dans un module.

    Un `ModeleNoms()` **vide** n'est pas un champ : c'est l'absence de champ,
    dite explicitement. Ce qui compte est le modele **peuple** -- et tout
    `NomEditable`, qui n'existe que pour etre edite.

    La mesure porte sur l'arbre et non sur le texte : un `ModeleNoms` cite dans
    une docstring n'est pas un champ, et une garde qui les confondrait se ferait
    affaiblir a la premiere prose.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
    fabriques = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        appele = noeud.func
        nom = (appele.id if isinstance(appele, ast.Name)
               else getattr(appele, "attr", None))
        if nom == "NomEditable":
            fabriques.append("NomEditable")
        elif nom == "ModeleNoms" and (noeud.args or noeud.keywords):
            fabriques.append("ModeleNoms(peuple)")
    return fabriques


def test_aucun_point_d_entree_de_coeur_ne_porte_de_place_pour_un_nom():
    """La mesure qui **conditionne** tout le reste du lot G.

    Elle est ecrite sur les signatures reelles, pas sur la fiche : c'est
    exactement ce que `EPIC11-ARB-141` a demande -- « le critere n'est pas
    l'intention, c'est le cablage ».
    """
    assert POINTS_D_ENTREE_SANS_PARAMETRE_DE_NOM, (
        "anti-vacuite : l'ensemble ferme ne peut pas etre vide, sinon la "
        "frontiere du champ ci-dessous serait verte pour rien")
    coupables = {}
    for nom, fonction in POINTS_D_ENTREE_SANS_PARAMETRE_DE_NOM:
        places = [parametre for parametre in inspect.signature(fonction).parameters
                  if MOTIF_D_UN_PARAMETRE_DE_NOM.search(parametre)]
        if places:
            coupables[nom] = places
    assert coupables == {}, (
        f"{coupables} : un point d'entree de coeur a gagne une place pour un "
        "nom d'operateur. `EPIC11-ARB-141` est leve pour lui, et le champ "
        "d'edition doit REVENIR sur l'ecran qui l'alimente -- ce n'est pas "
        "cette frontiere qu'il faut corriger, c'est le retrait qu'il faut "
        "reprendre.")


def test_la_mesure_des_places_de_nom_MORD_sur_une_signature_fautive():
    """Volet symetrique : un detecteur qui ne verrait rien serait vert sur tout."""
    def coeur_fautif(project_dir, *, logger=None, nom_du_lot=None):
        """Un point d'entree qui, lui, saurait recevoir un nom."""

    places = [parametre for parametre in inspect.signature(coeur_fautif).parameters
              if MOTIF_D_UN_PARAMETRE_DE_NOM.search(parametre)]
    assert places == ["nom_du_lot"]


def test_AUCUN_module_de_la_tui_ne_fabrique_plus_un_champ_de_nom(sources_tui):
    """**La frontiere du lot G** (G5), et le coeur du lot.

    Aucun ecran ne presente un champ de nom editable dont la valeur n'atteint
    aucun mot-cle du point d'entree de coeur -- et comme le test precedent
    mesure qu'AUCUN mot-cle de nom n'existe, la conclusion est absolue :
    aucun champ, nulle part.

    Ce que la mesure ne dit PAS, dit plutot que tu : elle ne mesure pas le
    modele lui-meme, qui survit dans `tui/noms.py` parce qu'`execution.py` --
    l'ecran partage, propriete d'un autre lot -- l'importe encore. C'est le
    test suivant qui tient cet ecart-la, et il est verse a `deferred-work.md`.
    """
    coupables = {chemin.name: champs_de_nom_fabriques(chemin)
                 for chemin in sources_tui}
    assert not any(coupables.values()), {
        nom: fabriques for nom, fabriques in coupables.items() if fabriques}


def test_la_mesure_du_champ_MORD_sur_un_module_fautif(tmp_path):
    """Volet symetrique, aux deux formes du defaut.

    Un module qui reintroduirait l'edition le ferait soit par un `NomEditable`,
    soit par un `ModeleNoms` peuple : les deux sont mesures, et le modele vide
    -- qui est l'absence de champ dite explicitement -- ne l'est pas.
    """
    fautif = tmp_path / "atelier_fautif.py"
    fautif.write_text(
        "from .noms import ModeleNoms, NomEditable\n"
        "def noms_du_plan(plan):\n"
        "    return ModeleNoms([NomEditable(lot.lot_id) for lot in plan.lots])\n",
        encoding="utf-8")
    assert champs_de_nom_fabriques(fautif) == ["ModeleNoms(peuple)",
                                               "NomEditable"]

    sobre = tmp_path / "atelier_sobre.py"
    sobre.write_text("from .noms import ModeleNoms\n"
                     "VIDE = ModeleNoms()\n", encoding="utf-8")
    assert champs_de_nom_fabriques(sobre) == []


def test_l_ensemble_des_modules_qui_importent_le_modele_est_EXACT(sources_tui):
    """L'ecart qui reste, **nomme** plutot que tu.

    `NomEditable` et `ModeleNoms` devaient partir de `tui/noms.py` (G3). Ils
    restent parce que `execution.py` les importe et qu'il appartient au lot I :
    la regle de decoupage interdit de le toucher. L'ensemble est donc **exact**
    -- il rougit sur un importateur neuf, et il rougit aussi le jour ou le
    nettoyage aura lieu, ce qui oblige a fermer l'entree de dette au lieu de la
    laisser survivre a la faute qu'elle documentait.
    """
    importateurs = set()
    for chemin in sources_tui:
        if chemin.name == "noms.py":
            continue
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module == "noms":
                if {alias.name for alias in noeud.names} & {"ModeleNoms",
                                                            "NomEditable"}:
                    importateurs.add(chemin.name)
    assert importateurs == MODULES_QUI_IMPORTENT_ENCORE_LE_MODELE, sorted(
        importateurs ^ MODULES_QUI_IMPORTENT_ENCORE_LE_MODELE)


# ===========================================================================
# 3 -- Les deux ecrans de jugement : plus de mode, mais toujours leurs noms
# ===========================================================================

def plan_de_l_extraction(tmp_path):
    """Trois lots, trois cadences, trois noms distinguables.

    Trois et non deux : les assertions de ce banc portent sur la liste
    **entiere**, donc sur une cible en tete, au milieu ET en queue.
    """
    return fabriques_extraction.plan(
        tmp_path, cadences=fabriques_extraction.TROIS_CADENCES)


def ecran_de_l_extraction(tmp_path):
    """`E2-3` construit directement, sans coque : ce banc ne mesure pas le rendu."""
    plan = plan_de_l_extraction(tmp_path)
    return extraction_tui.EcranExtractionConfirmation(
        extraction_tui.panneau_de_l_extraction(plan),
        extraction_tui.issues_de_l_extraction(),
        sur_issue=lambda issue: None), plan


def test_E2_3_n_a_plus_AUCUN_nom_editable_et_Tab_ne_mene_nulle_part(tmp_path):
    """G2 : le mode d'edition de l'Extraction n'existe plus.

    `Tab` rend `False` -- il n'est pas garde, il n'a **pas de destination** :
    c'est la consequence de ne pas donner de noms editables, pas une garde
    ajoutee. Une garde se retire ; une absence de destination, non.
    """
    ecran, _plan = ecran_de_l_extraction(tmp_path)
    assert len(ecran.noms) == 0
    assert ecran.traiter("tab") is False
    assert not ecran.noms.en_edition


def test_E3_6_n_a_plus_AUCUN_nom_editable_et_Tab_ne_mene_nulle_part():
    """G1 : idem cote Scan, sur le meme ecran partage."""
    ecran = scan_tui.EcranScanConfirmation(fabriques_scan.plan_nominal())
    assert len(ecran.noms) == 0
    assert ecran.traiter("tab") is False
    assert not ecran.noms.en_edition


def test_une_LETTRE_tapee_sur_E3_6_ne_modifie_plus_rien():
    """Le volet qui mesure que le mode est **inatteignable**, pas seulement ferme.

    Sans champ, une frappe n'est pas consommee : elle remonte a l'application.
    C'est l'inverse exact du mode d'edition, qui capturait TOUT le clavier.
    """
    ecran = scan_tui.EcranScanConfirmation(fabriques_scan.plan_nominal())
    assert ecran.traiter("r", "r") is False
    assert len(ecran.noms) == 0


def test_les_noms_DERIVES_de_E3_6_restent_montres_EN_ENTIER():
    """G1, volet positif : on retire un mode, pas la raison d'etre de l'ecran.

    L'assertion porte sur la liste **entiere et ordonnee** -- tete, milieu et
    queue. Un balayage tronque d'une entree ferait disparaitre le dernier lot
    en silence, et une cible au milieu ne le demasquerait pas.
    """
    panneau = scan_tui.panneau_de_la_confirmation(fabriques_scan.plan_nominal())
    assert panneau.noms == [
        extraction_tui.INDENT_DES_NOMS + fabriques_scan.SLUG_PREMIER,
        extraction_tui.INDENT_DES_NOMS + fabriques_scan.SLUG_CIBLE,
        extraction_tui.INDENT_DES_NOMS + fabriques_scan.SLUG_DERNIER,
    ]


def test_les_noms_DERIVES_de_E2_3_restent_montres_EN_ENTIER(tmp_path):
    """G2, volet positif. Meme mesure, meme motif, sur l'autre atelier."""
    plan = plan_de_l_extraction(tmp_path)
    panneau = extraction_tui.panneau_de_l_extraction(plan)
    attendus = [extraction_tui.INDENT_DES_NOMS + lot.lot_id
                for lot in plan.lots]
    assert len(attendus) == 3, plan.lots
    assert panneau.noms == attendus
    # Les trois sont **distinguables** : une fabrique uniforme rendrait
    # invisible toute permutation (mutant `M33` de la story 5.6).
    assert len(set(panneau.noms)) == 3


def test_le_cartouche_de_E2_3_MONTRE_les_trois_noms_a_l_ecran(tmp_path, banc):
    """Le volet monte : `EcranChiffre` rend un panneau **sans** ses noms.

    C'est le piege exact du lot H de la 11.7 : les noms d'un `Panneau` ne
    sortent que si l'ecran **redit** qu'il les veut. Un banc qui n'aurait mesure
    que le modele aurait ete vert sur un ecran muet.
    """
    plan = plan_de_l_extraction(tmp_path)

    async def scenario(pilote, ecran):
        return "\n".join(
            str(widget.content) for widget
            in pilote.app.screen.query_one("#centre").query("Static"))

    rendu, _ecrit, _boite = fabriques_extraction.monter_le_jugement(
        tmp_path, banc, scenario, plan=plan)
    for lot in plan.lots:
        assert lot.lot_id in rendu, (lot.lot_id, rendu)


# ===========================================================================
# 4 -- H2 : plus une seule touche annoncee qui ne mene nulle part
# ===========================================================================

#: Ce qu'une ligne d'etat ou une maquette ne peut plus annoncer. La formulation
#: est celle du produit d'avant (`execution.RACCOURCIS_CONFIRMATION`) et celle
#: de la maquette `T1-2` (« editer les noms produits »), reduites a leur tete
#: commune.
PROMESSE_RETIREE = "diter les noms"


@pytest.mark.parametrize("ligne", [
    pytest.param(extraction_tui.RACCOURCIS_EXTRACTION_CONFIRMATION, id="E2-3"),
    pytest.param(extraction_tui.RACCOURCIS_EXTRACTION_ECRASEMENT, id="T4-2"),
    pytest.param(scan_tui.RACCOURCIS_SCAN_CONFIRMATION, id="E3-6"),
])
def test_la_ligne_de_raccourcis_n_annonce_plus_l_edition(ligne):
    """H2. Une touche annoncee et inerte est le defaut que `coque.py` documente."""
    assert PROMESSE_RETIREE not in ligne
    assert "Tab" not in ligne


def test_les_deux_ecrans_portent_leur_PROPRE_ligne_et_non_celle_du_partage():
    """La ligne du partage promet encore `Tab` : la reprendre serait mentir.

    Les deux issues etaient de poser une ligne propre ou de corriger la
    constante partagee ; corriger la constante toucherait `execution.py`, qui
    appartient a un autre lot. C'est donc une ligne propre, sur le precedent
    des ateliers Pdf et Exports -- et l'ecart sur la constante partagee reste
    ouvert, verse a `deferred-work.md`.
    """
    from mixed_media_utility.tui.execution import RACCOURCIS_CONFIRMATION

    assert PROMESSE_RETIREE in RACCOURCIS_CONFIRMATION, (
        "anti-vacuite : le jour ou la constante partagee sera corrigee, les "
        "deux ateliers pourront la reprendre et cette tolerance tombera")
    assert extraction_tui.EcranExtractionConfirmation.raccourcis \
        is extraction_tui.RACCOURCIS_EXTRACTION_CONFIRMATION
    # **L'ecran d'ecrasement porte SA ligne depuis `EPIC11-ARB-245`** : son
    # cartouche defile, donc sa ligne annonce `Ctrl+↓`. Ce que ce test mesure
    # reste le meme -- aucun des deux ne reprend la ligne du partage, qui
    # promet `Tab` --, et la nouvelle ligne est verifiee ici aussi.
    assert extraction_tui.EcranExtractionEcrasement.raccourcis \
        is extraction_tui.RACCOURCIS_EXTRACTION_ECRASEMENT
    assert PROMESSE_RETIREE not in extraction_tui.RACCOURCIS_EXTRACTION_ECRASEMENT
    assert scan_tui.EcranScanConfirmation.raccourcis \
        is scan_tui.RACCOURCIS_SCAN_CONFIRMATION


# ===========================================================================
# 5 -- H1 : les maquettes suivent, et elles se corrigent A LA SOURCE
# ===========================================================================

#: Les maquettes qui montrent encore un champ de nom, et **pourquoi**. Ensemble
#: **EXACT** : il rougit sur une maquette neuve qui en montrerait un, et il
#: rougit aussi le jour ou celles-ci partiront.
#:
#: `E2-3b` et `E2-3c` sont les deux etats du mode d'edition d'`EcranChiffre` --
#: l'ecran partage de `execution.py`, que ce lot n'a pas le droit de toucher.
#: Elles decrivent donc un mode qui existe encore dans le code et qu'aucun
#: atelier n'atteint plus. Les retirer appartient au lot qui retirera le mode.
MAQUETTES_DU_MODE_D_EDITION_ENCORE_PRESENTES = {
    "E2-3b-extraction-edition-nom.txt",
    "E2-3c-extraction-nom-refuse.txt",
}


def test_AUCUNE_maquette_ne_montre_plus_un_champ_de_nom_editable():
    """H1, frontiere.

    Deux marques trahissent un champ : la **promesse** en ligne d'etat ou de
    raccourcis, et le **compteur vivant** `n/<borne>` que seul un champ porte.
    La seconde se mesure avec la borne LUE du coeur, jamais recopiee -- une
    maquette gravant le nombre serait fausse a la prochaine bascule, ce que
    l'ecart `H6` de la 11.6 a deja paye.
    """
    compteur = re.compile(r"\d+\s*/\s*%d\b" % CANONICAL_ID_MAX_LENGTH)
    fautives = {}
    lues = 0
    for chemin in sorted(MAQUETTES.glob("*.txt")):
        if chemin.name in MAQUETTES_DU_MODE_D_EDITION_ENCORE_PRESENTES:
            continue
        lues += 1
        # La grille seule : les annotations posees SOUS le cadre sont de la
        # prose de relecture, pas de l'ecran -- et l'une d'elles cite
        # legitimement l'ancienne touche pour en raconter le retrait.
        grille = chemin.read_text(encoding="utf-8").split("\n")[:24]
        texte = "\n".join(grille)
        marques = [marque for marque, present in (
            (PROMESSE_RETIREE, PROMESSE_RETIREE in texte),
            ("compteur de saisie", bool(compteur.search(texte))),
        ) if present]
        if marques:
            fautives[chemin.name] = marques
    assert fautives == {}, fautives
    assert lues >= 40, (
        f"anti-vacuite : la frontiere doit LIRE les maquettes ; elle en voit "
        f"{lues}")


def test_les_deux_maquettes_du_mode_d_edition_sont_TOUJOURS_la():
    """Volet symetrique de l'ensemble ferme ci-dessus.

    Sans lui, l'ensemble se viderait en silence le jour ou les deux maquettes
    partiraient, et la tolerance survivrait a la faute qu'elle documentait --
    c'est exactement ce que la revue du 2026-09-01 a trouve sur l'ensemble
    `MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE`.
    """
    presentes = {nom for nom in MAQUETTES_DU_MODE_D_EDITION_ENCORE_PRESENTES
                 if (MAQUETTES / nom).exists()}
    assert presentes == MAQUETTES_DU_MODE_D_EDITION_ENCORE_PRESENTES


@pytest.mark.parametrize("maquette,constante", [
    pytest.param("E2-3-extraction-confirmation.txt",
                 extraction_tui.RACCOURCIS_EXTRACTION_CONFIRMATION, id="E2-3"),
    # `T4-2`, validee par Egan le 2026-09-05 (`EPIC11-ARB-245`) : c'est elle
    # qui porte `Ctrl+↓ lire la suite`, et c'est elle qui fait foi.
    pytest.param("T4-2-ecrasement-cartouche-defilant.txt",
                 extraction_tui.RACCOURCIS_EXTRACTION_ECRASEMENT, id="T4-2"),
    pytest.param("E3-6-scan-confirmation.txt",
                 scan_tui.RACCOURCIS_SCAN_CONFIRMATION, id="E3-6"),
])
def test_la_maquette_annonce_EXACTEMENT_ce_que_l_ecran_annonce(maquette,
                                                               constante):
    """H1 et H2 ensemble : la maquette est **la source**, elle ne derive pas.

    Une maquette corrigee dans le `.txt` rendu se perdrait a la premiere
    regeneration ; une maquette non corrigee se relirait comme validee. Les
    deux se ferment par la meme mesure : la ligne 23 de la grille **est** la
    constante du produit.
    """
    lignes = (MAQUETTES / maquette).read_text(encoding="utf-8").split("\n")
    assert lignes[22][1:-1].rstrip() == " " + constante, lignes[22]
