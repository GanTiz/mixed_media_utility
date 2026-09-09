"""Frontiere : un litteral RECOPIE d'une maquette se confronte a sa SOURCE.

**Ce que ce banc ferme, et pourquoi une frontiere plutot que des corrections.**
Le 2026-09-06, quatre bancs du parcours Scan citaient une maquette nommement,
parfois jusqu'au numero de ligne, sans jamais ouvrir le dessin : chaque valeur
y avait ete recopiee a la main. Ils ont ete confrontes un a un
(`test_confrontation_maquettes_scan_profond.py`). Ca ne suffit pas : le geste
juste etait deja pratique **juste a cote** -- `test_atelier_scan_rapport.py`
lit `E3-3` et `E3-4` a leur source -- et le defaut est quand meme revenu quatre
fois. Ce qui manque au depot n'est pas une liste de corrections, c'est la
PROPRIETE, mesuree :

    un banc qui asserte un litteral dessine dans une maquette
    le confronte a sa source.

**Comment la propriete se boucle, et pourquoi un banc SEPARE est legitime.**
Le banc d'origine mesure `rendu == litteral` ; celui-ci mesure
`litteral ∈ dessin`, le dessin etant relu sur disque a chaque tour. Les deux
composes donnent `rendu ∈ dessin`, qui est ce que la propriete demande. Un
litteral confronte ici n'a donc pas besoin de l'etre a nouveau chez lui -- ce
qui evite d'editer vingt bancs que d'autres agents travaillent en parallele.

**Ce que "lire sa source" veut dire, et la mesure qui a corrige la premiere
version de ce banc.** Le premier critere retenu etait la presence du mot
`maquettes` **quelque part** dans le fichier. Il est trop permissif, et de
beaucoup : mesure a la commande, **dix** bancs portent ce mot en prose seule
-- docstring ou commentaire -- sans jamais ouvrir un dessin, et les **deux
plus gros recopieurs du depot** sont parmi eux (`test_ecrans_execution.py`,
24 litteraux ; `test_versionnage_du_pdf_en_tui.py`, 19). L'un d'eux annonce
meme une constante « epinglee sur le litteral des cinq maquettes, verbatim »
sans lire aucune des cinq. Le critere tenu ici est donc : un litteral de CODE
porte le chemin des maquettes. La premiere mesure annoncait 15 bancs et 36
litteraux ; la stricte en donne 20 et 94, mesures sur l'arbre du 2026-09-06
a 03:20. La fusion du tronc, quelques minutes plus tard, en a ajoute 42 --
voir plus bas.

**Le 40e banc n'a pas attendu la semaine prochaine : il en est arrive CINQ en
une heure.** Ce banc a ete ecrit sur un arbre mesure a 03:20 -- 20 bancs,
94 litteraux -- puis le tronc a ete fusionne. La frontiere a rougi
immediatement, sur **42 litteraux de plus** venus de cinq bancs livres dans la
nuit par d'autres lots :

    test_ecran_projet_inventaire.py    E6-1, E6-1a, E6-1c, E6-1d, E6-1e   19
    test_suppression_depuis_la_tui.py  E6-2, E6-2b, E6-2c, E6-3b          11
    test_versions_de_lot_tui.py        E2-1j, E2-3, T4-2                   6
    test_ecrans_de_conflit.py          E4-3b, E5-3b, E5-3c                 3
    test_suites_de_la_suppression.py   E6-3, E6-3b                         3

plus un litteral qui a CHANGE dans un banc deja au registre
(`test_ecran_E2_1f_refus_de_conflit.py`, `plan séquence 12.mov` devenu
`hd\\plan séquence 12.mov`). Aucun de ces auteurs n'a mal travaille : ils ont
fait ce que tout le depot fait depuis des mois, faute d'une frontiere qui le
dise. C'est exactement l'argument qui justifiait d'ecrire une propriete plutot
que de corriger 39 bancs un a un -- et il s'est verifie en moins d'une heure.
Registre porte a 25 bancs et 136 litteraux, tous confrontes -- puis **vide**,
par sept vagues de reduction. Vingt-cinq bancs y sont passes cette nuit -- ils
lisent desormais leurs dessins a leur source. Avec le lot
`montee-de-tous-les-ecrans`, pris en huitieme vague le jour meme, cela porte a
**65** le nombre de bancs lecteurs du dossier, sur 114 :

    test_ecrans_execution.py             24    test_versionnage_du_pdf_en_tui.py  19
    test_ecran_E2_1f_refus_de_conflit.py  8    test_atelier_scan_resultat.py       7
    test_atelier_pdf_calibration.py       6    test_lots_m_n_previz_et_refus.py    4
    test_atelier_extraction_ecriture.py   4    test_atelier_pdf_parcours.py        3
    test_atelier_scan_calibrate_tui.py    3    test_aide_de_champ.py               3
    test_ecrans_de_conflit.py             3    test_atelier_scan_depot.py          2
    test_atelier_scan_detection_tui.py    2    test_ecran_vivant.py                2
    test_atelier_scan_ecriture.py         1    test_ecran_ateliers.py              1
    test_fermeture_vague_B_tui.py         1    test_lot_k1_ajout_et_previz.py      1
    test_manuel_derive.py                 1    test_noms_editables.py              1
    test_versions_de_lot_tui.py           1    test_navigation_du_formulaire…py    1
    test_ecran_projet_inventaire.py      21    test_suppression_depuis_la_tui.py  13
    test_suites_de_la_suppression.py      3

C'est le mouvement voulu, et il est alle a son terme : **le registre est
VIDE**. 136 litteraux le 2026-09-06 a 03:20, zero a 06:00.

**Et il a tenu son premier choc a zero dans la demi-heure.** La fusion du lot
`montee-de-tous-les-ecrans`, quelques minutes plus tard, a fait rougir la
frontiere sur **neuf** couples venus d'un seul banc neuf -- dont l'en-tete
annoncait « ce banc ne recopie AUCUN litteral de maquette [...] il n'y en a
pas un seul ». C'est exactement ce que cette frontiere existe pour dire, et
elle l'a dit contre une declaration ecrite de bonne foi : trois des quatre
textes etaient des entrees de FABRIQUE, ce qui rendait la phrase plausible et
n'empechait pas la geometrie d'etre mesuree sur un libelle recopie de memoire.
Huitieme vague, banc converti, registre revenu a zero.

**Les trois derniers bancs n'ont pas ete difficiles, ils etaient INTERDITS.**
`test_ecran_projet_inventaire.py` (21), `test_suppression_depuis_la_tui.py`
(13) et `test_suites_de_la_suppression.py` (3) appartenaient a des lots que
d'autres agents tenaient la meme nuit ; la consigne de decoupage interdisait
de les ouvrir, et ils sont restes au registre -- lus et confrontes depuis ici,
jamais edites -- tant que l'interdit tenait. Leurs lots clos et fusionnes,
l'interdit est tombe et la septieme vague les a pris. Ce que le registre a
porte pendant ces heures, c'est exactement ce pour quoi il existe : nommer un
banc qui ne lit pas encore sa source, en tenant sa valeur pendant ce temps.

**A ZERO, une frontiere se retourne : le danger n'est plus la recopie, c'est
la CECITE.** Un registre vide passe le volet 1 sans rien dire, et il le
passerait tout autant si le dossier des maquettes avait bouge, si le glob ne
rendait plus rien, ou si le detecteur avait ete casse par une refonte. Le
volet 1 porte donc, depuis le 2026-09-06, une mesure qui distingue les deux :
**on rend chaque banc lecteur AVEUGLE** -- sa source privee du chemin des
maquettes, en memoire, jamais sur disque -- **et on mesure qu'il se denonce
alors**. Mesure du jour, prise APRES le vidage du registre et la fusion du
tronc : 65 lecteurs, **58 se denoncent une fois aveugles, pour 413
litteraux**. Le zero vient donc de la LECTURE, pas d'un detecteur
qui ne detecte plus rien. C'est le temoin de morsure de la regle des
fabriques, applique a la frontiere entiere plutot qu'a une collection.

**La vague 4 a rendu une mesure que les trois premieres n'avaient pas
produite : une appartenance VRAIE dont la conclusion est FAUSSE.** Le litteral
`scan requis` de `test_aide_de_champ.py` est bien dans `E3-9` -- et il n'en
est pas recopie : `E3-9` ne dessine aucune ligne `Valider`, et le litteral n'y
est present que comme prefixe de la ligne d'etat `résolution de scan requise`.
La confrontation ecrite la-bas le NOMME au lieu de faire semblant, en mesurant
que retirer la ligne d'etat fait disparaitre le litteral. C'est la limite « la
confrontation est une SOUS-CHAINE » ci-dessous, prise sur le fait plutot que
seulement declaree.

**Ce que ce banc NE mesure pas, dit plutot que tu.**

* un litteral de moins de `LONGUEUR_UTILE` codepoints, ou sans espace, est
  hors perimetre : `"Q"`, `"oui"`, `"186"` apparaissent dans trop de dessins
  pour qu'une appartenance y veuille dire quelque chose ;
* l'appartenance est une SOUS-CHAINE du dessin replie. Elle attrape donc des
  coincidences : `" bits · "`, `" frames · "` et `"la passe "` sont au
  registre sans avoir forcement ete recopies. Les confronter ne coute rien et
  ne ment pas -- ils SONT dans le dessin aujourd'hui ;
* elle ne dit rien d'un litteral construit par concatenation ou par f-string :
  le fragment se voit, la ligne assemblee non. Neuf lignes du registre sont
  dans ce cas -- `'lot scanné — '`, `'tout le lot '` -- et elles restent, car
  le fragment y EST bien recopie : c'est la ligne rendue qui echappe, pas la
  valeur. En revanche le fragment d'un message d'`assert` a ete SORTI du
  perimetre le 2026-09-06, mesure a l'appui : un message ne se compare a rien,
  donc il ne peut pas porter de valeur recopiee (voir `litteraux_de_code`) ;
* elle ne remonte pas la filiation d'une constante de MODULE. Un banc qui
  asserte `module.TITRE` sans jamais ecrire le texte est invisible ici -- et
  c'est bien ainsi, c'est au module d'etre confronte, ce que fait
  `test_confrontation_maquettes_scan_profond.py`.

**Le registre est le lieu ou la mesure a bouge, pas une tolerance muette.**
Il est vide aujourd'hui, et il le reste tant que personne ne recopie ; le jour
ou une ligne y revient, elle est confrontee a son dessin par le volet 2 avant
d'etre toleree. Une ligne au registre n'excuse donc rien : elle nomme un banc
qui ne lit pas encore sa source, pendant que la valeur, elle, est tenue.

**Et le volet 2 ne devient pas du code mort a zero.** Une confrontation qui
n'est jouee que quand le registre est plein serait cassee sans qu'on le sache,
et rendrait la premiere ligne revenue verte a tort. Elle est donc jouee a
chaque tour sur des dessins REELS pris du dossier -- tete, milieu et queue --
plutot que sur le seul registre.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
BANCS = RACINE / "tests" / "unit" / "tui"
MAQUETTES = (
    RACINE
    / "_bmad-output"
    / "planning-artifacts"
    / "ux-designs"
    / "ux-tui-2026-08-27"
    / "maquettes"
)

#: Les caracteres de cadre d'un dessin. Ils separent des colonnes, ils ne font
#: pas partie du texte : un litteral n'a aucune raison de les porter.
CADRE = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Une maquette est coupee ici : ce qui suit est de la prose d'accompagnement,
#: pas le dessin. Meme separateur que `test_confrontation_maquettes_scan_profond`.
SEPARATEUR_DE_NOTE = "\nNOTE"

#: En deca, l'appartenance a un dessin ne veut rien dire (voir l'en-tete).
LONGUEUR_UTILE = 8

#: Le code d'ecran tel que les bancs le citent : `E3-8`, `E2-1b`, `E5-6c`.
CODE_D_ECRAN = re.compile(r"\bE\d+-\d+[a-z]?\b")

#: La marque qu'un banc ouvre bien un dessin : le nom du dossier, dans un
#: litteral de CODE. En prose, il ne prouve rien -- c'est la mesure de
#: l'en-tete.
MARQUE_DE_LECTURE = "maquettes"


# --------------------------------------------------------------------------
# Les gestes elementaires, isoles pour etre mesurables un a un.
# --------------------------------------------------------------------------


def replie(texte: str) -> str:
    """Ramene un texte a sa forme comparable : espaces normalises.

    Un dessin aligne ses colonnes a coups d'espaces ; un litteral de banc en
    porte le nombre qu'il veut. Comparer sans replier ferait rougir sur de la
    mise en page.
    """
    return " ".join(texte.split())


def corps_du_dessin(chemin: Path) -> str:
    """Le dessin seul, cadre retire et prose d'accompagnement coupee."""
    brut = chemin.read_text(encoding="utf-8").split(SEPARATEUR_DE_NOTE)[0]
    return replie("".join(" " if c in CADRE else c for c in brut))


