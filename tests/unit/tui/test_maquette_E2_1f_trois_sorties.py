# -*- coding: utf-8 -*-
"""`E2-1f` porte TROIS sorties, et l'ORDRE des trois est mesure.

**Ce que cette frontiere ferme** (`EPIC11-ARB-231`, Egan le 2026-09-05).
L'ecran de conflit `rush-deja-declare` portait deux sorties -- relinker et
annuler. `EPIC11-ARB-230` ayant retire le dossier parent des criteres
d'identite, il restait un cas ou les quatre criteres coincident sur **deux
rushes reellement differents** : deux cameras jam-synchronisees, cartes
formatees pareil, `prise01.mov` sur les deux. Meme nom, meme duree, meme
cadence, meme timecode initial, deux angles. Sans une troisieme sortie,
`ARB-230` en fait un **faux conflit sans issue**, ce qu'`EPIC11-ARB-89`
interdit nommement.

**Pourquoi l'ORDRE et pas seulement la presence.** L'arbitrage l'ecrit :
« L'ordre porte la recommandation. » Un banc qui ne mesurerait que
l'appartenance laisserait permuter les trois lignes sans rougir -- et une
permutation deplace la recommandation, c'est-a-dire ce que l'ecran conseille
a l'operateur. La mesure porte donc sur la **liste ordonnee**, en egalite
exacte, jamais en appartenance.

**L'ECART AVEC LA TUI EST FERME** (2026-09-05, meme journee que sa mise au
registre). Ce paragraphe disait, jusqu'a la fermeture : « elle mesure la
MAQUETTE, pas le code de la TUI. `tui/ajout_de_rush.suites_du_rush_deja_
declare` construit encore DEUX issues au 2026-09-05, et
`test_ajout_de_rush_tui.py::test_les_DEUX_suites_sont_EXACTEMENT_relinker_et_
annuler` reste vert en le disant. [...] Le jour ou il les atteint, c'est ce
banc-ci qui dit ce que le rendu doit devenir. »

C'est ce jour-la. `ARB-231` a atteint le coeur (`ISSUES_PAR_MOTIF` porte trois
entrees), puis la TUI : `suites_du_rush_deja_declare` rend trois issues, et
`atelier_extraction.EcranRefusDeConflit` les dessine. La derniere section de ce
fichier porte donc le volet que la promesse annoncait : **le rendu de la TUI
contre la maquette**, memes libelles, meme ordre. Sans lui, la fermeture serait
declaree et non mesuree -- et ce banc continuerait de mesurer un dessin que
personne ne serait tenu de suivre.

**Ce que cette frontiere NE mesure PAS, dit plutot que tu.**

* elle ne juge aucune couleur ni aucun calage : `test_maquettes_couleur_a_
  jour.py` tient le rendu, `test_maquettes_txt_a_jour_de_leur_generateur.py`
  tient que ce `.txt` est bien ce que `_gen_extraction.py` produit. Sans ce
  second banc, mesurer le `.txt` mesurerait un produit qui a pu deriver de sa
  source ; avec lui, mesurer le `.txt` revient a mesurer le generateur ;
* le volet TUI ci-dessous mesure les LIBELLES et leur ORDRE, pas la geometrie :
  le cartouche, ses quatre criteres et la ligne d'etat de l'ecran monte sont
  tenus par `test_ecran_E2_1f_refus_de_conflit.py`, qui a les fabriques du
  coeur sous la main. Deux bancs, deux questions -- « le dessin dit-il ce que
  l'arbitrage a tranche ? » ici, « le produit rend-il le dessin ? » la-bas.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
SOURCES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
           / "ux-tui-2026-08-27" / "maquettes")
MAQUETTE = SOURCES / "E2-1f-declaration-rush-deja-declare.txt"

#: La grille plancher, en lignes et en colonnes. Ce qui la depasse dans un
#: `.txt` est une annotation manuscrite d'Egan, jamais du contenu d'ecran.
HAUTEUR_GRILLE = 24
LARGEUR_GRILLE = 80

#: Les trois sorties d'`EPIC11-ARB-231`, **dans l'ordre de l'arbitrage**.
#: Recopiees ici depuis le document de decision et non depuis la maquette :
#: une constante tiree de la maquette qu'elle mesure serait une tautologie.
LES_TROIS_SORTIES = (
    "Relinker plan séquence 12.mov vers D:\\…\\04_tournage_juin\\hd\\",
    "C'est un autre rush, le déclarer séparément",
    "Annuler",
)

#: La sortie NEUVE de l'arbitrage, et son rang. Le rang est le point : elle
#: n'est ni en tete (la recommandation reste le relink) ni en queue
#: (`Annuler` ferme toujours la liste).
SORTIE_NEUVE = LES_TROIS_SORTIES[1]
RANG_DE_LA_SORTIE_NEUVE = 1

#: Le glyphe de curseur et l'indentation d'une issue, tels que
#: `construire_maquette` les rend : `│ ` de bordure, puis trois blancs et le
#: glyphe, ou cinq blancs pour une issue sans curseur.
GLYPHE_DE_CURSEUR = "▸"
_ISSUE = re.compile(r"^(?P<curseur>   ▸ | {5})(?P<libelle>\S.*)$")

#: `N issues, M écrit|écrivent` -- les deux cardinaux de la ligne d'etat.
_CARDINAUX = re.compile(r"(\d+) issues?, (\d+) écri(?:t|vent)")


# --------------------------------------------------------------------------
# Les trois relevés vivent ICI et les tests de MORSURE les appellent, jamais
# une copie. Le finding `F3` de la revue de la 11.13 dit ce qui arrive sinon :
# un test de morsure qui recopie la comparaison laisse passer la tautologie
# posee dans l'original.
# --------------------------------------------------------------------------

def grille(texte: str) -> list[str]:
    """Les 24 lignes de la grille, sans les annotations qui la suivent."""
    return texte.rstrip("\n").split("\n")[:HAUTEUR_GRILLE]


def _contenu(ligne: str) -> str:
    """Le contenu d'une ligne de grille, bordures et rembourrage retires."""
    return ligne[2:-2].rstrip() if len(ligne) >= 4 else ""


