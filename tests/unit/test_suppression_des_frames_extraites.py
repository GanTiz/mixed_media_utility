# -*- coding: utf-8 -*-
"""Retirer LE jeu de frames extraites d'un lot, seul (retour de terrain d'Egan
du 2026-09-06 : « on ne peut pas retirer d'un projet un jeu de frames extraites
sans emporter autre chose »).

Ce banc mesure la cinquieme cible fine de `remove_project_element`, et surtout
les deux choses qui la distinguent des quatre autres :

* elle n'a **pas de rang propre** -- son dossier est nomme par le
  `version_rank` du LOT --, donc `--version` et `--liberer-le-rang` y sont
  refuses NOMMEMENT plutot qu'ignores ;
* elle retire un CONTENU sans retirer son contenant : le lot reste declare, et
  ses masters, ses planches et ses scans restent sur le disque.

**Regle des fabriques du CLAUDE.md, appliquee.** La fabrique produit TROIS lots
distinguables (frames de contenus differents, cardinaux differents), la cible
par defaut est au MILIEU, et deux tests la placent a CHAQUE bord -- en tete et
en queue. Un balayage tronque des lots ne se demasque pas autrement, et c'est
le mode de panne que le point 4 de la regle a paye en mutants survivants.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from mixed_media_utility.io import project_layout
from mixed_media_utility.project_maintenance import (
    ProjectMaintenanceError,
    _famille_des_frames_extraites,
    _ligne_d_eau_inexistante,
    remove_project_element,
)

RACINE = project_layout.EXTRACT_FRAMES_DIRNAME
RACINE_SCANNEES = project_layout.SCAN_FRAMES_DIRNAME


# ---------------------------------------------------------------------------
# La fabrique : trois lots DISTINGUABLES, la cible au milieu.
# ---------------------------------------------------------------------------


def _lot(lot_id: str, rush_id: str, cardinal: int) -> dict:
    """Un lot dont le dossier de frames porte `cardinal` frames DISTINCTES.

    Le cardinal varie d'un lot a l'autre, et le contenu de chaque frame porte
    le nom de son lot : une permutation entre deux lots ne se voit que si les
    deux different, et un remplissage uniforme la rendrait invisible (regle
    des fabriques, point 1).
    """
    return {
        "lot_id": lot_id,
        "rush_id": rush_id,
        "state": "extraction",
        "fps_target": 12.5,
        "frames_dir": f"{RACINE}/{lot_id}",
        # Ecrit par `_build_lot` a partir de la SELECTION, jamais d'un
        # comptage sur disque : ce banc mesure qu'il SURVIT au retrait.
        "expected_frame_count": cardinal,
        "first_frame_timecode": "00:00:00:00",
        "output_bit_depth": 16,
        "cardinal_de_la_fabrique": None,
    }


def _manifeste() -> dict:
    lots = [
        _lot("rush-a_24", "rush-a", 2),
        _lot("rush-b_12", "rush-b", 3),  # <- la cible par defaut, AU MILIEU
        _lot("rush-a_5", "rush-a", 4),
    ]
    for entree in lots:
        entree.pop("cardinal_de_la_fabrique")
    return {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": lots,
    }


def _ecrire_projet(tmp_path, manifest: dict):
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    for entree in manifest["lots"]:
        relatif = entree.get("frames_dir")
        if not relatif:
            continue
        dossier = projet / relatif
        dossier.mkdir(parents=True, exist_ok=True)
        for numero in range(entree["expected_frame_count"]):
            (dossier / f"{entree['lot_id']}_{numero:04d}.tiff").write_bytes(
                f"{entree['lot_id']}-{numero}".encode())
    return projet


def _projet(tmp_path):
    return _ecrire_projet(tmp_path, _manifeste())


def _lot_du_manifeste(projet, lot_id: str) -> dict | None:
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    return next((l for l in manifest["lots"] if l["lot_id"] == lot_id), None)


def _frames_presentes(projet, lot_id: str) -> list[str]:
    dossier = projet / RACINE / lot_id
    if not dossier.is_dir():
        return []
    return sorted(c.name for c in dossier.iterdir())


# ---------------------------------------------------------------------------
# Le geste nominal.
# ---------------------------------------------------------------------------


def test_l_apercu_NOMME_chaque_frame_et_n_ecrit_rien(tmp_path):
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True)
    assert rapport.dry_run is True and rapport.supprime is False
    assert rapport.fichiers_a_supprimer == (
        f"{RACINE}/rush-b_12/rush-b_12_0000.tiff",
        f"{RACINE}/rush-b_12/rush-b_12_0001.tiff",
        f"{RACINE}/rush-b_12/rush-b_12_0002.tiff",
    )
    # Rien n'a bouge, ni sur le disque ni au manifeste.
    assert len(_frames_presentes(projet, "rush-b_12")) == 3
    assert _lot_du_manifeste(projet, "rush-b_12")["frames_dir"] == (
        f"{RACINE}/rush-b_12")


def test_le_lot_RESTE_declare_et_seules_ses_frames_partent(tmp_path):
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.supprime is True
    assert not (projet / RACINE / "rush-b_12").exists()
    lot = _lot_du_manifeste(projet, "rush-b_12")
    assert lot is not None, "le lot ne doit PAS partir avec ses frames"
    assert "frames_dir" not in lot, (
        "le manifeste ne doit plus designer un dossier supprime")
    # Le PLAN d'extraction survit : ces champs viennent de la selection, pas
    # d'un comptage sur disque, et une reextraction s'y compare.
    assert lot["expected_frame_count"] == 3
    assert lot["first_frame_timecode"] == "00:00:00:00"
    assert lot["state"] == "extraction"


def test_les_frames_des_AUTRES_lots_ne_bougent_pas(tmp_path):
    projet = _projet(tmp_path)
    remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert _frames_presentes(projet, "rush-a_24") == [
        "rush-a_24_0000.tiff", "rush-a_24_0001.tiff"]
    assert len(_frames_presentes(projet, "rush-a_5")) == 4
    for autre in ("rush-a_24", "rush-a_5"):
        assert _lot_du_manifeste(projet, autre)["frames_dir"] == f"{RACINE}/{autre}"


@pytest.mark.parametrize("cible,cardinal", [("rush-a_24", 2), ("rush-a_5", 4)])
def test_la_cible_a_CHAQUE_BORD_part_bien_et_elle_seule(tmp_path, cible, cardinal):
    """Point 4 de la regle des fabriques : en TETE et en QUEUE.

    La cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque, qui saute la premiere ou la derniere entree du listing.
    Les deux bords sont donc mesures, et le controle porte sur ce qui RESTE
    autant que sur ce qui part.
    """
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id=cible, frames_extraites=True, dry_run=False)
    assert rapport.supprime is True
    assert len(rapport.fichiers_a_supprimer) == cardinal
    assert not (projet / RACINE / cible).exists()
    survivants = {"rush-a_24", "rush-b_12", "rush-a_5"} - {cible}
    for autre in survivants:
        assert _frames_presentes(projet, autre), (
            f"{autre} a perdu ses frames alors que {cible} etait vise")


def test_le_DERNIER_lot_du_projet_garde_ses_frames_supprimables_sans_confirmation(
        tmp_path):
    """Le second consentement protege le LOT, pas son contenu.

    `confirmation_dernier_lot` existe pour ne pas vider un projet de tout lot.
    Retirer les frames n'en retire aucun : l'exiger ici serait un consentement
    demande pour une consequence qui n'a pas lieu.
    """
    manifest = _manifeste()
    manifest["lots"] = [manifest["lots"][1]]
    projet = _ecrire_projet(tmp_path, manifest)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.supprime is True
    assert _lot_du_manifeste(projet, "rush-b_12") is not None


def test_un_dossier_DECLARE_mais_absent_DELIE_l_entree_sans_mentir(tmp_path):
    """Un dossier renomme a la main : l'entree part, le rapport le DIT.

    C'est la meme issue que pour un tirage renomme (`EPIC11-ARB-89`) : l'outil
    ne peut pas reconnaitre le dossier deplace, il ne le supprimera pas -- mais
    delier l'entree rend le geste possible au lieu de laisser un manifeste qui
    designe le vide pour toujours.
    """
    projet = _projet(tmp_path)
    shutil.move(str(projet / RACINE / "rush-b_12"),
                str(projet / RACINE / "renomme-a-la-main"))
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.fichiers_a_supprimer == ()
    assert rapport.fichiers_attendus_absents == (f"{RACINE}/rush-b_12",)
    assert "frames_dir" not in _lot_du_manifeste(projet, "rush-b_12")
    assert (projet / RACINE / "renomme-a-la-main").is_dir(), (
        "le dossier deplace reste sur le disque, et le rapport ne pretend pas "
        "le contraire")


def test_un_echec_de_suppression_RESTAURE_le_manifeste(tmp_path, monkeypatch):
    """Sinon le lot cesserait de declarer un dossier qui existe toujours.

    Meme motif que sur les quatre autres cibles : la resolution passe PAR le
    manifeste, donc une entree retiree alors que les fichiers survivent rend
    l'objet introuvable et referme la seule issue propre.
    """
    projet = _projet(tmp_path)

    def _rmtree_qui_echoue(*_args, **_kwargs):
        raise OSError("verrouille")

    monkeypatch.setattr(
        "mixed_media_utility.project_maintenance.shutil.rmtree",
        _rmtree_qui_echoue)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.supprime is False
    assert rapport.fichiers_non_supprimes == (f"{RACINE}/rush-b_12",)
    assert _lot_du_manifeste(projet, "rush-b_12")["frames_dir"] == (
        f"{RACINE}/rush-b_12"), "le geste doit rester REJOUABLE"


# ---------------------------------------------------------------------------
# Le rang : il n'y en a pas, et les deux refus le DISENT.
# ---------------------------------------------------------------------------


def test_le_rapport_dit_que_cet_objet_n_a_PAS_de_rang_propre(tmp_path):
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True)
    assert rapport.rang_independant is False
    assert rapport.objet_en_queue is False
    assert rapport.rangs_liberables == ()
    assert rapport.rang_libere is False


def test_le_drapeau_du_rang_VARIE_dans_les_deux_sens(tmp_path):
    """Une garde de variante fait varier son drapeau, sinon elle mesure une
    moitie du produit et l'annonce verte (CLAUDE.md, 2026-09-06).

    Le controle POSITIF est indispensable : un `rang_independant` cable a
    `False` en dur satisferait le test ci-dessus sans rien mesurer.
    """
    projet = _projet(tmp_path)
    (projet / RACINE_SCANNEES / "rush-b_12").mkdir(parents=True)
    (projet / RACINE_SCANNEES / "rush-b_12" / "f.tiff").write_bytes(b"scan")
    sans_rang = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True)
    avec_rang = remove_project_element(
        projet, lot_id="rush-b_12", lot_scanne=True)
    assert sans_rang.rang_independant is False
    assert avec_rang.rang_independant is True


@pytest.mark.parametrize("mot_cle,valeur,jeton", [
    ("version", 2, "--version"),
    ("liberer_le_rang", True, "--liberer-le-rang"),
])
def test_le_rang_demande_a_un_objet_qui_n_en_a_pas_est_REFUSE(
        tmp_path, mot_cle, valeur, jeton):
    """Le defaut que ce refus ferme est DESTRUCTEUR, pas cosmetique.

    `--version 2` designerait `extract-frames/<base>_v2`, qui est le dossier
    d'un AUTRE LOT ; `--liberer-le-rang` rendrait le rang du lot alors que son
    entree reste declaree, si bien que le lot suivant reprendrait un numero
    deja porte. Les deux se refusent avant toute lecture du manifeste.
    """
    projet = _projet(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True,
            dry_run=False, **{mot_cle: valeur})
    message = str(erreur.value)
    assert jeton in message
    assert "rang PROPRE" in message
    # `EPIC11-ARB-89` : deux issues nommees, jamais un mur.
    assert "Deux issues" in message
    assert len(_frames_presentes(projet, "rush-b_12")) == 3


def test_le_refus_du_rang_tombe_AVANT_la_lecture_du_manifeste(tmp_path):
    """Un argument sans effet se refuse pour ce qu'il est, pas par accident.

    Sur un lot qui ne declare aucun `frames_dir`, la lecture du manifeste
    refuse elle aussi -- mais pour un autre motif. Si le refus du rang tombait
    apres, l'operateur qui a mal designe sa cible lirait « pas de frames a
    retirer » alors que sa faute est ailleurs.
    """
    manifest = _manifeste()
    manifest["lots"][1].pop("frames_dir")
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, version=2)
    assert "rang PROPRE" in str(erreur.value)


def test_la_ligne_d_eau_inexistante_LEVE_au_lieu_de_se_taire():
    """Frontiere NEGATIVE : une surface morte ne se mesure pas.

    Quatre champs de ligne d'eau declares, lus, ecrits par personne : c'est ce
    que la revue du 2026-08-31 a trouve, et un `pass` pose ici en serait un
    cinquieme. La levee rend le defaut bruyant.
    """
    with pytest.raises(ProjectMaintenanceError) as erreur:
        _ligne_d_eau_inexistante(3)
    assert "Defaut interne" in str(erreur.value)


def test_aucune_ligne_d_eau_n_est_ecrite_par_ce_retrait(tmp_path):
    """Le pendant POSITIF du test ci-dessus : le chemin nominal ne l'appelle
    jamais -- s'il l'appelait, il leverait."""
    projet = _projet(tmp_path)
    remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert "lot_version_watermarks" not in manifest
    assert "output_frames_version_watermark" not in _lot_du_manifeste(
        projet, "rush-b_12")


# ---------------------------------------------------------------------------
# Les gardes de chemin, reprises telles quelles -- une porte neuve ne rouvre
# aucun des trous deja payes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("piege", [".", "", f"{RACINE}/..", "../ailleurs"])
def test_un_frames_dir_qui_SORT_du_lot_ne_detruit_rien(tmp_path, piege):
    """Les deux mesures payees de `_sous_le_projet`, sur la porte neuve.

    Un `frames_dir` valant `"."` ou `"frames/.."` resout sur le dossier projet
    et emportait `project.json` lui-meme ; un `"../ailleurs"` a REELLEMENT
    detruit un fichier hors du projet. La cible fine ne doit pas les rouvrir.
    """
    manifest = _manifeste()
    manifest["lots"][1]["frames_dir"] = piege
    projet = _ecrire_projet(tmp_path, manifest)
    dehors = tmp_path / "ailleurs"
    # `exist_ok` : la fabrique a deja cree ce dossier pour le piege sortant --
    # c'est justement la preuve que le chemin sort du projet.
    dehors.mkdir(exist_ok=True)
    (dehors / "precieux.txt").write_text("ne pas detruire", encoding="utf-8")
    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert (projet / "project.json").is_file()
    assert (dehors / "precieux.txt").is_file()
    assert len(_frames_presentes(projet, "rush-a_24")) == 2


def test_un_frames_dir_qui_CONTIENT_un_autre_lot_est_refuse(tmp_path):
    """L'ancetre commun : `rglob` y ramasse les frames de TOUS les lots.

    Le lot vise declare la RACINE des frames, qui contient les dossiers des
    deux autres lots. Les supprimer detruirait des frames que le manifeste
    continue de declarer.
    """
    manifest = _manifeste()
    manifest["lots"][1]["frames_dir"] = RACINE
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert "contient" in str(erreur.value)
    assert len(_frames_presentes(projet, "rush-a_24")) == 2
    assert len(_frames_presentes(projet, "rush-a_5")) == 4


def test_un_frames_dir_qui_contient_les_frames_SCANNEES_DU_MEME_LOT_est_refuse(
        tmp_path):
    """La garde que la cible fine ajoute, et que le chemin du LOT n'a pas besoin.

    Quand le lot entier part, ses deux dossiers partent ensemble : leur
    chevauchement lui est indifferent. Ici on ne retire QUE les frames
    extraites, et un `frames_dir` qui contient le `output_frames_dir` du meme
    lot emporterait un dossier que le manifeste continue de declarer.
    """
    manifest = _manifeste()
    manifest["lots"][1]["frames_dir"] = "media"
    manifest["lots"][1]["output_frames_dir"] = "media/scannees"
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / "media" / "scannees").mkdir(parents=True)
    (projet / "media" / "scannees" / "s.tiff").write_bytes(b"scan")
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert "rush-b_12" in str(erreur.value)
    assert (projet / "media" / "scannees" / "s.tiff").is_file()


def test_le_MEME_lot_sans_chevauchement_passe_toujours(tmp_path):
    """Controle NEGATIF de la garde ci-dessus : sans lui, un refus cable en
    dur -- « toujours refuser quand output_frames_dir existe » -- serait vert."""
    manifest = _manifeste()
    manifest["lots"][1]["output_frames_dir"] = f"{RACINE_SCANNEES}/rush-b_12"
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / RACINE_SCANNEES / "rush-b_12").mkdir(parents=True)
    (projet / RACINE_SCANNEES / "rush-b_12" / "s.tiff").write_bytes(b"scan")
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert rapport.supprime is True
    assert (projet / RACINE_SCANNEES / "rush-b_12" / "s.tiff").is_file(), (
        "les frames SCANNEES ne partent pas avec les frames EXTRAITES")


def test_un_lot_SANS_frames_dir_est_refuse_en_NOMMANT_ses_issues(tmp_path):
    manifest = _manifeste()
    manifest["lots"][1].pop("frames_dir")
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True)
    message = str(erreur.value)
    assert "ne declare aucun `frames_dir`" in message
    assert "ORPHELIN" in message and "lot entier" in message


# ---------------------------------------------------------------------------
# La grammaire des cibles : la cinquieme obeit aux memes regles que les quatre.
# ---------------------------------------------------------------------------


def test_la_cible_exige_un_lot(tmp_path):
    projet = _projet(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, rush_id="rush-a", frames_extraites=True)
    assert "exige lot_id" in str(erreur.value)


@pytest.mark.parametrize("autre", [
    {"planche": True}, {"master": True, "profile": "prores_422"},
    {"scan": "S"}, {"lot_scanne": True},
])
def test_deux_cibles_fines_ensemble_sont_refusees(tmp_path, autre):
    projet = _projet(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, **autre)
    assert "Une seule cible fine" in str(erreur.value)
    assert "--frames-extraites" in str(erreur.value)


@pytest.mark.parametrize("drapeau", ["avec_scans", "confirmation_dernier_lot"])
def test_un_drapeau_de_LOT_sur_cette_cible_est_refuse(tmp_path, drapeau):
    projet = _projet(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True,
            **{drapeau: True})
    assert "aucun sens" in str(erreur.value)


@pytest.mark.parametrize("valeur", [2, "extract-frames/x", 0])
def test_un_ENTIER_ou_une_CHAINE_n_est_pas_un_drapeau(tmp_path, valeur):
    """`2` est vrai au sens de Python : sans ce refus, un appelant croyant
    viser la version 2 leverait le drapeau et retomberait sur le lot vise."""
    projet = _projet(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=valeur, dry_run=False)
    assert "DRAPEAU nu" in str(erreur.value)
    assert len(_frames_presentes(projet, "rush-b_12")) == 3


def test_le_drapeau_au_repos_ne_change_RIEN_au_chemin_du_lot_entier(tmp_path):
    """L'autre sens du drapeau : `frames_extraites=False` doit laisser la
    suppression du lot entier au caractere pres."""
    projet = _projet(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=False, dry_run=False)
    assert rapport.supprime is True
    assert _lot_du_manifeste(projet, "rush-b_12") is None, (
        "le lot entier part, comme avant l'ajout de la cible")
    assert rapport.rang_independant is True


# ---------------------------------------------------------------------------
# La ligne de commande.
# ---------------------------------------------------------------------------


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "mixed_media_utility.cli", *args],
        capture_output=True, text=True, env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
    )


def test_cli_l_apercu_liste_les_frames_et_dit_qu_aucun_rang_n_est_en_jeu(tmp_path):
    projet = _projet(tmp_path)
    resultat = _cli("project", "remove", "--project", str(projet),
                    "--lot", "rush-b_12", "--frames-extraites")
    assert resultat.returncode == 0, resultat.stderr
    assert "3 fichier(s)" in resultat.stdout
    assert "Aucun rang propre pour: frames extraites" in resultat.stdout, (
        "la branche par defaut annoncait « un objet posterieur existe », ce qui "
        "est faux ici")
    assert "Aucune ecriture" in resultat.stdout
    assert len(_frames_presentes(projet, "rush-b_12")) == 3


def test_cli_confirmer_supprime_et_laisse_le_lot(tmp_path):
    projet = _projet(tmp_path)
    resultat = _cli("project", "remove", "--project", str(projet),
                    "--lot", "rush-b_12", "--frames-extraites", "--confirmer")
    assert resultat.returncode == 0, resultat.stderr
    assert not (projet / RACINE / "rush-b_12").exists()
    assert _lot_du_manifeste(projet, "rush-b_12") is not None


@pytest.mark.parametrize("argv", [
    ["--version", "2"], ["--liberer-le-rang"],
])
def test_cli_le_rang_est_refuse_avec_le_code_1_et_sans_trace_python(tmp_path, argv):
    projet = _projet(tmp_path)
    resultat = _cli("project", "remove", "--project", str(projet),
                    "--lot", "rush-b_12", "--frames-extraites",
                    "--confirmer", *argv)
    assert resultat.returncode == 1
    assert "Traceback" not in resultat.stderr
    assert "rang PROPRE" in resultat.stderr
    assert len(_frames_presentes(projet, "rush-b_12")) == 3


def test_la_fabrique_de_famille_est_bien_marquee_sans_rang_propre(tmp_path):
    """Frontiere sur le descripteur lui-meme : un futur objet copie-colle
    depuis celui-ci ne doit pas heriter d'un `rang_independant` vrai par
    inadvertance."""
    projet = _projet(tmp_path)
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    lot = manifest["lots"][1]
    famille = _famille_des_frames_extraites(projet, manifest, lot)
    assert famille.rang_independant is False
    assert famille.contenant == "lot"
    assert famille.poser_la_ligne is _ligne_d_eau_inexistante
    # **La famille se REDUIT a son unique membre, et le rang est celui du LOT**
    # (couche 1, mutant `M12` survivant : `rangs_declares=set()` passait les
    # 27 tests). Rien ne le lit aujourd'hui -- `rang_independant=False` coupe
    # les deux branches qui s'en serviraient --, mais un objet futur copie
    # depuis ce descripteur heriterait d'une famille VIDE, et une famille vide
    # rend `ligne_d_eau` sur un ensemble sans element.
    assert famille.rangs_declares == {famille.rang}
    assert famille.ligne_declaree is None


# ---------------------------------------------------------------------------
# Ce que la couche 1 a trouve en campagne de mutation (2026-09-07).
# ---------------------------------------------------------------------------


def test_le_rapport_dit_l_absence_de_rang_propre_APRES_ECRITURE_aussi(tmp_path):
    """Le drapeau varie dans les deux SENS **et** sur les deux CHEMINS.

    Mutant `M05` de la couche 1, survivant : `rang_independant=True` dans le
    rapport du chemin qui ECRIT passait les 27 tests, parce que le seul banc
    qui lisait ce champ tournait en apercu. La consequence n'est pas
    cosmetique -- le bloc de la CLI qui imprime le rang tourne AVANT le
    `return` du mode apercu, donc `mmu project remove --frames-extraites
    --confirmer` aurait annonce « Le rang 1 reste CONSOMME: un lot posterieur
    existe », phrase fausse de bout en bout sur le seul objet sans rang.
    """
    projet = _projet(tmp_path)
    ecrit = remove_project_element(
        projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    assert ecrit.dry_run is False
    assert ecrit.supprime is True
    assert ecrit.rang_independant is False
    # Le sens POSITIF sur le meme chemin d'ecriture : sans lui, un `False` en
    # dur satisferait l'assertion ci-dessus sans rien mesurer.
    (projet / RACINE_SCANNEES / "rush-a_24").mkdir(parents=True)
    (projet / RACINE_SCANNEES / "rush-a_24" / "f.tiff").write_bytes(b"scan")
    avec_rang = remove_project_element(
        projet, lot_id="rush-a_24", lot_scanne=True, dry_run=False)
    assert avec_rang.dry_run is False
    assert avec_rang.rang_independant is True


def test_cli_le_CONFIRMER_dit_AUSSI_qu_aucun_rang_n_est_en_jeu(tmp_path):
    """Le pendant CLI du test ci-dessus, sur la sortie reelle.

    `test_cli_confirmer_supprime_et_laisse_le_lot` ne lit que le disque et le
    manifeste ; aucune assertion ne portait sur la phrase du rang APRES
    ecriture, ce qui laissait `M05` en vie de l'autre cote de la frontiere.
    """
    projet = _projet(tmp_path)
    resultat = _cli("project", "remove", "--project", str(projet),
                    "--lot", "rush-b_12", "--frames-extraites", "--confirmer")
    assert resultat.returncode == 0, resultat.stderr
    assert "Aucun rang propre pour: frames extraites" in resultat.stdout
    assert "reste CONSOMME" not in resultat.stdout


@pytest.mark.parametrize("vide", ["", 0, False, []])
def test_un_frames_dir_FAUX_mais_PRESENT_est_refuse_par_SON_message(
        tmp_path, vide):
    """Mutant `M08` de la couche 1, survivant : `if not declare` remplace par
    `if declare is None` passait les 27 tests.

    Le banc des pieges de chemin parametrait bien `""`, mais il n'assertait
    que « ca leve » -- or `""` resout sur la RACINE du projet, que
    `_sous_le_projet` refuse de son cote. Les deux gardes rendaient donc un
    refus, et rien ne disait LAQUELLE. Ce qui se perd quand la premiere tombe
    est le message : « ce lot ne declare aucun `frames_dir` » et ses deux
    issues nommees, contre « lots[].frames_dir ('') sort du projet », qui parle
    d'une evasion que l'operateur n'a pas tentee.
    """
    manifest = _manifeste()
    manifest["lots"][1]["frames_dir"] = vide
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", frames_extraites=True, dry_run=False)
    message = str(erreur.value)
    assert "ne declare aucun `frames_dir`" in message
    assert "ORPHELIN" in message
    assert (projet / "project.json").is_file()


def test_la_regle_de_retrait_refuse_ELLE_MEME_le_rang_qu_elle_n_a_pas(tmp_path):
    """Mutant `M03` de la couche 1, survivant : la garde de
    `_retirer_un_objet_versionne` pouvait etre RETIREE sans qu'un test rougisse.

    Le refus est ecrit « UNE fois pour DEUX appelants » -- la garde d'arguments
    de `remove_project_element` et la regle de retrait elle-meme. Seul le
    premier appelant etait mesure, si bien que le second etait une garde qu'on
    croyait avoir : tout appelant futur qui composerait une famille sans rang
    propre (le prochain objet contenu, par exemple) aurait rendu le rang de son
    contenant en silence.
    """
    from mixed_media_utility.project_maintenance import (
        _retirer_un_objet_versionne)

    projet = _projet(tmp_path)
    chemin = projet / "project.json"
    manifest = json.loads(chemin.read_text(encoding="utf-8"))
    lot = manifest["lots"][1]
    famille = _famille_des_frames_extraites(projet, manifest, lot)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        _retirer_un_objet_versionne(
            projet, chemin, manifest, famille,
            dry_run=True, liberer_le_rang=True)
    assert "rang PROPRE" in str(erreur.value)
    assert "liberer_le_rang=" in str(erreur.value)
    # Rien n'a bouge : la garde tombe avant toute lecture de disque.
    assert len(_frames_presentes(projet, "rush-b_12")) == 3
