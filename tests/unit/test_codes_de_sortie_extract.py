"""Story 11.4, lot B3 -- la table exception -> code retour vit dans le coeur.

`EPIC11-ARB-75`, et le fait F4 de la story : `cli.py` etait la **seule** source
de verite des codes `0/1/2/3/130` d'`extract`. Or `tui/palier_projet.py` pose,
verbatim, « Ce module appelle io/, jamais cli.py », et l'AC 7 de la 11.4 exige
un code retour **identique** depuis la TUI. La table descend donc dans
`extraction.py` et se lit des deux cotes.

Ce banc mesure trois choses distinctes :

1. la table elle-meme, **exception par exception** -- douze correspondances,
   jamais une seule ;
2. son **ordre**, qui est semantique : la recherche rend la premiere entree
   qui correspond, ce qui est exactement ce que faisait la pile d'`except` ;
3. la frontiere : `cli.py` ne porte plus de seconde table, et la commande
   `extract` rend toujours les memes codes.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (
    cli,
    extraction,
    ffmpeg_utils,
    source_confirmation,
    video_metadata,
)
from mixed_media_utility.frame_selection import FrameSelectionError
from mixed_media_utility.io.extraction_manifest import (
    ExtractionPersistenceError,
    LotStateConflictError,
)
from mixed_media_utility.io.naming import NamingError

CHEMIN_CLI = REPO_ROOT / "src" / "mixed_media_utility" / "cli.py"

#: Les douze correspondances relevees dans `cli.py:3488-3535` au commit
#: `2da4205`, **dans l'ordre des `except`**. Elles ne sont pas devinees : la
#: pile d'origine posait `ExtractionInputError`, `NamingError`,
#: `FrameSelectionError`, `SourceReportError`, `FfmpegNotFoundError`,
#: `FfprobeNotFoundError`, `FfprobeError`, `FrameExtractionError`,
#: `ExtractionPersistenceError`, `ValidationError`, `KeyboardInterrupt`, puis
#: `OSError` en filet.
#:
#: Trois codes distincts y cohabitent (1, 2, 130) : une table dont toutes les
#: lignes rendraient la meme valeur ne verrait pas un appariement decale.
TABLE_ATTENDUE: tuple[tuple[type[BaseException], int], ...] = (
    (extraction.ExtractionInputError, 1),
    (NamingError, 1),
    (FrameSelectionError, 1),
    (source_confirmation.SourceReportError, 1),
    (ffmpeg_utils.FfmpegNotFoundError, 2),
    (video_metadata.FfprobeNotFoundError, 2),
    (video_metadata.FfprobeError, 1),
    (ffmpeg_utils.FrameExtractionError, 1),
    (ExtractionPersistenceError, 1),
    (ValidationError, 1),
    (KeyboardInterrupt, 130),
    (OSError, 1),
)


def _instance(classe: type[BaseException]) -> BaseException:
    """Fabriquer une instance de chaque classe de la table.

    `ValidationError` de jsonschema n'accepte pas la construction nue de la
    meme facon que les `RuntimeError` du depot : le message est passe en
    premier argument, ce qui suffit ici.
    """
    return classe("panne fabriquee pour la mesure")


@pytest.mark.parametrize("classe, attendu", TABLE_ATTENDUE,
                         ids=[c.__name__ for c, _ in TABLE_ATTENDUE])
def test_chaque_exception_de_la_table_rend_son_code(classe, attendu):
    """AC 7.3 : les douze correspondances, une par une."""
    assert extraction.code_de_sortie(_instance(classe)) == attendu


def test_la_table_du_coeur_est_exactement_celle_de_la_pile_d_except():
    """L'ordre est semantique : il est mesure, pas seulement le contenu."""
    assert extraction.CODES_DE_SORTIE == TABLE_ATTENDUE


