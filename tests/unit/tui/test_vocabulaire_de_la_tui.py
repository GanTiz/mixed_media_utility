# -*- coding: utf-8 -*-
"""Story 11.14, lot D1 -- le vocabulaire des objets, cote TUI.

**Ce que ce banc mesure, et pourquoi il est NEGATIF.** La story 11.14 retire
trois mots des surfaces du depot -- `output-frames`, `frames/` comme nom du
dossier des frames extraites, et « frames rescannees » -- et en pose deux :
`frames-scannees/` et `extract-frames/` (`EPIC11-ARB-214`, `EPIC11-ARB-220`).
Aucun test POSITIF ne verrait revenir un mot retire : on peut ecrire autant
d'assertions qu'on veut sur le mot neuf, elles resteront vertes le jour ou un
ecran voisin reintroduira l'ancien. Une frontiere negative est le seul genre
de mesure qui attrape une REINTRODUCTION, et c'est la lecon que ce depot a
payee assez de fois pour l'ecrire dans `CLAUDE.md`.

**Une frontiere PAR NOM RETIRE, jamais une seule pour l'ensemble** (forme de
l'AC 4.3, transposee du lot C) : un balayage global serait vert des que le
premier nom est couvert, et le second passerait sans qu'on le sache.

**Ce que ce banc NE mesure pas, dit plutot que tu :**

* il ne balaye que `src/mixed_media_utility/tui/`. Le `gui/` porte le meme
  vocabulaire (19 modules, ~590 occurrences) et reste hors story tant que
  `Q6` n'a pas repondu ; `cli.py` a sa propre frontiere, ecrite par le lot C
  dans `tests/unit/test_suppression_element_de_projet.py` ;
* il ne mesure pas que la TUI LIT la table des natures de
  `project_inventory` (AC 1.3, volet TUI) : au 2026-09-04 elle ne la lit
  **pas encore**, l'ecran d'inventaire `E6-1` n'etant pas construit. Ce qui
  est mesurable aujourd'hui l'est --
  :func:`test_le_mot_de_la_TUI_est_celui_de_la_NATURE_publiee_par_le_coeur`
  attache le libelle affiche a la nature du coeur par une normalisation,
  plutot que de laisser deux chaines independantes diverger en silence.
"""
from __future__ import annotations

import ast
import re
import unicodedata
from pathlib import Path

import pytest

from mixed_media_utility import project_inventory
from mixed_media_utility.io import project_layout
from mixed_media_utility.tui import (atelier_extraction_ecriture,
                                     atelier_scan_resultat, palier_projet,
                                     projet_lecture)

_RACINE_DU_DEPOT = Path(__file__).resolve().parents[3]
_RACINE_TUI = _RACINE_DU_DEPOT / "src" / "mixed_media_utility" / "tui"


# ---------------------------------------------------------------------------
# Les noms retires, un par ligne
# ---------------------------------------------------------------------------

#: Les mots que la story 11.14 retire des surfaces de la TUI, **une ligne par
#: mot** avec son motif et son remplacant.
#:
#: Chaque motif est borne par des **frontieres de token** plutot que par une
#: sous-chaine, et ce n'est pas un raffinement : c'est le defaut n°2 du lot A,
#: paye la-bas en 248 noms releves contre quelques dizaines. `--frames` ne doit
#: attraper ni `--frames-scannees` ni `--frames-par-page` ; `--frames-scannees`
#: ne doit pas attraper le DOSSIER `frames-scannees/`, qui est gele
#: (`SCAN_FRAMES_DIRNAME`) ; `frames/` ne doit attraper ni `extract-frames/` ni
#: `frames-scannees/`. Un motif par sous-chaine rendrait la frontiere rouge
#: **quoi qu'on fasse**, donc inutile.
NOMS_RETIRES_DES_ECRANS: tuple[tuple[str, str, str], ...] = (
    # (nom retire, motif qui le reconnait, ce qui le remplace)
    ("output-frames", r"output-frames", "frames-scannees"),
    ("frames/", r"(?<![-\w])frames/", "extract-frames/"),
    ("--frames", r"--frames(?![-\w])", "--lot-scanne"),
    # **Le nom neuf du lot C est devenu un nom RETIRE le 2026-09-05**
    # (`EPIC11-ARB-224`) : la chaine est `--frames`, puis `--frames-scannees`,
    # puis `--lot-scanne`. Chaque maillon garde sa ligne -- retirer celle de
    # `--frames` au motif qu'un nom plus recent existe rouvrirait le premier
    # defaut. Le `--` en tete distingue l'OPTION du DOSSIER `frames-scannees/`,
    # gele (`SCAN_FRAMES_DIRNAME`) et hors perimetre.
    ("--frames-scannees", r"--frames-scannees(?![-\w])", "--lot-scanne"),
    ("frames rescannees", r"[Ff]rames\s+rescann", "frames scannees"),
    ("rescanne", r"[Rr]escann", "scanne"),
)

#: **Les alias transitoires de `project_layout`, que la TUI ne doit plus lire.**
#:
#: `FRAMES_DIRNAME` et `OUTPUT_FRAMES_DIRNAME` portent la valeur NEUVE -- le
#: lot B les a laisses derriere lui « le temps que les lots C, D et E passent
#: aux noms neufs ». Ils ne sont donc pas un defaut de VALEUR, et aucun
#: balayage de chaines ne peut les voir : ce sont des NOMS, et le nom porte le
#: mot ambigu que la story existe pour retirer. Les mesurer ici est la moitie
#: du lot D1 qu'un balayage de texte ne fait pas.
ALIAS_TRANSITOIRES = ("FRAMES_DIRNAME", "OUTPUT_FRAMES_DIRNAME")


# ---------------------------------------------------------------------------
# Le collecteur -- un SUR-ENSEMBLE des libelles, docstrings compris
# ---------------------------------------------------------------------------

def chaines_visibles(source: str) -> list[tuple[int, str]]:
    """Toute chaine litterale d'un module, dans l'ordre des lignes.

    C'est un **sur-ensemble** des libelles affiches, et deliberement : un
    docstring n'atteint pas l'operateur, mais il atteint la session suivante,
    et un nom de dossier perime lu dans un docstring est exactement ce qui
    fait rechercher un dossier qui n'existe plus. Le lot C a pris la meme
    largeur sur `cli.py` pour la meme raison ; restreindre le balayage aux
    seuls libelles laisserait passer un nom perime a l'endroit ou une
    relecture le prend pour la reference.
    """
    return sorted(
        (noeud.lineno, noeud.value)
        for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
    )


def _porteuses(chaines: list[tuple[int, str]],
               motif: str) -> list[tuple[int, str]]:
    """Les chaines du balayage qui portent le motif -- avec leur ligne."""
    compile_ = re.compile(motif)
    return [(ligne, texte) for ligne, texte in chaines if compile_.search(texte)]


def _modules_de_la_tui(racine: Path | None = None) -> list[Path]:
    """Les modules du paquet, tries -- le COLLECTEUR du niveau PAQUET.

    `racine` n'est pas du confort : c'est ce qui rend ce collecteur
    **traversable par un corpus temoin**. Sans elle, aucun test ne pouvait
    voir une troncature ici, et les trois mutants `[:-1]`, `[1:]` et `[1:-1]`
    survivaient aux 47 tests de ce fichier (revue 11.14, couche 2, `C3`).
    Meme forme que le collecteur de `docs/` du lot D3, pour la meme raison.
    """
    return sorted((racine or _RACINE_TUI).glob("*.py"))


def _balayage_de_la_tui(
    racine: Path | None = None
) -> dict[str, list[tuple[int, str]]]:
    """Le balayage COMPLET du paquet, une entree par module.

    **Il est PARTAGE entre la frontiere negative et son volet symetrique, et
    ce n'est pas une economie de lignes.** Une frontiere negative attend une
    liste VIDE : elle reste donc verte si le balayage qui l'alimente est
    tronque, ce qu'aucune de ses propres assertions ne peut voir. En faisant
    consommer aux deux tests le MEME balayage, une troncature ici rougit le
    volet symetrique, qui attend, lui, des cardinaux et des temoins nommes.

    C'est la forme exacte du defaut qui a fait survivre deux mutants au lot C
    -- « le temoin de bord mesurait l'appariement et pas le COLLECTEUR » --,
    transposee un cran plus haut : ici le collecteur d'un module est
    :func:`chaines_visibles`, et celui du PAQUET est cette fonction.
    """
    return {module.name: chaines_visibles(module.read_text(encoding="utf-8"))
            for module in _modules_de_la_tui(racine)}


def _alias_lus_par_la_tui() -> dict[str, set[str]]:
    """Les noms references par chaque module -- meme raison qu'au-dessus.

    :func:`test_aucun_module_de_la_TUI_ne_lit_un_ALIAS_transitoire` attend un
    ensemble vide et :func:`test_la_TUI_lit_bien_les_constantes_NEUVES` attend
    des noms precis : les deux lisent cette table, donc une troncature qui
    rendrait la premiere verte pour rien rougit la seconde.
    """
    return {module.name: _noms_references(module.read_text(encoding="utf-8"))
            for module in _modules_de_la_tui()}


def _alias_lus_par_les_BANCS() -> dict[str, set[str]]:
    """Meme table, cote `tests/unit/tui/`.

    **Le banc compte autant que le produit ici**, et c'est le seul endroit de
    ce fichier ou la mesure se retourne sur elle-meme : les alias transitoires
    ne tomberont que le jour ou PLUS RIEN ne les lit. Un `tui/` propre et
    neuf face a dix bancs qui lisent encore `FRAMES_DIRNAME` laisserait le lot
    B croire sa transition finie alors qu'elle ne l'est pas.
    """
    return {chemin.name: _noms_references(chemin.read_text(encoding="utf-8"))
            for chemin in sorted(Path(__file__).resolve().parent.glob("*.py"))}


# ---------------------------------------------------------------------------
# AC 6.4 -- la frontiere negative, une par nom retire
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("retire,motif,neuf", NOMS_RETIRES_DES_ECRANS)
def test_aucune_chaine_de_la_TUI_ne_porte_le_nom_RETIRE(retire, motif, neuf):
    """AC 6.4 : « un `grep` d'un mot retire dans les libelles de `tui/` rend
    zero, avec la liste des exceptions NOMMEES dans le test ».

    **Il n'y a aucune exception**, et c'est un fait mesure plutot qu'une
    intention : au 2026-09-04, apres le lot D1, les cinq motifs rendent zero
    sur les 46 modules. Le jour ou une exception deviendra necessaire, elle
    s'ecrira ici -- dans le test, ou elle est mesuree -- et jamais dans un
    commentaire du module, ou rien ne la tiendrait.
    """
    porteuses = [f"  {nom}:{ligne}: {texte[:110]!r}"
                 for nom, chaines in _balayage_de_la_tui().items()
                 for ligne, texte in _porteuses(chaines, motif)]
    assert porteuses == [], (
        f"{len(porteuses)} chaine(s) de `tui/` portent encore {retire!r}, "
        f"qui se dit desormais {neuf!r}:\n" + "\n".join(porteuses))


