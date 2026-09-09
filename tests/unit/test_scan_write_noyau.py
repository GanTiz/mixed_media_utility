# -*- coding: utf-8 -*-
"""Story 11.4b, lot S1 -- le point d'entree de coeur de l'ecriture, et son enveloppeur.

Ce banc mesure les proprietes que l'extraction de `scan_write.ecrire_le_lot_detecte`
doit tenir, et seulement elles. Il est le symetrique aval de
`test_scan_detect_noyau.py`, qui mesure les memes proprietes sur la moitie amont
(`run_scan_detect`, story 7.3) :

1. **les memes artefacts** -- sur le meme lot, le coeur et la CLI ecrivent les
   memes frames (nom pour nom, octet pour octet) et la meme entree de manifest.
   La confrontation porte sur l'ARTEFACT PRODUIT et pas sur l'objet de retour :
   un test qui n'interroge que le modele ne voit aucune permutation de
   l'ecriture (`EPIC5-ARB-39`, story 5.8, ou deux tests d'integration
   survivaient aux trois mutations qu'ils devaient attraper) ;
2. **l'ordre d'`EPIC5-ARB-34`, mesure a l'ARRIVEE et a l'EXECUTION** --
   `check_scan_conflicts` avant `write_lot_output_frames` avant `persist_scan`.
   « Un refus qui arrive apres une destruction n'est pas un refus. » Le verrou de
   source vit dans `test_scan_manifest.py` ; celui-ci mord sur le chemin
   reellement pris ;
3. **le contrat de producteur** -- aucun `print`, aucun code de sortie, les
   exceptions du coeur levees telles quelles ;
4. **l'invite de correction est un PARAMETRE** -- le coeur ne lit jamais
   `stdin`, et les trois regimes restent ceux de la CLI.

Les planches sont **reellement peintes** par les fabriques du depot
(`test_scan_calibration_application`), jamais des fixtures TIFF versionnees :
`tests/fixtures/` n'en contient aucune.

Regle des fabriques : le lot nominal porte **deux planches distinguables** (deux
presses du meme tirage) et sa page de calibration est posee **en dernier**, pas
en premiere position -- une recherche fautive qui rendrait la premiere page lue
ne se demasque pas autrement.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli, scan_detection, scan_ingest, scan_output_frames, scan_write,
)
from mixed_media_utility.io import project_layout, scan_manifest  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _lot_de_deux_planches(tmp_path: Path, *, nom: str) -> Path:
    """Deux planches d'images DISTINGUABLES, sans page de calibration.

    Regle des fabriques, ses trois points a la fois :

    1. **deux** planches, jamais une -- et elles different par leur presse de
       tirage ET par leur emplacement de depart, donc une permutation entre
       elles se voit sur les octets produits ;
    2. la **cible** -- la page d'`page_index` 0 -- est posee en **seconde**
       position de lecture. Un appariement fautif qui rendrait la premiere page
       lue resterait vert autrement : c'est litteralement le mutant `M25` de la
       story 5.7, avec 257 tests verts et les cardinaux du scan ecrits sur le
       mauvais lot ;
    3. aucune page de calibration dans la pile : c'est le regime **nominal** du
       depot depuis `EPIC5-ARB-83` -- la page de calibration se scanne dans une
       passe separee et l'operateur **designe** le profil.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    return app.write_scan_folder(
        tmp_path / nom,
        [(payloads[1], app.PRESSES_DU_TIRAGE[1]),
         (payloads[0], app.PRESSES_DU_TIRAGE[0])])


def _lot_detecte(projet: Path, dossier: Path, *, dpi: int = app.DPI):
    """Ingerer et detecter, puis rendre ce que la moitie AVAL consomme.

    C'est exactement la sequence que `scan_command` pose avant d'appeler
    l'ecriture : le banc appelle donc le point d'entree **comme la 11.6
    l'appellera**, et non comme le module se mesurerait a lui-meme.
    """
    project_layout.ensure_project_layout(projet)
    report = scan_ingest.ingest_scan_lot(projet, dossier, dpi=dpi,
                                         ingest_slug=None)
    scan_ingest.ecrire_le_rapport(projet, report)
    scan_dpi, pages = scan_detection.detect_pages(projet, report, dpi=dpi)
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


def _profil_designe(tmp_path: Path, *, nom: str = "atelier") -> Path:
    """Le profil de la chaine, consigne par `scan ... calibrate` dans son projet.

    C'est le geste 1 d'`EPIC5-ARB-83`, et l'atelier est un projet a part : le
    profil designe se donne par un chemin, jamais par un appariement -- « un
    profil venu de n'importe ou est accepte » (`EPIC5-ARB-82`).
    """
    atelier = tmp_path / f"projet-{nom}"
    return app.consigner_le_profil_de_la_chaine(atelier, tmp_path, name=nom)


def _ecrire_par_le_coeur(projet: Path, dossier: Path, **surcharges):
    report, detection, payloads = _lot_detecte(projet, dossier)
    return scan_write.ecrire_le_lot_detecte(
        projet, report, detection, payloads,
        dpi_geometrie=app.DPI, dpi_manifest=app.DPI, **surcharges)


def _frames_ecrites(projet: Path) -> dict:
    """Les frames du projet, **par nom relatif et par condensat des octets**.

    Ni une liste de noms ni un cardinal : deux lots dont les frames seraient
    permutees entre deux planches porteraient les memes noms et le meme
    compte. Ce sont les octets qui distinguent, et les quatre zones d'une
    planche sont peintes de quatre couleurs differentes precisement pour que
    la permutation se voie.
    """
    racine = projet / project_layout.SCAN_FRAMES_DIRNAME
    return {
        str(chemin.relative_to(racine)):
            hashlib.sha256(chemin.read_bytes()).hexdigest()
        for chemin in sorted(racine.rglob("*.tiff"))
    }


def _lot_du_manifest(projet: Path) -> dict:
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    (lot,) = manifest["lots"]
    return lot


# ---------------------------------------------------------------------------
# 1 -- les memes artefacts que la CLI, contenu compare et non existence constatee
# ---------------------------------------------------------------------------


def test_le_coeur_et_la_cli_ecrivent_les_MEMES_frames_et_le_MEME_lot(tmp_path) -> None:
    """AC 1.2 et AC 10.1 : le corps a ete deplace, pas reecrit.

    Une seconde redaction du geste divergerait, et l'ecart ne se verrait que
    sur les TIFF produits -- c'est donc sur les TIFF produits que la mesure
    porte, octet pour octet, plus l'entree de lot du manifest.
    """
    # **Le MEME nom de dossier des deux cotes**, chacun sous son propre
    # parent (liaison du 2026-09-01). `EPIC11-ARB-109` a ajoute l'historique de
    # reconstruction PAR LOT, et son entree porte l'`ingest_slug` -- qui est
    # derive du nom du dossier ingere. Deux noms differents faisaient donc
    # diverger l'entree de lot pour une raison qui n'a rien a voir avec la voie
    # d'ecriture mesuree ici. Egaliser le slug plutot que l'exclure de la
    # comparaison : une egalite EXACTE mesure aussi les champs qu'on n'a pas
    # prevus, et c'est precisement ce qu'on veut d'un test « corps deplace,
    # jamais reecrit ».
    dossier_cli = _lot_de_deux_planches(tmp_path / "source-cli", nom="lot")
    dossier_coeur = _lot_de_deux_planches(tmp_path / "source-coeur", nom="lot")
    projet_cli = tmp_path / "projet-cli"
    projet_coeur = tmp_path / "projet-coeur"
    # **Le MEME profil designe des deux cotes**: sans lui les deux lots
    # sortiraient bruts, et l'egalite des octets serait celle de deux passes
    # qui n'ont rien corrige -- verte et creuse.
    profil = _profil_designe(tmp_path)

    assert app.run_scan(projet_cli, dossier_cli, "--profil", str(profil)) == 0
    issue = _ecrire_par_le_coeur(projet_coeur, dossier_coeur,
                                 profil_designe=profil)

    par_la_cli = _frames_ecrites(projet_cli)
    par_le_coeur = _frames_ecrites(projet_coeur)
    # Temoin : les deux passes ont bien produit de la matiere. Sans lui, deux
    # dossiers vides seraient egaux et ce test serait vert et creux.
    assert len(par_la_cli) == 8, sorted(par_la_cli)
    assert par_le_coeur == par_la_cli
    # Et les huit frames sont bien DISTINCTES : un ecrivain qui poserait huit
    # fois le meme raster passerait l'egalite ci-dessus.
    assert len(set(par_le_coeur.values())) == 8

    # L'entree de lot **entiere**, champ par champ: un test qui n'en
    # comparerait que le `lot_id` ne verrait ni un cardinal faux, ni une
    # provenance ecrite sur la mauvaise feuille.
    gauche = _lot_du_manifest(projet_cli)
    droite = _lot_du_manifest(projet_coeur)
    assert droite == gauche
    # Temoin: l'entree porte de la matiere, et pas seulement un identifiant.
    assert gauche["reconstructed_frame_count"] == 8, gauche
    assert gauche["expected_frame_count"] == 8, gauche
    assert gauche["state"] == "scan", gauche

    # L'objet de retour dit la meme chose que le manifest, sans le relire.
    assert issue.persisted.lot_id == droite["lot_id"]
    assert issue.persisted.manifest_path == projet_coeur / "project.json"
    assert issue.output.written_frame_count == 8
    # Et la correction a bel et bien ete posee : sans cela l'egalite des octets
    # comparerait deux passes brutes, et le test serait vert et creux.
    assert issue.profil_de_chaine_utilise is True
    assert issue.correction_appliquee is True
    # Et la correction a bel et bien ete posee : sans cela l'egalite des octets
    # comparerait deux passes brutes.
    assert issue.profil_de_chaine_utilise is True
    assert issue.correction_appliquee is True


