# -*- coding: utf-8 -*-
"""`E2-1i` est-elle bien la VARIANTE de `E2-1e`, et rien de plus ?

**Ce que cette frontiere ferme.** `EPIC11-ARB-227` (2026-09-05, verbatim
d'Egan sur l'encart du cardinal absent de la v4 de la planche : « On n'affiche
rien si on ne corrobore pas ») demande un QUATRIEME etat de l'ecran de
declaration -- pas un ecran de plus. Une variante a deux modes de panne
opposes, et aucun ne se voit a la relecture :

* elle **derive** -- une correction portee a `E2-1e` (le chemin, le codec, une
  issue, la ligne de raccourcis) ne suit pas sur `E2-1i`, et les deux ecrans
  finissent par montrer deux produits differents. C'est le defaut exact que
  `fiche_de_declaration` evite par construction cote generateur ; ce banc le
  mesure cote PRODUIT, sur le `.txt` livre ;
* elle **ne varie pas assez** -- le cardinal reste quelque part, ou revient
  sous la forme d'un `0`, d'un `--` ou d'un libelle d'absence. C'est ce que
  l'arbitrage interdit, et un test positif ne le verrait pas : il faut une
  frontiere NEGATIVE, la seule qui attrape une reintroduction.

**Ce que ce banc ne mesure PAS, dit plutot que tu.** Aucun ecran livre ne rend
cet etat : `tui/ajout_de_rush.py` calcule ce que `E2-1e` a `E2-1h` affichent,
et la variante du cardinal absent est un DESSIN valide, pas un comportement.
Ce banc mesure donc une maquette contre une maquette. Le lot qui codera
l'ecran devra porter sa propre frontiere, du meme genre mais sur le rendu
reel -- c'est le mode de panne que `test_sobriete_et_grille_extraction`
documente en tete : « une maquette propre au-dessus d'un ecran fautif ».

**Regle des fabriques de `CLAUDE.md`, les quatre points.** La collection ici
est la grille de 24 lignes, et la comparaison qui en tire les rangs
divergents est le seul objet que ce banc a a mesurer. Elle est donc
fabriquee : deux grilles de 24 lignes toutes DISTINGUABLES (point 1), avec la
divergence posee au milieu (point 2), en TETE et en QUEUE (point 4), et
plusieurs divergences a la fois -- une comparaison qui s'arrete a la premiere
est un autre mode de panne qu'aucune cible unique ne demasque.

**La comparaison vit ICI et les deux familles de tests l'APPELLENT.** Le
finding `F3` de la revue de la 11.13 est mot pour mot ce qui arrive sinon :
un test de morsure qui recopie la comparaison au lieu de l'appeler laisse
passer une tautologie posee dans l'original.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

NOMINALE = MAQUETTES / "E2-1e-declaration-confirmation.txt"
VARIANTE = MAQUETTES / "E2-1i-declaration-cardinal-absent.txt"

#: La grille de `DESIGN.md` section 1. Ecrite ici en clair plutot que lue de
#: `jetons` : c'est la GRILLE DU DESSIN qu'on mesure, et un banc qui lirait la
#: hauteur du produit rendrait vert le jour ou le produit changerait de forme
#: sans que les maquettes suivent -- exactement la divergence a attraper.
HAUTEUR_DE_GRILLE = 24
LARGEUR_DE_GRILLE = 80

#: Les DEUX rangs qui ont le droit de differer, comptes depuis 1 comme la
#: grille se lit. Rien d'autre ne varie entre les deux etats.
#:
#: * 11 -- la ligne `Résolution`, ce qu'`EPIC11-ARB-227` tranche nommement ;
#: * 22 -- la ligne d'etat, par deduction de `EPIC11-ARB-56` (elle porte une
#:   MESURE, et un cardinal non corrobore n'en est pas une) et de
#:   `DESIGN.md` section 3 (« elle est vide quand il n'y a rien a dire »).
RANGS_QUI_VARIENT = (11, 22)


def lignes_de_grille(chemin: Path) -> list[str]:
    """Les 24 lignes de la grille, sans les annotations manuscrites d'Egan."""
    return chemin.read_text(encoding="utf-8").rstrip("\n").split(
        "\n")[:HAUTEUR_DE_GRILLE]


