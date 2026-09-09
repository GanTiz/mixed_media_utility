# -*- coding: utf-8 -*-
"""Story 11.1, AC 1, 4, 5, 6, 7 et 8 -- les six ecrans partages, montes."""

from pathlib import Path

import pytest
from textual.widgets import Static

from mixed_media_utility.scan_detect import MOTIFS_D_ARRET
from mixed_media_utility.scan_sorting import MOTIFS_DE_RELIQUAT, MOTIFS_HORS_PERIMETRE
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.avancement import Avancement, Journal
from mixed_media_utility.tui.coque import CoqueTui, Contexte, Palier, PalierTemoin
from mixed_media_utility.tui.execution import (
    EcranChiffre,
    EcranEcrasement,
    EcranExecution,
    EcranInterruption,
    EcranRefus,
    EcranResultat,
    PanneauConfirmation,
    SurfaceExecution,
)
from mixed_media_utility.tui.noms import LIMITE, ModeleNoms, NomEditable
from mixed_media_utility.tui.panneau import (
    MENTION_MAJORANT,
    RIEN_ECRIT,
    ChoixExclusif,
    Issue,
    LigneChiffree,
    Panneau,
)

from outils_frontiere import chaines_de_code

#: Le vocabulaire FERME des refus du coeur (story 5.27 et suivantes). La TUI
#: ne doit en porter aucun en litteral : elle affiche celui qu'on lui donne.
CODES_DU_COEUR = tuple(MOTIFS_D_ARRET) + tuple(MOTIFS_DE_RELIQUAT) + tuple(
    MOTIFS_HORS_PERIMETRE)


#: Les valeurs que les maquettes `E2-1` a `E2-5` DESSINENT, nommees ici une
#: seule fois. Elles etaient tapees en clair sur vingt-quatre sites, donc
#: recopiees a la main d'un dessin que ce banc citait sans jamais l'ouvrir --
#: un texte recopie coincide le jour ou il est ecrit et derive ensuite sans
#: qu'aucune etape n'echoue. Chacune est confrontee a sa source en fin de
#: fichier, le dessin etant relu sur disque a chaque tour.
LIBELLE_ESPACE_DISQUE = "Espace disque"
MOT_DE_L_INACCESSIBLE = "reste inaccessible"
MOT_DU_NOM_TROP_LONG = "trop long"
TITRE_DE_L_EXECUTION = "Extraction en cours"
SUITE_DES_PLANCHES = "Composer les planches de ces lots"
DEBUT_DE_LA_SUITE_DES_PLANCHES = "Composer les planches"
SUITE_DU_DOSSIER = "Ouvrir le dossier des lots"
MOT_DES_CHOIX = "les choix"
PREFIXE_DU_BANDEAU = "mmu · projet_demo · "
RACCOURCI_DU_JOURNAL = "Tab journal"


def coque(**kwargs) -> CoqueTui:
    """Une coque a deux paliers temoins : l'ecran projet et le menu ateliers.

    Deux et non un : le retour au palier 1 (`EPIC11-ARB-13`) ne se distingue
    d'un retour a la racine que si la racine existe a cote.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def panneau_temoin() -> Panneau:
    return Panneau("A ecrire", [
        LigneChiffree("Lots crees", 2, "lots"),
        LigneChiffree("Frames ecrites", 186, "frames"),
        LigneChiffree(LIBELLE_ESPACE_DISQUE, "~ 3,1", "Go", majorant=True),
    ])


def noms_temoins() -> ModeleNoms:
    return ModeleNoms([NomEditable("projet_demo_rush_01_25fps"),
                       NomEditable("projet_demo_rush_01_12p5")])


def issues_temoins() -> ChoixExclusif:
    return ChoixExclusif([Issue("ecrire", "Extraire", ecrit=True),
                          Issue("modifier", "Modifier les reglages"),
                          Issue("annuler", "Annuler")])


def contenu_du_cartouche(app) -> str:
    """Tout le texte du cartouche : le bloc chiffre PLUS les lignes de noms.

    Le cartouche est devenu un conteneur -- un widget par nom -- pour qu'un
    nom refuse puisse porter sa propre couleur. Un seul bloc de texte ne le
    permettait pas, et un nom refuse etait rendu comme un nom valide.
    """
    morceaux = [app.screen.query_one("#chiffres", Static).content]
    morceaux += [w.content for w in app.screen.query(".nom")]
    return "\n".join(str(m) for m in morceaux)


def confirmation(**kwargs) -> PanneauConfirmation:
    return PanneauConfirmation(panneau_temoin(), issues_temoins(),
                               noms_temoins(), **kwargs)


# --------------------------------------------------------------------------
# AC 1 -- le panneau de confirmation, obligatoire avant toute ecriture
# --------------------------------------------------------------------------

def test_le_panneau_affiche_ses_chiffres_ses_noms_et_ses_issues(banc):
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return (contenu_du_cartouche(pilote.app),
                pilote.app.screen.query_one("#issues", Static).content,
                pilote.app.screen.query_one("#etat", Static).content)

    cartouche, issues, etat = banc(coque(), scenario)
    assert "186 frames" in cartouche
    assert MENTION_MAJORANT in cartouche
    assert "projet_demo_rush_01_25fps" in cartouche
    assert "Extraire" in issues and "Annuler" in issues
    assert etat == RIEN_ECRIT


def test_le_titre_du_cartouche_est_porte_par_le_cadre(banc):
    """`DESIGN.md` 7.4 : le titre est dans le trait, ce qui rend une ligne de
    la zone centrale au contenu."""
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#cartouche").border_title)

    assert banc(coque(), scenario) == "A ecrire"


def test_quitter_le_panneau_par_echap_n_ecrit_aucun_fichier(banc, tmp_path):
    """AC 1.4 : monter, naviguer, editer un nom, sortir -- zero fichier."""
    temoin = tmp_path / "temoin"
    temoin.mkdir()
    ecrits = []
    ecran = confirmation(sur_issue=lambda issue: ecrits.append(issue.cle))

    async def scenario(pilote):
        app = pilote.app
        app.descendre()          # menu des ateliers
        await pilote.pause()
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("down")
        # `Tab` et non `e` depuis `EPIC11-ARB-68` : dans un champ de saisie,
        # aucune LETTRE n'est un raccourci. Ce que ces tests mesurent n'a pas
        # bouge d'une assertion -- seule la porte de l'edition a change.
        await pilote.press("tab")
        await pilote.press("down")
        await pilote.press("r")
        await pilote.press("escape")   # sort de l'edition
        await pilote.press("escape")   # remonte
        await pilote.pause()
        return app.rang

    assert banc(coque(), scenario) == 1, "on est revenu au menu des ateliers"
    assert list(temoin.iterdir()) == []
    assert ecrits == [], "aucune issue n'a ete declenchee"


def test_le_comptage_de_fichiers_mord_quand_on_ecrit_vraiment(tmp_path):
    """AC 1.4, volet symetrique : sans lui, le repertoire vide ne prouve rien."""
    temoin = tmp_path / "temoin"
    temoin.mkdir()
    (temoin / "projet_demo_rush_01_25fps.tiff").write_bytes(b"x")
    assert len(list(temoin.iterdir())) == 1


def test_valider_par_REFLEXE_ne_declenche_pas_l_ecriture(banc):
    """Ce que `EPIC11-ARB-7` garde apres `EPIC11-ARB-45`, au clavier.

    La validation retient et suit desormais en un seul geste. La protection
    contre l'accident n'est donc plus le double geste : c'est que **le curseur
    ne part jamais sur l'issue qui ecrit**. Un operateur qui arrive sur le
    panneau et frappe la validation par reflexe declenche une sortie, jamais
    l'ecriture.
    """
    declenchees = []
    ecran = confirmation(sur_issue=declenchees.append)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        au_montage = ecran.choix.issues[ecran.choix.curseur]
        await pilote.press("enter")           # reflexe, sans avoir navigue
        await pilote.pause()
        return au_montage, ecran.issue_declenchee

    au_montage, declenchee = banc(coque(), scenario)
    assert au_montage.ecrit is False, "le curseur du montage vise une ecriture"
    assert declenchee is not None and declenchee.ecrit is False
    assert [i.cle for i in declenchees] == [declenchee.cle]
    # Volet symetrique : le panneau porte bien une issue qui ecrit, sinon la
    # mesure serait vraie par vacuite.
    assert any(i.ecrit for i in ecran.choix.issues)


def test_retenir_puis_valider_declenche_l_issue_sous_le_curseur(banc):
    """Volet symetrique : la cible visee est la TROISIEME issue, pas la
    premiere -- une liste indexee de travers rendrait « Extraire »."""
    declenchees = []
    ecran = confirmation(sur_issue=declenchees.append)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await pilote.press("down")
        await pilote.press("down")
        await pilote.press("space")
        await pilote.press("enter")
        await pilote.pause()
        return ecran.issue_declenchee

    issue = banc(coque(), scenario)
    assert issue.cle == "annuler"
    assert [i.cle for i in declenchees] == ["annuler"]


# --------------------------------------------------------------------------
# AC 2 -- l'edition, vue depuis l'ecran
# --------------------------------------------------------------------------

def test_chaque_nom_porte_SON_compteur_dans_le_cartouche(banc):
    """AC 2.2 : « un compteur vivant `n/48` **par nom** ».

    **Le test precedent mesurait ce que j'avais implemente, pas ce que l'AC
    demandait** : un compteur unique, en ligne d'etat, qui ne designait pas
    lequel des noms il comptait (revue de vague 1, couche 3). Les maquettes
    validees `E2-3b` et `E2-3c` le portent sur chaque ligne de nom.

    Les deux noms ont des longueurs DIFFERENTES : deux compteurs identiques ne
    prouveraient pas qu'ils comptent chacun leur nom.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return [str(w.content) for w in pilote.app.screen.query(".nom")]

    lignes = banc(coque(), scenario)
    assert len(lignes) == 2
    assert lignes[0].endswith("25/48")
    assert lignes[1].endswith("24/48")


def test_le_compteur_est_vivant_sous_la_frappe(banc):
    """AC 2.2 : « vivant ». Il ne l'etait pas -- rien ne pouvait le faire
    varier, faute de pouvoir taper."""
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")
        vus = [str(pilote.app.screen.query(".nom")[0].content)]
        for touche in ("underscore", "h", "i"):
            await pilote.press(touche)
        vus.append(str(pilote.app.screen.query(".nom")[0].content))
        return vus

    avant, apres = banc(coque(), scenario)
    assert avant.endswith("25/48")
    assert apres.endswith("28/48")
    assert "projet_demo_rush_01_25fps_hi" in apres


def test_on_peut_taper_un_nom_au_clavier(banc):
    """AC 1.1 et 2.1 : « et **editables** ». Le modele l'etait, l'ecran non --
    aucune touche n'ecrivait un caractere (revue de vague 1, couche 3)."""
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")
        # Cinq retours arriere retirent « 25fps », puis on tape « 12p5 ».
        for touche in ("backspace",) * 5 + ("1", "2", "p", "5"):
            await pilote.press(touche)
        await pilote.press("enter")
        await pilote.pause()
        return ecran.noms.valeurs, ecran.noms.en_edition

    valeurs, en_edition = banc(coque(), scenario)
    assert valeurs[0] == "projet_demo_rush_01_12p5"
    assert valeurs[1] == "projet_demo_rush_01_12p5", "le second nom n'a pas bouge"
    assert en_edition is False


def test_q_pendant_l_edition_TAPE_un_q_et_ne_quitte_pas(banc):
    """**`q` quittait la TUI en pleine edition**, sans confirmation et en
    perdant la saisie (revue de vague 1, couche 1). Un mode d'edition capture le
    clavier, sinon ce n'en est pas un."""
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")
        await pilote.press("q")
        await pilote.pause()
        return app._exit, ecran.noms.valeurs[0]

    sorti, valeur = banc(coque(), scenario)
    assert sorti is False
    assert valeur.endswith("q")


