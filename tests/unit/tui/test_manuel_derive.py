# -*- coding: utf-8 -*-
"""Story 11.9, lot A -- la DERIVATION du manuel (AC 3), et rien d'autre.

Ce banc mesure `tui/manuel.py` : le balayage du paquet remonte dans `src/`,
l'appartenance d'une ligne a un ecran **creee** (`EPIC11-ARB-196`), l'extraction
positive des items, les trois volets de l'AC 3.3 et la frontiere de cout de
l'AC 3.4. **Il ne mesure aucun ecran** : le manuel n'en a pas encore, et le lot
A ne depend d'aucun dessin.

**Les deux pieges que la validation de la fiche a deja payes, et qui commandent
la moitie de ce fichier :**

1. **l'import circulaire.** Vingt-cinq modules du paquet importent `coque`. Un
   balayage execute **a l'import** de `manuel.py`, joint a un
   `coque.action_aide` qui importerait le manuel au chargement, empecherait la
   TUI de demarrer. La paresse est donc mesuree des deux cotes : rien ne
   s'execute a l'import de `manuel.py`, et `coque.py` ne le nomme a aucun import
   de niveau module -- cette seconde mesure est **posee d'avance pour le lot C**,
   qui cablera `action_aide` ;
2. **la duplication du balayage.** `test_repli_ascii.py` le portait depuis la
   story 11.0 et **quatre bancs d'epic** le consomment par ce chemin. Il est
   REMONTE, pas recopie, et ce banc epingle l'identite des objets plutot que
   l'egalite de leur resultat : deux balayages qui rendent la meme chose
   aujourd'hui divergent au premier ecran ajoute.

**Chaque frontiere negative porte ici son VOLET DE MORSURE.** L'AC 3.3 est la
plus exposee du lot : ses deux volets sont des **inclusions entre ensembles**,
et deux inclusions entre deux ensembles VIDES sont vertes. Un balayage casse,
un module renomme, une derivation qui ne verrait plus rien -- et la mesure
passerait au vert sur tout. Le patron est celui de
`test_frontiere_cli.py:254,467,479`.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from mixed_media_utility.tui import manuel
from mixed_media_utility.tui.coque import Contexte, CoqueTui

#: Les deux regimes, portes par tout test qui touche au rendu. La derivation ne
#: peint pas -- mais elle est lue par un ecran qui peint, et l'affirmer sans le
#: mesurer serait une intention : voir
#: :func:`test_la_derivation_est_IDENTIQUE_dans_les_deux_regimes`.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

_RACINE = Path(__file__).resolve().parents[3]
_SRC = _RACINE / "src"
_SOURCE_DU_MANUEL = _SRC / "mixed_media_utility" / "tui" / "manuel.py"
_SOURCE_DE_LA_COQUE = _SRC / "mixed_media_utility" / "tui" / "coque.py"

#: Le paquet dont aucun import ne doit apparaitre au NIVEAU MODULE de
#: `manuel.py` : c'est lui qui porte le cycle.
_PAQUET_TUI = "mixed_media_utility.tui"


def _sonde(programme: str) -> dict:
    """Joue `programme` dans un interprete NEUF et rend son dictionnaire.

    **Un sous-processus et non le processus du banc**, parce que la mesure porte
    sur ce que l'import **charge** : au moment ou ce fichier s'execute, `pytest`
    a deja importe la moitie du paquet pour les bancs voisins, et `sys.modules`
    ne dirait plus rien. C'est la meme raison qui fait mesurer une frontiere de
    source a l'AST plutot qu'a l'execution.
    """
    acheve = subprocess.run(
        [sys.executable, "-c", programme],
        capture_output=True, text=True, cwd=str(_RACINE),
        env={"PYTHONPATH": str(_SRC), "PATH": "/usr/bin:/bin",
             "HOME": "/tmp", "LC_ALL": "C.UTF-8"})
    assert acheve.returncode == 0, acheve.stderr
    return eval(acheve.stdout.strip())  # noqa: S307 -- notre propre repr


# ===========================================================================
# A1 -- le balayage est REMONTE, jamais DUPLIQUE
# ===========================================================================

def test_le_banc_de_repli_RE_EXPORTE_le_balayage_au_lieu_d_en_garder_une_copie():
    """L'identite (`is`), jamais l'egalite du resultat.

    Deux balayages qui rendent le meme dictionnaire aujourd'hui divergeraient au
    premier ecran ajoute -- c'est exactement le mode de panne que
    `test_arb140_passages_sans_q_quitter.py:48-53` nomme (« on le REUTILISE
    plutot que d'en ecrire un second, qui divergerait ») et que
    `test_frontiere_cli.modules_de_coeur` a paye sur une liste tenue a la main.
    """
    import test_repli_ascii

    assert test_repli_ascii.classes_d_ecran is manuel.classes_d_ecran
    assert (test_repli_ascii.lignes_de_raccourcis_du_paquet
            is manuel.lignes_de_raccourcis_du_paquet)


def _definit_le_balayage(source: str) -> list[str]:
    """Les noms de balayage **definis** au niveau module par une source.

    A l'AST et non au texte : le docstring de `test_repli_ascii.py` explique
    justement pourquoi il ne les definit plus, donc il porte les deux noms --
    un grep y mordrait (defaut mesure a l'ecriture de la story 11.0 sur
    `tui/jetons.py`).
    """
    vises = {"classes_d_ecran", "lignes_de_raccourcis_du_paquet"}
    return sorted(noeud.name for noeud in ast.parse(source).body
                  if isinstance(noeud, ast.FunctionDef) and noeud.name in vises)


def test_le_banc_de_repli_ne_DEFINIT_plus_aucun_des_deux_noms():
    """Frontiere negative : la copie a bien disparu, pas seulement ete masquee.

    Une fonction laissee en place **sous** le re-export serait invisible au test
    d'identite ci-dessus (l'import gagne), et redeviendrait la source de verite
    le jour ou quelqu'un retire l'import.
    """
    source = (Path(__file__).parent / "test_repli_ascii.py").read_text(
        encoding="utf-8")
    assert _definit_le_balayage(source) == []


def test_la_mesure_de_la_DUPLICATION_du_balayage_MORD_sur_un_banc_fautif():
    """Volet de morsure : la frontiere ci-dessus regarde bien quelque chose.

    Le temoin porte les deux noms en **prose** avant de les definir : une garde
    qui grepperait le texte declarerait `test_repli_ascii.py` fautif sur son
    seul commentaire, donc serait inapplicable. Celle-ci ne mord que sur une
    definition.
    """
    innocent = ('"""Ce banc parle de classes_d_ecran et de'
                ' lignes_de_raccourcis_du_paquet sans les definir."""\n'
                "from mixed_media_utility.tui.manuel import classes_d_ecran\n")
    assert _definit_le_balayage(innocent) == []

    fautif = (innocent
              + "def lignes_de_raccourcis_du_paquet():\n    return {}\n"
              + "def classes_d_ecran():\n    return {}\n")
    assert _definit_le_balayage(fautif) == ["classes_d_ecran",
                                            "lignes_de_raccourcis_du_paquet"]


#: **Les quatre bancs d'epic qui consomment le balayage**, nommes un par un
#: parce que le lot A y touche. Trois l'importent au niveau module ou par le
#: module lui-meme ; `test_paliers` l'importe dans le corps d'une fonction, donc
#: il est mesure par son resultat plutot que par son attribut.
_BANCS_QUI_CONSOMMENT = (
    "test_majuscules_des_raccourcis",
    "test_sobriete_et_grille_extraction",
    "test_arb140_passages_sans_q_quitter",
    "test_paliers",
)


@pytest.mark.parametrize("nom_du_banc", _BANCS_QUI_CONSOMMENT[:2])
def test_les_bancs_d_epic_voient_LA_MEME_fonction_que_la_source(nom_du_banc):
    """Les deux bancs qui importent la fonction au niveau module.

    Parametre plutot qu'en boucle : un rouge nomme le banc casse au lieu de
    rendre un dictionnaire a lire.
    """
    banc = __import__(nom_du_banc)
    assert (banc.lignes_de_raccourcis_du_paquet
            is manuel.lignes_de_raccourcis_du_paquet)


def test_le_banc_ARB140_voit_LA_MEME_fonction_par_le_MODULE_de_repli():
    """`test_arb140_passages_sans_q_quitter` passe par `importlib`, pas par
    `from`. Son chemin est donc different des deux precedents, et il casserait
    seul."""
    banc = __import__("test_arb140_passages_sans_q_quitter")
    assert banc._balayage.classes_d_ecran is manuel.classes_d_ecran


def test_le_banc_des_PALIERS_tire_encore_des_lignes_du_paquet():
    """L'import y est dans le corps d'une fonction : seul son RESULTAT le dit.

    Un plancher et non un cardinal exact : le paquet grandit a chaque story, et
    ce banc ne doit pas rougir parce qu'un ecran de plus annonce `F1`.
    """
    banc = __import__("test_paliers")
    promesses = banc.lignes_de_raccourcis_qui_promettent_F1()
    assert len(promesses) >= 30, sorted(promesses)


# ===========================================================================
# A1 bis / AC 3.5 -- le balayage est PARESSEUX, et le cycle reste ferme
# ===========================================================================

def _imports_de_niveau_module(source: str, prefixe: str) -> list[str]:
    """Les imports de `prefixe` ecrits au NIVEAU MODULE d'une source.

    Un import dans le corps d'une fonction n'y figure pas -- c'est precisement
    la difference que l'AC 3.5 exige, et la mesurer au texte la rendrait
    aveugle a l'indentation.
    """
    trouves = []
    for noeud in ast.parse(source).body:
        if isinstance(noeud, ast.Import):
            trouves += [alias.name for alias in noeud.names
                        if alias.name.startswith(prefixe)]
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level or (noeud.module or "").startswith(prefixe):
                trouves.append(noeud.module or f"(relatif niveau {noeud.level})")
    return sorted(trouves)


def test_le_manuel_n_importe_AUCUN_module_du_paquet_au_NIVEAU_MODULE():
    """AC 3.5, geste 1 -- **une contrainte d'architecture, pas une optimisation**.

    Vingt-cinq modules du paquet importent `coque`, et `manuel.classes_d_ecran`
    a besoin de `coque.Palier`. Ecrit au niveau module, cet import ferme la
    boucle des que `coque` nommera le manuel (lot C) : la TUI ne demarrerait
    plus du tout.
    """
    source = _SOURCE_DU_MANUEL.read_text(encoding="utf-8")
    assert _imports_de_niveau_module(source, _PAQUET_TUI) == []


