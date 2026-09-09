# -*- coding: utf-8 -*-
"""Story 11.4e, lot I -- AC 8 : la progression AGREGE la passe et nomme le lot.

Le banc de l'AC 8, et **seulement** d'elle. Il mesure quatre choses que la
surface d'execution ne faisait pas : le compte agrege sur la passe entiere
(8.1), les deux regimes de remise a zero (8.2), le titre qui nomme le lot
courant (8.4) et la liste des lots avec ses trois etats fermes (8.5), le tout
sous la grille 80 x 24 (8.7) et sans seconde redaction dans le paquet (8.6).

**La regle des fabriques mord ici sur ses quatre points a la fois**, et c'est
l'agregation qui l'exige : une somme fausse ne se voit pas quand tous les
termes sont egaux (`7 + 7 + 7` et `3 x 7` rendent le meme 21), un `find` fautif
ne se voit pas quand la cible est premiere, et un **balayage tronque** -- le
mode de panne propre a une agregation -- ne se voit pas quand aucune cible
n'est en queue.
"""

import pathlib

import pytest
from textual.widgets import Static

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import (
    ETAT_DU_LOT_ECRIT,
    INDENT_DES_LIGNES,
    MENTION_ECRIT,
    MENTION_EN_ATTENTE,
    MENTION_EN_COURS,
    MENTIONS_DES_LOTS,
    EcranExecution,
    LotDeLaPasse,
    PasseEnCours,
    SurfaceExecution,
    largeur_des_mentions,
    ligne_du_lot,
    mention_du_lot,
)

from outils_frontiere import chaines_de_code

#: **Trois** lots, aux cardinaux DISTINCTS et aux noms DISTINGUABLES.
#:
#: Trois et non deux : une cible en seconde position d'une paire est aussi en
#: derniere, et les deux formes y sont indiscernables (`CLAUDE.md`, point 2 bis,
#: mesure deux fois le 2026-08-30).
#:
#: Cardinaux distincts et **jamais uniformes** : `7 + 13 + 5 = 25`, et aucune
#: somme partielle n'egale la totale -- un balayage qui sauterait le premier
#: rendrait 18, le dernier 20, celui du milieu 12. Avec trois fois 7, les trois
#: pannes rendraient 14 et seraient indiscernables entre elles.
LOTS_TEMOINS = (("projet_demo_rush_01_25fps", 7),
                ("projet_demo_rush_01_12p5", 13),
                ("projet_demo_rush_02_50fps", 5))
CARDINAL_DE_LA_PASSE = 25
LIBELLE = "Extraction en cours"

#: La maquette **approuvee** de `E2-4`, qui fait foi (`CLAUDE.md` : une maquette
#: se corrige a la source, jamais dans le rendu).
MAQUETTE_E2_4 = (pathlib.Path(__file__).resolve().parents[3]
                 / "_bmad-output" / "planning-artifacts" / "ux-designs"
                 / "ux-tui-2026-08-27" / "maquettes"
                 / "E2-4-extraction-execution.txt")


