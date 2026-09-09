# -*- coding: utf-8 -*-
"""Story 11.4, lots `M`, `N1`, `N3` et `Q11` -- 2026-08-30.

Quatre gestes trouves par Egan **en utilisant le produit**, aucun visible pour
les bancs existants :

* **`M`** -- « cette info n'est VRAIMENT pas interessante. Elle est deja en
  couleur dans le panneau de previz lui-meme. J'aimerais retirer cette notion
  de temps reel tenu ou pas des ecrans de la tui, TOUS les ecrans. » La colonne
  `temps réel` de `E2-2b`, la mention `vue · temps réel …` de `E2-2c`, les trois
  verdicts et la teinture des lignes de rapport disparaissent. **Le coeur garde
  sa mesure** ;
* **`Q11`** -- « on juge un mouvement, pas des frames uniques ». La pause et le
  pas-a-pas quittent la legende de la fenetre ; la boucle `L` reste ;
* **`N1`** -- `o` (« revoir ») ne faisait rien sur `E2-2b` : la touche etait
  cablee sur `E2-2c` seul ;
* **`N3`** -- les trois issues de `E2-1d` faisaient **la meme chose** :
  `choix.valider()` etait lue pour la seule comparaison a `None`, puis jetee.

**Pourquoi un fichier a part.** `test_atelier_extraction_cadences.py` est un
banc partage, et deux lots simultanes qui y ecrivent est le point de contention
que `CLAUDE.md` decrit apres trois incidents d'attribution. Les corrections
d'un banc existant y restent ; tout ce qui est neuf vit ici.

**Regle des fabriques, point 2 bis compris** : trois cadences aux trois comptes
distincts avec l'echec en troisieme, trois issues de refus avec la cible au
MILIEU au moins une fois, et deux lectures aux cardinaux differents pour que
« remplacer le resultat » se distingue de « le garder ».
"""
from __future__ import annotations

import re
import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import cadence_previz, frame_selection, relink
from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.tui import atelier_extraction as amont
from mixed_media_utility.tui import cadences, jetons, rushes
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Les quatre promesses de la fenetre, dessinees par `E2-2b`. Ecrites ici une
#: seule fois : le test qui les cherche dans le rendu et la confrontation qui
#: les cherche dans le dessin lisent la MEME liste, donc elles ne peuvent pas
#: diverger. Quatre valeurs distinguables, dans l'ordre du dessin.
PROMESSES_DE_LA_FENETRE = ("L boucle", "N suivante", "R relire", "Q fermer")

REGIMES = [False, True]

FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124
VALEURS_LUES = (Fraction(25), Fraction(25, 2), Fraction(25, 3))


# ---------------------------------------------------------------------------
# Fabriques de previz
# ---------------------------------------------------------------------------

def rapport(valeur: Fraction, *, attendues: int, presentees: int | None = None,
            en_retard: int = 0, partiel: bool = False):
    """Un `PlaybackReport` du VRAI producteur, jamais un double.

    Le verdict de temps reel reste celui du coeur : c'est ce qui permet de
    mesurer qu'il **existe encore** alors qu'il ne s'affiche plus.
    """
    presentees = attendues if presentees is None else presentees
    pas = 1.0 / float(valeur)
    observations = [
        cadence_previz.FrameObservation(
            output_rank=rang + 1, source_index=rang, t_theo_s=rang * pas,
            t_real_s=rang * pas + (0.5 if rang < en_retard else 0.0))
        for rang in range(presentees)]
    return cadence_previz.build_playback_report(
        observations, fps_target=float(valeur), frames_attendues=attendues,
        duree_nominale_s=max(attendues - 1, 0) * pas,
        frames_omises=attendues - presentees, partiel=partiel)


def session(cadence_corroboree: bool = True) -> cadence_previz.PrevizSession:
    selections = tuple(
        frame_selection.select_source_frames(
            fps_source=FPS_SOURCE, fps_target=valeur,
            source_frame_count=FRAMES_SOURCE)
        for valeur in VALEURS_LUES)
    return cadence_previz.PrevizSession(
        video_path=Path("/rushes/rush_01.mov"),
        fps_source=FPS_SOURCE,
        source_frame_count=FRAMES_SOURCE,
        source_frame_count_is_exact=True,
        start_timecode=None,
        stream_duration_seconds=None,
        fps_targets=tuple(float(valeur) for valeur in VALEURS_LUES),
        selections=selections,
        schedules=tuple(cadence_previz.build_schedule(selection, FPS_SOURCE)
                        for selection in selections),
        cadence_corroboree=cadence_corroboree)


def regardees() -> tuple[cadences.Cadence, ...]:
    """Trois cadences, trois comptes DIFFERENTS (124, 62, 42)."""
    return tuple(
        cadences.Cadence(valeur=valeur,
                         libelle=cadences.libelle_remarquable(diviseur),
                         compte=frame_selection.select_source_frames(
                             fps_source=FPS_SOURCE, fps_target=valeur,
                             source_frame_count=FRAMES_SOURCE
                         ).expected_frame_count)
        for diviseur, valeur in zip((1, 2, 3), VALEURS_LUES))


