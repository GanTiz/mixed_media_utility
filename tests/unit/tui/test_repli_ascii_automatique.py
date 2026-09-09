# -*- coding: utf-8 -*-
"""Retour terrain d'Egan du 2026-09-06 -- les glyphes illisibles sous console
Windows, et le repli qu'il a demande « si possible automatique ».

> « Le symbole "Enter" ne marche pas dans un terminal standard windows. Le
> symbole devient illisible. » / « Le glyphe d'attente (lecture des frames)
> n'est pas rendu par un terminal windows natif. » / « On est sur que ce n'est
> que Windows ? Et un powershell l'accepte ? Peut-on "forcer" l'utilisation
> d'un powershell ? Si c'est plus risque que juste windows, prevoyons un
> repli, si possible automatique. »

**La table de repli n'etait pas le probleme** : `jetons.GLYPHES_ASCII`,
`ROTOR_ASCII` et `REPLIS_DE_TEXTE` couvrent les 31 points de code non-ASCII du
paquet, `⏎ -> "Entree"` compris. Ce qui manquait est en amont : rien ne
*declenchait* le repli sans que l'operateur tape `--ascii`, et rien ne
permettait de le **refuser** une fois qu'on le declencherait tout seul.

Ce banc mesure les trois livrables, et **fait varier `ascii_seul` dans les
deux sens sur des cas ou le repli change la LARGEUR** -- la regle nee de la
regression des 11 bandeaux amputes : « une garde qui ne fait varier aucun de
ses drapeaux ne mesure qu'un seul chemin ».
"""
import subprocess
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.__main__ import (
    VARIABLES_D_HOTE,
    analyser,
    diagnostic,
    diagnostic_de_la_console,
    echantillon_de_glyphes,
    main,
    mode_ascii,
    repli_ascii_conseille,
)
from mixed_media_utility.tui.explorateur import Explorateur
from mixed_media_utility.tui.manuel import lignes_de_raccourcis_du_paquet


# ---------------------------------------------------------------------------
# G2 -- l'heuristique, ses cinq branches, dans les DEUX sens
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plateforme", ["linux", "darwin", "freebsd"])
def test_hors_windows_on_ne_replie_JAMAIS(plateforme):
    """Le probleme est un probleme de police, il n'est en droit pas propre a
    Windows -- mais les polices de console usuelles de Linux et de macOS
    portent U+23CE, et les deux plaintes viennent de Windows. Replier ailleurs
    degraderait des terminaux sains pour une hypothese que rien ne soutient."""
    repli, motif = repli_ascii_conseille({"WT_SESSION": ""}, plateforme,
                                         legacy=True)
    assert repli is False
    assert plateforme in motif


def test_la_console_windows_historique_replie():
    repli, motif = repli_ascii_conseille({}, "win32", legacy=True)
    assert repli is True
    assert "legacy_windows" in motif


@pytest.mark.parametrize("environnement,attendu,indice", [
    ({"WT_SESSION": "9f2c"}, False, "WT_SESSION"),
    ({"TERM_PROGRAM": "vscode"}, False, "VS Code"),
    ({}, True, "sans signal"),
    # Volet symetrique du precedent : un `TERM_PROGRAM` d'un AUTRE hote ne
    # vaut pas signal positif. Sans lui, un test qui lirait la seule presence
    # de la variable passerait.
    ({"TERM_PROGRAM": "Apple_Terminal"}, True, "sans signal"),
    # Et une variable vide ne vaut pas presence -- c'est l'inverse exact de la
    # convention `NO_COLOR`, et les deux coexistent dans ce lanceur.
    ({"WT_SESSION": ""}, True, "sans signal"),
])
def test_les_signaux_d_hote_windows_dans_les_deux_sens(environnement, attendu,
                                                       indice):
    repli, motif = repli_ascii_conseille(environnement, "win32", legacy=False)
    assert repli is attendu, motif
    assert indice in motif


def test_sys_stdout_encoding_n_est_PAS_un_signal(racine_depot):
    """Frontiere NEGATIVE, et c'est le signal qu'il fallait ecarter.

    Depuis Python 3.6, quand la sortie est attachee a une console Windows,
    CPython ecrit en UTF-16 par `WriteConsoleW` et `sys.stdout.encoding` rend
    `utf-8` **quelle que soit la page de code**. Il ne retombe sur `cp1252`
    que si la sortie est REDIRIGEE, c'est-a-dire quand la TUI ne tourne pas.
    Il detecte la redirection, pas le probleme.

    Aucun test positif ne verrait ce signal revenir dans la decision : c'est
    exactement ce qu'une frontiere negative existe pour attraper.
    """
    source = (racine_depot / "src" / "mixed_media_utility" / "tui"
              / "__main__.py").read_text(encoding="utf-8")
    decision = source.split("def repli_ascii_conseille")[1].split(
        "def echantillon_de_glyphes")[0]
    corps = decision.split('"""')[2]
    assert "stdout" not in corps, (
        "sys.stdout.encoding est revenu dans la DECISION du repli ; il ne "
        "mesure que la redirection de la sortie")


