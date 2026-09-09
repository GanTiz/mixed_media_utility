# -*- coding: utf-8 -*-
"""Story 11.14, lot E1 -- la FRONTIERE NEGATIVE des bancs extract/makepdf/previz.

**Un test positif ne verrait jamais revenir l'ancien nom.** Les sept bancs de
cette famille composaient 30 chemins en chaines litterales -- `p / "frames"`,
`"frames/rush-001_4"` -- et regardaient donc, apres le renommage du lot B, des
dossiers qui n'existent plus. Trente d'entre eux rougissaient ; les autres,
plus couteux, restaient **verts** en ayant cesse de mesurer quoi que ce soit.

Rien n'empeche qu'une story ulterieure en reintroduise un, et rien ne le
signalerait : un chemin litteral qui vise le bon dossier passe. C'est
exactement le motif pour lequel `CLAUDE.md` exige une frontiere negative --
« aucun test positif ne verrait revenir un `timeout 5400` ».

## Ce que cette frontiere mesure, et ce qu'elle ne mesure PAS

Elle mesure **deux formes**, et deux seulement, parce que ce sont les deux que
le lot E1 a reellement retirees :

* la **composition** : un litteral `"frames"` ou `"output-frames"` operande
  d'un `/`, argument de `Path(...)`, de `.joinpath(...)`, de `.glob(...)` ou de
  `.rglob(...)` ;
* le **chemin ecrit d'un trait** : un litteral qui porte l'un de ces noms comme
  **segment**, c'est-a-dire suivi ou precede d'un slash.

Elle ne mesure **pas** -- et c'est dit plutot que tu :

* les **cles de document**. `EPIC11-ARB-221` les gele : `frames_dir`,
  `output_frames_dir`, `reconstructions` restent ecrites ainsi, et la cle nue
  `"frames"` du manifeste POC aussi. Le souligne et l'absence de slash les
  mettent hors d'atteinte des deux motifs ci-dessus, **par construction** et non
  par une liste d'exceptions qu'il faudrait tenir a jour ;
* la **prose**. Les docstrings de ce depot expliquent justement pourquoi tel
  banc ne compose plus son chemin, donc ils portent les mots. La mesure est
  faite a l'**AST** et les docstrings en sont exclus -- un grep de texte y
  mordrait et se ferait affaiblir a la premiere phrase (defaut mesure sur
  `tui/jetons.py` a la story 11.0) ;
* les **dossiers de travail** qui ne sont pas des dossiers de projet.
  `tmp_path / "poc-frames"` et `directory / "src-frames"` portent le mot sans
  designer la racine du layout : la frontiere de segment les epargne, comme
  elle epargne `sheet_frames` et `frames-scannees`.

## Le volet POSITIF, sans lequel elle serait vide

Une frontiere qui compte a zero est verte dans un depot ou personne ne fait
rien -- y compris dans un depot ou le lecteur a cesse de lire. Trois mesures
l'en empechent : le lecteur MORD sur un fichier fautif fabrique pour lui, il
epargne un fichier temoin ecrit dans la forme correcte, et la liste des bancs
surveilles est confrontee au disque, pas seulement citee.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "tests" / "unit" / "tui") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests" / "unit" / "tui"))

from mixed_media_utility.io import project_layout  # noqa: E402

from outils_frontiere import _arbre, _docstrings  # noqa: E402

#: Les noms de dossier surveilles : les deux NEUFS et les deux ANCIENS.
#:
#: Les anciens y figurent parce qu'ils sont ce que la story retire ; les neufs
#: y figurent parce qu'un litteral `"extract-frames"` serait exactement la meme
#: faute -- une seconde redaction du nom, donc un second endroit a corriger au
#: renommage suivant, et une occasion de n'en corriger qu'un. La frontiere
#: n'interdit pas un MOT, elle interdit une seconde SOURCE.
#:
#: Ils sont **lus du module qui les porte**, jamais recopies : une frontiere
#: qui recopierait les noms qu'elle surveille cesserait de surveiller le jour
#: ou le module en change -- et resterait verte, puisqu'elle ne trouverait plus
#: rien.
NOMS_DE_DOSSIER_SURVEILLES = frozenset({
    project_layout.EXTRACT_FRAMES_DIRNAME,
    project_layout.SCAN_FRAMES_DIRNAME,
    project_layout.LEGACY_FRAMES_DIRNAME,
    project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME,
})

#: Les bancs de la famille extract / makepdf / previz -- le perimetre du lot
#: E1, nomme et non devine. Un glob attraperait les bancs des autres lots et
#: rendrait cette frontiere rouge pour le travail d'autrui.
BANCS_SURVEILLES = (
    "tests/unit/test_extract_command.py",
    "tests/unit/test_makepdf_noyau.py",
    "tests/unit/outils_identite_makepdf.py",
    "tests/unit/test_makepdf_command.py",
    "tests/unit/test_cadence_previz.py",
    "tests/unit/test_poc_run.py",
    "tests/unit/test_extraction_previz.py",
)

#: `outils_identite_makepdf.py` est la SEULE exception, et elle est nommee
#: plutot que toleree en silence. Ce module doit tourner sous le `src/` d'un
#: commit anterieur pour regenerer une reference : y importer
#: `io.project_layout` ferait exploser la regeneration a l'`ImportError`,
#: c'est-a-dire au moment precis ou l'instrument sert. Il porte donc ses deux
#: noms en clair, dans `DOSSIERS_DE_FRAMES_EXTRAITES`, et la frontiere le sait.
#:
#: L'exception est **bornee a un identifiant**, pas au fichier : tout autre
#: litteral de chemin y reste interdit.
#:
#: `test_makepdf_noyau.py` en porte trois, de nature differente : une table de
#: TRADUCTION doit ecrire le nom d'avant, c'est litteralement son objet, et ses
#: temoins doivent ecrire des cibles que le renommage ne suit PAS -- une cible
#: derivee du module mesure serait tautologique (defaut du lot D3, 2026-09-03).
EXCEPTION_NOMMEE = {
    "tests/unit/outils_identite_makepdf.py": frozenset({
        "DOSSIERS_DE_FRAMES_EXTRAITES"}),
    "tests/unit/test_makepdf_noyau.py": frozenset({
        "TRADUCTIONS_DU_VOCABULAIRE",
        "VOISINS_QUE_LA_TRADUCTION_EPARGNE",
        "DOCUMENT_TEMOIN_DE_LA_CLE_GELEE",
    }),
}

#: Les appels dont un argument litteral est un segment de chemin.
APPELS_DE_CHEMIN = frozenset({"Path", "joinpath", "glob", "rglob", "mkdir"})

#: Le nom surveille **adjacent a un slash**, dans un sens ou dans l'autre.
#:
#: La frontiere de mot exclut `[\w.-]` de part et d'autre, et ce sont les trois
#: classes qui separent un chemin de son voisin : `vieux-frames/` echappe par le
#: tiret, `artifacts.frames_dir` par le point et le souligne, `sheet_frames` par
#: le souligne. C'est le meme motif que celui des tables de traduction, et pour
#: la meme raison -- une traduction par sous-chaine renommerait ces trois-la
#: (defaut n°2 du lot A : `lot` attrapait `slot`).
#:
#: **Un simple `split("/")` ne suffisait pas**, et la mutation l'a montre : il
#: exige que le segment soit SEUL entre deux slashs, donc il ne voyait aucune
#: prose -- une docstring presentant le contrat en colonnes
#: (« `extract-frames/`  frames EXTRAITES d'un rush ») lui echappait. L'exclusion
#: des docstrings ne protegeait alors RIEN, et le mutant « docstrings non
#: exclus » SURVIVAIT (2026-09-04, sur 27 tests verts).
_MOTIF_DE_SEGMENT = re.compile(
    "|".join(
        f"(?<![\\w.-]){re.escape(nom)}/|/{re.escape(nom)}(?![\\w.-])"
        for nom in sorted(NOMS_DE_DOSSIER_SURVEILLES)
    )
)


def _est_segment_surveille(texte: str) -> bool:
    """Le litteral porte-t-il un nom surveille comme SEGMENT de chemin ?

    « Comme segment » : suivi ou precede d'un slash. C'est ce qui epargne
    `sheet_frames`, `frames_dir`, `frames-scannees` (qui est lui-meme un nom
    surveille, donc traite par l'egalite) et la prose -- et c'est une propriete
    du motif, jamais une liste d'exceptions.
    """
    return _MOTIF_DE_SEGMENT.search(texte) is not None


def _litteraux_de_chemin(
        chemin: Path, *, relatif: str | None = None) -> list[tuple[int, str]]:
    """Les litteraux de chemin fautifs de `chemin`, avec leur ligne.

    Deux formes, et deux seulement -- voir le docstring du module. Les
    docstrings sont exclus : la prose de ce depot porte les mots qu'elle
    interdit, c'est meme sa fonction.

    `relatif` dit SOUS QUEL NOM le fichier doit etre juge, quand il ne vit pas
    a cet endroit -- un temoin fabrique dans un `tmp_path` pour eprouver
    l'exception d'un banc reel. Sans lui, la seule facon d'exercer
    `EXCEPTION_NOMMEE` etait de remplacer temporairement le VRAI fichier du
    depot par le temoin, ce que ce banc faisait (revue 11.14, couche 1) :

    * un guetteur echantillonnant la taille pendant 40 executions a observe
      `outils_identite_makepdf.py` a **0, 104 et 16384** octets, pour 19 028
      attendus ;
    * le mode par defaut du depot (`scripts/mesure/mesure.py`) pose
      `--timeout-method=thread`, et `pytest-timeout` y appelle `os._exit(1)`,
      qui **n'execute pas le `finally`** : un depassement de plafond pendant
      cette fenetre laissait un banc versionne remplace par 104 octets DANS
      L'ARBRE DE TRAVAIL -- que le reflexe « commit de sauvegarde a chaque
      rendu » de `CLAUDE.md` aurait commite ;
    * `--dist load` disperse les tests d'un meme fichier entre workers, donc
      un lecteur pouvait lire ce fichier pendant la fenetre. Cette course-la
      n'a pas ete reproduite (25 lectures contre 25 ecritures, 25 verts) ; la
      mort dure ci-dessus, elle, est deterministe et ne depend d'aucune course.

    **Un banc n'ecrit pas dans un fichier versionne.** Le chemin ne servait
    qu'a resoudre `EXCEPTION_NOMMEE` ; le passer explicitement mesure
    exactement la meme propriete sans toucher au depot.
    """
    arbre = _arbre(chemin)
    exclus = _docstrings(arbre)
    if relatif is None:
        try:
            relatif = chemin.relative_to(REPO_ROOT).as_posix()
        except ValueError:      # un fichier fabrique hors du depot (temoins)
            relatif = chemin.name
    toleres = EXCEPTION_NOMMEE.get(relatif) or EXCEPTION_NOMMEE.get(
        f"tests/unit/{relatif}", frozenset())

    # Les litteraux affectes a un identifiant tolere. L'exception est bornee a
    # l'AFFECTATION : tout autre litteral du meme fichier reste interdit.
    epargnes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(
            isinstance(cible, ast.Name) and cible.id in toleres
            for cible in noeud.targets
        ):
            for sous in ast.walk(noeud.value):
                epargnes.add(id(sous))

    # Les litteraux qui sont operande d'une composition de chemin.
    composes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
            for cote in (noeud.left, noeud.right):
                composes.add(id(cote))
        elif isinstance(noeud, ast.Call):
            nom = getattr(noeud.func, "id", None) or getattr(
                noeud.func, "attr", None)
            if nom in APPELS_DE_CHEMIN:
                for argument in noeud.args:
                    composes.add(id(argument))

    fautifs = []
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Constant)
                and isinstance(noeud.value, str)):
            continue
        if id(noeud) in exclus or id(noeud) in epargnes:
            continue
        egal = noeud.value in NOMS_DE_DOSSIER_SURVEILLES
        if (egal and id(noeud) in composes) or _est_segment_surveille(noeud.value):
            fautifs.append((noeud.lineno, noeud.value))
    return sorted(fautifs)


@pytest.mark.parametrize("banc", BANCS_SURVEILLES)
def test_aucun_banc_de_la_famille_ne_COMPOSE_un_chemin_de_frames(banc) -> None:
    """La frontiere negative de l'AC 7.2, cote lot E1.

    Un nom de dossier se lit dans `io/project_layout` et nulle part ailleurs.
    Le message d'echec nomme la ligne et le litteral : un rouge qui dirait
    seulement « il en reste » obligerait a refaire la mesure a la main.
    """
    fautifs = _litteraux_de_chemin(REPO_ROOT / banc)
    assert fautifs == [], (
        f"{banc} recompose {len(fautifs)} chemin(s) de frames en dur : "
        + ", ".join(f"l.{ligne} {valeur!r}" for ligne, valeur in fautifs)
        + ". Passer par io/project_layout (extract_frames_dir_from_slug, "
        "scan_frames_dir_from_slug, racines_de_frames_extraites, "
        "EXTRACT_FRAMES_DIRNAME)."
    )


def test_les_bancs_surveilles_EXISTENT_tous_sur_le_disque() -> None:
    """Volet positif : une liste perimee rendrait la frontiere muette.

    Un banc renomme ou supprime sortirait du perimetre sans que rien ne le
    dise, et la mesure ci-dessus resterait verte sur ce qui reste. Sept, et
    c'est le cardinal du lot E1.
    """
    manquants = [banc for banc in BANCS_SURVEILLES
                 if not (REPO_ROOT / banc).is_file()]
    assert manquants == [], f"bancs surveilles introuvables : {manquants}"
    assert len(BANCS_SURVEILLES) == 7


#: Un fichier fautif **par forme interdite**, et un temoin correct. Ecrits en
#: clair : un fichier fabrique par derivation du lecteur serait tautologique --
#: il mordrait sur ce que le lecteur sait deja lire, jamais sur ce qu'il a
#: cesse de lire (defaut du lot D3, 2026-09-03).
_FAUTIFS = {
    "composition-par-slash": 'chemin = projet / "frames" / "rush-001_4"\n',
    "composition-ancienne-sortie": 'chemin = projet / "output-frames"\n',
    "composition-nom-neuf": 'chemin = projet / "extract-frames"\n',
    "chemin-d-un-trait": 'valeur = "frames/rush-001_4"\n',
    "chemin-de-sortie-d-un-trait": 'valeur = "output-frames/lot-a/scan.tiff"\n',
    "segment-au-MILIEU": 'valeur = "projet/frames-scannees/lot-a/x.tiff"\n',
    "argument-de-rglob": 'trouve = projet.rglob("frames/*.tiff")\n',
    "argument-de-Path": 'chemin = Path("frames")\n',
    # NU dans un `glob` : seule la regle d'APPEL l'attrape -- la regle de
    # segment ne voit rien, faute de slash. Sans lui, retirer `glob`/`rglob`
    # d'`APPELS_DE_CHEMIN` laissait les 27 mesures VERTES (mutant M18,
    # 2026-09-04).
    "argument-NU-de-glob": 'trouve = projet.glob("output-frames")\n',
    # Le nom precede d'un slash et suivi de RIEN : c'est la moitie droite du
    # motif de segment, celle qu'un chemin absolu hostile emprunte.
    "segment-EN-FIN-de-chemin": 'valeur = "/ailleurs/frames"\n',
}

_EPARGNES = {
    "cle-de-manifeste-gelee": 'assert lot["frames_dir"] == valeur\n',
    "cle-de-manifeste-de-sortie": 'assert lot["output_frames_dir"] == valeur\n',
    "cle-nue-du-manifeste-POC": 'assert manifest["inputs"]["frames"] == valeur\n',
    "nom-voisin": 'assert doc["sheet_frames"] == valeur\n',
    "dossier-de-travail": 'chemin = tmp_path / "poc-frames"\n',
    # Les deux moities de la FRONTIERE DE MOT, une par cote. Sans elles,
    # retirer l'une ou l'autre laissait les mesures vertes (mutants M15 et
    # M16, 2026-09-04) : la frontiere devenait une recherche de sous-chaine,
    # c'est-a-dire le defaut n°2 du lot A ou `lot` attrapait `slot`.
    "voisin-a-GAUCHE-du-slash": 'valeur = "vieux-frames/f.tiff"\n',
    "voisin-a-DROITE-du-slash": 'valeur = "projet/frames-bis/f.tiff"\n',
    "identifiant-de-fonction": 'monkeypatch.setattr(m, "extract_selected_frames", f)\n',
    # Le contrat de la story, presente en colonnes -- forme reelle, reprise de
    # la fiche 11.14. C'est CE cas que l'exclusion des docstrings protege ; sans
    # les espaces, le motif exact ne le voyait pas et l'exclusion ne servait a
    # rien (mutant survivant du 2026-09-04).
    "prose-de-docstring": (
        '"""Contrat.\n\n'
        "    extract-frames/     frames EXTRAITES d'un rush\n"
        '    output-frames/      ancien nom, reconnu en lecture\n'
        '    """\n'),
    "forme-correcte": (
        "chemin = project_layout.extract_frames_dir_from_slug(p, s)\n"),
}


