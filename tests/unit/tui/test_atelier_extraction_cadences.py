# -*- coding: utf-8 -*-
"""Story 11.4, lot E3-E5 -- les TROIS ecrans de cadences de l'atelier Extraction.

`E2-2` (quelles cadences regarder), `E2-2b` (la lecture comparee) et `E2-2c`
(lesquelles extraire). Le modele pur est mesure a cote (`test_cadences.py`) ;
ce banc-ci mesure ce que le modele ne peut pas dire : le chemin clavier, le
rendu confronte aux maquettes, et surtout les **quatre refus de conception**
que les arbitrages du 2026-08-29 posent -- pas de pourcentage, pas de previz
sans affichage, pas de probe repaye, pas de consentement herite.

**La regle des fabriques s'applique partout ici** : quatre cadences aux quatre
comptes DIFFERENTS, trois passes de previz dont l'echec est en TROISIEME
position, deux lots aux noms et aux comptes distincts, et la cadence jouee deux
fois n'est jamais la premiere.
"""
import re
import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import cadence_previz, frame_selection
from mixed_media_utility.tui import atelier_extraction, cadences, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

RACINE = Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: La source de `E2-2` : 124 frames a 25 im/s. C'est elle qui rend 124, 62, 42
#: et 31 -- les quatre comptes de la maquette -- par le VRAI coeur.
FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124

#: Les trois cadences que la previz de `E2-2b` a lues, dans l'ordre.
VALEURS_LUES = (Fraction(25), Fraction(25, 2), Fraction(25, 3))


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def lignes_de_maquette(nom: str, premiere: int, derniere: int) -> list[str]:
    """Les lignes utiles d'une maquette, cadre et marges retires.

    Meme decoupe que `test_cadences.py` : `│ ` a gauche, ` │` a droite, et les
    blancs de queue tombent des deux cotes de la comparaison.
    """
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").splitlines()
    return [ligne[2:-2].rstrip() for ligne in lignes[premiere:derniere]]


def source(**kwargs) -> atelier_extraction.SourceSondee:
    """La source deja SONDEE : le probe est paye avant, jamais ici."""
    defauts = dict(video_path=Path("/rushes/rush_01.mov"),
                   fps_source=FPS_SOURCE,
                   source_frame_count=FRAMES_SOURCE)
    defauts.update(kwargs)
    return atelier_extraction.SourceSondee(**defauts)


def ecran_de_cadences(**kwargs) -> atelier_extraction.EcranCadences:
    """`E2-2` monte sur la vraie source, donc sur les vrais comptes."""
    kwargs.setdefault("source", source())
    kwargs.setdefault("verifier_l_affichage", lambda: None)
    return atelier_extraction.EcranCadences(**kwargs)


def compte_du_coeur(valeur: Fraction, **kwargs) -> int:
    """Le compte que `select_source_frames` rend, calcule A PART du module.

    Recopier 124 dans le test mesurerait la maquette ; l'appeler ici mesure que
    l'ecran passe bien la Fraction EXACTE et le cardinal deja sonde.
    """
    return frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=valeur,
        source_frame_count=FRAMES_SOURCE, **kwargs).expected_frame_count


