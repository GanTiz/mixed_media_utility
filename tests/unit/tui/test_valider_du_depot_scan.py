# -*- coding: utf-8 -*-
"""La ligne `Valider` de `E3-1`, retour terrain d'Egan du 2026-09-06.

**Le verbatim, parce que c'est lui qui fait foi** : « sur l'ecran de parametrage
[scan] une fois le chemin specifie il manque un bouton valider. Le seul moyen de
valider est de faire Enter sur le DPI, pas intuitif. »

C'est le **meme grief** qu'`EPIC11-ARB-158` a tranche le 2026-09-01 sur `E3-9`,
l'ecran voisin du meme atelier (« la validation avec Entree n'est pas claire. Il
faut qu'il y ait un choix explicite en bas du formulaire : Valider »). La forme
en est donc **declinee**, pas inventee -- et les deux ecarts qu'il a fallu
trancher seuls sont mesures ici plutot que declares :

* **`Tab` et non les fleches.** `EPIC11-ARB-158` dit « on y accede en descendant
  avec les fleches ». Sur `E3-9` c'est possible ; sur `E3-1`, `↑↓` fait defiler
  la liste des sources, et la lui reprendre couperait l'operateur de la seule
  facon de lire une designation de trente planches.
  :func:`test_les_FLECHES_restent_le_defilement_de_la_liste_des_sources` mesure
  que rien n'a ete vole, et
  :func:`test_Tab_atteint_Valider_depuis_CHAQUE_ligne_du_parcours` que la touche
  annoncee au pied y mene vraiment -- « une ligne d'action inatteignable par la
  touche annoncee serait pire que pas de ligne du tout » ;
* **pas de seconde colonne.** `E3-9` porte `lancer la calibration` a cote de son
  `Valider` ; Egan a fait **retirer** la sienne d'`E5-2` le 2026-09-02. On suit
  la plus recente des deux formes, et
  :func:`test_la_ligne_Valider_n_a_PAS_de_seconde_colonne` le tient.

**La regle des drapeaux** (`CLAUDE.md`, 2026-09-06 : « une garde qui ne fait
varier AUCUN de ses drapeaux ne mesure qu'un seul chemin ») gouverne le
decoupage de ce fichier. Les quatre drapeaux de cette ligne, tous varies dans
les deux sens :

    source designee / absente        la ligne doit etre inaccessible ET le dire
    resolution saine / vide / refusee  trois motifs de refus, pas un seul
    ligne de reprise presente / non    le parcours change de cardinal
    `ascii_seul` vrai / faux           le depot a paye 11 bandeaux ampute
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import scan_ingest                       # noqa: E402
from mixed_media_utility.tui import atelier_scan, jetons          # noqa: E402
from mixed_media_utility.tui.coque import (                       # noqa: E402
    Contexte,
    CoqueTui,
    PalierTemoin,
)

#: Les deux regimes de rendu, joues partout ou le dessin compte.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le pied du palier temoin. `E3-1` et `E3-1b` le dessinent tous les deux,
#: et ce banc le LIT desormais a sa source -- voir la fin du fichier.
PIED_DU_PALIER = "Q quitter"

#: Le plancher de `EPIC11-ARB-21`, ecrit en clair : le relire de `jetons`
#: rendrait la mesure de hauteur tautologique.
LARGEUR_DU_PLANCHER = 80
HAUTEUR_DU_PLANCHER = 24
LIGNES_DE_CENTRE = 17

DPI_SAIN = 600


# ---------------------------------------------------------------------------
# Fabriques -- collections a DEUX elements distinguables au moins
# ---------------------------------------------------------------------------

def _page(chemin: Path, *, dpi: int | None, teinte: int) -> Path:
    """Une page PNG qui **declare** son dpi, ou qui n'en declare aucun.

    La teinte differe d'une page a l'autre : deux pages identiques rendraient
    toute permutation invisible (regle des fabriques, point 1).
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((40, 60, 3), teinte, dtype=np.uint8))
    if dpi is not None:
        Image.open(chemin).save(chemin, dpi=(dpi, dpi))
    return chemin


