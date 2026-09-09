# -*- coding: utf-8 -*-
"""Lot `MQ-B` -- la famille « la ligne d'etat ment » (audit du 2026-09-06).

**Ce que ce banc mesure, et pourquoi il est UN alors que les manques sont
CINQ.** Les cinq manques `MQ-1`, `MQ-2`, `MQ-3`, `MQ-6` et `MQ-7` ne partagent
ni module ni ecran ; ils partagent un **mode de panne** : le pied de l'ecran
promet une touche que l'ecran ne tient pas, ou tient une touche qu'il
n'annonce pas, ou refuse sans offrir d'issue. C'est ce mode de panne qui se
mesure ici, et le regrouper est ce qui rend visible qu'il se repete -- cinq
fichiers de banc l'auraient dilue en cinq details.

Les cinq regimes, tels que l'audit les a joues au clavier :

* `MQ-1` -- liste des rushes **vide** : `⏎` est annonce et strictement inerte
  (quatre frappes, pile, texte et ligne d'etat identiques). Seul `Tab` marche,
  et il faut le deviner ;
* `MQ-2` -- explorateur d'ajout d'un rush : valider le **dossier** propose par
  defaut mene a « pas encore » (`chemin_non_fichier`), alors que l'explorateur
  sait deja que la cible est un dossier ;
* `MQ-3` -- `EcranRushes` est la seule STATION a n'annoncer ni `F1` ni `Q`,
  alors que les deux marchent ;
* `MQ-6` -- reglages de la mire : `⏎ continuer` est annonce, refuse en
  silence, et le champ obligatoire ne porte pas la mention `requis` que les
  deux ecrans jumeaux du Scan portent deja ;
* `MQ-7` -- le refus de l'atelier Exports n'offre aucune suite, ses deux
  issues annoncees sont deux abandons, et `Échap` -- la seule qui ramene au
  travail -- n'est pas annoncee (`EPIC11-ARB-89`).

**Regle des fabriques (`CLAUDE.md`), et elle mord ici a ses QUATRE points.**
Le corpus de rushes porte **trois** elements distinguables (cadences,
resolutions et etats de liaison differents) ; la cible est jouee en **tete**,
au **milieu** et en **queue**, parce qu'un `⏎` fautif qui viserait toujours le
premier rang et un balayage qui sauterait le dernier sont deux modes de panne
distincts ; et l'ensemble des neuf sites de montage d'`EcranRefus` est mesure
**entier**, pas par echantillon.

**Ce que ce banc NE mesure PAS, dit plutot que tu.**

* il ne mesure pas ou `Échap` **atterrit** depuis chacun des neuf sites
  d'`EcranRefus`. Il mesure que la touche depile, et que les neuf sites
  partagent la meme annonce ; le palier retrouve depend de ce que chaque
  parcours a empile dessous, et deux d'entre eux (detection et ecriture du
  Scan) laissent leur ecran d'execution sous le refus ;
* il ne mesure pas le second palier de `MQ-2` (les quatre motifs de refus de
  declaration generalises a `EcranRefus`) ni celui de `MQ-7` (les suites
  renseignees du refus Exports). Les deux restent ouverts et chiffres dans le
  compte rendu du lot ;
* la garde de `MQ-7` a une **limite nommee** : pendant une tache,
  `action_remonter` arme l'interruption au lieu de depiler, donc `Échap`
  annonce ne depilerait pas. Elle est mesuree ci-dessous comme limite, et
  aucun des neuf sites ne monte le refus avec une tache en cours -- les deux
  du Scan appellent `oublier_la_tache()` juste avant.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.io import extraction_manifest
from mixed_media_utility.tui import (
    atelier_extraction,
    atelier_pdf_calibration,
    atelier_scan,
    execution,
    jetons,
    rushes,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.explorateur import Explorateur
from mixed_media_utility.tui.manuel import classes_d_ecran

import test_atelier_extraction_rushes as banc_rushes
import test_ecrans_declaration_de_rush as banc_declaration


PAQUET_TUI = Path(_SRC) / "mixed_media_utility" / "tui"


# ===========================================================================
# Fabriques -- trois rushes distinguables, et le projet VIDE que `MQ-1` vise
# ===========================================================================

def document_vide() -> dict:
    """Un projet neuf : zero rush declare. C'est le regime de `MQ-1`."""
    return banc_rushes.manifeste([], [])


def projet_vide(tmp_path) -> Path:
    dossier = tmp_path / "projet_neuf"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(document_vide(), indent=2, ensure_ascii=False,
                   sort_keys=True) + "\n",
        encoding="utf-8")
    return dossier


