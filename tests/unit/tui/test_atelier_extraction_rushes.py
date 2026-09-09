# -*- coding: utf-8 -*-
"""Story 11.4, lot E1-E2 -- `E2-1` et le relink, montes.

Le modele pur est mesure a cote (`test_rushes.py`) ; ce banc-ci mesure ce que
le modele ne peut pas dire : **le chemin clavier**, le couplage a l'explorateur,
et le fait que rien n'est ecrit avant validation.

**La regle des fabriques s'applique aux ecrans comme aux modeles** : les
manifestes portent trois rushes distinguables, l'absent n'est jamais le
premier, et le cas a deux absents place la cible en seconde position.
"""
import json
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import relink
from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.tui import atelier_extraction, jetons, rushes
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

from outils_frontiere import identifiants


# ---------------------------------------------------------------------------
# Fabriques -- trois rushes distinguables, l'absent en TROISIEME position
# ---------------------------------------------------------------------------

def rush(rush_id, *, fps, largeur, hauteur, chemin):
    from fractions import Fraction
    exacte = Fraction(fps).limit_denominator(1000)
    return {
        "rush_id": rush_id,
        "source_name": f"{rush_id}.mov",
        "fps_source": fps,
        "fps_source_exact": f"{exacte.numerator}/{exacte.denominator}",
        "resolution_source": {"width": largeur, "height": hauteur},
        "source_metadata_absent_fields": [],
        "source_path": chemin,
        "source_start_timecode": "00:00:00:00",
    }


def lot(lot_id, rush_id, frames):
    return {"lot_id": lot_id, "rush_id": rush_id, "state": "extraction",
            "source_frame_count": frames, "source_frame_count_is_exact": True}


def manifeste(rushes_declares, lots):
    return {"schema_version": "2.1", "project_id": "projet_demo",
            "rushes": list(rushes_declares), "lots": list(lots),
            "artifacts": {}, "color": {}, "video": {}, "reconstruction": {}}


def document_de_reference():
    return manifeste(
        [rush("rush_01", fps=25.0, largeur=1920, hauteur=1080,
              chemin="/rushes/rush_01.mov"),
         rush("zz_rush_02", fps=50.0, largeur=1280, hauteur=720,
              chemin="/rushes/zz_rush_02.mov"),
         rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
              chemin="/perdu/rush_hiver.mov")],
        [lot("rush_01_25", "rush_01", 6300),
         lot("zz_rush_02_50", "zz_rush_02", 37900),
         lot("rush_hiver_24", "rush_hiver", 3012)])


def document_a_deux_absents():
    """AC 4.4 : deux absents, la cible en SECONDE position parmi eux."""
    return manifeste(
        [rush("rush_01", fps=25.0, largeur=1920, hauteur=1080,
              chemin="/rushes/rush_01.mov"),
         rush("rush_perdu_a", fps=30.0, largeur=3840, hauteur=2160,
              chemin="/perdu/rush_perdu_a.mov"),
         rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
              chemin="/perdu/rush_hiver.mov")],
        [lot("rush_01_25", "rush_01", 6300),
         lot("rush_perdu_a_30", "rush_perdu_a", 900),
         lot("rush_hiver_24", "rush_hiver", 3012)])