def coque(**kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def surface_declaree(lots=LOTS_TEMOINS, libelle=LIBELLE) -> SurfaceExecution:
    surface = SurfaceExecution("frames")
    surface.declarer_la_passe(libelle, lots)
    return surface


def derouler(surface: SurfaceExecution, jusqu_au_rang: int,
             faites_du_dernier: int | None = None) -> list[tuple[int, int]]:
    """Jouer la passe jusqu'au lot `jusqu_au_rang` (0-fonde), et relever.

    Rend la suite des couples `(faites, total)` **recus par un observateur**,
    et non l'etat final : l'AC 8.1 porte sur la SUITE, pas sur son dernier
    terme -- une remise a zero au lot 2 laisse le dernier terme juste.
    """
    recus: list[tuple[int, int]] = []
    surface.abonner(lambda av: recus.append((av.faites, av.total)))
    for rang, (_nom, cardinal) in enumerate(LOTS_TEMOINS[:jusqu_au_rang + 1]):
        emetteur = surface.emetteur(cardinal)
        dernier = (cardinal if rang < jusqu_au_rang
                   else (cardinal if faites_du_dernier is None
                         else faites_du_dernier))
        for faites in range(1, dernier + 1):
            emetteur.emettre(faites)
    return recus


# --------------------------------------------------------------------------
# I1 -- AC 8.1 : le compte agrege la passe et ne decroit jamais
# --------------------------------------------------------------------------

def test_la_suite_des_couples_ne_DECROIT_jamais_sur_une_passe_a_trois_lots():
    """AC 8.1, et c'est le mutant naturel : remettre l'emetteur a zero au lot 2.

    La mesure porte sur la **suite entiere** des couples recus, pas sur son
    dernier terme : une remise a zero au deuxieme lot laisse le dernier terme
    parfaitement juste et n'apparait qu'au creux du milieu.
    """
    recus = derouler(surface_declaree(), jusqu_au_rang=2)

    assert len(recus) == CARDINAL_DE_LA_PASSE, (
        "un jalon par unite de la passe entiere", len(recus))
    for avant, apres in zip(recus, recus[1:]):
        assert apres[0] >= avant[0], ("le compte a recule", avant, apres)
        assert apres[1] >= avant[1], ("le total a recule", avant, apres)
    assert recus[-1] == (CARDINAL_DE_LA_PASSE, CARDINAL_DE_LA_PASSE)


def test_le_total_est_la_SOMME_des_cardinaux_DES_LE_PREMIER_jalon():
    """AC 8.1 : « la somme des cardinaux de tous les lots du plan ».

    Un total qui grossirait de lot en lot ne decroit pas non plus, et passerait
    donc le test precedent. C'est ce test-ci qui separe les deux : au premier
    jalon du premier lot, le total vaut deja 25 et non 7.
    """
    recus = derouler(surface_declaree(), jusqu_au_rang=0, faites_du_dernier=1)

    assert recus[0] == (1, CARDINAL_DE_LA_PASSE), (
        "le total du premier jalon n'est pas celui de la passe", recus[0])


def test_le_compte_du_lot_du_MILIEU_s_AJOUTE_a_celui_du_premier():
    """AC 8.1, cible **au milieu** : 7 faits, puis 4 du lot de 13, font 11.

    Le lot vise n'est ni le premier ni le dernier : un `find` qui rendrait
    toujours le premier lot, ou une somme qui n'agregerait que le lot courant,
    rendraient l'un 4 et l'autre 4 -- jamais 11.
    """
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=1, faites_du_dernier=4)

    assert (surface.avancement.faites, surface.avancement.total) == (
        11, CARDINAL_DE_LA_PASSE)


def test_le_DERNIER_lot_de_la_passe_est_compte_lui_aussi():
    """AC 8.1, cible en **queue** -- le mode de panne propre a une agregation.

    Un balayage tronque qui saute la derniere entree reste vert tant que toutes
    les cibles sont au milieu : il rendrait ici 20 sur 20 au lieu de 25 sur 25,
    et la barre atteindrait 100 % avant la fin de la passe.
    """
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=2)

    assert surface.avancement.faites == CARDINAL_DE_LA_PASSE
    assert surface.passe.cardinal_de_la_passe == CARDINAL_DE_LA_PASSE


def test_le_PREMIER_lot_de_la_passe_est_compte_lui_aussi():
    """AC 8.1, cible en **tete**. Volet symetrique du precedent : un balayage
    qui sauterait la premiere entree rendrait 18 la ou la passe en compte 25."""
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=0)

    assert surface.avancement.faites == LOTS_TEMOINS[0][1]
    assert surface.passe.faites_de_la_passe == LOTS_TEMOINS[0][1]


def test_le_cardinal_MESURE_prime_sur_le_cardinal_DECLARE():
    """Le plan promet, le coeur mesure -- et c'est le mesure qui vaut.

    Un total compose de promesses ferait diverger la barre du compte des
    jalons, et l'ecart ne se verrait qu'a la fin de la passe.
    """
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])
    # Le lot du MILIEU rend 11 frames la ou le plan en promettait 13.
    surface.emetteur(11)

    assert surface.passe.lots[1].cardinal == 11
    assert surface.avancement.total == CARDINAL_DE_LA_PASSE - 2


# --------------------------------------------------------------------------
# I1 -- AC 8.2 : les DEUX regimes, mesures separement
# --------------------------------------------------------------------------

def test_un_LOT_suivant_ne_remet_PAS_le_compte_a_zero():
    """AC 8.2, premier regime : lot suivant -> continuite."""
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=0)
    avant = surface.avancement.faites
    surface.emetteur(LOTS_TEMOINS[1][1])

    assert (avant, surface.avancement.faites) == (7, 7)


