# -*- coding: utf-8 -*-
"""Frontiere de `tests/_regime_du_depot.py` -- la distinction des deux depots.

**Pourquoi ce banc doit exister avant l'aide qu'il mesure.** L'aide sert a
faire SAUTER des tests. Une aide de saut qui se tromperait dans le sens
permissif eteindrait en silence les bancs qu'elle protege -- verts, sautes,
plus rien de mesure -- et **aucun d'eux ne pourrait le signaler, puisqu'ils
sauteraient**. C'est la circularite exacte que la politique du depot appelle un
faux vert, et le seul moyen d'en sortir est de mesurer l'aide sur des depots
FABRIQUES, ou la reponse est connue d'avance et ne depend pas du depot ou ce
banc tourne. Il rougit donc identiquement sur le depot de travail et sur
l'orphelin public.

Regle des fabriques : chaque depot fabrique porte DEUX commits distinguables,
et le commit cherche n'est jamais le premier -- un predicat qui ne regarderait
que la tete rendrait faux et passerait pour juste.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE_DEPOT / "tests"))

import _regime_du_depot as regime  # noqa: E402
from _regime_du_depot import (  # noqa: E402
    echoue_ou_saute,
    porte_l_historique_de_travail,
    references_de_module,
    references_joignables,
)


def _depot_a_deux_commits(dossier: Path, marque: str) -> list[str]:
    """Un depot git jetable de DEUX commits, rendus du plus ancien au plus recent.

    **`marque` n'est pas decoratif, et l'oublier a fait rougir ce banc.**
    Premiere redaction : les deux depots fabriques recevaient le meme contenu,
    les memes messages, le meme auteur -- et, crees dans la meme seconde, le
    meme horodatage. Git en a donc tire des condensats IDENTIQUES, si bien que
    le depot cense etre ORPHELIN contenait litteralement les commits de
    l'autre, et le test rougissait sur une fabrique et non sur l'aide.

    C'est la regle des fabriques du depot retournee contre le banc qui la
    cite : deux elements doivent etre DISTINGUABLES, un remplissage uniforme ne
    demasque rien. Ici l'uniformite ne cachait pas un defaut -- elle en
    fabriquait un.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    def git(*args):
        return subprocess.run(("git", *args), cwd=dossier,
                              capture_output=True, text=True, check=True).stdout
    git("init", "-q", "-b", "principale")
    git("config", "user.email", f"{marque}@exemple.invalid")
    git("config", "user.name", f"Banc {marque}")
    references = []
    for rang, contenu in enumerate(("premier", "second"), start=1):
        (dossier / f"fichier-{rang}.txt").write_text(
            f"{contenu} de {marque}", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", f"{marque} : commit {rang} ({contenu})")
        references.append(git("rev-parse", "HEAD").strip())
    return references


def test_une_reference_du_depot_est_joignable_et_une_INVENTEE_ne_l_est_pas(tmp_path):
    """Le volet nominal, sur un depot fabrique, et la cible n'est pas la tete.

    Le commit cherche est le PREMIER des deux -- donc pas `HEAD` --, faute de
    quoi une implementation qui ne saurait interroger que la tete passerait.
    """
    depot = tmp_path / "travail"
    anciens = _depot_a_deux_commits(depot, "travail")
    invente = "0" * 40

    assert references_joignables(depot, [anciens[0]]) == [anciens[0]]
    assert references_joignables(depot, [invente]) == []


def test_un_BLOB_n_est_PAS_une_reference_joignable(tmp_path):
    """Le mutant `R4`, qui a SURVECU a la premiere campagne et que voici ferme.

    `git cat-file -e <sha>` reussit sur **n'importe quel objet** : un arbre, un
    blob, une etiquette. Retirer le `^{commit}` de l'interrogation laissait donc
    les six autres tests VERTS tout en rendant le predicat faux -- un depot
    partageant un seul blob avec l'arbre de travail (un `LICENSE` identique
    suffit, et l'orphelin public en porte un) se serait declare porteur de
    l'historique de travail, et les douze bancs y auraient echoue comme avant.

    C'est le motif que la politique du depot repete depuis la revue 8.8 : « N
    mutants, 0 survivant » mesure la SOLIDITE de ce qui est asserte, jamais
    l'ETENDUE de ce qui ne l'est pas. Cinq mutations, une survivante, et c'est
    elle qui portait le vrai risque.

    La cible est le blob du SECOND fichier, jamais du premier : un predicat qui
    n'interrogerait que le premier objet du depot passerait autrement.
    """
    depot = tmp_path / "travail"
    commits = _depot_a_deux_commits(depot, "travail")
    blob = subprocess.run(
        ["git", "rev-parse", "HEAD:fichier-2.txt"],
        cwd=depot, capture_output=True, text=True, check=True).stdout.strip()

    # Le blob EXISTE bien dans ce depot -- c'est tout l'interet du cas.
    assert subprocess.run(["git", "cat-file", "-e", blob],
                          cwd=depot, capture_output=True).returncode == 0

    assert references_joignables(depot, [blob]) == [], (
        "un blob n'est pas un commit : l'interrogation doit porter sur "
        "`<sha>^{commit}`, sinon n'importe quel objet partage suffit a faire "
        "croire que ce depot porte l'historique de travail")
    assert porte_l_historique_de_travail(depot, [blob]) is False

    # Et le commit du meme depot, lui, reste bien joignable.
    assert references_joignables(depot, [commits[0]]) == [commits[0]]


def test_le_seuil_est_a_UNE_reference_et_non_a_TOUTES(tmp_path):
    """**Le volet qui distingue un cardinal d'un booleen**, et il porte la regle.

    Un depot qui porte une reference sur deux est le depot de TRAVAIL avec une
    reference perimee : son banc doit continuer d'echouer sur la manquante,
    c'est meme tout ce qu'il sait faire d'utile. Seul le zero absolu signale un
    AUTRE depot. Une aide qui exigerait « toutes joignables » ferait sauter les
    douze bancs des qu'un seul commit serait renomme.
    """
    depot = tmp_path / "partiel"
    presents = _depot_a_deux_commits(depot, "partiel")
    melange = [presents[1], "1" * 40]          # la manquante en SECONDE position

    assert references_joignables(depot, melange) == [presents[1]]
    assert porte_l_historique_de_travail(depot, melange) is True, (
        "une reference perimee sur deux ne change pas de depot : le banc doit "
        "continuer d'echouer dessus, pas sauter")


def test_un_historique_ORPHELIN_ne_joint_AUCUNE_reference(tmp_path):
    """Le regime du depot public, fabrique comme il le sera reellement.

    Ce n'est pas un depot vide : il a un historique, des commits, une tete --
    simplement AUCUN commit en commun avec l'arbre de travail, ce qui est la
    definition d'un orphelin (`EPIC8-ARB-12`). C'est le cas que les douze bancs
    confondent aujourd'hui avec un clone tronque.
    """
    travail = tmp_path / "travail"
    public = tmp_path / "public"
    references = _depot_a_deux_commits(travail, "travail")
    _depot_a_deux_commits(public, "public")    # son propre historique, DISJOINT

    assert references_joignables(public, references) == []
    assert porte_l_historique_de_travail(public, references) is False, (
        "un historique orphelin doit se reconnaitre : sinon les douze bancs y "
        "echouent sur des commits qui n'y existeront JAMAIS")
    # Et le sens inverse, pour que le test ne soit pas vert sur un depot casse.
    assert porte_l_historique_de_travail(travail, references) is True


def test_le_detecteur_ne_retient_que_les_constantes_de_MODULE():
    """La mesure qui a fait resserrer le detecteur, rejouee sur une source.

    Le litteral en ligne est en SECONDE position et le detecteur doit le
    manquer : c'est la forme des huit faux positifs mesures le 2026-09-08 sur
    `tests/**/*.py` -- sommes de controle de `test_patch_presets.py`,
    `deadbeef` de `test_scan_previz.py`, `0123456789abcdef` de `test_naming.py`.
    Un detecteur qui prendrait toute chaine en forme de SHA les prendrait tous.
    """
    source = (
        'BASELINE_DE_LA_STORY = "a1b2c3d"\n'
        'AUTRE = "0123456789abcdef"\n'
        'def f():\n'
        '    LOCALE = "deadbeef"\n'                 # dans une fonction : ignoree
        '    return _diff("1906211"), LOCALE\n'     # en ligne : ignoree
        'PAS_UN_SHA = "zzzzzzz"\n'                  # bonne longueur, mauvais alphabet
    )
    trouves = references_de_module(source)

    assert trouves == {"BASELINE_DE_LA_STORY": "a1b2c3d",
                       "AUTRE": "0123456789abcdef"}, trouves
    assert "deadbeef" not in trouves.values()
    assert "1906211" not in trouves.values()
    assert "zzzzzzz" not in trouves.values()


def test_le_detecteur_trouve_les_DOUZE_bancs_REELS_du_depot():
    """Le volet qui interdit un detecteur juste sur la synthese et faux ici.

    Il rejoue la mesure du 2026-09-08 sur l'arbre reel : douze fichiers, et
    zero fichier PORTEUR d'un faux positif connu. Sur l'orphelin public,
    `tests/` est identique -- ce banc y mesure donc la meme chose.
    """
    porteurs = {}
    for banc in sorted((RACINE_DEPOT / "tests").rglob("*.py")):
        try:
            trouves = references_de_module(banc.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        if trouves:
            porteurs[banc.relative_to(RACINE_DEPOT).as_posix()] = trouves

    assert len(porteurs) >= 7, (
        f"seulement {len(porteurs)} bancs a reference de module : le detecteur "
        "s'est resserre au point de ne plus rien voir")

    # Les huit faux positifs mesures ne doivent JAMAIS entrer, nommes un par un.
    for faux in ("tests/unit/test_patch_presets.py",
                 "tests/unit/test_scan_previz.py",
                 "tests/unit/test_naming.py",
                 "tests/unit/test_extraction_manifest.py",
                 "tests/unit/gui/fabriques_detection.py",
                 "tests/unit/test_encodeur_qr_segno.py",
                 "tests/unit/test_outillage_de_mesure.py"):
        assert faux not in porteurs, (
            f"`{faux}` ne porte que des SHA EN LIGNE -- somme de controle, "
            "valeur de fabrique. Le detecteur s'est relache et le prend pour "
            "un banc de perimetre.")


def test_les_references_reelles_sont_TOUTES_joignables_sur_CE_depot():
    """Le volet qui rougit sur une reference perimee, et il doit le faire ICI.

    C'est le seul test de ce fichier qui parle de l'arbre reel, donc le seul
    qui ne peut pas tenir sur l'orphelin. Il y saute -- structurellement, sur
    la mesure et non sur un drapeau -- par l'aide qu'il mesure lui-meme, ce qui
    est sans circularite : les cinq tests ci-dessus l'ont deja etablie sur des
    depots fabriques.
    """
    reelles = {}
    for banc in sorted((RACINE_DEPOT / "tests").rglob("*.py")):
        try:
            for nom, reference in references_de_module(
                    banc.read_text(encoding="utf-8")).items():
                reelles.setdefault(reference, []).append(
                    f"{banc.relative_to(RACINE_DEPOT).as_posix()}:{nom}")
        except SyntaxError:
            continue

    if not porte_l_historique_de_travail(RACINE_DEPOT, reelles):
        pytest.skip(
            "aucune des references de perimetre n'est joignable ici : ce depot "
            "n'est pas celui du TRAVAIL (historique orphelin du public, "
            "EPIC8-ARB-12). Il n'y a pas de reference perimee a y chercher.")

    manquantes = set(reelles) - set(references_joignables(RACINE_DEPOT, reelles))
    assert not manquantes, (
        "ces references de perimetre ne sont plus joignables sur le depot de "
        "TRAVAIL -- historique reecrit, ou constante perimee :\n  " + "\n  ".join(
            f"{r} ({', '.join(reelles[r])})" for r in sorted(manquantes)))


# ---------------------------------------------------------------------------
# `echoue_ou_saute` -- les TROIS cas, sur des depots FABRIQUES
#
# Meme motif que ci-dessus, et il compte davantage encore ici : cette fonction
# est celle qui fait sauter. Mesuree a travers les sept bancs qui l'appellent,
# elle serait mesuree par des tests qu'elle peut elle-meme faire sauter. Les
# trois cas sont donc joues sur des depots jetables, avec un ensemble de
# references declarees FABRIQUE lui aussi -- sinon le verdict dependrait du
# depot ou ce banc tourne, c'est-a-dire exactement de ce qu'il mesure.
# ---------------------------------------------------------------------------

MOTIF = "commit de reference deadbeef inatteignable : la frontiere ne s'evalue pas"


def _verdict_rendu(appel):
    """L'exception que `appel` leve, capturee SANS passer par `pytest.raises`.

    **Ce detour a ete paye, et par la campagne de mutation de ce banc-la.**
    Les quatre tests ci-dessous ecrivaient d'abord
    `with pytest.raises(pytest.fail.Exception)`. Deux mutants ont alors
    SURVECU -- « la sonde fabriquee cesse d'echouer dur » et « le seuil passe
    de UNE reference a TOUTES » --, non parce que le test les acceptait, mais
    parce que le `Skipped` qu'ils produisent **traverse** `pytest.raises` : le
    test etait rapporte SAUTE, et un saut ne figure dans aucune liste de
    rouges.

    C'est mot pour mot « un skip se lirait comme un vert », le defaut que
    `_regime_du_depot` existe pour arbitrer, retourne contre le banc qui
    l'arbitre. On capture donc les deux verdicts et on compare le TYPE.
    """
    try:
        appel()
    except BaseException as leve:                # noqa: BLE001 - c'est le sujet
        return leve
    raise AssertionError(
        "aucun verdict rendu : `echoue_ou_saute` est passee en silence, ce qui "
        "laisserait la frontiere appelante continuer sur une mesure absente")


def _echec_dur(appel, motif=None):
    """Exige un `pytest.fail`, et NOMME le verdict rendu a la place."""
    rendu = _verdict_rendu(appel)
    assert isinstance(rendu, pytest.fail.Exception), (
        f"verdict attendu : echec dur ; verdict rendu : "
        f"{type(rendu).__name__} -- {rendu}")
    if motif is not None:
        assert motif in str(rendu), str(rendu)
    return rendu


def _saut(appel):
    """Exige un `pytest.skip`, et NOMME le verdict rendu a la place."""
    rendu = _verdict_rendu(appel)
    assert isinstance(rendu, pytest.skip.Exception), (
        f"verdict attendu : saut ; verdict rendu : "
        f"{type(rendu).__name__} -- {rendu}")
    return rendu


def test_une_reference_FABRIQUEE_echoue_DUR_meme_sans_aucun_historique(tmp_path):
    """Premier cas : une sonde que personne ne declare doit faire MORDRE la porte.

    C'est le cas qui sauve
    `test_the_perimeter_gate_separates_a_copied_tree_from_a_truncated_history`,
    dont la sonde est litteralement `"0" * 40`. Sans lui, cette frontiere-la
    serait SAUTEE sur le depot public au lieu d'y echouer -- elle cesserait de
    mesurer la porte le jour ou elle en aurait le plus besoin.

    Aucune monkeypatch ici : on interroge l'ensemble des references REELLES du
    depot, et le point du test est qu'une sonde n'en fait jamais partie.
    """
    depot = tmp_path / "sans-histoire"
    _depot_a_deux_commits(depot, "sonde")
    _echec_dur(lambda: echoue_ou_saute(depot, "0" * 40, MOTIF), MOTIF)


def test_UNE_SEULE_reference_declaree_joignable_suffit_a_garder_l_echec_DUR(
        tmp_path, monkeypatch):
    """Deuxieme cas : le clone tronque, et c'est le comportement D'ORIGINE.

    Le depot fabrique porte DEUX commits ; on declare le PREMIER (donc pas la
    tete) et deux references introuvables. Une sur trois est joignable : c'est
    le depot de travail avec une reference perimee, et son banc doit echouer,
    pas sauter. Un predicat qui exigerait que TOUTES soient joignables
    rendrait ici un saut, et ce test le voit.
    """
    depot = tmp_path / "tronque"
    anciens = _depot_a_deux_commits(depot, "tronque")
    monkeypatch.setattr(
        regime, "references_declarees",
        lambda _racine: frozenset({anciens[0], "d" * 40, "e" * 40}))
    _echec_dur(lambda: echoue_ou_saute(depot, "d" * 40, MOTIF), MOTIF)


def test_AUCUNE_reference_declaree_joignable_fait_SAUTER_en_le_disant(
        tmp_path, monkeypatch):
    """Troisieme cas : un AUTRE depot. Le saut est nomme, et il porte le motif.

    Le motif d'origine est transporte dans le message plutot que remplace : un
    saut qui effacerait la raison pour laquelle la frontiere existait laisserait
    le lecteur suivant sans rien.
    """
    depot = tmp_path / "orphelin"
    _depot_a_deux_commits(depot, "orphelin")
    monkeypatch.setattr(
        regime, "references_declarees",
        lambda _racine: frozenset({"d" * 40, "e" * 40}))
    message = str(_saut(lambda: echoue_ou_saute(depot, "d" * 40, MOTIF)))
    assert "EPIC8-ARB-12" in message, message
    assert MOTIF in message, message


def test_les_trois_cas_se_distinguent_par_le_CARDINAL_et_non_par_la_reference(
        tmp_path, monkeypatch):
    """La meme reference sondee rend DEUX verdicts selon le seul cardinal.

    C'est la propriete que les trois tests ci-dessus etablissent separement, et
    qu'aucun d'eux ne montre seul : la reference sondee est identique des deux
    cotes, seul l'ensemble declare change. Un mecanisme qui trancherait sur la
    reference elle-meme -- sa longueur, sa forme, une liste de noms -- passerait
    les trois precedents et rougirait ici.
    """
    depot = tmp_path / "les-deux"
    anciens = _depot_a_deux_commits(depot, "les-deux")

    monkeypatch.setattr(regime, "references_declarees",
                        lambda _racine: frozenset({anciens[1], "d" * 40}))
    _echec_dur(lambda: echoue_ou_saute(depot, "d" * 40, MOTIF))

    monkeypatch.setattr(regime, "references_declarees",
                        lambda _racine: frozenset({"d" * 40}))
    _saut(lambda: echoue_ou_saute(depot, "d" * 40, MOTIF))


def test_references_declarees_balaye_un_ARBRE_DE_BANCS_fabrique(tmp_path):
    """L'inventaire, mesure sur un arbre fabrique plutot que sur le depot.

    Deux fichiers a deux niveaux, pour que le balayage soit RECURSIF, et un
    troisieme qui ne porte qu'un litteral EN LIGNE : c'est le faux positif que
    `references_de_module` ecarte deja, et l'inventaire doit heriter de ce tri
    plutot que de le refaire.
    """
    arbre = tmp_path / "bancs"
    (arbre / "profond").mkdir(parents=True)
    (arbre / "test_a.py").write_text('BASELINE = "aaaaaaa"\n', encoding="utf-8")
    (arbre / "profond" / "test_b.py").write_text(
        '_BORNE = "bbbbbbb"\n', encoding="utf-8")
    (arbre / "test_c.py").write_text(
        'def f():\n    return verifie("ccccccc")\n', encoding="utf-8")

    assert regime.references_declarees(str(arbre)) == frozenset({"aaaaaaa", "bbbbbbb"})


# ---------------------------------------------------------------------------
# La frontiere NEGATIVE : aucun banc ne reprend la decision a son compte
# ---------------------------------------------------------------------------

#: Le mot que les huit sites employaient tous, et qui les designe sans registre
#: de noms a tenir a jour. Le tri se fait sur la FORME de ce que le site DIT,
#: comme `chemins_joints` trie sur la forme de ce qu'un banc construit.
_MOT_DE_LA_REFERENCE_ABSENTE = "inatteignable"


def _verdicts_nus(source: str) -> list[str]:
    """Les `pytest.fail`/`pytest.skip` qui parlent eux-memes d'inatteignabilite."""
    import ast

    nus = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        if not (isinstance(cible, ast.Attribute)
                and cible.attr in ("fail", "skip")
                and isinstance(cible.value, ast.Name)
                and cible.value.id == "pytest"):
            continue
        litteraux = [n.value for n in ast.walk(noeud)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        if any(_MOT_DE_LA_REFERENCE_ABSENTE in t for t in litteraux):
            nus.append(f"pytest.{cible.attr} l.{noeud.lineno}")
    return nus


def test_AUCUN_banc_ne_tranche_LUI_MEME_une_reference_inatteignable():
    """Le mutant que ce test attrape : un site qui reprend `pytest.fail` en direct.

    **C'est la frontiere qui manquerait sinon**, et elle est negative parce
    qu'aucun test positif ne pourrait la remplacer : sur le depot de TRAVAIL,
    les quatorze references sont joignables, donc les huit sites ne s'executent
    jamais et un site revenu en arriere resterait invisible jusqu'a la
    publication -- c'est-a-dire jusqu'au seul moment ou il coute.

    Elle attrape les DEUX sens de la derive, et c'est voulu : un `pytest.fail`
    nu reintroduirait les 27 rouges de l'orphelin ; un `pytest.skip` nu ferait
    sauter la frontiere aussi sur un clone tronque, ou elle DOIT mordre. Seul
    le passage par `echoue_ou_saute` distingue les deux.

    Le tri se fait sur le mot que ces sites emploient tous, jamais sur une liste
    de fichiers : une liste derive des qu'une story neuve epingle sa borne, et
    rien ne le dirait. `_regime_du_depot.py` est exclu -- c'est lui qui rend le
    verdict, et il le rend forcement en clair.
    """
    coupables = {}
    for banc in sorted((RACINE_DEPOT / "tests").rglob("*.py")):
        if banc.name == "_regime_du_depot.py" or banc.name == Path(__file__).name:
            continue
        try:
            source = banc.read_text(encoding="utf-8")
        except OSError:                          # pragma: no cover - defensif
            continue
        try:
            nus = _verdicts_nus(source)
        except SyntaxError:                      # pragma: no cover - defensif
            continue
        if nus:
            coupables[banc.relative_to(RACINE_DEPOT).as_posix()] = nus
    assert not coupables, (
        "ces bancs tranchent eux-memes le sort d'une reference de perimetre "
        "inatteignable, au lieu de passer par `echoue_ou_saute` :\n"
        + "\n".join(f"  {f} : {', '.join(l)}" for f, l in sorted(coupables.items()))
        + "\nUn `pytest.fail` nu rend les 27 rouges de l'orphelin public ; un "
          "`pytest.skip` nu eteint la frontiere sur un clone tronque."
    )


def test_les_HUIT_sites_reels_appellent_bien_l_aide():
    """Le volet positif du precedent -- il en faut un, et il est CHIFFRE.

    La frontiere negative ci-dessus resterait verte sur un depot ou plus aucun
    site n'existerait du tout : supprimer les sept bancs de perimetre la
    satisferait. Le cardinal est donc mesure ici, et il vaut **huit appels dans
    sept fichiers** au 2026-09-08 -- `test_calibration_page_geometry.py` en
    porte deux, un pour le diff et un pour la source au baseline.

    Le cardinal est un PLANCHER et non une egalite : une story neuve qui
    epingle sa borne ajoutera un neuvieme appel, et elle n'a pas a venir
    corriger un chiffre ici. Ce qui doit rougir, c'est la disparition.
    """
    import ast

    appels = {}
    for banc in sorted((RACINE_DEPOT / "tests").rglob("test_*.py")):
        if banc.name == Path(__file__).name:
            continue
        try:
            arbre = ast.parse(banc.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):           # pragma: no cover - defensif
            continue
        n = sum(1 for noeud in ast.walk(arbre)
                if isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "echoue_ou_saute")
        if n:
            appels[banc.relative_to(RACINE_DEPOT).as_posix()] = n
    assert sum(appels.values()) >= 8 and len(appels) >= 7, appels


def test_chaque_site_passe_une_reference_DECLAREE_et_non_un_LITTERAL():
    """La frontiere qui manquait, et le defaut qu'elle ferme a ete paye le jour meme.

    `echoue_ou_saute` reconnait les references que les bancs **declarent** en
    constante de module ; un litteral ecrit en ligne y est indiscernable d'une
    sonde fabriquee, donc traite comme elle -- echec dur, dans tous les depots.

    C'est exactement ce qui est arrive a `test_calibration_page_geometry.py`,
    seul des douze a ecrire sa borne basse en ligne (`_diff_de_production(
    "1906211")`) alors que sa borne haute etait deja une constante : ses deux
    frontieres sont restees ROUGES sur l'orphelin quand les vingt-cinq autres
    sautaient. Une reference sur quinze, et la mesure de publication etait
    encore inexploitable.

    La garde porte sur la FORME de l'argument -- un nom, jamais une chaine --,
    ce qui la rend independante de la valeur et donc du depot ou elle tourne.
    Elle laisse en revanche libre la sonde de la porte
    (`_diff_de_production("0" * 40)`), qui ne passe pas par cette aide : c'est
    un appel au banc, pas au verdict.
    """
    import ast

    litteraux = {}
    for banc in sorted((RACINE_DEPOT / "tests").rglob("test_*.py")):
        if banc.name == Path(__file__).name:
            continue
        try:
            arbre = ast.parse(banc.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):           # pragma: no cover - defensif
            continue
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "echoue_ou_saute"):
                continue
            if len(noeud.args) < 2:
                continue
            reference = noeud.args[1]
            if isinstance(reference, ast.Name):
                continue
            litteraux.setdefault(
                banc.relative_to(RACINE_DEPOT).as_posix(), []).append(
                    f"l.{noeud.lineno} : {ast.dump(reference)[:60]}")
    assert not litteraux, (
        "ces sites passent a `echoue_ou_saute` une reference qui n'est pas un "
        "nom de constante, donc introuvable par l'inventaire :\n"
        + "\n".join(f"  {f} : {', '.join(l)}" for f, l in sorted(litteraux.items()))
        + "\nUne telle reference est traitee comme une sonde fabriquee, et son "
          "banc reste ROUGE sur le depot public."
    )


def test_git_ABSENT_echoue_DUR_et_ne_se_confond_pas_avec_un_autre_depot(
        tmp_path, monkeypatch):
    """Le quatrieme cas, celui qui manquait a la premiere redaction.

    Sans git, `references_joignables` leve `FileNotFoundError` et rend zero
    reference joignable -- ce qui a la lecture ressemble a l'orphelin public.
    Les deux situations n'ont pourtant pas le meme verdict : le public n'aura
    JAMAIS ces commits, alors qu'une machine sans git a une frontiere qui
    devait s'evaluer et ne l'a pas fait. C'est ce que `_git_disponible` et
    `_exige_git_disponible` disaient deja, chacun de son cote.

    La panne est FABRIQUEE plutot que provoquee : retirer git du PATH d'un
    conteneur pour un test le retirerait aussi de la course qui l'entoure.
    """
    depot = tmp_path / "sans-git"
    _depot_a_deux_commits(depot, "sans-git")

    def _pas_de_git(_racine, _references):
        raise FileNotFoundError("git: No such file or directory")

    monkeypatch.setattr(regime, "references_joignables", _pas_de_git)
    monkeypatch.setattr(regime, "references_declarees",
                        lambda _racine: frozenset({"d" * 40}))
    _echec_dur(lambda: echoue_ou_saute(depot, "d" * 40, MOTIF), MOTIF)