def projet(tmp_path, document=None) -> Path:
    dossier = tmp_path / "projet_demo"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(document or document_de_reference(), indent=2,
                   ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return dossier


def existe_sauf(*manquants):
    perdus = set(manquants)
    return lambda chemin: chemin not in perdus


SANS_HIVER = existe_sauf("/perdu/rush_hiver.mov")
SANS_LES_DEUX = existe_sauf("/perdu/rush_hiver.mov", "/perdu/rush_perdu_a.mov")


def probe_conforme(chemin):
    return relink.ProbeCandidat(nom_de_base="rush_hiver.mov",
                                cardinal_frames=3012, cardinal_est_exact=True,
                                timecode_depart="00:00:00:00")


def coque(ecran):
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


def ecran_de(tmp_path, document=None, existe=SANS_HIVER, **kwargs):
    return atelier_extraction.EcranRushes(
        projet(tmp_path, document), existe=existe, **kwargs)


# ---------------------------------------------------------------------------
# AC 2 -- la liste, sa presence, et le curseur qui ne saute pas
# ---------------------------------------------------------------------------

def test_l_ecran_liste_les_rushes_DANS_L_ORDRE_DU_MANIFESTE(tmp_path, banc):
    ecran = ecran_de(tmp_path)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return jetons.texte_affiche(pilote.app.screen.query_one(
            "#corps-atelier-rushes").content)

    rendu = banc(coque(ecran), scenario)
    rangs = [rendu.index(nom)
             for nom in ("rush_01", "zz_rush_02", "rush_hiver")]
    assert rangs == sorted(rangs), (
        "l'ordre du manifeste, pas l'ordre alphabetique : zz_rush_02 precede "
        "rush_hiver")


def test_le_curseur_SE_POSE_sur_un_rush_absent(tmp_path):
    """AC 2.3 : « on ne masque pas ce qu'on ne traite pas »."""
    ecran = ecran_de(tmp_path)
    ecran.traiter("down")
    ecran.traiter("down")
    assert ecran.liste.courant.rush_id == "rush_hiver"
    assert ecran.liste.courant.lie is False


def test_choisir_un_rush_ABSENT_ouvre_le_relink_et_n_extrait_RIEN(tmp_path):
    """AC 2.4 : « le choisir n'extrait rien -- il ouvre le relink »."""
    extraits = []
    ecran = ecran_de(tmp_path, extraire=extraits.append)
    ecran.liste.viser("rush_hiver")
    ecran.traiter("enter")
    assert extraits == []
    assert ecran.zone == atelier_extraction.ZONE_EXPLORATEUR
    assert ecran.but == atelier_extraction.BUT_RELINK


def test_choisir_un_rush_LIE_extrait(tmp_path):
    extraits = []
    ecran = ecran_de(tmp_path, extraire=extraits.append)
    ecran.liste.viser("zz_rush_02")
    ecran.traiter("enter")
    assert extraits == ["zz_rush_02"], (
        "la cible est le SECOND rush : un appel qui viserait toujours le "
        "premier ne se demasque pas autrement")
    assert ecran.zone == atelier_extraction.ZONE_LISTE


# ---------------------------------------------------------------------------
# AC 4 -- le relink, un rush a la fois
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("touche,mode,montrer", [
    ("r", rushes.MODE_RETROUVER, False),
    ("d", rushes.MODE_DESIGNER, True),
])
def test_les_deux_modes_ouvrent_LA_BONNE_VARIANTE_de_l_explorateur(
        tmp_path, touche, mode, montrer):
    """AC 4.1 : `montrer_fichiers=False` pour `r`, `True` pour `d`."""
    ecran = ecran_de(tmp_path)
    ecran.liste.viser("rush_hiver")
    assert ecran.traiter(touche, touche) is True
    assert ecran.mode == mode
    assert ecran.explorateur.montrer_fichiers is montrer


def test_r_et_d_ne_font_RIEN_quand_aucun_rush_n_est_absent(tmp_path):
    """Les deux touches ne sont annoncees que sur un absent : sur une liste
    entierement liee, elles ne doivent pas ouvrir un explorateur sans cible."""
    ecran = ecran_de(tmp_path, existe=lambda chemin: True)
    assert ecran.traiter("r", "r") is False
    assert ecran.zone == atelier_extraction.ZONE_LISTE


def test_Tab_ouvre_l_explorateur_pour_AJOUTER_un_rush(tmp_path):
    ecran = ecran_de(tmp_path)
    assert ecran.traiter("tab") is True
    assert ecran.but == atelier_extraction.BUT_AJOUTER
    assert ecran.explorateur.montrer_fichiers is True


def test_echap_sort_de_l_explorateur_VERS_LA_LISTE(tmp_path):
    """`Echap` ne remonte JAMAIS d'un dossier (`EPIC11-ARB-2`)."""
    ecran = ecran_de(tmp_path)
    ecran.liste.viser("rush_hiver")
    ecran.traiter("r", "r")
    assert ecran.traiter("escape") is True
    assert ecran.zone == atelier_extraction.ZONE_LISTE
    assert ecran.but is None


def test_le_relink_traite_LE_RUSH_SOUS_LE_CURSEUR_et_pas_le_premier_absent(
        tmp_path, banc):
    """AC 4.4, et c'est le mutant de la famille 5.7.

    Deux absents ; la cible est le **second**. Un relink qui prendrait « le
    premier absent » viserait `rush_perdu_a` et ce test le verrait.
    """
    dossier = projet(tmp_path, document_a_deux_absents())
    cible = tmp_path / "trouve.mov"
    cible.write_bytes(b"")
    ecran = atelier_extraction.EcranRushes(
        dossier, existe=SANS_LES_DEUX, probe=probe_conforme)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("d", "d")
        ecran._relinker(cible)
        await pilote.pause()

    banc(coque(ecran), scenario)
    document = json.loads(
        (dossier / extraction_manifest.MANIFEST_FILENAME).read_text("utf-8"))
    par_id = {e["rush_id"]: e for e in document["rushes"]}
    assert par_id["rush_hiver"]["source_path"] == str(cible)
    assert par_id["rush_perdu_a"]["source_path"] == "/perdu/rush_perdu_a.mov", (
        "le PREMIER absent ne doit pas avoir bouge : un seul rush par "
        "validation (AC 4.4)")


def test_un_relink_reussi_DIT_ce_qui_a_change(tmp_path, banc):
    """`EPIC11-ARB-81` : « une reparation muette et une reparation ratee se
    ressemblent trop »."""
    dossier = projet(tmp_path)
    cible = tmp_path / "trouve.mov"
    cible.write_bytes(b"")
    ecran = atelier_extraction.EcranRushes(dossier, existe=SANS_HIVER,
                                           probe=probe_conforme)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("d", "d")
        ecran._relinker(cible)
        await pilote.pause()
        return ecran.etat()

    etat = banc(coque(ecran), scenario)
    assert "rush_hiver" in etat


def test_preparer_le_relink_N_ECRIT_RIEN_quand_le_coeur_REFUSE(tmp_path, banc):
    """AC 4.5. Le probe ne correspond a rien : le relink doit refuser, et le
    manifeste rester **identique octet pour octet**."""
    dossier = projet(tmp_path)
    fichier = dossier / extraction_manifest.MANIFEST_FILENAME
    avant = fichier.read_bytes()
    cible = tmp_path / "autre.mov"
    cible.write_bytes(b"")

    def probe_qui_ne_correspond_pas(chemin):
        return relink.ProbeCandidat(nom_de_base="rien_a_voir.mov",
                                    cardinal_frames=1, cardinal_est_exact=True,
                                    timecode_depart="01:00:00:00")

    ecran = atelier_extraction.EcranRushes(
        dossier, existe=SANS_HIVER, probe=probe_qui_ne_correspond_pas)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("d", "d")
        ecran._relinker(cible)
        await pilote.pause()
        return type(pilote.app.screen).__name__

    ecran_final = banc(coque(ecran), scenario)
    assert fichier.read_bytes() == avant, "aucune ecriture avant validation"
    assert ecran_final == "EcranRefusRelink"


# ---------------------------------------------------------------------------
# `E2-1d` -- le refus porte son CODE, et il est rouge sur TOUTES ses lignes
# ---------------------------------------------------------------------------

def refus_long() -> rushes.Refus:
    return rushes.Refus(
        relink.REFUS_CANDIDATS_MULTIPLES,
        "3 fichiers de 03_tournage_mai/ verifient les trois criteres "
        "d'identite de rush_hiver : nom de base, 3 012 frames, timecode. "
        "Aucun ne peut etre choisi sans le dire.")


def test_le_refus_porte_SON_CODE_et_pas_une_phrase_inventee(banc):
    ecran = atelier_extraction.EcranRefusRelink(refus_long())

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return jetons.texte_affiche(
            pilote.app.screen.query_one("#chiffres").content)

    rendu = banc(coque(ecran), scenario)
    assert relink.REFUS_CANDIDATS_MULTIPLES in rendu


def test_le_message_REPLIE_du_refus_est_rouge_sur_TOUTES_ses_lignes(banc):
    """`EPIC11-ARB-71`, troisieme symptome : « l'erreur est rouge uniquement
    sur la ligne 1 »."""
    ecran = atelier_extraction.EcranRefusRelink(refus_long())

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        peint = pilote.app.screen.query_one("#chiffres").content
        # **On ne mesure que les lignes qui PORTENT du texte.** La ligne vide
        # qui separe le code du message n'a rien a teinter, et exiger une
        # couleur sur elle mesurerait le rendu de `rich`, pas la regle.
        return [str(ligne.spans[0].style) if ligne.spans else ""
                for ligne in peint.split("\n") if ligne.plain.strip()]

    styles = banc(coque(ecran), scenario)
    assert len(styles) > 2, "le message doit se replier, sinon on ne mesure rien"
    assert set(styles) == {jetons.couleur("state-absent")}, (
        "une ligne de continuation ne porte aucun glyphe : sans etat DONNE, "
        "elle reste blanche et le refus se lit comme deux messages")


def test_aucune_issue_de_l_ecran_de_refus_n_ECRIT():
    """`EPIC11-ARB-45` : la garde tient sans amenagement."""
    ecran = atelier_extraction.EcranRefusRelink(refus_long())
    assert all(not issue.ecrit for issue in ecran.choix.issues)


# ---------------------------------------------------------------------------
# Frontiere : l'atelier n'importe JAMAIS `cli`
# ---------------------------------------------------------------------------

def test_l_atelier_n_appelle_JAMAIS_cli_py():
    source = Path(atelier_extraction.__file__)
    assert "cli" not in identifiants(source), (
        "les fonctions de cli.py impriment sur stderr et rendent un code "
        "retour : les appeler depuis une TUI enverrait des lignes SOUS "
        "l'ecran dessine")


def test_la_garde_de_frontiere_cli_MORD(tmp_path):
    """Volet symetrique : sans lui, la garde pourrait ne rien regarder."""
    fautif = tmp_path / "module_fautif.py"
    fautif.write_text("from mixed_media_utility import cli\n"
                      "def f():\n    return cli.extract_command\n",
                      encoding="utf-8")
    assert "cli" in identifiants(fautif)


def test_le_code_du_refus_n_est_affiche_QU_UNE_FOIS(banc):
    """**Defaut trouve sur une capture reelle**, le 2026-08-30, et par aucun
    test : le banc mesurait le corps du cartouche, or le titre du CADRE n'est
    pas dans le corps. Le code sortait donc deux fois -- une sur le cadre, une
    dans le corps.

    La maquette `E2-1d` les separe : `┌ Refus ───┐` puis
    `✕ candidats-multiples` a l'interieur. Le cadre dit **de quoi il s'agit**,
    le corps dit **lequel**.
    """
    ecran = atelier_extraction.EcranRefusRelink(refus_long())

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        cadre = pilote.app.screen.query_one("#cartouche")
        corps = jetons.texte_affiche(
            pilote.app.screen.query_one("#chiffres").content)
        return str(cadre.border_title), corps

    titre, corps = banc(coque(ecran), scenario)
    assert titre == atelier_extraction.TITRE_DU_REFUS
    assert relink.REFUS_CANDIDATS_MULTIPLES not in titre, (
        "le cadre ne repete pas le code : il le porterait une seconde fois")
    assert corps.count(relink.REFUS_CANDIDATS_MULTIPLES) == 1


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("touche,titre_attendu", [
    ("tab", rushes.AJOUTER_UN_RUSH),
    ("r", "rush_hiver"),
    ("d", "rush_hiver"),
])
def test_la_zone_de_l_EXPLORATEUR_SE_DESSINE(tmp_path, banc, ascii_seul,
                                             touche, titre_attendu):
    """**Le trou que ce test ferme** : aucun banc ne RENDAIT cette zone.

    Les mesures portaient sur `traiter()` et sur la liste des rushes ; la zone
    de l'explorateur n'etait jamais dessinee. `Explorateur.lignes` prend
    `(largeur, titre, libelle, ascii_seul)`, et l'appeler positionnellement
    posait le booleen dans `titre` : l'ecran tombait sur
    `TypeError: can only concatenate str (not "bool")` des la premiere frappe
    qui ouvre l'explorateur. Trouve en MARCHANT le parcours au clavier, le
    2026-08-30, sur la vraie chaine.

    Les trois portes sont mesurees -- `Tab`, `r` et `d` -- parce qu'elles
    posent trois titres differents, et les deux regimes de repli avec elles.
    """
    ecran = ecran_de(tmp_path)
    ecran.liste.viser("rush_hiver")

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        pilote.app.ascii_seul = ascii_seul
        ecran.traiter(touche, touche if len(touche) == 1 else None)
        ecran.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(pilote.app.screen.query_one(
            "#corps-atelier-rushes").content), ecran.etat()

    rendu, etat = banc(coque(ecran), scenario)
    assert ecran.zone == atelier_extraction.ZONE_EXPLORATEUR
    assert titre_attendu in rendu, (
        "le cartouche de l'explorateur annonce ce qu'on y cherche")
    assert isinstance(etat, str) and etat, (
        "la ligne d'etat de l'explorateur est une chaine, jamais un booleen "
        "passe pour une largeur")


# ===========================================================================
# Lot I -- ce que les CAPTURES ont montre et qu'aucun banc ne voyait
#
# `I2`, `I3` et `I4`, tous les trois de la meme famille : un producteur livre,
# teste, exporte, et **appele par aucun ecran**. Un composant que rien ne cable
# est un composant que le produit n'a pas -- c'est ce que le lot `E9` a paye
# pendant deux vagues, masque par une demo qui assemblait la chaine a la main.
#
# **Ces tests-ci mesurent donc l'ECRAN, jamais le producteur.** Un test qui
# appelle `rushes.lignes_des_modes()` directement ne ferme rien : c'est
# exactement ce que `test_rushes.py` faisait pendant que `E2-1` ne dessinait
# ni sa question, ni `Ajouter un rush`, ni le bloc `r` / `d`.
# ===========================================================================

def document_absent_au_MILIEU():
    """Trois rushes distinguables, l'absent en **DEUXIEME** position.

    `CLAUDE.md` demande deux elements distinguables et une cible ailleurs qu'en
    premiere position ; le complement mesure le 2026-08-30 sur ce depot ajoute
    **ailleurs qu'en derniere non plus** : sur une fabrique de deux ou la cible
    est en second, second EST dernier, et un mutant `continue` -> `break`
    survit. Trois rushes, la cible au milieu, ferment les deux cotes a la fois.
    """
    return manifeste(
        [rush("aa_rush_lie", fps=25.0, largeur=1920, hauteur=1080,
              chemin="/rushes/aa_rush_lie.mov"),
         rush("rush_hiver", fps=24.0, largeur=4096, hauteur=2160,
              chemin="/perdu/rush_hiver.mov"),
         rush("zz_rush_lie", fps=50.0, largeur=1280, hauteur=720,
              chemin="/rushes/zz_rush_lie.mov")],
        [lot("aa_rush_lie_25", "aa_rush_lie", 6300),
         lot("rush_hiver_24", "rush_hiver", 3012),
         lot("zz_rush_lie_50", "zz_rush_lie", 37900)])


def corps_rendu(banc, ecran, ascii_seul: bool, touches=()) -> str:
    """Le corps de `E2-1` **tel qu'il est dessine**, apres des frappes.

    On lit le widget, pas `composer()` : c'est la seule mesure qui aurait vu
    `I2`, ou le producteur rendait les bonnes lignes et l'ecran ne les posait
    nulle part.
    """
    async def scenario(pilote):
        pilote.app.ascii_seul = ascii_seul
        pilote.app.descendre(ecran)
        await pilote.pause()
        for touche in touches:
            ecran.traiter(touche, touche if len(touche) == 1 else None)
        ecran.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(pilote.app.screen.query_one(
            "#corps-atelier-rushes").content)

    return banc(coque(ecran), scenario)


def bandeau_et_etat(banc, ecran, ascii_seul: bool, touches=()) -> tuple:
    """Le bandeau et la ligne d'etat **dessines**, apres des frappes."""
    from textual.widgets import Static

    async def scenario(pilote):
        pilote.app.ascii_seul = ascii_seul
        pilote.app.descendre(ecran)
        await pilote.pause()
        for touche in touches:
            ecran.traiter(touche, touche if len(touche) == 1 else None)
        ecran.rafraichir()
        await pilote.pause()
        ecran_courant = pilote.app.screen
        return (jetons.texte_affiche(
                    ecran_courant.query_one("#bandeau", Static).content),
                jetons.texte_affiche(
                    ecran_courant.query_one("#etat", Static).content))

    return banc(coque(ecran), scenario)


# --- I2 : `E2-1` ne portait ni sa question, ni `Ajouter un rush`, ni r / d --

@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E2_1_DESSINE_sa_question_et_l_entree_AJOUTER_UN_RUSH(
        tmp_path, banc, ascii_seul):
    """`I2` : les deux blocs que la maquette pose autour de la liste.

    `PHRASE_AJOUTER_UN_RUSH` n'etait **lue nulle part** dans tout le depot, et
    le plan de test manuel B.2 decrivait une entree que l'ecran ne dessinait
    pas. Les deux regimes, parce que le repli change les deux textes.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    rendu = corps_rendu(banc, ecran, ascii_seul)

    for texte in (atelier_extraction.TITRE_RUSHES, rushes.AJOUTER_UN_RUSH,
                  rushes.PHRASE_AJOUTER_UN_RUSH):
        attendu = jetons.replier_ascii(texte) if ascii_seul else texte
        assert attendu in rendu, (texte, rendu)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E2_1_DESSINE_le_bloc_r_d_sous_un_rush_ABSENT(tmp_path, banc,
                                                      ascii_seul):
    """`I2` : le bloc de relink, **rendu par l'ecran** et pas seulement produit.

    Les DEUX modes sont exiges, avec leur lettre, leur libelle et leur phrase :
    un rendu qui s'arreterait au premier (`continue` -> `break`) passerait
    autrement, et la cible du test est au MILIEU de la liste des rushes.

    La phrase du mode `r` deborde la place et s'enveloppe : sa continuation est
    exigee elle aussi, sans quoi un enveloppement qui perdrait la queue --
    « durée et timecode de départ », c'est-a-dire deux des trois criteres --
    resterait vert.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    rendu = corps_rendu(banc, ecran, ascii_seul)

    def replie(texte):
        return jetons.replier_ascii(texte) if ascii_seul else texte

    assert replie("rush_hiver — déclaré au manifest, introuvable") in rendu
    for touche, libelle, phrase in rushes.lignes_des_modes():
        assert replie(libelle) in rendu, (libelle, rendu)
        # La phrase est enveloppee : on mesure chacun de ses MOTS-CLES plutot
        # qu'une chaine entiere qu'un retour a la ligne couperait.
        for morceau in phrase.split(", "):
            assert replie(morceau) in rendu, (morceau, rendu)
    assert "durée et timecode" in replie(rendu) or replie(
        "durée et timecode") in rendu, (
        "la queue enveloppee de la phrase du mode `r`")


def test_un_rush_LIE_ne_fait_dessiner_AUCUN_bloc_r_d(tmp_path, banc):
    """Volet symetrique : le bloc n'existe que sous un absent.

    Sans lui, un ecran qui poserait le bloc en permanence passerait le test
    precedent -- et le plan de test manuel B.1 dit « Elles ne sont la **que**
    quand un rush est absent ».
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("zz_rush_lie")
    rendu = corps_rendu(banc, ecran, False)

    for _touche, libelle, _phrase in rushes.lignes_des_modes():
        assert libelle not in rendu, (libelle, rendu)
    assert "introuvable" not in rendu.split(rushes.AJOUTER_UN_RUSH)[-1], (
        "le filet de relink ne suit pas l'entree d'ajout sur un rush lie")
    # La question et l'entree d'ajout, elles, restent : ce sont les deux blocs
    # que la maquette pose sur TOUS les etats de l'ecran.
    assert atelier_extraction.TITRE_RUSHES in rendu
    assert rushes.AJOUTER_UN_RUSH in rendu


def test_le_curseur_et_les_ETATS_suivent_le_bloc_de_TETE(tmp_path):
    """`I2`, la moitie que le texte ne dit pas : les rangs sont DECALES.

    Le bloc de tete -- blanc, question, blanc -- pousse la liste de trois
    lignes. Un rang de curseur ou un etat laisse a son index de modele
    surlignerait la question et teindrait un blanc, sans qu'aucune assertion
    de texte ne le voie (`EPIC11-ARB-47` et `-71` : le rang est PASSE, jamais
    devine). La cible est au MILIEU des trois rushes.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    lignes, rang, etats = ecran.composer(jetons.LARGEUR_PLANCHER)

    assert rang is not None
    assert "rush_hiver" in lignes[rang], (rang, lignes)
    assert lignes[rang] is not lignes[ecran.liste.rang_du_curseur()], (
        "le rang du modele n'est pas celui de l'ecran : il est decale")
    for indice, nom in etats.items():
        assert nom == ("absent" if "rush_hiver" in lignes[indice]
                       else "complete"), (indice, nom, lignes[indice])
    assert sorted(etats) == [rang - 1, rang, rang + 1], (etats, rang)


# --- I3 : la droite du bandeau etait vide sur les douze ecrans -------------

@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("touche,mode", [("r", rushes.MODE_RETROUVER),
                                         ("d", rushes.MODE_DESIGNER)])
def test_le_BANDEAU_de_E2_1b_et_E2_1c_porte_le_rush_et_son_MODE(
        tmp_path, banc, ascii_seul, touche, mode):
    """`I3` : `rushes.bandeau_de_relink()` etait exporte et appele NULLE PART.

    La maquette met `rush_hiver · retrouver` a droite du bandeau de `E2-1b` et
    `rush_hiver · désigner` sur `E2-1c` : les deux modes sont mesures, sans
    quoi un bandeau qui rendrait toujours le premier passerait. La cible est
    l'absent du MILIEU.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    bandeau, _etat = bandeau_et_etat(banc, ecran, ascii_seul, [touche])

    attendu = rushes.bandeau_de_relink("rush_hiver", mode)
    if ascii_seul:
        attendu = jetons.replier_ascii(attendu)
    assert attendu in bandeau, (attendu, bandeau)
    assert bandeau.rstrip().endswith(attendu), (
        "l'objet travaille est cale a DROITE, comme sur la maquette")


def test_le_BANDEAU_de_E2_1_est_NU_tant_qu_aucun_relink_n_est_ouvert(
        tmp_path, banc):
    """Volet symetrique : la maquette `E2-1` porte un bandeau sans droite.

    Un ecran qui poserait l'objet en permanence passerait le test precedent, et
    montrerait un rush « en cours de relink » a qui n'a rien ouvert.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    bandeau, _etat = bandeau_et_etat(banc, ecran, False)

    assert "rush_hiver" not in bandeau, bandeau
    assert bandeau.rstrip() == "mmu · projet_demo · Extraction", bandeau


def test_SORTIR_de_l_explorateur_REND_le_bandeau_nu(tmp_path, banc):
    """L'objet travaille ne survit pas au geste : `Échap` le retire.

    C'est le motif pour lequel il n'est pas ecrit dans `Contexte` -- ce que la
    session porte traverse les etages, et un rush laisse la se lirait sur le
    bandeau du voisin.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    bandeau, _etat = bandeau_et_etat(banc, ecran, False, ["r", "escape"])

    assert "rush_hiver" not in bandeau, bandeau


def test_le_BANDEAU_de_E2_1d_porte_le_rush_et_le_mode_du_geste(banc):
    """`E2-1d` porte le meme bandeau que `E2-1b` sur sa maquette.

    Le rush et le mode voyagent avec le refus : cet ecran-la n'a pas de liste
    ou les relire.
    """
    from textual.widgets import Static

    ecran = atelier_extraction.EcranRefusRelink(
        refus_long(), rush_id="rush_hiver", mode=rushes.MODE_RETROUVER)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)

    bandeau = banc(coque(ecran), scenario)
    assert bandeau.rstrip().endswith(
        rushes.bandeau_de_relink("rush_hiver", rushes.MODE_RETROUVER)), bandeau


# --- I4 : les trois criteres d'appariement en ligne d'etat de E2-1b / E2-1c -

@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("touche", ["r", "d"])
def test_la_LIGNE_D_ETAT_de_E2_1b_et_E2_1c_porte_les_TROIS_CRITERES(
        tmp_path, banc, ascii_seul, touche):
    """`I4` : la ligne d'etat etait celle, GENERIQUE, de l'explorateur.

    Les trois criteres sont mesures **un par un** -- nom de base, cardinal,
    timecode de depart -- et pas comme une chaine unique : un rendu qui en
    perdrait un sur trois passerait autrement, et c'est exactement la forme du
    defaut (`plan-de-test-manuel-vague-3.md`, B.3).

    `EPIC11-ARB-56`, verbatim : la ligne d'etat « ne porte **aucune touche**
    [...] **aucun conseil d'usage** [...] **aucun motif de conception** ». Ce
    sont trois valeurs lues du manifeste, donc une mesure.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    _bandeau, etat = bandeau_et_etat(banc, ecran, ascii_seul, [touche])

    for critere in ("rush_hiver", "3 012", "frames", "TC 00:00:00:00"):
        assert critere in etat, (critere, etat)
    # La mesure de l'explorateur reste : les criteres s'ajoutent a elle, ils ne
    # la remplacent pas.
    assert "sous-dossier" in etat or "fichier" in etat, etat
    assert jetons.colonnes(etat) <= jetons.largeur_utile(), (
        jetons.colonnes(etat), etat)


def test_les_criteres_ne_portent_AUCUN_NOM_de_critere_du_coeur(tmp_path, banc):
    """`EPIC11-ARB-32` : « la logique d'appariement (nom, duree, timecode) que
    `relink` porte deja » reste dans le coeur.

    La ligne d'etat montre les trois VALEURS, jamais les trois noms de champ :
    un ecran qui ecrirait `source_frame_count` aurait recopie le vocabulaire
    d'appariement dans l'interface.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    _bandeau, etat = bandeau_et_etat(banc, ecran, False, ["r"])

    for critere in relink.CRITERES_IDENTITE_RELINK:
        assert critere not in etat, (critere, etat)


def test_la_ligne_d_etat_de_E2_1_SANS_relink_reste_celle_de_la_LISTE(
        tmp_path, banc):
    """Volet symetrique : les criteres n'apparaissent que pendant un relink.

    `Tab` ouvre le meme explorateur pour AJOUTER un rush : il n'y a alors
    aucune reference a montrer, et en montrer une nommerait un rush que
    l'operateur n'a pas vise.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    _b, etat_liste = bandeau_et_etat(banc, ecran, False)
    assert "TC " not in etat_liste, etat_liste

    ecran = ecran_de(tmp_path / "bis", document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    _b, etat_ajout = bandeau_et_etat(banc, ecran, False, ["tab"])
    assert "TC " not in etat_ajout, etat_ajout


def test_les_CRITERES_survivent_a_une_mesure_d_explorateur_TROP_LONGUE(
        tmp_path):
    """C'est la mesure de l'explorateur qui cede, jamais les criteres.

    Meme arbitrage que `Contexte.rendu`, et pour le meme motif : le compte du
    dossier se relit dans le corps de l'ecran, les criteres ne se relisent
    nulle part ailleurs. Sans cette regle, `E2-1c` -- dont la mesure est la
    plus longue -- perdrait le timecode par la droite.
    """
    ecran = ecran_de(tmp_path, document_absent_au_MILIEU())
    ecran.liste.viser("rush_hiver")
    ecran.but = atelier_extraction.BUT_RELINK
    ecran.mode = rushes.MODE_DESIGNER
    ecran._reference = rushes.reference_de_rush(ecran.dossier, "rush_hiver")

    utile = jetons.largeur_utile()
    etat = ecran._avec_les_criteres("x" * 200, utile, False)
    assert jetons.colonnes(etat) <= utile, (jetons.colonnes(etat), etat)
    assert etat.endswith("TC 00:00:00:00"), etat


# --- La garde generale : plus de surface publique cablee nulle part --------

#: Les surfaces publiques de `rushes` qu'AUCUN ecran ne cite, **et pourquoi**.
#: Chacune est consommee a l'interieur du module -- par une autre surface
#: publique, par un invariant de construction ou par le gabarit des refus --,
#: ou bien c'est un TYPE que les ecrans manipulent sans le nommer.
#:
#: Cet inventaire est le second volet de la garde ci-dessous : une surface
#: nouvelle qu'aucun ecran ne cable doit y entrer **avec sa raison**, sinon le
#: banc rougit. C'est la seule chose qui aurait empeche `bandeau_de_relink`,
#: `lignes_des_modes` et `PHRASE_AJOUTER_UN_RUSH` de vivre trois lots durant
#: sans qu'aucun ecran ne les appelle.
CONSOMMEES_DANS_LE_MODULE = {
    "Apercu": "type rendu par preparer_relink, jamais nomme par un ecran",
    "EcritureRefusee": "garde de type d'ecrire_le_relink",
    "ListeDesRushes": "type rendu par lister()",
    "Rush": "type porte par ListeDesRushes",
    "CODES_DE_REFUS": "inventaire ferme, mesure par les bancs",
    "CODES_DE_REFUS_DU_COEUR": "lu de relink.__all__, entre dans CODES_DE_REFUS",
    "ETATS_DE_PRESENCE": "table lue par Rush.etat",
    "HAUTEUR_LISTE": "budget de la fenetre, consomme par ListeDesRushes.fenetre",
    "LIBELLES_APRES_REFUS": "textes poses par issues_apres_refus",
    "LIBELLES_DE_MODE": "consomme par lignes_des_modes",
    "LIBELLE_ABSENT": "valeur de la table PRESENCES",
    "LIBELLE_LIE": "valeur de la table PRESENCES",
    # `MANIFESTE_INCHANGE` EST SORTI DE CET INVENTAIRE le 2026-09-05, avec
    # l'ecran `E2-1f` : `ajout_de_rush.etat_du_refus_de_conflit` le lit pour
    # composer la ligne d'etat du refus de conflit, exactement comme
    # `Refus.ligne_d_etat` le fait pour `E2-1d`. **C'est le volet « declarees
    # mais desormais cablees » qui l'a dit**, pas une relecture -- la garde a
    # rougi dans le sens de la reparation.
    "MODES": "inventaire ferme, garde de _mode_connu",
    "MOTS_DE_MODE": "consomme par bandeau_de_relink",
    "PHRASES_DE_MODE": "consomme par lignes_des_modes",
    "PRESENCES": "table lue par Rush.presence",
    "REFUS_MANIFESTE_ABSENT": "code rendu par preparer_relink",
    "REFUS_MANIFESTE_ILLISIBLE": "code rendu par preparer_relink",
    # `SIGNE_MULTIPLIER` et `duree_de_rush` SONT SORTIS DE CET INVENTAIRE le
    # 2026-09-05, avec les ecrans de declaration : `ajout_de_rush` les appelle
    # tous les deux pour la ligne `Résolution` de `E2-1e`. **C'est le volet
    # « declarees mais desormais cablees » qui l'a dit**, pas une relecture --
    # la garde a rougi dans le sens de la reparation, ce qu'une assertion
    # positive n'aurait pas fait.
    "rushes_du_manifeste": "consomme par lister()",
}


def surfaces_citees_par_un_ecran() -> set[str]:
    """Les attributs de `rushes` que les modules d'ECRAN nomment.

    Mesure sur l'arbre syntaxique et non par un grep : une prose d'explication
    qui cite `bandeau_de_relink` dans un docstring ne cable rien, et c'est
    precisement ce qui a rendu le defaut invisible -- le nom etait partout dans
    les commentaires et nulle part dans le code.

    **`ajout_de_rush.py` entre dans le balayage le 2026-09-05**, avec les
    ecrans de declaration. Il ne porte aucun ecran -- il porte ce que `E2-1e`
    et ses trois variantes CALCULENT --, et c'est justement pourquoi il compte
    ici : la question que cette garde pose est « cette surface atteint-elle le
    produit ? », pas « un `Screen` la nomme-t-il ? ». Un modele pur monte par
    un ecran est un consommateur reel ; l'exclure ferait declarer « orpheline »
    une surface que le produit affiche a chaque declaration de rush.
    """
    import ast

    paquet = Path(_SRC) / "mixed_media_utility" / "tui"
    citees: set[str] = set()
    for module in ("atelier_extraction.py", "atelier_extraction_ecriture.py",
                   "ajout_de_rush.py"):
        arbre = ast.parse((paquet / module).read_text(encoding="utf-8"))
        citees |= {noeud.attr for noeud in ast.walk(arbre)
                   if isinstance(noeud, ast.Attribute)
                   and isinstance(noeud.value, ast.Name)
                   and noeud.value.id == "rushes"}
    return citees


def test_TOUTE_surface_publique_de_rushes_est_CABLEE_ou_DECLAREE():
    """**La garde que `I2` et `I3` reclament** : un producteur sans consommateur.

    Trois surfaces -- `bandeau_de_relink`, `lignes_des_modes`,
    `PHRASE_AJOUTER_UN_RUSH` -- etaient livrees, testees, exportees, et
    appelees par aucun ecran. Le produit ne les avait donc pas, et seul un
    operateur regardant les douze ecrans tourner pouvait s'en apercevoir. C'est
    la troisieme occurrence du mode de panne du lot `E9`.

    L'egalite mord des DEUX cotes : une surface nouvelle qu'aucun ecran ne
    cable doit entrer dans `CONSOMMEES_DANS_LE_MODULE` avec sa raison, et une
    surface qu'on decablerait en sortirait -- ce qui fait rougir le banc.
    """
    citees = surfaces_citees_par_un_ecran()
    orphelines = {nom for nom in rushes.__all__ if nom not in citees}
    assert orphelines == set(CONSOMMEES_DANS_LE_MODULE), (
        "surfaces publiques de rushes.py qu'aucun ecran n'appelle et que "
        "l'inventaire ne declare pas : "
        f"{sorted(orphelines - set(CONSOMMEES_DANS_LE_MODULE))} ; "
        "declarees mais desormais cablees : "
        f"{sorted(set(CONSOMMEES_DANS_LE_MODULE) - orphelines)}")


def test_l_inventaire_des_ORPHELINES_ne_declare_que_des_surfaces_REELLES():
    """Volet symetrique : un inventaire qui deriverait rendrait la garde muette.

    Une entree qui ne correspond a aucun export ferait, a elle seule, tomber
    l'egalite du test precedent dans le mauvais sens -- et on serait tente de
    la relacher. Elle est donc mesuree ici, separement.
    """
    inconnues = set(CONSOMMEES_DANS_LE_MODULE) - set(rushes.__all__)
    assert inconnues == set(), inconnues
    assert all(raison for raison in CONSOMMEES_DANS_LE_MODULE.values())


# ===========================================================================
# Lot I -- `I7` : la DUREE est une mesure, elle ne s'abrege pas
#
# **Le defaut, et sa cause exacte.** `atelier_extraction` passait
# `jetons.largeur_utile(app.size.width)` a `ListeDesRushes.rendu`, dont le
# contrat prend la largeur de la FENETRE et retire lui-meme cadre et marges :
# `largeur_utile` etait donc appliquee DEUX FOIS, 80 -> 76 -> 72. La colonne
# technique tombait de 28 a 24 colonnes pour une valeur qui en fait 25, et la
# duree sortait abregee -- `4:…` en UTF-8, et **entierement perdue** en repli
# ASCII, ou `…` rend `...` et l'ellipse mange un caractere de plus.
#
# `EPIC11-ARB-21` n'admet d'abreger que le NOM (« un nom long est tronque a
# l'affichage, jamais a l'ecriture ») ; la duree, elle, est une mesure.
#
# **Ce que ces tests mesurent est la duree RENDUE, pas la largeur passee** : un
# banc qui verifierait l'argument se contenterait de decrire l'implementation
# courante et laisserait revenir le defaut par un autre chemin.
# ===========================================================================

def document_aux_TROIS_durees_distinctes():
    """Trois rushes, trois durees et trois resolutions **differentes**.

    La plus large est au MILIEU : ni premiere ni derniere. Et la troisieme
    duree est **courte** (`0:02`), donc elle tient meme a la largeur fautive :
    c'est elle qui empeche le test de passer par accident sur un corpus ou tout
    deborderait.

    **Depuis `J2`, la plus large est le cas REEL que l'arbitrage `Q8` sauve** :
    un 4K a 23,976 im/s de plus d'une heure, qui demande les 32 colonnes
    exactes que la colonne offre desormais. Avant `Q8` il ne tenait pas, donc
    le corpus ne pouvait pas le porter -- le test jumeau aurait rougi a bon
    droit. Le prendre ici rend les deux volets plus durs a la fois : le jumeau
    exige que meme ce cas-la soit rendu ENTIER au plancher, et celui-ci exige
    que la double deduction l'abrege.
    """
    return manifeste(
        [rush("aa_rush_lie", fps=25.0, largeur=1920, hauteur=1080,
              chemin="/rushes/aa_rush_lie.mov"),
         rush("rush_hiver", fps=23.976, largeur=4096, hauteur=2160,
              chemin="/perdu/rush_hiver.mov"),
         rush("zz_rush_court", fps=50.0, largeur=1280, hauteur=720,
              chemin="/rushes/zz_rush_court.mov")],
        [lot("aa_rush_lie_25", "aa_rush_lie", 6300),      # 4:12
         lot("rush_hiver_24", "rush_hiver", 90000),       # 1:02:33
         lot("zz_rush_court_50", "zz_rush_court", 100)])  # 0:02


#: Les trois durees que le coeur derive du document ci-dessus, **calculees** et
#: non recopiees : `duree_de_rush` fait foi, et un test qui ecrirait `4:12` en
#: dur mesurerait la fixture au lieu du rendu.
def durees_attendues() -> list:
    return [rushes.duree_de_rush(frames, fps)
            for frames, fps in ((6300, 25.0), (90000, 23.976), (100, 50.0))]


def test_les_TROIS_durees_de_la_fabrique_sont_DISTINCTES_et_derivables():
    """Volet symetrique de la fabrique : trois durees egales, ou nulles, ne
    demasqueraient aucune troncature."""
    durees = durees_attendues()
    assert len(set(durees)) == 3, durees
    assert all(durees), durees


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_DUREE_de_chaque_rush_est_rendue_ENTIERE_a_la_grille_plancher(
        tmp_path, banc, ascii_seul):
    """`I7` : au plancher 80x24, aucune duree n'est abregee, dans les DEUX
    regimes.

    La mesure est faite sur l'ecran MONTE et sur la duree **rendue** : c'est
    elle qui est la promesse. Le repli ASCII est le regime ou le defaut mordait
    le plus fort -- il y perdait la duree entiere --, donc il n'est pas
    optionnel ici.
    """
    ecran = ecran_de(tmp_path, document_aux_TROIS_durees_distinctes())
    rendu = corps_rendu(banc, ecran, ascii_seul)

    manquantes = [duree for duree in durees_attendues() if duree not in rendu]
    assert manquantes == [], (manquantes, rendu)
    # Et aucune ellipse dans la zone technique : elle ne peut abreger que le
    # NOM (`EPIC11-ARB-21`), et les noms de la fixture sont courts.
    points = jetons.points_d_abregement(ascii_seul)
    for ligne in rendu.splitlines():
        if "fps" in ligne:
            assert points not in ligne, (points, ligne)


def test_appliquer_largeur_utile_DEUX_FOIS_ABREGE_bien_la_duree(tmp_path):
    """Volet symetrique, et **c'est lui qui donne sa valeur au test precedent**.

    Sans lui, une fixture dont les colonnes tiendraient largement rendrait la
    mesure verte quelle que soit la largeur passee. Ici on reproduit la double
    deduction a la main -- `largeur_utile(largeur_utile(80))` -- et on exige
    qu'elle abrege : le corpus est donc bien assez serre pour que le defaut se
    voie.
    """
    liste = ecran_de(tmp_path, document_aux_TROIS_durees_distinctes()).liste
    plein = "\n".join(liste.rendu(jetons.LARGEUR_PLANCHER))
    fautif = "\n".join(liste.rendu(jetons.largeur_utile()))

    entieres = [duree for duree in durees_attendues() if duree in plein]
    perdues = [duree for duree in durees_attendues() if duree not in fautif]
    assert len(entieres) == 3, (entieres, plein)
    assert perdues, (
        "la double deduction n'abrege rien sur ce corpus : le test jumeau ne "
        f"mesurerait plus le defaut. Rendu fautif :\n{fautif}")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_LARGEUR_passee_a_rendu_est_celle_de_la_FENETRE(tmp_path, ascii_seul):
    """Le meme invariant, pris par l'autre bout : `composer` et `rendu`
    s'accordent sur la largeur.

    Le corps compose par l'ecran a 80 colonnes doit etre **identique** a ce que
    le modele rend a 80 colonnes. Toute deduction supplementaire faite en
    chemin -- par l'ecran, par un futur intermediaire -- fait diverger les deux,
    et c'est la seule facon de mesurer la double application sans nommer
    l'argument.
    """
    ecran = ecran_de(tmp_path, document_aux_TROIS_durees_distinctes())
    compose = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0]
    du_modele = ecran.liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)

    for ligne in du_modele:
        assert ligne in compose, (ligne, compose)