def dessin_de(code: str) -> str | None:
    """Le dessin du code d'ecran, lu a SA SOURCE. `None` s'il n'existe pas.

    Deux fichiers pour un meme code seraient une ambiguite : le banc REFUSE
    plutot que d'en trancher un par un tri muet. Un tri muet a survecu a la
    campagne (mutant `R11`) parce qu'aucun code n'est ambigu aujourd'hui --
    c'est-a-dire qu'il ne mesurait rien.
    """
    candidats = sorted(MAQUETTES.glob(f"{code}-*.txt"))
    if not candidats:
        return None
    if len(candidats) > 1:
        raise AssertionError(
            f"{code} designe {len(candidats)} maquettes : "
            + ", ".join(c.name for c in candidats)
        )
    return corps_du_dessin(candidats[0])


def _docstrings(arbre: ast.AST) -> set[str]:
    """Les docstrings de module, de classe et de fonction de l'arbre."""
    trouvees = set()
    for noeud in ast.walk(arbre):
        if isinstance(
            noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            texte = ast.get_docstring(noeud, clean=False)
            if texte is not None:
                trouvees.add(texte)
    return trouvees


def _dans_un_message_d_assertion(arbre: ast.AST) -> set[ast.Constant]:
    """Les noeuds de chaine qui vivent dans le MESSAGE d'un `assert`.

    Ce sont des noeuds, pas des textes : le meme texte peut etre a la fois une
    valeur comparee ici et une prose de message la, et seule la premiere
    compte.
    """
    dedans = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assert) and noeud.msg is not None:
            for fils in ast.walk(noeud.msg):
                if isinstance(fils, ast.Constant) and isinstance(fils.value, str):
                    dedans.add(fils)
    return dedans


