# -*- coding: utf-8 -*-
"""Story 11.4b, lot S1 (AC 1.5 et AC 2.1) -- deux frontieres, et leurs symetriques.

Elles sont ecrites dans un fichier a part, et pas ajoutees a
`test_palier_projet.py` : la premiere n'est plus une propriete du **palier**,
c'est une propriete du **paquet**. La seconde ne porte meme pas sur `tui/` mais
sur le coeur.

1. **Le paquet `tui/` entier n'appelle jamais `cli.py`.** La garde existait,
   posee sur un seul module (`test_palier_projet.test_le_palier_n_appelle_JAMAIS_cli_py`) ;
   elle balaie desormais tous les modules du paquet. Motif, verbatim de
   `tui/palier_projet.py:9-12` : « Ce module appelle `io/`, jamais `cli.py`. Les
   fonctions de `cli.py` impriment sur `stderr` et rendent un code retour :
   les appeler depuis une TUI enverrait des lignes dans le terminal **sous**
   l'ecran dessine, et rendrait un entier la ou l'interface a besoin d'un
   document ou d'un refus nomme. »

2. **Le module de coeur de l'ecriture ne lit jamais `stdin`.** Sous `textual`,
   `stdin` appartient a la boucle d'evenements : un appel bloquant y **gele
   l'interface entiere**. C'est la regression exacte payee cote GUI avec
   `QMessageBox.exec()` (`EPIC7-ARB-106` : « la suite GUI entiere a fige au
   sixieme test [...] `exec()` ne rend la main qu'au clic »). Le geste correct
   est le meme des deux cotes : la decision devient un **parametre** du coeur,
   l'invite reste chez la CLI.

**Les deux mesures sont faites a l'AST, jamais au texte** : les docstrings de
`palier_projet.py` et de `scan_write.py` expliquent justement pourquoi ces
modules ne font pas ce qu'on leur interdit, donc ils portent les mots -- un
grep de texte y mordrait et se ferait affaiblir a la premiere prose (defaut
mesure a l'ecriture de la story 11.0 sur `tui/jetons.py`).

**Story 11.8, lot B4 -- ce que la liste explicite avait oublie.** La constante
`MODULES_DE_COEUR` etait une liste de trois modules, tenue a la main story apres
story. Le lot B1 l'a mesuree : ni `makepdf.py` (11.7) ni `encode_master.py`
(11.8) n'y figuraient -- **les deux coeurs les plus recents du depot etaient
hors de la frontiere qui existe pour les tenir**, et la frontiere etait verte.
Elle est desormais une **decouverte** du paquet, avec ses exceptions ecrites et
bornees : voir :func:`modules_de_coeur` pour le motif du choix, et
`NOMS_TOLERES` pour ce que la mesure grossiere ne sait pas distinguer seule.

**Chaque frontiere porte son volet symetrique** : la meme mesure appliquee a un
module fabrique qui viole la regle DOIT mordre. Sans lui, une garde qui ne
regarderait plus rien serait verte -- et c'est le seul mode de panne qu'une
frontiere negative ne voit pas d'elle-meme.
"""

import ast
from pathlib import Path

import pytest

from outils_frontiere import identifiants

#: La racine du depot, lue au niveau module : la decouverte du paquet de coeur
#: a lieu a l'import, avant qu'aucune fixture ne soit disponible.
_RACINE_DEPOT = Path(__file__).resolve().parents[3]

#: Cache de :func:`identifiants` : la frontiere balaie une soixantaine de
#: modules fois sept noms interdits, et reparser `codec_profiles.py` quelques
#: centaines de fois couterait plus cher que toute la mesure.
_CACHE_DES_NOMS: dict[str, set[str]] = {}


def _noms(chemin: Path) -> set[str]:
    """:func:`identifiants`, memoise par chemin."""
    cle = str(chemin)
    if cle not in _CACHE_DES_NOMS:
        _CACHE_DES_NOMS[cle] = identifiants(chemin)
    return _CACHE_DES_NOMS[cle]

#: Ce par quoi un module lirait l'entree standard, nom par nom. `input` et
#: `stdin` sont les deux seuls chemins qui bloquent ; `readline` et `getpass`
#: sont leurs deguisements les plus ordinaires.
LECTURES_DE_STDIN = ("input", "stdin", "getpass", "readline")

#: Ce par quoi un module ecrirait sur le terminal. Une TUI a l'ecran dessine :
#: une ligne imprimee par le coeur atterrit **sous** l'ecran, corrompt le
#: rendu, et n'est lue par personne. Mesure ajoutee apres une injection ciblee
#: (story 11.4b, lot S1) : un `print` glisse sur le chemin de REFUS survivait
#: au banc du noyau, qui n'exerce que le chemin nominal -- une frontiere de
#: source ne depend, elle, d'aucun chemin exerce.
ECRITURES_SUR_LE_TERMINAL = ("print", "stdout", "stderr")

