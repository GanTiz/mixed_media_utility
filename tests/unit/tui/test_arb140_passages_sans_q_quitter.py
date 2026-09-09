# -*- coding: utf-8 -*-
"""`EPIC11-ARB-140` -- les passages annoncent `F1 aide`, jamais `Q quitter`.

**Ce que ce banc mesure, et pourquoi il n'existait pas avant.** Le chiffrage du
2026-09-02 (`deferred-work.md`, entree `EPIC11-ARB-140`) a mesure que **zero**
banc du depot epinglait ces lignes a l'egalite : trois courses de
`tests/unit/tui` -- temoin, un litteral change, trois litteraux changes -- ont
rendu 4402 verts et zero rouge. Autrement dit, le desaccord entre les sept
maquettes d'execution, les quatre maquettes de resultat et le produit **n'etait
mesure nulle part**, et rien n'aurait signale sa reapparition. Ce fichier est
la frontiere qui manquait.

**Ce banc est la moitie 1 d'un arbitrage qui en compte deux, et l'autre est sa
CONDITION.** Retirer `Q quitter` ne suffit pas : annoncer `F1 aide` sur un ecran
d'execution promet une aide dont on ne pouvait pas SORTIR -- `F1` empilait
`EcranPasEncore` et `Echap` y armait l'interruption au lieu de depiler. Le
cul-de-sac existait deja sur les deux ecrans Pdf ; l'alignement l'aurait porte
de deux ecrans a six. Il est ferme par le geste 2, mesure dans
`test_arb140_sortie_de_l_ecran_d_aide.py`.

**La redaction n'est pas inventee** : elle EST celle que le produit porte deja
dans `atelier_scan_parcours.RACCOURCIS_RAPPORT`, et le banc l'epingle **par
reference** plutot qu'en recopiant la chaine -- meme geste que
`test_atelier_pdf_calibration.py`, et meme motif que « la TUI lit la borne du
coeur, elle ne la recopie pas ».
"""
from __future__ import annotations

import importlib
import sys

from mixed_media_utility.tui.atelier_pdf_calibration import EcranMireEcrite
from mixed_media_utility.tui.atelier_scan_calibrate import (
    _classe_de_l_ecran_de_passe,
)
from mixed_media_utility.tui.atelier_scan_detection import EcranDetectionEnCours
from mixed_media_utility.tui.atelier_scan_ecriture import EcranEcritureDuScan
from mixed_media_utility.tui.atelier_scan_parcours import RACCOURCIS_RAPPORT
from mixed_media_utility.tui.atelier_scan_resultat import EcranResultatDuScan
from mixed_media_utility.tui.execution import (
    RACCOURCIS_RESULTAT,
    RACCOURCIS_RESULTAT_AVEC_JOURNAL,
    EcranExecution,
    EcranResultat,
)

