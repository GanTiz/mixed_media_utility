# -*- coding: utf-8 -*-
"""Story 11.4e, lot J1 -- `calibrer_la_chaine` porte la progression (AC 9.1 a 9.3).

**Ce banc et lui seul mesure J1.** J2 (la surface TUI) a le sien.

Ce que le lot ferme, mesure avant d'etre corrige : `scan_calibrate.calibrer_la_chaine`
n'avait **aucun** parametre `rappel_progression`, et `scan_detection.detect_lot_pages`
non plus -- alors que `detect_pages`, un cran plus bas, le porte depuis la story
11.4b. La calibration etait donc le seul travail long du produit sans canal de
progression, et c'est ce qu'Egan a vu : « Pas de page de progression quand on
lance une calibration. Cela prete a confusion. RIEN n'indique qu'on a lance le
processus. »

**Aucun second mecanisme n'est redige** (`EPIC7-ARB-79`) : le rappel n'est pas
appele, pas teste, pas enveloppe -- il est **passe**, de relais en relais,
jusqu'a l'emetteur qui possede a lui seul la monotonie, l'absence de doublon et
l'absorption des defaillances.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate, scan_detection, scan_ingest
from mixed_media_utility.io import project_layout

DPI = 600


def _page(chemin: Path, valeur: int) -> Path:
    """Une page image **distinguable**, jamais un remplissage uniforme."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(chemin), np.full((80, 60, 3), valeur, dtype=np.uint8))
    return chemin


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    project_layout.ensure_project_layout(dossier)
    return dossier


@pytest.fixture
def lot_de_trois(tmp_path: Path) -> Path:
    """TROIS pages distinguables. Trois, et pas deux.

    Une fabrique a deux elements place sa cible en seconde ET en derniere
    position, ou une faute de terminaison de boucle (`continue` -> `break`) est
    indiscernable d'une faute d'appariement. Le compte des jalons est
    precisement ce qu'une telle faute changerait.
    """
    dossier = tmp_path / "pile"
    for rang, valeur in enumerate((30, 130, 220)):
        _page(dossier / f"page_{rang:02d}.tiff", valeur)
    return dossier


# --- AC 9.1 : le relais existe, et il va jusqu'en bas ----------------------


def test_les_DEUX_relais_portent_le_rappel_jusqu_a_detect_pages(
    projet: Path, lot_de_trois: Path
) -> None:
    """AC 9.1 : `calibrer_la_chaine` -> `detect_lot_pages` -> `detect_pages`.

    Mesure du BOUT de la chaine et non de son premier maillon : on compte les
    jalons reellement recus. Un relais pose sur le premier appel et oublie sur
    le second serait vert sous une assertion de signature, et muet a l'usage.
    """
    jalons = []
    # **Deux arguments, et l'ecrire faux coute cher** : le rappel recoit
    # `(faites, total)`. Un `jalons.append` nu leve un `TypeError` que
    # `EmetteurProgression` ABSORBE par contrat -- le banc rendait alors zero
    # jalon et accusait le relais, qui n'y etait pour rien.
    rapport = scan_ingest.ingest_scan_lot(projet, lot_de_trois, dpi=DPI)
    scan_detection.detect_lot_pages(
        projet, rapport, dpi=DPI,
        rappel_progression=lambda faites, total: jalons.append((faites, total)))

    # Trois pages, trois jalons, et le dernier porte le total.
    assert [faites for faites, _total in jalons] == [1, 2, 3]
    assert {total for _faites, total in jalons} == {3}


