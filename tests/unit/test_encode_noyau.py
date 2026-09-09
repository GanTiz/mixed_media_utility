# -*- coding: utf-8 -*-
"""Story 11.8, **lot B1** -- le point d'entree de coeur d'`encode` (AC 2.1, 2.2, 2.4).

Trois mesures, et elles ne disent pas la meme chose :

* **AC 2.2, le dossier d'identite** : la sequence a ete DEPLACEE, pas reecrite.
  Vingt-cinq invocations reelles de `cli.main` qui encodent pour de vrai, jouees
  ici puis comparees au releve fait AVANT le deplacement. L'ensemble des
  scenarios qui divergent doit etre **vide** ;
* **AC 2.1, la forme du point d'entree** : parametres nommes, aucun objet `args`,
  aucun code de retour entier, rappels optionnels, et un module de coeur
  atteignable **sans importer `cli`** -- ce dernier point est la raison d'etre du
  deplacement, et il se mesure par un import reel plutot que par lecture de
  source ;
* **AC 2.4, l'ensemble EXACT des mots-cles** transmis au coeur, mesure dans les
  **deux sens** : si un mot-cle apparait comme s'il disparait. Meme geste que le
  lot H de la 11.6 (`MOTS_CLES_TRANSMIS_AU_COEUR` de
  `tests/unit/tui/test_frontieres_et_grille_scan_temps_2.py`), et c'est elle qui
  rendra reversible le retrait du nom de master (`EPIC11-ARB-141`, AC 6.4).

**Regle des fabriques du `CLAUDE.md`**, appliquee la ou une boucle compte : les
residus balayes sont **trois**, la cible **au milieu** (un mutant `continue` ->
`break` sur cette boucle ne se demasque pas autrement) ; la table des codes de
sortie est parcourue **entierement**, avec son temoin de cardinal.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
import subprocess
import signal
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    cli,
    codec_profiles,
    encode as encode_module,
    encode_master,
    video_metadata,
)
from mixed_media_utility.io import project_layout  # noqa: E402

import outils_identite_encode as identite  # noqa: E402
import outils_identite_scan as socle  # noqa: E402

from test_encode_command import LOT, load_manifest_dict, scanned_project  # noqa: E402

MODULE_DE_COEUR = REPO_ROOT / "src" / "mixed_media_utility" / "encode_master.py"

#: L'etat de la branche **juste avant** le deplacement du corps
#: d'`encode_command`. Contre lui, l'ensemble des divergents doit rester VIDE
#: pour toujours : c'est la mesure du deplacement lui-meme, et c'est elle qui
#: rougira si un lot suivant reecrit au lieu de deplacer.
#:
#: **La reference a ete REPRISE le 2026-09-03, et le motif importe plus que le
#: commit.** Elle sortait de `bad2f294`, l'arbre d'ou le lot B1 est parti. Mais
#: le lot B0 a ete developpe **en parallele**, dans un autre worktree, et il
#: change deliberement deux observables de `mmu encode` : la ligne d'eau des
#: masters apparait desormais au manifeste a la CONSOMMATION (douze scenarios),
#: et l'aide du parser gagne `--nouvelle-version`, que deux messages d'erreur
#: d'argparse recopient (deux scenarios). Quatorze scenarios divergeaient donc
#: **sans que le deplacement y soit pour rien**.
#:
#: Garder la vieille reference aurait laisse deux issues, toutes deux mauvaises :
#: une liste de tolerances -- qui detruit la propriete, puisque « l'ensemble des
#: divergents est VIDE » ne se mesure plus des qu'on en excepte --, ou un rouge
#: permanent qu'on apprend a ignorer. La reference est donc **rejouee sur l'arbre
#: de B0 seul** (`cf0e6f4f` = `bad2f294` + B0, sans une ligne du deplacement),
#: avec le meme outil et le meme materiau. Elle mesure alors exactement ce
#: qu'elle doit mesurer : le DEPLACEMENT, et rien d'autre.
#:
#: **Elle a ete REPRISE UNE SECONDE FOIS le 2026-09-07, pour le meme motif et
#: par le meme geste** -- et c'est le motif, pas le commit, qu'il faut garder.
#: Le lot F (`3ff23d6f5`) ajoute un maillon `setparams` a la chaine de filtres
#: de `mmu encode` : sous FFmpeg 8, `-color_primaries` et `-color_trc`
#: n'atteignent plus l'encodeur, et seule la propriete posee sur la FRAME tague
#: encore le master. C'est un changement **delibere** d'observable, etranger au
#: deplacement, et il mord par deux chemins distincts, mesures et non deduits :
#:
#: * `filter_chain` figure verbatim dans la « Description d'encodage » que
#:   `mmu encode` imprime -- **onze** scenarios (`01`, `03`, `10` a `15`, `29`,
#:   `40`, `42`) ;
#: * les masters **ProRes** changent de condensat. Le maillon ne convertit
#:   aucun pixel, mais il tague l'en-tete de frame : 48 frames x 3 champs, tous
#:   de `2` (UNSPECIFIED) a `1` (BT709), taille du fichier inchangee. **Dix**
#:   scenarios -- les neuf qui ecrivent du ProRes, plus `02`, qui n'encode rien
#:   et relit celui que `01` vient d'ecrire dans le meme projet. `12` (dnxhr)
#:   et `13` (h264) restent **bit a bit identiques**, et zero champ `ffprobe`
#:   bouge nulle part : l'atome `colr` du conteneur etait deja juste, ce qui est
#:   precisement pourquoi aucune garde du depot ne pouvait voir ce defaut.
#:
#: Douze scenarios sur vingt-cinq divergeaient donc **sans que le deplacement y
#: soit pour rien**, et les deux issues ecartees en 2026-09-03 le restent pour
#: les memes raisons. La reference est donc rejouee sur **`cf0e6f4f` plus ce
#: SEUL maillon** -- ni la sonde de version de `3ff23d6f5`, ni le nom du fichier
#: d'attente, ni ses bancs --, sur les entrees octet pour octet identiques aux
#: precedentes.
#:
#: **Ce qui rend cette reprise relisible, et qui manquait a la premiere : le
#: controle.** `cf0e6f4f` NU a d'abord ete rejoue avec le meme instrument et a
#: rendu l'ancien fichier **a l'octet** (`md5` egal). Sans lui, on ne saurait
#: pas si ce qui change dans la nouvelle reference vient du maillon ou de la
#: machine -- et une reference dont on ne sait pas cela ne mesure plus rien.
#: Aucun temoin chiffre du banc n'a bouge, ce qui est le second controle : 25
#: invocations, `{0: 11, 1: 11, 2: 2, 3: 1}`, 12 masters sondes, et les cinq
#: cardinaux de `TRADUCTIONS_DU_VOCABULAIRE` (240 / 25 / 25 / 2 / 2) inchanges.
REFERENCE_AVANT_DEPLACEMENT = (
    REPO_ROOT / "tests" / "fixtures"
    / "identite-encode-b0-cf0e6f4f-setparams-3ff23d6f5.json"
)

#: Le commit d'ou sort la reference. Nomme ici parce qu'un nom de fichier ne se
#: relit pas dans un message d'echec.
COMMIT_AVANT_DEPLACEMENT = (
    "cf0e6f4f (bad2f294 + lot B0) + le maillon setparams de 3ff23d6f5")

#: Le cardinal du dossier. Temoin a part, et il n'est pas decoratif : les
#: mesures qui suivent comparent deux dossiers, et **deux dossiers vides sont
#: egaux**. Un releve qui cesserait de jouer ne se verrait nulle part ailleurs.
INVOCATIONS_ATTENDUES = 25

#: Les codes de sortie que le dossier atteint reellement, avec leur cardinal.
#: Ecrits ici plutot que derives du releve : derives, ils diraient seulement
#: « le dossier joue ce qu'il joue », ce qui n'est pas une mesure. Le `130` et
#: le `143` n'y sont pas, et le motif est ecrit dans `outils_identite_encode`.
CARDINAL_PAR_CODE_DE_SORTIE = {0: 11, 1: 11, 2: 2, 3: 1}

#: Le nombre de masters que le dossier laisse derriere lui, tous sondes par
#: `ffprobe`. **Douze et non onze**, alors que onze scenarios seulement rendent
#: `0`, et l'ecart est lui-meme une mesure : `02-relance-master-deja-la` refuse
#: (`1`) dans le projet ou `01-nominal` vient d'ecrire, et le master de la passe
#: precedente **reste la, intact**. Un refus qui l'aurait detruit ferait tomber
#: ce compte a onze.
MASTERS_SONDES = 12


# ===========================================================================
# AC 2.2 -- le dossier d'identite
# ===========================================================================

def _construire_le_dossier(tmp_path_factory) -> dict:
    racine = tmp_path_factory.mktemp("identite-encode")
    entrees = racine / "entrees"
    identite.fabriquer(entrees)
    return identite.collecter(entrees, racine / "travail")


@pytest.fixture(scope="session")
def dossier_d_identite(tmp_path_factory) -> dict:
    """Le releve joue sous le `src/` d'AUJOURD'HUI, **une fois par course**.

    Portee session **et partagee entre les workers**, et ce n'est pas une
    optimisation de confort : c'est une correction de defaut, mesuree le
    2026-09-03. En portee module sous `-n 4`, chaque worker qui recoit l'un de
    ces tests construit **son propre** dossier -- quatre courses de vingt-cinq
    encodages reels en parallele. Le setup est passe de 93 s a plus de 300 s,
    c'est-a-dire au-dela du plafond PAR TEST de `scripts/mesure/mesure.py`, et
    `pytest-timeout` a tue trois workers : `node down: Not properly terminated`,
    trois tests rouges dont le message ne nommait ni le plafond ni la cause.

    Le partage suit l'idiome de `pytest-xdist` : le premier worker qui prend le
    verrou construit et publie, les autres attendent son fichier. `filelock`
    n'etant pas une dependance du depot, le verrou est un `O_CREAT | O_EXCL`,
    qui est atomique sur tout systeme de fichiers local -- et la publication est
    un `os.replace`, pour qu'aucun lecteur ne puisse voir un JSON tronque.

    **Hors xdist, aucun partage n'a lieu et c'est voulu** : le dossier partage
    vivrait alors dans `pytest-of-<user>/`, qui **survit d'une course a
    l'autre**, et la course suivante comparerait un releve perime -- exactement
    le faux vert que ce dossier existe pour ecarter.
    """
    if os.environ.get("PYTEST_XDIST_WORKER") is None:
        return _construire_le_dossier(tmp_path_factory)

    partage = tmp_path_factory.getbasetemp().parent
    publie = partage / "dossier-identite-encode.json"
    verrou = partage / "dossier-identite-encode.verrou"
    try:
        descripteur = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        limite = time.monotonic() + 600.0
        while time.monotonic() < limite:
            if publie.is_file():
                return json.loads(publie.read_text(encoding="utf-8"))
            time.sleep(0.5)
        raise AssertionError(
            "le worker qui construit le dossier d'identite n'a rien publie en "
            f"600 s ({publie}) : lire son journal plutot que relancer.")
    os.close(descripteur)
    dossier = _construire_le_dossier(tmp_path_factory)
    provisoire = partage / "dossier-identite-encode.partiel"
    provisoire.write_text(json.dumps(dossier), encoding="utf-8")
    os.replace(provisoire, publie)
    return dossier


#: Le vocabulaire de la story 11.14, applique a la reference **par
#: traduction** et non par regeneration.
#:
#: **La reference n'est pas un fichier d'or.** C'est le releve joue sous le
#: `src/` de `cf0e6f4f`, ou les dossiers s'appelaient `frames/` et
#: `output-frames/` et ou les libelles disaient « dossier ». La rejouer
#: rendrait exactement les memes octets -- ce commit ne change pas --, donc
#: « regenerer » serait un geste vide qui detruirait au passage la seule chose
#: que ce dossier mesure : le DEPLACEMENT du corps d'`encode_command`. Ce qu'il
#: faut, c'est rendre le releve d'hier dans les mots d'aujourd'hui. Geste deja
#: pose pour `EPIC11-ARB-171` (le mot `planches` d'un nom de tirage) et repris
#: du lot C de cette meme story (`test_identite_du_scan.py`).
#:
#: **Chaque ligne porte son cardinal EXACT**, et il est confronte au compte
#: brut du litteral dans le fichier : une regle morte et une regle deux fois
#: trop large se compensent dans un total, jamais dans cinq comptes separes.
#:
#: Les trois premieres sont des SEGMENTS DE CHEMIN, les deux dernieres des
#: LIBELLES -- et la distinction n'est pas cosmetique : un segment se traduit
#: sur les cles autant que sur les valeurs (une cle de l'arbre EST un chemin),
#: un libelle ne vit que dans une valeur. La cle de manifeste
#: `output_frames_dir`, elle, n'est traduite par AUCUNE des cinq
#: (`EPIC11-ARB-221`, regime « surfaces seules ») : son souligne la met hors
#: d'atteinte des motifs a tiret, et c'est mesure par
#: `test_la_traduction_LAISSE_VIVRE_la_cle_de_manifeste`.
#:
#: (nom, motif structurel, motif dans le TEXTE brut, remplacement,
#:  porte-t-elle sur les cles ?, cardinal exact, exemple AVANT, exemple APRES)
TRADUCTIONS_DU_VOCABULAIRE = (
    ("output-frames", r"(?<![\w-])output-frames(?![\w-])",
     r"(?<![\w-])output-frames(?![\w-])", "frames-scannees",
     True, 240,
     "projet/output-frames/lot-a/scan_f.tiff",
     "projet/frames-scannees/lot-a/scan_f.tiff"),
    ("frames/", r"(?<![\w-])frames/", r"(?<![\w-])frames/",
     "extract-frames/", True, 25,
     "frames/rush-encode_5", "extract-frames/rush-encode_5"),
    ("frames (dossier NU)", r"\Aframes\Z", r'"frames"',
     "extract-frames", False, 25,
     "frames", "extract-frames"),
    # -- les LIBELLES : « un objet se nomme par son type » (AC 6.2). Le
    #    CONTENANT versionne est un lot scanne ; « dossier » nommait un
    #    contenant generique la ou un type existe.
    ("libelle du lot scanne ABSENT", r"Le dossier declare par le lot ",
     r"Le dossier declare par le lot ", "Le lot scanne declare par le lot ",
     False, 2,
     "DOSSIER_DE_LOT_ABSENT: Le dossier declare par le lot 'x' est introuvable",
     "DOSSIER_DE_LOT_ABSENT: Le lot scanne declare par le lot 'x' est introuvable"),
    # Le lookahead est la garde, et elle est mesuree : « Le dossier projet
    # n'existe pas » (scenario 23) parle du PROJET, pas d'un lot scanne, et une
    # regle sur « Le dossier » nu le traduirait aussi -- en fabriquant une
    # phrase qu'aucun code ne produit.
    ("libelle du lot scanne VIDE",
     r"Le dossier (?=\S+ ne porte aucune frame conforme)",
     r"Le dossier (?=\S+ ne porte aucune frame conforme)", "Le lot scanne ",
     False, 2,
     "Le dossier /p/frames-scannees/x ne porte aucune frame conforme au lot",
     "Le lot scanne /p/frames-scannees/x ne porte aucune frame conforme au lot"),
)

_TRADUCTIONS = tuple(
    (ligne[0], re.compile(ligne[1]), ligne[3], ligne[4])
    for ligne in TRADUCTIONS_DU_VOCABULAIRE)


def _traduire_un_texte(texte: str, compteur: dict, *, cle: bool = False) -> str:
    """Appliquer les traductions a un texte, en comptant CHACUNE a part.

    `cle=True` restreint aux regles declarees valables sur les cles --
    `EPIC11-ARB-221`, « on touche aux valeurs de chemin, jamais aux noms de
    cles » : un libelle n'est jamais une cle, et le traduire dans une cle
    fabriquerait un chemin qui n'existe pas.
    """
    for retire, motif, neuf, sur_les_cles in _TRADUCTIONS:
        if cle and not sur_les_cles:
            continue
        texte, mordu = motif.subn(neuf, texte)
        compteur[retire] = compteur.get(retire, 0) + mordu
    return texte


def traduire_le_vocabulaire(valeur, compteur: dict):
    """Rendre un releve du baseline dans les mots d'aujourd'hui (story 11.14).

    Les **cles** de l'arbre des artefacts sont des chemins relatifs : c'est la
    que vit le nom du dossier, et c'est pourquoi la traduction porte sur les
    cles autant que sur les feuilles. Le compteur est rendu par la bande plutot
    que devine : un banc qui ne saurait pas combien de fois il a substitue ne
    saurait pas non plus quand il aurait cesse de le faire.
    """
    if isinstance(valeur, dict):
        return {_traduire_un_texte(str(cle), compteur, cle=True):
                traduire_le_vocabulaire(sous, compteur)
                for cle, sous in valeur.items()}
    if isinstance(valeur, list):
        return [traduire_le_vocabulaire(sous, compteur) for sous in valeur]
    if isinstance(valeur, str):
        return _traduire_un_texte(valeur, compteur)
    return valeur


def _reference_brute() -> dict:
    """La reference telle qu'elle est versionnee, SANS traduction.

    Elle sert aux temoins : sans elle, « la traduction a mordu 240 fois » ne
    pourrait etre confronte a ce que le fichier porte reellement.
    """
    return json.loads(REFERENCE_AVANT_DEPLACEMENT.read_text(encoding="utf-8"))


def _reference() -> dict:
    """La reference, **traduite** dans le vocabulaire d'aujourd'hui."""
    return traduire_le_vocabulaire(_reference_brute(), {})


def test_le_dossier_d_identite_porte_bien_VINGT_CINQ_invocations(
        dossier_d_identite) -> None:
    """Temoin de cardinal, **des deux cotes**.

    La reference y figure aussi : elle pourrait avoir ete regeneree sur un jeu
    de scenarios reduit, et la comparaison resterait verte en ne mesurant plus
    rien.
    """
    reference = _reference()
    assert len(dossier_d_identite["scenarios"]) == INVOCATIONS_ATTENDUES
    assert len(reference["scenarios"]) == INVOCATIONS_ATTENDUES
    assert set(reference["scenarios"]) == set(dossier_d_identite["scenarios"])


def test_les_deux_releves_ont_ete_joues_sur_les_MEMES_octets(
        dossier_d_identite) -> None:
    """« Des entrees octet pour octet identiques », mesure et non exigee.

    La fabrique des entrees vit dans `tests/` : elle peut changer entre
    l'ecriture d'une reference et sa relecture, et un ecart de fabrique se
    lirait alors comme un ecart de produit -- c'est-a-dire le contraire exact de
    ce que ce dossier existe pour dire.
    """
    reference = _reference()
    ecarts = {
        chemin for chemin in set(reference["entrees"]) | set(dossier_d_identite["entrees"])
        if reference["entrees"].get(chemin) != dossier_d_identite["entrees"].get(chemin)
    }
    assert ecarts == set(), sorted(ecarts)


# ===========================================================================
# La ponctuation d'`argparse` a change EN COURS DE SERIE -- 2026-09-08
# ===========================================================================

#: Les deux formes que CPython donne au meme fait. Ecrites ici plutot que
#: derivees de l'interpreteur courant : derivees, elles diraient seulement « ce
#: que fait cette machine », ce qui est exactement ce que la panne a coute --
#: le conteneur portait 3.12.3 et rendait vert ce que le runner rendait rouge.
FORME_QUOTEE = (
    "mmu encode: error: argument --profile: invalid choice: 'x' "
    "(choose from 'prores_hq', 'dnxhr_hq')")
FORME_NUE = (
    "mmu encode: error: argument --profile: invalid choice: 'x' "
    "(choose from prores_hq, dnxhr_hq)")


def test_les_DEUX_formes_d_argparse_different_REELLEMENT() -> None:
    """Le volet d'anti-vacuite, et il vient en premier.

    Sans lui, deux formes egales rendraient toutes les mesures qui suivent
    vraies pour toujours -- une canonisation qui ne canonise rien passerait
    pour bonne.
    """
    assert FORME_QUOTEE != FORME_NUE


def test_la_canonisation_ramene_la_forme_NUE_a_la_forme_QUOTEE() -> None:
    """Le sens qui ferme la panne : c'est la forme nue que le runner rend."""
    assert socle._choix_canonises(FORME_NUE) == FORME_QUOTEE


