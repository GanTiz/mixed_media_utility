# -*- coding: utf-8 -*-
"""Story 11.4e, lot C -- ce que la declaration d'un rush CALCULE.

**Ce banc ne mesure aucun ecran, et c'est le partage que le lot assume.**
`EPIC11-ARB-144` exige la maquette `E2-1e` **et sa validation** avant que
l'ecran de declaration soit code ; aucune approbation d'Egan n'est consignee au
2026-09-05, apres trois publications (treize notes, puis huit, puis deux). Ce
qui est mesure ici est donc ce que ces ecrans **calculeront** -- et chacun des
deux calculs est tranche par un arbitrage nomme, independamment de toute mise
en page :

* le repliement du chemin source -- `EPIC11-ARB-151`, plus les notes 6
  (2026-09-01) et 9 (2026-09-02) d'Egan ;
* les issues et les suites du rush deja declare -- `EPIC11-ARB-147`, `-152`,
  `-156`, et `-231` qui les porte a TROIS des deux cotes.

Plus le geste de curseur de l'AC 3.7, qui vit dans `EcranRushes` et n'a jamais
attendu de maquette : `_relinker` le fait depuis la story 11.4, le chemin
d'ajout ne le faisait pas.

**Les sorties attendues sont LUES DANS LES MAQUETTES**, jamais recopiees ici.
C'est la seule facon qu'un test a de rougir le jour ou le produit et le dessin
divergent -- une chaine recopiee dans un banc fige l'accord du jour ou elle a
ete tapee, pas l'accord.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.declaration_de_rush import (
    ISSUES_PAR_MOTIF,
    MOTIF_RUSH_DEJA_DECLARE,
)
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.tui import ajout_de_rush, jetons
from mixed_media_utility.tui import atelier_extraction as amont
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

_MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "maquettes")


# ===========================================================================
# Lire les maquettes plutot que les recopier
# ===========================================================================

def chemin_de_la_maquette(nom: str) -> tuple[list[str], int]:
    """Les lignes du champ « Chemin complet » de `nom`, et leur largeur.

    **La largeur est DERIVEE du dessin**, jamais ecrite ici : le retrait de la
    colonne de valeur se lit sur la ligne de continuation, et la largeur
    disponible est ce qui reste du corps du cartouche. Ecrire `43` dans ce banc
    ferait exactement ce que `CLAUDE.md` reproche a un test tautologique --
    figer un nombre que la maquette peut bouger sans que rien ne rougisse.

    Rend `(lignes, largeur)`. Les lignes sont dans l'ordre du dessin.
    """
    texte = (_MAQUETTES / nom).read_text(encoding="utf-8")
    corps: list[str] = []
    for ligne in texte.splitlines():
        morceaux = ligne.split("│")
        # `│   │ <corps> │   │` : le corps du cartouche est le troisieme champ.
        if len(morceaux) == 5 and morceaux[1].strip() == "":
            corps.append(morceaux[2][1:-1])
    valeurs, retrait, largeur = [], None, None
    for rang, ligne in enumerate(corps):
        if ligne.startswith("Chemin complet"):
            suite = corps[rang + 1]
            retrait = len(suite) - len(suite.lstrip(" "))
            largeur = len(ligne) - retrait
            valeurs = [ligne[retrait:].rstrip(), suite[retrait:].rstrip()]
            break
    assert valeurs and largeur, f"{nom} ne porte pas de « Chemin complet »"
    return valeurs, largeur


#: `E2-1e` -- le chemin **tient** : deux lignes, rien de retire
#: (`EPIC11-ARB-151`). Le dessin porte le resultat ; l'entree, elle, est le
#: recollement de ses deux lignes, ce qui n'est vrai QUE parce que rien n'a ete
#: retire -- l'assertion du test le verifie plutot que de le supposer.
LIGNES_ENTIERES, LARGEUR_DE_VALEUR = chemin_de_la_maquette(
    "E2-1e-declaration-confirmation.txt")
CHEMIN_ENTIER = "".join(LIGNES_ENTIERES)

#: `E2-1h` -- le chemin **ne tient pas** : la coupe de la note 6, sur une
#: frontiere de separateur (note 9). Le dessin porte le resultat ; l'entree est
#: ecrite ici parce qu'elle n'est PAS dans le dessin -- c'est justement ce que
#: la coupe a retire.
LIGNES_COUPEES, LARGEUR_COUPEE = chemin_de_la_maquette(
    "E2-1h-declaration-chemin-coupe.txt")
SEGMENTS_LONGS = ("D:\\", "HOKO\\", "Documents\\", "clients\\", "arte\\",
                  "documentaire-chendj\\", "tournage\\", "03_tournage_mai\\",
                  "camera_A\\", "hd\\", "prores\\", "plan séquence 12.mov")
CHEMIN_LONG = "".join(SEGMENTS_LONGS)

#: Un corpus de chemins **distinguables** -- aucune valeur uniforme, aucun
#: chemin a segment unique repete : une permutation de segments ne se voit que
#: si les segments different (regle des fabriques, point 1).
CORPUS = (
    CHEMIN_ENTIER,
    CHEMIN_LONG,
    "/home/egan/rushes/2026/clients/arte/doc/03_mai/camA/hd/plan.mov",
    "/a/bb/ccc/dddd/eeeee/ffffff/ggggggg/hhhhhhhh/fin.mov",
    "relatif/sans/racine/rush.mov",
    "sans_separateur_du_tout.mov",
)


# ===========================================================================
# `plier_le_chemin` -- contre le DESSIN, au caractere pres
# ===========================================================================

def test_le_chemin_qui_TIENT_est_rendu_ENTIER_et_replie_comme_la_maquette():
    """`EPIC11-ARB-151` : « le chemin source est COMPLET, quitte a prendre
    plusieurs lignes ».

    Deux assertions et non une : que le rendu soit celui du dessin, **et** que
    rien n'ait ete retire. La seconde n'est pas redondante -- une coupe qui
    tomberait pile sur le meme decoupage rendrait les memes deux lignes tout en
    ayant mange un segment, et le premier `assert` seul ne le verrait pas.
    """
    replie = ajout_de_rush.plier_le_chemin(CHEMIN_ENTIER, LARGEUR_DE_VALEUR)
    assert replie == LIGNES_ENTIERES, replie
    assert "".join(replie) == CHEMIN_ENTIER, (
        "un segment a ete retire d'un chemin qui tenait : ARB-151 dit "
        "l'inverse")
    assert jetons.points_d_abregement() not in "".join(replie)


def test_le_chemin_qui_NE_TIENT_PAS_est_coupe_comme_la_maquette():
    """La note 6 d'Egan, et la note 9 par-dessus : la coupe tombe sur un `\\`.

    Le resultat est **lu dans `E2-1h`**. L'entree, elle, est ecrite ici : elle
    ne peut pas etre dans le dessin, puisque le dessin est ce qu'il en reste.
    """
    replie = ajout_de_rush.plier_le_chemin(CHEMIN_LONG, LARGEUR_COUPEE)
    assert replie == LIGNES_COUPEES, replie
    assert LARGEUR_COUPEE == LARGEUR_DE_VALEUR, (
        "les deux maquettes doivent partager la colonne de valeur, sans quoi "
        "les deux mesures ci-dessus ne se comparent pas")


@pytest.mark.parametrize("chemin", CORPUS)
@pytest.mark.parametrize("largeur", (12, 20, 30, 43, 60, 200))
def test_la_coupe_tombe_TOUJOURS_sur_une_frontiere_de_separateur(chemin,
                                                                 largeur):
    """**La note 9, en frontiere** : « traiter les dossiers comme des blocs
    insecables dans la mesure du possible ».

    Verbatim d'Egan : « `...uc/tournage_juin/hd` » est fautif. La mesure porte
    donc sur les deux moities de la coupe -- tout ce qui precede les points est
    un prefixe de segments ENTIERS, tout ce qui suit un suffixe de segments
    ENTIERS. Un compte de caracteres passerait le test de la maquette et
    echouerait ici, et c'est tout l'objet de la note 9.

    **Le repli de dernier ressort est exclu explicitement**, pas par
    inadvertance : « dans la mesure du possible » est ecrit deux fois dans la
    note, et un chemin dont un segment depasse la ligne n'a aucune frontiere ou
    tomber. Il est mesure a part.
    """
    segments = ajout_de_rush.segments_de_chemin(chemin)
    if any(jetons.colonnes(s) > largeur for s in segments):
        pytest.skip("aucune frontiere ne tient : c'est le repli de dernier "
                    "ressort, mesure par son propre test")
    replie = ajout_de_rush.plier_le_chemin(chemin, largeur)
    entier = "".join(replie)
    points = jetons.points_d_abregement()
    if points not in entier:
        assert entier == chemin
        return
    tete, _, queue = entier.partition(points)
    assert queue.startswith(tuple(jetons.SEPARATEURS_DE_CHEMIN)), (
        f"la coupe ne rend pas la main sur un separateur : {entier!r}")
    queue = queue[1:]
    assert chemin.startswith(tete), (
        f"la tete n'est pas un prefixe du chemin : {tete!r}")
    assert chemin.endswith(queue), (
        f"la queue n'est pas un suffixe du chemin : {queue!r}")
    assert not tete or tete.endswith(tuple(jetons.SEPARATEURS_DE_CHEMIN)), (
        f"la tete coupe un nom de dossier en deux : {tete!r}")
    assert "".join(segments[:len(ajout_de_rush.segments_de_chemin(tete))]) \
        == tete
    assert len(tete) + len(queue) < len(chemin), (
        "les points sont poses sans que rien n'ait ete retire")


@pytest.mark.parametrize("chemin", CORPUS)
@pytest.mark.parametrize("largeur", (12, 20, 30, 43, 60, 200))
@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_ne_DEPASSE_jamais_la_largeur(chemin, largeur,
                                                   ascii_seul):
    """La mesure en COLONNES, dans les deux regimes, sur tout le corpus.

    C'est la frontiere qui attrape le defaut que `panneau.LigneChiffree` a paye
    en revue de vague 2 bis : une mesure en `len()` rend une ligne que le code
    croit calee juste pour le double de sa largeur reelle, et le regime ASCII
    rend `...` la ou `…` valait une colonne. Les deux se voient ici et nulle
    part ailleurs.
    """
    for ligne in ajout_de_rush.plier_le_chemin(chemin, largeur,
                                               ascii_seul=ascii_seul):
        assert jetons.colonnes(ligne) <= largeur, (
            f"{ligne!r} fait {jetons.colonnes(ligne)} colonnes pour "
            f"{largeur}")


def test_une_ligne_remplie_EXACTEMENT_n_est_pas_repliee():
    """Un `<` la ou il faut un `<=` fait deborder ce qui tient pile.

    **L'erreur d'une colonne ne se voit que sur la valeur exacte** : a une
    colonne pres dans un sens comme dans l'autre, les deux redactions rendent
    le meme decoupage, et c'est pourquoi aucun des autres tests de ce banc ne
    l'attrape. Ici la largeur est prise sur le chemin lui-meme, jamais ecrite
    a la main -- un nombre recopie cesserait de tomber juste au premier
    ajustement de la maquette.
    """
    juste = jetons.colonnes(CHEMIN_ENTIER)
    assert ajout_de_rush.plier_le_chemin(CHEMIN_ENTIER, juste,
                                         lignes=1) == [CHEMIN_ENTIER]
    # Volet symetrique : une colonne de moins, et il faut bien deux lignes --
    # sans quoi le test du dessus passerait aussi sur une fonction qui rend
    # toujours le chemin entier.
    replie = ajout_de_rush.plier_le_chemin(CHEMIN_ENTIER, juste - 1, lignes=2)
    assert len(replie) == 2 and "".join(replie) == CHEMIN_ENTIER, replie


@pytest.mark.parametrize("chemin", CORPUS)
def test_un_chemin_qui_tient_ne_PERD_RIEN(chemin):
    """A largeur confortable, le recollement rend le chemin, caractere pour
    caractere. C'est l'invariant de :func:`segments_de_chemin`, pris par le
    haut."""
    replie = ajout_de_rush.plier_le_chemin(chemin, 400)
    assert "".join(replie) == chemin
    assert replie == [chemin], "une seule ligne suffit a 400 colonnes"


def test_le_separateur_de_la_coupe_est_celui_DU_CHEMIN():
    """Volet symetrique, et il mord sur la plateforme ou personne ne regarde.

    Rendre `\\` a un chemin POSIX -- ou l'inverse -- fabriquerait une coupe qui
    n'existe sur aucune des deux plateformes. Les deux sens sont mesures : sans
    le second, un `return "/"` en dur passerait la moitie du test.
    """
    posix = "/home/egan/rushes/2026/clients/arte/doc/03_mai/camA/hd/plan.mov"
    replie = "".join(ajout_de_rush.plier_le_chemin(posix, 30))
    assert jetons.points_d_abregement() + "/" in replie, replie
    assert "\\" not in replie

    replie = "".join(ajout_de_rush.plier_le_chemin(CHEMIN_LONG, 30))
    assert jetons.points_d_abregement() + "\\" in replie, replie
    assert "/" not in replie


def test_la_tete_est_FIXE_et_la_queue_est_un_MINIMUM():
    """L'asymetrie de la note 6, et elle se mesure sur `E2-1h`.

    « en gardant les **3 premiers** dossiers de l'arborescence et les **deux
    derniers au moins** » : la tete est une quantite, la queue un plancher.
    Chercher la queue d'abord rend un chemin licite mais pas celui de la
    maquette -- `D:\\HOKO\\…\\tournage\\03_tournage_mai\\` au lieu de
    `D:\\HOKO\\Documents\\…\\03_tournage_mai\\`. Les deux passent la frontiere
    de la note 9 ; seul le second est le dessin.
    """
    tete = "".join(SEGMENTS_LONGS[:ajout_de_rush.TETE_DE_CHEMIN])
    replie = "".join(ajout_de_rush.plier_le_chemin(CHEMIN_LONG,
                                                  LARGEUR_COUPEE))
    assert replie.startswith(tete), (
        f"la tete de {ajout_de_rush.TETE_DE_CHEMIN} segments n'est pas "
        f"gardee : {replie!r}")
    gardes = ajout_de_rush.segments_de_chemin(
        replie.split(jetons.points_d_abregement())[1][1:])
    assert len(gardes) >= ajout_de_rush.QUEUE_DE_CHEMIN, gardes
    assert len(gardes) > ajout_de_rush.QUEUE_DE_CHEMIN, (
        "la queue ne s'est pas etendue : elle est un plancher, pas une "
        "quantite")


def test_la_tete_CEDE_quand_aucune_queue_ne_tient_a_cote_d_elle():
    """« Dans la mesure du possible », deuxieme occurrence.

    A largeur serree, garder trois segments de tete ne laisse la place a aucune
    queue -- et une queue vide perdrait le nom du fichier, c'est-a-dire la
    seule chose que l'operateur cherchait. La tete cede alors, et le nom reste.
    """
    segments = ("AAAAAAAAAAAA\\", "BBBBBBBBBBBB\\", "CCCCCCCCCCCC\\",
                "d\\", "e\\", "f.mov")
    replie = ajout_de_rush.plier_le_chemin("".join(segments), 18)
    entier = "".join(replie)
    assert segments[-1] in entier, entier
    tete = entier.split(jetons.points_d_abregement())[0]
    assert len(ajout_de_rush.segments_de_chemin(tete)) \
        < ajout_de_rush.TETE_DE_CHEMIN, tete


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_repli_ASCII_precede_la_mesure(ascii_seul):
    """`…` vaut une colonne, `...` en vaut trois.

    Choisir les points APRES avoir compte fait deborder de deux colonnes une
    ligne calee juste -- la regression payee sur le bandeau le 2026-08-28, puis
    a nouveau sur la ligne chiffree en revue de vague 2 bis. Le test mesure les
    deux moities : la forme des points, et le fait qu'aucune ligne ne deborde.
    """
    replie = ajout_de_rush.plier_le_chemin(CHEMIN_LONG, 30,
                                           ascii_seul=ascii_seul)
    entier = "".join(replie)
    if ascii_seul:
        assert "..." in entier and "\u2026" not in entier, entier
        assert entier.isascii(), (
            f"le regime --ascii rend du non-ASCII : {entier!r}. Le repli du "
            "CHEMIN a ete saute -- seuls les points l'ont ete")
        assert "plan sequence 12.mov" in entier, entier
    else:
        assert "\u2026" in entier and "..." not in entier, entier
    for ligne in replie:
        assert jetons.colonnes(ligne) <= 30


def test_le_repli_de_DERNIER_RESSORT_est_borne_et_ne_leve_pas():
    """Un segment plus large que la ligne : aucune frontiere ou tomber.

    La note 9 dit « dans la mesure du possible » deux fois : ce cas est
    l'impossible, et il se **nomme** plutot que de lever. On retombe sur la
    regle du depot pour un chemin qu'on lit -- une ligne, bornee, coupee au
    caractere. Sans ce chemin, un nom de dossier long ferait tomber l'ecran.
    """
    chemin = "/a/b/c/" + "n" * 40 + ".mov"
    replie = ajout_de_rush.plier_le_chemin(chemin, 20)
    assert len(replie) == 1, replie
    assert jetons.colonnes(replie[0]) <= 20
    assert replie[0].endswith(".mov"), (
        "le repli de dernier ressort a mange le nom du fichier")


@pytest.mark.parametrize("largeur,lignes", ((0, 2), (-3, 2), (20, 0),
                                            (20, -1)))
def test_une_place_NULLE_rend_une_liste_vide_et_jamais_une_exception(largeur,
                                                                     lignes):
    """Une zone trop etroite est un etat d'ecran, pas une erreur a lever --
    c'est ce que `jetons.abreger_chemin` dit deja de son propre cas."""
    assert ajout_de_rush.plier_le_chemin(CHEMIN_LONG, largeur,
                                         lignes=lignes) == []