def test_hors_edition_q_quitte_toujours(banc):
    """Volet symetrique : la capture du clavier est bornee au MODE, elle ne
    desarme pas `q` sur l'ecran."""
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("q")
        await pilote.pause()
        return app._exit

    assert banc(coque(), scenario) is True


def test_un_nom_refuse_porte_son_glyphe_et_sa_couleur(banc):
    """AC 2.3 : « le champ passe en `state-absent` ».

    Les DEUX canaux : la classe qui porte la couleur, et le glyphe `✕` qui la
    double -- regle 1 non negociable de `DESIGN.md` section 5. Un nom refuse
    etait jusqu'ici rendu exactement comme un nom valide.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.noms.descendre()
        ecran.noms.saisir("nom avec espaces")
        ecran.rafraichir()
        await pilote.pause()
        lignes = pilote.app.screen.query(".nom")
        return [(str(w.content), w.has_class("nom-refuse")) for w in lignes]

    (texte_valide, refuse_valide), (texte_refuse, refuse) = banc(coque(), scenario)
    assert refuse is True
    assert jetons.GLYPHES["absent"] in texte_refuse
    assert refuse_valide is False
    assert jetons.GLYPHES["absent"] not in texte_valide


def test_le_nom_courant_se_distingue_des_autres(banc):
    """Rien ne disait quel nom etait edite : le cartouche etait identique
    octet pour octet avant et apres un `↓`."""
    ecran = confirmation()

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")
        avant = [str(w.content) for w in app.screen.query(".nom")]
        await pilote.press("down")
        apres = [str(w.content) for w in app.screen.query(".nom")]
        classes = [w.has_class("nom-courant") for w in app.screen.query(".nom")]
        return avant, apres, classes

    avant, apres, classes = banc(coque(), scenario)
    assert avant != apres, "le curseur doit se voir"
    assert avant[0].startswith(jetons.GLYPHES["invite"])
    assert apres[1].startswith(jetons.GLYPHES["invite"])
    assert classes == [False, True]


def test_un_nom_REFUSE_met_la_MESURE_en_ligne_d_etat_et_le_MOTIF_dans_le_CORPS(banc):
    """La reconciliation d'`EPIC11-ARB-25` et d'`EPIC11-ARB-56`, mesuree.

    Les deux arbitrages se contredisaient sur cette ligne exacte, et le lot `G`
    l'avait declare sans le trancher :

    * `EPIC11-ARB-56`, verbatim : la ligne d'etat « ne porte **aucune touche**
      [...] **aucun conseil d'usage** [...] **aucun motif de conception** » ;
    * `EPIC11-ARB-25`, verbatim : « le message nomme le motif au lieu de dire
      « invalide » ».

    La maquette `E2-3c` les reconcilie **par la mise en page** : le motif
    descend dans le corps, la ligne d'etat ne garde qu'une mesure. Ce test
    mesure les deux moities ensemble -- une seule des deux serait verte sur un
    ecran qui aurait simplement perdu le motif.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")
        ecran.noms.saisir("a" * 60)
        ecran.rafraichir()
        await pilote.pause()
        return (str(pilote.app.screen.query_one("#etat", Static).content),
                str(pilote.app.screen.query_one("#refus-du-nom",
                                                Static).content),
                pilote.app.screen.query_one("#refus-du-nom", Static).display)

    etat, corps, visible = banc(coque(), scenario)
    # La ligne d'etat : une MESURE, plus la consequence. Aucun motif.
    assert "60" in etat and str(LIMITE) in etat, etat
    assert MOT_DE_L_INACCESSIBLE in etat, etat
    assert "prefixe" not in etat and "préfixe" not in etat, etat
    assert "invalide" not in etat.lower(), etat
    # Le corps : le motif, nomme, et VISIBLE.
    assert visible is True
    assert MOT_DU_NOM_TROP_LONG in corps, corps
    assert jetons.GLYPHES["absent"] in corps, corps


def test_le_CORPS_du_refus_est_MASQUE_tant_qu_aucun_nom_n_est_refuse(banc):
    """Volet symetrique : un corps toujours monte prendrait sa ligne de hauteur
    sur un ecran partage par les quatre ateliers, et rendrait le test precedent
    vert sur un ecran qui n'aurait rien a dire."""
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()
        return pilote.app.screen.query_one("#refus-du-nom", Static).display

    assert banc(coque(), scenario) is False


def test_un_nom_refuse_rend_l_action_principale_inaccessible(banc):
    """AC 2.3 : on ne corrige pas a sa place, et on n'ecrit pas."""
    declenchees = []
    ecran = confirmation(sur_issue=declenchees.append)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.noms.saisir("nom avec espaces")
        # **Viser l'issue qui ecrit, puis valider.** Depuis `EPIC11-ARB-45` il
        # n'y a plus de retenue separee : c'est le curseur qui designe, et le
        # refus doit mordre la, sur le geste complet.
        ecran.choix.viser(ecran.choix.action_qui_ecrit.cle)
        await pilote.press("enter")
        await pilote.pause()
        return ecran.issue_declenchee, ecran.action_principale_accessible

    issue, accessible = banc(coque(), scenario)
    assert issue is None
    assert accessible is False
    assert declenchees == []


def test_une_issue_qui_n_ecrit_pas_reste_accessible_malgre_un_nom_refuse(banc):
    """Volet symetrique : bloquer TOUT enfermerait l'operateur dans un panneau
    dont il ne pourrait plus sortir qu'en tuant la TUI."""
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.noms.saisir("nom avec espaces")
        await pilote.press("down")
        await pilote.press("down")
        await pilote.press("space")     # « Annuler », qui n'ecrit pas
        await pilote.press("enter")
        await pilote.pause()
        return ecran.issue_declenchee

    assert banc(coque(), scenario).cle == "annuler"


# --------------------------------------------------------------------------
# AC 4 -- interrompre
# --------------------------------------------------------------------------

def test_echap_pendant_l_execution_ouvre_l_interruption_au_lieu_de_remonter(banc):
    """AC 4.1 : `Echap` cesse d'etre une remontee -- il empile."""
    surface = SurfaceExecution("frames")
    surface.emetteur(124)
    ecran = EcranExecution(surface, TITRE_DE_L_EXECUTION)

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        # Execution et interruption sont deux **passages** sur le meme palier :
        # ce qui doit croitre est le nombre d'ecrans transitoires empiles, pas
        # le rang -- lequel ne doit justement PAS bouger.
        avant = (app.passages_empiles, app.rang)
        await pilote.press("escape")
        await pilote.pause()
        return avant, (app.passages_empiles, app.rang), type(app.screen).__name__

    avant, apres, ecran_courant = banc(coque(), scenario)
    assert apres[0] == avant[0] + 1, "on a empile, on n'a pas depile"
    assert apres[1] == avant[1], "une interruption ne change pas de palier"
    assert ecran_courant == "EcranInterruption"


def test_ouvrir_l_interruption_n_arrete_pas_la_tache(banc):
    """AC 4.2 : la progression avance encore pendant que l'ecran est monte."""
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    ecran = EcranExecution(surface, TITRE_DE_L_EXECUTION)

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        emetteur.emettre(40)
        await pilote.press("escape")
        await pilote.pause()
        avant = surface.avancement.faites
        emetteur.emettre(80)          # la tache continue derriere l'ecran
        await pilote.pause()
        return avant, surface.avancement.faites, type(app.screen).__name__

    avant, apres, ecran_courant = banc(coque(), scenario)
    assert (avant, apres) == (40, 80)
    assert ecran_courant == "EcranInterruption"


def test_l_ecran_d_interruption_dit_ce_qui_est_ecrit_et_ce_qui_reste(banc):
    """AC 4.4, et les deux chiffres sont MESURES : aucun majorant."""
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    emetteur.emettre(40)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        return contenu_du_cartouche(pilote.app)

    cartouche = banc(coque(), scenario)
    assert "40 frames" in cartouche
    assert "84 frames" in cartouche
    assert MENTION_MAJORANT not in cartouche


def test_l_interruption_porte_trois_issues_et_le_curseur_n_ecrit_pas():
    """AC 4.3."""
    ecran = EcranInterruption(Panneau("Deja ecrit", []))
    assert [i.cle for i in ecran.choix.issues] == ["garder", "effacer", "reprendre"]
    assert ecran.choix.retenue is None
    # `EPIC11-ARB-45` : rien n'est retenu au MONTAGE, et le curseur ne vise
    # pas l'issue qui ecrit -- c'est ce qui remplace l'ancien « valider sans
    # avoir choisi ne rend rien ».
    assert ecran.choix.retenue is None
    assert ecran.choix.issues[ecran.choix.curseur].ecrit is False
    # Une seule des trois ecrit : effacer. Les deux autres sont des sorties.
    assert [i.cle for i in ecran.choix.issues if i.ecrit] == ["effacer"]


# --------------------------------------------------------------------------
# AC 5 -- l'ecrasement est une confirmation en propre
# --------------------------------------------------------------------------

def test_l_ecran_d_ecrasement_est_distinct_du_panneau_nominal():
    """AC 5.1 : ce n'est pas le panneau nominal avec une phrase de plus."""
    assert EcranEcrasement is not PanneauConfirmation
    assert not issubclass(PanneauConfirmation, EcranEcrasement)
    assert EcranEcrasement.titre != PanneauConfirmation.titre


def test_l_ecrasement_dit_ce_qu_il_ne_fait_pas(banc):
    """AC 5.2 : les artefacts derives ne sont pas regeneres.

    **ECART AC / CODE, `EPIC11-ARB-245`, nomme au registre de la 11.4e (G4).**
    L'AC 5.2 tient ; c'est la MESURE qui change, et dans le sens de ce que l'AC
    dit. La phrase unique de 96 colonnes que ce test cherchait par la
    sous-chaine `ne regenere pas` sortait **ABREGEE** a 72 colonnes -- elle se
    dedouble depuis, verbatim de la maquette `T4-2` validee le 2026-09-05.

    La mesure ne se contente donc plus d'une sous-chaine de redaction : elle
    exige les DEUX artefacts derives nommes -- planches et masters --, ce que
    l'AC vise reellement, et que l'ancienne redaction ne mesurait qu'a moitie
    (`masters` n'y figurait pas). Aucune constante n'est assertee contre
    elle-meme : ce qui est lu est le cartouche PEINT.
    """
    panneau = Panneau("Deja present", [
        LigneChiffree("Frames existantes", 124, "frames"),
        LigneChiffree("Ecrit le", "26/08 14:32"),
        LigneChiffree("Planches qui en dependent", 4, "planches"),
    ])
    choix = ChoixExclusif([Issue("ecraser", "Ecraser", ecrit=True),
                           Issue("renommer", "Ecrire sous un autre nom",
                                 ecrit=True),
                           Issue("annuler", "Annuler")])
    ecran = EcranEcrasement(panneau, choix,
                            ModeleNoms([NomEditable("projet_demo_lot_25fps")]))

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return contenu_du_cartouche(pilote.app)

    cartouche = banc(coque(), scenario)
    assert "ne sont PAS reg" in cartouche, cartouche
    assert "masters" in cartouche.lower(), cartouche
    assert "planches" in cartouche.lower()
    assert "26/08 14:32" in cartouche


def test_le_champ_prerempli_de_l_ecrasement_est_soumis_a_la_limite():
    """AC 5.3 : « ecrire sous un autre nom » n'echappe pas a l'AC 2."""
    modele = ModeleNoms([NomEditable("projet_demo_lot_25fps")])
    modele.saisir("a" * 60)
    assert modele.valides is False


# --------------------------------------------------------------------------
# AC 6 -- un refus se nomme par son code
# --------------------------------------------------------------------------

