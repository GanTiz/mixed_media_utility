"""Story 5.22, tache 2: la sous-commande `scan calibrate` (AC 1, 2, 4).

Le geste est `scan --project P --scan S --dpi D calibrate`: la sous-commande
**porte** les options du parent et n'en declare aucune a elle.

**Amende le 2026-08-18 (story 5.23, AC 13, `EPIC5-ARB-88`).** Le drapeau qui
nommait la chaine a la main a ete retire, et avec lui tout ce que ce fichier
verifiait de la surcharge. L'identite de chaine est desormais **derivee** des
parametres reels du scan, et rien d'autre: depuis `EPIC5-ARB-83` l'operateur
designe le profil lui-meme, donc le `chain_id` ne sert plus a apparier -- il
nomme ce que cette commande produit. Les tests qui exercaient la surcharge sont
retires avec elle (leur sujet n'existe plus); ceux qui s'en servaient seulement
pour poser un nom court passent par la derive, obtenue du **vrai** producteur.
Ce que le drapeau protegeait, lui, est repris par
`test_restes_inertes_retires.py`: qu'il soit refuse aux deux positions.

Le defaut mesure le 2026-08-17 -- une option declaree sur le parent **et** sur le
sous-parseur voit sa valeur ecrasee par le defaut du sous-parseur, applique
apres l'analyse du parent -- reste vrai et reste la raison pour laquelle la
sous-commande ne declare aucune option a elle.

Ce fichier verifie la forme du geste (analyse argparse) et l'orchestration
du handler (ingestion reelle, derive de chaine, ecriture du profil, refus sans
profil) -- l'ajustement lui-meme est eprouve contre les vrais producteurs dans
`test_calibration_page_source` / `test_color_calibration`, et le point
d'orchestration qu'il faudrait un raster scanne complet pour exercer est
substitue ici, par le meme geste que `_parse_scan` de 5.16.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli,
    color_calibration as cc,
    scan_calibrate,
    scan_chain,
    scan_ingest,
)
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.io import reconstruction  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

import test_calibration_page_source as couleur  # noqa: E402


def _write_scan_folder(tmp_path: Path) -> Path:
    """Un dossier de scan ingerable, une page synthetique sans QR ni marqueur."""
    folder = tmp_path / "scan-calibration"
    folder.mkdir()
    assert cv2.imwrite(
        str(folder / "page.tif"),
        np.full((400, 600, 3), 200, dtype=np.uint8))
    return folder


def _lot_correction_ajuste():
    """Une correction **ajustee** par le vrai producteur, sur un raster synthetique."""
    profil = couleur._calibration_profile()
    # La forme du lot est celle du profil: une fixture ou les deux divergeraient
    # serait precisement l'incoherence que le handler a pour tache d'eviter.
    return cc.LotCorrection(
        source_page_id="calibration-0",
        template_id=couleur.TEMPLATE,
        profile=profil,
        correction_form_id=profil.correction_id,
    )


def _derive_attendu(folder: Path, project_dir: Path) -> str:
    """L'identite de chaine que la commande **derive**, par le vrai producteur.

    Le format mesure (`report_scan_input_format`) n'est jamais recopie en dur ici
    : c'est lui qui pilote le condensat, et un test qui ecrirait "tiff" a la
    main fixerait le format d'une extension au lieu du format mesure.
    """
    rapport = scan_ingest.ingest_scan_lot(project_dir, folder, dpi=600)
    return scan_chain.derive_chain_id(
        declared_dpi=rapport.declared_dpi,
        scan_input_format=scan_chain.report_scan_input_format(rapport))


def _chaine_derivee(folder: Path, tmp_path: Path) -> str:
    """L'identite que la commande **derive** de ce scan, par le vrai producteur.

    Depuis le retrait du drapeau de nommage (story 5.23, AC 13), c'est la seule
    identite qu'un profil puisse porter: les tests qui posaient un nom court
    (`chaine-x`) passent par ici plutot que par un litteral, sans quoi ils
    verifieraient un chemin de fichier que la commande n'ecrit plus.

    L'ingestion temoin se fait dans un projet **jetable**, pour ne pas semer un
    `logs/` ou un layout dans le projet que le test observe.
    """
    return _derive_attendu(folder, tmp_path / "derive-a-part")


def _capturer_args(monkeypatch) -> list:
    vus: list = []

    def capture(args):
        vus.append(args)
        return 0

    monkeypatch.setattr(cli, "scan_calibrate_command", capture)
    return vus


# --- la forme du geste (analyse argparse) ----------------------------------


def test_calibrate_se_parse_sous_scan_avec_ses_options_parentes(monkeypatch) -> None:
    """Le geste AC 1: `scan --project P --scan S --dpi D calibrate`.

    La sous-commande porte les options du parent, qui restent obligatoires
    **avant** elle: c'est le design mesure de la story, et c'est lui que ce test
    fige en traversant le vrai parseur.
    """
    vus = _capturer_args(monkeypatch)
    assert cli.main([
        "scan", "--project", "projet-x", "--scan", "scan-s",
        "--dpi", "600", "calibrate",
    ]) == 0
    (args,) = vus
    assert args.project == "projet-x"
    assert args.scan == "scan-s"
    assert args.dpi == 600


def test_calibrate_garde_le_refus_d_un_dpi_manquant() -> None:
    """Non-regression AC: `scan --project p --scan s` garde son code 2.

    Ajouter la sous-commande ne doit pas desserrer l'obligation `--dpi` du
    parent, qui est le contrat de 5.1 (un DPI devine fausse toute la geometrie).
    """
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["scan", "--project", "p", "--scan", "s", "calibrate"])
    assert excinfo.value.code == 2


# --- orchestration du handler, contre l'ingestion reelle -------------------
#
# Le seul point substitue est `cli._fit_lot_correction`, la ou l'ajustement du
# lot est orchestre: son contenu est eprouve contre les vrais producteurs dans
# les fichiers de la moitie couleur. La detection d'une page synthetique sans
# marqueur est reelle et rend une page refusee sans lever.


def test_calibrate_ecrit_le_profil_sous_versions_calibration(tmp_path, monkeypatch) -> None:
    """Le handler enchainement reel: ingestion -> fit -> fichier de profil (AC 2)."""
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())

    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    chain_id = _derive_attendu(folder, project_dir)
    chemin = calibration_profile.profile_path(project_dir, chain_id)
    assert chemin.is_file()
    document = calibration_profile.read_profile(project_dir, chain_id)
    assert document["chain_id"] == chain_id
    assert document["correction_form_id"] == cc.CORRECTION_FORM_ID
    assert document["source_page_id"] == "calibration-0"
    # Et rien d'un scan de lot n'est ecrit: ni frames, ni manifest projet.
    assert not (project_dir
               / project_layout.EXTRACT_FRAMES_DIRNAME).exists()
    assert not (project_dir / "project.json").exists()


def test_calibrate_sans_chain_id_derive_le_meme_identifiant_qu_a_la_main(
    tmp_path, monkeypatch,
) -> None:
    """La derive de la commande et la derive directe coincident (AC 4, defaut)."""
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0
    attendu = _derive_attendu(folder, project_dir)
    assert calibration_profile.profile_exists(project_dir, attendu)
    document = calibration_profile.read_profile(project_dir, attendu)
    assert document["chain_id"] == attendu


def test_calibrate_reecrit_un_profil_existant_a_l_identique(tmp_path, monkeypatch) -> None:
    """Re-calibrer la meme chaine **remplace** le profil, et la relecture est stable."""
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())
    chaine = _chaine_derivee(folder, tmp_path)
    argv = ["scan", "--project", str(project_dir), "--scan", str(folder),
            "--dpi", "600", "calibrate"]
    assert cli.main(argv) == 0
    premier = calibration_profile.read_profile(project_dir, chaine)
    assert cli.main(argv) == 0
    second = calibration_profile.read_profile(project_dir, chaine)
    assert premier == second


def test_calibrate_sans_page_de_calibration_refuse_sans_ecrire(
    tmp_path, monkeypatch,
) -> None:
    """Aucune page de calibration -> refus `1`, jamais un profil vide invente."""
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: None)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 1
    assert not calibration_profile.profile_exists(
        project_dir, _chaine_derivee(folder, tmp_path))


def test_calibrate_sur_un_fit_echoue_refuse_sans_ecrire(tmp_path, monkeypatch) -> None:
    """Un ajustement echoue (page illisible, geometrie perdue) ne consigne rien.

    La commande est explicite: un echec d'ajustement est un refus, pas un profil
    partiel. Le motif de l'echec voyage dans le message d'erreur.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    echec = cc.LotCorrection(
        source_page_id="calibration-0",
        template_id=couleur.TEMPLATE,
        profile=None,
        failure_reason=cc.FAILURE_PATCHES_NOT_FOUND,
        failure_message="Page de calibration 'calibration-0' non relisable.",
    )
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: echec)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 1
    assert not calibration_profile.profile_exists(
        project_dir, _chaine_derivee(folder, tmp_path))


# --- messages operateur de la commande (AC 1) -------------------------------
#
# **Ajoutes a la revue du 2026-08-17 (finding C5).** Aucun `capsys` ne portait sur
# cette commande: l'AC 1 exige un message qui **nomme la chaine**, et seul le
# fichier de profil etait verifie. Un handler devenu muet -- ou nommant la mauvaise
# chaine -- passait toute la suite, alors que ce message est la seule chose que
# l'operateur voit d'une commande qui reussit.


def _journal(project_dir: Path) -> str:
    """`logs/scan.log`, et non `caplog`.

    Le logger de `scan` pose `propagate = False` (`_configure_scan_logger`): aucun
    enregistrement n'atteint la racine que `caplog` ecoute, donc un test pose sur
    `caplog` y lirait une chaine vide et passerait des qu'on cesserait d'asserter
    dessus. Le journal sur disque est de surcroit l'artefact que l'operateur relit.
    """
    chemin = project_dir / project_layout.LOGS_DIRNAME / "scan.log"
    assert chemin.is_file(), f"aucun journal de scan sous {chemin}"
    return chemin.read_text(encoding="utf-8")


