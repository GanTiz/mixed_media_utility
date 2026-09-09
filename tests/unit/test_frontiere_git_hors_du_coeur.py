# -*- coding: utf-8 -*-
"""Story 11.13 (`EPIC11-ARB-199`) -- le suivi par git n'est plus une affaire du coeur.

Egan, le 2026-09-03, verbatim : « Le suivi par git n'est pas un sujet. [...]
l'utilitaire n'a pas vocation a traiter des fichiers au sein de depots git.
**Il faut supprimer cette ligne ET cette logique du coeur.** »

Trois frontieres negatives, chacune avec son volet de morsure :

1. **aucun module de `src/mixed_media_utility/` ne construit un appel de
   sous-processus a `git`** ;
2. **aucun n'porte la signature de pointeur Git LFS** -- et celle-la est un
   litteral d'OCTETS, ce qui est tout le piege de cette story ;
3. **le mot `IRRECUPERABLES` a disparu du produit**.

**Mesure a l'AST, jamais au grep, et ce n'est pas du zele.** Les docstrings de
`project_maintenance` et de `cli` racontent le `git rm -r` du 2026-08-27 qui a
detruit des frames irrecuperables : c'est le motif qui justifie l'existence
d'une suppression propre, et il **survit** au retrait. Un grep textuel rendrait
rouge une histoire qu'on veut conserver, puis se ferait affaiblir.

**Le lecteur d'AST est celui du depot, repris et non recopie**
(`tests/unit/tui/outils_frontiere.py`, story 11.0) : deux predicats pour un seul
interdit divergeraient, et c'est le module couvert par le plus laxiste des deux
qui passerait.

**La sous-chaine `git` mord sur du francais innocent -- mesure, pas suppose.**
Sur les 133 modules du paquet, six portent `git` en sous-chaine d'une chaine de
code et **quatre sont innocents** : `scan_crop.py` et `scan_write.py` par
« legitime », `scan_manifest.py` et `relink.py` par « s'a-git » -- oui, le mot
« agit » contient `git`. Le texte d'aide de `--master` de `cli.py` dit
« legitimement » et **reste**. La frontiere se pose donc sur une **egalite en
tete d'argv**, jamais sur une appartenance de sous-chaine : sans quoi elle nait
rouge sur quatre modules qui n'ont rien fait, et le reflexe suivant serait de
l'affaiblir.
"""

import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import ast  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "src") not in sys.path:
    sys.path.insert(0, str(RACINE / "src"))
# Le lecteur d'AST du depot, **repris et non recopie** : deux predicats pour un
# seul interdit divergeraient, et c'est le module couvert par le plus laxiste
# des deux qui passerait (`tests/unit/tui/outils_frontiere.py`, story 11.0).
if str(RACINE / "tests" / "unit" / "tui") not in sys.path:
    sys.path.insert(0, str(RACINE / "tests" / "unit" / "tui"))

from outils_frontiere import (  # noqa: E402
    _plie_une_concatenation,
    chaines_d_octets,
    chaines_de_code,
    chaines_de_docstring,
    chaines_recomposees,
    octets_recomposes,
)

SOURCES = RACINE / "src" / "mixed_media_utility"


def _plie_une_chaine(noeud):
    """La concatenation litterale que ce noeud vaut, ou ``None``.

    Le plieur du socle, **repris et non recopie** : deux plieurs pour un seul
    interdit divergeraient, et c'est le plus laxiste des deux qui laisserait
    passer.
    """
    return _plie_une_concatenation(noeud, str)

#: Plancher du balayage, **jamais une egalite** (AC 4.4) : le paquet grandit a
#: chaque story (131 modules au `baseline_commit` de la fiche, 133 au moment ou
#: ce banc est ecrit), et une egalite ferait rougir la story suivante sans rien
#: dire de git.
#:
#: Porte de 100 a 125 sur mesure de revue (couche 1, finding F8) : a 100 contre
#: 133 modules, **33 modules pouvaient disparaitre** sans que la garde bronche.
#: Le plancher reste un plancher -- il ne rougit que si le paquet **retrecit**.
PLANCHER_DE_MODULES = 125

#: Ce que le plancher a le droit de laisser disparaitre, au pire : la moitie du
#: paquet. Sans cette borne, `PLANCHER_DE_MODULES = 1` est un mutant survivant
#: (couche 2, finding F5, mutant `M15`) -- le plancher est alors une garde qui
#: ne garde rien. Un facteur 2 laisse le paquet doubler avant de mordre.
FACTEUR_DE_PLANCHER_ADMIS = 2

#: Les modules qui portaient la logique retiree. Nommes plutot que devines :
#: une frontiere qui balaierait « le paquet » cesserait de dire **lequel** a
#: rouvert l'interdit, et un balayage casse serait vert sur tout.
MODULES_TEMOINS = ("project_maintenance.py", "cli.py")

#: Les quatre modules qui portent `git` en sous-chaine **sans rien avoir fait**.
#: Mesures au `baseline_commit`, ils sont la borne qui interdit d'ecrire cette
#: frontiere en sous-chaine.
MODULES_INNOCENTS = (
    "scan_manifest.py",   # « il s'agit d'une planche PERIMEE »
    "relink.py",          # « qu'il s'agit d'un flux video exploitable »
    "scan_crop.py",       # « pas une page legitime »
    "scan_write.py",      # « C'est une issue legitime, pas un echec »
)

#: Le cinquieme innocent, **fabrique**, et c'est lui qui porte la mesure.
#:
#: Les quatre modules reels ci-dessus portent tous `git` **au milieu** d'une
#: phrase (« legitime », « s'agit »). Ils n'innocentent donc que les formes qui
#: inspectent la chaine ENTIERE. Mesure de la revue (couche 3, finding F3 ;
#: couche 2, finding F8) : sur les trois affaiblissements que le docstring de
#: la borne promet d'attraper, **deux survivent** -- `"git" in tete` et
#: `"git" in jetons[0]` --, et un quatrieme, `jetons[0].startswith("git")`,
#: survit aussi. Aucun module reel de `src/` ne peut jouer ce role : il
#: faudrait qu'une tete d'argv ou un premier mot y contienne `git`.
#:
#: Il porte aussi les litteraux d'OCTETS innocents que `src/` n'a pas -- un
#: seul litteral d'octets existe dans tout le paquet, et il est vide. La
#: frontiere LFS etait donc verte **par accident de corpus** (couche 2,
#: finding F4) : ecrite en sous-chaine `b"git"`, elle declarait fautif
#: `b"digit"` et `b"legitime"`, c'est-a-dire la forme meme que la story refuse
#: et argumente du cote `str`.
MODULE_INNOCENT_FABRIQUE = (
    '# Rien ici n\'appelle git, et pourtant tout y ressemble.\n'
    'ARGV = ["gitignore", "--check", "."]\n'
    'COMMANDE = "gitlab-runner exec shell build"\n'
    'HOTE = "github.com/GanTiz/mixed_media_utility"\n'
    'AIDE = "un lot porte legitimement plusieurs masters"\n'
    'MESSAGE = "il s\'agit d\'une planche PERIMEE"\n'
    'SEPARATEUR = b"digit"\n'
    'MOTIF = b"legitime"\n'
    'MIROIR = b"gitlab"\n'
    'RECUPERABLE = "les fichiers restent RECUPERABLES depuis la corbeille"\n'
)

