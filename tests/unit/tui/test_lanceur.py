# -*- coding: utf-8 -*-
"""Story 11.0, AC 6 -- le point d'entree, sur le patron du depot.

Les deux scripts sont **executes**, pas relus. Une assertion sur le texte du
script dirait que la bonne variable y figure ; elle ne dirait pas que le
`PYTHONPATH` de l'operateur survit -- qui est tout l'enjeu de l'AC 6.1, et le
seul point ou `bin/mmu` a une subtilite (prepend, jamais ecrase).
"""

import os
import re
import shutil
import subprocess
import sys

import pytest

#: Un chemin qui n'existe pas et ne ressemble a rien du depot : s'il ressort du
#: lanceur, c'est bien que celui-ci a preserve ce qu'on lui avait pose.
SENTINELLE = os.path.join("chemin", "pose", "par", "l", "operateur")


def _lancer(racine_depot, commande: list[str]) -> str:
    environnement = dict(os.environ, PYTHONPATH=SENTINELLE)
    resultat = subprocess.run(commande, cwd=racine_depot, env=environnement,
                              capture_output=True, text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout


def _lignes_chemin(sortie: str) -> tuple[str, list[str]]:
    pythonpath = ""
    chemins = []
    for ligne in sortie.splitlines():
        if ligne.startswith("PYTHONPATH="):
            pythonpath = ligne.partition("=")[2]
        elif ligne.startswith("sys.path="):
            chemins.append(ligne.partition("=")[2])
    return pythonpath, chemins


@pytest.mark.parametrize("nom", ["mmu-tui", "mmu-tui.cmd"])
def test_les_deux_lanceurs_jumeaux_existent(racine_depot, nom):
    """AC 6.1 : deux scripts, parce que le depot n'a pas de `console_scripts`."""
    assert (racine_depot / "bin" / nom).is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="le .cmd est le lanceur Windows")
def test_le_lanceur_cmd_prepose_src_et_preserve_le_pythonpath(racine_depot):
    """AC 6.1 : `src` en tete, la sentinelle toujours la, et derriere."""
    sortie = _lancer(racine_depot, ["cmd", "/c", r"bin\mmu-tui.cmd",
                                    "--diagnostic-chemin"])
    pythonpath, chemins = _lignes_chemin(sortie)
    morceaux = pythonpath.split(os.pathsep)
    assert morceaux[0].endswith(os.sep + "src")
    assert SENTINELLE in morceaux
    assert morceaux.index(SENTINELLE) > 0, (
        f"la sentinelle doit survivre DERRIERE src, vu : {morceaux}")
    # Et l'interpreteur a bien vu ce chemin : le lanceur ne se contente pas de
    # poser une variable que Python ignorerait.
    assert any(c.endswith(os.sep + "src") for c in chemins), chemins