@pytest.mark.parametrize("cas", sorted(_FAUTIFS))
def test_la_frontiere_MORD_sur_un_banc_fautif(tmp_path, cas) -> None:
    """Le temoin qui mord, un par forme interdite.

    Sans lui, « zero litteral » serait aussi vrai d'un lecteur casse que d'un
    depot propre -- et un lecteur casse ne se signale pas.
    """
    fautif = tmp_path / "banc_fautif.py"
    fautif.write_text(_FAUTIFS[cas], encoding="utf-8")
    assert _litteraux_de_chemin(fautif) != [], (
        f"la frontiere laisse passer la forme {cas!r}")


@pytest.mark.parametrize("cas", sorted(_EPARGNES))
def test_la_frontiere_EPARGNE_ce_qui_n_est_PAS_un_chemin(tmp_path, cas) -> None:
    """Le volet symetrique : une frontiere trop large est aussi fausse.

    Elle deviendrait un obstacle qu'on desarme -- et un interdit desarme ne
    mesure plus rien. Les trois premiers cas sont `EPIC11-ARB-221` lui-meme :
    une cle de document ne se renomme pas, donc elle ne doit pas rougir.
    """
    temoin = tmp_path / "banc_correct.py"
    temoin.write_text(_EPARGNES[cas], encoding="utf-8")
    assert _litteraux_de_chemin(temoin) == [], (
        f"la frontiere rougit a tort sur {cas!r} : "
        f"{_litteraux_de_chemin(temoin)}")


