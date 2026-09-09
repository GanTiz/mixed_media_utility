# -*- coding: utf-8 -*-
"""Story 11.5, lot F -- frontieres et cablage de l'atelier Scan (AC 8, AC 9).

Ce banc mesure ce qu'aucun des lots B a E ne pouvait mesurer seul : **le
paquet**, et **la chaine**. Les six autres bancs du Scan ont chacun leur module ;
celui-ci a la couture entre eux, et le fichier lui est propre -- « aucun lot ne
partage un fichier de banc avec un autre ».

**Le mode de panne central, et il a un compte de sept.** Un ecran livre, teste,
exporte -- et cable **nulle part** dans l'application. Le plus gros de la serie
(`E9`) faisait ouvrir a `mmu-tui` trois ecrans **temoins** alors que deux
paliers reels dormaient dans les bancs. Le temps 1 du Scan etait dans cet etat
exact avant ce lot : cinq ecrans livres et `ChaineReelle.entrer` menant l'entree
*Scan* a « pas encore ». Aucun banc unitaire ne peut voir ce defaut -- un banc
injecte le rappel lui-meme --, il faut monter **l'application du produit**.

**Ce que ce banc ne reecrit pas.** Les mesures de sobriete, de vocabulaire de
touche et de completion de chemin vivent deja dans le depot, chacune une fois :

* `test_sobriete_et_grille_extraction` porte le lexique des touches, des
  conseils et des motifs de conception ;
* `test_projets` porte la frontiere de la completion de **chemin**, resserree
  ce soir par `EPIC11-ARB-127` sur le **geste** et non sur le mot ;
* `outils_frontiere` porte la lecture d'AST.

Les trois sont **importees**, jamais recopiees : une seconde redaction
divergerait de la premiere, et le module non couvert par la plus stricte des
deux passerait. Le prix est une dependance entre bancs, dite plutot que tue.

**Regle des fabriques** (`CLAUDE.md`) : le corpus des sept ecrans porte sept
elements distinguables et **aucune mesure ne vise le premier** ; les fabriques
de lots viennent du banc du lot D, ou l'incomplet est **au milieu** de trois.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import previz_common, scan_corrections, scan_previz
from mixed_media_utility.tui import (
    atelier_scan,
    atelier_scan_calibrate,
    atelier_scan_calibration,
    atelier_scan_completion,
    atelier_scan_detection,
    atelier_scan_parcours,
    atelier_scan_rapport,
    jetons,
    projet_lecture,
)
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle,
    chaine_du_produit,
    construire_l_application,
)
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import SurfaceExecution

from outils_frontiere import identifiants
# Les fabriques de documents du lot D, LUES et non recopiees : elles placent
# deja leur lot incomplet **au milieu** de trois, et une seconde fabrique
# divergerait de celle-la a la premiere retouche du coeur.
import test_atelier_scan_rapport as fabriques_du_rapport
# La fabrique de source du lot B : trois pages reelles, la divergente au milieu.
import test_atelier_scan_depot as fabriques_du_depot
# Le lexique de sobriete du lot G de la 11.4, meme motif.
from test_sobriete_et_grille_extraction import (
    ecarts_de_sobriete,
    glyphes_hors_table,
)
# La frontiere de la completion de CHEMIN, resserree par `EPIC11-ARB-127`.
from test_projets import _occurrences_de_completion_de_chemin

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le paquet mesure.
PAQUET_TUI = Path(_SRC) / "mixed_media_utility" / "tui"

#: **Les modules NEUFS de la story 11.5**, nommes un par un. L'AC 8.1 le
#: demande mot pour mot : « un test le verifie **explicitement** sur eux plutot
#: que de le supposer » -- la frontiere de paquet de la 11.4b les couvre deja,
#: mais une frontiere de paquet reste verte si le paquet perd un module.
MODULES_NEUFS = (
    "atelier_scan.py",
    "atelier_scan_completion.py",
    "atelier_scan_detection.py",
    "atelier_scan_parcours.py",
    "atelier_scan_rapport.py",
)


# ===========================================================================
# Le corpus des SEPT ecrans du Scan
# ===========================================================================

def _source(tmp_path):
    """Une source designee, **mesuree par le vrai point d'entree du coeur**.

    La fabrique est celle du lot B -- trois pages reelles dont la divergente est
    au milieu --, et `designer` y appelle `scan_ingest.mesurer_la_source` sans
    double : c'est le chemin de production, et un double rendrait ici une forme
    que l'ingestion n'a pas reconnue.
    """
    dossier = tmp_path / "depot" / "planches"
    fabriques_du_depot._lot_de_trois_pages(dossier, divergent=False)
    return atelier_scan.designer(dossier)


def _rapport_incomplet():
    """`E3-4` : trois lots, l'incomplet **au milieu**, un reliquat de trois."""
    return atelier_scan_rapport.projeter(
        fabriques_du_rapport.documents_a_trois_lots(),
        partition=fabriques_du_rapport.partition_a_trois_entrees(),
        manifeste=fabriques_du_rapport.manifeste_a_trois_lots())


def _rapport_complet():
    """`E3-3` : les memes fabriques, **sans** le lot du milieu.

    Retirer celui du milieu plutot que le dernier est delibere : c'est la
    disposition qui demasque un `break` la ou un `continue` est attendu.
    """
    documents = [document
                 for document in fabriques_du_rapport.documents_a_trois_lots()
                 if document.subject.lot_id != fabriques_du_rapport.LOT_INCOMPLET]
    return atelier_scan_rapport.projeter(
        documents, partition=None,
        manifeste=fabriques_du_rapport.manifeste_a_trois_lots())


def _page_muette():
    """La planche muette du lot du milieu, telle que le rapport la designe."""
    completables = _rapport_incomplet().pages_completables
    assert completables, "la fabrique doit porter une planche completable"
    return completables[0]


def ecrans_du_scan(tmp_path) -> dict:
    """Les **sept** ecrans du temps 1, montables tels quels.

    La cle nomme la maquette : c'est elle que l'AC 8.3 designe, et un corpus
    indexe par nom de classe ne dirait pas lequel des sept manque.
    """
    projet = tmp_path / "projet"
    projet.mkdir(exist_ok=True)

    depot_vide = atelier_scan.EcranScanDepot(projet,
                                             detecter=lambda *_a: None)
    depot_pose = atelier_scan.EcranScanDepot(projet,
                                             detecter=lambda *_a: None)
    depot_pose.formulaire.poser_la_source(_source(tmp_path))

    surface = SurfaceExecution(unite=atelier_scan_detection.UNITE)
    # Un jalon **au milieu** de la passe : ni zero, ni le total. Une barre qui
    # ne dessinerait que ses extremites passerait sur les deux autres.
    surface.noter(3, 8)

    return {
        "E3-0": atelier_scan.EcranScanMenu(projet, entrer=lambda _e: None),
        "E3-1": depot_vide,
        "E3-1b": depot_pose,
        "E3-2": atelier_scan_detection.EcranDetectionEnCours(
            surface, titre_tache=atelier_scan_detection.TITRE_DE_LA_TACHE,
            sur_issue=lambda _i: None,
            objet=atelier_scan_detection.OBJET_DU_BANDEAU),
        "E3-3": atelier_scan_parcours.EcranRapportDeDetection(
            _rapport_complet(), sur_issue=lambda _i: None,
            document="versions/detection/26aout_1502.json"),
        "E3-4": atelier_scan_parcours.EcranRapportDeDetection(
            _rapport_incomplet(), sur_issue=lambda _i: None,
            document="versions/detection/26aout_1502.json"),
        "E3-4b": atelier_scan_completion.EcranCompletionQr(
            _page_muette(), fabriques_du_rapport.manifeste_a_trois_lots(),
            poser=lambda _i: None),
    }


#: Les sept noms, ecrits **en clair** a cote du corpus. Une constante comparee
#: a elle-meme ne mesurerait rien (piege du test tautologique, story 5.9).
MAQUETTES_DU_TEMPS_1 = ("E3-0", "E3-1", "E3-1b", "E3-2", "E3-3", "E3-4",
                        "E3-4b")

#: La cible des mesures parametrees. **Jamais la premiere du corpus** : un
#: `find` fautif qui rendrait toujours le premier element ne se demasquerait
#: pas autrement. Les sept y passent une par une.
CIBLES = [pytest.param(nom, id=nom) for nom in MAQUETTES_DU_TEMPS_1]


def _monter(banc, ecran, ascii_seul: bool, projet="projet_demo"):
    """Monter un ecran du Scan **au plancher** et rendre ce qu'il dessine.

    Rend le triplet que les mesures de ce banc consomment : la hauteur
    reellement occupee par la zone centrale, la ligne d'etat, et le texte de
    tous les blocs affiches.
    """
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                   contexte=Contexte(projet=projet), ascii_seul=ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        centre = pilote.app.screen.query_one("#centre")
        # `outer_size` et non `size` : le cartouche porte un cadre, et l'oublier
        # ferait tenir dix-neuf lignes la ou la grille en a dix-sept.
        hauteur = sum(enfant.outer_size.height for enfant in centre.children)
        etat = jetons.texte_affiche(
            str(pilote.app.screen.query_one("#etat").content))
        blocs = [jetons.texte_affiche(str(widget.content))
                 for widget in centre.query("Static")]
        return hauteur, etat, blocs

    return banc(app, scenario)