def test_le_message_de_succes_nomme_la_chaine_le_fichier_et_la_page_source(
    tmp_path, monkeypatch, capsys,
) -> None:
    """AC 1: le message rendu a l'operateur **nomme la chaine**.

    Les trois grandeurs sont assertees ensemble parce qu'elles repondent a trois
    questions distinctes que l'operateur se pose devant ce message: quelle chaine
    vient d'etre calibree, ou le profil a ete ecrit, et sur quelle feuille il a ete
    ajuste. Un message qui n'en porterait que deux obligerait a rouvrir le projet
    pour la troisieme.

    **La chaine dite est la chaine DERIVEE**, et depuis le retrait du drapeau de
    nommage (story 5.23, AC 13) c'est la seule qui existe. Ce volet etait porte par
    un second test, temoin du precedent tant qu'une surcharge etait possible; il
    est absorbe ici, et l'assertion garde son point: la valeur dite est celle sous
    laquelle `scan` **relira** le profil, la seule que l'operateur ne peut pas
    deviner.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())
    chaine = _chaine_derivee(folder, tmp_path)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    sortie = capsys.readouterr()
    # `stderr` porte la console du logger de `scan` (`_configure_scan_logger` y
    # branche un `StreamHandler`), donc l'assertion utile n'est pas qu'il soit vide
    # mais qu'aucun refus n'y ait ete ecrit.
    assert "Erreur: " not in sortie.err, sortie.err
    chemin_du_profil = str(calibration_profile.profile_path(project_dir, chaine))
    assert chemin_du_profil in sortie.out, sortie.out
    assert "calibration-0" in sortie.out, sortie.out
    # **La chaine est nommee HORS du chemin de fichier**, et cette precision n'est pas
    # cosmetique. Mesure du 2026-08-19: `chaine in sortie.out` seul est **inerte** --
    # le chemin du profil est `versions/calibration/<chain_id>.json`, donc il porte
    # deja l'identifiant, et le mutant qui retire « pour la chaine '<chain_id>' » du
    # message passait les 44 tests de ce fichier. L'AC 1 exige un message qui **nomme**
    # la chaine, pas un message d'ou on peut la deduire en lisant un nom de fichier:
    # on mesure donc sur ce qui reste du message une fois le chemin retire.
    sans_le_chemin = sortie.out.replace(chemin_du_profil, "")
    assert chaine in sans_le_chemin, (chaine, sortie.out)
    # Le journal porte la meme chaine: les deux artefacts se recoupent, et c'est ce
    # qui permet de relire deux jours plus tard une commande dont la console est
    # perdue.
    assert chaine in _journal(project_dir)


def test_les_refus_de_calibrate_nomment_le_geste_sur_la_sortie_d_erreur(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Les deux refus de la commande sortent **nommes** sur `stderr`, jamais muets.

    Les deux regimes ne se confondent pas et n'appellent pas le meme geste: aucune
    page de calibration lue (il faut en scanner une), contre ajustement echoue (la
    feuille est la, elle est inexploitable). Un refus qui rendrait `1` sans un mot
    laisserait l'operateur devant une commande qui n'a rien ecrit sans raison.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    chaine = _chaine_derivee(folder, tmp_path)
    argv = ["scan", "--project", str(project_dir), "--scan", str(folder),
            "--dpi", "600", "calibrate"]

    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: None)
    assert cli.main(argv) == 1
    absente = capsys.readouterr()
    # `in` et non `startswith`: la console du logger de `scan` partage `stderr` avec
    # les refus de la commande. C'est le refus **nomme** qui est mesure ici.
    assert "Erreur: " in absente.err, absente.err
    assert "page de calibration" in absente.err, absente.err
    # Le journal, lui, nomme la chaine: c'est ce qui distingue deux refus successifs
    # sur deux chaines differentes dans le meme projet.
    assert chaine in _journal(project_dir)

    echec = cc.LotCorrection(
        source_page_id="calibration-0", template_id=couleur.TEMPLATE, profile=None,
        failure_reason=cc.FAILURE_PATCHES_NOT_FOUND,
        failure_message="Page de calibration 'calibration-0' non relisable.")
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction", lambda *a, **k: echec)
    assert cli.main(argv) == 1
    inexploitable = capsys.readouterr()
    assert echec.failure_message in inexploitable.err, inexploitable.err
    # Les deux refus ne rendent **pas** le meme message: sinon la distinction que le
    # code prend soin de faire n'atteindrait pas l'operateur.
    assert inexploitable.err != absente.err


# --- C2: l'ecriture du profil peut echouer autrement que par validation -----
#
# **Trouve a la revue du 2026-08-17 (finding C2).** Seul `ProfileValidationError`
# etait rattrape, alors que `write_profile` echoue aussi a l'ecriture atomique
# (`ProfileReadError`) et au `mkdir` du dossier (`OSError` nue): disque plein,
# dossier en lecture seule. Ces deux familles sortaient en **traceback** au lieu du
# refus nomme et du code 1.
#
# Les deux regimes sont construits **sans stub**, par l'etat du systeme de fichiers:
# c'est la seule forme qui prouve que le code de production leve bien ce qu'on croit
# qu'il leve.


def _versions_calibration(project_dir: Path) -> Path:
    return (project_dir / calibration_profile.VERSIONS_DIRNAME
            / calibration_profile.CALIBRATION_DIRNAME)


def _bloquer_le_dossier_des_profils(project_dir: Path) -> None:
    """`versions/calibration` **est un fichier**: le `mkdir` de `write_profile` leve.

    Construction reelle du regime « le dossier ne peut pas etre cree », et elle a
    l'avantage de mordre aussi sous `root` -- ou un `chmod` ne bloque rien.
    """
    dossier = _versions_calibration(project_dir)
    dossier.parent.mkdir(parents=True, exist_ok=True)
    dossier.write_text("ceci n'est pas un dossier", encoding="utf-8")


def _bloquer_le_fichier_de_profil(project_dir: Path, chain_id: str) -> None:
    """Le chemin du profil **est un dossier**: le `os.replace` final leve.

    C'est le second etage d'`_atomic_write_profile`, celui qui rend
    `ProfileReadError` -- la famille « disque plein / remplacement impossible ».
    """
    calibration_profile.profile_path(project_dir, chain_id).mkdir(parents=True)


@pytest.mark.parametrize("bloquer", ["dossier", "fichier"])
def test_calibrate_rend_un_refus_nomme_quand_l_ecriture_du_profil_echoue(
    tmp_path, monkeypatch, capsys, bloquer,
) -> None:
    """Disque plein, dossier en lecture seule: refus nomme et code `1`, pas de trace.

    Les deux etages sont exerces parce qu'ils levent deux classes differentes --
    `OSError` nue pour le `mkdir`, `ProfileReadError` pour le remplacement atomique
    -- et qu'un rattrapage qui ne nommerait que la seconde laisserait le premier
    sortir en traceback, ce qui est exactement le defaut trouve.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())
    project_layout.ensure_project_layout(project_dir)
    chaine = _chaine_derivee(folder, tmp_path)
    if bloquer == "dossier":
        _bloquer_le_dossier_des_profils(project_dir)
    else:
        _bloquer_le_fichier_de_profil(project_dir, chaine)

    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 1
    sortie = capsys.readouterr()
    # Le refus est **nomme** et la commande n'a pas explose: c'est litteralement ce
    # que le finding C2 reprochait -- un traceback au lieu du couple refus + code 1.
    assert "Erreur: " in sortie.err, sortie.err
    assert "Traceback" not in sortie.err, sortie.err
    # Le journal nomme la chaine dont le profil n'a pas ete ecrit: sans elle, un
    # projet a plusieurs chaines ne dit pas laquelle est restee sans profil.
    assert chaine in _journal(project_dir)


# --- C7: les fonctions neuves de `cli.py`, a l'unite ------------------------
#
# **Ajoute a la revue du 2026-08-17 (finding C7).** Tout le contrat socle de la
# story n'etait epingle que depuis un fichier d'integration a 180 s, si bien qu'un
# mutant de `cli.py` n'etait confronte qu'a des tests de bout en bout. Les tests
# d'integration ne sont **pas** deplaces: c'est le niveau qui manquait qui est
# ajoute ici, contre les vrais producteurs et sans raster de page.


def _logger_de_projet(project_dir: Path):
    """Le logger que la commande utilise reellement, avec son fichier."""
    project_layout.ensure_project_layout(project_dir)
    return cli._configure_scan_logger(project_dir)


def _coefficients(profile) -> dict:
    """Les coefficients d'un profil, par nom -- pour comparer des **valeurs**."""
    document = cc.profile_to_document(
        profile, chain_id="x", source_page_id="p", template_id="t",
        read_patch_count=0, retained_patch_count=0, ink_floor_excluded=False)
    return {cle: np.asarray(valeur, dtype=float)
            for cle, valeur in document["coefficients"].items()}


def _ecrire_profil(project_dir: Path, chain_id: str, press) -> dict:
    """Consigner un profil de chaine, ajuste par les **vrais** producteurs.

    `press` est un parametre: c'est ce qui rend deux profils du meme projet
    **distinguables** au coefficient pres (regle des fabriques). Deux profils
    identiques rendraient invisible tout appariement chaine -> profil permute.
    """
    profil = couleur._calibration_profile(press=press)
    document = cc.profile_to_document(
        profil, chain_id=chain_id, source_page_id=f"{chain_id}-p0",
        template_id=couleur.TEMPLATE, read_patch_count=18, retained_patch_count=18,
        ink_floor_excluded=cc.correction_form_excludes_ink_floor(profil.correction_id))
    calibration_profile.write_profile(project_dir, document)
    return document


