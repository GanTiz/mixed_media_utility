# -*- coding: utf-8 -*-
"""Story 11.9, lot T2 -- le manuel REMPLIT la fenetre, et on le mesure a
PLUSIEURS TAILLES.

**L'arbitrage.** Egan, le 2026-09-04, en trois mots : « Remplir la fenetre ».
Le manuel s'elargissait avec le terminal mais restait pagine pour 17 lignes ;
il suit desormais la hauteur aussi. C'est une decision produit, et c'est
l'issue que la revue n'avait pas recommandee -- elle prime.

**Le defaut ferme, et ce qui l'avait rendu invisible.** `deferred-work.md`,
section « La HAUTEUR de page reste au plancher quand la LARGEUR suit la
fenetre » : `_regime()` lisait `application.size.width` -- la largeur **reelle**
-- et laissait la hauteur a `jetons.HAUTEUR_CENTRE_AU_PLANCHER`. Deux moities
du meme regime lues a deux endroits differents. A 120 x 50, le manuel entier
fait 28 lignes et tenait donc en **une** page ; le produit en annoncait deux,
laissait 28 lignes de zone centrale vides et imposait un `→` sans objet.

**Ce qui empechait de le voir, et c'est le geste central de ce banc** :
`tests/unit/tui/conftest.py` expose `piloter(app, scenario, taille=...)` depuis
la story 11.0, et **aucun** des sept bancs du manuel ne s'en servait. Tout etait
mesure a `TAILLE_PLANCHER = (80, 24)` -- la seule taille ou les deux lectures
coincident, donc la seule ou le defaut est invisible. Ce banc mesure a **trois**
tailles au moins, et deux d'entre elles ne sont pas le plancher.

**Les trois gardes heritees du lot E5**, parce que ce module a deja produit
trois faux « tues » :

1. **les attendus sont ecrits EN DUR**, jamais relus du module -- une sonde
   tiree de ce qu'on mesure ne mesure rien. Les hauteurs centrales attendues
   (17, 33, 43) sont posees ici a la main ;
2. **aucune frontiere ne se repose sur une valeur qui vaut aussi autre chose** :
   les tailles eprouvees donnent 17, 33 et 43, et une mort par collision avec
   `HAUTEUR_CENTRE_AU_PLANCHER` (qui vaut 17) ne tuerait qu'un cas sur trois ;
3. **toute frontiere negative porte son volet de morsure**. Celle qui interdit
   de recopier la soustraction de geometrie serait verte sur un paquet vide,
   sur un module renomme, et surtout si les quatre fonctions appelantes avaient
   simplement disparu -- le volet mesure qu'elles rendent la bonne valeur.

**Regle des fabriques** (`CLAUDE.md`, points 1 a 4) : le corpus de synthese de
la tache 5 porte **onze** entrees distinguables -- des libelles differents,
jamais un remplissage uniforme --, et ses cibles sont **en tete, au milieu et
en queue**, aux deux hauteurs jouees. La position se verifie sur la liste que
le **CODE** parcourt (les pages rendues), pas sur celle que le test a ecrite.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import (
    atelier_pdf_execution,
    atelier_pdf_resultat,
    ecran_manuel as em,
    jetons,
    manuel,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

RACINE = Path(__file__).resolve().parents[3]
PAQUET = RACINE / "src" / "mixed_media_utility" / "tui"
MODULE_DES_JETONS = PAQUET / "jetons.py"
MODULE_DE_L_EXECUTION = PAQUET / "execution.py"


def coque_temoin() -> CoqueTui:
    """La coque minimale d'ou `F1` ouvre le manuel."""
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir  F1 aide"),
                             PalierTemoin("Ateliers", "⏎ entrer  F1 aide")],
                    contexte=Contexte("projet_demo"))


# ===========================================================================
# Tache 1 -- le regime se lit AUX DEUX MOITIES, a plusieurs tailles
# ===========================================================================

