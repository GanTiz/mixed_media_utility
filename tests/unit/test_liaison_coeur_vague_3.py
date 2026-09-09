# -*- coding: utf-8 -*-
"""Story 11.4b, **lot S6** (AC 11) -- le document de liaison dit la verite.

`EPIC11-ARB-77`, verbatim -- Egan, le 2026-08-29 au soir : « **Pour le moment
importe le necessaire dans cette branche, on fera la liaison avec main et les
autres branches sur les modifications de coeur par la suite.** »

L'AC 11 est donc **revisee** : rien n'est pousse ailleurs, et ce qui est du,
c'est le **document de liaison** -- la liste des modules partages touches, avec
pour chacun le report a faire et son motif. Un document de liaison qui derive
du code qu'il decrit est pire qu'aucun document : il donnera au report une
liste fausse qu'on croira juste, et personne ne relira le diff pour la
verifier. Ce module est ce qui empeche cette derive.

Trois mesures, et elles ferment les deux moities de l'arbitrage :

* **la liaison est PREPAREE** -- les deux listes du depot qui recensent les
  fichiers de coeur touches par l'Epic 11 (`CHANGEMENTS_ACCEPTES` du registre
  et la table de liaison) nomment **les memes** ; et chaque ligne de la table
  dit si c'est un **ajout pur** ou un **changement de comportement**, seule
  distinction qui compte au moment du report ;
* **elle n'est PAS poussee** -- aucun commit de la vague n'est contenu dans une
  autre branche distante que `origin/oc/epic-11-TUI`.

Chaque mesure porte son **volet symetrique** : une table qu'on ne saurait plus
lire, ou une liste de branches distantes reduite a une seule, rendrait ces
tests verts sans qu'ils observent quoi que ce soit.
"""
from __future__ import annotations

import ast
import re
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[2]