def test_la_COQUE_n_importe_PAS_le_manuel_au_NIVEAU_MODULE():
    """AC 3.5, geste 2 -- l'autre moitie du cycle, **posee d'avance**.

    Le lot A ne cable rien dans `coque.action_aide` : c'est le lot C qui
    ouvrira l'ecran. La frontiere est ecrite maintenant parce qu'elle ne coute
    rien maintenant et qu'elle attrapera le cablage au moment ou il s'ecrira --
    l'inverse (la poser apres avoir paye le cycle) est ce que la validation de
    la fiche a nomme.
    """
    source = _SOURCE_DE_LA_COQUE.read_text(encoding="utf-8")
    assert "manuel" not in _imports_de_niveau_module(source, _PAQUET_TUI)
    assert f"{_PAQUET_TUI}.manuel" not in _imports_de_niveau_module(
        source, _PAQUET_TUI)


def test_la_mesure_de_l_IMPORT_DE_NIVEAU_MODULE_MORD_dans_ses_trois_formes():
    """Volet de morsure, et il en faut trois : les trois ecritures d'un import.

    Le temoin innocent fait l'import **dans le corps d'une fonction** -- la
    forme exacte que `manuel.py` emploie --, et il porte le nom du paquet en
    prose. Sans lui, une mesure qui mordrait sur tout passerait pour severe.
    """
    innocent = ('"""Ce module parle de mixed_media_utility.tui.coque."""\n'
                "def balayer():\n"
                "    from mixed_media_utility.tui.coque import Palier\n"
                "    return Palier\n")
    assert _imports_de_niveau_module(innocent, _PAQUET_TUI) == []

    for fautif in (
        "import mixed_media_utility.tui.coque\n",
        "from mixed_media_utility.tui.coque import Palier\n",
        "from mixed_media_utility.tui import manuel\n",
        "from .coque import Palier\n",
    ):
        assert _imports_de_niveau_module(fautif, _PAQUET_TUI) != [], fautif


def test_importer_le_manuel_ne_CHARGE_aucun_ecran_du_paquet():
    """AC 3.5, geste 1, mesure a l'execution et non a la source.

    **Deux volets dans un seul programme, et c'est voulu** : le premier montre
    que l'import ne charge presque rien, le second que le meme processus, une
    fois la derivation appelee, en charge quarante et plus. Un seul des deux
    serait vert sur un module vide.

    **La mesure est un DELTA, et c'est ce qui la rend juste.** Importer quoi que
    ce soit de `tui/` charge deja `coque` et `jetons` : le `__init__` du paquet
    les nomme. Comparer a une liste absolue ferait donc porter au manuel un cout
    qui n'est pas le sien, et rougirait le jour ou le `__init__` en nomme un
    troisieme. Ce qui se mesure ici est le **surcout** de l'import du manuel :
    il doit valoir exactement le manuel lui-meme.

    Cardinaux au `baseline_commit` : **4** modules du paquet charges apres
    l'import (`tui`, `coque`, `jetons`, `manuel`), **45** apres la derivation.
    """
    mesure = _sonde(
        "import sys\n"
        "import mixed_media_utility.tui\n"
        "paquet = sorted(m for m in sys.modules if m.startswith("
        f"{_PAQUET_TUI!r}))\n"
        "from mixed_media_utility.tui import manuel\n"
        "avant = sorted(m for m in sys.modules if m.startswith("
        f"{_PAQUET_TUI!r}))\n"
        "manuel.entrees_du_manuel()\n"
        "apres = sorted(m for m in sys.modules if m.startswith("
        f"{_PAQUET_TUI!r}))\n"
        "print({'paquet': paquet, 'avant': avant, 'apres': apres})\n")
    surcout = set(mesure["avant"]) - set(mesure["paquet"])
    assert surcout == {f"{_PAQUET_TUI}.manuel"}, sorted(surcout)
    assert len(mesure["apres"]) >= 40, mesure["apres"]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_monter_la_COQUE_puis_ouvrir_la_derivation_ne_BOUCLE_pas(ascii_seul):
    """AC 3.5 -- **la seule forme qui aurait attrape le cycle**, dans cet ordre.

    `CoqueTui` d'abord, la derivation ensuite : c'est l'ordre du produit, et
    c'est celui qui casse si le manuel est importe au chargement de `coque`.
    Une derivation appelee seule, dans un banc qui n'a jamais monte la coque,
    serait verte sur un paquet qui ne demarre pas.

    Les deux regimes sont joues, et le second volet mesure ce qu'ils changent :
    **rien**. La derivation lit des litteraux ; c'est le rendu qui replie.
    """
    coque = CoqueTui(contexte=Contexte("projet_demo"), ascii_seul=ascii_seul)
    assert coque.ascii_seul is ascii_seul
    entrees = manuel.entrees_du_manuel()
    assert entrees, "la derivation ne rend rien apres montage de la coque"


def test_la_derivation_est_IDENTIQUE_dans_les_deux_regimes():
    """Le volet symetrique du test ci-dessus, ecrit plutot que suppose.

    Deux montages successifs, un par regime, et une egalite : si un jour la
    derivation repliait elle-meme, ce test rougirait et dirait ou -- au lieu de
    laisser deux manuels differents coexister, ce que `EPIC11-ARB-122` nomme
    « deux rythmes dans le meme produit ».
    """
    CoqueTui(contexte=Contexte("projet_demo"), ascii_seul=False)
    en_utf8 = manuel.entrees_du_manuel()
    CoqueTui(contexte=Contexte("projet_demo"), ascii_seul=True)
    en_ascii = manuel.entrees_du_manuel()
    assert en_utf8 == en_ascii


# ===========================================================================
# A2 / `EPIC11-ARB-196` -- l'appartenance d'une ligne a un ECRAN, CREEE
# ===========================================================================

def test_toute_ligne_du_paquet_recoit_un_ECRAN_ni_plus_ni_moins():
    """Ensemble EXACT, difference symetrique en message.

    Une inclusion laisserait passer les deux defauts a la fois : une ligne
    oubliee par l'attribution (le manuel l'annoncerait sans ecran) et une
    attribution qui survit a la disparition de sa ligne.
    """
    attribuees = set(manuel.ecrans_par_ligne())
    balayees = set(manuel.lignes_de_raccourcis_du_paquet())
    assert attribuees == balayees, sorted(attribuees ^ balayees)


def test_AUCUNE_ligne_du_paquet_n_est_ORPHELINE():
    """`EPIC11-ARB-196` : l'appartenance est **creee**, donc elle existe pour
    toutes.

    Une ligne orpheline n'est pas un plantage -- l'etage 4 existe pour qu'elle
    se voie plutot qu'elle ne casse -- mais c'est un trou du manuel : il
    annoncerait une touche sans pouvoir dire ou elle repond.
    """
    orphelines = {cle for cle, (_, etage) in manuel.ecrans_par_ligne().items()
                  if etage == manuel.ETAGE_ORPHELINE}
    assert orphelines == set(), sorted(orphelines)


@pytest.mark.parametrize("etage", [manuel.ETAGE_CLASSE, manuel.ETAGE_SAUT,
                                   manuel.ETAGE_MODULE])
def test_CHACUN_des_trois_etages_de_l_attribution_PORTE_quelque_chose(etage):
    """**Un etage qui ne sert jamais est du code mort qui se croit une regle.**

    Les trois sont mesures separement, parce qu'ils tombent trois fois
    autrement : le premier sur 105 lignes, le deuxieme sur les dix lignes
    composees (`raccourcis_de_l_explorateur`, `PIED_PAR_CHAMP`), le troisieme
    sur quatre. Si le saut cessait de servir -- une refonte de `ecran_projet`,
    par exemple -- ce test le dirait au lieu de laisser dix lignes glisser en
    silence vers l'etage 3, qui est plus grossier.
    """
    servis = {cle for cle, (_, retenu) in manuel.ecrans_par_ligne().items()
              if retenu == etage}
    assert servis, f"l'etage {etage!r} ne sert plus : il ment ou il est mort"


#: **Une fabrique de collection produit TROIS elements distinguables, et la
#: cible est AU MILIEU** (`CLAUDE.md`, regle des fabriques ; mutants `M33` de
#: 5.6 et `M25` de 5.7). Ici : trois classes d'ecran aux noms differents et
#: trois constantes aux valeurs differentes -- jamais un remplissage uniforme,
#: sans quoi une permutation ne se verrait pas.
#:
#: **La position se verifie sur la liste que le CODE parcourt** :
#: `_noms_lus_par_bloc` parcourt `ast.parse(source).body`, donc l'ordre
#: d'ecriture ci-dessous. `EcranDuMilieu` y est le deuxieme des trois, et
#: `RACCOURCIS_DU_MILIEU` la deuxieme des trois constantes.
_MODULE_TEMOIN = '''
RACCOURCIS_D_ABORD = "A d'abord  Q quitter"
RACCOURCIS_DU_MILIEU = "M au milieu  Q quitter"
RACCOURCIS_ENFIN = "Z enfin  Q quitter"

PIED_PAR_CHAMP = {"champ": RACCOURCIS_ENFIN}


class EcranD_abord:
    raccourcis = RACCOURCIS_D_ABORD


class EcranDuMilieu:
    raccourcis = RACCOURCIS_DU_MILIEU


class EcranEnfin:
    def tete(self):
        return PIED_PAR_CHAMP["champ"]
'''


def test_l_attribution_par_la_CLASSE_ne_rend_pas_le_PREMIER_ecran_venu():
    """Le mutant `M25` de la story 5.7, sur la fabrique.

    `_find` qui rend le **premier** element est le defaut que trois campagnes
    de mutation ont trouve dans ce depot, et qu'aucune relecture n'a vu. La
    cible est ici la **deuxieme** des trois classes ecrites, et les trois
    portent des valeurs differentes : une attribution qui rendrait `EcranD_abord`
    a `RACCOURCIS_DU_MILIEU` rougit, ce qu'une fabrique mono-classe ne verrait
    pas.
    """
    par_classe, par_nom = manuel._noms_lus_par_bloc(_MODULE_TEMOIN)
    porteuses = {nom for nom, lus in par_classe.items()
                 if "RACCOURCIS_DU_MILIEU" in lus}
    assert porteuses == {"EcranDuMilieu"}, sorted(porteuses)
    autres = {nom for nom, lus in par_classe.items()
              if "RACCOURCIS_D_ABORD" in lus}
    assert autres == {"EcranD_abord"}, sorted(autres)


