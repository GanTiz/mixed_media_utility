# -*- coding: utf-8 -*-
"""Ce qui n'existe qu'une fois l'ecran monte ET en mouvement.

**C'est la ligne de partage que la revue de vague 1 a nommee** : tout ce qui
etait mesure en modele pur tenait, tout ce qui ne vivait qu'a l'ecran n'etait
pas mesure du tout. Les six sondes des couches 1 et 2 -- ecran monte, jalons qui
arrivent, fenetre qui change de taille, plancher franchi -- etaient rouges du
premier coup sur des tests par ailleurs verts.

Ce fichier existe pour que cette famille ait un domicile. Aucun test n'y appelle
`rafraichir()` a la main : **c'est le cablage qu'on mesure**, pas la methode.
"""

from pathlib import Path

import pytest
from textual.widgets import Static

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import CoqueTui, Contexte, PalierTemoin
from mixed_media_utility.tui.execution import (
    EcranExecution,
    EcranInterruption,
    PanneauConfirmation,
    SurfaceExecution,
)
from mixed_media_utility.tui.noms import ModeleNoms, NomEditable
from mixed_media_utility.tui.panneau import (
    RIEN_ECRIT,
    ChoixExclusif,
    Issue,
    LigneChiffree,
    Panneau,
)


class Horloge:
    """Horloge qu'on avance a la main : le temps ne passe pas en test."""

    def __init__(self) -> None:
        self.instant = 1000.0

    def __call__(self) -> float:
        return self.instant

    def avancer(self, secondes: float) -> None:
        self.instant += secondes