# La regle « reference de perimetre inatteignable : clone tronque, ou AUTRE
# depot ? » vit dans `tests/_regime_du_depot.py`, ecrite une fois pour ses
# appelants. Ce banc en est un : sa `BASELINE` est l'une des quatorze
# references declarees du depot, et elle n'existe pas dans l'orphelin public.
sys.path.insert(0, str(_RACINE / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402

#: Le document dont ce module mesure la fidelite.
LIAISON = (_RACINE / "_bmad-output" / "implementation-artifacts"
           / "liaison-coeur-vague-3.md")

#: L'autre liste du depot : le registre des changements de coeur acceptes par
#: l'Epic 11. Il est lu **par `ast`** et non importe : le module qui le porte
#: monte `textual`, et une frontiere documentaire n'a pas a payer ce prix.
REGISTRE = _RACINE / "tests" / "unit" / "tui" / "test_coeur_en_processus.py"

#: Le `baseline_commit` de la vague 3 -- le point d'ou partent les lots S.
BASELINE = "289f29d"


#: La branche de travail, et la **seule** que l'arbitrage autorise. Ecrite
#: **sans nom de depot distant**, et c'est un correctif du 2026-09-07.
#:
#: **Le defaut que ce nom court ferme, et il a ete mesure par une session
#: voisine.** Cette constante valait `"origin/oc/epic-11-TUI"`. Un conteneur
#: dont le distant s'appelle autrement -- `dev`, chez la session Outillage qui
#: l'a signale -- voit toutes ses branches nommees `dev/...`. La branche de
#: l'epic elle-meme s'y appelle donc `dev/oc/epic-11-TUI`, qui n'est pas egal a
#: `origin/oc/epic-11-TUI` : **la frontiere comptait la branche qu'elle protege
#: parmi les branches interdites**, et les cinq exemptions de
#: `BRANCHES_FILLES`, toutes ecrites `origin/...`, manquaient de meme. Huit
#: branches rouges chez elle, zero ici, sur le meme arbre.
#:
#: Le nom du distant est une convention **locale au clone** : `CLAUDE.md` en
#: impose deja deux dans ce depot (`origin` vers `-dev`, `public` vers la
#: distribution). Une frontiere qui en suppose un troisieme ne mesure pas
#: l'arbitrage, elle mesure le clone.
BRANCHE = "oc/epic-11-TUI"

#: Les noms de module qui existent **des deux cotes** de la frontiere `tui/`, et
#: que le rapprochement ci-dessous ne peut donc pas trancher : `jetons.py` vit
#: dans `gui/` (du coeur, au sens du registre) **et** dans `tui/` (qui n'en est
#: pas). Les lignes L6 et L7 parlent du second. Les nommer ici, plutot que
#: d'elargir le motif de reconnaissance, garde la mesure exacte sur tous les
#: autres.
AMBIGUS = frozenset({"jetons"})

#: Le vocabulaire que chaque ligne de la table doit employer dans sa colonne
#: « forme ». Ce n'est pas du style : au moment du report, un **ajout pur**
#: voyage sans discussion et un **changement de comportement** demande un
#: arbitrage. Une ligne qui ne tranche pas laisse la question ouverte a
#: quelqu'un qui n'aura plus le contexte.
FORMES = ("ajout pur", "changement de comportement", "fichier neuf",
          "extraction", "aucun report")


def _texte_de_liaison() -> str:
    return LIAISON.read_text(encoding="utf-8")


def _lignes_du_tableau() -> dict[str, list[str]]:
    """`L<n>` -> les colonnes de sa ligne, telles qu'elles sont ecrites."""
    lignes = {}
    for ligne in _texte_de_liaison().splitlines():
        if not ligne.startswith("| L"):
            continue
        colonnes = [c.strip() for c in ligne.strip().strip("|").split("|")]
        lignes[colonnes[0]] = colonnes
    return lignes


def _modules_de_coeur() -> set[str]:
    """Les modules de `src/` qui ne sont **pas** dans le paquet `tui/`.

    C'est exactement le perimetre du registre, qui n'excepte que `tui/` : ce
    qui touche le coeur doit etre reporte, ce qui est ne dans la TUI voyage
    avec l'epic.

    **Les DONNEES du paquet comptent aussi, et ce n'etait pas vrai avant le
    2026-09-07.** La liaison de la branche d'empaquetage a deplace les trois
    schemas JSON de `_bmad-output/specs/` vers `src/mixed_media_utility/
    specs/` : ils sont devenus des fichiers DU PAQUET, que `hatchling` embarque
    et qu'`io/manifest.py` resout par un chemin relatif au module. Le registre
    les a acceptes -- il indexe des CHEMINS, pas des modules --, et cette
    fonction ne balayait que `*.py` : les trois entraient dans la liste de
    reference sans pouvoir jamais entrer dans la table de liaison, donc la
    frontiere rougissait sans qu'aucune ligne ecrite ne puisse la fermer.
    Mesure : cinq stems manquants (`manifest`, `metadata_matrix` et les trois
    `project.schema*`), dont trois structurellement inatteignables.

    Le balayage porte donc sur les fichiers **livres**, `.py` et donnees, et
    pas sur un glob large : `__pycache__` est exclu explicitement, faute de
    quoi chaque `.pyc` d'un arbre deja joue entrerait dans le perimetre et le
    verdict dependrait de l'ordre des courses.
    """
    source = _RACINE / "src" / "mixed_media_utility"
    livres = list(source.rglob("*.py")) + list(source.rglob("specs/*.json"))
    return {chemin.stem for chemin in livres
            if "tui" not in chemin.parts
            and "__pycache__" not in chemin.parts
            and chemin.name != "__init__.py"}


def _registre() -> set[str]:
    arbre = ast.parse(REGISTRE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.AnnAssign)
                and getattr(noeud.target, "id", "") == "CHANGEMENTS_ACCEPTES"):
            return {Path(chemin).stem
                    for chemin in ast.literal_eval(noeud.value)}
    raise AssertionError(
        f"CHANGEMENTS_ACCEPTES introuvable dans {REGISTRE.name}")


def _motif(module: str) -> re.Pattern:
    """Le module cite **comme du code**, jamais comme un mot francais.

    `progression`, `extraction` et `reconstruction` sont a la fois des noms de
    module et des mots de la langue de travail : un motif qui accepterait le
    mot nu ferait passer « le canal de progression » pour une citation de
    `progression.py`, et la mesure deviendrait fausse dans le sens qui ne se
    voit pas -- elle declarerait couverte une ligne qui ne l'est pas.
    """
    return re.compile(r"(?:^|[/`\s(])" + re.escape(module)
                      + r"(?:\.py\b|\.[A-Za-z_])")


def _modules_nommes_par_la_liaison() -> set[str]:
    """Les modules de coeur que la table designe dans sa colonne « ce qui
    change » -- celle qui dit ce que la ligne **reporte**.

    La colonne des motifs est volontairement exclue : elle cite des modules que
    la ligne ne change pas (`write_lot_output_frames` du cote cible,
    `compose_lot_plan` comme source d'une formule), et les compter ferait
    croire a une couverture qui n'existe pas.
    """
    coeur = _modules_de_coeur()
    nommes: set[str] = set()
    for colonnes in _lignes_du_tableau().values():
        cite = " ".join(re.findall(r"`([^`]+)`", colonnes[1]))
        nommes |= {module for module in coeur if _motif(module).search(cite)}
    return nommes


# ===========================================================================
# « la liaison est PREPAREE » -- les deux listes disent la meme chose
# ===========================================================================

def test_chaque_fichier_de_coeur_du_REGISTRE_a_sa_ligne_de_liaison():
    """`EPIC11-ARB-77` : « on fera la liaison avec main et les autres branches
    sur les modifications de coeur **par la suite** » -- verbatim.

    Une liaison remise se reconstitue de memoire si personne ne l'ecrit
    pendant qu'elle se fait. Le registre, lui, est tenu par une frontiere qui
    rougit des qu'un fichier de coeur bouge sans y entrer : c'est donc **lui**
    la liste de reference, et la table de liaison doit la couvrir entierement.
    Un fichier accepte au registre sans ligne de liaison est un report qu'on
    fera de memoire.
    """
    manquants = _registre() - _modules_nommes_par_la_liaison()
    assert manquants == set(), (
        "fichiers de coeur acceptes au registre mais absents de la table de "
        f"liaison : {sorted(manquants)}. Chacun doit gagner sa ligne, avec sa "
        "forme (ajout pur / changement de comportement) et son motif.")


def test_la_liaison_ne_NOMME_aucun_fichier_de_coeur_hors_du_registre():
    """Le sens inverse, et il n'est pas symetrique par politesse.

    Une ligne de liaison qui reporterait un fichier de coeur absent du registre
    dirait que l'Epic 11 touche quelque chose que la frontiere du registre
    croit intact -- donc que l'une des deux mesures ment. Les deux listes sont
    tenues a la main, et c'est exactement la situation ou elles derivent.
    """
    hors_registre = (_modules_nommes_par_la_liaison()
                     - _registre() - AMBIGUS)
    assert hors_registre == set(), (
        "la table de liaison reporte des fichiers de coeur que "
        f"CHANGEMENTS_ACCEPTES ne connait pas : {sorted(hors_registre)}")


def test_chaque_ligne_de_liaison_TRANCHE_entre_ajout_pur_et_changement():
    """« ce qui est un ajout pur et voyagera sans discussion, ce qui change un
    comportement et demandera un arbitrage » -- verbatim de l'en-tete du
    document, et c'est la seule distinction qui compte au report.

    Les lignes qui ne reportent **rien** (un ecart signale, un trou identique
    des deux cotes) ont le droit de ne pas trancher, mais elles doivent le dire
    en toutes lettres plutot que par une case vide : une case vide se lit comme
    un oubli, et se comble de memoire.
    """
    sans_forme = {
        numero: colonnes[2]
        for numero, colonnes in _lignes_du_tableau().items()
        if not any(mot in colonnes[2].lower() for mot in FORMES)
        and not colonnes[1].lower().startswith(("**non porte", "**asymetrie",
                                                "**trou"))}
    assert sans_forme == {}, (
        "lignes de liaison dont la colonne « forme » ne tranche pas : "
        f"{sans_forme}")


def test_chaque_ligne_de_liaison_porte_un_NUMERO_UNIQUE_et_contigu():
    """Le defaut que cette mesure ferme, et il avait deja mange cinq lignes.

    `_lignes_du_tableau` indexe **par numero**. Deux lignes portant `L40` ne
    rendent donc qu'une entree : la seconde ecrase la premiere, sans un mot.
    Constate le 2026-09-07 -- les lots de la story 11.11 avaient repris la
    numerotation a `L40` la ou la story 6.8 s'etait arretee a `L44`, et
    **cinq** lignes de liaison (`gui/atelier_scan`, `scan_output_frames`,
    `extraction_previz`, `declaration_de_rush`, `source_confirmation`) etaient
    invisibles aux trois mesures ci-dessus. Elles etaient ecrites, relues,
    commitees -- et non mesurees.

    C'est le mode de panne le plus couteux d'un document de liaison : il ne
    manque rien a la lecture humaine, et la frontiere qui est censee empecher
    la derive certifie une table dont elle n'a lu que les neuf dixiemes.

    La contiguite est mesuree avec l'unicite parce qu'elle attrape l'autre
    moitie du meme geste : un lot qui reprend la numerotation trop loin laisse
    un trou, et un trou dans une table de liaison se lit comme une ligne
    retiree -- donc comme un report qu'on aurait renonce a faire.
    """
    numeros = [int(numero) for numero in re.findall(
        r"^\| L(\d+) ", _texte_de_liaison(), flags=re.MULTILINE)]
    # Le volet d'anti-vacuite vient EN PREMIER, et pas par gout de l'ordre : sur
    # une table illisible, `max(numeros)` leverait un `ValueError` nu, c'est-a-dire
    # un rouge qui ne dit pas ce qui ne va pas.
    assert len(numeros) >= 22, f"{len(numeros)} ligne(s) de table reconnue(s)"
    doublons = sorted({n for n in numeros if numeros.count(n) > 1})
    assert doublons == [], (
        f"numeros de ligne employes deux fois : {['L%d' % n for n in doublons]}. "
        "La table est indexee par numero : la seconde ligne ecrase la premiere "
        "et sort du champ des trois mesures ci-dessus.")
    trous = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
    assert trous == [], (
        f"numeros absents de la table : {['L%d' % n for n in trous]}. Un trou "
        "se lit comme une ligne retiree, c'est-a-dire comme un report abandonne.")
    # Et le volet qui empeche les deux assertions ci-dessus de mesurer le vide :
    # si le motif de tete cessait de reconnaitre les lignes, les deux listes
    # seraient vides et le test passerait sans rien observer.
    assert len(numeros) == len(_lignes_du_tableau()), (
        f"{len(numeros)} ligne(s) brute(s) pour {len(_lignes_du_tableau())} "
        "entree(s) lues -- l'indexation en perd.")


def test_la_LECTURE_du_tableau_n_est_pas_vide(capsys):
    """Volet symetrique des trois mesures ci-dessus.

    Si le motif de lecture cessait de reconnaitre les lignes -- une colonne
    ajoutee, un `|` de tete retire, un renommage du fichier --, les ensembles
    compares seraient vides et les trois tests passeraient en n'observant
    rien. Les cardinaux sont bornes par le bas, et le registre est lu par le
    meme geste.
    """
    lignes = _lignes_du_tableau()
    assert len(lignes) >= 22, f"{len(lignes)} ligne(s) lue(s) dans la table"
    assert all(len(colonnes) == 5 for colonnes in lignes.values()), (
        "chaque ligne porte cinq colonnes : numero, ce qui change, forme, ou "
        "reporter, ce qu'il faudra decider")
    assert len(_registre()) >= 14, len(_registre())
    nommes = _modules_nommes_par_la_liaison()
    assert len(nommes) >= 12, sorted(nommes)
    # Et le motif de reconnaissance ne prend pas le mot francais pour le
    # module : sans cette derniere ligne, `_motif` pourrait etre elargi sans
    # qu'aucun test ne s'en apercoive.
    assert not _motif("progression").search("le canal de progression du scan")
    assert _motif("progression").search("`progression.EmetteurProgression`")


# ===========================================================================
# « elle n'est PAS poussee » -- rien n'est parti ailleurs
# ===========================================================================

#: Les branches **coupees depuis** `oc/epic-11-TUI`, qui contiennent donc ses
#: commits par FILIATION et non par report. `EPIC11-ARB-77` interdit de
#: pousser le travail de l'epic ailleurs *avant la liaison* ; il n'interdit
#: pas qu'une branche de travail naisse de celle-ci -- c'est meme le geste
#: normal quand une session parallele corrige un atelier.
#:
#: **Ce n'est pas un affaiblissement, et le volet symetrique le mesure** :
#: `test_les_branches_FILLES_declarees_ne_couvrent_ni_main_ni_un_autre_epic`
#: refuse qu'on y inscrive `main` ou une autre branche d'epic, c'est-a-dire
#: exactement les cibles de la liaison. La frontiere garde donc ses dents pour
#: ce qu'elle protege, et cesse d'accuser une filiation qu'on a autorisee.
#:
#: Une entree se retire quand sa branche est fondue : elle n'a alors plus de
#: raison d'exister, et la laisser masquerait un vrai report.
BRANCHES_FILLES: dict[str, str] = {
    "claude/epic-11-file-explorer-l5hca4":
        "Branche de LOT, RECOUPEE depuis `oc/epic-11-TUI` le 2026-09-07 pour "
        "les retours de recette d'Egan sur l'explorateur -- le bloquant << "
        "impossible d'atteindre les volumes par l'explorateur de fichiers >>. "
        "Elle contient le premier commit de la vague parce qu'elle en DESCEND. "
        "Le nom avait deja servi : la branche d'origine a ete reconciliee dans "
        "`oc/epic-11-TUI` le 2026-09-06 (commit `7af4d032d`, ZERO contenu), "
        "elle ne portait donc plus que de l'historique deja fondu, et la "
        "repartir de la tete courante ne perd rien. A retirer de cette table a "
        "sa fusion.",
    "claude/allegement-livraison-tui":
        "Branche de LOT, coupee depuis `oc/epic-11-TUI` le 2026-09-06 pour le "
        "brief de livraison d'Egan -- << pip et le script one-liner doivent "
        "livrer uniquement la TUI fonctionnelle sur un ordinateur totalement "
        "vierge >> (EPIC11-ARB-253, -254, -255). Elle contient le premier "
        "commit de la vague parce qu'elle en DESCEND : rien de l'epic n'y a "
        "ete reporte. A retirer de cette table a sa fusion. "
        "NOTE MESUREE DU 2026-09-06, qui deborde cette entree : au moment de "
        "l'ecrire, `git branch -r --contains` rend CINQUANTE-QUATRE branches "
        "distantes portant ce commit, dont cinquante-trois ne sont pas dans "
        "cette table. Ce banc rouge donc sur un arbre NON TOUCHE aussi -- "
        "verifie sur un worktree detache a `origin/oc/epic-11-TUI` le meme "
        "jour. Ce n'est pas une regression : c'est que la table n'a pas suivi "
        "la multiplication des branches de lot. Elargir la table aux 53 "
        "autres la viderait de son sens, ce que "
        "`test_les_branches_FILLES_declarees_ne_couvrent_ni_main_ni_un_autre_"
        "epic` interdit deja ; le remede est un nettoyage des branches "
        "fusionnees, et il est verse a `deferred-work.md`. "
        "FUSION DES DEUX ENTREES du 2026-09-07 : cette branche etait declaree DEUX FOIS apres la liaison des seize branches, une cle en double dans un dict litteral ne gardant silencieusement que la DERNIERE -- donc pas celle-ci. Ce que la disparue disait de plus, et qui est conserve : base commune `c1803e0e`, dans la vague ; son sommet n'etait contenu par aucune autre branche distante, donc rien n'en est parti vers une cible de liaison.",
    "claude/scan-pdf-et-calibration":
        "Branche coupee depuis `oc/epic-11-TUI` le 2026-09-01 (source "
        "declaree de la session : `refs/heads/oc/epic-11-TUI`) pour corriger "
        "les trois defauts d'usage reel que le proprietaire a trouves sur "
        "l'atelier Scan -- PDF refuse a l'Espace, navigation du formulaire de "
        "calibration, absence d'ecran de progression. Elle contient le "
        "premier commit de la vague parce qu'elle en DESCEND, pas parce que "
        "quoi que ce soit y a ete reporte : aucun commit de l'epic n'y a ete "
        "pousse depuis, et c'est `oc/epic-11-TUI` qui la fusionnera apres sa "
        "revue en trois couches. A retirer de cette table au moment de cette "
        "fusion.",
    "lot-B5-11-8":
        "Branche de LOT, coupee depuis `oc/epic-11-TUI` le 2026-09-03 pour le "
        "cablage du point d'entree Exports (lot B5 de la story 11.8), et "
        "poussee comme commit de sauvegarde -- la session avait deja perdu "
        "trois courses d'agent sur des erreurs 529 ce jour-la, et `CLAUDE.md` "
        "exige de pousser un livrable partiel plutot que de risquer un "
        "livrable complet perdu. Elle contient le premier commit de la vague "
        "parce qu'elle en DESCEND. **Deja fusionnee** dans `oc/epic-11-TUI` "
        "par `c014c732` : cette entree est donc a retirer AVEC la branche "
        "distante, des que le nettoyage des branches de lot se fait. Elle est "
        "ecrite plutot que la branche supprimee dans la foulee parce que "
        "supprimer une reference distante est un geste vers l'exterieur, et "
        "qu'il revient au proprietaire de le decider.",
    "claude/epic6_6-7_6-8":
        "**Ni une fille au sens ci-dessus, ni un report -- un TROISIEME cas "
        "que cette table ne nommait pas**, et le dire vaut mieux que l'y "
        "ranger en silence. Cette branche n'est pas coupee depuis "
        "`oc/epic-11-TUI` : c'est la session EPIC 6, qui a FUSIONNE notre "
        "branche dans la sienne le 2026-09-03 (`7ebbb28f`, « Liaison de "
        "oc/epic-11-TUI : la story 6.8 arrive ») pour reprendre la story 6.8 "
        "qui en venait. Elle porte donc nos commits par son geste a elle, pas "
        "par un report du notre -- ce qu'`EPIC11-ARB-77` interdit est de "
        "POUSSER ailleurs, et rien n'a ete pousse la. Mesure qui l'etablit : "
        "notre `HEAD` n'y est PAS contenu, et elle porte quatre commits que "
        "nous n'avons pas ; un report aurait la forme inverse. "
        "A retirer de cette table quand la 6.7 et la 6.8 seront revenues.",
    "lot-A-11-9":
        "Branche de LOT, coupee depuis `oc/epic-11-TUI` le 2026-09-03 pour le "
        "lot A de la story 11.9 (la derivation du manuel des raccourcis). Elle "
        "contient le premier commit de la vague parce qu'elle en DESCEND. "
        "**Le motif du worktree separe est une regle de `CLAUDE.md`, pas un "
        "confort** : une mesure tournait dans l'arbre principal pour le lot A "
        "de la 11.11, et editer un arbre pendant qu'une mesure y tourne est "
        "precisement ce que le depot interdit. Deux lots simultanes "
        "demandaient donc deux arbres, donc deux branches. "
        "**Contenu deja INTEGRE** dans `oc/epic-11-TUI`, mais par des "
        "commits AUX SHA DIFFERENTS : un `git pull --rebase` lance juste "
        "apres la fusion a APLATI le commit de fusion et rejoue les trois "
        "commits du lot. `git merge-base --is-ancestor lot-A-11-9 HEAD` "
        "rend donc FAUX alors que rien n'est perdu -- le dire ici evite a "
        "une session suivante de conclure a une fusion manquante et de "
        "refusionner. Cette entree est "
        "a retirer AVEC la branche distante, des que le nettoyage des "
        "branches de lot se fait. Elle est ecrite plutot que la branche "
        "supprimee dans la foulee parce que supprimer une reference "
        "distante est un geste vers l'exterieur, et qu'il revient au "
        "proprietaire de le decider -- meme traitement que "
        "`origin/lot-B5-11-8` ci-dessus.",
}


def _branches_distantes(*args: str) -> list[str]:
    resultat = subprocess.run(
        ["git", "branch", "-r", *args],
        cwd=_RACINE, capture_output=True, text=True)
    assert resultat.returncode == 0, resultat.stderr
    return sorted(ligne.strip() for ligne in resultat.stdout.splitlines()
                  if ligne.strip() and "->" not in ligne)


#: Les FAMILLES de branches filles, par prefixe -- et c'est un mecanisme, pas
#: une commodite.
#:
#: **Le defaut que ce registre ferme** (2026-09-07). `BRANCHES_FILLES` nomme
#: une branche a la fois, avec son motif ecrit. C'est juste tant qu'il y en a
#: trois ; a **cinquante-quatre**, la table cesse d'etre tenue et la frontiere
#: rougit en permanence -- c'est-a-dire qu'elle cesse de mesurer quoi que ce
#: soit, puisqu'un rouge qui ne bouge plus ne se lit plus. Constate sur la
#: course `nuit0907` : cinquante-quatre branches portees, quatre declarees.
#:
#: **Pourquoi un prefixe et pas un elargissement du motif.** Les branches de la
#: vague naissent par lots, par revues et par sauvegardes, et leur nom le dit
#: deja -- c'est une convention du depot, pas un hasard. Ce que la frontiere
#: doit continuer d'attraper, ce sont les branches qui ne suivent PAS cette
#: convention : `main`, une branche d'un autre epic, une branche de report. Un
#: prefixe declare avec son motif garde cette distinction ; une liste qui
#: grandit sans fin la perd.
#:
#: **Ce que ce registre ne relache pas, et deux volets symetriques le
#: mesurent** : aucun prefixe ne peut couvrir `main`, `master` ni une branche
#: d'un autre epic (`..._ne_couvrent_ni_main_ni_un_autre_epic`), et un prefixe
#: qui ne couvre plus aucune branche vivante est un ecart perime qui se retire
#: (`..._sont_toutes_VIVANTES`).
FAMILLES_DE_BRANCHES_FILLES: dict[str, str] = {
    "lot-":
        "Branche de LOT, coupee depuis `oc/epic-11-TUI` pour un lot de story "
        "et poussee comme commit de sauvegarde -- `CLAUDE.md` exige de "
        "pousser un livrable partiel plutot que de risquer un livrable "
        "complet perdu, et une session de nuit en produit un par lot. Elle "
        "contient le premier commit de la vague parce qu'elle en DESCEND.",
    "cloture-":
        "Branche de CLOTURE d'une story ou d'un arbitrage, meme filiation et "
        "meme motif que `lot-` : elle porte la derniere passe d'un chantier "
        "avant sa fusion dans `oc/epic-11-TUI`.",
    "revue-":
        "Branche de REVUE en trois couches (`CLAUDE.md`, regle 5). Une couche "
        "y travaille sans toucher a la branche de la story, ce qui est "
        "precisement ce qui permet aux trois de tourner en parallele.",
    "revue/":
        "Meme chose que `revue-`, ecrit avec un separateur de hierarchie. Les "
        "deux formes coexistent dans le depot ; les declarer toutes les deux "
        "vaut mieux qu'elargir le motif, qui prendrait alors `revue` nu.",
    "sauvegarde/":
        "Branche de SAUVEGARDE d'une session, poussee pour ne pas perdre un "
        "arbre de travail quand une coupure de contexte menace. Elle n'est "
        "jamais une cible de report -- c'est meme l'inverse de ce qu'un "
        "report est.",
}


def _noms_des_distants() -> list[str]:
    """Les noms de depot distant de CE clone, les plus longs d'abord.

    Lus plutot que supposes : `CLAUDE.md` en impose deja deux ici (`origin`
    vers le depot de travail, `public` vers la distribution), et la session
    voisine qui a signale le defaut du 2026-09-07 en portait un troisieme,
    `dev`. Les plus longs d'abord parce qu'un nom peut etre le prefixe d'un
    autre (`dev` et `dev-old`) : retirer le plus court laisserait un tiret.
    """
    resultat = subprocess.run(["git", "remote"],
                              cwd=_RACINE, capture_output=True, text=True)
    if resultat.returncode != 0:
        return []
    return sorted((ligne.strip() for ligne in resultat.stdout.splitlines()
                   if ligne.strip()), key=len, reverse=True)


def _sans_le_distant(branche: str) -> str:
    """`dev/oc/epic-11-TUI` -> `oc/epic-11-TUI`, quel que soit le nom du clone.

    Ne retire **que** le premier segment, et seulement s'il nomme un distant
    reel. Une branche qui s'appellerait `origin-de-secours/x` n'est donc pas
    amputee : le separateur est exige.
    """
    for distant in _noms_des_distants():
        if branche.startswith(f"{distant}/"):
            return branche[len(distant) + 1:]
    return branche


def _est_une_fille(branche: str) -> bool:
    """Declaree nommement, ou couverte par une famille declaree.

    La comparaison se fait sur des noms **sans nom de clone** des deux cotes.
    Les cles de `BRANCHES_FILLES` etaient ecrites `origin/...` : un clone dont
    le distant s'appelle autrement les manquait alors TOUTES, ce qui est la
    moitie du defaut du 2026-09-07. Elles ont perdu ce prefixe -- une table de
    BRANCHES n'a pas a porter le nom d'un depot distant, qui est une
    convention locale au clone. Les motifs, eux, gardent leurs `origin/...` :
    ils racontent l'histoire d'une branche, ils ne decident d'aucun verdict.
    """
    court = _sans_le_distant(branche)
    if court in BRANCHES_FILLES:
        return True
    return any(court.startswith(prefixe)
               for prefixe in FAMILLES_DE_BRANCHES_FILLES)


#: Les CIBLES de liaison que la vague a DEJA atteintes, sur ordre d'Egan.
#:
#: **Un troisieme cas que ni `BRANCHES_FILLES` ni le refus ne nomment.** Une
#: fille DESCEND de la branche de l'epic ; une cible de liaison est l'inverse,
#: et `test_les_branches_FILLES_declarees_ne_couvrent_ni_main_ni_un_autre_epic`
#: interdit -- a juste titre -- de l'y ranger. Mais `EPIC11-ARB-77` ne dit pas
#: << jamais >>, il dit << **pour le moment** [...] on fera la liaison [...]
#: **par la suite** >>. La suite a commence : Egan a ordonne la chaine de
#: release du 2026-09-07 -- cloture, fusion avec `main`, fusion de la branche
#: de packaging, commit orphelin sur le depot public, release.
#:
#: Une cible ne s'y inscrit donc **pas** parce qu'elle porte nos commits, mais
#: parce que la liaison vers elle est FAITE et que le geste est le notre. Le
#: volet symetrique ci-dessous le mesure, plutot que de croire cette phrase :
#: la branche declaree doit contenir un commit de fusion que NOUS avons ecrit.
#: Une cible qui recevrait nos commits par un report anticipe -- ce que
#: l'arbitrage interdit -- ne le contiendrait pas, et rougirait encore.
#:
#: `main` n'y est pas et ne doit pas y etre tant que sa fusion n'est pas
#: faite : c'est l'etape suivante de la chaine, et cette frontiere est ce qui
#: dira qu'elle a eu lieu.
CIBLES_DE_LIAISON_ATTEINTES: dict[str, str] = {
    "claude/epic-8-packaging":
        "Branche de PACKAGING, deuxieme etape de la chaine de release ordonnee "
        "par Egan le 2026-09-07 (<< cloture -> FUSION AVEC MAIN -> FUSION DE LA "
        "BRANCHE DE PACKAGING -> commit orphelin -> release >>). Elle porte le "
        "premier commit de la vague depuis que sa session a fait un "
        "fast-forward sur `bdc2226ab`, le commit ou NOUS avons fusionne SA "
        "branche dans la notre -- c'est-a-dire par son geste a elle sur notre "
        "liaison, jamais par un report du notre. Mesure qui l'etablit et que le "
        "volet symetrique rejoue : `bdc2226ab` est un ancetre de cette branche. "
        "A retirer de cette table quand la chaine sera close et la frontiere "
        "avec elle.",

    "main":
        "PREMIERE etape de la meme chaine, franchie le 2026-09-08. "
        "`EPIC11-ARB-77` remettait la liaison avec `main` a plus tard ; Egan "
        "l'a ordonnee le 2026-09-07, et elle a eu lieu -- `main` a ete "
        "avance en fast-forward sur cette branche, donc il porte desormais "
        "nos commits ET nos fusions. Mesure qui l'etablit, et que le volet "
        "symetrique rejoue : `git merge-base --is-ancestor bdc2226ab "
        "origin/main` et `... 343a50bdd origin/main` rendent zero. "
        "C'est l'evenement que ce fichier tout entier existe pour attendre : "
        "la table n'exempte pas un report anticipe, elle enregistre que la "
        "liaison a ete FAITE. A retirer avec la frontiere quand la chaine "
        "sera close.",
}


def _fusions_que_nous_avons_ecrites() -> list[str]:
    """Les fusions faites SUR CETTE LIGNE **depuis le debut de la vague**.

    **Les DEUX bornes sont ce qui fait la mesure, et chacune a ete payee par un
    mutant survivant** -- `N1` (declarer `main`) et `N1b` (declarer
    `claude/epic-7`) ont survecu DEUX redactions avant celle-ci :

    * sans `--first-parent`, `git rev-list --merges HEAD` rend les fusions
      HERITEES -- celles que `main` a faites chez elle et qui sont arrivees ici
      par une liaison. Toute cible qui partage notre histoire en contient une ;
    * sans `BASELINE..`, `--first-parent` seul ne suffit toujours pas : le
      parcours finit par entrer dans l'histoire de `main`, dont il rend les
      propres fusions -- que `main` contient evidemment. C'est le mutant qui a
      survecu au premier correctif, et il a fallu le rejouer pour le voir.

    Bornees aux deux, il ne reste que les fusions dont NOUS sommes l'auteur du
    geste, faites depuis que la vague existe. Une cible qui en porte une nous a
    repris ; une cible qui n'en porte aucune a recu nos commits autrement,
    c'est-a-dire par un report -- ce qu'`EPIC11-ARB-77` interdit.
    """
    resultat = subprocess.run(
        ["git", "rev-list", "--merges", "--first-parent", f"{BASELINE}..HEAD"],
        cwd=_RACINE, capture_output=True, text=True)
    if resultat.returncode != 0:                 # pragma: no cover - defensif
        return []
    return resultat.stdout.split()


def test_AUCUN_commit_de_la_vague_n_est_pousse_sur_UNE_AUTRE_branche():
    """`EPIC11-ARB-77`, la moitie qui interdit : « **Pour le moment** importe
    le necessaire **dans cette branche**, on fera la liaison avec main et les
    autres branches sur les modifications de coeur **par la suite**. »

    L'AC 11.4 de la fiche le redit : « Rien n'est pousse ailleurs que sur
    `oc/epic-11-TUI`. » La mesure porte sur le **premier** commit de la vague :
    c'est celui qu'un report anticipe aurait emporte le premier, et le seul
    dont la presence ailleurs ne puisse pas s'expliquer par un ancetre commun.
    """
    premier = subprocess.run(
        ["git", "rev-list", "--ancestry-path", f"{BASELINE}..HEAD"],
        cwd=_RACINE, capture_output=True, text=True)
    assert premier.returncode == 0, premier.stderr
    commits = premier.stdout.split()
    assert commits, (
        f"aucun commit entre {BASELINE} et HEAD : la mesure porterait sur "
        "rien")

    porteuses = _branches_distantes("--contains", commits[-1])
    inattendues = {branche for branche in porteuses
                   if _sans_le_distant(branche) != BRANCHE
                   and not _est_une_fille(branche)
                   and _sans_le_distant(branche)
                   not in CIBLES_DE_LIAISON_ATTEINTES}
    assert not inattendues, (
        f"le premier commit de la vague ({commits[-1][:7]}) est contenu dans "
        f"{sorted(inattendues)} : EPIC11-ARB-77 remet la liaison a plus tard, "
        f"rien ne doit etre pousse ailleurs que sur {BRANCHE}. Si une branche "
        "est une FILLE de celle-ci et non un report, elle s'inscrit dans "
        "BRANCHES_FILLES avec son motif -- ou dans "
        "FAMILLES_DE_BRANCHES_FILLES si elle suit une convention de nommage "
        "du depot. Si c'est une CIBLE de liaison que la chaine de release a "
        "deja atteinte, elle s'inscrit dans CIBLES_DE_LIAISON_ATTEINTES, qui "
        "exige en retour qu'un commit de fusion ECRIT PAR NOUS y soit "
        "contenu.")


def test_chaque_CIBLE_de_liaison_declaree_porte_une_FUSION_QUE_NOUS_AVONS_FAITE():
    """Le volet qui empeche `CIBLES_DE_LIAISON_ATTEINTES` d'etre une porte.

    Sans lui, ce registre serait exactement le trou qu'`EPIC11-ARB-77` ferme :
    il suffirait d'y ecrire le nom d'une branche pour que le report anticipe
    qu'on vient d'y faire cesse de rougir. La declaration ne prouve rien -- la
    topologie, si.

    **Ce qui distingue une liaison d'un report, et c'est mesurable.** Une
    liaison est un geste que NOUS avons fait : elle laisse dans notre
    historique un commit de fusion, que la cible porte ensuite si elle nous a
    repris. Un report est l'inverse -- nos commits arrivent chez elle sans
    qu'aucune de nos fusions ne l'atteigne. La cible declaree doit donc
    contenir au moins une de nos fusions.
    """
    nos_fusions = _fusions_que_nous_avons_ecrites()
    if not nos_fusions:
        pytest.skip("aucune fusion dans cet historique : rien a rapprocher")
    distantes = {_sans_le_distant(branche): branche
                 for branche in _branches_distantes()}
    for cible, motif in sorted(CIBLES_DE_LIAISON_ATTEINTES.items()):
        assert motif.strip(), f"{cible} est exemptee sans motif ecrit"
        complet = distantes.get(cible)
        assert complet, (
            f"`{cible}` est declaree cible de liaison atteinte mais n'est plus "
            "une branche distante connue : une exemption perimee se retire")
        porteuses = {_sans_le_distant(nom)
                     for fusion in nos_fusions
                     for nom in _branches_distantes("--contains", fusion)}
        assert cible in porteuses, (
            f"`{cible}` porte nos commits sans porter AUCUNE de nos fusions : "
            "c'est la forme d'un REPORT, que `EPIC11-ARB-77` interdit, et non "
            "celle d'une liaison. Le registre ne peut pas la couvrir.")


def test_les_fusions_QUE_NOUS_AVONS_FAITES_ne_sont_AUCUNE_de_celles_de_main():
    """Le volet qui mesure le BORNAGE lui-meme, et il fallait le poser a part.

    Les mutants `N4` (retrait de `--first-parent`) et `N5` (retrait de
    `BASELINE..`) ont SURVECU au volet du registre, et le motif est instructif :
    avec un registre sain -- des cibles qui portent vraiment nos fusions --,
    relacher le parcours ne change aucun verdict. La strictesse du bornage n'est
    observable que **combinee** a une entree fautive, or une entree fautive est
    justement ce qu'on ne laisse pas dans l'arbre. Cette frontiere mesure donc
    le bornage directement, sans passer par le registre.

    **L'ETALON A CHANGE LE 2026-09-08, ET LA PREMIERE CORRECTION ETAIT UN FAUX
    VERT.** La redaction d'origine comparait a `origin/main` : une fusion
    << que nous avons faite >> ne pouvait pas etre une fusion que `main`
    portait deja. Le fast-forward de `main` sur cette branche a renverse la
    phrase -- `main` porte desormais nos QUATRE-VINGT-DEUX fusions, et le test
    les a declarees heritees en bloc. La correction suivante figeait `main` a
    son etat d'avant l'adoption (`f189b412c`) ; **elle a laisse N4 survivre**,
    et la mesure dit pourquoi : sur les 109 fusions que le mutant rend, ce
    `main`-la n'en est l'ancetre d'AUCUNE, les fusions heritees venant d'un
    `main` plus recent, absorbe par nos liaisons du 2026-09-01 et du
    2026-09-07. Un etalon exterieur trop ANCIEN ne mesure rien et l'annonce
    vert -- exactement le mode de panne que ce fichier existe pour fermer.
    Mesure des trois candidats, sur les 109 fusions du mutant :

        `f189b412c` (main d'avant l'adoption)   0 attrapee   -> faux vert
        `4f441ba^2` (main absorbe le 09-01)     4 attrapees
        `417979f4b^2` (main absorbe le 09-07)   6 attrapees

    **L'etalon est donc STRUCTUREL et non plus un nom.** Une fusion heritee est
    une fusion de `BASELINE..HEAD` qui n'est PAS sur notre ligne de premier
    parent : elle est arrivee par le second parent d'une de nos liaisons. Il y
    en a 27 dans cet arbre, contre 6 pour le meilleur etalon exterieur. C'est
    la meme doctrine que celle que `CLAUDE.md` tire de la bascule d'`origin` :
    on ne se mesure pas contre un nom qu'un tiers reecrit.

    **Ce que cette frontiere ne prouve PAS, dit plutot que tu** : elle re-derive
    << notre ligne >> par le meme `--first-parent` que la fonction mesuree. Une
    mutation qui relacherait les DEUX du meme geste survivrait. Le second volet
    -- aucune de nos fusions n'est anterieure a `BASELINE` -- ne depend, lui,
    d'aucun parcours, et c'est lui qui tue `N5`.
    """
    nos_fusions = _fusions_que_nous_avons_ecrites()
    assert nos_fusions, (
        "aucune fusion depuis le debut de la vague : la mesure ci-dessous "
        "serait vraie sans rien mesurer")

    toutes = subprocess.run(
        ["git", "rev-list", "--merges", f"{BASELINE}..HEAD"],
        cwd=_RACINE, capture_output=True, text=True)
    notre_ligne = subprocess.run(
        ["git", "rev-list", "--merges", "--first-parent", f"{BASELINE}..HEAD"],
        cwd=_RACINE, capture_output=True, text=True)
    if toutes.returncode != 0 or notre_ligne.returncode != 0:
        # **Ce n'est pas a ce banc de trancher**, et la frontiere negative de
        # `test_regime_du_depot.py` l'a dit avant qu'aucun humain ne le voie.
        # Le `git rev-list` echoue ici pour UNE raison : `BASELINE` est
        # inatteignable -- ce qui est vrai d'un clone tronque comme de
        # l'orphelin public, et les deux appellent des verdicts opposes.
        echoue_ou_saute(
            _RACINE, BASELINE,
            f"commit de reference {BASELINE} inatteignable : le bornage de "
            "cette frontiere ne s'evalue pas, et un skip se lirait comme un "
            "vert. Arbre exporte, historique tronque ou clone superficiel "
            "(`git fetch --unshallow`)")
    heritees = set(toutes.stdout.split()) - set(notre_ligne.stdout.split())
    assert heritees, (
        "aucune fusion HERITEE dans cet historique : les deux parcours "
        "rendent le meme ensemble, donc la mesure ci-dessous serait vraie "
        "sans rien observer. C'est le volet d'anti-vacuite, et il vient avant "
        "l'assertion pour que le rouge nomme la cause")

    empruntees = sorted(set(nos_fusions) & heritees)
    assert not empruntees, (
        f"{[c[:7] for c in empruntees]} sont rendues comme << nos fusions >> "
        "alors qu'elles ne sont pas sur notre ligne de premier parent : ce "
        "sont des fusions HERITEES, arrivees par le second parent d'une de nos "
        "liaisons. Un registre de cibles de liaison bati dessus exempterait "
        "n'importe quel nom qu'on y ecrirait -- c'est le mutant `N1`.")

    anterieures = [fusion for fusion in nos_fusions
                   if subprocess.run(
                       ["git", "merge-base", "--is-ancestor", fusion, BASELINE],
                       cwd=_RACINE, capture_output=True).returncode == 0]
    assert not anterieures, (
        f"{[c[:7] for c in anterieures]} sont rendues comme << nos fusions >> "
        f"alors qu'elles sont ANTERIEURES a {BASELINE} : le parcours a debordé "
        "la vague et rend les fusions de `main`, que `main` contient "
        "evidemment. C'est le mutant `N5`, et il ne se voit pas autrement.")


def test_une_CIBLE_de_liaison_n_est_JAMAIS_declaree_aussi_comme_FILLE():
    """Les deux registres disent des choses INVERSES : une branche dans les
    deux rendrait le verdict dependant de l'ordre de lecture.

    Une fille DESCEND de la branche de l'epic et y reviendra ; une cible de
    liaison la RECOIT. La meme branche ne peut pas etre les deux, et si elle
    l'etait, le motif ecrit dans l'une des deux tables serait faux -- donc
    la trace ecrite que ces tables existent pour porter le serait aussi.
    """
    communes = set(CIBLES_DE_LIAISON_ATTEINTES) & set(BRANCHES_FILLES)
    assert not communes, (
        f"{sorted(communes)} est declaree a la fois FILLE et CIBLE de liaison "
        "atteinte : l'un des deux motifs est faux")
    couvertes_par_famille = [cible for cible in CIBLES_DE_LIAISON_ATTEINTES
                             if any(cible.startswith(prefixe) for prefixe
                                    in FAMILLES_DE_BRANCHES_FILLES)]
    assert not couvertes_par_famille, (
        f"{couvertes_par_famille} tombe deja sous une famille de branches "
        "filles : la declarer cible de liaison est contradictoire")


def test_les_branches_FILLES_declarees_ne_couvrent_ni_main_ni_un_autre_epic():
    """Le volet symetrique de la mesure ci-dessus : sans lui, `BRANCHES_FILLES`
    pourrait etre elargi jusqu'a vider la frontiere de son sens.

    Une branche fille est **coupee depuis** `oc/epic-11-TUI` et destinee a y
    revenir ; elle contient donc nos commits par filiation, pas par report.
    `main` et les branches d'autres epics sont exactement l'inverse : ce sont
    les CIBLES de la liaison qu'`EPIC11-ARB-77` remet a plus tard, et aucune
    ne peut jamais entrer dans cette table.
    """
    interdits = ("main", "master", "epic-7", "epic-5", "epic-10")
    for nom, motif in BRANCHES_FILLES.items():
        assert motif.strip(), f"{nom} est exempte sans motif ecrit"
        court = _sans_le_distant(nom)
        assert not any(court == i or court.startswith(f"{i}/") or f"/{i}" in court
                       for i in interdits), (
            f"{nom} ne peut pas etre declaree branche fille : c'est une cible "
            "de liaison, pas une branche coupee depuis celle-ci")
        assert court != BRANCHE, (
            "la branche de travail n'est pas sa propre fille")

    # Et le meme refus sur les FAMILLES, qui sont la vraie surface d'attaque :
    # un prefixe couvre tout ce qui commence par lui, donc un prefixe trop
    # court -- ou vide -- exempterait le depot entier d'un seul caractere. Le
    # sens de la mesure est INVERSE de celui du dessus : on ne regarde pas si
    # l'entree ressemble a une cible, on regarde si une cible ressemble a
    # l'entree.
    cibles = [*interdits, BRANCHE,
              "claude/epic-7", "oc/epic-11-TUI"]
    for prefixe, motif in FAMILLES_DE_BRANCHES_FILLES.items():
        assert motif.strip(), f"la famille {prefixe!r} est declaree sans motif"
        assert len(prefixe) >= 4, (
            f"prefixe {prefixe!r} trop court : une famille couvre TOUT ce qui "
            "commence par elle")
        # Le rapprochement se fait dans LES DEUX SENS, et la seconde moitie
        # n'est pas du zele : `main-` ne couvre pas `main`, mais il ouvre la
        # famille sur l'espace de nommage d'une cible de liaison, ou la
        # prochaine branche s'appellera `main-report-du-scan`. Mesure faite --
        # avec le seul sens `cible.startswith`, un prefixe `main-truc` passait,
        # et seule la vivacite l'attrapait, c'est-a-dire par accident.
        couvertes = [cible for cible in cibles
                     if cible.startswith(prefixe) or prefixe.startswith(cible)]
        assert not couvertes, (
            f"la famille {prefixe!r} couvrirait {couvertes}, ou vit dans leur "
            "espace de nommage : ce sont les cibles de la liaison, pas des "
            "branches coupees depuis celle-ci")


def test_les_FAMILLES_de_branches_filles_sont_toutes_VIVANTES():
    """Volet symetrique : un prefixe perime relacherait la frontiere sans
    qu'aucun rouge ne le dise.

    Une famille qui ne couvre plus aucune branche distante n'exempte plus rien
    aujourd'hui -- mais elle exemptera la premiere branche qui reprendra le
    nom demain, et personne ne saura qu'un ecart existait. Meme discipline que
    pour `BRANCHES_FILLES`, dont le commentaire dit deja qu'une entree se
    retire quand sa branche est fondue.

    **Le saut est STRUCTUREL** : dans un clone qui n'a fetche que la branche de
    travail, il n'y a rien a comparer. C'est la meme forme de saut que celui de
    `test_politiques_du_depot.py` devant un `origin/main` hors d'atteinte, et
    non un drapeau qu'on oublierait de rallumer.
    """
    distantes = [_sans_le_distant(branche)
                 for branche in _branches_distantes()]
    if len(distantes) <= 3:
        pytest.skip(f"clone sans branches soeurs ({distantes}) : la vivacite "
                    "d'un prefixe n'a rien contre quoi se mesurer")
    mortes = {prefixe for prefixe in FAMILLES_DE_BRANCHES_FILLES
              if not any(nom.startswith(prefixe) for nom in distantes)}
    assert mortes == set(), (
        f"familles de branches filles qui ne couvrent plus rien : "
        f"{sorted(mortes)}. Une exemption perimee se retire ; laissee la, elle "
        "exemptera en silence la prochaine branche qui reprendra le nom.")


def test_AUCUNE_branche_n_est_declaree_DEUX_FOIS_dans_la_table():
    """Le defaut que la liaison des seize branches a produit, le 2026-09-07.

    **Pourquoi aucun test existant ne pouvait le voir.** Une cle repetee dans
    un dict litteral n'est ni une erreur ni un avertissement en Python : la
    DERNIERE gagne, les precedentes disparaissent. La table restait donc
    exemptante, sa longueur ne bougeait pas d'un cran visible, et le motif
    perdu -- ici la note mesuree des cinquante-quatre branches distantes --
    s'evanouissait sans une ligne de sortie.

    Le regime qui le fabrique est celui d'aujourd'hui, pas un cas d'ecole :
    deux sessions ajoutent la meme branche a la table, chacune avec le motif
    qu'elle a mesure, et la fusion les met cote a cote. C'est une collision de
    la meme famille que celle des numeros d'arbitrage.

    La mesure porte sur la SOURCE et non sur le dict construit, puisque le
    dict, lui, a deja perdu le doublon au moment ou on pourrait l'interroger.
    """
    arbre = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.AnnAssign)
                and getattr(noeud.target, "id", "") == "BRANCHES_FILLES"):
            continue
        cles = [cle.value for cle in noeud.value.keys
                if isinstance(cle, ast.Constant)]
        doublons = sorted({cle for cle in cles if cles.count(cle) > 1})
        assert not doublons, (
            f"{doublons} est declaree plusieurs fois dans BRANCHES_FILLES. "
            "Python garde SILENCIEUSEMENT la derniere : les motifs des "
            "precedentes sont perdus sans un mot. Fusionner les entrees en "
            "une seule, en conservant ce que chacune disait de plus.")
        break
    else:
        raise AssertionError("BRANCHES_FILLES introuvable dans la source")


