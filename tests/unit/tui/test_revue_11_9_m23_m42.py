# -*- coding: utf-8 -*-
"""Story 11.9 -- les DEUX constantes de dessin que rien ne mesurait (`M23`, `M42`).

Ce fichier ferme les deux derniers findings de **classe critique** de la 11.9 :

* **`M23` -- :data:`ecran_manuel.MARGE_DROITE`.** Documentee « relevee sur la
  maquette au caractere pres », elle ne l'etait par aucun banc : `+1` comme
  `-1` survivaient a l'integralite de `tests/unit/tui`.
* **`M42` -- :data:`ecran_manuel.SEPARATEUR_DES_LIBELLES`.** Meme diagnostic,
  avec une aggravation : le banc de la couche 3 croyait la tuer alors qu'il
  **s'en servait comme sonde de recherche** dans le texte de la maquette
  (`SEPARATEUR_DES_LIBELLES in contenu[rang]`). Ramener la constante a un
  espace simple rend cette recherche **plus facile**, donc le banc restait
  vert. Un banc qui emploie la constante pour trouver ce qu'il verifie ne
  verifie rien -- c'est la trace que ce fichier garde, et la raison pour
  laquelle plus une seule assertion ci-dessous ne lit `em.SEPARATEUR_DES_LIBELLES`.

**Pourquoi la confrontation existante ne pouvait structurellement pas les
voir.** `test_ecran_manuel.RANGS_DIVERGENTS_DE_T1_2` liste **quinze rangs
divergents sur vingt**, dont **toutes** les lignes d'entree : elle mesure donc
*quels* rangs different, jamais *comment*. Tout deplacement interne bouge du
texte dans une ligne deja declaree divergente, et rien ne rougit.

**Ce que ce banc fait a la place, et c'est le point.** Les quinze rangs
divergent parce que la maquette ecrit une **prose d'UX** que le produit ne
derive pas -- pas parce que le DESSIN differe. Reconstruite a partir des
libelles que la maquette porte elle-meme, chaque ligne d'entree de `T1-2` est
rendue par le produit **caractere pour caractere**. La confrontation redevient
donc exacte, et tout deplacement d'une colonne ou toute alteration du
separateur la fait rougir.

**Le releve de la marge droite ne vient PAS de `T1-2`, et il faut le dire.**
Aucune ligne de `T1-2` n'atteint le bord droit : la maquette du manuel ne pose
donc aucune borne de repli. La marge se releve la ou la docstring de la
constante l'envoie -- « comme dans les blocs de l'Extraction » --, sur
`E2-1b-relink-chercher-dossier` et `E2-1c-relink-designer-fichier`, dont les
listes portent une colonne **calee a droite** qui s'arrete exactement a la
colonne 74 de la zone utile (76). C'est un releve externe, en dur ci-dessous,
jamais un calcul refait a partir de la constante mesuree.

**Effet collateral MESURE, dit parce qu'il n'etait pas cherche.** La
confrontation caractere pour caractere tue aussi, incidemment, les quatre
mutants des trois colonnes du dessin -- dont `COLONNE_DU_LIBELLE 18 -> 19`,
le **contre-mutant que la couche 1 avait laisse survivant** : elle n'avait tue
que `18 -> 17`, et par la mauvaise frontiere (17 vaut
`jetons.HAUTEUR_CENTRE_AU_PLANCHER`, donc c'est la frontiere « pas de recopie
de constante de grille » qui rougissait, pas une mesure du dessin). Les quatre
morts sont ici mesurees, pas supposees :

===========================  =============================================
mutant                       ce qui rougit
===========================  =============================================
`COLONNE_DU_LIBELLE  -> 19`  11 tests, dont les neuf rangs de `T1-2`
`COLONNE_DU_LIBELLE  -> 17`  12 tests, dont les neuf rangs de `T1-2`
`COLONNE_DE_L_OUVREUR -> 6`  10 tests, dont les neuf rangs de `T1-2`
`COLONNE_DE_L_ATELIER -> 48`  2 tests, les deux rangs « propres » (16, 18)
===========================  =============================================

Ce n'est **pas** la fermeture du finding des colonnes -- il a son banc, son
histoire et sa triage --, c'est une mesure a verser a son dossier.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mixed_media_utility.tui import ecran_manuel as em
from mixed_media_utility.tui import jetons, manuel

MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")


def contenu_de_maquette(nom: str) -> list[str]:
    """Les lignes d'une maquette, cadre ET marge retires, comme le dessin.

    `ligne[2:-2]` retire la bordure (1 colonne) et la marge (1 colonne) de
    chaque cote : ce qui reste est la zone utile de 76 colonnes sur laquelle
    `jetons.largeur_utile(80)` s'accorde. C'est le meme decoupage que celui de
    `test_revue_11_9_couche_3.lignes_de_contenu_de_T1_2`, et il n'est pas
    negociable : c'est lui qui fait que la colonne 18 du code est la colonne 19
    du fichier.
    """
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")
    return [ligne[2:-2].rstrip() if ligne.startswith("│") else ""
            for ligne in lignes]


# ===========================================================================
# `M42` -- le SEPARATEUR, confronte CARACTERE POUR CARACTERE a `T1-2`
# ===========================================================================

#: Ce que `T1-2` ecrit entre deux roles d'un meme ouvreur, **releve en dur**.
#: Espace, point median `U+00B7`, espace. Il n'est PAS lu de la constante
#: mesuree : c'est exactement l'erreur que la couche 3 a commise.
SEPARATEUR_RELEVE_SUR_T1_2 = " · "

def rang_de_l_OUVREUR(ouvreur: str) -> int | None:
    """Le rang de `T1-2` qui ouvre `ouvreur`, **cherche**, ou `None`.

    **Aucun rang de maquette n'est plus ecrit en litteral ici**, et la lecon
    est mesuree : le 2026-09-05, `EPIC11-ARB-141` a retire la ligne
    `e   éditer les noms produits` a la source de la maquette ; `r` a glisse
    d'un rang et le cas `rang18` de ce banc a rougi -- pour une raison
    etrangere a ce qu'il mesure, qui est le SEPARATEUR et les COLONNES.
    """
    contenu = contenu_de_maquette("T1-2-manuel-raccourcis.txt")
    rangs = [rang for rang, ligne in enumerate(contenu)
             if ligne.startswith(" " * em.COLONNE_DE_L_OUVREUR)
             and ligne.strip().split("  ")[0].strip() == ouvreur]
    return rangs[0] if len(rangs) == 1 else None


#: Les lignes d'ENTREE de `T1-2`, relevees a la main : ouvreur, libelles dans
#: l'ordre, modules porteurs. Le decoupage en libelles est un **releve**, pas
#: un `split` sur le separateur -- un `split` referait du separateur une sonde.
#: **Le rang, lui, n'est plus releve : il se cherche** (voir ci-dessus).
#:
#: La ligne `e  éditer les noms produits  (avant écriture)` n'y a jamais figure :
#: sa parenthese portait une prose d'UX et non un nom d'atelier, donc le
#: produit ne pouvait pas la deriver. C'etait l'un des ecarts bornes par
#: l'AC 4.2 ; `EPIC11-ARB-141` l'a depuis retiree de la maquette.
ENTREES_RELEVEES_SUR_T1_2 = (
    ("↑ ↓", ("déplacer le curseur dans une liste",), (), True),
    ("Entrée", ("valider la ligne ou le formulaire courant",), (), True),
    ("Espace", ("cocher / décocher (listes à cases)",), (), True),
    # La SEULE ligne de `T1-2` qui porte le separateur, et elle en porte deux.
    ("Tab", ("champ suivant", "compléter un chemin", "voir le journal"),
     (), True),
    ("Échap", ("remonter d'un palier, sans rien écrire",), (), True),
    ("F1", ("aide du champ courant, ou ce manuel",), (), True),
    ("q", ("quitter (demande confirmation si une tâche tourne)",), (), True),
    ("a", ("ajouter une cadence",),
     ("mixed_media_utility.tui.atelier_extraction",), False),
    ("r", ("retrouver un rush absent",),
     ("mixed_media_utility.tui.atelier_extraction",), False),
)


def test_le_RELEVE_des_entrees_de_T1_2_designe_encore_des_lignes_REELLES():
    """L'anti-vacuite du releve, et il remplace la borne que les rangs
    donnaient.

    Un releve dont plus aucune entree ne se retrouve dans la maquette rendrait
    la confrontation ci-dessous **vide** sans qu'un seul test rougisse -- c'est
    le mode de panne exact d'une parametrisation calculee. On exige donc qu'au
    moins sept des neuf entrees relevees soient encore ouvertes par `T1-2`.
    """
    trouvees = [cas[0] for cas in ENTREES_RELEVEES_SUR_T1_2
                if rang_de_l_OUVREUR(cas[0]) is not None]
    assert len(trouvees) >= 7, sorted(trouvees)


def test_le_separateur_est_bien_CELUI_que_T1_2_ecrit_entre_deux_roles():
    """Le releve d'abord : sans lui, la confrontation ne mesurerait plus rien.

    On verifie que `T1-2` porte toujours la chaine relevee en dur, **et** qu'un
    espace simple ne suffit pas a la decrire : le rang 9 doit contenir
    ` · ` et pas seulement des blancs entre ses roles. Le jour ou la maquette
    change de separateur, c'est ici que ca rougit -- pas silencieusement.
    """
    rang = rang_de_l_OUVREUR("Tab")
    assert rang is not None, "`T1-2` n'ouvre plus `Tab` : le releve est vide"
    ligne = contenu_de_maquette("T1-2-manuel-raccourcis.txt")[rang]
    assert SEPARATEUR_RELEVE_SUR_T1_2 in ligne, repr(ligne)
    assert ligne.count(SEPARATEUR_RELEVE_SUR_T1_2) == 2, repr(ligne)


@pytest.mark.parametrize(
    "ouvreur,libelles,ateliers,partout",
    [pytest.param(*cas, id=cas[0].replace(" ", ""))
     for cas in ENTREES_RELEVEES_SUR_T1_2])
def test_la_ligne_d_entree_de_T1_2_est_rendue_CARACTERE_POUR_CARACTERE(
        ouvreur, libelles, ateliers, partout):
    """AC 4.1, la moitie que le jeu des rangs divergents ne pouvait pas voir.

    Reconstruite a partir des libelles que la maquette porte, la ligne rendue
    doit etre **egale** a la ligne de la maquette, caractere pour caractere.
    Rougit sur `MARGE_DROITE` seulement si la ligne se replie ; rougit sur
    `SEPARATEUR_DES_LIBELLES`, `COLONNE_DE_L_OUVREUR`, `COLONNE_DU_LIBELLE` et
    `COLONNE_DE_L_ATELIER` dans **les deux sens**.
    """
    rang = rang_de_l_OUVREUR(ouvreur)
    if rang is None:
        # `T1-2` n'ouvre plus cet ouvreur : l'ecart est ferme A LA SOURCE par
        # un arbitrage d'Egan, et exiger la ligne ferait rougir la CORRECTION.
        # L'anti-vacuite du releve est portee par le test ci-dessus, qui
        # rougirait si trop d'entrees disparaissaient d'un coup.
        return
    attendu = contenu_de_maquette("T1-2-manuel-raccourcis.txt")[rang]
    assert attendu, ("la maquette ne porte plus rien a ce rang : "
                     "le releve ne mesure rien")
    entree = manuel.Entree(ouvreur=ouvreur, libelles=libelles, ecrans=(),
                           ateliers=ateliers, partout=partout)
    rendu = em.lignes_d_une_entree(entree, jetons.LARGEUR_PLANCHER, False)
    assert rendu == [attendu], (rendu, [attendu])


def test_le_separateur_tient_a_CHAQUE_JOINTURE_pas_seulement_a_la_premiere():
    """Quatre roles, donc trois jointures : une en tete, une au milieu, une en queue.

    `T1-2` n'ecrit que deux jointures sur une seule ligne ; `Échap` en porte
    quatorze dans le produit reel. Un balayage tronque -- qui joindrait les
    trois premiers roles et laisserait le dernier -- passe la confrontation du
    rang 9 et meurt ici. Les quatre roles sont **distinguables** et de
    longueurs differentes : un appariement permute se verrait.
    """
    roles = ("premier", "deuxieme", "troisieme role", "fin")
    attendu = "     Z            premier · deuxieme · troisieme role · fin"
    # `attendu` est ecrit en dur avec le separateur RELEVE, pas avec la
    # constante mesuree -- on ne fabrique jamais l'attendu avec la valeur
    # qu'on verifie.
    assert attendu.count(SEPARATEUR_RELEVE_SUR_T1_2) == 3, attendu
    entree = manuel.Entree(ouvreur="Z", libelles=roles, ecrans=(),
                           ateliers=(), partout=True)
    rendu = em.lignes_d_une_entree(entree, jetons.LARGEUR_PLANCHER, False)
    assert rendu == [attendu], (rendu, [attendu])


def test_le_separateur_tient_AUSSI_entre_les_ateliers_d_un_raccourci_propre():
    """`ateliers_d_une_entree` emploie la meme constante, sur un autre chemin.

    Trois ateliers, donc deux jointures, l'une en tete et l'autre en queue de
    la parenthese. `T1-2` n'annote qu'un atelier par raccourci : ce chemin-la
    n'a **aucune** ligne de maquette qui le mesure, et c'est pourquoi il a son
    banc.
    """
    entree = manuel.Entree(
        ouvreur="w", libelles=("un role",), ecrans=(),
        ateliers=("mixed_media_utility.tui.atelier_extraction",
                  "mixed_media_utility.tui.atelier_pdf_lots",
                  "mixed_media_utility.tui.scan"),
        partout=False)
    assert em.ateliers_d_une_entree(entree) == "(Extraction · Pdf · Scan)"


# ===========================================================================
# `M23` -- la MARGE DROITE, relevee sur les blocs de l'Extraction
# ===========================================================================

#: La colonne, dans la zone utile de 76, ou s'arrete le texte d'un bloc dont
#: la colonne de droite est calee a droite. **Relevee** sur
#: `E2-1b-relink-chercher-dossier` et `E2-1c-relink-designer-fichier`, que la
#: docstring de `MARGE_DROITE` designe (« comme dans les blocs de
#: l'Extraction »). 76 - 74 = 2 : c'est la marge, et elle n'est ecrite nulle
#: part ailleurs dans ce fichier.
BORD_DROIT_RELEVE_SUR_L_EXTRACTION = 74

#: Ou commence le libelle, releve sur `T1-2` (colonne 19 du fichier, 18 de la
#: zone utile). Il est releve ici pour que la place de repli se DEDUISE de deux
#: mesures de maquette, et d'aucune constante du produit.
COLONNE_DU_LIBELLE_RELEVEE_SUR_T1_2 = 18

#: La largeur exacte qu'un libelle peut occuper avant de se replier.
PLACE_ATTENDUE = (BORD_DROIT_RELEVE_SUR_L_EXTRACTION
                  - COLONNE_DU_LIBELLE_RELEVEE_SUR_T1_2)


def test_les_deux_maquettes_de_l_Extraction_calent_bien_a_la_colonne_relevee():
    """Le releve d'abord, sur les deux maquettes et sur plusieurs rangs.

    Sans ce banc, `BORD_DROIT_RELEVE_SUR_L_EXTRACTION` serait un nombre pose
    dans un test -- exactement ce que `CLAUDE.md` appelle une constante
    recopiee. Ici il est **relu** a chaque course.
    """
    releves = set()
    for nom, rangs in (("E2-1b-relink-chercher-dossier.txt",
                        (9, 10, 11, 12, 13, 14, 15, 16)),
                       ("E2-1c-relink-designer-fichier.txt",
                        (9, 10, 11, 12, 13, 14))):
        contenu = contenu_de_maquette(nom)
        for rang in rangs:
            assert contenu[rang].strip(), (nom, rang, "rang vide : "
                                                      "le releve ne mesure rien")
            releves.add(len(contenu[rang]))
    assert releves == {BORD_DROIT_RELEVE_SUR_L_EXTRACTION}, sorted(releves)


def _libelle_de(colonnes: int, marque: str) -> str:
    """Un libelle de largeur EXACTE, reconnaissable a sa `marque`.

    La queue est un mot d'un seul tenant : replie d'une colonne de moins, il
    passe **entier** a la ligne suivante, ce qui rend la coupure franche et
    lisible dans le message d'echec.
    """
    tete = f"{marque} bord droit "
    return tete + "z" * (colonnes - jetons.colonnes(tete))


def _corpus(colonnes: int) -> tuple[manuel.Entree, ...]:
    """Cinq entrees distinguables, les cibles en TETE, au MILIEU et en QUEUE.

    Les deux entrees de remplissage sont courtes et de longueurs differentes :
    un appariement permute ou un balayage tronque ne peut pas se cacher
    derriere un remplissage uniforme (`CLAUDE.md`, regle des fabriques).
    """
    def entree(ouvreur: str, texte: str) -> manuel.Entree:
        return manuel.Entree(ouvreur=ouvreur, libelles=(texte,), ecrans=(),
                             ateliers=(), partout=True)
    return (
        entree("A", _libelle_de(colonnes, "cible tete")),
        entree("B", "court"),
        entree("C", _libelle_de(colonnes, "cible milieu")),
        entree("D", "un peu moins court"),
        entree("E", _libelle_de(colonnes, "cible queue")),
    )


#: Les ouvreurs des trois entrees calibrees, aux trois positions.
OUVREURS_CIBLES = ("A", "C", "E")


def test_un_libelle_JUSTE_a_la_place_relevee_tient_sur_une_seule_ligne():
    """Le bord DROIT : `MARGE_DROITE` trop grande replie ce qui devait tenir.

    Chaque cible fait exactement `PLACE_ATTENDUE` colonnes et doit donc
    s'ecrire d'un seul tenant, sa derniere colonne tombant exactement sur
    `BORD_DROIT_RELEVE_SUR_L_EXTRACTION`. Une marge d'une colonne de plus
    replie les trois et fait rougir ici.
    """
    corpus = _corpus(PLACE_ATTENDUE)
    touchent_le_bord = []
    for entree in corpus:
        lignes = em.lignes_d_une_entree(entree, jetons.LARGEUR_PLANCHER, False)
        largeurs = [jetons.colonnes(ligne) for ligne in lignes]
        assert max(largeurs) <= BORD_DROIT_RELEVE_SUR_L_EXTRACTION, (
            entree.ouvreur, lignes, "le texte deborde la marge relevee")
        if entree.ouvreur in OUVREURS_CIBLES:
            assert len(lignes) == 1, (
                entree.ouvreur, lignes,
                "un libelle juste a la place relevee s'est replie : "
                "la marge droite est plus large que celle des maquettes")
        if max(largeurs) == BORD_DROIT_RELEVE_SUR_L_EXTRACTION:
            touchent_le_bord.append(entree.ouvreur)
    assert tuple(touchent_le_bord) == OUVREURS_CIBLES, touchent_le_bord


def test_une_colonne_de_PLUS_que_la_place_relevee_se_replie():
    """Le bord GAUCHE du meme intervalle : `MARGE_DROITE` trop petite laisse passer.

    Sans ce volet, `MARGE_DROITE = 1` survit : un libelle de `PLACE_ATTENDUE`
    colonnes tient aussi bien sur 57 que sur 56, et le banc precedent reste
    vert. C'est le contre-mutant qui a demasque les deux faux « tues » de la
    revue du 2026-09-03 -- une borne ne se mesure que des deux cotes.
    """
    corpus = _corpus(PLACE_ATTENDUE + 1)
    replies = []
    for entree in corpus:
        lignes = em.lignes_d_une_entree(entree, jetons.LARGEUR_PLANCHER, False)
        assert max(jetons.colonnes(ligne) for ligne in lignes) <= (
            BORD_DROIT_RELEVE_SUR_L_EXTRACTION), (entree.ouvreur, lignes)
        if len(lignes) > 1:
            replies.append(entree.ouvreur)
    assert tuple(replies) == OUVREURS_CIBLES, (
        replies, "une colonne de trop n'a pas replie : la marge droite est "
                 "plus etroite que celle des maquettes")
