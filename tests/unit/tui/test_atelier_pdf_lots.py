# -*- coding: utf-8 -*-
"""Story 11.7, lot D -- `E5-1`, la liste a cocher des lots de l'atelier Pdf.

Ce banc mesure l'AC 4 en entier : la liste a cocher (`EPIC11-ARB-10` pt 1), le
filet du lot survole, le refus de valider a vide, le double compte RETIRE, et
les deux frontieres negatives qui gardent l'ecran de reprendre ce qu'Egan en a
fait retirer.

**La regle des fabriques s'applique partout ici** (`CLAUDE.md`, points 1, 2 et
2 bis) : les corpus portent **trois** lots au moins, aux cardinaux, aux dates et
aux verdicts **tous differents**, et le lot vise est **au milieu** -- ni en
premier, ce qui laisserait vivre un `find` qui rend toujours le premier element,
ni en dernier, ce qui laisserait vivre un `continue` -> `break` qui arrete la
passe au premier ecart. La position se verifie sur la liste que le CODE
parcourt, `ListeDeLots.lots`.

**Ce que la maquette a cesse de porter, et c'est mesure en frontiere
negative.** Retour d'Egan du 2026-09-02, verbatim : « Enlevons-juste geometrie
et cadence. La cadence ne joue pas sur une planche c'est le lot qui la
determine. La geometrie n'est pas reglable on ne l'affiche pas. C'est le nombre
de frames [...] qui nous interesse. » Deux tests le tiennent -- l'un sur le
corps compose, l'autre sur la maquette elle-meme --, parce qu'une AC de
frontiere negative qui ne mesurerait que le code laisserait la maquette
diverger, et reciproquement.
"""
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.io import extraction_manifest, naming
from mixed_media_utility.tui import atelier_pdf_lots as lots_pdf
from mixed_media_utility.tui import jetons, projet_lecture
from mixed_media_utility.tui.coque import Contexte, CoqueTui, Palier, PalierTemoin

RACINE = Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
MAQUETTE = "E5-1-pdf-lots.txt"

#: Les cinq lots de la demonstration, dans l'ordre de `E5-1`, avec le cardinal
#: que la maquette leur donne. Les deux coches sont le premier et le TROISIEME
#: -- ce que la maquette montre --, et leurs cardinaux somment le `164 frames`
#: de sa ligne d'etat.
LOTS_DE_LA_MAQUETTE = (
    ("plan-04_25", 124, True),
    ("plan-04_12p5", 62, False),
    ("plan-04_8", 40, True),
    ("hiver_24", 31, False),
    ("sequence-12-atelier-fonderie-prise-3_12p5", 18, False),
)

#: La date d'extraction de la demonstration, dans l'ecriture du coeur.
QUAND = "2026-08-26T09:12:00Z"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def lignes_de_maquette(premiere: int, derniere: int) -> list[str]:
    """Les lignes utiles de `E5-1`, cadre et marges retires."""
    lignes = (MAQUETTES / MAQUETTE).read_text(encoding="utf-8").splitlines()
    return [ligne[2:-2].rstrip() for ligne in lignes[premiere:derniere]]


def liste_de_la_maquette() -> lots_pdf.ListeDeLots:
    return lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot(lot_id=nom, frames=frames, extrait_le=QUAND, coche=coche)
        for nom, frames, coche in LOTS_DE_LA_MAQUETTE])


def trois_lots(**kwargs) -> lots_pdf.ListeDeLots:
    """TROIS lots distinguables, et **la cible au milieu**.

    Cardinaux, dates et verdicts sont tous differents : un appariement inverse
    entre la ligne affichee et le lot qu'elle decrit se verrait, ce qu'un
    remplissage uniforme cacherait (mutant `M33` de la story 5.6). Le lot vise
    par les tests est `du_milieu`, en seconde position sur trois -- donc ni
    premier ni dernier (`CLAUDE.md`, point 2 bis).
    """
    defauts = dict(lots=[
        lots_pdf.Lot(lot_id="en_tete_25", frames=124,
                     extrait_le="2026-08-24T08:00:00Z"),
        lots_pdf.Lot(lot_id="du_milieu_12p5", frames=62,
                     extrait_le="2026-08-26T09:12:00Z",
                     verdict=lots_pdf.VERDICT_NON_CONFORME),
        lots_pdf.Lot(lot_id="en_queue_8", frames=40,
                     extrait_le="2026-08-28T17:30:00Z"),
    ])
    defauts.update(kwargs)
    return lots_pdf.ListeDeLots(**defauts)


def manifeste(nombre_de_lots: int = 3) -> dict:
    """Un manifest **deja charge**, trois rushes et trois lots distinguables.

    Les trois lots viennent de trois rushes de **geometries differentes** :
    c'est ce que l'AC 4.5 exige de pouvoir cocher ensemble, et c'est aussi ce
    qui empeche une fabrique mono-rush de rendre invisible un appariement
    lot/rush errone.
    """
    geometries = ({"width": 1920, "height": 1080},
                  {"width": 4096, "height": 2160},
                  {"width": 720, "height": 576})
    cardinaux = (124, 62, 40)
    quand = ("2026-08-24T08:00:00Z", "2026-08-26T09:12:00Z",
             "2026-08-28T17:30:00Z")
    noms = ("en_tete_25", "du_milieu_12p5", "en_queue_8")
    return {
        "rushes": [{"rush_id": f"rush_{rang}", "resolution_source": geometrie}
                   for rang, geometrie in enumerate(geometries[:nombre_de_lots])],
        "lots": [{"lot_id": noms[rang], "rush_id": f"rush_{rang}",
                  "state": "extraction",
                  "expected_frame_count": cardinaux[rang],
                  "confirmation": {"mode": "auto", "confirmed_at": quand[rang]}}
                 for rang in range(nombre_de_lots)],
    }