def test_une_PASSE_suivante_remet_le_compte_a_zero():
    """AC 8.2, second regime : passe suivante -> remise a zero.

    Sur la **meme** surface : une seconde surface remettrait a zero par sa
    seule construction, et ne mesurerait donc rien de ce que la declaration
    fait. Le total, lui, devient celui de la passe NEUVE -- une passe suivante
    a d'autres lots.
    """
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=2)
    assert surface.avancement.faites == CARDINAL_DE_LA_PASSE

    surface.declarer_la_passe(LIBELLE, [("projet_demo_rush_03_24fps", 9)])

    assert (surface.avancement.faites, surface.avancement.total) == (0, 9)


def test_l_estimateur_et_le_temps_restant_sont_effaces_a_CHAQUE_lot():
    """AC 8.2 : l'agregation porte sur le COMPTE, jamais sur la vitesse.

    `EPIC7-ARB-67` mot pour mot : un `temps_restant` herite affichait
    « reste ~ 3 min 14 s » alors que l'estimateur du coeur rendait `None`. Deux
    lots de cadences differentes n'ont pas la meme vitesse.
    """
    surface = surface_declaree()
    derouler(surface, jusqu_au_rang=0)
    surface.avancement.temps_restant = 194.0

    surface.emetteur(LOTS_TEMOINS[1][1])

    assert surface.avancement.temps_restant is None
    assert surface.estimateur.temps_restant is None


def test_le_JOURNAL_n_est_remis_a_zero_dans_AUCUN_des_deux_regimes():
    """AC 8.3 : `EPIC11-ARB-93` n'est pas renverse, son motif residuel l'est."""
    surface = surface_declaree()
    surface.journal.inscrire("-- lot 1/3 : projet_demo_rush_01_25fps")
    derouler(surface, jusqu_au_rang=0)
    surface.emetteur(LOTS_TEMOINS[1][1])
    apres_un_lot = len(surface.journal)

    surface.declarer_la_passe(LIBELLE, [("projet_demo_rush_03_24fps", 9)])

    assert apres_un_lot > 1, "le journal a garde les jalons du premier lot"
    assert len(surface.journal) == apres_un_lot, (
        "une passe suivante n'efface pas le journal non plus")


# --------------------------------------------------------------------------
# I1 -- frontiere NEGATIVE : sans passe declaree, rien ne change
# --------------------------------------------------------------------------

def test_SANS_passe_declaree_l_emetteur_garde_le_regime_d_avant():
    """Volet symetrique de l'AC 8.1, et il n'est pas decoratif.

    Une passe non declaree est une passe dont on ne connait NI le nombre de
    lots NI la somme de leurs cardinaux. Agreger quand meme ferait grossir le
    total de lot en lot -- « 7/7, 100 % » a la fin du premier lot d'une passe
    qui en compte trois --, et une ligne fausse est pire qu'une ligne absente
    (`DESIGN.md` section 3). Trois ecrans d'execution du depot n'ont pas de
    plan a declarer : ce test est ce qui les protege.
    """
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(7)
    emetteur.emettre(7)
    assert (surface.avancement.faites, surface.avancement.total) == (7, 7)

    surface.emetteur(13)

    assert surface.passe is None
    assert (surface.avancement.faites, surface.avancement.total) == (0, 13)


# --------------------------------------------------------------------------
# I3 -- AC 8.5 : les trois etats, ensemble FERME
# --------------------------------------------------------------------------

def test_les_trois_etats_sur_une_passe_a_trois_lots_la_cible_au_MILIEU():
    """AC 8.5 : le lot `en cours` **au milieu**, les deux autres encadrent."""
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])
    surface.emetteur(LOTS_TEMOINS[1][1])

    assert surface.passe.mentions_des_lots() == [
        MENTION_ECRIT, MENTION_EN_COURS, MENTION_EN_ATTENTE]


def test_les_trois_etats_avec_la_cible_en_TETE_puis_en_QUEUE():
    """AC 8.5, les deux bords -- une comparaison d'un seul cote y meurt.

    En tete, `rang < courant` n'est jamais vrai ; en queue, `rang > courant` ne
    l'est jamais. Un `mention_du_lot` qui ne comparerait que dans un sens
    passerait l'un des deux et echouerait l'autre, et la cible au milieu ne les
    departage pas.
    """
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])
    en_tete = surface.passe.mentions_des_lots()
    surface.emetteur(LOTS_TEMOINS[1][1])
    surface.emetteur(LOTS_TEMOINS[2][1])
    en_queue = surface.passe.mentions_des_lots()

    assert en_tete == [MENTION_EN_COURS, MENTION_EN_ATTENTE,
                       MENTION_EN_ATTENTE]
    assert en_queue == [MENTION_ECRIT, MENTION_ECRIT, MENTION_EN_COURS]