def litteraux_de_code(source: str) -> list[str]:
    """Les litteraux de chaine du CODE : ni docstring, ni message d'assertion.

    Citer `E5-3` dans une docstring SITUE une scene -- ce n'est pas un defaut,
    et c'est meme utile. Le defaut est d'ASSERTER une valeur recopiee. Les
    commentaires n'apparaissent pas dans un arbre `ast`, donc ils sont exclus
    par construction ; les docstrings, si, et il faut les retirer.

    **Le message d'un `assert` est exclu pour la meme raison, et la mesure qui
    l'a impose est datee du 2026-09-06.** La frontiere retenait
    `('test_fermeture_vague_B_tui.py', 'E3-9', 'la passe ')` : le fragment
    constant de `f"la passe {rang + 1} doit monter son ecran d'execution"`,
    qui est la PROSE d'un message d'echec. `E3-9` dessine bien « la passe du
    12/08 — même chaîne », si bien que l'appartenance etait vraie et la
    conclusion fausse. Un message ne se compare a rien : il ne peut donc pas
    porter une valeur recopiee, et l'y chercher ne rend que du bruit. La
    propriete que ce banc tient parle d'un litteral **asserte** -- l'exclusion
    la rend litterale au lieu d'approximative.

    L'exclusion se fait par NOEUD, pas par texte : un meme texte compare dans
    un test et repete dans le message d'un autre reste mesure, parce que sa
    premiere occurrence, elle, est bien une valeur.
    """
    arbre = ast.parse(source)
    docs = _docstrings(arbre)
    proses = _dans_un_message_d_assertion(arbre)
    return [
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and noeud.value not in docs
        and noeud not in proses
    ]


def lit_ses_sources(source: str) -> bool:
    """Le banc ouvre-t-il un dessin ? Vrai si un litteral de CODE le nomme."""
    return any(MARQUE_DE_LECTURE in texte for texte in litteraux_de_code(source))


def codes_cites(source: str) -> list[str]:
    """Les codes d'ecran que le banc cite, ou qu'ils soient dans le fichier."""
    return sorted(set(CODE_D_ECRAN.findall(source)))


def recopies(source: str, dessins: dict[str, str]) -> set[tuple[str, str]]:
    """Les couples (code, litteral) que le banc a recopies d'un des dessins.

    Un litteral trop court ou sans espace est hors perimetre -- l'en-tete dit
    pourquoi. Il n'y a PAS de garde sur le litteral qui porte le chemin des
    maquettes : la campagne a montre qu'il ne mesurait rien (mutant `R8`, seul
    survivant de sa famille), un tel litteral etant deja ecarte deux fois --
    le banc qui le porte est exempte en amont, et un chemin n'a pas d'espace.
    """
    trouves = set()
    for texte in litteraux_de_code(source):
        if len(texte) < LONGUEUR_UTILE:
            continue
        if " " not in texte.strip():
            continue
        court = replie(texte)
        if not court:
            continue
        for code, dessin in dessins.items():
            if court in dessin:
                trouves.add((code, texte))
    return trouves


def bancs_du_dossier() -> list[Path]:
    """Tous les bancs du dossier, tries. Le balayage part de LA."""
    return sorted(BANCS.glob("test_*.py"))


def recopies_d_un_banc(source: str) -> set[tuple[str, str]]:
    """Ce qu'UN banc recopie, a partir de sa seule source.

    Factorisee hors de `releve_par_banc` le 2026-09-06, pour que la mesure de
    cecite du volet 1 emprunte exactement le meme chemin que le balayage : un
    detecteur qu'on prouve vivant par un chemin different de celui qu'on
    emploie ne prouve rien.
    """
    if lit_ses_sources(source):
        return set()
    dessins = {}
    for code in codes_cites(source):
        dessin = dessin_de(code)
        if dessin is not None:
            dessins[code] = dessin
    # Pas de garde `if dessins` : `recopies(source, {})` rend deja l'ensemble
    # vide, sa boucle interne ne s'executant pas. La garde qui etait ecrite la
    # a SURVECU a la campagne du 2026-09-06 (mutant `Z3`) parce qu'elle etait
    # equivalente -- une branche qui ne change rien est une surface qui ne
    # mesure rien, et elle se retire plutot qu'elle ne se tolere.
    return recopies(source, dessins)


def aveugle(source: str) -> str:
    """La MEME source, privee du chemin des maquettes -- EN MEMOIRE seulement.

    Aucun fichier n'est touche : c'est le texte lu qui est ampute, le temps
    d'une mesure. C'est le temoin de morsure de la frontiere a zero, decrit
    dans l'en-tete.
    """
    return source.replace(MARQUE_DE_LECTURE, "dessins__")


def confronte(
    registre: list[tuple[str, str, str]],
    dessins: dict[str, str] | None = None,
) -> list[tuple[str, str, str]]:
    """Les lignes du registre dont le litteral n'est PAS (ou plus) dessine.

    Un seul lieu pour la confrontation, deux appelants : le volet 2 la joue
    sur `REGISTRE`, le volet 4 sur un registre de synthese dont les cibles
    sont en tete, au milieu et en queue. Sans ce partage, la confrontation
    serait du code mort tant que le registre est vide -- et la premiere ligne
    revenue serait verte a tort.
    """
    fautives = []
    for banc, code, litteral in registre:
        dessin = dessin_de(code) if dessins is None else dessins.get(code)
        if dessin is None or replie(litteral) not in dessin:
            fautives.append((banc, code, litteral))
    return fautives