#: **La geometrie de la colonne technique, MESUREE.**
#:
#: Elle a change le 2026-08-30 : Egan a tranche `Q8` (`J2`) en option `a`, et
#: `rushes.COLONNE_TECHNIQUE` est passee de 30 a 26. La mesure obtient ses
#: **32** colonnes -- de quoi rendre `23,976 fps · 4096×2160 · 1:02:33`
#: entierement --, et la colonne du nom tombe de 23 a **19**.
#:
#: La note precedente disait « au-dela de 28 colonnes la duree est toujours
#: perdue » et demandait a etre reprise plutot qu'ajustee le jour ou le cas
#: tiendrait. Il tient : elle est donc **reprise**, pas rafistolee.
PLACE_TECHNIQUE_AU_PLANCHER = 32
PLACE_DU_NOM_AU_PLANCHER = 19
COLONNES_DEMANDEES_PAR_UN_4K_LONG = 32


def test_la_GEOMETRIE_de_la_liste_est_celle_de_l_arbitrage_Q8():
    """Les deux colonnes que `Q8` a arbitrees, tenues par une mesure.

    « On ecrit ce que la forme ne prouve pas » (`jetons.jeton_d_etat`). Une
    geometrie retouchee sans reprendre l'arbitrage fera rougir ce test.
    """
    utile = jetons.largeur_utile()
    colonne_presence = max(utile - rushes.LARGEUR_PRESENCE,
                           rushes.COLONNE_TECHNIQUE)
    place = (colonne_presence - rushes.COLONNE_TECHNIQUE
             - jetons.CREUX_MINIMAL)
    place_du_nom = (rushes.COLONNE_TECHNIQUE - rushes.COLONNE_NOM
                    - jetons.CREUX_MINIMAL)
    assert place == PLACE_TECHNIQUE_AU_PLANCHER, place
    assert place_du_nom == PLACE_DU_NOM_AU_PLANCHER, place_du_nom

    # Les valeurs de terrain du depot tiennent, avec du jeu.
    for duree, fps, largeur, hauteur, frames in (
            ("4:12", 25.0, 1920, 1080, 6300),
            ("2:05", 24.0, 4096, 2160, 3012)):
        vue = rushes.Rush("r", relink.LIE, fps, largeur, hauteur, frames)
        assert vue.duree == duree
        assert jetons.colonnes(vue.technique()) < place, vue.technique()


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_cas_qui_NE_TENAIT_PAS_tient_desormais_ENTIER(ascii_seul):
    """`J2` : la duree d'un 4K long n'est plus perdue, dans les DEUX regimes.

    C'est le cas exact que la note du lot `I` nommait sans le corriger : un 4K
    a 23,976 im/s de plus d'une heure. Il demandait 32 colonnes pour 28
    disponibles, et c'est la **duree** qui etait rognee -- une MESURE, la ou
    `EPIC11-ARB-21` n'admet d'abreger que le NOM.

    **Le regime ASCII n'est pas une redite** : c'est celui ou le defaut mordait
    le plus fort. Le repli ALLONGE -- `…` rend `...` --, si bien que la duree
    ne disparaissait pas a moitie mais entierement.

    La mesure porte sur la ligne RENDUE, pas sur la largeur passee : c'est la
    lecon de `I7`, ou une largeur juste etait deduite deux fois.
    """
    long_4k = rushes.Rush("rush_4k_long", relink.LIE, 23.976, 4096, 2160,
                          90000)
    demande = jetons.colonnes(long_4k.technique(ascii_seul))
    assert demande == COLONNES_DEMANDEES_PAR_UN_4K_LONG, demande
    assert demande <= PLACE_TECHNIQUE_AU_PLANCHER, (
        "si ce cas cesse de tenir, c'est l'arbitrage `Q8` qu'il faut rouvrir, "
        "pas ce chiffre qu'il faut ajuster")

    ligne = rushes.ListeDesRushes([long_4k]).rendu(jetons.LARGEUR_PLANCHER,
                                                   ascii_seul)[0]
    assert "1:02:33" in ligne, (
        f"la duree est encore perdue en {'ASCII' if ascii_seul else 'UTF-8'} : "
        f"{ligne!r}")
    assert jetons.points_d_abregement(ascii_seul) not in ligne, ligne
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(), ligne


