# -*- coding: utf-8 -*-
"""`E5-2` / `E5-2b` -- les reglages des planches (story 11.7, lot E, AC 5).

Ce banc mesure **une seule liste verticale** (`EPIC11-ARB-173`), le glyphe de
choix optimal **lu de `jetons`**, la grammaire de clavier tranchee par Egan le
2026-09-02 (`⏎` selectionne puis saute sur `Valider`), et le **repli de
cardinal** d'`EPIC11-ARB-179` -- qui monte, et dont le seul declencheur est le
basculement d'orientation.

**La regle des fabriques y est appliquee dans sa forme complete** : les
fabriques de bilan portent au moins **trois** mises en page, avec des valeurs
**distinguables**, la cible **au milieu** et **dans les deux orientations**. Une
fabrique a deux entrees place la cible en second ET en dernier, ou les fautes de
`find` et les fautes de terminaison de boucle sont indiscernables.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from mixed_media_utility import page_templates, pdf_composition
from mixed_media_utility.tui import atelier_pdf_reglages as reglages_pdf
from mixed_media_utility.tui import jetons

RACINE = pathlib.Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
SOURCE_DU_MODULE = pathlib.Path(reglages_pdf.__file__)
DOSSIER_TUI = SOURCE_DU_MODULE.parent

#: Les deux lots de la passe de demonstration des maquettes. Leurs cardinaux
#: **different**, ce qui est la condition pour que l'arrondi par lot se
#: distingue d'une pagination du total.
LOTS_DE_LA_MAQUETTE = (reglages_pdf.LotAPlanches("plan-04_25", 124),
                       reglages_pdf.LotAPlanches("plan-04_8", 40))


def centre_de_la_maquette(nom: str) -> list[str]:
    """Les lignes de la zone centrale d'une maquette, marge de gauche retiree."""
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
    cadre = [ligne for ligne in lignes if ligne.startswith("│")]
    # Le bandeau et sa mesure encadrent la zone centrale ; l'etat et les
    # raccourcis la suivent. On garde ce qui est entre les deux, et on retire
    # les lignes vides de queue : `textual` ne remplit pas la zone, la
    # composition s'arrete a sa derniere ligne de texte.
    centre = [ligne[2:-1].rstrip() for ligne in cadre[1:-2]]
    while centre and not centre[-1]:
        centre.pop()
    return centre


def etat_de_la_maquette(nom: str) -> str:
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
    cadre = [ligne for ligne in lignes if ligne.startswith("│")]
    return cadre[-2][2:-1].rstrip()


def raccourcis_de_la_maquette(nom: str) -> str:
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
    cadre = [ligne for ligne in lignes if ligne.startswith("│")]
    return cadre[-1][2:-1].rstrip()


def corps(ecran: reglages_pdf.EcranReglagesDesPlanches) -> list[str]:
    """Les lignes du corps, telles que le rendu les peindrait."""
    return [ligne.rstrip()
            for ligne in ecran.composer(jetons.LARGEUR_PLANCHER)[0]]


def reglages(**champs) -> reglages_pdf.ReglagesDesPlanches:
    champs.setdefault("lots", LOTS_DE_LA_MAQUETTE)
    return reglages_pdf.ReglagesDesPlanches(**champs)


# ===========================================================================
# La FABRIQUE de bilan -- trois mises en page, cible au milieu, deux
# orientations
# ===========================================================================

def mise(orientation: str, cardinal: int, largeur: float, hauteur: float,
         pages_par_lot: tuple[int, ...]) -> page_templates.MiseEnPageMesuree:
    return page_templates.MiseEnPageMesuree(
        orientation=orientation,
        frames_per_page=cardinal,
        template_id=f"fab-{orientation}-{cardinal}f",
        largeur_mm=largeur,
        hauteur_mm=hauteur,
        pages_par_lot=pages_par_lot,
    )


def bilan_fabrique() -> page_templates.BilanDeDomination:
    """Six mises en page, **trois par orientation**, toutes distinguables.

    La cible des tests est `paysage 4f` : elle est **au milieu** de sa liste
    (rang 1 sur 3) et **au milieu** du produit (rang 4 sur 6). Ni premiere, ni
    derniere, dans les deux parcours -- c'est ce qui separe une faute de `find`
    d'une faute de terminaison de boucle.

    Les surfaces et les pages sont **toutes differentes**, sans quoi une
    permutation entre deux lignes ne se verrait pas.
    """
    produit = (
        mise("portrait", 2, 180.0, 100.0, (60, 20)),   # 180,0 cm²  80 pages
        mise("portrait", 3, 120.0, 70.0, (42, 14)),    #  84,0 cm²  56 pages
        mise("portrait", 8, 90.0, 50.0, (16, 5)),      #  45,0 cm²  21 pages
        mise("paysage", 1, 230.0, 130.0, (124, 40)),   # 299,0 cm² 164 pages
        mise("paysage", 4, 110.0, 60.0, (31, 10)),     #  66,0 cm²  41 pages
        mise("paysage", 6, 85.0, 45.0, (21, 7)),       #  38,3 cm²  28 pages
    )
    return page_templates.BilanDeDomination(
        mises_en_page=produit,
        dominants=page_templates.dominants_des_mises_en_page(produit),
    )


# ===========================================================================
# E1 -- l'etat d'ouverture vient des constantes du COEUR
# ===========================================================================

def test_l_etat_d_ouverture_est_celui_du_coeur():
    """AC 5.1 : ni orientation, ni cardinal, ni marge ne sont recopies."""
    depart = reglages_pdf.ReglagesDesPlanches()
    assert depart.orientation == pdf_composition.resolve_orientation(None)
    assert depart.frames_par_page == page_templates.DEFAULT_FRAMES_PER_PAGE
    assert depart.marge == page_templates.DEFAULT_MARGIN_PRESET
    assert depart.champ == reglages_pdf.CHAMP_ORIENTATION