#: **Les paquets et modules qui ne sont PAS du coeur, et le motif de chacun.**
#: Ce sont les seules exceptions a la decouverte ci-dessous, et elles sont
#: ecrites plutot que devinees.
#:
#: * `tui/` et `gui/` sont les deux **interfaces**. L'interdit porte sur le
#:   coeur, precisement parce que les interfaces, elles, ont le droit de parler
#:   a l'operatrice ;
#: * `cli.py` est la **troisieme interface**, et c'est celle qui imprime et qui
#:   demande -- c'est son metier. `test_l_exclusion_de_cli_py_n_est_PAS_gratuite`
#:   mesure qu'elle serait bel et bien attrapee si elle entrait ici : une
#:   exclusion dont on ne prouve pas qu'elle exclut quelque chose est un trou.
PAQUETS_HORS_COEUR = ("tui", "gui")
MODULES_HORS_COEUR = ("cli.py",)


def modules_de_coeur() -> tuple[str, ...]:
    """**Le paquet de coeur, par DECOUVERTE.** Story 11.8, lot B4.

    **Le defaut que cette decouverte ferme, et il etait livre.** Cette
    constante etait une **liste explicite de trois modules** -- `scan_write`,
    `scan_detect`, `scan_calibrate` -- posee story apres story, chacune ajoutant
    le sien. Le lot B1 de la 11.8 l'a mesuree : ni `makepdf.py` (livre par la
    story 11.7) ni `encode_master.py` (livre le meme matin) n'y figuraient.
    **Les deux coeurs les plus recents du depot etaient hors de la frontiere qui
    existe pour les tenir**, et rien ne le disait -- une liste explicite est
    verte le jour ou elle oublie un module, exactement comme le jour ou elle les
    a tous.

    C'est la famille de defaut que ce depot connait le mieux : une mesure qui
    vieillit en silence pendant que le code avance. Le meme mecanisme a coute
    les numeros d'arbitrage 68 a 96 (`CLAUDE.md`, « les politiques de ce fichier
    se MESURENT ») et la borne de `CANONICAL_ID_MAX_LENGTH` recopiee dans une
    prose qui a perime.

    **Pourquoi la decouverte plutot qu'une liste tenue a jour.** Une liste
    demande un geste a chaque module neuf ; la decouverte demande un geste a
    chaque **exception**. Le premier s'oublie sans consequence visible -- c'est
    ce qui vient d'arriver deux fois --, le second ne peut pas s'oublier : un
    module de coeur qui violerait l'interdit fait rougir, et il faut soit le
    corriger, soit ecrire son motif ici. La charge tombe du bon cote.

    **Ce que la decouverte NE mesure PAS, dit plutot que tu** : un module de
    coeur pose ailleurs que sous `src/mixed_media_utility/` -- il n'y en a
    aucun -- lui resterait invisible, comme une regle sans identifiant reste
    invisible a la frontiere des politiques. C'est le prix d'une mesure de
    structure, et il se dit.
    """
    racine = _RACINE_DEPOT / "src" / "mixed_media_utility"
    trouves = []
    for chemin in sorted(racine.rglob("*.py")):
        relatif = chemin.relative_to(racine)
        if relatif.parts[0] in PAQUETS_HORS_COEUR:
            continue
        if relatif.as_posix() in MODULES_HORS_COEUR:
            continue
        trouves.append(relatif.as_posix())
    return tuple(trouves)


#: Les modules de coeur sur lesquels l'interdit porte, **decouverts** et non
#: recopies. Ils entrent des qu'ils sont ecrits : `makepdf.py` et
#: `encode_master.py` y sont sans qu'aucune story ait eu a les nommer, et le
#: prochain y sera de meme.
MODULES_DE_COEUR = modules_de_coeur()

#: **Tolerances ECRITES, avec leur motif, sur le modele de `LANCEURS_TOLERES`**
#: (`test_coeur_en_processus.py`) : ce n'est pas un affaiblissement silencieux
#: de la garde, c'est un arbitrage ecrit AVEC son motif et **borne par une
#: seconde mesure**.
#:
#: La mesure grossiere ci-dessus lit des **noms** (:func:`identifiants` rend
#: aussi les attributs). Elle ne distingue donc pas `sys.stdout` -- le vrai flux
#: du processus -- de `resultat.stdout`, qui est le champ d'un
#: `CompletedProcess` rendu par `ffprobe`. Les quatre premieres tolerances sont
#: toutes de cette seule famille : **une capture de sous-processus, jamais une
#: ecriture sur le terminal**.
#:
#: **`project_maintenance.py: ("stdout",)` a ete RETIREE le 2026-09-03** (story
#: 11.13, `EPIC11-ARB-199`) : elle ne couvrait que le `resultat.stdout` de
#: `_noms_suivis_par_git`, la seule lecture de git du coeur, et cette fonction
#: n'existe plus. C'est `test_chaque_TOLERANCE_est_encore_VIVE` qui l'a dit --
#: la tolerance morte a fait rougir la suite d'elle-meme, ce qui est
#: exactement ce que ce test existe pour faire.
#:
#: La cinquieme est d'une autre nature et vaut d'etre lue : le `readline` de
#: `source_confirmation.py` porte sur `in_stream`, un flux **passe en
#: parametre**. C'est exactement la forme que l'AC 2.1 EXIGE -- « la decision
#: devient un parametre du coeur, l'invite reste chez la CLI » --, donc la
#: tolerer n'est pas relacher l'interdit, c'est refuser de faire rougir sa
#: bonne reponse.
#:
#: Deux tests les bornent, et aucun ne se contente de les croire :
#: `test_chaque_TOLERANCE_est_encore_VIVE` retire celles qui ne servent plus,
#: `test_chaque_TOLERANCE_est_BORNEE` mesure qu'aucun de ces modules ne touche
#: le VRAI flux -- ni `sys.<nom>`, ni `from sys import <nom>`, ni appel nu.
NOMS_TOLERES: dict[str, tuple[str, ...]] = {
    "codec_profiles.py": ("stdout", "stderr"),
    "extraction.py": ("stdout",),
    "ffmpeg_utils.py": ("stderr",),
    "video_metadata.py": ("stdout", "stderr"),
    "source_confirmation.py": ("readline",),
}