def largeur_affichee(ligne: str) -> int:
    """La largeur en COLONNES, pas en points de code.

    `×`, `·`, `▸`, `⏎` et les filets sont tous d'une colonne ; les mesurer par
    `len()` marcherait ici par accident. On mesure ce qui compte -- une grille
    est un pavage de colonnes de terminal.
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in ligne)


def test_largeur_affichee_compte_des_COLONNES_et_non_des_points_de_code():
    """Mutant `M25` : `return len(ligne)` SURVIVAIT a la campagne.

    Il survivait pour une raison honnete -- aucune ligne des deux maquettes ne
    porte de caractere large, donc `len()` y rend le bon chiffre par accident.
    C'est le mode de panne que `CLAUDE.md` documente sous « une fixture de
    synthese peut fabriquer une panne que le terrain n'a pas », pris a
    l'envers : un corpus qui n'exerce pas un chemin ne le mesure pas. La
    fonction est donc mesuree sur son CONTRAT plutot que sur le corpus, et le
    jour ou un ideogramme entrerait dans une maquette, la grille serait comptee
    juste.
    """
    assert largeur_affichee("abc") == 3
    assert largeur_affichee("| . x > _ |") == 11
    assert largeur_affichee("\u6f22") == 2, "un ideogramme occupe deux colonnes"
    assert largeur_affichee("\u6f22\u5b57abc") == 7


# ===========================================================================
# La comparaison, UNE fois, appelee par les deux familles de tests
# ===========================================================================

def rangs_divergents(gauche: list[str], droite: list[str]) -> list[int]:
    """Les rangs (depuis 1) ou les deux grilles ne portent pas la meme ligne.

    Elle rend TOUS les ecarts, jamais le premier : c'est ce qui distingue une
    comparaison d'un `find`, et c'est le mode de panne que les fabriques
    ci-dessous posent a plusieurs cibles a la fois.

    Une difference de HAUTEUR est un ecart a part entiere : les rangs en trop
    d'un cote sont rendus comme divergents plutot que silencieusement ignores
    par un `zip`, qui tronque au plus court.
    """
    hauteur = max(len(gauche), len(droite))
    return [rang for rang in range(1, hauteur + 1)
            if (gauche[rang - 1] if rang <= len(gauche) else None)
            != (droite[rang - 1] if rang <= len(droite) else None)]


# ===========================================================================
# Les fabriques -- deux grilles de 24 lignes TOUTES DISTINGUABLES
# ===========================================================================

def grille_fabriquee(divergents: tuple[int, ...] = ()) -> tuple[list[str],
                                                                list[str]]:
    """Deux grilles de 24 lignes, identiques sauf aux rangs demandes.

    **Point 1 de la regle des fabriques** : les 24 lignes different toutes les
    unes des autres. Un remplissage uniforme rendrait invisible une
    comparaison qui melangerait les rangs -- une permutation ne se voit que si
    les elements diffèrent.
    """
    gauche = [f"ligne {rang:02d} de la grille temoin"
              for rang in range(1, HAUTEUR_DE_GRILLE + 1)]
    droite = list(gauche)
    for rang in divergents:
        droite[rang - 1] = f"ligne {rang:02d} ALTEREE"
    assert len(set(gauche)) == HAUTEUR_DE_GRILLE, (
        "la fabrique produit des lignes indistinguables")
    return gauche, droite


#: Les quatre poses, et le motif de chacune. `milieu` est le point 2 (une
#: cible ailleurs qu'en premiere position) ; `tete` et `queue` sont le point 4,
#: pose le 2026-09-03 sur un mutant de balayage tronque -- une cible mediane
#: ne demasque pas un `for` qui saute la premiere ou la derniere entree.
#: `les_deux_bords` attrape le troisieme mode de panne, celui qu'aucune cible
#: unique ne voit : une comparaison qui s'arrete au premier ecart.
#:
#: **Retirer `tete` ou `queue` de cet inventaire est un mutant EQUIVALENT, et
#: c'est mesure plutot que declare** (`M21`, `M22`, campagne du 2026-09-05).
#: Les deux survivaient a la garde ci-dessous, et la garde a raison : la
#: propriete qu'elle mesure -- les deux bords sont couverts -- reste vraie,
#: `les_deux_bords` les couvrant a lui seul. L'equivalence a ete verifiee par
#: COMPOSITION, seule preuve qui vaille ici : `M21` compose avec le balayage
#: tronque en queue (`M16`) ROUGIT, `M22` compose avec le balayage tronque en
#: tete (`M17`) ROUGIT. Un inventaire mutile detecte donc encore ce que
#: l'inventaire entier detecte, et les trois entrees a cible unique sont de la
#: lisibilite, pas du pouvoir de detection.
POSES = {
    "tete": (1,),
    "milieu": (12,),
    "queue": (HAUTEUR_DE_GRILLE,),
    "les_deux_bords": (1, HAUTEUR_DE_GRILLE),
}


def test_les_POSES_couvrent_bien_LES_DEUX_BORDS_et_le_milieu():
    """Mutants `M21` et `M22` : retirer `queue` ou `tete` SURVIVAIT.

    C'est le defaut le plus insidieux de la campagne, parce qu'il eteint
    exactement le point 4 de la regle des fabriques sans faire rougir personne
    -- le `parametrize` joue simplement une pose de moins, et pytest ne compte
    pas les tests qu'on ne lui a pas demandes. Un inventaire de poses se garde
    donc par son CONTENU, jamais par le fait qu'il soit parcouru.

    Les trois positions sont exigees par leur RANG plutot que par leur cle :
    renommer `queue` en `fin` ne doit pas suffire a la faire disparaitre.
    """
    couverts = {rang for rangs in POSES.values() for rang in rangs}
    assert 1 in couverts, "aucune pose en TETE (regle des fabriques, point 4)"
    assert HAUTEUR_DE_GRILLE in couverts, (
        "aucune pose en QUEUE (regle des fabriques, point 4) : une cible "
        "mediane ne demasque pas un balayage tronque")
    milieu = couverts - {1, HAUTEUR_DE_GRILLE}
    assert milieu, (
        "aucune pose au MILIEU (regle des fabriques, point 2) : une cible en "
        "premiere position ne demasque pas un `find` fautif")
    assert any(len(rangs) > 1 for rangs in POSES.values()), (
        "aucune pose MULTIPLE : une comparaison qui s'arrete au premier ecart "
        "resterait verte sur toutes les poses a cible unique")


# **Ce que cette garde ne mesure PAS, dit plutot que tu** : mutant `M34` --
# remplacer la derivation `couverts` ci-dessus par un ensemble ECRIT EN DUR
# survit, la garde devenant tautologique. C'est un niveau de regression de
# plus (une garde qui garde la garde), et le depot s'arrete la : le meme
# raisonnement vaut pour `test_le_plancher_n_est_pas_DEGENERE` de
# `test_maquettes_couleur_a_jour.py`, dont la garde est elle aussi mutilable
# d'un cran plus haut. Ce qui ferme reellement ce cran est ailleurs -- la
# revue en trois couches, qui LIT la garde.


@pytest.mark.parametrize("pose", sorted(POSES))
def test_la_comparaison_MORD_sur_une_divergence_a_chaque_POSE(pose):
    """La comparaison attrape-t-elle vraiment ce qu'elle nomme ?"""
    attendus = POSES[pose]
    gauche, droite = grille_fabriquee(attendus)
    assert rangs_divergents(gauche, droite) == list(attendus), (
        f"une divergence posee en {pose} ({attendus}) n'est pas attrapee : la "
        f"comparaison rend {rangs_divergents(gauche, droite)}")


