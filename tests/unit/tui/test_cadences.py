# -*- coding: utf-8 -*-
"""La liste cochable des cadences -- story 11.4, AC 3, maquettes `E2-2`/`E2-2c`.

Tout se mesure sur le **modele pur** : il ne connait pas `textual`, donc aucun
de ces tests n'a besoin du banc ni d'un terminal. Le cablage aux ecrans est
mesure ailleurs (lot E).

**La regle des fabriques est appliquee, pas citee.** Toute fabrique de ce
fichier produit au moins deux cadences DISTINGUABLES -- des comptes de frames
differents, jamais un remplissage uniforme --, et chaque cible (la cochee, la
refusee, l'ajoutee, la visee) est placee au moins une fois **ailleurs qu'en
premiere position**. Le motif est celui de la story 5.7 de ce depot :
`_find_lot` rendait le PREMIER lot au lieu du lot vise et 257 tests restaient
verts, parce que toutes les fixtures multi-lots placaient la cible en premier.

**Le compteur de reference est le VRAI producteur** : `select_source_frames`,
appele sur une source de 124 frames a 25 im/s. Les quatre comptes de `E2-2`
(124, 62, 42, 31) ne sont donc pas recopies de la maquette dans les tests, ils
en sortent -- et le message d'un refus est celui que le coeur ecrit vraiment,
pas une chaine de fixture qui aurait sa propre orthographe.
"""
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE / "src") not in sys.path:  # pragma: no cover - amorce du banc
    sys.path.insert(0, str(RACINE / "src"))

import pytest

from outils_frontiere import chaines_de_code, identifiants

from mixed_media_utility import frame_selection
from mixed_media_utility.tui import cadences, jetons
from mixed_media_utility.tui.cadences import (
    COLONNES_DE_L_EXTRACTION,
    DIVISEURS_REMARQUABLES,
    HAUTEUR_LISTE,
    MENTION_TOUTES,
    MOTIF_AUCUNE_COCHEE,
    MOTIF_DIVISEUR_NUL,
    MOTIF_DOUBLON,
    MOTIF_PAS_UN_NOMBRE,
    MOTIF_SOURCE_INCONNUE,
    SEPARATEUR_DE_NOMMAGE,
    Cadence,
    CadencesMalFormees,
    ListeDeCadences,
    analyser_la_saisie,
    libelle_remarquable,
    nom_court_de_cadence,
    texte_de_cadence,
)

#: La cadence source d'un rush NTSC -- `24000/1001`, le 23,976 de tout materiel
#: americain. **Elle est dans ce banc pour une raison payee** : un garde-fou de
#: cette vague, ecrit puis RETIRE, refusait toute cadence a developpement
#: decimal infini. Il marchait sur un rush a 25 im/s et refusait, sur un rush
#: NTSC, la cadence SOURCE elle-meme -- la ligne « (toutes) ».
FPS_NTSC = Fraction(24000, 1001)

MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: La source de `E2-2` : 124 frames a 25 im/s. C'est elle qui rend 124, 62, 42
#: et 31 -- les quatre comptes de la maquette -- par le vrai coeur.
FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def compteur_reel(fps_source: Fraction = FPS_SOURCE,
                  source_frame_count: int = FRAMES_SOURCE):
    """Le compteur branche sur le VRAI producteur, `select_source_frames`.

    Un double aurait ses propres refus et ses propres mots ; celui-ci rend les
    cardinaux et **les messages** que le coeur produit, ce qui est la seule
    facon de mesurer que le modele les porte verbatim.
    """
    def compter(valeur: Fraction) -> int:
        return frame_selection.select_source_frames(
            fps_source=fps_source, fps_target=valeur,
            source_frame_count=source_frame_count).expected_frame_count
    return compter


def compteur_double(comptes: dict, refus: dict | None = None):
    """Des comptes DONNES, cadence par cadence, et des refus injectes.

    Il sert deux mesures qu'aucune source reelle ne rend : des comptes qui
    **contredisent** tout produit duree x cadence, et les quatre familles de
    refus de l'AC 3.5 provoquees a volonte sur la cadence de son choix.
    """
    refus = refus or {}

    def compter(valeur: Fraction) -> int:
        if valeur in refus:
            raise refus[valeur]
        return comptes[valeur]
    return compter


def liste_reelle(**kwargs) -> ListeDeCadences:
    """Les quatre remarquables d'une source a 25 im/s : 124, 62, 42, 31.

    Quatre comptes DIFFERENTS, donc quatre lignes distinguables : une
    permutation de l'appariement ligne/compte se verrait.
    """
    return ListeDeCadences.remarquables(FPS_SOURCE, compteur_reel(**kwargs))


def liste_avec_refus_en_troisieme() -> ListeDeCadences:
    """Une liste dont la cadence REFUSEE est en troisieme position.

    La cible n'est jamais en tete : un cochage qui porterait sur le premier
    element, ou une table d'etats calee sur le rang zero, resterait verte sur
    une fixture qui mettrait la refusee en premier.
    """
    valeurs = [FPS_SOURCE / d for d in DIVISEURS_REMARQUABLES]
    comptes = dict(zip(valeurs, (124, 62, 0, 31)))
    refus = {valeurs[2]: frame_selection.SelectionTooLargeError(
        "Lot trop volumineux: 1240 images seraient extraites, au-dela du "
        "plafond de 1000 images par lot.")}
    return ListeDeCadences.remarquables(
        FPS_SOURCE, compteur_double(comptes, refus))


def lignes_de_maquette(nom: str, premiere: int, derniere: int) -> list[str]:
    """Les lignes utiles d'une maquette, cadre et marges retires.

    La zone utile fait 76 colonnes : `│ ` a gauche, ` │` a droite. Les blancs
    de queue sont ceux du cadre, pas ceux du modele -- ils tombent des deux
    cotes de la comparaison.
    """
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").splitlines()
    return [ligne[2:-2].rstrip() for ligne in lignes[premiere:derniere]]


# ---------------------------------------------------------------------------
# AC 3.1 -- les cadences remarquables, en constante nommee, source lue du coeur
# ---------------------------------------------------------------------------

def test_la_liste_est_preremplie_des_QUATRE_cadences_remarquables():
    liste = liste_reelle()
    assert [c.valeur for c in liste.cadences] == [
        FPS_SOURCE, FPS_SOURCE / 2, FPS_SOURCE / 3, FPS_SOURCE / 4]
    assert [c.libelle for c in liste.cadences] == [
        "source", "source / 2", "source / 3", "source / 4"]


