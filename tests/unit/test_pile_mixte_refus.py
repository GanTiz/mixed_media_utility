"""Story 5.23, AC 10 -- la pile mixte refuse, elle ne plante plus (`EPIC5-ARB-85`).

Deux moities, et elles ne se remplacent pas l'une l'autre.

**Le refus nomme.** Une passe qui mele une page de calibration a des planches d'images
rendait une `KeyError` nue -- 60 sur `project_id`, 2 sur `lot_id`, mesurees au
`baseline_commit` de l'amendement du 2026-08-18. Elle rend desormais une
`ReconstructionError` qui dit **quelle** feuille et **pourquoi**. Le refus n'ouvre rien
(`EPIC5-ARB-86`): deux passes separees restent le regime nominal, et la pile en vrac est
reportee a sa propre story.

**Le balayage de la famille.** C'est le sixieme acces indexe nu de la meme famille, apres
`scan_detection` (deux), `io/reconstruction._validate_page_payload`,
`scan_output_frames._lot_identity` et `cli._page_identifier`. Cinq corrections
successives, trouvees une par une, chacune apres coup: la seule facon d'arreter la serie
est de faire du balayage **l'assertion elle-meme**, comme les frontieres de perimetre de
5.19 et 5.22, plutot qu'une relecture ou un grep consigne dans un commentaire.

Le lot entier tient sous la seconde (AC 9): il ne lit que du source et ne compose aucun
PDF.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mixed_media_utility import page_roles  # noqa: E402
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io import reconstruction  # noqa: E402

MODULES = SRC / "mixed_media_utility"

#: Les cinq champs que le role `c` ne porte plus depuis l'AC 8bis (dont
#: `timecode_base_fps`, story 2.7). **Relus** au
#: contrat, jamais recopies: une seconde liste divergerait au premier champ ajoute, et
#: le balayage ci-dessous cesserait alors silencieusement de chercher le bon.
CHAMPS = frozenset(payload_io.CALIBRATION_ABSENT_FIELDS)


# ---------------------------------------------------------------------------
# Fabriques -- deux elements distinguables, cible jamais en premiere position
# ---------------------------------------------------------------------------

#: Deux libelles de chaine **differents**, et c'est la regle des fabriques du depot: une
#: pile ou les deux pages de calibration porteraient le meme libelle rendrait invisible
#: un message qui n'en nomme qu'une, ou qui nomme deux fois la meme.
LIBELLES = (
    "hp envy 4520 tiff 600 dpi auto corr off",
    "epson v600 tiff 1200 dpi profil scanner",
)


def _planche(*, page_index: int, page_count: int, lot_id: str = "lot_temoin_0001") -> dict:
    """Une planche d'images, par son **vrai** producteur.

    Les emplacements sont distinguables (rangs et timecodes tous differents) pour le
    motif de la regle des fabriques: un appariement positionnel inverse ne se voit pas
    sur un remplissage uniforme.
    """
    return payload_io.build_page_payload(
        project_id="projet_demo",
        rush_id="rush_temoin",
        lot_id=lot_id,
        page_index=page_index,
        page_count=page_count,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="tpl-a4-portrait-4f-v2",
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[
            {"slot_index": 2 * page_index + rang,
             "frame_timecode": f"00:00:{page_index:02d}:{rang:02d}"}
            for rang in range(2)
        ],
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )


def _page_de_calibration(*, page_index: int, page_count: int, libelle: str) -> dict:
    """Une page de calibration **d'apres l'AC 8bis**, par son vrai producteur.

    C'est le point du test: le producteur retire lui-meme les cinq champs de
    `CALIBRATION_ABSENT_FIELDS`. Un dictionnaire ecrit a la main ici pourrait les porter
    par distraction, et le defaut mesure ne se reproduirait pas.
    """
    return payload_io.build_page_payload(
        project_id=None,
        rush_id=None,
        lot_id=None,
        page_index=page_index,
        page_count=page_count,
        fps_target=None,
        timecode_base_fps=None,
        template_id="tpl-a4-portrait-4f-v2",
        patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
        scan_chain_label=libelle,
    )


def _pile_mixte() -> list[dict]:
    """Une planche, **puis** les deux pages de calibration, **puis** une planche.

    L'ordre n'est pas decoratif. La cible du refus n'est ni en premiere ni en derniere
    position, et la pile porte **deux** pages de calibration distinguables: une garde qui
    ne regarderait que `payloads[0]`, ou qui s'arreterait a la premiere trouvee, resterait
    verte sur une fabrique mono-element placee en tete.
    """
    return [
        _planche(page_index=1, page_count=4),
        _page_de_calibration(page_index=0, page_count=4, libelle=LIBELLES[0]),
        _page_de_calibration(page_index=3, page_count=4, libelle=LIBELLES[1]),
        _planche(page_index=2, page_count=4),
    ]


# ---------------------------------------------------------------------------
# AC 10 -- le refus nomme
# ---------------------------------------------------------------------------


def test_la_pile_mixte_rend_un_refus_nomme_et_jamais_une_keyerror():
    """Le coeur de l'AC 10, sur le chemin public de la reconstruction."""
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction.reconstruct_project_manifest(_pile_mixte())
    assert capture.value.reason == reconstruction.REFUS_PILE_MIXTE
    # `pytest.raises` sur `ReconstructionError` ne dirait rien d'une `KeyError`: elle
    # n'en est pas une sous-classe, donc le test serait rouge -- mais rouge par erreur de
    # type et non par assertion. On epingle le type exact pour que le motif de l'echec
    # reste lisible si la garde disparaissait.
    assert type(capture.value) is reconstruction.ReconstructionError


def test_le_refus_dit_quelle_page_et_pourquoi():
    """AC 10: « quelle page » et « pourquoi », pas « le lot »."""
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction.reconstruct_project_manifest(_pile_mixte())
    message = str(capture.value)
    # Quelle page: les **deux** pages de calibration sont nommees, par leur rang et par
    # le libelle de leur chaine -- les deux seules choses qui les designent, puisqu'elles
    # ne portent ni projet, ni rush, ni lot.
    for libelle in LIBELLES:
        assert libelle in message, message
    assert "page_index=0" in message and "page_index=3" in message, message
    # Pourquoi: la phrase qui porte le motif d'`EPIC5-ARB-82`, et le geste a faire.
    assert "chaine de scan" in message, message
    assert "passe separee" in message, message