def test_la_canonisation_est_IDEMPOTENTE_sur_la_forme_deja_QUOTEE() -> None:
    """La reference versionnee porte la forme quotee : elle ne doit pas bouger.

    Sans cette mesure, une canonisation qui requoterait les quotes ferait
    diverger les DEUX cotes a la fois, et la panne changerait de forme au lieu
    de se fermer.
    """
    assert socle._choix_canonises(FORME_QUOTEE) == FORME_QUOTEE


@pytest.mark.parametrize("ecart_reel", [
    # un profil qui disparait du produit
    "mmu encode: error: argument --profile: invalid choice: 'x' "
    "(choose from prores_hq)",
    # un profil renomme
    "mmu encode: error: argument --profile: invalid choice: 'x' "
    "(choose from prores_hq, dnxhr_444)",
    # l'ORDRE des choix, qui est `sorted(PROFILES)` et donc un observable
    "mmu encode: error: argument --profile: invalid choice: 'x' "
    "(choose from dnxhr_hq, prores_hq)",
    # la valeur refusee, qui n'est pas dans le fragment canonise
    "mmu encode: error: argument --profile: invalid choice: 'y' "
    "(choose from prores_hq, dnxhr_hq)",
    # le nom de l'argument
    "mmu encode: error: argument --preset: invalid choice: 'x' "
    "(choose from prores_hq, dnxhr_hq)",
])
def test_la_canonisation_NE_MASQUE_PAS_un_ecart_REEL(ecart_reel: str) -> None:
    """Le volet symetrique : elle porte sur la PONCTUATION, pas sur le contenu.

    C'est ce que cette famille mesure et qu'aucun test positif ne verrait : une
    canonisation trop large -- masquer le fragment entier, par exemple --
    rendrait le scenario vert quel que soit le produit, donc le scenario
    cesserait de mesurer que `--profile` refuse ce qu'il doit refuser.

    Les DEUX cotes passent par la canonisation, et ce detail est ce qui donne
    sa force a la mesure : compare a la constante NUE, ce banc survivait au
    mutant qui remplace le fragment entier par un litteral -- les deux cotes
    devenant alors differents pour la mauvaise raison. Mesure le 2026-09-08 :
    mutant `N2` survivant avant, tue apres.
    """
    assert (socle._choix_canonises(ecart_reel)
            != socle._choix_canonises(FORME_QUOTEE))


def test_la_canonisation_NE_TOUCHE_a_AUCUNE_ligne_sans_le_fragment() -> None:
    """Une ligne quelconque du releve traverse la canonisation inchangee."""
    for ligne in ("usage: mixed-media-util encode [-h] --project PROJECT",
                  "[--profile {dnxhr_hq,prores_hq}]",
                  "lot B0 : 3 frames, 12.5 im/s",
                  "(choose from) sans liste",
                  ""):
        assert socle._choix_canonises(ligne) == ligne


def test_le_message_de_divergence_NOMME_le_CONTENU_et_pas_seulement_la_CLE(
) -> None:
    """Ce qui a coute douze minutes de CI par hypothese, le 2026-09-08.

    Les trois formes d'observable du releve sont couvertes, et la borne aussi :
    un `arbre` de projet a des centaines d'entrees, un message non borne n'est
    pas lu.
    """
    lignes = _premieres_differences("22", "stderr", ["a", "b"], ["a", "c"])
    rendu = "\n".join(lignes)
    assert "22.stderr" in rendu
    assert "'b'" in rendu and "'c'" in rendu
    # ... et il ne recopie pas ce qui est EGAL : sans quoi la borne serait
    # depensee a rendre des lignes identiques.
    assert "'a'" not in rendu

    rendu_dict = "\n".join(_premieres_differences("22", "arbre",
                                                  {"f": "1"}, {"f": "2"}))
    assert "f : attendu '1' obtenu '2'" in rendu_dict

    rendu_nu = "\n".join(_premieres_differences("22", "code", 0, 2))
    assert "attendu 0" in rendu_nu and "obtenu  2" in rendu_nu

    # La borne mord, et elle le DIT plutot que de tronquer en silence.
    long_attendu = [str(rang) for rang in range(50)]
    long_obtenu = [f"x{rang}" for rang in range(50)]
    borne = _premieres_differences("22", "stderr", long_attendu, long_obtenu)
    assert len(borne) <= PLAFOND_DE_DIFFERENCES_RENDUES + 2
    assert borne[-1].strip() == "... (tronque)"


#: Le plafond de lignes rendues PAR OBSERVABLE divergent. Borne parce qu'un
#: `arbre` de projet compte des centaines d'entrees : un message non borne est
#: illisible, donc il n'est pas lu, donc il ne mesure rien -- meme motif que la
#: sortie bornee de `scripts/mesure/mesure.py etat`.
PLAFOND_DE_DIFFERENCES_RENDUES = 6


