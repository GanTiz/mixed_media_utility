# -*- coding: utf-8 -*-
"""La liste cochable des cadences (story 11.4, AC 3, maquettes `E2-2` / `E2-2c`).

**Modele pur**, comme `panneau.py`, `noms.py` et `explorateur.py` : aucun import
de `textual`, aucun rendu d'ecran, des dataclasses et des methodes qui rendent
des donnees. C'est le seul motif de `DESIGN.md` qui n'avait aucune
implementation -- `ChoixExclusif` est un choix *exclusif*, pas une liste
cochable -- et la story 11.7 (multi-lots Pdf) le reutilisera : il nait donc
modele pur plutot qu'a l'interieur d'un ecran.

**Ce module ne calcule aucun compte de frames, et il ne sait pas multiplier.**
`EPIC11-ARB-30`, verbatim : « le noyau ne derive **jamais** le cardinal d'une
duree, il l'exige ». Le compte arrive par le `compteur` injecte a la
construction -- en pratique `cadence_previz.prepare_previz`, dont la
`PrevizSession` porte une `FrameSelection` par cadence et son cardinal en
`.expected_frame_count`. Le modele le **recoit** ; le seul calcul qu'il fasse
sur les comptes est une **somme** de ceux des cochees.

**Ce que le coeur refuse est affiche refuse, avec les mots du coeur.** Le
`compteur` leve une des exceptions de :data:`REFUS_DU_COEUR` ; le modele en
prend `str(erreur)` **verbatim** et la cadence devient non cochable. Le cas
« zero frame » n'existe pas et n'est donc pas traite : mesure faite,
``expected_frame_count = ceil(window_frame_count / step)`` avec
``window_frame_count >= 1`` et ``step > 0`` (`frame_selection.py:894`) rend
**1** au minimum, toujours. Un compte inferieur a 1 est donc refuse **a la
construction** : le cas impossible reste impossible plutot que d'etre couvert
par du code mort.

**La cadence libre EST fractionnaire depuis la story 11.4, lot P.** Ce qui la
retenait n'etait pas la valeur -- le coeur compte les frames de `25/3` comme de
`8.333` (mesure d'`EPIC11-ARB-62`) -- mais le NOM. `EPIC11-ARB-72`, verbatim :
« Une saisie fractionnaire est **refusee nommement** [...], jamais
silencieusement convertie : `25/3` arrondi en `8.333` ecrirait un lot dont le
nom ment sur ce qu'il contient. » Le meme arbitrage garde les fractionnaires
**remarquables** : « Les cadences fractionnaires **remarquables**
(`source / 3` = `25/3`) restent proposees et cochables : elles ne passent pas
par la saisie libre, et leur nom de lot vient de la convention `_25s3`
(`EPIC11-ARB-62`), pas de `format_fps_short`. »

**Cette derniere phrase reposait sur une premisse FAUSSE, et ce lot la rend
vraie.** Au 2026-08-30, `deferred-work.md` le mesurait : « Cette convention
n'existe pas. Elles restent cochables, et l'apercu montre **le vrai nom** avant
d'ecrire -- rien ne ment, mais le nom est laid » (`rush_01_8p333333333333334`,
dix-sept chiffres d'artefact). :func:`nom_court_de_cadence` l'ecrit desormais, et
`io.naming.build_lot_id` sait la recevoir. Le refus d'`ARB-72` tombe donc avec
son motif : ce que la saisie fractionnaire produisait -- un nom qui ment -- n'est
plus ce qu'elle produit.

**La saisie et le nommage sont le MEME concept, employe deux fois.** Le `s` de
`cs3` a la saisie et le `s` de `rush_01_25s3` au nommage sont
:data:`SEPARATEUR_DE_NOMMAGE`, une seule constante : c'est ce qui fait qu'un
operateur qui a tape `c/3` reconnait le nom du lot qu'il obtient.

**Le nom court ne voyage pas en `Fraction`.** `extraction.run_extraction` refuse
une `Fraction` des son entree et `format_fps_short` a 22 appelants dans `src/` :
faire voyager la fraction jusqu'a `naming` toucherait une soixantaine de points
d'appel. On fait voyager **son nom**, calcule ici, la ou la fraction est encore
connue et exacte.

**Les textes venus des maquettes sont recopies verbatim**, accents compris
(`E2-2` fait foi sur le texte et sur les colonnes) ; les motifs de refus ecrits
ici suivent la forme de ceux de `noms.py`, leur voisin direct.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable

from ..frame_selection import FrameSelectionError
from . import jetons

#: Les cadences **remarquables** de `EPIC11-ARB-24`, en diviseurs de la cadence
#: source : la source, source/2, source/3, source/4. C'est un choix de
#: **presentation**, pas une regle metier -- un grep de `remarquable` sur `src/`
#: rendait zero avant cette story --, il vit donc cote TUI et en constante
#: nommee. La cadence source, elle, est **lue du coeur** : elle vient de la
#: qualification du rush, jamais d'une saisie.
DIVISEURS_REMARQUABLES = (1, 2, 3, 4)

#: Ce que la ligne de la cadence source porte en colonne de droite (`E2-2`).
MENTION_TOUTES = "(toutes)"

#: Le libelle de la cadence source, et le patron de ceux de ses divisions.
LIBELLE_DE_LA_SOURCE = "source"
LIBELLE_D_UNE_DIVISION = "source / {diviseur}"

#: Le libelle d'une cadence ajoutee a la volee par `a`, quand rien ne la
#: rattache a la cadence source.
LIBELLE_LIBRE = "libre"

#: Le libelle d'une cadence ajoutee a la volee qui divise la cadence SOURCE.
#:
#: **Il vaut celui des remarquables, et cette egalite est le point**
#: (`EPIC11-ARB-94`, Egan, 2026-08-30). Elle a d'abord valu `cadence/{diviseur}`,
#: sur son texte verbatim du matin : « 25/5 devrait etre accepte avec pour
#: valeur 5 et a cote ecrit cadence/5 **comme pour les autres**. » Deux
#: lectures tenaient dans cette phrase -- le format cite, ou la ressemblance
#: demandee --, et elles se contredisaient : « les autres » disent `source / N`,
#: qui vient de la maquette `E2-2` validee en trois passes. L'ecran portait donc
#: DEUX vocabulaires pour la meme notion, a trois lignes d'ecart (mesure au
#: parcours `H3`). Egan a tranche pour la ressemblance.
#:
#: `source / N` dit ce que la cadence **est** -- une division de la source --
#: la ou `cadence/N` repetait ce qui avait ete **tape**. La grammaire de
#: saisie, elle, n'est pas touchee : `cadence/5`, `c/5`, `cs5`, `25/5` restent
#: tous acceptes EN ENTREE. Seul l'affichage s'unifie.
#:
#: Le nom de la constante survit a l'egalite : les deux notions restent
#: distinctes (une division ANNONCEE contre une division SAISIE), et les
#: refondre en une seule ferait perdre le jour ou l'une des deux devra bouger.
LIBELLE_D_UNE_DIVISION_DE_LA_SOURCE = LIBELLE_D_UNE_DIVISION

#: Hauteur FIXE de la zone de liste, `…` compris -- meme regle que celle de
#: l'explorateur : une cible qui se deplace quand la liste change de longueur
#: est une cible qu'on rate. Quatre cadences et une ligne de position, c'est
#: exactement ce que `E2-2` montre.
HAUTEUR_LISTE = 5

#: Largeur de la colonne du compte, commune aux deux maquettes (mesuree sur
#: `E2-2` et `E2-2c` : « 124 frames » y est cale a droite dans dix colonnes).
LARGEUR_DU_COMPTE = 10

#: Decimales affichees d'une cadence. **C'est un rendu, pas une valeur** : le
#: modele garde la `Fraction` exacte, et `25/3` s'ecrit `8,333` a l'ecran comme
#: dans `E2-2` sans que rien n'arrondisse la cadence elle-meme.
DECIMALES_AFFICHEES = 3

#: **Le `s` qui tient la place de la barre oblique.** Un seul concept, deux
#: usages : c'est le separateur qu'Egan accepte a la SAISIE (« remplacer le
#: slash par un s ») et c'est celui de la convention de NOMMAGE d'un lot a
#: cadence fractionnaire, `EPIC11-ARB-62` verbatim : « Un lot a cadence
#: fractionnaire s'appelle **`rush-001_25s3`** -- le `s` tient la place de la
#: barre. » Une seconde constante pour le nommage en ferait deux conventions
#: qui divergeraient au premier raffinement de l'une des deux.
SEPARATEUR_DE_NOMMAGE = "s"

#: Ce qui separe le numerateur du denominateur dans une saisie de division.
#: `/` d'abord, puis le `s` ci-dessus.
SEPARATEURS_DE_SAISIE = ("/", SEPARATEUR_DE_NOMMAGE)

#: Les mots qui designent la cadence SOURCE dans une saisie, verbatim d'Egan :
#: « "cadence/[nombre entier]" (avec cadence en toutes lettres), ou bien
#: "c/[nombre entier]" avec l'abreviation "c/" [...] "cs[nombre entier]" ou
#: encore "cadences[nombre entier]" ». Les quatre formes sont acceptees, que
#: l'on lise `cs6` comme l'alias `c` suivi du separateur `s` ou comme l'alias
#: `cs` colle a son diviseur : la grammaire ci-dessous accepte les deux
#: lectures, et elles designent la meme cadence.
ALIAS_DE_LA_SOURCE = ("cadences", "cadence", "cs", "c")

#: La grammaire complete d'une division : un numerateur (un entier, ou un alias
#: de la cadence source), un separateur, un denominateur entier. Le separateur
#: est **obligatoire** : sans lui, `256` se lirait `25s6`.
MOTIF_DE_DIVISION = re.compile(
    r"^(?:(?P<source>" + "|".join(ALIAS_DE_LA_SOURCE) + r")|(?P<numerateur>\d+))"
    r"\s*(?P<separateur>[" + "".join(SEPARATEURS_DE_SAISIE) + r"])\s*"
    r"(?P<denominateur>\d+)$"
)

#: Ce qui ne doit **jamais** atteindre `Fraction` quand la grammaire ci-dessus
#: n'a pas reconnu la saisie. **Teste AVANT la conversion**, et ce n'est pas un
#: detail d'ordre : `Fraction("-25/3")` reussit, donc une garde posee apres la
#: conversion ne verrait jamais rien et une saisie que la grammaire a refusee
#: entrerait quand meme par la porte de derriere.
SEPARATEURS_A_NE_JAMAIS_CONVERTIR = ("/", ":")

#: Les refus du coeur que le modele transforme en cadence non cochable. Les
#: quatre refus **reels** de l'AC 3.5 -- `UpsamplingNotSupportedError`,
#: `SelectionTooLargeError` (plafond `MAX_EXPECTED_FRAME_COUNT`),
#: `InvalidFrameRateError`, `EmptySourceError` -- derivent toutes de cette
#: racine unique. Tout ce qui n'en derive pas remonte : une panne n'est pas un
#: refus, et l'avaler la ferait passer pour une cadence impossible.
REFUS_DU_COEUR = (FrameSelectionError,)

#: Une saisie que ni la grammaire des divisions ni l'ecriture decimale ne
#: reconnaissent. **Les exemples sont dans le message** : c'est la seule chose
#: qui dit a l'operateur ce qu'on attend de lui, et depuis la story 11.4 lot P
#: ce qu'on attend de lui n'est plus seulement un decimal.
MOTIF_PAS_UN_NOMBRE = (
    "Refuse : une cadence s'ecrit en decimal (12,5) ou en division de la "
    "cadence source (cadence/3, c/3, cs3, 25/3)."
)

#: Diviser par zero n'a pas de valeur, et le coeur ne verra jamais la cadence :
#: le refus est donc pris ici, nommement, plutot que de laisser remonter une
#: `ZeroDivisionError` nue.
MOTIF_DIVISEUR_NUL = "Refuse : une cadence ne se divise pas par zero."

#: Un alias de la cadence source (`cadence/3`, `c/3`, `cs3`) saisi dans une
#: liste qui ne connait pas sa source. Le cas ne se produit pas par la
#: construction normale -- `ListeDeCadences.remarquables` retient toujours la
#: source --, mais une liste batie a la main (l'ecran du temps 2 en batit une)
#: ne la porte pas forcement : le refus le dit au lieu de nommer `libre` une
#: cadence dont on ignore le referent.
MOTIF_SOURCE_INCONNUE = (
    "Refuse : la cadence source n'est pas connue ici, ecrire la cadence en "
    "decimal (12,5) ou en division chiffree (25/3)."
)

#: AC 3.7. Le doublon se mesure sur la valeur **exacte**, jamais sur le texte
#: affiche : `12,5` saisi et `source / 2` d'une source a 25 im/s sont la meme
#: cadence, et deux lignes identiques produiraient deux lots du meme nom.
MOTIF_DOUBLON = "Refuse : cette cadence est deja dans la liste."

#: AC 3.6. Une validation a zero cochee ne passe **jamais en silence**.
MOTIF_AUCUNE_COCHEE = "Refuse : aucune cadence cochee, il n'y a rien a faire."

#: Le type du compteur injecte : il rend le cardinal d'une cadence, ou leve un
#: :data:`REFUS_DU_COEUR`.
Compteur = Callable[[Fraction], int]


class CadencesMalFormees(ValueError):
    """Un invariant que la revue ne devrait pas avoir a trouver est viole."""


def _en_fraction(valeur: object, quoi: str) -> Fraction:
    """Une cadence, en `Fraction` exacte. **Un flottant est refuse.**

    Le coeur a une seule ecriture exacte des cadences,
    `codec_profiles.exact_frame_rate`, et c'est elle qui recale les decimales
    NTSC arrondies sur leur ratio : `Fraction(23.976)` rend le ratio binaire du
    flottant, la ou le coeur veut `24000/1001`. Accepter un flottant ici
    fabriquerait une seconde cadence source, proche et differente, et le
    doublon de l'AC 3.7 ne se mesurerait plus.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, (int, Fraction)):
        raise CadencesMalFormees(
            f"{quoi} se lit du coeur en Fraction exacte, jamais en "
            f"{type(valeur).__name__} ; recu {valeur!r}."
        )
    return Fraction(valeur)