def test_la_liste_SUIT_la_constante_nommee_et_ne_recopie_pas_ses_diviseurs(
        monkeypatch):
    """AC 3.1 : la constante est la SOURCE de la liste, pas son commentaire.

    Une liste ecrite en dur rendrait les memes quatre cadences et resterait
    verte au test precedent. Remplacer la constante est ce qui distingue les
    deux.
    """
    monkeypatch.setattr(cadences, "DIVISEURS_REMARQUABLES", (1, 5))
    liste = ListeDeCadences.remarquables(FPS_SOURCE, compteur_reel())
    assert [c.valeur for c in liste.cadences] == [FPS_SOURCE, FPS_SOURCE / 5]


def test_la_cadence_source_est_LUE_du_coeur_en_fraction_exacte():
    """Une source NTSC reste `24000/1001`, jamais un flottant approche.

    `Fraction(23.976)` rend le ratio binaire du flottant la ou le coeur veut
    `24000/1001` : deux cadences proches et differentes, donc deux lots, et un
    doublon qui ne se voit plus.
    """
    source = Fraction(24000, 1001)
    liste = ListeDeCadences.remarquables(
        source, compteur_reel(fps_source=source))
    assert liste.cadences[0].valeur == source
    assert liste.cadences[2].valeur == Fraction(8000, 1001)


@pytest.mark.parametrize("saisie", [
    23.976, "25", None,
    # **`True`, et il n'est pas decoratif** (revue de la vague 3, couche 2,
    # finding `T4`). `bool` est une sous-classe d'`int` en Python, donc
    # `isinstance(True, int)` est VRAI et `Fraction(True) == 1` : sans la garde
    # `isinstance(valeur, bool)`, un `True` egare deviendrait une cadence source
    # de **1 image par seconde**, parfaitement valide et silencieuse. La moitie
    # « un flottant est refuse » etait mesuree, celle-ci ne l'etait pas -- le
    # mutant qui retire le `isinstance(..., bool)` survivait.
    True, False,
])
def test_une_cadence_source_QUI_N_EST_PAS_EXACTE_est_refusee(saisie):
    with pytest.raises(CadencesMalFormees, match="Fraction exacte"):
        ListeDeCadences.remarquables(saisie, compteur_reel())


def test_aucune_cadence_n_est_PRECOCHEE_au_montage():
    """Meme motif que `EPIC11-ARB-7` sur les issues : « Une issue
    preselectionnee transforme `Entree` en accident »."""
    assert liste_reelle().cochees == ()


# ---------------------------------------------------------------------------
# AC 3.2 -- le compte vient du coeur, JAMAIS d'un produit duree x cadence
# ---------------------------------------------------------------------------

def test_le_COMPTE_DE_FRAMES_vient_du_coeur_et_JAMAIS_d_un_produit_duree_x_cadence():
    """`EPIC11-ARB-30`, verbatim : « le noyau ne derive **jamais** le cardinal
    d'une duree, il l'exige ».

    Les comptes injectes ici **contredisent** tout produit : la source rend 100
    et sa moitie 77, ce qu'aucune multiplication ne peut produire. Un modele qui
    calculerait rendrait 50, et c'est la seule facon de mesurer qu'il ne calcule
    pas.
    """
    valeurs = [FPS_SOURCE / d for d in DIVISEURS_REMARQUABLES]
    comptes = dict(zip(valeurs, (100, 77, 91, 3)))
    liste = ListeDeCadences.remarquables(FPS_SOURCE, compteur_double(comptes))
    assert [c.compte for c in liste.cadences] == [100, 77, 91, 3]


def test_les_comptes_des_quatre_remarquables_sont_CEUX_DU_VRAI_producteur():
    """Test d'integration contre le producteur reel, et il ASSERTE.

    Le corollaire de `EPIC5-ARB-39` : « un test d'integration contre le vrai
    producteur ne suffit pas s'il n'assert pas ». Les quatre comptes sont
    asseres un par un, et ce sont ceux de la maquette.
    """
    assert [c.compte for c in liste_reelle().cadences] == [124, 62, 42, 31]


def test_le_modele_ne_NOMME_aucune_fonction_de_comptage_ni_aucune_duree():
    """Frontiere negative : comptage a zero sur le module.

    Il ne reference ni `select_source_frames`, ni `prepare_previz`, ni aucune
    duree : le compte lui arrive par le compteur injecte. Mesure sur l'ARBRE
    SYNTAXIQUE, jamais sur le texte -- le docstring du module cite `ARB-30`,
    qui porte le mot « duree », et un grep de prose s'y ferait affaiblir.
    """
    trouves = identifiants(Path(cadences.__file__))
    interdits = {"select_source_frames", "prepare_previz", "duree", "duration",
                 "duration_seconds", "source_duration_seconds", "secondes"}
    assert not (trouves & interdits), sorted(trouves & interdits)


def test_la_frontiere_du_comptage_MORD_sur_un_module_fautif(tmp_path):
    """Volet symetrique : sans lui, la mesure ci-dessus ne prouve rien."""
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text(
        '"""Un docstring qui parle de duree sans la nommer."""\n'
        "from ..frame_selection import select_source_frames\n"
        "def compter(duree, fps):\n"
        "    return int(duree * fps)\n", encoding="utf-8")
    assert {"select_source_frames", "duree"} <= identifiants(chemin)


@pytest.mark.parametrize("compte", [0, -1])
def test_un_compte_INFERIEUR_A_UNE_frame_est_refuse_a_la_construction(compte):
    """F1 de la fiche : le cas « zero frame » n'existe pas.

    `expected_frame_count = ceil(window_frame_count / step)` avec
    `window_frame_count >= 1` et `step > 0` rend **1** au minimum, toujours.
    Un zero ne vient donc pas du coeur : c'est une erreur d'appariement, et elle
    se leve plutot que de fabriquer une ligne que rien ne pourrait cocher.
    """
    with pytest.raises(CadencesMalFormees, match="1 au minimum"):
        Cadence(valeur=FPS_SOURCE, libelle="source", compte=compte)


def test_le_minimum_D_UNE_FRAME_est_bien_celui_du_coeur():
    """La fixture doit pouvoir atteindre le seuil qu'elle pretend mesurer.

    Sur une source d'UNE frame et une cadence de 1/1000, le coeur rend 1 et non
    0 : c'est la mesure qui rend l'invariant precedent legitime.
    """
    selection = frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=Fraction(1, 1000),
        source_frame_count=1)
    assert selection.expected_frame_count == 1