def test_le_refus_nomme_la_page_de_calibration_et_non_la_planche():
    """Un refus qui nommerait la mauvaise feuille enverrait rescanner la bonne.

    Frontiere fine, et elle tue le mutant qui inverse la partition: c'est la page **sans
    identite de lot** qui est en cause, jamais celle qui en porte une.
    """
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction.reconstruct_project_manifest(_pile_mixte())
    message = str(capture.value)
    assert "lot_temoin_0001" not in message, message
    assert "page_index=1" not in message and "page_index=2" not in message, message
    assert "2 page(s) de calibration" in message, message
    assert "2 planche(s)" in message, message


def test_la_garde_voit_la_page_de_calibration_ou_qu_elle_soit_dans_la_pile():
    """Regle des fabriques, point 2: la cible ailleurs qu'en premiere position.

    Quatre positions exercees sur la meme pile de quatre pages. Une garde qui ne lirait
    que `payloads[0]` -- ce que faisait exactement le code fautif -- resterait verte sur
    trois d'entre elles.
    """
    for position in range(4):
        pile = [_planche(page_index=rang, page_count=4) for rang in range(4)]
        pile[position] = _page_de_calibration(
            page_index=position, page_count=4, libelle=LIBELLES[position % 2])
        with pytest.raises(reconstruction.ReconstructionError) as capture:
            reconstruction._check_pile_homogene(pile)
        assert capture.value.reason == reconstruction.REFUS_PILE_MIXTE, position
        assert f"page_index={position}" in str(capture.value), position


def test_la_chaine_de_scan_refuse_avant_d_ecrire_la_moindre_frame(tmp_path):
    """Le chemin reel du defaut: `cli.scan_command` -> `check_scan_conflicts`.

    C'est le seul endroit ou le refus est encore gratuit -- avant l'ecriture des frames
    (`EPIC5-ARB-34`) -- et c'est precisement la que la `KeyError` tombait.
    """
    from mixed_media_utility.io import project_layout, scan_manifest

    project_layout.ensure_project_layout(tmp_path)
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        scan_manifest.check_scan_conflicts(tmp_path, _pile_mixte())
    assert capture.value.reason == reconstruction.REFUS_PILE_MIXTE
    assert LIBELLES[0] in str(capture.value)


# ---------------------------------------------------------------------------
# AC 10 -- les frontieres negatives
# ---------------------------------------------------------------------------


def test_le_refus_ne_mord_pas_sur_une_pile_de_planches_seules():
    """Frontiere negative 1: le regime nominal du scan ne bouge pas d'un cran."""
    planches = [_planche(page_index=rang, page_count=3) for rang in range(3)]
    assert reconstruction._check_pile_homogene(planches) is None
    # Et la lecture aboutit vraiment, jusqu'a la reference de niveau lot: une garde qui
    # rendrait `None` en refusant plus loin passerait l'assertion ci-dessus.
    reference = reconstruction._check_lot_consistency(planches)
    assert reference["lot_id"] == "lot_temoin_0001"
    assert reference["fps_target"] == 24.0


def test_le_refus_de_pile_mixte_ne_mord_pas_sur_la_page_de_calibration_seule():
    """Frontiere negative 2: une passe qui ne porte que la page de calibration.

    C'est le regime nominal de `scan ... calibrate`, et il ne doit pas recevoir le refus
    de pile **mixte** -- qui lui dirait de separer une pile deja separee. Il recoit son
    propre motif, distinct, qui nomme le bon geste.
    """
    seules = [
        _page_de_calibration(page_index=0, page_count=2, libelle=LIBELLES[0]),
        _page_de_calibration(page_index=1, page_count=2, libelle=LIBELLES[1]),
    ]
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction._check_pile_homogene(seules)
    assert capture.value.reason == reconstruction.REFUS_PILE_SANS_PLANCHE
    assert capture.value.reason != reconstruction.REFUS_PILE_MIXTE
    assert "calibrate" in str(capture.value)
    # Les deux codes sont **distincts au litteral**: identiques, l'assertion ci-dessus
    # serait vraie par accident et les deux refus se confondraient pour tout appelant.
    assert reconstruction.REFUS_PILE_MIXTE != reconstruction.REFUS_PILE_SANS_PLANCHE


def test_la_garde_couvre_chacun_des_cinq_champs_pris_isolement():
    """L'invariant qui porte toute l'AC 10, epingle par les deux bouts.

    Le defaut vient de ce que `_LOT_LEVEL_FIELDS` **contient** les cinq champs de
    `CALIBRATION_ABSENT_FIELDS`: c'est ce qui faisait lever `_check_lot_consistency`, et
    c'est aussi ce qui permet a la garde de reconnaitre une page sans identite de lot.
    Un champ retire du premier ensemble creerait une page de calibration que la garde ne
    verrait plus -- et la `KeyError` reviendrait par la fenetre, sur ce champ-la seul.

    Les cinq sont exerces **un par un** et non en bloc: une page a qui il manque les
    cinq serait attrapee par n'importe lequel des cinq tests d'appartenance, donc un
    ensemble ampute resterait vert.
    """
    assert CHAMPS <= set(reconstruction._LOT_LEVEL_FIELDS), sorted(CHAMPS)
    for champ in sorted(CHAMPS):
        pile = [_planche(page_index=rang, page_count=3) for rang in range(3)]
        # La cible en **deuxieme** position, jamais en premiere (regle des fabriques).
        ampute = dict(pile[1])
        del ampute[champ]
        pile[1] = ampute
        with pytest.raises(reconstruction.ReconstructionError) as capture:
            reconstruction._check_pile_homogene(pile)
        assert capture.value.reason == reconstruction.REFUS_PILE_MIXTE, champ
        assert "page_index=1" in str(capture.value), champ