# ---------------------------------------------------------------------------
# `J2` -- ce que les quatre colonnes rendues coutent au NOM
# ---------------------------------------------------------------------------
#
# **C'est ici que l'option `a` peut mal tourner**, et c'est donc ici que le
# banc doit etre le plus dur. Les quatre colonnes rendues a la mesure sont
# prises au nom, qui tombe de 23 a 19 : un nom elide doit rester
# RECONNAISSABLE, faute de quoi on aurait echange une mesure fausse contre un
# nom faux.
#
# Les lots de ce depot se distinguent par leur **suffixe** -- `rush_01_25`
# contre `rush_01_12p5`, et pire avec les cadences non implementees
# d'`EPIC11-ARB-62` (`rush_01_8p333333333333334`). Une elision par la fin
# rendrait deux lots du meme rush **indiscernables a l'ecran** : c'est le
# risque `R12` remonte au niveau de l'affichage, et c'est la famille du mutant
# `M25` de la story 5.7, ou l'ecriture partait sur le mauvais lot.

#: Trois rushes qui ne different QUE par leur suffixe, tous plus longs que la
#: colonne -- donc tous elides. La cible est **au milieu** : ni la premiere ni
#: la derniere, point 2 bis de la regle des fabriques.
NOMS_QUI_NE_DIFFERENT_QUE_PAR_LEUR_SUFFIXE = (
    "projet_demo_rush_hiver_camera_A_25",
    "projet_demo_rush_hiver_camera_B_25",     # <- la cible, au MILIEU
    "projet_demo_rush_hiver_camera_C_25",
)


