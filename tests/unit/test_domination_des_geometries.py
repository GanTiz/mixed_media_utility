"""Banc de la domination des mises en page (story 11.7, lot B8 -- AC 5.4).

**Ce que ce banc mesure.** Une mise en page -- un couple orientation x cardinal
de frames par page -- est **dominee** si une autre rend une surface de dessin
**>=** pour un nombre de planches **<=**, avec au moins une inegalite stricte.
`EPIC11-ARB-154` exige que ce verdict soit « calcule par le produit et **jamais
recopie** », et `EPIC11-ARB-173` en fait la seule marque de l'ecran de reglages
(vert + glyphe + legende). Aucune fonction du depot ne comparait deux
geometries avant ce lot : c'est du travail neuf de coeur, pas un deplacement.

**Les quatre pieges que ce banc vise nommement.**

1. *La grille deduite.* La surface de dessin se lit aux **zones** du gabarit
   (`frame_zones_mm`), passees dans `frame_image_rect_mm` ; la deduire d'un
   nombre de colonnes et de rangees est ce qui a melange les geometries v1 et
   v2 le 2026-09-01. La frontiere est **negative et a l'AST** : l'ensemble des
   symboles du module que le calcul touche est mesure **exact**, ce qui attrape
   aussi bien un `_grid_shape` qui reviendrait qu'un symbole neuf non declare.
2. *Le produit oublie.* Le calcul porte sur les **deux** orientations alors que
   l'ecran n'en montre qu'une. Le banc mesure la seule entree du vocabulaire
   dont le verdict change selon qu'on calcule sur le produit ou sur la seule
   orientation affichee -- paysage 6f -- : sur son orientation seule, elle
   serait marquee non dominee, c'est-a-dire un glyphe **faux**, pas incomplet.
3. *L'arrondi global.* Les planches s'arrondissent **par lot**. Deux lots de
   124 et 40 frames a 3 frames par page font 42 + 14 = **56** planches et non
   `ceil(164 / 3) = 55`. Un banc a un seul lot ne distingue pas les deux
   formules -- il rendrait vert sur le mutant.
4. *L'inegalite stricte disparue.* Sans elle toute mise en page se domine
   elle-meme et l'ensemble des non dominees est vide. Elle est mesuree
   separement du reste, sur une fabrique.

**Fabrique** (`CLAUDE.md`, regle des fabriques ; politique de revue §6.1) : la
comparaison pure se mesure sur **trois** mises en page aux valeurs
**distinguables** -- trois surfaces et trois cardinaux de pages differents --,
la cible **au milieu**, et **dans les deux orientations**. Trois plutot que
deux : a deux elements la cible en seconde position est aussi en derniere, et
un mutant de terminaison de boucle (`continue` -> `break`) y est indiscernable
d'un parcours complet. La position est verifiee sur la liste que **le code
parcourt** -- un test mesure explicitement que le produit rendu n'est ni trie
ni filtre, donc que les deux listes coincident.

**Les valeurs epinglees et celles qui ne le sont pas.** Les tables de
domination et de pagination ci-dessous sont des mesures de reference de la
geometrie v2, identiques a celles que la maquette `E5-2` porte ; elles sont
epinglees parce que c'est l'AC. Aucune surface n'est en revanche recopiee : les
tests de mesure les recalculent depuis le **vrai producteur**
(`frame_zones_mm` + `frame_image_rect_mm`) et confrontent chaque famille de
valeurs projetee -- largeur, hauteur, surface en mm², surface en cm²,
`template_id`. Les constantes du coeur (marge par defaut, version de geometrie,
vocabulaire) sont **nommees**, jamais recopiees.
"""

from __future__ import annotations

import ast
import inspect
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import page_templates, pdf_composition  # noqa: E402

#: Les deux lots de `projet_demo`, de tailles **differentes** : c'est ce qui
#: rend l'arrondi par lot mesurable. `plan-04_25` porte 124 frames et
#: `plan-04_8` en porte 40.
LOTS_DE_REFERENCE = (124, 40)

