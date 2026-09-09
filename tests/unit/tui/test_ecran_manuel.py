# -*- coding: utf-8 -*-
"""Story 11.9, lot C -- l'ECRAN du manuel des raccourcis (AC 2, AC 4).

Ce banc mesure ce que le lot C **dessine** ; la derivation, elle, est mesuree
par `test_manuel_derive.py` (lot A) et n'est pas rejouee ici -- deux bancs qui
mesureraient la meme chose divergeraient au premier ajustement.

**Trois familles, et chacune a une raison d'exister separement :**

1. **la classe et sa sortie** -- le manuel est un `Palier` `TRANSITOIRE` qui
   s'ouvre par-dessus n'importe quoi, y compris une tache en cours. Sa sortie
   `Échap` est reprise d'`EcranPasEncore.on_key` (`EPIC11-ARB-140`) : elle
   depile sur `len(screen_stack) > 1`, **jamais** sur `rang > 0`. Une classe
   qui deriverait de `Palier` sans reprendre ce geste **rouvrirait les deux
   culs-de-sac** -- pendant une tache, et a la racine ;
2. **la pagination et le budget de grille** -- la hauteur d'une page et la
   largeur d'une ligne se **lisent** de `jetons`, jamais ne se recopient
   (lecon de la 11.7 : `CANONICAL_ID_MAX_LENGTH` recopiee fausse trois fois) ;
3. **les deux frontieres negatives**, chacune avec son **volet de morsure**.
   Une frontiere sans morsure est verte sur un rendu vide, un module renomme
   ou un balayage casse -- c'est le mode de panne que la 11.8 a paye deux fois
   (`M2`, `M4` : « ecrites, relues, plausibles, et ne mesurant rien »).

**Regle des fabriques** (`CLAUDE.md`, points 1 a 4, exigee nommement par
l'AC 5.6) : les corpus de ce banc portent **trois** elements distinguables au
moins -- des valeurs **differentes**, jamais un remplissage uniforme --, avec
une cible **au milieu** *et* une cible a **chaque bord**, et la position se
verifie **sur la liste que le CODE parcourt** (`pages_du_manuel`,
`groupes_du_manuel`), pas sur celle que le test a ecrite.

**Ce que ce banc mesure et que la fiche n'annonce pas**, dit plutot que tu :
la confrontation a `T1-2` rend **quinze** lignes divergentes sur vingt (dix-sept
au lot C ; le lot D en a ferme deux sans les viser), la ou l'AC 4.2 en nomme
six. Les six sont bien la et chacune est mesuree a part ; les neuf autres
viennent de ce que la maquette ecrit des libelles de prose que le produit n'a
jamais portes, et d'un ordre d'ouvreurs que la derivation ne rend pas. Voir
:data:`RANGS_DIVERGENTS_DE_T1_2`.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from outils_frontiere import chaines_de_code

from mixed_media_utility.tui import (
    atelier_scan_completion,
    atelier_scan_rapport,
    ecran_manuel as em,
    jetons,
    manuel,
)
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    Palier,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import EcranExecution, SurfaceExecution

RACINE = Path(__file__).resolve().parents[3]
MODULE = (RACINE / "src" / "mixed_media_utility" / "tui" / "ecran_manuel.py")
MODULE_DE_LA_COQUE = (RACINE / "src" / "mixed_media_utility" / "tui"
                      / "coque.py")
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Les deux regimes, portes par tout test qui peint (AC 5.4).
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]


# ===========================================================================
# Fabriques -- trois elements distinguables, cible au MILIEU et aux DEUX BORDS
# ===========================================================================

def entree(ouvreur: str, *libelles: str, partout: bool = True,
           modules: tuple[str, ...] = ("atelier_extraction",)) -> manuel.Entree:
    """Une entree de manuel fabriquee, **distinguable de ses voisines**.

    Le libelle est passe, jamais par defaut : trois entrees au meme libelle
    rendraient invisible toute inversion d'appariement entre ouvreur et
    libelle -- c'est le mutant `M33` de la story 5.6, et c'est litteralement ce
    que la regle des fabriques ferme.
    """
    ecrans = tuple(f"mixed_media_utility.tui.{module}.Ecran{rang}"
                   for rang, module in enumerate(modules))
    return manuel.Entree(ouvreur=ouvreur, libelles=tuple(libelles),
                         ecrans=ecrans, ateliers=tuple(modules),
                         partout=partout)


#: Les trois ouvreurs vises par la regle des fabriques, **aux trois positions
#: qui demasquent trois pannes differentes** : la premiere demasque un
#: `find` qui rendrait toujours le dernier, la derniere un balayage tronque
#: (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03), celle du milieu un
#: `find` qui rendrait toujours le premier (mutant `M25` de la 5.7).
OUVREUR_DU_PREMIER_BORD = "B0"
OUVREUR_DU_MILIEU = "M0"
OUVREUR_DU_DERNIER_BORD = "Z9"

#: Combien d'entrees il faut pour que la pagination rende **trois** pages a la
#: hauteur derivee de la grille. Le cardinal est **verifie** par
#: :func:`test_AC5_6_la_fabrique_des_PAGES_tient_ce_que_la_regle_exige`, jamais
#: suppose : une fabrique qui ne rendrait qu'une page laisserait toute la
#: pagination sans mesure.
CARDINAL_DU_CORPUS = 40


def corpus_a_trois_pages() -> tuple[manuel.Entree, ...]:
    """Quarante entrees d'une ligne, **toutes distinguables**, trois pages.

    L'ouvreur et le libelle different a chaque rang : un remplissage uniforme
    rendrait vert un decoupage qui melangerait les pages.
    """
    entrees = [entree(f"K{rang:02d}", f"geste {rang}")
               for rang in range(CARDINAL_DU_CORPUS)]
    entrees[0] = entree(OUVREUR_DU_PREMIER_BORD, "le tout premier geste")
    entrees[len(entrees) // 2] = entree(OUVREUR_DU_MILIEU, "le geste du milieu")
    entrees[-1] = entree(OUVREUR_DU_DERNIER_BORD, "le tout dernier geste")
    return tuple(entrees)


def pages_du_corpus(ascii_seul: bool = False) -> tuple[em.Page, ...]:
    return em.pages_du_manuel(corpus_a_trois_pages(), ascii_seul=ascii_seul)


def ecran_du_corpus() -> em.EcranManuel:
    return em.EcranManuel(corpus_a_trois_pages())


# ===========================================================================
# C1 -- la classe, sa ligne, et sa sortie `Échap`
# ===========================================================================

def test_C1_le_manuel_est_un_PALIER_et_un_PASSAGE():
    """AC 2.4 et AC 2.5, ensemble parce qu'ils se paient ensemble.

    `Palier`, sinon la classe echappe aux trois gardes d'epic qui balaient le
    paquet ; `TRANSITOIRE`, sinon `rang` compte un palier de plus et
    `revenir_aux_ateliers()` / `RANG_DES_ATELIERS` derailleraient.
    """
    assert issubclass(em.EcranManuel, Palier)
    assert em.EcranManuel.TRANSITOIRE is True


def test_C1_la_ligne_du_manuel_est_VUE_par_le_balayage_du_paquet():
    """AC 2.4, volet symetrique : une ligne que le balayage ne voit pas
    echappe aux mesures de largeur, de repli et de majuscules.

    L'identite (`is`) et non l'egalite : deux chaines egales aujourd'hui
    divergeraient a la premiere correction faite d'un seul cote.
    """
    assert em.EcranManuel.raccourcis is em.RACCOURCIS_MANUEL
    lignes = manuel.lignes_de_raccourcis_du_paquet()
    cle = "mixed_media_utility.tui.ecran_manuel.RACCOURCIS_MANUEL"
    assert lignes.get(cle) == em.RACCOURCIS_MANUEL, sorted(
        nom for nom in lignes if "ecran_manuel" in nom)


def test_AC5_7_la_ligne_du_manuel_ne_porte_PAS_Q_quitter():
    """`EPIC11-ARB-140` : les passages annoncent la sortie, jamais `Q quitter`.

    `test_arb140_passages_sans_q_quitter.py:96` mesure un ensemble **exact**
    de trois classes transitoires qui l'annoncent encore. Le manuel est
    transitoire : sa ligne portant `Q quitter` -- ce que `T1-2` dessine --
    aurait fait rougir ce banc-la. On le **constate** ici plutot que de le
    supposer, et des deux cotes : la ligne ne le porte pas, et l'ensemble
    mesure sur tout le paquet ne bouge pas.
    """
    assert "Q quitter" not in em.RACCOURCIS_MANUEL

    encore = {nom for nom, classe in manuel.classes_d_ecran().items()
              if classe.TRANSITOIRE and "Q quitter" in (classe.raccourcis or "")}
    attendu = {
        "mixed_media_utility.tui.execution.EcranRefus",
        "mixed_media_utility.tui.coque.EcranPasEncore",
        "mixed_media_utility.tui.ecran_projet.EcranCreation",
    }
    assert encore == attendu, sorted(encore ^ attendu)


def test_AC5_8_la_ligne_du_manuel_est_CONFORME_des_sa_premiere_ecriture():
    """Les trois bancs d'epic l'enrolent tout seuls : autant qu'elle passe.

    Lettres en MAJUSCULE (il n'y en a aucune ici, et c'est mesure plutot que
    suppose), touches nommees canoniques, separateur a **deux** espaces
    (`EPIC11-ARB-122`), et 76 colonnes **dans les deux regimes** -- le repli
    ASCII est ce qui contraint, `⏎` y valant six colonnes.
    """
    items = manuel.items_d_une_ligne(em.RACCOURCIS_MANUEL)
    assert len(items) == 3, items
    minuscules = [ouvreur for ouvreur, _ in items
                  if len(ouvreur) == 1 and ouvreur.isalpha()
                  and ouvreur.islower()]
    assert minuscules == [], minuscules
    assert "Échap" in em.RACCOURCIS_MANUEL, em.RACCOURCIS_MANUEL
    for ligne in (em.RACCOURCIS_MANUEL,
                  jetons.replier_ascii(em.RACCOURCIS_MANUEL)):
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(), (
            ligne, jetons.colonnes(ligne))
    assert jetons.replier_ascii(em.RACCOURCIS_MANUEL).isascii()


def coque_a_deux_paliers() -> CoqueTui:
    """Deux paliers temoins : la racine et le menu des ateliers.

    **Deux et non un** : une pile a un seul palier ne distinguerait pas
    « depiler l'aide » de « remonter d'un palier ».
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir  F1 aide"),
                             PalierTemoin("Ateliers", "⏎ entrer  F1 aide")],
                    contexte=Contexte("projet_demo"))


def execution_montee() -> EcranExecution:
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    return EcranExecution(surface, "Extraction en cours")


def test_C1_echap_DEPILE_le_manuel_PENDANT_une_tache_sans_y_toucher(banc):
    """Le premier cul-de-sac d'`EPIC11-ARB-140`, ferme sur la classe NEUVE.

    `action_remonter` voit `tache_en_cours`, arme `interruption_demandee` et
    rend la main **sans depiler** : un manuel qui laisserait monter `Échap`
    serait insortable pendant toute une passe. Les trois observables, et il
    faut les trois -- on est redescendu, la tache n'a pas bouge, aucune
    interruption n'a ete armee au passage.
    """
    ecran = execution_montee()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("f1")
        await pilote.pause()
        sur_le_manuel = isinstance(app.screen, em.EcranManuel)
        await pilote.press("escape")
        await pilote.pause()
        return (sur_le_manuel, type(app.screen).__name__,
                app.tache_en_cours, app.interruption_demandee)

    sur_le_manuel, apres, tache, interruption = banc(coque_a_deux_paliers(),
                                                     scenario)
    assert sur_le_manuel, "`F1` n'a pas ouvert le manuel : la sonde ne mesure rien"
    assert apres == "EcranExecution", apres
    assert tache is True, "`Échap` sur le manuel a touche a la tache"
    assert interruption is False, "`Échap` sur le manuel a arme une interruption"


def test_C1_echap_sort_du_manuel_AUSSI_a_la_racine(banc):
    """Le second cul-de-sac, ferme du meme geste.

    A la racine `rang` vaut 0 -- le manuel est un passage, il ne compte pas
    comme palier --, donc `if self.rang > 0` ne depilait pas davantage, sans
    qu'aucune tache soit en cause. La sortie ne depend donc pas de l'endroit
    d'ou l'aide a ete demandee.
    """
    async def scenario(pilote):
        app = pilote.app
        await pilote.press("f1")
        await pilote.pause()
        ouvert = isinstance(app.screen, em.EcranManuel)
        await pilote.press("escape")
        await pilote.pause()
        return ouvert, app.rang, isinstance(app.screen, em.EcranManuel)

    ouvert, rang, encore = banc(coque_a_deux_paliers(), scenario)
    assert ouvert, "`F1` n'a pas ouvert le manuel : la sonde ne mesure rien"
    assert rang == 0, "la sonde n'etait pas a la racine"
    assert not encore, "`Échap` n'a pas depile le manuel a la racine"