#: **Ce par quoi un module de `tui/` redigerait une SECONDE lecture d'un
#: document de detection** (story 11.6, AC 2.8). `gui/` en porte deja deux
#: (`chargeur_detections.py`, `lecture_detection.py`) ; une troisieme dans
#: `tui/` serait la faute que `EPIC11-ARB-108` nomme -- « un mecanisme, un
#: lieu ». Le point d'entree de coeur `scan_write.lire_le_document_de_detection`
#: existe depuis le lot B pour qu'il n'y ait rien a rediger.
LECTEUR_NORMATIF_DU_DOCUMENT = "scan_previz_from_json_dict"

#: **L'ensemble EXACT des modules de `tui/` qui relisent un document de
#: detection, et il n'en compte qu'un.** `atelier_scan_parcours` le fait depuis
#: la story 11.5 (lot C), pour **montrer** ce qu'un document dit -- c'est le
#: temps 1, pas le temps 2.
#:
#: L'egalite est ce qui mesure quelque chose : « aucun module du temps 2 n'en
#: redige » serait vrai d'un paquet ou personne ne lit rien, et resterait vrai
#: le jour ou un ecran du temps 2 en redigerait un second sous un autre nom.
#: L'ensemble EXACT mesure l'exception **et** son unicite (`CLAUDE.md`,
#: vague 3 : « une assertion positive laisse passer toute divergence
#: supplementaire »).
#:
#: **Ce que cet ensemble ne dit pas, dit plutot que taire** : le module qui y
#: figure gagnerait a passer par le lecteur de coeur lui aussi. Le faire
#: depuis cette story toucherait un module de la 11.5 et son banc, ce que la
#: regle de decoupage interdit ; l'ensemble le tient en lisiere en attendant.
MODULES_TUI_QUI_RELISENT_UN_DOCUMENT = {"atelier_scan_parcours.py"}


def _appelle_cli(chemin: Path) -> list[str]:
    """Les noms par lesquels ce module referencerait `cli.py`.

    Le predicat est celui de `test_palier_projet.test_le_palier_n_appelle_JAMAIS_cli_py`,
    mot pour mot : un import `mixed_media_utility.cli`, un `from ... import cli`,
    ou un acces d'attribut `.cli`. Le reprendre a l'identique est delibere --
    deux predicats pour un seul interdit divergeraient, et c'est le module non
    couvert par le plus strict des deux qui passerait.
    """
    noms = identifiants(chemin)
    return sorted(n for n in noms if n.endswith("cli") or n.endswith(".cli"))


# ---------------------------------------------------------------------------
# AC 1.5 -- le paquet `tui/` entier, et son volet symetrique
# ---------------------------------------------------------------------------


def test_le_paquet_tui_n_appelle_JAMAIS_cli_py(sources_tui):
    """AC 1.5 : comptage a zero sur **tous** les modules du paquet.

    La fixture `sources_tui` verifie deja son propre cardinal : une frontiere
    posee sur un paquet vide serait verte sans rien mesurer.
    """
    fautifs = {chemin.name: _appelle_cli(chemin) for chemin in sources_tui
               if _appelle_cli(chemin)}
    assert fautifs == {}, fautifs


def test_le_balayage_de_la_frontiere_cli_a_bien_VU_le_paquet(sources_tui):
    """AC 2.3, **second sens** : « le banc echoue s'il ne mesure plus rien ».

    La fixture `sources_tui` ne garantit qu'un plancher de deux modules -- assez
    pour dire que le paquet existe, pas assez pour dire qu'il a ete balaye. Le
    plancher est pose ici, au plus pres de la frontiere qu'il protege, plutot
    que dans le `conftest` que tous les lots de l'epic partagent.

    Un plancher et non une egalite : le paquet grandit a chaque story, et les
    ecrans de l'atelier Exports (lot B5) y entreront **sans qu'aucune ligne de
    ce banc ne change** -- c'est la meme raison qui fait passer
    `MODULES_DE_COEUR` d'une liste a une decouverte.
    """
    assert len(sources_tui) >= 30, [c.name for c in sources_tui]
    assert any(c.name == "palier_projet.py" for c in sources_tui)


