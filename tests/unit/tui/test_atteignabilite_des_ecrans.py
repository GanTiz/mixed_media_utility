# -*- coding: utf-8 -*-
"""La frontiere qui compte, pour chaque ecran du paquet, un CHEMIN qui y mene.

**Le mode de panne que ce banc ferme, et le depot l'a paye TROIS fois en
quelques jours** -- trois fois le meme fait, jamais le meme symptome :

* `MQ-4` et `MQ-5` (2026-09-06) : deux ateliers **livres** qu'aucun chainage
  n'atteignait, le filet `EcranPasEncore` etant reste en place apres la
  livraison de sa destination ;
* `MQ-8`, la porte de l'inventaire (`E6-1`, story 11.11) : classe livree,
  exportee, mesuree par 129 tests, et `git grep` rendait **trois** occurrences
  dont les trois vivaient dans son propre module. **Zero appelant.** La porte a
  du etre cablee dans un lot separe ;
* `projet_suppression` (2026-09-06 au matin) : quatre suites declarees, deux
  ecrans qui les portent, et **aucun `sur_suite`** -- « Reessayer » et « Ouvrir
  le dossier » menaient au filet.

Le point commun est le sujet de ce fichier : dans les trois cas le composant
existait, ses tests passaient, et **rien ne mesurait qu'on puisse y ARRIVER**.
La docstring de :func:`chaine_du_produit` le dit deja mot pour mot -- « un
composant livre, teste, et cable nulle part dans l'application est un composant
que le produit n'a pas » -- et le produit l'a quand meme paye trois fois. Une
phrase ne se mesure pas ; une frontiere, si.

Ce que cette frontiere mesure, en trois volets
----------------------------------------------
1. **le recensement**, lu sur l'ARBRE SYNTAXIQUE et jamais par grep. Une
   docstring qui cite `EcranPasEncore` pour dire qu'un ecran n'existe pas
   **porte le mot**, et un grep y mordrait -- c'est litteralement le texte qui
   a masque `MQ-4` et `MQ-5`. Un ecran est une classe qui derive,
   transitivement et a travers les modules, de :class:`coque.Palier` ;
2. **la confrontation** : chaque classe recensee est soit **atteinte** depuis
   :func:`chaine_du_produit` par un chemin de references reelles, soit inscrite
   au :data:`REGISTRE` avec son **motif ecrit**. Le registre est confronte au
   recensement **dans les deux sens** -- une classe ni atteinte ni inscrite
   fait rougir, et une entree de registre qui ne correspond plus a aucune
   classe **ou qui designe une classe desormais atteinte** fait rougir aussi :
   une entree perimee masquerait le manque suivant ;
3. **les montees reelles**, sans lesquelles les deux premiers volets ne
   mesureraient qu'un graphe. `test_couverture_des_suites.py` avertit
   d'elle-meme qu'elle « mesure qu'une branche est NOMMEE, pas qu'elle mene
   quelque part d'utile » ; le meme reproche vaut ici, et
   :data:`MONTEES_REELLES` y repond en **montant l'application du produit** et
   en confrontant le **type** de l'ecran d'arrivee, touche par touche, comme le
   fait `test_porte_de_l_inventaire.py`. Les dix montees servent en outre de
   **calibration du graphe** : le volet statique doit declarer atteignable
   chacune des classes que le clavier atteint pour de vrai.

Le volet qui empeche la mesure de se vider
------------------------------------------
Une frontiere de recensement est exactement le genre de banc qui **passe en
n'observant rien** : un recensement qui cesserait de reconnaitre une classe
d'ecran verrait zero ecran, donc zero manque. Les cardinaux sont donc bornes
par le bas (:func:`test_le_recensement_voit_au_moins_ce_qui_existe`), et le
recensement lui-meme est mesure sur des sources de synthese ou la cible est
posee **en tete, au milieu et en queue** du balayage.

Regle des fabriques (`CLAUDE.md`, les QUATRE points)
----------------------------------------------------
Les fabriques de ce banc produisent des **collections d'ecrans**, donc la regle
mord fort. Les paquets de synthese portent **quatre modules** et **au moins
trois classes d'ecran DISTINGUABLES** -- des noms et des bases differents,
jamais un remplissage uniforme : une permutation ne se verrait pas sur des
elements egaux. La cible -- la classe orpheline, le module tronque -- est posee
tour a tour **en tete**, **au milieu** et **en queue** de l'ordre alphabetique
du balayage : le milieu demasque un aiguillage fautif, les deux bords
demasquent un balayage tronque, qui est un **autre** mode de panne. Cote
produit, les cinq entrees du menu des ateliers sont montees **toutes les
cinq**, la premiere et la derniere comprises.

Ce que la campagne de mutation a change ici (2026-09-06)
--------------------------------------------------------
**45 mutants injectes, 43 tues.** Deux tolerances, nommees plus bas. Ce qui
compte n'est pas le compte : ce sont les deux defauts que les survivants du
premier tour ont revele, et qu'aucune relecture n'aurait montres.

* **un invariant ecrit a DEUX endroits n'est tenu nulle part.** L'arc
  d'heritage etait pose une fois dans :func:`construire_le_graphe` et une
  fois dans :func:`_arcs_d_un_sommet` ; retirer l'un des deux ne faisait
  rougir personne (`M17`). Un seul lieu desormais, et
  :func:`test_HERITER_c_est_ATTEINDRE` dessus -- reinjecte a ce lieu unique
  (`M17b`), le mutant meurt ;
* **une confrontation ecrite EN LIGNE dans son test n'est exercee que sur
  l'etat reel du depot.** Ici la liste des orphelins est **vide**, donc une
  troncature d'un bord y etait un non-evenement : `M22`, `M23` et `M24`
  survivaient tous les trois, et le defaut ne se serait reveille que le jour
  ou un orphelin serait apparu -- c'est-a-dire le jour ou la frontiere devait
  servir. Les trois confrontations sont sorties en fonctions **pures**
  (:func:`orphelins`, :func:`entrees_fantomes`, :func:`entrees_perimees`) et
  mesurees sur des donnees de synthese, la cible a chaque rang. Les six
  mutants reinjectes meurent.

Deux mutants portaient du **code mort**, retire plutot que couvert : une
boucle de `discard` d'imports locaux (`M12`) et la seconde ecriture de l'arc
d'heritage (`M17`). Un mutant qu'on ne peut pas tuer parce que le code ne sert
a rien se ferme en retirant le code.

**Les assertions du volet clavier sont PORTANTES, et c'est mesure par le
PRODUIT et non par le banc.** Muter une assertion d'un test ne peut jamais
faire rougir ce test : la question utile est « quelle regression du produit la
fait tomber ? ». Reponses mesurees le 2026-09-06 :

===============================================  ==========================
assertion                                        la regression qui la leve
===============================================  ==========================
le filet `EcranPasEncore` est refuse (`M30`)     `P04` : `ENTREE_MEDIAS`
le type d'arrivee est confronte (`M31`)          retombe dans le filet
`DEPART` est relie au binaire (`M28`)            `P06` : `__main__` remonte
                                                 `CoqueTui()` nu -- `E9`
les cinq entrees sont toutes montees (`M32`)     `P07` : un sixieme atelier
                                                 declare sans porte
la calibration graphe/clavier (`M29`)            `M15` : la forme pointee
                                                 ignoree dans le graphe
===============================================  ==========================

**Les deux tolerances, dites plutot que tues.** `M21` est un temoin volontaire
-- une reecriture equivalente du registre, injectee pour verifier que la
campagne ne rend pas de faux positifs. `M27` deplace `DEPART` de
:func:`chaine_du_produit` a :func:`construire_l_application` : les deux ont
**le meme ensemble d'ecrans atteignables**, et ce n'est pas une supposition --
:func:`test_le_DEPART_est_celui_que_LE_BINAIRE_emprunte` l'etablit par une
egalite. Un mutant equivalent par une propriete mesuree n'est pas un trou.

Ce que cette frontiere NE mesure PAS, dit plutot que tu
-------------------------------------------------------
Voir :func:`test_ce_que_cette_frontiere_ne_mesure_pas` -- la liste y est
executable plutot que declarative, pour qu'elle perime bruyamment.
"""
from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