class Reception:
    """Un double de l'appelant, qui COMPTE ce qu'il recoit."""

    def __init__(self) -> None:
        self.appels: list[lots_pdf.Validation] = []

    def __call__(self, validation) -> None:
        self.appels.append(validation)


def ecran(liste=None, **kwargs) -> lots_pdf.EcranLotsAPlanches:
    return lots_pdf.EcranLotsAPlanches(
        liste if liste is not None else liste_de_la_maquette(), **kwargs)


def coque(un_ecran) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "Q quitter"),
                             PalierTemoin("Ateliers", "Q quitter"), un_ecran],
                    contexte=Contexte("projet_demo"))


def peint(un_ecran, identifiant, banc, ascii_seul=False):
    """Le contenu PEINT de l'ecran, monte sur le banc."""
    application = coque(un_ecran)
    application.ascii_seul = ascii_seul

    async def scenario(pilote):
        pilote.app.descendre(un_ecran)
        await pilote.pause()
        return pilote.app.screen.query_one(identifiant).content

    return banc(application, scenario)


def corps(un_ecran, ascii_seul: bool = False) -> list[str]:
    return [ligne.rstrip()
            for ligne in un_ecran.composer(80, ascii_seul)[0]]


# ---------------------------------------------------------------------------
# `E5-1` confronte a sa maquette (D1, D3)
# ---------------------------------------------------------------------------

def test_le_corps_de_E5_1_est_CELUI_DE_LA_MAQUETTE():
    """La maquette fait foi sur le texte ET sur les colonnes.

    Les douze lignes vont du blanc de tete a la ligne du lot survole ; ce qui
    suit dans la zone centrale est du vide que `textual` remplit.
    """
    assert corps(ecran()) == lignes_de_maquette(3, 15)


def test_la_ligne_d_etat_de_E5_1_est_celle_de_la_maquette():
    """`2 lots cochés · 164 frames`, et les 164 sont une SOMME, pas un litteral."""
    attendue = lignes_de_maquette(21, 22)[0]
    assert ecran().ligne_d_etat(False) == attendue
    somme = sum(frames for _nom, frames, coche in LOTS_DE_LA_MAQUETTE if coche)
    assert str(somme) in attendue


def test_la_ligne_de_raccourcis_est_celle_de_la_maquette():
    assert lots_pdf.RACCOURCIS_LOTS == lignes_de_maquette(22, 23)[0]