def test_aucune_constante_d_ouverture_n_est_ecrite_en_litteral():
    """Frontiere negative : les defauts NOMMENT la constante du coeur.

    Un test qui compare seulement les valeurs reste vert si quelqu'un ecrit
    `frames_par_page: int = 2` -- il mesure alors que `2 == 2`. Celui-ci lit la
    source et exige la reference.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "page_templates.DEFAULT_FRAMES_PER_PAGE" in source
    assert "page_templates.DEFAULT_MARGIN_PRESET" in source
    assert "pdf_composition.resolve_orientation(None)" in source
    assert not re.search(r"frames_par_page: int = \d", source)
    assert not re.search(r"marge: str = \"[0-9]", source)


def test_la_ligne_du_format_lit_les_deux_constantes_du_coeur():
    """`A4 · 600` : le format du registre, le dpi du defaut de composition."""
    ligne = reglages().ligne_du_format()
    assert page_templates.DEFAULT_PAGE_FORMAT in ligne
    assert str(pdf_composition.RENDER_DPI_DEFAULT) in ligne
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "pdf_composition.RENDER_DPI_DEFAULT" in source
    assert "page_templates.DEFAULT_PAGE_FORMAT" in source


def test_les_presets_de_marge_viennent_de_la_table_du_coeur():
    ligne = reglages().ligne_de_la_marge()
    for preset in page_templates.MARGIN_PRESETS_MM:
        assert preset in ligne
    assert "MARGIN_PRESETS_MM" in SOURCE_DU_MODULE.read_text(encoding="utf-8")


# ===========================================================================
# E2 -- une seule liste verticale, surface et pages SUR chaque entree
# ===========================================================================

@pytest.mark.parametrize("orientation", page_templates.ORIENTATIONS)
def test_la_liste_est_EXACTEMENT_le_vocabulaire_de_l_orientation(orientation):
    """AC 5.3d : aucun cardinal n'est retire -- « on guide, on n'interdit pas ».

    Ensemble **exact**, et non « contient » : un sous-ensemble passerait une
    assertion positive.
    """
    attendu = page_templates.frames_per_page_vocabulary(orientation)
    r = reglages(orientation=orientation, frames_par_page=attendu[0])
    assert r.cardinaux() == attendu


def test_chaque_entree_porte_sa_surface_ET_ses_pages():
    """AC 5.2 : les deux criteres de la domination sont sur la ligne."""
    r = reglages(orientation="paysage", frames_par_page=6)
    for ligne, mesure in zip(r.lignes_de_la_liste(), r.mises_en_page()):
        assert " mm" in ligne and " cm²" in ligne and " pages" in ligne
        assert f"{mesure.pages:3d} pages" in ligne


def test_les_pages_s_arrondissent_PAR_LOT_et_jamais_sur_le_total():
    """AC 5.4b : 124 -> 42 et 40 -> 14 font **56** pages a 3 f/page, pas 55.

    Deux lots de tailles differentes, sans quoi les deux formules coincident.
    """
    r = reglages(orientation="portrait", frames_par_page=3)
    retenue = r.retenue()
    assert retenue.pages_par_lot == (42, 14)
    assert retenue.pages == 56
    assert retenue.pages != -(-164 // 3)


def test_la_ligne_d_etat_nomme_chaque_lot_avec_SES_pages():
    """L'appariement lot <-> pages, sur deux lots aux cardinaux differents."""
    r = reglages(orientation="paysage", frames_par_page=6)
    assert r.ligne_d_etat() == (
        "28 pages — plan-04_25 21 · plan-04_8 7 · 164 frames sur "
        "168 emplacements")


@pytest.mark.parametrize("nom,champs", [
    ("E5-2-pdf-reglages.txt",
     dict(orientation="paysage", frames_par_page=6,
          champ=reglages_pdf.CHAMP_VALIDER)),
    ("E5-2b-pdf-cardinal-refiltre.txt",
     dict(orientation="portrait", frames_par_page=8,
          champ=reglages_pdf.CHAMP_CARDINAL)),
])
def test_le_corps_rendu_est_celui_de_la_maquette(nom, champs):
    """Le produit contre le dessin **valide**, ligne par ligne.

    C'est la mesure la plus forte de cet ecran : elle attrape a la fois une
    colonne qui glisse, un chiffre qui change et un glyphe qui se deplace, et
    elle rougirait si une maquette etait regeneree sans que le produit suive.
    """
    ecran = reglages_pdf.EcranReglagesDesPlanches(reglages(**champs))
    assert corps(ecran) == centre_de_la_maquette(nom)


@pytest.mark.parametrize("nom,champ", [
    ("E5-2-pdf-reglages.txt", reglages_pdf.CHAMP_VALIDER),
    ("E5-2b-pdf-cardinal-refiltre.txt", reglages_pdf.CHAMP_CARDINAL),
])
def test_la_ligne_de_raccourcis_est_celle_de_la_maquette(nom, champ):
    r = reglages(champ=champ)
    assert r.raccourcis() == raccourcis_de_la_maquette(nom)


# ===========================================================================
# E3 -- le glyphe de choix optimal : `jetons`, jamais un litteral
# ===========================================================================

def test_le_glyphe_du_choix_optimal_vient_de_la_table_des_jetons():
    """AC 5.3b : `●` et `*` sont le MEME jeton, `state-complete`."""
    r = reglages(orientation="paysage", frames_par_page=6)
    assert jetons.GLYPHES[reglages_pdf.ETAT_CHOIX_OPTIMAL] in r.ligne_de_cardinal(
        r.bilan().de("paysage", 4))
    assert jetons.GLYPHES_ASCII[reglages_pdf.ETAT_CHOIX_OPTIMAL] in (
        r.ligne_de_cardinal(r.bilan().de("paysage", 4), ascii_seul=True))


def test_aucun_glyphe_n_est_ecrit_en_litteral_dans_le_module():
    """Frontiere negative : ni `●`, ni `*`, ni `▲`, ni `▸` dans la source.

    Un `*` litteral en UTF-8 ferait **deux** fautes d'un coup -- un glyphe hors
    de la table close de `DESIGN.md` §6, et une collision avec le repli ASCII
    de `●`, qui detruirait le second canal qu'il sert.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    litteraux = [noeud.value for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Constant)
                 and isinstance(noeud.value, str)]
    # Les dessins hors ASCII de la table, plus l'asterisque -- le cas nomme par
    # l'AC. Les autres replis ASCII (`.`, `>`, `-`) sont de la ponctuation
    # ordinaire qu'un `.replace(".", ",")` emploie legitimement, et la mesure
    # porte donc sur l'**egalite exacte** : `« Format · DPI »` contient le
    # dessin de `neutre` sans etre ce dessin.
    dessins = {dessin for dessin in jetons.GLYPHES.values()
               if not dessin.isascii()}
    dessins.add(jetons.GLYPHES_ASCII[reglages_pdf.ETAT_CHOIX_OPTIMAL])
    for litteral in litteraux:
        assert litteral not in dessins, litteral
    # Le volet symetrique : les dessins ne sont pas absents par hasard, ils
    # sont **lus** de la table -- et pour les deux regimes a la fois.
    assert "jetons.glyphes(ascii_seul)" in source


def test_la_legende_porte_le_glyphe_et_se_replie_avec_lui():
    """AC 5.3c, et la legende **fait trois mots** (Egan, 2026-09-02)."""
    r = reglages()
    assert r.ligne_de_la_legende().strip() == "● choix optimal"
    assert r.ligne_de_la_legende(ascii_seul=True).strip() == "* choix optimal"
    assert "non dominé" not in r.ligne_de_la_legende()


@pytest.mark.parametrize("orientation,attendu", [
    ("paysage", {1, 4}),
    ("portrait", {2, 3, 8}),
])
def test_l_ensemble_des_entrees_marquees_est_EXACTEMENT_celui_la(
        orientation, attendu):
    """AC 5.4 : la domination se calcule sur le PRODUIT des deux orientations.

    Une entree peut donc etre sans glyphe a cause d'une combinaison de l'AUTRE
    orientation -- `paysage 6f` est domine par `portrait 8f`. L'ensemble est
    mesure **exactement** : une assertion positive laisserait passer un glyphe
    de trop.
    """
    r = reglages(orientation=orientation,
                 frames_par_page=page_templates.frames_per_page_vocabulary(
                     orientation)[0])
    marques = {mesure.frames_per_page for mesure in r.mises_en_page()
               if r.est_optimale(mesure.frames_per_page)}
    assert marques == attendu


def test_le_glyphe_est_COLLE_au_chiffre_et_non_cale_a_droite():
    """Egan, 2026-09-02 : « directement a cote du chiffre. Pas une pastille
    tout a droite. »"""
    r = reglages(orientation="paysage", frames_par_page=6)
    ligne = r.ligne_de_cardinal(r.bilan().de("paysage", 4))
    glyphe = jetons.GLYPHES[reglages_pdf.ETAT_CHOIX_OPTIMAL]
    assert f"4{glyphe}" in ligne
    assert not ligne.rstrip().endswith(glyphe)


def test_les_etats_donnes_designent_EXACTEMENT_les_lignes_marquees():
    """`EPIC11-ARB-71` : colle au chiffre, le glyphe n'ouvre plus de colonne,
    donc `jetons.jeton_d_etat` ne le voit plus et l'etat doit etre DONNE."""
    r = reglages(orientation="paysage", frames_par_page=6)
    lignes = r.lignes_de_la_liste()
    etats = r.etats_de_la_liste()
    assert set(etats.values()) == {reglages_pdf.ETAT_CHOIX_OPTIMAL}
    glyphe = jetons.GLYPHES[reglages_pdf.ETAT_CHOIX_OPTIMAL]
    assert {rang for rang, ligne in enumerate(lignes)
            if glyphe in ligne} == set(etats)