#: La racine du paquet mesure. Deduite du fichier, jamais ecrite en dur.
TUI = _RACINE / "src" / "mixed_media_utility" / "tui"

#: La racine de l'arbre d'heritage des ecrans. `coque.Palier` derive du
#: `Screen` de `textual` et **c'est la seule** : mesure par
#: :func:`test_le_paquet_n_a_qu_UNE_racine_d_ecran`, faute de quoi une famille
#: d'ecrans posee sur une autre base echapperait au recensement en silence.
RACINE_DES_ECRANS = ("coque", "Palier")

#: Le point d'entree du PRODUIT, et pas un autre. `construire_l_application`
#: passe par lui ; `ChaineReelle(...)` nu est la version degradee que seuls les
#: bancs montent, et c'est cette assemblee manuelle qui a masque le lot `E9`.
DEPART = ("atelier_extraction_ecriture", "chaine_du_produit")


# ---------------------------------------------------------------------------
# Le recensement et le graphe -- ARBRE SYNTAXIQUE, jamais du texte
# ---------------------------------------------------------------------------

def arbres_du_paquet(racine: Path) -> dict[str, ast.Module]:
    """Chaque module d'un paquet, parse. Le balayage est **exhaustif**."""
    return {chemin.stem: ast.parse(chemin.read_text(encoding="utf-8"),
                                   filename=str(chemin))
            for chemin in sorted(racine.glob("*.py"))}


def portee_du_module(arbre: ast.Module) -> tuple[dict[str, tuple[str, str]],
                                                 dict[str, str]]:
    """Deux tables : nom local -> (module, nom), et nom local -> module.

    Les imports **locaux a une fonction** sont inclus deliberement : c'est la
    forme qu'emploie :func:`chaine_du_produit` pour injecter les quatre
    ouvertures d'atelier, et les ignorer reviendrait a ne pas voir le seul
    endroit ou le produit se cable.
    """
    symboles: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            origine = (noeud.module or "").rsplit(".", 1)[-1]
            for alias in noeud.names:
                if noeud.level and not noeud.module:
                    # `from . import machin` : c'est un MODULE, pas un symbole.
                    modules[alias.asname or alias.name] = alias.name
                else:
                    symboles[alias.asname or alias.name] = (origine, alias.name)
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                court = alias.name.rsplit(".", 1)[-1]
                modules[alias.asname or court] = court
    return symboles, modules


def liaisons_locales(fonction) -> set[str]:
    """Les noms **lies dans la portee** d'une fonction, donc masquants.

    **Le faux arc que cette fonction existe pour fermer, et il etait reel** :
    `ChaineReelle.__init__` prend un parametre `ouvrir_les_cadences` et ecrit
    `self._ouvrir_les_cadences = ouvrir_les_cadences`. Le module declare par
    ailleurs une fonction du **meme nom**. Sans portee, le graphe croyait donc
    que la classe appelait la fonction du module -- c'est-a-dire qu'il tenait
    l'injection pour faite alors qu'elle vient d'ailleurs. Mesure : retirer
    `ouvrir_les_cadences=` de :func:`chaine_du_produit` laissait **zero** ecran
    orphelin ; avec la portee, il en laisse **neuf**. Un graphe trop genereux
    est pire qu'un graphe absent : il rassure.

    Un import local, lui, **lie sans masquer** : il resout le nom vers son
    module d'origine, et c'est le cablage reel du produit -- c'est la forme
    qu'emploie :func:`chaine_du_produit` pour ses quatre ateliers. Aucune
    ligne n'est necessaire pour l'obtenir : un alias d'import n'est ni une
    affectation ni un parametre, donc il n'entre jamais dans `liees`. Une
    boucle de `discard` a existe ici « au cas ou » ; la campagne du 2026-09-06
    l'a mesuree morte (`M12` : la retirer ne changeait rien) et elle est
    partie. Le comportement, lui, reste mesure par
    :func:`test_le_graphe_SUIT_un_import_local`.
    """
    liees: set[str] = set()
    args = fonction.args
    for argument in (list(args.posonlyargs) + list(args.args)
                     + list(args.kwonlyargs) + [args.vararg, args.kwarg]):
        if argument is not None:
            liees.add(argument.arg)
    for noeud in ast.walk(fonction):
        if isinstance(noeud, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            cibles = (noeud.targets if isinstance(noeud, ast.Assign)
                      else [noeud.target])
            for cible in cibles:
                liees |= {n.id for n in ast.walk(cible)
                          if isinstance(n, ast.Name)}
        elif isinstance(noeud, (ast.For, ast.AsyncFor, ast.comprehension)):
            liees |= {n.id for n in ast.walk(noeud.target)
                      if isinstance(n, ast.Name)}
        elif isinstance(noeud, ast.withitem) and noeud.optional_vars is not None:
            liees |= {n.id for n in ast.walk(noeud.optional_vars)
                      if isinstance(n, ast.Name)}
        elif isinstance(noeud, ast.ExceptHandler) and noeud.name:
            liees.add(noeud.name)
        elif (isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)) and noeud is not fonction):
            liees.add(noeud.name)
    return liees


@dataclass(frozen=True)
class Graphe:
    """Les sommets d'un paquet, leurs arcs de reference, et leurs bases.

    Un **sommet** est une definition de premier niveau -- fonction ou classe --
    designee par `(module, nom)`. Un **arc** de A vers B dit que le corps de A
    nomme B : c'est ce que « atteindre » veut dire ici, et la limite est dite
    en toutes lettres dans :func:`test_ce_que_cette_frontiere_ne_mesure_pas`.
    """

    sommets: dict[tuple[str, str], ast.AST]
    arcs: dict[tuple[str, str], frozenset]
    bases: dict[tuple[str, str], tuple]

    def descendants(self, racine: tuple[str, str]) -> set[tuple[str, str]]:
        """La fermeture transitive de l'heritage sous `racine`, racine incluse.

        Transitive **et a travers les modules** : `EcranCollisionDuScan` derive
        d'`EcranCollisionDeProfil`, qui derive d'`EcranDeJugement`, qui derive
        de `Palier`. Une mesure a un seul niveau en raterait les deux tiers.
        """
        famille = {racine}
        change = True
        while change:
            change = False
            for classe, bases in self.bases.items():
                if classe not in famille and famille.intersection(bases):
                    famille.add(classe)
                    change = True
        return famille

    def atteignables(self, depart: tuple[str, str]) -> set[tuple[str, str]]:
        """Tout ce que `depart` nomme, transitivement. Depart inclus."""
        assert depart in self.sommets, (
            f"le point de depart « {depart} » n'existe pas : un depart "
            f"introuvable rendrait un ensemble vide, donc TOUS les ecrans "
            f"manquants -- une frontiere doit dire qu'elle a perdu son depart, "
            f"pas se deguiser en avalanche de manques")
        vus, pile = {depart}, [depart]
        while pile:
            for voisin in self.arcs.get(pile.pop(), ()):
                if voisin not in vus:
                    vus.add(voisin)
                    pile.append(voisin)
        return vus


def _references(module: str, noeud, arbres, sommets,
                masques: frozenset = frozenset()) -> set[tuple[str, str]]:
    """Les sommets du paquet **nommes** dans un noeud, portee respectee."""
    symboles, modules = portee_du_module(arbres[module])
    trouves: set[tuple[str, str]] = set()
    for interne in ast.walk(noeud):
        if isinstance(interne, ast.Name):
            if interne.id in masques:
                continue
            cible = symboles.get(interne.id, (module, interne.id))
        elif (isinstance(interne, ast.Attribute)
              and isinstance(interne.value, ast.Name)):
            base = interne.value.id
            cible = (modules.get(base, base), interne.attr)
        else:
            continue
        if cible in sommets:
            trouves.add(cible)
    return trouves