def releve_par_banc() -> dict[str, set[tuple[str, str]]]:
    """Ce que CHAQUE banc du dossier recopie sans avoir lu sa source.

    Un banc sans recopie garde une entree VIDE plutot que d'etre absent.
    C'est ce qui rend le balayage OBSERVABLE : une troncature d'un cran fait
    disparaitre une cle, donc elle se voit, alors qu'elle survivait quand le
    releve n'etait qu'un ensemble de triplets (mutant `R9` -- le dernier
    fichier du dossier n'est pas un recopieur, donc le sauter ne changeait
    rien). C'est le point 4 de la regle des fabriques, applique au balayage
    plutot qu'a une collection de donnees.
    """
    return {
        banc.name: recopies_d_un_banc(banc.read_text(encoding="utf-8"))
        for banc in bancs_du_dossier()
    }


def mesure_de_l_arbre() -> set[tuple[str, str, str]]:
    """Les triplets (banc, code, litteral) recopies SANS lecture de la source.

    C'est la mesure que le registre ci-dessous epingle.
    """
    return {
        (banc, code, texte)
        for banc, couples in releve_par_banc().items()
        for code, texte in couples
    }


# --------------------------------------------------------------------------
# Le registre des exceptions, exhaustif et mesure -- pas une liste tenue a la
# main. Chaque ligne nomme un banc qui asserte une valeur RECOPIEE sans ouvrir
# le dessin dont elle vient. Elle n'excuse rien : la valeur est confrontee plus
# bas. Le registre a vocation a DECROITRE ; il ne doit jamais croitre.
# --------------------------------------------------------------------------

#: (banc, code d ecran, litteral recopie), trie. **VIDE depuis le 2026-09-06 :
#: plus un seul banc du dossier n'asserte un litteral dessine sans ouvrir son
#: dessin.** Le type reste annote pour qu'une ligne qui revient s'ecrive sans
#: reflexion, et le volet 1 mesure que ce vide est une PROPRIETE de l'arbre et
#: non une cecite du detecteur.
REGISTRE: list[tuple[str, str, str]] = []


# --------------------------------------------------------------------------
# Volet 1 -- LA FRONTIERE. Aucune recopie hors registre.
# --------------------------------------------------------------------------


def test_aucune_recopie_de_maquette_hors_du_registre():
    """Le 95e litteral recopie sans lecture de sa source fait rougir ICI.

    C'est la seule direction qui protege le depot. Elle est stricte : un banc
    neuf qui recopie une valeur dessinee sans ouvrir le dessin est un defaut,
    quel que soit le soin mis a la recopier.
    """
    surplus = sorted(mesure_de_l_arbre() - set(REGISTRE))
    assert not surplus, (
        "des litteraux dessines sont assertes sans que leur dessin soit lu :\n"
        + "\n".join(f"    {b} :: {c} :: {t!r}" for b, c, t in surplus)
        + "\n\nLe geste : ouvrir la maquette dans le banc et comparer au dessin"
        " lu, comme le fait test_atelier_scan_rapport.py."
    )


def test_le_registre_ne_porte_aucune_ligne_morte():
    """Une ligne du registre sans contrepartie dans l'arbre fait rougir aussi.

    Ce rouge-la n'est PAS une regression : il dit qu'un banc a ete corrige et
    que le registre ne l'a pas suivi. Le message le nomme, pour qu'on retire
    la ligne au lieu de chercher un defaut qui n'existe plus.
    """
    mortes = sorted(set(REGISTRE) - mesure_de_l_arbre())
    assert not mortes, (
        "ces lignes sont a RETIRER du registre -- la recopie a disparu, ce"
        " n'est pas une regression :\n"
        + "\n".join(f"    {b} :: {c} :: {t!r}" for b, c, t in mortes)
    )


def test_le_registre_est_exactement_la_mesure():
    """Les deux sens ensemble, pour que l'egalite ne tienne pas par vacuite.

    Les deux tests ci-dessus se lisent chacun dans un sens ; celui-ci epingle
    le cardinal, qui est ce qu'un rapport cite.
    """
    releve = mesure_de_l_arbre()
    assert releve == set(REGISTRE)
    assert len(REGISTRE) == len(set(REGISTRE)), "le registre porte un doublon"
    assert len(releve) == len(REGISTRE)


def test_le_registre_est_trie():
    """Un registre trie se relit et se diff ; un registre en vrac, non."""
    assert REGISTRE == sorted(REGISTRE)


def test_le_registre_est_A_ZERO():
    """L'etat atteint le 2026-09-06, epingle en valeur plutot qu'en prose.

    Ce n'est pas une redite des trois tests ci-dessus : eux mesurent une
    EGALITE entre deux ensembles, qui tiendrait tout aussi bien a 12 lignes de
    chaque cote. Celui-ci dit lequel des deux etats l'arbre est cense etre. Le
    jour ou une ligne revient, il rougit en NOMMANT la regression, la ou
    l'egalite, elle, resterait verte apres qu'on ait ajoute la ligne au
    registre.
    """
    assert REGISTRE == [], (
        "le registre n'est plus vide -- une recopie a ete toleree :\n"
        + "\n".join(f"    {b} :: {c} :: {t!r}" for b, c, t in REGISTRE)
    )
    assert mesure_de_l_arbre() == set()


def test_le_ZERO_est_une_PROPRIETE_de_l_arbre_et_non_une_CECITE():
    """Le temoin de morsure de la frontiere entiere : on AVEUGLE les lecteurs.

    A registre plein, un detecteur casse se voyait -- les 136 lignes seraient
    devenues des lignes mortes. A zero, il ne se voit plus : un glob qui ne
    rend rien, un dossier deplace, une refonte de `recopies` qui avale tout,
    et le volet 1 reste vert en ne mesurant PLUS RIEN. C'est le mode de panne
    propre a une frontiere qui a fini son travail.

    La mesure qui l'ecarte : chaque banc lecteur voit sa source privee du
    chemin des maquettes -- en memoire, jamais sur disque -- et doit alors se
    denoncer. Mesure du 2026-09-06, prise APRES le vidage du registre et la
    fusion du tronc : 65 lecteurs, **58 se denoncent, pour 413 litteraux**.
    Les sept qui ne se denoncent pas ne sont pas un defaut : ils
    lisent un dessin sans en asserter de litteral confrontable (constantes de
    module, litteraux trop courts).

    Les bornes sont des PLANCHERS larges et non les valeurs exactes : l'arbre
    bouge sous plusieurs agents, et un banc de moins ne doit pas rougir ici
    alors que la propriete tient. Ce qui est mesure, c'est que le detecteur
    mord encore FORT, pas qu'il morde exactement 58 fois.
    """
    lecteurs = [
        chemin
        for chemin in bancs_du_dossier()
        if lit_ses_sources(chemin.read_text(encoding="utf-8"))
    ]
    assert len(lecteurs) >= 40, f"seulement {len(lecteurs)} bancs lecteurs"

    denonces: list[str] = []
    litteraux = 0
    for chemin in lecteurs:
        source = aveugle(chemin.read_text(encoding="utf-8"))
        assert lit_ses_sources(source) is False, (
            f"{chemin.name} reste exempte une fois aveugle : l'amputation ne"
            " porte pas, la mesure ne vaut rien"
        )
        trouves = recopies_d_un_banc(source)
        if trouves:
            denonces.append(chemin.name)
            litteraux += len(trouves)

    assert len(denonces) >= 40, (
        f"seuls {len(denonces)} bancs se denoncent une fois aveugles : le"
        " detecteur ne mord plus, et le zero du registre ne veut plus rien"
        " dire"
    )
    assert litteraux >= 200, f"seulement {litteraux} litteraux retrouves"