def lecture_FROIDE() -> tuple:
    """La premiere passe : cache froid, donc **toutes en retard**.

    C'est l'etat qu'Egan a vu -- « toutes les previz etaient en cadence non
    tenues » --, et le coeur le declare bien non tenu ici.
    """
    return tuple(rapport(valeur, attendues=compte, en_retard=compte)
                 for valeur, compte in zip(VALEURS_LUES, (124, 62, 42)))


def lecture_CHAUDE() -> tuple:
    """La relecture : le cache est chaud, et les cardinaux DIFFERENT.

    Les frames presentees changent (124/62/42 contre 100/50/30) : sans cette
    difference, « remplacer le resultat » et « garder l'ancien » rendraient le
    meme ecran et aucun banc ne les separerait.
    """
    return tuple(rapport(valeur, attendues=compte, presentees=vues)
                 for valeur, compte, vues
                 in zip(VALEURS_LUES, (124, 62, 42), (100, 50, 30)))


def resultat(rapports, sess=None) -> cadence_previz.PrevizResult:
    return cadence_previz.PrevizResult(
        session=session() if sess is None else sess,
        reports=tuple(rapports), interrupted=False,
        decoded_frames=0, cache_hits=0, cache_misses=0)


class JoueurDeuxLectures:
    """Le joueur du banc : une lecture FROIDE, puis des lectures CHAUDES.

    Il compte ses appels et retient les sessions recues -- c'est ce qui mesure
    a la fois « `o` rejoue » et « `o` ne repaie pas la preparation ».
    """

    def __init__(self) -> None:
        self.sessions: list = []

    def __call__(self, sess):
        self.sessions.append(sess)
        rapports = lecture_FROIDE() if len(self.sessions) == 1 else lecture_CHAUDE()
        return resultat(rapports, sess=sess)


def refuser_l_affichage():
    raise cadence_previz.DisplayUnavailableError(
        "Aucun affichage graphique n'est disponible.")


def ecran_de_previz(**kwargs) -> amont.EcranPreviz:
    kwargs.setdefault("regardees", regardees())
    kwargs.setdefault("session", session())
    kwargs.setdefault("verifier_l_affichage", lambda: None)
    ecran = amont.EcranPreviz(**kwargs)
    ecran.demarrer()
    return ecran


def previz_LUE(**kwargs) -> amont.EcranPreviz:
    """`E2-2b` apres le premier `⏎` : la fenetre s'est ouverte et refermee."""
    ecran = ecran_de_previz(**kwargs)
    ecran.traiter("enter")
    return ecran


def rendu(ecran, ascii_seul: bool) -> str:
    """Tout ce que l'ecran MONTRE : corps, ligne d'etat, ligne de raccourcis."""
    lignes, _rang, _etats = ecran.composer(80, ascii_seul)
    return "\n".join(lignes + [ecran.ligne_d_etat(ascii_seul),
                               ecran.raccourcis])


def ecran_de_choix(**kwargs) -> amont.EcranChoixDesCadences:
    kwargs.setdefault("regardees", regardees())
    kwargs.setdefault("resultat", resultat(lecture_FROIDE()))
    kwargs.setdefault("nommer", lambda cadence: f"lot_{cadence.valeur}")
    return amont.EcranChoixDesCadences(**kwargs)


# ===========================================================================
# Lot `M` -- le temps reel tenu / non tenu quitte les ecrans
# ===========================================================================

#: **L'interdit, recopie verbatim face au test** (regle du pare-arbitrage).
#: Egan, 2026-08-30 : « cette info n'est VRAIMENT pas interessante. Elle est
#: deja en couleur dans le panneau de previz lui-meme. J'aimerais retirer cette
#: notion de temps reel tenu ou pas des ecrans de la tui, TOUS les ecrans. »
#:
#: Les motifs sont des expressions a **frontieres de mot** : `retenues` contient
#: `tenu`, et un `in` nu ferait rougir la colonne qu'on garde.
MOTIFS_DU_VERDICT = (
    r"\btenu\b", r"\bnon tenu\b", r"\bnon mesur", r"temps r[ée]el",
)


@pytest.mark.parametrize("ascii_seul", REGIMES)
def test_E2_2b_ne_porte_AUCUN_mot_du_verdict_de_temps_reel(ascii_seul):
    """Frontiere negative sur le rendu REEL, dans les deux regimes.

    La passe du milieu est **interrompue** et la troisieme est **non tenue** au
    sens du coeur : les trois etats du verdict retire sont donc representes, et
    aucun ne doit laisser de trace.
    """
    ecran = previz_LUE(jouer=lambda sess: resultat(
        (rapport(VALEURS_LUES[0], attendues=124),
         rapport(VALEURS_LUES[1], attendues=62, partiel=True),
         rapport(VALEURS_LUES[2], attendues=42, presentees=32)), sess=sess))
    texte = rendu(ecran, ascii_seul)
    for motif in MOTIFS_DU_VERDICT:
        assert not re.search(motif, texte, re.IGNORECASE), (motif, texte)
    # Volet symetrique : ce qui RESTE est bien la, sinon la mesure ci-dessus
    # serait verte sur un ecran vide. Les en-tetes sont replies avant d'etre
    # cherches -- `présentées` s'ecrit `presentees` en repli.
    for entete in (amont.ENTETE_DE_LA_CADENCE, amont.ENTETE_DES_RETENUES,
                   amont.ENTETE_DES_PRESENTEES):
        attendu = jetons.replier_ascii(entete) if ascii_seul else entete
        assert attendu in texte, (attendu, texte)