def test_la_cible_du_lot_n_est_PAS_en_premiere_position(tmp_path) -> None:
    """Regle des fabriques, volet symetrique du banc lui-meme.

    La page de calibration du lot nominal est posee **en derniere** position du
    scan. Sans cette propriete, une recherche fautive qui rendrait la premiere
    page lue resterait verte partout dans ce fichier -- c'est le mutant `M25`
    de la story 5.7, avec 257 tests verts.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="ordre")
    assert len(sorted(dossier.glob("*.tiff"))) == 2
    _, detection, _ = _lot_detecte(tmp_path / "projet-ordre", dossier)

    lus = [(page.read_rank, page.payload["page_index"])
           for page in detection.pages if page.payload is not None]
    assert len(lus) == 2, lus
    # La cible -- `page_index` 0 -- est lue en SECONDE position : `read_rank` et
    # `page_index` ne coincident pas, donc un appariement par rang se demasque.
    assert [index for _rang, index in lus] == [1, 0], lus
    # Et les deux planches sont distinguables par leur emplacement de depart :
    # un remplissage uniforme cacherait toute permutation.
    departs = [page.payload["slots"][0]["frame_timecode"]
               for page in detection.pages if page.payload is not None]
    assert len(set(departs)) == 2, departs


# ---------------------------------------------------------------------------
# 2 -- l'ordre d'EPIC5-ARB-34, mesure a l'ARRIVEE et a l'EXECUTION
# ---------------------------------------------------------------------------


def test_l_ordre_conflits_frames_manifest_est_PRESERVE_apres_extraction(
        tmp_path, monkeypatch) -> None:
    """`EPIC5-ARB-34` : « un refus qui arrive apres une destruction n'est pas un refus. »

    L'ordre a voyage avec le corps, et il est mesure **a l'arrivee** : sur le
    point d'entree de coeur, pas sur la CLI. La mesure porte sur le chemin
    reellement pris (trois espions qui relaient), et non sur les numeros de
    ligne -- ceux-la sont deja verrouilles par `test_scan_manifest.py`, et un
    ordre de lignes juste ne dit rien d'un appel devenu conditionnel.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="ordre-arb34")
    projet = tmp_path / "projet-ordre-arb34"

    trace: list[str] = []
    for module, nom in ((scan_manifest, "check_scan_conflicts"),
                        (scan_write.scan_output_frames, "write_lot_output_frames"),
                        (scan_manifest, "persist_scan")):
        vrai = getattr(module, nom)

        def espion(*args, _vrai=vrai, _nom=nom, **kwargs):
            trace.append(_nom)
            return _vrai(*args, **kwargs)

        monkeypatch.setattr(module, nom, espion)

    _ecrire_par_le_coeur(projet, dossier)

    assert trace == ["check_scan_conflicts", "write_lot_output_frames",
                     "persist_scan"], trace


def test_un_refus_de_conflit_n_ecrit_AUCUNE_frame(tmp_path, capsys) -> None:
    """La moitie fonctionnelle du meme arbitrage : le refus tombe AVANT le disque.

    Un ordre juste sur trois espions ne dit rien si l'ecriture avait deja eu
    lieu quand le refus tombe. Ici le refus est reel -- le lot est deja au
    manifest et `overwrite` n'est pas demande --, et ce qui est mesure est
    qu'aucune frame de la seconde passe n'a atteint le disque.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="conflit")
    projet = tmp_path / "projet-conflit"
    _ecrire_par_le_coeur(projet, dossier)
    avant = _frames_ecrites(projet)
    assert avant

    dossier2 = _lot_de_deux_planches(tmp_path, nom="conflit-2")
    capsys.readouterr()
    with pytest.raises(Exception) as capture:
        _ecrire_par_le_coeur(projet, dossier2)

    # Le refus est bien celui de la garde prealable, et il porte un code de
    # sortie connu de la table du coeur.
    assert scan_write.code_de_sortie(capture.value) == scan_write.CODE_ERREUR
    assert _frames_ecrites(projet) == avant
    # **Le chemin de REFUS est muet lui aussi.** Trou mesure par injection
    # ciblee : `test_le_point_d_entree_de_coeur_n_imprime_RIEN` ne deroule que
    # le chemin nominal, donc un `print` pose sur un `except` y survivait.
    refuse = capsys.readouterr()
    assert refuse.out == "", refuse.out
    assert refuse.err == "", refuse.err


# ---------------------------------------------------------------------------
# 3 -- le contrat de producteur de coeur
# ---------------------------------------------------------------------------


def test_le_point_d_entree_de_coeur_n_imprime_RIEN(tmp_path, capsys) -> None:
    """AC 1.1 : aucun `print`, ni sur `stdout` ni sur `stderr`.

    Une interface branchee dessus recevrait sinon des lignes **sous** l'ecran
    dessine (`tui/palier_projet.py:9-12`). Le journal, lui, reste permis : il
    part dans un fichier ou un `logging.Handler`, jamais sur le terminal a
    l'insu de l'appelant.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="muet")
    projet = tmp_path / "projet-muet"
    capsys.readouterr()

    issue = _ecrire_par_le_coeur(projet, dossier)

    capture = capsys.readouterr()
    assert capture.out == "", capture.out
    assert capture.err == "", capture.err
    # Temoin positif : la passe a bel et bien ecrit, donc le silence n'est pas
    # celui d'une passe qui n'a rien fait.
    assert issue.output.written_frame_count == 8
    # Et elle ne rend pas un code de sortie deguise en objet.
    assert isinstance(issue, scan_write.EcritureDuLot)
    assert not isinstance(issue, int)