def test_les_segments_recolles_rendent_le_chemin():
    """L'invariant de :func:`segments_de_chemin`, et les deux separateurs
    ensemble : un chemin mixte se recolle aussi."""
    for chemin in CORPUS + ("D:\\a/b\\c.mov", "", "x"):
        assert "".join(ajout_de_rush.segments_de_chemin(chemin)) == chemin


# ===========================================================================
# Le rush deja declare : les issues LUES du coeur, les suites COMPOSEES ici
#
# **Les deux cardinaux ont cesse de diverger le 2026-09-05, et l'ecart etait
# NOMME dans les deux sens.** `EPIC11-ARB-231` a porte le refus du COEUR a
# trois issues (relinker, declarer separement, annuler) ; l'ECRAN est reste a
# deux suites le temps que sa maquette soit redessinee et validee, parce
# qu'`EPIC11-ARB-144` interdit de coder une planche non validee. Cette place
# portait donc un volet symetrique qui EXIGEAIT la divergence, et il disait de
# lui-meme : « le jour ou la planche a trois sorties est validee, ce test
# rougit -- et c'est le bon moment pour qu'il rougisse. » C'est ce qui est
# arrive, et c'est ce que ce lot ferme.
#
# Ce que ce banc mesure donc, et la distinction reste le sujet du fichier :
# les issues du coeur sont **lues** et jamais recopiees -- leur cardinal suit
# l'arbitrage tout seul --, tandis que les suites d'ecran sont **composees**
# ici sur les libelles de la maquette. Ce qui se rejoint est le CARDINAL et
# l'ORDRE ; le TEXTE, lui, diverge toujours et doit diverger -- la table du
# coeur porte des lignes de commande (`mmu relink --project ...`) qui ne se
# tapent pas depuis une TUI.
# ===========================================================================