def coque(**kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def confirmation(**kwargs) -> PanneauConfirmation:
    return PanneauConfirmation(
        Panneau("A ecrire", [LigneChiffree("Frames ecrites", 186, "frames")]),
        ChoixExclusif([Issue("ecrire", "Extraire", ecrit=True),
                       Issue("annuler", "Annuler")]),
        ModeleNoms([NomEditable("projet_demo_rush_01_25fps"),
                    NomEditable("projet_demo_rush_01_12p5")]),
        **kwargs)


def etat(app) -> str:
    return str(app.screen.query_one("#etat", Static).content)


# --------------------------------------------------------------------------
# Le cablage de la progression
# --------------------------------------------------------------------------

def test_la_ligne_d_etat_suit_les_jalons_du_coeur_sans_qu_on_la_rafraichisse(banc):
    """**L'ecran n'affichait jamais la progression.**

    `SurfaceExecution` portait un rappel `sur_jalon` que personne ne fournissait
    et l'ecran ne s'y inscrivait pas : la ligne d'etat etait dessinee une fois au
    montage puis plus jamais. Sur une extraction de 6 300 frames, l'operateur
    lisait `0 %  0/6300 frames` du debut a la fin -- un compte qui **ment**, la
    ou `DESIGN.md` section 9 n'admet qu'un compte qui n'avance pas.

    Les deux tests qui observaient une ligne vivante appelaient `rafraichir()` a
    la main : ils mesuraient la methode et laissaient le cablage libre. Celui-ci
    ne l'appelle **pas**.
    """
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    ecran = EcranExecution(surface, TITRE_DESSINE_DE_L_EXECUTION)

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        vus = [etat(app)]
        for faites in (30, 60, 84):
            emetteur.emettre(faites)
        await pilote.pause()
        vus.append(etat(app))
        return vus

    au_montage, apres = banc(coque(), scenario)
    assert "0/124 frames" in au_montage
    assert "84/124 frames" in apres
    assert "68 %" in apres


def test_le_journal_suit_les_jalons_lui_aussi(banc):
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        for faites in (30, 60):
            emetteur.emettre(faites)
        await pilote.pause()
        return str(app.screen.query_one("#journal", Static).content)

    journal = banc(coque(), scenario)
    assert "60/124 frames" in journal


def test_un_ecran_demonte_ne_recoit_plus_de_jalons():
    """Volet symetrique de l'abonnement : un ecran detruit qui recevrait encore
    des jalons ecrirait dans un arbre de widgets qui n'existe plus."""
    surface = SurfaceExecution("frames")
    recus = []
    surface.abonner(recus.append)
    surface.abonner(recus.append)   # deux fois : l'abonnement est idempotent
    emetteur = surface.emetteur(10)
    emetteur.emettre(1)
    assert len(recus) == 1, "un seul appel, malgre le double abonnement"
    surface.desabonner(recus.append)
    emetteur.emettre(2)
    assert len(recus) == 1, "plus rien apres le desabonnement"
    surface.desabonner(recus.append)   # retirer un absent ne leve pas


# --------------------------------------------------------------------------
# La reutilisation d'une surface
# --------------------------------------------------------------------------

def test_une_seconde_tache_n_herite_pas_du_TEMPS__mais_GARDE_le_journal():
    """**Deux moities, et elles ne vont plus dans le meme sens depuis
    `EPIC11-ARB-93`. Ce banc est le banc d'origine RETOURNE, pas un banc neuf.**

    **La moitie qui ne bouge pas.** Une duree etait affichee alors que le coeur
    n'en rendait aucune : la seconde tache s'ouvrait sur « reste ~ 3 min 14 s »
    quand `estimateur.temps_restant` valait `None`. C'est l'interdit
    d'`EPIC7-ARB-67` mot pour mot, trouve par deux couches separement, et il
    reste entier -- compte, `temps_restant` et estimateur sont toujours remis a
    zero.

    **La moitie qui est renversee, et par qui.** Le banc d'origine exigeait
    aussi `len(surface.journal) == 0`, au motif qu'« un journal herite montre
    les jalons de la tache d'avant, donc un compte qui recule ». Vrai des
    JALONS -- et le journal est devenu, a la vague 3, la destination du **log du
    coeur**. Comme `emetteur()` est appele **une fois par lot** et que le relais
    de log n'est vise qu'**une fois**, au montage de `E2-4`, les 58 lignes du
    coeur devenaient injoignables des le second lot : relevé `ffprobe`, borne
    d'occupation disque, mise a jour du manifest, et un AVERTISSEMENT
    `[NON_INTEGER_TARGET_RATE]`. Mesure du parcours `H3`, par identite d'objet.

    Egan a tranche (`EPIC11-ARB-93`) : le journal est **l'histoire de
    l'extraction**. L'objection d'origine est fermee ailleurs -- par l'en-tete
    que `executer_le_plan` inscrit au debut de chaque lot, mesuree par
    `test_le_journal_GARDE_les_deux_lots_et_NOMME_chacun`.
    """
    horloge = Horloge()
    surface = SurfaceExecution("frames", horloge=horloge)
    emetteur = surface.emetteur(100)
    for faites in (1, 2, 3):
        horloge.avancer(2.0)
        emetteur.emettre(faites)
    assert surface.avancement.temps_restant is not None
    assert len(surface.journal) == 3
    temoin = surface.journal.lignes[0]
    journal_avant = surface.journal

    surface.emetteur(50)
    # ce qu'`EPIC7-ARB-67` visait vraiment : remis a zero.
    assert surface.avancement.temps_restant is None
    assert surface.estimateur.temps_restant is None
    assert surface.avancement.faites == 0
    assert "reste" not in surface.avancement.ligne_d_etat()
    # ce qu'`EPIC11-ARB-93` protege : le journal SURVIT, et c'est le MEME
    # objet -- un `Journal()` neuf au meme contenu laisserait le relais de log
    # ecrire dans l'ancien, ce qui est exactement le defaut d'origine.
    assert len(surface.journal) == 3, (
        "le journal ne se remet plus a zero entre deux taches (EPIC11-ARB-93)")
    assert surface.journal.lignes[0] == temoin
    # **L'IDENTITE, et c'est elle qui compte.** Un `Journal()` neuf au meme
    # contenu ne suffirait pas : le relais de log garde la reference qu'il a
    # visee au montage, donc un rebind -- meme a contenu recopie -- le ferait
    # ecrire dans un objet mort. C'est litteralement le defaut d'origine.
    assert surface.journal is journal_avant, (
        "`emetteur()` ne doit pas REBIND le journal : le relais de log garde "
        "la reference qu'il a visee au montage de E2-4")


def test_la_seconde_tache_remesure_son_propre_temps():
    """Volet symetrique : la remise a zero n'eteint pas la mesure suivante."""
    horloge = Horloge()
    surface = SurfaceExecution("frames", horloge=horloge)
    surface.emetteur(100)
    emetteur = surface.emetteur(50)
    emetteur.emettre(1)
    horloge.avancer(2.0)
    emetteur.emettre(2)
    assert surface.avancement.temps_restant == pytest.approx(96.0)


# --------------------------------------------------------------------------
# Le redimensionnement, et le franchissement du plancher
# --------------------------------------------------------------------------

def test_la_ligne_d_etat_est_recalculee_au_redimensionnement(banc):
    """Elle gardait le texte calcule pour l'ancienne largeur : 93 colonnes
    conservees dans une zone de 76 apres un passage de 120 a 80, donc un temps
    restant qui disparaissait sans bruit."""
    horloge = Horloge()
    surface = SurfaceExecution("frames", horloge=horloge)
    emetteur = surface.emetteur(6300)
    surface.avancement.detail = "lot 2 sur 5 · frame 1234 de 6300 au total"
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        emetteur.emettre(1)
        horloge.avancer(2.0)
        emetteur.emettre(2)
        await pilote.pause()
        large = etat(app)
        await pilote.resize_terminal(80, 24)
        await pilote.pause()
        return large, etat(app)

    large, etroite = banc(coque(), scenario, taille=(120, 40))
    assert jetons.colonnes(large) <= jetons.largeur_utile(120)
    assert jetons.colonnes(etroite) <= jetons.largeur_utile(80)
    assert large != etroite, "la ligne doit avoir ete recalculee"
    # Le detail est abrege a 80 et entier a 120 : c'est la LARGEUR qui a change
    # la ligne, pas les jalons -- il n'en est arrive aucun entre les deux.
    assert "au total" in large
    assert "au total" not in etroite
    # Et le temps restant, lui, survit aux deux largeurs : il n'est jamais
    # sacrifie (`EPIC7-ARB-67`).
    assert large.endswith("reste ~ 3 h 29")
    assert etroite.endswith("reste ~ 3 h 29")


def test_le_bandeau_et_les_raccourcis_sont_recalcules_aussi(banc):
    async def scenario(pilote):
        app = pilote.app
        app.descendre(confirmation())
        await pilote.pause()
        large = str(app.screen.query_one("#bandeau", Static).content)
        await pilote.resize_terminal(80, 24)
        await pilote.pause()
        return large, str(app.screen.query_one("#bandeau", Static).content)

    large, etroit = banc(coque(), scenario, taille=(120, 40))
    assert jetons.colonnes(large) == jetons.largeur_utile(120)
    assert jetons.colonnes(etroit) == jetons.largeur_utile(80)


@pytest.mark.parametrize("petite", [(79, 24), (80, 23), (70, 20)])
def test_franchir_le_plancher_et_revenir_ne_perd_pas_la_ligne_d_etat(banc, petite):
    """**Elle etait perdue definitivement.**

    Sous le plancher, `on_resize` recompose ; mais `on_mount` -- seul appelant de
    `rafraichir()`, donc de `poser_etat()` -- ne se rejoue jamais. Un operateur
    qui retrecissait sa fenetre puis la reagrandissait perdait le constat
    « rien n'a encore ete ecrit » pour toute la duree de vie de l'ecran, et sur
    un ecran d'execution la barre, le compte et le temps restant d'un coup.
    Trouve par deux couches, separement.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre(confirmation())
        await pilote.pause()
        depart = etat(app)
        await pilote.resize_terminal(*petite)
        await pilote.pause()
        sous_le_plancher = [w.id for w in app.screen.walk_children() if w.id]
        await pilote.resize_terminal(80, 24)
        await pilote.pause()
        return depart, sous_le_plancher, etat(app)

    depart, sous_le_plancher, retour = banc(coque(), scenario)
    assert depart == RIEN_ECRIT
    assert sous_le_plancher == ["trop-petit"]
    assert retour == RIEN_ECRIT


def test_franchir_le_plancher_ne_perd_pas_la_progression_en_cours(banc):
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        emetteur.emettre(84)
        await pilote.pause()
        await pilote.resize_terminal(79, 24)
        await pilote.pause()
        await pilote.resize_terminal(80, 24)
        await pilote.pause()
        return etat(app)

    assert "84/124 frames" in banc(coque(), scenario)


# --------------------------------------------------------------------------
# La sortie de l'ecran d'interruption
# --------------------------------------------------------------------------

def test_reprendre_depile_et_rend_la_main_a_l_execution(banc):
    """**L'ecran d'interruption n'avait aucune sortie clavier.**

    `ouvrir_l_interruption()` omettait `sur_issue` : les trois issues posaient
    `issue_declenchee` et n'appelaient personne, `Echap` ne depilait pas (une
    tache tourne), `q` posait un drapeau que rien n'affichait. « Reprendre »
    comprise, qui est pourtant de la pure navigation interne a la surface
    partagee (revue de vague 1, couche 3).
    """
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        rang_execution = app.passages_empiles
        await pilote.press("escape")
        await pilote.pause()
        sur_interruption = (app.passages_empiles, type(app.screen).__name__)
        await pilote.press("down")
        await pilote.press("down")
        await pilote.press("space")
        await pilote.press("enter")
        await pilote.pause()
        return rang_execution, sur_interruption, (app.passages_empiles,
                                                  type(app.screen).__name__)

    empiles, interruption, retour = banc(coque(), scenario)
    # Deux **passages** sur le meme palier : c'est leur nombre qui croit, et le
    # rang qui doit rester immobile.
    assert interruption == (empiles + 1, "EcranInterruption")
    assert retour == (empiles, "EcranExecution")


def test_echap_sur_l_interruption_reprend_l_execution(banc):
    """La maquette `T6-1` l'annonce en toutes lettres : « Echap reprendre
    l'ecriture ». La touche ne faisait rien."""
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        empiles = app.passages_empiles
        await pilote.press("escape")
        await pilote.pause()
        sur_interruption = app.passages_empiles
        await pilote.press("escape")
        await pilote.pause()
        return empiles, sur_interruption, app.passages_empiles,             type(app.screen).__name__

    empiles, interruption, retour, ecran_courant = banc(coque(), scenario)
    assert interruption == empiles + 1
    assert (retour, ecran_courant) == (empiles, "EcranExecution")


