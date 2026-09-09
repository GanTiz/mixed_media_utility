# -*- coding: utf-8 -*-
"""L'atelier Pdf, ecrans `E5-3b` et `E5-3c` : le conflit de tirage.

Story 11.7, **lot G** (AC 7). Un PDF de planches porte deja le nom que la passe
s'apprete a ecrire : l'operateur tranche ici, **et il tranche toujours entre
plusieurs issues** (`EPIC11-ARB-89`, verbatim d'Egan : « au lieu d'un overwrite
destructif, toujours proposer un versionnage [...] Mais toujours permettre une
reecriture plutot qu'un blocage sec »).

**Un seul ecran, deux etats.** `E5-3b` et `E5-3c` sont le meme conflit : meme
lot, meme tirage, meme date. Seule la ligne `Scanné` change -- et avec elle la
liste des issues, qui perd `Remplacer ce tirage`. Les deux maquettes sont donc
rendues par **une** classe : faire deux ecrans separes aurait laissé la
frontiere negative (« l'ecrasement n'est pas offert ») mesurer un chemin de code
different de celui qui l'offre, c'est-a-dire ne rien mesurer du tout.

**Ce que ce module NE fait PAS, et c'est structurel :**

* il **ne calcule aucun rang**. `EPIC11-ARB-92`, verbatim d'Egan : « **il ne
  faut pas rendre le rang** ». Le rang du prochain tirage est **donne** a
  :class:`TirageEnConflit` par celui qui a interroge le coeur ; ce module
  l'affiche. La frontiere AST du lot C (`test_atelier_pdf_menu.py`) interdit
  jusqu'au **nom** des fonctions de calcul dans tout `tui/`, donc l'appel lui
  meme vit hors d'ici -- et c'est la forme la plus forte : un ecran qui ne
  connait pas le vocabulaire du calcul ne peut pas le reecrire par distraction ;
* il **ne deduit pas « scanne » de l'etat du LOT** (`EPIC11-ARB-176`, tranche
  par Egan le 2026-09-02). Un tirage n'est protege que s'il a **lui-meme** ete
  scanne : la deduction se fait **au rang**, en lisant
  `lots[].scanned_version_ranks` -- l'ensemble des rangs effectivement lus au QR,
  que `io/scan_manifest.py` persiste depuis le meme jour. Deduire du lot
  refuserait d'ecraser un `v4` jamais imprime au motif que le `v3` du meme lot a
  ete scanne : un blocage sec sur un objet innocent ;
* il **n'importe jamais `cli`** (frontiere de la story 11.4b) ;
* il **ne cable rien dans `atelier_pdf.py`** : le parcours se monte en un seul
  endroit, au lot I. Ce module rend des ecrans montables, et rien de plus.

**L'issue de masse et ses trois contraintes** (`EPIC11-ARB-177`, Egan :
« Excellente proposition : le choix 3 »). L'ecran reste **par lot** et gagne
« Appliquer ce choix aux N conflits restants ». Les trois contraintes que
l'arbitrage tire d'`EPIC11-ARB-89` sont tenues **par le code**, chacune a son
endroit :

1. **jamais la premiere issue atteinte** -- elle est posee apres l'issue
   unitaire, et `ChoixExclusif.__post_init__` deplace de toute facon le curseur
   hors des issues qui ecrivent ;
2. **elle nomme ce qu'elle emporte en cardinal ET en poids** -- voir
   :func:`consequence_de_la_masse`. « Un `appliquer aux 4 restants` muet sur les
   megaoctets serait moins informatif que l'ecran qu'il remplace, ce qui est
   l'inverse du but » ;
3. **elle reste une issue parmi d'autres** -- les issues unitaires demeurent.

**Et elle SAUTE les tirages scannes en le disant** (meme arbitrage, tranche
apres coup le 2026-09-02 : Egan a retenu « sauter en le disant »). Le compte
saute est **affiche**, jamais seulement journalise : « un lot ecarte sans que
l'ecran le nomme serait une decision cachee ».

**L'ordre des N conflits est « par lot »** -- reponse d'Egan du 2026-09-02, mot
pour mot, au dernier point qu'`EPIC11-ARB-177` laissait ouvert. C'est un ordre
**choisi**, et :func:`ordonner_par_lot` existe pour qu'il soit choisi une fois
plutot que subi : sans elle, l'ordre serait celui de `lots[]` du manifeste,
c'est-a-dire l'ordre de premiere creation des lots, qui ne veut rien dire pour
qui tranche des conflits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import pdf_manifest, scan_manifest
from . import jetons, projet_lecture
from .atelier_scan import INDENT_DU_CURSEUR, LARGEUR_DU_LIBELLE
from .coque import ObjetTravaille, Palier
from .panneau import ChoixExclusif, Issue

# ===========================================================================
# La grille du cartouche -- trois colonnes, comme la maquette les dessine
# ===========================================================================

#: Largeur de la colonne de la **valeur** du cartouche : `plan-04_25`, `· non`,
#: `26/08 à 16:22`. La glose commence donc toujours a la meme colonne, ce qui
#: est ce qui rend les cinq lignes lisibles en colonnes. La colonne du libelle,
#: elle, est celle du formulaire de l'atelier Scan (`LARGEUR_DU_LIBELLE`) et
#: n'est pas redigee ici : deux redactions du meme calage divergeraient au
#: premier reglage.
LARGEUR_DE_LA_VALEUR = 17

#: L'indentation d'une ligne de **consequence** d'issue (`▲ efface les 352 Mo
#: écrits`). Elle est **derivee** de celle du curseur plutot que tapee : les
#: deux se decalent ensemble le jour ou la maquette bouge.
INDENT_DE_LA_CONSEQUENCE = INDENT_DU_CURSEUR + " " * 4

#: Les libelles de la colonne de gauche du cartouche, dans l'ordre de la
#: maquette. Ce sont des constantes de module et non des litteraux au point
#: d'usage : c'est ce qui les fait balayer par les gardes d'epic (repli ASCII,
#: majuscules des raccourcis).
LIBELLE_DU_LOT = "Lot"
LIBELLE_DE_LA_DATE = "Écrit le"
LIBELLE_DU_CONTENU = "Contient"
LIBELLE_DE_LA_MISE_EN_PAGE = "Mise en page"
LIBELLE_DU_SCAN = "Scanné"

#: La glose de la ligne `Mise en page` quand le tirage present a ete compose
#: sous la mise en page que la passe s'apprete a employer. C'est le seul cas ou
#: le conflit se produit : deux mises en page differentes ecrivent deux fichiers
#: differents (`EPIC11-ARB-171`), et cet ecran ne se monterait pas.
GLOSE_MEME_MISE_EN_PAGE = "la même qu'aujourd'hui"

#: La glose de la ligne `Scanné`, dans ses deux etats. **Elle porte sur le
#: TIRAGE, jamais sur le lot** : c'est tout l'objet d'`EPIC11-ARB-176`, et la
#: redaction « aucun scan ne cite ce lot » d'avant cet arbitrage disait le
#: contraire de ce que le produit mesure.
GLOSE_SANS_SCAN = "aucun scan ne cite ce tirage"
GLOSE_DU_SCAN = "un scan cite ce tirage"

#: Le mot que porte la valeur de la ligne `Scanné`. Le glyphe qui le precede est
#: **neutre** au non et **avertisseur** au oui : un tirage non scanne n'est ni un
#: manque ni un refus, c'est le cas courant, et une ligne rouge sonnerait
#: l'alarme sur le seul etat qui autorise l'ecrasement.
VALEUR_NON_SCANNE = "non"
VALEUR_SCANNE = "oui"

#: Le nombre d'octets d'un megaoctet, ecrit une fois. La taille d'un tirage se
#: lit sur le disque -- le manifeste n'en porte aucune, et son idempotence est
#: verifiee octet a octet, precisement pour qu'il n'en porte pas.
OCTETS_PAR_MO = 1_000_000

#: Le format de la date d'ecriture d'un tirage : jour, mois, heure, comme la
#: maquette. Ce n'est **pas** `projet_lecture.date_courte`, et le motif n'est pas
#: la forme mais la SOURCE : celle-la traduit un horodatage ISO du manifeste,
#: alors qu'un tirage n'en porte aucun et que sa date vient du systeme de
#: fichiers.
FORMAT_DE_LA_DATE = "%d/%m à %H:%M"

#: La forme courte, pour les lignes d'etat : `26/08`.
FORMAT_DE_LA_DATE_COURTE = "%d/%m"

#: Le separateur des mesures d'une meme ligne : `21 pages · 124 frames · 352 Mo`.
SEPARATEUR = " · "

#: Le pluriel des deux cardinaux du cartouche. `projet_lecture.PLURIELS` ne porte
#: que les trois mots de son bandeau ; ceux-ci sont a l'atelier Pdf.
PLURIEL_DES_PAGES = {False: "page", True: "pages"}
PLURIEL_DES_FRAMES = {False: "frame", True: "frames"}


# ===========================================================================
# Le modele -- ce que l'ecran montre d'un tirage deja present
# ===========================================================================

@dataclass(frozen=True)
class TirageEnConflit:
    """Un tirage deja present, et ce que l'ecran en dit.

    **Les DEUX rangs sont donnes, aucun n'est calcule ici** (`EPIC11-ARB-92`,
    verbatim d'Egan : « il ne faut pas rendre le rang »). Ils arrivent **deja
    resolus du coeur** : celui du tirage present, et celui que la passe
    ecrirait. Ni l'un ni l'autre n'a de valeur par defaut -- un defaut ferait de
    l'oubli de cablage un silence, et un ecran qui inventerait un numero de
    tirage est le pire mode de panne du versionnage : deux feuilles de papier
    differentes portant le meme numero, et une fois l'encre seche aucun fichier
    ne rattrape cela.

    **Ce module ne porte donc AUCUN mot du vocabulaire des rangs**, pas meme en
    prose -- c'est ce que la frontiere de la story 11.6 compte a zero sur tout
    `tui/`, et elle a raison de le faire au texte : un module d'ecran qui
    connaitrait la borne ou la valeur d'origine aurait, de fait, de quoi
    calculer un rang.

    `pages`, `frames`, `poids_mo`, `quand` et `mise_en_page` valent `None` quand
    la source qui les porte ne repond pas -- un fichier disparu du disque, un
    manifeste qu'on ne peut plus paginer, un gabarit sorti du registre. Le
    segment correspondant **disparait** de la ligne : il vaut mieux une ligne
    plus courte qu'un chiffre invente. C'est la meme discipline que le pied de
    `E5-0`.
    """

    nom: str
    lot_id: str
    rang: int
    rang_propose: int
    pages: int | None = None
    frames: int | None = None
    poids_mo: int | None = None
    quand: str | None = None
    quand_court: str | None = None
    mise_en_page: str | None = None
    meme_mise_en_page: bool = True
    scanne: bool = False
    quand_scanne: str | None = None

    @property
    def ecrasable(self) -> bool:
        """`EPIC11-ARB-174`, ferme par Egan : « **S'il est scanné on ne peut de
        fait pas l'écraser.** » -- et `EPIC11-ARB-176` en fixe la portee au
        RANG. C'est la seule propriete que les deux etats de l'ecran lisent."""
        return not self.scanne


@dataclass(frozen=True)
class EmportDeLaMasse:
    """Ce que l'issue de masse emporte : un cardinal, un poids, un saut.

    Les trois sont **affiches** (`EPIC11-ARB-177`, contrainte 2). Un
    « appliquer aux 4 restants » muet sur les megaoctets serait moins informatif
    que l'ecran qu'il remplace ; un saut muet serait une decision cachee.
    """

    lots: int = 0
    poids_mo: int = 0
    sautes: int = 0
    destructif: bool = False


@dataclass(frozen=True)
class PasseDeConflits:
    """Les N conflits d'une passe, **dans l'ordre choisi**, et celui qu'on juge.

    L'ecran reste **par lot** (`EPIC11-ARB-177`) : cette classe ne porte donc
    aucune selection ligne par ligne, elle porte une **file**. Le conflit courant
    est celui que l'ecran monte ; les suivants sont ce que l'issue de masse
    emporte.
    """

    conflits: tuple[TirageEnConflit, ...]
    rang_courant: int = 0

    def __post_init__(self) -> None:
        if not self.conflits:
            raise ValueError(
                "Une passe de conflits en porte au moins un : monter cet ecran "
                "sans conflit afficherait un jugement sans objet.")

    @property
    def courant(self) -> TirageEnConflit:
        return self.conflits[self.rang_courant]

    @property
    def restants(self) -> tuple[TirageEnConflit, ...]:
        """Les conflits qui suivent le courant, dans l'ordre de la file."""
        return self.conflits[self.rang_courant + 1:]

    @property
    def portee(self) -> str:
        """La droite du bandeau : `1 conflit sur 5`.

        Le rang est **celui de la file**, compte a partir de un, et le cardinal
        est celui de la passe entiere : les deux etats de l'ecran portent le meme
        bandeau parce qu'ils sont deux etats du **meme** premier conflit.

        Il s'ecrit ainsi **meme sur un conflit unique** (`1 conflit sur 1`) : un
        bandeau qui changerait de forme selon le cardinal ferait deux redactions,
        et la seconde ne serait vue par personne -- le cas courant d'une passe
        multi-lots est celui qui se dessine.
        """
        return f"{self.rang_courant + 1} conflit sur {len(self.conflits)}"