def texte_de_cadence(valeur: Fraction, ascii_seul: bool = False) -> str:
    """La cadence telle que `E2-2` l'ecrit : `25`, `12,5`, `8,333`, `6,25`.

    **C'est un rendu, et il ne remonte jamais dans le modele.** La virgule est
    celle de la langue de travail, les zeros de queue tombent, et `25/3` s'ecrit
    `8,333` -- trois decimales, comme la maquette. La valeur gardee, elle, reste
    la `Fraction` exacte : c'est elle qui compte les frames et c'est la
    convention `_25s3` de `EPIC11-ARB-62`, pas ce texte, qui nommera le lot.

    `ascii_seul` ne change rien ici -- la virgule est deja de l'ASCII -- mais
    l'argument est porte quand meme : toute fonction de rendu de ce module
    prend les deux regimes, sans quoi un appelant devrait savoir lesquelles en
    ont besoin.
    """
    texte = f"{float(valeur):.{DECIMALES_AFFICHEES}f}"
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    texte = texte.replace(".", ",")
    return jetons.replier_ascii(texte) if ascii_seul else texte


def libelle_remarquable(diviseur: int) -> str:
    """`source`, `source / 2`, `source / 3`, `source / 4` -- texte de `E2-2`."""
    if diviseur == 1:
        return LIBELLE_DE_LA_SOURCE
    return LIBELLE_D_UNE_DIVISION.format(diviseur=diviseur)