@pytest.mark.parametrize("ascii_seul", REGIMES)
def test_E2_2c_ne_porte_AUCUN_mot_du_verdict_de_temps_reel(ascii_seul):
    ecran = ecran_de_choix()
    ecran.liste.viser(VALEURS_LUES[1])
    ecran.traiter("space", " ")
    texte = rendu(ecran, ascii_seul)
    for motif in MOTIFS_DU_VERDICT:
        assert not re.search(motif, texte, re.IGNORECASE), (motif, texte)
    assert "frames" in texte, "les cardinaux, eux, restent"


def test_AUCUNE_ligne_de_rapport_de_E2_2b_n_est_TEINTEE():
    """La teinture etait le verdict dit une seconde fois, en couleur.

    Retirer le mot et garder la couleur aurait laisse l'ecran juger sans plus
    dire de quoi. Seules les lignes que d'autres regles teignent -- ici
    l'avertissement de cadence non corroboree -- gardent leur etat, et le volet
    symetrique le mesure.
    """
    ecran = previz_LUE(jouer=lambda sess: resultat(lecture_FROIDE(), sess=sess))
    _lignes, _rang, etats = ecran.composer(80, False)
    assert etats == {}, etats

    corroboree = previz_LUE(session=session(cadence_corroboree=False),
                            jouer=lambda sess: resultat(lecture_FROIDE(),
                                                        sess=sess))
    _l, _r, etats_avertis = corroboree.composer(80, False)
    assert list(etats_avertis.values()) == ["substitute"], etats_avertis


def test_le_COEUR_garde_sa_mesure_de_temps_reel_ENTIERE():
    """Volet symetrique du lot `M` : **ce qui part est l'affichage**.

    Trois preuves distinctes, parce qu'un seul champ pourrait survivre a un
    retrait qui aurait quand meme casse la mesure : le champ du rapport, les
    deux seuils, et la ligne que `mmu previz` ecrit dans son journal.
    """
    froide = lecture_FROIDE()[2]
    # Une passe jouee d'un trait, sans retard et sans frame omise : le coeur la
    # declare tenue. Le couple des deux mesure que le verdict BASCULE encore.
    tenue = rapport(VALEURS_LUES[0], attendues=124)
    assert froide.temps_reel_tenu is False
    assert tenue.temps_reel_tenu is True
    assert cadence_previz.LATE_FRAME_RATE_THRESHOLD > 0
    assert cadence_previz.FINAL_DRIFT_RATIO_THRESHOLD > 0
    assert "NON TENU" in "\n".join(
        cadence_previz.format_report_lines(froide))


def test_AUCUN_etat_derive_n_est_STOCKE_sur_les_lignes_de_E2_2c():
    """**La lecon de fraicheur du lot `M`, mesuree plutot que racontee.**

    Le defaut d'origine : la mention de chaque ligne etait un etat derive POSE
    une fois sur `cadences.Cadence.mention`, et `_appliquer_les_verdicts` ne la
    reposait que pour les cadences que la NOUVELLE lecture avait rejouees. Une
    cadence non rejouee gardait donc, indefiniment et sans que rien ne le dise,
    le verdict de la toute premiere passe -- celle du cache froid.

    Le banc reproduit exactement ce cas : la relecture ne rapporte QUE la
    premiere cadence, les deux autres n'etant pas rejouees. Rien ne doit
    subsister sur les lignes, ni avant ni apres.
    """
    partielle = (rapport(VALEURS_LUES[0], attendues=124, presentees=100),)
    ecran = ecran_de_choix(rejouer=lambda sess: resultat(partielle, sess=sess))
    assert [c.mention for c in ecran.liste.cadences] == ["", "", ""]
    ecran.traiter("o", "o")
    assert [c.mention for c in ecran.liste.cadences] == ["", "", ""], (
        "un etat derive stocke ment des qu'il cesse d'etre repose ; celui-ci "
        "n'existe plus, et c'est ce qui ferme la famille")