def test_les_QUATRE_noms_surveilles_sortent_bien_du_MODULE_qui_les_porte() -> None:
    """Volet positif de la table : elle lit, elle ne recopie pas.

    Une frontiere qui recopierait les noms qu'elle surveille cesserait de
    surveiller le jour ou le module en change -- et resterait **verte**, puisque
    plus rien ne correspondrait. Quatre noms : les deux neufs et les deux
    anciens, tous distincts.
    """
    assert len(NOMS_DE_DOSSIER_SURVEILLES) == 4
    assert project_layout.EXTRACT_FRAMES_DIRNAME in NOMS_DE_DOSSIER_SURVEILLES
    assert project_layout.LEGACY_FRAMES_DIRNAME in NOMS_DE_DOSSIER_SURVEILLES
    # Les alias transitoires du lot B portent la valeur NEUVE : s'ils se
    # mettaient a porter l'ancienne, la surveillance perdrait son objet.
    assert project_layout.FRAMES_DIRNAME == project_layout.EXTRACT_FRAMES_DIRNAME
    assert project_layout.OUTPUT_FRAMES_DIRNAME == project_layout.SCAN_FRAMES_DIRNAME


def test_l_EXCEPTION_nommee_est_BORNEE_a_son_identifiant(tmp_path) -> None:
    """L'exception d'`outils_identite_makepdf` ne couvre pas tout le fichier.

    Une exception posee au fichier serait un trou : n'importe quel litteral
    reintroduit ailleurs dans ce module passerait. Elle est bornee a
    l'affectation de `DOSSIERS_DE_FRAMES_EXTRAITES`, et la mesure le montre en
    fabriquant un module qui porte les deux -- l'exception epargnee ET une
    faute a cote.
    """
    faux = tmp_path / "outils_identite_makepdf.py"
    faux.write_text(
        'DOSSIERS_DE_FRAMES_EXTRAITES = ("extract-frames", "frames")\n'
        'ailleurs = projet / "frames" / "rush-001_4"\n',
        encoding="utf-8")
    # Le lecteur resout l'exception par le chemin relatif au depot : on le lui
    # DIT, plutot que de remplacer le vrai fichier le temps de la mesure.
    # L'ecriture dans un fichier versionne est le defaut que la couche 1 de la
    # revue a mesure ; le motif complet vit sur `_litteraux_de_chemin`.
    fautifs = _litteraux_de_chemin(
        faux, relatif="tests/unit/outils_identite_makepdf.py")
    assert [valeur for _, valeur in fautifs] == ["frames"], (
        "l'exception deborde de son identifiant, ou elle ne s'applique pas : "
        f"{fautifs}")