def rapport(valeur: Fraction, *, attendues: int, presentees: int | None = None,
            omises: int = 0, en_retard: int = 0, partiel: bool = False):
    """Un `PlaybackReport` du VRAI producteur, jamais un double.

    Les instants sont fabriques a la main -- c'est ce que
    `build_playback_report` demande, elle est pure -- mais le verdict, lui,
    reste celui du coeur : un double aurait son propre seuil, donc sa propre
    frontiere, et la mesure ne dirait plus rien.

    Les frames en retard sont placees **en tete** : la derive finale se lit sur
    la DERNIERE frame, et la mettre en retard melangerait deux criteres.
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
        duree_nominale_s=max(attendues - 1, 0) * pas, frames_omises=omises,
        partiel=partiel)


def regardees() -> tuple[cadences.Cadence, ...]:
    """Les TROIS cadences cochees au temps 1, aux comptes du coeur.

    Trois comptes differents (124, 62, 42) : un appariement ligne/rapport
    inverse se verrait, ce qu'un remplissage uniforme cacherait.
    """
    return tuple(
        cadences.Cadence(valeur=valeur,
                         libelle=cadences.libelle_remarquable(diviseur),
                         compte=compte_du_coeur(valeur))
        for diviseur, valeur in zip((1, 2, 3), VALEURS_LUES))


def session(cadence_corroboree: bool = True) -> cadence_previz.PrevizSession:
    """Une `PrevizSession` reelle : selections et echeanciers du coeur."""
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


def rapports_de_la_maquette() -> tuple:
    """Les TROIS passes de `E2-2b`, la passe INCOMPLETE en TROISIEME position.

    124/124, 62/62 interrompue, 42/32. Placer l'incomplete en tete laisserait
    passer un rendu qui ne lirait que le premier rapport.

    Les trois couples de cardinaux sont **tous differents** : une permutation
    ligne / rapport se verrait, ce qu'un remplissage uniforme cacherait.
    """
    return (rapport(VALEURS_LUES[0], attendues=124),
            rapport(VALEURS_LUES[1], attendues=62, partiel=True),
            rapport(VALEURS_LUES[2], attendues=42, presentees=32, omises=10))


def rapports_du_choix() -> tuple:
    """Les TROIS passes de `E2-2c` -- deux tenues, la non-tenue en TROISIEME.

    Les deux maquettes ne montrent pas la meme lecture : `E2-2b` porte une
    passe interrompue que `E2-2c` n'a pas. Chaque banc consomme donc la sienne,
    plutot que d'aligner l'une sur l'autre.
    """
    return (rapport(VALEURS_LUES[0], attendues=124),
            rapport(VALEURS_LUES[1], attendues=62),
            rapport(VALEURS_LUES[2], attendues=42, presentees=32, omises=10))


def resultat(rapports=None, sess=None) -> cadence_previz.PrevizResult:
    return cadence_previz.PrevizResult(
        session=session() if sess is None else sess,
        reports=tuple(rapports_de_la_maquette() if rapports is None
                      else rapports),
        interrupted=False, decoded_frames=0, cache_hits=0, cache_misses=0)


def nommer_le_lot(cadence: cadences.Cadence) -> str:
    """Les DEUX noms de `E2-2c`, distincts et jamais uniformes.

    Le nom vient de l'appelant : la convention `_25s3` appartient au lot des
    noms, pas a cet ecran-ci.
    """
    court = {Fraction(25): "25fps", Fraction(25, 2): "12p5",
             Fraction(25, 3): "25s3"}[cadence.valeur]
    return f"projet_demo_rush_01_{court}"


def ecran_de_choix(**kwargs) -> atelier_extraction.EcranChoixDesCadences:
    kwargs.setdefault("regardees", regardees())
    kwargs.setdefault("resultat", resultat(rapports_du_choix()))
    kwargs.setdefault("nommer", nommer_le_lot)
    return atelier_extraction.EcranChoixDesCadences(**kwargs)


def ecran_de_previz(**kwargs) -> atelier_extraction.EcranPreviz:
    kwargs.setdefault("regardees", regardees())
    kwargs.setdefault("session", session())
    # Le banc tourne sans affichage : le cas NOMINAL est donc celui qu'il faut
    # injecter, le refus etant l'etat naturel d'un conteneur de test.
    kwargs.setdefault("verifier_l_affichage", lambda: None)
    return atelier_extraction.EcranPreviz(**kwargs)


def previz_lue(**kwargs) -> atelier_extraction.EcranPreviz:
    """`E2-2b` **apres** la lecture : monter, puis `⏎` une premiere fois.

    Depuis `K1.2`, la fenetre ne s'ouvre plus au montage -- `demarrer()` ne
    fait plus que la garde d'affichage, et c'est `⏎` qui ouvre. Les bancs qui
    mesurent le RAPPORT passent donc par ici : rester sur `demarrer()` seul
    mesurerait l'ecran d'ATTENTE en croyant mesurer le rapport.
    """
    ecran = ecran_de_previz(**kwargs)
    ecran.demarrer()
    ecran.traiter("enter")
    return ecran


def refus_d_affichage() -> cadence_previz.DisplayUnavailableError:
    """Le VRAI refus du coeur, leve par la vraie garde.

    Fabriquer l'exception a la main lui donnerait le `motif` du test ; ici
    c'est celui du coeur, avec son conseil qui nomme l'option interdite en TUI.
    """
    try:
        cadence_previz.ensure_display_available(environ={}, platform="linux")
    except cadence_previz.DisplayUnavailableError as refus:
        return refus
    raise AssertionError("la garde d'affichage n'a rien refuse")


def refuser_l_affichage() -> None:
    raise refus_d_affichage()


class JoueurCompte:
    """Un double de `play_cadences` qui COMPTE ses appels."""

    def __init__(self, rendu=None) -> None:
        self.appels: list = []
        self._rendu = rendu

    def __call__(self, session_jouee):
        self.appels.append(session_jouee)
        return (resultat(sess=session_jouee) if self._rendu is None
                else self._rendu)


def coque(ecran):
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


def peint(ecran, identifiant, banc, ascii_seul=False):
    """Le contenu PEINT de l'ecran, monte sur le banc."""
    application = coque(ecran)
    application.ascii_seul = ascii_seul

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one(identifiant).content

    return banc(application, scenario)


# ---------------------------------------------------------------------------
# `E2-2` -- la liste cochable et les bornes (E3)
# ---------------------------------------------------------------------------

def test_les_lignes_de_E2_2_sont_CELLES_DE_LA_MAQUETTE():
    """La maquette fait foi sur le texte ET sur les colonnes.

    **La ligne d'abregement est sautee, et c'est delibere.** Elle appartient au
    modele pur, dont le banc (`test_cadences.py`) ne la confronte pas non plus a
    la maquette : le modele cale sa position de fenetre a la marge droite (74),
    la maquette a 69. L'ecart est reel et il est verse en dette ; l'aligner
    ici en fabriquerait une seconde ecriture, dans l'ecran plutot que dans le
    modele.
    """
    ecran = ecran_de_cadences()
    for rang in (0, 1, 2):
        ecran.liste.cadences[rang].cochee = True
    for ajout in ("20", "15", "10", "5"):
        assert ecran.liste.ajouter(ajout) is None, ajout
    ecran.liste.curseur = 0
    ecran.liste.premier_visible = 0
    lignes, _rang, _etats = ecran.composer(80, False)
    rendues = [ligne.rstrip() for ligne in lignes]
    # Lignes 3 a 9 : le blanc de tete, le titre, puis les QUATRE cadences.
    assert rendues[:7] == lignes_de_maquette(
        "E2-2-extraction-cadences.txt", 3, 10)
    # Lignes 11 et 12 : le blanc, puis le rappel des cochees.
    assert rendues[8:10] == lignes_de_maquette(
        "E2-2-extraction-cadences.txt", 11, 13)