def test_l_ensemble_des_mentions_est_FERME_et_vaut_exactement_les_trois():
    """AC 8.5 : « les trois etats forment un ensemble ferme ».

    L'assertion porte sur l'ensemble EXACT et non sur une inclusion : « chaque
    mention est l'une des trois » laisserait passer une passe qui n'en rendrait
    jamais qu'une seule.
    """
    rendues = {mention_du_lot(rang, 1) for rang in range(3)}

    assert rendues == set(MENTIONS_DES_LOTS)
    assert len(MENTIONS_DES_LOTS) == 3


def test_les_etats_DERIVENT_de_l_avancement_et_non_d_un_compteur_d_ecran():
    """AC 8.5 : « derives de l'avancement reel, jamais d'un compteur d'ecran ».

    On ne touche ici **que** le canal du coeur ; aucun ecran n'est monte, et
    aucune methode d'ecran n'est appelee. Les mentions changent quand meme.
    """
    surface = surface_declaree()
    avant = surface.passe.mentions_des_lots()
    surface.emetteur(LOTS_TEMOINS[0][1])
    surface.emetteur(LOTS_TEMOINS[1][1])
    apres = surface.passe.mentions_des_lots()

    assert avant[0] == MENTION_EN_COURS and apres[0] == MENTION_ECRIT


def test_une_passe_SANS_lot_est_refusee_plutot_que_rendue_vide():
    """Un ecran d'execution sans rien a executer n'a pas d'etat a montrer."""
    with pytest.raises(ValueError):
        PasseEnCours(libelle=LIBELLE, lots=())


def test_un_lot_de_plus_que_la_passe_n_ecrit_pas_hors_de_la_liste():
    """Le rang est **borne a la queue**, il ne leve pas au milieu d'une passe.

    Deborder par la queue est le mode de panne d'une agregation ; le borner
    vaut mieux que de laisser un `IndexError` traverser jusqu'a l'ecran.
    """
    surface = surface_declaree()
    for _rang in range(len(LOTS_TEMOINS) + 2):
        surface.emetteur(3)

    assert surface.passe.rang_du_lot_courant == len(LOTS_TEMOINS) - 1


# --------------------------------------------------------------------------
# I2 -- AC 8.4 : le titre nomme le lot courant
# --------------------------------------------------------------------------

def test_le_titre_nomme_le_lot_courant_1_INDEXE_pour_l_operateur():
    """AC 8.4, cible **au milieu** : le deuxieme lot se dit « lot 2 sur 3 »."""
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])
    surface.emetteur(LOTS_TEMOINS[1][1])

    assert surface.passe.titre() == "Extraction en cours — lot 2 sur 3"


def test_le_titre_du_PREMIER_lot_dit_lot_1_et_non_lot_0():
    """AC 8.4, cible en **tete** : c'est ici qu'un rang 0-fonde se voit."""
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])

    assert surface.passe.titre() == "Extraction en cours — lot 1 sur 3"


def test_le_titre_rend_EXACTEMENT_la_ligne_5_de_la_maquette_approuvee():
    """AC 8.4 : « exactement comme la maquette approuvee ».

    La maquette fait foi et se lit a sa source : ce test la **lit** plutot que
    de recopier sa ligne, pour qu'une correction a la source fasse rougir ici
    plutot que de diverger en silence. Elle montre une passe a deux lots dont
    le courant est le SECOND -- la cible n'y est donc pas en premiere position.
    """
    attendue = MAQUETTE_E2_4.read_text(encoding="utf-8").split("\n")[4]
    attendue = attendue[2:-2].strip()
    surface = SurfaceExecution("frames")
    surface.declarer_la_passe(LIBELLE, LOTS_TEMOINS[:2])
    surface.emetteur(LOTS_TEMOINS[0][1])
    surface.emetteur(LOTS_TEMOINS[1][1])

    assert surface.passe.titre() == attendue


def test_SANS_passe_declaree_l_ecran_garde_le_titre_de_tache_de_l_atelier(banc):
    """Volet symetrique de l'AC 8.4 : aucun rang n'est invente.

    Un ecran qui composerait « lot 1 sur 1 » faute de plan dirait un chiffre
    que rien ne mesure -- et il le dirait sur les trois ecrans d'execution qui
    n'ont pas de plan a declarer.
    """
    surface = SurfaceExecution("frames")
    ecran = EcranExecution(surface, "Détection en cours")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one("#tache", Static).content

    contenu = banc(coque(), scenario)

    assert "Détection en cours" in str(contenu)
    assert "lot" not in str(contenu)