def test_le_balayage_de_la_TUI_VOIT_bien_quelque_chose():
    """Volet symetrique : une frontiere negative sur un balayage VIDE serait
    verte pour rien -- et elle le resterait apres un `[:-1]` sur le collecteur.

    Trois temoins pris **dans trois modules differents**, dont un aux deux
    bouts du paquet par ordre alphabetique : sans quoi un balayage qui ne
    lirait qu'un module passerait.
    """
    balayage = _balayage_de_la_tui()
    attendus = {module.name for module in _modules_de_la_tui()}
    assert set(balayage) == attendus, set(balayage) ^ attendus
    assert len(balayage) > 40, len(balayage)

    total = sum(len(chaines) for chaines in balayage.values())
    assert total > 3000, total

    # Les mots NEUFS, la ou ils sont reellement ecrits.
    par_module = {nom: [t for _, t in chaines]
                  for nom, chaines in balayage.items()}
    assert any("lots scannés" in t
               for t in par_module["atelier_scan_resultat.py"])
    assert any("frames-scannees" in t
               for t in par_module["atelier_scan_detection.py"])
    # **Ces quatre lignes ne sont PAS le temoin de bord, et c'est une mesure
    # qui l'a etabli** (revue 11.14, couche 2, `C3`). Elles lisent leurs deux
    # bords dans `attendus`, qui sort du MEME collecteur que `balayage` : une
    # troncature deplace simplement le bord, et les trois mutants `[:-1]`,
    # `[1:]` et `[1:-1]` restaient verts sur les 47 tests d'ici. Ce qu'elles
    # tiennent est plus modeste et vrai : aucun module du paquet n'est lu
    # comme VIDE. Le temoin de bord du collecteur de PAQUET est
    # :func:`test_le_balayage_du_PAQUET_lit_le_PREMIER_et_le_DERNIER_module`,
    # qui part d'un corpus miniature au lieu de sa propre sortie.
    muets = [nom for nom, chaines in balayage.items() if not chaines]
    assert muets == [], muets


@pytest.mark.parametrize("voisin", [
    # `--frames-scannees` a QUITTE cette liste avec `EPIC11-ARB-224` : ce n'est
    # plus un voisin legitime mais un nom retire, il a sa ligne ci-dessus. Le
    # DOSSIER `frames-scannees/` y reste, et c'est lui qui mesure que le motif
    # est borne au jeton plutot qu'a la sous-chaine.
    "--lot-scanne", "--frames-par-page", "frames-scannees/",
    "extract-frames/", "output_frames_dir", "frames_scannees",
])
def test_le_balayage_ne_confond_PAS_un_nom_VOISIN_avec_un_nom_retire(voisin):
    """Volet symetrique de la frontiere : un motif par sous-chaine rougirait ici.

    C'est le defaut n°2 du lot A -- `lot` attrapait `slot`, `patch` attrapait
    `patch_preset_id` --, et il mord d'autant plus fort ici que **le nom neuf
    PROLONGE l'ancien** : c'est exactement ce qui a fait accepter `--frames`
    comme abreviation de `--frames-scannees` cote CLI, defaut que le lot C a
    ferme par `allow_abbrev=False`.
    """
    faux = [(1, f"un libelle qui cite {voisin} et rien d'autre")]
    for retire, motif, _neuf in NOMS_RETIRES_DES_ECRANS:
        assert _porteuses(faux, motif) == [], (
            f"le motif de {retire!r} attrape son voisin {voisin!r}")


# ---------------------------------------------------------------------------
# Regle des fabriques, point 4 (2026-09-03) -- le COLLECTEUR, a chaque BORD
# ---------------------------------------------------------------------------

#: Un module TUI **miniature**, cinq chaines litterales **distinguables**, dans
#: l'ordre du fichier. Pas un remplissage uniforme : une permutation ou une
#: troncature du collecteur ne se voit pas autrement (regle des fabriques,
#: points 1 et 4).
#:
#: C'est un **source Python**, pas une liste de chaines toute faite : le temoin
#: doit traverser :func:`chaines_visibles` -- le COLLECTEUR --, et pas seulement
#: :func:`_porteuses` -- l'APPARIEMENT. Un collecteur tronque (« ne lire que
#: les affectations », « sauter la derniere ») est un mode de panne que
#: l'appariement ne peut pas voir, et c'est celui qui a laisse DEUX mutants
#: survivre au lot C avant qu'il ne parte, lui aussi, d'une source miniature.
_SOURCE_TEMOIN = [
    '"""Docstring alpha du module temoin."""',
    'TITRE = "libelle bravo, qui parle de scans"',
    'def suite(rapport):\n    """Docstring charlie, qui parle de masters."""',
    'SUITE = "libelle delta, qui parle de tirages"',
    'print("libelle echo, qui parle de rushes")',
]


@pytest.mark.parametrize("retire,motif,neuf", NOMS_RETIRES_DES_ECRANS)
@pytest.mark.parametrize("position", [0, 2, 4])
def test_le_balayage_de_la_TUI_MORD_a_CHAQUE_BORD(retire, motif, neuf,
                                                  position):
    """`CLAUDE.md`, regle des fabriques, point 4 -- en TETE **et** en QUEUE.

    « La cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque, qui est un autre mode de panne. » Les trois positions
    couvertes sont donc le premier element, un du milieu et le **dernier**.

    Les cinq chaines du temoin sont de **cinq formes syntaxiques
    differentes** -- docstring de module, affectation, docstring de fonction,
    affectation, argument d'appel -- parce qu'un collecteur qui ne lirait que
    les affectations raterait trois d'entre elles sans qu'aucun test
    d'appariement le voie.
    """
    lignes = [
        (ligne.replace("alpha", f"alpha {retire}")
              .replace("bravo", f"bravo {retire}")
              .replace("charlie", f"charlie {retire}")
              .replace("delta", f"delta {retire}")
              .replace("echo", f"echo {retire}"))
        if rang == position else ligne
        for rang, ligne in enumerate(_SOURCE_TEMOIN)
    ]
    chaines = chaines_visibles("\n".join(lignes) + "\n")
    assert len(chaines) == len(_SOURCE_TEMOIN), (
        f"le collecteur rend {len(chaines)} chaines pour "
        f"{len(_SOURCE_TEMOIN)} : il en saute")
    porteuses = _porteuses(chaines, motif)
    assert len(porteuses) == 1, (
        f"le balayage rate {retire!r} en position {position} sur "
        f"{len(_SOURCE_TEMOIN)} : {porteuses}")
    assert retire.split()[0].rstrip("/").lstrip("-") in porteuses[0][1]


#: **Le corpus miniature du collecteur de PAQUET**, trois modules TUI reduits
#: a une chaine chacun, et **distinguables** : leur libelle porte leur propre
#: nom. `glob` etant trie, l'ordre alphabetique EST l'ordre du balayage, donc
#: `a_tete.py` est le premier element et `z_queue.py` le dernier.
_CORPUS_MINIATURE = ("a_tete.py", "m_milieu.py", "z_queue.py")


@pytest.mark.parametrize("retire,motif,neuf", NOMS_RETIRES_DES_ECRANS)
@pytest.mark.parametrize("position", (0, 1, 2), ids=("tete", "milieu", "queue"))
def test_le_balayage_du_PAQUET_lit_le_PREMIER_et_le_DERNIER_module(
    tmp_path, retire, motif, neuf, position
):
    """`CLAUDE.md`, regle des fabriques, point 4 -- **un cran plus haut**.

    :func:`test_le_balayage_de_la_TUI_MORD_a_CHAQUE_BORD` tient le collecteur
    d'UN module (:func:`chaines_visibles`). Celui du PAQUET
    (:func:`_modules_de_la_tui`) n'avait, lui, aucun temoin : la revue 11.14
    a plante le meme libelle dans `tui/__init__.py` et `tui/rushes.py` -- le
    premier et le dernier module par ordre alphabetique -- et mesure que le
    collecteur SAIN fait rougir trois tests quand le collecteur tronque
    `[1:-1]` en fait rougir **zero**. La frontiere negative etait aveugle a
    ce qu'elle existe pour attraper.

    Et la raison pour laquelle le volet symetrique existant ne suffisait pas
    est celle qui a deja coute deux redactions dans cette story : il lisait
    ses deux bords dans la SORTIE du collecteur, donc une troncature
    deplacait le bord au lieu de le perdre. Le temoin part ici d'un **corpus
    miniature reel**, ecrit dans `tmp_path` et traverse par le collecteur --
    la forme retenue par le lot D3 sur `docs/` et par le lot C sur `cli.py`.

    Le nom retire se pose a CHAQUE position : une cible au milieu demasque un
    `find` fautif, elle ne demasque pas un balayage tronque.
    """
    for rang, nom in enumerate(_CORPUS_MINIATURE):
        libelle = f"libelle du module temoin {rang}"
        if rang == position:
            libelle = f"{libelle}, qui cite {retire} une seule fois"
        (tmp_path / nom).write_text(
            f'TITRE = "{libelle}"\n', encoding="utf-8")

    balayage = _balayage_de_la_tui(racine=tmp_path)

    # 1. Le collecteur rend les TROIS modules -- c'est lui qui est mesure.
    assert sorted(balayage) == sorted(_CORPUS_MINIATURE), (
        f"le collecteur de paquet rend {sorted(balayage)} pour "
        f"{sorted(_CORPUS_MINIATURE)} : il tronque le listing, et une "
        "frontiere negative qui attend une liste VIDE n'en devient que plus "
        "verte -- aucune de ses assertions ne peut le voir.")

    # 2. Et la frontiere, alimentee par ce balayage, MORD a cette position.
    porteurs = [nom for nom, chaines in balayage.items()
                if _porteuses(chaines, motif)]
    assert porteurs == [_CORPUS_MINIATURE[position]], (
        f"le nom retire {retire!r} pose en position {position} sur "
        f"{len(_CORPUS_MINIATURE)} est vu dans {porteurs} : la frontiere ne "
        f"le retrouve pas la ou il est.")


# ---------------------------------------------------------------------------
# AC 6.1, volet POSITIF -- les mots NEUFS sont bien ceux du coeur
# ---------------------------------------------------------------------------