NOM_DU_FICHIER = "plan séquence 12.mov"
CHEMIN_DESIGNE = "D:\\HOKO\\Documents\\rushes\\2026\\04_tournage_juin\\hd\\"


def test_les_issues_du_refus_sont_LUES_dans_la_table_du_coeur():
    """`EPIC11-ARB-156` : les issues sont **lues**, jamais recopiees.

    C'est le motif meme pour lequel `ISSUES_PAR_MOTIF` est publiee --
    « dupliquer le vocabulaire laisserait deux verites au meme moment, et un
    test symetrique ne rougirait qu'**apres** qu'on a diverge ».

    **Ce test mesurait `len(issues) == 1` jusqu'au 2026-09-05**, sur la foi
    d'`EPIC11-ARB-147` (« refus SEC, une seule issue »). `EPIC11-ARB-231` le
    supersede sur ce point precis : le refus de conflit d'identite porte
    **trois** issues. C'est la TROISIEME frontiere vivante que l'arbitrage
    fait rougir -- le document du 2026-09-05 n'en annoncait que deux, celles
    de `tests/unit/test_declaration_de_rush.py`.

    Le cardinal se lit desormais de la table plutot que d'un litteral, ce qui
    est ce que l'identite `is` disait deja : un banc qui ecrit le nombre a
    cote de la lecture recopie a moitie, et c'est cette moitie-la qui a du
    etre corrigee a la main aujourd'hui.
    """
    issues = ajout_de_rush.issues_du_refus()
    assert issues is ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE], (
        "les issues sont RECOPIEES et non lues : une seconde redaction du "
        "vocabulaire des refus ne rougirait qu'APRES avoir diverge")
    assert len(issues) == len(ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE])
    assert len(issues) == 3, (
        f"EPIC11-ARB-231 : relinker, declarer separement, annuler. "
        f"Recu {issues}")
    for motif, attendues in ISSUES_PAR_MOTIF.items():
        assert ajout_de_rush.issues_du_refus(motif) == attendues


