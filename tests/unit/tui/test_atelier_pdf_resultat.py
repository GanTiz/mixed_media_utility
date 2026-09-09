# -*- coding: utf-8 -*-
"""`E5-5` / `E5-5b` / `E5-5c` -- le compte rendu des planches (11.7, lot I, AC 10).

Ce banc mesure la **bascule de zone au `Tab`** et ce qui la rend honnete :

* **`Tab` DEPLACE le curseur, il ne le duplique pas** (`EPIC11-ARB-50`). Le
  mesure porte sur l'invariant reel -- **un seul** curseur dessine a la fois --
  et sur son volet symetrique : les issues restent dessinees et **entieres**
  quand la liste prend la main ;
* **la ligne du bas ne montre que ce qui marche** : dans la liste, `⏎` n'a rien
  a valider et **part** de la ligne. Les deux moities sont mesurees -- la
  touche absente de la ligne, et la touche inerte au clavier ;
* **la fenetre est indexee sur les LIGNES COMPOSEES, jamais sur le rang
  absolu**. C'est le trou que le lot D a paye : une liste indexee sur le rang
  absolu est indiscernable du bon tant que la fenetre commence a zero. La
  fabrique porte donc **sept** planches et un banc **fait defiler** la fenetre
  jusqu'a ce qu'elle ne commence plus a zero.

Regle des fabriques, sur la liste que le CODE parcourt
-------------------------------------------------------

`TableDesEcrits.lignes` boucle sur `planches[premier:dernier+1]`. La fabrique
porte **sept** planches, distinguables par leur nom, leur cardinal de pages et
leur rang de tirage -- dont une assez longue pour declencher l'abregement --,
et la cible des mesures de fenetre est au **milieu** de la fenetre, ni en
premiere ni en derniere position.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from mixed_media_utility import page_templates
from mixed_media_utility.io import naming
from mixed_media_utility.tui import atelier_pdf_resultat as resultat
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.atelier_scan_parcours import RACCOURCIS_RAPPORT

RACINE = pathlib.Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
SOURCE_DU_MODULE = pathlib.Path(resultat.__file__)

#: La hauteur de la zone centrale au plancher (80x24). Elle est **derivee**,
#: jamais saisie.
HAUTEUR_CENTRALE = resultat.hauteur_centrale(24)

#: Le fragment de mise en page des noms de la demonstration, **DERIVE du
#: produit** et jamais ecrit : c'est lui que l'abregement protege.
FRAGMENT = naming.sheets_layout_fragment(
    page_templates.build_template_id("paysage", 6, "0"))

#: Les **sept** planches de `E5-5b`, verbatim des noms de la maquette pour les
#: quatre qu'elle montre. Cardinaux et rangs **tous distincts** : une
#: permutation ne se voit que si les elements different.
SEPT_PLANCHES = (
    resultat.PlancheEcrite("projet_demo_plan-01_25_6f-pay_v2.pdf", 21, 2, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-02_12p5_6f-pay.pdf", 16, 1, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-03_8_6f-pay_v5.pdf", 9, 5, FRAGMENT),
    resultat.PlancheEcrite(
        "projet_demo_sequence-12-atelier-fondement_12p5_6f-pay.pdf", 13, 1, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-05_25_6f-pay_v3.pdf", 11, 3, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-06_8_6f-pay.pdf", 7, 1, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-07_12p5_6f-pay_v4.pdf", 4, 4, FRAGMENT),
)

#: Les **deux** planches de `E5-5`, dont la liste tient entiere.
DEUX_PLANCHES = (
    resultat.PlancheEcrite("projet_demo_plan-04_25_6f-pay_v4.pdf", 21, 4, FRAGMENT),
    resultat.PlancheEcrite("projet_demo_plan-04_8_6f-pay.pdf", 7, 1, FRAGMENT),
)

INFORMATIONS = (("Gabarit", "tpl-a4-paysage-6f-v2"),
                ("Emplacement", "projet_demo/planches/"))


def table_longue(**kwargs) -> resultat.TableDesEcrits:
    return resultat.TableDesEcrits(SEPT_PLANCHES, frames=512, **kwargs)


def table_courte() -> resultat.TableDesEcrits:
    return resultat.TableDesEcrits(DEUX_PLANCHES, frames=164)


class _Taille:
    def __init__(self, largeur=80, hauteur=24):
        self.width, self.height = largeur, hauteur


class _AppFactice:
    """Le strict necessaire pour peindre : une taille et deux modes."""

    def __init__(self, largeur=80, hauteur=24, ascii_seul=False):
        self.size = _Taille(largeur, hauteur)
        self.ascii_seul = ascii_seul
        self.sans_couleur = True
        self.ateliers = 0
        self.descendus = []

    def revenir_aux_ateliers(self):
        self.ateliers += 1

    def descendre(self, ecran):
        self.descendus.append(ecran)


class _Evenement:
    def __init__(self, touche):
        self.key = touche
        self.arrete = False

    def stop(self):
        self.arrete = True


class _EcranSousBanc(resultat.EcranResultatDesPlanches):
    """La sous-classe qui porte l'application factice, et le motif compte.

    `textual` fait de `Screen.app` une **propriete**, c'est-a-dire un
    descripteur de donnees : une affectation sur l'instance ne la masque pas.
    La seule facon de la remplacer sans monter l'application est donc de la
    redefinir sur une classe -- et ce banc redefinissait la classe de
    PRODUCTION, `EcranResultatDesPlanches` elle-meme, sans jamais la
    restaurer. Tout banc collecte apres celui-ci heritait de la mutation :
    trois mesures d'AC tombaient des que l'ordre de collecte changeait, et le
    dossier entier ne restait vert que par coincidence alphabetique.

    Une sous-classe porte la meme propriete sans toucher a ce que le produit
    livre.
    """

    @property
    def app(self):
        return self._app_factice


def ecran(table=None, suites=None, sur_suite=None) -> resultat.EcranResultatDesPlanches:
    """Un ecran construit **a nu**, sans monter `textual`.

    Sa geometrie est fournie par l'application factice ; tout ce que ce banc
    mesure passe par `composer`, `poser_les_raccourcis` et `on_key`, qui ne
    dessinent rien.
    """
    objet = _EcranSousBanc(
        table if table is not None else table_longue(),
        informations=INFORMATIONS, suites=suites,
        sur_suite=sur_suite or (lambda _suite: None))
    objet._app_factice = _AppFactice()
    # **Le dessin est neutralise, pas simule** : ce banc mesure la
    # composition, les raccourcis et le clavier -- trois choses qui ne
    # dessinent rien. `rafraichir` sort alors des sa premiere ligne, comme sur
    # un terminal trop petit.
    objet._assez_grand_au_dernier_dessin = False
    return objet


# ---------------------------------------------------------------------------
# AC 10.5 -- la ligne de `E5-5` est EXACTEMENT celle du produit
# ---------------------------------------------------------------------------


def test_E5_5_rend_EXACTEMENT_RACCOURCIS_RAPPORT():
    """`Tab journal` part, et c'est une correction : la ligne du produit pour un
    ecran de compte rendu n'en a jamais porte."""
    objet = ecran(table_courte())
    assert objet.poser_les_raccourcis(HAUTEUR_CENTRALE) == RACCOURCIS_RAPPORT