def test_le_corpus_porte_EXACTEMENT_les_SEPT_ecrans_du_temps_1(tmp_path):
    """Volet symetrique du corpus, et il vient en premier.

    Une mesure parametree sur un corpus ampute serait verte pour tous les
    ecrans qui restent. L'ensemble est donc mesure **exactement**, pas par
    inclusion : un huitieme ecran ajoute sans etre mesure fait rougir ici, et
    un septieme retire aussi.
    """
    assert set(ecrans_du_scan(tmp_path)) == set(MAQUETTES_DU_TEMPS_1)
    # Sept, ecrit en clair : `len(corpus) == len(corpus)` ne mesure rien.
    assert len(MAQUETTES_DU_TEMPS_1) == 7


def test_les_SEPT_maquettes_du_temps_1_EXISTENT_a_leur_source(tmp_path):
    """L'autre moitie : chacun des sept ecrans a bien une maquette validee.

    Un corpus d'ecrans qui ne correspondrait a aucune maquette mesurerait la
    conformite d'un dessin que personne n'a valide.
    """
    maquettes = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
                 / "ux-tui-2026-08-27" / "maquettes")
    manquantes = [nom for nom in MAQUETTES_DU_TEMPS_1
                  if not list(maquettes.glob(f"{nom}-*.txt"))]
    assert manquantes == [], manquantes


# ===========================================================================
# F1 -- le CABLAGE : l'atelier est atteignable, et aucun temoin ne subsiste
# ===========================================================================

def test_l_application_du_produit_ne_monte_AUCUN_palier_TEMOIN():
    """`E9`, remesure sur la chaine reelle -- et c'est la tache F1.

    Le defaut d'origine n'etait pas qu'un temoin trainait quelque part : c'est
    que `CoqueTui()` sans paliers en fabrique **trois**, et que le point
    d'entree du produit passait par ce chemin-la. La mesure porte donc sur les
    trois paliers de l'application reelle, en **ensemble exact** de leurs
    classes.
    """
    app = construire_l_application()
    classes = [type(palier).__name__ for palier in app._paliers]
    assert classes == ["EcranProjet", "EcranAteliers", "EcranPalierProjet"]
    assert not any(isinstance(palier, PalierTemoin) for palier in app._paliers)


def test_la_mesure_des_TEMOINS_MORD_sur_une_application_nue():
    """Volet symetrique : sans lui, la garde ci-dessus serait verte sur une
    application qui n'aurait plus aucun palier du tout."""
    nue = CoqueTui()
    assert any(isinstance(palier, PalierTemoin) for palier in nue._paliers)
    assert len(nue._paliers) == 3


def test_l_entree_SCAN_du_menu_des_ateliers_ouvre_le_MENU_DU_SCAN(tmp_path,
                                                                  banc):
    """F1 : `⏎` sur *Scan* mene a `E3-0`, **et plus a « pas encore »**.

    L'entree est cherchee par son **nom lu de `projet_lecture`**, jamais par
    son rang : le menu en porte cinq, et « la deuxieme » n'y designe rien de
    stable.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    chaine = chaine_du_produit()

    async def scenario(pilote):
        chaine.ouvrir(projet)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in chaine.menu.entrees}
        chaine.menu.entrer(entrees[projet_lecture.SCAN])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(chaine.app, scenario)
    assert isinstance(ecran, atelier_scan.EcranScanMenu), type(ecran).__name__
    assert not isinstance(ecran, EcranPasEncore)


#: Ce que chacune des cinq entrees du menu des ateliers ouvre, en table
#: **fermee**. Une assertion positive sur la seule entree *Scan* laisserait
#: passer une regression sur les quatre autres -- et c'est exactement ce que le
#: cablage touche : il ajoute une branche a `ChaineReelle.entrer`, la ou une
#: branche mal placee renverrait *Pdf* ou *Exports* vers l'atelier Scan.
#: Sur un projet **vide**, `Pdf` et `Exports` sont conditionnees -- « aucun lot »,
#: « aucun lot reconstruit » -- : le menu **reste** et nomme ce qui manque en
#: ligne d'etat, ce qui est le comportement voulu (`projet_lecture.entrees`).
#: `Scan`, lui, n'est jamais conditionne : « un projet reconstruit depuis le
#: scan seul est un cas nominal du depot ». C'est ce qui rend cette table
#: mesurable sur un projet neuf.
CE_QU_OUVRE_CHAQUE_ATELIER = {
    projet_lecture.PROJET: "EcranPalierProjet",
    projet_lecture.EXTRACTION: "EcranRushes",
    projet_lecture.SCAN: "EcranScanMenu",
    projet_lecture.PDF: "EcranAteliers",
    projet_lecture.EXPORTS: "EcranAteliers",
}

#: Les deux entrees que le projet vide condamne, en ensemble EXACT : le test
#: ci-dessous verifie qu'elles **disent** ce qui manque, et les trois autres
#: qu'elles descendent. Sans cet ensemble, une entree qui deviendrait muette
#: passerait pour une entree conditionnee.
ATELIERS_CONDITIONNES_SUR_UN_PROJET_VIDE = {projet_lecture.PDF,
                                            projet_lecture.EXPORTS}


@pytest.mark.parametrize("nom", sorted(CE_QU_OUVRE_CHAQUE_ATELIER))
def test_chaque_atelier_du_menu_mene_bien_OU_LA_TABLE_LE_DIT(tmp_path, banc,
                                                             nom):
    """Les cinq entrees, **une chaine neuve par entree**.

    Une seule chaine parcourue en boucle ne mesurerait pas ce qu'on croit : la
    remontee ne se fait pas au meme cran selon que l'ecran ouvert est un palier
    installe ou un passage, et les entrees suivantes partiraient d'un etat
    different. Le cout est cinq montages ; le benefice est que chaque cas est
    lisible seul quand il rougit.
    """
    projet = tmp_path / "projet"
    projet.mkdir(exist_ok=True)
    chaine = chaine_du_produit()

    async def scenario(pilote):
        chaine.ouvrir(projet)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in chaine.menu.entrees}
        chaine.menu.entrer(entrees[nom])
        chaine.menu.rafraichir()
        await pilote.pause()
        return (type(pilote.app.screen).__name__,
                jetons.texte_affiche(
                    str(chaine.menu.query_one("#etat").content)))

    vu, etat = banc(chaine.app, scenario)
    assert vu == CE_QU_OUVRE_CHAQUE_ATELIER[nom]
    # **Aucune des cinq n'est muette** : celle qui descend a change d'ecran,
    # celle qui ne descend pas NOMME ce qui manque. Une touche qui ne fait rien
    # et ne dit rien est indistinguable d'un clavier casse.
    if nom in ATELIERS_CONDITIONNES_SUR_UN_PROJET_VIDE:
        assert etat.strip() != "", nom
    else:
        assert etat.strip() == "", (nom, etat)


def test_la_table_des_CINQ_ateliers_couvre_le_menu_ENTIER(tmp_path, banc):
    """Volet symetrique de la table : elle porte **exactement** les entrees du
    menu, jamais un sous-ensemble.

    Sans lui, une sixieme entree ajoutee au menu resterait hors mesure, et la
    table ci-dessus serait verte en ne regardant plus tout.
    """
    projet = tmp_path / "projet"
    projet.mkdir(exist_ok=True)
    chaine = chaine_du_produit()

    async def scenario(pilote):
        chaine.ouvrir(projet)
        await pilote.pause()
        return {entree.nom for entree in chaine.menu.entrees}

    assert banc(chaine.app, scenario) == set(CE_QU_OUVRE_CHAQUE_ATELIER)


def test_le_parcours_du_Scan_est_INJECTE_par_la_chaine_du_PRODUIT(tmp_path,
                                                                  banc):
    """L'autre moitie de `E9` : le produit n'a pas de version degradee.

    `ChaineReelle` accepte le parcours en rappel -- c'est ce qui la rend
    mesurable sans disque --, mais `chaine_du_produit` l'injecte **toujours**.
    Une chaine construite sans lui NOMME ce qui manque plutot que de rester
    muette, et c'est cette seconde branche que l'on mesure ici : les deux
    doivent etre distinguables.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    assert chaine_du_produit()._ouvrir_l_atelier_scan is \
        atelier_scan_parcours.ouvrir_l_atelier_scan

    sans = ChaineReelle()

    async def scenario(pilote):
        sans.ouvrir(projet)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in sans.menu.entrees}
        sans.menu.entrer(entrees[projet_lecture.SCAN])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(sans.app, scenario)
    assert isinstance(ecran, EcranPasEncore)
    assert projet_lecture.SCAN in ecran.ce_qui_manque