def _premieres_differences(nom: str, cle: str, attendu, obtenu) -> list[str]:
    """Rendre CE QUI diverge, pas seulement OU.

    Ecrit le 2026-09-08, apres une divergence dont la CI publique n'a nomme que
    la cle (`{'22-profil-inconnu': ['stderr']}`) : il a fallu un aller-retour de
    douze minutes par hypothese pour apprendre que la ligne fautive etait la
    ponctuation d'`argparse`. Un message qui nomme la cle sans le contenu envoie
    chercher ailleurs ce qu'il a sous la main.

    Les trois formes que prend un observable du releve sont couvertes : une
    liste de lignes (`stdout`, `stderr`, un journal), un dictionnaire (l'arbre,
    les documents aplatis) et une valeur nue (le code de sortie).
    """
    entete = f"  {nom}.{cle} :"
    if isinstance(attendu, list) and isinstance(obtenu, list):
        lignes = [entete]
        for rang in range(max(len(attendu), len(obtenu))):
            gauche = attendu[rang] if rang < len(attendu) else "<absente>"
            droite = obtenu[rang] if rang < len(obtenu) else "<absente>"
            if gauche == droite:
                continue
            if len(lignes) > PLAFOND_DE_DIFFERENCES_RENDUES:
                lignes.append("    ... (tronque)")
                break
            lignes.append(f"    [{rang}] attendu {gauche!r}")
            lignes.append(f"    [{rang}] obtenu  {droite!r}")
        return lignes
    if isinstance(attendu, dict) and isinstance(obtenu, dict):
        lignes = [entete]
        for sous in sorted(set(attendu) | set(obtenu)):
            if attendu.get(sous) == obtenu.get(sous):
                continue
            if len(lignes) > PLAFOND_DE_DIFFERENCES_RENDUES:
                lignes.append("    ... (tronque)")
                break
            lignes.append(f"    {sous} : attendu {attendu.get(sous)!r} "
                          f"obtenu {obtenu.get(sous)!r}")
        return lignes
    return [entete, f"    attendu {attendu!r}", f"    obtenu  {obtenu!r}"]


def test_le_deplacement_ne_fait_diverger_AUCUN_scenario(dossier_d_identite) -> None:
    """AC 2.2 -- l'ensemble des divergents est **VIDE**, jamais « presque vide ».

    Un scenario est egal quand **tout** l'est a la fois : le code de sortie,
    `stdout` et `stderr` au caractere pres, le condensat SHA-256 de chaque
    fichier laisse dans le projet -- donc le master **octet a octet** --, le
    rapport `ffprobe` **champ a champ**, chaque document JSON aplati -- donc les
    metadonnees reinjectees au manifest -- et les lignes de `logs/encode.log`.
    """
    reference = _reference()["scenarios"]
    joues = dossier_d_identite["scenarios"]
    divergents = {nom for nom in reference if reference[nom] != joues[nom]}
    detail = {
        nom: sorted(cle for cle in set(reference[nom]) | set(joues[nom])
                    if reference[nom].get(cle) != joues[nom].get(cle))
        for nom in sorted(divergents)
    }
    assert divergents == set(), (
        f"le deplacement a change un observable par rapport a "
        f"{COMMIT_AVANT_DEPLACEMENT} : {detail}\n"
        + "\n".join(
            ligne
            for nom in sorted(divergents)
            for cle in detail[nom]
            for ligne in _premieres_differences(
                nom, cle, reference[nom].get(cle), joues[nom].get(cle))))


def test_le_dossier_atteint_bien_les_QUATRE_codes_de_sortie(
        dossier_d_identite) -> None:
    """Sans ce temoin, vingt-cinq refus identiques passeraient pour une couverture.

    Le cardinal par code est **exact** : « le code 0 est atteint » ne mesure
    rien, « onze scenarios rendent 0 et onze rendent 1 » mesure que les deux
    moities du contrat sont exercees.
    """
    cardinal: dict = {}
    for scenario in dossier_d_identite["scenarios"].values():
        cardinal[scenario["code"]] = cardinal.get(scenario["code"], 0) + 1
    assert cardinal == CARDINAL_PAR_CODE_DE_SORTIE


def test_le_dossier_a_reellement_ENCODE_et_pas_seulement_refuse(
        dossier_d_identite) -> None:
    """Le volet symetrique du precedent, et il porte sur l'ARTEFACT.

    Un dossier qui ne ferait que des refus comparerait des dossiers vides. On
    mesure donc que douze masters **sondables par `ffprobe`** ont ete laisses,
    et que les trois familles de codec et les deux conteneurs y sont.
    """
    rapports = [rapport for scenario in dossier_d_identite["scenarios"].values()
                for rapport in scenario["ffprobe"].values()]
    assert len(rapports) == MASTERS_SONDES

    codecs = {rapport["streams[0].codec_name"] for rapport in rapports}
    assert codecs == {"prores", "dnxhd", "h264"}, codecs
    conteneurs = {chemin.rsplit(".", 1)[-1]
                  for scenario in dossier_d_identite["scenarios"].values()
                  for chemin in scenario["ffprobe"]}
    assert conteneurs == {"mov", "mp4"}, conteneurs


# ===========================================================================
# Story 11.14 -- la reference se TRADUIT, elle ne se regenere pas
# ===========================================================================

@pytest.mark.parametrize(
    "retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres",
    TRADUCTIONS_DU_VOCABULAIRE,
    ids=[ligne[0] for ligne in TRADUCTIONS_DU_VOCABULAIRE])
def test_la_TRADUCTION_MORD_le_nombre_EXACT_de_fois(
        retire, motif, brut, neuf, sur_les_cles, cardinal, avant, apres) -> None:
    """Story 11.14 -- la traduction se mesure, elle ne se declare pas.

    **Une mesure par regle, jamais une seule pour les cinq** : un cardinal
    global serait juste alors qu'une regle serait morte et une autre deux fois
    trop large -- exactement le mode de panne que le lot B a paye sur son
    releve de noms ambigus, ou un cardinal stable recouvrait deux sorties et
    une entree.

    Le cardinal est confronte au compte **brut** du litteral dans le fichier de
    reference. Les deux coincident tant que toutes les occurrences relevent de
    la regle ; si l'une cessait d'en relever -- un mot du vocabulaire tombant
    dans une phrase plutot que dans un chemin --, les deux nombres divergeraient
    et c'est precisement ce qu'il faudrait savoir.

    Et la ligne porte son propre exemple AVANT/APRES : la traduction est
    rejouee dessus, donc une regle dont le motif ne mordrait plus son propre
    exemple rougit ici, sans qu'aucun temoin ait a redecouvrir le motif.
    """
    compteur: dict = {}
    traduire_le_vocabulaire(_reference_brute(), compteur)
    assert compteur.get(retire, 0) == cardinal, compteur

    dans_le_fichier = len(re.findall(
        brut, REFERENCE_AVANT_DEPLACEMENT.read_text(encoding="utf-8")))
    assert dans_le_fichier == cardinal, (
        f"{dans_le_fichier} occurrences de {retire!r} dans le fichier pour "
        f"{cardinal} substitutions : une occurrence n'est plus couverte par la "
        "regle, et la traduction la laisse passer en silence")

    temoin: dict = {}
    assert _traduire_un_texte(avant, temoin, cle=sur_les_cles) == apres


def test_la_traduction_LAISSE_VIVRE_la_cle_de_manifeste() -> None:
    """`EPIC11-ARB-221` -- les CLES du document ne changent pas. Frontiere NEGATIVE.

    C'est la moitie du renommage qu'il est le plus facile de faire par
    inadvertance : `output_frames_dir` **ressemble** a `output-frames`, et une
    regle ecrite au tiret pres est tout ce qui separe une traduction juste
    d'une reference qui declarerait une cle que le schema ne connait pas.

    Le compte est **exact et non nul des deux cotes** : la cle est presente 50
    fois avant et 50 fois apres. « Zero occurrence apres » serait aussi vrai si
    elle avait disparu, et « presente apres » serait vrai d'une seule survivante
    sur cinquante.
    """
    brut = REFERENCE_AVANT_DEPLACEMENT.read_text(encoding="utf-8")
    traduite = json.dumps(_reference(), ensure_ascii=False)
    assert brut.count("output_frames_dir") == 50
    assert traduite.count("output_frames_dir") == 50
    assert "frames-scannees_dir" not in traduite
    assert "extract-frames_dir" not in traduite


def test_la_traduction_ne_touche_PAS_au_dossier_du_PROJET() -> None:
    """Volet symetrique : une regle de libelle trop large fabriquerait une phrase.

    « Le dossier projet n'existe pas » (scenario 23) parle du PROJET, pas d'un
    lot scanne. Sans le lookahead de la regle « lot scanne VIDE », elle serait
    traduite en « Le lot scanne projet n'existe pas » -- une phrase qu'aucun
    code du depot ne produit, donc un rouge qu'on irait chercher dans le
    produit alors qu'il serait dans le banc.

    Sans ce temoin, les cardinaux exacts du test precedent ne suffiraient pas :
    ils comptent les morsures, ils ne disent pas OU elles mordent.
    """
    traduite = _reference()["scenarios"]["23-projet-inexistant"]["stderr"]
    assert any("Le dossier projet n'existe pas" in ligne for ligne in traduite), traduite
    assert not any("Le lot scanne projet" in ligne for ligne in traduite), traduite


def test_la_reference_TRADUITE_ne_porte_plus_AUCUN_mot_retire() -> None:
    """La sortie de la traduction, mesuree pour elle-meme.

    Les cardinaux disent que chaque regle a mordu ; ils ne disent pas que
    **rien** n'est reste. Une occurrence du mot retire dans une forme qu'aucune
    regle ne prevoit -- un `output-frames` colle a un autre mot, par exemple --
    ne se verrait dans aucun des cinq comptes.
    """
    traduite = json.dumps(_reference(), ensure_ascii=False)
    assert "output-frames" not in traduite
    assert not re.search(r"(?<![\w-])frames/", traduite)
    assert "Le dossier declare par le lot" not in traduite
    # Et le mot NEUF est bien la, sans quoi « plus aucun mot retire » serait
    # aussi vrai d'une reference vide.
    assert traduite.count("frames-scannees") == 240
    assert traduite.count("extract-frames") == 50


def test_les_scenarios_du_LOT_SCANNE_visent_un_dossier_qui_EXISTE(
        tmp_path) -> None:
    """Story 11.14 -- le defaut que `dossiers_de_lots_scannes` ferme.

    Les scenarios `27` et `32` composaient `projet / "output-frames"` en clair.
    Le dossier ayant change de nom, leur balayage a cesse de mordre et les deux
    scenarios ont continue de passer au VERT **en ne mesurant plus rien** : ils
    vidaient un dossier absent. Un chemin fige est pire qu'un rouge.

    Trois lots declares, **aux cardinaux distincts** (1, 3 puis 2 frames) et
    **repartis sur les deux racines** -- l'ancienne en TETE, la neuve en QUEUE,
    et une passe de reconstruction au MILIEU. Un balayage tronque d'un bout ou
    de l'autre, un `find` qui rendrait le premier lot, ou un lecteur qui
    ignorerait `reconstructions[]` rougissent tous les trois ici, et aucun ne
    se demasquerait sur une fabrique a un seul lot uniforme.
    """
    projet = tmp_path / "p"
    declares = {
        # en TETE : la racine d'AVANT, qu'`EPIC11-ARB-222` garde lisible
        "output-frames/lot-ancien": 1,
        # au MILIEU : une passe de reconstruction, sur la racine neuve
        "frames-scannees/lot-b_v2": 3,
        # en QUEUE : la racine NEUVE
        "frames-scannees/lot-c": 2,
    }
    for relatif, cardinal in declares.items():
        (projet / relatif).mkdir(parents=True)
        for index in range(cardinal):
            (projet / relatif / f"scan_r_12p5_00-00-00-{index:02d}.tiff").write_bytes(b"x")
    # Un dossier que NUL lot ne declare : il ne doit pas etre rendu, sans quoi
    # « les lots scannes declares » serait « tout ce qui traine ».
    (projet / "frames-scannees" / "lot-non-declare").mkdir(parents=True)
    (projet / "project.json").write_text(json.dumps({"lots": [
        {"lot_id": "a", "output_frames_dir": "output-frames/lot-ancien"},
        {"lot_id": "b", "output_frames_dir": "frames-scannees/lot-c",
         "reconstructions": [{"output_frames_dir": "frames-scannees/lot-b_v2"}]},
    ]}), encoding="utf-8")

    rendus = identite.dossiers_de_lots_scannes(projet)
    assert {chemin.relative_to(projet).as_posix() for chemin in rendus} == set(declares)
    assert sum(1 for chemin in rendus
               for fichier in chemin.rglob("*") if fichier.is_file()) == 6


