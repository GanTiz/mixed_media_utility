# -*- coding: utf-8 -*-
"""Story 11.9, lot A -- la DERIVATION du manuel des raccourcis (`EPIC11-ARB-196`).

Ce module ne dessine rien. Il rend, a partir du **paquet lui-meme**, ce qu'un
manuel des raccourcis a besoin de dire : quelles touches le produit annonce,
avec quels libelles, et sur quels ecrans. L'ecran qui l'affichera est un autre
lot ; le dessin ne conditionne rien ici.

**Pourquoi une derivation et non une table ecrite a la main.** Il n'existe
**aucun registre** des raccourcis dans ce depot : chaque ecran ecrit sa ligne
comme litteral, soit sur `Palier.raccourcis`, soit dans une constante de module
nommee `RACCOURCIS_*`. Au `baseline_commit` de la story (`a95d137a8`) cela fait
**59 constantes sur 24 modules**, plus les attributs de **60** classes de
palier, pour **119 entrees** et **51 lignes non vides distinctes**. Une table
recopiee a la main aurait vieilli des le premier ecran ajoute -- c'est la
famille de defaut que `CLAUDE.md` documente sous « les politiques de ce fichier
se MESURENT » et que `test_frontiere_cli.modules_de_coeur` a paye : une liste
explicite est verte le jour ou elle oublie un module.

**Le balayage est PARESSEUX, et c'est une contrainte d'architecture** (AC 3.5).
Vingt-cinq modules du paquet importent `coque`. Si ce module balayait le paquet
**a l'import**, et que `coque` l'importait au chargement, l'import serait
circulaire et la TUI ne demarrerait plus. Deux gestes, tous deux mesures par
`tests/unit/tui/test_manuel_derive.py` :

* aucun import de `mixed_media_utility.tui.*` au niveau de ce module -- ils sont
  tous dans le corps des fonctions ;
* aucun appel de balayage au niveau module : rien ne s'execute a l'import.

**Ce que ce module ne mesure pas, dit plutot que tu.** Il lit ce que le produit
**annonce**, pas ce qu'il **lie**. Une touche fonctionnelle mais non annoncee
(`Tab` sur le formulaire de calibration, synonyme non annonce par
`EPIC11-ARB-158`) n'y figure pas, et c'est voulu : un manuel des raccourcis dit
ce que l'interface promet. L'inverse -- une touche annoncee et inerte -- est le
finding `I8`, et ce sont d'autres bancs qui le tiennent.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

#: Le separateur d'items d'une ligne de raccourcis : **deux espaces au moins**
#: (`EPIC11-ARB-122`). Le depot le formalise deja dans
#: `test_majuscules_des_raccourcis._SEPARATEUR_D_ITEMS` ; il est repris ici
#: parce que la derivation vit desormais dans `src/` et qu'un banc n'est pas
#: une source pour du code de production. Les deux redactions sont identiques,
#: et un test les epingle a l'egalite plutot que de les laisser diverger.
SEPARATEUR_D_ITEMS = re.compile(r"\s{2,}")

#: Le prefixe des constantes de module qui portent une ligne de raccourcis.
#: C'est la **convention** du paquet, faute de registre -- voir le docstring de
#: :func:`lignes_de_raccourcis_du_paquet`.
PREFIXE_DES_CONSTANTES = "RACCOURCIS_"

#: Le module de l'ECRAN du manuel, **retire de la derivation** (et d'elle
#: seule -- le balayage, lui, le voit comme tous les autres).
#:
#: **Le defaut que cette exclusion ferme, et il a ete mesure.** Le lot C a
#: livre `ecran_manuel.RACCOURCIS_MANUEL` -- « → page suivante  ← page
#: precedente  Échap fermer ». Les fleches existaient deja sur un SEUL module
#: (`ecran_projet`), donc `partout=len(ateliers) > 1` les rangeait parmi les
#: raccourcis propres a un ecran. Le second module les a fait basculer, et la
#: derivation s'est mise a rendre **neuf** ouvreurs « partout » la ou la
#: maquette `T1-2` en range sept.
#:
#: **Ce n'est pas un ecart de cardinal, c'est un mensonge a l'operateur.**
#: `→` et `←` ne marchent PAS partout : ils tournent les pages du manuel, et
#: rien d'autre. Les annoncer « partout » sur la foi d'une ligne que le manuel
#: ecrit sur lui-meme, c'est laisser un ecran se decrire en decrivant le
#: produit -- exactement ce que la maquette refuse en ne portant ses propres
#: fleches dans AUCUN de ses deux blocs.
#:
#: **L'exclusion porte sur le MODULE, pas sur la ligne.** Viser la constante
#: (`RACCOURCIS_MANUEL`) laisserait rentrer la premiere ligne suivante ecrite
#: dans ce module sous un autre nom ; viser le module tient quel que soit le
#: nombre de lignes qu'il portera.
MODULE_DU_MANUEL = "ecran_manuel"


# ---------------------------------------------------------------------------
# Le balayage du paquet -- remonte des tests, sans y etre duplique
# ---------------------------------------------------------------------------

def classes_d_ecran() -> dict[str, type]:
    """Toutes les classes de palier du paquet, y compris non encore importees.

    **Le balayage ne passe pas par `__subclasses__`.** Deux defauts mesures :
    il ne voit que les classes deja importees -- ce qui rendait la garde
    dependante de l'ordre des fichiers de test -- et il voit les classes
    temoins fabriquees par les tests voisins, qui la faisaient rougir selon
    l'ordre d'execution (revue de vague 1, couche 1). Parcourir les MODULES du
    paquet est deterministe.

    **Ce corps vient de `tests/unit/tui/test_repli_ascii.py:31-55`, ou il vivait
    depuis la story 11.0.** Il est REMONTE ici, pas recopie : le banc le
    re-exporte desormais, parce que quatre bancs d'epic l'importent par ce
    chemin (`test_majuscules_des_raccourcis`, `test_sobriete_et_grille_extraction`,
    `test_paliers`, `test_arb140_passages_sans_q_quitter`) et qu'un second
    balayage divergerait du premier -- exactement ce que
    `test_arb140_passages_sans_q_quitter.py:48-53` ecrit : « on le REUTILISE
    plutot que d'en ecrire un second, qui divergerait ».
    """
    import importlib
    import inspect
    import pkgutil

    import mixed_media_utility.tui as paquet
    from mixed_media_utility.tui.coque import Palier

    trouvees: dict[str, type] = {}
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        for nom, objet in inspect.getmembers(module, inspect.isclass):
            if issubclass(objet, Palier) and objet.__module__.startswith(
                    paquet.__name__):
                trouvees[f"{objet.__module__}.{nom}"] = objet
    return trouvees


def lignes_de_raccourcis_du_paquet() -> dict[str, str]:
    """Toutes les lignes de raccourcis du paquet, portees par une CLASSE ou non.

    **Le balayage par classe ne suffit plus depuis la story 11.2.** Un ecran
    dont la ligne est **contextuelle** -- `EcranProjet` en a trois, une par zone
    (`DESIGN.md` section 4 : « elle ne montre que ce qui marche sur l'ecran
    courant ») -- ne peut en porter qu'une sur son attribut de classe. Les deux
    autres echappaient donc a la mesure de largeur **et** a celle du repli
    ASCII, c'est-a-dire aux deux garanties que `test_repli_ascii.py` existe pour
    tenir.

    Le remede est une convention mesurable plutot qu'une exception : toute
    ligne de raccourcis vit soit sur l'attribut de classe, soit dans une
    constante de module nommee `RACCOURCIS_*`. Les deux sont balayees ici.

    Meme remontee, meme motif que :func:`classes_d_ecran`.
    """
    import importlib
    import inspect
    import pkgutil

    import mixed_media_utility.tui as paquet

    trouvees = {f"{nom}.raccourcis": classe.raccourcis
                for nom, classe in classes_d_ecran().items()}
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        for nom, valeur in inspect.getmembers(module):
            if nom.startswith(PREFIXE_DES_CONSTANTES) and isinstance(valeur, str):
                trouvees[f"{module.__name__}.{nom}"] = valeur
    return trouvees


# ---------------------------------------------------------------------------
# `EPIC11-ARB-196` -- l'appartenance d'une ligne a un ECRAN, CREEE
# ---------------------------------------------------------------------------

#: Les quatre etages de l'appartenance, dans l'ordre ou ils sont essayes. Les
#: noms sont rendus par :func:`ecrans_par_ligne` pour que la mesure puisse dire
#: **par quel chemin** une ligne a ete rattachee -- une attribution dont on ne
#: sait pas d'ou elle vient ne se relit pas.
ETAGE_CLASSE = "classe"
ETAGE_SAUT = "saut"
ETAGE_MODULE = "module"
ETAGE_ORPHELINE = "orpheline"


def _noms_lus_par_bloc(source: str) -> tuple[dict[str, set[str]],
                                             dict[str, set[str]]]:
    """Les identifiants lus par chaque classe et par chaque nom de module.

    La lecture est faite **a l'AST, jamais au texte** : les docstrings de ce
    paquet nomment abondamment les constantes qu'elles expliquent, et un grep y
    mordrait -- c'est le defaut que `test_frontiere_cli.py` documente
    (« un grep de texte y mordrait et se ferait affaiblir a la premiere
    prose »).

    Rend deux tables : les noms lus dans le corps de chaque `class`, et les
    noms lus par chaque liaison de niveau module (fonction **ou** variable).
    La seconde est ce qui permet le saut d'un cran -- voir
    :func:`ecrans_par_ligne`.
    """
    arbre = ast.parse(source)
    par_classe: dict[str, set[str]] = {}
    par_nom_de_module: dict[str, set[str]] = {}
    for noeud in arbre.body:
        lus = {n.id for n in ast.walk(noeud) if isinstance(n, ast.Name)}
        if isinstance(noeud, ast.ClassDef):
            par_classe[noeud.name] = lus
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            par_nom_de_module.setdefault(noeud.name, set()).update(lus)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    par_nom_de_module.setdefault(cible.id, set()).update(lus)
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target,
                                                             ast.Name):
            par_nom_de_module.setdefault(noeud.target.id, set()).update(lus)
    return par_classe, par_nom_de_module


def ecrans_par_ligne() -> dict[str, tuple[tuple[str, ...], str]]:
    """A quel ECRAN appartient chaque ligne de raccourcis. `EPIC11-ARB-196`.

    **Cette donnee n'existe nulle part dans le depot, elle est CREEE ici.** Les
    59 constantes vivent dans des **modules**, pas rattachees a une classe
    d'ecran ; `ecran_projet` en porte sept a lui seul. Un manuel qui annonce
    « `A` ajouter une cadence » doit pourtant dire **ou** `A` repond, sans quoi
    il enseigne une touche sans son ecran.

    Quatre etages, essayes dans cet ordre, et le nom de l'etage retenu est rendu
    avec le resultat :

    1. **par la classe** -- la constante est nommee dans le corps d'une classe
       d'ecran du module (attribut de classe ou methode). C'est le cas de
       **45** des 59 constantes au `baseline_commit` ;
    2. **par un saut** -- la constante est nommee par une liaison de niveau
       module (fonction ou variable) que le corps d'une classe d'ecran nomme a
       son tour. Un seul cran, et il n'est pas theorique : il rattache les
       quatre lignes de l'explorateur, que `ecran_projet.raccourcis_de_l_explorateur()`
       compose pour deux ecrans, et les quatre lignes contextuelles du
       formulaire de calibration, que `atelier_scan_calibrate.PIED_PAR_CHAMP`
       (« une table plutot qu'une chaine de `if` ») distribue. **10** au
       `baseline_commit` ;
    3. **par le module** -- faute de mieux, tous les ecrans du module. **4** au
       `baseline_commit`, et les quatre tombent sur un module qui n'a **qu'un**
       ecran, donc sans perte de precision ;
    4. **orpheline** -- le module ne porte aucune classe d'ecran. **Zero** au
       `baseline_commit`, et l'etage existe quand meme : une ligne rendue par un
       module sans ecran ne doit pas faire tomber la derivation, elle doit se
       voir.

    **Ce que cette attribution ne sait pas faire, dit plutot que tu.** Elle
    rattache une constante a tout ecran qui la **nomme**, sans distinguer la
    branche qui l'emploie de celle qui l'ignore : `RACCOURCIS_MIRE_JUGEMENT` est
    rendue a ses deux ecrans, ce qui est juste, mais une constante nommee dans
    une branche morte le serait aussi. L'etage 3 est plus grossier encore. Les
    deux sont **ecrits** plutot que devines, et l'etage est rendu pour qu'une
    relecture sache lequel a servi.
    """
    import importlib
    import inspect
    import pkgutil

    import mixed_media_utility.tui as paquet

    par_module: dict[str, list[str]] = {}
    for nom, classe in classes_d_ecran().items():
        par_module.setdefault(classe.__module__, []).append(
            nom.rsplit(".", 1)[1])

    attribution: dict[str, tuple[tuple[str, ...], str]] = {}
    # Etage 0 -- un attribut de classe appartient a sa classe, sans detour.
    for nom in classes_d_ecran():
        attribution[f"{nom}.raccourcis"] = ((nom,), ETAGE_CLASSE)

    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        constantes = [nom for nom, valeur in inspect.getmembers(module)
                      if nom.startswith(PREFIXE_DES_CONSTANTES)
                      and isinstance(valeur, str)]
        if not constantes:
            continue
        ecrans = par_module.get(module.__name__, [])
        source = inspect.getsource(module)
        par_classe, par_nom_de_module = _noms_lus_par_bloc(source)
        for constante in constantes:
            directs = {classe for classe in ecrans
                       if constante in par_classe.get(classe, set())}
            etage = ETAGE_CLASSE
            if not directs:
                directs = {classe for classe in ecrans
                           for lu in par_classe.get(classe, set())
                           if constante in par_nom_de_module.get(lu, set())}
                etage = ETAGE_SAUT
            if not directs:
                directs, etage = set(ecrans), ETAGE_MODULE
            if not directs:
                etage = ETAGE_ORPHELINE
            attribution[f"{module.__name__}.{constante}"] = (
                tuple(sorted(f"{module.__name__}.{classe}"
                             for classe in directs)),
                etage)
    return attribution


# ---------------------------------------------------------------------------
# Le DOMAINE d'un module -- redaction unique, lue par le critere ET par le rendu
# ---------------------------------------------------------------------------

def noms_de_domaine() -> tuple[str, ...]:
    """Les noms de domaine que le produit ecrit, **lus de `projet_lecture`**.

    `ATELIERS` porte les quatre ateliers, `PROJET` le cinquieme domaine. Les
    recopier ici en ferait une seconde liste, qui divergerait au premier
    atelier ajoute -- meme motif que « la TUI lit la borne du coeur ».

    **Redaction unique, et elle est ICI** (revue de la story 11.9, couche 1
    `F1` et couche 2 `F2`, mutant `M07`). Ce calcul vivait dans
    `ecran_manuel`, c'est-a-dire **en aval** de la derivation qui en avait
    besoin : `manuel` ne peut pas importer `ecran_manuel` sans boucler, si
    bien que le critere `partout` se decidait sur le **module** pendant que
    l'affichage nommait l'**atelier**. Il descend donc au niveau ou il est
    consomme le plus tot ; `ecran_manuel`, qui importe deja `manuel`, le lit
    par ce chemin. L'import est dans le corps, comme tout import de paquet de
    ce module (AC 3.5, balayage paresseux).
    """
    from . import projet_lecture

    return projet_lecture.ATELIERS + (projet_lecture.PROJET,)


def atelier_lisible(module: str) -> str:
    """Le domaine qu'un module de la TUI porte. Le `(Extraction)` de `T1-2`.

    **Extraction positive** (AC 3.2) : la fonction dit ce qu'elle **garde** --
    le premier segment du nom de module qui EST un domaine du produit --, elle
    n'enumere jamais les prefixes qu'elle retire. Une liste de prefixes
    (`atelier_`, `ecran_`, `palier_`) serait a tenir a jour au premier module
    nomme autrement ; celle-ci n'a rien a rattraper.

    A defaut de domaine connu -- `execution`, `coque`, `ecran_manuel` --, on
    rend le dernier segment capitalise plutot que rien : un raccourci sans son
    lieu enseigne une touche sans son ecran.

    **Le repliement est le fait mesure qui fonde `F1`/`F2`** : neuf modules
    `atelier_pdf*` rendent tous `Pdf`, dix `atelier_scan*` rendent tous
    `Scan`, sept `atelier_exports*` rendent tous `Exports`, et `ecran_projet`
    comme `palier_projet` rendent tous deux `Projet`. Vingt-six des
    quarante-cinq modules du paquet se replient sur trois domaines : compter
    les modules et compter les domaines ne sont pas la meme mesure.
    """
    segments = module.rsplit(".", 1)[-1].split("_")
    connus = noms_de_domaine()
    for segment in segments:
        candidat = segment.capitalize()
        if candidat in connus:
            return candidat
    return segments[-1].capitalize()


# ---------------------------------------------------------------------------
# La derivation : ce qu'elle GARDE, jamais ce qu'elle retire (AC 3.2)
# ---------------------------------------------------------------------------

def items_d_une_ligne(ligne: str) -> tuple[tuple[str, str], ...]:
    """Les couples `(ouvreur, libelle)` d'une ligne de raccourcis.

    **Extraction positive** (AC 3.2, `EPIC11-ARB-196`) : la fonction dit ce
    qu'elle **garde** -- un item de deux mots au moins, dont le premier est
    l'ouvreur --, elle n'enumere jamais ce qu'elle retire. La seconde forme est
    a tenir a jour a chaque ligne neuve, la premiere n'a rien a rattraper.
    C'est le defaut mesure le 2026-09-01 et documente dans
    `test_sobriete_et_grille_extraction.py:88-110`.

    **Un item d'un seul mot n'est pas un raccourci** : c'est un **libelle de
    zone** (`Rushes`, `Explorateur`), qui ouvre la ligne de `E2-1` et celle de
    `E2-1b` sans nommer de touche. Meme lecture que
    `test_majuscules_des_raccourcis.noms_de_touche_annonces`.
    """
    items = []
    for item in SEPARATEUR_D_ITEMS.split((ligne or "").strip()):
        mots = item.split()
        if len(mots) < 2:
            continue
        items.append((mots[0], " ".join(mots[1:])))
    return tuple(items)


@dataclass(frozen=True)
class Entree:
    """Un ouvreur du manuel, avec tout ce que le paquet en dit.

    `libelles` porte **tous** les libelles que le produit associe a cet
    ouvreur, tries : `Échap` en a quinze au `baseline_commit` (`retour`,
    `ateliers`, `récents`, `menu Scan`...), et n'en garder qu'un ferait mentir
    le manuel sur quatorze ecrans.

    **Les trois collections sont TRIEES, et c'est un contrat, pas un hasard**
    (revue de la story 11.9, couche 1 `F5`, mutant `M11`). Elles se
    construisent en `set` : sans tri, le manuel changerait de rendu d'un
    lancement a l'autre, `PYTHONHASHSEED` n'etant pas fixe dans ce depot.
    Mesure : cinq graines rendaient **cinq** ordres distincts des quinze
    libelles d'`Échap`, sans qu'aucun test bouge.

    **`ateliers` porte des noms de MODULE, pas des domaines lisibles.** Le nom
    du champ est heritee de la premiere redaction et l'ecran le traverse par
    :func:`atelier_lisible` ; le critere :attr:`partout`, lui, se decide sur le
    domaine (couche 1 `F1`, couche 2 `F2`).
    """

    ouvreur: str
    libelles: tuple[str, ...]
    ecrans: tuple[str, ...]
    ateliers: tuple[str, ...]
    partout: bool


def entrees_du_manuel() -> tuple[Entree, ...]:
    """Le contenu du manuel, derive du paquet. AC 2.1, AC 3.1, AC 3.3.

    Rend les entrees **« partout » d'abord**, puis les **« propres a un
    ecran »**, chaque bloc trie par ouvreur -- c'est l'ordre des deux blocs de
    la maquette `T1-2`. La **pagination n'est pas ici** : elle est une
    consequence du cardinal rendu, et elle appartient a l'ecran.

    **Le partage entre les deux blocs se MESURE, il ne se decrete pas** : un
    ouvreur « vaut partout » quand ses ecrans porteurs s'etendent sur **plus
    d'un domaine** au sens de :func:`atelier_lisible` ; il est « propre »
    quand tous ses porteurs tiennent dans un seul.

    **Le domaine, et surtout pas le module** (revue de la story 11.9, couche 1
    `F1` et couche 2 `F2`, mutant `M07`). La premiere redaction posait
    l'equivalence « plus d'un atelier (plus d'un module du paquet) » : elle est
    **fausse**, et le rendu la contredisait deja puisqu'il annote ses
    raccourcis propres par le domaine. Le regime exact ou l'ecart mord a ete
    mesure : une ligne annoncee par `ecran_projet` **et** par `palier_projet`
    -- deux modules, un seul domaine `Projet` -- basculait sous « Raccourcis
    — partout », c'est-a-dire sous le seul bloc qui **n'ecrit pas** la
    parenthese du lieu. Le manuel promettait alors une touche partout sans
    meme pouvoir dire ou elle repond -- « ce n'est pas un ecart de cardinal,
    c'est un mensonge a l'operateur », comme le dit deja
    :data:`MODULE_DU_MANUEL` du meme defaut pris par l'autre bout. Le paquet
    n'en portait aucune instance : la zone etait vide **par accident**, et
    remonter la borne de `> 1` a `> 2` ne faisait rougir aucun des 584 tests.

    Ce critere n'est pas choisi au hasard, il est **confronte deux fois** :

    * la maquette `T1-2` range sept ouvreurs sous « Raccourcis — partout »
      (`↑↓`, `Entrée`, `Espace`, `Tab`, `Échap`, `F1`, `q`) ; la derivation en
      rend exactement sept, les memes ;
    * elle annote ses raccourcis propres par leur **atelier** -- « `a` ajouter
      une cadence **(Extraction)** » --, pas par leur ecran. C'est donc
      l'atelier qui separe, et c'est ce qui fait tomber `O revoir` du bon cote :
      il est annonce par **deux** ecrans (`EcranChoixDesCadences`,
      `EcranPreviz`) mais d'un **seul** atelier.

    **Le module du manuel est RETIRE de cette derivation** (voir
    :data:`MODULE_DU_MANUEL`) : ses propres fleches de pagination ne valent que
    dans le manuel, et la maquette `T1-2` ne les range dans aucun de ses deux
    blocs. Le balayage, lui, continue de le voir comme tous les autres.

    **L'alternative ecartee, et pourquoi.** Se fonder sur `CoqueTui.BINDINGS`
    -- les trois touches que la coque lie globalement -- aurait ete plus direct,
    mais aurait range `⏎`, `↑↓`, `Espace` et `Tab` parmi les raccourcis propres
    a un ecran, contre le dessin approuve : la coque n'en lie que trois quand la
    maquette en annonce sept.
    """
    attribution = ecrans_par_ligne()
    par_ouvreur: dict[str, tuple[set[str], set[str]]] = {}
    for cle, ligne in lignes_de_raccourcis_du_paquet().items():
        if MODULE_DU_MANUEL in cle.split("."):
            # Le manuel ne se decrit pas lui-meme -- voir MODULE_DU_MANUEL.
            # **L'appartenance se lit sur les SEGMENTS**, pas par un
            # `rsplit(".", 2)` : ce module porte DEUX cles de formes
            # differentes -- `ecran_manuel.RACCOURCIS_MANUEL` (constante) et
            # `ecran_manuel.EcranManuel.raccourcis` (attribut de classe) --,
            # et un decoupage par la fin rend `EcranManuel` sur la seconde.
            # Premiere redaction mesuree, et elle laissait passer la moitie.
            continue
        ecrans, _etage = attribution.get(cle, ((), ETAGE_ORPHELINE))
        for ouvreur, libelle in items_d_une_ligne(ligne):
            libelles, porteurs = par_ouvreur.setdefault(ouvreur, (set(), set()))
            libelles.add(libelle)
            porteurs.update(ecrans)

    entrees = []
    for ouvreur, (libelles, porteurs) in par_ouvreur.items():
        modules = {ecran.rsplit(".", 2)[-2] for ecran in porteurs}
        # `partout` se decide sur le DOMAINE, jamais sur le module -- voir
        # :func:`atelier_lisible` et le docstring ci-dessus.
        domaines = {atelier_lisible(module) for module in modules}
        entrees.append(Entree(ouvreur=ouvreur,
                              libelles=tuple(sorted(libelles)),
                              ecrans=tuple(sorted(porteurs)),
                              ateliers=tuple(sorted(modules)),
                              partout=len(domaines) > 1))
    return tuple(sorted(entrees, key=lambda e: (not e.partout, e.ouvreur)))


def est_une_lettre(ouvreur: str) -> bool:
    """Un ouvreur est-il une LETTRE : **un seul caractere, alphabetique**.

    **Ecrite ici, et une seule fois** (revue de la story 11.9, couche 1 `F11`,
    mutant `M12`). Cette borne vivait a deux endroits -- ci-dessous et une
    recopie dans `test_manuel_derive.py` --, si bien que le volet 2 de l'AC 3.3
    comparait deux ensembles construits **par la meme regle ecrite deux fois** :
    muter la production seule ne pouvait pas les faire diverger. Le test etait
    vert par **absence de temoin**, pas par mesure ; le paquet n'annonce que
    quatre lettres (`A`, `O`, `X`, `Q`) et aucun ouvreur qui distingue les deux
    moities du predicat.

    Les temoins qui manquaient au paquet vivent desormais dans
    `tests/unit/tui/test_revue_11_9_lot_e5.py` : `"A"`, `"e"` et `"é"` d'un
    cote ; `"Ab"`, `"F1"`, `"1"`, `"⏎"`, `"+"` et `""` de l'autre. Chacun
    echoue par **un** cote du `and`, ce qu'aucun ouvreur reel ne fait.
    """
    return len(ouvreur) == 1 and ouvreur.isalpha()


def lettres_du_manuel() -> dict[str, tuple[str, ...]]:
    """Les LETTRES annoncees par le manuel, et les ecrans de chacune. AC 3.3.

    Une lettre est un ouvreur **d'un seul caractere alphabetique** -- la meme
    lecture que `test_majuscules_des_raccourcis.lettres_annoncees`, a laquelle
    un test epingle cette fonction plutot que de la laisser diverger.

    Au `baseline_commit`, le paquet entier n'en annonce que **quatre** : `A`,
    `O`, `X` et `Q`. `e` et `r`, que la maquette `T1-2` cite, **n'existent
    plus** -- `EPIC11-ARB-68` les a remplaces par `Tab` et `Ctrl+R`.
    """
    return {entree.ouvreur: entree.ecrans for entree in entrees_du_manuel()
            if est_une_lettre(entree.ouvreur)}