def test_C1_entree_est_ARRETEE_et_n_empile_RIEN(banc):
    """`⏎` n'est pas annonce par la ligne du manuel : il ne doit donc rien faire.

    **Ce test etait TAUTOLOGIQUE, et il est garde en le disant** (revue 11.9,
    couche 1 `F9`, mutant `M39`, ferme au lot E5). Son motif d'origine --
    « le laisser monter jusqu'a `descendre()` empilerait cinq ecrans » --
    decrivait un mecanisme qui n'existe pas : `textual` route une touche vers
    l'ecran **actif** puis vers l'`App`, jamais vers les ecrans *sous* la pile,
    si bien que `PalierTemoin.on_key` n'est **jamais** atteint depuis le manuel
    et que `CoqueTui.BINDINGS` ne lie `enter` nulle part. `passages_empiles`
    vaut donc `1` **avec ou sans** le `evenement.stop()` de
    `EcranManuel.on_key` : `M39` y survivait, et la garantie annoncee etait
    fausse.

    Ce qu'il reste ici est ce qu'il mesurait reellement, et qui vaut d'etre
    garde : `⏎` ne quitte pas le manuel et n'empile rien de plus. **L'effet du
    `stop()`, lui, se mesure ailleurs** --
    `test_revue_11_9_lot_e5.py::test_E5_T1_entree_est_ARRETEE_et_ne_REMONTE_pas_a_l_application`,
    par une coque temoin qui journalise ce qui lui remonte, avec son volet de
    morsure.

    **Cinq pressions et non une** : c'est ce que le defaut d'API du 2026-08-28
    demandait de rejouer -- `descendre()` appele cinq fois --, et ca ne coute
    rien de le garder.
    """
    async def scenario(pilote):
        app = pilote.app
        await pilote.press("f1")
        await pilote.pause()
        for _ in range(5):
            await pilote.press("enter")
            await pilote.pause()
        return app.passages_empiles, isinstance(app.screen, em.EcranManuel)

    empiles, encore = banc(coque_a_deux_paliers(), scenario)
    assert empiles == 1, empiles
    assert encore, "`⏎` a quitte le manuel"


def test_C1_q_sur_le_manuel_ne_COURT_CIRCUITE_aucune_confirmation(banc):
    """Acquis de la 11.8, finding `C1-1` -- **troisieme occurrence de la classe**.

    Le manuel s'ouvre par-dessus une tache en cours. `q` n'y est pas annonce,
    mais la coque le lie globalement : il doit donc demander confirmation, et
    surtout pas quitter en une frappe.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre(execution_montee())
        await pilote.pause()
        await pilote.press("f1")
        await pilote.pause()
        await pilote.press("q")
        await pilote.pause()
        return (app.confirmation_de_sortie_demandee, app.tache_en_cours,
                app.is_running)

    confirmation, tache, vivante = banc(coque_a_deux_paliers(), scenario)
    assert tache is True, "la sonde n'avait pas de tache en cours"
    assert confirmation is True, "`q` n'a demande aucune confirmation"
    assert vivante, "`q` a quitte la TUI pendant une tache"


# ===========================================================================
# C2 -- la pagination, le budget de grille, la ligne d'etat
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_C2_aucune_page_ne_DEPASSE_la_hauteur_derivee_de_la_grille(ascii_seul):
    """`textual` coupe par le bas **en silence** : une page trop haute perdrait
    ses derniers raccourcis sans rien dire (defaut `I1`, mesure sur `E2-2`).

    La hauteur est **lue** de `jetons.HAUTEUR_CENTRE_AU_PLANCHER`, jamais
    saisie : la poser en dur ici en ferait une seconde source de verite, qui
    divergerait a la premiere retouche du cadre.
    """
    pages = em.pages_du_manuel(ascii_seul=ascii_seul)
    assert pages, "aucune page : la mesure ne mesure rien"
    trop_hautes = {rang: len(page.lignes) for rang, page in enumerate(pages)
                   if len(page.lignes) > jetons.HAUTEUR_CENTRE_AU_PLANCHER}
    assert trop_hautes == {}, trop_hautes


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C2_aucune_ligne_du_manuel_ne_DEBORDE_de_la_grille(ascii_seul):
    """AC 5.5 -- 76 colonnes en UTF-8 **et** en repli ASCII.

    Le budget se **lit** de `jetons.largeur_utile()`. C'est le repli qui
    contraint : `⏎` y vaut six colonnes (`Entree`), si bien qu'une ligne calee
    juste en UTF-8 deborde une fois repliee.
    """
    utile = jetons.largeur_utile()
    debordantes = [ligne
                   for page in em.pages_du_manuel(ascii_seul=ascii_seul)
                   for ligne in page.lignes
                   if jetons.colonnes(ligne) > utile]
    assert debordantes == [], debordantes


def test_C2_le_module_ne_RECOPIE_aucune_largeur_ni_hauteur_de_grille():
    """Frontiere negative : la lecon de `CANONICAL_ID_MAX_LENGTH`, recopiee
    fausse trois fois dans ce depot.

    Les colonnes du dessin (`5`, `18`, `47`) sont relevees sur la maquette et
    n'ont pas de source ailleurs ; le **budget**, lui, en a une. Un `76` ou un
    `17` litteral dans ce module serait une seconde source de verite.
    """
    interdits = {jetons.largeur_utile(), jetons.LARGEUR_PLANCHER,
                 jetons.HAUTEUR_CENTRE_AU_PLANCHER, jetons.HAUTEUR_PLANCHER}
    arbre = ast.parse(MODULE.read_text(encoding="utf-8"))
    recopies = sorted({noeud.value for noeud in ast.walk(arbre)
                       if isinstance(noeud, ast.Constant)
                       and isinstance(noeud.value, int)
                       and not isinstance(noeud.value, bool)
                       and noeud.value in interdits})
    assert recopies == [], recopies


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C2_la_ligne_d_etat_porte_une_MESURE_et_aucune_touche(ascii_seul):
    """`EPIC11-ARB-56`, contre le vide que `T1-1` et `T1-2` dessinent.

    Une ligne d'etat vide n'est pas neutre : c'est une zone de la grille qui ne
    dit rien alors que l'arbitrage lui donne un role. Elle porte donc une
    mesure -- et **aucune touche**, ce que le meme arbitrage interdit.
    """
    ecran = em.EcranManuel()
    ligne = ecran.ligne_d_etat(ascii_seul)
    assert ligne.strip(), "la ligne d'etat du manuel est vide"
    assert re.search(r"\d", ligne), ligne
    touches = {ouvreur for nom_de_ligne in
               manuel.lignes_de_raccourcis_du_paquet().values()
               for ouvreur, _ in manuel.items_d_une_ligne(nom_de_ligne)}
    assert touches, "le vocabulaire des touches est vide : rien n'est mesure"
    portees = sorted(touche for touche in touches
                     if touche in ligne.split())
    assert portees == [], (portees, ligne)


def test_C2_le_rang_de_page_du_bandeau_est_DERIVE_jamais_ECRIT():
    """Q2 de la fiche : « le manuel affiche `page 1 sur 1` plutot que de mentir
    a `3` ». Le total vient du cardinal derive, et de rien d'autre.

    La cible est la page **du milieu** du corpus a trois pages : ni la
    premiere, qui resterait juste avec un rang code en dur a 1, ni la derniere.
    """
    ecran = ecran_du_corpus()
    total = len(ecran.pages())
    assert total == 3, total
    ecran.rang_de_page = 1
    assert ecran.objet_du_bandeau() == "page 2 sur 3", ecran.objet_du_bandeau()
    ecran.rang_de_page = 2
    assert ecran.objet_du_bandeau() == "page 3 sur 3", ecran.objet_du_bandeau()

    reel = em.EcranManuel()
    assert reel.objet_du_bandeau() == f"page 1 sur {len(reel.pages())}"


def test_C2_aucun_ouvreur_n_est_PERDU_ni_DOUBLE_par_la_pagination():
    """Le decoupage ne perd rien et ne repete rien -- egalite d'ensembles.

    Une assertion positive (« la page 1 porte `Espace` ») laisserait passer un
    ouvreur oublie comme un ouvreur compte deux fois.
    """
    entrees = manuel.entrees_du_manuel()
    pagines = [ouvreur for page in em.pages_du_manuel()
               for ouvreur in page.ouvreurs]
    attendus = [e.ouvreur for e in entrees]
    assert pagines == attendus, (
        sorted(set(pagines) ^ set(attendus)), len(pagines), len(attendus))


def test_AC5_6_la_fabrique_des_PAGES_tient_ce_que_la_REGLE_exige():
    """Trois pages, cible **au milieu**, et une cible a **chaque bord**.

    La position se verifie sur la liste que le CODE parcourt -- les pages que
    :func:`ecran_manuel.pages_du_manuel` rend --, pas sur celle que le test a
    ecrite. Une cible au milieu demasque un `find` qui rendrait le premier
    element (mutant `M25` de la 5.7) ; elle **ne demasque pas** un balayage
    tronque, qui est un autre mode de panne, et c'est pourquoi les deux bords
    sont poses aussi (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03).
    """
    pages = pages_du_corpus()
    assert len(pages) == 3, [len(page.ouvreurs) for page in pages]
    assert OUVREUR_DU_PREMIER_BORD in pages[0].ouvreurs, pages[0].ouvreurs
    assert OUVREUR_DU_MILIEU in pages[1].ouvreurs, pages[1].ouvreurs
    assert OUVREUR_DU_DERNIER_BORD in pages[2].ouvreurs, pages[2].ouvreurs
    # Les trois libelles sont **distinguables** : un remplissage uniforme
    # rendrait vert un decoupage qui melangerait les pages.
    libelles = {ligne.strip() for page in pages for ligne in page.lignes}
    assert len({"le tout premier geste", "le geste du milieu",
                "le tout dernier geste"} & {
                    partie for libelle in libelles
                    for partie in [libelle.split("  ")[-1].strip()]}) == 3, (
        sorted(libelles))


@pytest.mark.parametrize("ascii_seul", MODES)
def test_AC5_6_les_LIGNES_d_une_entree_apparient_le_bon_LIBELLE(ascii_seul):
    """Trois libelles **distincts** sur un meme ouvreur, cible au milieu.

    Trois fois le meme libelle rendrait invisible toute inversion
    d'appariement -- c'est le mutant `M33` de la 5.6, et il n'a ete trouve que
    par mutation.
    """
    trois = entree("Tab", "premier", "AU MILIEU", "dernier")
    lignes = em.lignes_d_une_entree(trois, ascii_seul=ascii_seul)
    texte = " ".join(lignes)
    assert texte.index("premier") < texte.index("AU MILIEU") < texte.index(
        "dernier"), texte
    assert lignes[0].startswith(" " * em.COLONNE_DE_L_OUVREUR + "Tab"), lignes


@pytest.mark.parametrize("ascii_seul", MODES)
def test_AC5_6_l_ATELIER_annonce_est_celui_du_bon_MODULE(ascii_seul):
    """Trois modules distinguables, cible **au milieu**, plus les deux bords.

    Un resolveur qui rendrait toujours le premier module reste vert sur toute
    fabrique mono-module ; un balayage tronque reste vert sur toute fabrique
    dont la cible n'est pas en queue.
    """
    corpus = {
        "premier bord": entree("K1", "geste", partout=False,
                               modules=("atelier_extraction",)),
        "AU MILIEU": entree("K2", "geste", partout=False,
                            modules=("atelier_scan_calibrate",)),
        "dernier bord": entree("K3", "geste", partout=False,
                               modules=("atelier_exports_lot",)),
    }
    rendus = {cle: em.lignes_d_une_entree(valeur, ascii_seul=ascii_seul)[-1]
              for cle, valeur in corpus.items()}
    assert rendus["premier bord"].endswith("(Extraction)"), rendus
    assert rendus["AU MILIEU"].endswith("(Scan)"), rendus
    assert rendus["dernier bord"].endswith("(Exports)"), rendus


def test_C2_les_noms_d_ATELIER_sont_LUS_du_produit_et_non_RECOPIES():
    """Volet symetrique de la table de noms : si elle s'effondrait, tout
    tomberait dans le repli et la mesure ci-dessus serait vide."""
    connus = em.noms_de_domaine()
    assert len(connus) >= 5, connus
    assert {"Extraction", "Scan", "Pdf", "Exports", "Projet"} <= set(connus)
    # Le repli existe et il NOMME plutot que de rendre le vide.
    assert em.atelier_lisible("mixed_media_utility.tui.execution") == "Execution"
    assert em.atelier_lisible("mixed_media_utility.tui.ecran_projet") == "Projet"


# ===========================================================================
# AC 2.3 -- tout est atteignable au CLAVIER, par `traiter()` seul
# ===========================================================================

def test_AC2_3_chaque_page_est_atteinte_par_TRAITER_SEUL():
    """`EPIC11-ARB-11` : « aucun geste n'est atteignable seulement a la souris ».

    Sans `Pilot` ni souris, comme tout ecran du depot : pour **chaque** page,
    on l'atteint, on revient a la precedente, et on sort.
    """
    ecran = ecran_du_corpus()
    total = len(ecran.pages())
    assert total >= 3, total
    for vise in range(total):
        ecran.rang_de_page = 0
        for _ in range(vise):
            assert ecran.traiter("right") is True
        assert ecran.rang_de_page == vise, (vise, ecran.rang_de_page)
        assert ecran.traiter("left") is True
        assert ecran.rang_de_page == max(0, vise - 1)
        assert ecran.traiter("escape") is True, "la sortie n'est pas au clavier"


def test_AC2_3_l_ensemble_des_pages_ATTEINTES_est_EXACTEMENT_celui_de_la_derivation():
    """Le volet symetrique, et il n'est pas decoratif.

    Un `→` qui plafonnerait une page trop tot laisserait la derniere page
    inatteignable **sans faire rougir** le test positif ci-dessus, qui pose le
    rang au lieu de l'atteindre. On compare donc deux ENSEMBLES : ce que le
    clavier atteint, et ce que la derivation produit.
    """
    ecran = em.EcranManuel()
    derivees = [page.lignes for page in ecran.pages()]
    atteintes = [ecran.composer()]
    for _ in range(len(derivees) * 2):
        ecran.traiter("right")
        courante = ecran.composer()
        if tuple(courante) not in {tuple(page) for page in atteintes}:
            atteintes.append(courante)
    vues = {tuple(page) for page in atteintes}
    attendues = {tuple(page) for page in derivees}
    assert vues == attendues, len(vues ^ attendues)
    # Et le retour : `←` ramene jusqu'a la premiere page, sans la depasser.
    for _ in range(len(derivees) * 2):
        ecran.traiter("left")
    assert ecran.rang_de_page == 0, ecran.rang_de_page


@pytest.mark.parametrize("touche", ["down", "up", "space", "tab", "n", "p"])
def test_AC2_3_aucune_touche_NON_ANNONCEE_n_agit(touche):
    """« Une touche non annoncee qui agit est aussi trompeuse qu'une touche
    annoncee qui n'agit pas » -- l'autre moitie du finding `I8`."""
    ecran = ecran_du_corpus()
    ecran.rang_de_page = 1
    assert ecran.traiter(touche) is False, touche
    assert ecran.rang_de_page == 1


# ===========================================================================
# C3 -- la confrontation BORNEE aux maquettes `T1-2` et `T1-1`
# ===========================================================================

def grille_de_maquette(nom: str) -> list[str]:
    """Les 24 lignes de la grille d'une maquette, notes manuscrites exclues."""
    chemin = MAQUETTES / nom
    lignes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")
    return lignes[:jetons.HAUTEUR_PLANCHER]


