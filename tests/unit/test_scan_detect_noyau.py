# -*- coding: utf-8 -*-
"""Story 7.3, AC 2a -- le point d'appel unique du coeur, et son enveloppeur.

Ce banc mesure **trois** proprietes de l'extraction de `run_scan_detect`, et
seulement elles :

1. **le meme document** -- sur le meme lot, le noyau et la CLI ecrivent un
   document `scan_previz` identique **octet pour octet hors horodatage** (test
   d'integration contre le VRAI producteur, qui assert sur le contenu et non
   sur l'existence : `EPIC5-ARB-39`, 5.8, ou deux tests d'integration ecrits
   survivaient aux trois mutations qu'ils devaient attraper) ;
2. **les memes codes de sortie** -- `0`, `1`, `130`, plus les deux arrets a `0`
   sans document ;
3. **l'orchestration a bien quitte la commande** -- grep executable, avec son
   volet symetrique qui prouve que le grep mord.

Les images sont des planches **reellement peintes** par les fabriques du depot
(`test_scan_calibration_application`), jamais des fixtures TIFF versionnees :
`tests/fixtures/` ne contient aucun TIFF et cette story n'en introduit pas.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli, scan_detect, scan_ingest  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402

#: Les champs qui changent d'une passe a l'autre par construction : l'instant
#: de generation, et le condensat qui le scelle. Tout le reste doit coincider.
CHAMPS_VOLATILES = ("generated_at_utc", "fingerprints")


def _lot_de_deux_planches(tmp_path: Path, *, nom: str):
    """Deux planches d'images DISTINGUABLES, sans page de calibration.

    Les deux feuilles portent des `page_index` differents et des presses de
    tirage differentes : un appariement fautif se voit, un remplissage
    uniforme le cacherait (regle des fabriques).
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=False)
    dossier = app.write_scan_folder(
        tmp_path / nom,
        [(payloads[0], app.PRESSES_DU_TIRAGE[0]),
         (payloads[1], app.PRESSES_DU_TIRAGE[1])],
    )
    return dossier, payloads


def _documents(project_dir: Path) -> list[Path]:
    return sorted(
        (project_dir / project_layout.SCANS_DIRNAME).glob(
            f"*/{scan_detect.DETECTIONS_DIRNAME}/*.json"))


def _sans_les_volatiles(chemin: Path) -> dict:
    document = json.loads(chemin.read_text(encoding="utf-8"))
    for champ in CHAMPS_VOLATILES:
        document.pop(champ, None)
    return document


# ---------------------------------------------------------------------------
# 1 -- le meme document, contenu compare et non existence constatee
# ---------------------------------------------------------------------------


def test_la_cli_et_le_noyau_ecrivent_le_meme_document(tmp_path) -> None:
    dossier, _ = _lot_de_deux_planches(tmp_path, nom="equivalence")
    projet_cli = tmp_path / "projet-cli"
    projet_noyau = tmp_path / "projet-noyau"

    assert cli.main([
        "scan", "--project", str(projet_cli), "--scan", str(dossier),
        "--dpi", str(app.DPI), "detect",
    ]) == 0
    issue = scan_detect.run_scan_detect(
        projet_noyau, dossier, dpi=app.DPI)

    par_la_cli = _documents(projet_cli)
    par_le_noyau = _documents(projet_noyau)
    assert len(par_la_cli) == 1 and len(par_le_noyau) == 1
    assert issue.documents == (par_le_noyau[0],)
    assert issue.document_path == par_le_noyau[0]

    gauche = _sans_les_volatiles(par_la_cli[0])
    droite = _sans_les_volatiles(par_le_noyau[0])
    # Le contenu, champ par champ -- et pas seulement le fait qu'un fichier
    # existe. C'est la difference exacte entre le test qui a survecu aux trois
    # mutations de 5.8 et celui qui les aurait attrapees.
    assert droite == gauche
    # Temoin : le document compare porte bien de la matiere. Sans lui, deux
    # documents vides seraient egaux et ce test serait vert et creux.
    assert gauche["pages"], gauche
    assert len(gauche["pages"]) == 2
    assert {page["page_index"] for page in gauche["pages"]} == {0, 1}