def test_aucune_variable_d_hote_n_est_INVENTEE_par_le_depot():
    """L'arbitrage rouvert ne l'est que pour l'HOTE : on ne s'invente toujours
    aucune convention a nous."""
    for nom in VARIABLES_D_HOTE:
        assert not nom.startswith("MMU"), nom
    assert "MMU_ASCII" not in VARIABLES_D_HOTE


# ---------------------------------------------------------------------------
# G2 bis -- l'echappatoire, obligatoire, dans les DEUX sens
# ---------------------------------------------------------------------------

def test_ascii_force_le_repli_meme_quand_l_hote_dit_non():
    actif, motif = mode_ascii(analyser(["--ascii"]),
                              {"WT_SESSION": "9f2c"})
    assert actif is True and "--ascii" in motif


@pytest.mark.parametrize("option", ["--utf8", "--pas-d-ascii"])
def test_utf8_REFUSE_le_repli_meme_quand_l_hote_dit_oui(option, monkeypatch):
    """**Le test qui justifie l'existence de l'option.**

    Livrer la detection sans son echappatoire remplacerait un defaut visible
    -- des glyphes qui tombent -- par un defaut non contournable : un
    operateur dont l'hote est mal classe n'aurait aucun moyen de recuperer ses
    glyphes.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    # L'hote conseillerait le repli...
    assert repli_ascii_conseille({}, "win32", legacy=False)[0] is True
    # ... et l'option le refuse quand meme.
    actif, motif = mode_ascii(analyser([option]), {})
    assert actif is False and "--utf8" in motif


def test_les_deux_options_s_EXCLUENT():
    """Une ligne de commande qui demanderait les deux serait sans reponse ;
    argparse doit la refuser plutot que d'en privilegier une en silence."""
    with pytest.raises(SystemExit):
        analyser(["--ascii", "--utf8"])


def test_sans_option_c_est_l_hote_qui_tranche():
    options = analyser([])
    assert options.ascii_seul is False and options.pas_d_ascii is False
    assert mode_ascii(options, {"WT_SESSION": "x"}) == mode_ascii(
        options, {"WT_SESSION": "x"})
    # Deux hotes differents rendent deux verdicts differents : c'est bien
    # l'hote qui tranche et non une constante.
    assert mode_ascii(options, {}) != mode_ascii(options, {"WT_SESSION": "x"}) \
        or not sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# G1 -- l'instrument de mesure, qui est le vrai livrable pour Egan
# ---------------------------------------------------------------------------

def test_le_diagnostic_de_chemin_garde_ses_TROIS_rubriques(monkeypatch):
    """Frontiere de non-regression : `diagnostic()` n'a pas ete enrichi EN
    PLACE, et c'est deliberate -- deux bancs lisent `lignes[0]` et
    `lignes[-1]`, et glisser des lignes au milieu les ferait rougir pour une
    raison illisible."""
    monkeypatch.setenv("PYTHONPATH", "temoin")
    monkeypatch.setenv("ESCDELAY", "25")
    lignes = diagnostic().splitlines()
    assert lignes[0] == "PYTHONPATH=temoin"
    assert lignes[-1] == "ESCDELAY=25"
    assert all(l.startswith("sys.path=") for l in lignes[1:-1])


@pytest.mark.parametrize("rubrique", [
    "sys.platform=", "WT_SESSION=", "TERM_PROGRAM=", "TERM=",
    "rich.legacy_windows=", "sys.stdout.encoding=", "console.page_de_code=",
    "console.police=", "repli_ascii_conseille=", "repli_ascii_motif=",
])
def test_le_diagnostic_de_console_rend_chaque_rubrique(rubrique):
    assert any(l.startswith(rubrique)
               for l in diagnostic_de_la_console({}).splitlines()), rubrique


def test_le_diagnostic_de_console_rend_le_MOTIF_et_pas_seulement_le_verdict():
    """Un booleen nu ne se conteste pas ; un motif se lit et se contredit."""
    lignes = dict(l.split("=", 1)
                  for l in diagnostic_de_la_console({"WT_SESSION": "9f2c"}
                                                    ).splitlines()
                  if "=" in l and not l.startswith("glyphe"))
    assert lignes["repli_ascii_motif"].strip()


@pytest.mark.parametrize("caractere,role", jetons.GLYPHES_A_RISQUE)
def test_l_echantillon_imprime_chaque_glyphe_TEL_QUEL_avec_son_point_de_code(
        caractere, role):
    """C'est le seul livrable qui tranche : aucune detection ne sait ce qu'une
    police contient, un operateur qui regarde la liste le sait en une
    seconde."""
    sortie = echantillon_de_glyphes()
    assert caractere in sortie
    assert f"U+{ord(caractere):04X}" in sortie


