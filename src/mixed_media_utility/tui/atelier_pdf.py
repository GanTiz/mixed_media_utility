# -*- coding: utf-8 -*-
"""L'atelier Pdf, ecran `E5-0` : le menu de l'atelier et sa porte.

Story 11.7, **lot C** (AC 3). C'est le quatrieme atelier, et il etait jusqu'ici
le seul dont **aucun** ecran n'existait : `⏎` sur l'entree `Pdf` du menu des
ateliers menait a `EcranPasEncore`. Ce module tient cette promesse pour la
premiere moitie -- la porte et le menu -- et laisse les deux parcours qu'il
annonce aux lots voisins.

**Deux entrees, donc un menu** (`EPIC11-ARB-28`, verbatim : « **Tout atelier qui
a plus d'une entree commence par un menu d'atelier** »). Composer des planches
est le parcours principal ; la mire de calibration est le second. Le patron est
celui d'`atelier_scan.EcranScanMenu`, et il n'est pas re-redige : les constantes
de geometrie, la classe :class:`~mixed_media_utility.tui.atelier_scan.EntreeDeMenu`
et son invariant (« une entree non construite **doit** dire quand elle arrive »)
sont **importes**. Les deux maquettes `E3-0` et `E5-0` sont la meme colonne a la
colonne pres ; en recopier les chiffres ici les ferait diverger au premier
reglage, ce qui est exactement la classe de defaut que ce depot a deja payee
trois fois.

**Ce que ce module ne fait pas, et c'est structurel :**

* il **n'importe jamais `cli`** (frontiere de la story 11.4b) ;
* il **ne calcule aucun rang de tirage** (`EPIC11-ARB-92`, verbatim d'Egan : « il
  ne faut pas rendre le rang »). Le rang du pied est **lu** de l'inventaire du
  manifeste, jamais deduit d'un balayage ni d'un `max(...) + 1`. Il va plus loin
  que ca : **quand le manifeste ne declare aucun rang, le pied n'en affiche
  aucun** et dit `tirage d'origine`. C'est la meme convention que le nom de
  fichier, ou le rang d'origine n'ecrit aucun fragment (`EPIC11-ARB-88`), et
  c'est ce qui permet a ce module de ne porter **aucun** mot du vocabulaire des
  rangs du coeur -- ce que la frontiere de la story 11.6
  (`test_versionnage_du_scan_en_tui.py`) mesure sur le paquet entier, prose
  comprise. Deux frontieres AST de plus le mesurent ici, avec leur volet
  symetrique ;
* il **ne calcule aucune domination de geometries** : ce calcul vit au coeur
  depuis le lot B8 (`page_templates.bilan_de_domination`), et les ecrans de
  reglages l'**appellent**.

**Le pied ne dit que ce que le manifeste sait, et il y a un ecart avec la
maquette.** La maquette `E5-0` porte, sous le nom du tirage, `26/08 · 16 pages ·
tirage 3`. Or l'inventaire des tirages (`io.pdf_manifest.SHEETS_INVENTORY_FIELD`,
schema `additionalProperties: false`) ne porte **que** `path` et `version_rank` :
ni date, ni cardinal de pages. Les deux manquants sont donc **derives**, chacun
de la seule source qui les possede :

* les **pages** se recalculent par `pdf_composition.page_count_du_lot`, c'est-a-dire
  par le meme chemin que l'impression et jamais par un second calcul ;
* la **date** est celle du fichier sur le disque -- le seul signal d'horloge qui
  existe pour un tirage. Le manifeste n'en porte aucun **par construction** :
  son idempotence est verifiee octet a octet, et `io.pdf_manifest` exclut
  nommement `generated_at` pour cela. C'est aussi ce qui fixe le sens de
  « dernier » : l'ordre de `sheets_pdfs[]` est **trie par chemin** a l'ecriture,
  precisement pour ne **pas** porter l'ordre chronologique des impressions. Un
  `[-1]` y serait une invention.

Le pied lit donc le disque, comme celui du menu du Scan
(`atelier_scan.pied_du_menu`, qui appelle `profil_par_defaut`) : c'est le meme
endroit et le meme geste. Quand aucun fichier ne repond, le tirage reste nomme
et son segment de date **disparait** plutot que de mentir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..io import pdf_manifest
from . import jetons, projet_lecture
from .atelier_scan import (INDENT_DU_CURSEUR, INDENT_DU_TEXTE, LARGEUR_DU_NOM,
                           EntreeDeMenu, filet)
from .coque import EcranPasEncore, Palier

# ===========================================================================
# `E5-0` -- le menu de l'atelier (AC 3)
# ===========================================================================

#: La ligne de raccourcis du menu, verbatim de la maquette `E5-0` (l. 23), et
#: identique a celle du menu du Scan : les deux ecrans offrent les memes gestes.
#: Elle reste une constante de module **propre a cet atelier** plutot qu'un
#: import de `atelier_scan` : la garde d'epic des majuscules et celle du repli
#: ASCII balayent les `RACCOURCIS_*` de chaque module, et une ligne empruntee
#: sortirait de la mesure de l'atelier qui l'affiche.
#:
#: MESURE: 57/62
RACCOURCIS_PDF_MENU = ("⏎ entrer  ↑↓ naviguer  Échap ateliers  "
                       "F1 aide  Q quitter")

#: Le titre du menu, verbatim de la maquette (l. 5).
TITRE_DU_MENU = "Atelier Pdf"

#: Les cles des deux entrees. En constantes parce que **deux modules les
#: comparent** -- ce menu, et le cablage du parcours que les lots voisins
#: posent --, exactement comme `atelier_scan.CLE_DE_LA_DETECTION`. Une chaine
#: ecrite deux fois divergerait au premier renommage, et l'entree cesserait de
#: mener quelque part **en silence**.
CLE_DE_LA_COMPOSITION = "composer"
CLE_DE_LA_MIRE = "calibration"

#: L'echeance annoncee tant que le parcours n'est pas cable. Elle vit ici et non
#: sur les entrees : les deux entrees sont **construites** -- leurs ecrans sont
#: livres par les lots voisins de cette meme story --, et c'est le rappel qui
#: manque, pas l'ecran. « Sans la date, on ne distingue pas "pas encore fait" de
#: "abandonne" » ; sans cette branche, `⏎` serait muette, ce qui est
#: indistinguable d'un clavier casse.
QUAND_L_ATELIER_PDF = "la suite de l'atelier Pdf"

#: **DEUX entrees**, dans l'ordre de la chaine de travail : on compose avant de
#: calibrer, donc le curseur part sur le parcours principal. `EPIC11-ARB-28`
#: verbatim : « Tout atelier qui a plus d'une entree commence par un menu
#: d'atelier ».
ENTREES_DU_MENU: tuple[EntreeDeMenu, ...] = (
    EntreeDeMenu(
        CLE_DE_LA_COMPOSITION, "Composer des planches",
        "Mettre un ou plusieurs lots en pages imprimables. "
        "Le parcours principal."),
    EntreeDeMenu(
        CLE_DE_LA_MIRE, "Planche de calibration",
        "Générer la mire à imprimer avec les planches, pour calibrer "
        "le scanner."),
)


# ===========================================================================
# Le bandeau -- deux mesures, une seule lecture (AC 3.5)
# ===========================================================================

#: Le participe accorde de « tirages produits ». Une table de deux entrees et
#: non un `+ "s"` mecanique : le nom **et** son participe s'accordent, et
#: `projet_lecture.accorder` ne porte que le nom. Le singulier vaut aussi pour
#: zero, comme dans `projet_lecture`.
PARTICIPE_DES_TIRAGES = {False: "produit", True: "produits"}


@dataclass(frozen=True)
class ComptesDuPdf:
    """La droite du bandeau : `5 lots · 3 tirages produits`.

    **Les deux mesures sortent du meme document deja lu** (AC 3.5). Relire le
    manifeste une seconde fois pour le second compte donnerait deux etats
    potentiellement differents d'un projet qu'un autre processus peut ecrire
    entre-temps -- et le bandeau contredirait alors son propre pied. C'est
    exactement le motif deja ecrit sur `ecran_ateliers.EcranAteliers.charger`.
    """

    lots: int = 0
    tirages: int = 0

    def rendu(self) -> str:
        """`5 lots · 3 tirages produits`, au singulier quand il le faut.

        Un projet vide rend `0 lot · 0 tirage produit` -- **jamais** une chaine
        vide : « jamais une ligne vide » vaut au bandeau comme au pied.
        """
        return " · ".join((
            projet_lecture.accorder(self.lots, "lot"),
            f"{projet_lecture.accorder(self.tirages, 'tirage')} "
            f"{PARTICIPE_DES_TIRAGES[self.tirages > 1]}"))


def compter(manifeste: Mapping[str, Any] | None) -> ComptesDuPdf:
    """Les lots du projet, et **la somme** de leurs tirages.

    La somme, et non le compte du premier lot : un projet porte plusieurs lots
    imprimes, et un compte pris sur `lots[0]` serait juste tant qu'un seul en
    porte -- ce qu'une fabrique mono-lot ne demasque jamais. C'est le meme piege
    que `projet_lecture.compter` documente pour les masters, et il a deja coute
    une story a ce depot (mutant `M25`).
    """
    lots = projet_lecture._lots(manifeste)
    tirages = 0
    for lot in lots:
        tirages += len(_inventaire_du_lot(lot))
    return ComptesDuPdf(lots=len(lots), tirages=tirages)


def _inventaire_du_lot(lot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Les entrees de tirage d'un lot, les formes inattendues ecartees.

    Un manifeste ecrit avant `EPIC11-ARB-90` n'en porte aucun, et un document
    casse ne doit pas faire tomber un menu : le champ absent, mal type, ou
    porteur d'entrees qui ne sont pas des mappings rend une liste vide.
    """
    inventaire = lot.get(pdf_manifest.SHEETS_INVENTORY_FIELD)
    if not isinstance(inventaire, list):
        return []
    return [entree for entree in inventaire if isinstance(entree, Mapping)]