def issues_de(lignes: list[str]) -> list[str]:
    """Les libelles des issues, **dans l'ordre de la grille**.

    Le balayage porte sur TOUTE la grille et non sur une tranche : une issue
    posee ailleurs qu'a la place attendue doit se voir, et un balayage qui
    saute un bord doit rougir. C'est le point 4 de la regle des fabriques,
    applique au balayage plutot qu'a la fabrique.
    """
    trouvees = []
    for ligne in lignes:
        capture = _ISSUE.match(_contenu(ligne))
        if capture:
            trouvees.append(capture.group("libelle"))
    return trouvees


def curseur_de(lignes: list[str]) -> str | None:
    """Le libelle de l'issue qui porte le curseur `▸`, ou `None`."""
    for ligne in lignes:
        capture = _ISSUE.match(_contenu(ligne))
        if capture and GLYPHE_DE_CURSEUR in capture.group("curseur"):
            return capture.group("libelle")
    return None


def cardinaux_de_l_etat(lignes: list[str]) -> tuple[int, int] | None:
    """`(issues, celles qui ecrivent)` lus dans la ligne d'etat, ou `None`."""
    for ligne in lignes:
        capture = _CARDINAUX.search(_contenu(ligne))
        if capture:
            return int(capture.group(1)), int(capture.group(2))
    return None


@pytest.fixture(scope="module")
def maquette() -> list[str]:
    return grille(MAQUETTE.read_text(encoding="utf-8"))


# ------------------------------------------------------------ la maquette --