def test_la_SURFACE_PUBLIQUE_du_module_ne_porte_plus_le_verdict():
    """**Aucune constante orpheline laissee exportee.**

    C'est le mode de panne que cet epic a paye SIX fois -- « un composant
    livre, teste, cable nulle part » --, et un retrait est exactement le geste
    qui le fabrique : la constante cesse d'etre appelee, elle reste exportee,
    et plus rien ne dit qu'elle est morte. La garde du lot `J` tient
    `rushes.py` ; celle-ci tient la surface de `atelier_extraction` sur le
    vocabulaire retire.

    Les deux moities comptent : ce que le module **exporte** et ce qu'il
    **definit**. Une constante non exportee mais toujours ecrite serait du code
    mort tout autant.
    """
    import ast

    retires = ("VERDICT", "MENTION_VUE", "MENTION_TEMPS_REEL", "SEUIL_DE",
               "SEUIL_DES", "LIBELLE_DU_NON_MESURE", "ENTETE_DU_TEMPS_REEL",
               "verdict_d_une_passe", "marque_du_verdict",
               "mention_du_verdict", "_appliquer_les_verdicts")
    for nom in amont.__all__:
        assert not any(mort in nom for mort in retires), nom

    source = Path(amont.__file__).read_text(encoding="utf-8")
    definis = set()
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definis.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            definis |= {c.id for c in noeud.targets if isinstance(c, ast.Name)}
    for nom in sorted(definis):
        assert not any(mort in nom for mort in retires), nom
    # Volet symetrique : la surface n'a pas ete videe au passage.
    assert "EcranPreviz" in amont.__all__
    assert "rapport_de_la_cadence" in definis


# ===========================================================================
# `Q11` -- la pause et le pas-a-pas quittent la legende de la fenetre
# ===========================================================================

#: **L'arbitrage, recopie verbatim face au test.** Egan, 2026-08-30, `Q11`
#: option `b` : « **on juge un mouvement, pas des frames uniques** ». Il defait
#: sa propre decision du 2026-08-29 (« J'aimais bien le image par image en
#: pause quand on est sur la previz ») en connaissance de cause.
MOTIFS_DU_PAS_A_PAS = (r"\bpause\b", r"image par image", r"←", r"→", r"<", r">")


@pytest.mark.parametrize("ascii_seul", REGIMES)
def test_la_legende_de_la_fenetre_NE_PROMET_NI_pause_NI_pas_a_pas(ascii_seul):
    """Frontiere negative, sur les DEUX etats de l'ecran.

    L'ecran d'attente porte la meme legende que l'ecran lu : une promesse
    retiree d'un seul des deux temps se retrouverait dans l'autre.
    """
    for ecran in (ecran_de_previz(jouer=lambda s: resultat(lecture_FROIDE(),
                                                           sess=s)),
                  previz_LUE(jouer=lambda s: resultat(lecture_FROIDE(),
                                                      sess=s))):
        texte = rendu(ecran, ascii_seul)
        for motif in MOTIFS_DU_PAS_A_PAS:
            assert not re.search(motif, texte), (motif, texte)


@pytest.mark.parametrize("ascii_seul", REGIMES)
def test_la_BOUCLE_et_les_TROIS_touches_de_passe_RESTENT_annoncees(ascii_seul):
    """Volet symetrique : `Q11` ne retire que la pause et le pas-a-pas.

    `L` est livree par le lot `K2` et sert exactement le motif de l'arbitrage
    -- repasser le mouvement. `n`, `p`, `r` et `q` existent depuis le debut. Un
    retrait trop large les emporterait sans que la frontiere negative le voie.

    **Les quatre s'annoncent en MAJUSCULE depuis le lot `O`** (2026-08-30), et
    les touches liees restent les minuscules de `cadence_previz` : la seconde
    moitie de la mesure porte sur `KEY_NEXT` et ses voisines, qui valent bien
    `ord("n")` et jamais `ord("N")`.
    """
    from mixed_media_utility import cadence_previz

    ecran = previz_LUE(jouer=lambda s: resultat(lecture_FROIDE(), sess=s))
    texte = rendu(ecran, ascii_seul)
    for promesse in PROMESSES_DE_LA_FENETRE:
        assert promesse in texte, (promesse, texte)
    for touche, code in (("n", cadence_previz.KEY_NEXT),
                         ("p", cadence_previz.KEY_PREVIOUS),
                         ("r", cadence_previz.KEY_REPLAY),
                         ("l", cadence_previz.KEY_LOOP),
                         ("q", cadence_previz.KEY_QUIT)):
        assert code == ord(touche), (touche, code)
        assert code != ord(touche.upper()), (touche, code)
    assert len(amont.LIGNES_DE_LA_FENETRE) == 2, amont.LIGNES_DE_LA_FENETRE


# ===========================================================================
# Lot `N1` -- `o` revoit LA OU L'ON VIENT DE REGARDER
# ===========================================================================

def test_o_sur_E2_2b_ROUVRE_la_fenetre_sur_la_MEME_session():
    """Le defaut vecu : `o` ne faisait rien, et rien ne l'annoncait.

    Deux mesures en une : le joueur est rappele (donc la touche AGIT), et il
    l'est avec **la session du temps 1** -- `EPIC11-ARB-70`, « rouvrir, c'est
    rappeler `play_cadences` avec la session deja en main ».
    """
    joueur = JoueurDeuxLectures()
    depart = session()
    ecran = previz_LUE(session=depart, jouer=joueur)
    assert joueur.sessions == [depart]
    assert ecran.traiter("o", "o") is True
    assert joueur.sessions == [depart, depart], (
        "la seconde lecture repart de la session deja preparee")