def test_la_ligne_de_E5_5_est_LUE_du_produit_et_jamais_recopiee():
    """Une seconde redaction divergerait au premier ajustement de libelle."""
    assert resultat.RACCOURCIS_LISTE_ENTIERE is RACCOURCIS_RAPPORT
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide" not in source


def test_aucune_des_trois_lignes_ne_porte_Tab_journal():
    for ligne in (resultat.RACCOURCIS_LISTE_ENTIERE,
                  resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES,
                  resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE):
        assert "journal" not in ligne


# ---------------------------------------------------------------------------
# AC 10.4 -- la bascule de zone
# ---------------------------------------------------------------------------


def test_E5_5b_est_l_etat_d_ARRIVEE_le_curseur_sur_les_ISSUES():
    objet = ecran()
    assert objet.zone == resultat.ZONE_DES_ISSUES
    assert (objet.poser_les_raccourcis(HAUTEUR_CENTRALE)
            == resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES)


def test_Tab_DEPLACE_le_curseur_dans_la_liste_puis_le_ramene():
    objet = ecran()
    assert objet.basculer_la_zone(HAUTEUR_CENTRALE)
    assert objet.zone == resultat.ZONE_DE_LA_LISTE
    assert objet.basculer_la_zone(HAUTEUR_CENTRALE)
    assert objet.zone == resultat.ZONE_DES_ISSUES