def test_le_DOSSIER_des_maquettes_est_ATTEINT_et_ses_dessins_sont_LISIBLES():
    """L'autre cecite : un dossier vide rend la frontiere verte pour rien.

    `dessin_de` rend `None` sur un code sans fichier, et `recopies_d_un_banc`
    rend alors l'ensemble vide sans un mot. Un dossier deplace, renomme ou non
    descendu ferait donc passer le volet 1 avec zero -- exactement comme un
    arbre propre. Trois dessins reels, pris en tete, au milieu et en queue du
    dossier, sont ouverts et replies ici a chaque tour.
    """
    fichiers = sorted(MAQUETTES.glob("*.txt"))
    assert len(fichiers) >= 50, (
        f"{len(fichiers)} maquettes seulement : le dossier est-il au bon"
        f" endroit ? ({MAQUETTES})"
    )
    for position in (0, len(fichiers) // 2, -1):
        chemin = fichiers[position]
        dessin = corps_du_dessin(chemin)
        assert len(dessin) >= LONGUEUR_UTILE, f"{chemin.name} rend un dessin vide"
        assert not set(dessin) & set(CADRE), f"{chemin.name} garde son cadre"


# --------------------------------------------------------------------------
# Volet 2 -- LA CONFRONTATION. Chaque litteral du registre est dans son dessin.
# --------------------------------------------------------------------------


def test_chaque_litteral_du_registre_appartient_a_son_dessin():
    """Le litteral est dans la maquette, LUE A SA SOURCE a chaque tour.

    C'est ce qui empeche le registre d'etre une tolerance muette : la valeur
    est tenue ici pendant que le banc d'origine ne la tient pas encore. Le
    jour ou le dessin change, ce test rouge NOMME l'ecart -- il ne le redessine
    pas (`EPIC11-ARB-144`).

    **Ecrit en boucle et non en `parametrize` depuis le 2026-09-06, et c'est
    une correction plutot qu'un gout.** Sur un registre vide, `parametrize`
    rend un jeu de parametres vide, que pytest transforme en un SKIP muet :
    le volet 2 disparaissait du rapport sans rien dire. Une boucle, elle, joue
    a chaque tour -- vide aujourd'hui, mais c'est `confronte` qui est
    exercee, et le volet 4 la mesure sur un registre de synthese pour qu'elle
    ne soit pas du code mort.
    """
    fautives = confronte(REGISTRE)
    assert not fautives, (
        "ces litteraux sont dits tires d'un dessin qui ne les porte pas (ou"
        " plus) :\n"
        + "\n".join(f"    {b} :: {c} :: {t!r}" for b, c, t in fautives)
    )


def test_chaque_banc_du_registre_existe_et_cite_son_code():
    """Le registre parle de fichiers reels, pas de souvenirs."""
    for banc, code, _ in REGISTRE:
        chemin = BANCS / banc
        assert chemin.is_file(), f"{banc} n'existe pas"
        assert code in codes_cites(chemin.read_text(encoding="utf-8")), (
            f"{banc} ne cite pas {code}"
        )


def test_chaque_banc_du_registre_porte_bien_son_litteral():
    """Et le litteral est bien dans le CODE du banc, pas dans sa prose."""
    for banc, _, litteral in REGISTRE:
        source = (BANCS / banc).read_text(encoding="utf-8")
        assert litteral in litteraux_de_code(source), (
            f"{banc} ne porte plus {litteral!r} comme litteral de code"
        )


# --------------------------------------------------------------------------
# Volet 3 -- LE DETECTEUR SE MESURE. Sans ca, une frontiere verte ne prouve
# rien : un detecteur qui ne detecte jamais rien passe tous les tests du
# volet 1.
# --------------------------------------------------------------------------

#: Un dessin de synthese, avec son cadre et sa NOTE, tel qu'une maquette en
#: porte. Deux colonnes DISTINGUABLES, pour qu'une confusion se voie.
DESSIN_DE_SYNTHESE = """\
┌──────────────────────────────────────────┐
│  Detection en cours — 3 sur 7            │
│  gauche stricte      │      droite molle │
│  ⏎ valider  Échap retour                 │
└──────────────────────────────────────────┘

NOTE
Cette prose accompagne le dessin, elle n'en fait pas partie.
Le mot exclusif de la note est: pantoufle inattendue ici.
"""


def _source(corps: str) -> str:
    """Un banc de synthese minimal, cite `E9-9` dans son code."""
    return "CODE = 'E9-9'\n" + corps


def test_le_detecteur_attrape_une_recopie(tmp_path):
    """Un litteral recopie du dessin est vu. Sinon le volet 1 est decoratif."""
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    trouves = recopies(_source("assert 'Detection en cours' in rendu\n"), dessins)
    assert trouves == {("E9-9", "Detection en cours")}


def test_le_detecteur_ignore_un_banc_qui_lit_sa_source():
    """Un litteral de CODE portant le chemin exempte le banc, la prose non."""
    lecteur = _source("CHEMIN = 'ux-designs/maquettes/E9-9-synthese.txt'\n")
    prosateur = '"""Le banc suit les maquettes E9-9."""\n' + _source("X = 1\n")
    assert lit_ses_sources(lecteur) is True
    assert lit_ses_sources(prosateur) is False


def test_une_citation_en_prose_ne_compte_pas_comme_recopie(tmp_path):
    """Citer pour SITUER n'est pas un defaut -- c'est meme utile.

    Le meme texte, une fois en docstring et une fois asserte : seul le second
    est releve. C'est la distinction que tout le triage repose dessus.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    en_prose = '"""L\'ecran affiche Detection en cours — 3 sur 7."""\nX = 1\n'
    assert recopies(en_prose, dessins) == set()
    assert recopies(_source("Y = 'Detection en cours'\n"), dessins)


def test_un_MESSAGE_d_assertion_n_est_pas_une_recopie(tmp_path):
    """La prose d'echec cite le dessin sans jamais s'y comparer.

    Le cas reel qui l'a impose : `f"la passe {rang + 1} doit monter son ecran"`
    dans `test_fermeture_vague_B_tui.py`, dont le fragment `la passe ` est
    dessine par `E3-9` (« la passe du 12/08 — même chaîne »). L'appartenance
    etait vraie et la conclusion fausse : un message ne se compare a rien,
    donc il ne peut pas porter une valeur recopiee.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    banc = _source("assert x, 'Detection en cours — 3 sur 7'\n")
    assert recopies(banc, dessins) == set()

    # Le temoin de morsure : la MEME chaine, hors message, est bien relevee.
    # Sans lui, l'exclusion serait indistinguable d'un detecteur casse.
    hors_message = _source("Y = 'Detection en cours — 3 sur 7'\n")
    assert recopies(hors_message, dessins) == {
        ("E9-9", "Detection en cours — 3 sur 7")}


def test_l_exclusion_du_message_porte_sur_le_NOEUD_et_non_sur_le_TEXTE(tmp_path):
    """Un texte compare ICI reste mesure meme s'il est repete en message LA.

    Exclure par texte serait une passoire : il suffirait d'ecrire une fois la
    valeur recopiee dans un message pour la faire disparaitre de partout.
    C'est le mutant que cette mesure tue.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    banc = _source(
        "Y = 'Detection en cours'\n"
        "assert x, 'Detection en cours'\n")
    assert recopies(banc, dessins) == {("E9-9", "Detection en cours")}


