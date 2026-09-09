# -*- coding: utf-8 -*-
"""Story 11.4, lot `O` -- la regle des MAJUSCULES de raccourci.

Consigne d'Egan du 2026-08-30, **recopiee verbatim** parce que c'est elle que ce
banc oppose au code :

> « Il faudrait d'ailleurs ecrire tous les raccourcis partout en majuscules pour
> la lisibilite, meme si on cable directement la touche du clavier, pas le
> raccourci maj+lettre ! »

Elle a **deux moities**, et un banc qui n'en mesurerait qu'une laisserait passer
exactement la regression que la regle cree :

1. **l'affichage** -- toute LETTRE de raccourci s'ecrit en majuscule, dans les
   lignes de raccourcis du paquet, dans les legendes de touches, et dans les
   maquettes ;
2. **la touche liee** -- elle reste la lettre NUE, minuscule. `ord("o")`,
   `caractere == "o"`, `("q", "quitter", ...)`. Un operateur qui tape `o` doit
   continuer de marcher, et **rien ne doit exiger la majuscule**.

**La divergence entre les deux est VOULUE**, et c'est le piege de ce lot : la
ligne d'aide dit `O` et le code dit `"o"`, cote a cote, si bien que le reflexe
du relecteur est d'aligner l'un sur l'autre. Les deux alignements sont des
regressions -- l'un defait la lisibilite demandee, l'autre casse le produit.
La regle est ecrite en entier dans `tui/coque.py` ; ce banc en est la moitie
executable, et il est ecrit pour rougir dans **les deux sens**.

**Ce que la regle ne vise pas**, mesure ici comme frontiere positive :

* les **touches nommees** (`Tab`, `Échap`, `Entrée`, `Espace`, `Suppr`,
  `Ctrl+R`, `F1`) et les **glyphes** (`⏎ ↑↓ ←→ ⌫`) gardent leur forme : la
  regle vise les lettres ;
* une **paire ou la casse est deja porteuse** -- `g debut` / `G fin` du journal
  `T3-1`, convention de `less` et de `vi` -- ne peut pas s'y plier sans faire
  deux entrees `G` ; elle est exclue **nommement**, jamais par silence ;
* une **ligne d'etat** ne porte aucune touche du tout (`EPIC11-ARB-56`) : il n'y
  a donc rien a y mettre en majuscule, et une ligne d'etat qui en porte une est
  une violation de l'arbitrage, pas un candidat a cette regle.

**Regle des fabriques** (`CLAUDE.md`, points 1, 2 et 2 bis) : les corpus
fabriques de ce banc portent **trois** lignes distinguables et la ligne visee
est **au milieu** -- ni en premiere position, ce qui laisserait vivre un `find`
qui rend toujours le premier element, ni en derniere, ce qui laisserait vivre un
`continue` -> `break` qui arrete la passe au premier ecart.
"""
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import cadence_previz
from mixed_media_utility.tui import (
    atelier_extraction,
    coque,
    jetons,
    rushes,
)

import test_atelier_extraction_cadences as banc_cadences
from test_repli_ascii import lignes_de_raccourcis_du_paquet
from test_sobriete_et_grille_extraction import (
    contenu_de_la_ligne,
    ecarts_de_sobriete,
    lignes_de_maquette,
    RANG_DE_L_ETAT,
)

RACINE = Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le rang de la ligne de RACCOURCIS dans la grille : l'avant-derniere, juste
#: au-dessus de la bordure basse et juste sous la ligne d'etat. **Derive du
#: plancher**, comme `RANG_DE_L_ETAT` dont il est le voisin : une hauteur
#: ecrite en dur ici divergerait de `jetons.HAUTEUR_PLANCHER`.
RANG_DES_RACCOURCIS = RANG_DE_L_ETAT + 1


def maquettes_du_depot() -> dict:
    """Les 58 maquettes, **derivees du disque** et jamais enumerees.

    Une maquette ajoutee entre dans la mesure sans que personne ait a y penser ;
    une enumeration ecrite ici serait la seconde liste qui derive.
    """
    return {chemin.name: chemin for chemin in sorted(MAQUETTES.glob("*.txt"))}


# ===========================================================================
# Lire les LETTRES annoncees, sans les confondre avec les noms de touche
# ===========================================================================

#: Une ligne de raccourcis est faite d'items separes par au moins deux blancs,
#: chacun ouvert par sa touche. Meme decoupe que
#: `test_sobriete_et_grille_extraction.touches_annoncees` et que
#: `test_ecran_projet_tui._libelles_de_ligne` : trois lectures de la meme
#: convention, qui est celle de toutes les maquettes du depot.
_SEPARATEUR_D_ITEMS = re.compile(r"\s{2,}")


def lettres_annoncees(ligne: str) -> list[str]:
    """Les LETTRES de raccourci qu'une ligne annonce, dans l'ordre.

    Une lettre de raccourci est le **premier mot** d'un item, quand ce mot fait
    exactement un caractere alphabetique. Tout le reste est ecarte, et chaque
    exclusion a sa raison :

    * un premier mot de plusieurs caracteres est soit un nom de touche (`Tab`,
      `Échap`, `Ctrl+R`, `F1`), soit un **libelle de zone** -- `Rushes`,
      `Explorateur`, qui ouvrent les lignes de `E2-1` et de `E2-1b` sans etre
      des touches du tout ;
    * un premier caractere non alphabetique est un **glyphe** (`⏎`, `↑↓`, `←→`,
      `⌫`, `→`), qui n'a pas de casse.

    Un item sans libelle (un mot seul) n'est pas un raccourci : il est saute,
    sans quoi le `q` d'un hypothetique item nu passerait pour une touche.
    """
    lettres = []
    for item in _SEPARATEUR_D_ITEMS.split(ligne.strip()):
        mots = item.split()
        if len(mots) < 2:
            continue
        premier = mots[0]
        if len(premier) == 1 and premier.isalpha():
            lettres.append(premier)
    return lettres


def test_la_lecture_des_LETTRES_ecarte_bien_NOMS_et_GLYPHES():
    """Volet symetrique de l'analyseur, et il porte les deux sens.

    Sans lui, un analyseur qui ne trouverait **jamais** de lettre rendrait tous
    les tests de ce banc verts sur n'importe quelle ligne, et un analyseur qui
    en trouverait partout les rendrait tous rouges. On mesure donc ce qu'il
    prend ET ce qu'il laisse.
    """
    ligne = ("⏎ valider   Tab champ   O revoir   Ctrl+R remettre   "
             "↑↓ naviguer   F1 aide   Q quitter")
    assert lettres_annoncees(ligne) == ["O", "Q"], ligne
    # Les libelles de zone qui ouvrent `E2-1` et `E2-1b` ne sont pas des touches.
    assert lettres_annoncees("Rushes   Tab ajouter un rush   ⏎ choisir") == []
    assert lettres_annoncees("Explorateur   ⏎ valider   ← parent") == []
    # Et une ligne sans aucune lettre en rend zero, pas une liste fantome.
    assert lettres_annoncees("Échap fermer   F1 manuel complet") == []
    # **Le libelle de zone AU MILIEU, et une lettre APRES lui** (regle des
    # fabriques, point 2 bis -- ajoute apres le survivant `M20` de la
    # campagne). Toutes les lignes du depot placent leur libelle de zone en
    # TETE, si bien qu'un `continue` mue en `break` y rendait le meme resultat :
    # la passe s'arretait sur un item qui, de toute facon, n'apportait aucune
    # lettre. Un item sans libelle doit etre SAUTE, pas terminer la lecture, et
    # cela ne se voit qu'avec quelque chose a trouver derriere lui.
    assert lettres_annoncees("Tab champ   Rushes   O revoir   Q quitter") == [
        "O", "Q"], "un item sans libelle est saute, il n'arrete pas la passe"