def test_le_menu_du_Scan_mene_au_DEPOT_puis_le_depot_a_la_DETECTION(tmp_path,
                                                                    banc):
    """Le parcours, de bout en bout, **sans coeur reel**.

    Trois franchissements en un seul test, et c'est delibere : chacun d'eux a
    ete un rappel non cable ailleurs dans cet epic, et les mesurer separement
    ferait trois tests qui montent la meme chaine.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    vues = []

    class PasseFeinte:
        """Le double du coeur : il n'ecrit rien et rend un `outcome` nu."""

        documents = ()
        partition = None
        motif_d_arret = None

    def detection(*args, **kwargs):
        vues.append((args, sorted(kwargs)))
        return PasseFeinte()

    parcours = atelier_scan_parcours.ParcoursScan(
        None, projet, detection=detection)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app

    async def scenario(pilote):
        menu = parcours.ouvrir()
        await pilote.pause()
        etapes = [type(pilote.app.screen).__name__]
        menu.entrer(atelier_scan.ENTREES_DU_MENU[0])
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)
        parcours.detecter(projet / "planches", 600)
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)
        return etapes

    etapes = banc(app, scenario)
    assert etapes == ["EcranScanMenu", "EcranScanDepot",
                      "EcranRapportDeDetection"], etapes
    # Le coeur a bien ete appele **une** fois, et la source lui est passee
    # TELLE QUELLE (`EPIC7-ARB-88`) : aucune coercition en chemin.
    assert len(vues) == 1
    (args, mots) = vues[0]
    assert args == (projet, projet / "planches")
    # `nouvelle_version` s'ajoute avec le lot E de la 11.4e : le temps 1 porte
    # la seconde issue d'`EPIC11-ARB-89`, et le drapeau traverse le parcours
    # jusqu'au coeur. **L'ensemble reste mesure exactement** -- une inclusion
    # laisserait passer toute divergence supplementaire -- et il se met a jour
    # dans le commit qui l'ajoute, jamais apres coup.
    # `adopter` s'ajoute de meme avec `EPIC11-ARB-267`, le 2026-09-07.
    assert mots == ["adopter", "dpi", "ingest_slug", "logger",
                    "nouvelle_version", "rappel_progression"]


def test_l_entree_CALIBRER_ne_mene_PLUS_a_un_ecran_PAS_ENCORE(tmp_path, banc):
    """Ce test mesurait une **absence**, et il mesure desormais sa reparation.

    Jusqu'au lot H de la story 11.6, l'entree « Calibrer une chaine » etait
    `construite=False` et menait a `EcranPasEncore`, ce qui etait la forme
    honnete d'une absence. `E3-9` est livre et cable : les deux entrees du menu
    sont construites, et **aucune** ne mene plus a l'ecran qui nomme un manque.

    L'ensemble des entrees non construites est mesure **exactement vide** : une
    assertion sur la seule entree « calibrer » laisserait une troisieme entree
    revenir a `construite=False` sans que rien ne le dise.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    assert [entree.cle for entree in atelier_scan.ENTREES_DU_MENU
            if not entree.construite] == []

    parcours = atelier_scan_parcours.ParcoursScan(None, projet)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app
    entrees = {entree.cle: entree for entree in atelier_scan.ENTREES_DU_MENU}

    async def scenario(pilote):
        parcours.ouvrir()
        await pilote.pause()
        parcours.entrer(entrees["calibrer"])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert not isinstance(ecran, EcranPasEncore)
    assert isinstance(ecran, atelier_scan_calibrate.EcranCalibrerLaChaine), \
        type(ecran).__name__


def test_ECRIRE_les_frames_ouvre_le_CHOIX_DE_CALIBRATION_et_n_ecrit_rien(
        tmp_path, banc):
    """La seule issue du rapport qui ouvrait la 11.6 -- **elle l'ouvre**.

    Elle etait **atteignable et nommee** avant le lot H, et elle menait a un
    ecran qui disait l'absence ; elle mene maintenant a `E3-5`. Ce qui n'a pas
    change, et qui est mesure ici avec elle : **elle n'ecrit toujours rien**.
    `E3-5` puis `E3-6` sont deux ecrans de jugement, et rien n'est ecrit tant
    que la seule issue qui ecrit de `E3-6` n'a pas ete validee.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    temoin = projet / "temoin.txt"
    temoin.write_text("rien ne doit toucher ce dossier", encoding="utf-8")
    avant = sorted(chemin.name for chemin in projet.iterdir())
    parcours = atelier_scan_parcours.ParcoursScan(None, projet)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app
    parcours.rapport = _rapport_complet()

    async def scenario(pilote):
        ecran = parcours.montrer_le_rapport()
        await pilote.pause()
        ecrire = ecran.choix.action_qui_ecrit
        assert ecrire is not None and ecrire.cle == atelier_scan_rapport.ISSUE_ECRIRE
        parcours.juger(ecrire)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert not isinstance(ecran, EcranPasEncore)
    assert isinstance(
        ecran, atelier_scan_calibration.EcranChoixDeCalibration), \
        type(ecran).__name__
    # **Rien n'a ete ecrit**, et c'est mesure sur le disque plutot que promis.
    assert sorted(chemin.name for chemin in projet.iterdir()) == avant


# ===========================================================================
# F2 -- les frontieres du paquet, chacune avec son volet symetrique
# ===========================================================================

def test_les_CINQ_modules_du_Scan_EXISTENT(tmp_path):
    """Volet symetrique des deux frontieres qui suivent, et il vient avant.

    Une frontiere posee sur un module absent est verte sans rien mesurer :
    c'est le mode de panne que `sources_tui` ferme deja pour le paquet, ferme
    ici pour la liste nommee.
    """
    manquants = [nom for nom in MODULES_NEUFS
                 if not (PAQUET_TUI / nom).is_file()]
    assert manquants == [], manquants
    assert len(MODULES_NEUFS) == 5


@pytest.mark.parametrize("module", MODULES_NEUFS)
def test_aucun_module_du_Scan_n_appelle_JAMAIS_cli_py(module):
    """AC 8.1, **explicitement sur les modules neufs**.

    La frontiere de paquet de la 11.4b les couvre deja ; l'AC demande quand
    meme la mesure nommee, et elle a raison : une frontiere de paquet reste
    verte le jour ou un module sort du paquet, et celle-ci nomme lequel.

    Mesure a l'**AST** et non au texte : les docstrings de ces modules
    expliquent justement pourquoi ils n'appellent pas `cli`, donc ils portent
    le mot -- un grep y mordrait et se ferait affaiblir a la premiere prose.
    """
    noms = identifiants(PAQUET_TUI / module)
    fautifs = sorted(nom for nom in noms
                     if nom.endswith("cli") or nom.endswith(".cli"))
    assert fautifs == [], (module, fautifs)


def test_la_mesure_de_la_frontiere_cli_MORD_sur_un_module_du_Scan(tmp_path):
    """Volet symetrique, sur un module fabrique qui **ressemble** aux notres.

    Sa prose nomme `cli.py` sans l'appeler, et son code l'appelle : les deux
    moities dans le meme fichier, ce qui est la seule disposition ou une
    mesure de texte et une mesure d'AST rendent des reponses differentes.
    """
    fautif = tmp_path / "faux_atelier_scan.py"
    fautif.write_text(
        '"""Ce module parle de cli.py sans l\'appeler."""\n'
        "from mixed_media_utility import cli\n"
        "def detecter(args):\n"
        "    return cli.scan_command(args)\n",
        encoding="utf-8")
    noms = identifiants(fautif)
    assert any(nom.endswith("cli") for nom in noms), sorted(noms)

    innocent = tmp_path / "innocent_scan.py"
    innocent.write_text(
        '"""Ce module appelle io/, jamais cli.py."""\n'
        "MESSAGE = 'voir cli.py pour le detail'\n",
        encoding="utf-8")
    assert not any(nom.endswith("cli") for nom in identifiants(innocent))


def test_aucun_module_du_Scan_n_offre_de_COMPLETION_DE_CHEMIN():
    """AC 8.2, `EPIC11-ARB-48` **resserre par `EPIC11-ARB-127`**.

    Ce qui doit rendre zero est le **geste** de la barre d'adresse -- proposer
    la suite de ce qu'on tape --, pas le verbe francais : `E3-4b` s'appelle
    « Compléter le QR », et le lot D avait du renommer sa cle d'issue pour
    passer sous la frontiere d'avant. La mesure est donc celle de `test_projets`,
    **importee telle quelle** : la reecrire ici la re-elargirait au mot, et le
    contournement d'hier reviendrait en silence.
    """
    fautives = [ligne for ligne in _occurrences_de_completion_de_chemin(
        PAQUET_TUI) if ligne.split(":")[0] in MODULES_NEUFS]
    assert fautives == [], fautives


def test_le_vocabulaire_du_Scan_EST_bien_present_dans_les_modules_neufs():
    """Volet symetrique du precedent, et c'est lui qui rend la mesure honnete.

    Une frontiere qui rendrait zero parce que le mot a disparu du produit ne
    mesurerait plus rien : on verifie donc que le verbe est bel et bien la, et
    que c'est la frontiere qui le laisse passer, pas son absence.
    """
    source = (PAQUET_TUI / "atelier_scan_completion.py").read_text(
        encoding="utf-8")
    assert atelier_scan_rapport.LIBELLE_COMPLETER_LE_QR in (
        PAQUET_TUI / "atelier_scan_rapport.py").read_text(encoding="utf-8")
    assert "complet" + "er" in atelier_scan_rapport.ISSUE_COMPLETER
    assert "completion" in source.lower()