def test_calibrer_la_chaine_TRANSMET_le_rappel(
    projet: Path, lot_de_trois: Path, monkeypatch
) -> None:
    """AC 9.1, maillon du haut : `calibrer_la_chaine` passe ce qu'on lui donne.

    La detection est doublee pour que le banc mesure **le passage** et rien
    d'autre : une calibration reelle sur une mire est le sujet d'un autre banc,
    et l'y melanger ferait echouer celui-ci pour des motifs qui ne sont pas les
    siens.
    """
    recus = {}

    def _detection(project_dir, report, *, dpi=None, rappel_progression=None):
        recus["rappel"] = rappel_progression
        raise scan_detection.ScanDetectionError("arret volontaire du banc")

    monkeypatch.setattr(scan_detection, "detect_lot_pages", _detection)
    monkeypatch.setattr(scan_calibrate.scan_detection, "detect_lot_pages",
                        _detection)

    temoin = lambda faites, total: None
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_calibrate.calibrer_la_chaine(
            projet, lot_de_trois, dpi=DPI, rappel_progression=temoin)
    assert recus["rappel"] is temoin


# --- AC 9.2 : `AR3` sur les DEUX regimes -----------------------------------


def test_SANS_rappel_rien_ne_change_a_l_observable(
    projet: Path, lot_de_trois: Path, tmp_path: Path
) -> None:
    """AC 9.2, premier regime : « son absence ne change RIEN a l'observable ».

    Les deux passes sont comparees sur ce que la detection REND, pas sur
    l'absence d'exception : deux passes qui ne levent ni l'une ni l'autre mais
    rendent des verdicts differents seraient un defaut pire, parce que muet.
    """
    second = tmp_path / "projet2"
    project_layout.ensure_project_layout(second)

    r1 = scan_ingest.ingest_scan_lot(projet, lot_de_trois, dpi=DPI)
    sans = scan_detection.detect_lot_pages(projet, r1, dpi=DPI)

    r2 = scan_ingest.ingest_scan_lot(second, lot_de_trois, dpi=DPI)
    avec = scan_detection.detect_lot_pages(
        second, r2, dpi=DPI, rappel_progression=lambda *_: None)

    assert len(sans.pages) == len(avec.pages)
    assert [p.lot_id for p in sans.pages] == [p.lot_id for p in avec.pages]
    assert [p.status for p in sans.pages] == [p.status for p in avec.pages]
    assert [p.qr_status for p in sans.pages] == [p.qr_status for p in avec.pages]
    assert [p.read_rank for p in sans.pages] == [p.read_rank for p in avec.pages]
    assert sans.scan_dpi == avec.scan_dpi


@pytest.mark.parametrize("mauvais", [42, "un rappel", object(), {"a": 1}])
def test_un_rappel_du_MAUVAIS_TYPE_leve_au_lieu_de_s_eteindre(
    projet: Path, lot_de_trois: Path, mauvais
) -> None:
    """AC 9.2, second regime, et c'est le plus important des deux.

    « Un rappel qui s'eteint en silence quand on lui passe le mauvais type
    n'est pas optionnel, **il est casse** » (`AR3`). L'operateur croirait
    regarder une passe muette alors qu'il regarde un defaut de cablage.

    **La garde est a l'ENTREE, pas dans l'emetteur**, et c'est un choix de
    perimetre : `progression.EmetteurProgression` ecarte un non-appelable en
    silence (`rappel if callable(rappel) else None`), et l'y faire lever
    changerait le contrat de TOUS ses appelants -- extraction comprise. L'AC
    9.2 vise `calibrer_la_chaine` ; la garde y est.
    """
    with pytest.raises(TypeError) as refus:
        scan_calibrate.calibrer_la_chaine(
            projet, lot_de_trois, dpi=DPI, rappel_progression=mauvais)
    motif = str(refus.value)
    # **L'assertion porte sur la PHRASE de la garde, pas sur le nom du
    # parametre**, et ce n'est pas du zele : avant que le parametre n'existe,
    # Python levait lui-meme `TypeError: got an unexpected keyword argument
    # 'rappel_progression'` -- qui contient le nom. Ce banc etait donc VERT
    # avant l'implementation, sur le message de Python. Un faux vert dans le
    # rouge-vert est pire qu'un test manquant : il fait croire la propriete
    # acquise avant qu'elle n'existe.
    assert "n'est pas optionnel, il est casse" in motif
    assert type(mauvais).__name__ in motif


