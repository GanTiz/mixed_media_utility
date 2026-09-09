# -*- coding: utf-8 -*-
"""Story 11.7, lot F -- `E5-3`, la confirmation de l'atelier Pdf (AC 6).

Ce banc mesure `tui/atelier_pdf_confirmation.py`, et **lui seul**. Les autres
lots de la story ont chacun le leur : « aucun lot ne partage un fichier de banc
avec un autre » -- ni `git add -N` ni `git commit -- <chemins>` ne protegent a
l'interieur d'un fichier partage, defaut paye trois fois sur ce depot.

Les quatre regles de mesure heritees, et elles commandent la forme des fabriques
--------------------------------------------------------------------------------
1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte** (`CLAUDE.md`, points 2 et 2 bis). Les deux boucles du module sont
   **les lots du plan** et **les lots du parcours** : les deux fabriques placent
   leur cible en deuxieme position sur trois, avec des pages, des frames et des
   vides **tous differents** -- un remplissage uniforme rendrait invisible toute
   permutation ;
2. **la position se verifie sur la liste que le code PARCOURT**, jamais sur
   celle que la fabrique croit ecrire. Le banc assert donc d'abord sur
   `plan.planches` ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « Cette ligne est presente » ne mesure rien ; « l'ensemble des libelles est
   **exactement** {...} » mesure l'ensemble ET son unicite ;
4. **une frontiere negative porte toujours son volet symetrique**, sans quoi un
   detecteur casse serait vert sur tout.

Deux ecarts EPINGLES et non corriges, et pourquoi
--------------------------------------------------
`execution.py` et `panneau.py` sont partages par les quatre ateliers ; les
modifier depuis un lot d'ecran ferait bouger un observable pour tout le monde.
Les deux ecarts que ce lot rencontre sont donc **constates par un test** plutot
que tus -- c'est ce que le lot H de la 11.6 a fait de son cote, sur le meme
`EcranChiffre` et sur le meme ecart de ligne d'etat :

* `EcranChiffre.etat` rend `panneau.RIEN_ECRIT` **seul**, quand toutes les
  maquettes de confirmation prefixent un recapitulatif chiffre. `E5-3` s'en
  sort en **surchargeant** `etat`, ce que le banc mesure aux deux bouts ;
* `LigneChiffree.rendu` cale le chiffre **a DROITE** de la largeur utile, quand
  les cartouches des maquettes calent les valeurs **a gauche**, a une colonne
  fixe. C'est l'ecart de tous les `E*-3` du depot.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from outils_frontiere import chaines_de_code

from mixed_media_utility import page_templates, pdf_composition
from mixed_media_utility.io import naming
from mixed_media_utility.io.project_layout import PLANCHES_DIRNAME
from mixed_media_utility.tui import atelier_pdf_calibration as mire
from mixed_media_utility.tui import atelier_pdf_confirmation as confirmation
from mixed_media_utility.tui import atelier_pdf_reglages as reglages
from mixed_media_utility.tui import atelier_pdf_versions as versions
from mixed_media_utility.tui import execution, jetons
from mixed_media_utility.tui import noms as noms_tui
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.panneau import MENTION_MAJORANT, RIEN_ECRIT

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le module mesure, ce banc, et la fiche de story -- pour les frontieres.
SOURCE_DU_PRODUIT = (Path(_SRC) / "mixed_media_utility" / "tui"
                     / "atelier_pdf_confirmation.py")
SOURCE_DU_BANC = Path(__file__)
FICHE_DE_LA_STORY = (_RACINE / "_bmad-output" / "implementation-artifacts"
                     / "11-7-atelier-pdf.md")
MAQUETTE = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
            / "ux-tui-2026-08-27" / "maquettes" / "E5-3-pdf-confirmation.txt")


# ---------------------------------------------------------------------------
# Fabriques. Aucune ne produit un element unique, aucune ne remplit une
# collection d'une valeur uniforme.
# ---------------------------------------------------------------------------

PROJET = "projet_demo"
RUSH = "plan-04"

#: Les trois lots de la fabrique principale. **La cible est au MILIEU**, et les
#: trois se distinguent par leur identifiant, leur cardinal de frames, leurs
#: pages et leurs emplacements vides.
LOT_PREMIER = "plan-04_25"
LOT_CIBLE = "plan-04_12p5"
LOT_DERNIER = "plan-04_8"

#: Trois cardinaux de frames choisis pour que **pages et vides different tous
#: les trois** a 6 f/page : 124 -> 21 pages et 2 vides, 41 -> 7 pages et 1 vide,
#: 60 -> 10 pages et 0 vide. Une permutation de deux lots ne peut donc pas
#: passer inapercue, et un `break` sur le lot du milieu ferait disparaitre le
#: troisieme.
FRAMES_PREMIER = 124
FRAMES_CIBLE = 41
FRAMES_DERNIER = 60

#: Les deux lots de la MAQUETTE, qui n'est pas la fabrique nominale : c'est sur
#: eux que les chiffres verbatim de l'AC 6.2 et de l'AC 6.6 se mesurent.
FRAMES_MAQUETTE = (124, 40)

CARDINAL = 6
ORIENTATION = "paysage"
MARGE = page_templates.DEFAULT_MARGIN_PRESET

#: Un majorant de poids arbitraire. **Il est DONNE** : ce module ne pese rien,
#: et la valeur ne sert qu'a mesurer qu'elle est lue plutot que figee.
OCTETS = 470_000_000
AUTRES_OCTETS = 137_000_000


def mise_en_page(frames_par_lot, *, cardinal: int = CARDINAL,
                 orientation: str = ORIENTATION,
                 marge: str = MARGE) -> page_templates.MiseEnPageMesuree:
    """La mise en page **mesuree par le coeur**, jamais fabriquee a la main.

    C'est elle qui porte les pages par lot (AC 5.10) et le `template_id` qui
    nomme les fichiers : la fabriquer ici ferait mesurer le banc contre
    lui-meme.
    """
    return page_templates.bilan_de_domination(
        tuple(frames_par_lot), margin_preset=marge).de(orientation, cardinal)


def lots_a_trois(rangs=(None, None, None), tirages=(False, False, False),
                 scannes=(False, False, False)):
    """Les trois lots, **la cible au milieu**, chacun distinguable de ses voisins."""
    frames = (FRAMES_PREMIER, FRAMES_CIBLE, FRAMES_DERNIER)
    identifiants = (LOT_PREMIER, LOT_CIBLE, LOT_DERNIER)
    return [confirmation.LotAImprimer(lot_id=lot_id, rush_id=RUSH,
                                      frames=compte, rang=rang,
                                      tirage_anterieur=tirage, scanne=scanne)
            for lot_id, compte, rang, tirage, scanne
            in zip(identifiants, frames, rangs, tirages, scannes)]


def plan_a_trois(**reglages_du_plan) -> confirmation.PlanDesPlanches:
    """Le plan nominal : trois lots, la cible au milieu."""
    lots = reglages_du_plan.pop("lots", None) or lots_a_trois()
    return confirmation.preparer_le_plan(
        reglages_du_plan.pop("dossier_projet", Path("/tmp") / PROJET),
        project_id=PROJET,
        lots=lots,
        mise_en_page=reglages_du_plan.pop(
            "mise_en_page", mise_en_page([lot.frames for lot in lots])),
        marge=reglages_du_plan.pop("marge", MARGE),
        octets_majorants=reglages_du_plan.pop("octets_majorants", OCTETS))


def plan_de_la_maquette() -> confirmation.PlanDesPlanches:
    """Les deux lots de la maquette `E5-3`, avec son tirage sur le premier."""
    lots = [
        confirmation.LotAImprimer(LOT_PREMIER, RUSH, FRAMES_MAQUETTE[0],
                                  rang=4, tirage_anterieur=True),
        confirmation.LotAImprimer(LOT_DERNIER, RUSH, FRAMES_MAQUETTE[1]),
    ]
    return confirmation.preparer_le_plan(
        Path("/tmp") / PROJET, project_id=PROJET, lots=lots,
        mise_en_page=mise_en_page(FRAMES_MAQUETTE), marge=MARGE,
        octets_majorants=OCTETS)


def coque(ecran, ascii_seul: bool = False) -> CoqueTui:
    """Deux paliers temoins, puis l'ecran mesure au sommet."""
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=PROJET),
                    ascii_seul=ascii_seul)


