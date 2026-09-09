# -*- coding: utf-8 -*-
"""Les deux ecrans de progression PDF sont VIVANTS pendant que le coeur travaille.

**Ce banc mesure a l'EXECUTION ce que les autres lisent.** Le registre de
`test_frontiere_du_dessin_avant_le_coeur.py` est tombe a zero le 2026-09-06 :
plus aucun chemin du depot n'appelle le coeur juste apres avoir monte son
ecran. C'est une lecture -- une frontiere AST qui confronte des noms d'appels a
des positions dans un corps de fonction. Elle ne dit pas qu'un rotor tourne.

La phrase d'Egan, elle, porte sur ce qu'il voit : « tous les ecrans de
progression ne chargeaient pas. On passait de la confirmation au succes. Entre
les deux l'application restait muette parfois pendant plusieurs secondes ou
minutes. » La seule mesure qui reponde a cette phrase est de **monter les
ecrans pour de vrai** et de regarder s'ils bougent **pendant** que le coeur
travaille. C'est ce que fait ce fichier, et c'est ce qui separe « repare » de
« recompile ».

**Ce banc EST le seul du perimetre PDF a observer une horloge, et c'est
delibere.** `test_atelier_pdf_parcours.py` annonce en tete qu'aucun de ses
tests ne mesure une horloge, et `test_atelier_pdf_calibration.py` FIGE le rotor
par `_figer_le_rotor` -- deux disciplines payees par un piege reel (deux tests
du lot H qui se contredisaient via le meme minuteur). Elles restent justes pour
ce qu'elles mesurent : le mecanisme du rotor, qui s'appelle a la main.

Mais `E5-6c` n'a **que** ce minuteur pour bouger -- le canal du coeur emet un
jalon par page, une mire fait une page, il n'y en a donc qu'un et il tombe a la
fin. Un banc qui figerait l'horloge ici ne pourrait pas distinguer un rotor qui
tourne d'un rotor qui ne tourne pas, c'est-a-dire exactement le symptome
d'Egan. Les deux tests concernes assertent donc un **ecart entre zero et
non-zero** sous une borne genereuse, jamais un seuil de duree, et aucun
n'asserte qu'un pas ne bouge PAS -- c'est cette seconde forme qui avait
fabrique la contradiction du lot H.

**Les deux volets de frontiere que ce fichier porte, et pourquoi ils existent.**
Le volet A interdit qu'une classe **surcharge** `EcranExecution.sur_jalon` :
c'est par une surcharge, et non par un oubli, que la garde de fil a ete perdue
le 2026-09-06 sur `E5-4`. Le volet A bis exige que les deux lanceurs PDF
partent au fil **sous** un rendez-vous de dessin -- la frontiere du registre,
elle, se contente de l'un OU l'autre, ce qui est plus permissif que ce que ces
deux chemins promettent. Les deux volets sont nes d'un mutant survivant, pas
d'une intention : ils ferment ce que les mesures a l'execution ci-dessous ne
savaient pas voir.

**Regle des fabriques (`CLAUDE.md`), appliquee aux corpus de synthese** : des
cibles distinguables, une cible ailleurs qu'en premiere position, et une cible
a CHAQUE BORD -- tete et queue. Le point 4 est celui que ce depot paie le plus
souvent, et un balayage tronque en queue est precisement le mode de panne qui
rendrait un volet vert en mentant.

**Regle des drapeaux** : `ascii_seul` varie sur le rotor de `E5-6c`, dans les
deux sens, parce que `jetons.rotor` en depend et qu'un banc qui ne jouerait
qu'`ascii_seul=False` mesurerait la moitie du produit.
"""
from __future__ import annotations

import ast
import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# **La fabrique du parcours PDF est importee, jamais recopiee.** Monter `E5-4`
# demande un projet, un manifeste, trois lots aux tirages distinguables et le
# passage clavier par `E5-1` puis `E5-2` -- une centaine de lignes qui vivent
# deja dans le banc de cablage. Une seconde fabrique diverge le jour ou l'une
# des deux est corrigee, et c'est exactement ce que la regle des fabriques
# reproche a un remplissage uniforme : deux sources de verite pour un fait.
import test_atelier_pdf_parcours as cablage
from mixed_media_utility.io import project_layout
from mixed_media_utility.tui import atelier_pdf_calibration as calibration
from mixed_media_utility.tui import atelier_pdf_confirmation as confirmation
from mixed_media_utility.tui import atelier_pdf_execution as execution_pdf
from mixed_media_utility.tui import atelier_pdf_parcours as parcours_pdf
from mixed_media_utility.tui import jetons

PAQUET_TUI = _RACINE / "src" / "mixed_media_utility" / "tui"

#: Duree de la passe de synthese des temoins symetriques. La mesure ne depend
#: pas de sa valeur : c'est un ECART entre zero et non-zero qui est asserte.
DUREE_DU_GEL = 0.35

#: Borne de patience des mesures a l'execution. Genereuse : sous charge une
#: boucle vivante met plus longtemps, mais une boucle MORTE ne bouge jamais,
#: quelle que soit la patience. C'est cet ecart-la qui est mesure.
PATIENCE = 8.0


# ===========================================================================
# Volet A -- AUCUNE SURCHARGE de `sur_jalon` : la garde s'herite ou se perd
# ===========================================================================

#: La classe qui porte la garde de fil, et la methode qu'elle protege.
#: `EcranExecution.sur_jalon` teste le fil courant et, s'il n'est pas celui de
#: la boucle, reporte le rafraichissement par `call_from_thread`.
BASE_DU_JALON = ("execution.py", "EcranExecution")
METHODE_GARDEE = "sur_jalon"


def sur_jalons_de(source: str) -> list[tuple[str, str]]:
    """Les `(classe, methode)` qui DEFINISSENT `sur_jalon` dans une source.

    Le balayage descend dans TOUTES les classes du module, y compris
    imbriquees : une classe definie dans une fonction est un ecran comme un
    autre pour `textual`.
    """
    arbre = ast.parse(source)
    releve: list[tuple[str, str]] = []
    for classe in [n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)]:
        for methode in classe.body:
            if (isinstance(methode, ast.FunctionDef)
                    and methode.name == METHODE_GARDEE):
                releve.append((classe.name, methode.name))
    return releve


def porte_la_garde_de_fil(source: str, classe: str) -> bool:
    """La `sur_jalon` de `classe` teste-t-elle le fil courant ?

    Deux marques, et il faut les deux : le test de fil (`get_ident`) et le
    report (`call_from_thread`). L'une sans l'autre est soit une garde qui ne
    garde rien, soit un report inconditionnel -- que `textual` refuse depuis la
    boucle.
    """
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.ClassDef) or noeud.name != classe:
            continue
        for methode in noeud.body:
            if (isinstance(methode, ast.FunctionDef)
                    and methode.name == METHODE_GARDEE):
                corps = ast.dump(methode)
                return "get_ident" in corps and "call_from_thread" in corps
    return False


def releve_du_paquet() -> list[tuple[str, str]]:
    """`(module, classe)` de chaque `sur_jalon` defini dans le paquet TUI."""
    releve = []
    for chemin in sorted(PAQUET_TUI.rglob("*.py")):
        for classe, _ in sur_jalons_de(chemin.read_text(encoding="utf-8")):
            releve.append((chemin.name, classe))
    return releve


def test_AUCUNE_classe_ne_SURCHARGE_sur_jalon_hors_de_sa_base():
    """La frontiere, et elle nomme le defaut plutot que sa consequence.

    **Ce que ce lot a paye, et il l'a paye le jour meme.**
    `EcranExecution.sur_jalon` porte une garde de fil dont le docstring dit
    pourquoi elle est la plutot que chez chaque appelant : « un atelier qui
    partirait au fil demain OUBLIERAIT de la reposer, et le defaut est
    invisible ». Le meme jour, les ateliers Scan puis PDF sont partis au fil.
    La garde a bien tenu pour les ecrans qui en **heritent** -- et
    `EcranGenerationDesPlanches` ne le faisait pas : il **surchargeait**
    `sur_jalon`, et la surcharge avait emporte la garde avec la methode qu'elle
    remplacait. Sonde a l'execution sur le parcours reel, trois pages : **3
    rafraichissements sur 7 hors de la boucle**, un par jalon.

    **La frontiere interdit la SURCHARGE plutot que d'exiger une garde de
    plus**, et c'est la difference qui compte. Exiger que chaque surcharge
    reporte a son tour, c'est demander a chaque auteur de se souvenir -- la
    consigne qui a echoue. Interdire la surcharge ferme la classe entiere de
    defauts : ce qui n'existe pas ne peut rien oublier. Le correctif du
    2026-09-06 a donc **retire** la surcharge au lieu d'y ajouter une garde ;
    la base ignore de toute facon son argument et rappelle `self.rafraichir()`,
    que la sous-classe surcharge deja.

    Un ecran qui aurait vraiment besoin d'autre chose fera rougir cette ligne,
    et c'est voulu : il faut la lire avant de la contourner.
    """
    surcharges = [entree for entree in releve_du_paquet()
                  if entree != BASE_DU_JALON]
    assert not surcharges, (
        f"ces classes SURCHARGENT `{METHODE_GARDEE}` : elles court-circuitent"
        f" la garde de fil de `{BASE_DU_JALON[1]}` et mutent l'arbre de widgets"
        " depuis le fil de travail -- ce que `textual` ne signale pas et qui"
        " casse au hasard.\n"
        + "\n".join(f"    {mod}::{cls}.{METHODE_GARDEE}"
                    for mod, cls in surcharges)
        + "\n\nLe geste : porter le travail dans `rafraichir`, que la base"
        " rappelle apres avoir reporte sur la boucle.")