def test_l_enveloppeur_de_la_cli_rend_LES_MEMES_codes_et_LE_MEME_message(
        tmp_path, capsys) -> None:
    """AC 1.3 et AC 10.1 : `scan` rend `0` puis `1`, et le motif est celui du coeur.

    Le motif imprime est le `str` de l'exception levee par le coeur, prefixe et
    jamais reecrit : c'est le meme texte que la TUI affichera, deux lecteurs,
    une seule redaction.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="codes")
    projet = tmp_path / "projet-codes"
    assert app.run_scan(projet, dossier) == 0
    capsys.readouterr()

    dossier2 = _lot_de_deux_planches(tmp_path, nom="codes-2")
    assert app.run_scan(projet, dossier2) == 1
    erreur = capsys.readouterr().err
    # La ligne du refus, pas la derniere du flux: le journal de la passe part
    # sur le meme flux et le rapport de tri s'ecrit apres le refus du lot.
    refus = [ligne for ligne in erreur.splitlines()
             if ligne.startswith("Erreur: ")]
    assert len(refus) == 1, erreur
    (derniere,) = refus

    # Le meme refus, leve par le coeur : le message de la CLI est le motif du
    # coeur prefixe, pas une seconde redaction.
    dossier3 = _lot_de_deux_planches(tmp_path, nom="codes-3")
    with pytest.raises(Exception) as capture:
        _ecrire_par_le_coeur(projet, dossier3)
    assert derniere == f"Erreur: {capture.value}"


def test_ce_que_la_table_ne_nomme_PAS_remonte(tmp_path) -> None:
    """Un bug de programmation ne sort pas deguise en refus metier.

    La table `CODES_DE_SORTIE` rend `None` pour ce qu'elle ne nomme pas, et
    l'enveloppeur **relaie** alors -- c'est ce que faisait deja la pile
    d'`except` nommee qu'elle remplace. `OSError` et `KeyboardInterrupt` en
    font partie : les deux sont traitees par les gardes `AR2` de chaque
    commande, qui portent leur propre message.
    """
    assert scan_write.code_de_sortie(RuntimeError("bug")) is None
    assert scan_write.code_de_sortie(OSError("disque plein")) is None
    assert scan_write.code_de_sortie(KeyboardInterrupt()) is None
    # Et ce qu'elle nomme rend bien `1`, sur les cinq familles.
    for classe in (scan_ingest.ScanIngestError,
                   scan_write.scan_output_frames.ScanOutputError,
                   scan_write.ExtractionPersistenceError,
                   scan_write.ReconstructionError):
        assert scan_write.code_de_sortie(classe("motif")) == 1, classe


# ---------------------------------------------------------------------------
# 4 -- l'invite de correction est un PARAMETRE
# ---------------------------------------------------------------------------


def test_l_invite_n_est_posee_QUE_lorsqu_une_correction_existe(tmp_path) -> None:
    """AC 2.1 : le rappel n'est appele que dans le regime ou l'invite avait un sens.

    Posee plus tot, la question demanderait a un humain de trancher sur une
    correction que le lot n'a pas -- une question dont aucune reponse ne change
    rien, et qui apprend a repondre sans lire (AC 5 de 5.23).
    """
    # (a) aucun profil designe : rien a appliquer, donc aucune question.
    sans = _lot_de_deux_planches(tmp_path, nom="sans-correction")
    poses: list[int] = []
    _ecrire_par_le_coeur(
        tmp_path / "projet-sans", sans,
        demander_l_application_de_la_correction=lambda: poses.append(1) or True)
    assert poses == [], "aucune correction disponible: aucune question"

    # (b) un profil designe : la question est posee, une fois.
    avec = _lot_de_deux_planches(tmp_path, nom="avec-correction")
    poses.clear()
    _ecrire_par_le_coeur(
        tmp_path / "projet-avec", avec,
        profil_designe=_profil_designe(tmp_path),
        demander_l_application_de_la_correction=lambda: poses.append(1) or True)
    assert poses == [1], "une correction existe: la question est posee une fois"


def test_un_refus_de_correction_redescend_DANS_l_objet_de_correction(
        tmp_path) -> None:
    """`EPIC5-ARB-78` : « deux emplacements pour le meme fait, ce sont deux verites. »

    Sans ce report, un refus a l'invite laissait les frames non corrigees -- ce
    qui est correct -- mais laissait le document declarer qu'une correction
    avait ete **demandee**, donc perdait le seul motif lisible.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="refus-invite")
    issue = _ecrire_par_le_coeur(
        tmp_path / "projet-refus", dossier,
        profil_designe=_profil_designe(tmp_path),
        demander_l_application_de_la_correction=lambda: False)

    assert issue.correction_appliquee is False
    assert issue.lot_correction is not None
    assert issue.lot_correction.correction_requested is False
    # Temoin symetrique, sur le meme lot : sans refus, les deux sont vrais.
    dossier2 = _lot_de_deux_planches(tmp_path, nom="accord-invite")
    accepte = _ecrire_par_le_coeur(tmp_path / "projet-accord", dossier2,
                                   profil_designe=_profil_designe(tmp_path))
    assert accepte.correction_appliquee is True
    assert accepte.lot_correction.correction_requested is True


def test_le_defaut_SANS_rappel_est_appliquer(tmp_path) -> None:
    """AC 2.2, regime 2 : hors terminal, aucune invite et le defaut est appliquer.

    `None` vaut « personne pour repondre », et c'est le regime des scripts, de
    la CI et de cette suite. Une invite qui bloque un script est une panne, pas
    une precaution.
    """
    dossier = _lot_de_deux_planches(tmp_path, nom="sans-rappel")
    issue = _ecrire_par_le_coeur(tmp_path / "projet-sans-rappel", dossier,
                                 profil_designe=_profil_designe(tmp_path))
    assert issue.correction_appliquee is True
    assert issue.lot_correction is not None
    assert issue.lot_correction.correction_requested is True


def test_le_drapeau_explicite_COUPE_l_invite(tmp_path) -> None:
    """AC 2.2, regime 1 : l'operateur qui a tape le drapeau a deja repondu."""
    dossier = _lot_de_deux_planches(tmp_path, nom="drapeau")
    poses: list[int] = []
    issue = _ecrire_par_le_coeur(
        tmp_path / "projet-drapeau", dossier,
        profil_designe=_profil_designe(tmp_path),
        appliquer_la_correction=False,
        demander_l_application_de_la_correction=lambda: poses.append(1) or True)
    assert poses == []
    assert issue.correction_appliquee is False

    # Meme chose pour `--garder-le-scan-brut`, l'autre geste explicite.
    dossier2 = _lot_de_deux_planches(tmp_path, nom="brut")
    poses.clear()
    brut = _ecrire_par_le_coeur(
        tmp_path / "projet-brut", dossier2,
        profil_designe=_profil_designe(tmp_path),
        livrer_brut=True,
        demander_l_application_de_la_correction=lambda: poses.append(1) or True)
    assert poses == []
    assert brut.correction_appliquee is False


# ---------------------------------------------------------------------------
# 5 -- la moitie HAUTE du temps 2 (story 11.6, lot B, `EPIC11-ARB-129`)
#
# Le temps 2 n'avait AUCUN point d'entree de coeur : lecture du document de
# detection, refus nommes, condensat des octets, annonce de completude,
# adaptateurs et refus a zero page vivaient dans `cli.scan_write_command`, que
# la TUI a interdiction d'importer. Cette section mesure le corps a son
# arrivee : les refus, leur ordre, ce qu'aucun d'eux n'ecrit, et le contrat de
# producteur.
# ---------------------------------------------------------------------------

#: **La fabrique du temps 2 porte TROIS planches, et la cible est AU MILIEU de
#: la liste que le code PARCOURT** (`CLAUDE.md`, points 2 et 2 bis).
#:
#: Le code parcourt `document.pages`, ordonne par **rang de lecture**, et pas
#: la liste des `page_index`. Les trois planches sont donc posees sur la vitre
#: dans un ordre qui dissocie les deux : la planche `page_index=0` est lue en
#: **second**. Une cible en premiere position laisserait passer un `find`
#: fautif ; en derniere, un `continue` devenu `break` -- c'est le mutant paye
#: trois fois par la 11.4b. Le test :func:`test_la_cible_de_la_fabrique_est_AU_MILIEU`
#: verifie la position **sur la liste reellement parcourue**, jamais sur celle
#: que la fabrique ecrit.
RANG_DE_LA_CIBLE = 1


def _lot_de_trois_planches(tmp_path: Path, *, nom: str) -> Path:
    """Trois planches DISTINGUABLES, la cible en position du milieu."""
    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)
    return app.write_scan_folder(
        tmp_path / nom,
        [(payloads[2], app.PRESSES_DU_TIRAGE[0]),
         (payloads[0], app.PRESSES_DU_TIRAGE[1]),
         (payloads[1], app.PRESSES_DU_TIRAGE[0])])


def _projet_detecte(tmp_path: Path, *, nom: str = "temps2") -> tuple[Path, Path]:
    """Un projet dont la detection est **persistee**, et le chemin du document.

    C'est l'etat exact d'ou part le temps 2 : `scan detect` a tourne, le
    document est sur le disque, et rien n'a ete ecrit.
    """
    dossier = _lot_de_trois_planches(tmp_path, nom=f"scan-{nom}")
    projet = tmp_path / f"projet-{nom}"
    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier),
        "--dpi", str(app.DPI), "--lot-slug", "lot",
        cli.SCAN_DETECT_SUBCOMMAND]) == 0
    documents = sorted((projet / project_layout.SCANS_DIRNAME / "lot" / "detections").glob("*.json"))
    assert len(documents) == 1, documents
    return projet, documents[0]


