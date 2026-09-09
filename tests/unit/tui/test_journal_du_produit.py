# -*- coding: utf-8 -*-
"""Story 11.4 -- le journal du produit, et le plantage qu'il fermait.

**Ce banc existe parce qu'aucun autre ne pouvait voir la panne.** Elle a ete
trouvee le 2026-08-30 en CAPTURANT les douze ecrans de l'atelier (lot `H1`),
c'est-a-dire en regardant le produit tourner -- la meme facon dont trois autres
defauts de cette vague ont ete trouves, et qu'aucun test n'avait vus.

La panne, en deux moities :

1. `extraction.run_extraction` declare `logger` en mot-cle **sans defaut** et le
   dereference sans garde (`logger.info(...)`) ;
2. le rappel que le PRODUIT injecte -- `ChaineReelle.extraire`, qui appelle
   `self._ouvrir_les_cadences(self.app, self.menu.dossier, rush_id)` -- n'en
   passe aucun.

Donc **toute** extraction lancee depuis `mmu-tui` tombait sur
`AttributeError: 'NoneType' object has no attribute 'info'`.

**Pourquoi les 7 754 tests etaient verts.** `test_parcours_extraction.py:298`
construit sa chaine avec un rappel a lui, qui passe `logger=JournalMuet()` --
et c'est le geste naturel de qui ecrit un banc. Le banc mesurait donc un
parcours qui n'est pas celui du produit, sur le seul point ou les deux
different. Ce fichier-ci mesure le chemin par defaut : celui qu'on obtient
quand on n'en dit rien, qui est celui que `chaine_du_produit` emprunte.

**Corollaire du meme manque, ferme ici aussi** : le journal de `E2-4` n'etait
alimente par rien. `SurfaceExecution.noter` n'y inscrit que l'avancement
chiffre ; les lignes que la maquette y montre sont des `logger.info` du coeur,
et elles n'avaient nulle part ou aller.
"""
import ast
import inspect
import logging
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import extraction
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui.avancement import Journal


# ---------------------------------------------------------------------------
# La panne elle-meme : le coeur EXIGE un logger, le produit n'en passait pas
# ---------------------------------------------------------------------------

def test_le_coeur_EXIGE_un_logger_et_le_dereference_SANS_GARDE():
    """Le contrat du coeur, mesure -- c'est lui qui rend l'oubli fatal.

    Si un jour `run_extraction` se dote d'un defaut ou d'une garde, ce test
    rougit : ce sera le signal que le correctif ci-dessous n'a plus la meme
    raison d'etre, pas qu'il faut le retirer sans regarder.
    """
    parametre = inspect.signature(extraction.run_extraction).parameters["logger"]
    assert parametre.default is inspect.Parameter.empty, (
        "run_extraction s'est dote d'un defaut pour `logger` : relire "
        "RelaisDeJournal, dont tout le motif est que ce parametre est "
        "obligatoire")
    corps = inspect.getsource(extraction.run_extraction)
    assert "logger." in corps
    assert "if logger" not in corps and "logger is None" not in corps, (
        "run_extraction garde desormais son logger : meme remarque")


def test_le_rappel_QUE_LE_PRODUIT_INJECTE_ne_passe_aucun_logger():
    """La seconde moitie de la panne, lue a la source et non supposee.

    C'est `ChaineReelle.extraire` qui appelle le rappel, et c'est
    `chaine_du_produit` qui l'injecte -- « ici, et nulle part ailleurs ». Le
    rappel recoit trois arguments positionnels et **rien d'autre** : le produit
    ne peut donc pas passer de logger, et ce n'est pas un oubli a corriger au
    point d'appel mais la forme meme du cablage.
    """
    import textwrap
    arbre = ast.parse(
        textwrap.dedent(inspect.getsource(atelier.ChaineReelle.extraire)))
    appels = [n for n in ast.walk(arbre)
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute)
              and n.func.attr == "_ouvrir_les_cadences"]
    assert len(appels) == 1, "un seul point d'appel, et il est nomme"
    assert not appels[0].keywords, (
        "le rappel du produit passe desormais des mots-cles : verifier que "
        "`logger` n'en fait pas partie, sinon RelaisDeJournal devient mort")


def test_UN_PARCOURS_SANS_LOGGER_S_EN_DOTE__c_est_le_correctif(tmp_path):
    """Le correctif, et il est STRUCTUREL : le trou ne peut plus etre rouvert.

    Meme geste que le lot `A` sur les raccourcis de saisie : on ne corrige pas
    le point d'appel fautif, on rend l'etat fautif inatteignable. Un futur
    appelant qui oublie le mot-cle obtient un journal, pas un `None`.
    """
    parcours = atelier.ParcoursExtraction(None, tmp_path, "rush_01")

    assert parcours._logger is not None, (
        "le parcours du produit repart avec `logger=None` : c'est LA panne, "
        "toute extraction lancee depuis mmu-tui tombe sur "
        "AttributeError: 'NoneType' object has no attribute 'info'")
    assert isinstance(parcours._logger, logging.Logger)
    assert callable(parcours._logger.info)
    assert isinstance(parcours._relais_de_journal, atelier.RelaisDeJournal)

    # Et le defaut de la SIGNATURE reste `None` : c'est bien le corps qui
    # comble, pas un defaut d'argument -- un defaut construit a la definition
    # serait partage par tous les parcours de toutes les sessions.
    assert (inspect.signature(atelier.ParcoursExtraction.__init__)
            .parameters["logger"].default is None)