def test_le_bandeau_est_celui_de_la_maquette(banc):
    """`mmu · projet_demo · Pdf` -- un bandeau NU, sans objet travaille."""
    un_ecran = ecran()

    async def scenario(pilote):
        pilote.app.descendre(un_ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#bandeau").content)

    assert banc(coque(un_ecran), scenario).rstrip() == lignes_de_maquette(1, 2)[0]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E5_1_tient_la_grille_dans_LES_DEUX_regimes(ascii_seul):
    un_ecran = ecran()
    lignes = un_ecran.composer(80, ascii_seul)[0]
    for ligne in lignes + [un_ecran.ligne_d_etat(ascii_seul),
                           lots_pdf.RACCOURCIS_LOTS if not ascii_seul
                           else jetons.replier_ascii(lots_pdf.RACCOURCIS_LOTS)]:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        if ascii_seul:
            assert ligne.isascii(), ligne
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER


def test_l_ecran_monte_peint_la_ligne_du_curseur_et_les_etats(banc):
    """Le rang du curseur et les etats sont DONNES a `peindre`, jamais devines.

    On mesure le rendu peint : une couleur qui ne serait pas posee ne se verrait
    dans aucune assertion de texte.
    """
    liste = trois_lots()
    liste.deplacer(1)
    contenu = peint(ecran(liste), f"#{lots_pdf.EcranLotsAPlanches.ID_DU_CORPS}",
                    banc)
    lignes = contenu.split("\n")

    def teintes(jeton):
        couleur = jetons.couleur(jeton)
        return [rang for rang, ligne in enumerate(lignes)
                if ligne.spans and couleur in str(ligne.spans[0].style)]

    # Le curseur est sur le lot du MILIEU, qui est aussi le seul non conforme :
    # `peindre` fait passer l'accentuation devant l'etat, donc la ligne
    # accentuee est UNE, et les deux lignes vertes sont ses voisines.
    assert len(teintes("accent")) == 1, [ligne.plain for ligne in lignes]
    assert liste.lots[1].lot_id in lignes[teintes("accent")[0]].plain
    assert len(teintes("state-complete")) == 2, [l.plain for l in lignes]
    assert teintes("state-absent") == []


# ---------------------------------------------------------------------------
# La liste a cocher : `EPIC11-ARB-10` pt 1, `-45` / `-126` (D1)
# ---------------------------------------------------------------------------

def test_la_ligne_de_raccourcis_porte_LES_DEUX_la_case_ET_la_fleche():
    """`EPIC11-ARB-45` / `-126`, verbatim : « **Flèche seule !** C'est
    uniquement dans les listes a cocher qu'on trouve les deux. »

    Cet ecran EST une liste a cocher : il porte donc `Espace` **et** `↑↓`, et
    ses lignes portent une case. Le volet symetrique est mesure sur le rendu :
    une ligne sans case passerait ce test-ci sur la seule ligne de raccourcis.
    """
    assert "Espace" in lots_pdf.RACCOURCIS_LOTS
    assert "↑↓" in lots_pdf.RACCOURCIS_LOTS
    table = jetons.glyphes(False)
    lignes = liste_de_la_maquette().lignes_de_liste()
    assert all(table["coche"] in ligne or table["decoche"] in ligne
               for ligne in lignes[:len(LOTS_DE_LA_MAQUETTE)])
    assert table["curseur"] in lignes[0]


def test_espace_bascule_LE_LOT_SOUS_LE_CURSEUR_et_lui_seul():
    """La cible est **au milieu** des trois : un `basculer` qui viserait
    toujours le premier -- ou toujours le dernier -- se demasque ici, et nulle
    part ailleurs."""
    liste = trois_lots()
    liste.deplacer(1)
    assert liste.courant.lot_id == "du_milieu_12p5"
    liste.basculer()
    assert {lot.lot_id for lot in liste.coches} == {"du_milieu_12p5"}
    liste.basculer()
    assert liste.coches == ()


def test_l_ensemble_des_coches_apres_une_sequence_est_EXACTEMENT_celui_attendu():
    """AC 4.8 -- **exactement**, jamais « contient ».

    La sequence coche le premier et le dernier et laisse celui du milieu : une
    boucle de bascule qui deborderait sur son voisin se verrait, ce qu'une
    sequence a un seul coche ne dirait pas.
    """
    liste = trois_lots()
    un_ecran = ecran(liste)
    un_ecran.traiter("space")
    un_ecran.traiter("down")
    un_ecran.traiter("down")
    un_ecran.traiter("space")
    assert {lot.lot_id for lot in liste.coches} == {"en_tete_25", "en_queue_8"}
    assert liste.frames_cochees == 124 + 40


def test_les_fleches_ne_sortent_JAMAIS_de_la_liste():
    liste = trois_lots()
    for _ in range(5):
        liste.deplacer(-1)
    assert liste.curseur == 0
    for _ in range(9):
        liste.deplacer(1)
    assert liste.curseur == len(liste) - 1


def test_viser_un_lot_inconnu_NOMME_ce_qui_existe():
    liste = trois_lots()
    assert liste.viser("du_milieu_12p5").frames == 62
    with pytest.raises(lots_pdf.LotsMalFormes) as refus:
        liste.viser("jamais_extrait")
    assert "du_milieu_12p5" in str(refus.value)


def test_le_rang_d_un_lot_ne_rend_pas_le_PREMIER():
    """Mutant `M25` de la story 5.7, transpose : un `find` qui rendrait
    toujours la premiere entree reste vert sur toute fixture ou la cible est en
    tete."""
    liste = trois_lots()
    assert liste.rang("du_milieu_12p5") == 1
    assert liste.rang("en_queue_8") == 2
    assert liste.rang("jamais_extrait") is None


def test_deux_lots_du_meme_nom_sont_refuses_A_LA_CONSTRUCTION():
    with pytest.raises(lots_pdf.LotsMalFormes):
        lots_pdf.ListeDeLots(lots=[lots_pdf.Lot("plan-04_25", 124),
                                   lots_pdf.Lot("plan-04_12p5", 62),
                                   lots_pdf.Lot("plan-04_25", 40)])


def test_une_liste_vide_est_refusee_NOMMEMENT():
    with pytest.raises(lots_pdf.LotsMalFormes) as refus:
        lots_pdf.ListeDeLots(lots=[])
    assert "au moins un lot" in str(refus.value)


# ---------------------------------------------------------------------------
# La validation a zero coche (D2, AC 4.3)
# ---------------------------------------------------------------------------

def test_valider_a_ZERO_coche_ne_passe_PAS_en_silence():
    """AC 4.3 : le motif est dit, l'ecran reste monte, l'appelant n'est PAS
    appele. Les trois se mesurent ensemble : un refus qui dirait le motif et
    continuerait quand meme serait pire que pas de refus du tout."""
    liste = trois_lots()
    recu = Reception()
    un_ecran = ecran(liste, continuer=recu)
    assert un_ecran.traiter("enter") is True
    assert recu.appels == []
    assert lots_pdf.MOTIF_AUCUN_LOT_COCHE in un_ecran.ligne_d_etat(False)
    assert un_ecran.ligne_d_etat(False).startswith(jetons.glyphes(False)["absent"])


def test_le_refus_de_valider_a_vide_est_celui_des_CADENCES_transpose():
    """AC 4.3, verbatim de la fiche : « c'est litteralement
    `cadences.MOTIF_AUCUNE_COCHEE` transpose ». La forme est mesuree -- meme
    entete de refus, meme geste suivant nomme -- plutot que decrite."""
    from mixed_media_utility.tui import cadences

    assert cadences.MOTIF_AUCUNE_COCHEE.startswith("Refuse : aucune")
    assert lots_pdf.MOTIF_AUCUN_LOT_COCHE.startswith("Refuse : aucun lot")
    assert lots_pdf.MOTIF_AUCUN_LOT_COCHE.endswith(".")


def test_valider_AVEC_des_coches_passe_et_rend_EXACTEMENT_les_coches():
    """Volet symetrique du precedent : sans lui, un `valider` qui refuserait
    toujours passerait le test du refus."""
    liste = trois_lots()
    recu = Reception()
    un_ecran = ecran(liste, continuer=recu)
    un_ecran.traiter("down")
    un_ecran.traiter("space")
    un_ecran.traiter("down")
    un_ecran.traiter("space")
    un_ecran.traiter("enter")
    assert len(recu.appels) == 1
    validation = recu.appels[0]
    assert validation.passe
    assert {lot.lot_id for lot in validation.coches} == {"du_milieu_12p5",
                                                         "en_queue_8"}


def test_valider_SANS_appelant_ne_se_TAIT_pas(banc):
    """La garde structurelle des rappels, tenue sur place.

    « Une touche qui ne fait rien et ne dit rien est indistinguable d'un
    clavier casse » : tant que le parcours Pdf n'injecte pas `continuer`, `⏎`
    sur une liste cochee descend sur un ecran qui NOMME ce qui manque et
    quand il arrive. Le volet symetrique est le test precedent : avec un
    appelant, l'ecran ne descend nulle part de lui-meme.
    """
    liste = trois_lots()
    liste.lots[1].coche = True
    un_ecran = ecran(liste)
    application = coque(un_ecran)

    async def scenario(pilote):
        pilote.app.descendre(un_ecran)
        await pilote.pause()
        await pilote.press("enter")
        await pilote.pause()
        sommet = pilote.app.screen
        return (type(sommet).__name__, getattr(sommet, "ce_qui_manque", None),
                getattr(sommet, "quand", None))

    nom, manque, quand = banc(application, scenario)
    assert nom == "EcranPasEncore"
    assert manque == lots_pdf.CE_QUI_MANQUE_APRES_LES_LOTS
    assert quand == lots_pdf.QUAND_LES_REGLAGES


def test_l_ecran_reste_monte_apres_un_refus(banc):
    """« aucun ecran ne se demonte » : mesure sur la PILE, pas sur une intention."""
    un_ecran = ecran(trois_lots())
    application = coque(un_ecran)

    async def scenario(pilote):
        pilote.app.descendre(un_ecran)
        await pilote.pause()
        avant = len(pilote.app.screen_stack)
        await pilote.press("enter")
        await pilote.pause()
        return avant, len(pilote.app.screen_stack), pilote.app.screen is un_ecran

    avant, apres, au_sommet = banc(application, scenario)
    assert (avant, au_sommet) == (apres, True)


def test_la_mesure_revient_des_qu_on_rejoue_une_touche():
    """Un refus tient le temps d'un geste, pas au-dela : sinon la ligne d'etat
    mentirait sur le compte des le coche suivant."""
    un_ecran = ecran(trois_lots())
    un_ecran.traiter("enter")
    assert lots_pdf.MOTIF_AUCUN_LOT_COCHE in un_ecran.ligne_d_etat(False)
    un_ecran.traiter("space")
    assert un_ecran.ligne_d_etat(False) == "1 lot coché · 124 frames"


# ---------------------------------------------------------------------------
# Le filet « Le lot survolé » (D3, AC 4.2) et le retour d'Egan du 2026-09-02
# ---------------------------------------------------------------------------

def test_le_filet_decrit_le_lot_SOUS_LE_CURSEUR_pas_le_premier():
    """L'appariement de cet ecran, et la cible est **au milieu**.

    Les trois lots ont trois cardinaux et trois dates differents : un filet
    cale sur le premier lot, sur le dernier, ou sur un rang decale d'une unite
    rend trois lignes distinctes -- ce qu'un remplissage uniforme rendrait
    indiscernables.
    """
    liste = trois_lots()
    liste.deplacer(1)
    ligne = liste.ligne_du_survol()
    assert "62" in ligne and "26/08" in ligne
    assert "124" not in ligne and "40" not in ligne
    assert "24/08" not in ligne and "28/08" not in ligne


def test_le_cardinal_du_filet_n_est_PAS_le_total_des_coches():
    """La parenthese d'Egan (« c'est un total ? »), mesuree.

    Le curseur est sur un lot NON coche, et les deux autres sont coches : le
    filet dit `62`, la ligne d'etat dit `164`. Une fabrique ou le survole
    serait aussi coche ne separerait pas les deux nombres.
    """
    liste = trois_lots()
    liste.lots[0].coche = True
    liste.lots[2].coche = True
    liste.deplacer(1)
    un_ecran = ecran(liste)
    assert "62" in liste.ligne_du_survol()
    assert un_ecran.ligne_d_etat(False) == "2 lots cochés · 164 frames"


@pytest.mark.parametrize("mot", ["Cadence", "cadence", "Géométrie",
                                 "Geometrie", "×", "fps"])
@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_filet_ne_porte_NI_cadence_NI_geometrie(mot, ascii_seul):
    """Frontiere NEGATIVE du retour d'Egan du 2026-09-02.

    « La cadence ne joue pas sur une planche c'est le lot qui la determine. La
    geometrie n'est pas reglable on ne l'affiche pas. » Un grep du corps
    compose rend **zero** occurrence, dans les deux regimes -- y compris du
    signe de multiplication d'une resolution.
    """
    liste = trois_lots()
    liste.deplacer(1)
    for ligne in corps(ecran(liste), ascii_seul):
        assert mot not in ligne, ligne


@pytest.mark.parametrize("mot", ["Cadence", "Géométrie"])
def test_la_MAQUETTE_non_plus_ne_porte_ni_cadence_ni_geometrie(mot):
    """Volet symetrique du precedent, pose sur le dessin.

    « C'est le dessin qui fait foi, pas l'outil » : une frontiere qui ne
    mesurerait que le code laisserait la maquette reintroduire les deux lignes
    au prochain passage de son generateur, et le banc d'ecran deviendrait rouge
    sans que personne sache pourquoi.
    """
    dessin = (MAQUETTES / MAQUETTE).read_text(encoding="utf-8")
    bloc = dessin.split(lots_pdf.FILET_DU_SURVOL, 1)[1].split("├", 1)[0]
    assert mot not in bloc, bloc


def test_le_filet_porte_le_cardinal_ET_la_date_du_manifest():
    """Volet symetrique des deux frontieres negatives : sans lui, un filet vide
    les passerait toutes les deux."""
    liste = trois_lots()
    liste.deplacer(1)
    ligne = liste.ligne_du_survol()
    assert lots_pdf.LIBELLE_DES_FRAMES in ligne
    assert ligne.endswith("extraites le 26/08")


def test_un_lot_SANS_date_de_confirmation_ne_ment_pas():
    """Un lot venu du scan ne porte pas de `confirmation` : la mention
    disparait, elle ne s'invente pas et elle ne devient pas une date fausse."""
    liste = lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot("en_tete_25", 124, extrait_le="2026-08-24T08:00:00Z"),
        lots_pdf.Lot("du_milieu_12p5", 62, extrait_le=None),
        lots_pdf.Lot("en_queue_8", 40, extrait_le="2026-08-28T17:30:00Z"),
    ])
    liste.deplacer(1)
    ligne = liste.ligne_du_survol()
    assert ligne.rstrip().endswith("62")
    assert "extraites" not in ligne