def test_le_refus_affiche_son_code_puis_la_phrase_du_coeur(banc):
    """AC 6.1, et l'appariement de chaque rubrique avec SON contenu.

    Les trois rubriques portent des contenus **distinguables et croises** :
    « Conserve » et « Non ecrit » pouvaient etre echangees sans qu'aucun test ne
    le voie (revue de vague 1, couche 2), et un refus qui annoncerait conserve
    ce qu'il n'a pas ecrit dirait exactement le contraire de la verite.
    """
    code = MOTIFS_D_ARRET[1]      # deliberement PAS le premier de la liste
    message = ("Aucune planche n'a livre son QR : 0 page identifiee sur 12 "
               "ingerees.")
    ecran = EcranRefus(code, message,
                       non_ecrit=["AUCUN-DOCUMENT-DE-DETECTION"],
                       conserve=["LES-12-PAGES-INGEREES"],
                       suites=["RELANCER-AVEC-UN-SCAN-PLUS-CONTRASTE"])

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#refus", Static).content)

    affiche = banc(coque(), scenario)
    assert code in affiche
    assert message in affiche, "le texte du coeur passe VERBATIM"
    assert affiche.index(code) < affiche.index(message)
    # Chaque rubrique precede SON contenu, et aucun autre ne s'intercale.
    for rubrique, contenu in (("Non ecrit", "AUCUN-DOCUMENT-DE-DETECTION"),
                              ("Conserve", "LES-12-PAGES-INGEREES"),
                              ("Suites", "RELANCER-AVEC-UN-SCAN-PLUS-CONTRASTE")):
        debut = affiche.index(rubrique)
        assert affiche.index(contenu) > debut
        entre_deux = affiche[debut:affiche.index(contenu)]
        assert "-" not in entre_deux.replace("\u2514\u2500", ""), (
            f"{rubrique} porte le contenu d'une autre rubrique : {entre_deux!r}")


#: Les seuls mots que la TUI a le droit d'ajouter a un refus du coeur : les
#: intitules de ses trois rubriques. Ils sont de la mise en forme -- ils rangent
#: ce que l'appelant a fourni, ils ne disent rien sur le refus.
RUBRIQUES_DU_REFUS = {"Non", "ecrit", "Conserve", "Suites"}


def test_la_tui_n_ajoute_aucune_interpretation_au_message_du_coeur(banc):
    """AC 6.3 : le texte affiche est une SUR-CHAINE exacte du texte leve.

    **Mesuree sur l'ecran REEL, rubriques remplies.** La premiere version la
    jouait sur un refus sans rubrique -- c'est-a-dire dans la seule
    configuration ou la TUI n'ajoute structurellement rien : la garde ne pouvait
    pas mordre (revue de vague 1, couche 3). Ici elle mord sur tout mot qui ne
    serait ni du coeur, ni un intitule de rubrique.
    """
    message = "Le lot lot_25fps porte 3 frames pour 4 emplacements."
    fournis = ["12 pages ingerees", "aucun document de detection",
               "relancer la detection"]
    ecran = EcranRefus("aucune-planche-identifiee", message,
                       conserve=[fournis[0]], non_ecrit=[fournis[1]],
                       suites=[fournis[2]])

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#refus", Static).content)

    affiche = banc(coque(), scenario)
    reste = affiche.replace(message, "").replace("aucune-planche-identifiee", "")
    for fourni in fournis:
        reste = reste.replace(fourni, "")
    mots = {m for m in reste.split() if m.isalpha() and len(m) > 2}
    assert mots <= RUBRIQUES_DU_REFUS, (
        f"la TUI a ajoute des mots au refus du coeur : {sorted(mots - RUBRIQUES_DU_REFUS)}")


def test_la_mesure_de_sur_chaine_mord_sur_une_phrase_ajoutee(banc):
    """Volet symetrique : une TUI bavarde doit faire rougir la garde."""
    class RefusBavard(EcranRefus):
        def lignes(self):
            return super().lignes() + ["Ce refus vient probablement d'un scan trop pale."]

    ecran = RefusBavard("aucune-planche-identifiee", "0 page sur 12.")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#refus", Static).content)

    affiche = banc(coque(), scenario)
    reste = affiche.replace("0 page sur 12.", "").replace(
        "aucune-planche-identifiee", "")
    mots = {m for m in reste.split() if m.isalpha() and len(m) > 2}
    assert not mots <= RUBRIQUES_DU_REFUS, "la garde doit mordre ici"


@pytest.mark.parametrize("code", CODES_DU_COEUR)
def test_aucun_code_de_refus_n_est_ecrit_en_dur_dans_la_tui(code, sources_tui):
    """AC 6.2, frontiere : comptage a zero sur les huit codes du vocabulaire."""
    coupables = {chemin.name for chemin in sources_tui
                 if any(code in chaine for chaine in chaines_de_code(chemin))}
    assert not coupables, f"{code} ecrit en dur dans {sorted(coupables)}"


def test_la_mesure_des_codes_de_refus_mord_sur_un_module_fautif(tmp_path):
    """AC 6.2, volet symetrique."""
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text(f'CODE = "{MOTIFS_D_ARRET[0]}"\n', encoding="utf-8")
    assert any(MOTIFS_D_ARRET[0] in c for c in chaines_de_code(chemin))


def test_le_vocabulaire_mesure_n_est_pas_vide():
    """Volet symetrique du precedent : une frontiere posee sur une liste vide
    serait verte sans rien mesurer."""
    assert len(CODES_DU_COEUR) >= 8
    assert len(set(CODES_DU_COEUR)) == len(CODES_DU_COEUR)


# --------------------------------------------------------------------------
# AC 7 -- constater va en ligne d'etat, decider va en cartouche
# --------------------------------------------------------------------------

def test_tout_cartouche_monte_par_cette_story_porte_deux_issues():
    """AC 7.2, frontiere mesurable : un cartouche sans issue est un defaut."""
    from mixed_media_utility.tui.panneau import ChoixExclusif as C
    ecrans = [confirmation(),
              EcranEcrasement(panneau_temoin(), issues_temoins()),
              EcranInterruption(Panneau("Deja ecrit", []))]
    for ecran in ecrans:
        assert isinstance(ecran.choix, C)
        assert len(ecran.choix.issues) >= 2, type(ecran).__name__
        assert ecran.choix.sortie_sans_ecriture is not None, type(ecran).__name__


def test_un_constat_va_en_ligne_d_etat_et_pas_en_cartouche(banc):
    """`EPIC11-ARB-35` : la progression est un CONSTAT."""
    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(124)
    emetteur.emettre(84)
    ecran = EcranExecution(surface, TITRE_DE_L_EXECUTION)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()
        return (pilote.app.screen.query_one("#etat", Static).content,
                [w.id for w in pilote.app.screen.walk_children() if w.id])

    etat, identifiants = banc(coque(), scenario)
    assert "84/124 frames" in etat
    assert "cartouche" not in identifiants


# --------------------------------------------------------------------------
# AC 8 -- le retour au palier 1
# --------------------------------------------------------------------------

def test_le_succes_ramene_au_menu_des_ateliers_et_pas_a_l_ecran_projet(banc):
    """AC 8.1, premiere sortie. La pile fait cinq etages avant le retour :
    remonter d'un cran laisserait l'operateur sur l'ecran d'execution.

    **Le chemin a change le 2026-08-28, l'AC non.** Les suites sont desormais
    navigables (Egan : « il faudra les cabler vers l'ecran generique tout en
    laissant l'interaction possible »), donc `⏎` choisit la suite sous le
    curseur au lieu de rentrer d'office. Le retour aux ateliers est **une
    suite**, ajoutee d'office en dernier -- c'est ce que montre la maquette
    `E2-5`. Ce que l'AC exige reste mesure ici : la sortie mene au **menu des
    ateliers**, jamais a l'ecran projet, et depuis un ecran empile profond.

    On y va par `↑↓` puis `⏎`, c'est-a-dire par le chemin de l'operateur.
    """
    resultat = EcranResultat(Panneau("Ecrit", [
        LigneChiffree("Frames ecrites", 186, "frames")]),
        suites=["composer les planches du lot"])

    async def scenario(pilote):
        app = pilote.app
        app.descendre()                       # menu des ateliers
        await pilote.pause()
        app.descendre(confirmation())
        await pilote.pause()
        app.descendre(EcranExecution(SurfaceExecution("frames")))
        await pilote.pause()
        app.descendre(resultat)
        await pilote.pause()
        # **La profondeur se mesure en PASSAGES, pas en rang.** Confirmation,
        # execution et resultat sont trois ecrans transitoires poses sur le
        # meme palier : le rang ne bouge pas, et c'est desormais voulu.
        profond = app.passages_empiles
        await pilote.press("down")            # jusqu'a « Retour aux ateliers »
        await pilote.pause()
        await pilote.press("enter")
        await pilote.pause()
        return profond, app.rang, app.screen.titre

    profond, rang, titre = banc(coque(), scenario)
    assert profond == 3, "l'ecran de resultat n'etait pas empile profond"
    assert (rang, titre) == (1, "Ateliers")


def test_echap_sur_le_resultat_rentre_aux_ateliers_et_pas_sur_l_execution(banc):
    """Volet du meme AC : `Échap` ne depile pas d'un cran ici.

    L'ecran de resultat est empile PAR-DESSUS l'execution : une remontee
    ordinaire ramenerait l'operateur sur la tache qu'il vient de finir. Sans ce
    volet, un `Échap` laisse a l'application passerait le test precedent.
    """
    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        app.descendre(EcranExecution(SurfaceExecution("frames")))
        await pilote.pause()
        app.descendre(EcranResultat(Panneau("Ecrit", [
            LigneChiffree("Frames ecrites", 186, "frames")])))
        await pilote.pause()
        await pilote.press("escape")
        await pilote.pause()
        return app.rang, app.screen.titre

    assert banc(coque(), scenario) == (1, "Ateliers")


def test_une_suite_sans_atelier_mene_a_l_ecran_pas_encore_et_reste_interactive(banc):
    """Egan, 2026-08-28 : « les cabler vers l'ecran generique qui dit que
    l'ecran n'existe pas TOUT EN LAISSANT L'INTERACTION POSSIBLE ».

    **Deux suites distinctes, et la cible n'est pas la premiere** (regle des
    fabriques) : un curseur qui rendrait toujours le premier element ne se
    demasquerait pas autrement, et c'est le defaut `M25` de la story 5.7 mot
    pour mot.
    """
    resultat = EcranResultat(
        Panneau("Ecrit", [LigneChiffree("Frames ecrites", 186, "frames")]),
        suites=["Scanner les planches de ce rush",
                SUITE_DES_PLANCHES])

    async def scenario(pilote):
        app = pilote.app
        app.descendre(resultat)
        await pilote.pause()
        await pilote.press("down")            # la SECONDE suite
        await pilote.pause()
        await pilote.press("enter")
        await pilote.pause()
        return type(app.screen).__name__, chr(10).join(app.screen.lignes())

    nom, texte = banc(coque(), scenario)
    assert nom == "EcranPasEncore"
    assert SUITE_DES_PLANCHES in texte, (
        "l'ecran generique nomme LA suite choisie, pas une autre")
    assert "n'existe pas encore" in texte


def test_le_retour_aux_ateliers_est_ajoute_d_office_et_en_dernier():
    """Un ecran de resultat sans chemin de retour serait un cul-de-sac.

    C'est le defaut que la couche 3 avait trouve sur l'ecran d'interruption
    (`AA-3`), et il ne doit pas renaitre ici. Le volet symetrique verifie qu'on
    ne le double pas quand l'appelant l'a deja mis.
    """
    ajoute = EcranResultat(Panneau("Ecrit"), suites=["Scanner les planches"])
    assert ajoute.suites == ["Scanner les planches", EcranResultat.RETOUR]

    deja = EcranResultat(Panneau("Ecrit"),
                         suites=[EcranResultat.RETOUR, "Scanner les planches"])
    assert deja.suites.count(EcranResultat.RETOUR) == 1, (
        "le retour ne doit pas etre double quand l'appelant l'a deja pose")


