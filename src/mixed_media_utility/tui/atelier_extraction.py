# -*- coding: utf-8 -*-
"""L'atelier Extraction : de « quel rush » a « ecrit » (story 11.4).

**Le premier atelier de la TUI.** Les vagues 1 et 2 ont livre le socle -- grille,
jetons, paliers, surface d'execution -- et les ecrans de projet ; rien ne
produisait encore d'artefact. Ce module est celui qui fait passer la TUI de « on
navigue » a « on ecrit ».

Il est aussi le **banc d'essai des composants de la vague 2** : l'explorateur y
trouve son cinquieme site (`EPIC11-ARB-48`), la surface d'execution son premier
vrai producteur, et le panneau chiffre son premier point de jugement reel.

**Ce module ne porte que des ECRANS.** Les deux modeles purs qu'il consomme
vivent a cote et se testent sans clavier :

* :mod:`.rushes` -- la liste des rushes, leur presence, et la sequence de
  relink ;
* :mod:`.cadences` -- la liste cochable, les comptes de frames et les refus du
  coeur.

**Il n'importe JAMAIS `cli.py`** (`EPIC11-ARB-67`, et la meme regle que
`palier_projet.py:9-12`) : les fonctions de `cli.py` impriment sur `stderr` et
rendent un code retour ; les appeler depuis une TUI enverrait des lignes sous
l'ecran dessine. Une frontiere AST le mesure.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import Callable, Sequence

from textual.containers import Vertical
from textual.dom import NoActiveAppError
from textual.widget import Widget
from textual.widgets import Static

from .. import cadence_previz, frame_selection
from . import ajout_de_rush, cadences, jetons, panneau, rushes
from .coque import Contexte, ObjetTravaille, Palier
from .execution import EcranChiffre, bloc_peint
from .ecran_projet import CoutureExplorateur, raccourcis_de_l_explorateur
from .explorateur import FAMILLE_MATIERE, Explorateur, taille_lisible

#: Les deux zones de `E2-1`. L'explorateur **remplace** la liste quand il
#: s'ouvre, il ne s'y ajoute pas (`EPIC11-ARB-48`).
ZONE_LISTE = "liste"
ZONE_EXPLORATEUR = "explorateur"

#: Pourquoi l'explorateur est ouvert. Les deux buts partagent le composant et
#: **pas** ce qu'on fait de la cible : l'un ajoute un rush au projet, l'autre
#: rebranche un rush declare. Les confondre ferait ecrire au mauvais endroit.
BUT_AJOUTER = "ajouter"
BUT_RELINK = "relink"

#: `Tab` nomme sa DESTINATION (`ecran_projet.py:104`), et cette ligne est la
#: quatrieme application de la meme convention.
#:
#: **`F1 aide` y entre le 2026-09-06** (manque `MQ-3` de l'audit du parcours).
#: `EcranRushes` etait la **seule** STATION du paquet dont la ligne omettait
#: `F1` -- recensement mesure sur les quatorze stations --, alors que `F1`
#: ouvre bel et bien le manuel depuis cet ecran. Les treize autres omissions
#: sont des PASSAGES, ce qu'`EPIC11-ARB-140` prescrit.
#:
#: **`Q quitter` n'y entre PAS, et c'est une mesure de largeur, pas un oubli.**
#: La zone utile au plancher vaut 76 colonnes (80 moins le cadre et les
#: marges) ; avec `  F1 aide  Q quitter` la ligne vaudrait **79** colonnes en
#: UTF-8 et **84** une fois repliee en ASCII, donc `jetons.ajuster` la
#: couperait -- et une fin coupee est indistinguable d'une fin absente. Neuf
#: autres ecrans omettent deja `Q quitter` ; aucun autre n'omettait `F1`.
#: `test_manques_des_lignes_d_etat.py` epingle les deux moities de cet
#: arbitrage, la largeur comprise.
RACCOURCIS_RUSHES = ("⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  "
                     "Échap ateliers  F1 aide")

#: Ce que la ligne d'etat DIT quand `⏎` vise un dossier dans l'explorateur
#: d'AJOUT (manque `MQ-2`). Meme forme et meme absence d'accent que ses
#: voisins de refus -- `cadences.MOTIF_DOUBLON`,
#: `atelier_pdf_lots.MOTIF_AUCUN_LOT_COCHE` --, et **aucune touche, aucun
#: conseil d'usage** (`EPIC11-ARB-56`).
#:
#: **Le defaut qu'il ferme est mesure** : l'explorateur d'ajout s'ouvre curseur
#: sur le premier sous-dossier, son bandeau affiche `⏎  Valider   bac/`, et la
#: quatrieme frappe depuis le lancement du produit menait donc a « Cet ecran
#: n'existe pas encore » sur le motif `chemin_non_fichier`. Le coeur n'a rien
#: a trancher ici : l'explorateur sait deja que la cible est un dossier, et le
#: dire en ligne d'etat garde l'operateur sur l'ecran ou il travaille.
#:
#: **Elle tient dans la zone utile GLYPHE COMPRIS** : la ligne d'etat sort
#: prefixee de `✕ `, et une premiere redaction -- « non depuis un dossier » --
#: valait 77 colonnes pour 76, donc `jetons.ajuster` en aurait coupe la fin.
MOTIF_CIBLE_NON_FICHIER = ("Refuse : un rush se declare depuis un fichier "
                           "video, non un dossier.")

#: La question de `E2-1`, verbatim de la maquette et du plan de test manuel
#: (A.2 : « Tu dois arriver **directement** sur « Quel rush extraire ? » »).
#: Elle manquait a l'ecran, alors que les trois autres ecrans de l'atelier
#: portaient deja la leur -- defaut `I2`, trouve en photographiant l'ecran.
TITRE_RUSHES = "Quel rush extraire ?"


def ce_qui_manque_pour_ajouter(cible) -> str:
    """Ce que l'ecran « pas encore » NOMME quand `ajouter` n'est pas injecte.

    **Le defaut que cette phrase ferme est mesure** (`K1.1`, Egan, 2026-08-30) :
    `Ajouter un rush` ouvrait l'explorateur, on designait une vraie video, et
    **rien** ne se passait -- ni ajout, ni message, ni refus. Le rappel
    `ajouter` n'etait injecte nulle part dans le produit (`grep -rn "ajouter="
    src/mixed_media_utility/tui/` rendait zero), et le `if ... is not None` qui
    le gardait transformait ce manque en no-op **silencieux**.

    C'est la quatrieme occurrence dans cet epic du meme mode de panne -- un
    composant livre, teste, et cable nulle part -- et la pire des quatre : les
    trois autres se voyaient a l'ecran, celle-ci ne disait rien. Le nom du
    fichier designe est repris dans la phrase pour que l'operateur voie que son
    geste a bien ete recu, meme quand la suite manque.
    """
    return f"Ajouter {Path(cible).name} au projet"


def ce_qui_manque_pour_extraire(rush_id: str) -> str:
    """Meme regle sur `⏎`, l'autre `if ... is not None` de cet ecran.

    Le produit injecte bien `extraire` (`ChaineReelle.atelier_extraction`),
    donc ce chemin n'est pas celui qu'Egan a rencontre. Il est ferme du meme
    geste parce que c'est le geste qui compte : un rappel absent se DIT.
    """
    return f"Les cadences de {rush_id}"


def ce_qui_manque_pour_refuser(motif: str, source_name: str | None) -> str:
    """Ce que l'ecran « pas encore » NOMME quand le coeur REFUSE la declaration.

    **Elle ne sert plus que QUATRE motifs sur cinq depuis le 2026-09-05.** Ce
    docstring disait « `E2-1f` n'est pas construit, et sa maquette bouge encore
    (`EPIC11-ARB-231`) : `EPIC11-ARB-144` interdit donc de la coder ». Les deux
    blocages sont leves -- la maquette porte ses trois sorties et elle est
    validee --, et `MOTIF_RUSH_DEJA_DECLARE` monte desormais
    :class:`EcranRefusDeConflit` (voir :meth:`EcranRushes._declarer`).

    **Elle n'en sert plus que TROIS depuis le 2026-09-06.** Le motif
    `chemin_non_fichier` ne l'atteint plus par l'ajout : la garde de
    :meth:`EcranRushes._valider_l_explorateur` le refuse en ligne d'etat avant
    d'appeler le coeur (manque `MQ-2`). Elle reste le chemin des trois autres,
    et elle reste le chemin de `chemin_non_fichier` par tout appelant qui
    n'aurait pas vu la cible -- ce que la fonction ne peut pas supposer.

    **Ce qui reste, et ce n'est pas un residu.** Les quatre autres refus
    tombent AVANT toute comparaison d'identite : projet sans manifeste, fichier
    introuvable, chemin qui n'est pas un fichier, source non qualifiee. Le
    cartouche de `E2-1f` n'a pour eux ni criteres a montrer, ni entree
    bloquante a nommer, ni relink a proposer -- lui faire porter un refus qui
    ne compare rien afficherait un cadre vide sous un titre qui affirme qu'un
    rush identique existe.

    Ce qui n'est pas permis, c'est de laisser un refus **muet**. C'est le
    defaut `K1.1` pris par son autre bout : l'operateur designe une vraie
    video, le coeur la refuse pour un motif nomme, et l'ecran ne dirait rien.
    Le motif du coeur voyage donc verbatim jusqu'a l'ecran qui nomme le
    manque -- le meme geste que `ce_qui_manque_pour_ajouter`, et le meme motif.

    Le fichier est nomme quand le refus le porte : c'est ce qu'`EPIC11-ARB-148`
    a fait entrer sur `RefusDeDeclaration`, et le taire ici rendrait le
    message inutilisable devant deux tentatives de suite.
    """
    if source_name:
        return f"Le refus « {motif} » sur {source_name}"
    return f"Le refus « {motif} »"

# --- Colonnes de `E2-1`, relevees au caractere pres sur la maquette ---------
#
# La colonne du nom (5), celle de la technique (26 depuis `J2`) et celle de la
# presence (60) vivent dans `rushes` : ce sont celles de la LISTE, que le
# modele pose. Les trois ci-dessous sont celles des deux blocs que l'ECRAN pose
# autour d'elle, et elles se verifient par la droite : `27 + 47 = 74 = 76 - 2`
# pour la phrase d'ajout, et `35 + 39 = 74` pour celle des modes, la marge
# droite etant celle de tout l'atelier.

#: Ou commence `choisir un fichier vidéo dans l'explorateur`, sur la ligne
#: `Ajouter un rush`. **Une colonne apres celle de la technique** : la phrase
#: n'est pas une colonne de la liste, elle explique l'entree qui la precede, et
#: ce decalage d'une colonne est ce qui la donne a lire comme une explication
#: plutot que comme une valeur technique.
#:
#: **Elle est DERIVEE et non plus ecrite `31`** (`J2`, 2026-08-30) : la colonne
#: technique est passee de 30 a 26 quand Egan a tranche `Q8`, et un litteral
#: laisse ici aurait fait flotter la phrase cinq colonnes a droite de la
#: colonne qu'elle suit -- avec, au-dessus d'elle, un commentaire disant
#: « une colonne apres » qui aurait cesse d'etre vrai. La relation est ecrite
#: une fois, en code, la ou elle ne peut plus deriver.
COLONNE_PHRASE_D_AJOUT = rushes.COLONNE_TECHNIQUE + 1

#: Ou commence `Retrouver le fichier` / `Le désigner à la main`, apres la
#: lettre du mode posee a la colonne du nom.
COLONNE_LIBELLE_DE_MODE = 9

#: Ou commence la phrase du mode, et ou se calent ses lignes de continuation.
COLONNE_PHRASE_DE_MODE = 35

#: L'ecran de refus du relink (`E2-1d`) : trois issues, aucune n'ecrit.
RACCOURCIS_REFUS_RELINK = "⏎ choisir  ↑↓ naviguer  Échap rushes  F1 aide"

#: Ce que `ChoixExclusif.rendu` pose devant chaque libelle : le glyphe de
#: curseur (ou une espace) et une espace. Une issue dont le libelle est CALCULE
#: sur une largeur -- celle du relink porte un chemin -- doit le retrancher,
#: sans quoi sa ligne deborde de deux colonnes.
RESERVE_DU_CURSEUR = 2

#: L'ecran de refus de conflit (`E2-1f`) : trois issues, **deux ecrivent**.
#: Verbatim de la maquette, et elle est la MEME chaine que celle de `E2-1d` --
#: les deux ecrans repondent aux memes touches vers les memes destinations.
#: Elle est ecrite une seconde fois plutot que partagee, et c'est mesure :
#: `manuel.ecrans_par_ligne` rattache une constante a tout ecran qui la
#: **nomme**, si bien qu'une constante partagee ferait annoncer `E2-1d` sous
#: le nom de `E2-1f` et reciproquement. Deux ecrans, deux lignes ; si l'une
#: bouge sans l'autre, c'est un ecart a voir, pas une divergence a taire.
RACCOURCIS_REFUS_DE_CONFLIT = "⏎ choisir  ↑↓ naviguer  Échap rushes  F1 aide"

#: La ligne de raccourcis des quatre etats de `E2-1e`, verbatim des maquettes.
#: `Tab editer le nom` en est ABSENT (`EPIC11-ARB-141`, notes 3 et 11 d'Egan) :
#: il n'y a aucun nom a editer sur cet ecran, donc aucune destination a nommer.
#:
#: **Elle vit ICI et non dans `ajout_de_rush`**, ou vivent pourtant les quatre
#: etats qu'elle accompagne. Le motif est mesure : `manuel.ecrans_par_ligne`
#: rattache chaque ligne de raccourcis a l'ECRAN qui la porte, en cherchant
#: dans le module ou elle est ecrite -- et `ajout_de_rush` ne porte aucune
#: classe d'ecran, par construction. Une ligne posee la-bas tombait donc a
#: l'etage 4 de l'attribution, « orpheline », et le manuel annoncait quatre
#: touches sans pouvoir dire ou elles repondent. Trouve par la garde du manuel,
#: pas par la relecture.
RACCOURCIS_DECLARATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Le titre du CADRE de `E2-1d`. Le code du refus, lui, est la premiere ligne
#: du corps : le cadre dit de quoi il s'agit, le corps dit lequel.
TITRE_DU_REFUS = "Refus"

#: Ce que la ligne d'etat dit apres un relink reussi. **Une reparation muette
#: et une reparation ratee se ressemblent trop** (`EPIC11-ARB-81`).
def phrase_de_relink_reussi(rush_id: str, ascii_seul: bool = False) -> str:
    return jetons.marque("complete", f"{rush_id} est de nouveau lie",
                         ascii_seul)


#: Ce que la ligne d'etat dit apres une declaration reussie (AC 3.7).
#:
#: **Meme motif qu'au-dessus, et il est symetrique** : `EPIC11-ARB-81` dit
#: qu'une reparation muette et une reparation ratee se ressemblent trop. Une
#: DECLARATION muette et une declaration ratee se ressemblent exactement de la
#: meme facon -- c'est litteralement le defaut `K1.1`, ou l'operateur designait
#: une vraie video et ne voyait rien se passer. Le curseur qui se pose sur le
#: rush neuf le dit a qui regarde la liste ; cette phrase le dit a qui regarde
#: la ligne d'etat.
def phrase_de_declaration_reussie(rush_id: str,
                                  ascii_seul: bool = False) -> str:
    return jetons.marque("complete", f"{rush_id} est ajoute au projet",
                         ascii_seul)


#: Ce que la ligne d'etat dit quand le rappel d'ajout a rendu un identifiant
#: que la liste relue ne porte pas.
#:
#: **Ce cas se DIT plutot qu'il ne se tait**, et c'est la regle de `_pas_encore`
#: un cran plus loin : un rappel qui annonce avoir declare `rush_x` alors que le
#: manifeste relu ne le porte pas est une incoherence entre deux sources, pas un
#: no-op. La taire laisserait le curseur la ou il etait -- c'est-a-dire rendrait
#: la panne indistinguable d'un ajout qui aurait simplement atterri ailleurs
#: dans la liste.
def phrase_de_rush_declare_introuvable(rush_id: str,
                                       ascii_seul: bool = False) -> str:
    return jetons.marque(
        "absent", f"{rush_id} declare mais absent de la liste relue",
        ascii_seul)