def test_le_nom_du_DEPOT_DISTANT_ne_change_RIEN_a_la_mesure(monkeypatch):
    """Le defaut du 2026-09-07, mesure en faisant VARIER le nom du distant.

    La regle des fabriques de `CLAUDE.md` s'applique ici aux **modes** : une
    garde qui ne joue qu'un seul nom de distant mesure un seul clone et
    l'annonce verte. Trois noms sont joues, dont celui qui a mordu (`dev`), et
    la mesure doit rendre le meme verdict pour les trois.
    """
    for distant in ("origin", "dev", "amont-de-travail"):
        # On ne touche pas au clone : on injecte les noms de distants, que
        # `_sans_le_distant` relit a chaque appel.
        monkeypatch.setitem(globals(), "_noms_des_distants",
                            lambda d=distant: [d])
        assert _sans_le_distant(f"{distant}/oc/epic-11-TUI") == BRANCHE, (
            f"avec un distant nomme {distant!r}, la branche de l'epic n'est "
            "plus reconnue comme elle-meme : c'est exactement le defaut que la "
            "session Outillage a mesure, ou la frontiere comptait la branche "
            "qu'elle protege parmi les branches interdites")
        assert _est_une_fille(f"{distant}/claude/scan-pdf-et-calibration"), (
            f"avec un distant nomme {distant!r}, les exemptions nommees de "
            "BRANCHES_FILLES sont toutes manquees")
        assert _est_une_fille(f"{distant}/lot-A-11-9")