def test_la_mesure_de_la_COMPLETION_DE_CHEMIN_MORD(tmp_path):
    """Volet symetrique : la fonction importee doit SORTIR sur le geste retire,
    et **rester muette** sur le vocabulaire du Scan.

    Les deux fichiers sont dans le meme faux paquet, et le fautif est **au
    milieu** de trois : un `break` mis a la place du `continue` de la boucle de
    balayage laisserait le troisieme fichier hors mesure.
    """
    faux = tmp_path / "faux_paquet_scan"
    faux.mkdir()
    (faux / "a_sain.py").write_text("VALEUR = 1\n", encoding="utf-8")
    (faux / "b_fautif.py").write_text(
        "RACCOURCIS = 'Tab complete le chemin'\n", encoding="utf-8")
    (faux / "c_scan.py").write_text(
        "LIBELLE = 'Compléter le QR'\n", encoding="utf-8")
    trouvees = _occurrences_de_completion_de_chemin(faux)
    assert [ligne.split(":")[0] for ligne in trouvees] == ["b_fautif.py"], \
        trouvees


# ===========================================================================
# F3 -- la grille 80 x 24, la sobriete des bandeaux, la ligne d'etat
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_Scan_tient_les_24_LIGNES_de_la_grille(tmp_path, banc,
                                                               nom, ascii_seul):
    """AC 8.3, la dimension que la vague 2 ne mesurait pas.

    Le plafond est **derive** de la grille par
    `jetons.HAUTEUR_CENTRE_AU_PLANCHER` -- bordure, filets, bandeau, etat et
    raccourcis deduits --, jamais ecrit en dur : dix-sept pose ici serait une
    seconde source de verite.
    """
    hauteur, _etat, _blocs = _monter(banc, ecrans_du_scan(tmp_path)[nom],
                                     ascii_seul)
    assert hauteur <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, (nom, hauteur)


def test_la_mesure_de_HAUTEUR_MORD_sur_un_ecran_qui_DEBORDE(tmp_path, banc):
    """Volet symetrique : un corpus de petits ecrans ne mesure rien.

    L'ecran fabrique ici rend trente lignes de lot la ou la grille en admet une
    poignee. Sans lui, la mesure precedente resterait verte le jour ou la
    composition cesserait d'etre bornee -- ce qui est exactement l'etat dans
    lequel elle serait sans `budget_du_corps`.
    """
    class Deborde(atelier_scan_parcours.EcranRapportDeDetection):
        def lignes_des_lots(self):
            return [f"lot_{rang:02d}" for rang in range(30)]

    hauteur, _etat, _blocs = _monter(
        banc, Deborde(_rapport_complet(), sur_issue=lambda _i: None,
                      document="d.json"), False)
    assert hauteur > jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteur


def test_le_corpus_de_HAUTEUR_porte_un_ecran_qui_FROLE_le_plafond(tmp_path,
                                                                  banc):
    """Second volet symetrique : au moins un des sept **remplit** la grille.

    `E3-4` la remplit exactement -- trois lots, deux sous-lignes, un reliquat de
    trois fichiers et trois issues. Un corpus qui cesserait de le porter
    laisserait la mesure verte en permanence.
    """
    hauteurs = {nom: _monter(banc, ecran, False)[0]
                for nom, ecran in ecrans_du_scan(tmp_path).items()}
    assert max(hauteurs.values()) == jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteurs
    assert hauteurs["E3-4"] == jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteurs


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_Scan_tient_les_80_COLONNES(tmp_path, banc, nom,
                                                    ascii_seul):
    """AC 8.3, l'autre dimension, mesuree en **colonnes** et non en caracteres.

    `EPIC11-ARB-21` : « au-dela de 80 colonnes, la place gagnee allonge les
    lignes ; elle n'ajoute jamais une seconde colonne ». La mesure se fait donc
    au plancher, la ou tout doit deja tenir -- ligne d'etat comprise.
    """
    utile = jetons.largeur_utile()
    _hauteur, etat, blocs = _monter(banc, ecrans_du_scan(tmp_path)[nom],
                                    ascii_seul)
    trop_larges = [(rang, jetons.colonnes(ligne), ligne)
                   for bloc in blocs
                   for rang, ligne in enumerate(bloc.split("\n"))
                   if jetons.colonnes(ligne) > utile]
    assert trop_larges == [], (nom, trop_larges)
    assert jetons.colonnes(etat) <= utile, (nom, jetons.colonnes(etat), etat)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_aucune_ligne_d_etat_du_Scan_ne_porte_de_TOUCHE_ni_de_CONSEIL(
        tmp_path, banc, nom, ascii_seul):
    """AC 8.4, `EPIC11-ARB-56` : « la ligne d'etat porte une mesure, jamais une
    touche ni un conseil ».

    Le lexique est celui du lot G de la 11.4, **importe** : le recopier ici en
    ferait un second, qui divergerait au premier raccourci ajoute.
    """
    _hauteur, etat, _blocs = _monter(banc, ecrans_du_scan(tmp_path)[nom],
                                     ascii_seul)
    assert ecarts_de_sobriete(etat) == [], (nom, etat, ecarts_de_sobriete(etat))


def test_la_frontiere_de_SOBRIETE_MORD_sur_une_ligne_d_etat_du_Scan():
    """Volet symetrique : la mesure precedente regarde bien quelque chose.

    La ligne fautive est celle que la maquette `E3-1` portait avant la passe de
    ce matin -- « Tab complete les trois, ↓ choisit » --, et c'est l'ecart `G1`
    de cette story. Trois lignes, **la fautive au milieu** : une passe qui
    s'arreterait sur la premiere ligne saine laisserait la fautive hors mesure.
    """
    corpus = [
        "● 3 sources · 1,9 Go",
        "Un dossier, un fichier ou un PDF : Tab complete les trois, ↓ choisit.",
        "▲ 1 lot sur 2 est incomplet · 3 pages sur 4",
    ]
    fautives = [ligne for ligne in corpus if ecarts_de_sobriete(ligne)]
    assert fautives == [corpus[1]], fautives


#: Les ecrans dont la ligne d'etat est **volontairement vide**, en ensemble
#: EXACT. `DESIGN.md` section 3 : « une ligne d'etat sans rien a dire est une
#: ligne vide », jamais une ligne absente -- mais elle n'est legitime que quand
#: l'ecran n'a effectivement rien a mesurer :
#:
#: * `E3-0`, le menu de l'atelier : on n'y a rien fait, il n'y a rien a dire ;
#: * `E3-1` a l'arrivee : aucune source n'est designee, donc aucune mesure. Sa
#:   maquette est **sortie** le 2026-08-30 de l'inventaire des lignes d'etat
#:   fautives, ou elle nommait `Tab` et `↓` (ecart `G1`).
ECRANS_A_LIGNE_D_ETAT_VIDE = {"E3-0", "E3-1"}


def test_l_ensemble_des_lignes_d_etat_VIDES_est_EXACTEMENT_celui_la(tmp_path,
                                                                    banc):
    """L'autre moitie de l'AC 8.4, en **ensemble exact** et non par exception.

    « L'ensemble des chemins qui divergent est exactement {X} mesure l'exception
    ET son unicite » (`CLAUDE.md`). Une assertion du genre « E3-1 est vide »
    laisserait un troisieme ecran perdre sa mesure sans rien dire ; celle-ci
    rougit dans les deux sens -- y compris le jour ou `E3-1` gagnera la sienne.
    """
    vides = {nom for nom, ecran in ecrans_du_scan(tmp_path).items()
             if not _monter(banc, ecran, False)[1].strip()}
    assert vides == ECRANS_A_LIGNE_D_ETAT_VIDE, sorted(
        vides ^ ECRANS_A_LIGNE_D_ETAT_VIDE)


# ===========================================================================
# F4 -- le repli ASCII et la table des glyphes
# ===========================================================================

@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_Scan_se_rend_en_ASCII_PUR(tmp_path, banc, nom):
    """AC 8.5 : `--ascii` ne laisse **aucun** caractere hors ASCII imprimable.

    Le depot a paye ce chemin deux fois dans la journee -- findings `F7` puis
    `R1` : la frontiere existait, ses fabriques n'entraient pas dans les modes
    neufs. Elle entre ici dans les **sept** ecrans du Scan, ligne d'etat
    comprise.
    """
    _hauteur, etat, blocs = _monter(banc, ecrans_du_scan(tmp_path)[nom], True)
    hors_ascii = sorted({caractere
                         for texte in blocs + [etat]
                         for caractere in texte
                         if caractere not in "\n" and not (
                             32 <= ord(caractere) < 127)})
    assert hors_ascii == [], (nom, hors_ascii)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_aucun_GLYPHE_HORS_TABLE_dans_les_ecrans_du_Scan(tmp_path, banc, nom,
                                                         ascii_seul):
    """AC 8.6 : la table fermee de `DESIGN.md` section 6, sur les sept ecrans.

    Le predicat est celui du lot G de la 11.4, importe : il lit l'alphabet
    autorise de `jetons` -- glyphes du mode, symboles de repli, ellipse -- et
    non une liste recopiee.
    """
    _hauteur, etat, blocs = _monter(banc, ecrans_du_scan(tmp_path)[nom],
                                    ascii_seul)
    hors_table = set()
    for texte in blocs + [etat]:
        hors_table |= glyphes_hors_table(texte, ascii_seul)
    assert hors_table == set(), (nom, sorted(hors_table))