def test_derive_chain_id_n_a_plus_qu_une_voie_et_c_est_la_derive(tmp_path) -> None:
    """`_derive_chain_id` n'a plus qu'une voie depuis la story 5.23 (AC 13).

    L'ancienne redaction opposait la derive a un `override` et gardait un temoin de
    difference entre les deux; le drapeau retire, il ne reste que la derive. Le temoin
    est donc deplace, pas supprime: **deux scans differents doivent donner deux
    identites differentes**, sans quoi une derive devenue constante -- le mutant le plus
    dangereux ici, puisqu'il ferait relire un profil sous l'identite d'une autre chaine
    -- passerait un test qui n'appellerait la fonction qu'une fois.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    rapport = scan_ingest.ingest_scan_lot(project_dir, folder, dpi=600)
    logger = _logger_de_projet(project_dir)

    derive = cli._derive_chain_id(rapport, folder, logger)
    assert derive == _derive_attendu(folder, tmp_path / "derive-a-part")

    # Le temoin: un second scan, au **meme** dpi mais dans un autre format mesure, ne
    # doit pas rendre la meme identite.
    autre_dossier = tmp_path / "scan-png"
    autre_dossier.mkdir()
    assert cv2.imwrite(str(autre_dossier / "page.png"),
                       np.full((400, 600, 3), 200, dtype=np.uint8))
    autre = cli._derive_chain_id(
        scan_ingest.ingest_scan_lot(tmp_path / "projet-2", autre_dossier, dpi=600),
        autre_dossier, _logger_de_projet(tmp_path / "projet-2"))
    assert autre != derive, "derive constante: deux chaines partageraient un profil"


def _dossier_de_scan_tague(dossier: Path, *, make: str, model: str,
                           software: str) -> Path:
    """Un dossier de scan dont le raster porte **vraiment** les tags 271/272/305.

    `_write_scan_folder` ecrit par OpenCV, qui n'ecrit aucun de ces trois tags: toutes
    les fixtures de ce fichier faisaient donc passer un materiel de chaine ou les trois
    champs scanner valent `""`. Un raster tague est la seule facon de rendre le cablage
    `read_scan_tags` -> `derive_chain_id` **observable depuis la commande**.
    """
    from PIL import Image

    dossier.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((400, 600, 3), 200, dtype=np.uint8), mode="RGB").save(
        dossier / "page-01.tiff",
        tiffinfo={scan_chain.TIFF_TAG_MAKE: make,
                  scan_chain.TIFF_TAG_MODEL: model,
                  scan_chain.TIFF_TAG_SOFTWARE: software})
    return dossier


def test_les_tags_du_raster_atteignent_l_identite_derivee_par_la_commande(
    tmp_path,
) -> None:
    """`EPIC5-ARB-39`, le bout que la revue de 5.22 avait laisse ouvert.

    Le finding « aucune fixture ne fait jamais passer un tag scanner non vide » a ete
    ferme au niveau **module** le 2026-08-17 (`test_scan_chain.py::
    test_les_tags_tiff_reels_atteignent_le_chain_id`), et le commit qui l'a ferme le dit
    lui-meme: le cablage **dans `cli._derive_chain_id`** restait a mesurer, son site
    etant hors du perimetre de ce lot-la. Mesure du 2026-08-19: le mutant qui remplace
    `scan_chain.read_scan_tags(scan_locator)` par `("", "", "")` passait **60 tests sur
    60** des deux suites concernees. Un test d'integration qui n'asserte pas ne prouve
    rien -- ici, aucune assertion ne pouvait mordre puisque aucune fixture ne portait de
    tag.

    Les trois volets sont mesures ensemble, et aucun ne suffit seul:

    * (a) l'identite rendue par la commande est **exactement** celle des tags lus sur le
      raster -- le chemin de lecture ne les deforme pas ;
    * (b) elle **differe** de l'identite derivee sans tags: c'est le volet qui tue le
      mutant qui supprime le cablage ;
    * (c) deux dossiers identiques au seul `model` pres rendent deux identites
      differentes -- deux scanners au meme dpi et au meme format ne partagent pas de
      profil, ce qui est le risque inverse exact de celui que la story supprime.
    """
    project_dir = tmp_path / "projet"
    dossier = _dossier_de_scan_tague(
        tmp_path / "scan-epson", make="EPSON", model="V850", software="EpsonScan")
    rapport = scan_ingest.ingest_scan_lot(project_dir, dossier, dpi=600)
    logger = _logger_de_projet(project_dir)

    derive = cli._derive_chain_id(rapport, dossier, logger)

    # (a) le materiel est celui des tags du raster, jamais recopie a la main: le format
    # vient du producteur (`report_scan_input_format`), comme partout dans ce fichier.
    assert derive == scan_chain.derive_chain_id(
        declared_dpi=rapport.declared_dpi,
        scan_input_format=scan_chain.report_scan_input_format(rapport),
        make="EPSON", model="V850", software="EpsonScan")
    # (b) et il n'est pas celui du materiel **sans** tags: sans ce volet, un cablage
    # supprime rendrait encore une identite valide, seulement fausse.
    assert derive != scan_chain.derive_chain_id(
        declared_dpi=rapport.declared_dpi,
        scan_input_format=scan_chain.report_scan_input_format(rapport))

    # (c) le temoin de discrimination, sur un seul tag change.
    autre_projet = tmp_path / "projet-2"
    autre_dossier = _dossier_de_scan_tague(
        tmp_path / "scan-epson-2", make="EPSON", model="V600", software="EpsonScan")
    autre = cli._derive_chain_id(
        scan_ingest.ingest_scan_lot(autre_projet, autre_dossier, dpi=600),
        autre_dossier, _logger_de_projet(autre_projet))
    assert autre != derive, (
        "deux scanners distingues par le seul tag `model` partageraient un profil")


def test_derive_chain_id_rend_none_et_le_dit_quand_la_derive_est_impossible(
    tmp_path,
) -> None:
    """Un scan sans page ne derive aucune chaine -- et ce n'est pas un echec de commande.

    `_derive_chain_id` rend `None` **apres l'avoir dit**: c'est `scan` qui decide
    qu'un lot sans identite de chaine est livre en brut, et `calibrate` qu'il refuse.
    Un `None` muet aurait laisse l'operateur sans la raison.
    """
    project_dir = tmp_path / "projet"
    logger = _logger_de_projet(project_dir)
    vide = SimpleNamespace(declared_dpi=600, pages=())

    assert cli._derive_chain_id(vide, tmp_path, logger) is None
    journal = _journal(project_dir)
    assert "chaine" in journal.lower(), journal
    # **Plus aucun rattrapage a la main** depuis la story 5.23 (AC 13): un rapport
    # inderivable rend `None`, point. L'ancienne redaction verifiait ici qu'un override
    # restait souverain meme sur ce rapport -- ce chemin n'existe plus, et le laisser
    # aurait ete precisement le reste inerte que `EPIC5-ARB-88` supprime.


# --- l'appariement par `chain_id` a disparu (story 5.23, AC 12, 2026-08-18) --
#
# **Neuf tests ont ete retires ici**, et non desactives: leur sujet n'existe plus.
# `_resolve_chain_correction` derivait l'identite de la chaine de scan puis lisait
# `versions/calibration/<chain_id>.json`; `_consign_external_profile` consignait un
# profil externe sous cette identite-la et refusait tout fichier dont le `chain_id`
# differait. `EPIC5-ARB-83` supprime cet appariement: la derivation est **mesuree
# defaillante** sur le materiel d'Egan -- tags scanner absents, deux scanners rendant
# tous deux `600-tiff-e2168f9b2b81` --, donc elle acceptait le mauvais profil et
# refusait le bon, dans les deux cas en silence. C'est l'operateur qui designe.
#
# La distinction avec l'AC 11, qui **desactive** ses 42 tests au lieu de les retirer,
# tient a la mise en situation: celle des 42 (une page de calibration dans la meme passe
# que des planches) redeviendra valide avec l'ingest en vrac, seules leurs assertions
# meurent. Ici c'est l'inverse -- la fonction appelee n'existe plus, et aucune story a
# venir ne la fera revenir.
#
# **Ce qu'ils protegeaient et qui reste vrai** est repris nom pour nom dans
# `tests/unit/test_profil_designe.py`, jamais perdu en silence:
#
# | test retire | reprise |
# | --- | --- |
# | `..._rend_les_coefficients_de_LA_chaine_visee` | `test_le_profil_designe_est_celui_qui_est_applique` (trois profils, cible en deuxieme position, mesure sur les coefficients) |
# | `..._sans_profil_nomme_les_deux_gestes` | `test_aucun_profil_designe_avertit_et_ne_se_rabat_sur_rien` (les deux gestes sont nommes, et c'est un avertissement, pas un refus) |
# | `..._sans_chain_id_ne_lit_rien` | `test_aucun_profil_designe_ne_lit_aucun_fichier_de_profil` (meme mesure sur les lectures, meme temoin positif) |
# | `..._refuse_un_profil_present_mais_corrompu` | `test_un_profil_designe_illisible_ne_se_rabat_pas_sur_un_profil_du_projet` |
# | `test_consigner_un_profil_externe_l_ecrit_et_le_rend` | `test_un_profil_hors_du_projet_est_applique_sans_refus_lie_au_projet` |
# | `..._ne_compare_jamais_le_projet` | idem (la moitie « le refus de chaine mord encore » est morte avec l'appariement) |
# | `..._refuse_sans_rien_ecrire[illisible]` | `test_un_profil_designe_refuse_n_ecrit_rien_dans_le_projet` |
# | `..._refuse_sans_rien_ecrire[autre-chaine]` | morte: il n'y a plus de refus de chaine |
# | `..._survit_a_une_ecriture_impossible` | `test_une_ecriture_de_profil_impossible_ne_tue_pas_le_scan` (bloquant `C2` de la revue de 5.22, meme construction reelle du regime) |
#
# `_ecrire_profil`, `_logger_de_projet`, `_journal` et `_coefficients` restent: ils
# servent encore aux tests de `scan calibrate`, qui produit toujours un profil.


# --- les temoins bruts de la page passent dans le profil (2026-08-18) --------
#
# Mesure sur les vrais scans d'Egan: la chaine se calibrait, les planches se
# corrigeaient, et le manifeste rendait `raw_divergence_no_calibration_sheet` sur toutes
# les planches -- le profil ne portait aucune mesure de ses pastilles temoins, donc un
# scan ulterieur n'avait rien a comparer. C'est ici que la mesure entre dans le fichier.
#
# **Regle des fabriques**: six temoins distinguables, la valeur visee en avant-derniere
# position du jeu ecrit, jamais un remplissage uniforme.

_TEMOINS_DE_LA_PAGE = (
    ("secondary-magenta", (0.581, 0.232, 0.679)),
    ("primary-red", (0.180, 0.171, 0.742)),
    ("neutral-065", (0.251, 0.254, 0.257)),
    ("secondary-cyan", (0.684, 0.641, 0.233)),
    ("primary-blue", (0.622, 0.291, 0.174)),
    ("primary-green", (0.271, 0.583, 0.212)),
)


def _lot_correction_avec_temoins(temoins=_TEMOINS_DE_LA_PAGE):
    correction = _lot_correction_ajuste()
    return cc.LotCorrection(
        source_page_id=correction.source_page_id,
        template_id=correction.template_id,
        profile=correction.profile,
        correction_form_id=correction.correction_form_id,
        witness_raw_bgr=tuple(temoins))


def test_calibrate_consigne_les_temoins_bruts_de_la_page_dans_le_profil(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Le profil devient autoportant pour la divergence brute a brute.

    Verifie sur le **fichier relu**, pas sur l'objet en memoire: c'est le fichier qui
    voyage jusqu'au scan suivant, des semaines plus tard.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_avec_temoins())
    chaine = _chaine_derivee(folder, tmp_path)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    document = calibration_profile.read_profile(project_dir, chaine)
    temoins = dict(calibration_profile.witness_raw_of_document(document))
    assert set(temoins) == {value_id for value_id, _ in _TEMOINS_DE_LA_PAGE}
    # Appariement par identifiant: la cible n'est pas en premiere position du jeu ecrit,
    # et elle porte **sa** mesure, pas celle de sa voisine.
    assert temoins["primary-blue"] == (0.622, 0.291, 0.174)
    assert temoins["secondary-magenta"] == (0.581, 0.232, 0.679)
    # Et l'operateur l'apprend: c'est le seul moment ou il peut encore reimprimer une
    # page de calibration portant le bandeau.
    assert "6 pastille(s) temoin mesuree(s)" in capsys.readouterr().out


def test_calibrate_sur_une_page_sans_bandeau_ecrit_le_profil_et_le_dit(
    tmp_path, monkeypatch, capsys,
) -> None:
    """Pas de temoins -> profil valide **sans** le champ, et un avertissement explicite.

    Le champ absent et un champ vide ne disent pas la meme chose: l'absence se relit
    « pas mesure » et sort au manifeste sous `raw_divergence_no_calibration_sheet`, qui
    reste vrai de cette page. Ecrire une liste vide dirait « mesure, rien trouve ».
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_avec_temoins(()))
    chaine = _chaine_derivee(folder, tmp_path)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    brut = calibration_profile.profile_path(project_dir, chaine).read_text(
        encoding="utf-8")
    assert calibration_profile.WITNESS_RAW_FIELD not in brut
    assert calibration_profile.witness_raw_of_document(
        calibration_profile.read_profile(project_dir, chaine)) == ()
    sortie = capsys.readouterr().out
    assert "Aucune pastille temoin" in sortie
    assert "ne sera pas mesurable" in sortie