def document_aux_suffixes_voisins():
    """Un manifeste dont les trois rushes ne different que par leur suffixe."""
    return manifeste(
        [rush(nom, fps=25.0 + rang, largeur=1920 + rang, hauteur=1080 + rang,
              chemin=f"/rushes/{nom}.mov")
         for rang, nom in enumerate(NOMS_QUI_NE_DIFFERENT_QUE_PAR_LEUR_SUFFIXE)],
        [lot(f"{nom}_12", nom, 1000 + rang) for rang, nom
         in enumerate(NOMS_QUI_NE_DIFFERENT_QUE_PAR_LEUR_SUFFIXE)])


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_deux_lots_du_MEME_rush_restent_DISTINCTS_apres_elision(ascii_seul):
    """`J2`, exigence de l'arbitrage : **elide au MILIEU, jamais par la fin**.

    Les trois noms ne different que par leur derniere partie. Coupes par la
    fin, ils rendraient tous les trois `projet_demo_rush_hi…` -- trois lignes
    identiques pour trois rushes differents. `jetons.abreger_nom` garde les
    **deux bouts**, et c'est cela qui rend l'option `a` tenable.

    L'assertion est une **egalite de cardinal** et non une appartenance : « le
    suffixe A est visible » ne dit rien des deux autres, alors que « les trois
    lignes rendues sont deux a deux distinctes » mesure la propriete ET son
    unicite.
    """
    liste = rushes.ListeDesRushes(
        rushes.rushes_du_manifeste(document_aux_suffixes_voisins(),
                                   existe=lambda chemin: True))
    lignes = liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
    # **Le nom se lit a sa COLONNE**, jamais par decoupage en mots : la ligne
    # du curseur porte un glyphe de plus que les autres, et un `split()[1]`
    # lirait le nom sur l'une et la cadence sur les autres.
    noms = [ligne[rushes.COLONNE_NOM:
                  rushes.COLONNE_NOM + PLACE_DU_NOM_AU_PLANCHER].strip()
            for ligne in lignes]

    assert len(set(noms)) == len(noms), (
        "deux rushes rendent le meme nom a l'ecran : l'elision a mange le "
        f"suffixe qui les distingue -- {noms}")
    points = jetons.points_d_abregement(ascii_seul)
    for nom_rendu, nom_source in zip(noms,
                                     NOMS_QUI_NE_DIFFERENT_QUE_PAR_LEUR_SUFFIXE):
        assert points in nom_rendu, (
            f"{nom_rendu!r} n'est pas elide : la fabrique doit porter des noms "
            "PLUS LONGS que la colonne, sinon elle ne mesure rien")
        tete, queue = nom_rendu.split(points)
        assert nom_source.startswith(tete) and nom_source.endswith(queue), (
            nom_rendu, nom_source)
        assert queue, (
            f"{nom_rendu!r} n'a plus de queue : elide par la FIN, deux lots du "
            "meme rush deviennent indiscernables (risque R12 a l'ecran)")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_phrase_d_AJOUT_suit_la_colonne_technique_D_UNE_colonne(
        tmp_path, banc, racine_depot, ascii_seul):
    """`COLONNE_PHRASE_D_AJOUT` est **derivee**, et c'est mesure ici.

    Elle valait `31` en litteral. Quand `Q8` a ramene la colonne technique de
    30 a 26, un litteral laisse la aurait fait flotter la phrase **cinq
    colonnes** a droite de la colonne qu'elle suit -- sous un commentaire
    disant « une colonne apres celle de la technique » devenu faux. Aucun banc
    ne l'aurait vu : ceux du lot `I` mesurent que le TEXTE est present, jamais
    a quelle colonne.

    La mesure se fait contre la **maquette**, qui fait foi sur les colonnes
    comme sur le texte (`test_rushes.py` en fait autant pour les lignes de
    rush). En repli ASCII la maquette n'existe pas : on y mesure l'invariant
    lui-meme, la phrase commencant une colonne apres la technique.
    """
    ecran = ecran_de(tmp_path)
    ligne = [texte for texte in corps_rendu(banc, ecran, ascii_seul).splitlines()
             if rushes.AJOUTER_UN_RUSH in texte]
    assert len(ligne) == 1, ligne
    rendue = ligne[0]

    debut = jetons.colonnes(
        rendue[:rendue.index(_premier_mot_de_la_phrase(ascii_seul))])
    assert debut == rushes.COLONNE_TECHNIQUE + 1, (
        f"la phrase commence en {debut}, la colonne technique en "
        f"{rushes.COLONNE_TECHNIQUE} : le decalage d'UNE colonne est perdu")

    if not ascii_seul:
        maquette = (racine_depot / "_bmad-output" / "planning-artifacts"
                    / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
                    / "E2-1-extraction-rush.txt").read_text(encoding="utf-8")
        attendue = [ligne_m[2:-2].rstrip() for ligne_m in maquette.splitlines()
                    if rushes.AJOUTER_UN_RUSH in ligne_m]
        assert len(attendue) == 1, attendue
        assert rendue.rstrip() == attendue[0], (rendue, attendue[0])