def test_un_assert_SANS_message_ne_perd_aucun_litteral(tmp_path):
    """`Assert.msg` vaut `None` la plupart du temps : le balayage doit tenir.

    Une lecture non gardee de `msg` leverait sur tout banc du depot ; une
    garde trop large avalerait la condition elle-meme, qui est le lieu meme
    de la recopie.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    banc = _source("assert rendu == 'Detection en cours'\n")
    assert recopies(banc, dessins) == {("E9-9", "Detection en cours")}

def test_le_detecteur_ne_leve_pas_un_texte_absent_du_dessin(tmp_path):
    """Aucun faux positif : un texte qui n'est pas dessine n'est pas releve."""
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    assert recopies(_source("A = 'Ecriture terminee sans erreur'\n"), dessins) == set()


def test_le_repliement_absorbe_la_mise_en_page_mais_pas_un_ecart(tmp_path):
    """Le pli n'est pas complaisant : il mange les espaces, rien d'autre.

    Quatre contre-exemples : meme texte a l'espacement pres (releve), un
    caractere de plus (ignore), un caractere de moins (ignore), un mot
    permute (ignore).
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    assert recopies(_source("A = 'Detection    en\\n  cours'\n"), dessins)
    assert recopies(_source("A = 'Detection en cours!'\n"), dessins) == set()
    assert recopies(_source("A = 'Detecton en cours'\n"), dessins) == set()
    assert recopies(_source("A = 'en cours Detection'\n"), dessins) == set()


def test_le_cadre_est_retire_avant_la_comparaison(tmp_path):
    """Une valeur a cheval sur un montant du cadre reste comparable.

    Sans le retrait, `gauche stricte droite molle` ne serait jamais trouve --
    le dessin porte un `│` entre les deux colonnes.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessin = corps_du_dessin(chemin)
    assert not set(dessin) & set(CADRE)
    assert "gauche stricte droite molle" in dessin


def test_la_note_ne_fait_pas_partie_du_dessin(tmp_path):
    """Ce qui suit `NOTE` est de la prose : un banc peut la citer librement."""
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    assert "pantoufle" not in dessins["E9-9"]
    assert recopies(_source("A = 'pantoufle inattendue ici'\n"), dessins) == set()


def test_les_litteraux_hors_perimetre_sont_ecartes(tmp_path):
    """Trop court, ou d'un seul mot : hors perimetre, et c'est assume.

    `'valider'` est bien dans le dessin ; il est ecarte parce qu'un mot seul
    appartient a trop de dessins pour que l'appartenance signifie quelque
    chose. La borne est mesuree ici plutot que supposee.
    """
    chemin = tmp_path / "E9-9-synthese.txt"
    chemin.write_text(DESSIN_DE_SYNTHESE, encoding="utf-8")
    dessins = {"E9-9": corps_du_dessin(chemin)}
    assert "valider" in dessins["E9-9"]
    assert recopies(_source("A = 'valider'\n"), dessins) == set()
    assert recopies(_source("A = '3 sur 7'\n"), dessins) == set()
    assert len("3 sur 7") == LONGUEUR_UTILE - 1
    assert recopies(_source("A = '⏎ valider'\n"), dessins)


def test_le_balayage_visite_TOUS_les_bancs_du_dossier():
    """Une troncature d'un cran, en tete ou en queue, fait rougir ICI.

    Le releve porte une entree par banc, VIDE comprise ; le dossier est relu
    independamment. Les deux bords sont nommes en plus du cardinal, parce que
    le cardinal seul ne dit pas LEQUEL manque.
    """
    attendus = sorted(chemin.name for chemin in BANCS.glob("test_*.py"))
    visites = sorted(releve_par_banc())
    assert visites == attendus
    assert visites[0] == attendus[0]
    assert visites[-1] == attendus[-1]
    assert Path(__file__).name in visites


def test_le_balayage_garde_les_bancs_SANS_recopie():
    """L'entree vide est ce qui rend la troncature visible : elle doit exister.

    Sans elle, sauter un banc innocent ne changerait aucun triplet -- c'est
    exactement ce qui a fait survivre `R9`.

    **A zero, ce test ne suffit PLUS a lui seul, et il vaut mieux le dire.**
    Tous les bancs sont desormais vides, donc la partition `vides`/`pleins`
    n'a plus qu'un cote : elle ne distingue plus une entree vide d'une entree
    absente. C'est le corpus de synthese du volet 4 qui porte cette mesure
    depuis le 2026-09-06 -- lui garde des bancs pleins ET des bancs vides,
    par construction, quoi que fasse l'arbre reel.
    """
    releve = releve_par_banc()
    vides = {nom for nom, couples in releve.items() if not couples}
    pleins = {nom for nom, couples in releve.items() if couples}
    assert vides, "aucun banc innocent : le releve ne serait pas observable"
    assert pleins == {banc for banc, _, _ in REGISTRE}
    assert vides & pleins == set()
    assert vides | pleins == set(releve)
    assert pleins == set()
    assert len(vides) == len(releve) >= 100


def test_un_code_ambigu_est_REFUSE_et_non_tranche_en_silence(monkeypatch, tmp_path):
    """Deux dessins pour un code : le banc leve, il n'en choisit pas un.

    Trancher par un tri muet ne mesurait rien tant qu'aucun code n'est ambigu
    -- c'est ce que le mutant `R11` a montre. Le refus, lui, se mesure.
    """
    (tmp_path / "E9-9-premiere.txt").write_text("un dessin\n", encoding="utf-8")
    (tmp_path / "E9-9-seconde.txt").write_text("deux dessins\n", encoding="utf-8")
    (tmp_path / "E8-8-unique.txt").write_text("trois dessins\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "MAQUETTES", tmp_path)
    with pytest.raises(AssertionError, match="E9-9 designe 2 maquettes"):
        dessin_de("E9-9")
    assert dessin_de("E8-8") == "trois dessins"
    assert dessin_de("E7-7") is None


def test_ce_banc_ci_lit_bien_ses_sources():
    """L'auto-exemption se mesure au lieu de se supposer.

    **Et la mesure a change de reponse le 2026-09-06, ce qui vaut mieux que la
    phrase qu'elle remplace.** Tant que le registre etait plein, ce banc
    portait 38 litteraux dessines -- ses propres lignes de registre --, et son
    exemption etait exactement ce qui l'empechait de se denoncer lui-meme. Le
    registre vide, il n'en porte plus AUCUN : rendu aveugle, il reste muet.
    Il ne depend donc plus de son exemption du tout, ce qui est l'etat le plus
    fort qu'un banc puisse atteindre ici -- et c'est la mesure qui l'a dit, en
    faisant rougir un plancher `>= 20` ecrit de memoire quelques minutes plus
    tot.

    L'exemption reste mesuree : elle redeviendra necessaire le jour ou une
    ligne revient au registre.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    assert lit_ses_sources(source) is True
    assert Path(__file__).name not in {banc for banc, _, _ in REGISTRE}
    assert lit_ses_sources(aveugle(source)) is False
    assert recopies_d_un_banc(aveugle(source)) == set()

    # Le zero ci-dessus doit tenir par ABSENCE DE RECOPIE, pas par absence de
    # dessin a comparer : ce banc cite des codes reels, et ils sont dessines.
    reels = [code for code in codes_cites(source) if dessin_de(code) is not None]
    assert len(reels) >= 10, (
        f"ce banc ne cite que {len(reels)} codes reellement dessines : son"
        " silence une fois aveugle ne prouverait plus rien"
    )


