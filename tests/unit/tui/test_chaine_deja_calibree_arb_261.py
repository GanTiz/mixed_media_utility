# -*- coding: utf-8 -*-
"""`EPIC11-ARB-261` -- une chaine deja calibree gagne un SECOND fichier.

Ce banc ferme le finding `C3` de la revue du 2026-09-07, motif `K3` (« un
mecanisme juste, cable NULLE PART »), trouve independamment par les **trois**
couches : `io/calibration_profile.profils_de_la_chaine` -- le balayage inverse
qu'`EPIC11-ARB-261` chiffrait -- etait ecrit, mesure par son propre banc de
coeur, et `grep -rn "profils_de_la_chaine" src/` ne rendait que sa definition.

Le regime que son docstring decrit etait donc **toujours vivant**, et un
lecteur du module croyait le contraire : « recalibrer une chaine deja calibree
sous un libelle different ecrivait un second fichier, l'ancien devenait
orphelin sans un mot, et l'ecran annoncait "nouveau profil" sur ce qui est une
recalibration ».

**La frontiere qui compte est negative** : aucun test positif ne verrait
revenir un mecanisme decable. `test_le_balayage_inverse_a_desormais_un_APPELANT`
mesure qu'il en a un, en production, hors de sa propre definition.

REGLE DES FABRIQUES, appliquee ici. Les fabriques de ce banc produisent
**trois** profils distinguables sous `versions/calibration/`, la cible est
placee ailleurs qu'en premiere position, et deux tests placent une cible a
**chaque bord** du listing trie (point 4 de la regle, pose le 2026-09-03 sur un
mutant qui sautait la derniere entree d'un listing). Un balayage tronque en
tete ou en queue laisserait un orphelin, ce qui est exactement la panne que ce
lot ferme.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate
from mixed_media_utility.io import (calibration_profile, extraction_manifest,
                                    profile_designation, project_layout)
import pytest

from mixed_media_utility.tui import (atelier_scan_calibrate,
                                     atelier_scan_parcours, jetons)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

#: Le drapeau qui se FAIT VARIER. « Une garde de repli, de mode ou de variante
#: fait varier le drapeau dont elle depend » -- regle du depot posee le
#: 2026-09-06 apres deux occurrences dans la meme nuit, dont onze ecrans sur
#: quatorze qui amputaient leur bandeau en `--ascii` sous des bancs verts.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

PIED_DU_PALIER = "Q quitter"

#: **Deux chaines distinguables, jamais une seule** : une fabrique mono-element
#: rendrait invisible un balayage qui rendrait « tous les profils » au lieu de
#: « ceux de cette chaine ».
CHAINE_VISEE = "900-png-cccccccccccc"
CHAINE_VOISINE = "600-tif-dddddddddddd"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 3, 1000, 300.0, 1


class _Source:
    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 3, 300.0, 1
    est_multiple = False

    def __init__(self, chemin):
        self.chemin = chemin


def _formulaire(tmp_path: Path):
    formulaire = atelier_scan_calibrate.FormulaireDeCalibration()
    formulaire.poser_le_scan(_Source(tmp_path / "mire.pdf"))
    formulaire.dpi = "300"
    return formulaire


def _coque(ascii_seul: bool = False) -> CoqueTui:
    return CoqueTui([PalierTemoin("Projet", PIED_DU_PALIER),
                     PalierTemoin("Ateliers", PIED_DU_PALIER)],
                    Contexte(projet="projet_demo", palier="Scan"),
                    ascii_seul=ascii_seul)


def _poser_un_profil(projet: Path, radical: str, chaine: str) -> Path:
    """Un fichier de profil sur le disque, sous ce radical et cette chaine.

    Ecrit au plus court : le balayage inverse ne lit que `chain_id`, et un
    document complet ferait croire que la mesure depend d'autre chose.
    """
    chemin = projet / project_layout.VERSIONS_DIRNAME / "calibration" / f"{radical}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(_document(radical, chaine)),
                      encoding="utf-8")
    return chemin


def _document(radical: str, chaine: str) -> dict:
    """Un document de profil **complet au sens du manifeste**.

    Les huit champs de `profile_designation.ENTRY_DOCUMENT_FIELDS` y sont, et
    ce n'est pas du remplissage : sans eux `record_designated_profile` leve, et
    le banc du profil par defaut mesurerait un chemin que le produit ne prend
    jamais. Le balayage inverse, lui, ne lit que `chain_id`.
    """
    return {
        "schema_version": 1,
        "chain_id": chaine,
        "correction_form_id": "affine_bgr_v1",
        "source_page_id": "p0",
        "template_id": "mire_v1",
        "read_patch_count": 18,
        "retained_patch_count": 18,
        "ink_floor_excluded": False,
        "label": radical,
    }


#: Le lot temoin d'un `project.json` valide au schema v2.1, repris de
#: `tests/unit/test_profil_designe.py`. Un manifeste bricole ne serait pas
#: ecrit du tout -- l'ecriture atomique valide son temporaire avant la bascule
#: --, et le banc mesurerait alors le mauvais refus.
_LOT_TEMOIN = {
    "expected_frame_count": 20,
    "first_frame_timecode": "01:01:42:05",
    "fps_target": 25.0,
    "fps_target_exact": "25/1",
    "frame_timecodes_digest": (
        "sha256-v1:2491dd7fc618e3bea6bf10eb4195eea266e74c5bec73ec2c62b517397"
        "eabc519"),
    "frames_dir": "frames/rush-temoin_25-7f152a04",
    "gamut_map_id": "gamut-map-none-1",
    "last_frame_timecode": "01:01:42:24",
    "lot_id": "rush-temoin_25-7f152a04",
    "output_bit_depth": 16,
    "patch_preset_id": "patches-14-v3",
    "rounding_policy": "floor-index-ceil-count-v1",
    "rush_id": "rush-temoin",
    "selection_warnings": [],
    "source_frame_count": 106,
    "source_frame_count_is_exact": True,
    "source_in_timecode": "01:01:42:05",
    "source_out_timecode": "01:01:42:24",
    "source_tail_frames": 18,
    "state": "extraction",
    "template_id": "tpl-a4-portrait-8f-v2",
    "timecode_base": "source",
    "timecode_base_fps": "25/1",
}


def _projet_avec_manifeste(racine: Path) -> Path:
    """Un projet **reel**, avec son `project.json` valide.

    Il est requis des que la designation entre en jeu :
    `record_designated_profile` rend l'entree « qui aurait ete ecrite » quand
    le projet n'a pas encore de manifeste, et **ne persiste rien**. Un banc
    monte sur un dossier nu mesurerait donc un suivi de defaut qui n'a jamais
    ete ecrit -- vert des deux cotes, et faux des deux cotes.
    """
    projet = racine / "projet"
    project_layout.ensure_project_layout(projet)
    manifeste = {
        "schema_version": "2.1",
        "project_id": "projet-du-banc-261",
        "created": "2026-09-07T00:00:00Z",
        "artifacts": {"frames_dir": "frames", "outputs_dir": "outputs"},
        "color": {},
        "video": {},
        "reconstruction": {},
        "rushes": [{"rush_id": "rush-temoin",
                    "source_path": "rushes/temoin.mov"}],
        "lots": [dict(_LOT_TEMOIN)],
    }
    (projet / extraction_manifest.MANIFEST_FILENAME).write_text(
        json.dumps(manifeste, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return projet


class _CalibrationQuiEcrit:
    """Un double au contrat du coeur, **sans `**kwargs`**.

    Meme discipline que `CalibrationFeinte` : un faux permissif laisserait
    passer un appel dont un mot-cle est mal nomme.

    Il ecrit un vrai fichier de profil portant `chain_id`, parce que c'est
    exactement ce que le balayage inverse relit. Un double qui rendrait un
    `ProfilDeChaineConsigne` sans rien poser sur le disque mesurerait un
    balayage sur un dossier vide, c'est-a-dire rien.
    """

    def __init__(self, radical: str, chaine: str = CHAINE_VISEE):
        self.radical = radical
        self.chaine = chaine
        self.appels: list[dict] = []

    def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                 demander_le_nom_et_le_commentaire=None,
                 confirmer_l_ecrasement=None, rappel_progression=None):
        self.appels.append({"dpi": dpi})
        if demander_le_nom_et_le_commentaire is not None:
            demander_le_nom_et_le_commentaire(self.chaine)
        document = _document(self.radical, self.chaine)
        chemin = _poser_un_profil(Path(project_dir), self.radical, self.chaine)
        return scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id=self.chaine,
            etiquette=self.radical, commentaire="", lot_correction=None,
            document=document)


async def _tant_que(pilote, condition, tours: int = 600) -> bool:
    for _ in range(tours):
        if condition():
            return True
        await pilote.pause()
        await asyncio.sleep(0.005)
    return False


def _jouer(banc, tmp_path: Path, feinte, *, apres=None):
    """Une passe complete, **par le point d'entree de l'operateur**.

    Jamais par `lancer_la_passe_de_calibration`, qui court-circuiterait le
    cablage que ce banc existe pour mesurer.
    """
    app = _coque()
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    parcours = atelier_scan_parcours.ParcoursScan(app, projet,
                                                  calibration=feinte)
    vu: dict = {"projet": projet, "parcours": parcours}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        confirmation = pilote.app.screen
        confirmation.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        confirmation.valider()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        await pilote.pause()
        vu["sommet_avant"] = type(pilote.app.screen).__name__
        vu["ecran_avant"] = pilote.app.screen
        if apres is not None:
            await apres(pilote, vu)
            await pilote.pause()
        vu["sommet_apres"] = type(pilote.app.screen).__name__
        vu["etat_apres"] = getattr(pilote.app.screen, "_etat_courant", "")
        vu["fichiers"] = sorted(
            chemin.name for chemin
            in (vu["projet"] / project_layout.VERSIONS_DIRNAME / "calibration").glob("*.json"))
        return vu

    return banc(app, scenario)


# ---------------------------------------------------------------------------
# La frontiere NEGATIVE : le mecanisme est cable
# ---------------------------------------------------------------------------


def test_le_balayage_inverse_a_desormais_un_APPELANT_en_production():
    """`profils_de_la_chaine` est appele hors de sa propre definition.

    **Frontiere negative, et c'est la seule forme qui attrape le motif `K3`.**
    Un test positif -- « l'ecran monte quand deux profils existent » -- reste
    vert le jour ou quelqu'un decable l'appel et reecrit le balayage a la main
    dans la TUI. Celui-ci rougit.

    La mesure porte sur le paquet `src/` entier, definition exclue : c'est
    exactement le grep que les trois couches de la revue ont fait, et qui ne
    rendait qu'une ligne.

    **L'appelant a CHANGE DE COUCHE le 2026-09-07, et l'assertion suit.** Il
    etait `tui/atelier_scan_calibrate.py` ; il est desormais `scan_calibrate.py`
    -- le coeur --, parce que la ligne de commande avait besoin du meme releve
    et qu'une seconde redaction aurait diverge. Nommer le module attendu, plutot
    que se contenter d'une liste non vide, est ce qui distingue « le mecanisme
    est cable » de « le mecanisme est cable la ou les DEUX interfaces le
    trouvent » : un appelant qui redescendrait dans une seule interface
    rouvrirait le defaut par l'autre porte, et c'est exactement ce qui vient
    d'etre paye.
    """
    racine = RACINE / "src" / "mixed_media_utility"
    appelants = set()
    for chemin in racine.rglob("*.py"):
        texte = chemin.read_text(encoding="utf-8")
        for ligne in texte.splitlines():
            if "profils_de_la_chaine" not in ligne:
                continue
            if ligne.lstrip().startswith("def profils_de_la_chaine"):
                continue
            appelants.add(chemin.relative_to(racine).as_posix())
    assert appelants, (
        "`profils_de_la_chaine` n'a plus aucun appelant en production : le "
        "regime qu'il decrit (un second profil orphelin, sans un mot) est "
        "redevenu vivant, et son docstring dit le contraire")
    assert "scan_calibrate.py" in appelants, sorted(appelants)


# ---------------------------------------------------------------------------
# Le releve : ce qui declenche, et ce qui NE declenche pas
# ---------------------------------------------------------------------------


def test_un_SECOND_profil_de_la_meme_chaine_fait_monter_l_avertissement(
        tmp_path, banc):
    """Le regime d'`EPIC11-ARB-261`, de bout en bout et par le clavier.

    Trois profils prealables et **la cible ni en tete ni en queue** : `aaa` et
    `zzz` portent la chaine visee, `mmm` porte la voisine. Le profil ecrit
    s'appelle `nnn`, donc il tombe au milieu du listing trie. Un balayage
    tronque d'un bord laisserait un orphelin et ce banc rougirait.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "mmm", CHAINE_VOISINE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"))

    assert vu["sommet_avant"] == "EcranChaineDejaCalibreeDuScan", vu
    ecran = vu["ecran_avant"]
    assert [autre.name for autre in ecran.autres] == ["aaa.json", "zzz.json"], (
        "les DEUX bords du listing doivent etre vus, et la chaine voisine "
        "ecartee")