def _premier_mot_de_la_phrase(ascii_seul: bool) -> str:
    """`choisir` -- le premier mot de `PHRASE_AJOUTER_UN_RUSH`, replie au besoin.

    Lu de la constante et jamais recopie : c'est ce mot qui marque le debut de
    la phrase, et l'ecrire en dur ferait un second endroit a corriger le jour
    ou la maquette change de verbe.
    """
    phrase = rushes.PHRASE_AJOUTER_UN_RUSH
    if ascii_seul:
        phrase = jetons.replier_ascii(phrase)
    return phrase.split()[0]


def test_la_CIBLE_au_milieu_est_celle_que_l_ecran_designe(tmp_path):
    """Volet monte, et la cible est la **deuxieme** des trois.

    Un `find` fautif qui rendrait le premier, comme une boucle fautive qui
    rendrait le dernier, se demasquent tous deux ici -- c'est le point 2 et le
    point 2 bis de la regle des fabriques, sur la meme fabrique.
    """
    vise = NOMS_QUI_NE_DIFFERENT_QUE_PAR_LEUR_SUFFIXE[1]
    ecran = ecran_de(tmp_path, document_aux_suffixes_voisins(),
                     existe=lambda chemin: True)
    ecran.liste.viser(vise)
    assert ecran.liste.courant.rush_id == vise
    lignes, rang, _etats = ecran.composer(jetons.LARGEUR_PLANCHER, False)
    assert rang is not None
    # La ligne surlignee porte la QUEUE du nom vise, pas celle de ses voisins :
    # c'est ce que l'elision au milieu preserve, et c'est la SEULE chose qui
    # distingue ces trois noms l'un de l'autre.
    assert "_B_25" in lignes[rang], lignes[rang]
    for autre in ("_A_25", "_C_25"):
        assert autre not in lignes[rang], (autre, lignes[rang])