@pytest.mark.parametrize("compte, motif", [(None, None), (62, "refuse")])
def test_une_cadence_porte_son_compte_OU_son_motif_jamais_les_deux_ni_aucun(
        compte, motif):
    with pytest.raises(CadencesMalFormees, match="jamais les deux ni aucun"):
        Cadence(valeur=FPS_SOURCE, libelle="source", compte=compte, motif=motif)


# ---------------------------------------------------------------------------
# AC 3.3 -- Espace coche et decoche, le compte des cochees est rappele
# ---------------------------------------------------------------------------

def test_Espace_coche_la_cadence_SOUS_LE_CURSEUR_et_pas_la_premiere():
    """Le mutant vise : `self.cadences[0]` a la place de `self.courante`.

    La cible est en TROISIEME position : une fixture qui cocherait la premiere
    ne verrait jamais la difference.
    """
    liste = liste_reelle()
    liste.viser(FPS_SOURCE / 3)
    assert liste.basculer() is None
    assert [c.cochee for c in liste.cadences] == [False, False, True, False]


def test_Espace_DECOCHE_ce_qu_il_a_coche():
    liste = liste_reelle()
    liste.deplacer(1)
    liste.basculer()
    liste.basculer()
    assert liste.cochees == ()


def test_le_compte_des_cochees_est_la_SOMME_de_leurs_comptes():
    """Deux cochees hors premiere position, et une somme qui ne vaut aucune
    autre paire : 62 + 31 = 93."""
    liste = liste_reelle()
    liste.viser(FPS_SOURCE / 2).cochee = True
    liste.viser(FPS_SOURCE / 4).cochee = True
    assert liste.nombre_de_cochees == 2
    assert liste.frames_cochees == 93


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_de_compte_rappelle_les_cochees_et_leurs_frames(ascii_seul):
    liste = liste_reelle()
    for rang in (0, 1, 2):
        liste.cadences[rang].cochee = True
    attendu = "3 cochées sur 4 · 228 frames"
    if ascii_seul:
        attendu = jetons.replier_ascii(attendu)
    assert liste.ligne_de_compte(ascii_seul).strip() == attendu


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_de_compte_accorde_le_SINGULIER(ascii_seul):
    """« 1 cochée sur 4 · 124 frames », et non « 1 cochées »."""
    liste = liste_reelle()
    liste.cadences[0].cochee = True
    attendu = "1 cochée sur 4 · 124 frames"
    if ascii_seul:
        attendu = jetons.replier_ascii(attendu)
    assert liste.ligne_de_compte(ascii_seul).strip() == attendu


# ---------------------------------------------------------------------------
# AC 3.4 et 3.7 -- l'ajout libre DECIMAL, le fractionnaire refuse, le doublon
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("saisie", ["10,5", "10.5"])
def test_a_ajoute_une_cadence_libre_DECIMALE(saisie):
    """La virgule est celle de la langue de travail, le point celui du clavier
    numerique : les deux ecrivent la meme cadence."""
    liste = liste_reelle()
    assert liste.ajouter(saisie) is None
    ajoutee = liste.cadences[-1]
    assert ajoutee.valeur == Fraction(21, 2)
    assert ajoutee.libelle == "libre"
    # `ceil(124 / (25 / 10,5))` = 53, rendu par le coeur et non par le test.
    assert ajoutee.compte == 53


def test_la_cadence_ajoutee_recoit_son_compte_DU_COEUR():
    """Le compteur est appele avec la valeur EXACTE, et son resultat traverse."""
    vues = []

    def compter(valeur):
        vues.append(valeur)
        return compteur_reel()(valeur)

    liste = ListeDeCadences.remarquables(FPS_SOURCE, compter)
    vues.clear()
    liste.ajouter("5")
    assert vues == [Fraction(5)]
    assert liste.cadences[-1].compte == 25


def test_une_saisie_FRACTIONNAIRE_ENTRE_desormais_et_N_EST_PAS_arrondie():
    """`EPIC11-ARB-72`, verbatim : « Une saisie fractionnaire est **refusee
    nommement** [...], jamais silencieusement convertie : `25/3` arrondi en
    `8.333` ecrirait un lot dont le nom ment sur ce qu'il contient. »

    **Le refus tombe avec son motif, pas contre lui** (story 11.4, lot P). Ce
    que l'arbitrage protegeait, c'est le NOM -- et `EPIC11-ARB-62` le donne,
    verbatim : « Un lot a cadence fractionnaire s'appelle **`rush-001_25s3`** --
    le `s` tient la place de la barre. Le nom dit ce que l'operateur a demande
    (« une image sur trois »), ce qu'un nom decimal perdrait. » La cadence entre
    donc, **exacte** : ce qui reste interdit est l'arrondi.

    Le mutant vise : une conversion qui passerait par un `float`. `8,333` et
    `25/3` sont DEUX cadences differentes, et le test le mesure des deux cotes.
    """
    liste = liste_reelle()
    assert liste.ajouter("25/6") is None
    ajoutee = liste.cadences[-1]
    assert ajoutee.valeur == Fraction(25, 6)
    assert ajoutee.valeur != Fraction("4.167")
    assert ajoutee.nom_court() == "25s6"
    # Et l'arrondi decimal de la meme cadence est une AUTRE cadence, qui entre
    # a cote sans doublon : la valeur exacte n'a pas ete perdue en chemin.
    assert liste.ajouter("4,167") is None
    assert liste.cadences[-1].valeur == Fraction("4.167")