def _arcs_d_un_sommet(module: str, noeud, arbres, sommets) -> set:
    """Les arcs sortants d'une definition de premier niveau.

    Une **classe** est traitee methode par methode : chacune a sa propre
    portee, et une seule portee pour toute la classe ferait masquer par un
    parametre d'une methode le nom qu'une autre methode emploie librement.
    """
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _references(module, noeud, arbres, sommets,
                           frozenset(liaisons_locales(noeud)))
    arcs: set = set()
    methodes = [enfant for enfant in ast.walk(noeud)
                if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for methode in methodes:
        arcs |= _references(module, methode, arbres, sommets,
                            frozenset(liaisons_locales(methode)))
    # Le corps de classe HORS methodes -- attributs, decorateurs, **bases** --
    # est lu dans la portee du module : rien n'y masque.
    #
    # **Les bases passent par ICI et par nulle part ailleurs.** Elles y etaient
    # doublees d'un `sortants |= set(resolues)` dans `construire_le_graphe`, et
    # la campagne du 2026-09-06 a mesure ce que coute un invariant ecrit a deux
    # endroits : le mutant `M17`, qui retirait la seconde ecriture, SURVIVAIT a
    # toute la frontiere -- la premiere le rattrapait. Une regle qu'on peut
    # mutiler sans que rien ne rougisse n'est pas tenue, elle est seulement ecrite
    # deux fois. Un seul lieu, donc, et une mesure dessus :
    # `test_HERITER_c_est_ATTEINDRE`.
    hors_methodes = ast.Module(
        body=[enfant for enfant in noeud.body
              if not isinstance(enfant, (ast.FunctionDef,
                                         ast.AsyncFunctionDef))]
             + [ast.Expr(value=base) for base in noeud.bases]
             + [ast.Expr(value=decor) for decor in noeud.decorator_list],
        type_ignores=[])
    ast.fix_missing_locations(hors_methodes)
    return arcs | _references(module, hors_methodes, arbres, sommets)


def construire_le_graphe(racine: Path) -> Graphe:
    """Le graphe complet d'un paquet. Il ne consulte aucune table."""
    arbres = arbres_du_paquet(racine)
    sommets: dict[tuple[str, str], ast.AST] = {}
    for module, arbre in arbres.items():
        for noeud in arbre.body:
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                sommets[(module, noeud.name)] = noeud

    arcs: dict[tuple[str, str], frozenset] = {}
    bases: dict[tuple[str, str], tuple] = {}
    for (module, nom), noeud in sommets.items():
        sortants = _arcs_d_un_sommet(module, noeud, arbres, sommets)
        if isinstance(noeud, ast.ClassDef):
            symboles, modules = portee_du_module(arbres[module])
            resolues = []
            for base in noeud.bases:
                if isinstance(base, ast.Name):
                    cible = symboles.get(base.id, (module, base.id))
                elif (isinstance(base, ast.Attribute)
                      and isinstance(base.value, ast.Name)):
                    cible = (modules.get(base.value.id, base.value.id),
                             base.attr)
                else:
                    continue
                if cible in sommets:
                    resolues.append(cible)
            bases[(module, nom)] = tuple(resolues)
        arcs[(module, nom)] = frozenset(sortants)
    return Graphe(sommets=sommets, arcs=arcs, bases=bases)


@lru_cache(maxsize=None)
def graphe_du_produit() -> Graphe:
    """Le graphe du paquet `tui/` reel, calcule une fois pour tout le banc."""
    return construire_le_graphe(TUI)


def classes_d_ecran(racine: Path | None = None,
                    racine_des_ecrans: tuple[str, str] = RACINE_DES_ECRANS
                    ) -> set[tuple[str, str]]:
    """Toutes les classes d'ecran d'un paquet, la racine **exclue**.

    `racine` existe pour que le balayage soit lui-meme mesurable, et ce n'est
    pas de la generalite gratuite : c'est le seul moyen de poser une classe
    orpheline en **tete** et en **queue** de l'ordre alphabetique des fichiers,
    donc d'attraper un balayage tronque d'un bord.
    """
    graphe = (graphe_du_produit() if racine is None
              else construire_le_graphe(racine))
    return graphe.descendants(racine_des_ecrans) - {racine_des_ecrans}


# ---------------------------------------------------------------------------
# Le REGISTRE -- une classe qu'aucun chemin n'atteint, et son MOTIF
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HorsChaine:
    """Une classe d'ecran qu'aucun chemin n'atteint, et **pourquoi**.

    Le motif est du texte parce qu'il s'adresse a un humain ; il est
    **obligatoire et non vide**, mesure comme tel. Une entree sans motif serait
    une derogation muette, c'est-a-dire exactement le filet `EcranPasEncore`
    laisse en place que `MQ-4` a paye.
    """

    module: str
    classe: str
    motif: str

    @property
    def cle(self) -> tuple[str, str]:
        return (self.module, self.classe)

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return f"{self.module}.{self.classe}"


# ---------------------------------------------------------------------------
# La confrontation, en trois fonctions PURES
# ---------------------------------------------------------------------------
# Elles ne lisent ni le disque ni le paquet : elles prennent trois ensembles et
# rendent une liste. **C'est ce qui les rend mesurables sur des donnees de
# synthese**, donc ce qui permet de poser la cible en tete, au milieu et en
# queue -- le quatrieme point de la regle des fabriques. Ecrites en ligne dans
# les tests de frontiere, elles n'etaient exercees que sur l'etat REEL du
# depot, ou l'ensemble des orphelins est vide : une troncature d'un bord y
# etait un non-evenement, et trois mutants y survivaient (campagne du
# 2026-09-06, `M22`, `M23`, `M24`).


def orphelins(ecrans, atteints, registre) -> list:
    """Les ecrans que rien n'atteint et **qu'aucun motif n'excuse**."""
    inscrits = {entree.cle for entree in registre}
    return sorted(ecrans - set(atteints) - inscrits)


def entrees_fantomes(ecrans, registre) -> list:
    """Les entrees de registre qui ne designent plus aucune classe d'ecran.

    Une derogation perimee **excuse d'avance le manque suivant** : le jour ou
    une classe reprend ce nom sans etre cablee, l'entree la couvre en silence.
    """
    return sorted(entree.cle for entree in registre if entree.cle not in ecrans)


def entrees_perimees(atteints, registre) -> list:
    """Les entrees de registre dont la classe est **desormais atteinte**.

    C'est le filet « pas encore » laisse en place apres la livraison de sa
    destination -- `MQ-4` et `MQ-5` mot pour mot, transpose au registre.
    """
    atteints = set(atteints)
    return sorted(entree.cle for entree in registre if entree.cle in atteints)


#: **Le registre des ecrans hors chaine.** Confronte au recensement dans les
#: DEUX sens par :func:`test_le_registre_et_le_recensement_se_confrontent`.
#:
#: **VIDE depuis le 2026-09-06**, et c'est le volet « aucune entree perimee »
#: qui l'a exige plutot qu'une relecture. Sa seule ligne etait
#: `EcranSuppressionEnCours` (`E6-2c`), differee parce que le lot
#: « suites-de-la-suppression » ecrivait alors le meme module -- il a atterri
#: (`56ac0078`), et `suite_de_la_suppression` monte desormais l'ecran. La
#: condition que l'entree posait elle-meme (« se retire quand le lot
#: atterrit ») est donc tenue.
REGISTRE: tuple[HorsChaine, ...] = ()


# ---------------------------------------------------------------------------
# La frontiere -- volets 1 et 2
# ---------------------------------------------------------------------------

def test_le_paquet_n_a_qu_UNE_racine_d_ecran():
    """`coque.Palier` est la seule base d'ecran, et c'est mesure.

    Sans ce test, une famille posee demain sur `ModalScreen` ou sur `Screen`
    directement echapperait au recensement **sans que rien ne rougisse** : le
    recensement ne verrait pas ces classes, donc ne les compterait pas
    manquantes. C'est le mode de panne d'une frontiere qui n'observe pas.
    """
    lignes = [ligne for chemin in sorted(TUI.glob("*.py"))
              for ligne in ast.parse(chemin.read_text(encoding="utf-8")).body
              if isinstance(ligne, ast.ClassDef)]
    depuis_textual = []
    for classe in lignes:
        for base in classe.bases:
            nom = (base.id if isinstance(base, ast.Name)
                   else getattr(base, "attr", ""))
            if nom in ("Screen", "ModalScreen"):
                depuis_textual.append(classe.name)
    assert depuis_textual == ["Palier"], (
        f"une base d'ecran autre que `Palier` est apparue : {depuis_textual}. "
        f"Le recensement de cette frontiere part de `Palier` et ne verrait "
        f"pas cette famille -- il ne la compterait donc pas manquante.")


def test_chaque_ECRAN_est_atteint_ou_INSCRIT_avec_son_motif():
    """Le coeur de la frontiere : aucun ecran orphelin **en silence**.

    C'est `MQ-8` en une ligne, et `MQ-4`/`MQ-5` par le meme fait :
    `EcranInventaireDuProjet` etait livre, exporte, mesure, et aucun chemin ne
    partait de :func:`chaine_du_produit` pour l'atteindre. La mesure porte sur
    le **graphe des references reelles**, jamais sur la presence d'un mot.
    """
    graphe = graphe_du_produit()
    ecrans = classes_d_ecran()
    assert ecrans, (
        "le recensement ne voit plus AUCUN ecran : c'est le seul moyen pour "
        "cette frontiere de passer sans rien mesurer")
    atteints = graphe.atteignables(DEPART)
    sans_porte = orphelins(ecrans, atteints, REGISTRE)
    assert not sans_porte, (
        f"{len(sans_porte)} ecran(s) qu'aucun chemin ne relie a "
        f"« {DEPART[0]}.{DEPART[1]} » et qu'aucun motif n'excuse : "
        f"{', '.join(f'{m}.{c}' for m, c in sans_porte)}. Un composant livre, "
        f"teste, et cable nulle part est un composant que le produit n'a pas "
        f"-- soit on pose la porte, soit on l'inscrit au REGISTRE avec son "
        f"motif ecrit.")


def test_le_registre_et_le_recensement_se_confrontent():
    """Le volet **symetrique**, et il n'est pas decoratif.

    Une entree de registre qui ne correspond plus a aucune classe -- classe
    renommee, module fusionne -- **masquerait le manque suivant** : le jour ou
    une classe reprend ce nom sans etre cablee, l'entree perimee l'excuserait
    d'avance. Et une entree qui designe une classe desormais **atteinte** ment
    sur l'etat du produit : son motif dit « pas cable » alors qu'un chemin
    existe, ce qui est exactement le filet laisse en place de `MQ-4`.
    """
    graphe = graphe_du_produit()
    ecrans = classes_d_ecran()
    atteints = graphe.atteignables(DEPART)

    fantomes = entrees_fantomes(ecrans, REGISTRE)
    assert not fantomes, (
        f"entree(s) de registre sans classe d'ecran correspondante : "
        f"{fantomes}. Une derogation perimee excuse d'avance le manque suivant.")

    perimees = entrees_perimees(atteints, REGISTRE)
    assert not perimees, (
        f"entree(s) de registre dont la classe est desormais ATTEINTE : "
        f"{perimees}. La porte est posee, le motif ne tient plus : l'entree "
        f"se retire, comme un filet « pas encore » se retire quand sa "
        f"destination est livree.")

    for entree in REGISTRE:
        assert entree.motif.strip(), f"{entree} est inscrite SANS motif"
        assert len(entree.motif) >= 40, (
            f"{entree} porte un motif trop court pour dire quoi que ce soit "
            f"d'utile : « {entree.motif} »")

    cles = [entree.cle for entree in REGISTRE]
    assert len(set(cles)) == len(cles), (
        f"le registre inscrit deux fois la meme classe : {cles}")


def test_le_recensement_voit_au_moins_ce_qui_existe():
    """Le volet qui empeche la mesure de se vider, par des cardinaux mesures.

    Une frontiere de recensement qui cesserait de reconnaitre quoi que ce soit
    passerait **en n'observant rien** -- c'est ce que ce depot appelle une
    assertion tautologique. Les bornes sont celles du 2026-09-06 : 70 classes
    d'ecran sur 21 modules, un graphe de plus de 400 sommets, et au plus une
    poignee d'entrees au registre.
    """
    graphe = graphe_du_produit()
    ecrans = classes_d_ecran()
    assert len(ecrans) >= 65, len(ecrans)
    assert len({module for module, _ in ecrans}) >= 20, sorted(ecrans)
    assert len(graphe.sommets) >= 400, len(graphe.sommets)
    assert sum(len(a) for a in graphe.arcs.values()) >= 800
    atteints = ecrans & graphe.atteignables(DEPART)
    assert len(atteints) >= 65, sorted(ecrans - atteints)
    # Un registre qui enflerait cesserait d'etre une exception : il deviendrait
    # la mesure. Cinq est large -- il en porte UNE au 2026-09-06.
    assert len(REGISTRE) <= 5, [str(e) for e in REGISTRE]


def test_le_DEPART_est_celui_que_LE_BINAIRE_emprunte():
    """`DEPART` n'est pas un choix de banc : `mmu-tui` y passe, et c'est mesure.

    Le point d'entree reel est `__main__.main`, qui appelle
    :func:`construire_l_application`, qui appelle :func:`chaine_du_produit`.
    L'egalite ci-dessous **etablit** que partir de l'un ou de l'autre revient
    au meme, au lieu de le supposer -- et elle rougirait le jour ou `__main__`
    atteindrait une famille d'ecrans que :func:`chaine_du_produit` n'atteint
    pas, c'est-a-dire le jour ou la frontiere cesserait de mesurer le produit.

    Sans ce test, `DEPART` serait une constante que rien ne relie au binaire.
    C'est litteralement la panne du lot `E9` : « la recette passait par la
    demo, jamais par le point d'entree du produit ».
    """
    graphe = graphe_du_produit()
    ecrans = classes_d_ecran()
    depuis_le_binaire = graphe.atteignables(("__main__", "main"))
    assert DEPART in depuis_le_binaire, (
        f"« {DEPART[0]}.{DEPART[1]} » n'est plus sur le chemin de `mmu-tui` : "
        f"cette frontiere mesure un point d'entree que le produit n'emprunte "
        f"pas")
    ecart = sorted((ecrans & depuis_le_binaire)
                   - (ecrans & graphe.atteignables(DEPART)))
    assert not ecart, (
        f"le binaire atteint des ecrans que le DEPART n'atteint pas : {ecart}")


# ---------------------------------------------------------------------------
# Les bancs de la CONFRONTATION -- la cible a CHAQUE rang de la liste
# ---------------------------------------------------------------------------

#: Trois ecrans de synthese, **distinguables** : trois modules, trois noms,
#: trois rangs dans l'ordre trie. Jamais un remplissage uniforme -- une
#: troncature ou une permutation ne se verrait pas sur des elements egaux.
_TROIS_ECRANS = (("aaa_module", "EcranDeTete"),
                 ("mmm_module", "EcranDuMilieu"),
                 ("zzz_module", "EcranDeQueue"))


def _registre_de_synthese(*cles) -> tuple:
    """Un registre de synthese, un motif long et **different** par entree."""
    return tuple(HorsChaine(module, classe,
                            f"motif de synthese pour {classe}, assez long "
                            f"pour passer la mesure de longueur du banc")
                 for module, classe in cles)


@pytest.mark.parametrize("rang", [0, 1, 2],
                         ids=["tete", "milieu", "queue"])
def test_l_orphelin_est_vu_A_CHAQUE_RANG_de_la_liste(rang):
    """Tete, milieu et queue : aucun orphelin n'echappe a la confrontation.

    **Le mutant qui a impose ce banc** : `sorted(...)[:-1]` sur la liste des
    orphelins (`M22`, campagne du 2026-09-06). Il **survivait** a toute la
    frontiere, parce que sur l'etat reel du depot cette liste est vide -- une
    troncature d'une liste vide est un non-evenement. Le defaut ne se serait
    reveille que le jour ou un orphelin serait apparu, c'est-a-dire exactement
    le jour ou la frontiere devait servir.
    """
    ecrans = set(_TROIS_ECRANS)
    cible = _TROIS_ECRANS[rang]
    atteints = {c for c in _TROIS_ECRANS if c != cible}
    assert orphelins(ecrans, atteints, ()) == [cible]
    # Inscrite au registre, elle cesse d'etre un manque -- et elle seule.
    assert orphelins(ecrans, atteints, _registre_de_synthese(cible)) == []
    # Un registre qui inscrirait une AUTRE classe ne l'excuse pas.
    autre = _TROIS_ECRANS[(rang + 1) % 3]
    assert orphelins(ecrans, atteints, _registre_de_synthese(autre)) == [cible]


@pytest.mark.parametrize("rang", [0, 1, 2],
                         ids=["tete", "milieu", "queue"])
def test_l_entree_FANTOME_est_vue_A_CHAQUE_RANG(rang):
    """Une entree de registre sans classe correspondante, a chaque rang.

    Le registre est parcouru **en entier** : un balayage qui sauterait sa
    derniere entree laisserait vivre une derogation perimee, et une derogation
    perimee excuse d'avance le manque suivant.
    """
    registre = _registre_de_synthese(*_TROIS_ECRANS)
    cible = _TROIS_ECRANS[rang]
    ecrans = {c for c in _TROIS_ECRANS if c != cible}
    assert entrees_fantomes(ecrans, registre) == [cible]
    assert entrees_fantomes(set(_TROIS_ECRANS), registre) == []


@pytest.mark.parametrize("rang", [0, 1, 2],
                         ids=["tete", "milieu", "queue"])
def test_l_entree_PERIMEE_est_vue_A_CHAQUE_RANG(rang):
    """Une entree dont la classe est desormais atteinte, a chaque rang.

    C'est le filet « pas encore » reste en place apres la livraison de sa
    destination -- `MQ-4` et `MQ-5` transposes au registre. Les trois rangs
    sont joues parce que le balayage, la aussi, peut se tronquer d'un bord.
    """
    registre = _registre_de_synthese(*_TROIS_ECRANS)
    cible = _TROIS_ECRANS[rang]
    assert entrees_perimees({cible}, registre) == [cible]
    assert entrees_perimees(set(), registre) == []
    assert entrees_perimees(set(_TROIS_ECRANS), registre) == sorted(_TROIS_ECRANS)


# ---------------------------------------------------------------------------
# Les bancs du RECENSEMENT -- la cible a CHAQUE rang du balayage
# ---------------------------------------------------------------------------

def _paquet_de_synthese(dossier: Path, orpheline: str) -> None:
    """Quatre modules, **quatre ecrans distinguables**, un non-ecran.

    Les quatre ecrans different par leur nom **et par leur base** -- l'un
    derive de la racine, un autre d'un intermediaire, un troisieme d'une base
    **d'un autre module** : jamais un remplissage uniforme, ou une permutation
    ne se verrait pas. Les fichiers sont nommes pour que l'orpheline puisse
    etre posee en **tete** (`aaa_`), au **milieu** (`mmm_`) ou en **queue**
    (`zzz_`) de l'ordre alphabetique du balayage.
    """
    (dossier / "coque.py").write_text(
        "from textual.screen import Screen\n\n\n"
        "class Palier(Screen):\n"
        "    pass\n\n\n"
        "class PasUnEcran:\n"
        '    """Une classe ordinaire, qui cite Palier sans en deriver."""\n',
        encoding="utf-8")
    corps = {
        "aaa_en_tete": (
            "from .coque import Palier\n\n\n"
            "class EcranDeTete(Palier):\n"
            '    """Le premier du balayage."""\n'),
        "mmm_au_milieu": (
            "from .coque import Palier\n\n\n"
            "class EcranIntermediaire(Palier):\n"
            '    """Une base d\'un autre module."""\n\n\n'
            "class EcranDuMilieu(EcranIntermediaire):\n"
            '    """Deux niveaux d\'heritage, dans le meme module."""\n'),
        "zzz_en_queue": (
            "from . import mmm_au_milieu\n"
            "from .mmm_au_milieu import EcranIntermediaire\n\n\n"
            "class EcranDeQueue(EcranIntermediaire):\n"
            '    """Heritage a TRAVERS les modules, trois niveaux."""\n\n\n'
            "class EcranPointe(mmm_au_milieu.EcranIntermediaire):\n"
            '    """Base ecrite en forme POINTEE -- `module.Classe`."""\n'),
    }
    for nom, source in corps.items():
        (dossier / f"{nom}.py").write_text(source, encoding="utf-8")
    (dossier / "nnn_sans_ecran.py").write_text(
        'UNE_CONSTANTE = "EcranDeQueue"\n\n\n'
        "class RienDuTout:\n"
        '    """Ni ecran ni orpheline : le recensement doit l\'ecarter."""\n',
        encoding="utf-8")
    assert orpheline in ("EcranDeTete", "EcranDuMilieu", "EcranDeQueue")


def test_le_recensement_voit_un_ecran_a_CHAQUE_BORD_du_balayage(tmp_path):
    """Tete, milieu et queue : un balayage tronque d'un bord se voit.

    **Le mode de panne vise** : `sorted(...)[:-1]` ou `[1:]` dans
    :func:`arbres_du_paquet`. Aucun test positif ne le verrait -- il ne manque
    rien dans ce qui est observe, c'est **ce qui n'est plus observe** qui
    manque. C'est le quatrieme point de la regle des fabriques, et le defaut
    que ce depot paie le plus souvent en mutants survivants.
    """
    _paquet_de_synthese(tmp_path, "EcranDeTete")
    recense = classes_d_ecran(tmp_path, ("coque", "Palier"))
    assert recense == {
        ("aaa_en_tete", "EcranDeTete"),
        ("mmm_au_milieu", "EcranIntermediaire"),
        ("mmm_au_milieu", "EcranDuMilieu"),
        ("zzz_en_queue", "EcranDeQueue"),
        ("zzz_en_queue", "EcranPointe"),
    }, sorted(recense)


def test_le_recensement_suit_l_heritage_A_TRAVERS_les_modules(tmp_path):
    """Trois niveaux et deux modules : `EcranDeQueue` est bien un ecran.

    Le regime est reel : `atelier_scan_parcours.EcranCollisionDuScan` derive
    d'`atelier_scan_calibrate.EcranCollisionDeProfil`, qui derive
    d'`EcranDeJugement`, qui derive de `Palier`. Une fermeture a un seul
    niveau, ou limitee au module, en raterait la majorite.
    """
    _paquet_de_synthese(tmp_path, "EcranDeQueue")
    recense = classes_d_ecran(tmp_path, ("coque", "Palier"))
    assert ("zzz_en_queue", "EcranDeQueue") in recense
    assert ("coque", "PasUnEcran") not in recense
    assert ("nnn_sans_ecran", "RienDuTout") not in recense


def test_le_recensement_resout_une_base_ECRITE_EN_FORME_POINTEE(tmp_path):
    """`class X(module.Base)` est un heritage comme un autre, et c'est reel.

    Le regime du produit : `atelier_scan_parcours.EcranCollisionDuScan` derive
    d'`atelier_scan_calibrate.EcranCollisionDeProfil`, ecrit en toutes lettres
    avec son module. Un resolveur qui ne connaitrait que la forme nue
    perdrait cette classe -- et une classe **hors recensement** n'est pas
    signalee manquante : elle disparait, ce qui est le pire des deux verdicts.

    **Le mutant qui a impose ce test** : `M19` de la campagne du 2026-09-06,
    survivant a l'ensemble de la frontiere parce qu'aucune source de synthese
    ne portait cette forme.
    """
    _paquet_de_synthese(tmp_path, "EcranDeQueue")
    recense = classes_d_ecran(tmp_path, ("coque", "Palier"))
    assert ("zzz_en_queue", "EcranPointe") in recense, sorted(recense)


def test_HERITER_c_est_ATTEINDRE(tmp_path):
    """Une base atteinte par sa fille seule fait vivre ses methodes.

    C'est la propriete sans laquelle le graphe serait faux dans le sens
    dangereux : une sous-classe montee par le produit **execute** les methodes
    de sa base, donc tout ce que ces methodes construisent est atteint. Le
    depot en depend partout -- `EcranResultat`, `EcranChiffre`,
    `EcranExecution` portent l'essentiel du comportement de leurs filles.

    **Le mutant qui a impose ce test** : `M17`, qui retirait l'arc
    d'heritage. Il **survivait**, parce que l'arc etait ecrit a DEUX endroits
    et que le second rattrapait le premier. L'invariant est desormais ecrit
    une fois, et mesure ici : `EcranSocle` n'est atteint que par sa fille, et
    c'est sa methode qui construit `EcranAnnexe`.
    """
    (tmp_path / "coque.py").write_text(
        "from textual.screen import Screen\n\n\nclass Palier(Screen):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "sss_annexe.py").write_text(
        "from .coque import Palier\n\n\nclass EcranAnnexe(Palier):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "ttt_socle.py").write_text(
        "from .coque import Palier\n\n\n"
        "class EcranSocle(Palier):\n"
        "    def secours(self):\n"
        "        from .sss_annexe import EcranAnnexe\n"
        "        return EcranAnnexe()\n",
        encoding="utf-8")
    (tmp_path / "uuu_fille.py").write_text(
        "from .ttt_socle import EcranSocle\n\n\n"
        "class EcranFille(EcranSocle):\n"
        '    """Elle n\'ecrit rien : tout son comportement vient du socle."""\n',
        encoding="utf-8")
    (tmp_path / "ddd_depart.py").write_text(
        "from .uuu_fille import EcranFille\n\n\n"
        "def depart():\n"
        '    """Le produit ne connait QUE la fille."""\n'
        "    return EcranFille()\n",
        encoding="utf-8")
    graphe = construire_le_graphe(tmp_path)
    atteints = graphe.atteignables(("ddd_depart", "depart"))
    assert ("ttt_socle", "EcranSocle") in atteints, (
        "la base n'est pas atteinte par sa fille : heriter cesse d'etre "
        "atteindre, et toutes les familles d'ecrans du depot deviennent "
        "orphelines de leur socle")
    assert ("sss_annexe", "EcranAnnexe") in atteints, (
        "l'ecran que construit une methode HERITEE n'est pas atteint : le "
        "graphe declarerait orphelin tout ce qu'un socle ouvre")
    assert classes_d_ecran(tmp_path, ("coque", "Palier")) - atteints == set()


def test_le_recensement_ne_mord_pas_sur_un_nom_CITE_dans_un_docstring(tmp_path):
    """Ce qui distingue cette frontiere d'un grep, et le regime est reel.

    `nnn_sans_ecran` porte la chaine `"EcranDeQueue"` et `coque.PasUnEcran`
    cite `Palier` dans sa prose. Un grep les compterait ; l'arbre syntaxique
    ne les voit pas comme des bases. C'est exactement le texte qui a masque
    `MQ-4` et `MQ-5` : les docstrings de `suivre` nommaient `SUITE_PDF` pour
    dire qu'elle n'avait pas d'atelier.
    """
    _paquet_de_synthese(tmp_path, "EcranDuMilieu")
    (tmp_path / "bbb_prose.py").write_text(
        "from .coque import Palier\n\n\n"
        "class PurTexte:\n"
        '    """Cet ecran ressemble a Palier et cite EcranDeTete, sans hériter."""\n'
        '    NOTE = "class EcranMenteur(Palier):"\n',
        encoding="utf-8")
    recense = classes_d_ecran(tmp_path, ("coque", "Palier"))
    assert ("bbb_prose", "PurTexte") not in recense
    assert ("bbb_prose", "EcranMenteur") not in recense
    assert len(recense) == 5, sorted(recense)


# ---------------------------------------------------------------------------
# Les bancs du GRAPHE -- l'orpheline a CHAQUE rang
# ---------------------------------------------------------------------------

def _paquet_avec_une_orpheline(dossier: Path, orpheline: str) -> None:
    """Le paquet de synthese, plus un depart qui atteint **tous sauf une**.

    Les trois ecrans atteints le sont par trois chemins **differents** : un
    appel direct, un import local, et une traversee de classe. Trois chemins
    identiques ne demasqueraient pas un resolveur qui n'en connaitrait qu'un.
    """
    _paquet_de_synthese(dossier, orpheline)
    ouvertures = {
        "EcranDeTete": "    from .aaa_en_tete import EcranDeTete\n"
                       "    return EcranDeTete()\n",
        "EcranDuMilieu": "    return mmm_au_milieu.EcranDuMilieu()\n",
        "EcranDeQueue": "    return _passer_par_la_queue()\n",
    }
    lignes = ["from . import mmm_au_milieu\n",
              "from .zzz_en_queue import EcranDeQueue\n\n\n",
              "def _passer_par_la_queue():\n",
              "    return EcranDeQueue()\n\n\n",
              "def depart():\n",
              '    """Le point d\'entree de synthese."""\n']
    lignes += [source for nom, source in ouvertures.items()
               if nom != orpheline]
    (dossier / "ddd_depart.py").write_text("".join(lignes), encoding="utf-8")


@pytest.mark.parametrize("orpheline,module", [
    ("EcranDeTete", "aaa_en_tete"),
    ("EcranDuMilieu", "mmm_au_milieu"),
    ("EcranDeQueue", "zzz_en_queue"),
])
def test_le_graphe_voit_l_orpheline_a_CHAQUE_RANG(tmp_path, orpheline, module):
    """En **tete**, au **milieu** et en **queue** : les trois sont vues.

    Le milieu demasque un aiguillage fautif ; les deux bords demasquent un
    balayage tronque. Les trois cibles sont **distinguables** -- trois noms,
    trois modules, trois profondeurs d'heritage.
    """
    _paquet_avec_une_orpheline(tmp_path, orpheline)
    graphe = construire_le_graphe(tmp_path)
    ecrans = classes_d_ecran(tmp_path, ("coque", "Palier"))
    atteints = graphe.atteignables(("ddd_depart", "depart"))
    orphelins = ecrans - atteints
    # `EcranIntermediaire` n'est atteint que quand une de ses filles l'est :
    # c'est l'heritage qui l'amene, pas un appel.
    assert (module, orpheline) in orphelins, sorted(orphelins)
    for autre in ("EcranDeTete", "EcranDuMilieu", "EcranDeQueue"):
        if autre != orpheline:
            assert not [c for c in orphelins if c[1] == autre], sorted(orphelins)


def test_le_graphe_NE_confond_PAS_un_parametre_avec_la_fonction_du_module(
        tmp_path):
    """Le faux arc reel, mesure et ferme : la portee locale MASQUE.

    **Le regime est celui du produit** : `ChaineReelle.__init__` prend
    `ouvrir_les_cadences` en parametre et l'affecte a un attribut, pendant que
    le meme module declare une fonction de ce nom. Sans portee, le graphe
    tenait l'injection pour faite -- retirer `ouvrir_les_cadences=` de
    :func:`chaine_du_produit` laissait alors **zero** orphelin au lieu de neuf.

    Un graphe trop genereux ne rate pas seulement un manque : il **certifie**
    qu'il n'y en a pas.
    """
    (tmp_path / "coque.py").write_text(
        "from textual.screen import Screen\n\n\nclass Palier(Screen):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "mmm_ecran.py").write_text(
        "from .coque import Palier\n\n\nclass EcranCache(Palier):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "ddd_depart.py").write_text(
        "from .mmm_ecran import EcranCache\n\n\n"
        "def ouvrir():\n"
        '    """La VRAIE ouverture : elle seule construit l\'ecran."""\n'
        "    return EcranCache()\n\n\n"
        "class Chaine:\n"
        "    def __init__(self, ouvrir=None):\n"
        "        # `ouvrir` est le PARAMETRE, pas la fonction du module.\n"
        "        self._ouvrir = ouvrir\n\n\n"
        "def depart():\n"
        "    return Chaine()\n",
        encoding="utf-8")
    graphe = construire_le_graphe(tmp_path)
    atteints = graphe.atteignables(("ddd_depart", "depart"))
    assert ("ddd_depart", "ouvrir") not in atteints, (
        "le parametre `ouvrir` a ete confondu avec la fonction du module : le "
        "graphe croit l'injection faite alors qu'elle vient d'ailleurs")
    assert ("mmm_ecran", "EcranCache") not in atteints


def test_le_graphe_SUIT_un_import_local(tmp_path):
    """Le symetrique du test ci-dessus, et il n'est pas redondant.

    Un import pose **dans** une fonction lie lui aussi un nom local -- si la
    portee le traitait comme masquant, le graphe perdrait le seul endroit ou le
    produit se cable : :func:`chaine_du_produit` importe ses quatre ouvertures
    d'atelier a l'interieur de son corps. Une portee trop stricte rendrait
    alors les cinquante ecrans des ateliers orphelins d'un coup.
    """
    (tmp_path / "coque.py").write_text(
        "from textual.screen import Screen\n\n\nclass Palier(Screen):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "mmm_ecran.py").write_text(
        "from .coque import Palier\n\n\nclass EcranVu(Palier):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "ddd_depart.py").write_text(
        "def depart():\n"
        "    from .mmm_ecran import EcranVu\n"
        "    return EcranVu()\n",
        encoding="utf-8")
    graphe = construire_le_graphe(tmp_path)
    atteints = graphe.atteignables(("ddd_depart", "depart"))
    assert ("mmm_ecran", "EcranVu") in atteints


def test_un_DEPART_introuvable_LEVE_au_lieu_de_tout_declarer_orphelin(tmp_path):
    """Un depart renomme dit qu'il est renomme, il ne se deguise pas.

    Sans cette garde, renommer :func:`chaine_du_produit` rendrait un ensemble
    vide, donc **soixante-dix** manques d'un coup -- un message qui ne
    designerait pas la cause. Meme patron que le rappel introuvable de
    `test_couverture_des_suites.py`.
    """
    (tmp_path / "coque.py").write_text(
        "from textual.screen import Screen\n\n\nclass Palier(Screen):\n    pass\n",
        encoding="utf-8")
    graphe = construire_le_graphe(tmp_path)
    with pytest.raises(AssertionError, match="n'existe pas"):
        graphe.atteignables(("ddd_depart", "absent"))


# ---------------------------------------------------------------------------
# Volet 3 -- les MONTEES REELLES, clavier compris
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Montee:
    """Une suite de frappes, et le TYPE de l'ecran qui doit arriver.

    `touches` part de l'application nue montee par :func:`chaine_du_produit`,
    jamais d'une chaine assemblee a la main : c'est cette assemblee manuelle
    qui a masque le lot `E9` pendant deux vagues.
    """

    touches: tuple[str, ...]
    module: str
    classe: str
    parcours: str

    @property
    def cle(self) -> tuple[str, str]:
        return (self.module, self.classe)

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return self.parcours


#: **Les portes du produit, montees pour de vrai.** Les cinq entrees du menu
#: des ateliers sont jouees **toutes les cinq** -- la premiere et la derniere
#: comprises : un aiguillage qui rendrait toujours la premiere destination
#: resterait vert sur elle seule, et un balayage tronque des entrees ne se
#: verrait qu'aux bords. Les deux menus d'atelier qui en ont un
#: (`EPIC11-ARB-28`) sont descendus d'un cran de plus.
MONTEES_REELLES: tuple[Montee, ...] = (
    Montee(("enter", "enter"),
           "atelier_extraction", "EcranRushes",
           "ateliers[0] Extraction -- la TETE du menu"),
    # **`Pdf` est en rang 1 et `Scan` en rang 2 depuis le 2026-09-06** (retour
    # terrain d'Egan : « remonter l'atelier [PDF] dans la liste AVANT scan
    # (ordre logique) »). Les frappes suivent l'ordre reel du menu, qui est
    # celui de `projet_lecture.ATELIERS`.
    Montee(("enter", "down", "enter"),
           "atelier_pdf", "EcranPdfMenu",
           "ateliers[1] Pdf -- `MQ-4`"),
    Montee(("enter", "down", "down", "enter"),
           "atelier_scan", "EcranScanMenu",
           "ateliers[2] Scan"),
    Montee(("enter", "down", "down", "down", "enter"),
           "atelier_exports_lot", "EcranDesLotsAEncoder",
           "ateliers[3] Exports -- `MQ-5`"),
    Montee(("enter", "down", "down", "down", "down", "enter"),
           "palier_projet", "EcranPalierProjet",
           "ateliers[4] Projet -- la QUEUE du menu"),
    Montee(("enter", "down", "down", "down", "down", "enter", "enter"),
           "projet_inventaire", "EcranInventaireDuProjet",
           "projet[0] Gestion des medias -- `MQ-8`"),
    Montee(("enter", "down", "enter", "enter"),
           "atelier_pdf_lots", "EcranLotsAPlanches",
           "pdf[0] Composer des planches"),
    Montee(("enter", "down", "enter", "down", "enter"),
           "atelier_pdf_calibration", "EcranMireReglages",
           "pdf[1] Imprimer une mire -- la QUEUE du menu Pdf"),
    Montee(("enter", "down", "down", "enter", "enter"),
           "atelier_scan", "EcranScanDepot",
           "scan[0] Deposer un scan"),
    Montee(("enter", "down", "down", "enter", "down", "enter"),
           "atelier_scan_calibrate", "EcranCalibrerLaChaine",
           "scan[1] Calibrer la chaine -- la QUEUE du menu Scan"),
)


def _projet_montable(tmp_path: Path) -> Path:
    """Un projet reel **dont les cinq entrees du menu sont disponibles**.

    Deux rushes, deux lots, **tous distinguables** : deux geometries, deux
    cadences, deux cardinaux de frames et quatre poids de fichier tous
    differents (11, 21, 31 et 1001 octets). Jamais un remplissage uniforme --
    un desappariement entre un lot et ce qu'un ecran en dit ne se verrait pas
    sur des valeurs egales.

    Les `output_frames_dir` **et leur matiere sur le disque** sont ce qui rend
    l'entree `Exports` disponible : son verdict est celui du coeur
    (`encode.list_encodable_lots`) et « porte sur la matiere autant que sur
    l'etat ». Sans eux, `⏎` reste sur le menu et nomme sa condition -- ce qui
    est le comportement voulu, mais qui ne mesurerait pas la porte.
    """
    from mixed_media_utility import encode
    from mixed_media_utility.gui.depot_projets import creer_projet

    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [
        {"rush_id": "a-premier",
         "resolution_source": {"width": 1920, "height": 1080}},
        {"rush_id": "z-second",
         "resolution_source": {"width": 1280, "height": 720}},
    ]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25",
         "state": encode.MINIMUM_LOT_STATE, "fps_target": 25,
         "expected_frame_count": 2, "timecode_base_fps": "25/1",
         "output_frames_dir": "output-frames/a-premier_25",
         "output_bit_depth": 16},
        {"lot_id": "z-second_8", "rush_id": "z-second",
         "frames_dir": "extract-frames/z-second_8",
         "state": encode.MINIMUM_LOT_STATE, "fps_target": 8,
         "expected_frame_count": 1, "timecode_base_fps": "8/1",
         "output_frames_dir": "output-frames/z-second_8",
         "output_bit_depth": 16},
    ]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (
            ("extract-frames/a-premier_25/f0.tiff", 11),
            ("extract-frames/z-second_8/f0.tiff", 1001),
            ("output-frames/a-premier_25/f0.tiff", 21),
            ("output-frames/a-premier_25/f1.tiff", 31),
            ("output-frames/z-second_8/f0.tiff", 41)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _monter(chemin: Path, tmp_path: Path, touches, banc):
    """Monter **l'application du produit** et frapper `touches`.

    `chaine_du_produit` et non `ChaineReelle(...)` : le premier injecte les
    parcours, le second est la version degradee que seuls les bancs montent.
    Mesurer le second serait mesurer un produit qui n'existe pas.
    """
    from mixed_media_utility.tui import projets
    from mixed_media_utility.tui.atelier_extraction_ecriture import (
        chaine_du_produit)

    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    chaine = chaine_du_produit(recents=recents)

    async def scenario(pilote):
        await pilote.press(*touches)
        await pilote.pause()
        return pilote.app.screen

    return banc(chaine.app, scenario)


@pytest.mark.parametrize("montee", MONTEES_REELLES, ids=str)
def test_la_porte_S_OUVRE_POUR_DE_VRAI_au_clavier(tmp_path, banc, montee):
    """Le volet que le graphe ne remplace pas : on MONTE, on ne lit pas.

    `test_couverture_des_suites.py` avertit d'elle-meme qu'elle « mesure qu'une
    branche est NOMMEE, pas qu'elle mene quelque part d'utile ». Le graphe de
    ce fichier a la meme limite d'un cran plus loin : il mesure qu'une classe
    est **nommee dans un corps atteignable**, pas qu'une suite de frappes y
    conduise. Ces dix montees ferment l'ecart aux endroits ou les trois manques
    ont vecu -- **aux portes**, jamais au fond d'un atelier.

    `EcranPasEncore` est refuse explicitement : c'est la forme exacte qu'ont
    prise `MQ-4`, `MQ-5` et `MQ-8`, et un test qui ne verifierait que « l'ecran
    a change » l'accepterait.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    chemin = _projet_montable(tmp_path)
    ecran = _monter(chemin, tmp_path, montee.touches, banc)

    assert not isinstance(ecran, EcranPasEncore), (
        f"{montee} tombe dans le filet « pas encore » : "
        f"{getattr(ecran, 'ce_qui_manque', '')!r}")
    obtenu = (type(ecran).__module__.rsplit(".", 1)[-1], type(ecran).__name__)
    assert obtenu == montee.cle, (
        f"{montee} : attendu {montee.module}.{montee.classe}, "
        f"obtenu {obtenu[0]}.{obtenu[1]}")


def test_les_montees_CALIBRENT_le_graphe_et_le_recensement():
    """Ce que le clavier atteint, le graphe doit le declarer atteignable.

    C'est la confrontation des deux volets, et elle va **dans le sens qui
    peut echouer** : un graphe qui declarerait orpheline une classe que dix
    frappes atteignent serait faux, et son verdict d'orphelinat -- le seul qui
    fasse rougir la frontiere -- ne vaudrait plus rien.

    Les dix montees sont en outre toutes **distinctes**, et leurs classes sont
    toutes recensees : une montee vers une classe hors recensement mesurerait
    un ecran que la frontiere ne garde pas.
    """
    graphe = graphe_du_produit()
    ecrans = classes_d_ecran()
    atteints = graphe.atteignables(DEPART)

    assert len(MONTEES_REELLES) >= 10, len(MONTEES_REELLES)
    cles = [montee.cle for montee in MONTEES_REELLES]
    assert len(set(cles)) == len(cles), f"deux montees vers la meme classe : {cles}"
    chemins = [montee.touches for montee in MONTEES_REELLES]
    assert len(set(chemins)) == len(chemins), "deux montees aux memes frappes"

    for montee in MONTEES_REELLES:
        assert montee.cle in ecrans, (
            f"{montee} vise {montee.module}.{montee.classe}, qui n'est pas "
            f"une classe d'ecran recensee")
        assert montee.cle in atteints, (
            f"{montee} est atteinte au CLAVIER et le graphe la declare "
            f"orpheline : le graphe est faux, et son verdict d'orphelinat ne "
            f"vaut plus rien")


def test_les_cinq_entrees_du_menu_des_ateliers_sont_TOUTES_montees():
    """Aucune entree du menu ne sort du banc en silence.

    C'est le meme volet symetrique que « aucun module declarant n'echappe a la
    table » : sans lui, une sixieme entree du menu pourrait etre livree sans
    porte et sans qu'aucune montee ne la joue. Le recensement des entrees est
    lu du **coeur** (`projet_lecture.ATELIERS + (PROJET,)`), jamais recopie
    ici.
    """
    from mixed_media_utility.tui import projet_lecture

    attendues = len(projet_lecture.ATELIERS) + 1
    depuis_le_menu = [montee for montee in MONTEES_REELLES
                      if montee.touches[0] == "enter"
                      and set(montee.touches[1:-1]) <= {"down"}
                      and montee.touches[-1] == "enter"]
    descentes = {montee.touches.count("down") for montee in depuis_le_menu}
    assert descentes == set(range(attendues)), (
        f"les entrees du menu jouees sont {sorted(descentes)} pour "
        f"{attendues} entrees declarees par le coeur : la tete et la queue "
        f"sont exigees, pas seulement le milieu")


# ---------------------------------------------------------------------------
# Ce que cette frontiere NE mesure PAS -- executable, pour perimer bruyamment
# ---------------------------------------------------------------------------

def test_ce_que_cette_frontiere_ne_mesure_pas(tmp_path):
    """Les trois limites connues, **mesurees** plutot que declarees en prose.

    1. **Elle mesure une reference, pas une execution.** Un
       `if False: EcranX()` -- ou une branche morte, ou un rappel jamais
       appele -- suffit a rendre un ecran « atteint ». C'est la meme limite
       que `test_couverture_des_suites.py` s'ecrit a elle-meme, d'un cran plus
       loin, et c'est pourquoi :data:`MONTEES_REELLES` existe. Les dix montees
       couvrent les **portes** ; elles ne couvrent pas le fond des ateliers ;
    2. **elle ne mesure pas la reciproque au clavier.** Un ecran que le graphe
       declare atteint peut n'etre atteignable par aucune suite de frappes --
       si son unique appelant est un chemin d'erreur qu'aucune donnee ne
       declenche, par exemple. Mesurer cela exigerait un parcours exhaustif du
       clavier, qui n'existe pas dans ce depot ;
    3. **elle ne voit pas un aiguillage par CHAINE.** Un rappel choisi par
       `getattr(module, nom)` ou par une table de chaines ne produit aucun arc.
       Aucun cablage du paquet `tui/` n'a cette forme au 2026-09-06 -- c'est
       mesure ci-dessous --, mais la frontiere ne rougirait pas si l'un en
       prenait une.
    """
    # 1. Une branche morte suffit -- la limite est demontree, pas supposee.
    (tmp_path / "coque.py").write_text(
        "from textual.screen import Screen\n\n\nclass Palier(Screen):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "mmm_ecran.py").write_text(
        "from .coque import Palier\n\n\nclass EcranMort(Palier):\n    pass\n",
        encoding="utf-8")
    (tmp_path / "ddd_depart.py").write_text(
        "from .mmm_ecran import EcranMort\n\n\n"
        "def depart():\n"
        "    if False:\n"
        "        return EcranMort()\n"
        "    return None\n",
        encoding="utf-8")
    graphe = construire_le_graphe(tmp_path)
    assert ("mmm_ecran", "EcranMort") in graphe.atteignables(
        ("ddd_depart", "depart")), (
        "cette limite vient d'etre fermee : la mettre a jour dans le "
        "docstring plutot que de la laisser mentir")

    # 3. Aucun cablage du paquet reel ne passe par `getattr` sur un ecran.
    suspects = []
    for chemin in sorted(TUI.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "getattr"
                    and len(noeud.args) >= 2
                    and isinstance(noeud.args[1], ast.Constant)
                    and str(noeud.args[1].value).startswith("Ecran")):
                suspects.append(f"{chemin.stem}:{noeud.lineno}")
    assert not suspects, (
        f"un ecran est desormais choisi par son NOM et non par une reference : "
        f"{suspects}. Le graphe de cette frontiere ne produit aucun arc pour "
        f"cette forme -- l'ecran passerait pour orphelin, ou pire, un autre "
        f"passerait pour atteint.")
