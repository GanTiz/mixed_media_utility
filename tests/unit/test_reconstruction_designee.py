# -*- coding: utf-8 -*-
"""Story 6.8 -- un master s'encode depuis une reconstruction DESIGNEE.

Ce banc mesure ce que la story 6.8 ouvre : les jeux de frames rescannees que le
depot versionne deja (`EPIC11-ARB-105`) et inscrit a l'historique du lot
(`EPIC11-ARB-109`) etaient **inatteignables a l'export**, parce que
`encode.check_lot_admission` ne lisait que le champ **scalaire**
`lots[].output_frames_dir`, reecrit a chaque passe.

**La fabrique porte TROIS reconstructions, la cible AU MILIEU** (regle des
fabriques, `CLAUDE.md`). Trois et non deux : a deux elements, la cible en second
est aussi la **derniere**, et les deux formes y sont indiscernables -- un mutant
`continue` -> `break` y survit (mesure sur la story 11.4b). Trois defauts sont
ainsi separes d'un coup :

* un `find` fautif qui rend **toujours le premier** ;
* une boucle qui s'arrete **trop tot** ;
* un repli silencieux sur la **derniere** passe -- et c'est pour lui que le
  scalaire du lot pointe deliberement la **troisieme** : sans cela, "la passe
  designee" et "la derniere passe" rendraient le meme dossier, et l'assertion
  ne mesurerait rien.
"""

from __future__ import annotations

import ast
import inspect
import re
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    encode as encode_module,
    encode_master,
    encode_previz,
)
from mixed_media_utility.io import naming  # noqa: E402
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME  # noqa: E402

from test_encode_command import LOT, lot_of, scanned_project  # noqa: E402


# ===========================================================================
# T1 -- l'inverse du fragment de version (`io/naming.py`)
# ===========================================================================

def test_un_nom_SANS_fragment_porte_le_rang_d_ORIGINE() -> None:
    """Le rang 1 ne porte aucun fragment, et c'est `EPIC11-ARB-88` qui le veut."""
    assert naming.rang_du_fragment_de_version("rush-001_12p5") == 1


@pytest.mark.parametrize("rang", [2, 3, 17, 99])
def test_un_nom_AVEC_fragment_rend_son_rang(rang: int) -> None:
    assert naming.rang_du_fragment_de_version(f"rush-001_12p5_v{rang}") == rang


def test_l_aller_RETOUR_tient_sur_TOUTE_la_plage_des_rangs() -> None:
    """La propriete qui compte : l'inverse est bien l'inverse.

    Un banc a trois valeurs choisies laisserait passer une borne fausse d'une
    unite ; la plage entiere ne le laisse pas.
    """
    for rang in range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1):
        nom = f"lot{naming.format_version_suffix(rang)}"
        assert naming.rang_du_fragment_de_version(nom) == rang, nom


@pytest.mark.parametrize(
    "nom",
    [
        "lot_v1",    # le rang 1 ne s'ecrit JAMAIS -- `format_version_suffix` le refuse
        "lot_v0",    # sous la borne
        "lot_v100",  # au-dela de la borne : le fragment gagnerait un 3e chiffre
        "lot_v02",   # `EPIC11-ARB-88` : jamais de zero de tete
        "lot_v",     # fragment tronque
        "lot_vx",    # pas un nombre
        "_v2",       # un fragment SANS tige n'est pas un nom versionne
    ],
)
def test_ce_qui_RESSEMBLE_a_un_fragment_sans_en_etre_un_rend_l_ORIGINE(nom: str) -> None:
    """Le volet negatif, et il est ce qui donne du sens au volet positif.

    Sans lui, une lecture qui rendrait un rang pour `lot_v0` ou `lot_v100`
    passerait : aucun test positif ne regarde ces noms-la.
    """
    assert naming.rang_du_fragment_de_version(nom) == 1


def test_l_inverse_vit_A_COTE_de_la_fabrique_du_fragment() -> None:
    """Frontiere de non-redaction : un seul module connait la forme `_v<n>`.

    `encode` ne recompose pas cette expression pour son propre compte -- son
    source ne porte aucune expression reguliere sur le fragment de version.
    """
    assert naming.rang_du_fragment_de_version.__module__ == naming.format_version_suffix.__module__
    source = Path(encode_module.__file__).read_text(encoding="utf-8")
    assert "_v(" not in source and "_v([0-9]" not in source


# ===========================================================================
# La fabrique -- TROIS reconstructions, la cible AU MILIEU
# ===========================================================================

#: Les trois passes, dans l'ordre CHRONOLOGIQUE ou le manifest les porte.
#: Les slugs sont choisis pour que l'ordre chronologique et l'ordre
#: alphabetique **different** : sans cela, "l'ordre du manifest" et "un tri"
#: rendraient la meme liste, et l'AC 2 ne mesurerait rien.
SLUGS = ("scan-c", "scan-a", "scan-b")

#: La cible est la DEUXIEME des trois, donc ni la premiere ni la derniere.
RANG_CIBLE = 2


def _octet_temoin(dossier: Path, marqueur: int) -> None:
    """Rendre les copies distinguables AUX OCTETS, pas seulement par leur nom.

    Un condensat ne prouve rien quand la fixture est deterministe : les trois
    copies seraient octet pour octet identiques, et un test qui croit lire la
    deuxieme passe pourrait lire la premiere sans qu'aucune assertion ne bouge.
    L'octet touche est pris **en fin de fichier** -- donnee de pixel, jamais
    l'entete TIFF -- pour que `ffprobe` continue de lire l'image.
    """
    for fichier in sorted(dossier.iterdir()):
        if not fichier.is_file():
            continue
        octets = bytearray(fichier.read_bytes())
        octets[-1] = marqueur
        fichier.write_bytes(bytes(octets))