@pytest.mark.parametrize("saisie,valeur,libelle", [
    # Les cinq exemples d'Egan (2026-08-30), recopies un a un. Ils FONT FOI
    # pour la SAISIE et pour la VALEUR ; le libelle affiche, lui, a ete tranche
    # a part le meme soir (`EPIC11-ARB-94`, voir le docstring).
    ("25/5", Fraction(5), "source / 5"),
    ("2500/634", Fraction(2500, 634), "libre"),
    ("cs6", Fraction(25, 6), "source / 6"),
    ("25s6", Fraction(25, 6), "source / 6"),
    ("cadences6", Fraction(25, 6), "source / 6"),
])
def test_les_CINQ_exemples_d_Egan_font_foi(saisie, valeur, libelle):
    """Verbatim, 2026-08-30 : « 25/5 devrait etre accepte avec pour valeur 5 et
    a cote ecrit cadence/5 comme pour les autres. 25/6 devrait aussi passer avec
    sa valeur decimale et cadence/6 ecrit a cote. J'aimerais que l'utilisateur
    puisse ecrire "cadence/[nombre entier]" (avec cadence en toutes lettres), ou
    bien "c/[nombre entier]" avec l'abreviation "c/", puisse ecrire
    "[nombre entier]/[autre nombre entier]" ou encore remplacer le slash par un
    s (donc "cs[nombre entier]" ou encore "cadences[nombre entier]" ou encore
    "[nombre entier]s[nombre entier]"). »

    **Le verbatim est garde entier, et le libelle attendu ne le suit plus.**
    Ce n'est pas une contradiction laissee la : la phrase ci-dessus portait deux
    lectures qui se contredisaient -- le format cite (`cadence/5`) et la
    ressemblance demandee (« comme pour les autres »), or « les autres »
    affichent `source / N`, libelle de la maquette `E2-2` validee en trois
    passes. L'ecran a donc porte DEUX vocabulaires pour la meme notion, a trois
    lignes d'ecart, jusqu'a ce que le parcours `H3` le montre. Egan a tranche le
    2026-08-30 au soir, pour la ressemblance : `EPIC11-ARB-94`.

    Ce qui n'a pas bouge d'un caractere : la GRAMMAIRE de saisie. Les six
    ecritures de ce verbatim restent toutes acceptees en entree, et c'est le
    banc suivant qui le mesure.
    """
    obtenue, obtenu_libelle, motif = analyser_la_saisie(saisie, FPS_SOURCE)
    assert motif is None
    assert obtenue == valeur
    assert obtenu_libelle == libelle


@pytest.mark.parametrize("saisie", [
    "cadence/6", "cadences/6", "c/6", "cs/6", "cs6", "cadences6", "25/6",
    "25s6", "CS6", "25 / 3",
])
def test_toutes_les_ecritures_d_une_division_sont_acceptees(saisie):
    """La grammaire complete, et rien qu'elle : deux alias longs, deux courts,
    deux separateurs, la casse indifferente, les blancs autour du separateur.

    Le mutant vise : un alias perdu de la table, ou le separateur `s` ignore.
    """
    valeur, libelle, motif = analyser_la_saisie(saisie, FPS_SOURCE)
    assert motif is None, saisie
    # Le libelle est celui des remarquables depuis `EPIC11-ARB-94` : c'est
    # l'UNIFICATION qui est mesuree ici, pas le format. Ecrit en dur, jamais
    # obtenu de la constante -- un mutant qui changerait le patron casserait
    # sinon les deux cotes de l'egalite d'un coup.
    assert libelle.startswith("source / "), saisie
    assert valeur in (Fraction(25, 6), Fraction(25, 3))


def test_le_libelle_dit_source_sur_N_SEULEMENT_quand_le_numerateur_EST_la_source():
    """La regle, en une ligne : le numerateur qui **vaut la cadence source**
    donne `source / N` ; sinon `libre`.

    Le libelle est celui des remarquables depuis `EPIC11-ARB-94` -- un seul
    vocabulaire par ecran. Ce que ce banc mesure n'a pas change pour autant :
    c'est la FRONTIERE entre « division de la source » et « libre », pas le
    format de l'un des deux.

    Le mutant vise : `libre` rendu la ou `source / N` etait du, et l'inverse.
    Les deux sens sont mesures sur la MEME saisie, `25/5`, dont seule la source
    change -- une seule des deux directions laisserait passer la moitie du
    defaut.
    """
    _, sur_25, _ = analyser_la_saisie("25/5", Fraction(25))
    _, sur_30, _ = analyser_la_saisie("25/5", Fraction(30))
    assert sur_25 == "source / 5"
    assert sur_30 == "libre"
    # Et l'alias vaut TOUJOURS la source, quelle qu'elle soit.
    assert analyser_la_saisie("c/5", Fraction(30))[1] == "source / 5"

    # **Le volet d'unification d'`EPIC11-ARB-94`, et il est le point de
    # l'arbitrage** : une cadence SAISIE et une cadence REMARQUABLE qui
    # designent la meme division rendent le MEME libelle. C'est ce qui manquait
    # -- l'ecran portait `cadence/5` a trois lignes de `source / 2`.
    saisie = analyser_la_saisie("c/2", Fraction(25))[1]
    assert saisie == "source / 2"          # ecrit en dur : un mutant du patron
    assert saisie == libelle_remarquable(2)  # ET egal a ce que la LISTE produit


def test_un_ALIAS_de_source_passe_sur_un_rush_NTSC():
    """**Le piege deja paye, mesure a l'envers.** Le garde-fou retire de cette
    vague refusait tout developpement decimal infini : sur un rush NTSC il
    refusait la cadence SOURCE elle-meme. Ici `cadence/2` d'un rush NTSC passe,
    et son nom de lot est court et exact.
    """
    valeur, libelle, motif = analyser_la_saisie("cadence/2", FPS_NTSC)
    assert motif is None
    assert valeur == Fraction(12000, 1001)
    # L'ECRITURE `cadence/2` reste acceptee en entree ; c'est l'AFFICHAGE qui
    # s'unifie sur celui des remarquables (`EPIC11-ARB-94`).
    assert libelle == "source / 2"
    assert nom_court_de_cadence(valeur) == "12000s1001"
    # La ligne « (toutes) » elle-meme, celle que le garde-fou retire refusait.
    assert nom_court_de_cadence(FPS_NTSC) == "24000s1001"


def test_les_QUATRE_remarquables_d_un_rush_NTSC_ont_toutes_un_nom_court():
    """La mesure de `deferred-work.md`, prise a l'envers : les quatre cadences
    remarquables d'un rush NTSC rendaient `rush_01_23p976023976023978` et ses
    trois soeurs. Elles rendent desormais quatre noms courts et distincts.
    """
    noms = [nom_court_de_cadence(FPS_NTSC / d) for d in DIVISEURS_REMARQUABLES]
    assert noms == ["24000s1001", "12000s1001", "8000s1001", "6000s1001"]
    assert len(set(noms)) == len(noms)
    assert all(len(nom) <= 12 for nom in noms)


def test_une_division_par_ZERO_est_refusee_NOMMEMENT():
    """Le coeur ne verra jamais cette cadence : il n'y a pas de valeur a lui
    soumettre. Le refus est donc pris a la saisie, plutot que de laisser
    remonter une `ZeroDivisionError` nue.
    """
    liste = liste_reelle()
    avant = len(liste)
    assert liste.ajouter("25/0") == MOTIF_DIVISEUR_NUL
    assert liste.ajouter("c/0") == MOTIF_DIVISEUR_NUL
    assert len(liste) == avant