def _sans_accent(texte: str) -> str:
    """`lots scannés` -> `lots scannes`. Le coeur ecrit en ASCII, pas la TUI."""
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if unicodedata.category(c) != "Mn")


def test_le_mot_de_la_TUI_est_celui_de_la_NATURE_publiee_par_le_coeur():
    """AC 1.1 : « une interface LIT le vocabulaire, elle ne le REDIGE pas ».

    La TUI ne peut pas afficher :data:`~mixed_media_utility.project_inventory.
    NATURE_LOT_SCANNE` tel quel -- `lot_scanne` est un IDENTIFIANT, pas un
    libelle : il porte un souligne et aucun accent. Ce que ce test tient, a
    defaut, c'est le lien : le libelle de `E3-8` doit **contenir** la forme
    humaine de la nature du coeur. Le jour ou le coeur renommera sa nature, ce
    test rougira -- ce qu'aucune paire de chaines independantes ne ferait.
    """
    singulier = project_inventory.NATURE_LOT_SCANNE.replace("_", " ")
    assert singulier == "lot scanne"
    # Le pluriel se DERIVE du singulier -- « les jeu de framess posterieurs »
    # est ce qu'un `objet + "s"` naif a produit cote CLI, trouve en revue : ici
    # l'accord porte sur chaque mot, ce qui est la regle du francais pour un
    # nom suivi d'un participe.
    pluriel = " ".join(f"{mot}s" for mot in singulier.split())
    assert pluriel == "lots scannes"
    for libelle in (atelier_scan_resultat.SUITE_DOSSIER,
                    atelier_scan_resultat.SUITE_EXPORTS,
                    atelier_scan_resultat.AUCUN_LOT_A_OUVRIR):
        nu = _sans_accent(libelle)
        assert singulier in nu or pluriel in nu, (
            f"{libelle!r} ne porte pas le mot du coeur "
            f"{singulier!r} (ni son pluriel {pluriel!r})")


def test_le_MENU_nomme_le_lot_scanne_comme_le_coeur_et_comme_E3_8():
    """`D3-5` -- le NEUVIEME nom de l'objet, trouve hors perimetre par le lot D3.

    `projet_lecture` decrivait l'atelier Exports « Encoder un master depuis un
    lot **reconstruit** », et sa condition disait « aucun lot reconstruit ».
    Aucun autre endroit du depot n'appelle cet objet ainsi ; le coeur dit
    `lot_scanne` et `E3-8` propose « Encoder un master depuis ces lots
    scannes » -- la MEME action, sous deux mots.

    La mesure est **derivee**, pas epinglee : le mot attendu vient de
    :data:`~mixed_media_utility.project_inventory.NATURE_LOT_SCANNE`, si bien
    qu'un renommage au coeur rougit ici.
    """
    singulier = project_inventory.NATURE_LOT_SCANNE.replace("_", " ")
    phrase = projet_lecture.PHRASES[projet_lecture.EXPORTS]
    assert singulier in _sans_accent(phrase), phrase

    # Et la CONDITION, qui est l'autre moitie : un menu peut nommer juste
    # l'entree et faux ce qui lui manque, et c'est le refus que l'operateur
    # lit le plus souvent.
    par_nom = {e.nom: e for e in projet_lecture.entrees({"lots": []})}
    condition = par_nom[projet_lecture.EXPORTS].condition
    assert condition is not None
    assert singulier in _sans_accent(condition), condition


def test_le_mot_RECONSTRUIT_reste_la_ou_il_designe_un_AUTRE_objet():
    """Volet symetrique du precedent, et il est le plus important des deux.

    « Ne renomme pas mecaniquement -- lis ce que chaque ecran montre. »
    :func:`~mixed_media_utility.tui.palier_projet.panneau_de_reconstruction`
    compte des « Lots reconstruits » qui sont les lots qu'une **reconstruction
    de projet** recree au manifeste depuis les payloads : un autre objet, une
    autre commande (`reconstruct-project`), et le mot y est juste.

    Sans ce volet, la correction du `D3-5` se serait etendue par ressemblance
    de mot a un ecran qui ne parle pas du meme objet -- exactement ce que la
    story existe pour empecher, a l'envers.
    """
    from mixed_media_utility.tui.panneau import Panneau  # noqa: F401
    apercu = palier_projet.ProjetReconstruit(
        pages=4, rushes=2, lots=3, chemin=Path("/p/project.json"))
    libelles = [ligne.libelle
                for ligne in palier_projet.panneau_de_reconstruction(apercu).lignes]
    assert "Lots reconstruits" in libelles, libelles


def test_les_DEUX_ecrans_de_resultat_ne_disent_PLUS_la_MEME_chose():
    """**C'est la mesure de la story, et elle porte sur un ECART.**

    Avant le lot D1, `E2-5` (Extraction) et `E3-8` (Scan) portaient trois
    chaines **identiques au caractere pres** -- « Ouvrir le dossier des lots »
    et « Aucun lot écrit : ... » -- pour deux dossiers differents :
    `extract-frames/` d'un cote, `frames-scannees/` de l'autre. C'est
    litteralement le « il faut deviner » qu'Egan a nomme le 2026-09-04.

    Une assertion sur la seule valeur neuve serait verte meme si l'ecran
    voisin avait ete renomme lui aussi : ce qui se mesure ici est donc la
    PAIRE, dans les deux sens.
    """
    assert (atelier_scan_resultat.SUITE_DOSSIER
            != atelier_extraction_ecriture.SUITE_DOSSIER)
    assert (atelier_scan_resultat.AUCUN_LOT_A_OUVRIR
            != atelier_extraction_ecriture.AUCUN_LOT_A_OUVRIR)
    # Et l'ecran d'Extraction garde le mot d'Egan pour SON objet : un lot est
    # « un ensemble de frames extraites depuis le rush source avec extract ».
    assert "scann" not in atelier_extraction_ecriture.SUITE_DOSSIER
    assert "scann" in atelier_scan_resultat.SUITE_DOSSIER


# ---------------------------------------------------------------------------
# AC 2.3 transposee -- aucun nom de dossier compose a la main dans `tui/`
# ---------------------------------------------------------------------------

#: Les noms de dossier de l'arborescence v2 qu'un module n'a pas a composer
#: lui-meme. Les quatre premiers sont ceux de la story 11.14 ; les autres sont
#: la pour que la frontiere ne soit pas vraie par accident sur un seul mot.
DOSSIERS_DE_L_ARBORESCENCE = frozenset({
    "frames", "output-frames", "extract-frames", "frames-scannees",
    "outputs", "scans", "patches", "inputs", "logs", "versions",
})

#: **`planches` n'entre PAS dans l'ensemble ci-dessus, et c'est une mesure.**
#:
#: `EPIC11-ARB-225` renomme `patches/` en `planches/`, et le reflexe serait
#: d'ajouter le nom neuf ici. Il a ete essaye, et il rend la frontiere FAUSSE :
#: elle mesure une egalite de chaine nue, or `planches` est aussi le mot
#: francais ordinaire de l'objet. Mesure a l'ajout, le 2026-09-06 : trois bancs
#: GARDES deviennent rouges (`test_atelier_scan_depot.py` l. 153 et 615,
#: `test_frontiere_coeur_atteignable.py` l. 289) sans qu'aucun d'eux compose un
#: chemin de l'arborescence v2 -- ce sont des dossiers de depot de scan et des
#: fixtures de travail --, et la dette de composition passe de 207 a 222.
#:
#: C'est le symetrique exact du piege d'homonymie que le renommage devait
#: eviter cote `patches` (les pastilles de couleur) : le nom neuf entre en
#: collision avec le vocabulaire, l'ancien entrait en collision avec la
#: colorimetrie. Le nom d'AVANT reste surveille ici -- l'y attraper est
#: precisement l'objet de la frontiere.
#:
#: Le nom neuf n'est pas pour autant sans garde : `test_ecran_projet_tui.py`
#: derive la sienne de `BASE_SUBDIRS`, donc il l'a surveille des le premier
#: commit du renommage, sans que personne ait a l'y poser.


#: Le segment qui, present dans une chaine de `/`, dit que le chemin ne designe
#: PAS un projet mais le corpus de fixtures du depot.
#:
#: **Pourquoi cette exception existe, et pourquoi elle n'est pas un
#: relachement** (posee le 2026-09-07). `tests/fixtures/scans/` est un chemin
#: REEL du depot -- c'est la que vivent les PDF de scans de terrain, et
#: `.gitattributes` y scope le LFS PAR CE CHEMIN. Un banc qui l'ecrit ne
#: compose pas un dossier de projet : il nomme un corpus, et `io/project_layout`
#: n'a rien a en dire. Sans cette exception, les deux seules issues etaient
#: d'exempter `test_nom_du_profil_de_calibration.py` et
#: `test_orphelin_du_scan_de_calibration.py` **en entier et pour toujours** --
#: ce que le commentaire de `BANCS_QUI_COMPOSENT_ENCORE_A_LA_MAIN` refuse --,
#: ou de tordre le chemin pour esquiver le motif, ce qui aurait truque la
#: mesure au lieu de l'affiner.
#:
#: C'est le meme raisonnement que celui tenu pour `planches` juste au-dessus :
#: la frontiere compare des chaines nues, donc elle doit dire ou une chaine nue
#: ne veut pas dire ce qu'elle a l'air de vouloir dire.
#:
#: **Ce qu'elle ne relache pas, et un temoin le mesure** : elle ne porte que sur
#: la chaine de `/` qui traverse `fixtures`. Une composition de projet ecrite
#: dans le MEME fichier, deux lignes plus loin, reste attrapee.
SEGMENT_DU_CORPUS_DE_FIXTURES = "fixtures"


def _sous_un_corpus_de_fixtures(noeud: ast.BinOp) -> bool:
    """La chaine de `/` traverse-t-elle `fixtures` ?

    Mesure sur le noeud ENTIER plutot que sur son seul cote gauche : le segment
    peut arriver par un `Path(...)` imbrique (`Path(__file__).parents[1] /
    "fixtures" / "scans"`) comme par une variable deja composee.
    """
    return any(isinstance(fils, ast.Constant)
               and fils.value == SEGMENT_DU_CORPUS_DE_FIXTURES
               for fils in ast.walk(noeud))