def ordonner_par_lot(
        conflits: Iterable[TirageEnConflit]) -> tuple[TirageEnConflit, ...]:
    """Les conflits **par lot**, et c'est un ordre CHOISI.

    Reponse d'Egan du 2026-09-02, mot pour mot -- « **Par lot** » --, au dernier
    point qu'`EPIC11-ARB-177` laissait ouvert : « l'ordre dans lequel les N
    conflits se presentent -- par lot, par date, par poids ? [...] a poser
    explicitement plutot qu'a laisser l'ordre du manifeste decider en silence ».

    **Ce que cette fonction ferme.** Sans elle, l'ordre serait celui de `lots[]`,
    c'est-a-dire l'ordre de **premiere creation** des lots -- un ordre qui existe
    pour une autre raison, qui ne veut rien dire pour qui tranche des conflits,
    et que personne n'aurait choisi. C'est pourquoi le tri se mesure comme un
    choix : un banc dont la fabrique ecrirait deja les lots dans l'ordre
    alphabetique ne verrait pas la difference entre les deux.
    """
    return tuple(sorted(conflits, key=lambda conflit: conflit.lot_id))


def emport_de_la_masse(restants: Sequence[TirageEnConflit],
                       destructif: bool) -> EmportDeLaMasse:
    """Ce que « appliquer ce choix aux N restants » emporte reellement.

    **Le saut du tirage scanne est ici, et il n'est pas negociable.** Un
    ecrasement de masse ne peut pas emporter un tirage scanne
    (`EPIC11-ARB-174`/`-176`), et refuser l'issue en bloc des qu'un scanne est
    present ferait perdre les N-1 autres pour un seul -- ce qu'`EPIC11-ARB-89`
    proscrit et ce que le choix 3 existe pour fermer. Le tirage scanne est donc
    **saute**, et le saut est **compte** pour pouvoir etre dit.

    Une masse **non destructive** ne saute personne : creer la vN d'un tirage
    scanne est precisement ce que `E5-3c` offre. Son poids est nul, et c'est une
    mesure -- « rien n'est effacé » -- et non une absence de mesure.
    """
    if not destructif:
        return EmportDeLaMasse(lots=len(restants), poids_mo=0, sautes=0,
                               destructif=False)
    emportes = [conflit for conflit in restants if conflit.ecrasable]
    return EmportDeLaMasse(
        lots=len(emportes),
        poids_mo=sum(conflit.poids_mo or 0 for conflit in emportes),
        sautes=len(restants) - len(emportes),
        destructif=True,
    )