class Composition:
    """Une zone centrale qui TIENT sa hauteur, et qui le tient en un passage.

    **Le defaut qu'elle ferme** (`I1`, 2026-08-30, trouve en photographiant
    `E2-2` sans affichage) : les ecrans de cet atelier empilent des blocs de
    hauteur VARIABLE -- un refus qui se replie sur deux lignes, un champ de
    saisie qui s'ouvre -- au-dessus de blocs fixes. Additionner les blocs sans
    budget rend une composition plus haute que la zone, et `textual` **coupe
    par le bas, en silence** : la ligne `Borne de sortie` de `E2-2` avait ainsi
    disparu des qu'aucun affichage ne repondait, dans les deux regimes, sur
    l'ecran meme de l'AC 5.2. Aucun banc ne le voyait -- ils mesuraient la
    **largeur** des lignes, jamais leur **nombre**.

    Deux natures de lignes, et c'est tout le mecanisme :

    * une ligne posee par :meth:`poser` ou :meth:`bloc` porte du texte, et
      **elle n'est jamais retiree**. Si la composition deborde encore une fois
      les respirations tombees, c'est une mise en page fautive, pas un
      arbitrage de place : :meth:`rendu` la rend telle quelle pour que le banc
      la voie, plutot que de la tronquer comme le faisait `textual` ;
    * une ligne vide posee par :meth:`respirer` est **sacrifiable**. Elles
      tombent de HAUT EN BAS : la premiere sacrifiee est le blanc de tete, qui
      ne separe rien -- le filet du bandeau le fait deja --, et la derniere
      serait celle qui separe les deux derniers blocs.

    Le rang du curseur et les etats de ligne sont **reindexes** a la sortie :
    ils sont donnes en rang RELATIF au bloc qui les porte, si bien qu'une
    respiration retiree ne decale pas la couleur d'une ligne
    (`EPIC11-ARB-47` et `-71`, ou le rang est passe et jamais devine).
    """

    def __init__(self) -> None:
        self._lignes: list[str] = []
        self._respirations: list[int] = []
        self._etats: dict[int, str] = {}
        self._curseur: int | None = None

    def poser(self, *lignes: str) -> "Composition":
        """Poser des lignes de texte, dans l'ordre. Aucune n'est sacrifiable."""
        self._lignes.extend(lignes)
        return self

    def respirer(self) -> "Composition":
        """Poser une ligne vide **sacrifiable** : elle aere tant que la place
        existe, elle tombe quand un bloc variable s'ajoute."""
        self._respirations.append(len(self._lignes))
        self._lignes.append("")
        return self

    def bloc(self, lignes: Sequence[str], *,
             etats: "dict[int, str] | None" = None,
             curseur: int | None = None) -> "Composition":
        """Poser un bloc, avec ses etats et son curseur en rangs RELATIFS.

        Relatifs, parce que c'est ce que les modeles purs rendent
        (`ListeDeCadences.etats_des_lignes` indexe **sa** liste) : c'est la
        composition qui sait ou ce bloc a atterri, et elle est seule a le
        savoir apres qu'une respiration est tombee.
        """
        depart = len(self._lignes)
        self._lignes.extend(lignes)
        for rang, nom in (etats or {}).items():
            self._etats[depart + rang] = nom
        if curseur is not None:
            self._curseur = depart + curseur
        return self

    def rendu(self, hauteur: int = jetons.HAUTEUR_CENTRE_AU_PLANCHER
              ) -> tuple[list[str], int | None, dict[int, str]]:
        """`(lignes, rang du curseur, etats)`, sous la hauteur demandee.

        `hauteur` est celle de la zone centrale, **derivee** de la grille par
        `jetons.HAUTEUR_CENTRE_AU_PLANCHER` : la poser en dur ici en ferait une
        seconde source de verite, qui divergerait de la premiere retouche du
        cadre.
        """
        a_retirer = set(self._respirations[:max(0, len(self._lignes) - hauteur)])
        lignes: list[str] = []
        etats: dict[int, str] = {}
        curseur: int | None = None
        for rang, ligne in enumerate(self._lignes):
            if rang in a_retirer:
                continue
            if rang == self._curseur:
                curseur = len(lignes)
            if rang in self._etats:
                etats[len(lignes)] = self._etats[rang]
            lignes.append(ligne)
        return lignes, curseur, etats