# ===========================================================================
# E4 -- `Entree` selectionne, le bouton valide, la ligne de raccourcis suit
# ===========================================================================

def test_les_champs_parcourus_par_Tab_sont_EXACTEMENT_ces_quatre_la():
    """`Format · DPI` n'en est pas un : `PAGE_FORMATS` n'a qu'un membre."""
    assert reglages_pdf.CHAMPS == ("orientation", "marge", "cardinal",
                                   "valider")
    r = reglages()
    vus = [r.champ]
    for _ in range(len(reglages_pdf.CHAMPS)):
        r.avancer()
        vus.append(r.champ)
    assert vus == list(reglages_pdf.CHAMPS) + [reglages_pdf.CHAMP_ORIENTATION]


@pytest.mark.parametrize("champ", reglages_pdf.CHAMPS_DE_CHOIX)
def test_entree_dans_un_choix_SAUTE_sur_le_bouton_sans_valider(champ):
    """Egan, 2026-09-02 : « ⏎ "saute" ensuite en dehors du choix pour valider »."""
    r = reglages(champ=champ)
    assert r.entrer() is False
    assert r.champ == reglages_pdf.CHAMP_VALIDER


def test_entree_sur_le_bouton_VALIDE_et_appelle_la_suite():
    vus = []
    r = reglages(champ=reglages_pdf.CHAMP_VALIDER)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r, continuer=vus.append)
    assert ecran.traiter("enter") is True
    assert vus == [r]


def test_valider_SANS_appelant_nomme_ce_qui_manque_au_lieu_de_se_taire():
    """`K1.1a` : un `if ... is not None` sans `else` rend la touche
    indistinguable d'un clavier casse.

    **Reecrit le 2026-09-02, par le lot de cablage, et le motif compte.** Ce
    test mesurait deux choses : que la branche `else` existe, et que
    l'inventaire des rappels (`test_rappels_cables.py`) declarait ce manque.
    La seconde moitie est **tombee avec le manque** : `ParcoursPdf` injecte
    desormais `continuer`, donc l'entree est sortie de l'inventaire -- c'est
    le volet « declares mais desormais cables » de la garde qui l'a dit.

    Ce qui reste, et qui vaut d'etre mesure : la branche `else` est un
    **filet**, pas une promesse. Elle ne se retire pas avec le cablage -- un
    futur appelant qui oublierait le mot-cle retomberait dessus, et le finding
    `K1.1a` dit ce que couterait de la laisser muette. Le volet positif du
    cablage vit dans `test_atelier_pdf_parcours.py`, qui mesure ou `⏎` mene
    reellement.
    """
    r = reglages(champ=reglages_pdf.CHAMP_VALIDER)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    assert ecran.traiter("enter") is True
    assert reglages_pdf.CE_QUI_MANQUE_APRES_LES_REGLAGES
    assert reglages_pdf.QUAND_LA_CONFIRMATION
    # Le filet est **appele**, et non seulement declare : un `traiter` qui
    # rendrait `True` sans passer par la branche serait vert sur les trois
    # assertions ci-dessus.
    appels = []
    ecran._pas_encore = lambda: appels.append(True)
    assert ecran.traiter("enter") is True
    assert appels == [True]


def test_entree_dans_la_liste_n_appelle_PAS_la_suite():
    """Le saut n'est pas une validation : un seul `⏎` ne compose rien."""
    vus = []
    r = reglages(champ=reglages_pdf.CHAMP_CARDINAL)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r, continuer=vus.append)
    ecran.traiter("enter")
    assert vus == []
    assert r.champ == reglages_pdf.CHAMP_VALIDER


def test_la_ligne_de_raccourcis_est_CONTEXTUELLE_dans_les_deux_etats():
    """AC 5.5c : une AC qui n'en mesure qu'un laisse passer une ligne figee."""
    dans_la_liste = reglages(champ=reglages_pdf.CHAMP_CARDINAL).raccourcis()
    sur_le_bouton = reglages(champ=reglages_pdf.CHAMP_VALIDER).raccourcis()
    assert dans_la_liste != sur_le_bouton
    assert dans_la_liste.startswith("⏎ sélectionner")
    assert sur_le_bouton.startswith("⏎ valider")
    assert reglages(champ=reglages_pdf.CHAMP_ORIENTATION).raccourcis() == (
        dans_la_liste)


def test_l_ecran_POSE_sa_ligne_de_raccourcis_a_chaque_dessin():
    """L'idiome du depot, et le motif de ne pas en faire une `property`.

    `test_majuscules_des_raccourcis` balaie l'attribut de CLASSE `raccourcis` de
    tous les ecrans du paquet et attend une chaine : une `property` y rendait
    quatorze tests rouges d'un coup, dont deux frontieres de grille. L'ecran
    **assigne** donc son attribut, comme `atelier_extraction` et `atelier_scan`.
    """
    assert isinstance(
        reglages_pdf.EcranReglagesDesPlanches.raccourcis, str)
    r = reglages(champ=reglages_pdf.CHAMP_CARDINAL)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    assert ecran.poser_les_raccourcis() == reglages_pdf.RACCOURCIS_CHOIX
    assert ecran.raccourcis == reglages_pdf.RACCOURCIS_CHOIX
    ecran.traiter("enter")
    assert ecran.poser_les_raccourcis() == reglages_pdf.RACCOURCIS_VALIDER
    assert ecran.raccourcis == reglages_pdf.RACCOURCIS_VALIDER


def test_le_bouton_se_dessine_comme_un_champ():
    """AC 5.5a : rien a gauche, la valeur a la colonne des valeurs, `>` au
    focus -- et **aucune seconde colonne** (Egan, 2026-09-02)."""
    au_focus = reglages(champ=reglages_pdf.CHAMP_VALIDER).ligne_du_bouton()
    hors_focus = reglages(champ=reglages_pdf.CHAMP_CARDINAL).ligne_du_bouton()
    assert au_focus.strip() == f"{jetons.GLYPHES['invite']} Valider"
    assert hors_focus.strip() == "Valider"
    assert au_focus.index("Valider") == hors_focus.index("Valider")
    assert "compose les planches" not in au_focus