# --------------------------------------------------------------------------
# I3 -- AC 8.5 : la liste des lots, montee
# --------------------------------------------------------------------------

def test_l_ecran_montre_les_TROIS_lots_nommes_avec_leur_etat(banc):
    """AC 8.4 et 8.5, montes : le titre, puis un lot par ligne.

    Les trois noms sont **distinguables** : un appariement positionnel inverse
    entre les lots et leurs mentions resterait vert sur une fabrique uniforme
    (`M33` de la 5.6).
    """
    surface = surface_declaree()
    ecran = EcranExecution(surface, "Extraction de rush_01 — 3 lots")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        surface.emetteur(LOTS_TEMOINS[0][1])
        surface.emetteur(LOTS_TEMOINS[1][1])
        pilote.app.screen.rafraichir()
        await pilote.pause()
        return str(pilote.app.screen.query_one("#tache", Static).content)

    rendu = banc(coque(), scenario)
    lignes = [ligne.rstrip() for ligne in rendu.split("\n")]

    assert lignes[0].strip() == "Extraction en cours — lot 2 sur 3"
    corps = [ligne for ligne in lignes if ligne.strip()][1:]
    assert len(corps) == 3, (corps,)
    for (nom, _cardinal), mention, ligne in zip(
            LOTS_TEMOINS,
            (MENTION_ECRIT, MENTION_EN_COURS, MENTION_EN_ATTENTE), corps):
        assert ligne.strip().startswith(nom), (nom, ligne)
        assert ligne.strip().endswith(mention), (mention, ligne)


def test_seul_le_lot_ECRIT_porte_un_etat_de_peinture(banc):
    """AC 8.5 : les maquettes ne posent de marque que sur ce qui est fait.

    La cible n'est ni la premiere ni la derniere ligne du bloc : le titre et la
    respiration la precedent, deux lots la suivent. Un rang de peinture ecrit
    en dur teindrait le titre.
    """
    surface = surface_declaree()
    surface.emetteur(LOTS_TEMOINS[0][1])
    surface.emetteur(LOTS_TEMOINS[1][1])
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one("#tache", Static).content

    contenu = banc(coque(), scenario)
    # Le jeton de COULEUR est prefixe `state-`, l'etat de peinture ne l'est
    # pas : `jetons.couleur` leve sur un nom inconnu plutot que de rendre une
    # teinte vide, et c'est ce qui a fait rougir la premiere redaction de ce
    # banc au lieu de le laisser passer sans rien mesurer.
    teinte = jetons.couleur(f"state-{ETAT_DU_LOT_ECRIT}")
    teintes = [ligne.plain.strip() for ligne in contenu.split("\n")
               if any(teinte in str(span.style) for span in ligne.spans)]

    assert teintes == [
        ligne_du_lot(LOTS_TEMOINS[0][0], MENTION_ECRIT,
                     jetons.largeur_utile()).strip()], (teintes, str(contenu))


# --------------------------------------------------------------------------
# I4 -- AC 8.6 : le meme rendu sert les deux ateliers, une seule redaction
# --------------------------------------------------------------------------

def test_les_DEUX_ateliers_declarent_leur_passe_par_le_MEME_chemin():
    """AC 8.6 : la passe d'ecriture du Scan recoit le meme traitement que
    l'Extraction, et **sans seconde redaction**.

    Les deux boucles sont jouees pour de vrai, avec un coeur factice : c'est le
    seul moyen de mesurer que le champ `passe` est ECRIT par un chemin reel, et
    non seulement declare au modele -- « un champ declare au schema et lu par un
    resolveur mais ecrit par aucun chemin est une surface morte qui retourne
    l'arbitrage en silence » (`CLAUDE.md`).
    """
    from mixed_media_utility.tui import (atelier_extraction_ecriture,
                                         atelier_scan_ecriture)

    assert "declarer_la_passe" in _source(atelier_extraction_ecriture)
    assert "declarer_la_passe" in _source(atelier_scan_ecriture)
    # Le libelle de chaque atelier est celui de SA maquette, et les deux
    # different : `E2-4` dit « Extraction en cours », `E3-7` nomme ce qu'il
    # ecrit. Un libelle compose dans l'ecran aurait donc ete devine.
    assert (atelier_extraction_ecriture.LIBELLE_DE_LA_PASSE
            != atelier_scan_ecriture.LIBELLE_DE_LA_PASSE)