# ===========================================================================
# Les issues -- jamais une seule, jamais un blocage sec
# ===========================================================================

CLE_CREER = "creer"
CLE_REMPLACER = "remplacer"
CLE_MASSE = "masse"
CLE_ANNULER = "annuler"

#: `Créer la v4` -- l'issue non destructive, et celle que le curseur vise au
#: montage. **Elle ne porte pas `ecrit=True`**, et le motif est celui que
#: `atelier_scan_calibrate.issues_de_la_collision` a deja ecrit : dans ce depot,
#: `Issue.ecrit` marque l'issue dont la validation **detruit** quelque chose. La
#: marquer ferait partir le curseur sur `Annuler`, c'est-a-dire l'inverse de ce
#: que l'AC 7.2a demande -- et la maquette signale elle-meme cet ecart de
#: vocabulaire (« soit le produit descend `Créer la vN` dans la categorie qui
#: n'ecrit pas au sens d'`ARB-7` (elle n'efface rien), soit les maquettes
#: montrent `Annuler` sous le curseur. A trancher au developpement »).
LIBELLE_CREER = "Créer la v{rang}"

#: `Remplacer ce tirage` -- l'ecriture destructive **consciente**
#: d'`EPIC11-ARB-89`. Elle n'est offerte que sur un tirage **non scanne**.
LIBELLE_REMPLACER = "Remplacer ce tirage"

#: `Appliquer ce choix aux 4 conflits restants` -- l'issue de masse
#: d'`EPIC11-ARB-177`, **accordee**, comme ses deux voisins immediats
#: (:data:`SAUT_DE_LA_MASSE` et :data:`MOT_DES_VERSIONS`).
#:
#: L'accord n'est pas cosmetique : le singulier est atteint des qu'une passe
#: porte **deux** conflits, c'est-a-dire par le cas multi-lots courant, et
#: `aux 1 conflits restants` y etait ce que l'operateur lisait. La forme
#: singuliere ne porte pas le chiffre -- « le conflit restant » en dit
#: exactement autant, et le lire est plus court que le compter.
LIBELLE_MASSE = {False: "Appliquer ce choix au conflit restant",
                 True: "Appliquer ce choix aux {restants} conflits restants"}

#: `Annuler` -- la sortie qui n'ecrit rien, et elle est toujours la.
LIBELLE_ANNULER = "Annuler"

#: La consequence de l'ecrasement unitaire : `efface les 352 Mo écrits`. Une
#: issue qui ecrase **dit ce qu'elle ecrase**, sans quoi le consentement
#: d'`EPIC11-ARB-89` (« une ecriture destructive CONSCIENTE ») porte sur rien.
CONSEQUENCE_DE_L_ECRASEMENT = "efface les {poids} Mo écrits"

#: La consequence de la masse **destructive** : cardinal, poids, et le saut.
CONSEQUENCE_DE_LA_MASSE = "{lots} · {poids} Mo effacés"

#: La consequence de la masse destructive qui n'emporte **rien** -- le conflit
#: courant est ecrasable, et tous les restants sont scannes. `0 lot · 0 Mo
#: effacés` promet une destruction qui n'aura pas lieu ; ce que la ligne a a
#: dire est la reserve, et elle la garde. La phrase est ecrite **une fois**
#: (:data:`RIEN_N_EST_EFFACE`) et partagee avec la masse non destructive : deux
#: redactions divergeraient au premier ajustement de libelle.
RIEN_N_EST_EFFACE = "rien n'est effacé"
CONSEQUENCE_DE_LA_MASSE_SANS_EMPORT = RIEN_N_EST_EFFACE

#: Le segment de saut, accorde. **Il ne disparait jamais quand il y a un saut**
#: -- c'est ce qui distingue « sauter en le disant » d'un saut silencieux.
SAUT_DE_LA_MASSE = {False: "{sautes} sauté, il est scanné",
                    True: "{sautes} sautés, ils sont scannés"}

#: Le tiret qui accroche le saut a la consequence. Un `·` y ferait un quatrieme
#: element de liste ; le saut n'est pas une mesure de plus, c'est une reserve
#: sur les precedentes.
LIAISON_DU_SAUT = " — "

#: La consequence de la masse **non destructive** : `4 versions créées — rien
#: n'est effacé`. Le poids y est nul, et il est **dit** plutot que tu : c'est la
#: contrainte 2 d'`EPIC11-ARB-177`, qui vaut aussi quand la reponse est zero.
CONSEQUENCE_DE_LA_MASSE_DOUCE = "{lots} — " + RIEN_N_EST_EFFACE

#: Le mot compte par la masse non destructive, au singulier et au pluriel.
#: **Il n'entre pas dans `projet_lecture.PLURIELS`**, et c'est delibere : cette
#: table-la accorde un NOM (`rush` -> `rushes`), alors qu'il y a ici un nom et un
#: participe qui s'accordent tous les deux. L'y verser aurait fait porter a une
#: table d'accord de noms une regle qui n'en est pas une.
MOT_DES_VERSIONS = ("version créée", "versions créées")


def libelle_de_la_creation(rang_propose: int) -> str:
    """`Créer la v4`. Le rang est **affiche**, jamais derive ici."""
    return LIBELLE_CREER.format(rang=rang_propose)


def libelle_de_la_masse(restants: int) -> str:
    """`Appliquer ce choix aux 4 conflits restants`, ou sa forme singuliere."""
    return LIBELLE_MASSE[restants > 1].format(restants=restants)


def consequence_de_l_ecrasement(tirage: TirageEnConflit) -> str:
    """`efface les 352 Mo écrits`, ou rien quand le disque n'a pas repondu.

    Un poids inconnu ne s'ecrit **pas** `0 Mo` : ce serait annoncer qu'on
    n'efface rien alors qu'on efface un fichier dont on n'a pas su lire la
    taille. La ligne disparait, l'issue reste.
    """
    if tirage.poids_mo is None:
        return ""
    return CONSEQUENCE_DE_L_ECRASEMENT.format(poids=_grouper(tirage.poids_mo))


def consequence_de_la_masse(emport: EmportDeLaMasse) -> str:
    """Ce que la masse emporte : cardinal, poids, **et le saut quand il y en a**.

    Trois contraintes d'`EPIC11-ARB-177` se lisent dans cette seule fonction :
    le cardinal et le poids y sont **tous les deux** (contrainte 2), et le saut
    y est **dit** plutot que journalise. Il disparait quand il vaut zero -- « 0
    sauté » se lirait comme une reserve la ou il n'y en a aucune.
    """
    if not emport.destructif:
        return CONSEQUENCE_DE_LA_MASSE_DOUCE.format(
            lots=f"{emport.lots} {MOT_DES_VERSIONS[emport.lots > 1]}")
    if emport.lots:
        texte = CONSEQUENCE_DE_LA_MASSE.format(
            lots=projet_lecture.accorder(emport.lots, "lot"),
            poids=_grouper(emport.poids_mo))
    else:
        texte = CONSEQUENCE_DE_LA_MASSE_SANS_EMPORT
    if emport.sautes:
        texte += LIAISON_DU_SAUT + SAUT_DE_LA_MASSE[emport.sautes > 1].format(
            sautes=emport.sautes)
    return texte