class EcranRushes(ObjetTravaille, CoutureExplorateur, Palier):
    """`E2-1` -- quel rush extraire, et le relink d'un rush absent.

    **Deux explorateurs, montes a la construction et non a l'ouverture.** C'est
    le motif d'`ecran_projet.py:400` repris tel quel : l'explorateur lit
    `Path.cwd()`, et le lire plus tard ferait dependre le dossier de depart du
    moment ou l'on appuie. Ils different par leur `montrer_fichiers`, passe
    explicitement des deux cotes parce que c'est ce qui rend le reglage lisible
    -- on cherche un dossier a parcourir, ou on designe un fichier.

    **Le curseur ne saute jamais un rush absent** (AC 2.3) : c'est le modele qui
    le garantit, l'ecran ne filtre rien.
    """

    #: Famille « matiere » : les rushes, comme les planches et les scans,
    #: vivent souvent sur le meme volume externe. C'est le parcours que
    #: `EPIC11-ARB-54` nomme -- « sur un parcours Scan puis Pdf, on ne
    #: retraverse pas trois fois la meme arborescence » -- donc les ateliers
    #: PARTAGENT ce souvenir, c'est tout son objet.
    FAMILLE_D_EXPLORATION = FAMILLE_MATIERE

    titre = "Extraction"
    raccourcis = RACCOURCIS_RUSHES
    TRANSITOIRE = False

    def __init__(self, dossier: Path | str,
                 *,
                 existe: Callable[[str], bool] | None = None,
                 probe=None,
                 extraire: Callable[[str], None] | None = None,
                 ajouter: Callable[[Path], "str | None"] | None = None,
                 preparer: Callable[[Path], object] | None = None,
                 ecrire: Callable[[object], "str | None"] | None = None
                 ) -> None:
        super().__init__()
        self.dossier = Path(dossier)
        self._existe = existe
        self._probe = probe
        self._extraire = extraire
        self._ajouter = ajouter
        #: **Les DEUX TEMPS de la declaration** (`EPIC11-ARB-4`), et c'est
        #: pourquoi ils sont deux rappels et non un. `preparer` ne touche aucun
        #: octet -- une frontiere du coeur le mesure --, `ecrire` ecrit. Entre
        #: les deux il y a un ecran, `EcranDeclaration`, et c'est tout l'objet
        #: de la coupure : un panneau chiffre qui n'aurait pas de « avant »
        #: n'aurait rien a montrer.
        self._preparer = preparer
        self._ecrire = ecrire
        self.liste = rushes.lister(self.dossier, existe=existe)
        self.zone = ZONE_LISTE
        self.but: str | None = None
        self.mode: str | None = None
        # Un explorateur par variante, chacun stable. Voir le docstring.
        #
        # **Les DEUX partagent la memoire de la famille « matiere »**, et ce
        # n'est pas un raccourci : `montrer_fichiers` differe, le DOSSIER
        # cherche est le meme -- « retrouver » et « designer » sont deux facons
        # de regarder le meme endroit. Leur donner deux souvenirs ferait
        # retraverser l'arborescence en changeant simplement de facon de
        # chercher.
        self._explorateurs = {
            rushes.MODE_RETROUVER: Explorateur(
                montrer_fichiers=rushes.MONTRER_FICHIERS[
                    rushes.MODE_RETROUVER]),
            rushes.MODE_DESIGNER: Explorateur(
                montrer_fichiers=rushes.MONTRER_FICHIERS[
                    rushes.MODE_DESIGNER]),
        }
        self.explorateur = self._explorateurs[rushes.MODE_DESIGNER]
        self._etat_a_dire = ""
        #: Le rush que le relink en cours vise, et les trois references
        #: d'identite que le coeur va comparer. Poses a l'ouverture de
        #: l'explorateur, remis a `None` quand on en sort : le bandeau et la
        #: ligne d'etat ne survivent pas au geste qui les a ouverts.
        self._vise: str | None = None
        self._reference = None

    # -- lecture -------------------------------------------------------------

    def relire(self) -> None:
        """Relire le manifeste. Appelee apres toute ecriture."""
        curseur = self.liste.curseur
        self.liste = rushes.lister(self.dossier, existe=self._existe)
        # **Par `poser_le_curseur`, jamais par l'attribut** : la liste defile
        # depuis `J1`, et un curseur pose sans recadrer laisserait la fenetre
        # sur les premiers rangs -- apres un ajout, la ligne surlignee ne
        # serait plus a l'ecran du tout.
        self.liste.poser_le_curseur(curseur)

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic de `test_repli_ascii.py` balaye les sous-classes de `Palier` et
        lit `classe.raccourcis` au niveau de la CLASSE. Une propriete ferait
        echapper cet ecran a la mesure, c'est-a-dire affaiblirait une garde
        commune pour faire tenir un ecran.
        """
        if self.zone == ZONE_EXPLORATEUR:
            self.raccourcis = raccourcis_de_l_explorateur(self.explorateur)
        else:
            self.raccourcis = RACCOURCIS_RUSHES

    def lignes(self) -> list[str]:
        if self.zone == ZONE_EXPLORATEUR:
            # **Par mots-cles, et la largeur BRUTE.** `Explorateur.lignes` prend
            # `(largeur, titre, libelle, ascii_seul)` : l'appeler
            # positionnellement posait `ascii_seul` dans `titre`, et l'ecran
            # tombait sur `TypeError: can only concatenate str (not "bool")` des
            # que la zone se dessinait. Defaut trouve en MARCHANT le parcours au
            # clavier, jamais par un test -- les bancs mesuraient `traiter()` et
            # la liste, aucun ne rendait la zone de l'explorateur.
            #
            # La largeur passee est celle de la FENETRE : l'explorateur retire
            # lui-meme ses marges, comme `ecran_projet.py:513` le fait deja.
            return self.explorateur.lignes(
                self.app.size.width, titre=self._titre_de_l_explorateur(),
                libelle=self._libelle_de_l_explorateur(),
                ascii_seul=self.app.ascii_seul)
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E2-1` : sa question, ses rushes, `Ajouter un rush`, et
        le bloc `r` / `d` quand le curseur est sur un absent.

        **Trois de ces quatre blocs manquaient** (`I2`, 2026-08-30) : l'ecran ne
        rendait que la liste. Les producteurs, eux, existaient depuis le lot E
        -- `rushes.lignes_des_modes()`, `rushes.PHRASE_AJOUTER_UN_RUSH`,
        `ListeDesRushes.titre_du_relink()` -- et n'etaient appeles par aucun
        ecran. Le plan de test manuel B.1 et B.2 decrivait donc des elements que
        le produit ne dessinait pas.

        Le rang du curseur et les etats de ligne sont ceux du **modele**,
        decales du bloc de tete par la :class:`Composition` : les recalculer ici
        ferait un second reperage, qui divergerait a la premiere ligne inseree.
        """
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_RUSHES, ascii_seul))
        composition.respirer()
        # **La largeur PLEINE, pas la largeur utile** (`I7`). `rendu` prend
        # la largeur de la FENETRE et retire lui-meme cadre et marges, comme
        # `cadences.ListeDeCadences.lignes` et `rushes.Refus.lignes`. Lui
        # passer `utile` appliquait `largeur_utile` DEUX FOIS -- 80 -> 76 ->
        # 72 --, la colonne technique tombait de 28 a 24 colonnes pour une
        # valeur qui en fait 25, et **la duree etait abregee**. En repli ASCII
        # elle disparaissait entierement : `…` rend `...`, l'ellipse allonge
        # et mange un caractere de plus. C'est une MESURE qui etait perdue, la
        # ou `EPIC11-ARB-21` n'admet d'abreger que le NOM.
        composition.bloc(self.liste.rendu(largeur, ascii_seul),
                         etats=self.liste.etats_des_lignes(),
                         curseur=self.liste.rang_du_curseur())
        composition.poser(self._ligne_d_ajout(utile, ascii_seul))
        titre = self.liste.titre_du_relink()
        if titre is not None:
            # **Le bloc n'apparait QUE sous un rush absent**, et c'est le modele
            # qui le dit : `titre_du_relink()` rend `None` sur un rush lie. Le
            # meme test tient les deux touches -- `r` et `d` ne font rien
            # ailleurs (voir `traiter`).
            composition.respirer()
            composition.poser(filet_titre(titre, utile, ascii_seul))
            composition.respirer()
            composition.poser(*self._lignes_des_modes(utile, ascii_seul))
        return composition.rendu()

    def _ligne_d_ajout(self, utile: int, ascii_seul: bool) -> str:
        """`Ajouter un rush` et sa phrase, aux colonnes de la maquette.

        **Ce n'est pas une entree de la liste**, et `rushes.py:104` dit
        pourquoi : elle ne vient pas du manifeste, et la faire entrer dans la
        liste rendrait « le rush sous le curseur » ambigu au moment ou l'AC 4.4
        en depend. Le curseur ne s'y pose donc pas ; `Tab` fait ce qu'elle
        annonce.
        """
        gauche = (" " * rushes.COLONNE_NOM
                  + _replie(rushes.AJOUTER_UN_RUSH, ascii_seul))
        gauche += " " * max(jetons.CREUX_MINIMAL,
                            COLONNE_PHRASE_D_AJOUT - jetons.colonnes(gauche))
        place = utile - _MARGE_DROITE - jetons.colonnes(gauche)
        return gauche + jetons.ajuster(
            _replie(rushes.PHRASE_AJOUTER_UN_RUSH, ascii_seul), place,
            ascii_seul)

    def _lignes_des_modes(self, utile: int, ascii_seul: bool) -> list[str]:
        """Le bloc `r` / `d`, cale par l'ECRAN sur les donnees du modele.

        `rushes.lignes_des_modes()` rend des donnees et non du texte cale : la
        largeur est ce que l'ecran connait, et deux calages du meme bloc
        divergeraient. La phrase est **enveloppee**, jamais abregee -- c'est
        elle qui dit ce que le mode va chercher.
        """
        place = utile - _MARGE_DROITE - COLONNE_PHRASE_DE_MODE
        lignes: list[str] = []
        for touche, libelle, phrase in rushes.lignes_des_modes():
            tete = " " * rushes.COLONNE_NOM + touche
            tete += " " * max(1, COLONNE_LIBELLE_DE_MODE
                              - jetons.colonnes(tete))
            tete += _a_gauche(
                _replie(libelle, ascii_seul),
                COLONNE_PHRASE_DE_MODE - COLONNE_LIBELLE_DE_MODE, ascii_seul)
            enveloppee = jetons.envelopper(_replie(phrase, ascii_seul), place,
                                           ascii_seul)
            for rang, morceau in enumerate(enveloppee):
                lignes.append(((tete if rang == 0
                                else " " * COLONNE_PHRASE_DE_MODE)
                               + morceau).rstrip())
        return lignes

    def _titre_de_l_explorateur(self) -> str:
        """Ce que le cartouche de l'explorateur annonce, selon le but."""
        if self.but == BUT_RELINK:
            vise = self.liste.rush_a_relinker()
            if vise is not None:
                return rushes.titre_de_relink(vise.rush_id, self.mode)
        return rushes.AJOUTER_UN_RUSH

    def _libelle_de_l_explorateur(self) -> str:
        """`Dossier` quand on parcourt, `Fichier` quand on designe."""
        return ("Dossier" if self.mode == rushes.MODE_RETROUVER else "Fichier")

    def etat(self) -> str:
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_EXPLORATEUR:
            # Meme piege qu'au-dessus : `etat` prend `(utile, ascii_seul)`, et
            # l'appeler positionnellement passait un booleen pour une largeur.
            utile = jetons.largeur_utile(self.app.size.width)
            return self._avec_les_criteres(
                self.explorateur.etat(utile, self.app.ascii_seul), utile,
                self.app.ascii_seul)
        return self.liste.resume(self.app.ascii_seul)

    def _avec_les_criteres(self, mesure: str, utile: int,
                           ascii_seul: bool) -> str:
        """Les trois criteres d'appariement, a droite de la mesure (`E2-1b`).

        **Le defaut qu'elle ferme** (`I4`, 2026-08-30) : `E2-1b` et `E2-1c`
        portaient la ligne d'etat **generique** de l'explorateur, alors que la
        maquette de `E2-1b` y met `rush_hiver : 3 012 frames · TC 00:00:00:00`
        et que le plan de test manuel B.3 l'annonce. Les trois references sur
        lesquelles le coeur va apparier -- nom de base, cardinal, timecode de
        depart -- n'etaient nulle part a l'ecran.

        C'est une **mesure**, pas un conseil : `EPIC11-ARB-56`, verbatim, la
        ligne d'etat « ne porte **aucune touche** [...] **aucun conseil
        d'usage** [...] **aucun motif de conception** ». Ce sont trois valeurs
        lues du manifeste par `relink.charger_reference`, rendues par
        `rushes.resume_de_reference` -- aucun nom de critere n'est ecrit, le
        vocabulaire d'appariement reste dans le coeur (`EPIC11-ARB-32`).

        **C'est la mesure de l'explorateur qui cede quand les deux ne tiennent
        pas ensemble**, jamais les criteres. Meme arbitrage que
        `Contexte.rendu`, et pour le meme motif : le compte du dossier est
        relisible dans le corps de l'ecran, les criteres ne se relisent nulle
        part ailleurs.
        """
        if self.but != BUT_RELINK or self._reference is None:
            return mesure
        criteres = rushes.resume_de_reference(self._reference, ascii_seul)
        separateur = _replie(rushes.SEPARATEUR, ascii_seul)
        place = (utile - jetons.colonnes(separateur)
                 - jetons.colonnes(criteres))
        if place < jetons.CREUX_MINIMAL:
            return jetons.ajuster(criteres, utile, ascii_seul)
        return (jetons.ajuster(mesure, place, ascii_seul) + separateur
                + criteres)

    def objet_du_bandeau(self) -> str:
        """`rush_hiver · retrouver` pendant un relink, rien sinon.

        La maquette `E2-1` porte un bandeau nu -- il n'y a pas encore d'objet
        travaille --, et `E2-1b` / `E2-1c` portent le rush vise et le mode.
        C'est exactement ce que `rushes.bandeau_de_relink` rend, et c'est ici
        qu'il est enfin appele.
        """
        if self.but != BUT_RELINK or self._vise is None or self.mode is None:
            return ""
        return rushes.bandeau_de_relink(self._vise, self.mode)

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-atelier-rushes")
        return [Vertical(self._corps, id="centre-atelier-rushes")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self._appliquer_la_zone()
        # **Le rang du curseur et les etats sont PASSES**, jamais devines
        # (`EPIC11-ARB-47` et `-71`) : l'auto-detection teste `startswith` sur
        # le glyphe de curseur, et les lignes de cet ecran sont indentees --
        # elle ne trouverait rien, en silence.
        #
        # Dans la zone de liste, les trois viennent du MEME passage de
        # `composer` : le bloc de tete decale la liste, et un rang recalcule a
        # cote divergerait du texte des la premiere ligne inseree.
        if self.zone == ZONE_EXPLORATEUR:
            lignes = self.lignes()
            rang = self.explorateur.rang_du_curseur()
            etats = None
        else:
            lignes, rang, etats = self.composer(self.app.size.width,
                                                self.app.ascii_seul)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang,
            etats=etats))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self._appliquer_la_zone()
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        self._etat_a_dire = ""
        if self.zone == ZONE_EXPLORATEUR:
            return self._traiter_l_explorateur(touche, caractere)
        if touche in ("up", "down"):
            self.liste.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "tab":
            return self._ouvrir_l_explorateur(BUT_AJOUTER,
                                              rushes.MODE_DESIGNER)
        if caractere in rushes.TOUCHES_DE_MODE and self.liste.rush_a_relinker():
            # **`r` et `d` ne sont annonces QUE quand un rush est absent** : la
            # liste ne les propose pas autrement, et la touche ne fait rien
            # plutot que d'ouvrir un explorateur sans cible.
            return self._ouvrir_l_explorateur(
                BUT_RELINK, rushes.TOUCHES_DE_MODE[caractere])
        if touche == "enter":
            return self._choisir()
        return False

    def _choisir(self) -> bool:
        action = self.liste.action_du_choix()
        if action is None:
            # **Liste VIDE : `⏎` ne peut vouloir dire qu'une chose ici**
            # (manque `MQ-1`, audit du 2026-09-06). Sur un projet neuf, cet
            # ecran ne porte qu'une ligne -- `Ajouter un rush` --, et `⏎`
            # etait annonce au pied tout en etant STRICTEMENT inerte : quatre
            # frappes mesurees sans que la pile, le texte ni la ligne d'etat
            # bougent d'un caractere. Il fallait deviner `Tab`.
            #
            # **On route plutot qu'on refuse**, et c'est la lecture la plus
            # conservatrice des deux : `EPIC11-ARB-89` interdit le blocage
            # sec, et un refus poli sur un ecran qui n'offre qu'un seul geste
            # serait une corvee de plus, pas une issue. `AJOUTER_UN_RUSH`
            # reste hors de la liste -- l'invariant de `rushes.py:103-108`
            # n'est pas touche : c'est l'ECRAN qui traduit « rien a choisir »
            # en « ouvrir l'ajout », pas le modele qui gagne une entree.
            return self._ouvrir_l_explorateur(BUT_AJOUTER,
                                              rushes.MODE_DESIGNER)
        if action == rushes.ACTION_RELINK:
            # **Le choisir n'extrait rien** (AC 2.4) : il ouvre le relink, dans
            # le mode de recherche par defaut.
            return self._ouvrir_l_explorateur(BUT_RELINK,
                                              rushes.MODE_RETROUVER)
        if action == rushes.ACTION_EXTRAIRE:
            rush_id = self.liste.courant.rush_id
            if self._extraire is None:
                self._pas_encore(ce_qui_manque_pour_extraire(rush_id))
                return True
            self._extraire(rush_id)
        return True

    def _pas_encore(self, ce_qui_manque: str) -> None:
        """Nommer ce qui manque, plutot que de ne rien faire du tout.

        **Aucune echeance n'est annoncee**, du meme motif que
        `ChaineReelle.entrer_commande` : « sans annoncer d'echeance, faute d'en
        connaitre une : une date inventee vaudrait moins que pas de date ». Ce
        que `Ajouter un rush` attend est un point d'entree de COEUR -- declarer
        un rush sans l'extraire --, qui n'existe pas et n'est pas encore
        arbitre.
        """
        from .coque import EcranPasEncore

        self.app.descendre(EcranPasEncore(ce_qui_manque))

    def _ouvrir_l_explorateur(self, but: str, mode: str) -> bool:
        self.but, self.mode = but, mode
        self.explorateur = self._explorateurs[mode]
        # **A l'ouverture, avant la relecture** (2026-09-06) : la reprise peut
        # changer de dossier, et relire d'abord ferait payer deux listages du
        # disque -- dont un de l'ancien dossier, que personne ne verra.
        # `reprendre_la_memoire` relit elle-meme quand elle deplace ; le
        # `relire` ci-dessous reste pour le cas ou elle ne deplace rien (le
        # dossier a pu changer sous nos pieds depuis la derniere visite).
        self.reprendre_la_memoire_de_session()
        self.explorateur.relire()
        self.zone = ZONE_EXPLORATEUR
        # **La cible du relink est MEMORISEE a l'ouverture**, pas relue au
        # moment de dessiner : le bandeau et la ligne d'etat doivent nommer le
        # rush sur lequel le geste a commence, meme si la liste change dessous
        # (une ecriture, un manifeste relu). C'est aussi le rush que
        # `_relinker` traitera -- un seul par validation (AC 4.4).
        self._vise = self._reference = None
        if but == BUT_RELINK:
            vise = self.liste.rush_a_relinker()
            if vise is not None:
                self._vise = vise.rush_id
                self._reference = rushes.reference_de_rush(self.dossier,
                                                           vise.rush_id)
        self._appliquer_la_zone()
        return True

    # -- ce qu'un AUTRE palier peut demander a cet ecran ----------------------

    def ouvrir_le_geste(self, but: str, mode: str) -> bool:
        """Ouvrir l'explorateur sur un geste demande **de l'exterieur**.

        **Elle existe pour que rien n'ecrive `ecran._ouvrir_l_explorateur(...)`
        depuis un autre module**, et ce n'est pas du confort : poser ou appeler
        un membre prive depuis l'exterieur fait de la forme du champ une
        interface, si bien que le renommer casse un appelant qui n'etait cense
        connaitre que l'ecran. C'est le meme motif, dit dans les memes termes,
        que :meth:`~mixed_media_utility.tui.projet_inventaire.EcranInventaireDuProjet.poser_la_suppression`.

        Son appelant est `tui/projet_medias.py`, qui sert `Ctrl+A` et `Ctrl+L`
        de l'inventaire du palier Projet (retour terrain d'Egan, 2026-09-06) :
        les deux touches nomment un geste que cet ecran-ci sait deja faire, et
        elles n'ont besoin de rien d'autre que de le lui demander.

        **A appeler APRES l'empilement** : `_ouvrir_l_explorateur` lit la
        memoire de session sur l'APPLICATION, et un ecran pas encore empile n'y
        a pas acces -- l'explorateur repartirait de `Path.cwd()`.
        """
        return self._ouvrir_l_explorateur(but, mode)

    def dire(self, phrase: str) -> None:
        """Poser sur la ligne d'etat un refus venu d'AILLEURS.

        Le refus se DIT (`EPIC11-ARB-258`) meme quand ce n'est pas cet ecran
        qui le prononce : `Ctrl+L` de `E6-1` peut viser un rush que le
        manifeste ne connait pas, ou un rush deja lie, et dans les deux cas
        l'ecran monte quand meme -- la liste est justement l'endroit ou
        l'operateur corrige son tir. Une phrase posee et aucun ecran de plus.

        Elle ecrit le meme champ que les refus de l'ecran lui-meme, donc elle
        est effacee par la premiere touche, comme eux. C'est voulu : un motif
        qui survivrait a la frappe suivante decrirait un etat revolu.
        """
        self._etat_a_dire = phrase

    # -- les deux gestes que la couture laisse a l'ecran ----------------------

    def _sortir_de_l_explorateur(self) -> bool:
        """Ou mene `Échap` : a la liste, jamais d'un dossier vers son parent."""
        self.zone = ZONE_LISTE
        self.but = self.mode = None
        self._vise = self._reference = None
        self._appliquer_la_zone()
        return True

    def _valider_l_explorateur(self) -> None:
        """Ce que `⏎` fait de la cible.

        **Rien n'est ecrit ici tant que le relink n'est pas valide** (AC 4.5) :
        `preparer_relink` ne touche pas au disque, et l'ecriture n'a lieu
        qu'apres, sur un apercu valide.

        **Un DOSSIER designe pour un ajout se refuse ici** (manque `MQ-2`), en
        ligne d'etat et sans quitter l'ecran : voir la garde ci-dessous.
        """
        cible = self.explorateur.cible_de_validation()
        if cible is None:
            self._etat_a_dire = jetons.marque(
                "substitute", "rien a valider", self.app.ascii_seul)
            return
        if self.but == BUT_AJOUTER:
            if cible.is_dir():
                # **Le refus se DIT ici, sans quitter l'ecran** (manque
                # `MQ-2`). Appeler le temps 1 sur un dossier fait lever le
                # coeur sur `chemin_non_fichier`, et ce motif-la n'a pas
                # d'ecran : il retombe sur le pis-aller « pas encore », qui
                # est un ecran de plus a quitter pour une erreur que
                # l'explorateur voit deja.
                #
                # **La garde porte sur le BUT, pas sur la cible seule**, et
                # c'est structurel : le relink par `r` parcourt et valide des
                # DOSSIERS -- c'est son mode nominal --, donc une garde ecrite
                # au-dessus de `if self.but == BUT_AJOUTER` fermerait ce
                # chemin-la en silence.
                self._etat_a_dire = jetons.marque(
                    "absent", MOTIF_CIBLE_NON_FICHIER, self.app.ascii_seul)
                return
            self.zone = ZONE_LISTE
            self.but = self.mode = None
            self._appliquer_la_zone()
            # **Le TEMPS 1 d'abord, s'il est cable** (`EPIC11-ARB-4`) : le
            # panneau chiffre se peint sur une preparation qui n'a rien ecrit,
            # et l'ecriture attend la validation de l'operateur.
            if self._preparer is not None:
                self._declarer(cible)
                return
            # **Jamais de retour muet** (`K1.1`) : sans rappel d'ajout, l'ecran
            # NOMME ce qui manque au lieu de refermer l'explorateur sur rien.
            # Voir :func:`ce_qui_manque_pour_ajouter` pour ce que ce silence a
            # coute.
            if self._ajouter is None:
                self._pas_encore(ce_qui_manque_pour_ajouter(cible))
                return
            declare = self._ajouter(cible)
            # Le manifeste a pu changer sous l'ecran : on le relit, comme apres
            # toute ecriture (meme geste que `_relinker`).
            self.relire()
            self._viser_le_rush_declare(declare)
            return
        self._relinker(cible)

    def _declarer(self, cible: Path, *, separer: bool = False) -> None:
        """Le TEMPS 1 : preparer, montrer, et **ne rien ecrire** (AC 3.3).

        `preparer_une_declaration` leve ou rend ; il n'existe aucune
        preparation invalide, donc il n'y a rien a garder ici. Ce qui peut
        arriver, en revanche, c'est un **refus** -- l'un des cinq motifs du
        coeur -- et les cinq ne se traitent plus pareil depuis le 2026-09-05 :

        * `MOTIF_RUSH_DEJA_DECLARE` monte :class:`EcranRefusDeConflit`, la
          maquette `E2-1f`, avec ses trois issues cablees ;
        * les **quatre autres** gardent l'ecran « pas encore », qui NOMME le
          motif plutot que de se taire (voir
          :func:`ce_qui_manque_pour_refuser`). Ce n'est pas une dette
          oubliee : ces quatre-la tombent avant toute comparaison, et le
          cartouche de `E2-1f` n'a que la PREUVE d'une comparaison a montrer.

        `separer` est la deuxieme issue de `E2-1f` portee jusqu'au coeur
        (`EPIC11-ARB-232`, `--force-distinct` en ligne de commande) : elle
        affirme que c'est un autre rush malgre les quatre criteres identiques,
        et elle **repasse par le meme temps 1** plutot que d'ecrire par un
        chemin a part -- le panneau chiffre d'`EPIC11-ARB-4` reste obligatoire,
        et le coeur peut refuser une seconde fois.

        **La conclusion tient, sa RAISON a change** (`EPIC11-ARB-233`,
        2026-09-05 ; corrige le meme jour, finding `F17` de la revue). Cette
        place invoquait un suffixe deterministe « une fois pris, il n'y a plus
        rien a forcer » : c'etait vrai du dossier, ce n'est plus vrai du RANG,
        qui trouve toujours une place libre tant que la borne n'est pas
        atteinte. Ce qui peut encore refuser, c'est l'EPUISEMENT des rangs --
        le 99e homonyme, dont la borne est **nommee par le coeur et par lui
        seul** : `test_versionnage_du_scan_en_tui.py` compte a zero le
        vocabulaire des rangs sur tout `tui/`, **prose comprise**, et la
        premiere redaction de ce paragraphe -- qui citait la constante -- l'a
        fait rougir. Un regime rare, mais que ce chemin doit continuer de
        porter jusqu'a l'ecran.

        **Le rang du rush est lu sur la LISTE, pas sur la preparation.**
        `DeclarationPreparee` ne le porte pas et ne le peut pas : c'est un
        cardinal du projet, que cet ecran-ci tient deja. Il vaut le nombre de
        rushes deja declares **plus un** -- le rush qu'on s'apprete a ajouter.
        """
        from ..declaration_de_rush import (
            MOTIF_RUSH_DEJA_DECLARE,
            RefusDeDeclaration,
        )

        try:
            preparee = (self._preparer(cible, force_distinct=True) if separer
                        else self._preparer(cible))
        except RefusDeDeclaration as refus:
            if refus.motif == MOTIF_RUSH_DEJA_DECLARE:
                self.app.descendre(EcranRefusDeConflit(
                    refus, cible,
                    # **La cible est LIEE ici, pendant qu'on la tient** -- meme
                    # geste que `_relinker` avec son `partial(...)`, et pour le
                    # meme motif : la relire plus tard sur l'ecran du dessous
                    # ferait dependre l'ecriture d'un explorateur qui a pu se
                    # refermer.
                    sur_issue=partial(self._suite_du_refus_de_conflit,
                                      refus, cible)))
                return
            self._pas_encore(ce_qui_manque_pour_refuser(
                refus.motif, getattr(refus, "source_name", None)))
            return
        self.app.descendre(EcranDeclaration(
            preparee, rang=len(self.liste.rushes) + 1,
            # **La preparation est LIEE ici, pendant qu'on la tient** -- meme
            # geste que `_relinker` avec son `partial(..., vise.rush_id)`, et
            # pour le meme motif : la relire plus tard sur l'ecran du dessus
            # ferait dependre l'ecriture d'une pile dont on ne sait plus, a ce
            # moment-la, ce qu'elle porte.
            sur_issue=partial(self._suite_de_la_declaration, preparee)))

    def _suite_du_refus_de_conflit(self, refus, cible: Path, issue) -> None:
        """Les TROIS issues de `E2-1f`, et deux d'entre elles ECRIVENT.

        **On remonte D'ABORD, on agit ENSUITE** : meme geste que
        `_suite_de_la_declaration` et `EcranRefusRelink.traiter`, et pour le
        meme motif -- la suite agit sur `EcranRushes`, qui doit etre revenu au
        sommet de la pile avant de changer de zone ou d'empiler un autre ecran,
        sinon le refus resterait peint par-dessus.

        * **relinker** -- le rush deja declare est repointe vers le fichier
          qu'on vient de designer. C'est `refus.rush_id` qui est relinke, et
          **jamais le rush sous le curseur** : `rush_a_relinker()` ne rend que
          le rush courant s'il est ABSENT, or celui-ci est present et n'a
          aucune raison d'etre sous le curseur. Le lire la serait le mode de
          panne de `_find_lot` en 5.7, une fois de plus ;
        * **le declarer separement** -- retour au temps 1 avec
          `force_distinct=True`, puis le chemin de declaration ordinaire, y
          compris son panneau chiffre. Le coeur peut refuser encore une fois,
          et cet ecran-ci se remontera : c'est ce qu'il doit faire ;
        * **annuler** -- rien. Rien n'avait ete ecrit, il n'y a rien a defaire,
          et c'est la sortie que le curseur vise au montage.
        """
        self.app.action_remonter()
        if issue.cle == ajout_de_rush.CLE_SEPARER:
            self._declarer(cible, separer=True)
            return
        if issue.cle != ajout_de_rush.CLE_RELINKER:
            return
        rush_id = getattr(refus, "rush_id", None)
        if rush_id is None:
            # Defensif, et il ne se tait pas : un refus de conflit porte
            # toujours l'identifiant qui bloque (`EPIC11-ARB-148`), mais un
            # refus fabrique a la main peut ne pas l'avoir -- et un relink sans
            # rush vise n'a pas de sens.
            self._pas_encore(ce_qui_manque_pour_refuser(
                refus.motif, getattr(refus, "source_name", None)))
            return
        apercu = rushes.preparer_relink(
            self.dossier, rush_id=rush_id, mode=rushes.MODE_DESIGNER,
            cible=cible,
            **({"probe": self._probe} if self._probe is not None else {}))
        self._appliquer_l_apercu_de_relink(apercu, rush_id,
                                           rushes.MODE_DESIGNER)

    def _appliquer_l_apercu_de_relink(self, apercu, rush_id: str,
                                      mode: str) -> None:
        """Ce qu'on fait d'un apercu de relink : le refus, ou l'ecriture.

        **Ecrite UNE fois pour DEUX gestes** (2026-09-05) : le relink depuis la
        liste (`E2-1b` / `E2-1c`) et celui de `E2-1f`. Les deux preparent
        differemment -- l'un sur le rush sous le curseur et le mode choisi,
        l'autre sur le rush que le refus nomme et une designation a la main --
        mais ce qu'ils font de l'apercu est identique au caractere pres. Deux
        redactions auraient diverge au premier ajustement, et l'une des deux
        est le chemin qu'un operateur emprunte apres un refus, c'est-a-dire
        celui qu'on regarde le moins.

        **Le refus garde le bandeau du geste** : `E2-1d` porte
        `rush_hiver · retrouver` sur sa maquette, comme `E2-1b`. Le rush et le
        mode voyagent donc avec le refus, plutot que d'etre relus d'une liste
        que cet ecran-la n'a pas.
        """
        if not apercu.valide:
            self.app.descendre(EcranRefusRelink(
                apercu.refus, rush_id=rush_id, mode=mode,
                # **L'issue du refus est HONOREE, et c'est le lot `N3`** : voir
                # :meth:`_reprendre_apres_refus`. Le rush vise est lie ici,
                # pendant qu'on le tient : le relire plus tard sur le curseur
                # ferait dependre la reprise d'un curseur qui a pu bouger.
                reprendre=partial(self._reprendre_apres_refus, rush_id)))
            return
        rushes.ecrire_le_relink(self.dossier, apercu)
        self.relire()
        self.liste.viser(rush_id)
        self.zone = ZONE_LISTE
        self.but = self.mode = None
        self._vise = self._reference = None
        self._appliquer_la_zone()
        self._etat_a_dire = phrase_de_relink_reussi(rush_id,
                                                    self.app.ascii_seul)

    def _suite_de_la_declaration(self, preparee, issue) -> None:
        """Le TEMPS 2, ou la sortie -- et une seule des trois issues ecrit.

        **On remonte D'ABORD, on ecrit ENSUITE** : meme geste que
        `EcranRefusRelink.traiter`, et pour le meme motif -- la suite agit sur
        `EcranRushes`, qui doit etre revenu au sommet de la pile avant de
        changer de zone, sinon le panneau resterait peint par-dessus
        l'explorateur qu'on vient de rouvrir.

        * `Déclarer le rush` -- `ecrire_la_declaration`, puis la liste relue et
          le curseur pose sur le rush neuf (AC 3.7) ;
        * `Désigner un autre fichier` -- l'explorateur en mode fichiers, la ou
          le geste avait commence ;
        * `Annuler` -- rien, et c'est la sortie que le curseur vise au montage.

        Sans rappel d'ecriture, `Déclarer le rush` **nomme ce qui manque**
        plutot que de refermer le panneau sur rien : le panneau est le point de
        jugement, et un jugement qui n'aboutit a rien est le defaut `K1.1`.
        """
        self.app.action_remonter()
        if issue.cle == ajout_de_rush.CLE_DESIGNER:
            self._ouvrir_l_explorateur(BUT_AJOUTER, rushes.MODE_DESIGNER)
            self.rafraichir()
            return
        if issue.cle != ajout_de_rush.CLE_DECLARER:
            return
        if self._ecrire is None:
            self._pas_encore(ce_qui_manque_pour_ajouter(preparee.source_path))
            return
        declare = self._ecrire(preparee)
        self.relire()
        self._viser_le_rush_declare(declare)
        self.rafraichir()

    def _viser_le_rush_declare(self, rush_id: "str | None") -> None:
        """AC 3.7 : le curseur se pose sur le rush DECLARE, et le dit.

        **La relecture seule ne suffit pas, et l'ecart se mesure.** Avant ce
        geste, `_valider_l_explorateur` relisait le manifeste puis rendait la
        main : `relire()` repose le curseur au RANG qu'il occupait, or le rush
        neuf s'insere a sa place alphabetique. Un ajout au milieu de la liste
        laissait donc le curseur sur le rush **suivant**, et un ajout en tete
        le decalait d'un cran -- l'operateur retrouvait sa liste avec la
        surbrillance ailleurs que sur ce qu'il venait de faire. C'est le geste
        que `_relinker` fait deja (`self.liste.viser(vise.rush_id)`), et il
        manquait ici parce que le chemin d'ajout n'a jamais eu de suite.

        **L'identifiant vient du rappel, jamais d'un calcul refait ici.** Le
        coeur peut avoir leve une homonymie (`EPIC11-ARB-9`) et ecrit un
        `rush_id` suffixe : le deriver une seconde fois depuis le nom du
        fichier viserait un rush qui n'existe pas, ou pire, l'homonyme. C'est
        `EPIC11-ARB-146` pris a l'endroit -- le `rush_id` est derive **une
        fois**, par le coeur.

        Un rappel qui ne rend rien -- `None`, ce que rend n'importe quelle
        fonction sans `return` -- laisse le curseur ou il est **sans rien
        dire** : c'est le contrat d'avant, et le rompre ferait rougir les bancs
        d'un cablage qui n'a pas encore de raison de nommer son rush.
        """
        if rush_id is None:
            return
        try:
            self.liste.viser(rush_id)
        except KeyError:
            self._etat_a_dire = phrase_de_rush_declare_introuvable(
                rush_id, self.app.ascii_seul)
            return
        self._etat_a_dire = phrase_de_declaration_reussie(
            rush_id, self.app.ascii_seul)

    def _relinker(self, cible: Path) -> None:
        """La sequence de relink, **un seul rush par validation** (AC 4.4)."""
        vise = self.liste.rush_a_relinker()
        if vise is None:      # defensif : la touche n'est offerte que sinon
            return
        apercu = rushes.preparer_relink(
            self.dossier, rush_id=vise.rush_id, mode=self.mode, cible=cible,
            **({"probe": self._probe} if self._probe is not None else {}))
        # La suite est partagee avec `E2-1f` : voir
        # :meth:`_appliquer_l_apercu_de_relink`.
        self._appliquer_l_apercu_de_relink(apercu, vise.rush_id, self.mode)

    def _reprendre_apres_refus(self, rush_id: str, cle: str) -> None:
        """Ce que l'issue de `E2-1d` relance vraiment (lot `N3`, 2026-08-30).

        **Le defaut, et il est pire qu'un mauvais explorateur.** `E2-1d`
        propose trois issues -- « Le désigner à la main », « Chercher dans un
        autre dossier », « Revenir à la liste des rushes » -- et les trois
        faisaient **la meme chose** : `traiter` lisait `choix.valider()`
        uniquement pour verifier qu'elle n'etait pas `None`, jetait l'issue, et
        remontait d'un palier. Or remonter d'un palier ne ramene pas a la
        liste : `EcranRushes` est reste dans la ZONE EXPLORATEUR, dans le mode
        du geste qui vient d'echouer. Egan, apres un `r` refuse, a donc choisi
        « Le désigner à la main » et retrouve la vue **par dossiers** de la
        recherche -- pas parce qu'un mauvais explorateur etait appele, mais
        parce qu'aucun ne l'etait.

        C'est la **septieme** occurrence du mode de panne de cet epic, et sa
        famille est voisine sans etre la meme : ici rien ne manquait a
        l'injection, c'est une **valeur de retour lue puis jetee**. Un choix
        qui nomme trois destinations et n'en a qu'une fait mentir deux
        libelles sur trois.

        Les trois issues, desormais :

        * `MODE_DESIGNER` -> l'explorateur en fichiers (`MONTRER_FICHIERS`) ;
        * `MODE_RETROUVER` -> l'explorateur en dossiers ;
        * `ISSUE_REVENIR` -> la liste, par le meme chemin qu'`Échap`.

        **Le rush vise survit au refus** : il est repointe explicitement avant
        de rouvrir. Sans ce `viser`, `_ouvrir_l_explorateur` le redemanderait a
        `rush_a_relinker()`, c'est-a-dire au CURSEUR -- et un operateur qui
        aurait bouge entre-temps relinkerait un autre rush sans que rien ne le
        dise. C'est le mode de panne de `_find_lot` en 5.7, une fois de plus.

        **Rien n'ecrit ici** : ouvrir un explorateur ne touche pas au disque,
        et `_ouvrir_l_explorateur` n'a aucun chemin vers lui.
        """
        self.liste.viser(rush_id)
        if cle == rushes.ISSUE_REVENIR:
            self._sortir_de_l_explorateur()
        else:
            self._ouvrir_l_explorateur(BUT_RELINK, cle)
        self.rafraichir()


