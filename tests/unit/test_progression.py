"""Banc du canal de progression du coeur (story 5.28).

Deux sujets, dans cet ordre :

* :class:`EstimateurTempsRestant` -- le calcul pur, horloge simulee. C'est la
  que se jouent l'interdit d'`EPIC7-ARB-67` (aucun temps sans mesure reelle) et
  la borne d'estimation ;
* :class:`EmetteurProgression` -- la surface d'emission, et son innocuite
  (`EPIC7-ARB-79`).

Le vocabulaire est un interdit mesure (`EPIC7-ARB-80`) : le dernier test du
fichier le verifie sur le module **et sur ce banc**.
"""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import pytest

from mixed_media_utility import progression


# ---------------------------------------------------------------------------
# Horloge simulee
# ---------------------------------------------------------------------------


class HorlogeSimulee:
    """Horloge monotone pilotee a la main, en secondes."""

    def __init__(self, depart: float = 1000.0) -> None:
        self.instant = float(depart)

    def __call__(self) -> float:
        return self.instant

    def avancer(self, secondes: float) -> float:
        self.instant += float(secondes)
        return self.instant


@pytest.fixture
def horloge() -> HorlogeSimulee:
    return HorlogeSimulee()


def _estimateur(horloge, fenetre=None):
    if fenetre is None:
        return progression.EstimateurTempsRestant(horloge=horloge)
    return progression.EstimateurTempsRestant(fenetre_secondes=fenetre, horloge=horloge)


# ---------------------------------------------------------------------------
# AC 1 -- la forme du calculateur
# ---------------------------------------------------------------------------


def test_l_horloge_par_defaut_est_monotonic_et_jamais_l_horloge_murale():
    """AC 1 : `time.time` recule quand l'horloge systeme est ajustee."""
    estimateur = progression.EstimateurTempsRestant()
    assert estimateur.horloge is time.monotonic
    assert estimateur.horloge is not time.time


def test_la_fenetre_glissante_est_une_constante_nommee_du_module():
    """AC 1 : la duree de fenetre ne se dissemine pas en litteraux."""
    assert progression.FENETRE_GLISSANTE_SECONDES > 0
    assert (
        progression.EstimateurTempsRestant().fenetre_secondes
        == progression.FENETRE_GLISSANTE_SECONDES
    )


def test_le_module_de_progression_ne_depend_ni_de_qt_ni_du_disque_ni_de_ffmpeg():
    """AC 1 : calcul pur -- aucun import de `gui/`, de Qt, de subprocess ni de cv2."""
    source = Path(progression.__file__).read_text(encoding="utf-8")
    for interdit in ("PySide", "PyQt", "import cv2", "subprocess", "mixed_media_utility.gui"):
        assert interdit not in source, f"import interdit dans progression.py : {interdit}"


def test_une_fenetre_non_positive_est_refusee_a_la_construction():
    for mauvaise in (0.0, -1.0):
        with pytest.raises(ValueError):
            progression.EstimateurTempsRestant(fenetre_secondes=mauvaise)


# ---------------------------------------------------------------------------
# AC 2 -- les quatre regimes qui ne rendent AUCUN temps
# ---------------------------------------------------------------------------


def test_aucun_jalon_note_ne_rend_aucun_temps(horloge):
    """AC 2, regime 1 : rien n'a ete note."""
    estimateur = _estimateur(horloge)
    assert estimateur.temps_restant is None
    assert estimateur.secondes_par_frame is None


def test_un_seul_jalon_ne_rend_aucun_temps(horloge):
    """AC 2, regime 2 : une seule mesure ne mesure aucune duree."""
    estimateur = _estimateur(horloge)
    estimateur.noter(3, 10)
    assert estimateur.temps_restant is None
    assert estimateur.secondes_par_frame is None