def _compositions_de_chemin(source: str) -> list[tuple[int, str]]:
    """Toute composition de chemin sur un litteral de dossier, avec sa ligne.

    Deux formes, et il faut les deux : l'operateur `/` de `pathlib`
    (`racine / "frames"`) et la construction ou la jointure explicite
    (`Path("frames")`, `.joinpath("frames")`). Ne mesurer que la premiere
    laisserait passer la seconde, et c'est la forme la plus frequente cote
    banc.
    """
    trouves: list[tuple[int, str]] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
            if _sous_un_corpus_de_fixtures(noeud):
                continue
            for cote in (noeud.left, noeud.right):
                if (isinstance(cote, ast.Constant)
                        and cote.value in DOSSIERS_DE_L_ARBORESCENCE):
                    trouves.append((noeud.lineno, f"... / {cote.value!r}"))
        elif isinstance(noeud, ast.Call):
            nom = getattr(noeud.func, "id", None) or getattr(
                noeud.func, "attr", None)
            if nom in {"Path", "PurePosixPath", "joinpath"}:
                for arg in noeud.args:
                    if (isinstance(arg, ast.Constant)
                            and arg.value in DOSSIERS_DE_L_ARBORESCENCE):
                        trouves.append((noeud.lineno, f"{nom}({arg.value!r})"))
    return trouves


def test_aucun_module_de_la_TUI_ne_compose_un_nom_de_dossier_a_la_main():
    """Frontiere NEGATIVE, transposee de l'AC 2.3.

    **C'est ce qui a fait que le renommage du lot B n'a casse aucun ecran** :
    la TUI compose ses chemins par `project_layout`, jamais par un litteral, et
    la mesure ci-dessous le montre plutot que de le supposer. Une chaine en dur
    aurait annonce, apres le renommage, un dossier qui n'existe plus -- et
    l'ecart ne se serait vu qu'a l'usage.
    """
    fautifs: list[str] = []
    for module in _modules_de_la_tui():
        fautifs += [f"  {module.name}:{ligne}: {forme}"
                    for ligne, forme in _compositions_de_chemin(
                        module.read_text(encoding="utf-8"))]
    assert fautifs == [], (
        "un module de `tui/` compose un nom de dossier a la main : il doit "
        "passer par `io/project_layout`, seul lieu du depot ou ces noms sont "
        "ecrits.\n" + "\n".join(fautifs))


#: **Les bancs qui composent ENCORE un nom de dossier a la main**, nommes un
#: par un plutot que decrits (AC 6.4 : « la liste des exceptions NOMMEES dans
#: le test plutot que dans un commentaire »).
#:
#: Ils n'appartiennent pas au lot E2 -- ce sont les bancs des autres familles,
#: qui suivront. Les nommer ici sert deux choses a la fois : le perimetre de la
#: frontiere est le RESTE, donc il se DERIVE et ne peut pas retrecir en silence
#: quand quelqu'un edite une liste ; et cette liste-ci dit exactement ce que la
#: story 11.14 laisse ouvert cote bancs.
#:
#: **Le sens est a UNE SEULE VOIE, et c'est delibere** : un banc de cette liste
#: a le droit de devenir propre -- c'est un progres, et il ne doit pas faire
#: rougir un agent qui travaille en parallele. C'est le PLAFOND ci-dessous qui
#: empeche la liste de servir de fourre-tout.
BANCS_QUI_COMPOSENT_ENCORE_A_LA_MAIN = frozenset({
    "outils_identite_encode.py", "outils_identite_scan.py",
    "test_aruco_detection.py", "test_bascule_calibration_pile_seule.py",
    "test_cadence_previz.py", "test_calibration_profile.py",
    "test_calibration_provenance_wiring.py", "test_codec_profiles.py",
    "test_encode_noyau.py", "test_extract_command.py",
    "test_extraction_manifest.py", "test_ffmpeg_utils.py",
    "test_identite_du_scan.py", "test_inventaire_de_projet.py",
    "test_liste_des_profils_designes.py", "test_lots_encodables.py",
    "test_makepdf_noyau.py", "test_poc_run.py", "test_poc_scan_bit_depth.py",
    "test_project_layout.py", "test_retours_terrain_2026_08_27.py",
    "test_scan_detect_command.py", "test_scan_detect_nouvelle_version.py",
    "test_scan_ingest.py", "test_scan_vrac_command.py",
    "test_scan_write_command.py", "test_source_confirmation.py",
    "test_versions_de_planche.py",
    "tui/test_atelier_pdf_menu.py", "tui/test_atelier_pdf_parcours.py",
    "tui/test_atelier_scan_calibrate_aide_de_l_action.py",
    "tui/test_atelier_scan_completion_qr.py",
    "tui/test_atelier_scan_ecriture.py", "tui/test_atelier_scan_resultat.py",
    "tui/test_fermeture_vague_4_tui.py", "tui/test_fermeture_vague_B_tui.py",
    "tui/test_frontieres_et_grille_scan.py",
    "tui/test_frontieres_et_grille_scan_temps_2.py",
    "tui/test_palier_projet.py",
})

#: Le PLAFOND, mesure sur les fichiers ci-dessus : **307** compositions dans
#: 40 fichiers. Il ne peut que DESCENDRE, et il l'a deja fait : 320 dans 42
#: fichiers a la premiere pose, le 2026-09-04, avant que les deux bancs de
#: calibration du scan ne rejoignent la garde le meme jour.
#:
#: Sans lui, la liste d'exceptions serait un fourre-tout : il suffirait d'y
#: inscrire un banc pour avoir le droit d'y ecrire autant de litteraux qu'on
#: veut. Un cardinal qui ne peut que descendre transforme une liste de dettes
#: en une dette qui se rembourse -- et il rougit si une regression en ajoute,
#: y compris DANS un fichier deja excuse, ce que la liste seule ne verrait pas.
#:
#: **307 -> 297 le 2026-09-05** (`EPIC11-ARB-224`) : les 24 `projet / "outputs"`
#: de `test_suppression_element_de_projet.py` lisent desormais
#: `project_layout.OUTPUTS_DIRNAME`. La descente s'ecrit dans le meme commit
#: que le portage, comme cette note l'exige -- sinon la dette remboursee laisse
#: une marge ou la regression suivante se glisse sans rougir. Elle a d'ailleurs
#: failli : ce lot avait AJOUTE quinze litteraux, et c'est ce plafond-la qui
#: les a vus, aucune relecture.
#:
#: **297 -> 207 le 2026-09-05**, a la cloture de la revue d'`EPIC11-ARB-224`.
#: Le plafond avait ete franchi (300 pour 297) par la fermeture de la revue de
#: la 11.13, qui avait ajoute TROIS compositions au meme banc -- premier accroc
#: depuis que la dette est mesuree, et c'est cette frontiere qui l'a vu.
#:
#: Plutot que de rendre les trois, `test_suppression_element_de_projet.py` a
#: ete porte ENTIEREMENT -- ses 93 litteraux, de tres loin le premier
#: contributeur du depot -- et **sort de la liste des exceptions**. Il passe
#: donc desormais sous la frontiere stricte du dessus, celle qui n'admet aucun
#: litteral : une dette remboursee ne se surveille plus par un plafond, elle
#: cesse d'exister. Les quatre familles portees valent EXACTEMENT ce qu'elles
#: valaient -- `LEGACY_FRAMES_DIRNAME`, `LEGACY_OUTPUT_FRAMES_DIRNAME`,
#: `LEGACY_SOURCES_DIRNAME` pour les noms d'avant, `PLANCHES_DIRNAME` et
#: `SCANS_DIRNAME` pour les autres --, si bien que le portage ne change aucun
#: verdict : 266 passed / 2 skipped avant comme apres.
PLAFOND_DES_COMPOSITIONS_RESTANTES = 207


def _bancs_a_garder():
    """Le perimetre de la frontiere : TOUS les bancs, moins les exceptions.

    **Derive par glob, jamais tape.** Une liste ecrite a la main peut perdre un
    nom sans que rien ne le voie -- mesure : un mutant qui retirait le premier
    fichier d'une telle liste SURVIVAIT a la campagne du lot E2. Le perimetre
    etant ici le COMPLEMENT d'une liste, retirer un nom des exceptions AJOUTE
    un fichier a la garde au lieu d'en retirer un : le sens de la panne est
    inverse, et c'est ce qui ferme le trou. Un banc NEUF est garde d'office.
    """
    fichiers = (sorted((_RACINE_DU_DEPOT / "tests" / "unit").glob("*.py"))
                + sorted((_RACINE_DU_DEPOT / "tests" / "unit" / "tui")
                         .glob("*.py")))
    racine = _RACINE_DU_DEPOT / "tests" / "unit"
    return [chemin for chemin in fichiers
            if str(chemin.relative_to(racine))
            not in BANCS_QUI_COMPOSENT_ENCORE_A_LA_MAIN]


def _compositions_des_bancs(chemins) -> list[str]:
    """Le COLLECTEUR : chaque fichier balaye, ses trouvailles rassemblees.

    Il est isole de la frontiere qui l'emploie pour une seule raison, et c'est
    la lecon la plus chere de cette story : **une frontiere negative attend une
    liste vide, donc elle reste verte si le balayage qui l'alimente est
    tronque**, et aucune de ses propres assertions ne peut le voir. Un `[:-1]`
    ici rendrait la frontiere ci-dessous verte a jamais. C'est pourquoi ce
    collecteur a son propre temoin, sur un corpus miniature a trois bords.
    """
    trouves: list[str] = []
    for chemin in chemins:
        trouves += [
            f"  {chemin.name}:{ligne}: {forme}"
            for ligne, forme in _compositions_de_chemin(
                chemin.read_text(encoding="utf-8"))]
    return trouves


def test_aucun_banc_GARDE_ne_compose_un_nom_de_dossier_a_la_main():
    """Frontiere NEGATIVE contre la reintroduction d'un chemin litteral.

    C'est le defaut que le lot E2 vient de payer sur vingt-neuf tests : un banc
    qui ecrit `projet / "output-frames"` regarde un dossier que plus personne
    n'ecrit. Le rouge est le cas HEUREUX -- le cas couteux est le vert, quand le
    litteral alimente un collecteur qui rend vide sans se plaindre : huit tests
    de ce lot comparaient `{}` a `{}` en restant verts.

    Aucun test positif ne verrait revenir ce defaut : c'est exactement ce qu'une
    frontiere negative existe pour attraper.
    """
    fautifs = _compositions_des_bancs(_bancs_a_garder())
    assert fautifs == [], (
        "un banc GARDE compose un nom de dossier a la main. Il doit passer par "
        "`io/project_layout` -- seul lieu du depot ou ces noms sont ecrits, et "
        "seul endroit qui connaisse la cohabitation du nom neuf et de celui "
        "d'avant (`EPIC11-ARB-222`).\n" + "\n".join(fautifs))