# ---------------------------------------------------------------------------
# Correctif de revue (lot A, couche 3, F3): les avertissements sont **emis**
# ---------------------------------------------------------------------------
#
# Le defaut mesure: les deux `if` d'emission de `scan_command` remplaces par `pass`
# etaient un **mutant survivant** -- sur le lot de la story comme sur
# `test_chain_profile_scan.py`, les deux seuls lots qui relisent `logs/scan.log`. Le
# **libelle** des deux messages etait epingle par les tests unitaires de
# `color_calibration`; leur **existence** ne l'etait par rien.
#
# C'est la moitie visible de `EPIC5-ARB-82` decisions 4 et 7, c'est-a-dire de la
# demande fondatrice d'Egan « avertir, pas refuser »: un message parfaitement redige
# qui n'est jamais ecrit vaut exactement l'absence de message. Les deux `if` sont
# desormais dans `cli._avertir_sur_une_page`, extraite pour cette seule raison.

#: Les deux seuils, **ecrits en litteral** et jamais lus sur le registre du code. Une
#: valeur derivee de la constante resterait au-dessus du seuil apres le mutant qui
#: change le seuil, c'est-a-dire mesurerait la constante contre elle-meme.
SEUIL_DIVERGENCE_BRUTE_LITTERAL = 5.0
SEUIL_DEGRADATION_MAXIMALE_LITTERAL = 25.0


def _divergence_brute(*, moyenne: float):
    """Une mesure de divergence brute, par le **vrai** type de la couche couleur.

    `exceeds` est calcule par le vrai predicat du module et non pose a la main: un
    booleen ecrit ici mesurerait le test, pas le code.
    """
    from mixed_media_utility import color_metrics
    return cc.RawDivergenceAssessment(
        page_id="lot_temoin_0001-p1",
        source_page_id="calibration-0",
        divergence_id=color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID,
        threshold_de76=SEUIL_DIVERGENCE_BRUTE_LITTERAL,
        mean_raw_de76=moyenne,
        paired_value_ids=("temoin-a", "temoin-b"),
        exceeds=color_metrics.raw_divergence_exceeds(
            moyenne, color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID),
    )


def _acceptation(*, degradation_maximale: float | None):
    """Un verdict d'acceptation par son vrai type, portant la degradation isolee."""
    return cc.AcceptanceVerdict(
        # Litteral, comme la production l'ecrit elle-meme (`color_calibration:1075`):
        # ce champ n'est pas la propriete mesuree ici, il est le decor minimal d'un
        # verdict que l'avertissement de l'AC 7 doit pouvoir lire.
        status="applied",
        mean_delta_e=1.0,
        max_delta_e=2.0,
        mean_delta_e_before=8.0,
        acceptance_id=cc.ACTIVE_COLOR_ACCEPTANCE_ID,
        max_degradation_de76=degradation_maximale,
    )


class _JournalDeTest:
    """Un journal qui **retient** ses avertissements, sans fichier ni configuration.

    Substitue au `logging.Logger` de la commande: la propriete mesuree ici est
    l'emission, et la faire transiter par un fichier ajouterait a l'assertion tout ce
    qui peut rater dans une configuration de journal.
    """

    def __init__(self) -> None:
        self.avertissements: list[str] = []

    def warning(self, gabarit, *arguments) -> None:
        self.avertissements.append(gabarit % arguments)


def _resultat(*, divergence=None, acceptation=None):
    """Le minimum de `PageCalibration` que la fonction d'avertissement lit."""
    return SimpleNamespace(raw_divergence=divergence, acceptance=acceptation)


def test_l_avertissement_de_divergence_brute_est_emis_au_dela_du_seuil() -> None:
    """AC 4: au-dela du seuil, on avertit -- et l'avertissement **sort**.

    Le mutant tue: le `if` remplace par `pass`. La valeur passee est strictement
    au-dessus du seuil ecrit en litteral, jamais lue sur le registre.
    """
    journal = _JournalDeTest()
    emis = cli._avertir_sur_une_page(
        journal, 1,
        _resultat(divergence=_divergence_brute(
            moyenne=SEUIL_DIVERGENCE_BRUTE_LITTERAL + 3.0)),
        page_id="lot_temoin_0001-p1")
    assert emis == 1, journal.avertissements
    assert len(journal.avertissements) == 1, journal.avertissements
    assert "Page 1" in journal.avertissements[0], journal.avertissements
    # Le chiffre de l'ecart voyage: un avertissement de l'AC 4 sans chiffre serait le
    # faux succes que le module refuse partout ailleurs.
    assert "8.0" in journal.avertissements[0], journal.avertissements


def test_aucun_avertissement_de_divergence_brute_sous_le_seuil() -> None:
    """Frontiere negative: sous le seuil, **rien** n'est ecrit.

    Sans elle, un `return 1` inconditionnel -- ou un `logger.warning` sorti du `if` --
    passerait le test precedent. La valeur est strictement sous le seuil litteral.
    """
    journal = _JournalDeTest()
    emis = cli._avertir_sur_une_page(
        journal, 2,
        _resultat(divergence=_divergence_brute(
            moyenne=SEUIL_DIVERGENCE_BRUTE_LITTERAL - 3.0)),
        page_id="lot_temoin_0001-p2")
    assert emis == 0, journal.avertissements
    assert journal.avertissements == []


def test_aucun_avertissement_quand_la_divergence_n_a_pas_ete_mesuree() -> None:
    """Le troisieme regime: mesure impossible, donc `exceeds` a `None`.

    Il n'est pas redondant avec le precedent: un `if raw_divergence is not None` seul
    -- sans la lecture d'`exceeds` -- passerait la frontiere du dessous mais leverait
    ici, parce que le constructeur du message refuse une divergence sans chiffre.
    """
    journal = _JournalDeTest()
    non_mesuree = cc.RawDivergenceAssessment(
        page_id="lot_temoin_0001-p3", source_page_id="calibration-0",
        divergence_id="color-divergence-2",
        threshold_de76=SEUIL_DIVERGENCE_BRUTE_LITTERAL,
        mean_raw_de76=None, exceeds=None, reason="aucun temoin apparie")
    assert cli._avertir_sur_une_page(
        journal, 3, _resultat(divergence=non_mesuree),
        page_id="lot_temoin_0001-p3") == 0
    assert journal.avertissements == []


def test_l_avertissement_de_degradation_maximale_est_emis_au_dela_du_plafond() -> None:
    """AC 7: la garde de degradation maximale avertit, et l'avertissement **sort**.

    Second mutant tue. Le plafond est ecrit en litteral; la valeur passee lui est
    strictement superieure.
    """
    journal = _JournalDeTest()
    emis = cli._avertir_sur_une_page(
        journal, 4,
        _resultat(acceptation=_acceptation(
            degradation_maximale=SEUIL_DEGRADATION_MAXIMALE_LITTERAL + 5.0)),
        page_id="lot_temoin_0001-p4")
    assert emis == 1, journal.avertissements
    assert len(journal.avertissements) == 1, journal.avertissements
    assert "Page 4" in journal.avertissements[0], journal.avertissements


def test_aucun_avertissement_de_degradation_sous_le_plafond() -> None:
    """Frontiere negative du second: sous le plafond, rien n'est ecrit."""
    journal = _JournalDeTest()
    assert cli._avertir_sur_une_page(
        journal, 5,
        _resultat(acceptation=_acceptation(
            degradation_maximale=SEUIL_DEGRADATION_MAXIMALE_LITTERAL - 5.0)),
        page_id="lot_temoin_0001-p5") == 0
    assert journal.avertissements == []


def test_les_deux_avertissements_sont_independants_et_se_cumulent() -> None:
    """Les deux `if` ne sont **pas** exclusifs, et c'est ce que le code annonce.

    Le commentaire de production dit pourquoi: « les mettre dans une branche `elif` les
    rendrait muets exactement dans le regime nominal, qui est le seul ou ils ont un
    sens ». Un `elif` injecte n'emettrait qu'un seul des deux et ce test le dirait --
    aucune des quatre assertions ci-dessus ne le ferait.
    """
    journal = _JournalDeTest()
    emis = cli._avertir_sur_une_page(
        journal, 6,
        _resultat(
            divergence=_divergence_brute(
                moyenne=SEUIL_DIVERGENCE_BRUTE_LITTERAL + 3.0),
            acceptation=_acceptation(
                degradation_maximale=SEUIL_DEGRADATION_MAXIMALE_LITTERAL + 5.0)),
        page_id="lot_temoin_0001-p6")
    assert emis == 2, journal.avertissements
    assert len(journal.avertissements) == 2, journal.avertissements