#: Les trois tailles du banc, et ce que la grille leur laisse au centre.
#: **Ecrit en dur** : relire `jetons.hauteur_centrale` ferait de l'assertion une
#: sonde de ce qu'elle mesure. 24 - 2 lignes de cadre - 2 filets - bandeau -
#: etat - raccourcis = 17 ; 40 en laisse 33 ; 50 en laisse 43.
TAILLES_ET_HAUTEUR_CENTRALE = [
    pytest.param((80, 24), 17, id="plancher-80x24"),
    pytest.param((100, 40), 33, id="100x40"),
    pytest.param((120, 50), 43, id="120x50"),
]


@pytest.mark.parametrize("taille,hauteur_centrale", TAILLES_ET_HAUTEUR_CENTRALE)
def test_T2_le_regime_du_manuel_porte_la_HAUTEUR_de_la_fenetre(
        banc, taille, hauteur_centrale):
    """Le defaut exact : la largeur suivait la fenetre, la hauteur non.

    Jusqu'au 2026-09-04, `_regime()` rendait `(largeur_reelle, repli)` et la
    hauteur restait a `HAUTEUR_CENTRE_AU_PLANCHER` **quelle que soit la
    fenetre**. Le regime porte desormais les deux moities, et elles se lisent
    au meme endroit.

    Mesure sur une application **reellement montee** : c'est la seule facon de
    voir `application.size`, et c'est precisement ce que les sept bancs du
    manuel ne faisaient qu'au plancher.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        return pilote.app.screen._regime()

    regime = banc(coque_temoin(), scenario, taille=taille)
    assert regime == (taille[0], hauteur_centrale, False), (
        f"a {taille[0]} x {taille[1]}, le regime du manuel devrait etre "
        f"({taille[0]}, {hauteur_centrale}, False) ; il rend {regime}. Une "
        "hauteur restee a 17 est le defaut d'origine : la largeur suit la "
        "fenetre, la hauteur reste au plancher.")


@pytest.mark.parametrize("taille,hauteur_centrale", TAILLES_ET_HAUTEUR_CENTRALE)
def test_T2_la_page_peinte_TIENT_dans_la_zone_centrale_de_CETTE_fenetre(
        banc, taille, hauteur_centrale):
    """Le volet de securite : remplir la fenetre, jamais la deborder.

    `textual` coupe par le bas **en silence** (defaut `I1`, paye sur `E2-2`) :
    une page plus haute que sa zone centrale perdrait ses derniers raccourcis
    sans rien dire. La borne se deplace maintenant avec la fenetre, donc elle
    doit etre mesuree **a chaque taille** et non plus au seul plancher.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        return [len(page.lignes) for page in ecran.pages()]

    hauteurs = banc(coque_temoin(), scenario, taille=taille)
    assert hauteurs, "aucune page rendue : la sonde ne mesure rien"
    trop_hautes = [h for h in hauteurs if h > hauteur_centrale]
    assert trop_hautes == [], (
        f"a {taille[0]} x {taille[1]} la zone centrale vaut "
        f"{hauteur_centrale} lignes, et des pages en portent {trop_hautes}")


# ===========================================================================
# Tache 2 -- ce que l'arbitrage promet : le manuel REMPLIT la fenetre
# ===========================================================================