def test_le_cardinal_de_l_ECRAN_a_REJOINT_celui_du_COEUR():
    """La fermeture de l'ecart, et elle se mesure des DEUX cotes.

    Ce test remplace `test_volet_symetrique_l_ECRAN_reste_a_DEUX_suites_tant_
    que_la_maquette`, qui exigeait l'inverse -- deux suites a l'ecran contre
    trois issues au coeur -- tant que la planche a trois sorties n'etait pas
    validee. Elle l'est (`EPIC11-ARB-231`), et l'ancien volet a rougi au bon
    moment, ce pour quoi il avait ete ecrit.

    **Le cardinal se LIT de la table du coeur, jamais d'un litteral.** C'est
    ce que l'ancien volet avait a moitie rate : il ecrivait `== 2` a cote
    d'une lecture, et c'est cette moitie-la qu'il a fallu corriger a la main
    le jour de l'arbitrage. Ici, une quatrieme issue ajoutee demain au coeur
    fait rougir l'ecran plutot que de passer.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(NOM_DU_FICHIER,
                                                      CHEMIN_DESIGNE)
    issues = ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE]
    assert len(choix.issues) == len(issues), (
        "les suites de l'ECRAN et les issues du COEUR ont cesse d'avoir le "
        f"meme cardinal : {len(choix.issues)} contre {len(issues)}. Soit un "
        "arbitrage en a ajoute une d'un cote seulement, soit la maquette "
        "E2-1f a bouge sans que la TUI suive (EPIC11-ARB-144)")


def test_le_TEXTE_des_suites_ne_RECOPIE_pas_celui_du_coeur():
    """Frontiere NEGATIVE : le cardinal se rejoint, le texte doit diverger.

    Sans elle, la fermeture ci-dessus inviterait au geste exactement fautif --
    lire les libelles dans `ISSUES_PAR_MOTIF` puisque le cardinal coincide.
    Les phrases du coeur sont des lignes de COMMANDE (« ... avec `mmu relink
    --project <projet> --rush <rush_id> --video <fichier>` ») : posees a
    l'ecran, elles proposeraient a l'operateur de quitter la TUI pour taper ce
    que la TUI vient de lui offrir de faire.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(NOM_DU_FICHIER,
                                                      CHEMIN_DESIGNE)
    du_coeur = ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE]
    for issue in choix.issues:
        assert issue.libelle not in du_coeur, (
            f"la suite {issue.cle} recopie le texte du coeur : {issue.libelle}")
        assert "mmu " not in issue.libelle, (
            f"la suite {issue.cle} propose une ligne de commande a une TUI : "
            f"{issue.libelle}")
        assert "--" not in issue.libelle, (
            f"la suite {issue.cle} nomme un drapeau de CLI : {issue.libelle}")