def test_scan_calibrate_ne_passe_pas_par_la_garde_de_pile():
    """Le regime nominal de `scan ... calibrate` reste vert **par construction**.

    Verifie au source plutot qu'en montant un scan complet: la sous-commande ne
    reconstruit aucun lot, donc elle n'atteint ni `check_scan_conflicts` ni la garde. Si
    elle venait a y passer un jour, une pile de calibration seule la ferait refuser, et
    c'est ce test qui le dirait.
    """
    # **Story 11.6 (lot B): la sequence a quitte `cli.py`** pour le point d'entree
    # de coeur `scan_calibrate.calibrer_la_chaine` (`EPIC11-ARB-129`). La garde
    # se verifie donc sur les DEUX etages -- l'enveloppeur de terminal et le
    # corps --, sans quoi elle pourrait se glisser dans celui qu'on ne regarde
    # plus.
    appels = {}
    for fichier, nom in (("cli.py", "scan_calibrate_command"),
                         ("scan_calibrate.py", "calibrer_la_chaine"),
                         ("scan_calibrate.py", "consigner_le_profil_de_chaine")):
        arbre = ast.parse((MODULES / fichier).read_text(encoding="utf-8"))
        corps = [n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef) and n.name == nom]
        assert len(corps) == 1, (
            f"{nom} a change de nom: ce test ne mesure plus rien")
        appels[nom] = {ast.unparse(n.func)
                       for n in ast.walk(corps[0]) if isinstance(n, ast.Call)}
        assert not any("check_scan_conflicts" in appel
                       for appel in appels[nom]), (nom, sorted(appels[nom]))
    # Temoin positif: le balayage voit bien des appels dans ces corps. Sans lui, un corps
    # vide ou une extraction muette rendrait l'assertion vraie par vacuite.
    assert any("ingest_scan_lot" in appel
               for appel in appels["calibrer_la_chaine"]), appels
    assert any("_fit_lot_correction" in appel
               for appel in appels["consigner_le_profil_de_chaine"]), appels


# ---------------------------------------------------------------------------
# AC 10 -- le balayage de la famille des acces indexes nus
# ---------------------------------------------------------------------------

_BASE_PAYLOAD = re.compile(r"(?:^|_)payloads?$")


def _identifiants(noeud: ast.AST) -> set[str]:
    """Tous les identifiants d'une expression, noms et attributs confondus."""
    trouves: set[str] = set()
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Name):
            trouves.add(sous.id)
        elif isinstance(sous, ast.Attribute):
            trouves.add(sous.attr)
    return trouves


def _collections_de_champs(arbre: ast.AST) -> set[str]:
    """Noms lies a une collection litterale de chaines **contenant** l'un des champs.

    C'est ce qui fait que le balayage voit le defaut d'origine. Le code fautif ne
    contenait aucun litteral `'project_id'`: il ecrivait `payloads[0][field]` dans une
    boucle sur `_LOT_LEVEL_FIELDS`. Un balayage qui ne chercherait que des cles
    constantes -- le premier reflexe -- serait passe a cote des six occurrences.
    """
    dangereuses: set[str] = set()
    for noeud in ast.walk(arbre):
        cibles: list[ast.expr] = []
        valeur: ast.expr | None = None
        if isinstance(noeud, ast.Assign):
            cibles, valeur = noeud.targets, noeud.value
        elif isinstance(noeud, ast.AnnAssign) and noeud.value is not None:
            cibles, valeur = [noeud.target], noeud.value
        if valeur is None:
            continue
        # `frozenset((...))`, `tuple([...])`: on descend jusqu'au litteral.
        while isinstance(valeur, ast.Call) and valeur.args:
            valeur = valeur.args[0]
        if not isinstance(valeur, (ast.Tuple, ast.List, ast.Set)):
            continue
        litteraux = {e.value for e in valeur.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if litteraux & CHAMPS:
            dangereuses |= {c.id for c in cibles if isinstance(c, ast.Name)}
    return dangereuses


def _variables_de_boucle(arbre: ast.AST, dangereuses: set[str]) -> set[str]:
    """Variables liees par une iteration sur l'une de ces collections."""
    liees: set[str] = set()
    for noeud in ast.walk(arbre):
        iterations: list[tuple[ast.expr, ast.expr]] = []
        if isinstance(noeud, (ast.For, ast.AsyncFor)):
            iterations = [(noeud.target, noeud.iter)]
        elif isinstance(noeud, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            iterations = [(g.target, g.iter) for g in noeud.generators]
        for cible, iterable in iterations:
            base = iterable
            while isinstance(base, ast.Call) and base.args:
                base = base.args[0]
            if _identifiants(base) & dangereuses and isinstance(cible, ast.Name):
                liees.add(cible.id)
    return liees


def _alias_et_parametres(arbres: dict[pathlib.Path, ast.Module],
                         dangereuses: set[str]) -> set[str]:
    """Propager la dangerosite **par alias et par passage de parametre**, jusqu'au point fixe.

    Sans cette passe le balayage dependrait d'une coincidence de nommage: `_require_fields`
    recoit sa liste de champs en parametre, et ne serait vue que parce qu'un autre module
    appelle « fields » sa propre liste locale. Un simple renommage ailleurs aurait alors
    rendu le balayage aveugle **en restant vert**, ce qui est le pire mode de panne pour
    une garde de cette famille.

    Deux regles, appliquees jusqu'a stabilisation:

    * `x = COLLECTION_DANGEREUSE` rend `x` dangereux (alias direct);
    * `f(..., COLLECTION_DANGEREUSE, ...)` rend dangereux le parametre correspondant de
      **toute** fonction du depot nommee `f` -- le depot n'a pas deux fonctions de meme
      nom prenant l'une une liste de champs et l'autre autre chose, et surestimer est ici
      le bon sens de l'erreur: un acces de trop se declare, un acces manque ne se voit pas.
    """
    signatures: dict[str, list[str]] = {}
    for arbre in arbres.values():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = noeud.args
                signatures[noeud.name] = [
                    a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]

    courant = set(dangereuses)
    for _tour in range(8):
        avant = len(courant)
        for arbre in arbres.values():
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Assign) and isinstance(noeud.value, (ast.Name, ast.Attribute)):
                    if _identifiants(noeud.value) & courant:
                        courant |= {c.id for c in noeud.targets if isinstance(c, ast.Name)}
                elif isinstance(noeud, ast.Call):
                    nom = ast.unparse(noeud.func).rsplit(".", 1)[-1]
                    parametres = signatures.get(nom)
                    if parametres is None:
                        continue
                    for rang, argument in enumerate(noeud.args):
                        if rang < len(parametres) and _identifiants(argument) & courant:
                            courant.add(parametres[rang])
                    for mot_clef in noeud.keywords:
                        if mot_clef.arg and _identifiants(mot_clef.value) & courant:
                            courant.add(mot_clef.arg)
        if len(courant) == avant:
            break
    return courant


def _modules_de_production() -> dict[pathlib.Path, ast.Module]:
    return {chemin: ast.parse(chemin.read_text(encoding="utf-8"))
            for chemin in sorted(MODULES.rglob("*.py"))}


def _acces_nus(arbres: dict[pathlib.Path, ast.Module]) -> list[tuple[str, str, str]]:
    """Tout acces indexe **nu** a l'un des cinq champs, sur une base de payload.

    Rend `(chemin, fonction englobante, expression)`, une entree par occurrence.
    """
    dangereuses: set[str] = set()
    for arbre in arbres.values():
        dangereuses |= _collections_de_champs(arbre)
    dangereuses = _alias_et_parametres(arbres, dangereuses)

    trouves: list[tuple[str, str, str]] = []
    for chemin, arbre in arbres.items():
        liees = _variables_de_boucle(arbre, dangereuses)
        portee: dict[int, str] = {}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for ligne in range(noeud.lineno, (noeud.end_lineno or noeud.lineno) + 1):
                    portee[ligne] = noeud.name
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Subscript):
                continue
            cle = noeud.slice
            if isinstance(cle, ast.Constant) and cle.value in CHAMPS:
                pass
            elif isinstance(cle, ast.Name) and cle.id in liees:
                pass
            else:
                continue
            if not any(_BASE_PAYLOAD.search(nom) for nom in _identifiants(noeud.value)):
                continue
            trouves.append((
                chemin.relative_to(MODULES).as_posix(),
                portee.get(noeud.lineno, "<module>"),
                ast.unparse(noeud),
            ))
    return trouves