def contenu_de_la_ligne(ligne: str) -> str:
    """Ce qu'une ligne de maquette porte a l'interieur de son cadre."""
    return ligne[2:-2].rstrip() if ligne.startswith("│") else ""


#: Les quatre zones de la grille confrontees a `T1-2` : le bandeau, les
#: dix-sept lignes du corps, la ligne d'etat, la ligne de raccourcis. Les
#: quatre lignes de cadre n'en sont pas -- elles appartiennent a la coque et
#: `test_repli_ascii.py` les mesure deja.
RANGS_DE_LA_GRILLE = [1] + list(range(3, 20)) + [21, 22]

#: Le rang de la zone du BANDEAU dans la grille confrontee, et celui de la
#: ligne de raccourcis. Ce sont des **zones**, pas du contenu : DESIGN.md les
#: fixe pour tous les ecrans, et elles ne bougent pas quand la maquette change
#: d'entree.
RANG_DU_BANDEAU = 0
RANG_DE_LA_LIGNE_D_ETAT = len(RANGS_DE_LA_GRILLE) - 2
RANG_DE_LA_LIGNE_DE_RACCOURCIS = len(RANGS_DE_LA_GRILLE) - 1


def contenu_de_T1_2() -> list[str]:
    """Les vingt lignes de contenu de `T1-2`, dans l'ordre de la grille."""
    grille = grille_de_maquette("T1-2-manuel-raccourcis.txt")
    return [contenu_de_la_ligne(grille[rang]) for rang in RANGS_DE_LA_GRILLE]


def rang_de_l_OUVREUR_dans_T1_2(ouvreur: str) -> int:
    """Le rang de la ligne de `T1-2` qui ouvre `ouvreur`, **CHERCHE**.

    **Un rang de maquette ne s'ecrit jamais en litteral dans ce banc**, et la
    lecon est mesuree plutot que theorique. Le 2026-09-05, `EPIC11-ARB-141` a
    retire la ligne `e   éditer les noms produits` de `T1-2` -- correction faite
    a la source, comme `EPIC11-ARB-142` l'exige. **Cinq bancs ont rougi**, et
    tous les cinq pour la meme raison : ils encodaient l'indice du jour. Aucun
    des seize bancs du lot voisin, qui n'en encodait aucun, n'a bouge.

    Un rang ecrit a la main mesure donc la **mise en page** de la maquette, pas
    l'ecart qu'il pretend borner -- et il rougit exactement quand la maquette
    est corrigee, c'est-a-dire au moment ou l'on a le moins besoin d'un faux
    rouge.
    """
    contenu = contenu_de_T1_2()
    rangs = [rang for rang, ligne in enumerate(contenu)
             if ligne.strip().split("  ")[0].strip() == ouvreur
             and ligne.startswith(" " * em.COLONNE_DE_L_OUVREUR)]
    assert len(rangs) == 1, (
        f"`T1-2` porte {len(rangs)} ligne(s) ouvrant {ouvreur!r} : "
        f"la mesure ne sait plus laquelle designer")
    return rangs[0]


def rangs_des_RACCOURCIS_de_T1_2() -> list[int]:
    """Tous les rangs de `T1-2` qui ouvrent un raccourci, **derives**.

    Une ligne de raccourci est celle qui laisse blanc jusqu'a
    `COLONNE_DE_L_OUVREUR` exclu et ecrit juste apres -- la meme lecture que le
    dessin. Titres de bloc (indentes de deux colonnes) et respirations en sont
    exclus sans qu'on ait a les nommer.
    """
    contenu = contenu_de_T1_2()
    rangs = [rang for rang, ligne in enumerate(contenu)
             if ligne[:em.COLONNE_DE_L_OUVREUR].strip() == ""
             and ligne[em.COLONNE_DE_L_OUVREUR:em.COLONNE_DU_LIBELLE].strip()]
    assert len(rangs) >= 5, (
        "`T1-2` ne porte presque plus de raccourci : la confrontation ne "
        f"mesurerait plus rien ({rangs})")
    return rangs


def rangs_qui_COINCIDENT_avec_T1_2(contenu: list[str],
                                   corps_peint: int) -> list[int]:
    """Les rangs ou le rendu **doit** reproduire la maquette, **DERIVES**.

    Remplace, le 2026-09-05, la liste litterale `RANGS_DIVERGENTS_DE_T1_2`
    (« 4 a 16, 18, 19 »), qui a rougi au premier retrait d'une entree de la
    maquette. L'assertion de l'AC 4.1 reste une **egalite exacte** -- « les
    lignes divergentes sont listees explicitement, jamais tues » : ce qui
    change est que la liste se **calcule** de la maquette au lieu de figer sa
    mise en page du jour.

    Trois familles, et ce sont les trois seules :

    * le **bandeau** -- il coincide au caractere pres, cardinal de pages
      compris, depuis le lot D. C'est un des deux ecarts que ce lot a fermes
      sans les viser ;
    * le **groupe de titre du bloc « partout »** -- sa respiration, son titre,
      sa respiration. Le rang du titre est **cherche** dans la maquette, et le
      produit ouvre sa page 1 sur le meme groupe ;
    * les **respirations de queue** -- les rangs du corps que le produit ne
      peint pas (sa page est plus courte que la zone) et ou la maquette est
      vide elle aussi. Le cardinal `corps_peint` vient du **produit**, pas
      d'une coincidence constatee.

    Tout le reste diverge. En particulier la **ligne d'etat**, que `T1-2`
    laisse vide et ou `EPIC11-ARB-56` pose une mesure, et la **ligne de
    raccourcis**, qui porte `Q quitter` (ecart 6 de l'AC 4.2).

    **Ce que cette derivation NE dit pas, dit plutot que tu** : elle ne fige
    plus le CARDINAL des rangs divergents -- quinze avant le retrait du
    2026-09-05, quatorze apres. Ce cardinal etait une propriete de la mise en
    page de la maquette, pas de l'ecart ; le borner revenait a interdire a
    Egan de corriger sa propre maquette sans faire rougir un banc.
    """
    titre = "  " + em.TITRE_DU_BLOC_PARTOUT
    rangs_du_titre = [rang for rang, ligne in enumerate(contenu)
                      if ligne == titre]
    assert len(rangs_du_titre) == 1, (titre, rangs_du_titre)
    rang_du_titre = rangs_du_titre[0]
    assert contenu[rang_du_titre - 1] == "" and contenu[rang_du_titre + 1] == "", (
        "le titre du bloc « partout » n'est plus encadre de ses respirations "
        "dans `T1-2` : le groupe que le produit reproduit n'existe plus")
    queue = [rang for rang in range(RANG_DU_BANDEAU + 1 + corps_peint,
                                    RANG_DE_LA_LIGNE_D_ETAT)
             if contenu[rang] == ""]
    return sorted({RANG_DU_BANDEAU, rang_du_titre - 1, rang_du_titre,
                   rang_du_titre + 1} | set(queue))


def zones_rendues(ecran: em.EcranManuel, ascii_seul: bool = False) -> list[str]:
    """Les memes quatre zones, rendues par l'ecran, dans le meme ordre."""
    contexte = Contexte("projet_demo", em.TITRE_DU_MANUEL,
                        ecran.objet_du_bandeau())
    bandeau = contexte.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
    raccourcis = (jetons.replier_ascii(ecran.raccourcis) if ascii_seul
                  else ecran.raccourcis)
    lignes = ([bandeau] + ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
              + [ecran.ligne_d_etat(ascii_seul), raccourcis])
    return [ligne.rstrip() for ligne in lignes]


def zones_completees(ecran: em.EcranManuel,
                     ascii_seul: bool = False) -> list[str]:
    """Les memes zones, le corps **COMPLETE a la hauteur de la zone centrale**.

    Ce n'est pas un arrangement de test : une page qui ne remplit pas la zone
    laisse le reste du cadre en blanc a l'ecran, et c'est exactement ce que ces
    lignes vides representent. Seule la confrontation a la maquette en a
    besoin -- elle compare deux grilles de meme hauteur --, et les autres
    mesures continuent de lire ce que l'ecran peint reellement.

    **Ajoute au lot D (2026-09-03), et le motif est une coincidence qui a
    cesse.** La hauteur d'une page **depend du contenu** : retirer le module du
    manuel de sa propre derivation a fait passer la premiere page de dix-sept
    lignes de corps a quinze. Sans ce complement, `zip` tronquait par le bas --
    la confrontation cessait de mesurer ses dernieres lignes au moment precis
    ou elles changeaient --, et l'assertion de longueur, verte par coincidence
    depuis le lot C, rougissait sans qu'aucun ecart de DESSIN ait bouge.
    """
    zones = zones_rendues(ecran, ascii_seul)
    corps = zones[1:-2]
    assert len(corps) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, (
        "une page deborde la zone centrale : `textual` la couperait en "
        f"silence par le bas (defaut `I1`) -- {len(corps)} lignes")
    complement = [""] * (jetons.HAUTEUR_CENTRE_AU_PLANCHER - len(corps))
    return zones[:1] + corps + complement + zones[-2:]