# ===========================================================================
# Le pied -- le dernier tirage produit (AC 3.4, AC 3.7)
# ===========================================================================

#: Le libelle du pied et ce qu'il dit quand le projet n'a rien imprime.
#: **Jamais une ligne vide, jamais un `0`** : un pied absent et un pied qui dit
#: « aucun » ne portent pas la meme information, et le premier se lit comme un
#: defaut d'affichage.
LIBELLE_DU_PIED = "Dernier tirage produit"
PIED_SANS_TIRAGE = "aucun tirage produit"

#: Largeur de la colonne du libelle du pied, **derivee de la maquette** : la
#: valeur du pied s'y aligne, et les deux lignes de suite s'alignent sur elle.
LARGEUR_DU_LIBELLE_DU_PIED = 28

#: Le separateur de la seconde ligne du pied : `26/08 · 16 pages · tirage 3`.
SEPARATEUR_DU_PIED = " · "

#: Le format de la date du pied, celui de la maquette : le jour et le mois, sans
#: l'heure. Ce n'est **pas** un appel a `projet_lecture.date_lisible`, et le
#: motif n'est pas la forme mais la SOURCE : ces fonctions-la traduisent un
#: horodatage **ISO du manifeste**, alors qu'un tirage n'en porte aucun et que
#: la date vient ici du systeme de fichiers.
#:
#: **A unifier a la liaison de la vague**, et c'est dit plutot que taire : le
#: lot D de la meme story pose `projet_lecture.date_courte`, qui rend la meme
#: forme depuis l'autre source. Deux redactions du meme format vivront donc
#: cote a cote le temps que les deux lots se rejoignent ; la fusion est une
#: ligne, et elle appartient a celui qui les voit tous les deux.
FORMAT_DE_LA_DATE = "%d/%m"