def _gardes_de_la_fonction(arbre: ast.Module, nom: str) -> str:
    """Le texte de toutes les conditions ecrites dans cette fonction, concatene."""
    morceaux: list[str] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) or noeud.name != nom:
            continue
        for sous in ast.walk(noeud):
            if isinstance(sous, ast.If):
                morceaux.append(ast.unparse(sous.test))
            elif isinstance(sous, (ast.ListComp, ast.SetComp, ast.DictComp,
                                   ast.GeneratorExp)):
                morceaux += [ast.unparse(c) for g in sous.generators for c in g.ifs]
            elif isinstance(sous, ast.BoolOp):
                morceaux += [ast.unparse(v) for v in sous.values]
    return "\n".join(morceaux)


#: Sentinelle: l'acces n'est pas garde **dans** sa fonction mais par un appel place
#: avant elle chez chacun de ses appelants. C'est le seul cas du depot, et il est
#: verifie a part, par `test_tout_appelant_de_check_lot_consistency_garde_la_pile`.
GARDE_EN_AMONT = "@amont:_check_pile_homogene"

#: **L'inventaire exact des acces indexes nus survivants**, chacun avec la garde qui le
#: rend inatteignable par une page de calibration. Ce n'est pas une liste blanche: la
#: garde declaree est **verifiee au source** (ou, pour la sentinelle ci-dessus, par le
#: balayage des appelants). Retirer une garde sans retirer son entree rend le lot rouge,
#: et ajouter un septieme acces nu le rend rouge aussi -- c'est tout l'objet de l'AC 10.
_ACCES_NUS_ATTENDUS: dict[tuple[str, str, str], tuple[int, str]] = {
    # `validate_payload` ecrit le contrat lui-meme: les cinq champs ne sont lus que
    # dans la branche des planches d'images, la ou ils sont exiges. La branche `c` est
    # traitee juste au-dessus, et y **refuse** leur presence.
    ("io/payload.py", "validate_payload", "payload['project_id']"): (2, "not calibration"),
    ("io/payload.py", "validate_payload", "payload['rush_id']"): (2, "not calibration"),
    ("io/payload.py", "validate_payload", "payload['lot_id']"): (2, "not calibration"),
    ("io/payload.py", "validate_payload", "payload['fps_target']"): (1, "not calibration"),
    # Story 2.7 (payload 2.1, EPIC7-ARB-56): meme garde que `fps_target` juste
    # au-dessus, meme motif -- la cadence source n'est lue que dans la branche des
    # planches d'images.
    ("io/payload.py", "validate_payload", "payload['timecode_base_fps']"): (
        1, "not calibration"),
    # `_require_fields` teste l'appartenance dans la meme expression, avant de lire:
    # le court-circuit du `or` est la garde, et elle est locale.
    ("io/reconstruction.py", "_require_fields", "payload[field]"): (1, "field not in payload"),
    # `_lot_identity` ne lit le champ que sur les pages qui le declarent, et refuse
    # nommement quand aucune ne le declare (cinquieme acces nu de la famille, ferme le
    # 2026-08-18).
    ("scan_output_frames.py", "_lot_identity", "page.payload[field]"): (
        1, "field in page.payload"),
    # Les trois du defaut de l'AC 10. Ils restent **intacts au caractere** -- la story
    # 5.16 a pose une garde d'egalite au source sur cette fonction -- et c'est
    # `_check_pile_homogene`, appelee par chacun de ses appelants, qui les met hors
    # d'atteinte d'une page de calibration.
    ("io/reconstruction.py", "_check_lot_consistency", "payloads[0][field]"): (
        1, GARDE_EN_AMONT),
    ("io/reconstruction.py", "_check_lot_consistency", "payload[field]"): (
        2, GARDE_EN_AMONT),
    # Story 11.6, lot E (`tui/atelier_scan_ecriture.dossier_de_sortie`), pose a
    # la liaison du 2026-09-01. Septieme occurrence de la famille, attrapee par
    # cette frontiere avant toute page de calibration reelle -- ce qui est
    # exactement ce pour quoi elle existe. La garde est locale et **nomme les
    # champs manquants** au lieu de laisser une `KeyError` nue remonter : le
    # payload d'une page de calibration ne porte aucun des trois, et
    # `io/payload.validate_payload` en refuse la presence sur cette branche.
    ("tui/atelier_scan_ecriture.py", "dossier_de_sortie", "payload['rush_id']"): (
        1, "champ not in payload"),
    ("tui/atelier_scan_ecriture.py", "dossier_de_sortie", "payload['fps_target']"): (
        1, "champ not in payload"),
    ("tui/atelier_scan_ecriture.py", "dossier_de_sortie", "payload['lot_id']"): (
        1, "champ not in payload"),
    # Story 11.7, `EPIC11-ARB-178` (`io/payload.sheets_pdf_filename_from_payload`,
    # commit `8fb443e5`). **Huitieme occurrence de la famille, et le tri a ete
    # fait avant la declaration** : ces trois acces sont-ils atteignables par
    # une charge utile a qui il manque une cle ? Non, et la garde est LOCALE,
    # dans la meme fonction, deux lignes au-dessus -- la comprehension
    # `manquants` refuse **avant** toute indexation, en NOMMANT les champs
    # absents (`PayloadValidationError`, jamais une `KeyError` nue), ce que le
    # depot exige d'un refus depuis `EPIC5-ARB-85`. Elle est de surcroit
    # doublee en amont par le refus des pages de calibration, qui tombe le
    # premier pour que le message parle de la calibration plutot que d'un
    # `project_id` absent.
    #
    # **Elle est plus forte que les gardes voisines sur un point** : elle
    # refuse la chaine VIDE autant que la cle absente (`not payload.get(champ)`
    # et non `champ not in payload`), parce qu'une chaine vide traverserait
    # jusqu'a `io/naming`, dont la garde leve une `NamingError` -- une autre
    # famille d'exception que celle que la fonction declare. Le mutant qui
    # remplace l'un par l'autre est mesure par
    # `test_une_charge_utile_TRONQUEE_est_refusee_en_nommant_le_champ`.
    #
    # `template_id` est lu nu lui aussi et par la meme garde, mais il n'est pas
    # l'un des cinq `CALIBRATION_ABSENT_FIELDS` : le balayage ne le voit pas, et
    # l'inventaire ne l'invente pas.
    ("io/payload.py", "sheets_pdf_filename_from_payload", "payload['project_id']"): (
        1, "not payload.get(champ)"),
    ("io/payload.py", "sheets_pdf_filename_from_payload", "payload['rush_id']"): (
        1, "not payload.get(champ)"),
    ("io/payload.py", "sheets_pdf_filename_from_payload", "payload['lot_id']"): (
        1, "not payload.get(champ)"),
}