def test_C3_le_manuel_est_confronte_a_T1_2_LIGNE_A_LIGNE_et_l_ecart_est_LISTE():
    """AC 4.1 -- « borner l'ecart est ce qui l'empeche de grandir ».

    La comparaison porte sur les vingt lignes de contenu de la grille, au
    caractere pres, et les rangs divergents sont **listes explicitement** :
    une divergence de plus fait rougir ce test, pas une revue.

    **Ce test est volontairement fragile, et c'est son role** : il rougit des
    qu'une ligne de raccourcis change quelque part dans le paquet, parce que
    le manuel est derive du paquet entier. Le remede n'est jamais d'assouplir
    l'assertion, c'est de relire la liste.

    La confrontation se fait en UTF-8 seul : la maquette est ecrite en UTF-8,
    et la confronter au repli comparerait deux alphabets. Le repli, lui, est
    mesure par le budget de largeur ci-dessus, dans les deux regimes.
    """
    maquette = contenu_de_T1_2()
    ecran = em.EcranManuel()
    rendu = zones_completees(ecran)
    assert len(rendu) == len(maquette), (len(rendu), len(maquette))

    coincidents = rangs_qui_COINCIDENT_avec_T1_2(
        maquette, len(ecran.composer(jetons.LARGEUR_PLANCHER)))
    attendus = [rang for rang in range(len(maquette))
                if rang not in coincidents]
    divergentes = [rang for rang, (a, b) in enumerate(zip(rendu, maquette))
                   if a != b]
    assert divergentes == attendus, [
        (rang, rendu[rang], maquette[rang])
        for rang in sorted(set(divergentes) ^ set(attendus))]
    # Le volet symetrique : les lignes qui COINCIDENT sont bien celles qu'on
    # croit. Sans lui, un rendu entierement vide serait « borne ».
    groupe = [rang for rang in coincidents if rang != RANG_DU_BANDEAU][:3]
    assert [maquette[rang] for rang in groupe] == [
        "", "  " + em.TITRE_DU_BLOC_PARTOUT, ""], groupe
    # **Et aucune ligne de RACCOURCI de la maquette n'est reproduite**, ou que
    # ce soit dans le rendu. C'est la moitie que la liste des rangs ne disait
    # pas : elle bornait un ecart de POSITION, jamais un ecart de CONTENU.
    reproduites = [maquette[rang] for rang in rangs_des_RACCOURCIS_de_T1_2()
                   if maquette[rang] in rendu]
    assert reproduites == [], reproduites
    # Le bandeau coincide au caractere pres, cardinal de pages compris : c'est
    # le premier des deux ecarts fermes au lot D, et il ne serait pas mesure
    # par la seule liste des rangs divergents, qui dit ce qui differe et non ce
    # qui a cesse de differer.
    assert rendu[RANG_DU_BANDEAU] == maquette[RANG_DU_BANDEAU], rendu[0]
    assert "page 1 sur 3" in rendu[RANG_DU_BANDEAU], rendu[RANG_DU_BANDEAU]


def libelles_du_paquet(ouvreur: str) -> tuple[str, ...]:
    """Ce que le PRODUIT associe a un ouvreur, ou rien s'il ne l'annonce pas."""
    for entree_derivee in manuel.entrees_du_manuel():
        if entree_derivee.ouvreur == ouvreur:
            return entree_derivee.libelles
    return ()


def test_C3_ecart_1_de_T1_2_la_ligne_Tab_est_FAUSSE_sur_ses_TROIS_roles():
    """`EPIC11-ARB-48` a retire la completion ; `EPIC11-ARB-51` tranche que
    « `Tab` entre dans la saisie du chemin et en sort. **Rien d'autre** ».

    Mesure : la maquette annonce les trois roles, et le produit n'en porte
    aucun sous cette forme.
    """
    ligne = contenu_de_T1_2()[rang_de_l_OUVREUR_dans_T1_2("Tab")]
    assert ligne.split()[0] == "Tab", ligne
    assert "compléter un chemin" in ligne, ligne
    assert LA_COMPLETION_DE_CHEMIN.search(ligne), ligne
    portes = libelles_du_paquet("Tab")
    assert portes, "le produit n'annonce plus `Tab` : la mesure ne mesure rien"
    fautifs = [libelle for libelle in portes
               if LA_COMPLETION_DE_CHEMIN.search(libelle)]
    assert fautifs == [], fautifs


def ouvreurs_de_T1_2() -> set[str]:
    """Les ouvreurs que `T1-2` annonce, **lus** de la maquette."""
    contenu = contenu_de_T1_2()
    return {contenu[rang].strip().split("  ")[0].strip()
            for rang in rangs_des_RACCOURCIS_de_T1_2()}


#: Les deux lettres que `T1-2` ecrit en minuscule et que le produit porte en
#: majuscule (regle des majuscules, `coque.py:247-296`) -- ecarts 2 et 3 de
#: l'AC 4.2.
#:
#: **La liste est celle de l'AC, pas celle de la maquette du jour**, et elle se
#: **croise** avec ce que la maquette porte encore. Les deux sens comptent : une
#: lettre que l'AC ne nomme pas et que la maquette ecrirait en minuscule fait
#: rougir (l'ecart ne grandit pas) ; une lettre que l'AC nomme et qu'une
#: correction a la source retire cesse d'etre mesuree sans rougir (une
#: approbation corrigee ne casse pas un banc).
LETTRES_EN_MINUSCULE_NOMMEES_PAR_L_AC_4_2 = ("q", "a")

#: Les deux gestes que `T1-2` annonce et que le produit n'a plus -- ecarts 4 et
#: 5 de l'AC 4.2. `EPIC11-ARB-68` a remplace `e` par `Tab` et `Ctrl+R`.
#:
#: **`e` a ete RETIRE de la maquette a sa source le 2026-09-05**
#: (`EPIC11-ARB-141`, applique dans `_gen_b.py` puis regenere). L'ecart est donc
#: **ferme**, et la liste ci-dessous le garde nomme plutot que de l'effacer :
#: c'est l'AC qu'elle transcrit, et l'AC ne se reecrit pas depuis un banc.
GESTES_DISPARUS_NOMMES_PAR_L_AC_4_2 = ("e", "r")


def test_C3_les_lettres_EN_MINUSCULE_de_T1_2_sont_EXACTEMENT_celles_que_l_AC_nomme():
    """Le volet collectif des ecarts 2 et 3 : l'ecart ne grandit pas.

    Toute lettre isolee que la maquette ecrit en minuscule est un ecart de
    casse ; l'ensemble mesure doit tomber sur ce que l'AC 4.2 nomme, croise
    avec ce que la maquette porte encore.
    """
    minuscules = {ouvreur for ouvreur in ouvreurs_de_T1_2()
                  if len(ouvreur) == 1 and ouvreur.islower()}
    attendues = set(LETTRES_EN_MINUSCULE_NOMMEES_PAR_L_AC_4_2
                    + GESTES_DISPARUS_NOMMES_PAR_L_AC_4_2) & ouvreurs_de_T1_2()
    assert minuscules == attendues, sorted(minuscules ^ attendues)
    assert minuscules, "`T1-2` n'ecrit plus aucune minuscule : mesure vide"


@pytest.mark.parametrize("lettre", LETTRES_EN_MINUSCULE_NOMMEES_PAR_L_AC_4_2)
def test_C3_ecarts_2_et_3_de_T1_2_deux_lettres_en_MINUSCULE(lettre):
    """La regle des majuscules (`coque.py:247-296`) : `q quitter` s'ecrit
    `Q quitter`, `a ajouter` s'ecrit `A ajouter`.

    Mesure des deux cotes : la maquette porte la minuscule, et le produit
    porte la majuscule -- une assertion sur la seule maquette ne dirait pas
    laquelle des deux a raison.

    Si la maquette ne porte plus la lettre, l'ecart est **ferme a la source**
    et le test le dit : il verifie alors que le produit porte bien la
    majuscule, ce qui reste la moitie vraie de la mesure. Il ne se saute pas --
    un saut serait un trou, et c'est ce que la 11.8 a paye deux fois.
    """
    if lettre in ouvreurs_de_T1_2():
        ligne = contenu_de_T1_2()[rang_de_l_OUVREUR_dans_T1_2(lettre)]
        assert ligne.split()[0] == lettre, ligne
        assert libelles_du_paquet(lettre) == (), (
            f"le produit annoncerait la minuscule {lettre!r}")
    assert libelles_du_paquet(lettre.upper()), (
        f"le produit n'annonce pas {lettre.upper()!r} : la mesure est vide")


@pytest.mark.parametrize("lettre", GESTES_DISPARUS_NOMMES_PAR_L_AC_4_2)
def test_C3_ecarts_4_et_5_de_T1_2_deux_gestes_QUI_N_EXISTENT_PLUS(lettre):
    """`EPIC11-ARB-68` a remplace `e` par `Tab` et `Ctrl+R`.

    Mesure : **aucune ligne du paquet n'annonce ces lettres**, ni en
    minuscule ni en majuscule. `EPIC11-ARB-37` les cite comme illustration de
    ce qui manquait au manuel, pas comme contrat.

    La moitie « la maquette l'annonce encore » est **conditionnelle depuis le
    2026-09-05** : `e` a ete retire de `T1-2` a sa source par
    `EPIC11-ARB-141`, donc l'ecart est ferme de ce cote. La moitie « le produit
    ne l'annonce pas », elle, reste exigee des deux -- c'est elle qui dit que
    le geste n'existe plus, et elle ne depend pas de la maquette.
    """
    if lettre in ouvreurs_de_T1_2():
        ligne = contenu_de_T1_2()[rang_de_l_OUVREUR_dans_T1_2(lettre)]
        assert ligne.split()[0] == lettre, ligne
    lettres = manuel.lettres_du_manuel()
    assert lettre not in lettres and lettre.upper() not in lettres, sorted(
        lettres)
    # Volet symetrique : la derivation VOIT bien des lettres. Deux inclusions
    # entre deux ensembles vides seraient vertes.
    assert {"A", "O", "Q", "X"} <= set(lettres), sorted(lettres)


def test_C3_ecart_6_de_T1_2_la_ligne_de_raccourcis_porte_Q_quitter():
    """`EPIC11-ARB-140` le retire des passages ; le manuel est un passage.

    C'est l'ecart que l'AC 5.7 rend NON NEGOCIABLE : la ligne du manuel
    portant `Q quitter`, `test_arb140_passages_sans_q_quitter.py:96` rougirait.
    """
    ligne = contenu_de_T1_2()[RANG_DE_LA_LIGNE_DE_RACCOURCIS]
    assert "Q quitter" in ligne, ligne
    assert "Q quitter" not in em.RACCOURCIS_MANUEL, em.RACCOURCIS_MANUEL
    # `EPIC11-ARB-60` : chaque fleche garde son sens NOMME.
    assert "→ page suivante" in ligne and "→ page suivante" in em.RACCOURCIS_MANUEL
    assert "naviguer" not in em.RACCOURCIS_MANUEL


def test_C3_les_TROIS_ecarts_de_T1_1_sont_NOMMES_et_MESURES():
    """AC 1.6 -- `T1-1` dit autre chose que l'AC 1.2, et l'ecart se borne.

    Les trois, mesures sur la maquette et confrontes au produit livre en 11.5
    (`atelier_scan_completion`, le SEUL etage 1 du depot) :

    1. `T1-1` dessine un **panneau defilant** (`↑↓ faire défiler`,
       `Échap fermer`), la ou le produit fait une **bascule de tete** a
       cardinal de lignes constant -- `EPIC11-ARB-198` : generaliser le livre,
       ne pas le reecrire ;
    2. elle ouvre un **troisieme etat** que le dispatch de l'AC 1.4 ne couvre
       pas : aide ouverte, `F1` menerait au manuel (`F1 manuel complet`) ;
    3. sa **ligne d'etat est vide**, ce qu'`EPIC11-ARB-56` refuse.

    `T1-1` **ne se retouche pas** (`EPIC11-ARB-142`) : l'ecart attend Egan.
    """
    grille = grille_de_maquette("T1-1-aide-champ.txt")
    raccourcis = contenu_de_la_ligne(grille[22])
    etat = contenu_de_la_ligne(grille[21])

    # 1 -- le panneau defilant, contre la bascule de tete du produit.
    assert "↑↓ faire défiler" in raccourcis, raccourcis
    assert "défiler" not in atelier_scan_completion.RACCOURCIS_COMPLETION

    # 2 -- le troisieme etat, que le produit ne rend pas.
    assert "F1 manuel complet" in raccourcis, raccourcis
    assert "F1 où lire ce champ" in atelier_scan_completion.RACCOURCIS_COMPLETION

    # 3 -- la ligne d'etat vide, contre `EPIC11-ARB-56`.
    assert etat == "", repr(etat)
    assert em.EcranManuel().ligne_d_etat().strip(), (
        "le manuel, lui, ne laisse pas sa ligne d'etat vide")


