"""Frontieres du crochet de session, cote LFS.

**Le defaut que ce banc ferme, et il a ete paye tous les jours.** Jusqu'au
2026-09-10, `.claude/hooks/session-start.sh` rematerialisait **un seul** media :
`tests/TEST_FILE.mp4`. Or QUATRE objets LFS descendent automatiquement dans
tout clone -- `.lfsconfig` exclut les autres --, et les trois PDF de
`tests/fixtures/scans/` (25,5 Mio, lus par quatre bancs) n'etaient pas repares.

`EPIC11-ARB-241` prescrivant le ROUGE sur un media manquant, toute session dont
le conteneur porte `filter.lfs.smudge --skip` -- ce que l'image pose elle-meme
-- demarrait avec des bancs de terrain rouges que rien ne reparait. C'est le
« bloque par LFS » qu'Egan lisait dans chaque session, et sa cause tenait en
cinq lignes.

**Pourquoi des frontieres NEGATIVES ici.** Aucun test positif ne verrait
revenir la forme fautive : un crochet qui ne repare qu'un fichier repare
quelque chose, donc il « marche ». Ce qui se mesure est ce qu'il ne fait PAS --
nommer un seul media, ou telecharger la ou une reecriture locale suffit.

**Le saut est STRUCTUREL.** `.claude/` n'est pas publie (le script de
publication l'exclut), donc ce fichier n'existe pas dans un clone du depot
public. Le saut n'est alors pas un drapeau qu'on oublie de rallumer : il n'y a
rien a mesurer. Meme famille que le saut de `test_politiques_du_depot` quand
`origin/main` est hors d'atteinte.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]
_CROCHET = _RACINE / ".claude" / "hooks" / "session-start.sh"
_LFSCONFIG = _RACINE / ".lfsconfig"


def _texte() -> str:
    if not _CROCHET.is_file():
        pytest.skip(
            "`.claude/hooks/session-start.sh` absent : ce clone ne porte pas "
            "l'outillage d'agent (le depot public l'exclut). Rien a mesurer."
        )
    return _CROCHET.read_text(encoding="utf-8")


def _bloc_lfs(texte: str) -> str:
    """Le bloc qui traite LFS, commentaires exclus -- on mesure du CODE."""
    lignes = [l for l in texte.splitlines() if not l.lstrip().startswith("#")]
    return "\n".join(lignes)


def test_le_crochet_repare_par_SONDE_et_non_par_liste_ecrite_a_la_main():
    """La reparation part de `git lfs ls-files`, pas d'un chemin en dur.

    C'est ce qui l'empeche de deriver : un media ajoute demain est couvert
    sans que personne ait pense a l'inscrire.
    """
    code = _bloc_lfs(_texte())
    assert "git lfs ls-files" in code, (
        "le crochet doit SONDER les medias suivis. Sans cette sonde, la "
        "reparation retombe sur une liste ecrite a la main, qui est "
        "exactement la forme qui a laisse trois PDF de scans en pointeur."
    )


def test_FRONTIERE_NEGATIVE_aucun_media_n_est_nomme_en_dur_dans_la_reparation():
    """Un chemin de media en dur est la signature de la regression de 2026-09-10.

    On tolere les chemins qui servent d'EXEMPLE dans un message d'aide
    (`--include="tests/**"`), jamais un chemin de fichier precis.
    """
    code = _bloc_lfs(_texte())
    medias = re.findall(r'tests/[\w./-]+\.(?:mp4|pdf|tiff|png)', code)
    assert not medias, (
        "le crochet nomme un media precis : "
        f"{sorted(set(medias))}. C'est la forme qui n'en reparait qu'un sur "
        "quatre. La sonde doit les trouver tous."
    )


def test_la_reparation_passe_par_CHECKOUT_qui_ne_coute_aucun_reseau():
    """`checkout` reecrit depuis `.git/lfs/objects` ; `pull` telecharge.

    Mesure du 2026-09-03 : 38 objets, 350 Mo repares sans un octet reseau.
    Le conteneur porte `filter.lfs.smudge --skip` au niveau SYSTEME, donc les
    objets sont deja la -- seule leur ecriture a ete sautee.
    """
    code = _bloc_lfs(_texte())
    assert "lfs checkout" in code, (
        "la reparation doit employer `git lfs checkout`, qui ne coute rien. "
        "`git lfs pull` repaie une bande passante deja depensee."
    )


def test_FRONTIERE_NEGATIVE_le_crochet_ne_TELECHARGE_pas_de_lui_meme():
    """Tirer d'office consommerait le quota a chaque conteneur neuf.

    C'est precisement ce que la revision du 2026-09-03 a supprime. Le crochet
    peut NOMMER la commande de rapatriement ; il ne doit pas la jouer.
    """
    code = _bloc_lfs(_texte())
    executions = [
        l for l in code.splitlines()
        if "lfs pull" in l and not l.lstrip().startswith(("echo", "printf"))
    ]
    assert not executions, (
        "le crochet execute un telechargement LFS : "
        f"{executions}. Il doit se borner a la reecriture locale et NOMMER "
        "le rapatriement, qui coute du quota."
    )


def test_l_exclusion_est_LUE_de_lfsconfig_et_jamais_recopiee():
    """Deux declarations, c'est une qui derive.

    L'alarme ne doit crier que sur ce qu'un clone recoit AUTOMATIQUEMENT :
    ce que `.lfsconfig` exclut est un pointeur PAR CHOIX, et crier dessus a
    chaque session apprendrait a ignorer l'alarme.
    """
    code = _bloc_lfs(_texte())
    assert "lfs.fetchexclude" in code, (
        "le crochet doit lire l'exclusion dans `.lfsconfig` a l'execution."
    )
    valeur = _LFSCONFIG.read_text(encoding="utf-8").split("fetchexclude")[-1]
    for motif in ("projects/**", "tests/fixtures/lots/**"):
        assert motif in valeur, f"{motif} devrait etre exclu par .lfsconfig"
        assert motif not in code, (
            f"le crochet RECOPIE l'exclusion `{motif}` au lieu de la lire. "
            "Une seconde declaration derive des que .lfsconfig change."
        )


def test_le_crochet_NOMME_ce_qui_reste_en_pointeur_plutot_que_de_se_taire():
    """Un echec muet est ce qui rend un pointeur incomprehensible.

    Un pointeur ne leve aucune erreur : le banc echoue bien plus loin, sur un
    message qui ne nomme ni LFS ni le fichier.
    """
    code = _bloc_lfs(_texte())
    assert "MEDIAS LFS MANQUANTS" in code, (
        "le crochet doit annoncer explicitement les medias non materialises, "
        "et nommer la consequence (des bancs de terrain rouges)."
    )
    assert '--exclude=\\"\\"' in code or '--exclude=""' in code, (
        "la commande de rapatriement suggeree doit porter son exclusion VIDE : "
        "sans elle, `.lfsconfig` gagne et la commande ne tire RIEN, en silence."
    )