#: Les marqueurs qui font un pointeur Git LFS, en minuscules.
#:
#: La frontiere mesurait `git` (couche 1, finding F3) -- c'est-a-dire un nom
#: d'hote, un detail. Le discriminant REEL d'un pointeur LFS est le prefixe
#: `version https://` : aucun autre fichier binaire ne commence ainsi, et
#: `b"version https://"` seul reintroduisait `_est_pointeur_lfs` a l'identique
#: fonctionnel en restant vert. `oid sha256:` est la seconde ligne du pointeur,
#: et le second discriminant possible.
#:
#: Aucun de ces trois marqueurs n'apparait dans `src/` -- mesure du
#: 2026-09-05, sur les 133 modules, chaines de code ET litteraux d'octets.
MARQUEURS_DE_POINTEUR_LFS = (
    "version https://",
    "git-lfs",
    "oid sha256",
)

#: Le mot interdit, **par sa racine** et non par sa graphie exacte.
#:
#: `IRRECUPERABLE` au singulier reintroduisait l'avertissement sans faire
#: rougir la frontiere (couche 1, finding F4, mutant `M8`). La racine couvre
#: les deux nombres pour un caractere de moins. Ce qu'elle ne couvre toujours
#: pas -- l'avertissement REFORMULE, sans le mot -- demande un banc de
#: comportement et part en dette.
RACINE_DU_MOT_INTERDIT = "IRRECUPERABLE"


def modules_du_coeur() -> list[Path]:
    """Tous les modules du paquet, decouverts et non tenus a la main.

    Une liste ecrite a la main se perime : la story 11.8 a mesure que les deux
    coeurs les plus recents du depot etaient hors de la frontiere qui existe
    pour les tenir, et que la frontiere etait verte.
    """
    return sorted(SOURCES.rglob("*.py"))


def modules_du_coeur_par_un_AUTRE_parcours() -> set[Path]:
    """Le meme ensemble, par `os.walk` -- un parcours qui ne partage RIEN.

    Le second temoin du balayage, et il n'existe que pour cela : `rglob` et
    `os.walk` descendent l'arborescence par deux implementations distinctes,
    donc une troncature glissee dans l'une ne se glisse pas dans l'autre.
    Mesure de la revue (couche 2, finding F5) : `sorted(...)[1:]` et
    `sorted(...)[:-1]` etaient **deux mutants survivants** du garde-fou --
    parce que les deux temoins nommes sont aux index 2 et 70 sur 133, donc
    aucune cible n'etait a un bord.

    C'est le point 4 de la regle des fabriques applique au balayage : la
    difference des deux ensembles **nomme** le module perdu, quel que soit le
    bord ou il se trouvait. Un cardinal ne l'aurait pas nomme, et deux
    cardinaux egaux peuvent recouvrir deux ensembles differents.
    """
    trouves = set()
    for dossier, _sous_dossiers, fichiers in os.walk(SOURCES):
        for fichier in fichiers:
            if fichier.endswith(".py"):
                trouves.add(Path(dossier) / fichier)
    return trouves


def _nom_d_executable(jeton: str) -> str:
    """Le nom d'executable que ce jeton designe, sans chemin ni extension.

    `git`, `/usr/bin/git`, `git.exe` et `C:\\Program Files\\Git\\bin\\git.exe`
    designent **le meme programme**. La frontiere mesurait la troisieme
    orthographe et laissait passer les trois autres : mesure de la revue
    (couche 2, finding F2 ; couche 1, finding F5), `/usr/bin/git` et `git.exe`
    sont **l'appel exact retire par le lot B**, au nom d'executable pres, et
    ils passaient tous les deux. Windows est une cible reelle du depot
    (`scripts/install-mmu.ps1`), donc `git.exe` n'est pas une hypothese.

    Le predicat reste une **EGALITE**, ce que l'AC 4.1 exige : il normalise
    avant de comparer, il n'elargit pas en sous-chaine. Mesure sur les 133
    modules : `gitignore`, `legitimement`, `s'agit`, `digit`, `github.com` et
    `/usr/bin/gitk` se normalisent tous en eux-memes, aucun en `git`.
    """
    nom = PureWindowsPath(PurePosixPath(jeton.strip()).name).name
    if nom.lower().endswith(".exe"):
        nom = nom[:-4]
    return nom.lower()


def _est_l_executable_git(jeton: str) -> bool:
    """Ce jeton designe-t-il l'executable `git` ? Par egalite, apres normalisation."""
    return _nom_d_executable(jeton) == "git"