def test_les_TROIS_suites_sont_EXACTEMENT_celles_de_la_maquette_ET_DANS_L_ORDRE():
    """`EPIC11-ARB-231`, verbatim : « L'ordre porte la recommandation. »

    En egalite EXACTE sur la liste ordonnee, jamais en appartenance : une
    quatrieme suite glissee demain, ou deux lignes permutees, passeraient
    toute assertion prise suite par suite. Une permutation n'est pas un detail
    de rendu -- elle deplace ce que l'ecran CONSEILLE.

    **Les libelles sont LUS dans la maquette**, jamais recopies ici : c'est la
    regle du fichier (« une chaine recopiee dans un banc fige l'accord du jour
    ou elle a ete tapee, pas l'accord »), et c'est aussi ce qui fait de ce
    banc le pendant TUI de `test_maquette_E2_1f_trois_sorties.py`, qui mesure
    le dessin.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(NOM_DU_FICHIER,
                                                      CHEMIN_DESIGNE, 76)
    assert [issue.cle for issue in choix.issues] == [
        ajout_de_rush.CLE_RELINKER, ajout_de_rush.CLE_SEPARER,
        ajout_de_rush.CLE_ANNULER], (
        "l'ORDRE compte autant que l'ensemble : la maquette porte l'action "
        "recommandee en premier, la sortie neuve au MILIEU et Annuler en "
        "queue, et c'est ce qui rend le deplacement du curseur "
        "d'EPIC11-ARB-7 visible")
    assert [issue.ecrit for issue in choix.issues] == [True, True, False], (
        "des trois suites, seule Annuler n'ecrit pas -- la sortie neuve cree "
        "une seconde entree rushes[]")


def test_la_sortie_NEUVE_n_est_ni_en_TETE_ni_en_QUEUE():
    """Le rang de la sortie neuve EST la recommandation.

    En tete, l'ecran conseillerait de declarer un second rush la ou le cas
    ordinaire est un relink ; en queue, elle passerait pour une variante
    d'`Annuler`. Mesurer sa presence sans mesurer son rang laisserait les deux
    derives passer -- meme mesure que sur la maquette, et c'est voulu : les
    deux doivent bouger ensemble.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(NOM_DU_FICHIER,
                                                      CHEMIN_DESIGNE)
    cles = [issue.cle for issue in choix.issues]
    rang = cles.index(ajout_de_rush.CLE_SEPARER)
    assert 0 < rang < len(cles) - 1, cles