def projet_a_trois_reconstructions(
    tmp_path: Path, *, retirer_le_dossier_du_rang: int | None = None
) -> tuple[Path, dict]:
    """Un projet reel dont le lot a subi TROIS passes de scan.

    Le projet part de la chaine reelle (`scanned_project` : payloads,
    `write_lot_output_frames`, `persist_scan`) -- jamais d'un manifest ecrit a
    la main. Les deux passes supplementaires sont deposees comme un rescan
    `--nouvelle-version` les depose : `output-frames/<lot>_v2` et `<lot>_v3`.

    Le scalaire `lots[].output_frames_dir` pointe la **troisieme**, qui est
    l'etat qu'une troisieme passe reelle laisse -- et c'est ce qui rend un repli
    silencieux visible.
    """
    project_dir, manifest = scanned_project(tmp_path)
    lot = lot_of(manifest)
    origine = Path(str(lot["output_frames_dir"]))

    dossiers = [origine]
    for rang in (2, 3):
        copie = origine.parent / f"{origine.name}{naming.format_version_suffix(rang)}"
        shutil.copytree(project_dir / origine, project_dir / copie)
        _octet_temoin(project_dir / copie, marqueur=rang)
        dossiers.append(copie)

    lot["reconstructions"] = [
        {
            "ingest_slug": slug,
            "output_frames_dir": dossier.as_posix(),
            "origin": "scan",
            "status": "complete",
        }
        for slug, dossier in zip(SLUGS, dossiers)
    ]
    # Le scalaire suit la DERNIERE passe, comme `io/scan_manifest` l'ecrit.
    lot["output_frames_dir"] = dossiers[-1].as_posix()

    if retirer_le_dossier_du_rang is not None:
        shutil.rmtree(project_dir / dossiers[retirer_le_dossier_du_rang - 1])

    (project_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return project_dir, manifest


def dossier_du_rang(manifest: dict, rang: int) -> str:
    return str(lot_of(manifest)["reconstructions"][rang - 1]["output_frames_dir"])


# ===========================================================================
# T2 -- l'enumeration (AC 2)
# ===========================================================================

def test_l_enumeration_rend_les_TROIS_passes_avec_leur_rang_et_leur_slug(tmp_path) -> None:
    """AC 2 : rang, dossier, `ingest_slug`, presence disque -- pour chacune."""
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    passes = encode_module.enumerer_les_reconstructions(lot_of(manifest), project_dir)

    assert [p.rang for p in passes] == [1, 2, 3]
    assert [p.ingest_slug for p in passes] == list(SLUGS)
    assert [p.output_frames_dir for p in passes] == [
        dossier_du_rang(manifest, rang) for rang in (1, 2, 3)
    ]
    assert all(p.presente for p in passes)


def test_l_enumeration_rend_l_ordre_du_manifest_et_JAMAIS_un_tri(tmp_path) -> None:
    """`EPIC11-ARB-109` : l'ordre est CHRONOLOGIQUE et jamais trie.

    Il porte "quelle passe a suivi laquelle", que le tri detruirait. Les slugs
    de la fabrique sont ordonnes `scan-c`, `scan-a`, `scan-b` : un tri les
    rendrait dans un autre ordre, ce qui separe les deux hypotheses.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    passes = encode_module.enumerer_les_reconstructions(lot_of(manifest), project_dir)

    rendus = [p.ingest_slug for p in passes]
    assert rendus == list(SLUGS)
    assert rendus != sorted(SLUGS), (
        "temoin : si la fabrique portait des slugs deja tries, ce banc serait "
        "vert sans rien mesurer")


def test_l_enumeration_porte_la_PRESENCE_DISQUE_plutot_que_de_la_laisser_juger(
        tmp_path) -> None:
    """`EPIC11-ARB-30` : le coeur enumere, l'appelant n'ecrit aucun jugement.

    La passe du MILIEU est celle dont le dossier manque : une enumeration qui
    ne regarderait que la premiere ou la derniere ne le verrait pas.
    """
    project_dir, manifest = projet_a_trois_reconstructions(
        tmp_path, retirer_le_dossier_du_rang=RANG_CIBLE)
    passes = encode_module.enumerer_les_reconstructions(lot_of(manifest), project_dir)

    assert [p.presente for p in passes] == [True, False, True]
    # L'entree absente reste ENUMEREE, avec son dossier et son slug : une
    # enumeration qui la sauterait obligerait l'appelant a rejuger.
    assert passes[RANG_CIBLE - 1].output_frames_dir == dossier_du_rang(manifest, RANG_CIBLE)
    assert passes[RANG_CIBLE - 1].ingest_slug == SLUGS[RANG_CIBLE - 1]


def test_une_entree_SANS_dossier_est_enumeree_sans_rang_et_sans_presence(tmp_path) -> None:
    """Le schema ne rend `required` que `ingest_slug` : le cas est legal.

    Elle est enumeree -- pas jugee, pas sautee -- avec `rang` a `None`.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot = lot_of(manifest)
    lot["reconstructions"][RANG_CIBLE - 1].pop("output_frames_dir")

    passes = encode_module.enumerer_les_reconstructions(lot, project_dir)
    milieu = passes[RANG_CIBLE - 1]
    assert len(passes) == 3
    assert milieu.rang is None
    assert milieu.output_frames_dir == ""
    assert milieu.presente is False
    assert milieu.ingest_slug == SLUGS[RANG_CIBLE - 1]


def test_un_lot_SANS_historique_enumere_ZERO_passe(tmp_path) -> None:
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot = lot_of(manifest)
    lot.pop("reconstructions")
    assert encode_module.enumerer_les_reconstructions(lot, project_dir) == []


# ===========================================================================
# T3 / T4 -- la designation atteint la decision (AC 1, AC 3, AC 5)
# ===========================================================================

def plan(project_dir: Path, manifest: dict, **kwargs):
    return encode_module.plan_encode(project_dir, manifest, lot_id=LOT, **kwargs)


def test_SANS_designation_le_comportement_est_CELUI_D_AUJOURD_HUI(tmp_path) -> None:
    """AC 1 : l'absence de designation n'est jamais un refus.

    Elle rend le scalaire du lot, c'est-a-dire la DERNIERE passe.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    decide = plan(project_dir, manifest)
    assert decide.frame_paths[0].parent.name == Path(dossier_du_rang(manifest, 3)).name
    assert decide.reconstruction_designee == ""


def test_la_passe_du_MILIEU_est_joignable_alors_que_le_lot_pointe_la_DERNIERE(
        tmp_path) -> None:
    """AC 1, AC 5, `EPIC11-ARB-105` -- le coeur de la story.

    Le scalaire du lot pointe la TROISIEME passe. Designer la DEUXIEME doit
    rendre la deuxieme : ni la premiere (un `find` fautif), ni la troisieme (un
    repli silencieux). Les trois dossiers different aussi AUX OCTETS, donc
    l'assertion ne repose pas sur le seul nom de dossier.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    vise = dossier_du_rang(manifest, RANG_CIBLE)

    par_dossier = plan(project_dir, manifest, reconstruction_visee=vise)
    par_rang = plan(project_dir, manifest, reconstruction_visee=RANG_CIBLE)

    for decide in (par_dossier, par_rang):
        assert decide.frame_paths[0].parent == project_dir / vise
        assert decide.reconstruction_designee == vise
        # Le TEMOIN d'octets : la frame lue vient bien de la copie du milieu.
        assert decide.frame_paths[0].read_bytes()[-1] == RANG_CIBLE
        assert decide.frame_paths[0].read_bytes()[-1] != 3

    assert par_dossier.frame_paths == par_rang.frame_paths


def test_la_PREMIERE_passe_est_joignable_elle_aussi(tmp_path) -> None:
    """Volet symetrique : la designation ne privilegie aucune position.

    Sans lui, une lecture qui rendrait toujours l'element du milieu passerait.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    vise = dossier_du_rang(manifest, 1)
    decide = plan(project_dir, manifest, reconstruction_visee=1)
    assert decide.frame_paths[0].parent == project_dir / vise
    assert decide.frame_paths[0].read_bytes()[-1] != RANG_CIBLE


def test_un_dossier_designe_ABSENT_refuse_en_le_NOMMANT_et_ne_se_rabat_sur_AUCUNE_autre_passe(
        tmp_path) -> None:
    """AC 3, `EPIC11-ARB-89`.

    La cible est celle du MILIEU, et les deux autres passes sont **presentes**
    sur le disque : un repli silencieux aurait donc de quoi se rabattre, et
    c'est cela qui rend le refus mesurable. La mesure porte sur l'ABSENCE de
    plan -- une levee seule ne dirait pas qu'aucune autre passe n'a servi.
    """
    project_dir, manifest = projet_a_trois_reconstructions(
        tmp_path, retirer_le_dossier_du_rang=RANG_CIBLE)
    vise = dossier_du_rang(manifest, RANG_CIBLE)

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee=vise)

    assert refus.value.code == encode_module.ENCODE_OUTPUT_DIR_ABSENT
    message = str(refus.value)
    assert vise in message
    # **Aucune des deux autres passes n'est proposee comme repli**, et la mesure
    # porte sur les SLUGS et non sur les dossiers : le dossier d'origine est un
    # PREFIXE de celui de la version 2 (`..._5` contre `..._5_v2`), si bien
    # qu'une comparaison de sous-chaine y serait vraie sans rien mesurer. Les
    # trois slugs, eux, ne se prefixent pas.
    assert SLUGS[RANG_CIBLE - 1] in message
    assert SLUGS[0] not in message
    assert SLUGS[2] not in message
    assert dossier_du_rang(manifest, 3) not in message


def test_une_designation_INCONNUE_refuse_en_ENUMERANT_les_passes_disponibles(
        tmp_path) -> None:
    """AC 3, second volet : un refus qui n'offre aucune issue est fautif.

    `EPIC11-ARB-89` -- jamais un blocage sec. Le refus nomme donc les trois
    passes reellement disponibles.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee="output-frames/inexistant")

    assert refus.value.code == encode_module.ENCODE_RECONSTRUCTION_UNKNOWN
    message = str(refus.value)
    assert "output-frames/inexistant" in message
    for rang in (1, 2, 3):
        assert dossier_du_rang(manifest, rang) in message
    for slug in SLUGS:
        assert slug in message


