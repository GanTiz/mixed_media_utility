# -*- coding: utf-8 -*-
"""Le budget de colonnes de l'atelier Pdf, RECALCULE plutot que relu (AC 11, lot J).

**Ce que ce banc ferme, et il a ete paye deux fois.** Les lignes `MESURE:` des
constantes `RACCOURCIS_*` etaient jusqu'ici de la **prose** posee a la main --
« 48 colonnes en UTF-8, 53 en repli ASCII ». Un chiffre ecrit a la main perime
en silence : au 2026-09-02, **cinq des neuf** commentaires existants etaient
faux (45/51 valait 47/52, 44/54 valait 44/49, 55/60 valait 47/47), sans que
rien ne l'ait jamais signale. C'est exactement la famille que `CLAUDE.md`
poursuit -- « un document ne recopie jamais une valeur qui vit dans le code » --
appliquee cette fois a un commentaire.

Le geste : le banc **recalcule** les deux largeurs a chaque course et les
confronte au commentaire. Un libelle qui s'allonge fait rougir la ligne qui le
decrit, et non l'inverse.

**Pourquoi les DEUX regimes, et pourquoi l'ASCII est le regime dangereux.** Le
repli ASCII est le seul endroit du depot ou une ligne **s'allonge** : `⏎` vaut
une colonne et son repli `Entree` en vaut six. C'est donc toujours en `--ascii`
qu'une ligne deborde en premier, et c'est le regime que personne ne regarde.

**Et le debordement ne rougit nulle part de lui-meme** : une ligne trop large
passe sous `jetons.ajuster`, qui l'**abrege**. Le rendu devient
`... Echap retour  F1 a...` -- l'annonce de la touche d'aide est mutilee, en
silence, et seulement dans un regime. D'ou la mesure a l'egalite plutot qu'une
borne : on veut savoir **avant**, pas voir un ecran tronque.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

from mixed_media_utility.tui import atelier_pdf, jetons

#: `MESURE: <utf8>/<ascii>`, le format exige par l'AC 11.4.
FORME_DE_LA_MESURE = re.compile(r"MESURE:\s*(\d+)/(\d+)\s*$")

#: La seule constante qui touche la borne, et ce n'est pas une tolerance : c'est
#: un fait mesure qu'on rend OPPOSABLE. Une deuxieme qui l'atteindrait ferait
#: rougir, et celle-ci si elle s'en eloignait -- l'ensemble se mesure a
#: l'egalite, jamais par appartenance (`CLAUDE.md`, 2026-08-30).
CONSTANTES_A_LA_BORNE = {"atelier_pdf_reglages.RACCOURCIS_CHOIX"}


def _modules_de_l_atelier() -> list[Path]:
    dossier = Path(atelier_pdf.__file__).resolve().parent
    return sorted(dossier.glob("atelier_pdf*.py"))


def _noms_de_raccourcis(chemin: Path) -> dict[str, int]:
    """Les noms des constantes `RACCOURCIS_*` du module, et leur ligne.

    **On collecte les noms par l'arbre syntaxique et les VALEURS par import**,
    et ce partage est le coeur de ce banc. Une premiere redaction lisait aussi
    la valeur dans l'arbre, ce qui ne voyait que les litteraux : les trois
    constantes de `atelier_pdf_resultat` -- un **alias** et deux `join(...)` --
    tombaient hors du balayage, et le test « toutes portent leur mesure »
    passait au vert **sans les avoir regardees**. Un faux vert par omission,
    de la meme famille que ceux que `CLAUDE.md` collectionne : la mesure ne
    disait pas ce qu'elle ne mesurait pas.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    trouves: dict[str, int] = {}
    for noeud in arbre.body:
        if not isinstance(noeud, ast.Assign) or len(noeud.targets) != 1:
            continue
        cible = noeud.targets[0]
        if isinstance(cible, ast.Name) and cible.id.startswith("RACCOURCIS_"):
            trouves[cible.id] = noeud.lineno
    return trouves


def _mesure_declaree(chemin: Path, ligne_de_definition: int) -> tuple[int, int] | None:
    """La derniere ligne `MESURE:` du bloc de commentaires qui precede.

    On remonte depuis la definition tant qu'on lit des lignes de commentaire :
    une mesure posee ailleurs qu'au contact de sa constante ne la decrit pas.
    """
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    rang = ligne_de_definition - 2
    while rang >= 0 and lignes[rang].lstrip().startswith("#"):
        trouve = FORME_DE_LA_MESURE.search(lignes[rang])
        if trouve:
            return int(trouve.group(1)), int(trouve.group(2))
        rang -= 1
    return None


def _largeurs(ligne: str) -> tuple[int, int]:
    return jetons.colonnes(ligne), jetons.colonnes(jetons.replier_ascii(ligne))