def test_ce_BANC_n_ecrit_dans_AUCUN_fichier_du_depot() -> None:
    """Frontiere negative : la reintroduction ne se voit pas autrement.

    Ce banc a ecrit, pendant deux jours, dans `outils_identite_makepdf.py` --
    un fichier VERSIONNE -- le temps d'une mesure, en comptant sur un `finally`
    pour le restaurer. Sous `--timeout-method=thread`, le defaut du depot,
    `pytest-timeout` appelle `os._exit(1)` et le `finally` ne s'execute PAS :
    le fichier reste tronque dans l'arbre de travail. Aucun test POSITIF ne
    verrait revenir ce geste ; seule une frontiere qui l'interdit le peut.

    Elle est bornee a ce fichier et a la forme qui a mordu : une ecriture dont
    la cible se compose depuis `REPO_ROOT`. Un temoin de `tmp_path` n'en
    depend jamais.
    """
    arbre = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    # **Les ALIAS comptent**, et c'est un mutant qui l'a exige : la premiere
    # redaction ne regardait que la cible de l'appel, si bien que la
    # reintroduction litterale du geste d'avant -- `reel = REPO_ROOT / ... ;
    # reel.write_bytes(...)` -- la traversait SANS UN MOT. Une frontiere
    # negative qui ne rattrape pas la forme exacte qu'elle interdit ne mesure
    # rien.
    alias = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        if not any(isinstance(sous, ast.Name) and sous.id == "REPO_ROOT"
                   for sous in ast.walk(noeud.value)):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name):
                alias.add(cible.id)

    ecritures = []
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr in ("write_text", "write_bytes",
                                        "unlink", "mkdir", "rename")):
            continue
        # La cible se compose-t-elle depuis `REPO_ROOT`, directement ou par un
        # nom local qui en vient ?
        if any(isinstance(sous, ast.Name)
               and (sous.id == "REPO_ROOT" or sous.id in alias)
               for sous in ast.walk(noeud.func.value)):
            ecritures.append(noeud.lineno)
    assert ecritures == [], (
        "ce banc ecrit dans un fichier du DEPOT aux lignes "
        f"{ecritures} : sous `--timeout-method=thread` un depassement de "
        "plafond laisserait ce fichier tronque dans l'arbre de travail. "
        "Fabriquer le temoin dans `tmp_path` et passer `relatif=`.")


