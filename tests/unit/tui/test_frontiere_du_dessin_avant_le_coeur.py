"""Frontiere : un ecran de progression est DESSINE avant que le coeur travaille.

**Ce que ce banc ferme, et pourquoi il existe.** Le 2026-09-06, Egan a
constate en utilisant le produit : « tous les ecrans de progression ne montent
pas. On passe de la confirmation au succes sans voir la progression.
L'interface se fige et toutes les touches tapees pendant l'attente se
resolvent a la sortie. » La mesure lui donne raison, et le mecanisme est
connu du depot depuis le 2026-09-05 (`deferred-work.md`, entree
`EcranSuppressionEnCours`) : `textual` peint depuis sa boucle d'evenements, et
une passe synchrone occupe cette boucle du premier au dernier jalon.

Ce qui manquait n'est pas le diagnostic, c'est la MESURE. Aucun banc du depot
ne dit qu'un ecran de progression est dessine avant que le coeur ne travaille :
les bancs montent l'ecran **seul** et lisent ce qu'il rend, ce qui ne mesure
jamais l'ORDRE. D'ou cette frontiere, et non quatre corrections :

    une fonction qui monte un ecran de progression puis appelle le coeur
    passe par un rendez-vous de dessin, ou par un fil de travail.

**Les deux chiffres qui fondent tout, mesures a l'application reelle.** Sur
`atelier_pdf_execution`, c'est-a-dire un chemin qui monte pourtant
correctement son ecran, en comptant les ecritures au pilote `textual` :

    images ecrites depuis descendre : 0        boucle bloquee   : 1,01 s
    on_mount a tourne               : False    images apres     : 1

Cette mesure n'est pas un souvenir : le volet 5a la REJOUE a chaque course, et
il rougit si `textual` cesse un jour de se comporter ainsi.

Zero image du montage a la fin de la passe. Et les touches frappees pendant :

    touches traitees PENDANT la passe : []
    'tab'    recue par le palier SUIVANT a t+1,02 s
    'escape' recue par le palier SUIVANT a t+1,03 s

Elles ne sont pas perdues -- elles sont delivrees a un AUTRE ecran que celui
qui etait affiche quand l'operateur a frappe. Une touche a le sens de l'ecran
ou elle atterrit : c'est une action non voulue, pas un silence.

**Le releve du jour, huit lanceurs et six monteurs.** SIX lanceurs passent
(trois par un rendez-vous, trois par un fil), deux non -- ce sont les deux
lignes du registre.

**Le registre a DECRU pour la premiere fois le 2026-09-06**, et c'est ce a quoi
il sert. Les deux chemins Scan -- `detecter` et `trancher_le_conflit` -- sont
partis au fil de travail le jour meme, sur arbitrage d'Egan (« mon choix est
que tu peux corriger ») et apres que l'agent principal de l'EPIC 11 a degage
le chemin. Ils ont ete repares EN PREMIER pour une raison mesuree : leur ecran
d'arrivee porte l'issue qui ecrit, et deux frappes en file suffisent a
l'atteindre (`up` puis `entree`). Les deux chemins PDF qui restent arrivent
sur des ecrans sans aucune issue ecrivante.

**Et la frontiere a refuse la reparation d'abord, ce qui est le bon
comportement.** Le detecteur reconnaissait un fil par le NOM appele : la
fonction `lancer_la_detection`, ecrite pour reparer, lui etait invisible --
exactement comme `ouvrir_la_calibration_en_cours` l'avait ete. Un niveau
d'indirection se CALCULE desormais (`porteurs_directs`) plutot que de
s'ajouter a une liste : demander a un banc de connaitre par coeur le code
qu'il mesure est ce qui rend un registre faux en silence.

**LA GARDE A ETE DURCIE LE SOIR DU 2026-09-06, et c'est le fait le plus
important de cette tete.** Le registre etait tombe a zero le matin sous la
regle « rendez-vous OU fil ». Egan a fait passer la TUI sur le terrain
l'apres-midi : « la barre de progression saute de 0 a 100. Pas eu
l'impression de voir les frames progresser » (extraction), « le glyphe
d'attente [...] sur le terminal VS Code il est **immobile** » (encodage).
Trois chemins gelaient donc encore devant un banc vert -- l'extraction,
l'encodage, l'ecriture du scan --, et tous trois passaient parce qu'ils
portaient un rendez-vous de dessin. La regle ne demande plus que le fil
(`ACQUITTENT`), le registre porte de nouveau une ligne -- le chemin Scan,
repare en parallele --, et les deux autres sont partis au fil.

Ce que ce durcissement dit de la premiere redaction : elle **savait**. Son
propre paragraphe ci-dessous ecrit que « un chemin qui a le premier sans le
second montre un ecran fige : le rotor ne tourne pas, la barre ne bouge pas ».
La mesure a ete ecrite plus laxiste que la doctrine qu'elle enonce, et c'est
la doctrine qui avait raison -- mot pour mot, deux mois d'usage plus tard, sur
les deux symptomes qu'elle nommait.

**Deux proprietes distinctes, et il faut les deux.** Le rendez-vous de dessin
(`call_after_refresh`, via `_lancer_apres_le_dessin`) fait apparaitre l'ecran
**une fois** ; le fil (`run_worker`) est ce qui le garde vivant **pendant** la
passe. Un chemin qui a le premier sans le second montre un ecran fige : le
rotor ne tourne pas, la barre ne bouge pas. Le paquet portait **un seul**
`run_worker` -- `atelier_scan_parcours`, la passe `scan-calibrate` --, qui a
donc servi de patron ; il en porte **deux** depuis la reparation des chemins
Scan.

**Ce banc ne corrige rien**, et c'est delibere : le geste traverse
`execution.py` et les trois parcours, dont le seul chemin du depot qui detruit
des fichiers. Il MESURE, il epingle l'etat du jour, et il rougit des qu'un
chemin de plus regresse. Le registre a vocation a decroitre jusqu'a zero --
meme forme que `test_frontiere_des_maquettes_recopiees.py`, et pour le meme
motif : ce qui se mesure se tient, ce qui se rappelle se perd.

**Ce que ce banc NE mesure pas, dit plutot que tu.**

* il ne mesure pas qu'un rendez-vous SUFFISE. Il ne mesure que sa presence ;
  un chemin qui rend la main une fois puis bloque une minute passe le volet 1
  et gele quand meme. C'est pourquoi le fil est nomme a part ;
* il ne voit pas un chemin qui ne monte AUCUN ecran de progression -- il n'y
  a alors rien a dessiner trop tard. C'est exactement le cas de
  `suite_de_la_suppression`, et c'est le **volet 5b** qui l'attrape, par
  l'autre bout : tout ecran de progression ecrit doit etre monte par un chemin
  de production. Il en trouve **un**, `EcranSuppressionEnCours` -- ecrit,
  complet, construit nulle part ;
* le detecteur du volet 1 lit la STRUCTURE du code, pas son execution ; seul,
  il mesurerait sa propre syntaxe. Le **volet 5a** l'ancre sur l'application
  reelle -- vraie `CoqueTui`, vrai `_lancer_apres_le_dessin` -- en comptant
  les images ecrites au pilote `textual` ;
* il ne mesure pas le PRODUIT sur ses chemins reels. Le volet 5a rejoue le
  mecanisme sur une passe de synthese : il etablit que `textual` se comporte
  bien comme la frontiere le suppose, pas que `generer` gele aujourd'hui --
  ca, c'est le volet 1 qui le lit, et c'est une lecture.

**Campagne de mutation : 33 mutants, 32 morts, 1 survivant EQUIVALENT mesure.**
Trois vagues, et ce que les deux premieres ont trouve n'aurait ete vu par
aucune relecture :

* premiere vague, 21/29 -- huit survivants. Cinq etaient de vrais trous :
  l'ancre prise au DERNIER montage au lieu du premier (un chemin qui monte,
  appelle le coeur, puis empile son compte rendu passait pour un monteur) ;
  la borne de position elargie ; les gestes de pile comptes comme du travail ;
  le rendez-vous teste avant le fil (un chemin qui a les deux etait annonce au
  rendez-vous, et le compte exact des fils ne voyait plus son patron) ; et une
  troncature de la QUEUE du balayage des CONSTRUCTIONS, invisible parce que le
  corpus de synthese n'en portait aucune en queue ;
* un survivant etait EQUIVALENT et il a ete traite comme tel : la garde
  `role == "lanceur"` de `mesure_de_l_arbre` est indistinguable de son absence,
  un monteur portant le verdict `-` et jamais `AUCUN`. Elle est **retiree**
  plutot que toleree -- meme geste que le depot demande ailleurs pour une
  garde qui se relit comme une protection qu'on n'a pas ;
* le corpus des orphelins est passe de cinq a **six** modules pour cette
  seule raison : ce volet a DEUX balayages -- definitions et constructions --,
  donc quatre bords, et chacun porte desormais une cible.

**Seconde campagne, sur la fermeture transitive : 9 mutants, 9 morts.** Elle
porte sur ce que le detecteur a gagne le 2026-09-06 -- les deux bords du
balayage des porteurs, la fermeture qui ne rendrait rien, celle qui rendrait
tout, les deux marqueurs CROISES (le fil pris pour un rendez-vous et
l'inverse), et l'ordre des verdicts. Zero survivant.

**Le survivant qui reste est nomme plutot que tu** : remplacer la boucle
occupee de `_passe_synchrone` par `time.sleep` laisse les trois tests du
volet 5a verts. C'est attendu -- un `sleep` synchrone occupe le fil de la
boucle exactement comme un calcul --, et c'est donc une equivalence, pas un
trou.
"""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
TUI = RACINE / "src" / "mixed_media_utility" / "tui"

#: Les ecrans de progression du produit. Ecrits ici plutot que devines : un
#: ecran neuf qui n'y figure pas echappe a la frontiere, et c'est le volet 5
#: qui le dirait en trouvant une classe montee par rien.
ECRANS_DE_PROGRESSION = frozenset({
    "EcranEncodageEnCours", "EcranMireEnCours", "EcranGenerationDesPlanches",
    "EcranDetectionEnCours", "EcranEcritureDuScan", "EcranSuppressionEnCours",
    "EcranExecution",
    # `atelier_scan_calibrate` ne nomme pas sa classe au site de montage : il
    # la fabrique (`_classe_de_l_ecran_de_passe()(...)`, une sous-classe
    # d'`EcranExecution` construite une seule fois). Le NOM sous lequel
    # l'ecran est construit la est donc celui de la fabrique, et c'est lui
    # qu'un detecteur syntaxique voit. L'omettre rendait `atelier_scan_calibrate`
    # invisible au releve -- avec lui, le seul chemin du paquet qui part au
    # fil de travail.
    "_classe_de_l_ecran_de_passe",
})