def test_la_mesure_de_la_frontiere_cli_MORD_sur_un_module_fautif(tmp_path):
    """AC 1.5, volet symetrique : la garde ci-dessus regarde bien quelque chose.

    Trois formes de violation, et la prose innocente au milieu. Une garde qui
    grepperait le texte declarerait le module fautif sur son seul docstring et
    serait donc inapplicable ; celle-ci ne mord que sur du code.
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        '"""Ce module parle de cli.py et de mixed_media_utility.cli sans les'
        ' appeler."""\n'
        "# Encore un commentaire qui nomme cli.py.\n"
        "MESSAGE = 'voir cli.py pour le detail'\n",
        encoding="utf-8")
    assert _appelle_cli(innocent) == [], "la prose n'est pas un appel"

    for source in (
        "from mixed_media_utility import cli\n",
        "import mixed_media_utility.cli\n",
        "from mixed_media_utility import cli as noyau\nnoyau.scan_command(None)\n",
        "import mixed_media_utility as mmu\nmmu.cli.scan_command(None)\n",
    ):
        fautif = tmp_path / "fautif.py"
        fautif.write_text(source, encoding="utf-8")
        assert _appelle_cli(fautif) != [], source


# ---------------------------------------------------------------------------
# AC 2.1 -- le coeur ne lit jamais `stdin`, et son volet symetrique
# ---------------------------------------------------------------------------


def _est_une_violation(chemin: Path, module: str, interdit: str) -> bool:
    """Le nom est present ET la paire n'est pas une tolerance ecrite."""
    return (interdit in _noms(chemin)
            and interdit not in NOMS_TOLERES.get(module, ()))


@pytest.mark.parametrize("module", MODULES_DE_COEUR)
@pytest.mark.parametrize("interdit", LECTURES_DE_STDIN)
def test_le_module_de_coeur_ne_lit_JAMAIS_stdin(racine_depot, module, interdit):
    """AC 2.1 : un nom a la fois, sur **chaque** module du paquet de coeur.

    Parametre nom par nom plutot qu'en un seul balayage : un echec dit **quel**
    chemin a ete rouvert, et un `input()` glisse dans un module ne peut pas se
    cacher derriere le silence d'un autre.

    **Aucun `skip` sur les tolerances.** Un test vert d'un cote et saute de
    l'autre ne figure dans aucune des deux listes de rouges alors qu'il signale
    qu'un regime n'a pas joue (`CLAUDE.md` : « on compare des listes de
    verdicts, jamais des compteurs »). La tolerance entre donc dans le
    **predicat**, et elle est bornee par ses deux tests a elle.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / module
    assert chemin.is_file(), chemin
    assert not _est_une_violation(chemin, module, interdit), (module, interdit)


@pytest.mark.parametrize("module", MODULES_DE_COEUR)
@pytest.mark.parametrize("interdit", ECRITURES_SUR_LE_TERMINAL)
def test_le_module_de_coeur_n_ECRIT_JAMAIS_sur_le_terminal(racine_depot, module,
                                                           interdit):
    """AC 1.1 : « aucun `print` ». Sur le source, donc sur TOUS les chemins.

    Un banc d'execution ne mesure que les chemins qu'il exerce : l'injection
    ciblee de la story 11.4b a montre qu'un `print` pose sur le chemin de
    REFUS survivait au banc du noyau, qui deroulait le chemin nominal. La
    frontiere de source ne depend d'aucun chemin exerce.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / module
    assert chemin.is_file(), chemin
    assert not _est_une_violation(chemin, module, interdit), (module, interdit)


# ---------------------------------------------------------------------------
# AC 11.1 (story 11.8, lot B4) -- la DECOUVERTE regarde bien le paquet entier
# ---------------------------------------------------------------------------


def test_la_decouverte_du_coeur_voit_les_modules_les_plus_RECENTS():
    """**Le defaut mesure par le lot B1, nomme.** Volet positif de la decouverte.

    `makepdf.py` (story 11.7) et `encode_master.py` (11.8, lot B1) sont les deux
    modules que la liste explicite avait oublies. Les nommer ici n'est pas
    revenir a une liste : c'est mesurer que la decouverte **ramene** ce que la
    liste ratait. Le jour ou elle se viderait -- un `rglob` casse, une racine
    fausse --, ce test rougit ; les centaines de frontieres ci-dessus, elles,
    resteraient vertes en ne mesurant plus rien.
    """
    assert "makepdf.py" in MODULES_DE_COEUR
    assert "encode_master.py" in MODULES_DE_COEUR


def test_la_decouverte_regarde_une_surface_NON_VIDE_et_PROFONDE():
    """Le cardinal au **plancher**, et les deux sous-paquets nommes.

    Un plancher et non une egalite : le paquet grandit a chaque story, et une
    egalite ferait rougir la frontiere pour une raison qui n'est pas la sienne.
    Les sous-paquets sont nommes parce qu'un `glob("*.py")` -- au lieu d'un
    `rglob` -- rendrait une surface de bonne taille en manquant `io/` entier,
    et le seul cardinal ne le verrait pas.
    """
    assert len(MODULES_DE_COEUR) >= 40, MODULES_DE_COEUR
    assert any(m.startswith("io/") for m in MODULES_DE_COEUR), MODULES_DE_COEUR
    assert any(m.startswith("detection/") for m in MODULES_DE_COEUR), MODULES_DE_COEUR