def _dossier_mesure(racine: Path, pages: int = 3) -> Path:
    """Un dossier de pages **qui declarent toutes leur dpi**.

    C'est ce qui fait exister la ligne de reprise -- donc le regime a quatre
    lignes de parcours.
    """
    for rang in range(pages):
        _page(racine / f"page_{rang + 1:02d}.png", dpi=DPI_SAIN,
              teinte=10 + 40 * rang)
    return racine


def _dossier_sans_mesure(racine: Path, pages: int = 2) -> Path:
    """Son symetrique : aucune page ne declare de dpi, donc pas de reprise."""
    for rang in range(pages):
        _page(racine / f"page_{rang + 1:02d}.png", dpi=None,
              teinte=20 + 60 * rang)
    return racine


def _huit_sources(racine: Path) -> list[Path]:
    """Huit fichiers **distinguables** -- assez pour que la liste DEBORDE."""
    return [_page(racine / f"planche_{rang:02d}.png", dpi=None,
                  teinte=5 + 20 * rang) for rang in range(8)]


def _avec_mesure(source: atelier_scan.SourceDesignee, dpi: float = 600.0):
    """La meme designation, mais qui **a livre** une mesure.

    Utile sur une designation multiple, ou la mesure du coeur ne remonte pas
    toujours : c'est le seul moyen d'atteindre le regime le plus HAUT de cet
    ecran -- liste qui deborde **et** ligne de reprise --, celui ou le plancher
    de dix-sept lignes se joue.
    """
    return dataclasses.replace(
        source, mesure=dataclasses.replace(source.mesure, dpi=dpi))


def _app(ecran, ascii_seul: bool = False) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", PIED_DU_PALIER), ecran],
                    contexte=Contexte(projet="projet_demo"),
                    ascii_seul=ascii_seul)


def _rendu(ecran) -> list[str]:
    """Les lignes **telles qu'elles s'affichent** : repli ASCII applique, et
    balisage de couleur retire.

    `lignes()` rend le texte AVANT `jetons.ajuster` : le lire en mode `--ascii`
    mesurerait un rendu UTF-8 qui n'atteint jamais l'ecran. Le piege est exact-
    ement celui que le depot a paye sur onze bandeaux le 2026-09-06.
    """
    return jetons.texte_affiche(str(ecran._corps.content)).splitlines()


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _jusqu_a_valider(ecran) -> int:
    """Amener le curseur sur `Valider` **par la touche annoncee**, et compter.

    `Tab` et non une affectation directe : le grief d'Egan porte autant sur
    l'ACCES a la ligne que sur son existence, et un banc qui poserait
    `formulaire.champ` sauterait exactement ce qu'il a signale. La boucle est
    bornee par le cardinal du parcours -- un `Tab` inerte ferait sinon une
    boucle infinie plutot qu'un rouge.
    """
    for coups in range(len(ecran.formulaire.champs()) + 1):
        if ecran.formulaire.champ == atelier_scan.CHAMP_VALIDER:
            return coups
        ecran.traiter("tab")
    raise AssertionError(
        f"`Tab` n'atteint pas la ligne d'action : {ecran.formulaire.champs()}")