def test_o_sur_E2_2b_REMPLACE_le_rapport_par_celui_de_la_NOUVELLE_lecture():
    """C'est ce qui rend le rapport de `E2-2b` RAFRAICHISSABLE.

    Sans `o`, `self.resultat` etait pose une fois par `_lire` et rien, jamais,
    ne pouvait le remplacer : le bilan n'acceptait que le premier etat. Les
    deux lectures ont des cardinaux differents, ligne par ligne -- une
    fabrique uniforme ne separerait pas « remplace » de « garde ».
    """
    ecran = previz_LUE(jouer=JoueurDeuxLectures())
    froid = [ligne for ligne in ecran.composer(80, False)[0] if "fps" in ligne]
    ecran.traiter("o", "o")
    chaud = [ligne for ligne in ecran.composer(80, False)[0] if "fps" in ligne]
    assert len(chaud) == 3
    assert chaud != froid
    assert "100" in chaud[0] and "50" in chaud[1] and "30" in chaud[2], chaud


def test_o_sur_E2_2b_NE_DESCEND_PAS_au_temps_2():
    """Revoir n'est pas choisir : `o` reste sur l'ecran de lecture."""
    choisis = []
    ecran = previz_LUE(jouer=JoueurDeuxLectures(), choisir=choisis.append)
    ecran.traiter("o", "o")
    assert choisis == []
    assert ecran.traiter("enter") is True
    assert choisis == [ecran.resultat], "`⏎`, lui, descend toujours"


def test_o_AVANT_la_premiere_lecture_n_ouvre_RIEN():
    """Il n'y a rien a **re**voir avant d'avoir vu.

    La ligne d'attente n'annonce que `⏎ ouvrir la fenêtre` : deux touches pour
    le meme geste apprendraient a l'operateur une touche de trop.
    """
    joueur = JoueurDeuxLectures()
    ecran = ecran_de_previz(jouer=joueur)
    assert ecran.traiter("o", "o") is False
    assert joueur.sessions == []


def test_o_sur_une_previz_REFUSEE_n_ouvre_RIEN():
    """AC 5.2 : sans affichage, aucun chemin n'atteint `play_cadences`.

    `N1` ajoute une touche ; ce banc mesure qu'elle ne rouvre pas le trou que
    l'AC 5.2 avait ferme -- c'est le meme volet que `⏎` porte deja.

    **Les DEUX moities de la garde sont mesurees**, et c'est une campagne
    d'injection qui l'a impose : sur le chemin nominal, `refus` implique
    `resultat is None`, si bien qu'un mutant qui retirerait le test du refus
    survivrait -- la seconde condition le couvrant par accident. La garde de
    l'AC 5.2 est trop chere pour tenir par accident : le second volet pose
    donc un resultat sur un ecran refuse et exige le meme silence.
    """
    joueur = JoueurDeuxLectures()
    ecran = ecran_de_previz(jouer=joueur,
                            verifier_l_affichage=refuser_l_affichage)
    assert ecran.refus
    assert ecran.traiter("o", "o") is False
    assert joueur.sessions == []

    ecran.resultat = resultat(lecture_FROIDE())
    assert ecran.traiter("o", "o") is False, (
        "un refus d'affichage ferme la touche, quel que soit ce que l'ecran "
        "porte deja")
    assert joueur.sessions == []


def test_o_SANS_lecteur_branche_le_DIT_au_lieu_de_se_taire():
    """Lecon `K1.1` : un rappel absent se DIT.

    Le chemin est celui d'`⏎`, et c'est voulu -- une seconde redaction du meme
    manque divergerait de la sienne a la premiere retouche.
    """
    ecran = ecran_de_previz(jouer=None)
    ecran.resultat = resultat(lecture_FROIDE())
    assert ecran.traiter("o", "o") is True
    assert amont.PHRASE_AUCUN_LECTEUR in ecran.ligne_d_etat(False)


@pytest.mark.parametrize("ascii_seul", REGIMES)
def test_la_ligne_de_raccourcis_de_E2_2b_ANNONCE_o_et_TIENT_la_grille(
        ascii_seul):
    """`EPIC11-ARB-41` : une promesse s'annonce ou se retire.

    Les trois lignes de l'ecran sont mesurees ensemble : celle d'apres la
    lecture annonce `O`, celle d'avant et celle du refus ne l'annoncent pas --
    il n'y a alors rien a revoir. Et les trois tiennent la zone de 76 colonnes
    **dans les deux regimes**, ce qui est exactement ce qui a impose de
    raccourcir la destination d'`Échap`.

    **La lettre annoncee est `O`, la touche cablee est `o`** (lot `O`,
    2026-08-30). La mesure de largeur est refaite ici parce que c'etait le
    risque nomme du lot : un repli ASCII allonge, et il fallait verifier -- pas
    croire -- qu'une majuscule ne change rien en chasse fixe.
    """
    def mesure(ligne: str) -> int:
        return jetons.colonnes(
            jetons.replier_ascii(ligne) if ascii_seul else ligne)

    assert re.search(r"\bO revoir\b", amont.RACCOURCIS_PREVIZ)
    assert not re.search(r"\bO revoir\b", amont.RACCOURCIS_PREVIZ_AVANT)
    assert not re.search(r"\bO revoir\b", amont.RACCOURCIS_PREVIZ_REFUSEE)
    # La touche liee reste la minuscule NUE : la frappe le prouve, pas le texte.
    ecran = ecran_de_previz(jouer=JoueurDeuxLectures())
    ecran.traiter("enter")
    assert ecran.traiter("o", "o") is True, "`o` nue agit"
    for ligne in (amont.RACCOURCIS_PREVIZ, amont.RACCOURCIS_PREVIZ_AVANT,
                  amont.RACCOURCIS_PREVIZ_REFUSEE):
        assert mesure(ligne) <= jetons.largeur_utile(80), (
            ligne, mesure(ligne))