#: Verdict de domination mesure sur la geometrie v2, A4, marge par defaut, pour
#: les deux lots ci-dessus : pour **chaque** mise en page du produit, l'ensemble
#: **exact** de ses dominants. Un ensemble exact et non une appartenance : « X
#: est dominee par Y » laisserait passer un dominant surnumeraire, c'est-a-dire
#: exactement ce qu'un `>=` devenu `>` ou un `<=` devenu `<` produit.
DOMINANTS_ATTENDUS = {
    ("portrait", 1): {("portrait", 2), ("paysage", 1)},
    ("portrait", 2): set(),
    ("portrait", 3): set(),
    ("portrait", 4): {("paysage", 4)},
    ("portrait", 8): set(),
    ("paysage", 1): set(),
    ("paysage", 2): {("portrait", 2)},
    ("paysage", 4): set(),
    ("paysage", 6): {("portrait", 8)},
    ("paysage", 8): {("portrait", 8)},
}

#: Planches **par lot** de chaque mise en page, pour `LOTS_DE_REFERENCE`.
PAGES_PAR_LOT_ATTENDUES = {
    ("portrait", 1): (124, 40),
    ("portrait", 2): (62, 20),
    ("portrait", 3): (42, 14),
    ("portrait", 4): (31, 10),
    ("portrait", 8): (16, 5),
    ("paysage", 1): (124, 40),
    ("paysage", 2): (62, 20),
    ("paysage", 4): (31, 10),
    ("paysage", 6): (21, 7),
    ("paysage", 8): (16, 5),
}


def produit_attendu() -> tuple[tuple[str, int], ...]:
    """Le produit des deux orientations, **lu du vocabulaire du coeur**.

    Jamais une liste de cardinaux recopiee : le vocabulaire retire le 6 en
    portrait, et le recopier ici ferait de ce banc une seconde redaction du
    vocabulaire au lieu d'une mesure.
    """
    return tuple(
        (orientation, cardinal)
        for orientation in page_templates.ORIENTATIONS
        for cardinal in page_templates.frames_per_page_vocabulary(
            orientation, page_templates.DEFAULT_GEOMETRY_VERSION
        )
    )


# --- Fabrique de la comparaison pure ---------------------------------------


def mise(orientation: str, cardinal: int, surface_mm2: float,
         pages_par_lot: tuple[int, ...]) -> page_templates.MiseEnPageMesuree:
    """Une mise en page de fabrique, de surface **choisie**.

    La surface est portee par la largeur, la hauteur restant a 1 mm : c'est la
    surface que la comparaison lit, et la fabrique n'a pas a simuler un 16:9
    pour mesurer un comparateur.
    """
    return page_templates.MiseEnPageMesuree(
        orientation=orientation,
        frames_per_page=cardinal,
        template_id=f"fabrique-{orientation}-{cardinal}f",
        largeur_mm=surface_mm2,
        hauteur_mm=1.0,
        pages_par_lot=pages_par_lot,
    )


def trois_mises_en_page_cible_au_milieu(
    orientation_cible: str, orientation_dominante: str
) -> tuple[page_templates.MiseEnPageMesuree, ...]:
    """Trois mises en page distinguables, la **cible au milieu**.

    * en **premiere** position, une mise en page qui ne domine rien : petite
      surface et beaucoup de pages ;
    * au **milieu**, la cible -- surface moyenne, pages moyennes ;
    * en **derniere** position, la seule qui domine la cible, et elle est de
      l'**autre** orientation.

    Trois valeurs distinctes partout (surfaces 10 / 20 / 30, pages 9 / 6 / 3) :
    un remplissage uniforme rendrait toute permutation invisible. Le dominant
    est en queue **et** dans l'autre orientation, ce qui fait de ce jeu la
    mesure conjointe de deux mutants : un parcours qui s'arrete au premier
    element (`break`) et un calcul qui ne regarderait que l'orientation de la
    cible.
    """
    return (
        mise(orientation_cible, 1, surface_mm2=10.0, pages_par_lot=(5, 4)),
        mise(orientation_cible, 2, surface_mm2=20.0, pages_par_lot=(4, 2)),
        mise(orientation_dominante, 4, surface_mm2=30.0, pages_par_lot=(2, 1)),
    )