def _toutes_les_constantes() -> dict[str, tuple[Path, str, int]]:
    """Nom qualifie -> (fichier, valeur RESOLUE, ligne de definition)."""
    tout: dict[str, tuple[Path, str, int]] = {}
    for chemin in _modules_de_l_atelier():
        module = importlib.import_module(
            f"mixed_media_utility.tui.{chemin.stem}")
        for nom, rang in _noms_de_raccourcis(chemin).items():
            tout[f"{chemin.stem}.{nom}"] = (chemin, getattr(module, nom), rang)
    return tout


#: Les treize constantes de raccourcis de l'atelier, nommees une par une.
#:
#: **Cet ensemble existe parce que le balayage a deja ete incomplet sans que
#: rien ne le dise** : trois constantes de `atelier_pdf_resultat` sortaient du
#: filet, et les tests « toutes portent leur mesure » et « aucune ne deborde »
#: rendaient vert en n'en regardant que dix. Une mesure qui ne dit pas son
#: cardinal ne dit pas grand-chose.
CONSTANTES_DE_L_ATELIER = {
    "atelier_pdf.RACCOURCIS_PDF_MENU",
    "atelier_pdf_calibration.RACCOURCIS_MIRE_EN_COURS",
    "atelier_pdf_calibration.RACCOURCIS_MIRE_JUGEMENT",
    "atelier_pdf_calibration.RACCOURCIS_MIRE_REGLAGES",
    "atelier_pdf_confirmation.RACCOURCIS_PDF_CONFIRMATION",
    "atelier_pdf_execution.RACCOURCIS_GENERATION",
    "atelier_pdf_lots.RACCOURCIS_LOTS",
    "atelier_pdf_reglages.RACCOURCIS_CHOIX",
    "atelier_pdf_reglages.RACCOURCIS_VALIDER",
    "atelier_pdf_resultat.RACCOURCIS_CURSEUR_DANS_LA_LISTE",
    "atelier_pdf_resultat.RACCOURCIS_CURSEUR_SUR_LES_ISSUES",
    "atelier_pdf_resultat.RACCOURCIS_LISTE_ENTIERE",
    "atelier_pdf_versions.RACCOURCIS_DU_CONFLIT",
}


def test_le_balayage_voit_EXACTEMENT_les_treize_constantes():
    """Le cardinal du filet se mesure, sinon rien de ce qui suit ne vaut.

    Une quatorzieme constante ajoutee demain sans mesure ferait rougir ici ;
    une qui disparaitrait aussi.
    """
    assert set(_toutes_les_constantes()) == CONSTANTES_DE_L_ATELIER


# ---------------------------------------------------------------------------
# Le volet symetrique : la mesure sait-elle voir une faute ?
# ---------------------------------------------------------------------------

def test_le_lecteur_de_MESURE_voit_un_chiffre_et_refuse_la_prose(tmp_path):
    """Sans ce temoin, un balayage muet passerait pour une preuve.

    Trois formes, et les trois comptent : la bonne, la **prose** (l'ancien
    format, qui doit desormais etre refuse) et l'**absence**.
    """
    bon = tmp_path / "bon.py"
    bon.write_text('#: MESURE: 12/15\nRACCOURCIS_X = "abc"\n', encoding="utf-8")
    assert _mesure_declaree(bon, 2) == (12, 15)

    prose = tmp_path / "prose.py"
    prose.write_text('#: MESURE: 12 colonnes en UTF-8, 15 en ASCII.\n'
                     'RACCOURCIS_X = "abc"\n', encoding="utf-8")
    assert _mesure_declaree(prose, 2) is None

    muet = tmp_path / "muet.py"
    muet.write_text('#: une explication sans chiffre\nRACCOURCIS_X = "abc"\n',
                    encoding="utf-8")
    assert _mesure_declaree(muet, 2) is None


def test_le_calcul_des_largeurs_VOIT_l_allongement_du_repli_ASCII():
    """Le repli est le seul endroit du depot ou une ligne s'ALLONGE.

    `⏎` vaut une colonne, `Entree` en vaut six : sans ce temoin, un banc qui
    ne mesurerait que l'UTF-8 se croirait complet.
    """
    utf8, ascii_seul = _largeurs("⏎ continuer")
    assert ascii_seul > utf8
    assert (utf8, ascii_seul) == (11, 16)


# ---------------------------------------------------------------------------
# La mesure elle-meme
# ---------------------------------------------------------------------------

def test_TOUTE_constante_de_raccourcis_porte_sa_ligne_MESURE():
    """AC 11.4 : l'ensemble de celles qui n'en portent pas est EXACTEMENT vide.

    Une appartenance (« tel module la porte ») laisserait passer le module
    suivant sans rien dire.
    """
    sans_mesure = {
        nom for nom, (chemin, _valeur, rang) in _toutes_les_constantes().items()
        if _mesure_declaree(chemin, rang) is None
    }
    assert sans_mesure == set()