def nom_court_de_cadence(valeur: Fraction) -> str:
    """Le fragment de cadence d'un identifiant de lot (`EPIC11-ARB-62`).

    C'est **le** point ou la convention de nommage d'une cadence est ecrite, et
    il vit ici plutot que dans `io/naming.py` parce que c'est ici que la cadence
    est encore une `Fraction` exacte. `naming.build_lot_id` la recoit en
    `float` : `25/3` y arrive en `8.333333333333334` et rend
    `rush_01_8p333333333333334`, dix-sept chiffres d'artefact ou l'operateur
    attendait « une image sur trois ».

    Trois familles, et une seule regle : **le nom est une fonction de la seule
    valeur**, jamais du chemin par lequel elle a ete saisie.

    * cadence entiere -> `25` ;
    * developpement decimal **fini** -> `12p5`, `6p25`, la forme exacte de
      `naming.format_fps_short`, qui est celle des lots deja livres ;
    * developpement decimal **infini** -> `25s3`, `8000s1001` : le numerateur,
      :data:`SEPARATEUR_DE_NOMMAGE`, le denominateur de la fraction reduite.

    **Deux cadences differentes ne peuvent pas rendre le meme nom.** Les trois
    familles sont disjointes par leurs caracteres (`p` dans l'une, `s` dans
    l'autre, ni l'un ni l'autre dans la troisieme), l'ecriture decimale finie
    d'un rationnel est unique une fois ses zeros de queue tombes, et une
    fraction reduite l'est aussi. Un banc le mesure sur des milliers de
    cadences plutot que sur cette phrase.

    **La forme `s` n'est pas un pis-aller : c'est celle qui parle.** Sur une
    source a 25 im/s, « une image sur trois » s'ecrit `25s3` -- exactement ce
    que l'operateur a tape (`25/3`, `c/3`, `cs3`). Sur une source NTSC
    (`24000/1001`) elle s'ecrit `8000s1001`, qui ne dit plus « sur trois » mais
    reste exacte, courte et unique ; dire « sur trois » y exigerait d'ecrire la
    source dans le nom, donc de faire dependre le nom d'autre chose que de la
    valeur -- et deux lots de meme cadence issus de deux qualifications
    differentes porteraient deux noms.
    """
    valeur = _en_fraction(valeur, "une cadence")
    signe = "-" if valeur < 0 else ""
    absolue = -valeur if valeur < 0 else valeur

    if absolue.denominator == 1:
        return f"{signe}{absolue.numerator}"

    # Un rationnel a un developpement decimal fini si et seulement si son
    # denominateur reduit ne porte que des 2 et des 5. C'est le test exact, et
    # il remplace le garde-fou ecrit puis RETIRE de cette vague, qui REFUSAIT
    # le developpement infini : ce refus marchait sur un rush a 25 im/s et
    # refusait, sur un rush NTSC, la cadence SOURCE elle-meme -- la ligne
    # « (toutes) ». Ici, le developpement infini n'est pas refuse, il est
    # NOMME.
    reste = absolue.denominator
    for facteur in (2, 5):
        while reste % facteur == 0:
            reste //= facteur
    if reste != 1:
        return (f"{signe}{absolue.numerator}{SEPARATEUR_DE_NOMMAGE}"
                f"{absolue.denominator}")

    # Developpement fini : on multiplie par 10 jusqu'a tomber sur un entier.
    # Le calcul est EXACT (jamais un `float`, dont le repr rend `8.333...4`),
    # et il s'arrete au premier exposant qui suffit, donc le resultat ne porte
    # aucun zero de queue -- ce qui est exactement ce que `format_fps_short`
    # obtient par `rstrip("0")`.
    decimales = 0
    entier = absolue
    while entier.denominator != 1:
        entier *= 10
        decimales += 1
    chiffres = str(entier.numerator).rjust(decimales + 1, "0")
    return f"{signe}{chiffres[:-decimales]}p{chiffres[-decimales:]}"