def test_une_date_illisible_se_montre_TELLE_QUELLE():
    """Meme repli que `projet_lecture.date_lisible` : « un format inattendu se
    montre plutot que de disparaitre »."""
    assert projet_lecture.date_courte("2026-08-26T09:12:00Z") == "26/08"
    assert projet_lecture.date_courte("hier") == "hier"
    liste = lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot("en_tete_25", 124),
        lots_pdf.Lot("du_milieu_12p5", 62, extrait_le="hier"),
        lots_pdf.Lot("en_queue_8", 40)])
    liste.deplacer(1)
    assert "extraites le hier" in liste.ligne_du_survol()


def test_les_deux_dates_courtes_lisent_les_MEMES_horodatages():
    """`date_courte` et `date_lisible` partagent leur table de motifs : deux
    tables divergeraient, et l'une des surfaces cesserait de lire une date que
    l'autre lit."""
    for horodatage in ("2026-08-26T09:12:00Z", "2026-08-26T09:12:00+0000",
                       "2026-08-26T09:12:00.500000Z"):
        assert projet_lecture.date_courte(horodatage) == "26/08", horodatage
        assert projet_lecture.date_lisible(horodatage).startswith("26/08")


# ---------------------------------------------------------------------------
# Le double compte RETIRE (D4, AC 4.6)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("coches", [0, 1, 2, 3])
@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_corps_ne_porte_AUCUN_second_compte_de_coches(coches, ascii_seul):
    """AC 4.6 -- frontiere a ZERO, note 4 d'Egan du 2026-09-01 : « Laisse juste
    la mention du bas [...] toujours en double ».

    Mesuree dans les quatre etats de cochage et dans les deux regimes : un
    compte qui ne s'afficherait qu'a partir de deux coches passerait une mesure
    faite sur le seul etat de la maquette.
    """
    liste = trois_lots()
    for rang in range(coches):
        liste.lots[rang].coche = True
    motif = re.compile(r"coch|sur \d+ lots?\b")
    for ligne in corps(ecran(liste), ascii_seul):
        assert not motif.search(ligne), ligne


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_LIGNE_D_ETAT_porte_le_compte_elle(ascii_seul):
    """Volet symetrique : sans lui, un ecran qui ne compterait NULLE PART
    passerait la frontiere ci-dessus."""
    liste = trois_lots()
    liste.lots[1].coche = True
    etat = ecran(liste).ligne_d_etat(ascii_seul)
    assert "62 frames" in etat
    assert ("coché" if not ascii_seul else "coche") in etat