@pytest.mark.skipif(shutil.which("bash") is None, reason="pas de bash ici")
def test_le_lanceur_shell_prepose_src_et_preserve_le_pythonpath(
        racine_depot, tmp_path):
    """AC 6.1, jumeau POSIX -- mesure du script, avec un python postiche.

    **Pourquoi un postiche plutot que le vrai interpreteur.** Sous Git Bash sur
    Windows, le script calcule un chemin POSIX (`/d/...`) et joint avec `:` :
    c'est correct pour un hote POSIX, et illisible pour le `python.exe` de
    l'hote, qui echoue sur un `ModuleNotFoundError` sans rapport avec l'AC.
    Mesure faite au developpement de la story. Le postiche isole ce que l'AC
    demande -- la composition du `PYTHONPATH` par le script -- de ce qu'elle ne
    demande pas : l'interoperabilite de deux conventions de chemins.
    """
    faux = tmp_path / "python3"
    faux.write_text('#!/usr/bin/env bash\necho "PYTHONPATH=$PYTHONPATH"\n',
                    encoding="utf-8", newline="\n")
    faux.chmod(0o755)
    environnement = dict(os.environ, PYTHONPATH=SENTINELLE,
                         PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    resultat = subprocess.run(["bash", "bin/mmu-tui", "--diagnostic-chemin"],
                              cwd=racine_depot, env=environnement,
                              capture_output=True, text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    pythonpath, _ = _lignes_chemin(resultat.stdout)
    # Le script `sh` joint avec `:`, y compris sous Git Bash ou l'hote
    # utiliserait `;`. On lit donc avec le separateur du script.
    morceaux = pythonpath.split(":")
    assert morceaux[0].endswith("/src"), morceaux
    assert any(SENTINELLE in m for m in morceaux[1:]), morceaux


def test_le_lanceur_appelle_le_module_de_la_tui_et_pas_celui_de_la_cli(racine_depot):
    """AC 6.1 et AC 7 : le jumeau vise `...tui`, la CLI garde le sien.

    Une copie de `bin/mmu` dont on aurait oublie la derniere ligne lancerait la
    CLI sous le nom de la TUI -- panne silencieuse, et le diagnostic de chemin
    ne la verrait pas.
    """
    for nom in ("mmu-tui", "mmu-tui.cmd"):
        source = (racine_depot / "bin" / nom).read_text(encoding="utf-8")
        assert "mixed_media_utility.tui" in source
        assert "mixed_media_utility.cli" not in source
    for nom in ("mmu", "mmu.cmd"):
        source = (racine_depot / "bin" / nom).read_text(encoding="utf-8")
        assert "mixed_media_utility.cli" in source
        assert "mixed_media_utility.tui" not in source


# --------------------------------------------------------------------------
# AC 6.2 et 6.3 -- la dependance, declaree puis verifiee
# --------------------------------------------------------------------------

def _contrainte(racine_depot, paquet: str) -> str:
    motif = re.compile(r"^" + re.escape(paquet) + r"(?![A-Za-z0-9._-])")
    lignes = [l.strip() for l
              in (racine_depot / "requirements.txt").read_text(
                  encoding="utf-8").splitlines()
              if l.strip() and not l.strip().startswith("#")]
    retenues = [l for l in lignes if motif.match(l)]
    assert len(retenues) == 1, (
        f"{paquet} doit apparaitre exactement une fois, trouve {retenues!r}")
    return retenues[0]


def test_textual_est_epingle_par_serie_majeure(racine_depot):
    """AC 6.2, sur le modele des autres lignes du fichier."""
    assert _contrainte(racine_depot, "textual") == "textual>=8.2,<9"


def test_la_serie_installee_est_celle_qui_est_epinglee():
    """AC 6.3 : la version se compare en TUPLE d'entiers, jamais en chaine.

    « 10.0 » < « 2 » est vrai entre chaines et faux entre versions ; c'est le
    piege que `tests/unit/gui/test_environnement.py` documente deja.
    """
    import textual

    version = tuple(int(p) for p in textual.__version__.split(".")[:2])
    assert (8, 2) <= version < (9, 0), (
        f"textual doit etre en serie 8, trouve {textual.__version__}")


def test_le_paquet_de_la_tui_s_importe_et_expose_sa_coque():
    """AC 6.3, second volet : le module vise par les lanceurs existe vraiment."""
    from mixed_media_utility.tui import CoqueTui
    from mixed_media_utility.tui.__main__ import main

    assert callable(main)
    assert CoqueTui is not None


def _escdelay(sortie: str) -> str:
    """La valeur d'`ESCDELAY` telle que l'interpreteur l'a vue."""
    for ligne in sortie.splitlines():
        if ligne.startswith("ESCDELAY="):
            return ligne.partition("=")[2]
    raise AssertionError(
        "le diagnostic ne rend pas ESCDELAY ; sans lui on ne peut mesurer "
        f"le reglage qu'en relisant le script. Sortie : {sortie!r}")


def _lancer_avec(racine_depot, commande: list[str], **variables) -> str:
    """Comme `_lancer`, mais en posant des variables d'environnement precises.

    Une valeur `None` **retire** la variable : c'est ce qui distingue « le
    lanceur pose sa valeur par defaut » de « le lanceur ecrase celle de
    l'operateur », et les deux cas doivent etre mesures.
    """
    environnement = dict(os.environ, PYTHONPATH=SENTINELLE)
    for nom, valeur in variables.items():
        if valeur is None:
            environnement.pop(nom, None)
        else:
            environnement[nom] = valeur
    resultat = subprocess.run(commande, cwd=racine_depot, env=environnement,
                              capture_output=True, text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout


def _postiche(tmp_path):
    """Un faux `python3` qui rend l'environnement que le script lui a pose.

    Meme raison que pour l'AC 6.1 plus haut : sous Git Bash sur Windows, le
    script POSIX joint les chemins avec `:` et le `python.exe` de l'hote ne sait
    pas les lire. Le postiche isole ce qu'on mesure -- le reglage pose par le
    script -- de ce qu'on ne mesure pas : l'interoperabilite des conventions de
    chemins.
    """
    faux = tmp_path / "python3"
    faux.write_text('#!/usr/bin/env bash\necho "ESCDELAY=$ESCDELAY"\n',
                    encoding="utf-8", newline="\n")
    faux.chmod(0o755)
    return faux


def _lancer_pour_escdelay(racine_depot, tmp_path, lanceur: str,
                          escdelay: str | None) -> str:
    """Execute un lanceur et rend l'`ESCDELAY` vu en aval.

    `escdelay=None` **retire** la variable : c'est ce qui distingue « le lanceur
    pose sa valeur par defaut » de « le lanceur ecrase celle de l'operateur »,
    et les deux cas doivent etre mesures separement.
    """
    environnement = dict(os.environ, PYTHONPATH=SENTINELLE)
    if escdelay is None:
        environnement.pop("ESCDELAY", None)
    else:
        environnement["ESCDELAY"] = escdelay

    if lanceur == "cmd":
        commande = ["cmd", "/c", r"bin\mmu-tui.cmd", "--diagnostic-chemin"]
    else:
        environnement["PATH"] = f"{_postiche(tmp_path).parent}{os.pathsep}" \
                                f"{os.environ['PATH']}"
        commande = ["bash", "bin/mmu-tui", "--diagnostic-chemin"]

    resultat = subprocess.run(commande, cwd=racine_depot, env=environnement,
                              capture_output=True, text=True, timeout=120)
    assert resultat.returncode == 0, resultat.stderr
    for ligne in resultat.stdout.splitlines():
        if ligne.startswith("ESCDELAY="):
            return ligne.partition("=")[2]
    raise AssertionError(
        "rien ne rend ESCDELAY en aval du lanceur ; sans cela le reglage ne se "
        f"mesurerait qu'en relisant le script. Sortie : {resultat.stdout!r}")


#: Les deux lanceurs jumeaux, chacun sous sa condition de plateforme.
_LANCEURS = [
    pytest.param("cmd", id="cmd",
                 marks=pytest.mark.skipif(sys.platform != "win32",
                                          reason="le .cmd est le lanceur Windows")),
    pytest.param("bash", id="bash",
                 marks=pytest.mark.skipif(shutil.which("bash") is None,
                                          reason="pas de bash ici")),
]


@pytest.mark.parametrize("lanceur", _LANCEURS)
def test_le_lanceur_raccourcit_le_delai_d_echappement(racine_depot, tmp_path,
                                                      lanceur):
    """Vague 1 bis : `Echap` ne doit pas couter 100 ms de latence.

    `Echap` emet le meme octet que le prefixe de toute sequence d'echappement.
    `ESCDELAY` est donc a la fois **la latence de `Echap`** et la fenetre
    pendant laquelle la touche suivante lui est collee -- ce qu'Egan a observe
    le 2026-08-28 comme un « lag » et comme des touches devenues inertes.

    Mesure par **execution**, jamais par relecture : une ligne presente dans le
    script et un reglage qui atteint l'aval ne sont pas la meme chose.
    """
    assert _lancer_pour_escdelay(racine_depot, tmp_path, lanceur, None) == "25"


@pytest.mark.parametrize("lanceur", _LANCEURS)
def test_un_escdelay_pose_par_l_operateur_survit_au_lanceur(racine_depot,
                                                            tmp_path, lanceur):
    """Volet symetrique, et il n'est pas decoratif.

    Sur un terminal distant ou lent, les caracteres d'une sequence n'arrivent
    pas dans la meme lecture et la valeur haute est la bonne : ecraser le
    reglage de l'operateur casserait ses fleches. La valeur de test est
    **differente du defaut de textual (100) et du notre (25)**, sans quoi un
    lanceur qui ecraserait tout passerait par coincidence.
    """
    assert _lancer_pour_escdelay(racine_depot, tmp_path, lanceur, "180") == "180"