def test_la_grille_tient_encore_24_lignes_de_80_COLONNES(maquette):
    """Une sortie de plus ne se paie pas en debordant de la grille plancher.

    Mesure en COLONNES de terminal et non en caracteres : les glyphes de
    cadre et `·` sont etroits ici, mais un glyphe large ajoute demain
    passerait un controle par `len()`.
    """
    import unicodedata

    assert len(maquette) == HAUTEUR_GRILLE, len(maquette)
    for rang, ligne in enumerate(maquette, start=1):
        largeur = sum(2 if unicodedata.east_asian_width(c) in ("W", "F")
                      else 1 for c in ligne)
        assert largeur == LARGEUR_GRILLE, (rang, largeur, ligne)


def test_les_TROIS_sorties_sont_CELLES_d_ARB_231_et_DANS_CET_ORDRE(maquette):
    """`EPIC11-ARB-231`, verbatim : « L'ordre porte la recommandation. »

    En egalite EXACTE sur la liste ordonnee, jamais en appartenance : une
    quatrieme sortie glissee demain, ou deux lignes permutees, passeraient
    toute assertion prise sortie par sortie.
    """
    assert issues_de(maquette) == list(LES_TROIS_SORTIES), issues_de(maquette)


def test_la_sortie_NEUVE_n_est_ni_en_TETE_ni_en_QUEUE(maquette):
    """Le rang de la sortie neuve EST la recommandation.

    En tete, l'ecran conseillerait de declarer un second rush la ou le cas
    ordinaire est un relink ; en queue, elle passerait pour une variante
    d'`Annuler`. Mesurer sa presence sans mesurer son rang laisserait les
    deux derives passer.
    """
    trouvees = issues_de(maquette)
    assert trouvees.index(SORTIE_NEUVE) == RANG_DE_LA_SORTIE_NEUVE, trouvees
    assert 0 < RANG_DE_LA_SORTIE_NEUVE < len(LES_TROIS_SORTIES) - 1


def test_le_RELINK_ouvre_la_liste_et_ANNULER_la_ferme(maquette):
    """Les deux BORDS de la liste, nommes plutot que deduits du rang milieu.

    `EPIC11-ARB-89` : la sortie recommandee vient d'abord, et un ecran ne se
    ferme jamais sur une issue qui ecrit.
    """
    trouvees = issues_de(maquette)
    assert trouvees[0].startswith("Relinker "), trouvees
    assert trouvees[-1] == "Annuler", trouvees


def test_le_curseur_reste_sur_la_SEULE_sortie_qui_N_ECRIT_PAS(maquette):
    """`EPIC11-ARB-7` sous la forme reduite d'`EPIC11-ARB-45`.

    La sortie neuve ECRIT -- elle cree une seconde entree `rushes[]`. Des
    trois, seule `Annuler` n'ecrit pas : le curseur doit donc y rester, et
    une sortie qui ecrit ne doit pas etre atteignable en une frappe depuis le
    montage de l'ecran.
    """
    assert curseur_de(maquette) == "Annuler", curseur_de(maquette)
    assert sum(1 for l in maquette
               if GLYPHE_DE_CURSEUR in _contenu(l)) == 1


def test_la_ligne_d_etat_COMPTE_les_sorties_reellement_dessinees(maquette):
    """`EPIC11-ARB-56` / DESIGN.md section 3 : la ligne d'etat porte une MESURE.

    Le lien est mesure plutot que relu : le cardinal annonce est confronte au
    cardinal DESSINE. C'est ce qui empeche la panne exacte qu'`ARB-231` vient
    de produire -- l'ecran gagne une sortie, la ligne d'etat continue d'en
    annoncer deux, et personne ne rougit. Un cardinal perime est pire
    qu'absent : il se lit comme une verification.
    """
    releve = cardinaux_de_l_etat(maquette)
    assert releve is not None, "la ligne d'etat n'annonce aucun cardinal"
    annoncees, ecrivantes = releve
    assert annoncees == len(issues_de(maquette)) == 3, releve
    # Seule `Annuler` n'ecrit pas ; les deux autres engagent une ecriture.
    assert ecrivantes == annoncees - 1 == 2, releve