def test_une_page_sans_mesure_du_tout_n_ecrit_rien() -> None:
    """Le regime le plus frequent: aucune des deux grandeurs n'est portee.

    C'est le temoin qui empeche un `logger.warning` inconditionnel de passer les six
    tests ci-dessus.
    """
    journal = _JournalDeTest()
    assert cli._avertir_sur_une_page(
        journal, 7, _resultat(), page_id="lot_temoin_0001-p7") == 0
    assert journal.avertissements == []


def test_la_boucle_de_scan_appelle_bien_la_fonction_d_avertissement() -> None:
    """L'extraction n'a pas debranche l'emission de la commande.

    Sans ce test, les sept ci-dessus mesureraient une fonction que la boucle de scan
    n'appellerait plus -- exactement la panne que l'extraction devait rendre visible.
    Lu au source (AST), parce que l'exercer demanderait un scan complet, ce que le
    budget de l'AC 9 exclut.

    Adaptation 5.26 (extraction, AC 2): la boucle d'avertissements vit desormais dans
    `_ecrire_le_lot_detecte`, la moitie aval extraite de `scan_command` que `scan` et
    `scan-write` appellent tous deux -- l'invariant (emission cablee, jamais
    dedoublee) se mesure a l'endroit ou le code est parti.

    Adaptation 11.4b (lot S1): ce corps a fait un pas de plus et vit dans le module de
    coeur `scan_write` (`ecrire_le_lot_detecte`), d'ou `cli.py` ne peut plus l'appeler
    autrement qu'en enveloppeur. Meme mesure, meme assertion, un fichier plus loin.
    """
    import ast
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "scan_write.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    corps = [n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef) and n.name == "ecrire_le_lot_detecte"]
    assert len(corps) == 1, len(corps)
    appels = {ast.unparse(n.func) for n in ast.walk(corps[0]) if isinstance(n, ast.Call)}
    assert "_avertir_sur_une_page" in appels, sorted(appels)
    # Et l'emission ne s'est pas dedoublee dans la commande: un second `logger.warning`
    # portant l'un des deux constructeurs de message serait une seconde redaction.
    constructeurs = {appel for appel in appels
                     if "warning_message" in appel}
    assert constructeurs == set(), sorted(constructeurs)


# ---------------------------------------------------------------------------
# `EPIC5-ARB-103` -- aucun profil par defaut au projet, ca se dit
# ---------------------------------------------------------------------------


def test_l_absence_de_profil_designe_nomme_les_deux_gestes_et_le_scan_brut(
    tmp_path,
) -> None:
    """Mots d'Egan: « le dire et proposer un scan brut ou inviter a designer un defaut ».

    L'avertissement existait deja (`EPIC5-ARB-83` decision 5); ce qui manquait est qu'il
    **nomme le geste** -- la commande `set-default-profile` -- et qu'il pose le choix au
    lieu de constater une absence.

    **Le comportement ne change pas**: la fonction rend `None` (lot livre en brut),
    jamais un refus, jamais un repli vers un profil trouve dans le projet. Les deux
    faits sont assertes ensemble: un message enrichi qui aurait au passage introduit un
    repli serait le defaut que `EPIC5-ARB-83` supprime.
    """
    journal = _JournalDeTest()
    assert cli._resolve_designated_correction(
        tmp_path, None, journal, correction_requested=True) is None
    assert len(journal.avertissements) == 1, journal.avertissements
    message = journal.avertissements[0]
    # Les deux gestes, chacun avec sa commande complete, et le nom de la commande
    # dediee ecrit **en litteral**: lu sur la constante, un renommage silencieux
    # laisserait le test vert et l'operateur devant une commande inexistante.
    assert "set-default-profile" in message, message
    assert "--profil" in message, message
    assert "--project" in message, message
    # Le choix est pose, et le scan brut y figure comme une issue legitime.
    assert "brut" in message, message
    assert "choix" in message, message
    # Frontiere negative: le message ne promet aucun repli automatique.
    assert "n'est choisi a votre place" in message, message


def test_le_nom_de_la_commande_de_profil_par_defaut_est_analysable(monkeypatch) -> None:
    """Le geste nomme par le message **existe** dans le parseur.

    Une invite qui nommerait une commande que le parseur n'accepte pas enverrait
    l'operateur taper une commande inexistante -- meme regle que l'invite de bascule de
    `EPIC5-ARB-92`. Le nom est confronte au **vrai** parseur, ecrit en litteral.
    """
    vus: list = []
    monkeypatch.setattr(cli, "set_default_profile_command",
                        lambda args: vus.append(args) or 0)
    assert cli.main(["set-default-profile", "--project", str(REPO_ROOT),
                     "--profil", "p.json"]) == 0
    (args,) = vus
    assert args.profil == "p.json"


# ---------------------------------------------------------------------------
# `EPIC5-ARB-101` -- l'aide de `calibrate` ne promet plus `<chain_id>.json`
# ---------------------------------------------------------------------------


def test_l_aide_de_calibrate_ne_promet_plus_un_fichier_nomme_par_la_chaine(
    capsys,
) -> None:
    """Reste inerte de l'AC 8quater: le nom du fichier a change, l'aide non.

    Depuis l'AC 8quater, `write_profile` nomme le fichier par le **slug de l'etiquette**
    et le `chain_id` seulement a defaut. Une aide qui promet `<chain_id>.json` envoie
    l'operateur chercher un fichier qui porte un autre nom -- et il en conclut que la
    commande n'a rien ecrit. Meme regle que la frontiere du mot « seuil » de 5.16: une
    aide qui nomme une chose inexistante la fait chercher.

    Le motif est reconstitue plutot qu'ecrit en clair, pour que ce fichier ne se cite
    pas lui-meme si le balayage venait a l'englober.
    """
    motif = "<chain" + "_id>.json"
    aides = []
    for argv in (["scan", "--help"], ["scan", "calibrate", "--help"]):
        with pytest.raises(SystemExit):
            cli.main(argv)
        aides.append(capsys.readouterr().out)
    # Temoin de capture: sans lui, la frontiere serait verte sur une aide vide.
    assert all(aide.strip() for aide in aides), aides
    assert any("calibrate" in aide for aide in aides), aides
    fautives = [aide for aide in aides if motif in aide]
    assert fautives == [], fautives


# ---------------------------------------------------------------------------
# `EPIC5-ARB-99` geste 3 -- l'invite d'ecrasement est atteignable depuis un terminal
# ---------------------------------------------------------------------------
#
# Le module de profil porte deja tout: la detection de collision, le texte de la
# question (`COLLISION_PROMPT`), l'empreinte differenciante, et les deux issues sous
# `confirm_overwrite=` -- eprouves dans `test_profil_nomme_par_l_operateur.py`. Ce qui
# manquait est le **cablage**: sans lui, `confirm_overwrite` valait toujours `None` et
# l'invite d'Egan n'existait sur aucun chemin d'operateur.
#
# **Le comportement etait deja sur avant ce cablage**, et c'est ce qui rendait le trou
# discret: hors terminal le defaut est l'empreinte differenciante, jamais l'ecrasement.
# Le cablage n'ouvre donc pas une garde, il ouvre un **choix**.


class _EntreeQuiSeDitTerminal:
    """Une entree standard qui se declare terminal sans en etre un.

    Meme dispositif que `test_bascule_calibration_pile_seule`: c'est le seul moyen
    d'exercer le regime interactif dans une suite qui, elle, ne l'est jamais.
    """

    def isatty(self) -> bool:
        return True


def _terminal(monkeypatch, reponse: str | None) -> list[str]:
    """Declarer l'entree interactive et scripter la reponse. Rend les invites posees."""
    invites: list[str] = []
    monkeypatch.setattr(sys, "stdin", _EntreeQuiSeDitTerminal())

    def _input(*args):
        invites.append("".join(str(a) for a in args))
        if reponse is None:
            raise EOFError
        return reponse

    monkeypatch.setattr("builtins.input", _input)
    return invites


def test_hors_terminal_aucune_confirmation_n_est_fournie_au_module(monkeypatch) -> None:
    """Le regime des scripts, de la CI et de ces 4900 tests: personne pour repondre.

    `None` est la valeur que `write_profile` interprete comme « pas d'humain », et sur
    laquelle il prend l'empreinte differenciante. La rendre autrement -- un appelable
    qui rendrait `True` par defaut, par exemple -- serait l'ecrasement silencieux que
    `EPIC5-ARB-99` supprime.

    L'invite est verifiee **absente** et pas seulement inoperante: un `input()` pose
    hors terminal leve `EOFError` sous pytest et bloque sous `cron`.
    """
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail(
        "une invite d'ecrasement a ete posee hors terminal"))
    assert cli._confirmation_d_ecrasement_de_profil() is None


def test_sur_un_terminal_la_confirmation_fournie_est_l_invite(monkeypatch) -> None:
    """Temoin positif du precedent: derriere un terminal, l'invite est bien fournie.

    Sans lui, le test ci-dessus serait vrai d'un cablage qui rendrait `None` partout,
    c'est-a-dire de l'etat d'avant ce lot.
    """
    monkeypatch.setattr(sys, "stdin", _EntreeQuiSeDitTerminal())
    assert cli._confirmation_d_ecrasement_de_profil() is cli._ask_overwrite_profile


@pytest.mark.parametrize("reponse", ["y", "Y", "oui", "o", "yes"])
def test_l_invite_d_ecrasement_rend_vrai_sur_un_oui_explicite(
    monkeypatch, capsys, reponse,
) -> None:
    """`Y` ecrase, et c'est un geste explicite: le seul chemin ou un profil se perd.

    La question posee nomme les deux choses dont l'operateur a besoin pour repondre --
    le nom du fichier et la chaine qui l'occupe --, et son texte vient du module, jamais
    d'une seconde redaction ecrite ici.
    """
    invites = _terminal(monkeypatch, reponse)
    assert cli._ask_overwrite_profile("600-tif-abcdef012345", "hp-envy-4520") is True
    assert len(invites) == 1, invites
    sortie = capsys.readouterr().out
    assert "hp-envy-4520" in sortie, sortie
    assert "600-tif-abcdef012345" in sortie, sortie
    assert "ecraser" in sortie.lower(), sortie
    assert "[y/N]" in sortie, sortie