def test_None_reste_ACCEPTE_et_ne_leve_pas(projet: Path,
                                           lot_de_trois: Path) -> None:
    """Le volet symetrique de la garde : `None` est le repli, pas une faute.

    Sans lui, une garde ecrite trop large (`if rappel is not None` mal placee,
    ou un `callable(None)` mal lu) rendrait le parametre OBLIGATOIRE, et tous
    les appelants existants -- la CLI en tete -- leveraient.
    """
    rapport = scan_ingest.ingest_scan_lot(projet, lot_de_trois, dpi=DPI)
    # Le refus attendu est celui de la calibration (pas de mire), jamais un
    # `TypeError` de garde.
    with pytest.raises(scan_calibrate.RefusDeCalibration):
        scan_calibrate.calibrer_la_chaine(
            projet, lot_de_trois, dpi=DPI, rappel_progression=None)
    assert rapport.pages


# --- AC 9.3 : aucun jalon avant la premiere page ---------------------------


def test_un_refus_d_INGESTION_ne_produit_AUCUN_jalon(projet: Path,
                                                     tmp_path: Path) -> None:
    """AC 9.3, frontiere negative sur un refus REEL (`EPIC7-ARB-79`).

    « Aucun jalon avant la premiere ecriture. » Un ecran de progression qui
    paraitrait sur un refus d'ingestion annoncerait une tache qui n'a jamais
    commence -- et c'est exactement la confusion que ce lot existe pour fermer,
    a l'envers.

    Le refus est REEL et non simule : un dossier sans aucune page. Un double
    qui leverait a la place de l'ingestion mesurerait le banc, pas le produit.
    """
    vide = tmp_path / "sans_pages"
    vide.mkdir()
    (vide / "notes.txt").write_text("rien", encoding="utf-8")

    jalons = []
    with pytest.raises(scan_ingest.ScanIngestError):
        scan_calibrate.calibrer_la_chaine(
            projet, vide, dpi=DPI, rappel_progression=lambda *a: jalons.append(a))
    assert jalons == []


def test_un_refus_de_DPI_ne_produit_pas_davantage_de_jalon(
    projet: Path, lot_de_trois: Path
) -> None:
    """Le refus d'un cran PLUS PROFOND, et il compte autant.

    Le premier volet s'arrete a l'ingestion : la detection n'est jamais
    atteinte, donc l'emetteur n'est jamais construit. Celui-ci passe
    l'ingestion et meurt dans `detect_pages`, ou l'emetteur EXISTE -- c'est le
    seul regime qui mesure que le refus precede bien l'ouverture du canal, et
    non l'inverse.
    """
    rapport = scan_ingest.ingest_scan_lot(projet, lot_de_trois, dpi=DPI)
    jalons = []
    with pytest.raises(scan_detection.ScanDetectionError):
        scan_detection.detect_lot_pages(
            projet, rapport, dpi=0,
            rappel_progression=lambda *a: jalons.append(a))
    assert jalons == []


# ---------------------------------------------------------------------------
# Fermeture de la revue de VAGUE B -- ce que la campagne avait laisse passer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mauvaise_arite", [
    pytest.param(lambda faites: None, id="un-seul-parametre"),
    pytest.param(lambda: None, id="aucun-parametre"),
    pytest.param(lambda a, b, c: None, id="trois-parametres"),
])
def test_un_rappel_de_MAUVAISE_ARITE_leve_au_lieu_de_s_eteindre(
    projet: Path, lot_de_trois: Path, mauvaise_arite
) -> None:
    """`AR3`, la moitie que la garde de type ne voyait pas.

    `lambda faites: ...` est **appelable**, donc il passait la garde ; puis
    `EmetteurProgression` absorbait le `TypeError` **par contrat**
    (`EPIC7-ARB-79` : le canal ne peut pas faire echouer le travail qu'il
    observe). Resultat mesure sur un lot de trois pages : zero jalon, aucune
    levee, aucun message -- exactement le regime que l'AC 9.2 dit fermer, et la
    forme qu'on ecrit par accident. Le banc du lot documente lui-meme s'y etre
    fait prendre avec un `jalons.append` nu.

    **Trois arites fautives et non une**, dont une en trop : une garde ecrite
    avec un `<` au lieu d'une egalite passerait la troisieme.
    """
    with pytest.raises(TypeError) as refus:
        scan_calibrate.calibrer_la_chaine(
            projet, lot_de_trois, dpi=DPI,
            rappel_progression=mauvaise_arite)
    # **La phrase de la garde, pas le nom du parametre.** Le `TypeError` natif
    # de Python contient deja « rappel_progression » quand le mot-cle est
    # inconnu : une assertion sur ce nom serait verte AVANT l'implementation.
    assert "il est casse" in str(refus.value)
    assert "deux entiers" in str(refus.value)