# --- B8.1 : la fonction vit dans `page_templates`, jamais dans `tui/` -------


def test_les_pieces_de_la_domination_vivent_dans_page_templates():
    """B8.1 -- le calcul est un objet du coeur, a cote du vocabulaire."""
    pieces = (
        page_templates.MiseEnPageMesuree,
        page_templates.BilanDeDomination,
        page_templates.surface_de_dessin_mm,
        page_templates.mesurer_les_mises_en_page,
        page_templates.domine,
        page_templates.dominants_des_mises_en_page,
        page_templates.bilan_de_domination,
    )
    assert {piece.__module__ for piece in pieces} == {
        "mixed_media_utility.page_templates"
    }


def test_aucun_module_de_la_tui_ne_mesure_ni_ne_compare_une_geometrie():
    """B8.1 -- frontiere **negative** : la TUI lit un bilan, elle n'en fait pas.

    Elle est negative parce qu'aucun test positif ne verrait revenir une
    seconde redaction : un ecran qui recalculerait la domination afficherait
    des glyphes plausibles, et rien n'echouerait. L'ensemble mesure est celui
    des modules **fautifs**, et il est exact : vide.
    """
    interdits = {
        "frame_zones_mm",
        "frame_image_rect_mm",
        "surface_de_dessin_mm",
        "dominants_des_mises_en_page",
        "_grid_shape",
        "_drawing_area_mm2",
    }
    fautifs = {}
    for module in sorted((REPO_ROOT / "src" / "mixed_media_utility" / "tui").glob("*.py")):
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        touches = {
            noeud.attr for noeud in ast.walk(arbre) if isinstance(noeud, ast.Attribute)
        } | {
            noeud.id for noeud in ast.walk(arbre) if isinstance(noeud, ast.Name)
        }
        if touches & interdits:
            fautifs[module.name] = sorted(touches & interdits)
    assert fautifs == {}


# --- B8.2 : les zones, puis le rectangle 16:9 -- jamais la grille -----------

#: Symboles de `page_templates` que le calcul de domination a le droit de
#: toucher. **Ensemble exact** : un symbole en trop est un finding, qu'il
#: s'agisse d'une deduction de grille qui revient ou d'un chemin neuf que
#: personne n'a declare.
SYMBOLES_AUTORISES = {
    # Les deux outils de declaration, importes par le module et donc visibles
    # comme des attributs de celui-ci: le decorateur des deux dataclasses et le
    # type de la table de dominants.
    "dataclass",
    "Mapping",
    "DEFAULT_GEOMETRY_VERSION",
    "DEFAULT_MARGIN_PRESET",
    "ORIENTATIONS",
    "UnknownTemplateError",
    "MiseEnPageMesuree",
    "BilanDeDomination",
    "frame_image_rect_mm",
    "frames_per_page_vocabulary",
    "template_for",
    "surface_de_dessin_mm",
    "mesurer_les_mises_en_page",
    "domine",
    "dominants_des_mises_en_page",
}

#: Ce que la deduction de grille sortirait, et qui ne doit jamais apparaitre.
#: Redondant avec l'ensemble exact ci-dessus **a dessein** : c'est ce nom-la
#: qu'une revue lit quand le test rougit.
SYMBOLES_DE_DEDUCTION_DE_GRILLE = {
    "_grid_shape",
    "_drawing_area_mm2",
    "grid_columns",
    "grid_rows",
    "FRAMES_PER_PAGE_VOCABULARY",
}