def test_un_RANG_inconnu_refuse_de_la_meme_facon(tmp_path) -> None:
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee=7)
    assert refus.value.code == encode_module.ENCODE_RECONSTRUCTION_UNKNOWN
    assert "7" in str(refus.value)


def test_un_lot_SANS_historique_refuse_une_designation_en_le_DISANT(tmp_path) -> None:
    """Cas limite tranche : un manifeste anterieur a `EPIC11-ARB-109`.

    Il n'a pas d'historique. Refuser en le disant vaut mieux qu'un repli.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot_of(manifest).pop("reconstructions")
    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee=2)
    assert refus.value.code == encode_module.ENCODE_RECONSTRUCTION_UNKNOWN
    assert "aucune" in str(refus.value).lower()


@pytest.mark.parametrize("valeur", [True, False, 2.0, ["output-frames/x"], object()])
def test_une_designation_d_un_TYPE_inattendu_refuse_en_nommant_le_type(
        tmp_path, valeur) -> None:
    """`True` est le cas qui mord : `bool` est un `int` en Python.

    Sans garde, `reconstruction_visee=True` designerait le rang 1 **en
    silence** -- un choix pris a la place de l'operateur.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee=valeur)
    assert refus.value.code == encode_module.ENCODE_RECONSTRUCTION_UNKNOWN
    assert type(valeur).__name__ in str(refus.value)