def test_le_balayage_ne_trouve_aucun_acces_nu_hors_de_l_inventaire():
    """AC 10, seconde puce: **le balayage est l'assertion**.

    Sixieme occurrence de la meme famille en cinq corrections. Un septieme acces nu
    ajoute n'importe ou sous `src/mixed_media_utility` rend ce test rouge, avec son
    chemin, sa fonction et son expression -- il n'attend pas qu'une page de calibration
    tombe dessus en production.
    """
    trouves = _acces_nus(_modules_de_production())
    comptes: dict[tuple[str, str, str], int] = {}
    for entree in trouves:
        comptes[entree] = comptes.get(entree, 0) + 1
    attendus = {cle: nombre for cle, (nombre, _motif) in _ACCES_NUS_ATTENDUS.items()}
    assert comptes == attendus, {
        "non declares": sorted(set(comptes) - set(attendus)),
        "declares et disparus": sorted(set(attendus) - set(comptes)),
        "cardinal different": sorted(
            cle for cle in set(comptes) & set(attendus) if comptes[cle] != attendus[cle]),
    }


def test_chaque_acces_nu_survivant_porte_la_garde_qu_il_declare():
    """L'inventaire n'est pas une liste blanche: chaque garde est relue au source.

    Sans ce test, il suffirait de supprimer un `if not calibration:` pour rouvrir la
    `KeyError` sans qu'aucune assertion ne bouge -- l'inventaire, lui, resterait exact.
    """
    arbres = {chemin.relative_to(MODULES).as_posix(): arbre
              for chemin, arbre in _modules_de_production().items()}
    verifiees = 0
    for (fichier, fonction, expression), (_nombre, motif) in _ACCES_NUS_ATTENDUS.items():
        if motif == GARDE_EN_AMONT:
            continue
        gardes = _gardes_de_la_fonction(arbres[fichier], fonction)
        assert motif in gardes, (fichier, fonction, expression, motif, gardes)
        verifiees += 1
    # Le balayage doit avoir verifie quelque chose: une extraction muette rendrait la
    # boucle vide et ce test vrai par vacuite.
    # Story 2.7: sept depuis l'ajout de l'entree `timecode_base_fps` (etait six).
    # **Dix depuis la liaison du 2026-09-01** : les trois lectures de
    # `tui/atelier_scan_ecriture.dossier_de_sortie`, gardees par le refus qui
    # nomme les champs manquants. **Treize depuis `EPIC11-ARB-178`** : les trois
    # lectures de `io/payload.sheets_pdf_filename_from_payload`, gardees par la
    # comprehension `manquants` de la meme fonction. Ce cardinal ecrit en clair
    # est ce qui rend une entree ajoutee SANS garde impossible a passer en
    # silence.
    assert verifiees == 13, verifiees