@pytest.mark.parametrize("caractere,role", jetons.GLYPHES_A_RISQUE)
def test_chaque_glyphe_a_risque_a_un_repli_ASCII_qui_ne_perd_rien(caractere,
                                                                  role):
    """Volet symetrique de l'echantillon : montrer le probleme ne sert a rien
    si `--ascii` rendait `?` a la place."""
    replie = jetons.replier_ascii(caractere)
    assert replie.isascii(), (caractere, replie)
    assert "?" not in replie, (caractere, replie)
    assert replie.strip(), (caractere, replie)


def test_les_deux_glyphes_CONFIRMES_casses_sont_dans_l_echantillon():
    """`⏎` et le rotor : ce sont les deux que le terrain a nommes. Un
    echantillon qui les perdrait ne mesurerait pas la plainte."""
    caracteres = [c for c, _ in jetons.GLYPHES_A_RISQUE]
    assert "⏎" in caracteres
    assert "◐" in caracteres
    # Et les temoins CP437, sans lesquels on ne saurait pas distinguer « la
    # police ne couvre pas » de « la sortie n'est pas en UTF-8 ».
    assert "▓" in caracteres and "─" in caracteres


def test_le_diagnostic_sort_sans_monter_l_application(capsys):
    assert main(["--diagnostic-chemin"]) == 0
    sortie = capsys.readouterr().out
    assert sortie.startswith("PYTHONPATH=")
    assert "repli_ascii_conseille=" in sortie
    assert "⏎" in sortie


def test_le_diagnostic_repond_dans_un_PROCESSUS_NEUF(racine_depot):
    """La mesure du lanceur, pas de la fonction : c'est ce qu'Egan lancera.

    Un diagnostic qui ne repondrait qu'importe -- parce qu'il leve sur une
    console absente, par exemple -- ne servirait a rien sur sa machine.
    """
    resultat = subprocess.run(
        [sys.executable, "-m", "mixed_media_utility.tui",
         "--diagnostic-chemin"],
        cwd=racine_depot, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(racine_depot / "src"),
             "PYTHONIOENCODING": "utf-8"})
    assert resultat.returncode == 0, resultat.stderr
    assert "repli_ascii_motif=" in resultat.stdout


# ---------------------------------------------------------------------------
# MESURE -- le drapeau varie dans les DEUX sens, sur la LARGEUR
# ---------------------------------------------------------------------------

def test_le_repli_CHANGE_la_largeur_des_lignes_de_raccourcis():
    """Sans ce volet, une garde qui ne jouerait qu'`ascii_seul=False`
    mesurerait la moitie du produit et l'annoncerait verte.

    Le repli n'est pas neutre en largeur : `⏎` (1 colonne) devient `Entree`
    (6), soit **+5 colonnes** par ligne qui le porte. C'est precisement ce qui
    rend la mesure du plancher 80x24 non triviale.
    """
    lignes = lignes_de_raccourcis_du_paquet()
    porteuses = {n: l for n, l in lignes.items() if "⏎" in l}
    assert porteuses, "aucune ligne ne porte ⏎ : le banc ne mesure rien"
    elargies = 0
    for nom, ligne in porteuses.items():
        utf8 = jetons.colonnes(ligne)
        ascii_ = jetons.colonnes(jetons.replier_ascii(ligne))
        assert ascii_ != utf8 or "É" in ligne, nom
        elargies += ascii_ > utf8
    assert elargies, "le repli n'elargit aucune ligne : la mesure est vide"


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_toute_ligne_de_raccourcis_tient_dans_les_DEUX_modes(ascii_seul):
    """Les deux sens du meme drapeau, sur la contrainte que le repli tend."""
    for nom, ligne in lignes_de_raccourcis_du_paquet().items():
        rendue = jetons.replier_ascii(ligne) if ascii_seul else ligne
        assert jetons.colonnes(rendue) <= jetons.largeur_utile(), (
            nom, jetons.colonnes(rendue))
        if ascii_seul:
            assert rendue.isascii(), (nom, rendue)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_l_explorateur_se_rend_dans_les_DEUX_modes_et_tient(tmp_path,
                                                            ascii_seul):
    """L'explorateur est le composant que le RETOUR 1 touche : ses deux modes
    se mesurent ici, sur un dossier a plusieurs entrees distinguables."""
    for nom in ("alpha", "beta", "omega"):
        (tmp_path / nom).mkdir()
    (tmp_path / "un fichier.mov").write_bytes(b"")
    exp = Explorateur(tmp_path, montrer_fichiers=True)

    lignes = exp.lignes(ascii_seul=ascii_seul)
    assert lignes
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(), ligne
        if ascii_seul:
            assert ligne.isascii(), ligne
            assert "?" not in ligne, ligne


def test_l_explorateur_rend_bien_DEUX_dessins_differents_selon_le_mode(tmp_path):
    """Volet symetrique : sans lui, un explorateur qui rendrait le meme texte
    dans les deux modes passerait le test ci-dessus, et le repli serait mort
    sans que rien ne le dise."""
    for nom in ("alpha", "beta", "omega"):
        (tmp_path / nom).mkdir()
    exp = Explorateur(tmp_path)
    assert exp.lignes(ascii_seul=True) != exp.lignes(ascii_seul=False)