def test_les_deux_issues_qui_interrompent_vont_a_l_atelier(banc):
    """Volet symetrique : « reprendre » se traite ici, les deux autres non --
    seul l'atelier sait ce qu'il a ouvert. La cible visee est la PREMIERE, et
    un autre test vise la troisieme : une liste indexee de travers rendrait
    « effacer » a la place de « garder »."""
    recues = []
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    ecran = EcranExecution(surface, "Extraction", sur_issue=recues.append)

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("escape")
        await pilote.pause()
        rang_interruption = app.rang
        await pilote.press("space")     # « garder », premiere issue
        await pilote.press("enter")
        await pilote.pause()
        return rang_interruption, app.rang, type(app.screen).__name__

    avant, apres, ecran_courant = banc(coque(), scenario)
    assert [issue.cle for issue in recues] == ["garder"]
    # L'ecran reste monte : c'est l'atelier qui decide de la suite.
    assert (apres, ecran_courant) == (avant, "EcranInterruption")


def test_la_ligne_de_raccourcis_de_l_interruption_annonce_sa_sortie():
    """Elle n'annoncait aucune sortie, et il n'y en avait aucune."""
    assert "Échap" in EcranInterruption.raccourcis
    assert "reprendre" in EcranInterruption.raccourcis.lower()