def _oublier_les_page_index(noeud) -> None:
    """Mettre a `None` **tous** les `page_index` du sous-arbre.

    Le lecteur de `scan_previz` refuse un document ou l'adresse d'un marqueur
    contredit son porteur : une planche mutique doit l'etre partout a la fois.
    """
    if isinstance(noeud, dict):
        if "page_index" in noeud:
            noeud["page_index"] = None
        for valeur in noeud.values():
            _oublier_les_page_index(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            _oublier_les_page_index(valeur)


def _document_sans_etat_detected(brut: dict) -> None:
    """Un document `reconstructed` **valide** -- pas un document corrompu.

    Les quatre champs sont poses parce que le lecteur de `scan_previz` refuse
    d'abord un `reconstructed` incoherent : sans eux, la mesure tomberait sur
    le refus `pas-une-previz-de-scan` et ne mesurerait pas la garde d'etat.
    """
    brut["state"] = "reconstructed"
    brut["counters"]["frames_written"] = 12
    brut["counters"]["frames_expected"] = 12
    brut["counters"]["synthetic_frame_count"] = 0
    brut["subject"]["output_dir_relative"] = f"{project_layout.SCAN_FRAMES_DIRNAME}/rush-001_5"


def _document_anterieur_a_5_26(brut: dict) -> None:
    """La page **du milieu** perd son condensat de source (cle OMISE, pas nulle)."""
    del brut["pages"][RANG_DE_LA_CIBLE]["source_digest"]


def _document_sans_payload_verbatim(brut: dict) -> None:
    """La page **du milieu** garde son `page_index` et perd son payload.

    **La SECONDE moitie de la garde des documents anterieurs a 5.26**, et elle
    se mesure a part : le refus tombe sur `source_digest is None` **ou** sur
    « une page identifiee sans payload verbatim ». Un mutant qui reduisait la
    garde a sa premiere moitie a **survecu** a la campagne du lot B tant que ce
    scenario n'existait pas -- un document ou une page identifiee a perdu son
    payload serait alors passe jusqu'a la moitie aval, qui n'aurait pas de quoi
    retrouver ses timecodes (`timecode_base_fps` ne vit nulle part ailleurs).
    """
    del brut["pages"][RANG_DE_LA_CIBLE]["payload"]


def _document_sans_aucune_page_identifiee(brut: dict) -> None:
    """Aucune planche n'a livre son QR : ni payload, ni `page_index`."""
    for page in brut["pages"]:
        page.pop("payload", None)
        _oublier_les_page_index(page)


#: **Les huit scenarios de refus, un par motif de la table publiee.** Chacun est
#: le plus petit ecart qui l'atteigne, et il porte sur la planche **du milieu**
#: quand il porte sur une planche.
#:
#: `transformation` edite le document JSON ; `sabotage` edite le projet sur le
#: disque ; `chemin` remplace le chemin passe au point d'entree.
SCENARIOS_DE_REFUS: tuple[tuple[str, object, object, object], ...] = (
    (scan_write.REFUS_DOCUMENT_INTROUVABLE, None, None,
     lambda projet, document: projet / "aucun-document.json"),
    (scan_write.REFUS_DOCUMENT_JSON_INVALIDE, None,
     lambda projet, document: document.write_text("{ pas du json",
                                                  encoding="utf-8"), None),
    (scan_write.REFUS_DOCUMENT_PAS_UNE_PREVIZ_DE_SCAN,
     lambda brut: brut.__setitem__("kind", "extraction"), None, None),
    (scan_write.REFUS_DOCUMENT_ETAT_INATTENDU, _document_sans_etat_detected,
     None, None),
    (scan_write.REFUS_DOCUMENT_ANTERIEUR, _document_anterieur_a_5_26, None,
     None),
    # Le MEME motif par l'autre moitie de la garde : la table nomme un refus,
    # pas un chemin, et les deux moities doivent y mener.
    (scan_write.REFUS_DOCUMENT_ANTERIEUR, _document_sans_payload_verbatim,
     None, None),
    (scan_write.REFUS_SOURCE_MANQUANTE, None,
     lambda projet, document: (projet / project_layout.SCANS_DIRNAME / "lot"
                               / "page_02.tiff").unlink(), None),
    (scan_write.REFUS_SOURCE_CONDENSAT_DIVERGENT, None,
     lambda projet, document: (projet / project_layout.SCANS_DIRNAME / "lot" / "page_02.tiff")
     .write_bytes((projet / project_layout.SCANS_DIRNAME / "lot" / "page_01.tiff").read_bytes()),
     None),
    (scan_write.REFUS_DOCUMENT_SANS_PAGE_IDENTIFIEE,
     _document_sans_aucune_page_identifiee, None, None),
)


def _refuser(tmp_path: Path, motif: str, transformation, sabotage, chemin,
             **surcharges):
    """Monter le scenario de `motif` et rendre (projet, document, exception)."""
    projet, document = _projet_detecte(tmp_path, nom=motif)
    if transformation is not None:
        brut = json.loads(document.read_text(encoding="utf-8"))
        transformation(brut)
        document.write_text(json.dumps(brut), encoding="utf-8")
    if sabotage is not None:
        sabotage(projet, document)
    vise = document if chemin is None else chemin(projet, document)
    with pytest.raises(scan_write.RefusDuDocumentDeDetection) as leve:
        scan_write.ecrire_depuis_le_document(projet, vise, **surcharges)
    return projet, document, leve.value


@pytest.mark.parametrize(
    "motif,transformation,sabotage,chemin", SCENARIOS_DE_REFUS,
    ids=[f"{scenario[0]}-{rang}"
         for rang, scenario in enumerate(SCENARIOS_DE_REFUS)])
def test_chaque_scenario_leve_SON_refus_nomme(tmp_path, motif, transformation,
                                              sabotage, chemin) -> None:
    """AC 2.3 : le motif est **teste**, jamais devine sur un bout de phrase.

    Parametre un a un plutot qu'en un seul balayage : un echec dit **quel**
    refus s'est mis a en rendre un autre, et un refus qui absorberait son
    voisin ne peut pas se cacher derriere le silence des sept autres.
    """
    _projet, _document, refus = _refuser(tmp_path, motif, transformation,
                                         sabotage, chemin)
    assert refus.motif == motif, str(refus)
    # Le message reste ce qu'un terminal imprime, et il n'est pas vide : le
    # motif ne le remplace pas, il l'accompagne.
    assert str(refus).strip(), motif


def test_les_refus_du_document_sont_EXACTEMENT_ceux_de_la_table(tmp_path) -> None:
    """AC 2.3, en ensemble **EXACT** et dans les deux sens.

    « Une assertion positive laisse passer toute divergence supplementaire »
    (`CLAUDE.md`) : « ce motif est leve » ne mesure rien, « l'ensemble des
    motifs atteignables est **exactement** celui que la table publie » mesure la
    table ET son unicite. Un motif publie qu'aucun chemin n'atteint est un reste
    inerte ; un refus atteignable qui n'est pas dans la table est un refus
    qu'aucune interface ne saura nommer.
    """
    atteints = set()
    for rang, (motif, transformation, sabotage, chemin) in enumerate(
            SCENARIOS_DE_REFUS):
        _projet, _document, refus = _refuser(tmp_path, f"{motif}-{rang}",
                                             transformation, sabotage, chemin)
        atteints.add(refus.motif)
    assert atteints == set(scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT)
    # Neuf scenarios pour huit motifs : `document-anterieur` a DEUX chemins,
    # et les deux sont exerces -- la garde est une disjonction, et une
    # disjonction dont une moitie n'est jamais atteinte se laisse retirer sans
    # qu'un test ne bouge (mutant `M06` de la campagne du lot B, survivant
    # jusqu'a ce que ce scenario existe).
    assert len(SCENARIOS_DE_REFUS) == 9
    # Temoin de cardinal : la table ne s'est pas videe sous la mesure.
    assert len(scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT) == 8
    # Et les huit sont **distincts** : une table qui repeterait un nom
    # satisferait l'egalite d'ensembles ci-dessus.
    assert len(set(scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT)) == 8
    # Les cinq refus de la LECTURE sont le prefixe de la table, jamais une
    # seconde liste tenue a la main.
    assert (scan_write.MOTIFS_DE_REFUS_A_LA_LECTURE
            == scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT[:5])


def test_l_ordre_des_gardes_d_ARB_34_a_voyage_avec_le_corps(tmp_path) -> None:
    """AC 2.4 : « un refus qui arrive apres une destruction n'est pas un refus ».

    Mesure sur des documents qui violent **deux** gardes a la fois : c'est le
    seul montage ou l'ordre se voit. Un document dont l'etat est mauvais ET dont
    une source a disparu doit rendre le refus d'ETAT -- s'il rendait celui de
    condensat, c'est que la lecture serait passee apres.
    """
    # Garde 1 (lecture) avant garde 2 (condensat des sources).
    _projet, _doc, refus = _refuser(
        tmp_path, "ordre-etat-avant-source", _document_sans_etat_detected,
        lambda projet, document: (projet / project_layout.SCANS_DIRNAME / "lot"
                                  / "page_02.tiff").unlink(), None)
    assert refus.motif == scan_write.REFUS_DOCUMENT_ETAT_INATTENDU, str(refus)

    # Garde 2 (condensat) avant garde 4 (document a zero page identifiee).
    _projet, _doc, refus = _refuser(
        tmp_path, "ordre-source-avant-zero-page",
        _document_sans_aucune_page_identifiee,
        lambda projet, document: (projet / project_layout.SCANS_DIRNAME / "lot"
                                  / "page_02.tiff").unlink(), None)
    assert refus.motif == scan_write.REFUS_SOURCE_MANQUANTE, str(refus)


def test_l_annonce_de_completude_precede_le_refus_a_zero_page(tmp_path) -> None:
    """AC 2.4, garde 3 : l'annonce **precede** le dernier refus.

    C'est l'ordre que la CLI imprimait, et il n'est pas cosmetique : un lot
    troue voit sa completude annoncee avant que quoi que ce soit ne soit
    refuse. Si l'annonce passait apres, l'operateur lirait un refus sans savoir
    ce que le document disait.
    """
    dites = []
    _projet, _doc, refus = _refuser(
        tmp_path, "annonce-avant-refus", _document_sans_aucune_page_identifiee,
        None, None, annoncer_la_completude=dites.append)
    assert refus.motif == scan_write.REFUS_DOCUMENT_SANS_PAGE_IDENTIFIEE
    assert len(dites) == 1, dites
    assert "Completude du lot" in dites[0], dites
    # Et l'annonce dit bien ce que le document porte : **zero** page
    # identifiee sur trois attendues, les trois nommees comme manquantes.
    assert "0 page(s) identifiee(s) sur 3 attendue(s)" in dites[0], dites
    assert "0, 1, 2" in dites[0], dites


def test_le_condensat_des_sources_precede_l_ANNONCE_de_completude(
        tmp_path) -> None:
    """AC 2.4, la paire (garde 2, garde 3) -- **le pan que personne ne mesurait**.

    Les deux tests voisins mesurent (lecture, condensat) et (annonce, refus a
    zero page). La paire du milieu ne l'etait par personne : deplacer
    :func:`scan_write.verifier_les_condensats_des_sources` **apres** le bloc
    d'annonce laissait le banc de coeur entier vert -- mutant d'ordre survivant
    sur les 33 tests de ce fichier.

    Le regime ou l'inversion mord : un document dont une source a disparu.
    L'operateur lirait alors une **annonce de completude derivee d'octets non
    verifies** -- « ce lot est complet, 3 pages sur 3 » -- avant le refus qui
    dit que l'une de ces pages n'existe plus. C'est litteralement
    `EPIC5-ARB-34` : « un refus qui arrive apres une destruction n'est pas un
    refus, c'est un constat de deces ».

    **L'assertion qui mesure l'ordre est `dites == []`**, pas le motif du refus.
    Le motif reste `source-manquante` des deux cotes de l'inversion -- le refus
    finit toujours par tomber --, et c'est precisement pour cela qu'un test qui
    ne regarderait que lui serait inerte ici.
    """
    dites: list[str] = []
    _projet, _doc, refus = _refuser(
        tmp_path, "condensat-avant-annonce", None,
        lambda projet, document: (projet / project_layout.SCANS_DIRNAME / "lot"
                                  / "page_02.tiff").unlink(), None,
        annoncer_la_completude=dites.append)
    assert refus.motif == scan_write.REFUS_SOURCE_MANQUANTE, str(refus)
    assert dites == [], (
        "la completude a ete annoncee AVANT que les octets des sources ne "
        "soient verifies : l'ordre d'EPIC5-ARB-34 est rompu")


def test_aucun_refus_n_ecrit_de_frame_ni_ne_TOUCHE_le_document(tmp_path) -> None:
    """AC 2.4 et AC 5.5 : zero ecriture, et le document reste **intact**.

    **Un condensat ne prouverait rien ici** (`CLAUDE.md`, vague 3) : la fixture
    est deterministe, donc une reecriture rendrait exactement les memes octets.
    La mesure porte sur l'**inode**, sur `st_mtime_ns`, et sur un **temoin**
    depose dans le dossier des detections -- un dossier reecrit perdrait le
    temoin, quel que soit le contenu des fichiers qu'il porte.
    """
    for rang, (motif, transformation, sabotage, chemin) in enumerate(
            SCENARIOS_DE_REFUS):
        projet, document = _projet_detecte(tmp_path,
                                           nom=f"intact-{motif}-{rang}")
        if transformation is not None:
            brut = json.loads(document.read_text(encoding="utf-8"))
            transformation(brut)
            document.write_text(json.dumps(brut), encoding="utf-8")
        if sabotage is not None:
            sabotage(projet, document)
        temoin = document.parent / "temoin.txt"
        temoin.write_text("depose avant le refus", encoding="utf-8")
        avant = document.stat()
        vise = document if chemin is None else chemin(projet, document)

        with pytest.raises(scan_write.RefusDuDocumentDeDetection):
            scan_write.ecrire_depuis_le_document(projet, vise)

        apres = document.stat()
        assert apres.st_ino == avant.st_ino, motif
        assert apres.st_mtime_ns == avant.st_mtime_ns, motif
        assert temoin.is_file(), motif
        assert temoin.read_text(encoding="utf-8") == "depose avant le refus"
        # Zero frame, et le dossier de sortie n'existe meme pas.
        sorties = projet / project_layout.SCAN_FRAMES_DIRNAME
        assert list(sorties.rglob("*.tiff")) == [] if sorties.exists() else True


def test_la_cible_de_la_fabrique_est_AU_MILIEU_de_la_liste_PARCOURUE(
        tmp_path) -> None:
    """Regle des fabriques, points 2 et 2 bis, verifiee la ou ca compte.

    La position se verifie **sur la liste que le code parcourt** --
    `document.pages`, ordonnee par rang de lecture --, jamais sur celle que la
    fabrique ecrit. C'est litteralement la cause instrumentee du mutant
    `continue` -> `break` de la 11.4b : une fixture **croyait** respecter le
    point 2 bis alors que l'ordre de la liste iteree n'etait pas celui des
    `page_index`.
    """
    _projet, document = _projet_detecte(tmp_path, nom="fabrique")
    lu = scan_write.lire_le_document_de_detection(document)
    pages = lu.document.pages
    # Trois elements, pas deux : a deux, « au milieu » et « en dernier » sont
    # indiscernables, et un `break` fautif passerait.
    assert len(pages) == 3, [page.read_rank for page in pages]
    # La cible est celle du milieu de la liste PARCOURUE...
    cible = pages[RANG_DE_LA_CIBLE]
    assert cible.read_rank == RANG_DE_LA_CIBLE
    assert cible.source_path_relative.endswith("page_02.tiff")
    # ... et son `page_index` n'est PAS son rang de lecture : les deux ordres
    # sont dissocies, donc un appariement par position se voit.
    assert cible.page_index == 0
    assert [page.page_index for page in pages] == [2, 0, 1]
    # Les trois sources sont distinctes : une fabrique qui poserait trois fois
    # la meme planche rendrait toute permutation invisible.
    assert len({page.source_digest for page in pages}) == 3


def test_le_temps_2_ecrit_les_MEMES_artefacts_que_la_CLI(tmp_path) -> None:
    """AC 2.2 et AC 2.5 : corps **deplace**, pas reecrit -- mesure sur les TIFF.

    Une seconde redaction du geste divergerait, et l'ecart ne se verrait que
    sur les octets produits : c'est donc sur eux que la mesure porte, plus
    l'entree de lot du manifest.
    """
    projet_cli, document_cli = _projet_detecte(tmp_path, nom="cli")
    projet_coeur, document_coeur = _projet_detecte(tmp_path, nom="coeur")

    assert cli.main([cli.SCAN_WRITE_COMMAND, "--project", str(projet_cli),
                     "--detection", str(document_cli)]) == 0
    issue = scan_write.ecrire_depuis_le_document(projet_coeur, document_coeur)

    par_la_cli = _frames_ecrites(projet_cli)
    par_le_coeur = _frames_ecrites(projet_coeur)
    # Temoin : les deux passes ont produit de la matiere -- douze frames, trois
    # planches de quatre. Un ecrivain qui poserait douze fois le meme raster
    # passerait l'egalite ci-dessous sans ce temoin.
    assert len(par_la_cli) == 12, sorted(par_la_cli)
    assert par_le_coeur == par_la_cli
    # **Huit rasters distincts et non douze, et c'est mesure plutot que
    # suppose** : le depot ne fabrique que DEUX presses de tirage
    # (`app.PRESSES_DU_TIRAGE`), donc la premiere et la troisieme planche
    # partagent la leur. Ce qui compte pour la regle des fabriques est que la
    # **cible** -- la planche du milieu, seule sous la seconde presse -- soit
    # distinguable des deux autres : ses quatre frames n'apparaissent qu'une
    # fois chacune dans tout le lot. Une permutation qui la deplacerait se voit
    # donc sur les octets.
    assert len(set(par_le_coeur.values())) == 8, sorted(par_le_coeur)
    comptes = {}
    for condensat in par_le_coeur.values():
        comptes[condensat] = comptes.get(condensat, 0) + 1
    frames_de_la_cible = [
        condensat for nom, condensat in par_le_coeur.items()
        if any(timecode in nom for timecode in
               ("00-00-00-00", "00-00-01-00", "00-00-02-00", "00-00-03-00"))]
    assert len(frames_de_la_cible) == 4, sorted(par_le_coeur)
    assert all(comptes[condensat] == 1 for condensat in frames_de_la_cible), (
        "les frames de la planche du milieu doivent etre uniques dans le lot")
    assert _lot_du_manifest(projet_coeur) == _lot_du_manifest(projet_cli)
    # L'objet rendu porte le rapport que le compte rendu final lit.
    assert issue.rapport is not None
    assert len(issue.rapport.pages) == 3
    assert issue.rapport.scans_dir == "scans/lot"
    assert issue.rapport.ingest_slug == "lot"


def test_l_annonce_de_completude_est_un_rappel_OPTIONNEL_et_ACTIF(
        tmp_path, capsys) -> None:
    """`AR3` : optionnel, et son absence ne change **rien** a l'observable.

    Les **deux** regimes sont mesures, et le second mesure que le canal est
    **actif** -- pas seulement qu'il ne plante pas : « un rappel qui s'eteint en
    silence quand on lui passe le mauvais type n'est pas optionnel, il est
    casse ».
    """
    projet_muet, document_muet = _projet_detecte(tmp_path, nom="muet")
    projet_dit, document_dit = _projet_detecte(tmp_path, nom="dit")
    # Purger ce que `scan detect` a imprime en montant les deux fixtures : la
    # mesure qui suit porte sur ce que le COEUR ecrit, pas sur la CLI qui a
    # servi a poser le decor.
    capsys.readouterr()

    scan_write.ecrire_depuis_le_document(projet_muet, document_muet)
    # Regime 1 : aucun rappel. Le coeur n'ecrit rien sur le terminal -- c'est
    # la moitie observable de « ce module ne met en forme aucun message ».
    assert capsys.readouterr().out == ""

    dites = []
    scan_write.ecrire_depuis_le_document(projet_dit, document_dit,
                                         annoncer_la_completude=dites.append)
    # Regime 2 : le canal est ACTIF, une seule fois, avant l'ecriture.
    assert len(dites) == 1, dites
    assert dites[0] == scan_write.annonce_de_completude(
        scan_write.lire_le_document_de_detection(document_dit).document)
    assert "3 page(s) identifiee(s) sur 3 attendue(s), aucune manquante" in dites[0]
    # Et l'observable ne change pas d'un octet entre les deux regimes.
    assert _frames_ecrites(projet_dit) == _frames_ecrites(projet_muet)
    assert (_lot_du_manifest(projet_dit) == _lot_du_manifest(projet_muet))


def test_les_points_d_entree_du_temps_2_sont_des_PRODUCTEURS() -> None:
    """AC 2.1 : parametres nommes, aucun objet `args`, un objet de resultat.

    La frontiere qui interdit `print` et `stdin` sur ces modules vit dans
    `tests/unit/tui/test_frontiere_cli.py` : elle porte sur le **source**, donc
    sur tous les chemins. Celle-ci mesure l'autre moitie du contrat, sur la
    signature.
    """
    import inspect

    from mixed_media_utility import scan_calibrate

    for fonction, positionnels in (
            (scan_write.ecrire_depuis_le_document, 2),
            (scan_calibrate.calibrer_la_chaine, 2),
            (scan_calibrate.consigner_le_profil_de_chaine, 3)):
        parametres = list(inspect.signature(fonction).parameters.values())
        assert "args" not in {p.name for p in parametres}, fonction
        # Tout ce qui suit les positionnels est **nomme**: un appelant qui se
        # tromperait d'ordre ne peut pas passer un dpi pour un logger.
        for parametre in parametres[positionnels:]:
            assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, (
                fonction, parametre)
        # Aucun n'a de valeur de retour entiere annoncee: ce sont des faits,
        # jamais un code de sortie.
        assert inspect.signature(fonction).return_annotation is not int

    # Les rappels qui portaient une invite sont OPTIONNELS et valent `None`.
    for fonction, rappel in (
            (scan_write.ecrire_depuis_le_document, "annoncer_la_completude"),
            (scan_write.ecrire_depuis_le_document, "confirmer_l_ecrasement"),
            (scan_calibrate.calibrer_la_chaine,
             "demander_le_nom_et_le_commentaire"),
            (scan_calibrate.calibrer_la_chaine, "confirmer_l_ecrasement")):
        parametre = inspect.signature(fonction).parameters[rappel]
        assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, rappel
        assert parametre.default is None, rappel


def test_une_INTERFACE_atteint_le_temps_2_sans_importer_cli() -> None:
    """AC 2.7, mesure par un import REEL et non par lecture de source.

    C'est le blocage exact d'`EPIC11-ARB-67` : la TUI a interdiction d'importer
    `cli.py`, donc le point d'entree doit etre atteignable sans lui. Un
    sous-processus neuf est le seul montage qui le prouve -- dans celui du
    banc, `cli` est deja importe par les autres tests de ce fichier, et
    `sys.modules` ne dirait plus rien.
    """
    import subprocess

    programme = (
        "import sys\n"
        "from mixed_media_utility.tui import atelier_scan_parcours\n"
        "from mixed_media_utility import scan_write, scan_calibrate\n"
        "assert callable(scan_write.ecrire_depuis_le_document)\n"
        "assert callable(scan_calibrate.calibrer_la_chaine)\n"
        "charges = sorted(m for m in sys.modules\n"
        "                 if m.startswith('mixed_media_utility'))\n"
        "assert 'mixed_media_utility.cli' not in charges, charges\n"
        "print('ok')\n"
    )
    issue = subprocess.run(
        [sys.executable, "-c", programme], capture_output=True, text=True,
        cwd=str(REPO_ROOT), env={"PYTHONPATH": str(REPO_ROOT / "src"),
                                 "PATH": "/usr/bin:/bin"})
    assert issue.returncode == 0, issue.stderr
    assert issue.stdout.strip() == "ok", issue.stdout

    # Volet symetrique : le meme montage MORD quand `cli` est bel et bien
    # importe. Sans lui, un `sys.modules` devenu muet rendrait le test vert.
    fautif = subprocess.run(
        [sys.executable, "-c",
         "import sys\nfrom mixed_media_utility import cli\n"
         "assert 'mixed_media_utility.cli' not in sys.modules\n"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"})
    assert fautif.returncode != 0, fautif.stdout


def test_les_DEUX_dpi_sont_lus_DANS_le_document_et_ne_s_echangent_pas(
        tmp_path) -> None:
    """AC 1 de 5.26, mesuree sur un document ou les deux dpi DIVERGENT.

    « Le dpi de geometrie est lu dans le document (`scan_dpi_detection` : c'est
    lui qui a decide l'homographie et les zones), le manifest recoit
    `scan_dpi_declared` -- jamais une option qui pourrait diverger. » Sur la
    fixture nominale les deux valent 300, donc un ECHANGE des deux est
    **invisible** : c'est litteralement le mutant `M15` de la campagne du lot B,
    survivant tant que ce test n'existait pas. Le document est donc edite pour
    que les deux valeurs different.
    """
    projet, document = _projet_detecte(tmp_path, nom="dpi-divergents")
    brut = json.loads(document.read_text(encoding="utf-8"))
    # `scan_dpi_declared` seul bouge : c'est celui qui part au manifest. La
    # geometrie, elle, reste celle qui a decide l'homographie -- l'echanger
    # rejouerait le recadrage a une echelle qui n'est pas celle du raster.
    assert brut["subject"]["scan_dpi_detection"] == app.DPI
    brut["subject"]["scan_dpi_declared"] = 2 * app.DPI
    document.write_text(json.dumps(brut), encoding="utf-8")

    scan_write.ecrire_depuis_le_document(projet, document)

    manifest = json.loads(
        (projet / "project.json").read_text(encoding="utf-8"))
    assert manifest["reconstruction"]["scan"]["scan_dpi"] == 2 * app.DPI, (
        manifest["reconstruction"]["scan"])
    # Volet symetrique : le dpi de GEOMETRIE n'a pas suivi. S'il avait suivi,
    # le recadrage se serait rejoue a la mauvaise echelle et les frames
    # differeraient de celles de la passe nominale, octet pour octet.
    projet_nominal, document_nominal = _projet_detecte(tmp_path, nom="dpi-nominal")
    scan_write.ecrire_depuis_le_document(projet_nominal, document_nominal)
    assert _frames_ecrites(projet) == _frames_ecrites(projet_nominal)


def test_l_ecrasement_demande_atteint_la_moitie_aval(tmp_path) -> None:
    """`overwrite` est RELAYE verbatim, et son absence refuse.

    Les deux regimes, parce qu'un seul ne mesure rien : sans le refus, un
    `overwrite=True` code en dur passerait ; sans le succes, un
    `overwrite=False` code en dur passerait aussi. C'est le mutant `M17` de la
    campagne du lot B, survivant tant qu'aucun banc n'exercait `--overwrite`
    sur `scan-write` autrement que par la surface d'argparse.

    **C'est aussi le parametre par lequel la seconde issue d'`EPIC11-ARB-89`
    entrera** : quand `nouvelle_version=` arrivera sur la moitie aval a la
    liaison, il se branchera a cote de celui-ci, et ce banc est ce qui dira
    qu'il est relaye plutot que perdu.
    """
    projet, document = _projet_detecte(tmp_path, nom="ecrasement")
    scan_write.ecrire_depuis_le_document(projet, document)
    avant = _frames_ecrites(projet)
    assert len(avant) == 12

    # Sans `overwrite`, la moitie aval refuse et **rien n'est reecrit**.
    with pytest.raises(scan_output_frames.OutputFrameExistsError):
        scan_write.ecrire_depuis_le_document(projet, document)
    assert _frames_ecrites(projet) == avant

    # Avec `overwrite`, la passe aboutit et l'inventaire porte le constat.
    issue = scan_write.ecrire_depuis_le_document(projet, document,
                                                 overwrite=True)
    assert "OUTPUT_FRAME_OVERWRITTEN" in scan_write.inventaire_de_l_ecriture(
        issue)
    assert _frames_ecrites(projet) == avant


# ---------------------------------------------------------------------------
# 6 -- `scan calibrate` au coeur : les deux relais que seule une sonde mesure
#
# Les deux mutants `M24` et `M26` de la campagne du lot B ont survecu a 205
# tests de comportement, et pour la meme raison : ils portent sur une valeur
# **transmise** dont les fixtures du depot ne distinguent pas les deux
# versions. `confirm_overwrite` vaut `None` sous pytest de toute facon (aucun
# `stdin` interactif), et `read_scan_tags` rend `('', '', '')` sur un dossier de
# scan comme sur un dossier projet -- mesure faite, les trois captures reelles
# du depot ne portent aucun tag scanner (`scan_chain`, 2026-08-17). Un banc de
# comportement ne peut donc PAS les distinguer : c'est la sonde sur l'argument
# transmis qui les ferme, et elle est plus forte qu'une mesure d'observable.
# ---------------------------------------------------------------------------


def test_l_identite_de_chaine_se_derive_du_SCAN_et_jamais_du_PROJET(
        tmp_path, monkeypatch) -> None:
    """Mutant `M26` : le localisateur transmis est celui du **scan**.

    Les deux dossiers rendent les memes tags aujourd'hui -- aucune capture du
    depot ne porte les tags TIFF 271/272/305 --, donc l'echange est
    **silencieux** sur tout observable. Le jour ou un scanner tague ses
    fichiers, l'identite de chaine deviendrait celle du dossier projet : la
    meme pour toutes les chaines, c'est-a-dire un profil que plus aucun scan ne
    retrouve.
    """
    from mixed_media_utility import scan_calibrate

    vus = []

    def sonde(report, scan_locator, logger=None):
        vus.append(scan_locator)
        return None      # -> refus nomme, la passe s'arrete ici

    monkeypatch.setattr(scan_calibrate, "derive_chain_id", sonde)
    projet = tmp_path / "projet-calibrate"
    dossier = _lot_de_trois_planches(tmp_path, nom="scan-calibrate")
    project_layout.ensure_project_layout(projet)

    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate.calibrer_la_chaine(projet, dossier, dpi=app.DPI)

    assert leve.value.motif == scan_calibrate.REFUS_IDENTITE_NON_DERIVABLE
    assert vus == [dossier], vus
    # Volet symetrique : la sonde a bien vu passer autre chose que le projet.
    assert projet not in vus


def test_la_confirmation_d_ecrasement_de_profil_est_RELAYEE_verbatim(
        tmp_path, monkeypatch) -> None:
    """Mutant `M24` : `confirmer_l_ecrasement` atteint `write_profile`.

    Sous pytest, `stdin` n'est jamais un terminal, donc la CLI passe `None` et
    un mutant qui coderait `None` en dur est **indistinguable** de l'original
    sur tout observable -- 205 tests de comportement l'ont laisse passer. La
    sonde mesure la valeur **transmise**, la seule chose qui differe.

    Ce que le relais tient, et pourquoi il compte (`EPIC5-ARB-99`) : « hors
    terminal, le defaut est l'empreinte, jamais l'ecrasement ». Un rappel perdu
    ferait de l'empreinte differenciante le SEUL comportement possible, y
    compris pour l'operateur en terminal qui a demande a ecraser -- c'est-a-dire
    le blocage sec qu'`EPIC11-ARB-89` interdit.
    """
    from types import SimpleNamespace

    import test_scan_calibrate_command as calib
    from mixed_media_utility import scan_calibrate
    from mixed_media_utility.io import calibration_profile

    recus = {}

    def faux_write_profile(project_dir, document, *, confirm_overwrite=None):
        recus["confirm_overwrite"] = confirm_overwrite
        chemin = Path(project_dir) / project_layout.VERSIONS_DIRNAME / "calibration" / "profil.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{}", encoding="utf-8")
        return chemin

    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: calib._lot_correction_ajuste())
    monkeypatch.setattr(calibration_profile, "write_profile",
                        faux_write_profile)

    projet = tmp_path / "projet-ecrasement"
    dossier = _lot_de_trois_planches(tmp_path, nom="scan-ecrasement")
    project_layout.ensure_project_layout(projet)
    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=app.DPI)

    def sentinelle() -> bool:      # ce que la CLI passe en terminal
        return True

    # Une detection SUBSTITUEE, nommee plutot qu'un `object()` nu -- et elle
    # doit porter `pages`. Depuis le constat de terrain `D2` (2026-09-06),
    # `consigner_le_profil_de_chaine` lit la detection pour y chercher le
    # libelle de chaine imprime sur la page ; un `object()` y levait un
    # `AttributeError`. Le lot de ce banc ne porte AUCUNE page de calibration,
    # donc la liste vide est ce que la detection reelle rendrait, et la
    # precedence retombe sur le `chain_id` comme avant. Pas un contournement :
    # le meme substitut que `test_scan_calibrate_command.DETECTION_SUBSTITUEE`.
    detection = SimpleNamespace(pages=())

    consigne = scan_calibrate.consigner_le_profil_de_chaine(
        projet, rapport, detection, dpi=app.DPI, scan_locator=dossier,
        confirmer_l_ecrasement=sentinelle)

    # **Identite et non egalite** : c'est l'objet de l'appelant qui descend,
    # jamais un rappel reconstruit ici -- un enrobage se ferait passer pour un
    # relais sur une egalite.
    assert recus["confirm_overwrite"] is sentinelle
    assert consigne.profile_path.name == "profil.json"

    # Volet symetrique : sans rappel, c'est `None` qui descend, et pas la
    # sentinelle restee accrochee d'un appel precedent.
    recus.clear()
    projet_muet = tmp_path / "projet-muet"
    project_layout.ensure_project_layout(projet_muet)
    rapport_muet = scan_ingest.ingest_scan_lot(projet_muet, dossier,
                                               dpi=app.DPI)
    scan_calibrate.consigner_le_profil_de_chaine(
        projet_muet, rapport_muet, detection, dpi=app.DPI,
        scan_locator=dossier)
    assert recus["confirm_overwrite"] is None