def test_la_DETTE_de_composition_ne_peut_que_DESCENDRE():
    """Le plafond, et il ferme le seul echappatoire de la frontiere ci-dessus.

    Celle-ci se contourne en une ligne : inscrire son fichier dans les
    exceptions. Le plafond rend ce geste visible -- il compte les litteraux
    RESTANTS, exceptions comprises, et rougit des qu'on en ajoute. Une liste de
    dettes devient une dette qui se rembourse.

    **On compare un cardinal ici, et c'est le seul endroit ou c'est legitime** :
    ce n'est pas une preuve d'identite entre deux ensembles (« un cardinal
    stable n'est pas une preuve »), c'est une BORNE. Elle ne dit pas quels
    litteraux restent -- la frontiere voisine et la liste nommee le disent --,
    elle dit seulement qu'il n'y en a pas davantage.
    """
    racine = _RACINE_DU_DEPOT / "tests" / "unit"
    restants = _compositions_des_bancs(
        chemin for chemin in
        (sorted(racine.glob("*.py")) + sorted((racine / "tui").glob("*.py")))
        if str(chemin.relative_to(racine))
        in BANCS_QUI_COMPOSENT_ENCORE_A_LA_MAIN)
    assert len(restants) <= PLAFOND_DES_COMPOSITIONS_RESTANTES, (
        f"{len(restants)} compositions litterales restantes pour un plafond de "
        f"{PLAFOND_DES_COMPOSITIONS_RESTANTES} : une regression en a AJOUTE. "
        "Le plafond ne monte pas ; il descend quand une famille de bancs est "
        "portee, et cette descente s'ecrit dans le meme commit.")


def test_le_PERIMETRE_garde_ne_perd_aucun_banc():
    """Le collecteur **un cran plus haut**, et il lui fallait son propre temoin.

    `test_le_balayage_des_bancs_VOIT_ses_TROIS_bords` mesure le SCANNER
    (`_compositions_des_bancs`) ; il ne mesure pas le CONSTRUCTEUR DE PERIMETRE
    (`_bancs_a_garder`). Mesure, et c'est pour cela que ce test existe : un
    mutant qui tronquait `_bancs_a_garder` d'un seul fichier SURVIVAIT a la
    campagne du lot E2 -- le fichier perdu cessait d'etre garde et rien ne le
    disait. C'est le meme defaut que les quatre survivants du lot D1, un cran
    au-dessus de l'appariement.

    La mesure compare **deux routes differentes** vers le meme ensemble --
    `glob` d'un cote, `iterdir` de l'autre --, jamais une expression a
    elle-meme : une troncature n'affecte qu'une des deux, et l'ecart se voit.
    Comparer un cardinal ne suffirait pas ; ce sont les ENSEMBLES qui sont
    confrontes, parce qu'un fichier perdu et un fichier gagne s'annulent dans
    un compte.
    """
    racine = _RACINE_DU_DEPOT / "tests" / "unit"
    par_iterdir = {
        str(chemin.relative_to(racine))
        for dossier in (racine, racine / "tui")
        for chemin in dossier.iterdir()
        if chemin.is_file() and chemin.suffix == ".py"
    } - set(BANCS_QUI_COMPOSENT_ENCORE_A_LA_MAIN)
    par_glob = {str(chemin.relative_to(racine))
                for chemin in _bancs_a_garder()}

    assert par_glob == par_iterdir, (
        "le perimetre garde et le contenu reel des dossiers de bancs "
        f"divergent. Absents du perimetre : {sorted(par_iterdir - par_glob)} ; "
        f"en trop : {sorted(par_glob - par_iterdir)}. Un banc absent du "
        "perimetre n'est plus garde, et la frontiere negative reste verte.")


def test_le_collecteur_d_ALIAS_ne_perd_aucun_module():
    """Meme famille, sur l'autre collecteur de ce banc.

    `_modules_qui_referencent` alimente QUATRE mesures d'ici, dont deux qui
    attendent un ensemble vide. Un mutant qui tronquait `_alias_lus_par_la_tui`
    d'un module SURVIVAIT lui aussi : le module perdu cessait d'etre inspecte,
    et les frontieres negatives s'en trouvaient plus vertes, pas moins.

    Les deux routes, ici, sont la table construite par le collecteur et la
    liste de modules dont elle est censee etre l'image. Confrontees en
    ENSEMBLES, pas en cardinaux.
    """
    assert set(_alias_lus_par_la_tui()) == {
        module.name for module in _modules_de_la_tui()}, (
        "la table des alias n'a plus une entree par module de `tui/` : le "
        "balayage est tronque, et toutes les frontieres negatives qui la "
        "lisent sont devenues plus vertes qu'elles ne devraient.")

    # **Et le FILTRE par-dessus la table, qui est un second endroit ou tronquer.**
    # La mesure ci-dessus tient la table ; elle ne tient pas `_modules_qui_
    # referencent`, qui la reparcourt -- et c'est LA que le mutant survivant du
    # lot E2 coupait. Le motif `.*` fait rendre au filtre tout module portant au
    # moins un nom : il doit les rendre TOUS, y compris celui de queue.
    portant_un_nom = {nom for nom, noms in _alias_lus_par_la_tui().items()
                      if noms}
    assert _modules_qui_referencent(r".*") == portant_un_nom, (
        "le filtre `_modules_qui_referencent` ne rend plus tous les modules "
        "que la table lui donne : il est tronque. Les frontieres negatives "
        "qu'il alimente attendent des ensembles VIDES -- une troncature les "
        "rend donc vertes, jamais rouges, et aucune ne peut le voir.")


def test_le_balayage_des_bancs_VOIT_ses_TROIS_bords(tmp_path):
    """Volet symetrique de la frontiere, et il porte tout son poids.

    Elle attend une liste vide : elle serait verte pour un collecteur qui ne lit
    plus rien, pour une sequence de fichiers tronquee, pour un
    `_compositions_de_chemin` devenu muet. Aucune de ses assertions ne peut voir
    cela -- c'est le defaut trouve sur les lots C, D1 et D3 de cette meme story,
    trois fois de suite.

    Le temoin part donc d'un **corpus miniature reel**, traverse par le MEME
    collecteur, avec une cible a CHAQUE BORD (regle des fabriques, point 4 du
    2026-09-03) : en TETE, au MILIEU et en QUEUE, et **distinguables** -- trois
    dossiers differents, pas un remplissage uniforme. Une cible au milieu
    demasque un `find` fautif ; elle ne demasque PAS un balayage tronque, qui
    est un autre mode de panne. Ici, `[1:]` perd la tete et `[:-1]` la queue.
    """
    corpus = []
    for nom, dossier in (("a_tete.py", "frames"),
                         ("m_milieu.py", "output-frames"),
                         ("z_queue.py", "frames-scannees")):
        chemin = tmp_path / nom
        chemin.write_text(f'x = racine / "{dossier}"\n', encoding="utf-8")
        corpus.append(chemin)

    trouves = _compositions_des_bancs(corpus)

    assert len(trouves) == 3, trouves
    assert "a_tete.py" in trouves[0] and "'frames'" in trouves[0], trouves
    assert "m_milieu.py" in trouves[1], trouves
    assert "z_queue.py" in trouves[2] and "'frames-scannees'" in trouves[2], (
        trouves)


def test_la_mesure_des_compositions_de_chemin_MORD():
    """Volet symetrique : sans lui, la frontiere ci-dessus serait verte pour un
    balayage qui ne voit rien -- ou pour un `DOSSIERS_DE_L_ARBORESCENCE` vide.

    Les trois formes sont mesurees **une par une**, et la source temoin porte
    aussi un voisin qui ne doit PAS mordre (`"frames_scannees"`, l'identifiant
    de nature, qui n'est pas un nom de dossier).
    """
    temoin = (
        'a = racine / "frames"\n'
        'b = Path("output-frames")\n'
        'c = racine.joinpath("frames-scannees")\n'
        'd = "frames_scannees"\n'
        'e = racine / autre\n'
    )
    trouves = _compositions_de_chemin(temoin)
    assert [forme for _, forme in trouves] == [
        "... / 'frames'", "Path('output-frames')",
        "joinpath('frames-scannees')"], trouves


def test_l_exception_du_CORPUS_DE_FIXTURES_ne_couvre_QUE_sa_chaine():
    """Volet symetrique de `SEGMENT_DU_CORPUS_DE_FIXTURES`.

    Une exception qui se contenterait de regarder si le mot `fixtures` figure
    quelque part dans le FICHIER rendrait muette toute composition de projet
    ecrite dans un banc qui lit aussi un corpus -- c'est-a-dire dans la moitie
    des bancs de scan. La mesure porte donc sur la **chaine de `/`**, et ce
    temoin le tient : les deux formes se suivent dans la meme source, et seule
    la seconde est attrapee.

    La derniere ligne mesure le cas qui a motive l'exception : le segment
    arrive par un `Path(...)` imbrique, pas par une constante de tete.
    """
    temoin = (
        'a = racine / "fixtures" / "scans"\n'
        'b = projet / "scans"\n'
        'c = Path(__file__).resolve().parents[1] / "fixtures" / "scans"\n'
    )
    trouves = _compositions_de_chemin(temoin)
    assert [(ligne, forme) for ligne, forme in trouves] == [
        (2, "... / 'scans'")], trouves


# ---------------------------------------------------------------------------
# Les alias transitoires du lot B -- la TUI n'en lit plus aucun
# ---------------------------------------------------------------------------

def _noms_references(source: str) -> set[str]:
    """Tout nom reellement REFERENCE par le code -- prose exclue.

    A l'AST, jamais au grep : le docstring de ce banc cite `FRAMES_DIRNAME`
    pour l'expliquer, et un balayage de texte y mordrait, ce qui reviendrait a
    se faire affaiblir par sa propre explication. C'est la lecon de
    `outils_frontiere`, ecrite a la story 11.0.
    """
    arbre = ast.parse(source)
    noms: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.ImportFrom):
            noms.update(alias.name for alias in noeud.names)
    return noms


@pytest.mark.parametrize("alias", ALIAS_TRANSITOIRES)
def test_aucun_module_de_la_TUI_ne_lit_un_ALIAS_transitoire(alias):
    """Une frontiere par alias (meme forme que l'AC 4.3).

    Ces deux alias portent la valeur NEUVE : aucun balayage de CHAINES ne peut
    les voir, et c'est precisement ce qui les rend dangereux. Le lot B les a
    poses pour que la branche continue de s'importer pendant la transition, en
    ecrivant qu'ils tombent quand « les lots C, D et E [seront] passes aux noms
    neufs ». Ce test est la moitie qui dit que le lot D est passe.
    """
    fautifs = [f"tui/{nom}" for nom, noms in _alias_lus_par_la_tui().items()
               if alias in noms]
    fautifs += [f"tests/unit/tui/{nom}"
                for nom, noms in _alias_lus_par_les_BANCS().items()
                if alias in noms]
    assert fautifs == [], (
        f"{fautifs} lit encore l'alias transitoire {alias!r} : le nom porte le "
        "mot ambigu que la story 11.14 retire, alors meme que sa VALEUR est "
        "juste. Lire `EXTRACT_FRAMES_DIRNAME` / `SCAN_FRAMES_DIRNAME`.")