def test_aucune_frame_faite_ne_rend_aucun_temps(horloge):
    """AC 2, regime 3 : `faites == 0`, meme sur plusieurs jalons."""
    estimateur = _estimateur(horloge)
    estimateur.noter(0, 10)
    horloge.avancer(1.0)
    estimateur.noter(0, 10)
    assert estimateur.temps_restant is None


def test_une_tache_qui_cale_ne_rend_aucun_temps(horloge):
    """AC 2, regime 4 : accroissement nul sur la fenetre."""
    estimateur = _estimateur(horloge, fenetre=5.0)
    estimateur.noter(2, 10)
    horloge.avancer(1.0)
    estimateur.noter(4, 10)
    assert estimateur.temps_restant is not None
    # La tache cale : plus rien n'avance, et les jalons utiles sortent de la
    # fenetre. Aucun chiffre ne doit survivre a cette sortie.
    horloge.avancer(60.0)
    assert estimateur.temps_restant is None
    assert estimateur.secondes_par_frame is None


def test_l_absence_de_temps_est_None_jamais_zero_ni_infini(horloge):
    """AC 2 : « il reste 0 seconde » est un mensonge, pas une absence."""
    estimateur = _estimateur(horloge)
    for valeur in (estimateur.temps_restant, estimateur.secondes_par_frame):
        assert valeur is None
        assert valeur != 0
        assert valeur != float("inf")


def test_deux_jalons_au_meme_instant_ne_rendent_aucun_temps(horloge):
    """AC 1, garde numerique : duree nulle, pas de division par zero."""
    estimateur = _estimateur(horloge)
    estimateur.noter(1, 10)
    estimateur.noter(5, 10)  # meme instant : l'horloge n'a pas avance
    assert estimateur.secondes_par_frame is None
    assert estimateur.temps_restant is None


# ---------------------------------------------------------------------------
# AC 1 -- les gardes numeriques sur `noter`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("faites, total", [(1, 0), (1, -3), (-1, 10), (11, 10)])
def test_un_jalon_hors_bornes_est_ignore_et_ne_rend_aucun_temps(horloge, faites, total):
    """AC 1 : total nul ou negatif, `faites` negatif ou au-dela du total."""
    estimateur = _estimateur(horloge)
    assert estimateur.noter(faites, total) is False
    horloge.avancer(1.0)
    assert estimateur.noter(faites, total) is False
    assert estimateur.temps_restant is None


def test_un_jalon_qui_recule_est_ignore(horloge):
    """AC 1 : `faites` decroissant ne se note pas."""
    estimateur = _estimateur(horloge)
    estimateur.noter(6, 10)
    horloge.avancer(1.0)
    assert estimateur.noter(3, 10) is False
    assert estimateur.faites == 6


def test_un_jalon_illisible_est_ignore_sans_lever(horloge):
    estimateur = _estimateur(horloge)
    assert estimateur.noter("beaucoup", 10) is False
    assert estimateur.noter(3, None) is False
    assert estimateur.temps_restant is None


@pytest.mark.parametrize(
    "faites, total",
    [
        (float("inf"), 10),
        (float("-inf"), 10),
        (1, float("inf")),
        (1, float("-inf")),
        (float("nan"), 10),
        (1, float("nan")),
    ],
)
def test_un_jalon_non_fini_est_ignore_sans_lever(horloge, faites, total):
    """AC 11 (EC-6) : `int(inf)` leve `OverflowError`, pas `ValueError`.

    Le contrat ecrit sur `noter` est « les jalons hors bornes sont **ignores**,
    jamais refuses par une exception ». Les trois `except (TypeError,
    ValueError)` du module attrapaient `nan` et laissaient passer l'infini : la
    surface publique levait alors que sa docstring promet le contraire.
    """
    estimateur = _estimateur(horloge)
    assert estimateur.noter(faites, total) is False
    assert estimateur.temps_restant is None


