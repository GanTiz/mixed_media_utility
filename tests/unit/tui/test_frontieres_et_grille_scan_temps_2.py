# -*- coding: utf-8 -*-
"""Story 11.6, lot H -- frontieres, grille et cablage du TEMPS 2 du Scan.

Ce banc mesure ce qu'aucun des lots C a G ne pouvait mesurer seul : **le
paquet**, et **la chaine**. Les cinq autres bancs du temps 2 ont chacun leur
module ; celui-ci a la couture entre eux, et le fichier lui est propre --
« aucun lot ne partage un fichier de banc avec un autre ».

**Le mode de panne central, et il a un compte de sept.** Un ecran livre, teste,
exporte -- et cable **nulle part** dans l'application. Le temps 2 etait dans cet
etat exact avant ce lot : six ecrans livres, et deux `EcranPasEncore` a leur
place dans le produit. Aucun banc unitaire ne peut voir ce defaut -- un banc
injecte le rappel lui-meme --, il faut monter **l'application**.

**Ce que ce banc ne reecrit pas.** Les mesures de sobriete, de vocabulaire de
touche, de completion de chemin et de glyphes vivent deja dans le depot, chacune
une fois, et elles sont **importees** :

* `test_sobriete_et_grille_extraction` porte le lexique des touches, des
  conseils et des motifs de conception, et la table des glyphes ;
* `test_projets` porte la frontiere de la completion de **chemin**, resserree
  par `EPIC11-ARB-127` sur la **chose** et non sur le mot ;
* `outils_frontiere` porte la lecture d'AST.

Les fabriques viennent de meme des bancs des lots C a G : elles placent deja
leur cible **au milieu** de trois elements distinguables, et une seconde
fabrique divergerait de celle-la a la premiere retouche du coeur.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import scan_calibrate, scan_write
from mixed_media_utility.tui import (
    atelier_scan,
    atelier_scan_calibrate,
    atelier_scan_calibration,
    atelier_scan_confirmation,
    atelier_scan_ecriture,
    atelier_scan_rapport,
    atelier_scan_parcours,
    atelier_scan_resultat,
    jetons,
)
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import SurfaceExecution

from outils_frontiere import chaines_de_code, identifiants
# Les fabriques des lots C a G, LUES et non recopiees.
import test_atelier_scan_calibrate_tui as fabriques_de_calibrate
import test_atelier_scan_calibration_tui as fabriques_de_calibration
import test_atelier_scan_confirmation as fabriques_de_confirmation
import test_atelier_scan_ecriture as fabriques_d_ecriture
import test_atelier_scan_resultat as fabriques_du_resultat
# Le lexique de sobriete et la table des glyphes du lot G de la 11.4.
from test_sobriete_et_grille_extraction import (
    ecarts_de_sobriete,
    glyphes_hors_table,
)
# La frontiere de la completion de CHEMIN, resserree par `EPIC11-ARB-127`.
from test_projets import _occurrences_de_completion_de_chemin
# Les fabriques de documents ECRITS du lot F de la 11.5 : elles rendent
# relisibles par le coeur les documents que le lot D projette en memoire.
import test_frontieres_et_grille_scan as fabriques_du_temps_1

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le paquet mesure.
PAQUET_TUI = Path(_SRC) / "mixed_media_utility" / "tui"

#: **Les modules du temps 2**, nommes un par un. La frontiere de paquet de la
#: 11.4b les couvre deja ; l'AC 9.1 demande quand meme la mesure nommee, et elle
#: a raison -- une frontiere de paquet reste verte le jour ou un module sort du
#: paquet, et celle-ci nomme lequel. `atelier_scan_parcours` y est parce que
#: **c'est lui qui cable** : le cablage est ce que ce lot ajoute, donc ce que ce
#: lot doit mesurer.
MODULES_DU_TEMPS_2 = (
    "atelier_scan_calibrate.py",
    "atelier_scan_calibration.py",
    "atelier_scan_confirmation.py",
    "atelier_scan_ecriture.py",
    "atelier_scan_parcours.py",
    "atelier_scan_resultat.py",
)


# ===========================================================================
# Le corpus des SIX ecrans du temps 2
#
# Chaque entree est une **fabrique qui monte l'ecran dans l'application** et non
# un ecran deja construit : `E3-7` et `E3-8` ne sont completement eux-memes
# qu'apres montage -- le premier abonne sa surface aux jalons a `on_mount`, le
# second recoit sa ligne d'etat apres `descendre`. Un corpus d'objets nus les
# mesurerait a moitie.
# ===========================================================================

def _projet_a_trois_profils(tmp_path):
    """Le projet du lot C : trois profils, la cible **au milieu**, un defaut."""
    return fabriques_de_calibration._projet(
        tmp_path, rang_du_defaut=fabriques_de_calibration.RANG_DE_LA_CIBLE)


def _journal_peuple():
    """Un journal qui porte des lignes : `E3-8` n'annonce `Tab` que s'il en a un.

    Trois lignes **distinctes**, et la cible au milieu : un journal rempli d'une
    valeur uniforme laisserait passer un affichage qui ne rendrait que la
    premiere.
    """
    surface = SurfaceExecution(unite=atelier_scan_ecriture.UNITE)
    for ligne in ("correction ajustee sur la page de calibration",
                  "recadrage de la planche 2 sur 3",
                  "12 frames ecrites"):
        surface.journal.inscrire(ligne)
    return surface.journal


def _monter_E3_5(app, tmp_path):
    ecran = atelier_scan_calibration.EcranChoixDeCalibration(
        _projet_a_trois_profils(tmp_path), retenir=lambda _r: None, lots=3,
        dpi_du_scan=fabriques_de_calibration.DPI_DU_SCAN_DIVERGENT)
    app.descendre(ecran)
    return ecran


def _monter_E3_6(app, _tmp_path):
    plan = fabriques_de_confirmation.plan_nominal(
        calibration=fabriques_de_calibration.PROFILS[
            fabriques_de_calibration.RANG_DE_LA_CIBLE]["source"])
    ecran = atelier_scan_confirmation.EcranScanConfirmation(
        plan, sur_issue=lambda _i: None)
    app.descendre(ecran)
    return ecran


def _monter_E3_7(app, tmp_path):
    plan = fabriques_d_ecriture.plan_de_trois_lots(
        tmp_path, frames_sur_le_disque=(2, 7, 3))
    ecran = atelier_scan_ecriture.ouvrir_l_ecriture(app, plan)
    # Un jalon **au milieu** de la passe : ni zero, ni le total. Une barre qui
    # ne dessinerait que ses extremites passerait sur les deux autres.
    ecran.surface.noter(7, 15)
    return ecran


def _monter_E3_8(app, tmp_path):
    rapport = fabriques_du_resultat.rapport_de_trois_lots(tmp_path)
    return atelier_scan_resultat.ouvrir_le_resultat(
        app, rapport, journal=_journal_peuple(), duree=754.0, attendues=200,
        sur_suite=lambda _s: None)


def _monter_E3_9(app, tmp_path):
    ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
        fabriques_de_calibrate._projet(tmp_path),
        calibrer=lambda _formulaire: None)
    app.descendre(ecran)
    return ecran


def _monter_T6_1(app, tmp_path):
    plan = fabriques_d_ecriture.plan_de_trois_lots(
        tmp_path, frames_sur_le_disque=(2, 7, 3))
    ecran = atelier_scan_ecriture.ouvrir_l_ecriture(app, plan)
    app.tache_en_cours = True
    return ecran.ouvrir_l_interruption()


#: Les six fabriques, indexees par le nom de leur **maquette** : c'est elle que
#: l'AC 9.3 designe, et un corpus indexe par nom de classe ne dirait pas lequel
#: des six manque.
FABRIQUES = {
    "E3-5": _monter_E3_5,
    "E3-6": _monter_E3_6,
    "E3-7": _monter_E3_7,
    "E3-8": _monter_E3_8,
    "E3-9": _monter_E3_9,
    "T6-1": _monter_T6_1,
}

#: Les six noms, ecrits **en clair** a cote du corpus. Une constante comparee a
#: elle-meme ne mesurerait rien (piege du test tautologique, story 5.9).
MAQUETTES_DU_TEMPS_2 = ("E3-5", "E3-6", "E3-7", "E3-8", "E3-9", "T6-1")

#: La cible des mesures parametrees. **Jamais la premiere du corpus** : les six
#: y passent une par une.
CIBLES = [pytest.param(nom, id=nom) for nom in MAQUETTES_DU_TEMPS_2]


def _coque(ascii_seul: bool = False, paliers: int = 2) -> CoqueTui:
    """Une coque a paliers temoins, montee au **plancher** par le banc.

    Deux au minimum -- l'ecran projet et le menu des ateliers --, parce que le
    retour au menu des ateliers (`EPIC11-ARB-13`) ne se distingue d'un retour a
    la racine que si la racine existe a cote.
    """
    noms = ["Projet", "Ateliers", "E3-0 menu", "E3-1 depot", "E3-3 rapport"]
    return CoqueTui(
        paliers=[PalierTemoin(nom, "⏎ entrer  Q quitter")
                 for nom in noms[:paliers]],
        contexte=Contexte(projet="projet_demo"), ascii_seul=ascii_seul)


def _monter(banc, nom, tmp_path, ascii_seul):
    """Monter l'ecran nomme **au plancher** et rendre ce qu'il dessine.

    Rend le triplet que les mesures de ce banc consomment : la hauteur
    reellement occupee par la zone centrale, la ligne d'etat, et le texte de
    tous les blocs affiches.
    """
    app = _coque(ascii_seul)

    async def scenario(pilote):
        FABRIQUES[nom](pilote.app, tmp_path)
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


def test_le_corpus_porte_EXACTEMENT_les_SIX_ecrans_du_temps_2():
    """Volet symetrique du corpus, et il vient en premier.

    Une mesure parametree sur un corpus ampute serait verte pour tous les
    ecrans qui restent. L'ensemble est donc mesure **exactement**, pas par
    inclusion : un septieme ecran ajoute sans etre mesure fait rougir ici, et un
    sixieme retire aussi.
    """
    assert set(FABRIQUES) == set(MAQUETTES_DU_TEMPS_2)
    # Six, ecrit en clair : `len(corpus) == len(corpus)` ne mesure rien.
    assert len(MAQUETTES_DU_TEMPS_2) == 6


def test_les_SIX_maquettes_du_temps_2_EXISTENT_a_leur_source():
    """L'autre moitie : chacun des six ecrans a bien une maquette validee.

    Un corpus d'ecrans qui ne correspondrait a aucune maquette mesurerait la
    conformite d'un dessin que personne n'a valide.
    """
    maquettes = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
                 / "ux-tui-2026-08-27" / "maquettes")
    manquantes = [nom for nom in MAQUETTES_DU_TEMPS_2
                  if not list(maquettes.glob(f"{nom}-*.txt"))]
    assert manquantes == [], manquantes


# ===========================================================================
# H1 -- le CABLAGE : plus aucun `EcranPasEncore` dans l'atelier Scan
# ===========================================================================

def _projet(tmp_path):
    """Le dossier de projet du parcours, avec ses trois documents ecrits."""
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    return projet, fabriques_du_temps_1._ecrire_les_documents(projet)


def _parcours_cable(tmp_path, app, **doubles):
    """Un `ParcoursScan` dont les documents sont **relus du disque**."""
    projet, chemins = _projet(tmp_path)
    parcours = atelier_scan_parcours.ParcoursScan(app, projet, **doubles)
    parcours.documents = atelier_scan_parcours.documents_relus(chemins)
    return parcours


#: Ce que **chaque geste de l'atelier Scan** ouvre, en table FERMEE. Une
#: assertion positive sur le seul geste qu'on vient de cabler laisserait les
#: autres deriver ; c'est l'ensemble qui se mesure, et son unicite avec lui.
#:
#: Les deux entrees du menu et les quatre issues du rapport y sont : ce sont les
#: seuls gestes de l'atelier qui **descendent**. « Annuler » n'y est pas, elle
#: remonte -- et le banc du temps 1 la mesure deja.
#: Les cles viennent des **constantes**, jamais recopiees : le lot D de la 11.5
#: a du renommer `ISSUE_COMPLETER` pour passer sous la frontiere de la
#: completion de chemin, et une cle ecrite en clair ici aurait survecu au
#: renommage en mesurant un geste qui n'existe plus.
CE_QU_OUVRE_CHAQUE_GESTE = {
    f"menu:{atelier_scan.CLE_DE_LA_DETECTION}": "EcranScanDepot",
    f"menu:{atelier_scan_calibration.CLE_DE_LA_CALIBRATION}":
        "EcranCalibrerLaChaine",
    f"rapport:{atelier_scan_rapport.ISSUE_ECRIRE}": "EcranChoixDeCalibration",
    f"rapport:{atelier_scan_rapport.ISSUE_COMPLETER}": "EcranCompletionQr",
}


@pytest.mark.parametrize("geste", sorted(CE_QU_OUVRE_CHAQUE_GESTE))
def test_AUCUN_geste_de_l_atelier_Scan_ne_mene_a_PAS_ENCORE(tmp_path, banc,
                                                            geste):
    """H1 : les six ecrans du temps 2 sont **atteignables depuis le produit**.

    Le defaut que cette mesure ferme a un compte de sept dans cet epic : un
    ecran livre, teste, exporte -- et cable nulle part. Aucun banc unitaire ne
    peut le voir, parce qu'un banc injecte lui-meme le rappel qui manque.

    Chaque geste part d'un parcours **neuf** : la remontee ne se fait pas au
    meme cran selon que l'ecran ouvert est un palier ou un passage, et les
    gestes suivants partiraient d'un etat different.
    """
    app = _coque()
    parcours = _parcours_cable(tmp_path, app)
    famille, cle = geste.split(":")
    entrees = {entree.cle: entree for entree in atelier_scan.ENTREES_DU_MENU}

    async def scenario(pilote):
        if famille == "menu":
            # La pile du produit : l'atelier se monte SUR le menu des
            # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
            # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
            # mesure sur une pile que le produit ne construit jamais.
            pilote.app.descendre()
            await pilote.pause()
            parcours.ouvrir()
            await pilote.pause()
            parcours.entrer(entrees[cle])
        else:
            ecran = parcours.montrer_le_rapport()
            await pilote.pause()
            issues = {issue.cle: issue for issue in ecran.choix.issues}
            assert cle in issues, (cle, sorted(issues))
            parcours.juger(issues[cle])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert not isinstance(ecran, EcranPasEncore), geste
    assert type(ecran).__name__ == CE_QU_OUVRE_CHAQUE_GESTE[geste], geste


def test_la_table_des_GESTES_couvre_l_atelier_ENTIER(tmp_path, banc):
    """Volet symetrique de la table : elle porte **exactement** les gestes qui
    descendent, jamais un sous-ensemble.

    Sans lui, une troisieme entree de menu ou une cinquieme issue de rapport
    resterait hors mesure, et la table ci-dessus serait verte en ne regardant
    plus tout.
    """
    app = _coque()
    parcours = _parcours_cable(tmp_path, app)

    async def scenario(pilote):
        ecran = parcours.montrer_le_rapport()
        await pilote.pause()
        return {issue.cle for issue in ecran.choix.issues}

    issues = banc(app, scenario)
    gestes = {f"menu:{entree.cle}" for entree in atelier_scan.ENTREES_DU_MENU}
    gestes |= {f"rapport:{cle}" for cle in issues
               # « Annuler » remonte, elle n'ouvre rien : elle est mesuree par
               # le banc du temps 1, la ou elle est nee.
               if cle != atelier_scan_rapport.ISSUE_ANNULER}
    assert gestes == set(CE_QU_OUVRE_CHAQUE_GESTE), sorted(
        gestes ^ set(CE_QU_OUVRE_CHAQUE_GESTE))


def test_la_mesure_de_PAS_ENCORE_MORD_sur_une_application_NUE(banc):
    """Volet symetrique, et il est la moitie qui manque le plus souvent.

    Sans lui, « aucun `EcranPasEncore` » serait vert sur une application qui
    n'ouvrirait **rien du tout** -- une application sans palier, ou un parcours
    dont tous les gestes seraient muets, passerait pour conforme. On mesure donc
    que l'ecran existe encore, qu'il est atteignable, et que le predicat le
    reconnait.
    """
    app = _coque(paliers=1)

    async def scenario(pilote):
        # Descendre sous le dernier palier : la coque monte alors l'ecran qui
        # NOMME l'absence. C'est le regime que la mesure ci-dessus doit voir.
        pilote.app.descendre()
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, EcranPasEncore)
    assert ecran.quand == CoqueTui.QUAND_ARRIVENT_LES_ATELIERS


def test_les_DEUX_constantes_d_echeance_du_temps_2_ont_DISPARU():
    """H2 : « une constante d'echeance qui survit a l'echeance ment ».

    `QUAND_LE_TEMPS_2` nommait « l'ecriture des frames du Scan (story 11.6) » et
    `QUAND_LA_CALIBRATION` « l'ecriture du Scan » : les deux echeances sont
    echues, les six ecrans sont livres et cables. Les constantes partent **avec
    leur dernier usage**, et la mesure porte sur le paquet entier -- une
    constante retiree d'un module et recopiee dans un autre ne serait pas un
    retrait.
    """
    fautives = [fichier.name for fichier in sorted(PAQUET_TUI.glob("*.py"))
                for chaine in identifiants(fichier)
                if chaine in ("QUAND_LE_TEMPS_2", "QUAND_LA_CALIBRATION")]
    assert fautives == [], fautives


def test_le_MECANISME_de_l_echeance_n_a_PAS_disparu_avec_elles():
    """Volet symetrique du precedent : on retire une promesse echue, pas l'outil.

    `EcranPasEncore` reste, et il reste **capable de dire une echeance** : c'est
    ce qui permettra a « Recalibrer un lot ecrit » de revenir au menu le jour ou
    une story de coeur livrera la commande (`EPIC11-ARB-101`, note 2). Sans ce
    volet, un retrait qui aurait emporte le mecanisme passerait pour un menage.
    """
    ecran = EcranPasEncore("Recalibrer un lot écrit", "une story de cœur")
    lignes = ecran.lignes()
    assert any("une story de cœur" in ligne for ligne in lignes), lignes
    # Et sans echeance, la ligne est **absente** -- ce qui est exactement
    # l'ambiguite que l'invariant d'`EntreeDeMenu` ferme en amont.
    assert len(EcranPasEncore("X").lignes()) == len(lignes) - 1


# ===========================================================================
# H1 (suite) -- la CHAINE de bout en bout, et ce qu'elle TRANSPORTE
#
# Les mesures ci-dessus disent que la chaine mene quelque part ; celles-ci
# disent qu'elle y mene avec les BONNES valeurs. C'est la seconde moitie du
# cablage, et c'est celle que la 11.5 a payee en vingt et un mutants.
# ===========================================================================

class EcritureFeinte:
    """Le `ecrire_depuis_le_document` du banc : il emet un jalon, et rend.

    Il porte la **meme signature** que le point d'entree du coeur, mots-cles
    compris et **sans `**kwargs`**. Un faux qui accepterait `**kwargs`
    laisserait passer un appel dont un mot-cle est mal nomme, c'est-a-dire
    exactement la panne que le lot `H1` de la 11.4 a payee (`logger` non passe,
    `AttributeError` a la premiere ligne du coeur).
    """

    def __init__(self) -> None:
        self.appels: list[dict] = []

    def __call__(self, project_dir, document_path, *, overwrite=False,
                 logger=None, appliquer_la_correction=True, livrer_brut=False,
                 divergence_bypass=False, profil_designe=None,
                 origine_du_profil=None, nouvelle_version=False,
                 manifest_du_projet=None, rappel_progression=None,
                 annoncer_la_completude=None,
                 demander_l_application_de_la_correction=None,
                 confirmer_l_ecrasement=None):
        lot_id = Path(document_path).stem
        self.appels.append({
            "project_dir": project_dir, "document_path": Path(document_path),
            "lot_id": lot_id, "overwrite": overwrite, "logger": logger,
            "appliquer_la_correction": appliquer_la_correction,
            "divergence_bypass": divergence_bypass,
            "livrer_brut": livrer_brut, "profil_designe": profil_designe,
            "origine_du_profil": origine_du_profil,
            "nouvelle_version": nouvelle_version,
            "manifest_du_projet": manifest_du_projet,
            "rappel_progression": rappel_progression,
        })
        if rappel_progression is not None:
            rappel_progression(1, 1)
        # Un **vrai** `EcritureDuLot`, avec sa persistance : `E3-8` lit
        # `persisted.findings`, et un double a attributs libres rendrait vert un
        # accesseur mal nomme. Les deux fabriques viennent du banc du lot F.
        return scan_write.EcritureDuLot(
            persisted=fabriques_du_resultat.persistance(lot_id),
            output=fabriques_du_resultat.rapport_de_sortie(
                lot_id, ecrites=1, dossier=f"output-frames/{lot_id}"),
            lot_correction=None, correction_appliquee=False,
            profil_de_chaine_utilise=False)


def _projet_avec_profils_et_documents(tmp_path):
    """Un projet **reel** : trois profils (la cible au milieu, elle est le
    defaut) et les trois documents de detection ecrits sur son disque."""
    projet = _projet_a_trois_profils(tmp_path)
    fabriques_du_temps_1._ecrire_les_documents(projet)
    return projet


def _dernier_ecran_de(pilote):
    return pilote.app.screen


def _derouler_le_temps_2(banc, tmp_path, *, aucune: bool = False):
    """`E3-4` -> `E3-5` -> `E3-6` -> `E3-7` -> `E3-8`, par le CLAVIER.

    Chaque franchissement passe par `traiter`, jamais par un appel direct au
    rappel : un cablage mesure en appelant soi-meme la methode cablee ne mesure
    que la methode. Le seul appel direct est celui de la premiere issue --
    `EcranChiffre` la valide par le curseur, et le curseur ne se pose jamais
    sur une issue qui ecrit (`EPIC11-ARB-7`), donc on l'y **deplace**.
    """
    projet = _projet_avec_profils_et_documents(tmp_path)
    app = _coque()
    feinte = EcritureFeinte()
    parcours = atelier_scan_parcours.ParcoursScan(app, projet, ecriture=feinte)
    parcours.documents = atelier_scan_parcours.documents_relus(
        sorted((projet / "versions" / "detection").glob("*.json")))
    parcours.dpi = fabriques_de_calibration.DPI_DU_SCAN_DIVERGENT
    etapes = []

    async def scenario(pilote):
        rapport = parcours.montrer_le_rapport()
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)
        issues = {issue.cle: issue for issue in rapport.choix.issues}
        parcours.juger(issues[atelier_scan_rapport.ISSUE_ECRIRE])
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)

        choix = pilote.app.screen
        if aucune:
            while choix.choix.courante.cle != atelier_scan_calibration.CLE_AUCUNE:
                assert choix.traiter("down")
        choix.traiter("enter")
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)

        confirmation = pilote.app.screen
        while (confirmation.choix.issues[confirmation.choix.curseur].cle
               != atelier_scan_confirmation.ISSUE_ECRIRE):
            assert confirmation.traiter("up")
        confirmation.traiter("enter")
        await pilote.pause()
        await pilote.pause()
        etapes.append(type(pilote.app.screen).__name__)
        return etapes, parcours, feinte

    return banc(app, scenario)


def test_le_temps_2_va_de_E3_4_a_E3_8_SANS_un_seul_ecran_manquant(tmp_path,
                                                                  banc):
    """Les quatre franchissements en un seul test, et c'est delibere.

    Chacun d'eux a ete un rappel non cable ailleurs dans cet epic ; les mesurer
    separement ferait quatre tests qui montent la meme chaine, et aucun ne
    dirait que la chaine tient d'un bout a l'autre.
    """
    etapes, parcours, feinte = _derouler_le_temps_2(banc, tmp_path)
    assert etapes == ["EcranRapportDeDetection", "EcranChoixDeCalibration",
                      "EcranScanConfirmation", "EcranResultatDuScan"], etapes
    # Le coeur a bien ete appele **une fois par lot**, et dans l'ordre du
    # RAPPORT -- qui est celui du tri du coeur, jamais un ordre recompose au
    # cablage. C'est cet ordre-la qu'on compare, pas une liste ecrite a la main
    # : trois lots ranges autrement rendraient une egalite fausse pour une
    # bonne raison, et on ajusterait le test au code.
    assert [appel["lot_id"] for appel in feinte.appels] == [
        lot.lot_id for lot in parcours.rapport.lots], feinte.appels
    assert len({appel["lot_id"] for appel in feinte.appels}) == 3


def test_le_profil_retenu_en_E3_5_arrive_TEL_QUEL_au_coeur(tmp_path, banc):
    """Les deux champs de `CalibrationRetenue` partent a leurs deux mots-cles.

    Le curseur de `E3-5` part sur le **profil par defaut du projet** : c'est la
    proposition, et `⏎` la retient. Ce qui est mesure ici est qu'elle arrive au
    coeur **sans etre recomposee** -- le chemin resolu par le registre, et
    l'origine du geste avec lui, pour le journal.
    """
    _etapes, _parcours, feinte = _derouler_le_temps_2(banc, tmp_path)
    designes = {appel["profil_designe"] for appel in feinte.appels}
    assert len(designes) == 1, designes
    chemin = designes.pop()
    assert chemin is not None
    assert Path(chemin).is_file(), chemin
    assert all(appel["livrer_brut"] is False for appel in feinte.appels)
    assert {appel["origine_du_profil"] for appel in feinte.appels} == {
        atelier_scan_parcours.ORIGINE_DU_PROFIL}


def test_l_entree_AUCUNE_livre_le_lot_BRUT_et_ne_designe_AUCUN_profil(tmp_path,
                                                                      banc):
    """Volet symetrique du precedent, et il porte l'autre champ.

    Sans lui, un cablage qui passerait **toujours** le profil par defaut serait
    vert : les deux regimes rendent un lot ecrit, et seule la valeur des deux
    mots-cles les distingue. Un profil vide serait une correction identite,
    c'est-a-dire une correction *appliquee*, et le manifeste la declarerait
    comme telle.
    """
    _etapes, _parcours, feinte = _derouler_le_temps_2(banc, tmp_path,
                                                      aucune=True)
    assert [appel["livrer_brut"] for appel in feinte.appels] == [True] * 3
    assert [appel["profil_designe"] for appel in feinte.appels] == [None] * 3
    assert [appel["origine_du_profil"] for appel in feinte.appels] == [None] * 3


#: L'ensemble **EXACT** des mots-cles que le cablage transmet au coeur. Il
#: mesure deux choses a la fois, et la seconde est celle qui compte :
#:
#: * ce qui part **part** -- le logger sans lequel le coeur tombe a sa premiere
#:   ligne (finding `H1` de la 11.4), le canal de progression sans lequel la
#:   barre reste figee ;
#: * ce qui **ne part pas** : il n'y a **aucun** mot-cle de nom de lot ni de
#:   slug d'ingest, parce que `ecrire_depuis_le_document` n'en a aucun. C'est
#:   l'ecart remonte par le lot D, et il appartient a Egan. L'ensemble exact est
#:   ce qui fait qu'il ne peut pas rester tu : le jour ou le coeur gagnera ce
#:   parametre, cette frontiere rougira.
MOTS_CLES_TRANSMIS_AU_COEUR = {
    "overwrite", "logger", "appliquer_la_correction", "livrer_brut",
    "divergence_bypass", "profil_designe", "origine_du_profil",
    "nouvelle_version", "manifest_du_projet", "rappel_progression",
}


def test_AUCUN_nom_ne_part_de_E3_6_vers_le_coeur(tmp_path, banc):
    """L'ecart du lot D, **tranche** depuis (`EPIC11-ARB-141`).

    Il portait sur des noms EDITES, retenus par le parcours et qui s'arretaient
    la. Egan a retire l'edition plutot que de garder le champ : il n'y a plus de
    nom a retenir, `slugs_retenus` a disparu du parcours et de l'ecran, et les
    trois lots partent au coeur sous leur identite seule.

    **L'ensemble EXACT des mots-cles reste, INCHANGE, et c'est tout le sujet**
    (AC 7.3) : c'est lui qui rougira le jour ou `ecrire_depuis_le_document`
    gagnera un parametre de nom, et c'est ce qui rend le report reversible sans
    dette cachee. Une assertion positive (« le logger part bien ») laisserait
    passer un mot-cle de nom apparu entre-temps.
    """
    _etapes, parcours, feinte = _derouler_le_temps_2(banc, tmp_path)
    assert not hasattr(parcours, "slugs_retenus"), (
        "le parcours retient encore un nom que le coeur ne prend pas")
    # Les trois lots partent, et ils sont **distincts** : un appariement fautif
    # rendrait le meme succes apparent avec trois fois le meme lot.
    lots = [appel["lot_id"] for appel in feinte.appels]
    assert len(set(lots)) == 3, lots
    transmis = set(feinte.appels[0]) - {
        "project_dir", "document_path", "lot_id"}
    assert transmis == MOTS_CLES_TRANSMIS_AU_COEUR, sorted(
        transmis ^ MOTS_CLES_TRANSMIS_AU_COEUR)


def test_un_lot_SANS_document_AU_MILIEU_ne_fait_pas_disparaitre_les_SUIVANTS(
        tmp_path, banc):
    """La famille `continue` -> `break` de la 11.4b, sur la boucle du plan.

    Le lot sans document est **au milieu** de trois, et c'est la seule position
    qui demasque les deux fautes a la fois : en premiere position un `break`
    rendrait un plan vide (visible autrement), en derniere il ne changerait
    rien. Au milieu, il fait disparaitre le troisieme lot **en silence** -- ni
    frames, ni refus, et tout reste vert.
    """
    projet = _projet_avec_profils_et_documents(tmp_path)
    app = _coque()
    parcours = atelier_scan_parcours.ParcoursScan(app, projet)
    parcours.documents = atelier_scan_parcours.documents_relus(
        sorted((projet / "versions" / "detection").glob("*.json")))
    lots = list(fabriques_de_confirmation.rapport_a_trois_lots().lots)
    connus = [entree[2].subject.lot_id for entree in parcours.documents]
    confirme = atelier_scan_confirmation.PlanDEcriture(lots=tuple(
        atelier_scan_confirmation.LotAEcrire(
            lot_id=lot_id, slug=f"slug_{lot_id}", frames=rang + 2,
            frames_attendues=rang + 2)
        for rang, lot_id in enumerate(
            [connus[0], "lot_sans_document", connus[2]])))
    assert len(confirme.lots) == 3 and len(lots) == 3

    plan = parcours.plan_d_ecriture(confirme)

    assert [lot.lot_id for lot in plan.lots] == [connus[0], connus[2]], plan


# ===========================================================================
# H1 (suite) -- LE POINT DUR : une question posee PAR LE COEUR, DEPUIS
# l'interieur de l'ecriture, a laquelle un ecran repond.
#
# `io.calibration_profile.write_profile` appelle `confirm_overwrite` dans sa
# propre pile d'appel, et `executer_en_processus` est un appel direct. Rejouer
# la passe n'est pas une issue : `ingest_scan_lot` a deja ecrit dans le projet
# quand la question arrive. Le mecanisme retenu -- un fil de travail, et un
# `threading.Event` -- est donc mesure ici, aux deux etages : la piece seule,
# puis la chaine entiere.
# ===========================================================================

def test_la_QUESTION_bloque_le_FIL_qui_la_pose_et_rend_la_REPONSE(tmp_path):
    """L'etage du mecanisme, mesure avec de **vrais fils** et non un double.

    Deux fils, comme en production : celui qui pose la question -- le fil de
    travail ou tourne le coeur -- et celui qui repond -- la boucle. Le premier
    doit **bloquer** jusqu'a ce que le second reponde, et rendre exactement ce
    qu'il a repondu.

    Le test mesure aussi que le blocage a bien eu lieu : sans lui, une question
    qui rendrait son defaut sans attendre passerait -- et en production elle
    ferait ecrire (ou ne pas ecrire) sans que personne n'ait repondu.
    """
    pose = threading.Event()
    rendus = []
    repondeurs = []

    def poser(collision, repondre):
        pose.set()
        repondeurs.append((collision, repondre))

    question = atelier_scan_parcours.QuestionDeCollision(poser)
    collision = atelier_scan_calibrate.CollisionDeProfil(
        occupant="900-png-cccccccccccc", radical="beta")

    fil = threading.Thread(
        target=lambda: rendus.append(question.demander(collision)))
    fil.start()
    assert pose.wait(5), "la question n'a jamais ete posee"
    # **Le fil est encore vivant** : c'est la mesure du blocage. Une question
    # qui rendrait sans attendre aurait deja termine ce fil.
    fil.join(timeout=0.2)
    assert fil.is_alive(), "le fil n'a pas attendu la reponse"
    assert rendus == []

    _collision, repondre = repondeurs[0]
    repondre(atelier_scan_calibrate.CLE_ECRASER)
    fil.join(timeout=5)
    assert not fil.is_alive(), "le fil n'a pas ete libere par la reponse"
    assert rendus == [atelier_scan_calibrate.CLE_ECRASER]
    assert question.reponse == atelier_scan_calibrate.CLE_ECRASER


def test_la_PREMIERE_reponse_gagne_et_le_defaut_n_ECRASE_rien():
    """Les deux proprietes qui rendent le filet du demontage inoffensif.

    Le demontage de l'ecran de collision repond `annuler` -- c'est ce qui
    empeche un `Échap` de laisser le fil de travail attendre pour toujours.
    Cette reponse-la ne doit jamais **ecraser** celle qu'une issue vient de
    poser : sinon un operateur qui a choisi « ecraser » verrait son choix
    silencieusement retourne, ce qui n'est ni la destruction consciente qu'il a
    demandee ni un refus qui se nomme.

    Et le defaut, avant toute question, est l'issue qui **n'ecrit pas** : un
    defaut a « ecraser » ferait d'une panne de cablage une destruction.
    """
    reponses = []

    def poser(_collision, repondre):
        repondre(atelier_scan_calibrate.CLE_ECRASER)
        repondre(atelier_scan_calibrate.CLE_ANNULER)
        reponses.append("posee")

    question = atelier_scan_parcours.QuestionDeCollision(poser)
    assert question.reponse == atelier_scan_calibrate.CLE_ANNULER
    assert question.demander(None) == atelier_scan_calibrate.CLE_ECRASER
    assert reponses == ["posee"]
    # Et la table du coeur traduit bien la cle qui n'ecrit pas en « n'ecris
    # rien » : la mesure est LUE du lot G, jamais recopiee ici.
    assert atelier_scan_calibrate.REPONSE_DES_ISSUES[
        atelier_scan_calibrate.CLE_ANNULER] is None
    assert atelier_scan_calibrate.REPONSE_DES_ISSUES[
        atelier_scan_calibrate.CLE_ECRASER] is True


class CalibrationFeinte:
    """Le `calibrer_la_chaine` du banc : il pose la question du coeur, et rend.

    Il porte la **meme signature** que le point d'entree du coeur, mots-cles
    compris et sans `**kwargs` -- un faux permissif laisserait passer un appel
    dont un mot-cle est mal nomme.

    Il appelle `confirmer_l_ecrasement` **exactement la ou le coeur l'appelle** :
    depuis l'interieur de la passe, dans sa propre pile d'appel. C'est ce qui
    fait de ce double une mesure du mecanisme et non de son imitation.
    """

    CHAINE = "600-tiff-dddddddddddd"

    def __init__(self, *, collision=None, leve=None) -> None:
        self.collision = collision
        self.leve = leve
        self.appels: list[dict] = []
        self.ecrase = None
        self.nomme = None

    def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                 demander_le_nom_et_le_commentaire=None,
                 confirmer_l_ecrasement=None, rappel_progression=None):
        # **Le double suit le contrat du COEUR, mot-cle pour mot-cle.** Le lot
        # J1 a ajoute `rappel_progression` a `calibrer_la_chaine` ; un double
        # qui ne l'accepte pas leve un `TypeError` DANS le fil de travail, et
        # ce que le banc mesure alors est son propre double. C'est le prix a
        # payer d'un double, et la contrepartie de sa vitesse : il faut le
        # tenir a jour, sans quoi il mesure une fonction qui n'existe plus.
        self.appels.append({"project_dir": project_dir, "scan_path": scan_path,
                            "dpi": dpi, "logger": logger,
                            "rappel_progression": rappel_progression})
        if demander_le_nom_et_le_commentaire is not None:
            self.nomme = demander_le_nom_et_le_commentaire(self.CHAINE)
        if self.collision is not None and confirmer_l_ecrasement is not None:
            self.ecrase = confirmer_l_ecrasement(*self.collision)
        if self.leve is not None:
            raise self.leve
        chemin = (Path(project_dir) / "versions" / "calibration"
                  / "profil-de-banc.json")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{}", encoding="utf-8")
        return scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id=self.CHAINE, etiquette="beta",
            commentaire="", lot_correction=None, document={})


async def _tant_que(pilote, condition, tours: int = 600) -> bool:
    """Rendre la main a la boucle **et au fil de travail** jusqu'a la condition.

    Une attente qui ne rendrait pas la main a la boucle ferait exactement ce que
    ce mecanisme evite : bloquer le fil qui doit repondre.
    """
    for _ in range(tours):
        if condition():
            return True
        await pilote.pause()
        await asyncio.sleep(0.005)
    return False


def _ouvrir_E3_9(tmp_path, app, feinte):
    """Un parcours cable sur `E3-9`, avec sa passe doublee."""
    projet = fabriques_de_calibrate._projet(tmp_path)
    parcours = atelier_scan_parcours.ParcoursScan(app, projet,
                                                  calibration=feinte)
    return parcours, projet


def _lancer_la_calibration(pilote, parcours, tmp_path):
    """Remplir `E3-9` comme l'operateur le remplit, puis lancer.

    **Le parcours a gagne deux gestes le 2026-09-01** (`EPIC11-ARB-158` et le
    lot J2), et cette fabrique les joue plutot que de les court-circuiter :

    * `⏎` sur un champ de saisie ne lance plus rien -- il DESCEND. Egan :
      « la validation avec Entree n'est pas claire [...] il faut qu'il y ait un
      choix explicite en bas du formulaire : Valider ». La fabrique pose donc
      le curseur sur `CHAMP_VALIDER` ;
    * `Valider` ouvre une page de CONFIRMATION avant la passe -- « pas de page
      de validation avant, ce n'est pas conforme au reste des parcours ». La
      fabrique y retient l'issue `lancer`.

    Les appeler par le point d'entree interne (`lancer_la_passe_de_calibration`)
    aurait ete plus court et aurait **cesse de mesurer le cablage** : c'est
    justement ce que les tests qui emploient cette fabrique verifient -- « le
    mecanisme peut etre juste et n'etre cable nulle part ».
    """
    ecran = pilote.app.screen
    ecran.formulaire = fabriques_de_calibrate._formulaire(
        fabriques_de_calibrate._page_de_scan(tmp_path, "scan-de-banc"),
        etiquette=fabriques_de_calibrate.ETIQUETTE_EN_COLLISION)
    ecran.formulaire.champ = atelier_scan_calibrate.CHAMP_VALIDER
    assert ecran.traiter("enter")
    confirmation = pilote.app.screen
    assert isinstance(confirmation,
                      atelier_scan_calibrate.EcranCalibrationAConfirmer), (
        "`Valider` doit ouvrir la page de confirmation, pas lancer la passe")
    # **Le geste se joue sur l'ecran MONTE, jamais sur un jumeau construit
    # pour l'occasion.** La premiere redaction appelait
    # `trancher_la_confirmation` avec `issues_de_la_confirmation().issues[0]`
    # -- une liste NEUVE. `confirmation.choix`, la liste que le code parcourt
    # et valide, n'etait donc jamais touchee : ni le placement du curseur, ni
    # `viser`, ni `valider()` n'etaient joues sur aucun des neuf sites qui
    # emploient cette fabrique. C'est ce qui a laisse passer le `⏎` reflexe --
    # le curseur se posait sur « Lancer » et rien ne le mesurait (revue de
    # vague B, couche 2).
    confirmation.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
    assert confirmation.valider(), "l'issue retenue doit etre traitee"
    return ecran


def test_la_COLLISION_ouvre_son_ecran_et_la_reponse_REMONTE_au_coeur(tmp_path,
                                                                     banc):
    """La chaine entiere du point dur : `E3-0` -> `E3-9` -> collision -> coeur.

    C'est la mesure qui compte, parce qu'aucune des deux moities ne suffit : le
    mecanisme peut etre juste et n'etre cable nulle part, et le cablage peut
    etre juste et se bloquer. On mesure donc que l'operateur voit **les trois
    issues d'`EPIC11-ARB-89`**, que son choix redescend au coeur, et que la
    passe finit.
    """
    app = _coque()
    feinte = CalibrationFeinte(collision=("900-png-cccccccccccc", "beta"))
    parcours, _projet = _ouvrir_E3_9(tmp_path, app, feinte)
    vus = {}

    async def scenario(pilote):
        # La pile du produit : l'atelier se monte SUR le menu des
        # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
        # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
        # mesure sur une pile que le produit ne construit jamais.
        pilote.app.descendre()
        await pilote.pause()
        parcours.ouvrir()
        await pilote.pause()
        parcours.entrer({entree.cle: entree
                         for entree in atelier_scan.ENTREES_DU_MENU}["calibrer"])
        await pilote.pause()
        vus["E3-9"] = type(pilote.app.screen).__name__
        _lancer_la_calibration(pilote, parcours, tmp_path)
        assert await _tant_que(pilote, lambda: isinstance(
            pilote.app.screen, atelier_scan_parcours.EcranCollisionDuScan)), \
            "l'ecran de collision n'est jamais monte"
        collision = pilote.app.screen
        vus["issues"] = [issue.cle for issue in collision.choix.issues]
        vus["curseur"] = collision.choix.issues[collision.choix.curseur].ecrit
        while (collision.choix.issues[collision.choix.curseur].cle
               != atelier_scan_calibrate.CLE_ECRASER):
            assert collision.traiter("down") or collision.traiter("up")
        collision.traiter("enter")
        assert await _tant_que(
            pilote, lambda: parcours.ecran_de_calibration.passe is not None), \
            "la passe n'a jamais ete annoncee"
        await pilote.pause()
        vus["final"] = type(pilote.app.screen).__name__
        vus["E3-9 dans la pile"] = any(
            isinstance(ecran, atelier_scan_calibrate.EcranCalibrerLaChaine)
            for ecran in pilote.app.screen_stack)
        return vus

    vus = banc(app, scenario)
    assert vus["E3-9"] == "EcranCalibrerLaChaine"
    assert vus["issues"] == [atelier_scan_calibrate.CLE_NOM_DIFFERENCIE,
                             atelier_scan_calibrate.CLE_ECRASER,
                             atelier_scan_calibrate.CLE_ANNULER]
    assert vus["curseur"] is False, "le curseur s'est pose sur l'issue qui ecrase"
    # **La reponse est redescendue au coeur**, dans sa propre pile d'appel.
    assert feinte.ecrase is True
    # **Une passe qui ECRIT finit sur son ecran de succes** depuis le
    # 2026-09-06 (retour terrain d'Egan : « pas d'ecran de succes et on revient
    # directement a la page pour lancer une calibration »). `E3-9` reste
    # dessous, annote -- ce que la seconde assertion mesure, et c'est elle qui
    # distingue « monte par-dessus » de « a remplace ».
    assert vus["final"] == "EcranCalibrationEcrite"
    assert vus["E3-9 dans la pile"] is True
    assert parcours.ecran_de_calibration.passe.a_ecrit is True
    # Et le nom du formulaire a bien traverse le rappel de nommage du coeur.
    assert feinte.nomme == (fabriques_de_calibrate.ETIQUETTE_EN_COLLISION, "")


def test_ECHAP_sur_la_collision_repond_ANNULER_et_ne_BLOQUE_personne(tmp_path,
                                                                     banc):
    """Le filet, et il est la moitie qui manque a la plupart des mecanismes.

    `EcranDeJugement` ne traite pas `Échap` : c'est l'application qui depile
    l'ecran. Sans filet, le fil de travail attendrait une reponse qui ne
    viendrait jamais -- la passe ne finirait pas, `E3-9` n'annoncerait rien, et
    le symptome serait une interface **vivante** devant un travail mort.

    Sortir sans choisir ne peut signifier que « n'ecris pas » : la reponse est
    `annuler`, l'issue qui n'ecrase rien. Le coeur la recoit comme un refus, et
    c'est le contrat de `RelaisDeCollision` -- lu du lot G, pas rejoue ici.
    """
    app = _coque()
    feinte = CalibrationFeinte(collision=("900-png-cccccccccccc", "beta"))
    parcours, _projet = _ouvrir_E3_9(tmp_path, app, feinte)

    async def scenario(pilote):
        # La pile du produit : l'atelier se monte SUR le menu des
        # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
        # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
        # mesure sur une pile que le produit ne construit jamais.
        pilote.app.descendre()
        await pilote.pause()
        parcours.ouvrir()
        await pilote.pause()
        parcours.entrer({entree.cle: entree
                         for entree in atelier_scan.ENTREES_DU_MENU}["calibrer"])
        await pilote.pause()
        _lancer_la_calibration(pilote, parcours, tmp_path)
        assert await _tant_que(pilote, lambda: isinstance(
            pilote.app.screen, atelier_scan_parcours.EcranCollisionDuScan))
        await pilote.press("escape")
        assert await _tant_que(
            pilote, lambda: parcours.ecran_de_calibration.passe is not None), \
            "le fil de travail attend encore : le filet du demontage manque"
        return parcours.ecran_de_calibration.passe

    passe = banc(app, scenario)
    assert passe.a_ecrit is False
    assert isinstance(passe.refus, atelier_scan_calibrate.CalibrationAnnulee)
    assert passe.issue == atelier_scan_calibrate.CLE_ANNULER
    # **Le coeur n'a jamais recu de « oui »** : le relais a leve avant.
    assert feinte.ecrase is None


#: Le motif de refus employe par les mesures ci-dessous : **celui du milieu**
#: de la table publiee du coeur. Ni le premier (un `find` fautif rend le
#: premier), ni le dernier (une boucle fautive s'arrete au dernier). La table
#: est LUE, jamais recopiee.
MOTIF_DE_REFUS = scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION[1]


def _passe_qui_refuse(tmp_path, app):
    """Un parcours dont la passe **refuse nommement**, sans rien ecrire."""
    feinte = CalibrationFeinte(leve=scan_calibrate.RefusDeCalibration(
        "aucune page de calibration dans ce scan", motif=MOTIF_DE_REFUS))
    return _ouvrir_E3_9(tmp_path, app, feinte)[0], feinte


def test_un_REFUS_du_coeur_ouvre_un_ecran_qui_offre_DEUX_issues(tmp_path,
                                                                banc):
    """AC 8.3 : « un refus qui n'offre aucune issue est aussi fautif qu'une
    destruction silencieuse » (`EPIC11-ARB-89`).

    Le coeur porte un chemin qui ne propose **rien**. L'ecran ne le laisse pas
    nu : deux issues, dont aucune n'ecrit -- renommer l'etiquette change le
    radical vise, donc sort de l'impasse ; abandonner ramene au menu.
    """
    app = _coque()
    parcours, feinte = _passe_qui_refuse(tmp_path, app)

    async def scenario(pilote):
        # La pile du produit : l'atelier se monte SUR le menu des
        # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
        # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
        # mesure sur une pile que le produit ne construit jamais.
        pilote.app.descendre()
        await pilote.pause()
        parcours.ouvrir()
        await pilote.pause()
        parcours.entrer({entree.cle: entree
                         for entree in atelier_scan.ENTREES_DU_MENU}["calibrer"])
        await pilote.pause()
        _lancer_la_calibration(pilote, parcours, tmp_path)
        assert await _tant_que(pilote, lambda: isinstance(
            pilote.app.screen, atelier_scan_calibrate.EcranRefusDeCalibration))
        return pilote.app.screen

    ecran = banc(app, scenario)
    issues = [issue.cle for issue in ecran.choix.issues]
    assert issues == [atelier_scan_calibrate.CLE_RENOMMER,
                      atelier_scan_calibrate.CLE_ABANDONNER]
    assert [issue for issue in ecran.choix.issues if issue.ecrit] == []
    assert ecran.passe.motif == MOTIF_DE_REFUS
    # **Il ne dit jamais « echec »** (`DESIGN.md` section 9) : il nomme ce qui
    # n'a pas eu lieu, et porte le message du coeur verbatim.
    assert "echec" not in ecran.titre_du_choix.lower()
    assert "aucune page de calibration" in ecran.phrase


def test_ANNULER_devant_la_collision_n_ouvre_PAS_l_ecran_de_refus(tmp_path,
                                                                  banc):
    """Volet symetrique du precedent, et il porte la distinction qui compte.

    Une annulation devant la collision **est** un refus du coeur -- le relais
    leve --, mais ce n'est pas une impasse : l'operateur vient de dire « n'ecris
    rien », et son formulaire est toujours sous ses yeux. Lui reposer la
    question serait l'invite qui apprend a repondre sans lire, ce qu'
    `EPIC5-ARB-99` ecarte nommement.

    Sans ce volet, un cablage qui ouvrirait le refus **pour tout** passerait :
    les deux chemins portent un `refus`, et seul le type les distingue.
    """
    app = _coque()
    feinte = CalibrationFeinte(collision=("900-png-cccccccccccc", "beta"))
    parcours, _projet = _ouvrir_E3_9(tmp_path, app, feinte)

    async def scenario(pilote):
        # La pile du produit : l'atelier se monte SUR le menu des
        # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
        # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
        # mesure sur une pile que le produit ne construit jamais.
        pilote.app.descendre()
        await pilote.pause()
        parcours.ouvrir()
        await pilote.pause()
        parcours.entrer({entree.cle: entree
                         for entree in atelier_scan.ENTREES_DU_MENU}["calibrer"])
        await pilote.pause()
        _lancer_la_calibration(pilote, parcours, tmp_path)
        assert await _tant_que(pilote, lambda: isinstance(
            pilote.app.screen, atelier_scan_parcours.EcranCollisionDuScan))
        collision = pilote.app.screen
        while (collision.choix.issues[collision.choix.curseur].cle
               != atelier_scan_calibrate.CLE_ANNULER):
            assert collision.traiter("down")
        collision.traiter("enter")
        assert await _tant_que(
            pilote, lambda: parcours.ecran_de_calibration.passe is not None)
        return type(pilote.app.screen).__name__

    assert banc(app, scenario) == "EcranCalibrerLaChaine"


def test_les_DEUX_issues_de_l_impasse_menent_chacune_QUELQUE_PART(tmp_path,
                                                                  banc):
    """« Renommer » revient au formulaire, « Abandonner » au menu de l'atelier.

    Les deux sont mesurees ensemble parce que c'est leur **difference** qui est
    le sujet : deux issues qui remonteraient au meme endroit seraient une seule
    issue offerte deux fois, et le point de jugement serait decoratif.

    « Abandonner » s'arrete a `E3-0` et **pas plus haut** (`EPIC11-ARB-13`) :
    l'operateur qui vient de calibrer enchaine dans le meme atelier.
    """
    resultats = {}
    for cle in (atelier_scan_calibrate.CLE_RENOMMER,
                atelier_scan_calibrate.CLE_ABANDONNER):
        app = _coque()
        (tmp_path / cle).mkdir(parents=True, exist_ok=True)
        parcours, _feinte = _passe_qui_refuse(tmp_path / cle, app)

        async def scenario(pilote, cle=cle, parcours=parcours):
            # La pile du produit : l'atelier se monte SUR le menu des
            # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
            # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
            # mesure sur une pile que le produit ne construit jamais.
            pilote.app.descendre()
            await pilote.pause()
            parcours.ouvrir()
            await pilote.pause()
            parcours.entrer({e.cle: e
                             for e in atelier_scan.ENTREES_DU_MENU}["calibrer"])
            await pilote.pause()
            _lancer_la_calibration(pilote, parcours, tmp_path / cle)
            assert await _tant_que(pilote, lambda: isinstance(
                pilote.app.screen,
                atelier_scan_calibrate.EcranRefusDeCalibration))
            refus = pilote.app.screen
            while refus.choix.issues[refus.choix.curseur].cle != cle:
                assert refus.traiter("down") or refus.traiter("up")
            refus.traiter("enter")
            await pilote.pause()
            return type(pilote.app.screen).__name__

        resultats[cle] = banc(app, scenario)

    assert resultats[atelier_scan_calibrate.CLE_RENOMMER] == \
        "EcranCalibrerLaChaine"
    assert resultats[atelier_scan_calibrate.CLE_ABANDONNER] == "EcranScanMenu"


def test_le_retour_du_RESULTAT_s_arrete_a_E3_0_et_PAS_a_E3_5(tmp_path, banc):
    """La dependance que le lot F a nommee, mesuree **sur la vraie pile**.

    `remonter_a_l_ouverture_de_l_atelier` depile **jusqu'au rang**
    `RANG_DES_ATELIERS + 1`, et non « jusqu'au premier palier non transitoire »
    comme le fait l'Extraction : le Scan empile **quatre** stations, si bien que
    la regle de l'Extraction s'arreterait sur `E3-5` -- devant un profil a
    valider pour un lot deja ecrit.

    La mesure suppose donc que `E3-0` est empile comme palier, et c'est
    exactement ce que le cablage du lot H garantit. Elle rougirait le jour ou
    `E3-0` cesserait d'etre une station.
    """
    etapes, parcours, _feinte = _derouler_le_temps_2(banc, tmp_path)
    assert etapes[-1] == "EcranResultatDuScan"

    app = _coque()
    parcours2 = _parcours_cable(tmp_path / "second", app)

    async def scenario(pilote):
        # La pile du produit : l'atelier se monte SUR le menu des
        # ateliers. Sans ce cran, `RANG_DES_ATELIERS + 1` designerait
        # `E3-1` au lieu de `E3-0`, et le retour du resultat serait
        # mesure sur une pile que le produit ne construit jamais.
        pilote.app.descendre()
        await pilote.pause()
        parcours2.ouvrir()
        await pilote.pause()
        rang_du_menu = pilote.app.rang
        parcours2.deposer()
        await pilote.pause()
        parcours2.montrer_le_rapport()
        await pilote.pause()
        parcours2.choisir_la_calibration()
        await pilote.pause()
        avant = type(pilote.app.screen).__name__
        atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier(pilote.app)
        await pilote.pause()
        return avant, type(pilote.app.screen).__name__, rang_du_menu, \
            pilote.app.rang

    avant, apres, rang_menu, rang_final = banc(app, scenario)
    assert avant == "EcranChoixDeCalibration"
    assert apres == "EcranScanMenu", apres
    assert rang_final == rang_menu == CoqueTui.RANG_DES_ATELIERS + 1


def test_une_suite_INCONNUE_du_temps_2_mene_a_PAS_ENCORE_et_c_est_VOULU(
        tmp_path, banc):
    """Le filet du finding `K3` -- « une suite sans destination doit le DIRE ».

    **Ce test portait sur :data:`SUITE_EXPORTS` jusqu'au 2026-09-06, et il
    avait cesse d'etre vrai sans cesser d'etre vert.** Il affirmait « l'atelier
    Exports n'existe pas » et se donnait pour raison d'etre « qu'une revue ne
    prenne pas cet `EcranPasEncore`-la pour un cablage manquant » -- c'etait
    exactement un cablage manquant, depuis que la story 11.8 avait livre
    l'atelier et que `ChaineReelle.atelier_exports` le cablait. C'est `MQ-5` de
    l'audit du parcours complet, et il aura fallu jouer le parcours au clavier
    pour le voir : le filet *fonctionnait*, donc rien ne rougissait.

    Ce qui reste vrai, et que ce test mesure desormais, c'est le filet
    lui-meme : un libelle qu'aucune branche ne traite doit **nommer** son
    absence plutot que de consommer la touche en silence. Il est exerce sur un
    libelle inconnu, qui ne peut pas etre livre par une story et donc pas se
    perimer. Le fait que chaque `SUITE_*` **declaree**, elle, porte une branche
    nommee est mesure a part, par
    `test_couverture_des_suites.py`.
    """
    app = _coque()
    rapport = fabriques_du_resultat.rapport_de_trois_lots(tmp_path)
    inconnue = "Une suite que personne n'a cablee"

    async def scenario(pilote):
        atelier_scan_resultat.suivre(pilote.app, rapport, inconnue)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, EcranPasEncore)
    assert ecran.ce_qui_manque == inconnue


# ===========================================================================
# H3 -- la grille 80 x 24, sur les SIX ecrans, dans les DEUX modes
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_temps_2_tient_les_24_LIGNES(tmp_path, banc, nom,
                                                     ascii_seul):
    """AC 9.3, la hauteur.

    Le plafond est **derive** de la grille par
    `jetons.HAUTEUR_CENTRE_AU_PLANCHER` -- bordure, filets, bandeau, etat et
    raccourcis deduits --, jamais ecrit en dur : dix-sept pose ici serait une
    seconde source de verite.
    """
    hauteur, _etat, _blocs = _monter(banc, nom, tmp_path, ascii_seul)
    assert hauteur <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, (nom, hauteur)


def test_la_mesure_de_HAUTEUR_MORD_sur_un_ecran_qui_DEBORDE(tmp_path, banc):
    """Volet symetrique : un corpus de petits ecrans ne mesure rien.

    L'ecran fabrique ici rend trente lignes de carte la ou la grille en admet
    une poignee. Sans lui, la mesure precedente resterait verte le jour ou la
    composition cesserait d'etre bornee.
    """
    class Deborde(atelier_scan_confirmation.EcranScanConfirmation):
        def lignes_du_panneau(self):
            return [f"ligne {rang:02d}" for rang in range(30)]

    app = _coque()
    plan = fabriques_de_confirmation.plan_nominal()

    async def scenario(pilote):
        pilote.app.descendre(Deborde(plan, sur_issue=lambda _i: None))
        await pilote.pause()
        centre = pilote.app.screen.query_one("#centre")
        return sum(enfant.outer_size.height for enfant in centre.children)

    assert banc(app, scenario) > jetons.HAUTEUR_CENTRE_AU_PLANCHER


def test_le_corpus_de_HAUTEUR_porte_un_ecran_qui_FROLE_le_plafond(tmp_path,
                                                                  banc):
    """Second volet symetrique : au moins un des six **remplit** la grille.

    Un corpus qui ne porterait que des ecrans a trois lignes laisserait la
    mesure verte en permanence, quelle que soit la valeur du plafond.
    """
    hauteurs = {nom: _monter(banc, nom, tmp_path, False)[0]
                for nom in MAQUETTES_DU_TEMPS_2}
    assert max(hauteurs.values()) >= jetons.HAUTEUR_CENTRE_AU_PLANCHER - 2, \
        hauteurs


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_temps_2_tient_les_80_COLONNES(tmp_path, banc, nom,
                                                       ascii_seul):
    """AC 9.3, l'autre dimension, mesuree en **colonnes** et non en caracteres.

    `EPIC11-ARB-21` : « au-dela de 80 colonnes, la place gagnee allonge les
    lignes ; elle n'ajoute jamais une seconde colonne ». La mesure se fait donc
    au plancher, la ou tout doit deja tenir -- ligne d'etat comprise.
    """
    utile = jetons.largeur_utile()
    _hauteur, etat, blocs = _monter(banc, nom, tmp_path, ascii_seul)
    trop_larges = [(rang, jetons.colonnes(ligne), ligne)
                   for bloc in blocs
                   for rang, ligne in enumerate(bloc.split("\n"))
                   if jetons.colonnes(ligne) > utile]
    assert trop_larges == [], (nom, trop_larges)
    assert jetons.colonnes(etat) <= utile, (nom, jetons.colonnes(etat), etat)


# ===========================================================================
# H4 -- lignes d'etat, repli ASCII, glyphes, touches, vocabulaire
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_aucune_ligne_d_etat_du_temps_2_ne_porte_de_TOUCHE_ni_de_CONSEIL(
        tmp_path, banc, nom, ascii_seul):
    """AC 9.4, `EPIC11-ARB-56` : « la ligne d'etat porte une **mesure**, jamais
    une touche ni un conseil ».

    Le lexique est celui du lot G de la 11.4, **importe** : le recopier ici en
    ferait un second, qui divergerait au premier raccourci ajoute.
    """
    _hauteur, etat, _blocs = _monter(banc, nom, tmp_path, ascii_seul)
    assert ecarts_de_sobriete(etat) == [], (nom, etat,
                                            ecarts_de_sobriete(etat))


def test_la_frontiere_de_SOBRIETE_MORD_sur_une_ligne_d_etat_du_temps_2():
    """Volet symetrique : la mesure precedente regarde bien quelque chose.

    La ligne fautive est celle que la maquette `E3-6` portait avant la passe du
    lot A -- « e pour éditer les noms » --, et c'est l'ecart `H6` de cette
    story. Trois lignes, **la fautive au milieu** : une passe qui s'arreterait
    sur la premiere ligne saine laisserait la fautive hors mesure.
    """
    corpus = [
        "2 lots · 186 frames · ~ 5,4 Go — rien n'a encore été écrit",
        "e pour éditer les noms — 48 caractères au plus",
        "profil posé le 12/08 · remplacé le 31/08",
    ]
    fautives = [ligne for ligne in corpus if ecarts_de_sobriete(ligne)]
    assert fautives == [corpus[1]], fautives


#: Les ecrans dont la ligne d'etat est **volontairement vide**, en ensemble
#: EXACT. `DESIGN.md` section 3 : « une ligne d'etat sans rien a dire est une
#: ligne vide », jamais une ligne absente -- mais elle n'est legitime que quand
#: l'ecran n'a effectivement rien a mesurer. `E3-9` a l'arrivee est dans ce cas :
#: aucun scan n'est designe, aucune passe n'a tourne, il n'y a rien a dire.
ECRANS_DU_TEMPS_2_A_LIGNE_D_ETAT_VIDE = {"E3-9"}


def test_l_ensemble_des_lignes_d_etat_VIDES_est_EXACTEMENT_celui_la(tmp_path,
                                                                    banc):
    """L'autre moitie de l'AC 9.4, en **ensemble exact** et non par exception.

    « L'ensemble des chemins qui divergent est exactement {X} mesure l'exception
    ET son unicite » (`CLAUDE.md`). Une assertion du genre « `E3-9` est vide »
    laisserait un second ecran perdre sa mesure sans rien dire ; celle-ci rougit
    dans les deux sens.
    """
    vides = {nom for nom in MAQUETTES_DU_TEMPS_2
             if not _monter(banc, nom, tmp_path, False)[1].strip()}
    assert vides == ECRANS_DU_TEMPS_2_A_LIGNE_D_ETAT_VIDE, sorted(
        vides ^ ECRANS_DU_TEMPS_2_A_LIGNE_D_ETAT_VIDE)


@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_ecran_du_temps_2_se_rend_en_ASCII_PUR(tmp_path, banc, nom):
    """AC 9.6 : `--ascii` ne laisse **aucun** caractere hors ASCII imprimable.

    Le depot a paye ce chemin trois fois -- findings `F7`, `R1`, puis le `ΔE`
    du lot C, que `--ascii` rendait `?E` faute d'entree dans
    `jetons.REPLIS_DE_TEXTE`. La frontiere entre ici dans les **six** ecrans du
    temps 2, ligne d'etat comprise.
    """
    _hauteur, etat, blocs = _monter(banc, nom, tmp_path, True)
    hors_ascii = sorted({caractere
                         for texte in blocs + [etat]
                         for caractere in texte
                         if caractere not in "\n" and not (
                             32 <= ord(caractere) < 127)})
    assert hors_ascii == [], (nom, hors_ascii)


def test_le_repli_de_l_unite_de_DIVERGENCE_est_DANS_la_table_partagee():
    """H4, l'entree versee par le lot C -- et elle est **derivee**, pas recopiee.

    `Δ` manquait a `jetons.REPLIS_DE_TEXTE` : la decomposition Unicode ne
    connait pas la majuscule grecque, et `replier_ascii` la remplacait par `?`.
    Le lot C avait pose un repli **local**, faute de pouvoir toucher un module
    partage ; l'entree est desormais dans la table, et la constante de l'ecran
    la **derive**.

    L'identite est mesuree, pas l'egalite : deux redactions qui coincident
    aujourd'hui divergeraient au premier ajustement, et l'ecart ne se verrait
    qu'en `--ascii`.
    """
    assert jetons.replier_ascii(
        atelier_scan_calibration.UNITE_DE_DIVERGENCE) == \
        atelier_scan_calibration.UNITE_DE_DIVERGENCE_ASCII
    assert atelier_scan_calibration.unite_de_divergence(True) == "dE"
    # Volet symetrique : sans l'entree, le repli rendrait `?`. On mesure donc
    # que la table la porte, et qu'elle ne rend pas le caractere de remplacement.
    assert "?" not in jetons.replier_ascii("ΔE")
    assert "Δ" in jetons.REPLIS_DE_TEXTE


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_aucun_GLYPHE_HORS_TABLE_dans_les_ecrans_du_temps_2(tmp_path, banc,
                                                            nom, ascii_seul):
    """AC 9.7 : la table fermee de `DESIGN.md` section 6, sur les six ecrans.

    Le predicat est celui du lot G de la 11.4, importe : il lit l'alphabet
    autorise de `jetons` -- glyphes du mode, symboles de repli, ellipse -- et
    non une liste recopiee.
    """
    _hauteur, etat, blocs = _monter(banc, nom, tmp_path, ascii_seul)
    hors_table = set()
    for texte in blocs + [etat]:
        hors_table |= glyphes_hors_table(texte, ascii_seul)
    assert hors_table == set(), (nom, sorted(hors_table))


def test_la_table_des_GLYPHES_MORD_sur_un_dessin_qui_n_y_est_pas():
    """Volet symetrique : sans lui, un predicat qui ne verrait rien serait vert
    sur les six ecrans a la fois."""
    assert glyphes_hors_table("★ un profil", False) == {"★"}
    assert glyphes_hors_table("● un profil", False) == set()


#: Les touches que **l'application** traite, quel que soit l'ecran. Elles sont
#: LUES de `CoqueTui.BINDINGS`, jamais recopiees : `DESIGN.md` section 4 les
#: pose comme « presentes sur tout ecran sans exception », et une liste ecrite
#: ici survivrait au jour ou l'une d'elles serait deliee.
TOUCHES_DE_L_APPLICATION = {"Échap": "escape", "F1": "f1", "Q": "q"}

#: Les touches que **l'ecran** doit traiter lui-meme, avec le geste qui les
#: exerce. Une touche annoncee en ligne de raccourcis et traitee par personne
#: se lit comme une panne -- finding `I8`, quarante fois paye.
TOUCHES_DE_L_ECRAN = {"⏎": "enter", "↑↓": "down", "Tab": "tab"}


class _Frappe:
    """Un evenement clavier minimal : ce que `on_key` lit, et son `stop()`."""

    def __init__(self, touche: str) -> None:
        self.key = touche
        self.character = None
        self.arrete = False

    def stop(self) -> None:
        self.arrete = True


def _frapper(ecran, touche: str) -> bool:
    """Frapper une touche, **quel que soit le point d'entree clavier**.

    Deux formes coexistent dans le paquet, et il faut les deux : `traiter`,
    mesurable sans clavier, qui **rend** si elle a consomme la touche ; et
    `on_key`, qui **arrete** l'evenement quand elle l'a traite. La seconde est
    celle des ecrans de `execution.py`, partages avec l'Extraction et que cette
    story n'a pas le droit de modifier. Les deux disent la meme chose -- la
    touche a-t-elle ete consommee --, et une mesure qui n'en connaitrait qu'une
    declarerait inertes deux ecrans sur six.
    """
    if hasattr(ecran, "traiter"):
        return bool(ecran.traiter(touche))
    evenement = _Frappe(touche)
    ecran.on_key(evenement)
    return evenement.arrete


@pytest.mark.parametrize("nom", CIBLES)
def test_chaque_touche_ANNONCEE_par_le_temps_2_est_une_touche_CABLEE(
        tmp_path, banc, nom):
    """AC 9.5 : « une touche annoncee est une touche cablee », sur les six.

    Les trois touches de l'application sont **lues** de ses liaisons ; les
    autres sont exercees sur l'ecran lui-meme, par `traiter`, qui rend vrai
    quand il les a consommees. Une ligne de raccourcis honnete se mesure des
    deux cotes -- ce qu'elle promet et ce qu'elle tient.
    """
    app = _coque()
    liees = {liaison[0] for liaison in CoqueTui.BINDINGS}

    async def scenario(pilote):
        ecran = FABRIQUES[nom](pilote.app, tmp_path)
        await pilote.pause()
        annonces = ecran.raccourcis
        muettes = []
        for promesse, touche in TOUCHES_DE_L_APPLICATION.items():
            if promesse in annonces and touche not in liees:
                muettes.append(promesse)
        for promesse, touche in TOUCHES_DE_L_ECRAN.items():
            if promesse in annonces and not _frapper(ecran, touche):
                muettes.append(promesse)
        return annonces, muettes

    annonces, muettes = banc(app, scenario)
    assert muettes == [], (nom, annonces, muettes)
    # Volet symetrique de la mesure elle-meme : une ligne qui n'annoncerait
    # RIEN passerait la boucle ci-dessus sans rien mesurer.
    assert any(promesse in annonces
               for promesse in (list(TOUCHES_DE_L_APPLICATION)
                                + list(TOUCHES_DE_L_ECRAN))), (nom, annonces)


def test_la_mesure_des_TOUCHES_ANNONCEES_mord_sur_une_promesse_INERTE(tmp_path,
                                                                      banc):
    """Volet symetrique : une touche promise et traitee par personne rougit.

    L'ecran fabrique ici annonce `Tab` sur un ecran qui ne le traite pas --
    c'est litteralement l'ecart `H16` que la 11.5 a leve sur `E3-3`, et le
    defaut `I8` que le lot I a paye quarante fois.
    """
    class Menteur(atelier_scan_calibration.EcranChoixDeCalibration):
        raccourcis = "⏎ continuer  Tab journal  Échap retour  F1 aide"

        def _appliquer_la_zone(self):
            """L'ecran reel repose sa ligne au montage ; le temoin garde la
            sienne, sans quoi le mensonge serait efface avant d'etre mesure."""

    app = _coque()

    async def scenario(pilote):
        ecran = Menteur(_projet_a_trois_profils(tmp_path),
                        retenir=lambda _r: None)
        pilote.app.descendre(ecran)
        await pilote.pause()
        return "Tab" in ecran.raccourcis, _frapper(ecran, "tab")

    annoncee, traitee = banc(app, scenario)
    assert annoncee is True
    assert traitee is False, "l'ecran temoin traite `Tab` : il ne ment plus"