#: Les fonctions qui montent un de ces ecrans pour le compte d'un appelant.
#:
#: **`ouvrir_la_calibration_en_cours` a manque a la premiere redaction**, et
#: son absence est ce qui a fait rougir `test_les_chemins_CORRECTS_existent_encore`
#: en annoncant « plus aucun chemin ne passe par un fil ». Le paquet en portait
#: bien un -- `atelier_scan_parcours.lancer_la_passe_de_calibration` --, c'est
#: le detecteur qui ne le voyait pas. Un banc qui rougit pour son propre angle
#: mort est exactement ce qu'on lui demande.
OUVREURS = frozenset({
    "ouvrir_la_generation", "ouvrir_l_encodage", "ouvrir_l_ecriture",
    "ouvrir_la_detection", "ouvrir_la_generation_de_la_mire",
    "ouvrir_l_execution", "ouvrir_la_calibration_en_cours",
})

MONTAGE = frozenset({"descendre", "push_screen"})

#: Ce qui, apres le montage, releve encore de la PILE et non du travail :
#: empiler, construire un ecran de progression, appeler un ouvreur. Un chemin
#: qui empile deux fois -- la progression, puis un refus par-dessus si le
#: prealable manque -- n'occupe pas la boucle pour autant, et le compter comme
#: un appel au coeur ferait de ce monteur un faux positif. La construction
#: compte parce qu'un `app.descendre(EcranX(...))` la porte sur la MEME ligne
#: que le montage, mais un second montage la porte plus loin.
GESTES_DE_PILE = MONTAGE | ECRANS_DE_PROGRESSION | OUVREURS

#: Le rendez-vous que `textual` offre pour laisser la boucle peindre.
RENDEZ_VOUS = frozenset({"_lancer_apres_le_dessin", "call_after_refresh"})

#: Le fil de travail : la seule chose qui garde la boucle vivante PENDANT.
FIL = frozenset({"run_worker"})

#: Ce qui, appele apres le montage, ne fait pas d'un monteur un lanceur. Ce
#: sont des gestes qui ne peuvent pas occuper la boucle : ni entree-sortie, ni
#: appel au coeur. La liste est courte et sa brievete est voulue -- un nom de
#: trop y ferait passer un vrai lanceur pour un monteur.
ANODINS = frozenset({
    "getattr", "setattr", "hasattr", "len", "str", "int", "bool", "list",
    "tuple", "dict", "set", "sorted", "abs", "min", "max", "isinstance",
    "format", "append", "add", "get", "join", "keys", "values", "items",
    "strip", "split", "chronometre",
})


# --------------------------------------------------------------------------
# Les gestes elementaires, isoles pour etre mesurables un a un.
# --------------------------------------------------------------------------


def nom_appele(appel: ast.Call) -> str:
    """Le nom sous lequel un appel est ecrit : `f(...)` ou `x.f(...)`."""
    f = appel.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def porteurs_directs(marqueurs: frozenset[str],
                     racine: Path | None = None) -> frozenset[str]:
    """Les fonctions du paquet qui portent un marqueur **dans leur corps**.

    **Pourquoi une fermeture transitive plutot qu'une liste a la main.** Le
    detecteur reconnait un rendez-vous ou un fil par le NOM appele. Il a donc
    un angle mort structurel : toute indirection neuve lui est invisible, et
    ce banc l'a paye deux fois -- `ouvrir_la_calibration_en_cours`, qu'il a
    fallu ajouter a `OUVREURS`, puis `lancer_la_detection`, ecrite le
    2026-09-06 pour reparer les deux chemins Scan, apres quoi la frontiere
    annoncait toujours ces chemins fautifs alors qu'ils ne l'etaient plus.

    Allonger la liste a chaque reparation, c'est demander a un banc de
    connaitre par coeur le code qu'il mesure -- et c'est ce qui rend un
    registre faux en silence. Un niveau d'indirection se **calcule** : une
    fonction du paquet qui porte `run_worker` dans son corps EST un depart au
    fil, quel que soit son nom, et l'appeler vaut donc l'appeler lui.

    **Ce que ca ne mesure pas, dit plutot que tu** : un seul niveau, et par
    presence du marqueur dans le corps -- pas par chemin d'execution. Une
    fonction qui porterait un `run_worker` dans une branche morte serait
    acquittee a tort. Le cas ne se presente pas aujourd'hui, et il se
    verrait : les deux fonctions concernees ne font que ca.
    """
    porteurs = set()
    for module, fonction in fonctions_du_paquet(racine):
        for n in ast.walk(fonction):
            if isinstance(n, ast.Call) and nom_appele(n) in marqueurs:
                porteurs.add(fonction.name)
    return frozenset(porteurs)


def role_et_verdict(fonction: ast.AST, *, fils: frozenset[str] = FIL,
                    rendez_vous: frozenset[str] = RENDEZ_VOUS
                    ) -> tuple[str, str] | None:
    """Le role d'une fonction vis-a-vis d'un ecran de progression.

    Rend `None` si elle n'en monte aucun. Sinon `(role, verdict)` :

    * `monteur` -- elle empile et rend la main. Rien ne lui est demande : ce
      n'est pas elle qui enchaine sur le coeur ;
    * `lanceur` -- elle empile PUIS appelle autre chose, dans le meme corps.
      C'est elle que la propriete vise, et son verdict vaut `fil`,
      `rendez-vous` ou `AUCUN`.

    **La distinction n'est pas cosmetique, et l'omettre rendait la mesure
    fausse.** Une premiere redaction comptait tout montage et annoncait « douze
    chemins fautifs sur quatorze » ; elle mettait au meme rang
    `atelier_pdf_execution.ouvrir_la_generation`, qui empile et rend la main --
    donc qui ne peut rien bloquer -- et `atelier_pdf_parcours.generer`, qui
    appelle le coeur juste apres. Mesure refaite : **huit lanceurs, dont
    quatre sans rendez-vous**, et six monteurs hors de cause.
    """
    appels = [n for n in ast.walk(fonction) if isinstance(n, ast.Call)]
    construits = {nom_appele(a) for a in appels} & ECRANS_DE_PROGRESSION
    montages = [a for a in appels
                if nom_appele(a) in OUVREURS
                or (nom_appele(a) in MONTAGE and construits)]
    if not montages:
        return None
    ligne_du_montage = min(a.lineno for a in montages)
    apres = {nom_appele(a) for a in appels
             if a.lineno > ligne_du_montage
             and nom_appele(a) not in ANODINS
             and nom_appele(a) not in GESTES_DE_PILE}
    if not apres:
        return ("monteur", "-")
    if apres & fils:
        return ("lanceur", "fil")
    if apres & rendez_vous:
        return ("lanceur", "rendez-vous")
    return ("lanceur", "AUCUN")