def test_UN_LOGGER_EXPLICITE_N_EST_PAS_ECRASE(tmp_path):
    """Volet symetrique : les bancs qui en passent un doivent le garder.

    Sans ce volet, un correctif qui construirait le journal SANS REGARDER
    l'argument passerait le test precedent tout en cassant les 7 754 bancs qui
    injectent leur propre journal muet -- et on le decouvrirait a la suite
    complete plutot qu'ici.
    """
    a_moi = logging.getLogger("banc.a.moi")
    parcours = atelier.ParcoursExtraction(None, tmp_path, "rush_01",
                                          logger=a_moi)
    assert parcours._logger is a_moi
    assert parcours._relais_de_journal is None, (
        "un relais pose sur un logger fourni par l'appelant ecrirait dans le "
        "journal de E2-4 des lignes que cet appelant destine ailleurs")


# ---------------------------------------------------------------------------
# LE FIL, et pas seulement le mecanisme
# ---------------------------------------------------------------------------
#
# Ce bloc existe parce que la premiere version de ce fichier laissait SURVIVRE
# le mutant « le relais n'est jamais branche sur le journal de `E2-4` » : les
# neuf tests mesuraient le relais, sa politique d'attente, son desempilement --
# tout sauf le fil. C'est litteralement le mode de panne que ce banc corrige,
# reproduit dans le banc lui-meme.


class _PlanDouble:
    """Le minimum que `titre_de_la_tache` et `E2-4` lisent d'un plan."""

    def __init__(self, rush_id="rush_02", lots=("a", "b")):
        self.rush_id = rush_id
        self.lots = list(lots)


class _AppDouble:
    """Une application qui empile, sans `call_after_refresh`.

    Sans ce mot-cle, `_lancer_apres_le_dessin` appelle l'action directement --
    c'est le repli qu'il documente pour les appelants qui ne montent aucune
    application. L'ordre reste donc observable dans le fil du test.
    """

    def __init__(self):
        self.empiles = []

    def descendre(self, ecran):
        self.empiles.append(ecran)


def test_LE_RELAIS_EST_BRANCHE_sur_le_journal_de_l_ecran_QUI_VIENT_D_ETRE_MONTE(
        tmp_path, monkeypatch):
    """Le fil lui-meme : `_ecrire` doit viser le journal de `E2-4`.

    Deux choses sont mesurees, et la seconde est la plus fragile : que le
    relais soit branche **avant** que le coeur ne parte. Branche apres, les
    premieres lignes de l'extraction -- la qualification de la source, le
    compte de frames retenues -- tomberaient dans le vide, et le journal
    commencerait au milieu de son histoire.
    """
    vu = {}

    def lancement_double(app, ecran, plan, *, logger, extraire=None,
                         sur_suite=None, sur_rapport=None):
        # `sur_suite` est arrive au lot `K3` : le produit injecte desormais le
        # rappel des suites de `E2-5`. `sur_rapport` est arrive avec le passage
        # au fil du 2026-09-06. Ce banc-ci ne mesure que le journal, il accepte
        # donc les deux mots-cles sans les lire -- c'est
        # `test_suites_du_resultat.py` qui mesure que le premier est passe.

        # L'ordre, mesure a l'instant ou le coeur PARTIRAIT.
        vu["cible_au_depart"] = ecran.surface.journal
        vu["visee_au_depart"] = parcours._relais_de_journal._journal
        vu["logger"] = logger

    # **La cible du double a change avec le passage au fil** (2026-09-06) :
    # `_ecrire` n'appelle plus `executer_et_conclure` -- qui reste, synchrone,
    # pour les bancs -- mais `lancer_l_extraction`, qui prend le rendez-vous de
    # dessin PUIS part au fil de travail. Ce que ce banc mesure est inchange :
    # a l'instant ou le coeur partirait, le relais vise-t-il deja le journal de
    # l'ecran qui vient d'etre monte ?
    monkeypatch.setattr(atelier, "lancer_l_extraction", lancement_double)

    app = _AppDouble()
    parcours = atelier.ParcoursExtraction(app, tmp_path, "rush_02")
    parcours._ecrire(_PlanDouble())

    ecran = app.empiles[-1]
    assert parcours._relais_de_journal._journal is ecran.surface.journal, (
        "le relais ne vise pas le journal de l'ecran monte : les lignes du "
        "coeur n'arrivent nulle part et E2-4 reste vide, ce qui est "
        "exactement le corollaire de la panne que ce fichier ferme")
    assert vu["visee_au_depart"] is vu["cible_au_depart"], (
        "le relais est branche APRES le depart du coeur : les premieres "
        "lignes de l'extraction sont perdues")

    # Et ce qui part au coeur est bien le journal du produit, pas un `None`.
    assert vu["logger"] is parcours._logger
    assert callable(vu["logger"].info)

    # Bout a bout : une ligne emise par le coeur atterrit dans l'ecran.
    parcours._logger.info("Manifest mis a jour: lot %s", "rush_02_25")
    assert ecran.surface.journal.lignes == [
        "Manifest mis a jour: lot rush_02_25"]


