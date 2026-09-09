# -*- coding: utf-8 -*-
"""Edition des noms produits, sous la contrainte du coeur (story 11.1, AC 2).

**La limite et le motif ne sont pas ecrits ici.** Ils sont ceux de
:mod:`mixed_media_utility.io.naming`, et la validation elle-meme est
deleguee a :func:`~mixed_media_utility.io.naming.validate_manifest_identifier`.
Recopier `48` ou le motif `^[A-Za-z0-9_-]+$` dans une interface, c'est
fabriquer une seconde regle qui divergera de celle du schema au premier
ajustement -- et l'interface est le mauvais endroit pour arbitrer ce que le
manifest accepte.

**On refuse, on ne tronque jamais** (`EPIC11-ARB-25`, et le precedent
`io/calibration_profile.py`). Le motif est structurel et doit etre dit a
l'operateur : **deux noms tronques au meme prefixe seraient le meme lot**.
Une troncature silencieuse fabriquerait une collision d'identifiants, c'est-a-
dire deux lots ecrasant leurs frames l'un sur l'autre.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..io.naming import CANONICAL_ID_MAX_LENGTH, NamingError, validate_manifest_identifier
from .jetons import CREUX_MINIMAL as _CREUX_MINIMAL
from .jetons import abreger_nom as _abreger
from .jetons import colonnes as _colonnes
from .jetons import glyphes as _glyphes

#: Point d'import unique de la limite. Aucun autre module de la TUI ne
#: mentionne le nombre : la frontiere negative de l'AC 2.4 le mesure a zero.
LIMITE = CANONICAL_ID_MAX_LENGTH

#: Ce que l'operateur lit quand il depasse, **en corps d'ecran** : une MESURE
#: du depassement, pas la justification de la regle.
#:
#: **Il portait la justification, et c'est ce que le lot I corrige** (finding
#: `I5`/`I6`, et la tension `EPIC11-ARB-25` / `EPIC11-ARB-56` que le lot G avait
#: declaree sans la trancher). Sa redaction d'avant --
#: `Refuse : deux noms coupes au meme prefixe seraient le meme lot.` -- posait
#: deux defauts a la fois :
#:
#: * elle etait rendue **en ligne d'etat**, ou `EPIC11-ARB-56` n'admet
#:   « **aucun motif de conception** ». « deux noms coupes au meme prefixe
#:   seraient le meme lot » est exactement cela : le motif de la regle, pas la
#:   mesure de ce que l'operateur regarde ;
#: * elle etait ecrite **sans accents dans une source rendue en UTF-8**, donc
#:   identique dans les deux regimes -- ce que la table `jetons.REPLIS_DE_TEXTE`
#:   existe justement pour eviter (finding `I6`, vu sur la capture reelle
#:   `22-E2-3c-nom-refuse.svg`).
#:
#: La reconciliation est celle que la **maquette** `E2-3c` fait par la mise en
#: page, et Egan l'avait deja demandee sur elle (« On se contente de dire que le
#: nom est trop long. Pas de justification. ») : le **corps** nomme le motif et
#: le mesure, la **ligne d'etat** ne porte qu'une mesure. Les deux arbitrages
#: tiennent alors ensemble, verbatim :
#:
#: * `EPIC11-ARB-25` : « le message nomme le motif au lieu de dire
#:   « invalide » » -- le corps dit `trop long`, jamais `invalide` ;
#: * `EPIC11-ARB-56` : la ligne d'etat « ne porte **aucune touche** [...]
#:   **aucun conseil d'usage** [...] **aucun motif de conception** ».
#:
#: **La limite n'est pas ecrite ici** : elle est interpolee depuis
#: :data:`LIMITE`, seul point d'import du depot (frontiere negative de l'AC 2.4).
GABARIT_TROP_LONG = "Le nom est trop long : {longueur} caractères pour {limite} admis."


def motif_de_longueur(longueur: int) -> str:
    """`Le nom est trop long : 50 caractères pour 48 admis.` (corps de `E2-3c`).

    Une **fonction** et non une constante, parce que le motif porte desormais la
    mesure : une constante ne pourrait dire que « trop long », c'est-a-dire le
    jugement sans le chiffre qui permet de corriger.
    """
    return GABARIT_TROP_LONG.format(longueur=longueur, limite=LIMITE)


#: Le pattern vient du schema v2 ; la phrase dit ce qui est accepte, jamais une
#: expression reguliere -- un operateur ne lit pas `^[A-Za-z0-9_-]+$`.
#:
#: **Accentuee depuis le lot I** (`I6`) : une phrase ecrite sans accents dans la
#: source court-circuite `jetons.REPLIS_DE_TEXTE` et rend le meme texte en UTF-8
#: et en repli ASCII -- exactement ce que la table existe pour eviter.
MOTIF_CARACTERES = "Refusé : lettres non accentuées, chiffres, tiret, souligné."

#: Meme correction d'accents, meme motif (`I6`).
MOTIF_VIDE = "Refusé : un nom vide ne désigne aucun lot."


@dataclass
class NomEditable:
    """Un nom produit, sa valeur conventionnelle, et ce que l'operateur en fait.

    ``conventionnel`` est ce que le coeur aurait nomme ; ``valeur`` est ce qui
    sera ecrit. Les deux sont gardes separement pour que `r` puisse remettre le
    premier sans avoir a le recalculer -- et pour qu'on puisse dire si le nom a
    ete touche.
    """

    conventionnel: str
    valeur: str = ""

    def __post_init__(self) -> None:
        if not self.valeur:
            self.valeur = self.conventionnel

    # -- lecture ----------------------------------------------------------

    @property
    def modifie(self) -> bool:
        return self.valeur != self.conventionnel

    @property
    def longueur(self) -> int:
        return len(self.valeur)

    @property
    def compteur(self) -> str:
        """Le compteur vivant `n/48` de l'AC 2.2. Il compte ce qui est SAISI.

        Il depasse donc la limite quand la saisie la depasse : afficher `48/48`
        sur une saisie de 50 caracteres serait la troncature, en affichage.
        """
        return f"{self.longueur}/{LIMITE}"

    @property
    def motif(self) -> str | None:
        """Le motif du refus, ou ``None`` si la valeur est acceptable.

        L'ordre des verifications suit ce que l'operateur doit corriger en
        premier : un nom vide n'a pas de longueur a discuter, et un nom trop
        long dont les caracteres sont mauvais est d'abord trop long -- parce
        que raccourcir peut suffire, et que l'inverse n'est pas vrai.
        """
        if not self.valeur:
            return MOTIF_VIDE
        if len(self.valeur) > LIMITE:
            return motif_de_longueur(self.longueur)
        try:
            validate_manifest_identifier(self.valeur, label="nom")
        except NamingError:
            return MOTIF_CARACTERES
        return None

    @property
    def valide(self) -> bool:
        return self.motif is None

    # -- ecriture ---------------------------------------------------------

    def saisir(self, texte: str) -> None:
        """Prend la saisie TELLE QUELLE. Aucune coupe, aucun nettoyage.

        C'est le coeur de l'AC 2.3 : une saisie de 50 caracteres rend une
        valeur de 50 caracteres, refusee. Nettoyer ici rendrait le refus
        inobservable et remplacerait le choix de l'operateur par le notre.
        """
        self.valeur = texte

    def taper(self, caractere: str) -> None:
        """Ajoute UN caractere, tel quel, a la position d'insertion.

        Aucun filtrage a la frappe (`EPIC11-ARB-25`) : un caractere refuse doit
        pouvoir etre **tape puis vu refuse**. Interdire la frappe rendrait le
        refus muet -- l'operateur croirait son clavier casse la ou la TUI doit
        lui dire ce qui ne va pas.
        """
        self.valeur += caractere

    def effacer(self) -> None:
        """Retour arriere. Sur une valeur vide, ne fait rien -- et ne leve pas."""
        self.valeur = self.valeur[:-1]

    def remettre(self) -> None:
        """`Ctrl+R` : revenir au nom conventionnel.

        **Une combinaison, jamais la lettre `r`** (`EPIC11-ARB-68`) : « Aucune
        lettre n'est un raccourci dans un champ de saisie. »
        """
        self.valeur = self.conventionnel


@dataclass
class ModeleNoms:
    """Les noms d'un panneau, plus le curseur qui dit lequel on edite.

    **Au moins deux noms des que la commande en produit deux** : le curseur, le
    passage `↑↓` et la validation d'ensemble ne se mesurent pas sur une liste a
    un element (regle des fabriques).
    """

    noms: list[NomEditable] = field(default_factory=list)
    curseur: int = 0
    #: Vrai entre `Tab` et `Echap`/validation. Hors edition, `↑↓` navigue dans
    #: le panneau et non dans les noms.
    en_edition: bool = False

    def __post_init__(self) -> None:
        self._sauvegarde: list[str] | None = None

    # -- lecture ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self.noms)

    @property
    def courant(self) -> NomEditable:
        return self.noms[self.curseur]

    @property
    def valides(self) -> bool:
        """Tous, pas seulement celui qu'on regarde.

        Un panneau qui n'examinerait que le nom sous le curseur laisserait
        passer un nom refuse edite plus tot -- et l'action principale
        redeviendrait accessible sur un jeu invalide.
        """
        return all(nom.valide for nom in self.noms)

    @property
    def motifs(self) -> dict[int, str]:
        """Les refus, par rang. Vide quand tout passe."""
        return {rang: nom.motif for rang, nom in enumerate(self.noms)
                if nom.motif is not None}

    @property
    def valeurs(self) -> list[str]:
        return [nom.valeur for nom in self.noms]

    # -- edition ----------------------------------------------------------

    def entrer_en_edition(self) -> None:
        """`Tab` : on entre, et on note ce qu'on pourra rendre a l'abandon."""
        self.en_edition = True
        self._sauvegarde = self.valeurs

    def abandonner(self) -> None:
        """`Echap` : les valeurs reviennent a ce qu'elles etaient a l'entree.

        « Sans modifier les valeurs » (AC 2.1) ne veut pas dire « sans les
        avoir touchees » : l'operateur a pu taper. C'est la sauvegarde prise a
        l'entree qui rend l'abandon vrai, pas l'absence de frappe.
        """
        if self._sauvegarde is not None:
            for nom, valeur in zip(self.noms, self._sauvegarde):
                nom.valeur = valeur
        self.en_edition = False
        self._sauvegarde = None

    def confirmer(self) -> None:
        """Sortir de l'edition en gardant ce qui a ete tape."""
        self.en_edition = False
        self._sauvegarde = None

    def descendre(self) -> None:
        """`↓` : nom suivant, sans boucler -- le dernier reste le dernier."""
        self.curseur = min(self.curseur + 1, len(self.noms) - 1)

    def monter(self) -> None:
        self.curseur = max(self.curseur - 1, 0)

    def saisir(self, texte: str) -> None:
        self.courant.saisir(texte)

    def taper(self, caractere: str) -> None:
        self.courant.taper(caractere)

    def effacer(self) -> None:
        self.courant.effacer()

    def remettre(self) -> None:
        self.courant.remettre()

    def ligne(self, rang: int, largeur: int, ascii_seul: bool = False) -> str:
        """La ligne d'un nom dans le cartouche : marque, valeur, compteur.

        Trois informations, et **chacune a son glyphe** (`DESIGN.md` section 5,
        regle 1 non negociable) :

        * le nom **courant** porte l'invite `>` ; les autres, deux espaces ;
        * le nom **refuse** porte `✕` -- le compteur seul ne suffirait pas, un
          nom peut etre refuse en etant court ;
        * le **compteur `n/48`** est sur la ligne du nom, comme les maquettes
          `E2-3b` et `E2-3c` le montrent, et non en ligne d'etat ou il ne
          designerait pas lequel des noms il compte.
        """
        table = _glyphes(ascii_seul)
        nom = self.noms[rang]
        invite = table["invite"] if rang == self.curseur else " "
        etat = table["absent"] if not nom.valide else " "
        caret = table["caret"] if (self.en_edition and rang == self.curseur) else ""
        tete = f"{invite} {etat} "
        # **La borne HAUTE, absente jusqu'a la revue de vague 2 bis.** Mesure
        # faite sur le cartouche du plancher (72 colonnes) : des 62 colonnes de
        # valeur -- 61 en edition, le caret en coutant une -- la ligne
        # debordait, et le garde-fou `jetons.ajuster` la rattrapait en coupant
        # PAR LA FIN, c'est-a-dire en mangeant le compteur `n/48`. Or le
        # compteur est la seule chose qui dit a l'operateur POURQUOI son nom est
        # refuse : le perdre exactement quand le nom est trop long, c'est le
        # perdre au seul moment ou il sert.
        #
        # Le seuil est atteint bien avant la limite du schema en double chasse :
        # **31 ideogrammes font 62 colonnes** alors que le compteur affiche
        # `31/48`. Compter en caracteres ferait donc croire la ligne a l'aise
        # au moment meme ou elle deborde de six colonnes.
        place = largeur - _colonnes(tete)
        # Le compteur passe en premier sur le budget -- on borne le nom, jamais
        # les compteurs (regle posee sur la liste de l'explorateur) --, mais il
        # reste borne lui aussi : sans cela une valeur collee de plusieurs
        # milliers de caracteres ferait deborder par son seul compteur.
        compteur = _abreger(nom.compteur, max(place - _CREUX_MINIMAL, 0),
                            ascii_seul)
        # Le caret est intouchable : il dit ou l'on tape. Il se reserve donc
        # AVANT l'abregement de la valeur, pas apres.
        valeur = _abreger(
            nom.valeur,
            place - _colonnes(compteur) - _CREUX_MINIMAL - _colonnes(caret),
            ascii_seul)
        gauche = f"{tete}{valeur}{caret}"
        creux = largeur - _colonnes(gauche) - _colonnes(compteur)
        return gauche + " " * max(_CREUX_MINIMAL, creux) + compteur