def test_le_curseur_ne_se_pose_dans_la_liste_QUE_si_elle_a_le_focus():
    """`E5-2` porte `>` sur le bouton et aucun `▸` ; `E5-2b` l'inverse."""
    glyphe = jetons.GLYPHES["curseur"]
    dans_la_liste = reglages(orientation="portrait", frames_par_page=8,
                             champ=reglages_pdf.CHAMP_CARDINAL)
    sur_le_bouton = reglages(orientation="portrait", frames_par_page=8,
                             champ=reglages_pdf.CHAMP_VALIDER)
    marquees = [ligne for ligne in dans_la_liste.lignes_de_la_liste()
                if glyphe in ligne]
    assert len(marquees) == 1 and " 8" in marquees[0]
    assert not any(glyphe in ligne
                   for ligne in sur_le_bouton.lignes_de_la_liste())


def test_les_fleches_choisissent_dans_le_champ_et_naviguent_sur_le_bouton():
    """`↑↓ choisir` dans un champ, `↑↓ naviguer` sur le bouton : la ligne de
    raccourcis dit ce que les touches font, et les touches le font."""
    r = reglages(orientation="paysage", frames_par_page=6,
                 champ=reglages_pdf.CHAMP_CARDINAL)
    r.choisir(1)
    assert r.frames_par_page == 8
    r.choisir(-1)
    assert r.frames_par_page == 6
    sur_le_bouton = reglages(champ=reglages_pdf.CHAMP_VALIDER)
    sur_le_bouton.choisir(-1)
    assert sur_le_bouton.champ == reglages_pdf.CHAMP_CARDINAL


def test_un_cardinal_HORS_vocabulaire_n_entre_pas_dans_l_ecran():
    """`EPIC11-ARB-17` : l'ecran « ne laisse JAMAIS a l'ecran un couple que le
    coeur refuserait ».

    Le refus se mesure sur les deux sens : `6` est offert en paysage et
    **retire** en portrait, `3` l'inverse. Une garde qui ne testerait que
    l'egalite avec la valeur courante laisserait entrer les deux.
    """
    portrait = reglages(orientation="portrait", frames_par_page=8)
    assert portrait.poser_le_cardinal(6) is False
    assert portrait.frames_par_page == 8
    paysage = reglages(orientation="paysage", frames_par_page=6)
    assert paysage.poser_le_cardinal(3) is False
    assert paysage.frames_par_page == 6
    page_templates.build_template_id(
        paysage.orientation, paysage.frames_par_page, paysage.marge)


def test_le_choix_est_borne_et_ne_s_enroule_pas():
    """De `1` a `8` par une seule pression serait du plus de papier au moins de
    papier sans que rien ne l'ait montre."""
    r = reglages(orientation="paysage", frames_par_page=1,
                 champ=reglages_pdf.CHAMP_CARDINAL)
    assert r.choisir(-1) is False
    assert r.frames_par_page == 1


# ===========================================================================
# E5 -- la domination est APPELEE, jamais recalculee
# ===========================================================================

def test_le_glyphe_suit_le_bilan_DU_COEUR_et_ne_le_rejoue_pas(monkeypatch):
    """Le volet **positif** de la frontiere : on remplace la mesure du coeur
    par une fabrique ou la cible est dominee, et l'ecran doit changer d'avis.

    Un ecran qui recalculerait la domination ignorerait cette substitution et
    resterait vert -- c'est exactement ce que ce test attrape.
    """
    fabrique = bilan_fabrique()
    monkeypatch.setattr(page_templates, "bilan_de_domination",
                        lambda *a, **k: fabrique)
    r = reglages(orientation="paysage", frames_par_page=4)
    assert r.cardinaux() == (1, 4, 6)
    marques = {mesure.frames_per_page for mesure in r.mises_en_page()
               if r.est_optimale(mesure.frames_per_page)}
    # `paysage 4f` (66,0 cm² / 41 pages) est domine par `portrait 3f`
    # (84,0 cm² / 56 pages) ? non : plus de pages. Par `portrait 2f` ? non.
    # Il ne l'est par personne, et `paysage 6f` l'est par `portrait 8f`.
    assert marques == {1, 4}
    assert not r.est_optimale(6)


