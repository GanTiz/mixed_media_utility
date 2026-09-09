# -*- coding: utf-8 -*-
"""Le compte des cibles fines se MESURE, il ne se recopie pas en prose.

**Le defaut que ce banc ferme, et il a ete paye.** Le 2026-09-07, le lot qui
a ajoute `frames_extraites` -- la cinquieme cible fine de
`remove_project_element` -- a laisse SIX phrases du depot annoncer « les
quatre cibles fines ». Aucune frontiere ne les voyait : le code etait juste,
la prose fausse, et les deux etaient commites ensemble. C'est exactement la
forme de derive que `CLAUDE.md` decrit de ses propres politiques -- « ce qui
se mesure se tient ; ce qui se rappelle se perd » --, appliquee cette fois a
un cardinal de code.

Un cardinal en prose est une redite de ce que le code sait deja. Il ne se
supprime pas pour autant : il porte le SENS qu'une liste de tuples ne porte
pas. Il se **confronte**.

**Ce que ce banc NE mesure pas, dit plutot que tu.** Il ne sait pas
reconnaitre qu'une phrase neuve *est* un compte : elle doit dire « N cibles
fines » dans ces mots-la. Une phrase qui ecrirait « planche, master, scan et
lot scanne » en toutes lettres lui reste invisible. Il attrape la derive de
cardinal, pas la derive d'enumeration.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "src" / "mixed_media_utility"

#: Le seul endroit du depot ou l'ensemble des cibles fines est ecrit en clair :
#: la comprehension `cibles_fines = [...]` de `remove_project_element`, qui
#: sert la garde « une seule cible fine a la fois » et celle du `lot_id`.
#: Le compte se lit LA, jamais dans un commentaire.
MODULE_DU_COMPTE = SOURCE / "project_maintenance.py"

#: Les mots par lesquels une prose francaise ecrit un petit cardinal. On ne
#: mesure que ceux-la : au-dela, un cardinal ne s'ecrit plus en lettres.
CARDINAUX = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
             "sept": 7, "huit": 8, "neuf": 9, "dix": 10}

_MOTIF_DE_CITATION = re.compile(
    r"\b(" + "|".join(CARDINAUX) + r")\s+cibles\s+fines", re.IGNORECASE)

#: Les citations HISTORIQUES : elles ne comptent pas l'ensemble courant, elles
#: nomment ce qu'un arbitrage donne a AJOUTE. Elles sont legitimes et elles
#: doivent le rester -- retirer le compte d'origine ferait perdre ce que
#: l'arbitrage a change. La forme est donc imposee plutot qu'interdite : le
#: mot `AJOUTEES`, en capitales, dans la meme phrase.
#:
#: **Pourquoi une FORME et non un registre de sites.** Un registre par chemin
#: et par ligne se perime au premier deplacement de fonction, et sa mise a
#: jour est le geste meme qu'on ne fait pas. Une forme voyage avec la phrase.
MARQUEUR_HISTORIQUE = "AJOUTEES"


def _compte_mesure_dans_le_code() -> int:
    """Le cardinal des cibles fines, lu de l'arbre syntaxique du module.

    On lit la comprehension plutot que de compter les parametres de
    `remove_project_element` : ses parametres portent aussi `lot_id`,
    `version`, `dry_run` et les trois consentements, qui ne sont pas des
    cibles. La comprehension, elle, ne porte QUE les cibles -- c'est ce qui en
    fait la source unique.
    """
    arbre = ast.parse(MODULE_DU_COMPTE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Assign)
                and any(isinstance(c, ast.Name) and c.id == "cibles_fines"
                        for c in noeud.targets)):
            continue
        if not isinstance(noeud.value, ast.ListComp):
            continue
        for generateur in noeud.value.generators:
            if isinstance(generateur.iter, ast.Tuple):
                return len(generateur.iter.elts)
    raise AssertionError(
        "la comprehension `cibles_fines = [... for ... in (<tuples>)]` est "
        f"introuvable dans {MODULE_DU_COMPTE.name} : ce banc mesurait le "
        "compte a partir d'elle, et il ne mesure plus rien.")


def _citations() -> list[tuple[str, int, str, str]]:
    """Chaque « N cibles fines » du paquet, avec son fichier, sa ligne, sa phrase."""
    trouvees: list[tuple[str, int, str, str]] = []
    for chemin in sorted(SOURCE.rglob("*.py")):
        for numero, ligne in enumerate(
                chemin.read_text(encoding="utf-8").splitlines(), start=1):
            for correspondance in _MOTIF_DE_CITATION.finditer(ligne):
                trouvees.append((
                    str(chemin.relative_to(RACINE)), numero,
                    correspondance.group(1).lower(), ligne.strip()))
    return trouvees


# ===========================================================================
# Le volet POSITIF : le code porte bien un compte lisible
# ===========================================================================

def test_le_compte_des_cibles_fines_se_LIT_du_code():
    """Sans cette lecture, les deux volets suivants ne mesureraient rien.

    Anti-vacuite : un banc qui compare une prose a un compte introuvable
    passerait vert en ne comparant rien.
    """
    compte = _compte_mesure_dans_le_code()
    assert compte >= 2, (
        f"{compte} cible(s) fine(s) mesuree(s) : une garde « une seule cible "
        "fine a la fois » n'a de sens qu'a partir de deux.")


def test_il_EXISTE_des_citations_en_prose_a_confronter():
    """Anti-vacuite du volet suivant : s'il n'y a plus une seule phrase a
    confronter, ce banc est devenu decoratif et doit le dire lui-meme."""
    citations = _citations()
    assert len(citations) >= 3, (
        f"{len(citations)} citation(s) « N cibles fines » dans le paquet. "
        "Le banc qui les confronte ne mesure plus grand-chose ; verifier que "
        "le motif de reconnaissance n'a pas ete distance par une reformulation.")


# ===========================================================================
# Le volet qui MORD : toute citation courante dit le compte mesure
# ===========================================================================

def test_toute_citation_NON_HISTORIQUE_dit_le_compte_MESURE():
    """Le rouge du 2026-09-07, tenu pour qu'il ne revienne pas.

    Une phrase qui annonce « les quatre cibles fines » pendant que le code en
    porte cinq n'est pas une coquille : c'est une consigne fausse, et le
    lecteur qui la suit ecrit un cinquieme chemin en croyant en couvrir
    quatre.
    """
    compte = _compte_mesure_dans_le_code()
    fautives = [
        f"  {fichier}:{numero} annonce « {mot} » : {phrase}"
        for fichier, numero, mot, phrase in _citations()
        if MARQUEUR_HISTORIQUE not in phrase and CARDINAUX[mot] != compte
    ]
    assert fautives == [], (
        f"le code porte {compte} cibles fines ; ces phrases en annoncent un "
        "autre nombre sans se declarer historiques :\n" + "\n".join(fautives)
        + f"\n\nLe geste : corriger le cardinal, ou -- si la phrase raconte ce "
        f"qu'un arbitrage a ajoute a l'epoque -- ecrire « {MARQUEUR_HISTORIQUE} » "
        "dans la meme phrase, ce qui la declare historique.")


# ===========================================================================
# Le volet SYMETRIQUE : la sortie historique n'avale que l'histoire
# ===========================================================================

def test_le_marqueur_HISTORIQUE_ne_couvre_QUE_des_comptes_PERIMES():
    """Sans ce volet, `AJOUTEES` deviendrait le mot magique qui eteint la garde.

    Une citation historique qui vaudrait le compte courant n'est pas
    historique : c'est une citation ordinaire qu'on a exemptee pour rien, et
    l'exemption survivra au jour ou le compte changera -- rendant la phrase
    fausse et muette a la fois.
    """
    compte = _compte_mesure_dans_le_code()
    inutiles = [
        f"  {fichier}:{numero} : {phrase}"
        for fichier, numero, mot, phrase in _citations()
        if MARQUEUR_HISTORIQUE in phrase and CARDINAUX[mot] == compte
    ]
    assert inutiles == [], (
        f"ces phrases se declarent historiques alors qu'elles annoncent le "
        f"compte COURANT ({compte}) :\n" + "\n".join(inutiles)
        + f"\n\nRetirer « {MARQUEUR_HISTORIQUE} » : l'exemption ne sert a rien "
        "aujourd'hui et masquera la derive demain.")


def test_toute_citation_HISTORIQUE_nomme_l_arbitrage_qui_l_explique():
    """Un compte perime sans son motif est indiscernable d'une faute.

    Le lecteur doit pouvoir aller lire POURQUOI ce nombre-la a ete vrai. Sans
    la reference, `AJOUTEES` n'est qu'un moyen de faire taire la frontiere.
    """
    sans_motif = [
        f"  {fichier}:{numero} : {phrase}"
        for fichier, numero, _mot, phrase in _citations()
        if MARQUEUR_HISTORIQUE in phrase
        and not re.search(r"EPIC\d+-ARB-\d+", phrase)
    ]
    assert sans_motif == [], (
        "ces phrases se declarent historiques sans nommer l'arbitrage qui "
        "explique leur compte :\n" + "\n".join(sans_motif))


def test_le_MOTIF_de_reconnaissance_attrape_bien_les_deux_formes():
    """Frontiere du banc sur lui-meme : le motif doit voir la prose reelle.

    Une regexp trop etroite rendrait les trois volets ci-dessus verts en ne
    trouvant rien. On la confronte donc a des phrases fabriquees, dont
    certaines DOIVENT etre refusees -- une garde qui n'accepte que des cas
    positifs ne mesure qu'une moitie.
    """
    acceptees = ("les quatre cibles fines se lisent",
                 "le CONTEXTE des cinq cibles fines (`EPIC11-ARB-224`)",
                 "Les trois  cibles\tfines qu'un arbitrage a AJOUTEES")
    refusees = ("les cibles fines du lot",              # aucun cardinal
                "les quatre cibles du lot",             # pas « fines »
                "quatre cibles, fines ou non",          # ponctuation entre
                "les 4 cibles fines",                   # chiffre, pas un mot
                "les quatre lignes fines")              # autre nom
    for phrase in acceptees:
        assert _MOTIF_DE_CITATION.search(phrase), f"non reconnue : {phrase!r}"
    for phrase in refusees:
        assert not _MOTIF_DE_CITATION.search(phrase), f"avalee a tort : {phrase!r}"