# ===========================================================================
# MOITIE 1 -- l'AFFICHAGE : toute lettre annoncee est en majuscule
# ===========================================================================

@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_toute_LETTRE_annoncee_par_le_PAQUET_est_en_MAJUSCULE(nom, ligne):
    """La moitie visible de la regle, sur **toutes** les lignes du paquet.

    Le balayage est celui de `test_repli_ascii` -- attributs de classe **et**
    constantes `RACCOURCIS_*` de module --, donc les lignes contextuelles
    (`EcranProjet` en a trois, `EcranPreviz` aussi) y sont. Le recopier ici en
    ferait un second balayage, qui divergerait au premier ecran ajoute.
    """
    minuscules = [lettre for lettre in lettres_annoncees(ligne)
                  if lettre.islower()]
    assert minuscules == [], (nom, minuscules, ligne)


def test_le_balayage_du_paquet_VOIT_vraiment_des_lettres():
    """Volet symetrique : un balayage qui ne verrait aucune lettre serait vert.

    Les quatre lettres du produit sont nommees : `A` et `X` sur `E2-2`, `O` sur
    `E2-2b` et `E2-2c`, `Q` sur les huit lignes qui annoncent la sortie.
    """
    vues = set()
    for ligne in lignes_de_raccourcis_du_paquet().values():
        vues.update(lettres_annoncees(ligne))
    assert {"A", "O", "Q", "X"} <= vues, sorted(vues)


#: **La legende de la fenetre de previz n'est pas une ligne de raccourcis**, et
#: elle porte pourtant des touches : celles d'une AUTRE surface, la fenetre
#: `cadence_previz` ouverte a cote du terminal. Ses items sont separes par ` · `
#: et non par trois blancs, donc le balayage generique ne la voit pas -- c'est
#: pour cela qu'elle est mesuree a part plutot que laissee de cote.
_SEPARATEUR_DE_LEGENDE = re.compile(r"\s*·\s*")


def test_la_LEGENDE_DE_LA_FENETRE_annonce_elle_aussi_des_MAJUSCULES():
    """`L boucle · N suivante · P précédente · R relire` / `Q fermer ...`.

    `L` portait deja la regle avant qu'elle soit generale (`cadence_previz`,
    lot `K2`), les quatre autres l'ont recue au lot `O`.
    """
    vues = []
    for ligne in atelier_extraction.LIGNES_DE_LA_FENETRE:
        for item in _SEPARATEUR_DE_LEGENDE.split(ligne.strip()):
            mots = item.split()
            if len(mots) >= 2 and len(mots[0]) == 1 and mots[0].isalpha():
                vues.append(mots[0])
    assert vues == ["L", "N", "P", "R", "Q"], vues


#: Les noms de touche, dans leur **forme canonique** : c'est ainsi qu'un clavier
#: les nomme, et la regle des majuscules ne les vise pas. Inventaire ferme,
#: ecrit ici parce que le depot n'en a aucune constante -- ce sont les noms des
#: touches d'un clavier, pas des valeurs du produit. Il est verifie non vide et
#: effectivement present dans le paquet par le volet symetrique ci-dessous.
_TOUCHES_NOMMEES = re.compile(
    r"^(Tab|Échap|Entrée|Espace|Suppr|Retour"
    r"|Ctrl\+\S+|Alt\+\S+|Maj\+\S+|Cmd\+\S+|F\d{1,2})$")

#: **Le seul ouvreur d'item qui n'est ni une touche ni un libelle de zone.**
#: `Coller : terminal` est une PHRASE, pas un raccourci : `Ctrl+V coller` a
#: quitte la ligne de saisie au finding `C1` parce que c'etait une promesse
#: qu'aucun terminal ne tient -- le collage passe par l'evenement `Paste`. La
#: ligne dit donc ou le geste se fait, sans nommer de touche. Ensemble ferme, et
#: son unicite est mesuree.
OUVREURS_QUI_NE_SONT_PAS_DES_TOUCHES = {"Coller"}


def noms_de_touche_annonces(ligne: str) -> list[str]:
    """Les ouvreurs d'item qui ne sont **ni une lettre ni un glyphe**.

    Ce sont les candidats « nom de touche » : plus d'un caractere, et un
    premier caractere alphabetique. Un item d'un seul mot est saute -- c'est un
    **libelle de zone** (`Rushes`, `Explorateur`), qui ouvre la ligne de `E2-1`
    et celle de `E2-1b` sans etre une touche.
    """
    noms = []
    for item in _SEPARATEUR_D_ITEMS.split(ligne.strip()):
        mots = item.split()
        if len(mots) < 2:
            continue
        premier = mots[0]
        if len(premier) > 1 and premier[0].isalpha():
            noms.append(premier)
    return noms


@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_toute_TOUCHE_NOMMEE_du_PAQUET_garde_sa_forme_CANONIQUE(nom, ligne):
    """**L'exclusion de la regle, mesuree** -- ajoutee apres les survivants
    `M14` et `M16` de la campagne.

    La regle des majuscules vise les LETTRES ; les touches nommees gardent leur
    forme. Rien ne le mesurait, et les deux sens y passaient : `Tab journal`
    mue en `TAB journal` (quelqu'un applique la regle trop loin) comme
    `F1 aide` mue en `f1 aide` (quelqu'un l'applique a l'envers). Une exclusion
    documentee et non mesuree n'est pas une exclusion, c'est une intention.
    """
    fautifs = [ouvreur for ouvreur in noms_de_touche_annonces(ligne)
               if ouvreur not in OUVREURS_QUI_NE_SONT_PAS_DES_TOUCHES
               and not _TOUCHES_NOMMEES.match(ouvreur)]
    assert fautifs == [], (nom, fautifs, ligne)


@pytest.mark.parametrize("nom", sorted(maquettes_du_depot()))
def test_toute_TOUCHE_NOMMEE_d_une_MAQUETTE_garde_sa_forme_CANONIQUE(nom):
    """Le meme invariant cote maquettes : elles portent les memes lignes."""
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_du_depot()[nom])[RANG_DES_RACCOURCIS - 1])
    fautifs = [ouvreur for ouvreur in noms_de_touche_annonces(ligne)
               if ouvreur not in OUVREURS_QUI_NE_SONT_PAS_DES_TOUCHES
               and not _TOUCHES_NOMMEES.match(ouvreur)]
    assert fautifs == [], (nom, fautifs, ligne)


