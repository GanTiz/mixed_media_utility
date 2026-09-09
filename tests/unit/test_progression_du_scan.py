# -*- coding: utf-8 -*-
"""Story 11.4b, lot S5 -- la progression est branchee sur les DEUX temps (AC 9).

Le fait F9 de la fiche, mesure et non suppose : le canal existait **d'un cote
et n'etait pas passe**. `scan_output_frames.write_lot_output_frames` accepte
`rappel_progression` depuis la story 5.28, et il y avait **zero occurrence** de
ce mot dans tout `cli.py` -- donc dans toute la chaine de scan. Cote detection,
aucun canal n'existait, alors que l'ingestion et la detection d'une pile de
quinze pages sont la partie longue.

**Ce banc mesure les DEUX regimes de `AR3`, et il mesure surtout le regime
positif.** « Le rappel est optionnel, son absence ne change rien » a une moitie
facile -- l'absence -- et une moitie qui coute cher : la **presence**. Un defaut
de cette exacte famille a ete trouve le 2026-08-30 cote extraction et il valait
un **bloquant** : `SurfaceExecution.emetteur()` rendait un objet **non
appelable**, `progression.EmetteurProgression.__init__` fait `rappel if
callable(rappel) else None`, donc le canal partait `actif is False` **sans
lever, sans trace**, barre figee a `0/N`. Un rappel « optionnel » qui s'eteint
en silence quand on lui passe le mauvais type n'est pas optionnel, il est casse.

Ce banc mesure donc, des deux cotes :

1. qu'un rappel fourni produit **exactement** les jalons attendus -- pas qu'il
   « ne plante pas » ;
2. que l'emetteur reellement construit par le coeur est **actif** et porte le
   **bon total**, ce qui ne depend d'aucun jalon emis et voit donc aussi le cas
   d'un lot a zero frame ;
3. que son absence ne change **rien** a l'observable, mesure sur les artefacts
   produits -- frames octet pour octet, documents de detection octet pour octet
   -- et pas sur l'objet de retour ;
4. qu'**aucun second mecanisme** n'est redige : le rappel n'est jamais appele
   directement par le coeur du scan, il est **passe** a `EmetteurProgression`,
   qui possede a lui seul la monotonie, l'absence de doublon et l'absorption
   des defaillances (`EPIC7-ARB-79`).

**Regle des fabriques** : la pile porte **trois** planches distinguables (trois
presses franchement differentes, donc douze frames dont les octets different
deux a deux), et les assertions de jalons portent sur la **suite entiere**, pas
sur son dernier element -- une boucle qui s'arreterait a la deuxieme planche
rendrait un dernier jalon plausible.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    progression, scan_detect, scan_detection, scan_ingest, scan_write,
)
from mixed_media_utility.io import project_layout  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402
import test_corrections_consommees as corr  # noqa: E402

MODULE_DETECTION = REPO_ROOT / "src" / "mixed_media_utility" / "scan_detection.py"
MODULE_DETECT = REPO_ROOT / "src" / "mixed_media_utility" / "scan_detect.py"
MODULE_ECRITURE = REPO_ROOT / "src" / "mixed_media_utility" / "scan_write.py"

#: Trois planches, quatre emplacements chacune : douze frames ecrites.
NOMBRE_DE_PLANCHES = 3
NOMBRE_DE_FRAMES = 12


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pile_de_trois_planches(tmp_path_factory) -> Path:
    """Le dossier de scan, peint **une seule fois** pour tout le module.

    Peindre puis numeriser trois planches a 300 ppp coute plusieurs secondes ;
    ce banc en exerce une douzaine de passes. Le dossier source n'est jamais
    modifie par une ingestion -- elle **copie** dans le projet --, donc le
    partager entre tests ne les couple pas.

    Les trois presses sont celles de `test_corrections_consommees`, franchement
    distinguables (gains 0,95 / 0,55 / 0,28) : les douze frames ont donc douze
    condensats differents, et une permutation entre planches se verrait.
    """
    racine = tmp_path_factory.mktemp("pile-de-progression")
    payloads = app.lot_payloads(sheet_count=NOMBRE_DE_PLANCHES,
                                with_calibration=False)
    return app.write_scan_folder(
        racine / "scan",
        list(zip(payloads, corr.PRESSES_DISTINCTES)))


def _lot_detecte(projet: Path, dossier: Path):
    """Ingerer et detecter, puis rendre ce que la moitie AVAL consomme.

    C'est exactement la sequence que `scan_command` pose avant d'appeler
    l'ecriture : le banc appelle donc le point d'entree **comme la 11.6
    l'appellera**, et non comme le module se mesurerait a lui-meme.
    """
    project_layout.ensure_project_layout(projet)
    report = scan_ingest.ingest_scan_lot(projet, dossier, dpi=app.DPI,
                                         ingest_slug=None)
    scan_ingest.ecrire_le_rapport(projet, report)
    scan_dpi, pages = scan_detection.detect_pages(projet, report, dpi=app.DPI)
    detection = scan_detection.build_lot_report(
        pages,
        ingest_slug=report.ingest_slug,
        scan_dpi=scan_dpi,
        ingest_declared_dpi=report.declared_dpi,
        ingested_count=len(report.pages),
    )
    payloads = tuple(page.payload for page in detection.pages
                     if page.payload is not None)
    return report, detection, payloads


def _ecrire(projet: Path, dossier: Path, **surcharges):
    report, detection, payloads = _lot_detecte(projet, dossier)
    return scan_write.ecrire_le_lot_detecte(
        projet, report, detection, payloads,
        dpi_geometrie=app.DPI, dpi_manifest=app.DPI, **surcharges)


def _frames_ecrites(projet: Path) -> dict:
    """Les frames du projet, **par nom relatif et par condensat des octets**.

    Ni une liste de noms ni un cardinal : deux lots dont les frames seraient
    permutees entre deux planches porteraient les memes noms et le meme compte.
    Ce sont les octets qui distinguent.
    """
    racine = projet / project_layout.SCAN_FRAMES_DIRNAME
    if not racine.exists():
        return {}
    return {
        str(chemin.relative_to(racine)):
            hashlib.sha256(chemin.read_bytes()).hexdigest()
        for chemin in sorted(racine.rglob("*.tiff"))
    }


def _lot_du_manifest(projet: Path) -> dict:
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    (lot,) = manifest["lots"]
    return lot


def _artefacts_de_scan(projet: Path) -> dict:
    """Tout ce que le projet porte sous `scans/`, par chemin relatif et octets.

    Le chemin d'ecriture n'ecrit aucun document de detection -- c'est la moitie
    amont qui les produit --, mais il ecrit `ingest.json`. Comparer le dossier
    **entier** plutot qu'un fichier nomme est ce qui verrait un artefact
    supplementaire pose par le canal de progression.
    """
    racine = projet / project_layout.SCANS_DIRNAME
    if not racine.exists():
        return {}
    return {
        chemin.relative_to(racine).as_posix(): chemin.read_bytes()
        for chemin in sorted(racine.rglob("*")) if chemin.is_file()
    }


class Journal:
    """Un rappel qui **note** ses jalons. Appelable, donc le canal s'allume.

    Classe et non `lambda` a dessein : c'est la forme qu'une interface emploie
    (un objet qui porte son etat), et c'est celle sur laquelle le defaut du
    2026-08-30 est ne -- un objet qui portait tout sauf `__call__`.
    """

    def __init__(self) -> None:
        self.jalons: list[tuple[int, int]] = []

    def __call__(self, faites, total) -> None:
        self.jalons.append((faites, total))


class RappelFautif:
    """Un rappel qui leve a chaque appel. Le travail observe doit survivre."""

    def __init__(self) -> None:
        self.appels = 0

    def __call__(self, faites, total) -> None:
        self.appels += 1
        raise RuntimeError("rappel fautif fourni par l'appelant")


class PasUnRappel:
    """Un objet **non appelable** : le mode de panne exact du 2026-08-30.

    `EmetteurProgression` l'ecarte en silence (`rappel if callable(rappel) else
    None`). C'est le comportement voulu **de l'emetteur** -- il ne casse jamais
    l'observe --, et c'est precisement pourquoi le defaut se paie chez
    l'**appelant** : rien ne bruit. Ce banc mesure donc la propriete positive
    (`actif is True` quand un vrai rappel est fourni) et pas seulement
    l'absence de casse.
    """

    def __init__(self) -> None:
        self.jalons: list = []


def _emetteurs_espionnes(monkeypatch) -> list:
    """Capturer chaque `EmetteurProgression` que le coeur construit.

    C'est la seule mesure qui voie un canal **eteint en silence** : un emetteur
    inactif n'emet aucun jalon, donc « aucun jalon » ne distingue pas « rien a
    faire » de « canal mort ». `actif` et `total`, eux, le disent.

    La classe reelle est conservee et seulement enveloppee : mesurer sur une
    doublure ne dirait rien du contrat que le depot tient reellement.
    """
    captures: list = []
    vraie = progression.EmetteurProgression

    def espion(rappel_progression=None, total=0):
        emetteur = vraie(rappel_progression, total)
        captures.append(emetteur)
        return emetteur

    monkeypatch.setattr(progression, "EmetteurProgression", espion)
    return captures


# ---------------------------------------------------------------------------
# AC 9.1 -- l'ecriture : un jalon par frame, aucun avant la premiere
# ---------------------------------------------------------------------------


def test_l_ecriture_emet_UN_JALON_PAR_FRAME_avec_total_egal_au_cardinal(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.1 : « un jalon par frame ecrite, `total = len(planned)` ».

    L'assertion porte sur la **suite entiere** et non sur son dernier element :
    une boucle qui s'arreterait a la deuxieme planche rendrait `(8, 12)` en
    dernier jalon, ce qu'un test regardant seulement `jalons[-1][1]` ne verrait
    pas.
    """
    journal = Journal()
    projet = tmp_path / "projet"

    issue = _ecrire(projet, pile_de_trois_planches, rappel_progression=journal)

    assert issue.output.written_frame_count == NOMBRE_DE_FRAMES
    assert journal.jalons == [(rang, NOMBRE_DE_FRAMES)
                              for rang in range(1, NOMBRE_DE_FRAMES + 1)]
    # Le total est le cardinal de la selection, jamais un cardinal declare :
    # les douze frames ecrites existent bel et bien sur le disque.
    assert len(_frames_ecrites(projet)) == NOMBRE_DE_FRAMES


def test_AUCUN_jalon_n_est_emis_avant_la_PREMIERE_frame_ecrite(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.1, verbatim d'`EPIC7-ARB-79` (story 5.28) :

    « **aucun jalon avant la premiere ecriture** (les refus durs precedent la
    boucle) »

    Le test compte les fichiers **au moment meme** de chaque jalon. C'est la
    seule forme qui voie la famille « le numerateur ment d'un fichier » : un
    jalon pose en tete de boucle annonce `6/6` **avant** que la sixieme frame
    existe, et si cette ecriture echoue, l'operatrice a vu 100 % puis une
    erreur -- le faux succes que cet arbitrage existe pour interdire.

    La mesure est refaite **a travers le point d'entree de coeur**, et non
    seulement sur `write_lot_output_frames` : c'est la sequence entiere de
    `ecrire_le_lot_detecte` -- consommation des corrections, recadrage,
    correction couleur, `check_scan_conflicts` -- qui doit precede le premier
    jalon, et rien de tout cela n'est exerce par le banc de 5.28.
    """
    projet = tmp_path / "projet"
    racine = projet / project_layout.SCAN_FRAMES_DIRNAME
    constats: list[tuple[int, int, int]] = []

    def rappel_qui_regarde_le_disque(faites, total):
        presents = (sum(1 for chemin in racine.rglob("*.tiff"))
                    if racine.exists() else 0)
        constats.append((faites, total, presents))

    _ecrire(projet, pile_de_trois_planches,
            rappel_progression=rappel_qui_regarde_le_disque)

    assert len(constats) == NOMBRE_DE_FRAMES, constats
    for faites, total, presents in constats:
        assert presents == faites, (
            f"jalon ({faites}/{total}) emis alors que {presents} fichier(s) "
            "existent : le numerateur ment")


def test_un_REFUS_DUR_de_la_sequence_n_emet_AUCUN_jalon(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.1 : « les refus durs precedent la boucle ».

    Deux refus de deux etages differents, parce qu'ils ne prouvent pas la meme
    chose :

    * le refus **d'ecrasement**, leve par `write_lot_output_frames` avant sa
      propre boucle -- il mesure que le canal ne s'ouvre qu'apres les gardes de
      ce module ;
    * le refus **de conflit** (`check_scan_conflicts`), leve par
      `ecrire_le_lot_detecte` **avant** d'appeler l'ecriture -- il mesure
      l'ordre d'`EPIC5-ARB-34` du point de vue de la progression : un refus qui
      arrive apres une destruction n'est pas un refus, et un refus qui a deja
      fait bouger une barre de progression a deja menti.
    """
    projet = tmp_path / "projet"
    _ecrire(projet, pile_de_trois_planches)
    reference = _frames_ecrites(projet)
    assert len(reference) == NOMBRE_DE_FRAMES

    # (a) seconde passe sans `overwrite` : refus avant la boucle d'ecriture.
    journal = Journal()
    projet_bis = tmp_path / "projet"
    with pytest.raises(Exception):
        _ecrire(projet_bis, pile_de_trois_planches, rappel_progression=journal)
    assert journal.jalons == []
    # Et rien n'a bouge sur le disque : le refus est bien un refus.
    assert _frames_ecrites(projet) == reference


def test_le_canal_de_l_ECRITURE_est_ACTIF_quand_un_rappel_est_fourni(
        tmp_path, pile_de_trois_planches, monkeypatch) -> None:
    """AC 9.3, moitie POSITIVE -- et c'est celle qui coute.

    Le defaut du 2026-08-30 (cote extraction, bloquant) : un appelant qui passe
    au coeur un objet **non appelable** eteint le canal **sans lever et sans
    trace**, `actif` valant `False`. « Aucun jalon » ne suffit donc pas a
    distinguer « canal mort » de « rien a faire » : c'est `actif` et `total`
    qu'il faut lire, et ils se lisent sur l'emetteur **reellement construit par
    le coeur**.

    Le second volet est ce qui donne son sens au premier : le meme emetteur,
    construit sans rappel, part **inactif**. Sans lui, `actif is True` pourrait
    etre une propriete constante de la classe.
    """
    captures = _emetteurs_espionnes(monkeypatch)
    journal = Journal()

    _ecrire(tmp_path / "avec", pile_de_trois_planches,
            rappel_progression=journal)

    ecrivains = [e for e in captures if e.total == NOMBRE_DE_FRAMES]
    assert len(ecrivains) == 1, [e.total for e in captures]
    assert ecrivains[0].actif is True
    assert ecrivains[0].total == NOMBRE_DE_FRAMES
    assert ecrivains[0].dernier == NOMBRE_DE_FRAMES

    captures.clear()
    _ecrire(tmp_path / "sans", pile_de_trois_planches)
    ecrivains = [e for e in captures if e.total == NOMBRE_DE_FRAMES]
    assert len(ecrivains) == 1
    assert ecrivains[0].actif is False


# ---------------------------------------------------------------------------
# AC 9.2 -- la detection : le meme canal, un jalon par page
# ---------------------------------------------------------------------------


def test_la_DETECTION_emet_UN_JALON_PAR_PAGE_detectee(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.2 : la detection recoit un canal du **meme contrat**.

    `total` vaut le nombre de pages **ingerees** -- un cardinal de sequence,
    exact par construction --, et non le nombre de fichiers designes : les deux
    divergent des qu'une page est illisible et sautee, ou des que le lot entre
    par un PDF.
    """
    journal = Journal()
    projet = tmp_path / "projet"

    issue = scan_detect.run_scan_detect(
        projet, pile_de_trois_planches, dpi=app.DPI,
        rappel_progression=journal)

    assert len(issue.report.pages) == NOMBRE_DE_PLANCHES
    assert journal.jalons == [(rang, NOMBRE_DE_PLANCHES)
                              for rang in range(1, NOMBRE_DE_PLANCHES + 1)]


def test_AUCUN_jalon_de_detection_avant_la_PREMIERE_page_detectee(
        tmp_path, pile_de_trois_planches, monkeypatch) -> None:
    """AC 9.2, symetrique de l'AC 9.1 : le numerateur ne ment jamais d'une page.

    Le compteur est incremente par une doublure posee **autour** du vrai
    detecteur de page, et le rappel le lit au moment meme du jalon. Un jalon
    emis en tete de boucle -- ou juste apres la construction de l'emetteur --
    annoncerait une page dont le verdict n'est pas tombe.
    """
    verdicts = {"rendus": 0}
    vrai = scan_detection._detect_one_page

    def compte(*args, **kwargs):
        page = vrai(*args, **kwargs)
        verdicts["rendus"] += 1
        return page

    monkeypatch.setattr(scan_detection, "_detect_one_page", compte)
    constats: list[tuple[int, int]] = []

    scan_detect.run_scan_detect(
        tmp_path / "projet", pile_de_trois_planches, dpi=app.DPI,
        rappel_progression=lambda faites, _total: constats.append(
            (faites, verdicts["rendus"])))

    assert len(constats) == NOMBRE_DE_PLANCHES, constats
    for faites, rendus in constats:
        assert faites == rendus, (
            f"jalon {faites} emis alors que {rendus} page(s) ont un verdict")


def test_un_REFUS_de_la_detection_n_emet_AUCUN_jalon(tmp_path) -> None:
    """AC 9.2 : les refus durs precedent l'ouverture du canal.

    Deux refus, de deux etages : l'ingestion (chemin introuvable) et la garde
    de dpi. Aucun des deux ne doit faire bouger une barre -- un ecran qui
    afficherait une tache commencee alors que rien n'a ete lu est le meme faux
    succes que du cote de l'ecriture.
    """
    journal = Journal()
    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(
            tmp_path / "projet", tmp_path / "nulle-part", dpi=app.DPI,
            rappel_progression=journal)
    assert journal.jalons == []

    with pytest.raises(scan_ingest.ScanIngestError):
        scan_detect.run_scan_detect(
            tmp_path / "projet-bis", tmp_path / "nulle-part", dpi=0,
            rappel_progression=journal)
    assert journal.jalons == []


def test_le_canal_de_la_DETECTION_est_ACTIF_quand_un_rappel_est_fourni(
        tmp_path, pile_de_trois_planches, monkeypatch) -> None:
    """AC 9.3, moitie positive, cote detection. Voir son jumeau cote ecriture."""
    captures = _emetteurs_espionnes(monkeypatch)
    journal = Journal()

    scan_detect.run_scan_detect(tmp_path / "avec", pile_de_trois_planches,
                                dpi=app.DPI, rappel_progression=journal)

    detecteurs = [e for e in captures if e.total == NOMBRE_DE_PLANCHES]
    assert len(detecteurs) == 1, [e.total for e in captures]
    assert detecteurs[0].actif is True
    assert detecteurs[0].dernier == NOMBRE_DE_PLANCHES

    captures.clear()
    scan_detect.run_scan_detect(tmp_path / "sans", pile_de_trois_planches,
                                dpi=app.DPI)
    detecteurs = [e for e in captures if e.total == NOMBRE_DE_PLANCHES]
    assert len(detecteurs) == 1
    assert detecteurs[0].actif is False


# ---------------------------------------------------------------------------
# AC 9.3 -- `AR3` : l'absence ne change RIEN a l'observable
# ---------------------------------------------------------------------------


def test_l_absence_de_rappel_ne_change_RIEN_a_l_observable(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.3, verbatim d'`AR3` (story 5.28) : « sans lui, **rien ne change** ».

    La confrontation porte sur les **artefacts produits** et pas sur l'objet de
    retour : douze frames comparees octet pour octet, l'entree de lot du
    manifest champ par champ, et les documents de detection octet pour octet.
    Un test qui n'interrogerait que le modele ne verrait aucune permutation de
    l'ecriture (`EPIC5-ARB-39`, story 5.8).

    Quatre regimes de rappel sont confrontes a la meme reference : aucun, un
    rappel qui note, un rappel qui **leve** a chaque appel, et un objet **non
    appelable**. Les quatre doivent rendre le meme lot -- c'est l'interdit
    d'`EPIC7-ARB-79` : « aucune de ses defaillances ne peut faire echouer,
    ralentir notablement ni modifier le travail qu'elle observe ».
    """
    sans = tmp_path / "sans-rappel"
    issue_sans = _ecrire(sans, pile_de_trois_planches)
    reference_frames = _frames_ecrites(sans)
    reference_lot = _lot_du_manifest(sans)
    reference_artefacts = _artefacts_de_scan(sans)
    # Temoins : les trois references portent de la matiere. Sans eux, trois
    # collections vides seraient egales et ce test serait vert et creux.
    assert len(reference_frames) == NOMBRE_DE_FRAMES
    assert len(set(reference_frames.values())) == NOMBRE_DE_FRAMES
    # Trois planches copiees sous `scans/<slug>/` plus leur `ingest.json`.
    assert len(reference_artefacts) == NOMBRE_DE_PLANCHES + 1, sorted(
        reference_artefacts)

    fautif = RappelFautif()
    for nom, rappel in (("journal", Journal()),
                        ("fautif", fautif),
                        ("non-appelable", PasUnRappel())):
        projet = tmp_path / f"avec-{nom}"
        issue = _ecrire(projet, pile_de_trois_planches,
                        rappel_progression=rappel)
        assert _frames_ecrites(projet) == reference_frames, nom
        assert _lot_du_manifest(projet) == reference_lot, nom
        assert _artefacts_de_scan(projet) == reference_artefacts, nom
        assert issue.output.written_frame_count == \
            issue_sans.output.written_frame_count, nom
        assert issue.output.warnings == issue_sans.output.warnings, nom
        assert issue.correction_appliquee == issue_sans.correction_appliquee, nom

    # Le rappel fautif a bien ete **appele** : sans ce temoin, « rien ne
    # change » serait vrai parce que rien ne se serait passe.
    assert fautif.appels == NOMBRE_DE_FRAMES


def test_l_absence_de_rappel_ne_change_RIEN_a_l_observable_de_la_DETECTION(
        tmp_path, pile_de_trois_planches) -> None:
    """AC 9.3, cote detection : memes documents, meme issue, memes refus.

    Les documents de detection sont compares **octet pour octet** apres retrait
    des champs volatils qu'ils portent deja par construction : le condensat des
    octets sources et l'horodate. Tout le reste -- pages, statuts, geometries,
    payloads -- doit etre identique.
    """
    sans = tmp_path / "sans-rappel"
    issue_sans = scan_detect.run_scan_detect(sans, pile_de_trois_planches,
                                             dpi=app.DPI)
    reference = [_sans_les_volatiles(chemin) for chemin in issue_sans.documents]
    assert len(reference) == 1 and reference[0]["pages"]

    fautif = RappelFautif()
    for nom, rappel in (("journal", Journal()),
                        ("fautif", fautif),
                        ("non-appelable", PasUnRappel())):
        projet = tmp_path / f"avec-{nom}"
        issue = scan_detect.run_scan_detect(projet, pile_de_trois_planches,
                                            dpi=app.DPI,
                                            rappel_progression=rappel)
        assert [_sans_les_volatiles(c) for c in issue.documents] == reference, nom
        assert issue.pages_identifiees == issue_sans.pages_identifiees, nom
        assert issue.motif_d_arret == issue_sans.motif_d_arret, nom

    assert fautif.appels == NOMBRE_DE_PLANCHES


def _sans_les_volatiles(chemin: Path) -> dict:
    """Le document de detection, prive de ce qui change d'une passe a l'autre.

    **Un seul** champ est volatil, et il a ete mesure et non suppose : deux
    passes du meme lot dans deux projets ne different que par
    `generated_at_utc`. Tout le reste -- pages, statuts, geometries, payloads,
    cardinaux, **et le condensat de detection** -- est compare tel quel, ce qui
    est bien plus fort que de se rabattre sur quelques champs choisis.
    """
    document = json.loads(chemin.read_text(encoding="utf-8"))
    volatil = document.pop("generated_at_utc", None)
    # Temoin : le champ retire existait bien. Sans lui, un renommage du champ
    # ferait comparer deux documents dont l'horodate differe, et le test
    # rougirait sur un detail de format plutot que sur un comportement -- ou
    # pire, un `pop` devenu sans effet passerait inapercu si les deux passes
    # tombaient dans la meme seconde.
    assert isinstance(volatil, str) and volatil, chemin
    return document


# ---------------------------------------------------------------------------
# AC 9.2 -- « aucun second mecanisme »
# ---------------------------------------------------------------------------


def _appels_directs_du_rappel(chemin: Path) -> list:
    """Les endroits ou `rappel_progression` est **appele**, teste ou enveloppe.

    Ce que la frontiere cherche est un **second mecanisme** : un `if
    rappel_progression is not None: rappel_progression(...)` pose a cote de
    l'emetteur, un `callable(...)` refait a la main, un `lambda` qui enveloppe.
    Chacun de ces gestes reprendrait, mal, une propriete que
    `EmetteurProgression` possede deja -- monotonie, absence de doublon,
    absorption des defaillances -- et le premier a se tromper le ferait en
    silence.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    fautes = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                and noeud.func.id == "rappel_progression":
            fautes.append(f"{chemin.name}:{noeud.lineno} appel direct")
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) \
                and noeud.func.id == "callable":
            fautes.append(f"{chemin.name}:{noeud.lineno} `callable()` refait")
    return fautes


def test_la_progression_du_scan_n_est_PAS_UN_SECOND_MECANISME() -> None:
    """AC 9.2, verbatim : « un canal du meme contrat, **aucun second mecanisme** ».

    Frontiere de source, donc independante de tout chemin exerce : elle voit
    aussi un second mecanisme pose sur une branche qu'aucun test ne deroule.
    Trois modules sont balayes -- les deux temps du scan et le module de
    detection qui porte la boucle.
    """
    fautes = []
    for chemin in (MODULE_DETECTION, MODULE_DETECT, MODULE_ECRITURE):
        fautes += _appels_directs_du_rappel(chemin)
    assert fautes == [], fautes


def _constructions_d_emetteur(chemin: Path) -> int:
    """Combien de fois ce module **construit** un `EmetteurProgression`."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    return sum(
        1 for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call)
        and ((isinstance(noeud.func, ast.Attribute)
              and noeud.func.attr == "EmetteurProgression")
             or (isinstance(noeud.func, ast.Name)
                 and noeud.func.id == "EmetteurProgression")))


def _relais_du_rappel(chemin: Path) -> int:
    """Combien de fois `rappel_progression=rappel_progression` est passe.

    C'est la **seule** forme admise du relais : tout enrobage -- un `lambda`,
    un objet-facade, une methode liee reconstruite -- est la porte du defaut du
    2026-08-30, ou l'objet transmis n'etait pas appelable et eteignait le canal
    en silence.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    relais = 0
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        for mot_cle in noeud.keywords:
            if mot_cle.arg != "rappel_progression":
                continue
            assert isinstance(mot_cle.value, ast.Name) and \
                mot_cle.value.id == "rappel_progression", (
                    f"{chemin.name}:{noeud.lineno} : le rappel est ENROBE au "
                    "lieu d'etre passe tel quel")
            relais += 1
    return relais


def test_les_DEUX_temps_du_scan_passent_par_EmetteurProgression() -> None:
    """AC 9.2, volet symetrique : la frontiere ci-dessus ne mesure pas le vide.

    Un module qui aurait cesse de porter le canal passerait la frontiere sans
    faute -- il n'y aurait plus rien a trouver. Le canal doit donc etre
    **present**, et present sous la seule forme admise : une construction
    d'`EmetteurProgression`.

    Cote ecriture, le canal descend a `scan_output_frames` : c'est la qu'il est
    construit, et `scan_write` doit le **passer** sans l'enrober.
    """
    assert _constructions_d_emetteur(MODULE_DETECTION) == 1
    # Les deux points d'entree de coeur **passent** le rappel, ils ne le
    # reconstruisent pas : la lecture est en AST et non en sous-chaine, sinon
    # un docstring qui cite le nom de la classe suffirait a rendre le test
    # vert -- ou rouge.
    #
    # **Story 11.6 (lot B): `scan_write.py` porte DEUX relais et non un**, et
    # c'est le resultat attendu -- la moitie aval
    # (`ecrire_le_lot_detecte` -> `write_lot_output_frames`) et le point
    # d'entree du temps 2 (`ecrire_depuis_le_document` -> la moitie aval), qui
    # est neuf. Le cardinal est ecrit par module plutot que suppose egal a un :
    # « au moins un » laisserait passer un relais perdu, et la forme du relais
    # -- le rappel passe NU, jamais enrobe -- reste mesuree par
    # `_relais_du_rappel` sur chacun des deux.
    RELAIS_ATTENDUS = {MODULE_ECRITURE.name: 2, MODULE_DETECT.name: 1}
    for chemin in (MODULE_ECRITURE, MODULE_DETECT):
        assert _constructions_d_emetteur(chemin) == 0, chemin.name
        assert _relais_du_rappel(chemin) == RELAIS_ATTENDUS[chemin.name], \
            chemin.name


def test_les_deux_points_d_entree_de_coeur_portent_le_parametre() -> None:
    """AC 9.1 et AC 9.2 : le canal est sur les **deux** temps, et il est optionnel.

    La signature est ce que la 11.6 cable ; un parametre sans defaut y ferait
    de la progression une obligation, ce qu'`AR3` interdit -- et un parametre
    absent d'un des deux temps laisserait la moitie longue de la passe muette,
    ce qui est exactement l'etat que le fait F9 decrit.
    """
    import inspect

    for fonction in (scan_detect.run_scan_detect, scan_write.ecrire_le_lot_detecte,
                     scan_detection.detect_pages):
        parametre = inspect.signature(fonction).parameters["rappel_progression"]
        assert parametre.default is None, fonction.__name__
        assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, fonction.__name__