def test_une_RECALIBRATION_pure_ne_montre_AUCUN_avertissement(tmp_path, banc):
    """Meme chaine, meme fichier : rien a trancher, et rien a montrer.

    C'est le regime que `write_profile` documente depuis 5.22 -- « poser la
    question a chaque recalibration serait une invite qui apprend a repondre
    oui sans lire ». Le releve d'`EPIC11-ARB-261` doit donc **ecarter le
    fichier qu'on vient d'ecrire**, et ce test est ce qui l'etablit : sans
    l'exclusion, tout operateur qui recalibre verrait l'avertissement.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "nnn", CHAINE_VISEE)

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"))

    assert vu["sommet_avant"] == "EcranCalibrationEcrite", vu
    assert vu["fichiers"] == ["nnn.json"], vu


def test_une_AUTRE_chaine_deja_calibree_ne_declenche_RIEN(tmp_path, banc):
    """Deux dpi ou deux scanners font deux chaines, et deux fichiers y sont justes.

    Le docstring du coeur le dit (« ce n'est pas un doublon »), et sans ce test
    un balayage qui rendrait *tous* les profils du projet passerait vert sur le
    banc precedent -- il y trouverait bien deux fichiers.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VOISINE)
    _poser_un_profil(projet, "zzz", CHAINE_VOISINE)

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"))

    assert vu["sommet_avant"] == "EcranCalibrationEcrite", vu
    assert vu["fichiers"] == ["aaa.json", "nnn.json", "zzz.json"], vu