def test_la_comparaison_ne_voit_RIEN_sur_deux_grilles_identiques():
    """Le volet symetrique : une comparaison qui rougirait toujours ne dirait
    rien non plus. Sans lui, `rangs_divergents` pourrait rendre tous les rangs
    et les quatre poses ci-dessus resteraient... rouges, mais un mutant plus
    fin -- rendre `[rang]` des le premier ecart -- passerait la pose `tete`."""
    gauche, droite = grille_fabriquee()
    assert rangs_divergents(gauche, droite) == []


def test_la_comparaison_voit_une_grille_TRONQUEE():
    """Une grille de 23 lignes face a une de 24 : le rang 24 est un ecart.

    Sans ce test, un `zip` -- qui tronque au plus court sans un mot -- rendrait
    la variante conforme le jour ou elle perdrait sa derniere ligne.
    """
    gauche, _ = grille_fabriquee()
    assert rangs_divergents(gauche, gauche[:-1]) == [HAUTEUR_DE_GRILLE]
    assert rangs_divergents(gauche[:-1], gauche) == [HAUTEUR_DE_GRILLE]


# ===========================================================================
# La variante mesuree contre la nominale
# ===========================================================================

def test_les_deux_maquettes_EXISTENT():
    """Un chemin faux rendrait tout ce qui suit vert sur deux listes vides."""
    assert NOMINALE.is_file(), f"{NOMINALE} manque"
    assert VARIANTE.is_file(), f"{VARIANTE} manque"