def tetes_d_argv(chemin) -> list[str]:
    """Les tetes d'argv litterales construites par ce module.

    Toute liste ou tuple litteral du code dont le premier element est une
    chaine : c'est la forme sous laquelle un argv se pose
    (`subprocess.run(["git", "ls-files", ...])`). Le predicat ne regarde pas
    **qui** est appele, seulement ce qui est construit -- une garde qui
    exigerait de reconnaitre `subprocess.run` se contournerait en aliasant le
    module, ce qu'un balayage de la forme ne permet pas.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"), filename=str(chemin))
    tetes = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.List, ast.Tuple)) and noeud.elts:
            premier = noeud.elts[0]
            if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
                tetes.append(premier.value)
            else:
                # Une tete ASSEMBLEE (`["gi" + "t", ...]`) n'est pas un
                # `ast.Constant` : sans ce pli, elle passe. Mesure de la revue,
                # mutant `M3` de la couche 1.
                plie = _plie_une_chaine(premier)
                if plie is not None:
                    tetes.append(plie)
    return tetes


def appels_de_sous_processus_git(chemin) -> list[str]:
    """Ce module lance-t-il `git` ? Par EGALITE en tete, jamais par sous-chaine.

    Deux formes, parce qu'un sous-processus s'ecrit de deux facons :

    * un **argv** liste ou tuple dont la tete vaut exactement ``"git"`` ;
    * une **commande** en une seule chaine (`shell=True`) dont le premier jeton
      vaut exactement ``"git"``.

    Dans les deux cas c'est une egalite : « legitimement », « il s'agit » et
    « git-lfs.github.com » ne sont pas des invocations de git, et une frontiere
    qui les declarerait fautifs serait affaiblie des sa premiere lecture.
    L'egalite porte sur le **nom d'executable** (:func:`_est_l_executable_git`)
    et non sur son orthographe : `/usr/bin/git` et `git.exe` sont le meme
    appel, et ils passaient tous les deux (couche 2, finding F2).

    **Chaque constat porte le volet qui l'a trouve** (`argv:` ou `shell:`), et
    ce n'est pas de la decoration. Mesure de la revue (couche 2, finding F3) :
    le volet argv pouvait etre **eteint** sans qu'un seul test rougisse, parce
    qu'aucun banc ne mesurait sa contribution propre -- une tete d'argv `"git"`
    est aussi un litteral `str` que le volet chaine ramasse, donc le volet
    chaine couvrait l'argv en entier. L'etiquette est ce qui rend les deux
    volets observables separement, et donc mesurables separement.
    """
    fautifs = [f"argv:{tete}" for tete in tetes_d_argv(chemin)
               if _est_l_executable_git(tete)]
    # Les chaines ASSEMBLEES comptent autant que les litterales : `"gi" + "t"`
    # est le meme appel (couche 1, mutant `M3`).
    for chaine in list(chaines_de_code(chemin)) + list(chaines_recomposees(chemin)):
        jetons = chaine.split()
        if jetons and _est_l_executable_git(jetons[0]):
            fautifs.append(f"shell:{chaine}")
    return fautifs


def signatures_de_pointeur_lfs(chemin) -> list[str]:
    """Les litteraux de ce module qui portent un marqueur de POINTEUR LFS.

    **C'est ici que la story se joue**, et c'est ici que la premiere redaction
    de la frontiere mesurait autre chose que ce qu'elle promettait.

    Ce qui a change, sur trois mesures de la revue :

    * elle mesurait le mot `git`, pas le concept (couche 1, finding F3).
      `b"version https://"` et `b"oid sha256:"` reintroduisent
      `_est_pointeur_lfs` **a l'identique fonctionnel** et restaient verts. Le
      discriminant reel d'un pointeur LFS est le prefixe `version https://` --
      le nom d'hote `git-lfs.github.com` n'en est qu'un detail. La frontiere
      mesurait le detail et laissait passer le discriminant ;
    * elle ne lisait que les OCTETS (couche 2, finding F1). Ecrite
      `"version https://git-lfs...".encode("ascii")`, la meme constante n'est
      un litteral d'octets pour personne, et le volet `str` ne la voyait pas
      non plus -- il testait `jetons[0] == "git"` quand la chaine commence par
      `version`. **Les deux lecteurs se croisaient sans se recouvrir**, et le
      trou etait au milieu. Elle lit donc les deux, plus ce que le code
      assemble par `+` ;
    * elle etait ecrite en SOUS-CHAINE `b"git"`, sans borne d'innocence
      (couche 2, finding F4) : `b"digit"` et `b"legitime"` la rendaient rouge.
      C'est mot pour mot la forme que la story refuse du cote `str`, et elle
      n'etait verte que par accident de corpus -- `src/` ne porte qu'un seul
      litteral d'octets, et il est vide. Les marqueurs sont plus etroits que
      `git` **et** plus justes : c'est l'artefact qu'on interdit, pas une
      sequence de trois lettres.

    Chaque constat porte son volet (`octets:` ou `code:`), pour la meme raison
    qu'en :func:`appels_de_sous_processus_git` : deux volets qu'un seul
    predicat couvre ne se mesurent pas separement.
    """
    fautifs = []
    for octets in list(chaines_d_octets(chemin)) + list(octets_recomposes(chemin)):
        minuscules = octets.lower()
        if any(marqueur.encode("ascii") in minuscules
               for marqueur in MARQUEURS_DE_POINTEUR_LFS):
            fautifs.append(f"octets:{octets!r}")
    for chaine in list(chaines_de_code(chemin)) + list(chaines_recomposees(chemin)):
        minuscules = chaine.lower()
        if any(marqueur in minuscules for marqueur in MARQUEURS_DE_POINTEUR_LFS):
            fautifs.append(f"code:{chaine!r}")
    return fautifs


def porte_le_mot_irrecuperables(chemin) -> list[str]:
    """Le mot `IRRECUPERABLES` dans une chaine de CODE, docstrings exclus.

    Docstrings exclus a dessein : si un jour un docstring racontait l'incident
    du 2026-08-27 en employant le mot, il ne serait pas pour autant imprime a
    l'operateur. Ce qui est interdit, c'est de le **dire** a l'ecran.

    Par la RACINE du mot et non par sa graphie : `IRRECUPERABLE` au singulier
    etait un mutant survivant (couche 1, finding F4, mutant `M8`). Les chaines
    assemblees comptent aussi -- `"IRRECUPER" + "ABLES"` etait la sonde `P4` de
    la couche 2, survivante elle aussi.
    """
    candidates = list(chaines_de_code(chemin)) + list(chaines_recomposees(chemin))
    return [c for c in candidates if RACINE_DU_MOT_INTERDIT in c]


def porte_le_mot_irrecuperables_MEME_EN_DOCSTRING(chemin) -> list[str]:
    """L'AC 4.2 **a la lettre** : le mot nulle part dans le module.

    L'AC dit « le litteral ``IRRECUPERABLES`` n'apparait dans **aucun module**
    de ``src/`` » ; :func:`porte_le_mot_irrecuperables` ne mesure que les
    chaines de CODE. La couche 3 (finding F4) a nomme l'ecart et personne ne le
    mesurait : une reintroduction du mot dans un docstring passait verte alors
    que l'AC, telle qu'ecrite, l'interdit.

    **Les deux lectures cohabitent plutot que l'une remplace l'autre**, et
    chacune mesure une chose differente :

    * l'etroite est la frontiere de PRODUIT -- ce qui est interdit, c'est de
      **dire** le mot a l'ecran, et un docstring n'est jamais imprime ;
    * la large est la lecture LITTERALE de l'AC, et elle est **verte au
      2026-09-05** sur les 133 modules du paquet. C'est la mesure qui l'etablit
      et non un argument : aucun docstring de ``src/`` ne porte la racine.

    **Ce que cette lecture large ne CONTREDIT PAS, et c'est ce qui la rend
    posable.** Le livrable « l'histoire du ``git rm -r`` du 2026-08-27 survit
    dans les docstrings » est intact : le seul docstring de ``src/`` qui
    raconte l'incident avec ce mot est ``project_inventory.py`` (« a detruit
    des frames irrecuperables »), et il l'ecrit en MINUSCULES. La racine etant
    comparee telle quelle, la prose survit et seule la clameur du produit
    tombe. Le lot precedent avait nomme un conflit entre l'AC et le livrable ;
    la mesure dit qu'il n'y en a pas dans ``src/`` -- il n'existe que pour un
    temoin FABRIQUE qui hurle le mot dans un docstring, et ce temoin-la est
    mesure separement ci-dessous.

    Ce qu'elle ne voit pas, dit plutot que tu : le mot en minuscules (meme
    angle mort que l'etroite), et l'avertissement REFORMULE sans le mot
    (mutant ``M9``, en dette -- il demande un banc de comportement).
    """
    candidates = (list(chaines_de_code(chemin))
                  + list(chaines_recomposees(chemin))
                  + list(chaines_de_docstring(chemin)))
    return [c for c in candidates if RACINE_DU_MOT_INTERDIT in c]


# ---------------------------------------------------------------------------
# AC 4.4 -- le balayage a bien VU quelque chose
# ---------------------------------------------------------------------------


def test_le_balayage_de_la_frontiere_git_a_bien_VU_le_paquet():
    """AC 4.4 : deux inclusions entre deux ensembles vides sont vertes.

    Un plancher **et** la presence nominative des deux modules qui portaient la
    logique : un chemin de paquet errone rendrait toutes les frontieres de ce
    banc vertes sur tout, ce qui est le seul mode de panne qu'une frontiere
    negative ne voit pas d'elle-meme.

    **Le garde-fou lui-meme n'etait pas mesure** : sur ses quatre modes de
    panne, quatre mutants survivaient (couche 2, finding F5). Ce qui a ete
    ajoute, mode par panne :

    * une **troncature en tete ou en queue** du balayage -- les deux temoins
      nommes sont aux index 2 et 70 sur 133, donc aucune cible n'etait a un
      bord, et une troncature ne perdait que des modules innocents. C'est le
      point 4 de la regle des fabriques, un cran au-dessus d'une fabrique :
      le second parcours (`os.walk`) **nomme** le module perdu, quel que soit
      son bord, et les deux bords sont en plus mesures nominativement ;
    * un **plancher effondre** (`PLANCHER_DE_MODULES = 1`) -- une garde qui ne
      garde rien. Le plancher se mesure desormais contre le cardinal reel ;
    * des **temoins vides** (`MODULES_TEMOINS = ()`) -- une boucle sur un
      tuple vide n'assert rien. Le tuple se mesure contre un litteral ecrit a
      la main.
    """
    modules = modules_du_coeur()
    balayes = set(modules)
    independants = modules_du_coeur_par_un_AUTRE_parcours()

    # --- le second parcours, qui NOMME ce qui manque ------------------------
    perdus = independants - balayes
    surnumeraires = balayes - independants
    assert not perdus and not surnumeraires, (
        "le balayage de la frontiere et un parcours independant du meme paquet "
        "ne voient pas les memes modules -- l'un des deux est tronque",
        {"vus par os.walk et pas par le balayage": sorted(m.name for m in perdus),
         "vus par le balayage et pas par os.walk": sorted(
             m.name for m in surnumeraires)})

    # --- une cible a CHAQUE BORD, decouverte et non ecrite a la main --------
    tete, queue = min(independants), max(independants)
    assert tete in balayes, (
        "le PREMIER module du balayage trie manque -- troncature en tete", tete)
    assert queue in balayes, (
        "le DERNIER module du balayage trie manque -- troncature en queue", queue)
    assert modules[0] == tete and modules[-1] == queue, (
        "les bords du balayage ne sont pas ceux du parcours independant",
        {"bords balayes": (modules[0].name, modules[-1].name),
         "bords independants": (tete.name, queue.name)})

    # --- le plancher est un plancher, pas un decor --------------------------
    assert len(modules) >= PLANCHER_DE_MODULES, [m.name for m in modules]
    assert PLANCHER_DE_MODULES * FACTEUR_DE_PLANCHER_ADMIS >= len(modules), (
        f"PLANCHER_DE_MODULES={PLANCHER_DE_MODULES} laisserait disparaitre plus "
        f"de la moitie des {len(modules)} modules du paquet sans broncher : "
        "ce n'est plus une garde. Le remonter, ou assumer le facteur.")

    # --- les temoins nommes existent, et le tuple qui les nomme aussi -------
    assert set(MODULES_TEMOINS) == {"project_maintenance.py", "cli.py"}, (
        "MODULES_TEMOINS ne nomme plus les deux modules qui portaient la "
        "logique retiree : un tuple vide ferait de la boucle ci-dessous une "
        "assertion sur rien", MODULES_TEMOINS)
    noms = {m.name for m in modules}
    for temoin in MODULES_TEMOINS:
        assert temoin in noms, (temoin, sorted(noms))


def test_le_SECOND_parcours_du_balayage_n_est_PAS_le_premier():
    """Anti-tautologie : deux parcours qui partagent leur code ne mesurent rien.

    Le garde-fou ci-dessus tient parce que ses deux parcours sont
    **independants** : une troncature glissee dans l'un ne se glisse pas dans
    l'autre. Recrire `modules_du_coeur_par_un_AUTRE_parcours` en
    `set(modules_du_coeur())` rendrait la comparaison vraie par construction et
    ferait revivre les deux mutants de bord, **sans qu'un test rougisse** --
    c'est le mode de panne que la section 6.2 de la politique appelle
    endemique : un test qui passe sans mesurer ce qu'il dit mesurer.

    Mesure a l'AST plutot qu'a l'intention, sur ce banc lui-meme : le second
    parcours n'appelle ni le premier ni sa primitive, et descend l'arborescence
    par la sienne.
    """
    arbre = ast.parse(Path(__file__).read_text(encoding="utf-8"),
                      filename=__file__)
    corps = [n for n in ast.walk(arbre)
             if isinstance(n, ast.FunctionDef)
             and n.name == "modules_du_coeur_par_un_AUTRE_parcours"]
    assert len(corps) == 1, "le second parcours a disparu de ce banc"
    appeles = set()
    for noeud in ast.walk(corps[0]):
        if isinstance(noeud, ast.Call):
            cible = noeud.func
            if isinstance(cible, ast.Name):
                appeles.add(cible.id)
            elif isinstance(cible, ast.Attribute):
                appeles.add(cible.attr)
    assert "modules_du_coeur" not in appeles, (
        "le second parcours appelle le premier : la comparaison du garde-fou "
        "devient vraie par construction et ne mesure plus rien", sorted(appeles))
    assert "rglob" not in appeles, (
        "le second parcours emploie la primitive du premier", sorted(appeles))
    assert "walk" in appeles, (
        "le second parcours ne descend plus l'arborescence lui-meme",
        sorted(appeles))


# ---------------------------------------------------------------------------
# AC 4.1 -- aucun sous-processus `git`, aucune signature LFS
# ---------------------------------------------------------------------------


def test_aucun_module_du_coeur_n_appelle_un_sous_processus_git():
    """AC 4.1 : « l'utilitaire n'a pas vocation a traiter des fichiers au sein
    de depots git » (`EPIC11-ARB-199`).

    Rouge au `baseline_commit` sur `project_maintenance.py`, qui construit
    `["git", "ls-files", "-z", "--", *noms]`.
    """
    fautifs = {chemin.name: appels_de_sous_processus_git(chemin)
               for chemin in modules_du_coeur()
               if appels_de_sous_processus_git(chemin)}
    assert fautifs == {}, fautifs


def test_aucun_module_du_coeur_ne_porte_la_signature_de_pointeur_LFS():
    """AC 4.1, volet `bytes` : un pointeur LFS est un artefact git.

    Rouge au `baseline_commit` sur `project_maintenance.py:70`. C'est la
    frontiere qu'un balayage `str` seul rendrait verte sans rien mesurer.
    """
    fautifs = {chemin.name: signatures_de_pointeur_lfs(chemin)
               for chemin in modules_du_coeur()
               if signatures_de_pointeur_lfs(chemin)}
    assert fautifs == {}, fautifs


def test_les_quatre_modules_INNOCENTS_ne_sont_JAMAIS_declares_fautifs():
    """La borne qui interdit de reecrire cette frontiere en sous-chaine.

    Ces quatre modules portent `git` dans une chaine de code -- par
    « legitime » et par « s'agit » -- et n'ont rien fait. Le jour ou quelqu'un
    remplacera l'egalite par un `in`, c'est ce test qui rougira, et pas les
    quatre autres qui deviendraient inexplicablement rouges sans que personne
    ne sache pourquoi.
    """
    noms = {m.name: m for m in modules_du_coeur()}
    for innocent in MODULES_INNOCENTS:
        chemin = noms.get(innocent)
        # Un `noms[innocent]` tombait en `KeyError` le jour d'un renommage --
        # `relink.py` et `scan_write.py` sont des modules vivants (couche 2,
        # finding F10). Le message que le banc sait deja dire etait sous la
        # mauvaise assertion.
        assert chemin is not None, (
            f"{innocent} n'existe plus dans le paquet : la borne ne mesure "
            "plus rien, il faut lui trouver un autre temoin")
        assert any("git" in c.lower() for c in chaines_de_code(chemin)), (
            f"{innocent} ne porte plus `git` en sous-chaine : la borne ne mesure "
            "plus rien, il faut lui trouver un autre temoin")
        assert appels_de_sous_processus_git(chemin) == [], innocent
        assert signatures_de_pointeur_lfs(chemin) == [], innocent


def test_le_cinquieme_innocent_FABRIQUE_est_epargne_par_les_TROIS_frontieres(tmp_path):
    """La borne d'innocence que `src/` ne peut pas fournir.

    Les quatre modules reels portent `git` **au milieu** d'une phrase. Ils
    n'innocentent donc que les affaiblissements qui inspectent la chaine
    ENTIERE, et la mesure le dit : sur les trois formes du `in` que la borne
    promet d'attraper, deux survivaient (couche 3, finding F3), un
    affaiblissement en prefixe survivait aussi (couche 2, finding F8), et le
    volet d'octets n'avait **aucune** borne d'innocence -- il declarait fautifs
    `b"digit"` et `b"legitime"` (couche 2, finding F4).

    Ce module de synthese porte, chacun a la place ou il mord :

    * `git` en tete d'argv (`"gitignore"`) -- ferme `"git" in tete` ;
    * `git` en premier jeton d'une commande (`"gitlab-runner ..."`) -- ferme
      `"git" in jetons[0]` **et** `jetons[0].startswith("git")` ;
    * `git` dans des litteraux d'OCTETS innocents -- ferme `b"git" in octets` ;
    * la racine `RECUPERABLE` sans le `IR` -- ferme un elargissement du mot
      interdit a sa racine trop courte.

    Rien de tout cela n'existe dans `src/`, et rien ne peut y etre pose : la
    borne reelle et la borne fabriquee se completent, elles ne se remplacent
    pas.
    """
    innocent = _ecrire(tmp_path, "innocent_fabrique.py", MODULE_INNOCENT_FABRIQUE)
    assert appels_de_sous_processus_git(innocent) == [], (
        "la frontiere git mord sur un module qui n'appelle pas git")
    assert signatures_de_pointeur_lfs(innocent) == [], (
        "la frontiere LFS mord sur des litteraux d'octets innocents")
    assert porte_le_mot_irrecuperables(innocent) == [], (
        "la frontiere du mot interdit mord sur `RECUPERABLES`")


# ---------------------------------------------------------------------------
# AC 4.2 -- le mot `IRRECUPERABLES` a quitte le produit
# ---------------------------------------------------------------------------


def test_le_mot_IRRECUPERABLES_n_est_plus_imprime_par_le_produit():
    """AC 4.2 : « il n'apparait que quand c'est vrai » n'est plus tenable.

    `projects/` n'etant plus versionne, tout fichier tombait en
    `NATURE_NON_SUIVI` par construction : l'avertissement se declenchait
    **toujours**, donc il n'avertissait plus de rien. Rouge au
    `baseline_commit` sur `cli.py:2202`, unique occurrence.
    """
    fautifs = {chemin.name: porte_le_mot_irrecuperables(chemin)
               for chemin in modules_du_coeur()
               if porte_le_mot_irrecuperables(chemin)}
    assert fautifs == {}, fautifs


def test_le_mot_IRRECUPERABLES_est_absent_MEME_DES_DOCSTRINGS():
    """AC 4.2 lue A LA LETTRE -- « aucun module », pas « aucune chaine de code ».

    Couche 3, finding F4. L'AC interdit le litteral dans **aucun module** de
    ``src/`` ; la frontiere ci-dessus n'en mesure que les chaines de CODE, et
    **rien ne mesurait la difference** : le mutant ``M25`` -- le mot glisse
    dans le docstring reel de ``project_remove_command`` -- laissait le banc a
    ``16 passed``. L'ecart entre ce que l'AC exige et ce que la frontiere
    mesure vivait en prose ; il vit desormais dans deux mesures.

    **Pourquoi les deux lectures cohabitent au lieu que l'une remplace
    l'autre** : l'etroite est la frontiere de produit (ce qui compte est de ne
    pas le DIRE a l'ecran) et la large est l'AC au mot pres. Le lot precedent
    avait nomme un CONFLIT -- honorer l'AC interdirait le livrable « l'histoire
    du ``git rm -r`` survit dans les docstrings ». La mesure le renverse : le
    seul docstring de ``src/`` qui raconte l'incident avec ce mot l'ecrit en
    minuscules (``project_inventory.py``, « a detruit des frames
    irrecuperables »), donc la lecture large est **verte** sans rien couter au
    livrable. Le conflit n'existe que pour un temoin fabrique, et celui-la est
    mesure a part.
    """
    fautifs = {chemin.name: porte_le_mot_irrecuperables_MEME_EN_DOCSTRING(chemin)
               for chemin in modules_du_coeur()
               if porte_le_mot_irrecuperables_MEME_EN_DOCSTRING(chemin)}
    assert fautifs == {}, fautifs

    # Le garde-fou de la mesure elle-meme : un predicat qui ne lirait aucun
    # docstring serait vert ici pour la mauvaise raison, et cette AC-la ne
    # mesurerait plus rien. Le temoin est le docstring qui raconte l'incident.
    inventaire = SOURCES / "project_inventory.py"
    proses = chaines_de_docstring(inventaire)
    assert any("irrecuperables" in prose for prose in proses), (
        "le lecteur de docstrings ne rend plus la prose qui raconte le "
        "`git rm -r` du 2026-08-27 : la lecture large ci-dessus serait verte "
        "parce qu'elle ne lit rien, pas parce que le mot est absent")


# ---------------------------------------------------------------------------
# AC 4.3 -- les volets de morsure, un par frontiere
# ---------------------------------------------------------------------------


def _ecrire(tmp_path, nom, source):
    chemin = tmp_path / nom
    chemin.write_text(source, encoding="utf-8")
    return chemin


def test_la_frontiere_git_MORD_sur_un_module_fautif_forme_str(tmp_path):
    """AC 4.3, forme `str` : trois facons d'appeler git, toutes attrapees.

    Sans ce volet, un balayage casse, un chemin de paquet errone ou un
    `ast.walk` qui ne visite rien rendraient la frontiere verte sur tout --
    defaut paye **deux fois** sur la 11.8, ou « deux gardes neuves ont survecu
    a leur premiere reinjection ».
    """
    for source in (
        'import subprocess\nsubprocess.run(["git", "ls-files", "-z"])\n',
        'import subprocess\nsubprocess.run(("git", "status"), check=False)\n',
        'import subprocess\nsubprocess.run("git ls-files -z", shell=True)\n',
        'ARGV = ["git", "checkout", "--", "."]\n',
    ):
        fautif = _ecrire(tmp_path, "fautif.py", source)
        assert appels_de_sous_processus_git(fautif) != [], source


#: Les reintroductions que la revue a mesurees VERTES : l'appel exact retire,
#: au nom d'executable pres ou a l'assemblage pres. Chacune est ici avec le
#: volet qui doit la nommer.
REINTRODUCTIONS_DE_L_APPEL_GIT = (
    ('import subprocess\nsubprocess.run(["/usr/bin/git", "ls-files", "-z"])\n',
     "argv", "couche 2 F2 / couche 1 F5, sonde P1 -- chemin absolu"),
    ('import subprocess\nsubprocess.run(["git.exe", "ls-files", "--", "a"])\n',
     "argv", "couche 2 F2, sonde P3 -- portage Windows (install-mmu.ps1)"),
    ('import subprocess\nARGV = ["C:\\\\Program Files\\\\Git\\\\bin\\\\git.exe", "status"]\n',
     "argv", "couche 2 F2 -- chemin absolu Windows"),
    ('import subprocess\nsubprocess.run("/usr/bin/git ls-files -z", shell=True)\n',
     "shell", "couche 2 F2 -- chemin absolu en commande shell"),
    ('import subprocess\n_EXE = "gi" + "t"\nsubprocess.run([_EXE, "ls-files"])\n',
     "shell", "couche 1 F5, mutant M3 -- executable assemble"),
)


def test_la_frontiere_git_MORD_sur_les_REINTRODUCTIONS_mesurees_vertes(tmp_path):
    """AC 4.3, volet de non-regression : les cinq formes qui passaient.

    Une frontiere negative ne vaut que par ce qu'elle attrape a la
    **reintroduction** -- c'est le seul moment ou elle servira. La revue a
    mesure huit reintroductions reelles dans `src/` : trois attrapees, quatre
    laissees passer, deux faux positifs. Les formes laissees passer sont ici,
    une par une, avec le volet qui doit les nommer.

    Elles ne sont pas des evasions adversaires : `/usr/bin/git` est le reflexe
    de durcissement de qui ne veut pas dependre du `PATH`, `git.exe` celui du
    portage Windows -- et Windows est une cible reelle du depot.
    """
    for source, volet, origine in REINTRODUCTIONS_DE_L_APPEL_GIT:
        fautif = _ecrire(tmp_path, "reintroduction.py", source)
        constats = appels_de_sous_processus_git(fautif)
        assert constats != [], (origine, source)
        assert any(c.startswith(f"{volet}:") for c in constats), (
            f"attrape, mais pas par le volet {volet} -- le volet qui devait la "
            f"voir est muet", origine, constats)


def test_le_volet_ARGV_de_la_frontiere_git_MORD_SEUL(tmp_path):
    """AC 4.3 : le volet argv, mesure **en propre** et non par sa somme.

    Mesure de la revue (couche 2, finding F3) : le volet argv pouvait etre
    **eteint** (`tete == "__git__"`) ou **affaibli en sous-chaine**
    (`"git" in tete`) sans qu'un seul test rougisse. La cause n'etait pas un
    oubli mais une structure : une tete d'argv `"git"` est aussi un litteral
    `str` que le volet chaine ramasse, donc le volet chaine couvrait l'argv en
    entier et le volet argv ne couvrait rien en propre.

    Le volet de morsure existant ne pouvait pas le voir : il faisait tomber ses
    quatre sources dans le meme predicat et attestait que **la fonction** mord,
    jamais que **chacun de ses deux volets** mord. C'est pourtant la seule
    chose qu'un volet de morsure existe pour attester -- symetrique exact du
    volet `bytes`, qui lui est correctement isole.
    """
    fautif = _ecrire(tmp_path, "fautif_argv.py",
                     'import subprocess\nsubprocess.run(["git", "ls-files"])\n')
    constats = appels_de_sous_processus_git(fautif)
    assert [c for c in constats if c.startswith("argv:")] == ["argv:git"], (
        "le volet ARGV ne nomme plus l'appel qu'il est seul a voir en position",
        constats)
    assert [c for c in constats if c.startswith("shell:")] == ["shell:git"], (
        "le volet CHAINE ne nomme plus l'appel", constats)


def test_le_volet_SHELL_de_la_frontiere_git_MORD_SEUL(tmp_path):
    """AC 4.3 : le volet chaine, mesure en propre lui aussi.

    Le pendant du test ci-dessus, sur une commande en une seule chaine
    (`shell=True`) : aucune liste litterale, donc le volet argv n'a rien a
    voir et le volet chaine est seul.
    """
    fautif = _ecrire(tmp_path, "fautif_shell.py",
                     'import subprocess\n'
                     'subprocess.run("git ls-files -z", shell=True)\n')
    constats = appels_de_sous_processus_git(fautif)
    assert [c for c in constats if c.startswith("argv:")] == [], constats
    assert constats == ["shell:git ls-files -z"], (
        "le volet CHAINE ne mord plus seul", constats)


def test_la_frontiere_LFS_MORD_sur_un_module_fautif_forme_bytes(tmp_path):
    """AC 4.3, forme `bytes` -- **le volet qui compte le plus ici**.

    `chaines_de_code` ne rend que des `str` : une frontiere ecrite sans ce
    volet serait verte AVANT le retrait comme apres, c'est-a-dire qu'elle ne
    mesurerait rien. Le module fabrique ci-dessous ne porte le mot dans
    **aucune** chaine `str`.
    """
    for source in (
        'SIGNATURE = b"version https://git-lfs.github.com/spec/v1"\n',
        'def lit(f):\n    return f.read(512).startswith(b"version https://git-lfs")\n',
    ):
        fautif = _ecrire(tmp_path, "fautif_bytes.py", source)
        constats = signatures_de_pointeur_lfs(fautif)
        assert constats != [], source
        assert all(c.startswith("octets:") for c in constats), (
            "attrape, mais pas par le volet OCTETS", source, constats)
        assert appels_de_sous_processus_git(fautif) == [], (
            "la frontiere `str` ne voit PAS les octets : c'est tout le motif de "
            "ce volet")


#: Les reintroductions de `_est_pointeur_lfs` que la revue a mesurees VERTES.
#: Chacune est la fonction retiree, au comportement pres identique.
REINTRODUCTIONS_DU_POINTEUR_LFS = (
    ('SIGNATURE = b"version https://"\n'
     'def lit(f):\n    return f.read(512).startswith(SIGNATURE)\n',
     "octets", "couche 1 F3, mutant M5 -- le discriminant REEL du pointeur"),
    ('def lit(f):\n    return b"oid sha256:" in f.read(512)\n',
     "octets", "couche 1 F3, mutant M6 -- la seconde ligne du pointeur"),
    ('SIGNATURE = b"version " + b"https://git-lfs.github.com/spec/v1"\n',
     "octets", "octets assembles par `+`"),
    ('SIGNATURE = "version https://git-lfs.github.com/spec/v1".encode("ascii")\n'
     'def lit(f):\n    return f.read(512).startswith(SIGNATURE)\n',
     "code", "couche 2 F1, sonde P2 -- la constante ecrite en `str` puis encodee"),
    ('_HOTE = "git-lfs.github.com"\n', "code", "couche 2 F1 -- le nom d'hote seul"),
)


def test_la_frontiere_LFS_MORD_sur_les_REINTRODUCTIONS_mesurees_vertes(tmp_path):
    """AC 4.3, volet de non-regression du pointeur LFS.

    Les deux lecteurs se croisaient sans se recouvrir : `chaines_d_octets` ne
    voyait pas les `str`, `chaines_de_code` ne voyait pas les octets, et le
    volet `str` de la frontiere git testait `jetons[0] == "git"` quand la
    constante commence par `version`. Le trou etait au milieu, et
    `"...".encode()` est la forme qu'ecrit naturellement qui veut garder la
    constante lisible -- pas une evasion.
    """
    for source, volet, origine in REINTRODUCTIONS_DU_POINTEUR_LFS:
        fautif = _ecrire(tmp_path, "reintroduction_lfs.py", source)
        constats = signatures_de_pointeur_lfs(fautif)
        assert constats != [], (origine, source)
        assert any(c.startswith(f"{volet}:") for c in constats), (
            f"attrape, mais pas par le volet {volet}", origine, constats)


def test_la_frontiere_LFS_EPARGNE_les_litteraux_d_octets_INNOCENTS(tmp_path):
    """Le volet symetrique, celui qui manquait entierement.

    Mesure de la revue (couche 2, finding F4) : ecrite `b"git" in octets`, la
    frontiere declarait fautifs `b"digit"` et `b"legitime"` -- c'est-a-dire la
    forme meme que la story refuse et argumente sur trois paragraphes du cote
    `str`. Elle n'etait verte que par accident de corpus : `src/` ne porte
    qu'un seul litteral d'octets, et il est vide. Le jour ou l'un de ces
    litteraux arrive, la frontiere rougit sur un module innocent -- exactement
    le scenario dont la story dit qu'il conduit a l'affaiblir.
    """
    for source in (
        'SEPARATEUR = b"digit"\n',
        'MOTIF = b"legitime"\n',
        'MIROIR = b"gitlab"\n',
        'ENTETE = b"\\x89PNG\\r\\n\\x1a\\n"\n',
        'HOTE = "github.com/GanTiz"\n',
        'AIDE = "un lot porte legitimement plusieurs masters"\n',
    ):
        innocent = _ecrire(tmp_path, "innocent_octets.py", source)
        assert signatures_de_pointeur_lfs(innocent) == [], source


def test_la_frontiere_IRRECUPERABLES_MORD_sur_un_module_fautif(tmp_path):
    """AC 4.3, troisieme frontiere -- et sur les deux formes qui passaient.

    La frontiere mesurait une **graphie** : `IRRECUPERABLE` au singulier
    (couche 1, mutant `M8`) et `"IRRECUPER" + "ABLES"` (couche 2, sonde `P4`)
    reintroduisaient l'avertissement en restant verts. Elle mesure desormais la
    racine, et lit ce que le code assemble.

    Ce qu'elle ne mesure toujours PAS, dit plutot que tu : l'avertissement
    **reformule sans le mot** (couche 1, mutant `M9` -- « aucune sauvegarde ne
    les rendra »). Fermer celui-la demande un banc de comportement sur la
    sortie de `project remove`, pas un elargissement de predicat : il est en
    dette avec son origine.
    """
    for source in (
        'print("Attention: 3 fichier(s) seront IRRECUPERABLES.")\n',
        'print("Attention: chaque fichier est IRRECUPERABLE.")\n',
        'print("  Attention: " + "IRRECUPER" + "ABLES.")\n',
    ):
        fautif = _ecrire(tmp_path, "fautif_mot.py", source)
        assert porte_le_mot_irrecuperables(fautif) != [], source


def test_les_trois_frontieres_EPARGNENT_la_prose_qui_raconte_l_incident(tmp_path):
    """Le volet symetrique de la morsure : l'histoire du `git rm -r` survit.

    C'est un livrable explicite de la story (« elle n'efface pas l'histoire du
    `git rm -r` du 2026-08-27 des docstrings ») : le motif reel qui justifie
    l'existence du module reste ecrit. Un grep textuel declarerait ce module
    fautif trois fois.
    """
    innocent = _ecrire(
        tmp_path, "innocent.py",
        '"""Le nettoyage manuel du 2026-08-27 a detruit au `git rm -r` des\n'
        'frames absentes de HEAD, donc IRRECUPERABLES -- un pointeur Git LFS\n'
        'valant b"version https://git-lfs.github.com/spec/v1" n\'y changeait\n'
        'rien."""\n'
        "# Encore un commentaire qui parle de `git ls-files` et de git-lfs.\n"
        "AIDE = \"un lot porte legitimement plusieurs masters\"\n"
        "MESSAGE = \"il s'agit d'une planche PERIMEE\"\n")
    assert appels_de_sous_processus_git(innocent) == []
    assert signatures_de_pointeur_lfs(innocent) == []
    assert porte_le_mot_irrecuperables(innocent) == []