@pytest.mark.parametrize("reponse", ["n", "N", "non", "", "   ", "peut-etre", None])
def test_l_invite_d_ecrasement_rend_faux_par_defaut(monkeypatch, reponse) -> None:
    """**Le defaut est de ne rien detruire**, et c'est l'inverse des deux autres invites.

    L'AC 5 et la bascule de `EPIC5-ARB-92` appliquent par defaut, parce que le geste par
    defaut y sert l'operateur. Ici le geste par defaut est celui qui ne perd aucun
    profil: entree vide, fin de flux (`None` ci-dessus) et reponse incomprise gardent
    les deux fichiers, exactement comme la branche hors terminal.

    Sans ce parametrage, un `return not reponse.startswith("n")` -- la forme des deux
    autres invites du fichier, copiee par reflexe -- passerait le test du `oui` et
    ferait ecraser sur une frappe d'Entree.
    """
    _terminal(monkeypatch, reponse)
    assert cli._ask_overwrite_profile("600-tif-abcdef012345", "hp-envy-4520") is False


def test_le_texte_de_la_question_n_est_pas_reecrit_dans_la_cli() -> None:
    """La phrase d'Egan vit dans le module, la CLI la met en forme -- une seule fois.

    Une seconde redaction divergerait de celle que `write_profile` documente, et
    l'operateur lirait deux questions differentes pour la meme decision selon le chemin
    emprunte.
    """
    import ast
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    corps = [n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef) and n.name == "_ask_overwrite_profile"]
    assert len(corps) == 1, len(corps)
    rendu = ast.unparse(corps[0])
    assert "COLLISION_PROMPT" in rendu, rendu
    # Frontiere: aucun **litteral executable** de la fonction ne recopie la phrase. Le
    # balayage porte sur les constantes de chaine du corps, docstring exclu: le
    # docstring cite le mandat d'Egan verbatim, ce qui est la trace de la decision et
    # non une seconde redaction -- un balayage du fichier entier se trouverait
    # lui-meme, comme les motifs de `test_restes_inertes_retires.py`.
    motif = "porte deja " + "ce nom"
    litteraux = [n.value for n in ast.walk(corps[0])
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert litteraux, rendu
    executables = litteraux[1:] if ast.get_docstring(corps[0]) else litteraux
    fautifs = [texte for texte in executables if motif in texte]
    assert fautifs == [], fautifs
    # Temoin: le balayage voit bien des litteraux executables (le `[y/N]` de l'invite).
    assert any("[y/N]" in texte for texte in executables), executables


def test_les_trois_chemins_d_ecriture_de_profil_cablent_la_confirmation() -> None:
    """Les **trois** sites, pas un seul: le site oublie serait le trou silencieux.

    Un cablage pose sur deux chemins sur trois ne se voit pas -- l'operateur qui
    emprunte le troisieme n'obtient jamais l'invite et n'a aucun moyen de le savoir.
    Les trois sont donc nommes et lus au source, comme les frontieres de perimetre de
    5.19 et 5.22.
    """
    import ast
    source = (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    fonctions = {n.name: n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef)}
    # **Story 11.4b (lot S1): le troisieme site a change de nom, pas de nature.**
    # L'import du profil designe a suivi la moitie aval du scan dans le module de
    # coeur `scan_write`, qui n'a pas le droit de lire `stdin`: le predicat
    # d'interactivite y entre desormais par un parametre nomme, cable **ici**, dans
    # l'enveloppeur. Les trois sites restent trois, et chacun cable toujours le
    # predicat plutot que l'invite nue -- ce que le mot-cle change ne change pas.
    #
    # **Story 11.6 (lot B): DEUX des trois sites cablent maintenant par une
    # fabrique d'options.** Les corps qu'ils enveloppaient -- l'ecriture d'un lot
    # detecte, la consignation d'un profil de chaine -- vivent au coeur, qui
    # n'a pas le droit de lire `stdin`; le predicat y entre par
    # `_options_d_ecriture_du_terminal` et `_options_de_calibration_du_terminal`,
    # une fabrique par voie, parce que chaque voie a desormais **deux** appelants
    # et que deux lectures divergentes du meme `args` produiraient deux passes
    # differentes. Ce qui est mesure ne change pas d'un iota: le site existe, il
    # est unique, et il passe le PREDICAT et non l'invite nue.
    for nom, appelee, mot_cle in (
            ("_options_de_calibration_du_terminal", "dict",
             "confirmer_l_ecrasement"),
            ("_options_d_ecriture_du_terminal", "dict",
             "confirmer_l_ecrasement"),
            ("set_default_profile_command", "import_designated_profile",
             "confirm_overwrite")):
        assert nom in fonctions, sorted(fonctions)
        cables = [
            noeud for noeud in ast.walk(fonctions[nom])
            if isinstance(noeud, ast.Call)
            and appelee in ast.unparse(noeud.func)
            and any(mot.arg == mot_cle for mot in noeud.keywords)
        ]
        assert len(cables) == 1, (nom, ast.unparse(fonctions[nom])[:400])
        (cable,) = cables
        (mot,) = [m for m in cable.keywords if m.arg == mot_cle]
        # La valeur passee est le predicat d'interactivite, jamais l'invite nue: la
        # passer nue ferait poser un `input()` sous `cron`.
        assert ast.unparse(mot.value) == "_confirmation_d_ecrasement_de_profil()", \
            ast.unparse(mot.value)


# ---------------------------------------------------------------------------
# `EPIC5-ARB-104` -- le motif du bandeau entre dans le fichier de profil
# ---------------------------------------------------------------------------
#
# Troisieme et dernier etage du defaut. Les deux premiers sont fermes ailleurs: la
# mesure distingue desormais ses cinq regimes (`_sample_calibration_witness_band` rend
# `(temoins, motif)`), et le document de profil sait accueillir le champ. Sans le
# cablage ci-dessous, le motif mourait **dans la memoire de la commande**: le fichier
# ecrit ne portait que le vide, donc apres relecture une chaine dont la page a bel et
# bien ete lue -- bandeau imprime puis rogne au redressage -- ressortait
# `raw_divergence_no_calibration_sheet`, c'est-a-dire « aucune feuille de calibration ».
# C'est la faussete **persistee** que la revue a trouvee, et elle survivait a la
# correction des deux premiers etages.

#: Le motif vise, ecrit **en litteral**. Lu sur `RAW_DIVERGENCE_BAND_REASONS`, le test
#: resterait vert apres le mutant qui renomme le vocabulaire, alors que tous les
#: profils deja ecrits porteraient l'ancien mot.
MOTIF_BANDEAU_ROGNE_LITTERAL = "raw_divergence_witness_band_cropped"


def _lot_correction_sans_bandeau(motif: str):
    """Une correction ajustee dont le bandeau n'a rien rendu, **et qui dit pourquoi**."""
    correction = _lot_correction_ajuste()
    return cc.LotCorrection(
        source_page_id=correction.source_page_id,
        template_id=correction.template_id,
        profile=correction.profile,
        correction_form_id=correction.correction_form_id,
        witness_raw_bgr=(),
        witness_band_reason=motif)


def test_le_motif_du_bandeau_est_ecrit_dans_le_fichier_de_profil(
    tmp_path, monkeypatch,
) -> None:
    """Verifie sur le **fichier relu**, jamais sur l'objet en memoire.

    C'est le fichier qui voyage jusqu'au scan suivant, des semaines plus tard, et c'est
    lui qui portait la faussete. Le motif est confronte a son litteral: « rogne » et
    « papier nu » sont deux diagnostics opposes pour l'operateur -- l'un se corrige au
    redressage, l'autre en reimprimant la feuille.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(
        scan_calibrate, "_fit_lot_correction",
        lambda *a, **k: _lot_correction_sans_bandeau(MOTIF_BANDEAU_ROGNE_LITTERAL))
    chaine = _chaine_derivee(folder, tmp_path)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    document = calibration_profile.read_profile(project_dir, chaine)
    assert calibration_profile.witness_band_reason_of_document(document) == (
        MOTIF_BANDEAU_ROGNE_LITTERAL)
    # Le motif appartient bien au vocabulaire ferme du module qui le produit: un motif
    # ecrit au fichier et inconnu de la relecture ne vaudrait pas mieux que le vide.
    assert MOTIF_BANDEAU_ROGNE_LITTERAL in cc.RAW_DIVERGENCE_BAND_REASONS


def test_un_bandeau_mesure_n_ecrit_aucun_motif(tmp_path, monkeypatch) -> None:
    """Frontiere negative: le champ est absent quand il n'y a rien a expliquer.

    Meme patron que `witness_raw_bgr` (champ absent contre valeur explicite), et c'est
    volontairement le meme: « pas de motif » se relit « le bandeau a ete mesure », et
    un motif pose sur un bandeau lu enverrait diagnostiquer une panne qui n'a pas eu
    lieu. Sans cette frontiere, un cablage qui ecrirait toujours un motif -- ou une
    constante -- passerait le test ci-dessus.
    """
    project_dir = tmp_path / "projet"
    folder = _write_scan_folder(tmp_path)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_avec_temoins())
    chaine = _chaine_derivee(folder, tmp_path)
    assert cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ]) == 0

    brut = calibration_profile.profile_path(project_dir, chaine).read_text(
        encoding="utf-8")
    assert calibration_profile.WITNESS_BAND_REASON_FIELD not in brut, brut
    assert calibration_profile.witness_band_reason_of_document(
        calibration_profile.read_profile(project_dir, chaine)) == ""


# ===========================================================================
# Vague 4, couche 1 bis : les refus de `calibrate`, en ENSEMBLE EXACT
# ===========================================================================
#
# **Pourquoi ces tests existent, et ils sont nes de trois survivants.** La
# couche 1 bis de la revue de la vague 4 a injecte trois mutants dans ce
# module ; les trois ont survecu :
#
# * `M2` -- `motif=REFUS_PAGE_INEXPLOITABLE` remplace par
#   `motif=REFUS_AUCUNE_PAGE_DE_CALIBRATION` : **218 verdicts identiques**.
#   Les deux refus etaient interchangeables pour tous les bancs du depot, alors
#   que leurs remedes sont opposes -- *rescanner la mire* d'un cote (la feuille
#   est la, elle est abimee), *reimprimer la mire* de l'autre (la feuille est
#   absente). C'est la distinction qu'`EPIC5-ARB-70` a posee ;
# * `M3` -- l'invite de nommage remontee AVANT les trois gardes : **208
#   verdicts identiques**. Le module promet deux fois qu'on ne demande jamais a
#   l'operateur de nommer un profil qui ne sera pas ecrit ; rien ne le mesurait ;
# * la critique **structurelle** : aucun banc ne mesurait que l'ensemble
#   ATTEIGNABLE des motifs est **exactement** la table publiee. `scan_write` le
#   fait de son cote (`test_scan_write_noyau.py`,
#   `test_les_refus_du_document_sont_EXACTEMENT_ceux_de_la_table`) ; c'est ce
#   parcours-la qui aurait attrape `M2` a l'ecriture.
#
# Les scenarios portent sur le **point d'entree de coeur**
# (`consigner_le_profil_de_chaine`) et non sur `cli.main` : c'est lui qui porte
# les gardes, le motif et l'invite, et c'est lui que la TUI appelle.

from mixed_media_utility import scan_detection  # noqa: E402


#: Ce qui est passe a la place de la detection. Un objet nomme dit ce fait mieux
#: qu'un `None`.
#:
#: **`pages=()` n'est plus decoratif depuis `D2`** (2026-09-06). Ce commentaire
#: disait que `consigner_le_profil_de_chaine` « ne s'en sert que pour appeler
#: `_fit_lot_correction`, qui est substitue dans tous les scenarios » : c'etait
#: vrai, ca ne l'est plus. La detection est aussi lue par
#: `etiquette_du_profil`, qui y cherche le libelle de chaine imprime sur la
#: page. La liste vide est donc un regime REEL -- aucune page de calibration
#: declaree --, et elle fait retomber la precedence sur le `chain_id`, ce que
#: ces scenarios attendent.
DETECTION_SUBSTITUEE = SimpleNamespace(pages=())


def _lot_correction_inexploitable():
    """Une page de calibration **presente et lue**, que l'ajustement refuse.

    C'est le regime que `REFUS_PAGE_INEXPLOITABLE` nomme, et il ne se confond
    pas avec l'absence : la mire a ete scannee, ses pastilles sont hors
    tolerance (ou son bandeau illisible, ou le seuil ArUco a lache).
    `available` est `False` parce que `profile` est `None`.
    """
    return cc.LotCorrection(
        source_page_id="calibration-0",
        template_id=couleur.TEMPLATE,
        profile=None,
        failure_reason=cc.FAILURE_PATCHES_NOT_FOUND,
        failure_message="Page de calibration 'calibration-0' non relisable.")


def _rapport_sans_page():
    """Un rapport d'ingestion dont aucune identite de chaine ne se derive."""
    return SimpleNamespace(declared_dpi=600, pages=())


def _bloquer_le_profil_par_son_fichier(project_dir: Path, folder: Path) -> None:
    """Le chemin du profil **est un dossier** : `os.replace` leve."""
    _bloquer_le_fichier_de_profil(
        project_dir, _chaine_derivee(folder, project_dir.parent))


#: **Les cinq scenarios de refus, un par motif de la table publiee** -- et deux
#: pour `profil-non-ecrit`, dont la garde est une **disjonction** de deux
#: familles d'exception (`OSError` nue au `mkdir`, `ProfileReadError` au
#: remplacement atomique). Une disjonction dont une moitie n'est jamais
#: atteinte se laisse retirer sans qu'un test ne bouge : c'est le mutant `M06`
#: de la campagne du lot B, cote `scan_write`.
#:
#: `ajustement` est ce que `_fit_lot_correction` rend (ou leve) ; `sabotage`
#: edite le projet sur le disque ; `rapport` remplace le rapport d'ingestion
#: reel ; `invite_attendue` est le nombre de fois que l'invite de nommage doit
#: avoir ete posee quand ce refus tombe.
SCENARIOS_DE_REFUS_DE_CALIBRATION: tuple[tuple, ...] = (
    (scan_calibrate.REFUS_IDENTITE_NON_DERIVABLE,
     _lot_correction_ajuste, None, _rapport_sans_page, 0),
    (scan_calibrate.REFUS_AUCUNE_PAGE_DE_CALIBRATION,
     lambda: None, None, None, 0),
    (scan_calibrate.REFUS_PAGE_INEXPLOITABLE,
     _lot_correction_inexploitable, None, None, 0),
    (scan_calibrate.REFUS_PROFIL_NON_ECRIT,
     _lot_correction_ajuste,
     lambda project_dir, folder: _bloquer_le_dossier_des_profils(project_dir),
     None, 1),
    # Le MEME motif par l'autre moitie de la garde : la table nomme un refus,
    # pas un chemin, et les deux familles d'exception doivent y mener.
    (scan_calibrate.REFUS_PROFIL_NON_ECRIT,
     _lot_correction_ajuste, _bloquer_le_profil_par_son_fichier, None, 1),
)



def _refuser_par_une_pile_mixte(tmp_path, monkeypatch, nom):
    """Le refus d'`EPIC11-ARB-266`, par le point d'entree qui le porte.

    Les cinq autres scenarios entrent par `consigner_le_profil_de_chaine` ;
    celui-ci ne le peut pas, et **c'est la propriete qui compte** : la garde de
    pile mixte est deliberement posee dans `calibrer_la_chaine` et pas dans ce
    corps-la, parce que le tri en vrac de la 5.24 appelle ce corps sur une pile
    mixte par construction. Un scenario qui entrerait par le meme point que les
    autres mesurerait donc l'inverse de ce qui est voulu.

    La detection est substituee -- deux pages, la mire et une planche : ce qui
    se mesure ici est le refus, pas la lecture d'un raster.
    """
    base = tmp_path / nom
    base.mkdir(parents=True, exist_ok=True)
    folder = _write_scan_folder(base)
    project_dir = base / "projet"
    project_layout.ensure_project_layout(project_dir)

    class _Page:
        def __init__(self, payload):
            self.payload = payload

    class _Detection:
        pages = (_Page({"scan_chain_label": "epson-v850", "page_index": 0}),
                 _Page({champ: f"{champ}-x"
                        for champ in reconstruction._LOT_LEVEL_FIELDS}))

    monkeypatch.setattr(scan_calibrate.scan_detection, "detect_lot_pages",
                        lambda *a, **k: _Detection())
    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate.calibrer_la_chaine(project_dir, folder, dpi=600)
    return leve.value, []

#: Les scenarios qui n'entrent PAS par `consigner_le_profil_de_chaine`, avec
#: leur propre declencheur. `EPIC11-ARB-266` en est le premier, et sa presence
#: ici est ce qui rend la table du dessous exacte sans mentir sur le chemin :
#: sa garde vit dans `calibrer_la_chaine`, et le banc entre par la meme porte
#: que l'operateur.
SCENARIOS_DE_REFUS_PAR_UN_AUTRE_POINT_D_ENTREE: tuple[tuple, ...] = (
    (scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION,
     _refuser_par_une_pile_mixte),
)


def _refuser_la_calibration(tmp_path, monkeypatch, nom, ajustement, sabotage,
                            rapport):
    """Monter un scenario de refus et rendre `(refus, invites)`.

    `invites` est la liste des `chain_id` pour lesquels l'invite de nommage a
    ete posee : c'est elle qui mesure le **placement** de l'invite, et non une
    lecture du source.
    """
    base = tmp_path / nom
    base.mkdir(parents=True, exist_ok=True)
    folder = _write_scan_folder(base)
    project_dir = base / "projet"
    project_layout.ensure_project_layout(project_dir)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: ajustement())
    reel = (scan_ingest.ingest_scan_lot(project_dir, folder, dpi=600)
            if rapport is None else rapport())
    if sabotage is not None:
        sabotage(project_dir, folder)

    invites: list[str] = []

    def demander_le_nom(chain_id: str) -> tuple[str, str]:
        invites.append(chain_id)
        return "", ""

    with pytest.raises(scan_calibrate.RefusDeCalibration) as leve:
        scan_calibrate.consigner_le_profil_de_chaine(
            project_dir, reel, DETECTION_SUBSTITUEE, dpi=600,
            scan_locator=folder,
            demander_le_nom_et_le_commentaire=demander_le_nom)
    return leve.value, invites