def test_la_table_des_GLYPHES_MORD_sur_un_dessin_qui_n_y_est_pas():
    """Volet symetrique : sans lui, un predicat qui ne verrait rien serait vert
    sur les sept ecrans a la fois."""
    assert glyphes_hors_table("★ un lot", False) == {"★"}
    assert glyphes_hors_table("● un lot", False) == set()


def test_le_repli_ASCII_du_rapport_ALLONGE_bien_au_moins_une_ligne(tmp_path,
                                                                   banc):
    """Volet symetrique du repli : `—` rend `--`, `…` rend `...`.

    Une mesure de repli sur un corpus qui ne se replierait pas serait verte en
    permanence -- c'est exactement ce qu'etait le verificateur de maquettes
    avant le 2026-08-29. La phrase d'ouverture du rapport porte un cadratin :
    elle s'allonge d'une colonne, et c'est ce qui donne sa valeur a la mesure
    de largeur en mode ASCII.
    """
    titre = atelier_scan_parcours.TITRE_DU_RAPPORT
    assert jetons.colonnes(jetons.replier_ascii(titre)) > jetons.colonnes(titre)


# ===========================================================================
# La ligne de raccourcis du rapport -- ce qu'elle promet, elle le tient
# ===========================================================================

def test_la_ligne_de_raccourcis_du_RAPPORT_n_annonce_que_des_touches_LIEES():
    """`I8`, la classe de defaut que le lot I a payee quarante fois.

    La maquette annonce `Tab journal` ; aucun ecran de journal n'est monte par
    le temps 1 et `CoqueTui.BINDINGS` n'a pas de liaison `tab`. La ligne du
    produit ne le promet donc pas -- et ce test la garde, dans les deux sens :
    la reintroduire sans monter le journal le fait rougir.
    """
    ligne = atelier_scan_parcours.RACCOURCIS_RAPPORT
    assert "Tab" not in ligne, ligne
    # Ce qu'elle promet, en revanche, est bien la : `⏎` et `↑↓` sont traites
    # par `EcranChiffre.traiter`, `Échap` et `F1` par l'application.
    for promesse in ("⏎", "↑↓", "Échap", "F1"):
        assert promesse in ligne, (promesse, ligne)


def test_le_rapport_repond_bien_aux_touches_qu_il_ANNONCE(tmp_path, banc):
    """L'autre moitie : les touches annoncees **agissent**.

    Une ligne de raccourcis honnete se mesure des deux cotes -- ce qu'elle tait
    et ce qu'elle tient. Le curseur part sur une issue qui n'ecrit pas
    (`ChoixExclusif`), et `↓` le deplace : les deux sont mesures ensemble, sans
    quoi un curseur fige passerait pour un curseur bien place.
    """
    ecran = ecrans_du_scan(tmp_path)["E3-4"]
    depart = ecran.choix.curseur
    assert not ecran.choix.issues[depart].ecrit
    assert ecran.traiter("down") is True
    assert ecran.choix.curseur != depart
    assert ecran.traiter("up") is True
    assert ecran.choix.curseur == depart


# ===========================================================================
# Ce que le cablage TRANSPORTE -- la seconde moitie du lot F
#
# Les mesures ci-dessus disent que la chaine mene quelque part ; celles-ci
# disent qu'elle y mene avec les BONNES valeurs. La campagne d'injection les a
# toutes exigees : sans elles, vingt et un mutants survivaient -- dont la
# famille `M25` / `R12` (« la correction est ecrite dans le premier document de
# la passe ») et la famille `continue` -> `break` de la 11.4b.
# ===========================================================================

def _recette(graine: str) -> str:
    """Une empreinte de la forme que le coeur exige, derivee de sa graine.

    `sha256-v1:` suivi de 64 hexadecimaux : le lecteur normatif de `scan_previz`
    la verifie, et une fabrique qui ecrirait `empreinte-lot_25fps` produit un
    document que **rien ne peut relire** -- ce qui rendrait le banc vert en ne
    mesurant plus rien.
    """
    return "sha256-v1:" + hashlib.sha256(graine.encode("utf-8")).hexdigest()


def _document_relisible(document):
    """Un document de la fabrique du lot D, rendu **relisible par le coeur**.

    Le banc du lot D ne serialise jamais ses documents : il projette des objets
    en memoire, donc trois raccourcis de fabrique lui suffisent (version
    d'enveloppe `1.0`, empreintes en clair, payload sans les champs que
    l'ecriture exige). Ce banc-ci les ECRIT sur le disque et les relit par
    `scan_previz.scan_previz_from_json_dict` : les trois raccourcis y deviennent
    des refus. On les comble ici plutot que de toucher a la fabrique du lot D --
    elle est juste pour ce qu'elle mesure.
    """
    pages = []
    for page in document.pages:
        if page.payload is not None:
            charge = dict(page.payload)
            charge.setdefault("page_role", "frames")
            charge.setdefault("patch_preset_id", None)
            charge.setdefault("slots", [])
            page = dataclasses.replace(page, payload=charge)
        pages.append(dataclasses.replace(
            page, source_digest=_recette(str(page.read_rank))))
    return dataclasses.replace(
        document, previz_schema_version=previz_common.PREVIZ_SCHEMA_VERSION,
        pages=tuple(pages),
        fingerprints=scan_previz.ScanPrevizFingerprints(
            detection=_recette(document.subject.lot_id)))


def _ecrire_les_documents(tmp_path, documents=None) -> list[Path]:
    """Ecrire les trois documents de la fabrique, **un par lot**, sur le disque.

    Ils portent des `ingest_slug` **differents de leurs `lot_id`** -- la
    fabrique du lot D les prefixe `slug_` --, et c'est ce qui demasque un
    document cherche par le mauvais champ.
    """
    documents = (documents
                 if documents is not None
                 else fabriques_du_rapport.documents_a_trois_lots())
    chemins = []
    for document in documents:
        document = _document_relisible(document)
        chemin = (tmp_path / "versions" / "detection"
                  / f"{document.subject.lot_id}.json")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(scan_previz.scan_previz_to_json_dict(document)),
            encoding="utf-8")
        chemins.append(chemin)
    return chemins


class AppFeinte:
    """Le strict minimum de `CoqueTui` qu'un parcours touche hors terminal.

    Elle existe pour mesurer ce que le parcours **fait** -- quel document il
    ecrit, quelle planche il retient -- sans monter d'application : monter
    `textual` pour verifier une ecriture sur le disque melangerait deux mesures,
    et c'est celle du disque qui compte ici. Les ecrans montes sont **retenus**
    plutot que jetes : un parcours qui ne descendrait nulle part se verrait.
    """

    ascii_seul = False
    sans_couleur = False
    interruption_demandee = False

    def __init__(self) -> None:
        self.montes = []

    def descendre(self, ecran=None) -> None:
        self.montes.append(ecran)

    def revenir_aux_ateliers(self) -> None:
        self.montes.append("ateliers")

    @property
    def screen(self):
        return self.montes[-1] if self.montes else None


def _parcours(tmp_path, chemins=None):
    """Un parcours dont les documents sont **relus du disque**, sans app."""
    parcours = atelier_scan_parcours.ParcoursScan(AppFeinte(), tmp_path)
    parcours.documents = atelier_scan_parcours.documents_relus(
        chemins if chemins is not None else _ecrire_les_documents(tmp_path))
    return parcours


def _identite(lot_id: str, read_rank: int = 12):
    """L'identite saisie sur `E3-4b`, telle que le formulaire la rend."""
    return scan_corrections.IdentiteManuelle(
        read_rank=read_rank, lot_id=lot_id, template_id="T1",
        frames_per_page=2, page_index=1,
        first_frame_timecode="00:00:01:00",
        last_frame_timecode="00:00:02:00")


def test_la_fabrique_de_documents_est_bien_RELISIBLE_par_le_coeur(tmp_path):
    """Volet symetrique des mesures qui suivent, et il vient avant elles.

    `documents_relus` **saute** un document illisible : une fabrique qui en
    produirait trois d'illisibles rendrait un parcours a zero document, et
    toutes les mesures d'ecriture ci-dessous seraient vertes en ne touchant
    rien du tout.
    """
    parcours = _parcours(tmp_path)
    lots = [objet.subject.lot_id for _c, _b, objet in parcours.documents]
    assert lots == [fabriques_du_rapport.LOT_PREMIER,
                    fabriques_du_rapport.LOT_INCOMPLET,
                    fabriques_du_rapport.LOT_DERNIER], lots


def test_un_document_ILLISIBLE_AU_MILIEU_ne_fait_pas_disparaitre_les_SUIVANTS(
        tmp_path):
    """La famille `continue` -> `break` de la 11.4b, sur la boucle de relecture.

    Le document abime est **au milieu** de trois, et c'est la seule position qui
    demasque les deux fautes a la fois : en premiere position un `break`
    rendrait une liste vide (visible autrement), en derniere il ne changerait
    rien du tout. Au milieu, il fait disparaitre le troisieme lot **en
    silence** -- ni frames, ni mires, ni declaration, et tout reste vert.
    """
    chemins = _ecrire_les_documents(tmp_path)
    chemins[1].write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    relus = atelier_scan_parcours.documents_relus(chemins)
    assert [objet.subject.lot_id for _c, _b, objet in relus] == [
        fabriques_du_rapport.LOT_PREMIER, fabriques_du_rapport.LOT_DERNIER]