def test_la_ligne_de_raccourcis_SUIT_le_temps_de_l_ecran():
    """La ligne posee n'est pas celle de la classe : elle suit l'etat."""
    ecran = ecran_de_previz(jouer=JoueurDeuxLectures())
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ_AVANT
    ecran.traiter("enter")
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ
    ecran.traiter("o", "o")
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ


# ===========================================================================
# Lot `N3` -- les trois issues de `E2-1d` menent a TROIS destinations
# ===========================================================================

def rush(rush_id, *, fps, largeur, hauteur, chemin):
    exacte = Fraction(fps).limit_denominator(1000)
    return {"rush_id": rush_id, "source_name": f"{rush_id}.mov",
            "fps_source": fps,
            "fps_source_exact": f"{exacte.numerator}/{exacte.denominator}",
            "resolution_source": {"width": largeur, "height": hauteur},
            "source_metadata_absent_fields": [], "source_path": chemin,
            "source_start_timecode": "00:00:00:00"}


def document_absent_au_MILIEU() -> dict:
    """Trois rushes, l'absent au MILIEU -- point 2 bis de la regle.

    Ni premier ni dernier : un `find` qui rendrait le premier element et une
    boucle qui s'arreterait au dernier se demasquent tous deux.
    """
    import json  # noqa: F401 -- lisibilite locale, voir `projet`
    return {"schema_version": "2.1", "project_id": "projet_demo",
            "rushes": [
                rush("rush_01", fps=25.0, largeur=1920, hauteur=1080,
                     chemin="/rushes/rush_01.mov"),
                rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
                     chemin="/perdu/rush_hiver.mov"),
                rush("zz_rush_03", fps=50.0, largeur=1280, hauteur=720,
                     chemin="/rushes/zz_rush_03.mov")],
            "lots": [
                {"lot_id": "rush_01_25", "rush_id": "rush_01",
                 "state": "extraction", "source_frame_count": 6300,
                 "source_frame_count_is_exact": True},
                {"lot_id": "rush_hiver_24", "rush_id": "rush_hiver",
                 "state": "extraction", "source_frame_count": 3012,
                 "source_frame_count_is_exact": True},
                {"lot_id": "zz_rush_03_50", "rush_id": "zz_rush_03",
                 "state": "extraction", "source_frame_count": 37900,
                 "source_frame_count_is_exact": True}],
            "artifacts": {}, "color": {}, "video": {}, "reconstruction": {}}


def projet(tmp_path: Path) -> Path:
    import json
    dossier = tmp_path / "projet_demo"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(document_absent_au_MILIEU(), indent=2, ensure_ascii=False,
                   sort_keys=True) + "\n", encoding="utf-8")
    return dossier


def probe_qui_ne_correspond_a_rien(_chemin):
    return relink.ProbeCandidat(nom_de_base="rien_a_voir.mov",
                                cardinal_frames=1, cardinal_est_exact=True,
                                timecode_depart="01:00:00:00")


def coque(ecran) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


def apres_le_refus(banc, tmp_path, issue_visee: str, *, deplacer=False,
                   dossier: Path | None = None):
    """Le parcours REEL : `r`, une cible refusee, puis l'issue choisie.

    Rien n'est construit a la main : c'est `EcranRushes._relinker` qui monte
    l'ecran de refus et qui injecte la reprise. Un banc qui monterait
    `EcranRefusRelink` lui-meme mesurerait son propre cablage -- exactement le
    piege que `K3.1a` a paye.

    `dossier` est **donne** par le banc qui mesure les ecritures : poser la
    fixture ici reecrirait le manifeste apres son releve d'inode, et la mesure
    accuserait le banc lui-meme.
    """
    dossier = projet(tmp_path) if dossier is None else dossier
    cible = tmp_path / "autre.mov"
    cible.write_bytes(b"")
    ecran = amont.EcranRushes(dossier, existe=lambda c: "perdu" not in c,
                              probe=probe_qui_ne_correspond_a_rien)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("r", "r")
        ecran._relinker(cible)
        await pilote.pause()
        refus = pilote.app.screen
        assert isinstance(refus, amont.EcranRefusRelink), type(refus)
        if deplacer:
            # **Le curseur bouge PENDANT le refus.** C'est ce qui distingue
            # « le rush vise survit » de « on relit le curseur » : sans cette
            # frappe, les deux implementations rendraient le meme resultat.
            ecran.liste.viser("rush_01")
        while refus.choix.retenir() is None or \
                refus.choix.issues[refus.choix.curseur].cle != issue_visee:
            refus.traiter("down")
        refus.traiter("enter")
        await pilote.pause()
        return type(pilote.app.screen).__name__

    final = banc(coque(ecran), scenario)
    return ecran, final