def test_la_frontiere_des_TOUCHES_NOMMEES_MORD_dans_LES_DEUX_SENS():
    """Volet symetrique, et il porte les deux mutants qui avaient survecu.

    La cible est **au milieu** du corpus a trois lignes, et elle est la seule
    fautive : on mesure a la fois que la frontiere la trouve et qu'elle ne
    trouve qu'elle.
    """
    corpus = {
        "premiere": "⏎ valider   Tab champ   Échap retour   F1 aide",
        "AU MILIEU": "Tab journal   ÉCHAP interrompre   Q quitter",
        "derniere": "Espace cocher   Ctrl+R remettre   Suppr retirer",
    }
    trouves = {cle: [o for o in noms_de_touche_annonces(l)
                     if o not in OUVREURS_QUI_NE_SONT_PAS_DES_TOUCHES
                     and not _TOUCHES_NOMMEES.match(o)]
               for cle, l in corpus.items()}
    assert trouves["AU MILIEU"] == ["ÉCHAP"], trouves
    assert trouves["premiere"] == [] and trouves["derniere"] == [], trouves
    # Les deux mutants qui avaient survecu, verbatim.
    for fautive in ("TAB journal   Échap interrompre   Q quitter",
                    "⏎ entrer   ↑↓ naviguer   Échap projet   f1 aide"):
        assert [o for o in noms_de_touche_annonces(fautive)
                if not _TOUCHES_NOMMEES.match(o)], fautive
    # **Le libelle de zone AU MILIEU, et un nom de touche APRES lui.** Meme
    # forme que pour l'analyseur des lettres, et pour la meme raison : le
    # survivant `M20b` de la campagne etait un `continue` mue en `break` dans
    # `noms_de_touche_annonces`. Trois items, l'item sans libelle au milieu, et
    # la faute derriere lui -- une passe qui s'arreterait sur l'item sans
    # libelle ne verrait jamais le nom fautif.
    assert noms_de_touche_annonces(
        "Tab champ   Rushes   ÉCHAP retour") == ["Tab", "ÉCHAP"], (
        "un item sans libelle est saute, il n'arrete pas la passe")


def test_l_inventaire_des_TOUCHES_NOMMEES_est_VIVANT_et_son_exception_UNIQUE():
    """Volet symetrique de l'inventaire : une liste morte serait verte sur tout.

    Deux volets. D'abord chaque famille de l'inventaire doit etre **portee par
    une ligne reelle** du depot -- sinon la regex pourrait accepter n'importe
    quoi sans qu'on le voie. Ensuite l'exception `Coller` doit etre
    **exactement** celle-la : « une assertion positive laisse passer toute
    divergence supplementaire ».
    """
    ouvreurs = set()
    for ligne in lignes_de_raccourcis_du_paquet().values():
        ouvreurs.update(noms_de_touche_annonces(ligne))
    for nom, chemin in maquettes_du_depot().items():
        ouvreurs.update(noms_de_touche_annonces(contenu_de_la_ligne(
            lignes_de_maquette(chemin)[RANG_DES_RACCOURCIS - 1])))
    for attendu in ("Tab", "Échap", "Espace", "Suppr", "F1", "Ctrl+R"):
        assert attendu in ouvreurs, sorted(ouvreurs)
    hors_inventaire = {o for o in ouvreurs if not _TOUCHES_NOMMEES.match(o)}
    assert hors_inventaire == OUVREURS_QUI_NE_SONT_PAS_DES_TOUCHES, (
        sorted(hors_inventaire))


# ===========================================================================
# MOITIE 2 -- la TOUCHE LIEE reste la lettre NUE, en minuscule
# ===========================================================================

def test_la_touche_liee_de_la_SORTIE_est_la_MINUSCULE_nue():
    """`Q quitter` s'affiche, `("q", ...)` se cable.

    C'est le binding de l'application, donc celui de **tous** les ecrans : un
    seul endroit a mesurer, et c'est celui qui ferait le plus de degats.
    """
    touches = {touche for touche, _action, _libelle in coque.CoqueTui.BINDINGS}
    assert "q" in touches, sorted(touches)
    assert "Q" not in touches, sorted(touches)


def test_les_touches_de_la_FENETRE_de_previz_sont_les_MINUSCULES_nues():
    """Les cinq codes de `cadence_previz`, en face de la legende majuscule.

    `cv2.waitKey` masque a 8 bits **sans normaliser la casse** : `Maj+N` et `n`
    y sont deux codes distincts, si bien qu'une majuscule liee ici ne serait pas
    un doublon inoffensif mais un deplacement de la touche.
    """
    for lettre, code in (("n", cadence_previz.KEY_NEXT),
                         ("p", cadence_previz.KEY_PREVIOUS),
                         ("r", cadence_previz.KEY_REPLAY),
                         ("l", cadence_previz.KEY_LOOP),
                         ("q", cadence_previz.KEY_QUIT)):
        assert code == ord(lettre), (lettre, code)
        assert code != ord(lettre.upper()), (lettre, code)


def test_A_et_X_de_E2_2_agissent_a_la_MINUSCULE_nue():
    """`A ajouter` et `X extraire sans voir` s'affichent ; `a` et `x` agissent.

    Mesure **comportementale** : on presse la lettre nue sur l'ecran reel et on
    regarde ce qui change. Une garde textuelle sur le code source dirait que la
    lettre y figure, pas qu'elle est atteinte.
    """
    ecran = banc_cadences.ecran_de_cadences()
    assert ecran.traiter("a", "a") is True, "`a` nue ouvre la saisie"
    assert ecran.saisie == "", "et le champ de saisie est ouvert, pas seulement consomme"

    extraites = []
    autre = banc_cadences.ecran_de_cadences(extraire=extraites.append)
    # **La cible au MILIEU** (regle des fabriques, point 2 bis) : cocher la
    # premiere cadence laisserait vivre un parcours qui prend toujours la
    # premiere, cocher la derniere un parcours qui prend toujours la derniere.
    autre.liste.cadences[1].cochee = True
    assert autre.traiter("x", "x") is True, "`x` nue extrait sans voir"
    assert len(extraites) == 1, extraites


def test_O_de_E2_2c_agit_a_la_MINUSCULE_nue():
    """`O revoir` s'affiche, `caractere == "o"` se cable (`N1`, 2026-08-30)."""
    ecran = banc_cadences.ecran_de_choix()
    assert ecran.traiter("o", "o") is True, "`o` nue revient a la previz"


def test_les_TOUCHES_DE_MODE_du_relink_restent_en_MINUSCULE():
    """`r` et `d` sont une table de touches CABLEES, jamais un affichage.

    Elle est donc **hors** de la regle des majuscules, exactement comme les
    `BINDINGS` de la coque : ce qui doit passer en majuscule, c'est le bloc
    `r` / `d` **dessine** sur `E2-1`, et il ne l'est pas encore -- voir la note
    de ce banc sur la maquette `E2-1`.
    """
    assert set(rushes.TOUCHES_DE_MODE) == {"r", "d"}, dict(rushes.TOUCHES_DE_MODE)