def test_la_correction_est_ecrite_dans_le_document_DU_LOT_SAISI(tmp_path):
    """La famille `M25` de la story 5.7, et sa consequence de terrain `R12`.

    « `_find_lot` rendait le **premier** lot au lieu du lot vise, et les 257
    tests restaient verts » : les cardinaux du scan etaient ecrits **sur le
    mauvais lot**. Ici c'est une identite manuelle, et le succes apparent est le
    meme -- l'ecriture aboutit, le rapport se recalcule, rien n'echoue.

    On mesure donc **quel** document a recu la correction, en ensemble EXACT :
    « l'ensemble des chemins qui divergent est exactement {X} » mesure
    l'exception ET son unicite. Le lot vise est celui **du milieu**.
    """
    chemins = _ecrire_les_documents(tmp_path)
    parcours = _parcours(tmp_path, chemins)
    parcours.rapport = _rapport_incomplet()
    avant = {chemin: chemin.read_bytes() for chemin in chemins}

    parcours.poser(_identite(fabriques_du_rapport.LOT_INCOMPLET))

    divergents = {chemin.name for chemin in chemins
                  if chemin.read_bytes() != avant[chemin]}
    assert divergents == {f"{fabriques_du_rapport.LOT_INCOMPLET}.json"}, \
        divergents
    posees = scan_corrections.lire_les_identites(
        json.loads(chemins[1].read_text(encoding="utf-8")))
    assert [identite.lot_id for identite in posees.values()] == [
        fabriques_du_rapport.LOT_INCOMPLET]


def test_le_document_est_cherche_par_son_LOT_et_non_par_son_SLUG(tmp_path):
    """Le champ voisin, et il ment de la meme facon.

    `subject.ingest_slug` et `subject.lot_id` sont deux chaines differentes du
    meme objet -- la fabrique les distingue (`slug_lot_12p5` contre
    `lot_12p5`). Chercher par l'un ou par l'autre donne le meme resultat sur une
    fabrique qui les confondrait ; ici, chercher par le slug ne trouve **rien**,
    donc rien ne serait ecrit.
    """
    parcours = _parcours(tmp_path)
    trouve = parcours._document_du_lot(fabriques_du_rapport.LOT_INCOMPLET)
    assert trouve is not None
    assert trouve[2].subject.lot_id == fabriques_du_rapport.LOT_INCOMPLET
    assert trouve[2].subject.ingest_slug != fabriques_du_rapport.LOT_INCOMPLET
    # Et le slug ne designe aucun document : la confusion se voit.
    assert parcours._document_du_lot(trouve[2].subject.ingest_slug) is None


def test_un_lot_SANS_DOCUMENT_n_ecrit_RIEN_et_le_DIT(tmp_path, banc):
    """La branche que la campagne a trouvee muette (mutants `F12` et `F13`).

    Un lot connu du manifeste peut n'avoir **aucun** document de detection --
    c'est le cas de la planche du reliquat dont le lot n'a livre aucune autre
    page. Fabriquer un document ici ecrirait ce que la detection n'a pas
    trouve ; ecrire dans « le premier document » serait `R12`. Reste la seule
    issue honnete : ne rien ecrire, **et le dire**.

    La mesure porte sur les DEUX moities : les fichiers sont inchanges, et la
    ligne d'etat de l'ecran porte le motif -- **apres un redessin**, parce que
    c'est la que `poser_etat` seul se serait fait effacer.
    """
    chemins = _ecrire_les_documents(tmp_path)
    parcours = _parcours(tmp_path, chemins)
    avant = {chemin: (chemin.stat().st_ino, chemin.stat().st_mtime_ns)
             for chemin in chemins}

    ecran = atelier_scan_completion.EcranCompletionQr(
        _page_muette(), fabriques_du_rapport.manifeste_a_trois_lots(),
        poser=parcours.poser)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        parcours.poser(_identite("lot_qui_n_a_aucun_document"))
        # Le dessin qui suit toute touche : c'est lui qui effacerait un etat
        # pose par `poser_etat` seul.
        ecran.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#etat").content))

    etat = banc(app, scenario)
    assert "lot_qui_n_a_aucun_document" in etat, etat
    apres = {chemin: (chemin.stat().st_ino, chemin.stat().st_mtime_ns)
             for chemin in chemins}
    assert apres == avant, "aucun document ne doit avoir ete touche"


def test_la_planche_completee_n_est_PLUS_reproposee(tmp_path):
    """Les deux moities de « on avance » (mutants `F10` et `F11`).

    `posees` retient le rang de lecture, et le document corrige est **relu** :
    sans le premier, l'operateur retape indefiniment la meme planche ; sans le
    second, le rapport recalcule montre encore une planche que le disque, lui,
    ne compte plus comme muette.
    """
    chemins = _ecrire_les_documents(tmp_path)
    parcours = _parcours(tmp_path, chemins)
    parcours.rapport = atelier_scan_rapport.projeter(
        [objet for _c, _b, objet in parcours.documents],
        manifeste=fabriques_du_rapport.manifeste_a_trois_lots())
    muette = parcours.rapport.pages_completables[0]

    parcours.poser(_identite(fabriques_du_rapport.LOT_INCOMPLET,
                             read_rank=muette.read_rank))

    assert parcours.posees == [muette.read_rank]
    # Le triplet du lot corrige a ete REMPLACE : son objet porte desormais la
    # correction, donc le rapport recalcule la verra.
    corrige = parcours._document_du_lot(fabriques_du_rapport.LOT_INCOMPLET)
    assert scan_corrections.lire_les_identites(corrige[1])
    assert atelier_scan_completion.page_suivante_a_completer(
        parcours.rapport.pages_completables, parcours.posees) is None


def test_les_pages_lues_d_une_planche_du_RELIQUAT_sont_VIDES(tmp_path):
    """AC 7.4 : une planche que le tri n'a rattachee a rien n'a **aucune soeur**.

    C'est un regime nominal -- la pile d'une seule planche muette --, pas un
    manque. Lui donner les pages d'un lot vide ferait porter la verification de
    coherence sur des planches qu'elle n'a pas.
    """
    parcours = _parcours(tmp_path)
    reliquat = atelier_scan_rapport.PageMuette(
        read_rank=32, fichier="scans/pile/planche_07.tiff", lot_id=None)
    assert parcours._pages_lues(reliquat) == ()
    # Volet symetrique, et il porte l'ensemble EXACT : une planche RATTACHEE
    # recoit les soeurs de **son** lot, jamais celles d'un autre. Les trois lots
    # de la fabrique portent des rangs de lecture disjoints, si bien qu'un
    # `documents[0]` mis a la place du lot vise se voit -- c'est la famille
    # `M25` de la 5.7, portee sur la verification de coherence.
    rattachee = atelier_scan_rapport.PageMuette(
        read_rank=12, fichier="scans/pile/planche_03.tiff",
        lot_id=fabriques_du_rapport.LOT_INCOMPLET)
    assert [page.read_rank for page in parcours._pages_lues(rattachee)] == \
        [11, 13]


#: Ce que chacune des issues du rapport ouvre, en table **fermee**. Le mutant
#: qui intervertit « Compléter le QR » et « Reprendre » survivait a tout : les
#: deux menent quelque part, rien n'echoue, et seule une table exacte le voit.
#: Chaque issue est mesuree sur le rapport **qui la porte** : `E3-4` offre
#: « Compléter le QR » parce qu'une planche muette existe, `E3-3` offre
#: « Reprendre » parce qu'aucune ne l'est. Les chercher toutes sur le meme
#: rapport rendrait la table fausse d'une entree.
CE_QU_OUVRE_CHAQUE_ISSUE = {
    # **Elle ouvrait `EcranPasEncore` jusqu'au lot H de la story 11.6**, et la
    # table dit desormais ou elle mene : `E3-5`, le premier ecran du temps 2.
    # Le changement est *dans le sens de la reparation*, et c'est cette table
    # fermee qui l'a dit -- pas une relecture.
    atelier_scan_rapport.ISSUE_ECRIRE: ("E3-4", "EcranChoixDeCalibration"),
    atelier_scan_rapport.ISSUE_COMPLETER: ("E3-4", "EcranCompletionQr"),
    atelier_scan_rapport.ISSUE_REPRENDRE: ("E3-3", "EcranScanDepot"),
}