@pytest.mark.parametrize(
    "motif,ajustement,sabotage,rapport,invite_attendue",
    SCENARIOS_DE_REFUS_DE_CALIBRATION,
    ids=[f"{scenario[0]}-{rang}"
         for rang, scenario in enumerate(SCENARIOS_DE_REFUS_DE_CALIBRATION)])
def test_chaque_scenario_leve_SON_refus_de_calibration_nomme(
        tmp_path, monkeypatch, motif, ajustement, sabotage, rapport,
        invite_attendue) -> None:
    """Le motif est **teste**, jamais devine sur un bout de phrase.

    Parametre un a un plutot qu'en un seul balayage : un echec dit **quel**
    refus s'est mis a en rendre un autre. C'est ce qui manquait quand `M2` a
    survecu -- « page inexploitable » et « aucune page » etaient
    interchangeables pour la totalite du depot.
    """
    refus, _invites = _refuser_la_calibration(
        tmp_path, monkeypatch, f"{motif}-{invite_attendue}", ajustement,
        sabotage, rapport)
    assert refus.motif == motif, str(refus)
    # Le message reste ce qu'un terminal imprime, et il n'est pas vide : le
    # motif ne le remplace pas, il l'accompagne.
    assert str(refus).strip(), motif


def test_les_refus_de_la_calibration_sont_EXACTEMENT_ceux_de_la_table(
        tmp_path, monkeypatch) -> None:
    """La table publiee, en ensemble **EXACT** et dans les deux sens.

    « Une assertion positive laisse passer toute divergence supplementaire »
    (`CLAUDE.md`) : « ce motif est leve » ne mesure rien, « l'ensemble des
    motifs atteignables est **exactement** celui que la table publie » mesure
    la table ET son unicite. Un motif publie qu'aucun chemin n'atteint est un
    reste inerte -- ce que `REFUS_PAGE_INEXPLOITABLE` etait devenu ; un refus
    atteignable absent de la table est un refus qu'aucune interface ne saura
    nommer.
    """
    atteints = set()
    for rang, (motif, ajustement, sabotage, rapport, _invite) in enumerate(
            SCENARIOS_DE_REFUS_DE_CALIBRATION):
        refus, _invites = _refuser_la_calibration(
            tmp_path, monkeypatch, f"exact-{motif}-{rang}", ajustement,
            sabotage, rapport)
        atteints.add(refus.motif)
    for rang, (motif, declencheur) in enumerate(
            SCENARIOS_DE_REFUS_PAR_UN_AUTRE_POINT_D_ENTREE):
        refus, _invites = declencheur(
            tmp_path, monkeypatch, f"exact-autre-{motif}-{rang}")
        atteints.add(refus.motif)
    assert atteints == set(scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION)
    # Cinq scenarios pour quatre motifs : `profil-non-ecrit` a DEUX familles
    # d'exception, et les deux sont exercees.
    assert len(SCENARIOS_DE_REFUS_DE_CALIBRATION) == 5
    # **Et le cinquieme motif entre par une AUTRE porte**, ce qui est une
    # propriete du produit et non un detail de banc : la garde de pile mixte
    # est dans `calibrer_la_chaine`, pas dans le corps que le tri en vrac
    # appelle (`EPIC11-ARB-266`).
    assert len(SCENARIOS_DE_REFUS_PAR_UN_AUTRE_POINT_D_ENTREE) == 1
    # Temoin de cardinal : la table ne s'est pas videe sous la mesure.
    assert len(scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION) == 5
    # Et les quatre sont **distincts** : une table qui repeterait un nom
    # satisferait l'egalite d'ensembles ci-dessus. C'est litteralement la forme
    # de `M2`, vue depuis la table plutot que depuis le `raise`.
    assert len(set(scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION)) == 5