@pytest.mark.parametrize("lettre", ["a", "x", "o", "q"])
def test_AUCUNE_majuscule_n_est_EXIGEE_nulle_part(lettre):
    """La moitie de la regle qu'Egan souligne : « rien ne doit exiger la
    majuscule ».

    La mesure est une **frontiere negative sur le paquet** : aucune comparaison
    de touche du paquet ne teste la majuscule d'une lettre de raccourci. Un
    `caractere == "O"` glisse dans un ecran passerait toutes les mesures
    comportementales ci-dessus -- elles disent que la minuscule marche, pas
    qu'elle est la seule voie -- et c'est precisement le mutant que ce lot
    devait tuer.
    """
    fautifs = []
    for module in sorted(Path(_SRC, "mixed_media_utility", "tui").glob("*.py")):
        texte = module.read_text(encoding="utf-8")
        # Les docstrings et commentaires citent la regle : on ne mesure que les
        # lignes de CODE, reperees a l'absence de marqueur de commentaire en
        # tete. La citation `ord("O")` de `coque.py` vit dans un commentaire.
        for rang, ligne in enumerate(texte.split("\n"), 1):
            if ligne.lstrip().startswith("#"):
                continue
            for motif in (f'== "{lettre.upper()}"', f'ord("{lettre.upper()}")',
                          f'"maj+{lettre}"', f'"shift+{lettre}"'):
                if motif in ligne:
                    fautifs.append((module.name, rang, motif))
    assert fautifs == [], fautifs


# ===========================================================================
# LES MAQUETTES suivent, et l'exclusion `g` / `G` est NOMMEE
# ===========================================================================

#: **La seule exclusion de la regle**, et elle est nominative : sur le journal
#: `T3-1`, `g` (debut) et `G` (fin) sont DEUX touches distinctes -- la
#: convention de `less` et de `vi` --, si bien que la casse y est porteuse.
#: Les mettre toutes deux en majuscule ferait deux entrees `G` dans la meme
#: ligne. `c copier` de la meme ligne, lui, suit la regle. L'ecart est remonte
#: a Egan comme un arbitrage a trancher, jamais corrige en silence.
EXCLUSION_DE_CASSE_PORTEUSE = {"T3-1-journal.txt": ["g"]}


def test_le_balayage_des_maquettes_les_VOIT_TOUTES():
    """Volet symetrique : un glob qui ne rendrait rien serait vert sur tout."""
    vues = maquettes_du_depot()
    assert len(vues) >= 55, sorted(vues)
    for attendue in ("E0-1-projet-recents.txt", "E2-2-extraction-cadences.txt",
                     "T3-1-journal.txt", "X9-recents-cinq-compteurs.txt"):
        assert attendue in vues, sorted(vues)


@pytest.mark.parametrize("nom", sorted(maquettes_du_depot()))
def test_toute_LETTRE_de_la_ligne_de_raccourcis_d_une_MAQUETTE_est_en_MAJUSCULE(
        nom):
    """La moitie visible, cote maquettes -- la source, pas le rendu.

    Les maquettes sont corrigees dans leurs generateurs puis regenerees ; ce
    banc constate a posteriori, en lisant ce que les generateurs produisent.
    C'est la meme disposition que le volet maquette de l'AC 8.4, et pour la
    meme raison : une correction faite dans le fichier rendu serait effacee a
    la regeneration suivante.
    """
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_du_depot()[nom])[RANG_DES_RACCOURCIS - 1])
    tolerees = EXCLUSION_DE_CASSE_PORTEUSE.get(nom, [])
    minuscules = [lettre for lettre in lettres_annoncees(ligne)
                  if lettre.islower() and lettre not in tolerees]
    assert minuscules == [], (nom, minuscules, ligne)


def test_l_EXCLUSION_de_casse_porteuse_est_EXACTEMENT_celle_qu_on_croit():
    """« Une assertion positive laisse passer toute divergence supplementaire »
    (`CLAUDE.md`, 2026-08-30). On mesure donc l'exception **et son unicite**.

    Deux volets : la ligne exclue porte bien les deux touches qui justifient
    l'exclusion, et **aucune autre maquette** n'a besoin d'y figurer.
    """
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_du_depot()["T3-1-journal.txt"])[
            RANG_DES_RACCOURCIS - 1])
    assert "g début" in ligne and "G fin" in ligne, ligne
    assert "C copier" in ligne, "la lettre sans homonyme, elle, suit la regle"

    en_defaut = set()
    for nom, chemin in maquettes_du_depot().items():
        raccourcis = contenu_de_la_ligne(
            lignes_de_maquette(chemin)[RANG_DES_RACCOURCIS - 1])
        if any(lettre.islower() for lettre in lettres_annoncees(raccourcis)):
            en_defaut.add(nom)
    assert en_defaut == set(EXCLUSION_DE_CASSE_PORTEUSE), sorted(en_defaut)


#: **Les maquettes qui coincident au CARACTERE PRES avec leur ecran.**
#: L'entree « Cinq ecarts entre les maquettes `E2-*` et la ligne de RACCOURCIS
#: des ecrans » de `deferred-work.md` (lot `G`, 2026-08-30) mesure la
#: confrontation ecran par ecran et conclut, verbatim : « `E2-1d`, `E2-2`,
#: `E2-2b` et `E2-2c` **coincident au caractere pres**. » Cette coincidence
#: etait **constatee et non mesuree** : rien n'empechait la maquette et la ligne
#: de deriver l'une de l'autre, ce que le survivant `M18` de la campagne a
#: montre en faisant diverger `E2-2c` sans qu'aucun banc rougisse.
#:
#: Les cinq autres ecrans de cet audit ne sont pas ici, et c'est deliberé :
#: leurs ecarts sont reels, documentes, et appartiennent au lot qui les
#: tranchera.
#:
#: **`E2-1f` s'y ajoute le 2026-09-05, et sa coincidence est mesuree ICI et non
#: heritee** (fermeture de `F18` de la revue de la 11.4e). Elle ne pouvait pas
#: venir de l'audit du 2026-08-30 : la maquette n'existait pas encore, elle est
#: nee d'`EPIC11-ARB-231` le 2026-09-05. `RACCOURCIS_REFUS_DE_CONFLIT` se
#: DISAIT « verbatim de la maquette » dans sa propre prose, et rien ne le
#: tenait -- c'est **litteralement** le mode de panne pour lequel cette
#: frontiere a ete ecrite, reapparu sur l'ecran suivant. Verdict avant
#: inscription : la ligne de code changee sans sa maquette passait les 6 757
#: tests de `tests/unit/tui` sans un rouge.
#:
#: **Ce que l'inventaire ne peut pas voir, dit plutot que tu** : `E2-1d` et
#: `E2-1f` portent volontairement la MEME chaine dans deux constantes
#: distinctes (`atelier_extraction`, et son commentaire dit pourquoi --
#: `manuel.ecrans_par_ligne` rattache une ligne a l'ecran qui la NOMME). Une
#: interversion des deux valeurs de cet inventaire resterait donc verte. Elle
#: cesserait de l'etre au premier jour ou les deux ecrans divergent, qui est
#: exactement le jour ou ca compte.
MAQUETTES_QUI_COINCIDENT_AVEC_LEUR_ECRAN = {
    "E2-1d-relink-refus-nomme.txt": "RACCOURCIS_REFUS_RELINK",
    "E2-1f-declaration-rush-deja-declare.txt": "RACCOURCIS_REFUS_DE_CONFLIT",
    "E2-2-extraction-cadences.txt": "RACCOURCIS_CADENCES",
    "E2-2b-extraction-previz.txt": "RACCOURCIS_PREVIZ",
    "E2-2c-extraction-choix.txt": "RACCOURCIS_CHOIX",
}

