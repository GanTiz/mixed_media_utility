# -*- coding: utf-8 -*-
"""Le REGISTRE des filets « pas encore » -- un inventaire ferme, confronte au code.

**Le mode de panne que ce banc ferme, et le depot l'a paye QUATRE fois.**
`EcranPasEncore` est le filet du produit : un ecran qui NOMME ce qui n'existe
pas encore, avec son echeance. C'est un bon dispositif -- `EPIC11-ARB-89`
interdit le blocage sec, donc nommer vaut mieux que refuser. Son mode de panne
est ailleurs : **un filet laisse en place APRES que sa destination a ete
livree**. L'operateur atteint alors un ecran qui dit « pas encore » pour
quelque chose qui existe.

Les quatre occurrences, toutes du 2026-09-05 au 2026-09-06 :

* `MQ-4` et `MQ-5` -- les suites `SUITE_PDF` et `SUITE_EXPORTS` tombaient dans
  le filet alors que les stories 11.7 et 11.8 avaient livre leurs ateliers ;
* `MQ-A` -- deux ateliers livres qu'aucun chainage n'atteignait ;
* les quatre suites de `E6-3`/`E6-3b`, montees **sans `sur_suite`**, donc
  toutes au filet, sur deux ecrans livres et valides.

**Ce que les quatre frontieres existantes mesurent deja, et pourquoi il en
fallait une cinquieme.** Le depot approche le probleme par la DESTINATION :

======================================================  =========================
frontiere                                               ce qu'elle recense
======================================================  =========================
`test_couverture_des_suites.py`                         les constantes `SUITE_*`
`test_couverture_des_entrees_de_palier.py`              les constantes `ENTREE_*`
`test_rappels_cables.py`                                les rappels `Callable`
`test_atteignabilite_des_ecrans.py`                     les classes d'ecran
======================================================  =========================

**Aucune ne recense les SITES qui montent le filet.** Un filet dont la garde
n'est ni une constante declaree ni un rappel optionnel -- une condition
ordinaire, comme `if cible is None` dans
`projet_suppression.ouvrir_la_suppression` ou `if not dossier_projet` dans
`projet_inventaire.ouvrir_l_inventaire_du_projet` -- est invisible aux quatre.
Un filet **neuf** ajoute demain dans un module qui ne declare ni suite ni
entree de palier l'est aussi. C'est par la que la cinquieme occurrence
entrerait, et c'est ce trou que ce fichier ferme : **tout site qui monte
`EcranPasEncore` doit entrer au registre, avec la raison pour laquelle sa
destination n'existe pas encore.**

Ce que cette frontiere mesure, en quatre volets
-----------------------------------------------
1. **le recensement**, lu sur l'ARBRE SYNTAXIQUE et jamais par grep. C'est la
   lecon exacte de `MQ-4`/`MQ-5` : un docstring qui cite `EcranPasEncore` pour
   dire qu'un ecran n'existe pas **porte le mot**, et un grep y mord. Le
   recensement porte sur **tout** `src/mixed_media_utility/`, pas sur `tui/`
   seul : rien n'empeche un filet de naitre ailleurs ;
2. **la confrontation au registre, dans les DEUX sens.** Un site absent du
   registre fait rougir -- c'est le filet neuf, non justifie. Une entree de
   registre qui ne correspond a aucun site fait rougir aussi -- c'est
   l'entree PERIMEE, celle qui masquerait le manque suivant. Meme discipline
   que le `REGISTRE` de `test_atteignabilite_des_ecrans.py`, et pour le meme
   motif ;
3. **la confrontation de chaque REVENDICATION au produit**, et c'est ce qui
   distingue ce banc d'une liste de commentaires. Une entree ne dit pas
   seulement « ce filet est legitime » : elle dit **pourquoi**, sous une forme
   que le code peut dementir --

   * :data:`HORS_PRODUIT_RAPPEL` revendique que le site n'est atteint que
     lorsqu'un rappel optionnel n'est pas injecte, et que **le produit
     l'injecte**. La paire `(classe, mot-cle)` est confrontee a
     :func:`test_rappels_cables.rappels_injectes`, importee plutot que
     recopiee. Le jour ou quelqu'un decable ce rappel, le filet redevient
     atteignable et **ce banc rougit** ;
   * :data:`ATTEIGNABLE_ABSENCE` revendique que la destination n'existe pas.
     Quand cette absence porte un nom -- un parametre de coeur, un symbole --,
     l'entree pose un `temoin`, et le banc mesure que **le temoin ne resout
     toujours pas**. Le jour ou la destination est livree, le temoin resout et
     ce banc rougit : c'est la mesure anti-cinquieme-occurrence proprement
     dite ;
   * :data:`HORS_PRODUIT_CLE` revendique que le site n'est atteint que par une
     cle ou une suite qu'aucun module ne declare, et **nomme la frontiere
     soeur** qui tient cette revendication. Le fichier nomme doit exister ;
4. **le volet symetrique**, sans lequel les trois autres passeraient en
   n'observant rien : un recenseur qui cesserait de reconnaitre un site verrait
   zero filet, donc zero manque. Les cardinaux sont bornes par le bas, et le
   recenseur lui-meme est mesure sur des sources de synthese.

Ce que cette frontiere NE mesure PAS, dit plutot que tu
--------------------------------------------------------
* **elle ne sait pas si un motif est VRAI.** Un motif est de la prose, et de la
  prose ne se mesure pas. Ce qu'elle tient, c'est qu'il y en ait un, et que la
  revendication *typee* qui l'accompagne -- la paire de rappel, le temoin, la
  frontiere soeur -- soit confrontee au code. Un motif faux sous une
  revendication vraie passe ; c'est le prix, et il est nomme ici plutot que
  tu ;
* **elle ne voit une destination livree que si un temoin la nomme.** Le seul
  temoin que ce registre ait jamais porte -- le parametre de coeur
  `frames_extraites` -- a RESOLU le 2026-09-07 : le banc a rougi, le filet a
  ete cable et son entree a change de famille. C'est la mesure faisant ce
  qu'elle promettait, et c'est aussi ce qui rend le trou visible : les entrees
  `ATTEIGNABLE_ABSENCE` restantes n'en portent AUCUN, parce qu'elles attendent
  un ECRAN que personne n'a encore nomme. Poser un temoin sur un nom que le
  depot n'a pas promis serait decoratif -- il ne resoudrait pas davantage le
  jour ou l'ecran arriverait sous un autre nom. Le trou est reel et il est
  ici ;
* **elle ne mesure aucune montee reelle.** Qu'un site soit hors du produit est
  une revendication *statique*. Le clavier est mesure ailleurs -- les dix
  montees reelles de `test_atteignabilite_des_ecrans.py`, qui refusent le filet
  a l'arrivee. Les deux mesures sont complementaires et aucune ne remplace
  l'autre : celle-la attrape l'erreur de cablage, celle-ci attrape l'oubli ;
* **elle ne juge pas l'ECHEANCE.** Elle recense les echeances employees et
  ferme leur ensemble -- une echeance neuve doit se declarer --, mais elle ne
  sait pas qu'une echeance est PASSEE. `QUAND_ARRIVENT_LES_ATELIERS` vaut « les
  ateliers de la vague 3 », qui sont livres : c'est un calendrier perime sur
  douze sites, il est porte a `deferred-work.md`, et **ce banc ne le voit
  pas**. Il ne le verra pas davantage demain : departager une echeance vraie
  d'une echeance passee demande de savoir ce qui a ete livre, ce qu'aucun
  fichier du depot ne dit sous une forme mesurable.

Regle des fabriques (`CLAUDE.md`, les QUATRE points)
-----------------------------------------------------
Le recenseur balaie deux collections emboitees -- les modules d'un paquet, puis
les appels d'un module --, donc la regle mord des deux cotes. Les paquets de
synthese portent **trois modules aux noms distincts**, jamais un remplissage
uniforme, et le module porteur du filet est place tour a tour **en tete**, **au
milieu** et **en queue** de l'ordre du balayage. A l'interieur d'un module, deux
sites sont poses dans la **meme fonction**, l'un en premiere instruction du
corps et l'autre en derniere : le milieu demasque un aiguillage fautif, les deux
bords demasquent un balayage tronque, qui est un autre mode de panne.

Ce que la campagne de mutation a change ici (2026-09-06)
--------------------------------------------------------
**26 mutants injectes, 14 tues, 12 replies en mesure de REGRESSION.** Les
quatorze premiers portent sur l'OUTIL -- le recenseur, le resolveur de portee,
le temoin --, et ils meurent : troncature du balayage en tete et en queue,
`ast.walk` reduit au corps de tete, un seul site par module, portee la plus
exterieure au lieu de la plus interieure, forme pointee ignoree, echeance
jamais lue, temoin qui rend toujours faux ou toujours vrai.

Les douze autres portent sur les ASSERTIONS, et **muter une assertion ne peut
jamais faire rougir son propre banc** : la question utile est « quelle
regression la fait tomber ? ». Elle a ete posee et mesuree une par une, chaque
regression injectee puis le test vise joue :

==================================================  ==========================
assertion                                           la regression qui la leve
==================================================  ==========================
le site est au registre (`M15`)                     un filet NEUF, non declare
l'entree n'est pas perimee (`M16`)                  un filet retire, l'entree
                                                    reste
les bornes du recensement (`M17`, `M25`)            recenseur et registre vides
                                                    ENSEMBLE
l'ensemble des echeances est ferme (`M18`)          un filet neuf portant une
                                                    echeance neuve
la cle est discriminante (`M19`)                    deux entrees sur le meme
                                                    site
le rappel est injecte (`M20`)                       un rappel DECABLE dans
                                                    `src/`
la frontiere soeur existe (`M21`)                   elle est renommee
le motif est ecrit (`M22`)                          une entree sans motif
la famille est dans l'ensemble (`M23`)              une famille inventee
**le temoin ne resout pas (`M24`)**                 **le coeur gagne un
                                                    parametre nomme par un
                                                    temoin** (arrive le
                                                    2026-09-07 avec
                                                    `frames_extraites=`)
le drapeau ASCII varie (`M26`)                      l'echeance disparait en
                                                    repli
==================================================  ==========================

Les onze regressions sont **rouges**. La dixieme est la mesure
anti-cinquieme-occurrence elle-meme : ajouter le parametre au coeur fait
rougir ce banc, qui nomme le site a cabler.

**Deux defauts que les survivants ont reveles, et qu'aucune relecture n'aurait
montres.** `ECHEANCES_DECLAREES` etait derive du registre
(`frozenset(f.site.quand for f in REGISTRE)`), donc la mesure etait une
tautologie : `M18` survivait, et sa regression passait. L'ensemble est
desormais ECRIT a plat. Et les bornes basses du recensement se croyaient la
premiere ligne contre un recenseur vide : elles ne le sont pas -- l'entree
perimee l'attrape d'abord --, ce que leur docstring dit maintenant.

Le drapeau que ce banc fait varier
-----------------------------------
Le filet est un ECRAN, et un ecran se rend dans deux geometries.
:func:`test_le_filet_rend_son_echeance_dans_les_DEUX_geometries` monte
`EcranPasEncore` avec `ascii_seul` **vrai puis faux** sur la meme echeance :
« une garde qui ne fait varier aucun de ses drapeaux ne mesure qu'un seul
chemin » (`CLAUDE.md`, 2026-09-06, apres `coque.Palier.bandeau`). Sans lui, un
filet correctement recense pourrait rendre une echeance amputee en `--ascii`
sans que rien ne le dise.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Les outils de recensement des rappels vivent la-bas, et on les **importe**
# plutot que de les recopier : un invariant ecrit a deux endroits n'est tenu
# nulle part (lecon `M17` de la campagne de `test_atteignabilite_des_ecrans`).
from test_rappels_cables import rappels_injectes  # noqa: E402

#: La racine mesuree. Deduite du fichier, jamais ecrite en dur : un depot
#: deplace ne doit pas faire rougir une frontiere de recensement.
PAQUET = _RACINE / "src" / "mixed_media_utility"

#: Le nom de la classe dont tout montage est un filet.
FILET = "EcranPasEncore"


# ---------------------------------------------------------------------------
# Les familles : chacune est une REVENDICATION que le code peut dementir
# ---------------------------------------------------------------------------

#: Le site n'est atteint que lorsqu'un rappel optionnel n'est pas injecte, et le
#: produit l'injecte. Exige `rappel` -- la paire `(classe, mot-cle)` --, qui est
#: confrontee a l'inventaire des rappels reellement injectes dans `src/`.
HORS_PRODUIT_RAPPEL = "hors-produit:rappel"

#: Le site n'est atteint que par une cle, une suite ou un nom d'atelier
#: qu'aucun module ne declare. Exige `mesuree_par` : le fichier de la frontiere
#: soeur qui tient la revendication « toute cle declaree porte sa branche ».
HORS_PRODUIT_CLE = "hors-produit:cle"

#: Le site n'est atteint que par un ecran construit hors du produit -- un
#: palier temoin, une entree de menu marquee non construite. Exige un motif qui
#: dise **ou** vit ce constructeur.
HORS_PRODUIT_TEMOIN = "hors-produit:temoin"

#: Le site EST atteignable dans le produit, et sa destination n'existe pas.
#: `temoin` est pose quand l'absence porte un nom mesurable ; sinon le motif
#: dit pourquoi aucun temoin n'est nommable.
ATTEIGNABLE_ABSENCE = "atteignable:absence"

#: Le site EST atteignable, et il porte le message d'un REFUS du coeur. Le
#: router vers `execution.EcranRefus` -- qui existe et sert huit sites -- est un
#: arbitrage produit, pas un cablage : `deferred-work.md` le porte.
ATTEIGNABLE_REFUS = "atteignable:refus"

FAMILLES = frozenset({HORS_PRODUIT_RAPPEL, HORS_PRODUIT_CLE,
                      HORS_PRODUIT_TEMOIN, ATTEIGNABLE_ABSENCE,
                      ATTEIGNABLE_REFUS})


# ---------------------------------------------------------------------------
# Le recensement -- arbre syntaxique, jamais texte
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Site:
    """Un montage de filet, identifie par ce qu'il DIT et non par sa ligne.

    **La cle ne porte pas de numero de ligne, et c'est delibere.** Une cle qui
    en porterait rougirait a chaque edition du module, et un registre qui rougit
    pour rien se met a jour sans qu'on le lise -- c'est-a-dire qu'il cesse de
    mesurer. Ce qui identifie un site est le couple de ses arguments : ce qui
    manque, et quand ca arrive. Les 36 sites du depot au 2026-09-06 sont
    distincts sous cette cle, et :func:`test_la_cle_d_un_site_est_DISCRIMINANTE`
    le mesure plutot que de le supposer.
    """

    module: str
    #: `Classe.methode` ou `fonction`, tel que l'arbre le donne.
    rappel: str
    #: La source du premier argument, telle qu'`ast.unparse` la rend.
    ce_qui_manque: str
    #: La source du second argument, ou `""` quand aucune echeance n'est dite.
    quand: str

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return f"{self.module}::{self.rappel}({self.ce_qui_manque}, {self.quand})"


def _qualnoms(arbre: ast.Module) -> list[tuple[int, int, str]]:
    """Les portees nommees du module, avec leurs bornes de lignes."""
    portees: list[tuple[int, int, str]] = []

    def descendre(noeud: ast.AST, prefixe: list[str]) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                chemin = prefixe + [enfant.name]
                portees.append((enfant.lineno, enfant.end_lineno or
                                enfant.lineno, ".".join(chemin)))
                descendre(enfant, chemin)
            else:
                descendre(enfant, prefixe)

    descendre(arbre, [])
    return portees


def _portee_la_plus_proche(portees, ligne: int) -> str:
    """La portee la plus INTERIEURE qui contient cette ligne.

    « La plus interieure » et non « la premiere trouvee » : un montage dans une
    methode vit aussi dans sa classe, et rendre la classe perdrait le rappel.
    C'est la borne de debut la plus grande qui designe la portee la plus
    profonde.
    """
    trouvee = ""
    depart = -1
    for debut, fin, nom in portees:
        if debut <= ligne <= fin and debut > depart:
            trouvee, depart = nom, debut
    return trouvee


def _nom_appele(noeud: ast.expr) -> str:
    """Le nom de ce qui est appele, forme pointee comprise.

    `EcranPasEncore(...)` et `coque.EcranPasEncore(...)` sont le meme montage.
    Le depot n'emploie aujourd'hui que la premiere forme -- souvent derriere un
    import differe au corps de la fonction --, mais une frontiere qui ne
    verrait pas la seconde serait contournable sans le vouloir.
    """
    if isinstance(noeud, ast.Name):
        return noeud.id
    if isinstance(noeud, ast.Attribute):
        return noeud.attr
    return ""


def sites_du_paquet(racine: Path | None = None) -> set[Site]:
    """Tous les montages de filet du paquet, lus a l'arbre syntaxique.

    **La definition de la classe elle-meme n'est pas un montage**, et rien ne
    l'exclut explicitement : `class EcranPasEncore(Palier)` est un `ClassDef`,
    pas un `Call`. C'est l'arbre qui fait la distinction, et c'est exactement
    pourquoi il est lu plutot que grepe.
    """
    racine = racine or PAQUET
    trouves: set[Site] = set()
    for fichier in sorted(racine.rglob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        portees = _qualnoms(arbre)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if _nom_appele(noeud.func) != FILET:
                continue
            args = [ast.unparse(a) for a in noeud.args]
            trouves.add(Site(
                module=fichier.relative_to(racine).as_posix(),
                rappel=_portee_la_plus_proche(portees, noeud.lineno),
                ce_qui_manque=args[0] if args else "",
                quand=args[1] if len(args) > 1 else ""))
    return trouves


# ---------------------------------------------------------------------------
# LE REGISTRE -- ferme, confronte au recensement dans les deux sens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Filet:
    """Une entree du registre : un site, sa famille, et sa revendication."""

    site: Site
    famille: str
    motif: str
    #: `(classe, mot-cle)` -- exige par :data:`HORS_PRODUIT_RAPPEL`. Il ne
    #: porte PAS le meme sens que `Site.rappel`, qui est le nom de la portee :
    #: celui-ci designe l'argument optionnel dont l'absence ouvre le filet.
    rappel_optionnel: tuple[str, str] | None = None
    #: Le fichier de la frontiere soeur -- exige par :data:`HORS_PRODUIT_CLE`.
    mesuree_par: str = ""
    #: Ce qui ne doit PAS exister. Deux formes seulement :
    #: `"symbole:<chemin.pointe>"` et `"parametre:<chemin.pointe>:<nom>"`.
    temoin: str = ""


def _f(module: str, portee: str, ce_qui_manque: str, quand: str, famille: str,
       motif: str, **reste) -> Filet:
    """Confort de redaction : le site s'ecrit a plat, l'entree se construit."""
    return Filet(Site(module, portee, ce_qui_manque, quand), famille, motif,
                 **reste)


_ECHEANCE_ATELIERS = "self.app.QUAND_ARRIVENT_LES_ATELIERS"
_ECHEANCE_MEDIAS = "QUAND_LA_GESTION_DES_MEDIAS"
_ECHEANCE_PORTE = "self.QUAND_LA_PORTE_VERS_UN_FICHIER"

#: **Les 36 filets du depot au 2026-09-06**, et le chemin qui y mene se lit de
#: droite a gauche : 37 avant `EPIC11-ARB-260`, qui a sorti les DEUX filets de
#: `ProjectMaintenanceError` (voir le commentaire du palier Projet plus bas),
#: donc 35 apres lui ; puis 36, l'ecran « Profil de calibration par defaut »
#: du palier Projet en ayant ajoute UN le soir du retour terrain d'Egan.
#: Chaque entree porte la raison pour
#: laquelle sa destination n'existe pas encore, sous une forme que le code peut
#: dementir. Une entree qui ne correspond plus a aucun site est **perimee** et
#: fait rougir : c'est ce que `test_atteignabilite_des_ecrans.py` a paye en
#: mutants survivants, et le geste est repris ici.
REGISTRE: tuple[Filet, ...] = (

    # -- Atelier Exports ----------------------------------------------------
    _f("tui/atelier_exports_execution.py", "EcranEncodageEnCours._pas_encore",
       "CE_QUI_MANQUE_APRES_L_INTERRUPTION", "QUAND_LE_PARCOURS",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursExports.encoder` injecte `sur_issue` depuis le lot B5 de la "
       "11.8 ; le repli ne sert que l'ecran construit a nu par un banc.",
       rappel_optionnel=("EcranEncodageEnCours", "sur_issue")),
    _f("tui/atelier_exports_lot.py", "EcranDesLotsAEncoder._pas_encore",
       "CE_QUI_MANQUE_APRES_LE_LOT", "QUAND_LES_REGLAGES",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursExports.ouvrir` injecte `continuer` depuis le lot B5 de la "
       "11.8 ; `E4-2` monte, et le repli ne sert que le banc.",
       rappel_optionnel=("EcranDesLotsAEncoder", "continuer")),
    _f("tui/atelier_exports_reglages.py",
       "EcranReglagesDeL_encodage._pas_encore",
       "CE_QUI_MANQUE_APRES_LES_REGLAGES", "QUAND_LA_CONFIRMATION",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursExports.designer` injecte `continuer` depuis le lot B5 ; "
       "`E4-3` (ou `E4-3b`) monte, et le repli ne sert que le banc.",
       rappel_optionnel=("EcranReglagesDeL_encodage", "continuer")),
    _f("tui/atelier_exports_parcours.py", "ParcoursExports.suivre",
       "suite", _ECHEANCE_ATELIERS,
       HORS_PRODUIT_CLE,
       "Repli d'une suite qu'aucun module ne declare. Les trois suites de "
       "`E4-5` portent chacune leur branche nommee.",
       mesuree_par="test_couverture_des_suites.py"),
    _f("tui/atelier_exports_resultat.py", "suivre",
       "suite", "app.QUAND_ARRIVENT_LES_ATELIERS",
       HORS_PRODUIT_CLE,
       "Meme repli, cote module de l'ecran plutot que du parcours : les deux "
       "rappels sont dans la table des couvertures.",
       mesuree_par="test_couverture_des_suites.py"),

    # -- Atelier Pdf --------------------------------------------------------
    _f("tui/atelier_pdf.py", "EcranPdfMenu.entrer",
       "entree.nom", "entree.quand",
       HORS_PRODUIT_TEMOIN,
       "Branche des entrees marquees `construite=False`. Les deux entrees du "
       "menu Pdf sont construites au 2026-09-06 : seule une entree fabriquee "
       "par un banc atteint cette branche, que l'invariant "
       "`EntreeDeMenu.__post_init__` garde par ailleurs."),
    _f("tui/atelier_pdf.py", "EcranPdfMenu.entrer",
       "entree.nom", "QUAND_L_ATELIER_PDF",
       HORS_PRODUIT_RAPPEL,
       "`ouvrir_l_atelier_pdf` injecte `entrer` depuis le lot C de la 11.7.",
       rappel_optionnel=("EcranPdfMenu", "entrer")),
    _f("tui/atelier_pdf_lots.py", "EcranLotsAPlanches._pas_encore",
       "CE_QUI_MANQUE_APRES_LES_LOTS", "QUAND_LES_REGLAGES",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursPdf.choisir_les_lots` injecte `continuer` depuis la 11.7.",
       rappel_optionnel=("EcranLotsAPlanches", "continuer")),
    _f("tui/atelier_pdf_reglages.py", "EcranReglagesDesPlanches._pas_encore",
       "CE_QUI_MANQUE_APRES_LES_REGLAGES", "QUAND_LA_CONFIRMATION",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursPdf.regler` injecte `continuer` ; `E5-3` est livre par le "
       "lot F de la 11.7 et le parcours les relie depuis le lot C.",
       rappel_optionnel=("EcranReglagesDesPlanches", "continuer")),
    _f("tui/atelier_pdf_calibration.py", "EcranMireReglages.continuer",
       "TITRE_DES_REGLAGES", "QUAND_LA_SUITE_DE_LA_MIRE",
       HORS_PRODUIT_RAPPEL,
       "`ouvrir_les_reglages` exige `sur_continuer` (sans defaut) et "
       "`ParcoursPdf.regler_la_mire` le passe : seul un ecran construit a nu "
       "atteint ce repli.",
       rappel_optionnel=("EcranMireReglages", "sur_continuer")),
    _f("tui/atelier_pdf_calibration.py", "EcranMireEnCours.interrompre",
       "NOM_DE_L_INTERRUPTION", "QUAND_LA_SUITE_DE_LA_MIRE",
       HORS_PRODUIT_RAPPEL,
       "`ouvrir_la_generation` exige `sur_interruption` (sans defaut) et "
       "`ParcoursPdf.generer_la_mire` le passe.",
       rappel_optionnel=("EcranMireEnCours", "sur_interruption")),
    _f("tui/atelier_pdf_parcours.py", "ParcoursPdf.entrer",
       "entree.nom", "getattr(entree, 'quand', '')",
       HORS_PRODUIT_CLE,
       "Repli d'une cle d'entree de menu inconnue -- une erreur de cablage, "
       "pas un etat du produit. Les deux cles du menu Pdf sont traitees.",
       mesuree_par="test_atelier_pdf_menu.py"),
    _f("tui/atelier_pdf_parcours.py", "ParcoursPdf.suivre",
       "suite", "atelier_pdf.QUAND_L_ATELIER_PDF",
       HORS_PRODUIT_CLE,
       "Repli d'une suite de `E5-5` qu'aucun module ne declare : les trois "
       "suites du resultat des planches portent chacune leur branche.",
       mesuree_par="test_couverture_des_suites.py"),
    _f("tui/atelier_pdf_parcours.py", "ParcoursPdf.suivre_apres_la_mire",
       "suite", "atelier_pdf.QUAND_L_ATELIER_PDF",
       HORS_PRODUIT_CLE,
       "Repli d'une suite de `E5-6e` qu'aucun module ne declare : les trois "
       "suites du resultat de la mire portent chacune leur branche.",
       mesuree_par="test_couverture_des_suites.py"),

    # -- Atelier Scan -------------------------------------------------------
    _f("tui/atelier_scan.py", "EcranScanMenu.entrer",
       "entree.nom", "entree.quand",
       HORS_PRODUIT_TEMOIN,
       "Branche des entrees marquees `construite=False`. Les deux entrees du "
       "menu Scan sont construites depuis le lot H de la 11.6."),
    _f("tui/atelier_scan.py", "EcranScanMenu.entrer",
       "entree.nom", "QUAND_LA_DETECTION",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursScan.ouvrir` injecte `entrer` depuis le lot F de la 11.5.",
       rappel_optionnel=("EcranScanMenu", "entrer")),
    _f("tui/atelier_scan.py", "EcranScanDepot._lancer_la_detection",
       "CE_QUI_MANQUE_POUR_DETECTER", "QUAND_LA_DETECTION",
       HORS_PRODUIT_RAPPEL,
       "`ParcoursScan.deposer` injecte `detecter` depuis le lot F de la 11.5.",
       rappel_optionnel=("EcranScanDepot", "detecter")),
    _f("tui/atelier_scan_parcours.py", "ParcoursScan.entrer",
       "entree.nom", "getattr(entree, 'quand', '')",
       HORS_PRODUIT_CLE,
       "Repli d'une cle d'entree de menu inconnue. Les deux cles du menu Scan "
       "-- detection et calibration -- sont traitees depuis le lot H.",
       mesuree_par="test_atelier_pdf_menu.py"),
    _f("tui/atelier_scan_resultat.py", "suivre",
       "suite", "app.QUAND_ARRIVENT_LES_ATELIERS",
       HORS_PRODUIT_CLE,
       "Repli d'une suite de `E3-8` qu'aucun module ne declare. C'est ce "
       "rappel qui portait `MQ-5` : `SUITE_EXPORTS` y a desormais sa branche.",
       mesuree_par="test_couverture_des_suites.py"),

    # -- Atelier Extraction et la chaine du produit -------------------------
    _f("tui/atelier_extraction.py", "EcranRushes._pas_encore",
       "ce_qui_manque", "",
       ATTEIGNABLE_REFUS,
       "Un site, TROIS chemins. Deux sont hors produit -- `ajouter` est "
       "court-circuite par `_preparer`, injecte, et `extraire`/`ecrire` sont "
       "injectes. Le troisieme EST atteignable : quatre des cinq motifs de "
       "`RefusDeDeclaration` y portent le message du coeur, faute d'ecran de "
       "refus cable. `execution.EcranRefus` existe et sert huit sites ; l'y "
       "router est un arbitrage produit, porte a `deferred-work.md`."),
    _f("tui/atelier_extraction_ecriture.py", "ParcoursExtraction.suivre",
       "suite", _ECHEANCE_ATELIERS,
       HORS_PRODUIT_CLE,
       "Repli d'une suite de `E2-5` qu'aucun module ne declare. C'est ce "
       "rappel qui portait `MQ-4` : `SUITE_PDF` y a desormais sa branche.",
       mesuree_par="test_couverture_des_suites.py"),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.entrer",
       'f"L\'atelier {entree.nom}"', _ECHEANCE_ATELIERS,
       HORS_PRODUIT_CLE,
       "Repli d'un nom d'atelier que `projet_lecture` ne declare pas. Les "
       "cinq entrees du menu sont cablees depuis le lot B5 de la 11.8, et le "
       "banc du menu mesure cette branche en ensemble EXACT, desormais vide.",
       mesuree_par="test_atelier_pdf_menu.py"),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.atelier_scan",
       'f"L\'atelier {projet_lecture.SCAN}"', _ECHEANCE_ATELIERS,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_l_atelier_scan` ; le produit n'a "
       "pas de version degradee.",
       rappel_optionnel=("ChaineReelle", "ouvrir_l_atelier_scan")),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.atelier_pdf",
       'f"L\'atelier {projet_lecture.PDF}"', _ECHEANCE_ATELIERS,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_l_atelier_pdf` (11.7, lot C).",
       rappel_optionnel=("ChaineReelle", "ouvrir_l_atelier_pdf")),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.atelier_exports",
       'f"L\'atelier {projet_lecture.EXPORTS}"', _ECHEANCE_ATELIERS,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_l_atelier_exports` (11.8, B5).",
       rappel_optionnel=("ChaineReelle", "ouvrir_l_atelier_exports")),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.extraire",
       "f'Les cadences de {rush_id}'", _ECHEANCE_ATELIERS,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_les_cadences` : choisir un rush "
       "ouvre `E2-2`, jamais le filet.",
       rappel_optionnel=("ChaineReelle", "ouvrir_les_cadences")),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.gestion_des_medias",
       "palier_projet.LIBELLES[palier_projet.ENTREE_MEDIAS]", _ECHEANCE_PORTE,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_la_gestion_des_medias` depuis le "
       "lot de la porte de l'inventaire (`MQ-8`, 2026-09-06).",
       rappel_optionnel=("ChaineReelle", "ouvrir_la_gestion_des_medias")),
    _f("tui/atelier_extraction_ecriture.py", "ChaineReelle.profil_par_defaut",
       "palier_projet.LIBELLES[palier_projet.ENTREE_PROFIL]", _ECHEANCE_PORTE,
       HORS_PRODUIT_RAPPEL,
       "`chaine_du_produit` injecte `ouvrir_le_profil_par_defaut` depuis le "
       "lot de l'ecran « Profil de calibration par defaut » du palier Projet "
       "(retour terrain d'Egan, 2026-09-06). Meme forme et meme motif que "
       "`gestion_des_medias` ci-dessus.",
       rappel_optionnel=("ChaineReelle", "ouvrir_le_profil_par_defaut")),
    _f("tui/atelier_extraction_ecriture.py",
       "ChaineReelle._pas_de_porte_vers_un_fichier",
       "issue.libelle", _ECHEANCE_PORTE,
       ATTEIGNABLE_ABSENCE,
       "ATTEIGNABLE : `ENTREE_RECONSTRUCTION` du palier Projet y mene au "
       "clavier, et elle SEULE depuis le 2026-09-06 -- `ENTREE_PROFIL` a "
       "gagne son ecran ce soir-la. `palier_projet.apercu_de_reconstruction` "
       "existe, mais exige des CHEMINS que seul `demo_vague_2.py` fournit : "
       "ce qui manque est un ecran de designation de fichier, qu'aucune story "
       "du depot ne porte. Aucun temoin nommable -- poser un nom que le depot "
       "n'a pas promis serait decoratif. Deja au registre de "
       "`deferred-work.md`."),

    # -- La coque et les ecrans partages ------------------------------------
    _f("tui/coque.py", "CoqueTui.descendre",
       "f'La suite de {self.screen.titre}'", "self.QUAND_ARRIVENT_LES_ATELIERS",
       HORS_PRODUIT_TEMOIN,
       "Repli de `descendre()` sans argument au DERNIER palier. Les trois "
       "paliers du produit traitent `enter` eux-memes ; le seul appelant qui "
       "descend sans argument depuis le fond est `PalierTemoin.on_key`, monte "
       "par `paliers_temoins()` -- le lanceur nu, jamais `chaine_du_produit`."),
    _f("tui/execution.py", "EcranResultat.choisir",
       "suite", _ECHEANCE_ATELIERS,
       HORS_PRODUIT_RAPPEL,
       "Repli commun des quatre ecrans de resultat quand `sur_suite` n'est pas "
       "injecte. Les quatre parcours l'injectent.",
       rappel_optionnel=("EcranResultat", "sur_suite")),

    # -- Le palier Projet : inventaire et suppression -----------------------
    _f("tui/projet_inventaire.py", "EcranInventaireDuProjet._pas_encore",
       "ce_qui_manque", "quand",
       ATTEIGNABLE_ABSENCE,
       "ATTEIGNABLE par UN seul chemin depuis le 2026-09-07, et il n'attend "
       "plus un ecran. `Ctrl+A` et `Ctrl+L` sont CABLES -- leur coeur et leur "
       "ecran existaient depuis la story 11.4 (`EcranRushes`, `E2-1e`, "
       "`E2-1f`, `E2-1d`), et `tui/projet_medias.py` ouvre la porte ; leurs "
       "deux `_pas_encore` sont desormais des replis hors produit, atteints "
       "seulement si un appelant construit l'inventaire sans `ajouter=` ni "
       "`relinker=`, ce que l'ouvreur fait toujours. Reste `Ctrl+D`, et ce "
       "qui lui manque n'est PAS un dessin : la mesure du 2026-09-07 ne trouve "
       "aucune commande de coeur qui inscrive au manifeste un objet deja "
       "present sur le disque -- `mmu project` n'a que `remove` et `add-rush`, "
       "laquelle declare depuis un FICHIER VIDEO. Il porte donc une echeance "
       "VIDE, comme `projet_suppression.ouvrir_la_suppression` "
       "(`EPIC11-ARB-260`) et pour le motif exact : annoncer « il arrive avec "
       "les ecrans de gestion des medias » a quelqu'un qui EST dans ces ecrans "
       "fait attendre ce qui est deja la. La phrase le dit elle-meme et se "
       "verifie a l'oeil. L'echeance est ici un ARGUMENT (`quand`) parce que "
       "les sites de cette methode ne demandent plus la meme chose. Aucun "
       "temoin nommable : ce qui manque est une commande de coeur qu'aucune "
       "story du depot ne porte -- deja a `deferred-work.md`, entree « Un lot "
       "absent du manifeste n'a AUCUNE issue de completion manuelle »."),
    _f("tui/projet_inventaire.py", "ouvrir_l_inventaire_du_projet",
       "CE_QUI_MANQUE_SANS_PROJET", _ECHEANCE_MEDIAS,
       ATTEIGNABLE_ABSENCE,
       "ATTEIGNABLE : le palier Projet peut etre monte sans dossier. Ce qui "
       "est nomme n'est pas un ecran a construire mais un etat -- « aucun "
       "projet n'est ouvert » --, et il n'a pas de destination a cabler. "
       "Aucun temoin : il n'y a rien qui puisse arriver un jour."),
    _f("tui/palier_profil_defaut.py", "ouvrir_le_profil_par_defaut",
       "CE_QUI_MANQUE_SANS_PROJET", "QUAND_LE_PROFIL_PAR_DEFAUT",
       ATTEIGNABLE_ABSENCE,
       "ATTEIGNABLE : le palier Projet peut etre monte sans dossier. **Meme "
       "site, meme famille et meme motif que son jumeau "
       "`ouvrir_l_inventaire_du_projet`** ci-dessus, et pour la meme raison : "
       "ce qui est nomme n'est pas un ecran a construire mais un ETAT -- "
       "« aucun projet n'est ouvert » --, et il n'a pas de destination a "
       "cabler. Ce qui manque est un projet, et l'echeance le dit : ouvrir un "
       "projet sur le palier Projet. Aucun temoin : il n'y a rien qui puisse "
       "arriver un jour."),
    _f("tui/projet_suppression.py", "ouvrir_la_suppression",
       "CE_QUI_MANQUE_A_LA_CIBLE_FINE.format(nature=nature)", "",
       HORS_PRODUIT_CLE,
       "CABLE le 2026-09-07, et le temoin qui le disait a fait son travail. Ce "
       "site etait `atteignable:absence` : `Suppr` sur un jeu de frames "
       "extraites, pour lequel le coeur n'avait aucun mot-cle. Le retour de "
       "terrain d'Egan du 2026-09-06 -- « on ne peut pas retirer d'un projet un "
       "jeu de frames extraites sans emporter autre chose » -- a produit "
       "`remove_project_element(frames_extraites=True)`, le temoin a resolu, ce "
       "banc a rougi, et la nature est sortie de "
       "`NATURES_SANS_CIBLE_FINE`, qui est desormais VIDE. Le site reste dans "
       "`src/`, donc au registre, mais il n'est plus atteint par aucune nature "
       "livree : c'est le MECANISME qui attend la prochaine nature sans cible "
       "fine, exactement comme une cle qu'aucun module ne declare. Aucun "
       "temoin : ce qui manquerait n'a pas de nom, puisque cette nature-la "
       "n'existe pas encore.",
       mesuree_par="test_suppression_depuis_la_tui.py"),
    # **Les DEUX filets de `ProjectMaintenanceError` sont SORTIS du registre le
    # 2026-09-06** (`EPIC11-ARB-260`), et c'est le registre lui-meme qui avait
    # nomme l'obstacle : « le router vers `execution.EcranRefus` demande de
    # decider quel CODE afficher -- `ProjectMaintenanceError` n'en porte pas
    # --, donc un arbitrage ». L'arbitrage est tranche, et le code se DERIVE du
    # nom de la classe levee (`projet_inventaire.code_du_refus`) plutot que de
    # se choisir. `ouvrir_la_suppression` et `reessayer_la_suppression` montent
    # desormais `refus_de_la_suppression`, donc ces deux sites ne sont plus des
    # filets : ils ne mènent plus a une absence.
    _f("tui/projet_suppression.py", "suivre",
       "suite", _ECHEANCE_MEDIAS,
       HORS_PRODUIT_CLE,
       "Repli d'une suite de `E6-3`/`E6-3b` qu'aucun module ne declare. Les "
       "quatre suites declarees portent leur branche depuis le lot des suites "
       "de la suppression.",
       mesuree_par="test_couverture_des_suites.py"),
)

#: L'ensemble ferme des echeances employees. Il n'est pas decoratif : une
#: echeance neuve doit s'y declarer, ce qui ramene un lecteur ici.
#:
#: **Il est ECRIT et non derive du registre, et c'est la campagne de mutation
#: qui l'a impose** (mutant `M18`, 2026-09-06). Ecrit comme
#: `frozenset(f.site.quand for f in REGISTRE)`, il ne pouvait par construction
#: jamais diverger de lui : la mesure etait une tautologie, et relacher son
#: egalite en inclusion ne changeait aucun verdict. Ecrit a plat, il mord --
#: une echeance neuve doit etre ajoutee ICI en plus du registre, et une
#: echeance qui cesse de servir doit en sortir.
#:
#: **Ce qu'il ne dit PAS** : qu'une echeance est encore vraie.
#: `QUAND_ARRIVENT_LES_ATELIERS` vaut « les ateliers de la vague 3 », livres, et
#: rien ici ne le voit -- voir la tete de fichier et `deferred-work.md`.
ECHEANCES_DECLAREES = frozenset({
    "",                                       # `EcranRushes._pas_encore`, seul
    "QUAND_LA_CONFIRMATION",
    "QUAND_LA_DETECTION",
    "QUAND_LA_GESTION_DES_MEDIAS",
    "QUAND_LA_SUITE_DE_LA_MIRE",
    "QUAND_LES_REGLAGES",
    "QUAND_LE_PARCOURS",
    "QUAND_LE_PROFIL_PAR_DEFAUT",
    "QUAND_L_ATELIER_PDF",
    "app.QUAND_ARRIVENT_LES_ATELIERS",
    "atelier_pdf.QUAND_L_ATELIER_PDF",
    "entree.quand",
    "getattr(entree, 'quand', '')",
    # `EcranInventaireDuProjet._pas_encore`, seul : ses sites ne demandent plus
    # la meme echeance depuis le 2026-09-07 -- `Suppr` sans rappel garde
    # `QUAND_LA_GESTION_DES_MEDIAS`, `Ctrl+D` n'en a aucune a annoncer.
    "quand",
    "self.QUAND_ARRIVENT_LES_ATELIERS",
    "self.QUAND_LA_PORTE_VERS_UN_FICHIER",
    "self.app.QUAND_ARRIVENT_LES_ATELIERS",
})


def _entrees_par_site() -> dict[Site, Filet]:
    return {f.site: f for f in REGISTRE}


# ---------------------------------------------------------------------------
# Volet 1 et 2 -- le recensement, confronte au registre dans les deux sens
# ---------------------------------------------------------------------------

def test_tout_site_de_filet_est_AU_REGISTRE():
    """Un filet neuf ne peut plus naitre en silence.

    C'est la porte par laquelle la cinquieme occurrence entrerait : un montage
    ajoute dans un module qui ne declare ni suite ni entree de palier, et dont
    la garde n'est pas un rappel optionnel, est invisible aux quatre frontieres
    existantes.
    """
    inconnus = sorted(str(s) for s in sites_du_paquet() - set(_entrees_par_site()))
    assert not inconnus, (
        "Ces montages de `EcranPasEncore` ne sont pas au REGISTRE. Un filet "
        "se declare avec la raison pour laquelle sa destination n'existe pas "
        "encore :\n  " + "\n  ".join(inconnus))


def test_aucune_entree_du_registre_n_est_PERIMEE():
    """Une entree sans site est le symptome meme qu'on chasse.

    Un filet retire -- parce que sa destination a ete livree et cablee --
    laisse une entree orpheline. La laisser masquerait le manque suivant :
    c'est la lecon des entrees perimees de `test_atteignabilite_des_ecrans.py`.
    """
    perimees = sorted(str(s) for s in set(_entrees_par_site()) - sites_du_paquet())
    assert not perimees, (
        "Ces entrees du REGISTRE ne correspondent plus a aucun montage. Si le "
        "filet a ete cable sur sa vraie destination, retirez l'entree :\n  "
        + "\n  ".join(perimees))


def test_la_cle_d_un_site_est_DISCRIMINANTE():
    """Deux montages distincts ne doivent pas se confondre sous la meme cle.

    Le registre est un dictionnaire indexe par site : deux sites egaux
    n'occuperaient qu'une entree, et l'un des deux sortirait de la mesure sans
    que rien ne rougisse. Deux fonctions du depot montent DEUX filets chacune
    (`EcranPdfMenu.entrer`, `EcranScanMenu.entrer`, `ouvrir_la_suppression`) :
    c'est le cas que cette mesure garde.
    """
    assert len(_entrees_par_site()) == len(REGISTRE), (
        "Deux entrees du REGISTRE portent le meme site.")
    assert len(sites_du_paquet()) == len(REGISTRE)


# ---------------------------------------------------------------------------
# Volet 3 -- chaque revendication est confrontee au produit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entree", REGISTRE, ids=lambda f: str(f.site))
def test_chaque_entree_porte_une_famille_et_un_MOTIF(entree: Filet):
    """Une entree sans raison est une entree qui classe le defaut au lieu de le dire."""
    assert entree.famille in FAMILLES, entree.famille
    assert len(entree.motif) >= 60, (
        f"Le motif de {entree.site} est trop court pour dire pourquoi la "
        f"destination n'existe pas : {entree.motif!r}")


@pytest.mark.parametrize(
    "entree", [f for f in REGISTRE if f.famille == HORS_PRODUIT_RAPPEL],
    ids=lambda f: str(f.site))
def test_un_filet_HORS_PRODUIT_repose_sur_un_rappel_que_le_produit_INJECTE(
        entree: Filet):
    """**La mesure anti-cinquieme-occurrence, cote cablage.**

    L'entree revendique que le site n'est atteint que si un rappel n'est pas
    injecte, et que le produit l'injecte. La revendication est confrontee a
    l'inventaire reel des injections de `src/`, lu a l'arbre syntaxique par
    `test_rappels_cables.rappels_injectes` -- **importe** et non recopie.

    Le jour ou quelqu'un decable ce rappel, le filet redevient atteignable dans
    le produit et ce banc rougit, en nommant le site. C'est exactement la panne
    du lot `E9` et des sept rappels de la famille `K1.1`, prise par son autre
    bout : la ils etaient decables et personne ne le disait ; ici la
    revendication qui les declare inoffensifs devient fausse et le dit.
    """
    assert entree.rappel_optionnel is not None, (
        f"{entree.site} : la famille {HORS_PRODUIT_RAPPEL} exige la paire "
        "`rappel_optionnel=(classe, mot-cle)`.")
    assert entree.rappel_optionnel in rappels_injectes(), (
        f"{entree.site} revendique que `{entree.rappel_optionnel[0]}."
        f"{entree.rappel_optionnel[1]}` est injecte par le produit. Il ne l'est plus : "
        "le filet est redevenu ATTEIGNABLE, et il faut soit recabler le "
        "rappel, soit reclasser l'entree.")


@pytest.mark.parametrize(
    "entree", [f for f in REGISTRE if f.famille == HORS_PRODUIT_CLE],
    ids=lambda f: str(f.site))
def test_un_filet_de_CLE_INCONNUE_nomme_la_frontiere_qui_le_tient(entree: Filet):
    """La revendication « aucune cle declaree ne tombe ici » se delegue, et se NOMME.

    Elle est tenue ailleurs -- par la couverture des suites, celle des entrees
    de palier, ou le banc du menu des ateliers. Ce banc-ci ne la redemontre pas
    (« un invariant ecrit a deux endroits n'est tenu nulle part ») : il exige
    que la frontiere soeur soit nommee et **existe**, si bien qu'un renommage
    ou une suppression de cette frontiere ramene un lecteur ici.
    """
    assert entree.mesuree_par, (
        f"{entree.site} : la famille {HORS_PRODUIT_CLE} exige `mesuree_par`.")
    soeur = Path(__file__).parent / entree.mesuree_par
    assert soeur.is_file(), (
        f"{entree.site} nomme `{entree.mesuree_par}`, qui n'existe pas.")


def _resoudre(chemin: str):
    """Rendre l'objet designe par un chemin pointe, ou `None`."""
    morceaux = chemin.split(".")
    for coupe in range(len(morceaux) - 1, 0, -1):
        try:
            module = importlib.import_module(".".join(morceaux[:coupe]))
        except ImportError:
            continue
        objet = module
        for nom in morceaux[coupe:]:
            objet = getattr(objet, nom, None)
            if objet is None:
                break
        if objet is not None:
            return objet
    return None


def temoin_resout(temoin: str) -> bool:
    """Vrai quand ce que le temoin declare ABSENT existe desormais.

    Deux formes, et deux seulement :

    * ``symbole:<chemin.pointe>`` -- le symbole doit rester introuvable ;
    * ``parametre:<chemin.pointe>:<nom>`` -- l'appelable doit exister, et ce
      parametre-la ne doit PAS figurer dans sa signature. Que l'appelable ait
      disparu n'est pas « le temoin resout » : c'est une erreur de registre, et
      elle se leve plutot que de passer en silence -- un temoin qui pointe dans
      le vide serait decoratif, ce qui est pire qu'absent.
    """
    forme, _, reste = temoin.partition(":")
    if forme == "symbole":
        return _resoudre(reste) is not None
    if forme == "parametre":
        chemin, _, parametre = reste.rpartition(":")
        appelable = _resoudre(chemin)
        if appelable is None:
            raise AssertionError(
                f"Le temoin `{temoin}` pointe sur `{chemin}`, introuvable. "
                "Un temoin qui ne mesure rien est pire qu'absent.")
        return parametre in inspect.signature(appelable).parameters
    raise AssertionError(f"Forme de temoin inconnue : {temoin!r}")


def test_AUCUNE_entree_du_registre_ne_porte_de_TEMOIN():
    """Le ZERO de la tete de fichier, en VALEUR plutot qu'en prose.

    **Pourquoi ce test en plus du parametre ci-dessous.** Sur un registre sans
    temoin, `parametrize` ne rend aucun cas : le test d'a cote devient un
    `skip`, et une frontiere sautee n'affirme rien. La tete de ce fichier
    affirme pourtant quelque chose -- « les entrees `ATTEIGNABLE_ABSENCE`
    restantes n'en portent AUCUN » --, et jusqu'ici cette affirmation etait de
    la prose que rien ne mesurait. C'est le meme geste que
    `test_AUCUNE_tolerance_d_abreviation_ne_SUBSISTE`, pose pour le meme motif.

    **Ce test n'INTERDIT rien**, et c'est ce qui le distingue de son modele :
    un temoin qui revient est un evenement legitime -- une absence qui gagne un
    nom mesurable. Il est une PASSATION, pas un verrou. Le jour ou il rougit,
    trois choses sont vraies en meme temps : une absence porte un nom, le banc
    parametre ci-dessous s'est reveille tout seul, et sa declaration
    d'endormissement dans `tests/unit/test_aucun_test_endormi.py` est devenue
    perimee -- ce que la frontiere de ce fichier-la rougira aussi, de son cote.
    Le message dit quoi retirer.

    Historique mesure : le seul temoin que ce registre ait jamais porte --
    `remove_project_element:frames_extraites` -- a resolu le 2026-09-07, et le
    filet a ete cable le meme jour. Le vide d'aujourd'hui est le RESULTAT de la
    mesure, pas son absence.
    """
    porteurs = [str(f.site) for f in REGISTRE if f.temoin]
    assert porteurs == [], (
        "une entree du registre porte a nouveau un temoin :\n"
        + "\n".join(f"  {site}" for site in porteurs)
        + "\n`test_le_TEMOIN_d_une_absence_n_existe_TOUJOURS_PAS` n'est donc "
          "plus endormi : retirer son entree de `ENDORMIS_DECLARES`, dans "
          "`tests/unit/test_aucun_test_endormi.py`, et mettre a jour la tete "
          "de ce fichier, qui annonce zero temoin.")


@pytest.mark.parametrize(
    "entree", [f for f in REGISTRE if f.temoin], ids=lambda f: str(f.site))
def test_le_TEMOIN_d_une_absence_n_existe_TOUJOURS_PAS(entree: Filet):
    """**La mesure anti-cinquieme-occurrence, cote destination.**

    C'est le seul volet qui attrape le defaut EXACT de `MQ-4`/`MQ-5` : la
    destination est livree, et le filet reste. Il ne l'attrape que la ou
    l'absence porte un nom.

    **ENDORMI depuis le 2026-09-07, et declare comme tel.** Plus aucune entree
    ne porte de temoin -- le seul qui ait jamais existe a resolu, et son filet
    a ete cable --, donc `parametrize` ne rend aucun cas et pytest saute avec
    « got empty parameter set ». Le skip est inscrit a `ENDORMIS_DECLARES`
    dans `tests/unit/test_aucun_test_endormi.py`, avec son motif ; le zero est
    tenu en valeur par `test_AUCUNE_entree_du_registre_ne_porte_de_TEMOIN`
    ci-dessus ; et l'outil `temoin_resout`, lui, reste mesure dans les deux
    sens sur un corpus de SYNTHESE. Une entree qui porte a nouveau un temoin
    reveille ce volet sans qu'on ait rien a rallumer.
    """
    assert not temoin_resout(entree.temoin), (
        f"{entree.site} : la destination existe desormais "
        f"(`{entree.temoin}`). Le filet est PERIME -- cablez-le, puis retirez "
        "son entree du REGISTRE.")


def test_toute_echeance_employee_est_DECLAREE():
    """L'ensemble des echeances est ferme : une echeance neuve ramene ici.

    Elle ne mesure pas qu'une echeance soit VRAIE -- rien ici ne peut le faire.
    Elle mesure qu'aucune ne s'ajoute sans qu'un lecteur relise le registre.
    """
    employees = {s.quand for s in sites_du_paquet()}
    assert employees == set(ECHEANCES_DECLAREES), (
        "Echeances non declarees : "
        f"{sorted(employees - set(ECHEANCES_DECLAREES))} ; "
        f"declarees sans emploi : {sorted(set(ECHEANCES_DECLAREES) - employees)}")


# ---------------------------------------------------------------------------
# Volet 4 -- le recenseur lui-meme, et la regle des fabriques
# ---------------------------------------------------------------------------

def test_le_recensement_voit_au_moins_ce_qui_existe():
    """Le volet qui empeche ce banc de passer en n'observant RIEN.

    Un recenseur casse verrait zero site, donc zero manque. Les bornes sont
    donc posees par le bas, sur le cardinal des sites ET sur celui des modules
    porteurs : un recenseur qui ne balaierait plus qu'un module passerait la
    premiere borne si ce module portait assez de sites.

    **Ce sont une SECONDE ligne, et la campagne de mutation l'a mesure**
    (`M17`, `M25`, 2026-09-06). Un recenseur vide fait deja rougir
    :func:`test_aucune_entree_du_registre_n_est_PERIMEE`, puisque les 36
    entrees deviennent orphelines : les bornes ne sont donc PAS ce qui attrape
    ce cas-la. Ce qu'elles attrapent seules, c'est le regime ou le recenseur et
    le registre se vident **ensemble** -- une reecriture qui ferait les deux du
    meme geste --, et la mesure de cette regression est ce qui les garde.
    """
    sites = sites_du_paquet()
    assert len(sites) >= 30, len(sites)
    assert len({s.module for s in sites}) >= 12
    assert len({s.rappel for s in sites}) >= 25


def _module_porteur(nom_de_classe: str) -> str:
    """Un module de synthese qui monte DEUX filets dans la MEME fonction.

    Les deux sont poses aux deux BORDS du corps -- premiere et derniere
    instruction --, et ils sont **distinguables** : les arguments different.
    C'est le point 4 de la regle des fabriques : la cible au milieu demasque un
    aiguillage fautif, elle ne demasque pas un balayage tronque.
    """
    return (
        "from .coque import EcranPasEncore\n\n\n"
        f"class {nom_de_classe}:\n"
        "    def entrer(self, entree):\n"
        "        self.app.descendre(EcranPasEncore('en tete', 'A'))\n"
        "        faire_autre_chose()\n"
        "        self.app.descendre(EcranPasEncore('en queue', 'B'))\n"
    )


def _module_muet(nom: str) -> str:
    """Un module qui CITE le filet sans le monter -- docstring et commentaire.

    C'est litteralement le texte qui a masque `MQ-4` et `MQ-5` : un grep y mord,
    un arbre syntaxique non.
    """
    return (
        '"""Ce module parle de EcranPasEncore sans en monter aucun.\n\n'
        "    Il ecrit meme EcranPasEncore('faux', 'faux') dans sa prose.\n"
        '    """\n'
        f"# EcranPasEncore('{nom}', 'commentaire')\n"
        f"MENTION_{nom.upper()} = \"EcranPasEncore\"\n"
    )


@pytest.mark.parametrize("rang", ["tete", "milieu", "queue"])
def test_le_recenseur_voit_un_porteur_a_CHAQUE_RANG(tmp_path: Path, rang: str):
    """Trois modules DISTINGUABLES, le porteur a chacun des trois rangs.

    Les noms sont choisis pour que l'ordre du balayage (`rglob` trie) soit
    `a_amont`, `b_milieu`, `c_aval` : le porteur se deplace d'un bout a l'autre
    sans que les deux autres changent de place.
    """
    noms = ["a_amont", "b_milieu", "c_aval"]
    porteur = {"tete": "a_amont", "milieu": "b_milieu", "queue": "c_aval"}[rang]
    paquet = tmp_path / "faux_paquet"
    paquet.mkdir()
    for nom in noms:
        corps = (_module_porteur("Ecran" + nom.title().replace("_", ""))
                 if nom == porteur else _module_muet(nom))
        (paquet / f"{nom}.py").write_text(corps, encoding="utf-8")

    sites = sites_du_paquet(paquet)
    assert {s.module for s in sites} == {f"{porteur}.py"}, (
        f"Le porteur au rang {rang} n'est pas vu seul.")
    assert {s.ce_qui_manque for s in sites} == {"'en tete'", "'en queue'"}, (
        "Les deux bords du corps de la fonction ne sont pas vus tous les deux.")


def test_le_recenseur_ne_mord_pas_sur_une_MENTION(tmp_path: Path):
    """Trois modules qui citent le filet, zero montage : le grep se tromperait."""
    paquet = tmp_path / "que_des_mentions"
    paquet.mkdir()
    for nom in ("a_amont", "b_milieu", "c_aval"):
        (paquet / f"{nom}.py").write_text(_module_muet(nom), encoding="utf-8")
    assert sites_du_paquet(paquet) == set()


def test_le_recenseur_rend_la_portee_la_plus_INTERIEURE(tmp_path: Path):
    """Une methode, pas sa classe -- et une fonction imbriquee, pas sa methode.

    Rendre la classe confondrait deux methodes de la meme classe sous une seule
    cle, ce qui ferait sortir un site de la mesure : c'est le mode de panne que
    `test_la_cle_d_un_site_est_DISCRIMINANTE` garde du cote du registre, et
    celui-ci du cote de l'outil.
    """
    paquet = tmp_path / "imbrique"
    paquet.mkdir()
    (paquet / "m.py").write_text(
        "class Dehors:\n"
        "    def methode(self):\n"
        "        def dedans():\n"
        "            app.descendre(EcranPasEncore('profond', 'Q'))\n"
        "        app.descendre(EcranPasEncore('surface', 'Q'))\n",
        encoding="utf-8")
    portees = {s.rappel for s in sites_du_paquet(paquet)}
    assert portees == {"Dehors.methode", "Dehors.methode.dedans"}


def test_le_recenseur_voit_la_forme_POINTEE(tmp_path: Path):
    """`coque.EcranPasEncore(...)` est le meme montage que `EcranPasEncore(...)`.

    Le depot n'emploie que la seconde forme aujourd'hui, derriere des imports
    differes. Une frontiere qui ne verrait pas la premiere serait contournable
    par un import de module au lieu d'un import de nom -- sans intention, et
    sans que rien ne le dise.
    """
    paquet = tmp_path / "pointe"
    paquet.mkdir()
    (paquet / "m.py").write_text(
        "from . import coque\n\n\n"
        "def ouvrir(app):\n"
        "    app.descendre(coque.EcranPasEncore('pointe', 'Q'))\n",
        encoding="utf-8")
    sites = sites_du_paquet(paquet)
    assert {s.ce_qui_manque for s in sites} == {"'pointe'"}


def test_le_temoin_de_PARAMETRE_mord_dans_les_deux_sens():
    """L'outil de temoin, mesure sur les deux verdicts plutot que sur un seul.

    Un test qui ne mesurerait que « le temoin ne resout pas » serait vert avec
    une fonction qui rend toujours faux -- c'est-a-dire avec un temoin
    decoratif, ce que ce banc existe pour empecher. Les deux sens sont donc
    joues : un parametre qui EXISTE fait resoudre, un parametre absent non.
    """
    reel = ("parametre:mixed_media_utility.project_maintenance."
            "remove_project_element:")
    assert temoin_resout(reel + "lot_id"), (
        "`lot_id` EXISTE dans la signature du coeur : le temoin doit resoudre.")
    # **`frames_extraites` etait le contre-exemple, il ne l'est plus** : le
    # coeur l'a gagne le 2026-09-07 (retour de terrain d'Egan du 2026-09-06),
    # et ce banc a rougi ici comme il devait. Le contre-exemple prend donc un
    # nom qu'aucune cible n'a jamais porte -- un nom que le depot n'a PAS
    # promis, pour qu'il ne soit pas rattrape par une livraison future comme
    # celui-ci vient de l'etre.
    assert temoin_resout(reel + "frames_extraites"), (
        "`frames_extraites=` EXISTE depuis le 2026-09-07 : le temoin resout.")
    assert not temoin_resout(reel + "cible_que_le_depot_n_a_jamais_promise")


def test_un_temoin_qui_pointe_dans_le_VIDE_se_leve():
    """Un temoin decoratif est pire qu'absent, donc il ne passe pas en silence."""
    with pytest.raises(AssertionError, match="introuvable"):
        temoin_resout("parametre:mixed_media_utility.project_maintenance."
                      "fonction_qui_n_existe_pas:x")


# ---------------------------------------------------------------------------
# Le drapeau que ce banc fait varier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_filet_rend_son_echeance_dans_les_DEUX_geometries(ascii_seul: bool):
    """L'echeance survit au repli ASCII, et la ligne est mesuree des deux cotes.

    « Une garde qui ne fait varier aucun de ses drapeaux ne mesure qu'un seul
    chemin » (`CLAUDE.md`, 2026-09-06, apres les onze bandeaux amputes de
    `coque.Palier`). Le filet est l'ecran que `F1` empile de n'importe ou : son
    texte se lit dans les deux geometries, et l'echeance est precisement ce
    qu'Egan a demande pour distinguer « pas encore fait » d'« abandonne ».

    La mesure porte sur :meth:`EcranPasEncore.lignes`, qui compose le texte
    avant toute mise en page : c'est la que l'echeance vit ou disparait. Le
    repli lui-meme est mesure ailleurs (`test_repli_ascii.py`) ; ce qui est
    tenu ici, c'est que **le drapeau ne change rien a ce que le filet DIT**.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    ecran = EcranPasEncore("Retirer un jeu de frames extraites du projet",
                           "les ecrans de gestion des medias du palier Projet")
    ecran.ascii_seul = ascii_seul          # le drapeau, pose des deux cotes
    lignes = ecran.lignes()
    assert lignes[-1] == ("Il arrive avec les ecrans de gestion des medias "
                          "du palier Projet.")
    assert "Retirer un jeu de frames extraites du projet" in lignes[0]


def test_un_filet_SANS_echeance_ne_ment_pas_par_une_ligne_vide():
    """Le volet symetrique du precedent : pas d'echeance, pas de ligne.

    Un site du registre n'en dit aucune (`EcranRushes._pas_encore`), et c'est
    delibere -- « une date inventee vaudrait moins que pas de date ». Mesurer
    l'echeance sans mesurer son absence laisserait passer une ligne
    « Il arrive avec . », qui dirait quelque chose de faux.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    lignes = EcranPasEncore("Ajouter le rush au projet").lignes()
    assert not any(ligne.startswith("Il arrive avec") for ligne in lignes)