def test_la_garde_d_ARITE_precede_l_ingestion_comme_celle_de_TYPE(
    projet: Path, lot_de_trois: Path, monkeypatch
) -> None:
    """« Un rappel casse doit se dire AVANT que la passe n'ait rien copie. »

    Mutant vise : deplacer la garde **apres** `ingest_scan_lot`. Il survivait a
    la campagne du lot -- aucun banc ne mesurait l'ORDRE, seulement la levee.

    La mesure est un **temoin** : on remplace l'ingestion par une sentinelle qui
    note son passage. Un refus qui la trouve appelee est un refus trop tardif.
    """
    passages = []

    def _ingestion_temoin(*args, **kwargs):
        passages.append("ingestion")
        raise AssertionError("l'ingestion ne doit pas etre atteinte")

    monkeypatch.setattr(scan_ingest, "ingest_scan_lot", _ingestion_temoin)
    with pytest.raises(TypeError):
        scan_calibrate.calibrer_la_chaine(
            projet, lot_de_trois, dpi=DPI,
            rappel_progression=lambda faites: None)
    assert passages == [], (
        "la garde doit refuser AVANT que la passe n'ait rien copie")


def test_un_appelable_INTROSPECTABLE_a_deux_entiers_reste_ACCEPTE(
    projet: Path, lot_de_trois: Path
) -> None:
    """Volet symetrique : la garde d'arite ne refuse pas ce qui est bon.

    Sans lui, une garde qui leverait sur TOUT rappel serait verte au test
    precedent -- et fermerait le canal que la story ouvre. Les trois formes
    legitimes du depot sont jouees : la lambda a deux parametres, la methode
    liee, et le `*args` variadique que les bancs emploient.
    """
    jalons: list[tuple] = []

    class _Surface:
        def noter(self, faites, total):
            jalons.append((faites, total))

    for rappel in (lambda faites, total: jalons.append((faites, total)),
                   _Surface().noter,
                   lambda *args: jalons.append(args)):
        jalons.clear()
        # La passe echoue plus loin (pas de mire sur des pages de synthese) ;
        # ce qui compte est qu'aucun `TypeError` de garde ne soit leve.
        try:
            scan_calibrate.calibrer_la_chaine(
                projet, lot_de_trois, dpi=DPI, rappel_progression=rappel)
        except TypeError as exc:  # pragma: no cover -- ne doit pas arriver
            raise AssertionError(
                f"un rappel legitime a ete refuse : {exc}") from exc
        except Exception:
            pass
        assert jalons, f"le rappel {rappel!r} n'a recu aucun jalon"