def test_les_TROIS_issues_de_E2_1d_menent_a_TROIS_etats_DIFFERENTS(
        tmp_path, banc):
    """**Le defaut d'origine, mesure d'un seul coup.**

    `traiter` lisait `choix.valider()` pour la seule comparaison a `None`, puis
    la **jetait** : les trois issues remontaient d'un palier et rien d'autre.
    Or remonter d'un palier ne ramene pas a la liste -- `EcranRushes` reste
    dans la ZONE EXPLORATEUR, dans le mode du geste qui vient d'echouer. Egan a
    donc choisi « Le désigner à la main » apres un `r` refuse et retrouve la vue
    par DOSSIERS de la recherche.

    Les trois etats sont compares entre eux, pas a une valeur attendue : c'est
    ce qui fait mourir aussi bien « l'issue est jetee » que « les deux modes
    sont intervertis ».
    """
    etats = {}
    for cle in (rushes.MODE_DESIGNER, rushes.MODE_RETROUVER,
                rushes.ISSUE_REVENIR):
        ecran, _final = apres_le_refus(banc, tmp_path / cle, cle)
        etats[cle] = (ecran.zone, ecran.mode,
                      ecran.explorateur.montrer_fichiers)
    assert len(set(etats.values())) == 3, etats


def test_LE_DESIGNER_A_LA_MAIN_ouvre_l_explorateur_en_FICHIERS(tmp_path, banc):
    """Le libelle nomme une destination : elle doit exister.

    `MONTRER_FICHIERS[MODE_DESIGNER]` vaut `True` -- on designe un fichier, on
    ne cherche pas un dossier. Le mode est lu de la table du modele et non
    recopie : deux ecritures de la meme table divergeraient.
    """
    ecran, _final = apres_le_refus(banc, tmp_path, rushes.MODE_DESIGNER)
    assert ecran.zone == amont.ZONE_EXPLORATEUR
    assert ecran.mode == rushes.MODE_DESIGNER
    assert ecran.explorateur.montrer_fichiers is \
        rushes.MONTRER_FICHIERS[rushes.MODE_DESIGNER]


def test_CHERCHER_AILLEURS_rouvre_l_explorateur_en_DOSSIERS(tmp_path, banc):
    ecran, _final = apres_le_refus(banc, tmp_path, rushes.MODE_RETROUVER)
    assert ecran.zone == amont.ZONE_EXPLORATEUR
    assert ecran.mode == rushes.MODE_RETROUVER
    assert ecran.explorateur.montrer_fichiers is \
        rushes.MONTRER_FICHIERS[rushes.MODE_RETROUVER]


def test_REVENIR_ramene_a_la_LISTE_des_rushes(tmp_path, banc):
    """La troisieme issue, celle qui ne relance rien : elle sort vraiment."""
    ecran, _final = apres_le_refus(banc, tmp_path, rushes.ISSUE_REVENIR)
    assert ecran.zone == amont.ZONE_LISTE
    assert ecran.mode is None and ecran.but is None


def test_le_RUSH_VISE_survit_au_refus_meme_si_le_curseur_a_BOUGE(
        tmp_path, banc):
    """Egan ne doit pas avoir a re-selectionner son rush apres un echec.

    Le curseur est deplace **pendant** le refus, sur un rush qui n'est pas
    absent. Sans le `viser` explicite de la reprise,
    `_ouvrir_l_explorateur` redemanderait la cible a `rush_a_relinker()`,
    c'est-a-dire au curseur : il n'y aurait plus de rush a relinker du tout, et
    l'explorateur s'ouvrirait sans cible. C'est le mode de panne de `_find_lot`
    en 5.7, une fois de plus.
    """
    ecran, _final = apres_le_refus(banc, tmp_path, rushes.MODE_DESIGNER,
                                   deplacer=True)
    assert ecran._vise == "rush_hiver", ecran._vise
    assert ecran.liste.courant.rush_id == "rush_hiver"