@dataclass(frozen=True)
class Colonnes:
    """La geometrie d'une ligne, **mesuree sur les maquettes**.

    Les deux temps de l'atelier n'ont pas les memes colonnes -- `E2-2` porte un
    libelle (`source / 2`) que `E2-2c` remplace par un suffixe (`25 fps`) -- et
    c'est la seule chose qui les distingue. Deux calibrations d'une meme mise en
    page, donc, plutot que deux fonctions de rendu qui divergeraient.

    Toutes les valeurs sont des largeurs de champ, en colonnes, a partir de la
    fin de la tete (curseur, case a cocher) qui en occupe neuf.
    """

    valeur: int
    libelle: int
    creux_mention: int
    suffixe: str = ""


#: `E2-2`, temps 1. Mesure : valeur en 9, libelle en 19, compte cale a droite en
#: 47, mention en 55.
COLONNES_DU_CHOIX = Colonnes(valeur=10, libelle=18, creux_mention=8)

#: `E2-2c`, temps 2. Mesure : valeur en 9 (suffixee ` fps`), pas de libelle,
#: compte cale a droite en 35, mention en 39.
COLONNES_DE_L_EXTRACTION = Colonnes(
    valeur=16, libelle=0, creux_mention=4, suffixe=" fps")

#: Colonne ou commence la tete d'une ligne, comme dans l'explorateur : trois
#: blancs, le curseur, un blanc, la case, un blanc.
_INDENT = 5
#: Deux colonnes de respiration au bord droit, comme partout ailleurs.
_MARGE_DROITE = 2
#: Largeur de la case a cocher, `[x]` comme `[ ]`.
_LARGEUR_DE_LA_CASE = 3


@dataclass
class Cadence:
    """Une cadence de la liste : sa valeur, son compte, et ce qui la refuse.

    ``compte`` et ``motif`` s'excluent, et l'un des deux est obligatoire : une
    cadence sans compte ni motif serait une ligne qui ne dit rien, et une
    cadence portant les deux serait une ligne qui se contredit. Les deux cas
    sont refuses **a la construction** plutot que signales en revue.

    ``mention`` est la colonne de droite libre : `(toutes)` sur la source en
    `E2-2`, le verdict de previz en `E2-2c`. Le modele ne la fabrique pas -- il
    ne connait ni la previz ni ses seuils --, il la porte.
    """

    valeur: Fraction
    libelle: str
    compte: int | None = None
    motif: str | None = None
    cochee: bool = False
    mention: str = ""

    def __post_init__(self) -> None:
        self.valeur = _en_fraction(self.valeur, "une cadence")
        if (self.compte is None) == (self.motif is None):
            raise CadencesMalFormees(
                f"La cadence {self.libelle!r} porte compte={self.compte!r} et "
                f"motif={self.motif!r} : une cadence porte son compte OU le "
                "motif du coeur qui la refuse, jamais les deux ni aucun."
            )
        if self.compte is not None and self.compte < 1:
            # F1 de la fiche : `ceil(window_frame_count / step)` avec
            # `window_frame_count >= 1` et `step > 0` rend 1 au minimum,
            # toujours -- mesure faite sur une source d'UNE frame et
            # `fps_target=0.001`. Un compte a zero ne vient donc pas du coeur :
            # c'est une erreur d'appariement, et elle se leve ici.
            raise CadencesMalFormees(
                f"La cadence {self.libelle!r} annonce {self.compte} frame(s) : "
                "le coeur en rend 1 au minimum, toujours (frame_selection.py, "
                "ceil(window_frame_count / step))."
            )
        if self.cochee and self.refusee:
            raise CadencesMalFormees(
                f"La cadence {self.libelle!r} est cochee alors que le coeur la "
                f"refuse : {self.motif}"
            )

    @property
    def refusee(self) -> bool:
        return self.motif is not None

    @property
    def cochable(self) -> bool:
        """AC 3.5 : une cadence que le coeur refuse n'est **pas** cochable."""
        return not self.refusee

    def texte_de_valeur(self, ascii_seul: bool = False, suffixe: str = "") -> str:
        return texte_de_cadence(self.valeur, ascii_seul) + suffixe

    def nom_court(self) -> str:
        """Le fragment de cadence du nom de son lot (`EPIC11-ARB-62`).

        C'est ce que l'ecriture passera en `fps_short_name=` a
        `io.naming.build_lot_id` : la cadence est encore exacte ici, elle ne
        l'est plus la-bas.
        """
        return nom_court_de_cadence(self.valeur)

    def texte_du_compte(self, ascii_seul: bool = False) -> str:
        """`124 frames`, texte de `E2-2`. Vide quand la cadence est refusee."""
        if self.compte is None:
            return ""
        return f"{self.compte} frame{'s' if self.compte > 1 else ''}"