# ---------------------------------------------------------------------------
# Les DEUX issues, et ce qu'elles font vraiment
# ---------------------------------------------------------------------------


def test_l_avertissement_ne_PRESELECTIONNE_rien_et_une_SEULE_issue_ecrit(
        tmp_path, banc):
    """`EPIC11-ARB-89` : jamais un blocage sec, jamais une destruction muette.

    Deux issues -- donc pas de mur --, aucune preselectionnee, le curseur sur
    celle qui ne retire rien, et **exactement une** marquee `ecrit`. Les quatre
    proprietes ensemble : trois d'entre elles seraient vertes sur un ecran qui
    n'offrirait que « remplacer ».
    """
    choix = atelier_scan_calibrate.choix_de_la_chaine_deja_calibree()
    assert len(choix.issues) == 2
    assert [issue.cle for issue in choix.issues] == [
        atelier_scan_calibrate.CLE_GARDER_LES_DEUX,
        atelier_scan_calibrate.CLE_REMPLACER_LE_PROFIL]
    assert choix.retenue is None
    assert choix.curseur == 0, "le curseur part sur l'issue qui ne retire rien"
    assert [issue.cle for issue in choix.issues if issue.ecrit] == [
        atelier_scan_calibrate.CLE_REMPLACER_LE_PROFIL]