def test_le_curseur_ne_vise_JAMAIS_la_suite_qui_ECRIT():
    """`EPIC11-ARB-7`, tenu par `EPIC11-ARB-45` et jamais reecrit ici.

    Relinker ecrit, annuler non. Le curseur doit donc partir sur `Annuler`, ce
    que la maquette `E2-1f` dessine (`▸ Annuler`). Le mesurer par
    `ecrit is False` plutot que par la cle est delibere : c'est l'invariant qui
    compte, et il survivrait a un renommage des cles.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(NOM_DU_FICHIER,
                                                      CHEMIN_DESIGNE)
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.issues[choix.curseur].cle == ajout_de_rush.CLE_ANNULER
    assert choix.action_qui_ecrit.cle == ajout_de_rush.CLE_RELINKER
    assert choix.retenue is None, "aucune issue n'est preselectionnee"


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_TROIS_suites_sont_reellement_ATTEIGNABLES(ascii_seul):
    """La revue d'`ARB-224` vient de trouver un refus dont une issue etait
    **intypable** : nommee au modele, absente du rendu.

    La mesure porte donc sur les deux bouts -- la cle se resout, et le libelle
    apparait bien dans le rendu. Une suite qu'on ne peut pas voir ne se choisit
    pas.

    **Le balayage porte sur les issues RENDUES, pas sur une liste de cles
    ecrite ici** : une liste ecrite aurait laisse la sortie neuve d'`ARB-231`
    hors mesure le jour ou elle est arrivee -- c'est exactement ce qui s'est
    passe, ce test ne citait que `relinker` et `annuler`. Les trois cles sont
    quand meme confrontees a l'inventaire, sans quoi un balayage sur une liste
    vide passerait sans rien mesurer.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(
        NOM_DU_FICHIER, CHEMIN_DESIGNE, ascii_seul=ascii_seul)
    rendu = "\n".join(choix.rendu(ascii_seul))
    assert {issue.cle for issue in choix.issues} == {
        ajout_de_rush.CLE_RELINKER, ajout_de_rush.CLE_SEPARER,
        ajout_de_rush.CLE_ANNULER}
    for issue in choix.issues:
        assert issue.libelle, issue.cle
        assert issue.libelle in rendu, (
            f"l'issue {issue.cle} est nommee au modele et absente du rendu : "
            "elle est intypable")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_libelle_de_relink_nomme_le_FICHIER_et_le_CHEMIN_designe(
        ascii_seul):
    """Notes 3 et 4 d'Egan : « relinker [rushe] vers [chemin designe] ».

    La note 4 dit pourquoi cette formulation suffit seule : elle **reintroduit
    le chemin designe**, que l'ecran ne porte nulle part ailleurs. Et le nom
    montre est `source_name`, accents et espaces compris -- jamais
    l'identifiant derive (`EPIC11-ARB-153`, renforce par `-141`).
    """
    libelle = ajout_de_rush.libelle_de_relink(NOM_DU_FICHIER, CHEMIN_DESIGNE,
                                              78, ascii_seul)
    attendu = (jetons.replier_ascii(NOM_DU_FICHIER) if ascii_seul
               else NOM_DU_FICHIER)
    assert attendu in libelle, libelle
    assert "04_tournage_juin" in libelle, (
        "le chemin designe a disparu : la note 4 tombe avec lui")
    assert "plan-sequence-12" not in libelle, (
        "l'identifiant derive n'a rien a faire sur cet ecran (ARB-153)")


@pytest.mark.parametrize("largeur", (40, 55, 78, 120))
@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_libelle_de_relink_ne_DEPASSE_pas_sa_ligne(largeur, ascii_seul):
    """Une issue fait une ligne par contrat : le chemin s'abrege AU MILIEU.

    C'est le cas symetrique de :func:`plier_le_chemin`, ou la hauteur existe --
    et c'est pourquoi les deux ne partagent pas leur regle.
    """
    libelle = ajout_de_rush.libelle_de_relink(NOM_DU_FICHIER, CHEMIN_DESIGNE,
                                              largeur, ascii_seul)
    assert jetons.colonnes(libelle) <= largeur, (
        f"{jetons.colonnes(libelle)} colonnes pour {largeur} : {libelle!r}")


# ===========================================================================
# AC 3.7 -- le curseur se pose sur le rush DECLARE
# ===========================================================================