def test_le_compte_de_la_ligne_d_etat_s_ACCORDE():
    """`0 lot coché · 0 frame`, `1 lot coché · 124 frames`, `2 lots cochés`.

    L'accord du mot `lot` passe par `projet_lecture.accorder` -- la table du
    depot --, jamais par un `+ "s"` local.
    """
    liste = trois_lots()
    un_ecran = ecran(liste)
    assert un_ecran.ligne_d_etat(False) == "0 lot coché · 0 frame"
    liste.lots[0].coche = True
    assert un_ecran.ligne_d_etat(False) == "1 lot coché · 124 frames"
    liste.lots[1].coche = True
    assert un_ecran.ligne_d_etat(False) == "2 lots cochés · 186 frames"
    assert liste.ligne_de_compte(False).startswith(
        projet_lecture.accorder(2, "lot"))


def test_la_ligne_d_etat_ne_porte_AUCUNE_touche(banc):
    """`EPIC11-ARB-56` : aucune touche, aucun conseil d'usage, aucun motif de
    conception en ligne d'etat."""
    liste = trois_lots()
    liste.lots[1].coche = True
    un_ecran = ecran(liste)
    for ascii_seul in (False, True):
        etat = un_ecran.ligne_d_etat(ascii_seul)
        for touche in ("Espace", "⏎", "Échap", "Echap", "F1", "↑↓", "Tab"):
            assert touche not in etat, (etat, touche)


# ---------------------------------------------------------------------------
# La colonne des noms, lue du COEUR (AC 4.1, note 1 d'Egan)
# ---------------------------------------------------------------------------

def test_la_colonne_des_noms_est_CELLE_DU_COEUR_et_pas_celle_de_la_demo():
    """Note 1 d'Egan : « les noms sont bien plus longs dans mes projets ».

    La colonne se lit de `io.naming.CANONICAL_ID_MAX_LENGTH`, et le module ne
    recopie pas sa valeur -- un litteral y serait une seconde source de verite,
    qui divergerait au prochain arbitrage sur la falaise QR (la borne a valu
    48, puis 64, puis 48).
    """
    assert lots_pdf.LARGEUR_DU_NOM == naming.CANONICAL_ID_MAX_LENGTH
    source = (Path(lots_pdf.__file__)).read_text(encoding="utf-8")
    assert str(naming.CANONICAL_ID_MAX_LENGTH) not in re.sub(
        r"^\s*#.*$", "", source, flags=re.M)
    plus_long = max(len(nom) for nom, _f, _c in LOTS_DE_LA_MAQUETTE)
    assert lots_pdf.LARGEUR_DU_NOM > plus_long