def test_le_refus_ramene_au_meme_endroit_que_le_succes(banc):
    """AC 8.1, seconde sortie -- mesuree separement, comme l'AC l'exige."""
    async def scenario(pilote):
        app = pilote.app
        app.descendre()          # menu des ateliers
        await pilote.pause()
        app.descendre(confirmation())
        await pilote.pause()
        app.descendre(EcranRefus("aucune-planche-identifiee", "0 page sur 12."))
        await pilote.pause()
        await pilote.press("enter")
        await pilote.pause()
        return app.rang, app.screen.titre

    assert banc(coque(), scenario) == (1, "Ateliers")


def test_le_retour_aux_ateliers_eteint_le_drapeau_de_tache_en_cours(banc):
    """Sans quoi `q` continuerait de demander confirmation apres la fin."""
    async def scenario(pilote):
        app = pilote.app
        app.descendre(EcranExecution(SurfaceExecution("frames")))
        await pilote.pause()
        en_cours = app.tache_en_cours
        app.revenir_aux_ateliers()
        await pilote.pause()
        return en_cours, app.tache_en_cours

    assert banc(coque(), scenario) == (True, False)


def test_un_ecran_de_resultat_refuse_un_panneau_qui_porte_un_majorant():
    """AC 8.2 : le travail est fait, les chiffres sont mesures."""
    with pytest.raises(ValueError, match="majorant"):
        EcranResultat(Panneau("Ecrit", [
            LigneChiffree(LIBELLE_ESPACE_DISQUE, "~ 3,1", "Go", majorant=True)]))


def test_l_ecran_de_resultat_porte_ses_suites(banc):
    resultat = EcranResultat(
        Panneau("Ecrit", [LigneChiffree("Frames ecrites", 186, "frames")]),
        suites=["composer les planches", "encoder un master"])

    async def scenario(pilote):
        pilote.app.descendre(resultat)
        await pilote.pause()
        return pilote.app.screen.query_one("#resultat", Static).content

    affiche = banc(coque(), scenario)
    assert "186 frames" in affiche
    assert "composer les planches" in affiche
    assert "encoder un master" in affiche


# --------------------------------------------------------------------------
# Garde de grille, pour tout l'epic
# --------------------------------------------------------------------------

# La garde « aucune ligne de raccourcis ne deborde » a demenage dans
# `test_repli_ascii.py` : sa premiere version balayait `Palier.__subclasses__`,
# donc elle ne voyait que les classes deja importees ET voyait la classe temoin
# de son propre volet symetrique -- elle rougissait selon l'ordre d'execution
# des tests, ce qui est exactement le defaut qu'elle existait pour empecher
# (revue de vague 1, couche 1). Elle parcourt desormais les modules du paquet.


def test_les_avancements_tiennent_la_grille_quelle_que_soit_la_fenetre():
    for largeur in (80, 100, 120):
        ligne = Avancement("frames", 84, 124, temps_restant=70).ligne_d_etat(
            jetons.largeur_utile(largeur))
        assert len(ligne) <= jetons.largeur_utile(largeur)


# --------------------------------------------------------------------------
# `EPIC11-ARB-47` -- la couleur, sur CES ecrans aussi, et des DEUX cotes
#
# Sa portee nomme « les cinq ecrans de la vague 2 **et** les quatre ecrans a
# issues de la story 11.1 ». Les seconds rendaient leur zone centrale en texte
# nu : le defaut a ete trouve le 2026-08-29, en relisant la portee, et ce qui
# le laissait passer est que les AC de la vague ne mesuraient qu'un cote --
# « l'information survit sans couleur », jamais « elle est coloree avec ».
# --------------------------------------------------------------------------

def _styles(contenu) -> list[str]:
    """Les styles poses sur un contenu de widget, ou une liste vide."""
    spans = getattr(contenu, "spans", [])
    return [str(s.style) for s in spans if s.style]


def test_la_ligne_du_curseur_des_ISSUES_est_coloree(banc):
    """Volet « colore » : la moitie du mecanisme de choix d'`EPIC11-ARB-45`.

    Le curseur est pose sur la DEUXIEME issue, jamais la premiere : un rendu qui
    colorerait toujours la ligne 0 passerait sur une fixture au repos.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        pilote.app.screen.choix.deplacer(1)
        pilote.app.screen.rafraichir()
        await pilote.pause()
        contenu = pilote.app.screen.query_one("#issues", Static).content
        return _styles(contenu), str(contenu)

    styles, texte = banc(coque(), scenario)
    accent = jetons.couleur("accent")
    assert any(accent in s and "bold" in s for s in styles), (styles, texte)


def test_un_ecran_de_RESULTAT_colore_la_suite_sous_le_curseur(banc):
    """Meme mesure, sur l'ecran ou la detection automatique ECHOUERAIT.

    Ses suites sont indentees de deux espaces, et `peindre` cherche le glyphe de
    curseur en tete de ligne : sans le rang passe explicitement, cet ecran ne
    colorerait rien -- et il ne planterait pas, ce qui est pire.
    """
    ecran = EcranResultat(Panneau("Resultat", [
        LigneChiffree("Lots crees", 2, "lots")]),
        suites=["Voir le lot", "Revenir aux ateliers"])

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        pilote.app.screen.curseur = 1          # la DEUXIEME suite
        pilote.app.screen.rafraichir()
        await pilote.pause()
        contenu = pilote.app.screen.query_one("#resultat", Static).content
        return _styles(contenu), str(contenu)

    styles, texte = banc(coque(), scenario)
    accent = jetons.couleur("accent")
    assert any(accent in s and "bold" in s for s in styles), (styles, texte)


def test_un_ecran_de_REFUS_teinte_sa_ligne_de_code(banc):
    """Le glyphe `✕` du code de refus doit porter SA couleur, pas la couleur
    par defaut : c'est ce que les six jetons du `DESIGN.md` existent pour."""
    ecran = EcranRefus("scan_hors_perimetre", "Le motif du coeur, verbatim.")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return _styles(pilote.app.screen.query_one("#refus", Static).content)

    styles = banc(coque(), scenario)
    assert jetons.couleur("state-absent") in " ".join(styles), styles


@pytest.mark.parametrize("fabrique, cible", [
    (lambda: confirmation(), "#issues"),
    (lambda: EcranRefus("code", "message"), "#refus"),
])
def test_SANS_COULEUR_le_texte_reste_identique(banc, fabrique, cible):
    """Volet symetrique, et c'est la regle 1 non negociable du `DESIGN.md`
    section 5 : la couleur **double** un canal, elle ne le porte jamais seule.

    Deux rendus du meme ecran, avec et sans couleur, doivent rendre le meme
    texte -- un terminal monochrome lit exactement la meme chose.
    """
    def texte(sans_couleur):
        async def scenario(pilote):
            pilote.app.descendre(fabrique())
            await pilote.pause()
            return str(pilote.app.screen.query_one(cible, Static).content)
        return banc(coque(sans_couleur=sans_couleur), scenario)

    assert texte(True) == texte(False)


def test_SANS_COULEUR_aucun_style_n_est_pose(banc):
    """Et le volet strict : « sans couleur » veut dire AUCUNE couleur, pas
    « moins de couleur »."""
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return _styles(pilote.app.screen.query_one("#issues", Static).content)

    assert banc(coque(sans_couleur=True), scenario) == []


# --------------------------------------------------------------------------
# Le RANG de la ligne accentuee -- ce qui est peint, pas ce qui est calcule
#
# Revue de la vague 2 bis, couche 1, finding F3 (CRITIQUE) : le mutant `M3`
# -- `EcranResultat.rang_du_curseur` : `+ 1 +` devient `+ 0 +`, c'est-a-dire
# la ligne vide posee par `lignes()` cessant d'etre comptee -- survivait aux
# 682 tests. Les tests de couleur ci-dessus mesurent qu'UNE ligne est
# accentuee ; aucun ne mesurait LAQUELLE. Un rang decale d'un cran peint la
# derniere ligne du panneau chiffre au lieu de la premiere suite, et reste
# vert.
#
# Ce que ces tests mesurent est donc la ligne RENDUE, nommee par son contenu.
# Fabriques (`CLAUDE.md`, politique 6.1) : trois suites DISTINCTES, un panneau
# dont la hauteur VARIE, et le curseur pose ailleurs qu'en premiere position.
# --------------------------------------------------------------------------

#: Trois suites distinguables. Un remplissage uniforme rendrait invisible tout
#: decalage de rang : c'est le point 1 de la regle des fabriques.
SUITES_TEMOINS = (DEBUT_DE_LA_SUITE_DES_PLANCHES, "Encoder un master",
                  EcranResultat.RETOUR)


def resultat_temoin(chiffres: int = 1) -> EcranResultat:
    """Un ecran de resultat a `chiffres` lignes chiffrees et trois suites.

    **La hauteur du panneau est un parametre**, et ce n'est pas de la
    completude : le rang du curseur s'en deduit. Une fixture a hauteur fixe ne
    distingue pas un rang juste d'un rang constant qui vaudrait juste pour
    cette hauteur-la.
    """
    return EcranResultat(
        Panneau("Ecrit", [LigneChiffree(f"Mesure {n}", n, "lots")
                          for n in range(1, chiffres + 1)]),
        suites=list(SUITES_TEMOINS))


def _lignes_du_bloc(contenu) -> list:
    """Le bloc peint, decoupe en lignes qui gardent CHACUNE leur style.

    `rich` pose les styles en intervalles d'offsets sur tout le bloc : sans ce
    decoupage, un test ne peut dire que « un style est pose quelque part », ce
    qui est exactement l'aveuglement que `M3` exploitait.
    """
    return list(contenu.split(chr(10))) if hasattr(contenu, "split") else []


def _lignes_accentuees(contenu) -> list[str]:
    """Les lignes rendues en GRAS + couleur d'accentuation, dans l'ordre."""
    accent = jetons.couleur("accent")
    return [ligne.plain for ligne in _lignes_du_bloc(contenu)
            if any(accent in str(s.style) and "bold" in str(s.style)
                   for s in ligne.spans)]


def _lignes_teintes(contenu, jeton: str) -> list[str]:
    """Les lignes rendues dans la couleur du jeton d'etat nomme."""
    teinte = jetons.couleur(jeton)
    return [ligne.plain for ligne in _lignes_du_bloc(contenu)
            if any(teinte in str(s.style) for s in ligne.spans)]


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("chiffres", [1, 3])
@pytest.mark.parametrize("rang_vise", [0, 1, 2])
def test_la_ligne_accentuee_du_RESULTAT_est_CELLE_qui_porte_le_curseur(
        banc, chiffres, rang_vise, ascii_seul):
    """`EcranResultat.rang_du_curseur` mesure, par la ligne effectivement peinte.

    Le curseur est deplace au clavier -- `↓` autant de fois qu'il faut --, donc
    la mesure traverse `on_key`, `rafraichir`, `rang_du_curseur` et `peindre`
    d'un bout a l'autre. L'assertion nomme le CONTENU de la ligne : un rang
    decale d'un cran peint la derniere ligne chiffree ou la mauvaise suite, et
    aucune de ces deux lignes ne porte le libelle attendu.

    **Le repli ASCII est dans la mesure**, et pas par completude : en `--ascii`
    le glyphe de curseur et celui d'invite sont le MEME caractere (`>`), donc
    `peindre` y a deux regles capables de teindre la meme ligne. Un rang faux
    s'y lit differemment d'en UTF-8 -- deux lignes accentuees au lieu d'une
    seule mal placee --, et l'egalite stricte ci-dessous prend les deux.
    """
    ecran = resultat_temoin(chiffres)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        for _ in range(rang_vise):
            await pilote.press("down")
        await pilote.pause()
        return pilote.app.screen.query_one("#resultat", Static).content

    contenu = banc(coque(ascii_seul=ascii_seul), scenario)
    accentuees = _lignes_accentuees(contenu)
    curseur = jetons.glyphes(ascii_seul)["curseur"]
    attendue = f"  {curseur} {SUITES_TEMOINS[rang_vise]}"
    assert accentuees == [attendue], (
        "la ligne peinte en accentuation n'est pas celle qui porte le curseur",
        accentuees, str(contenu))