def bac_a_designer(tmp_path) -> Path:
    """Un bac a **deux** sous-dossiers et **deux** fichiers, distinguables.

    Deux de chaque, et non un : une fabrique mono-element ne demasque ni un
    appariement inverse ni un balayage tronque, et c'est la regle des
    fabriques du depot prise a la lettre. Les noms sont ordonnes pour que
    « le premier » et « le dernier » soient deux entrees differentes.
    """
    bac = tmp_path / "bac"
    (bac / "aa_premier_dossier").mkdir(parents=True)
    (bac / "zz_dernier_dossier").mkdir(parents=True)
    (bac / "aa_premier.mov").write_bytes(b"\x00" * 32)
    (bac / "zz_dernier.mov").write_bytes(b"\x00" * 64)
    return bac


def ecran_vide(tmp_path, **kwargs) -> atelier_extraction.EcranRushes:
    return atelier_extraction.EcranRushes(projet_vide(tmp_path), **kwargs)


def coque(*ecrans) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "Q quitter"),
                             PalierTemoin("Ateliers", "Q quitter"), *ecrans],
                    contexte=Contexte("projet_demo"))


# ===========================================================================
# `MQ-1` -- `⏎` sur une liste VIDE ouvre l'explorateur d'ajout
# ===========================================================================

def test_MQ1_choisir_sur_une_liste_VIDE_ouvre_l_explorateur_d_ajout(tmp_path):
    """Le geste naturel du premier ecran de travail du produit.

    L'audit a mesure quatre frappes (`⏎`, `↑`, `↓`, `⏎`) sans qu'une seule
    change quoi que ce soit : ni la pile, ni le texte, ni la ligne d'etat.
    `Tab` etait la seule sortie, et il fallait la deviner.
    """
    ecran = ecran_vide(tmp_path)
    assert ecran.liste.action_du_choix() is None, (
        "le regime mesure est bien la liste vide")

    assert ecran.traiter("enter") is True
    assert ecran.zone == atelier_extraction.ZONE_EXPLORATEUR
    assert ecran.but == atelier_extraction.BUT_AJOUTER
    assert ecran.mode == rushes.MODE_DESIGNER


def test_MQ1_le_chemin_de_la_touche_ENTREE_est_celui_de_TAB(tmp_path):
    """La meme destination par les deux touches, mesuree par comparaison.

    Le prendre par egalite plutot qu'en reecrivant les trois attributs
    attendus : une destination qui divergerait de celle de `Tab` serait un
    second chemin d'ajout, c'est-a-dire le defaut que la couture partagee de
    l'explorateur existe pour empecher.
    """
    par_tab = ecran_vide(tmp_path)
    par_tab.traiter("tab")
    par_entree = ecran_vide(tmp_path)
    par_entree.traiter("enter")

    assert ((par_entree.zone, par_entree.but, par_entree.mode)
            == (par_tab.zone, par_tab.but, par_tab.mode))


@pytest.mark.parametrize("rush_id,attendu_zone,attendu_but", [
    # La cible en TETE, au MILIEU et en QUEUE : trois rangs, trois issues
    # mesurees. Le rang de queue est l'absent, donc c'est aussi lui qui
    # demasquerait un balayage tronque.
    ("rush_01", atelier_extraction.ZONE_LISTE, None),
    ("zz_rush_02", atelier_extraction.ZONE_LISTE, None),
    ("rush_hiver", atelier_extraction.ZONE_EXPLORATEUR,
     atelier_extraction.BUT_RELINK),
])
def test_MQ1_une_liste_NON_VIDE_garde_ses_trois_issues(
        tmp_path, rush_id, attendu_zone, attendu_but):
    """Le volet symetrique, et il est **obligatoire**.

    Router `action is None` vers l'ajout ne doit rien changer aux trois rangs
    qui portent une action : un rush lie s'extrait, un rush absent ouvre le
    relink. Sans ces trois mesures, une garde ecrite trop large ouvrirait
    l'explorateur d'ajout sur n'importe quel `⏎`.
    """
    extraits: list[str] = []
    ecran = banc_rushes.ecran_de(tmp_path, extraire=extraits.append)
    ecran.liste.viser(rush_id)

    ecran.traiter("enter")

    assert ecran.zone == attendu_zone
    assert ecran.but == attendu_but
    assert extraits == ([] if attendu_but else [rush_id])