def issues_du_conflit(passe: PasseDeConflits) -> list[Issue]:
    """Les issues de `E5-3b` (trois ou quatre) et de `E5-3c` (deux ou trois).

    **L'ensemble est EXACT et il se lit ici**, pas dans la maquette :

    * `Créer la vN` -- toujours, dans les deux etats. C'est ce qui fait tenir
      `EPIC11-ARB-104` (« tout doit etre versionnable OU ecrase ») sur un tirage
      scanne : l'objet reste versionnable, seul l'ecrasement tombe ;
    * `Remplacer ce tirage` -- **seulement si le tirage est ecrasable**. C'est la
      frontiere negative de l'AC 7.9c, et elle est ici plutot que dans un second
      ecran : une issue retiree par une branche que personne n'exerce n'est pas
      retiree ;
    * `Appliquer ce choix aux N restants` -- seulement s'il **reste** des
      conflits. La proposer sur le dernier n'emporterait rien et se lirait comme
      un bouton mort ;
    * `Annuler` -- toujours, et c'est la seule qui n'ecrit rien. « Jamais une
      seule issue, jamais un blocage sec. »

    L'ordre est celui de la maquette, et il porte la contrainte 1
    d'`EPIC11-ARB-177` : la masse est posee **apres** l'issue unitaire.
    """
    tirage = passe.courant
    issues = [Issue(CLE_CREER, libelle_de_la_creation(tirage.rang_propose))]
    if tirage.ecrasable:
        issues.append(Issue(CLE_REMPLACER, LIBELLE_REMPLACER, ecrit=True))
    if passe.restants:
        issues.append(Issue(CLE_MASSE,
                            libelle_de_la_masse(len(passe.restants)),
                            ecrit=tirage.ecrasable))
    issues.append(Issue(CLE_ANNULER, LIBELLE_ANNULER))
    return issues


def choix_du_conflit(passe: PasseDeConflits) -> ChoixExclusif:
    """Le point de jugement du conflit. **Le curseur part sur `Créer la vN`.**

    Il n'est pas pose ici : c'est `ChoixExclusif.__post_init__` qui le place, et
    cet invariant n'est pas reecrit (`EPIC11-ARB-7`). Ce module se contente de
    lui donner des issues dont la premiere n'ecrit pas -- ce qui est aussi ce qui
    rend l'invariant **verifiable** plutot que suppose.
    """
    return ChoixExclusif(issues_du_conflit(passe))


def consequences_des_issues(passe: PasseDeConflits) -> dict[str, str]:
    """La ligne de consequence de chaque issue qui en porte une.

    Deux issues seulement en portent : l'ecrasement unitaire et la masse. Les
    deux autres n'emportent rien qui doive etre chiffre -- et une ligne de
    consequence vide sous `Annuler` occuperait une ligne de la grille pour ne
    rien dire.
    """
    consequences: dict[str, str] = {}
    tirage = passe.courant
    if tirage.ecrasable:
        ligne = consequence_de_l_ecrasement(tirage)
        if ligne:
            consequences[CLE_REMPLACER] = ligne
    if passe.restants:
        consequences[CLE_MASSE] = consequence_de_la_masse(
            emport_de_la_masse(passe.restants, tirage.ecrasable))
    return consequences


# ===========================================================================
# Le cartouche et les deux mentions
# ===========================================================================

#: Le titre du cartouche, dans ses deux etats. Le second **dit l'etat qui retire
#: une issue** : une issue qui manque sans motif se lit comme un bug.
TITRE_DU_CONFLIT = "Ce tirage existe déjà"
TITRE_DU_CONFLIT_SCANNE = "Ce tirage existe déjà, et il a été scanné"

#: La mention de `E5-3b`, **mot pour mot d'Egan** (2026-09-02) : « On y ajoute la
#: mention "Si cette page a déjà été imprimée, n'écrasez pas cette planche sous
#: peine de générer des conflits de version". On fait confiance a
#: l'operateur.ice. » Elle n'est coupee que par la largeur du cartouche ; aucun
#: mot n'est change ni abrege, et un test la mesure **verbatim** plutot que par
#: mots-cles -- une paraphrase serait exactement le defaut que le pare-arbitrage
#: du depot existe pour empecher.
MENTION_DE_L_ECRASEMENT = (
    "Si cette page a déjà été imprimée, n'écrasez pas cette planche sous "
    "peine de générer des conflits de version")

#: La mention de `E5-3c`, **reecrite par Egan le 2026-09-02 au soir** : « ce
#: tirage a deja ete imprime. Vous ne pouvez pas l'ecraser car cela pourrait
#: causer des conflits de version. »
#:
#: Elle **remplace** la redaction qui expliquait le mecanisme (« la feuille porte
#: son rang dans son QR, le remplacer ferait dire deux choses au meme numero »).
#: Motif d'Egan : le message etait trop long -- deux phrases contre quatre lignes
#: de cartouche --, et **le mecanisme n'est pas la raison qu'un operateur a
#: besoin de lire**. Il vit dans les documents de decision
#: (`EPIC11-ARB-174`/`-176`), pas a l'ecran.
#:
#: **Deux ecarts avec sa frappe, et ils sont nommes plutot que tus** : les
#: accents sont poses (son message etait en ASCII, la TUI ecrit accentue et
#: replie par `jetons.REPLIS_DE_TEXTE`) et la premiere lettre est une majuscule
#: (une phrase de cartouche qui commencerait en minuscule se lirait comme un
#: defaut de rendu). **Aucun mot n'est change, aucun n'est ajoute**, et un test
#: mesure la suite des mots.
MENTION_DU_TIRAGE_SCANNE = (
    "Ce tirage a déjà été imprimé. Vous ne pouvez pas l'écraser car cela "
    "pourrait causer des conflits de version.")


def _grouper(valeur: int) -> str:
    """`1056` -> `1 056`. L'espace des milliers, comme les maquettes l'ecrivent.

    Une espace ordinaire et non insecable : la grille est mesuree en colonnes, et
    `jetons.colonnes` compte les deux pareil -- mais le repli ASCII, lui, ne
    connait pas l'insecable, qui sortirait tel quel sur un terminal qui ne la
    dessine pas.
    """
    return f"{valeur:,}".replace(",", " ")


def _mesures_du_contenu(tirage: TirageEnConflit) -> str:
    """`21 pages · 124 frames · 352 Mo` -- les segments inconnus disparaissent."""
    mesures = []
    if tirage.pages is not None:
        mesures.append(f"{tirage.pages} {PLURIEL_DES_PAGES[tirage.pages > 1]}")
    if tirage.frames is not None:
        mesures.append(
            f"{tirage.frames} {PLURIEL_DES_FRAMES[tirage.frames > 1]}")
    if tirage.poids_mo is not None:
        mesures.append(f"{_grouper(tirage.poids_mo)} Mo")
    return SEPARATEUR.join(mesures)


def _ligne_de_fiche(libelle: str, valeur: str, glose: str = "") -> str:
    """Une ligne du cartouche : libelle, valeur, glose, en trois colonnes.

    La valeur est **calee** sur `LARGEUR_DE_LA_VALEUR` pour que les gloses
    s'alignent ; une valeur plus large que sa colonne pousse sa glose plutot que
    de la tronquer -- il vaut mieux une glose decalee qu'une valeur amputee,
    puisque c'est la valeur qui porte le fait.
    """
    tete = f"{libelle:<{LARGEUR_DU_LIBELLE}}"
    if not glose:
        return (tete + valeur).rstrip()
    creux = max(LARGEUR_DE_LA_VALEUR - jetons.colonnes(valeur), 2)
    return tete + valeur + " " * creux + glose


#: L'ordinal francais, en table. **C'est de la TYPOGRAPHIE, pas une regle de
#: rang** : le premier de n'importe quoi s'ecrit `1er` en francais -- une page,
#: un rush, un tirage --, et la table vaut pour tous. Ce module n'a donc rien a
#: savoir de ce que le premier tirage EST : il met en forme le nombre qu'on lui
#: donne, et rien d'autre.
ORDINAUX = {1: "1er"}

#: La glose de la ligne `Lot` : quel tirage est present, et qu'il est le dernier.
ORDINAL_DU_TIRAGE = "{ordinal} tirage, le plus récent"