def test_la_BASE_porte_encore_sa_garde_de_fil():
    """La contrepartie, et sans elle la frontiere ci-dessus serait creuse.

    Interdire les surcharges ne vaut que si ce dont on herite garde. Une base
    qui perdrait son test de fil rendrait le volet A vert sur un paquet
    entierement fautif -- la forme de panne la plus couteuse d'une frontiere.
    """
    source = (PAQUET_TUI / BASE_DU_JALON[0]).read_text(encoding="utf-8")
    assert porte_la_garde_de_fil(source, BASE_DU_JALON[1]), (
        f"`{BASE_DU_JALON[1]}.{METHODE_GARDEE}` ne teste plus le fil courant :"
        " tous les ecrans de progression du paquet mutent alors l'arbre depuis"
        " le fil de travail, et cette frontiere ne le verrait pas")


def test_le_balayage_VOIT_le_sur_jalon_du_paquet():
    """Le cardinal exact, pour qu'un balayage muet ne passe pas pour vert.

    Un unique `sur_jalon` au 2026-09-06, celui de la base. Un second fera
    rougir la frontiere ci-dessus **et** cette ligne : deux rouges pour un
    seul fait, ce qui est voulu -- l'un dit la regle, l'autre dit que la
    mesure a bien vu quelque chose.
    """
    assert releve_du_paquet() == [BASE_DU_JALON], releve_du_paquet()


def test_le_detecteur_ATTRAPE_une_surcharge():
    """Le detecteur se mesure, sinon une frontiere verte ne prouve rien."""
    surcharge = (
        "class Ecran(EcranExecution):\n"
        "    def sur_jalon(self, avancement):\n"
        "        self.rafraichir()\n"
    )
    assert sur_jalons_de(surcharge) == [("Ecran", "sur_jalon")]


def test_le_detecteur_ACQUITTE_une_classe_qui_HERITE():
    """Le symetrique : un detecteur qui verrait `sur_jalon` partout serait
    rouge sur tout le paquet, donc ignore en une semaine."""
    heritiere = (
        "class Ecran(EcranExecution):\n"
        "    def rafraichir(self):\n"
        "        self._corps.update('')\n"
    )
    assert sur_jalons_de(heritiere) == []


def test_le_detecteur_de_GARDE_lit_les_DEUX_marques():
    """Une marque seule ne fait pas une garde, et les deux manques diffèrent.

    Un test de fil sans report laisse l'appel muter l'arbre quand meme ; un
    report sans test de fil leve des que le jalon vient de la boucle. Le
    detecteur doit refuser les deux, sinon la contrepartie ci-dessus acquitte
    une base cassee.
    """
    gardee = (
        "class B:\n"
        "    def sur_jalon(self, a):\n"
        "        if self.app._thread_id != threading.get_ident():\n"
        "            self.app.call_from_thread(self.rafraichir)\n"
        "            return\n"
        "        self.rafraichir()\n"
    )
    test_seul = (
        "class B:\n"
        "    def sur_jalon(self, a):\n"
        "        if self.app._thread_id != threading.get_ident():\n"
        "            return\n"
        "        self.rafraichir()\n"
    )
    report_seul = (
        "class B:\n"
        "    def sur_jalon(self, a):\n"
        "        self.app.call_from_thread(self.rafraichir)\n"
    )
    assert porte_la_garde_de_fil(gardee, "B") is True
    assert porte_la_garde_de_fil(test_seul, "B") is False
    assert porte_la_garde_de_fil(report_seul, "B") is False
    # Et une classe absente n'est pas acquittee par defaut.
    assert porte_la_garde_de_fil(gardee, "Absente") is False


#: Corpus de synthese du volet A. **Regle des fabriques, les quatre points** :
#: cinq classes distinguables (des noms differents, jamais un remplissage
#: uniforme), des `sur_jalon` en TETE et en QUEUE, et une cible au MILIEU. Les
#: trois positions repondent a trois modes de panne distincts : un balayage qui
#: rendrait toujours le premier, un balayage tronque en queue, et un balayage
#: qui s'arreterait au premier trouve.
CORPUS_A = (
    "class EnTete:\n"
    "    def sur_jalon(self, a):\n"
    "        self.rafraichir()\n"
    "\n"
    "class SansJalon:\n"
    "    def rafraichir(self):\n"
    "        pass\n"
    "\n"
    "class AuMilieu:\n"
    "    def sur_jalon(self, a):\n"
    "        if self.app._thread_id != threading.get_ident():\n"
    "            self.app.call_from_thread(self.rafraichir)\n"
    "            return\n"
    "        self.rafraichir()\n"
    "\n"
    "class AutreSansJalon:\n"
    "    def contenu(self):\n"
    "        return []\n"
    "\n"
    "class EnQueue:\n"
    "    def sur_jalon(self, a):\n"
    "        self.rafraichir()\n"
)


def test_le_corpus_est_releve_ENTIEREMENT_des_deux_BORDS():
    """Point 4 de la regle des fabriques : une cible a CHAQUE bord.

    Une cible au milieu demasque un balayage qui rendrait toujours le premier ;
    elle ne demasque **pas** un balayage tronque. Les deux modes de panne sont
    distincts, et c'est la troisieme fois que ce depot le paie en mutants
    survivants plutot qu'en relecture.

    Les gardes sont distinguables elles aussi -- seule `AuMilieu` en porte
    une --, sans quoi un corpus uniforme cacherait une permutation.
    """
    releve = sur_jalons_de(CORPUS_A)
    assert [c for c, _ in releve] == ["EnTete", "AuMilieu", "EnQueue"]
    assert [porte_la_garde_de_fil(CORPUS_A, c) for c, _ in releve] == [
        False, True, False]


@pytest.mark.parametrize("bord", ["tete", "queue"])
def test_une_TRONCATURE_du_balayage_se_voit_a_CHAQUE_bord(bord):
    """Le mutant de bord, pose des deux cotes et tue des deux cotes.

    C'est l'oracle du test precedent, rendu independant du detecteur : on
    tronque le releve lui-meme et on verifie qu'il change. Un balayage qui
    sauterait un bord rendrait le meme releve sur les deux corpus.
    """
    classes = [c for c, _ in sur_jalons_de(CORPUS_A)]
    tronque = classes[1:] if bord == "tete" else classes[:-1]
    assert tronque != classes, (
        "la troncature ne change rien : le corpus ne porte pas de cible a ce"
        f" bord ({bord}), donc le balayage n'y est pas mesure")


def test_les_cibles_du_corpus_sont_DISTINGUABLES():
    """Point 1 : cinq classes, cinq noms. Un corpus uniforme cache une
    permutation, et c'est la classe de defaut payee trois fois par ce depot."""
    noms = [n.name for n in ast.walk(ast.parse(CORPUS_A))
            if isinstance(n, ast.ClassDef)]
    assert len(noms) == len(set(noms)) == 5, noms


def traduction_avant_la_garde_de_taille(source: str, classe: str) -> bool:
    """Dans le `rafraichir` de `classe`, la lecture de l'avancement precede-
    t-elle le premier `return` ?

    **Detecteur separe du test qu'il sert, et une campagne l'a impose.** Ecrite
    en ligne dans son test, la comparaison `lecture < garde` etait un `assert`
    que rien ne mesurait : un mutant qui l'affaiblissait restait vert, puisque
    le produit est correct des deux cotes d'une assertion toujours vraie. Un
    oracle ne se tue que s'il est jouable sur autre chose que la seule source
    qu'il valide -- d'ou cette fonction, et le corpus a deux ordres qui la
    mesure.
    """
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.ClassDef) or noeud.name != classe:
            continue
        for methode in noeud.body:
            if not (isinstance(methode, ast.FunctionDef)
                    and methode.name == "rafraichir"):
                continue
            lectures = [n.lineno for n in ast.walk(methode)
                        if isinstance(n, ast.Attribute)
                        and n.attr == "avancement"]
            gardes = [n.lineno for n in ast.walk(methode)
                      if isinstance(n, ast.Return)]
            if not lectures or not gardes:
                return False
            return min(lectures) < min(gardes)
    return False


def test_le_TRAVAIL_du_jalon_est_fait_AVANT_la_garde_de_taille():
    """Le piege de la suppression de la surcharge, et il est mesure.

    La surcharge retiree ecrivait l'etat de la passe **quoi qu'il arrive** ; le
    `rafraichir` qui la remplace commence, lui, par rendre la main quand la
    fenetre est trop petite. Y laisser tomber la traduction figerait la
    progression sous le plancher 80x24 -- une regression que rien d'autre ne
    verrait, puisque l'ecran ne se dessine de toute facon pas.
    """
    source = (PAQUET_TUI / "atelier_pdf_execution.py").read_text(
        encoding="utf-8")
    assert traduction_avant_la_garde_de_taille(
        source, "EcranGenerationDesPlanches"), (
        "la traduction du jalon est passee SOUS la garde de taille : l'etat de"
        " la passe n'est plus ecrit quand la fenetre est trop petite, et la"
        " progression se fige sous le plancher 80x24")


#: Corpus des DEUX ORDRES. **Regle des fabriques, les quatre points** : six
#: classes distinguables, les deux fautes aux deux BORDS -- l'ordre inverse en
#: tete, l'absence de lecture en queue --, la forme correcte au milieu, et
#: **deux classes ou le PREMIER et le DERNIER d'une meme famille ne donnent pas
#: le meme verdict**. Ces deux-la sont nees d'un mutant survivant : tant que
#: chaque classe ne portait qu'une lecture et qu'un `return`, `min` et `max`
#: coincidaient, et un detecteur qui comparait les maxima passait -- exactement
#: le remplissage uniforme que le point 1 proscrit.
CORPUS_DE_L_ORDRE = (
    "class OrdreInverse:\n"
    "    def rafraichir(self):\n"
    "        if not self._assez_grand:\n"
    "            return\n"
    "        a = self.surface.avancement\n"
    "\n"
    "class LueAvantPuisEncoreApres:\n"
    "    def rafraichir(self):\n"
    "        a = self.surface.avancement\n"
    "        if not self._assez_grand:\n"
    "            return\n"
    "        b = self.surface.avancement\n"
    "\n"
    "class Correct:\n"
    "    def rafraichir(self):\n"
    "        a = self.surface.avancement\n"
    "        if not self._assez_grand:\n"
    "            return\n"
    "\n"
    "class GardeeAvantPuisEncoreApres:\n"
    "    def rafraichir(self):\n"
    "        if not self._assez_grand:\n"
    "            return\n"
    "        a = self.surface.avancement\n"
    "        if self._fini:\n"
    "            return\n"
    "\n"
    "class SansGarde:\n"
    "    def rafraichir(self):\n"
    "        a = self.surface.avancement\n"
    "\n"
    "class SansLecture:\n"
    "    def rafraichir(self):\n"
    "        if not self._assez_grand:\n"
    "            return\n"
)