def fonctions_du_paquet(racine: Path | None = None):
    """Chaque fonction de `tui/`, avec son module. Le balayage part de LA."""
    dossier = TUI if racine is None else racine
    for chemin in sorted(dossier.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield chemin.name, n


def releve_des_chemins(racine: Path | None = None) -> dict[str, tuple[str, str]]:
    """`{module::fonction: (role, verdict)}` pour tout ce qui monte.

    Un chemin correct garde une entree plutot que d'etre absent : c'est ce qui
    rend le balayage OBSERVABLE. Une troncature d'un cran fait disparaitre une
    cle, donc elle se voit -- alors qu'elle survivrait si le releve n'etait que
    l'ensemble des fautifs (regle des fabriques, point 4, appliquee au
    balayage).
    """
    fils = FIL | porteurs_directs(FIL, racine)
    rendez_vous = RENDEZ_VOUS | porteurs_directs(RENDEZ_VOUS, racine)
    releve = {}
    for module, fonction in fonctions_du_paquet(racine):
        verdict = role_et_verdict(fonction, fils=fils, rendez_vous=rendez_vous)
        if verdict is not None:
            releve[f"{module}::{fonction.name}"] = verdict
    return releve


def fils_du_paquet(racine: Path | None = None) -> set[str]:
    """Les sites de `run_worker`, comptes **hors du releve**.

    Contrepartie du verdict `fil`, et elle n'est pas redondante : le releve ne
    voit un fil que s'il est dans une fonction qui monte aussi un ecran. Un
    `run_worker` ecrit ailleurs -- ou le seul du paquet supprime -- ne bougerait
    aucune ligne du releve. Ici, si.
    """
    sites = set()
    for module, fonction in fonctions_du_paquet(racine):
        for n in ast.walk(fonction):
            if isinstance(n, ast.Call) and nom_appele(n) in FIL:
                sites.add(f"{module}::{fonction.name}")
    return sites


#: Ce qui ACQUITTE un lanceur. **Le fil, et lui seul, depuis le 2026-09-06.**
#:
#: La premiere redaction acquittait « rendez-vous OU fil », et son propre
#: docstring de tete reconnaissait deja que le rendez-vous SEUL montre un ecran
#: fige. Le registre etant tombe a zero sous cette regle laxiste, la frontiere
#: annoncait vert un produit ou **deux** chemins gelaient encore -- l'extraction
#: (« la barre saute de 0 a 100 ») et l'encodage (« le glyphe d'attente est
#: immobile sur VS Code »). Les deux sont des mesures de terrain d'Egan, prises
#: le jour meme, sur un depot dont ce banc etait vert.
#:
#: Le rendez-vous reste un VERDICT -- `role_et_verdict` le rend, et le releve le
#: montre --, il n'est simplement plus un acquittement. Les deux proprietes sont
#: distinctes et il faut les deux : le rendez-vous pour que l'ecran soit peint
#: **une fois** avant que le coeur parte, le fil pour qu'il reste vivant
#: **pendant**. Un chemin qui a le fil a forcement laisse la boucle libre --
#: c'est ce que le fil est --, et le verdict `fil` l'emporte sur `rendez-vous`
#: quand les deux sont la (`test_le_FIL_l_emporte_sur_le_rendez_vous_...`).
ACQUITTENT = frozenset({"fil"})


def mesure_de_l_arbre(racine: Path | None = None,
                      acquittent: frozenset[str] = ACQUITTENT) -> set[str]:
    """Les LANCEURS que le fil n'acquitte pas. C'est ce qui gele.

    **La garde de role est REVENUE le 2026-09-06, et elle n'est plus
    equivalente.** Une premiere redaction ecrivait
    `role == "lanceur" and verdict == "AUCUN"`, et la campagne de mutation
    avait montre que la premiere moitie etait indistinguable de son absence --
    un monteur porte le verdict `-`, jamais `AUCUN`. C'etait vrai **de la
    regle laxiste** : `-` n'etant pas `AUCUN`, les monteurs tombaient d'
    eux-memes. Ce ne l'est plus de la regle stricte, ou tout ce qui n'est pas
    `fil` est retenu : sans la garde, les six MONTEURS du paquet -- qui
    empilent et rendent la main, donc qui ne peuvent rien bloquer --
    apparaitraient au registre. Le mutant est donc redevenu tuable, et
    `test_le_corpus_est_releve_ENTIEREMENT_des_deux_BORDS` le tue par son
    module `d_monteur.py`.
    """
    return {cle for cle, (role, verdict) in releve_des_chemins(racine).items()
            if role == "lanceur" and verdict not in acquittent}


# --------------------------------------------------------------------------
# Le registre, exhaustif et mesure. Il a vocation a DECROITRE jusqu'a zero ;
# il ne doit jamais croitre. Chaque ligne nomme un chemin qui appelle le coeur
# sans avoir laisse son ecran se dessiner -- donc un gel visible par
# l'operateur, et des touches qui se resolvent sur l'ecran suivant.
# --------------------------------------------------------------------------

#: `module::fonction`, trie. La LIGNE n'y figure pas : elle derive a chaque
#: edition du module, et un registre qui rougit pour un decalage de ligne
#: apprend a etre ignore.
#: **VIDE, et sous la regle STRICTE** -- l'etat de la fin du 2026-09-06.
#:
#: > **Deux textes se contredisaient ici** (finding `T2`, revue du
#: > 2026-09-07). Le premier annoncait « il porte de nouveau une ligne le soir
#: > sous la regle stricte », le second, quinze lignes plus bas, « VIDE de
#: > nouveau depuis le soir du 2026-09-06 ». Le registre valant `[]`, c'est le
#: > second qui disait vrai : le premier avait ete ecrit AVANT que la derniere
#: > ligne ne soit fermee, et le commit qui l'a fermee a ajoute sa prose sans
#: > retirer celle qu'elle perimait. Les deux sont fondus ci-dessous.
#:
#: La journee, dans l'ordre, parce qu'elle explique ce que la regle mesure :
#: sous « rendez-vous OU fil » -- la regle LAXISTE --, le registre est tombe a
#: quatre, puis deux, puis zero dans la matinee **pendant que trois chemins
#: montraient encore un ecran fige a l'operateur** : l'extraction, l'encodage
#: et l'ecriture du scan. Un registre a zero disait donc l'inverse de ce que
#: l'operateur voyait. Le durcissement -- tout ce qui n'est pas `fil` est
#: retenu -- a fait remonter la mesure a une ligne, et ce n'etait pas une
#: regression : c'est la mesure qui avait cesse de mentir.
#:
#: Cette derniere ligne etait `atelier_scan_parcours.py::ecrire`, qui montait
#: `E3-7` puis appelait `atelier_scan_ecriture.executer_et_conclure` derriere
#: un rendez-vous de dessin SEUL -- l'ecran apparaissait une fois et se figeait
#: pendant toute l'ecriture du scan. Le lot voisin l'a porte au fil par
#: `atelier_scan_ecriture.lancer_l_ecriture`, sur le patron de
#: `lancer_la_detection` et de `lancer_l_extraction`. Les trois lanceurs geles
#: du 2026-09-06 sont donc fermes tous les trois, et c'est
#: `test_le_registre_ne_porte_aucune_ligne_morte` qui a demande ce dernier
#: retrait et qui l'a valide.
#:
#: **Un registre vide n'est pas un banc mort** : c'est l'etat ou le volet 1
#: mesure ce qu'il annonce sans exception. Toute ligne qui y reapparaitrait
#: **hors reparation en cours** serait une regression, et non plus une dette
#: connue.
REGISTRE: list[str] = []


#: Les ecrans de progression qu'aucun chemin de production ne monte. Meme
#: registre, autre bout du defaut -- voir le volet 5.
#:
#: **Vide depuis le 2026-09-06.** `EcranSuppressionEnCours` etait sa seule
#: ligne : ecrit, complet, valide par sa maquette `E6-2c`, et monte par
#: personne. `suite_de_la_suppression` appelait le coeur puis empilait son
#: compte rendu, si bien que l'operateur passait de la confirmation au
#: resultat sans rien voir -- sur un lot de plusieurs gigaoctets, une
#: interface figee pendant toute l'ecriture. Il se monte desormais, derriere
#: un rendez-vous de dessin, avec son ecriture au fil et un rotor qui tourne
#: (il n'en avait aucun : monte tel quel, il aurait montre un rotor FIGE).
REGISTRE_DES_ECRANS_ORPHELINS: list[str] = []


# --------------------------------------------------------------------------
# Volet 1 -- LA FRONTIERE. Aucun lanceur sans rendez-vous hors du registre.
# --------------------------------------------------------------------------


def test_aucun_lanceur_sans_FIL_hors_du_registre():
    """Le chemin de plus qui gele l'interface fait rougir ICI.

    **Cette garde exigeait « rendez-vous OU fil » et elle etait verte a tort.**
    Le 2026-09-06, avec un registre a zero sous cette regle, Egan a fait passer
    la TUI sur le terrain : « la barre de progression saute de 0 a 100 » sur
    l'extraction, « le glyphe d'attente est immobile » sur l'encodage. Les deux
    chemins portaient bien un `_lancer_apres_le_dessin`, et les deux gelaient --
    parce qu'un rendez-vous DIFFERE d'une image, il ne QUITTE pas la boucle.
    Ce que l'operateur voit alors n'est pas un ecran absent, c'est un ecran
    **fige** : `0 %  0/6300` qui ne bouge plus, un rotor arrete. La forme la
    plus couteuse, puisqu'elle ressemble a un coeur en panne.

    C'est la seule direction qui protege le produit : un chemin neuf qui
    appelle le coeur sur la boucle apres avoir monte son ecran est un gel, quel
    que soit le soin mis a l'ecrire.
    """
    surplus = sorted(mesure_de_l_arbre() - set(REGISTRE))
    assert not surplus, (
        "ces chemins montent un ecran de progression puis appellent le coeur"
        " SUR LA BOUCLE -- l'ecran apparait peut-etre, il ne bougera pas :\n"
        + "\n".join(f"    {c}" for c in surplus)
        + "\n\nLe geste, et il en faut DEUX : `_lancer_apres_le_dessin` pour"
        " que l'ecran soit peint une fois avant le depart, et"
        " `run_worker(thread=True)` SOUS lui pour qu'il reste vivant pendant"
        " la passe. Le patron est"
        " `atelier_scan_detection.lancer_la_detection`."
    )


def test_le_registre_ne_porte_aucune_ligne_morte():
    """Un chemin repare doit SORTIR du registre, et ce rouge le dit.

    Ce rouge-la n'est pas une regression : il annonce une reparation que le
    registre n'a pas suivie. Le message le nomme, pour qu'on retire la ligne
    au lieu de chercher un defaut qui n'existe plus.
    """
    mortes = sorted(set(REGISTRE) - mesure_de_l_arbre())
    assert not mortes, (
        "ces chemins ne gelent plus -- retirer leur ligne du registre, ce"
        " n'est pas une regression :\n" + "\n".join(f"    {c}" for c in mortes)
    )


def test_le_registre_est_exactement_la_mesure():
    """Les deux sens ensemble, plus le cardinal qu'un rapport cite."""
    releve = mesure_de_l_arbre()
    assert releve == set(REGISTRE)
    assert len(REGISTRE) == len(set(REGISTRE)), "le registre porte un doublon"
    assert REGISTRE == sorted(REGISTRE), "registre en vrac : il ne se diff pas"


def test_les_chemins_CORRECTS_existent_encore():
    """La contrepartie du registre, sans laquelle il pourrait tout avaler.

    Si les trois chemins qui passent par un rendez-vous regressaient, le
    registre grossirait et le volet 1 le dirait -- mais rien ne dirait que le
    depot ne sait PLUS faire le geste. Ici, on mesure qu'il le sait encore, et
    on nomme le seul chemin du paquet qui va jusqu'au fil.
    """
    releve = releve_des_chemins()
    corrects = {cle for cle, (role, v) in releve.items()
                if role == "lanceur" and v in ("rendez-vous", "fil")}
    assert len(corrects) >= 9, f"plus que {len(corrects)} chemins corrects"
    avec_fil = {cle for cle, (role, v) in releve.items() if v == "fil"}
    assert avec_fil == {
        # **Les deux entrees NEUVES du 2026-09-06**, et elles ferment les deux
        # retours de terrain d'Egan : la barre de `E2-4` qui « saute de 0 a
        # 100 », et le rotor de `E4-4` « immobile sur le terminal VS Code ».
        "atelier_exports_parcours.py::encoder",
        "atelier_extraction_ecriture.py::_ecrire",
        "atelier_pdf_parcours.py::generer",
        "atelier_pdf_parcours.py::generer_la_mire",
        "atelier_scan_detection.py::trancher_le_conflit",
        # **L'entree NEUVE du 2026-09-07** (`EPIC11-ARB-267`) : l'adoption
        # d'une planche etrangere RELANCE la passe, et elle la relance au fil
        # comme la passe d'origine. Elle vit dans le PARCOURS et non dans le
        # module de l'ecran -- contrairement a `trancher_le_conflit` juste
        # au-dessus --, parce que la frontiere `C3` de
        # `test_journal_du_scan_atteint_la_tui.py` exige que la methode qui
        # donne `self._logger` au coeur soit aussi celle qui revise le relais
        # sur la surface neuve.
        "atelier_scan_parcours.py::adopter",
        "atelier_scan_parcours.py::detecter",
        # **L'entree NEUVE du soir du 2026-09-06**, la troisieme et derniere de
        # la journee : l'ecriture du Scan etait la seule ligne du registre, et
        # elle part desormais au fil par `atelier_scan_ecriture.`
        # `lancer_l_ecriture`. Le registre est vide **sous la regle stricte**.
        "atelier_scan_parcours.py::ecrire",
        "atelier_scan_parcours.py::lancer_la_passe_de_calibration",
        "projet_suppression.py::suite_de_la_suppression",
    }, (
        "les chemins qui partent au fil de travail ont change :"
        f" {sorted(avec_fil)}.\n"
        "En trouver un de plus est une bonne nouvelle -- ajoute-le ici. En"
        " perdre un est une regression : c'est le fil, et lui seul, qui garde"
        " l'ecran vivant PENDANT la passe.")
    assert fils_du_paquet() == {
        "atelier_exports_parcours.py::encoder",
        # L'extraction porte son `run_worker` dans une fonction de module --
        # `lancer_l_extraction` --, comme la detection : c'est la fermeture
        # transitive de `porteurs_directs` qui rattache le verdict `fil` a
        # `_ecrire`, et c'est pourquoi les deux ensembles de ce test ne se
        # recouvrent pas ligne pour ligne.
        "atelier_extraction_ecriture.py::lancer_l_extraction",
        "atelier_pdf_parcours.py::generer",
        "atelier_pdf_parcours.py::generer_la_mire",
        "atelier_scan_detection.py::lancer_la_detection",
        # Meme forme que l'extraction et la detection : le `run_worker` vit
        # dans une fonction de MODULE, et c'est la fermeture transitive de
        # `porteurs_directs` qui rattache le verdict `fil` a
        # `atelier_scan_parcours.py::ecrire`.
        "atelier_scan_ecriture.py::lancer_l_ecriture",
        "atelier_scan_parcours.py::lancer_la_passe_de_calibration",
        "projet_suppression.py::suite_de_la_suppression",
    }, (
        "les sites de `run_worker` du paquet ont change :"
        f" {sorted(fils_du_paquet())}")


# --------------------------------------------------------------------------
# Volet 2 -- LA CONFRONTATION. Chaque ligne du registre est un chemin REEL.
# --------------------------------------------------------------------------


# Un `parametrize` sur une liste vide ne rend pas un vert : il rend un SAUT,
# et un `s` dans la sortie se lit comme un vert de plus. C'est exactement la
# tolerance muette contre laquelle ce volet existe -- retournee contre lui le
# jour ou le registre est enfin tombe a zero (2026-09-06). La sentinelle garde
# une ligne de sortie et nomme ce qu'elle mesure.
SENTINELLE_DU_REGISTRE_VIDE = "<registre vide>"


@pytest.mark.parametrize("cle", REGISTRE or [SENTINELLE_DU_REGISTRE_VIDE])
def test_chaque_ligne_du_registre_est_un_lanceur_reel(cle):
    """Le module existe, la fonction existe, et elle monte bien un ecran.

    Sans ce volet, une ligne de registre mal orthographiee serait une
    tolerance muette : elle n'apparaitrait dans aucune mesure et personne ne
    la verrait jamais rougir.
    """
    if cle == SENTINELLE_DU_REGISTRE_VIDE:
        # Le premier assert seul serait TAUTOLOGIQUE : cette branche n'est
        # atteinte que quand `REGISTRE` est vide. C'est le second qui mesure
        # -- il va rechercher dans l'arbre, et rougit si le registre est vide
        # parce qu'on l'a EFFACE plutot que parce qu'il n'y a plus rien a y
        # mettre.
        assert REGISTRE == [], (
            f"sentinelle jouee alors que le registre porte des lignes : {REGISTRE}")
        fautifs = mesure_de_l_arbre()
        assert fautifs == set(), (
            "le registre est vide mais l'arbre porte encore des chemins"
            f" fautifs : {sorted(fautifs)}")
        return
    module, _, fonction = cle.partition("::")
    chemin = TUI / module
    assert chemin.is_file(), f"{module} n'existe pas"
    trouvee = [f for m, f in fonctions_du_paquet()
               if m == module and f.name == fonction]
    assert trouvee, f"{module} ne porte pas de fonction {fonction}"
    # **Le verdict attendu n'est plus `AUCUN` mais « tout sauf `fil` »** : une
    # ligne de registre peut desormais porter un chemin qui prend bien
    # rendez-vous et qui gele quand meme, ce qui est exactement le cas de
    # `atelier_scan_parcours.ecrire`. Exiger `AUCUN` ici aurait rendu la
    # ligne inscriptible impossible, et donc la garde inutilisable pour la
    # classe de defaut qu'elle vient d'apprendre a voir.
    role, verdict = role_et_verdict(trouvee[0])
    assert role == "lanceur", (role, verdict)
    assert verdict not in ACQUITTENT, (
        f"{cle} part au fil : ce n'est plus une ligne de registre")


# --------------------------------------------------------------------------
# Volet 3 -- LE DETECTEUR SE MESURE. Sans ca, une frontiere verte ne prouve
# rien : un detecteur qui ne detecte jamais rien passe tout le volet 1.
# --------------------------------------------------------------------------


def _fonction(corps: str) -> ast.AST:
    """La premiere fonction d'un source de synthese."""
    arbre = ast.parse(corps)
    return next(n for n in ast.walk(arbre)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))