def ordinal_du_tirage(rang: int) -> str:
    """`3e tirage, le plus récent` -- le nombre est **affiche**, jamais derive."""
    return ORDINAL_DU_TIRAGE.format(ordinal=ORDINAUX.get(rang, f"{rang}e"))


def lignes_du_cartouche(tirage: TirageEnConflit,
                        ascii_seul: bool = False) -> list[str]:
    """Les lignes du cartouche de `E5-3b` / `E5-3c`, dans l'ordre de la maquette.

    La derniere est la **mention**, et c'est elle qui change entre les deux
    etats : l'avertissement d'Egan sur un tirage ecrasable, sa reecriture du soir
    sur un tirage scanne. La ligne `Mise en page` ne figure que sur `E5-3b` --
    sur `E5-3c` l'ecran a une mention plus longue a porter, et la mise en page
    n'est pas ce que l'operateur a besoin de lire pour comprendre qu'il ne peut
    pas ecraser.
    """
    table = jetons.glyphes(ascii_seul)
    # **Aucune ligne vide sous le nom du fichier**, et c'est une mesure de
    # grille et non un gout : `E5-3b` est l'ecran le plus haut du lot -- neuf
    # lignes de cartouche, deux de cadre, six d'issues -- et il tient a la ligne
    # pres dans les 17 de la zone centrale (`EPIC11-ARB-21`). La maquette
    # `E5-3c` en porte une parce qu'elle a une ligne de moins a montrer ; la
    # reprendre ici ferait deborder le cas qui n'a pas de marge.
    lignes = [f"{table['substitute']} {tirage.nom}"]
    lignes.append(_ligne_de_fiche(LIBELLE_DU_LOT, tirage.lot_id,
                                  ordinal_du_tirage(tirage.rang)))
    if tirage.quand:
        lignes.append(_ligne_de_fiche(LIBELLE_DE_LA_DATE, tirage.quand))
    contenu = _mesures_du_contenu(tirage)
    if contenu:
        lignes.append(_ligne_de_fiche(LIBELLE_DU_CONTENU, contenu))
    if tirage.ecrasable and tirage.mise_en_page:
        lignes.append(_ligne_de_fiche(
            LIBELLE_DE_LA_MISE_EN_PAGE, tirage.mise_en_page,
            GLOSE_MEME_MISE_EN_PAGE if tirage.meme_mise_en_page else ""))
    lignes.append(_ligne_de_fiche(
        LIBELLE_DU_SCAN,
        f"{table['substitute'] if tirage.scanne else table['neutre']} "
        f"{VALEUR_SCANNE if tirage.scanne else VALEUR_NON_SCANNE}",
        _glose_du_scan(tirage)))
    return lignes


def _glose_du_scan(tirage: TirageEnConflit) -> str:
    """La glose de la ligne `Scanné`. Elle porte sur le TIRAGE, jamais le lot."""
    if not tirage.scanne:
        return GLOSE_SANS_SCAN
    if tirage.quand_scanne:
        return f"{GLOSE_DU_SCAN}, le {tirage.quand_scanne}"
    return GLOSE_DU_SCAN


# ===========================================================================
# Les deux lignes d'etat -- des CONSTATS, jamais un conseil
# ===========================================================================

#: `EPIC11-ARB-56` : la ligne d'etat ne porte aucune touche, aucun conseil
#: d'usage, aucun motif de conception. Les deux qui suivent sont des mesures --
#: ce qui est ecrit, et ce qui n'est pas offert.
#: Ce que la ligne dit **toujours** sur un tirage ecrasable : le fait qui
#: autorise l'ecrasement. Ecrit une seule fois, et les deux gabarits ci-dessous
#: le composent -- une seconde redaction divergerait au premier ajustement.
ETAT_SANS_SCAN = "ce tirage n'est pas scanné"
ETAT_DU_TIRAGE_PRESENT = "{mesures} · " + ETAT_SANS_SCAN
#: Le meme constat quand **aucune** mesure ne repond. Le module retire partout
#: ailleurs les segments qu'il ne sait pas remplir (« il vaut mieux une ligne
#: plus courte qu'un chiffre invente ») ; le separateur de tete en etait la
#: seule exception, et il annoncait une mesure qui n'existe pas. Le cas est
#: atteignable : un fichier declare a l'inventaire qui ne repond plus rend
#: `poids_mo` et `quand` a `None`, et un inventaire plus court que ce que le
#: coeur annonce rend un conflit sans aucune mesure.
ETAT_DU_TIRAGE_PRESENT_SANS_MESURE = ETAT_SANS_SCAN
ECRITURE_DU_TIRAGE = "{poids} Mo écrits le {quand}"
ETAT_DU_TIRAGE_SCANNE = "{issue} n'est pas offert — il a été scanné"
ETAT_DU_TIRAGE_SCANNE_DATE = (
    "{issue} n'est pas offert — il a été scanné le {quand}")


def ligne_d_etat(tirage: TirageEnConflit, ascii_seul: bool = False) -> str:
    """La ligne d'etat de l'ecran, dans l'etat ou il se trouve.

    Le glyphe distingue les deux : `▲` sur le tirage ecrasable -- une reserve --,
    `✕` sur le tirage scanne -- **un interdit** (AC 7.9d). Le libelle de l'issue
    absente n'est pas recopie : il est lu de :data:`LIBELLE_REMPLACER`, sans quoi
    la ligne d'etat annoncerait un jour un nom d'issue qui n'existe plus.
    """
    table = jetons.glyphes(ascii_seul)
    if tirage.ecrasable:
        segments = []
        if tirage.pages is not None:
            segments.append(
                f"{tirage.pages} {PLURIEL_DES_PAGES[tirage.pages > 1]}")
        if tirage.poids_mo is not None and tirage.quand_court:
            segments.append(ECRITURE_DU_TIRAGE.format(
                poids=_grouper(tirage.poids_mo), quand=tirage.quand_court))
        modele_present = (ETAT_DU_TIRAGE_PRESENT if segments
                          else ETAT_DU_TIRAGE_PRESENT_SANS_MESURE)
        return (f"{table['substitute']}  "
                + modele_present.format(mesures=SEPARATEUR.join(segments)))
    modele = (ETAT_DU_TIRAGE_SCANNE_DATE if tirage.quand_scanne
              else ETAT_DU_TIRAGE_SCANNE)
    return (f"{table['absent']}  "
            + modele.format(issue=LIBELLE_REMPLACER,
                            quand=tirage.quand_scanne))


# ===========================================================================
# Le refus des rangs epuises -- un refus qui NOMME ses issues (AC 7.8)
# ===========================================================================

#: Le titre du refus. Il ne dit **jamais** « echec » (`DESIGN.md` section 9) : il
#: nomme ce qui n'a pas eu lieu.
TITRE_DES_RANGS_EPUISES = "Aucun tirage n'a été écrit"

#: La ligne d'etat du refus. Un CONSTAT, et **sans chiffre** : le nombre de rangs
#: est une donnee du coeur, deja portee par le texte du refus.
ETAT_DES_RANGS_EPUISES = "il ne reste aucune version disponible pour {lot}"

CLE_RETIRER_DE_LA_PASSE = "retirer-de-la-passe"

#: Les deux issues qui restent quand les 99 rangs sont consommes, plus
#: l'ecrasement conscient quand le tirage n'est pas scanne. **Jamais zero** : « un
#: refus qui n'offre aucune issue est aussi fautif qu'une destruction
#: silencieuse » (`EPIC11-ARB-89`).
#:
#: La troisieme issue du texte du coeur -- retirer le dernier tirage en liberant
#: son rang -- n'est **pas** offerte ici, et c'est delibere : la suppression est
#: la story 11.11, et une issue qui ne ferait rien serait pire qu'absente. Le
#: texte du coeur, lui, la nomme : il est affiche **tel quel**.
LIBELLE_RETIRER_DE_LA_PASSE = "Retirer ce lot de la passe"