# ===========================================================================
# `MQ-2` -- valider un DOSSIER dans l'explorateur d'ajout se refuse EN LIGNE
# ===========================================================================

def ecran_sur_le_bac(tmp_path, *, but=atelier_extraction.BUT_AJOUTER,
                     **kwargs) -> atelier_extraction.EcranRushes:
    """Un `EcranRushes` dont l'explorateur d'ajout est pose sur le bac."""
    ecran = banc_rushes.ecran_de(tmp_path, **kwargs)
    bac = bac_a_designer(tmp_path)
    for mode in (rushes.MODE_DESIGNER, rushes.MODE_RETROUVER):
        ecran._explorateurs[mode] = Explorateur(
            depart=bac, montrer_fichiers=rushes.MONTRER_FICHIERS[mode])
    mode = (rushes.MODE_DESIGNER if but == atelier_extraction.BUT_AJOUTER
            else rushes.MODE_RETROUVER)
    if but == atelier_extraction.BUT_RELINK:
        ecran.liste.viser("rush_hiver")
    ecran._ouvrir_l_explorateur(but, mode)
    return ecran


@pytest.mark.parametrize("rang", [0, 1])
def test_MQ2_valider_un_DOSSIER_refuse_EN_LIGNE_et_ne_quitte_pas_l_ecran(
        tmp_path, banc, rang):
    """Les DEUX dossiers du bac, le premier et le dernier.

    Le rang 0 est celui que l'explorateur propose **a l'ouverture** -- c'est
    la quatrieme frappe du regime mesure par l'audit --, le rang 1 est le
    dernier dossier de la liste : une garde qui ne verrait que la premiere
    entree laisserait le second passer.
    """
    prepares: list[Path] = []
    ecran = ecran_sur_le_bac(tmp_path, preparer=prepares.append)
    ecran.explorateur.deplacer(rang)
    cible = ecran.explorateur.cible_de_validation()
    assert cible is not None and cible.is_dir(), cible

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran._valider_l_explorateur()
        await pilote.pause()
        return None

    banc(coque(), scenario)

    assert prepares == [], "le temps 1 ne doit PAS etre appele sur un dossier"
    assert ecran.zone == atelier_extraction.ZONE_EXPLORATEUR, (
        "l'explorateur reste ouvert : on ne quitte pas l'ecran pour dire non")
    assert atelier_extraction.MOTIF_CIBLE_NON_FICHIER in ecran._etat_a_dire


@pytest.mark.parametrize("rang", [2, 3])
def test_MQ2_valider_un_FICHIER_appelle_toujours_le_temps_1(tmp_path, banc,
                                                            rang):
    """Volet symetrique : la garde ne doit pas fermer le chemin nominal.

    Les DEUX fichiers du bac sont joues -- le premier et le dernier de la
    liste. L'ecran est monte pour de vrai : le temps 1 empile `EcranDeclaration`,
    donc il lui faut une application.
    """
    prepares: list[Path] = []

    def preparer(cible):
        # Le temps 1 rend une **vraie** preparation : `EcranDeclaration` la
        # peint des qu'il est monte, et un `None` y tomberait sur un defaut
        # du banc plutot que sur la mesure cherchee.
        prepares.append(cible)
        return banc_declaration.preparee(chemin=str(cible))

    ecran = ecran_sur_le_bac(tmp_path, preparer=preparer)
    ecran.explorateur.deplacer(rang)
    cible = ecran.explorateur.cible_de_validation()
    assert cible is not None and cible.is_file(), cible

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran._valider_l_explorateur()
        await pilote.pause()
        return None

    banc(coque(), scenario)

    assert prepares == [cible], (
        "les deux fichiers du bac sont joues, dont le DERNIER : un appel qui "
        "viserait toujours la premiere entree ne se demasque pas autrement")
    assert ecran.zone == atelier_extraction.ZONE_LISTE


def test_MQ2_la_garde_ne_touche_PAS_le_relink(tmp_path, banc):
    """Second volet symetrique, et il n'est pas decoratif.

    Le relink par `r` parcourt des **dossiers** et les valide : c'est son
    mode nominal (`MODE_RETROUVER`). Une garde ecrite sur la cible plutot que
    sur le BUT fermerait ce chemin-la en silence.
    """
    ecran = ecran_sur_le_bac(tmp_path, but=atelier_extraction.BUT_RELINK)
    vus: list[Path] = []
    ecran._relinker = lambda cible: vus.append(cible)
    cible = ecran.explorateur.cible_de_validation()
    assert cible is not None and cible.is_dir(), cible

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran._valider_l_explorateur()
        await pilote.pause()
        return None

    banc(coque(), scenario)

    assert vus == [cible]
    assert ecran._etat_a_dire == ""