def test_l_attribution_par_SAUT_traverse_une_liaison_de_module():
    """L'etage 2, sur la fabrique : `EcranEnfin` ne nomme jamais la constante.

    Il nomme `PIED_PAR_CHAMP`, qui la nomme. C'est la forme reelle de
    `atelier_scan_calibrate` (« une table plutot qu'une chaine de `if` ») et de
    `ecran_projet.raccourcis_de_l_explorateur()`. Sans ce saut, dix lignes du
    paquet tomberaient a l'etage 3, qui rattache au module entier.
    """
    par_classe, par_nom = manuel._noms_lus_par_bloc(_MODULE_TEMOIN)
    assert "RACCOURCIS_ENFIN" not in par_classe["EcranEnfin"]
    assert "PIED_PAR_CHAMP" in par_classe["EcranEnfin"]
    assert "RACCOURCIS_ENFIN" in par_nom["PIED_PAR_CHAMP"]


def test_les_NEUF_ecrans_porteurs_de_Q_sont_rendus_ENTIERS_et_pas_le_premier():
    """La collection qui porte le risque `M25` **sur le produit reel**.

    `Q` est la lettre la plus portee du paquet, et un resolveur qui rendrait son
    premier porteur au lieu de tous resterait vert sur toute fabrique
    mono-porteur. La cible verifiee ici est **au milieu** de la liste triee que
    le code rend -- ni la premiere (`atelier_pdf.EcranPdfMenu`) ni la derniere
    (`palier_projet.EcranPalierProjet`).

    **Un cardinal mesure, et il contredit la fiche** : la fiche annonce « treize
    porteurs ». Le balayage en rend **neuf ecrans**, pour **17 entrees** du
    balayage et **10 lignes distinctes** -- aucun des quatre comptages ne fait
    treize. Le cardinal qui compte pour la regle des fabriques est celui des
    **ecrans**, et il est de neuf.
    """
    porteurs = manuel.lettres_du_manuel()["Q"]
    assert len(porteurs) == 9, sorted(porteurs)
    assert porteurs[0].endswith("atelier_pdf.EcranPdfMenu")
    assert porteurs[-1].endswith("palier_projet.EcranPalierProjet")
    # La cible au MILIEU : ni premiere ni derniere, et elle n'est portee par
    # AUCUN attribut de classe -- elle n'existe que par l'attribution creee.
    assert f"{_PAQUET_TUI}.atelier_scan.EcranScanDepot" in porteurs


# ===========================================================================
# A3 / AC 3.2 -- l'extraction dit ce qu'elle GARDE
# ===========================================================================

def test_l_extraction_rend_les_TROIS_items_d_une_ligne_dans_l_ordre():
    """Trois items **distinguables**, cible au milieu, sur la liste que le code
    parcourt (`SEPARATEUR_D_ITEMS.split`).

    Trois libelles differents et non trois fois le meme : une fabrique uniforme
    rendrait invisible toute inversion d'appariement entre ouvreur et libelle --
    le mutant `M33` de la story 5.6, mot pour mot.
    """
    items = manuel.items_d_une_ligne(
        "⏎ ouvrir  ↑↓ liste  Suppr retirer  Tab explorateur")
    assert items == (("⏎", "ouvrir"), ("↑↓", "liste"),
                     ("Suppr", "retirer"), ("Tab", "explorateur"))
    assert items[2] == ("Suppr", "retirer"), items


def test_un_item_d_UN_SEUL_MOT_est_un_libelle_de_zone_et_non_un_raccourci():
    """`Rushes` et `Explorateur` ouvrent les lignes de `E2-1` et `E2-1b`.

    Ce sont des **noms de zone**, pas des touches. Les garder ferait annoncer au
    manuel un raccourci « Rushes » qui n'existe pas.
    """
    items = manuel.items_d_une_ligne(LIGNE_MELEE_DES_DEUX_ECRANS)
    assert items == (("⏎", "choisir"), ("Tab", COUPLE_D_AJOUT_DESSINE))


@pytest.mark.parametrize("vide", ["", "   ", None])
def test_une_ligne_VIDE_ne_rend_aucun_item_et_ne_leve_rien(vide):
    """Trois formes du vide, et non la premiere : `Palier.raccourcis` vaut la
    chaine vide sur les classes de base, et l'attribut peut manquer."""
    assert manuel.items_d_une_ligne(vide) == ()


def test_le_SEPARATEUR_de_la_source_est_CELUI_que_le_banc_des_majuscules_epingle():
    """Une valeur ne se recopie pas : elle se nomme, et on dit ou elle habite.

    `EPIC11-ARB-122` fixe le separateur a **deux espaces**, et
    `test_majuscules_des_raccourcis._SEPARATEUR_D_ITEMS` le formalise depuis le
    lot `O`. La derivation vit maintenant dans `src/` et ne peut pas importer un
    banc ; les deux redactions sont donc epinglees a l'egalite ici plutot que
    laissees diverger -- c'est la lecon de `CANONICAL_ID_MAX_LENGTH`, recopiee
    fausse trois fois.
    """
    banc = __import__("test_majuscules_des_raccourcis")
    assert (manuel.SEPARATEUR_D_ITEMS.pattern
            == banc._SEPARATEUR_D_ITEMS.pattern)


def test_l_extraction_GARDE_tous_les_libelles_d_un_MEME_ouvreur():
    """`Échap` en a quinze au `baseline_commit`, `⏎` dix-neuf.

    N'en garder qu'un ferait mentir le manuel sur quatorze ecrans -- et le
    defaut serait invisible a toute mesure qui ne compterait que les ouvreurs.
    Plancher et non cardinal exact : le paquet grandit.
    """
    par_ouvreur = {entree.ouvreur: entree
                   for entree in manuel.entrees_du_manuel()}
    assert len(par_ouvreur["Échap"].libelles) >= 10, par_ouvreur["Échap"]
    assert len(par_ouvreur["⏎"].libelles) >= 10, par_ouvreur["⏎"]
    assert "retour" in par_ouvreur["Échap"].libelles
    assert "ateliers" in par_ouvreur["Échap"].libelles


def test_les_DEUX_blocs_du_manuel_sont_ceux_que_la_maquette_range():
    """Le partage « partout » / « propre a un ecran » est **mesure**, AC 2.1.

    La maquette `T1-2` range **sept** ouvreurs sous « Raccourcis — partout » ;
    la derivation en rend sept, et ce sont les memes. C'est la confrontation qui
    valide le critere (« plus d'un atelier »), et non l'inverse.

    Les trois lettres propres sont **toutes de l'Extraction**, comme la fiche
    l'annonce, et `e` / `r` n'y sont pas : `EPIC11-ARB-68` les a remplacees par
    `Tab` et `Ctrl+R`. Un test qui les attendrait mesurerait la maquette au lieu
    du produit.
    """
    partout = {e.ouvreur for e in manuel.entrees_du_manuel() if e.partout}
    attendu = {"↑↓", "⏎", "Espace", "Tab", "Échap", "F1", "Q"}
    assert partout == attendu, sorted(partout ^ attendu)

    propres = {e.ouvreur for e in manuel.entrees_du_manuel() if not e.partout}
    assert {"A", "O", "X"} <= propres, sorted(propres)
    assert {"e", "r"} & propres == set(), sorted(propres)


# ===========================================================================
# Lot D / `EPIC11-ARB-196` -- le manuel ne SE decrit pas lui-meme
# ===========================================================================
#
# **Le defaut que ces cinq tests ferment, et il n'a ete vu par aucune
# relecture.** Le lot C a livre `ecran_manuel.RACCOURCIS_MANUEL` -- « → page
# suivante  ← page precedente  Échap fermer ». Les fleches existaient deja sur
# un SEUL module (`ecran_projet`), donc le critere `len(ateliers) > 1` les
# rangeait parmi les raccourcis propres. Le second module les a fait basculer,
# et `test_les_DEUX_blocs_...` ci-dessus est passe au rouge en annoncant
# **neuf** ouvreurs « partout » la ou `T1-2` en range sept.
#
# Ce n'est pas un ecart de cardinal : `→` et `←` ne marchent PAS partout, ils
# tournent les pages du manuel. La maquette le dit d'elle-meme en ne portant
# ses propres fleches dans AUCUN de ses deux blocs, alors qu'elle les annonce
# dans sa ligne de pied.


def test_les_fleches_du_manuel_ne_sont_PAS_annoncees_comme_valant_partout():
    """Le volet positif, sur le produit reel.

    Les deux fleches restent **dans** le manuel -- `ecran_projet` les porte --,
    mais du cote « propre a un ecran », qui est le vrai.
    """
    par_ouvreur = {e.ouvreur: e for e in manuel.entrees_du_manuel()}
    for fleche in ("→", "←"):
        assert fleche in par_ouvreur, f"{fleche} a disparu du manuel"
        assert not par_ouvreur[fleche].partout, par_ouvreur[fleche].ateliers
        assert manuel.MODULE_DU_MANUEL not in par_ouvreur[fleche].ateliers


def test_AUCUNE_entree_du_manuel_n_est_portee_par_le_module_du_manuel():
    """L'exception ET son unicite, sur toutes les entrees a la fois.

    Une assertion sur les seules fleches serait verte le jour ou ce module
    porterait une troisieme ligne -- regle des fabriques : « ces deux-la sont
    corriges » ne dit rien d'un troisieme.
    """
    fautives = {e.ouvreur: e.ecrans for e in manuel.entrees_du_manuel()
                if any(ecran.split(".")[-2] == manuel.MODULE_DU_MANUEL
                       for ecran in e.ecrans)}
    assert fautives == {}, fautives