@pytest.mark.parametrize(("classe", "attendu"), [
    ("OrdreInverse", False),
    ("LueAvantPuisEncoreApres", True),
    ("Correct", True),
    ("GardeeAvantPuisEncoreApres", False),
    ("SansGarde", False),
    ("SansLecture", False),
    ("Absente", False),
])
def test_le_detecteur_de_l_ORDRE_se_mesure_aux_DEUX_sens(classe, attendu):
    """L'oracle de l'oracle : les deux ordres, et les deux manques.

    Trois cas meritent d'etre nommes :

    * `SansGarde` -- un `rafraichir` sans `return` de taille lit bien
      l'avancement, mais la question posee n'a plus de sens. Rendre vrai
      la-dessus ferait passer pour mesuree une propriete qui n'existe plus dans
      ce corps ; il est donc **faux** ;
    * `LueAvantPuisEncoreApres` -- lue en tete PUIS relue plus bas. C'est
      **vrai** : ce qui compte est que la premiere lecture precede la garde.
      Un detecteur qui comparerait les DERNIERES occurrences le declarerait
      faux ;
    * `GardeeAvantPuisEncoreApres` -- gardee en tete, un second `return` plus
      bas. C'est **faux**, et le meme detecteur fautif le declarerait vrai.

    Les deux derniers sont la seule raison pour laquelle `min` ne peut pas etre
    remplace par `max` en silence -- un mutant a survecu tant qu'ils
    manquaient.
    """
    assert traduction_avant_la_garde_de_taille(
        CORPUS_DE_L_ORDRE, classe) is attendu


def test_le_corpus_de_l_ORDRE_porte_ses_SIX_classes_DISTINGUABLES():
    """Point 1 et point 4 : six noms, et les deux fautes aux deux bords."""
    noms = [n.name for n in ast.walk(ast.parse(CORPUS_DE_L_ORDRE))
            if isinstance(n, ast.ClassDef)]
    assert noms == ["OrdreInverse", "LueAvantPuisEncoreApres", "Correct",
                    "GardeeAvantPuisEncoreApres", "SansGarde", "SansLecture"]
    assert traduction_avant_la_garde_de_taille(
        CORPUS_DE_L_ORDRE, noms[0]) is False
    assert traduction_avant_la_garde_de_taille(
        CORPUS_DE_L_ORDRE, noms[-1]) is False


# ===========================================================================
# Volet A bis -- LES DEUX PROPRIETES, et il en faut DEUX
# ===========================================================================

#: Les deux lanceurs PDF, et le nom de leur ouvrier. Nommes plutot que
#: decouverts : un balayage qui les chercherait tout seul pourrait n'en trouver
#: aucun et rester vert, ce qui est le mode de panne le plus courant de ce
#: depot. Une entree de plus se lit avant de s'ajouter.
LANCEURS_PDF = {
    "generer": "pdf-generer",
    "generer_la_mire": "pdf-mire",
}

RENDEZ_VOUS = "_lancer_apres_le_dessin"
FIL = "run_worker"


def _appels(noeud: ast.AST) -> set[str]:
    """Les noms sous lesquels les appels d'un sous-arbre sont ecrits."""
    noms = set()
    for n in ast.walk(noeud):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Attribute):
            noms.add(n.func.attr)
        elif isinstance(n.func, ast.Name):
            noms.add(n.func.id)
    return noms


def fil_sous_rendez_vous(source: str, nom: str) -> tuple[bool, bool, bool]:
    """`(a_le_rendez_vous, a_le_fil, le_fil_est_SOUS_le_rendez_vous)`.

    La troisieme est la seule qui distingue les deux formes correctes de la
    forme tiede : un chemin qui prend rendez-vous **puis** part au fil ailleurs
    dans son corps a bien les deux appels, et n'a pourtant pas la propriete.
    """
    arbre = ast.parse(source)
    fonction = next(
        (n for n in ast.walk(arbre)
         if isinstance(n, ast.FunctionDef) and n.name == nom), None)
    assert fonction is not None, f"aucune fonction nommee {nom!r}"
    appels = _appels(fonction)
    sous = any(
        FIL in _appels(appel)
        for appel in ast.walk(fonction)
        if isinstance(appel, ast.Call)
        and isinstance(appel.func, ast.Name) and appel.func.id == RENDEZ_VOUS)
    return RENDEZ_VOUS in appels, FIL in appels, sous


@pytest.mark.parametrize("lanceur", sorted(LANCEURS_PDF))
def test_les_deux_lanceurs_PDF_partent_au_fil_SOUS_un_rendez_vous(lanceur):
    """Les deux proprietes sont distinctes, et il faut **les deux**.

    Le rapport du 2026-09-06 le dit en toutes lettres : « le rendez-vous de
    dessin fait apparaitre l'ecran UNE FOIS ; le fil est ce qui le garde vivant
    PENDANT la passe ». La frontiere du registre, elle, acquitte un chemin qui
    a l'un **ou** l'autre -- c'est son contrat, et il est plus permissif que ce
    que ces deux chemins-ci promettent.

    **C'est un mutant survivant qui a impose cette ligne.** Retirer le
    rendez-vous de `generer_la_mire` en gardant le fil laissait tout le reste
    de ce banc vert : la boucle etant libre, `on_mount` finit par tourner, le
    rotor par tourner aussi, et les images par sortir. Ce qui se perd est la
    **garantie d'ordre** -- que l'ecran soit peint avant que le coeur parte --
    et elle ne se mesure pas a l'execution sans ordonner deux fils a la
    milliseconde. Elle se mesure ici, par construction.

    La troisieme lecture est celle qui compte : le fil doit etre **sous** le
    rendez-vous. Les deux appels presents cote a cote ne donnent pas l'ordre.
    """
    source = (PAQUET_TUI / "atelier_pdf_parcours.py").read_text(
        encoding="utf-8")
    rendez_vous, fil, sous = fil_sous_rendez_vous(source, lanceur)
    assert rendez_vous, (
        f"`{lanceur}` ne prend plus rendez-vous : son ecran peut partir sans"
        " avoir ete peint une seule fois")
    assert fil, (
        f"`{lanceur}` n'appelle plus `{FIL}` : la boucle est reprise par le"
        " coeur, l'ecran se fige et les touches s'accumulent")
    assert sous, (
        f"`{lanceur}` porte les deux appels mais le fil n'est pas SOUS le"
        " rendez-vous : rien ne garantit que l'ecran soit peint avant que le"
        " coeur parte")