# ===========================================================================
# C4 -- les DEUX frontieres negatives, chacune avec son volet de MORSURE
# ===========================================================================

#: Les quatre termes de conception qu'`EPIC11-ARB-28` interdit a l'ecran :
#: « ne s'affichent **jamais** a l'ecran », et « une occurrence de ce mot dans
#: une maquette est **un defaut de revue** ». `EPIC11-ARB-37` le redit pour le
#: manuel nommement : « notre vocabulaire de conception n'a pas sa place dans
#: l'interface ».
TERMES_DE_CONCEPTION = ("parcours a part", "parcours à part", "palier",
                        "feuille cli", "point de jugement")


def termes_trouves(texte: str) -> list[str]:
    """Ceux des quatre termes que `texte` porte, insensible a la casse."""
    return [terme for terme in TERMES_DE_CONCEPTION
            if terme in texte.lower()]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C4_le_RENDU_du_manuel_ne_porte_AUCUN_terme_de_conception(ascii_seul):
    """AC 2.2, premiere surface : ce que l'operateur LIT.

    Toutes les pages, pas la premiere seule : un terme glisse dans un libelle
    de la derniere page ne se verrait pas autrement.
    """
    ecran = em.EcranManuel()
    rendu = "\n".join(
        [ligne for page in ecran.pages(ascii_seul=ascii_seul)
         for ligne in page.lignes]
        + [ecran.ligne_d_etat(ascii_seul), ecran.raccourcis,
           em.TITRE_DU_BLOC_PARTOUT, em.TITRE_DU_BLOC_PROPRES])
    assert rendu.strip(), "le rendu est vide : la frontiere ne mesure rien"
    assert termes_trouves(rendu) == [], termes_trouves(rendu)


def test_C4_le_MODULE_n_ecrit_aucun_terme_de_conception_en_LITTERAL():
    """AC 2.2, seconde surface : ce que le module ECRIT.

    Docstrings exclus -- la prose qui explique pourquoi le manuel ne dit pas
    « palier » porte forcement le mot, et un grep de texte y mordrait puis se
    ferait affaiblir a la premiere phrase (modele
    `test_atelier_exports_lot.py:592-616`).
    """
    fautives = [valeur for valeur in chaines_de_code(MODULE)
                if termes_trouves(valeur)]
    assert fautives == [], fautives


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C4_la_frontiere_des_termes_de_conception_MORD(ascii_seul):
    """Le volet sans lequel les deux precedents sont verts sur tout.

    Corpus a **trois** lignes distinguables, la fautive **au milieu** : on
    mesure a la fois que la frontiere la trouve et qu'elle ne trouve qu'elle.
    Modele : `test_frontiere_cli.py:254`.
    """
    corpus = {
        "premiere": "     Tab          champ suivant · explorateur",
        "AU MILIEU": "     Échap        remonter d'un palier, sans rien écrire",
        "derniere": "     F1           aide · où lire ce champ",
    }
    if ascii_seul:
        corpus = {cle: jetons.replier_ascii(valeur)
                  for cle, valeur in corpus.items()}
    trouves = {cle: termes_trouves(valeur) for cle, valeur in corpus.items()}
    assert trouves["AU MILIEU"] == ["palier"], trouves
    assert trouves["premiere"] == [] and trouves["derniere"] == [], trouves


#: **La COMPLETION DE CHEMIN, la chose et non le mot** (`EPIC11-ARB-127`,
#: verbatim : « on resserre la frontiere sur la chose -- on ne renomme pas la
#: chose pour la faire passer sous la frontiere »). Le verbe seul attraperait
#: « Compléter le QR », que `EPIC11-ARB-29` a choisi apres discussion ; c'est
#: l'adjacence a un **chemin** qui fait la chose qu'`EPIC11-ARB-48` a retiree.
LA_COMPLETION_DE_CHEMIN = re.compile(
    r"compl[eé]t\w*[^.\n·]{0,24}chemins?", re.IGNORECASE)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C4_ni_le_RENDU_ni_le_MODULE_ne_portent_la_COMPLETION_DE_CHEMIN(
        ascii_seul):
    """AC 4.4 -- `EPIC11-ARB-48` : « il n'y a plus de completion a rendre
    disponible, l'explorateur de la story 11.2b l'a remplacee partout ».

    Les deux surfaces, comme pour les termes de conception : le rendu, et le
    litteral du module.
    """
    ecran = em.EcranManuel()
    rendu = "\n".join([ligne for page in ecran.pages(ascii_seul=ascii_seul)
                       for ligne in page.lignes]
                      + [ecran.ligne_d_etat(ascii_seul), ecran.raccourcis])
    assert rendu.strip(), "le rendu est vide : la frontiere ne mesure rien"
    assert LA_COMPLETION_DE_CHEMIN.search(rendu) is None, rendu
    fautives = [valeur for valeur in chaines_de_code(MODULE)
                if LA_COMPLETION_DE_CHEMIN.search(valeur)]
    assert fautives == [], fautives


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C4_la_frontiere_de_la_COMPLETION_DE_CHEMIN_MORD(ascii_seul):
    """Premier sens du volet symetrique : elle attrape bien la chose.

    Corpus a trois lignes, la fautive **au milieu** -- c'est exactement la
    ligne que `T1-2` dessine et que le produit ne porte plus.
    """
    corpus = {
        "premiere": "     ⏎            valider · ouvrir",
        "AU MILIEU": "     Tab          champ suivant · compléter un chemin",
        "derniere": "     Échap        retour · ateliers",
    }
    if ascii_seul:
        corpus = {cle: jetons.replier_ascii(valeur)
                  for cle, valeur in corpus.items()}
    mordus = {cle for cle, valeur in corpus.items()
              if LA_COMPLETION_DE_CHEMIN.search(valeur)}
    assert mordus == {"AU MILIEU"}, sorted(mordus)


def test_C4_la_frontiere_de_la_COMPLETION_DE_CHEMIN_NE_MORD_PAS_sur_le_SCAN():
    """Second sens, et c'est lui qui garde la frontiere honnete.

    `EPIC11-ARB-127` a resserre la frontiere **parce qu'elle attrapait le
    vocabulaire du Scan** : « compléter un chemin qu'on saisit » et
    « compléter l'identité d'une planche dont le QR n'a pas été lu » sont deux
    gestes sans rapport qui portent le meme mot. Les deux phrases sont prises
    **par reference au produit**, jamais recopiees : une recopie divergerait au
    premier ajustement du libelle.
    """
    du_scan = (atelier_scan_rapport.LIBELLE_COMPLETER_LE_QR,
               atelier_scan_completion.TITRE,
               "le contrat de complétion a gagné un champ")
    mordus = [phrase for phrase in du_scan
              if LA_COMPLETION_DE_CHEMIN.search(phrase)]
    assert mordus == [], mordus
    # Volet du volet : les phrases du Scan portent bien le verbe, sans quoi ce
    # test serait vert sur un corpus qui n'a rien a voir.
    assert all(re.search(r"ompl[eé]t", phrase, re.IGNORECASE)
               for phrase in du_scan), du_scan


# ===========================================================================
# AC 3.5, AC 5.2, AC 5.3 -- la liaison depuis la coque
# ===========================================================================

def test_AC3_5_la_coque_MONTE_puis_le_manuel_S_OUVRE(banc):
    """« Un test monte `CoqueTui` PUIS ouvre le manuel, dans cet ordre --
    c'est la seule forme qui aurait attrape le cycle. »

    Vingt-cinq modules du paquet importent `coque`, et `tui/manuel.py` balaie
    le paquet a l'appel : un import du manuel au niveau de `coque` rendrait
    l'import circulaire et la TUI ne demarrerait plus.
    """
    async def scenario(pilote):
        await pilote.press("f1")
        await pilote.pause()
        ecran = pilote.app.screen
        return type(ecran).__name__, ecran.titre, ecran.raccourcis

    nom, titre, raccourcis = banc(coque_a_deux_paliers(), scenario)
    assert nom == "EcranManuel", nom
    assert titre == em.TITRE_DU_MANUEL
    assert raccourcis == em.RACCOURCIS_MANUEL


def test_AC3_5_coque_n_importe_le_manuel_QUE_dans_le_corps_de_action_aide():
    """La mesure est faite a l'AST, jamais au texte : le docstring
    d'`action_aide` explique justement pourquoi l'import est dans le corps,
    donc il porte le mot -- un grep y mordrait.
    """
    arbre = ast.parse(MODULE_DE_LA_COQUE.read_text(encoding="utf-8"))
    au_niveau_module = [noeud for noeud in arbre.body
                        if isinstance(noeud, (ast.Import, ast.ImportFrom))]
    fautifs = [noeud for noeud in au_niveau_module
               if any("ecran_manuel" in (alias.name or "")
                      for alias in noeud.names)
               or "ecran_manuel" in (getattr(noeud, "module", "") or "")]
    assert fautifs == [], [ast.dump(noeud) for noeud in fautifs]
    # Volet symetrique : l'import EXISTE bien, quelque part dans un corps.
    dans_un_corps = [noeud for noeud in ast.walk(arbre)
                     if isinstance(noeud, ast.ImportFrom)
                     and "ecran_manuel" in (noeud.module or "")]
    assert dans_un_corps, "aucun import du manuel : la coque ne l'ouvre pas"


def test_AC5_3_la_garde_anti_empilement_vise_le_MANUEL(banc):
    """AC 5.3 -- la garde d'`action_aide` change de cible avec `F1`.

    **Cinq pressions et non une** : la garde ne se demasque pas sur une seule.
    Restee sur `EcranPasEncore`, elle aurait protege un ecran que `F1`
    n'ouvre plus, et cinq `F1` auraient empile cinq manuels.
    """
    async def scenario(pilote):
        for _ in range(5):
            await pilote.press("f1")
            await pilote.pause()
        return (pilote.app.rang, pilote.app.passages_empiles,
                type(pilote.app.screen).__name__)

    rang, empiles, nom = banc(coque_a_deux_paliers(), scenario)
    assert empiles == 1, "le manuel s'est empile sur lui-meme"
    assert rang == 0, "`F1` fait croire qu'on a descendu un palier"
    assert nom == "EcranManuel", nom


def test_AC5_2_EcranPasEncore_n_est_PAS_supprime_et_descendre_s_en_sert(banc):
    """AC 5.2 -- `descendre()` l'emploie encore pour « la suite de X ».

    Le supprimer parce que `F1` ne l'ouvre plus aurait casse le dernier
    palier : `⏎` y menerait a une touche qui ne fait rien et ne dit rien.
    """
    async def scenario(pilote):
        await pilote.press("enter")     # palier 1
        await pilote.pause()
        await pilote.press("enter")     # il n'y a rien en dessous
        await pilote.pause()
        ecran = pilote.app.screen
        return type(ecran).__name__, "\n".join(ecran.lignes())

    nom, texte = banc(coque_a_deux_paliers(), scenario)
    assert nom == EcranPasEncore.__name__, nom
    assert "n'existe pas encore" in texte, texte


def test_le_balayage_du_paquet_VOIT_le_manuel():
    """Volet symetrique de toutes les gardes parametrees sur le paquet.

    Une garde qui ne verrait pas la classe neuve serait verte sans rien tenir
    -- c'est le motif de `test_repli_ascii.py:118`.
    """
    classes = manuel.classes_d_ecran()
    assert len(classes) >= 8, len(classes)
    assert "mixed_media_utility.tui.ecran_manuel.EcranManuel" in classes, sorted(
        nom for nom in classes if "manuel" in nom)