# --------------------------------------------------------------------------
# `Entree` sur une action bloquee
# --------------------------------------------------------------------------

def test_valider_une_action_bloquee_dit_pourquoi(banc):
    """Elle ne faisait rien **et ne disait rien** : indistinguable d'un clavier
    casse. Elle nomme desormais le motif, et deplace le curseur sur le nom
    fautif -- qui n'est pas le premier."""
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        ecran.noms.descendre()
        ecran.noms.saisir("nom avec espaces")
        ecran.noms.monter()
        # Viser l'issue qui ecrit, puis valider : depuis `EPIC11-ARB-45` le
        # curseur EST la selection, il n'y a plus de retenue separee.
        ecran.choix.viser(ecran.choix.action_qui_ecrit.cle)
        await pilote.press("enter")
        await pilote.pause()
        corps = app.screen.query_one("#refus-du-nom", Static)
        return (etat(app), ecran.issue_declenchee, ecran.noms.curseur,
                str(corps.content), corps.display)

    message, issue, curseur, corps, visible = banc(coque(), scenario)
    assert issue is None, "rien n'est declenche"
    # **La ligne d'etat dit la MESURE et la consequence** (`EPIC11-ARB-56`) ;
    # le motif du coeur, lui, descend dans le corps (`EPIC11-ARB-25`). C'est la
    # mise en page de la maquette `E2-3c`, et les deux moities sont mesurees
    # ici -- sans la seconde, un ecran qui aurait perdu le motif serait vert.
    assert FIN_DESSINEE_DE_LA_LIGNE_D_ETAT in message, message
    assert "lettres non accentuees" not in message, message
    assert curseur == 1, "le curseur va sur le nom fautif"
    assert visible is True, "le corps du refus doit se montrer"
    assert "lettres non accentuées" in corps, corps