@pytest.mark.parametrize("nom", sorted(_toutes_les_constantes()))
def test_la_ligne_MESURE_dit_les_largeurs_REELLES(nom):
    """Le commentaire est confronte au calcul, dans les deux regimes.

    C'est ici que le banc gagne son prix : cinq des neuf commentaires poses a
    la main etaient faux le 2026-09-02, et aucun test ne le disait.
    """
    chemin, valeur, rang = _toutes_les_constantes()[nom]
    assert _mesure_declaree(chemin, rang) == _largeurs(valeur), (
        nom, "declare", _mesure_declaree(chemin, rang), "mesure", _largeurs(valeur))


@pytest.mark.parametrize("nom", sorted(_toutes_les_constantes()))
def test_aucune_ligne_de_raccourcis_ne_DEBORDE_la_zone_utile(nom):
    """La grille 80x24, dans les deux regimes, sur la zone reellement utile.

    La borne est **lue** de `jetons.largeur_utile()`, jamais recopiee.
    """
    _chemin, valeur, _rang = _toutes_les_constantes()[nom]
    utile = jetons.largeur_utile()
    for regime, largeur in zip(("utf8", "ascii"), _largeurs(valeur)):
        assert largeur <= utile, (nom, regime, largeur, utile)


def test_l_ensemble_des_lignes_A_LA_BORNE_est_EXACTEMENT_celui_la():
    """Ce qui touche la borne est nomme, et son unicite est mesuree.

    Une ligne a la borne n'est pas fautive -- elle tient. Elle est **fragile** :
    une lettre de plus et elle passe sous `jetons.ajuster`, qui l'abrege en
    silence et mutile l'annonce de `F1 aide`, dans le seul regime ASCII. On
    mesure donc l'ensemble EXACT de ces lignes : une deuxieme qui arriverait
    la ferait rougir, et celle-ci si elle s'en eloignait.
    """
    utile = jetons.largeur_utile()
    a_la_borne = {
        nom for nom, (_c, valeur, _r) in _toutes_les_constantes().items()
        if max(_largeurs(valeur)) == utile
    }
    assert a_la_borne == CONSTANTES_A_LA_BORNE


# ---------------------------------------------------------------------------
# AC 11.2 et 11.6 -- les deux frontieres qui n'etaient mesurees NULLE PART
# en ensemble, sur les neuf modules
# ---------------------------------------------------------------------------

#: Les blocs Unicode ou vivent les marqueurs d'ecran : fleches, formes
#: geometriques, symboles divers, dingbats.
#:
#: On ne balaie pas « tout ce qui n'est pas ASCII » : les libelles portent des
#: accents et des guillemets francais, qui sont du TEXTE et non des marqueurs.
#: Une frontiere qui les compterait rougirait sur `Échap` et se ferait
#: desactiver dans la semaine.
def _est_un_marqueur(caractere: str) -> bool:
    point = ord(caractere)
    return (0x2190 <= point <= 0x21FF      # fleches
            or 0x2500 <= point <= 0x27BF   # traits, formes, symboles, dingbats
            or 0x2B00 <= point <= 0x2BFF)  # symboles et fleches, supplement