#: Cinq rushes **distinguables**, pour que la cible puisse etre placee en tete,
#: au milieu ET en queue (regle des fabriques, points 1, 2 et 4). Un balayage
#: tronque et un `find` qui rend le premier element sont deux modes de panne
#: differents, et seule une cible a chaque bord les separe.
RUSHES = ("rush_00_avant", "rush_01_puis", "rush_02_milieu", "rush_03_ensuite",
          "rush_04_apres")


def projet(tmp_path, rushes=RUSHES) -> Path:
    """Un projet reel dont le manifeste porte `rushes`, dans cet ORDRE."""
    dossier = creer_projet(tmp_path, "projet_demo").chemin
    sources = tmp_path / "sources"
    sources.mkdir(exist_ok=True)
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    entrees = []
    for rang, rush_id in enumerate(rushes):
        # Des tailles DIFFERENTES : un appariement positionnel entre l'entree
        # du manifeste et son fichier se verrait.
        chemin = sources / f"{rush_id}.mov"
        chemin.write_bytes(b"x" * (10 + rang))
        entrees.append({"rush_id": rush_id, "source_path": str(chemin)})
    document["rushes"] = entrees
    (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                             encoding="utf-8")
    return dossier


#: Trois videos dans le dossier de l'explorateur, la cible **au milieu** : ni
#: premiere -- un curseur qui ne bouge pas la rendrait --, ni derniere.
VIDEOS = ("a_premiere.mov", "b_cible.mov", "c_derniere.mov")
VIDEO_CIBLE = VIDEOS[1]


def dossier_des_videos(tmp_path) -> Path:
    """Les trois videos que l'explorateur listera, de tailles distinctes."""
    dossier = tmp_path / "rushes_a_ajouter"
    dossier.mkdir(exist_ok=True)
    for rang, nom in enumerate(VIDEOS):
        (dossier / nom).write_bytes(b"y" * (20 + rang))
    return dossier


def coque(ecran) -> CoqueTui:
    """Deux paliers temoins puis l'ecran mesure : la pile du banc."""
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


async def designer_la_video(pilote, ecran):
    """`Tab`, descendre jusqu'a la video du MILIEU, `⏎`.

    **Le parcours clavier reel**, jamais un appel direct a la methode de
    validation : c'est le piege que `test_journal_du_produit.py` raconte --
    « le banc mesurait un parcours qui n'est pas celui du produit, sur le seul
    point ou les deux different ». La cible est verifiee avant la validation,
    sans quoi un test qui validerait la premiere entree passerait aussi.
    """
    ecran.traiter("tab")
    await pilote.pause()
    assert ecran.zone == amont.ZONE_EXPLORATEUR
    for _ in range(len(ecran.explorateur.entrees)):
        cible = ecran.explorateur.cible_de_validation()
        if cible is not None and cible.name == VIDEO_CIBLE:
            break
        ecran.traiter("down")
    cible = ecran.explorateur.cible_de_validation()
    assert cible is not None and cible.name == VIDEO_CIBLE, cible
    ecran.traiter("enter")
    await pilote.pause()
    return cible