def monter(banc, ecran, ascii_seul: bool = False):
    """Monter l'ecran au plancher et rendre ce que le test veut lire."""
    app = coque(ecran, ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        etat = jetons.texte_affiche(str(courant.query_one("#etat").content))
        raccourcis = jetons.texte_affiche(
            str(courant.query_one("#raccourcis").content))
        bandeau = jetons.texte_affiche(
            str(courant.query_one("#bandeau").content))
        blocs = [jetons.texte_affiche(str(widget.content))
                 for widget in courant.query_one("#centre").query("Static")]
        return courant, etat, raccourcis, bandeau, blocs

    return banc(app, scenario)


def _arbre_du_produit() -> ast.Module:
    return ast.parse(SOURCE_DU_PRODUIT.read_text(encoding="utf-8"))


# ===========================================================================
# Famille 0 -- la fabrique se mesure AVANT ce qu'elle sert
# ===========================================================================


def test_la_cible_est_au_MILIEU_de_la_liste_QUE_LE_CODE_PARCOURT():
    """Point 2 bis de `CLAUDE.md`, verifie sur `plan.planches`.

    Trois planches, la cible en **deuxieme** position : un `find` fautif qui
    rendrait toujours la premiere ne se demasque pas autrement, et une boucle
    qui s'arreterait au premier tour ferait disparaitre la troisieme.
    """
    parcourus = [planche.lot_id for planche in plan_a_trois().planches]
    assert parcourus == [LOT_PREMIER, LOT_CIBLE, LOT_DERNIER]
    assert parcourus.index(LOT_CIBLE) == 1
    assert len(parcourus) == 3


def test_les_trois_planches_sont_DISTINGUABLES_sur_QUATRE_axes():
    """Volet symetrique de la fabrique : trois valeurs uniformes ne mesureraient
    rien. Les pages, les frames, les vides **et** les noms different tous les
    trois -- une permutation de deux planches change donc quatre observables.
    """
    planches = plan_a_trois().planches
    for axe in ("pages", "frames", "vides", "nom"):
        valeurs = [getattr(planche, axe) for planche in planches]
        assert len(set(valeurs)) == 3, (axe, valeurs)


# ===========================================================================
# Famille 1 -- AC 6.2 : chaque ligne depuis sa source, aucune rederivation
# ===========================================================================


def test_les_pages_viennent_du_COEUR_lot_par_lot_et_JAMAIS_d_un_arrondi_refait():
    """AC 5.10 relaye par l'AC 6.2 : `MiseEnPageMesuree.pages_par_lot`.

    L'egalite porte sur la liste **entiere et dans l'ordre**, pas sur le total :
    deux totaux egaux peuvent recouvrir deux repartitions differentes, et c'est
    exactement l'appariement que ce module fait.
    """
    plan = plan_a_trois()
    mesure = mise_en_page([FRAMES_PREMIER, FRAMES_CIBLE, FRAMES_DERNIER])
    assert [planche.pages for planche in plan.planches] == list(
        mesure.pages_par_lot)
    assert plan.pages == mesure.pages


def test_la_CIBLE_recoit_SES_pages_et_non_celles_d_une_voisine():
    """L'appariement positionnel, mesure la ou il peut se rater.

    Le lot du milieu est confronte a la mesure que le coeur rend pour **son**
    cardinal seul. Un decalage d'un rang lui donnerait les pages du premier ou
    du dernier, et le total resterait juste : c'est le mutant `M33` de la 5.6
    et le `M25` de la 5.7, la meme classe de defaut pour la troisieme fois.
    """
    planche = plan_a_trois().planches[1]
    assert planche.lot_id == LOT_CIBLE
    seul = mise_en_page([FRAMES_CIBLE])
    assert planche.pages == seul.pages_par_lot[0]
    voisines = {mise_en_page([FRAMES_PREMIER]).pages_par_lot[0],
                mise_en_page([FRAMES_DERNIER]).pages_par_lot[0]}
    assert planche.pages not in voisines


def test_un_desaccord_de_CARDINAL_est_refuse_NOMMEMENT_et_jamais_tronque():
    """Le seul desaccord d'appariement qu'on puisse voir d'ici.

    Un `zip` silencieux laisserait tomber les lots en trop **sans un mot** :
    l'ecran annoncerait deux PDF pour trois lots coches. Le refus le rend
    impossible plutot qu'improbable, et il nomme les deux cardinaux.
    """
    lots = lots_a_trois()
    with pytest.raises(confirmation.PlanMalForme) as refus:
        confirmation.preparer_le_plan(
            Path("/tmp") / PROJET, project_id=PROJET, lots=lots,
            mise_en_page=mise_en_page([FRAMES_PREMIER, FRAMES_CIBLE]))
    assert "2" in str(refus.value) and "3" in str(refus.value)


def test_les_noms_sortent_de_build_sheets_pdf_filename_ET_DE_RIEN_D_AUTRE():
    """Ensemble **exact** des noms, confronte a la seule redaction du depot.

    L'assertion est une egalite de tuple, pas une inclusion : « ces noms sont
    presents » laisserait passer un nom de plus.
    """
    plan = plan_de_la_maquette()
    gabarit = mise_en_page(FRAMES_MAQUETTE).template_id
    attendus = (
        naming.build_sheets_pdf_filename(PROJET, RUSH, LOT_PREMIER,
                                         version_rank=4,
                                         template_id=gabarit),
        naming.build_sheets_pdf_filename(PROJET, RUSH, LOT_DERNIER,
                                         version_rank=None,
                                         template_id=gabarit),
    )
    assert plan.noms == attendus
    assert len(set(plan.noms)) == 2


def test_le_nom_suit_le_GABARIT_qui_a_produit_les_pages():
    """Changer la mise en page change le nom, et il n'y a pas de second calcul.

    Deux mises en page du meme lot rendaient le meme nom avant `EPIC11-ARB-171`,
    ce qui rendait le motif d'un conflit opaque. Le banc mesure les deux formes
    **differentes** et le gabarit lu de la mesure, jamais recompose.
    """
    lots = [confirmation.LotAImprimer(LOT_CIBLE, RUSH, FRAMES_CIBLE)]
    paysage = confirmation.preparer_le_plan(
        None, project_id=PROJET, lots=lots,
        mise_en_page=mise_en_page([FRAMES_CIBLE], cardinal=6,
                                  orientation="paysage"))
    portrait = confirmation.preparer_le_plan(
        None, project_id=PROJET, lots=lots,
        mise_en_page=mise_en_page([FRAMES_CIBLE], cardinal=4,
                                  orientation="portrait"))
    assert paysage.noms != portrait.noms
    assert len(set(paysage.noms) | set(portrait.noms)) == 2


def test_le_tirage_TRAVERSE_verbatim_jusqu_au_nom_et_n_est_JAMAIS_interprete():
    """`EPIC11-ARB-92`, mesure a l'AST plutot qu'au texte.

    Ce qui compte n'est pas qu'un mot soit absent -- la frontiere de la 11.6 le
    mesure deja sur le paquet entier -- mais que l'argument nomme du
    constructeur de nom soit **l'attribut du lot** et rien d'autre : ni une
    comparaison, ni un repli, ni une arithmetique. Une expression a cet endroit
    serait une regle de tirage ecrite dans la TUI, c'est-a-dire une seconde
    regle qui divergerait de celle du coeur.
    """
    passages = [ast.dump(mot.value)
                for noeud in ast.walk(_arbre_du_produit())
                if isinstance(noeud, ast.Call)
                for mot in noeud.keywords if mot.arg == "version_rank"]
    assert passages == [ast.dump(ast.parse("lot.rang", mode="eval").body)]


def test_le_tirage_d_ORIGINE_ne_porte_aucun_fragment_et_l_autre_en_porte_un():
    """La frontiere et son volet symetrique, sur le meme lot.

    Le nom est le seul endroit ou le tirage se relit apres coup, sur le disque
    (retour d'Egan du 2026-09-02) : deux tirages du meme lot doivent donc rendre
    deux noms differents, et celui de l'origine doit etre exactement celui que
    `io.naming` rend sans tirage.
    """
    gabarit = mise_en_page([FRAMES_CIBLE]).template_id
    origine = confirmation.preparer_le_plan(
        None, project_id=PROJET,
        lots=[confirmation.LotAImprimer(LOT_CIBLE, RUSH, FRAMES_CIBLE)],
        mise_en_page=mise_en_page([FRAMES_CIBLE]))
    suivant = confirmation.preparer_le_plan(
        None, project_id=PROJET,
        lots=[confirmation.LotAImprimer(LOT_CIBLE, RUSH, FRAMES_CIBLE, rang=4)],
        mise_en_page=mise_en_page([FRAMES_CIBLE]))
    assert origine.noms[0] == naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT_CIBLE, version_rank=None, template_id=gabarit)
    assert suivant.noms[0] != origine.noms[0]
    assert suivant.noms[0].startswith(origine.noms[0].removesuffix(".pdf"))