# ---------------------------------------------------------------------------
# Ce que le lot D1 NE POUVAIT PAS renommer -- ecrit ici plutot que tu
# ---------------------------------------------------------------------------
#
# Deux references de la TUI portent encore le mot `output_frames`, et elles ne
# sont PAS de la meme famille. Les confondre dirait quelque chose de faux : la
# premiere est FIGEE par un arbitrage, la seconde ATTEND un nom qui n'existe
# pas. C'est pourquoi elles sont mesurees separement, et dans les deux sens.

#: **Le nom de CLE de manifeste -- fige par `EPIC11-ARB-221`, a ne PAS
#: renommer.** Egan, 2026-09-04, a pris le regime « surfaces seules » : les
#: cles JSON restent telles quelles, `output_frames_dir` compris, et le schema
#: ne monte pas de version. Le cout est nomme dans l'arbitrage : « le
#: manifeste continuera de dire l'ancien vocabulaire la ou toute l'interface
#: dira le neuf ».
#:
#: Ce test est donc une frontiere **positive**, et c'est delibere : il existe
#: pour qu'un agent zele qui renommerait cette lecture « par coherence » se
#: fasse arreter par une mesure plutot que par une relecture.
LECTURES_DE_CLE_DE_MANIFESTE = {"atelier_exports_lot.py"}

#: **Le nom de FONCTION de coeur -- perime, mais sans pendant.**
#: `io/project_layout` publie `output_frames_dir_from_slug` et n'a pas de
#: `scan_frames_dir_from_slug` (le lot B a bien ecrit le pendant EXTRAIT,
#: `extract_frames_dir_from_slug`, pas le pendant SCANNE). Un module de `tui/`
#: qui l'appelle n'a donc **rien d'autre a appeler** : ce n'est pas un defaut
#: du lot D1, c'est une surface restee dans `io/`, hors de son perimetre.
#:
#: Ce releve est ecrit **pour que le nombre soit quelque part**. C'est la
#: lecon du lot A -- « le nom qu'on ne trouve pas est celui qu'on oublie de
#: renommer » -- et celle du lot B : un cardinal qui ne bouge pas apres un
#: renommage de fond ne dit pas que rien n'a change.
APPELS_DE_FONCTION_AU_NOM_PERIME: set[str] = set()

#: **Le pendant NEUF de la ligne ci-dessus, et il n'est pas decoratif.**
#: `APPELS_DE_FONCTION_AU_NOM_PERIME` est VIDE depuis que le lot B a publie
#: `scan_frames_dir_from_slug` et que l'appel a ete porte : un ensemble vide
#: compare a un ensemble vide est vrai meme si `_modules_qui_referencent`
#: avait cesse de trouver quoi que ce soit. Ce releve-ci fait donc PARLER le
#: meme collecteur sur un nom qui existe -- c'est le volet symetrique sans
#: lequel la frontiere negative ne mesurerait plus rien.
APPELS_DE_FONCTION_AU_NOM_NEUF = {"atelier_scan_ecriture.py"}


def _modules_qui_referencent(motif: str) -> set[str]:
    compile_ = re.compile(motif)
    return {nom for nom, noms in _alias_lus_par_la_tui().items()
            if any(compile_.fullmatch(reference) for reference in noms)}


def test_la_CLE_de_manifeste_est_TOUJOURS_lue_telle_quelle():
    """`EPIC11-ARB-221` : les cles du manifeste NE changent PAS.

    Frontiere **positive**, et c'est le seul endroit de ce banc ou elle l'est.
    Toutes les autres mesures d'ici retirent un mot ; celle-ci en RETIENT un,
    parce qu'un renommage « par coherence » casserait la lecture de tous les
    projets deja sur disque -- ce qu'`EPIC11-ARB-222` interdit explicitement
    (« un projet existant ne se convertit pas »).
    """
    assert (_modules_qui_referencent(r"output_frames_dir")
            == LECTURES_DE_CLE_DE_MANIFESTE), (
        "la lecture de la cle de manifeste `output_frames_dir` a bouge. "
        "Elle est FIGEE par EPIC11-ARB-221 : le regime retenu est « surfaces "
        "seules », les cles JSON restent telles quelles.")


def test_le_RELEVE_des_noms_de_FONCTION_encore_perimes_est_EXACT():
    """Il ne rougit pas d'un defaut : il rougit d'un CHANGEMENT non consigne.

    **Le releve est VIDE, et il l'est parce que la prediction s'est realisee.**
    Il portait `atelier_scan_ecriture` pour le nom `output_frames_dir_from_slug`,
    avec cette phrase : « le jour ou `io/project_layout` publiera le pendant au
    nom neuf, ce test rougira et obligera a porter l'appel plutot qu'a
    l'oublier ». Le lot B a publie `scan_frames_dir_from_slug`, l'appel a ete
    porte, et ce banc a bien rougi -- c'est le lot E2 qui l'a solde. Le releve
    ne se vide donc pas par relachement : il se vide parce qu'il n'a plus rien
    a nommer.

    **Un ensemble vide ne se mesure pas seul** -- il resterait vert si
    `_modules_qui_referencent` avait cesse de trouver quoi que ce soit. C'est
    tout l'objet de `test_l_appel_PORTE_est_bien_VU_par_le_meme_collecteur`
    juste dessous : le meme collecteur, sur le meme module, pour le nom NEUF.

    **La borne du releve est nommee** : `frames_dir` n'y entre pas, parce que
    la fonction ne dit rien de faux -- un lot est bien « un ensemble de frames
    extraites », et c'est le mot d'Egan.
    """
    assert (_modules_qui_referencent(r"output_frames_dir_from_slug")
            == APPELS_DE_FONCTION_AU_NOM_PERIME), (
        "le releve des appels de coeur au nom perime a bouge. Si "
        "`io/project_layout` a publie un nom neuf, porter l'appel ; si un "
        "appel a ete ajoute, il n'avait pas a l'etre.")


def test_l_appel_PORTE_est_bien_VU_par_le_meme_collecteur():
    """Volet symetrique du test ci-dessus, et il porte tout son poids.

    Sans lui, `set() == set()` serait vert le jour ou `_noms_references`
    cesserait de lire les appels -- une troncature du balayage, un motif trop
    etroit, un module deplace. Le collecteur est alors AVEUGLE et la frontiere
    negative le felicite. C'est le piege paye trois fois dans cette story :
    « une frontiere negative attend une liste vide, elle reste verte si le
    balayage qui l'alimente est tronque, et aucune de ses propres assertions ne
    peut le voir ».

    La mesure fait donc dire au MEME collecteur, sur le MEME module, le nom
    NEUF -- `scan_frames_dir_from_slug`. Verte, elle prouve deux choses a la
    fois : que le balayage voit encore `tui/atelier_scan_ecriture.py`, et que
    l'appel y a bien ete porte au lieu d'y avoir ete supprime.
    """
    assert (_modules_qui_referencent(r"scan_frames_dir_from_slug")
            == APPELS_DE_FONCTION_AU_NOM_NEUF), (
        "le collecteur ne voit plus l'appel PORTE. Soit `atelier_scan_ecriture` "
        "a cesse d'appeler `scan_frames_dir_from_slug` -- et le chemin de "
        "resolution est alors recompose ailleurs, ce que `io/project_layout` "
        "existe pour empecher --, soit le balayage de `_noms_references` est "
        "tronque, auquel cas la frontiere negative voisine ne mesure plus rien.")