def test_un_nom_de_LONGUEUR_MAXIMALE_ne_colle_pas_son_etat():
    """L'ecart mesure entre la maquette et ce que le produit peut rendre.

    La maquette pose l'etat immediatement apres un champ de nom de la longueur
    maximale du produit : un lot nomme sur exactement
    `CANONICAL_ID_MAX_LENGTH` caracteres y ecrirait `..._12p5● complet`. Le
    creux est donc pris sur le NOM, ce qui garde les colonnes de la maquette
    tout en tenant le pire cas. Le nom reste reconnaissable par ses DEUX bouts.
    """
    nom = "z" * naming.CANONICAL_ID_MAX_LENGTH
    liste = lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot("en_tete_25", 124),
        lots_pdf.Lot(nom, 62),
        lots_pdf.Lot("en_queue_8", 40)])
    ligne = liste.ligne(1)
    marque = jetons.marque(lots_pdf.ETAT_CONFORME, lots_pdf.MENTION_CONFORME)
    assert marque in ligne
    avant = ligne.split(marque)[0]
    assert avant.endswith(" " * jetons.CREUX_MINIMAL), repr(ligne)
    # La colonne de l'etat ne bouge pas d'un lot a l'autre : c'est ce qui rend
    # la colonne lisible, et c'est la mesure de la maquette.
    assert (jetons.colonnes(avant)
            == jetons.colonnes(liste.ligne(0).split(marque)[0]))


def test_un_nom_trop_long_s_abrege_AU_MILIEU_et_garde_son_suffixe():
    """Deux lots d'un meme rush ne se distinguent QUE par leur suffixe : une
    elision par la fin les rendrait identiques a l'ecran, c'est-a-dire le
    risque R12 remonte au niveau de l'affichage."""
    prefixe = "sequence-12-atelier-fonderie-prise-3-bis-longue"
    liste = lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot("en_tete_25", 124),
        lots_pdf.Lot(f"{prefixe}_25", 62),
        lots_pdf.Lot(f"{prefixe}_12p5", 40)])
    du_milieu, en_queue = liste.ligne(1), liste.ligne(2)
    assert du_milieu != en_queue
    assert "_25" in du_milieu and "_12p5" in en_queue
    assert jetons.points_d_abregement(False) in du_milieu


# ---------------------------------------------------------------------------
# Le verdict du coeur, AFFICHE et jamais rejoue (AC 4.4)
# ---------------------------------------------------------------------------

def test_un_lot_NON_CONFORME_reste_cochable_avec_son_glyphe():
    """AC 4.4 : « un lot non conforme reste cochable, avec son glyphe ». La
    cible est **au milieu** des trois."""
    liste = trois_lots()
    liste.deplacer(1)
    assert liste.courant.verdict is lots_pdf.VERDICT_NON_CONFORME
    assert liste.courant.cochable
    liste.basculer()
    assert {lot.lot_id for lot in liste.coches} == {"du_milieu_12p5"}
    ligne = liste.ligne(1)
    assert jetons.glyphes(False)["absent"] in ligne
    assert lots_pdf.MENTION_NON_CONFORME in ligne


def test_les_etats_de_ligne_suivent_le_lot_et_pas_le_rang():
    """L'appariement ligne / verdict, mesure en ensemble EXACT.

    Le seul lot non conforme est au MILIEU : un decalage d'un rang, dans un
    sens ou dans l'autre, peint la mauvaise ligne et se voit ici.
    """
    liste = trois_lots()
    assert liste.etats_des_lignes() == {
        0: lots_pdf.ETAT_CONFORME,
        1: lots_pdf.ETAT_NON_CONFORME,
        2: lots_pdf.ETAT_CONFORME,
    }


def test_les_etats_suivent_la_FENETRE_quand_la_liste_defile():
    """Le survivant `M04` de la campagne, ferme.

    Tant que la fenetre commence au rang zero, `decalage + (rang - premier)`
    et `rang` rendent la meme table : un etat indexe sur le rang ABSOLU passait
    donc toute la mesure. Des que la liste defile, il peint la mauvaise ligne
    -- et `jetons.peindre` refuse meme un rang hors bornes, ce qui fait tomber
    l'ecran plutot que de le mal peindre.

    Neuf lots, le NON CONFORME au milieu de la fenetre finale : ni sur la
    premiere ligne visible, ni sur la derniere.
    """
    lots = [lots_pdf.Lot(f"lot_{rang:02d}", 10 + rang) for rang in range(9)]
    lots[6].verdict = lots_pdf.VERDICT_NON_CONFORME
    liste = lots_pdf.ListeDeLots(lots=lots)
    liste.viser("lot_08")
    lignes = liste.lignes_de_liste()
    etats = liste.etats_des_lignes()
    assert set(etats) <= set(range(len(lignes))), (etats, lignes)
    rouges = [rang for rang, nom in etats.items()
              if nom == lots_pdf.ETAT_NON_CONFORME]
    assert len(rouges) == 1, etats
    assert "lot_06" in lignes[rouges[0]], (rouges, lignes)
    assert 0 < rouges[0] < len(lignes) - 1, (rouges, lignes)


@pytest.mark.parametrize("declare,attendu", [
    (124, 124), (0, 0), (-3, 0), (None, 0), ("beaucoup", 0), (True, 0),
])
def test_un_cardinal_ABIME_vaut_zero_et_ne_fait_pas_tomber_l_ecran(declare,
                                                                   attendu):
    """Le survivant `M35`, ferme -- et son motif etait un mutant EQUIVALENT.

    La redaction d'origine (`cardinal >= 0 else 0`) rendait zero des deux cotes
    de la borne : `>= 0` et `> 0` y etaient indiscernables, et aucun test ne
    pouvait les separer. Le repli est desormais ecrit une fois
    (`_cardinal_declare`), ou la borne est un `max` -- que la table ci-dessus
    separe d'un `min`.

    `True` a sa ligne parce que c'est le cas qui ne se voit pas : `True` est un
    `int`, et sans la garde un `"expected_frame_count": true` rendrait un lot
    d'UNE frame, valeur parfaitement plausible.
    """
    document = manifeste()
    if declare is None:
        document["lots"][1].pop("expected_frame_count")
    else:
        document["lots"][1]["expected_frame_count"] = declare
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(document)
    assert liste.viser("du_milieu_12p5").frames == attendu
    assert [lot.lot_id for lot in liste.lots] == [
        "en_tete_25", "du_milieu_12p5", "en_queue_8"]