def test_le_FORMAT_et_le_DPI_sont_lus_des_constantes_du_COEUR():
    """La ligne de mise en page ne recopie aucun nombre.

    Un `A4` ou un `600` ecrits ici seraient une seconde redaction de ce que
    `page_templates` et `pdf_composition` posent deja, et que l'ecran de
    reglages lit deja de la meme facon.
    """
    ligne = confirmation.ligne_de_la_mise_en_page(plan_de_la_maquette())
    assert page_templates.DEFAULT_PAGE_FORMAT in ligne.chiffre
    assert str(pdf_composition.RENDER_DPI_DEFAULT) in ligne.chiffre
    # La mesure porte sur les chaines que le CODE compose, docstrings exclus :
    # une prose qui cite la maquette (`A4 · 600 dpi`) ne recopie rien, alors
    # qu'un litteral au milieu d'une `f`-chaine, si. C'est la lecon du finding
    # `I3` -- un grep de texte confond les deux et se fait affaiblir.
    litteraux = "".join(chaines_de_code(SOURCE_DU_PRODUIT))
    for interdit in (page_templates.DEFAULT_PAGE_FORMAT,
                     str(pdf_composition.RENDER_DPI_DEFAULT)):
        assert interdit not in litteraux, interdit


def test_la_ligne_de_MISE_EN_PAGE_est_celle_de_la_maquette_VERBATIM():
    """`6 f/page · paysage · A4 · 600 dpi · marge 0` (AC 6.2, mesure attendue)."""
    ligne = confirmation.ligne_de_la_mise_en_page(plan_de_la_maquette())
    assert ligne.libelle == confirmation.LIBELLE_MISE_EN_PAGE
    assert ligne.chiffre == "6 f/page · paysage · A4 · 600 dpi · marge 0"


def test_la_ligne_des_PLANCHES_est_celle_de_la_maquette_VERBATIM():
    """`2 PDF · 28 pages` (AC 6.2, mesure attendue)."""
    ligne = confirmation.ligne_des_planches(plan_de_la_maquette())
    assert ligne.libelle == confirmation.LIBELLE_PLANCHES
    assert ligne.chiffre == "2 PDF · 28 pages"


def test_la_marge_porte_le_MOT_d_ARB_34_et_pas_celui_que_l_arbitrage_ecarte():
    """`EPIC11-ARB-34` : « Marge de travail », au panneau de confirmation aussi.

    Le libelle plein vit a l'ecran de reglages ; ici la mention est en **tete
    d'une mesure** et non en tete d'une ligne, donc elle est reduite. Ce que
    l'arbitrage impose est le MOT, et ce test mesure que les deux redactions ne
    peuvent pas diverger : celle des reglages commence par celle-ci.

    Le volet negatif porte sur le paquet, prose comprise (AC 11.3).
    """
    assert reglages.LIBELLE_MARGE.lower().startswith(
        confirmation.MENTION_DE_LA_MARGE)
    assert "recadrage" not in SOURCE_DU_PRODUIT.read_text(
        encoding="utf-8").lower()
    # Volet symetrique : le detecteur mord bien -- il attrape le mot la ou il
    # est ecrit, c'est-a-dire dans la ligne ci-dessus.
    assert "recadrage" in SOURCE_DU_BANC.read_text(encoding="utf-8").lower()


def test_la_DESTINATION_se_lit_du_dossier_de_projet_et_disparait_sans_lui():
    """`projet_demo/planches/`, et rien quand aucun projet n'est ouvert.

    Un chemin devine serait pire qu'une ligne absente : c'est la seule chose qui
    dit ou l'operateur ira chercher ses fichiers.
    """
    plan = plan_de_la_maquette()
    assert plan.destination == f"{PROJET}/{PLANCHES_DIRNAME}/"
    assert confirmation.ligne_de_la_destination(plan) is not None
    sans_projet = plan_a_trois(dossier_projet=None)
    assert sans_projet.destination == ""
    assert confirmation.ligne_de_la_destination(sans_projet) is None


# ===========================================================================
# Famille 2 -- la TAILLE est un ordre de grandeur, jamais une promesse
# ===========================================================================


def test_la_taille_est_un_MAJORANT_annonce_comme_tel_sur_DEUX_canaux():
    """`~ 470 Mo   (majorant)` : le prefixe ET la mention.

    Un seul des deux canaux suffirait a se perdre -- `~` se lit mal en repli
    ASCII, `(majorant)` seul ne dit pas que le chiffre est arrondi. La mention
    est posee par `LigneChiffree` elle-meme, jamais ecrite ici.
    """
    ligne = confirmation.ligne_de_la_taille(plan_de_la_maquette())
    assert ligne.majorant is True
    assert ligne.chiffre.startswith("~ ")
    assert ligne.chiffre.endswith(MENTION_MAJORANT)


def test_la_taille_est_LUE_du_plan_et_non_FIGEE():
    """Deux majorants differents rendent deux lignes differentes.

    C'est ce qui distingue une valeur lue d'un chiffre de maquette recopie : un
    `470` ecrit dans le module rendrait la meme ligne pour les deux plans.
    """
    premier = confirmation.ligne_de_la_taille(
        plan_a_trois(octets_majorants=OCTETS))
    second = confirmation.ligne_de_la_taille(
        plan_a_trois(octets_majorants=AUTRES_OCTETS))
    assert premier.chiffre != second.chiffre
    litteraux = "".join(chaines_de_code(SOURCE_DU_PRODUIT))
    for chiffre in (str(OCTETS), str(AUTRES_OCTETS)):
        assert chiffre not in litteraux, chiffre


def test_un_poids_INCONNU_fait_disparaitre_la_ligne_plutot_que_de_dire_ZERO():
    """Annoncer `0 Mo` serait affirmer qu'on a pese.

    La ligne d'etat le perd aussi, et pour la meme raison -- mais elle garde sa
    queue, qui est la seule chose que cet ecran doit dire quoi qu'il arrive.
    """
    plan = plan_a_trois(octets_majorants=None)
    assert confirmation.ligne_de_la_taille(plan) is None
    libelles = [ligne.libelle for ligne in confirmation.lignes_du_cartouche(plan)]
    assert confirmation.LIBELLE_TAILLE not in libelles
    mesure = confirmation.mesure_de_la_confirmation(plan)
    assert "~" not in mesure
    assert mesure.endswith(confirmation.QUEUE_RIEN_ECRIT)