def issues_des_rangs_epuises(tirage: TirageEnConflit) -> list[Issue]:
    """Les issues du refus. Deux au moins, trois quand l'ecrasement est permis."""
    issues = []
    if tirage.ecrasable:
        issues.append(Issue(CLE_REMPLACER, LIBELLE_REMPLACER, ecrit=True))
    issues.append(Issue(CLE_RETIRER_DE_LA_PASSE, LIBELLE_RETIRER_DE_LA_PASSE))
    issues.append(Issue(CLE_ANNULER, LIBELLE_ANNULER))
    return issues


# ===========================================================================
# La lecture du manifeste -- ce que le produit SAIT d'un tirage
# ===========================================================================

def rangs_scannes(lot: Mapping[str, Any]) -> frozenset[int]:
    """Les rangs de tirage que ce lot a **effectivement** vus passer au scanner.

    `EPIC11-ARB-176` : c'est `lots[].scanned_version_ranks`, ecrit par
    `io/scan_manifest.py` par **union** et jamais par ecrasement. Lecture
    defensive, comme partout ou la TUI lit un document : la cle absente, mal
    typee, ou porteuse d'autre chose que des entiers rend un ensemble vide.

    **Une cle absente veut dire « on ne sait pas », jamais « aucun »** -- mais les
    deux se rendent ici par le meme ensemble vide, et c'est juste : un tirage dont
    on ne sait pas qu'il a ete scanne reste ecrasable, avec l'avertissement
    d'Egan sous les yeux. C'est exactement ce qu'il a tranche : « **On fait
    confiance a l'operateur.ice.** »
    """
    lus = lot.get(scan_manifest.SCANNED_VERSION_RANKS_FIELD)
    if not isinstance(lus, (list, tuple)):
        return frozenset()
    return frozenset(rang for rang in lus
                     if isinstance(rang, int) and not isinstance(rang, bool))


def _mo_du_fichier(chemin: Path) -> int | None:
    """La taille du tirage en megaoctets, ou `None` s'il ne repond pas."""
    try:
        return round(chemin.stat().st_size / OCTETS_PAR_MO)
    except OSError:
        return None


def _quand_du_fichier(chemin: Path, format_: str) -> str | None:
    try:
        horodate = chemin.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(horodate).strftime(format_)


def mise_en_page_du_gabarit(gabarit: Any) -> str | None:
    """`6 f/page · paysage`, lu du registre des gabarits et jamais recompose.

    Rend `None` des que le gabarit n'est pas connu : un fragment de mise en page
    invente serait pire qu'absent, l'ecran s'en servant pour dire que le conflit
    porte bien sur la **meme** mise en page.
    """
    if not isinstance(gabarit, str) or not gabarit:
        return None
    from .. import page_templates

    try:
        specification = page_templates.get_template(gabarit)
    except Exception:                                      # noqa: BLE001
        return None
    return (f"{specification.frames_per_page} f/page"
            f"{SEPARATEUR}{specification.orientation}")


def _cardinaux_du_lot(manifeste: Mapping[str, Any] | None, lot: Mapping[str, Any],
                      gabarit: Any) -> tuple[int | None, int | None]:
    """`(pages, frames)` du lot, **recalcules par le coeur** ou `(None, None)`.

    Meme chemin que l'impression : la selection se recalcule depuis le seul
    manifeste, jamais depuis un `glob` ni depuis `expected_frame_count`. L'import
    est differe comme partout ou ce paquet touche au coeur lourd.
    """
    if manifeste is None or not isinstance(gabarit, str) or not gabarit:
        return None, None
    from .. import page_templates, pdf_composition
    from ..io import extraction_manifest

    try:
        emplacements = page_templates.get_template(gabarit).frames_per_page
        selection, _ = extraction_manifest.recompute_lot_selection(
            manifeste, lot)
        if selection is None:
            return None, None
        frames = len(list(selection.frames))
        return pdf_composition.nombre_de_planches(frames, emplacements), frames
    except Exception:                                      # noqa: BLE001
        # L'ecran de conflit ne tombe pas sur un manifeste incoherent : il dit
        # ce qu'il sait. Nommer les refus du coeur un par un ferait une seconde
        # table a maintenir a cote de la sienne.
        return None, None


def conflit_du_tirage(manifeste: Mapping[str, Any] | None,
                      lot: Mapping[str, Any],
                      entree: Mapping[str, Any],
                      *,
                      rang: int,
                      rang_propose: int,
                      dossier: Path | str | None = None,
                      quand_scanne: str | None = None) -> TirageEnConflit:
    """Le conflit d'un tirage present, lu du manifeste et du disque.

    **`rang` et `rang_propose` sont requis et sans defaut** : ce sont les deux
    nombres que le coeur resout, et ce module ne sait produire ni l'un ni
    l'autre (`EPIC11-ARB-92`). Un defaut ferait de l'oubli de cablage un
    silence -- le finding `K3`, paye quatre fois dans cet epic --, et le silence
    porterait ici sur un numero grave sur du papier.

    **Pourquoi `rang` ne se lit pas de l'entree d'inventaire ici**, alors qu'il
    y figure : l'inventaire **omet** le champ pour le tirage d'origine, si bien
    que le lire demanderait de savoir quel nombre vaut cette absence -- et le
    manifeste de scan, lui, ecrit ce nombre-la explicitement. Faire cette
    jonction dans un ecran serait la convention en deux exemplaires, donc deux
    occasions de diverger ; elle se fait une fois, au coeur, avant d'arriver ici.

    Le reste se lit : le chemin dans l'inventaire des tirages
    (`io.pdf_manifest`), la taille et la date sur le **disque** -- le manifeste
    n'en porte aucune, son idempotence etant verifiee octet a octet --, et l'etat
    de scan dans `lots[].scanned_version_ranks`, **au rang**.

    **Un piege signale plutot que suppose** : la mise en page affichee est celle
    du **LOT** (`lots[].template_id`), pas celle du tirage -- le fragment du nom
    de fichier ne suffit pas a la remonter, la marge et la version de geometrie
    n'y figurant pas. C'est correct **ici** parce que deux mises en page
    differentes ecrivent deux fichiers differents (`EPIC11-ARB-171`) : un conflit
    porte donc, par construction, sur la meme mise en page qu'aujourd'hui, ce
    que la glose dit. Elle serait fausse d'un tirage ANTERIEUR quelconque, et
    c'est pourquoi cet ecran n'en montre aucun.
    """
    chemin_relatif = entree.get(pdf_manifest.SHEETS_INVENTORY_KEY)
    chemin_relatif = chemin_relatif if isinstance(chemin_relatif, str) else ""
    racine = Path(dossier) if dossier is not None else None
    chemin = (racine / chemin_relatif) if racine and chemin_relatif else None
    gabarit = lot.get("template_id")
    pages, frames = _cardinaux_du_lot(manifeste, lot, gabarit)
    return TirageEnConflit(
        nom=Path(chemin_relatif).name if chemin_relatif else "",
        lot_id=lot.get("lot_id") if isinstance(lot.get("lot_id"), str) else "",
        rang=rang,
        rang_propose=rang_propose,
        pages=pages,
        frames=frames,
        poids_mo=_mo_du_fichier(chemin) if chemin else None,
        quand=_quand_du_fichier(chemin, FORMAT_DE_LA_DATE) if chemin else None,
        quand_court=(_quand_du_fichier(chemin, FORMAT_DE_LA_DATE_COURTE)
                     if chemin else None),
        mise_en_page=mise_en_page_du_gabarit(gabarit),
        scanne=rang in rangs_scannes(lot),
        quand_scanne=quand_scanne,
    )