#: Le pluriel de « page » pour la seconde ligne du pied. `projet_lecture.PLURIELS`
#: ne porte que les trois mots de son bandeau ; celui-ci est a l'atelier Pdf.
PLURIEL_DES_PAGES = {False: "page", True: "pages"}

#: Ce que le pied dit du rang, dans les deux cas. **Le second n'est pas un repli
#: par defaut, c'est une lecture** : l'inventaire n'ecrit le rang qu'a partir du
#: second tirage, et son absence dit deja « tirage d'origine » -- exactement
#: comme le nom de fichier, qui ne porte aucun fragment a ce rang-la
#: (`EPIC11-ARB-88`).
#:
#: **Ecrire ici le numero du premier rang serait recopier une valeur qui vit au
#: coeur**, et le paquet `tui/` n'a meme pas le droit d'en nommer la constante :
#: la frontiere de la story 11.6 compte a **zero** le vocabulaire des rangs sur
#: tout le paquet, prose comprise. La seule facon de tenir les deux regles
#: ensemble est de ne pas avoir de rang a afficher quand le manifeste n'en
#: declare pas.
MENTION_DU_RANG = "tirage {rang}"
MENTION_DU_TIRAGE_D_ORIGINE = "tirage d'origine"


@dataclass(frozen=True)
class DernierTirage:
    """Ce que le pied de `E5-0` porte : un tirage, ou l'absence de tirage.

    `pages`, `gabarit` et `quand` valent `None` quand la source qui les porte ne
    repond pas -- un manifeste qu'on ne peut plus paginer, un lot sans gabarit
    declare, un fichier disparu du disque. Le segment correspondant **disparait**
    de la ligne : il vaut mieux une ligne plus courte qu'un chiffre invente.
    """

    nom: str | None = None
    lot_id: str | None = None
    rang: int | None = None
    pages: int | None = None
    gabarit: str | None = None
    quand: str | None = None

    @property
    def existe(self) -> bool:
        return self.nom is not None