def test_le_BLOC_DES_BORNES_est_celui_de_la_maquette():
    """Le filet, les deux libelles et la mention facultative, au caractere."""
    ecran = ecran_de_cadences(borne_d_entree="00:00:04:12")
    lignes, _rang, _etats = ecran.composer(80, False)
    attendues = lignes_de_maquette("E2-2-extraction-cadences.txt", 14, 18)
    assert [ligne.rstrip() for ligne in lignes[-4:]] == attendues


def test_la_ligne_d_etat_de_E2_2_est_celle_de_la_maquette():
    ecran = ecran_de_cadences()
    for rang in (0, 1, 2):
        ecran.liste.cadences[rang].cochee = True
    for ajout in ("20", "15", "10", "5"):
        ecran.liste.ajouter(ajout)
    assert ecran.ligne_d_etat(False) == lignes_de_maquette(
        "E2-2-extraction-cadences.txt", 21, 22)[0]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E2_2_tient_la_grille_dans_LES_DEUX_regimes(ascii_seul):
    ecran = ecran_de_cadences(borne_d_entree="00:00:04:12")
    lignes, _rang, _etats = ecran.composer(80, ascii_seul)
    for ligne in lignes + [ecran.ligne_d_etat(ascii_seul)]:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        if ascii_seul:
            assert ligne.isascii(), ligne


def test_le_COMPTE_vient_de_select_source_frames_avec_la_FRACTION_EXACTE():
    """`EPIC11-ARB-79`. Deux mesures dans le meme test, et elles se tiennent.

    Le compte est celui du coeur, cadence par cadence -- quatre comptes
    DIFFERENTS, donc aucune permutation ne passe --, et la Fraction exacte est
    ce qui les rend : `prepare_previz` refuse une `Fraction`, et la convertir
    en flottant reintroduirait l'approximation.
    """
    ecran = ecran_de_cadences()
    attendus = [compte_du_coeur(FPS_SOURCE / d) for d in (1, 2, 3, 4)]
    assert attendus == [124, 62, 42, 31]
    assert [c.compte for c in ecran.liste.cadences] == attendus


def test_le_comptage_ne_passe_JAMAIS_par_prepare_previz(monkeypatch):
    """`EPIC11-ARB-79`, volet negatif ET son volet symetrique.

    Le double compte ses appels : zero. Et la seconde moitie prouve POURQUOI
    le chemin n'existe pas -- le filtre de `prepare_previz` refuse la Fraction
    exacte que le modele garde.
    """
    appels = []
    monkeypatch.setattr(cadence_previz, "prepare_previz",
                        lambda **kwargs: appels.append(kwargs))
    ecran_de_cadences()
    assert appels == []
    with pytest.raises(Exception):
        cadence_previz._validated_targets([Fraction(25, 3)])


def test_Espace_coche_la_cadence_SOUS_LE_CURSEUR_et_pas_la_PREMIERE():
    """Le mutant de la famille 5.7 : la cible est la TROISIEME."""
    ecran = ecran_de_cadences()
    ecran.liste.viser(FPS_SOURCE / 3)
    assert ecran.traiter("space", " ") is True
    assert [c.cochee for c in ecran.liste.cadences] == [False, False, True,
                                                        False]


def test_Espace_sur_une_cadence_REFUSEE_dit_le_MOTIF_DU_COEUR():
    """AC 3.5 : la cadence refusee n'est pas cochable, et le message est celui
    du coeur -- ici l'upsampling, provoque par une cadence libre au-dessus de
    la source."""
    ecran = ecran_de_cadences()
    assert ecran.liste.ajouter("50") is None
    ecran.traiter("space", " ")
    assert ecran.liste.cadences[-1].cochee is False
    assert ecran.liste.cadences[-1].motif in ecran.ligne_d_etat(False)


def test_a_ouvre_la_saisie_et_TOUTE_LETTRE_y_devient_du_TEXTE():
    """`EPIC11-ARB-68` : « Aucune lettre n'est un raccourci dans un champ de
    saisie. » `x` et `a` sont des raccourcis hors saisie ; dedans, du texte."""
    ecran = ecran_de_cadences(extraire=lambda validation: pytest.fail(
        "x ne doit rien extraire pendant une saisie"))
    assert ecran.traiter("a", "a") is True
    assert ecran.saisie == ""
    for caractere in "12x,a5":
        ecran.traiter(caractere, caractere)
    assert ecran.saisie == "12x,a5"


def test_la_saisie_VALIDEE_ajoute_la_cadence_libre():
    ecran = ecran_de_cadences()
    ecran.traiter("a", "a")
    for caractere in "2,5":
        ecran.traiter(caractere, caractere)
    assert ecran.traiter("enter") is True
    assert ecran.saisie is None
    assert ecran.liste.cadences[-1].valeur == Fraction(5, 2)


def test_une_saisie_FRACTIONNAIRE_ENTRE_par_le_champ_de_saisie():
    """Story 11.4, lot P (`EPIC11-ARB-62`) : le champ de saisie n'a rien a
    apprendre pour porter la grammaire des divisions.

    `EPIC11-ARB-68`, verbatim -- « Aucune lettre n'est un raccourci dans un
    champ de saisie » -- est ce qui rend `c`, `s` et les lettres de `cadence`
    tapables sans qu'aucun raccourci ne les intercepte. Le test le mesure sur
    l'alias LE PLUS LONG, celui qui traverse le plus de lettres.
    """
    ecran = ecran_de_cadences()
    ecran.traiter("a", "a")
    for caractere in "cadences6":
        ecran.traiter(caractere, caractere)
    assert ecran.traiter("enter") is True
    assert ecran.saisie is None
    assert len(ecran.liste.cadences) == 5
    ajoutee = ecran.liste.cadences[-1]
    assert ajoutee.valeur == Fraction(25, 6)
    # L'ECRITURE `cadences6` reste acceptee en entree ; l'AFFICHAGE, lui, est
    # celui des remarquables depuis `EPIC11-ARB-94` -- un seul vocabulaire par
    # ecran, la ou `cadence/6` cohabitait avec `source / 2` a trois lignes
    # d'ecart. Ecrit en dur : un mutant du patron ne doit pas casser les deux
    # cotes d'une egalite d'un coup.
    assert ajoutee.libelle == "source / 6"
    assert ajoutee.nom_court() == "25s6"

    # **Le volet d'unification** : la cadence saisie et une remarquable qui
    # designe la meme division portent le MEME libelle sur le MEME ecran.
    remarquables = [c.libelle for c in ecran.liste.cadences[:4]]
    assert "source / 2" in remarquables
    assert ajoutee.libelle.split(" / ")[0] == remarquables[1].split(" / ")[0]