def test_T2_a_120x50_le_manuel_ENTIER_tient_en_UNE_page(banc):
    """« Remplir la fenetre » (Egan, 2026-09-04) -- le chiffre de la dette.

    A 120 x 50, le manuel entier fait 28 lignes pour 43 disponibles : il tient
    en **une** page, le bandeau doit dire `page 1 sur 1`, et il ne doit rester
    **aucun** `→` a presser. Avant le correctif, le produit annoncait deux
    pages, laissait 28 lignes de zone centrale vides et imposait une touche
    sans objet.

    **Ce test est volontairement fragile, comme `test_C3`** : le manuel est
    derive du paquet entier, donc il rougirait si le paquet doublait de
    raccourcis. Le remede serait alors de relire ce chiffre, pas d'assouplir
    l'assertion -- la marge est de 43 contre 28.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        avant = ecran.objet_du_bandeau()
        await pilote.press("right")
        await pilote.pause()
        return (len(ecran.pages()), avant, ecran.rang_de_page,
                ecran.objet_du_bandeau())

    pages, bandeau, rang_apres_fleche, bandeau_apres = banc(
        coque_temoin(), scenario, taille=(120, 50))
    assert pages == 1, (
        f"a 120 x 50 le manuel entier tient dans la zone centrale (43 lignes "
        f"pour 28 de matiere) ; il est pourtant coupe en {pages} pages")
    assert bandeau == "page 1 sur 1", bandeau
    assert rang_apres_fleche == 0, (
        "`→` a change de page alors qu'il n'y en a qu'une")
    assert bandeau_apres == "page 1 sur 1", bandeau_apres


def test_T2_au_PLANCHER_le_manuel_reste_PAGINE(banc):
    """Le volet de morsure du test precedent, et il n'est pas decoratif.

    « Une seule page » serait aussi vrai d'un paginateur casse qui ne couperait
    jamais -- et un tel defaut perdrait les trois quarts du manuel, `textual`
    coupant par le bas en silence. Au plancher, les 34 lignes du manuel ne
    tiennent pas dans 17 : la coupure doit avoir lieu.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        return len(ecran.pages()), ecran.objet_du_bandeau()

    pages, bandeau = banc(coque_temoin(), scenario, taille=(80, 24))
    assert pages > 1, (
        "au plancher le manuel ne tient pas en une page : un paginateur qui "
        f"n'en rend qu'une a cesse de couper ({pages} page)")
    assert bandeau == f"page 1 sur {pages}", bandeau


def test_T2_la_page_peinte_GRANDIT_avec_la_fenetre(banc):
    """La propriete que l'arbitrage demande, dite sans chiffre de contenu.

    Elle ne depend d'aucun cardinal de raccourcis : agrandir la fenetre doit
    faire grandir ce que la page peint. Avant le correctif, la page peinte
    valait 15 lignes a 80 x 24 **et** 15 lignes a 120 x 50 -- la largeur seule
    bougeait.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        return len(pilote.app.screen.composer())

    au_plancher = banc(coque_temoin(), scenario, taille=(80, 24))
    en_grand = banc(coque_temoin(), scenario, taille=(120, 50))
    assert en_grand > au_plancher, (
        f"la page peinte vaut {au_plancher} lignes au plancher et "
        f"{en_grand} a 120 x 50 : la hauteur ne suit pas la fenetre")


# ===========================================================================
# Tache 3 -- la HAUTEUR est dans la CLE de la memoire de pagination
# ===========================================================================

def test_T2_un_agrandissement_en_HAUTEUR_SEULE_repagine(banc):
    """Sans la hauteur dans la cle, on peindrait la pagination de l'ancienne
    fenetre.

    Le redimensionnement est fait **en hauteur seule** (80 x 24 -> 80 x 50),
    et c'est ce qui isole la moitie mesuree : la largeur ne bouge pas, donc une
    cle `(largeur, repli)` serait **identique** avant et apres et rendrait les
    pages du plancher. A 80 x 50 la zone centrale vaut 43 lignes, le manuel en
    fait 34 : une seule page.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        avant = len(ecran.pages())
        await pilote.resize_terminal(80, 50)
        await pilote.pause()
        return avant, len(ecran.pages()), ecran.objet_du_bandeau()

    avant, apres, bandeau = banc(coque_temoin(), scenario, taille=(80, 24))
    assert avant > 1, (
        f"la sonde n'a pas commence pagine : {avant} page au plancher")
    assert apres == 1, (
        f"apres agrandissement en hauteur seule, le manuel rend encore {apres} "
        "pages : la pagination du plancher a ete resservie, donc la hauteur "
        "n'est pas dans la cle de `_pages_par_regime`")
    assert bandeau == "page 1 sur 1", bandeau