def _rang_declare(entree: Mapping[str, Any]) -> int | None:
    """Le rang **lu** de l'entree d'inventaire, ou `None` -- jamais calcule.

    Le schema pose `minimum: 2` sur ce champ : un tirage d'origine n'en porte
    pas, et son absence le dit. On rend donc `None` plutot qu'un numero, et
    c'est le rendu qui choisit le mot -- voir :data:`MENTION_DU_RANG`. Un
    booleen est ecarte explicitement : `True` est un `int` pour Python, et
    afficherait « tirage True ».
    """
    rang = entree.get("version_rank")
    if isinstance(rang, bool) or not isinstance(rang, int):
        return None
    return rang


def _horodatage(dossier: Path | None, chemin_relatif: str) -> float | None:
    """La date de derniere ecriture du PDF, ou `None` s'il ne repond pas.

    Ne leve jamais : un tirage declare dont le fichier a ete renomme a la main
    est **le cas meme** que l'inventaire existe pour couvrir, et le menu doit
    s'ouvrir dessus.
    """
    if dossier is None:
        return None
    try:
        return (Path(dossier) / chemin_relatif).stat().st_mtime
    except OSError:
        return None


def _ordre_du_dernier(candidat: tuple) -> tuple:
    """La cle de tri qui designe « le dernier tirage produit ».

    Elle est **totale et deterministe**, et c'est ce qui compte : un tirage dont
    le fichier repond passe toujours devant un tirage disparu (premier terme),
    les fichiers presents se departagent par leur date (deuxieme), et deux
    dates egales par leur chemin (troisieme). Sans le troisieme terme, deux
    tirages ecrits dans la meme seconde -- ce qu'une fabrique de banc produit
    systematiquement -- rendraient un pied qui change d'une lecture a l'autre.
    """
    quand, chemin = candidat[0], candidat[1]
    return (quand is not None, quand or 0.0, chemin)


def _pages_du_tirage(manifeste: Mapping[str, Any] | None, lot_id: Any,
                     gabarit: Any) -> int | None:
    """Le nombre de pages du lot sous ce gabarit, **recalcule par le coeur**.

    `pdf_composition.page_count_du_lot` est le chemin de l'impression, et le
    cardinal d'emplacements vient du registre des gabarits : ni l'un ni l'autre
    n'est redige ici. Rend `None` des que la deduction n'est pas possible --
    lot inconnu, manifeste qu'on ne peut plus paginer, gabarit sorti du
    registre : le segment disparait alors de la ligne plutot que d'annoncer un
    cardinal faux.

    L'import est **differe**, comme partout ou ce paquet touche au coeur lourd :
    `pdf_composition` tire la chaine de composition entiere, et le menu des
    ateliers doit s'ouvrir sur un environnement partiel.
    """
    if manifeste is None or not isinstance(lot_id, str) or not lot_id:
        return None
    if not isinstance(gabarit, str) or not gabarit:
        return None
    from .. import page_templates, pdf_composition

    try:
        emplacements = page_templates.get_template(gabarit).frames_per_page
        return pdf_composition.page_count_du_lot(
            manifeste, lot_id, frames_per_page=emplacements)
    except Exception:                                      # noqa: BLE001
        # Le menu ne tombe pas sur un manifeste incoherent : il dit ce qu'il
        # sait. Les refus du coeur sont nombreux et de familles differentes
        # (`UnknownTemplateError`, `LotContentError`, et ce que la relecture de
        # selection leve) ; les nommer un par un ici ferait une seconde table de
        # refus a maintenir a cote de celle du coeur.
        return None