def _replier_sous_un_glyphe(texte: str, nom_etat: str, largeur: int,
                            ascii_seul: bool = False) -> list[str]:
    """Un message replie, son glyphe en tete, ses continuations **alignees**.

    Les lignes de continuation sont indentees de deux colonnes -- la largeur du
    glyphe et de son blanc --, si bien que le message se lit comme un seul bloc.
    C'est aussi ce qui le rend colorisable d'un coup : `EPIC11-ARB-71` exige
    qu'un avertissement multiligne soit peint **entierement**, et une
    continuation ne porte par construction aucun glyphe a reconnaitre.
    """
    table = jetons.glyphes(ascii_seul)
    repliees = jetons.envelopper(texte, max(largeur - 2, 1), ascii_seul)
    if not repliees:
        return []
    return ([f"{table[nom_etat]} {repliees[0]}"]
            + [f"  {ligne}" for ligne in repliees[1:]])


# ===========================================================================
# Les ecrans
# ===========================================================================

#: La ligne de raccourcis des deux ecrans, verbatim des maquettes. Constante de
#: module, comme celles des autres ateliers : c'est ce qui la fait balayer par la
#: garde d'epic du repli ASCII et par celle des majuscules.
#: MESURE: 44/49
RACCOURCIS_DU_CONFLIT = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Le titre de l'atelier, porte par le bandeau.
TITRE_DE_L_ATELIER = "Pdf"