# --------------------------------------------------------------------------
# Volet 4 -- LA REGLE DES FABRIQUES, portee par un CORPUS DE SYNTHESE.
#
# Elle portait sur le registre tant qu'il etait plein : tete, milieu et queue
# etaient trois de ses lignes. A zero, un registre vide ne porte plus aucune
# cible, et la regle disparaissait avec lui -- c'est-a-dire au moment ou le
# balayage est le seul a mesurer quelque chose. Elle porte donc desormais sur
# un corpus construit ici, qui garde ses trois cibles quoi que fasse l'arbre
# reel : deux elements distinguables (point 1), une cible ailleurs qu'en
# premiere position (point 2), et une cible a CHAQUE BORD (point 4).
# --------------------------------------------------------------------------

#: Trois dessins DISTINGUABLES : ni le meme texte, ni le meme cardinal, ni le
#: meme objet. Un remplissage uniforme rendrait invisible une permutation.
LIGNES_DU_CORPUS = {
    "E9-1": "Detection en cours — 3 sur 7",
    "E9-2": "Écriture des planches — 2 sur 5",
    "E9-3": "Relecture des masters — 1 sur 9",
}

#: Le corpus, dans l'ordre ou `sorted()` le rend. Les recopieurs sont en TETE,
#: au MILIEU et en QUEUE ; les innocents sont intercales, pour qu'un balayage
#: qui s'arrete a la premiere trouvaille se voie aussi.
CORPUS = [
    ("test_a_tete.py", "E9-1"),
    ("test_b_lecteur.py", None),
    ("test_c_milieu.py", "E9-2"),
    ("test_d_muet.py", None),
    ("test_e_queue.py", "E9-3"),
]


def _monte_le_corpus(monkeypatch, tmp_path):
    """Ecrit les cinq bancs et les trois dessins, puis branche le module.

    `BANCS` et `MAQUETTES` sont relus a chaque appel par `bancs_du_dossier` et
    `dessin_de` : les remplacer suffit a faire tourner tout le balayage sur le
    corpus, sans dupliquer une ligne de sa logique.
    """
    maquettes = tmp_path / "maquettes"
    maquettes.mkdir()
    for code, ligne in LIGNES_DU_CORPUS.items():
        (maquettes / f"{code}-synthese.txt").write_text(
            "┌────────────────────────────────────┐\n"
            f"│  {ligne}  │\n"
            "└────────────────────────────────────┘\n"
            "\nNOTE\nCette prose ne fait pas partie du dessin.\n",
            encoding="utf-8",
        )

    bancs = tmp_path / "bancs"
    bancs.mkdir()
    for nom, code in CORPUS:
        if code is not None:
            corps = f"CODE = {code!r}\nATTENDU = {LIGNES_DU_CORPUS[code]!r}\n"
        elif nom == "test_b_lecteur.py":
            # Lecteur : il recopie AUSSI, et reste exempte parce qu'il lit.
            corps = (
                "CODE = 'E9-1'\n"
                "CHEMIN = 'ux-designs/maquettes/E9-1-synthese.txt'\n"
                f"ATTENDU = {LIGNES_DU_CORPUS['E9-1']!r}\n"
            )
        else:
            # Muet : ni code cite, ni litteral dessine.
            corps = "ATTENDU = 'une phrase qui n est dessinee nulle part'\n"
        (bancs / nom).write_text(corps, encoding="utf-8")

    module = sys.modules[__name__]
    monkeypatch.setattr(module, "BANCS", bancs)
    monkeypatch.setattr(module, "MAQUETTES", maquettes)
    return bancs, maquettes


#: Ce que le corpus DOIT rendre. Ecrit une fois, relu par plusieurs tests.
TRIPLETS_DU_CORPUS = {
    (nom, code, LIGNES_DU_CORPUS[code]) for nom, code in CORPUS if code is not None
}


def test_le_corpus_est_releve_ENTIEREMENT_des_deux_BORDS(monkeypatch, tmp_path):
    """Le balayage complet, sur un corpus dont les cibles sont aux deux bords.

    C'est le point 4 de la regle des fabriques : une cible au milieu demasque
    un appariement fautif, elle ne demasque pas un balayage tronque. Les deux
    bords sont donc nommes en plus de l'egalite, pour que le message dise
    LEQUEL manque plutot que « les ensembles different ».
    """
    _monte_le_corpus(monkeypatch, tmp_path)
    mesure = mesure_de_l_arbre()
    assert mesure == TRIPLETS_DU_CORPUS
    assert ("test_a_tete.py", "E9-1", LIGNES_DU_CORPUS["E9-1"]) in mesure
    assert ("test_c_milieu.py", "E9-2", LIGNES_DU_CORPUS["E9-2"]) in mesure
    assert ("test_e_queue.py", "E9-3", LIGNES_DU_CORPUS["E9-3"]) in mesure


def test_le_corpus_garde_ses_bancs_VIDES_et_ses_bancs_PLEINS(
    monkeypatch, tmp_path
):
    """La partition que l'arbre reel ne porte plus a zero, tenue ici.

    Le lecteur recopie et reste vide parce qu'il LIT ; le muet est vide parce
    qu'il ne recopie rien. Deux raisons differentes d'etre vide, ce qui rend
    la mesure sensible a une exemption trop large comme a une trop etroite.
    """
    _monte_le_corpus(monkeypatch, tmp_path)
    releve = releve_par_banc()
    assert sorted(releve) == [nom for nom, _ in CORPUS]
    vides = {nom for nom, couples in releve.items() if not couples}
    pleins = {nom for nom, couples in releve.items() if couples}
    assert vides == {"test_b_lecteur.py", "test_d_muet.py"}
    assert pleins == {"test_a_tete.py", "test_c_milieu.py", "test_e_queue.py"}