def test_tout_appelant_de_check_lot_consistency_garde_la_pile():
    """La sentinelle `@amont` est **verifiee**, pas declaree sur parole.

    Chaque appel a `_check_lot_consistency` dans le depot doit etre precede, dans le
    corps de la meme fonction, d'un appel a `_check_pile_homogene`. C'est ce qui rend les
    trois acces nus de `_check_lot_consistency` inatteignables par une page de
    calibration -- et un troisieme appelant ajoute sans la garde rend ce test rouge.
    """
    appelants: list[tuple[str, str]] = []
    for chemin, arbre in _modules_de_production().items():
        nom_fichier = chemin.relative_to(MODULES).as_posix()
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lignes_consistency = [
                appel.lineno for appel in ast.walk(noeud)
                if isinstance(appel, ast.Call)
                and "_check_lot_consistency" in ast.unparse(appel.func)]
            if not lignes_consistency:
                continue
            lignes_garde = [
                appel.lineno for appel in ast.walk(noeud)
                if isinstance(appel, ast.Call)
                and "_check_pile_homogene" in ast.unparse(appel.func)]
            appelants.append((nom_fichier, noeud.name))
            assert lignes_garde, (nom_fichier, noeud.name, "aucune garde de pile")
            assert min(lignes_garde) < min(lignes_consistency), (
                nom_fichier, noeud.name, lignes_garde, lignes_consistency)
    # Les deux appelants du depot, nommes: si l'un disparaissait, ce test se mettrait a
    # ne plus rien mesurer en restant vert.
    assert sorted(appelants) == [
        ("io/reconstruction.py", "reconstruct_project_manifest"),
        ("io/scan_manifest.py", "check_scan_conflicts"),
    ], sorted(appelants)


# ---------------------------------------------------------------------------
# Le balayage est-il capable de voir ? Temoins negatifs.
# ---------------------------------------------------------------------------


def _balayer_source(source: str, nom: str = "temoin.py") -> list[tuple[str, str, str]]:
    """Faire tourner le balayage sur une source synthetique, hors du depot."""
    arbre = ast.parse(source)
    faux_chemin = MODULES / nom
    return _acces_nus({faux_chemin: arbre})


@pytest.mark.parametrize("champ", sorted(CHAMPS))
def test_le_balayage_voit_un_acces_nu_par_cle_constante(champ):
    """Un champ retire de la liste balayee doit faire echouer ce test, champ par champ.

    Parametre sur les cinq: un balayage qui n'en chercherait qu'une partie resterait vert
    sur une assertion ecrite sur un seul.
    """
    trouves = _balayer_source(f"def f(payload):\n    return payload[{champ!r}]\n")
    assert [entree[2] for entree in trouves] == [f"payload[{champ!r}]"], (champ, trouves)


@pytest.mark.parametrize("champ", sorted(CHAMPS))
def test_le_balayage_voit_un_acces_nu_par_variable_de_boucle(champ):
    """La forme **reelle** du defaut: la cle est une variable, jamais un litteral.

    C'est la moitie du balayage qu'un grep n'a pas. Sans elle, les trois acces de
    `_check_lot_consistency` -- ceux qui levaient les 62 `KeyError` -- seraient invisibles.
    """
    source = (
        f"CHAMPS_DE_LOT = ('template_id', {champ!r})\n"
        "def f(payloads):\n"
        "    return {c: payloads[0][c] for c in CHAMPS_DE_LOT}\n"
    )
    trouves = _balayer_source(source)
    assert [entree[2] for entree in trouves] == ["payloads[0][c]"], (champ, trouves)


def test_le_balayage_ignore_ce_qui_n_est_pas_un_payload():
    """Une cle de niveau lot deja consolidee n'est pas un chemin de page.

    Sans cette borne le balayage crierait sur les cinquante lectures legitimes de
    `reference[...]`, `identity[...]` ou `lot[...]`, et l'AC 10 aurait accouche d'un test
    que personne ne pourrait garder vert.
    """
    assert _balayer_source("def f(reference):\n    return reference['lot_id']\n") == []
    assert _balayer_source("def f(lot):\n    return lot['rush_id']\n") == []


def test_le_balayage_visite_tous_les_modules_de_production():
    """Un balayage qui ne regarde qu'un fichier est le mutant le plus facile a ecrire.

    Il est aussi le plus silencieux: le lot resterait entierement vert. On epingle donc
    l'ensemble **exact** des modules parcourus contre celui du disque.
    """
    parcourus = set(_modules_de_production())
    sur_disque = set(MODULES.rglob("*.py"))
    assert parcourus == sur_disque
    assert len(parcourus) > 20, len(parcourus)
    # Et les modules ou la famille a deja mordu sont dedans, nommement.
    for nom in ("io/reconstruction.py", "io/payload.py", "scan_output_frames.py",
                "scan_detection.py", "cli.py"):
        assert MODULES / nom in parcourus, nom


# ---------------------------------------------------------------------------
# Correctifs de revue -- les trois gardes annoncees « mordantes » et jamais mesurees
# ---------------------------------------------------------------------------
#
# Les trois findings ont la meme forme, celle que le depot dit avoir payee huit fois:
# **un commentaire de production revendique une garde, et aucun test ne l'exerce**. Les
# trois mutants correspondants (`P14`, `P18`/`P19`, `P20` de la couche 1 du lot B)
# survivaient a tous les lots essayes, `test_payload_short_keys.py` (48 s) compris.


def _payload_de_calibration_ecrit_a_la_main(*, libelle: str | None = LIBELLES[1],
                                            **surcharges) -> dict:
    """Un payload de role `c` **construit a la main**, hors de toute fabrique.

    C'est le seul moyen d'exercer `validate_payload` sur ce que la fabrique interdit par
    construction: elle retire elle-meme les cinq champs de lot et impose le libelle.
    Le chemin vise est celui qu'un **document relu** emprunte -- `parse_payload` appelle
    `validate_payload` sans passer par `build_page_payload` --, et c'est precisement
    celui qui n'etait mesure par rien.
    """
    payload = {
        "schema_version": payload_io.PAYLOAD_SCHEMA_VERSION,
        "page_index": 1,
        "page_count": 2,
        "page_role": page_roles.PAGE_ROLE_CALIBRATION,
        "template_id": "tpl-a4-portrait-4f-v2",
        "patch_preset_id": "patches-14-v3",
        "target_colorspace": "rec709",
        "gamut_map_id": payload_io.GAMUT_MAP_IDENTITY,
        "slots": [],
    }
    if libelle is not None:
        payload[payload_io.SCAN_CHAIN_LABEL_FIELD] = libelle
    payload.update(surcharges)
    return payload