def _marqueurs_du_source(chemin: Path) -> set[str]:
    """Les marqueurs presents dans les chaines de CODE du module.

    Docstrings exclus : un module qui EXPLIQUE pourquoi il n'emploie pas un
    glyphe ne doit pas se faire prendre par sa propre explication -- c'est le
    meme piege que la frontiere des termes interdits a deja paye.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docs = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef)):
            if noeud.body and isinstance(noeud.body[0], ast.Expr):
                valeur = noeud.body[0].value
                if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
                    docs.add(id(valeur))
    vus: set[str] = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and id(noeud) not in docs):
            vus |= {c for c in noeud.value if _est_un_marqueur(c)}
    return vus


def _table_des_glyphes() -> set[str]:
    """La table, LUE de `jetons.py` et jamais recopiee ici.

    C'est la meme discipline qu'`EPIC11-ARB-181` a posee le 2026-09-02 pour
    `RANG_ORIGINE` : la valeur vit a un seul endroit, l'appelant la nomme.
    Une liste de glyphes recopiee dans ce banc divergerait au premier ajout.
    """
    return _marqueurs_du_source(Path(jetons.__file__))


def test_la_table_des_glyphes_n_est_pas_VIDE():
    """Volet symetrique : une table vide rendrait la frontiere 11.6 tautologique.

    Sans ce temoin, un `jetons.py` qu'on n'arriverait plus a lire donnerait une
    table vide, et « aucun glyphe hors de la table » deviendrait « aucun
    glyphe », donc vert pour la mauvaise raison.
    """
    table = _table_des_glyphes()
    assert len(table) >= 10, sorted(table)
    for attendu in ("↑", "↓", "▸", "●", "▲"):
        assert attendu in table, (attendu, sorted(table))


def test_AUCUN_glyphe_hors_de_la_table_n_entre_dans_les_modules():
    """AC 11.6 : l'ensemble des glyphes etrangers est EXACTEMENT vide.

    `*` litteral est nommement vise par l'AC -- il entrerait en collision avec
    le repli ASCII de `●` --, et il tombe sous la meme mesure par une autre
    porte : le test suivant.
    """
    table = _table_des_glyphes()
    etrangers = {
        chemin.name: sorted(_marqueurs_du_source(chemin) - table)
        for chemin in _modules_de_l_atelier()
    }
    assert {n: g for n, g in etrangers.items() if g} == {}


def test_AUCUNE_etoile_litterale_n_entre_dans_les_modules():
    """AC 11.6, l'autre moitie : `*` est le glyphe que la table ne peut pas voir.

    `*` est de l'ASCII pur, donc le balayage des blocs de marqueurs ci-dessus
    lui est structurellement aveugle. Il faut une mesure a lui, sans quoi la
    frontiere aurait un trou exactement a l'endroit que l'AC nomme.
    """
    fautifs = {}
    for chemin in _modules_de_l_atelier():
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        docs = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef)):
                if noeud.body and isinstance(noeud.body[0], ast.Expr):
                    valeur = noeud.body[0].value
                    if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str):
                        docs.add(id(valeur))
        textes = [n.value for n in ast.walk(arbre)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and id(n) not in docs and "*" in n.value]
        if textes:
            fautifs[chemin.name] = textes
    assert fautifs == {}


def test_la_mesure_de_l_ETOILE_sait_rougir(tmp_path):
    """Volet symetrique de la mesure ci-dessus, sur un temoin ecrit ici."""
    fautif = tmp_path / "fautif.py"
    fautif.write_text('MARQUE = "* coche"\n', encoding="utf-8")
    arbre = ast.parse(fautif.read_text(encoding="utf-8"))
    assert [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and "*" in n.value] == ["* coche"]


#: Ce que la TUI ne doit jamais faire : ecrire sur la sortie standard, ou lancer
#: un process. Les trois noms sont ceux de l'AC 11.2.
SURFACES_INTERDITES = ("print", "sys.stdout", "subprocess")


def test_AUCUN_module_de_l_atelier_n_ECRIT_sur_la_sortie_standard():
    """AC 11.2 : ni `print`, ni `sys.stdout`, ni `subprocess`, en ensemble EXACT.

    Une TUI qui ecrit sur la sortie standard **corrompt son propre ecran** :
    `textual` tient le terminal, et une ligne imprimee a cote traverse le
    dessin. Le defaut ne se voit pas en test unitaire, seulement au clavier --
    c'est exactement le genre de faute qu'une frontiere doit attraper avant.
    """
    fautifs: dict[str, list[str]] = {}
    for chemin in _modules_de_l_atelier():
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        vus = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
                if noeud.func.id == "print":
                    vus.append(f"print (l. {noeud.lineno})")
            if isinstance(noeud, ast.Attribute) and noeud.attr == "stdout":
                vus.append(f"stdout (l. {noeud.lineno})")
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                noms = [a.name for a in noeud.names]
                if isinstance(noeud, ast.ImportFrom) and noeud.module:
                    noms.append(noeud.module)
                if any(n and n.split(".")[0] == "subprocess" for n in noms):
                    vus.append(f"subprocess (l. {noeud.lineno})")
        if vus:
            fautifs[chemin.name] = vus
    assert fautifs == {}


def test_la_mesure_des_SURFACES_INTERDITES_sait_rougir(tmp_path):
    """Volet symetrique : les trois formes, sur trois temoins ecrits ici.

    Une frontiere negative qui ne mord sur aucun temoin est verte sans rien
    mesurer -- le defaut que l'AC 11.5 existe pour ecarter.
    """
    for source, attendu in (
        ('def f():\n    print("bonjour")\n', "print"),
        ("import sys\n\n\ndef f():\n    sys.stdout.write('x')\n", "stdout"),
        ("import subprocess\n", "subprocess"),
    ):
        fautif = tmp_path / f"temoin_{attendu}.py"
        fautif.write_text(source, encoding="utf-8")
        arbre = ast.parse(source)
        vu = False
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "print"):
                vu = vu or attendu == "print"
            if isinstance(noeud, ast.Attribute) and noeud.attr == "stdout":
                vu = vu or attendu == "stdout"
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                noms = [a.name for a in noeud.names]
                if any(n and n.split(".")[0] == "subprocess" for n in noms):
                    vu = vu or attendu == "subprocess"
        assert vu, (attendu, source)