@pytest.mark.parametrize("cle", sorted(CE_QU_OUVRE_CHAQUE_ISSUE))
def test_chaque_ISSUE_du_rapport_ouvre_bien_CE_QUE_LA_TABLE_DIT(tmp_path, banc,
                                                                cle):
    """Les trois issues qui descendent, une par une.

    `Annuler` n'y est pas : elle ne descend pas, elle **remonte** -- c'est le
    test suivant. Les melanger ferait une table dont une entree se lirait
    differemment des autres.
    """
    ecran_source, attendu = CE_QU_OUVRE_CHAQUE_ISSUE[cle]
    # Le rapport se **recalcule** depuis les documents relus : poser
    # `parcours.rapport` ne suffirait pas, `montrer_le_rapport` le refait. C'est
    # exactement le contrat de la note 10 d'Egan, et il se voit ici.
    documents = fabriques_du_rapport.documents_a_trois_lots()
    if ecran_source == "E3-3":
        documents = [document for document in documents
                     if document.subject.lot_id
                     != fabriques_du_rapport.LOT_INCOMPLET]
    parcours = _parcours(tmp_path,
                         _ecrire_les_documents(tmp_path, documents))
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app

    async def scenario(pilote):
        ecran = parcours.montrer_le_rapport()
        await pilote.pause()
        issues = {issue.cle: issue for issue in ecran.choix.issues}
        assert cle in issues, (cle, sorted(issues))
        parcours.juger(issues[cle])
        await pilote.pause()
        return type(pilote.app.screen).__name__

    assert banc(app, scenario) == attendu