def test_un_projet_SANS_lot_scanne_declare_REFUSE_plutot_que_de_se_taire(
        tmp_path) -> None:
    """Volet symetrique du precedent, et c'est lui qui ferme le defaut d'origine.

    Rendre une liste vide serait exactement la panne payee : la boucle
    d'effacement tournerait a vide et le scenario passerait au vert sans avoir
    rien fait. Le refus NOMME le manifeste fautif (`EPIC11-ARB-89` : un refus
    qui n'offre aucune issue est aussi fautif qu'une destruction silencieuse).
    """
    projet = tmp_path / "p"
    projet.mkdir()
    (projet / "project.json").write_text(
        json.dumps({"lots": [{"lot_id": "a"}]}), encoding="utf-8")
    with pytest.raises(AssertionError) as refus:
        identite.dossiers_de_lots_scannes(projet)
    assert "aucun lot scanne declare" in str(refus.value)
    assert "project.json" in str(refus.value)


# ===========================================================================
# Story 11.14 -- les LIBELLES nomment l'objet par son TYPE (AC 6.2)
# ===========================================================================

def test_les_candidats_d_un_lot_sont_decrits_par_LOT_SCANNE_et_non_par_dossier(
) -> None:
    """`encode.describe_lot_candidate` -- « un objet se nomme par son type ».

    Le champ decrit est `output_frames_dir`, c'est-a-dire le CONTENANT
    versionne : un **lot scanne**. « dossier » nommait un contenant generique la
    ou un type existe, et c'est le retour d'Egan que la planche v2 n'avait pas
    porte (note 9 du 2026-09-04 : « reste a les nommer »).

    **Trois candidats distinguables**, jamais un remplissage uniforme : leurs
    cardinaux different, et le lot **sans** dossier declare est en QUEUE
    -- « non declare » est le cas ou la phrase se replie, et un balayage tronque
    par la queue ne le verrait pas. Le second porte une VERSION, donc un rang :
    c'est le candidat du milieu, celui qu'un `find` fautif rendrait a la place
    du premier.
    """
    manifeste = {"lots": [
        {"lot_id": "L", "state": "scan", "expected_frame_count": 8,
         "reconstructed_frame_count": 8, "synthetic_frame_count": 0,
         "output_frames_dir": "frames-scannees/L"},
        {"lot_id": "L-t2", encode_module.DERIVED_FROM_LOT_FIELD: "L",
         "state": "scan", "expected_frame_count": 5,
         "reconstructed_frame_count": 4, "synthetic_frame_count": 1,
         "output_frames_dir": "frames-scannees/L_v2"},
        {"lot_id": "L-t3", encode_module.DERIVED_FROM_LOT_FIELD: "L",
         "state": "reconstruction", "expected_frame_count": 3},
    ]}
    lignes = [encode_module.describe_lot_candidate(lot)
              for lot in encode_module.find_lot_candidates(manifeste, "L")]

    assert lignes == [
        "L (etat scan, cardinal attendu 8, frames reelles 8, mires 0, "
        "lot scanne frames-scannees/L)",
        "L-t2 (etat scan, cardinal attendu 5, frames reelles 4, mires 1, "
        "lot scanne frames-scannees/L_v2)",
        "L-t3 (etat reconstruction, cardinal attendu 3, frames reelles inconnu, "
        "mires inconnu, lot scanne non declare)",
    ], lignes
    assert not any("dossier" in ligne for ligne in lignes), lignes


def test_les_passes_d_un_lot_sont_decrites_par_LOT_SCANNE_et_non_par_dossier(
        tmp_path) -> None:
    """Le refus qui NOMME les passes (`EPIC11-ARB-89`), dans les mots d'Egan.

    Une passe de `lots[].reconstructions` **est** un lot scanne : c'est ce que
    le lot B a promu au rang d'objet. Le libelle le dit donc, comme le coeur.

    **Quatre passes distinguables, une cible a chaque bord** : la premiere est
    presente sur le disque, la derniere ABSENTE, et celle **sans** dossier
    declare -- le cas legal ou le rang vaut `None` -- est au milieu. Un
    balayage tronque d'un bout ou de l'autre perd un etat que les autres ne
    portent pas, et le cardinal exact des lignes est ce qui le dit.
    """
    projet = tmp_path / "p"
    (projet / "frames-scannees" / "L").mkdir(parents=True)
    (projet / "frames-scannees" / "L_v2").mkdir(parents=True)
    lot = {"lot_id": "L", "reconstructions": [
        {"output_frames_dir": "frames-scannees/L", "ingest_slug": "scan-a"},
        {"output_frames_dir": "frames-scannees/L_v2", "ingest_slug": "scan-b"},
        {"ingest_slug": "scan-c"},
        {"output_frames_dir": "frames-scannees/L_v3", "ingest_slug": "scan-d"},
    ]}
    passes = encode_module.enumerer_les_reconstructions(lot, projet)
    rendu = encode_module._decrire_les_reconstructions(passes)

    assert rendu == (
        "\n  - rang 1, lot scanne frames-scannees/L (scan scan-a)"
        "\n  - rang 2, lot scanne frames-scannees/L_v2 (scan scan-b)"
        "\n  - rang inconnu, lot scanne non declare (scan scan-c, ABSENT du disque)"
        "\n  - rang 3, lot scanne frames-scannees/L_v3 (scan scan-d, ABSENT du disque)"
    ), rendu
    assert rendu.count("lot scanne") == 4, rendu
    assert "dossier" not in rendu, rendu


# ===========================================================================
# Story 11.14 -- la FRONTIERE NEGATIVE du vocabulaire
# ===========================================================================
#
# Elle vit ici plutot que dans un banc par module, et le choix se dit : les
# trois modules sont ceux d'un meme lot, et la propriete mesuree est **une** --
# « un mot, un objet ». Trois bancs porteraient trois redactions de la meme
# liste de mots retires, c'est-a-dire la seconde verite que cette story existe
# pour fermer.

#: Les modules que ce lot possede. `scan_output_frames.py` n'y est PAS : son
#: nom porte l'ancien vocabulaire, c'est vu et assume -- le renommer touche les
#: imports de tout le depot, donc de tous les lots en vol, et c'est une
#: operation a part.
MODULES_DU_LOT = ("encode.py", "io/naming.py", "gui/atelier_scan.py")

#: Les mots retires, et ce qui les remplace. Un test POSITIF ne verrait jamais
#: revenir l'un d'eux : il faut une frontiere negative, et c'est la seule facon
#: d'attraper la reintroduction d'un defaut.
#:
#: `--frames` est mesure **seul** (`(?![-\w])`) : `--frames-par-page` est une
#: option vivante qui parle des pages d'une planche, donc d'un autre objet, et
#: `frames-scannees/` est le nom du DOSSIER, gele. Une regle qui les attraperait rougirait sur
#: du code juste, et un banc qui rougit a tort finit desarme.
#:
#: **Les deux dernieres lignes sont d'`EPIC11-ARB-223`** (2026-09-04, lot F) :
#: « reconstruction » etait le TROISIEME nom de la passe de scan, et c'est
#: desormais « lot scanne ». Leurs motifs sont deliberement ETROITS, et chaque
#: restriction paie un survivant precis que le volet symetrique ci-dessous
#: mesure : un motif sur `reconstruction` nu rougirait sur la cle gelee
#: `reconstructions` (`RECONSTRUCTIONS_FIELD`), sur la section `reconstruction`
#: du manifeste -- qui decrit un AUTRE objet, le detail par frame -- et sur le
#: chemin de module `io/reconstruction`. Une frontiere rouge sur du code juste
#: finit desarmee ; on mesure donc la PROSE FRANCAISE qui nomme l'objet
#: (determinant + mot, ou « Reconstruction visee/designee » en tete de refus),
#: jamais le jeton.
#:
#: (nom, motif, ce qui le remplace, exemple qui le porte)
MOTS_RETIRES = (
    ("output-frames", r"output-frames", "frames-scannees",
     "le dossier output-frames/lot-a"),
    ("frames rescannees", r"frames?\s+rescannees?", "frames scannees",
     "les frames rescannees du lot"),
    ("lot rescanne", r"lots?\s+rescannes?", "lot scanne",
     "un lot rescanne de ce projet"),
    ("--frames seul", r"--frames(?![-\w])", "--lot-scanne",
     "relancer avec --frames 2"),
    # `EPIC11-ARB-224` : le nom neuf du lot C est a son tour retire. Le motif
    # garde la borne de jeton -- `frames-scannees/` reste le nom du DOSSIER
    # (`SCAN_FRAMES_DIRNAME`, gele) et le `--` en tete l'en distingue.
    ("--frames-scannees", r"--frames-scannees(?![-\w])", "--lot-scanne",
     "relancer avec --frames-scannees 2"),
    ("reconstruction, avec determinant",
     r"(?:[Aa]ucune|[Ll]a|[Uu]ne|[Cc]ette)\s+reconstruction", "lot scanne",
     "Aucune reconstruction 'v2' pour le lot 'rush-b_12'"),
    ("Reconstruction visee ou designee",
     r"Reconstruction\s+(?:visee|designee)", "Lot scanne vise ou designe",
     "Reconstruction visee inexploitable pour le lot 'L'"),
)

#: Ce qui doit RESTER, et c'est le volet symetrique sans lequel la frontiere
#: serait verte sur un module devenu muet. La cle de manifeste est gelee par
#: `EPIC11-ARB-221` : elle DOIT continuer d'etre nommee a l'operateur, puisque
#: c'est la cle qu'il aura a ecrire dans son document.
CLE_DE_MANIFESTE_GELEE = "output_frames_dir"


def _chaines_visibles(source: str) -> list:
    """Toute chaine litterale d'un module, docstrings comprises, DANS L'ORDRE.

    « Visible » se definit ici, une fois : ce qu'un operateur peut lire. Une
    chaine litterale peut atteindre un terminal, une fenetre ou un `--help` ;
    un commentaire `#`, jamais. C'est pourquoi le bloc de frontiere en tete
    d'`encode.py` peut NOMMER les mots retires sans faire rougir cette
    mesure -- meme raison que `LEGACY_FRAMES_DIRNAME`, qui entre dans le releve
    du lot A et y reste parce qu'il nomme le mot qu'il retire.

    L'ordre est celui de la SOURCE (`ast.walk` rend un parcours en largeur, pas
    l'ordre du fichier) : sans lui, « la premiere chaine » et « la derniere »
    ne voudraient rien dire, et le temoin de bord ci-dessous ne mesurerait pas
    ce qu'il annonce.
    """
    noeuds = [noeud for noeud in ast.walk(ast.parse(source))
              if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)]
    noeuds.sort(key=lambda noeud: (noeud.lineno, noeud.col_offset))
    return [(noeud.lineno, noeud.value) for noeud in noeuds]


#: Un module MINIATURE, mais un vrai module : il est parse par le vrai
#: collecteur. Les mots retires y sont poses **en tete et en queue**, et un
#: commentaire `#` en porte un au milieu.
#:
#: **Sa forme n'est pas libre, et c'est un mutant survivant qui l'a dit.** La
#: chaine de queue est posee au niveau MODULE et celle du milieu au fond d'une
#: fonction : `ast.walk` rend un parcours en LARGEUR, donc il remonterait
#: `"--frames"` avant `"au milieu"` et la queue ne serait plus la queue. Une
#: premiere version rangeait les deux dans l'autre sens ; retirer le tri de
#: `_chaines_visibles` n'y changeait rien, et le mutant `M09` survivait.
#: Autrement dit le temoin mesurait le collecteur sans mesurer son ORDRE.
#:
#: C'est le piege paye par le lot C, et il est repris tel quel : ses deux
#: mutants survivants venaient d'un temoin qui mesurait l'APPARIEMENT et non le
#: COLLECTEUR -- un `[:-1]` ou un `[1:]` passait. Ici le temoin part de la
#: source et traverse `_chaines_visibles`, donc les deux troncatures meurent.
MODULE_MINIATURE = '''"""Docstring de tete: output-frames."""


def f():
    """Docstring du milieu: frames rescannees."""
    return "au milieu, rien de retire"


# Un commentaire qui nomme output-frames -- il ne doit PAS etre collecte.
CONSTANTE_DE_QUEUE = "--frames"
'''