def ecrire_le_rush(dossier: Path, rush_id: str, rang: int):
    """Un double d'ecriture qui ecrit VRAIMENT, au rang demande.

    Il rend le `rush_id` -- c'est le contrat que l'AC 3.7 exige du rappel, et
    c'est ce que le coeur rend deja (`DeclarationDeRush.rush_id`).
    """
    def ajouter(cible: Path) -> str:
        document = json.loads(
            (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        entrees = list(document["rushes"])
        entrees.insert(rang, {"rush_id": rush_id, "source_path": str(cible)})
        document["rushes"] = entrees
        (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                                 encoding="utf-8")
        return rush_id
    return ajouter


def apres_un_ajout(banc, monkeypatch, tmp_path, dossier, ajouter,
                   depart: str = RUSHES[0], ascii_seul: bool = False):
    """Monter `E2-1`, poser le curseur sur `depart`, declarer, rendre l'ecran.

    Le curseur de depart est **pose et verifie** : sans ce controle, un test ou
    la cible arrive pile sous le curseur passerait sans rien mesurer.
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    ecran = amont.EcranRushes(dossier, ajouter=ajouter)

    async def scenario(pilote):
        pilote.app.ascii_seul = ascii_seul
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.liste.viser(depart)
        assert ecran.liste.courant.rush_id == depart
        await designer_la_video(pilote, ecran)
        return ecran

    return banc(coque(ecran), scenario)


@pytest.mark.parametrize("rang,depart", (
    (0, RUSHES[0]),                 # en TETE : la liste entiere se decale
    (2, RUSHES[1]),                 # au MILIEU
    (len(RUSHES), RUSHES[-1]),      # en QUEUE : rien ne se decale
))
def test_le_curseur_se_pose_sur_le_rush_DECLARE_a_CHAQUE_BORD(
        tmp_path, banc, monkeypatch, rang, depart):
    """AC 3.7, et la regle des fabriques point 4 : tete, milieu **et** queue.

    **Ce que la relecture seule ne fait pas.** `relire()` repose le curseur au
    RANG qu'il occupait ; un rush insere AVANT ce rang decale toute la liste
    d'un cran, et l'operateur retrouve la surbrillance sur son voisin. Un rush
    insere en queue ne decale rien -- c'est le cas ou l'oubli du `viser` est
    INVISIBLE, et c'est pourquoi il est mesure lui aussi : un correctif qui ne
    traiterait que l'insertion en tete passerait les deux autres cas.

    Les rangs voisins sont nommes dans les parametres pour que le test dise ce
    qu'il aurait vu SANS le correctif, plutot que seulement ce qu'il attend.
    """
    dossier = projet(tmp_path)
    ecran = apres_un_ajout(banc, monkeypatch, tmp_path, dossier,
                           ecrire_le_rush(dossier, "rush_zz_neuf", rang),
                           depart=depart)
    assert ecran.liste.courant.rush_id == "rush_zz_neuf", (
        f"le curseur est reste sur {ecran.liste.courant.rush_id}")
    voisins = [r.rush_id for r in ecran.liste.rushes]
    assert voisins[rang] == "rush_zz_neuf", voisins
    assert voisins == list(RUSHES[:rang]) + ["rush_zz_neuf"] \
        + list(RUSHES[rang:]), voisins


def test_un_rappel_qui_ne_rend_RIEN_laisse_le_curseur_ou_il_est(
        tmp_path, banc, monkeypatch):
    """Le contrat d'AVANT, et il ne se rompt pas.

    N'importe quelle fonction sans `return` rend `None`, et les bancs de `K1.1`
    injectent `list.append`. Un `viser` qui exigerait un identifiant les ferait
    rougir pour un cablage qui n'a pas encore de raison de nommer son rush.
    """
    dossier = projet(tmp_path)
    ajoutes: list[Path] = []
    ecran = apres_un_ajout(banc, monkeypatch, tmp_path, dossier,
                           ajoutes.append, depart=RUSHES[2])
    assert [c.name for c in ajoutes] == [VIDEO_CIBLE], ajoutes
    assert ecran.liste.courant.rush_id == RUSHES[2]
    assert ecran._etat_a_dire == "", (
        "un rappel muet par contrat ne doit rien faire dire a la ligne d'etat")


def test_le_rush_vise_est_celui_que_le_RAPPEL_a_nomme(tmp_path, banc,
                                                      monkeypatch):
    """`EPIC11-ARB-9` : le coeur peut avoir SUFFIXE l'identifiant.

    Deux rushes homonymes venus de deux dossiers differents sont deux rushes
    distincts, et le second est ecrit sous un identifiant suffixe. Un ecran qui
    redeviserait le `rush_id` depuis le nom du fichier viserait alors
    l'homonyme -- c'est-a-dire poserait la surbrillance sur le rush de
    QUELQU'UN D'AUTRE, le mode de panne du mutant `M25` de la story 5.7.

    La fabrique place donc l'homonyme **avant** la cible : viser le premier
    identifiant qui commence pareil se demasque.
    """
    dossier = projet(tmp_path, ("neuf", ) + RUSHES)
    ecran = apres_un_ajout(banc, monkeypatch, tmp_path, dossier,
                           ecrire_le_rush(dossier, "neuf-hd", 3),
                           depart=RUSHES[0])
    assert ecran.liste.courant.rush_id == "neuf-hd", (
        f"le curseur vise {ecran.liste.courant.rush_id} : l'identifiant a ete "
        "redevine au lieu d'etre lu du rappel")


def test_un_rush_declare_ABSENT_de_la_liste_relue_se_DIT(tmp_path, banc,
                                                         monkeypatch):
    """Une incoherence entre deux sources se nomme, elle ne se tait pas.

    Un rappel qui annonce `rush_x` alors que le manifeste relu ne le porte pas
    n'est pas un no-op : c'est le silence de `K1.1` un cran plus loin. Le
    curseur ne bouge pas -- il n'y a nulle part ou aller -- mais la ligne
    d'etat le dit.
    """
    dossier = projet(tmp_path)
    ecran = apres_un_ajout(banc, monkeypatch, tmp_path, dossier,
                           lambda cible: "rush_fantome", depart=RUSHES[2])
    assert ecran.liste.courant.rush_id == RUSHES[2]
    assert "rush_fantome" in ecran._etat_a_dire, ecran._etat_a_dire
    assert ecran._etat_a_dire == amont.phrase_de_rush_declare_introuvable(
        "rush_fantome")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_une_declaration_reussie_le_DIT_en_ligne_d_etat(tmp_path, banc,
                                                        monkeypatch,
                                                        ascii_seul):
    """`EPIC11-ARB-81` : une reparation muette et une reparation ratee se
    ressemblent trop. Une declaration muette aussi -- c'est litteralement
    `K1.1`.

    La phrase est mesuree par **identite** avec la fonction qui la produit,
    jamais par une chaine recopiee : le libelle peut changer, la regle non.
    """
    dossier = projet(tmp_path)
    ecran = apres_un_ajout(banc, monkeypatch, tmp_path, dossier,
                           ecrire_le_rush(dossier, "rush_zz_neuf", 2),
                           depart=RUSHES[0], ascii_seul=ascii_seul)
    assert ecran._etat_a_dire == amont.phrase_de_declaration_reussie(
        "rush_zz_neuf", ascii_seul)
    assert ecran._etat_a_dire != amont.phrase_de_declaration_reussie(
        "rush_zz_neuf", not ascii_seul), (
        "les deux regimes rendent la meme chaine : le repli ASCII ne joue pas")