def test_la_decouverte_du_coeur_ne_ramene_AUCUNE_interface():
    """Les trois exclusions, mesurees plutot que crues.

    `tui/` et `gui/` n'ont pas a repondre d'un interdit ecrit pour le coeur ;
    `cli.py` non plus, et c'est le test suivant qui dit pourquoi cette
    troisieme exclusion n'est pas une echappatoire.
    """
    assert not [m for m in MODULES_DE_COEUR
                if m.startswith(("tui/", "gui/"))], MODULES_DE_COEUR
    assert "cli.py" not in MODULES_DE_COEUR


@pytest.mark.parametrize("famille,interdits", [
    ("elle LIT l'entree standard", LECTURES_DE_STDIN),
    ("elle ECRIT sur le terminal", ECRITURES_SUR_LE_TERMINAL),
])
def test_l_exclusion_de_cli_py_n_est_PAS_gratuite(racine_depot, famille,
                                                  interdits):
    """**Volet symetrique de l'exclusion**, sur le vrai `cli.py` du depot.

    Une exclusion se justifie par ce qu'elle exclut : `cli.py` serait attrapee
    par les **deux** frontieres si elle y entrait, et c'est pour cela qu'elle en
    sort par un motif ecrit plutot que par omission. Le jour ou elle cesserait
    d'imprimer ou de demander, l'exclusion ne protegerait plus rien et devrait
    tomber -- ce test le dirait.

    Et surtout : c'est le seul test qui prouve que la mesure mord sur un
    **module reel** du depot, pas seulement sur les modules fabriques de
    `tmp_path`. Une mesure devenue muette rendrait les centaines de frontieres
    ci-dessus vertes ; elle rougit ici d'abord.

    La mesure porte sur la **famille** et non sur chaque nom : `cli.py` ne porte
    pas `getpass` -- elle n'a pas de mot de passe a demander --, et exiger les
    sept noms ferait rougir ce banc pour une raison qui n'est pas la sienne.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / "cli.py"
    portes = sorted(nom for nom in interdits if nom in _noms(chemin))
    assert portes, (famille, interdits)


# ---------------------------------------------------------------------------
# AC 11.1 -- les tolerances : vives, et bornees
# ---------------------------------------------------------------------------


def _touche_le_VRAI_flux(chemin: Path, nom: str) -> list[str]:
    """Les sites ou ce module designe le flux standard du PROCESSUS.

    Trois formes, et elles suffisent a separer `resultat.stdout` -- le champ
    d'un `CompletedProcess` -- de `sys.stdout`, qui est le terminal :

    * `sys.<nom>`, l'acces direct ;
    * `from sys import <nom>`, le meme par un autre chemin -- sans cette forme,
      un module echapperait a la mesure en important le flux sous son nom nu ;
    * un **appel nu** `<nom>(...)`, qui est ce que sont `print(...)`,
      `input(...)` et `getpass(...)`.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    sites = []
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute) and noeud.attr == nom
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "sys"):
            sites.append(f"{chemin.name}:{noeud.lineno} sys.{nom}")
        elif (isinstance(noeud, ast.ImportFrom) and noeud.module == "sys"
                and any(alias.name == nom for alias in noeud.names)):
            sites.append(f"{chemin.name}:{noeud.lineno} from sys import {nom}")
        elif (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == nom):
            sites.append(f"{chemin.name}:{noeud.lineno} appel nu {nom}()")
    return sites


PAIRES_TOLEREES = [(module, nom) for module, noms in sorted(NOMS_TOLERES.items())
                   for nom in noms]


@pytest.mark.parametrize("module,interdit", PAIRES_TOLEREES)
def test_chaque_TOLERANCE_est_encore_VIVE(racine_depot, module, interdit):
    """Une tolerance qui ne sert plus se **retire**, elle ne dort pas.

    C'est la moitie qu'on oublie : une exception ecrite pour un site disparu
    reste ouverte pour le site suivant, qui n'aura, lui, aucun motif ecrit.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / module
    assert chemin.is_file(), chemin
    assert interdit in _noms(chemin), (
        f"{module} ne porte plus {interdit!r} : retirer la tolerance")


@pytest.mark.parametrize("module,interdit", PAIRES_TOLEREES)
def test_chaque_TOLERANCE_est_BORNEE_au_flux_d_un_SOUS_PROCESSUS(
        racine_depot, module, interdit):
    """**La tolerance ne peut pas cacher une vraie ecriture.**

    Elle porte sur un NOM ; la borne porte sur ce que ce nom **designe**. Un
    `print()` glisse demain dans `codec_profiles.py` serait couvert par sa
    tolerance `stdout`/`stderr` si elle n'etait pas bornee -- il fait rougir
    ici.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / module
    sites = _touche_le_VRAI_flux(chemin, interdit)
    assert sites == [], sites