@pytest.mark.parametrize("cle", [
    f"{_PAQUET_TUI}.ecran_manuel.RACCOURCIS_INVENTE",
    f"{_PAQUET_TUI}.ecran_manuel.EcranInvente.raccourcis",
])
def test_l_exclusion_tient_sur_les_DEUX_FORMES_de_cle_du_module(monkeypatch, cle):
    """Le mode de panne de la premiere redaction, epingle.

    Ce module porte **deux** cles de formes differentes -- une constante
    (`ecran_manuel.RACCOURCIS_MANUEL`) et un attribut de classe
    (`ecran_manuel.EcranManuel.raccourcis`). La premiere redaction de
    l'exclusion lisait le module par `cle.rsplit(".", 2)[-2]`, ce qui rend
    `EcranManuel` sur la seconde forme : **la moitie du module passait au
    travers**, et le banc ci-dessus restait rouge.

    Les deux formes sont donc mesurees separement, sur un ouvreur **invente**
    qui n'existe nulle part ailleurs dans le paquet : sa presence dans la
    derivation ne pourrait venir que de cette ligne-la.
    """
    reelles = manuel.lignes_de_raccourcis_du_paquet()
    monkeypatch.setattr(manuel, "lignes_de_raccourcis_du_paquet",
                        lambda: {**reelles, cle: "Ctrl+Y refaire"})
    assert "Ctrl+Y" not in {e.ouvreur for e in manuel.entrees_du_manuel()}


def test_la_mesure_de_l_EXCLUSION_MORD_sur_une_ligne_d_un_AUTRE_module(monkeypatch):
    """Le volet de morsure -- sans lui, une exclusion trop large serait verte.

    Meme temoin, meme ouvreur invente, **un seul caractere de difference** :
    le module. S'il entre, l'exclusion vise bien le manuel et pas le paquet
    entier ; s'il n'entrait pas, les quatre tests ci-dessus seraient verts sur
    une derivation qui ne rend plus rien.
    """
    reelles = manuel.lignes_de_raccourcis_du_paquet()
    cle = f"{_PAQUET_TUI}.ecran_invente.RACCOURCIS_INVENTE"
    monkeypatch.setattr(manuel, "lignes_de_raccourcis_du_paquet",
                        lambda: {**reelles, cle: "Ctrl+Y refaire"})
    vus = {e.ouvreur for e in manuel.entrees_du_manuel()}
    assert "Ctrl+Y" in vus, "l'exclusion mord au-dela du module du manuel"


def test_le_BALAYAGE_voit_TOUJOURS_le_module_du_manuel_lui():
    """L'exclusion porte sur la DERIVATION, jamais sur le balayage.

    Trois autres bancs d'epic lisent le meme balayage pour d'autres mesures --
    le repli ASCII, les majuscules, le budget de colonnes. Retirer le manuel de
    la SOURCE l'aurait soustrait a ces trois-la d'un coup, c'est-a-dire le
    defaut symetrique : une mesure portee sans son module.
    """
    cles = manuel.lignes_de_raccourcis_du_paquet()
    du_manuel = [c for c in cles if manuel.MODULE_DU_MANUEL in c.split(".")]
    assert len(du_manuel) >= 2, sorted(cles)


def test_les_entrees_PARTOUT_precedent_les_PROPRES_dans_l_ordre_rendu():
    """L'ordre des deux blocs de `T1-2`, et il est porte par la derivation.

    Le rendu ne doit pas avoir a retrier : deux tris (ici et a l'ecran)
    divergeraient au premier ajustement.
    """
    partout = [e.partout for e in manuel.entrees_du_manuel()]
    assert partout == sorted(partout, reverse=True), partout


# ===========================================================================
# A4 / AC 3.3 -- les TROIS volets de l'appartenance des lettres
# ===========================================================================

def _lettres_annoncees_par_le_paquet() -> dict[str, set[str]]:
    """Les lettres vues **directement** sur les lignes, sans passer par le
    manuel.

    Second chemin de lecture, delibere : confronter la derivation a elle-meme ne
    mesurerait rien.
    """
    vues: dict[str, set[str]] = {}
    for cle, ligne in manuel.lignes_de_raccourcis_du_paquet().items():
        for ouvreur, _libelle in manuel.items_d_une_ligne(ligne):
            # **Le predicat est APPELE, plus recopie** (revue 11.9, couche 1
            # `F11`, mutant `M12`, ferme au lot E5). La recopie qui tenait
            # cette place -- `len(ouvreur) == 1 and ouvreur.isalpha()` --
            # faisait de ce volet une comparaison de deux ensembles construits
            # par la MEME regle ecrite deux fois : la production pouvait etre
            # mutee sans que rien diverge. Le chemin de LECTURE reste second
            # (on relit les lignes du paquet, pas la derivation), c'est la
            # DEFINITION qui cesse d'etre double.
            if manuel.est_une_lettre(ouvreur):
                vues.setdefault(ouvreur, set()).add(cle)
    return vues


def _lettres_qui_nomment_un_ecran_INCONNU(lettres, classes) -> dict:
    """La mesure du volet 1, **extraite** pour que sa morsure la reutilise.

    Une mesure ecrite en ligne dans son test ne peut pas etre confrontee a un
    temoin fautif : c'est ce qui rend une frontiere verte sur tout.
    """
    return {lettre: sorted(set(ecrans) - set(classes))
            for lettre, ecrans in lettres.items()
            if set(ecrans) - set(classes)}


def test_volet_1_AUCUNE_lettre_du_manuel_ne_nomme_un_ecran_INVENTE():
    """AC 3.3, premier volet : toute lettre annoncee nomme un ecran **reel**.

    L'appartenance est creee par une lecture d'AST ; une classe renommee, un
    module deplace, et le manuel enverrait l'operateur sur un ecran qui
    n'existe pas.
    """
    inconnus = _lettres_qui_nomment_un_ecran_INCONNU(
        manuel.lettres_du_manuel(), manuel.classes_d_ecran())
    assert inconnus == {}, inconnus


def test_volet_2_AUCUNE_lettre_annoncee_par_le_PAQUET_ne_manque_au_manuel():
    """AC 3.3, second volet, et il se lit dans l'autre sens.

    Egalite d'ensembles et non inclusion : une lettre **de trop** au manuel est
    aussi fautive qu'une lettre oubliee -- la premiere enseigne un geste qui
    n'existe pas, la seconde laisse deviner.
    """
    du_manuel = set(manuel.lettres_du_manuel())
    du_paquet = set(_lettres_annoncees_par_le_paquet())
    assert du_manuel == du_paquet, sorted(du_manuel ^ du_paquet)


def test_volet_3_la_derivation_VOIT_vraiment_des_lettres_et_leurs_porteurs():
    """AC 3.3, troisieme volet -- **sans lui les deux premiers sont VIDES**.

    Deux inclusions entre deux ensembles vides sont vertes : un balayage casse,
    un paquet renomme, et les deux volets ci-dessus passent sur un manuel qui ne
    dit rien. C'est le defaut que
    `test_majuscules_des_raccourcis.test_le_balayage_du_paquet_VOIT_vraiment_des_lettres`
    et `test_repli_ascii.test_le_balayage_des_ecrans_trouve_les_classes_du_paquet`
    ferment deja, chacun dans son fichier.

    Les quatre lettres du `baseline_commit`, et **au moins un porteur pour
    chacune** : une lettre vue sans porteur serait la moitie du defaut.
    """
    lettres = manuel.lettres_du_manuel()
    assert {"A", "O", "Q", "X"} <= set(lettres), sorted(lettres)
    sans_porteur = sorted(lettre for lettre, ecrans in lettres.items()
                          if not ecrans)
    assert sans_porteur == [], sans_porteur


def test_la_mesure_du_volet_1_MORD_sur_une_lettre_qui_nomme_un_ecran_ABSENT():
    """Volet de morsure du premier volet.

    Le temoin porte **trois** lettres distinguables, la fautive **au milieu** :
    une mesure qui ne regarderait que la premiere entree resterait verte ici.
    """
    classes = {f"{_PAQUET_TUI}.reel.EcranReel": object}
    temoin = {
        "A": (f"{_PAQUET_TUI}.reel.EcranReel",),
        "M": (f"{_PAQUET_TUI}.fantome.EcranQuiNExistePas",),
        "Z": (f"{_PAQUET_TUI}.reel.EcranReel",),
    }
    assert _lettres_qui_nomment_un_ecran_INCONNU(temoin, classes) == {
        "M": [f"{_PAQUET_TUI}.fantome.EcranQuiNExistePas"]}
    # Et elle ne mord PAS quand toutes nomment un ecran connu : sans ce sens,
    # un resserrement futur ferait rougir le produit sans rien dire de plus.
    assert _lettres_qui_nomment_un_ecran_INCONNU(
        {cle: temoin[cle] for cle in ("A", "Z")}, classes) == {}


def test_la_mesure_du_volet_3_MORD_sur_une_derivation_qui_ne_voit_RIEN():
    """Volet de morsure du troisieme volet -- celui qui protege les deux autres.

    Deux temoins, parce qu'il y a deux facons de ne rien voir : **aucune
    lettre**, et **une lettre sans porteur**. La seconde est la plus sournoise :
    l'ensemble des lettres est alors non vide, donc l'inclusion du volet 3
    passerait.
    """
    aveugle: dict[str, tuple[str, ...]] = {}
    assert not ({"A", "O", "Q", "X"} <= set(aveugle))

    sans_porteur = {"A": (), "O": (f"{_PAQUET_TUI}.reel.EcranReel",),
                    "Q": (), "X": (f"{_PAQUET_TUI}.reel.EcranReel",)}
    assert {"A", "O", "Q", "X"} <= set(sans_porteur), "l'inclusion seule passe"
    orphelines = sorted(lettre for lettre, ecrans in sans_porteur.items()
                        if not ecrans)
    assert orphelines == ["A", "Q"], orphelines


# ===========================================================================
# A5 / AC 3.4 -- la frontiere de COUT, avec ses deux volets
# ===========================================================================

#: Le programme de sonde, ecrit UNE fois : les trois tests ci-dessous mesurent
#: le meme fait sous trois angles, et trois redactions divergeraient.
_SONDE_DE_LA_DERIVATION = (
    "import sys\n"
    "from mixed_media_utility.tui import manuel\n"
    "entrees = manuel.entrees_du_manuel()\n"
    "print({'cli': 'mixed_media_utility.cli' in sys.modules,\n"
    "       'modules': len([m for m in sys.modules if m.startswith("
    f"{_PAQUET_TUI!r})]),\n"
    "       'entrees': len(entrees)})\n")