def test_le_temoin_de_tmp_path_est_bien_JUGE_sous_le_nom_du_banc_REEL(
        tmp_path) -> None:
    """Volet symetrique : `relatif=` doit VRAIMENT porter l'exception.

    Sans lui, le temoin serait juge sous son propre nom de fichier, aucune
    exception ne s'appliquerait, et `DOSSIERS_DE_FRAMES_EXTRAITES` rougirait
    au meme titre que la faute d'a cote -- deux fautifs au lieu d'un. Le test
    qui l'emploie ne ferait alors plus la difference entre « l'exception est
    bornee » et « l'exception ne s'applique pas ».
    """
    faux = tmp_path / "un_nom_qui_n_est_pas_celui_du_banc.py"
    # Le litteral EPARGNE est COMPOSE, sans quoi il ne serait pas fautif meme
    # sans exception et ce temoin ne discriminerait rien -- c'est la forme que
    # `_litteraux_de_chemin` attrape (operande d'un `/`).
    faux.write_text(
        'DOSSIERS_DE_FRAMES_EXTRAITES = (projet / "frames",)\n'
        'ailleurs = projet / "frames" / "rush-001_4"\n',
        encoding="utf-8")
    # Juge sous SON nom : aucune exception ne s'applique, les DEUX rougissent.
    assert [valeur for _, valeur in _litteraux_de_chemin(faux)] == [
        "frames", "frames"]
    # Juge sous le nom du banc reel : l'exception couvre l'affectation, et
    # elle seule -- la faute d'a cote reste.
    assert [valeur for _, valeur in _litteraux_de_chemin(
        faux, relatif="tests/unit/outils_identite_makepdf.py")] == ["frames"]


def test_les_EXCEPTIONS_nommees_existent_TOUTES_dans_leur_fichier() -> None:
    """Volet positif des exceptions : une exception perimee est un trou muet.

    Un identifiant renomme ou disparu laisserait son exception en place, prete
    a couvrir autre chose le jour ou le nom serait reemploye -- et personne ne
    le verrait, puisqu'une exception qui ne s'applique a rien ne fait rien
    rougir. Elles sont donc confrontees au code qu'elles pretendent couvrir.
    """
    for banc, identifiants in EXCEPTION_NOMMEE.items():
        assert banc in BANCS_SURVEILLES, (
            f"{banc} porte une exception mais n'est pas surveille")
        arbre = _arbre(REPO_ROOT / banc)
        affectes = {
            cible.id
            for noeud in ast.walk(arbre) if isinstance(noeud, ast.Assign)
            for cible in noeud.targets if isinstance(cible, ast.Name)
        }
        manquants = sorted(identifiants - affectes)
        assert manquants == [], (
            f"{banc} : exception(s) sans affectation correspondante -- "
            f"{manquants}")