def test_AUCUNE_issue_de_E2_1d_n_ECRIT_sur_le_disque(tmp_path, banc):
    """`EPIC11-ARB-45` : « trois issues, aucune n'ecrit », et c'est MESURE.

    La mesure ne se fait ni sur un condensat ni sur la taille : une reecriture
    a l'identique rendrait exactement les memes octets sur une fixture
    deterministe (`EPIC11-ARB-83`). On mesure donc l'**inode**, le
    `st_mtime_ns`, et un **temoin** depose dans le dossier -- un fichier qui
    disparaitrait, ou un dossier reecrit, se verraient tous les deux.
    """
    for cle in (rushes.MODE_DESIGNER, rushes.MODE_RETROUVER,
                rushes.ISSUE_REVENIR):
        bac = tmp_path / cle
        dossier = projet(bac)
        manifeste = dossier / extraction_manifest.MANIFEST_FILENAME
        temoin = dossier / "temoin.txt"
        temoin.write_text("intact\n", encoding="utf-8")
        avant = manifeste.stat()
        avant_temoin = temoin.stat()
        apres_le_refus(banc, bac, cle, dossier=dossier)
        apres = manifeste.stat()
        assert (apres.st_ino, apres.st_mtime_ns) == (avant.st_ino,
                                                     avant.st_mtime_ns), cle
        assert temoin.read_text(encoding="utf-8") == "intact\n"
        assert temoin.stat().st_ino == avant_temoin.st_ino


def test_le_PRODUIT_injecte_bien_la_reprise_du_refus(tmp_path, banc):
    """Le volet de cablage, celui qu'aucun banc d'ecran ne peut voir.

    `_relinker` est le SEUL chemin par lequel le produit monte `E2-1d`. Si la
    reprise cessait d'y etre injectee, les trois issues redeviendraient
    identiques -- et tous les bancs qui montent l'ecran a la main resteraient
    verts. C'est ce que la garde de `test_rappels_cables.py` mesure
    structurellement ; celui-ci le mesure sur le parcours reel.
    """
    dossier = projet(tmp_path)
    cible = tmp_path / "autre.mov"
    cible.write_bytes(b"")
    ecran = amont.EcranRushes(dossier, existe=lambda c: "perdu" not in c,
                              probe=probe_qui_ne_correspond_a_rien)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("r", "r")
        ecran._relinker(cible)
        await pilote.pause()
        return pilote.app.screen._reprendre

    reprise = banc(coque(ecran), scenario)
    assert reprise is not None, (
        "sans reprise injectee, les trois issues de E2-1d font la meme chose")


# ===========================================================================
# La maquette `E2-2b`, LUE a sa source plutot que recopiee
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-2b` et n'ouvrait pas
# le dessin : les quatre promesses de la fenetre de previsualisation y etaient
# recopiees a la main, dans une boucle, au milieu d'un test. Un texte recopie
# coincide le jour ou il est ecrit et derive ensuite sans qu'aucune etape
# n'echoue -- et ces quatre-la sont exactement le genre de valeur qu'un
# arbitrage de raccourci deplace (`O`, 2026-08-30, les a passees en
# MAJUSCULE).

#: La maquette, a sa source.
MAQUETTE_DE_LA_PREVIZ = (
    Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
    / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
    / "E2-2b-extraction-previz.txt")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_previz() -> str:
    """Le corps de `E2-2b`, cadre retire, notes coupees, espaces replies."""
    brut = MAQUETTE_DE_LA_PREVIZ.read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


@pytest.mark.parametrize("promesse", PROMESSES_DE_LA_FENETRE)
def test_chaque_promesse_de_la_fenetre_est_VERBATIM_de_E2_2b(promesse):
    """La promesse est DANS le dessin, lu sur disque a ce tour-ci.

    Les quatre sont mesurees separement plutot qu'en bloc : un `in` sur la
    liste entiere rougirait sans dire LAQUELLE a bouge, et c'est la seule
    information utile le jour ou l'une bouge.
    """
    assert promesse in dessin_de_la_previz(), promesse


def test_les_quatre_promesses_sont_dans_l_ORDRE_du_dessin():
    """L'ordre est celui de la ligne dessinee, pas un ordre de commodite.

    `E2-2b` ecrit `L boucle · N suivante · P précédente · R relire` puis
    `Q fermer` a la ligne suivante. Une liste re-triee passerait le test
    ci-dessus sans rien dire de la ligne que l'operateur lit.
    """
    dessin = dessin_de_la_previz()
    positions = [dessin.index(p) for p in PROMESSES_DE_LA_FENETRE]
    assert positions == sorted(positions), positions


def test_la_cinquieme_promesse_du_dessin_est_ABSENTE_de_la_liste():
    """Frontiere negative, et elle nomme un ecart REEL plutot qu'invente.

    Le dessin porte CINQ promesses ; le banc n'en cherche que quatre --
    `P précédente` n'y est pas, alors que `KEY_PREVIOUS` est bien mesuree
    juste a cote. L'ecart est NOMME ici (`EPIC11-ARB-144`) plutot que
    corrige en douce : ajouter la cinquieme changerait ce que le test du
    rendu exige, ce qui n'appartient pas a un lot d'audit.
    """
    dessin = dessin_de_la_previz()
    assert "P précédente" in dessin
    assert "P précédente" not in PROMESSES_DE_LA_FENETRE
    assert len(PROMESSES_DE_LA_FENETRE) == 4
    # Et le pli n'absorbe pas un ecart d'un mot.
    assert "L boucler" not in dessin
    assert "Q fermer et revenir au terminal" in dessin