def test_un_ALIAS_dans_une_liste_qui_IGNORE_sa_source_est_refuse_NOMMEMENT():
    """Une liste batie a la main ne porte pas forcement sa source -- l'ecran du
    temps 2 en batit une. L'alias y est refuse **nommement** plutot que
    resolu en `libre` sur une source devinee.
    """
    liste = ListeDeCadences(
        cadences=[Cadence(valeur=Fraction(25), libelle="source", compte=124),
                  Cadence(valeur=Fraction(10), libelle="libre", compte=50)],
        compteur=compteur_reel())
    assert liste.fps_source is None
    assert liste.ajouter("c/5") == MOTIF_SOURCE_INCONNUE
    # La division CHIFFREE, elle, n'a besoin d'aucune source.
    assert liste.ajouter("25/5") is None
    assert liste.cadences[-1].libelle == "libre"


def test_la_saisie_fractionnaire_voit_le_doublon_AILLEURS_qu_en_tete_de_liste():
    """AC 3.7 par le chemin neuf. La cible est la TROISIEME des quatre cadences.

    Source a 25 im/s : les remarquables valent 25, 12,5, 25/3, 6,25. `c/3`
    tombe donc sur la troisieme -- ni la premiere, ni la derniere. Un doublon
    detecte en ne regardant que la tete, ou que la queue, resterait vert sur une
    fixture qui viserait `25` ou `6,25`.
    """
    liste = liste_reelle()
    avant = [c.valeur for c in liste.cadences]
    assert liste.rang(Fraction(25, 3)) == 2
    assert liste.ajouter("c/3") == MOTIF_DOUBLON
    assert liste.ajouter("25/3") == MOTIF_DOUBLON
    assert liste.ajouter("cs3") == MOTIF_DOUBLON
    assert [c.valeur for c in liste.cadences] == avant


# ---------------------------------------------------------------------------
# `EPIC11-ARB-62` -- le nom court d'une cadence
# ---------------------------------------------------------------------------

def test_le_nom_court_d_une_fractionnaire_est_celui_de_l_ARBITRAGE():
    """`EPIC11-ARB-62`, verbatim : « Un lot a cadence fractionnaire s'appelle
    **`rush-001_25s3`** -- le `s` tient la place de la barre. »

    Et `EPIC11-ARB-72`, verbatim, dont ce lot rend la premisse vraie : « leur
    nom de lot vient de la convention `_25s3` (`EPIC11-ARB-62`), pas de
    `format_fps_short` ». Au 2026-08-30, `deferred-work.md` mesurait que cette
    convention n'existait NULLE PART.
    """
    assert nom_court_de_cadence(Fraction(25, 3)) == "25s3"
    assert SEPARATEUR_DE_NOMMAGE in nom_court_de_cadence(Fraction(25, 3))


@pytest.mark.parametrize("valeur,attendu", [
    (Fraction(25), "25"),
    (Fraction(24), "24"),
    (Fraction(25, 2), "12p5"),
    (Fraction(25, 4), "6p25"),
    (Fraction(1, 8), "0p125"),
    (Fraction(25, 3), "25s3"),
    (Fraction(24000, 1001), "24000s1001"),
    (Fraction("8.333"), "8p333"),
])
def test_les_TROIS_familles_de_noms_courts(valeur, attendu):
    """Entiere, decimale finie, fractionnaire. Le mutant vise : le test de
    finitude du developpement decimal, qui decide de la famille."""
    assert nom_court_de_cadence(valeur) == attendu


def test_le_nom_court_d_une_decimale_FINIE_est_celui_des_lots_DEJA_LIVRES():
    """La compatibilite se mesure contre le VRAI producteur, `format_fps_short`,
    et non contre une table recopiee.

    C'est ce qui garantit qu'un lot a 12,5 im/s garde le nom qu'il a
    aujourd'hui, que l'ecriture passe ou non par le nom court.
    """
    from mixed_media_utility.io.naming import format_fps_short
    finies = [Fraction(n, d) for n in range(1, 121) for d in (1, 2, 4, 5, 8, 10)]
    for valeur in finies:
        assert nom_court_de_cadence(valeur) == format_fps_short(float(valeur)), valeur


def test_DEUX_cadences_DIFFERENTES_ne_rendent_JAMAIS_le_meme_nom_court():
    """La garde d'unicite, mesuree et non affirmee.

    Le mutant vise : un nom court qui perdrait son denominateur, ou qui
    confondrait les familles. Le domaine balaye les trois familles a la fois --
    entiers, decimales finies, fractions a developpement infini -- parce qu'une
    collision entre familles ne se verrait sur aucune des trois prises seule.
    """
    valeurs = set()
    for numerateur in range(1, 61):
        for denominateur in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1001):
            valeurs.add(Fraction(numerateur, denominateur))
    noms = {valeur: nom_court_de_cadence(valeur) for valeur in valeurs}
    assert len(set(noms.values())) == len(valeurs), [
        (v, n) for v, n in noms.items()
        if list(noms.values()).count(n) > 1]


def test_le_nom_court_est_une_fonction_de_la_SEULE_valeur():
    """`25/5`, `c/5` et `5` produisent la meme cadence, donc le meme nom -- ce
    qui est justement pourquoi elles ne peuvent pas coexister dans la liste
    (AC 3.7). Le libelle, lui, differe : il dit ce que l'operateur a ECRIT.
    """
    saisies = ["25/5", "c/5", "cs5", "5", "5,0"]
    valeurs = {analyser_la_saisie(s, FPS_SOURCE)[0] for s in saisies}
    assert valeurs == {Fraction(5)}
    assert {nom_court_de_cadence(v) for v in valeurs} == {"5"}


def test_les_fractionnaires_REMARQUABLES_restent_proposees_et_cochables():
    """Le meme arbitrage, son autre moitie : « Les cadences fractionnaires
    **remarquables** (`source / 3` = `25/3`) restent proposees et cochables ».

    C'est la frontiere que la saisie libre ne franchit pas, et elle doit rester
    visible : sans ce test, refuser tout ce qui est fractionnaire passerait.
    """
    liste = liste_reelle()
    tierce = liste.viser(Fraction(25, 3))
    assert tierce.cochable
    assert liste.basculer() is None
    assert tierce.cochee


