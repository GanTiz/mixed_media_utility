# -*- coding: utf-8 -*-
"""La frontiere qui compte, pour chaque `SUITE_*` declaree, sa branche nommee.

**Le mode de panne que ce banc ferme, et il a ete paye deux fois le meme
jour** (audit du parcours complet, 2026-09-06, entrees `MQ-4` et `MQ-5`) : un
filet `EcranPasEncore` pose quand l'atelier cible n'existait pas, **laisse en
place quand il a ete livre**, et justifie par un docstring que personne n'a
rouvert.

Aucun banc ne rougissait, et c'est ce qu'il faut comprendre avant de lire la
suite : le filet **fonctionne**. Il nomme une absence, exactement comme prevu,
et son banc mesure qu'il la nomme. Ce qui a change, c'est que l'absence n'en
est plus une -- l'atelier Pdf est livre (story 11.7), l'atelier Exports aussi
(story 11.8) --, et rien dans le code ne relie ces deux faits. Une suite
declaree qui tombe dans le filet est donc indistinguable, pour toute mesure
existante, d'une suite qui n'a legitimement pas de destination.

**Ce que cette frontiere mesure**, et elle le mesure sur l'ARBRE SYNTAXIQUE
plutot que sur du texte -- un docstring qui cite `SUITE_PDF` pour dire qu'elle
n'a pas d'atelier porte le mot, et un grep y mordrait :

* pour chaque module qui **declare** des `SUITE_*`, et pour chacun des rappels
  qui les traitent, **toute suite declaree porte une branche NOMMEE** dans le
  rappel. Elle rougit donc le jour ou une suite neuve est declaree sans
  branche, **et** le jour ou un atelier est livre sans que son filet soit
  retire -- c'est le meme test, parce que c'est le meme fait ;
* le **volet symetrique**, et il n'est pas decoratif : une frontiere dont le
  recensement cesserait de reconnaitre quoi que ce soit passerait en
  n'observant rien. Les cardinaux du recensement sont donc bornes par le bas
  et mesures (:func:`test_le_recensement_voit_au_moins_ce_qui_existe`), et le
  recensement des modules declarants est confronte a la table
  (:func:`test_aucun_module_declarant_n_echappe_a_la_table`) : un module neuf
  qui declarerait des suites sans entrer dans la table fait rougir.

**Ce que cette frontiere NE mesure PAS, dit plutot que tu.** Elle mesure qu'une
branche est **nommee**, pas qu'elle mene quelque part d'utile : un
`if suite == SUITE_PDF: return` la satisferait. Ce que la branche fait est
mesure par les bancs de parcours, qui exercent le clavier et confrontent
l'ecran d'arrivee. Les deux mesures sont complementaires et aucune ne remplace
l'autre -- celle-ci attrape l'oubli, celle-la attrape l'erreur.

**Regle des fabriques (`CLAUDE.md`, les QUATRE points).** Les bancs des outils
de recensement ci-dessous travaillent sur des sources de synthese portant
**trois** suites aux libelles **distincts** (jamais un remplissage uniforme :
une permutation ne se verrait pas), et la suite non traitee y est placee tour a
tour **en tete**, **au milieu** et **en queue** -- le milieu demasque un
aiguillage fautif, les deux bords demasquent un balayage tronque, qui est un
autre mode de panne.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

#: La racine du paquet mesure. Deduite du fichier, jamais ecrite en dur : un
#: depot deplace ne doit pas faire rougir une frontiere de couverture.
PAQUET = Path(__file__).resolve().parents[3] / "src" / "mixed_media_utility"
TUI = PAQUET / "tui"

#: Ce qui fait d'un nom une suite. Les constantes de suite du depot sont des
#: majuscules prefixees, et c'est **la** convention que la table exploite.
MOTIF_DE_SUITE = re.compile(r"^SUITE_[A-Z0-9_]+$")

#: **Le motif est un PARAMETRE depuis le 2026-09-06**, et rien d'autre n'a
#: bouge ici. La meme mesure -- « toute constante declaree au module porte une
#: branche nommee dans son rappel » -- sert les entrees d'un palier, dont les
#: constantes sont prefixees `ENTREE_`. Sa frontiere vit dans
#: `test_couverture_des_entrees_de_palier.py`, qui **importe** ces outils
#: plutot que de les recopier ; le fichier reste separe pour deux raisons
#: mesurees, ecrites dans son propre docstring.


@dataclass(frozen=True)
class Couverture:
    """Un rappel de suites, et le module dont il doit traiter les declarations.

    `declarant` et `rappelant` different des que l'ecran de resultat vit dans
    un module et son parcours dans un autre -- c'est le cas de trois des cinq
    ateliers. Ils coincident pour les deux autres, et la table le dit plutot
    que de le deviner.
    """

    declarant: str
    rappelant: str
    #: Le chemin pointe de la fonction, `Classe.methode` ou `fonction`.
    rappel: str

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return f"{self.declarant} -> {self.rappelant}.{self.rappel}"


#: **La table des rappels de suites du produit.** Elle est confrontee au
#: recensement par :func:`test_aucun_module_declarant_n_echappe_a_la_table` :
#: un module qui declarerait des suites sans figurer ici fait rougir, si bien
#: que la table ne peut pas prendre du retard en silence.
COUVERTURES: tuple[Couverture, ...] = (
    Couverture("atelier_extraction_ecriture", "atelier_extraction_ecriture",
               "ParcoursExtraction.suivre"),
    Couverture("atelier_scan_resultat", "atelier_scan_resultat", "suivre"),
    Couverture("atelier_pdf_resultat", "atelier_pdf_parcours",
               "ParcoursPdf.suivre"),
    Couverture("atelier_pdf_calibration", "atelier_pdf_parcours",
               "ParcoursPdf.suivre_apres_la_mire"),
    Couverture("atelier_exports_resultat", "atelier_exports_parcours",
               "ParcoursExports.suivre"),
    Couverture("atelier_exports_resultat", "atelier_exports_resultat",
               "suivre"),
    Couverture("atelier_scan_calibrate", "atelier_scan_parcours",
               "ParcoursScan.suivre_le_resultat_de_la_calibration"),
    Couverture("projet_suppression", "projet_suppression", "suivre"),
)


# ---------------------------------------------------------------------------
# Le recensement -- il lit l'arbre syntaxique, jamais le texte
# ---------------------------------------------------------------------------

def arbre_du_module(nom: str) -> ast.Module:
    """L'arbre d'un module de `tui/`, lu sur le disque du depot."""
    chemin = TUI / f"{nom}.py"
    return ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))


def suites_declarees(arbre: ast.Module,
                     motif: re.Pattern = MOTIF_DE_SUITE) -> dict[str, str]:
    """Les `SUITE_*` **declarees au module**, et leur libelle.

    Seules les affectations de premier niveau comptent : une constante posee
    dans une fonction n'est pas une suite du produit, et une chaine egale a un
    libelle de suite croisee ailleurs n'en est pas une non plus. C'est la
    difference entre lire le code et lire du texte.
    """
    declarees: dict[str, str] = {}
    for noeud in arbre.body:
        cibles = []
        if isinstance(noeud, ast.Assign):
            cibles = noeud.targets
        elif isinstance(noeud, ast.AnnAssign):
            cibles = [noeud.target]
        else:
            continue
        valeur = noeud.value
        if not (isinstance(valeur, ast.Constant)
                and isinstance(valeur.value, str)):
            continue
        for cible in cibles:
            if isinstance(cible, ast.Name) and motif.match(cible.id):
                declarees[cible.id] = valeur.value
    return declarees


def _origines_importees(arbre: ast.Module, motif: re.Pattern = MOTIF_DE_SUITE
                        ) -> dict[str, tuple[str, str]]:
    """Nom local -> (module d'origine, nom d'origine), pour les suites importees.

    **L'alias est le piege que cette fonction existe pour fermer** :
    `atelier_pdf_parcours` importe `SUITE_DOSSIER` de DEUX modules, dont l'un
    sous le nom `MIRE_SUITE_DOSSIER`. Une mesure qui comparerait des noms
    locaux verrait une suite traitee deux fois et une autre jamais.
    """
    origines: dict[str, tuple[str, str]] = {}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.ImportFrom):
            continue
        module = (noeud.module or "").rsplit(".", 1)[-1]
        for alias in noeud.names:
            if motif.match(alias.name):
                origines[alias.asname or alias.name] = (module, alias.name)
    return origines


def _modules_importes(arbre: ast.Module, motif: re.Pattern = MOTIF_DE_SUITE
                      ) -> dict[str, str]:
    """Nom local -> nom du module, pour `from . import X` et `import a.b as c`."""
    modules: dict[str, str] = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            for alias in noeud.names:
                if not motif.match(alias.name):
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                court = alias.name.rsplit(".", 1)[-1]
                modules[alias.asname or court] = court
    return modules


def _corps_du_rappel(arbre: ast.Module, chemin: str) -> ast.AST:
    """Le noeud de fonction designe par `Classe.methode` ou `fonction`."""
    segments = chemin.split(".")
    courant: ast.AST = arbre
    for rang, segment in enumerate(segments):
        dernier = rang == len(segments) - 1
        attendus = ((ast.FunctionDef, ast.AsyncFunctionDef) if dernier
                    else (ast.ClassDef,))
        for enfant in getattr(courant, "body", []):
            if isinstance(enfant, attendus) and enfant.name == segment:
                courant = enfant
                break
        else:
            raise AssertionError(
                f"le rappel « {chemin} » n'existe pas : « {segment} » "
                f"est introuvable")
    return courant


def suites_nommees(arbre: ast.Module, chemin: str,
                   declarant_par_defaut: str,
                   motif: re.Pattern = MOTIF_DE_SUITE) -> set[tuple[str, str]]:
    """Les couples (module, nom de suite) **nommes dans le corps du rappel**.

    Un nom nu se resout d'abord par les imports du module, puis, a defaut, sur
    le module lui-meme : c'est le cas d'un rappel qui vit la ou les suites sont
    declarees. La forme pointee (`module.SUITE_X`) est resolue par les imports
    de module, et rendue telle quelle quand la base est inconnue -- une mesure
    qui laisse voir ce qu'elle n'a pas su resoudre vaut mieux qu'une mesure qui
    l'avale.
    """
    origines = _origines_importees(arbre, motif)
    modules = _modules_importes(arbre, motif)
    nommees: set[tuple[str, str]] = set()
    for noeud in ast.walk(_corps_du_rappel(arbre, chemin)):
        if isinstance(noeud, ast.Attribute) and motif.match(noeud.attr):
            base = noeud.value
            nom_de_base = base.id if isinstance(base, ast.Name) else ""
            nommees.add((modules.get(nom_de_base, nom_de_base), noeud.attr))
        elif isinstance(noeud, ast.Name) and (
                noeud.id in origines or motif.match(noeud.id)):
            # **Le nom local est teste AVANT le motif** : un alias peut ne
            # pas ressembler a une suite (`MIRE_SUITE_DOSSIER`), et le
            # rater ferait passer une suite non traitee pour traitee.
            nommees.add(origines.get(noeud.id,
                                     (declarant_par_defaut, noeud.id)))
    return nommees


def modules_declarants(racine: Path | None = None,
                       motif: re.Pattern = MOTIF_DE_SUITE
                       ) -> dict[str, dict[str, str]]:
    """Tous les modules d'un paquet qui declarent des suites, et leurs suites.

    Le balayage est **exhaustif** et ne consulte pas la table : c'est ce qui
    permet de confronter l'une a l'autre.

    **`racine` existe pour que le balayage lui-meme soit mesurable**, et ce
    n'est pas de la generalite gratuite : le mutant `M15` -- un
    `sorted(...)[:-1]`, c'est-a-dire un balayage tronque d'un fichier --
    **survivait** tant que cette fonction ne savait lire que `tui/`, ou le
    dernier module par ordre alphabetique ne declare aucune suite. C'est le
    quatrieme point de la regle des fabriques applique a la frontiere
    elle-meme : la cible au milieu demasque un aiguillage fautif, elle ne
    demasque pas un balayage tronque.
    """
    recensement: dict[str, dict[str, str]] = {}
    for chemin in sorted((racine or TUI).glob("*.py")):
        declarees = suites_declarees(
            ast.parse(chemin.read_text(encoding="utf-8"),
                      filename=str(chemin)), motif)
        if declarees:
            recensement[chemin.stem] = declarees
    return recensement


# ---------------------------------------------------------------------------
# La frontiere elle-meme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("couverture", COUVERTURES, ids=str)
def test_chaque_suite_declaree_porte_une_branche_nommee(couverture):
    """Aucune suite declaree ne tombe dans le filet **par oubli**.

    C'est `MQ-4` et `MQ-5` en une ligne : `SUITE_PDF` et `SUITE_EXPORTS`
    etaient declarees, offertes a l'ecran, et absentes de leur aiguillage.
    """
    declarees = suites_declarees(arbre_du_module(couverture.declarant))
    assert declarees, (
        f"« {couverture.declarant} » ne declare plus aucune suite : le "
        f"recensement n'observe rien, ce qui est le seul moyen pour cette "
        f"frontiere de passer sans mesurer")
    nommees = suites_nommees(arbre_du_module(couverture.rappelant),
                             couverture.rappel, couverture.rappelant)
    manquantes = sorted(nom for nom in declarees
                        if (couverture.declarant, nom) not in nommees)
    assert not manquantes, (
        f"{couverture} : {len(manquantes)} suite(s) declaree(s) sans branche "
        f"nommee -- {', '.join(manquantes)}. Une suite qui tombe dans le "
        f"filet « pas encore » alors que son atelier est livre est le defaut "
        f"que cette frontiere mesure ; si l'absence est reelle, la branche se "
        f"nomme quand meme, avec l'echeance qui la date.")


def test_aucun_module_declarant_n_echappe_a_la_table():
    """Un module neuf qui declare des suites **entre dans la table**.

    Sans ce test, la table prendrait du retard en silence : la frontiere
    ci-dessus ne mesure que ce qu'on lui a donne a mesurer.
    """
    recenses = set(modules_declarants())
    tabules = {couverture.declarant for couverture in COUVERTURES}
    assert recenses == tabules, (
        f"le recensement et la table divergent -- recenses et non tabules : "
        f"{sorted(recenses - tabules)} ; tabules et non recenses : "
        f"{sorted(tabules - recenses)}")


def test_le_recensement_voit_au_moins_ce_qui_existe():
    """Le **volet symetrique** : des cardinaux bornes par le bas, et mesures.

    Une frontiere qui ne reconnait plus rien passe en n'observant rien. Les
    bornes sont celles du 2026-09-06, **relevees** le meme jour par le lot des
    suites de la suppression : six modules declarants, sept rappels, dix-neuf
    suites, et jamais moins de deux suites par module -- un module a suite
    unique n'aurait de toute facon pas d'aiguillage a mesurer.

    **Les bornes se relevent avec la population**, sans quoi elles cessent de
    mesurer : laissees a cinq et quinze, elles seraient restees vertes le jour
    ou `projet_suppression` aurait perdu ses quatre suites.
    """
    recensement = modules_declarants()
    assert len(recensement) >= 6, recensement
    assert len(COUVERTURES) >= 7
    assert sum(len(suites) for suites in recensement.values()) >= 19
    for module, suites in recensement.items():
        assert len(suites) >= 2, f"« {module} » ne declare qu'une suite"
    for couverture in COUVERTURES:
        nommees = suites_nommees(arbre_du_module(couverture.rappelant),
                                 couverture.rappel, couverture.rappelant)
        assert len(nommees) >= 2, f"{couverture} ne nomme presque rien"


def test_le_recensement_voit_un_declarant_a_CHAQUE_BORD_du_balayage(tmp_path):
    """Un balayage tronque d'un fichier, en tete ou en queue, doit se voir.

    **Le mutant qui a impose ce test** : `sorted(...)[:-1]` dans
    :func:`modules_declarants`. Il survivait aux seize autres tests de ce
    fichier, parce que le dernier module de `tui/` par ordre alphabetique ne
    declare aucune suite -- la troncature ne retirait donc rien du
    recensement. Aucun test positif ne pouvait le voir : il ne manquait rien
    dans ce qui etait observe, c'est **ce qui n'etait plus observe** qui
    manquait.

    Quatre modules de synthese, trois declarants **distinguables** (six suites,
    six libelles differents), places en **tete**, au **milieu** et en
    **queue** de l'ordre alphabetique, plus un module sans suite pour que le
    recensement ait quelque chose a ecarter.
    """
    (tmp_path / "aaa_en_tete.py").write_text(
        'SUITE_UNE = "la premiere de tete"\nSUITE_DEUX = "la seconde de tete"\n',
        encoding="utf-8")
    (tmp_path / "mmm_au_milieu.py").write_text(
        'SUITE_TROIS = "la premiere du milieu"\n'
        'SUITE_QUATRE = "la seconde du milieu"\n', encoding="utf-8")
    (tmp_path / "nnn_sans_aucune_suite.py").write_text(
        'AUTRE_CHOSE = "rien a recenser ici"\n', encoding="utf-8")
    (tmp_path / "zzz_en_queue.py").write_text(
        'SUITE_CINQ = "la premiere de queue"\n'
        'SUITE_SIX = "la seconde de queue"\n', encoding="utf-8")

    recense = modules_declarants(tmp_path)

    assert set(recense) == {"aaa_en_tete", "mmm_au_milieu", "zzz_en_queue"}
    assert set(recense["aaa_en_tete"]) == {"SUITE_UNE", "SUITE_DEUX"}
    assert set(recense["zzz_en_queue"]) == {"SUITE_CINQ", "SUITE_SIX"}


def test_les_libelles_declares_sont_tous_distincts_dans_un_module():
    """Deux suites au meme libelle dans un module seraient indistinguables.

    L'aiguillage compare des chaines : deux constantes de meme valeur feraient
    de la seconde une branche morte que rien ne signale.
    """
    for module, suites in modules_declarants().items():
        libelles = list(suites.values())
        assert len(set(libelles)) == len(libelles), (
            f"« {module} » declare deux suites au meme libelle : {libelles}")


# ---------------------------------------------------------------------------
# Les bancs des outils de recensement -- la cible a CHAQUE rang
# ---------------------------------------------------------------------------

def _source_de_synthese(sans_branche: str) -> tuple[str, str]:
    """Un declarant et un rappelant de synthese, **trois suites distinctes**.

    Les trois libelles different -- « une », « deux », « trois » --, jamais un
    remplissage uniforme : une permutation d'aiguillage ne se verrait pas sur
    des valeurs egales. `sans_branche` designe celle que le rappel omet.
    """
    declarant = (
        'SUITE_TETE = "la premiere"\n'
        'SUITE_MILIEU = "la deuxieme"\n'
        'SUITE_QUEUE = "la troisieme"\n')
    branches = "".join(
        f"        if suite == {nom}:\n            return {rang}\n"
        for rang, nom in enumerate(("SUITE_TETE", "SUITE_MILIEU",
                                    "SUITE_QUEUE"))
        if nom != sans_branche)
    rappelant = (
        "from .declarant import SUITE_TETE, SUITE_MILIEU, SUITE_QUEUE\n\n\n"
        "class Parcours:\n"
        "    def suivre(self, suite):\n"
        f"{branches}"
        "        return None\n")
    return declarant, rappelant


@pytest.mark.parametrize("sans_branche",
                         ["SUITE_TETE", "SUITE_MILIEU", "SUITE_QUEUE"])
def test_l_outil_voit_la_suite_sans_branche_a_chaque_rang(sans_branche):
    """En **tete**, au **milieu** et en **queue** : les trois sont vues.

    Le milieu demasque un aiguillage fautif ; les deux bords demasquent un
    balayage tronque, qui est un autre mode de panne -- c'est le quatrieme
    point de la regle des fabriques, et celui que ce depot paie le plus
    souvent en mutants survivants.
    """
    source_declarant, source_rappelant = _source_de_synthese(sans_branche)
    declarees = suites_declarees(ast.parse(source_declarant))
    assert set(declarees) == {"SUITE_TETE", "SUITE_MILIEU", "SUITE_QUEUE"}
    nommees = suites_nommees(ast.parse(source_rappelant), "Parcours.suivre",
                             "rappelant")
    manquantes = {nom for nom in declarees
                  if ("declarant", nom) not in nommees}
    assert manquantes == {sans_branche}


def test_l_outil_resout_un_alias_d_import():
    """Un `import ... as ...` ne fait pas passer une suite pour une autre.

    C'est le regime reel d'`atelier_pdf_parcours`, qui importe deux
    `SUITE_DOSSIER` de deux modules dont l'un renomme.
    """
    source = (
        "from .un import SUITE_DOSSIER\n"
        "from .deux import SUITE_DOSSIER as AUTRE_SUITE_DOSSIER\n\n\n"
        "def suivre(suite):\n"
        "    if suite == AUTRE_SUITE_DOSSIER:\n"
        "        return 1\n"
        "    return None\n")
    nommees = suites_nommees(ast.parse(source), "suivre", "ici")
    assert ("deux", "SUITE_DOSSIER") in nommees
    assert ("un", "SUITE_DOSSIER") not in nommees


def test_l_outil_ne_compte_pas_une_suite_citee_dans_un_docstring():
    """Un docstring qui **explique** une suite n'est pas une branche.

    C'est ce qui distingue cette frontiere d'un grep, et le regime est reel :
    les docstrings de `suivre` nommaient `SUITE_PDF` et `SUITE_EXPORTS` pour
    dire qu'elles n'avaient pas d'atelier.
    """
    source = (
        "from .un import SUITE_A, SUITE_B\n\n\n"
        "def suivre(suite):\n"
        '    """Tout le reste -- SUITE_B, dont l\'atelier n\'existe pas."""\n'
        "    if suite == SUITE_A:\n"
        "        return 1\n"
        "    return None\n")
    nommees = suites_nommees(ast.parse(source), "suivre", "ici")
    assert ("un", "SUITE_A") in nommees
    assert ("un", "SUITE_B") not in nommees


def test_l_outil_ignore_une_constante_locale_a_une_fonction():
    """Une `SUITE_*` posee dans une fonction n'est pas une suite du produit."""
    source = ('SUITE_VRAIE = "au module"\n\n\n'
              "def fabriquer():\n"
              '    SUITE_FAUSSE = "dans la fonction"\n'
              "    return SUITE_FAUSSE\n")
    assert set(suites_declarees(ast.parse(source))) == {"SUITE_VRAIE"}


def test_l_outil_nomme_le_rappel_introuvable():
    """Un chemin de rappel perime **leve**, il ne rend pas un ensemble vide.

    Un ensemble vide ferait passer la frontiere : toute suite y serait
    « manquante », donc le test rougirait -- mais un rappel renomme doit dire
    qu'il est renomme, pas se deguiser en couverture manquante.
    """
    source = "def suivre(suite):\n    return None\n"
    with pytest.raises(AssertionError, match="n'existe pas"):
        suites_nommees(ast.parse(source), "Absent.suivre", "ici")