def test_le_detecteur_attrape_un_lanceur_nu():
    """Monter puis appeler le coeur, sans rien entre les deux : c'est le gel."""
    assert role_et_verdict(_fonction(
        "def generer(self):\n"
        "    ecran = ouvrir_la_generation(self.app, s, p)\n"
        "    rapport = executer_les_lots(lots)\n")) == ("lanceur", "AUCUN")


def test_le_rendez_vous_SEUL_est_un_verdict_mais_n_ACQUITTE_PLUS():
    """Le meme corps, un rendez-vous en plus : le verdict change, pas le sort.

    **C'est la ligne de doctrine du durcissement du 2026-09-06.** Le
    rendez-vous reste **mesure** -- il faut bien pouvoir dire d'un chemin qu'il
    l'a --, mais il n'acquitte plus : `ACQUITTENT` ne porte que `fil`. Les deux
    assertions sont ensemble parce qu'aucune ne suffit : la premiere seule
    laisserait croire que le detecteur a change d'avis sur ce qu'est un
    rendez-vous, la seconde seule ne dirait pas ce qui a ete detecte.
    """
    assert role_et_verdict(_fonction(
        "def generer(self):\n"
        "    ecran = ouvrir_la_generation(self.app, s, p)\n"
        "    _lancer_apres_le_dessin(self.app, self.lancer)\n"
    )) == ("lanceur", "rendez-vous")
    assert "rendez-vous" not in ACQUITTENT, (
        "le rendez-vous acquitte de nouveau : la frontiere redevient verte sur"
        " les deux chemins qu'Egan a vus figes le 2026-09-06")


def test_le_detecteur_ACQUITTE_un_lanceur_qui_part_au_FIL():
    """Le fil vaut acquittement, et il vaut mieux que le rendez-vous."""
    assert role_et_verdict(_fonction(
        "def calibrer(self):\n"
        "    ecran = ouvrir_la_detection(self.app)\n"
        "    return self.app.run_worker(passe, thread=True)\n"
    )) == ("lanceur", "fil")


def test_un_MONTEUR_n_est_pas_un_lanceur():
    """Empiler et rendre la main ne peut rien bloquer -- rien ne lui est demande.

    C'est la correction qui a fait passer la mesure de « douze fautifs » a
    « quatre » : sans elle, les six ouvreurs du paquet etaient comptes comme
    des defauts alors qu'ils n'appellent aucun coeur.
    """
    assert role_et_verdict(_fonction(
        "def ouvrir_la_generation(app, surface, passe):\n"
        "    ecran = EcranGenerationDesPlanches(surface, passe)\n"
        "    setattr(app, ATTRIBUT, ecran)\n"
        "    app.descendre(ecran)\n"
        "    return ecran\n")) == ("monteur", "-")


def test_une_fonction_SANS_ecran_de_progression_est_hors_perimetre():
    """Aucun faux positif : monter un ecran quelconque ne concerne pas ce banc."""
    assert role_et_verdict(_fonction(
        "def remonter(self):\n"
        "    self.app.descendre(EcranReglages())\n"
        "    self.recalculer()\n")) is None


def test_le_rendez_vous_AVANT_le_montage_ne_compte_PAS():
    """La position compte : un rendez-vous pris avant d'empiler ne protege rien.

    C'est le mutant que cette mesure tue. Un detecteur qui chercherait le mot
    n'importe ou dans le corps acquitterait un chemin qui rend la main puis
    monte puis bloque -- c'est-a-dire exactement le gel, avec le bon mot au
    mauvais endroit.
    """
    assert role_et_verdict(_fonction(
        "def generer(self):\n"
        "    _lancer_apres_le_dessin(self.app, self.preparer)\n"
        "    ecran = ouvrir_la_generation(self.app, s, p)\n"
        "    rapport = executer_les_lots(lots)\n")) == ("lanceur", "AUCUN")


def test_l_ancre_est_le_PREMIER_montage_et_non_le_dernier():
    """Un chemin qui monte, travaille, puis remonte : le travail est AU MILIEU.

    Prendre le dernier montage pour ancre deplacerait la fenetre APRES l'appel
    au coeur, et ce chemin -- qui gele -- serait rendu comme un monteur sans
    reproche. La forme est realiste : un parcours qui monte sa progression,
    appelle le coeur, puis empile son compte rendu dans le meme corps.
    """
    assert role_et_verdict(_fonction(
        "def generer(self):\n"
        "    ouvrir_la_generation(self.app, s, p)\n"
        "    rapport = executer_les_lots(lots)\n"
        "    self.app.descendre(EcranGenerationDesPlanches(rapport))\n"
    )) == ("lanceur", "AUCUN")


def test_ce_qui_est_SUR_la_ligne_du_montage_n_est_pas_APRES_lui():
    """La borne est stricte, et un appel imbrique partage la ligne du montage.

    `app.descendre(EcranDetectionEnCours(s))` tient sur une ligne : la
    construction de l'ecran y a le meme numero que `descendre`. Une borne large
    (`>=`) la compterait comme du travail fait apres le montage, et ce monteur
    -- qui empile et rend la main -- deviendrait un chemin fautif de plus.
    C'est un faux positif, la moitie la plus couteuse d'une frontiere : elle
    apprend a etre ignoree.
    """
    assert role_et_verdict(_fonction(
        "def ouvrir_la_detection(app, s):\n"
        "    app.descendre(EcranDetectionEnCours(s))\n"
        "    return None\n")) == ("monteur", "-")


def test_un_ARGUMENT_calcule_SUR_la_ligne_du_montage_est_AVANT_lui():
    """La borne stricte, mesuree sur ce qui n'est PAS un geste de pile.

    Un appel imbrique dans le montage s'evalue **avant** que l'ecran ne soit
    empile -- c'est l'ordre d'evaluation de Python, pas une convention. Le
    compter comme du travail fait apres le dessin est faux dans le seul sens
    qui coute : il fabrique un chemin fautif la ou il n'y en a pas.

    Le cas est distinct de celui de la construction d'ecran ci-dessous : ici
    l'appel imbrique n'est **pas** un geste de pile, donc aucun filtre de nom
    ne le rattrape. Seule la borne stricte le fait, et c'est ce qui rend ce
    test necessaire en plus de l'autre.
    """
    assert role_et_verdict(_fonction(
        "def ouvrir_la_generation(app, lots):\n"
        "    app.descendre(EcranGenerationDesPlanches(plan_des_lots(lots)))\n"
        "    return None\n")) == ("monteur", "-")


def test_un_SECOND_montage_n_est_pas_du_travail():
    """Empiler deux fois ne gele rien : ce sont deux gestes de pile.

    Le cas est reel -- un ouvreur qui empile la progression puis, si le
    prealable manque, empile un refus par-dessus. Compter le second `descendre`
    comme un appel au coeur ferait de ce monteur un lanceur fautif.
    """
    assert role_et_verdict(_fonction(
        "def ouvrir(app, plan):\n"
        "    ecran = EcranEcritureDuScan(plan)\n"
        "    app.descendre(ecran)\n"
        "    if plan is None:\n"
        "        app.push_screen(EcranEcritureDuScan(plan))\n"
        "    return ecran\n")) == ("monteur", "-")


def test_le_FIL_l_emporte_sur_le_rendez_vous_quand_les_DEUX_sont_la():
    """L'ordre des verdicts n'est pas arbitraire, et il porte une doctrine.

    Le rendez-vous fait apparaitre l'ecran **une fois** ; le fil est ce qui le
    garde vivant **pendant**. Un chemin qui a les deux est au meilleur des deux
    regimes, et c'est `fil` qui doit le dire -- sinon
    `test_les_chemins_CORRECTS_existent_encore`, qui compte les fils
    exactement, ne verrait plus le patron a recopier le jour ou il gagne un
    rendez-vous de plus.
    """
    assert role_et_verdict(_fonction(
        "def calibrer(self):\n"
        "    ouvrir_la_calibration_en_cours(self.app, surface=s)\n"
        "    _lancer_apres_le_dessin(self.app, self.preparer)\n"
        "    return self.app.run_worker(passe, thread=True)\n"
    )) == ("lanceur", "fil")