def test_le_COLLECTEUR_de_chaines_visibles_voit_la_TETE_et_la_QUEUE() -> None:
    """Le temoin part d'une SOURCE reelle et traverse le vrai collecteur.

    Quatre chaines distinguables, un mot retire en **tete** et un autre en
    **queue** (regle des fabriques, point 4 : une cible au milieu demasque un
    `find` fautif, elle ne demasque pas un balayage tronque). Le `# commentaire`
    du milieu porte lui aussi un mot retire et ne doit PAS etre collecte : sans
    lui, un collecteur qui lirait le texte brut au lieu de l'AST passerait.
    """
    chaines = [valeur for _ligne, valeur in _chaines_visibles(MODULE_MINIATURE)]
    assert len(chaines) == 4, chaines
    assert "output-frames" in chaines[0], chaines[0]
    assert chaines[-1] == "--frames", chaines[-1]
    assert any("frames rescannees" in valeur for valeur in chaines)
    # Et la queue n'est la queue que parce que l'ordre est celui de la SOURCE :
    # en largeur, `"--frames"` (niveau module) remonterait avant `"au milieu"`
    # (au fond de `f`). C'est ce que le mutant `M09` a etabli.
    assert chaines[-2] == "au milieu, rien de retire", chaines
    # Le commentaire n'est nulle part -- et son texte n'est identique a aucune
    # des chaines, donc son absence se mesure vraiment.
    assert not any("il ne doit PAS etre collecte" in valeur for valeur in chaines)

    # Le collecteur trouve TROIS mots retires dans cette miniature : un par
    # bord, un au milieu. Une troncature d'un bout ou de l'autre en rendrait
    # deux, et le cardinal exact est ce qui les separe.
    trouves = [valeur for valeur in chaines
               if any(re.search(motif, valeur)
                      for _n, motif, _neuf, _ex in MOTS_RETIRES)]
    assert len(trouves) == 3, trouves


def _module_temoin(exemple: str) -> str:
    """Un module Python MINIATURE portant `exemple` en TETE, au MILIEU et en QUEUE.

    C'est un **source**, pas une liste de chaines : le temoin doit traverser
    `_chaines_visibles` -- le COLLECTEUR --, et pas seulement `re.search` --
    l'appariement. C'est le defaut paye trois fois dans cette story (lot C :
    deux mutants ; lot D1 : quatre) : une frontiere negative attend une liste
    vide, donc elle reste VERTE si le balayage qui l'alimente est tronque, et
    aucune de ses propres assertions ne peut le voir.

    Les trois porteuses sont **distinguables** -- elles ne different pas que
    par leur position -- et une quatrieme chaine, sans le mot, s'intercale :
    sans elle, « trois porteuses sur trois chaines » serait aussi vrai d'un
    motif qui attrape tout.

    La chaine de QUEUE est posee au niveau MODULE et celle du MILIEU au fond
    d'une fonction, parce qu'`ast.walk` rend un parcours en LARGEUR : sans le
    tri de `_chaines_visibles`, la queue ne serait plus la queue. C'est ce
    qu'a etabli le mutant `M09`.
    """
    return (
        f'''"""Docstring de tete: {exemple} -- porteuse numero un."""


def f():
    """Docstring du milieu: {exemple} -- porteuse numero deux."""
    return "une chaine intercalee, qui ne porte AUCUN mot retire"


# Un commentaire qui cite {exemple} -- il ne doit PAS etre collecte.
CONSTANTE_DE_QUEUE = "{exemple} -- porteuse numero trois, en queue"
'''
    )


@pytest.mark.parametrize("nom,motif,neuf,exemple", MOTS_RETIRES)
def test_le_BALAYAGE_de_chaque_mot_retire_MORD_a_CHAQUE_BORD(
    nom, motif, neuf, exemple
) -> None:
    """Regle des fabriques, point 4 -- en TETE **et** en QUEUE, mot par mot.

    Une ligne par mot retire, jamais une seule pour l'ensemble : un temoin
    global serait vert des que le premier mot mord, et les cinq autres motifs
    pourraient etre morts sans que rien ne le dise.

    Ce qui est mesure ici n'est PAS que le motif reconnait son exemple -- ca,
    `re.search` le dirait seul. C'est que le motif le reconnait **apres etre
    passe par le collecteur**, a chacun des trois emplacements. Un collecteur
    tronque d'un bout (`[1:]` ou `[:-1]`) rend deux porteuses au lieu de
    trois, et le cardinal exact est ce qui les separe.
    """
    chaines = _chaines_visibles(_module_temoin(exemple))
    assert len(chaines) == 4, chaines
    porteuses = [valeur for _ligne, valeur in chaines if re.search(motif, valeur)]
    assert len(porteuses) == 3, (nom, porteuses)
    assert "numero un" in porteuses[0], porteuses
    assert "numero deux" in porteuses[1], porteuses
    assert "numero trois" in porteuses[-1], porteuses
    # Le commentaire `#` porte lui aussi l'exemple et n'est nulle part : sans
    # cette moitie, un collecteur lisant le TEXTE BRUT rendrait quatre
    # porteuses et passerait quand meme les trois assertions ci-dessus.
    assert not any("PAS etre collecte" in valeur for _l, valeur in chaines)


#: Ce que les motifs d'`EPIC11-ARB-223` ne doivent SURTOUT pas attraper. Chaque
#: entree est un survivant legitime, et chacune dit pourquoi : un motif sur
#: `reconstruction` nu les prendrait toutes, la frontiere rougirait sur du code
#: juste, et un banc qui rougit a tort finit desarme.
VOISINS_DE_LA_RECONSTRUCTION = (
    # la cle de manifeste GELEE (`EPIC11-ARB-221`). Lue de la CONSTANTE plutot
    # que reepelee : un banc qui reecrit la cle en litteral est un second
    # endroit ou elle vit, et la garde chiffree de l'`ARB-221` -- le compte des
    # litteraux de cle dans `src/` et `tests/`, egal avant et apres -- le
    # verrait bouger pour un temoin de test.
    encode_module.RECONSTRUCTIONS_FIELD,
    # la section du manifeste, qui decrit un AUTRE objet -- le detail par frame
    "la section `reconstruction` ne decrit pas ce lot",
    # le chemin de MODULE, qui n'est le nom d'aucun objet d'Egan
    "`io/reconstruction.DEFAULT_LOT_STATE` vaut `reconstruction`",
    # le detail par page, nomme par sa cle
    "le detail par page vit dans reconstruction.page_calibration_results",
    # le jeton de contrat, miroite caractere pour caractere dans `encode_previz`
    "RECONSTRUCTION_INCONNUE",
    # la prose du schema, citee verbatim : « reecrite a chaque reconstruction »
    "reecrite en entier a chaque reconstruction: le scan d'un second lot",
)


@pytest.mark.parametrize("voisin", VOISINS_DE_LA_RECONSTRUCTION)
def test_les_motifs_de_l_ARB_223_ne_confondent_PAS_un_VOISIN_legitime(voisin) -> None:
    """Volet symetrique de la frontiere, et il est ce qui la rend utilisable.

    C'est le defaut n°2 du lot A, paye en 248 noms contre quelques dizaines :
    `lot` attrapait `slot`, `patch` attrapait `patch_preset_id`. Ici un motif
    trop large rougirait **quoi qu'on fasse**, puisque ces six formes doivent
    toutes survivre a `EPIC11-ARB-223` -- donc la frontiere serait inutile.
    """
    for nom, motif, _neuf, _exemple in MOTS_RETIRES:
        assert not re.search(motif, voisin), (
            f"le motif de {nom!r} attrape le voisin legitime {voisin!r}")


@pytest.mark.parametrize("module", MODULES_DU_LOT)
def test_AUCUNE_chaine_visible_ne_porte_un_mot_RETIRE(module) -> None:
    """Story 11.14 -- frontiere negative, un module a la fois.

    **Un banc par module, jamais un seul pour les trois** : un test global
    serait vert des que le premier module est propre, et c'est exactement la
    forme que l'AC 4.3 interdit (« une frontiere par nom renomme, pas une seule
    pour l'ensemble »).

    Ce qui est mesure est la chaine VISIBLE : ni le commentaire de frontiere en
    tete d'`encode.py`, qui nomme les mots retires pour les interdire, ni la cle
    de manifeste `output_frames_dir`, que `EPIC11-ARB-221` gele et que le test
    suivant exige au contraire de retrouver.
    """
    source = (REPO_ROOT / "src" / "mixed_media_utility" / module).read_text(
        encoding="utf-8")
    fautives = [
        (ligne, nom, neuf, valeur[:120])
        for ligne, valeur in _chaines_visibles(source)
        for nom, motif, neuf, _exemple in MOTS_RETIRES
        if re.search(motif, valeur)
    ]
    assert fautives == [], (
        f"{module} porte encore le vocabulaire d'avant dans une chaine que "
        f"l'operateur peut lire : {fautives}")


def test_la_frontiere_LAISSE_VIVRE_la_cle_de_manifeste_et_le_mot_NEUF() -> None:
    """Volet symetrique : sans lui, un module devenu muet passerait la frontiere.

    Deux moities, et elles disent deux choses differentes :

    * `encode.py` continue de NOMMER `output_frames_dir` a l'operateur. C'est
      la cle du document, gelee par `EPIC11-ARB-221`, et le refus
      `ENCODE_OUTPUT_DIR_NOT_DECLARED` doit la nommer telle quelle : la
      renommer dans le message ferait chercher a l'operateur une cle qui
      n'existe pas, c'est-a-dire un blocage sec deguise (`EPIC11-ARB-89`) ;
    * les mots NEUFS sont bien arrives -- « lot scanne » dans les libelles
      d'`encode.py`, « frames scannees » dans ceux d'`io/naming.py`. La
      frontiere negative seule serait satisfaite par un module qui aurait
      simplement cesse de parler.
    """
    chaines_encode = [valeur for _l, valeur in _chaines_visibles(
        (REPO_ROOT / "src" / "mixed_media_utility" / "encode.py").read_text(
            encoding="utf-8"))]
    assert any(CLE_DE_MANIFESTE_GELEE in valeur for valeur in chaines_encode)
    assert any("lot scanne" in valeur for valeur in chaines_encode)

    chaines_naming = [valeur for _l, valeur in _chaines_visibles(
        (REPO_ROOT / "src" / "mixed_media_utility" / "io" / "naming.py").read_text(
            encoding="utf-8"))]
    assert any("frames scannees" in valeur for valeur in chaines_naming)


def test_AUCUN_chemin_n_est_compose_en_CHAINE_LITTERALE() -> None:
    """Story 11.14, livrable 3 -- les noms de dossier ont UN seul proprietaire.

    Mesure AST plutot que `grep` : ce qui est interdit n'est pas de citer le
    mot, c'est de **composer un chemin** avec. On cherche donc les `/` dont un
    operande est un litteral portant un nom de dossier du vocabulaire.

    `gui/atelier_scan.py` est le module qui pourrait rechuter -- il compose bien
    un chemin, mais depuis `project_layout.racines_de_frames_scannees`, donc
    depuis le module qui POSSEDE la regle de cohabitation des deux racines
    (`EPIC11-ARB-222`).
    """
    noms_de_dossier = {"frames", "extract-frames", "frames-scannees",
                       "output-frames"}
    fautifs = []
    for module in MODULES_DU_LOT:
        chemin = REPO_ROOT / "src" / "mixed_media_utility" / module
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.BinOp) or not isinstance(noeud.op, ast.Div):
                continue
            for cote in (noeud.left, noeud.right):
                if (isinstance(cote, ast.Constant)
                        and isinstance(cote.value, str)
                        and cote.value.strip("/") in noms_de_dossier):
                    fautifs.append((module, noeud.lineno, cote.value))
    assert fautifs == [], (
        "un nom de dossier se compose ailleurs que dans `io/project_layout` : "
        f"{fautifs}")


# ===========================================================================
# AC 2.1 -- la forme du point d'entree, et le module qui le porte
# ===========================================================================