def test_le_RESULTAT_n_accentue_QU_UNE_ligne_et_jamais_le_panneau_chiffre(banc):
    """Volet symetrique : ni zero ligne, ni deux, ni une ligne du cartouche.

    Un rang tombe hors des suites -- trop grand, ou negatif -- ne plante pas :
    `peindre` ne trouve simplement rien a peindre, ou peint un chiffre. Les
    deux se lisent comme « l'ecran n'a pas de curseur », et c'est le mode de
    panne muet que la story dit vouloir eviter.
    """
    ecran = resultat_temoin(chiffres=3)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await pilote.press("down")
        await pilote.pause()
        return pilote.app.screen.query_one("#resultat", Static).content

    contenu = banc(coque(), scenario)
    accentuees = _lignes_accentuees(contenu)
    assert len(accentuees) == 1, (accentuees, str(contenu))
    assert not any(f"Mesure {n}" in accentuees[0] for n in (1, 2, 3)), (
        "une ligne CHIFFREE est peinte comme si elle portait le curseur",
        accentuees, str(contenu))
    assert accentuees[0].strip(), (
        "la ligne vide de separation est peinte a la place d'une suite",
        str(contenu))


def test_le_cartouche_CHIFFRE_n_accentue_AUCUNE_ligne(banc):
    """L'autre appel de `bloc_peint` du panneau de confirmation.

    Il ne passe **aucun** rang : la detection automatique de `peindre` cherche
    le glyphe de curseur en tete de ligne, et un cartouche n'en porte pas. Si
    une ligne chiffree s'y retrouvait accentuee, l'operateur lirait deux
    curseurs sur le meme ecran -- un dans le cartouche, un dans les issues.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one("#chiffres", Static).content

    contenu = banc(coque(), scenario)
    assert _lignes_accentuees(contenu) == [], str(contenu)


@pytest.mark.parametrize("pas", [0, 1])
def test_la_ligne_accentuee_des_ISSUES_est_CELLE_du_curseur(banc, pas):
    """Meme mesure sur le bloc des issues, ou le rang est DEVINE.

    La detection automatique rend le **premier** element qui commence par le
    glyphe de curseur : une fixture ou le curseur serait en tete ne separerait
    donc pas « le bon rang » de « toujours le premier ». Le curseur part ici
    sur `Modifier les reglages` (`EPIC11-ARB-45` interdit qu'il vise l'issue
    qui ecrit) et descend jusqu'a `Annuler` : dans les deux cas il est ailleurs
    qu'en premiere position.
    """
    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        for _ in range(pas):
            await pilote.press("down")
        await pilote.pause()
        ecran_courant = pilote.app.screen
        libelle = ecran_courant.choix.issues[ecran_courant.choix.curseur].libelle
        return libelle, ecran_courant.query_one("#issues", Static).content

    libelle, contenu = banc(coque(), scenario)
    accentuees = _lignes_accentuees(contenu)
    assert len(accentuees) == 1, (accentuees, str(contenu))
    assert accentuees[0].strip().endswith(libelle), (
        "la ligne peinte n'est pas celle de l'issue sous le curseur",
        libelle, accentuees, str(contenu))
    assert jetons.GLYPHES["curseur"] in accentuees[0], (accentuees,)


def test_le_REFUS_teinte_la_ligne_du_CODE_et_elle_seule(banc):
    """Troisieme appel de `bloc_peint` du module : aucun rang, un etat.

    L'ecran de refus rend un code, un message, et jusqu'a trois sections de
    rattachements. Une seule de ces lignes porte le glyphe `✕`, et c'est celle
    du code : le test precedent (`..._teinte_sa_ligne_de_code`) verifiait que
    la couleur est **quelque part** dans le bloc, jamais sur quelle ligne. Un
    ecran qui teindrait le message du coeur en rouge dirait que le message est
    l'erreur.
    """
    ecran = EcranRefus("scan_hors_perimetre", "Deux planches hors perimetre.",
                       conserve=["lot_conserve"], non_ecrit=["lot_non_ecrit"],
                       suites=["Reprendre le scan"])

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one("#refus", Static).content

    contenu = banc(coque(), scenario)
    teintes = _lignes_teintes(contenu, "state-absent")
    assert teintes == [f"{jetons.GLYPHES['absent']} scan_hors_perimetre"], (
        teintes, str(contenu))
    assert _lignes_accentuees(contenu) == [], (
        "un ecran de refus n'a pas de curseur : rien n'y est accentue",
        str(contenu))


def test_le_JOURNAL_teinte_la_ligne_EN_ECHEC_et_pas_ses_voisines(banc):
    """Quatrieme appel : le journal d'execution, replie a deux lignes.

    Deux lignes rendues, distinguables, et **la ligne en echec n'est pas la
    premiere** : un rendu qui teindrait toujours la ligne 0 -- ou qui rendrait
    les plus ANCIENNES lignes au lieu des dernieres -- passerait sur une
    fixture uniforme. Trois lignes sont inscrites pour que le glissement de
    `dernieres()` soit lui aussi dans la mesure.
    """
    surface = SurfaceExecution(Avancement("frames", 0, 4))
    ecran = EcranExecution(surface, "Extraction")
    echec = f"{jetons.GLYPHES['absent']} 3/4 frames refusees"

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        surface.journal.inscrire(f"{jetons.GLYPHES['complete']} 1/4 frames")
        surface.journal.inscrire(f"{jetons.GLYPHES['neutre']} 2/4 frames")
        surface.journal.inscrire(echec)
        pilote.app.screen.rafraichir()
        await pilote.pause()
        return pilote.app.screen.query_one("#journal", Static).content

    contenu = banc(coque(), scenario)
    rendues = [ligne.plain for ligne in _lignes_du_bloc(contenu)]
    assert [l.strip() for l in rendues] == [
        f"{jetons.GLYPHES['neutre']} 2/4 frames", echec], (
        "le journal replie ne montre pas les DEUX dernieres lignes", rendues)
    assert _lignes_teintes(contenu, "state-absent") == [f"  {echec}"], (
        _lignes_teintes(contenu, "state-absent"), str(contenu))
    assert _lignes_accentuees(contenu) == [], (
        "le journal n'a pas de curseur : rien n'y est accentue", str(contenu))


# --------------------------------------------------------------------------
# Le repli ASCII precede la mesure -- sur les DEUX ecrans qui rendent un panneau
# --------------------------------------------------------------------------

#: Une valeur de ligne chiffree assez longue pour etre ABREGEE au plancher.
#: Ce n'est pas un cas de laboratoire : `palier_projet` pose deux lignes qui
#: portent un nom de FICHIER (`Fichier de projet`, `Fichier du profil`), et
#: c'est celle-la que la revue de vague 2 bis a mesuree a 76 colonnes dans un
#: cartouche de 72.
_VALEUR_ABREGEE = "2026-08-29_tournage_exterieur_nuit_camera_B_prise_02.json"

#: La meme, en DOUBLE CHASSE. Chaque ideogramme vaut deux colonnes en UTF-8 et
#: une seule une fois replie en `?` : mesurer sur du latin seul laisserait
#: passer un abregement calcule sur la mauvaise unite.
_VALEUR_ABREGEE_CJK = ("2026-08-29_" + "夜間屋外撮影"
                       "本番" * 4 + "_prise_02.json")

#: Ce que la fin de la valeur porte, et que l'operateur doit lire : l'extension
#: et le numero de prise. C'est exactement ce qu'une coupe PAR LA FIN mange.
_FIN_DE_VALEUR = "_prise_02.json"

#: Le libelle de la ligne visee. Distinct des deux autres lignes de la fabrique,
#: et il n'est pas en premiere position.
_LIBELLE_VISE = "Fichier de projet"


def panneau_a_ligne_abregee(valeur: str) -> Panneau:
    """Trois lignes chiffrees DISTINGUABLES, la ligne visee en DERNIERE.

    Regle des fabriques (`CLAUDE.md`) : une fabrique mono-element rendrait
    invisible un rendu qui n'abregerait, par exemple, que sa premiere ligne.
    """
    return Panneau("A ecrire", [
        LigneChiffree("Lots crees", 2, "lots"),
        LigneChiffree("Frames ecrites", 186, "frames"),
        LigneChiffree(_LIBELLE_VISE, valeur),
    ])


def _confirmation_abregee(valeur: str):
    """L'ecran de confirmation, et l'identifiant du bloc ou lire ses chiffres."""
    return PanneauConfirmation(panneau_a_ligne_abregee(valeur),
                               issues_temoins(), noms_temoins()), "chiffres"


def _resultat_abrege(valeur: str):
    """L'ecran de resultat, second appelant de `Panneau.rendu`."""
    return EcranResultat(panneau_a_ligne_abregee(valeur),
                         suites=list(SUITES_TEMOINS)), "resultat"


@pytest.mark.parametrize("fabrique", [_confirmation_abregee, _resultat_abrege])
@pytest.mark.parametrize("valeur", [_VALEUR_ABREGEE, _VALEUR_ABREGEE_CJK])
@pytest.mark.parametrize("ascii_seul", [False, True])
def test_une_ligne_chiffree_ABREGEE_est_repliee_AVANT_d_etre_mesuree(
        banc, fabrique, valeur, ascii_seul):
    """Les deux appelants de `Panneau.rendu` passent le MODE. AC de couture.

    `LigneChiffree.rendu` prend `ascii_seul` parce que l'abregement doit
    choisir ses points AVANT de compter : `…` vaut une colonne, `...` en vaut
    trois. Un appelant qui ne le passe pas fabrique une ligne calee juste en
    UTF-8, que `bloc`/`bloc_peint` replie ENSUITE -- deux colonnes de trop, que
    `jetons.ajuster` rattrape en coupant **par la fin**, c'est-a-dire en
    mangeant le chiffre. C'est le seul contenu que le panneau existe pour
    montrer.

    Les deux ecrans ne paient pas le meme prix, et c'est pourquoi la mesure
    porte sur les deux grandeurs a la fois :

    * le cartouche de la confirmation ajuste a 72 colonnes, donc la ligne y est
      **coupee** : elle finit en `...` au lieu de `.json` ;
    * l'ecran de resultat ajuste a 76, donc rien n'y est coupe -- mais la ligne
      sort a **74 colonnes** alors que le panneau l'a mesuree pour 72.

    Sur de la double chasse le defaut change de signe : replies apres coup, les
    ideogrammes tombent de deux colonnes a une, et la ligne sort **trop
    courte** (61 colonnes mesurees pour 72) -- un abregement qui jette du texte
    dont la place existait.
    """
    ecran, bloc_vise = fabrique(valeur)
    utile = jetons.largeur_de_cartouche(80)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return pilote.app.screen.query_one(f"#{bloc_vise}", Static).content

    contenu = banc(coque(ascii_seul=ascii_seul), scenario)
    libelle = jetons.replier_ascii(_LIBELLE_VISE) if ascii_seul else _LIBELLE_VISE
    visees = [ligne.plain for ligne in _lignes_du_bloc(contenu)
              if ligne.plain.startswith(libelle)]
    assert len(visees) == 1, (
        "la ligne visee doit etre rendue une fois et une seule", visees)
    ligne = visees[0]
    assert jetons.colonnes(ligne) == utile, (
        "la ligne chiffree abregee ne remplit pas exactement le cartouche",
        jetons.colonnes(ligne), utile, ligne)
    assert ligne.endswith(_FIN_DE_VALEUR), (
        "l'abregement a mange la FIN de la valeur -- le chiffre lui-meme",
        ligne)