#: Le TEMOIN du volet anti-tautologie : une ligne du MEME module qui differe de
#: toutes les lignes inscrites. Elle est nommee une fois plutot que choisie au
#: cas par cas, et son unicite est mesuree -- un temoin qui se mettrait a
#: coincider avec une inscrite rendrait le volet muet sans rougir.
TEMOIN_QUI_DIFFERE = "RACCOURCIS_CADENCES_SANS_ECRAN"


@pytest.mark.parametrize("nom,constante",
                         sorted(MAQUETTES_QUI_COINCIDENT_AVEC_LEUR_ECRAN.items()))
def test_les_maquettes_qui_COINCIDENT_coincident_VRAIMENT(nom, constante):
    """La coincidence documentee, rendue OPPOSABLE.

    On lit **la maquette**, pas une transcription : c'est la seule facon que la
    mesure survive a un ajustement de la maquette. Le banc rougit des deux
    cotes -- une ligne de code qui bouge sans sa maquette, une maquette qui
    bouge sans son ecran --, ce qui est exactement le mode de panne que la
    regle des majuscules pouvait creer en touchant les deux surfaces a la fois.

    Le nom ne porte plus de cardinal (« les QUATRE ») : il en portait un, et
    l'entree de `E2-1f` l'a rendu faux le jour ou elle est arrivee. Un cardinal
    ecrit dans un nom de test est une seconde redaction de l'inventaire.
    """
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_du_depot()[nom])[RANG_DES_RACCOURCIS - 1])
    code = getattr(atelier_extraction, constante)
    assert ligne == code, (nom, constante, ligne, code)


@pytest.mark.parametrize("nom",
                         sorted(MAQUETTES_QUI_COINCIDENT_AVEC_LEUR_ECRAN))
def test_la_coincidence_INSCRITE_est_une_MESURE_et_non_une_TAUTOLOGIE(nom):
    """Volet symetrique : la comparaison doit MORDRE sur une divergence.

    Sans lui, une lecture de maquette qui rendrait la constante elle-meme (ou
    la chaine vide des deux cotes) rendrait le test precedent vert sur tout.

    Il porte sur **chaque** inscrite et non plus sur une seule : une lecture
    qui ne saurait ouvrir qu'un fichier -- et rendrait la chaine vide pour les
    autres -- passait le volet a une cible. La TETE et la QUEUE de l'inventaire
    y sont donc par construction (point 4 de la regle des fabriques), sans
    qu'un rang soit ecrit nulle part.
    """
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_du_depot()[nom])[RANG_DES_RACCOURCIS - 1])
    assert ligne, ("la lecture ne rend rien pour cette maquette : le volet "
                   "positif serait vert sur une constante vide", nom)
    temoin = getattr(atelier_extraction, TEMOIN_QUI_DIFFERE)
    assert ligne != temoin, (
        "et elle distingue deux lignes voisines du meme module", nom)


def test_le_TEMOIN_anti_tautologie_differe_de_TOUTES_les_inscrites():
    """Le volet qui garde le volet : un temoin qui coincide ne mesure rien.

    `E2-1d` et `E2-1f` portent deja la meme chaine dans deux constantes
    differentes -- la coincidence entre deux lignes de raccourcis n'est donc
    pas une hypothese d'ecole dans ce module.
    """
    temoin = getattr(atelier_extraction, TEMOIN_QUI_DIFFERE)
    coincidentes = [constante
                    for constante in MAQUETTES_QUI_COINCIDENT_AVEC_LEUR_ECRAN
                                     .values()
                    if getattr(atelier_extraction, constante) == temoin]
    assert coincidentes == [], (TEMOIN_QUI_DIFFERE, coincidentes)


# ===========================================================================
# LA FRONTIERE MORD -- dans les deux sens, et la cible est AU MILIEU
# ===========================================================================

#: **Trois lignes distinguables, la fautive au MILIEU** (`CLAUDE.md`, regle des
#: fabriques, points 2 et 2 bis). Une fabrique a deux elements dont la cible est
#: en second la place aussi en dernier, et les deux formes y sont
#: indiscernables : un `break` fautif au premier ecart passerait.
CORPUS_FAUTIF = {
    "premiere": "⏎ valider   Tab champ   Échap retour   F1 aide",
    "AU MILIEU": "Espace cocher   o revoir   ⏎ continuer   Q quitter",
    "derniere": "↑↓ naviguer   Ctrl+R remettre   Q quitter",
}


def test_la_frontiere_des_MAJUSCULES_MORD_sur_une_ligne_fautive():
    """Volet symetrique : une frontiere qui ne mord sur rien ne prouve rien.

    La ligne fautive est **au milieu** du corpus, et elle est la SEULE fautive :
    on mesure donc a la fois que la mesure la trouve et qu'elle ne trouve
    qu'elle.
    """
    trouvees = {nom: [lettre for lettre in lettres_annoncees(ligne)
                      if lettre.islower()]
                for nom, ligne in CORPUS_FAUTIF.items()}
    assert trouvees["AU MILIEU"] == ["o"], trouvees
    assert trouvees["premiere"] == [] and trouvees["derniere"] == [], trouvees


def test_la_frontiere_des_MAJUSCULES_ne_mord_PAS_sur_un_NOM_DE_TOUCHE():
    """Volet symetrique inverse, et il porte les pieges reels du depot.

    `Tab`, `Échap`, `Espace`, `Suppr`, `Ctrl+R`, `F1` commencent tous par une
    lettre ; une mesure naive sur le premier CARACTERE les declarerait fautifs
    et il faudrait alors ecrire `TAB` ou `ÉCHAP`, ce qu'Egan n'a pas demande.
    """
    for ligne in ("Tab journal   Échap interrompre   F1 aide",
                  "⌫ effacer   Ctrl+R remettre   Tab les choix   Échap annuler",
                  "⏎ ouvrir   Suppr retirer   Tab explorateur   F1 aide",
                  "→ page suivante   Échap fermer"):
        assert lettres_annoncees(ligne) == [], ligne


# ===========================================================================
# LE PIEGE DE MESURE DU LOT -- une majuscule n'est PAS plus large
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_la_MAJUSCULE_ne_change_AUCUNE_largeur(nom, ligne, ascii_seul):
    """Le risque nomme par Egan, **verifie plutot que cru**.

    « Une majuscule est parfois plus large qu'une minuscule dans une police a
    chasse variable -- mais la TUI est en chasse fixe, donc la largeur ne change
    pas. Verifie-le plutot que de me croire. »

    On compare donc la ligne a **elle-meme en minuscules** : si une casse
    coutait une colonne, les deux mesures divergeraient. Et on mesure dans les
    DEUX regimes, parce que le repli ASCII est le seul endroit du depot ou une
    ligne s'allonge (`⏎` vaut six colonnes une fois replie en `Entree`).
    """
    def mesure(texte: str) -> int:
        return jetons.colonnes(
            jetons.replier_ascii(texte) if ascii_seul else texte)

    assert mesure(ligne) == mesure(ligne.lower()), (nom, ligne)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom,ligne",
                         sorted(lignes_de_raccourcis_du_paquet().items()))