def test_le_point_d_entree_a_la_SIGNATURE_d_un_producteur_de_coeur() -> None:
    """AC 2.1 -- parametres nommes, **aucun objet `args`**.

    Le modele est `scan_detect.run_scan_detect`,
    `scan_write.ecrire_depuis_le_document` et
    `makepdf.generer_les_planches_du_lot` : un seul parametre positionnel, le
    dossier projet, et tout le reste **nomme**. Un `args` argparse est ce qui
    rendait ce corps inappelable depuis une interface -- c'est le fait F1 de la
    11.4b, et la raison d'etre de ce deplacement.
    """
    parametres = inspect.signature(encode_master.encoder_le_master_du_lot).parameters
    assert "args" not in parametres
    positionnels = [nom for nom, p in parametres.items()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert positionnels == ["project_dir"], positionnels
    for nom, parametre in parametres.items():
        if nom == "project_dir":
            continue
        assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, nom
    # Aucun code de sortie annonce: ce sont des faits, jamais un entier.
    # `eval_str=True` est necessaire et non decoratif : le module de coeur porte
    # `from __future__ import annotations`, donc l'annotation brute est la
    # CHAINE "MasterDuLot" -- et `chaine is not int` serait vrai meme si le
    # point d'entree annoncait `-> int`.
    resolue = inspect.signature(
        encode_master.encoder_le_master_du_lot, eval_str=True).return_annotation
    assert resolue is not int
    assert resolue is encode_master.MasterDuLot


@pytest.mark.parametrize("rappel", ["annoncer_le_recapitulatif",
                                    "confirmer_l_encodage",
                                    "annoncer_le_master",
                                    "logger"])
def test_les_rappels_et_le_journal_sont_OPTIONNELS(rappel: str) -> None:
    """`AR3` : leur absence ne change **rien** a l'observable.

    Une interface qui n'en passe aucun doit obtenir le meme master. Le regime
    est mesure pour de vrai plus bas
    (`test_sans_AUCUN_rappel_le_master_est_le_MEME_octet_pour_octet`) ; ici on
    mesure seulement que la signature le permet.
    """
    parametre = inspect.signature(
        encode_master.encoder_le_master_du_lot).parameters[rappel]
    assert parametre.default is None, rappel


def _litteraux_de_code(chemin: Path) -> list[str]:
    """Les chaines qui s'EXECUTENT, docstrings retirees.

    La distinction n'est pas une commodite : ce module explique au long
    pourquoi il n'imprime pas, et une frontiere qui compterait la prose
    punirait la phrase qui l'explique tout en laissant passer un `print` reel.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list) or not corps:
            continue
        premier = corps[0]
        if (isinstance(premier, ast.Expr)
                and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)):
            del corps[0]
    return [noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)]


def test_le_module_de_coeur_n_IMPRIME_pas_et_ne_lit_pas_stdin() -> None:
    """Le contrat qui rend ce module appelable sous une boucle d'evenements.

    Sous `textual`, une ligne imprimee tombe **sous** l'ecran dessine et un
    `stdin.readline()` gele l'interface entiere (`EPIC7-ARB-106`). La mesure
    porte sur l'AST -- donc sur **tous** les chemins, y compris ceux qu'aucun
    scenario n'atteint -- et elle porte son volet symetrique : les memes noms
    existent bel et bien dans l'enveloppe, sans quoi ce comptage serait vert sur
    un depot qui aurait simplement perdu ses invites.
    """
    arbre = ast.parse(MODULE_DE_COEUR.read_text(encoding="utf-8"))
    appels = {noeud.func.id for noeud in ast.walk(arbre)
              if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)}
    assert "print" not in appels
    noms = {noeud.attr for noeud in ast.walk(arbre) if isinstance(noeud, ast.Attribute)}
    for interdit in ("stdin", "stdout", "stderr", "input"):
        assert interdit not in noms, interdit

    # Volet symetrique : l'enveloppe, elle, imprime et lit `stdin`.
    enveloppe = ast.parse(
        (REPO_ROOT / "src" / "mixed_media_utility" / "cli.py").read_text(
            encoding="utf-8"))
    appels_cli = {noeud.func.id for noeud in ast.walk(enveloppe)
                  if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)}
    assert "print" in appels_cli


def test_une_INTERFACE_atteint_le_point_d_entree_sans_importer_cli() -> None:
    """AC 2.1, mesure par un import REEL et non par lecture de source.

    C'est le blocage exact d'`EPIC11-ARB-67` : la TUI a interdiction d'importer
    `cli.py`, donc le point d'entree doit etre atteignable sans lui. Un
    sous-processus neuf est le seul montage qui le prouve -- dans celui du banc,
    `cli` est deja importe par les autres tests de ce fichier, et `sys.modules`
    ne dirait plus rien.
    """
    programme = (
        "import sys\n"
        "from mixed_media_utility import encode_master\n"
        "assert callable(encode_master.encoder_le_master_du_lot)\n"
        "assert callable(encode_master.ouvrir_le_journal)\n"
        "charges = sorted(m for m in sys.modules\n"
        "                 if m.startswith('mixed_media_utility'))\n"
        "assert 'mixed_media_utility.cli' not in charges, charges\n"
        "print('ok')\n"
    )
    acheve = subprocess.run(
        [sys.executable, "-c", programme],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")})
    assert acheve.returncode == 0, acheve.stderr
    assert acheve.stdout.strip() == "ok"


def test_les_deux_noms_de_cli_ne_sont_que_des_ALIAS_du_coeur() -> None:
    """Une seule classe, deux noms -- jamais deux classes.

    Deux classes distinctes feraient qu'un `except` de l'une ne verrait pas
    l'autre : `cli` attraperait son `_EncodeTerminated` la ou le coeur leve le
    sien, et le contrat `143` tomberait en silence d'un cote sur deux.
    """
    assert cli._EncodeTerminated is encode_master.TerminaisonDemandee
    assert cli._terminate_kills_the_encoder is encode_master.le_signal_tue_l_encodeur


# ===========================================================================
# AC 2.4 -- l'ensemble EXACT des mots-cles transmis au coeur
# ===========================================================================

class _EspionDeDecision:
    """Espion pose sur `encode.plan_encode`, vu depuis le point d'entree."""

    def __init__(self) -> None:
        self.positionnels = None
        self.mots_cles = None

    def __call__(self, *args, **kwargs):
        self.positionnels = args
        self.mots_cles = dict(kwargs)
        raise encode_module.EncodeDecisionError(
            encode_module.ENCODE_LOT_ABSENT, "arret volontaire du banc")


def test_l_ensemble_EXACT_des_mots_cles_transmis_a_la_DECISION(
        tmp_path, monkeypatch) -> None:
    """AC 2.4, et la frontiere rougit **dans les deux sens**.

    « Une assertion positive laisse passer toute divergence supplementaire » :
    on mesure l'ensemble, jamais l'appartenance. Un mot-cle qui **apparait**
    fait rougir autant qu'un mot-cle qui **disparait**, et c'est cette
    propriete-la qui rend reversible le retrait du nom de master
    (`EPIC11-ARB-141`) : le jour ou `plan_encode` gagnera ce parametre, ce test
    le dira au lieu de laisser l'ecart redevenir invisible.
    """
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDeDecision()
    monkeypatch.setattr(encode_module, "plan_encode", espion)

    with pytest.raises(encode_module.EncodeDecisionError):
        encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)

    # Temoin : sans lui, un espion jamais appele rendrait deux ensembles vides,
    # et l'egalite serait verte sur un point d'entree qui n'appelle plus rien.
    assert espion.mots_cles is not None
    assert set(espion.mots_cles) == set(encode_master.MOTS_CLES_DE_LA_DECISION), (
        sorted(set(espion.mots_cles) ^ set(encode_master.MOTS_CLES_DE_LA_DECISION)))
    # Les deux positionnels sont le projet et le manifest **deja valide** : le
    # relire dans la decision ferait juger sur un document different de celui
    # que les gardes ont accepte.
    assert len(espion.positionnels) == 2
    assert espion.positionnels[0] == Path(projet)
    assert espion.positionnels[1]["schema_version"]


#: Une valeur DISTINCTE de son defaut pour chacun des huit mots-cles. Chacune
#: doit differer du defaut de `encoder_le_master_du_lot` : substituer un
#: mot-cle par son defaut est exactement le mutant qui survivait, et une valeur
#: egale au defaut le laisserait survivre encore.
VALEURS_DISTINCTES_DE_LA_DECISION = {
    "lot_id": LOT,
    "profile_id": "profil-temoin-de-ce-banc",
    "resolution": "resolution-temoin-de-ce-banc",
    "overwrite": True,
    "nouvelle_version": True,
    "accept_incomplete": True,
    "cadence_source_override": "25/3",
    "reconstruction_visee": 2,
}


def test_CHAQUE_VALEUR_transmise_a_la_DECISION_arrive_VERBATIM(
        tmp_path, monkeypatch) -> None:
    """Finding R1 de la revue en trois couches de la 6.8 (2026-09-03).

    **Le defaut, et il etait invisible par construction.** Le test voisin
    mesure l'ensemble des **noms** de mots-cles vus par l'espion. Il ne peut
    structurellement pas voir une **valeur** substituee : le mutant
    `reconstruction_visee=reconstruction_visee` -> `=None` -- le mot-cle
    restant transmis -- survivait a 73 tests, dossier d'identite compris,
    pendant que le mutant symetrique (retrait de la ligne) etait bien tue.
    C'est ce mutant symetrique qui rendait celui-ci invisible : on croyait la
    ligne mesuree.

    **La panne.** L'atelier Exports est le seul consommateur nomme de la story.
    L'operateur demande la passe 2, le coeur encode la 3, `render_summary`
    n'emet rien (le champ est vide), et la dette de provenance
    d'`encoded_masters[]` rend le resultat indetectable a posteriori : la story
    pouvait etre entierement inoperante chez son unique consommateur sans qu'un
    seul banc ne rougisse.

    **La mesure porte sur les HUIT mots-cles et non sur le seul fautif** : le
    defaut n'est pas propre a `reconstruction_visee`, il est propre a une
    frontiere qui lit des noms. Un dictionnaire compare en bloc rougit dans les
    deux sens -- valeur substituee, mot-cle apparu, mot-cle disparu.
    """
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDeDecision()
    monkeypatch.setattr(encode_module, "plan_encode", espion)

    # TEMOIN de couverture : la table ci-dessus couvre l'ensemble EXACT des
    # mots-cles. Sans lui, un mot-cle ajoute demain a la decision echapperait
    # en silence a la mesure des valeurs -- le defaut d'aujourd'hui, refait.
    assert set(VALEURS_DISTINCTES_DE_LA_DECISION) == set(
        encode_master.MOTS_CLES_DE_LA_DECISION)

    with pytest.raises(encode_module.EncodeDecisionError):
        encode_master.encoder_le_master_du_lot(
            projet, **VALEURS_DISTINCTES_DE_LA_DECISION)

    assert espion.mots_cles == VALEURS_DISTINCTES_DE_LA_DECISION

    # TEMOIN de discrimination : chaque valeur differe bien du defaut de la
    # signature, sans quoi une substitution par le defaut resterait verte.
    defauts = inspect.signature(encode_master.encoder_le_master_du_lot).parameters
    for mot, valeur in VALEURS_DISTINCTES_DE_LA_DECISION.items():
        if mot == "lot_id":  # sans defaut : il est requis
            continue
        assert valeur != defauts[mot].default, mot


def test_AUCUN_mot_cle_de_NOM_de_master_n_atteint_le_coeur() -> None:
    """`EPIC11-ARB-141`, la moitie **negative** de l'AC 2.4.

    L'arbitrage retire l'edition des noms partout ou elle ne peut pas etre
    effective. Ici elle ne le peut pas : `plan_encode` n'a aucun parametre de
    nom, un master etant nomme par `io.naming`. Le comptage est a **zero** sur
    l'ensemble transmis, avec son volet symetrique -- la constante nomme bien
    des mots-cles que `plan_encode` accepte reellement, sans quoi elle pourrait
    nommer n'importe quoi et ce comptage resterait vert.
    """
    for mot in encode_master.MOTS_CLES_DE_LA_DECISION:
        assert "nom" not in mot and "name" not in mot and "master" not in mot, mot

    acceptes = set(inspect.signature(encode_module.plan_encode).parameters)
    manquants = sorted(encode_master.MOTS_CLES_DE_LA_DECISION - acceptes)
    assert manquants == [], manquants


class _EspionDExecution:
    """Espion pose sur `encode.execute_plan`."""

    def __init__(self) -> None:
        self.positionnels = None
        self.mots_cles = None

    def __call__(self, *args, **kwargs):
        self.positionnels = args
        self.mots_cles = dict(kwargs)
        raise codec_profiles.EncodeError("arret volontaire du banc")


def test_l_ensemble_EXACT_des_mots_cles_transmis_a_l_EXECUTION(
        tmp_path, monkeypatch) -> None:
    """L'autre moitie du cablage, mesuree de la meme facon.

    Le plan en positionnel, et **exactement deux** mots-cles. Un `ffprobe_bin`
    qui apparaitrait ici serait un parametre que personne n'employait -- une
    reecriture, pas un deplacement --, et c'est pour ca que la mesure est une
    egalite d'ensemble et non une appartenance.

    **`rappel_progression` est arrive avec la story 6.7**, et son passage par
    cette frontiere est le signal attendu : c'est le canal de progression qui
    traverse `encoder_le_master_du_lot` -> `execute_plan` -> `run_encode`. La
    frontiere a fait exactement ce qu'on lui demande -- signaler qu'un mot-cle
    de plus circule -- et elle continue a interdire le troisieme.

    Le volet qui compte, et qui n'existait pas avant : **la valeur transmise
    est celle que l'appelant a donnee**, pas un rappel refabrique en route. Un
    canal qui perdrait le rappel en chemin laisserait cette egalite d'ensemble
    verte tout en n'observant plus rien.
    """
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDExecution()
    monkeypatch.setattr(encode_module, "execute_plan", espion)

    def rappel_de_l_appelant(faites, total):
        """Un appelable DISTINGUABLE : son identite est ce qu'on mesure."""

    with pytest.raises(codec_profiles.EncodeError):
        encode_master.encoder_le_master_du_lot(
            projet, lot_id=LOT, rappel_progression=rappel_de_l_appelant)

    assert espion.mots_cles is not None
    assert set(espion.mots_cles) == {"swept", "rappel_progression"}
    assert espion.mots_cles["rappel_progression"] is rappel_de_l_appelant
    assert len(espion.positionnels) == 1
    assert isinstance(espion.positionnels[0], encode_module.EncodePlan)