def test_MQ2_le_motif_du_refus_ne_porte_ni_touche_ni_conseil():
    """`EPIC11-ARB-56` : une ligne d'etat mesure, elle ne conseille pas."""
    motif = atelier_extraction.MOTIF_CIBLE_NON_FICHIER
    assert "⏎" not in motif and "Tab" not in motif and "Échap" not in motif
    assert "→" not in motif
    assert jetons.colonnes(jetons.replier_ascii(motif)) <= jetons.largeur_utile()


# ===========================================================================
# `MQ-3` -- la ligne des rushes annonce `F1`, et la LARGEUR est l'arbitrage
# ===========================================================================

def test_MQ3_la_ligne_des_rushes_annonce_F1():
    """`F1` **ouvre le manuel** depuis cet ecran : il doit donc etre annonce.

    `EPIC11-ARB-140` a tranche que les STATIONS annoncent `F1 aide` ;
    `EcranRushes` en est une (`TRANSITOIRE` faux) et etait la seule a l'omettre.
    """
    assert atelier_extraction.EcranRushes.TRANSITOIRE is False
    assert "F1 aide" in atelier_extraction.RACCOURCIS_RUSHES


def test_MQ3_la_ligne_des_rushes_tient_la_grille_en_UTF8_ET_en_ASCII():
    """La contrainte qui a decide de la redaction, mesuree ici a part.

    Le balayage general (`test_repli_ascii.py`) la couvre deja ; cette mesure
    la redit **sur cette ligne** parce que c'est elle qui a tranche entre
    `F1 aide` seul et `F1 aide  Q quitter`.
    """
    ligne = atelier_extraction.RACCOURCIS_RUSHES
    utile = jetons.largeur_utile()
    assert jetons.colonnes(ligne) <= utile, jetons.colonnes(ligne)
    assert jetons.colonnes(jetons.replier_ascii(ligne)) <= utile, (
        jetons.colonnes(jetons.replier_ascii(ligne)))


def test_MQ3_ajouter_Q_QUITTER_a_cette_ligne_la_ferait_DEBORDER():
    """**L'arbitrage de largeur, mesure et non suppose.**

    L'audit annoncait « 62 colonnes portees a 82 pour un plancher de 80 » ;
    la mesure reelle est autre et va dans le meme sens en pire : la zone utile
    au plancher vaut **76** colonnes (80 moins le cadre et les marges), et la
    ligne complete `… F1 aide  Q quitter` en vaut **79** en UTF-8 et **84**
    une fois repliee en ASCII. `jetons.ajuster` la couperait, donc `Q quitter`
    ne s'annonce pas ici -- ce qui reste conforme aux neuf autres ecrans qui
    l'omettent deja, la ou l'omission de `F1` etait unique.

    Ce test est ce qui empeche que la question soit rouverte a l'aveugle : il
    rougirait le jour ou la ligne raccourcirait assez pour que `Q quitter`
    entre, et c'est ce jour-la qu'il faudra le reposer.
    """
    utile = jetons.largeur_utile()
    complete = atelier_extraction.RACCOURCIS_RUSHES + "  Q quitter"
    assert max(jetons.colonnes(complete),
               jetons.colonnes(jetons.replier_ascii(complete))) > utile


#: Les stations dont l'omission de `F1` serait **tranchee** plutot qu'oubliee.
#: Vide, et c'est une mesure : au 2026-09-06, le recensement sur les quatorze
#: stations du paquet n'en trouve qu'une qui omette `F1`, et c'est celle que
#: `MQ-3` ferme. Une entree ajoutee ici doit porter son arbitrage.
STATIONS_SANS_F1_TOLEREES: frozenset[str] = frozenset()


def test_MQ3_le_recensement_des_STATIONS_est_NON_VIDE():
    """Volet symetrique : un recensement vide rendrait la mesure suivante muette."""
    stations = [nom for nom, classe in classes_d_ecran().items()
                if not classe.TRANSITOIRE and classe.raccourcis]
    assert len(stations) >= 10, sorted(stations)