def test_UN_SEUL_curseur_est_dessine_a_la_fois():
    """**L'invariant reel d'`EPIC11-ARB-50`**, mesure dans les deux etats.

    On compte les fleches dans le corps compose, pas dans une intention : deux
    zones navigables sont permises, deux curseurs simultanes ne le sont pas.
    """
    objet = ecran()
    for _ in range(2):
        lignes, _, _ = objet.composer(80, False, HAUTEUR_CENTRALE)
        fleches = [ligne for ligne in lignes
                   if jetons.GLYPHES["curseur"] in ligne]
        assert len(fleches) == 1, (objet.zone, fleches)
        objet.basculer_la_zone(HAUTEUR_CENTRALE)


def test_les_issues_restent_DESSINEES_ET_ENTIERES_quand_la_liste_a_la_main():
    """Elles perdent la main, elles ne disparaissent pas.

    C'est ce que `E5-5c` doit montrer, et c'est le volet symetrique du test
    ci-dessus : « un seul curseur » serait aussi vrai d'un ecran qui effacerait
    l'autre zone.
    """
    objet = ecran()
    objet.basculer_la_zone(HAUTEUR_CENTRALE)
    texte = "\n".join(objet.composer(80, False, HAUTEUR_CENTRALE)[0])
    for suite in resultat.SUITES:
        assert suite in texte
    assert objet.RETOUR in texte


def test_dans_la_liste_la_ligne_du_bas_PERD_la_touche_de_validation():
    """`⏎` n'a rien a valider sur un fichier ecrit : il n'est pas annonce."""
    objet = ecran()
    objet.basculer_la_zone(HAUTEUR_CENTRALE)
    ligne = objet.poser_les_raccourcis(HAUTEUR_CENTRALE)
    assert ligne == resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE
    assert "⏎" not in ligne


def test_dans_la_liste_la_touche_de_validation_est_AUSSI_inerte():
    """**La seconde moitie de la promesse.** Une touche retiree de la ligne mais
    encore active serait le defaut symetrique de la touche annoncee et inerte.
    """
    choisies = []
    objet = ecran(sur_suite=choisies.append)
    objet.basculer_la_zone(HAUTEUR_CENTRALE)
    evenement = _Evenement("enter")
    objet.on_key(evenement)
    assert choisies == []
    assert not evenement.arrete


def test_dans_les_issues_la_touche_de_validation_MARCHE():
    """Volet symetrique : elle n'est inerte que dans la liste."""
    choisies = []
    objet = ecran(sur_suite=choisies.append)
    objet.on_key(_Evenement("enter"))
    assert choisies == [resultat.SUITE_DOSSIER]


def test_les_deux_etats_annoncent_le_MEME_libelle_pour_Tab():
    """`Tab champ` des deux cotes -- « deux gestes identiques portent le meme
    mot » (regle `F-17`). La maquette validee le porte des deux cotes."""
    assert (resultat.JETON_DE_LA_BASCULE
            in resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES)
    assert (resultat.JETON_DE_LA_BASCULE
            in resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE)


def test_Tab_n_est_ni_offert_ni_annonce_quand_la_liste_TIENT_entiere():
    """Une touche annoncee qui ne fait rien se lit comme une panne."""
    objet = ecran(table_courte())
    assert not objet.liste_parcourable(HAUTEUR_CENTRALE)
    assert not objet.basculer_la_zone(HAUTEUR_CENTRALE)
    assert objet.zone == resultat.ZONE_DES_ISSUES
    assert (resultat.JETON_DE_LA_BASCULE
            not in objet.poser_les_raccourcis(HAUTEUR_CENTRALE))


def test_Tab_sur_une_liste_qui_tient_ne_CONSOMME_pas_la_touche():
    objet = ecran(table_courte())
    evenement = _Evenement("tab")
    objet.on_key(evenement)
    assert not evenement.arrete