def test_la_SOURCE_du_manuel_ne_nomme_JAMAIS_cli__mesure_a_l_AST():
    """AC 3.4, volet de source -- et il **REUTILISE** le predicat du depot.

    `test_frontiere_cli._appelle_cli` est le predicat de l'interdit, ecrit une
    fois pour tout le paquet et repris mot pour mot depuis
    `test_palier_projet` : « deux predicats pour un seul interdit divergeraient,
    et c'est le module non couvert par le plus strict des deux qui passerait ».
    En ecrire un second ici serait exactement le defaut que le lot A vient de
    fermer sur le balayage.

    **Sa morsure n'est pas reecrite ici, et c'est voulu** : elle vit dans
    `test_frontiere_cli.test_la_mesure_de_la_frontiere_cli_MORD_sur_un_module_fautif`,
    sur quatre formes de violation plus une prose innocente. Une seconde
    morsure du meme predicat serait une seconde source de verite.

    Ce test est le volet de **source** ; le volet de **cloture transitive** est
    celui qui suit, et les deux ne mesurent pas la meme chose : celui-ci ne voit
    que `manuel.py`, celui-la voit les quarante-trois modules que la derivation
    importe.
    """
    banc = __import__("test_frontiere_cli")
    assert banc._appelle_cli(_SOURCE_DU_MANUEL) == []
    # Le balayage a bien vu un module reel, et non un chemin qui n'existe pas :
    # `identifiants` d'un fichier absent leverait, mais un chemin renomme au
    # fil d'une refonte rendrait ce test muet s'il ne l'exigeait pas.
    assert _SOURCE_DU_MANUEL.is_file(), _SOURCE_DU_MANUEL
    assert banc._appelle_cli(_SOURCE_DE_LA_COQUE) == []


def test_la_derivation_ne_tire_JAMAIS_cli_par_TRANSITIVITE():
    """AC 3.4 -- la frontiere de cout, mesuree a l'EXECUTION.

    `test_frontiere_cli.py` mesure deja qu'aucune **source** du paquet ne nomme
    `cli`. Cette mesure-ci est plus forte et differente : la derivation importe
    les quarante-trois modules du paquet, donc elle ferme la **cloture
    transitive** des imports -- un module tiers qui tirerait `cli` demain serait
    invisible a l'AST du seul `manuel.py`, et visible ici.

    Motif, verbatim de `tui/palier_projet.py:9-12` : les fonctions de `cli.py`
    « impriment sur `stderr` et rendent un code retour », ce qui, sous une TUI,
    envoie des lignes **sous** l'ecran dessine.
    """
    assert _sonde(_SONDE_DE_LA_DERIVATION)["cli"] is False


def test_le_balayage_de_la_frontiere_de_cout_a_bien_VU_le_paquet():
    """AC 3.4, premier volet -- « le banc echoue s'il ne mesure plus rien ».

    Une derivation qui n'importerait rien ne tirerait pas `cli` non plus, et le
    test ci-dessus serait vert sur un module vide. Plancher et non egalite : le
    paquet grandit a chaque story, et l'ecran de manuel du lot C y entrera sans
    qu'une ligne d'ici ne change.
    """
    mesure = _sonde(_SONDE_DE_LA_DERIVATION)
    assert mesure["modules"] >= 40, mesure
    assert mesure["entrees"] >= 15, mesure


def test_la_mesure_de_la_frontiere_de_cout_MORD_sur_un_programme_fautif():
    """AC 3.4, second volet -- la sonde regarde bien `sys.modules`.

    Le temoin innocent **nomme** `cli` en prose et en chaine sans l'importer :
    une sonde qui grepperait son propre programme le declarerait fautif. Le
    temoin fautif l'importe pour de bon.
    """
    innocent = ("import sys\n"
                "MESSAGE = 'ce programme parle de mixed_media_utility.cli'\n"
                "print({'cli': 'mixed_media_utility.cli' in sys.modules})\n")
    assert _sonde(innocent)["cli"] is False

    fautif = ("import sys\n"
              "import mixed_media_utility.cli\n"
              "print({'cli': 'mixed_media_utility.cli' in sys.modules})\n")
    assert _sonde(fautif)["cli"] is True


def test_le_COUT_D_IMPORT_du_manuel_n_ouvre_AUCUN_ecran_du_paquet():
    """AC 3.4 -- « le cout d'import du balayage est mesure et ecrit ».

    **Le cardinal de modules plutot qu'une duree** : un seuil de millisecondes
    rougirait sur une machine chargee et ne dirait rien de ce qui a coute. Le
    cout mesure au `baseline_commit`, pour memoire et non comme assertion :

    * importer le paquet `tui` -- **201 ms** : c'est son `__init__`, qui nomme
      `coque`, lequel nomme `jetons`. Ce cout est paye par tout import de `tui/`
      et n'est pas celui du manuel ;
    * importer `tui.manuel` **par-dessus** -- **1 ms**, un module de plus, zero
      ecran ;
    * `classes_d_ecran()` a froid, qui charge les quarante-trois modules --
      **491 ms** ; a chaud, **2 ms** ;
    * `lignes_de_raccourcis_du_paquet()` a chaud -- **4 ms**. C'est ce que
      paient les quatre bancs d'epic, et c'est ce qu'ils payaient deja ;
    * `entrees_du_manuel()` a chaud, AST des vingt-quatre modules porteurs --
      **262 ms**.

    Le module n'est donc **pas** cache : une derivation memoisee mentirait le
    jour ou un banc ajoute une classe temoin, et les 262 ms sont payes une fois
    par ouverture du manuel, pas par frappe.

    **Ce que ce test mesure, et que le delta ci-dessus ne mesure pas** : les
    trois modules charges a l'import sont nommement `coque` et `jetons`, qui ne
    portent aucun **atelier**. Un import qui tirerait `atelier_extraction` ou
    `execution` serait un balayage deguise -- exactement ce que l'AC 3.5
    interdit --, et un delta d'un seul module ne le dirait pas si le paquet le
    chargeait deja.
    """
    mesure = _sonde(
        "import sys\n"
        "from mixed_media_utility.tui import manuel\n"
        "print({'modules': sorted(m for m in sys.modules if m.startswith("
        f"{_PAQUET_TUI!r}))}})\n")
    assert mesure["modules"] == [_PAQUET_TUI, f"{_PAQUET_TUI}.coque",
                                 f"{_PAQUET_TUI}.jetons",
                                 f"{_PAQUET_TUI}.manuel"], mesure
    ateliers = [m for m in mesure["modules"] if ".atelier" in m]
    assert ateliers == [], ateliers


# ===========================================================================
# A6 -- aucun LIBELLE du paquet ne s'ouvre sur une ponctuation
#       (defaut `F4` de la couche 3, 2026-09-03)
# ===========================================================================

#: Ce qu'un libelle de raccourci ne peut pas porter en **premier caractere**.
#:
#: `items_d_une_ligne` decoupe un item sur les blancs et prend le premier mot
#: comme ouvreur : la ligne `Coller : terminal` rendait donc le couple
#: `("Coller", ": terminal")`, et le manuel ecrivait
#:
#: ```
#:      Coller       : terminal                   (Projet)
#: ```
#:
#: -- un deux-points **orphelin** en tete de colonne, visible par l'operateur.
#: Ce n'est pas un defaut de la derivation : elle rend fidelement ce que la
#: ligne annonce. C'est la ligne source qui employait `:` comme
#: sous-separateur, et un sous-separateur ne survit pas au passage en deux
#: colonnes.
#:
#: L'ensemble est ferme et **negatif** : il dit la forme interdite, il
#: n'enumere pas les libelles permis -- meme geste que l'extraction positive
#: d'`items_d_une_ligne`.
PONCTUATIONS_INTERDITES_EN_TETE_DE_LIBELLE = tuple(":;,.!?/|=+*")


def _libelles_fautifs(ligne: str) -> list[str]:
    """Les libelles d'une ligne qui s'ouvrent sur une ponctuation."""
    return [libelle for _ouvreur, libelle in manuel.items_d_une_ligne(ligne)
            if libelle.startswith(PONCTUATIONS_INTERDITES_EN_TETE_DE_LIBELLE)]


@pytest.mark.parametrize(
    "nom,ligne", sorted(manuel.lignes_de_raccourcis_du_paquet().items()))
def test_A6_aucun_LIBELLE_annonce_par_le_PAQUET_ne_s_ouvre_sur_une_PONCTUATION(
        nom, ligne):
    """Frontiere negative, mesuree **ligne par ligne** sur le paquet entier.

    Une mesure agregee (« aucun libelle fautif dans le paquet ») dirait la meme
    chose ; posee par ligne, elle **nomme** la ligne fautive dans son propre
    identifiant de test, ce qui est ce que la revue a du reconstruire a la main
    le 2026-09-03.
    """
    assert _libelles_fautifs(ligne) == [], (nom, ligne)


def test_A6_le_manuel_RENDU_ne_porte_aucun_libelle_ouvert_sur_une_PONCTUATION():
    """Le meme invariant **du cote du rendu**, parce que c'est la qu'il mord.

    La ligne source reste lisible dans son pied d'ecran (`Coller : terminal` s'y
    lit comme une phrase) ; c'est la mise en deux colonnes du manuel qui rend le
    deux-points orphelin. Mesurer la seule ligne source laisserait donc croire
    que le probleme est ailleurs qu'il n'est.
    """
    fautives = [(entree.ouvreur, libelle)
                for entree in manuel.entrees_du_manuel()
                for libelle in entree.libelles
                if libelle.startswith(PONCTUATIONS_INTERDITES_EN_TETE_DE_LIBELLE)]
    assert fautives == [], fautives