class _EcranDeConflit(ObjetTravaille, Palier):
    """Le tronc commun des deux points de jugement du lot G.

    Un cartouche, une mention, un `ChoixExclusif` dont certaines issues portent
    une ligne de consequence. **Il n'existe pas d'instance a zero issue** :
    `ChoixExclusif.__post_init__` en exige deux, et cet invariant n'est pas
    reecrit ici.

    `retenir` est **injecte et REQUIS** (finding `K3`) : un point de jugement qui
    ne sait pas a qui rendre son issue est un cul-de-sac.
    """

    titre = TITRE_DE_L_ATELIER
    raccourcis = RACCOURCIS_DU_CONFLIT

    #: Un passage : on y decide, puis on en sort.
    TRANSITOIRE = True

    def __init__(self, choix: ChoixExclusif, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__()
        self.choix = choix
        self._retenir = retenir

    # -- rendu ------------------------------------------------------------

    def largeur_du_cartouche(self) -> int:
        """La largeur ecrivable du cartouche, **lue de la fenetre courante**.

        Elle retombe sur le plancher d'`EPIC11-ARB-21` tant qu'aucune
        application ne porte l'ecran : le repli d'un message se calcule aussi
        hors montage -- c'est ainsi qu'un banc mesure la mention sans piloter la
        boucle d'evenements.
        """
        try:
            largeur = self.app.size.width
        except Exception:                                  # noqa: BLE001
            # `Screen.app` LEVE quand aucune application n'est active -- ce
            # n'est pas un attribut absent, donc un `getattr(..., None)` ne
            # rattrape rien. Le repli est le plancher d'`EPIC11-ARB-21`, la
            # seule largeur dont ce paquet soit certain.
            largeur = jetons.LARGEUR_PLANCHER
        return jetons.largeur_de_cartouche(largeur)

    def titre_du_cartouche(self, ascii_seul: bool = False) -> str:
        raise NotImplementedError

    def lignes_du_corps(self, ascii_seul: bool = False) -> list[str]:
        raise NotImplementedError

    def consequences(self) -> Mapping[str, str]:
        return {}

    def etat(self, ascii_seul: bool = False) -> str:
        return ""

    def lignes_des_issues(self,
                          ascii_seul: bool = False) -> tuple[list[str], int]:
        """Les lignes des issues **et** le rang de celle du curseur, en UN passage.

        Deux reperages tenus separement -- une methode qui rendrait les lignes,
        une autre qui compterait les rangs -- divergent des la premiere ligne de
        consequence ajoutee, et le curseur se peindrait alors sur une autre
        issue sans que rien ne le dise. C'est la meme raison qui fait que
        `cadences.rang_du_curseur` indexe la liste que `cadences.lignes` rend.
        """
        table = jetons.glyphes(ascii_seul)
        consequences = self.consequences()
        lignes: list[str] = []
        rang = 0
        for position, issue in enumerate(self.choix.issues):
            if position == self.choix.curseur:
                rang = len(lignes)
            marque = (table["curseur"] if position == self.choix.curseur
                      else " ")
            lignes.append(f"{INDENT_DU_CURSEUR}{marque} {issue.libelle}")
            consequence = consequences.get(issue.cle)
            if consequence:
                lignes.append(f"{INDENT_DE_LA_CONSEQUENCE}"
                              f"{table['substitute']} {consequence}")
        return lignes, rang

    def contenu(self) -> list[Widget]:
        ascii_seul = getattr(self.app, "ascii_seul", False)
        self._cartouche = Static("", id="cartouche-conflit")
        self._corps = Vertical(self._cartouche, id="corps-conflit")
        self._corps.border_title = self.titre_du_cartouche(ascii_seul)
        self._issues = Static("", id="issues-conflit")
        # **Aucun separateur entre le cartouche et les issues** : la maquette
        # `E5-3b` n'en porte pas, et elle occupe deja les 17 lignes de la zone
        # centrale a la ligne pres. Un `Static("")` de confort y couterait la
        # derniere issue.
        return [self._corps, self._issues]

    def on_mount(self) -> None:
        self.rafraichir()

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        ascii_seul = self.app.ascii_seul
        largeur = self.app.size.width
        cartouche = jetons.largeur_de_cartouche(largeur)
        utile = jetons.largeur_utile(largeur)
        self._corps.border_title = self.titre_du_cartouche(ascii_seul)
        self._cartouche.update(jetons.peindre(
            [jetons.ajuster(ligne, cartouche, ascii_seul)
             for ligne in self.lignes_du_corps(ascii_seul)],
            ascii_seul=ascii_seul, sans_couleur=self.app.sans_couleur,
            etats=self.etats_du_cartouche(ascii_seul)))
        lignes, rang = self.lignes_des_issues(ascii_seul)
        self._issues.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, ascii_seul) for ligne in lignes],
            ascii_seul=ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang))
        self.poser_etat(self.etat(ascii_seul))
        super().rafraichir()

    def etats_du_cartouche(self, ascii_seul: bool = False) -> dict[int, str]:
        """L'etat de chaque ligne du cartouche, **DONNE** et non devine.

        `EPIC11-ARB-71` : un glyphe pose dans un cartouche est precede de la
        bordure et d'un seul blanc, donc il n'ouvre pas de colonne et le repli
        par motif de `jetons.jeton_d_etat` ne le voit pas. Et une ligne de
        **continuation** d'une mention repliee ne porte, par construction, aucun
        glyphe : un avertissement sur trois lignes serait colore sur la premiere
        seulement, et se lirait comme deux messages.
        """
        return {}

    # -- clavier ----------------------------------------------------------

    def rang_du_curseur(self, ascii_seul: bool = False) -> int:
        """Le rang **rendu** de la ligne du curseur, dans le bloc des issues.

        Le regime est **passe** plutot que lu de l'application : un test qui
        interroge le rang apres avoir referme le banc n'a plus d'application
        active, et `Screen.app` **leve** alors -- ce qui ferait echouer une
        mesure pour une raison etrangere a ce qu'elle mesure.
        """
        return self.lignes_des_issues(ascii_seul)[1]

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`↑↓` deplacent, `⏎` retient. **Aucune lettre n'est un raccourci.**

        `EPIC11-ARB-45` / `-126` : fleche seule hors des listes a cocher. La
        frappe imprimable est **consommee** -- la ligne de raccourcis n'annonce
        aucune sortie par lettre, et laisser remonter `q` fermerait
        l'application sur une touche que rien n'annonce.
        """
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is not None:
                self._retenir(issue)
            return True
        if caractere and caractere.isprintable():
            return True
        return False


class EcranConflitDeTirage(_EcranDeConflit):
    """`E5-3b` et `E5-3c` -- **un seul ecran, deux etats** (AC 7.1, AC 7.9).

    L'etat est celui du **tirage**, pas du lot : `TirageEnConflit.ecrasable`
    lit `lots[].scanned_version_ranks` au rang (`EPIC11-ARB-176`). Ce qui change
    entre les deux : le titre du cartouche, la ligne `Scanné`, la mention, la
    ligne d'etat -- et la presence de `Remplacer ce tirage`.
    """

    def __init__(self, passe: PasseDeConflits, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__(choix_du_conflit(passe), retenir=retenir)
        self.passe = passe

    @property
    def tirage(self) -> TirageEnConflit:
        return self.passe.courant

    def objet_du_bandeau(self) -> str:
        """La DROITE du bandeau : `1 conflit sur 5 · tirage présent`.

        Elle est **rendue au moment de dessiner** et jamais ecrite dans la
        session (`ObjetTravaille`) : l'objet travaille change d'un ecran a
        l'autre, et l'ecrire dans le contexte le ferait survivre au palier qui
        l'a pose.
        """
        return f"{self.passe.portee}{SEPARATEUR}{self._etat_du_tirage()}"

    def _etat_du_tirage(self) -> str:
        return ("tirage présent" if self.tirage.ecrasable
                else "tirage scanné")

    def titre_du_cartouche(self, ascii_seul: bool = False) -> str:
        titre = (TITRE_DU_CONFLIT if self.tirage.ecrasable
                 else TITRE_DU_CONFLIT_SCANNE)
        return jetons.replier_ascii(titre) if ascii_seul else titre

    def mention(self) -> str:
        """L'avertissement d'Egan, ou sa reecriture du soir.

        Les deux sont des constantes de module et voyagent **verbatim** : l'ecran
        ne les reformule pas, il les relaie.
        """
        return (MENTION_DE_L_ECRASEMENT if self.tirage.ecrasable
                else MENTION_DU_TIRAGE_SCANNE)

    def lignes_de_la_mention(self, ascii_seul: bool = False) -> list[str]:
        """La mention, **repliee par la largeur** et jamais abregee.

        `jetons.envelopper` coupe entre les mots : aucun mot n'est change ni
        tronque, ce qui est ce que « mot pour mot » exige d'un cartouche de 72
        colonnes.
        """
        return _replier_sous_un_glyphe(self.mention(), "substitute",
                                       self.largeur_du_cartouche(), ascii_seul)

    def lignes_du_corps(self, ascii_seul: bool = False) -> list[str]:
        return (lignes_du_cartouche(self.tirage, ascii_seul) + [""]
                + self.lignes_de_la_mention(ascii_seul))

    def etats_du_cartouche(self, ascii_seul: bool = False) -> dict[int, str]:
        """Le nom du fichier, la ligne `Scanné`, et **toute** la mention.

        « Un avertissement se colorise ENTIEREMENT, jamais une ligne sur deux --
        un avertissement multiligne est un seul objet » (`EPIC11-ARB-71`, apres
        trois retours d'Egan le meme jour).
        """
        lignes = self.lignes_du_corps(ascii_seul)
        mention = len(self.lignes_de_la_mention(ascii_seul))
        etats = {0: "substitute"}
        for rang in range(len(lignes) - mention, len(lignes)):
            etats[rang] = "substitute"
        return etats

    def consequences(self) -> Mapping[str, str]:
        return consequences_des_issues(self.passe)

    def etat(self, ascii_seul: bool = False) -> str:
        return ligne_d_etat(self.tirage, ascii_seul)


class EcranRangsEpuises(_EcranDeConflit):
    """AC 7.8 -- les 99 rangs sont consommes : **un refus qui nomme ses issues**.

    Le texte du coeur (`io.version_ranks.refus_de_rangs_epuises`, leve par
    `pdf_composition`) est affiche **tel quel** : il nomme le lot, les bornes et
    les deux gestes qui debloquent. L'ecran ne le reformule pas -- une seconde
    redaction divergerait du coeur au premier ajustement -- et il y ajoute ce
    qu'un texte ne peut pas porter : des issues actionnables.
    """

    def __init__(self, tirage: TirageEnConflit, refus: str, *,
                 retenir: Callable[[Issue], None]) -> None:
        super().__init__(ChoixExclusif(issues_des_rangs_epuises(tirage)),
                         retenir=retenir)
        self.tirage = tirage
        self.refus = refus

    def titre_du_cartouche(self, ascii_seul: bool = False) -> str:
        return (jetons.replier_ascii(TITRE_DES_RANGS_EPUISES) if ascii_seul
                else TITRE_DES_RANGS_EPUISES)

    def lignes_du_corps(self, ascii_seul: bool = False) -> list[str]:
        return _replier_sous_un_glyphe(self.refus, "absent",
                                       self.largeur_du_cartouche(), ascii_seul)

    def etats_du_cartouche(self, ascii_seul: bool = False) -> dict[int, str]:
        return {rang: "absent"
                for rang in range(len(self.lignes_du_corps(ascii_seul)))}

    def etat(self, ascii_seul: bool = False) -> str:
        """Un constat, jamais un conseil (`EPIC11-ARB-56`).

        **Elle ne porte AUCUN chiffre**, et c'est delibere : la borne vit au
        coeur, le texte du refus la nomme deja dans le cartouche, et une ligne
        d'etat qui la recopierait serait le seul endroit de la TUI a connaitre
        un nombre de rangs. Elle dit ce qui est constate -- il n'en reste plus.
        """
        table = jetons.glyphes(ascii_seul)
        constat = ETAT_DES_RANGS_EPUISES.format(lot=self.tirage.lot_id)
        return f"{table['absent']}  {constat}"


__all__ = [
    "CLE_ANNULER",
    "CLE_CREER",
    "CLE_MASSE",
    "CLE_REMPLACER",
    "CLE_RETIRER_DE_LA_PASSE",
    "CONSEQUENCE_DE_LA_MASSE",
    "CONSEQUENCE_DE_LA_MASSE_DOUCE",
    "CONSEQUENCE_DE_L_ECRASEMENT",
    "EcranConflitDeTirage",
    "EcranRangsEpuises",
    "EmportDeLaMasse",
    "ETAT_DES_RANGS_EPUISES",
    "ETAT_DU_TIRAGE_PRESENT",
    "ETAT_DU_TIRAGE_SCANNE",
    "ETAT_DU_TIRAGE_SCANNE_DATE",
    "GLOSE_DU_SCAN",
    "GLOSE_MEME_MISE_EN_PAGE",
    "GLOSE_SANS_SCAN",
    "LIBELLE_ANNULER",
    "LIBELLE_DE_LA_DATE",
    "LIBELLE_DE_LA_MISE_EN_PAGE",
    "LIBELLE_DU_CONTENU",
    "LIBELLE_DU_LOT",
    "LIBELLE_DU_SCAN",
    "LIBELLE_CREER",
    "LIBELLE_MASSE",
    "LIBELLE_REMPLACER",
    "LIBELLE_RETIRER_DE_LA_PASSE",
    "MENTION_DE_L_ECRASEMENT",
    "MENTION_DU_TIRAGE_SCANNE",
    "ORDINAUX",
    "PasseDeConflits",
    "RACCOURCIS_DU_CONFLIT",
    "SAUT_DE_LA_MASSE",
    "TITRE_DES_RANGS_EPUISES",
    "TITRE_DU_CONFLIT",
    "TITRE_DU_CONFLIT_SCANNE",
    "TirageEnConflit",
    "choix_du_conflit",
    "conflit_du_tirage",
    "consequence_de_la_masse",
    "consequence_de_l_ecrasement",
    "consequences_des_issues",
    "emport_de_la_masse",
    "issues_des_rangs_epuises",
    "issues_du_conflit",
    "libelle_de_la_creation",
    "libelle_de_la_masse",
    "ligne_d_etat",
    "lignes_du_cartouche",
    "mise_en_page_du_gabarit",
    "ordinal_du_tirage",
    "ordonner_par_lot",
    "rangs_scannes",
]