def test_la_fabrique_a_la_main_est_acceptee_telle_quelle():
    """Temoin positif des trois familles ci-dessous, et il n'est pas decoratif.

    Sans lui, chacun des refus qui suivent pourrait tomber pour une raison etrangere au
    champ que le test croit exercer -- un `template_id` mal ecrit, par exemple -- et la
    garde visee resterait non mesuree sous un test vert.
    """
    payload_io.validate_payload(_payload_de_calibration_ecrit_a_la_main())


@pytest.mark.parametrize("champ", sorted(CHAMPS))
def test_une_page_de_calibration_qui_declare_un_champ_de_lot_est_refusee(champ):
    """Mutant `P20`: le refus devient un `continue` silencieux, et rien ne bouge.

    Le commentaire de production annonce ce que ce test mesure: « present, il doit etre
    refuse plutot qu'ignore -- sans quoi une page de calibration pourrait declarer un lot
    en silence et **le regime d'avant reviendrait par la fenetre** ». Le regime en
    question est celui que `EPIC5-ARB-82` supprime.

    La consequence exacte de l'absence de garde, mesuree: le payload serait accepte,
    puis range en `porteuses` par `_partition_de_la_pile` -- donc traite comme une
    **planche d'images**, avec un `lot_id` qui n'a plus de sens.

    Les cinq champs sont exerces **un par un** (meme motif que la garde de pile
    ci-dessus): un payload qui les porterait tous les cinq serait attrape par
    n'importe lequel des cinq refus, donc un ensemble ampute resterait vert.
    """
    valeurs = {"project_id": "projet_demo", "rush_id": "rush_temoin",
               "lot_id": "lot_temoin_0001", "fps_target": 24.0,
               # Story 2.7: cinquieme champ de lot desormais absent d'une page de
               # calibration (EPIC7-ARB-56) -- meme motif que ses quatre voisins.
               "timecode_base_fps": "25/1"}
    payload = _payload_de_calibration_ecrit_a_la_main(**{champ: valeurs[champ]})
    with pytest.raises(payload_io.PayloadValidationError) as capture:
        payload_io.validate_payload(payload)
    message = str(capture.value)
    assert f"'{champ}'" in message, message
    assert "must be absent" in message, message
    # Le motif nomme le tirage et le geste (`EPIC5-ARB-90`), et non une avarie: une
    # feuille qui declare encore ce champ est conforme a **son** tirage.
    assert "EPIC5-ARB-90" in message, message
    assert "Reimprimez" in message, message


def test_une_page_de_calibration_declarant_un_lot_serait_prise_pour_une_planche():
    """Ce que le refus ci-dessus empeche, mesure plutot qu'affirme.

    La partition se lit **sur les champs**: un payload de role `c` qui porte les cinq
    champs de lot est range en `porteuses` et traverse `_check_pile_homogene` sans le
    moindre refus. C'est exactement « le regime d'avant revient par la fenetre », et
    c'est ce qui rend le refus de `validate_payload` porteur au lieu d'etre decoratif.

    Le pendant chaine complete: une telle feuille n'atteint jamais cette partition,
    parce que `validate_payload` la refuse au decodage du QR.
    """
    ancien = dict(_planche(page_index=1, page_count=2))
    ancien["page_role"] = page_roles.PAGE_ROLE_CALIBRATION
    ancien["slots"] = []
    sans_identite, porteuses = reconstruction._partition_de_la_pile([ancien])
    assert sans_identite == [], sans_identite
    assert porteuses == [ancien]
    # Aucun refus: la garde de pile ne la voit pas passer, et c'est le fait mesure.
    reconstruction._check_pile_homogene([ancien, _planche(page_index=0, page_count=2)])


def test_une_page_de_calibration_sans_libelle_de_chaine_est_refusee():
    """Mutant `P18`: l'**exigence** du libelle sous le role `c`, jamais mesuree.

    Le commentaire de production revendique les deux sens (« un seul des deux laisserait
    exprimable soit une page de calibration anonyme, soit une planche d'images qui se
    declare feuille de calibration »); c'est le premier des deux.

    Le refus cote fabrique (`build_page_payload`) est teste ailleurs, mais c'est le
    **chemin d'ecriture**. `validate_payload` est celui qu'un document relu traverse
    sans passer par la fabrique, et c'est celui qui n'avait rien.
    """
    payload = _payload_de_calibration_ecrit_a_la_main(libelle=None)
    with pytest.raises(payload_io.PayloadValidationError) as capture:
        payload_io.validate_payload(payload)
    message = str(capture.value)
    assert "scan_chain_label" in message, message
    assert "missing" in message, message
    # Le motif de l'ancien tirage: la feuille est conforme a son epoque, sa geometrie
    # n'est pas en cause, et le geste est de la reimprimer (`EPIC5-ARB-90`).
    assert "EPIC5-ARB-90" in message, message
    assert "5.23" in message, message
    assert "Reimprimez" in message, message


def test_une_planche_d_images_qui_declare_une_chaine_de_scan_est_refusee():
    """Mutant `P19`: le **refus** du libelle hors du role `c`, jamais mesure.

    Le second sens de la meme garde. Sans lui, une planche d'images se declarerait
    feuille de calibration a la relecture: la partition la rangerait toujours en
    `porteuses` (elle porte ses cinq champs), mais tout ce qui lit `page_role`
    -- `_read_calibration_pages`, `_declared_calibration_pages`, la geometrie de page --
    la prendrait pour la feuille de calibration du lot.

    Le payload est **une vraie planche**, produite par la fabrique, a qui on ajoute le
    seul champ interdit: aucune autre difference ne peut expliquer le refus.
    """
    planche = dict(_planche(page_index=1, page_count=2))
    planche[payload_io.SCAN_CHAIN_LABEL_FIELD] = LIBELLES[0]
    with pytest.raises(payload_io.PayloadValidationError) as capture:
        payload_io.validate_payload(planche)
    message = str(capture.value)
    assert "scan_chain_label" in message, message
    assert "must be absent" in message, message
    # Temoin positif: la meme planche **sans** le champ passe. Sans lui, le refus
    # ci-dessus pourrait venir de n'importe quoi d'autre dans le payload.
    payload_io.validate_payload(_planche(page_index=1, page_count=2))