# ===========================================================================
# Vague 4, couche 1 bis : `locator_page_index` sur une source MULTIPAGE
# ===========================================================================
#
# **Pourquoi cette fixture existe, et elle ferme une fabrique DEGENEREE.** La
# couche 1 bis a injecte `locator_page_index=page.source_page_index` ->
# `locator_page_index=None` dans `objets_consommables_du_document` : le mutant
# `M4` a **survecu a 134 verdicts**. Motif mesure : toutes les fixtures du
# temps 2 sont des TIFF **mono-page** (un fichier par planche), pour lesquels
# `source_page_index` vaut deja `None`. Le champ qui decide **de quelle page
# d'un PDF** les pixels d'une planche sont relus n'etait donc transporte que la
# ou sa valeur ne peut pas differer.
#
# Le regime n'est pas theorique : un scan livre en **un seul PDF multipage**
# est ce qu'un scanner a chargeur produit par defaut, et
# `verifier_les_condensats_des_sources` le documente explicitement en le gerant
# (« un condensat par chemin: deux pages du meme PDF partagent le meme
# fichier »). La fonction voisine le nommait, aucun banc du temps 2 ne le
# jouait.
#
# **Les DEUX mutants sont fermes ici, dont celui que la couche 1 bis n'avait
# pas pu injecter** :
#
# * `locator_page_index=None` -- la forme *bruyante* : `load_page_array`
#   tenterait de lire le PDF comme un fichier-image ;
# * `locator_page_index=page.page_index` -- la forme **silencieusement
#   fausse** : l'index de page du LOT au lieu de celui de la SOURCE. Elle rend
#   un raster **valide**, celui d'une autre planche du meme PDF, et les frames
#   ecrites portent alors le contenu de la mauvaise feuille. C'est pour elle
#   que la fixture dissocie les deux ordres et peint un temoin par page.

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