def test_GARDER_LES_DEUX_laisse_les_fichiers_et_montre_le_RESULTAT(
        tmp_path, banc):
    """L'issue non destructive, et la continuation qui la suit.

    Les deux moitie comptent : ne rien retirer, **et** ne pas laisser
    l'operateur sans ecran de resultat -- c'est le court-circuit qu'Egan a
    constate le 2026-09-06 (« pas d'ecran de succes, on revient directement a
    la page pour lancer une calibration »).
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    async def apres(pilote, vu):
        pilote.app.screen.choix.viser(
            atelier_scan_calibrate.CLE_GARDER_LES_DEUX)
        pilote.app.screen.traiter("enter")
        await _tant_que(
            pilote,
            lambda: type(pilote.app.screen).__name__ == "EcranCalibrationEcrite")

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"), apres=apres)

    assert vu["sommet_apres"] == "EcranCalibrationEcrite", vu
    assert vu["fichiers"] == ["aaa.json", "nnn.json", "zzz.json"], vu


def test_REMPLACER_retire_les_DEUX_bords_et_montre_le_RESULTAT(tmp_path, banc):
    """L'issue destructive, **consciente**, et les deux bords du listing.

    `aaa` est en tete du listing trie, `zzz` en queue, le profil ecrit au
    milieu : c'est le point 4 de la regle des fabriques, pose sur un mutant qui
    sautait la derniere entree d'un listing d'orphelins. Une cible au milieu
    seule ne demasque pas un balayage tronque.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "mmm", CHAINE_VOISINE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    async def apres(pilote, vu):
        pilote.app.screen.choix.viser(
            atelier_scan_calibrate.CLE_REMPLACER_LE_PROFIL)
        pilote.app.screen.traiter("enter")
        await _tant_que(
            pilote,
            lambda: type(pilote.app.screen).__name__ == "EcranCalibrationEcrite")

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"), apres=apres)

    assert vu["sommet_apres"] == "EcranCalibrationEcrite", vu
    # `mmm` est d'une AUTRE chaine : le retrait ne l'emporte pas.
    assert vu["fichiers"] == ["mmm.json", "nnn.json"], vu
    assert "2" in vu["etat_apres"], (
        "le retrait se PRONONCE sur la ligne d'etat, sans quoi une "
        "destruction consciente ne se dirait nulle part", vu["etat_apres"])