@pytest.mark.parametrize("interdit", ("stdout", "stderr", "print", "input"))
def test_la_BORNE_des_tolerances_MORD_sur_le_vrai_cli_py(racine_depot, interdit):
    """Volet symetrique de la borne, sur un module reel et pas fabrique.

    `cli.py` fait les deux : `sys.stdout` et `print(...)`. Si
    :func:`_touche_le_VRAI_flux` devenait muette -- un nom de champ AST change,
    un `walk` casse --, les tolerances ci-dessus deviendraient sans borne **et**
    vertes. Ce test est ce qui l'empeche.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / "cli.py"
    assert _touche_le_VRAI_flux(chemin, interdit), interdit


def test_la_BORNE_ne_mord_PAS_sur_une_capture_de_SOUS_PROCESSUS(tmp_path):
    """L'autre moitie du volet : ce que la borne **tolere**, ecrit.

    Sans lui, un resserrement futur de la borne ferait rougir les six modules
    tolerees du depot sans que rien ne dise qu'ils etaient legitimes.
    """
    innocent = tmp_path / "capture.py"
    innocent.write_text(
        "import subprocess\n"
        "def sonder(commande):\n"
        "    resultat = subprocess.run(commande, capture_output=True)\n"
        "    return resultat.stdout, resultat.stderr\n",
        encoding="utf-8")
    assert _touche_le_VRAI_flux(innocent, "stdout") == []
    assert _touche_le_VRAI_flux(innocent, "stderr") == []

    for source in ("import sys\nsys.stdout.write('x')\n",
                   "from sys import stdout\nstdout.write('x')\n"):
        bavard = tmp_path / "bavard.py"
        bavard.write_text(source, encoding="utf-8")
        assert _touche_le_VRAI_flux(bavard, "stdout") != [], source


@pytest.mark.parametrize("interdit", ECRITURES_SUR_LE_TERMINAL)
def test_la_mesure_des_ecritures_MORD_sur_un_module_fautif(tmp_path, interdit):
    """Volet symetrique, sur les trois noms et pas sur le premier."""
    chemin = tmp_path / "module_bavard.py"
    chemin.write_text(
        f'"""Un docstring qui parle de {interdit} sans rien ecrire."""\n'
        "import sys\n"
        "def dire(message):\n"
        f"    return {interdit}\n",
        encoding="utf-8")
    assert interdit in identifiants(chemin), interdit


@pytest.mark.parametrize("interdit", LECTURES_DE_STDIN)
def test_la_mesure_de_stdin_MORD_sur_un_module_fautif(tmp_path, interdit):
    """AC 2.1, volet symetrique, sur les quatre noms et pas sur le premier."""
    chemin = tmp_path / "module_fautif.py"
    chemin.write_text(
        f'"""Un docstring qui parle de {interdit} sans le lire."""\n'
        "import sys\n"
        "def demander():\n"
        f"    return sys.{interdit} if hasattr(sys, '{interdit}') else {interdit}\n",
        encoding="utf-8")
    assert interdit in identifiants(chemin), interdit


def test_la_decision_de_correction_est_bien_UN_PARAMETRE_du_coeur():
    """Volet positif de l'AC 2.1 : la frontiere n'est pas verte par amputation.

    Une garde qui interdit `stdin` serait satisfaite par un coeur qui ne
    poserait plus la question du tout -- ce qui supprimerait les trois regimes
    au lieu de les deplacer. Ce que ce test mesure est l'autre moitie : la
    decision **entre**, par un parametre nomme, et elle porte un defaut qui
    reproduit le regime non interactif.
    """
    import inspect

    from mixed_media_utility import scan_write

    signature = inspect.signature(scan_write.ecrire_le_lot_detecte)
    rappel = signature.parameters["demander_l_application_de_la_correction"]
    assert rappel.kind is inspect.Parameter.KEYWORD_ONLY
    # `None` = « personne pour repondre »: aucune invite, la correction est
    # appliquee. C'est le regime 2 des trois, et c'est celui des scripts.
    assert rappel.default is None
    # Et l'invite elle-meme est restee du cote qui a le droit de la poser.
    from mixed_media_utility import cli
    assert callable(cli._ask_apply_correction)


# ---------------------------------------------------------------------------
# AC 2.8 (story 11.6, lot B) -- aucune TROISIEME lecture de document dans `tui/`
# ---------------------------------------------------------------------------


def test_les_modules_tui_qui_relisent_un_document_sont_EXACTEMENT_connus(
        sources_tui):
    """AC 2.8 : comptage a l'AST, en **egalite** et jamais en inclusion.

    Le lot B a publie `scan_write.lire_le_document_de_detection` precisement
    pour qu'aucun ecran du temps 2 n'ait a rediger la sequence -- lecture,
    cinq refus nommes, condensat. Cette mesure rougit des qu'un module de plus
    s'y met, quel que soit son nom.
    """
    lecteurs = {chemin.name for chemin in sources_tui
                if LECTEUR_NORMATIF_DU_DOCUMENT in identifiants(chemin)}
    assert lecteurs == MODULES_TUI_QUI_RELISENT_UN_DOCUMENT, sorted(lecteurs)


def test_la_mesure_de_la_TROISIEME_lecture_MORD_sur_un_module_fautif(tmp_path):
    """AC 2.8, volet symetrique : la garde ci-dessus regarde bien quelque chose.

    Sans lui, un `identifiants` devenu muet -- ou un nom de fonction change au
    coeur sans que la constante suive -- rendrait l'egalite ci-dessus vraie sur
    un ensemble vide **et** sur l'ensemble attendu, donc verte pour la
    mauvaise raison.
    """
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        f'"""Ce module parle de {LECTEUR_NORMATIF_DU_DOCUMENT} sans l\'appeler."""\n'
        f"MESSAGE = 'voir {LECTEUR_NORMATIF_DU_DOCUMENT} pour le detail'\n",
        encoding="utf-8")
    assert LECTEUR_NORMATIF_DU_DOCUMENT not in identifiants(innocent)

    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        "from mixed_media_utility import scan_previz\n"
        "def relire(brut):\n"
        f"    return scan_previz.{LECTEUR_NORMATIF_DU_DOCUMENT}(brut)\n",
        encoding="utf-8")
    assert LECTEUR_NORMATIF_DU_DOCUMENT in identifiants(fautif)