def test_la_designation_PRIME_un_lot_sans_scalaire_declare(tmp_path) -> None:
    """Cas limite tranche : le refus "le lot n'a pas ete rescanne" ne joue pas.

    Avec une designation, l'operateur nomme une passe, et c'est elle qui est
    jugee -- pas le champ scalaire qu'il n'a pas utilise.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot_of(manifest).pop("output_frames_dir")
    decide = plan(project_dir, manifest, reconstruction_visee=RANG_CIBLE)
    assert decide.frame_paths[0].parent.name.endswith(
        naming.format_version_suffix(RANG_CIBLE))


def test_la_garde_d_ETAT_joue_dans_TOUS_les_regimes(tmp_path) -> None:
    """Une seule garde, jamais recopiee : l'etat est verifie avant tout dossier.

    Un lot ramene en deca de `scan` refuse par son ETAT, designation ou non --
    et le code n'est pas celui de la designation.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot_of(manifest)["state"] = "extract"
    for designation in (None, RANG_CIBLE, dossier_du_rang(manifest, RANG_CIBLE)):
        with pytest.raises(encode_module.EncodeDecisionError) as refus:
            plan(project_dir, manifest, reconstruction_visee=designation)
        assert refus.value.code == encode_module.ENCODE_LOT_STATE_TOO_EARLY, designation