#: **La couleur temoin de chaque page du PDF, en BGR**, peinte par-dessus la
#: premiere zone de frame de la planche. Elles sont **maximalement separees**
#: pour survivre a la compression du PDF : c'est ce qui rend la mesure du
#: contenu decisive plutot qu'approchee.
TEMOINS_DES_PAGES_DU_PDF: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255), (0, 255, 0), (255, 0, 0))

#: Le rang de lecture de la page **cible** dans le PDF : celle du milieu.
#: `source_page_index` y vaut 1, et son `page_index` de lot vaut 0 -- les deux
#: ordres sont **dissocies**, sans quoi les deux mutants seraient
#: indiscernables l'un de l'autre et du code sain.
RANG_DE_LA_CIBLE_DU_PDF = 1


def _peindre_le_temoin(page, couleur_bgr) -> None:
    """Remplir la PREMIERE zone de frame de la planche d'une couleur unie."""
    zone = app.page_templates.get_template(
        "tpl-a4-portrait-4f-v2").frame_zones_mm[0]
    x0, y0 = app.page_templates.mm_to_px(zone["x"], zone["y"], app.DPI)
    x1, y1 = app.page_templates.mm_to_px(
        zone["x"] + zone["width"], zone["y"] + zone["height"], app.DPI)
    page[y0:y1, x0:x1] = np.asarray(couleur_bgr, dtype=np.uint8)