# ---------------------------------------------------------------------------
# AC 10.4c -- la fenetre, et le mutant du rang absolu
# ---------------------------------------------------------------------------


def test_la_fenetre_est_RENDUE_par_jetons_et_jamais_recalculee():
    """Frontiere AST : le module appelle les deux fonctions du socle, et
    n'ecrit aucune arithmetique de fenetre a cote."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "jetons.fenetre_de_liste(" in source
    assert "jetons.recadrer_la_fenetre(" in source


def test_le_module_ne_definit_AUCUNE_fonction_de_fenetre_a_lui():
    """Volet symetrique : la frontiere ci-dessus resterait verte si le module
    appelait `jetons` a un endroit et recalculait a un autre."""
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    noms = {noeud.name for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.FunctionDef)}
    for interdit in ("fenetre_de_liste", "recadrer_la_fenetre"):
        assert interdit not in noms


def test_a_l_arrivee_la_fenetre_montre_les_QUATRE_premieres_et_le_compte():
    """`E5-5b` : `1-4 sur 7 PDF écrits`, et un seul `…`, en bas."""
    table = table_longue()
    hauteur = resultat.hauteur_de_la_fenetre(HAUTEUR_CENTRALE, 4, 2)
    assert hauteur == 5
    assert table.bornes(hauteur) == (0, 3)
    assert table.marqueur(hauteur) == "1-4 sur 7 PDF écrits"


def test_apres_le_Tab_et_QUATRE_fleches_la_fenetre_est_RECADREE_au_MILIEU():
    """`E5-5c` : `3-5 sur 7`, et les DEUX `…` visibles a la fois.

    **C'est le banc qui fait defiler la fenetre**, et c'est lui qui demasque
    une liste indexee sur le rang absolu : tant que la fenetre commence a zero,
    les deux indexations rendent le meme resultat.
    """
    objet = ecran()
    assert objet.basculer_la_zone(HAUTEUR_CENTRALE)
    for _ in range(4):
        objet.on_key(_Evenement("down"))
    hauteur = objet.hauteur_de_la_fenetre(HAUTEUR_CENTRALE)
    assert objet.table.curseur == 4
    assert objet.table.premier_visible == 2
    assert objet.table.bornes(hauteur) == (2, 4)
    assert objet.table.marqueur(hauteur) == "3-5 sur 7 PDF écrits"
    lignes, _, _ = objet.table.lignes(hauteur, 76, avec_curseur=True)
    ellipse = jetons.points_d_abregement()
    assert lignes[0].strip() == ellipse and lignes[-1].strip().startswith(ellipse)


def test_le_rang_du_curseur_rendu_est_celui_des_LIGNES_pas_le_rang_ABSOLU():
    """**Le mutant qui compte.** La fenetre commence au rang 2 et porte un `…`
    de tete : le curseur, absolu 3, est a la ligne **2** des lignes composees.

    Un module qui rendrait le rang absolu peindrait la mauvaise ligne, et
    aucune mesure calee en tete de liste ne le verrait.
    """
    table = table_longue(curseur=3, premier_visible=2)
    lignes, rang, _ = table.lignes(5, 76, avec_curseur=True)
    assert rang == 2
    assert rang != table.curseur
    assert jetons.GLYPHES["curseur"] in lignes[rang]
    assert SEPT_PLANCHES[3].nom.split("_")[1] in lignes[rang]


def test_la_fenetre_du_MILIEU_porte_les_DEUX_ellipses():
    """Celle du haut nue, celle du bas porteuse du compte -- la forme de `X4`."""
    table = table_longue(curseur=3, premier_visible=2)
    lignes, _, _ = table.lignes(5, 76, avec_curseur=True)
    ellipse = jetons.points_d_abregement()
    assert lignes[0].strip() == ellipse
    assert lignes[-1].strip().startswith(ellipse)
    assert "3-5 sur 7" in lignes[-1]


def test_les_fleches_NE_DEFILENT_PAS_elles_deplacent_et_la_fenetre_suit():
    """Un rang a la fois : la fenetre ne bouge pas tant que le curseur tient.

    Mesure de l'**entrelacement** : le couple (curseur, premier_visible) apres
    chaque fleche, dans l'ordre -- pas seulement l'etat final.
    """
    table = table_longue()
    hauteur = 5
    suite = []
    for _ in range(5):
        table.deplacer(1, hauteur)
        suite.append((table.curseur, table.premier_visible))
    assert suite == [(1, 0), (2, 0), (3, 0), (4, 2), (5, 3)]


def test_la_fenetre_ne_recule_JAMAIS_au_dela_de_zero():
    table = table_longue(curseur=0, premier_visible=0)
    for _ in range(3):
        table.deplacer(-1, 5)
    assert (table.curseur, table.premier_visible) == (0, 0)


def test_une_liste_qui_TIENT_ne_porte_aucune_ellipse():
    """Volet symetrique : `E5-5` ne montre ni `…` ni marqueur de fenetre."""
    lignes, _, _ = table_courte().lignes(5, 72)
    ellipse = jetons.points_d_abregement()
    assert all(ellipse not in ligne for ligne in lignes)
    assert len(lignes) == 2


def test_la_liste_ne_se_PARCOURT_que_si_elle_deborde():
    assert table_longue().se_parcourt(5)
    assert not table_courte().se_parcourt(5)


def test_une_liste_qui_tient_JUSTE_ne_se_parcourt_PAS():
    """La borne exacte : sept planches dans sept lignes tiennent entieres.

    C'est le seul point ou `>` et `>=` different, et sans lui `Tab` serait
    offert sur une liste ou il n'y a rien a parcourir -- la touche annoncee et
    inerte, par l'autre bout.
    """
    table = table_longue()
    assert not table.se_parcourt(len(SEPT_PLANCHES))
    assert table.se_parcourt(len(SEPT_PLANCHES) - 1)
    # Et la fenetre le confirme : elle rend les sept rangs, sans ellipse.
    assert table.bornes(len(SEPT_PLANCHES)) == (0, len(SEPT_PLANCHES) - 1)


# ---------------------------------------------------------------------------
# AC 10.1 -- le tableau : un PDF par ligne, ses pages, son rang
# ---------------------------------------------------------------------------


def test_chaque_ligne_porte_son_nom_ses_pages_et_son_RANG_de_tirage():
    lignes, _, _ = table_longue().lignes(5, 76)
    premiere = lignes[0]
    assert SEPT_PLANCHES[0].nom in premiere
    assert premiere.rstrip().endswith("21        2")
    assert premiere.startswith(resultat.INDENT_DES_LIGNES)


def test_le_rang_est_AFFICHE_jamais_recalcule():
    """`EPIC11-ARB-92`, frontiere AST : aucun resolveur de rang n'est appele."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8").lower()
    for interdit in ("resolve_version_rank", "version_ranks",
                     "nouvelle_version", "watermark", "ligne d'eau"):
        assert interdit not in source, interdit