def test_le_lecteur_normatif_du_document_est_bien_CELUI_du_coeur():
    """Volet positif : la constante nomme une fonction qui existe.

    Une frontiere posee sur un nom qui n'existe plus est verte pour toujours.
    Le nom est donc confronte au coeur, des deux cotes de la mesure : le
    lecteur de `scan_previz`, et le point d'entree de `scan_write` qui
    l'appelle a la place des interfaces.
    """
    from mixed_media_utility import scan_previz, scan_write

    assert callable(getattr(scan_previz, LECTEUR_NORMATIF_DU_DOCUMENT))
    assert callable(scan_write.lire_le_document_de_detection)



# ---------------------------------------------------------------------------
# Story 11.11, lot E -- AC 5.1 et AC 5.2, chacune avec son volet symetrique
# ---------------------------------------------------------------------------

#: Les deux modules d'ecran de la story 11.11. Ils sont NOMMES ici -- une
#: decouverte par motif (`projet_*.py`) ramenerait `projets.py` et
#: `projet_lecture.py`, qui ne sont pas de cette story et n'ont pas ses
#: contraintes. Deux noms tenus a la main pour deux modules, contre une regle
#: de nommage a maintenir : le nommage explicite est ici le moins fragile.
ECRANS_DE_LA_11_11 = ("projet_inventaire.py", "projet_suppression.py")

#: Ce par quoi un ecran ouvrirait un champ de nom editable (`EPIC11-ARB-141`,
#: AC 5.1). `ModeleNoms` est le seul mecanisme d'edition de nom du depot, et
#: `Input` est le widget `textual` qui le contournerait.
#:
#: **`ModeleNoms` n'est PAS dans la liste**, et c'est le point : les deux
#: ecrans de suppression en construisent un **vide**, ce qui est exactement la
#: forme que l'`ARB-141` demande -- `EcranChiffre.traiter` rend alors `Tab`
#: inerte de lui-meme, par absence de destination et non par une garde. Ce qui
#: est interdit, c'est de le PEUPLER : `Nom(`, `noms=[`, ou un widget de saisie.
OUVERTURES_DE_CHAMP = ("Input", "TextArea", "MaskedInput")


@pytest.mark.parametrize("module", ECRANS_DE_LA_11_11)
def test_11_11_aucun_ecran_n_ouvre_un_CHAMP_DE_NOM(racine_depot, module):
    """AC 5.1 / `EPIC11-ARB-141` : aucun nom n'est editable dans cette story.

    L'inventaire montre des noms produits et la suppression en retire : ni l'un
    ni l'autre n'a de raison de laisser en saisir un, et un champ de saisie sur
    un ecran destructeur serait le pire endroit du produit pour en avoir un.
    """
    chemin = racine_depot / "src" / "mixed_media_utility" / "tui" / module
    noms = _noms(chemin)
    for interdit in OUVERTURES_DE_CHAMP:
        assert interdit not in noms, f"{module} ouvre un {interdit}"


def test_11_11_la_mesure_du_champ_de_nom_MORD_sur_un_ecran_fautif(tmp_path):
    """Volet symetrique : la garde ci-dessus regarde bien quelque chose.

    Sans lui, un `OUVERTURES_DE_CHAMP` vide -- ou un `_noms` qui cesserait de
    voir les appels -- rendrait la frontiere verte sur un ecran qui ouvre bel
    et bien un champ.
    """
    fautif = tmp_path / "fautif.py"
    fautif.write_text("from textual.widgets import Input\n"
                      "def contenu():\n    return [Input()]\n",
                      encoding="utf-8")
    assert any(interdit in identifiants(fautif)
               for interdit in OUVERTURES_DE_CHAMP)


@pytest.mark.parametrize("module", ECRANS_DE_LA_11_11)
def test_11_11_les_ecrans_de_la_story_sont_bien_DANS_le_balayage(sources_tui,
                                                                 module):
    """Le second sens d'AC 2.3 : « le banc echoue s'il ne mesure plus rien ».

    Les deux modules neufs sont couverts par la frontiere `cli.py` du paquet
    **sans qu'aucune ligne ne soit ajoutee** -- c'est la vertu d'une decouverte
    contre une liste. Encore faut-il le CONSTATER : le lot B1 de la story 11.8
    a mesure que les deux coeurs les plus recents du depot etaient hors de la
    frontiere qui existe pour les tenir, et la frontiere etait verte.
    """
    assert any(chemin.name == module for chemin in sources_tui), module