def test_toute_ligne_de_raccourcis_TIENT_la_grille_dans_LES_DEUX_regimes(
        nom, ligne, ascii_seul):
    """La grille 80x24, sur tous les ecrans touches, avant comme apres.

    `test_repli_ascii` mesure deja la meme chose ; la refaire ici n'est pas une
    redite mais la **contrepartie** de la regle : si une ligne devait etre
    raccourcie a cause du passage en majuscule, c'est ici qu'on le verrait, et
    c'est la LIGNE qu'on raccourcirait -- jamais la grille.
    """
    texte = jetons.replier_ascii(ligne) if ascii_seul else ligne
    if ascii_seul:
        assert texte.isascii(), (nom, texte)
    assert jetons.colonnes(texte) <= jetons.largeur_utile(80), (
        nom, jetons.colonnes(texte), texte)


@pytest.mark.parametrize("nom", sorted(maquettes_du_depot()))
def test_la_ligne_de_raccourcis_de_CHAQUE_MAQUETTE_tient_ses_80_colonnes(nom):
    """Meme mesure cote maquettes, cadre compris.

    La grille fait 80 colonnes bordures incluses : une majuscule qui aurait
    coute une colonne aurait pousse le `│` de droite, et le verificateur du
    generateur l'aurait vu -- mais seulement au moment de regenerer. Ce banc le
    voit a chaque passe.

    **Un seul regime ici, et c'est une frontiere, pas un oubli** : une maquette
    est un artefact UTF-8, cadre `│` compris. Lui appliquer `replier_ascii`
    mesurerait la largeur d'un fichier qui n'existe pas -- le repli est ce que
    l'ECRAN fait a l'execution, sur son texte, jamais ce que la maquette
    subit. Le repli des lignes du produit est mesure au test voisin, sur les
    lignes du paquet, dans les deux regimes.
    """
    ligne = lignes_de_maquette(maquettes_du_depot()[nom])[
        RANG_DES_RACCOURCIS - 1]
    assert jetons.colonnes(ligne) == 80, (nom, jetons.colonnes(ligne), ligne)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_TROIS_ecrans_a_lettres_de_l_atelier_TIENNENT_la_grille(ascii_seul):
    """La mesure de bout en bout, sur les ecrans reels et non sur des constantes.

    `E2-2`, `E2-2b` et `E2-2c` sont les trois ecrans dont une lettre a change ;
    ce sont donc les trois ou une ligne pourrait deborder. On mesure le corps
    ET la ligne d'etat, dans les deux regimes.
    """
    ecrans = (banc_cadences.ecran_de_cadences(),
              banc_cadences.previz_lue(jouer=banc_cadences.JoueurCompte()),
              banc_cadences.ecran_de_choix())
    for ecran in ecrans:
        lignes, _rang, _etats = ecran.composer(80, ascii_seul)
        for ligne in list(lignes) + [ecran.ligne_d_etat(ascii_seul),
                                     ecran.raccourcis]:
            texte = jetons.replier_ascii(ligne) if ascii_seul else ligne
            assert jetons.colonnes(texte) <= jetons.largeur_utile(80), (
                ecran.__class__.__name__, texte)
            if ascii_seul:
                assert texte.isascii(), (ecran.__class__.__name__, texte)


# ===========================================================================
# PARE-ARBITRAGE -- `EPIC11-ARB-56`, recopie verbatim
# ===========================================================================

#: **L'arbitrage, recopie verbatim face au test qui le mesure.**
#: `EPIC11-ARB-56`, pose par Egan le 2026-08-29 sur une remarque explicitement
#: generale :
#:
#:     « une remarque generale pour TOUS tes ecrans : tu es trop bavard dans les
#:     bandeaux en bas. Contente toi de mettre les raccourcis et les infos
#:     pertinentes mais pas une remarque d'aide ou, pire, de methode, a chaque
#:     fois. [...] Sois sobre. »
#:
#: Formule pour etre verifiable : la ligne d'etat porte une **mesure de l'ecran
#: courant**. Elle ne porte
#:
#: * **aucune touche** -- une touche va a la ligne des raccourcis ;
#: * **aucun conseil d'usage** (« tapez une lettre pour sauter ») ;
#: * **aucun motif de conception** (« un chemin en cours de frappe n'est pas une
#:   erreur »).
#:
#: **Portee, verbatim de la decision** : « Les neuf maquettes de l'explorateur
#: sont refaites sous cette regle. Les 46 autres maquettes et les cinq ecrans
#: deja livres **ne sont pas repris** dans cette story. »
#:
#: C'est pour cela que l'ensemble ci-dessous n'est pas vide et que ce banc ne le
#: vide pas : les six maquettes qui restent portent des touches en ligne d'etat,
#: elles appartiennent a des ateliers non livres, et les reprendre serait
#: elargir le scope du lot `O` -- ce que `CLAUDE.md` interdit explicitement.
#: Elles sont **remontees comme findings**, et cet ensemble ferme les rend
#: opposables : toute NOUVELLE violation rougit, et toute reparation aussi.
MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE = {
    "E0-2-projet-chemin.txt",        # `Tab complète, ↓ descend dans la liste`
    # `E3-1-scan-depot.txt` EST SORTI DE CET ENSEMBLE le 2026-08-30, avec la
    # passe de maquettes de la story 11.5 : sa ligne d'etat nommait `Tab` et
    # `↓`, elle est desormais VIDE -- l'ecran n'a encore rien a mesurer tant
    # qu'aucune source n'est designee. La frontiere a fait exactement ce qu'elle
    # promet : elle a rougi dans le sens de l'AMELIORATION, ce qu'une assertion
    # positive n'aurait pas fait.
    # `E3-6-scan-confirmation.txt` EST SORTI DE CET ENSEMBLE le 2026-09-01, avec
    # la passe de maquettes de la story 11.6 (ecart `H6`). Sa ligne d'etat
    # cumulait TROIS fautes -- `e pour éditer les noms — 48 caractères au plus,
    # A-Z a-z 0-9 - _` : une touche (`EPIC11-ARB-56`), une LETTRE offerte a cote
    # d'un champ de saisie (`EPIC11-ARB-68`), et le nombre 48 RECOPIE la ou
    # `tui.noms.LIMITE` EST `io.naming.CANONICAL_ID_MAX_LENGTH`. Elle porte
    # desormais une mesure, sur le modele de `E2-3`.
    #
    # La frontiere a fait exactement ce qu'elle promet : elle a rougi dans le
    # sens de l'AMELIORATION, ce qu'une assertion positive n'aurait pas fait.
    # C'est la deuxieme fois -- `E3-1` en est sorti le 2026-08-30 avec la 11.5.
    # `E4-2-exports-reglages.txt` et `E4-3-exports-confirmation.txt` SONT SORTIS
    # DE CET ENSEMBLE le 2026-09-02, avec la refonte des huit ecrans `E4-*` du
    # lot A de la story 11.8. Leurs lignes d'etat portaient respectivement
    # `↑↓ parcourt ... · ⏎ retient · e édite` et `↑↓ pour choisir, Entrée pour
    # valider.` -- des touches et un conseil d'usage, ce qu'`EPIC11-ARB-56`
    # interdit deux fois. Elles portent desormais une mesure.
    #
    # **QUATRIEME et CINQUIEME morsures de cette frontiere dans le sens de
    # l'AMELIORATION**, apres `E3-1` (2026-08-30, story 11.5), `E3-6`
    # (2026-09-01, story 11.6) et `E5-3` (2026-09-01, story 11.7). Cinq fois sur
    # cinq, c'est une REPARATION qu'elle a signalee, jamais une violation neuve
    # -- ce qu'une assertion positive n'aurait vu aucune de ces fois. La
    # frontiere ne mesure donc pas ce qu'on croyait lui demander (« surveiller
    # les fautes ») mais quelque chose de plus utile : **elle date les progres
    # et oblige a les dire**.
    # `E5-3-pdf-confirmation.txt` EST SORTI DE CET ENSEMBLE le 2026-09-01, avec
    # la passe de maquettes preparatoire de la story 11.7 (ecart `P4`). Sa ligne
    # d'etat portait DEUX touches et un conseil -- la meme que `E4-3`, recopiee
    # --, ce qu'`EPIC11-ARB-56` interdit : « la ligne d'etat porte une mesure,
    # jamais une touche ».
    #
    # **TROISIEME morsure de cette frontiere dans le sens de l'AMELIORATION**,
    # apres `E3-1` (2026-08-30, story 11.5) et `E3-6` (2026-09-01, story 11.6).
    # Elle merite d'etre notee pour ce qu'elle a attrape CETTE fois : la
    # correction et la sortie de l'ensemble ont ete faites par DEUX agents
    # differents, l'un n'ayant pas le droit d'ecrire dans ce fichier et l'autre
    # ne sachant pas pourquoi il venait de rougir. Sans l'ensemble EXACT, le
    # rouge n'aurait pas eu lieu et l'entree serait restee la -- une tolerance
    # survivante pour une faute corrigee, c'est-a-dire une frontiere qui
    # protege un defaut qui n'existe plus.
    #
    # `E4-3` reste, lui : l'atelier Exports n'a pas ete repris.
}


