# -*- coding: utf-8 -*-
"""La FORME de l'explorateur de dossiers, en un seul endroit.

Ces fonctions vivaient dans `_gen_explorateur.py`, qui produit les maquettes
`X1` a `X9` validees par Egan le 2026-08-29. L'atelier Extraction ouvre le meme
explorateur a son cinquieme site (`EPIC11-ARB-48`) : `E2-1b` (variante dossiers
seuls, pour `r retrouver`) et `E2-1c` (variante fichiers visibles, pour
`d designer`).

**Elles sont extraites ici plutot que recopiees.** Une seconde forme
d'explorateur, meme fidele le jour ou elle est ecrite, derive au premier
raffinement : c'est exactement le defaut que `construire_maquette` existe pour
empecher a l'echelle de la grille. Les deux generateurs importent donc la meme
mise en page, et une correction de forme se fait une fois.

Rien n'est change au passage : les maquettes `X*.txt` sont identiques au
caractere pres avant et apres l'extraction (verifie par `git diff`).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from construire_maquette import UTILE, colonnes, maquette, regle  # noqa: E402

COLONNE_VALEUR = 26
COLONNE_NOM = 5
BORD_DROIT = UTILE - 2
#: Hauteur fixe de la zone de liste. Neuf lignes, `…` compris : c'est ce qui
#: reste des 17 lignes de la grille une fois posees les deux etiquettes vives.
LIGNES_DE_LISTE = 9


def champ(libelle: str, valeur: str, focus: bool) -> str:
    marqueur = ">" if focus else " "
    tete = " " * COLONNE_NOM + libelle
    tete += " " * (COLONNE_VALEUR - 2 - colonnes(tete)) + marqueur + " "
    return tete + valeur


def ligne(nom: str, droite: str = "", curseur: bool = False) -> str:
    tete = " " * (COLONNE_NOM - 2) + ("▸ " if curseur else "  ") + nom
    if not droite:
        return tete
    creux = BORD_DROIT - colonnes(tete) - colonnes(droite)
    return tete + " " * max(2, creux) + droite


def points(droite: str = "") -> str:
    return ligne("…", droite)


#: Largeur de la case a cocher, en colonnes. `[x]` et `[ ]` en font trois, et le
#: refus (`✕` cale) en fait trois aussi : la colonne du nom ne bouge donc jamais
#: selon ce qu'une ligne porte. C'est la largeur de `cadences._LARGEUR_DE_LA_CASE`,
#: et ce n'est pas un hasard -- la liste de cadences est le precedent du depot
#: pour une selection multiple (`EPIC11-ARB-103`).
LARGEUR_DE_LA_CASE = 3

#: Les trois etats d'une case, dans l'ordre ou on les rencontre.
CASES = {
    "vide": "[ ]",
    "cochee": "[x]",
    "refusee": " ✕ ",
}


def ligne_cochable(nom: str, case: str = "vide", droite: str = "",
                   curseur: bool = False) -> str:
    """Une ligne de liste en MODE SELECTION : la case, puis le nom.

    La disposition est celle de `cadences.py` -- `curseur + " " + case + " "` --
    et elle est copiee plutot que reinventee : deux dispositions pour le meme
    geste seraient deux grammaires (`EPIC11-ARB-103`).

    **La case coute quatre colonnes au nom** (trois de case, une de blanc), et
    c'est le seul prix de ce mode. Mesure au 2026-08-31 : un nom accompagne
    d'une colonne de droite disposait de 51 colonnes, il en garde 47 ; le nom le
    plus long du depot, `2026-08-29_tournage_exterieur_nuit_camera_B`, en fait
    42. Le prix se paie, il ne mord pas.
    """
    tete = (" " * (COLONNE_NOM - 2) + ("▸ " if curseur else "  ")
            + CASES[case] + " " + nom)
    if not droite:
        return tete
    creux = BORD_DROIT - colonnes(tete) - colonnes(droite)
    return tete + " " * max(2, creux) + droite


def liste(entrees: list[str]) -> list[str]:
    if len(entrees) > LIGNES_DE_LISTE:
        raise ValueError(
            f"{len(entrees)} lignes de liste pour {LIGNES_DE_LISTE} disponibles")
    return entrees + [""] * (LIGNES_DE_LISTE - len(entrees))


def etiquette(touche: str, cible: str, libelle: str = "") -> str:
    """Une ETIQUETTE VIVE : la touche, et ce sur quoi elle agit.

    Ce n'est pas un bouton. Le curseur n'y va jamais -- c'est ce qui empeche a
    la fois les deux curseurs de la v1 et les vingt-sept frappes qu'il fallait
    pour atteindre « Valider ».

    **Calee a gauche, et le parent ne porte que son nom court** (demande d'Egan
    du 2026-08-29, notes `x1` et `x2`) : « mettre juste la fleche et
    "...\\Documents\\" au lieu du chemin complet. Justifie a gauche et non a
    droite. » Le chemin complet du parent n'apprend rien -- il ne differe de
    celui de la barre d'adresse que par son dernier segment.
    """
    milieu = f"{libelle}   " if libelle else ""
    return f"   {touche}  {milieu}{cible}"


def ecran(*, bandeau_gauche: str, bandeau_droite: str, titre: str,
          parent: str, libelle: str, chemin: str, focus_adresse: bool,
          entrees: list[str], valide: str,
          etat: str, raccourcis: str) -> str:
    centre = [
        "",
        "  " + titre,
        "",
        etiquette("←", parent),
        champ(libelle, chemin, focus_adresse),
        regle(),
        *liste(entrees),
        regle(),
        valide,
    ]
    return maquette(bandeau_gauche=bandeau_gauche, bandeau_droite=bandeau_droite,
                    centre=centre, etat=etat, raccourcis=raccourcis)


def valider(cible: str, note: str = "") -> str:
    """La ligne de validation. Son separateur vaut **TROIS** blancs.

    **Et ce n'est pas un oubli du resserrement d'`EPIC11-ARB-122`** (finding
    `R13` de la revue du 2026-08-31) : cet arbitrage porte sur les lignes de
    RACCOURCIS, et la ligne de validation n'en est pas une. Le produit ecrit
    `"Valider   "` puis, en mode selection, un separateur de trois blancs avant
    le poids (`explorateur.py`) -- c'est ce rythme-la qu'on suit ici.

    La passe de resserrement avait serre cette ligne sur `X2`, `X5`, `X6` et
    `X8` et pas sur `X11`, `X11b`, `E2-1b`, `E2-1c` : deux rythmes dans le meme
    construit, ce que le motif de l'arbitrage invoque justement pour se
    justifier.
    """
    return etiquette("⏎", cible + (f"   {note}" if note else ""),
                     libelle="Valider")


# Les lignes de raccourcis. `⏎ valider` vient EN TETE : c'est l'action
# principale, et sa place dans l'ordre est ce qui la rend decouvrable.
RACCOURCIS = ("⏎ valider  → entrer  ← parent  "
              "↑↓ liste  Tab chemin  Échap sortir")
#: `X7` seulement : `Ctrl+H` n'a de sens que la ou il y a des dossiers caches.
#: Une TOUCHE va a la ligne des raccourcis, jamais a la ligne d'etat -- regle
#: de sobriete posee par Egan le 2026-08-29, valable sur tous les ecrans.
# `↑↓ liste` sort ici, et LA c'est mesure : la ligne complete fait 78 colonnes
# une fois repliee en ASCII pour une zone de 76. C'est exactement ce que
# `↑↓ liste` RENDU (finding `R12` de la revue du 2026-08-31). Le jeton avait ete
# sacrifie ici parce que la ligne debordait -- « le curseur peint le dit deja ».
# `EPIC11-ARB-122` a rendu six colonnes en resserrant le separateur, et
# `ecran_projet.RACCOURCIS_CHEMIN_CACHES` a repris le jeton dans le PRODUIT ;
# la maquette ne l'avait pas suivi, si bien qu'elle montrait une ligne plus
# pauvre que l'ecran livre. Mesure : 68 colonnes en UTF-8, 73 en repli, pour 76.
RACCOURCIS_CACHES = ("⏎ valider  → entrer  ← parent  ↑↓ liste  "
                     "Ctrl+H cachés  Échap sortir")
#: Dans la barre d'adresse, `←` et `→` deplacent le CARET, pas le
#: dossier : c'est le motif pour lequel il faut une touche qui entre dans la
#: saisie et qui en sort, et c'est `Tab` (note `x5b` d'Egan).
#: **`Coller : terminal` et non `Ctrl+V coller`.** Le produit a fait ce
#: changement au finding `C1` -- `Ctrl+V` est une promesse qu'aucun terminal ne
#: tient, le collage passe par l'evenement `Paste` --, et la maquette ne l'avait
#: pas suivi. La divergence a ete trouvee par la frontiere de `R12` a la seconde
#: ou elle a cesse de ne comparer que les touches COMMUNES : ce n'etait pas le
#: defaut qu'on cherchait, c'est son symetrique.
#:
#: **Puis `Coller par le terminal`, le 2026-09-03** (defaut `F4` de la couche 3
#: de la revue de la 11.9). Le `:` servait de sous-separateur, et le manuel des
#: raccourcis -- qui decoupe un item sur les blancs -- publiait un deux-points
#: orphelin en tete de colonne. La maquette suit le produit, comme la fois
#: precedente, et par la SOURCE. Mesure : 70 UTF-8 / 75 repli, pour 76 utiles.
RACCOURCIS_ADRESSE = ("⏎ valider  ←→ curseur  "
                      "Coller par le terminal  Tab liste  Échap sortir")
#: **Le mode SELECTION** (`EPIC11-ARB-103`) : `X6`, `X10`, `X11` et `X11b`.
#:
#: Elle vivait dans `_gen_selection.py`, ou seules les trois maquettes de la
#: 11.2c la lisaient. Elle remonte ici le 2026-08-31 avec le lot E bis de la
#: 11.5, parce qu'`X6` -- le site du depot du Scan -- la porte desormais lui
#: aussi : deux redactions de la meme ligne dans deux generateurs auraient
#: diverge au premier ajustement, et c'est exactement le defaut que la
#: frontiere `R12` a paye entre une maquette et le produit.
#:
#: `Espace cocher` reprend la formulation deja employee par la liste de
#: cadences, jamais inventee ici. Le budget, mesure au repli ASCII ou `⏎` vaut
#: six colonnes : sept jetons pesent 85 colonnes pour 76, six en pesent 75.
#: C'est `↑↓ liste` qui tombe -- precedent ecrit du depot, applique deux fois,
#: « le curseur peint le dit deja ».
RACCOURCIS_SELECTION = ("⏎ valider  Espace cocher  → entrer  "
                        "← parent  Tab chemin  Échap sortir")