def test_MQ3_aucune_autre_STATION_du_paquet_n_omet_F1():
    """Le volet qui dit que le manque est **ferme**, pas deplace.

    Recensement sur toutes les sous-classes de `Palier` du paquet : une
    station -- `TRANSITOIRE` faux -- qui porte une ligne de raccourcis non
    vide doit y annoncer `F1`. Les passages en sont exclus, ce qu'
    `EPIC11-ARB-140` prescrit.
    """
    manquantes = []
    for nom, classe in classes_d_ecran().items():
        if classe.TRANSITOIRE or not classe.raccourcis:
            continue
        if nom in STATIONS_SANS_F1_TOLEREES:
            continue
        if "F1" not in classe.raccourcis:
            manquantes.append((nom, classe.raccourcis))
    assert manquantes == [], manquantes


# ===========================================================================
# `MQ-6` -- la mire dit `requis`, et son refus se DIT
# ===========================================================================

def formulaire(chaine: str = "", commentaire: str = ""):
    return atelier_pdf_calibration.FormulaireDeLaMire(
        chaine=chaine, commentaire=commentaire)


def ecran_de_mire(chaine: str = "", commentaire: str = "", **kwargs):
    return atelier_pdf_calibration.EcranMireReglages(
        "projet_demo", formulaire=formulaire(chaine, commentaire), **kwargs)


def colonne_de(ligne: str, mention: str) -> int:
    """La colonne ou commence `mention` dans `ligne`, mesuree en COLONNES.

    En colonnes et non en caracteres : le glyphe de focus et le glyphe neutre
    de cet ecran ne sont pas de l'ASCII, et `len()` y dirait autre chose.
    """
    return jetons.colonnes(ligne[:ligne.rindex(mention)])


def rendu(banc, ecran, **kwargs) -> list[str]:
    """Les lignes de l'ecran, monte pour de vrai -- jamais une constante relue."""
    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return list(ecran.lignes())

    return banc(coque(), scenario)


@pytest.mark.parametrize("chaine,attendu", [
    ("", True),
    ("   ", True),        # blancs seuls : le coeur lit une chaine vide
    ("hp-envy-4520", False),
])
def test_MQ6_le_champ_de_chaine_porte_requis_TANT_QU_IL_EST_VIDE(
        banc, chaine, attendu):
    """La forme des deux ecrans jumeaux du Scan, portee ici.

    `EcranScanDepot` rend `Source  > ·   requis` et `EcranCalibrerLaChaine`
    rend `Scan de la page  > ·  requis` ; `E5-6` ne rendait rien, si bien que
    rien a l'ecran ne disait que le premier champ etait obligatoire.
    """
    lignes = rendu(banc, ecran_de_mire(chaine))
    ligne = next(l for l in lignes
                 if atelier_pdf_calibration.LIBELLES_DES_CHAMPS[
                     atelier_pdf_calibration.CHAMP_CHAINE] in l)
    assert (atelier_scan.MENTION_REQUIS in ligne) is attendu, ligne


def test_MQ6_le_COMMENTAIRE_ne_porte_JAMAIS_requis(banc):
    """Volet symetrique : le coeur accepte un commentaire absent.

    La cible est le SECOND champ du formulaire : une mention posee sur tous
    les champs plutot que sur le champ requis ne se demasque pas autrement.
    """
    lignes = rendu(banc, ecran_de_mire())
    ligne = next(l for l in lignes
                 if atelier_pdf_calibration.LIBELLES_DES_CHAMPS[
                     atelier_pdf_calibration.CHAMP_COMMENTAIRE] in l)
    assert atelier_scan.MENTION_REQUIS not in ligne, ligne


def test_MQ6_la_mention_se_cale_sur_la_COLONNE_des_lignes_imposees(banc):
    """Une seule colonne de mention sur cet ecran, et c'est un contrat.

    La maquette dessine sa propre mention a deux colonnes differentes selon
    la ligne ; le produit en tient **une** -- c'est ce que
    `LARGEUR_DE_LA_VALEUR` dit deja des lignes imposees, et la mention du
    champ requis doit s'y caler plutot que d'ouvrir une seconde colonne.
    """
    ecran = ecran_de_mire()
    lignes = rendu(banc, ecran)
    du_champ = next(l for l in lignes
                    if atelier_scan.MENTION_REQUIS in l)
    imposee = next(l for l in lignes
                   if atelier_pdf_calibration.LIBELLE_PASTILLES in l)
    mention_imposee = ecran.donnees.decomposition_longue
    assert mention_imposee and mention_imposee in imposee, imposee

    assert (colonne_de(du_champ, atelier_scan.MENTION_REQUIS)
            == colonne_de(imposee, mention_imposee)), (du_champ, imposee)