def test_le_rappel_ABSENT_traverse_quand_meme_en_valant_None(
        tmp_path, monkeypatch) -> None:
    """Volet symetrique : le repli `AR3` passe par le meme chemin.

    Sans rappel, le mot-cle est **toujours** transmis -- il vaut `None`. Une
    transmission conditionnelle serait une seconde redaction du repli, la ou
    `EmetteurProgression` le porte deja : c'est lui, et lui seul, qui decide
    qu'un canal sans rappel est inactif.
    """
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDExecution()
    monkeypatch.setattr(encode_module, "execute_plan", espion)

    with pytest.raises(codec_profiles.EncodeError):
        encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)

    assert set(espion.mots_cles) == {"swept", "rappel_progression"}
    assert espion.mots_cles["rappel_progression"] is None


class _EspionDuCoeur:
    """Espion pose sur `encode_master.encoder_le_master_du_lot`, vu de `cli`."""

    def __init__(self) -> None:
        self.positionnels = None
        self.mots_cles = None

    def __call__(self, *args, **kwargs):
        self.positionnels = args
        self.mots_cles = dict(kwargs)
        raise encode_master.RefusDOuvertureDuProjet("arret volontaire du banc")


#: L'ensemble **EXACT** des mots-cles que l'ENVELOPPE transmet au point
#: d'entree. Il mesure deux choses a la fois, et la seconde est celle qui
#: compte :
#:
#: * ce qui part **part** -- les six reglages d'`args`, le journal sans lequel
#:   `logs/encode.log` s'arreterait, et les trois rappels sans lesquels la
#:   commande deviendrait muette et n'aurait plus d'invite ;
#: * ce qui **ne part pas** : aucun nom de master, aucun `ffprobe_bin`.
#:
#: **`nouvelle_version` est entre le 2026-09-03, et cette frontiere l'a fait
#: entrer.** Le commentaire d'origine disait, ecrit par le lot B1 lui-meme :
#: « aucun `nouvelle_version` -- ce dernier appartient au lot B0, qui n'est pas
#: ouvert. Le jour ou il le sera, cette frontiere rougira, et c'est ce qu'on lui
#: demande. » B0 et B1 ont ete developpes en parallele, chacun dans son worktree,
#: et la fusion a trois voies n'a leve **aucun** conflit : les deux lots editent
#: des regions differentes de `cli.py`. Le resultat passait
#: `nouvelle_version=args.nouvelle_version` a un point d'entree qui ne l'acceptait
#: pas -- un `TypeError` sur **tout** `mmu encode`, pas seulement avec l'option.
#: La frontiere a rougi le jour meme, comme annonce, et c'est la seule chose qui
#: ait vu la couture : aucun conflit git, aucun banc de comportement.
MOTS_CLES_TRANSMIS_AU_COEUR = {
    "lot_id", "profile_id", "resolution", "overwrite", "nouvelle_version",
    "accept_incomplete",
    "cadence_source_override", "logger", "annoncer_le_recapitulatif",
    "confirmer_l_encodage", "annoncer_le_master",
}


def test_l_ensemble_EXACT_des_mots_cles_que_la_COMMANDE_passe_au_COEUR(
        tmp_path, monkeypatch) -> None:
    """AC 2.4 vue depuis l'enveloppe, et dans les deux sens elle aussi."""
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDuCoeur()
    monkeypatch.setattr(encode_master, "encoder_le_master_du_lot", espion)

    assert cli.main(["encode", "--project", str(projet), "--lot", LOT,
                     "--yes"]) == encode_master.CODE_ERREUR

    assert espion.mots_cles is not None
    assert set(espion.mots_cles) == MOTS_CLES_TRANSMIS_AU_COEUR, sorted(
        set(espion.mots_cles) ^ MOTS_CLES_TRANSMIS_AU_COEUR)
    assert espion.positionnels == (Path(projet),)
    # Les six reglages sont ceux d'`args`, pas des valeurs par defaut recopiees.
    assert espion.mots_cles["lot_id"] == LOT
    assert espion.mots_cles["profile_id"] == codec_profiles.DEFAULT_PROFILE_ID
    assert espion.mots_cles["overwrite"] is False
    assert espion.mots_cles["accept_incomplete"] is False


def test_les_reglages_de_la_ligne_de_commande_atteignent_le_coeur_TELS_QUELS(
        tmp_path, monkeypatch) -> None:
    """Volet symetrique du precedent : les valeurs **non par defaut** passent.

    Sans lui, une enveloppe qui poserait six constantes au lieu de lire `args`
    rendrait le meme ensemble de mots-cles et le test ci-dessus resterait vert.
    """
    projet, _ = scanned_project(tmp_path)
    espion = _EspionDuCoeur()
    monkeypatch.setattr(encode_master, "encoder_le_master_du_lot", espion)

    cli.main(["encode", "--project", str(projet), "--lot", LOT, "--yes",
              "--profile", "prores_lt", "--resolution", "native",
              "--overwrite", "--accept-incomplete-lot",
              "--cadence-source", "25/3"])

    assert espion.mots_cles["profile_id"] == "prores_lt"
    assert espion.mots_cles["resolution"] == "native"
    assert espion.mots_cles["overwrite"] is True
    assert espion.mots_cles["accept_incomplete"] is True
    # Transmise **telle quelle**, jamais convertie en `float` : `8.333333`
    # retombe sur une fraction proche mais differente de `25/3` (story 3.8).
    assert espion.mots_cles["cadence_source_override"] == "25/3"


# ===========================================================================
# La table des codes de sortie -- LUE, jamais retapee
# ===========================================================================

def test_la_table_des_codes_de_sortie_est_PARCOURUE_en_entier() -> None:
    """Chaque entree rend son code, y compris celles du milieu et de la fin.

    `code_de_sortie` boucle et rend la premiere correspondance : un mutant qui
    rendrait toujours le code de la **premiere** entree survivrait a un test
    mono-entree, et un mutant `break` premature survivrait a un test qui ne
    regarderait que le debut. La table entiere est donc jouee, avec son temoin
    de cardinal -- sans lui, une table videe rendrait zero iteration et le test
    passerait en ne mesurant rien.
    """
    assert len(encode_master.CODES_DE_SORTIE) == 13
    for rang, (famille, attendu) in enumerate(encode_master.CODES_DE_SORTIE):
        instance = _instance_de(famille)
        assert encode_master.code_de_sortie(instance) == attendu, (rang, famille)


def _instance_de(famille: type) -> BaseException:
    """Une instance de `famille`, quel que soit ce que son `__init__` exige.

    Les familles qui demandent plus d'un argument sont nommees une a une : un
    `except` generique fabriquerait `object()` et mesurerait autre chose.
    """
    if famille is encode_module.EncodeVerificationRefused:
        return famille("motif de banc", staged_path=Path("."), report={})
    if famille is encode_module.EncodeDecisionError:
        return famille(encode_module.ENCODE_LOT_ABSENT, "motif de banc")
    return famille("motif de banc")


def test_les_deux_familles_de_PREREQUIS_precedent_bien_leur_classe_de_BASE() -> None:
    """L'ordre de la table est l'AC, et il se mesure sur la HIERARCHIE.

    `EncoderUnavailableError` et `ProbeUnavailableError` derivent d'`EncodeError`
    (volet symetrique : sans cette verification, l'ordre n'aurait aucune
    importance et ce test ne mesurerait rien). Placees apres elle, elles
    rendraient `1` au lieu de `2` -- « prerequis externe absent » deviendrait
    « erreur de traitement », et l'operateur chercherait un defaut de projet la
    ou il lui manque un encodeur.
    """
    assert issubclass(codec_profiles.EncoderUnavailableError, codec_profiles.EncodeError)
    assert issubclass(codec_profiles.ProbeUnavailableError, codec_profiles.EncodeError)
    familles = [famille for famille, _ in encode_master.CODES_DE_SORTIE]
    for prerequis in (codec_profiles.EncoderUnavailableError,
                      codec_profiles.ProbeUnavailableError):
        assert familles.index(prerequis) < familles.index(codec_profiles.EncodeError)


def test_une_exception_HORS_table_ne_recoit_aucun_code() -> None:
    """`None`, jamais `1` : la deguiser ferait passer un defaut de
    programmation pour un refus opposable a l'operateur (`EPIC11-ARB-75`)."""
    assert encode_master.code_de_sortie(ZeroDivisionError("defaut")) is None
    # `OSError` NUE en fait partie, et c'est la mesure : une `OSError` de la
    # phase de DECISION remontait en trace Python avant le deplacement, et doit
    # continuer de le faire. Seule la sous-classe nommee est dans la table.
    assert encode_master.code_de_sortie(OSError("disque")) is None
    assert encode_master.code_de_sortie(
        encode_master.ErreurDeDisquePendantEncodage("disque")) == 1


def test_l_ensemble_des_codes_de_la_table_est_EXACTEMENT_celui_la() -> None:
    """Ensemble **exact**, jamais une inclusion.

    `130` et `143` n'y sont pas, et ce n'est pas un oubli : ils viennent d'une
    interruption, dont seule la sequence connait la phase, et
    `EncodageInterrompu` les porte.
    """
    assert {code for _, code in encode_master.CODES_DE_SORTIE} == {1, 2, 3}
    assert encode_master.EncodageInterrompu(
        "m", phase="encodage", par_signal=True).code_de_sortie == 143
    assert encode_master.EncodageInterrompu(
        "m", phase="encodage").code_de_sortie == 130


def test_une_phase_d_interruption_INCONNUE_est_refusee() -> None:
    """L'ensemble des phases est **ferme** : une quatrieme serait un endroit de
    plus ou l'etat laisse sur le disque n'est pas celui que le message annonce."""
    assert encode_master.PHASES == ("decision", "encodage", "persistance")
    with pytest.raises(ValueError):
        encode_master.EncodageInterrompu("m", phase="ailleurs")


# ===========================================================================
# Les rappels -- ce qu'ils changent, et ce qu'ils ne changent pas
# ===========================================================================

def test_sans_AUCUN_rappel_le_master_est_le_MEME_octet_pour_octet(tmp_path) -> None:
    """`AR3` : l'absence de rappel ne change **rien** a l'observable.

    Deux projets identiques, deux regimes -- muet et bavard --, et le master
    compare **octet a octet**, pas seulement en taille. C'est le regime d'une
    interface qui appelle le coeur sans terminal, et c'est celui du lot B5.
    """
    muet, _ = scanned_project(tmp_path, name="muet")
    bavard, _ = scanned_project(tmp_path, name="bavard")

    silencieux = encode_master.encoder_le_master_du_lot(muet, lot_id=LOT)

    dits: list = []
    parle = encode_master.encoder_le_master_du_lot(
        bavard, lot_id=LOT,
        annoncer_le_recapitulatif=dits.append,
        confirmer_l_encodage=lambda: (True, "accorde par le banc"),
        annoncer_le_master=lambda resultat: dits.append("master"))

    octets_muet = Path(silencieux.resultat.outcome.output_path).read_bytes()
    octets_parle = Path(parle.resultat.outcome.output_path).read_bytes()
    assert octets_muet == octets_parle
    # Temoin : le regime bavard a bien parle, sans quoi on comparerait deux fois
    # le meme silence.
    assert len(dits) == 2 and dits[1] == "master"
    assert "Recapitulatif de l'encodage" in dits[0]


def test_un_consentement_REFUSE_n_ecrit_RIEN_et_porte_le_message_verbatim(
        tmp_path) -> None:
    """Le motif de la story 3.3 : rien n'a rate, l'operateur a dit non.

    Le message du rappel voyage **verbatim** -- les trois motifs de refus ne
    disent pas la meme chose --, et `outputs/` n'existe pas : c'est la garde
    « un refus qui arrive apres une destruction n'est pas un refus ».
    """
    projet, _ = scanned_project(tmp_path)
    with pytest.raises(encode_master.EncodageNonConsenti) as refus:
        encode_master.encoder_le_master_du_lot(
            projet, lot_id=LOT,
            confirmer_l_encodage=lambda: (False, "motif exact du banc"))
    assert str(refus.value) == "motif exact du banc"
    assert not project_layout.outputs_dir(projet).exists()