def test_les_sept_rangs_de_la_fabrique_sont_rendus_TELS_QUELS():
    """Volet symetrique du precedent : le rang est bien affiche, pas ignore.

    Les rangs sont **tous distincts** de leur position dans la liste : un
    module qui rendrait l'index rendrait 1..7.
    """
    table = table_longue()
    rendus = []
    for premier in (0, 2, 4):
        table.premier_visible = premier
        for ligne in table.lignes(5, 76)[0]:
            if jetons.GLYPHES["complete"] in ligne:
                rendus.append(int(ligne.rstrip().rsplit(" ", 1)[-1]))
    attendus = {planche.rang for planche in SEPT_PLANCHES}
    assert set(rendus) <= attendus
    assert set(rendus) == attendus


#: Un nom dont le lot porte LUI-MEME le fragment de mise en page. Il est legal
#: -- rien n'interdit un `lot_id` qui contient `6f-pay` -- et c'est le seul cas
#: ou la premiere et la derniere occurrence different.
NOM_A_DEUX_FRAGMENTS = f"projet_demo_essai-{FRAGMENT}-bis_25_{FRAGMENT}_v3.pdf"


def test_l_abregement_protege_la_DERNIERE_occurrence_du_fragment():
    """La queue protegee est la mise en page **du nom**, pas une homonymie.

    Couper a la premiere occurrence garderait `-bis_25_6f-pay_v3.pdf` en queue
    -- plus long, donc moins de tete conservee -- et surtout couperait au
    milieu d'un segment de lot, ce que le fragment n'est pas la pour faire.
    """
    assert NOM_A_DEUX_FRAGMENTS.count(FRAGMENT) == 2
    largeur = 40
    abrege = resultat.abreger_le_nom_de_planche(NOM_A_DEUX_FRAGMENTS, largeur,
                                                FRAGMENT)
    assert jetons.colonnes(abrege) <= largeur
    points = jetons.points_d_abregement()
    queue = abrege.split(points)[-1]
    assert queue == f"{FRAGMENT}_v3.pdf"
    assert queue == NOM_A_DEUX_FRAGMENTS[NOM_A_DEUX_FRAGMENTS.rfind(FRAGMENT):]