# ===========================================================================
# La ligne existe, elle est au BAS, et dans les DEUX modes de rendu
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_Valider_FERME_l_ecran_dans_les_DEUX_modes(tmp_path, banc,
                                                            ascii_seul):
    """AC du retour : « il manque un bouton valider », et il est **en bas**.

    Les deux modes comptent : le depot a paye une regression ou onze des
    quatorze ecrans amputaient leur bandeau en `--ascii` parce qu'aucun banc ne
    jouait le mode. Ici la mesure porte sur le rang de la ligne, qu'un repli
    pourrait faire disparaitre du rendu sans rien signaler.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))

    async def scenario(_pilote):
        ecran.rafraichir()
        return _rendu(ecran)

    lignes = _monte(_app(ecran, ascii_seul), scenario, banc)
    portant = [rang for rang, ligne in enumerate(lignes)
               if atelier_scan.LIBELLE_VALIDER in ligne]
    assert portant == [len(lignes) - 1], (portant, lignes)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_Valider_n_a_PAS_de_seconde_colonne(tmp_path, banc,
                                                     ascii_seul):
    """**Arbitrage (b), mesure** : la forme est celle d'`E5-2`, pas d'`E3-9`.

    `E3-9` porte `ACTION_VALIDER = "lancer la calibration"` dans la colonne des
    valeurs ; Egan a fait retirer la sienne d'`E5-2` le 2026-09-02 (« enlever la
    deuxieme colonne "compose les planches..." a cote de valider »). La ligne ne
    porte donc que le mot et, a droite, la mention de refus -- la meme colonne
    que `requis` et `requis · dpi` sur les lignes voisines.

    La frontiere est **negative et bornee** : on mesure que la ligne, une fois
    ses deux parts connues retirees, ne contient plus rien. Une troisieme part
    quelconque -- un verbe, un chemin, un cardinal -- la ferait rougir.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))

    async def scenario(_pilote):
        ecran.rafraichir()
        return (_rendu(ecran)[-1],
                ecran.mention_du_champ(atelier_scan.CHAMP_VALIDER))

    ligne, mention = _monte(_app(ecran, ascii_seul), scenario, banc)
    attendu = (jetons.replier_ascii(atelier_scan.LIBELLE_VALIDER) if ascii_seul
               else atelier_scan.LIBELLE_VALIDER)
    attendue_mention = (jetons.replier_ascii(mention) if ascii_seul
                        else mention)
    assert attendu in ligne and attendue_mention in ligne, (ligne, mention)
    reste = ligne.replace(attendu, "").replace(attendue_mention, "")
    assert reste.strip() == "", (reste, ligne)
    # Anti-vacuite : la mention n'est pas vide dans cet etat, sinon le retrait
    # ci-dessus ne prouverait rien de la colonne de droite.
    assert mention == atelier_scan.MENTION_VALIDER_SANS_DPI, mention


@pytest.mark.parametrize("avec_reprise", [True, False],
                         ids=["avec-reprise", "sans-reprise"])
def test_Valider_est_dans_le_parcours_QUELS_QUE_SOIENT_les_autres_champs(
        tmp_path, avec_reprise):
    """Le drapeau « ligne de reprise », varie dans les deux sens.

    La reprise entre et sort du parcours selon qu'une mesure existe ; `Valider`,
    lui, y est **toujours**. Une ligne d'action qui n'existerait que lorsque
    l'action est possible serait absente exactement au moment ou l'operateur
    cherche pourquoi il ne peut pas partir.
    """
    dossier = (_dossier_mesure(tmp_path / "avec") if avec_reprise
               else _dossier_sans_mesure(tmp_path / "sans"))
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.poser_la_source(atelier_scan.designer(dossier))
    champs = formulaire.champs()
    assert champs[-1] == atelier_scan.CHAMP_VALIDER, champs
    assert (atelier_scan.CHAMP_REPRISE in champs) is avec_reprise, champs
    # Et sur un formulaire NU, avant toute designation : la ligne est deja la.
    assert atelier_scan.FormulaireDuDepot().champs()[-1] == \
        atelier_scan.CHAMP_VALIDER


# ===========================================================================
# Arbitrage (a) -- `Tab` y mene, et les fleches ne sont PAS volees
# ===========================================================================

@pytest.mark.parametrize("depart", [atelier_scan.CHAMP_SOURCE,
                                    atelier_scan.CHAMP_DPI,
                                    atelier_scan.CHAMP_REPRISE])