def _symboles_touches() -> set[str]:
    """Tous les noms et attributs cites par le calcul de domination."""
    touches: set[str] = set()
    for piece in (
        page_templates.MiseEnPageMesuree,
        page_templates.BilanDeDomination,
        page_templates.surface_de_dessin_mm,
        page_templates.mesurer_les_mises_en_page,
        page_templates.domine,
        page_templates.dominants_des_mises_en_page,
        page_templates.bilan_de_domination,
    ):
        arbre = ast.parse(inspect.getsource(piece))
        touches |= {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        touches |= {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
    return touches


def test_le_calcul_ne_touche_aucun_symbole_de_deduction_de_grille():
    """B8.2 -- frontiere negative nommee : la grille ne se deduit jamais."""
    assert _symboles_touches() & SYMBOLES_DE_DEDUCTION_DE_GRILLE == set()


def test_l_ensemble_des_symboles_du_module_touches_est_exact():
    """B8.2 -- ensemble **exact**, pas une appartenance.

    Une assertion positive (« il appelle bien `frame_image_rect_mm` ») laisse
    passer toute divergence supplementaire : c'est le defaut que la vague 3 de
    l'Epic 11 a paye. L'ensemble exact mesure l'appel voulu **et** son unicite.
    """
    du_module = {
        nom for nom in _symboles_touches() if hasattr(page_templates, nom)
    }
    assert du_module == SYMBOLES_AUTORISES


def test_les_deux_pieces_obligatoires_sont_bien_citees():
    """B8.2 -- volet **positif** : les zones du gabarit, puis le 16:9 inscrit."""
    source_mesure = inspect.getsource(page_templates.mesurer_les_mises_en_page)
    source_surface = inspect.getsource(page_templates.surface_de_dessin_mm)
    assert "frame_zones_mm" in source_mesure
    assert "frame_image_rect_mm" in source_surface


@pytest.mark.parametrize("margin_preset", sorted(page_templates.MARGIN_PRESETS_MM))
def test_chaque_surface_mesuree_est_celle_du_vrai_producteur(margin_preset):
    """B8.2 -- confrontation au vrai producteur, sur **chaque** famille de valeurs.

    Un test d'integration contre le vrai producteur ne suffit pas s'il n'assert
    pas sur chaque famille projetee (`EPIC5-ARB-39`) : largeur, hauteur, les
    deux surfaces derivees et le `template_id` sont donc tous confrontes, sur
    les trois presets de marge.
    """
    mesures = page_templates.mesurer_les_mises_en_page(
        LOTS_DE_REFERENCE, margin_preset=margin_preset
    )
    assert tuple(m.cle for m in mesures) == produit_attendu()
    for mesuree in mesures:
        spec = page_templates.template_for(
            mesuree.orientation, mesuree.frames_per_page, margin_preset
        )
        rects = [
            page_templates.frame_image_rect_mm(zone, spec.margin_mm)
            for zone in spec.frame_zones_mm
        ]
        largeur, hauteur = min(rects, key=lambda r: r[2] * r[3])[2:]
        assert mesuree.template_id == spec.template_id
        assert mesuree.largeur_mm == largeur
        assert mesuree.hauteur_mm == hauteur
        assert mesuree.surface_mm2 == largeur * hauteur
        assert mesuree.surface_cm2 == largeur * hauteur / 100.0


def test_la_plus_petite_zone_est_retenue_et_elle_est_au_milieu():
    """B8.2 -- fabrique de zones : ni la premiere, ni la derniere.

    Trois zones **distinguables**, la plus petite au **milieu**. Prendre la
    premiere zone -- ce que la geometrie v2 rendrait indiscernable, ses zones
    etant toutes egales -- est exactement le mutant que cette fabrique tue.
    """
    zones = [
        {"name": "grande", "x": 0.0, "y": 0.0, "width": 160.0, "height": 90.0},
        {"name": "petite", "x": 0.0, "y": 0.0, "width": 32.0, "height": 18.0},
        {"name": "moyenne", "x": 0.0, "y": 0.0, "width": 80.0, "height": 45.0},
    ]
    assert page_templates.surface_de_dessin_mm(zones, 0.0) == (32.0, 18.0)


def test_les_zones_de_la_geometrie_v2_sont_toutes_egales():
    """B8.2 -- la mesure qui autorise le raccourci, faite plutot que supposee.

    Elle n'est pas decorative : c'est elle qui dit que le minimum retenu
    ci-dessus vaut la valeur commune sur la geometrie livree. Le jour ou une
    version composerait des zones inegales, ce test rougit et le choix du
    minimum redevient une decision a prendre, plutot qu'un silence.
    """
    inegaux = {}
    for margin_preset in page_templates.MARGIN_PRESETS_MM:
        for orientation, cardinal in produit_attendu():
            spec = page_templates.template_for(orientation, cardinal, margin_preset)
            surfaces = {
                round(rect[2] * rect[3], 9)
                for rect in (
                    page_templates.frame_image_rect_mm(zone, spec.margin_mm)
                    for zone in spec.frame_zones_mm
                )
            }
            if len(surfaces) != 1:
                inegaux[spec.template_id, margin_preset] = sorted(surfaces)
    assert inegaux == {}


def test_une_mise_en_page_sans_zone_est_un_refus_explicite():
    """B8.2 -- une surface introuvable ne se rend pas comme une surface nulle."""
    with pytest.raises(page_templates.UnknownTemplateError):
        page_templates.surface_de_dessin_mm((), 0.0)


# --- B8.3 : le produit des deux orientations -------------------------------


def test_le_produit_porte_les_deux_orientations_en_entier():
    """B8.3 -- ensemble **exact** : ni une orientation, ni un sous-ensemble."""
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    assert tuple(m.cle for m in bilan.mises_en_page) == produit_attendu()
    assert set(bilan.dominants) == set(produit_attendu())


def test_chaque_mise_en_page_a_exactement_ces_dominants():
    """B8.3 -- la table de domination entiere, en ensembles exacts.

    C'est le test qui porte l'AC. Les ensembles exacts attrapent les deux
    mutants de comparateur que l'ensemble des non dominees, seul, laisse
    passer : `>=` -> `>` ne change pas qui est marque, il change **par qui**
    (portrait 1f perd son dominant a surface egale, portrait 2f).
    """
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    mesure = {
        cle: {dominant.cle for dominant in bilan.dominants_de(*cle)}
        for cle in produit_attendu()
    }
    assert mesure == DOMINANTS_ATTENDUS


def test_l_ensemble_des_non_dominees_est_exactement_celui_la():
    """B8.3 -- les cinq entrees que le glyphe `●` marque, et rien d'autre."""
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    attendues = {cle for cle, dom in DOMINANTS_ATTENDUS.items() if not dom}
    assert {m.cle for m in bilan.non_dominees()} == attendues
    assert attendues != set()


def test_le_verdict_de_paysage_6f_CHANGE_si_l_on_ignore_l_autre_orientation():
    """B8.3 -- la mesure qui prouve que le produit compte.

    Paysage 6f n'est dominee par **aucune** combinaison de son orientation ;
    elle l'est par portrait 8f, qui fait mieux sur les **deux** criteres a la
    fois. Un calcul restreint a l'orientation affichee lui poserait donc le
    glyphe, c'est-a-dire un verdict **faux** et non incomplet -- et aucune
    mesure faite sur le seul paysage ne pourrait le voir.
    """
    produit = page_templates.mesurer_les_mises_en_page(LOTS_DE_REFERENCE)
    paysage_seul = tuple(m for m in produit if m.orientation == "paysage")
    dominants_du_paysage_seul = page_templates.dominants_des_mises_en_page(paysage_seul)

    assert dominants_du_paysage_seul[("paysage", 6)] == ()

    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    assert {d.cle for d in bilan.dominants_de("paysage", 6)} == {("portrait", 8)}
    assert bilan.est_dominee("paysage", 6)


def test_la_liste_d_une_orientation_est_exactement_son_vocabulaire():
    """B8.3 -- `EPIC11-ARB-154` : on guide, on n'interdit pas.

    Aucune entree dominee n'est retiree de la liste que l'ecran affiche.
    """
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    for orientation in page_templates.ORIENTATIONS:
        vocabulaire = page_templates.frames_per_page_vocabulary(
            orientation, page_templates.DEFAULT_GEOMETRY_VERSION
        )
        affichee = bilan.de_l_orientation(orientation)
        assert tuple(m.frames_per_page for m in affichee) == vocabulaire
        assert any(bilan.est_dominee(*m.cle) for m in affichee)


# --- B8.4 : les pages s'arrondissent PAR LOT --------------------------------


def test_les_pages_par_lot_sont_exactement_celles_la():
    """B8.4 -- deux lots de tailles differentes, planche par planche."""
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    mesure = {cle: bilan.de(*cle).pages_par_lot for cle in produit_attendu()}
    assert mesure == PAGES_PAR_LOT_ATTENDUES


def test_le_total_est_la_somme_des_arrondis_jamais_l_arrondi_de_la_somme():
    """B8.4 -- 42 + 14 = 56, et surtout **pas** `ceil(164 / 3) = 55`.

    Le papier ne se partage pas entre deux lots : la derniere planche d'un lot
    reste a moitie vide, elle n'accueille pas les frames du suivant.
    """
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    trois_frames_par_page = bilan.de("portrait", 3)
    assert trois_frames_par_page.pages_par_lot == (42, 14)
    assert trois_frames_par_page.pages == 56
    assert trois_frames_par_page.pages != math.ceil(sum(LOTS_DE_REFERENCE) / 3)


def test_un_seul_lot_ne_distinguerait_pas_les_deux_formules():
    """B8.4 -- pourquoi la fabrique porte **deux** lots et pas un.

    Sur un lot unique de 164 frames, la somme des arrondis et l'arrondi de la
    somme coincident pour **tous** les cardinaux du vocabulaire : un banc a un
    seul lot rendrait vert sur le mutant, quelle que soit sa richesse par
    ailleurs. Avec les deux lots reels, l'ensemble **exact** des cardinaux qui
    les separent est `{3}` -- une seule entree du produit porte la mesure, et
    la perdre serait invisible.
    """
    un_seul_lot = page_templates.bilan_de_domination((sum(LOTS_DE_REFERENCE),))
    separateurs_a_un_lot = {
        m.frames_per_page
        for m in un_seul_lot.mises_en_page
        if m.pages != math.ceil(sum(LOTS_DE_REFERENCE) / m.frames_per_page)
    }
    assert separateurs_a_un_lot == set()

    deux_lots = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    separateurs_a_deux_lots = {
        m.frames_per_page
        for m in deux_lots.mises_en_page
        if m.pages != math.ceil(sum(LOTS_DE_REFERENCE) / m.frames_per_page)
    }
    assert separateurs_a_deux_lots == {3}


def test_deux_lots_d_autres_tailles_deplacent_les_cardinaux_separateurs():
    """B8.4 -- le `{3}` ci-dessus n'est pas une propriete du cardinal 3.

    Sur deux lots de 5 et 5 frames, ce sont les cardinaux **2 et 4** qui
    separent les deux formules, et plus le 3 -- qui, lui, redevient d'accord
    avec l'arrondi global. Sans cette seconde paire, le test precedent se
    lirait comme un fait sur la geometrie ; il est un fait sur les **tailles
    des lots**, et les deux ensembles sont ici **disjoints**.
    """
    petits_lots = (5, 5)
    bilan = page_templates.bilan_de_domination(petits_lots)
    separateurs = {
        m.frames_per_page
        for m in bilan.mises_en_page
        if m.pages != math.ceil(sum(petits_lots) / m.frames_per_page)
    }
    assert separateurs == {2, 4}
    assert separateurs & {3} == set()
    assert bilan.de("portrait", 2).pages_par_lot == (3, 3)
    assert bilan.de("portrait", 2).pages == 6


def test_la_pagination_est_celle_du_coeur_et_non_une_seconde_redaction():
    """B8.4 -- chaque compte par lot vient de `nombre_de_planches`."""
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    for mesuree in bilan.mises_en_page:
        assert mesuree.pages_par_lot == tuple(
            pdf_composition.nombre_de_planches(frames, mesuree.frames_per_page)
            for frames in LOTS_DE_REFERENCE
        )


def test_un_cardinal_de_frames_absurde_est_refuse_par_le_coeur():
    """B8.4 -- le refus de la pagination du coeur traverse, il ne s'avale pas."""
    with pytest.raises(pdf_composition.LotContentError):
        page_templates.bilan_de_domination((-1,))


# --- B8.5 : la comparaison pure, sur trois mises en page, cible au milieu ----


@pytest.mark.parametrize(
    "orientation_cible, orientation_dominante",
    [("portrait", "paysage"), ("paysage", "portrait")],
)
def test_la_cible_du_milieu_trouve_son_dominant_en_queue(
    orientation_cible, orientation_dominante
):
    """B8.5 -- trois mises en page, cible au milieu, **les deux orientations**.

    Le dominant est le **dernier** element : un parcours qui s'arreterait au
    premier (`break`) rendrait la cible non dominee. Et il est de l'**autre**
    orientation : un calcul qui filtrerait sur l'orientation de la cible
    rendrait le meme faux verdict, par un autre chemin.
    """
    produit = trois_mises_en_page_cible_au_milieu(
        orientation_cible, orientation_dominante
    )
    cible = produit[1]
    dominants = page_templates.dominants_des_mises_en_page(produit)

    assert {d.cle for d in dominants[cible.cle]} == {(orientation_dominante, 4)}
    assert dominants[produit[0].cle] != ()
    assert dominants[produit[2].cle] == ()


@pytest.mark.parametrize(
    "orientation_cible, orientation_dominante",
    [("portrait", "paysage"), ("paysage", "portrait")],
)
def test_le_produit_rendu_n_est_ni_trie_ni_filtre(
    orientation_cible, orientation_dominante
):
    """B8.5 -- la position se verifie sur la liste que **le code** parcourt.

    Sans cette mesure, « la cible est au milieu » serait un fait sur la
    fabrique et non sur le parcours : un tri interne la deplacerait sans que
    rien ne le dise.
    """
    produit = trois_mises_en_page_cible_au_milieu(
        orientation_cible, orientation_dominante
    )
    dominants = page_templates.dominants_des_mises_en_page(produit)
    assert tuple(dominants) == tuple(m.cle for m in produit)

    bilan = page_templates.BilanDeDomination(
        mises_en_page=produit, dominants=dominants
    )
    assert tuple(m.cle for m in bilan.mises_en_page) == tuple(m.cle for m in produit)


def test_un_produit_qui_porte_deux_fois_la_meme_cle_est_refuse():
    """B8.5 -- deux entrees de meme cle rendraient la moitie du bilan muette."""
    doublon = (
        mise("portrait", 2, surface_mm2=10.0, pages_par_lot=(3,)),
        mise("portrait", 2, surface_mm2=20.0, pages_par_lot=(2,)),
    )
    with pytest.raises(page_templates.UnknownTemplateError):
        page_templates.dominants_des_mises_en_page(doublon)


# --- Le comparateur lui-meme, terme a terme ---------------------------------


def test_une_surface_egale_et_moins_de_pages_domine():
    """`>=` sur la surface : c'est ce cas qui le distingue d'un `>`.

    Mesure reelle du vocabulaire : portrait 1f et portrait 2f rendent
    **exactement** la meme surface de dessin ; le 1f n'est donc domine par le
    2f que si la comparaison de surface accepte l'egalite.
    """
    petite = mise("portrait", 1, surface_mm2=100.0, pages_par_lot=(8,))
    grande = mise("portrait", 2, surface_mm2=100.0, pages_par_lot=(4,))
    assert page_templates.domine(grande, petite)
    assert not page_templates.domine(petite, grande)


def test_une_surface_superieure_a_pages_egales_domine():
    """`<=` sur les pages : c'est ce cas qui le distingue d'un `<`.

    Mesure reelle : paysage 8f et portrait 8f coutent le meme nombre de
    planches, et le portrait rend presque le double de surface.
    """
    etroite = mise("paysage", 8, surface_mm2=24.1, pages_par_lot=(16, 5))
    large = mise("portrait", 8, surface_mm2=46.1, pages_par_lot=(16, 5))
    assert page_templates.domine(large, etroite)
    assert not page_templates.domine(etroite, large)


def test_deux_mises_en_page_identiques_ne_se_dominent_pas():
    """L'inegalite stricte : sans elle, tout se domine et rien n'est marque."""
    une = mise("portrait", 2, surface_mm2=50.0, pages_par_lot=(7,))
    autre = mise("paysage", 2, surface_mm2=50.0, pages_par_lot=(7,))
    assert not page_templates.domine(une, autre)
    assert not page_templates.domine(autre, une)


def test_une_mise_en_page_ne_se_domine_jamais_elle_meme():
    """La consequence directe de l'inegalite stricte, mesuree comme telle.

    C'est elle qui dispense d'exclure `candidate is autre` a l'appel. Un
    comparateur qui perdrait la stricte rendrait **toutes** les entrees
    dominees, et l'ecran n'aurait plus un seul glyphe a poser.
    """
    for mesuree in page_templates.mesurer_les_mises_en_page(LOTS_DE_REFERENCE):
        assert not page_templates.domine(mesuree, mesuree)


def test_un_meilleur_dessin_paye_en_papier_ne_domine_pas():
    """Le `and` : faire mieux sur **un seul** critere ne domine pas.

    C'est le mutant `and` -> `or`, qui rendrait toute l'echelle dominee par
    tout le reste.
    """
    grande_et_chere = mise("paysage", 1, surface_mm2=311.5, pages_par_lot=(124, 40))
    petite_et_sobre = mise("portrait", 8, surface_mm2=46.1, pages_par_lot=(16, 5))
    assert not page_templates.domine(grande_et_chere, petite_et_sobre)
    assert not page_templates.domine(petite_et_sobre, grande_et_chere)


# --- Le bilan comme objet de lecture ---------------------------------------


def test_une_mise_en_page_hors_produit_est_un_refus_nomme():
    """Le 6 est retire du portrait : le demander n'est pas une entree vide."""
    bilan = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    assert 6 not in page_templates.frames_per_page_vocabulary(
        "portrait", page_templates.DEFAULT_GEOMETRY_VERSION
    )
    with pytest.raises(page_templates.UnknownTemplateError):
        bilan.de("portrait", 6)
    with pytest.raises(page_templates.UnknownTemplateError):
        bilan.dominants_de("portrait", 6)


def test_l_etat_d_ouverture_du_coeur_n_est_pas_recopie_par_le_bilan():
    """Les defauts du bilan **sont** ceux du coeur, jamais des litteraux."""
    par_defaut = page_templates.bilan_de_domination(LOTS_DE_REFERENCE)
    explicite = page_templates.bilan_de_domination(
        LOTS_DE_REFERENCE,
        margin_preset=page_templates.DEFAULT_MARGIN_PRESET,
        geometry_version=page_templates.DEFAULT_GEOMETRY_VERSION,
    )
    assert par_defaut.mises_en_page == explicite.mises_en_page
    assert par_defaut.dominants == explicite.dominants


def test_une_marge_plus_grande_reduit_chaque_surface_sans_toucher_aux_pages():
    """La marge traverse jusqu'a la surface, et **seulement** jusqu'a elle."""
    sans_marge = page_templates.bilan_de_domination(LOTS_DE_REFERENCE, margin_preset="0")
    avec_marge = page_templates.bilan_de_domination(LOTS_DE_REFERENCE, margin_preset="5")
    for petite, grande in zip(avec_marge.mises_en_page, sans_marge.mises_en_page):
        assert petite.cle == grande.cle
        assert petite.surface_mm2 < grande.surface_mm2
        assert petite.pages_par_lot == grande.pages_par_lot