def test_A6_la_frontiere_de_la_PONCTUATION_MORD_et_seulement_sur_le_fautif():
    """Volet symetrique. Sans lui, un analyseur casse rendrait la frontiere
    verte sur toutes les lignes du paquet.

    Le corpus porte **trois** items distinguables, le fautif **au milieu** --
    un balayage qui s'arreterait au premier item ne le verrait pas --, puis
    deux corpus de bord, le fautif en **tete** et en **queue**, parce qu'un
    balayage tronque par un bout est un autre mode de panne que celui qu'une
    cible au milieu demasque (`fabrique-poser-aussi-aux-deux-bords`).
    """
    assert _libelles_fautifs(
        "⏎ valider  Coller : terminal  Échap sortir") == [": terminal"]
    assert _libelles_fautifs(
        "Coller : terminal  ⏎ valider  Échap sortir") == [": terminal"]
    assert _libelles_fautifs(
        "⏎ valider  Échap sortir  Coller : terminal") == [": terminal"]
    # Et il ne mord PAS sur une ligne saine, ni sur une ponctuation qui est
    # **dans** le libelle plutot qu'en tete -- `récents · projet` en porte.
    assert _libelles_fautifs(
        "⏎ valider  Coller par le terminal  Échap sortir") == []
    assert _libelles_fautifs("Tab champ · liste  Échap retour") == []
    # Anti-vacuite : l'analyseur lit bien trois items sur ces lignes.
    assert len(manuel.items_d_une_ligne(
        "⏎ valider  Coller : terminal  Échap sortir")) == 3


# ===========================================================================
# E2 -- la fermeture des findings de la revue du 2026-09-03 sur `manuel.py`
#
# Chaque bloc ci-dessous nomme le finding qu'il ferme et le mutant qui, une
# fois REINJECTE, doit le faire rougir (politique 6.2). Aucun de ces bancs
# n'encode un cardinal ni un rang du manuel du jour : la story 11.4e retire
# une entree du produit (`EPIC11-ARB-141`), et une frontiere qui compterait
# les entrees rougirait a la fusion pour une raison etrangere a ce qu'elle
# mesure. Ils mesurent tous une RELATION.
# ===========================================================================

#: Un ouvreur qui n'existe **nulle part** dans le paquet. Sa presence dans une
#: derivation ne peut donc venir que de la ligne temoin qui l'injecte -- meme
#: geste que `test_l_exclusion_tient_sur_les_DEUX_FORMES_de_cle_du_module`.
_OUVREUR_INVENTE = "Ctrl+Y"


#: Les deux tables reelles, calculees **une fois** pour tout le fichier.
#: `ecrans_par_ligne` analyse a l'AST les quarante-cinq modules du paquet :
#: la rappeler a chaque temoin faisait passer ce lot de 25 a 60 secondes,
#: c'est-a-dire multipliait par deux le cout de chaque reinjection de la
#: campagne de fermeture. Les tables sont copiees avant usage, jamais
#: partagees en ecriture.
_TABLES_REELLES: dict = {}


def _tables_reelles() -> tuple[dict, dict]:
    """Les tables du paquet, memoisees. Elles ne dependent d'aucun temoin."""
    if not _TABLES_REELLES:
        _TABLES_REELLES["lignes"] = manuel.lignes_de_raccourcis_du_paquet()
        _TABLES_REELLES["attribution"] = manuel.ecrans_par_ligne()
    return _TABLES_REELLES["lignes"], _TABLES_REELLES["attribution"]


def _derivation_avec(monkeypatch, temoins):
    """La derivation reelle, **plus** des lignes temoins attribuees a la main.

    `temoins` est une suite de `(cle, ligne, ecrans)`. Les deux tables que
    `entrees_du_manuel` consomme sont remplacees ensemble : la table des
    lignes et celle de l'attribution. Les remplacer separement laisserait la
    ligne temoin retomber a l'etage `orpheline`, ce qui mesurerait autre chose
    que ce que le test annonce.

    Rend les entrees **indexees par ouvreur**, jamais une liste indexee par
    rang : le rang d'une entree bouge des qu'un raccourci du produit change.
    """
    lignes_reelles, attribution_reelle = _tables_reelles()
    lignes = dict(lignes_reelles)
    attribution = dict(attribution_reelle)
    for cle, ligne, ecrans in temoins:
        lignes[cle] = ligne
        if ecrans is not None:
            attribution[cle] = (tuple(ecrans), manuel.ETAGE_CLASSE)
    monkeypatch.setattr(manuel, "lignes_de_raccourcis_du_paquet",
                        lambda: lignes)
    monkeypatch.setattr(manuel, "ecrans_par_ligne", lambda: attribution)
    return {entree.ouvreur: entree for entree in manuel.entrees_du_manuel()}


# ---------------------------------------------------------------------------
# Couche 1 `F1` / couche 2 `F2`, mutant `M07` -- `partout` se decide sur le
# DOMAINE, jamais sur le module
# ---------------------------------------------------------------------------

#: Deux modules **reels** du paquet qui se replient sur un seul domaine, et
#: deux qui n'en partagent aucun. Les quatre noms sont distinguables et les
#: deux paires sont symetriques : sans la seconde, un critere qui rendrait
#: `partout=False` pour tout le monde serait vert sur la premiere.
_DEUX_MODULES_D_UN_MEME_DOMAINE = ("ecran_projet", "palier_projet")
_DEUX_MODULES_DE_DOMAINES_DIFFERENTS = ("ecran_projet", "atelier_scan")


def test_le_DOMAINE_REPLIE_plusieurs_modules_du_paquet_reel():
    """Le fait sans lequel `F1`/`F2` n'existeraient pas, mesure sur le produit.

    Si chaque module etait son propre domaine, compter les modules et compter
    les domaines reviendraient au meme et le mutant `M07` serait sans objet.
    La mesure est une **relation** -- « ces deux-la se replient, ces deux-la
    non » -- et non un cardinal de modules par domaine, qui bougerait au
    premier ecran ajoute.
    """
    replies = {manuel.atelier_lisible(m)
               for m in _DEUX_MODULES_D_UN_MEME_DOMAINE}
    assert len(replies) == 1, replies
    distincts = {manuel.atelier_lisible(m)
                 for m in _DEUX_MODULES_DE_DOMAINES_DIFFERENTS}
    assert len(distincts) == 2, distincts
    # Anti-vacuite : les quatre modules existent bel et bien dans le paquet.
    du_paquet = {classe.__module__.rsplit(".", 1)[-1]
                 for classe in manuel.classes_d_ecran().values()}
    absents = (set(_DEUX_MODULES_D_UN_MEME_DOMAINE)
               | set(_DEUX_MODULES_DE_DOMAINES_DIFFERENTS)) - du_paquet
    assert absents == set(), absents


def test_DEUX_modules_d_un_MEME_domaine_ne_valent_PAS_partout(monkeypatch):
    """`M07`, exactement : la borne du critere, eprouvee **a sa frontiere**.

    Le paquet ne porte aujourd'hui aucun ouvreur a deux modules : la zone ou
    le critere mord est vide **par accident**, pas par construction, et c'est
    ce qui laissait `> 1` -> `> 2` sans un seul test rouge. Le temoin la
    remplit : une ligne annoncee par `ecran_projet` **et** par `palier_projet`
    -- deux modules, un seul domaine `Projet`.

    Le bloc « partout » est le seul des deux qui **n'ecrit pas** la parenthese
    du lieu : y ranger cette touche promettrait a l'operateur une touche
    partout sans pouvoir dire ou elle repond.
    """
    ecrans = tuple(f"{_PAQUET_TUI}.{module}.EcranTemoin{rang}"
                   for rang, module in enumerate(
                       _DEUX_MODULES_D_UN_MEME_DOMAINE))
    entrees = _derivation_avec(monkeypatch, [
        (f"{_PAQUET_TUI}.ecran_projet.RACCOURCIS_TEMOIN",
         f"{_OUVREUR_INVENTE} replier", ecrans)])
    temoin = entrees[_OUVREUR_INVENTE]
    assert temoin.partout is False, (temoin.ateliers, temoin.ecrans)
    # Et le temoin porte bien ses DEUX modules : sans quoi le verdict
    # `partout is False` viendrait d'un porteur perdu, pas du critere.
    assert temoin.ateliers == tuple(sorted(_DEUX_MODULES_D_UN_MEME_DOMAINE))


def test_DEUX_modules_de_domaines_DIFFERENTS_valent_partout(monkeypatch):
    """Le volet de morsure, sans lequel le test ci-dessus serait vert sur un
    critere qui ne rend plus jamais `partout`.

    Meme fabrique, meme ouvreur invente, **un seul module de difference**.
    """
    ecrans = tuple(f"{_PAQUET_TUI}.{module}.EcranTemoin{rang}"
                   for rang, module in enumerate(
                       _DEUX_MODULES_DE_DOMAINES_DIFFERENTS))
    entrees = _derivation_avec(monkeypatch, [
        (f"{_PAQUET_TUI}.ecran_projet.RACCOURCIS_TEMOIN",
         f"{_OUVREUR_INVENTE} replier", ecrans)])
    temoin = entrees[_OUVREUR_INVENTE]
    assert temoin.partout is True, (temoin.ateliers, temoin.ecrans)
    assert temoin.ateliers == tuple(sorted(_DEUX_MODULES_DE_DOMAINES_DIFFERENTS))


def test_le_DOMAINE_est_lu_de_projet_lecture_et_non_recopie(monkeypatch):
    """La liste des domaines **vient du produit**, elle n'est pas ecrite ici.

    Une liste recopiee serait verte le jour ou le produit ajoute un cinquieme
    atelier, et le manuel rangerait ses raccourcis sous un domaine que plus
    personne ne nomme. Le temoin ajoute un domaine **invente** a la source et
    verifie qu'il ressort : c'est la seule forme qui distingue une lecture
    d'une recopie.
    """
    from mixed_media_utility.tui import projet_lecture

    monkeypatch.setattr(projet_lecture, "ATELIERS",
                        projet_lecture.ATELIERS + ("Zircon",))
    assert "Zircon" in manuel.noms_de_domaine()
    assert manuel.atelier_lisible("mixed_media_utility.tui.atelier_zircon") == (
        "Zircon")