def test_l_ACCORD_du_verbe_suit_le_cardinal(maquette):
    """`2 écrivent`, pas `2 écrit` -- et l'inverse au singulier.

    Une frontiere sur les seuls chiffres laisserait passer `3 issues, 2
    écrit`, qui se lit comme une faute de frappe et qu'une relecture ne
    rattrape pas plus qu'elle n'a rattrape le `2 issues` perime.
    """
    etat = next(_contenu(l) for l in maquette if _CARDINAUX.search(_contenu(l)))
    _, ecrivantes = cardinaux_de_l_etat(maquette)
    attendu = "écrivent" if ecrivantes > 1 else "écrit"
    assert f"{ecrivantes} {attendu}" in etat, etat


def test_le_balayage_NE_PREND_PAS_le_cartouche_pour_des_issues(maquette):
    """Volet negatif : un balayage trop large rendrait ce banc bavard.

    Les lignes du cartouche, le bandeau, la ligne d'etat et celle des
    raccourcis ne sont pas des issues. Sans ce volet, elargir `_ISSUE` pour
    « reparer » un rouge ferait entrer douze lignes de donnees dans la liste
    ordonnee -- et le message d'erreur deviendrait illisible avant d'etre
    faux.
    """
    trouvees = issues_de(maquette)
    assert len(trouvees) == 3, trouvees
    for indesirable in ("Nom du fichier", "Déclaré depuis", "rush-deja-declare",
                        "Timecode initial", "mmu · projet_demo", "F1 aide"):
        assert not any(indesirable in libelle for libelle in trouvees), (
            f"{indesirable!r} est passe pour une issue : {trouvees}")


# ------------------------------------------------------------- la morsure --
#
# Deux collections imbriquees sont en jeu, et la regle des fabriques vaut pour
# les DEUX : les 24 LIGNES que le balayage parcourt, et les TROIS SORTIES
# qu'il en rend. Les poses ci-dessous couvrent les deux bords de chacune.

#: Les trois rangs OU l'on pose l'issue, dans la grille. La tete et la queue
#: sont le point : une issue posee au MILIEU ne demasque pas un balayage
#: tronque, qui est un autre mode de panne que l'appariement fautif (point 4
#: de la regle des fabriques, pose le 2026-09-03).
RANGS_DE_POSE = {"premiere_ligne": 0, "ligne_mediane": 12, "derniere_ligne": -1}


def _grille_d_une_seule_issue(maquette: list[str], rang: int) -> list[str]:
    """La grille reelle, videe de ses issues, avec UNE issue posee au `rang`.

    La ligne posee est **prelevee sur la maquette reelle** plutot que
    recomposee : un banc qui refabriquerait la forme d'une issue mesurerait sa
    propre copie de `construire_maquette`, pas le producteur.
    """
    lignes = list(maquette)
    modele = next(l for l in lignes if _ISSUE.match(_contenu(l)))
    vide = "│" + " " * (LARGEUR_GRILLE - 2) + "│"
    lignes = [vide if _ISSUE.match(_contenu(l)) else l for l in lignes]
    lignes[rang] = modele
    return lignes