#: L'ensemble EXACT des mots-cles que la story transmet a chaque point d'entree
#: de coeur (AC 5.2). Il est compare a la SIGNATURE du coeur : le test rougira
#: le jour ou un parametre s'ajoutera sans etre cable, ce qu'une assertion
#: positive (« `dry_run` est bien transmis ») ne ferait pas.
#:
#: **Ce n'est pas une liste des mots-cles UTILISES**, c'est une liste de ceux
#: que la story a VUS et tranches. Un parametre neuf du coeur doit passer par
#: une decision -- le cabler, ou ecrire pourquoi on ne le cable pas --, et
#: c'est cette decision que la frontiere force.
MOTS_CLES_DE_LA_SUPPRESSION = {
    # Cables, et chacun par une issue ou une cible :
    "lot_id", "rush_id", "dry_run", "confirmation_dernier_lot", "avec_scans",
    "planche", "liberer_le_rang", "master", "profile", "resolution", "scan",
    "lot_scanne", "version",
    # `frames_extraites` est venu le 2026-09-07 avec `EPIC11-ARB-111` --
    # cinquieme cible fine du coeur. **Il est CABLE**, et l'entree dit ou :
    # `tui/projet_suppression.cible_du_noeud`, branche `NATURE_FRAMES_EXTRAITES`,
    # qui pose `fine["frames_extraites"] = True` puis rend TOUT DE SUITE. Le
    # retour immediat est la partie qu'un lecteur du seul nom ne devinerait pas
    # et qui est mesuree ailleurs : le `version=` general de la fin de fonction
    # est court-circuite, parce que le dossier de frames extraites porte le rang
    # du LOT et non le sien (`project_layout.rush_dir_slug`), si bien qu'un rang
    # lu de l'arbre et transmis ici designerait le dossier d'un AUTRE lot.
    "frames_extraites",
}


def test_11_11_AC_5_2_l_ensemble_EXACT_des_mots_cles_du_coeur_est_TRANCHE():
    """AC 5.2 : la frontiere rougit au premier parametre ajoute sans cablage.

    La fiche de la story decrit une signature a ONZE mots-cles ; le coeur en
    porte QUATORZE au 2026-09-07 (`lot_scanne` et `version` sont venus avec
    `EPIC11-ARB-214` et `-224`, `resolution` avec les masters,
    `frames_extraites` avec `EPIC11-ARB-111`). La fiche est donc perimee, et
    c'est **ecrit au registre plutot que corrige dans son texte** -- aucun
    texte d'AC ne se reecrit.

    **Le compte de ce paragraphe etait FAUX, et il l'etait avant le mot-cle
    neuf.** Il annoncait QUATORZE au 2026-09-05 pendant que le registre en
    portait treize et que le test etait vert -- donc pendant que le coeur en
    portait treize lui aussi, mesure a `b7138e79d`. Un compte ecrit en prose
    ne se mesure pas ; c'est l'egalite des deux ensembles, ci-dessous, qui
    fait foi, et c'est pourquoi elle existe.

    Ce test tient l'ecart mesure : il compare l'ensemble tranche a la signature
    REELLE, et il dira lui-meme lequel des deux a bouge.
    """
    import inspect

    from mixed_media_utility.project_maintenance import remove_project_element

    signature = inspect.signature(remove_project_element)
    mots_cles = {nom for nom, p in signature.parameters.items()
                 if p.kind is inspect.Parameter.KEYWORD_ONLY}
    assert mots_cles == MOTS_CLES_DE_LA_SUPPRESSION, (
        "la signature du coeur a change : chaque mot-cle neuf doit etre cable "
        "ou son absence de cablage ecrite au registre de la story.\n"
        f"  au coeur et pas tranches : {sorted(mots_cles - MOTS_CLES_DE_LA_SUPPRESSION)}\n"
        f"  tranches et plus au coeur : {sorted(MOTS_CLES_DE_LA_SUPPRESSION - mots_cles)}")


def test_11_11_AC_5_2_l_INVENTAIRE_est_lu_du_coeur_et_non_derive():
    """AC 1 : la TUI ne derive pas l'inventaire, elle le LIT.

    Le point d'entree du coeur prend le dossier du projet et **rien d'autre** :
    tout parametre supplementaire serait une decision prise a l'ecran sur ce
    qu'on inventorie, c'est-a-dire un debut de derivation.

    Le volet symetrique compte ce que l'ecran lit : les natures et les etats
    sont ceux du coeur, importes, jamais redeclares. Une seconde table de
    natures divergerait au premier ajout -- et c'est la nature nouvelle,
    invisible a l'ecran, qui disparaitrait de l'arbre.
    """
    import inspect

    from mixed_media_utility import project_inventory as coeur
    from mixed_media_utility.tui import projet_inventaire

    signature = inspect.signature(coeur.inventorier_le_projet)
    assert [p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            for p in signature.parameters.values()] == [True]

    source = (Path(projet_inventaire.__file__)).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    importes = {alias.name for noeud in ast.walk(arbre)
                if isinstance(noeud, ast.ImportFrom)
                and (noeud.module or "").endswith("project_inventory")
                for alias in noeud.names}
    natures = {nom for nom in dir(coeur) if nom.startswith("NATURE_")}
    manquantes = natures - importes
    assert manquantes == set(), (
        f"l'ecran ignore des natures du coeur : {sorted(manquantes)}. Une "
        "nature que l'ecran ne connait pas disparait de l'arbre en silence.")
    # Et le volet negatif : aucune nature n'est **redeclaree** a l'ecran.
    assert not [n for n in dir(projet_inventaire)
                if n.startswith("NATURE_") and n not in natures]