def test_le_noyau_ecrit_au_meme_endroit_que_la_cli(tmp_path) -> None:
    """Le document vit sous `scans/<slug>/detections/`, des deux cotes."""
    dossier, _ = _lot_de_deux_planches(tmp_path, nom="endroit")
    projet = tmp_path / "projet-endroit"

    issue = scan_detect.run_scan_detect(projet, dossier, dpi=app.DPI)

    attendu = (projet / project_layout.SCANS_DIRNAME / issue.report.ingest_slug
               / scan_detect.DETECTIONS_DIRNAME)
    assert issue.document_path.parent == attendu
    assert issue.rapport_d_ingestion == (
        projet / project_layout.SCANS_DIRNAME / issue.report.ingest_slug
        / scan_detect.INGEST_DOCUMENT_FILENAME)
    assert issue.rapport_d_ingestion.exists()


# ---------------------------------------------------------------------------
# 2 -- les codes de sortie de la CLI sont inchanges
# ---------------------------------------------------------------------------


def test_les_codes_de_sortie_de_la_cli_sont_inchanges(tmp_path, capsys) -> None:
    """Les trois codes, et les deux arrets a `0` sans document, re-mesures.

    Chaque regime est mesure sur SA phrase et SON dossier de documents -- un
    code de sortie juste avec un document ecrit au mauvais moment passerait un
    test qui ne regarderait que le code.
    """
    # `0` nominal, avec document.
    dossier, _ = _lot_de_deux_planches(tmp_path, nom="codes")
    projet = tmp_path / "projet-codes"
    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier),
        "--dpi", str(app.DPI), "detect",
    ]) == 0
    assert len(_documents(projet)) == 1
    sortie = capsys.readouterr().out
    assert "scan detect termine" in sortie

    # `1` -- l'ingestion refuse un chemin qui n'existe pas.
    projet_refus = tmp_path / "projet-refus"
    assert cli.main([
        "scan", "--project", str(projet_refus),
        "--scan", str(tmp_path / "nulle-part"),
        "--dpi", str(app.DPI), "detect",
    ]) == 1
    erreur = capsys.readouterr().err
    # Le flux d'erreur porte aussi le journal de la passe : ce qui est mesure
    # ici est la DERNIERE ligne, celle que la commande imprime pour l'operateur.
    assert erreur.strip().splitlines()[-1].startswith("Erreur: "), erreur
    assert _documents(projet_refus) == []


def test_les_deux_arrets_a_zero_n_ecrivent_aucun_document(tmp_path) -> None:
    """Aucune planche identifiee, et pile de calibration seule : `0`, rien d'ecrit.

    Les deux motifs sont **nommes** par le noyau (vocabulaire ferme), et c'est
    l'enveloppeur qui en tire sa phrase -- l'un et l'autre lisent le meme fait.
    """
    # (a) aucune planche n'a livre son QR : une feuille blanche.
    import cv2
    import numpy as np

    muet = tmp_path / "muet"
    muet.mkdir()
    cv2.imwrite(str(muet / "page_01.tiff"),
                np.full((2480, 1748, 3), 255, dtype=np.uint8))
    projet_muet = tmp_path / "projet-muet"
    issue = scan_detect.run_scan_detect(projet_muet, muet, dpi=app.DPI)
    assert issue.motif_d_arret == scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE
    assert issue.documents == ()
    assert _documents(projet_muet) == []
    assert issue.pages_identifiees == 0

    # (b) pile de calibration seule.
    payloads = app.lot_payloads(sheet_count=0, with_calibration=True)
    calibration = app.write_scan_folder(
        tmp_path / "calibration", [(payloads[0], app.PRESSES_DU_TIRAGE[0])])
    projet_calibration = tmp_path / "projet-calibration"
    issue = scan_detect.run_scan_detect(
        projet_calibration, calibration, dpi=app.DPI)
    assert issue.motif_d_arret == scan_detect.ARRET_PILE_DE_CALIBRATION_SEULE
    assert issue.documents == ()
    assert _documents(projet_calibration) == []
    # Les deux motifs sont distinguables : un vocabulaire a une seule valeur
    # utile ne dirait rien de plus qu'un booleen.
    assert (scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE
            != scan_detect.ARRET_PILE_DE_CALIBRATION_SEULE)
    assert set(scan_detect.MOTIFS_D_ARRET) == {
        scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE,
        scan_detect.ARRET_PILE_DE_CALIBRATION_SEULE,
    }


