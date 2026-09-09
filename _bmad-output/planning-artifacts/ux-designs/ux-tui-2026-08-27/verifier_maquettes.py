"""Verifie que chaque maquette tient exactement la grille 80x24 du DESIGN.md.

Une maquette de TUI qui ne fait pas 80 colonnes est une maquette fausse: elle
promet une mise en page que le terminal plancher ne rendra pas. Ce script est le
seul juge -- une relecture a l'oeil ne compte pas les colonnes.

Usage: python verifier_maquettes.py [dossier]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

LARGEUR = 80
HAUTEUR = 24

#: Les glyphes est-asiatiques occupent DEUX colonnes dans un terminal: une
#: maquette qui en contient est large de plus de colonnes qu'elle n'a de
#: caracteres. On compte donc en colonnes, pas en caracteres.
def colonnes(texte: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in texte)


#: La ligne de raccourcis est **l'avant-derniere** ligne de la grille : celle
#: qui precede la bordure basse. Elle est verifiee a part parce qu'elle est la
#: seule dont le code porte une CONSTANTE : tout le reste est recompose au
#: rendu, et se re-abrege donc en mode ASCII. Une constante, elle, est repliee
#: TELLE QUELLE.
RANG_DES_RACCOURCIS = HAUTEUR - 1

#: Zone utile a l'interieur des bordures : 80 moins deux bordures et deux
#: marges. C'est ce que `jetons.largeur_utile(80)` rend.
UTILE = 76

#: Ce que le repli ASCII fait GRANDIR. Seules ces substitutions comptent ici :
#: les autres rendent une largeur egale ou moindre, et une maquette ne peut pas
#: deborder en retrecissant. La table vit dans `tui/jetons.py`
#: (`REPLIS_DE_TEXTE`) ; elle est recopiee ICI plutot qu'importee pour que ce
#: script reste utilisable sans le paquet sur le `PYTHONPATH` -- une garde qui
#: ne tourne que dans un environnement prepare ne tourne jamais.
REPLIS_QUI_ALLONGENT = {"⏎": "Entree", "…": "...", "—": "--"}


#: **LA REGLE DE COLORISATION** (Egan, le 2026-09-02, sur TROIS ecrans a la
#: fois : « la deuxieme ligne de ton avertissement n'est pas colorisee »,
#: « l'avertissement n'est pas colorise [...] colorise en bleu au lieu du
#: orange », « cela devrait donc etre un avertissement orange plutot qu'une
#: validation verte »). Ce n'etaient pas trois retouches, c'etait une regle
#: absente, et elle tient en deux points :
#:
#:   1. **un avertissement se colorise ENTIEREMENT**, jamais une ligne sur
#:      deux -- un avertissement multiligne est un seul objet ;
#:   2. **la teinte suit ce que le message FAIT**, jamais l'habitude : orange
#:      quand il avertit, jamais bleu ; **jamais vert sur un interdit**, le vert
#:      disant « valide » et le poser sur un refus retournant le sens.
#:
#: Les trois frontieres ci-dessous la mesurent. Ecrite en commentaire, elle se
#: serait perdue comme les precedentes ; mesuree, elle tient.
#:
#: Les trois glyphes d'etat et leurs deux motifs de reconnaissance sont recopies
#: ICI plutot qu'importes, pour la meme raison que `REPLIS_QUI_ALLONGENT`
#: ci-dessus : une garde qui ne tourne que dans un environnement prepare ne
#: tourne jamais. La source de verite reste `tui/jetons.py`.
GLYPHES_D_ETAT = {"\u25cf": "complete", "\u25b2": "substitute", "\u2715": "absent"}

#: `jetons._OUVRE_UNE_COLONNE` et `jetons._PORTE_UN_LIBELLE`, verbatim.
_OUVRE_UNE_COLONNE = r"(?:^[ \t]*|[ \t]{2,})"
_PORTE_UN_LIBELLE = r"(?:[ \t](?=[^ \t])|[ \t]*$)"

#: Le meme, elargi a la bordure d'un CARTOUCHE suivie d'un seul blanc. C'est
#: exactement l'ecart entre ce que le repli du produit VOIT et ce qu'une
#: maquette PORTE : `jetons.peindre` documente ce cas comme celui pour lequel
#: son parametre `etats` existe.
_OUVRE_UNE_COLONNE_OU_CARTOUCHE = r"(?:^[ \t]*|[ \t]{2,}|\u2502[ \t])"

#: Le registre des etats DECLARES par les generateurs, ecrit par
#: `construire_maquette.ecrire`. Il est le seul moyen de colorier un glyphe que
#: le repli par motif ne peut pas voir -- dans un cartouche, ou sur la ligne de
#: continuation d'un message.
ETATS_DECLARES = "etats.json"

#: Ce qui fait d'une ligne d'etat un REFUS et non un simple compte. `E3-4b`
#: porte `✕  5 champs sur 6 saisis` -- un formulaire incomplet, pas un interdit,
#: et son point vert « Coherent avec les 3 pages deja lues » est legitime. `E5-3c`
#: porte `✕  Remplacer n'est pas offert` : la, une validation verte a l'ecran
#: dirait le contraire de ce que l'ecran fait.
MOTS_D_INTERDIT = (
    "n'est pas offert", "n'est pas possible", "impossible", "interdit",
    "refuse", "refusé", "ne peut pas", "n'est pas permis",
)

#: Les bornes de la ZONE CENTRALE. Le bandeau, la ligne d'etat et la ligne de
#: raccourcis ont leur propre regle de peinture -- elles sont servies d'un bloc,
#: en `data` ou en `muted` -- et aucune de ces frontieres ne les regarde.
PREMIERE_DU_CENTRE = 3
DERNIERE_DU_CENTRE = HAUTEUR - 3


def etat_devine(ligne: str) -> str | None:
    """Ce que le repli par MOTIF trouverait -- copie de `jetons.jeton_d_etat`."""
    for glyphe, nom in GLYPHES_D_ETAT.items():
        if re.search(_OUVRE_UNE_COLONNE + re.escape(glyphe) + _PORTE_UN_LIBELLE,
                     ligne):
            return nom
    return None


def etat_porte(ligne: str) -> str | None:
    """L'etat que la ligne PORTE en position de colonne, cartouche compris.

    Plus large qu'`etat_devine` d'exactement une alternative -- la bordure de
    cartouche --, et c'est cet ecart-la que la frontiere 1 mesure. Elle n'est
    pas plus large que ca, et c'est deliberer : une prose separe ses mots par UN
    blanc, si bien qu'un `✕` au milieu d'une ligne de JOURNAL -- texte venu du
    coeur, dont aucun ecran ne connait l'etat -- ne serait pas un etat, et
    l'attraper ferait rougir sur ce que le produit ne peint pas non plus.
    """
    interne = ligne[1:-1] if ligne.startswith("\u2502") else ligne
    for glyphe, nom in GLYPHES_D_ETAT.items():
        if re.search(_OUVRE_UNE_COLONNE_OU_CARTOUCHE + re.escape(glyphe)
                     + _PORTE_UN_LIBELLE, interne):
            return nom
    return None


def etat_quelconque(ligne: str) -> str | None:
    """L'etat porte par la ligne, glyphe pris OU QU'IL SOIT.

    Sert seulement a la frontiere 3, pour verifier qu'une declaration ne
    contredit pas le glyphe de sa propre ligne -- y compris quand le generateur
    a colle le glyphe a un chiffre (`( ) 4●`).
    """
    interne = ligne[1:-1] if ligne.startswith("\u2502") else ligne
    for glyphe, nom in GLYPHES_D_ETAT.items():
        rang = interne.find(glyphe)
        if rang < 0:
            continue
        suite = interne[rang + len(glyphe):]
        if not suite.strip() or suite.startswith(" "):
            return nom
    return None


def replie_en_ascii(texte: str) -> str:
    for source, cible in REPLIS_QUI_ALLONGENT.items():
        texte = texte.replace(source, cible)
    return texte


#: Les deux coins qui BORNENT la grille. Ils servent a separer la maquette de
#: ce qui la suit : plusieurs maquettes portent, sous leur cadre, les notes
#: manuscrites d'Egan et la decision qui y repond.
#:
#: **Sans cette separation le script ne mesurait plus rien** : il comptait les
#: lignes de note comme des lignes de grille et rendait 156 defauts sur 58
#: maquettes, dont zero portait sur une grille reellement fausse (mesure du
#: 2026-08-30, lot G de la story 11.4). Un verificateur qui rougit toujours ne
#: dit plus si quelque chose a casse -- c'est la seule raison de ce correctif.
#:
#: Les deux coins sont exiges, et pas seulement le compte de lignes : c'est ce
#: qui empeche qu'une note se fasse absorber dans la grille par une maquette
#: qui aurait perdu une ligne.
COIN_HAUT = "\u250c"
COIN_BAS = "\u2514"


def grille(lignes: list[str]) -> list[str]:
    """Les lignes de la MAQUETTE, sans les notes qui la suivent."""
    return lignes[:HAUTEUR]


def verifier(chemin: Path, declares: dict | None = None) -> list[str]:
    toutes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")
    lignes = grille(toutes)
    defauts: list[str] = []
    if len(lignes) != HAUTEUR:
        defauts.append(f"{len(lignes)} lignes au lieu de {HAUTEUR}")
    if lignes and not lignes[0].startswith(COIN_HAUT):
        defauts.append(f"ligne 1: la grille n'ouvre pas par {COIN_HAUT!r}")
    if len(lignes) == HAUTEUR and not lignes[-1].startswith(COIN_BAS):
        defauts.append(
            f"ligne {HAUTEUR}: la grille ne ferme pas par {COIN_BAS!r} -- "
            "une note a-t-elle ete absorbee dans la maquette ?")
    for numero, ligne in enumerate(lignes, 1):
        largeur = colonnes(ligne)
        if largeur != LARGEUR:
            defauts.append(f"ligne {numero}: {largeur} colonnes au lieu de {LARGEUR}")

    # **La grille tient en UTF-8 et ne prouve RIEN sur le repli.** Defaut mesure
    # le 2026-08-29 : la ligne de raccourcis de `E2-2` faisait 75 colonnes en
    # UTF-8 et **80** une fois repliee (`⏎` -> `Entree`), pour une zone de 76.
    # Ce script la declarait conforme, et c'est une garde de code -- pas ce
    # script -- qui a fini par mordre, au developpement. Le repli precede la
    # mesure : c'est la regle du depot, et elle valait aussi ici.
    if len(lignes) >= HAUTEUR:
        brute = lignes[RANG_DES_RACCOURCIS - 1]
        if brute.startswith("│") and brute.endswith("│"):
            contenu = brute[1:-1].strip()
            replie = colonnes(replie_en_ascii(contenu))
            if replie > UTILE:
                defauts.append(
                    f"ligne {RANG_DES_RACCOURCIS} (raccourcis): {replie} "
                    f"colonnes une fois REPLIEE EN ASCII, pour {UTILE} "
                    f"disponibles ({colonnes(contenu)} en UTF-8)")
    if len(lignes) == HAUTEUR:
        defauts += verifier_la_colorisation(
            lignes, (declares or {}).get(chemin.stem, {}))
    return defauts


def verifier_la_colorisation(lignes: list[str], etats: dict) -> list[str]:
    """Les TROIS frontieres de la regle de colorisation. Voir `GLYPHES_D_ETAT`.

    **Ce qu'elles NE mesurent pas, dit plutot que taire.** Aucune ne sait
    reconnaitre, dans le seul texte, qu'une ligne est la CONTINUATION du message
    d'au-dessus. La mesure a ete faite : sur les sept lignes du depot qui sont
    alignees sous le texte d'un glyphe d'etat, TROIS sont des entrees soeurs et
    non des continuations (`E5-4`, `E6-2c`, `E3-4`). Un detecteur par alignement
    rendrait donc trois faux rouges. La hauteur d'un message est pour cette
    raison DECLAREE par le generateur -- qui la sait, puisqu'il vient de la
    composer -- exactement comme `hauteur_du_curseur` l'est depuis
    `EPIC11-ARB-125`. La frontiere 3 mesure la forme de cette declaration ; elle
    ne mesure pas qu'on ait pense a la poser.
    """
    defauts: list[str] = []
    declares = {int(r): n for r, n in etats.items()}

    # ---- Frontiere 1 : aucun glyphe d'etat ne reste sans couleur ------------
    for rang in range(PREMIERE_DU_CENTRE, DERNIERE_DU_CENTRE):
        porte = etat_porte(lignes[rang])
        if porte and not etat_devine(lignes[rang]) and rang not in declares:
            defauts.append(
                f"ligne {rang + 1}: glyphe d'etat '{porte}' qu'AUCUN repli par "
                "motif ne peut voir (cartouche, ou continuation) et qu'aucune "
                "declaration ne porte -- il resterait sans couleur")

    # ---- Frontiere 2 : jamais de vert sur un ecran qui refuse ---------------
    ligne_d_etat = lignes[HAUTEUR - 3]
    if (GLYPHES_D_ETAT_INVERSE["absent"] in ligne_d_etat
            and any(mot in ligne_d_etat.lower() for mot in MOTS_D_INTERDIT)):
        verts = [rang for rang in range(PREMIERE_DU_CENTRE, DERNIERE_DU_CENTRE)
                 if etat_quelconque(lignes[rang]) == "complete"]
        for rang in verts:
            defauts.append(
                f"ligne {rang + 1}: une validation VERTE sur un ecran qui "
                "refuse -- le vert dit « valide », et le poser sur un interdit "
                "retourne le sens (attendu: l'orange de l'avertissement)")

    # ---- Frontiere 3 : une declaration d'etat est un BLOC entier ------------
    for rang, nom in sorted(declares.items()):
        if nom not in set(GLYPHES_D_ETAT.values()):
            defauts.append(f"declaration ligne {rang + 1}: etat inconnu {nom!r}")
        elif not PREMIERE_DU_CENTRE <= rang < DERNIERE_DU_CENTRE:
            defauts.append(
                f"declaration ligne {rang + 1}: hors de la zone centrale")
        elif not lignes[rang][1:-1].strip():
            defauts.append(
                f"declaration ligne {rang + 1}: la ligne est vide -- un "
                "message troue est un message colorise une ligne sur deux")
        elif etat_quelconque(lignes[rang]) not in (None, nom):
            defauts.append(
                f"declaration ligne {rang + 1}: la ligne porte l'etat "
                f"'{etat_quelconque(lignes[rang])}' et non {nom!r}")
    for rang, nom in sorted(declares.items()):
        # La tete d'un bloc porte le glyphe ; une continuation n'en porte aucun
        # et suit immediatement une ligne du meme etat.
        if etat_quelconque(lignes[rang]) is None and declares.get(rang - 1) != nom:
            defauts.append(
                f"declaration ligne {rang + 1}: continuation sans tete -- "
                "aucune ligne du meme etat ne la precede immediatement")
    return defauts


#: L'inverse de `GLYPHES_D_ETAT`, pour nommer un glyphe par son etat.
GLYPHES_D_ETAT_INVERSE = {nom: glyphe for glyphe, nom in GLYPHES_D_ETAT.items()}


def main(argv: list[str]) -> int:
    racine = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent / "maquettes"
    maquettes = sorted(racine.glob("*.txt"))
    if not maquettes:
        print(f"aucune maquette dans {racine}")
        return 1
    total_defauts = 0
    registre = racine / ETATS_DECLARES
    declares = (json.loads(registre.read_text(encoding="utf-8"))
                if registre.exists() else {})
    for maquette in maquettes:
        defauts = verifier(maquette, declares)
        total_defauts += len(defauts)
        if defauts:
            print(f"[x] {maquette.name}")
            for defaut in defauts:
                print(f"      {defaut}")
        else:
            print(f"[o] {maquette.name}")
    print(f"\n{len(maquettes)} maquettes, {total_defauts} defauts")
    return 1 if total_defauts else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