def test_une_cadence_EN_DOUBLE_n_est_pas_ajoutee_deux_fois():
    """AC 3.7. La cible est la TROISIEME cadence de la liste, pas la premiere.

    Source a 24 im/s : les remarquables valent 24, 12, 8, 6, et `8` saisi tombe
    donc sur la troisieme. Un doublon detecte en ne regardant que la tete de
    liste resterait vert sur une fixture qui viserait `24`.
    """
    liste = ListeDeCadences.remarquables(
        Fraction(24), compteur_reel(fps_source=Fraction(24)))
    avant = [c.valeur for c in liste.cadences]
    assert liste.ajouter("8") == MOTIF_DOUBLON
    assert [c.valeur for c in liste.cadences] == avant


def test_le_doublon_se_mesure_sur_la_valeur_EXACTE_et_pas_sur_le_texte_affiche():
    """`8,333` saisi n'est PAS `25/3`, et les deux cohabitent.

    Ce n'est pas un contournement du doublon : ce sont deux cadences
    differentes, dont les lots porteront deux noms differents (`_8p333` contre
    la convention `_25s3` de `EPIC11-ARB-62`). Le test existe pour que la
    distinction soit voulue et non decouverte.
    """
    liste = liste_reelle()
    assert liste.ajouter("8,333") is None
    assert liste.cadences[-1].valeur == Fraction("8.333") != Fraction(25, 3)
    assert liste.ajouter("12,5") == MOTIF_DOUBLON


@pytest.mark.parametrize("saisie", ["", "   ", "abc", "12,5,3", "inf", "nan",
                                    "1e", "25:3", "-25/3", "25//3", "c3",
                                    "3/", "/3", "cadence"])
def test_une_saisie_HORS_GRAMMAIRE_est_refusee(saisie):
    """Ce que la grammaire n'accepte pas, et qui ne doit surtout pas entrer par
    la porte de derriere : `Fraction("-25/3")` reussit nativement, donc la garde
    des separateurs doit PRECEDER la conversion.

    `c3` et `cadence` sont la pour une raison propre : le separateur est
    **obligatoire**. Sans lui, `256` se lirait `25s6`.
    """
    liste = liste_reelle()
    avant = len(liste)
    assert liste.ajouter(saisie) == MOTIF_PAS_UN_NOMBRE
    assert len(liste) == avant


def test_un_ENTIER_A_TROIS_CHIFFRES_n_est_PAS_lu_comme_une_division():
    """`256` est deux cent cinquante-six, jamais `25s6`. Le mutant vise : le
    separateur rendu optionnel dans la grammaire."""
    valeur, libelle, motif = analyser_la_saisie("256", FPS_SOURCE)
    assert (valeur, libelle, motif) == (Fraction(256), "libre", None)


def test_le_curseur_SUIT_la_cadence_ajoutee():
    liste = liste_reelle()
    liste.ajouter("5")
    assert liste.curseur == len(liste) - 1
    assert liste.courante.valeur == Fraction(5)


# ---------------------------------------------------------------------------
# AC 3.5 -- ce que le coeur refuse : marque, non cochable, message du coeur
# ---------------------------------------------------------------------------

def test_une_cadence_que_le_coeur_REFUSE_n_est_PAS_COCHABLE():
    """Le mutant vise : `cochable` qui redeviendrait vrai, ou `basculer` qui
    cocherait sans regarder.

    La refusee est en TROISIEME position, et la premiere reste cochable : une
    fixture ou tout serait refuse ne distinguerait pas les deux cas.
    """
    liste = liste_avec_refus_en_troisieme()
    refusee = liste.viser(FPS_SOURCE / 3)
    assert refusee.refusee and not refusee.cochable
    assert liste.basculer() == refusee.motif
    assert not refusee.cochee
    assert liste.cochees == ()
    liste.viser(FPS_SOURCE)
    assert liste.basculer() is None


def test_cocher_une_cadence_refusee_est_refuse_MEME_a_la_construction():
    with pytest.raises(CadencesMalFormees, match="cochee alors que"):
        Cadence(valeur=FPS_SOURCE, libelle="source",
                motif="Sur-echantillonnage non supporte", cochee=True)


@pytest.mark.parametrize("erreur", [
    frame_selection.UpsamplingNotSupportedError,
    frame_selection.SelectionTooLargeError,
    frame_selection.InvalidFrameRateError,
    frame_selection.EmptySourceError,
])
def test_les_QUATRE_refus_reels_du_coeur_marquent_la_cadence(erreur):
    """Les quatre refus que l'AC 3.5 nomme, un par un.

    Ils derivent tous de `FrameSelectionError` : c'est cette racine unique que
    le modele capture, et la mesure porte sur les quatre familles plutot que sur
    la premiere.
    """
    valeurs = [FPS_SOURCE / d for d in DIVISEURS_REMARQUABLES]
    liste = ListeDeCadences.remarquables(FPS_SOURCE, compteur_double(
        dict(zip(valeurs, (124, 62, 0, 31))),
        {valeurs[2]: erreur("ce que le coeur en dit")}))
    assert liste.cadences[2].motif == "ce que le coeur en dit"
    assert liste.cadences[2].compte is None
    assert [c.refusee for c in liste.cadences] == [False, False, True, False]


def test_le_message_du_coeur_traverse_VERBATIM_et_n_est_jamais_reecrit():
    """AC 3.4 : « Les messages de refus sont **ceux du coeur**, jamais reecrits. »

    L'upsampling est provoque sur le VRAI producteur, et le message est compare
    a celui que l'exception porte : une seconde redaction cote TUI divergerait
    au premier ajustement du coeur.
    """
    liste = liste_reelle()
    assert liste.ajouter("30") is None
    ajoutee = liste.cadences[-1]
    with pytest.raises(frame_selection.UpsamplingNotSupportedError) as leve:
        compteur_reel()(Fraction(30))
    assert ajoutee.motif == str(leve.value)
    assert not ajoutee.cochable


def test_une_cadence_refusee_par_le_coeur_ENTRE_dans_la_liste():
    """AC 3.5 : elle s'y voit, marquee, plutot que de disparaitre.

    La sortir remplacerait un refus visible par un message qui passe.
    """
    liste = liste_reelle()
    liste.ajouter("30")
    assert liste.cadences[-1].refusee
    assert len(liste) == len(DIVISEURS_REMARQUABLES) + 1


def test_le_plafond_de_mille_images_est_un_refus_ATTEIGNABLE():
    """La fixture doit pouvoir atteindre le seuil qu'elle pretend mesurer.

    Sur une source de 1200 frames, la cadence source depasse
    `MAX_EXPECTED_FRAME_COUNT` et la premiere remarquable est refusee **par le
    coeur**, pas par une exception fabriquee a la main.
    """
    liste = ListeDeCadences.remarquables(
        FPS_SOURCE, compteur_reel(source_frame_count=1200))
    assert liste.cadences[0].refusee
    assert str(frame_selection.MAX_EXPECTED_FRAME_COUNT) in liste.cadences[0].motif
    assert liste.cadences[1].compte == 600