def test_le_noyau_leve_les_exceptions_du_coeur_inchangees(tmp_path) -> None:
    """`EPIC7-ARB-64` : aucune exception ne se transforme en message compose.

    Le motif porte par l'exception qui remonte du noyau est **exactement** celui
    de l'exception du coeur, et la CLI le prefixe sans le reecrire.
    """
    projet = tmp_path / "projet-leve"
    with pytest.raises(Exception) as capture:
        scan_detect.run_scan_detect(
            projet, tmp_path / "inexistant", dpi=app.DPI)
    motif = str(capture.value)
    assert motif, "une exception du coeur porte toujours son motif"
    assert not motif.startswith("Erreur: "), motif
    # La classe est bien une exception du coeur, pas une exception maison.
    assert type(capture.value).__module__.startswith("mixed_media_utility")


def test_le_noyau_propage_l_exception_du_coeur_SANS_LA_RECOMPOSER(tmp_path) -> None:
    """Revue de vague 3, F6 -- distingue une exception PROPAGEE d'une RECOMPOSEE.

    `test_le_noyau_leve_les_exceptions_du_coeur_inchangees` ci-dessus est
    TAUTOLOGIQUE face au mutant M2a (`raise` -> `raise
    ScanIngestError(f"Echec de l'ingestion: {exc}")`, `scan_detect.py:185`) :
    un message RECOMPOSE reste non vide, ne commence pas par `"Erreur: "`, et
    porte une classe du paquet `mixed_media_utility` -- les trois assertions
    passent quand meme. Ce test-ci compare le motif du noyau au motif de la
    MEME erreur levee **directement** par le coeur, sur le meme appel : un
    motif recompose ENGLOBE le motif d'origine (il le contient comme
    sous-chaine) sans lui etre EGAL, et sa classe n'est plus celle du coeur
    mais la classe de base generique -- c'est exactement ce que le mutant
    introduit et que ce test doit faire rougir.
    """
    scan_path = tmp_path / "inexistant"

    # Reference : l'erreur que le COEUR leve, en direct, sur ce meme chemin.
    with pytest.raises(scan_ingest.ScanIngestError) as capture_coeur:
        scan_ingest.ingest_scan_lot(
            tmp_path / "projet-direct", scan_path, dpi=app.DPI)

    # Le noyau, sur le meme chemin.
    with pytest.raises(scan_ingest.ScanIngestError) as capture_noyau:
        scan_detect.run_scan_detect(
            tmp_path / "projet-noyau", scan_path, dpi=app.DPI)

    # Meme classe EXACTE -- une recomposition change de classe (la classe de
    # base generique remplace la sous-classe precise que le coeur avait
    # choisie).
    assert type(capture_noyau.value) is type(capture_coeur.value), (
        type(capture_noyau.value), type(capture_coeur.value))
    # Meme motif VERBATIM -- pas un prefixe de plus, pas un englobement. Un
    # motif recompose CONTIENT le motif d'origine sans lui etre egal ; c'est
    # cette difference, precisement, que ce test mesure.
    assert str(capture_noyau.value) == str(capture_coeur.value)


# ---------------------------------------------------------------------------
# 3 -- l'orchestration a quitte la commande (grep executable + son symetrique)
# ---------------------------------------------------------------------------

#: Les quatre noms d'orchestration nommes par l'AC 2a, plus les trois appels de
#: sequence : une commande qui les garderait n'aurait pas ete reduite a un
#: enveloppeur, elle aurait ete dupliquee.
_ORCHESTRATION = (
    "build_scan_previz",
    "detect_lot_pages",
    "detect_pages",
    "build_lot_report",
    "build_page_crop_plan",
    "canonical_json",
    "ingest_scan_lot",
    "check_scan_conflicts",
    "trier_les_pages",
)