@pytest.mark.parametrize("pose", sorted(RANGS_DE_POSE))
def test_le_balayage_TROUVE_une_issue_a_CHAQUE_BORD_de_la_grille(maquette, pose):
    """Le mutant vise : un balayage tronque (`lignes[1:]`, `lignes[:-1]`).

    Sur la maquette reelle les trois issues sont au milieu de la grille --
    rangs 18 a 20 sur 24. Une troncature d'un bord y resterait donc VERTE, et
    c'est exactement le mutant que la 11.11 a vu survivre. On pose donc la
    cible en premiere ligne, au milieu, puis en derniere.
    """
    rang = RANGS_DE_POSE[pose]
    lignes = _grille_d_une_seule_issue(maquette, rang)
    # **La pose se VERIFIE avant de se mesurer**, et ce n'est pas une
    # precaution de style : le mutant `M19` de la campagne de ce lot remplacait
    # `lignes[rang]` par `lignes[12]` dans la fabrique, si bien que les TROIS
    # poses retombaient au milieu de la grille. Les trois tests restaient
    # verts, la couverture des bords etait perdue en silence -- et `M12` /
    # `M13`, les deux balayages tronques, ressuscitaient derriere. La garde
    # d'inventaire ci-dessous tient les RANGS annonces ; celle-ci tient que la
    # fabrique les a reellement employes.
    assert _ISSUE.match(_contenu(lignes[rang])), (
        f"la pose {pose} n'a pas atterri au rang {rang} : la fabrique ignore "
        f"le rang qu'on lui donne, et les trois poses mesurent le meme point")
    assert len(issues_de(lignes)) == 1, (
        f"issue posee en {pose} et non vue par le balayage : "
        f"{issues_de(lignes)}")


def test_les_RANGS_DE_POSE_couvrent_les_DEUX_bords_de_la_grille():
    """La garde de l'inventaire, pour le meme motif que sur les poses.

    Un inventaire de poses se garde par son CONTENU : retirer une entree d'un
    `parametrize` joue une pose de moins sans faire rougir personne.
    """
    rangs = set(RANGS_DE_POSE.values())
    assert 0 in rangs, "aucune pose en PREMIERE ligne de grille"
    assert -1 in rangs, "aucune pose en DERNIERE ligne de grille"
    assert rangs - {0, -1}, "aucune pose au MILIEU de la grille"


@pytest.mark.parametrize("rang", range(len(LES_TROIS_SORTIES)))
def test_la_comparaison_MORD_sur_une_sortie_RETIREE_a_chaque_rang(rang):
    """Chacune des trois retiree, tete et queue comprises.

    Le mutant vise ici est un balayage qui rendrait une sortie de moins --
    par troncature, ou parce qu'une ligne aurait cesse d'etre reconnue.
    """
    ampute = [s for i, s in enumerate(LES_TROIS_SORTIES) if i != rang]
    assert ampute != list(LES_TROIS_SORTIES)
    assert len(ampute) == len(LES_TROIS_SORTIES) - 1


@pytest.mark.parametrize("a,b", [(0, 1), (1, 2), (0, 2)])
def test_la_comparaison_MORD_sur_une_PERMUTATION_des_trois(a, b):
    """L'ordre porte la recommandation : une transposition doit rougir.

    Les trois transpositions sont jouees, donc chacune des trois sorties est
    deplacee au moins une fois -- y compris celle de tete et celle de queue.
    Une egalite d'ENSEMBLE passerait les trois sans rien dire.
    """
    permute = list(LES_TROIS_SORTIES)
    permute[a], permute[b] = permute[b], permute[a]
    assert permute != list(LES_TROIS_SORTIES), (
        "cette transposition ne permute rien : les deux sorties sont egales")
    assert sorted(permute) == sorted(LES_TROIS_SORTIES), (
        "la pose doit permuter, pas alterer -- sans quoi elle mesurerait "
        "l'appartenance et non l'ordre")


def test_les_TROIS_sorties_sont_DISTINGUABLES_entre_elles():
    """Point 1 de la regle des fabriques, sur la collection mesuree.

    Trois libelles identiques rendraient toute permutation invisible, et les
    deux bancs de morsure ci-dessus passeraient sans rien mesurer.
    """
    assert len(set(LES_TROIS_SORTIES)) == len(LES_TROIS_SORTIES)