def test_l_ecran_se_MONTE_et_PEINT_ses_quatre_zones_sans_terminal(banc):
    """Le contrat du banc headless, et il porte les quatre zones de la grille.

    Un ecran qui compose bien mais ne monte pas est un ecran qui n'existe
    pas -- et `textual` coupe par le bas **en silence**, si bien qu'un corps
    trop haut ne se voit qu'ici. Les quatre zones ensemble, parce que
    :func:`zones_rendues` fait un raccourci -- il compose le bandeau lui-meme
    plutot que de le lire de l'ecran monte --, et que ce test est ce qui
    epingle ce raccourci a la realite.
    """
    ecran = em.EcranManuel()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        lu = lambda cible: jetons.texte_affiche(
            str(ecran.query_one(cible).content))
        return (lu("#bandeau"), lu(f"#{em.EcranManuel.ID_DU_CORPS}"),
                lu("#etat"), lu("#raccourcis"))

    bandeau, corps, etat, raccourcis = banc(coque_a_deux_paliers(), scenario)
    attendu = zones_rendues(ecran)
    assert bandeau.rstrip() == attendu[0], (bandeau, attendu[0])
    assert [ligne.rstrip() for ligne in corps.split(chr(10))] == attendu[1:-2]
    assert etat.rstrip() == attendu[-2], (etat, attendu[-2])
    assert raccourcis.rstrip() == attendu[-1], (raccourcis, attendu[-1])


def test_le_manuel_ne_fait_PAS_entrer_ses_fleches_dans_le_bloc_PARTOUT():
    """**L'effet de retour que le lot C a constate, et que le lot D a tranche.**

    Le manuel est derive du paquet, et sa propre ligne de raccourcis est une
    ligne du paquet : `→` et `←`, annonces par le seul explorateur
    d'`ecran_projet`, se sont trouves annonces par **deux** modules des que le
    lot C a livre `RACCOURCIS_MANUEL`. Le critere du lot A -- « un ouvreur vaut
    partout quand ses ecrans porteurs s'etendent sur plus d'un atelier » -- les
    faisait basculer vers « partout », et contredisait
    `test_manuel_derive.test_les_DEUX_blocs_...`, qui epingle cet ensemble a
    SEPT ouvreurs.

    Le lot C a **ecrit le constat plutot que de le laisser a une revue**, en
    nommant les deux issues possibles et en les mettant hors de son perimetre.
    **Le lot D a pris la premiere** : la derivation exclut le module du manuel
    de son propre comptage (`manuel.MODULE_DU_MANUEL`). Le motif n'est pas le
    cardinal, c'est la verite de l'annonce -- `→` et `←` ne marchent PAS
    partout, ils tournent les pages du manuel, et `T1-2` ne les porte dans
    aucun de ses deux blocs alors qu'elle les annonce dans sa ligne de pied.

    Ce test garde la trace de l'effet **par son autre bout** : la mesure de
    l'exclusion elle-meme, avec ses volets de morsure, vit dans
    `test_manuel_derive.py` -- deux redactions divergeraient. Ici on tient le
    seul fait qui appartienne a l'ecran : les deux fleches restent **dans** le
    manuel, du cote « propre a un ecran », et l'ecran les rend.
    """
    par_ouvreur = {e.ouvreur: e for e in manuel.entrees_du_manuel()}
    for fleche in ("→", "←"):
        assert fleche in par_ouvreur, f"{fleche} a disparu du manuel"
        assert not par_ouvreur[fleche].partout, par_ouvreur[fleche].ateliers
        assert par_ouvreur[fleche].ateliers == ("ecran_projet",), (
            par_ouvreur[fleche].ateliers)
    rendu = "\n".join(ligne for page in em.EcranManuel().pages()
                       for ligne in page.lignes)
    assert "→" in rendu and "←" in rendu, "l'ecran ne rend plus les fleches"


# ===========================================================================
# C5 -- un bloc GARDE son titre quand il traverse une page
#       (defaut `F3` de la couche 1 / `F5` de la couche 3, 2026-09-03)
# ===========================================================================
#
# **Le defaut, et il mordait sur le paquet REEL.** `pages_du_manuel` emettait
# le titre d'un bloc **une seule fois**, au changement de `partout`, et coupait
# entre groupes sans jamais regarder ce que le groupe quitte. Deux regimes en
# sortaient, tous deux payes :
#
# * **(a)** la page 2 s'ouvrait au milieu du bloc « partout » et la page 3
#   entierement dans le bloc « propres », **sans titre ni l'une ni l'autre**.
#   L'operateur qui arrive par `→` voyait deux raccourcis qu'il ne pouvait
#   rattacher a rien ;
# * **(b)** un titre pouvait rester **seul en bas** d'une page, son bloc
#   commencant sur la suivante. Le paquet reel etait a une ligne de ce regime.
#
# Le docstring de `groupes_du_manuel` posait pourtant l'argument exact qui
# manquait -- « un ouvreur dont les libelles se retrouveraient a cheval sur
# deux pages serait illisible sur les deux » : c'est vrai d'un **bloc** autant
# que d'un ouvreur.

def _titre_de_bloc(partout: bool, ascii_seul: bool = False) -> str:
    """La ligne de titre du bloc, **telle que le module l'ecrit**."""
    return em.ligne_de_titre(
        em.TITRE_DU_BLOC_PARTOUT if partout else em.TITRE_DU_BLOC_PROPRES,
        ascii_seul)


def _lignes_pleines(page: em.Page) -> list[str]:
    """Les lignes non vides d'une page -- les respirations ne titrent rien."""
    return [ligne for ligne in page.lignes if ligne.strip()]


def corpus_a_deux_blocs() -> tuple[manuel.Entree, ...]:
    """Vingt « partout » puis vingt « propres », **toutes distinguables**.

    Le corpus de la pagination (`corpus_a_trois_pages`) est **entierement**
    `partout=True` : il ne produit qu'un bloc, si bien que la pagination du
    second titre n'etait jouee par aucun test -- c'est ce qui a rendu le defaut
    `F3` invisible a 584 tests verts. Celui-ci porte les deux blocs et les fait
    traverser plusieurs pages, dans les deux sens.

    Regle des fabriques : ouvreurs et libelles **tous differents** ; cible en
    **tete** (bloc « partout »), au **milieu** (la charniere des deux blocs) et
    en **queue** (bloc « propres »), et les positions se verifient sur les
    pages que le CODE rend.
    """
    partout = [entree(f"P{rang:02d}", f"geste partout {rang}")
               for rang in range(20)]
    propres = [entree(f"S{rang:02d}", f"geste propre {rang}", partout=False)
               for rang in range(20)]
    partout[0] = entree(OUVREUR_DU_PREMIER_BORD, "le tout premier geste")
    propres[-1] = entree(OUVREUR_DU_DERNIER_BORD, "le tout dernier geste",
                         partout=False)
    return tuple(partout + propres)


def corpus_du_titre_ORPHELIN() -> tuple[manuel.Entree, ...]:
    """Le corpus temoin du regime **(b)** : onze « partout » puis trois
    « propres ».

    Les cardinaux ne sont pas choisis au hasard -- ils sont ceux que la
    couche 1 a mesures : le groupe de titre du second bloc (trois lignes) y
    remplit la page **exactement**, si bien que `len(lignes) + len(groupe) >
    hauteur` l'acceptait et que son premier raccourci partait a la page
    suivante. Le paquet reel etait a **une ligne** de ce regime.
    """
    return tuple(
        [entree(f"P{rang:02d}", f"geste partout {rang}") for rang in range(11)]
        + [entree(f"S{rang:02d}", f"geste propre {rang}", partout=False)
           for rang in range(3)])


#: Les trois corpus confrontes aux deux proprietes : le paquet **reel** (c'est
#: lui qui portait le defaut), les deux blocs, et le titre orphelin.
CORPUS_DE_PAGINATION = [
    pytest.param(None, id="paquet-reel"),
    pytest.param(corpus_a_deux_blocs, id="deux-blocs"),
    pytest.param(corpus_du_titre_ORPHELIN, id="titre-orphelin"),
]


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("fabrique", CORPUS_DE_PAGINATION)
def test_C5_toute_page_PORTE_le_titre_du_bloc_qu_elle_continue(fabrique,
                                                               ascii_seul):
    """Regime **(a)** : une page qui continue un bloc **rappelle son titre**.

    La confrontation porte sur **toutes** les pages et non sur la seule
    premiere : c'est exactement ce que le decoupage d'origine faisait -- seule
    la premiere page etait confrontee a quoi que ce soit, et les mutants `M27`,
    `M28` et `M29` survivaient tous les trois pour cette raison.

    Le titre attendu est celui du bloc du **premier ouvreur de la page**, lu
    des entrees : le recopier ici en ferait une seconde source de verite.
    """
    entrees = fabrique() if fabrique is not None else manuel.entrees_du_manuel()
    bloc_de = {e.ouvreur: e.partout for e in entrees}
    pages = em.pages_du_manuel(entrees, ascii_seul=ascii_seul)
    assert len(pages) >= 2, len(pages)  # anti-vacuite : il y a bien coupure
    sans_titre = []
    for rang, page in enumerate(pages):
        pleines = _lignes_pleines(page)
        assert pleines, (rang, page.lignes)
        assert page.ouvreurs, (rang, page.lignes)
        attendu = _titre_de_bloc(bloc_de[page.ouvreurs[0]], ascii_seul)
        if pleines[0] != attendu:
            sans_titre.append((rang, pleines[0], attendu))
    assert sans_titre == [], sans_titre


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("fabrique", CORPUS_DE_PAGINATION)
def test_C5_un_titre_de_bloc_n_est_JAMAIS_SEUL_en_bas_d_une_page(fabrique,
                                                                 ascii_seul):
    """Regime **(b)** : un titre n'est jamais la derniere ligne pleine d'une
    page.

    Un titre seul en bas de page annonce un bloc que la page ne montre pas :
    c'est un en-tete de tableau sans son tableau. Le corpus `titre-orphelin`
    est le temoin mesure du regime ; les deux autres verifient qu'on ne l'a pas
    ferme en le deplacant ailleurs.
    """
    entrees = fabrique() if fabrique is not None else manuel.entrees_du_manuel()
    titres = {_titre_de_bloc(True, ascii_seul), _titre_de_bloc(False, ascii_seul)}
    pages = em.pages_du_manuel(entrees, ascii_seul=ascii_seul)
    orphelins = [(rang, _lignes_pleines(page)[-1])
                 for rang, page in enumerate(pages)
                 if _lignes_pleines(page) and _lignes_pleines(page)[-1] in titres]
    assert orphelins == [], orphelins


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C5_le_titre_repris_est_le_MEME_mot_sans_suffixe_invente(ascii_seul):
    """Le rappel est **verbatim** : le meme groupe de trois lignes que
    l'original, respirations comprises.

    Un « (suite) » serait une decision de libelle, et elle appartient a Egan --
    pas au correctif. La mesure epingle donc l'egalite au caractere pres : le
    jour ou quelqu'un ajoute un suffixe, ce test rougit au lieu de laisser
    passer un second vocabulaire.
    """
    pages = em.pages_du_manuel(corpus_a_deux_blocs(), ascii_seul=ascii_seul)
    titres = {_titre_de_bloc(True, ascii_seul), _titre_de_bloc(False, ascii_seul)}
    rappels = [ligne for page in pages[1:] for ligne in page.lignes[:2]
               if ligne.strip()]
    assert rappels, [page.lignes[:2] for page in pages[1:]]
    assert set(rappels) <= titres, sorted(set(rappels) - titres)
    # Et la respiration qui encadre le titre est reprise elle aussi : le groupe
    # est le meme des deux cotes, sans quoi la page rappelee serait cadrée
    # autrement que la page qui ouvre le bloc.
    for page in pages[1:]:
        assert page.lignes[0] == "", page.lignes[:3]
        assert page.lignes[2] == "", page.lignes[:3]


def test_C5_la_fabrique_des_DEUX_BLOCS_tient_ce_que_la_REGLE_exige():
    """Regle des fabriques, verifiee sur la liste que le CODE parcourt.

    Cible en **tete** (page 1), au **milieu** (une page qui n'est ni la
    premiere ni la derniere) et en **queue** (derniere page). Une cible au
    milieu demasque un `find` qui rendrait le premier element ; elle ne
    demasque **pas** un balayage tronque, et c'est pourquoi les deux bords sont
    poses aussi (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03).
    """
    entrees = corpus_a_deux_blocs()
    pages = em.pages_du_manuel(entrees)
    assert len(pages) >= 3, [len(page.ouvreurs) for page in pages]
    assert OUVREUR_DU_PREMIER_BORD in pages[0].ouvreurs, pages[0].ouvreurs
    assert OUVREUR_DU_DERNIER_BORD in pages[-1].ouvreurs, pages[-1].ouvreurs
    # Les deux blocs sont bien traverses, et la charniere tombe au MILIEU du
    # decoupage : sans elle, la reprise du second titre ne serait pas jouee.
    bloc_de = {e.ouvreur: e.partout for e in entrees}
    melangees = [rang for rang, page in enumerate(pages)
                 if len({bloc_de[ouvreur] for ouvreur in page.ouvreurs}) == 2]
    assert melangees and 0 not in melangees, melangees
    assert melangees[-1] != len(pages) - 1, (melangees, len(pages))
    # Aucun ouvreur perdu ni double par la reprise des titres.
    pagines = [ouvreur for page in pages for ouvreur in page.ouvreurs]
    assert pagines == [e.ouvreur for e in entrees], (
        len(pagines), len(entrees))
    # Les libelles sont **distinguables** : un remplissage uniforme rendrait
    # vert un decoupage qui melangerait les pages.
    libelles = {e.libelles for e in entrees}
    assert len(libelles) == len(entrees), len(libelles)