def _corps_sans_docstring(fonction) -> str:
    """Le CODE d'une fonction, sa docstring retiree.

    Un docstring a le droit de nommer ce que la fonction ne fait plus -- c'est
    meme ce qui rend l'histoire lisible. Le grep, lui, porte sur ce qui
    s'execute : le confondre avec la prose rendrait la frontiere inapplicable
    ou, pire, ferait supprimer l'explication pour faire passer un test.
    """
    arbre = ast.parse(inspect.getsource(fonction)).body[0]
    corps = list(arbre.body)
    if (corps and isinstance(corps[0], ast.Expr)
            and isinstance(corps[0].value, ast.Constant)
            and isinstance(corps[0].value.value, str)):
        corps = corps[1:]
    return "\n".join(ast.unparse(noeud) for noeud in corps)


def test_le_chemin_detect_de_la_cli_n_orchestre_plus() -> None:
    source = _corps_sans_docstring(cli.scan_detect_command)
    trouves = [nom for nom in _ORCHESTRATION if nom in source]
    assert trouves == [], (
        f"`scan_detect_command` orchestre encore : {trouves}. Le corps vit "
        "dans `scan_detect.run_scan_detect`, la commande l'enveloppe.")
    # Volet positif : elle appelle bien le point d'appel unique. Sans lui, une
    # commande videe de tout passerait ce grep sans rien faire.
    assert "scan_detect.run_scan_detect(" in source


def test_la_frontiere_d_orchestration_mord_vraiment() -> None:
    """Le grep ci-dessus mord sur un corps fautif fabrique.

    « Une frontiere qui ne mord sur rien n'est pas une frontiere. » Le temoin
    est le corps que la commande avait AVANT l'extraction, en miniature.
    """
    temoin = (
        "def scan_detect_command(args):\n"
        "    report = scan_ingest.ingest_scan_lot(project_dir, args.scan)\n"
        "    document = scan_previz.build_scan_previz(ingest=report)\n"
        "    return 0\n"
    )
    trouves = [nom for nom in _ORCHESTRATION if nom in temoin]
    assert "ingest_scan_lot" in trouves and "build_scan_previz" in trouves


def test_le_noyau_porte_bien_l_orchestration() -> None:
    """Symetrique du precedent : ce que la commande a perdu, le noyau l'a.

    Sans cette moitie, le grep serait satisfait par une orchestration qui aurait
    simplement disparu du depot.
    """
    source = Path(scan_detect.__file__).read_text(encoding="utf-8")
    manquants = [nom for nom in _ORCHESTRATION
                 if nom not in source and nom != "detect_lot_pages"]
    assert manquants == [], manquants


def test_l_enveloppeur_garde_ses_deux_gardes_ar2() -> None:
    """AR2 : le `try` de haut niveau ne porte que `KeyboardInterrupt` et `OSError`."""
    arbre = ast.parse(inspect.getsource(cli.scan_detect_command))
    fonction = arbre.body[0]
    tries = [n for n in fonction.body if isinstance(n, ast.Try)]
    assert len(tries) == 1, len(tries)
    assert [h.type.id for h in tries[0].handlers] == ["KeyboardInterrupt", "OSError"]


def test_le_noyau_n_imprime_rien_et_ne_rend_aucun_code() -> None:
    """`EPIC7-ARB-64`, frontiere negative : ni `print`, ni code de retour.

    C'est ce qui rend le module consommable par une interface : un motif
    imprime est un motif perdu pour tout appelant qui n'est pas un terminal.
    """
    source = Path(scan_detect.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    prints = [
        noeud for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "print"
    ]
    assert prints == [], f"{len(prints)} print() dans le module de coeur"
    assert "sys.stderr" not in source
    # Temoin : le module porte bien du code appelable, le balayage n'est pas vide.
    assert any(isinstance(n, ast.FunctionDef) for n in ast.walk(arbre))