class EcranRefusRelink(ObjetTravaille, Palier):
    """`E2-1d` -- le relink a refuse, et il le dit PAR SON CODE.

    Les onze codes du coeur traversent tels quels (AC 4.3) ; deux codes locaux
    couvrent ce que le coeur ne code pas (`EPIC11-ARB-80`), et le message du
    coeur voyage **verbatim** dans le corps meme dans ce cas.

    **Trois issues, aucune n'ecrit** : la garde d'`EPIC11-ARB-45` tient sans
    amenagement. Depuis le lot `N3` les trois mènent chacune ou leur libelle
    l'annonce -- ouvrir un explorateur n'ecrit rien de plus que remonter d'un
    palier, et un banc le mesure sur le disque plutot que de l'affirmer.

    **Le cartouche est un CADRE, pas des lignes de texte** : c'est le motif de
    `DESIGN.md` 7.4, repris de `EcranChiffre` -- le titre est porte par la
    bordure, ce qui rend une ligne de la zone centrale au contenu.
    """

    titre = "Extraction"
    raccourcis = RACCOURCIS_REFUS_RELINK
    #: Un passage : un refus se lit puis se quitte.
    TRANSITOIRE = True

    def __init__(self, refus: rushes.Refus, *, rush_id: str | None = None,
                 mode: str | None = None,
                 reprendre: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.refus = refus
        self.choix = rushes.issues_apres_refus()
        #: Ce que l'issue retenue relance, sur l'ecran d'en dessous. Injecte
        #: par `EcranRushes._relinker` (lot `N3`) : sans lui, les trois issues
        #: feraient a nouveau la meme chose.
        self._reprendre = reprendre
        #: Le rush et le mode du geste qui a refuse, pour la droite du bandeau
        #: (`E2-1d` porte `rush_hiver · retrouver`, comme `E2-1b`). Ils sont
        #: **facultatifs** : un refus rendu hors du parcours de relink -- un
        #: banc, une reprise -- reste montrable, avec un bandeau nu.
        self.rush_id = rush_id
        self.mode = mode

    def objet_du_bandeau(self) -> str:
        if self.rush_id is None or self.mode is None:
            return ""
        return rushes.bandeau_de_relink(self.rush_id, self.mode)

    def lignes_du_refus(self) -> list[str]:
        return self.refus.lignes(self.app.size.width, self.app.ascii_seul)

    def contenu(self) -> list[Widget]:
        self._bloc = Static("", id="chiffres")
        self._corps = Vertical(self._bloc, id="cartouche")
        # **Le cadre porte `Refus`, le corps porte le CODE.** Les deux ne
        # disent pas la meme chose, et la maquette `E2-1d` les separe :
        # `┌ Refus ───┐` puis `✕ candidats-multiples` a l'interieur. Poser le
        # code sur le cadre l'affichait DEUX FOIS -- defaut trouve sur une
        # capture reelle le 2026-08-30, jamais par un test : le banc mesurait
        # le corps, et le titre du cadre n'est pas dans le corps.
        self._corps.border_title = TITRE_DU_REFUS
        self._issues = Static("", id="issues")
        return [self._corps, Static(""), self._issues]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        lignes = self.lignes_du_refus()
        cartouche = jetons.largeur_de_cartouche(self.app.size.width)
        # **Tout le bloc de refus est en `absent`, lignes repliees comprises**
        # (`EPIC11-ARB-71`). L'etat est DONNE : le decalage vaut zero, ce bloc
        # etant seul dans son cartouche.
        self._bloc.update(jetons.peindre(
            [jetons.ajuster(ligne, cartouche, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            etats=self.refus.etats_des_lignes(len(lignes))))
        # **Le rang de la ligne surlignee est PASSE explicitement** (AC 8.5),
        # comme sur `E2-3` et pour le meme motif : `ChoixExclusif.curseur` EST
        # le compteur du modele, et le lire vaut mieux que le faire retrouver
        # par `startswith` -- une detection qui echoue ne leve rien, elle
        # cesse simplement de surligner.
        self._issues.update(bloc_peint(
            self.choix.rendu(ascii_seul=self.app.ascii_seul),
            jetons.largeur_utile(self.app.size.width), self.app,
            rang=self.choix.curseur))
        self.poser_etat(self.refus.ligne_d_etat(self.app.ascii_seul))
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`⏎` **honore l'issue retenue** -- lot `N3`, 2026-08-30.

        Les trois issues nomment trois destinations differentes (designer a la
        main, chercher ailleurs, revenir a la liste) et faisaient jusqu'ici la
        meme chose : `valider()` etait lue pour verifier qu'elle n'etait pas
        `None`, puis **jetee**. Voir `EcranRushes._reprendre_apres_refus` pour
        ce que ce silence a coute et pourquoi ce n'etait pas « retomber sur la
        liste ».

        Aucune n'ecrit, et aucune ne peut ecrire -- `issues_apres_refus` le
        garantit a la construction, et la reprise n'ouvre qu'un explorateur.

        **On remonte D'ABORD, on relance ENSUITE** : la reprise agit sur
        `EcranRushes`, qui doit etre revenu au sommet de la pile avant de
        changer de zone -- sinon l'ecran de refus resterait peint par-dessus
        l'explorateur qu'on vient d'ouvrir.
        """
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is None:
                return True
            self.app.action_remonter()
            # Sans reprise injectee, `⏎` s'arrete a la remontee -- c'est le
            # chemin des bancs qui montent cet ecran a nu, et la garde de
            # `test_les_RAPPELS_acceptes_par_les_ecrans_sont_INJECTES` mesure
            # que le produit, lui, l'injecte toujours.
            if self._reprendre is not None:
                self._reprendre(issue.cle)
            return True
        return False


class EcranRefusDeConflit(ObjetTravaille, Palier):
    """`E2-1f` -- « Un rush identique existe déjà », et TROIS issues.

    **L'ecran que la TUI n'avait pas, et son absence n'etait pas muette.**
    Jusqu'au 2026-09-05, `EcranRushes._declarer` attrapait
    `RefusDeDeclaration` et montait un ecran « pas encore » qui NOMMAIT ce
    manque (« `E2-1f`, l'ecran qui le montrera, n'est pas construit ») : le
    coeur savait refuser depuis `EPIC11-ARB-148`, la CLI savait le dire, et la
    TUI n'avait ni la maquette validee (`EPIC11-ARB-144`) ni les trois sorties
    (`EPIC11-ARB-231`). Les deux blocages sont leves, et c'est ce lot qui
    ferme le pis-aller **a la source**.

    **Il ne vaut que pour UN motif de refus sur cinq**, et c'est une frontiere
    negative du lot : les quatre autres -- projet sans manifeste, fichier
    introuvable, chemin non fichier, source non qualifiee -- gardent le
    « pas encore ». Ce cartouche montre la **preuve** d'une comparaison
    d'identite ; il n'a rien a montrer devant un fichier qui n'existe pas.

    **Trois issues, deux qui ecrivent, et le curseur sur la troisieme.** C'est
    `panneau.ChoixExclusif` qui le garantit (`EPIC11-ARB-7` sous la forme
    d'`EPIC11-ARB-45`) : rien n'est pose a la main ici, ni le curseur, ni le
    rang de l'issue principale.

    **Le cartouche est un CADRE, pas des lignes de texte** (`DESIGN.md` 7.4),
    meme geste que :class:`EcranRefusRelink` : le titre est porte par la
    bordure, ce qui rend une ligne de la zone centrale au contenu -- et cette
    ligne compte, la zone centrale de cet ecran-la etant pleine a 17 sur 17.
    """

    titre = "Extraction"
    raccourcis = RACCOURCIS_REFUS_DE_CONFLIT
    #: Un passage : un refus se lit, se tranche, et se quitte.
    TRANSITOIRE = True

    def __init__(self, refus, chemin_designe: Path | str, *,
                 sur_issue: Callable[[panneau.Issue], None] | None = None
                 ) -> None:
        super().__init__()
        #: Le modele pur. L'ecran ne calcule rien lui-meme : il donne une
        #: largeur et un regime, et il dessine ce qu'on lui rend.
        self.fiche = ajout_de_rush.FicheDeRefusDeConflit(refus)
        #: Le chemin que l'operateur vient de DESIGNER, jamais celui d'ou vient
        #: le rush deja declare (`EPIC11-ARB-153`, note 3). C'est vers lui que
        #: le relink pointe, et c'est la seule place de l'ecran ou il apparait
        #: (note 4) -- le cartouche ne porte que le chemin de l'entree.
        self.chemin_designe = str(chemin_designe)
        self.choix = self.fiche.suites(self.chemin_designe)
        self._sur_issue = sur_issue
        #: L'issue retenue, pour un banc qui monte l'ecran sans rappel. Meme
        #: nom et meme role que sur `EcranChiffre`.
        self.issue_declenchee: panneau.Issue | None = None

    # -- rendu ---------------------------------------------------------------

    def objet_du_bandeau(self) -> str:
        """`plan séquence 12.mov · refusé` -- le nom DESIGNE (`EPIC11-ARB-153`)."""
        return self.fiche.bandeau(self.app.ascii_seul)

    def contenu(self) -> list[Widget]:
        self._bloc = Static("", id="chiffres")
        self._corps = Vertical(self._bloc, id="cartouche")
        # Le cadre porte le TITRE, le corps porte le CODE : c'est le defaut
        # paye sur `E2-1d` le 2026-08-30, ou poser le code sur le cadre
        # l'affichait deux fois -- trouve sur une capture, jamais par un test.
        self._corps.border_title = ajout_de_rush.TITRE_DU_REFUS_DE_CONFLIT
        # La ligne d'explication de `E2-1j` (`EPIC11-ARB-239`). Elle occupe
        # EXACTEMENT la place que la suite « le declarer separement » libere
        # quand les rangs d'homonyme sont pris : `display = False` la retire de
        # la mise en page au lieu de la vider, sans quoi `E2-1f` ordinaire
        # gagnerait une ligne blanche et deborderait ses 17 lignes utiles.
        self._explication = Static("", id="explication")
        self._explication.display = False
        self._issues = Static("", id="issues")
        return [self._corps, Static(""), self._explication, self._issues]

    def _recomposer_les_suites(self, largeur: int, ascii_seul: bool) -> None:
        """Refaire les trois suites a la largeur REELLE, curseur conserve.

        **Elles ne peuvent pas etre figees a la construction**, et c'est ce qui
        distingue cet ecran de :class:`EcranRefusRelink` : le libelle du relink
        porte un CHEMIN, donc il depend de la largeur de la fenetre et du
        regime ASCII -- deux grandeurs que `self.app` seul connait, et qui
        changent quand l'operateur redimensionne.

        Le curseur est reporte plutot que relaisse a `__post_init__` : il a pu
        bouger, et le perdre a chaque redimensionnement ramenerait l'operateur
        sur `Annuler` au milieu de son geste. Le report est **sur le rang**,
        les trois issues gardant leur ordre par contrat.

        **La largeur donnee au modele est celle du LIBELLE, pas celle de la
        zone** : `ChoixExclusif.rendu` prefixe chaque ligne du glyphe de
        curseur et d'une espace. Sans cette reserve, la ligne du relink
        depasserait de deux colonnes et `jetons.ajuster` la couperait par la
        FIN -- c'est-a-dire en mangeant les deux derniers dossiers du chemin
        designe, la seule chose que la note 4 d'Egan met la pour etre lue.
        """
        curseur = self.choix.curseur
        self.choix = self.fiche.suites(
            self.chemin_designe, max(largeur - RESERVE_DU_CURSEUR, 0),
            ascii_seul)
        self.choix.curseur = min(curseur, len(self.choix.issues) - 1)

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        cartouche = jetons.largeur_de_cartouche(self.app.size.width)
        utile = jetons.largeur_utile(self.app.size.width)
        lignes = self.fiche.lignes(cartouche, self.app.ascii_seul)
        # **Seule la ligne du code est en `absent`** : c'est ce que le rendu
        # couleur valide peint, et la preuve n'est pas une erreur. Voir
        # `FicheDeRefusDeConflit.etats_des_lignes`.
        self._bloc.update(jetons.peindre(
            [jetons.ajuster(ligne, cartouche, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            etats=self.fiche.etats_des_lignes()))
        self._recomposer_les_suites(utile, self.app.ascii_seul)
        # `E2-1j` : la ligne se pose AVANT les issues, et son regime est celui
        # que le modele lit sur le refus -- l'ecran ne le redecide pas.
        explication = self.fiche.ligne_des_rangs_epuises(self.app.ascii_seul)
        self._explication.display = explication is not None
        if explication is not None:
            self._explication.update(bloc_peint([explication], utile,
                                                self.app))
        # Le rang surligne est PASSE explicitement (AC 8.5) : `curseur` EST le
        # compteur du modele, et le lire vaut mieux que le faire retrouver par
        # `startswith` -- une detection qui echoue ne leve rien, elle cesse
        # simplement de surligner.
        self._issues.update(bloc_peint(
            self.choix.rendu(ascii_seul=self.app.ascii_seul), utile, self.app,
            rang=self.choix.curseur))
        self.poser_etat(self.fiche.etat(self.choix, self.app.ascii_seul))
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`↑↓` parcourt, `⏎` retient l'issue sous le curseur et la SUIT.

        **L'issue est rendue a l'appelant, jamais jetee** : c'est le defaut du
        lot `N3` sur `E2-1d`, ou trois libelles nommaient trois destinations et
        faisaient la meme chose. Ici les trois different vraiment -- l'une
        relinke, l'une declare un second rush, l'une ne fait rien -- et les
        deux premieres ECRIVENT.

        **La remontee appartient au rappel, pas a l'ecran** : c'est le geste
        d'`EcranChiffre.valider` et celui de `_suite_de_la_declaration` -- « on
        remonte D'ABORD, on agit ENSUITE », la suite agissant sur `EcranRushes`
        qui doit etre revenu au sommet de la pile. Un ecran qui remonterait
        lui-meme **et** appellerait le rappel depilerait deux fois.

        Sans rappel injecte, `⏎` retient l'issue et s'arrete la : c'est le
        chemin des bancs qui montent cet ecran a nu, et
        :attr:`issue_declenchee` reste lisible pour qu'ils mesurent le CHOIX
        sans avoir a doubler une navigation.
        """
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is None:
                return True
            self.issue_declenchee = issue
            if self._sur_issue is not None:
                self._sur_issue(issue)
            return True
        return False


class EcranDeclaration(EcranChiffre):
    """`E2-1e` et ses trois variantes -- le TEMPS 1 de la declaration d'un rush.

    **C'est le panneau qu'`EPIC11-ARB-4` rend « obligatoire pour toute commande
    qui ecrit »**, et il manquait : `Ajouter un rush` menait a un ecran « pas
    encore », puis, une fois le rappel cable, aurait ecrit sans rien montrer.
    Le coeur a ete coupe en deux temps pour cet ecran-ci
    (`declaration_de_rush.preparer_une_declaration`, qui ne touche **aucun
    octet**, puis `ecrire_la_declaration`) : le panneau se peint sur la
    preparation, et l'ecriture n'a lieu qu'apres validation de l'operateur.

    **Quatre etats, un seul ecran** (`EPIC11-ARB-226`, Egan le 2026-09-05 :
    « Je valide la v4 »). `E2-1g` (colorimetrie non signalee), `E2-1h` (chemin
    coupe) et `E2-1i` (cardinal non corrobore) ne sont pas des ecrans de plus :
    ce sont des etats de celui-ci, et ce qui les distingue vit **entierement**
    dans :class:`~mixed_media_utility.tui.ajout_de_rush.FicheDeDeclaration`,
    qui est pure et se mesure sans clavier.

    **Aucun nom n'est editable ici** (`EPIC11-ARB-141`, AC 3.4) : le modele de
    noms reste vide, donc `Tab` ne trouve aucune destination et rend `False`.
    L'ecran montre `source_name` -- le vrai nom du fichier -- et **jamais**
    l'identifiant derive (`EPIC11-ARB-153`, `EPIC11-ARB-228` : une ligne « nom
    sur le disque » a ete refusee nommement).

    **`E2-1f` -- le refus « rush deja declare » -- n'est PAS ici**, et ce n'est
    plus une absence : c'est :class:`EcranRefusDeConflit`, un ecran a part,
    monte par le meme :meth:`EcranRushes._declarer`. Les deux se ressemblent de
    loin -- un cartouche, des issues -- et ne partagent rien : celui-ci montre
    ce qui SERA ecrit, celui-la montre ce qui EXISTE deja.
    """

    titre = "Extraction"
    raccourcis = RACCOURCIS_DECLARATION
    #: Un passage : le point de jugement chiffre se lit, se tranche, et se
    #: quitte. Comme `EcranChiffre`, dont il herite la valeur -- reecrite ici
    #: pour que la garde d'epic la lise au niveau de CETTE classe.
    TRANSITOIRE = True

    def __init__(self, preparee, *, rang: int | None = None,
                 sur_issue: Callable[[panneau.Issue], None] | None = None
                 ) -> None:
        super().__init__(
            panneau.Panneau(ajout_de_rush.TITRE_DU_CARTOUCHE),
            ajout_de_rush.issues_de_la_declaration(),
            sur_issue=sur_issue)
        #: Le modele pur des quatre etats. L'ecran ne calcule rien lui-meme :
        #: il donne une largeur et un regime, et il dessine ce qu'on lui rend.
        self.fiche = ajout_de_rush.FicheDeDeclaration(preparee, rang=rang)

    # -- rendu ---------------------------------------------------------------

    def _cartouche(self) -> int:
        """La largeur ECRIVABLE du cartouche, derivee de la fenetre.

        Ecrite une fois : la ligne d'etat et le corps doivent mesurer la coupe
        du chemin sur **la meme** largeur, sans quoi la ligne d'etat pourrait
        annoncer une coupe que le corps n'a pas faite.
        """
        return jetons.largeur_de_cartouche(self.app.size.width)

    def lignes_du_panneau(self) -> list[str]:
        return self.fiche.lignes(self._cartouche(), self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """`plan séquence 12.mov · 25 fps · 4:12` -- le VRAI nom (AC 3.4)."""
        return self.fiche.bandeau(self.app.ascii_seul)

    def etat(self) -> str:
        """La ligne d'etat des quatre maquettes, et rien d'autre.

        Elle **remplace** celle d'`EcranChiffre` (`Rien n'a encore été écrit.`)
        plutot qu'elle ne s'y ajoute : `EPIC11-ARB-56` veut une MESURE, et les
        quatre maquettes en portent une -- le cardinal de frames source, puis
        le rang du rush, la coupe du chemin ou l'absence de colorimetrie.
        L'etat du disque y est garde en seconde moitie, parce que c'est la
        premiere question qu'un operateur se pose devant un panneau qui
        s'appelle « À déclarer ».
        """
        return self.fiche.etat(self._cartouche(), self.app.ascii_seul)

    def contenu(self) -> list[Widget]:
        """Le cartouche, l'assertion de traitement, puis les issues.

        **L'assertion est HORS du cartouche**, et ce n'est pas une preference
        de mise en page : le cadre s'appelle « À déclarer », donc tout ce qu'il
        porte se lit comme destine au manifeste -- or `bt709` n'y est **jamais**
        ecrit (`source_confirmation._normalize_probe_value` l'interdit
        nommement, « ni affiche ni transmis a 3.4 »). Dire dans le cadre que le
        rush sera traite comme du Rec. 709 aurait donc affirme une ecriture qui
        n'a pas lieu.

        Les deux widgets sont **masques** hors de `E2-1g` plutot que vides : un
        `Static` vide garde sa ligne et decalerait la geometrie de l'etat
        nominal. Meme geste que `_refus_du_nom` sur `EcranChiffre`.
        """
        widgets = super().contenu()
        self._blanc_d_assertion = Static("")
        self._assertion = Static("", id="assertion-de-declaration")
        self._blanc_d_assertion.display = False
        self._assertion.display = False
        return [widgets[0], self._blanc_d_assertion, self._assertion,
                *widgets[1:]]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        assertion = self.fiche.assertion(self.app.ascii_seul)
        self._blanc_d_assertion.display = assertion is not None
        self._assertion.display = assertion is not None
        if assertion is not None:
            self._assertion.update(bloc_peint(
                [assertion], jetons.largeur_utile(self.app.size.width),
                self.app))
        super().rafraichir()


# ---------------------------------------------------------------------------
# Les trois ecrans de cadences : `E2-2`, `E2-2b`, `E2-2c`
#
# Ils partagent une geometrie -- l'indentation des blocs, le filet titre, les
# champs mesures en COLONNES -- et un modele pur, `cadences.ListeDeCadences`.
# Aucun d'eux ne compte de frames et aucun ne joue de video : le compte vient de
# `frame_selection`, la lecture de `cadence_previz`, et les deux entrent ici par
# un rappel qu'un test peut doubler.
# ---------------------------------------------------------------------------

#: Colonne ou commence un bloc indente -- la meme que celle de la zone de liste
#: de `cadences`, mesuree sur `E2-2`, `E2-2b` et `E2-2c` : les lignes de
#: cadence, les lignes de rapport et les lignes de lot se calent toutes la.
_INDENT = 5

#: Colonne du titre de zone (`Quelles cadences regarder ?`), mesuree sur les
#: trois maquettes. Il est **moins** indente que les blocs qu'il annonce.
_INDENT_DU_TITRE = 2

#: Les deux colonnes de respiration au bord droit, comme partout ailleurs.
_MARGE_DROITE = 2

#: **Majuscule d'affichage, touche NUE en minuscule** -- la regle des
#: majuscules de raccourci, ecrite en entier dans `coque.py`. La lettre
#: annoncee ici est en majuscule ; la touche cablee reste la minuscule.
RACCOURCIS_CADENCES = ("Espace cocher  A ajouter  ⏎ prévisualiser  "
                       "X extraire sans voir")

#: **Sans affichage, l'entree « previsualiser » n'est pas grisee : elle
#: disparait** (`EPIC11-ARB-41`, « on ne degrade pas une promesse, on la retire
#: quand elle ne peut pas etre tenue »). Annoncer une touche qui ne fait rien
#: serait la degrader.
RACCOURCIS_CADENCES_SANS_ECRAN = "Espace cocher  A ajouter  X extraire sans voir"

#: Pendant une saisie, **aucune lettre n'est un raccourci** (`EPIC11-ARB-68`) :
#: la ligne ne peut donc annoncer que les deux touches qui ne sont pas du texte.
RACCOURCIS_SAISIE_DE_CADENCE = "⏎ ajouter la cadence  Échap annuler"

#: La ligne de `E2-2b` **une fois la lecture faite**. Elle annonce `O`
#: (`N1`, 2026-08-30) : Egan a tape `o` ICI -- sur l'ecran ou l'on vient de
#: regarder -- et rien ne s'est produit, la touche n'etant cablee que sur
#: `E2-2c`. Une touche qui marche la ou l'on n'est pas ne marche pas.
#:
#: **Majuscule d'affichage, touche NUE en minuscule** (lot `O`, 2026-08-30) :
#: la ligne annonce `O revoir`, `EcranPreviz.traiter` teste `caractere == "o"`.
#: La divergence est voulue -- regle ecrite en entier dans `coque.py`.
#:
#: **La destination d'`Échap` y est raccourcie, et c'est une mesure, pas un
#: gout** : `⏎ choisir quoi extraire  O revoir  Échap reprendre les cadences
#: F1 aide` fait 72 colonnes en UTF-8 mais **77** une fois repliee en ASCII,
#: pour une zone de 76. La majuscule ne change rien a ce compte : la TUI est en
#: chasse fixe, `O` et `o` valent une colonne (mesure au lot `O`). C'est la
#: promesse d'`O` qu'on garde et le mot de trop qu'on retire -- jamais
#: l'inverse.
#:
#: **Les chiffres ont ete corriges le 2026-08-31** (finding `R18`) : ils
#: annoncaient 75 / 80, comptes avant le resserrement d'`EPIC11-ARB-122`. La
#: troncature reste justifiee -- 77 depasse toujours 76 -- mais d'un cran au
#: lieu de quatre, et une justification qui s'appuie sur un chiffre faux ne
#: justifie rien. Forme actuelle : **62 / 67**.
#: MESURE: 62/67
RACCOURCIS_PREVIZ = "⏎ choisir quoi extraire  O revoir  Échap les cadences  F1 aide"

#: La ligne de `E2-2b` **avant** que la fenetre ne soit ouverte, et c'est
#: l'invitation qu'Egan demande (`K1.2`, 2026-08-30) : « cet ecran invite a
#: taper `⏎` une premiere fois pour ouvrir la previz ». `⏎` nomme donc ici sa
#: DESTINATION -- ouvrir la fenetre --, avant de nommer la suivante, choisir
#: quoi extraire, une fois la lecture faite.
RACCOURCIS_PREVIZ_AVANT = ("⏎ ouvrir la fenêtre  Échap reprendre les cadences"
                           "  F1 aide")

#: Rien a choisir quand rien n'a ete lu : l'entree principale disparait aussi.
RACCOURCIS_PREVIZ_REFUSEE = "Échap reprendre les cadences  F1 aide"

RACCOURCIS_CHOIX = "Espace cocher  ⏎ continuer  O revoir  Échap retour  F1 aide"

#: Les trois titres de zone, verbatim des maquettes.
TITRE_CADENCES = "Quelles cadences regarder ?"

#: La droite du bandeau des DEUX TEMPS, verbatim des maquettes `E2-2`,
#: `E2-2b` et `E2-2c`. Elle etait vide sur les trois ecrans (`I3`) : le
#: `Contexte.objet` de la coque existait depuis la vague 1 et l'atelier ne le
#: posait nulle part. Elle dit **ou l'on en est** dans le parcours, ce que ni
#: le titre de zone ni la ligne d'etat ne disent.
OBJET_TEMPS_1 = "temps 1 sur 2 · prévisualiser"
OBJET_TEMPS_2 = "temps 2 sur 2 · extraire"
TITRE_PREVIZ = "Lecture comparée — une fenêtre s'est ouverte à côté du terminal"

#: Le meme titre, **au futur**, tant que la fenetre n'est pas ouverte (`K1.2`).
#:
#: Egan, 2026-08-30 : la fenetre s'ouvrait dans `demarrer()`, donc au montage,
#: et `demarrer()` BLOQUE jusqu'a sa fermeture -- `textual` ne peignait jamais
#: `E2-2b` avant. L'operateur voyait donc la fenetre d'abord, et l'ecran
#: d'instructions **apres** l'avoir fermee, ou il annoncait au passe (« une
#: fenetre s'est ouverte ») ce qui venait de se terminer. Deux titres plutot
#: qu'un seul : un ecran qui promet et un ecran qui constate ne disent pas la
#: meme chose, et en garder un seul obligerait a mentir dans l'un des deux
#: temps.
TITRE_PREVIZ_AVANT = "Lecture comparée — une fenêtre va s'ouvrir à côté du terminal"
TITRE_CHOIX = "Lesquelles extraire ?"

#: Il n'y a pas de maquette du refus d'affichage : elle dirait qu'une fenetre
#: s'est ouverte, ce qui serait faux. Le titre suit la forme de `E2-1d` -- un
#: constat au passe, puis le motif du coeur.
TITRE_PREVIZ_REFUSEE = "La lecture comparée n'a pas pu s'ouvrir"

#: Les trois filets titres, verbatim des maquettes.
FILET_BORNES = "Bornes"
FILET_RAPPORT = "Rapport, au fil de la lecture"
FILET_LOTS = "Lots à produire"

#: Le bloc de legende de `E2-2b` : ce que les touches font **dans la fenetre**,
#: qui n'est pas le terminal. Ce n'est pas une ligne d'etat et la regle de
#: sobriete d'`EPIC11-ARB-56` ne la vise pas : elle porte les touches d'une
#: autre surface, que rien d'autre ne dit.
LEGENDE_DE_LA_FENETRE = "Dans la fenêtre :"
#: **Ni pause ni pas-a-pas** (`Q11`, tranchee option `b` le 2026-08-30). Egan
#: defait sa propre decision du 2026-08-29 (« J'aimais bien le image par image
#: en pause quand on est sur la previz ») en connaissance de cause, et son
#: motif vaut mieux que ceux qu'on avait ecrits : « **on juge un mouvement, pas
#: des frames uniques** ». La previz existe pour juger une cadence de LECTURE ;
#: un pas-a-pas ne montre pas ce qu'on est venu voir.
#:
#: La boucle `L` reste : elle est livree par le lot `K2` et elle sert
#: justement a juger un mouvement, en le repassant.
#: **Majuscule d'affichage, touches NUES en minuscule.** `cadence_previz` lie
#: `ord("n")`, `ord("p")`, `ord("r")`, `ord("l")` et `ord("q")` ; cette legende
#: les annonce en majuscule. `L` portait deja la regle avant qu'elle soit
#: generale (voir `cadence_previz.KEY_LOOP`), les quatre autres l'ont recue au
#: lot `O`. **Ne jamais lier la majuscule ici** : `cv2.waitKey` masque a 8 bits
#: sans normaliser la casse, donc `Maj+N` et `n` sont deux codes distincts.
LIGNES_DE_LA_FENETRE = (
    "L boucle · N suivante · P précédente · R relire",
    "Q fermer et revenir au terminal",
)

#: Les deux bornes de `E2-2`. Elles sont **affichees, pas saisies ici** : la
#: maquette n'annonce aucune touche pour les changer, et le compte de frames en
#: depend -- une borne editable sur cet ecran demanderait de recompter a chaque
#: frappe.
LIBELLE_BORNE_D_ENTREE = "Borne d'entrée"
LIBELLE_BORNE_DE_SORTIE = "Borne de sortie"
MENTION_FACULTATIF = "(facultatif)"
#: Largeur du libelle de borne, mesuree sur `E2-2` : la valeur commence en 26.
LARGEUR_DU_LIBELLE_DE_BORNE = 21

#: Les en-tetes du rapport de `E2-2b`, verbatim, et la geometrie de leurs
#: colonnes -- mesuree sur la maquette : cadence en 5, retenues calees a droite
#: en 25, presentees en 38.
#:
#: **La quatrieme colonne, `temps réel`, a ete RETIREE** (lot `M`, 2026-08-30)
#: -- voir le commentaire de :meth:`EcranPreviz.composer`. Les trois qui
#: restent sont des CARDINAUX ; aucune n'est un jugement.
ENTETE_DE_LA_CADENCE = "cadence"
ENTETE_DES_RETENUES = "retenues"
ENTETE_DES_PRESENTEES = "présentées"
_LARGEUR_DE_LA_CADENCE = 12
_LARGEUR_DES_RETENUES = 8
_LARGEUR_DES_PRESENTEES = 10
_CREUX_DU_RAPPORT = 3

#: Ce que la colonne de droite d'une ligne de lot reserve, mesure sur `E2-2c` :
#: le compte se cale a droite en 51 sur une zone de 76. La reserve est comptee
#: depuis le bord DROIT, si bien qu'un terminal plus large allonge la ligne au
#: lieu d'ouvrir une seconde colonne (`EPIC11-ARB-21`).
_RESERVE_DU_LOT = 25

# ---------------------------------------------------------------------------
# **Le « temps reel tenu / non tenu » a QUITTE les ecrans** (lot `M`,
# 2026-08-30). Egan, verbatim : « cette info n'est VRAIMENT pas interessante.
# Elle est deja en couleur dans le panneau de previz lui-meme. J'aimerais
# retirer cette notion de temps reel tenu ou pas des ecrans de la tui, TOUS les
# ecrans. »
#
# Ce qui part, et ce qui reste :
#
# * partent les trois verdicts (`tenu`, `non tenu`, `pause · non mesuré`), la
#   colonne `temps réel` de `E2-2b`, la mention `vue · temps réel …` de
#   `E2-2c`, le compte de passes non mesurees de la ligne d'etat, la teinture
#   des lignes de rapport, et les deux seuils qui n'existaient QUE pour nommer
#   la frontiere d'un verdict qu'on affichait ;
# * **le coeur garde sa mesure, entiere** : `PlaybackReport.temps_reel_tenu`,
#   `LATE_FRAME_RATE_THRESHOLD`, `FINAL_DRIFT_RATIO_THRESHOLD` et
#   `format_report_lines` sont intacts. C'est la fenetre de previz qui porte le
#   temps reel, en couleur, sur les images elles-memes -- et `mmu previz` le
#   chiffre toujours dans son journal. Seul l'AFFICHAGE EN TERMINAL disparait.
#
# **Le defaut de fraicheur que le retrait emporte au passage**, et qui vaut
# d'etre garde en memoire parce que sa famille reste : la mention de `E2-2c`
# etait un **etat derive POSE une fois** sur `cadences.Cadence.mention`, jamais
# recalcule au rendu. `_appliquer_les_verdicts` ne la reposait que pour les
# cadences que la NOUVELLE lecture avait rejouees ; les autres gardaient,
# indefiniment et sans que rien ne le dise, le verdict de la toute premiere
# passe -- celle qui lit un cache froid, donc la plus severe. Un etat derive
# stocke ment des qu'il cesse d'etre reposé ; un etat derive CALCULE au rendu
# ne le peut pas. Ce qui reste a l'ecran est desormais du second genre.
# ---------------------------------------------------------------------------

#: `EPIC11-ARB-76`, verbatim : le temps 1 « **avertit** [...] Il n'interdit pas
#: de regarder ». La lecture comparee n'ecrit rien ; c'est l'extraction qui
#: porte la garde, et le defaut n'etait pas qu'elle reussisse mais que rien ne
#: previenne.
PHRASE_CADENCE_NON_CORROBOREE = (
    "Cette source ne corrobore pas sa cadence ; l'extraction la refusera.")

#: Ce que la TUI ajoute au motif nu du coeur (`EPIC11-ARB-73`). Le conseil de
#: la CLI nomme une option de ligne de commande ; celui-ci nomme la seule chose
#: qu'un operateur de TUI puisse faire.
CONSEIL_SESSION_GRAPHIQUE = "Relancer dans une session graphique."

#: Ce que la ligne d'etat dit quand rien n'a ete lu. C'est un compte, pas un
#: conseil : la ligne d'etat porte une mesure et rien d'autre.
PHRASE_AUCUNE_LECTURE = "aucune passe lue"

def phrase_a_lire(combien: int) -> str:
    """`n cadences à lire` -- ce que la ligne d'etat dit AVANT l'ouverture.

    Un compte de ce qui va etre lu, jamais un conseil ni un nom de touche
    (`EPIC11-ARB-56`) : l'invitation a taper `⏎` vit dans la ligne de
    raccourcis, qui est faite pour ca ; la ligne d'etat, elle, mesure.
    """
    return f"{combien} cadence{'s' if combien > 1 else ''} à lire"


#: Ce que la ligne d'etat dit quand `⏎` ne peut ouvrir aucune fenetre faute de
#: lecteur branche. **Ce n'est pas du silence** : un `if ... is not None` qui
#: rend `None` est exactement le defaut que `K1.1` ferme, et il ne se rouvre
#: pas ici par la petite porte.
PHRASE_AUCUN_LECTEUR = "aucun lecteur n'est branché sur cet écran"


@dataclass(frozen=True)
class SourceSondee:
    """Ce que le probe a rendu, **paye une seule fois** et repasse ensuite.

    `EPIC11-ARB-79` : le compte de frames vient de
    `frame_selection.select_source_frames`, appele directement avec la
    `Fraction` exacte et le cardinal **deja sonde**. Le probe reste paye une
    seule fois -- c'est son resultat qu'on repasse a chaque comptage --, mais il
    ne passe **pas** par `prepare_previz`, dont le filtre d'entrees refuse une
    `Fraction` : la convertir en flottant reintroduirait l'approximation que le
    modele garde exacte.
    """

    video_path: Path
    fps_source: Fraction
    source_frame_count: int
    source_frame_count_is_exact: bool = True
    source_start_timecode: str | None = None


@dataclass(frozen=True)
class LotAProduire:
    """Un lot que la validation du temps 2 produira : son nom, son compte, sa
    cadence **exacte**.

    Le nom vient de l'appelant (`nommer`), pas d'ici : la convention de nommage
    des lots vit dans le lot des noms, et deux ecritures d'une meme convention
    divergeraient. Ce qui vit ici est la ligne qui les montre.
    """

    nom: str
    compte: int
    cadence: Fraction


def compteur_de_frames(source: SourceSondee, *,
                       borne_d_entree: str | None = None,
                       borne_de_sortie: str | None = None):
    """Le compteur que `ListeDeCadences` consomme, branche sur le vrai coeur.

    **Aucun produit duree x cadence** (`EPIC11-ARB-30`, verbatim : « le noyau ne
    derive jamais le cardinal d'une duree, il l'exige ») : le cardinal est celui
    que `select_source_frames` rend, pour la cadence exacte demandee et dans la
    fenetre des bornes.

    Il ne laisse remonter que des `FrameSelectionError` -- ce que le modele pur
    sait transformer en cadence refusee, avec les mots du coeur.
    """
    def compter(valeur: Fraction) -> int:
        return frame_selection.select_source_frames(
            fps_source=source.fps_source,
            fps_target=valeur,
            source_frame_count=source.source_frame_count,
            source_frame_count_is_exact=source.source_frame_count_is_exact,
            source_start_timecode=source.source_start_timecode,
            source_in_timecode=borne_d_entree,
            source_out_timecode=borne_de_sortie,
        ).expected_frame_count

    return compter


def texte_de_cadence_exacte(valeur: Fraction, ascii_seul: bool = False) -> str:
    """La cadence **sans perte** : `25`, `12,5`, `25/3`.

    Elle double `cadences.texte_de_cadence` sans la remplacer, et les deux
    coexistent parce qu'elles ne disent pas la meme chose. La liste ecrit
    `8,333` -- trois decimales, la maquette fait foi -- ; la ligne d'un lot
    ecrit `25/3`, parce qu'un lot porte ce que l'operateur a demande, « une
    image sur trois » (`EPIC11-ARB-62`), et qu'un arrondi y nommerait un lot
    qui ment sur ce qu'il contient.

    Une cadence dont le denominateur n'a que des facteurs 2 et 5 a une ecriture
    decimale **finie** : c'est celle qu'on rend. Les autres gardent leur ratio.
    """
    reste = valeur.denominator
    for facteur in (2, 5):
        while reste % facteur == 0:
            reste //= facteur
    if reste != 1:
        return f"{valeur.numerator}/{valeur.denominator}"
    decimal = Decimal(valeur.numerator) / Decimal(valeur.denominator)
    texte = format(decimal.normalize(), "f").replace(".", ",")
    return jetons.replier_ascii(texte) if ascii_seul else texte


def rapport_de_la_cadence(rapports: Sequence, valeur: Fraction):
    """Le **DERNIER** rapport de cette cadence, ou `None`.

    Le dernier et non le premier, et ce n'est pas un detail : `play_cadences`
    empile ses rapports dans l'ordre ou les passes ont ete jouees, et `p`, `r`
    puis `o` font rejouer une meme cadence. Rendre le premier afficherait les
    **cardinaux de la premiere passe** -- celle qui lit un cache froid -- sur
    une cadence que l'operateur vient de revoir : exactement le mode de panne
    de `_find_lot` en 5.7, ou une fonction rendait le premier element au lieu
    de la cible.
    """
    cible = float(valeur)
    trouve = None
    for rapport in rapports:
        if rapport.fps_target == cible:
            trouve = rapport
    return trouve


def _a_gauche(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un champ cale a gauche, mesure en **COLONNES** et jamais en `len()`."""
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return texte + " " * max(0, largeur - jetons.colonnes(texte))


def _a_droite(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return " " * max(0, largeur - jetons.colonnes(texte)) + texte


def _application_montee(ecran):
    """L'application qui porte `ecran`, ou `None` quand il n'est pas monte.

    `textual` fait de `Screen.app` une propriete qui **leve** hors montage --
    y compris a travers `getattr(..., None)`, la valeur par defaut ne couvrant
    que `AttributeError`. Les bancs construisent les ecrans a nu ; sans cette
    fonction, `_lancer_apres_le_dessin` ne pourrait pas s'y appeler du tout,
    alors que son repli direct est justement fait « pour les appelants qui ne
    montent aucune application ».
    """
    try:
        return ecran.app
    except NoActiveAppError:
        return None


def _replie(texte: str, ascii_seul: bool) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def ligne_de_titre(titre: str, ascii_seul: bool = False) -> str:
    """Le titre de zone, a l'indentation des maquettes."""
    return " " * _INDENT_DU_TITRE + _replie(titre, ascii_seul)


def filet_titre(titre: str, utile: int, ascii_seul: bool = False) -> str:
    """`── Bornes ────…────` -- le filet qui porte son titre.

    **Il se replie aussi** : `─` n'est pas de l'ASCII, et un terminal qui ne
    rend pas `▓` ne rend pas davantage un filet Unicode. Le repli garde la meme
    largeur, les deux caracteres occupant une colonne.
    """
    trait = "-" if ascii_seul else "─"
    tete = f"{' ' * _INDENT_DU_TITRE}{trait * 2} {_replie(titre, ascii_seul)} "
    reste = utile - _MARGE_DROITE - jetons.colonnes(tete)
    return tete + trait * max(0, reste)


def _dit(nom_etat: str, texte: str, ascii_seul: bool = False) -> str:
    """Une ligne d'etat qui porte un glyphe : deux blancs apres lui.

    C'est la forme des maquettes, distincte du glyphe colle d'un cartouche, et
    celle que `rushes.Refus.ligne_d_etat` emploie deja.
    """
    glyphe = jetons.glyphes(ascii_seul)[nom_etat]
    return _replie(f"{glyphe}  {texte}", ascii_seul)


class _EcranDeCadences(ObjetTravaille, Palier):
    """Ce que les trois ecrans partagent : le corps peint, et rien d'autre.

    Chacun rend `composer(largeur, ascii_seul)` -> `(lignes, rang, etats)`
    **en un seul passage**. Un second reperage tenu ailleurs -- une methode qui
    rendrait les lignes et une autre qui rendrait les rangs colores -- divergent
    des la premiere ligne inseree : c'est la meme raison qui fait que
    `cadences.rang_du_curseur` indexe la liste que `cadences.lignes` rend.
    """

    titre = "Extraction"
    #: Formulaires : ils occupent la pile sans etre des paliers.
    TRANSITOIRE = True
    #: L'identifiant du widget de corps, redefini par chaque ecran.
    ID_DU_CORPS = "corps"

    def __init__(self) -> None:
        super().__init__()
        #: Ce que la ligne d'etat dit **a la place** de sa mesure, le temps
        #: d'un refus : `(nom d'etat, texte)`. Le couple est garde brut, et non
        #: deja peint, pour que la ligne se redise dans les deux regimes.
        self._a_dire: tuple[str, str] | None = None

    # -- lecture --------------------------------------------------------------

    def composer(self, largeur: int,
                 ascii_seul: bool = False) -> tuple[list[str], int | None,
                                                    dict[int, str]]:
        raise NotImplementedError

    def mesure(self, ascii_seul: bool = False) -> str:
        """Ce que la ligne d'etat dit quand il n'y a pas de refus a dire."""
        raise NotImplementedError

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        if self._a_dire is not None:
            return _dit(self._a_dire[0], self._a_dire[1], ascii_seul)
        return self.mesure(ascii_seul)

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.ligne_d_etat(self.app.ascii_seul)

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        lignes, rang, etats = self.composer(self.app.size.width,
                                            self.app.ascii_seul)
        # **Le rang du curseur et les etats sont DONNES, jamais devines**
        # (`EPIC11-ARB-47` et `-71`) : l'auto-detection teste `startswith` sur
        # le glyphe de curseur, or ces lignes-ci sont indentees ; et la
        # reconnaissance par motif ne teint ni un glyphe pose dans un cartouche
        # ni une ligne de continuation.
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in lignes],
            ascii_seul=self.app.ascii_seul,
            sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang,
            etats=etats))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self.demarrer()
        self.rafraichir()

    def demarrer(self) -> None:
        """Ce que l'ecran fait au montage. Par defaut : rien."""

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        raise NotImplementedError


class EcranCadences(_EcranDeCadences):
    """`E2-2` -- quelles cadences regarder, et les deux bornes de la fenetre.

    La liste est le modele pur `cadences.ListeDeCadences` ; cet ecran ne compte
    rien, ne nomme rien et ne juge rien. Il branche trois choses : le compteur
    du coeur, le clavier, et les deux issues du temps 1 -- `⏎` previsualiser,
    `x` extraire sans regarder (AC 5.1).

    **`Espace` garde son role ici, et c'est une frontiere volontaire.**
    `EPIC11-ARB-45` retire la case a cocher de tout ecran a **issue unique** ;
    cette liste-ci n'en est pas un, et la case y reste.
    """

    raccourcis = RACCOURCIS_CADENCES
    ID_DU_CORPS = "corps-cadences"

    def __init__(self, source: SourceSondee, *,
                 borne_d_entree: str | None = None,
                 borne_de_sortie: str | None = None,
                 previsualiser: Callable[[cadences.Validation], None] | None = None,
                 extraire: Callable[[cadences.Validation], None] | None = None,
                 verifier_l_affichage: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.source = source
        self.borne_d_entree = borne_d_entree
        self.borne_de_sortie = borne_de_sortie
        self._previsualiser = previsualiser
        self._extraire = extraire
        self._verifier_l_affichage = (verifier_l_affichage
                                      or cadence_previz.ensure_display_available)
        self.liste = cadences.ListeDeCadences.remarquables(
            source.fps_source,
            compteur_de_frames(source, borne_d_entree=borne_d_entree,
                               borne_de_sortie=borne_de_sortie))
        #: Le texte en cours de frappe, ou `None` hors saisie. La chaine vide
        #: est un etat legitime -- on vient d'ouvrir le champ --, ce que `None`
        #: ne dirait pas.
        self.saisie: str | None = None
        #: Le motif NU du refus d'affichage (`EPIC11-ARB-73`), ou `None`.
        self.refus_d_affichage: str | None = None

    def demarrer(self) -> None:
        """**L'absence d'affichage est detectee AVANT tout lancement** (AC 5.2).

        Elle l'est ici, au montage du temps 1, parce que c'est l'entree
        « previsualiser » qui doit devenir inactive : un refus decouvert apres
        la frappe aurait deja fait descendre d'un ecran.
        """
        try:
            self._verifier_l_affichage()
        except cadence_previz.DisplayUnavailableError as refus:
            self.refus_d_affichage = refus.motif
        self._appliquer_les_raccourcis()

    def _appliquer_les_raccourcis(self) -> None:
        """**`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic balaye les sous-classes de `Palier` et lit `classe.raccourcis` au
        niveau de la CLASSE."""
        if self.saisie is not None:
            self.raccourcis = RACCOURCIS_SAISIE_DE_CADENCE
        elif self.refus_d_affichage:
            self.raccourcis = RACCOURCIS_CADENCES_SANS_ECRAN
        else:
            self.raccourcis = RACCOURCIS_CADENCES

    # -- lecture --------------------------------------------------------------

    def composer(self, largeur: int, ascii_seul: bool = False):
        """Le corps de `E2-2`, **sous la hauteur de la zone centrale**.

        **Le defaut que la :class:`Composition` ferme ici** (`I1`) : le bloc de
        refus d'affichage fait deux lignes, et son blanc de separation une
        troisieme. Additionnes sans budget, les quinze lignes du nominal en
        faisaient dix-huit pour dix-sept dessinees, et `textual` coupait la
        derniere -- `Borne de sortie` disparaissait EN SILENCE, dans les deux
        regimes, sur l'ecran meme de l'AC 5.2. Les respirations tombent
        desormais avant qu'une ligne de texte ne soit perdue.
        """
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_CADENCES, ascii_seul))
        composition.respirer()
        composition.bloc(self.liste.lignes(largeur, ascii_seul),
                         etats=self.liste.etats_des_lignes(),
                         curseur=self.liste.rang_du_curseur())
        if self.refus_d_affichage:
            composition.respirer()
            refus = self._lignes_du_refus(utile, ascii_seul)
            # Toutes les lignes du refus sont en `absent`, les REPLIEES
            # comprises (`EPIC11-ARB-71`) : une ligne de continuation ne porte
            # aucun glyphe, donc la reconnaissance par motif ne la teindrait
            # pas et le refus se lirait comme deux messages.
            composition.bloc(refus,
                             etats={rang: "absent"
                                    for rang in range(len(refus))})
        if self.saisie is not None:
            composition.respirer()
            composition.poser(self._ligne_de_saisie(ascii_seul))
        composition.respirer()
        composition.poser(filet_titre(FILET_BORNES, utile, ascii_seul))
        composition.respirer()
        composition.poser(
            self._ligne_de_borne(LIBELLE_BORNE_D_ENTREE, self.borne_d_entree,
                                 "", utile, ascii_seul),
            self._ligne_de_borne(LIBELLE_BORNE_DE_SORTIE, self.borne_de_sortie,
                                 MENTION_FACULTATIF, utile, ascii_seul))
        return composition.rendu()

    def objet_du_bandeau(self) -> str:
        """`temps 1 sur 2 · prévisualiser`, **tant que la previz est tenable**.

        `EPIC11-ARB-41`, verbatim : « **on ne degrade pas une promesse, on la
        retire quand elle ne peut pas etre tenue** ». Sans affichage il n'y a
        plus deux temps -- l'entree previz est inactive et `x` extrait
        directement --, donc le bandeau ne promet pas un temps 1 qui n'existe
        pas. Il redevient nu, comme celui de `E2-1`.
        """
        return "" if self.refus_d_affichage else OBJET_TEMPS_1

    def _lignes_du_refus(self, utile: int, ascii_seul: bool) -> list[str]:
        """Le motif du coeur, **replie** et indente. Aucun succedane (AC 5.3)."""
        place = utile - _INDENT - _MARGE_DROITE
        glyphe = jetons.glyphes(ascii_seul)["absent"]
        texte = _replie(f"{glyphe} {self.refus_d_affichage}", ascii_seul)
        return [" " * _INDENT + ligne
                for ligne in jetons.envelopper(texte, place, ascii_seul)]

    def _ligne_de_saisie(self, ascii_seul: bool) -> str:
        """Le champ de saisie de `a` : l'invite, le texte, le caret.

        La maquette montre la liste APRES l'ajout, jamais pendant la frappe :
        la forme reprend donc celle des champs deja livres (`noms.ligne`),
        plutot que d'en inventer une seconde.
        """
        table = jetons.glyphes(ascii_seul)
        return (f"{' ' * _INDENT}{table['invite']} "
                f"{_replie(self.saisie or '', ascii_seul)}{table['caret']}")

    def _ligne_de_borne(self, libelle: str, valeur: str | None, mention: str,
                        utile: int, ascii_seul: bool) -> str:
        table = jetons.glyphes(ascii_seul)
        gauche = (" " * _INDENT
                  + _a_gauche(_replie(libelle, ascii_seul),
                              LARGEUR_DU_LIBELLE_DE_BORNE, ascii_seul)
                  + (_replie(valeur, ascii_seul) if valeur else table["neutre"]))
        if not mention:
            return gauche.rstrip()
        mention = _replie(mention, ascii_seul)
        creux = (utile - _MARGE_DROITE - jetons.colonnes(gauche)
                 - jetons.colonnes(mention))
        return gauche + " " * max(jetons.CREUX_MINIMAL, creux) + mention

    def mesure(self, ascii_seul: bool = False) -> str:
        cochees = self.liste.nombre_de_cochees
        frames = self.liste.frames_cochees
        total = len(self.liste)
        texte = (f"{cochees} cadence{'s' if cochees > 1 else ''} "
                 f"cochée{'s' if cochees > 1 else ''} · "
                 f"{frames} frame{'s' if frames > 1 else ''} sur "
                 f"{total} cadence{'s' if total > 1 else ''} "
                 f"proposée{'s' if total > 1 else ''}")
        return _replie(texte, ascii_seul)

    # -- clavier --------------------------------------------------------------

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        self._a_dire = None
        if self.saisie is not None:
            return self._traiter_la_saisie(touche, caractere)
        if touche in ("up", "down"):
            self.liste.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "space" or caractere == " ":
            motif = self.liste.basculer()
            if motif is not None:
                self._a_dire = ("absent", motif)
            return True
        if caractere == "a":
            self.saisie = ""
            self._appliquer_les_raccourcis()
            return True
        if touche == "enter":
            if self.refus_d_affichage:
                # L'entree est INACTIVE, et elle le dit avec le motif du coeur.
                self._a_dire = ("absent", self.refus_d_affichage)
                return True
            return self._valider(self._previsualiser)
        if caractere == "x":
            return self._valider(self._extraire)
        return False

    def _traiter_la_saisie(self, touche: str, caractere: str | None) -> bool:
        """**Aucune lettre n'est un raccourci dans un champ de saisie**
        (`EPIC11-ARB-68`, verbatim) : tout caractere imprimable est du texte,
        sans exception et sans ordre de priorite a maintenir."""
        if touche == "escape":
            self.saisie = None
            self._appliquer_les_raccourcis()
            return True
        if touche == "enter":
            motif = self.liste.ajouter(self.saisie or "")
            if motif is not None:
                # Le champ reste ouvert : le refus nomme ce qui ne va pas, et
                # fermer le champ obligerait a tout retaper pour le corriger.
                self._a_dire = ("absent", motif)
                return True
            self.saisie = None
            self._appliquer_les_raccourcis()
            return True
        if touche == "backspace":
            self.saisie = self.saisie[:-1]
            return True
        if caractere is not None and len(caractere) == 1 and caractere.isprintable():
            self.saisie += caractere
            return True
        return False

    def _valider(self, rappel) -> bool:
        """AC 3.6 : une validation a zero cochee ne passe **jamais** en silence."""
        validation = self.liste.valider()
        if not validation.passe:
            self._a_dire = ("absent", validation.motif or "")
            return True
        if rappel is not None:
            rappel(validation)
        return True


class EcranPreviz(_EcranDeCadences):
    """`E2-2b` -- la lecture comparee, et le rapport qu'elle laisse.

    **Sans affichage, `play_cadences` n'est jamais atteinte** (AC 5.2) :
    `ensure_display_available` est appelee au montage, et le refus arrive avant
    tout lancement. « Un refus qui arrive apres coup vaut un plantage »
    (`EPIC11-ARB-41`).

    **Aucun succedane n'est propose a la place de la previz refusee** (AC 5.3) :
    ni rapport chiffre, ni lecture degradee. « On ne degrade pas une promesse,
    on la retire quand elle ne peut pas etre tenue. »

    **Le rapport ne porte que des CARDINAUX** (`EPIC11-ARB-69` pour l'ecart
    chiffre, lot `M` pour le verdict) : la cadence, les frames retenues, les
    frames presentees. Ni pourcentage, ni `tenu` / `non tenu` -- le temps reel
    se juge dans la fenetre, en couleur, sur les images elles-memes.

    **Cet ecran a DEUX temps, et c'est le correctif `K1.2` du 2026-08-30.**
    Jusque-la, `demarrer()` -- donc le montage -- ouvrait la fenetre lui-meme.
    Or `play_cadences` BLOQUE jusqu'a la fermeture de la fenetre OpenCV :
    `textual` ne peignait donc jamais `E2-2b` avant, et l'operateur voyait
    l'ecran d'instructions **apres** avoir ferme la fenetre, la ou il annoncait
    au passe (« une fenetre s'est ouverte ») ce qui venait de se terminer.

    Depuis :

    1. le montage ne fait plus que la **garde d'affichage** -- elle doit rester
       la, « un refus qui arrive apres coup vaut un plantage » ;
    2. l'ecran se peint alors au **futur** (:data:`TITRE_PREVIZ_AVANT`) et
       invite a `⏎` ;
    3. `⏎` ouvre la fenetre, **apres le dessin** :
       `atelier_extraction_ecriture._lancer_apres_le_dessin` porte deja ce
       rendez-vous pour l'ecran d'execution `E2-4`, et son docstring documente
       ce qui casse quand l'ordre n'est pas tenu ;
    4. la fenetre fermee, l'ecran repasse au **passe**
       (:data:`TITRE_PREVIZ`) avec son rapport, exactement la maquette.

    Le temps courant se lit sur `self.resultat` : `None` tant que la fenetre
    n'a pas rendu de lecture. Aucun second drapeau -- deux memoires du meme
    etat divergent a la premiere retouche.

    **`o` rouvre la fenetre, ICI aussi** (`N1`, 2026-08-30). Egan a tape `o`
    sur cet ecran-la -- celui ou l'on vient de regarder -- et rien ne s'est
    produit : la touche n'etait cablee que sur `E2-2c`, et `E2-2b` ne traitait
    qu'`⏎`. Une touche qui marche a l'ecran suivant ne marche pas.

    Le geste est le meme que sur `E2-2c` : **la session deja en main**
    (`EPIC11-ARB-70`), donc ni probe ni selections repayes, et le rapport
    affiche est celui de la **nouvelle** lecture. C'est aussi ce qui rend le
    rapport de cet ecran RAFRAICHISSABLE : sans `o`, `self.resultat` etait pose
    une fois par `_lire` et rien, jamais, ne pouvait le remplacer.
    """

    raccourcis = RACCOURCIS_PREVIZ_AVANT
    ID_DU_CORPS = "corps-previz"

    def __init__(self, regardees: Sequence[cadences.Cadence],
                 session: cadence_previz.PrevizSession, *,
                 jouer: Callable[[cadence_previz.PrevizSession], object] | None = None,
                 verifier_l_affichage: Callable[[], None] | None = None,
                 choisir: Callable[[object], None] | None = None) -> None:
        super().__init__()
        self.regardees = tuple(regardees)
        self.session = session
        self._jouer = jouer
        self._verifier_l_affichage = (verifier_l_affichage
                                      or cadence_previz.ensure_display_available)
        self._choisir = choisir
        #: Le motif NU du refus (`EPIC11-ARB-73`), ou `None`.
        self.refus: str | None = None
        self.resultat = None

    def demarrer(self) -> None:
        """Le montage : la garde d'affichage, **et plus rien d'autre**.

        La fenetre ne s'ouvre plus ici (`K1.2`) -- voir le docstring de la
        classe. Ce qui reste doit rester : sans affichage, le refus est pose
        avant que `⏎` ne puisse ouvrir quoi que ce soit.
        """
        try:
            self._verifier_l_affichage()
        except cadence_previz.DisplayUnavailableError as refus:
            # **Rien n'est lance.** C'est la seule ligne de cette methode qui
            # compte, et un test la mesure en comptant les appels du joueur.
            self.refus = refus.motif
            self.raccourcis = RACCOURCIS_PREVIZ_REFUSEE
            return

    def _ouvrir_la_fenetre(self) -> bool:
        """Ouvrir la fenetre **apres le dessin** -- `⏎` la premiere fois, `o`
        ensuite (`N1`).

        **Un seul chemin d'ouverture pour les deux touches** : deux redactions
        du meme differe divergeraient a la premiere retouche, et c'est
        exactement ce que `E2-2c` a evite en appelant `play_cadences` avec la
        session deja en main plutot qu'en reconstruisant la sienne.

        Le rendez-vous est celui de
        `atelier_extraction_ecriture._lancer_apres_le_dessin`, ecrit pour
        exactement ce probleme sur `E2-4` -- il est **importe**, jamais
        recopie : une seconde redaction du meme differe divergerait de la
        sienne a la premiere retouche. L'import est local parce que
        `atelier_extraction_ecriture` importe ce module-ci a l'appel, et qu'un
        import de tete y ferait un cycle.

        Le rappel manquant ne rend pas cette touche muette : il se DIT
        (`PHRASE_AUCUN_LECTEUR`) -- c'est la lecon `K1.1` du meme jour.
        """
        from .atelier_extraction_ecriture import _lancer_apres_le_dessin

        if self._jouer is None:
            self._a_dire = ("absent", PHRASE_AUCUN_LECTEUR)
            return True
        _lancer_apres_le_dessin(_application_montee(self), self._lire)
        return True

    def _lire(self) -> None:
        """La lecture elle-meme, une fois l'ecran peint.

        C'est ici, et pas dans `traiter`, que l'ecran repasse au passe : le
        redessin de `on_key` a lieu **avant** que ce differe ne tourne, si bien
        qu'un titre change dans `traiter` serait peint alors que la fenetre
        n'est pas encore ouverte.
        """
        self.resultat = self._jouer(self.session)
        self.raccourcis = RACCOURCIS_PREVIZ
        self.rafraichir()

    def objet_du_bandeau(self) -> str:
        """`temps 1 sur 2 · prévisualiser` : on est encore dans le temps 1,
        c'est la previz elle-meme."""
        return OBJET_TEMPS_1

    @property
    def rapports(self) -> tuple:
        return () if self.resultat is None else tuple(self.resultat.reports)

    def _passes(self) -> list[tuple]:
        apparies = []
        for cadence in self.regardees:
            rapport = rapport_de_la_cadence(self.rapports, cadence.valeur)
            if rapport is not None:
                apparies.append((cadence, rapport))
        return apparies

    @staticmethod
    def _ligne_de_rapport(cadence: str, retenues: str, presentees: str,
                          ascii_seul: bool) -> str:
        """Les TROIS colonnes du rapport, et plus aucune quatrieme.

        La geometrie des trois premieres est inchangee -- c'est celle de la
        maquette, mesuree en colonnes -- ; la colonne de verdict qui les
        suivait est partie avec la notion (lot `M`).
        """
        return (" " * _INDENT
                + _a_gauche(cadence, _LARGEUR_DE_LA_CADENCE, ascii_seul)
                + _a_droite(retenues, _LARGEUR_DES_RETENUES, ascii_seul)
                + " " * _CREUX_DU_RAPPORT
                + _a_droite(_replie(presentees, ascii_seul),
                            _LARGEUR_DES_PRESENTEES, ascii_seul)).rstrip()

    def composer(self, largeur: int, ascii_seul: bool = False):
        utile = jetons.largeur_utile(largeur)
        etats: dict[int, str] = {}
        if self.refus is not None:
            lignes = ["", ligne_de_titre(TITRE_PREVIZ_REFUSEE, ascii_seul), ""]
            glyphe = jetons.glyphes(ascii_seul)["absent"]
            texte = _replie(f"{glyphe} {self.refus}", ascii_seul)
            for ligne in jetons.envelopper(
                    texte, utile - _INDENT - _MARGE_DROITE, ascii_seul):
                etats[len(lignes)] = "absent"
                lignes.append(" " * _INDENT + ligne)
            lignes += ["", " " * _INDENT + _replie(CONSEIL_SESSION_GRAPHIQUE,
                                                   ascii_seul)]
            return lignes, None, etats

        # **Le temps se lit sur `resultat`, et le TITRE en depend** : promettre
        # au futur tant que rien n'est ouvert, constater au passe une fois la
        # fenetre fermee (`K1.2`).
        lue = self.resultat is not None
        lignes = ["", ligne_de_titre(
            TITRE_PREVIZ if lue else TITRE_PREVIZ_AVANT, ascii_seul), ""]
        # **Le repli precede la mesure** : le libelle est replie d'abord, et
        # c'est sa largeur repliee qui donne l'indentation des lignes de
        # continuation -- un repli qui allonge le texte les decalerait toutes.
        legende = _replie(LEGENDE_DE_LA_FENETRE, ascii_seul)
        colonne = jetons.colonnes(legende) + jetons.CREUX_MINIMAL
        for rang, texte in enumerate(LIGNES_DE_LA_FENETRE):
            tete = (_a_gauche(legende, colonne, ascii_seul) if rang == 0
                    else " " * colonne)
            lignes.append(" " * _INDENT + tete + _replie(texte, ascii_seul))
        if self.session.cadence_corroboree is False:
            # **Avertir, jamais interdire** (`EPIC11-ARB-76`).
            lignes.append("")
            etats[len(lignes)] = "substitute"
            lignes.append(" " * _INDENT + jetons.marque(
                "substitute", _replie(PHRASE_CADENCE_NON_CORROBOREE,
                                      ascii_seul), ascii_seul))
        if not lue:
            # **Aucun cadre de rapport avant la lecture** : le filet « Rapport,
            # au fil de la lecture » pose sur zero ligne annoncerait une mesure
            # qui n'a pas commence. L'ecran d'attente ne porte que ce qui va se
            # passer -- et la ligne de raccourcis, elle, porte l'invitation.
            return lignes, None, etats
        lignes += ["", filet_titre(FILET_RAPPORT, utile, ascii_seul), ""]
        lignes.append(self._ligne_de_rapport(
            ENTETE_DE_LA_CADENCE, ENTETE_DES_RETENUES, ENTETE_DES_PRESENTEES,
            ascii_seul))
        # **Une cadence cochee que la session n'a pas jouee n'a pas de ligne** :
        # elle n'a pas ete regardee, et lui en inventer une la ferait passer
        # pour mesuree.
        #
        # **Aucune ligne de rapport n'est TEINTEE** (lot `M`) : la teinture
        # etait le verdict de temps reel dit une seconde fois, en couleur.
        # Retirer le mot et garder la couleur aurait laisse l'ecran juger sans
        # plus dire de quoi -- ce qui est pire que de juger.
        for cadence, rapport in self._passes():
            lignes.append(self._ligne_de_rapport(
                cadence.texte_de_valeur(
                    ascii_seul, cadences.COLONNES_DE_L_EXTRACTION.suffixe),
                str(rapport.frames_attendues), str(rapport.frames_presentees),
                ascii_seul))
        return lignes, None, etats

    def mesure(self, ascii_seul: bool = False) -> str:
        if self.refus is None and self.resultat is None:
            # **Avant l'ouverture, il n'y a rien de LU a compter** : ce qui se
            # mesure est ce qui attend. « aucune passe lue » serait vrai mais
            # dirait l'echec la ou il n'y a qu'un debut.
            return _replie(phrase_a_lire(len(self.regardees)), ascii_seul)
        passes = self._passes()
        if not passes:
            return _dit("absent", PHRASE_AUCUNE_LECTURE, ascii_seul)
        # **Trois cardinaux, et rien qui juge** : le compte de passes « non
        # mesurees » qui fermait cette ligne etait le verdict de temps reel
        # additionne, et il part avec lui (lot `M`).
        lues = len(passes)
        retenues = sum(rapport.frames_attendues for _c, rapport in passes)
        presentees = sum(rapport.frames_presentees for _c, rapport in passes)
        texte = (f"{lues} cadence{'s' if lues > 1 else ''} "
                 f"lue{'s' if lues > 1 else ''} · "
                 f"{retenues} retenue{'s' if retenues > 1 else ''}, "
                 f"{presentees} présentée{'s' if presentees > 1 else ''}")
        return _replie(texte, ascii_seul)

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`⏎` a **deux** sens sur cet ecran, et l'ordre des deux est le
        correctif `K1.2` : la premiere fois il OUVRE la fenetre, ensuite il
        choisit quoi extraire. `o` en rouvre une (`N1`)."""
        self._a_dire = None
        if caractere == "o":
            return self._revoir()
        if touche == "enter":
            if self.refus is not None:
                # Sans affichage il n'y a ni fenetre a ouvrir ni lecture a
                # choisir : la ligne de raccourcis ne promet deja plus `⏎`.
                return True
            if self.resultat is None:
                return self._ouvrir_la_fenetre()
            # Rien a choisir quand rien n'a ete lu : l'issue n'existe pas
            # plutot que de mener a un ecran vide.
            if self._choisir is not None:
                self._choisir(self.resultat)
            return True
        return False

    def _revoir(self) -> bool:
        """`o` -- rouvrir la fenetre sur la **meme session** (`N1`).

        Trois refus, et aucun n'est muet :

        * sans affichage, la touche n'est pas offerte -- la ligne de raccourcis
          du refus ne l'annonce pas, et `EPIC11-ARB-41` veut qu'une promesse
          intenable soit **retiree**, pas grisee ;
        * **avant la premiere lecture, `o` n'a rien a revoir** : la ligne
          d'attente n'annonce que `⏎ ouvrir la fenêtre`, et deux touches pour
          le meme geste apprendraient a l'operateur une touche de trop ;
        * sans joueur branche, le manque se **dit** (:data:`PHRASE_AUCUN_LECTEUR`)
          au lieu d'etre avale par un `if ... is not None` -- lecon `K1.1`.

        La session repassee est celle du temps 1, jamais une preparation neuve
        (`EPIC11-ARB-70`) : `reader` et `cache` naissent a l'interieur de
        `play_cadences`, il n'y a rien a resonder.
        """
        if self.refus is not None or self.resultat is None:
            return False
        return self._ouvrir_la_fenetre()


class EcranChoixDesCadences(_EcranDeCadences):
    """`E2-2c` -- lesquelles extraire, parmi celles qu'on a regardees.

    **Le temps 2 n'herite d'aucun consentement du temps 1** (AC 5.5) : la liste
    arrive entierement decochee, quoi qu'on ait coche au temps 1, et `⏎` repasse
    par le rappel de confirmation que l'appelant fournit. Cet ecran ne construit
    aucun panneau et n'ecrit rien.

    **`o` rouvre la previz sans repayer le probe** (`EPIC11-ARB-70`, verbatim :
    « rouvrir, c'est rappeler `play_cadences` avec la session deja en main »).
    La session est celle que `PrevizResult` a rendue ; `reader` et `cache` sont
    crees a l'interieur de `play_cadences`, donc rien n'est a rejouer.
    """

    raccourcis = RACCOURCIS_CHOIX
    ID_DU_CORPS = "corps-choix"

    def __init__(self, regardees: Sequence[cadences.Cadence], resultat, *,
                 nommer: Callable[[cadences.Cadence], str],
                 confirmer: Callable[[tuple], None] | None = None,
                 rejouer: Callable[[cadence_previz.PrevizSession], object] | None = None,
                 octets_par_frame: int | None = None) -> None:
        super().__init__()
        self.resultat = resultat
        self._nommer = nommer
        self._confirmer = confirmer
        self._rejouer = rejouer
        self._octets_par_frame = octets_par_frame
        vues = [cadence for cadence in regardees
                if rapport_de_la_cadence(self._rapports(), cadence.valeur)
                is not None]
        self.liste = cadences.ListeDeCadences(
            cadences=[cadences.Cadence(
                valeur=cadence.valeur, libelle=cadence.libelle,
                compte=cadence.compte, motif=cadence.motif)
                for cadence in vues],
            # Aucune cadence n'entre ni ne sort de cette liste : le compteur
            # n'a donc rien a compter. Il existe parce que le modele en exige
            # un, et il refuse plutot que d'inventer un cardinal.
            compteur=_compteur_refuse)

    def objet_du_bandeau(self) -> str:
        """`temps 2 sur 2 · extraire` -- et c'est le seul ecran de l'atelier
        qui l'annonce : le temps 2 n'herite d'aucun consentement du temps 1
        (`EPIC11-ARB-24`), il se re-choisit."""
        return OBJET_TEMPS_2

    def _rapports(self) -> tuple:
        return () if self.resultat is None else tuple(self.resultat.reports)

    # -- lecture --------------------------------------------------------------

    def lots(self) -> tuple[LotAProduire, ...]:
        """Une cochee, un lot : `run_extraction` prend **un** `fps_target`."""
        return tuple(
            LotAProduire(nom=self._nommer(cadence), compte=cadence.compte or 0,
                         cadence=cadence.valeur)
            for cadence in self.liste.cochees)

    def ligne_de_lot(self, lot: LotAProduire, utile: int,
                     ascii_seul: bool = False) -> str:
        compte = str(lot.compte)
        droite = (f" frame{'s' if lot.compte > 1 else ''} · "
                  f"{texte_de_cadence_exacte(lot.cadence, ascii_seul)}"
                  f"{cadences.COLONNES_DE_L_EXTRACTION.suffixe}")
        colonne = max(utile - _RESERVE_DU_LOT,
                      _INDENT + len(compte) + jetons.CREUX_MINIMAL)
        place = colonne - _INDENT - jetons.colonnes(compte) - jetons.CREUX_MINIMAL
        # **Un nom long est tronque a l'affichage, jamais a l'ecriture**
        # (`EPIC11-ARB-21`), et il l'est AU MILIEU : deux lots d'un meme rush ne
        # different souvent qu'a leur derniere lettre.
        nom = jetons.abreger_nom(_replie(lot.nom, ascii_seul), max(place, 0),
                                 ascii_seul)
        creux = colonne - _INDENT - jetons.colonnes(nom) - jetons.colonnes(compte)
        return (" " * _INDENT + nom + " " * max(jetons.CREUX_MINIMAL, creux)
                + compte + _replie(droite, ascii_seul)).rstrip()

    def composer(self, largeur: int, ascii_seul: bool = False):
        utile = jetons.largeur_utile(largeur)
        lignes = ["", ligne_de_titre(TITRE_CHOIX, ascii_seul), ""]
        etats: dict[int, str] = {}
        rang_de_la_liste = len(lignes)
        for decalage, nom in self.liste.etats_des_lignes().items():
            etats[rang_de_la_liste + decalage] = nom
        # **La zone de liste n'est pas calee a une hauteur fixe ici** : `E2-2c`
        # ne montre que les cadences regardees, et la maquette place le rappel
        # des lots juste sous la derniere. Les blancs de remplissage du modele
        # tombent donc, jamais ses lignes.
        rendues = list(self.liste.lignes_de_liste(
            utile, ascii_seul, cadences.COLONNES_DE_L_EXTRACTION))
        while rendues and not rendues[-1].strip():
            rendues.pop()
        lignes += rendues
        rang = self.liste.rang_du_curseur()
        lignes += ["", self.liste.ligne_des_lots(ascii_seul), "",
                   filet_titre(FILET_LOTS, utile, ascii_seul), ""]
        lignes += [self.ligne_de_lot(lot, utile, ascii_seul)
                   for lot in self.lots()]
        return lignes, (None if rang is None else rang_de_la_liste + rang), etats

    def mesure(self, ascii_seul: bool = False) -> str:
        lots = self.lots()
        frames = sum(lot.compte for lot in lots)
        texte = (f"{len(lots)} lot{'s' if len(lots) > 1 else ''} · "
                 f"{frames} frame{'s' if frames > 1 else ''}")
        if self._octets_par_frame:
            # **Le majorant n'est dit que s'il est DONNE.** Le fabriquer ici
            # demanderait d'inventer un poids de frame, c'est-a-dire d'ecrire un
            # chiffre que rien ne mesure ; il vient de l'appelant, qui tient la
            # mesure, ou il ne s'ecrit pas.
            majorant = taille_lisible(frames * self._octets_par_frame)
            texte += f" · ~ {majorant} {panneau.MENTION_MAJORANT}"
        return _replie(texte, ascii_seul)

    # -- clavier --------------------------------------------------------------

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        self._a_dire = None
        if touche in ("up", "down"):
            self.liste.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "space" or caractere == " ":
            motif = self.liste.basculer()
            if motif is not None:
                self._a_dire = ("absent", motif)
            return True
        if caractere == "o":
            return self._rouvrir()
        if touche == "enter":
            validation = self.liste.valider()
            if not validation.passe:
                self._a_dire = ("absent", validation.motif or "")
                return True
            if self._confirmer is not None:
                self._confirmer(self.lots())
            return True
        return False

    def _rouvrir(self) -> bool:
        """`o` -- **la session deja en main**, jamais une preparation neuve.

        **Les cochees ne bougent pas** : rouvrir la previz remesure ce qu'on
        regarde, pas ce qu'on a choisi. Perdre le choix en cours a chaque `o`
        rendrait la touche inutilisable.

        Rien de derive n'est **repose** ici depuis le lot `M` : la seule chose
        que la relecture changeait etait la mention de temps reel, qui n'existe
        plus. Ce qui s'affiche encore -- la liste des cadences vues et leurs
        comptes -- est calcule au rendu, donc a jour par construction.
        """
        if self._rejouer is None or self.resultat is None:
            return True
        self.resultat = self._rejouer(self.resultat.session)
        return True


def _compteur_refuse(valeur: Fraction) -> int:
    """Le compteur d'une liste **fermee** : elle n'accueille aucune cadence.

    Il leve plutot que de rendre un cardinal : un compte invente au temps 2
    n'aurait ete mesure par personne, et le refus nomme le chemin qui n'existe
    pas au lieu de le laisser produire un chiffre faux.
    """
    raise cadences.CadencesMalFormees(
        f"Le temps 2 ne compte aucune cadence : {valeur} n'a pas ete regardée.")


__all__ = [
    "BUT_AJOUTER",
    "BUT_RELINK",
    "CONSEIL_SESSION_GRAPHIQUE",
    "EcranCadences",
    "EcranChoixDesCadences",
    "EcranPreviz",
    "EcranRefusRelink",
    "EcranRushes",
    "FILET_BORNES",
    "OBJET_TEMPS_1",
    "OBJET_TEMPS_2",
    "FILET_LOTS",
    "FILET_RAPPORT",
    "LotAProduire",
    "MOTIF_CIBLE_NON_FICHIER",
    "PHRASE_AUCUNE_LECTURE",
    "PHRASE_CADENCE_NON_CORROBOREE",
    "RACCOURCIS_CADENCES",
    "RACCOURCIS_CADENCES_SANS_ECRAN",
    "RACCOURCIS_CHOIX",
    "RACCOURCIS_PREVIZ",
    "RACCOURCIS_PREVIZ_REFUSEE",
    "RACCOURCIS_REFUS_RELINK",
    "RACCOURCIS_RUSHES",
    "RACCOURCIS_SAISIE_DE_CADENCE",
    "Composition",
    "ObjetTravaille",
    "SourceSondee",
    "TITRE_CADENCES",
    "TITRE_CHOIX",
    "TITRE_RUSHES",
    "TITRE_PREVIZ",
    "TITRE_PREVIZ_REFUSEE",
    "ZONE_EXPLORATEUR",
    "ZONE_LISTE",
    "compteur_de_frames",
    "filet_titre",
    "ligne_de_titre",
    "phrase_de_relink_reussi",
    "rapport_de_la_cadence",
    "texte_de_cadence_exacte",
]