def test_un_geste_ANODIN_apres_le_montage_ne_fait_pas_un_lanceur():
    """Poser un drapeau n'occupe pas la boucle ; appeler le coeur, si.

    Les deux moities sont mesurees ensemble, sinon la liste des anodins
    pourrait tout avaler sans que rien ne le dise.
    """
    assert role_et_verdict(_fonction(
        "def ouvrir(app):\n"
        "    ecran = EcranDetectionEnCours(s)\n"
        "    app.descendre(ecran)\n"
        "    setattr(app, 'tache', True)\n"
        "    return ecran\n")) == ("monteur", "-")
    assert role_et_verdict(_fonction(
        "def ouvrir(app):\n"
        "    ecran = EcranDetectionEnCours(s)\n"
        "    app.descendre(ecran)\n"
        "    setattr(app, 'tache', True)\n"
        "    detecter(tout)\n")) == ("lanceur", "AUCUN")


def modules_PORTEURS_DE_FONCTION(dossier: Path) -> list[str]:
    """Les modules qui definissent au moins une fonction, **par un autre chemin**.

    Oracle independant du detecteur : une expression reguliere sur le TEXTE,
    la ou `fonctions_du_paquet` passe par `ast`. Comparer `ast` a `ast`
    n'aurait mesure que la coherence du balayage avec lui-meme -- une
    troncature commune aux deux cotes serait restee verte.

    Le filtre est necessaire et sa raison se mesure : `tui/` porte
    **cinquante** fichiers dont **`__init__.py` ne definit aucune fonction**.
    Une egalite avec le simple `glob` rougissait donc en permanence, ce qui
    est le defaut que ce banc a lui-meme paye a sa premiere redaction.
    """
    return sorted(c.name for c in dossier.glob("*.py")
                  if re.search(r"^[ \t]*(async +)?def ",
                               c.read_text(encoding="utf-8"), re.M))


#: Corpus de synthese pour la fermeture transitive. **Quatre modules**, et les
#: deux porteurs sont aux deux BORDS -- point 4 de la regle des fabriques,
#: applique au troisieme detecteur du banc. Les cibles sont DISTINGUABLES :
#: un porteur de fil, un porteur de rendez-vous, un lanceur qui n'appelle ni
#: l'un ni l'autre, et un lanceur par chaque porteur.
CORPUS_TRANSITIF = {
    "a_porte_le_fil.py": (
        "def lancer_la_detection(app, ecran, demande):\n"
        "    return app.run_worker(passe, thread=True)\n"),
    "b_lanceurs.py": (
        "def detecter(self, source):\n"
        "    ecran = ouvrir_la_detection(self.app)\n"
        "    return lancer_la_detection(self.app, ecran, demande)\n\n"
        "def encoder(self):\n"
        "    ecran = ouvrir_l_encodage(self.app, p)\n"
        "    return lancer_l_encodage(self.app, ecran)\n\n"
        "def generer(self):\n"
        "    ecran = ouvrir_la_generation(self.app, s, p)\n"
        "    executer_les_lots(lots)\n"),
    "c_intercale.py": "VALEUR = 1\n",
    "d_porte_le_rendez_vous.py": (
        "def lancer_l_encodage(app, ecran):\n"
        "    return _lancer_apres_le_dessin(app, passe)\n"),
}


def _monte_le_corpus_transitif(tmp_path: Path) -> Path:
    dossier = tmp_path / "transitif"
    dossier.mkdir()
    for nom, corps in CORPUS_TRANSITIF.items():
        (dossier / nom).write_text(corps, encoding="utf-8")
    return dossier


def test_l_INDIRECTION_est_suivie_d_UN_cran_dans_les_deux_sens(tmp_path):
    """Le detecteur reconnait un fil par le NOM, donc toute indirection neuve
    lui echappe -- et ce banc l'a paye deux fois.

    Les deux porteurs sont aux deux BORDS du corpus : celui du fil en tete,
    celui du rendez-vous en queue. Un balayage tronque d'un cran perd l'un ou
    l'autre, et le lanceur correspondant retombe a `AUCUN` -- ce qui se voit.
    """
    dossier = _monte_le_corpus_transitif(tmp_path)
    releve = releve_des_chemins(dossier)
    assert releve["b_lanceurs.py::detecter"] == ("lanceur", "fil")
    assert releve["b_lanceurs.py::encoder"] == ("lanceur", "rendez-vous")
    assert releve["b_lanceurs.py::generer"] == ("lanceur", "AUCUN")
    # **Sous la regle stricte, `encoder` est fautif lui aussi** : il a bien
    # trouve son porteur de rendez-vous a un cran -- c'est ce que la ligne
    # ci-dessus mesure --, et un rendez-vous ne suffit plus.
    assert mesure_de_l_arbre(dossier) == {"b_lanceurs.py::generer",
                                          "b_lanceurs.py::encoder"}


def test_une_TRONCATURE_du_balayage_des_PORTEURS_se_voit_aux_DEUX_BORDS(tmp_path):
    """Retirer le porteur de tete, puis celui de queue : les deux mordent.

    Sans ce volet, `porteurs_directs` pourrait ne lire qu'un module sur deux
    sans qu'aucune mesure ne bouge -- c'est exactement le mode de panne que le
    corpus des orphelins a demasque sur son second balayage.
    """
    dossier = _monte_le_corpus_transitif(tmp_path)

    (dossier / "a_porte_le_fil.py").unlink()
    assert releve_des_chemins(dossier)["b_lanceurs.py::detecter"] == (
        "lanceur", "AUCUN"), "porteur de TETE saute : le fil n'est plus suivi"
    assert mesure_de_l_arbre(dossier) == {"b_lanceurs.py::generer",
                                          "b_lanceurs.py::encoder",
                                          "b_lanceurs.py::detecter"}

    (dossier / "a_porte_le_fil.py").write_text(
        CORPUS_TRANSITIF["a_porte_le_fil.py"], encoding="utf-8")
    (dossier / "d_porte_le_rendez_vous.py").unlink()
    # **Le bord de QUEUE se lit sur le VERDICT, pas sur la mesure**, et c'est
    # le durcissement qui l'impose : `encoder` etant fautif des deux cotes
    # sous la regle stricte -- rendez-vous ou pas --, l'ensemble des fautifs
    # ne bouge plus quand ce porteur disparait. Le verdict, lui, passe de
    # `rendez-vous` a `AUCUN` : c'est la seule mesure qui voie encore cette
    # troncature-la, et elle est plus fine que celle qu'elle remplace.
    assert releve_des_chemins(dossier)["b_lanceurs.py::encoder"] == (
        "lanceur", "AUCUN"), "porteur de QUEUE saute : le rendez-vous n'est"
    assert mesure_de_l_arbre(dossier) == {"b_lanceurs.py::generer",
                                          "b_lanceurs.py::encoder"}


def test_porteurs_directs_ne_rend_QUE_les_porteurs(tmp_path):
    """La contrepartie : la fermeture ne doit pas tout acquitter.

    Un detecteur qui rendrait l'ensemble des fonctions du paquet ferait passer
    n'importe quel lanceur pour correct, et le registre tomberait a zero en
    mentant. Les deux ensembles sont mesures separement, et ils sont DISJOINTS.
    """
    dossier = _monte_le_corpus_transitif(tmp_path)
    assert porteurs_directs(FIL, dossier) == {"lancer_la_detection"}
    assert porteurs_directs(RENDEZ_VOUS, dossier) == {"lancer_l_encodage"}
    assert not (porteurs_directs(FIL, dossier)
                & porteurs_directs(RENDEZ_VOUS, dossier))


def test_le_balayage_visite_TOUS_les_modules_du_paquet():
    """Une troncature d'un cran, en tete ou en queue, fait rougir ICI.

    Le releve garde les chemins CORRECTS ; le paquet est relu independamment,
    par l'oracle textuel ci-dessus. Les deux bords sont nommes en plus du
    cardinal, parce que le cardinal seul ne dit pas LEQUEL manque.
    """
    modules = sorted({cle.split("::")[0] for cle in releve_des_chemins()})
    fichiers = sorted(c.name for c in TUI.glob("*.py"))
    assert modules, "aucun module ne monte d'ecran : le balayage est mort"
    assert set(modules) <= set(fichiers)

    attendus = modules_PORTEURS_DE_FONCTION(TUI)
    vus = sorted({m for m, _ in fonctions_du_paquet()})
    manquants = sorted(set(attendus) - set(vus))
    assert not manquants, (
        "le balayage saute ces modules, qui portent pourtant des fonctions :\n"
        + "\n".join(f"    {m}" for m in manquants))
    assert vus == attendus
    assert vus[0] == attendus[0], f"tete sautee : {attendus[0]}"
    assert vus[-1] == attendus[-1], f"queue sautee : {attendus[-1]}"