#: Les deux maquettes dont le cadre est mesure. Un INVENTAIRE nomme plutot
#: qu'une liste posee dans le `parametrize` : mutant `M27` de la campagne --
#: retirer `NOMINALE` de la liste laissait les 17 autres tests VERTS, et la
#: grille de reference cessait d'etre mesuree sans un mot. Le cardinal
#: ci-dessous garde l'inventaire ; une liste anonyme n'a rien qui la garde.
CADRES_MESURES = {"E2-1e": NOMINALE, "E2-1i": VARIANTE}


def test_l_inventaire_des_CADRES_MESURES_porte_bien_LES_DEUX():
    """Volet qui manquait : sans lui, l'inventaire se vide en silence.

    Mesurer la variante seule ne suffit pas. La comparaison rang par rang
    plus bas est vraie de deux grilles egalement fautives ; c'est le cadre de
    la NOMINALE qui ancre la mesure, et il doit donc etre mesure lui aussi.
    """
    assert set(CADRES_MESURES) == {"E2-1e", "E2-1i"}, sorted(CADRES_MESURES)
    assert CADRES_MESURES["E2-1e"] == NOMINALE
    assert CADRES_MESURES["E2-1i"] == VARIANTE


@pytest.mark.parametrize("nom", sorted(CADRES_MESURES))
def test_le_cadre_80x24_TIENT(nom):
    """La grille de `DESIGN.md` section 1, mesuree des deux cotes.

    Les deux et non la seule variante : une grille de reference qui aurait
    derive rendrait la comparaison ci-dessous vraie pour une mauvaise raison.
    """
    chemin = CADRES_MESURES[nom]
    lignes = lignes_de_grille(chemin)
    assert len(lignes) == HAUTEUR_DE_GRILLE, (
        f"{chemin.name} porte {len(lignes)} lignes de grille")
    fautives = {rang: largeur_affichee(ligne)
                for rang, ligne in enumerate(lignes, 1)
                if largeur_affichee(ligne) != LARGEUR_DE_GRILLE}
    assert not fautives, (
        f"{chemin.name} : largeurs hors grille aux rangs {fautives}")


def test_la_variante_ne_porte_AUCUNE_annotation_manuscrite():
    """Une maquette neuve n'a pas encore ete relue : rien sous le cadre.

    Ce n'est pas un detail de forme. `construire_maquette.ecrire` REFUSE de
    reecrire une maquette annotee -- 38 des 85 `.txt` du dossier sont dans ce
    cas et sont donc hors d'atteinte de leur generateur. Tant que `E2-1i` n'en
    porte pas, elle se regenere ; le jour ou Egan y ecrit, ce test rougit et
    c'est le signal que ses remarques doivent partir dans
    `annotations-egan-<date>.md` AVANT toute regeneration.
    """
    entier = VARIANTE.read_text(encoding="utf-8").rstrip("\n").split("\n")
    surplus = [ligne for ligne in entier[HAUTEUR_DE_GRILLE:] if ligne.strip()]
    assert not surplus, (
        f"{VARIANTE.name} porte {len(surplus)} ligne(s) hors grille : les "
        "recopier dans `annotations-egan-<date>.md` avant de regenerer.")


def test_la_variante_ne_differe_de_E2_1e_QUE_sur_les_deux_rangs_ATTENDUS():
    """Le coeur du banc : `E2-1i` est une VARIANTE, pas un second ecran.

    Vingt-deux rangs sur vingt-quatre doivent etre identiques au caractere
    pres -- le bandeau, le cadre, les sept autres lignes de la fiche, les trois
    issues, la ligne de raccourcis. Une correction portee a l'un des deux
    ecrans et pas a l'autre fait rougir ici, ce qui est le seul moment ou elle
    se voit.
    """
    ecarts = rangs_divergents(lignes_de_grille(NOMINALE),
                              lignes_de_grille(VARIANTE))
    assert ecarts == list(RANGS_QUI_VARIENT), (
        f"`E2-1i` diverge de `E2-1e` aux rangs {ecarts}, attendu "
        f"{list(RANGS_QUI_VARIENT)}. Un rang de plus est une DERIVE : les deux "
        "etats se composent de la meme `fiche_de_declaration` cote "
        "generateur, et ce banc mesure que le produit le reflete. Un rang de "
        "moins veut dire que la variante ne varie plus.")