def test_Tab_atteint_Valider_depuis_CHAQUE_ligne_du_parcours(tmp_path, banc,
                                                             depart):
    """**Arbitrage (a), mesure sur le vrai chemin clavier.**

    Depuis chaque ligne, `Tab` mene a l'action en au plus un tour -- y compris
    depuis la **derniere** ligne avant elle, qui est le bord qu'une boucle
    tronquee raterait (regle des fabriques, point 4).
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))

    async def scenario(_pilote):
        ecran.formulaire.champ = depart
        coups = _jusqu_a_valider(ecran)
        return coups, ecran.formulaire.champ, ecran.raccourcis

    coups, champ, pied = _monte(_app(ecran), scenario, banc)
    assert champ == atelier_scan.CHAMP_VALIDER
    assert 1 <= coups <= len(ecran.formulaire.champs()), coups
    # Le pied de la ligne atteinte annonce le geste, sinon la touche est muette.
    assert pied == atelier_scan.RACCOURCIS_SUR_VALIDER, pied


def test_les_FLECHES_restent_le_defilement_de_la_liste_des_sources(tmp_path,
                                                                   banc):
    """**Le prix de l'arbitrage (a), mesure plutot que suppose.**

    `EPIC11-ARB-158` dit « on y accede en descendant avec les fleches ». Ici
    non, et il faut prouver que le motif tient : `↑↓` doit **encore** faire
    defiler la liste des sources, sinon on aurait echange un defaut contre un
    autre. La cible est prise sur une liste qui DEBORDE -- sur une liste qui
    tient, `defiler_les_sources` rend faux et la mesure serait vide.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(atelier_scan.designer(
        _huit_sources(tmp_path / "prestataire")))

    async def scenario(_pilote):
        ecran.formulaire.champ = atelier_scan.CHAMP_VALIDER
        avant = ecran.formulaire.premier_visible
        consomme = ecran.traiter("down")
        return avant, consomme, ecran.formulaire.premier_visible, \
            ecran.formulaire.champ

    avant, consomme, apres, champ = _monte(_app(ecran), scenario, banc)
    assert ecran.formulaire.sources_defilent is True
    assert consomme is True
    assert apres == avant + 1, (avant, apres)
    # **Et le curseur du formulaire n'a pas bouge** : c'est la moitie qui dit
    # que les fleches n'ont pas ete detournees vers le parcours.
    assert champ == atelier_scan.CHAMP_VALIDER


# ===========================================================================
# `⏎` ne lance QUE depuis cette ligne
# ===========================================================================

def test_Entree_ne_lance_la_detection_QUE_depuis_la_ligne_Valider(tmp_path,
                                                                  banc):
    """Le coeur du grief : « le seul moyen de valider est de faire Enter sur le
    DPI, pas intuitif ».

    La frontiere est **negative sur trois lignes et positive sur la
    quatrieme** : sans le volet negatif, un `⏎` qui lancerait encore depuis
    n'importe ou passerait le volet positif sans broncher.
    """
    dossier = _dossier_mesure(tmp_path / "lot")
    lances = []
    ecran = atelier_scan.EcranScanDepot(
        detecter=lambda chemin, dpi: lances.append((chemin, dpi)))
    ecran.formulaire.poser_la_source(atelier_scan.designer(dossier))
    ecran.formulaire.dpi = str(DPI_SAIN)

    async def scenario(pilote):
        muettes = {}
        for champ in (atelier_scan.CHAMP_DPI, atelier_scan.CHAMP_REPRISE):
            ecran.formulaire.champ = champ
            ecran.traiter("enter")
            await pilote.pause()
            muettes[champ] = list(lances)
        ecran.formulaire.champ = atelier_scan.CHAMP_VALIDER
        ecran.traiter("enter")
        await pilote.pause()
        return muettes, list(lances)

    muettes, apres = _monte(_app(ecran), scenario, banc)
    assert muettes == {atelier_scan.CHAMP_DPI: [],
                       atelier_scan.CHAMP_REPRISE: []}, muettes
    assert apres == [(dossier, DPI_SAIN)], apres


def test_Entree_sur_un_champ_de_saisie_DESCEND_au_lieu_de_ne_rien_faire():
    """« Une touche annoncee qui ne fait rien et ne dit rien est indistinguable
    d'un clavier casse. »

    `⏎` ne lance plus depuis le dpi -- il ne doit pas pour autant y etre
    inerte : il y **descend**, ce qui est la convention de tout formulaire.
    Mesure sans terminal, sur le modele pur.
    """
    formulaire = atelier_scan.FormulaireDuDepot()
    formulaire.champ = atelier_scan.CHAMP_DPI
    suivant = formulaire.champs()[
        formulaire.champs().index(atelier_scan.CHAMP_DPI) + 1]
    assert formulaire.avancer() is True
    assert formulaire.champ == suivant


# ===========================================================================
# Elle DIT ce qui manque -- les trois regimes, une seule redaction
# ===========================================================================