def test_l_abregement_garde_la_TETE_du_nom_et_pas_seulement_la_queue():
    """Volet symetrique : c'est ce qui le distingue de `jetons.abreger_chemin`,
    qui coupe par le debut sur un nom sans separateur et rend deux lots
    indiscernables."""
    long = SEPT_PLANCHES[3].nom
    abrege = resultat.abreger_le_nom_de_planche(long, 45, FRAGMENT)
    assert abrege.startswith("projet_demo_sequence-12")
    assert abrege.endswith(".pdf")
    # Et sans fragment, on retombe **sur le socle**, pas sur une devinette.
    assert (resultat.abreger_le_nom_de_planche(long, 45)
            == jetons.abreger_chemin(long, 45))


def test_un_nom_LONG_est_abrege_et_ne_deborde_jamais():
    """La fabrique porte le nom de 57 caracteres de la maquette, expres."""
    long = SEPT_PLANCHES[3]
    assert len(long.nom) > 50
    for ascii_seul in (False, True):
        for utile in (76, 72, 60):
            lignes, _, _ = resultat.TableDesEcrits(
                (long,) + DEUX_PLANCHES, frames=1).lignes(5, utile, ascii_seul)
            for ligne in lignes:
                assert jetons.colonnes(ligne) <= utile, (utile, ligne)
        abrege = resultat.TableDesEcrits((long,) + DEUX_PLANCHES,
                                          frames=1).lignes(5, 60, ascii_seul)[0][0]
        assert jetons.points_d_abregement(ascii_seul) in abrege
        # **La queue est protegee** : le fragment de mise en page, le rang et
        # l'extension restent lisibles. Un abregement par le debut les
        # garderait aussi ; c'est la TETE qui distingue ce test.
        assert FRAGMENT in abrege
        assert abrege.lstrip().startswith(
            jetons.glyphes(ascii_seul)["complete"])


def test_toutes_les_planches_portent_le_glyphe_d_ETAT():
    lignes, _, etats = table_longue().lignes(5, 76)
    portees = [rang for rang, ligne in enumerate(lignes)
               if jetons.GLYPHES["complete"] in ligne]
    assert set(etats) == set(portees)
    assert etats == {rang: resultat.ETAT_DE_LA_PLANCHE for rang in portees}


def test_les_ETATS_sont_indexes_sur_les_LIGNES_pas_sur_le_rang_absolu():
    """**Le second mutant du rang absolu**, et il est distinct du premier.

    `rang_du_curseur` et `etats` sont deux indexations independantes : fermer
    l'une laisse l'autre ouverte. Fenetre au milieu, `…` de tete : les rangs
    absolus visibles sont 2, 3, 4 et les rangs de LIGNE 1, 2, 3.
    """
    lignes, _, etats = table_longue(curseur=3, premier_visible=2).lignes(
        5, 76, avec_curseur=True)
    assert sorted(etats) == [1, 2, 3]
    assert 0 not in etats and 4 not in etats
    for rang in etats:
        assert jetons.GLYPHES["complete"] in lignes[rang]
    # Volet symetrique : les deux lignes SANS glyphe sont bien les ellipses.
    ellipse = jetons.points_d_abregement()
    assert lignes[0].strip() == ellipse
    assert lignes[4].strip().startswith(ellipse)