def test_le_nom_de_l_OUVRIER_de_chaque_lanceur_est_le_sien():
    """Deux ouvriers homonymes rendraient les deux mesures interchangeables.

    Le banc de cablage attend `pdf-generer` et `pdf-mire` par leur nom ; si les
    deux chemins portaient le meme, deux tests passeraient en ne mesurant
    qu'une seule des deux entrees. C'est le meme motif que la regle des
    fabriques oppose a un remplissage uniforme.
    """
    source = (PAQUET_TUI / "atelier_pdf_parcours.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    trouves = {}
    for nom in LANCEURS_PDF:
        fonction = next(n for n in ast.walk(arbre)
                        if isinstance(n, ast.FunctionDef) and n.name == nom)
        for appel in ast.walk(fonction):
            if (isinstance(appel, ast.Call)
                    and isinstance(appel.func, ast.Attribute)
                    and appel.func.attr == FIL):
                trouves[nom] = next(
                    (mc.value.value for mc in appel.keywords
                     if mc.arg == "name"), None)
    assert trouves == LANCEURS_PDF, trouves
    assert len(set(trouves.values())) == len(trouves), trouves


#: Corpus du volet A bis. **Regle des fabriques** : quatre lanceurs
#: distinguables, la forme correcte au MILIEU, et les deux formes fautives aux
#: deux BORDS -- le fil nu en tete, le rendez-vous vide en queue.
CORPUS_A_BIS = (
    "def fil_nu(self):\n"
    "    self.app.run_worker(passe, thread=True)\n"
    "\n"
    "def correct(self):\n"
    "    _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(\n"
    "        passe, thread=True))\n"
    "\n"
    "def cote_a_cote(self):\n"
    "    _lancer_apres_le_dessin(self.app, lambda: None)\n"
    "    self.app.run_worker(passe, thread=True)\n"
    "\n"
    "def rendez_vous_vide(self):\n"
    "    _lancer_apres_le_dessin(self.app, lambda: None)\n"
)


@pytest.mark.parametrize(("nom", "attendu"), [
    ("fil_nu", (False, True, False)),
    ("correct", (True, True, True)),
    ("cote_a_cote", (True, True, False)),
    ("rendez_vous_vide", (True, False, False)),
])
def test_le_detecteur_du_volet_A_bis_se_mesure_aux_QUATRE_formes(nom, attendu):
    """Le detecteur, sur les quatre formes et aux deux bords du corpus.

    `cote_a_cote` est celle qui compte : les deux appels sont la, et la
    propriete ne l'est pas. Un detecteur qui ne ferait qu'additionner des
    presences l'acquitterait.
    """
    assert fil_sous_rendez_vous(CORPUS_A_BIS, nom) == attendu


def test_le_corpus_A_bis_porte_ses_QUATRE_formes_DISTINGUABLES():
    """Point 1 : quatre noms, quatre corps differents. Et les deux fautes sont
    aux deux BORDS -- un balayage tronque a l'un ou l'autre bout acquitterait
    exactement la forme qu'il ne voit plus."""
    noms = [n.name for n in ast.walk(ast.parse(CORPUS_A_BIS))
            if isinstance(n, ast.FunctionDef)]
    assert noms == ["fil_nu", "correct", "cote_a_cote", "rendez_vous_vide"]
    assert fil_sous_rendez_vous(CORPUS_A_BIS, noms[0])[2] is False
    assert fil_sous_rendez_vous(CORPUS_A_BIS, noms[-1])[2] is False


# ===========================================================================
# Volet B -- L'EXECUTION. Les ecrans montes pour de vrai, et ce qu'ils font
#            PENDANT que le coeur travaille.
# ===========================================================================


def compteur_d_images(app) -> dict:
    """Compte les ecritures au pilote `textual`, c'est-a-dire les IMAGES.

    `is_mounted` dit qu'un objet existe ; il ne dit pas qu'un pixel a atteint
    le terminal, et c'est bien de pixels qu'Egan parle. Le pilote est le
    dernier maillon avant l'ecran.

    Technique reprise du volet 5a de `test_frontiere_du_dessin_avant_le_coeur`,
    ou elle a ete etablie -- la difference tient a ce qu'on y branche : la-bas
    un palier de synthese, ici les deux ecrans du produit sur leur parcours
    reel.
    """
    pilote = app._driver
    ecrire = pilote.write
    boite = {"images": 0}

    def compte(texte):
        boite["images"] += 1
        return ecrire(texte)

    pilote.write = compte
    return boite


class CoeurQuiSArrete(cablage.CoeurDouble):
    """Le coeur des planches, **arrete en plein travail** sur un jalon donne.

    C'est ce qui rend la mesure possible sans horloge : au lieu d'attendre et
    d'esperer avoir regarde au bon moment, on retient le coeur DANS son fil et
    on observe l'ecran a loisir. Le jalon d'arret est emis **avant** l'arret --
    `rappel_progression` etant reporte sur la boucle, il est deja applique
    quand le fil se bloque.
    """

    def __init__(self, *, pages, arret_apres: int):
        super().__init__(pages=pages)
        self.arret_apres = arret_apres
        #: Pose par le FIL quand il atteint son point d'arret.
        self.arrive = threading.Event()
        #: Pose par le TEST pour rendre la main au coeur.
        self.reprendre = threading.Event()

    def __call__(self, dossier_projet, *, rappel_progression=None, **reste):
        def relais(rang, total):
            if rappel_progression is not None:
                rappel_progression(rang, total)
            if rang == self.arret_apres:
                self.arrive.set()
                # La borne evite qu'un banc rouge suspende la suite entiere :
                # sans elle, un test qui echoue avant de liberer le coeur
                # laisserait le fil bloque pour toujours.
                self.reprendre.wait(timeout=PATIENCE * 2)

        return super().__call__(dossier_projet,
                                rappel_progression=relais, **reste)


class MireQuiSArrete:
    """Le coeur de la mire, retenu dans son fil. Meme geste, autre entree."""

    def __init__(self) -> None:
        self.appels: list[dict] = []
        self.arrive = threading.Event()
        self.reprendre = threading.Event()

    def __call__(self, dossier_projet, **reglages):
        self.appels.append(dict(dossier=Path(dossier_projet), **reglages))
        self.arrive.set()
        self.reprendre.wait(timeout=PATIENCE * 2)
        chemin = Path(dossier_projet) / project_layout.PLANCHES_DIRNAME / "mire.pdf"
        return cablage._Issue(
            plan=cablage._Plan(1, "tpl-a4-paysage-6f-v2", ()),
            output_path=chemin)


async def attendre(pilote, condition, quoi: str, patience: float = PATIENCE):
    """Rendre la main a la boucle jusqu'a `condition()`, ou echouer en le disant.

    `pilote.pause()` seul ne suffit pas : il draine la file de messages, il ne
    laisse pas passer le temps qu'un `set_interval` attend. Le `sleep` est donc
    ce qui rend la boucle observable, et la borne est ce qui empeche un banc
    rouge de suspendre la course -- CLAUDE.md : « le plafond est par test, le
    test qui suspend meurt seul », et un banc qui s'y fie quand meme est un
    banc qui a renonce a dire ce qu'il mesure.
    """
    limite = time.monotonic() + patience
    while time.monotonic() < limite:
        if condition():
            return True
        await pilote.pause()
        await asyncio.sleep(0.02)
    raise AssertionError(
        f"{quoi} n'est pas arrive en {patience} s. Une boucle VIVANTE y arrive"
        " en quelques dizaines de millisecondes ; une boucle prise par un"
        " appel synchrone n'y arrive jamais, quelle que soit la patience.")


def monter_jusqu_a_la_confirmation(pilote, dossier, coeur):
    """Le parcours au clavier jusqu'a `E5-3`, visant `Generer`.

    Passe par les ecrans, jamais par les rappels : ce qu'on mesure est ce qu'un
    operateur obtient de son clavier.
    """
    parcours = cablage._parcours(pilote.app, dossier, coeur=coeur)
    parcours.ouvrir().traiter("enter")
    return parcours


# -- `E5-4` : la barre avance, sans une horloge ------------------------------


def test_E5_4_est_PEINT_et_sa_BARRE_AVANCE_pendant_que_le_coeur_travaille(
        tmp_path, banc):
    """La reponse a la phrase d'Egan, sur `E5-4` et a l'execution.

    Trois pages, le coeur retenu dans son fil apres la premiere. Pendant qu'il
    est retenu -- donc pendant qu'il « travaille » du point de vue de
    l'operateur -- on lit ce que l'ecran montre :

    * l'ecran du dessus est bien `E5-4`, et il est **monte** ;
    * des images ont ete ecrites au pilote : elles ne l'etaient pas avant la
      reparation, et c'est la moitie « on ne voit rien » du symptome ;
    * la barre porte **le premier jalon**, pas zero et pas trois : la
      progression avance PENDANT la passe et non a sa fin.

    **Aucune horloge ici**, et c'est ce qui rend ce test-ci deterministe : le
    coeur est retenu par un evenement, pas par une duree, et le jalon qui fait
    avancer la barre est emis par le coeur lui-meme.
    """
    dossier = cablage._projet(tmp_path)
    coeur = CoeurQuiSArrete(pages={cablage.LOT_SANS_TIRAGE: 3}, arret_apres=1)
    app = cablage._app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = monter_jusqu_a_la_confirmation(pilote, dossier, coeur)
        await pilote.pause()
        cablage._cocher_et_regler(parcours, pilote.app.screen,
                                  lots=[cablage.LOT_SANS_TIRAGE])
        await pilote.pause()
        pilote.app.screen.choix.viser(confirmation.ISSUE_GENERER)
        boite = compteur_d_images(pilote.app)
        try:
            parcours.generer()
            await attendre(pilote, coeur.arrive.is_set,
                           "le coeur n'a pas atteint son premier jalon")
            # **ICI le coeur est BLOQUE dans son fil.** Tout ce qui suit
            # decrit donc ce que l'operateur a sous les yeux pendant l'attente.
            ecran = pilote.app.screen
            mesure["ecran"] = type(ecran).__name__
            mesure["monte"] = ecran.is_mounted
            mesure["images"] = boite["images"]
            mesure["faites"] = ecran.passe.pages_du_lot_courant
        finally:
            coeur.reprendre.set()
        await attendre(pilote,
                       lambda: ("pdf", cablage.LOT_SANS_TIRAGE) in coeur.trace,
                       "la passe ne se termine pas")
        for _ in range(5):
            await pilote.pause()
        mesure["ecran_final"] = type(pilote.app.screen).__name__

    cablage._jouer(scenario, app, banc)

    assert mesure["ecran"] == execution_pdf.EcranGenerationDesPlanches.__name__
    assert mesure["monte"] is True, (
        "`E5-4` n'est pas monte pendant que le coeur travaille : l'operateur"
        " passe de la confirmation au succes sans rien voir")
    assert mesure["images"] >= 1, (
        "aucune image n'a atteint le pilote pendant la passe : l'ecran est"
        " empile mais jamais PEINT -- c'est la mesure d'Egan, mot pour mot")
    assert mesure["faites"] == 1, (
        "la barre ne porte pas le premier jalon pendant la passe"
        f" (lu : {mesure['faites']}). Zero dirait que le jalon n'arrive pas ;"
        " trois dirait qu'on ne regarde qu'apres la fin.")
    # Et la passe aboutit quand meme : une mesure qui casserait le chemin
    # nominal ne mesurerait plus le produit.
    assert mesure["ecran_final"] != mesure["ecran"]


def test_le_jalon_de_E5_4_arrive_SUR_LA_BOUCLE_et_jamais_depuis_le_FIL(
        tmp_path, banc):
    """Le volet A, mesure a l'execution plutot que lu dans un arbre AST.

    La frontiere du volet A lit des noms d'appels ; elle serait verte si
    `reporter_sur_la_boucle` cessait de reporter quoi que ce soit. Ce test-ci
    regarde le **fil reel** sur lequel `rafraichir` tourne, et il porte le
    chiffre qui a trouve le defaut : avant la reparation, 3 rafraichissements
    sur 7 tombaient hors de la boucle, un par jalon.
    """
    dossier = cablage._projet(tmp_path)
    coeur = cablage.CoeurDouble(pages={cablage.LOT_SANS_TIRAGE: 3})
    app = cablage._app()
    vus: list[int] = []
    vrai = execution_pdf.EcranGenerationDesPlanches.rafraichir

    def espion(self):
        vus.append(threading.get_ident())
        return vrai(self)

    execution_pdf.EcranGenerationDesPlanches.rafraichir = espion
    try:
        async def scenario(pilote):
            parcours = monter_jusqu_a_la_confirmation(pilote, dossier, coeur)
            await pilote.pause()
            cablage._cocher_et_regler(parcours, pilote.app.screen,
                                      lots=[cablage.LOT_SANS_TIRAGE])
            await pilote.pause()
            pilote.app.screen.choix.viser(confirmation.ISSUE_GENERER)
            vus.clear()
            parcours.generer()
            await attendre(
                pilote,
                lambda: ("pdf", cablage.LOT_SANS_TIRAGE) in coeur.trace,
                "la passe ne se termine pas")
            for _ in range(5):
                await pilote.pause()
            return pilote.app._thread_id

        boucle = cablage._jouer(scenario, app, banc)
    finally:
        execution_pdf.EcranGenerationDesPlanches.rafraichir = vrai

    hors = [fil for fil in vus if fil != boucle]
    assert vus, (
        "aucun rafraichissement observe : l'espion ne mesure rien, donc le"
        " zero ci-dessous ne prouverait rien")
    assert hors == [], (
        f"{len(hors)} rafraichissements sur {len(vus)} tournent hors de la"
        " boucle `textual`. Chacun mute l'arbre de widgets depuis le fil de"
        " travail : `textual` ne signale rien, l'ecran se met a jour la"
        " plupart du temps, et ce qui casse casse au hasard.")


# -- `E5-6c` : le rotor tourne. La seule motion de cet ecran ---------------


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E5_6c_est_PEINT_et_son_ROTOR_TOURNE_pendant_que_le_coeur_travaille(
        tmp_path, banc, ascii_seul):
    """Le chemin qui avait le plus a gagner, et le seul dont le gel est muet.

    `E5-6c` n'a **aucune barre**, et c'est une mesure : le canal du coeur emet
    un jalon par page, une mire fait une page. Ce qui reste est « un rotor, la
    ligne du fichier, et une ligne d'etat qui ne dit que ce qui est su » -- et
    un rotor qui ne tourne pas est exactement le symptome d'Egan, sur le seul
    ecran ou aucune barre ne viendrait le trahir.

    Quatre mesures, prises pendant que le coeur est retenu dans son fil :

    * le minuteur du rotor **existe** -- il est pose par `on_mount`, donc son
      existence prouve que la boucle a distribue `Mount` avant que le coeur
      parte. Avant la reparation, `on_mount` ne tournait jamais ;
    * `pas` **augmente** : le minuteur bat pendant que le coeur travaille ;
    * le **glyphe dessine** change, dans le mode demande. C'est ce que
      l'operateur voit, et `pas` seul ne le dirait pas ;
    * des images atteignent le pilote.

    `ascii_seul` varie dans les deux sens parce que `jetons.rotor` en depend :
    un banc qui ne jouerait que le mode UTF-8 mesurerait la moitie du produit
    et l'annoncerait verte.
    """
    dossier = cablage._projet(tmp_path)
    mire = MireQuiSArrete()
    app = cablage._app(ascii_seul=ascii_seul)
    mesure: dict = {}

    async def scenario(pilote):
        parcours = cablage._parcours(pilote.app, dossier, mire=mire)
        parcours.charger()
        parcours.formulaire = calibration.FormulaireDeLaMire(chaine="hp-envy")
        boite = compteur_d_images(pilote.app)
        try:
            parcours.generer_la_mire()
            await attendre(pilote, mire.arrive.is_set,
                           "le coeur de la mire n'a pas demarre")
            ecran = pilote.app.screen
            mesure["ecran"] = type(ecran).__name__
            mesure["monte"] = ecran.is_mounted
            mesure["minuteur"] = ecran.minuteur is not None
            depart = ecran.pas
            glyphe_de_depart = ecran.glyphe_du_rotor(ascii_seul)
            await attendre(pilote, lambda: ecran.pas > depart,
                           "le rotor de `E5-6c` ne tourne pas")
            # Un pas de plus ne suffit pas : `jetons.rotor` fait un modulo, et
            # un rotor a un seul dessin tournerait sans que rien ne bouge.
            await attendre(
                pilote,
                lambda: ecran.glyphe_du_rotor(ascii_seul) != glyphe_de_depart,
                "le rotor avance mais son DESSIN ne change pas")
            mesure["pas"] = ecran.pas - depart
            mesure["glyphes"] = (glyphe_de_depart,
                                 ecran.glyphe_du_rotor(ascii_seul))
            mesure["images"] = boite["images"]
        finally:
            mire.reprendre.set()
        await attendre(pilote, lambda: bool(mire.appels),
                       "la mire ne s'ecrit pas")
        for _ in range(5):
            await pilote.pause()
        mesure["ecran_final"] = type(pilote.app.screen).__name__

    cablage._jouer(scenario, app, banc)

    assert mesure["ecran"] == calibration.EcranMireEnCours.__name__
    assert mesure["monte"] is True
    assert mesure["minuteur"] is True, (
        "le minuteur du rotor n'est pas pose : `on_mount` n'a pas tourne, donc"
        " la boucle n'a pas distribue `Mount` avant que le coeur parte")
    assert mesure["pas"] >= 1
    assert mesure["glyphes"][0] != mesure["glyphes"][1]
    assert mesure["images"] >= 1, (
        "aucune image pendant la generation de la mire : le rotor tourne dans"
        " le modele et rien n'atteint le terminal")
    assert mesure["ecran_final"] == calibration.EcranMireEcrite.__name__


def test_les_deux_MODES_du_rotor_donnent_des_dessins_DIFFERENTS():
    """L'oracle du parametrage ci-dessus, sans lequel il serait decoratif.

    Si `jetons.rotor` rendait le meme dessin dans les deux modes, les deux
    tours du test precedent mesureraient la meme chose et le drapeau ne ferait
    varier que le nom du cas.
    """
    utf8 = [jetons.rotor(pas, False) for pas in range(4)]
    ascii_ = [jetons.rotor(pas, True) for pas in range(4)]
    assert utf8 != ascii_, (utf8, ascii_)
    assert len(set(utf8)) > 1 and len(set(ascii_)) > 1


# -- Les temoins symetriques : la mesure SAIT voir le gel --------------------


def gel(monkeypatch, app):
    """Rendre au produit sa forme d'AVANT la reparation, sur le parcours reel.

    Trois gestes, et il faut les trois -- c'est le rapport du 2026-09-06 qui le
    dit pour les deux premiers : le rendez-vous de dessin fait apparaitre
    l'ecran **une fois**, le fil est ce qui le garde vivant **pendant**.

    * `_lancer_apres_le_dessin` appelle sa suite immediatement, sans rendre la
      main a la boucle ;
    * `run_worker` execute son appelable en ligne, sur la boucle ;
    * `call_from_thread` appelle directement.

    **Le troisieme n'est pas une commodite de banc, et l'oublier faisait lever
    le temoin.** `textual` refuse `call_from_thread` depuis le fil de la
    boucle, et c'est justement ou l'on se retrouve quand on inline l'ouvrier.
    Le retirer n'affaiblit donc pas le temoin : il le rend fidele. Avant le
    2026-09-06 le produit n'appelait `call_from_thread` **nulle part** sur ces
    deux chemins -- la passe et sa conclusion tournaient sur la boucle, de bout
    en bout. Les trois gestes ensemble reconstituent ce code-la, ni plus ni
    moins.

    **Ce temoin est ce qui donne un sens aux verts ci-dessus.** Sans lui, « des
    images ont ete ecrites » pourrait n'etre qu'un compteur qui compte
    n'importe quoi, et « le rotor tourne » un rotor qui tournait deja. Il est
    le symetrique que ce depot exige d'une mesure de terrain : celui qui prouve
    que le defaut est reproductible.
    """
    monkeypatch.setattr(parcours_pdf, "_lancer_apres_le_dessin",
                        lambda _app, suite: suite())
    monkeypatch.setattr(type(app), "run_worker",
                        lambda self, appel, **kw: appel())
    monkeypatch.setattr(type(app), "call_from_thread",
                        lambda self, appel, *a, **k: appel(*a, **k))


class CoeurOccupe(cablage.CoeurDouble):
    """Un coeur qui OCCUPE la boucle, comme un vrai calcul.

    Attente active et non `sleep` : la difference est de forme et non de
    resultat -- les deux occupent le fil de la boucle --, mais c'est ce que
    fait un appel au coeur, et le temoin doit ressembler au produit.
    """

    def __call__(self, dossier_projet, **reste):
        debut = time.monotonic()
        while time.monotonic() - debut < DUREE_DU_GEL:
            pass
        return super().__call__(dossier_projet, **reste)


def test_TEMOIN_sans_le_fil_ni_le_rendez_vous_E5_4_n_est_JAMAIS_peint(
        tmp_path, banc, monkeypatch):
    """Le gel d'Egan, reproduit sur le parcours reel de `E5-4`.

    Zero image du montage a la fin de la passe, et l'ecran meme pas monte : le
    symptome au mot pres. C'est ce que la mesure du test nominal doit savoir
    distinguer, et ce test-ci est la seule preuve qu'elle le sait.
    """
    dossier = cablage._projet(tmp_path)
    coeur = CoeurOccupe(pages={cablage.LOT_SANS_TIRAGE: 3})
    app = cablage._app()
    gel(monkeypatch, app)
    mesure: dict = {}

    async def scenario(pilote):
        parcours = monter_jusqu_a_la_confirmation(pilote, dossier, coeur)
        await pilote.pause()
        cablage._cocher_et_regler(parcours, pilote.app.screen,
                                  lots=[cablage.LOT_SANS_TIRAGE])
        await pilote.pause()
        pilote.app.screen.choix.viser(confirmation.ISSUE_GENERER)
        boite = compteur_d_images(pilote.app)
        ecran = parcours.generer()
        # Lu SANS avoir rendu la main : c'est l'etat que l'operateur subit.
        mesure["images_pendant"] = boite["images"]
        mesure["monte_pendant"] = ecran.is_mounted
        await pilote.pause()
        mesure["images_apres"] = boite["images"]

    cablage._jouer(scenario, app, banc)

    assert mesure["images_pendant"] == 0, (
        "des images ont ete ecrites alors que la boucle etait prise par un"
        " appel synchrone : le temoin ne reproduit plus le gel, donc les tests"
        " nominaux ne prouvent plus rien -- le verifier avant de conclure")
    assert mesure["monte_pendant"] is False
    assert mesure["images_apres"] >= 1, (
        "aucune image meme APRES avoir rendu la main : le compteur ne compte"
        " rien, donc le zero ci-dessus ne prouvait rien")


def test_TEMOIN_sans_le_fil_ni_le_rendez_vous_le_ROTOR_de_E5_6c_est_FIGE(
        tmp_path, banc, monkeypatch):
    """Le meme temoin sur la mire, ou le gel est le plus silencieux.

    Le minuteur du rotor est pose par `on_mount`, et `on_mount` est distribue
    par la boucle : une boucle prise par la generation ne le pose donc jamais.
    Le rotor reste a son premier dessin -- et comme cet ecran n'a pas de barre,
    rien d'autre ne trahit l'attente.
    """
    dossier = cablage._projet(tmp_path)
    app = cablage._app()
    gel(monkeypatch, app)
    mesure: dict = {}

    class MireOccupee:
        def __init__(self) -> None:
            self.appels: list[dict] = []

        def __call__(self, dossier_projet, **reglages):
            debut = time.monotonic()
            while time.monotonic() - debut < DUREE_DU_GEL:
                pass
            self.appels.append(dict(dossier=Path(dossier_projet)))
            return cablage._Issue(
                plan=cablage._Plan(1, "tpl-a4-paysage-6f-v2", ()),
                output_path=Path(dossier_projet) / project_layout.PLANCHES_DIRNAME / "mire.pdf")

    async def scenario(pilote):
        parcours = cablage._parcours(pilote.app, dossier, mire=MireOccupee())
        parcours.charger()
        parcours.formulaire = calibration.FormulaireDeLaMire(chaine="hp-envy")
        boite = compteur_d_images(pilote.app)
        ecran = parcours.generer_la_mire()
        mesure["images_pendant"] = boite["images"]
        mesure["minuteur"] = ecran.minuteur is not None
        mesure["pas"] = ecran.pas
        mesure["monte_pendant"] = ecran.is_mounted

    cablage._jouer(scenario, app, banc)

    assert mesure["images_pendant"] == 0
    assert mesure["monte_pendant"] is False
    assert mesure["minuteur"] is False, (
        "le minuteur est pose alors que la boucle etait prise : `on_mount`"
        " aurait donc tourne pendant un appel synchrone, ce sur quoi tout ce"
        " banc repose -- le verifier avant de conclure")
    assert mesure["pas"] == 0


# ===========================================================================
# Volet C -- L'EXTRACTION (`E2-4`) et L'ENCODAGE (`E4-4`), montes pour de vrai
#
# **Pourquoi ce volet existe, et il a ete paye deux fois le meme jour.** Tout
# ce qui precede ne couvre que le perimetre PDF. Le 2026-09-06, avec ce banc
# vert et le registre de `test_frontiere_du_dessin_avant_le_coeur.py` a zero,
# Egan a fait passer la TUI sur le terrain :
#
#   Extract -- « La barre de progression saute de 0 a 100. Pas eu l'impression
#              de voir les frames progresser. Je ne suis pas sur que le coeur
#              sache le faire ? »
#   Encode  -- « Le glyphe d'attente (lecture des frames) [...] Sur le terminal
#              VS Code il est immobile. »
#
# **Le coeur sait, et tres finement** : `ffmpeg_utils` scrute le repertoire
# temporaire toutes les 0,25 s et emet un jalon a chaque passage -- des
# centaines sur 6 300 frames. Ce qui manquait n'etait ni le coeur ni le canal,
# c'etait le FIL : les deux chemins prenaient un rendez-vous de dessin puis
# gardaient la boucle du premier au dernier jalon. Le rotor de `E4-4` etant un
# `set_interval`, il ne battait pas -- ce n'etait donc pas une affaire de
# police de caracteres, contrairement a ce que « sur VS Code » laissait croire.
#
# Ces tests sont batis sur le modele EXACT des deux tests PDF ci-dessus, et
# leurs temoins symetriques avec eux : sans le temoin, « la barre porte 62 »
# pourrait n'etre qu'un compteur qui compte n'importe quoi.
# ===========================================================================

import test_atelier_exports_parcours as cablage_exports      # noqa: E402
import test_parcours_extraction as cablage_extraction        # noqa: E402
from mixed_media_utility import progression, video_metadata   # noqa: E402
from mixed_media_utility.tui import (                         # noqa: E402
    atelier_exports_confirmation as confirmation_exports,
    atelier_exports_execution as execution_exports,
    atelier_exports_parcours as parcours_exports,
    atelier_extraction_ecriture as atelier_extraction,
)
from mixed_media_utility.tui.execution import EcranExecution  # noqa: E402


# -- Volet A bis, etendu aux DEUX lanceurs neufs -----------------------------

#: `module -> fonction` pour les deux chemins repares le 2026-09-06, avec le
#: nom de leur ouvrier. Nommes plutot que decouverts, meme motif que
#: `LANCEURS_PDF` : un balayage qui les chercherait tout seul pourrait n'en
#: trouver aucun et rester vert.
#:
#: **La fonction nommee n'est pas toujours celle qui monte l'ecran.** Cote
#: extraction, `ParcoursExtraction._ecrire` monte `E2-4` puis delegue a
#: `lancer_l_extraction`, qui porte les deux gestes -- meme forme que
#: `atelier_scan_detection.lancer_la_detection`. C'est donc cette fonction-la
#: qu'on lit, et la frontiere du registre rattache le verdict a `_ecrire` par
#: sa fermeture transitive.
LANCEURS_AU_FIL = {
    ("atelier_extraction_ecriture.py", "lancer_l_extraction"):
        atelier_extraction.OUVRIER_DE_L_EXTRACTION,
    ("atelier_exports_parcours.py", "encoder"):
        parcours_exports.OUVRIER_DE_L_ENCODAGE,
}


@pytest.mark.parametrize(("module", "lanceur"), sorted(LANCEURS_AU_FIL))
def test_les_lanceurs_EXTRACTION_et_ENCODE_partent_au_fil_SOUS_un_rendez_vous(
        module, lanceur):
    """Les deux proprietes, sur les deux chemins neufs. Il faut **les deux**.

    Le rendez-vous fait apparaitre l'ecran UNE FOIS -- c'est ce que les deux
    chemins avaient deja, et ce qui ne suffisait pas. Le fil est ce qui le
    garde vivant PENDANT la passe. La troisieme lecture est celle qui compte :
    le fil doit etre **sous** le rendez-vous, sans quoi rien ne garantit que
    l'ecran soit peint avant que le coeur parte.
    """
    source = (PAQUET_TUI / module).read_text(encoding="utf-8")
    rendez_vous, fil, sous = fil_sous_rendez_vous(source, lanceur)
    assert rendez_vous, (
        f"`{lanceur}` ne prend plus rendez-vous : son ecran peut partir sans"
        " avoir ete peint une seule fois")
    assert fil, (
        f"`{lanceur}` n'appelle plus `{FIL}` : la boucle est reprise par le"
        " coeur, l'ecran se fige -- barre immobile, rotor arrete")
    assert sous, (
        f"`{lanceur}` porte les deux appels mais le fil n'est pas SOUS le"
        " rendez-vous : rien ne garantit que l'ecran soit peint avant que le"
        " coeur parte")


def test_les_QUATRE_ouvriers_du_depot_portent_des_noms_DISTINCTS():
    """Deux ouvriers homonymes rendraient deux mesures interchangeables.

    Les quatre noms sont lus la ou ils sont ECRITS -- deux constantes de
    module pour les chemins neufs, la table `LANCEURS_PDF` pour les deux
    anciens --, jamais recopies ici.
    """
    noms = sorted(LANCEURS_PDF.values()) + sorted(LANCEURS_AU_FIL.values())
    assert len(set(noms)) == len(noms) == 4, noms


# -- `E2-4` : la barre porte un PALIER INTERMEDIAIRE --------------------------


class ExtracteurQuiSArrete(cablage_extraction.ExtracteurCompte):
    """Le coeur de l'extraction, **arrete en plein travail** sur un jalon.

    Meme geste que :class:`CoeurQuiSArrete` cote PDF, et pour la meme raison :
    au lieu d'attendre et d'esperer avoir regarde au bon moment, on retient le
    coeur DANS son fil et on observe l'ecran a loisir.

    Le compte des jalons est **global a la passe** et non par lot : le plan de
    ce banc porte deux lots de deux jalons chacun, et s'arreter au premier
    jalon du premier lot est le seul point ou `faites` est strictement entre
    zero et le cardinal de la passe.

    Il emet par le VRAI emetteur du coeur, comme la classe dont il herite --
    un rappel non appelable y est absorbe en silence, exactement comme dans
    `ffmpeg_utils`. Un double qui appellerait le rappel a la main leverait, et
    transformerait une extinction silencieuse en erreur bruyante.
    """

    def __init__(self, dossier, *, arret_au_jalon: int = 1) -> None:
        super().__init__(dossier)
        self.arret_au_jalon = arret_au_jalon
        self.emis = 0
        #: Pose par le FIL quand il atteint son point d'arret.
        self.arrive = threading.Event()
        #: Pose par le TEST pour rendre la main au coeur.
        self.reprendre = threading.Event()

    def __call__(self, **kwargs):
        self.appels.append(kwargs)
        if self.app is not None:
            self.taches_en_cours.append(bool(self.app.tache_en_cours))
        cible = kwargs["fps_target"]
        frames = self.frames_attendues(cible)
        emetteur = progression.EmetteurProgression(
            kwargs.get("rappel_progression"), frames)
        for faites in (frames // 2, frames):
            self.jalons.append(faites)
            emetteur.emettre(faites)
            self.emis += 1
            if self.emis == self.arret_au_jalon:
                self.arrive.set()
                # La borne evite qu'un banc rouge suspende la suite entiere.
                self.reprendre.wait(timeout=PATIENCE * 2)
        return cablage_extraction.issue_reussie(
            self.dossier, cablage_extraction.build_lot_id(
                cablage_extraction.RUSH_VISE, cible),
            cible, frames)


def _chaine_d_extraction(tmp_path, monkeypatch, extracteur):
    """La chaine REELLE de l'atelier Extraction, sondage double.

    Le double de `probe_media` est pose ici plutot que par la fixture `sonde`
    du banc voisin : une fixture ne s'importe pas, et la recopier serait une
    seconde source de verite pour un fait (regle des fabriques).
    """
    monkeypatch.setattr(video_metadata, "probe_media",
                        cablage_extraction.SondeComptee())
    lien = cablage_extraction.chaine(tmp_path, extracteur=extracteur)
    # Le dossier du projet n'existe qu'une fois la chaine batie ; l'extracteur
    # en a besoin pour poser les frames de ses lots.
    extracteur.dossier = Path(lien.menu.dossier)
    return lien


async def _jusqu_a_l_ecriture(pilote, lien):
    """Le parcours au clavier jusqu'a `E2-3`, curseur sur l'issue qui ecrit.

    Passe par les ecrans, jamais par les rappels : ce qu'on mesure est ce
    qu'un operateur obtient de son clavier.
    """
    panneau = await cablage_extraction.jusqu_au_panneau(
        pilote, lien, par_la_previz=False)
    panneau.choix.viser(atelier_extraction.ISSUE_EXTRAIRE)
    return panneau


def test_E2_4_est_PEINT_et_sa_BARRE_porte_un_PALIER_INTERMEDIAIRE(
        tmp_path, banc, monkeypatch):
    """La reponse a la phrase d'Egan sur l'extraction, a l'execution.

    Deux lots, quatre jalons, le coeur retenu dans son fil apres le PREMIER.
    Pendant qu'il est retenu -- donc pendant qu'il « travaille » du point de
    vue de l'operateur -- on lit ce que l'ecran montre :

    * l'ecran du dessus est bien `E2-4`, et il est **monte** ;
    * des images ont ete ecrites au pilote : elles ne l'etaient pas avant la
      reparation, et c'est la moitie « on ne voit rien » du symptome ;
    * la barre porte un **palier INTERMEDIAIRE** -- strictement entre zero et
      le cardinal de la passe. C'est la seule assertion qui reponde a « la
      barre saute de 0 a 100 » : zero dirait que le jalon n'arrive pas, le
      total dirait qu'on ne regarde qu'apres la fin, et **les deux passeraient
      une assertion qui se contenterait de "un jalon est arrive"**. C'est
      exactement le defaut de `test_extract_command.py`, corrige le meme jour.

    **Aucune horloge ici**, et c'est ce qui rend ce test deterministe : le
    coeur est retenu par un evenement, pas par une duree, et le jalon qui fait
    avancer la barre est emis par le coeur lui-meme.
    """
    extracteur = ExtracteurQuiSArrete(tmp_path)
    lien = _chaine_d_extraction(tmp_path, monkeypatch, extracteur)
    mesure: dict = {}

    async def scenario(pilote):
        await _jusqu_a_l_ecriture(pilote, lien)
        boite = compteur_d_images(pilote.app)
        try:
            pilote.app.screen.traiter("enter")
            await attendre(pilote, extracteur.arrive.is_set,
                           "le coeur n'a pas atteint son premier jalon")
            # **ICI le coeur est BLOQUE dans son fil.** Tout ce qui suit decrit
            # donc ce que l'operateur a sous les yeux pendant l'attente.
            ecran = pilote.app.screen
            mesure["ecran"] = type(ecran).__name__
            mesure["monte"] = ecran.is_mounted
            mesure["images"] = boite["images"]
            mesure["faites"] = ecran.surface.avancement.faites
            mesure["total"] = ecran.surface.avancement.total
        finally:
            extracteur.reprendre.set()
        await attendre(pilote, lambda: len(extracteur.appels) == 2,
                       "la passe ne va pas jusqu'au second lot")
        for _ in range(5):
            await pilote.pause()
        mesure["ecran_final"] = type(pilote.app.screen).__name__

    banc(lien.app, scenario)

    assert mesure["ecran"] == EcranExecution.__name__
    assert mesure["monte"] is True, (
        "`E2-4` n'est pas monte pendant que le coeur travaille : l'operateur"
        " passe de la confirmation au succes sans rien voir")
    assert mesure["images"] >= 1, (
        "aucune image n'a atteint le pilote pendant la passe : l'ecran est"
        " empile mais jamais PEINT -- c'est la mesure d'Egan, mot pour mot")
    assert 0 < mesure["faites"] < mesure["total"], (
        "la barre ne porte pas de palier INTERMEDIAIRE pendant la passe"
        f" ({mesure['faites']}/{mesure['total']}). Zero dirait que le jalon"
        " n'arrive pas ; le total dirait qu'on ne regarde qu'apres la fin --"
        " c'est-a-dire « la barre saute de 0 a 100 ».")
    # Et la passe aboutit quand meme : une mesure qui casserait le chemin
    # nominal ne mesurerait plus le produit.
    assert mesure["ecran_final"] != mesure["ecran"]


def test_le_jalon_de_E2_4_arrive_SUR_LA_BOUCLE_et_jamais_depuis_le_FIL(
        tmp_path, banc, monkeypatch):
    """Le volet A, mesure a l'execution sur le chemin de l'extraction.

    `E2-4` est un `EcranExecution` **nu** -- il n'en derive pas, il l'EST --,
    donc il herite de la garde de fil sans surcharge possible. Ce test-ci le
    verifie a l'execution plutot que dans un arbre syntaxique : il regarde le
    fil reel sur lequel `rafraichir` tourne pendant une passe entiere.

    Sans lui, la reparation aurait pu muter l'arbre de widgets depuis le fil
    de travail sans que rien ne le signale -- `textual` ne dit rien, l'ecran
    se met a jour la plupart du temps, et ce qui casse casse au hasard.
    """
    extracteur = cablage_extraction.ExtracteurCompte(tmp_path)
    lien = _chaine_d_extraction(tmp_path, monkeypatch, extracteur)
    vus: list[int] = []
    vrai = EcranExecution.rafraichir

    def espion(self):
        vus.append(threading.get_ident())
        return vrai(self)

    monkeypatch.setattr(EcranExecution, "rafraichir", espion)

    async def scenario(pilote):
        await _jusqu_a_l_ecriture(pilote, lien)
        vus.clear()
        pilote.app.screen.traiter("enter")
        await attendre(pilote, lambda: len(extracteur.appels) == 2,
                       "la passe ne se termine pas")
        for _ in range(5):
            await pilote.pause()
        return pilote.app._thread_id

    boucle = banc(lien.app, scenario)

    hors = [fil for fil in vus if fil != boucle]
    assert vus, (
        "aucun rafraichissement observe : l'espion ne mesure rien, donc le"
        " zero ci-dessous ne prouverait rien")
    assert hors == [], (
        f"{len(hors)} rafraichissements sur {len(vus)} tournent hors de la"
        " boucle `textual`. Chacun mute l'arbre de widgets depuis le fil de"
        " travail : `textual` ne signale rien, l'ecran se met a jour la"
        " plupart du temps, et ce qui casse casse au hasard.")


def gel_de_l_extraction(monkeypatch, app):
    """Rendre au produit sa forme d'AVANT la reparation, sur le parcours reel.

    Les trois memes gestes que :func:`gel`, poses sur le module de
    l'extraction : le rendez-vous appelle sa suite immediatement, l'ouvrier
    s'execute en ligne, et `call_from_thread` appelle directement -- ce dernier
    parce que `textual` refuse cet appel depuis le fil de la boucle, qui est
    justement ou l'on se retrouve quand on inline l'ouvrier.
    """
    monkeypatch.setattr(atelier_extraction, "_lancer_apres_le_dessin",
                        lambda _app, suite: suite())
    monkeypatch.setattr(type(app), "run_worker",
                        lambda self, appel, **kw: appel())
    monkeypatch.setattr(type(app), "call_from_thread",
                        lambda self, appel, *a, **k: appel(*a, **k))


class ExtracteurOccupe(cablage_extraction.ExtracteurCompte):
    """Un extracteur qui OCCUPE la boucle, comme un vrai appel a ffmpeg.

    Attente active et non `sleep` : la difference est de forme et non de
    resultat -- les deux occupent le fil de la boucle --, mais c'est ce que
    fait un appel au coeur, et le temoin doit ressembler au produit.
    """

    def __call__(self, **kwargs):
        debut = time.monotonic()
        while time.monotonic() - debut < DUREE_DU_GEL:
            pass
        return super().__call__(**kwargs)


def test_TEMOIN_sans_le_fil_ni_le_rendez_vous_E2_4_n_est_JAMAIS_peint(
        tmp_path, banc, monkeypatch):
    """Le gel d'Egan, reproduit sur le parcours reel de `E2-4`.

    Zero image du montage a la fin de la passe, et l'ecran meme pas monte : le
    symptome au mot pres. C'est ce que la mesure du test nominal doit savoir
    distinguer, et ce test-ci est la seule preuve qu'elle le sait.
    """
    extracteur = ExtracteurOccupe(tmp_path)
    lien = _chaine_d_extraction(tmp_path, monkeypatch, extracteur)
    gel_de_l_extraction(monkeypatch, lien.app)
    mesure: dict = {}

    async def scenario(pilote):
        await _jusqu_a_l_ecriture(pilote, lien)
        boite = compteur_d_images(pilote.app)
        pilote.app.screen.traiter("enter")
        # Lu SANS avoir rendu la main : c'est l'etat que l'operateur subit.
        mesure["images_pendant"] = boite["images"]
        mesure["ecrans"] = [type(e).__name__ for e in pilote.app.screen_stack]
        await pilote.pause()
        mesure["images_apres"] = boite["images"]

    banc(lien.app, scenario)

    assert mesure["images_pendant"] == 0, (
        "des images ont ete ecrites alors que la boucle etait prise par un"
        " appel synchrone : le temoin ne reproduit plus le gel, donc les tests"
        " nominaux ne prouvent plus rien -- le verifier avant de conclure")
    assert mesure["images_apres"] >= 1, (
        "aucune image meme APRES avoir rendu la main : le compteur ne compte"
        " rien, donc le zero ci-dessus ne prouvait rien")


# -- `E4-4` : le rotor tourne. La seule motion de cet ecran ------------------


class CoeurDEncodageQuiSArrete(cablage_exports.CoeurDouble):
    """Le coeur de l'encodage, retenu dans son fil. Meme geste, autre entree."""

    def __init__(self) -> None:
        super().__init__()
        self.arrive = threading.Event()
        self.reprendre = threading.Event()

    def __call__(self, dossier_projet, **reste):
        self.arrive.set()
        self.reprendre.wait(timeout=PATIENCE * 2)
        return super().__call__(dossier_projet, **reste)


async def _jusqu_a_la_confirmation_d_encodage(pilote, dossier, coeur):
    """Le parcours au clavier jusqu'a `E4-3`, curseur sur `Encoder`."""
    parcours = cablage_exports._parcours(pilote.app, dossier, coeur=coeur)
    await cablage_exports._jusqu_aux_reglages(
        pilote, parcours, cablage_exports.LOT_CIBLE)
    ecran = await cablage_exports._valider_les_reglages(pilote)
    cablage_exports._viser(ecran.choix, confirmation_exports.ISSUE_ENCODER)
    return ecran


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_E4_4_est_PEINT_et_son_ROTOR_TOURNE_pendant_que_le_coeur_travaille(
        tmp_path, banc, ascii_seul):
    """Le retour d'Egan sur l'encodage, et le gel le plus silencieux du lot.

    « Le glyphe d'attente (lecture des frames) [...] Sur le terminal VS Code il
    est **immobile**. » Ce n'est pas une affaire de police : le rotor de `E4-4`
    est un `set_interval`, et un minuteur `textual` ne bat que si la boucle
    d'evenements tourne. `E4-4` n'a **aucune barre** -- le coeur d'`encode`
    n'emet aucun jalon aujourd'hui (`EPIC11-ARB-184`) --, donc le rotor est la
    seule chose qui bouge, et rien d'autre ne trahit l'attente.

    Quatre mesures, prises pendant que le coeur est retenu dans son fil :

    * le minuteur **existe** -- il est pose par `on_mount`, donc son existence
      prouve que la boucle a distribue `Mount` avant que le coeur parte ;
    * `pas` **augmente** : le minuteur bat pendant que le coeur travaille ;
    * le **glyphe dessine** change, dans le mode demande. C'est ce que
      l'operateur voit, et `pas` seul ne le dirait pas -- un rotor a un seul
      dessin tournerait sans que rien ne bouge ;
    * des images atteignent le pilote.

    `ascii_seul` varie dans les deux sens parce que `jetons.rotor` en depend :
    un banc qui ne jouerait que le mode UTF-8 mesurerait la moitie du produit
    et l'annoncerait verte (regle des drapeaux, `CLAUDE.md`).
    """
    dossier = cablage_exports.projet(tmp_path)
    coeur = CoeurDEncodageQuiSArrete()
    app = cablage_exports._app(ascii_seul=ascii_seul)
    mesure: dict = {}

    async def scenario(pilote):
        ecran_de_confirmation = await _jusqu_a_la_confirmation_d_encodage(
            pilote, dossier, coeur)
        boite = compteur_d_images(pilote.app)
        try:
            ecran_de_confirmation.traiter("enter")
            await attendre(pilote, coeur.arrive.is_set,
                           "le coeur de l'encodage n'a pas demarre")
            ecran = pilote.app.screen
            mesure["ecran"] = type(ecran).__name__
            mesure["monte"] = ecran.is_mounted
            mesure["minuteur"] = ecran.minuteur is not None
            depart = ecran.passage.pas
            glyphe_de_depart = ecran.passage.glyphe_du_rotor(ascii_seul)
            await attendre(pilote, lambda: ecran.passage.pas > depart,
                           "le rotor de `E4-4` ne tourne pas")
            await attendre(
                pilote,
                lambda: (ecran.passage.glyphe_du_rotor(ascii_seul)
                         != glyphe_de_depart),
                "le rotor avance mais son DESSIN ne change pas")
            mesure["pas"] = ecran.passage.pas - depart
            mesure["glyphes"] = (glyphe_de_depart,
                                 ecran.passage.glyphe_du_rotor(ascii_seul))
            mesure["images"] = boite["images"]
        finally:
            coeur.reprendre.set()
        await attendre(pilote, lambda: bool(coeur.appels),
                       "le master ne s'ecrit pas")
        for _ in range(5):
            await pilote.pause()
        mesure["ecran_final"] = type(pilote.app.screen).__name__

    banc(app, scenario)

    assert mesure["ecran"] == execution_exports.EcranEncodageEnCours.__name__
    assert mesure["monte"] is True
    assert mesure["minuteur"] is True, (
        "le minuteur du rotor n'est pas pose : `on_mount` n'a pas tourne, donc"
        " la boucle n'a pas distribue `Mount` avant que le coeur parte")
    assert mesure["pas"] >= 1
    assert mesure["glyphes"][0] != mesure["glyphes"][1]
    assert mesure["images"] >= 1, (
        "aucune image pendant l'encodage : le rotor tourne dans le modele et"
        " rien n'atteint le terminal")
    assert mesure["ecran_final"] != mesure["ecran"]


def test_TEMOIN_sans_le_fil_ni_le_rendez_vous_le_ROTOR_de_E4_4_est_FIGE(
        tmp_path, banc, monkeypatch):
    """Le meme temoin sur l'encodage, la ou le gel ne laisse aucune trace.

    Le minuteur du rotor est pose par `on_mount`, et `on_mount` est distribue
    par la boucle : une boucle prise par l'encodage ne le pose donc jamais. Le
    rotor reste a son premier dessin -- et comme cet ecran n'a pas de barre,
    rien d'autre ne trahit l'attente. C'est litteralement le « glyphe immobile »
    d'Egan, reproduit.
    """
    dossier = cablage_exports.projet(tmp_path)
    app = cablage_exports._app()
    mesure: dict = {}

    class CoeurOccupeALEncodage(cablage_exports.CoeurDouble):
        def __call__(self, dossier_projet, **reste):
            debut = time.monotonic()
            while time.monotonic() - debut < DUREE_DU_GEL:
                pass
            return super().__call__(dossier_projet, **reste)

    coeur = CoeurOccupeALEncodage()

    async def scenario(pilote):
        ecran_de_confirmation = await _jusqu_a_la_confirmation_d_encodage(
            pilote, dossier, coeur)
        # Le gel n'est pose qu'ICI : monter le parcours a besoin de la vraie
        # boucle, et un `run_worker` inline des le depart la priverait des
        # rendez-vous de dessin des ecrans amont.
        monkeypatch.setattr(parcours_exports, "_lancer_apres_le_dessin",
                            lambda _app, suite: suite())
        monkeypatch.setattr(type(pilote.app), "run_worker",
                            lambda self, appel, **kw: appel())
        monkeypatch.setattr(type(pilote.app), "call_from_thread",
                            lambda self, appel, *a, **k: appel(*a, **k))
        boite = compteur_d_images(pilote.app)
        ecran_de_confirmation.traiter("enter")
        # Lu SANS avoir rendu la main : c'est l'etat que l'operateur subit.
        mesure["images_pendant"] = boite["images"]
        mesure["ecran_de_la_passe"] = getattr(
            pilote.app, execution_exports.ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None)
        await pilote.pause()
        mesure["images_apres"] = boite["images"]

    banc(app, scenario)

    ecran = mesure["ecran_de_la_passe"]
    assert ecran is not None, (
        "l'ecran de la passe n'a jamais ete construit : le temoin ne mesure"
        " plus le chemin qu'il croit mesurer")
    assert mesure["images_pendant"] == 0, (
        "des images ont ete ecrites alors que la boucle etait prise par un"
        " appel synchrone : le temoin ne reproduit plus le gel, donc les tests"
        " nominaux ne prouvent plus rien -- le verifier avant de conclure")
    assert ecran.minuteur is None, (
        "le minuteur est pose alors que la boucle etait prise : `on_mount`"
        " aurait donc tourne pendant un appel synchrone, ce sur quoi tout ce"
        " banc repose -- le verifier avant de conclure")
    assert ecran.passage.pas == 0, (
        f"le rotor a avance de {ecran.passage.pas} pas pendant un appel"
        " synchrone : le temoin ne reproduit plus le gel")
    assert mesure["images_apres"] >= 1, (
        "aucune image meme APRES avoir rendu la main : le compteur ne compte"
        " rien, donc le zero ci-dessus ne prouvait rien")