def test_l_ensemble_des_lignes_d_etat_FAUTIVES_est_EXACTEMENT_celui_la():
    """AC 8.4 elargi aux 58 maquettes, en ensemble EXACT et non en assertion
    positive.

    « L'ensemble des chemins qui divergent est **exactement** {X} mesure
    l'exception ET son unicite » (`CLAUDE.md`, 2026-08-30). Une assertion du
    genre « `E0-2` est fautive » laisserait entrer une septieme violation sans
    rien dire ; celle-ci rougit dans les deux sens.

    **Le lot `O` n'en repare aucune, et c'est delibere** : une ligne d'etat qui
    porte une touche est une violation d'`EPIC11-ARB-56`, pas une lettre a
    mettre en majuscule. La corriger demanderait de reecrire la mesure que la
    ligne doit porter a la place, ce qui est un arbitrage produit.
    """
    fautives = set()
    for nom, chemin in maquettes_du_depot().items():
        etat = contenu_de_la_ligne(
            lignes_de_maquette(chemin)[RANG_DE_L_ETAT - 1])
        if ecarts_de_sobriete(etat):
            fautives.add(nom)
    assert fautives == MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE, (
        sorted(fautives ^ MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE))


def test_AUCUNE_ligne_d_etat_du_PAQUET_ne_gagne_une_touche_au_passage():
    """La contrepartie cote code : mettre des lettres en majuscule ne doit pas
    en faire glisser une dans une ligne d'etat.

    Les lignes d'etat du paquet sont des CONSTANTES `PHRASE_*` et `LIBELLE_*`,
    balayees ici comme `test_repli_ascii` balaye les `RACCOURCIS_*`. C'est la
    frontiere que `EPIC11-ARB-56` demande, appliquee au produit et non aux
    maquettes.
    """
    import importlib
    import inspect
    import pkgutil

    import mixed_media_utility.tui as paquet

    fautives = []
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        for nom, valeur in inspect.getmembers(module):
            if not nom.startswith(("PHRASE_", "MENTION_")):
                continue
            if not isinstance(valeur, str) or not valeur:
                continue
            if ecarts_de_sobriete(valeur):
                fautives.append((module.__name__, nom, valeur))
    # `PHRASE_SUPPR` et `PHRASE_COLLAGE` sont les deux exceptions connues et
    # documentees d'`ecran_projet` : elles vivent dans le CORPS de l'ecran, pas
    # en ligne d'etat, et `EPIC11-ARB-56` ne vise que la ligne d'etat.
    hors_ligne_d_etat = {"PHRASE_SUPPR", "PHRASE_COLLAGE"}
    restantes = [f for f in fautives if f[1] not in hors_ligne_d_etat]
    assert restantes == [], restantes


# ---------------------------------------------------------------------------
# Story 11.2c, AC 4 ter -- `EPIC11-ARB-122`. Le separateur des lignes de
# raccourcis vaut DEUX blancs, dans tout le produit.
#
# La frontiere ci-dessous est ce qui fait tenir l'arbitrage : sans elle, « deux
# blancs » serait une phrase, vraie jusqu'a ce qu'un troisieme se glisse dans
# une ligne neuve sans que rien ne rougisse.
# ---------------------------------------------------------------------------

def _constantes_de_raccourcis():
    """Toutes les lignes de raccourcis du paquet `tui`, nommees par leur module.

    On lit les MODULES et non le texte des fichiers : une constante composee de
    deux morceaux -- la forme la plus courante ici -- ne se mesure pas a la
    lecture du source, et une frontiere qui la raterait ne mesurerait que les
    lignes courtes.
    """
    import importlib
    import pkgutil

    from mixed_media_utility import tui as paquet
    from mixed_media_utility.tui import coque

    trouvees = {}
    paliers = []
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        for nom in dir(module):
            valeur = getattr(module, nom)
            if nom.startswith("RACCOURCIS"):
                if isinstance(valeur, str) and valeur:
                    trouvees[f"{info.name}.{nom}"] = valeur
                continue
            # **Les PALIERS portent aussi leur ligne, et elle atteint l'ecran**
            # (finding `R14` de la revue du 2026-08-31, trouve par deux
            # couches). Cette fonction ne balayait que les noms commencant par
            # `RACCOURCIS`, si bien que cinq paliers vivants -- `EcranPasEncore`,
            # `EcranChiffre`, `EcranExecution`, `EcranInterruption`,
            # `EcranRefus` -- gardaient trois blancs pendant que la frontiere
            # restait verte. Il y avait donc deux rythmes a l'ecran, ce que le
            # motif d'`EPIC11-ARB-122` invoque precisement pour justifier sa
            # portee « produit entier ».
            if (isinstance(valeur, type)
                    and issubclass(valeur, coque.Palier)
                    and isinstance(getattr(valeur, "raccourcis", None), str)
                    and valeur.raccourcis):
                paliers.append((f"{info.name}.{nom}.raccourcis",
                                valeur.raccourcis))
    trouvees.update(paliers)
    return trouvees


def test_la_frontiere_voit_bien_TOUTES_les_lignes_de_raccourcis():
    """Anti-vacuite : une frontiere qui ne trouverait rien serait verte pour
    rien. Le depot en portait dix-neuf au `baseline_commit`."""
    trouvees = _constantes_de_raccourcis()
    assert len(trouvees) >= 15, sorted(trouvees)
    assert any(".RACCOURCIS_CHEMIN" in nom for nom in trouvees), sorted(trouvees)