@dataclass(frozen=True)
class Validation:
    """Ce que rend une validation : les cochees, ou un refus **nomme**.

    AC 3.6. Rendre une liste vide et rien d'autre laisserait l'appelant libre de
    continuer sans rien remarquer ; le motif force a le lire.
    """

    cochees: tuple[Cadence, ...] = ()
    motif: str | None = None

    @property
    def passe(self) -> bool:
        return self.motif is None


@dataclass
class ListeDeCadences:
    """La liste cochable : des cadences, un curseur, une fenetre.

    ``compteur`` est le seul chemin par lequel un compte de frames entre ici. Il
    rend le cardinal d'une cadence ou leve un :data:`REFUS_DU_COEUR` ; le
    modele ne l'interprete pas, il le porte.
    """

    cadences: list[Cadence]
    compteur: Compteur
    curseur: int = 0
    premier_visible: int = field(default=0)
    #: La cadence source du rush, quand la liste la connait. Elle sert **au
    #: seul** libelle des divisions saisies (`c/6` -> `cadence/6`) et n'est
    #: jamais une cadence de la liste : celles-la sont dans `cadences`. Une
    #: liste batie a la main peut l'ignorer, et alors un alias est refuse
    #: nommement (:data:`MOTIF_SOURCE_INCONNUE`) plutot que devine.
    fps_source: Fraction | None = None

    def __post_init__(self) -> None:
        if not self.cadences:
            raise CadencesMalFormees(
                "Une liste de cadences porte au moins une cadence ; une liste "
                "vide n'est pas un choix, c'est un ecran sans objet."
            )
        valeurs = [cadence.valeur for cadence in self.cadences]
        if len(set(valeurs)) != len(valeurs):
            # Meme motif que l'AC 3.7, mais pris a la construction : deux lignes
            # de meme valeur produiraient deux lots portant le meme nom.
            raise CadencesMalFormees(
                f"Deux cadences portent la meme valeur : "
                f"{[texte_de_cadence(v) for v in valeurs]}")

    # -- construction --------------------------------------------------------

    @classmethod
    def remarquables(cls, fps_source: Fraction,
                     compteur: Compteur) -> "ListeDeCadences":
        """AC 3.1 : la liste preremplie des cadences remarquables.

        ``fps_source`` est **lue du coeur** -- `PrevizSession.fps_source`, qui
        vient de la qualification du rush --, elle n'est jamais saisie. Les
        diviseurs viennent de :data:`DIVISEURS_REMARQUABLES` et de nulle part
        ailleurs : c'est ce que mesure le test qui remplace la constante.

        **Aucune cadence n'est precochee.** `EPIC11-ARB-7` le dit des issues
        d'un point de decision (« Une issue preselectionnee transforme `Entree`
        en accident ») et la raison vaut mot pour mot ici : une liste prechoisie
        ferait extraire le choix de quelqu'un d'autre.
        """
        fps_source = _en_fraction(fps_source, "la cadence source")
        cadences = []
        for diviseur in DIVISEURS_REMARQUABLES:
            valeur = fps_source / diviseur
            compte, motif = _mesurer(compteur, valeur)
            cadences.append(Cadence(
                valeur=valeur,
                libelle=libelle_remarquable(diviseur),
                compte=compte,
                motif=motif,
                mention=MENTION_TOUTES if diviseur == 1 else "",
            ))
        # La source est RETENUE : c'est elle qui fera lire `c/6` comme
        # `cadence/6` a la saisie. La liste ne la recalcule pas depuis sa
        # premiere ligne -- « la premiere ligne est la source » serait un
        # invariant de presentation utilise comme donnee.
        return cls(cadences=cadences, compteur=compteur, fps_source=fps_source)

    # -- lecture -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.cadences)

    @property
    def courante(self) -> Cadence:
        return self.cadences[self.curseur]

    @property
    def cochees(self) -> tuple[Cadence, ...]:
        return tuple(cadence for cadence in self.cadences if cadence.cochee)

    @property
    def nombre_de_cochees(self) -> int:
        return len(self.cochees)

    @property
    def frames_cochees(self) -> int:
        """La **somme** des comptes des cochees. Aucun produit, jamais.

        `EPIC11-ARB-30`, verbatim : « le noyau ne derive **jamais** le cardinal
        d'une duree, il l'exige ». Une cochee sans compte est impossible : le
        cochage d'une cadence refusee est refuse (AC 3.5), et une cadence porte
        toujours l'un des deux.
        """
        return sum(cadence.compte or 0 for cadence in self.cochees)

    def rang(self, valeur: Fraction) -> int | None:
        """Le rang de la cadence de cette valeur exacte, ou ``None``."""
        valeur = _en_fraction(valeur, "une cadence")
        for rang, cadence in enumerate(self.cadences):
            if cadence.valeur == valeur:
                return rang
        return None

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓` : le curseur reste dans la liste, il n'en sort jamais."""
        self.curseur = min(max(self.curseur + pas, 0), len(self.cadences) - 1)
        self._recadrer()

    def viser(self, valeur: Fraction) -> Cadence:
        """Placer le curseur sur une cadence **nommee par sa valeur**.

        Meme geste que `ChoixExclusif.viser` et meme motif : c'est le chemin
        qu'un operateur parcourt avec les fleches, donc le chemin qu'un test
        doit emprunter. Un `next()` nu remonterait en « StopIteration », qui ne
        nomme ni la valeur demandee ni celles qui existent.
        """
        rang = self.rang(valeur)
        if rang is None:
            connues = [texte_de_cadence(c.valeur) for c in self.cadences]
            raise CadencesMalFormees(
                f"Aucune cadence ne vaut {texte_de_cadence(Fraction(valeur))} ;"
                f" connues : {connues}.")
        self.curseur = rang
        self._recadrer()
        return self.cadences[rang]

    # -- ecriture ------------------------------------------------------------

    def basculer(self) -> str | None:
        """`Espace` coche et decoche la cadence **sous le curseur** (AC 3.3).

        `EPIC11-ARB-45` retire la case a cocher de **tout ecran a issue
        unique** (« il n'y a plus de case a cocher », « `Espace` n'a plus de
        role ») ; cette liste-ci n'en est pas un, et c'est la frontiere que la
        story rend visible : ici `Espace` garde son role, et la case avec.

        Rend le motif du coeur quand la cadence est refusee -- elle n'est pas
        cochable (AC 3.5) --, et ``None`` quand la bascule a eu lieu.
        """
        cadence = self.courante
        if not cadence.cochable:
            return cadence.motif
        cadence.cochee = not cadence.cochee
        return None

    def ajouter(self, texte: str) -> str | None:
        """`a` ajoute une cadence libre, decimale **ou fractionnaire** (AC 3.4).

        Rend le motif du refus de la **saisie**, ou ``None`` quand la cadence
        entre dans la liste. Quatre refus de saisie, tous nommes : ce qui n'est
        ni un decimal ni une division, le diviseur nul, l'alias de source dans
        une liste qui ignore sa source, et le doublon (AC 3.7).

        **Le libelle vient de la saisie, pas de la valeur.** `25/5` sur une
        source a 25 im/s donne `cadence/5` ; `5` tape tout court donne `libre`,
        et les deux portent pourtant la meme valeur. Ce n'est pas une
        incoherence, c'est ce qu'Egan a demande : le libelle dit ce que
        l'operateur a ecrit. Le NOM du lot, lui, ne depend que de la valeur
        (:func:`nom_court_de_cadence`) -- les deux saisies produiraient donc le
        meme lot, et c'est le doublon de l'AC 3.7 qui empeche qu'elles
        coexistent.

        **Une cadence que le COEUR refuse entre quand meme dans la liste**, et
        c'est le fond de l'AC 3.5 : elle s'y voit, marquee refusee et non
        cochable, avec le message du coeur sur sa ligne. La sortir de la liste
        remplacerait ce refus visible par un message qui passe, c'est-a-dire par
        rien.

        Le curseur suit la cadence ajoutee : c'est elle qu'on vient de demander,
        et elle est en fin de liste -- donc hors de la fenetre des qu'il y a
        plus de quatre cadences.
        """
        valeur, libelle, motif = analyser_la_saisie(texte, self.fps_source)
        if motif is not None:
            return motif
        if self.rang(valeur) is not None:
            return MOTIF_DOUBLON
        compte, motif_du_coeur = _mesurer(self.compteur, valeur)
        self.cadences.append(Cadence(
            valeur=valeur, libelle=libelle,
            compte=compte, motif=motif_du_coeur))
        self.curseur = len(self.cadences) - 1
        self._recadrer()
        return None

    def valider(self) -> Validation:
        """AC 3.6 : zero cochee ne passe **jamais** en silence."""
        cochees = self.cochees
        if not cochees:
            return Validation(motif=MOTIF_AUCUNE_COCHEE)
        return Validation(cochees=cochees)

    # -- ce que la fenetre montre -------------------------------------------

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        **Le calcul vit dans `jetons`, pas ici** : c'etait le meme que celui de
        l'explorateur, recopie, et la liste des rushes en aurait fait une
        troisieme redaction. La raison reste la sienne -- la ligne `…` se
        reserve **avant** le decoupage, sans quoi la derniere cadence se
        cacherait derriere le `…` qui annonce qu'elle existe.
        """
        return jetons.fenetre_de_liste(len(self.cadences),
                                       self.premier_visible, HAUTEUR_LISTE)

    def _recadrer(self) -> None:
        """Faire suivre la fenetre au curseur, d'un rang a la fois."""
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.cadences),
            HAUTEUR_LISTE)

    # -- rendu ---------------------------------------------------------------

    def lignes(self, largeur: int = jetons.LARGEUR_PLANCHER,
               ascii_seul: bool = False,
               colonnes: Colonnes = COLONNES_DU_CHOIX) -> list[str]:
        """La zone de liste, une ligne vide, puis le rappel des cochees.

        C'est le bloc que `E2-2` montre entre le titre et le filet des bornes.
        :meth:`rang_du_curseur` et :meth:`etats_des_lignes` indexent **cette**
        liste-ci : un second reperage tenu ailleurs divergerait du premier.
        """
        utile = jetons.largeur_utile(largeur)
        return (self.lignes_de_liste(utile, ascii_seul, colonnes)
                + ["", self.ligne_de_compte(ascii_seul)])

    def lignes_de_liste(self, utile: int = jetons.largeur_utile(),
                        ascii_seul: bool = False,
                        colonnes: Colonnes = COLONNES_DU_CHOIX) -> list[str]:
        """Les :data:`HAUTEUR_LISTE` lignes de la zone, `…` compris."""
        total = len(self.cadences)
        premier, dernier = self.fenetre()
        points = jetons.points_d_abregement(ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(" " * _INDENT + points)
        for rang in range(premier, dernier + 1):
            rendues.append(self.ligne(rang, utile, ascii_seul, colonnes))
        if dernier < total - 1:
            position = f"{premier + 1}-{dernier + 1} sur {total} cadences"
            tete = " " * _INDENT + points
            creux = utile - _MARGE_DROITE - len(tete) - jetons.colonnes(position)
            rendues.append(tete + " " * max(jetons.CREUX_MINIMAL, creux)
                           + position)
        return rendues + [""] * (HAUTEUR_LISTE - len(rendues))

    def ligne(self, rang: int, utile: int = jetons.largeur_utile(),
              ascii_seul: bool = False,
              colonnes: Colonnes = COLONNES_DU_CHOIX) -> str:
        """Une ligne de cadence, aux colonnes de la maquette.

        La case a cocher laisse la place au glyphe `absent` quand le coeur
        refuse la cadence, **au milieu des trois colonnes** -- la ou se tient la
        marque de `[x]`. C'est le second canal de `DESIGN.md` section 6 : l'etat
        se lit sans couleur, et il ne se lit pas comme une case vide, qui
        inviterait a cocher ce qui n'est pas cochable.

        Le motif du coeur, lui, s'abrege **par la fin** (`jetons.ajuster`) et
        non au milieu comme un nom : le sens d'un message est a son debut, et
        c'est le debut qu'un operateur lit avant d'aller chercher la ligne
        d'etat, qui le porte en entier.
        """
        table = jetons.glyphes(ascii_seul)
        cadence = self.cadences[rang]
        if cadence.refusee:
            case = f" {table['absent']} "
        else:
            case = table["coche" if cadence.cochee else "decoche"]
        curseur = table["curseur"] if rang == self.curseur else " "
        tete = (" " * (_INDENT - 2) + curseur + " "
                + _cale(case, _LARGEUR_DE_LA_CASE, ascii_seul) + " ")
        valeur = cadence.texte_de_valeur(ascii_seul, colonnes.suffixe)
        gauche = tete + _cale(valeur, colonnes.valeur, ascii_seul)
        if colonnes.libelle:
            libelle = cadence.libelle
            if ascii_seul:
                libelle = jetons.replier_ascii(libelle)
            gauche += _cale(libelle, colonnes.libelle, ascii_seul)
        place = utile - _MARGE_DROITE - jetons.colonnes(gauche)
        if cadence.refusee:
            return (gauche + jetons.ajuster(cadence.motif or "", place,
                                            ascii_seul)).rstrip()
        # La colonne du compte est bornee par la place restante avant de l'etre
        # par sa largeur nominale : sur une fenetre etroite, un champ cale a dix
        # colonnes ferait deborder la ligne par son seul remplissage.
        largeur_du_compte = min(LARGEUR_DU_COMPTE, max(place, 0))
        compte = jetons.ajuster(cadence.texte_du_compte(ascii_seul),
                                largeur_du_compte, ascii_seul)
        droite = " " * (largeur_du_compte - jetons.colonnes(compte)) + compte
        mention = cadence.mention
        if mention:
            if ascii_seul:
                mention = jetons.replier_ascii(mention)
            reste = place - jetons.colonnes(droite) - colonnes.creux_mention
            mention = " " * colonnes.creux_mention + jetons.ajuster(
                mention, reste, ascii_seul)
        return (gauche + droite + mention).rstrip()

    def ligne_de_compte(self, ascii_seul: bool = False) -> str:
        """AC 3.3 : le compte des cochees, rappele **sous la liste**.

        Texte de `E2-2`, verbatim : « 3 cochées sur 8 · 228 frames ».
        """
        nombre = self.nombre_de_cochees
        frames = self.frames_cochees
        texte = (f"{nombre} cochée{'s' if nombre > 1 else ''} sur "
                 f"{len(self.cadences)} · {frames} frame"
                 f"{'s' if frames > 1 else ''}")
        return " " * _INDENT + (jetons.replier_ascii(texte) if ascii_seul
                                else texte)

    def ligne_des_lots(self, ascii_seul: bool = False) -> str:
        """Le rappel du temps 2 ; texte de `E2-2c` : « 2 cadences cochées → 2
        lots ».

        Une cochee, un lot : `run_extraction` prend **un** `fps_target`, et « 2
        cadences cochees -> 2 lots » est N invocations. Le rappel dit donc le
        nombre de lots que la validation produira, la ou celui du temps 1 dit le
        nombre de frames qu'il y aura a regarder.
        """
        nombre = self.nombre_de_cochees
        texte = (f"{nombre} cadence{'s' if nombre > 1 else ''} "
                 f"cochée{'s' if nombre > 1 else ''} → "
                 f"{nombre} lot{'s' if nombre > 1 else ''}")
        return " " * _INDENT + (jetons.replier_ascii(texte) if ascii_seul
                                else texte)

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes`, de la ligne a peindre en accentuation.

        **Passe explicitement a `jetons.peindre`, jamais devine** : son
        auto-detection teste `startswith` sur le glyphe de curseur, et ces
        lignes-ci sont indentees de trois blancs -- elle ne trouverait rien, en
        silence.
        """
        premier, dernier = self.fenetre()
        if not premier <= self.curseur <= dernier:
            return None
        return (1 if premier > 0 else 0) + (self.curseur - premier)

    def etats_des_lignes(self) -> dict[int, str]:
        """L'etat de chaque ligne refusee, par rang dans :meth:`lignes`.

        `EPIC11-ARB-71` : la couleur est **posee** la ou l'on sait qu'on ecrit
        un etat, au lieu d'etre retrouvee dans un texte. Le glyphe d'une ligne
        de liste est precede d'un blanc unique, donc le repli par motif de
        `jetons.jeton_d_etat` ne le verrait pas : sans cette table, aucune
        cadence refusee ne serait coloree.
        """
        premier, dernier = self.fenetre()
        decalage = 1 if premier > 0 else 0
        return {decalage + (rang - premier): "absent"
                for rang in range(premier, dernier + 1)
                if self.cadences[rang].refusee}


def _cale(texte: str, largeur: int, ascii_seul: bool) -> str:
    """Un champ de largeur fixe, mesure en **colonnes** et jamais en `len()`.

    Un ideogramme occupe deux colonnes et une marque combinante zero :
    `str.ljust` calerait un champ de dix caracteres sur vingt colonnes, et
    toutes les colonnes de droite de la ligne partiraient avec.
    """
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return texte + " " * max(0, largeur - jetons.colonnes(texte))


def _mesurer(compteur: Compteur, valeur: Fraction) -> tuple[int | None, str | None]:
    """Le compte de la cadence, ou le motif du coeur qui la refuse.

    **Le message n'est jamais reecrit** (AC 3.4) : `str(erreur)` traverse tel
    quel. Deux redactions du meme refus divergeraient, et c'est le coeur qui
    sait pourquoi il refuse -- le plafond de 1000 images va jusqu'a proposer la
    cadence qui rentrerait, chose qu'une interface ne saurait pas recalculer.
    """
    try:
        return int(compteur(valeur)), None
    except REFUS_DU_COEUR as refus:
        return None, str(refus)


def analyser_la_saisie(
    texte: str, fps_source: Fraction | None = None,
) -> tuple[Fraction | None, str, str | None]:
    """La saisie libre, en `(valeur, libelle, motif)`.

    **La grammaire, verbatim d'Egan (2026-08-30)** : « J'aimerais que
    l'utilisateur puisse ecrire "cadence/[nombre entier]" (avec cadence en
    toutes lettres), ou bien "c/[nombre entier]" avec l'abreviation "c/", puisse
    ecrire "[nombre entier]/[autre nombre entier]" ou encore remplacer le slash
    par un s (donc "cs[nombre entier]" ou encore "cadences[nombre entier]" ou
    encore "[nombre entier]s[nombre entier]"). »

    **La regle du libelle, tiree de ses exemples** : le numerateur qui **vaut la
    cadence source** donne `cadence/N` ; sinon `libre`. Ses cinq exemples font
    foi, et le banc les reprend un a un :

    ====================  ==================  ================
    saisie                valeur              libelle
    ====================  ==================  ================
    ``25/5``              5                   ``cadence/5``
    ``2500/634``          ~3,943              ``libre``
    ``cs6``               source / 6          ``cadence/6``
    ``25s6``              idem                ``cadence/6``
    ``cadences6``         idem                ``cadence/6``
    ====================  ==================  ================

    Un alias (`cadence`, `cadences`, `c`, `cs`) **est** la cadence source : il
    donne donc toujours `cadence/N`, y compris quand la source n'est pas un
    entier -- c'est ce qui fait passer `c/2` sur un rush NTSC.

    **La garde separateur precede la conversion**, et ce n'est pas un detail
    d'ordre : `Fraction("25/3")` reussit tout comme `Fraction("-25/3")`. Posee
    apres, elle ne verrait jamais rien, et une saisie que la grammaire a
    refusee entrerait par la porte de derriere avec le libelle `libre`.

    Ce qui n'est **pas** filtre ici : les cadences nulles, negatives ou
    superieures a la source. Ce sont des refus du **coeur** (AC 3.5), et les
    doubler ici ferait une seconde regle, avec ses propres mots. Le diviseur
    nul, lui, l'est : le coeur ne verrait jamais la cadence, il n'y a pas de
    valeur a lui soumettre.
    """
    texte = (texte or "").strip().replace(",", ".").lower()
    if not texte:
        return None, LIBELLE_LIBRE, MOTIF_PAS_UN_NOMBRE

    division = MOTIF_DE_DIVISION.match(texte)
    if division is not None:
        return _resoudre_une_division(division, fps_source)

    if any(sep in texte for sep in SEPARATEURS_A_NE_JAMAIS_CONVERTIR):
        return None, LIBELLE_LIBRE, MOTIF_PAS_UN_NOMBRE
    try:
        return Fraction(texte), LIBELLE_LIBRE, None
    except (ValueError, ZeroDivisionError, OverflowError):
        # `Fraction("inf")` et `Fraction("nan")` levent : la cadence non finie
        # n'a donc aucune ecriture decimale, et elle est refusee ici plutot que
        # par `InvalidFrameRateError` -- le coeur ne la voit jamais.
        return None, LIBELLE_LIBRE, MOTIF_PAS_UN_NOMBRE


def _resoudre_une_division(
    division: "re.Match[str]", fps_source: Fraction | None,
) -> tuple[Fraction | None, str, str | None]:
    """Une division reconnue par :data:`MOTIF_DE_DIVISION`, resolue.

    Deux entrees possibles dans le numerateur -- un alias de la source ou un
    entier -- et **une seule** regle de libelle, appliquee aux deux : le
    numerateur vaut la cadence source, ou il ne la vaut pas. Ecrire la regle une
    fois pour l'alias et une fois pour l'entier en ferait deux, qui
    divergeraient : `25/5` sur une source a 25 doit donner exactement ce que
    `c/5` donne.
    """
    diviseur = int(division.group("denominateur"))
    if diviseur == 0:
        return None, LIBELLE_LIBRE, MOTIF_DIVISEUR_NUL

    if division.group("source") is not None:
        if fps_source is None:
            return None, LIBELLE_LIBRE, MOTIF_SOURCE_INCONNUE
        numerateur = _en_fraction(fps_source, "la cadence source")
    else:
        numerateur = Fraction(int(division.group("numerateur")))

    valeur = numerateur / diviseur
    if fps_source is not None and numerateur == _en_fraction(
            fps_source, "la cadence source"):
        libelle = LIBELLE_D_UNE_DIVISION_DE_LA_SOURCE.format(diviseur=diviseur)
    else:
        libelle = LIBELLE_LIBRE
    return valeur, libelle, None