def dernier_tirage(manifeste: Mapping[str, Any] | None,
                   dossier: Path | str | None = None) -> DernierTirage:
    """Le tirage que le pied de `E5-0` nomme, ou l'absence de tirage.

    Balaie **tous** les lots et **toutes** leurs entrees d'inventaire : le
    dernier tirage d'un projet n'est ni celui du premier lot -- mutant « rendre
    le premier » -- ni celui du dernier -- l'ordre de `lots[]` est celui de
    **premiere creation**, jamais un ordre d'impression.

    Le tri est celui de :func:`_ordre_du_dernier`, et il repose sur la date du
    fichier : l'inventaire est **trie par chemin** a l'ecriture, deliberement,
    « si bien qu'un ordre d'insertion porterait l'ordre chronologique des
    impressions » -- c'est-a-dire un signal d'horloge dans un document dont
    l'idempotence est verifiee octet a octet. Prendre `sheets_pdfs[-1]` serait
    donc lire un ordre alphabetique pour une chronologie.
    """
    racine = Path(dossier) if dossier is not None else None
    candidats: list[tuple] = []
    for lot in projet_lecture._lots(manifeste):
        for entree in _inventaire_du_lot(lot):
            chemin = entree.get(pdf_manifest.SHEETS_INVENTORY_KEY)
            if not isinstance(chemin, str) or not chemin:
                continue
            candidats.append((_horodatage(racine, chemin), chemin,
                              lot.get("lot_id"), lot.get("template_id"),
                              _rang_declare(entree)))
    if not candidats:
        return DernierTirage()
    quand, chemin, lot_id, gabarit, rang = max(candidats,
                                               key=_ordre_du_dernier)
    return DernierTirage(
        nom=Path(chemin).name,
        lot_id=lot_id if isinstance(lot_id, str) else None,
        rang=rang,
        pages=_pages_du_tirage(manifeste, lot_id, gabarit),
        gabarit=gabarit if isinstance(gabarit, str) and gabarit else None,
        quand=(datetime.fromtimestamp(quand).strftime(FORMAT_DE_LA_DATE)
               if quand is not None else None),
    )


def lignes_du_pied(tirage: DernierTirage) -> list[str]:
    """Les une a trois lignes du pied, telles que la maquette les dessine.

    Une ligne de libelle et sa valeur, puis les lignes de suite alignees sur la
    colonne de la valeur. Aucune n'est vide : un pied qui n'a rien a dire dit
    `aucun tirage produit`, et un segment qu'on ne sait pas remplir disparait
    au lieu de laisser un blanc.
    """
    colonne = len(INDENT_DU_CURSEUR) + 2 + LARGEUR_DU_LIBELLE_DU_PIED
    tete = (INDENT_DU_CURSEUR + "  "
            + f"{LIBELLE_DU_PIED:<{LARGEUR_DU_LIBELLE_DU_PIED}}")
    if not tirage.existe:
        return [tete + PIED_SANS_TIRAGE]
    lignes = [tete + str(tirage.nom)]
    mesures = []
    if tirage.quand:
        mesures.append(tirage.quand)
    if tirage.pages is not None:
        mesures.append(f"{tirage.pages} "
                       f"{PLURIEL_DES_PAGES[tirage.pages > 1]}")
    mesures.append(MENTION_DU_TIRAGE_D_ORIGINE if tirage.rang is None
                   else MENTION_DU_RANG.format(rang=tirage.rang))
    lignes.append(" " * colonne + SEPARATEUR_DU_PIED.join(mesures))
    if tirage.gabarit:
        lignes.append(" " * colonne + tirage.gabarit)
    return lignes


# ===========================================================================
# L'ecran
# ===========================================================================