#: Le vocabulaire de nos **documents de decision**, qui ne s'affiche jamais
#: (`EPIC11-ARB-28`, verbatim : « ca dit qu'une commande de coeur est distincte,
#: **ca ne dit a personne ou cliquer** »).
TERMES_DE_NOS_DOCUMENTS = ("palier", "parcours a part", "parcours à part",
                           "feuille cli", "point de jugement")


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", CIBLES)
def test_aucun_TERME_de_nos_documents_ne_s_affiche_dans_le_temps_2(
        tmp_path, banc, nom, ascii_seul):
    """AC 9.8, mesure **sur ce qui est affiche** et non sur le source.

    Un terme peut vivre dans un nom de constante sans jamais atteindre l'ecran
    -- `PALIER_DE_L_ECRAN` en est un --, et c'est legitime : ce que l'arbitrage
    interdit est de le **montrer**. La mesure porte donc sur les blocs peints et
    la ligne d'etat.
    """
    _hauteur, etat, blocs = _monter(banc, nom, tmp_path, ascii_seul)
    affiche = " ".join(blocs + [etat]).lower()
    trouves = [terme for terme in TERMES_DE_NOS_DOCUMENTS if terme in affiche]
    assert trouves == [], (nom, trouves)


def test_aucun_TERME_de_nos_documents_dans_les_TEXTES_des_modules():
    """L'autre moitie : un texte qui n'est pas affiche **aujourd'hui** le sera.

    La mesure porte sur les chaines de **code** des six modules du temps 2,
    docstrings exclus -- ce sont eux qui expliquent pourquoi ces mots
    n'apparaissent pas, donc un grep de fichier s'y ferait affaiblir a la
    premiere prose (lecon du finding `I3`).
    """
    fautifs = []
    for module in MODULES_DU_TEMPS_2:
        exportes = set(getattr(
            __import__(f"mixed_media_utility.tui.{module[:-3]}",
                       fromlist=["__all__"]), "__all__", ()))
        for chaine in chaines_de_code(PAQUET_TUI / module):
            # `__all__` liste des **noms**, pas des textes : `PALIER_DE_L_ECRAN`
            # y est une chaine sans jamais atteindre l'ecran. Les exclure est le
            # contraire d'un relachement -- la mesure d'affichage ci-dessus les
            # attraperait s'ils s'affichaient.
            if chaine in exportes:
                continue
            minuscule = chaine.lower()
            fautifs += [(module, terme, chaine)
                        for terme in TERMES_DE_NOS_DOCUMENTS
                        if terme in minuscule]
    assert fautifs == [], fautifs