def test_un_total_different_reinitialise_la_mesure(horloge):
    """AC 1 et AC 7 : un denominateur fige au premier lot est le defaut traque.

    Deux lots de cardinaux **differents** se suivent ; la mesure du premier ne
    doit rien dire du second, et le total rendu est celui du lot courant.
    """
    estimateur = _estimateur(horloge)
    for faites in (1, 2, 3):
        estimateur.noter(faites, 3)
        horloge.avancer(0.1)
    assert estimateur.total == 3
    estimateur.noter(1, 20)
    assert estimateur.total == 20
    # Un seul jalon sur le nouveau lot : aucune mesure, donc aucun temps.
    assert estimateur.temps_restant is None


def test_reinitialiser_efface_toute_mesure(horloge):
    estimateur = _estimateur(horloge)
    estimateur.noter(1, 10)
    horloge.avancer(1.0)
    estimateur.noter(4, 10)
    assert estimateur.temps_restant is not None
    estimateur.reinitialiser()
    assert estimateur.temps_restant is None
    assert estimateur.total is None
    assert estimateur.faites == 0


def test_une_tache_terminee_rend_zero_seconde_restante(horloge):
    """`faites == total` : la mesure existe et vaut reellement zero."""
    estimateur = _estimateur(horloge)
    estimateur.noter(0, 4)
    for faites in (1, 2, 3, 4):
        horloge.avancer(0.5)
        estimateur.noter(faites, 4)
    assert estimateur.temps_restant == 0.0


# ---------------------------------------------------------------------------
# AC 3 -- l'estimation est bornee, et elle SUIT
# ---------------------------------------------------------------------------


def test_l_estimation_reste_dans_une_borne_relative_a_temps_par_frame_connu(horloge):
    """AC 3 : source factice a temps par frame connu, avec gigue de +/- 10 %.

    Sans gigue le calcul serait exact et le test ne mesurerait rien. La gigue
    est deterministe (graine fixee) et la borne relative est ecrite ici :
    **15 %**, soit une fois et demie l'amplitude de la gigue.
    """
    reference = 0.20  # secondes par frame ecrite
    borne_relative = 0.15
    total = 60
    alea = random.Random(20260826)
    estimateur = _estimateur(horloge, fenetre=2.0)

    ecarts_mesures = []
    points_verifies = 0
    for faites in range(1, total + 1):
        horloge.avancer(reference * alea.uniform(0.9, 1.1))
        estimateur.noter(faites, total)
        # Trois points de la course : fenetre tout juste pleine, milieu, fin.
        if faites in (15, 30, total - 1):
            points_verifies += 1
            attendu = reference * (total - faites)
            obtenu = estimateur.temps_restant
            assert obtenu is not None
            ecart = abs(obtenu - attendu) / max(attendu, 1e-9)
            ecarts_mesures.append(ecart)
            assert ecart <= borne_relative, (
                f"a {faites}/{total} frames : {obtenu:.3f} s contre {attendu:.3f} s "
                f"attendues, ecart relatif {ecart:.1%} > {borne_relative:.0%}"
            )
    assert points_verifies == 3
    assert len(ecarts_mesures) == 3


def test_l_estimation_suit_un_changement_de_regime_grace_a_la_fenetre(horloge):
    """AC 3 : une moyenne depuis le debut echoue a ce test.

    Trente frames lentes puis trente rapides. La fenetre glissante ne voit plus
    que le regime rapide ; une moyenne depuis le debut resterait tiree vers le
    haut par les frames lentes.
    """
    lent, rapide = 0.50, 0.05
    total = 60
    estimateur = _estimateur(horloge, fenetre=1.0)

    for faites in range(1, 31):
        horloge.avancer(lent)
        estimateur.noter(faites, total)
    for faites in range(31, total):
        horloge.avancer(rapide)
        estimateur.noter(faites, total)

    restantes = total - (total - 1)
    attendu_fenetre = rapide * restantes
    obtenu = estimateur.temps_restant
    assert obtenu is not None
    assert obtenu == pytest.approx(attendu_fenetre, rel=0.25)

    # La verite arithmetique d'une moyenne depuis le debut, ecrite ici pour que
    # le mutant « fenetre -> depuis le debut » ne puisse pas survivre.
    duree_totale = lent * 30 + rapide * 29
    moyenne_depuis_le_debut = (duree_totale / (total - 1)) * restantes
    assert moyenne_depuis_le_debut > obtenu * 3