def _source(module) -> str:
    return pathlib.Path(module.__file__).read_text(encoding="utf-8")


def test_AUCUNE_seconde_redaction_des_TROIS_mentions_dans_le_paquet(
        sources_tui):
    """AC 8.6 : comptage a ZERO d'une seconde implementation de la liste.

    La mesure porte sur les chaines du **code**, docstrings exclus : un grep de
    texte mordrait sur les proses qui expliquent la regle. Le critere est
    l'ensemble des trois mentions EXACTES dans un meme module -- `écrit` seul
    se dit partout (« Frames écrites », « Déjà écrit ») et ne prouve rien, et
    `atelier_exports_execution` porte deux des trois pour un autre ensemble
    ferme (les etapes d'un encodage, dont la premiere mention est `conforme`).
    """
    porteurs = sorted(
        chemin.name for chemin in sources_tui
        if set(MENTIONS_DES_LOTS) <= set(chaines_de_code(chemin)))

    assert porteurs == ["execution.py"], porteurs


def test_le_JEU_FERME_des_mentions_n_est_liE_qu_UNE_fois(sources_tui):
    """AC 8.6, volet du meme comptage : le tuple qui cale la colonne.

    C'est lui qui rend la mesure operatoire plutot que decorative : deux
    modules qui lient chacun leur jeu de mentions calent chacun leur colonne,
    et les deux divergent au premier etat ajoute. La mesure ne porte PAS sur
    l'indentation -- `atelier_pdf_resultat` en pose une pour une liste de
    planches, qui n'est pas une liste de lots.
    """
    porteurs = sorted(chemin.name for chemin in sources_tui
                      if "MENTIONS_DES_LOTS = " in chemin.read_text(
                          encoding="utf-8"))

    assert porteurs == ["execution.py"], porteurs


# --------------------------------------------------------------------------
# I5 -- AC 8.7 : la grille 80 x 24, et le bornage
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ascii_seul", [False, True])
def test_aucune_ligne_de_lot_ne_depasse_la_zone_utile(ascii_seul):
    """AC 8.7, budget RECALCULE : 5 + 57 + 2 + 2 + 10 = 76 exactement.

    La mesure est faite sur les trois mentions -- la colonne est calee sur le
    jeu complet, donc c'est `en attente` qui la dimensionne -- et sur les deux
    regimes : `replier_ascii` peut changer la largeur d'un texte accentue.
    """
    utile = jetons.largeur_utile()
    for mention in MENTIONS_DES_LOTS:
        for nom in ("court", "projet_demo_rush_01_25fps", "n" * 300):
            ligne = ligne_du_lot(nom, mention, utile, ascii_seul)
            assert jetons.colonnes(ligne) <= utile, (
                mention, len(nom), jetons.colonnes(ligne), ligne)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_une_ligne_EXACTEMENT_a_la_borne_n_est_pas_mutilee(ascii_seul):
    """AC 8.7, le piege nomme par le lot J de la 11.7.

    Une ligne exactement a la borne passe sous l'abreviateur et est mutilee en
    silence **dans le seul regime ASCII**. On construit donc le nom qui rend la
    ligne longue de 76 colonnes tout rond, et on verifie que le nom en ressort
    entier -- pas de points d'abregement, pas un caractere perdu.
    """
    utile = jetons.largeur_utile()
    place = (utile - len(INDENT_DES_LIGNES) - largeur_des_mentions(ascii_seul)
             - 2 * jetons.CREUX_MINIMAL)
    nom = "n" * place
    ligne = ligne_du_lot(nom, MENTION_EN_ATTENTE, utile, ascii_seul)

    assert jetons.colonnes(ligne) == utile, (jetons.colonnes(ligne), ligne)
    assert nom in ligne, ligne
    assert jetons.points_d_abregement(ascii_seul) not in ligne, ligne