# ---------------------------------------------------------------------------
# Le relais : ce qui arrive au journal de `E2-4`, et ce qui n'y arrive pas
# ---------------------------------------------------------------------------

def test_les_lignes_du_coeur_arrivent_au_journal_UNE_FOIS_L_ECRAN_MONTE():
    """Le corollaire : sans ce relais, le journal de `E2-4` reste vide a jamais."""
    logger, relais = atelier.journal_du_produit()
    journal = Journal()
    relais.viser(journal)

    # Deux lignes DISTINGUABLES, et l'ordre compte : un journal se lit de la
    # plus ancienne a la plus recente (regle des fabriques -- une seule ligne
    # rendrait une permutation invisible).
    logger.info("Source qualifiee: cadence %s im/s", 25)
    logger.info("Manifest mis a jour: lot %s", "rush_01_25")

    assert journal.lignes == ["Source qualifiee: cadence 25 im/s",
                              "Manifest mis a jour: lot rush_01_25"]


def test_AVANT_le_montage_de_l_ecran_rien_n_est_MIS_EN_ATTENTE():
    """Volet symetrique, et c'est une decision, pas un effet de bord.

    Le plan est prepare et juge avant que `E2-4` n'existe. Ces lignes-la sont
    **jetees** : un relais qui les mettrait en attente deverserait d'un coup,
    au montage de l'ecran, un passe que l'operateur n'a pas demande a lire.
    """
    logger, relais = atelier.journal_du_produit()
    logger.info("Sondage de la source")        # aucune cible : jetee
    journal = Journal()
    relais.viser(journal)
    assert journal.lignes == []

    logger.info("Premiere frame ecrite")
    assert journal.lignes == ["Premiere frame ecrite"]


def test_DEUX_parcours_successifs_n_inscrivent_PAS_CHAQUE_LIGNE_DEUX_FOIS():
    """`logging.getLogger` est un singleton par nom : les relais s'empilaient.

    Sans le desempilement, la deuxieme extraction d'une meme session ecrirait
    chaque ligne deux fois, la troisieme trois fois. C'est le genre de defaut
    qu'un banc a un seul parcours ne peut pas voir -- la regle des fabriques,
    appliquee au temps plutot qu'a une collection.
    """
    _, premier = atelier.journal_du_produit()
    logger, second = atelier.journal_du_produit()
    journal = Journal()
    second.viser(journal)
    premier.viser(journal)                     # l'ancien, s'il survivait

    logger.info("une seule fois")
    assert journal.lignes == ["une seule fois"], (
        f"la ligne est inscrite {len(journal.lignes)} fois : les relais "
        "s'empilent d'un parcours a l'autre")

    relais = [h for h in logger.handlers
              if isinstance(h, atelier.RelaisDeJournal)]
    assert len(relais) == 1


def test_le_journal_du_produit_n_ECRIT_JAMAIS_par_dessus_l_interface():
    """Sous une TUI, un handler herite du racine ecrit sur `stdout` en plein ecran."""
    logger, _ = atelier.journal_du_produit()
    assert logger.propagate is False
    assert logger.name == atelier.NOM_DU_JOURNAL
    assert logger.name != "", "jamais le racine : il capterait les tierces parties"


def test_une_ligne_de_journal_RATEE_ne_fait_pas_tomber_l_extraction():
    """Contrat de `logging.Handler`, et il n'est pas theorique ici.

    L'extraction que la ligne raconte vaut plus que la ligne. Un journal qui
    leve arreterait le coeur au milieu d'une ecriture de frames.
    """
    logger, relais = atelier.journal_du_produit()

    class JournalQuiCasse:
        def inscrire(self, ligne):
            raise RuntimeError("disque plein")

    relais.viser(JournalQuiCasse())
    relais.handleError = lambda record: None   # silencieux, comme `logging` l'est
    logger.info("ceci ne doit pas remonter")   # ne leve pas


@pytest.fixture(autouse=True)
def _journal_propre():
    """Chaque test repart d'un logger sans relais : le nom est un singleton."""
    yield
    logger = logging.getLogger(atelier.NOM_DU_JOURNAL)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