def test_les_DEUX_lectures_de_l_AC_4_2_se_SEPARENT_sur_un_docstring(tmp_path):
    """Le perimetre exact des deux lectures, MESURE et non plus argumente.

    Couche 3, finding F4 -- son volet de morsure. Le finding ne reprochait pas
    a la frontiere etroite d'etre fausse : la couche 3 la juge « meilleure que
    l'AC ». Il reprochait a l'ecart de vivre en PROSE. Ce test le rend
    mesurable dans les deux sens a la fois : sur un module dont le mot est
    **dans un docstring et nulle part ailleurs**, l'etroite est verte, la large
    est rouge. Aucune des deux ne peut plus deriver vers l'autre sans que ce
    test le dise.

    **Regle des fabriques, quatre points** (CLAUDE.md). Trois modules
    DISTINGUABLES -- prose innocente, mot en docstring, mot a l'ecran --, et le
    balayage est rejoue avec le fautif a CHAQUE position : tete, milieu, queue.
    Une cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque, qui est l'autre mode de panne (mutant du lot A de la
    11.11). Ici la troncature serait un `modules[:-1]` glisse dans un balayage
    de frontiere, exactement ce que la couche 2 avait trouve vivant (F5).
    """
    prose = _ecrire(
        tmp_path, "prose.py",
        '"""Le nettoyage du 2026-08-27 a detruit des frames irrecuperables."""\n'
        'AIDE = "un lot porte legitimement plusieurs masters"\n')
    docstring = _ecrire(
        tmp_path, "docstring.py",
        '"""Les frames absentes de HEAD etaient IRRECUPERABLES."""\n'
        'AIDE = "rien de fautif dans le code de ce module"\n')
    ecran = _ecrire(
        tmp_path, "ecran.py",
        '"""Un docstring parfaitement muet."""\n'
        'print("Attention: 3 fichier(s) seront IRRECUPERABLES.")\n')

    # --- les deux lectures se separent, et sur le SEUL module qui les separe
    assert porte_le_mot_irrecuperables(docstring) == [], (
        "la lecture ETROITE doit epargner un mot qui ne quitte jamais le "
        "docstring : c'est le choix argumente du developpeur, et il tient")
    assert porte_le_mot_irrecuperables_MEME_EN_DOCSTRING(docstring) != [], (
        "la lecture LARGE doit mordre la : c'est l'AC 4.2 au mot pres, et "
        "c'est le mutant `M25` que rien ne tuait")

    # --- les deux bornes : ce que les DEUX lisent pareil ---------------------
    for lecture in (porte_le_mot_irrecuperables,
                    porte_le_mot_irrecuperables_MEME_EN_DOCSTRING):
        assert lecture(prose) == [], (
            "la prose EN MINUSCULES qui raconte le `git rm -r` du 2026-08-27 "
            "survit aux deux lectures -- c'est un livrable explicite de la "
            "story, et c'est ce qui rend la lecture large posable", lecture)
        assert lecture(ecran) != [], (
            "le mot IMPRIME a l'operateur est fautif pour les deux lectures",
            lecture)

    # --- les deux lectures PARTITIONNENT, elles ne se recouvrent pas ---------
    # Sans quoi « l'une est le produit, l'autre est l'AC » serait une phrase et
    # non une propriete : une chaine tombant dans les deux, ou dans aucune,
    # rendrait la difference des deux lectures illisible -- et c'est cette
    # difference que ce test existe pour mesurer.
    for module in (prose, docstring, ecran):
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        toutes = [n.value for n in ast.walk(arbre)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert (len(chaines_de_code(module)) + len(chaines_de_docstring(module))
                == len(toutes)), (
            "les deux lectures ne partitionnent plus les chaines litterales de "
            f"{module.name} : l'ecart entre elles cesse d'etre mesurable",
            {"code": len(chaines_de_code(module)),
             "docstring": len(chaines_de_docstring(module)),
             "toutes": len(toutes)})

    # --- la cible a CHAQUE BORD du balayage, jamais au seul milieu -----------
    for position, paquet in (
        ("tete", [docstring, prose, ecran]),
        ("milieu", [prose, docstring, ecran]),
        ("queue", [prose, ecran, docstring]),
    ):
        vus = {chemin.name for chemin in paquet
               if porte_le_mot_irrecuperables_MEME_EN_DOCSTRING(chemin)}
        assert "docstring.py" in vus, (
            f"le module fautif en position {position} echappe au balayage : "
            "une troncature de bord rendrait cette frontiere verte sur tout",
            sorted(vus))
