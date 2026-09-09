# -*- coding: utf-8 -*-
"""La frontiere qui compte, pour chaque `ENTREE_*` d'un palier, sa branche nommee.

**Le mode de panne que ce banc ferme, et il a ete paye QUATRE fois dans cet
epic** : un composant livre, mesure, et cable nulle part -- `E9` (les paliers
reels montes par personne), `I3` (`bandeau_de_relink`), puis `MQ-4`/`MQ-5` (les
suites `Pdf` et `Exports`) la nuit du 2026-09-06. La quatrieme est `MQ-8`, et
c'est celle-ci : `EcranInventaireDuProjet` -- `E6-1`, story 11.11, 129 tests --
n'etait construit par **rien**, parce que les **trois** entrees du palier Projet
partaient vers `EcranPasEncore`, y compris celle que la maquette validee dessine
en tete.

**Le point commun des quatre, et c'est lui qu'on mesure** : une constante
declaree au module, offerte a l'operateur, et **absente de l'aiguillage qui la
traite**. Aucun banc ne rougissait, parce que le filet *fonctionne* -- il nomme
une absence, et son banc mesure qu'il la nomme. Ce qui manquait, c'est de quoi
distinguer une entree qui tombe dans le filet **par oubli** d'une entree qui n'a
legitimement pas encore de destination.

Pourquoi ce fichier n'est PAS `test_couverture_des_suites.py`
--------------------------------------------------------------
La question s'est posee exactement dans ces termes, et elle s'est tranchee par
la mesure plutot que par le gout. **Les outils, eux, ne sont pas dupliques** :
ce fichier les IMPORTE de la frontiere des suites, ou ils vivent, apres que le
lot du 2026-09-06 y a fait du motif un parametre -- un ajout pur, aucun renom,
aucune ligne deplacee.

Deux raisons de ne pas y avoir mis la frontiere elle-meme :

* **une mesure, faite avant d'ecrire** : `test_couverture_des_suites.py` est
  ROUGE sur cette branche, et il l'etait deja au commit dont ce lot est coupe
  (`51bb801c5`) -- `projet_suppression` y declare quatre suites et n'entre pas
  dans la table, faute d'avoir un rappel qui les traite. C'est un constat de la
  story 11.11, pas de ce lot-ci (entree portee a `deferred-work.md`). Y greffer
  cette frontiere-ci ferait dependre son verdict de la reparation d'un autre
  lot, c'est-a-dire la rendrait illisible tout de suite ;
* **une raison de forme, et elle tient seule** : le volet symetrique de la
  frontiere des suites (`test_aucun_module_declarant_n_echappe_a_la_table`) est
  une **egalite d'ensembles** sur la population des modules qui declarent des
  suites -- cinq. Celle des paliers en compte **un**. Une seule egalite
  melangeant les deux populations aurait un message d'echec qui ne dit plus
  laquelle a derive.

Ce que cette frontiere NE mesure PAS, dit plutot que tu
--------------------------------------------------------
Comme sa soeur, elle mesure qu'une branche est **nommee**, pas qu'elle mene
quelque part d'utile : `destinations = {ENTREE_X: filet}` la satisfait. C'est
voulu -- une entree dont l'ecran n'existe pas doit pouvoir etre declaree comme
telle, avec son echeance, et c'est exactement ce que
`ChaineReelle.QUAND_LA_PORTE_VERS_UN_FICHIER` fait pour les deux entrees qui
attendent leur ecran de designation de fichier. Ce que la branche fait est
mesure par `test_porte_de_l_inventaire.py`, qui exerce le clavier du produit et
confronte l'ecran d'arrivee. Les deux mesures sont complementaires : celle-ci
attrape l'oubli, celle-la attrape l'erreur.

Regle des fabriques (`CLAUDE.md`, les QUATRE points)
------------------------------------------------------
Les bancs des outils travaillent sur des sources de synthese portant **trois**
entrees aux libelles **distincts** (jamais un remplissage uniforme : une
permutation ne se verrait pas), et l'entree non traitee y est placee tour a
tour **en tete**, **au milieu** et **en queue** -- le milieu demasque un
aiguillage fautif, les deux bords demasquent un balayage tronque, qui est un
autre mode de panne. C'est le quatrieme point, et le lot `MQ-A` vient de le
payer sur sa propre frontiere.
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Les outils vivent dans la frontiere des suites : c'est la MEME mesure sur
# l'arbre syntaxique, au motif pres. On les importe plutot que de les recopier
# -- une seconde redaction perimerait en silence, ce que ce depot a deja paye.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_couverture_des_suites import (  # noqa: E402
    TUI, arbre_du_module, modules_declarants, suites_declarees, suites_nommees)

#: Ce qui fait d'un nom une entree de palier. Les entrees du depot sont des
#: majuscules prefixees, exactement comme les suites, et c'est **la** convention
#: que la table exploite.
MOTIF_D_ENTREE = re.compile(r"^ENTREE_[A-Z0-9_]+$")


@dataclass(frozen=True)
class CouvertureDEntrees:
    """Un aiguillage d'entrees, et le module de palier dont il vient.

    `declarant` et `rappelant` different toujours ici, et c'est structurel : un
    palier declare ses entrees et **ne sait pas** ou elles menent -- c'est la
    chaine du produit qui le sait, parce qu'elle seule tient l'application.
    """

    declarant: str
    rappelant: str
    #: Le chemin pointe de la fonction, `Classe.methode` ou `fonction`.
    rappel: str

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return f"{self.declarant} -> {self.rappelant}.{self.rappel}"


#: **La table des aiguillages d'entrees du produit.** Elle est confrontee au
#: recensement par :func:`test_aucun_palier_declarant_n_echappe_a_la_table` : un
#: palier qui declarerait des entrees sans figurer ici fait rougir, si bien que
#: la table ne peut pas prendre du retard en silence.
COUVERTURES: tuple[CouvertureDEntrees, ...] = (
    CouvertureDEntrees("palier_projet", "atelier_extraction_ecriture",
                       "ChaineReelle.entrer_commande"),
)


def entrees_declarees(arbre: ast.Module) -> dict[str, str]:
    """Les `ENTREE_*` declarees au module, et leur valeur."""
    return suites_declarees(arbre, MOTIF_D_ENTREE)


def entrees_nommees(arbre: ast.Module, chemin: str,
                    declarant_par_defaut: str) -> set[tuple[str, str]]:
    """Les couples (module, nom d'entree) nommes dans le corps du rappel."""
    return suites_nommees(arbre, chemin, declarant_par_defaut, MOTIF_D_ENTREE)


def paliers_declarants(racine: Path | None = None) -> dict[str, dict[str, str]]:
    """Tous les modules de `tui/` qui declarent des entrees, et leurs entrees."""
    return modules_declarants(racine, MOTIF_D_ENTREE)


# ---------------------------------------------------------------------------
# La frontiere elle-meme
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("couverture", COUVERTURES, ids=str)
def test_chaque_entree_declaree_porte_une_branche_nommee(couverture):
    """Aucune entree de palier ne tombe dans le filet **par oubli**.

    C'est `MQ-8` en une ligne : `ENTREE_MEDIAS` etait declaree, dessinee en
    tete de la maquette validee, offerte a l'operateur -- et absente de
    l'aiguillage, comme ses deux voisines.
    """
    declarees = entrees_declarees(arbre_du_module(couverture.declarant))
    assert declarees, (
        f"« {couverture.declarant} » ne declare plus aucune entree : le "
        f"recensement n'observe rien, ce qui est le seul moyen pour cette "
        f"frontiere de passer sans mesurer")
    nommees = entrees_nommees(arbre_du_module(couverture.rappelant),
                              couverture.rappel, couverture.rappelant)
    manquantes = sorted(nom for nom in declarees
                        if (couverture.declarant, nom) not in nommees)
    assert not manquantes, (
        f"{couverture} : {len(manquantes)} entree(s) declaree(s) sans branche "
        f"nommee -- {', '.join(manquantes)}. Une entree qui tombe dans le "
        f"filet « pas encore » alors que son ecran est livre est le defaut que "
        f"cette frontiere mesure ; si l'absence est reelle, la branche se "
        f"nomme quand meme, avec l'echeance qui la date.")


def test_aucun_palier_declarant_n_echappe_a_la_table():
    """Un palier neuf qui declare des entrees **entre dans la table**.

    Sans ce test, la table prendrait du retard en silence : la frontiere
    ci-dessus ne mesure que ce qu'on lui a donne a mesurer.
    """
    recenses = set(paliers_declarants())
    tabules = {couverture.declarant for couverture in COUVERTURES}
    assert recenses == tabules, (
        f"le recensement et la table divergent -- recenses et non tabules : "
        f"{sorted(recenses - tabules)} ; tabules et non recenses : "
        f"{sorted(tabules - recenses)}")


def test_le_recensement_voit_au_moins_ce_qui_existe():
    """Le **volet symetrique** : des cardinaux bornes par le bas, et mesures.

    Une frontiere qui ne reconnait plus rien passe en n'observant rien. Les
    bornes sont celles du 2026-09-06 : un palier declarant, un aiguillage,
    trois entrees -- et jamais moins de deux entrees par palier, un palier a
    entree unique n'ayant de toute facon pas d'aiguillage a mesurer.

    Le paquet balaye est bien celui du produit, et pas un dossier vide : la
    mesure porte sur `TUI`, dont on verifie qu'il porte plusieurs modules.
    """
    assert len(sorted(TUI.glob("*.py"))) >= 2, TUI
    recensement = paliers_declarants()
    assert len(recensement) >= 1, recensement
    assert len(COUVERTURES) >= 1
    assert sum(len(entrees) for entrees in recensement.values()) >= 3
    for palier, entrees in recensement.items():
        assert len(entrees) >= 2, f"« {palier} » ne declare qu'une entree"
    for couverture in COUVERTURES:
        nommees = entrees_nommees(arbre_du_module(couverture.rappelant),
                                  couverture.rappel, couverture.rappelant)
        assert len(nommees) >= 2, f"{couverture} ne nomme presque rien"


def test_le_recensement_voit_un_palier_a_CHAQUE_BORD_du_balayage(tmp_path):
    """Un balayage tronque d'un fichier, en tete ou en queue, doit se voir.

    **Le quatrieme point de la regle des fabriques**, applique a la frontiere
    elle-meme. Le lot `MQ-A` a paye exactement ce mutant sur sa soeur : un
    `sorted(...)[:-1]` survivait a seize tests, parce que le dernier module de
    `tui/` par ordre alphabetique ne declarait rien -- la troncature ne retirait
    donc rien du recensement, et aucun test positif ne pouvait le voir.

    Quatre modules de synthese, trois declarants **distinguables** (six entrees,
    six valeurs differentes), places en **tete**, au **milieu** et en **queue**
    de l'ordre alphabetique, plus un module sans entree pour que le recensement
    ait quelque chose a ecarter.
    """
    (tmp_path / "aaa_en_tete.py").write_text(
        'ENTREE_UNE = "premiere-de-tete"\nENTREE_DEUX = "seconde-de-tete"\n',
        encoding="utf-8")
    (tmp_path / "mmm_au_milieu.py").write_text(
        'ENTREE_TROIS = "premiere-du-milieu"\n'
        'ENTREE_QUATRE = "seconde-du-milieu"\n', encoding="utf-8")
    (tmp_path / "nnn_sans_aucune_entree.py").write_text(
        'AUTRE_CHOSE = "rien a recenser ici"\n', encoding="utf-8")
    (tmp_path / "zzz_en_queue.py").write_text(
        'ENTREE_CINQ = "premiere-de-queue"\n'
        'ENTREE_SIX = "seconde-de-queue"\n', encoding="utf-8")

    recense = paliers_declarants(tmp_path)

    assert set(recense) == {"aaa_en_tete", "mmm_au_milieu", "zzz_en_queue"}
    assert set(recense["aaa_en_tete"]) == {"ENTREE_UNE", "ENTREE_DEUX"}
    assert set(recense["zzz_en_queue"]) == {"ENTREE_CINQ", "ENTREE_SIX"}


def test_les_valeurs_declarees_sont_toutes_distinctes_dans_un_palier():
    """Deux entrees a la meme valeur seraient indistinguables.

    L'aiguillage compare des chaines -- `issue.cle` contre la cle de la table
    -- : deux constantes de meme valeur feraient de la seconde une branche
    morte que rien ne signale.
    """
    for palier, entrees in paliers_declarants().items():
        valeurs = list(entrees.values())
        assert len(set(valeurs)) == len(valeurs), (
            f"« {palier} » declare deux entrees a la meme valeur : {valeurs}")


# ---------------------------------------------------------------------------
# Les bancs des outils -- la cible a CHAQUE rang
# ---------------------------------------------------------------------------

def _source_de_synthese(sans_branche: str) -> tuple[str, str]:
    """Un palier et une chaine de synthese, **trois entrees distinctes**.

    Les trois valeurs different -- jamais un remplissage uniforme : une
    permutation d'aiguillage ne se verrait pas sur des valeurs egales.
    `sans_branche` designe l'entree que le rappel omet.
    """
    declarant = ('ENTREE_TETE = "la-premiere"\n'
                 'ENTREE_MILIEU = "la-deuxieme"\n'
                 'ENTREE_QUEUE = "la-troisieme"\n')
    branches = "".join(
        f"            {nom}: self.faire_{rang},\n"
        for rang, nom in enumerate(("ENTREE_TETE", "ENTREE_MILIEU",
                                    "ENTREE_QUEUE"))
        if nom != sans_branche)
    rappelant = (
        "from .declarant import ENTREE_TETE, ENTREE_MILIEU, ENTREE_QUEUE\n\n\n"
        "class Chaine:\n"
        "    def entrer_commande(self, issue):\n"
        "        destinations = {\n"
        f"{branches}"
        "        }\n"
        "        destinations.get(issue.cle, self.filet)(issue)\n")
    return declarant, rappelant


@pytest.mark.parametrize("sans_branche",
                         ["ENTREE_TETE", "ENTREE_MILIEU", "ENTREE_QUEUE"])
def test_l_outil_voit_l_entree_sans_branche_a_chaque_rang(sans_branche):
    """En **tete**, au **milieu** et en **queue** : les trois sont vues.

    Le milieu demasque un aiguillage fautif ; les deux bords demasquent un
    balayage tronque, qui est un autre mode de panne -- c'est le quatrieme
    point de la regle des fabriques, et celui que ce depot paie le plus souvent
    en mutants survivants.
    """
    source_declarant, source_rappelant = _source_de_synthese(sans_branche)
    declarees = entrees_declarees(ast.parse(source_declarant))
    assert set(declarees) == {"ENTREE_TETE", "ENTREE_MILIEU", "ENTREE_QUEUE"}
    nommees = entrees_nommees(ast.parse(source_rappelant),
                              "Chaine.entrer_commande", "rappelant")
    manquantes = {nom for nom in declarees
                  if ("declarant", nom) not in nommees}
    assert manquantes == {sans_branche}


def test_l_outil_ne_compte_pas_une_entree_citee_dans_un_DOCSTRING():
    """Un docstring qui **explique** une entree n'est pas une branche.

    C'est ce qui distingue cette frontiere d'un grep, et le regime est reel :
    le docstring d'`entrer_commande` nommait `ENTREE_MEDIAS` en prose bien
    avant que la porte soit posee.
    """
    source = (
        "from .palier import ENTREE_A, ENTREE_B\n\n\n"
        "def entrer_commande(issue):\n"
        '    """Tout le reste -- ENTREE_B, dont l\'ecran n\'existe pas."""\n'
        "    if issue.cle == ENTREE_A:\n"
        "        return 1\n"
        "    return None\n")
    nommees = entrees_nommees(ast.parse(source), "entrer_commande", "ici")
    assert ("palier", "ENTREE_A") in nommees
    assert ("palier", "ENTREE_B") not in nommees


def test_l_outil_resout_la_forme_POINTEE_qui_est_celle_du_produit():
    """`palier_projet.ENTREE_MEDIAS` -- le module est importe, pas les noms.

    C'est le regime reel de `ChaineReelle.entrer_commande`, dont l'import de
    `palier_projet` est **local** : ce module tire `gui.depot_projets`, et le
    garder hors du chargement laisse `--diagnostic-chemin` repondre sur un
    environnement partiel. Une mesure qui ne saurait lire que la forme nue
    verrait zero entree nommee et rougirait sur un produit correct.
    """
    source = ("def entrer_commande(issue):\n"
              "    from . import palier_projet\n"
              "    if issue.cle == palier_projet.ENTREE_MEDIAS:\n"
              "        return 1\n"
              "    return None\n")
    nommees = entrees_nommees(ast.parse(source), "entrer_commande", "ici")
    assert ("palier_projet", "ENTREE_MEDIAS") in nommees


def test_l_outil_ignore_une_constante_locale_a_une_fonction():
    """Une `ENTREE_*` posee dans une fonction n'est pas une entree du produit."""
    source = ('ENTREE_VRAIE = "au module"\n\n\n'
              "def fabriquer():\n"
              '    ENTREE_FAUSSE = "dans la fonction"\n'
              "    return ENTREE_FAUSSE\n")
    assert set(entrees_declarees(ast.parse(source))) == {"ENTREE_VRAIE"}


def test_l_outil_nomme_le_rappel_introuvable():
    """Un chemin de rappel perime **leve**, il ne rend pas un ensemble vide.

    Un ensemble vide ferait passer la frontiere dans le mauvais sens : toute
    entree y serait « manquante », donc le test rougirait -- mais un rappel
    renomme doit dire qu'il est renomme, pas se deguiser en couverture
    manquante.
    """
    source = "def entrer_commande(issue):\n    return None\n"
    with pytest.raises(AssertionError, match="n'existe pas"):
        entrees_nommees(ast.parse(source), "Absent.entrer_commande", "ici")