def test_le_corps_tient_au_PLANCHER_et_la_liste_s_y_borne(banc):
    """AC 8.7 : la grille reste 80 x 24, ligne d'etat comprise.

    Vingt lots, c'est-a-dire plus que la zone centrale n'en peut montrer : la
    liste se borne, et le bloc entier tient dans les 17 lignes du plancher.
    """
    lots = [(f"projet_demo_lot_{rang:02d}", rang + 1) for rang in range(20)]
    surface = SurfaceExecution("frames")
    surface.declarer_la_passe(LIBELLE, lots)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran_ = pilote.app.screen
        tete = str(ecran_.query_one("#tache", Static).content).split("\n")
        return len(tete), ecran_.lignes_de_lots_visibles(), max(
            jetons.colonnes(ligne) for ligne in tete)

    hauteur_du_bloc, place, plus_large = banc(coque(), scenario)
    centre = jetons.hauteur_centrale(jetons.HAUTEUR_PLANCHER)

    assert place == centre - EcranExecution.LIGNES_HORS_LOTS - 2, place
    # 1 titre + 1 respiration + `place` lignes de liste, ligne `…` comprise.
    assert hauteur_du_bloc <= 2 + place, (hauteur_du_bloc, place)
    # Le bloc, la ligne vide, le journal replie et la respiration.
    assert hauteur_du_bloc + 1 + 2 + 1 <= centre, (hauteur_du_bloc, centre)
    assert plus_large <= jetons.largeur_utile(), plus_large


def test_la_place_gagnee_en_hauteur_va_a_la_LISTE_et_pas_au_cadre(banc):
    """AC 8.7 : « un test mesure le rendu a la hauteur plancher ET a une
    hauteur superieure -- la place gagnee va a la zone centrale »."""
    lots = [(f"projet_demo_lot_{rang:02d}", rang + 1) for rang in range(20)]
    surface = SurfaceExecution("frames")
    surface.declarer_la_passe(LIBELLE, lots)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.lignes_de_lots_visibles()

    au_plancher = banc(coque(), scenario)
    plus_haut = banc(coque(), scenario, taille=(80, 34))

    assert plus_haut == au_plancher + 10, (au_plancher, plus_haut)


def test_le_journal_DEPLIE_prend_la_place_de_la_liste_des_lots(banc):
    """AC 8.7 : `Tab journal` promet le journal complet, et il le tient.

    Le budget du journal ne bouge dans **aucun** des deux regimes : une liste
    des lots qui le rognerait serait une regression sur trois ecrans qui n'ont
    rien demande.
    """
    surface = surface_declaree()
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        replie = (pilote.app.screen.lignes_de_lots_visibles(),
                  pilote.app.screen.lignes_de_journal_visibles())
        await pilote.press("tab")
        await pilote.pause()
        deplie = (pilote.app.screen.lignes_de_lots_visibles(),
                  pilote.app.screen.lignes_de_journal_visibles())
        tete = str(pilote.app.screen.query_one("#tache", Static).content)
        return replie, deplie, tete

    replie, deplie, tete = banc(coque(), scenario)
    centre = jetons.hauteur_centrale(jetons.HAUTEUR_PLANCHER)

    assert replie == (centre - EcranExecution.LIGNES_HORS_LOTS - 2, 2)
    assert deplie == (0, centre - 3)
    # Le titre reste : c'est la LISTE qui tombe, pas le rang du lot.
    assert tete.strip() == surface.passe.titre()


def test_le_lot_courant_reste_visible_quand_la_liste_defile(banc):
    """AC 8.7 : borner ne doit pas cacher ce que le titre annonce.

    Le lot courant est place **en queue** de vingt lots : une fenetre figee sur
    la tete montrerait vingt lignes dont aucune n'est celle qui travaille.
    """
    lots = [(f"projet_demo_lot_{rang:02d}", rang + 1) for rang in range(20)]
    surface = SurfaceExecution("frames")
    surface.declarer_la_passe(LIBELLE, lots)
    for _nom, cardinal in lots:
        surface.emetteur(cardinal)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#tache", Static).content)

    rendu = banc(coque(), scenario)

    assert "projet_demo_lot_19" in rendu, rendu
    assert rendu.split("\n")[0].strip().endswith("lot 20 sur 20")


def test_un_lot_declare_par_un_couple_vaut_un_LotDeLaPasse():
    """La declaration accepte les deux formes, et elles rendent le meme objet.

    Deux formes valent mieux qu'une seule ici : les ateliers declarent des
    couples, et les bancs de rendu ont besoin de l'objet nomme.
    """
    surface = surface_declaree(lots=[LotDeLaPasse("a", 3), ("b", 4)])

    assert surface.passe.lots == (LotDeLaPasse("a", 3), LotDeLaPasse("b", 4))
    assert surface.avancement.total == 7