def _lot_en_UN_SEUL_PDF(tmp_path: Path, *, nom: str) -> Path:
    """Trois planches livrees en **un seul PDF**, et le chemin de ce PDF.

    Meme ordre de pose que `_lot_de_trois_planches` -- la cible (`page_index`
    de lot 0) est lue en **seconde** position --, donc `source_page_index` vaut
    1 la ou `page_index` vaut 0 : un transport qui confondrait les deux se voit.
    """
    payloads = app.lot_payloads(sheet_count=3, with_calibration=False)
    ordre = ((payloads[2], app.PRESSES_DU_TIRAGE[0]),
             (payloads[0], app.PRESSES_DU_TIRAGE[1]),
             (payloads[1], app.PRESSES_DU_TIRAGE[0]))
    rasters = []
    for rang, (payload, presse) in enumerate(ordre):
        page = app.build_page(payload, press=presse)
        _peindre_le_temoin(page, TEMOINS_DES_PAGES_DU_PDF[rang])
        # BGR -> RGB : Pillow ecrit du RGB, OpenCV peint du BGR.
        rasters.append(Image.fromarray(page[:, :, ::-1]))
    dossier = tmp_path / nom
    dossier.mkdir(parents=True, exist_ok=True)
    pdf = dossier / "planches.pdf"
    rasters[0].save(pdf, save_all=True, append_images=list(rasters[1:]),
                    resolution=app.DPI)
    return pdf