def test_une_saisie_HORS_GRAMMAIRE_est_refusee_NOMMEMENT_et_n_entre_pas():
    """Le volet symetrique du precedent : le refus reste nomme et le champ
    reste ouvert (`25:3` n'est pas une ecriture de la grammaire)."""
    ecran = ecran_de_cadences()
    ecran.traiter("a", "a")
    for caractere in "25:3":
        ecran.traiter(caractere, caractere)
    ecran.traiter("enter")
    assert len(ecran.liste.cadences) == 4
    assert cadences.MOTIF_PAS_UN_NOMBRE in ecran.ligne_d_etat(False)


def test_Echap_ABANDONNE_la_saisie_sans_rien_ajouter():
    ecran = ecran_de_cadences()
    ecran.traiter("a", "a")
    ecran.traiter("9", "9")
    assert ecran.traiter("escape") is True
    assert ecran.saisie is None
    assert len(ecran.liste.cadences) == 4


def test_Entree_PREVISUALISE_les_cochees_et_x_EXTRAIT_sans_regarder():
    """AC 5.1. Les deux cochees ne sont pas les premieres de la liste."""
    vues, extraites = [], []
    ecran = ecran_de_cadences(previsualiser=vues.append,
                              extraire=extraites.append)
    ecran.liste.viser(FPS_SOURCE / 3)
    ecran.traiter("space", " ")
    ecran.liste.viser(FPS_SOURCE / 4)
    ecran.traiter("space", " ")
    assert ecran.traiter("enter") is True
    assert [c.valeur for c in vues[0].cochees] == [FPS_SOURCE / 3,
                                                   FPS_SOURCE / 4]
    assert extraites == []
    assert ecran.traiter("x", "x") is True
    assert [c.valeur for c in extraites[0].cochees] == [FPS_SOURCE / 3,
                                                        FPS_SOURCE / 4]


def test_une_validation_a_ZERO_cochee_ne_passe_pas_en_SILENCE():
    """AC 3.6, sur les DEUX issues du temps 1."""
    vues, extraites = [], []
    ecran = ecran_de_cadences(previsualiser=vues.append,
                              extraire=extraites.append)
    ecran.traiter("enter")
    assert vues == []
    assert cadences.MOTIF_AUCUNE_COCHEE in ecran.ligne_d_etat(False)
    ecran.traiter("x", "x")
    assert extraites == []


