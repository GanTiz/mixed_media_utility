# -*- coding: utf-8 -*-
"""`EPIC11-ARB-261` **au TERMINAL** -- la moitie qui manquait entierement.

La revue du 2026-09-07 a trouve, par ses trois couches independamment, que
`io/calibration_profile.profils_de_la_chaine` n'avait aucun appelant. Le lot de
fermeture l'a cable... **dans la TUI seule**. Mesure prise le meme jour, avant
ce banc : `mmu scan ... calibrate` sur une chaine deja calibree sous un autre
libelle ecrivait un SECOND fichier et n'en disait pas un mot -- c'est-a-dire
exactement le regime que l'arbitrage ferme, laisse ouvert pour l'operateur qui
travaille en ligne de commande.

**Ce que ce banc mesure, et qu'aucun autre ne mesurait** : la sortie du
terminal. Le banc de la TUI mesure un ecran ; celui du coeur mesure une liste
de chemins. Ni l'un ni l'autre ne voit qu'une commande se tait.

REGLE DES FABRIQUES. Trois profils prealables **distinguables**, la cible ni en
tete ni en queue (`nnn` entre `aaa` et `zzz`), et une chaine voisine pour qu'un
balayage qui rendrait *tous* les profils du projet ne passe pas vert. Deux
cibles sont posees a **chaque bord** du listing trie -- point 4 de la regle des
fabriques, pose le 2026-09-03 sur un mutant qui sautait la derniere entree.

REGLE DES DRAPEAUX. `_stdin_is_interactive` **varie dans les deux sens**, et
c'est le drapeau dont tout ce chemin depend : un banc qui ne jouerait que le
regime non interactif ne verrait jamais l'invite, et un banc qui ne jouerait que
le terminal ne verrait jamais qu'un script est renseigne plutot que bloque.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import cli, scan_calibrate
from mixed_media_utility.io import project_layout

#: Deux chaines distinguables : une fabrique mono-chaine rendrait invisible un
#: balayage qui rendrait « tous les profils » au lieu de « ceux de la chaine ».
CHAINE_VISEE = "900-png-cccccccccccc"
CHAINE_VOISINE = "600-tif-dddddddddddd"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _document(radical: str, chaine: str) -> dict:
    """Un document de profil, ecrit au plus court.

    Le balayage inverse ne lit que `chain_id` ; un document complet ferait
    croire que la mesure depend d'autre chose.
    """
    return {"schema_version": 1, "chain_id": chaine, "label": radical,
            "correction_form_id": "affine_bgr_v1", "source_page_id": "p0"}


def _poser_un_profil(projet: Path, radical: str, chaine: str) -> Path:
    chemin = (projet / project_layout.VERSIONS_DIRNAME / "calibration"
              / f"{radical}.json")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(_document(radical, chaine)), encoding="utf-8")
    return chemin


class _JournalMuet:
    """Un journal qui ne rend rien, pour que la mesure porte sur la SORTIE.

    Il n'est pas une doublure du `logging` du depot : la commande y ecrit son
    compte rendu machine, que ce banc ne mesure pas. Ce qu'il mesure est ce que
    l'operateur LIT, et un operateur ne lit pas `scan.log`.
    """

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _consigne(projet: Path, radical: str, chaine: str = CHAINE_VISEE):
    """La passe **telle que le coeur la rend**, releve inclus.

    Le releve n'est pas recompose ici : il passe par
    `scan_calibrate.autres_profils_de_la_chaine`, donc ce banc mesure le meme
    calcul que la production. Le recomposer ferait un banc qui reste vert le
    jour ou le releve se trompe.
    """
    ecrit = _poser_un_profil(projet, radical, chaine)
    return scan_calibrate.ProfilDeChaineConsigne(
        profile_path=ecrit, chain_id=chaine, etiquette=radical,
        commentaire="", lot_correction=object(),
        document=_document(radical, chaine),
        autres_profils=tuple(scan_calibrate.autres_profils_de_la_chaine(
            projet, ecrit, chaine)))


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    project_layout.ensure_project_layout(dossier)
    return dossier


def _fichiers(projet: Path) -> list[str]:
    return sorted(
        chemin.name for chemin
        in (projet / project_layout.VERSIONS_DIRNAME / "calibration")
        .glob("*.json"))


def _jouer(projet, consigne, monkeypatch, capsys, *, terminal: bool,
           reponse: str = ""):
    """Jouer le chemin terminal, **le drapeau varie par ce parametre**.

    `_stdin_is_interactive` est substitue plutot que `sys.stdin` : c'est le
    predicat que le module isole precisement pour etre substituable, et sa
    docstring dit pourquoi (« le regime non teste serait alors precisement
    celui qui pend »).
    """
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: terminal)
    monkeypatch.setattr("builtins.input", lambda: reponse)
    cli._traiter_la_chaine_deja_calibree(projet, consigne, _JournalMuet())
    return capsys.readouterr()


# ---------------------------------------------------------------------------
# Le releve : ce qui declenche, et ce qui NE declenche pas
# ---------------------------------------------------------------------------

def test_une_chaine_deja_calibree_AVERTIT_au_terminal(projet, monkeypatch,
                                                      capsys):
    """Le defaut d'Egan, ferme : la commande ne se tait plus.

    Deux anciens profils, aux DEUX bords du listing trie (`aaa` et `zzz`), la
    cible au milieu (`nnn`). Un balayage tronque d'un bord laisserait un
    orphelin non nomme, et ce banc rougirait.
    """
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "mmm", CHAINE_VOISINE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=True, reponse="n")

    assert CHAINE_VISEE in sortie.err
    assert "aaa.json" in sortie.err and "zzz.json" in sortie.err, sortie.err
    assert "mmm.json" not in sortie.err, (
        "la chaine VOISINE ne doit pas etre nommee : deux dpi font deux "
        "chaines, et deux fichiers y sont corrects")


def test_une_RECALIBRATION_pure_ne_dit_RIEN(projet, monkeypatch, capsys):
    """Meme chaine, meme fichier : rien a trancher, donc rien a dire.

    Sans l'exclusion du fichier qu'on vient d'ecrire, tout operateur qui
    recalibre lirait l'avertissement -- l'invite qui apprend a repondre oui
    sans lire, que `write_profile` ecarte depuis 5.22.
    """
    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=True)

    assert sortie.err == "", sortie.err


def test_une_AUTRE_chaine_deja_calibree_ne_dit_RIEN(projet, monkeypatch,
                                                    capsys):
    """Deux scanners font deux chaines, et deux fichiers y sont justes."""
    _poser_un_profil(projet, "aaa", CHAINE_VOISINE)
    _poser_un_profil(projet, "zzz", CHAINE_VOISINE)

    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=True)

    assert sortie.err == "", sortie.err


# ---------------------------------------------------------------------------
# Les DEUX issues -- `EPIC11-ARB-89`, jamais un blocage sec
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reponse", ["y", "o", "Y", "oui"])
def test_l_operateur_qui_ACCEPTE_voit_les_anciens_retires(projet, monkeypatch,
                                                          capsys, reponse):
    """La seconde issue, celle qui ecrit. **Consciente, apres avertissement.**

    Quatre graphies de l'accord se jouent : l'operateur francais frappe `o`, et
    une garde qui ne reconnaitrait que `y` transformerait un accord en refus --
    silencieusement, puisque le refus ne dit rien de plus qu'un « conserves ».
    """
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=True, reponse=reponse)

    assert _fichiers(projet) == ["nnn.json"], _fichiers(projet)
    assert "2 ancien(s) profil(s)" in sortie.err, sortie.err


@pytest.mark.parametrize("reponse", ["n", "", "non", "peu importe"])
def test_l_operateur_qui_REFUSE_garde_les_deux(projet, monkeypatch, capsys,
                                               reponse):
    """La premiere issue, celle qui n'ecrit rien -- et c'est le DEFAUT.

    Une entree vide (l'operateur qui frappe Entree) et une reponse incomprise
    gardent les deux : `EPIC5-ARB-99` pose deja la meme regle pour la collision,
    « hors terminal, le defaut est l'empreinte, jamais l'ecrasement ». On ne
    boucle pas non plus sur une reponse incomprise -- une invite qui insiste est
    un cran de plus vers l'invite qui bloque.
    """
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)

    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=True, reponse=reponse)

    assert _fichiers(projet) == ["aaa.json", "nnn.json", "zzz.json"]
    assert cli.PHRASE_CONSERVATION_DES_DEUX in sortie.err, sortie.err


def test_HORS_terminal_rien_n_est_retire_et_la_seconde_issue_est_NOMMEE(
        projet, monkeypatch, capsys):
    """Le regime des scripts, de `cron` et de ces milliers de tests.

    **Jamais un blocage sec** (`EPIC11-ARB-89`) : la passe a abouti, le profil
    neuf est ecrit, et la phrase nomme ce qu'il reste a faire. Un script qui
    lirait seulement « les deux profils sont conserves » ne saurait pas comment
    en sortir -- c'est le refus sans issue que l'arbitrage ecarte.
    """
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)

    sortie = _jouer(projet, _consigne(projet, "nnn"), monkeypatch, capsys,
                    terminal=False, reponse="y")

    assert _fichiers(projet) == ["aaa.json", "nnn.json"], (
        "hors terminal, la reponse posee sur `input` ne doit JAMAIS etre lue : "
        "personne ne l'a frappee")
    assert cli.PHRASE_HORS_TERMINAL_CHAINE_DEJA_CALIBREE in sortie.err


def test_un_retrait_qui_ECHOUE_se_prononce_et_n_emporte_pas_les_autres(
        projet, monkeypatch, capsys):
    """`EPIC11-ARB-258` : un refus se dit, et il ne fait pas perdre le reste.

    Le motif systeme voyage **verbatim** -- « Permission denied » dit a
    l'operateur quoi faire, « retrait impossible » ne dit rien --, et le
    resistant est annonce AVANT le cardinal des retires : sinon l'operateur lit
    « 1 profil retire » et rate celui qui est reste.
    """
    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    _poser_un_profil(projet, "zzz", CHAINE_VISEE)
    consigne = _consigne(projet, "nnn")
    reel = Path.unlink

    def unlink_capricieux(self, *args, **kwargs):
        if self.name == "aaa.json":
            raise PermissionError("Permission denied")
        return reel(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_capricieux)
    sortie = _jouer(projet, consigne, monkeypatch, capsys, terminal=True,
                    reponse="o")

    assert _fichiers(projet) == ["aaa.json", "nnn.json"], _fichiers(projet)
    assert "Permission denied" in sortie.err, sortie.err
    assert sortie.err.index("aaa.json") < sortie.err.index("1 ancien(s)"), (
        "ce qui n'a PAS eu lieu se dit avant ce qui a eu lieu")


# ---------------------------------------------------------------------------
# Frontieres NEGATIVES -- ce qu'aucun test positif ne verrait revenir
# ---------------------------------------------------------------------------

def test_les_DEUX_points_d_entree_du_terminal_avertissent(projet):
    """`EPIC5-ARB-92` : ni la sous-commande ni la bascule ne peut se taire.

    Frontiere negative. Un test positif sur `scan_calibrate_command` reste vert
    le jour ou la bascule de `scan` -- l'autre porte, celle qu'Egan emprunte
    quand sa pile ne porte qu'une mire -- perd l'avertissement. La mesure porte
    sur le SOURCE des deux fonctions, parce que c'est la seule facon de voir
    l'absence d'un appel.
    """
    import inspect

    for fonction in (cli.scan_calibrate_command,
                     cli._consigner_le_profil_de_chaine):
        source = inspect.getsource(fonction)
        assert "_traiter_la_chaine_deja_calibree" in source, (
            f"{fonction.__name__} n'avertit pas d'une chaine deja calibree : "
            "le defaut d'`EPIC11-ARB-261` est rouvert par cette porte")


def test_le_coeur_POSE_le_releve_sur_ce_qu_il_rend(projet):
    """Le releve vit dans le COEUR, pas dans une interface.

    Frontiere negative contre le retour du defaut de fond : il etait cable dans
    la TUI seule, donc la ligne de commande ne fermait rien. Un champ porte par
    `ProfilDeChaineConsigne` est ce qui garantit que les deux interfaces
    obtiennent la meme mesure sans la recalculer -- deux redactions
    divergeraient, et le symptome serait deux interfaces qui ne comptent pas les
    memes profils.
    """
    champs = scan_calibrate.ProfilDeChaineConsigne.__dataclass_fields__
    assert "autres_profils" in champs, sorted(champs)

    _poser_un_profil(projet, "aaa", CHAINE_VISEE)
    consigne = _consigne(projet, "nnn")
    assert [autre.name for autre in consigne.autres_profils] == ["aaa.json"]
