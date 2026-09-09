# -*- coding: utf-8 -*-
"""L'atelier Scan, temps 1 : le menu et le depot (story 11.5, lot B).

Deux ecrans, et ils repondent a deux questions differentes : `E3-0` demande
**quoi faire** dans cet atelier, `E3-1` demande **quoi lire**. Le reste du
temps 1 -- la detection en cours, le rapport, la completion de QR -- vit dans
les modules des lots voisins : aucun ecran d'ici ne les connait, et c'est ce
qui permet a trois agents de travailler la meme story sans se marcher dessus.

**Ce module n'ecrit aucune frame, et il n'ecrit rien du tout.** Le temps 1
produit un document de detection (`EPIC11-ARB-6`) ; le depot, lui, ne fait que
mesurer ce qu'on lui designe -- `scan_ingest.mesurer_la_source` ne copie rien,
ne cree aucun dossier de lot et n'exige aucun dpi.

Trois regles du produit s'y croisent, et chacune a deja ete payee ailleurs :

* **un seul champ de source** (`EPIC11-ARB-26`) -- dossier, fichier et PDF y
  passent ensemble, sans selecteur de mode. C'est l'explorateur livre par la
  story 11.2b qui le sert, avec `montrer_fichiers=True` : ecrire un second
  explorateur ici serait « la faute que la story existe pour eviter »
  (`explorateur.py`) ;
* **le vocabulaire suit la forme retenue** -- des pages pour un PDF, des
  fichiers pour un dossier. Ce n'est pas cosmetique : confondre les deux est ce
  qui ferait declarer un lot incomplet a tort. La forme est **rendue par le
  coeur** (`scan_ingest.mesurer_la_source`) et jamais redecidee ici, parce que
  « c'est l'ingestion qui distingue les quatre formes, et elle seule »
  (`EPIC7-ARB-88`) ;
* **le dpi est offert, jamais pose** (`EPIC11-ARB-38`, `EPIC7-ARB-44`) -- le
  champ reste requis et **vide**, la mesure s'affiche a cote, et un geste la
  reprend. Ce geste est `Tab` puis `⏎` sur une ligne du formulaire, jamais une
  lettre : « aucune lettre n'est un raccourci dans un champ de saisie »
  (`EPIC11-ARB-68`), tranche par Egan le 2026-08-31 (`EPIC11-ARB-101`, note 7).

**Ce module appelle `io/` et le coeur, jamais `cli.py`** -- la frontiere AST du
paquet le mesure deja, et l'AC 8.1 le verifie nommement sur les modules neufs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import scan_ingest
from . import aide_de_champ, jetons
from .coque import EcranPasEncore, Palier
from .ecran_projet import CoutureExplorateur, raccourcis_de_l_explorateur
from .explorateur import FAMILLE_MATIERE, Explorateur, taille_lisible
from .palier_projet import nom_du_profil, profil_par_defaut

# ===========================================================================
# Geometrie commune aux deux ecrans, DERIVEE des maquettes `E3-0` et `E3-1`.
# ===========================================================================

#: Colonne ou commence le nom d'une entree de menu, et le libelle d'un champ.
#: Trois blancs plus le glyphe de curseur et son blanc : la colonne est la meme
#: qu'une entree porte le curseur ou non, sans quoi les noms danseraient d'une
#: colonne a chaque `↑`.
INDENT_DU_CURSEUR = "   "

#: Colonne du texte courant (titre, filet, resume) : deux blancs. C'est celle
#: des maquettes, et elle est plus a gauche que les entrees a dessein -- un
#: titre qui s'alignerait sur ses entrees ne se distinguerait plus d'elles.
INDENT_DU_TEXTE = "  "

#: Largeur de la colonne des noms d'entree du menu (`E3-0`). Le nom le plus
#: long tient dedans, et la phrase de droite commence donc toujours au meme
#: endroit -- c'est ce qui rend les deux entrees lisibles en colonne.
LARGEUR_DU_NOM = 27

#: Largeur de la colonne des libelles du formulaire (`E3-1`). Le glyphe de
#: focus `>` se pose juste apres, et la valeur un blanc plus loin.
LARGEUR_DU_LIBELLE = 19

#: Ce qui reste a droite d'une mention de champ (« requis », « requis · dpi »).
#: Les mentions sont calees a droite : c'est la colonne que l'oeil balaye pour
#: savoir ce qui manque encore.
MARGE_DES_MENTIONS = 5


def _cale_a_droite(gauche: str, droite: str, utile: int) -> str:
    """`gauche` a sa place, `droite` calee au bord, un creux d'au moins deux.

    Meme regle de creux que `panneau.LigneChiffree.rendu`, et pour le meme
    motif : coller les deux colonnes rendrait la ligne illisible en plus d'etre
    trop longue. La mesure est en **colonnes** et non en `len()` -- un nom de
    fichier en ideogrammes rendrait une ligne calee juste a 92 colonnes reelles
    pour 72 comptees.
    """
    if not droite:
        return gauche
    place = max(utile - MARGE_DES_MENTIONS, 0)
    creux = place - jetons.colonnes(gauche) - jetons.colonnes(droite)
    return gauche + " " * max(jetons.CREUX_MINIMAL, creux) + droite


def filet(utile: int, titre: str = "", ascii_seul: bool = False) -> str:
    """Le filet horizontal, avec son titre optionnel a gauche.

    `── Ce qui sera lu ────────` sur `E3-1`, un filet nu sur `E3-0`. Il n'est
    pas un cadre : c'est une **separation**, et la table des glyphes de
    `DESIGN.md` section 6 ne porte pas de trait horizontal -- il vit dans
    `jetons.REPLIS_DE_TEXTE`, comme les symboles de texte de l'explorateur.
    """
    trait = "-" if ascii_seul else "─"
    largeur = max(utile - 2 * len(INDENT_DU_TEXTE), 0)
    if not titre:
        return INDENT_DU_TEXTE + trait * largeur
    tete = f"{trait * 2} {titre} "
    return INDENT_DU_TEXTE + tete + trait * max(largeur - jetons.colonnes(tete), 0)


# ===========================================================================
# `E3-0` -- le menu de l'atelier (AC 2)
# ===========================================================================

#: La ligne de raccourcis du menu, verbatim de la maquette `E3-0`. Constante de
#: module, comme celles du menu des ateliers : c'est ce qui la fait balayer par
#: la garde d'epic de `test_repli_ascii.py` et par celle des majuscules.
RACCOURCIS_SCAN_MENU = ("⏎ entrer  ↑↓ naviguer  Échap ateliers  "
                        "F1 aide  Q quitter")

#: Le titre du menu.
TITRE_DU_MENU = "Atelier Scan"

#: Le libelle du pied (AC 2.2) et ce qu'il dit quand rien n'est designe.
#: **Jamais une ligne vide** : un pied absent et un pied qui dit « aucun » ne
#: portent pas la meme information, et le premier se lit comme un defaut
#: d'affichage.
LIBELLE_DU_PROFIL = "Profil par défaut du projet"
PIED_SANS_PROFIL = "aucun profil désigné"

@dataclass(frozen=True)
class EntreeDeMenu:
    """Une entree du menu de l'atelier : ce qu'elle est, et ou elle mene.

    ``construite`` distingue une entree **livree** d'une entree qui mene a
    `EcranPasEncore`. Elle reste visible et nommee dans les deux cas -- « un
    operateur doit pouvoir voir ce qui existe avant de savoir qu'il n'y a pas
    acces » --, et une touche qui ne ferait rien et ne dirait rien serait
    indistinguable d'un clavier casse.

    ``quand`` est l'**echeance de cette entree-la**, et elle a remplace la
    constante de module `QUAND_LA_CALIBRATION` au lot H de la story 11.6.
    Motif : l'echeance qu'elle nommait -- « l'ecriture du Scan » -- est
    **echue**, `E3-9` etant livre et cable ; « une constante d'echeance qui
    survit a l'echeance est une promesse qui ment ». Le mecanisme, lui, reste :
    « Recalibrer un lot ecrit » reviendra au menu le jour ou une story de coeur
    livrera la commande (`EPIC11-ARB-101`, note 2), et elle portera **sa**
    date, pas celle d'une autre entree.

    L'invariant qui va avec : une entree non construite **doit** dire quand elle
    arrive. « Sans la date, on ne distingue pas "pas encore fait" de
    "abandonne" » (`EcranPasEncore`), et une echeance vide se rendrait par une
    ligne absente -- exactement l'ambiguite que cet ecran existe pour fermer.
    """

    cle: str
    nom: str
    phrase: str
    construite: bool = True
    quand: str = ""

    def __post_init__(self) -> None:
        if not self.construite and not self.quand:
            raise ValueError(
                f"l'entree {self.cle!r} n'est pas construite et ne dit pas "
                "quand elle arrive : « sans la date, on ne distingue pas "
                "\u00ab pas encore fait \u00bb de \u00ab abandonne \u00bb »")


#: **DEUX entrees, et pas trois** (`EPIC11-ARB-101`, note 2, tranche par Egan le
#: 2026-08-31). « Recalibrer un lot ecrit » a ete retiree : mesure faite,
#: `apply-calibration` est un talon du POC, et rien dans le depot n'applique un
#: profil a des frames **deja ecrites**. L'entree promettait donc une capacite
#: que le coeur n'a jamais eue -- ce n'etait pas « son ecran arrive avec le
#: temps 2 », il n'y a aucune commande derriere. Elle reviendra le jour ou une
#: story de coeur livrera la commande.
#:
#: L'ordre est celui de la chaine de travail, et il n'est pas negociable : on
#: detecte avant de calibrer, et le curseur part donc sur le parcours principal.
#: La cle de l'entree du parcours principal. En constante parce que **deux
#: modules la comparent** -- le menu ici, le cablage dans
#: `atelier_scan_parcours.entrer` --, exactement comme
#: `atelier_scan_calibration.CLE_DE_LA_CALIBRATION` pour l'autre entree. Une
#: chaine ecrite deux fois divergerait au premier renommage, et l'entree
#: cesserait de mener quelque part **en silence**.
CLE_DE_LA_DETECTION = "detecter"

ENTREES_DU_MENU: tuple[EntreeDeMenu, ...] = (
    EntreeDeMenu(
        CLE_DE_LA_DETECTION, "Détecter des planches",
        "Déposer des scans, lire les QR, puis écrire les TIFF. "
        "Le parcours principal."),
    EntreeDeMenu(
        "calibrer", "Calibrer une chaîne",
        "Depuis le scan d'une page de calibration, produire le profil "
        "couleur du scanner."),
)


def pied_du_menu(dossier) -> str:
    """Le profil de calibration par defaut du projet, ou son absence.

    Lu par `io.profile_designation.default_profile_entry` a travers
    `palier_projet.profil_par_defaut`, qui est le point de lecture deja livre.
    Le nom affiche passe par `palier_projet.nom_du_profil` : deux redactions de
    « sous quel nom un profil s'affiche » divergeraient, et l'ecart ne se
    verrait que sur un projet dont le profil a perdu sa provenance.
    """
    if dossier is None:
        return PIED_SANS_PROFIL
    entree, _chemin = profil_par_defaut(dossier)
    if not entree:
        return PIED_SANS_PROFIL
    return f"{LIBELLE_DU_PROFIL}   {nom_du_profil(entree)}"


class EcranScanMenu(Palier):
    """`E3-0` -- deux entrees, et le pied du profil par defaut.

    `entrer` est **injecte**, comme `ouvrir` l'est au palier 0 et `entrer` au
    menu des ateliers : cet ecran ne sait pas ce que « deposer des scans » veut
    dire, et c'est l'application qui le lui dit. Sans cette couture, le menu
    dependrait des modules des lots voisins, et les trois lots ne pourraient
    plus etre developpes en parallele.
    """

    titre = "Scan"
    raccourcis = RACCOURCIS_SCAN_MENU

    def __init__(self, dossier=None,
                 entrer: Callable[[EntreeDeMenu], None] | None = None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._entrer = entrer
        self.curseur = 0
        self.entrees: tuple[EntreeDeMenu, ...] = ENTREES_DU_MENU

    # -- lecture ------------------------------------------------------------

    def lignes_d_entree(self, rang: int, utile: int) -> list[str]:
        """Une entree : son nom en colonne, puis sa phrase repliee a droite.

        **La phrase est repliee, jamais abregee** : elle dit ce que l'entree
        fait, et une phrase coupee par la fin perdrait precisement la moitie
        qui distingue les deux entrees. C'est le motif de `jetons.envelopper`.
        """
        table = self.app.glyphes
        entree = self.entrees[rang]
        marque = table["curseur"] if rang == self.curseur else " "
        tete = (f"{INDENT_DU_CURSEUR}{marque} "
                + jetons.caler_a_gauche(entree.nom, LARGEUR_DU_NOM,
                                        self.app.ascii_seul))
        colonne = len(INDENT_DU_CURSEUR) + 2 + LARGEUR_DU_NOM
        morceaux = jetons.envelopper(entree.phrase, max(utile - colonne, 1),
                                     self.app.ascii_seul)
        lignes = [tete + (morceaux[0] if morceaux else "")]
        lignes += [" " * colonne + suite for suite in morceaux[1:]]
        return lignes

    def lignes(self) -> list[str]:
        utile = jetons.largeur_utile(self.app.size.width)
        corps = [INDENT_DU_TEXTE + TITRE_DU_MENU, ""]
        for rang in range(len(self.entrees)):
            if rang:
                # Une ligne vide **entre** les entrees, jamais apres la
                # derniere : la posee avant l'entree plutot qu'apres la
                # precedente, pour qu'une troisieme entree un jour ne laisse
                # pas la separation au mauvais endroit.
                corps.append("")
            corps += self.lignes_d_entree(rang, utile)
        corps += ["", filet(utile, ascii_seul=self.app.ascii_seul), ""]
        corps.append(INDENT_DU_CURSEUR + "  " + pied_du_menu(self.dossier))
        return corps

    def rangs_du_curseur(self) -> list[int]:
        """Les rangs de **toute** l'entree courante, pas seulement sa premiere.

        `EPIC11-ARB-101`, note 1 d'Egan : « Detecter les planches et la premiere
        ligne de description sont en bleu. Pas la seconde ligne de description.
        [...] il faut revoir la logique de colorisation pour qu'elle considere
        les lignes en entier. » Une ligne de continuation ne porte, par
        construction, aucun glyphe : aucune reconnaissance par motif ne peut la
        trouver, il faut la **donner**. C'est ce que `jetons.peindre` attend
        dans `lignes_du_curseur`.
        """
        utile = jetons.largeur_utile(self.app.size.width)
        rang_rendu = 2                        # le titre et sa ligne vide
        for rang in range(len(self.entrees)):
            if rang:
                rang_rendu += 1
            hauteur = len(self.lignes_d_entree(rang, utile))
            if rang == self.curseur:
                return list(range(rang_rendu, rang_rendu + hauteur))
            rang_rendu += hauteur
        return []

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-scan-menu")
        return [Vertical(self._corps, id="centre-scan-menu")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            lignes_du_curseur=self.rangs_du_curseur()))
        self.poser_etat("")
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        if touche in ("up", "down"):
            pas = -1 if touche == "up" else 1
            self.curseur = min(max(self.curseur + pas, 0),
                               len(self.entrees) - 1)
            return True
        if touche == "enter":
            self.entrer(self.entrees[self.curseur])
            return True
        return False

    def entrer(self, entree: EntreeDeMenu) -> None:
        """`⏎` sur une entree. **Aucune des deux branches n'est muette.**

        Une entree non construite nomme ce qui manque et quand il arrive. Et une
        entree construite dont le rappel n'est pas cable fait de meme, plutot que
        de consommer la touche sur rien : « une touche qui ne fait rien et ne dit
        rien est indistinguable d'un clavier casse », et le silence de cette
        seconde branche a ete trouve par la garde des rappels cables -- pas par
        la relecture.
        """
        if not entree.construite:
            # L'echeance est celle de **l'entree**, jamais une constante de
            # module partagee : voir :class:`EntreeDeMenu`. Au 2026-09-01 les
            # deux entrees du menu sont construites, et cette branche ne se
            # mesure donc plus que sur une entree fabriquee -- ce que le banc
            # fait, plutot que de laisser le mecanisme sortir de la mesure avec
            # la derniere entree qui l'employait.
            self.app.descendre(EcranPasEncore(entree.nom, entree.quand))
            return
        if self._entrer is None:
            self.app.descendre(EcranPasEncore(entree.nom, QUAND_LA_DETECTION))
            return
        self._entrer(entree)


# ===========================================================================
# `E3-1` / `E3-1b` -- le depot (AC 3 et AC 4)
# ===========================================================================

#: Ce que le bandeau porte a droite pendant tout le depot. Le temps 1 et le
#: temps 2 sont deux commandes de coeur distinctes (`EPIC11-ARB-6`) ; l'ecran
#: dit **ou l'on en est**, pas pourquoi la coupure existe.
OBJET_DU_DEPOT = "temps 1 sur 2 · détecter"

#: La queue commune des pieds du depot -- tout ce qui ne depend pas de la ligne
#: ou est le curseur. Elle est ecrite **une fois** : huit redactions du meme
#: `Échap ateliers` divergeraient au premier renommage.
_QUEUE_DEPOT = "Tab champ  Échap ateliers  F1 aide  Q quitter"
#: Et sa variante quand la liste des sources DEBORDE. `↑↓` ne fait quelque chose
#: que dans ce regime-la, et l'annoncer ailleurs promettrait une touche inerte,
#: ce qui est indistinguable d'un clavier casse.
_QUEUE_DEPOT_MULTIPLE = f"↑↓ sources  {_QUEUE_DEPOT}"

#: **Le pied dit desormais le geste de la LIGNE COURANTE**, patron d'`E3-9`
#: (`EPIC11-ARB-158`), importe ici par le retour terrain du 2026-09-06 : « sur
#: l'ecran de parametrage [scan] une fois le chemin specifie il manque un bouton
#: valider. Le seul moyen de valider est de faire Enter sur le DPI, pas
#: intuitif. »
#:
#: Ces deux lignes-ci sont le pied **par defaut** -- celui du champ de dpi, ou
#: `⏎` ne fait que descendre. Elles n'annoncent donc plus `⏎`, et c'est le
#: correctif de fond : elles disaient « ⏎ détecter » depuis n'importe quelle
#: ligne, y compris depuis `Source` ou `⏎` ouvre l'explorateur.
#:
#: MESURE (2026-09-06) : 45 et 57 colonnes en UTF-8, autant en repli ASCII,
#: pour une zone de 76.
RACCOURCIS_DEPOT = _QUEUE_DEPOT
RACCOURCIS_DEPOT_MULTIPLE = _QUEUE_DEPOT_MULTIPLE

#: Le pied de la ligne `Source` **tant qu'aucune source n'est designee**. Il
#: garde sa redaction d'origine, `Q quitter` compris -- c'est-a-dire absent :
#: c'est l'etat d'ouverture de l'ecran, et la sortie y est `Échap ateliers`.
RACCOURCIS_DEPOT_SANS_SOURCE = ("⏎ désigner la source  Tab champ  "
                                "Échap ateliers  F1 aide")

#: Les pieds des trois lignes qui ont un geste propre, dans les deux regimes de
#: la liste des sources.
#:
#: **`Q quitter` cede la place quand la ligne porte a la fois un geste long et
#: `↑↓ sources`**, et ce n'est pas un choix de style : mesure faite, les deux
#: lignes concernees passent a 79 et 80 colonnes en UTF-8 (84 et 85 en repli
#: ASCII) pour une zone de 76. Le raccourci sacrifie est celui qui a un double
#: -- `Échap ateliers` reste annonce --, et le precedent existe deja sur cet
#: ecran avec :data:`RACCOURCIS_DEPOT_SANS_SOURCE`.
#:
#: MESURE (2026-09-06), en colonnes UTF-8 / ASCII pour une zone de 76 :
#: 67/72, 68/73, 68/73, 69/74, 57/62, 69/74.
RACCOURCIS_SUR_LA_SOURCE = f"⏎ désigner la source  {_QUEUE_DEPOT}"
RACCOURCIS_SUR_LA_SOURCE_MULTIPLE = ("⏎ désigner la source  ↑↓ sources  "
                                     "Tab champ  Échap ateliers  F1 aide")
RACCOURCIS_SUR_LA_REPRISE = f"⏎ reprendre la mesure  {_QUEUE_DEPOT}"
RACCOURCIS_SUR_LA_REPRISE_MULTIPLE = ("⏎ reprendre la mesure  ↑↓ sources  "
                                      "Tab champ  Échap ateliers  F1 aide")
RACCOURCIS_SUR_VALIDER = f"⏎ détecter  {_QUEUE_DEPOT}"
RACCOURCIS_SUR_VALIDER_MULTIPLE = f"⏎ détecter  {_QUEUE_DEPOT_MULTIPLE}"

#: Le titre du depot, et le titre du filet qui separe la saisie de la mesure.
TITRE_DU_DEPOT = "Que faut-il détecter ?"
TITRE_DU_RESUME = "Ce qui sera lu"

#: Les libelles des trois lignes du formulaire. Celle de la reprise n'existe que
#: quand une mesure existe (AC 4.4) : proposer de reprendre ce qui n'a pas ete
#: mesure serait une ligne qui ment.
LIBELLE_SOURCE = "Source"
LIBELLE_DPI = "Résolution de scan"
LIBELLE_REPRISE = "Reprendre la mesure"
#: Le libelle de la ligne d'action. Il se dessine **comme le bouton d'`E5-2`** :
#: rien dans la colonne des libelles, le mot a la colonne des valeurs, le glyphe
#: `>` au focus (`DESIGN.md` section 7.3) -- et **sans seconde colonne**.
#:
#: C'est un ecart assume avec `E3-9`, qui porte `ACTION_VALIDER = "lancer la
#: calibration"` a cote de son `Valider`. Le motif : Egan a fait **retirer**
#: cette seconde colonne d'`E5-2` le 2026-09-02 (verbatim : « enlever la
#: deuxieme colonne "compose les planches..." a cote de valider »), et c'est le
#: plus recent des deux gestes. On ne suit pas deux formes a la fois, et on
#: n'en invente pas une troisieme.
LIBELLE_VALIDER = "Valider"

#: Ce que le champ de source ET la tete du resume disent quand la designation
#: en porte plusieurs. **Verbatim d'Egan**, note 5 du 2026-08-31
#: (`EPIC11-ARB-101`) : « si fichiers multiples on dit *sources multiples*, en
#: dessous la liste navigable ». Une seule redaction pour les deux endroits :
#: deux formulations diraient deux choses du meme fait, a deux lignes d'ecart.
LIBELLE_SOURCES_MULTIPLES = "sources multiples"

#: La hauteur de la liste navigable des sources, `…` compris. **Derivee de la
#: place qui reste** : le formulaire multiple occupe onze lignes des dix-sept du
#: plancher (titre, trois champs et leurs blancs, filet, resume, blanc), et cinq
#: est ce qui tient sans jamais deborder -- y compris quand la ligne de reprise
#: de la mesure existe.
HAUTEUR_DES_SOURCES = 5

#: Ce que le resume dit tant que rien n'est designe. **Ligne de corps, pas ligne
#: d'etat** : `EPIC11-ARB-56` ne vise que la seconde.
LIBELLE_RIEN_ENCORE = "rien encore — désignez une source"

#: Les mentions calees a droite des champs requis.
MENTION_REQUIS = "requis"
MENTION_REQUIS_DPI = "requis · dpi"

#: Ce que la ligne d'etat dit quand la source est la et le dpi non. **Une
#: mesure de l'ecran courant**, sans touche, sans conseil et sans motif de
#: conception (`EPIC11-ARB-56`).
PHRASE_DPI_REQUIS = "résolution de scan requise — la détection ne peut pas partir"
#: Et les deux autres motifs pour lesquels la detection ne peut pas partir.
#: `peut_detecter` est faux pour **trois** raisons, et la ligne d'etat n'en
#: nommait qu'une : sur un `E3-1` vierge elle disait « résolution de scan
#: requise » alors que la resolution n'etait meme pas en cause. C'est le defaut
#: qu'`E3-9` a paye deux fois -- « une mention qui nomme le mauvais manque
#: envoie l'operateur corriger un champ qui va bien ».
PHRASE_SOURCE_REQUISE = "source requise — la détection ne peut pas partir"
PHRASE_DPI_REFUSE = ("résolution de scan hors bornes — la détection ne peut "
                     "pas partir")

#: Les mentions calees a droite de la ligne `Valider`, une par motif de refus.
#: **Sans glyphe** : la colonne de mention de ce formulaire est en texte nu
#: partout (`requis`, `requis · dpi`), et c'est la grammaire qu'on suit.
MENTION_VALIDER_SANS_SOURCE = "source requise"
MENTION_VALIDER_SANS_DPI = "résolution requise"
#: Le troisieme regime : une resolution SAISIE que le coeur refuse. « requise »
#: y serait faux -- elle est la, elle ne convient pas.
MENTION_VALIDER_DPI_REFUSE = "résolution hors bornes"

#: L'unite du dpi, ecrite une fois. Elle suit la valeur reprise (« 600 dpi »)
#: comme la mention du champ, et deux redactions divergeraient.
UNITE_DPI = "dpi"

#: Les deux zones du depot : le formulaire, et l'explorateur monte par-dessus le
#: champ de source.
ZONE_FORMULAIRE = "formulaire"
ZONE_EXPLORATEUR = "explorateur"

#: Ce que l'ecran nomme quand aucun rappel de detection n'est cable, et quand
#: il le sera. Il ne dit pas « echec » : rien n'a echoue, l'execution n'est
#: simplement pas branchee sur cet assemblage.
CE_QUI_MANQUE_POUR_DETECTER = "Lancer la détection"
QUAND_LA_DETECTION = "l'exécution du Scan"

#: Les cles des champs du formulaire, dans l'ordre ou `Tab` les parcourt.
CHAMP_SOURCE = "source"
CHAMP_DPI = "dpi"
CHAMP_REPRISE = "reprise"
#: **La ligne d'action, en bas du formulaire.** Retour terrain d'Egan du
#: 2026-09-06, verbatim : « sur l'ecran de parametrage [scan] une fois le chemin
#: specifie il manque un bouton valider. Le seul moyen de valider est de faire
#: Enter sur le DPI, pas intuitif. »
#:
#: C'est le **meme grief** qu'`EPIC11-ARB-158` a tranche le 2026-09-01 sur
#: `E3-9`, l'ecran voisin du meme atelier : « la validation avec Entree n'est
#: pas claire. Il faut qu'il y ait un choix explicite en bas du formulaire :
#: Valider. » La forme est donc **declinee de `E3-9`**, elle n'est pas inventee.
#:
#: **Une ligne du formulaire, pas une issue** : elle se parcourt avec les
#: autres, et c'est ce qui la rend atteignable. En faire une liste d'issues
#: separee la mettrait derriere un second geste, ce que le grief vise
#: precisement.
#:
#: **Elle s'atteint par `Tab`, et non par les fleches -- ecart assume avec
#: `EPIC11-ARB-158`.** L'arbitrage dit « on y accede en descendant avec les
#: fleches » ; il a ete pris sur `E3-9`, qui n'a **pas** de liste de sources.
#: Ici `↑↓` fait defiler cette liste (voir :meth:`FormulaireDuDepot
#: .defiler_les_sources`) et `Tab` est deja la navigation de formulaire de cet
#: ecran-la. Rendre les fleches au formulaire retirerait a l'operateur le seul
#: moyen de lire une designation de trente planches. Le pied l'annonce
#: (`Tab champ`) : une ligne d'action inatteignable par la touche annoncee
#: serait pire que pas de ligne du tout.
CHAMP_VALIDER = "valider"

#: **`F1` sur un champ : ce que ce champ attend** (`EPIC11-ARB-14`, story 11.9
#: lot B). Le mecanisme est celui du paquet (`aide_de_champ`) ; cette table est
#: **la donnee de cet ecran**, et elle reste ici -- `EPIC11-ARB-198` generalise
#: le mecanisme, pas les phrases.
#:
#: Chaque phrase dit trois choses, dans cet ordre : ce que le champ attend, les
#: **formes acceptees**, et une **valeur du contexte courant** -- la marque
#: `{valeur}`, remplie par :meth:`EcranScanDepot.valeur_de_l_aide`. « Une aide
#: qui paraphrase le libelle est un defaut » : aucune de ces phrases ne redit
#: `Source`, `Résolution de scan` ni `Reprendre la mesure`.
#:
#: **Le plafond du dpi est LU du coeur** (`scan_ingest.MAX_SCAN_DPI`) et jamais
#: recopie : `validate_scan_dpi` est la seule autorite du depot sur ce qu'est un
#: dpi acceptable, et une aide qui annoncerait une autre borne enverrait
#: l'operateur saisir une valeur que l'ingestion refuse dix secondes plus tard.
#: C'est la lecon d'`CANONICAL_ID_MAX_LENGTH`, recopiee fausse trois fois.
AIDE_PAR_CHAMP = {
    CHAMP_SOURCE: "Un dossier, un PDF ou plusieurs pages ; ici : {valeur}.",
    CHAMP_DPI: (f"Un entier jusqu'à {scan_ingest.MAX_SCAN_DPI}, celui du "
                "scanner ; ici : {valeur}."),
    CHAMP_REPRISE: ("Relit la résolution écrite dans la source ; "
                    "ici : {valeur}."),
    # **La ligne d'ACTION dit ce que `⏎` FAIT**, et ici `⏎` part vraiment : il
    # n'y a pas de recapitulatif entre cette ligne et le coeur, contrairement a
    # `E3-9`. La phrase le dit donc sans adoucir -- « lance » et non
    # « récapitule » --, et elle nomme le **temps 1**, qui est le mot que ni le
    # libelle ni le pied ne portent (`EPIC11-ARB-14` interdit de paraphraser le
    # libelle).
    CHAMP_VALIDER: ("Lance le temps 1 sur ce qui est désigné ; "
                    "ici : {valeur}."),
}

#: Ce que la valeur de contexte dit d'une source non designee, et d'une source
#: qui n'a livre aucune mesure. Deux constats, pas deux conseils.
AIDE_SANS_SOURCE = "rien de désigné"
AIDE_SANS_MESURE = "aucune mesure lue"
#: Et d'un dpi saisi que le coeur refuse. La ligne du champ le montre tel quel ;
#: l'aide dit ce que le coeur en fait, ce que la ligne ne dit pas.
AIDE_DPI_REFUSE = "{saisi} — hors bornes"
#: Ce que la ligne d'action cite quand la detection peut partir. Le cas
#: contraire est **lu de :func:`motif_du_refus_de_partir`**, deja seule
#: redaction du motif pour la mention et pour la ligne d'etat : une troisieme
#: divergerait.
AIDE_PRET_A_PARTIR = "prêt à partir"


def motif_du_refus_de_partir(formulaire: "FormulaireDuDepot"
                             ) -> tuple[str, str]:
    """Ce qui manque en premier, **pour la mention ET pour la ligne d'etat**.

    Une seule redaction pour les deux surfaces : sur `E3-9`, les avoir ecrites
    deux fois a fait corriger la premiere sans la seconde, deux fois de suite.
    L'ordre est celui du formulaire -- la source se designe avant sa resolution
    --, donc le motif rendu est celui du **premier** manque rencontre.

    Les trois regimes sont distincts, et le troisieme est celui qu'on oublie :
    un dpi PRESENT mais refuse par le coeur (`abc`, `0`, `999999`). Dire
    « résolution requise » avec `999999` ecrit dans le champ, c'est renvoyer
    l'operateur remplir une case deja pleine.
    """
    if formulaire.source is None:
        return MENTION_VALIDER_SANS_SOURCE, PHRASE_SOURCE_REQUISE
    if not formulaire.saisie(CHAMP_DPI):
        return MENTION_VALIDER_SANS_DPI, PHRASE_DPI_REQUIS
    return MENTION_VALIDER_DPI_REFUSE, PHRASE_DPI_REFUSE


#: Quelle ligne de pied pour quelle ligne du formulaire, **et dans les deux
#: regimes de la liste des sources** -- le couple est
#: `(liste qui tient, liste qui deborde)`.
#:
#: Le champ absent de la table -- le dpi -- prend le pied par defaut, qui
#: n'annonce pas `⏎` : il y **descend**, et annoncer une touche pour dire
#: qu'elle fait la meme chose que `Tab` serait du bruit. C'est le patron
#: d'`E3-9` (`PIED_PAR_CHAMP`), avec la dimension de plus que cet ecran-la n'a
#: pas : `E3-9` n'a aucune liste a faire defiler.
#:
#: Une table plutot qu'une chaine de `if` : elle se lit d'un coup d'oeil, et
#: c'est elle que le banc confronte a l'ensemble des champs.
PIED_PAR_CHAMP = {
    CHAMP_SOURCE: (RACCOURCIS_SUR_LA_SOURCE, RACCOURCIS_SUR_LA_SOURCE_MULTIPLE),
    CHAMP_REPRISE: (RACCOURCIS_SUR_LA_REPRISE,
                    RACCOURCIS_SUR_LA_REPRISE_MULTIPLE),
    CHAMP_VALIDER: (RACCOURCIS_SUR_VALIDER, RACCOURCIS_SUR_VALIDER_MULTIPLE),
}


def source_acceptable(chemin: Path) -> bool:
    """Ce que l'explorateur retient comme source (AC 3.1).

    Les extensions sont **lues du coeur**, jamais recopiees : `scan_ingest`
    porte la table, et une seconde redaction divergerait au premier format
    ajoute -- l'ecran refuserait alors un fichier que l'ingestion sait lire, ce
    qui est la pire des deux divergences possibles.

    **Une SEULE table est lue, et ce n'etait pas le cas** : cette ligne
    additionnait `IMAGE_EXTENSIONS + PDF_EXTENSIONS`, ce qui etait une seconde
    redaction de l'union -- correcte le jour ou elle a ete ecrite, et muette le
    jour ou le coeur a cesse d'accepter les deux familles au meme endroit.
    Elle lit desormais `PAGE_EXTENSIONS`, l'union que le coeur redige lui-meme
    (`EPIC11-ARB-157`).

    Un dossier n'a pas a passer par ici : l'explorateur ne soumet au filtre que
    les fichiers, et un dossier est une forme d'entree a lui seul.
    """
    return chemin.suffix.lower() in scan_ingest.PAGE_EXTENSIONS


@dataclass(frozen=True)
class SourceDesignee:
    """Un chemin designe et ce que le coeur y a mesure, sans rien ingerer.

    ``chemin`` est ``None`` -- et seulement alors -- quand la designation porte
    **plusieurs** sources : la quatrieme forme d'`EPIC7-ARB-88` n'a pas un
    chemin, elle en a une sequence, et lui en inventer un (le parent commun,
    le premier de la liste) serait exactement la coercition que l'arbitrage
    interdit a l'appelant.

    ``sources`` porte alors, dans l'ordre de la designation, le couple
    ``(chemin, octets)`` de chaque source -- ``None`` en octets quand la mesure
    n'a pas pu se faire, jamais un `0` qui se lirait comme un fichier vide.
    """

    chemin: Path | None
    mesure: scan_ingest.SourceMesuree
    sources: tuple[tuple[Path, int | None], ...] = ()

    @property
    def forme(self) -> str:
        return self.mesure.forme

    @property
    def cardinal(self) -> int:
        return self.mesure.cardinal

    @property
    def fichiers(self) -> int:
        """Sur combien de FICHIERS les pages du cardinal sont reparties.

        Relaye du coeur comme les trois autres, et pour le meme motif : le
        vocabulaire de l'ecran (`unite_du_cardinal`) se decide en confrontant
        ce nombre au cardinal, et le recalculer ici en compterait les chemins
        designes plutot que les fichiers RETENUS -- les deux different des
        qu'un dossier porte un `Thumbs.db`.
        """
        return self.mesure.fichiers

    @property
    def dpi(self) -> float | None:
        return self.mesure.dpi

    @property
    def est_multiple(self) -> bool:
        """La designation porte-t-elle plusieurs sources ?

        **La forme est LUE du coeur, jamais redecidee ici** (`EPIC7-ARB-88`) :
        une designation d'un seul element est ramenee par l'ingestion au cas a
        un chemin (`_reconnaitre_la_source`), si bien qu'un test sur la
        longueur de la sequence rendrait vrai la ou le coeur dit « image
        seule ». Les deux ecrans divergeraient alors sur le meme lot.
        """
        return self.forme == scan_ingest.FORME_SELECTION

    @property
    def argument_de_detection(self) -> "Path | list[Path]":
        """Ce qui part au coeur, **tel quel**.

        `EPIC7-ARB-88`, verbatim : « aucune coercition ici : c'est l'ingestion
        qui distingue les quatre formes, **et elle seule** ». Une sequence part
        en sequence ; la reduire a son dossier commun ferait ingerer des
        fichiers que l'operateur n'a pas coches.
        """
        if self.est_multiple:
            return [chemin for chemin, _ in self.sources]
        return self.chemin


def poids_du_fichier(chemin: Path) -> int | None:
    """La taille d'une source, ou ``None`` quand elle ne se mesure pas.

    ``None`` et jamais `0` : `DESIGN.md` section 3 refuse la valeur devinee, et
    un `0` se lirait comme un fichier vide -- c'est-a-dire comme une mesure.
    """
    try:
        return chemin.stat().st_size
    except OSError:
        return None


def _chemins_designes(designation) -> tuple[Path, ...]:
    """La designation en chemins, **sans decider de sa forme**.

    Une chaine et un `Path` sont des chemins et non des sequences -- meme garde
    qu'`scan_ingest._normaliser_la_selection`, et pour la meme raison : `str`
    est iterable, et l'oublier ferait une selection de caracteres.
    """
    if isinstance(designation, (str, Path)):
        return (Path(designation),)
    return tuple(Path(chemin) for chemin in designation)


def designer(chemin, *, mesurer=None) -> SourceDesignee:
    """Mesurer la source designee. **Rien n'est ecrit, rien n'est copie.**

    `mesurer` est injecte pour les bancs ; son defaut est le point d'entree du
    coeur. Les refus qu'il leve (`scan_ingest.ScanIngestError`) traversent :
    l'ecran les rend **verbatim**, parce qu'un motif du coeur est deja une
    phrase pour l'operateur et que le resumer le detruirait (`EPIC11-ARB-30`).

    **La mesure passe AVANT toute coercition en `Path`, et ce n'est pas un
    detail de style** : la premiere redaction ecrivait
    `SourceDesignee(Path(chemin), mesurer(chemin))`, dont Python evalue
    l'argument de gauche d'abord. Une sequence de chemins y levait donc un
    `TypeError` nu **avant** que le coeur ait pu la reconnaitre -- exactement le
    piege deja paye a `scan_detect.py:250-260`, ou coercer `scan_path` en `Path`
    « detruisait la quatrieme forme et remplacait un motif lisible par un
    message Python ». Le coeur mesure, puis on lit la forme qu'il rend.
    """
    mesurer = mesurer or scan_ingest.mesurer_la_source
    mesure = mesurer(chemin)
    chemins = _chemins_designes(chemin)
    if mesure.forme == scan_ingest.FORME_SELECTION:
        return SourceDesignee(None, mesure,
                              tuple((c, poids_du_fichier(c)) for c in chemins))
    # Le cas a un seul element **n'est pas une selection** : l'ingestion l'a
    # ramene au chemin unique, et l'ecran suit ce qu'elle dit plutot que ce que
    # l'operateur a coche -- sans quoi cocher un dossier seul l'annoncerait
    # « sources multiples » pour un lot que le coeur traite en dossier.
    return SourceDesignee(chemins[0], mesure)


def unite_du_cardinal(source) -> str:
    """« page » quand le compte n'est PAS un compte de fichiers, sinon
    « fichier » (`EPIC11-ARB-26`, etendu par `EPIC11-ARB-157`).

    **Une seule redaction du vocabulaire**, employee par le resume ET par la
    mention de mesure du dpi. Deux redactions diraient « 8 pages » ici et
    « 8 fichiers » deux lignes plus bas, ce qui est exactement la confusion que
    l'arbitrage existe pour supprimer.

    **La regle ne se lit plus de la seule `forme`, et c'est ce qui a change.**
    `EPIC11-ARB-26` disait « page pour un PDF, fichier pour le reste », ce qui
    etait exact tant qu'un dossier ne portait que des images -- un fichier, une
    page. Depuis `EPIC11-ARB-157`, un dossier peut melanger trois PDF et deux
    TIFF : trois fichiers y font six pages, et l'ancienne regle aurait annonce
    « 6 fichiers » pour cinq fichiers. Ce n'est pas une nuance de style, c'est
    un compte faux presente comme une mesure.

    La regle a donc **deux** moities, et la seconde seule ne suffit pas :

    1. un PDF designe seul dit « page », inconditionnellement -- c'est
       `EPIC11-ARB-26` mot pour mot, et il vaut aussi pour un PDF d'**une**
       page, ou `cardinal` et `fichiers` valent tous deux `1`. Deduire le mot du
       seul ecart des deux nombres ferait dire « la fichier declare 300 dpi »
       la ou l'arbitrage demande « la page » ;
    2. sinon, le mot suit la question « ce nombre compte-t-il des fichiers ? »,
       qui se repond par `cardinal == fichiers`. C'est cette moitie-la qui est
       neuve, et elle ne sert qu'aux dossiers et selections melanges.

    Un dossier d'images continue donc de dire « fichier », a l'identique.
    """
    if source.forme == scan_ingest.FORME_PDF:
        return "page"
    return "fichier" if source.cardinal == source.fichiers else "page"


#: L'article defini de chaque unite, au singulier. Une table et non une regle :
#: « page » est feminin, « fichier » masculin, et deviner le genre d'un nom
#: francais n'est pas quelque chose qu'un `if` sait faire. Elle est courte parce
#: que le vocabulaire l'est -- `unite_du_cardinal` n'en rend que deux.
ARTICLE_SINGULIER = {"page": "la", "fichier": "le"}


def compte_dans_le_vocabulaire(source) -> str:
    """« 8 pages », « 24 fichiers », « 1 fichier ». Le pluriel suit le compte."""
    unite = unite_du_cardinal(source)
    cardinal = source.cardinal
    return f"{cardinal} {unite}{'s' if cardinal > 1 else ''}"


def resume_de_la_source(source: SourceDesignee) -> str:
    """Ce qui sera lu, **dans le vocabulaire de la forme retenue** (AC 3.4).

    `1 PDF · 8 pages · 1,2 Go` pour un PDF, `24 fichiers · 1,9 Go` pour un
    dossier. Le PDF porte sa nature en tete parce que son cardinal ne compte
    pas des fichiers : sans elle, « 8 pages » ne dirait pas d'ou viennent les
    pages, et c'est precisement ce que l'operateur verifie du coin de l'oeil.

    **Le resume compte, il n'enumere pas** (`EPIC11-ARB-101`, note 6 d'Egan :
    « Pas la peine de lister toutes les pages. Juste de les compter suffit non ?
    En ligne c'est illisible au dela d'un certain nombre en plus. »).
    """
    morceaux = []
    if source.forme == scan_ingest.FORME_PDF:
        morceaux.append("1 PDF")
    if source.est_multiple:
        # **La tete dit la NATURE de la designation, le reste ce qu'elle
        # pese** -- meme forme que le PDF juste au-dessus, et pour le meme
        # motif : sans elle, « 3 fichiers » ne dirait pas d'ou viennent les
        # fichiers, alors que c'est ce que l'operateur verifie du coin de
        # l'oeil avant de lancer une passe.
        morceaux.append(LIBELLE_SOURCES_MULTIPLES)
    morceaux.append(compte_dans_le_vocabulaire(source))
    morceaux.append(taille_lisible(source.mesure.octets))
    return " · ".join(morceaux)


def ligne_d_une_source(chemin: Path, octets: int | None, utile: int,
                       neutre: str = "·", ascii_seul: bool = False) -> str:
    """Une ligne de la liste navigable : le nom, et **son poids seul**.

    « A cote d'un fichier juste son poids » (Egan, note 5). Le compte de pages
    que la meme note demande a cote d'un PDF **n'a toujours pas de ligne ici,
    mais le motif a change et il faut le dire** : jusqu'au 2026-09-01 cette
    branche etait litteralement inatteignable -- `_normaliser_la_selection`
    refusait un PDF dans une selection, donc une source de cette liste etait
    forcement une image. `EPIC11-ARB-157` a leve ce refus : une selection peut
    desormais melanger des PDF et des images, et la moitie « nombre de pages »
    de la note 5 est **atteignable**.

    Elle n'est pas ecrite ici pour autant, et c'est un choix de perimetre
    plutot qu'une mesure : la rendre demande un compte de pages PAR FICHIER,
    que `SourceDesignee.sources` ne porte pas (il ne porte que
    `(chemin, octets)`). C'est au registre de `deferred-work.md`, avec son
    origine, plutot qu'enterre ici en silence.

    Le nom s'abrege **ici**, a la source, et jamais par le garde-fou de
    l'ecran : celui-la coupe par la fin, c'est-a-dire par ce qui distingue deux
    planches voisines (finding `E10` de l'explorateur).
    """
    droite = neutre if octets is None else taille_lisible(octets)
    place = max(utile - MARGE_DES_MENTIONS - len(INDENT_DU_CURSEUR)
                - jetons.colonnes(droite) - jetons.CREUX_MINIMAL, 1)
    nom = jetons.abreger_nom(chemin.name, place, ascii_seul)
    return _cale_a_droite(INDENT_DU_CURSEUR + nom, droite, utile)


def mention_de_la_mesure(source: SourceDesignee | None) -> str:
    """« les 8 pages déclarent 600 dpi », ou **rien** (AC 4.2 et AC 4.4).

    Rien, et jamais `0`, jamais `--`, jamais une valeur devinee : c'est la meme
    regle que le temps restant (`DESIGN.md` section 3), et
    `scan_ingest.mesurer_le_dpi` rend `None` quand aucune page ne declare de
    resolution. Une valeur inventee ici serait le risque R8 sous sa forme la
    plus vicieuse -- une valeur *qui a l'air juste*.
    """
    if source is None or source.dpi is None:
        return ""
    mesure = f"{dpi_lisible(source.dpi)} {UNITE_DPI}"
    unite = unite_du_cardinal(source)
    if source.cardinal == 1:
        # « la page declare », « le fichier declare » -- **pas** « les 1
        # fichier », qui est ce qu'un pluriel pose sans condition rendait. Le
        # cas a un element est le seul ou la faute se voie, et c'est pour cela
        # qu'une fabrique le porte.
        return f"{ARTICLE_SINGULIER[unite]} {unite} déclare {mesure}"
    compte = compte_dans_le_vocabulaire(source)
    return f"les {compte} déclarent {mesure}"


def dpi_lisible(mesure: float) -> str:
    """Un dpi mesure, sans decimale inutile.

    Un PNG stocke sa resolution en pixels par metre : 72 dpi en ressort a
    72,009. Afficher la decimale ferait lire une precision que la mesure n'a
    pas, et la reprendre telle quelle poserait un dpi que
    `scan_ingest.validate_scan_dpi` refuserait -- il exige un entier.
    """
    return f"{round(mesure)}"


@dataclass
class FormulaireDuDepot:
    """Le modele du depot : une source, un dpi, et le champ au focus.

    **Modele pur** : aucune dependance a `textual`, comme `panneau.py` et
    `explorateur.py`. C'est ce qui rend mesurables sans terminal les trois
    appariements a risque de cet ecran -- champ au focus contre ligne rendue,
    forme retenue contre vocabulaire du resume, et mesure du coeur contre
    valeur reprise.

    ``dpi`` est une **chaine** et non un entier : c'est ce que l'operateur
    frappe, et le champ doit pouvoir etre vide, ce qu'aucun entier ne sait
    dire. Il part **vide** (`EPIC11-ARB-38` : « elle n'est pas preremplie. Le
    champ reste requis, et vide »).
    """

    source: SourceDesignee | None = None
    dpi: str = ""
    #: Le champ courant, **suivi** : `aide_de_champ.ChampSuivi` compte chaque
    #: deplacement du curseur, et c'est ce compte qui fait TOMBER l'aide de
    #: champ au lieu de la cacher (correctif du 2026-09-04). Le comptage se
    #: fait a l'AFFECTATION : aucun chemin de navigation -- ni ceux d'ici, ni
    #: un chemin ajoute plus tard -- n'a rien a appeler pour cela.
    champ: str = aide_de_champ.ChampSuivi(CHAMP_SOURCE)
    #: Le premier rang visible de la liste des sources. **Un etat de la vue et
    #: non du curseur** : cette liste ne se choisit pas, elle se lit -- le
    #: curseur y designerait une source que `⏎` ne retiendrait pas, et
    #: `EPIC11-ARB-45` dit que « le curseur *est* la selection ».
    premier_visible: int = 0

    # -- lecture ------------------------------------------------------------

    def saisie(self, cle: str) -> str:
        """Ce qu'un champ de saisie porte VRAIMENT, blancs de bord retires.

        **Une seule redaction pour quatre surfaces** : la valeur dessinee
        (:meth:`EcranScanDepot.valeur_du_champ`), la mention de la colonne de
        droite (:meth:`EcranScanDepot.mention_du_champ`), la ligne d'etat
        (:meth:`EcranScanDepot.etat`) et la valeur citee par l'aide
        (:meth:`EcranScanDepot.valeur_de_l_aide`).

        **C'est le meme defaut que `E3-9` a deja paye, et il etait ouvert ici.**
        `Espace` est un geste annonce sur la ligne voisine ; frappe dans le dpi
        par reflexe, elle tombe sur `frapper(" ")` et rendait `dpi` VRAI. Les
        **trois** canaux qui disent « rien ici » -- le glyphe neutre, la mention
        `requis · dpi`, la ligne d'etat -- s'eteignaient ensemble pendant que
        `peut_detecter` restait faux : un champ requis qui se lit comme rempli
        et ne l'est pas (defaut `F-C1-1` de la revue du 2026-09-04).
        `FormulaireDeCalibration` portait cette methode ; le lot B a enrole
        `E3-1` dans le mecanisme d'aide sans porter la normalisation qui allait
        avec.

        Elle rend l'attribut **tel quel** quand il n'est pas une chaine : la
        source est un objet, et un `.strip()` n'y aurait aucun sens.
        """
        valeur = getattr(self, cle, "")
        return valeur.strip() if isinstance(valeur, str) else valeur

    def champs(self) -> tuple[str, ...]:
        """Les champs que `Tab` parcourt, dans l'ordre de saisie.

        **La reprise n'en est un que quand une mesure existe** : une ligne de
        formulaire qui proposerait de reprendre ce qui n'a pas ete mesure serait
        une cible qui ne fait rien, et le curseur s'y arreterait pour rien.

        **`Valider` en est un TOUJOURS** (retour terrain du 2026-09-06, patron
        d'`EPIC11-ARB-158`) : une ligne d'action qui n'existerait que lorsque
        l'action est possible serait invisible exactement quand l'operateur
        cherche pourquoi il ne peut pas partir. Elle est la, et elle DIT ce qui
        manque -- voir :func:`motif_du_refus_de_partir`.
        """
        if mention_de_la_mesure(self.source):
            return (CHAMP_SOURCE, CHAMP_DPI, CHAMP_REPRISE, CHAMP_VALIDER)
        return (CHAMP_SOURCE, CHAMP_DPI, CHAMP_VALIDER)

    @property
    def dpi_valide(self) -> int | None:
        """Le dpi saisi, **valide par le coeur**, ou `None`.

        `scan_ingest.validate_scan_dpi` est la seule autorite du depot sur ce
        qu'est un dpi acceptable : plafond de faute de frappe compris. Une
        seconde regle ecrite ici accepterait un `20001` que l'ingestion
        refuserait dix secondes plus tard.
        """
        if not self.dpi:
            return None
        try:
            return scan_ingest.validate_scan_dpi(int(self.dpi))
        except (ValueError, scan_ingest.InvalidScanDpiError):
            return None

    @property
    def peut_detecter(self) -> bool:
        """L'action principale est **inaccessible** tant qu'un champ requis est
        vide ou invalide (`DESIGN.md` section 7.3, `EPIC7-ARB-44` : le dpi est
        « obligatoire et sans defaut, aucun appelant n'en invente un »)."""
        return self.source is not None and self.dpi_valide is not None

    @property
    def sources_defilent(self) -> bool:
        """La liste des sources deborde-t-elle de sa zone ?

        C'est la condition de la **troisieme** ligne de raccourcis : `↑↓` ne
        fait rien sur une liste qui tient entiere, et l'annoncer alors serait
        promettre une touche inerte.
        """
        return (self.source is not None and self.source.est_multiple
                and len(self.source.sources) > HAUTEUR_DES_SOURCES)

    # -- ecriture -----------------------------------------------------------

    def avancer(self, pas: int = 1) -> bool:
        """`Tab` : le champ suivant, en boucle.

        En boucle, et non borne : le formulaire tient sur trois lignes, et une
        borne obligerait a une seconde touche pour revenir en arriere -- ce qui
        rendrait la ligne de reprise atteignable dans un sens seulement.
        """
        champs = self.champs()
        if self.champ not in champs:
            # La ligne de reprise a disparu sous le curseur (une source
            # redesignee, sans mesure cette fois) : on retombe sur le dpi
            # plutot que de laisser un focus qui ne designe plus rien.
            self.champ = CHAMP_DPI
            return True
        self.champ = champs[(champs.index(self.champ) + pas) % len(champs)]
        return True

    def poser_la_source(self, source: SourceDesignee) -> None:
        """Retenir la source mesuree. **Le dpi n'est pas touche.**

        `EPIC11-ARB-38` : la mesure « est confrontee au DPI declare, jamais
        substituee ». Poser la valeur mesuree ici serait la substitution que
        l'arbitrage interdit, sous la forme la plus difficile a voir -- un champ
        qui se remplit tout seul et qu'on ne relit pas.
        """
        self.source = source
        self.champ = CHAMP_DPI
        # **La vue repart en tete a chaque designation** : gardee, elle
        # montrerait le milieu d'une liste de trois sources apres en avoir
        # parcouru trente, c'est-a-dire une zone vide sans que rien ne le dise.
        self.premier_visible = 0

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans le champ de dpi. **Toute lettre s'y ecrit.**

        `EPIC11-ARB-68` : « aucune lettre n'est un raccourci dans un champ de
        saisie, sans exception et sans ordre de priorite a maintenir ». Filtrer
        les caracteres non numeriques serait une facon detournee de rendre une
        lettre inerte ; le champ les accepte et la validation les refuse, ce qui
        est visible.
        """
        if self.champ != CHAMP_DPI:
            return False
        self.dpi += caractere
        return True

    def effacer(self) -> bool:
        if self.champ != CHAMP_DPI or not self.dpi:
            return False
        self.dpi = self.dpi[:-1]
        return True

    def defiler_les_sources(self, pas: int) -> bool:
        """`↑↓` : faire glisser la fenetre de la liste, d'un rang a la fois.

        **La borne haute vient de `jetons.fenetre_de_liste` et non d'un calcul
        recrit** : la ligne `…` de tete se reserve dans la hauteur des qu'on a
        defile, si bien que la derniere source ne se voit qu'a partir de
        `total - hauteur + 1`. Un `total - hauteur` -- la borne « evidente » --
        laisserait la derniere source inaccessible, cachee derriere le `…` qui
        annonce justement qu'elle existe.

        Rend faux quand rien n'a bouge : la touche n'est alors pas consommee,
        et l'ecran ne se repeint pas pour rien.
        """
        if not self.sources_defilent:
            return False
        total = len(self.source.sources)
        maximum = max(total - HAUTEUR_DES_SOURCES + 1, 0)
        vise = min(max(self.premier_visible + pas, 0), maximum)
        if vise == self.premier_visible:
            return False
        self.premier_visible = vise
        return True

    def reprendre_la_mesure(self) -> bool:
        """Le geste qui reprend le dpi mesure d'un coup (AC 4.3).

        **Ce geste n'est pas une lettre** (`EPIC11-ARB-68`, `EPIC11-ARB-101`
        note 7, tranche par Egan : « Oui pourquoi pas ! ») : la mesure est une
        **ligne du formulaire**, atteinte par `Tab` et validee par `⏎`. Zero
        ressaisie, mais un acte de l'operateur -- ce qui reste conforme a
        `EPIC11-ARB-38` : la valeur est offerte, jamais posee.
        """
        if self.source is None or self.source.dpi is None:
            return False
        self.dpi = dpi_lisible(self.source.dpi)
        return True


class EcranScanDepot(CoutureExplorateur, Palier):
    """`E3-1` et `E3-1b` -- un seul champ de source, trois formes, un dpi.

    **L'explorateur est celui du depot, pas un second** (AC 3.1) :
    `EPIC11-ARB-48` nomme `E3-1` comme l'un de ses cinq sites, et la story 11.2b
    l'a livre sans le cabler ici. `montrer_fichiers=True` et son `accepte=` sont
    passes explicitement -- c'est ce qui rend le reglage lisible : on designe
    une source, pas un dossier de projet.

    **Le clavier passe par `CoutureExplorateur`** (AC 3.2) : cet ecran ne recable
    aucune touche a la main, comme `E2-1` ne l'a pas fait. Un composant partage
    dont chaque site reimplemente le routage ne tient que la moitie de sa
    promesse.

    `detecter` est **injecte** : l'ecran ne lance pas la detection, il la
    demande. C'est ce qui garde le temps 1 en deux moities separables -- le
    depot ici, l'execution ailleurs.

    **Une limite HERITEE, dite plutot que tue** : le collage d'un chemin dans la
    barre d'adresse (`CoutureExplorateur.coller`) ne s'applique que dans la zone
    `ecran_projet.ZONE_CHEMIN`, donc il est inerte ici comme il l'est deja sur
    `E2-1`. La couture est bien celle du composant partage -- un test mesure
    l'identite de fonction --, mais son garde-fou de zone n'est vrai que du site
    qui l'a ecrite. Le corriger touche `ecran_projet.py`, partage par trois
    ecrans livres : c'est un finding, pas un elargissement de ce lot.
    """

    titre = "Scan"
    raccourcis = RACCOURCIS_DEPOT_SANS_SOURCE
    #: **La famille d'exploration de cet ecran** -- retour terrain d'Egan du
    #: 2026-09-06, « l'explorateur de fichiers ne retient pas le dernier chemin
    #: explore ». C'est `FAMILLE_MATIERE` et non `FAMILLE_PROJETS` : on designe
    #: ici un scan a deposer, c'est-a-dire de la matiere, et la partager avec
    #: les dossiers de projet renverrait l'operateur dans l'arborescence de ses
    #: projets a chaque depot. Le partage, sa creation a la demande et son
    #: application sont tenus par `CoutureExplorateur` : cette ligne est tout
    #: ce que le site a a poser.
    FAMILLE_D_EXPLORATION = FAMILLE_MATIERE
    #: **La declaration qui fait entrer cet ecran dans l'ensemble borne** de
    #: `aide_de_champ.ECRANS_A_TABLE_D_AIDE` (AC 1.5, `EPIC11-ARB-198`).
    TABLE_D_AIDE = AIDE_PAR_CHAMP

    def __init__(self, dossier=None, *,
                 detecter: Callable[[Path, int], None] | None = None,
                 mesurer=None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._detecter = detecter
        self._mesurer = mesurer
        self.formulaire = FormulaireDuDepot()
        self.zone = ZONE_FORMULAIRE
        # **Monte a la construction et non a l'ouverture** : l'explorateur lit
        # `Path.cwd()`, et le lire plus tard ferait dependre le dossier de
        # depart du moment ou l'on appuie. Motif d'`ecran_projet` repris tel
        # quel, et de `EcranRushes` apres lui.
        self.explorateur = Explorateur(montrer_fichiers=True,
                                       accepte=source_acceptable,
                                       selection_multiple=True)
        self._etat_a_dire = ""
        #: `F1` : l'aide du champ courant (story 11.9, AC 1). Elle **remplace**
        #: la ligne blanche qui suit le titre : le corps garde donc exactement
        #: le meme cardinal de lignes aide ouverte et aide fermee, et le dessin
        #: approuve ne bouge pas d'un caractere tant qu'elle est fermee. C'est
        #: pour cela que la consigne est vide -- cet ecran n'en dessine aucune,
        #: et lui en inventer une changerait `E3-1` sans qu'aucun arbitrage ne
        #: l'ait demande.
        self.aide = aide_de_champ.AideDeChamp(
            AIDE_PAR_CHAMP, formulaire=self.formulaire)

    # -- lecture ------------------------------------------------------------

    def _appliquer_la_zone(self) -> None:
        """Poser la ligne de raccourcis de la zone courante.

        **`raccourcis` reste un ATTRIBUT, jamais une propriete** : la garde
        d'epic de `test_repli_ascii.py` lit `classe.raccourcis` au niveau de la
        CLASSE, et une propriete ferait echapper cet ecran a la mesure.

        **L'aide de champ tombe en quittant le formulaire.** Elle tombe deja
        toute seule au changement de CHAMP -- le mecanisme retient celui sur
        lequel `F1` a ete frappee --, mais entrer dans l'explorateur ne change
        aucun champ : sans ce geste, l'aide reapparaitrait au retour, sur un
        ecran ou plus personne ne l'a demandee.
        """
        if self.zone != ZONE_FORMULAIRE:
            self.aide.fermer()
        if self.zone == ZONE_EXPLORATEUR:
            self.raccourcis = raccourcis_de_l_explorateur(self.explorateur)
            return
        self.raccourcis = self.pied_du_formulaire()

    def pied_du_formulaire(self) -> str:
        """**Le pied dit le geste de la LIGNE COURANTE** (patron d'`E3-9`).

        Il ne le disait pas : il annoncait « ⏎ détecter » des qu'une source
        etait posee, depuis n'importe quelle ligne -- y compris depuis `Source`,
        ou `⏎` ouvre l'explorateur. Un pied qui promet un geste que la ligne ne
        fait pas est le meme defaut que la touche inerte, retourne.

        **Mesurable sans monter l'ecran** : aucune lecture de `self.app`.
        """
        champ, formulaire = self.formulaire.champ, self.formulaire
        if champ == CHAMP_SOURCE and formulaire.source is None:
            # L'etat d'ouverture de l'ecran, et sa redaction d'origine.
            return RACCOURCIS_DEPOT_SANS_SOURCE
        tient, deborde = PIED_PAR_CHAMP.get(
            champ, (RACCOURCIS_DEPOT, RACCOURCIS_DEPOT_MULTIPLE))
        return deborde if formulaire.sources_defilent else tient

    def bandeau(self, largeur: int | None = None) -> str:
        """Le bandeau, avec « temps 1 sur 2 · détecter » a droite."""
        from .coque import Contexte

        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, OBJET_DU_DEPOT)
        return contexte.rendu(self.app.size.width if largeur is None else largeur,
                              getattr(self.app, "ascii_seul", False))

    def valeur_du_champ(self, cle: str) -> str:
        """Ce que le champ affiche a droite de son libelle.

        Le glyphe `neutre` -- et jamais une chaine vide -- marque un champ non
        renseigne : `DESIGN.md` section 6 en fait le second canal de « rien
        ici », et une case vide se lit comme un defaut de rendu.
        """
        neutre = self.app.glyphes["neutre"]
        if cle == CHAMP_VALIDER:
            # **Le mot occupe la colonne des VALEURS**, pas celle des libelles :
            # c'est la forme du bouton d'`E5-2`, et elle est sans seconde
            # colonne (voir :data:`LIBELLE_VALIDER`).
            return LIBELLE_VALIDER
        if cle == CHAMP_SOURCE:
            source = self.formulaire.source
            if source is None:
                return neutre
            if source.est_multiple:
                # Le champ dit ce qui a ete designe ; **la liste, en dessous,
                # dit quoi** (note 5 d'Egan). Y ecrire le premier chemin de la
                # sequence ferait passer une designation de trente planches
                # pour une seule.
                return LIBELLE_SOURCES_MULTIPLES
            utile = jetons.largeur_utile(self.app.size.width)
            place = utile - len(INDENT_DU_CURSEUR) - LARGEUR_DU_LIBELLE - 2
            return jetons.abreger_chemin(str(source.chemin), max(place, 1),
                                         self.app.ascii_seul)
        if cle == CHAMP_DPI:
            # `saisie` et non l'attribut brut : un dpi de blancs doit rendre le
            # glyphe neutre, qui est le second canal de « rien ici ».
            return self.formulaire.saisie(CHAMP_DPI) or neutre
        source = self.formulaire.source
        if source is None or source.dpi is None:
            return neutre
        return f"{dpi_lisible(source.dpi)} {UNITE_DPI}"

    def valeur_de_l_aide(self, cle: str) -> str:
        """La **valeur du contexte courant** que l'aide de ce champ cite (AC 1.1).

        Elle ne redit pas la colonne de valeur : elle dit ce que la ligne ne
        montre pas. Le champ de source affiche un chemin abrege ; l'aide dit
        **combien** de fichiers une designation multiple porte. Le champ de dpi
        affiche la frappe telle quelle ; l'aide dit ce que le coeur en fait --
        `dpi_valide` est la seule autorite, et un `999999` saisi se lit
        « hors bornes » ici alors que la ligne le montre sans commentaire.

        **Aucune lecture de `self.app`** : cette methode est mesurable sans
        terminal, comme le formulaire qu'elle interroge.
        """
        source = self.formulaire.source
        if cle == CHAMP_VALIDER:
            # **Le motif est LU de la seule redaction**, jamais reecrit ici.
            if self.formulaire.peut_detecter:
                return AIDE_PRET_A_PARTIR
            return motif_du_refus_de_partir(self.formulaire)[0]
        if cle == CHAMP_SOURCE:
            if source is None:
                return AIDE_SANS_SOURCE
            if source.est_multiple:
                return f"{len(source.sources)} fichiers"
            return Path(source.chemin).name
        if cle == CHAMP_DPI:
            saisi = self.formulaire.saisie(CHAMP_DPI)
            if not saisi:
                return aide_de_champ.VALEUR_ABSENTE
            if self.formulaire.dpi_valide is None:
                return AIDE_DPI_REFUSE.format(saisi=saisi)
            return saisi
        if source is None or source.dpi is None:
            return AIDE_SANS_MESURE
        return f"{dpi_lisible(source.dpi)} {UNITE_DPI}"

    def mention_du_champ(self, cle: str) -> str:
        """La colonne de droite d'un champ : ce qui manque, ou la mesure."""
        if cle == CHAMP_VALIDER:
            # **Le motif est sur la ligne de l'action**, la ou l'operateur
            # regarde au moment ou il appuie -- pas seulement en ligne d'etat.
            if self.formulaire.peut_detecter:
                return ""
            return motif_du_refus_de_partir(self.formulaire)[0]
        if cle == CHAMP_SOURCE:
            return "" if self.formulaire.source is not None else MENTION_REQUIS
        if cle == CHAMP_DPI:
            # Meme lecture que la valeur dessinee : sans elle, un dpi de blancs
            # affichait une valeur pendant que sa mention `requis` disparaissait.
            return ("" if self.formulaire.saisie(CHAMP_DPI)
                    else MENTION_REQUIS_DPI)
        return mention_de_la_mesure(self.formulaire.source)

    def ligne_de_champ(self, cle: str, libelle: str, utile: int) -> str:
        """Une ligne de formulaire : libelle, glyphe de focus, valeur, mention.

        Le glyphe `>` marque le champ **au focus** (`DESIGN.md` section 7.3), et
        il ouvre sa colonne : les autres champs portent un blanc a sa place,
        pour que les valeurs restent alignees quand le focus se deplace.
        """
        table = self.app.glyphes
        focus = table["invite"] if self.formulaire.champ == cle else " "
        gauche = (f"{INDENT_DU_CURSEUR}{libelle:<{LARGEUR_DU_LIBELLE}}"
                  f"{focus} {self.valeur_du_champ(cle)}")
        return _cale_a_droite(gauche, self.mention_du_champ(cle), utile)

    def lignes_du_formulaire(self, utile: int) -> list[str]:
        """Le corps de `E3-1`, **sous les dix-sept lignes du plancher**.

        La ligne `Valider` **ferme l'ecran** et non le bloc de saisie : c'est la
        place qu'`E3-9` lui donne -- sous le filet, avec ce qu'elle execute --,
        et la seule qui reste ici sans crever le plancher. Elle n'est **pas**
        precedee d'une ligne vide, et c'est mesure plutot que choisi : au regime
        le plus haut de cet ecran (une designation multiple qui deborde, avec sa
        ligne de reprise) le corps fait deja seize lignes, et le blanc de
        respiration d'`E3-9` en ferait dix-huit -- la ligne d'action serait
        alors dessinee hors du cadre, ce que `textual` ne signale pas. C'est
        aussi la grammaire du bouton d'`E5-2`, qui suit son voisin sans blanc.
        """
        libelles = {CHAMP_SOURCE: LIBELLE_SOURCE, CHAMP_DPI: LIBELLE_DPI,
                    CHAMP_REPRISE: LIBELLE_REPRISE, CHAMP_VALIDER: ""}
        corps = [INDENT_DU_TEXTE + TITRE_DU_DEPOT,
                 aide_de_champ.ligne_de_tete_de(
                     self, self.formulaire.champ, utile=utile,
                     indent=INDENT_DU_TEXTE,
                     ascii_seul=self.app.ascii_seul)]
        for cle in self.formulaire.champs():
            if cle == CHAMP_VALIDER:
                # Elle est dessinee en dernier, sous le resume : passer ici
                # laisserait « Valider » au milieu du formulaire, c'est-a-dire
                # ailleurs qu'« en bas » (`EPIC11-ARB-158`).
                continue
            if cle == CHAMP_DPI:
                # La ligne vide separe la source de la resolution : ce sont deux
                # questions, et la reprise appartient a la seconde -- elle reste
                # donc collee au champ de dpi, sans ligne entre eux.
                corps.append("")
            corps.append(self.ligne_de_champ(cle, libelles[cle], utile))
        corps += ["", filet(utile, TITRE_DU_RESUME, self.app.ascii_seul), ""]
        source = self.formulaire.source
        corps.append(INDENT_DU_CURSEUR + (resume_de_la_source(source)
                                          if source is not None
                                          else LIBELLE_RIEN_ENCORE))
        if source is not None and source.est_multiple:
            corps.append("")
            corps += self.lignes_des_sources(utile)
        corps.append(self.ligne_de_champ(CHAMP_VALIDER,
                                         libelles[CHAMP_VALIDER], utile))
        return corps

    def lignes_des_sources(self, utile: int) -> list[str]:
        """La liste navigable des sources, `…` compris (note 5 d'Egan).

        **Le defilement est celui de l'explorateur, pas un second** : la fenetre
        vient de `jetons.fenetre_de_liste` et la ligne de position se lit comme
        la sienne (`…   1-4 sur 8`). Une seconde mecanique de fenetrage
        divergerait sur la seule chose qui compte ici -- la reservation d'une
        ligne pour chaque `…` **avant** le decoupage, sans quoi la derniere
        source se cacherait derriere le `…` qui annonce qu'elle existe.

        La zone n'est **pas rembourree** a hauteur fixe : le formulaire qui la
        precede change deja de hauteur avec la ligne de reprise, et des blancs
        de remplissage n'y stabiliseraient rien tout en poussant le plancher.
        """
        source = self.formulaire.source
        ascii_seul = self.app.ascii_seul
        neutre = self.app.glyphes["neutre"]
        total = len(source.sources)
        premier, dernier = jetons.fenetre_de_liste(
            total, self.formulaire.premier_visible, HAUTEUR_DES_SOURCES)
        points = jetons.points_d_abregement(ascii_seul)
        rendues = []
        if premier > 0:
            rendues.append(INDENT_DU_CURSEUR + points)
        for rang in range(premier, dernier + 1):
            chemin, octets = source.sources[rang]
            rendues.append(ligne_d_une_source(chemin, octets, utile,
                                              neutre, ascii_seul))
        if dernier < total - 1:
            rendues.append(_cale_a_droite(
                INDENT_DU_CURSEUR + points,
                f"{premier + 1}-{dernier + 1} sur {total}", utile))
        return rendues

    def lignes(self) -> list[str]:
        if self.zone == ZONE_EXPLORATEUR:
            # **Par mots-cles, et la largeur BRUTE** : `Explorateur.lignes`
            # prend `(largeur, titre, libelle, ascii_seul)`, et l'appeler
            # positionnellement poserait `ascii_seul` dans `titre`. Piege deja
            # paye sur `EcranRushes`, et trouve en MARCHANT le parcours.
            return self.explorateur.lignes(
                self.app.size.width, titre=TITRE_DU_DEPOT,
                libelle=LIBELLE_SOURCE, ascii_seul=self.app.ascii_seul)
        return self.lignes_du_formulaire(
            jetons.largeur_utile(self.app.size.width))

    def etat(self) -> str:
        """La ligne d'etat : une **mesure** de l'ecran courant.

        Vide quand il n'y a rien a dire -- et il n'y a rien a dire tant qu'aucune
        source n'est designee : l'ecran n'a encore rien compte.
        """
        if self._etat_a_dire:
            return self._etat_a_dire
        if self.zone == ZONE_EXPLORATEUR:
            return self.explorateur.etat(
                jetons.largeur_utile(self.app.size.width),
                self.app.ascii_seul)
        if (self.formulaire.source is not None
                and not self.formulaire.saisie(CHAMP_DPI)):
            return jetons.marque("absent", PHRASE_DPI_REQUIS,
                                 self.app.ascii_seul)
        return ""

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-scan-depot")
        return [Vertical(self._corps, id="centre-scan-depot")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        rang = (self.explorateur.rang_du_curseur()
                if self.zone == ZONE_EXPLORATEUR else None)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            ligne_du_curseur=rang))
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
        self._etat_a_dire = ""
        if self.zone == ZONE_EXPLORATEUR:
            traite = self._traiter_l_explorateur(touche, caractere)
            self._appliquer_la_zone()
            return traite
        if touche == "f1":
            # **`F1` est consommee ICI quand le focus est sur un champ**, et
            # elle ne l'est pas autrement (AC 1.4). Consommee, l'aide du champ
            # remplace la ligne de tete ; non consommee -- dans l'explorateur,
            # ou sur une ligne que la table ne porte pas --, elle remonte a la
            # liaison applicative, qui ouvre le manuel des raccourcis. Sans le
            # premier volet, le manuel s'ouvrirait par-dessus le formulaire ;
            # sans le second, il ne s'ouvrirait jamais depuis cet ecran.
            return self.aide.basculer(self.formulaire.champ)
        if touche == "tab":
            avance = self.formulaire.avancer()
            # **Le pied suit le curseur**, sinon il annoncerait le geste de la
            # ligne qu'on vient de quitter -- exactement le mensonge que la
            # table `PIED_PAR_CHAMP` ferme.
            self._appliquer_la_zone()
            return avance
        if touche in ("up", "down"):
            # **`↑↓` ne fait defiler que la liste des sources**, et rien
            # d'autre : le formulaire se parcourt par `Tab` (`DESIGN.md`
            # section 7.3), et donner deux moyens de deplacer le focus ferait
            # deux etats a tenir pour une seule intention.
            return self.formulaire.defiler_les_sources(
                -1 if touche == "up" else 1)
        if touche == "enter":
            return self._valider_le_formulaire()
        if touche == "backspace":
            return self.formulaire.effacer()
        if caractere and caractere.isprintable():
            # **Aucune lettre n'est un raccourci ici** (`EPIC11-ARB-68`) : le
            # champ de dpi est un champ de saisie, et une lettre frappee doit
            # s'y ecrire. Hors du champ, la frappe est consommee plutot que de
            # remonter au binding applicatif `q` -- une meme touche qui
            # quitterait ou saisirait selon le champ serait pire qu'inerte.
            self.formulaire.frapper(caractere)
            return True
        return False

    def _valider_le_formulaire(self) -> bool:
        """Ce que `⏎` fait, champ par champ. **Une seule ligne lance.**

        Retour terrain d'Egan du 2026-09-06 : « le seul moyen de valider est de
        faire Enter sur le DPI, pas intuitif ». Il ne l'etait pas parce que la
        detection partait d'un **champ de saisie** -- frapper une resolution
        puis valider par reflexe lancait le temps 1. Desormais `⏎` fait **le
        geste de sa ligne**, et seule la ligne `Valider` lance.

        Sur le champ de dpi il n'y a pas de geste propre : `⏎` y **descend**, ce
        qui est la convention de tout formulaire et ne surprend personne. Il n'y
        est donc jamais inerte -- « une touche annoncee qui ne fait rien et ne
        dit rien est indistinguable d'un clavier casse » --, et le pied ne
        l'annonce que la ou il fait autre chose que descendre.
        """
        if self.formulaire.champ == CHAMP_SOURCE:
            return self._ouvrir_l_explorateur()
        if self.formulaire.champ == CHAMP_REPRISE:
            return self.formulaire.reprendre_la_mesure()
        if self.formulaire.champ != CHAMP_VALIDER:
            avance = self.formulaire.avancer()
            self._appliquer_la_zone()
            return avance
        if not self.formulaire.peut_detecter:
            # **L'action principale reste inaccessible**, et elle DIT pourquoi :
            # une touche annoncee qui ne fait rien et ne dit rien est
            # indistinguable d'un clavier casse. Le motif est **lu de la seule
            # redaction**, celle que la mention de la ligne porte deja : deux
            # redactions ont deja diverge sur `E3-9`.
            self._etat_a_dire = jetons.marque(
                "absent", motif_du_refus_de_partir(self.formulaire)[1],
                self.app.ascii_seul)
            return True
        self._lancer_la_detection()
        return True

    def _lancer_la_detection(self) -> None:
        """Passer la main -- **cet ecran ne detecte rien lui-meme**.

        **Jamais de retour muet** : sans rappel de detection cable, l'ecran
        NOMME ce qui manque au lieu de consommer la touche sur rien. C'est le
        meme geste que `EcranRushes` sur un ajout sans rappel, et il a ete paye
        la-bas : une validation silencieuse est indistinguable d'un plantage.
        """
        if self._detecter is None:
            self.app.descendre(EcranPasEncore(CE_QUI_MANQUE_POUR_DETECTER,
                                              QUAND_LA_DETECTION))
            return
        # **Tel quel** (`EPIC7-ARB-88`) : une sequence part en sequence, et
        # c'est l'ingestion qui distingue les quatre formes, elle seule.
        self._detecter(self.formulaire.source.argument_de_detection,
                       self.formulaire.dpi_valide)

    def _ouvrir_l_explorateur(self) -> bool:
        # **A l'ouverture, avant la relecture** : la reprise peut deplacer
        # l'explorateur, et relire d'abord ferait payer deux listages du disque
        # dont un de l'ancien dossier, que personne ne verra.
        # `reprendre_la_memoire` relit elle-meme quand elle deplace ; le
        # `relire` ci-dessous reste pour le cas ou elle ne deplace rien -- le
        # dossier a pu changer sous nos pieds depuis la derniere visite. Meme
        # ordre que `EcranRushes._ouvrir_l_explorateur`, et pour le meme motif.
        self.reprendre_la_memoire_de_session()
        self.explorateur.relire()
        self.zone = ZONE_EXPLORATEUR
        self._appliquer_la_zone()
        return True

    # -- les deux gestes que la couture laisse a l'ecran ----------------------

    def _sortir_de_l_explorateur(self) -> bool:
        """Ou mene `Échap` : au formulaire, jamais d'un dossier vers son parent
        (`EPIC11-ARB-2`)."""
        self.zone = ZONE_FORMULAIRE
        self._appliquer_la_zone()
        return True

    def _valider_l_explorateur(self) -> None:
        """Ce que `⏎` fait de la cible : **il la mesure, il n'ingere rien**."""
        # **`valider()` et non `cible_de_validation()`**, et c'est le finding 1
        # de la revue de la 11.2c, renvoye nommement a cette story : « des
        # qu'une coche existe, la ligne du bas annonce la selection et `⏎` la
        # rend, mais `cible_de_validation()` rend toujours l'entree sous le
        # curseur ». Lire la seconde ici ferait retenir **autre chose que ce
        # que l'ecran vient de promettre**, sur le geste ou la promesse compte
        # le plus.
        cible = self.explorateur.valider()
        if cible is None:
            self._etat_a_dire = jetons.marque(
                "substitute", "rien a valider", self.app.ascii_seul)
            return
        try:
            source = designer(cible, mesurer=self._mesurer)
        except scan_ingest.ScanIngestError as refus:
            # **Le motif du coeur, verbatim** : c'est deja une phrase pour
            # l'operateur, et la resumer la detruirait (`EPIC11-ARB-30`).
            # L'ecran reste sur l'explorateur : la cible est fautive, pas le
            # geste, et refermer ferait recommencer la navigation.
            self._etat_a_dire = jetons.marque("absent", str(refus),
                                              self.app.ascii_seul)
            return
        self.formulaire.poser_la_source(source)
        self.zone = ZONE_FORMULAIRE
        self._appliquer_la_zone()


__all__ = [
    "AIDE_PAR_CHAMP",
    "AIDE_PRET_A_PARTIR",
    "ARTICLE_SINGULIER",
    "CE_QUI_MANQUE_POUR_DETECTER",
    "CHAMP_DPI",
    "CHAMP_REPRISE",
    "CHAMP_SOURCE",
    "CHAMP_VALIDER",
    "CLE_DE_LA_DETECTION",
    "ENTREES_DU_MENU",
    "EcranScanDepot",
    "EcranScanMenu",
    "EntreeDeMenu",
    "FormulaireDuDepot",
    "HAUTEUR_DES_SOURCES",
    "LIBELLE_DPI",
    "LIBELLE_DU_PROFIL",
    "LIBELLE_REPRISE",
    "LIBELLE_RIEN_ENCORE",
    "LIBELLE_SOURCE",
    "LIBELLE_SOURCES_MULTIPLES",
    "LIBELLE_VALIDER",
    "MENTION_REQUIS",
    "MENTION_REQUIS_DPI",
    "MENTION_VALIDER_DPI_REFUSE",
    "MENTION_VALIDER_SANS_DPI",
    "MENTION_VALIDER_SANS_SOURCE",
    "OBJET_DU_DEPOT",
    "PHRASE_DPI_REFUSE",
    "PHRASE_DPI_REQUIS",
    "PHRASE_SOURCE_REQUISE",
    "PIED_PAR_CHAMP",
    "PIED_SANS_PROFIL",
    "QUAND_LA_DETECTION",
    "RACCOURCIS_DEPOT",
    "RACCOURCIS_DEPOT_MULTIPLE",
    "RACCOURCIS_DEPOT_SANS_SOURCE",
    "RACCOURCIS_SCAN_MENU",
    "RACCOURCIS_SUR_LA_REPRISE",
    "RACCOURCIS_SUR_LA_REPRISE_MULTIPLE",
    "RACCOURCIS_SUR_LA_SOURCE",
    "RACCOURCIS_SUR_LA_SOURCE_MULTIPLE",
    "RACCOURCIS_SUR_VALIDER",
    "RACCOURCIS_SUR_VALIDER_MULTIPLE",
    "SourceDesignee",
    "TITRE_DU_DEPOT",
    "TITRE_DU_MENU",
    "TITRE_DU_RESUME",
    "ZONE_EXPLORATEUR",
    "ZONE_FORMULAIRE",
    "compte_dans_le_vocabulaire",
    "designer",
    "dpi_lisible",
    "filet",
    "ligne_d_une_source",
    "mention_de_la_mesure",
    "motif_du_refus_de_partir",
    "pied_du_menu",
    "poids_du_fichier",
    "resume_de_la_source",
    "source_acceptable",
    "unite_du_cardinal",
]