def test_ANNULER_remonte_aux_ateliers_et_n_est_JAMAIS_muette(tmp_path, banc):
    """La quatrieme issue : elle **remonte**, et elle fait quelque chose.

    Un `return` nu y serait invisible a toute table de descente -- l'ecran
    resterait celui du rapport, ce qui est aussi ce qu'on verrait si la touche
    n'etait liee a rien. On mesure donc la remontee elle-meme.

    **La pile porte les deux paliers du dessous**, et ce n'est pas decoratif :
    `revenir_aux_ateliers` depile « jusqu'a un RANG » et non « d'un cran ». Une
    pile trop courte y rendrait un no-op indistinguable du mutant.
    """
    parcours = _parcours(tmp_path)
    app = CoqueTui(paliers=[PalierTemoin("Projet", "Q quitter"),
                            PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    parcours.app = app

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = parcours.montrer_le_rapport()
        await pilote.pause()
        avant = type(pilote.app.screen).__name__
        issues = {issue.cle: issue for issue in ecran.choix.issues}
        parcours.juger(issues[atelier_scan_rapport.ISSUE_ANNULER])
        await pilote.pause()
        return avant, pilote.app.screen.titre

    avant, apres = banc(app, scenario)
    assert avant == "EcranRapportDeDetection"
    # Le palier d'arrivee est nomme : « Ateliers », et pas seulement « autre
    # chose que le rapport ». Un depilement d'un cran de trop irait au projet.
    assert apres == "Ateliers", apres


def test_le_rapport_est_une_STATION_et_non_un_passage(tmp_path):
    """On revient dessus apres chaque planche completee : il doit y etre.

    Un ecran `TRANSITOIRE` sort de la pile a la descente suivante -- c'est ce
    que `coque.Palier` documente --, et le retour de `E3-4b` ne retrouverait
    plus l'ecran qui l'avait ouverte.
    """
    ecran = ecrans_du_scan(tmp_path)["E3-4"]
    assert ecran.TRANSITOIRE is False
    # Volet symetrique : le formulaire de completion, LUI, est un passage.
    assert ecrans_du_scan(tmp_path)["E3-4b"].TRANSITOIRE is True


# ---------------------------------------------------------------------------
# Ce que le rapport MONTRE -- lignes de lot, file, issues, ligne d'etat
# ---------------------------------------------------------------------------

#: Les trois glyphes d'etat qui **ouvrent** une ligne de lot dans le cartouche.
#: Une ligne de lot se reconnait a son glyphe, jamais a son nom seul : l'a-cote
#: de l'issue « Écrire quand même » porte le meme nom de lot, et une mesure qui
#: chercherait le nom en trouverait deux.
GLYPHES_D_ETAT_DE_LOT = tuple(
    jetons.glyphes(mode)[etat]
    for mode in (False, True)
    for etat in ("complete", "substitute", "absent"))


def _est_une_ligne_de_lot(ligne: str) -> bool:
    return ligne.startswith(GLYPHES_D_ETAT_DE_LOT)


def _corps(banc, ecran, ascii_seul: bool = False) -> list[str]:
    """Toutes les lignes de la zone centrale d'un ecran monte."""
    _hauteur, _etat, blocs = _monter(banc, ecran, ascii_seul)
    return [ligne for bloc in blocs for ligne in bloc.split("\n")]


def test_chaque_LOT_du_rapport_a_sa_ligne_avec_SES_PROPRES_chiffres(tmp_path,
                                                                    banc):
    """AC 6.1, et c'est l'appariement que la regle des fabriques vise.

    Trois lots aux comptes **tous differents** : une ligne qui porterait les
    chiffres d'un autre lot se voit, ce qu'un remplissage uniforme rendrait
    invisible (mutant `M33` de la 5.6). Chaque lot est cherche par son nom, et
    ses deux mesures sont exigees **sur sa ligne**, pas dans l'ecran.
    """
    lignes = _corps(banc, ecrans_du_scan(tmp_path)["E3-4"])
    attendu = {
        fabriques_du_rapport.LOT_PREMIER: ("2 pages / 2", "5 frames / 5"),
        fabriques_du_rapport.LOT_INCOMPLET: ("2 pages / 3", "3 frames / 62"),
        fabriques_du_rapport.LOT_DERNIER: ("3 pages / 3", "9 frames / 9"),
    }
    for lot, (pages, frames) in attendu.items():
        portantes = [ligne for ligne in lignes
                     if _est_une_ligne_de_lot(ligne) and lot in ligne]
        assert len(portantes) == 1, (lot, portantes)
        assert pages in portantes[0] and frames in portantes[0], (lot,
                                                                  portantes[0])


def test_un_attendu_ABSENT_ne_se_remplace_ni_par_ZERO_ni_par_un_TIRET(tmp_path,
                                                                      banc):
    """`DESIGN.md` section 3 : jamais `0`, jamais `--`, jamais une valeur
    devinee.

    Le rapport est projete **sans manifeste** : les frames attendues valent
    alors `None` pour les trois lots. La ligne doit dire ce qu'elle a mesure et
    **se taire** sur ce qu'elle n'a pas -- un `/ 0` se lirait comme « tout est
    manquant » sur un lot dont personne ne connait le cardinal.
    """
    sans_manifeste = atelier_scan_rapport.projeter(
        fabriques_du_rapport.documents_a_trois_lots(),
        partition=fabriques_du_rapport.partition_a_trois_entrees())
    ecran = atelier_scan_parcours.EcranRapportDeDetection(
        sans_manifeste, sur_issue=lambda _i: None, document="d.json")
    lignes = [ligne for ligne in _corps(banc, ecran)
              if _est_une_ligne_de_lot(ligne)
              and fabriques_du_rapport.LOT_INCOMPLET in ligne]
    assert len(lignes) == 1, lignes
    assert "3 frames" in lignes[0], lignes[0]
    assert "/ 0" not in lignes[0] and "/ --" not in lignes[0], lignes[0]
    # Les PAGES, elles, ont bien leur attendu : le lot D le lit des documents,
    # pas du manifeste. Sans ce volet, le test serait vert sur une ligne qui
    # aurait perdu ses deux mesures.
    assert "2 pages / 3" in lignes[0], lignes[0]


def test_la_ligne_d_etat_ne_compte_QUE_les_lots_INCOMPLETS(tmp_path, banc):
    """AC 8.4 : la mesure de `E3-4`, verbatim de sa maquette moins l'ecart `G11`.

    Trois lots, **un seul incomplet, au milieu** : une somme qui porterait sur
    tous les lots afficherait « 3 lots sur 3 », et une somme qui s'arreterait au
    premier afficherait « 0 lot ». Les deux fautes sont exclues par la meme
    mesure.
    """
    _hauteur, etat, _blocs = _monter(banc, ecrans_du_scan(tmp_path)["E3-4"],
                                     False)
    assert "1 lot sur 3 est incomplet" in etat, etat
    assert "2 pages sur 3" in etat and "3 frames sur 62" in etat, etat


def test_la_ligne_d_etat_TAIT_une_mesure_dont_l_attendu_MANQUE(tmp_path, banc):
    """Le pendant de la ligne de lot, en ligne d'etat.

    « Ce champ diverge » ne mesure rien ; ce qui est mesure ici est qu'une somme
    **partielle** ne s'affiche pas du tout. Un total partiel se lit exactement
    comme un total, et c'est ce qui le rend dangereux.
    """
    sans_manifeste = atelier_scan_rapport.projeter(
        fabriques_du_rapport.documents_a_trois_lots(),
        partition=fabriques_du_rapport.partition_a_trois_entrees())
    ecran = atelier_scan_parcours.EcranRapportDeDetection(
        sans_manifeste, sur_issue=lambda _i: None, document="d.json")
    _hauteur, etat, _blocs = _monter(banc, ecran, False)
    assert "1 lot sur 3 est incomplet" in etat, etat
    assert "pages sur" in etat, etat
    assert "frames sur" not in etat, etat


def test_les_DEUX_manques_d_un_lot_incomplet_sont_dits_SEPAREMENT(tmp_path,
                                                                  banc):
    """AC 6.7, `EPIC11-ARB-29` : ils n'ont pas la meme reparation.

    Une planche **absente** n'a jamais ete scannee ; une planche **muette** est
    sur la vitre et son identite est inconnue. Le lot du milieu porte les deux,
    et l'ensemble de ses sous-lignes est mesure **exactement** : une assertion
    positive sur l'une laisserait l'autre disparaitre sans rien dire.
    """
    lignes = _corps(banc, ecrans_du_scan(tmp_path)["E3-4"])
    rattachement = jetons.glyphes(False)["rattachement"]
    sous_lignes = [ligne.strip() for ligne in lignes
                   if ligne.strip().startswith(rattachement)]
    assert len(sous_lignes) == 2, sous_lignes
    assert any("page 1 manquante" in ligne for ligne in sous_lignes), sous_lignes
    assert any("planche_03.tiff" in ligne for ligne in sous_lignes), sous_lignes


def test_la_file_en_attente_est_NOMMEE_fichier_par_fichier(tmp_path, banc):
    """AC 6.1 : « jamais reduite a un compte ».

    L'en-tete porte la mesure **et** le glyphe de l'etat ; les lignes suivantes
    portent les noms et le motif, lu verbatim du vocabulaire ferme du coeur.
    Le glyphe est verifie avec le compte, sans quoi un glyphe inverse -- le
    second canal de `DESIGN.md` section 6 disant le contraire du texte a cote de
    lui -- passerait inapercu.
    """
    lignes = _corps(banc, ecrans_du_scan(tmp_path)["E3-4"])
    entetes = [ligne for ligne in lignes
               if atelier_scan_parcours.LIBELLE_EN_ATTENTE in ligne]
    assert len(entetes) == 1, entetes
    assert jetons.glyphes(False)["absent"] in entetes[0], entetes[0]
    assert "3 fichiers non rattachés" in entetes[0], entetes[0]
    assert jetons.glyphes(False)["complete"] not in entetes[0], entetes[0]
    # Et au moins un fichier est NOMME sous l'en-tete.
    assert any("feuille_a.tiff" in ligne for ligne in lignes), lignes


def test_une_file_QUI_TIENT_nomme_TOUS_ses_fichiers(tmp_path, banc):
    """AC 6.1 sur la branche **non bornee** : quand la place suffit, tout est la.

    Le test precedent mesure la file coupee ; celui-ci mesure la file entiere,
    et les deux sont necessaires -- un `return` qui laisserait tomber les noms
    dans la seule branche large passerait sous la mesure de la branche etroite.
    Un seul lot, donc de la place : les trois fichiers sont nommes, un par un.
    """
    un_lot = [document
              for document in fabriques_du_rapport.documents_a_trois_lots()
              if document.subject.lot_id == fabriques_du_rapport.LOT_PREMIER]
    ecran = atelier_scan_parcours.EcranRapportDeDetection(
        atelier_scan_rapport.projeter(
            un_lot,
            partition=fabriques_du_rapport.partition_a_trois_entrees(),
            manifeste=fabriques_du_rapport.manifeste_a_trois_lots()),
        sur_issue=lambda _i: None, document="d.json")
    lignes = _corps(banc, ecran)
    for nom in ("feuille_a.tiff", "planche_07.tiff", "etranger.pdf"):
        assert any(nom in ligne for ligne in lignes), (nom, lignes)
    # Rien n'est coupe : aucune ligne de reste.
    assert not [ligne for ligne in lignes if ligne.strip().startswith("…")], \
        lignes


def test_une_file_VIDE_porte_le_glyphe_du_COMPLET_et_le_dit(tmp_path, banc):
    """Volet symetrique du precedent : le glyphe suit ce qu'il y a a dire.

    Sans lui, un glyphe fige sur `absent` serait vert sur `E3-4` et faux sur
    `E3-3`. `E3-3` est projete sans partition, donc sa file est vide -- et une
    ligne vide y serait illisible : l'operateur ne saurait pas si la question a
    ete posee.
    """
    lignes = _corps(banc, ecrans_du_scan(tmp_path)["E3-3"])
    entetes = [ligne for ligne in lignes
               if atelier_scan_parcours.LIBELLE_EN_ATTENTE in ligne]
    assert len(entetes) == 1, entetes
    assert jetons.glyphes(False)["complete"] in entetes[0], entetes[0]
    assert atelier_scan_rapport.AUCUN_FICHIER_EN_ATTENTE in entetes[0], \
        entetes[0]


def test_la_file_BORNEE_dit_combien_de_fichiers_elle_ne_montre_PAS(tmp_path,
                                                                   banc):
    """Couper est admis ; couper **en silence** ne l'est pas.

    La grille ne tient pas trois lots, leurs sous-lignes, trois fichiers en
    attente et trois issues. Ce sont les lots qui gagnent -- ils sont l'objet du
    jugement --, et la file dit alors combien de noms elle a laisses de cote.
    """
    lignes = _corps(banc, ecrans_du_scan(tmp_path)["E3-4"])
    restes = [ligne.strip() for ligne in lignes
              if ligne.strip().startswith("…")]
    assert len(restes) == 1, restes
    assert "2 autres fichiers" in restes[0], restes[0]
    # Le budget garde AU MOINS l'en-tete de la file : sans lui, l'ecran perdrait
    # la seule ligne qui dit qu'un reliquat existe.
    assert any(atelier_scan_parcours.LIBELLE_EN_ATTENTE in ligne
               for ligne in lignes), lignes


def test_les_LOTS_non_dessines_sont_COMPTES_plutot_que_tus(tmp_path, banc):
    """L'autre coupe, celle des lots -- et elle se dit aussi.

    Un vrac de dix lots ne tient dans aucune grille de 24 lignes. Ce qui n'est
    pas admissible est qu'il en montre quatre sans dire qu'il y en a six autres
    -- c'est litteralement le defaut que la 11.4b a paye trois fois, neuf
    planches evanouies et 288 tests verts.
    """
    documents = []
    for rang in range(10):
        documents.append(fabriques_du_rapport.document(
            f"lot_{rang:02d}", [fabriques_du_rapport.page(
                rang, page_index=0, page_count=1, lot_id=f"lot_{rang:02d}",
                frames=rang + 1)], pages_expected=1))
    # **Avec un reliquat**, et ce n'est pas decoratif : c'est la seule
    # disposition ou les lots ET la file se disputent la grille, donc la seule
    # ou l'on voit si chacun garde ce qui lui revient.
    ecran = atelier_scan_parcours.EcranRapportDeDetection(
        atelier_scan_rapport.projeter(
            documents,
            partition=fabriques_du_rapport.partition_a_trois_entrees()),
        sur_issue=lambda _i: None, document="d.json")
    hauteur, _etat, blocs = _monter(banc, ecran, False)
    lignes = [ligne for bloc in blocs for ligne in bloc.split("\n")]
    # La ligne qui dit le reste se **reserve** dans le budget : ajoutee apres
    # coup, elle deborderait la grille d'une ligne -- ou chasserait un lot deja
    # pose, ce qui rendrait le compte annonce faux d'une unite.
    assert hauteur <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteur
    # Et la file garde AU MOINS son en-tete : sans elle, l'ecran perdrait la
    # seule ligne qui dit qu'un reliquat existe.
    assert any(atelier_scan_parcours.LIBELLE_EN_ATTENTE in ligne
               for ligne in lignes), lignes
    restes = [ligne.strip() for ligne in lignes
              if ligne.strip().startswith("…")]
    assert len(restes) == 1, restes
    assert "autres lots" in restes[0], restes[0]
    # Le compte annonce est **exact** : autant de lots restants que de lots que
    # l'ecran n'a pas dessines.
    dessines = sum(1 for ligne in lignes
                   if any(f"lot_{rang:02d}" in ligne for rang in range(10)))
    assert f"{10 - dessines} autres lots" in restes[0], (dessines, restes[0])


def test_chaque_ISSUE_du_rapport_porte_son_A_COTE_avec_son_CHIFFRE_REEL(
        tmp_path, banc):
    """AC 6.5 : « le compte reel, jamais le compte attendu ».

    Le lot du milieu porte **3** frames reelles pour 62 attendues : un a-cote
    qui annoncerait l'attendu dirait a l'operateur qu'il va ecrire un lot
    complet. Les trois a-cotes sont mesures ensemble, en ensemble exact des
    issues -- une issue qui perdrait le sien ne se verrait pas autrement.
    """
    ecran = ecrans_du_scan(tmp_path)["E3-4"]
    lignes = _corps(banc, ecran)
    rendues = {issue.cle: None for issue in ecran.choix.issues}
    assert set(rendues) == {atelier_scan_rapport.ISSUE_ECRIRE,
                            atelier_scan_rapport.ISSUE_COMPLETER,
                            atelier_scan_rapport.ISSUE_ANNULER}
    portante = [ligne for ligne in lignes
                if atelier_scan_rapport.LIBELLE_ECRIRE_QUAND_MEME in ligne]
    assert len(portante) == 1, portante
    assert f"{fabriques_du_rapport.LOT_INCOMPLET} sera écrit incomplet" in \
        portante[0], portante[0]
    assert "3 frames" in portante[0] and "62" not in portante[0], portante[0]
    # Les deux autres portent le leur aussi : sans ce volet, un a-cote unique
    # suffirait a rendre le test vert.
    assert any(atelier_scan_rapport.A_COTE_ANNULER in ligne
               for ligne in lignes), lignes
    assert any("planche_03" in ligne
               and atelier_scan_rapport.LIBELLE_COMPLETER_LE_QR in ligne
               for ligne in lignes), lignes