def test_les_DEUX_redactions_du_DOMAINE_sont_epinglees_a_l_EGALITE():
    """`ecran_manuel` porte encore sa propre copie : elles sont mesurees egales.

    La redaction qui fait foi est celle de `manuel` -- c'est elle que le
    critere `partout` consomme, et `manuel` ne peut pas importer `ecran_manuel`
    sans boucler. Tant que la copie d'aval vit, elle est epinglee a l'egalite
    plutot que laissee diverger : meme geste que
    :data:`manuel.SEPARATEUR_D_ITEMS` face au banc des majuscules. La fusion
    des trois lots de revue doit la remplacer par une re-exportation, et c'est
    dit dans le registre des findings.

    La comparaison porte sur **tous** les modules du paquet, plus deux formes
    que le paquet ne porte pas -- un module sans aucun domaine connu, et un
    module dont le domaine n'est pas le premier segment.
    """
    from mixed_media_utility.tui import ecran_manuel

    copie = getattr(ecran_manuel, "atelier_lisible", None)
    if copie is None or copie is manuel.atelier_lisible:
        pytest.skip("la copie d'aval a disparu ou est devenue une "
                    "re-exportation : il n'y a plus deux redactions a "
                    "epingler, ce qui est l'issue voulue")

    modules = sorted({classe.__module__
                      for classe in manuel.classes_d_ecran().values()})
    modules += [f"{_PAQUET_TUI}.zircon_sans_domaine",
                f"{_PAQUET_TUI}.ecran_scan_tardif"]
    assert modules, "le balayage ne rend aucun module"
    ecarts = {m: (manuel.atelier_lisible(m), ecran_manuel.atelier_lisible(m))
              for m in modules
              if manuel.atelier_lisible(m) != ecran_manuel.atelier_lisible(m)}
    assert ecarts == {}, ecarts
    assert set(manuel.noms_de_domaine()) == set(ecran_manuel.noms_de_domaine())


# ---------------------------------------------------------------------------
# Couche 1 `F5`, mutant `M11` -- l'ORDRE des collections d'une entree
# ---------------------------------------------------------------------------

#: Douze libelles **distinguables**, ecrits dans un ordre qui n'est PAS le
#: leur une fois tries. Douze parce que la propriete mesuree est « la sortie
#: est triee » : sur un ensemble de `n` elements, un ordre d'iteration
#: quelconque coincide avec l'ordre trie une fois sur `n!`, et `12!` place la
#: coincidence a deux chances sur un milliard. C'est ce qui rend cette mesure
#: fiable **sans** fixer `PYTHONHASHSEED` par un sous-processus.
_LIBELLES_TEMOINS = ("zebre", "myrtille", "abricot", "roseau", "cerise",
                     "hibou", "genet", "tilleul", "bruyere", "ocre",
                     "figue", "lichen")


def test_les_LIBELLES_d_un_ouvreur_sortent_TRIES_sur_une_fabrique_distinguable(
        monkeypatch):
    """`M11` : `libelles` se construit en `set`, donc sans tri il n'a pas
    d'ordre.

    `PYTHONHASHSEED` n'est pas fixe dans ce depot : le manuel cesserait d'etre
    reproductible d'un lancement a l'autre -- cinq graines, cinq rendus
    distincts des libelles d'`Échap`, mesure le 2026-09-03 -- sans qu'aucun
    test bouge. La politique classe l'ordre d'iteration en **critique, zero
    survivant**, et precise que mutmut ne genere jamais ce mutant : il ne
    s'obtient que par injection manuelle.

    La fabrique est **distinguable et desordonnee a la source** : douze
    libelles ecrits dans le desordre, sur douze lignes temoins d'un meme
    ouvreur invente. Elle ne depend d'aucun raccourci du produit du jour.
    """
    temoins = [(f"{_PAQUET_TUI}.ecran_projet.RACCOURCIS_TEMOIN_{rang}",
                f"{_OUVREUR_INVENTE} {libelle}",
                (f"{_PAQUET_TUI}.ecran_projet.EcranTemoin",))
               for rang, libelle in enumerate(_LIBELLES_TEMOINS)]
    temoin = _derivation_avec(monkeypatch, temoins)[_OUVREUR_INVENTE]
    assert temoin.libelles == tuple(sorted(_LIBELLES_TEMOINS)), temoin.libelles
    # Anti-vacuite : les douze sont bien tous la, et l'ordre ecrit n'etait
    # pas deja l'ordre trie -- sans quoi la frontiere serait sans objet.
    assert len(temoin.libelles) == len(_LIBELLES_TEMOINS)
    assert _LIBELLES_TEMOINS != tuple(sorted(_LIBELLES_TEMOINS))


def test_les_ECRANS_et_les_MODULES_d_un_ouvreur_sortent_TRIES_eux_aussi(
        monkeypatch):
    """Les deux autres collections de :class:`manuel.Entree`, meme mutant.

    Fermer `libelles` seul laisserait `ecrans` et `ateliers` sans temoin : ce
    sont trois `sorted()` distincts sur trois `set` distincts, donc trois
    mutants distincts. La fabrique place les modules dans le desordre, et sur
    **des domaines differents** pour que les deux collections soient
    reellement de cardinal superieur a un.
    """
    modules = ("palier_projet", "atelier_scan", "atelier_extraction",
               "atelier_pdf", "ecran_ateliers")
    ecrans = tuple(f"{_PAQUET_TUI}.{module}.EcranTemoin{rang}"
                   for rang, module in enumerate(modules))
    temoin = _derivation_avec(monkeypatch, [
        (f"{_PAQUET_TUI}.ecran_projet.RACCOURCIS_TEMOIN",
         f"{_OUVREUR_INVENTE} replier", ecrans)])[_OUVREUR_INVENTE]
    assert temoin.ecrans == tuple(sorted(ecrans)), temoin.ecrans
    assert temoin.ateliers == tuple(sorted(modules)), temoin.ateliers
    assert ecrans != tuple(sorted(ecrans)), "la fabrique est deja triee"


def test_AUCUNE_entree_du_produit_ne_sort_d_une_collection_NON_TRIEE():
    """Le meme invariant **sur le paquet reel**, en relation et sans cardinal.

    Il ne remplace pas la fabrique ci-dessus -- sa force depend de ce que le
    produit annonce le jour ou il tourne, et le produit change. Il ajoute ce
    que la fabrique ne peut pas dire : qu'aucun chemin du produit reel ne
    contourne le tri.
    """
    desordonnees = {
        entree.ouvreur: (entree.libelles, entree.ecrans, entree.ateliers)
        for entree in manuel.entrees_du_manuel()
        if (list(entree.libelles) != sorted(entree.libelles)
            or list(entree.ecrans) != sorted(entree.ecrans)
            or list(entree.ateliers) != sorted(entree.ateliers))}
    assert desordonnees == {}, desordonnees
    # Anti-vacuite : au moins une entree porte plusieurs libelles ET plusieurs
    # ecrans, sans quoi « trie » ne dirait rien.
    riches = [e.ouvreur for e in manuel.entrees_du_manuel()
              if len(e.libelles) > 1 and len(e.ecrans) > 1]
    assert riches, "aucune entree multiple : la mesure du tri serait vide"


# ---------------------------------------------------------------------------
# Couche 2 `F12`, mutant `M31` -- une ligne rend TOUS ses ecrans porteurs
# ---------------------------------------------------------------------------

#: Trois ecrans temoins **distinguables**, sur trois modules d'un meme
#: domaine, choisis pour que le tri du code les rende dans cet ordre-la. La
#: cible est verifiee **a chaque position** : en tete, au milieu et en queue
#: (regle des fabriques, points 2, 2 bis et 4). Une cible au seul milieu
#: demasque un `find` fautif mais pas un balayage tronque par un bout, qui est
#: un autre mode de panne -- mesure le 2026-09-03 sur un mutant survivant.
_TROIS_ECRANS_D_UNE_LIGNE = (
    f"{_PAQUET_TUI}.ecran_projet.EcranTemoinA",
    f"{_PAQUET_TUI}.ecran_projet.EcranTemoinM",
    f"{_PAQUET_TUI}.ecran_projet.EcranTemoinZ")


def test_une_ligne_portee_par_TROIS_ecrans_les_rend_TOUS_LES_TROIS(monkeypatch):
    """`M31` : `porteurs.update(ecrans)` tronque a un seul porteur.

    Mesure du mutant sur le produit : six lignes du paquet sont attribuees a
    deux ecrans, et n'en garder que le premier faisait perdre un porteur a
    plusieurs entrees **sans qu'un seul des 584 tests rougisse**. La raison
    etait nette : `Entree.ecrans` n'etait asserti que par `lettres_du_manuel`,
    dont les lignes sont toutes mono-ecran.

    L'egalite porte sur le tuple **entier**, donc sur les trois positions a la
    fois : un `[:1]`, un `[:-1]`, un `[1:]` et un `find` du premier venu
    rougissent tous les quatre.
    """
    temoin = _derivation_avec(monkeypatch, [
        (f"{_PAQUET_TUI}.ecran_projet.RACCOURCIS_TEMOIN",
         f"{_OUVREUR_INVENTE} replier", _TROIS_ECRANS_D_UNE_LIGNE)]
    )[_OUVREUR_INVENTE]
    assert temoin.ecrans == _TROIS_ECRANS_D_UNE_LIGNE, temoin.ecrans
    # Les deux BORDS, nommes separement : un rapport de rouge qui dit « la
    # queue manque » se relit, une egalite de tuples se dechiffre.
    assert _TROIS_ECRANS_D_UNE_LIGNE[0] in temoin.ecrans, "le porteur de TETE"
    assert _TROIS_ECRANS_D_UNE_LIGNE[-1] in temoin.ecrans, "le porteur de QUEUE"


def test_CHAQUE_ligne_du_paquet_rend_TOUS_ses_porteurs_a_CHACUN_de_ses_ouvreurs():
    """Le meme invariant sur le produit reel, ecrit en RELATION.

    Pour chaque ligne du paquet et chaque ouvreur qu'elle annonce, les ecrans
    que l'attribution donne a cette ligne se retrouvent dans les `ecrans` de
    l'entree. Aucun cardinal : ni le nombre de lignes multi-ecrans, ni le
    nombre d'entrees, ni un rang. La story 11.4e retire une entree du produit,
    et cette frontiere doit y survivre.

    **Ce qu'elle ne peut pas dire, et pourquoi la fabrique ci-dessus existe** :
    `Entree.ecrans` est une **union** sur toutes les lignes d'un ouvreur, donc
    un porteur perdu sur une ligne peut etre rendu par une autre -- c'est
    exactement l'aveuglement que la couche 3 a mesure sur les neuf ecrans de
    `Q`. La fabrique isole un ouvreur qui n'a qu'une seule ligne ; celle-ci
    couvre le produit.
    """
    attribution = manuel.ecrans_par_ligne()
    entrees = {e.ouvreur: e for e in manuel.entrees_du_manuel()}
    manquants = {}
    couverts = 0
    for cle, ligne in manuel.lignes_de_raccourcis_du_paquet().items():
        if manuel.MODULE_DU_MANUEL in cle.split("."):
            continue
        ecrans, _etage = attribution.get(cle, ((), manuel.ETAGE_ORPHELINE))
        if len(ecrans) > 1:
            couverts += 1
        for ouvreur, _libelle in manuel.items_d_une_ligne(ligne):
            absents = set(ecrans) - set(entrees[ouvreur].ecrans)
            if absents:
                manquants[(cle, ouvreur)] = sorted(absents)
    assert manquants == {}, manquants
    # Anti-vacuite : le paquet porte bien des lignes MULTI-ecrans, sans quoi
    # la relation ci-dessus serait vraie sur des singletons.
    assert couverts, "aucune ligne multi-ecrans : la relation est vide"