class EcranPdfMenu(Palier):
    """`E5-0` -- deux entrees, et le pied du dernier tirage produit.

    `entrer` est **injecte**, comme il l'est au menu du Scan : cet ecran ne sait
    pas ce que « composer des planches » veut dire, et c'est le parcours qui le
    lui dit. Sans cette couture, le menu dependrait des modules des lots voisins,
    et les lots de cette story ne pourraient plus etre developpes en parallele.

    **Le manifeste est lu une fois par visite**, dans :meth:`charger`, et les
    deux mesures du bandeau comme le pied s'en derivent (AC 3.5).
    """

    titre = "Pdf"
    raccourcis = RACCOURCIS_PDF_MENU

    def __init__(self, dossier=None,
                 entrer: Callable[[EntreeDeMenu], None] | None = None) -> None:
        super().__init__()
        self.dossier = Path(dossier) if dossier is not None else None
        self._entrer = entrer
        self.curseur = 0
        self.entrees: tuple[EntreeDeMenu, ...] = ENTREES_DU_MENU
        self.manifeste: Mapping[str, Any] | None = None
        self.charger()

    # -- lecture ------------------------------------------------------------

    def charger(self) -> None:
        """Relire le manifeste. **Une seule lecture pour les deux calculs.**"""
        self.manifeste = (projet_lecture.lire_manifeste(self.dossier)
                          if self.dossier is not None else None)

    def reprendre(self) -> None:
        """Revenir sur le menu **relit le manifeste** avant de le redessiner.

        Le palier survit a la visite : sans cette relecture, revenir d'une
        generation laisserait le bandeau a `3 tirages produits` et le pied sur
        l'avant-dernier. C'est le defaut `V2-M2`, deja paye sur le menu des
        ateliers.
        """
        self.charger()
        self.rafraichir()

    @property
    def comptes(self) -> ComptesDuPdf:
        return compter(self.manifeste)

    @property
    def tirage(self) -> DernierTirage:
        return dernier_tirage(self.manifeste, self.dossier)

    def bandeau(self, largeur: int | None = None) -> str:
        """Le bandeau, avec `5 lots · 3 tirages produits` a droite.

        Les compteurs sont poses sur l'**objet** du contexte, ce qui les fait
        passer par l'elision de `Contexte.rendu` : quand les deux cotes ne
        tiennent pas ensemble, c'est le nom du projet qui est abrege et
        **jamais** les compteurs.
        """
        from .coque import Contexte

        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre, self.comptes.rendu())
        return contexte.rendu(
            self.app.size.width if largeur is None else largeur,
            getattr(self.app, "ascii_seul", False))

    def lignes_d_entree(self, rang: int, utile: int) -> list[str]:
        """Une entree : son nom en colonne, puis sa phrase repliee a droite.

        **La phrase est repliee, jamais abregee** : elle dit ce que l'entree
        fait, et une phrase coupee par la fin perdrait precisement la moitie qui
        distingue les deux entrees.
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
                # derniere : posee avant l'entree plutot qu'apres la precedente,
                # pour qu'une troisieme entree un jour ne laisse pas la
                # separation au mauvais endroit.
                corps.append("")
            corps += self.lignes_d_entree(rang, utile)
        corps += ["", filet(utile, ascii_seul=self.app.ascii_seul), ""]
        corps += lignes_du_pied(self.tirage)
        return corps

    def rangs_du_curseur(self) -> list[int]:
        """Les rangs de **toute** l'entree courante, pas seulement sa premiere.

        `EPIC11-ARB-125` : une ligne de continuation ne porte, par construction,
        aucun glyphe -- aucune reconnaissance par motif ne peut la trouver, il
        faut la **donner**. C'est ce que `jetons.peindre` attend dans
        `lignes_du_curseur`, et c'est ce que la maquette declare par
        `hauteur_du_curseur=2`.
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
        self._corps = Static("", id="corps-pdf-menu")
        return [Vertical(self._corps, id="centre-pdf-menu")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            lignes_du_curseur=self.rangs_du_curseur()))
        # `EPIC11-ARB-56` : la ligne d'etat ne porte **aucune** touche, aucun
        # conseil d'usage, aucun motif de conception. Ce menu n'a rien a
        # mesurer, elle reste donc vide.
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
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **Fleche seule** (`EPIC11-ARB-45`, `-126`, verbatim d'Egan : « Fleche
        seule ! C'est uniquement dans les listes a cocher qu'on trouve les
        deux ») : ce menu n'est pas une liste a cocher, aucune lettre n'y
        navigue.
        """
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

        Une entree non construite nomme ce qui manque et quand il arrive ; une
        entree construite dont le rappel n'est pas cable fait de meme, plutot
        que de consommer la touche sur rien.
        """
        if not entree.construite:
            self.app.descendre(EcranPasEncore(entree.nom, entree.quand))
            return
        if self._entrer is None:
            self.app.descendre(EcranPasEncore(entree.nom, QUAND_L_ATELIER_PDF))
            return
        self._entrer(entree)