def test_la_recherche_rend_la_PREMIERE_entree_qui_correspond():
    """Volet d'ordre : une exception a deux titres suit la pile, pas le hasard.

    `FfmpegNotFoundError` (code 2) est la cinquieme entree, `FfprobeError`
    (code 1) la septieme. Une classe qui herite des deux doit rendre **2**,
    comme le faisait la pile d'`except` : le premier `except` qui attrape
    gagne. Une recherche qui parcourrait la table dans un autre ordre -- ou un
    dictionnaire, dont l'ordre ne dit rien -- rendrait 1.
    """
    class PanneDouble(ffmpeg_utils.FfmpegNotFoundError,
                      video_metadata.FfprobeError):
        pass

    assert extraction.code_de_sortie(PanneDouble("les deux a la fois")) == 2


def test_une_exception_absente_de_la_table_ne_recoit_aucun_code():
    """Ce qui n'est pas dans la table remonte : la CLI ne l'avale pas.

    `except Exception` sans ce garde-fou transformerait n'importe quel bug en
    « Erreur: ... » avec le code 1, ce que la pile d'`except` nommee ne faisait
    pas.
    """
    class PanneInconnue(Exception):
        pass

    assert extraction.code_de_sortie(PanneInconnue("bug")) is None


def test_un_sous_type_d_entree_de_la_table_recoit_le_code_de_son_parent():
    """La pile d'`except` attrapait les sous-classes ; la table aussi.

    La cible est ici un sous-type de la **neuvieme** entree, jamais de la
    premiere : une recherche qui rendrait toujours la premiere ligne passerait
    sur `ExtractionInputError` et tomberait ici.
    """
    class PersistanceCassee(ExtractionPersistenceError):
        pass

    assert extraction.code_de_sortie(PersistanceCassee("disque")) == 1


def test_le_refus_d_etat_de_lot_du_coeur_rend_bien_le_code_1():
    """AC 7.5 : le refus que la TUI doit rendre tel quel a un code, et c'est 1.

    `LotStateConflictError` n'a jamais eu d'entree a elle dans la pile
    d'`except`: elle derive d'`ExtractionPersistenceError`, et c'est cette
    entree qui l'attrapait. Le test le mesure sur le **vrai** producteur, pas
    sur une sous-classe fabriquee -- une table qui listerait les classes par
    egalite stricte plutot que par `isinstance` laisserait ce refus remonter en
    trace Python devant l'operateur.
    """
    assert issubclass(LotStateConflictError, ExtractionPersistenceError)
    assert extraction.code_de_sortie(
        LotStateConflictError("lot deja passe en pdf")) == 1


def test_les_codes_nommes_valent_ce_que_la_cli_rendait():
    """Les cinq codes d'`extract`, en constantes, avec leurs valeurs d'origine."""
    assert extraction.CODE_SUCCES == 0
    assert extraction.CODE_ERREUR == 1
    assert extraction.CODE_PREREQUIS_ABSENT == 2
    assert extraction.CODE_REFUS == 3
    assert extraction.CODE_INTERRUPTION == 130


# --------------------------------------------------------------------------
# La CLI se comporte a l'identique
# --------------------------------------------------------------------------


@pytest.fixture()
def rush(tmp_path: Path) -> Path:
    chemin = tmp_path / "rush-001.mov"
    chemin.write_bytes(b"fake source")
    return chemin


def _lancer_extract(tmp_path: Path, rush: Path) -> int:
    return cli.main(["extract", "--project", str(tmp_path / "proj"),
                     "--video", str(rush), "--fps", "4", "--yes"])


@pytest.mark.parametrize("classe, attendu", TABLE_ATTENDUE,
                         ids=[c.__name__ for c, _ in TABLE_ATTENDUE])
def test_la_commande_extract_rend_le_code_de_la_table(
    monkeypatch, tmp_path, rush, capsys, classe, attendu
):
    """AC 10 : `mmu extract` rend les memes codes qu'au `baseline_commit`.

    La panne est injectee dans `run_extraction`, c'est-a-dire exactement la ou
    la pile d'`except` la recevait.
    """
    def refuser(**_kwargs):
        raise _instance(classe)

    monkeypatch.setattr(extraction, "run_extraction", refuser)
    assert _lancer_extract(tmp_path, rush) == attendu