def test_ECHAP_vaut_GARDER_LES_DEUX_et_montre_quand_meme_le_resultat(
        tmp_path, banc):
    """Sortir sans choisir ne peut pas signifier DETRUIRE.

    Meme principe que le filet de `EcranCollisionDuScan`, ou le demontage
    repond `annuler`. Ici il n'y a rien a annuler -- le profil est deja ecrit
    --, donc le repli est l'issue qui ne retire rien. Et la continuation joue
    quand meme : `Échap` ne doit pas escamoter l'ecran de resultat.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)

    async def apres(pilote, vu):
        pilote.app.screen.traiter("escape")
        await _tant_que(
            pilote,
            lambda: type(pilote.app.screen).__name__ == "EcranCalibrationEcrite")

    vu = _jouer(banc, tmp_path, _CalibrationQuiEcrit("nnn"), apres=apres)

    assert vu["sommet_apres"] == "EcranCalibrationEcrite", vu
    assert vu["fichiers"] == ["aaa.json", "nnn.json"], vu


# ---------------------------------------------------------------------------
# Le point que l'invite d'Egan n'a PAS pose : le profil par defaut
# ---------------------------------------------------------------------------


def test_le_profil_par_DEFAUT_suit_le_remplacement(tmp_path):
    """Sans suivi, le defaut du projet pointe sur un fichier disparu.

    **Mesure du resolveur, prise avant d'ecrire quoi que ce soit** :
    `profile_designation.default_profile_path` rend `None` des que le fichier a
    disparu, et son propre docstring dit ce que ca coute -- « l'appelant
    avertit, et le lot sort brut ». Le manifeste, lui, ne rougit pas : c'est un
    chemin relatif parfaitement valide vers un fichier absent. La degradation
    est donc **silencieuse et durable**, et c'est ce qui tranche : le contraire
    du suivi n'est pas « ne rien faire », c'est « casser le defaut du projet
    sans le dire ».

    Ce test mesure aussi l'ORDRE, qui est le correctif : relever le defaut
    apres le retrait rendrait `None` dans les deux cas et le suivi ne se
    declencherait jamais.
    """
    projet = _projet_avec_manifeste(tmp_path)
    ancien = _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    neuf = _poser_un_profil(projet, "nnn", CHAINE_VISEE)
    document = json.loads(ancien.read_text(encoding="utf-8"))
    profile_designation.record_designated_profile(
        projet, document, project_path=ancien, source=str(ancien),
        as_default=True)
    assert profile_designation.default_profile_path(projet) == ancien

    passe = atelier_scan_calibrate.PasseDeCalibration(
        profil=scan_calibrate.ProfilDeChaineConsigne(
            profile_path=neuf, chain_id=CHAINE_VISEE, etiquette="nnn",
            commentaire="", lot_correction=None,
            document=json.loads(neuf.read_text(encoding="utf-8"))),
        chaine=CHAINE_VISEE)
    autres = atelier_scan_calibrate.profils_a_remplacer(projet, passe)
    assert autres == [ancien]

    remplacement = atelier_scan_calibrate.remplacer_les_profils_de_la_chaine(
        projet, passe, autres)

    assert remplacement.retires == (ancien,)
    assert remplacement.defaut_suivi is True
    assert profile_designation.default_profile_path(projet) == neuf
    assert not ancien.exists()


def test_un_defaut_qui_ne_designait_AUCUN_des_retires_ne_bouge_pas(tmp_path):
    """Le symetrique, sans lequel la mesure ne verrait qu'une moitie.

    Un suivi inconditionnel repointerait le defaut du projet a chaque
    remplacement, y compris quand l'operateur avait designe une **autre**
    chaine : le profil qu'il a choisi serait remplace par celui qu'il vient de
    mesurer, sans l'avoir demande. C'est la meme faute qu'un ecrasement
    silencieux, dans le manifeste plutot que sur le disque.
    """
    projet = _projet_avec_manifeste(tmp_path)
    ancien = _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    voisin = _poser_un_profil(projet, "mmm", CHAINE_VOISINE)
    neuf = _poser_un_profil(projet, "nnn", CHAINE_VISEE)
    profile_designation.record_designated_profile(
        projet, json.loads(voisin.read_text(encoding="utf-8")),
        project_path=voisin, source=str(voisin), as_default=True)

    passe = atelier_scan_calibrate.PasseDeCalibration(
        profil=scan_calibrate.ProfilDeChaineConsigne(
            profile_path=neuf, chain_id=CHAINE_VISEE, etiquette="nnn",
            commentaire="", lot_correction=None,
            document=json.loads(neuf.read_text(encoding="utf-8"))),
        chaine=CHAINE_VISEE)
    remplacement = atelier_scan_calibrate.remplacer_les_profils_de_la_chaine(
        projet, passe, [ancien])

    assert remplacement.defaut_suivi is False
    assert profile_designation.default_profile_path(projet) == voisin


def test_un_fichier_qui_RESISTE_se_prononce_et_n_emporte_pas_les_autres(
        tmp_path):
    """`EPIC11-ARB-258` : un refus se prononce, et il ne devient pas un silence.

    Un fichier qui ne se retire pas -- lecture seule, verrou -- ne doit ni
    faire perdre le retrait des autres, ni etre annonce retire. Les deux
    listes sont donc separees, et le motif systeme voyage **verbatim** : « No
    such file or directory » dit a l'operateur quoi faire, « retrait
    impossible » ne dit rien.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    present = _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    neuf = _poser_un_profil(projet, "nnn", CHAINE_VISEE)
    absent = projet / project_layout.VERSIONS_DIRNAME / "calibration" / "disparu.json"

    passe = atelier_scan_calibrate.PasseDeCalibration(
        profil=scan_calibrate.ProfilDeChaineConsigne(
            profile_path=neuf, chain_id=CHAINE_VISEE, etiquette="nnn",
            commentaire="", lot_correction=None, document={}),
        chaine=CHAINE_VISEE)
    remplacement = atelier_scan_calibrate.remplacer_les_profils_de_la_chaine(
        projet, passe, [absent, present])

    assert remplacement.retires == (present,)
    assert [chemin for chemin, _ in remplacement.resistants] == [absent]
    etat = atelier_scan_calibrate.etat_du_remplacement(remplacement)
    assert "disparu.json" in etat
    # Le resistant passe EN TETE : sinon l'operateur lit « 1 profil retiré » et
    # rate celui qui est reste.
    assert etat.index("disparu.json") < etat.index("1")