def test_la_TUI_lit_bien_les_constantes_NEUVES():
    """Volet symetrique du precedent, et il n'est pas decoratif.

    Sans lui, la frontiere serait verte pour une TUI qui ne lirait **aucune**
    constante de dossier -- par exemple parce qu'elle aurait recopie la chaine
    a la main, c'est-a-dire le defaut exact que l'autre frontiere de ce banc
    mesure. Les deux se tiennent l'une l'autre.
    """
    table = _alias_lus_par_la_tui()
    attendus = {module.name for module in _modules_de_la_tui()}
    assert set(table) == attendus, set(table) ^ attendus
    lus: set[str] = set().union(*table.values())
    assert "EXTRACT_FRAMES_DIRNAME" in lus, (
        "aucun module de `tui/` ne lit le nom du dossier des frames "
        "extraites : il le compose donc a la main quelque part")

    # Et cote bancs, les DEUX constantes neuves : sans ce volet, la frontiere
    # sur les alias serait verte pour une suite qui aurait simplement cesse de
    # nommer le dossier -- c'est-a-dire qui aurait cesse de le mesurer.
    lus_bancs: set[str] = set().union(*_alias_lus_par_les_BANCS().values())
    for neuve in ("EXTRACT_FRAMES_DIRNAME", "SCAN_FRAMES_DIRNAME"):
        assert neuve in lus_bancs, (
            f"aucun banc de `tests/unit/tui/` ne lit {neuve} : la frontiere "
            "sur les alias serait verte pour rien")
    # Et la valeur lue est bien celle du coeur, pas une chaine qui y ressemble.
    assert (atelier_extraction_ecriture.EXTRACT_FRAMES_DIRNAME
            is project_layout.EXTRACT_FRAMES_DIRNAME)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-222` -- l'ancien dossier reste lu, le NEUF aussi
# ---------------------------------------------------------------------------
#
# **Le trou que cette section ferme, et il est mesure.** Au 2026-09-04, les
# ~60 litteraux `output-frames/...` que porte `tests/unit/tui/` sont **tous**
# a l'ANCIENNE forme : aucun banc de la TUI ne fait passer un projet declarant
# `frames-scannees/`. La suite etait donc entierement verte sur la forme que la
# story RETIRE et n'exercait pas une seule fois celle qu'elle POSE -- la meme
# famille de defaut que « un cardinal stable n'est pas une preuve », vue du
# cote des entrees plutot que des sorties.
#
# Les traduire en masse appartient au lot E ; ce qui manquait ici et qui ne
# coute rien, c'est le VOLET SYMETRIQUE : une mesure qui joue les DEUX formes
# dans le meme test et exige le meme verdict.


def _manifeste_a_deux_lots(premier: str, dernier: str) -> dict:
    """Deux lots **distinguables**, leurs dossiers de frames scannees nommes.

    Regle des fabriques, points 1 et 4 : deux elements, jamais un remplissage
    uniforme, et les deux formes du nom de dossier sont posees **aux deux
    bords** de la liste plutot qu'au milieu -- un balayage tronque en tete ou
    en queue est un mode de panne que la cible du milieu ne demasque pas.
    """
    return {
        "schema_version": "2.1", "project_id": "p", "rushes": [],
        "lots": [
            {"lot_id": "premier", "state": "scan",
             "output_frames_dir": f"{premier}/premier", "encoded_masters": []},
            {"lot_id": "dernier", "state": "scan",
             "output_frames_dir": f"{dernier}/dernier", "encoded_masters": []},
        ],
    }


@pytest.mark.parametrize("dirname,forme", [
    (project_layout.SCAN_FRAMES_DIRNAME, "NEUVE"),
    (project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME, "ANCIENNE"),
])
def test_la_TUI_juge_PAREIL_un_projet_a_l_ANCIENNE_et_a_la_NOUVELLE_forme(
        tmp_path, dirname, forme):
    """`EPIC11-ARB-222` : « un projet existant ne se convertit pas ».

    Les deux formes doivent donner le MEME verdict, et la mesure porte sur les
    deux dans le meme banc : ne jouer que l'ancienne laisserait la TUI casser
    en silence sur un projet neuf, ne jouer que la neuve casserait tous les
    projets deja sur disque. C'est exactement la paire que l'arbitrage exige.

    La TUI n'a d'ailleurs **rien a faire** pour que ce soit vrai -- elle lit la
    VALEUR declaree au manifeste, elle ne recompose pas le nom du dossier --,
    et c'est precisement ce que ce test etablit plutot que de le supposer.
    """
    racine = tmp_path / f"projet_{forme.lower()}"
    racine.mkdir()
    document = _manifeste_a_deux_lots(dirname, dirname)
    for entree in document["lots"]:
        (racine / entree["output_frames_dir"]).mkdir(parents=True)

    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert par_nom["Exports"].disponible, (
        f"un projet a la forme {forme} ({dirname}/) n'ouvre pas Exports")


def test_les_DEUX_formes_COHABITENT_dans_un_meme_projet(tmp_path):
    """Le cas que ni l'un ni l'autre des deux precedents ne couvre.

    `EPIC11-ARB-222` ne convertit rien : un projet reel finira donc par porter
    des lots aux deux formes -- les anciens sous leur dossier d'origine, les
    neufs sous le nom neuf. La resolution du lot B est faite **par lot** et non
    par racine, exactement pour que ce cas tienne ; ce test le mesure du cote
    TUI, avec une forme a CHAQUE BORD de la liste.
    """
    racine = tmp_path / "projet_mixte"
    racine.mkdir()
    document = _manifeste_a_deux_lots(
        project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME,
        project_layout.SCAN_FRAMES_DIRNAME)
    # **La fabrique produit-elle vraiment DEUX formes ?** Regle des fabriques,
    # point 1 : un remplissage uniforme rendrait ce test vert en ne mesurant
    # plus aucune cohabitation, et rien d'autre ne le verrait.
    racines = {Path(entree["output_frames_dir"]).parts[0]
               for entree in document["lots"]}
    assert len(racines) == 2, racines
    for entree in document["lots"]:
        (racine / entree["output_frames_dir"]).mkdir(parents=True)

    par_nom = {e.nom: e for e in projet_lecture.entrees(document, racine)}
    assert par_nom["Exports"].disponible

    # Volet negatif : un dossier DECLARE mais absent ne doit pas ouvrir --
    # sans quoi le test ci-dessus serait vert pour une TUI qui ne regarde
    # jamais le disque, et ne mesurerait donc pas la forme du nom.
    vide = tmp_path / "projet_declare_sans_matiere"
    vide.mkdir()
    par_nom = {e.nom: e for e in projet_lecture.entrees(document, vide)}
    assert not par_nom["Exports"].disponible


# ===========================================================================
# `EPIC11-ARB-246` -- le jeton `Tab journal` est UNIQUE dans tout le produit
# ===========================================================================
#
# **Ce que cette section ferme, et ce qu'elle a coute avant d'exister.** Le
# depot a porte pendant tout l'Epic 11 **deux** formulations du meme geste :
# `Tab journal complet`, que quatre maquettes approuvees dessinaient et qu'un
# seul site du code rendait (`atelier_pdf_execution.RACCOURCIS_GENERATION`),
# et `Tab journal`, que la classe partagee `execution.EcranExecution` rend
# pour les quatre autres ecrans « en cours ». L'ecart etait EPINGLE des deux
# cotes dans trois bancs -- personne ne l'ignorait, personne ne pouvait le
# fermer sans arbitrage. Egan a tranche le 2026-09-06, par invite, verbatim :
# « Tab journal partout ». Ce sont les maquettes qui se sont alignees.
#
# **Pourquoi une frontiere NEGATIVE, et pas une egalite de plus.** Les bancs
# qui epinglaient l'ecart ont ete retournes : ils mesurent maintenant que le
# dessin et le rendu portent le MEME jeton. Aucun d'eux ne verrait un
# quinzieme ecran, ecrit demain, reintroduire la forme longue quelque part
# ailleurs -- une assertion positive reste verte a cote d'un nouveau site
# fautif. Seul un balayage qui attend ZERO l'attrape, et c'est la doctrine
# de tout ce fichier.
#
# **Ou la forme longue reste ECRIVABLE, dit plutot que tu.** Le balayage lit
# les chaines litterales (:func:`chaines_visibles`), docstrings comprises --
# meme largeur que le reste du banc, et pour le motif que son docstring
# donne : un nom perime lu dans un docstring est ce qui fait chercher ce qui
# n'existe plus. L'historique de l'arbitrage se cite donc en **commentaire**
# `#`, jamais dans une chaine ; c'est la forme retenue dans `execution.py` et
# dans `atelier_pdf_execution.py`.

#: La forme RETIREE du produit, et la seule qui doive rendre zero.
FORME_RETIREE_DU_JOURNAL = "Tab journal complet"

#: La forme retenue. Elle n'est pas la negation de la precedente : un produit
#: qui aurait perdu les DEUX ferait rougir le volet symetrique ci-dessous.
JETON_DU_JOURNAL = "Tab journal"

#: La racine des maquettes, second versant du perimetre. Une frontiere qui ne
#: balayerait que `src/` laisserait la forme longue revenir par le dessin --
#: c'est-a-dire par le cote d'ou elle venait.
_RACINE_DES_MAQUETTES = (_RACINE_DU_DEPOT / "_bmad-output"
                         / "planning-artifacts" / "ux-designs"
                         / "ux-tui-2026-08-27" / "maquettes")

#: La hauteur de la grille d'une maquette. Ce qui la depasse est une
#: annotation manuscrite d'Egan, jamais du contenu d'ecran -- et une note qui
#: relate l'arbitrage a le droit de citer la forme retiree.
_HAUTEUR_DE_GRILLE = 24


def grilles_des_maquettes(racine: Path | None = None) -> dict[str, list[str]]:
    """Les 24 lignes de grille de chaque maquette, une entree par fichier.

    **Le COLLECTEUR de ce versant**, ecrit avec sa `racine` en argument pour
    la meme raison que :func:`_modules_de_la_tui` : sans elle, aucun temoin ne
    peut traverser le listing, et une troncature (`[1:]`, `[:-1]`) laisserait
    la frontiere negative verte pour rien.
    """
    return {
        chemin.name: chemin.read_text(
            encoding="utf-8").split("\n")[:_HAUTEUR_DE_GRILLE]
        for chemin in sorted((racine or _RACINE_DES_MAQUETTES).glob("*.txt"))
    }


def _porteuses_du_jeton(grilles: dict[str, list[str]],
                        jeton: str) -> list[tuple[str, int, str]]:
    """`(maquette, numero de ligne, ligne)` de tout ce qui porte le jeton."""
    return [(nom, rang, ligne)
            for nom, lignes in grilles.items()
            for rang, ligne in enumerate(lignes, 1)
            if jeton in ligne]


# ---------------------------------------------------------------------------
# La frontiere negative, ses DEUX versants
# ---------------------------------------------------------------------------

def test_aucune_chaine_de_la_TUI_ne_porte_la_forme_RETIREE_du_journal():
    """Versant `src/` : un grep de la forme longue doit rendre ZERO.

    Le balayage est celui que tout ce fichier partage, donc une troncature du
    collecteur fait rougir
    :func:`test_le_balayage_de_la_TUI_VOIT_bien_quelque_chose` plutot que de
    verdir celui-ci en silence.
    """
    # **L'ancrage des deux constantes, et il n'est pas decoratif.** Les temoins
    # de bord ci-dessous ecrivent leur corpus AVEC
    # :data:`FORME_RETIREE_DU_JOURNAL` et le cherchent AVEC elle : remplacer
    # cette constante par une chaine que rien ne porte rendrait les deux
    # frontieres negatives vertes sans qu'aucun temoin ne bouge. L'ancrer au
    # jeton retenu ferme ce mutant -- et le jeton retenu, lui, est ancre au
    # produit par le volet symetrique.
    assert FORME_RETIREE_DU_JOURNAL == f"{JETON_DU_JOURNAL} complet"

    fautifs = {nom: _porteuses(chaines, re.escape(FORME_RETIREE_DU_JOURNAL))
               for nom, chaines in _balayage_de_la_tui().items()}
    fautifs = {nom: trouve for nom, trouve in fautifs.items() if trouve}
    assert not fautifs, (
        f"`{FORME_RETIREE_DU_JOURNAL}` est retire du produit "
        f"(`EPIC11-ARB-246`, « Tab journal partout ») : {fautifs}. "
        f"Le jeton du produit est `{JETON_DU_JOURNAL}`. Pour citer la forme "
        "retiree dans une note d'historique, l'ecrire en commentaire `#` et "
        "non dans une chaine.")


def test_aucune_MAQUETTE_ne_dessine_la_forme_RETIREE_du_journal():
    """Versant dessin, et il compte autant : la forme longue venait de la.

    Quatre maquettes la portaient -- `E2-4`, `E3-2`, `E3-7`, `E5-4` --, toutes
    corrigees A LA SOURCE dans leurs generateurs (`EPIC11-ARB-142` : jamais un
    rendu edite a la main). Sans ce versant, une regeneration a partir d'un
    generateur non corrige la ferait redescendre sans que rien ne rougisse.
    """
    fautives = _porteuses_du_jeton(grilles_des_maquettes(),
                                   FORME_RETIREE_DU_JOURNAL)
    assert not fautives, (
        f"ces maquettes dessinent encore `{FORME_RETIREE_DU_JOURNAL}` : "
        f"{[(nom, rang) for nom, rang, _ in fautives]}. Corriger le "
        "GENERATEUR puis relancer `regenerer.py`, jamais le `.txt`.")