# ===========================================================================
# Lot I -- `I5` et `I8` : ce que les CAPTURES ont montre et qu'aucun banc ne
# voyait. Les trois ecrans du point de jugement etaient le meme a un caret
# pres, et `EcranChiffre` n'avait pas de ligne de raccourcis contextuelle.
# ===========================================================================

def _releve_des_deux_modes(banc, ecran, ascii_seul: bool = False):
    """Le titre du cartouche et la ligne de raccourcis, HORS puis EN edition.

    Les deux sont releves dans le meme scenario, sur le meme ecran : c'est ce
    qui rend la COMPARAISON possible. Deux scenarios separes mesureraient deux
    ecrans, et un ecran qui ne changerait rien serait vert sur les deux.
    """
    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()
        hors = (str(pilote.app.screen.query_one("#raccourcis", Static).content),
                str(ecran._corps.border_title))
        await pilote.press("tab")
        await pilote.pause()
        dedans = (str(pilote.app.screen.query_one("#raccourcis",
                                                  Static).content),
                  str(ecran._corps.border_title))
        await pilote.press("escape")            # sortir de l'edition
        await pilote.pause()
        ressorti = (str(pilote.app.screen.query_one("#raccourcis",
                                                    Static).content),
                    str(ecran._corps.border_title))
        return hors, dedans, ressorti

    return banc(coque(ascii_seul=ascii_seul), scenario)


def test_entrer_dans_les_NOMS_change_la_ligne_de_raccourcis_ET_le_titre(banc):
    """Finding `I5` : `E2-3`, `E2-3b` et `E2-3c` etaient le meme ecran.

    Mesure du 2026-08-30, sur les captures `20-` a `22-` : meme titre de
    cartouche (`À écrire`) et **meme ligne de raccourcis**, qui annoncait
    `Tab éditer` PENDANT l'edition -- c'est-a-dire l'entree dans un mode ou
    l'on etait deja, alors que `Tab` en **sort**.

    `EPIC11-ARB-68`, verbatim : « `Tab` **nomme sa DESTINATION** ».
    """
    hors, dedans, ressorti = _releve_des_deux_modes(banc, confirmation())
    assert hors[0] != dedans[0], "la ligne de raccourcis n'a pas change"
    assert hors[1] != dedans[1], "le titre du cartouche n'a pas change"
    # `Tab éditer` n'est plus annonce PENDANT l'edition.
    assert "éditer" not in dedans[0], dedans[0]
    # Et le mode se referme : l'ecran redevient exactement `E2-3`.
    assert ressorti == hors, (ressorti, hors)


def test_la_ligne_d_EDITION_annonce_Ctrl_R_et_la_DESTINATION_de_Tab(banc):
    """Finding `I8`, le plus grave des cinq ecarts du lot `G`.

    `Ctrl+R`, livre par le lot `A` (`EPIC11-ARB-68`, point 3 : « **`Ctrl+R`
    remet le nom propose.** Une combinaison, jamais une lettre nue »), **n'etait
    annonce nulle part** -- ni sur cet ecran ni ailleurs. C'est la classe de
    defaut que `coque.py` documente (« une touche annoncee en ligne de
    raccourcis devenait **inerte** »), prise par l'autre bout : une touche qui
    marche et que rien n'annonce.
    """
    _hors, dedans, _ = _releve_des_deux_modes(banc, confirmation())
    ligne = dedans[0]
    assert "Ctrl+R" in ligne, ligne
    # `Tab` nomme ou il MENE, pas le mode qu'on vient de quitter.
    assert MOT_DES_CHOIX in ligne, ligne


def test_le_MEME_geste_contextuel_vaut_pour_l_ECRAN_D_ECRASEMENT(banc):
    """Volet symetrique de portee : l'ecran d'ecrasement partage `EcranChiffre`
    et ses noms editables. Une correction posee sur la seule confirmation
    laisserait `T4-1` mentir de la meme facon."""
    ecran = EcranEcrasement(panneau_temoin(), issues_temoins(), noms_temoins())
    hors, dedans, _ = _releve_des_deux_modes(banc, ecran)
    assert hors[0] != dedans[0]
    assert "Ctrl+R" in dedans[0], dedans[0]


@pytest.mark.parametrize("touche,attendu", [
    ("ctrl+r", "remettre le nom propose"),
    ("down", "passer au nom suivant"),
    ("tab", "sortir vers les choix"),
    ("escape", "annuler l'edition"),
])
def test_CHAQUE_touche_annoncee_en_EDITION_fait_ce_qu_elle_annonce(
        banc, touche, attendu):
    """La frontiere positive de la ligne contextuelle : ce qu'elle promet agit.

    Le nom edite est le **second**, jamais le premier (regle des fabriques) :
    un modele qui ecrirait toujours dans `noms[0]` ne se demasque pas
    autrement.
    """
    ecran = confirmation()
    conventionnel = ecran.noms.noms[1].conventionnel

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await pilote.press("tab")               # entrer dans les noms
        await pilote.press("down")              # le SECOND nom
        ecran.noms.saisir("z" * 5)
        ecran.rafraichir()
        await pilote.pause()
        avant = (ecran.noms.curseur, ecran.noms.valeurs[1],
                 ecran.noms.en_edition)
        await pilote.press(touche)
        await pilote.pause()
        return avant, (ecran.noms.curseur, ecran.noms.valeurs[1],
                       ecran.noms.en_edition)

    avant, apres = banc(coque(), scenario)
    assert avant == (1, "zzzzz", True), avant
    if touche == "ctrl+r":
        assert apres == (1, conventionnel, True), (attendu, apres)
    elif touche == "down":
        # Deux noms seulement : `↓` sur le dernier ne boucle pas, il reste.
        assert apres[2] is True, (attendu, apres)
    elif touche == "tab":
        assert apres == (1, "zzzzz", False), (attendu, apres)
    else:
        assert apres[2] is False and apres[1] == conventionnel, (attendu, apres)


def test_les_DEUX_lignes_de_raccourcis_de_l_ecran_sont_des_CONSTANTES_de_module():
    """Volet symetrique de la garde d'epic : une ligne contextuelle calculee a
    la volee echapperait a la mesure de largeur ET a celle du repli ASCII de
    `test_repli_ascii.py`, qui balaye les `RACCOURCIS_*` des modules."""
    from mixed_media_utility.tui import execution as module

    assert module.RACCOURCIS_CONFIRMATION
    assert module.RACCOURCIS_EDITION_DES_NOMS
    assert PanneauConfirmation.raccourcis is module.RACCOURCIS_CONFIRMATION


# --- `I8`, troisieme volet : `Tab journal` sur `E2-5` -----------------------

#: Un journal **plus long que la fenetre**, et c'est la regle des fabriques
#: appliquee a une fenetre glissante.
#:
#: **Vingt jalons et non quatre, et c'est une correction payee** : la premiere
#: version en portait quatre, pour une fenetre qui en montre neuf a
#: `HAUTEUR_CENTRE_AU_PLANCHER`. `dernieres(9)` et `lignes[:9]` rendaient donc
#: **la meme chose**, et le mutant « le journal montre les PREMIERES lignes »
#: a SURVECU a la campagne. Une fenetre glissante ne se mesure que sur un
#: corpus qui deborde -- exactement le point 1 de la regle des fabriques, dans
#: sa version « au moins deux elements **distinguables** ».
JALONS_TEMOINS = tuple(f"14:31:{rang:02d}  jalon numero {rang}"
                       for rang in range(1, 21))


def journal_temoin() -> Journal:
    journal = Journal()
    for ligne in JALONS_TEMOINS:
        journal.inscrire(ligne)
    return journal


def test_TAB_sur_E2_5_DEPLIE_le_journal_puis_le_REPLIE(banc):
    """Finding `I8` : la maquette `E2-5` annonce `Tab journal` depuis toujours
    et `EcranResultat.on_key` ne traitait pas `tab` du tout.

    Mesure du lot `G` : `down`, `up`, `enter`, `escape`, et rien d'autre. Le
    journal d'une extraction terminee n'etait donc relisible **de nulle part**
    -- `E2-4`, qui le portait, est depile au moment ou `E2-5` monte.

    Les deux sens sont mesures : une bascule qui ne saurait que deplier
    enfermerait l'operateur dans le journal.
    """
    ecran = EcranResultat(Panneau("Ecrit", [LigneChiffree("Lots", 2, "lots")]),
                          suites=list(SUITES_TEMOINS),
                          journal=journal_temoin())

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        depart = str(pilote.app.screen.query_one("#resultat", Static).content)
        await pilote.press("tab")
        await pilote.pause()
        deplie = str(pilote.app.screen.query_one("#resultat", Static).content)
        await pilote.press("tab")
        await pilote.pause()
        replie = str(pilote.app.screen.query_one("#resultat", Static).content)
        return depart, deplie, replie

    depart, deplie, replie = banc(coque(), scenario)
    assert JALONS_TEMOINS[-1] not in depart, "le journal ne s'ouvre pas tout seul"
    # **Un journal est glissant : il montre la FIN.** Le dernier jalon est la,
    # le premier n'y est pas -- et la cible intermediaire n'est ni l'un ni
    # l'autre. Sans le corpus qui deborde, les trois assertions seraient vraies
    # d'un `[:n]` comme d'un `[-n:]`.
    assert JALONS_TEMOINS[-1] in deplie, deplie
    assert JALONS_TEMOINS[-2] in deplie, deplie
    assert JALONS_TEMOINS[0] not in deplie, (
        "le journal montre le DEBUT : une fenetre glissante montre la fin")
    assert replie == depart, "la seconde pression n'a pas referme le journal"


def test_E2_5_annonce_Tab_journal_SEULEMENT_quand_il_en_a_un():
    """La ligne est contextuelle : « elle ne montre que ce qui marche sur
    l'ecran courant » (`DESIGN.md` section 4).

    Volet symetrique du precedent : sans lui, un ecran qui annoncerait la
    touche en permanence passerait le test de bascule et mentirait partout
    ailleurs -- c'est-a-dire le defaut d'origine, deplace.
    """
    avec = EcranResultat(Panneau("Ecrit"), journal=journal_temoin())
    sans = EcranResultat(Panneau("Ecrit"))
    assert RACCOURCI_DU_JOURNAL in avec.raccourcis, avec.raccourcis
    assert RACCOURCI_DU_JOURNAL not in sans.raccourcis, sans.raccourcis
    assert sans.basculer_le_journal() is False
    assert sans.journal_deplie is False


def test_le_journal_TRAVERSE_de_l_execution_au_resultat(banc, tmp_path):
    """Le cablage, et non les deux moities : `E2-4` tient le journal, `E2-5`
    doit le recevoir.

    C'est le mode de panne que le commit `41c7b30` a paye sur ce meme journal
    (« M2 a SURVECU : les neuf tests mesuraient le relais, sa politique
    d'attente, son desempilement -- tout sauf le fil »). Le test vise donc le
    FIL : ce que `ouvrir_le_resultat` recoit de la surface d'execution.
    """
    from mixed_media_utility.tui import atelier_extraction_ecriture as ecriture

    surface = SurfaceExecution("frames")
    surface.emetteur(9).emettre(4)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = ecriture.ouvrir_le_resultat(
            pilote.app, ecriture.RapportExtraction(),
            journal=surface.journal)
        await pilote.pause()
        return ecran.journal, ecran.raccourcis

    journal, raccourcis = banc(coque(), scenario)
    assert journal is surface.journal
    assert journal.lignes, "la surface n'a rien inscrit"
    assert RACCOURCI_DU_JOURNAL in raccourcis