def test_la_mesure_du_VOCABULAIRE_mord_sur_un_texte_fautif(tmp_path):
    """Volet symetrique : sans lui, la mesure serait verte sur un module vide.

    Le module fabrique porte le terme dans un **docstring** (legitime : il
    explique la regle) et dans une **chaine de code** (fautif : elle s'affiche).
    Les deux dans le meme fichier, ce qui est la seule disposition ou une mesure
    de texte et une mesure d'AST rendent des reponses differentes.
    """
    fautif = tmp_path / "faux_module_du_temps_2.py"
    fautif.write_text(
        '"""Ce module explique pourquoi il ne dit jamais palier."""\n'
        'TITRE = "Retour au palier precedent"\n',
        encoding="utf-8")
    chaines = chaines_de_code(fautif)
    assert [c for c in chaines if "palier" in c.lower()] == [
        "Retour au palier precedent"], chaines


def test_aucun_module_du_temps_2_n_appelle_JAMAIS_cli_py():
    """AC 9.1, **explicitement sur les modules du temps 2**.

    La frontiere de paquet de la 11.4b les couvre deja ; l'AC demande quand
    meme la mesure nommee, et elle a raison : une frontiere de paquet reste
    verte le jour ou un module sort du paquet, et celle-ci nomme lequel.
    """
    fautifs = []
    for module in MODULES_DU_TEMPS_2:
        noms = identifiants(PAQUET_TUI / module)
        fautifs += [(module, nom) for nom in sorted(noms)
                    if nom == "cli" or nom.endswith(".cli")]
    assert fautifs == [], fautifs