#: Les **trois** regimes de refus, avec la mention et la phrase attendues.
#: Trois et non un : `peut_detecter` est faux pour trois raisons, et une ligne
#: qui n'en nommerait qu'une enverrait l'operateur corriger un champ qui va
#: bien -- c'est le defaut qu'`E3-9` a paye deux fois.
REFUS = {
    "sans source": (
        lambda f: None,
        atelier_scan.MENTION_VALIDER_SANS_SOURCE,
        atelier_scan.PHRASE_SOURCE_REQUISE),
    "sans resolution": (
        lambda f: None,
        atelier_scan.MENTION_VALIDER_SANS_DPI,
        atelier_scan.PHRASE_DPI_REQUIS),
    "resolution refusee": (
        lambda f: setattr(f, "dpi", str(scan_ingest.MAX_SCAN_DPI + 1)),
        atelier_scan.MENTION_VALIDER_DPI_REFUSE,
        atelier_scan.PHRASE_DPI_REFUSE),
}


@pytest.mark.parametrize("regime", sorted(REFUS))
def test_la_ligne_DIT_le_bon_manque_dans_les_TROIS_regimes(tmp_path, banc,
                                                           regime):
    """Le drapeau « source » et le drapeau « resolution », varies ensemble.

    La mention, l'aide et la ligne d'etat sortent toutes de
    :func:`atelier_scan.motif_du_refus_de_partir` : c'est **une seule
    redaction** pour trois surfaces, et c'est ce que ce banc mesure -- sur
    `E3-9`, les avoir ecrites deux fois a fait corriger la premiere sans la
    seconde, deux fois de suite.
    """
    poser, mention, phrase = REFUS[regime]
    ecran = atelier_scan.EcranScanDepot()
    if regime != "sans source":
        ecran.formulaire.poser_la_source(
            atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))
    poser(ecran.formulaire)

    async def scenario(pilote):
        ecran.formulaire.champ = atelier_scan.CHAMP_VALIDER
        ecran.traiter("enter")
        await pilote.pause()
        return (ecran.mention_du_champ(atelier_scan.CHAMP_VALIDER),
                ecran.valeur_de_l_aide(atelier_scan.CHAMP_VALIDER),
                ecran.etat(),
                ecran.formulaire.peut_detecter)

    rendue, aide, etat, peut = _monte(_app(ecran), scenario, banc)
    assert peut is False, regime
    assert rendue == mention, (regime, rendue)
    assert aide == mention, (regime, aide)
    assert phrase in jetons.texte_affiche(etat), (regime, etat)


def test_les_TROIS_motifs_de_refus_sont_DISTINGUABLES():
    """Anti-vacuite du banc precedent, et il n'est pas decoratif.

    Trois regimes qui rendraient la meme phrase le laisseraient vert tout en
    ne mesurant qu'un chemin : c'est la fabrique mono-element appliquee aux
    motifs. Les mentions ET les phrases sont donc comparees deux a deux.
    """
    mentions = [mention for _p, mention, _phrase in REFUS.values()]
    phrases = [phrase for _p, _mention, phrase in REFUS.values()]
    assert len(set(mentions)) == 3, mentions
    assert len(set(phrases)) == 3, phrases