def test_AUCUNE_ligne_de_raccourcis_ne_porte_TROIS_blancs():
    """`EPIC11-ARB-122`. Le separateur vaut deux blancs, partout.

    Deux rythmes dans le meme produit seraient un defaut plus visible que les
    six colonnes gagnees -- c'est pourquoi la portee est le produit entier et
    non la seule ligne du mode selection.
    """
    fautives = {nom: ligne for nom, ligne in _constantes_de_raccourcis().items()
                if "   " in ligne}
    assert fautives == {}, fautives


def test_AUCUNE_ligne_de_raccourcis_ne_deborde_de_la_grille():
    """Et c'est le repli ASCII qui contraint : `⏎` y vaut SIX colonnes.

    Une frontiere qui ne mesurerait que l'UTF-8 laisserait passer exactement les
    lignes que le terminal plancher ne rend pas -- le defaut deja paye sur
    `RACCOURCIS_CHEMIN_CACHES` et `RACCOURCIS_RECENTS`.
    """
    utile = jetons.largeur_utile()
    debordent = {}
    for nom, ligne in _constantes_de_raccourcis().items():
        for rendu, texte in (("UTF-8", ligne),
                             ("ASCII", jetons.replier_ascii(ligne))):
            if jetons.colonnes(texte) > utile:
                debordent[f"{nom} ({rendu})"] = jetons.colonnes(texte)
    assert debordent == {}, debordent


def test_R14_la_frontiere_voit_les_lignes_des_PALIERS_et_pas_seulement_les_constantes():
    """Finding `R14`, trouve par deux couches de la revue du 2026-08-31.

    `_constantes_de_raccourcis` ne balayait que les noms de module commencant
    par `RACCOURCIS`. Or un palier porte sa ligne dans un ATTRIBUT DE CLASSE, et
    elle atteint l'ecran exactement comme une constante. Cinq paliers vivants
    gardaient donc trois blancs pendant que la frontiere restait verte -- deux
    rythmes a l'ecran, ce qu'`EPIC11-ARB-122` invoque pour justifier sa portee.

    Anti-vacuite : ce test verifie que le balayage RAMENE bien des lignes de
    palier. Sans lui, un `issubclass` qui cesserait de matcher rendrait la
    frontiere verte pour rien -- la panne exacte qu'elle vient de fermer.
    """
    trouvees = _constantes_de_raccourcis()
    de_paliers = {nom for nom in trouvees if nom.endswith(".raccourcis")}
    assert len(de_paliers) >= 5, (
        "le balayage doit ramener les lignes portees par les PALIERS ; il en "
        f"trouve {len(de_paliers)} : {sorted(de_paliers)}")
    attendus = {"EcranPasEncore", "EcranChiffre", "EcranExecution",
                "EcranInterruption", "EcranRefus"}
    vus = {nom.split(".")[1] for nom in de_paliers}
    manquants = attendus - vus
    assert manquants == set(), (
        f"les cinq paliers que la revue a nommes doivent etre vus : "
        f"{sorted(manquants)} manquent. Vus : {sorted(vus)}")


def test_R18_les_MESURES_annoncees_en_commentaire_sont_les_mesures_REELLES():
    """Finding `R18`. Trois commentaires annoncaient des largeurs fausses.

    Ils comptaient AVANT le resserrement d'`EPIC11-ARB-122`, et l'un d'eux
    racontait encore la chute d'un jeton que le meme arbitrage venait de rendre
    -- il disait donc l'inverse de la constante qu'il commentait. Une
    justification qui s'appuie sur un chiffre faux ne justifie rien.

    La prose ne se mesure pas ; un chiffre, si. La convention est donc une
    ligne `#: MESURE: <utf8>/<ascii>` juste au-dessus de la constante, et ce
    test la confronte au reel. Ce qui se mesure se tient ; ce qui se relit se
    perd -- c'est la doctrine que `CLAUDE.md` applique deja a ses propres
    regles.
    """
    import re

    from mixed_media_utility.tui import jetons

    racine = Path(__file__).resolve().parents[3] / "src/mixed_media_utility/tui"
    motif = re.compile(
        r"#: MESURE: (\d+)/(\d+)\n(RACCOURCIS[A-Z_]*) = ", re.MULTILINE)
    vues = 0
    for chemin in sorted(racine.glob("*.py")):
        source = chemin.read_text(encoding="utf-8")
        module = __import__(
            f"mixed_media_utility.tui.{chemin.stem}", fromlist=["*"])
        for utf8, ascii_, nom in motif.findall(source):
            ligne = getattr(module, nom)
            reel = (jetons.colonnes(ligne),
                    jetons.colonnes(jetons.replier_ascii(ligne)))
            assert reel == (int(utf8), int(ascii_)), (
                f"{chemin.name}.{nom} : le commentaire annonce "
                f"{utf8}/{ascii_} colonnes, la constante en fait "
                f"{reel[0]}/{reel[1]}")
            assert max(reel) <= jetons.largeur_utile(), (chemin.name, nom, reel)
            vues += 1
    assert vues >= 3, (
        "anti-vacuite : la convention `#: MESURE:` doit etre TROUVEE. Une "
        f"frontiere qui ne lirait rien serait verte pour rien ; elle en voit {vues}")


def test_R26_les_lignes_de_raccourcis_des_MAQUETTES_tiennent_aussi_la_grille():
    """AC 4ter.2, que rien ne mesurait (finding `R26`).

    La ligne du mode selection n'existe que dans le generateur de maquettes --
    coherent, puisque la story 11.2c ne dessine aucun ecran --, et la frontiere
    neuve n'itere que le paquet `tui` : elle ne pouvait pas la voir. Mesuree a
    la main lors de la revue : 70 UTF-8 / 75 ASCII pour 76, conforme, mais rien
    ne le tenait.

    Les maquettes sont donc balayees elles aussi : leur ligne de raccourcis est
    la ligne 23 de la grille, entre les bordures. Deux proprietes, les memes que
    pour le produit -- pas de troisieme blanc, pas de debordement dans l'un ou
    l'autre rendu.
    """
    from mixed_media_utility.tui import jetons

    maquettes = (Path(__file__).resolve().parents[3] / "_bmad-output"
                 / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
                 / "maquettes")
    lues = 0
    fautives = {}
    debordantes = {}
    for chemin in sorted(maquettes.glob("*.txt")):
        lignes = chemin.read_text(encoding="utf-8").split("\n")
        if len(lignes) < 23:
            continue
        ligne = lignes[22][1:-1].rstrip()
        if not ligne.strip():
            continue
        lues += 1
        if "   " in ligne:
            fautives[chemin.stem] = ligne
        replie = jetons.replier_ascii(ligne)
        if max(jetons.colonnes(ligne),
               jetons.colonnes(replie)) > jetons.largeur_utile() + 2:
            debordantes[chemin.stem] = (jetons.colonnes(ligne),
                                        jetons.colonnes(replie))
    assert lues >= 30, (
        f"anti-vacuite : le balayage doit LIRE des lignes ; il en voit {lues}")
    assert fautives == {}, fautives
    assert debordantes == {}, debordantes