def test_aucun_module_du_temps_2_n_offre_de_COMPLETION_DE_CHEMIN():
    """AC 9.2, `EPIC11-ARB-48` **resserre par `EPIC11-ARB-127`**.

    Ce qui doit rendre zero est le **geste** de la barre d'adresse -- proposer
    la suite de ce qu'on tape --, pas le verbe francais. La mesure est celle de
    `test_projets`, **importee telle quelle** : la reecrire ici la
    re-elargirait au mot, et le contournement reviendrait en silence.
    """
    fautives = [ligne for ligne in _occurrences_de_completion_de_chemin(
        PAQUET_TUI) if ligne.split(":")[0] in MODULES_DU_TEMPS_2]
    assert fautives == [], fautives


def test_les_SIX_modules_du_temps_2_EXISTENT():
    """Volet symetrique des trois frontieres ci-dessus, et il vient avec elles.

    Une frontiere posee sur un module absent est verte sans rien mesurer :
    c'est le mode de panne que `sources_tui` ferme deja pour le paquet, ferme
    ici pour la liste nommee.
    """
    manquants = [nom for nom in MODULES_DU_TEMPS_2
                 if not (PAQUET_TUI / nom).is_file()]
    assert manquants == [], manquants
    assert len(MODULES_DU_TEMPS_2) == 6
