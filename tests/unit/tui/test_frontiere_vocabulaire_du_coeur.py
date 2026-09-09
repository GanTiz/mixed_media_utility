# -*- coding: utf-8 -*-
"""Story 11.8, lot B4 (AC 11.2) -- le vocabulaire du coeur ne se RECOPIE pas.

AC 11.2, verbatim : « Aucun litteral de vocabulaire du coeur -- profils,
categories, conteneurs, resolutions, etats de lot, codes de refus -- n'apparait
dans les modules de cet atelier. Chaque frontiere negative est doublee d'un test
**positif** qui prouve qu'elle mesure encore quelque chose. »

## Ce que ce banc mesure, et sur quelle surface

**Le paquet `tui/` entier, par decouverte, et pas les seuls modules de
l'atelier Exports.** Ces modules-la n'existent pas encore -- ils arrivent avec
le lot B5 --, et une frontiere posee sur un ensemble vide est verte sans rien
mesurer : c'est le mode de panne exact que ce lot ferme par ailleurs sur
`MODULES_DE_COEUR`. La surface est donc le paquet, ce qui est **strictement
plus fort** que ce que l'AC demande, et les ecrans de l'atelier y entreront
sans qu'une ligne de ce banc change.
:func:`test_un_ecran_de_l_atelier_EXPORTS_serait_bien_MESURE` mesure cette
promesse plutot que de la formuler.

**Le vocabulaire est LU du coeur, jamais recopie ici.** C'est la regle que
`CLAUDE.md` s'est donnee apres trois corrections successives d'un meme nombre :
« un document de politique ne recopie jamais une valeur qui vit dans le code, il
**nomme la constante** et dit ou elle habite ». Un banc de frontiere est dans le
meme cas : une liste de profils recopiee ici cesserait de mesurer le jour ou le
coeur en ajoute un, **sans rougir**. Les six familles sont donc lues de
`codec_profiles`, d'`encode` et d'`io.manifest`, et les volets symetriques sont
parametres sur les valeurs reelles -- renommer `prores_hq` dans le coeur
deplace la mesure avec lui.

## Deux regimes, parce que le vocabulaire n'est pas d'une seule sorte

**Regime A -- la PRESENCE.** Profils, resolutions et codes de refus. Aucun de
ces mots n'a d'homonyme : `prores_hq`, `uhd2160`, `MASTER_DEJA_PRESENT` ne
veulent dire qu'une chose dans ce depot. Le litteral est interdit, point.

**Regime B -- le JUGEMENT.** Categories, conteneurs et etats de lot. Ces
mots-la ont des homonymes hors du coeur : `"primary"` est aussi une variante de
bouton `textual`, `"mov"` et `"mp4"` sont aussi des extensions de fichier
ordinaires, et `CHAMP_SCAN = "scan"` est deja, dans `atelier_scan_calibrate.py`,
un identifiant de champ de formulaire. Interdire leur presence ferait rougir des
sites legitimes ; ce qui est fautif est de **decider** dessus. La mesure porte
donc sur la forme -- une collection litterale, ou une comparaison -- exactement
comme `test_frontiere_vocabulaire_d_etat.py` le fait deja pour les etats.

**Et les deux predicats sont CONFRONTES plutot que laisses diverger** :
:func:`test_le_predicat_de_jugement_S_ACCORDE_avec_celui_des_etats` rejoue le
catalogue du banc voisin sur celui-ci. « Deux predicats pour un seul interdit
divergeraient, et c'est le module non couvert par le plus strict des deux qui
passerait » -- la remarque est de `test_frontiere_cli.py`, elle vaut ici.

## Ce que ce banc NE mesure PAS, dit plutot que tu

* un vocabulaire **reconstruit** sans litteral -- `sorted(PROFILES)[0]` --, qui
  est d'ailleurs la bonne facon de faire et n'a pas a rougir ;
* une valeur du coeur assemblee morceau par morceau (`"prores" + "_hq"`). C'est
  le prix d'une mesure syntaxique, le meme que paie la frontiere des politiques
  de `CLAUDE.md` face a une regle sans identifiant, et il se dit ;
* le vocabulaire des **autres** ateliers (scan, pdf, extraction) : les six
  familles sont celles que l'AC 11.2 nomme, c'est-a-dire celles de l'atelier
  Exports.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from outils_frontiere import chaines_de_code

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import codec_profiles, encode  # noqa: E402
from mixed_media_utility.io.manifest import LOT_STATES  # noqa: E402

PAQUET_TUI = _RACINE / "src" / "mixed_media_utility" / "tui"


def _codes_de_refus() -> frozenset[str]:
    """Les codes de refus d'`encode`, **par decouverte** et non par recopie.

    `ENCODE_REFUSAL_CODES` n'en porte qu'une partie -- le tuple sert au
    classement des refus de la commande, et plusieurs codes vivent hors de lui.
    On prend donc toute constante publique `ENCODE_*` de valeur textuelle : le
    code de refus ajoute demain entre dans la frontiere le jour ou il est ecrit,
    sans qu'aucune story ait a le nommer.
    """
    return frozenset(valeur for nom, valeur in vars(encode).items()
                     if nom.startswith("ENCODE_") and isinstance(valeur, str))


#: **Regime A** : les familles sans homonyme. Le litteral y est interdit.
VOCABULAIRE_DE_PRESENCE: dict[str, frozenset[str]] = {
    "profil": frozenset(codec_profiles.PROFILES)
              | {codec_profiles.DEFAULT_PROFILE_ID},
    "resolution": frozenset(encode.known_resolution_ids())
                  | {encode.DEFAULT_RESOLUTION_ID,
                     encode.NATIVE_RESOLUTION_KEYWORD},
    "code de refus": _codes_de_refus(),
}

#: **Regime B** : les familles a homonymes. Seul le **jugement** est interdit.
VOCABULAIRE_DE_JUGEMENT: dict[str, frozenset[str]] = {
    "categorie de profil": frozenset(profil.category for profil
                                     in codec_profiles.PROFILES.values()),
    "conteneur": frozenset(codec_profiles.CONTAINER_MUXERS),
    "etat de lot": frozenset(LOT_STATES),
}

#: Plancher de cardinal par famille. Une famille vide rendrait sa frontiere
#: verte sans rien mesurer -- c'est le meme mode de panne que la liste de
#: modules oubliee, par une autre porte.
PLANCHERS = {
    "profil": 5, "resolution": 3, "code de refus": 20,
    "categorie de profil": 2, "conteneur": 2, "etat de lot": 4,
}


def modules_de_la_tui(racine: Path = PAQUET_TUI) -> list[Path]:
    """Le paquet, par decouverte. Les ecrans de B5 y entreront tout seuls."""
    return sorted(racine.rglob("*.py"))


# ---------------------------------------------------------------------------
# Les deux predicats
# ---------------------------------------------------------------------------


def sites_de_presence(source: str, mots: frozenset[str],
                      nom: str = "<source>") -> list[str]:
    """Les endroits ou ce source **ecrit** un mot du vocabulaire en litteral.

    Docstrings exclus par :func:`chaines_de_code` : la prose qui explique
    pourquoi un module ne recopie pas un profil porte forcement son nom, et un
    grep de texte s'y ferait affaiblir des la premiere explication.
    """
    return [f"{nom}: litteral {valeur!r}"
            for valeur in chaines_de_code_de(source, nom) if valeur in mots]


def chaines_de_code_de(source: str, nom: str) -> list[str]:
    """:func:`chaines_de_code`, mais sur une source en memoire.

    Le detour par un fichier temporaire serait le seul autre moyen d'exercer le
    volet symetrique, et il rendrait les volets illisibles.
    """
    arbre = ast.parse(source, filename=nom)
    docstrings = set()
    porteurs = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, porteurs):
            continue
        corps = getattr(noeud, "body", [])
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            docstrings.add(id(corps[0].value))
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def sites_de_jugement(source: str, mots: frozenset[str],
                      nom: str = "<source>") -> list[str]:
    """Les endroits ou ce source **juge** sur un mot du vocabulaire.

    Deux formes, et ce sont celles du banc voisin, reprises a l'identique parce
    que l'interdit est le meme :

    1. une **collection litterale** dont un element est du vocabulaire ;
    2. une **comparaison** contre un litteral du vocabulaire.

    Un mot passe en **argument** n'est pas un jugement : demander au coeur
    combien de lots ont atteint `"pdf"`, c'est le laisser juger.
    """
    arbre = ast.parse(source, filename=nom)
    sites: list[str] = []

    def _est_du_vocabulaire(noeud: ast.AST) -> bool:
        return (isinstance(noeud, ast.Constant)
                and isinstance(noeud.value, str) and noeud.value in mots)

    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Tuple, ast.List, ast.Set)):
            trouves = [e.value for e in noeud.elts if _est_du_vocabulaire(e)]
            if trouves:
                sites.append(f"{nom}:{noeud.lineno} collection {trouves}")
        elif isinstance(noeud, ast.Compare):
            trouves = [c.value for c in noeud.comparators
                       if _est_du_vocabulaire(c)]
            if trouves:
                sites.append(f"{nom}:{noeud.lineno} comparaison a {trouves}")
    return sites


def _sites_du_paquet(predicat, mots: frozenset[str],
                     racine: Path = PAQUET_TUI) -> list[str]:
    return [site for chemin in modules_de_la_tui(racine)
            for site in predicat(chemin.read_text(encoding="utf-8"), mots,
                                 chemin.name)]


# ---------------------------------------------------------------------------
# AC 11.2 -- les frontieres negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("famille", sorted(VOCABULAIRE_DE_PRESENCE))
def test_le_paquet_tui_ne_RECOPIE_aucun_litteral_du_coeur(famille):
    """Regime A. **Tolerance zero**, sur le paquet entier.

    Une liste d'exceptions serait le premier pas vers une seconde redaction du
    vocabulaire : le jour ou elle en porterait une, plus personne ne saurait
    dire si la TUI lit le coeur ou le repete.
    """
    trouves = _sites_du_paquet(sites_de_presence,
                               VOCABULAIRE_DE_PRESENCE[famille])
    assert trouves == [], trouves


@pytest.mark.parametrize("famille", sorted(VOCABULAIRE_DE_JUGEMENT))
def test_le_paquet_tui_ne_JUGE_sur_aucun_mot_du_coeur(famille):
    """Regime B. Le mot peut traverser ; la decision, non."""
    trouves = _sites_du_paquet(sites_de_jugement,
                               VOCABULAIRE_DE_JUGEMENT[famille])
    assert trouves == [], trouves


# ---------------------------------------------------------------------------
# AC 11.2 -- les volets POSITIFS, un par frontiere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("famille", sorted(PLANCHERS))
def test_chaque_famille_de_vocabulaire_est_LUE_du_coeur_et_NON_VIDE(famille):
    """Le volet le plus important : la frontiere a bien quelque chose a chercher.

    Un renommage dans le coeur -- `PROFILES` qui devient `PROFILS`, un import
    circulaire qui rend le module a moitie initialise -- viderait la famille et
    rendrait sa frontiere verte pour toujours. Le plancher est ce qui l'attrape.
    """
    mots = dict(VOCABULAIRE_DE_PRESENCE, **VOCABULAIRE_DE_JUGEMENT)[famille]
    assert len(mots) >= PLANCHERS[famille], sorted(mots)
    assert all(isinstance(mot, str) and mot for mot in mots), sorted(mots)


@pytest.mark.parametrize("famille,mot", sorted(
    (famille, mot) for famille, mots in VOCABULAIRE_DE_PRESENCE.items()
    for mot in mots))
def test_la_frontiere_de_PRESENCE_MORD_sur_chaque_mot_reel(famille, mot):
    """Volet symetrique du regime A, **sur les valeurs reelles du coeur**.

    Parametre sur le vocabulaire lui-meme et non sur un exemple ecrit a la
    main : renommer `prores_hq` dans le coeur deplace la mesure avec lui, la ou
    un exemple recopie mesurerait pour toujours un mot que plus personne
    n'emploie.
    """
    mots = VOCABULAIRE_DE_PRESENCE[famille]
    assert sites_de_presence(f"CHOIX = {mot!r}\n", mots), mot
    # Le mot est un segment ENTIER de la f-string : colle a un autre texte,
    # il ne serait plus la meme constante, et le volet mesurerait a cote.
    assert sites_de_presence(f"def f(x):\n    return f'{{x}}{mot}'\n",
                             mots), mot


@pytest.mark.parametrize("famille", sorted(VOCABULAIRE_DE_PRESENCE))
def test_la_frontiere_de_PRESENCE_ne_mord_PAS_sur_la_prose(famille):
    """L'autre moitie : ce que le regime A tolere, ecrit.

    C'est la raison pour laquelle la mesure est un AST et non un grep. Le
    module qui explique pourquoi il ne recopie pas un profil porte forcement le
    mot, et il ne doit pas rougir pour l'avoir explique.
    """
    mots = VOCABULAIRE_DE_PRESENCE[famille]
    mot = sorted(mots)[0]
    assert sites_de_presence(f'"""On ne recopie jamais {mot} ici."""\n',
                             mots) == []
    assert sites_de_presence("from mixed_media_utility import codec_profiles\n"
                             "CHOIX = sorted(codec_profiles.PROFILES)[0]\n",
                             mots) == []


@pytest.mark.parametrize("famille,mot", sorted(
    (famille, mot) for famille, mots in VOCABULAIRE_DE_JUGEMENT.items()
    for mot in mots))
def test_la_frontiere_de_JUGEMENT_MORD_sur_chaque_mot_reel(famille, mot):
    """Volet symetrique du regime B, sur les deux formes et sur chaque mot."""
    mots = VOCABULAIRE_DE_JUGEMENT[famille]
    assert sites_de_jugement(f"CONNUS = ({mot!r},)\n", mots), mot
    assert sites_de_jugement(f"def f(v):\n    return v == {mot!r}\n", mots), mot
    assert sites_de_jugement(f"def f(v):\n    return v in [{mot!r}]\n",
                             mots), mot


@pytest.mark.parametrize("famille", sorted(VOCABULAIRE_DE_JUGEMENT))
def test_la_frontiere_de_JUGEMENT_ne_mord_PAS_sur_ce_qu_elle_tolere(famille):
    """Les trois tolerances du regime B, **ecrites** plutot que subies.

    Sans ce volet, un resserrement futur de la mesure ferait rougir des sites
    legitimes du depot sans que rien ne dise qu'ils l'etaient -- et les deux
    premiers existent, aujourd'hui, dans `projets.py` et
    `atelier_scan_calibrate.py`.
    """
    mots = VOCABULAIRE_DE_JUGEMENT[famille]
    mot = sorted(mots)[0]
    assert sites_de_jugement(f"compte = _lots_arrives_a(lots, {mot!r})\n",
                             mots) == []
    assert sites_de_jugement(f"CHAMP = {mot!r}\n", mots) == []
    assert sites_de_jugement(f'"""On ne compare jamais a {mot}."""\n',
                             mots) == []


# ---------------------------------------------------------------------------
# La SURFACE : le paquet entier, et l'atelier qui n'existe pas encore
# ---------------------------------------------------------------------------


def test_le_balayage_a_bien_VU_le_paquet():
    """Volet du volet : une frontiere qui ne lirait aucun fichier serait verte.

    Plancher et non egalite -- le paquet grandit a chaque story --, et deux
    modules nommes : le cardinal seul ne verrait pas un `glob` mis a la place du
    `rglob`.
    """
    modules = modules_de_la_tui()
    assert len(modules) >= 30, [m.name for m in modules]
    assert {"projet_lecture.py", "palier_projet.py"} <= {m.name for m in modules}


def test_un_ecran_de_l_atelier_EXPORTS_serait_bien_MESURE(tmp_path):
    """**La promesse de la surface, mesuree.**

    Les ecrans de l'atelier Exports arrivent avec le lot B5. Ce banc affirme
    qu'ils entreront dans la frontiere sans qu'une ligne change ; l'affirmation
    est verifiee ici en deposant un ecran fautif dans un paquet fabrique, plutot
    que laissee a la relecture. C'est la meme exigence que le lot ferme sur
    `MODULES_DE_COEUR` : une frontiere qui attend d'etre mise a jour n'est pas
    une frontiere.
    """
    paquet = tmp_path / "tui"
    (paquet / "sous_paquet").mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    profil = sorted(VOCABULAIRE_DE_PRESENCE["profil"])[0]
    (paquet / "atelier_exports_reglages.py").write_text(
        f"PROFIL_PAR_DEFAUT = {profil!r}\n", encoding="utf-8")
    conteneur = sorted(VOCABULAIRE_DE_JUGEMENT["conteneur"])[0]
    (paquet / "sous_paquet" / "atelier_exports_resultat.py").write_text(
        f"def f(v):\n    return v == {conteneur!r}\n", encoding="utf-8")

    presence = _sites_du_paquet(sites_de_presence,
                                VOCABULAIRE_DE_PRESENCE["profil"], paquet)
    jugement = _sites_du_paquet(sites_de_jugement,
                                VOCABULAIRE_DE_JUGEMENT["conteneur"], paquet)
    assert len(presence) == 1, presence
    assert len(jugement) == 1, jugement


# ---------------------------------------------------------------------------
# Les deux predicats de jugement du depot, CONFRONTES
# ---------------------------------------------------------------------------


def test_la_lecture_DES_CHAINES_s_accorde_avec_l_outil_du_depot():
    """`chaines_de_code_de` ne doit pas deriver de `chaines_de_code`.

    La seconde vit dans `outils_frontiere` et lit un **fichier** ; la premiere
    lit une **source en memoire**, ce dont les volets symetriques ont besoin.
    C'est deux fois le meme predicat, donc deux fois l'occasion de diverger.
    On les confronte sur tous les modules du paquet plutot que de s'en
    remettre a la relecture.
    """
    desaccords = [chemin.name for chemin in modules_de_la_tui()
                  if chaines_de_code(chemin)
                  != chaines_de_code_de(chemin.read_text(encoding="utf-8"),
                                        chemin.name)]
    assert desaccords == [], desaccords


def test_le_predicat_de_jugement_S_ACCORDE_avec_celui_des_etats():
    """Un seul interdit ne doit pas avoir deux predicats qui divergent.

    `test_frontiere_vocabulaire_d_etat.py` porte le sien depuis le lot B2, avec
    son catalogue de formes fautives et de tolerances. On le rejoue ici, verdict
    contre verdict : le jour ou l'un des deux se resserre sans l'autre, c'est le
    module couvert par le plus laxiste qui passerait, et personne ne le verrait.

    L'import est fait **dans** le test pour que sa disparition rende un rouge
    nomme plutot qu'une erreur de collecte du banc entier.
    """
    from test_frontiere_vocabulaire_d_etat import sites_de_jugement_d_etat

    catalogue = [
        'ETATS_RECONSTRUITS = ("reconstruction", "encode")\n',
        'ENCODABLES = ["scan", "reconstruction"]\n',
        'ENCODABLES = {"encode"}\n',
        'def f(lot):\n    return lot.get("state") in ("reconstruction", "encode")\n',
        'def f(lot):\n    return lot.get("state") == "reconstruction"\n',
        'compte = _lots_arrives_a(lots, "pdf")\n',
        'def f(lot):\n    return lot.get("state") in ETATS_DE_LOT\n',
        'CHAMP_SCAN = "scan"\n',
        '"""On ne compare jamais a "reconstruction" ni a "encode"."""\n',
    ]
    etats = VOCABULAIRE_DE_JUGEMENT["etat de lot"]
    desaccords = [source for source in catalogue
                  if bool(sites_de_jugement(source, etats))
                  != bool(sites_de_jugement_d_etat(source))]
    assert desaccords == [], desaccords