def test_aucun_module_de_tui_ne_calcule_une_domination():
    """Frontiere a l'AST (AC 5.4) : la comparaison vit au COEUR.

    Le critere est nomme plutot que devine : aucune fonction de `tui/` ne
    definit la relation -- ni par son nom, ni en comparant deux surfaces ou
    deux cardinaux de pages entre eux.
    """
    interdits = {"domine", "dominants_des_mises_en_page",
                 "surface_de_dessin_mm", "mesurer_les_mises_en_page"}
    for chemin in sorted(DOSSIER_TUI.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert noeud.name not in interdits, (chemin.name, noeud.name)
            if isinstance(noeud, ast.Compare):
                attributs = {c.attr for c in ast.walk(noeud)
                             if isinstance(c, ast.Attribute)}
                assert not ({"surface_mm2", "surface_cm2"} & attributs
                            and "pages" in attributs), (chemin.name,
                                                        ast.dump(noeud))


def test_aucun_module_de_tui_ne_calcule_une_distance_entre_cardinaux():
    """Frontiere a l'AST (AC 5.6) : la regle de repli vit au COEUR.

    `abs(candidat - cardinal)` est la forme naturelle d'un repli « au plus
    proche », et c'est precisement celle qu'`EPIC11-ARB-179` a ecartee.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    for noeud in ast.walk(ast.parse(source)):
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id in ("abs", "sorted")):
            raise AssertionError(f"un `{noeud.func.id}()` dans les reglages")
    # Le volet symetrique : la regle est appelee, et elle vient du coeur.
    assert "page_templates.replier_le_cardinal" in source
    assert hasattr(page_templates, "replier_le_cardinal")


def test_le_conseil_nomme_UNE_seule_dominante_et_la_plus_optimale():
    """AC 5.4a : le conseil est le seul endroit qui nomme l'autre orientation.

    Il n'y en a **qu'un** (Egan : « on affiche UNIQUEMENT le conseil le plus
    optimal »), et il tombe quand la mise en page retenue n'est dominee par
    personne.
    """
    domine = reglages(orientation="paysage", frames_par_page=6)
    lignes = domine.lignes_du_conseil(jetons.largeur_utile())
    assert len(lignes) == 2
    assert "8 frames portrait est plus optimal" in lignes[0]
    assert "et gain de pages" in lignes[1]
    non_domine = reglages(orientation="portrait", frames_par_page=8)
    assert non_domine.lignes_du_conseil(jetons.largeur_utile()) == []


def test_le_conseil_departage_deux_dominantes_de_MEME_surface_aux_pages(
        monkeypatch):
    """Le depart d'egalite du conseil : a surface egale, le MOINS de papier.

    Le cas n'existe pas sur la geometrie livree -- aucune dominante n'y partage
    sa surface avec une autre --, donc seule une fabrique peut le montrer. Sans
    lui, `(surface, -pages)` et `(surface, pages)` rendent le meme conseil et
    le mutant du comparateur survit (`M08` de la campagne).

    La cible est `paysage 6f`, **au milieu** de sa liste de trois.
    """
    produit = (
        mise("portrait", 2, 180.0, 100.0, (60, 20)),   # 180,0 cm²  80 pages
        mise("portrait", 3, 120.0, 70.0, (20, 7)),     #  84,0 cm²  27 pages
        mise("portrait", 8, 90.0, 50.0, (16, 5)),      #  45,0 cm²  21 pages
        mise("paysage", 1, 230.0, 130.0, (124, 40)),   # 299,0 cm² 164 pages
        mise("paysage", 6, 84.0, 46.0, (21, 7)),       #  38,6 cm²  28 pages
        mise("paysage", 4, 120.0, 70.0, (21, 7)),      #  84,0 cm²  28 pages
    )
    fabrique = page_templates.BilanDeDomination(
        mises_en_page=produit,
        dominants=page_templates.dominants_des_mises_en_page(produit))
    monkeypatch.setattr(page_templates, "bilan_de_domination",
                        lambda *a, **k: fabrique)
    r = reglages(orientation="paysage", frames_par_page=6)
    dominantes = {mesure.cle for mesure in fabrique.dominants_de("paysage", 6)}
    assert dominantes == {("portrait", 3), ("portrait", 8), ("paysage", 4)}
    # Deux d'entre elles partagent EXACTEMENT la meme surface -- c'est la seule
    # configuration ou le depart d'egalite se mesure.
    egales = [mesure for mesure in fabrique.dominants_de("paysage", 6)
              if mesure.surface_mm2 == 8400.0]
    assert {mesure.cle for mesure in egales} == {("portrait", 3),
                                                 ("paysage", 4)}
    meilleure = r.meilleure_que_la_retenue()
    assert meilleure.surface_mm2 == 8400.0
    assert meilleure.pages == 27
    assert meilleure.cle == ("portrait", 3)
    assert "3 frames portrait est plus optimal" in r.lignes_du_conseil(76)[0]


def test_le_conseil_ne_dit_gain_de_pages_que_quand_les_pages_BAISSENT():
    """Les deux formes du motif, mesurees toutes les deux."""
    avec = reglages(orientation="paysage", frames_par_page=6)
    assert "et gain de pages" in avec.lignes_du_conseil(76)[1]
    sans = reglages(orientation="portrait", frames_par_page=4)
    lignes = sans.lignes_du_conseil(76)
    assert "4 frames paysage est plus optimal" in lignes[0]
    assert "et gain de pages" not in lignes[1]


# ===========================================================================
# E6 -- le REPLI de cardinal (`EPIC11-ARB-179`), et il MONTE
# ===========================================================================

@pytest.mark.parametrize("depart,orientation,attendu,refuse", [
    # Les deux -- et les seuls deux -- cas du depot.
    (6, "portrait", 8, 4),     # descendre rendrait 4 : 31 feuilles contre 16
    (3, "paysage", 4, 2),      # descendre rendrait 2
])
def test_le_repli_MONTE_au_cardinal_offert_immediatement_superieur(
        depart, orientation, attendu, refuse):
    """`EPIC11-ARB-179`, verbatim d'Egan : « On economise le papier. »

    Le cardinal refuse est **asserte** lui aussi : c'est ce qui tue le mutant
    « monter -> descendre », qu'une assertion sur le seul resultat attendu
    laisserait vivre si la valeur descendante coincidait.
    """
    repli = page_templates.replier_le_cardinal(orientation, depart)
    assert repli.retenu == attendu
    assert repli.retenu != refuse
    assert repli.demande == depart
    assert repli.a_replie is True


def test_le_repli_prend_le_PLUS_PETIT_des_superieurs_et_non_le_plus_grand():
    """`3` en paysage a **trois** superieurs offerts -- 4, 6 et 8.

    C'est le seul cas du depot ou `min` et `max` divergent, donc le seul qui
    puisse tuer le mutant du comparateur.
    """
    offerts = page_templates.frames_per_page_vocabulary("paysage")
    superieurs = tuple(c for c in offerts if c > 3)
    assert len(superieurs) > 1, superieurs
    assert page_templates.replier_le_cardinal("paysage", 3).retenu == min(
        superieurs)


def test_le_comparateur_du_repli_est_STRICT_et_la_garde_le_rend_equivalent():
    """Tolerance DOCUMENTEE, avec sa preuve -- mutant `M03` de la campagne.

    Remplacer `offert > cardinal` par `offert >= cardinal` survit a toute la
    suite, et c'est un mutant **equivalent** : la garde `if cardinal in
    vocabulaire` rend avant, donc tout cardinal qui atteint la comparaison est
    absent du vocabulaire et `offert == cardinal` est impossible. Ce test mesure
    la garde qui rend l'equivalence vraie -- si elle tombait, le mutant
    cesserait d'etre equivalent et ce test rougirait en premier.
    """
    for orientation in page_templates.ORIENTATIONS:
        offerts = page_templates.frames_per_page_vocabulary(orientation)
        for cardinal in offerts:
            repli = page_templates.replier_le_cardinal(orientation, cardinal)
            assert repli.retenu == cardinal
            assert repli.a_replie is False


def test_un_cardinal_deja_offert_se_rend_lui_meme_sans_replier():
    """Un ecran peut appeler a chaque basculement sans decider lui-meme."""
    repli = page_templates.replier_le_cardinal("paysage", 6)
    assert repli.retenu == 6
    assert repli.a_replie is False


def test_la_regle_du_repli_COINCIDE_avec_ce_que_le_coeur_dit_deja():
    """Le motif de retrait de `6` en portrait **nomme son remplacant**.

    Deux raisonnements independants -- monter d'un barreau, et lire le motif du
    retrait -- rendent le meme cardinal. La coincidence est **mesuree** ici et
    non supposee : c'est ce qui rend la regle sure plutot que seulement simple.
    """
    motif = page_templates.retired_cardinal_reason(
        page_templates.DEFAULT_GEOMETRY_VERSION, 6, "portrait")
    assert motif is not None
    nomme = re.search(r"Utiliser (\d+) pour la meme surface", motif)
    assert nomme is not None, motif
    assert int(nomme.group(1)) == page_templates.replier_le_cardinal(
        "portrait", 6).retenu


def test_sans_cardinal_superieur_le_coeur_REFUSE_et_ne_devine_pas():
    """`EPIC11-ARB-179` ne dit PAS ce qu'il faut faire dans ce cas.

    Descendre serait un `max()` silencieux qui renverserait « on economise le
    papier » sans qu'aucune decision ne l'ait dit. Le refus nomme l'arbitrage,
    pour que la trace mene a la question plutot qu'a du code.
    """
    with pytest.raises(page_templates.UnknownTemplateError) as refus:
        page_templates.replier_le_cardinal("portrait", 9)
    assert "EPIC11-ARB-179" in str(refus.value)
    assert "9" in str(refus.value)


def test_le_refus_est_INJOIGNABLE_sur_toutes_les_geometries_livrees():
    """La frontiere qui rend le cas non arbitre inatteignable par un ecran.

    Elle balaie le produit entier -- versions x orientations x vocabulaires --
    et rougirait le jour ou une geometrie ferait tomber la propriete, **avant**
    qu'un ecran ait a affronter le cas.
    """
    for version in page_templates.GEOMETRY_VERSIONS:
        for depart in page_templates.ORIENTATIONS:
            for arrivee in page_templates.ORIENTATIONS:
                for cardinal in page_templates.frames_per_page_vocabulary(
                        depart, version):
                    repli = page_templates.replier_le_cardinal(
                        arrivee, cardinal, version)
                    assert repli.retenu in (
                        page_templates.frames_per_page_vocabulary(
                            arrivee, version))


def test_le_basculement_est_le_SEUL_declencheur_du_repli():
    """`EPIC11-ARB-179` : par la ligne de commande il n'y a rien a replier."""
    r = reglages(orientation="paysage", frames_par_page=6)
    assert r.repli is None
    assert r.poser_le_cardinal(8) is True
    assert r.repli is None
    assert r.poser_l_orientation("portrait") is True
    assert r.repli is None          # `8` est offert en portrait
    r.poser_l_orientation("paysage")
    r.poser_le_cardinal(6)
    assert r.poser_l_orientation("portrait") is True
    assert r.repli is not None and r.frames_par_page == 8


def test_l_ecran_ne_laisse_JAMAIS_un_couple_que_le_coeur_refuserait():
    """`EPIC11-ARB-17`. Mesure sur **tout** le produit, pas sur un cas."""
    for depart in page_templates.ORIENTATIONS:
        for cardinal in page_templates.frames_per_page_vocabulary(depart):
            for arrivee in page_templates.ORIENTATIONS:
                r = reglages(orientation=depart, frames_par_page=cardinal)
                r.poser_l_orientation(arrivee)
                page_templates.build_template_id(
                    r.orientation, r.frames_par_page, r.marge)


def test_le_constat_de_repli_est_celui_de_la_maquette_VALIDEE():
    """La ligne d'etat garde sa forme (Egan, 2026-09-02 : « Non, on laisse la
    ligne du bas avec les infos. »), et elle ne porte AUCUN motif de conception
    (`EPIC11-ARB-56`)."""
    r = reglages(orientation="paysage", frames_par_page=6)
    r.poser_l_orientation("portrait")
    assert r.ligne_d_etat() == etat_de_la_maquette(
        "E5-2b-pdf-cardinal-refiltre.txt")
    assert "parce que" not in r.ligne_d_etat()
    assert "Tab" not in r.ligne_d_etat() and "⏎" not in r.ligne_d_etat()


def test_le_constat_de_repli_SURVIT_au_redessin():
    """`poser_etat` seul se fait effacer par le dessin suivant : l'etat est
    porte par le modele, pas pose une fois."""
    r = reglages(orientation="paysage", frames_par_page=6)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    r.poser_l_orientation("portrait")
    attendu = r.ligne_d_etat()
    for _ in range(3):
        ecran.composer(jetons.LARGEUR_PLANCHER)
        assert r.ligne_d_etat() == attendu


def test_le_constat_de_repli_TOMBE_au_geste_suivant():
    """Un constat qui resterait sous un reglage change decrirait le passe."""
    r = reglages(orientation="paysage", frames_par_page=6)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    r.poser_l_orientation("portrait")
    assert r.repli is not None
    ecran.traiter("tab")
    assert r.repli is None
    assert r.ligne_d_etat() == r.mesure()


def test_le_basculement_par_les_fleches_replie_lui_aussi():
    """Le repli n'est pas branche sur une seule porte d'entree."""
    r = reglages(orientation="paysage", frames_par_page=6,
                 champ=reglages_pdf.CHAMP_ORIENTATION)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    ecran.traiter("down")
    assert r.orientation == "portrait"
    assert r.frames_par_page == 8
    assert r.ligne_d_etat().startswith(jetons.GLYPHES[reglages_pdf.ETAT_DU_REPLI])


# ===========================================================================
# E7 -- zero champ de gamut, et le libelle de la marge
# ===========================================================================

def test_aucun_champ_de_gamut_a_l_ecran():
    """AC 5.9a, frontiere negative. « On enlève compression de gamut. »

    Elle porte sur les **identifiants** -- champ, attribut, constante -- et sur
    ce qui est dessine, jamais sur le mot : la prose de ce module dit pourquoi
    le champ n'existe pas, et un grep du mot rendrait cette explication
    interdite en meme temps que le champ.
    """
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        nom = getattr(noeud, "id", None) or getattr(noeud, "attr", None) or ""
        assert "gamut" not in nom.lower(), nom
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            assert "gamut" not in noeud.value.lower() or len(noeud.value) > 40
    assert reglages_pdf.CHAMPS == ("orientation", "marge", "cardinal",
                                   "valider")
    r = reglages()
    assert not any("gamut" in ligne.lower()
                   for ligne in corps(reglages_pdf.EcranReglagesDesPlanches(r)))


def test_le_libelle_est_marge_de_travail_et_nulle_part_marge_de_recadrage():
    """`EPIC11-ARB-34`, avec son volet negatif sur tout `tui/`."""
    assert reglages_pdf.LIBELLE_MARGE == "Marge de travail"
    assert reglages_pdf.LIBELLE_MARGE in reglages().ligne_de_la_marge()
    for chemin in sorted(DOSSIER_TUI.glob("*.py")):
        assert "marge de recadrage" not in chemin.read_text(
            encoding="utf-8").lower(), chemin.name


def test_le_template_id_n_est_ni_un_champ_ni_affiche():
    """`EPIC11-ARB-17` et AC 5.7 : il se lit a la confirmation `E5-3`."""
    r = reglages(orientation="paysage", frames_par_page=6)
    gabarit = r.retenue().template_id
    assert gabarit.startswith("tpl-")
    lignes = corps(reglages_pdf.EcranReglagesDesPlanches(r))
    assert not any(gabarit in ligne for ligne in lignes)
    assert "template_id" not in [champ for champ in reglages_pdf.CHAMPS]


# ===========================================================================
# E8 -- la FABRIQUE : trois entrees, cible au milieu, deux orientations
# ===========================================================================

def test_la_fabrique_place_la_cible_au_MILIEU_des_deux_parcours():
    """La regle des fabriques, mesuree sur la fabrique elle-meme.

    Une fabrique dont la cible est en second sur deux elements la place aussi en
    dernier : un mutant `continue` -> `break` y survit. Ce controle est ce qui
    empeche la fabrique de se degrader en silence.
    """
    produit = bilan_fabrique().mises_en_page
    cles = [mesure.cle for mesure in produit]
    assert cles.index(("paysage", 4)) not in (0, len(cles) - 1)
    paysage = [cle for cle in cles if cle[0] == "paysage"]
    assert len(paysage) >= 3
    assert paysage.index(("paysage", 4)) not in (0, len(paysage) - 1)
    surfaces = [mesure.surface_mm2 for mesure in produit]
    assert len(set(surfaces)) == len(surfaces)
    pages = [mesure.pages for mesure in produit]
    assert len(set(pages)) == len(pages)
    assert {cle[0] for cle in cles} == set(page_templates.ORIENTATIONS)


def test_l_appariement_ligne_mesure_tient_sur_la_cible_du_milieu(monkeypatch):
    """Une permutation entre deux lignes ne se voit que si elles different."""
    fabrique = bilan_fabrique()
    monkeypatch.setattr(page_templates, "bilan_de_domination",
                        lambda *a, **k: fabrique)
    r = reglages(orientation="paysage", frames_par_page=4)
    lignes = r.lignes_de_la_liste()
    assert len(lignes) == 3
    milieu = lignes[1]
    assert "110,0 ×  60,0 mm" in milieu
    assert " 66,0 cm²" in milieu
    assert " 41 pages" in milieu
    assert jetons.GLYPHES["exclusif-retenu"] in milieu
    assert jetons.GLYPHES["exclusif-libre"] in lignes[0]
    assert jetons.GLYPHES["exclusif-libre"] in lignes[2]


# ===========================================================================
# La grille 80x24 et le repli ASCII
# ===========================================================================

@pytest.mark.parametrize("orientation", page_templates.ORIENTATIONS)
@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("champ", reglages_pdf.CHAMPS)
def test_aucune_ligne_ne_deborde_la_zone_utile(orientation, ascii_seul, champ):
    """`DESIGN.md` §1 : la grille est 80x24, et la zone utile 76 colonnes.

    MESURE: la plus longue ligne du corps fait 74 colonnes en UTF-8 comme en
    ASCII (`E5-2`, conseil a deux lignes).
    """
    cardinal = page_templates.frames_per_page_vocabulary(orientation)[-2]
    r = reglages(orientation=orientation, frames_par_page=cardinal,
                 champ=champ)
    ecran = reglages_pdf.EcranReglagesDesPlanches(r)
    lignes, _rang, _etats = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
    utile = jetons.largeur_utile()
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= utile, repr(ligne)
    assert jetons.colonnes(r.ligne_d_etat(ascii_seul)) <= utile
    assert jetons.colonnes(r.raccourcis()) <= utile


def test_le_repli_ascii_garde_le_second_canal():
    """Le point vert devient une **asterisque**, et rien d'autre ne bouge."""
    r = reglages(orientation="paysage", frames_par_page=6)
    utf8 = r.lignes_de_la_liste()
    repli = r.lignes_de_la_liste(ascii_seul=True)
    assert len(utf8) == len(repli)
    marquees_utf8 = [rang for rang, ligne in enumerate(utf8)
                     if jetons.GLYPHES["complete"] in ligne]
    marquees_ascii = [rang for rang, ligne in enumerate(repli)
                      if jetons.GLYPHES_ASCII["complete"] in ligne]
    assert marquees_utf8 == marquees_ascii
    assert all("●" not in ligne for ligne in repli)


def test_la_ligne_d_etat_ne_porte_aucune_touche():
    """`EPIC11-ARB-56` : ni touche, ni conseil d'usage, ni motif de conception."""
    r = reglages(orientation="paysage", frames_par_page=6)
    for ligne in (r.mesure(), r.ligne_d_etat()):
        for touche in ("Tab", "Échap", "F1", "⏎", "Entrée"):
            assert touche not in ligne


# ===========================================================================
# `EPIC11-ARB-180` -- un champ exclusif FOCALISE porte les DEUX glyphes
# ===========================================================================

def _lignes_des_cardinaux(r, ascii_seul: bool = False) -> dict[int, str]:
    """Les lignes de la liste des geometries, indexees par cardinal."""
    bilan = r.bilan()
    return {cardinal: r.ligne_de_cardinal(bilan.de(r.orientation, cardinal),
                                          ascii_seul=ascii_seul)
            for cardinal in r.cardinaux()}


def test_ARB_180_le_champ_FOCALISE_porte_la_fleche_ET_la_puce():
    """`EPIC11-ARB-180`, tranche par Egan le 2026-09-02.

    `EPIC11-ARB-126` dit « **Flèche seule ! C'est uniquement dans les listes à
    cocher qu'on trouve les deux.** », mais son tableau n'oppose que « liste
    d'issues » et « liste a cocher ». La liste des geometries n'est ni l'une ni
    l'autre : c'est un **champ exclusif de formulaire**, et il ne porte la
    fleche que **quand la zone a le focus**. C'est le TROISIEME cas du tableau,
    enterine plutot que corrige -- retirer la fleche couterait un observable
    pour rendre l'ecran MOINS informatif : on ne saurait plus quelle geometrie
    `Entree` va retenir.

    **Le produit le faisait deja et rien ne le mesurait** -- exactement l'etat
    qu'un arbitrage enterinant laisse derriere lui s'il ne s'accompagne pas
    d'une mesure. La cible est **au milieu** de la liste, jamais en tete ni en
    queue (regle des fabriques).
    """
    r = reglages(champ=reglages_pdf.CHAMP_CARDINAL)
    cardinaux = r.cardinaux()
    assert len(cardinaux) >= 3, cardinaux
    cible = cardinaux[len(cardinaux) // 2]
    r.frames_par_page = cible
    assert cible not in (cardinaux[0], cardinaux[-1]), (cible, cardinaux)

    glyphes = jetons.glyphes()
    lignes = _lignes_des_cardinaux(r)
    portant_la_fleche = {c for c, ligne in lignes.items()
                         if glyphes["curseur"] in ligne}
    portant_la_puce = {c for c, ligne in lignes.items()
                       if glyphes["exclusif-retenu"] in ligne}

    # les deux ensembles sont EGAUX et valent la cible : la fleche dit ou est
    # le curseur, la puce ce qui est retenu, et sur cet ecran les deux
    # coincident -- une selection differee serait un etat que le dessin ne sait
    # pas montrer.
    assert portant_la_fleche == {cible}
    assert portant_la_puce == {cible}


def test_ARB_180_hors_focus_la_fleche_DISPARAIT_et_la_puce_reste():
    """Le second volet, sans lequel le premier ne dit rien.

    Si la fleche etait posee quel que soit le champ, l'ecran porterait deux
    curseurs a la fois -- ce qu'`EPIC11-ARB-50` interdit --, et le premier test
    passerait quand meme. C'est la **disparition** hors focus qui fait de ce
    cas un troisieme cas et non une violation d'`ARB-126`.
    """
    r = reglages(champ="valider")
    cardinaux = r.cardinaux()
    r.frames_par_page = cardinaux[len(cardinaux) // 2]

    glyphes = jetons.glyphes()
    lignes = _lignes_des_cardinaux(r)
    assert {c for c, ligne in lignes.items()
            if glyphes["curseur"] in ligne} == set()
    assert {c for c, ligne in lignes.items()
            if glyphes["exclusif-retenu"] in ligne} == {r.frames_par_page}


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_ARB_180_tient_AUSSI_en_repli_ASCII(ascii_seul):
    """Le repli ne doit pas confondre les deux marques.

    `jetons` garantit l'injectivite de son repli ; on le mesure ici sur les
    deux glyphes qui se cotoient, parce que c'est le seul endroit du depot ou
    ils se cotoient.
    """
    r = reglages(champ=reglages_pdf.CHAMP_CARDINAL)
    cardinaux = r.cardinaux()
    cible = cardinaux[len(cardinaux) // 2]
    r.frames_par_page = cible

    glyphes = jetons.glyphes(ascii_seul)
    assert glyphes["curseur"] != glyphes["exclusif-retenu"]
    ligne = _lignes_des_cardinaux(r, ascii_seul)[cible]
    assert glyphes["curseur"] in ligne
    assert glyphes["exclusif-retenu"] in ligne


# ===========================================================================
# Le FOCUS se voit -- les quatre champs sont distinguables a l'ecran
# ===========================================================================
#
# **Le defaut, rapporte par Egan le 2026-09-06 : « la fleche de selection est
# absente de l'ecran de parametrage pdf. On agit a l'aveugle sur cet ecran. »**
#
# Mesure : le glyphe `>` de `DESIGN.md` §7.3 -- « Le champ au focus porte `>` ;
# les autres, un espace » -- n'etait pose que dans `ligne_du_bouton`. Sur
# `CHAMP_ORIENTATION` et `CHAMP_MARGE`, l'ecran ne montrait RIEN, et les deux
# corps rendus etaient identiques au caractere pres : `↑` ne disait pas ce
# qu'il allait changer.
#
# **Ce que ce banc mesurait deja et pourquoi il est reste vert** : les deux
# confrontations aux dessins portent sur `E5-2` (focus sur `Valider`) et
# `E5-2b` (focus dans la liste), c'est-a-dire sur les deux SEULS etats qui
# marchaient. Aucune maquette ne dessine le focus sur les deux autres champs,
# donc aucune confrontation ne pouvait les voir. La mesure qui manquait n'est
# pas une confrontation de plus : c'est une PROPRIETE portant sur les quatre
# etats a la fois, et elle ne demande aucun dessin neuf.


@pytest.mark.parametrize("ascii_seul", [False, True],
                         ids=["utf8", "ascii"])
def test_les_QUATRE_champs_rendent_QUATRE_corps_DISTINCTS(ascii_seul):
    """« On agit a l'aveugle » se mesure comme ceci, et pas autrement.

    Deux champs qui rendent le meme corps sont indiscernables a l'ecran, quel
    que soit ce que chacun affiche par ailleurs. La propriete porte donc sur
    les QUATRE etats pris ensemble -- une assertion par champ, prise isolement,
    resterait verte sur deux corps jumeaux.

    Les deux modes sont joues : une garde qui ne fait varier aucun de ses
    drapeaux ne mesure qu'un chemin (`CLAUDE.md`, 2026-09-06), et le glyphe de
    focus a precisement un repli ASCII.
    """
    corps_par_champ = {
        champ: tuple(
            ligne.rstrip() for ligne in
            reglages_pdf.EcranReglagesDesPlanches(reglages(champ=champ))
            .composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0])
        for champ in reglages_pdf.CHAMPS}
    distincts = set(corps_par_champ.values())
    assert len(distincts) == len(reglages_pdf.CHAMPS), {
        champ: corps_par_champ[champ] for champ in reglages_pdf.CHAMPS
        if list(corps_par_champ.values()).count(corps_par_champ[champ]) > 1}


@pytest.mark.parametrize("ascii_seul", [False, True],
                         ids=["utf8", "ascii"])
@pytest.mark.parametrize("champ", reglages_pdf.CHAMPS)
def test_le_champ_au_FOCUS_porte_sa_marque_et_les_autres_NON(champ,
                                                             ascii_seul):
    """Chaque champ porte une marque au focus, et une seule ligne la porte.

    **Les deux volets sont necessaires.** Le premier attrape le champ oublie --
    c'est le defaut d'Egan. Le second attrape son symetrique, une marque restee
    collee sur une ligne qui n'a plus le focus : deux marques a l'ecran valent
    zero, l'operateur ne sait toujours pas ou il est.

    La marque n'est pas la meme partout, et ce n'est pas une incoherence : le
    formulaire porte `>` (`DESIGN.md` §7.3, `jetons` « invite »), la liste des
    cardinaux porte `▸` (le curseur d'un choix exclusif, ce que `E5-2b`
    dessine). Le banc lit les deux glyphes dans `jetons`, jamais un litteral.
    """
    table = jetons.glyphes(ascii_seul)
    marques = (table["invite"], table["curseur"])
    corps_rendu = [
        ligne.rstrip() for ligne in
        reglages_pdf.EcranReglagesDesPlanches(reglages(champ=champ))
        .composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0]]
    porteuses = [ligne for ligne in corps_rendu
                 if any(f"{marque} " in ligne for marque in marques)]
    assert len(porteuses) == 1, (champ, porteuses, corps_rendu)


@pytest.mark.parametrize("ascii_seul", [False, True],
                         ids=["utf8", "ascii"])
def test_la_marque_de_focus_n_a_PAS_bouge_les_colonnes(ascii_seul):
    """Frontiere negative : le glyphe OUVRE sa colonne, il ne pousse rien.

    Sans elle, un correctif qui insere `>` devant la valeur alignerait
    differemment le champ au focus et les autres -- la valeur sauterait de deux
    colonnes a chaque deplacement du focus, ce qui est un second defaut de
    lecture la ou on venait d'en fermer un.

    La mesure est la colonne ou commence la VALEUR, prise sur le meme champ
    avec et sans focus.
    """
    def colonne_de_la_valeur(champ_au_focus: str) -> int:
        modele = reglages(champ=champ_au_focus)
        ligne = modele.ligne_de_l_orientation(ascii_seul)
        return jetons.colonnes(ligne[:ligne.index("(")])

    assert (colonne_de_la_valeur(reglages_pdf.CHAMP_ORIENTATION)
            == colonne_de_la_valeur(reglages_pdf.CHAMP_MARGE))


def test_la_marque_de_focus_est_LUE_dans_le_mode_et_pas_seulement_appelee():
    """Frontiere ANTI-TAUTOLOGIE : `_tete_de_champ` SUIT `ascii_seul`.

    **Elle ferme un mutant qui avait survecu** (campagne du 2026-09-06,
    93 verts) : figer le mode a `jetons.glyphes(False)` ne rougissait rien,
    parce que le glyphe `invite` vaut `>` dans les DEUX modes -- mesure a
    l'instant, contre `curseur` qui vaut `▸` puis `>`. Le mutant etait donc
    equivalent SOUS LA TABLE DU JOUR, et seulement sous elle.

    C'est la famille de defaut que le depot a payee deux fois la meme nuit
    (`PHRASE_DERNIER_LOT`, et le bandeau de `coque` qui n'a jamais passe
    `ascii_seul`) : une mesure qui epingle la PRESENCE d'un appel, jamais son
    USAGE, cesse de mesurer des que la valeur change. La greffe pose donc une
    table ou les deux modes DIFFERENT sur ce glyphe -- ce que la table
    d'aujourd'hui ne fait pas.
    """
    from unittest import mock

    reelle = jetons.glyphes

    def table_greffee(ascii_seul=False):
        table = dict(reelle(ascii_seul))
        table["invite"] = "#" if ascii_seul else ">"
        return table

    modele = reglages(champ=reglages_pdf.CHAMP_ORIENTATION)
    with mock.patch.object(reglages_pdf.jetons, "glyphes", table_greffee):
        utf8 = modele.ligne_de_l_orientation(False)
        ascii_ = modele.ligne_de_l_orientation(True)
    assert "> " in utf8 and "# " not in utf8, utf8
    assert "# " in ascii_ and "> " not in ascii_, ascii_