def test_la_fenetre_ne_retient_que_les_jalons_plus_recents_que_sa_duree(horloge):
    """AC 1 : la borne de fenetre est stricte et se mesure."""
    estimateur = _estimateur(horloge, fenetre=3.0)
    estimateur.noter(0, 100)  # a t + 0, sortira de la fenetre
    horloge.avancer(1.0)
    estimateur.noter(10, 100)  # a t + 1
    horloge.avancer(1.0)
    estimateur.noter(20, 100)  # a t + 2
    # Fenetre pleine : de t+0 a t+2, 20 frames en 2 s -> 0,1 s par frame.
    assert estimateur.secondes_par_frame == pytest.approx(0.1)
    # A t + 3,5 le jalon de t + 0 est sorti : de t+1 a t+2, 10 frames en 1 s.
    horloge.avancer(1.5)
    assert estimateur.secondes_par_frame == pytest.approx(0.1)
    estimateur.noter(21, 100)  # a t + 3,5 : 11 frames en 2,5 s
    assert estimateur.secondes_par_frame == pytest.approx(2.5 / 11)


def test_un_jalon_tombant_EXACTEMENT_sur_la_borne_de_fenetre_en_sort(horloge):
    """AC 1 (EC-4) : la borne est **stricte**, et la mesure le voit.

    Aucun test ne faisait tomber un jalon exactement sur `reference - fenetre` :
    le mutant `jalon[0] > limite` -> `jalon[0] >= limite` survivait a 59 tests
    sur 59. Ici les deux lectures donnent deux chiffres differents, ecrits
    l'un et l'autre.
    """
    estimateur = _estimateur(horloge, fenetre=3.0)
    estimateur.noter(0, 100)          # a t + 0
    horloge.avancer(1.0)
    estimateur.noter(10, 100)         # a t + 1
    horloge.avancer(2.0)
    estimateur.noter(20, 100)         # a t + 3 : le jalon de t + 0 est SUR la borne

    # Borne stricte : le jalon de t + 0 sort. De t+1 a t+3, 10 frames en 2 s.
    assert estimateur.secondes_par_frame == pytest.approx(2.0 / 10)
    # Une borne relachee (`>=`) le garderait : 20 frames en 3 s, soit 0,15 --
    # ecrit ici pour que le mutant ne puisse pas se cacher derriere un `approx`.
    assert estimateur.secondes_par_frame != pytest.approx(3.0 / 20)
    assert estimateur.temps_restant == pytest.approx(0.2 * 80)


@pytest.mark.parametrize("pas", [4.9, 5.0, 6.0])
def test_un_travail_plus_lent_que_la_fenetre_rend_toujours_une_estimation(pas):
    """AC 3 (EC-5) : la fenetre borne la moyenne, elle n'eteint pas la mesure.

    Des que deux jalons consecutifs etaient espaces d'au moins
    `FENETRE_GLISSANTE_SECONDES` (5,0 s), la liste retombait a un element et
    `temps_restant` rendait `None` **pour toujours** -- alors que le regime
    concerne, une unite de travail plus lente que la fenetre (une frame de scan
    16 bits), est celui ou l'estimation sert le plus. Les trois pas encadrent la
    bascule mesuree : 4,9 s rendait un chiffre, 5,0 s et 6,0 s rendaient `None`.
    """
    horloge = HorlogeSimulee()
    estimateur = progression.EstimateurTempsRestant(horloge=horloge)
    total = 100
    for faites in range(1, 21):
        horloge.avancer(pas)
        estimateur.noter(faites, total)

    par_frame = estimateur.secondes_par_frame
    assert par_frame is not None, f"pas = {pas} s : plus aucune mesure"
    assert par_frame == pytest.approx(pas, rel=0.05)
    restant = estimateur.temps_restant
    assert restant is not None
    assert restant == pytest.approx(pas * (total - 20), rel=0.05)