def test_l_interruption_clavier_garde_son_message_et_n_a_pas_de_prefixe_erreur(
    monkeypatch, tmp_path, rush, capsys
):
    """`Ctrl+C` : code 130, message propre, aucun `Erreur:` et aucune trace."""
    def refuser(**_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(extraction, "run_extraction", refuser)
    assert _lancer_extract(tmp_path, rush) == 130
    sortie = capsys.readouterr()
    assert "Interruption clavier: extraction arretee." in sortie.out
    assert "Aucun lot n'a ete declare, le manifest est inchange." in sortie.out
    assert "Erreur:" not in sortie.err


def test_l_erreur_disque_garde_son_message_reformule(
    monkeypatch, tmp_path, rush, capsys
):
    """Le filet `OSError` reformule la panne ; ce texte ne bouge pas non plus.

    C'est la seule entree de la table dont l'appelant ne rend pas l'exception
    telle quelle : le distinguer est ce qui rend l'ordre de la table
    observable.
    """
    def refuser(**_kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(extraction, "run_extraction", refuser)
    assert _lancer_extract(tmp_path, rush) == 1
    erreur = capsys.readouterr().err
    assert ("Erreur: Erreur d'acces disque pendant l'extraction: "
            "No space left on device. Verifier l'espace disponible et les "
            "droits d'ecriture sur le dossier projet.") in erreur


def test_une_panne_hors_table_remonte_au_lieu_d_etre_transformee_en_code(
    monkeypatch, tmp_path, rush
):
    """Volet symetrique de la frontiere : la CLI n'attrape pas tout.

    Sans ce test, remplacer la pile d'`except` par un `except Exception`
    passerait inapercu -- et un bug de programmation sortirait deguise en
    refus metier avec le code 1.
    """
    class PanneInconnue(Exception):
        pass

    def refuser(**_kwargs):
        raise PanneInconnue("bug de programmation")

    monkeypatch.setattr(extraction, "run_extraction", refuser)
    with pytest.raises(PanneInconnue):
        _lancer_extract(tmp_path, rush)


# --------------------------------------------------------------------------
# Frontiere : plus de seconde table dans `cli.py`
# --------------------------------------------------------------------------


def _corps_de_extract_command() -> ast.FunctionDef:
    arbre = ast.parse(CHEMIN_CLI.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "extract_command":
            return noeud
    raise AssertionError("extract_command introuvable dans cli.py")


def test_extract_command_ne_porte_plus_aucun_code_de_sortie_litteral():
    """`EPIC11-ARB-75` : une seule table vraie, celle du coeur.

    La mesure est un comptage a zero sur les litteraux entiers de la fonction :
    tant qu'un `return 1` y subsiste, `cli.py` porte une seconde table, et deux
    tables vraies au meme moment divergent sans que rien ne rougisse.
    """
    litteraux = [
        noeud.value for noeud in ast.walk(_corps_de_extract_command())
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, int) and not isinstance(noeud.value, bool)
    ]
    assert litteraux == [], (
        "codes de sortie ecrits en dur dans extract_command : "
        f"{litteraux}. Ils se lisent dans extraction.CODES_DE_SORTIE.")


def test_extract_command_lit_bien_la_table_du_coeur():
    """Volet symetrique : l'absence de litteraux ne suffit pas.

    Une fonction vide passerait le test ci-dessus. Celle-ci exige que les noms
    du coeur y soient reellement cites.
    """
    noms = {noeud.attr for noeud in ast.walk(_corps_de_extract_command())
            if isinstance(noeud, ast.Attribute)}
    assert "correspondance_de_sortie" in noms or "code_de_sortie" in noms
    assert {"CODE_SUCCES", "CODE_ERREUR", "CODE_REFUS",
            "CODE_INTERRUPTION"} <= noms