# ===========================================================================
# C6 -- la ligne d'etat porte une MESURE, et cette mesure est le CARDINAL
#       D'OUVREURS de la page (`EPIC11-ARB-56`)
# ===========================================================================
#
# Lot E2 de la revue du 2026-09-03 -- couche 1 `F7` et couche 2 `F10`, le meme
# mutant sous deux numeros : `len(page.ouvreurs)` -> `len(page.lignes)` dans
# `mesure_de_la_page`. Reinjecte au HEAD de la branche de cloture le
# 2026-09-05, il **survivait encore** aux 323 tests des six bancs de la story.
#
# Ce qui ne le voyait pas : `test_C2_la_ligne_d_etat_porte_une_MESURE_et_aucune
# _touche` verifie que la ligne n'est pas vide, qu'elle porte **un** chiffre et
# qu'elle ne nomme aucune touche -- les trois interdits de l'arbitrage. Aucun
# ne dit **lequel**. Le test mesurait la forme, jamais la mesure, et sous le
# mutant la page 2 du paquet reel annonce « 17 raccourcis sur 16 », c'est-a-dire
# plus que le manuel entier n'en porte.
#
# **La confrontation ne relit PAS `page.ouvreurs`**, ce qui serait tautologique
# (politique 6.2 : « un test ecrit pour fermer un finding n'est clos que si le
# mutant reinjecte le fait rougir » -- et le faux vert de cette famille est
# endemique ici). Elle **recompte sur le dessin** : une ligne qui ouvre un
# raccourci est celle dont les `COLONNE_DE_L_OUVREUR` premieres colonnes sont
# blanches et dont la suivante ne l'est pas. Le produit compte la derivation,
# le banc compte la peinture ; les deux doivent tomber juste.

def _ouvreurs_PEINTS(page: em.Page) -> list[str]:
    """Les raccourcis qu'une page MONTRE, recomptes sur les lignes rendues.

    Seconde lecture **voulue**. Un titre de bloc s'indente de deux colonnes et
    non de cinq, une ligne de suite s'indente de `COLONNE_DU_LIBELLE` : seule
    une ligne d'ouvreur laisse blanc jusqu'a `COLONNE_DE_L_OUVREUR` exclu et
    ecrit juste apres.
    """
    return [ligne for ligne in page.lignes
            if ligne[:em.COLONNE_DE_L_OUVREUR].strip() == ""
            and ligne[em.COLONNE_DE_L_OUVREUR:em.COLONNE_DU_LIBELLE].strip()]


def _entree_HAUTE(ouvreur: str, lignes: int,
                  partout: bool = True) -> manuel.Entree:
    """Une entree dont le rendu s'enveloppe sur EXACTEMENT `lignes` lignes.

    Le cardinal de libelles n'est pas ecrit en dur : il **se cherche**, parce
    qu'il depend de la largeur de l'ouvreur, de la colonne du libelle et de la
    branche (`partout` enveloppe sur la largeur utile, `propre` sur la place
    laissee avant la colonne de l'atelier). Une formule ecrite ici serait une
    seconde implementation de l'enveloppement, qui divergerait au premier
    ajustement de colonne -- exactement ce que `CLAUDE.md` reproche a une
    valeur recopiee.

    Les libelles sont **tous differents** et portent le nom de l'ouvreur : un
    remplissage uniforme rendrait invisible toute permutation, ce que la regle
    des fabriques ferme depuis le mutant `M33` de la 5.6.
    """
    for cardinal in range(1, 80):
        candidate = entree(
            ouvreur, *[f"role {ouvreur}-{rang}" for rang in range(cardinal)],
            partout=partout)
        if len(em.lignes_d_une_entree(candidate)) == lignes:
            return candidate
    raise AssertionError(
        f"aucun cardinal de libelles ne rend {lignes} lignes pour {ouvreur!r} "
        f"(partout={partout}) : la fabrique ne peut plus produire le bord "
        "qu'elle est faite pour produire")


#: Le corpus de la MESURE : trois pages dont les cardinaux d'ouvreurs sont
#: **tous les trois differents** -- 14, 9 et 3 -- et **tous differents du
#: cardinal de lignes** de leur page. Les deux proprietes sont necessaires :
#: trois pages a cardinal egal rendraient la mesure tautologique, et une page
#: ou `len(ouvreurs) == len(lignes)` laisserait passer le mutant sur elle.
def corpus_de_la_MESURE() -> tuple[manuel.Entree, ...]:
    return tuple(
        [entree(f"K{rang:02d}", f"geste {rang}") for rang in range(14)]
        + [_entree_HAUTE(f"H{rang}", 3) for rang in range(5)]
        + [entree(f"Z{rang:02d}", f"dernier geste {rang}") for rang in range(7)])


def test_C6_la_fabrique_de_la_MESURE_tient_ce_que_la_REGLE_exige():
    """Sans ces quatre proprietes, la mesure de la ligne d'etat serait verte
    par coincidence.

    Cible en **tete**, au **milieu** et en **queue** de la liste que le CODE
    parcourt -- les pages rendues --, cardinaux **distinguables**, et sur
    chaque page `len(ouvreurs) != len(lignes)` : c'est exactement l'ecart que
    le mutant exploite.
    """
    entrees = corpus_de_la_MESURE()
    pages = em.pages_du_manuel(entrees)
    assert len(pages) == 3, [len(page.lignes) for page in pages]
    cardinaux = [len(page.ouvreurs) for page in pages]
    assert len(set(cardinaux)) == 3, cardinaux
    confondus = [rang for rang, page in enumerate(pages)
                 if len(page.ouvreurs) == len(page.lignes)]
    assert confondus == [], (confondus, cardinaux,
                            [len(page.lignes) for page in pages])
    # Les trois cibles nommees, une par page, dont une au MILIEU.
    assert "K00" in pages[0].ouvreurs, pages[0].ouvreurs
    assert "H2" in pages[1].ouvreurs, pages[1].ouvreurs
    assert "Z06" in pages[2].ouvreurs, pages[2].ouvreurs
    # Aucun ouvreur perdu ni double, et tous distinguables.
    pagines = [ouvreur for page in pages for ouvreur in page.ouvreurs]
    assert pagines == [e.ouvreur for e in entrees], len(pagines)
    assert len({e.libelles for e in entrees}) == len(entrees)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("rang_de_page", [0, 1, 2])
def test_C6_la_ligne_d_etat_COMPTE_les_RACCOURCIS_de_la_page_et_non_ses_LIGNES(
        rang_de_page, ascii_seul):
    """Mutant `M31` (couche 1 `F7`) / `M20` (couche 2 `F10`).

    Le premier nombre de la ligne d'etat est le cardinal des **raccourcis**
    que la page montre, recompte sur le dessin -- pas son cardinal de
    **lignes**, pas celui d'une autre page, pas une constante.
    """
    ecran = em.EcranManuel(corpus_de_la_MESURE())
    ecran.rang_de_page = rang_de_page
    page = ecran.pages()[rang_de_page]
    peints = _ouvreurs_PEINTS(page)
    assert peints, page.lignes
    nombres = [int(morceau) for morceau in re.findall(r"\d+",
                                                      ecran.ligne_d_etat(ascii_seul))]
    assert len(nombres) == 2, (nombres, ecran.ligne_d_etat(ascii_seul))
    assert nombres[0] == len(peints), (
        f"la page {rang_de_page + 1} peint {len(peints)} raccourcis et la "
        f"ligne d'etat en annonce {nombres[0]} "
        f"(elle en porte {len(page.lignes)} lignes) : "
        f"{ecran.ligne_d_etat(ascii_seul)!r}")


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("rang_de_page", [0, 1, 2])
def test_C6_le_TOTAL_de_la_ligne_d_etat_est_le_CARDINAL_de_la_derivation(
        rang_de_page, ascii_seul):
    """Le second nombre est ce que le **paquet** annonce, pas ce que la page
    montre.

    Il est confronte au cardinal des entrees livrees a l'ecran, jamais a une
    somme recalculee sur les pages : la somme viendrait de la meme lecture que
    le produit, et une inversion des deux nombres y resterait invisible sur une
    page ou ils coincideraient.
    """
    entrees = corpus_de_la_MESURE()
    ecran = em.EcranManuel(entrees)
    ecran.rang_de_page = rang_de_page
    nombres = [int(morceau) for morceau in re.findall(r"\d+",
                                                      ecran.ligne_d_etat(ascii_seul))]
    assert nombres[1] == len(entrees), (
        nombres, len(entrees), ecran.ligne_d_etat(ascii_seul))
    # Et les deux nombres ne se confondent pas : sur ce corpus aucune page ne
    # porte tout le manuel, donc une inversion rougit.
    assert nombres[0] != nombres[1], nombres


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C6_sur_le_PAQUET_REEL_la_ligne_d_etat_compte_JUSTE_sur_chaque_page(
        ascii_seul):
    """Le meme volet sur la derivation reelle -- c'est elle que le defaut
    mordait.

    Aucun rang de page n'est ecrit ici : le nombre de pages du manuel reel
    bouge a chaque ecran ajoute au paquet, et un rang en litteral rougirait
    pour une raison etrangere a ce qu'il mesure.
    """
    ecran = em.EcranManuel()
    pages = ecran.pages()
    total_annonce = set()
    for rang, page in enumerate(pages):
        ecran.rang_de_page = rang
        nombres = [int(m) for m in re.findall(r"\d+",
                                              ecran.ligne_d_etat(ascii_seul))]
        assert nombres[0] == len(_ouvreurs_PEINTS(page)), (
            rang, nombres, len(page.lignes))
        total_annonce.add(nombres[1])
    assert len(total_annonce) == 1, sorted(total_annonce)
    assert total_annonce == {sum(len(page.ouvreurs) for page in pages)}
    # Anti-vacuite : un manuel d'une seule page ne ferait rien mordre.
    assert len(pages) >= 2, len(pages)


# ===========================================================================
# C7 -- l'appariement POSITIONNEL a l'interieur des lignes ENVELOPPEES
# ===========================================================================
#
# Lot E2 -- couche 2 `F11` et `F12`, mutants `M32` et `M18`. Les deux etaient
# encore **survivants** au HEAD de la branche de cloture le 2026-09-05.
#
# * `M32` pose l'ouvreur sur la **derniere** ligne enveloppee au lieu de la
#   premiere. Quatre entrees du produit sont multi-lignes (`Tab`, `Échap`,
#   `↑↓`, `⏎`) : le mutant brouille donc reellement les trois quarts de la
#   page 1 du manuel ;
# * `M18` pose l'atelier sur `lignes[0]` au lieu de `lignes[-1]`.
#
# **Pourquoi rien ne les voyait**, et c'est la regle des fabriques mot pour
# mot : `lignes[0] is lignes[-1]` **partout**. Aucune fabrique du banc ne
# produisait d'entree multi-ligne, et aucune entree « propre » du produit ne
# s'enveloppe -- le bord n'existait dans aucun corpus. La confrontation a
# `T1-2`, elle, est aveugle par construction : elle asserte **quels** rangs
# divergent, jamais **comment**, et toutes les lignes de contenu sont deja
# listees comme divergentes.
#
# La mesure qui ferme est **positive et structurelle** : l'ouvreur est en
# `COLONNE_DE_L_OUVREUR` de la **premiere** ligne du groupe et d'aucune autre ;
# l'atelier est en `COLONNE_DE_L_ATELIER` de la **derniere** et d'aucune autre.

#: Trois entrees enveloppees, **de hauteurs differentes** et a des places
#: differentes du corpus : deux lignes en tete, quatre au milieu, trois en
#: queue. Les hauteurs different pour que la cible du milieu ne soit pas
#: indiscernable d'une cible de bord (point 2 bis de la regle des fabriques).
ENTREES_ENVELOPPEES = [
    pytest.param("E2", 2, "premier bord", id="tete-2-lignes"),
    pytest.param("M4", 4, "milieu", id="AU-MILIEU-4-lignes"),
    pytest.param("Q3", 3, "dernier bord", id="queue-3-lignes"),
]