def test_annoncer_le_master_est_appele_APRES_la_bascule_et_AVANT_la_declaration(
        tmp_path) -> None:
    """La POSITION du rappel est l'observable, pas un detail de mise en page.

    C'est la seule fenetre ou « Master ecrit » doit etre dit meme si la
    declaration echoue ensuite -- et c'est exactement ce que la commande
    faisait. Le rappel mesure les deux faits au moment ou il est appele : le
    fichier **est** la, et le manifest ne le declare **pas encore**.
    """
    projet, _ = scanned_project(tmp_path)
    constats: list = []

    def _au_moment_ou(resultat):
        chemin = Path(resultat.outcome.output_path)
        lot = next(l for l in load_manifest_dict(projet)["lots"]
                   if l["lot_id"] == LOT)
        constats.append((chemin.is_file(), chemin.stat().st_size,
                         lot.get("encoded_masters"), lot.get("state")))

    master = encode_master.encoder_le_master_du_lot(
        projet, lot_id=LOT, annoncer_le_master=_au_moment_ou)

    assert len(constats) == 1
    existe, taille, masters, etat = constats[0]
    assert existe and taille > 0
    assert masters is None, masters
    assert etat != "encode", etat
    # Et apres, la declaration a bien eu lieu : sans ce volet, le test serait
    # vert sur un point d'entree qui ne declare plus rien.
    apres = next(l for l in load_manifest_dict(projet)["lots"]
                 if l["lot_id"] == LOT)
    assert apres["state"] == "encode"
    assert apres["encoded_masters"]
    assert master.persisted.master_path


def test_le_recapitulatif_part_ENTIER_au_journal_et_dans_l_ORDRE(tmp_path) -> None:
    """La boucle qui journalise le recapitulatif **compte**.

    Un mutant qui la couperait (`break` a la premiere ligne) laisserait
    `logs/encode.log` ampute de quatorze lignes sans qu'aucun code de sortie ne
    bouge. On mesure donc que **toutes** les lignes y sont, et **dans l'ordre**
    -- un ensemble seul ne verrait pas une permutation.
    """
    projet, _ = scanned_project(tmp_path)
    # L'arborescence PRECEDE le journal, et c'est l'ordre du produit :
    # `encode_command` appelle `ensure_project_layout` avant
    # `_configure_encode_logger`, parce qu'un `FileHandler` sur `logs/` qui
    # n'existe pas leve `FileNotFoundError`. Un banc qui l'ignorerait mesurerait
    # une panne de banc, pas une propriete du produit.
    project_layout.ensure_project_layout(projet)
    journal = encode_master.ouvrir_le_journal(projet)
    try:
        master = encode_master.encoder_le_master_du_lot(
            projet, lot_id=LOT, logger=journal)
    finally:
        for handler in journal.handlers[:]:
            handler.flush()
            handler.close()
            journal.removeHandler(handler)

    lignes = (projet / project_layout.LOGS_DIRNAME / "encode.log").read_text(
        encoding="utf-8").splitlines()
    messages = [ligne.split("] ", 1)[-1] for ligne in lignes]
    attendues = master.recapitulatif.splitlines()
    assert len(attendues) > 10, len(attendues)
    debut = messages.index(attendues[0])
    assert messages[debut:debut + len(attendues)] == attendues


def _poser_un_residu(dossier: Path, nom: str) -> Path:
    """Un residu d'encodage tue : cache, nom de temporaire, vieux de deux jours.

    Les trois criteres sont ceux de `codec_profiles.sweep_encode_residues`, et
    ils sont poses ici plutot que devines : un fichier qui n'en remplirait qu'un
    ne serait pas balaye, et le banc mesurerait un balayage qui n'a pas eu lieu.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f".{nom}.4242-0123456789ab.mov"
    chemin.write_bytes(b"residu du banc")
    vieux = time.time() - 2 * 86400
    os.utime(chemin, (vieux, vieux))
    return chemin


def test_les_TROIS_residus_balayes_sont_journalises_la_CIBLE_AU_MILIEU(
        tmp_path) -> None:
    """La regle des fabriques, point 2 bis, sur la boucle qui journalise.

    **Trois** residus et la cible **au milieu** : a deux elements, la cible en
    second est aussi la derniere, et un mutant `continue` -> `break` y est
    indiscernable. Au milieu, il fait disparaitre le troisieme **en silence** --
    ni erreur, ni code de sortie different, juste un journal incomplet.

    Les trois noms sont **distinguables** : trois residus au meme nom
    laisseraient une inversion d'appariement invisible.
    """
    projet, _ = scanned_project(tmp_path)
    project_layout.ensure_project_layout(projet)
    sorties = project_layout.outputs_dir(projet)
    poses = [_poser_un_residu(sorties, nom)
             for nom in ("premier", "cible-du-milieu", "dernier")]

    journal = encode_master.ouvrir_le_journal(projet)
    try:
        master = encode_master.encoder_le_master_du_lot(
            projet, lot_id=LOT, logger=journal)
    finally:
        for handler in journal.handlers[:]:
            handler.flush()
            handler.close()
            journal.removeHandler(handler)

    texte = (projet / project_layout.LOGS_DIRNAME / "encode.log").read_text(
        encoding="utf-8")
    for chemin in poses:
        assert f"Residu d'encodage balaye: {chemin}" in texte, chemin.name
        assert not chemin.exists(), chemin.name
    assert encode_module.ENCODE_RESIDUES_SWEPT in master.resultat.findings


# ===========================================================================
# Les deux gardes d'ouverture -- avant le journal, et sans rien creer
# ===========================================================================

def test_un_projet_INEXISTANT_est_refuse_sans_rien_creer(tmp_path) -> None:
    """La garde precede le journal, et l'observable est le DISQUE.

    `mmu encode --project <inexistant>` n'a jamais cree ni arborescence, ni
    `logs/encode.log`. Le mesurer par l'absence du dossier est plus fort que par
    le message : un refus qui creerait `logs/` avant de refuser passerait un
    test de message.
    """
    absent = tmp_path / "jamais-cree"
    with pytest.raises(encode_master.RefusDOuvertureDuProjet) as refus:
        encode_master.encoder_le_master_du_lot(absent, lot_id=LOT)
    assert "n'existe pas" in str(refus.value)
    assert not absent.exists()


def test_un_projet_SANS_manifest_est_refuse_sans_ouvrir_de_journal(tmp_path) -> None:
    """Volet symetrique : le dossier existe, le manifest non."""
    projet = tmp_path / "vide"
    projet.mkdir()
    with pytest.raises(encode_master.RefusDOuvertureDuProjet) as refus:
        encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)
    assert "Aucun manifest" in str(refus.value)
    assert not (projet / project_layout.LOGS_DIRNAME).exists()
    assert sorted(p.name for p in projet.iterdir()) == []


def test_le_master_produit_par_le_COEUR_porte_ce_que_la_commande_declarait(
        tmp_path) -> None:
    """Le produit fini, relu dans le FICHIER et non dans l'objet qui le decrit.

    C'est la lecon de la story 6.0 -- « aucun test ne regardait le produit
    fini » -- transposee au point d'entree : cardinal, geometrie, cadence et
    format de pixel sont relus par `ffprobe`.
    """
    projet, _ = scanned_project(tmp_path)
    master = encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)

    chemin = Path(master.resultat.outcome.output_path)
    assert chemin.is_file()
    sonde = video_metadata.probe_media(str(chemin))
    flux = next(s for s in sonde["streams"] if s.get("codec_type") == "video")
    assert (flux["width"], flux["height"]) == master.resultat.outcome.encoded_size
    assert flux["pix_fmt"] == master.resultat.outcome.pix_fmt
    assert int(flux["nb_frames"]) == len(master.resultat.plan.muxed_frame_paths)


# ===========================================================================
# C2-1 -- les DEUX interruptions de la phase de persistance, en PAIRE
# ===========================================================================
#
# Le defaut ferme ici : `le_signal_tue_l_encodeur` n'enveloppait que
# `execute_plan`. Quand `persist_encode` tournait, le gestionnaire etait deja
# restaure au defaut, si bien qu'un `SIGTERM` a cet instant tuait le process
# net -- aucun message, aucune entree de journal --, la ou un `Ctrl-C` a la
# meme milliseconde rendait un constat nomme. Deux fenetres de meme nature, une
# seule tenue, et le contrat `:raises` du module annoncait les deux.
#
# **La paire est le test**, et une seule de ses deux moities ne mesurerait
# rien : c'est l'ASYMETRIE qui etait le defaut, pas l'absence d'un cas. Un test
# du seul `SIGTERM` serait vert le jour ou quelqu'un retirerait le rattrapage
# du clavier, et l'atelier retomberait dans l'etat d'avant par l'autre bout.


def _persistance_qui_leve(monkeypatch, exception: BaseException) -> None:
    """Faire lever la phase 3, sans encoder pour de vrai.

    `from_command_result` est neutralise **aussi**, et pas par confort : c'est
    un argument de `persist_encode`, donc il s'evalue AVANT elle. Sans ce
    neutre, le test mesurerait la fabrique du releve plutot que la fenetre
    d'interruption qu'il vise.
    """
    def _leve(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(encode_master.encode_manifest, "persist_encode", _leve)
    monkeypatch.setattr(
        encode_master.encode_manifest.EncodeRecord, "from_command_result",
        staticmethod(lambda _resultat: None))


@pytest.mark.parametrize("leve,par_signal,code,mot", [
    (KeyboardInterrupt(), False, 130, "interruption clavier"),
    (encode_master.TerminaisonDemandee("signal 15"), True, 143,
     "arret demande (SIGTERM)"),
])
def test_les_DEUX_interruptions_de_la_PERSISTANCE_rendent_le_meme_constat(
        tmp_path, monkeypatch, leve, par_signal, code, mot) -> None:
    """Meme phase, meme etat laisse sur le disque, deux origines DISTINGUEES.

    Ce que le constat doit dire est le meme des deux cotes -- le manifeste est
    intact, le master est ecrit et **non declare** -- et ce qu'il doit
    distinguer est l'origine : un operateur qui lit `INTERRUPTION_CLAVIER`
    apres un `kill -TERM` chercherait un clavier que personne n'a touche.
    """
    projet, _ = scanned_project(tmp_path)
    _persistance_qui_leve(monkeypatch, leve)

    with pytest.raises(encode_master.EncodageInterrompu) as capture:
        encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)

    refus = capture.value
    assert refus.phase == "persistance"
    assert refus.par_signal is par_signal
    assert refus.code_de_sortie == code
    assert mot in str(refus)
    # Ce que les deux constats partagent, et qui est l'etat REEL du disque.
    assert "n'est **pas** declare" in str(refus)


def test_le_gestionnaire_de_SIGTERM_est_POSE_PENDANT_l_ecriture_du_manifest(
        tmp_path, monkeypatch) -> None:
    """Le volet que le test en paire ci-dessus ne mesure PAS, et il l'a prouve.

    **Mesure d'abord, regle ensuite** : retirer le `with
    le_signal_tue_l_encodeur():` autour de la phase 3 laissait la paire
    ci-dessus **verte**. C'est logique et c'etait invisible -- elle leve
    `TerminaisonDemandee` comme une exception Python ordinaire, donc elle
    mesure le RATTRAPAGE et jamais la conversion du signal en exception. Le
    contexte etait une surface posee sans frontiere ; sans ce test, le
    correctif de C2-1 aurait pu etre a moitie retire sans qu'aucun banc ne le
    dise.

    **Et il ne s'envoie pas de vrai signal**, deliberement : sans gestionnaire
    pose, `SIGTERM` tue le process, c'est-a-dire le worker pytest et les
    milliers de tests qu'il porte. Un banc dont le rouge emporte la course
    n'est pas un banc. Ce qui se lit sans rien tuer, c'est la **disposition**
    du signal au moment ou la phase 3 s'execute -- et c'est exactement la
    propriete que le contexte promet.
    """
    projet, _ = scanned_project(tmp_path)
    releve: dict = {}
    avant = signal.getsignal(signal.SIGTERM)

    def _persister(*_args, **_kwargs):
        releve["pendant"] = signal.getsignal(signal.SIGTERM)
        raise KeyboardInterrupt

    monkeypatch.setattr(encode_master.encode_manifest, "persist_encode",
                        _persister)
    monkeypatch.setattr(
        encode_master.encode_manifest.EncodeRecord, "from_command_result",
        staticmethod(lambda _resultat: None))

    with pytest.raises(encode_master.EncodageInterrompu):
        encode_master.encoder_le_master_du_lot(projet, lot_id=LOT)

    # Temoin : sans lui, un `persist_encode` jamais appele rendrait un releve
    # vide et l'inegalite serait verte sur une phase 3 qui n'a pas tourne.
    assert "pendant" in releve
    assert releve["pendant"] is not avant
    # Et la disposition est RENDUE en sortant : une commande qui rend la main
    # ne laisse pas derriere elle un `SIGTERM` detourne.
    assert signal.getsignal(signal.SIGTERM) is avant