# ===========================================================================
# Famille 3 -- AC 6.6 : la derniere page partiellement remplie
# ===========================================================================


def test_la_REPARTITION_des_vides_est_celle_de_la_maquette_et_non_leur_total():
    """AC 6.6, sur les chiffres refaits de la maquette d'aujourd'hui.

    A 6 f/page, `164` frames sur `168` emplacements recouvrent `124 = 20x6 + 4`
    (21 pages) et `40 = 6x6 + 4` (7 pages) : les quatre vides sont **deux dans
    chacun** des deux PDF, pas quatre dans un seul. Un total juste avec une
    repartition fausse est le defaut exact que cette AC existe pour attraper,
    et c'est pourquoi le tuple est mesure avant le total.
    """
    plan = plan_de_la_maquette()
    assert plan.vides_par_planche == (2, 2)
    assert plan.vides == 4
    assert plan.emplacements == 168
    assert plan.frames == 164


def test_un_TOTAL_juste_avec_une_repartition_FAUSSE_est_attrape():
    """Le volet qui rend le test precedent autre chose qu'une coincidence.

    Quatre vides tombant tous dans un seul PDF donnent le meme total et une
    repartition differente. L'operateur qui va imprimer n'a pas la meme feuille
    a jeter dans les deux cas, et la ligne du cartouche ne dit donc pas la meme
    chose.
    """
    frames = (5 * CARDINAL, 3 * CARDINAL - 4)
    lots = [confirmation.LotAImprimer(LOT_PREMIER, RUSH, frames[0]),
            confirmation.LotAImprimer(LOT_DERNIER, RUSH, frames[1])]
    plan = confirmation.preparer_le_plan(
        None, project_id=PROJET, lots=lots,
        mise_en_page=mise_en_page(frames))
    assert plan.vides == 4
    assert plan.vides_par_planche == (0, 4)
    assert (confirmation.ligne_des_emplacements(plan).chiffre
            != confirmation.ligne_des_emplacements(
                plan_de_la_maquette()).chiffre)


def test_la_ligne_des_emplacements_dit_le_PDF_ou_les_vides_TOMBENT():
    """Trois planches, la cible au milieu, trois comptes de vides distincts.

    La repartition se lit dans l'ordre des planches, c'est-a-dire dans celui de
    la liste plate des noms juste en dessous. Une somme `2 + 1 + 0` ne se
    confond avec aucune de ses permutations.
    """
    plan = plan_a_trois()
    assert plan.vides_par_planche == (2, 1, 0)
    assert confirmation.ligne_des_emplacements(plan).chiffre == (
        "228 emplacements · 3 vides (2 + 1 + 0)")


def test_une_passe_qui_remplit_EXACTEMENT_n_affiche_aucune_ligne_de_vides():
    """Zero vide ne s'ecrit pas `0 vide` : ce serait du bruit sur le nominal.

    Frontiere negative avec son volet symetrique -- la meme fabrique, un lot
    incomplet, fait reapparaitre la ligne.
    """
    pleines = (4 * CARDINAL, 2 * CARDINAL)
    lots = [confirmation.LotAImprimer(LOT_PREMIER, RUSH, pleines[0]),
            confirmation.LotAImprimer(LOT_DERNIER, RUSH, pleines[1])]
    plan = confirmation.preparer_le_plan(
        None, project_id=PROJET, lots=lots, mise_en_page=mise_en_page(pleines))
    assert plan.vides == 0
    assert confirmation.ligne_des_emplacements(plan) is None
    assert confirmation.LIBELLE_EMPLACEMENTS not in [
        ligne.libelle for ligne in confirmation.lignes_du_cartouche(plan)]
    assert confirmation.ligne_des_emplacements(plan_de_la_maquette()) is not None


# ===========================================================================
# Famille 4 -- le cartouche, en ensemble EXACT
# ===========================================================================


def test_l_ensemble_EXACT_des_libelles_du_cartouche():
    """Cinq lignes quand une derniere page est partielle, quatre sinon.

    L'egalite est une **liste ordonnee** et non un ensemble : l'ordre du
    cartouche est celui de la maquette -- ce qui sera produit, ce que cela
    remplit, ce que cela coute, ou ca va --, et une ligne qui remonterait
    changerait la lecture sans rien casser d'autre.
    """
    avec_vides = [ligne.libelle
                  for ligne in confirmation.lignes_du_cartouche(
                      plan_de_la_maquette())]
    assert avec_vides == [
        confirmation.LIBELLE_PLANCHES,
        confirmation.LIBELLE_EMPLACEMENTS,
        confirmation.LIBELLE_MISE_EN_PAGE,
        confirmation.LIBELLE_TAILLE,
        "Destination",
    ]


def test_la_liste_des_noms_est_PLATE_une_ligne_par_PDF_et_rien_d_autre():
    """Le retour d'Egan du 2026-09-02, mesure plutot que declare.

    Verbatim : « mets juste la liste de toutes les planches produites. Ne
    regroupe pas par lot et tirage, c'est trop lourd a lire. » La mesure qui
    l'exprime : **autant de lignes que de PDF**, chacune portant un nom de
    fichier et rien de plus -- pas une ligne de lot par-dessus, pas une colonne
    de tirage a cote.
    """
    plan = plan_a_trois()
    lignes = confirmation.noms_des_planches(plan, 80)
    assert len(lignes) == plan.pdf == 3
    for ligne, nom in zip(lignes, plan.noms):
        assert ligne.strip() == nom
        assert ligne.endswith(".pdf")
        assert "·" not in ligne


def test_AUCUN_terme_de_METHODE_n_atteint_l_ecran():
    """`EPIC11-ARB-28` : les termes des documents de decision ne s'affichent pas.

    Les deux phrases qu'Egan a fait retirer de la maquette -- « lot par lot, le
    rang se compte par lot » et celle qui disait que l'origine n'ecrit aucun
    fragment -- sont de la **tuyauterie interne**. Ce test les compte a zero sur
    tout ce que l'ecran rend : cartouche, noms, issues, ligne d'etat, bandeau.

    Il porte sur le **texte rendu** et non sur la source, parce que c'est le
    texte rendu qu'un operateur lit. Le volet symetrique est le test suivant :
    ce que ces phrases disaient reste **visible**, par le dessin.
    """
    plan = plan_de_la_maquette()
    rendu = " ".join([
        *(ligne.rendu(80) for ligne in confirmation.lignes_du_cartouche(plan)),
        *confirmation.noms_des_planches(plan, 80),
        *confirmation.issues_de_la_confirmation(plan).rendu(),
        confirmation.mesure_de_la_confirmation(plan),
        confirmation.bandeau_du_plan(plan),
    ]).lower()
    for terme in ("lot par lot", "se compte par", "origine", "antérieur",
                  "anterieur", "tirage"):
        assert terme not in rendu, terme