# ---------------------------------------------------------------------------
# `J1` -- la liste des rushes n'avait AUCUNE fenetre de defilement
# ---------------------------------------------------------------------------
#
# **Le defaut, et pourquoi aucun banc ne le voyait.** `ListeDesRushes.rendu`
# rendait une ligne par rush declare, sans borne. Au-dela d'une douzaine de
# rushes -- ce qu'un projet reel depasse largement --, `E2-1` debordait la zone
# centrale : la ligne `Ajouter un rush` et tout le bloc `r` / `d` tombaient hors
# de l'ecran. Tous les bancs de ce fichier montaient TROIS rushes, c'est-a-dire
# la seule taille ou le defaut n'existe pas.
#
# Ces bancs-ci mesurent donc **vingt** rushes, et ils mesurent la HAUTEUR --
# `len(lignes)` --, jamais la largeur : c'est la dimension que personne ne
# regardait, et c'est la meme lecon que `I1` avait deja payee sur `E2-2`.

#: Vingt rushes : plus que la douzaine ou le defaut mord, et assez pour que la
#: fenetre ait du contenu au-dessus **et** au-dessous d'elle a la fois.
COMBIEN_DE_RUSHES = 20

#: Le rang de l'absent dans la liste longue. **Ni le premier, ni le dernier**,
#: et c'est le point 2 bis de la regle des fabriques : une fabrique a deux
#: elements dont la cible est en second la place aussi en dernier, et les deux
#: formes y sont indiscernables. Une fenetre de defilement est litteralement une
#: boucle sur une collection -- c'est la famille de fautes que le point 2 bis
#: vise, et le rang 9 sur 20 la demasque.
RANG_DE_L_ABSENT = 9


def document_long(combien: int = COMBIEN_DE_RUSHES,
                  rang_absent: int = RANG_DE_L_ABSENT):
    """Vingt rushes **distinguables**, l'absent au MILIEU.

    Chaque rush porte une cadence, une resolution et un cardinal differents : un
    remplissage uniforme rendrait invisible tout appariement decale entre la
    fenetre et les lignes qu'elle rend -- c'est le mutant `M33` de la 5.6, et le
    depot en est a sa cinquieme recidive sur cette famille.
    """
    declares, lots = [], []
    for rang in range(combien):
        nom = f"rush_{rang:02d}"
        absent = rang == rang_absent
        declares.append(rush(
            nom, fps=24.0 + rang, largeur=1920 + rang, hauteur=1080 + rang,
            chemin=(f"/perdu/{nom}.mov" if absent else f"/rushes/{nom}.mov")))
        lots.append(lot(f"{nom}_12", nom, 1000 + rang))
    return manifeste(declares, lots)


def liste_longue(combien: int = COMBIEN_DE_RUSHES,
                 rang_absent: int = RANG_DE_L_ABSENT):
    """Le modele pur, monte sur le document long. Aucun ecran, aucun clavier."""
    document = document_long(combien, rang_absent)
    absent = document["rushes"][rang_absent]["source_path"]
    return rushes.ListeDesRushes(
        rushes.rushes_du_manifeste(document, existe=existe_sauf(absent)))


def ecran_long(tmp_path, combien: int = COMBIEN_DE_RUSHES,
               rang_absent: int = RANG_DE_L_ABSENT):
    document = document_long(combien, rang_absent)
    absent = document["rushes"][rang_absent]["source_path"]
    return ecran_de(tmp_path, document, existe=existe_sauf(absent))


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("rang", list(range(COMBIEN_DE_RUSHES)))
def test_E2_1_TIENT_la_zone_centrale_sur_VINGT_rushes(tmp_path, rang,
                                                      ascii_seul):
    """`J1` : la composition ne deborde **a aucun rang du curseur**.

    Le curseur est promene sur les vingt rangs, et le rang 9 ouvre en plus le
    bloc `r` / `d` : c'est le pire cas, et il ne se distingue des autres que
    parce que la cible est au MILIEU de la liste.

    **La :class:`Composition` REND son debordement** au lieu de le tronquer en
    silence (`I1`) -- c'est ce qui rend ce banc capable de le voir. Sans elle,
    `textual` couperait par le bas et l'assertion porterait sur des lignes que
    l'ecran ne dessine pas.
    """
    ecran = ecran_long(tmp_path)
    ecran.liste.poser_le_curseur(rang)
    lignes, _rang, _etats = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, (
        f"curseur au rang {rang} : {len(lignes)} lignes composees pour "
        f"{jetons.HAUTEUR_CENTRE_AU_PLANCHER} dessinees ; la liste deborde")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_fenetre_ne_montre_JAMAIS_plus_que_son_budget(ascii_seul):
    """La borne haute, mesuree en lignes RENDUES et dans les deux regimes.

    Le repli ASCII peut **allonger** une ligne (`…` rend `...`), jamais en
    ajouter une : le compte doit donc etre le meme des deux cotes, et un banc
    qui ne mesurerait qu'un regime laisserait passer une ligne de position
    posee deux fois.
    """
    liste = liste_longue()
    for rang in range(COMBIEN_DE_RUSHES):
        liste.poser_le_curseur(rang)
        rendues = liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
        assert len(rendues) <= rushes.HAUTEUR_LISTE, (
            f"rang {rang} : {len(rendues)} lignes pour "
            f"{rushes.HAUTEUR_LISTE} de budget")


def test_la_fenetre_REMPLIT_son_budget_quand_la_liste_est_longue():
    """Volet symetrique du precedent : une borne trop **basse** passerait
    sinon. Une fenetre qui ne montrerait qu'un rush par ecran tiendrait la
    grille sans rien montrer, et le banc du dessus resterait vert."""
    liste = liste_longue()
    liste.poser_le_curseur(0)
    assert len(liste.rendu()) == rushes.HAUTEUR_LISTE


def test_les_rushes_HORS_FENETRE_ne_sont_pas_rendus():
    """Ce que la fenetre retire, elle le retire vraiment.

    Mesure d'**egalite** et non d'appartenance : « le rang 0 est rendu » ne dit
    rien de ce qui l'accompagne, alors que « l'ensemble des rushes rendus est
    exactement celui de la fenetre » mesure la borne ET son unicite.
    """
    liste = liste_longue()
    liste.poser_le_curseur(0)
    rendu = "\n".join(liste.rendu())
    premier, dernier = liste.fenetre()
    montres = {rush_vu.rush_id for rush_vu in liste.rushes
               if rush_vu.rush_id in rendu}
    attendus = {liste.rushes[rang].rush_id
                for rang in range(premier, dernier + 1)}
    assert montres == attendus, (sorted(montres), sorted(attendus))
    assert dernier < COMBIEN_DE_RUSHES - 1, (
        "avec vingt rushes pour sept lignes, la fenetre ne peut pas atteindre "
        "le dernier rang depuis le premier")