# ---------------------------------------------------------------------------
# AC 10.2 / 10.7 -- les suites, ensemble EXACT
# ---------------------------------------------------------------------------


def test_l_ensemble_des_suites_est_EXACT_le_retour_compris():
    objet = ecran()
    assert objet.suites == list(resultat.SUITES) + [objet.RETOUR]


def test_la_suite_de_calibration_est_proposee_ICI_avec_son_motif():
    """Egan : on imprime les deux ensemble. La mention le dit."""
    lignes = resultat.lignes_des_suites(
        resultat.SUITES, resultat.ZONE_DES_ISSUES, 0, 76)
    calibration = [ligne for ligne in lignes
                   if resultat.SUITE_CALIBRATION in ligne][0]
    assert resultat.MENTION_CALIBRATION in calibration


def test_une_seule_suite_porte_une_mention():
    """Ensemble exact : « une assertion positive laisse passer toute divergence
    supplementaire »."""
    assert set(resultat.MENTIONS_DES_SUITES) == {resultat.SUITE_CALIBRATION}


def test_chaque_suite_est_atteignable_au_CLAVIER():
    """AC 10.7 : les quatre se visent par `↑↓`, et `⏎` les declenche."""
    choisies = []
    objet = ecran(sur_suite=choisies.append)
    for _ in range(len(objet.suites) - 1):
        objet.on_key(_Evenement("enter"))
        objet.on_key(_Evenement("down"))
    assert choisies == list(resultat.SUITES)


def test_le_curseur_des_issues_ne_DEBORDE_pas_la_liste():
    objet = ecran()
    for _ in range(20):
        objet.on_key(_Evenement("down"))
    assert objet.curseur == len(objet.suites) - 1
    for _ in range(20):
        objet.on_key(_Evenement("up"))
    assert objet.curseur == 0


# ---------------------------------------------------------------------------
# AC 10.3 / 10.6 -- l'explorateur, et le retour
# ---------------------------------------------------------------------------


def test_ouvrir_le_dossier_passe_par_execution_et_JAMAIS_par_subprocess():
    """Frontiere AST, pas textuelle : la PROSE a le droit de nommer
    `subprocess` pour dire ou il est tolere ; le CODE n'a pas le droit de
    l'importer ni de l'appeler."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "ouvrir_dans_l_explorateur_du_systeme" in source
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                assert alias.name.split(".")[0] not in ("subprocess", "os")
        elif isinstance(noeud, ast.ImportFrom):
            assert (noeud.module or "").split(".")[0] not in ("subprocess",
                                                              "os", "sys")
        elif isinstance(noeud, ast.Name):
            assert noeud.id not in ("subprocess", "print")
        elif isinstance(noeud, ast.Attribute) and isinstance(noeud.value,
                                                             ast.Name):
            assert (noeud.value.id, noeud.attr) != ("sys", "stdout")


def test_ouvrir_le_dossier_DIT_le_resultat_meme_quand_il_n_y_a_rien():
    """Un echec silencieux serait indistinguable d'une suite decorative."""
    class _Palier:
        def __init__(self):
            self.etat = None

        def poser_etat(self, texte):
            self.etat = texte

    app = _AppFactice()
    app.palier_courant = _Palier()
    fait = resultat.ouvrir_le_dossier_des_planches(app, None)
    assert fait == resultat.AUCUN_DOSSIER_A_OUVRIR
    assert app.palier_courant.etat == fait


def test_Echap_retombe_aux_ATELIERS_et_non_au_menu_Pdf():
    """AC 10.6 : c'est ce que la ligne annonce (`Échap ateliers`)."""
    objet = ecran()
    evenement = _Evenement("escape")
    objet.on_key(evenement)
    assert objet.app.ateliers == 1
    assert evenement.arrete
    for ligne in (resultat.RACCOURCIS_LISTE_ENTIERE,
                  resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES,
                  resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE):
        assert "Échap ateliers" in ligne