# --------------------------------------------------------------------------
# Les trois survivants de la campagne de mutation, fermes (2026-09-05)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_colonne_des_mentions_ne_BOUGE_PAS_quand_un_lot_change_d_etat(
        ascii_seul):
    """Mutant `M11`, survivant de la premiere campagne, ferme ici.

    Caler la colonne sur la mention COURANTE au lieu du jeu complet rend des
    lignes plus **courtes**, jamais plus longues : le controle de debordement
    ne peut donc pas le voir. Ce qu'il produit se voit ailleurs -- la colonne
    saute de cinq colonnes au moment precis ou un lot passe de `en cours` a
    `écrit`, c'est-a-dire pendant la passe, sous les yeux de l'operateur.

    C'est le motif que le commentaire de `MENTIONS_DES_LOTS` annonce, et il
    n'etait mesure nulle part avant ce banc.
    """
    utile = jetons.largeur_utile()
    nom = "projet_demo_rush_01_25fps"
    colonnes = {}
    for mention in MENTIONS_DES_LOTS:
        ligne = ligne_du_lot(nom, mention, utile, ascii_seul)
        rendue = jetons.replier_ascii(mention) if ascii_seul else mention
        colonnes[mention] = jetons.colonnes(ligne[:ligne.rindex(rendue)])

    assert len(set(colonnes.values())) == 1, colonnes
    # Volet symetrique : la colonne existe bien, elle n'est pas simplement
    # zero des trois cotes -- une ligne ou la mention ouvrirait a gauche
    # passerait le test d'unicite sans rien dire.
    assert set(colonnes.values()) == {
        utile - largeur_des_mentions(ascii_seul)}, colonnes


def test_en_regime_ASCII_la_mention_est_REPLIEE_et_le_riche_ne_l_est_pas():
    """Mutant `M13`, survivant de la premiere campagne, ferme ici.

    Une seule des trois mentions porte un accent, et c'est **`écrit`** : les
    deux autres traversent `replier_ascii` sans changer, si bien qu'un banc
    ecrit sur `en attente` -- ce que faisait celui de la borne -- ne peut pas
    voir le repli disparaitre. Le regime ASCII est exactement celui ou aucune
    capture couleur ne montre l'ecart.
    """
    utile = jetons.largeur_utile()
    nom = "projet_demo_rush_01_25fps"
    replie = ligne_du_lot(nom, MENTION_ECRIT, utile, True)
    riche = ligne_du_lot(nom, MENTION_ECRIT, utile, False)

    assert replie.isascii(), replie
    assert replie.rstrip().endswith(jetons.replier_ascii(MENTION_ECRIT))
    assert MENTION_ECRIT not in replie, replie
    assert riche.rstrip().endswith(MENTION_ECRIT), riche
    assert not riche.isascii(), (
        "volet symetrique : hors ASCII la mention garde son accent, sans quoi "
        "ce banc serait vert sur un repli applique des DEUX cotes")


def test_le_zero_du_journal_DEPLIE_est_tenu_DEUX_fois_et_c_est_dit():
    """Mutant `M14` : **equivalent**, et il vaut mieux le dire que le chasser.

    Retirer la garde `if self.journal_deplie: return 0` ne change rien a
    l'observable, et ce n'est pas un trou du banc : quand le journal est
    deplie il prend `centre - 3` lignes, et la soustraction rend alors
    `centre - LIGNES_HORS_LOTS - (centre - 3)`, soit `3 - LIGNES_HORS_LOTS`,
    soit `-1`, que le plancher a zero ramene a zero. Les deux chemins rendent
    la meme valeur pour **toute** hauteur, le `centre` s'annulant.

    Aucun banc ne tuera donc ce mutant, et « zero survivant exige » ne peut pas
    s'y appliquer. Ce que ce test mesure a la place est la raison pour laquelle
    l'equivalence tient -- elle rougirait si `LIGNES_HORS_LOTS` descendait sous
    trois, c'est-a-dire le jour ou la garde cesserait d'etre equivalente et
    deviendrait la seule chose qui empeche la liste de manger le journal.
    """
    assert EcranExecution.LIGNES_HORS_LOTS >= 3, (
        "sous trois, la garde du journal deplie cesse d'etre redondante")
    for hauteur in (jetons.HAUTEUR_PLANCHER, 30, 40, 60):
        centre = jetons.hauteur_centrale(hauteur)
        assert centre - EcranExecution.LIGNES_HORS_LOTS - (centre - 3) <= 0, (
            hauteur, centre)