#: Les DEUX branches de `lignes_d_une_entree`, chacune avec son propre
#: `rang == 0`. Les mesurer ensemble n'est pas du zele : la premiere redaction
#: de ce banc ne portait que `partout`, et la reinjection du **meme** mutant
#: dans la branche « propre » (`M32b`) a **survecu** aux 107 tests -- le mode
#: de panne exact que la politique 6.2 existe pour attraper.
BRANCHES_DE_L_ENTREE = [pytest.param(True, id="bloc-partout"),
                        pytest.param(False, id="bloc-propre")]


def corpus_ENVELOPPE(partout: bool = True) -> tuple[manuel.Entree, ...]:
    """Les trois entrees enveloppees, **entourees** d'entrees d'une ligne.

    L'entourage n'est pas decoratif : sans lui, la cible du milieu serait aussi
    la seule, et un balayage tronque en tete comme en queue resterait vert.
    """
    return (entree("A00", "geste zero", partout=partout),
            _entree_HAUTE("E2", 2, partout),
            entree("A01", "geste un", partout=partout),
            _entree_HAUTE("M4", 4, partout),
            entree("A02", "geste deux", partout=partout),
            _entree_HAUTE("Q3", 3, partout),
            entree("A03", "geste trois", partout=partout))


@pytest.mark.parametrize("partout", BRANCHES_DE_L_ENTREE)
def test_C7_la_fabrique_des_LIGNES_ENVELOPPEES_tient_ce_que_la_REGLE_exige(
        partout):
    """Les deux branches de `lignes_d_une_entree` produisent bien du
    multi-ligne.

    C'est la propriete que **personne** ne tenait : sans elle,
    `lignes[0] is lignes[-1]` et les deux mutants sont indistinguables du code
    sain. Le cardinal exact de chaque cible est verifie ici, pas suppose.
    """
    rendus = {e.ouvreur: em.lignes_d_une_entree(e)
              for e in corpus_ENVELOPPE(partout)}
    hauteurs = {ouvreur: len(lignes) for ouvreur, lignes in rendus.items()}
    assert hauteurs["E2"] == 2, hauteurs
    assert hauteurs["M4"] == 4, hauteurs
    assert hauteurs["Q3"] == 3, hauteurs
    assert all(hauteurs[nom] == 1 for nom in ("A00", "A01", "A02", "A03")), (
        hauteurs)
    # Distinguables : aucun libelle n'est repete d'une entree a l'autre.
    libelles = [e.libelles for e in corpus_ENVELOPPE(partout)]
    assert len(set(libelles)) == len(libelles), libelles


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("partout", BRANCHES_DE_L_ENTREE)
@pytest.mark.parametrize("ouvreur,hauteur,position", ENTREES_ENVELOPPEES)
def test_C7_l_OUVREUR_est_en_TETE_de_ses_lignes_et_sur_AUCUNE_autre(
        ouvreur, hauteur, position, partout, ascii_seul):
    """Mutants `M32` et `M32b` : `rang == 0` porte a `rang == len(morceaux) - 1`,
    dans l'une puis l'autre branche.

    Deux moities, et il faut les deux : la premiere ligne **porte** l'ouvreur a
    sa colonne, et **aucune** des suivantes n'ecrit quoi que ce soit avant
    `COLONNE_DU_LIBELLE`. La premiere seule laisserait passer un ouvreur
    duplique sur chaque ligne ; la seconde seule laisserait passer un groupe
    entierement indente.
    """
    cible = next(e for e in corpus_ENVELOPPE(partout) if e.ouvreur == ouvreur)
    lignes = em.lignes_d_une_entree(cible, ascii_seul=ascii_seul)
    assert len(lignes) == hauteur, (position, lignes)
    attendu = " " * em.COLONNE_DE_L_OUVREUR + jetons.replier_ascii(
        ouvreur) if ascii_seul else " " * em.COLONNE_DE_L_OUVREUR + ouvreur
    assert lignes[0].startswith(attendu), (position, lignes[0])
    suites = [rang for rang, ligne in enumerate(lignes[1:], start=1)
              if ligne[:em.COLONNE_DU_LIBELLE].strip()]
    assert suites == [], (
        f"l'entree {ouvreur} ({position}, partout={partout}) ecrit avant la "
        f"colonne du libelle sur les lignes {suites} : l'ouvreur a quitte la "
        f"premiere. Rendu : {lignes!r}")


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("ouvreur,hauteur,position", ENTREES_ENVELOPPEES)
def test_C7_l_ATELIER_est_en_QUEUE_de_ses_lignes_et_sur_AUCUNE_autre(
        ouvreur, hauteur, position, ascii_seul):
    """Mutant `M18` : `lignes[-1]` porte a `lignes[0]`.

    L'atelier annote le raccourci **une fois**, a droite de sa derniere ligne,
    comme `T1-2` l'ecrit. Pose sur la premiere, il couperait le libelle d'un
    raccourci qui s'enveloppe -- et aucune entree « propre » du produit ne
    s'enveloppant aujourd'hui, la fabrique est le seul endroit ou ce bord
    existe.
    """
    cible = next(e for e in corpus_ENVELOPPE(partout=False)
                 if e.ouvreur == ouvreur)
    lignes = em.lignes_d_une_entree(cible, ascii_seul=ascii_seul)
    assert len(lignes) == hauteur, (position, lignes)
    atelier = em.ateliers_d_une_entree(cible)
    assert atelier == "(Extraction)", atelier
    assert lignes[-1].endswith(atelier), (position, lignes[-1])
    assert lignes[-1].index(atelier) == em.COLONNE_DE_L_ATELIER, lignes[-1]
    ailleurs = [rang for rang, ligne in enumerate(lignes[:-1])
                if atelier in ligne]
    assert ailleurs == [], (
        f"l'atelier de {ouvreur} ({position}) est ecrit sur les lignes "
        f"{ailleurs} au lieu de la seule derniere. Rendu : {lignes!r}")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C7_sur_le_PAQUET_REEL_aucun_OUVREUR_ne_quitte_sa_PREMIERE_ligne(
        ascii_seul):
    """Le volet sur la derivation reelle -- c'est la que `M32` mord vraiment.

    Rien n'est designe par un rang : le corpus est le paquet, et le paquet
    bouge. La garde d'anti-vacuite porte donc sur une **propriete** -- il
    existe au moins trois entrees multi-lignes -- et non sur des noms
    d'ouvreurs, qui changeraient avec la maquette comme avec le produit.
    """
    entrees = manuel.entrees_du_manuel()
    rendus = {e.ouvreur: em.lignes_d_une_entree(e, ascii_seul=ascii_seul)
              for e in entrees}
    multi = {ouvreur: lignes for ouvreur, lignes in rendus.items()
             if len(lignes) > 1}
    assert len(multi) >= 3, (
        "moins de trois entrees du paquet s'enveloppent : la mesure ne peut "
        f"plus distinguer la premiere ligne de la derniere ({sorted(multi)})")
    fautives = {ouvreur: lignes for ouvreur, lignes in multi.items()
                if any(ligne[:em.COLONNE_DU_LIBELLE].strip()
                       for ligne in lignes[1:])
                or not lignes[0][:em.COLONNE_DE_L_OUVREUR].strip() == ""
                or not lignes[0][em.COLONNE_DE_L_OUVREUR:].strip()}
    assert fautives == {}, sorted(fautives)


# ===========================================================================
# C8 -- les deux gardes de la page VIDE, mesurees CHACUNE POUR ELLE-MEME
# ===========================================================================
#
# Lot E2 -- couche 1 `F3` (mutants `M28`, `M29`) et couche 2 `F14`. Les deux
# survivaient encore au HEAD de la branche de cloture : la reprise du titre a
# la coupure a ferme `M27`, elle n'a pas ferme les deux gardes voisines.

def test_C8_une_derivation_VIDE_rend_UNE_page_vide_plutot_que_ZERO():
    """Mutant `M29` : `if lignes or not pages:` -> `if lignes:`.

    Sans le `or not pages`, un paquet sans aucun raccourci rendrait **zero**
    page, et `composer()` leverait `IndexError` sur `pages[0]`. La garde est
    inatteignable en production tant que le paquet annonce des raccourcis --
    elle n'en est pas moins une garde, et une garde non mesuree part au premier
    nettoyage.
    """
    pages = em.pages_du_manuel(())
    assert len(pages) == 1, pages
    assert pages[0].lignes == (), pages[0]
    assert pages[0].ouvreurs == (), pages[0]
    ecran = em.EcranManuel(())
    assert ecran.composer() == []
    assert ecran.objet_du_bandeau() == em.libelle_de_page(0, 1)
    assert ecran.ligne_d_etat().startswith("0 ")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C8_aucune_page_n_est_VIDE_meme_quand_la_PREMIERE_unite_deborde(
        ascii_seul):
    """Mutant `M28` : `if lignes and ...` -> `if ...`.

    Sans le `lignes and`, une premiere unite plus haute que la zone centrale
    declenche la coupure **avant** d'avoir rien pose : le manuel s'ouvre sur
    une page entierement blanche, et `page 1 sur 3` designe du vide.

    Le corpus est taille pour ce bord exact -- titre (3 lignes) plus une entree
    de quatre lignes contre une hauteur de cinq --, et il porte trois entrees
    distinguables dont la cible n'est ni seule ni en derniere position.
    """
    corpus = (_entree_HAUTE("H4", 4),
              entree("A00", "un geste d'une ligne"),
              entree("A01", "un autre geste d'une ligne"))
    pages = em.pages_du_manuel(corpus, ascii_seul=ascii_seul, hauteur=5)
    vides = [rang for rang, page in enumerate(pages) if not page.ouvreurs]
    assert vides == [], (
        f"les pages {vides} ne portent aucun raccourci : la pagination a "
        f"coupe avant d'avoir rien pose. Cardinaux : "
        f"{[(len(p.lignes), len(p.ouvreurs)) for p in pages]}")
    # Volet de morsure : la coupure a bien lieu, sans quoi ce test serait vert
    # sur une pagination qui ne couperait jamais.
    assert len(pages) >= 2, [len(page.lignes) for page in pages]
    assert pages[0].ouvreurs == ("H4",), pages[0].ouvreurs


# ===========================================================================
# C9 -- chaque plafond de rang de page se mesure SEUL
# ===========================================================================
#
# Lot E2 -- couche 2 `F9`. Le rang de page est borne **deux fois** : `traiter`
# plafonne a la frappe, et `pages()` recale a la lecture suivante. Retirer
# **l'un** des deux ne faisait rougir personne (mutant `M15` : survivant encore
# au HEAD) ; retirer les deux faisait rougir. Le banc mesurait donc la
# **conjonction**, jamais aucun des deux termes -- et le jour ou l'un est retire
# pour simplifier, la suite reste verte et le second porte seul une charge que
# personne n'a verifiee.
#
# Le geste qui les separe : lire `rang_de_page` **juste apres la frappe**, sans
# rappeler `pages()`, qui rattraperait le debordement.

def test_C9_le_plafond_de_TRAITER_tient_SEUL_sur_la_derniere_page():
    """Mutant `M15` : `min(rang + 1, len(pages) - 1)` -> `rang + 1`.

    `rang_de_page` est lu **directement**, sans repasser par `pages()` : c'est
    la seule facon de mesurer ce plafond-ci plutot que celui de la lecture.
    """
    ecran = ecran_du_corpus()
    dernier = len(ecran.pages()) - 1
    assert dernier >= 2, dernier
    ecran.rang_de_page = dernier
    assert ecran.traiter("right") is True
    assert ecran.rang_de_page == dernier, (
        f"`traiter` a porte le rang a {ecran.rang_de_page} alors que le manuel "
        f"n'a que {dernier + 1} pages : son plafond ne tient pas seul")


def test_C9_le_plancher_de_TRAITER_tient_SEUL_en_premiere_page():
    """Le symetrique, sans lequel le test precedent serait vert sur une
    pagination qui n'avancerait jamais."""
    ecran = ecran_du_corpus()
    ecran.rang_de_page = 0
    assert ecran.traiter("left") is True
    assert ecran.rang_de_page == 0, ecran.rang_de_page
    # Et la morsure : depuis la page du milieu, les deux touches bougent.
    ecran.rang_de_page = 1
    assert ecran.traiter("right") is True and ecran.rang_de_page == 2
    assert ecran.traiter("left") is True and ecran.rang_de_page == 1