def test_valider_par_REFLEXE_suit_une_sortie_et_n_ecrit_pas(banc):
    """`EPIC11-ARB-45` a supprime le geste de retenue ; la validation n'est
    donc plus jamais muette -- ce qu'Egan avait lu comme un blocage.

    Ce qui protege de l'accident est desormais la position du curseur au
    montage : il ne vise jamais l'issue qui ecrit.
    """
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        au_montage = ecran.choix.issues[ecran.choix.curseur]
        await pilote.press("enter")
        await pilote.pause()
        return au_montage, ecran.issue_declenchee

    au_montage, issue = banc(coque(), scenario)
    assert au_montage.ecrit is False
    assert issue is not None, "la validation n'est plus muette"
    assert issue.ecrit is False, "un reflexe a declenche une ecriture"


def test_le_retour_aux_ateliers_eteint_les_trois_drapeaux(banc):
    """Deux drapeaux etaient poses a vrai et **aucun chemin ne les remettait a
    faux** : un atelier qui les consulterait verrait une interruption demandee
    bien apres la fin de la tache (revue de vague 1, couche 2)."""
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        app.descendre(EcranExecution(SurfaceExecution("frames")))
        await pilote.pause()
        app.tache_en_cours = True
        app.interruption_demandee = True
        app.confirmation_de_sortie_demandee = True
        app.revenir_aux_ateliers()
        await pilote.pause()
        return (app.tache_en_cours, app.interruption_demandee,
                app.confirmation_de_sortie_demandee, app.rang)

    assert banc(coque(), scenario) == (False, False, False, 1)


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc nomme `E2-3c` (« c'est la mise
# en page de la maquette `E2-3c` ») et monte un ecran titre comme `E2-4`,
# sans ouvrir ni l'un ni l'autre.

#: Le titre que `E2-4` dessine en tete de son ecran d'execution (l. 5, avant
#: le rang du lot). Confronte a sa source ci-dessous.
TITRE_DESSINE_DE_L_EXECUTION = "Extraction en cours"

#: La fin de la ligne d'etat que `E2-3c` dessine (l. 22). Confrontee aussi.
FIN_DESSINEE_DE_LA_LIGNE_D_ETAT = "reste inaccessible"

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_TITRE_de_l_execution_est_celui_que_E2_4_dessine():
    """Le titre est un PREFIXE du titre dessine, et le dire est la mesure.

    `E2-4` porte « Extraction en cours — lot 2 sur 2 » : le dessin situe la
    passe, le banc n'en monte que la tete parce qu'il ne fabrique pas de
    plan. Ce n'est pas un ecart -- c'est un montage partiel --, mais une
    confrontation qui se contenterait de l'appartenance ne saurait pas le
    dire. Elle mesure donc les deux : la tete appartient, la queue non.
    """
    dessin = dessin_de_la_maquette("E2-4-extraction-execution.txt")
    assert TITRE_DESSINE_DE_L_EXECUTION in dessin
    assert TITRE_DESSINE_DE_L_EXECUTION + " — lot 2 sur 2" in dessin
    assert TITRE_DESSINE_DE_L_EXECUTION + " —" not in TITRE_DESSINE_DE_L_EXECUTION


def test_la_LIGNE_D_ETAT_et_le_CORPS_de_E2_3c_portent_les_DEUX_moities():
    """La mise en page que ce banc invoque, mesuree sur le dessin.

    `EPIC11-ARB-56` veut la mesure et la consequence en ligne d'etat ;
    `EPIC11-ARB-25` veut le motif dans le corps. Le dessin le montre : la
    consequence est au pied, le motif est au corps, et ils ne sont PAS au
    meme endroit. Mesurer les deux moities separement est ce qui distingue
    « les deux textes existent » de « ils sont a leur place ».
    """
    dessin = dessin_de_la_maquette("E2-3c-extraction-nom-refuse.txt")
    assert FIN_DESSINEE_DE_LA_LIGNE_D_ETAT in dessin
    assert "trop long" in dessin

    # La consequence tombe APRES le motif dans le dessin : le corps est en
    # haut, la ligne d'etat en pied.
    assert dessin.index("trop long") < dessin.index(
        FIN_DESSINEE_DE_LA_LIGNE_D_ETAT)


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    refus = dessin_de_la_maquette("E2-3c-extraction-nom-refuse.txt")
    execution = dessin_de_la_maquette("E2-4-extraction-execution.txt")
    assert "reste accessible" not in refus
    assert TITRE_DESSINE_DE_L_EXECUTION not in refus
    assert FIN_DESSINEE_DE_LA_LIGNE_D_ETAT not in execution