def test_faites_ne_recule_jamais_apres_un_calage(horloge):
    """BH-1 : la jauge ne retombe pas de 50 % a 0 % parce qu'on l'a lue.

    Mesure d'origine : `faites=50 total=100` en marche, puis `faites=0
    total=100` apres trente secondes de calage -- un recul de la jauge, que
    `count_written_temp_frames` cite pourtant `EPIC7-ARB-79` comme interdisant.
    `EmetteurProgression` impose la monotonie ; l'estimateur, qui porte le
    `total`, ne l'imposait pas.
    """
    estimateur = _estimateur(horloge, fenetre=5.0)
    for faites in (10, 30, 50):
        estimateur.noter(faites, 100)
        horloge.avancer(1.0)
    assert estimateur.faites == 50
    assert estimateur.total == 100
    assert estimateur.temps_restant is not None

    horloge.avancer(30.0)
    # La mesure meurt -- c'est l'interdit d'`EPIC7-ARB-67` --, mais le compte,
    # lui, reste ce qu'il est : 50 frames sur 100 ont bien ete faites.
    assert estimateur.temps_restant is None
    assert estimateur.faites == 50
    assert estimateur.total == 100


def test_lire_le_temps_par_frame_ne_deplace_pas_ce_qu_il_lit(horloge):
    """BH-1 : une propriete de lecture ne doit pas muter l'etat observable.

    L'elagage etait pratique **depuis** `secondes_par_frame` : deux lectures
    consecutives, sans rien noter entre les deux, ne rendaient pas la meme chose
    et faisaient bouger `faites`.
    """
    estimateur = _estimateur(horloge, fenetre=5.0)
    estimateur.noter(10, 100)
    horloge.avancer(1.0)
    estimateur.noter(30, 100)
    horloge.avancer(1.0)
    estimateur.noter(50, 100)

    premiere = estimateur.secondes_par_frame
    faites_apres_lecture = estimateur.faites
    seconde = estimateur.secondes_par_frame
    assert premiere is not None
    assert seconde == premiere
    assert faites_apres_lecture == estimateur.faites == 50

    # Meme exigence apres le calage, la ou le defaut mordait.
    horloge.avancer(30.0)
    assert estimateur.secondes_par_frame is None
    assert estimateur.faites == 50
    assert estimateur.secondes_par_frame is None
    assert estimateur.faites == 50


def test_les_jalons_d_egalite_allongent_la_fenetre_et_degradent_la_mesure(horloge):
    """BH-4 : « l'egalite est legitime » n'etait mesure par rien.

    Le mutant `faites < dernier` -> `faites <= dernier` survivait a 32 tests sur
    32 : les jalons a `faites` constant cessaient d'etre notes, donc la fenetre
    cessait de s'allonger et le temps par frame **gelait** sur sa derniere valeur
    optimiste avant de sauter a `None`. Ici il doit se **degrader** pendant que
    le travail patine.
    """
    estimateur = _estimateur(horloge, fenetre=5.0)
    estimateur.noter(10, 100)
    horloge.avancer(1.0)
    estimateur.noter(20, 100)
    assert estimateur.secondes_par_frame == pytest.approx(0.1)

    degradation = []
    for _ in range(3):
        horloge.avancer(1.0)
        # Le travail patine : le meme compte est note, et c'est legitime.
        assert estimateur.noter(20, 100) is True
        degradation.append(estimateur.secondes_par_frame)

    assert degradation == pytest.approx([0.2, 0.3, 0.4])
    assert degradation == sorted(degradation)
    assert degradation[-1] > 0.1 * 3