def ouvrir_l_atelier_pdf(app, dossier_projet, **reglages) -> EcranPdfMenu:
    """Ce que l'entree *Pdf* du menu des ateliers ouvre.

    C'est le rappel que `ChaineReelle` injecte, et sa signature est celle que
    `ChaineReelle.atelier_pdf` appelle : `(app, dossier)`. Tout le reste est du
    reglage que seuls les bancs fournissent -- meme forme que
    `atelier_scan_parcours.ouvrir_l_atelier_scan`.

    **Le parcours est monte ici depuis le lot de cablage** : les deux entrees du
    menu menent desormais a leurs ecrans, et non plus a l'ecran « pas encore »
    que ce module gardait tant que rien ne les reliait. L'import est **differe**
    au corps de la fonction, et pour une raison de structure plutot que de gout :
    `atelier_pdf_parcours` importe ce module -- il monte :class:`EcranPdfMenu` --,
    donc un import de tete refermerait le cycle. C'est l'idiome du depot, employe
    partout ou deux modules se tiennent l'un l'autre.
    """
    from .atelier_pdf_parcours import ParcoursPdf

    return ParcoursPdf(app, dossier_projet, **reglages).ouvrir()


def ouvrir_la_composition_des_planches(app, dossier_projet, **reglages):
    """L'atelier Pdf ouvert **directement sur sa liste de lots** (`E5-1`).

    C'est ce que « Composer les planches de ces lots » demande depuis l'ecran
    de resultat de l'Extraction (`MQ-4`, audit du 2026-09-06) : le libelle
    promet des planches *de ces lots*, et rendre le menu de l'atelier ferait
    de `E5-0` « un ecran a franchir pour rien » -- le motif exact qu'invoque
    `EPIC11-ARB-28` pour refuser un menu aux ateliers a une seule entree.

    **Le menu est monte quand meme, en dessous**, et ce n'est pas un detail :
    c'est lui la page d'ouverture de l'atelier Pdf. Sans lui, `Echap` depuis la
    liste des lots sauterait l'atelier entier pour retomber au menu des
    ateliers, et `remonter_a_l_ouverture_de_l_atelier` -- que les suites de
    `E5-5` appellent -- n'aurait plus de station ou s'arreter.

    Le montage passe par le **meme** :class:`~.atelier_pdf_parcours.ParcoursPdf`
    que :func:`ouvrir_l_atelier_pdf`, et non par un second cablage : deux
    parcours pour un atelier divergeraient au premier reglage ajoute.
    """
    from .atelier_pdf_parcours import ParcoursPdf

    parcours = ParcoursPdf(app, dossier_projet, **reglages)
    parcours.ouvrir()
    return parcours.choisir_les_lots()


__all__ = [
    "CLE_DE_LA_COMPOSITION",
    "CLE_DE_LA_MIRE",
    "ENTREES_DU_MENU",
    "FORMAT_DE_LA_DATE",
    "LARGEUR_DU_LIBELLE_DU_PIED",
    "LIBELLE_DU_PIED",
    "MENTION_DU_RANG",
    "MENTION_DU_TIRAGE_D_ORIGINE",
    "PARTICIPE_DES_TIRAGES",
    "PIED_SANS_TIRAGE",
    "PLURIEL_DES_PAGES",
    "QUAND_L_ATELIER_PDF",
    "RACCOURCIS_PDF_MENU",
    "SEPARATEUR_DU_PIED",
    "TITRE_DU_MENU",
    "ComptesDuPdf",
    "DernierTirage",
    "EcranPdfMenu",
    "compter",
    "dernier_tirage",
    "lignes_du_pied",
    "ouvrir_l_atelier_pdf",
    "ouvrir_la_composition_des_planches",
]