#: Le balayage du paquet vit dans `test_repli_ascii.py` : on le REUTILISE plutot
#: que d'en ecrire un second, qui divergerait. C'est le meme geste que
#: `test_atelier_scan_confirmation.py` fait avec le banc des maquettes.
if str(__import__("pathlib").Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
_balayage = importlib.import_module("test_repli_ascii")


#: Les **six** ecrans que l'arbitrage aligne, plus le septieme qui n'est
#: atteignable que par sa fabrique (classe imbriquee, invisible au balayage de
#: modules). Quatre d'execution, trois de resultat.
def ecrans_alignes() -> dict:
    """Les sept ecrans d'execution et de resultat, nommes un par un.

    **Trois d'entre eux n'ont pas de ligne a eux** : `EcranDetectionEnCours`,
    `EcranEcritureDuScan` et l'ecran de la passe de `calibrate` **heritent**
    celle d'`EcranExecution`. C'est ce qui fait qu'UN littéral couvre QUATRE
    ecrans, et le test d'heritage ci-dessous le mesure plutot que de le
    supposer.
    """
    return {
        "execution.EcranExecution": EcranExecution,
        "atelier_scan_detection.EcranDetectionEnCours": EcranDetectionEnCours,
        "atelier_scan_ecriture.EcranEcritureDuScan": EcranEcritureDuScan,
        "atelier_scan_calibrate.EcranCalibrationEnCours":
            _classe_de_l_ecran_de_passe(),
        "execution.EcranResultat": EcranResultat,
        "atelier_scan_resultat.EcranResultatDuScan": EcranResultatDuScan,
        "atelier_pdf_calibration.EcranMireEcrite": EcranMireEcrite,
    }


# ===========================================================================
# Geste 1 -- les lignes de raccourcis
# ===========================================================================

def test_les_sept_ecrans_alignes_annoncent_F1_aide_et_PAS_Q_quitter():
    """Le volet positif, sur les sept ecrans a la fois.

    Sept et non un : une assertion sur le seul `EcranExecution` serait verte
    alors qu'une sous-classe redefinirait sa ligne, ce que rien n'empeche.
    """
    fautifs = {nom: classe.raccourcis
               for nom, classe in ecrans_alignes().items()
               if "Q quitter" in classe.raccourcis
               or "F1 aide" not in classe.raccourcis}
    assert fautifs == {}, fautifs


def test_l_ensemble_des_PASSAGES_qui_annoncent_ENCORE_Q_quitter_est_EXACTEMENT_celui_la():
    """L'exception ET son unicite, sur tout le paquet.

    **Une assertion positive laisserait passer toute divergence
    supplementaire** (regle des fabriques, 2026-08-30) : « ces sept ecrans sont
    corriges » ne dit rien d'un huitieme passage qui porterait encore
    `Q quitter`, ni d'un neuvieme qui le reprendrait demain.

    Les trois qui restent sont **hors perimetre d'`ARB-140`**, nommes par le
    chiffrage et non corriges ici :

    * `execution.EcranRefus` (`T5-1`) -- la maquette porte `F1 aide`, le produit
      non. Meme famille, autre arbitrage ;
    * `coque.EcranPasEncore` -- sans maquette. Son `Echap` est repare ci-dessous
      (le cul-de-sac), sa LIGNE ne l'est pas ;
    * `ecran_projet.EcranCreation` -- un formulaire, qui porte **deja** les deux
      jetons (`F1 aide  Q quitter`) : il ne fait pas partie du desaccord.
    """
    encore = {nom for nom, classe in _balayage.classes_d_ecran().items()
              if classe.TRANSITOIRE and "Q quitter" in (classe.raccourcis or "")}
    attendu = {
        "mixed_media_utility.tui.execution.EcranRefus",
        "mixed_media_utility.tui.coque.EcranPasEncore",
        "mixed_media_utility.tui.ecran_projet.EcranCreation",
    }
    assert encore == attendu, sorted(encore ^ attendu)


def test_les_trois_sous_classes_d_execution_HERITENT_la_ligne_au_lieu_de_la_recopier():
    """Ce qui fait qu'UN littéral couvre QUATRE ecrans.

    L'identite (`is`), pas l'egalite : deux chaines egales aujourd'hui
    divergeraient a la premiere correction faite d'un seul cote, et c'est
    exactement le mode de panne que l'arbitrage vient de payer sur sept ecrans.
    """
    heritieres = {
        "EcranDetectionEnCours": EcranDetectionEnCours,
        "EcranCalibrationEnCours": _classe_de_l_ecran_de_passe(),
        "EcranEcritureDuScan": EcranEcritureDuScan,
    }
    recopieuses = {nom for nom, classe in heritieres.items()
                   if classe.raccourcis is not EcranExecution.raccourcis}
    assert recopieuses == set(), sorted(recopieuses)


def test_la_ligne_du_resultat_est_celle_QUE_LE_PRODUIT_PORTE_DEJA():
    """Par REFERENCE, jamais en recopiant la chaine.

    `atelier_scan_parcours.RACCOURCIS_RAPPORT` est la redaction approuvee des
    quatre maquettes de resultat, livree bien avant cet arbitrage. La recopier
    ici donnerait deux sources de verite qui divergeraient en silence.
    """
    assert RACCOURCIS_RESULTAT == RACCOURCIS_RAPPORT


def test_les_DEUX_lignes_de_resultat_ne_different_QUE_par_Tab_journal():
    """La ligne est contextuelle ; elle ne doit pas diverger sur autre chose.

    Sans cette mesure, corriger une des deux et oublier l'autre passerait --
    c'est le defaut que le finding `I8` a paye dans l'autre sens.
    """
    assert RACCOURCIS_RESULTAT_AVEC_JOURNAL == RACCOURCIS_RESULTAT.replace(
        "  Échap ateliers", "  Tab journal  Échap ateliers")


# **Il n'y a PAS de test de budget de colonnes ici, et c'est une mesure, pas un
# oubli.** Ce banc en portait un ; la campagne du lot l'a trouve **tautologique**
# et l'a retire. Le mutant `M5` -- `EcranExecution.raccourcis` allongee a 91
# colonnes pour une zone utile de 76 -- lui a **survecu**, parce qu'il mesurait
# `jetons.colonnes(jetons.ajuster(ligne, utile))` : `ajuster` ABREGE a la
# largeur demandee, donc son resultat ne peut par construction jamais la
# depasser. Le test mesurait `ajuster`, pas la ligne.
#
# Le meme mutant est **tue 9 fois** par `test_repli_ascii.py`, qui mesure
# `jetons.colonnes(classe.raccourcis)` sans passer par `ajuster`, dans les deux
# regimes, et par un balayage de MODULES qui voit les lignes neuves sans qu'on
# ait rien a y declarer. Un second test ici n'ajouterait donc rien qu'une
# seconde source de verite.
#
# Le budget est de toute facon **inerte** sur cet arbitrage (chiffrage du
# 2026-09-02) : la cible fait 39 colonnes contre 41 pour la ligne d'avant --
# elle DETEND --, et ces lignes ne portant ni `⏎` ni `↑↓`, le repli ASCII les
# rend a largeur egale au caractere pres.