def test_le_verdict_lit_ok_du_coeur_et_JAMAIS_ses_findings():
    """`LotVerification.ok` est la propriete par laquelle le COEUR juge.

    Le cas qui separe les deux lectures : une verification qui porte un constat
    **informatif** a `findings` non vide et `ok` vrai. Un verdict ecrit
    `not findings` y declarerait un lot conforme non conforme, et aucun test
    ecrit sur un `findings` vide ne le verrait.
    """
    def verification(findings):
        return extraction_manifest.LotVerification(
            lot_id="du_milieu_12p5", frames_dir=None, expected_frame_count=62,
            observed_frame_count=62, missing_frames=(), unexpected_files=(),
            nonconforming_files=(), selection_recomputed=False,
            digest_matches=None, findings=findings)

    informatif = extraction_manifest.INFORMATIONAL_VERIFICATION_CODES[0]
    assert lots_pdf.verdict_du_coeur(verification(())) is lots_pdf.VERDICT_CONFORME
    assert lots_pdf.verdict_du_coeur(
        verification((informatif,))) is lots_pdf.VERDICT_CONFORME
    assert lots_pdf.verdict_du_coeur(verification(
        (extraction_manifest.VERIFY_LOT_ABSENT,))) is lots_pdf.VERDICT_NON_CONFORME


def test_le_verdict_vient_du_VRAI_verify_extracted_lot(tmp_path):
    """Contre le vrai producteur, pas contre un double : un double aurait son
    propre `ok`, donc sa propre frontiere."""
    document = manifeste()
    reel = extraction_manifest.verify_extracted_lot(
        tmp_path, document, "jamais_extrait")
    assert lots_pdf.verdict_du_coeur(reel) is lots_pdf.VERDICT_NON_CONFORME
    assert extraction_manifest.VERIFY_LOT_ABSENT in reel.findings


def test_un_etat_inconnu_est_refuse_A_LA_CONSTRUCTION():
    """Un jeton mal orthographie rendrait une surface silencieusement hors
    charte : `jetons.peindre` leve deja, et le refus est pris plus tot."""
    with pytest.raises(lots_pdf.LotsMalFormes):
        lots_pdf.Verdict(etat="vert", mention="complet")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_les_deux_verdicts_restent_DISTINCTS_en_repli_ascii(ascii_seul):
    """Le second canal de `DESIGN.md` section 6 : deux etats distincts rendent
    deux chaines distinctes, meme sans couleur."""
    conforme = lots_pdf.VERDICT_CONFORME.rendu(ascii_seul)
    non_conforme = lots_pdf.VERDICT_NON_CONFORME.rendu(ascii_seul)
    assert conforme != non_conforme
    if ascii_seul:
        assert conforme.isascii() and non_conforme.isascii()


# ---------------------------------------------------------------------------
# Le manifest DEJA CHARGE (AC 4.2, AC 4.5, D5)
# ---------------------------------------------------------------------------

def test_l_ensemble_des_lots_LISTES_est_EXACTEMENT_celui_du_manifest():
    """AC 4.8, second volet : exactement, jamais « contient »."""
    document = manifeste()
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(document)
    assert [lot.lot_id for lot in liste.lots] == [
        entree["lot_id"] for entree in document["lots"]]
    assert [lot.frames for lot in liste.lots] == [124, 62, 40]


def test_le_cardinal_et_la_date_viennent_du_manifest_LOT_PAR_LOT():
    """L'appariement lot / valeurs, la cible **au milieu**.

    Les trois cardinaux et les trois dates sont distincts : un `depuis_le_
    manifeste` qui lirait toujours la premiere entree -- ou qui s'arreterait a
    la premiere -- se demasque ici.
    """
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(manifeste())
    du_milieu = liste.viser("du_milieu_12p5")
    assert (du_milieu.frames, du_milieu.extrait_le) == (62, "2026-08-26T09:12:00Z")
    assert "62" in liste.ligne_du_survol()
    assert len(liste) == 3


def test_les_verdicts_sont_indexes_par_NOM_et_jamais_par_rang():
    """« Deux listes qui doivent rester en correspondance sont deux occasions
    de les desapparier. »

    Le verdict est donne pour le lot du MILIEU seul : un `verdicts[rang]` --
    ou un `zip` -- le poserait sur le premier lot, et une fabrique a un seul
    verdict ne le dirait pas.
    """
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(
        manifeste(), verdicts={"du_milieu_12p5": lots_pdf.VERDICT_NON_CONFORME})
    assert {lot.lot_id for lot in liste.lots
            if lot.verdict is lots_pdf.VERDICT_NON_CONFORME} == {"du_milieu_12p5"}


def test_des_lots_de_GEOMETRIES_DIFFERENTES_sont_cochables_ENSEMBLE():
    """AC 4.5 : chaque lot a sa planche, ce n'est pas un refus.

    La fabrique porte trois rushes de trois geometries : la mesure serait vide
    sur un corpus mono-geometrie.
    """
    document = manifeste()
    geometries = {tuple(rush["resolution_source"].values())
                  for rush in document["rushes"]}
    assert len(geometries) == 3
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(document)
    un_ecran = ecran(liste)
    for _ in range(3):
        un_ecran.traiter("space")
        un_ecran.traiter("down")
    assert {lot.lot_id for lot in liste.coches} == {
        "en_tete_25", "du_milieu_12p5", "en_queue_8"}
    assert un_ecran.traiter("enter") is True
    assert lots_pdf.MOTIF_AUCUN_LOT_COCHE not in un_ecran.ligne_d_etat(False)