# ===========================================================================
# Ce que les deux rangs qui varient doivent porter -- et NE PAS porter
# ===========================================================================

def contenu(chemin: Path, rang: int) -> str:
    """Le texte d'un rang, hors bordures de cadre.

    Les bordures s'epluchent en BOUCLE et non d'un coup : une ligne de la
    fiche est doublement encadree (`│   │ … │   │`), et un `strip("│")` unique
    laissait les bordures internes -- premiere redaction de ce banc, attrapee
    par `test_la_ligne_RESOLUTION_garde_ce_qui_EST_mesure`.
    """
    texte = lignes_de_grille(chemin)[rang - 1]
    precedent = None
    while texte != precedent:
        precedent = texte
        texte = texte.strip().strip("│")
    return texte


#: Le compte de frames tel que la nominale l'ecrit. Une seule graphie compte
#: -- celle du dessin --, et elle est lue de `E2-1e` plutot que recopiee.
def cardinal_de_la_nominale() -> str:
    trouve = re.search(r"\d[\d   ]*frames", contenu(NOMINALE, 11))
    assert trouve is not None, (
        "la ligne `Résolution` de `E2-1e` ne porte plus de compte de frames : "
        "la variante n'a plus rien a omettre, et ce banc mesurerait le vide.")
    return trouve.group(0)


#: Les substituts INTERDITS a la place d'un champ non mesure. Trois familles,
#: chacune deja payee dans ce depot :
#:
#: * le zero et le tiret -- `DESIGN.md` / `EPIC7-ARB-67`, « jamais `0:00`,
#:   jamais `--:--` presente comme une duree » ;
#: * le mot `frames` sous toutes ses formes -- le compte lui-meme ;
#: * les libelles d'absence -- c'est l'issue 2, RECOMMANDEE a Egan et qu'il a
#:   ECARTEE. Elle est nommee ici pour qu'un futur lot ne la repose pas comme
#:   neuve en croyant appliquer l'arbitrage.
SUBSTITUTS_INTERDITS = (
    "frames",
    "images",
    "non corrobore",
    "non corroboré",
    "inconnu",
    "indisponible",
    "--",
    "―",
    "n/a",
    "?",
)


@pytest.mark.parametrize("rang", RANGS_QUI_VARIENT)
def test_aucun_SUBSTITUT_ne_prend_la_place_du_cardinal_absent(rang):
    """La frontiere NEGATIVE, et c'est la seule qui attrape un retour.

    Aucun test positif ne verrait revenir `nombre d'images non corrobore` ou
    un `--` : la ligne resterait bien formee, la grille tiendrait, la
    comparaison ci-dessus rougirait seulement si le rang cessait de varier --
    or il varierait toujours. Il faut nommer ce qui est interdit.
    """
    vus = substituts_vus(contenu(VARIANTE, rang))
    assert not vus, (
        f"rang {rang} de `E2-1i` : {vus} y prend la place du cardinal absent. "
        "`EPIC11-ARB-227`, verbatim d'Egan : « On n'affiche rien si on ne "
        f"corrobore pas ». Ligne fautive : {contenu(VARIANTE, rang)!r}")


def substituts_vus(texte: str) -> list[str]:
    """Les substituts interdits presents dans un texte.

    Ecrite UNE fois et appelee deux fois -- par la frontiere negative et par sa
    morsure. Le finding `F3` de la revue de la 11.13 dit ce qui arrive sinon :
    une comparaison recopiee dans son test de morsure n'est pas mesuree.
    """
    return [motif for motif in SUBSTITUTS_INTERDITS
            if motif.lower() in texte.lower()]


