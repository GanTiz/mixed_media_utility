# -*- coding: utf-8 -*-
"""Story 11.9, lot E5 -- fermeture des critiques qui sont des TROUS DE MESURE.

Ce banc ne ferme que les critiques de `deferred-work.md` qui ne demandent
**aucun arbitrage produit** : chacune est un endroit ou le produit se comporte
correctement et ou **rien ne le mesure**. Les trois critiques qui attendent une
decision d'Egan -- le critere `partout` decide sur le module, la hauteur de page
restee au plancher, l'aide de champ qui se cache au lieu de tomber -- ne sont
**pas** ici.

**Le piege de cette story, paye TROIS fois avant ce lot, et la garde qu'on lui
oppose.** Trois faux « tues » ont ete trouves sur ce module : un mutant qui
mourait par la **mauvaise** frontiere (`COLONNE_DU_LIBELLE` 18 -> 17 mourait
parce que 17 vaut `jetons.HAUTEUR_CENTRE_AU_PLANCHER`), un banc qui employait la
constante comme **sonde de recherche** de ce qu'il verifiait, et un banc
**tautologique**. Les trois gestes que ce banc s'impose en consequence :

1. **aucune frontiere de ce fichier ne se repose sur une valeur qui vaut aussi
   autre chose** -- la borne de pagination est jouee a **trois** hauteurs
   distinctes (`10`, `17`, `22`), de sorte qu'une mort par collision avec
   `HAUTEUR_CENTRE_AU_PLANCHER` serait visible : elle ne tuerait qu'un cas sur
   trois ;
2. **aucune assertion n'emploie la valeur mesuree comme sonde** -- ce qui est
   attendu est ecrit **en dur** dans le test, jamais relu du module ;
3. **toute promesse ecrite est jouee** -- le temoin de la tache 1 porte son
   **volet de morsure** (`test_..._et_le_TEMOIN_est_bien_ATTEIGNABLE`), sans
   quoi « la touche n'est pas remontee » serait vrai d'un temoin debranche.
   C'est exactement ce qui rendait tautologique le banc qu'il remplace.

**Regle des fabriques** (`CLAUDE.md`, points 1 a 4) : les corpus portent au
moins trois elements **distinguables**, avec une cible **au milieu** et une a
**chaque bord**, et la position se verifie sur la liste que le **CODE**
parcourt -- ici `entrees_du_manuel()` dans son ordre rendu, pas une liste que le
test aurait ecrite de son cote.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import (
    ecran_manuel as em,
    jetons,
    manuel,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin


# ===========================================================================
# Tache 1 -- `⏎` : le `stop()` a bien un effet, et il se MESURE
# ===========================================================================

class CoqueQuiCOMPTELesTouchesRemontees(CoqueTui):
    """Une coque temoin qui **enregistre** les touches qui lui remontent.

    C'est le temoin que le banc d'origine n'avait pas. `textual` route une
    touche vers l'ecran **actif** puis, si l'ecran ne l'arrete pas, la fait
    remonter jusqu'a l'`App` -- **jamais** vers les ecrans *sous* la pile.
    L'effet reel de `evenement.stop()` dans `EcranManuel.on_key` n'est donc pas
    « empiler un second ecran » (ce mecanisme n'existe pas), c'est **couper la
    remontee vers l'application**. Ce temoin est le seul endroit d'ou cet effet
    est observable.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: Les touches vues par l'APPLICATION, dans l'ordre. Une liste et non
        #: un cardinal : deux touches differentes remontees une fois chacune se
        #: confondraient dans un compteur.
        self.touches_remontees: list[str] = []

    def on_key(self, evenement) -> None:  # pragma: no cover - pilote par le banc
        self.touches_remontees.append(evenement.key)


def coque_temoin() -> CoqueQuiCOMPTELesTouchesRemontees:
    """Deux paliers temoins, comme le banc du lot C : la racine et les ateliers."""
    return CoqueQuiCOMPTELesTouchesRemontees(
        paliers=[PalierTemoin("Projet", "⏎ ouvrir  F1 aide"),
                 PalierTemoin("Ateliers", "⏎ entrer  F1 aide")],
        contexte=Contexte("projet_demo"))


def _remontees_apres(touche: str, repetitions: int = 5):
    """Ouvre le manuel par `F1`, frappe `touche` n fois, rend ce qui a remonte.

    Le journal est **vide** juste apres `F1` : `F1` lui-meme remonte, et le
    compter fausserait la mesure de la touche visee.
    """
    async def scenario(pilote):
        app = pilote.app
        await pilote.press("f1")
        await pilote.pause()
        app.touches_remontees.clear()
        for _ in range(repetitions):
            await pilote.press(touche)
            await pilote.pause()
        return (list(app.touches_remontees),
                app.passages_empiles,
                isinstance(app.screen, em.EcranManuel))

    from conftest import piloter
    return piloter(coque_temoin(), scenario)


def test_E5_T1_entree_est_ARRETEE_et_ne_REMONTE_pas_a_l_application():
    """`⏎` sur le manuel : `stop()` coupe la remontee vers l'`App`. Mutant `M39`.

    **Ce que ce test remplace, et pourquoi.**
    `test_C1_entree_est_ARRETEE_et_n_empile_RIEN` asserte `passages_empiles == 1`
    en se reclamant d'un mecanisme qui n'existe pas -- « le laisser monter
    jusqu'a `descendre()` empilerait un second ecran ». `PalierTemoin.on_key`
    n'est **jamais** atteint depuis le manuel (`textual` ne descend pas sous la
    pile) et `CoqueTui.BINDINGS` ne lie `enter` nulle part : l'assertion est
    vraie **avec ou sans** `stop()`, c'est-a-dire tautologique. `M39` (retrait
    du `stop()`) y survivait.

    Ici, la garantie est celle que le produit tient reellement : rien ne remonte
    a l'application. Son volet de morsure est le test suivant.
    """
    remontees, empiles, encore = _remontees_apres("enter")
    assert remontees == [], (
        "`⏎` a REMONTE jusqu'a l'application alors que `EcranManuel.on_key` "
        f"est cense l'arreter par `evenement.stop()` : {remontees!r}")
    assert empiles == 1, empiles
    assert encore, "`⏎` a quitte le manuel"


def test_E5_T1_le_TEMOIN_est_bien_ATTEIGNABLE_par_une_touche_NON_arretee():
    """Volet de morsure : sans le temoin, le test precedent serait vert sur tout.

    `z` n'est ni annoncee ni arretee -- `traiter()` rend `False` et `on_key`
    sort **sans** `stop()`. Elle doit donc remonter, une fois par frappe. Si ce
    test rougissait, le precedent ne mesurerait plus rien : c'est le mode de
    panne « frontiere negative sans volet de morsure » que la 11.8 a paye deux
    fois.
    """
    remontees, _empiles, encore = _remontees_apres("z", repetitions=3)
    assert remontees == ["z", "z", "z"], (
        "le temoin de remontee est DEBRANCHE : une touche que le manuel "
        f"n'arrete pas doit atteindre l'application ({remontees!r})")
    assert encore, "`z` a quitte le manuel"


# ===========================================================================
# Tache 2 -- la borne de hauteur de page, eprouvee A L'EGALITE
# ===========================================================================

def _entree_d_une_ligne(rang: int) -> manuel.Entree:
    """Une entree d'**une** ligne, distinguable de ses voisines par son libelle."""
    return manuel.Entree(
        ouvreur=f"K{rang:02d}",
        libelles=(f"geste numero {rang}",),
        ecrans=(f"mixed_media_utility.tui.atelier_extraction.Ecran{rang}",),
        ateliers=("atelier_extraction",),
        partout=True)


#: Combien de lignes le titre de bloc coute en tete de la premiere unite :
#: une respiration, le titre, une respiration. Ecrit **en dur** plutot que relu
#: du module -- le relire ferait de l'assertion une sonde de ce qu'elle mesure,
#: qui est le second faux « tue » de cette story.
LIGNES_DU_TITRE_DE_BLOC = 3


def _corpus_de_hauteur_exacte(hauteur: int) -> tuple[manuel.Entree, ...]:
    """Le corpus dont la premiere page vaut **exactement** ``hauteur`` lignes."""
    return tuple(_entree_d_une_ligne(rang)
                 for rang in range(hauteur - LIGNES_DU_TITRE_DE_BLOC))


#: Trois hauteurs, et **aucune n'est seule a decider**. Le plancher de la grille
#: y figure parce que c'est le regime reel ; les deux autres parce qu'une mort
#: obtenue par collision avec une constante homonyme (`HAUTEUR_CENTRE_AU_PLANCHER`
#: vaut 17, et c'est par la que `COLONNE_DU_LIBELLE` 18 -> 17 avait faussement
#: « tue ») ne tuerait qu'un cas sur trois.
HAUTEURS_EPROUVEES = [10, jetons.HAUTEUR_CENTRE_AU_PLANCHER, 22]


@pytest.mark.parametrize("hauteur", HAUTEURS_EPROUVEES)
def test_E5_T2_une_page_qui_vaut_EXACTEMENT_la_hauteur_n_est_PAS_coupee(hauteur):
    """Mutant `M12` : `>` porte a `>=` a `ecran_manuel.py:315`.

    C'est le seul endroit du module ou `>` et `>=` ne disent pas la meme chose,
    et **rien** ne l'eprouvait a l'egalite : `test_C2_aucune_page_ne_DEPASSE_la
    _hauteur` est verte a `16 <= 17`, et `test_AC5_6_la_fabrique_des_PAGES`
    n'asserte que « trois pages ». Sous `>=`, la page perd sa derniere unite et
    `← parent` glisse d'une page -- sans un rouge.

    Le corpus est **taille pour l'egalite** : sa premiere page vaut exactement
    ``hauteur``. Sous `>=` elle en vaudrait une de moins et le manuel rendrait
    **deux** pages la ou il n'en faut qu'une.
    """
    pages = em.pages_du_manuel(_corpus_de_hauteur_exacte(hauteur),
                               hauteur=hauteur)
    assert len(pages) == 1, (
        f"un corpus qui tient en EXACTEMENT {hauteur} lignes a ete coupe en "
        f"{len(pages)} pages : la borne de pagination refuse l'egalite "
        f"(cardinaux rendus : {[len(page.lignes) for page in pages]})")
    assert len(pages[0].lignes) == hauteur, (
        f"la page unique devait porter EXACTEMENT {hauteur} lignes, elle en "
        f"porte {len(pages[0].lignes)}")


@pytest.mark.parametrize("hauteur", HAUTEURS_EPROUVEES)
def test_E5_T2_une_ligne_de_PLUS_coupe_bien_la_page(hauteur):
    """Le volet symetrique, sans lequel le test precedent serait vert sur tout.

    Une borne qui ne couperait **jamais** rendrait aussi « une seule page » :
    a `hauteur + 1` lignes de matiere, la coupure doit avoir lieu, et la
    premiere page doit valoir **exactement** ``hauteur``.
    """
    corpus = _corpus_de_hauteur_exacte(hauteur) + (
        _entree_d_une_ligne(hauteur),)
    pages = em.pages_du_manuel(corpus, hauteur=hauteur)
    assert len(pages) == 2, (
        f"un corpus de {hauteur + 1} lignes devait etre coupe en deux pages, "
        f"il en rend {len(pages)}")
    assert len(pages[0].lignes) == hauteur, (
        f"la premiere page devait etre remplie jusqu'a {hauteur} lignes avant "
        f"la coupure, elle en porte {len(pages[0].lignes)}")


# ===========================================================================
# Tache 3 -- `Entree.ecrans` mesure sur une ligne MULTI-ECRANS
# ===========================================================================

#: Les trois ouvreurs temoins, **aux trois positions de la liste que le CODE
#: parcourt** -- l'ordre rendu par `entrees_du_manuel()`, pas un ordre que le
#: test aurait choisi. `Espace` y est en **tete**, `→` en **queue**, `Coller`
#: **au milieu** (regle des fabriques, points 2 et 4). Les trois sont portes par
#: des lignes attribuees a DEUX ecrans, ce qui est exactement le regime que
#: `lettres_du_manuel()` ne peut pas voir : elle ne rend que des ouvreurs d'un
#: seul caractere, tous mono-ecran.
ECRANS_ATTENDUS_PAR_OUVREUR = {
    "Espace": (
        # `EcranInventaireDuProjet` a rejoint la liste le 2026-09-05 avec la
        # story 11.11 : `E6-1d` coche des objets de l'inventaire pour les
        # supprimer ensemble. L'attendu etant ecrit EN DUR, un porteur neuf
        # se declare ici -- c'est ce qui a fait rougir la garde, et c'est
        # exactement ce pour quoi elle est ecrite en dur.
        "mixed_media_utility.tui.atelier_extraction.EcranCadences",
        "mixed_media_utility.tui.atelier_extraction.EcranChoixDesCadences",
        "mixed_media_utility.tui.atelier_pdf_lots.EcranLotsAPlanches",
        "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine",
        "mixed_media_utility.tui.ecran_projet.EcranCreation",
        "mixed_media_utility.tui.ecran_projet.EcranProjet",
        "mixed_media_utility.tui.projet_inventaire.EcranInventaireDuProjet",
    ),
    "Coller": (
        "mixed_media_utility.tui.ecran_projet.EcranCreation",
        "mixed_media_utility.tui.ecran_projet.EcranProjet",
    ),
    "→": (
        "mixed_media_utility.tui.ecran_projet.EcranCreation",
        "mixed_media_utility.tui.ecran_projet.EcranProjet",
    ),
}


def test_E5_T3_les_trois_temoins_sont_bien_en_TETE_au_MILIEU_et_en_QUEUE():
    """La regle des fabriques se verifie sur la liste que le CODE parcourt.

    Sans ce test, les trois cibles pourraient toutes se retrouver au milieu au
    premier ajout d'un raccourci -- et le mutant de bord (un balayage tronque)
    redeviendrait invisible, ce qui est litteralement le defaut du 2026-09-03.
    """
    ouvreurs = [entree.ouvreur for entree in manuel.entrees_du_manuel()]
    assert len(ouvreurs) >= 3, ouvreurs
    assert ouvreurs[0] == "Espace", (
        f"la cible de TETE a bouge : {ouvreurs[:3]}")
    assert ouvreurs[-1] == "→", (
        f"la cible de QUEUE a bouge : {ouvreurs[-3:]}")
    milieu = ouvreurs.index("Coller")
    assert 0 < milieu < len(ouvreurs) - 1, (
        f"la cible du MILIEU est passee a un bord (rang {milieu} sur "
        f"{len(ouvreurs)})")


@pytest.mark.parametrize("ouvreur", sorted(ECRANS_ATTENDUS_PAR_OUVREUR))
def test_E5_T3_les_ECRANS_d_un_ouvreur_MULTI_ECRANS_sont_tous_retenus(ouvreur):
    """Mutant `M31` : `porteurs.update(ecrans)` reduit au **premier** ecran.

    `Entree.ecrans` n'etait asserti que par `lettres_du_manuel()`, qui ne rend
    que les ouvreurs d'**un seul caractere alphabetique** -- quatre au paquet,
    tous portes par des lignes mono-ecran. En ne retenant que le premier ecran
    de chaque ligne, **six entrees sur seize** perdaient un porteur et les
    584 tests restaient verts.

    L'attendu est ecrit **en dur** : le derouler du module en ferait une sonde
    de ce qu'il mesure.
    """
    entrees = {entree.ouvreur: entree for entree in manuel.entrees_du_manuel()}
    assert ouvreur in entrees, sorted(entrees)
    attendus = ECRANS_ATTENDUS_PAR_OUVREUR[ouvreur]
    assert entrees[ouvreur].ecrans == attendus, (
        f"les ECRANS porteurs de `{ouvreur}` ont change : le manuel en annonce "
        f"{len(entrees[ouvreur].ecrans)} la ou {len(attendus)} sont attendus. "
        f"Rendu {entrees[ouvreur].ecrans!r}, attendu {attendus!r}")


def test_E5_T3_au_moins_une_ligne_du_paquet_nomme_DEUX_ecrans():
    """Volet de morsure : la mesure ci-dessus serait vaine sur un paquet
    entierement mono-ecran.

    Elle epingle le regime que le docstring d'`ecrans_par_ligne` donne pour
    nominal -- une constante nommee par **deux** classes d'ecran du meme module.
    """
    multiples = {cle: ecrans
                 for cle, (ecrans, _etage) in manuel.ecrans_par_ligne().items()
                 if len(ecrans) > 1}
    assert len(multiples) >= 2, (
        "aucune ligne du paquet n'est attribuee a plusieurs ecrans : la mesure "
        f"de `Entree.ecrans` ne porte plus sur rien ({multiples!r})")


# ===========================================================================
# Tache 4 -- l'ORDRE des libelles, des ecrans et des ateliers d'une entree
# ===========================================================================

def test_E5_T4_toute_entree_derivee_rend_ses_LIBELLES_TRIES():
    """Mutants `M11` et `M35` : `tuple(sorted(...))` reduit a `tuple(...)`.

    `manuel.py` construit les libelles, les ecrans et les ateliers a partir de
    **`set`**, et `PYTHONHASHSEED` n'est pas fixe dans ce depot. Sans le tri, le
    manuel cesserait d'etre reproductible d'un lancement a l'autre -- mesure a
    la couche 1 : cinq graines, un seul rendu sain, **cinq** rendus mutes.

    La frontiere ne depend d'**aucune** graine : elle relit l'ordre rendu.
    """
    entrees = manuel.entrees_du_manuel()
    for entree in entrees:
        assert entree.libelles == tuple(sorted(entree.libelles)), (
            f"les libelles de `{entree.ouvreur}` ne sont pas TRIES -- le manuel "
            f"changerait d'un lancement a l'autre : {entree.libelles!r}")
        assert entree.ecrans == tuple(sorted(entree.ecrans)), (
            f"les ecrans de `{entree.ouvreur}` ne sont pas TRIES : "
            f"{entree.ecrans!r}")
        assert entree.ateliers == tuple(sorted(entree.ateliers)), (
            f"les ateliers de `{entree.ouvreur}` ne sont pas TRIES : "
            f"{entree.ateliers!r}")


def test_E5_T4_le_paquet_porte_de_QUOI_faire_mordre_ce_tri():
    """Volet de morsure : un tri sur des collections d'un seul element serait
    vert par construction.

    Trois cardinaux, pour les trois champs tries -- la couche 1 note que `M35`
    ne mord pas aujourd'hui **faute** d'entree a plusieurs ateliers ; ce test
    dit lequel des trois volets est reellement charge, plutot que de laisser
    croire que les trois le sont.
    """
    entrees = manuel.entrees_du_manuel()
    assert max(len(e.libelles) for e in entrees) >= 3, (
        "aucune entree ne porte trois libelles : le tri des libelles n'est pas "
        "mordu")
    assert max(len(e.ecrans) for e in entrees) >= 3, (
        "aucune entree ne porte trois ecrans : le tri des ecrans n'est pas "
        "mordu")
    assert max(len(e.ateliers) for e in entrees) >= 3, (
        "aucune entree ne porte trois ateliers : le tri des ateliers n'est pas "
        "mordu")


#: Huit ateliers **distinguables**, ecrits dans un ordre qui n'est PAS le leur
#: une fois tries -- `Scan` avant `Pdf` avant `Extraction`. Huit et non trois :
#: la survie du mutant « `sorted` retire » vaut la probabilite que l'ordre
#: d'iteration d'un `set` coincide avec l'ordre trie, soit `1/8!` par graine au
#: lieu de `1/3!`. Les cinq derniers ne sont pas des domaines connus de
#: `noms_de_domaine()` : ils tombent sur le repli « dernier segment
#: capitalise », ce qui est deliberement le chemin le moins mesure.
ATELIERS_TEMOINS = ("atelier_scan", "atelier_pdf", "atelier_extraction",
                    "atelier_hotel", "atelier_golf", "atelier_delta",
                    "atelier_charlie", "atelier_bravo")


def _entree_propre_a_HUIT_ateliers() -> manuel.Entree:
    """Une entree « propre » multi-ateliers -- que la derivation ne produit pas.

    `partout = len(ateliers) > 1` : une entree a plusieurs ateliers est donc
    toujours `partout`, et la branche qui **joint** les ateliers n'est jamais
    executee en production (`M30`, code mort, dette a part). Elle se mesure
    par fabrique ou pas du tout.
    """
    return manuel.Entree(
        ouvreur="T0",
        libelles=("un geste temoin",),
        ecrans=tuple(f"mixed_media_utility.tui.{module}.Ecran{rang}"
                     for rang, module in enumerate(ATELIERS_TEMOINS)),
        ateliers=ATELIERS_TEMOINS,
        partout=False)


def test_E5_T4_la_JOINTURE_des_ateliers_d_une_entree_est_TRIEE():
    """Le meme tri, sur `ecran_manuel.ateliers_d_une_entree` (mutant `M35`).

    Volet **en-processus** : il tue le mutant deterministe (`sorted(...)` porte
    a `sorted(..., reverse=True)`). Le mutant « `sorted` retire », lui, depend
    de l'ordre d'iteration d'un `set` et se ferme au volet suivant, qui est le
    seul a pouvoir le voir.
    """
    fabriquee = _entree_propre_a_HUIT_ateliers()
    lisibles = [em.atelier_lisible(module) for module in fabriquee.ateliers]
    attendu = f"({em.SEPARATEUR_DES_LIBELLES.join(sorted(lisibles))})"
    assert em.ateliers_d_une_entree(fabriquee) == attendu, (
        f"la jointure des ateliers n'est pas TRIEE : rendu "
        f"{em.ateliers_d_une_entree(fabriquee)!r}, attendu {attendu!r}")
    assert lisibles != sorted(lisibles), (
        "la fabrique a perdu sa morsure : ses ateliers sont deja dans l'ordre "
        f"trie, un rendu non trie serait indistinguable ({lisibles!r})")


#: Les graines jouees par le volet inter-processus. **Quatre valeurs fixes et
#: non `random`** : une graine tiree au hasard rendrait le banc irreproductible,
#: ce qui est exactement le defaut qu'il mesure.
GRAINES_EPROUVEES = ("0", "1", "7", "1234")


def _rendu_des_ateliers_sous_la_graine(graine: str) -> str:
    """Le rendu de la jointure, obtenu dans un processus a `PYTHONHASHSEED` fixe.

    **Un sous-processus est ici indispensable, et c'est le seul de ce banc** :
    `PYTHONHASHSEED` est lu au demarrage de l'interprete, un `set` de chaines
    ne peut donc pas changer d'ordre dans le processus courant.
    """
    import json
    import os
    import subprocess

    programme = (
        "import json, sys;"
        f"sys.path.insert(0, {_SRC!r});"
        "from mixed_media_utility.tui import ecran_manuel as em, manuel;"
        f"ateliers = {ATELIERS_TEMOINS!r};"
        "entree = manuel.Entree(ouvreur='T0', libelles=('un geste temoin',),"
        " ecrans=tuple('mixed_media_utility.tui.%s.Ecran%d' % (m, r)"
        "              for r, m in enumerate(ateliers)),"
        " ateliers=ateliers, partout=False);"
        "print(json.dumps(em.ateliers_d_une_entree(entree)))"
    )
    environnement = dict(os.environ, PYTHONHASHSEED=graine)
    acheve = subprocess.run([sys.executable, "-c", programme],
                            capture_output=True, text=True, timeout=60,
                            env=environnement)
    assert acheve.returncode == 0, acheve.stderr
    return json.loads(acheve.stdout.strip())


def test_E5_T4_la_JOINTURE_des_ateliers_est_LA_MEME_sous_quatre_graines():
    """Mutant `M35` sous sa vraie forme : `sorted({...})` reduit a `list({...})`.

    **Pourquoi ce volet existe alors que le precedent semble suffire.** Le
    mutant « `sorted` retire » a d'abord ete joue en processus unique, sur une
    fabrique a **trois** ateliers : il a **SURVECU**, l'ordre d'iteration du
    `set` coincidant, sur cette graine-la, avec l'ordre trie. Une frontiere qui
    ne tue qu'une graine sur six n'est pas une frontiere -- c'est un tirage.

    Ce que ce volet mesure est la propriete que le produit doit vraiment tenir :
    **le manuel se rend a l'identique d'un lancement a l'autre**. Elle est
    inter-processus par nature, puisque `PYTHONHASHSEED` n'est pas fixe dans ce
    depot et change a chaque lancement.

    **Ce que ce volet NE garantit pas, dit plutot que tu** : le code sain rend
    toujours vrai (le tri ne depend d'aucune graine), donc ce test n'est
    **jamais** rouge par hasard. Le mutant, lui, ne survivrait que si les
    **quatre** graines rendaient toutes le `set` de huit elements dans l'ordre
    trie -- de l'ordre de `(1/8!)**4`. C'est une quasi-certitude, pas une
    preuve, et c'est le prix de ne pas fixer `PYTHONHASHSEED` au depot.
    """
    lisibles = [em.atelier_lisible(module) for module in ATELIERS_TEMOINS]
    attendu = f"({em.SEPARATEUR_DES_LIBELLES.join(sorted(lisibles))})"
    rendus = {graine: _rendu_des_ateliers_sous_la_graine(graine)
              for graine in GRAINES_EPROUVEES}
    divergents = {graine: rendu for graine, rendu in rendus.items()
                  if rendu != attendu}
    assert not divergents, (
        "la jointure des ateliers CHANGE d'un lancement a l'autre : le manuel "
        f"n'est plus reproductible. Attendu {attendu!r} sous toute graine, "
        f"rendu autrement sous {divergents!r}")


# ===========================================================================
# Tache 5 -- la definition d'une « lettre », ecrite UNE fois et EPROUVEE
# ===========================================================================

#: Les temoins de la borne, et **chacun echoue par un cote different** du
#: predicat `len(ouvreur) == 1 and ouvreur.isalpha()`. Une table plutot qu'une
#: suite d'assertions : le paquet n'a aucun ouvreur qui distingue les deux
#: moities, donc le temoin ne peut venir que d'ici.
TEMOINS_DE_LA_LETTRE = [
    # (ouvreur, est-ce une lettre, ce que le temoin distingue)
    pytest.param("A", True, id="majuscule-nominale"),
    pytest.param("e", True, id="minuscule-nominale"),
    pytest.param("é", True, id="accentuee-un-caractere"),
    pytest.param("Ab", False, id="deux-caracteres-alphabetiques"),
    pytest.param("F1", False, id="deux-caracteres-mixtes"),
    pytest.param("1", False, id="un-caractere-non-alphabetique"),
    pytest.param("⏎", False, id="un-caractere-symbole"),
    pytest.param("+", False, id="un-caractere-ponctuation"),
    pytest.param("", False, id="chaine-vide"),
]


@pytest.mark.parametrize("ouvreur, attendu", [
    pytest.param(p.values[0], p.values[1], id=p.id)
    for p in TEMOINS_DE_LA_LETTRE])
def test_E5_T5_la_definition_d_une_LETTRE_a_ses_TEMOINS(ouvreur, attendu):
    """Mutant `M12` de la couche 1 : la borne `len(...) == 1 and isalpha()`.

    Elle etait ecrite **deux fois** -- `manuel.py` et une recopie dans
    `test_manuel_derive.py` --, si bien que le volet 2 comparait deux ensembles
    construits par la meme regle : muter la production seule ne pouvait pas les
    faire diverger, faute d'un ouvreur temoin au paquet. Le test etait vert
    **par absence de temoin**, pas par mesure.

    Le predicat vit desormais dans :func:`manuel.est_une_lettre`, appele par la
    production **et** par la recopie du banc, et il est eprouve ici sur des
    temoins qui distinguent chacune de ses deux moities.
    """
    assert manuel.est_une_lettre(ouvreur) is attendu, (
        f"`est_une_lettre({ouvreur!r})` devait rendre {attendu} -- la borne "
        "« un seul caractere ET alphabetique » a bouge")


def test_E5_T5_les_LETTRES_du_manuel_sont_exactement_celles_du_predicat():
    """Le predicat est celui que la derivation **emploie**, pas un homonyme.

    Sans ce volet, `est_une_lettre` pourrait etre juste et
    `lettres_du_manuel()` continuer a filtrer autrement : deux redactions a
    nouveau, ce que cette fermeture ferme.
    """
    attendues = {entree.ouvreur for entree in manuel.entrees_du_manuel()
                 if manuel.est_une_lettre(entree.ouvreur)}
    assert set(manuel.lettres_du_manuel()) == attendues, (
        f"rendu {sorted(manuel.lettres_du_manuel())}, "
        f"attendu {sorted(attendues)}")
    assert attendues, "le paquet n'annonce plus aucune lettre"
