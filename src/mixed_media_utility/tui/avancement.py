# -*- coding: utf-8 -*-
"""La progression, le temps restant et le journal (story 11.1, AC 3).

**Ce module ne calcule pas le temps restant** : il le demande a
:class:`~mixed_media_utility.progression.EstimateurTempsRestant`, et il ne
l'affiche que si l'estimateur en rend un. Trois contrats du coeur, cites de son
docstring et portes ici :

* **l'unite est la seconde par frame ecrite** (`EPIC7-ARB-80`), jamais son
  inverse -- dans ce depot « images par seconde » designe toujours la cadence
  d'un rush, et l'homonymie porterait sur le concept central du produit ;
* **aucun temps n'est rendu tant qu'aucune mesure reelle n'existe**
  (`EPIC7-ARB-67`) : la reponse est ``None``, et l'affichage ne fabrique alors
  ni `0:00`, ni `--:--`, ni chaine vide la ou une duree est attendue -- il
  n'ecrit **rien** ;
* le canal est **observationnel** (`EPIC7-ARB-79`) : une defaillance du rappel
  n'echoue pas la tache. **Interdit symetrique** : une erreur du travail
  observe traverse intacte, texte compris.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from . import jetons

#: Nombre de lignes de journal conservees. Une extraction de 6 300 frames emet
#: 6 300 jalons ; tout garder ferait grossir la memoire sans que personne ne
#: relise la ligne 12. Le plafond est **glissant** : ce sont les DERNIERES
#: lignes qui interessent, ce sont elles qu'on garde.
#:
#: La valeur n'est pas un arbitrage produit tant qu'aucune mesure ne dit ou ca
#: fait mal (question 2 de la fiche 11.1) : 200 tient trois ecrans de journal
#: deplie a 80x24, ce qui est le seul repere disponible aujourd'hui.
LIGNES_DE_JOURNAL = 200

#: Separateur entre les champs de la ligne d'etat. **Deux** espaces et non
#: trois : mesure faite a la construction des maquettes, trois faisaient 77
#: colonnes pour 76 disponibles.
SEPARATEUR = "  "


def barre(faites: int, total: int, largeur: int = jetons.LARGEUR_BARRE,
          ascii_seul: bool = False) -> str:
    """La barre de `DESIGN.md` section 8 : pleins, puis vides, largeur fixe.

    La largeur est **constante** (36 colonnes, lues dans les jetons) : une
    barre qui s'etirerait avec la fenetre rendrait deux captures
    incomparables.
    """
    table = jetons.glyphes(ascii_seul)
    if total <= 0:
        return table["barre-vide"] * largeur
    part = min(max(faites / total, 0.0), 1.0)
    # **La barre n'est pleine QUE quand le travail l'est.** `round` la
    # remplissait des 98,6 % : deux champs disaient « termine » pendant que le
    # compte reel disait qu'il restait du travail. C'est exactement la
    # contradiction que `EmetteurProgression` prend soin d'eviter cote coeur --
    # « il n'est jamais force a `total` en fin de course [...] completer
    # artificiellement a 100 % masquerait dans l'affichage exactement le defaut
    # que cette garde existe pour lever » (risque R12).
    pleins = largeur if part >= 1.0 else min(round(part * largeur), largeur - 1)
    return table["barre-pleine"] * pleins + table["barre-vide"] * (largeur - pleins)


def pourcentage(faites: int, total: int) -> str:
    """Le pourcentage. Vide si le total ne veut rien dire.

    **`100 %` est reserve a la fin**, comme la barre pleine : `:.0f` l'ecrivait
    des 99,5 %, donc sur les trente dernieres frames d'une extraction de 6 300.
    Le compte reel dit la verite a cote (`DESIGN.md` section 8 : « le compte est
    ce qui est vrai, le pourcentage est ce qui est lisible ») -- raison de plus
    pour que le lisible ne le contredise pas.
    """
    if total <= 0:
        return ""
    part = min(max(faites / total, 0.0), 1.0)
    if part >= 1.0:
        return "100 %"
    return f"{min(round(part * 100), 99)} %"


def duree_lisible(secondes: float) -> str:
    """Une duree en clair, dans la grammaire du `DESIGN.md`.

    **La grammaire est celle de la section 8, pas la mienne** : ``X s`` sous la
    minute (`reste ~ 8 s`), ``M min SS`` au-dessus (`reste ~ 1 min 10`),
    ``H h MM`` au-dessus de l'heure -- comme on ecrit `1 h 30`. Ecrire
    `1 min 10 s` ajoutait deux colonnes que le DESIGN n'ecrit pas, et **c'est
    de la que venait le debordement** de la ligne d'etat : le DESIGN calcule
    lui-meme 75 colonnes pour cette ligne, et la maquette `E2-4` est juste.
    J'avais accuse la maquette ; la couche 3 de la revue l'a mesuree caractere
    par caractere et c'etait ce format-ci le fautif.

    **L'arrondi est vers le HAUT, avant le choix de l'unite.** Annoncer « 0 s »
    pour 0,4 seconde restante serait le mensonge qu'`EPIC7-ARB-67` interdit ; et
    arrondir apres avoir choisi l'unite rendait « 60 s » sur toute la bande
    ]59, 60[, ou la grammaire veut « 1 min 00 » (revue de vague 1, couche 2).
    """
    entier = max(math.ceil(max(float(secondes), 0.0)), 1)
    if entier < 60:
        return f"{entier} s"
    minutes, reste = divmod(entier, 60)
    if minutes < 60:
        return f"{minutes} min {reste:02d}"
    heures, minutes = divmod(minutes, 60)
    return f"{heures} h {minutes:02d}"


@dataclass
class Avancement:
    """Ce qu'un ecran d'execution affiche a un instant : jamais plus que su.

    ``unite`` nomme ce qui est compte -- « frames », « pages », « lots ». Elle
    est obligatoire : `124/186` sans unite ne dit pas ce qui avance.
    """

    unite: str
    faites: int = 0
    total: int = 0
    #: Le detail du second niveau, quand il y en a un (AC 3.5). Il **remplace**
    #: le compte simple, il ne s'y ajoute pas : les deux ensemble ne tiennent
    #: pas dans les 76 colonnes utiles.
    detail: str | None = None
    #: Rendu par `EstimateurTempsRestant.temps_restant`, ou ``None``.
    temps_restant: float | None = None

    def ligne_d_etat(self, largeur: int | None = None,
                     ascii_seul: bool = False) -> str:
        """La ligne d'etat complete : barre, pourcentage, compte, temps restant.

        Les separateurs sont de **deux** espaces et non trois : mesure faite a
        la construction des maquettes, trois faisaient 77 colonnes pour 76
        disponibles.

        **Elle ne deborde jamais**, et ce n'est pas une precaution d'affichage :
        `textual` ne tronque pas une ligne trop longue, il la **replie** -- sur
        une zone de hauteur 1, la fin disparait sans bruit. Un temps restant
        perdu de cette facon serait indistinguable d'un temps restant absent,
        c'est-a-dire du regime que `EPIC7-ARB-67` reserve a « aucune mesure ».

        L'ordre des sacrifices est fixe, du moins couteux au plus couteux :

        1. **le pourcentage** part le premier -- la barre le dit deja, en
           dessin ; rien n'est perdu ;
        2. **le detail** est ensuite abrege -- c'est un reperage libre fourni
           par l'appelant (« lot 2 sur 5 »), pas une donnee du produit ;
        3. **la barre et le temps restant ne sont jamais touches** : l'une est
           de largeur fixe pour que deux captures restent comparables, l'autre
           est la seule information qu'on ne peut pas relire ailleurs.
        """
        largeur = jetons.largeur_utile() if largeur is None else largeur
        dessin = barre(self.faites, self.total, ascii_seul=ascii_seul)
        part = pourcentage(self.faites, self.total)
        # Un detail VIDE retombe sur le compte simple, il ne l'efface pas : le
        # contrat du champ est « il remplace le compte », pas « il peut le
        # supprimer », et une ligne d'etat sans aucun compte ne dit plus rien.
        detail = (self.detail if self.detail
                  else f"{self.faites}/{self.total} {self.unite}")
        reste = ("" if self.temps_restant is None
                 # `EPIC7-ARB-67` : on n'entre ici que si une mesure existe.
                 else f"reste ~ {duree_lisible(self.temps_restant)}")

        def assemble(part_: str, detail_: str) -> str:
            return SEPARATEUR.join(
                c for c in (dessin, part_, detail_, reste) if c)

        ligne = assemble(part, detail)
        if jetons.colonnes(ligne) <= largeur:
            return ligne
        ligne = assemble("", detail)
        if jetons.colonnes(ligne) <= largeur:
            return ligne
        # Il ne reste que le detail a raccourcir. Le budget est ce qui reste
        # une fois la barre et le temps restant poses -- **moins le separateur
        # de deux espaces que le detail ramene avec lui**, qui ne figure pas
        # dans l'assemblage sans detail.
        budget = largeur - jetons.colonnes(assemble("", "")) - len(SEPARATEUR)
        return assemble("", jetons.ajuster(detail, budget, ascii_seul))


@dataclass
class Journal:
    """Les dernieres lignes emises, plafonnees et glissantes."""

    plafond: int = LIGNES_DE_JOURNAL
    _lignes: deque = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lignes = deque(maxlen=self.plafond)

    def __len__(self) -> int:
        return len(self._lignes)

    def inscrire(self, ligne: str) -> None:
        self._lignes.append(ligne)

    @property
    def lignes(self) -> list[str]:
        """De la plus ancienne a la plus recente, comme on lit un journal."""
        return list(self._lignes)

    def dernieres(self, combien: int) -> list[str]:
        """Les `combien` dernieres -- ce qu'un journal replie montre."""
        return self.lignes[-combien:] if combien > 0 else []