# ---------------------------------------------------------------------------
# Le MODE se fait varier, il n'est pas suppose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_dit_la_MEME_chose_en_utf8_et_en_ascii(tmp_path, banc,
                                                       ascii_seul):
    """Les deux modes, sur le meme ecran, avec le drapeau qui VARIE.

    « Une garde de repli, de mode ou de variante fait varier le drapeau dont
    elle depend » (regle du depot, 2026-09-06). Un banc qui ne joue
    qu'`ascii_seul=False` mesure la moitie du produit et l'annonce verte :
    c'est exactement ce qui a laisse onze ecrans sur quatorze amputer leur
    bandeau du haut en `--ascii`, sous des bancs verts.

    Ce qui est mesure des deux cotes : les deux issues et le nom du fichier
    concerne sont **lisibles**, et aucune ligne ne deborde la largeur utile --
    un debordement se rendrait par une coupe a droite, donc par une issue
    tronquee.
    """
    app = _coque(ascii_seul=ascii_seul)
    passe = atelier_scan_calibrate.PasseDeCalibration(chaine=CHAINE_VISEE)
    ecran = atelier_scan_calibrate.EcranChaineDejaCalibree(
        passe, [Path("aaa.json")], retenir=lambda issue: None)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        utile = jetons.largeur_utile(pilote.app.size.width)
        lignes = ecran.lignes()
        return lignes, utile

    lignes, utile = banc(app, scenario)
    texte = " ".join(lignes)
    assert atelier_scan_calibrate.LIBELLE_GARDER_LES_DEUX in texte
    assert atelier_scan_calibrate.LIBELLE_REMPLACER_LE_PROFIL in texte
    assert "aaa.json" in texte
    trop_larges = [ligne for ligne in lignes
                   if jetons.colonnes(ligne) > utile]
    assert trop_larges == [], (ascii_seul, trop_larges)