def test_ce_que_ces_phrases_disaient_reste_VISIBLE_par_le_dessin():
    """Volet symetrique : retirer la prose ne retire pas l'information.

    Le fait que le tirage se compte par lot se lit dans la liste plate elle-meme
    -- deux lots de la meme passe rendent deux noms dont un seul porte un
    fragment de version --, et c'est le seul endroit ou il se relira apres coup,
    sur le disque.
    """
    noms = plan_de_la_maquette().noms
    sans_extension = [nom.removesuffix(".pdf") for nom in noms]
    assert sans_extension[0] != sans_extension[1]
    assert len(sans_extension[0]) > len(sans_extension[1].rsplit("_", 0)[0]) - 1
    # Le premier lot, qui avait des tirages, porte quelque chose que le second
    # n'a pas ; le second, qui part a l'origine, ne porte rien de plus.
    assert sans_extension[1] == naming.build_sheets_pdf_filename(
        PROJET, RUSH, LOT_DERNIER, version_rank=None,
        template_id=mise_en_page(FRAMES_MAQUETTE).template_id
    ).removesuffix(".pdf")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_un_nom_TROP_LONG_est_abrege_AU_MILIEU_et_garde_sa_queue(ascii_seul):
    """Un nom coupe par la fin perdrait ce qui distingue deux tirages du meme lot.

    L'abregement passe par `jetons.abreger_nom`, la seule redaction du depot :
    en recopier une seconde ferait deux abregements differents sur le meme
    ecran, defaut sanctionne par la revue de vague 2 bis.
    """
    lot = "l" * 90
    plan = confirmation.preparer_le_plan(
        None, project_id=PROJET,
        lots=[confirmation.LotAImprimer(lot, RUSH, FRAMES_CIBLE),
              confirmation.LotAImprimer(LOT_CIBLE, RUSH, FRAMES_CIBLE)],
        mise_en_page=mise_en_page([FRAMES_CIBLE, FRAMES_CIBLE]))
    largeur = 80
    budget = jetons.largeur_de_cartouche(largeur) - len(
        confirmation.INDENT_DES_NOMS)
    ligne = confirmation.noms_des_planches(plan, largeur, ascii_seul)[0]
    assert jetons.colonnes(ligne.strip()) <= budget
    assert ligne.strip().endswith(".pdf")
    assert ligne.strip() == jetons.abreger_nom(plan.noms[0], budget, ascii_seul)


# ===========================================================================
# Famille 5 -- les issues : la fleche ne vise JAMAIS l'ecriture
# ===========================================================================


def test_l_ensemble_EXACT_des_trois_issues():
    """Cles et libelles, dans l'ordre de la deliberation.

    « Ces trois issues sont presentes » laisserait passer une quatrieme ; c'est
    une egalite de liste.
    """
    choix = confirmation.issues_de_la_confirmation(plan_de_la_maquette())
    assert [issue.cle for issue in choix.issues] == [
        confirmation.ISSUE_GENERER,
        confirmation.ISSUE_MODIFIER,
        confirmation.ISSUE_ANNULER,
    ]
    assert [issue.libelle for issue in choix.issues] == [
        confirmation.LIBELLE_GENERER,
        confirmation.LIBELLE_MODIFIER,
        confirmation.LIBELLE_ANNULER,
    ]


def test_la_fleche_se_pose_sur_MODIFIER_au_montage_et_JAMAIS_sur_GENERER():
    """On ne declenche pas une ecriture par reflexe.

    C'est une **assertion** de position attendue, pas la relecture d'un effet de
    bord : le test nomme l'issue sur laquelle le curseur doit etre. Depuis
    `EPIC11-ARB-45` la validation retient en un seul geste, donc une fleche
    posee sur « Générer » rendrait l'ecriture atteignable en UNE frappe.
    """
    choix = confirmation.issues_de_la_confirmation(plan_de_la_maquette())
    assert choix.issues[choix.curseur].cle == confirmation.ISSUE_MODIFIER
    assert choix.retenue is None


def test_la_fleche_est_posee_par_ChoixExclusif_APPELE_et_non_REECRIT():
    """`panneau.ChoixExclusif.__post_init__` fait le travail ; on l'appelle.

    Mesure a l'AST : le module construit un `ChoixExclusif` et n'ecrit jamais
    dans `curseur` ni dans `retenue`. Reecrire la regle ici en ferait une
    seconde, qui divergerait de celle du panneau au premier ajustement -- et
    c'est cette regle-la qui empeche l'ecriture en une frappe sur les quatre
    ateliers a la fois.
    """
    arbre = _arbre_du_produit()
    construit = [noeud for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Call)
                 and isinstance(noeud.func, ast.Name)
                 and noeud.func.id == "ChoixExclusif"]
    assert len(construit) == 1
    ecritures = [cible.attr for noeud in ast.walk(arbre)
                 if isinstance(noeud, (ast.Assign, ast.AugAssign))
                 for cible in (noeud.targets if isinstance(noeud, ast.Assign)
                               else [noeud.target])
                 if isinstance(cible, ast.Attribute)]
    assert "curseur" not in ecritures
    assert "retenue" not in ecritures


def test_une_SEULE_issue_ecrit_et_il_en_reste_qui_n_ecrivent_pas():
    """Un point de jugement dont toutes les issues ecrivent est un couloir."""
    choix = confirmation.issues_de_la_confirmation(plan_de_la_maquette())
    assert [issue.cle for issue in choix.issues if issue.ecrit] == [
        confirmation.ISSUE_GENERER]
    assert choix.action_qui_ecrit.cle == confirmation.ISSUE_GENERER
    assert choix.sortie_sans_ecriture.cle == confirmation.ISSUE_MODIFIER


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_rendu_des_issues_porte_la_FLECHE_SEULE_une_ligne_par_issue(ascii_seul):
    """`EPIC11-ARB-126` : « Flèche seule ! C'est uniquement dans les listes à
    cocher qu'on trouve les deux. » Aucune case, aucune puce, aucune lettre.
    """
    lignes = confirmation.issues_de_la_confirmation(
        plan_de_la_maquette()).rendu(ascii_seul)
    assert len(lignes) == 3
    curseur = jetons.glyphes(ascii_seul)["curseur"]
    assert [ligne for ligne in lignes if ligne.startswith(curseur)] == [
        f"{curseur} {confirmation.LIBELLE_MODIFIER}"]
    for ligne in lignes:
        for interdit in ("( )", "(•)", "[ ]", "[x]"):
            assert interdit not in ligne


# ===========================================================================
# Famille 6 -- AC 6.3 : aucun champ de nom, et une ligne de raccourcis propre
# ===========================================================================


def test_AUCUN_nom_n_est_editable_et_Tab_est_inerte_DE_LUI_MEME():
    """`EPIC11-ARB-141` : les noms sont derives et montres, jamais saisis.

    Le modele d'edition est **vide**, donc `EcranChiffre.traiter` rend `Tab`
    inerte sans qu'aucune garde soit ajoutee ici : c'est une consequence de ne
    pas donner de noms editables, pas un `if` de plus.
    """
    ecran = confirmation.EcranPdfConfirmation(plan_de_la_maquette())
    assert len(ecran.noms) == 0
    assert ecran.noms.en_edition is False
    assert ecran.traiter("tab") is False


def test_la_ligne_de_raccourcis_n_annonce_PAS_Tab_et_la_partagee_SI():
    """AC 6.3a, frontiere negative **avec son volet symetrique**.

    Annoncer une touche qui ne fait rien est le defaut que `coque.py:510`
    documente. Le volet symetrique mesure que la constante partagee porte
    toujours `Tab` : sans lui, une constante renommee rendrait ce test vert
    pour la mauvaise raison.
    """
    assert "Tab" not in confirmation.RACCOURCIS_PDF_CONFIRMATION
    assert "Tab" in execution.RACCOURCIS_CONFIRMATION
    assert (confirmation.RACCOURCIS_PDF_CONFIRMATION
            != execution.RACCOURCIS_CONFIRMATION)


def test_la_ligne_de_raccourcis_est_celle_de_la_MAQUETTE_verbatim():
    """`⏎ valider  ↑↓ choisir  Échap retour  F1 aide` (l. 23)."""
    assert (confirmation.RACCOURCIS_PDF_CONFIRMATION
            == "⏎ valider  ↑↓ choisir  Échap retour  F1 aide")
    assert confirmation.RACCOURCIS_PDF_CONFIRMATION in MAQUETTE.read_text(
        encoding="utf-8")