def test_un_manifest_ABIME_ne_fait_pas_tomber_l_ecran():
    """Un lot sans nom est saute, un cardinal absent vaut zero : « le menu doit
    s'ouvrir meme sur un projet dont le document est casse »."""
    document = manifeste()
    document["lots"].insert(1, {"rush_id": "rush_x"})
    document["lots"][2].pop("expected_frame_count")
    document["lots"][3].pop("confirmation")
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(document)
    assert [lot.lot_id for lot in liste.lots] == [
        "en_tete_25", "du_milieu_12p5", "en_queue_8"]
    assert liste.viser("du_milieu_12p5").frames == 0
    assert liste.viser("en_queue_8").extrait_le is None


def test_la_liste_ne_lit_RIEN_sur_le_disque():
    """AC 4.2 : « aucune seconde lecture, aucun `glob` sur le disque ».

    Trois volets, parce qu'aucun ne suffit seul :

    * **la frontiere de source** -- aucune des cinq portes d'acces au disque
      n'est ecrite dans le module ;
    * **la signature** -- `depuis_le_manifeste` ne prend AUCUN chemin, donc
      elle n'a rien a explorer ;
    * **le volet positif** -- tout ce que l'ecran montre suit le dictionnaire :
      un cardinal change dans le document change la ligne rendue, ce qu'une
      seconde lecture du disque ne ferait pas.
    """
    import inspect

    source = Path(lots_pdf.__file__).read_text(encoding="utf-8")
    for interdite in ("glob(", "iterdir(", "open(", "read_text(", "listdir("):
        assert interdite not in source, interdite
    parametres = inspect.signature(
        lots_pdf.ListeDeLots.depuis_le_manifeste).parameters
    assert set(parametres) == {"manifeste", "verdicts"}

    document = manifeste()
    document["lots"][1]["expected_frame_count"] = 999
    liste = lots_pdf.ListeDeLots.depuis_le_manifeste(document)
    liste.deplacer(1)
    assert "999" in liste.ligne_du_survol()


# ---------------------------------------------------------------------------
# La fenetre de la liste
# ---------------------------------------------------------------------------

def test_la_zone_de_liste_garde_SA_HAUTEUR_quel_que_soit_le_nombre_de_lots():
    """Le filet du survol ne danse pas : c'est ce qui rend la ligne du lot
    survole visable a l'oeil d'un projet a l'autre."""
    for nombre in (1, 2, 3, 5, 9):
        liste = lots_pdf.ListeDeLots(lots=[
            lots_pdf.Lot(f"lot_{rang:02d}", 10 + rang)
            for rang in range(nombre)])
        lignes = liste.lignes_de_liste()
        assert len(lignes) == lots_pdf.HAUTEUR_LISTE, nombre
        rendu = corps(ecran(liste))
        filet = [rang for rang, ligne in enumerate(rendu)
                 if lots_pdf.FILET_DU_SURVOL in ligne]
        assert filet == [9], (nombre, rendu)


def test_une_liste_plus_longue_que_la_fenetre_dit_OU_ON_EN_EST():
    """La ligne de position remplace la derniere ligne : la cible du test est
    le NEUVIEME lot, donc hors de la fenetre initiale."""
    liste = lots_pdf.ListeDeLots(lots=[
        lots_pdf.Lot(f"lot_{rang:02d}", 10 + rang) for rang in range(9)])
    lignes = liste.lignes_de_liste()
    assert "sur 9 lots" in lignes[-1]
    liste.viser("lot_08")
    lignes = liste.lignes_de_liste()
    assert lignes[0].strip() == jetons.points_d_abregement(False)
    assert "lot_08" in lignes[-1]
    assert liste.rang_du_curseur() == lots_pdf.HAUTEUR_LISTE - 1


def test_toutes_les_lignes_de_la_fenetre_sont_RENDUES():
    """Un `break` dans la boucle de rendu laisserait la zone a moitie vide, et
    une fabrique a deux lots ne le dirait pas : la cible est au MILIEU."""
    liste = trois_lots()
    lignes = liste.lignes_de_liste()
    assert [ligne for ligne in lignes if ligne] and len(lignes) == 5
    for rang, lot in enumerate(liste.lots):
        assert lot.lot_id in lignes[rang], (rang, lignes)
    assert lignes[3] == "" and lignes[4] == ""


def test_les_frames_cochees_sont_la_SOMME_de_TOUTES_les_cochees():
    """Un `break` au premier coche rendrait 124 au lieu de 164 : les trois
    cardinaux sont distincts et deux coches encadrent un non coche."""
    liste = trois_lots()
    liste.lots[0].coche = True
    liste.lots[2].coche = True
    assert liste.frames_cochees == 164
    assert liste.nombre_de_coches == 2


# ---------------------------------------------------------------------------
# Frontieres de paquet
# ---------------------------------------------------------------------------

def test_l_ecran_pdf_n_importe_JAMAIS_cli():
    """`EPIC11-ARB-67` : le point d'entree de coeur de cet atelier est
    `mixed_media_utility.makepdf`, jamais `cli.py`. La frontiere generale du
    paquet le mesure aussi ; celle-ci nomme le module de la story."""
    source = Path(lots_pdf.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:from|import)\s+\S+", source, flags=re.M)
    assert imports, "aucun import vu : la frontiere ne mesurerait rien"
    assert not [ligne for ligne in imports if "cli" in ligne], imports


def test_l_ecran_est_un_palier_du_paquet_avec_sa_ligne_de_raccourcis():
    """Volet symetrique des gardes de `test_repli_ascii.py` : sans lui, un
    ecran qui ne serait pas un `Palier` echapperait a toutes."""
    assert issubclass(lots_pdf.EcranLotsAPlanches, Palier)
    assert lots_pdf.EcranLotsAPlanches.raccourcis == lots_pdf.RACCOURCIS_LOTS
    assert lots_pdf.EcranLotsAPlanches.titre == projet_lecture.PDF