def test_l_ORACLE_du_balayage_est_bien_INDEPENDANT_du_detecteur(tmp_path):
    """L'oracle se mesure a son tour, sinon il pourrait tout accepter.

    Trois modules distinguables : deux porteurs de fonction aux deux BORDS,
    un module sans fonction au milieu -- exactement la forme que `tui/` a
    (`__init__.py` n'en porte aucune) et que la premiere redaction ignorait.
    """
    dossier = tmp_path / "paquet"
    dossier.mkdir()
    (dossier / "a_avec.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (dossier / "b_sans.py").write_text("X = 1\nY = 2\n", encoding="utf-8")
    (dossier / "c_avec.py").write_text(
        "class K:\n    async def g(self):\n        pass\n", encoding="utf-8")

    assert modules_PORTEURS_DE_FONCTION(dossier) == ["a_avec.py", "c_avec.py"]
    assert sorted({m for m, _ in fonctions_du_paquet(dossier)}) == \
        modules_PORTEURS_DE_FONCTION(dossier)


# --------------------------------------------------------------------------
# Volet 4 -- LA REGLE DES FABRIQUES, sur un corpus de synthese. Cibles en
# tete, au milieu et en queue, elements distinguables.
# --------------------------------------------------------------------------

#: Cinq modules de synthese, DISTINGUABLES -- ni le meme ecran, ni le meme
#: verdict, ni le meme nombre de fonctions. Les fautifs sont en TETE, au
#: MILIEU et en QUEUE ; les corrects sont intercales, pour qu'un balayage qui
#: s'arrete a la premiere trouvaille se voie aussi.
CORPUS = {
    "a_tete.py": (
        "def generer(self):\n"
        "    ecran = ouvrir_la_generation(self.app, s, p)\n"
        "    executer_les_lots(lots)\n"),
    # **La forme CORRECTE porte les deux gestes depuis le 2026-09-06** : le
    # rendez-vous, et le fil SOUS lui. Avec le seul rendez-vous, ce module
    # etait le « correct » du corpus sous la regle laxiste -- il serait
    # desormais fautif, et le corpus n'aurait plus aucun acquitte a opposer
    # a ses trois cibles.
    "b_correct.py": (
        "def encoder(self):\n"
        "    ecran = ouvrir_l_encodage(self.app, p)\n"
        "    _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(\n"
        "        self.lancer, thread=True))\n"),
    # **La cible du MILIEU est la classe de defaut NEUVE** : un rendez-vous
    # seul, c'est-a-dire un ecran peint une fois puis fige. Elle est ici, et
    # pas ailleurs, parce qu'elle est le seul module du corpus dont le sort
    # DEPEND du durcissement : sous la regle laxiste il sort de la mesure, et
    # `test_le_corpus_est_releve_ENTIEREMENT_des_deux_BORDS` rougit. Le corpus
    # mesure donc la regle, et pas seulement le balayage.
    "c_milieu.py": (
        "def detecter(self):\n"
        "    ecran = ouvrir_la_detection(self.app)\n"
        "    _lancer_apres_le_dessin(self.app, self.conclure)\n"),
    "d_monteur.py": (
        "def ouvrir_l_ecriture(app, plan):\n"
        "    ecran = EcranEcritureDuScan(plan)\n"
        "    app.descendre(ecran)\n"
        "    return ecran\n"),
    "e_queue.py": (
        "def supprimer(self):\n"
        "    ecran = EcranSuppressionEnCours(plan)\n"
        "    self.app.descendre(ecran)\n"
        "    executer_la_suppression(plan)\n"),
}

FAUTIFS_DU_CORPUS = {"a_tete.py::generer", "c_milieu.py::detecter",
                     "e_queue.py::supprimer"}


def _monte_le_corpus(tmp_path: Path) -> Path:
    """Ecrit les cinq modules et rend leur dossier."""
    dossier = tmp_path / "tui"
    dossier.mkdir()
    for nom, corps in CORPUS.items():
        (dossier / nom).write_text(corps, encoding="utf-8")
    return dossier


def test_le_corpus_est_releve_ENTIEREMENT_des_deux_BORDS(tmp_path):
    """Le balayage complet, cibles aux deux bords ET au milieu.

    Point 4 de la regle des fabriques : une cible au milieu demasque un
    appariement fautif, elle ne demasque pas un balayage tronque. Les deux
    bords sont nommes en plus de l'egalite, pour que le message dise LEQUEL
    manque.
    """
    dossier = _monte_le_corpus(tmp_path)
    mesure = mesure_de_l_arbre(dossier)
    assert mesure == FAUTIFS_DU_CORPUS
    assert "a_tete.py::generer" in mesure
    assert "c_milieu.py::detecter" in mesure
    assert "e_queue.py::supprimer" in mesure


def test_le_corpus_garde_ses_chemins_CORRECTS_et_ses_MONTEURS(tmp_path):
    """La partition, sans laquelle « trois fautifs » ne voudrait rien dire.

    Deux raisons differentes de ne pas etre au registre -- un rendez-vous, et
    le fait de n'etre qu'un monteur --, ce qui rend la mesure sensible a un
    acquittement trop large comme a un trop etroit.
    """
    dossier = _monte_le_corpus(tmp_path)
    releve = releve_des_chemins(dossier)
    assert sorted(releve) == sorted(
        ["a_tete.py::generer", "b_correct.py::encoder", "c_milieu.py::detecter",
         "d_monteur.py::ouvrir_l_ecriture", "e_queue.py::supprimer"])
    assert releve["b_correct.py::encoder"] == ("lanceur", "fil")
    assert releve["c_milieu.py::detecter"] == ("lanceur", "rendez-vous")
    assert releve["d_monteur.py::ouvrir_l_ecriture"] == ("monteur", "-")
    # **Le monteur est hors mesure, et c'est la garde de role qui le tient.**
    # Sous la regle stricte, son verdict `-` n'est pas dans `ACQUITTENT` : sans
    # la garde, il tomberait au registre. Le mutant est redevenu tuable, et
    # c'est ici qu'il meurt.
    assert "d_monteur.py::ouvrir_l_ecriture" not in mesure_de_l_arbre(dossier)


def test_une_TRONCATURE_du_balayage_a_l_un_ou_l_autre_BORD_se_voit(tmp_path):
    """Retirer le premier module, puis le dernier : les deux font bouger la mesure."""
    dossier = _monte_le_corpus(tmp_path)
    entier = mesure_de_l_arbre(dossier)

    (dossier / "a_tete.py").unlink()
    assert entier - mesure_de_l_arbre(dossier) == {"a_tete.py::generer"}

    (dossier / "a_tete.py").write_text(CORPUS["a_tete.py"], encoding="utf-8")
    (dossier / "e_queue.py").unlink()
    assert entier - mesure_de_l_arbre(dossier) == {"e_queue.py::supprimer"}


def test_les_cibles_du_corpus_sont_DISTINGUABLES(tmp_path):
    """Point 1 de la regle des fabriques : trois cibles uniformes ne mesureraient
    aucune permutation."""
    dossier = _monte_le_corpus(tmp_path)
    releve = releve_des_chemins(dossier)
    assert len({cle.split("::")[1] for cle in releve}) == len(releve)
    # QUATRE verdicts distincts depuis le durcissement -- `AUCUN`,
    # `rendez-vous`, `fil` et `-` --, la ou trois suffisaient. Le quatrieme est
    # celui qui separe « fige » de « vivant », donc celui qui compte.
    assert len({verdict for _, verdict in releve.values()}) >= 4


# --------------------------------------------------------------------------
# Volet 5a -- L'ANCRE DYNAMIQUE. Le detecteur ci-dessus lit du texte ; ici on
# compte des IMAGES sur la vraie boucle `textual`, avec la vraie `CoqueTui` et
# le vrai `_lancer_apres_le_dessin` du produit. Sans ce volet, la frontiere ne
# mesurerait que sa propre grammaire.
# --------------------------------------------------------------------------

#: Duree de la passe de synthese. Assez longue pour qu'une boucle vivante ait
#: peint plusieurs fois, assez courte pour ne pas peser sur la suite. La
#: mesure ne depend pas de sa valeur : c'est un ECART entre zero et non-zero
#: qui est asserte, jamais un seuil de temps.
DUREE_DE_LA_PASSE = 0.4


def _classe_de_palier():
    """`Palier` du produit, augmente d'un journal de touches."""
    from mixed_media_utility.tui.coque import Palier

    class PalierTemoin(Palier):
        def __init__(self, titre: str) -> None:
            super().__init__()
            self.titre = titre
            self.touches: list[str] = []

        def on_key(self, evenement) -> None:  # pragma: no cover - pilote
            self.touches.append(evenement.key)

    return PalierTemoin


def _compteur_d_images(app) -> dict:
    """Compte les ecritures au pilote `textual`, c'est-a-dire les IMAGES.

    C'est la seule mesure qui reponde a la phrase d'Egan -- « on ne voit pas la
    progression ». Un `is_mounted` dit qu'un objet existe ; il ne dit pas qu'un
    pixel a atteint le terminal. La premiere redaction interrogeait le
    compositeur (`Compositor.map`) et levait ; le pilote, lui, est le dernier
    maillon avant l'ecran.
    """
    pilote = app._driver
    ecrire = pilote.write
    boite = {"images": 0}

    def compte(texte):
        boite["images"] += 1
        return ecrire(texte)

    pilote.write = compte
    return boite


def _passe_synchrone(duree: float = DUREE_DE_LA_PASSE) -> None:
    """Le coeur, tel que la boucle le subit : elle n'a pas la main.

    Une attente **active** et non un `sleep`, et la difference est de FORME et
    non de resultat : la campagne de mutation a remplace cette boucle par
    `time.sleep(duree)` et **les trois tests du volet 5a restent verts**. C'est
    attendu -- un `sleep` synchrone occupe le fil de la boucle exactement comme
    un calcul. Le mutant est donc **equivalent**, garde comme temoin plutot que
    tolere en silence, et la boucle occupee reste preferee pour une raison qui
    n'est pas la mesure : c'est ce que fait un appel au coeur.
    """
    debut = time.monotonic()
    while time.monotonic() - debut < duree:
        pass


def test_SANS_rendez_vous_l_ecran_n_est_JAMAIS_dessine():
    """La mesure d'Egan, reproduite : zero image, et l'ecran meme pas monte.

    C'est le fait qui fonde tout le banc. `descendre` empile ; le dessin, lui,
    est un evenement de la boucle, et une passe synchrone la garde du premier
    au dernier jalon. Le symetrique est mesure dans la foulee -- sans lui,
    « zero image » pourrait n'etre qu'un compteur mort.
    """
    import asyncio

    from mixed_media_utility.tui.coque import CoqueTui

    Palier = _classe_de_palier()
    depart, progression = Palier("depart"), Palier("progression")
    app = CoqueTui(paliers=[depart])
    mesure = {}

    async def tour():
        async with app.run_test(size=(80, 24)) as pilote:
            await pilote.pause()
            boite = _compteur_d_images(app)
            app.descendre(progression)
            _passe_synchrone()
            mesure["images_pendant"] = boite["images"]
            mesure["monte_pendant"] = progression.is_mounted
            await pilote.pause()
            mesure["images_apres"] = boite["images"]
            mesure["monte_apres"] = progression.is_mounted

    asyncio.run(tour())

    assert mesure["images_pendant"] == 0, (
        "des images ont ete ecrites pendant une passe synchrone : la boucle"
        " `textual` n'est plus bloquee par un appel synchrone, et tout ce banc"
        " repose sur le contraire -- le verifier avant de conclure")
    assert mesure["monte_pendant"] is False
    assert mesure["images_apres"] >= 1, (
        "aucune image meme APRES avoir rendu la main : le compteur ne compte"
        " rien, donc le zero ci-dessus ne prouvait rien")
    assert mesure["monte_apres"] is True


def test_AVEC_un_rendez_vous_l_ecran_est_dessine_AVANT_la_passe():
    """Le geste que le registre reclame, mesure sur `_lancer_apres_le_dessin`.

    Meme corps, meme passe, meme compteur : la seule difference est le
    rendez-vous. Il vaut au moins une image avant que le coeur ne parte, et
    l'ecran est monte -- donc visible.
    """
    import asyncio

    from mixed_media_utility.tui.atelier_extraction_ecriture import (
        _lancer_apres_le_dessin)
    from mixed_media_utility.tui.coque import CoqueTui

    Palier = _classe_de_palier()
    depart, progression = Palier("depart"), Palier("progression")
    app = CoqueTui(paliers=[depart])
    mesure = {}

    async def tour():
        async with app.run_test(size=(80, 24)) as pilote:
            await pilote.pause()
            boite = _compteur_d_images(app)
            app.descendre(progression)
            _lancer_apres_le_dessin(app, _passe_synchrone)
            await pilote.pause()
            mesure["images"] = boite["images"]
            mesure["monte"] = progression.is_mounted

    asyncio.run(tour())

    assert mesure["images"] >= 1, (
        "`_lancer_apres_le_dessin` ne laisse plus la boucle peindre : le geste"
        " que le registre reclame ne repare plus rien")
    assert mesure["monte"] is True


def test_les_touches_frappees_PENDANT_la_passe_arrivent_a_l_ecran_SUIVANT():
    """La seconde moitie de la phrase d'Egan, et la plus couteuse.

    « toutes les touches tapees pendant l'attente se resolvent a la sortie ».
    Elles ne sont donc **pas perdues** : elles sont delivrees a un AUTRE ecran
    que celui qui etait affiche quand l'operateur a frappe. Une touche a le
    sens de l'ecran ou elle atterrit -- `Echap` sur un ecran de progression
    interrompt, `Echap` sur un compte rendu remonte. C'est une action non
    voulue, pas un silence, et c'est ce qui contredit la dette du 2026-09-05
    quand elle disait « il n'y a ni perte ni faute ».

    Les touches sont postees depuis un FIL, pendant que la boucle est occupee :
    c'est le seul moyen de reproduire une frappe reelle, l'unique fil de la
    boucle etant justement celui qui bloque.
    """
    import asyncio
    import threading

    from textual import events

    from mixed_media_utility.tui.coque import CoqueTui

    Palier = _classe_de_palier()
    depart = Palier("depart")
    progression, suivant = Palier("progression"), Palier("compte rendu")
    app = CoqueTui(paliers=[depart])
    mesure = {}

    async def tour():
        async with app.run_test(size=(80, 24)) as pilote:
            await pilote.pause()
            app.descendre(progression)

            horodatage = {}

            def frappe():
                time.sleep(DUREE_DE_LA_PASSE / 3)
                horodatage["poste"] = time.monotonic()
                app.post_message(events.Key("tab", None))
                app.post_message(events.Key("escape", None))

            fil = threading.Thread(target=frappe)
            fil.start()
            _passe_synchrone()
            horodatage["fin_de_passe"] = time.monotonic()
            fil.join()
            mesure["pendant"] = list(progression.touches)
            mesure["frappe_pendant_la_passe"] = (
                horodatage["poste"] < horodatage["fin_de_passe"])

            # La passe conclut : l'ecran de progression cede la place.
            app.pop_screen()
            app.descendre(suivant)
            await pilote.pause()
            await pilote.pause()
            mesure["progression"] = list(progression.touches)
            mesure["suivant"] = list(suivant.touches)

    asyncio.run(tour())

    assert mesure["frappe_pendant_la_passe"], (
        "les touches ont ete postees APRES la fin de la passe : le banc ne"
        " mesure plus une frappe pendant le gel, mais une frappe apres lui --"
        " ce qui est un tout autre regime et un tout autre verdict")
    assert mesure["pendant"] == [], (
        "une touche a ete traitee pendant la passe : la boucle tourne, et la"
        " mesure de gel de ce banc ne tient plus")
    assert mesure["progression"] == [], (
        "l'ecran de progression a fini par recevoir les touches : le defaut"
        f" mesure a change de nature ({mesure['progression']})")
    assert mesure["suivant"] == ["tab", "escape"], (
        "les touches ne se resolvent plus sur l'ecran suivant :"
        f" {mesure['suivant']}. Si elles sont PERDUES, c'est un autre defaut"
        " -- et la dette du 2026-09-05 est a rouvrir dans l'autre sens")


# --------------------------------------------------------------------------
# Volet 5b -- L'AUTRE BOUT. Un ecran de progression qu'aucun chemin ne monte
# est un defaut que le volet 1 ne peut pas voir : il n'y a alors rien a
# dessiner trop tard. C'est le cas de `EcranSuppressionEnCours`.
# --------------------------------------------------------------------------

#: Les ecrans de progression qui sont de vraies CLASSES du paquet.
#: `_classe_de_l_ecran_de_passe` n'en est pas une -- c'est la fabrique par
#: laquelle `atelier_scan_calibrate` construit la sienne --, et la chercher
#: parmi les `class ...` ne rendrait jamais rien.
ECRANS_ECRITS = ECRANS_DE_PROGRESSION - {"_classe_de_l_ecran_de_passe"}


def ecrans_definis(racine: Path | None = None) -> dict[str, str]:
    """`{classe: module}` pour chaque ecran de progression DEFINI."""
    dossier = TUI if racine is None else racine
    definis = {}
    for chemin in sorted(dossier.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, ast.ClassDef) and n.name in ECRANS_ECRITS:
                definis[n.name] = chemin.name
    return definis


def ecrans_construits(racine: Path | None = None) -> dict[str, set[str]]:
    """`{classe: {modules qui l'appellent}}`, definition exclue.

    Un `class X(Base)` n'est pas un appel : seule une CONSTRUCTION compte, et
    c'est voulu. Une classe qu'on definit sans jamais l'instancier ne montre
    rien a l'operateur, quelle que soit la qualite de son `compose`.
    """
    dossier = TUI if racine is None else racine
    construits: dict[str, set[str]] = {}
    for chemin in sorted(dossier.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call) and nom_appele(n) in ECRANS_ECRITS:
                construits.setdefault(nom_appele(n), set()).add(chemin.name)
    return construits


def ecrans_orphelins(racine: Path | None = None) -> set[str]:
    """Les ecrans de progression ecrits que RIEN ne construit."""
    return set(ecrans_definis(racine)) - set(ecrans_construits(racine))


def test_aucun_ecran_de_progression_ORPHELIN_hors_du_registre():
    """Un ecran ecrit et jamais monte est du travail invisible a l'operateur.

    Ce volet attrape ce que le volet 1 ne peut pas voir. `suite_de_la_suppression`
    ne monte AUCUN ecran de progression : elle appelle le coeur puis empile son
    compte rendu. Le detecteur de lanceurs la trouve donc hors perimetre, a
    juste titre -- et pourtant `EcranSuppressionEnCours` existe, complet, dans
    le meme module. C'est le defaut par l'autre bout.
    """
    surplus = sorted(ecrans_orphelins() - set(REGISTRE_DES_ECRANS_ORPHELINS))
    assert not surplus, (
        "ces ecrans de progression sont ecrits mais construits NULLE PART --"
        " l'operateur ne les verra jamais :\n"
        + "\n".join(f"    {e}" for e in surplus))


def test_le_registre_des_ORPHELINS_ne_porte_aucune_ligne_morte():
    """Un ecran enfin monte doit SORTIR du registre -- ce rouge est une bonne
    nouvelle, et le message le dit pour qu'on ne cherche pas un defaut."""
    mortes = sorted(set(REGISTRE_DES_ECRANS_ORPHELINS) - ecrans_orphelins())
    assert not mortes, (
        "ces ecrans sont desormais montes par un chemin de production --"
        " retirer leur ligne du registre :\n"
        + "\n".join(f"    {e}" for e in mortes))


def test_le_registre_des_ORPHELINS_est_exactement_la_mesure():
    """Les deux sens ensemble, et la definition existe encore.

    Le second assert n'est pas redondant : un orphelin dont on SUPPRIMERAIT la
    classe sortirait de la mesure par le mauvais bout, et les deux tests
    ci-dessus resteraient verts sans que le produit ait gagne un ecran.
    """
    assert ecrans_orphelins() == set(REGISTRE_DES_ECRANS_ORPHELINS)
    definis = ecrans_definis()
    for orphelin in REGISTRE_DES_ECRANS_ORPHELINS:
        assert orphelin in definis, (
            f"{orphelin} n'est plus defini nulle part : ce n'est pas une"
            " reparation, c'est une disparition")


def test_les_ecrans_de_progression_MONTES_le_sont_encore():
    """La contrepartie : la mesure ne doit pas tout declarer orphelin.

    Sans elle, un balayage des constructions qui rendrait vide ferait passer
    les sept ecrans pour des orphelins, dont un seul est au registre -- donc
    le volet rougirait, mais pour la mauvaise raison, et on chercherait six
    defauts qui n'existent pas.
    """
    construits = ecrans_construits()
    montes = set(ecrans_definis()) & set(construits)
    assert len(montes) >= 5, f"plus que {len(montes)} ecrans construits"
    for ecran in sorted(montes):
        assert construits[ecran], f"{ecran} sans module constructeur"


#: Corpus de synthese pour le volet 5b. **Six** modules, et la forme est
#: contrainte par une mesure : ce volet a DEUX balayages -- les definitions et
#: les constructions --, et une troncature d'un cran doit se voir aux deux
#: bords de CHACUN. Le corpus a cinq modules de la premiere redaction ne
#: portait aucune construction en queue, et le mutant qui sautait la derniere
#: entree du balayage des constructions y **survivait**.
#:
#: La repartition, chaque nom d'ecran servant une fois :
#:
#:   a_bord.py    definit un ORPHELIN (tete des definitions)
#:                ET construit l'ecran de b (tete des constructions)
#:   b_defini.py  definit un ecran monte par a, et par personne d'autre
#:   c_orphelin.py definit un ORPHELIN (milieu)
#:   d_monte.py   definit et construit le sien -- le cas nominal
#:   e_defini.py  definit un ecran monte par f, et par personne d'autre
#:   f_bord.py    definit un ORPHELIN (queue des definitions)
#:                ET construit l'ecran de e (queue des constructions)
CORPUS_DES_ORPHELINS = {
    "a_bord.py": (
        "class EcranMireEnCours(Ecran):\n    pass\n\n"
        "def ouvrir(app):\n"
        "    app.descendre(EcranExecution())\n"),
    "b_defini.py": "class EcranExecution(Ecran):\n    pass\n",
    "c_orphelin.py": "class EcranEcritureDuScan(Ecran):\n    pass\n",
    "d_monte.py": (
        "class EcranEncodageEnCours(Ecran):\n    pass\n\n"
        "def ouvrir(app):\n"
        "    app.descendre(EcranEncodageEnCours())\n"),
    "e_defini.py": "class EcranGenerationDesPlanches(Ecran):\n    pass\n",
    "f_bord.py": (
        "class EcranSuppressionEnCours(Ecran):\n    pass\n\n"
        "def ouvrir(app):\n"
        "    app.descendre(EcranGenerationDesPlanches())\n"),
}

ORPHELINS_DU_CORPUS = {"EcranMireEnCours", "EcranEcritureDuScan",
                       "EcranSuppressionEnCours"}


def _monte_le_corpus_des_orphelins(tmp_path: Path) -> Path:
    dossier = tmp_path / "orphelins"
    dossier.mkdir()
    for nom, corps in CORPUS_DES_ORPHELINS.items():
        (dossier / nom).write_text(corps, encoding="utf-8")
    return dossier


def test_le_detecteur_d_ORPHELINS_releve_les_TROIS_BORDS(tmp_path):
    """Point 4 de la regle des fabriques, applique au second detecteur."""
    dossier = _monte_le_corpus_des_orphelins(tmp_path)
    mesure = ecrans_orphelins(dossier)
    assert mesure == ORPHELINS_DU_CORPUS
    assert "EcranMireEnCours" in mesure, "tete sautee"
    assert "EcranEcritureDuScan" in mesure, "milieu saute"
    assert "EcranSuppressionEnCours" in mesure, "queue sautee"


def test_le_corpus_des_orphelins_porte_ses_SIX_modules_DISTINGUABLES(tmp_path):
    """La partition, sans laquelle « trois orphelins » ne voudrait rien dire.

    Six modules, six ecrans differents, trois roles differents -- orphelin
    seul, defini-monte-ailleurs, defini-et-monte-chez-lui. Un remplissage
    uniforme rendrait toute permutation invisible (regle des fabriques,
    point 1).
    """
    dossier = _monte_le_corpus_des_orphelins(tmp_path)
    definis = ecrans_definis(dossier)
    construits = ecrans_construits(dossier)
    assert len(definis) == 6
    assert len(set(definis.values())) == 6, "deux ecrans dans le meme module"
    assert sorted(construits) == ["EcranEncodageEnCours",
                                  "EcranExecution",
                                  "EcranGenerationDesPlanches"]
    assert definis["EcranExecution"] == "b_defini.py"
    assert construits["EcranExecution"] == {"a_bord.py"}
    assert construits["EcranGenerationDesPlanches"] == {"f_bord.py"}


def test_une_TRONCATURE_du_balayage_des_DEFINITIONS_se_voit_aux_DEUX_BORDS(tmp_path):
    """Retirer le premier module, puis le dernier : les deux font bouger la mesure.

    Et le sens compte : retirer un module qui MONTE un ecran cree un orphelin
    au lieu d'en retirer un. Les deux directions sont mesurees, sinon un
    detecteur qui rendrait toujours l'ensemble des classes passerait.
    """
    dossier = _monte_le_corpus_des_orphelins(tmp_path)
    entier = ecrans_orphelins(dossier)

    (dossier / "a_bord.py").unlink()
    # Retirer `a` retire son orphelin ET la seule construction de l'ecran de
    # `b` : les deux mouvements se voient, et dans les deux sens.
    assert entier - ecrans_orphelins(dossier) == {"EcranMireEnCours"}
    assert ecrans_orphelins(dossier) - entier == {"EcranExecution"}

    (dossier / "a_bord.py").write_text(
        CORPUS_DES_ORPHELINS["a_bord.py"], encoding="utf-8")
    (dossier / "c_orphelin.py").unlink()
    assert entier - ecrans_orphelins(dossier) == {"EcranEcritureDuScan"}

    (dossier / "c_orphelin.py").write_text(
        CORPUS_DES_ORPHELINS["c_orphelin.py"], encoding="utf-8")
    (dossier / "f_bord.py").unlink()
    assert entier - ecrans_orphelins(dossier) == {"EcranSuppressionEnCours"}
    assert ecrans_orphelins(dossier) - entier == {"EcranGenerationDesPlanches"}


def test_une_TRONCATURE_du_balayage_des_CONSTRUCTIONS_se_voit_aux_DEUX_BORDS(tmp_path):
    """Le second balayage, mesure a part -- et il ne l'etait pas.

    `ecrans_construits` a son propre parcours de fichiers, donc sa propre
    troncature possible, et les deux bords en portent une construction :
    l'ecran de `b` n'est monte que par le PREMIER module, celui de `e` que par
    le DERNIER. Sauter l'un ou l'autre cran fabrique un orphelin.
    """
    dossier = _monte_le_corpus_des_orphelins(tmp_path)
    construits = ecrans_construits(dossier)

    par_tete = {e for e, m in construits.items() if m == {"a_bord.py"}}
    par_queue = {e for e, m in construits.items() if m == {"f_bord.py"}}
    assert par_tete == {"EcranExecution"}
    assert par_queue == {"EcranGenerationDesPlanches"}

    # Le meme fait, dit par la mesure d'orphelins : chaque bord retire fait
    # apparaitre exactement un orphelin de plus.
    entier = ecrans_orphelins(dossier)
    (dossier / "a_bord.py").write_text(
        "class EcranMireEnCours(Ecran):\n    pass\n", encoding="utf-8")
    assert ecrans_orphelins(dossier) - entier == {"EcranExecution"}

    (dossier / "a_bord.py").write_text(
        CORPUS_DES_ORPHELINS["a_bord.py"], encoding="utf-8")
    (dossier / "f_bord.py").write_text(
        "class EcranSuppressionEnCours(Ecran):\n    pass\n", encoding="utf-8")
    assert ecrans_orphelins(dossier) - entier == {"EcranGenerationDesPlanches"}


def test_une_DEFINITION_seule_ne_vaut_pas_montage(tmp_path):
    """Le point de doctrine du volet, isole pour etre mutable.

    Un detecteur qui compterait `class X(Base)` comme un usage acquitterait
    exactement `EcranSuppressionEnCours` -- qui est defini, complet, et monte
    par rien. C'est le mutant que ce test tue.
    """
    dossier = tmp_path / "un_seul"
    dossier.mkdir()
    (dossier / "m.py").write_text(
        "class EcranMireEnCours(Ecran):\n    pass\n\n"
        "class Derivee(EcranMireEnCours):\n    pass\n", encoding="utf-8")
    assert ecrans_orphelins(dossier) == {"EcranMireEnCours"}


# --------------------------------------------------------------------------
# Volet 5c -- LE JALON REPASSE PAR LA BOUCLE. Une passe au fil ne suffit pas :
# le coeur ecrit ses jalons DEPUIS le fil, et l'ecran qui s'y rafraichit mute
# l'arbre de widgets hors de la boucle. `textual` ne signale rien.
# --------------------------------------------------------------------------


def test_un_jalon_emis_DEPUIS_UN_FIL_rafraichit_l_ecran_SUR_LA_BOUCLE():
    """Le defaut que la reparation des chemins Scan a introduit, et sa garde.

    **Mesure du 2026-09-06, dans les deux sens.** Avant la garde : trois jalons
    sur trois rafraichissaient l'ecran depuis le fil de travail. Apres : toutes
    les mutations passent par la boucle. C'est le meme defaut que
    `atelier_scan_parcours.lancer_la_passe_de_calibration` reglait chez lui --
    « le fil de travail n'appelle **jamais** un ecran directement » --, remonte
    dans `EcranExecution` pour qu'un atelier qui partirait au fil demain ne
    puisse pas oublier de le reposer.

    Le banc mesure le fil ou `rafraichir` s'execute, et non celui ou `sur_jalon`
    est appele : c'est `rafraichir` qui touche les widgets, et la garde le
    redirige justement sans deplacer `sur_jalon`. La distinction a ete payee --
    une premiere sonde mesurait `sur_jalon` et annoncait le defaut toujours
    ouvert alors qu'il etait ferme.
    """
    import asyncio
    import threading

    from mixed_media_utility.tui.coque import CoqueTui
    from mixed_media_utility.tui.execution import EcranExecution, SurfaceExecution

    Palier = _classe_de_palier()
    app = CoqueTui(paliers=[Palier("depart")])
    mesure: dict = {"fils_de_rafraichir": []}
    surface = SurfaceExecution(unite="frames")

    class EcranTemoin(EcranExecution):
        def rafraichir(self) -> None:
            mesure["fils_de_rafraichir"].append(threading.get_ident())

    ecran = EcranTemoin(surface, titre_tache="temoin")

    def coeur() -> None:
        """Le coeur, au fil : il ecrit ses jalons comme le vrai."""
        for fait in (1, 2, 3):
            surface.noter(fait, 3)

    async def tour():
        async with app.run_test(size=(80, 24)) as pilote:
            await pilote.pause()
            app.descendre(ecran)
            await pilote.pause()
            mesure["boucle"] = app._thread_id
            mesure["au_montage"] = len(mesure["fils_de_rafraichir"])
            ouvrier = app.run_worker(coeur, thread=True, name="temoin")
            for _ in range(60):
                await pilote.pause()
                if ouvrier.is_finished:
                    break
            await pilote.pause()

    asyncio.run(tour())

    depuis_le_jalon = mesure["fils_de_rafraichir"][mesure["au_montage"]:]
    assert depuis_le_jalon, (
        "aucun rafraichissement n'a suivi les jalons : le banc ne mesure rien"
        " -- l'abonnement de `EcranExecution.on_mount` a peut-etre disparu")
    hors_boucle = [f for f in depuis_le_jalon if f != mesure["boucle"]]
    assert not hors_boucle, (
        f"{len(hors_boucle)} rafraichissement(s) sur {len(depuis_le_jalon)}"
        " mutent l'arbre de widgets HORS de la boucle d'evenements.\n"
        "Le geste : `EcranExecution.sur_jalon` repasse par"
        " `app.call_from_thread` des qu'il est appele depuis un fil. `textual`"
        " ne signale rien quand on l'oublie -- l'ecran se met a jour la"
        " plupart du temps, et ce qui casse casse au hasard.")


def test_le_jalon_emis_SUR_LA_BOUCLE_n_appelle_PAS_call_from_thread():
    """Le symetrique, et il n'est pas decoratif : `call_from_thread` LEVE.

    Une garde qui appellerait `call_from_thread` inconditionnellement ferait
    lever tous les ateliers restes synchrones -- `textual` refuse
    explicitement cet appel depuis le fil de l'application. Le test fait donc
    varier le drapeau dont la garde depend, dans les deux sens, ce que la
    regle des gardes du depot exige.
    """
    import asyncio
    import threading

    from mixed_media_utility.tui.coque import CoqueTui
    from mixed_media_utility.tui.execution import EcranExecution, SurfaceExecution

    Palier = _classe_de_palier()
    app = CoqueTui(paliers=[Palier("depart")])
    mesure: dict = {"fils": [], "appels_a_call_from_thread": 0}
    surface = SurfaceExecution(unite="frames")

    class EcranTemoin(EcranExecution):
        def rafraichir(self) -> None:
            mesure["fils"].append(threading.get_ident())

    ecran = EcranTemoin(surface, titre_tache="temoin")

    async def tour():
        async with app.run_test(size=(80, 24)) as pilote:
            await pilote.pause()
            app.descendre(ecran)
            await pilote.pause()
            mesure["boucle"] = app._thread_id
            vrai = app.call_from_thread

            def compte(*args, **kwargs):
                mesure["appels_a_call_from_thread"] += 1
                return vrai(*args, **kwargs)

            app.call_from_thread = compte
            avant = len(mesure["fils"])
            # Le jalon est emis ICI, sur la boucle : c'est le regime des
            # ateliers qui n'ont pas encore de fil.
            surface.noter(1, 3)
            await pilote.pause()
            mesure["depuis_la_boucle"] = mesure["fils"][avant:]

    asyncio.run(tour())

    assert mesure["depuis_la_boucle"] == [mesure["boucle"]], (
        "un jalon emis sur la boucle doit rafraichir sur la boucle, sans"
        f" detour : {mesure['depuis_la_boucle']}")
    assert mesure["appels_a_call_from_thread"] == 0, (
        "la garde a appele `call_from_thread` depuis le fil de l'application :"
        " `textual` leve un `RuntimeError` dans ce cas, et tous les ateliers"
        " restes synchrones tomberaient")
