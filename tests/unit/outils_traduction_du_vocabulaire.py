# -*- coding: utf-8 -*-
"""Story 11.14, lot E1 -- traduire un releve GELE dans les mots d'aujourd'hui.

**Ce module n'est pas un banc.** C'est le noyau que partagent les dossiers
d'identite : `makepdf` ici, et demain `encode` et `scan`, qui portent
aujourd'hui chacun leur propre redaction du meme mecanisme.

Pourquoi il existe, et pourquoi ici plutot qu'une troisieme fois dans un banc :
`CLAUDE.md` dit qu'« une regle ecrite a deux endroits diverge », et le depot
l'a paye en propre sur ce sujet meme -- deux redactions du calcul de rang, deux
gestes de composition de chemin. Le lot C a ecrit ce mecanisme dans
`test_identite_du_scan.py` ; le lot E1 devait le transposer sur `makepdf`. Le
transposer **par recopie** en aurait fait la deuxieme redaction, et le dossier
d'`encode` la troisieme. Ce module est donc la redaction unique, et les tables
de traduction restent chez chaque banc : **le mecanisme est commun, les
cardinaux ne le sont pas.** Un cardinal est une mesure du fichier gele qui le
porte ; le mutualiser rendrait vrai un compte qui ne l'est que d'un cote.

## Ce qu'une reference d'identite EST, et ce qu'elle n'est pas

Ce n'est **pas** un fichier d'or. C'est le releve joue sous le `src/` d'un
commit donne, sur des entrees octet pour octet identiques : **le regenerer
rendrait exactement les memes octets**, puisque le commit ne bouge pas. Le
geste correct devant un renommage de dossier n'est donc pas la regeneration --
elle ne changerait rien -- mais la **traduction de la reference**, segment de
chemin par segment de chemin, avec cardinal exact.

## La regle qui ne se voit pas a la relecture

`EPIC11-ARB-221` gele les **cles** de document (`frames_dir`,
`output_frames_dir`, `reconstructions`) et ne renomme que les **chemins**.
Or les releves d'identite sont des arbres `chemin relatif -> condensat` : le
nom du dossier vit donc dans les **cles** autant que dans les valeurs, et une
traduction qui ne porterait que sur les feuilles laisserait chaque fichier
renomme diverger deux fois -- absent d'un cote, present de l'autre.

D'ou le drapeau `sur_les_cles` porte par chaque ligne de table : il dit,
ligne par ligne, si la substitution a le droit de toucher une cle. La ligne du
dossier NU (`"frames"` sans slash, valeur d'`artifacts.frames_dir` dans les
documents aplatis) ne l'a **pas** : sa forme est exactement celle d'une cle de
manifeste, et l'y appliquer renommerait la cle que l'arbitrage gele.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

#: Une ligne de table de traduction, dans l'ordre ou les bancs la parametrent.
#: Ecrit ici pour que les trois bancs ne se disputent pas l'ordre des colonnes.
#:
#: * `retire` -- le nom d'avant, en clair, pour les messages d'echec ;
#: * `motif` -- le motif applique a une chaine STRUCTURELLE (cle ou valeur) ;
#: * `brut` -- le motif applique au TEXTE du fichier de reference. Il sert au
#:   volet symetrique : si les deux comptes divergent, une occurrence n'est pas
#:   un segment de chemin et la traduction la laisse passer en silence ;
#: * `neuf` -- le nom d'aujourd'hui ;
#: * `sur_les_cles` -- `EPIC11-ARB-221`, voir le docstring du module ;
#: * `cardinal` -- le compte EXACT, mesure sur le fichier gele ;
#: * `avant` / `apres` -- un exemplaire et sa traduction, ecrits dans la table
#:   plutot que derives du motif : les temoins de bord doivent fabriquer une
#:   cible que CETTE ligne-la reconnait, et une cible derivee du motif par
#:   inspection serait un second lieu ou la regle vivrait -- c'est-a-dire un
#:   temoin tautologique, defaut mesure sur le lot D3 le 2026-09-03.
COLONNES = (
    "retire", "motif", "brut", "neuf", "sur_les_cles", "cardinal",
    "avant", "apres",
)


def compiler(table: Iterable[tuple]) -> tuple:
    """Precompiler une table de traduction en triplets prets a l'emploi."""
    return tuple(
        (ligne[0], re.compile(ligne[1]), ligne[3], ligne[4]) for ligne in table
    )