# ---------------------------------------------------------------------------
# Les volets symetriques : une frontiere negative seule est verte sur le vide
# ---------------------------------------------------------------------------

def test_le_jeton_RETENU_est_bien_present_des_DEUX_cotes():
    """Sans lui, les deux tests ci-dessus resteraient verts sur un produit qui
    aurait perdu le jeton **entier** -- ce qui n'est pas ce qu'Egan a demande.

    Les cardinaux sont mesures, pas ecrits en dur : ce qui compte est qu'il y
    en ait plusieurs de chaque cote, et qu'ils portent tous la MEME forme.
    """
    du_code = {nom: _porteuses(chaines, re.escape(JETON_DU_JOURNAL))
               for nom, chaines in _balayage_de_la_tui().items()}
    du_code = {nom: trouve for nom, trouve in du_code.items() if trouve}
    assert len(du_code) >= 2, (
        f"le jeton `{JETON_DU_JOURNAL}` n'est plus rendu que par {du_code} : "
        "le produit l'a perdu au lieu de l'unifier")

    du_dessin = _porteuses_du_jeton(grilles_des_maquettes(), JETON_DU_JOURNAL)
    maquettes = {nom for nom, _, _ in du_dessin}
    assert len(maquettes) >= 4, (
        f"seules {sorted(maquettes)} dessinent `{JETON_DU_JOURNAL}` : les "
        "maquettes l'ont perdu au lieu de s'aligner")


def test_les_lignes_de_raccourcis_du_produit_disent_TOUTES_le_meme_jeton():
    """L'unicite, mesuree sur les lignes REELLES plutot que sur des chaines.

    Une chaine quelconque peut citer le jeton en prose ; une **ligne de
    raccourcis** est ce que l'operateur lit. Le balayage passe donc par le
    manuel, qui sait les collecter, et non par le texte des modules.
    """
    from mixed_media_utility.tui import manuel

    lignes = manuel.lignes_de_raccourcis_du_paquet()
    porteuses = {cle: ligne for cle, ligne in lignes.items()
                 if JETON_DU_JOURNAL in ligne}
    assert len(porteuses) >= 4, (
        f"seules {sorted(porteuses)} annoncent le journal : le collecteur "
        "voit moins que le produit, ou le produit a perdu le jeton")
    for cle, ligne in porteuses.items():
        libelles = [libelle for ouvreur, libelle
                    in manuel.items_d_une_ligne(ligne) if ouvreur == "Tab"]
        assert libelles == ["journal"], (
            f"{cle} annonce `Tab {libelles}` : le jeton du produit est "
            f"`{JETON_DU_JOURNAL}`, et il est UNIQUE (`EPIC11-ARB-246`)")


# ---------------------------------------------------------------------------
# Regle des fabriques, point 4 -- le collecteur des MAQUETTES a chaque BORD
# ---------------------------------------------------------------------------

#: Trois maquettes miniatures **distinguables**, nommees pour que `glob`, qui
#: trie, place `a_tete` en premier et `z_queue` en dernier. Meme forme que
#: :data:`_CORPUS_MINIATURE`, et pour la meme raison : la cible au milieu
#: demasque un `find` fautif, elle ne demasque pas un balayage tronque.
_MAQUETTES_MINIATURES = ("a_tete.txt", "m_milieu.txt", "z_queue.txt")


@pytest.mark.parametrize("position", (0, 1, 2), ids=("tete", "milieu", "queue"))
def test_le_collecteur_des_MAQUETTES_lit_la_PREMIERE_et_la_DERNIERE(
    tmp_path, position
):
    """`CLAUDE.md`, regle des fabriques, points 1, 2 et 4.

    Le corpus porte **trois** maquettes aux libelles differents -- un
    remplissage uniforme ne montrerait ni permutation ni troncature -- et la
    cible se pose successivement en TETE, au MILIEU et en QUEUE.
    """
    for rang, nom in enumerate(_MAQUETTES_MINIATURES):
        pied = f"│ ⏎ choisir  Échap sortir  temoin {rang}"
        if rang == position:
            pied = f"│ {FORME_RETIREE_DU_JOURNAL}  Échap sortir  temoin {rang}"
        (tmp_path / nom).write_text(
            "\n".join([f"┌ maquette temoin {rang} ┐"] + [""] * 21
                      + [pied, "└" + "─" * 20 + "┘"]) + "\n",
            encoding="utf-8")

    grilles = grilles_des_maquettes(racine=tmp_path)

    # 1. Le collecteur rend les TROIS maquettes -- c'est lui qui est mesure.
    assert sorted(grilles) == sorted(_MAQUETTES_MINIATURES), (
        f"le collecteur rend {sorted(grilles)} pour "
        f"{sorted(_MAQUETTES_MINIATURES)} : il tronque le listing, et une "
        "frontiere negative qui attend une liste VIDE n'en devient que plus "
        "verte.")

    # 2. Et la frontiere, alimentee par ce collecteur, MORD a cette position.
    fautives = _porteuses_du_jeton(grilles, FORME_RETIREE_DU_JOURNAL)
    assert [nom for nom, _, _ in fautives] == [_MAQUETTES_MINIATURES[position]], (
        f"la forme retiree posee en position {position} sur "
        f"{len(_MAQUETTES_MINIATURES)} est vue dans {fautives}")


def test_le_collecteur_des_MAQUETTES_s_ARRETE_a_la_GRILLE(tmp_path):
    """Une annotation manuscrite SOUS le cadre n'est pas du contenu d'ecran.

    C'est la contrepartie exacte du point ci-dessus : le collecteur doit
    couper a 24 lignes. Sans cette mesure, la coupe pourrait disparaitre sans
    que rien ne rougisse -- et une note d'Egan qui relate l'arbitrage en
    citant la forme retiree ferait alors rougir la frontiere pour rien.
    """
    (tmp_path / "annotee.txt").write_text(
        "\n".join([f"ligne {rang}" for rang in range(_HAUTEUR_DE_GRILLE)]
                  + [f"NOTE : on retire « {FORME_RETIREE_DU_JOURNAL} » d'ici"])
        + "\n",
        encoding="utf-8")

    grilles = grilles_des_maquettes(racine=tmp_path)
    assert len(grilles["annotee.txt"]) == _HAUTEUR_DE_GRILLE
    assert not _porteuses_du_jeton(grilles, FORME_RETIREE_DU_JOURNAL)


def test_le_perimetre_des_MAQUETTES_balayees_est_bien_CELUI_du_depot():
    """La garde qui empeche le collecteur de pointer sur un dossier vide.

    Une frontiere negative branchee sur une racine fausse est verte pour
    toujours. C'est le meme filet que
    :func:`test_le_balayage_de_la_TUI_VOIT_bien_quelque_chose`.
    """
    grilles = grilles_des_maquettes()
    assert len(grilles) >= 80, (
        f"{len(grilles)} maquettes balayees : la racine "
        f"{_RACINE_DES_MAQUETTES} n'est plus la bonne")
    for nom in ("E2-4-extraction-execution.txt", "E5-4-pdf-execution.txt",
                "E6-3-projet-suppression-resultat.txt"):
        assert nom in grilles, nom
        assert len(grilles[nom]) == _HAUTEUR_DE_GRILLE, nom
        # **La coupe tombe-t-elle au bon endroit ?** Le test ci-dessus est
        # tautologique -- il relit la constante qu'il mesure. Le bas du cadre,
        # lui, est une valeur du DEPOT : la derniere ligne de grille d'une
        # maquette est son bord inferieur, et une coupe d'un cran trop haut la
        # perd. C'est le seul point de ce test qui ne se deplace pas avec la
        # borne.
        assert grilles[nom][-1].startswith("└"), (
            f"{nom}: la grille ne finit pas sur le bas du cadre -- "
            f"la coupe a {_HAUTEUR_DE_GRILLE} lignes tombe a cote")


# ---------------------------------------------------------------------------
# `Q21` -- le jeton est RETIRE de `E6-3` et `E6-3b`, dessin ET code
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("maquette", [
    "E6-3-projet-suppression-resultat.txt",
    "E6-3b-projet-suppression-reussie.txt",
])
def test_les_deux_comptes_rendus_de_SUPPRESSION_n_annoncent_AUCUN_journal(
    maquette: str,
):
    """`EPIC11-ARB-246`, second volet (Egan : « Retirer le jeton de ces deux
    ecrans »). Ni le dessin, ni le code.

    Ces deux ecrans n'ont **aucun** journal a ouvrir : `monter_le_compte_rendu`
    ne leur en passe pas, et leurs `__init__` ne savent plus en recevoir un.
    Annoncer la touche etait le defaut `I8`, paye quarante fois par ce depot.
    """
    from mixed_media_utility.tui import projet_suppression

    grille = grilles_des_maquettes()[maquette]
    pieds = [ligne for ligne in grille if "F1 aide" in ligne]
    assert len(pieds) == 1, f"{maquette}: {len(pieds)} lignes de raccourcis"
    assert "Tab" not in pieds[0], f"{maquette}: le dessin annonce encore Tab"
    # Le dessin porte bien la ligne du produit, mot pour mot -- sans quoi le
    # retrait ci-dessus serait vrai d'un dessin devenu etranger au code.
    assert projet_suppression.RACCOURCIS_RESULTAT in pieds[0]
    assert "Tab" not in projet_suppression.RACCOURCIS_RESULTAT


@pytest.mark.parametrize("nom", ["EcranResultatDeSuppression",
                                 "EcranReussiteDeSuppression"])
def test_les_deux_comptes_rendus_de_SUPPRESSION_ne_RECOIVENT_plus_de_journal(
    nom: str,
):
    """Le retrait est STRUCTUREL, et c'est ce qui le rend tenable.

    `EcranResultat.__init__` remplace la ligne de raccourcis par
    `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` des qu'un journal lui est
    passe -- une ligne qui annonce `Tab journal` **et** dit `Échap ateliers`
    la ou ces deux ecrans disent `Échap inventaire`. Laisser le mot-cle
    recevable, c'etait laisser ouvert le chemin qui retablit le jeton sans un
    mot. Une frontiere sur la seule constante ne l'aurait pas vu.
    """
    import inspect

    from mixed_media_utility.tui import projet_suppression

    parametres = inspect.signature(
        getattr(projet_suppression, nom).__init__).parameters
    assert "journal" not in parametres, (
        f"{nom} accepte encore un `journal` : `EPIC11-ARB-246` retire "
        "`Tab journal` de cet ecran, et un journal passe le RETABLIRAIT en "
        "remplacant sa ligne de raccourcis")