def test_la_ligne_d_etat_MORD_sur_un_cardinal_PERIME():
    """Le defaut exact de ce lot, rejoue : deux sorties annoncees pour trois.

    C'est la ligne que `ARB-231` a rendue fausse. Sans cette morsure, la
    frontiere du cardinal pourrait etre satisfaite par un releve qui ne
    releve rien.
    """
    perimee = ["│ ✕  rush-deja-declare · 2 issues, 1 écrit · inchangé"
               + " " * 26 + "│"]
    assert cardinaux_de_l_etat(perimee) == (2, 1)
    assert cardinaux_de_l_etat(perimee) != (3, 2)
    assert cardinaux_de_l_etat(["│" + " " * 78 + "│"]) is None, (
        "un releve qui rend un cardinal sur une ligne vide mesurerait le vide")


def test_le_curseur_MORD_quand_il_se_pose_sur_une_sortie_QUI_ECRIT():
    """Volet negatif du curseur, sur une grille fabriquee.

    Sans lui, `curseur_de` pourrait rendre le premier libelle venu et le banc
    du curseur resterait vert sur un ecran ou `Relinker` serait presélectionne
    -- c'est-a-dire une ecriture atteignable en une frappe.
    """
    fautive = ["│    ▸ Relinker vers ailleurs" + " " * 50 + "│",
               "│      Annuler" + " " * 65 + "│"]
    assert curseur_de(fautive) == "Relinker vers ailleurs"
    assert curseur_de(fautive) != "Annuler"


# ------------------------------------------------------- le rendu de la TUI --
#
# **Le volet que la promesse de ce fichier annoncait**, et il ferme l'ecart :
# le dessin porte trois sorties depuis `EPIC11-ARB-231`, la TUI en portait deux
# et un test restait vert en le disant. Ce qui suit confronte les LIBELLES et
# leur ORDRE, cote a cote, sur les deux producteurs.

import sys  # noqa: E402