def test_AR3_sur_CALIBRER_LA_CHAINE_et_non_sur_un_maillon_plus_bas(
    projet: Path, lot_de_trois: Path
) -> None:
    """`AR3` premier regime, mesure sur la fonction que l'AC 9.2 NOMME.

    Mutant vise : `if rappel_progression is not None: dpi = dpi + 1` juste avant
    la detection. **SURVIVANT sur 1465 tests** -- la presence du rappel pouvait
    changer l'observable sans qu'aucun banc ne bronche.

    Le banc du lot comparait deux appels a `detect_lot_pages` sur leurs pages et
    leurs statuts : un maillon plus bas que celui que l'AC vise. Aucun test ne
    faisait tourner `calibrer_la_chaine` avec et sans rappel.

    L'observable compare est **ce que la fonction rend ou leve**, terme a
    terme : « ce champ diverge » ne mesure rien, « l'ensemble des chemins qui
    divergent est exactement vide » mesure l'exception ET son unicite.
    """
    def _issue(rappel):
        try:
            return ("rendu", scan_calibrate.calibrer_la_chaine(
                projet, lot_de_trois, dpi=DPI, rappel_progression=rappel))
        except Exception as exc:
            return ("leve", type(exc).__name__, str(exc))

    sans = _issue(None)
    avec = _issue(lambda faites, total: None)
    assert sans == avec, (
        "la presence du rappel ne doit RIEN changer a l'observable : "
        f"sans={sans!r} avec={avec!r}")


def test_AR3_ce_que_la_passe_FAIT_ne_change_pas_non_plus(
    projet: Path, lot_de_trois: Path, monkeypatch
) -> None:
    """`AR3` premier regime, mesure sur les ARGUMENTS et non sur l'issue seule.

    Mutant vise : `if rappel_progression is not None: dpi = dpi + 1` avant
    l'ingestion. **Il a survecu au banc voisin**, et le motif est instructif :
    sur des pages de synthese la passe echoue au meme endroit avec 300 comme
    avec 301, si bien que ce qu'elle REND est identique alors que ce qu'elle
    FAIT ne l'est pas. Comparer l'issue ne suffit donc pas -- un rappel qui
    deregle la resolution passerait, et c'est exactement le genre de faute
    d'argument qu'`AR3` existe pour ecarter.

    On compare donc ce que `calibrer_la_chaine` transmet a ses deux
    collaborateurs, et on rend l'ensemble EXACT des cles qui divergent : « ce
    champ diverge » ne mesure rien, « l'ensemble des cles qui divergent est
    exactement {'rappel_progression'} » mesure l'exception ET son unicite.
    """
    def _recolter(rappel):
        vus: list[tuple[str, dict]] = []
        vrai_ingest = scan_ingest.ingest_scan_lot
        vrai_detect = scan_detection.detect_lot_pages

        def _ingest(project_dir, scan_path, **kwargs):
            vus.append(("ingest", dict(kwargs)))
            return vrai_ingest(project_dir, scan_path, **kwargs)

        def _detect(project_dir, rapport, **kwargs):
            # Le rappel lui-meme est remplace par un marqueur : deux fonctions
            # distinctes ne sont jamais egales, et la comparaison porte sur sa
            # PRESENCE, pas sur son identite.
            note = dict(kwargs)
            note["rappel_progression"] = (
                "pose" if note.get("rappel_progression") else "absent")
            vus.append(("detect", note))
            return vrai_detect(project_dir, rapport, **kwargs)

        monkeypatch.setattr(scan_ingest, "ingest_scan_lot", _ingest)
        monkeypatch.setattr(scan_detection, "detect_lot_pages", _detect)
        try:
            scan_calibrate.calibrer_la_chaine(
                projet, lot_de_trois, dpi=DPI, rappel_progression=rappel)
        except Exception:
            pass
        monkeypatch.undo()
        return vus

    sans = _recolter(None)
    avec = _recolter(lambda faites, total: None)

    assert [nom for nom, _ in sans] == [nom for nom, _ in avec], (
        "la presence du rappel ne doit pas changer QUI est appele")
    assert sans, "la passe doit atteindre au moins l'ingestion"
    divergentes = {
        cle
        for (_, gauche), (_, droite) in zip(sans, avec)
        for cle in set(gauche) | set(droite)
        if gauche.get(cle) != droite.get(cle)
    }
    assert divergentes == {"rappel_progression"}, (
        "le SEUL argument qui doit differer est le rappel lui-meme ; "
        f"divergents : {divergentes}")