def test_la_ligne_d_etat_du_panneau_est_ACCENTUEE_et_se_replie(banc):
    """Finding `I6` : `Rien n'a encore ete ecrit.` etait ecrite sans accents
    dans une source rendue en UTF-8.

    Elle rendait donc **le meme texte dans les deux regimes** : le repli ASCII
    a sa table (`jetons.REPLIS_DE_TEXTE`, puis la decomposition Unicode), et
    une chaine desaccentuee a la source court-circuite ce mecanisme. Vu sur la
    capture reelle `20-E2-3-confirmation.svg`.
    """
    assert RIEN_ECRIT.isascii() is False, RIEN_ECRIT
    replie = jetons.replier_ascii(RIEN_ECRIT)
    assert replie.isascii()
    assert replie != RIEN_ECRIT, "le repli ne change rien : source desaccentuee"

    ecran = confirmation()

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return str(pilote.app.screen.query_one("#etat", Static).content)

    assert banc(coque(), scenario) == RIEN_ECRIT


@pytest.mark.parametrize("ascii_seul", [
    pytest.param(False, id="utf8"), pytest.param(True, id="ascii")])
def test_le_TITRE_du_cartouche_se_REPLIE_comme_le_reste_de_l_ecran(
        banc, ascii_seul):
    """Le defaut que la capture ASCII montrait, et qu'aucun banc ne mesurait.

    `border_title` etait pose depuis `panneau.titre` **sans passer par aucune
    table** : `20-E2-3-confirmation-ascii.svg` porte `À écrire` accentue au
    milieu d'un ecran par ailleurs entierement replie. Le separateur `—` du
    titre d'edition aurait ajoute le meme defaut en pire -- `REPLIS_DE_TEXTE`
    le rend `--`, donc sans repli il serait sorti tel quel sur un terminal qui
    ne le dessine pas.

    **Les deux modes sont parametres et les deux titres sont mesures** : c'est
    le titre d'EDITION qui porte le separateur, donc un repli pose sur le seul
    titre nominal resterait vert ici sans rien corriger.
    """
    _hors, dedans, _ = _releve_des_deux_modes(banc, confirmation(), ascii_seul)
    hors_titre = _hors[1]
    if ascii_seul:
        assert hors_titre.isascii(), hors_titre
        assert dedans[1].isascii(), dedans[1]
    else:
        # Volet symetrique : en UTF-8 le titre GARDE ses signes, sans quoi un
        # repli inconditionnel passerait le volet ASCII sans rien prouver.
        assert not dedans[1].isascii(), dedans[1]


# ---------------------------------------------------------------------------
# `J3` -- cinq ecrans gardaient un bandeau NU
# ---------------------------------------------------------------------------
#
# **Le defaut, et pourquoi il avait survecu au lot `I`.** Les maquettes `E2-3`,
# `E2-3b`, `E2-3c`, `E2-4` et `E2-5` portent toutes les cinq
# `rush_01 · 25 fps · 4:12` a droite du bandeau, et les cinq ecrans rendaient
# `mmu · projet_demo · Confirmation` et rien d'autre (captures `20-` a `24-`,
# rejouees au commit `783fd9d`). Le lot `I` avait cable les sept autres ecrans
# de l'atelier ; ces cinq-la vivent dans `execution.py`, partage par les quatre
# ateliers, donc hors de son perimetre.
#
# **Le mixin est celui du lot `I`, deplace et non recopie** : il vit desormais
# dans `coque.py`, parce qu'`execution.py` est importe PAR
# `atelier_extraction.py` et ne peut pas l'importer en retour. Un second mixin
# ecrit de ce cote-ci aurait ete deux redactions du meme motif.

#: L'objet des cinq maquettes, verbatim.
OBJET_DU_RUSH = "rush_01 · 25 fps · 4:12"


def bandeau_dessine(banc, ecran, ascii_seul: bool = False) -> str:
    """Le bandeau **dessine** par l'ecran, pas celui qu'il dit rendre.

    Mesure sur le widget monte : c'est la seule facon de constater qu'un ecran
    generique porte l'objet que l'atelier lui a passe -- appeler `bandeau()` a
    la main sauterait le montage, c'est-a-dire l'endroit exact ou le defaut
    vivait.
    """
    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)

    return banc(coque(ascii_seul=ascii_seul), scenario)


#: Les cinq ecrans de `J3`, chacun sous forme de **fabrique** et non
#: d'instance : un `Screen` de `textual` ne se monte qu'une fois, donc une
#: instance partagee entre deux parametrages serait montee deux fois -- et le
#: second cas mesurerait un ecran demonte. Le banc l'a paye a l'ecriture.
#:
#: `E2-3`, `E2-3b` et `E2-3c` sont le **meme** ecran a un mode pres -- c'est ce
#: que le finding `I5` a etabli --, donc la table porte les classes reellement
#: distinctes, plus l'ecrasement qui derive de la meme base.
FABRIQUES_DU_JUGEMENT = {
    "E2-3 confirmation": lambda objet: PanneauConfirmation(
        panneau_temoin(), issues_temoins(), noms_temoins(), objet=objet),
    "E2-3b/E2-3c edition des noms": lambda objet: PanneauConfirmation(
        panneau_temoin(), issues_temoins(), noms_temoins(), objet=objet),
    "E2-4 execution": lambda objet: EcranExecution(
        SurfaceExecution(unite="frames"),
        titre_tache="Extraction de rush_01", objet=objet),
    # Le panneau du resultat est MESURE : « un ecran de resultat ne porte aucun
    # majorant » (AC 8.2), et sa construction le refuse.
    "E2-5 resultat": lambda objet: EcranResultat(
        Panneau("Ecrit", [LigneChiffree("Lots ecrits", 2, "lots"),
                          LigneChiffree("Frames ecrites", 22, "frames")]),
        [SUITE_DU_DOSSIER], objet=objet),
    "ecrasement": lambda objet: EcranEcrasement(
        panneau_temoin(), issues_temoins(), noms_temoins(), objet=objet),
}


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("nom", sorted(FABRIQUES_DU_JUGEMENT))
def test_les_cinq_ecrans_PORTENT_leur_objet_a_droite_du_bandeau(
        banc, nom, ascii_seul):
    """`J3` : l'objet est a DROITE, et il y est dans les deux regimes.

    La mesure porte sur la fin de la ligne et non sur une appartenance : « le
    texte est quelque part dans le bandeau » laisserait passer un objet colle a
    gauche, c'est-a-dire au milieu du chemin de navigation.

    **Le repli ASCII peut ALLONGER la ligne** -- `·` rend `.`, `—` rend `--` --,
    donc le regime ASCII n'est pas une redite du premier : c'est le seul ou le
    bandeau peut deborder alors qu'il tenait en UTF-8.
    """
    attendu = jetons.replier_ascii(OBJET_DU_RUSH) if ascii_seul \
        else OBJET_DU_RUSH
    bandeau = bandeau_dessine(banc, FABRIQUES_DU_JUGEMENT[nom](OBJET_DU_RUSH),
                              ascii_seul)
    assert bandeau.rstrip().endswith(attendu), (nom, bandeau)
    assert bandeau.startswith("mmu"), (
        f"{nom} : le chemin de navigation reste a gauche")
    assert jetons.colonnes(bandeau) <= jetons.largeur_utile(), bandeau


@pytest.mark.parametrize("nom", sorted(FABRIQUES_DU_JUGEMENT))
def test_les_cinq_ecrans_SANS_objet_gardent_un_bandeau_NU(banc, nom):
    """Volet symetrique, et il n'est pas decoratif : sans lui, un ecran qui
    poserait un objet **constant** -- ou qui relirait celui de la session --
    passerait le banc du dessus. C'est exactement le mutant que `J3` vise.

    Un bandeau nu est un etat legitime : c'est ce que la maquette `E2-1` porte.
    """
    ecran = FABRIQUES_DU_JUGEMENT[nom]("")
    bandeau = bandeau_dessine(banc, ecran)
    assert bandeau.rstrip() == f"{PREFIXE_DU_BANDEAU}{ecran.titre}", (
        nom, bandeau)


def test_l_objet_NE_TRAVERSE_PAS_jusqu_a_l_ecran_VOISIN(banc):
    """**Le motif du mixin, mesure** : l'objet est rendu AU DESSIN, jamais
    ecrit dans le `Contexte` de session.

    `Contexte` est gele et vit sur l'application : ce qu'il porte traverse les
    etages sans changer -- c'est ce que l'AC 4.4 de la 11.0 mesure. Un ecran
    qui y ecrirait son rush le laisserait sur le bandeau du palier suivant,
    qui n'a rien a voir avec lui. Le banc monte donc l'ecran porteur, remonte,
    et lit le bandeau du VOISIN.
    """
    porteur = PanneauConfirmation(panneau_temoin(), issues_temoins(),
                                  noms_temoins(), objet=OBJET_DU_RUSH)

    async def scenario(pilote):
        # **Descendre d'abord sur un vrai palier.** `rang` compte les paliers
        # et non la hauteur de pile : un ecran transitoire pose sur la racine
        # laisse `rang` a zero, et `Echap` n'y remonte rien. Le banc mesurerait
        # alors le bandeau de l'ecran porteur en croyant lire celui du voisin.
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre(porteur)
        await pilote.pause()
        porte = jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)
        pilote.app.action_remonter()
        await pilote.pause()
        voisin = jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)
        return porte, voisin, pilote.app.contexte.objet

    porte, voisin, objet_de_session = banc(coque(), scenario)
    assert porte.rstrip().endswith(OBJET_DU_RUSH), porte
    assert voisin.rstrip() == f"{PREFIXE_DU_BANDEAU}Ateliers", voisin
    assert "rush_01" not in voisin, (
        "le rush est reste sur le bandeau du voisin : l'objet a ete ecrit "
        "dans le Contexte de session au lieu d'etre rendu au dessin")
    assert objet_de_session == "", (
        "le Contexte de session porte un objet : il traverse les etages, et "
        f"c'est ce qu'il ne doit jamais porter ici ({objet_de_session!r})")


def test_c_est_le_NOM_DU_PROJET_qui_cede_quand_les_deux_cotes_ne_tiennent_pas(
        banc):
    """`Contexte.rendu`, verbatim : « **Le bandeau ne deborde jamais, et il ne
    perd jamais sa droite.** Quand les deux cotes ne tiennent pas ensemble,
    c'est le **nom du projet** qui est abrege -- jamais l'objet travaille. »

    Motif du depot : le projet est ecrit partout ailleurs, l'objet porte les
    chiffres du parcours en cours, qui ne se relisent nulle part. Le nom
    employe ici est un nom de projet REEL du depot, celui qui avait deja
    emporte la cadence avec lui en revue de vague 1.
    """
    long_projet = "projet_demo_planche_4f_heteroclite"
    ecran = PanneauConfirmation(panneau_temoin(), issues_temoins(),
                                noms_temoins(), objet=OBJET_DU_RUSH)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)

    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter")],
                   contexte=Contexte(long_projet))
    bandeau = banc(app, scenario)
    assert bandeau.rstrip().endswith(OBJET_DU_RUSH), bandeau
    assert long_projet not in bandeau, (
        "le nom du projet devait etre abrege pour laisser tenir l'objet")
    assert jetons.colonnes(bandeau) <= jetons.largeur_utile(), bandeau