_SRC = str(RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.tui import ajout_de_rush  # noqa: E402

#: L'entree du producteur TUI : le fichier designe et le dossier ou il vit.
#:
#: **Ils sont ECRITS ici et non relus de la maquette, et il faut le dire** :
#: le dessin ne porte que la forme ABREGEE du chemin
#: (`D:\…\04_tournage_juin\hd\`), qui est une SORTIE de `plier_le_chemin`
#: et non son entree. Les relire pour les redonner au meme replieur ferait
#: mesurer un aller-retour sur une valeur deja repliee, c'est-a-dire rien.
#: Le nom du fichier, lui, est verifie contre le dessin par
#: :func:`test_le_libelle_de_relink_dit_les_MEMES_choses_que_le_dessin`.
NOM_DESSINE = "plan séquence 12.mov"
CHEMIN_DESIGNE = ("D:\\HOKO\\Documents\\rushes\\2026\\04_tournage_juin\\hd\\")

#: La largeur utile d'une zone de la grille plancher : 80 colonnes moins les
#: deux bordures et les deux colonnes de respiration.
LARGEUR_UTILE = LARGEUR_GRILLE - 4


def suites_de_la_tui(largeur: int = LARGEUR_UTILE) -> list[str]:
    """Les libelles que la TUI rend, dans l'ordre ou elle les rend."""
    choix = ajout_de_rush.suites_du_rush_deja_declare(
        NOM_DESSINE, CHEMIN_DESIGNE, largeur)
    return [issue.libelle for issue in choix.issues]


def test_la_TUI_rend_AUTANT_de_sorties_que_la_maquette_en_dessine(maquette):
    """Le cardinal, confronte producteur contre producteur.

    C'est le premier des deux volets, et il ne suffit pas seul : trois libelles
    permutes passeraient. Il est separe parce qu'un cardinal faux et un ordre
    faux ne se reparent pas au meme endroit -- l'un est une sortie oubliee au
    modele, l'autre est la recommandation deplacee.
    """
    assert len(suites_de_la_tui()) == len(issues_de(maquette)) == 3


def test_la_TUI_porte_les_MEMES_libelles_dans_le_MEME_ordre(maquette):
    """Les deux sorties dont le texte est FIXE, en egalite exacte et par rang.

    **La sortie de relink est traitee a part et ce n'est pas une exception de
    confort** : son libelle porte un CHEMIN, donc il depend de la largeur --
    voir :func:`test_le_libelle_de_relink_dit_les_MEMES_choses_que_le_dessin`
    pour ce qui s'y mesure et pourquoi le verbatim n'y a pas de sens.

    Le rang est mesure et non l'appartenance : c'est la seule facon d'attraper
    une permutation, et une permutation deplace la recommandation.
    """
    dessinees = issues_de(maquette)
    rendues = suites_de_la_tui()
    for rang in (1, 2):
        assert rendues[rang] == dessinees[rang], (
            f"rang {rang} : la TUI rend {rendues[rang]!r}, la maquette "
            f"dessine {dessinees[rang]!r}")
    assert rendues[0].startswith("Relinker "), rendues


def test_le_libelle_de_relink_dit_les_MEMES_choses_que_le_dessin(maquette):
    """Ce que les deux producteurs doivent dire, malgre un budget different.

    **La divergence est de GEOMETRIE et elle est anterieure a ce lot** : la
    maquette dessine ce libelle a un budget plus etroit que la zone utile du
    produit, si bien qu'elle garde un seul segment de tete
    (`D:\\…\\04_tournage_juin\\hd\\`) la ou la TUI, qui a la place, en garde
    trois (`D:\\HOKO\\Documents\\…\\04_tournage_juin\\hd\\`). Les deux sont
    licites au regard de la note 6 d'Egan (« les **3 premiers** dossiers [...]
    et les deux derniers **au moins** ») ; ce qui ne le serait pas, c'est de
    perdre le nom du fichier ou les deux derniers dossiers, qui sont la seule
    raison d'etre de la note 4.

    Un verbatim ici mesurerait donc la largeur du dessin, pas le produit -- et
    il rougirait au premier redimensionnement de fenetre, qui est le regime
    normal d'une TUI.
    """
    dessine = issues_de(maquette)[0]
    rendu = suites_de_la_tui()[0]
    for morceau in (NOM_DESSINE, "04_tournage_juin", "hd\\"):
        assert morceau in dessine, (morceau, dessine)
        assert morceau in rendu, (morceau, rendu)
    assert "plan-sequence-12" not in rendu, (
        "l'identifiant derive n'a rien a faire sur cet ecran (ARB-153)")


@pytest.mark.parametrize("largeur", (40, 55, 76, 120))
def test_la_TUI_garde_ses_TROIS_sorties_a_TOUTE_largeur(largeur):
    """Le cardinal ne depend pas de la place, seul le libelle du relink en
    depend.

    Sans ce volet, une largeur etroite pourrait faire disparaitre une sortie --
    par un repliement qui rend une liste vide, par exemple -- et l'ecran
    perdrait une issue en silence a la seule fenetre ou l'operateur travaille.
    """
    rendues = suites_de_la_tui(largeur)
    assert len(rendues) == 3, rendues
    assert all(libelle.strip() for libelle in rendues), rendues


def test_la_TUI_ne_pose_le_curseur_que_sur_la_sortie_qui_N_ECRIT_PAS(maquette):
    """Le meme invariant des deux cotes, et c'est ce qui le rend mesurable.

    La maquette dessine `▸` sur `Annuler` ; le modele de la TUI y pose son
    curseur **de lui-meme** (`ChoixExclusif.__post_init__`). Confronter les
    deux attrape le cas ou l'un des deux bougerait seul -- une sortie neuve
    posee en queue, par exemple, deplacerait le curseur du dessin sans que le
    modele le sache.
    """
    choix = ajout_de_rush.suites_du_rush_deja_declare(
        NOM_DESSINE, CHEMIN_DESIGNE, LARGEUR_UTILE)
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.issues[choix.curseur].libelle == curseur_de(maquette)
    assert sum(1 for issue in choix.issues if issue.ecrit) == 2, (
        "la ligne d'etat de la maquette annonce « 2 écrivent » : si ce "
        "cardinal change ici, elle devient perimee")