def test_l_ordre_des_gardes_de_la_calibration_est_celui_de_la_table(
        tmp_path, monkeypatch) -> None:
    """« L'ordre du tuple est l'ordre des gardes [...] et il est mesure comme tel ».

    Mesure sur des montages qui violent **deux** gardes a la fois : c'est le
    seul montage ou l'ordre se voit. Un scan dont l'identite n'est pas derivable
    ET dont la page de calibration est absente doit rendre le refus d'IDENTITE
    -- s'il rendait celui de la page, c'est que la derive serait passee apres.
    """
    # Garde 1 (identite) avant garde 2 (page absente).
    refus, _invites = _refuser_la_calibration(
        tmp_path, monkeypatch, "ordre-identite-avant-page",
        lambda: None, None, _rapport_sans_page)
    assert refus.motif == scan_calibrate.REFUS_IDENTITE_NON_DERIVABLE, str(refus)

    # Garde 2 (page absente) avant garde 4 (ecriture du profil).
    refus, _invites = _refuser_la_calibration(
        tmp_path, monkeypatch, "ordre-page-avant-ecriture",
        lambda: None,
        lambda project_dir, folder: _bloquer_le_dossier_des_profils(project_dir),
        None)
    assert refus.motif == scan_calibrate.REFUS_AUCUNE_PAGE_DE_CALIBRATION, str(refus)

    # Garde 3 (page inexploitable) avant garde 4 (ecriture du profil).
    refus, _invites = _refuser_la_calibration(
        tmp_path, monkeypatch, "ordre-inexploitable-avant-ecriture",
        _lot_correction_inexploitable,
        lambda project_dir, folder: _bloquer_le_dossier_des_profils(project_dir),
        None)
    assert refus.motif == scan_calibrate.REFUS_PAGE_INEXPLOITABLE, str(refus)


@pytest.mark.parametrize(
    "motif,ajustement,sabotage,rapport,invite_attendue",
    SCENARIOS_DE_REFUS_DE_CALIBRATION,
    ids=[f"{scenario[0]}-{rang}"
         for rang, scenario in enumerate(SCENARIOS_DE_REFUS_DE_CALIBRATION)])
def test_l_invite_de_nommage_est_posee_APRES_le_dernier_refus_qui_la_precede(
        tmp_path, monkeypatch, motif, ajustement, sabotage, rapport,
        invite_attendue) -> None:
    """L'ORDRE est un contrat : « ici et pas plus haut ».

    Le module le promet deux fois -- dans le corps et dans la docstring du
    parametre -- : « tous les refus sont derriere, donc on ne demande **jamais**
    a l'operateur de nommer un profil qui ne sera pas ecrit ». Remontee avant
    les gardes, l'invite pose deux `input()` bloquants sur un terminal -- ou un
    ecran modal de nommage sous la TUI -- pour un profil qui n'existera jamais.

    Le cardinal est mesure **exactement**, jamais « au moins zero » : les trois
    refus qui precedent l'invite en attendent **0**, et `profil-non-ecrit`, qui
    tombe apres elle, en attend **1**. Un scenario qui n'attendrait rien de
    positif rendrait la mesure vide -- une invite jamais cablee la satisferait.
    """
    _refus, invites = _refuser_la_calibration(
        tmp_path, monkeypatch, f"invite-{motif}-{invite_attendue}", ajustement,
        sabotage, rapport)
    assert len(invites) == invite_attendue, invites


def test_l_invite_de_nommage_EST_bien_posee_sur_le_chemin_qui_aboutit(
        tmp_path, monkeypatch) -> None:
    """Le volet symetrique, sans lequel le parcours ci-dessus serait vide.

    Un rappel qu'aucun chemin n'appelle satisfait « zero invite sur un refus »
    sans rien mesurer. Ici la passe **aboutit** : l'invite est posee une fois,
    et elle recoit le `chain_id` -- c'est-a-dire le nom par defaut que
    l'operateur voit dans la question.
    """
    base = tmp_path / "invite-abouti"
    base.mkdir()
    folder = _write_scan_folder(base)
    project_dir = base / "projet"
    project_layout.ensure_project_layout(project_dir)
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _lot_correction_ajuste())
    rapport = scan_ingest.ingest_scan_lot(project_dir, folder, dpi=600)

    invites: list[str] = []

    def demander_le_nom(chain_id: str) -> tuple[str, str]:
        invites.append(chain_id)
        return "mire-atelier", "relu au survol"

    consigne = scan_calibrate.consigner_le_profil_de_chaine(
        project_dir, rapport, DETECTION_SUBSTITUEE, dpi=600,
        scan_locator=folder,
        demander_le_nom_et_le_commentaire=demander_le_nom)

    assert invites == [consigne.chain_id]
    assert consigne.etiquette == "mire-atelier"
    assert consigne.commentaire == "relu au survol"


# ===========================================================================
# Vague 4, couche 1 bis : `CODES_DE_SORTIE`, entree par entree
# ===========================================================================
#
# **Nee du survivant `M5`** : retirer l'entree
# `(scan_detection.ScanDetectionError, CODE_ERREUR)` de la table a survecu a
# **152 verdicts**. Sans elle, `code_de_sortie` rend `None`, l'enveloppeur
# **releve**, et la commande sort en trace Python nue la ou l'operateur doit
# lire `Erreur: <message>` et recevoir le code `1`.
#
# **Les trois familles sont ecrites EN LITTERAL ici, jamais lues de la table
# mesuree.** Un parametrage qui lirait `CODES_DE_SORTIE` perdrait simplement un
# cas de test quand une entree disparait -- c'est-a-dire qu'il resterait vert
# devant le mutant qu'il existe pour attraper.

#: Les trois familles que `scan ... calibrate` doit convertir en refus nomme.
FAMILLES_DU_REFUS_DE_CALIBRATION = (
    scan_calibrate.RefusDeCalibration,
    scan_ingest.ScanIngestError,
    scan_detection.ScanDetectionError,
)

#: Le code et le prefixe, recopies du comportement attendu et non lus des
#: constantes mesurees : lire `scan_calibrate.CODE_ERREUR` ferait un test
#: tautologique, exactement le defaut de la campagne de la story 5.9.
CODE_DU_REFUS_LITTERAL = 1
PREFIXE_DU_REFUS_LITTERAL = "Erreur: "


@pytest.mark.parametrize("classe", FAMILLES_DU_REFUS_DE_CALIBRATION,
                         ids=[f.__name__
                              for f in FAMILLES_DU_REFUS_DE_CALIBRATION])
def test_chaque_famille_de_la_table_des_codes_sort_en_refus_nomme(
        tmp_path, monkeypatch, capsys, classe) -> None:
    """La table est fermee **entree par entree**, pas seulement sur celles qu'un
    refus reel atteint.

    Deux niveaux dans le meme test : `code_de_sortie` rend `1` pour la famille
    (ce que la TUI lit, sans importer `cli.py`), et la commande imprime
    `Erreur: <message>` sans trace (ce que l'operateur lit). Les deux doivent
    coincider -- c'est la promesse de la table : « la TUI doit rendre le meme
    verdict que la CLI ».
    """
    panne = classe("panne simulee")
    assert scan_calibrate.code_de_sortie(panne) == CODE_DU_REFUS_LITTERAL, (
        f"{classe.__name__} n'est pas nommee par CODES_DE_SORTIE")

    base = tmp_path / f"codes-{classe.__name__}"
    base.mkdir()
    folder = _write_scan_folder(base)
    project_dir = base / "projet"

    def toujours_en_panne(*args, **kwargs):
        raise panne

    monkeypatch.setattr(scan_calibrate, "calibrer_la_chaine", toujours_en_panne)
    code = cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", "600", "calibrate",
    ])
    sortie = capsys.readouterr()
    assert code == CODE_DU_REFUS_LITTERAL, sortie.err
    assert PREFIXE_DU_REFUS_LITTERAL + str(panne) in sortie.err, sortie.err
    assert "Traceback" not in sortie.err, sortie.err


def test_la_table_des_codes_de_calibration_ne_porte_QUE_ces_trois_familles(
) -> None:
    """L'autre sens de l'ensemble exact : aucune entree en trop, aucun doublon.

    Le parcours ci-dessus ferme « chaque famille nommee est traitee ». Celui-ci
    ferme « et il n'y en a pas d'autre » : une famille ajoutee a la table sans
    etre voulue deguiserait un bug de programmation en code d'erreur ordinaire,
    ce que `code_de_sortie` documente refuser en rendant `None`.
    """
    familles = tuple(classe for classe, _code in scan_calibrate.CODES_DE_SORTIE)
    assert set(familles) == set(FAMILLES_DU_REFUS_DE_CALIBRATION)
    assert len(scan_calibrate.CODES_DE_SORTIE) == 3
    assert len(set(familles)) == 3
    # Et le code est le meme pour les trois : la table promet « tous au meme
    # code de sortie `1` et au meme prefixe `Erreur: ` ».
    assert {code for _classe, code in scan_calibrate.CODES_DE_SORTIE} == {
        CODE_DU_REFUS_LITTERAL}
    # Une exception que la table ne nomme pas se **relaie**, elle ne se deguise
    # pas en refus metier : c'est la frontiere negative de `code_de_sortie`.
    assert scan_calibrate.code_de_sortie(ZeroDivisionError("bug")) is None