def test_les_ecrans_de_JUGEMENT_de_l_atelier_annoncent_les_MEMES_touches():
    """Deux confirmations du meme atelier qui divergeraient sont un defaut.

    C'est exactement ce qu'une revue par vague existe pour trouver, et ce qu'une
    revue par story ne peut structurellement pas voir : `E5-3`, `E5-3b` / `E5-3c`
    et le jugement de la mire sont trois ecrans de trois lots differents.
    """
    assert (confirmation.RACCOURCIS_PDF_CONFIRMATION
            == versions.RACCOURCIS_DU_CONFLIT
            == mire.RACCOURCIS_MIRE_JUGEMENT)


def test_raccourcis_est_un_ATTRIBUT_DE_CLASSE_et_jamais_une_property():
    """La garde de paquet lit `classe.raccourcis` au niveau de la CLASSE.

    Une `@property` y rendrait un objet `property` et ferait echapper l'ecran a
    la mesure du repli ASCII -- meme forme, et meme motif, que les dix ecrans
    `atelier_scan_*`.
    """
    brut = confirmation.EcranPdfConfirmation.__dict__["raccourcis"]
    assert isinstance(brut, str)
    assert not isinstance(brut, property)
    assert brut == confirmation.RACCOURCIS_PDF_CONFIRMATION


def test_la_BORNE_des_noms_est_celle_du_COEUR_sans_que_sa_valeur_soit_ECRITE():
    """AC 6.4 : `noms.LIMITE` **est** `io.naming.CANONICAL_ID_MAX_LENGTH`.

    L'egalite se mesure sans asserter la valeur -- c'est la frontiere qui
    interdit a la TUI de recopier un nombre --, et le volet negatif compte a
    zero l'ecriture de ce nombre dans le module comme dans ce banc.
    """
    assert noms_tui.LIMITE == naming.CANONICAL_ID_MAX_LENGTH
    borne = str(naming.CANONICAL_ID_MAX_LENGTH)
    for source in (SOURCE_DU_PRODUIT, SOURCE_DU_BANC):
        assert borne not in source.read_text(encoding="utf-8")


# ===========================================================================
# Famille 7 -- la ligne d'etat : le DERNIER ecran ou rien n'est ecrit
# ===========================================================================


def test_la_ligne_d_etat_porte_les_chiffres_de_ce_qui_VA_s_ecrire():
    """`2 PDF · 28 pages · ~ 470 Mo — rien n'a encore été écrit` (l. 22)."""
    mesure = confirmation.mesure_de_la_confirmation(plan_de_la_maquette())
    assert mesure.startswith("2 PDF · 28 pages · ~ ")
    assert mesure.endswith(
        confirmation.LIAISON_DE_LA_MESURE + confirmation.QUEUE_RIEN_ECRIT)


def test_la_queue_est_DERIVEE_de_RIEN_ECRIT_et_jamais_recopiee():
    """Une seconde redaction divergerait au premier ajustement d'accent.

    Et une phrase desaccentuee a la source rendrait le repli ASCII
    indistinguable du nominal : c'est le finding `I6`, paye une fois.
    """
    assert confirmation.QUEUE_RIEN_ECRIT == (
        RIEN_ECRIT[0].lower() + RIEN_ECRIT[1:].rstrip("."))
    assert confirmation.QUEUE_RIEN_ECRIT in RIEN_ECRIT.lower()
    assert "é" in confirmation.QUEUE_RIEN_ECRIT


def test_la_ligne_d_etat_est_LUE_du_plan_et_change_avec_lui():
    """Trois plans, trois lignes d'etat : le figement se verrait ici."""
    lignes = {confirmation.mesure_de_la_confirmation(plan)
              for plan in (plan_de_la_maquette(), plan_a_trois(),
                           plan_a_trois(octets_majorants=AUTRES_OCTETS))}
    assert len(lignes) == 3


def test_ECART_EPINGLE_la_ligne_d_etat_PARTAGEE_ne_porte_aucun_recapitulatif():
    """**Un constat, pas une correction** -- et c'est le meme que le lot H.

    `EcranChiffre.etat` rend `panneau.RIEN_ECRIT` **seul**, alors que toutes les
    maquettes de confirmation prefixent un recapitulatif chiffre. `execution.py`
    est partage par les quatre ateliers : le corriger depuis un lot d'ecran
    ferait bouger un observable pour tout le monde, donc l'ecart est **epingle**
    plutot que tu, et `E5-3` s'en sort en surchargeant `etat`.

    Les deux moities se mesurent : la base rend la phrase nue, la surcharge rend
    la mesure. Le jour ou la base sera corrigee, ce test rougira -- et c'est ce
    qu'on lui demande.
    """
    assert execution.EcranChiffre.etat is not \
        confirmation.EcranPdfConfirmation.etat
    plan = plan_de_la_maquette()
    ecran = confirmation.EcranPdfConfirmation(plan)
    assert execution.EcranChiffre.etat(ecran) == RIEN_ECRIT
    assert ecran.etat() == confirmation.mesure_de_la_confirmation(plan)
    assert ecran.etat() != RIEN_ECRIT


def test_ECART_EPINGLE_les_valeurs_du_cartouche_sont_calees_a_DROITE():
    """**Un constat, pas une correction** -- l'ecart de tous les `E*-3`.

    Les cartouches des maquettes calent les valeurs a **gauche**, a une colonne
    fixe ; `panneau.LigneChiffree.rendu` cale le chiffre a **droite** de la
    largeur utile. `panneau.py` est le modele partage par les quatre ateliers,
    et le corriger d'ici deplacerait toutes les valeurs de tous les panneaux du
    depot.

    La mesure : sur deux lignes de libelles de longueurs differentes, les
    valeurs commencent a des colonnes differentes -- alors que la maquette les
    aligne. Le jour ou l'alignement sera repris, ce test rougira.
    """
    lignes = confirmation.lignes_du_cartouche(plan_de_la_maquette())
    debuts = {ligne.rendu(80).index(ligne.chiffre.split(" ")[0])
              for ligne in lignes[:2]}
    assert len(debuts) == 2, debuts
    fins = {len(ligne.rendu(80).rstrip()) for ligne in lignes[:2]}
    assert len(fins) == 1, fins


# ===========================================================================
# Famille 8 -- AC 6.7 : RIEN n'est ecrit, mesure aux INODES et par un TEMOIN
# ===========================================================================


def _empreintes(racine: Path) -> dict[str, tuple[int, int, int]]:
    """Inode, `st_mtime_ns` et taille de tout ce qui vit sous la racine.

    **Jamais un condensat** : la fixture est deterministe, donc une reecriture
    rendrait exactement les memes octets et le condensat serait vert sur une
    ecriture reelle. C'est le defaut mesure le 2026-08-30 sur `EPIC11-ARB-83`.
    """
    empreintes = {}
    for chemin in sorted(racine.rglob("*")):
        etat = chemin.stat()
        empreintes[str(chemin.relative_to(racine))] = (
            etat.st_ino, etat.st_mtime_ns, etat.st_size)
    return empreintes


@pytest.fixture
def projet_temoin(tmp_path: Path) -> Path:
    """Un projet avec un `planches/` deja peuple, et un temoin dedans."""
    racine = tmp_path / PROJET
    patches = racine / PLANCHES_DIRNAME
    patches.mkdir(parents=True)
    (patches / "deja_la.pdf").write_bytes(b"un tirage anterieur")
    (patches / "TEMOIN").write_text("temoin", encoding="utf-8")
    return racine