# ---------------------------------------------------------------------------
# La phrase : singulier et pluriel, deux redactions
# ---------------------------------------------------------------------------


def test_la_phrase_se_dit_au_SINGULIER_et_au_PLURIEL(tmp_path):
    """Deux redactions, jamais un `(s)` postiche.

    Le cas pluriel n'est pas theorique : c'est le regime des projets
    d'aujourd'hui, calibres plusieurs fois sous des libelles differents avant
    que cet ecran n'existe.
    """
    passe = atelier_scan_calibrate.PasseDeCalibration(chaine=CHAINE_VISEE)
    une = atelier_scan_calibrate.phrase_de_la_chaine_deja_calibree(
        passe, [Path("aaa.json")])
    deux = atelier_scan_calibrate.phrase_de_la_chaine_deja_calibree(
        passe, [Path("aaa.json"), Path("zzz.json")])

    assert "aaa.json" in une and "2 autres" not in une
    assert "aaa.json" in deux and "zzz.json" in deux and "2 autres" in deux
    assert CHAINE_VISEE in une and CHAINE_VISEE in deux


def test_le_releve_est_VIDE_quand_la_passe_n_a_rien_ecrit(tmp_path):
    """Aucun releve sur une passe refusee : il n'y a pas de chemin a exclure.

    Sans cette garde, `passe.chemin is None` ferait comparer `None` a des
    chemins et **tous** les profils de la chaine seraient rendus -- un
    avertissement sur une passe qui n'a rien ecrit, c'est-a-dire un chiffre
    invente presente comme une mesure.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    refusee = atelier_scan_calibrate.PasseDeCalibration(
        refus=scan_calibrate.RefusDeCalibration("pas de mire"),
        chaine=CHAINE_VISEE)

    assert atelier_scan_calibrate.profils_a_remplacer(projet, refusee) == []


def test_le_releve_est_VIDE_quand_la_chaine_n_a_pas_traverse(tmp_path):
    """Sans identite de chaine, aucun balayage : le coeur en dit deja autant.

    `profils_de_la_chaine` rend `[]` sur une chaine vide -- « elle ne rend
    jamais que ce qui est LITTERALEMENT la meme chaine » --, et cette garde-ci
    evite d'aller le lui demander. Les deux disent la meme chose ; celle-ci le
    dit sans lire le disque.
    """
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    chemin = _poser_un_profil(projet, "nnn", CHAINE_VISEE)
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    sans_chaine = atelier_scan_calibrate.PasseDeCalibration(
        profil=scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id="", etiquette="", commentaire="",
            lot_correction=None, document={}),
        chaine="")

    assert atelier_scan_calibrate.profils_a_remplacer(projet, sans_chaine) == []
    assert calibration_profile.profils_de_la_chaine(projet, "") == []