# ---------------------------------------------------------------------------
# Couche 1 `F10`, mutants `M16` et `M17` -- les deux gardes du balayage
# remonte dans `src/` (tolerances, fermees parce qu'elles sont bon marche)
# ---------------------------------------------------------------------------

#: Un module du paquet qui ne porte ni classe de palier ni ligne de
#: raccourcis : ce qu'un temoin y depose ne peut venir que du temoin.
_MODULE_NEUTRE = "jetons"


def test_le_balayage_IGNORE_une_classe_de_palier_venue_de_HORS_du_paquet(
        monkeypatch):
    """`M16` : la garde `objet.__module__.startswith(paquet.__name__)`.

    Son docstring dit pourquoi elle existe -- « le balayage voit les classes
    temoins fabriquees par les tests voisins, qui la faisaient rougir selon
    l'ordre d'execution ». Le code a ete **remonte** d'un banc vers `src/` au
    lot A1 : la garde a voyage, son motif n'avait jamais eu de mesure. Le
    temoin est litteralement le cas qu'elle decrit -- une sous-classe de
    `Palier` definie dans un banc, rendue visible depuis un module du paquet.
    """
    from mixed_media_utility.tui import jetons
    from mixed_media_utility.tui.coque import Palier

    class PalierEtrangerAuPaquet(Palier):
        pass

    assert not PalierEtrangerAuPaquet.__module__.startswith(_PAQUET_TUI)
    monkeypatch.setattr(jetons, "PalierEtrangerAuPaquet",
                        PalierEtrangerAuPaquet, raising=False)
    vues = manuel.classes_d_ecran()
    intruses = [nom for nom in vues if nom.endswith("PalierEtrangerAuPaquet")]
    assert intruses == [], intruses


def test_le_balayage_VOIT_la_meme_classe_des_qu_elle_appartient_au_paquet(
        monkeypatch):
    """Le volet de morsure de `M16`.

    Sans lui, un balayage qui ne verrait plus **aucune** classe rendrait le
    test ci-dessus vert. Meme classe, meme depot, **un seul attribut de
    difference** : son `__module__`.
    """
    from mixed_media_utility.tui import jetons
    from mixed_media_utility.tui.coque import Palier

    class PalierAdopteParLePaquet(Palier):
        pass

    monkeypatch.setattr(PalierAdopteParLePaquet, "__module__",
                        f"{_PAQUET_TUI}.{_MODULE_NEUTRE}")
    monkeypatch.setattr(jetons, "PalierAdopteParLePaquet",
                        PalierAdopteParLePaquet, raising=False)
    vues = manuel.classes_d_ecran()
    assert f"{_PAQUET_TUI}.{_MODULE_NEUTRE}.PalierAdopteParLePaquet" in vues


@pytest.mark.parametrize("balayage", [
    pytest.param("lignes_de_raccourcis_du_paquet", id="lignes"),
    pytest.param("ecrans_par_ligne", id="attribution"),
])
def test_une_constante_RACCOURCIS_NON_TEXTUELLE_est_ECARTEE(monkeypatch,
                                                            balayage):
    """`M17` : la garde `isinstance(valeur, str)`, **aux deux endroits**.

    Elle est ecrite deux fois -- une par balayage -- donc elle porte deux
    mutants distincts, et le paquet n'offre aucun temoin puisque toutes ses
    constantes `RACCOURCIS_*` sont des chaines. Sans temoin, retirer l'une ou
    l'autre laissait les 584 tests verts ; avec, une constante entiere
    remonterait jusqu'a `items_d_une_ligne`, qui appelle `.strip()`.
    """
    from mixed_media_utility.tui import jetons

    monkeypatch.setattr(jetons, "RACCOURCIS_CHIFFRE_TEMOIN", 3, raising=False)
    cle = f"{_PAQUET_TUI}.{_MODULE_NEUTRE}.RACCOURCIS_CHIFFRE_TEMOIN"
    assert cle not in getattr(manuel, balayage)()


@pytest.mark.parametrize("balayage", [
    pytest.param("lignes_de_raccourcis_du_paquet", id="lignes"),
    pytest.param("ecrans_par_ligne", id="attribution"),
])
def test_la_meme_constante_ENTRE_des_qu_elle_est_TEXTUELLE(monkeypatch,
                                                           balayage):
    """Le volet de morsure de `M17`, aux deux endroits.

    Meme module, meme nom de constante, **un seul type de difference**.
    """
    from mixed_media_utility.tui import jetons

    monkeypatch.setattr(jetons, "RACCOURCIS_CHIFFRE_TEMOIN",
                        f"{_OUVREUR_INVENTE} replier", raising=False)
    cle = f"{_PAQUET_TUI}.{_MODULE_NEUTRE}.RACCOURCIS_CHIFFRE_TEMOIN"
    assert cle in getattr(manuel, balayage)()


# ---------------------------------------------------------------------------
# Couche 2 `F6` -- ce que la derivation FAIT d'une ligne orpheline
# (tolerance : la mesure est ici, le choix produit du RENDU ne l'est pas)
# ---------------------------------------------------------------------------

def test_une_ligne_ORPHELINE_traverse_la_derivation_SANS_ecran_ni_domaine(
        monkeypatch):
    """Ce que le produit ferait d'une orpheline, epingle plutot que suppose.

    `test_AUCUNE_ligne_du_paquet_n_est_ORPHELINE` mesure qu'il n'y en a aucune
    au `HEAD` -- bonne frontiere, mais elle ne dit rien du jour ou elle
    rougit. Ici : la ligne traverse, elle ne fait pas tomber la derivation, et
    elle sort **sans porteur**, donc rangee du cote « propres a un ecran » --
    c'est-a-dire dans le seul bloc qui promet de nommer le lieu, et sans
    pouvoir le nommer.

    **Le verdict d'etage est calcule puis JETE** par `entrees_du_manuel`
    (`ecrans, _etage = attribution.get(...)`) : rien en aval ne le consomme.
    Faut-il ecarter les orphelines de la derivation, ou les rendre visibles
    par une mention ? C'est un choix de RENDU, il appartient a
    `tui/ecran_manuel.py` et il est verse a `deferred-work.md` avec son
    origine. Ce banc n'anticipe pas ce choix : il mesure l'etat actuel pour
    qu'un changement se voie.
    """
    entrees = _derivation_avec(monkeypatch, [
        (f"{_PAQUET_TUI}.module_sans_ecran.RACCOURCIS_TEMOIN",
         f"{_OUVREUR_INVENTE} replier", None)])
    temoin = entrees[_OUVREUR_INVENTE]
    assert temoin.ecrans == ()
    assert temoin.ateliers == ()
    assert temoin.partout is False
    # Et l'attribution, elle, SAIT le dire -- c'est la derivation qui jette
    # le verdict, pas l'attribution qui manque de le rendre.
    assert manuel.ETAGE_ORPHELINE == "orpheline"


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-1` et `E2-1b` pour
# justifier que `Rushes` et `Explorateur` sont des noms de ZONE et non des
# touches -- et n'ouvrait ni l'un ni l'autre. C'est le cas ou la recopie
# coute le plus : l'argument du test REPOSE sur ce que les dessins portent.

#: Le libelle de l'ajout, dessine au pied de `E2-1`. Confronte ci-dessous.
COUPLE_D_AJOUT_DESSINE = "ajouter un rush"

#: L'entree du test : une ligne FABRIQUEE qui mele les deux pieds, pour que
#: la fonction voie les deux noms de zone dans la meme ligne. Elle n'est
#: recopiee d'aucun dessin -- ce que la confrontation dit explicitement.
LIGNE_MELEE_DES_DEUX_ECRANS = "Rushes  ⏎ choisir  Explorateur  Tab ajouter un rush"

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_les_NOMS_DE_ZONE_ouvrent_bien_les_pieds_des_DEUX_dessins():
    """L'argument du test ci-dessus, mesure sur les dessins qu'il invoque.

    `E2-1` ouvre son pied par `Rushes`, `E2-1b` par `Explorateur`, et dans
    les deux cas le mot est suivi de couples touche/verbe. Les deux dessins
    plutot qu'un : un seul ne distinguerait pas « ce pied commence par un nom
    de zone » de « ce mot-la commence ce pied-la ».
    """
    rush = dessin_de_la_maquette("E2-1-extraction-rush.txt")
    explorateur = dessin_de_la_maquette("E2-1b-relink-chercher-dossier.txt")

    assert "Rushes Tab " + COUPLE_D_AJOUT_DESSINE in rush
    assert "Explorateur ⏎ valider" in explorateur

    # Chaque nom de zone n'ouvre QUE son propre pied.
    assert "Explorateur" not in rush
    assert "Rushes" not in explorateur.split("Explorateur")[1]


def test_la_ligne_d_entree_du_test_est_FABRIQUEE_et_non_recopiee():
    """Dit plutot que tu : cette ligne n'existe dans aucun dessin.

    Elle mele les deux pieds pour que la fonction voie deux noms de zone
    d'un coup -- ce qu'aucun ecran ne montre. Seul le couple `Tab ajouter un
    rush` en est repris, et lui est confronte a sa source.
    """
    rush = dessin_de_la_maquette("E2-1-extraction-rush.txt")
    explorateur = dessin_de_la_maquette("E2-1b-relink-chercher-dossier.txt")
    assert LIGNE_MELEE_DES_DEUX_ECRANS not in rush
    assert LIGNE_MELEE_DES_DEUX_ECRANS not in explorateur
    assert COUPLE_D_AJOUT_DESSINE in rush


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    rush = dessin_de_la_maquette("E2-1-extraction-rush.txt")
    assert "ajouter un lot" not in rush
    assert "Tab ajouter un rush du tournage" not in rush