@pytest.mark.parametrize("champ", sorted(CHAMPS))
def test_une_planche_d_images_amputee_d_un_champ_de_lot_est_refusee_a_la_relecture(champ):
    """Mutant `P14`: la branche « planche d'images » de `_validate_page_payload`.

    Ce n'est pas une garde secondaire, c'est **l'argument porteur** du choix de lire la
    partition sur les champs plutot que sur le role -- le docstring de
    `_check_pile_homogene` le dit mot pour mot: « un payload de planche d'images tronque
    ne peut pas se faufiler ici pour autant: `_validate_page_payload` passe avant et
    refuse deja une planche a qui il manque l'un des cinq ».

    Consequence mesuree de sa disparition: `_partition_de_la_pile` range la planche
    amputee dans `sans_identite`, et l'operateur recoit `REFUS_PILE_MIXTE`, c'est-a-dire
    « tu as melange deux types de feuilles ». **Une corruption annoncee comme une erreur
    de geste** envoie chercher au mauvais endroit -- et le geste propose (« scannez la
    page de calibration dans une passe separee ») ne corrige rien.

    Le pendant positif -- l'allegement de la liste sous le role `c` -- est deja teste;
    ce test est le negatif, qui manquait. La cible est en **deuxieme** position parmi
    trois planches (regle des fabriques).
    """
    pile = [_planche(page_index=rang, page_count=3) for rang in range(3)]
    ampute = dict(pile[1])
    del ampute[champ]
    pile[1] = ampute
    with pytest.raises(reconstruction.ReconstructionError) as capture:
        reconstruction._validate_page_payload(ampute)
    message = str(capture.value)
    assert champ in message, message
    assert "page_index=1" in message, message
    # **Ce n'est pas un refus de pile.** L'exception d'une garde de payload ne porte
    # aucun code de refus de pile: c'est ce qui distingue « ta feuille est abimee » de
    # « tu as melange deux types de feuilles ».
    assert getattr(capture.value, "reason", None) != reconstruction.REFUS_PILE_MIXTE
    # Et le temoin de ce que la garde empeche: sans elle, cette meme pile ressort en
    # refus de pile mixte, qui designe la mauvaise cause.
    with pytest.raises(reconstruction.ReconstructionError) as pile_capture:
        reconstruction._check_pile_homogene(pile)
    assert pile_capture.value.reason == reconstruction.REFUS_PILE_MIXTE


def test_une_planche_d_images_complete_traverse_la_garde_de_payload():
    """Temoin positif du parametrage ci-dessus: une planche entiere n'est pas refusee.

    Sans lui, les cinq refus passeraient aussi bien si `_validate_page_payload` avait
    cesse d'accepter quoi que ce soit.
    """
    for rang in range(3):
        reconstruction._validate_page_payload(_planche(page_index=rang, page_count=3))


def test_une_page_de_calibration_conforme_traverse_la_garde_de_payload():
    """Le pendant du precedent sous le role `c`: l'allegement de la liste tient.

    Les deux temoins ensemble bornent la garde des deux cotes: la liste est **entiere**
    pour une planche, **allegee** pour une page de calibration, et ni l'une ni l'autre
    ne se refuse quand elle est conforme.
    """
    for rang, libelle in enumerate(LIBELLES):
        reconstruction._validate_page_payload(
            _page_de_calibration(page_index=rang, page_count=2, libelle=libelle))


# ---------------------------------------------------------------------------
# Story 5.23, AC 8bis -- le cardinal du contrat, epingle **en litteral**
# ---------------------------------------------------------------------------


def test_les_cinq_champs_absents_de_la_page_de_calibration_sont_ceux_declares():
    """AC 8bis: egalite d'**ensembles** en litteral, jamais une inclusion, jamais derivee.

    **Ce test existe parce que le contrat n'etait epingle nulle part en litteral**
    (`EPIC5-ARB-100`, injection par AC du 2026-08-19). Retirer `fps_target` de
    `CALIBRATION_ABSENT_FIELDS` -- c'est-a-dire rouvrir a la page de calibration le droit
    de declarer une cadence, ce que l'AC 8bis interdit nommement -- survivait a tout lot
    court. Toutes les references du depot (`CHAMPS` de ce fichier compris) **derivent** de
    la constante: un retrait la reduit des deux cotes a la fois, et le balayage cesse de
    chercher le champ retire sans qu'aucune assertion ne tombe. C'est la tautologie payee
    trois fois dans ce depot, et elle se ferme d'un cote en ecrivant le litteral.

    Le mutant n'etait tue que par `test_calibration_page_on_demand.py`, **12,2 s**, qui
    compose une vraie page. Ici, la meme propriete coute une microseconde.

    **Story 2.7** (payload 2.1, `EPIC7-ARB-56`) ajoute un cinquieme champ, `timecode_base_fps`
    -- la cadence source du rush est elle aussi un champ de lot, absent d'une page de
    calibration pour le meme motif que ses quatre voisins.

    L'ensemble complementaire est epingle dans le meme mouvement: `scan_chain_label` est
    le champ que le role `c` est **seul** a porter (`EPIC5-ARB-102`), et les deux tables
    se lisent au meme endroit pour ne pas pouvoir diverger.
    """
    assert set(payload_io.CALIBRATION_ABSENT_FIELDS) == {
        "project_id", "rush_id", "lot_id", "fps_target", "timecode_base_fps"}
    assert set(payload_io.CALIBRATION_ONLY_FIELDS) == {"scan_chain_label"}
    assert payload_io.SCAN_CHAIN_LABEL_FIELD == "scan_chain_label"
    # Les deux tables sont **disjointes**: un champ a la fois exige et interdit sous le
    # role `c` rendrait `validate_payload` inconsistante avec elle-meme.
    assert set(payload_io.CALIBRATION_ABSENT_FIELDS).isdisjoint(
        payload_io.CALIBRATION_ONLY_FIELDS)