# ---------------------------------------------------------------------------
# AC 3.6 -- une validation a zero cochee ne passe jamais en silence
# ---------------------------------------------------------------------------

def test_une_validation_a_ZERO_cochee_rend_un_refus_NOMME():
    verdict = liste_reelle().valider()
    assert not verdict.passe
    assert verdict.motif == MOTIF_AUCUNE_COCHEE
    assert verdict.cochees == ()


def test_une_validation_rend_EXACTEMENT_les_cochees_dans_l_ordre_de_la_liste():
    """Les deux cochees sont en DEUXIEME et QUATRIEME position."""
    liste = liste_reelle()
    liste.viser(FPS_SOURCE / 4).cochee = True
    liste.viser(FPS_SOURCE / 2).cochee = True
    verdict = liste.valider()
    assert verdict.passe and verdict.motif is None
    assert [c.compte for c in verdict.cochees] == [62, 31]


def test_une_validation_ou_TOUT_est_refuse_ne_passe_pas_davantage():
    valeurs = [FPS_SOURCE / d for d in DIVISEURS_REMARQUABLES]
    liste = ListeDeCadences.remarquables(FPS_SOURCE, compteur_double(
        {}, {valeur: frame_selection.InvalidFrameRateError("cadence refusee")
             for valeur in valeurs}))
    assert liste.valider().motif == MOTIF_AUCUNE_COCHEE


# ---------------------------------------------------------------------------
# Le rendu : confronte a la maquette, ligne a ligne, dans les deux regimes
# ---------------------------------------------------------------------------

def test_les_QUATRE_lignes_rendues_sont_CELLES_DE_LA_MAQUETTE_E2_2():
    """La maquette fait foi sur le texte ET sur les colonnes.

    Un test qui n'interrogerait que le modele ne verrait aucune permutation du
    rendu : c'est le corollaire mesure de la regle des fabriques.
    """
    liste = liste_reelle()
    for rang in (0, 1, 2):
        liste.cadences[rang].cochee = True
    for _ in range(len(DIVISEURS_REMARQUABLES)):
        liste.ajouter(str(20 - _ * 5))
    liste.curseur = 0
    liste.premier_visible = 0
    rendues = [ligne.rstrip() for ligne in liste.lignes()]
    attendues = lignes_de_maquette("E2-2-extraction-cadences.txt", 6, 10)
    assert rendues[:4] == attendues
    assert rendues[6] == lignes_de_maquette(
        "E2-2-extraction-cadences.txt", 12, 13)[0]


def test_les_TROIS_lignes_du_temps_2_sont_CELLES_DE_LA_MAQUETTE_E2_2c():
    """`E2-2c` : memes lignes, autres colonnes -- la valeur porte ` fps` et le
    libelle disparait.

    **Aucune mention n'est portee depuis le lot `M`** (2026-08-30) : la colonne
    de droite portait `vue · temps réel tenu`, c'est-a-dire le verdict de
    temps reel, retire de TOUS les ecrans. La ligne s'arrete au compte.

    Les mentions sont vidées ici parce que c'est ce que le TEMPS 2 fait :
    `EcranChoixDesCadences` reconstruit ses `Cadence` a partir des seules
    valeur, libelle, compte et motif -- `(toutes)`, qui est la mention de la
    cadence source sur `E2-2`, ne traverse pas.
    """
    liste = liste_reelle()
    liste.cadences.pop()
    liste.cadences[0].cochee = True
    liste.cadences[2].cochee = True
    for cadence in liste.cadences:
        cadence.mention = ""
    rendues = [ligne.rstrip() for ligne
               in liste.lignes_de_liste(colonnes=COLONNES_DE_L_EXTRACTION)]
    assert rendues[:3] == lignes_de_maquette(
        "E2-2c-extraction-choix.txt", 6, 9)
    assert liste.ligne_des_lots().rstrip() == lignes_de_maquette(
        "E2-2c-extraction-choix.txt", 10, 11)[0]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_porte_la_cadence_du_RANG_demande_et_pas_celle_du_curseur(
        ascii_seul):
    """L'appariement rang / ligne, mesure sur quatre comptes DIFFERENTS.

    Une fabrique uniforme -- quatre cadences au meme compte -- rendrait quatre
    lignes identiques et ne verrait aucune permutation.
    """
    liste = liste_reelle()
    for rang, (valeur, compte) in enumerate(
            (("25", "124"), ("12,5", "62"), ("8,333", "42"), ("6,25", "31"))):
        ligne = liste.ligne(rang, ascii_seul=ascii_seul)
        assert valeur in ligne and f"{compte} frames" in ligne


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_GLYPHE_de_curseur_est_sur_la_ligne_visee_et_sur_elle_seule(
        ascii_seul):
    liste = liste_reelle()
    liste.viser(FPS_SOURCE / 3)
    lignes = liste.lignes_de_liste(ascii_seul=ascii_seul)
    curseur = jetons.glyphes(ascii_seul)["curseur"]
    porteuses = [rang for rang, ligne in enumerate(lignes)
                 if ligne.startswith("   " + curseur)]
    assert porteuses == [2]
    assert liste.rang_du_curseur() == 2


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_cadence_REFUSEE_porte_le_glyphe_absent_a_la_place_de_sa_case(
        ascii_seul):
    """Second canal de `DESIGN.md` section 6 : l'etat se lit SANS couleur.

    Et il ne se lit pas comme une case vide, qui inviterait a cocher ce qui
    n'est pas cochable.
    """
    liste = liste_avec_refus_en_troisieme()
    table = jetons.glyphes(ascii_seul)
    lignes = liste.lignes_de_liste(ascii_seul=ascii_seul)
    assert table["absent"] in lignes[2]
    assert table["decoche"] not in lignes[2]
    assert table["decoche"] in lignes[1]


def test_l_etat_ABSENT_est_DONNE_au_rang_de_la_ligne_refusee():
    """`EPIC11-ARB-71` : la couleur est POSEE la ou l'on sait qu'on ecrit un
    etat, au lieu d'etre retrouvee dans un texte.

    Le glyphe d'une ligne de liste est precede d'UN blanc : le repli par motif
    de `jetons.jeton_d_etat` ne le verrait pas, et aucune cadence refusee ne
    serait coloree.
    """
    liste = liste_avec_refus_en_troisieme()
    assert liste.etats_des_lignes() == {2: "absent"}
    lignes = liste.lignes()
    peint = jetons.peindre(lignes, ligne_du_curseur=liste.rang_du_curseur(),
                           etats=liste.etats_des_lignes())
    assert jetons.texte_affiche(peint).splitlines() == lignes