def test_une_tache_calee_ne_survit_pas_a_l_elagage_a_deux_jalons(horloge):
    """AC 2 (EC-5, garde-fou) : le plancher a deux jalons n'ouvre pas de trou.

    Conserver deux jalons quoi qu'il arrive rendrait un chiffre herite pendant
    qu'une tache calee ne bouge plus -- exactement l'interdit d'`EPIC7-ARB-67`.
    Le plancher ne s'applique donc que si le jalon **le plus recent** est encore
    dans la fenetre.
    """
    estimateur = _estimateur(horloge, fenetre=5.0)
    estimateur.noter(10, 100)
    horloge.avancer(6.0)
    estimateur.noter(20, 100)
    assert estimateur.secondes_par_frame == pytest.approx(0.6)
    # Plus rien n'est note et l'horloge continue : le dernier jalon sort a son
    # tour de la fenetre, et la mesure doit mourir avec lui.
    horloge.avancer(30.0)
    assert estimateur.secondes_par_frame is None
    assert estimateur.temps_restant is None


# ---------------------------------------------------------------------------
# AC 11 / AC 5 -- l'emetteur : monotone, borne, et innocent
# ---------------------------------------------------------------------------


class Collecteur:
    """Rappel de test : enregistre les jalons recus, et leve si on le demande."""

    def __init__(self, leve: bool = False) -> None:
        self.jalons: list[tuple[int, int]] = []
        self.leve = leve

    def __call__(self, faites, total):
        self.jalons.append((faites, total))
        if self.leve:
            raise RuntimeError("rappel fautif de l'appelant")


def _emetteur(collecteur, total, **kwargs):
    return progression.EmetteurProgression(collecteur, total, **kwargs)


def test_l_emetteur_n_emet_qu_une_avancee_reelle():
    """AC 5 : monotone, sans doublon."""
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 10)
    assert emetteur.emettre(0) is False
    assert emetteur.emettre(3) is True
    assert emetteur.emettre(3) is False
    assert emetteur.emettre(2) is False
    assert emetteur.emettre(7) is True
    assert collecteur.jalons == [(3, 10), (7, 10)]


def test_l_emetteur_ne_depasse_jamais_le_total():
    """AC 5 : un comptage surnumeraire est borne, jamais transmis tel quel."""
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 4)
    emetteur.emettre(9)
    assert collecteur.jalons == [(4, 4)]


def test_l_emetteur_ne_force_jamais_le_total_a_la_fin():
    """AC 5 et AC 12 : le dernier jalon reste SOUS le total quand le travail
    observe a produit moins que prevu. Forcer 100 % echangerait un mensonge
    d'affichage contre un faux succes (risque R12)."""
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 10)
    emetteur.emettre(3)
    emetteur.emettre(3)  # dernier comptage, apres la fin du travail observe
    assert collecteur.jalons == [(3, 10)]
    assert emetteur.dernier == 3
    assert emetteur.dernier < emetteur.total


def test_sans_rappel_l_emetteur_est_inactif_et_n_appelle_rien():
    """AC 8 : le rappel est optionnel de bout en bout."""
    emetteur = progression.EmetteurProgression(None, 10)
    assert emetteur.actif is False
    assert emetteur.emettre(5) is False
    assert emetteur.dernier == 0


def test_un_total_nul_rend_l_emetteur_inactif():
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 0)
    assert emetteur.actif is False
    assert emetteur.emettre(1) is False
    assert collecteur.jalons == []