@pytest.mark.parametrize("chaine", ["", "   "])
def test_MQ6_continuer_sans_AUCUNE_chaine_pose_le_message_du_MANQUE(chaine):
    """`⏎ continuer` est annonce : il ne peut pas refuser en silence.

    Le regime mesure ici est celui du manque `MQ-6` proprement dit -- le champ
    **vide**, ou blanc, ce que `saisie` ramene au vide. C'est le seul des deux
    regimes de refus que l'ecran ne disait pas.
    """
    appels: list[object] = []
    ecran = ecran_de_mire(chaine, sur_continuer=appels.append)

    assert ecran.traiter("enter") is True

    assert appels == []
    assert ecran.etat() == atelier_pdf_calibration.ETAT_CHAINE_REQUISE


@pytest.mark.parametrize("chaine", ["---", "!!!", ".."])
def test_MQ6_une_chaine_INNOMMABLE_garde_la_phrase_du_finding_C2_2(chaine):
    """**Deux refus, deux phrases** -- et la seconde existait deja.

    `peut_continuer` est faux dans deux regimes, pas un : le champ vide, et le
    champ rempli d'un libelle que le coeur refuse de nommer (`---`, `!!!`,
    `..`). Le second portait deja sa phrase, posee par le finding `C2-2` :
    `ligne_d_etat_des_reglages(nommable=False)` rend
    `ETAT_CHAINE_INUTILISABLE`, en permanence et non en transitoire.

    **Ce que ce test empeche, et il l'a deja attrape** : le premier jet de
    `MQ-6` posait `ETAT_CHAINE_REQUISE` sur *tout* refus. Sur `---` la phrase
    generique **masquait** la phrase juste et, pire, mentait -- un nom EST
    saisi, il est seulement inutilisable. La non-regression du 2026-09-06 l'a
    rendu par le rouge de
    `test_atelier_pdf_parcours.py::test_C2_2_un_libelle_INNOMMABLE_ne_fait_PAS_tomber_la_TUI`.

    Les trois libelles sont **distinguables** et non un remplissage uniforme :
    trois familles de caracteres non alphanumeriques, dont une de longueur 2.
    """
    appels: list[object] = []
    ecran = ecran_de_mire(chaine, sur_continuer=appels.append)

    assert ecran.traiter("enter") is True

    assert appels == []
    etat = ecran.etat()
    assert atelier_pdf_calibration.ETAT_CHAINE_INUTILISABLE in etat, etat
    assert atelier_pdf_calibration.ETAT_CHAINE_REQUISE not in etat, etat


def test_MQ6_les_DEUX_phrases_de_refus_sont_DISTINCTES():
    """Deux regimes qui rendraient la meme phrase ne se distingueraient plus.

    Frontiere de redaction : si un jour les deux constantes convergeaient, le
    test ci-dessus deviendrait tautologique -- il verifierait qu'une phrase
    est absente d'elle-meme.
    """
    assert (atelier_pdf_calibration.ETAT_CHAINE_REQUISE
            != atelier_pdf_calibration.ETAT_CHAINE_INUTILISABLE)
    assert (atelier_pdf_calibration.ETAT_CHAINE_REQUISE
            not in atelier_pdf_calibration.ETAT_CHAINE_INUTILISABLE)
    assert (atelier_pdf_calibration.ETAT_CHAINE_INUTILISABLE
            not in atelier_pdf_calibration.ETAT_CHAINE_REQUISE)


def test_MQ6_le_message_de_refus_S_EFFACE_a_la_frappe_suivante():
    """Un message d'etat est un evenement, pas un decor.

    Sans effacement, la phrase de refus survivrait a la saisie qui la corrige
    et l'ecran continuerait de refuser a l'ecrit ce qu'il accepte au clavier.
    """
    ecran = ecran_de_mire()
    ecran.traiter("enter")
    assert ecran.etat() == atelier_pdf_calibration.ETAT_CHAINE_REQUISE

    ecran.traiter("h", "h")

    assert ecran.etat() != atelier_pdf_calibration.ETAT_CHAINE_REQUISE


def test_MQ6_continuer_avec_une_chaine_NOMMABLE_appelle_le_rappel():
    """Volet symetrique : la mesure ne doit pas fermer le chemin nominal."""
    appels: list[object] = []
    ecran = ecran_de_mire("hp-envy-4520", sur_continuer=appels.append)

    assert ecran.traiter("enter") is True

    assert len(appels) == 1
    assert ecran.etat() != atelier_pdf_calibration.ETAT_CHAINE_REQUISE