@pytest.mark.parametrize("ascii_seul", MODES)
def test_quand_la_detection_PEUT_partir_la_ligne_se_TAIT(tmp_path, banc,
                                                         ascii_seul):
    """Volet symetrique des trois refus : sans lui, une mention **toujours**
    affichee serait verte partout ci-dessus.

    Les deux modes : un repli qui ferait reapparaitre un motif serait un
    avertissement fantome sur un formulaire complet.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))
    ecran.formulaire.dpi = str(DPI_SAIN)

    async def scenario(_pilote):
        ecran.rafraichir()
        return (ecran.mention_du_champ(atelier_scan.CHAMP_VALIDER),
                ecran.valeur_de_l_aide(atelier_scan.CHAMP_VALIDER),
                _rendu(ecran)[-1])

    mention, aide, ligne = _monte(_app(ecran, ascii_seul), scenario, banc)
    assert ecran.formulaire.peut_detecter is True
    assert mention == ""
    assert aide == atelier_scan.AIDE_PRET_A_PARTIR
    for _poser, motif, _phrase in REFUS.values():
        replie = jetons.replier_ascii(motif) if ascii_seul else motif
        assert replie not in ligne, (motif, ligne)


# ===========================================================================
# Le pied dit le geste de la LIGNE COURANTE
# ===========================================================================

def test_le_pied_annonce_detecter_SUR_Valider_et_nulle_part_ailleurs(tmp_path,
                                                                     banc):
    """Le pied mentait : il annoncait « ⏎ détecter » des qu'une source etait
    posee, **depuis n'importe quelle ligne** -- y compris depuis `Source`, ou
    `⏎` ouvre l'explorateur.

    La mesure est un ensemble EXACT : les lignes qui annoncent le geste, contre
    la seule qui le fait. Une assertion positive (« Valider l'annonce ») serait
    verte sur l'ancien pied, qui l'annoncait partout.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(
        atelier_scan.designer(_dossier_mesure(tmp_path / "lot")))

    async def scenario(_pilote):
        pieds = {}
        for champ in ecran.formulaire.champs():
            ecran.formulaire.champ = champ
            ecran._appliquer_la_zone()
            pieds[champ] = ecran.raccourcis
        return pieds

    pieds = _monte(_app(ecran), scenario, banc)
    annoncent = {champ for champ, pied in pieds.items() if "détecter" in pied}
    assert annoncent == {atelier_scan.CHAMP_VALIDER}, pieds
    # Et chaque ligne a bien un pied a elle : quatre lignes, quatre redactions.
    assert len(set(pieds.values())) == len(pieds), pieds


@pytest.mark.parametrize("deborde", [True, False],
                         ids=["liste-qui-deborde", "liste-qui-tient"])
def test_le_pied_de_Valider_garde_le_defilement_QUAND_il_existe(tmp_path,
                                                                banc, deborde):
    """Le drapeau « la liste des sources deborde », varie dans les deux sens.

    `↑↓` marche depuis la ligne `Valider` comme depuis les autres : son pied
    doit donc l'annoncer quand la liste deborde, et **se taire sinon** --
    annoncer une touche inerte est indistinguable d'un clavier casse.
    """
    racine = tmp_path / "prestataire"
    sources = _huit_sources(racine)
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(atelier_scan.designer(
        sources if deborde else sources[:2]))

    async def scenario(_pilote):
        ecran.formulaire.champ = atelier_scan.CHAMP_VALIDER
        ecran._appliquer_la_zone()
        return ecran.raccourcis

    pied = _monte(_app(ecran), scenario, banc)
    assert ecran.formulaire.sources_defilent is deborde
    attendu = (atelier_scan.RACCOURCIS_SUR_VALIDER_MULTIPLE if deborde
               else atelier_scan.RACCOURCIS_SUR_VALIDER)
    assert pied == attendu, pied
    assert ("↑↓" in pied) is deborde, pied


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_NEUF_pieds_du_depot_tiennent_la_grille_dans_les_DEUX_modes(
        ascii_seul):
    """Le budget de largeur, sur **toutes** les lignes de pied de cet ecran.

    Le balayage de `manuel.lignes_de_raccourcis_du_paquet` les voit deja parce
    qu'elles sont des constantes `RACCOURCIS_*` de module -- et c'est
    exactement pour cela qu'elles en sont : une ligne composee a la volee
    echapperait aux deux garanties de `test_repli_ascii.py`. Ce banc-ci mesure
    en plus que l'ensemble est **complet** : neuf constantes -- trois pieds par
    defaut et six pieds de ligne. Un cardinal, parce qu'une ligne de pied
    ajoutee sans mesure de largeur est exactement ce qui a coute onze bandeaux
    ampute le 2026-09-06.
    """
    pieds = {nom: valeur for nom, valeur in vars(atelier_scan).items()
             if nom.startswith("RACCOURCIS_DEPOT")
             or nom.startswith("RACCOURCIS_SUR_")}
    assert len(pieds) == 9, sorted(pieds)
    for nom, ligne in sorted(pieds.items()):
        rendue = jetons.replier_ascii(ligne) if ascii_seul else ligne
        if ascii_seul:
            assert rendue.isascii(), (nom, rendue)
        assert jetons.colonnes(rendue) <= jetons.largeur_utile(), (
            nom, jetons.colonnes(rendue))


# ===========================================================================
# Le plancher -- la ligne d'action doit rester DESSINEE au regime le plus haut
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_au_regime_le_plus_HAUT_le_corps_tient_les_dix_sept_lignes(tmp_path,
                                                                   banc,
                                                                   ascii_seul):
    """**La mesure qui a decide la place de la ligne**, et elle n'est pas
    theorique.

    Au regime le plus haut de cet ecran -- huit sources qui debordent, la
    fenetre au milieu (donc `…` en tete ET en queue) et la ligne de reprise --
    le corps fait exactement dix-sept lignes. La ligne vide de respiration
    qu'`E3-9` pose avant son `Valider` en ferait dix-huit, et `textual` ne
    signale rien : la ligne d'action serait dessinee hors du cadre, donc
    indistinguable d'un ecran qui n'en a pas.

    La borne est ecrite en clair ici : la relire de `jetons` rendrait la mesure
    tautologique.
    """
    ecran = atelier_scan.EcranScanDepot()
    ecran.formulaire.poser_la_source(_avec_mesure(atelier_scan.designer(
        _huit_sources(tmp_path / "prestataire"))))
    ecran.formulaire.premier_visible = 2

    async def scenario(_pilote):
        ecran.rafraichir()
        return _rendu(ecran)

    app = _app(ecran, ascii_seul)
    lignes = _monte(app, scenario, banc)
    # Anti-vacuite : on est bien au regime le plus haut, les deux `…` compris.
    assert atelier_scan.CHAMP_REPRISE in ecran.formulaire.champs()
    assert ecran.formulaire.sources_defilent is True
    assert len(lignes) == LIGNES_DE_CENTRE, (len(lignes), lignes)
    assert atelier_scan.LIBELLE_VALIDER in lignes[-1], lignes[-1]


def test_le_plancher_ecrit_ici_est_CELUI_du_produit():
    """Le seul point de contact entre la borne ecrite en clair et le produit.

    Une egalite entre deux nombres ecrits separement : sans elle, deplacer le
    plancher dans `jetons` deplacerait l'attente du meme mouvement et le banc
    resterait vert en laissant passer un ecran soudain trop haut.
    """
    assert jetons.largeur_utile(LARGEUR_DU_PLANCHER) == 76
    assert HAUTEUR_DU_PLANCHER - LIGNES_DE_CENTRE == 7


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# Frontiere `test_frontiere_des_maquettes_recopiees.py` : un banc qui asserte
# un litteral dessine le confronte a sa SOURCE. Le pied du palier temoin etait
# recopie a la main -- un double dont le pied n'est pas celui du dessin mesure
# un ecran que personne n'a approuve.

#: Le dossier des dessins approuves.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c\u2501\u2503\u258f\u2595"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_PIED_du_palier_temoin_de_ce_banc_est_DESSINE():
    """`Q quitter` se lit sur les DEUX dessins du depot, il n'est pas invente ici."""
    # Les deux ecrans du depot ont des pieds DIFFERENTS -- `E3-1` offre
    # `↑↓ sources`, `E3-1b` non, parce qu'il n'a qu'un fichier -- et ils
    # finissent tous deux par ce pied. Mesurer les deux plutot qu'un seul est
    # ce qui distingue une fin de pied commune d'une coincidence.
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    unique = dessin_de_la_maquette("E3-1b-scan-depot-fichier-unique.txt")
    assert PIED_DU_PALIER in depot
    assert PIED_DU_PALIER in unique
    assert "↑↓ sources" in depot
    assert "↑↓ sources" not in unique


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe.

    Le volet symetrique de la confrontation ci-dessus. Un `in` sur un dessin
    de plusieurs centaines de caracteres est vrai bien trop souvent pour se
    passer de son contre-exemple.
    """
    dessin = dessin_de_la_maquette("E3-1-scan-depot.txt")
    assert "Q quitter et revenir" not in dessin
    assert "Q fermer" not in dessin