def test_T2_le_RANG_de_page_est_RECLAMPE_quand_la_pagination_retrecit(banc):
    """Mutant `M38` -- le retrait de la reclampe de `rang_de_page`.

    Il survivait pour une raison simple : **aucun banc ne changeait de taille**,
    donc le cardinal de pages ne bougeait jamais sous un rang deja pose. Ici la
    sonde va d'abord sur la **derniere** page au plancher, puis agrandit : la
    pagination retrecit a une page et le rang designerait une page qui n'existe
    plus.

    Sans la reclampe, `composer()` leve `IndexError` -- ce que la sonde appelle
    explicitement, parce qu'une exception levee dans `rafraichir()` pourrait
    etre absorbee par la boucle d'evenements de `textual`.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        pages_au_plancher = len(ecran.pages())
        for _ in range(pages_au_plancher + 2):
            await pilote.press("right")
            await pilote.pause()
        rang_au_plancher = ecran.rang_de_page
        await pilote.resize_terminal(80, 50)
        await pilote.pause()
        return (pages_au_plancher, rang_au_plancher, len(ecran.pages()),
                ecran.rang_de_page, len(ecran.composer()))

    pages, rang_avant, apres, rang_apres, peinte = banc(
        coque_temoin(), scenario, taille=(80, 24))
    assert pages > 1, f"la sonde n'a pas commence pagine ({pages} page)"
    assert rang_avant == pages - 1, (
        f"la sonde devait etre sur la DERNIERE page ({pages - 1}), elle est "
        f"sur la {rang_avant}")
    assert apres == 1, apres
    assert rang_apres == 0, (
        f"apres retrecissement de la pagination a {apres} page, le rang vaut "
        f"encore {rang_apres} : il designe une page qui n'existe plus")
    assert peinte > 0, "la page courante est vide"


# ===========================================================================
# Tache 4 -- la soustraction de geometrie n'est ecrite QU'UNE FOIS
# ===========================================================================

def _attributs_de_jetons(source: Path) -> set[str]:
    """Les `jetons.<NOM>` qu'un module lit, releves a l'AST.

    A l'AST et non au grep : une mention en commentaire ou en docstring n'est
    pas une recopie de geometrie, et une frontiere qui rougirait dessus
    serait retiree a la premiere prose.
    """
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    return {noeud.attr for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Attribute)
            and isinstance(noeud.value, ast.Name)
            and noeud.value.id == "jetons"}


#: Les deux jetons qui n'existent QUE pour la soustraction verticale. Un module
#: qui les nomme est en train de refaire le calcul de `hauteur_centrale` --
#: c'est ce que quatre modules faisaient jusqu'au 2026-09-04.
JETONS_DE_LA_SOUSTRACTION = {"BORDURE", "FILETS"}


def test_T2_aucun_module_du_paquet_ne_REFAIT_la_soustraction_de_hauteur(
        sources_tui):
    """Frontiere NEGATIVE -- la seule qui attrape une REINTRODUCTION.

    La soustraction `hauteur - 2*BORDURE - FILETS - bandeau - etat -
    raccourcis` etait ecrite **quatre fois** dans le paquet
    (`atelier_pdf_resultat`, `atelier_pdf_execution`, `execution` deux fois),
    chacune avec son `max(..., 0)` et son commentaire. Elle vit desormais dans
    `jetons.hauteur_centrale`, comme `largeur_utile` y vit deja.

    Aucun test positif ne verrait revenir une cinquieme copie : c'est le motif
    exact que `CLAUDE.md` donne aux frontieres negatives.
    """
    recopies = {source.name: sorted(
                    _attributs_de_jetons(source) & JETONS_DE_LA_SOUSTRACTION)
                for source in sources_tui
                if source.name != MODULE_DES_JETONS.name
                and _attributs_de_jetons(source) & JETONS_DE_LA_SOUSTRACTION}
    assert recopies == {}, (
        "ces modules lisent les jetons de la soustraction verticale : ils "
        "refont le calcul de `jetons.hauteur_centrale` au lieu de l'appeler "
        f"-- {recopies}")


#: Ce que la grille laisse au centre, **ecrit en dur**, y compris sous le
#: plancher ou la soustraction devient negative et le plancher a zero joue.
HAUTEURS_CENTRALES_ATTENDUES = {24: 17, 40: 33, 50: 43, 20: 13, 10: 3,
                                7: 0, 6: 0, 0: 0}


@pytest.mark.parametrize("fenetre,centre",
                         sorted(HAUTEURS_CENTRALES_ATTENDUES.items()))
def test_T2_les_QUATRE_appelants_rendent_la_MEME_hauteur_que_jetons(
        fenetre, centre):
    """Le volet de morsure de la frontiere negative ci-dessus.

    Sans lui, la frontiere serait verte si les fonctions appelantes avaient
    simplement disparu, ou si elles rendaient n'importe quoi : « aucun module
    ne recopie » est vrai d'un paquet qui ne calcule plus rien. Les valeurs
    attendues sont **ecrites en dur**, jamais relues du module mesure.

    Les deux sites d'`execution.py` sont des methodes qui lisent
    `self.app.size.height` : ils sont couverts par la frontiere AST, et le
    volet positif ci-dessous mesure qu'ils appellent bien la fonction commune.
    """
    assert jetons.hauteur_centrale(fenetre) == centre, fenetre
    assert atelier_pdf_resultat.hauteur_centrale(fenetre) == centre, fenetre
    assert atelier_pdf_execution.hauteur_centrale(fenetre) == centre, fenetre


def test_T2_execution_APPELLE_bien_la_hauteur_commune_a_ses_DEUX_sites():
    """Volet positif des deux sites qui n'ont pas de fonction nommee.

    `EcranResultat.lignes_de_journal_visibles` et
    `EcranExecution.lignes_de_journal_visibles` recopiaient la soustraction
    chacune de son cote. Plusieurs appels, pas un : un seul site converti
    laisserait l'autre diverger, et c'est le regime que la frontiere negative
    seule ne distingue pas d'une suppression.

    **Le cardinal passe de deux a TROIS avec la 11.4e** (AC 8.7) :
    `EcranExecution.lignes_de_lots_visibles` est un troisieme site, et il
    appelle la meme fonction commune plutot que de refaire la soustraction.
    Le cardinal est ecrit en dur ici **exprès** -- c'est ce qui fait rougir le
    jour ou un quatrieme site la recopie au lieu de l'appeler.

    **Puis a QUATRE avec `EPIC11-ARB-245`** (lot `arb245`, 2026-09-05) :
    `EcranEcrasement.hauteur_du_cartouche` est le quatrieme, et il APPELLE --
    c'est exactement le regime que ce test veut, pas celui qu'il refuse. La
    frontiere a fait son travail dans les deux sens le meme jour : son volet
    NEGATIF a attrape un `2 * jetons.BORDURE` que ce lot avait ecrit dans
    `execution.py`, et qui est devenu `LIGNES_DU_CADRE_DU_CARTOUCHE` -- le
    cadre du CARTOUCHE n'est pas celui de l'ECRAN, meme s'ils valent un.

    **Puis a CINQ le 2026-09-07**, avec le constat `C2-1` des retours terrain :
    `EcranResultat.lignes_de_cartouche_visibles` est le cinquieme, et il
    APPELLE lui aussi. Le motif de son existence est le meme que celui des
    quatre autres, une soustraction qui vivait ailleurs -- ici le cartouche de
    l'ecran de resultat mangeait tout le centre quand il portait plus de lignes
    que la fenetre, et le journal deplie tombait a zero ligne visible sans que
    rien ne le dise. Il abrege desormais le cartouche pour garder au journal un
    plancher de `LIGNES_MINIMALES_DU_JOURNAL`, et il lui faut donc la meme
    hauteur commune que les quatre autres.
    """
    arbre = ast.parse(MODULE_DE_L_EXECUTION.read_text(encoding="utf-8"))
    appels = [noeud for noeud in ast.walk(arbre)
              if isinstance(noeud, ast.Call)
              and isinstance(noeud.func, ast.Attribute)
              and noeud.func.attr == "hauteur_centrale"
              and isinstance(noeud.func.value, ast.Name)
              and noeud.func.value.id == "jetons"]
    assert len(appels) == 5, (
        "`execution.py` porte CINQ sites qui lisent la hauteur centrale -- "
        "les deux journaux, la liste des lots de la 11.4e, le cartouche "
        "defilant d'`EPIC11-ARB-245` et le cartouche abrege du resultat "
        "(`C2-1`) -- ; ils doivent tous appeler "
        f"`jetons.hauteur_centrale` -- {len(appels)}")


# ===========================================================================
# Tache 5 -- ce que la HAUTEUR fait a la pagination, sur un corpus de synthese
# ===========================================================================

def _entree_d_une_ligne(rang: int) -> manuel.Entree:
    """Une entree d'**une** ligne, distinguable de ses voisines par son libelle.

    Regle des fabriques, point 1 : des valeurs **differentes**, jamais un
    remplissage uniforme -- une permutation ne se voit que si les elements
    different.
    """
    return manuel.Entree(
        ouvreur=f"T{rang:02d}",
        libelles=(f"geste numero {rang}",),
        ecrans=(f"mixed_media_utility.tui.atelier_extraction.Ecran{rang}",),
        ateliers=("atelier_extraction",),
        partout=True)


#: Onze entrees d'une ligne : assez pour que la pagination rende plusieurs
#: pages a 10 lignes de hauteur et une seule a 43.
CORPUS = tuple(_entree_d_une_ligne(rang) for rang in range(11))

#: Les trois cibles, **en tete, au milieu et en queue** du corpus que le CODE
#: parcourt (regle des fabriques, points 2 et 4). La cible du milieu demasque
#: un `find` fautif ; celles des bords demasquent un balayage tronque, qui est
#: un autre mode de panne.
CIBLE_DE_TETE = "T00"
CIBLE_DU_MILIEU = "T05"
CIBLE_DE_QUEUE = "T10"


def test_T2_les_trois_cibles_sont_bien_en_TETE_au_MILIEU_et_en_QUEUE():
    """La regle des fabriques se verifie sur la liste que le CODE parcourt."""
    ouvreurs = [entree.ouvreur for entree in CORPUS]
    assert len(ouvreurs) == 11, ouvreurs
    assert ouvreurs[0] == CIBLE_DE_TETE, ouvreurs
    assert ouvreurs[len(ouvreurs) // 2] == CIBLE_DU_MILIEU, ouvreurs
    assert ouvreurs[-1] == CIBLE_DE_QUEUE, ouvreurs
    assert len(set(ouvreurs)) == len(ouvreurs), (
        "deux entrees identiques rendraient toute erreur d'appariement "
        f"invisible -- {ouvreurs}")


#: Ce que la pagination doit rendre du corpus a chaque hauteur, **ecrit en
#: dur**. Le corpus fait 11 lignes plus 3 de titre de bloc = 14 lignes.
#: A 10 : deux pages (7 unites tenant avec le titre, puis le reste avec son
#: rappel de titre). A 43 : une seule.
PAGES_ATTENDUES_PAR_HAUTEUR = {10: 2, 17: 1, 43: 1}


@pytest.mark.parametrize("hauteur,attendu",
                         sorted(PAGES_ATTENDUES_PAR_HAUTEUR.items()))
def test_T2_la_HAUTEUR_decide_du_cardinal_de_pages(hauteur, attendu):
    """La hauteur pilote la pagination -- trois hauteurs, pas une.

    Une seule hauteur laisserait passer une mort par collision avec
    `HAUTEUR_CENTRE_AU_PLANCHER` (qui vaut 17, et qui est exactement par la
    qu'un mutant de colonne avait faussement « tue » au lot E5).
    """
    pages = em.pages_du_manuel(CORPUS, hauteur=hauteur)
    assert len(pages) == attendu, (
        f"a hauteur {hauteur}, le corpus de 14 lignes devait rendre {attendu} "
        f"page(s) ; il en rend {len(pages)} "
        f"(cardinaux : {[len(page.lignes) for page in pages]})")
    debordantes = [len(page.lignes) for page in pages
                   if len(page.lignes) > hauteur]
    assert debordantes == [], debordantes


@pytest.mark.parametrize("hauteur", sorted(PAGES_ATTENDUES_PAR_HAUTEUR))
def test_T2_les_trois_cibles_survivent_a_TOUTE_hauteur(hauteur):
    """Aucune entree ne se perd quand la hauteur change.

    Le volet qui manquerait sans les cibles de bord : un balayage tronque
    d'une ligne perdrait `T10` sans qu'un cardinal de pages bouge.
    """
    pages = em.pages_du_manuel(CORPUS, hauteur=hauteur)
    portes = [ouvreur for page in pages for ouvreur in page.ouvreurs]
    assert portes[0] == CIBLE_DE_TETE, portes
    assert CIBLE_DU_MILIEU in portes, portes
    assert portes[-1] == CIBLE_DE_QUEUE, portes
    assert len(portes) == 11, portes


# ===========================================================================
# Tache 6 -- le repli hors montage, et ce qui se passe SOUS le plancher
# ===========================================================================

def test_T2_hors_montage_le_regime_reste_AU_PLANCHER():
    """La reserve posee par la couche 1 : « le repli hors montage doit rester ».

    `textual` fait de `Screen.app` une propriete qui **leve** hors montage, y
    compris a travers `getattr(..., None)`. Les bancs construisent les ecrans a
    nu ; sans ce repli, `traiter()` ne serait pas mesurable sans terminal, ce
    qu'`EPIC11-ARB-11` exige. Hors montage il n'y a pas de fenetre a suivre :
    le plancher est la seule taille que le depot connaisse.

    Attendus **en dur** : 80 colonnes, 17 lignes de zone centrale, pas de repli.
    """
    ecran = em.EcranManuel()
    assert ecran._regime() == (80, 17, False), ecran._regime()
    assert len(ecran.pages()) > 1, (
        "hors montage le manuel doit rester pagine au plancher")
    assert ecran.composer(), "hors montage, le manuel ne peint rien"


#: Sous 24 lignes la fenetre est hors plancher : la coque n'y dessine que le
#: message d'`EPIC11-ARB-21`. Ce que le manuel calcule alors n'est peint par
#: personne -- mais il ne doit ni lever ni rendre zero page. La derniere taille
#: pousse la soustraction en NEGATIF (6 - 6 = 0), ou le plancher a zero joue.
TAILLES_SOUS_LE_PLANCHER = [
    pytest.param((80, 20), 13, id="80x20"),
    pytest.param((80, 10), 3, id="80x10"),
    pytest.param((80, 6), 0, id="80x6-soustraction-nulle"),
    pytest.param((60, 24), 17, id="60x24-trop-etroit"),
]


@pytest.mark.parametrize("taille,hauteur_centrale", TAILLES_SOUS_LE_PLANCHER)
def test_T2_SOUS_le_plancher_rien_n_est_peint_et_rien_ne_LEVE(
        banc, taille, hauteur_centrale):
    """Mesure plutot que suppose -- la reserve de la couche 1, second volet.

    Ce que devient la mise en page **sous** 24 lignes n'avait jamais ete
    mesure. Le verdict : la coque ne dessine que `#trop-petit` (elle sort de
    `compose` avant le bandeau, la zone centrale et la ligne d'etat), donc le
    manuel n'y peint rien du tout. Sa pagination degradee reste neanmoins
    **appelable** -- `objet_du_bandeau()` et `pages()` ne sont derriere aucune
    garde --, et elle ne doit ni lever ni rendre un cardinal nul : c'est ce que
    le plancher a zero de `jetons.hauteur_centrale` garantit.

    Et parce que la hauteur est dans la cle, la pagination degradee ne sera
    **pas** resservie au retour au-dessus du plancher.
    """
    async def scenario(pilote):
        ecran = pilote.app.screen
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        return (type(ecran).__name__, len(ecran.query("#trop-petit")),
                len(ecran.query("#centre")), ecran._regime(),
                len(ecran.pages()), ecran.objet_du_bandeau())

    (nom, trop_petit, centre, regime, pages,
     bandeau) = banc(coque_temoin(), scenario, taille=taille)
    assert nom == "EcranManuel", nom
    assert trop_petit == 1, (
        f"a {taille}, la coque devrait ne dessiner que le message de "
        f"`EPIC11-ARB-21` ; `#trop-petit` compte {trop_petit}")
    assert centre == 0, (
        f"a {taille}, la zone centrale ne doit pas exister : une mise en page "
        "tronquee ment sur ce qui tient")
    assert regime == (taille[0], hauteur_centrale, False), regime
    assert pages >= 1, (
        f"a {taille}, la pagination degradee rend {pages} page : un cardinal "
        "nul ferait lever `composer()` et `objet_du_bandeau()`")
    assert bandeau == f"page 1 sur {pages}", bandeau
