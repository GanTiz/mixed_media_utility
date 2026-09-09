# Story 7.0, AC 4 et AC 5 -- l'executeur appelle le coeur EN PROCESSUS
# (jamais un sous-processus CLI), les etats en-cours -> terminee / echouee
# sont observables par signaux, le motif d'echec est le str(exc) verbatim
# du coeur, et le rappel de progression est optionnel de bout en bout.

import subprocess
import threading

import pytest

from mixed_media_utility import page_templates, scan_crop
from mixed_media_utility.gui import executeur as executeur_module
from mixed_media_utility.gui.coquille import Coquille
from mixed_media_utility.gui.executeur import (
    ECHOUEE,
    EN_COURS,
    Executeur,
    TERMINEE,
    tache_de_demonstration,
)


@pytest.fixture
def file_de_taches(qtbot):
    ex = Executeur()
    yield ex
    # Ne jamais laisser un thread de travail survivre au test.
    assert ex.attendre(10000)


@pytest.fixture
def coquille(qtbot):
    fenetre = Coquille()
    qtbot.addWidget(fenetre)
    fenetre.show()
    qtbot.waitExposed(fenetre)
    return fenetre


# ---------------------------------------------------------------------------
# Fabrique de taches de test -- regle des fabriques : AU MOINS DEUX taches
# DISTINGUABLES (fonctions differentes, resultats differents), et un test
# observe la tache en SECONDE position de la file.
# ---------------------------------------------------------------------------


def _tache_alpha():
    return "resultat-alpha"


def _tache_beta():
    return "resultat-beta"


def fabrique_taches():
    """Deux taches distinguables : (fonction, resultat attendu)."""
    return [(_tache_alpha, "resultat-alpha"), (_tache_beta, "resultat-beta")]


def test_la_fabrique_produit_des_taches_distinguables():
    taches = fabrique_taches()
    assert len(taches) >= 2
    fonctions = [f for f, _ in taches]
    resultats = [r for _, r in taches]
    assert len(set(fonctions)) == len(fonctions)
    assert len(set(resultats)) == len(resultats)


# ---------------------------------------------------------------------------
# AC 4 -- nominal : une vraie fonction du coeur, dans le meme processus.
# ---------------------------------------------------------------------------


def test_une_tache_du_coeur_passe_en_cours_puis_terminee(
    qtbot, file_de_taches, monkeypatch
):
    # Aucun sous-processus : le premier appel a subprocess.Popen echoue.
    def _interdit(*args, **kwargs):
        raise AssertionError("sous-processus interdit : le coeur est heberge en processus (FR1)")

    monkeypatch.setattr(subprocess, "Popen", _interdit)

    tache = file_de_taches.soumettre(tache_de_demonstration)
    assert tache.etat in (EN_COURS, TERMINEE)  # en cours des la soumission
    qtbot.waitUntil(lambda: tache.etat == TERMINEE, timeout=5000)

    # Le resultat est celui du coeur, confronte a une attente calculee
    # INDEPENDAMMENT (le gabarit du depot, pas une recopie du module).
    plan = tache.resultat
    spec = page_templates.get_template(executeur_module.GABARIT_DEMONSTRATION)
    assert plan.template_id == executeur_module.GABARIT_DEMONSTRATION
    assert len(plan.frames) == spec.frames_per_page
    indices = [frame.slot_index for frame in plan.frames]
    assert indices == sorted(indices) and len(set(indices)) == len(indices)
    assert tache.motif is None


def test_les_transitions_sont_observables_par_signaux(qtbot, file_de_taches):
    # La connexion se fait pendant que la tache est BLOQUEE : l'emission ne
    # peut pas preceder l'abonnement, le test est deterministe.
    barriere = threading.Event()

    def tache_bloquee():
        assert barriere.wait(10), "barriere jamais relachee"
        return "debloquee"

    tache = file_de_taches.soumettre(tache_bloquee)
    with qtbot.waitSignal(tache.terminee, timeout=5000) as observation:
        barriere.set()
    assert observation.args == ["debloquee"]
    assert tache.etat == TERMINEE


# ---------------------------------------------------------------------------
# AC 4 -- l'atelier reste utilisable pendant l'execution.
# ---------------------------------------------------------------------------


def test_deux_bascules_d_atelier_pendant_une_tache_bloquee(
    qtbot, coquille, file_de_taches
):
    barriere = threading.Event()

    def tache_bloquee():
        assert barriere.wait(10), "barriere jamais relachee"
        return "fini"

    tache = file_de_taches.soumettre(tache_bloquee)
    ateliers = coquille.ateliers()
    try:
        # Deux bascules d'onglet pendant que la tache tourne ; chacune
        # aboutit (l'onglet actif rapporte le nom vise).
        coquille.activer_atelier(2)
        qtbot.waitUntil(lambda: coquille.atelier_actif() == ateliers[2], timeout=2000)
        assert tache.etat == EN_COURS  # la bascule n'a rien interrompu
        coquille.activer_atelier(1)
        qtbot.waitUntil(lambda: coquille.atelier_actif() == ateliers[1], timeout=2000)
        assert tache.etat == EN_COURS
    finally:
        barriere.set()
    qtbot.waitUntil(lambda: tache.etat == TERMINEE, timeout=5000)
    assert tache.resultat == "fini"


# ---------------------------------------------------------------------------
# AC 4 -- echec : motif verbatim du coeur, jamais un crash.
# ---------------------------------------------------------------------------