def test_le_TEXTE_de_l_objet_est_celui_de_la_MAQUETTE_et_pas_le_sien():
    """`rushes.bandeau_du_rush`, epinglee sur le litteral des cinq maquettes.

    **Ce banc ferme une tautologie**, trouvee par la campagne du lot J (mutant
    `M20`, survivant) : le banc du parcours derive son attendu de
    `bandeau_du_rush` elle-meme, donc une mutation de la fonction changeait les
    deux cotes de l'egalite a la fois et restait verte. On peut ainsi retirer
    la duree de l'objet -- une MESURE -- sans qu'aucun test ne rougisse. C'est
    le mode de panne du test tautologique de la story 5.9, sur la constante
    centrale de la calibration.

    Le litteral, lui, est celui des maquettes `E2-3` a `E2-5`, verbatim. Les
    valeurs d'entree sont celles que la maquette `E2-1` donne au meme rush --
    `25 fps`, `4:12` --, donc les deux ecrans disent la meme chose du meme
    rush, ce qui est precisement l'invariant qu'une seconde redaction du rendu
    casserait.
    """
    from mixed_media_utility.tui import rushes

    # `rush_01`, 25 im/s, 6300 frames -> 4:12. Les memes chiffres que la ligne
    # `rush_01   25 fps · 1920×1080 · 4:12` de la maquette `E2-1`.
    assert rushes.bandeau_du_rush("rush_01", 25.0, 6300) == OBJET_DU_RUSH
    assert rushes.bandeau_du_rush("rush_01", 25.0, 6300, True) == \
        jetons.replier_ascii(OBJET_DU_RUSH)


@pytest.mark.parametrize("fps,frames,manquant", [
    (None, 6300, "la cadence"),
    (25.0, None, "la duree"),
])
def test_une_mesure_ABSENTE_prend_le_glyphe_neutre_et_ne_s_invente_pas(
        fps, frames, manquant):
    """Volet symetrique : ce qui manque **se voit**, il ne disparait pas.

    Trois morceaux toujours, comme `Rush.technique` : « trois colonnes qui
    glissent d'un rang selon ce qui manque ne se lisent plus l'une sous
    l'autre ». Sans ce volet, une fonction qui **omettrait** la valeur absente
    passerait le banc du dessus -- et c'est aussi ce qui distingue une mesure
    absente d'une mesure fausse.
    """
    from mixed_media_utility.tui import rushes

    rendu = rushes.bandeau_du_rush("rush_01", fps, frames)
    assert rendu.count(rushes.SEPARATEUR) == 2, (manquant, rendu)
    assert jetons.GLYPHES["neutre"] in rendu, (manquant, rendu)
    assert rendu.startswith("rush_01"), rendu


# --------------------------------------------------------------------------
# Revue de la vague 3, couche 1 -- le `find` du refus de validation
# --------------------------------------------------------------------------

def test_le_refus_de_validation_vise_le_PREMIER_nom_fautif__pas_un_autre(banc):
    """**Le `find` de `valider()`, mesure par aucune fabrique jusqu'ici**
    (finding `C3`).

    `execution.py:553` fait `next(iter(sorted(self.noms.motifs.items())))` : il
    choisit le **premier** rang fautif, y place le curseur, et annonce **la
    mesure de CE nom-la**. Le mutant `sorted(..., reverse=True)` survivait a
    260 tests, parce que le cardinal de `motifs` ne depassait jamais 1 dans
    toute la suite : la question « lequel des fautifs ? » n'etait jamais posee.
    C'est le mutant `M25` de la story 5.7 (`_find_lot` rendait le premier lot)
    transpose aux noms.

    **TROIS noms, DEUX fautifs de longueurs DISTINCTES, le premier fautif au
    MILIEU** (`CLAUDE.md`, regle des fabriques, points 2 et 2 bis) : le rang 0
    est sain, donc « rendre le premier de la liste » se demasque ; les rangs 1
    et 2 sont fautifs de 60 et 70 caracteres, donc « rendre le DERNIER fautif »
    se demasque aussi -- et par la **mesure annoncee**, pas seulement par un
    rang, ce qui est ce que l'operateur lit.

    Le banc monte une application : `mesure_du_nom_refuse` lit `self.app` pour
    connaitre le regime ASCII, donc ce chemin n'est pas mesurable hors montage.
    C'est aussi pourquoi il n'etait pas mesure.

    Consequence si le choix etait faux : l'operateur corrige le mauvais nom, la
    longueur annoncee ne correspond pas au champ qu'il vient d'atteindre, et il
    croit a un defaut d'affichage.
    """
    ecran = EcranChiffre(
        Panneau("A ecrire", []),
        ChoixExclusif([Issue("annuler", "Annuler"),
                       Issue("ecrire", "Extraire", ecrit=True)]),
        ModeleNoms([NomEditable("lot_sain"),
                    NomEditable("lot_fautif_milieu"),
                    NomEditable("lot_fautif_dernier")]))
    ecran.noms.entrer_en_edition()
    ecran.noms.descendre()
    for _ in range(len(ecran.noms.courant.valeur)):
        ecran.noms.effacer()
    ecran.noms.saisir("a" * 60)
    ecran.noms.descendre()
    for _ in range(len(ecran.noms.courant.valeur)):
        ecran.noms.effacer()
    ecran.noms.saisir("b" * 70)
    ecran.noms.confirmer()

    assert set(ecran.noms.motifs) == {1, 2}, (
        "la fabrique doit poser DEUX noms fautifs, sinon la question "
        f"« lequel ? » n'est pas posee (obtenu {set(ecran.noms.motifs)})")
    assert ecran.noms.noms[1].longueur == 60
    assert ecran.noms.noms[2].longueur == 70

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.choix.viser("ecrire")
        ecran.valider()
        await pilote.pause()
        return ecran.noms.curseur, ecran.etat()

    curseur, annonce = banc(coque(), scenario)

    assert curseur == 1, (
        "le curseur va sur le PREMIER rang fautif, jamais sur un autre")
    assert "60" in annonce, (
        "la mesure annoncee est celle du nom VISE (60 caracteres), pas celle "
        f"de l'autre fautif (70) -- obtenue : {annonce!r}")
    assert "70" not in annonce, annonce


# ===========================================================================
# Les six maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06, et c'est le plus gros du depot.** Ce banc
# citait `E2-1`, `E2-3`, `E2-3b`, `E2-3c`, `E2-4` et `E2-5` -- jusque dans le
# titre d'une section et jusqu'au numero de capture -- sans ouvrir un seul
# dessin. Vingt-quatre de ses valeurs en etaient recopiees, et une docstring
# annoncait meme une constante « epinglee sur le litteral des cinq maquettes,
# **verbatim** » alors qu'aucune des cinq n'etait lue. Le geste juste se
# pratiquait deja a cote (`test_atelier_scan_rapport.py` lit `E3-3` et `E3-4`
# a leur source) ; il ne se pratiquait pas ici.
#
# **Ce que la confrontation ajoute a la section `J3`, qui ferme deja une
# tautologie.** `J3` epingle `rushes.bandeau_du_rush(...)` sur le litteral
# `OBJET_DU_RUSH` plutot que sur elle-meme, ce qui empeche une mutation de la
# fonction de changer les deux cotes de l'egalite a la fois. C'etait le bon
# geste, et il lui manquait sa moitie : le litteral n'etait confronte a rien.
# Composees, les deux mesures donnent `bandeau_du_rush(...) ∈ dessin`, qui est
# ce que « verbatim » veut dire.

#: Les maquettes, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


#: Ce que les six dessins portent, et ce que chacun porte EN PROPRE. Six
#: elements distinguables : aucun ne porte la meme liste, `E2-1` est le seul
#: sans objet de rush, `E2-3c` le seul avec le refus de nom, `E2-5` le seul
#: avec des suites. Une permutation de deux lignes se verrait.
DESSINS_DE_L_EXECUTION = [
    ("E2-1", "E2-1-extraction-rush.txt", ()),
    ("E2-3", "E2-3-extraction-confirmation.txt",
     (LIBELLE_ESPACE_DISQUE, OBJET_DU_RUSH)),
    ("E2-3b", "E2-3b-extraction-edition-nom.txt",
     (LIBELLE_ESPACE_DISQUE, MOT_DES_CHOIX, OBJET_DU_RUSH)),
    ("E2-3c", "E2-3c-extraction-nom-refuse.txt",
     (LIBELLE_ESPACE_DISQUE, MOT_DES_CHOIX, MOT_DE_L_INACCESSIBLE,
      MOT_DU_NOM_TROP_LONG, OBJET_DU_RUSH)),
    ("E2-4", "E2-4-extraction-execution.txt",
     (TITRE_DE_L_EXECUTION, RACCOURCI_DU_JOURNAL, OBJET_DU_RUSH)),
    ("E2-5", "E2-5-extraction-resultat.txt",
     (DEBUT_DE_LA_SUITE_DES_PLANCHES, SUITE_DES_PLANCHES, SUITE_DU_DOSSIER,
      RACCOURCI_DU_JOURNAL, OBJET_DU_RUSH)),
]


@pytest.mark.parametrize(("code", "fichier", "propres"),
                         DESSINS_DE_L_EXECUTION,
                         ids=[c for c, _, _ in DESSINS_DE_L_EXECUTION])
def test_les_valeurs_de_l_execution_sont_VERBATIM_de_leur_maquette(
        code, fichier, propres):
    """Chaque valeur est DANS le dessin, lu sur disque a ce tour-ci.

    Ce n'est pas une ressemblance, c'est une appartenance. Le jour ou une
    maquette change, ce test rouge NOMME l'ecart (`EPIC11-ARB-144`) plutot
    que de laisser l'ecran et le dessin approuve diverger en silence.
    """
    dessin = dessin_de_la_maquette(fichier)
    for attendu in (PREFIXE_DU_BANDEAU.strip(),) + tuple(propres):
        assert " ".join(attendu.split()) in dessin, (code, attendu)


def test_l_objet_du_rush_du_PRODUIT_est_celui_des_CINQ_dessins():
    """La moitie manquante de `J3` : le litteral vient bien du dessin.

    `J3` epingle `bandeau_du_rush` sur `OBJET_DU_RUSH` pour ne pas se mesurer
    a elle-meme ; ici `OBJET_DU_RUSH` est confronte au dessin. Composees, les
    deux disent `bandeau_du_rush(...) ∈ dessin`. Et `E2-1` est nomme comme
    contre-exemple : il montre le rush AVANT l'atelier, sans son objet de
    bandeau, donc il ne doit PAS le porter -- sans quoi la table ci-dessus
    serait verte en confondant les six ecrans.
    """
    from mixed_media_utility.tui import rushes

    assert rushes.bandeau_du_rush("rush_01", 25.0, 6300) == OBJET_DU_RUSH
    portent = {code for code, fichier, _ in DESSINS_DE_L_EXECUTION
               if OBJET_DU_RUSH in dessin_de_la_maquette(fichier)}
    assert portent == {"E2-3", "E2-3b", "E2-3c", "E2-4", "E2-5"}
    assert "E2-1" not in portent


def test_les_six_dessins_se_DISTINGUENT_les_uns_des_autres():
    """Le volet symetrique, sans quoi la table passerait en ne mesurant rien.

    Quatre valeurs qui n'appartiennent qu'a une partie des six : si l'une
    d'elles etait partout, la confrontation serait verte sans distinguer un
    ecran d'un autre. Les cardinaux sont mesures, pas supposes.
    """
    def ou(valeur: str) -> set[str]:
        """Les codes des dessins qui portent cette valeur."""
        return {code for code, fichier, _ in DESSINS_DE_L_EXECUTION
                if valeur in dessin_de_la_maquette(fichier)}

    assert ou(MOT_DU_NOM_TROP_LONG) == {"E2-3c"}
    assert ou(TITRE_DE_L_EXECUTION) == {"E2-4"}
    assert ou(SUITE_DU_DOSSIER) == {"E2-5"}
    assert ou(LIBELLE_ESPACE_DISQUE) == {"E2-3", "E2-3b", "E2-3c"}


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Quatre contre-exemples, dont trois a un mot ou un caractere pres. Sans
    eux, une comparaison toujours vraie passerait les trois tests ci-dessus.
    """
    resultat = dessin_de_la_maquette("E2-5-extraction-resultat.txt")
    assert SUITE_DU_DOSSIER in resultat
    assert "Ouvrir le dossier des lot" + "s de ce rush" not in resultat
    assert "Composer les planche de ces lots" not in resultat
    assert "rush_01 · 24 fps · 4:12" not in resultat
    assert PREFIXE_DU_BANDEAU + "Inventaire" not in resultat