def test_le_lexique_des_SUBSTITUTS_mord_vraiment():
    """Mutant `M20` : vider `SUBSTITUTS_INTERDITS` SURVIVAIT a la campagne.

    La frontiere negative devenait alors structurellement incapable de rougir
    -- aucun motif, donc aucune trouvaille, donc verte pour toujours. C'est la
    version « lexique » de l'assertion tautologique, et le depot la connait :
    `test_sobriete_et_grille_extraction` verifie de la meme facon que son
    lexique de tournures directives mord sur les lignes reellement fautives.

    Le lexique est confronte a du texte qui LE contient vraiment, dont la ligne
    de la NOMINALE : elle porte un compte de frames, donc `frames` doit s'y
    voir. Une fabrique de synthese seule ne suffirait pas -- c'est le corpus
    reel qui dit que le lexique est ecrit dans la bonne graphie.
    """
    assert SUBSTITUTS_INTERDITS, "le lexique est vide : il ne mord plus rien"
    assert "frames" in substituts_vus(contenu(NOMINALE, 11)), (
        "le lexique ne voit pas le compte de la NOMINALE : sa graphie a derive")
    for faux in ("1920 x 1080 - nombre d'images non corrobore - 4:12",
                 "1920 x 1080 - -- - 4:12",
                 "1920 x 1080 - 6 300 frames - 4:12"):
        assert substituts_vus(faux), (
            f"le lexique laisse passer {faux!r}, qui est exactement ce "
            "qu'`EPIC11-ARB-227` interdit")
    assert not substituts_vus("Resolution  1920 x 1080 - 4:12"), (
        "le lexique mord sur une ligne CONFORME : il rougirait toujours, donc "
        "il ne dirait rien")


@pytest.mark.parametrize("rang", RANGS_QUI_VARIENT)
def test_le_cardinal_de_la_NOMINALE_a_bien_DISPARU_de_la_variante(rang):
    """Le volet symetrique du precedent, et il mord sur la graphie EXACTE.

    La liste ci-dessus est un lexique ferme ; celui-ci lit le compte tel que
    `E2-1e` l'ecrit, donc il suit si le dessin change de chiffre ou de
    separateur de milliers -- ce qu'un lexique recopie ne ferait pas.
    """
    compte = cardinal_de_la_nominale()
    assert compte in contenu(NOMINALE, 11), "la lecture du compte a derive"
    assert compte not in contenu(VARIANTE, rang), (
        f"rang {rang} de `E2-1i` porte encore {compte!r}")


def test_la_ligne_RESOLUTION_garde_ce_qui_EST_mesure():
    """L'omission ne doit pas emporter les deux champs qui restent.

    Une variante qui se contenterait de vider la ligne passerait les deux
    frontieres negatives ci-dessus. La resolution du flux et la duree, elles,
    sont mesurees -- la duree en particulier existe par construction, c'est
    elle qui a servi a TENTER la corroboration.
    """
    texte = contenu(VARIANTE, 11)
    assert texte.startswith("Résolution"), texte
    for garde in ("1920 × 1080", "4:12"):
        assert garde in texte, (
            f"{garde!r} a disparu de la ligne `Résolution` de la variante : "
            f"l'omission a emporte un champ MESURE. Ligne : {texte!r}")


def test_la_ligne_d_ETAT_de_la_variante_porte_encore_une_MESURE():
    """`EPIC11-ARB-56` : la ligne d'etat porte une mesure de l'ecran courant.

    Le cardinal en sort, mais elle ne devient pas vide pour autant : le rang du
    rush dans le projet et l'etat du disque sont deux mesures, et
    `DESIGN.md` section 3 n'autorise le vide que quand il n'y a **rien** a
    dire. Sans ce test, retirer la ligne entiere passerait pour une omission
    correcte.
    """
    texte = contenu(VARIANTE, 22)
    assert texte, "la ligne d'etat de `E2-1i` est vide"
    assert re.search(r"\d", texte), (
        f"la ligne d'etat ne porte plus aucun chiffre : {texte!r}")
    assert "rush du projet" in texte, texte


def test_la_ligne_d_etat_nominale_porte_bien_le_cardinal_QU_ON_RETIRE():
    """Volet amont : sans lui, la mesure du retrait porterait sur rien.

    Si `E2-1e` cessait un jour de nommer le compte dans sa ligne d'etat, le
    test du retrait ci-dessus resterait vert **sans rien mesurer** -- la
    tautologie exacte que ce depot chasse.
    """
    assert cardinal_de_la_nominale() in contenu(NOMINALE, 22), (
        "la ligne d'etat de `E2-1e` ne porte plus le compte de frames : le "
        "retrait mesure sur `E2-1i` ne mesure plus rien.")