def test_MQ6_la_phrase_du_refus_ne_porte_ni_touche_ni_chiffre_invente():
    """`EPIC11-ARB-56` : aucune touche, aucun conseil d'usage."""
    phrase = atelier_pdf_calibration.ETAT_CHAINE_REQUISE
    assert "⏎" not in phrase and "F1" not in phrase and "Tab" not in phrase
    assert jetons.colonnes(jetons.replier_ascii(phrase)) <= \
        jetons.largeur_utile()


# ===========================================================================
# `MQ-7` -- le refus annonce `Échap`, la seule issue qui ramene au travail
# ===========================================================================

def sites_de_montage_du_refus() -> list[tuple[str, int]]:
    """Les sites qui construisent `EcranRefus`, releves a l'**AST**.

    A l'AST et non au grep : une prose qui nomme la classe -- ce docstring en
    est un -- ferait mordre un grep et affaiblirait la mesure. C'est le meme
    geste que `outils_frontiere`.
    """
    sites: list[tuple[str, int]] = []
    for chemin in sorted(PAQUET_TUI.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"),
                          filename=str(chemin))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "EcranRefus"):
                sites.append((chemin.name, noeud.lineno))
    return sites


def test_MQ7_le_recensement_des_sites_est_NON_VIDE_et_en_compte_NEUF():
    """Volet symetrique : un recensement vide rendrait la mesure suivante muette.

    Le cardinal est epingle parce qu'il est le contenu de l'avertissement de
    l'audit : « ce littéral est partage par les sites de montage ». Un site de
    plus fait rougir ce test, ce qui est le comportement voulu -- il ramene un
    lecteur ici plutot que de laisser la mesure se perimer.

    **Et c'est exactement ce qui s'est passe le 2026-09-06** : le cardinal est
    passe de HUIT a NEUF. Le neuvieme site est
    `projet_inventaire.refus_de_l_inventaire`, pose en reconciliant les deux
    ouvreurs du palier Projet -- les quatre refus d'`inventorier_le_projet`
    (`ProjetIntrouvable`, `ManifesteIntrouvable`, `ManifesteIllisible`,
    `ManifesteIncoherent`) y montent `EcranRefus` avec le message du coeur
    verbatim, plutot qu'un `EcranPasEncore` : un manifeste qui ne se lit pas
    n'annonce rien a venir. La garde a donc rougi **dans le sens voulu**, et
    la mise a jour de ce cardinal est sa reponse, pas son contournement --
    l'autre volet (`…partagent_la_MEME_ligne_de_raccourcis`) est reste vert,
    donc le neuvieme site herite bien de la ligne d'annonce commune.

    **Et une DIXIEME fois le meme jour, pour le meme motif.**
    `projet_suppression.refus_de_la_suppression` (`EPIC11-ARB-260`) prend la
    place des deux `EcranPasEncore` qui habillaient un `ProjectMaintenanceError`
    -- le mur qu'Egan a rencontre en supprimant un rush qui porte encore un
    lot : un refus motive, legitime et definitif s'affichait sous « Cet ecran
    n'existe pas encore », avec une echeance qui n'arrivera jamais. **UN seul
    site pour DEUX chemins**, et c'est delibere : `ouvrir_la_suppression` et
    `reessayer_la_suppression` passent tous deux par cette fonction, si bien
    que le cardinal ne monte que d'une unite et que la mise en forme du refus
    n'a qu'une seule redaction.

    **Le cardinal est a ONZE et non a dix**, et le onzieme n'est pas de ce lot :
    `palier_profil_defaut.py` a gagne son propre site le meme soir, sur une
    autre branche de travail. Le nombre est donc **contendu** tant que les lots
    du 2026-09-06 ne sont pas fusionnes -- deux lots qui montent chacun un site
    verront chacun ce test rougir chez l'autre, et c'est la fusion qui
    reconcilie, pas l'un des deux. Le releve est fait a l'AST, donc il dit la
    verite de l'arbre qu'il lit ; ce qu'il ne peut pas dire, c'est de quel lot
    vient chaque site.
    """
    sites = sites_de_montage_du_refus()
    assert len(sites) == 11, sites
    assert len({nom for nom, _ in sites}) >= 5, sites


def mots_cles_des_montages_du_refus() -> set[str]:
    """Les mots-cles que les sites passent a `EcranRefus`, tous sites confondus."""
    mots: set[str] = set()
    for chemin in sorted(PAQUET_TUI.rglob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"),
                          filename=str(chemin))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "EcranRefus"):
                mots.update(cle.arg for cle in noeud.keywords if cle.arg)
    return mots