def test_un_nom_qui_n_est_PAS_un_distant_n_est_PAS_ampute(monkeypatch):
    """Le volet symetrique, sans lequel le test ci-dessus se satisferait d'un
    retrait aveugle du premier segment.

    Une branche `oc/epic-11-TUI` porte deja un segment avant son nom, et une
    branche pourrait s'appeler `origin-de-secours/x` : ni l'une ni l'autre ne
    doit perdre quoi que ce soit.
    """
    monkeypatch.setitem(globals(), "_noms_des_distants", lambda: ["origin"])
    assert _sans_le_distant("oc/epic-11-TUI") == "oc/epic-11-TUI"
    assert _sans_le_distant("origin-de-secours/x") == "origin-de-secours/x"
    assert _sans_le_distant("origin/oc/epic-11-TUI") == "oc/epic-11-TUI"


def test_le_module_ne_code_AUCUN_nom_de_distant_en_dur():
    """Frontiere NEGATIVE : aucun test positif ne verrait revenir un
    `"origin/..."` code en dur dans une comparaison.

    Les **motifs** de `BRANCHES_FILLES` peuvent citer `origin/` en prose -- ils
    racontent l'histoire d'une branche. Ce qui est interdit, c'est un
    `removeprefix` d'un nom de clone, c'est-a-dire un endroit ou le nom du
    clone deciderait du verdict.

    **La mesure porte sur le CODE, jamais sur le texte du fichier**, et c'est
    la premiere version de cette frontiere qui l'a appris : ecrite en
    `motif not in source`, elle s'attrapait **elle-meme** -- son propre
    docstring cite le motif qu'elle interdit. Une frontiere negative qui lit
    la prose mesure sa propre redaction. L'arbre syntaxique ne voit que les
    appels.
    """
    arbre = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        if not (isinstance(fonction, ast.Attribute)
                and fonction.attr == "removeprefix"):
            continue
        for argument in noeud.args:
            if not (isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)):
                continue
            assert "/" not in argument.value, (
                f"`removeprefix({argument.value!r})` a la ligne "
                f"{noeud.lineno} code un nom de depot distant en dur. Ce nom "
                "est une convention LOCALE au clone -- `CLAUDE.md` en impose "
                "deja deux ici, `origin` vers le depot de travail et `public` "
                "vers la distribution, et la session qui a mesure le defaut du "
                "2026-09-07 en portait un troisieme. Passer par "
                "`_sans_le_distant`, qui LIT les distants du clone.")


def test_les_AUTRES_branches_sont_bien_CONNUES_du_depot():
    """Volet symetrique, et sans lui le test ci-dessus ne mesure rien.

    Dans un clone qui n'aurait fetche que la branche de travail, « aucune autre
    branche ne contient ce commit » serait vrai parce qu'aucune autre branche
    n'existerait. Les deux cibles nommees par l'AC 11 -- `main` et l'Epic 7 --
    doivent donc etre visibles pour que l'absence ait un sens.
    """
    connues = {_sans_le_distant(branche)
               for branche in _branches_distantes()}
    attendues = {"main", "claude/epic-7", BRANCHE}
    assert attendues <= connues, (
        f"branches distantes connues : {sorted(connues)} ; il manque "
        f"{sorted(attendues - connues)}, donc l'absence mesuree ci-dessus ne "
        "prouverait rien")