def test_l_etat_et_le_curseur_suivent_la_FENETRE_quand_la_liste_defile():
    """L'appariement rang de cadence / rang de ligne, decale par le `…` du haut.

    La refusee est en SIXIEME position et la fenetre commence a la cinquieme :
    une table d'etats calee sur le rang de la cadence rendrait 5, c'est-a-dire
    une ligne qui n'existe pas.
    """
    liste = liste_reelle()
    for valeur in ("20", "15", "10", "5"):
        liste.ajouter(valeur)
    liste.cadences[5].motif = "refus du coeur"
    liste.cadences[5].compte = None
    liste.viser(liste.cadences[7].valeur)
    liste.premier_visible = 4
    premier, dernier = liste.fenetre()
    assert (premier, dernier) == (4, 7)
    assert liste.etats_des_lignes() == {2: "absent"}
    assert liste.rang_du_curseur() == 4


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_zone_de_liste_garde_une_HAUTEUR_FIXE(ascii_seul):
    """Une cible qui se deplace quand la liste change de longueur est une cible
    qu'on rate."""
    liste = liste_reelle()
    assert len(liste.lignes_de_liste(ascii_seul=ascii_seul)) == HAUTEUR_LISTE
    for valeur in ("20", "15", "10", "5"):
        liste.ajouter(valeur)
    assert len(liste.lignes_de_liste(ascii_seul=ascii_seul)) == HAUTEUR_LISTE


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_de_position_annonce_la_fenetre_et_le_TOTAL(ascii_seul):
    liste = liste_reelle()
    for valeur in ("20", "15", "10", "5"):
        liste.ajouter(valeur)
    liste.premier_visible = 0
    liste.curseur = 0
    lignes = liste.lignes_de_liste(ascii_seul=ascii_seul)
    assert lignes[4].strip().endswith("1-4 sur 8 cadences")


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("largeur", [80, 100])
def test_AUCUNE_ligne_ne_deborde_de_la_grille(ascii_seul, largeur):
    """Y compris la plus longue : un message de coeur de plusieurs lignes,
    porte par une cadence dont le libelle est deja long."""
    liste = liste_reelle()
    liste.ajouter("30")
    liste.cadences[-1].mention = "vue · temps réel non tenu"
    utile = jetons.largeur_utile(largeur)
    for colonnes in (cadences.COLONNES_DU_CHOIX, COLONNES_DE_L_EXTRACTION):
        for ligne in liste.lignes(largeur, ascii_seul, colonnes):
            assert jetons.colonnes(ligne) <= utile, repr(ligne)


def test_le_repli_ASCII_ne_laisse_RIEN_hors_ASCII():
    liste = liste_reelle()
    liste.ajouter("30")
    liste.cadences[1].cochee = True
    liste.cadences[-1].mention = "vue · temps réel non tenu"
    rendues = liste.lignes(ascii_seul=True) + [liste.ligne_des_lots(True)]
    for ligne in rendues:
        assert ligne == ligne.encode("ascii", "replace").decode("ascii"), ligne


@pytest.mark.parametrize("valeur, attendu", [
    (Fraction(25), "25"), (Fraction(25, 2), "12,5"),
    (Fraction(25, 3), "8,333"), (Fraction(25, 4), "6,25"),
    (Fraction(24000, 1001), "23,976"),
])
def test_la_cadence_s_ecrit_comme_dans_la_maquette(valeur, attendu):
    assert texte_de_cadence(valeur) == attendu


def test_le_texte_de_la_cadence_n_est_QU_UN_RENDU():
    """`8,333` affiche, `25/3` garde : le lot se nommera `_25s3`
    (`EPIC11-ARB-62`), pas depuis ce texte."""
    liste = liste_reelle()
    assert texte_de_cadence(liste.cadences[2].valeur) == "8,333"
    assert liste.cadences[2].valeur == Fraction(25, 3)


# ---------------------------------------------------------------------------
# Navigation et invariants de liste
# ---------------------------------------------------------------------------

def test_le_curseur_ne_sort_JAMAIS_de_la_liste():
    liste = liste_reelle()
    liste.deplacer(-5)
    assert liste.curseur == 0
    liste.deplacer(50)
    assert liste.curseur == len(liste) - 1


def test_viser_place_le_curseur_sur_la_cadence_NOMMEE():
    """Cible en QUATRIEME position : un `viser` qui rendrait toujours la
    premiere -- le mutant `M25` de la story 5.7 -- resterait vert sur une
    fixture qui viserait la tete."""
    liste = liste_reelle()
    visee = liste.viser(FPS_SOURCE / 4)
    assert liste.curseur == 3
    assert visee is liste.cadences[3]


def test_viser_une_cadence_INCONNUE_nomme_celles_qui_existent():
    with pytest.raises(CadencesMalFormees, match="connues"):
        liste_reelle().viser(Fraction(7))


def test_une_liste_qui_porte_DEUX_FOIS_la_meme_cadence_est_refusee():
    with pytest.raises(CadencesMalFormees, match="meme valeur"):
        ListeDeCadences(
            cadences=[Cadence(FPS_SOURCE, "source", compte=124),
                      Cadence(FPS_SOURCE, "libre", compte=124)],
            compteur=compteur_reel())


def test_une_liste_VIDE_est_refusee():
    with pytest.raises(CadencesMalFormees, match="au moins une cadence"):
        ListeDeCadences(cadences=[], compteur=compteur_reel())


def test_la_mention_de_la_source_est_celle_de_la_maquette():
    liste = liste_reelle()
    assert liste.cadences[0].mention == MENTION_TOUTES
    assert [c.mention for c in liste.cadences[1:]] == ["", "", ""]


def test_aucun_terme_de_NOS_DOCUMENTS_dans_les_textes_du_module():
    """`EPIC11-ARB-28` : les termes de nos documents de decision « ne
    s'affichent jamais a l'ecran ».

    La mesure porte sur les chaines du CODE, docstrings exclus : le module cite
    ses arbitrages en prose, et c'est la ce qu'il doit faire.
    """
    interdits = ("EPIC11-ARB", "AC 3", "arbitrage", "story", "mutant",
                 "modele pur")
    for chaine in chaines_de_code(Path(cadences.__file__)):
        for terme in interdits:
            assert terme not in chaine, (terme, chaine)