def test_MQ7_les_neuf_sites_partagent_la_MEME_ligne_de_raccourcis():
    """Aucun site ne redefinit l'annonce : elle est donc vraie partout ou
    fausse partout, et c'est ce qui fait qu'**une** ligne la corrige.

    Deux formes de redefinition sont mesurees, parce qu'elles sont deux :
    l'affectation sur la classe et le mot-cle passe au montage. Le volet
    NON VIDE est porte par les mots-cles reellement employes -- un ensemble
    vide dirait que la mesure ne voit plus rien.
    """
    mots = mots_cles_des_montages_du_refus()
    assert {"conserve", "non_ecrit"} <= mots, sorted(mots)
    assert "raccourcis" not in mots, sorted(mots)

    affectations = [chemin.name for chemin in PAQUET_TUI.rglob("*.py")
                    if "EcranRefus.raccourcis =" in
                    chemin.read_text(encoding="utf-8")]
    assert affectations == [], affectations


def test_MQ7_la_ligne_du_refus_annonce_les_TROIS_touches_qui_marchent():
    """`EPIC11-ARB-89` : « toujours proposer […] jamais un blocage sec ».

    Les deux issues annoncees etaient `⏎` -- qui depile jusqu'aux ateliers,
    donc jette le lot choisi et les reglages retenus -- et `Q`, qui quitte.
    Les deux sont des abandons. `Échap` ramene au travail, reglages intacts,
    et n'etait pas annonce : un refus dont les seules portes visibles perdent
    le travail est un blocage sec habille.
    """
    ligne = execution.EcranRefus.raccourcis
    assert "⏎" in ligne and "Échap" in ligne and "Q quitter" in ligne


def test_MQ7_la_ligne_du_refus_tient_la_grille_en_UTF8_ET_en_ASCII():
    ligne = execution.EcranRefus.raccourcis
    utile = jetons.largeur_utile()
    assert jetons.colonnes(ligne) <= utile, jetons.colonnes(ligne)
    assert jetons.colonnes(jetons.replier_ascii(ligne)) <= utile


def test_MQ7_ECHAP_depile_le_refus_et_rend_le_palier_du_dessous(banc):
    """La touche annoncee **agit**, mesuree sur l'application montee.

    Une annonce se paie en mesure : c'est exactement le defaut symetrique de
    `MQ-1` -- « une touche non annoncee qui agit est aussi trompeuse qu'une
    touche annoncee qui n'agit pas ».
    """
    refus = execution.EcranRefus("DOSSIER_DE_LOT_VIDE", "le lot ne porte rien")

    async def scenario(pilote):
        # **Le refus se monte sur un PALIER, jamais sur la racine.** `rang`
        # compte les paliers non transitoires et `action_remonter` ne depile
        # qu'au-dessus de zero : monte sur la racine, le refus serait
        # insortable par `Échap` -- ce que les neuf sites du produit ne font
        # pas, tous etant a l'interieur d'un atelier.
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre(refus)
        await pilote.pause()
        avant = len(pilote.app.screen_stack)
        await pilote.press("escape")
        await pilote.pause()
        return avant, len(pilote.app.screen_stack), pilote.app.screen

    avant, apres, ecran = banc(coque(), scenario)
    assert apres == avant - 1, (avant, apres)
    assert not isinstance(ecran, execution.EcranRefus), type(ecran)


def test_MQ7_ECHAP_ne_depile_PAS_pendant_une_tache_et_c_est_la_LIMITE(banc):
    """La limite de l'annonce, mesuree plutot que tue.

    `action_remonter` arme l'interruption au lieu de depiler quand une tache
    tourne. Aucun des neuf sites ne monte le refus dans ce regime -- les deux
    du Scan appellent `oublier_la_tache()` juste avant --, mais un neuvieme
    site qui l'oublierait ferait mentir la ligne, et c'est ce test qui dit ou
    regarder.
    """
    refus = execution.EcranRefus("DOSSIER_DE_LOT_VIDE", "le lot ne porte rien")

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.tache_en_cours = True
        pilote.app.descendre(refus)
        await pilote.pause()
        avant = len(pilote.app.screen_stack)
        await pilote.press("escape")
        await pilote.pause()
        return avant, len(pilote.app.screen_stack), pilote.app.interruption_demandee

    avant, apres, armee = banc(coque(), scenario)
    assert apres == avant
    assert armee is True