def test_une_exception_typee_du_coeur_devient_echouee_motif_verbatim(
    qtbot, coquille, file_de_taches
):
    # L'attendu se calcule en appelant le coeur DIRECTEMENT : le motif de
    # la tache doit etre octet pour octet le str() de l'exception typee.
    def appel_fautif():
        return scan_crop.build_page_crop_plan(
            template_id="tpl-inexistant-v1", slots=[], dpi=300
        )

    with pytest.raises(Exception) as attendu:
        appel_fautif()
    motif_attendu = str(attendu.value)
    assert motif_attendu  # le coeur ecrit un message, la GUI le lira

    tache = file_de_taches.soumettre(appel_fautif)
    qtbot.waitUntil(lambda: tache.etat == ECHOUEE, timeout=5000)
    assert tache.motif == motif_attendu
    assert tache.resultat is None

    # Jamais un crash d'application : la fenetre repond encore.
    ateliers = coquille.ateliers()
    coquille.activer_atelier(3)
    qtbot.waitUntil(lambda: coquille.atelier_actif() == ateliers[3], timeout=2000)


# ---------------------------------------------------------------------------
# AC 4 -- une exception de CONTROLE (KeyboardInterrupt, SystemExit) tuant le
# thread de travail ne doit jamais laisser la tache EN_COURS pour toujours
# (revue de vague 1 : `except Exception` ne les attrapait pas, aucun signal
# n'etait emis, tout attendeur restait suspendu).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exception_de_controle", [KeyboardInterrupt, SystemExit])
def test_une_exception_de_controle_ne_laisse_pas_la_tache_en_cours_pour_toujours(
    qtbot, file_de_taches, exception_de_controle
):
    motif = f"controle-{exception_de_controle.__name__}"

    def tache_interrompue():
        raise exception_de_controle(motif)

    tache = file_de_taches.soumettre(tache_interrompue)
    # Sans le correctif, cet etat n'est JAMAIS atteint (BaseException
    # traverse `_Execution.run` sans emettre ``echouee``) : le test
    # echouerait par timeout, pas par assertion.
    qtbot.waitUntil(lambda: tache.etat == ECHOUEE, timeout=5000)
    assert tache.motif == motif  # motif verbatim, meme regle que le coeur
    assert tache.resultat is None


# ---------------------------------------------------------------------------
# AC 4 -- la tache en SECONDE position rapporte SON etat et SON resultat.
# ---------------------------------------------------------------------------


def test_la_tache_en_seconde_position_rapporte_son_resultat(qtbot, file_de_taches):
    barriere = threading.Event()

    def premiere_bloquee():
        assert barriere.wait(10), "barriere jamais relachee"
        return fabrique_taches()[0][1]

    fonction_seconde, resultat_seconde = fabrique_taches()[1]

    premiere = file_de_taches.soumettre(premiere_bloquee)
    seconde = file_de_taches.soumettre(fonction_seconde)

    # File serielle : tant que la premiere bloque, la seconde n'a pas fini.
    assert seconde.etat == EN_COURS
    assert seconde.resultat is None

    barriere.set()
    qtbot.waitUntil(lambda: seconde.etat == TERMINEE, timeout=5000)
    # L'etat et le resultat rapportes sont LES SIENS, pas ceux de la
    # premiere (regle des fabriques : cible hors premiere position).
    assert seconde.resultat == resultat_seconde
    assert seconde.resultat != premiere.resultat
    qtbot.waitUntil(lambda: premiere.etat == TERMINEE, timeout=5000)
    assert premiere.resultat == fabrique_taches()[0][1]


# ---------------------------------------------------------------------------
# AC 5 -- rappel de progression optionnel de bout en bout.
# ---------------------------------------------------------------------------


def test_sans_rappel_la_tache_de_demonstration_fonctionne(qtbot, file_de_taches):
    tache = file_de_taches.soumettre(tache_de_demonstration)
    qtbot.waitUntil(lambda: tache.etat == TERMINEE, timeout=5000)
    assert tache.resultat is not None


def test_avec_rappel_la_tache_de_demonstration_l_invoque(qtbot, file_de_taches):
    jalons = []
    tache = file_de_taches.soumettre(
        tache_de_demonstration, rappel_progression=lambda *args: jalons.append(args)
    )
    qtbot.waitUntil(lambda: tache.etat == TERMINEE, timeout=5000)
    assert jalons == [(0, 1), (1, 1)]
    # Le resultat est identique avec et sans rappel : le rappel observe,
    # il ne change pas le calcul.
    temoin = file_de_taches.soumettre(tache_de_demonstration)
    qtbot.waitUntil(lambda: temoin.etat == TERMINEE, timeout=5000)
    assert temoin.resultat == tache.resultat


def test_le_rappel_n_est_pas_impose_a_une_fonction_qui_ne_le_declare_pas(
    qtbot, file_de_taches
):
    # Une fonction du coeur SANS parametre de rappel s'execute a
    # l'identique meme quand l'appelant fournit un rappel : l'executeur ne
    # le transmet qu'aux taches qui savent le consommer (AR3 : rappels
    # optionnels, jamais un parametre obligatoire).
    appels = []
    fonction, resultat_attendu = fabrique_taches()[1]
    tache = file_de_taches.soumettre(
        fonction, rappel_progression=lambda *args: appels.append(args)
    )
    qtbot.waitUntil(lambda: tache.etat == TERMINEE, timeout=5000)
    assert tache.resultat == resultat_attendu
    assert appels == []  # jamais transmis de force