def traduire_un_texte(
    texte: str, traductions: tuple, compteur: dict, *, cle: bool = False
) -> str:
    """Appliquer les traductions a un texte, en comptant **chacune a part**.

    Comptees separement : un cardinal global serait juste alors qu'une des
    traductions serait morte et une autre deux fois trop large. C'est le mode
    de panne exact que le lot B a mesure sur son propre releve -- 147 avant,
    147 apres, une ambiguite neuve ayant remplace deux retirees.

    `cle=True` restreint aux traductions declarees valables sur les cles
    (`EPIC11-ARB-221`).
    """
    for retire, motif, neuf, sur_les_cles in traductions:
        if cle and not sur_les_cles:
            continue
        texte, mordu = motif.subn(neuf, texte)
        compteur[retire] = compteur.get(retire, 0) + mordu
    return texte


def traduire(valeur: Any, traductions: tuple, compteur: dict) -> Any:
    """Rendre un releve gele dans les mots d'aujourd'hui, en profondeur.

    Le compteur est rendu **par la bande** plutot que devine : un banc qui ne
    saurait pas combien de fois il a substitue ne saurait pas non plus quand il
    a cesse de le faire.
    """
    if isinstance(valeur, dict):
        return {
            traduire_un_texte(str(cle), traductions, compteur, cle=True):
                traduire(sous, traductions, compteur)
            for cle, sous in valeur.items()
        }
    if isinstance(valeur, list):
        return [traduire(sous, traductions, compteur) for sous in valeur]
    if isinstance(valeur, str):
        return traduire_un_texte(valeur, traductions, compteur)
    return valeur


#: Cinq valeurs **distinguables** -- pas un remplissage uniforme : une
#: permutation ou une troncature du parcours ne se voit pas autrement (regle
#: des fabriques, points 1 et 4 de `CLAUDE.md`). Elles sont ECRITES et non
#: derivees d'une sortie du parcours : un corpus calcule depuis ce qu'on mesure
#: deplace le bord au lieu de le perdre, et le temoin reste vert.
VALEURS_TEMOINS = (
    "scans/lot-a",
    "outputs",
    "12 frames extraites dans <PROJET>",
    "planches/mire.pdf",
    "versions/calibration",
)

#: Cinq cles d'arbre, distinguables pour le meme motif. Un arbre d'artefacts
#: est un `chemin relatif -> condensat` : c'est la que vit le nom du dossier.
ARBRE_TEMOIN = (
    "scans/lot-a/page-01.tiff",
    "versions/calibration/alpha.json",
    "logs/makepdf.log",
    "outputs/rush-ident_5_mmu.mov",
    "planches/mire.pdf",
)

#: Cinq LIGNES de journal, distinguables. Les listes sont la troisieme
#: structure du parcours, et la seule qu'aucun temoin ne traversait avant le
#: 2026-09-04 : un mutant qui remplacait la descente dans les listes par un
#: `list(valeur)` a **survecu** a la campagne du lot E1, sur 111 tests verts.
#:
#: Il etait invisible aux deux references de `makepdf` -- mesure : **zero** de
#: leurs 195 occurrences ne vit dans une liste -- mais `stdout` et `stderr`
#: d'un releve SONT des listes, et un message qui nommerait le dossier y
#: tomberait. C'est exactement « le collecteur, pas seulement l'appariement » :
#: un temoin qui ne traverse pas la structure ne mesure pas le parcours qui
#: l'alimente.
LIGNES_TEMOINS = (
    "planche ecrite dans planches/",
    "12 image(s) retenue(s)",
    "genere le 2026-09-04",
    "rang consomme : 2",
    "journal : logs/makepdf.log",
)

#: Les positions ou une cible est posee : **tete, milieu et queue**. Le point 4
#: de la regle des fabriques (2026-09-03) : « la cible au milieu demasque un
#: `find` fautif ; elle ne demasque pas un balayage tronque ». Un parcours qui
#: sauterait la premiere ou la derniere entree d'un document resterait vert sur
#: une cible au milieu.
POSITIONS_DE_BORD = (0, 2, 4)
