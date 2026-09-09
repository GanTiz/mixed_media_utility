# -*- coding: utf-8 -*-
"""`MQ-4` et `MQ-5` : les deux suites qui menaient au filet alors que leur
atelier etait livre -- et `MQ-8` (partie 1), les deux commandes du palier
Projet qui n'annoncaient aucune echeance.

**Le mode de panne est commun aux deux premieres**, et c'est ce qui justifie un
banc unique : un filet `EcranPasEncore` pose quand l'atelier cible n'existait
pas, **laisse en place quand il a ete livre**, et justifie par un docstring que
personne n'a rouvert. Aucun banc ne rougissait, parce que le filet
*fonctionne* : il nomme une absence, exactement comme prevu. Ce qui a change,
c'est que l'absence n'en est plus une -- l'atelier Pdf est livre (story 11.7),
l'atelier Exports aussi (story 11.8), et les deux sont cables dans
`ChaineReelle`.

Le recensement mecanique de ce defaut vit dans
`test_couverture_des_suites.py` : il compte, pour chaque `SUITE_*` declaree,
qu'elle porte une branche **nommee** dans son rappel. Ce banc-ci mesure l'autre
moitie, celle qu'aucun arbre syntaxique ne voit : **ou** la branche mene, au
clavier, sur l'application du produit.

**Regle des fabriques (`CLAUDE.md`, les QUATRE points).** Les projets de ces
bancs portent **trois** lots aux identifiants et aux cardinaux **distincts** ;
la cible d'un choix n'est jamais en premiere position ; et les deux **bords**
sont exerces la ou l'ordre d'une liste est ce qu'on mesure -- un balayage
tronque saute une extremite, pas le milieu.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))
_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest  # noqa: E402

from mixed_media_utility.io.project_layout import (  # noqa: E402
    extract_frames_dir,
)
from mixed_media_utility.tui import (  # noqa: E402
    atelier_extraction_ecriture as extraction,
)
from mixed_media_utility.tui import atelier_scan_ecriture as scan_ecriture  # noqa: E402
from mixed_media_utility.tui import atelier_scan_resultat as scan_resultat  # noqa: E402
from mixed_media_utility.tui.atelier_exports_lot import (  # noqa: E402
    EcranDesLotsAEncoder,
)
from mixed_media_utility.tui.atelier_pdf import EcranPdfMenu  # noqa: E402
from mixed_media_utility.tui.atelier_pdf_lots import (  # noqa: E402
    EcranLotsAPlanches,
)
from mixed_media_utility.tui.coque import EcranPasEncore  # noqa: E402
from mixed_media_utility.tui.palier_projet import entrees_du_palier  # noqa: E402

import test_atelier_exports_parcours as fabriques_exports  # noqa: E402
import test_atelier_scan_resultat as fabriques_scan  # noqa: E402
import test_suites_du_resultat as fabriques_extraction  # noqa: E402


@pytest.fixture
def sonde(monkeypatch):
    """Le probe du coeur, remplace la ou les trois consommateurs le lisent.

    Reprise litterale de `test_suites_du_resultat.sonde` : la fabrique
    `chaine()` importee de ce module en depend, et une fixture ne traverse pas
    un import.
    """
    from mixed_media_utility import video_metadata

    monkeypatch.setattr(
        video_metadata, "probe_media",
        lambda chemin, **kwargs: fabriques_extraction.probe_de_la_source())


def _coque_du_scan(pilote) -> None:
    """Descendre jusqu'a la QUATRIEME station : le Scan en empile quatre.

    La coque monte son premier palier toute seule ; les suivants se descendent
    au clavier, comme le produit le fait.
    """
    for _ in range(3):
        pilote.app.descendre()


# ===========================================================================
# `MQ-4` -- « Composer les planches de ces lots » ouvre l'atelier Pdf
# ===========================================================================

def chaine_qui_declare(tmp_path):
    """La chaine REELLE du produit, dont le double d'extraction DECLARE au manifeste.

    **Pourquoi ce supplement a `test_suites_du_resultat.chaine`.** Le double
    d'extraction de ce module-la ecrit de vrais dossiers de lot mais n'inscrit
    rien au manifeste, la ou le vrai `run_extraction` appelle
    `io.extraction_manifest.persist_extraction` juste apres l'ecriture des
    TIFF. L'atelier Pdf, lui, **relit le manifeste** : sans declaration, il
    n'ouvrirait pas sa liste mais son refus « aucun lot », et le banc
    mesurerait la fabrique au lieu du produit.

    Les deux lots declares sont **distinguables** -- identifiants et cardinaux
    differents, tires des deux cadences cochees --, jamais un remplissage
    uniforme : une liste qui n'en montrerait qu'un, ou qui recopierait le meme
    chiffre, se verrait.
    """
    dossier, _video = fabriques_extraction.projet(tmp_path)
    manifeste = dossier / "project.json"
    reel = fabriques_extraction.extracteur(dossier)

    def double(**kwargs):
        issue = reel(**kwargs)
        document = json.loads(manifeste.read_text(encoding="utf-8"))
        document.setdefault("lots", []).append({
            "lot_id": issue.lot_id,
            "rush_id": fabriques_extraction.RUSH_VISE,
            "frame_count": issue.written_frame_count,
        })
        manifeste.write_text(json.dumps(document), encoding="utf-8")
        return issue

    def rappel(app, dossier_du_menu, rush_id):
        return extraction.ouvrir_les_cadences(
            app, dossier_du_menu, rush_id, extraire=double,
            logger=fabriques_extraction.JournalMuet(),
            verifier_l_affichage=lambda: None)

    lien = extraction.ChaineReelle(ouvrir_les_cadences=rappel)
    lien.menu.dossier = lien.palier_projet.dossier = dossier
    lien.menu.charger()
    lien.dossier = dossier
    return lien


def test_composer_les_planches_OUVRE_L_ATELIER_PDF_sur_les_lots_ecrits(
        tmp_path, banc, sonde):
    """Le chainage naturel du produit : on extrait pour imprimer.

    **Mesure par le chemin du PRODUIT**, du menu des ateliers a `E2-5` au
    clavier, puis la suite : c'est la lecon de `test_journal_du_produit.py`,
    « le banc mesurait un parcours qui n'est pas celui du produit, sur le seul
    point ou les deux different ».

    Ce que la suite doit rendre, et pas un cran de moins : la **liste des
    lots** de l'atelier Pdf (`E5-1`), pas son menu -- le libelle promet des
    planches « de ces lots », et s'arreter au menu ferait retomber sur un
    ecran a franchir pour rien.
    """
    lien = chaine_qui_declare(tmp_path)

    async def scenario(pilote):
        _rushes, resultat = await fabriques_extraction.jusqu_au_resultat(
            pilote, lien)
        fabriques_extraction.choisir(resultat, extraction.SUITE_PDF)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(lien.app, scenario)
    assert not isinstance(ecran, EcranPasEncore), (
        "« Composer les planches de ces lots » mene encore au filet alors que "
        "l'atelier Pdf est livre et cable dans `ChaineReelle.atelier_pdf`")
    assert isinstance(ecran, EcranLotsAPlanches), type(ecran).__name__
    #: Les DEUX lots que l'extraction vient d'ecrire sont ceux que l'atelier
    #: Pdf propose : la suite ouvre l'atelier **sur ce qui vient d'etre fait**,
    #: pas sur un projet vide.
    proposes = [lot.lot_id for lot in ecran.liste.lots]
    assert len(proposes) == 2, proposes
    assert len(set(proposes)) == 2, f"deux lots indistinguables : {proposes}"


def test_composer_les_planches_DEPILE_l_atelier_extraction_avant_d_ouvrir(
        tmp_path, banc, sonde):
    """Le finding `F3`, un atelier plus loin : sans depilement, ca s'empile.

    Une suite qui ouvre un **autre** atelier sans remonter d'abord laisse sous
    elle tout le parcours d'extraction -- cadences, jugement, execution,
    resultat. `Echap` depuis la liste des lots ramenerait alors sur l'ecran de
    resultat d'une extraction finie au lieu du menu des ateliers.

    On mesure la pile **par ce qu'elle contient**, pas par sa profondeur : un
    cardinal egal peut recouvrir deux piles differentes.
    """
    lien = chaine_qui_declare(tmp_path)

    async def scenario(pilote):
        _rushes, resultat = await fabriques_extraction.jusqu_au_resultat(
            pilote, lien)
        avant = [type(ecran).__name__ for ecran in pilote.app.screen_stack]
        fabriques_extraction.choisir(resultat, extraction.SUITE_PDF)
        await pilote.pause()
        return avant, [type(e).__name__ for e in pilote.app.screen_stack]

    avant, apres = banc(lien.app, scenario)
    assert "EcranResultat" in avant, avant
    assert "EcranRushes" in avant, avant
    #: Plus rien de l'atelier Extraction sous la liste des lots : la suite a
    #: remonte au menu des ateliers avant de descendre dans le Pdf.
    assert "EcranResultat" not in apres, apres
    assert "EcranRushes" not in apres, apres
    assert apres[-1] == "EcranLotsAPlanches", apres
    assert apres[-2] == EcranPdfMenu.__name__, apres


def test_les_TROIS_suites_de_E2_5_menent_a_TROIS_endroits_DISTINCTS(tmp_path):
    """La frontiere de la dispatch, reprise **avec** la destination neuve.

    Une `suivre` qui rendrait toujours la meme chose passerait chacun des
    tests ci-dessus pris a part : chacun n'exerce qu'une suite.
    """
    lot = extract_frames_dir(tmp_path, "rush_01", 25.0)
    lot.mkdir(parents=True)
    rapport = extraction.RapportExtraction(lots_ecrits=(
        extraction.LotEcrit("rush_01_25", 124, 25.0, 10, lot),))

    ou = {}
    for suite in (extraction.SUITE_DOSSIER, extraction.SUITE_PDF,
                  extraction.SUITE_AUTRE_RUSH):
        app = _AppEspionne()
        parcours = extraction.ParcoursExtraction(
            app, tmp_path, "rush_01",
            logger=fabriques_extraction.JournalMuet(),
            composer_les_planches=lambda a, d: a.faits.append(("pdf", d)))
        parcours.rapport = rapport
        parcours._ouvrir_le_dossier = lambda: None
        parcours.suivre(suite)
        ou[suite] = app.faits

    assert ou[extraction.SUITE_PDF] == [("ateliers", None), ("pdf", tmp_path)]
    assert ou[extraction.SUITE_AUTRE_RUSH] == [("depiler", None)]
    assert len({tuple(faits) for faits in ou.values()}) == 3, ou


def test_une_suite_INCONNUE_de_E2_5_nomme_toujours_l_absence(tmp_path):
    """Le filet reste, et c'est lui qui empeche la rechute.

    Le corriger ne consiste pas a le retirer : une suite ajoutee demain et
    oubliee dans `suivre` doit continuer de **dire** qu'elle ne mene nulle
    part.
    """
    app = _AppEspionne()
    parcours = extraction.ParcoursExtraction(
        app, tmp_path, "rush_01", logger=fabriques_extraction.JournalMuet())
    parcours.suivre("Une suite que personne n'a cablee")
    assert app.faits == [("descendre", "Une suite que personne n'a cablee")]


class _AppEspionne:
    """Une application qui NOTE ce qu'on lui demande, sans rien dessiner.

    Elle porte les quatre surfaces que `suivre` touche -- descendre, depiler,
    remonter au menu des ateliers, poser un etat -- et rien d'autre : c'est ce
    qui rend les destinations comparables **par ce qu'elles font**.
    """

    QUAND_ARRIVENT_LES_ATELIERS = "les ateliers de la vague 3"
    ascii_seul = False

    def __init__(self) -> None:
        self.faits: list[tuple] = []
        self.screen_stack = [object(), object()]
        self.passages_empiles = 1
        self.palier_courant = self

    def descendre(self, ecran) -> None:
        self.faits.append(("descendre", getattr(ecran, "ce_qui_manque", None)))

    def pop_screen(self) -> None:
        self.passages_empiles = 0
        self.faits.append(("depiler", None))

    def revenir_aux_ateliers(self) -> None:
        self.faits.append(("ateliers", None))

    def poser_etat(self, texte: str) -> None:
        self.faits.append(("etat", texte))


# ===========================================================================
# `MQ-5` -- « Encoder un master depuis ces lots scannés » ouvre les Exports
# ===========================================================================

def _projet_et_rapport(tmp_path):
    """Un projet **reel** avec ses trois lots encodables, et un rapport de scan.

    Les deux fabriques du depot sont reprises telles quelles, dans cet ordre :
    celle des Exports pose le manifeste et les frames sur le disque (sans quoi
    `check_lot_admission` ecarterait les lots et la liste serait plus courte
    que la fabrique ne le croit), celle du Scan pose le rapport d'ecriture.
    """
    chemin = fabriques_exports.projet(tmp_path)
    rapport = fabriques_scan.rapport_de_trois_lots(tmp_path)
    assert rapport.manifeste == chemin / "project.json", rapport.manifeste
    return chemin, rapport


def test_encoder_un_master_OUVRE_L_ATELIER_EXPORTS_sur_les_lots_scannes(
        tmp_path, banc):
    """Le frere exact de `MQ-4`, dans l'autre atelier.

    L'atelier Exports n'a **pas** de menu (`EPIC11-ARB-28`, verbatim :
    « Extraction et Exports n'en ont pas ») : la suite doit donc rendre `E4-1`,
    la designation du lot, et non un menu qui n'existe pas.
    """
    _chemin, rapport = _projet_et_rapport(tmp_path)
    app = fabriques_scan.coque(paliers=4)

    async def scenario(pilote):
        _coque_du_scan(pilote)
        await pilote.pause()
        scan_resultat.suivre(pilote.app, rapport, scan_resultat.SUITE_EXPORTS)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert not isinstance(ecran, EcranPasEncore), (
        "« Encoder un master depuis ces lots scannés » mene encore au filet "
        "alors que l'atelier Exports est livre et cable dans "
        "`ChaineReelle.atelier_exports`")
    assert isinstance(ecran, EcranDesLotsAEncoder), type(ecran).__name__
    proposes = [lot.lot_id for lot in ecran.liste.lots]
    assert len(proposes) == 3, proposes
    assert len(set(proposes)) == 3, f"trois lots indistinguables : {proposes}"


def test_encoder_un_master_REMONTE_a_l_atelier_avant_de_descendre(tmp_path,
                                                                  banc):
    """Meme geste que cote Extraction, et pour le meme motif (`F3`).

    Le Scan empile **quatre** stations ; les laisser sous `E4-1` ferait
    remonter `Echap` sur le choix de calibration d'une passe deja ecrite.
    """
    _chemin, rapport = _projet_et_rapport(tmp_path)
    app = fabriques_scan.coque(paliers=4)

    async def scenario(pilote):
        _coque_du_scan(pilote)
        await pilote.pause()
        avant = [p.titre for p in pilote.app.screen_stack
                 if hasattr(p, "titre")]
        scan_resultat.suivre(pilote.app, rapport, scan_resultat.SUITE_EXPORTS)
        await pilote.pause()
        return avant, pilote.app.screen_stack

    avant, pile = banc(app, scenario)
    assert len(avant) >= 4, avant
    noms = [type(ecran).__name__ for ecran in pile]
    assert noms[-1] == "EcranDesLotsAEncoder", noms
    #: Les stations de l'atelier Scan ont ete depilees : il ne reste, sous
    #: `E4-1`, que l'ecran projet et le menu des ateliers.
    assert len(pile) == 3, noms


def test_un_rapport_SANS_manifeste_le_DIT_au_lieu_d_ouvrir_n_importe_ou(
        tmp_path, banc):
    """Le volet symetrique, et c'est une **tolerance documentee**.

    `dossier_du_projet` deduit la racine du chemin du manifeste, que le coeur
    pose a chaque passe (`atelier_scan_ecriture.ecrire_les_lots`). Un rapport
    qui n'en porte pas ne peut pas designer de projet : ouvrir l'atelier sur
    le dossier courant du processus serait la panne muette
    qu'`EPIC11-ARB-46` interdit. On retombe donc sur le filet, qui **nomme**.
    """
    rapport = scan_ecriture.RapportDEcriture(
        ecrits=fabriques_scan.rapport_de_trois_lots(tmp_path).ecrits)
    assert scan_resultat.dossier_du_projet(rapport) is None

    async def scenario(pilote):
        scan_resultat.suivre(pilote.app, rapport, scan_resultat.SUITE_EXPORTS)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(fabriques_scan.coque(), scenario)
    assert isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert ecran.ce_qui_manque == scan_resultat.SUITE_EXPORTS


def test_les_TROIS_suites_de_E3_8_menent_a_TROIS_endroits_DISTINCTS(tmp_path,
                                                                    banc,
                                                                    monkeypatch):
    """La dispatch du Scan, fermee comme celle de l'Extraction."""
    monkeypatch.setattr(scan_resultat, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier, **kwargs: f"ouvert {dossier}")
    _chemin, rapport = _projet_et_rapport(tmp_path)

    ou = {}
    for suite in (scan_resultat.SUITE_DOSSIER, scan_resultat.SUITE_EXPORTS,
                  scan_resultat.SUITE_AUTRES_SCANS):
        async def scenario(pilote, suite=suite):
            _coque_du_scan(pilote)
            await pilote.pause()
            scan_resultat.suivre(pilote.app, rapport, suite)
            await pilote.pause()
            return (type(pilote.app.screen).__name__,
                    len(pilote.app.screen_stack))

        ou[suite] = banc(fabriques_scan.coque(paliers=4), scenario)

    assert ou[scan_resultat.SUITE_EXPORTS] == ("EcranDesLotsAEncoder", 3), ou
    assert len(set(ou.values())) == 3, ou


# ===========================================================================
# `MQ-8`, partie 1 -- les deux commandes du palier Projet portent une echeance
# ===========================================================================

@pytest.mark.parametrize("rang", [0, 1])
def test_les_deux_commandes_du_palier_Projet_PORTENT_une_echeance(rang):
    """Sans echeance, « pas encore construit » et « abandonne » se confondent.

    Consigne d'Egan du 2026-08-28, verbatim : « comme ça on sait que c'est
    temporaire et que ce n'est pas un bug ». Le palier Projet n'a que **deux**
    commandes : les deux sortaient sans la ligne, donc un operateur qui entrait
    dans « Projet » n'y trouvait rien qui se distingue d'un abandon.

    Les **deux** rangs sont exerces -- tete et queue d'un choix a deux entrees
    (`CLAUDE.md`, quatrieme point de la regle des fabriques) : une echeance
    posee sur une seule des deux ne passerait pas.
    """
    montes = []
    lien = extraction.ChaineReelle()
    lien.app.descendre = montes.append
    issue = entrees_du_palier().issues[rang]

    lien.entrer_commande(issue)

    assert len(montes) == 1, montes
    ecran = montes[0]
    assert isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert ecran.ce_qui_manque == issue.libelle
    assert ecran.quand, (
        f"« {issue.libelle} » monte l'ecran « pas encore » SANS echeance : "
        f"rien ne la distingue d'une commande abandonnee")
    assert f"Il arrive avec {ecran.quand}." in ecran.lignes()


def test_l_echeance_du_palier_Projet_est_la_MEME_pour_les_deux_commandes():
    """Une seule constante, jamais deux redactions du meme fait.

    Les deux commandes attendent **la meme** chose -- l'ecran de designation
    de fichier que ce palier n'a pas --, et deux phrases divergentes feraient
    croire a deux echeances differentes.
    """
    quands = set()
    for issue in entrees_du_palier().issues:
        montes = []
        lien = extraction.ChaineReelle()
        lien.app.descendre = montes.append
        lien.entrer_commande(issue)
        quands.add(montes[0].quand)
    assert len(quands) == 1, quands
    assert quands == {extraction.ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER}


def test_l_echeance_du_palier_Projet_ne_promet_AUCUNE_date_ni_AUCUNE_vague():
    """**Une echeance vraie, ou pas d'echeance** -- jamais une date inventee.

    Aucune story du depot ne porte ces deux commandes : le recensement du
    2026-09-06 le mesure (`audit-2026-09-06-parcours-complet-les-manques.md`,
    `MQ-8`). Promettre « la vague N » ou une date serait pire que le silence,
    parce que le silence, lui, ne ment pas. Ce que la phrase nomme est ce qui
    manque **reellement** et qui est verifiable a l'oeil : l'ecran de
    designation de fichier.

    Frontiere **negative** : c'est le seul moyen d'attraper la reintroduction
    d'une promesse de calendrier, qu'aucun test positif ne verrait revenir.
    """
    quand = extraction.ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER
    assert "vague" not in quand.lower(), quand
    assert not any(caractere.isdigit() for caractere in quand), quand
    assert quand != extraction.CoqueTui.QUAND_ARRIVENT_LES_ATELIERS, quand