def test_le_DERNIER_rush_ne_se_cache_pas_derriere_le_point_qui_l_annonce():
    """La ligne `…` se reserve **avant** le decoupage.

    C'est la borne exacte que le mutant « decalee d'un » deplace : une place
    calculee apres coup ferait rendre un rush de plus que la fenetre n'a de
    lignes, ou cacherait le dernier derriere le `…` qui annonce qu'il existe.
    Mesure au rang le plus bas : le curseur y est, donc il DOIT etre visible.
    """
    liste = liste_longue()
    liste.poser_le_curseur(COMBIEN_DE_RUSHES - 1)
    premier, dernier = liste.fenetre()
    assert dernier == COMBIEN_DE_RUSHES - 1, (premier, dernier)
    rendues = liste.rendu()
    assert len(rendues) == rushes.HAUTEUR_LISTE, len(rendues)
    assert liste.rushes[-1].rush_id in rendues[-1], rendues[-1]
    points = jetons.points_d_abregement()
    assert rendues[0].strip() == points, (
        "arrive en bas, la fenetre porte un `…` de TETE et aucun de pied")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_de_position_dit_COMBIEN_il_reste(ascii_seul):
    """`…   1-6 sur 20 rushes` : le `…` dit qu'il y a un ailleurs, la position
    dit sa taille. Sans elle, l'operateur ne sait pas s'il lui reste trois
    rushes ou quarante.

    Le pluriel vient de `projet_lecture.accorder` -- le depot ecrit « rushes »,
    et un `+ "s"` mecanique rendrait « 20 rushs ».
    """
    liste = liste_longue()
    liste.poser_le_curseur(0)
    premier, dernier = liste.fenetre()
    derniere = liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)[-1]
    attendu = f"{premier + 1}-{dernier + 1} sur 20 rushes"
    if ascii_seul:
        attendu = jetons.replier_ascii(attendu)
    assert attendu in derniere, (attendu, derniere)
    assert jetons.colonnes(derniere) <= jetons.largeur_utile(), derniere


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_fenetre_SUIT_le_curseur_dans_les_deux_sens(ascii_seul):
    """Le rush sous le curseur est **toujours** rendu, a chacun des vingt rangs
    puis en remontant. Une fenetre qui ne suivrait qu'en descendant laisserait
    le curseur derriere elle des la premiere fleche vers le haut."""
    liste = liste_longue()
    parcours = (list(range(COMBIEN_DE_RUSHES))
                + list(reversed(range(COMBIEN_DE_RUSHES))))
    liste.poser_le_curseur(0)
    precedent = 0
    for rang in parcours:
        liste.deplacer(rang - precedent)
        precedent = rang
        assert liste.curseur == rang
        rendu = "\n".join(liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul))
        assert liste.rushes[rang].rush_id in rendu, (
            f"le rush du rang {rang} est sous le curseur et hors fenetre")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_rang_du_curseur_DESIGNE_la_ligne_du_rush_vise(ascii_seul):
    """`rang_du_curseur()` indexe **les lignes rendues**, `…` compris.

    C'est le decalage que la fenetre introduit : avant `J1` le rang du curseur
    etait l'index du rush, et il l'est resté juste tant que la liste tenait
    entiere. Le banc le mesure aux vingt rangs, donc y compris sous un `…` de
    tete -- le seul regime ou les deux nombres different.
    """
    liste = liste_longue()
    for rang in range(COMBIEN_DE_RUSHES):
        liste.poser_le_curseur(rang)
        rendues = liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
        surlignee = liste.rang_du_curseur()
        assert surlignee is not None, rang
        assert 0 <= surlignee < len(rendues), (surlignee, len(rendues))
        assert liste.rushes[rang].rush_id in rendues[surlignee], (
            f"rang {rang} : la ligne {surlignee} porte "
            f"{rendues[surlignee]!r}, pas le rush vise")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_les_etats_des_lignes_DESIGNENT_les_lignes_rendues(ascii_seul):
    """`etats_des_lignes()` est reindexe comme le rang du curseur.

    Une table indexee sur la liste entiere peindrait la couleur d'un rush hors
    fenetre sur la ligne d'un autre : avec l'absent au rang 9 et une fenetre de
    sept, c'est litteralement une croix rouge posee sur un rush lie.
    """
    liste = liste_longue()
    for rang in range(COMBIEN_DE_RUSHES):
        liste.poser_le_curseur(rang)
        rendues = liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
        etats = liste.etats_des_lignes()
        assert set(etats) <= set(range(len(rendues))), (rang, sorted(etats))
        marque = rushes.LIBELLE_ABSENT
        if ascii_seul:
            marque = jetons.replier_ascii(marque)
        for ligne_rendue, nom_etat in etats.items():
            porte_absent = marque in rendues[ligne_rendue]
            assert (nom_etat == "absent") == porte_absent, (
                f"rang {rang}, ligne {ligne_rendue} : etat {nom_etat!r} pour "
                f"{rendues[ligne_rendue]!r}")


def test_relire_apres_un_AJOUT_garde_le_curseur_dans_la_fenetre(tmp_path):
    """`relire()` repose le curseur **par `poser_le_curseur`**.

    Il ecrivait `liste.curseur` directement : sur une liste longue, la fenetre
    de la liste neuve repartait du rang 0 et la ligne surlignee n'etait plus a
    l'ecran. Le banc mesure que le rush vise est rendu APRES la relecture.
    """
    ecran = ecran_long(tmp_path)
    ecran.liste.poser_le_curseur(COMBIEN_DE_RUSHES - 2)
    vise = ecran.liste.courant.rush_id
    ecran.relire()
    assert ecran.liste.courant.rush_id == vise
    assert vise in "\n".join(ecran.liste.rendu()), (
        "le curseur a survecu a la relecture, la fenetre non")


def test_TROIS_rushes_ne_declenchent_NI_fenetre_NI_position(tmp_path):
    """Volet symetrique, et il tient la maquette `E2-1` : sous le budget, la
    liste se rend entiere, sans `…` et sans ligne de position -- `Ajouter un
    rush` suit immediatement le dernier rush, comme la maquette le montre.

    Sans ce volet, une fenetre qui poserait ses `…` en toutes circonstances
    passerait tous les bancs ci-dessus.
    """
    ecran = ecran_de(tmp_path)
    rendues = ecran.liste.rendu()
    assert len(rendues) == 3, rendues
    assert jetons.points_d_abregement() not in "\n".join(rendues)
    assert ecran.liste.fenetre() == (0, 2)
    assert ecran.liste.rang_du_curseur() == 0


@pytest.mark.parametrize("rang", [0, RANG_DE_L_ABSENT, COMBIEN_DE_RUSHES - 1])
def test_viser_un_rush_le_RAMENE_DANS_la_fenetre(rang):
    """`viser()` recadre, comme `deplacer()`.

    **Trouve par la campagne du lot J** (mutant `M9`, survivant) : le banc de
    la fenetre ne passait que par `deplacer` et `poser_le_curseur`, si bien
    qu'un `viser` sans recadrage restait vert. Or `viser` est le chemin que
    l'ECRAN emprunte -- `EcranRushes` l'appelle pour poser le curseur sur un
    rush nomme --, donc le seul mutant survivant portait sur le chemin reel.

    Les trois rangs mesures couvrent les trois regimes de la fenetre : avant
    elle, dedans, apres elle. Le rang du milieu n'est pas decoratif -- une
    fabrique a deux elements confondrait « second » et « dernier ».
    """
    liste = liste_longue()
    # Partir du BAS : viser vers le haut et vers le bas depuis le meme etat
    # n'emprunte pas la meme branche du recadrage.
    liste.poser_le_curseur(COMBIEN_DE_RUSHES - 1)
    vise = liste.rushes[rang].rush_id
    rendu = liste.viser(vise)
    assert rendu.rush_id == vise
    assert liste.curseur == rang
    lignes = liste.rendu()
    assert vise in "\n".join(lignes), (
        f"{vise} est vise et hors fenetre : `viser` n'a pas recadre")
    surlignee = liste.rang_du_curseur()
    assert surlignee is not None and vise in lignes[surlignee], (
        surlignee, lignes)


def test_l_ECRAN_qui_vise_un_rush_le_MONTRE(tmp_path):
    """Le volet monte du precedent : c'est `EcranRushes` qui appelle `viser`,
    et c'est a l'ecran que le defaut se serait vu."""
    ecran = ecran_long(tmp_path)
    ecran.liste.viser(f"rush_{COMBIEN_DE_RUSHES - 1:02d}")
    lignes, rang, _etats = ecran.composer(jetons.LARGEUR_PLANCHER, False)
    assert rang is not None
    assert f"rush_{COMBIEN_DE_RUSHES - 1:02d}" in lignes[rang], lignes


#: Ce que `E2-1` pose de blancs autour de la liste, selon que le bloc `r` / `d`
#: est ouvert ou non. **Ce sont les `respirer()` de la composition**, et aucune
#: autre ligne de cet ecran n'est vide : les lignes de rush, le titre, le filet,
#: `Ajouter un rush` et les lignes de mode portent toutes du texte.
RESPIRATIONS_SANS_RELINK = 2      # le blanc de tete, celui qui suit le titre
RESPIRATIONS_AVEC_RELINK = 4      # plus les deux qui encadrent le filet


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("rang", list(range(COMBIEN_DE_RUSHES)))
def test_E2_1_GARDE_ses_respirations_sur_VINGT_rushes(tmp_path, rang,
                                                      ascii_seul):
    """La liste tient la zone **sans faire tomber un seul blanc**.

    **Trouve par la campagne du lot J** (mutant `M5`, survivant de la premiere
    passe) : porter `HAUTEUR_LISTE` de 7 a 11 ne fait PAS deborder `E2-1`, donc
    le banc de hauteur restait vert. Il ne deborde pas parce que
    `Composition` **sacrifie ses quatre respirations** -- ce qu'elle a le droit
    de faire, c'est son contrat. L'ecran obtenu n'a alors plus un seul blanc
    entre le titre, la liste et le bloc `r` / `d`, et ne ressemble plus a sa
    maquette.

    Le budget de la fenetre protege donc deux choses, et le banc doit mesurer
    les deux : que rien ne deborde, et que rien n'ait eu besoin d'etre
    sacrifie pour cela. Sans ce second volet, tout budget jusqu'a 11 passait.
    """
    ecran = ecran_long(tmp_path)
    ecran.liste.poser_le_curseur(rang)
    lignes, _rang, _etats = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
    attendu = (RESPIRATIONS_AVEC_RELINK if rang == RANG_DE_L_ABSENT
               else RESPIRATIONS_SANS_RELINK)
    vides = sum(1 for ligne in lignes if not ligne.strip())
    assert vides == attendu, (
        f"curseur au rang {rang} : {vides} respirations pour {attendu} ; la "
        "composition en a sacrifie pour tenir la zone, donc le budget de la "
        "fenetre est trop haut")