def _projet_detecte_depuis_un_PDF(tmp_path: Path, *,
                                  nom: str) -> tuple[Path, Path]:
    """Un projet dont la detection est persistee, **depuis un PDF multipage**."""
    pdf = _lot_en_UN_SEUL_PDF(tmp_path, nom=f"scan-{nom}")
    projet = tmp_path / f"projet-{nom}"
    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(pdf),
        "--dpi", str(app.DPI), "--lot-slug", "lot",
        cli.SCAN_DETECT_SUBCOMMAND]) == 0
    documents = sorted((projet / project_layout.SCANS_DIRNAME / "lot" / "detections").glob("*.json"))
    assert len(documents) == 1, documents
    return projet, documents[0]


def test_la_fixture_PDF_dissocie_bien_les_deux_index_de_page(tmp_path) -> None:
    """La fabrique elle-meme, mesuree avant ce qu'elle sert a mesurer.

    Sans cette verification, la fixture pourrait degenerer en silence -- trois
    pages dont `page_index` et `source_page_index` coincideraient -- et les
    deux tests suivants resteraient verts en ne mesurant plus rien. C'est
    exactement le defaut que `M4` a exploite pendant tout le temps 2.
    """
    _projet, document = _projet_detecte_depuis_un_PDF(tmp_path, nom="fabrique")
    pages = scan_write.lire_le_document_de_detection(document).document.pages
    # Trois elements, pas deux : a deux, « au milieu » et « en dernier » sont
    # indiscernables.
    assert len(pages) == 3, [page.read_rank for page in pages]
    # Les trois pages viennent du **meme fichier** -- c'est la propriete du PDF
    # multipage, celle que `verifier_les_condensats_des_sources` documente en
    # la gerant et qu'aucun banc du temps 2 ne jouait.
    assert len({page.source_path_relative for page in pages}) == 1
    assert pages[0].source_path_relative.endswith(".pdf")
    assert len({page.source_digest for page in pages}) == 1
    # Les index de page de la SOURCE sont distinguables et ordonnes...
    assert [page.source_page_index for page in pages] == [0, 1, 2]
    # ... et ils ne coincident PAS avec les `page_index` du LOT : c'est cette
    # dissociation qui rend visible un transport qui confondrait les deux.
    assert [page.page_index for page in pages] == [2, 0, 1]
    cible = pages[RANG_DE_LA_CIBLE_DU_PDF]
    assert cible.source_page_index == 1 and cible.page_index == 0


def test_locator_page_index_transporte_l_index_de_la_SOURCE(tmp_path) -> None:
    """L'appariement, mesure **par position sur la liste que le code parcourt**.

    `objets_consommables_du_document` transporte « champ par champ (`read_rank`
    ET `page_index`, jamais deduits l'un de l'autre) ». Le couple
    `locator_source` / `locator_page_index` decide **de quelle page d'un PDF**
    les pixels d'une planche sont relus : `scan_ingest.load_page_array` branche
    sur `locator.page_index is None` -- `None` lit un fichier-image, un entier
    rend la page N d'un PDF.

    La position est verifiee sur les tuples **rendus**, jamais par une
    recherche par `read_rank` : une recherche retrouverait la bonne page meme
    si l'ordre avait ete permute.
    """
    _projet, document = _projet_detecte_depuis_un_PDF(tmp_path, nom="adaptateur")
    lu = scan_write.lire_le_document_de_detection(document)
    rapport, detection, _payloads = scan_write.objets_consommables_du_document(
        lu.document)

    for pages_transportees in (rapport.pages, detection.pages):
        assert [page.locator_page_index for page in pages_transportees] == [0, 1, 2]
        assert [page.page_index for page in pages_transportees] == [2, 0, 1]
        cible = pages_transportees[RANG_DE_LA_CIBLE_DU_PDF]
        # La cible du milieu porte l'index de la SOURCE (1), pas celui du LOT
        # (0) : les deux mutants de la couche 1 bis meurent ici, et ils
        # meurent **differemment** l'un de l'autre.
        assert cible.locator_page_index == 1
        assert cible.locator_page_index != cible.page_index
        assert cible.locator_source.endswith(".pdf")
    # Et les deux vues transportent le MEME appariement : le rapport et la
    # detection descendent de la meme liste, une divergence entre eux ferait
    # relire une page pour une geometrie ajustee sur une autre.
    assert ([page.locator_page_index for page in rapport.pages]
            == [page.locator_page_index for page in detection.pages])


def _temoin_de_la_frame(chemin: Path):
    """La couleur moyenne du **coeur** d'une frame ecrite, en BGR.

    Le coeur (les 50 % centraux) et non la frame entiere : les bords portent
    l'interpolation du redressage, et un bord ne dit rien de la page dont les
    pixels viennent.
    """
    frame = np.asarray(Image.open(chemin).convert("RGB"))[:, :, ::-1]
    hauteur, largeur = frame.shape[:2]
    coeur = frame[hauteur // 4:3 * hauteur // 4, largeur // 4:3 * largeur // 4]
    return coeur.reshape(-1, 3).mean(axis=0)


def test_les_frames_d_un_PDF_viennent_de_LA_BONNE_page_du_PDF(tmp_path) -> None:
    """La mesure de contenu : le mutant *silencieusement faux* meurt sur les pixels.

    `locator_page_index=page.page_index` rend un raster parfaitement **valide**
    -- celui d'une autre planche du meme PDF --, et aucune garde ne le refuse :
    la geometrie vient de la detection de la bonne page, les timecodes du
    payload de la bonne page, et seuls **les pixels** sont ceux d'une autre
    feuille. C'est la panne qu'un operateur ne verrait qu'a l'oeil, sur la
    frame livree.

    La planche cible (`page_index` de lot 0, `source_page_index` 1) porte les
    slots 0 a 3, donc la frame de timecode `00:00:00:00`. Son temoin doit etre
    celui de la **seconde** page du PDF, et strictement plus proche de lui que
    des deux autres.
    """
    projet, document = _projet_detecte_depuis_un_PDF(tmp_path, nom="contenu")
    scan_write.ecrire_depuis_le_document(projet, document,
                                         appliquer_la_correction=False)
    frames = sorted((projet / project_layout.SCAN_FRAMES_DIRNAME).rglob("*.tiff"))
    assert len(frames) == 12, [chemin.name for chemin in frames]

    premiere, = [chemin for chemin in frames
                 if chemin.name.endswith("_00-00-00-00.tiff")]
    mesure = _temoin_de_la_frame(premiere)
    ecarts = [float(np.abs(mesure - np.asarray(temoin, dtype=np.float64)).max())
              for temoin in TEMOINS_DES_PAGES_DU_PDF]
    # Le plus proche est celui de la page du PDF que le `source_page_index` de
    # la cible designe -- et il l'est **strictement**, donc un raster venu
    # d'une autre page ne peut pas satisfaire l'assertion par tolerance.
    assert ecarts.index(min(ecarts)) == RANG_DE_LA_CIBLE_DU_PDF, ecarts
    assert min(ecarts) < 40.0, (mesure, ecarts)
    assert min(ecarts) * 3 < sorted(ecarts)[1], ecarts