def test_un_rappel_qui_leve_est_absorbe_et_journalise_une_seule_fois(caplog):
    """AC 11 : un rappel fautif appele trois cents fois noierait le journal."""
    collecteur = Collecteur(leve=True)
    emetteur = _emetteur(collecteur, 300)
    with caplog.at_level(logging.WARNING, logger=progression.__name__):
        for faites in range(1, 301):
            emetteur.emettre(faites)
    assert len(collecteur.jalons) == 300  # le travail observe n'a rien perdu
    avertissements = [
        enregistrement
        for enregistrement in caplog.records
        if enregistrement.name == progression.__name__
    ]
    assert len(avertissements) == 1, (
        f"{len(avertissements)} avertissements journalises, un seul est permis"
    )


def test_un_rappel_qui_leve_ne_remonte_jamais(caplog):
    """AC 11 : l'exception de l'appelant ne traverse pas l'emetteur."""
    collecteur = Collecteur(leve=True)
    emetteur = _emetteur(collecteur, 5)
    with caplog.at_level(logging.WARNING, logger=progression.__name__):
        assert emetteur.emettre(1) is True
        assert emetteur.emettre(2) is True
    assert emetteur.dernier == 2


def test_un_rappel_non_appelable_rend_l_emetteur_inactif():
    emetteur = progression.EmetteurProgression("pas un rappel", 5)
    assert emetteur.actif is False
    assert emetteur.emettre(2) is False


def test_un_compte_illisible_ne_produit_pas_de_jalon_et_ne_leve_pas():
    """AC 11 : un comptage impossible donne MOINS de jalons, jamais une erreur."""
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 10)
    assert emetteur.emettre(None) is False
    assert emetteur.emettre("trois") is False
    assert collecteur.jalons == []
    assert emetteur.emettre(4) is True


@pytest.mark.parametrize(
    "compte", [float("inf"), float("-inf"), float("nan")]
)
def test_un_compte_non_fini_ne_fait_pas_lever_l_emetteur(compte):
    """AC 11 (EC-6) : « Ne leve jamais » vaut aussi pour l'infini.

    `int(nan)` leve `ValueError` et etait attrape ; `int(inf)` leve
    `OverflowError` et ne l'etait pas, si bien que la surface qui porte la
    propriete rendant la progression observationnelle levait.
    """
    collecteur = Collecteur()
    emetteur = _emetteur(collecteur, 10)
    assert emetteur.emettre(compte) is False
    assert collecteur.jalons == []
    assert emetteur.emettre(4) is True


@pytest.mark.parametrize(
    "total", [float("inf"), float("-inf"), float("nan"), "beaucoup", None]
)
def test_un_total_illisible_desactive_le_canal_sans_lever(total):
    """AC 11 (EC-6) : « un total illisible desactive le canal ; il ne fait
    jamais echouer la tache qui vient de le construire »."""
    collecteur = Collecteur()
    emetteur = progression.EmetteurProgression(collecteur, total)
    assert emetteur.actif is False
    assert emetteur.total == 0
    assert emetteur.emettre(1) is False
    assert collecteur.jalons == []


# ---------------------------------------------------------------------------
# AC 13 -- le vocabulaire est un interdit mesure
# ---------------------------------------------------------------------------


def test_le_vocabulaire_du_rythme_du_rush_est_absent_du_module_et_du_banc():
    """AC 13 (`EPIC7-ARB-80`) : grep de frontiere a zero.

    Les termes cherches sont **assembles par morceaux** : ecrits en clair ils
    apparaitraient dans ce fichier, qui fait lui-meme partie du perimetre grepe.
    """
    interdits = ["f" + "ps", "cad" + "ence", "vit" + "esse"]
    perimetre = [Path(progression.__file__), Path(__file__)]
    for fichier in perimetre:
        lignes = fichier.read_text(encoding="utf-8").lower().splitlines()
        for terme in interdits:
            occurrences = [ligne for ligne in lignes if terme in ligne]
            assert occurrences == [], (
                f"{fichier.name} porte {len(occurrences)} occurrence(s) d'un terme "
                f"interdit par EPIC7-ARB-80 : {occurrences[:3]}"
            )