def test_RIEN_n_est_ecrit_TANT_QUE_l_issue_n_est_pas_validee(projet_temoin):
    """AC 6.7 : inodes, `st_mtime_ns`, et un temoin depose dans `planches/`.

    Le parcours mesure est celui d'un operateur : construire le plan, dessiner
    le cartouche et la liste des noms, deplacer la fleche, et valider **chacune**
    des trois issues -- y compris celle qui ecrit, puisque c'est l'appelant qui
    ecrira, jamais cet ecran.
    """
    avant = _empreintes(projet_temoin)
    assert avant, "la fixture doit porter des fichiers, sinon rien n'est mesure"

    lots = lots_a_trois()
    plan = confirmation.preparer_le_plan(
        projet_temoin, project_id=PROJET, lots=lots,
        mise_en_page=mise_en_page([lot.frames for lot in lots]),
        octets_majorants=OCTETS)
    confirmation.panneau_de_la_confirmation(plan, 80)
    confirmation.mesure_de_la_confirmation(plan)
    confirmation.bandeau_du_plan(plan)
    ecran = confirmation.EcranPdfConfirmation(plan)
    for cle in (confirmation.ISSUE_GENERER, confirmation.ISSUE_MODIFIER,
                confirmation.ISSUE_ANNULER):
        ecran.choix.viser(cle)
        ecran.choix.valider()

    assert _empreintes(projet_temoin) == avant
    assert (projet_temoin / PLANCHES_DIRNAME / "TEMOIN").read_text(
        encoding="utf-8") == "temoin"
    ecrits = {chemin.name for chemin in
              (projet_temoin / PLANCHES_DIRNAME).iterdir()}
    assert ecrits == {"deja_la.pdf", "TEMOIN"}
    assert not set(plan.noms) & ecrits


def test_le_module_n_a_AUCUN_chemin_vers_le_disque():
    """Frontiere negative **avec son volet symetrique**.

    Ni ecriture, ni lecture : un `open`, un `write_text`, un `mkdir` ou un
    `rglob` dans ce module serait un chemin vers le disque sur un ecran qui
    promet de n'en avoir aucun. Le volet symetrique verifie que le detecteur
    mord bien -- il attrape ces memes appels dans un module qui en porte.
    """
    interdits = {"open", "write_text", "write_bytes", "mkdir", "unlink",
                 "rglob", "iterdir", "read_text", "read_bytes"}
    appeles = {noeud.func.attr if isinstance(noeud.func, ast.Attribute)
               else getattr(noeud.func, "id", "")
               for noeud in ast.walk(_arbre_du_produit())
               if isinstance(noeud, ast.Call)}
    assert not (appeles & interdits), sorted(appeles & interdits)
    # Volet symetrique : le detecteur mord sur un module qui, lui, lit le disque.
    temoin = ast.parse(SOURCE_DU_BANC.read_text(encoding="utf-8"))
    du_banc = {noeud.func.attr if isinstance(noeud.func, ast.Attribute)
               else getattr(noeud.func, "id", "")
               for noeud in ast.walk(temoin) if isinstance(noeud, ast.Call)}
    assert du_banc & interdits


# ===========================================================================
# Famille 9 -- AC 6.8 : l'ordre des ecrans, en ensemble EXACT
# ===========================================================================


def test_sans_aucun_tirage_anterieur_l_ensemble_EXACT_est_la_CONFIRMATION_SEULE():
    """`EPIC11-ARB-172` : l'ecran de conflit ne se monte pas pour rien.

    Trois lots, aucun tirage : l'ensemble est **exactement** `{E5-3}`, et le
    tuple aussi -- une egalite d'ensemble seule laisserait passer un doublon.
    """
    enchainement = confirmation.ecrans_du_parcours(lots_a_trois())
    assert enchainement == (confirmation.ECRAN_DE_LA_CONFIRMATION,)
    assert set(enchainement) == {confirmation.ECRAN_DE_LA_CONFIRMATION}


def test_un_tirage_sur_le_lot_du_MILIEU_insere_le_conflit_AVANT_la_confirmation():
    """La cible au milieu, et la boucle qui va jusqu'au bout.

    Un `break` sur le premier lot en conflit ferait disparaitre les suivants ;
    une cible en premiere ou en derniere position ne saurait pas le dire. Ici le
    lot du milieu et le dernier sont en conflit : deux ecrans de conflit, puis la
    confirmation.
    """
    lots = lots_a_trois(rangs=(None, 4, 2),
                        tirages=(False, True, True))
    assert confirmation.ecrans_du_parcours(lots) == (
        confirmation.ECRAN_DU_CONFLIT,
        confirmation.ECRAN_DU_CONFLIT,
        confirmation.ECRAN_DE_LA_CONFIRMATION,
    )


def test_un_tirage_SCANNE_monte_l_autre_ecran_et_l_ensemble_reste_EXACT():
    """`EPIC11-ARB-176` : un tirage scanne ne peut plus etre ecrase du tout.

    Le depart se lit sur le seul champ qui le porte. Les trois lots sont dans
    trois etats differents -- rien, un tirage non scanne, un tirage scanne --,
    donc une confusion des deux ecrans se verrait.
    """
    lots = lots_a_trois(rangs=(None, 4, 2),
                        tirages=(False, True, True),
                        scannes=(False, False, True))
    assert confirmation.ecrans_du_parcours(lots) == (
        confirmation.ECRAN_DU_CONFLIT,
        confirmation.ECRAN_DU_TIRAGE_SCANNE,
        confirmation.ECRAN_DE_LA_CONFIRMATION,
    )


def test_la_confirmation_est_TOUJOURS_le_DERNIER_ecran():
    """Elle annonce des faits deja tranches ; elle ne peut donc pas passer avant.

    Mesure sur les quatre regimes d'un meme lot, pour que la propriete ne tienne
    pas d'un seul cas.
    """
    for tirage, scanne in ((False, False), (True, False), (True, True),
                           (False, True)):
        lots = [confirmation.LotAImprimer(LOT_CIBLE, RUSH, FRAMES_CIBLE,
                                          rang=4 if tirage else None,
                                          tirage_anterieur=tirage,
                                          scanne=scanne)]
        enchainement = confirmation.ecrans_du_parcours(lots)
        assert enchainement[-1] == confirmation.ECRAN_DE_LA_CONFIRMATION
        assert enchainement.count(confirmation.ECRAN_DE_LA_CONFIRMATION) == 1


# ===========================================================================
# Famille 10 -- AC 6.1 : `execution.py` n'est pas modifie
# ===========================================================================


def test_E5_3_EST_un_EcranChiffre_du_execution_py_LIVRE():
    """AC 6.1 : aucun second point de jugement n'est ecrit ici.

    Le volet positif de la frontiere suivante : sans lui, un ecran qui
    reimplementerait tout sans toucher `execution.py` la passerait.
    """
    assert issubclass(confirmation.EcranPdfConfirmation, execution.EcranChiffre)
    assert confirmation.EcranPdfConfirmation.TRANSITOIRE is True