def test_une_TRONCATURE_du_balayage_a_l_un_ou_l_autre_BORD_se_voit(
    monkeypatch, tmp_path
):
    """Retirer le premier banc, puis le dernier : les deux font bouger la mesure.

    C'est la mesure que le registre portait avant d'etre vide, et le mutant
    qui a coute la regle du 2026-09-03 : un balayage qui saute la derniere
    entree restait vert quand toutes les cibles etaient au milieu.
    """
    bancs, _ = _monte_le_corpus(monkeypatch, tmp_path)
    entier = mesure_de_l_arbre()

    (bancs / "test_a_tete.py").unlink()
    sans_tete = mesure_de_l_arbre()
    assert entier - sans_tete == {
        ("test_a_tete.py", "E9-1", LIGNES_DU_CORPUS["E9-1"])
    }

    (bancs / "test_a_tete.py").write_text(
        f"CODE = 'E9-1'\nATTENDU = {LIGNES_DU_CORPUS['E9-1']!r}\n",
        encoding="utf-8",
    )
    (bancs / "test_e_queue.py").unlink()
    sans_queue = mesure_de_l_arbre()
    assert entier - sans_queue == {
        ("test_e_queue.py", "E9-3", LIGNES_DU_CORPUS["E9-3"])
    }


def test_les_trois_cibles_du_corpus_sont_DISTINGUABLES(monkeypatch, tmp_path):
    """Chaque litteral n'appartient qu'a SON dessin -- sinon rien ne se permute.

    Point 1 de la regle des fabriques, mesure plutot que declare : trois
    valeurs uniformes passeraient toutes les autres mesures de ce volet en
    rendant une permutation banc/code invisible.
    """
    _monte_le_corpus(monkeypatch, tmp_path)
    assert len(set(LIGNES_DU_CORPUS.values())) == len(LIGNES_DU_CORPUS)
    for code, ligne in LIGNES_DU_CORPUS.items():
        for autre, dessin in (
            (c, dessin_de(c)) for c in LIGNES_DU_CORPUS
        ):
            assert dessin is not None
            if autre == code:
                assert replie(ligne) in dessin
            else:
                assert replie(ligne) not in dessin


def test_la_CONFRONTATION_nomme_la_ligne_fautive_a_CHAQUE_position(
    monkeypatch, tmp_path
):
    """`confronte` est exercee ICI, tete, milieu et queue -- pas seulement a vide.

    Sans ce test, la confrontation du volet 2 serait du code mort tant que le
    registre est vide, et la premiere ligne qui y reviendrait serait verte a
    tort. Un registre de synthese la joue donc a chaque tour, dans les deux
    sens : trois lignes justes ne rendent rien, et chacune des trois positions
    faussee est nommee -- seule.
    """
    _monte_le_corpus(monkeypatch, tmp_path)
    juste = sorted(TRIPLETS_DU_CORPUS)
    assert len(juste) == 3
    assert confronte(juste) == []

    for position in (0, 1, -1):
        faux = list(juste)
        banc, code, litteral = faux[position]
        faux[position] = (banc, code, litteral + " et une queue de trop")
        assert confronte(faux) == [faux[position]], (
            f"la ligne en position {position} n'est pas nommee seule"
        )

    # DEUX fautives a la fois, aux deux BORDS : toutes sont nommees, pas
    # seulement la premiere. Sans ce cas, `return fautives[:1]` survivait
    # (mutant `Z11` du 2026-09-06) -- et le volet 2 aurait cache tous les
    # ecarts sauf un, ce qui est la panne meme que ce banc existe pour eviter.
    deux = list(juste)
    deux[0] = (deux[0][0], deux[0][1], deux[0][2] + " et une queue de trop")
    deux[-1] = (deux[-1][0], deux[-1][1], deux[-1][2] + " et une autre queue")
    assert confronte(deux) == [deux[0], deux[-1]]

    # Le REPLIEMENT est exerce : un litteral qui ne differe du dessin que par
    # sa mise en page doit etre trouve. Sans ce cas, retirer `replie` de la
    # confrontation ne changeait rien (mutant `Z10`), parce que toutes les
    # cibles de ce banc etaient deja repliees.
    banc, code, litteral = juste[0]
    etale = " \n  ".join(litteral.split())
    assert etale != litteral
    assert confronte([(banc, code, etale)]) == []

    # Et un code sans dessin est fautif plutot qu'ignore en silence : sinon
    # un dossier deplace rendrait toute confrontation verte.
    assert confronte([("test_z.py", "E9-8", "un texte quelconque")]) == [
        ("test_z.py", "E9-8", "un texte quelconque")
    ]


def test_la_CONFRONTATION_tient_sur_des_dessins_REELS_du_dossier():
    """La meme mesure, mais sur le dossier reel -- tete, milieu et queue.

    Une confrontation qui ne serait mesuree que sur des dessins de synthese
    mesurerait la synthese. La regle du depot est de confronter au moins une
    fois l'artefact de terrain : trois maquettes reelles sont ouvertes ici,
    et un fragment PRIS DANS chacune doit etre retrouve -- pendant que le meme
    fragment prolonge d'un caractere absent ne l'est pas.
    """
    fichiers = sorted(MAQUETTES.glob("*.txt"))
    assert len(fichiers) >= 50
    intrus = "ẑ"
    vus = 0
    for position in (0, len(fichiers) // 2, -1):
        dessin = corps_du_dessin(fichiers[position])
        assert intrus not in dessin
        extrait = _fragment_confrontable(dessin)
        assert extrait is not None, f"{fichiers[position].name} n'a aucun fragment"
        banc = "test_synthese.py"
        assert confronte([(banc, "E9-9", extrait)], {"E9-9": dessin}) == []
        assert confronte([(banc, "E9-9", extrait + intrus)], {"E9-9": dessin}) == [
            (banc, "E9-9", extrait + intrus)
        ]
        vus += 1
    assert vus == 3


def _fragment_confrontable(dessin: str) -> str | None:
    """Un fragment REEL du dessin, assez long pour etre dans le perimetre.

    Pris dans le dessin plutot qu'ecrit ici : un fragment recopie a la main
    serait exactement le defaut que ce banc mesure, et il perimerait le jour
    ou la maquette bouge.
    """
    mots = dessin.split()
    for depart in range(len(mots)):
        for fin in range(depart + 2, min(depart + 6, len(mots)) + 1):
            fragment = " ".join(mots[depart:fin])
            if len(fragment) >= LONGUEUR_UTILE:
                return fragment
    return None