def test_sans_affichage_l_entree_PREVISUALISER_est_INACTIVE():
    """AC 5.2, cote `E2-2` : l'entree est retiree, pas degradee."""
    vues = []
    ecran = ecran_de_cadences(previsualiser=vues.append,
                              verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    ecran.liste.viser(FPS_SOURCE)
    ecran.traiter("space", " ")
    ecran.traiter("enter")
    assert vues == []
    assert ecran.raccourcis == atelier_extraction.RACCOURCIS_CADENCES_SANS_ECRAN
    assert "prévisualiser" not in ecran.raccourcis


def test_le_rang_du_curseur_est_PASSE_a_peindre_sur_E2_2(banc):
    """La ligne accentuee est celle de la cadence VISEE, pas la premiere.

    L'auto-detection de `peindre` teste `startswith` sur le glyphe de curseur ;
    les lignes de cet ecran sont indentees de trois blancs, elle ne trouverait
    rien -- en silence.
    """
    ecran = ecran_de_cadences()
    ecran.liste.viser(FPS_SOURCE / 3)
    contenu = peint(ecran, "#corps-cadences", banc)
    lignes = contenu.split("\n")
    accent = jetons.couleur("accent")
    accentuees = [rang for rang, ligne in enumerate(lignes)
                  if ligne.spans and accent in str(ligne.spans[0].style)]
    assert len(accentuees) == 1, accentuees
    assert "8,333" in lignes[accentuees[0]].plain


def test_une_cadence_REFUSEE_est_COLOREE_et_lisible_SANS_couleur(banc):
    """`EPIC11-ARB-43` : la couleur ne porte jamais seule une information."""
    ecran = ecran_de_cadences()
    assert ecran.liste.ajouter("50") is None
    # Le curseur est deplace HORS de la ligne refusee : `peindre` fait passer
    # l'accentuation du curseur devant l'etat, et une cible sous le curseur
    # mesurerait la mauvaise regle.
    ecran.liste.viser(FPS_SOURCE)
    contenu = peint(ecran, "#corps-cadences", banc)
    rouges = [ligne for ligne in contenu.split("\n")
              if ligne.spans
              and jetons.couleur("state-absent") in str(ligne.spans[0].style)]
    assert len(rouges) == 1, [l.plain for l in contenu.split("\n")]
    assert jetons.GLYPHES["absent"] in rouges[0].plain


# ---------------------------------------------------------------------------
# `E2-2b` -- la lecture comparee (E4)
# ---------------------------------------------------------------------------

def test_l_absence_d_AFFICHAGE_est_detectee_AVANT_tout_lancement():
    """AC 5.2, et c'est la mesure la plus dure de la story.

    Le double de `play_cadences` compte ses appels : **exactement zero**. Un
    refus qui arriverait apres coup vaudrait un plantage.
    """
    joueur = JoueurCompte()
    ecran = ecran_de_previz(jouer=joueur,
                            verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    assert joueur.appels == []
    assert ecran.resultat is None
    assert ecran.refus
    # **Ni au montage, ni sur la touche** : depuis `K1.2` c'est `⏎` qui ouvre
    # la fenetre, et le refus doit fermer CE chemin-la aussi -- sans ce volet,
    # le correctif de l'ordre rouvrirait le trou que l'AC 5.2 avait ferme.
    ecran.traiter("enter")
    assert joueur.appels == []
    assert ecran.resultat is None


def test_le_motif_affiche_vient_de_l_ATTRIBUT_motif_et_PAS_de_str():
    """`EPIC11-ARB-73`, et son volet symetrique.

    Le meme refus porte deux textes : le `motif` nu, que la TUI affiche, et
    `str(exception)` qui nomme l'option. Sans le second volet, la mesure
    passerait sur un refus qui ne nommerait rien.
    """
    refus = refus_d_affichage()
    assert "no-display" in str(refus), "le refus du coeur nomme bien l'option"
    assert "no-display" not in refus.motif
    ecran = ecran_de_previz(jouer=JoueurCompte(),
                            verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    assert ecran.refus == refus.motif


def test_le_rendu_de_la_TUI_ne_NOMME_JAMAIS_no_display():
    """`EPIC11-ARB-41`, frontiere negative : un grep rend ZERO."""
    ecran = ecran_de_previz(jouer=JoueurCompte(),
                            verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    for ascii_seul in (False, True):
        lignes, _rang, _etats = ecran.composer(80, ascii_seul)
        rendu = "\n".join(lignes + [ecran.ligne_d_etat(ascii_seul),
                                    ecran.raccourcis])
        assert "no-display" not in rendu
        assert "--" not in rendu.replace("—", "")


def test_AUCUN_rapport_chiffre_n_est_rendu_a_la_place_de_la_previz_REFUSEE():
    """AC 5.3 : « on ne degrade pas une promesse, on la retire »."""
    ecran = ecran_de_previz(jouer=JoueurCompte(),
                            verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    lignes, _rang, _etats = ecran.composer(80, False)
    rendu = "\n".join(lignes)
    assert atelier_extraction.FILET_RAPPORT not in rendu
    assert "retenues" not in rendu
    assert not re.search(r"\d+\s+\d+", rendu), rendu


def test_les_lignes_du_RAPPORT_sont_CELLES_DE_LA_MAQUETTE_E2_2b():
    """Trois passes, l'echec en TROISIEME position, colonnes au caractere."""
    joueur = JoueurCompte()
    ecran = previz_lue(jouer=joueur)
    assert len(joueur.appels) == 1
    lignes, _rang, _etats = ecran.composer(80, False)
    rendues = [ligne.rstrip() for ligne in lignes]
    assert rendues[:8] == lignes_de_maquette(
        "E2-2b-extraction-previz.txt", 3, 11)
    assert rendues[8:12] == lignes_de_maquette(
        "E2-2b-extraction-previz.txt", 11, 15)


def test_la_ligne_d_etat_de_E2_2b_est_celle_de_la_maquette():
    ecran = previz_lue(jouer=JoueurCompte())
    assert ecran.ligne_d_etat(False) == lignes_de_maquette(
        "E2-2b-extraction-previz.txt", 21, 22)[0]


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("corroboree", [True, False])
def test_E2_2b_tient_la_grille_dans_LES_DEUX_regimes(ascii_seul, corroboree):
    """Les deux regimes ET les deux etats de corroboration : la ligne
    d'avertissement est la plus longue de l'ecran, elle doit tenir aussi."""
    ecran = previz_lue(session=session(cadence_corroboree=corroboree),
                       jouer=JoueurCompte())
    lignes, _rang, _etats = ecran.composer(80, ascii_seul)
    for ligne in lignes + [ecran.ligne_d_etat(ascii_seul)]:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        if ascii_seul:
            assert ligne.isascii(), ligne


@pytest.mark.parametrize("nom", ["E2-2b-extraction-previz.txt",
                                 "E2-2c-extraction-choix.txt"])
def test_AUCUN_pourcentage_d_ecart_n_est_rendu_sur_E2_2b_ni_E2_2c(nom):
    """`EPIC11-ARB-69`, frontiere negative : un grep de `%` rend ZERO.

    La mesure porte sur le rendu REEL des deux ecrans, et son volet symetrique
    sur le coeur : lui continue de chiffrer l'ecart, ce qui disparait est son
    affichage, pas son calcul.
    """
    if nom.endswith("previz.txt"):
        ecran = previz_lue(jouer=JoueurCompte())
    else:
        ecran = ecran_de_choix()
    for ascii_seul in (False, True):
        lignes, _rang, _etats = ecran.composer(80, ascii_seul)
        rendu = "\n".join(lignes + [ecran.ligne_d_etat(ascii_seul)])
        assert "%" not in rendu, rendu
    assert "%" in "\n".join(cadence_previz.format_report_lines(
        rapports_de_la_maquette()[2]))


def test_le_coeur_CONTINUE_de_rendre_son_verdict_de_temps_reel():
    """Volet symetrique du lot `M` : **ce qui part est l'affichage, pas la
    mesure.**

    Cent frames, une seule en retard : le coeur declare le temps reel tenu.
    Deux : il ne le declare plus. Les deux cas sont construits sur des
    litteraux et non sur la constante -- un test qui derive son cas de la
    constante qu'il mesure ne mesure que lui-meme. Ce banc-ci reste vert quoi
    que la TUI affiche : c'est ce qui prouve que le retrait n'a pas touche au
    coeur.
    """
    tenu = rapport(Fraction(25), attendues=100, en_retard=1)
    non_tenu = rapport(Fraction(25), attendues=100, en_retard=2)
    assert tenu.temps_reel_tenu is True
    assert non_tenu.temps_reel_tenu is False
    assert cadence_previz.LATE_FRAME_RATE_THRESHOLD > 0
    assert cadence_previz.FINAL_DRIFT_RATIO_THRESHOLD > 0
    # Le journal de `mmu previz` continue de le DIRE, en toutes lettres.
    assert "NON TENU" in "\n".join(
        cadence_previz.format_report_lines(non_tenu))


def test_la_source_qui_ne_CORROBORE_PAS_sa_cadence_AVERTIT_sans_INTERDIRE():
    """`EPIC11-ARB-76` : « Il n'interdit pas de regarder. »"""
    joueur = JoueurCompte()
    ecran = previz_lue(session=session(cadence_corroboree=False),
                       jouer=joueur)
    assert len(joueur.appels) == 1, "avertir n'est pas refuser"
    lignes, _rang, etats = ecran.composer(80, False)
    porteuses = [rang for rang, ligne in enumerate(lignes)
                 if atelier_extraction.PHRASE_CADENCE_NON_CORROBOREE in ligne]
    assert len(porteuses) == 1
    assert etats[porteuses[0]] == "substitute"


def test_Entree_depuis_E2_2b_passe_le_RESULTAT_au_temps_2():
    choisis = []
    ecran = previz_lue(jouer=JoueurCompte(), choisir=choisis.append)
    # Le PREMIER `⏎` a ouvert la fenetre (`previz_lue`), le SECOND choisit :
    # c'est l'ordre des deux sens de la touche, et il est ce que `K1.2` pose.
    assert choisis == []
    assert ecran.traiter("enter") is True
    assert choisis == [ecran.resultat]


def test_Entree_ne_mene_NULLE_PART_quand_la_previz_a_ete_REFUSEE():
    choisis = []
    ecran = ecran_de_previz(jouer=JoueurCompte(), choisir=choisis.append,
                            verifier_l_affichage=refuser_l_affichage)
    ecran.demarrer()
    ecran.traiter("enter")
    assert choisis == []


# ---------------------------------------------------------------------------
# `E2-2c` -- lesquelles extraire (E5)
# ---------------------------------------------------------------------------

def test_les_lignes_de_E2_2c_sont_CELLES_DE_LA_MAQUETTE():
    ecran = ecran_de_choix()
    ecran.liste.viser(VALEURS_LUES[0])
    ecran.traiter("space", " ")
    ecran.liste.viser(VALEURS_LUES[2])
    ecran.traiter("space", " ")
    ecran.liste.viser(VALEURS_LUES[0])
    lignes, _rang, _etats = ecran.composer(80, False)
    rendues = [ligne.rstrip() for ligne in lignes]
    assert rendues[:8] == lignes_de_maquette(
        "E2-2c-extraction-choix.txt", 3, 11)
    assert rendues[8:13] == lignes_de_maquette(
        "E2-2c-extraction-choix.txt", 11, 16)


def test_la_ligne_d_etat_de_E2_2c_porte_les_LOTS_et_leurs_FRAMES():
    ecran = ecran_de_choix()
    ecran.liste.viser(VALEURS_LUES[0])
    ecran.traiter("space", " ")
    ecran.liste.viser(VALEURS_LUES[2])
    ecran.traiter("space", " ")
    assert ecran.ligne_d_etat(False) == "2 lots · 166 frames"


def test_la_ligne_d_etat_porte_le_MAJORANT_quand_on_le_lui_DONNE():
    """Un majorant fabrique ici serait un chiffre orphelin : il vient de
    l'appelant, qui tient la mesure, ou il ne s'ecrit pas."""
    ecran = ecran_de_choix(octets_par_frame=17 * 1024 * 1024)
    ecran.liste.viser(VALEURS_LUES[0])
    ecran.traiter("space", " ")
    etat = ecran.ligne_d_etat(False)
    assert etat.startswith("1 lot · 124 frames · ~ ")
    assert etat.endswith(" (majorant)")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E2_2c_tient_la_grille_dans_LES_DEUX_regimes(ascii_seul):
    ecran = ecran_de_choix()
    ecran.liste.viser(VALEURS_LUES[2])
    ecran.traiter("space", " ")
    lignes, _rang, _etats = ecran.composer(80, ascii_seul)
    for ligne in lignes + [ecran.ligne_d_etat(ascii_seul)]:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        if ascii_seul:
            assert ligne.isascii(), ligne


def test_seules_les_cadences_REGARDEES_sont_montrees():
    """AC 5.4 : le temps 2 ne repropose pas ce qui n'a pas ete vu."""
    ecran = ecran_de_choix()
    assert [c.valeur for c in ecran.liste.cadences] == list(VALEURS_LUES)


def test_le_rapport_d_une_cadence_JOUEE_DEUX_FOIS_est_le_DERNIER():
    """La regle des fabriques, appliquee au rapport : quatre passes, la cadence
    rejouee est la TROISIEME et sa seconde passe est la DERNIERE.

    Une fonction qui rendrait « le premier rapport de cette cadence »
    afficherait les cardinaux du cache froid la ou l'operateur vient de revoir
    la lecture. C'est le mode de panne de `_find_lot` en 5.7.

    La mesure porte sur `frames_presentees`, seul champ qui distingue les deux
    passes de cette cadence-la : 32 la premiere fois, 42 la seconde.
    """
    rapports = list(rapports_du_choix())
    rapports.append(rapport(VALEURS_LUES[2], attendues=42))
    assert rapports[2].frames_presentees == 32
    assert rapports[3].frames_presentees == 42
    trouve = atelier_extraction.rapport_de_la_cadence(rapports, VALEURS_LUES[2])
    assert trouve is rapports[3]


def test_o_ROUVRE_sans_repayer_NI_le_probe_NI_les_selections(monkeypatch):
    """`EPIC11-ARB-70` : « rappeler `play_cadences` avec la session deja en
    main ». Le double de `prepare_previz` compte ses appels : EXACTEMENT UN,
    celui du temps 1.

    Le double est pose **sur le module**, et pas seulement passe a l'ecran :
    c'est la seule facon de voir un appel que l'ecran ferait de lui-meme, qui
    est precisement le defaut que cet arbitrage ferme.
    """
    prepares = []

    def preparer(**kwargs):
        prepares.append(kwargs)
        return session()

    monkeypatch.setattr(cadence_previz, "prepare_previz", preparer)
    premiere = cadence_previz.prepare_previz(
        video_path="/rushes/rush_01.mov", fps_targets=[25.0])
    joueur = JoueurCompte()
    ecran = ecran_de_choix(resultat=resultat(rapports_du_choix(), premiere),
                           rejouer=joueur)
    assert ecran.traiter("o", "o") is True
    assert len(prepares) == 1, "le probe ne se repaie pas"
    assert joueur.appels == [premiere], (
        "la session rendue par le temps 1 est celle qu'on rejoue")


def test_o_REMPLACE_le_RESULTAT_par_celui_de_la_NOUVELLE_lecture():
    """`o` repose `resultat`, et c'est LUI que tout le reste relit.

    Depuis le lot `M`, plus rien n'est derive puis stocke sur les lignes :
    la seule chose que `o` avait a rafraichir etait la mention de temps reel,
    qui n'existe plus. Ce banc mesure donc ce qui reste : la nouvelle lecture
    prend la place de l'ancienne, entierement.
    """
    relue = list(rapports_du_choix())
    relue[2] = rapport(VALEURS_LUES[2], attendues=42)
    neuf = resultat(relue, sess=session())
    ecran = ecran_de_choix(rejouer=JoueurCompte(rendu=neuf))
    ancien = ecran.resultat
    assert ancien is not neuf
    ecran.traiter("o", "o")
    assert ecran.resultat is neuf
    assert atelier_extraction.rapport_de_la_cadence(
        ecran.resultat.reports, VALEURS_LUES[2]).frames_presentees == 42


def test_o_GARDE_les_cadences_deja_cochees():
    """Rouvrir la previz n'est pas repartir de zero : le choix en cours est ce
    qu'on est en train de faire, et le perdre a chaque `o` le rendrait
    inutilisable."""
    ecran = ecran_de_choix(rejouer=JoueurCompte())
    ecran.liste.viser(VALEURS_LUES[2])
    ecran.traiter("space", " ")
    ecran.traiter("o", "o")
    assert [c.cochee for c in ecran.liste.cadences] == [False, False, True]


def test_le_TEMPS_2_n_HERITE_d_AUCUN_consentement_du_temps_1():
    """AC 5.5. Les trois cadences arrivent COCHEES du temps 1 -- elles ont ete
    regardees --, et aucune ne l'est au temps 2."""
    vues = regardees()
    for cadence in vues:
        cadence.cochee = True
    confirmes = []
    ecran = ecran_de_choix(regardees=vues, confirmer=confirmes.append)
    assert [c.cochee for c in ecran.liste.cadences] == [False, False, False]
    assert confirmes == []
    ecran.traiter("enter")
    assert confirmes == [], "zero cochee ne passe pas en silence"
    assert cadences.MOTIF_AUCUNE_COCHEE in ecran.ligne_d_etat(False)


def test_Entree_passe_les_DEUX_LOTS_au_rappel_de_confirmation():
    """Deux lots aux noms ET aux comptes distincts ; la cible n'est pas le
    premier element de la liste."""
    confirmes = []
    ecran = ecran_de_choix(confirmer=confirmes.append)
    ecran.liste.viser(VALEURS_LUES[0])
    ecran.traiter("space", " ")
    ecran.liste.viser(VALEURS_LUES[2])
    ecran.traiter("space", " ")
    assert ecran.traiter("enter") is True
    lots = confirmes[0]
    assert [lot.nom for lot in lots] == ["projet_demo_rush_01_25fps",
                                         "projet_demo_rush_01_25s3"]
    assert [lot.compte for lot in lots] == [124, 42]
    assert [lot.cadence for lot in lots] == [VALEURS_LUES[0], VALEURS_LUES[2]]


@pytest.mark.parametrize("valeur,attendu", [
    (Fraction(25), "25"),
    (Fraction(25, 2), "12,5"),
    (Fraction(25, 3), "25/3"),
])
def test_la_cadence_d_un_LOT_s_ecrit_SANS_PERTE(valeur, attendu):
    """`E2-2c` ecrit `25/3 fps` sur la ligne du lot, la ou la liste ecrit
    `8,333` : le nom du lot dit ce qui a ete demande, pas son arrondi."""
    assert atelier_extraction.texte_de_cadence_exacte(valeur) == attendu


def test_le_rang_du_curseur_est_PASSE_a_peindre_sur_E2_2c(banc):
    ecran = ecran_de_choix()
    ecran.liste.viser(VALEURS_LUES[2])
    contenu = peint(ecran, "#corps-choix", banc)
    lignes = contenu.split("\n")
    accent = jetons.couleur("accent")
    accentuees = [rang for rang, ligne in enumerate(lignes)
                  if ligne.spans and accent in str(ligne.spans[0].style)]
    assert len(accentuees) == 1, accentuees
    assert "8,333" in lignes[accentuees[0]].plain


# ---------------------------------------------------------------------------
# Sobriete -- ce que les trois lignes d'etat ne portent JAMAIS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fabrique", ["cadences", "previz", "choix"])
def test_aucune_ligne_d_etat_des_TROIS_ecrans_ne_porte_un_NOM_DE_TOUCHE(
        fabrique):
    """AC 8.4 / `EPIC11-ARB-56` : la ligne d'etat porte une MESURE."""
    if fabrique == "cadences":
        ecran = ecran_de_cadences()
    elif fabrique == "previz":
        ecran = ecran_de_previz(jouer=JoueurCompte())
        ecran.demarrer()
    else:
        ecran = ecran_de_choix()
    for ascii_seul in (False, True):
        etat = ecran.ligne_d_etat(ascii_seul)
        for touche in ("Échap", "Echap", "Entree", "Espace", "F1", "Tab",
                       "⏎"):
            assert touche not in etat, (fabrique, etat)


def test_la_frontiere_de_SOBRIETE_MORD():
    """Volet symetrique : sans lui, la garde ci-dessus serait verte sur une
    ligne d'etat vide."""
    assert "Espace" in atelier_extraction.RACCOURCIS_CADENCES
    assert "⏎" in atelier_extraction.RACCOURCIS_PREVIZ
    assert "Échap" in atelier_extraction.RACCOURCIS_CHOIX


# ===========================================================================
# Lot I -- `I3` : la droite du bandeau des DEUX TEMPS
#
# Elle etait vide sur les trois ecrans de cadences comme sur les neuf autres :
# `Contexte.objet` existait depuis la vague 1 et l'atelier ne le posait nulle
# part. Les maquettes y portent `temps 1 sur 2 · prévisualiser` (`E2-2`,
# `E2-2b`) et `temps 2 sur 2 · extraire` (`E2-2c`) -- c'est ce qui dit OU L'ON
# EN EST dans le parcours, ce que ni le titre de zone ni la ligne d'etat ne
# disent.
# ===========================================================================

def bandeau_dessine(banc, ecran, ascii_seul: bool = False) -> str:
    """La ligne de bandeau **telle qu'elle est dessinee**, ecran monte."""
    from textual.widgets import Static

    async def scenario(pilote):
        pilote.app.ascii_seul = ascii_seul
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)

    return banc(coque(ecran), scenario)


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("fabrique,attendu", [
    ("cadences", atelier_extraction.OBJET_TEMPS_1),
    ("previz", atelier_extraction.OBJET_TEMPS_1),
    ("choix", atelier_extraction.OBJET_TEMPS_2),
])
def test_le_BANDEAU_des_trois_ecrans_de_cadences_annonce_SON_TEMPS(
        banc, ascii_seul, fabrique, attendu):
    """`I3` : les deux temps sont mesures, et ils DIFFERENT.

    Les trois ecrans sont pris, et le troisieme n'annonce pas le meme temps que
    les deux premiers : un bandeau qui rendrait toujours la meme chaine
    passerait sur un corpus a un seul ecran.
    """
    ecran = {"cadences": ecran_de_cadences,
             "previz": ecran_de_previz,
             "choix": ecran_de_choix}[fabrique]()
    droite = jetons.replier_ascii(attendu) if ascii_seul else attendu
    bandeau = bandeau_dessine(banc, ecran, ascii_seul)

    assert bandeau.rstrip().endswith(droite), (bandeau, droite)
    assert jetons.colonnes(bandeau) <= jetons.largeur_utile(), bandeau


def test_les_DEUX_temps_ne_disent_pas_la_meme_chose():
    """Volet symetrique du precedent : deux constantes egales le rendraient
    vert sans rien mesurer -- c'est la regle des fabriques, appliquee a un
    couple de textes."""
    assert atelier_extraction.OBJET_TEMPS_1 != atelier_extraction.OBJET_TEMPS_2
    assert "1 sur 2" in atelier_extraction.OBJET_TEMPS_1
    assert "2 sur 2" in atelier_extraction.OBJET_TEMPS_2


def test_SANS_AFFICHAGE_le_bandeau_de_E2_2_ne_promet_AUCUN_temps_1(banc):
    """`EPIC11-ARB-41`, verbatim : « **on ne degrade pas une promesse, on la
    retire quand elle ne peut pas etre tenue** ».

    Sans affichage il n'y a plus deux temps -- l'entree previz est inactive et
    `x` extrait directement (AC 5.1) --, donc le bandeau redevient nu au lieu
    d'annoncer un temps 1 qui ne mene nulle part.
    """
    ecran = ecran_de_cadences(verifier_l_affichage=refuser_l_affichage)
    bandeau = bandeau_dessine(banc, ecran)

    assert ecran.refus_d_affichage, "la fixture ne refuse rien"
    assert atelier_extraction.OBJET_TEMPS_1 not in bandeau, bandeau
    assert bandeau.rstrip() == "mmu · projet_demo · Extraction", bandeau