def test_execution_py_est_ABSENT_de_ce_que_la_story_declare_TOUCHER():
    """AC 6.1, mesure **par la fiche** et non par un condensat.

    Un condensat du fichier ne prouverait rien : la fixture est deterministe,
    donc une reecriture rendrait exactement les memes octets (`EPIC11-ARB-83`,
    mesure du 2026-08-30). Ce qui se mesure est ce que la story **declare** :
    elle dit, dans « Ce que cette story NE fait PAS », qu'elle ne modifie pas ce
    module -- et le lot F ne le nomme dans aucun de ses fichiers a toucher.
    """
    fiche = FICHE_DE_LA_STORY.read_text(encoding="utf-8")
    # **L'ancrage a bouge le 2026-09-02, et le motif compte.** La fiche disait
    # « elle ne modifie pas `execution.py` » ; elle dit desormais « elle ne
    # modifiait pas », parce qu'`EPIC11-ARB-140` -- un arbitrage SEPARE, ouvert
    # par Egan apres chiffrage -- y a retire `Q quitter` au profit de `F1 aide`
    # et y a ferme le cul-de-sac de `F1`.
    #
    # Ce que l'AC 6.1 mesure n'a pas change pour autant : **aucun lot de CETTE
    # story n'ecrit dans le module partage**, et le lot F en particulier n'y
    # pose pas de second point de jugement. On mesure donc les deux faits --
    # la phrase, dans sa forme d'aujourd'hui, ET la raison nommee de
    # l'exception --, plutot qu'une tournure figee dont la moindre retouche
    # ferait rougir une frontiere qui n'a rien a dire sur elle.
    assert "elle ne modifiait pas `execution.py`" in fiche
    assert "`EPIC11-ARB-140`" in fiche
    debut = fiche.index("**Lot F --")
    fin = fiche.index("**Lot I --")
    lot_f = fiche[debut:fin]
    assert "test_atelier_pdf_confirmation.py" in lot_f
    # **La mesure porte sur la LISTE, pas sur une tournure.** Ce que le lot
    # declare toucher est son en-tete et ses cases -- le premier paragraphe du
    # bloc, avant toute prose. Le module partage ne peut y figurer que comme une
    # ABSENCE ; une ligne qui l'y nommerait autrement serait une declaration de
    # le toucher, et c'est ce que l'AC 6.1 compte a zero.
    declare = lot_f.split("\n\n")[0]
    mentions = [ligne for ligne in declare.splitlines()
                if "execution.py" in ligne]
    assert mentions, "les cases du lot doivent dire quelque chose du partage"
    for ligne in mentions:
        assert "absent" in ligne, ligne


def test_le_module_n_ECRIT_PAS_dans_le_paquet_partage():
    """Frontiere negative : aucune affectation sur `execution` ni sur ses classes.

    Un `execution.RACCOURCIS_CONFIRMATION = ...` ou un
    `EcranChiffre.etat = ...` pose ici changerait un observable pour les quatre
    ateliers, sans toucher au fichier partage et sans qu'aucun condensat le voie.
    """
    partages = {"execution", "EcranChiffre", "ChoixExclusif", "LigneChiffree",
                "Panneau", "ModeleNoms"}
    for noeud in ast.walk(_arbre_du_produit()):
        if not isinstance(noeud, (ast.Assign, ast.AugAssign)):
            continue
        cibles = (noeud.targets if isinstance(noeud, ast.Assign)
                  else [noeud.target])
        for cible in cibles:
            if isinstance(cible, ast.Attribute) and isinstance(cible.value,
                                                              ast.Name):
                assert cible.value.id not in partages, ast.dump(cible)


# ===========================================================================
# Famille 11 -- l'ecran MONTE, dans les deux regimes
# ===========================================================================


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_monte_rend_son_cartouche_ses_noms_et_sa_mesure(banc, ascii_seul):
    """Le rendu complet, au plancher de `EPIC11-ARB-21` (80x24).

    Un ecran qui tient a 100x30 et deborde a 80x24 est un defaut que seule cette
    taille demasque.
    """
    plan = plan_de_la_maquette()
    ecran = confirmation.EcranPdfConfirmation(plan)
    courant, etat, raccourcis, bandeau, blocs = monter(banc, ecran, ascii_seul)

    texte = "\n".join(blocs)
    attendu_libelles = [ligne.libelle for ligne
                        in confirmation.lignes_du_cartouche(plan)]
    for libelle in attendu_libelles:
        cible = jetons.replier_ascii(libelle) if ascii_seul else libelle
        assert cible in texte, cible
    for nom in plan.noms:
        assert nom in texte, nom
    assert etat == (jetons.replier_ascii(
        confirmation.mesure_de_la_confirmation(plan)) if ascii_seul
        else confirmation.mesure_de_la_confirmation(plan))
    assert raccourcis == (jetons.replier_ascii(
        confirmation.RACCOURCIS_PDF_CONFIRMATION) if ascii_seul
        else confirmation.RACCOURCIS_PDF_CONFIRMATION)
    assert confirmation.bandeau_du_plan(plan) in bandeau or jetons.replier_ascii(
        confirmation.bandeau_du_plan(plan)) in bandeau
    assert courant.plan is plan


def test_le_bandeau_compte_les_LOTS_et_les_FRAMES_pas_les_PDF_et_les_PAGES():
    """`2 lots · 164 frames` (l. 2), la ou la ligne d'etat compte autre chose.

    Les deux se lisent du meme plan et ne disent pas la meme chose : le bandeau
    dit ce qu'on travaille, la ligne d'etat ce qu'on va produire. Les confondre
    ferait annoncer 28 lots.
    """
    plan = plan_de_la_maquette()
    assert confirmation.bandeau_du_plan(plan) == "2 lots · 164 frames"
    assert (confirmation.bandeau_du_plan(plan)
            != confirmation.mesure_de_la_confirmation(plan))


def test_le_bandeau_ACCORDE_ses_pluriels_sur_le_compte():
    """Un `+ "s"` pose au hasard rendrait « 1 lots »."""
    un_lot = confirmation.preparer_le_plan(
        None, project_id=PROJET,
        lots=[confirmation.LotAImprimer(LOT_CIBLE, RUSH, 1)],
        mise_en_page=mise_en_page([1]))
    assert confirmation.bandeau_du_plan(un_lot) == "1 lot · 1 frame"
    assert confirmation.mesure_de_la_confirmation(un_lot).startswith(
        "1 PDF · 1 page")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_monte_pose_la_fleche_sur_MODIFIER_et_non_sur_GENERER(
        banc, ascii_seul):
    """La mesure au montage, sur le texte que l'operateur voit."""
    ecran = confirmation.EcranPdfConfirmation(plan_de_la_maquette())
    _courant, _etat, _raccourcis, _bandeau, blocs = monter(banc, ecran,
                                                           ascii_seul)
    curseur = jetons.glyphes(ascii_seul)["curseur"]
    modifie = jetons.replier_ascii(confirmation.LIBELLE_MODIFIER) if ascii_seul \
        else confirmation.LIBELLE_MODIFIER
    genere = jetons.replier_ascii(confirmation.LIBELLE_GENERER) if ascii_seul \
        else confirmation.LIBELLE_GENERER
    lignes = [ligne for bloc in blocs for ligne in bloc.splitlines()
              if curseur in ligne]
    assert [ligne for ligne in lignes if modifie in ligne]
    assert not [ligne for ligne in lignes if genere in ligne]


def test_l_issue_retenue_ATTEINT_l_appelant_meme_sans_rappel_injecte():
    """Ce qui distingue le rappel absent d'un no-op muet.

    Le parcours qui injecte `sur_issue` est le lot I ; en attendant,
    `issue_declenchee` reste lisible sur l'ecran, et c'est la raison pour
    laquelle ce rappel est declare a l'inventaire de `test_rappels_cables.py`.
    """
    ecran = confirmation.EcranPdfConfirmation(plan_de_la_maquette())
    ecran.choix.viser(confirmation.ISSUE_ANNULER)
    ecran.valider()
    assert ecran.issue_declenchee.cle == confirmation.ISSUE_ANNULER

    recues = []
    avec_rappel = confirmation.EcranPdfConfirmation(
        plan_de_la_maquette(), sur_issue=recues.append)
    avec_rappel.choix.viser(confirmation.ISSUE_GENERER)
    avec_rappel.valider()
    assert [issue.cle for issue in recues] == [confirmation.ISSUE_GENERER]


def test_le_plan_est_GELE_et_ne_peut_pas_deriver_sous_l_ecran():
    """Un plan mutable se ferait modifier entre le dessin et la validation.

    Les chiffres annonces et les chiffres ecrits seraient alors deux choses
    differentes, sur le seul ecran dont c'est la fonction de les faire coincider.
    """
    plan = plan_de_la_maquette()
    with pytest.raises((AttributeError, TypeError)):
        plan.planches = ()
    with pytest.raises((AttributeError, TypeError)):
        plan.planches[0].nom = "autre.pdf"