def test_Echap_retombe_aux_ateliers_AUSSI_depuis_la_liste():
    """La bascule ne doit pas creer une zone d'ou l'on ne sort plus."""
    objet = ecran()
    objet.basculer_la_zone(HAUTEUR_CENTRALE)
    objet.on_key(_Evenement("escape"))
    assert objet.app.ateliers == 1


# ---------------------------------------------------------------------------
# Le rendu, la grille, les frontieres
# ---------------------------------------------------------------------------


def test_le_corps_TIENT_la_hauteur_et_la_largeur_dans_les_deux_regimes():
    objet = ecran()
    for ascii_seul in (False, True):
        for largeur, hauteur in ((80, 24), (100, 30), (80, 20)):
            centre = resultat.hauteur_centrale(hauteur)
            lignes, _, _ = objet.composer(largeur, ascii_seul, centre)
            assert len(lignes) <= centre, (largeur, hauteur)
            for ligne in lignes:
                assert jetons.colonnes(ligne) <= jetons.largeur_utile(largeur)


def test_les_trois_lignes_de_raccourcis_tiennent_le_budget_des_DEUX_regimes():
    """MESURE commentee dans le module, refaite ici. Zone utile de 76."""
    for ligne in (resultat.RACCOURCIS_LISTE_ENTIERE,
                  resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES,
                  resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE):
        assert jetons.colonnes(ligne) <= 76, ligne
        assert jetons.colonnes(jetons.replier_ascii(ligne)) <= 76, ligne


def test_les_lignes_de_raccourcis_sont_celles_des_MAQUETTES():
    for nom, attendue in (
            ("E5-5-pdf-resultat.txt", resultat.RACCOURCIS_LISTE_ENTIERE),
            ("E5-5b-pdf-resultat-nombreux.txt",
             resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES),
            ("E5-5c-pdf-resultat-liste-parcourue.txt",
             resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE)):
        lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
        cadre = [ligne for ligne in lignes if ligne.startswith("│")]
        assert cadre[-1][2:-1].rstrip() == attendue, nom


def test_la_ligne_d_etat_porte_TROIS_mesures_et_pas_un_mot_de_mecanisme():
    ligne = resultat.ligne_d_etat(table_longue())
    assert ligne == "7 PDF écrits · 512 frames placées · aucun refus"
    for interdit in ("Échap", "Tab", "Entrée", "curseur", "zone"):
        assert interdit not in ligne


def test_la_mention_aucun_refus_TOMBE_quand_il_y_a_eu_un_refus():
    """Volet symetrique : le constat n'est pas une decoration permanente."""
    assert resultat.AUCUN_REFUS not in resultat.ligne_d_etat(table_longue(), 1)


def test_le_module_n_importe_JAMAIS_cli():
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    modules = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            modules.add(noeud.module or "")
    assert not any("cli" in nom.split(".") for nom in modules), modules


def test_aucun_glyphe_hors_de_la_table_n_entre_dans_le_module():
    """Ni `*` litteral -- il entrerait en collision avec le repli de `●` --, ni
    glyphe de deroulant : le depot n'en a aucun."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    for deroulant in ("▾", "▼", "▸▸", "►"):
        assert deroulant not in source, deroulant


def test_le_bandeau_ne_porte_aucun_terme_de_CONCEPTION():
    assert resultat.PALIER_DU_RESULTAT == "Pdf"
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8").lower()
    for interdit in ("parcours a part", "feuille cli", "point de jugement"):
        assert interdit not in source, interdit


# ---------------------------------------------------------------------------
# Les gardes de la fabrique elle-meme
# ---------------------------------------------------------------------------


def test_la_fabrique_porte_SEPT_planches_toutes_DISTINGUABLES():
    assert len(SEPT_PLANCHES) == 7
    assert len({planche.nom for planche in SEPT_PLANCHES}) == 7
    assert len({planche.pages for planche in SEPT_PLANCHES}) == 7


def test_la_fabrique_fait_bien_DEFILER_la_fenetre():
    """La garde du banc : sans defilement, le mutant du rang absolu survit."""
    table = table_longue()
    for _ in range(4):
        table.deplacer(1, 5)
    assert table.premier_visible > 0


def test_une_table_SANS_planche_est_refusee_a_la_construction():
    with pytest.raises(ValueError):
        resultat.TableDesEcrits(())