def test_le_recapitulatif_ne_change_QUE_si_une_designation_a_ete_faite(tmp_path) -> None:
    """Le dossier d'identite fige `stdout` au caractere pres sur 25 invocations.

    Sans designation, le recapitulatif doit donc etre celui d'avant ; avec une
    designation, il dit d'ou viennent les frames -- sans quoi l'operateur ne
    peut pas verifier ce qu'il vient de demander.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    vise = dossier_du_rang(manifest, RANG_CIBLE)

    sans = encode_module.render_summary(plan(project_dir, manifest))
    avec = encode_module.render_summary(
        plan(project_dir, manifest, reconstruction_visee=RANG_CIBLE))

    assert vise not in sans
    assert vise in avec


# ===========================================================================
# AC 4 -- l'arbitrage : la cle de famille ne gagne PAS la reconstruction
# ===========================================================================

def test_deux_masters_de_DEUX_reconstructions_partagent_la_meme_famille_et_le_second_prend_le_rang_2(
        tmp_path) -> None:
    """AC 4, volet positif.

    Deux masters issus de deux reconstructions differentes du meme lot, au meme
    profil et a la meme resolution, sont DEUX VERSIONS l'un de l'autre. Le
    motif est mecanique : une famille par reconstruction ferait partir chacune
    au RANG_ORIGINE, qui ne porte AUCUN fragment de nom -- les deux masters
    reclameraient alors le MEME nom de fichier.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)

    premier = plan(project_dir, manifest, reconstruction_visee=1)
    second = plan(project_dir, manifest, reconstruction_visee=RANG_CIBLE)
    assert premier.masters_family_key == second.masters_family_key

    # Le premier master declare, le second demande une nouvelle version : la
    # ligne d'eau de la famille commune le porte au rang 2.
    lot = lot_of(manifest)
    lot["encoded_masters"] = [{
        "path": f"outputs/{premier.output_path.name}",
        "profile_id": premier.profile_id,
        "frame_count": premier.frame_count,
        "incomplete": False,
    }]
    (project_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    versionne = plan(project_dir, manifest,
                     reconstruction_visee=RANG_CIBLE, nouvelle_version=True)
    assert versionne.master_version_rank == 2
    assert versionne.output_path.stem.endswith(naming.format_version_suffix(2))


def test_la_cle_de_famille_ne_porte_AUCUN_parametre_de_reconstruction() -> None:
    """AC 4, volet negatif -- sans lui, l'egalite ci-dessus ne mesure rien.

    Une egalite se lit aussi bien sur deux plans qui se ressemblent que sur une
    cle qui ignore ce qu'on lui passe. Ici la mesure porte sur la SIGNATURE et
    sur le SOURCE : la reconstruction n'y entre pas.
    """
    parametres = inspect.signature(encode_module.cle_de_famille_de_master).parameters
    assert list(parametres) == ["profile_id", "resolution_segment"]
    source = inspect.getsource(encode_module.cle_de_famille_de_master)
    assert "reconstruction" not in source
    # La propriete qui la porte sur le plan ne la lit pas davantage.
    portee = inspect.getsource(encode_module.EncodePlan.masters_family_key.fget)
    assert "reconstruction" not in portee


# ===========================================================================
# AC 6 / AC 7 -- transport et vocabulaire
# ===========================================================================

def test_le_point_d_entree_de_coeur_TRANSPORTE_la_designation() -> None:
    """AC 6 : la TUI (11.8, ecran 1) appelle `encode_master`, pas `cli`."""
    assert "reconstruction_visee" in encode_master.MOTS_CLES_DE_LA_DECISION
    assert "reconstruction_visee" in inspect.signature(
        encode_master.encoder_le_master_du_lot).parameters
    assert "reconstruction_visee" in inspect.signature(
        encode_module.plan_encode).parameters


def test_le_code_neuf_est_MIROITE_dans_le_vocabulaire_de_la_previz() -> None:
    """AC 7 : le miroir de `encode_previz` est litteral ET positionnel.

    Le defaut a deja ete paye : `main` avait ajoute `RANGS_DE_MASTER_EPUISES`
    chez le producteur sans le miroir, et trois bancs ont rougi.
    """
    codes = encode_module.ENCODE_REFUSAL_CODES
    miroir = encode_previz.ENCODE_PREVIZ_REFUSAL_CODES
    assert encode_module.ENCODE_RECONSTRUCTION_UNKNOWN in codes
    assert list(codes) == list(miroir)


def test_le_dossier_de_lot_absent_REUTILISE_son_code_plutot_que_d_en_creer_un() -> None:
    """AC 7 : un seul code neuf, pas deux.

    Un dossier designe absent EST un dossier de lot absent ; grossir un
    vocabulaire ferme pour redire la meme chose serait une seconde verite.
    """
    neufs = [c for c in encode_module.ENCODE_REFUSAL_CODES if "RECONSTRUCTION" in c]
    assert neufs == [encode_module.ENCODE_RECONSTRUCTION_UNKNOWN]


# ===========================================================================
# AC 8 -- les trois frontieres de perimetre
# ===========================================================================

def _modules_importes(module) -> set[str]:
    """Les modules reellement IMPORTES, lus a l'AST et jamais par un grep.

    Le depot a deja paye la confusion entre les deux : quatre bancs avaient ete
    declares "important PySide6" alors qu'ils ne faisaient que CITER le nom
    dans une liste d'imports interdits. `encode.py` est dans le meme cas ici --
    sa docstring nomme `tui/projet_lecture` pour raconter le defaut que
    `list_encodable_lots` ferme, et un grep y verrait un import.
    """
    arbre = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            noms.add(noeud.module or "")
            noms.update(f"{noeud.module or ''}.{a.name}" for a in noeud.names)
    return noms


def test_les_modules_de_cette_story_n_importent_AUCUN_fichier_de_tui() -> None:
    """AC 8 : les ecrans de l'atelier Exports sont bloques ailleurs.

    **La mesure est STATIQUE et non un `git diff`**, et c'est delibere : une
    frontiere epinglee sur le commit de depart de cette branche deviendrait
    rouge le jour de la fusion sur `main`, ou ce meme intervalle contient tout
    le reste du travail -- elle mesurerait la fusion, pas la story. La propriete
    qui survit au report est celle-ci : les quatre modules touches sont du
    **coeur**, et le coeur ne connait pas la TUI.
    """
    for module in (encode_module, encode_master, encode_previz, naming):
        fautifs = [n for n in _modules_importes(module)
                   if n == "tui" or ".tui" in n or n.startswith("tui.")]
        assert fautifs == [], (module.__name__, fautifs)
    # Temoin : la lecture d'imports rend bien quelque chose, sans quoi la garde
    # ci-dessus serait verte sur un ensemble vide.
    assert "codec_profiles" in {n.rsplit(".", 1)[-1]
                                for n in _modules_importes(encode_module)}


def test_le_parser_argparse_de_encode_ne_gagne_AUCUNE_option() -> None:
    """AC 8 : le dossier d'identite fige `stderr` au caractere pres.

    Deux de ses scenarios (`22-profil-inconnu`,
    `43-cadence-source-syntaxe-fautive`) recopient la ligne `usage:` d'argparse,
    **qui enumere les options** -- la reference porte, verbatim,
    `[--nouvelle-version] [--yes]`. Une option de plus les ferait diverger et
    exigerait de rejouer la reference sur `cf0e6f4f`.

    **La mesure porte sur `cli.py` et pas sur un diff** : le jour ou quelqu'un
    cablera `--reconstruction`, ce banc rougira **avec le motif sous les yeux**,
    quel que soit l'age de la branche. Le consommateur vise reste la TUI, qui
    appelle `encode_master`.
    """
    cli_source = (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
        encoding="utf-8")
    assert "reconstruction_visee" not in cli_source
    assert "--reconstruction" not in cli_source
    # Temoin : sans lui, une faute de chemin rendrait ce banc vert sur un
    # fichier vide. `--nouvelle-version`, elle, EST cablee et doit se lire.
    assert "--nouvelle-version" in cli_source


def test_ce_que_encode_ECRIT_au_manifest_est_INCHANGE() -> None:
    """AC 8 : onze scenarios du dossier d'identite comparent chaque JSON aplati."""
    from mixed_media_utility.io import encode_manifest

    assert len(encode_manifest.ENCODE_MASTER_FIELDS) == 4
    assert set(encode_manifest.ENCODE_LOT_FIELDS) == {
        "state", "encoded_masters", "masters_version_watermark"}


# ===========================================================================
# T7 -- les findings CRITIQUE de la revue en trois couches du 2026-09-03
#
# Revue menee par la session « EPIC 6 stories 6.7 et 6.8 » sur
# `claude/epic6_6-7_6-8` (rapport `review-6-8-triage.md`, commit `fd66ebb3`),
# 101 mutants injectes par les trois couches. Les fermetures sont ecrites ici,
# sur `oc/epic-11-TUI`, parce qu'`EPIC11-ARB-77` veut que le coeur de l'Epic 11
# ne se pousse nulle part ailleurs -- et pour qu'une meme fermeture n'existe
# pas sur deux branches a la fois.
# ===========================================================================

def _entree_hors_norme() -> object:
    """Une entree de `reconstructions[]` qui n'est PAS un objet.

    Le manifeste est un document que le depot relit sans le posseder : un
    schema additif, une migration, une edition a la main peuvent y deposer
    autre chose qu'un objet. `enumerer_les_reconstructions` la saute
    (`continue`) plutot que de tomber -- c'est ce `continue` que le present
    banc mesure.
    """
    return "cette entree n'est pas un objet"


def test_une_entree_NON_OBJET_en_tete_n_ARRETE_PAS_l_enumeration(tmp_path) -> None:
    """R2 -- la regle des fabriques tenue A LA LETTRE, manquee sur le fond.

    La fabrique de ce banc porte bien trois passes avec la cible au milieu,
    et le point 2 bis de la checklist est donc satisfait. Mais ses trois
    entrees sont **toutes des `Mapping` bien formes**, si bien que la branche
    `continue` d'`enumerer_les_reconstructions` n'est **jamais empruntee** :
    le mutant `continue` -> `break` survivait aux 33 tests de ce fichier.

    Trois elements ne ferment pas une terminaison de boucle si aucun des trois
    n'emprunte la branche que le mutant deplace. C'est la condition d'entree du
    point 2 bis prise en defaut par elle-meme, et c'est le seul enseignement de
    ce test qui vaille au-dela de la story.

    La panne, si le `break` revenait : les deux passes reelles disparaissent de
    l'enumeration, et `mmu encode` refuse alors en affirmant « Passes declarees
    par ce lot: aucune » sur un lot qui en declare deux -- un refus qui MENT sur
    l'historique, la ou `EPIC11-ARB-89` fait de l'enumeration l'issue.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot = lot_of(manifest)
    lot["reconstructions"] = [_entree_hors_norme()] + list(lot["reconstructions"])

    passes = encode_module.enumerer_les_reconstructions(lot, project_dir)

    # SOUS LE MUTANT : zero. Aujourd'hui : les trois, dans l'ordre du manifest.
    assert [p.ingest_slug for p in passes] == list(SLUGS)
    assert len(passes) == 3


def test_une_entree_NON_OBJET_AU_MILIEU_ne_coupe_pas_la_QUEUE_de_l_enumeration(
        tmp_path) -> None:
    """Le volet qui separe `continue` de `break` a l'endroit ou ils divergent.

    En tete, `break` rend zero passe et `continue` les rend toutes : l'ecart est
    maximal, donc facile. Au MILIEU, `break` rend la premiere seule -- une liste
    non vide, plausible, et c'est le regime ou un mutant se cache le mieux.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    lot = lot_of(manifest)
    entrees = list(lot["reconstructions"])
    lot["reconstructions"] = [entrees[0], _entree_hors_norme(), entrees[1], entrees[2]]

    passes = encode_module.enumerer_les_reconstructions(lot, project_dir)

    assert [p.ingest_slug for p in passes] == list(SLUGS)


#: L'ordre dans lequel la fabrique de base range ses trois passes fait
#: coincider la chronologie avec l'ordre des rangs (1, 2, 3) ET avec l'ordre
#: alphabetique des dossiers (`lot`, `lot_v2`, `lot_v3`) : deux des trois tris
#: les plus naturels y rendent exactement la liste du manifest. Cette
#: permutation-la les separe tous les trois d'un coup.
ORDRE_QUI_SEPARE_LES_TROIS_TRIS = (3, 1, 2)


def permuter_les_reconstructions(manifest: dict, ordre: tuple[int, ...]) -> list:
    """Ranger `reconstructions[]` dans l'ordre des RANGS donne.

    Une chronologie 3, 1, 2 n'est pas une curiosite de banc : `EPIC11-ARB-92`
    veut qu'un rang se libere **en queue** et se reemploie, donc qu'une passe
    de rang 2 puisse etre la plus recente des trois. Le jour ou cela se
    produira sur un vrai projet est exactement celui ou un tri par rang
    mentirait le plus.
    """
    lot = lot_of(manifest)
    entrees = list(lot["reconstructions"])
    lot["reconstructions"] = [entrees[rang - 1] for rang in ordre]
    return lot["reconstructions"]


def _lignes_de_l_enumeration(message: str) -> list[str]:
    """Les lignes « rang N, dossier ... (scan ...) » d'un message de refus."""
    return [ligne.strip()[2:].strip()
            for ligne in message.splitlines() if ligne.strip().startswith("- rang ")]


def test_la_DESCRIPTION_du_refus_rend_l_ordre_du_MANIFEST_et_JAMAIS_un_tri(
        tmp_path) -> None:
    """R3 -- l'ordre etait mesure la ou personne ne le lit.

    La propriete « l'ordre du manifest, jamais un tri » etait mesuree **une
    fois**, sur `enumerer_les_reconstructions`, et pas sur le second
    consommateur de la meme collection : `_decrire_les_reconstructions`, qui
    compose le message de refus. Or ce message est le **seul endroit du
    produit** ou un humain voit cette liste, et `EPIC11-ARB-89` en fait l'issue
    qui rend le refus acceptable. Un `sorted()` injecte la survivait.

    L'ordre lu ici est celui du manifest, et le TEMOIN ci-dessous verifie qu'il
    se separe des **trois** tris naturels -- par slug, par rang, par dossier.
    Sans ce temoin, le test serait vert sur une fabrique dont la chronologie
    coincide avec un tri, ce qui etait le cas de la fabrique de ce banc.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    permuter_les_reconstructions(manifest, ORDRE_QUI_SEPARE_LES_TROIS_TRIS)
    attendus = [str(e["ingest_slug"]) for e in lot_of(manifest)["reconstructions"]]

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee="output-frames/inexistant")

    lignes = _lignes_de_l_enumeration(str(refus.value))
    assert len(lignes) == 3, lignes
    assert [ligne.split("(scan ")[1].rstrip(")") for ligne in lignes] == attendus

    # TEMOIN, et il porte sur la FABRIQUE : les trois tris se separent de la
    # chronologie. Un seul d'entre eux coincidant, le test ci-dessus serait vert
    # sous le mutant correspondant.
    rangs = [int(ligne.split("rang ")[1].split(",")[0]) for ligne in lignes]
    # Story 11.14 : le libelle nomme desormais l'objet par son TYPE -- une
    # passe EST un lot scanne --, la ou il disait « dossier ».
    lots_scannes = [ligne.split("lot scanne ")[1].split(" (scan")[0]
                    for ligne in lignes]
    assert attendus != sorted(attendus), "un tri par slug rendrait cette liste"
    assert rangs != sorted(rangs), "un tri par rang rendrait cette liste"
    assert lots_scannes != sorted(lots_scannes), (
        "un tri par lot scanne rendrait cette liste")


def _passe_qui_pointe(manifest: dict, rang: int, dossier: str) -> str:
    """Faire pointer la passe de `rang` sur `dossier`, et rendre ce dossier."""
    lot_of(manifest)["reconstructions"][rang - 1]["output_frames_dir"] = dossier
    return dossier


@pytest.mark.parametrize("forme", ["absolu", "remontee"])
def test_un_dossier_de_passe_qui_SORT_du_projet_refuse_DANS_le_vocabulaire(
        tmp_path, forme: str) -> None:
    """R4 -- trois pannes mesurees a la sonde, fermees par une seule garde.

    Avant : un `output_frames_dir` **absolu** faisait sortir un `ValueError`
    NU de `plan_encode` -- hors du vocabulaire ferme de refus, et leve APRES
    que la decision entiere ait ete prise, si bien qu'une TUI recevait une
    trace la ou le contrat promet un code ; une **remontee** faisait construire
    un plan **complet** sur des frames etrangeres au projet, `presente=True` et
    aucun refus.

    Le dossier hors projet porte de VRAIES frames, copiees depuis une passe
    reelle : sans elles le refus tomberait pour « dossier absent », et la garde
    de confinement ne serait mesuree par rien.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    dehors = tmp_path / "hors-projet"
    shutil.copytree(project_dir / dossier_du_rang(manifest, 1), dehors)

    declare = (dehors.as_posix() if forme == "absolu"
               else f"../{dehors.name}")
    vise = _passe_qui_pointe(manifest, RANG_CIBLE, declare)

    with pytest.raises(encode_module.EncodeDecisionError) as refus:
        plan(project_dir, manifest, reconstruction_visee=vise)

    assert refus.value.code == encode_module.ENCODE_RECONSTRUCTION_UNKNOWN
    assert refus.value.code in encode_module.ENCODE_REFUSAL_CODES
    message = str(refus.value)
    assert declare in message
    # `EPIC11-ARB-89` : un refus nomme ce qui existe, et offre une issue.
    assert "Passes declarees par ce lot" in message
    assert "issues" in message


def test_la_garde_de_CONFINEMENT_ne_refuse_PAS_une_passe_legitime(tmp_path) -> None:
    """Le volet symetrique, sans lequel une garde trop large passerait.

    Une garde qui refuserait tout -- ou qui refuserait le dossier projet
    lui-meme mal compare -- rendrait les trois tests de refus verts sans qu'un
    seul encodage designe fonctionne encore.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    vise = dossier_du_rang(manifest, RANG_CIBLE)
    decide = plan(project_dir, manifest, reconstruction_visee=vise)
    assert decide.reconstruction_designee == vise


def test_la_regle_de_CONFINEMENT_a_UN_SEUL_domicile_ET_DEUX_appelants() -> None:
    """R4, volet de mecanisme : trois lecteurs la voulaient, deux l'avaient.

    Le depot avait ferme cette famille deux fois -- `output_frames_dir_from_slug`
    et `project_maintenance._sous_le_projet` -- et le lecteur neuf de la story
    6.8 n'avait ni l'une ni l'autre, parce que rien ne pouvait le lui dire. La
    regle vit desormais dans `io/project_layout` ; ce banc mesure qu'elle y est,
    qu'elle rougit **dans les deux sens**, et que les deux juges du depot
    l'appellent au lieu d'en porter chacun sa version.

    **Ce que cette frontiere NE mesure PAS, dit plutot que tu** : elle ne verra
    pas une troisieme redaction ecrite de zero ailleurs. La premiere version de
    ce test cherchait l'idiome (`resolve()` compare a `.parents`) par grep, et
    elle attrapait deux `parents[3]` qui cherchent la racine du depot **et** la
    garde de CHEVAUCHEMENT de `project_maintenance` (`dossier in cible.parents`,
    :281), qui est une autre regle -- deux lots qui se contiennent, pas un
    chemin qui sort du projet. Un grep assez large pour voir la recopie voyait
    aussi ce qui n'en est pas une, et une liste d'exceptions aurait detruit la
    propriete « l'ensemble des sites est exactement {un} ». On mesure donc ce
    qui se mesure exactement.
    """
    from mixed_media_utility.io import project_layout

    # La regle elle-meme, dans les DEUX sens : sans le volet negatif, un
    # predicat rendant toujours `True` passerait le volet positif.
    racine = REPO_ROOT
    assert project_layout.est_strictement_sous_le_projet(racine, racine / "src")
    assert not project_layout.est_strictement_sous_le_projet(racine, racine)
    assert not project_layout.est_strictement_sous_le_projet(racine, racine.parent)

    # Les deux juges du depot l'APPELLENT -- ils ne la recopient pas.
    for module in (encode_module, __import__(
            "mixed_media_utility.project_maintenance", fromlist=["x"])):
        source = inspect.getsource(module)
        assert "est_strictement_sous_le_projet" in source, module.__name__


# ===========================================================================
# T8 -- les deux tolerances que la session soeur a redites NOMMEMENT
# ===========================================================================

#: Les cinq ecritures d'un meme dossier que la normalisation ramene a une
#: seule. Les quatre dernieres sont ce qu'un operateur produit reellement :
#: une completion de shell laisse la barre finale, un copier-coller laisse le
#: `./`, une concatenation maladroite double la barre, et un explorateur
#: Windows rend des antislashs.
ECRITURES_DU_MEME_DOSSIER = {
    "canonique": lambda d: d,
    "barre_finale": lambda d: d + "/",
    "cran_de_tete": lambda d: "./" + d,
    "double_barre": lambda d: d.replace("/", "//"),
    "antislash": lambda d: d.replace("/", "\\"),
}


@pytest.mark.parametrize("forme", sorted(ECRITURES_DU_MEME_DOSSIER))
def test_CINQ_ecritures_du_meme_dossier_designent_la_MEME_passe(
        tmp_path, forme: str) -> None:
    """R7 -- une normalisation a ZERO test, et une docstring qui disait l'inverse.

    Les deux mutants de la normalisation (retrait du `.replace()` d'antislash,
    retrait du `PurePosixPath(...).as_posix()`) survivaient tous les deux : la
    fonctionnalite existait sans etre mesuree une seule fois.

    **L'arbitrage rendu, et il est le mien -- reversible** : le code est garde,
    la docstring corrigee. Elle disait "separateurs POSIX", or le code accepte
    l'antislash depuis toujours ; le NFR1 fait de Windows une plateforme cible,
    et refuser a un operateur Windows l'orthographe de son propre explorateur
    serait un blocage sec sur une faute qui n'en est pas une. Fermer ce finding
    par « deux parametrages de plus » aurait **gele** ce choix sans le nommer :
    c'est la session qui a mene la revue qui l'a dit, et elle avait raison de le
    dire avant que la fermeture facile ne tranche a ma place.

    Cout residuel, dit plutot que tu : sur un systeme POSIX, un dossier dont le
    nom contient litteralement un antislash serait mal lu. Le producteur n'en
    ecrit aucun, donc le cas demande un manifeste edite a la main.
    """
    project_dir, manifest = projet_a_trois_reconstructions(tmp_path)
    canonique = dossier_du_rang(manifest, RANG_CIBLE)
    ecriture = ECRITURES_DU_MEME_DOSSIER[forme](canonique)

    # TEMOIN : les quatre variantes s'ECARTENT bien de la forme canonique.
    # Sans lui, une table dont une entree rendrait `d` inchange serait verte
    # sans rien mesurer de la normalisation.
    assert (ecriture == canonique) == (forme == "canonique"), ecriture

    decide = plan(project_dir, manifest, reconstruction_visee=ecriture)

    assert decide.reconstruction_designee == canonique
    # Le TEMOIN d'octets : c'est bien la passe du MILIEU qui a ete lue, et non
    # un repli sur le scalaire du lot (qui pointe la troisieme).
    assert decide.frame_paths[0].read_bytes()[-1] == RANG_CIBLE


@pytest.mark.parametrize(
    "nom",
    [
        "lot_v2-bis",      # une copie manuelle, le cas de terrain
        "lot_v2.old",
        "lot_v2 (copie)",
        "lot_v2_brouillon",
    ],
)
def test_ce_qui_PORTE_un_fragment_SANS_finir_par_lui_rend_l_ORIGINE(nom: str) -> None:
    """R8 -- l'ancre `$` n'avait AUCUN cas negatif, et c'est elle qui tient R12.

    Les sept noms du volet negatif existant ne portent rien **apres** le
    fragment (`lot_v0`, `lot_v100`, `lot_vx`, ...), or c'est la **seule** chose
    que le `$` ecarte : sans lui, `^.+_v([1-9][0-9]*)` mord sur `lot_v2-bis` --
    `.+` etant gourmand -- et rend **2** la ou le nom ne designe aucune version.

    **Pourquoi cette garde-la plutot qu'une autre** : la session qui a mene la
    revue classe R12 (`next(reversed(passes))` survit sur la resolution par
    rang) en tolerance parce qu'elle n'a **pas su exhiber** un chemin de
    production creant deux dossiers de meme rang pour un lot. Le `$` est
    precisement ce qui l'en empeche : une copie manuelle `lot_v2-bis` a cote de
    `lot_v2` rendrait deux passes de rang 2, et la resolution par rang
    choisirait alors silencieusement l'une des deux. Fermer R8 tient R12 ;
    l'inverse n'est pas vrai, et c'est pour cela qu'on ferme celle-ci.
    """
    assert naming.rang_du_fragment_de_version(nom) == 1
