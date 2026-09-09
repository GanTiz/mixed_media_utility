# -*- coding: utf-8 -*-
"""`E5-2` / `E5-2b` -- les reglages des planches (story 11.7, lot E, AC 5).

**UNE seule liste verticale** (`EPIC11-ARB-173`). Les deux rangees « proposes
d'office » / « et aussi » n'existent plus, le bloc « Ce qui en decoule » non
plus, et le champ de compression de gamut non plus : la surface de dessin et
les pages vivent desormais **sur chaque entree**, pour toutes les mises en page
de l'orientation et non pour la seule retenue. C'est ce qui rend le glyphe de
choix optimal lisible au lieu d'etre a croire.

**Ce module ne compare AUCUNE geometrie.** La domination -- « surface >= ET
pages <=, avec au moins une inegalite stricte » -- est calculee par
`page_templates.bilan_de_domination` (lot B8), appelee ici et jamais rejouee :
c'est une regle de vocabulaire de geometrie, pas une regle d'ecran, et une
seconde redaction cote TUI melangerait les geometries v1 et v2 exactement comme
le 2026-09-01. Une frontiere a l'AST le mesure.

**Ce module ne calcule AUCUNE distance entre cardinaux** non plus. Le repli
d'orientation vit dans `page_templates.replier_le_cardinal`
(`EPIC11-ARB-179`) : l'ecran lui donne l'orientation d'arrivee et le cardinal
courant, et affiche ce qu'il rend.

**Le glyphe et sa couleur ne font qu'UN jeton** (`DESIGN.md` §6) : `●` vaut
`state-complete` -- le vert -- et son repli ASCII est `*` -- l'asterisque
qu'Egan demande. Ecrire un `*` litteral en UTF-8 ferait deux fautes d'un coup :
un glyphe hors table, et une collision avec le repli de `●`. Le glyphe est
**colle au chiffre** du cardinal (Egan, 2026-09-02 : « une asterisque
directement a cote du chiffre du nombre de frames, et la couleur. Pas une
pastille tout a droite. ») ; colle, il n'ouvre plus de colonne, donc
`jetons.jeton_d_etat` ne peut plus le voir et la couleur passe par l'etat
**donne** (`jetons.peindre(etats=...)`, `EPIC11-ARB-71`).

**`⏎` SELECTIONNE puis saute hors du choix** (Egan, 2026-09-02, verbatim :
« appuyer sur Entree "saute" ensuite en dehors du choix pour valider »). C'est
un bouton `Valider` qui sort du formulaire, et la ligne de raccourcis le dit --
elle est contextuelle par charte (`DESIGN.md` §4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import page_templates, pdf_composition
from . import jetons, projet_lecture
from .atelier_extraction import (Composition, _application_montee,
                                 filet_titre, ligne_de_titre)
from .coque import EcranPasEncore, ObjetTravaille, Palier

# ---------------------------------------------------------------------------
# Les textes de `E5-2` / `E5-2b`, verbatim des maquettes validees
# ---------------------------------------------------------------------------

#: Le titre de la zone centrale.
TITRE_DES_REGLAGES = "Réglages des planches"

#: Le filet qui ouvre la liste unique.
FILET_DES_CARDINAUX = "Frames par page"

LIBELLE_ORIENTATION = "Orientation"
LIBELLE_FORMAT_DPI = "Format · DPI"

#: `EPIC11-ARB-34`. Le libelle est mesure par une frontiere negative : le
#: libelle qu'il remplace -- celui que le coeur emploie encore pour ses presets
#: -- doit rendre **zero** occurrence dans `tui/`, et ce fichier n'a donc pas le
#: droit de l'ecrire, meme pour en parler.
LIBELLE_MARGE = "Marge de travail"

#: Le bouton, dernier champ du formulaire. Il se dessine **comme un champ** --
#: rien a gauche, la valeur a la colonne des valeurs, le glyphe `>` au focus
#: (`DESIGN.md` §7.3) -- et **sans seconde colonne** (Egan, 2026-09-02 :
#: « enlever la deuxieme colonne "compose les planches ..." a cote de valider »).
LIBELLE_VALIDER = "Valider"

#: La legende du glyphe. **Trois mots, et c'est tout** (Egan, 2026-09-02,
#: verbatim : « La legende : choix optimal (c'est tout). »). Elle disait
#: « non dominé : aucune autre ne fait mieux en surface ET en pages » -- la
#: definition de la mesure, pas ce que le glyphe veut dire pour celui qui
#: choisit. Les deux criteres restent chiffres sur chaque ligne de la liste.
LEGENDE_CHOIX_OPTIMAL = "choix optimal"

#: L'etat que porte une mise en page **non dominee**. Un nom de la table de
#: `jetons`, jamais un dessin : c'est ce qui donne le vert ET l'asterisque.
ETAT_CHOIX_OPTIMAL = "complete"

#: L'etat du constat de repli, en ligne d'etat.
ETAT_DU_REPLI = "substitute"

#: La ligne de raccourcis quand le focus est **dans un champ de choix**
#: (`E5-2b`). `⏎` y retient la valeur et saute sur `Valider`.
#:
#: **C'est la plus large des treize lignes de l'atelier, et elle est EXACTEMENT
#: a la borne** : 76 colonnes en repli ASCII pour une zone utile de 76
#: (`jetons.largeur_utile()`). Une seule lettre de plus et la ligne ne rougit
#: nulle part -- elle passe sous `jetons.ajuster`, qui l'abrege : le rendu
#: devient `... Echap retour  F1 a...`, c'est-a-dire que **l'annonce de la
#: touche d'aide est mutilee**, et seulement en `--ascii`. Le regime UTF-8, lui,
#: reste a 71 et ne dit rien. Un ajout de libelle ici se mesure donc AVANT
#: d'etre ecrit -- ce que `test_frontieres_et_grille_pdf.py` fait desormais a
#: chaque course, en recalculant les deux largeurs et en les confrontant a la
#: ligne `MESURE:` ci-dessous.
#:
#: MESURE: 71/76
RACCOURCIS_CHOIX = ("⏎ sélectionner et Valider  Tab champ  ↑↓ choisir  "
                    "Échap retour  F1 aide")

#: La ligne de raccourcis quand le focus est **sur le bouton** (`E5-2`). C'est
#: le seul endroit ou `⏎` valide, et `↑↓` n'y choisit rien : il n'y a rien a
#: choisir sur un bouton, donc les fleches y naviguent entre les champs. La
#: ligne le dit -- « naviguer » contre « choisir » --, ce qui est exactement ce
#: qu'une ligne de raccourcis contextuelle sert a faire.
#: MESURE: 56/61
RACCOURCIS_VALIDER = ("⏎ valider  Tab champ  ↑↓ naviguer  "
                      "Échap retour  F1 aide")

#: Le constat que la ligne d'etat porte apres un basculement qui a repli.
#:
#: **Sa forme est celle de la maquette VALIDEE, et elle a ete remise** (Egan,
#: 2026-09-02, verbatim : « Non, on laisse la ligne du bas avec les infos. Pas
#: besoin de nouvelle validation pour ca. »). Une redaction « cardinal demande /
#: retenu / motif » avait ete proposee et **refusee** : `EPIC11-ARB-56` veut de
#: la ligne d'etat des **constats**, pas des explications de mecanisme.
#:
#: La clause « meme surface qu'a 8 f » que la maquette portait avant
#: `EPIC11-ARB-179` **tombe d'elle-meme** : elle nommait `8` pour justifier un
#: repli vers `4`, et le repli qui monte retient `8`. La garder ecrirait deux
#: fois le meme cardinal dans la meme phrase.
MOTIF_DU_REPLI = "{demande} f/page n'existe pas en {orientation} — ramené à {retenu}"

#: La ligne d'etat de l'ecran au repos : ce que la passe imprimerait telle
#: qu'elle est reglee. Les pages sont **par lot**, jamais un total repagine.
MOTIF_DE_LA_MESURE = ("{pages} pages — {par_lot} · {frames} frames sur "
                      "{emplacements} emplacements")

#: Le conseil qui traverse les orientations (`EPIC11-ARB-154`, note 11 d'Egan).
#: Il reste **necessaire malgre la liste unique** : le glyphe se calcule sur le
#: PRODUIT des deux orientations alors que la liste n'en montre qu'une, donc une
#: entree peut etre sans glyphe a cause d'une combinaison de l'AUTRE
#: orientation -- et cette ligne est le seul endroit qui la nomme.
MOTIF_DU_CONSEIL = "{glyphe} {cardinal} frames {orientation} est plus optimal :"
MOTIF_SURFACE_SUPERIEURE = "surface de dessin supérieure"
MENTION_GAIN_DE_PAGES = " et gain de pages"

#: Ce que `Valider` demande, quand l'ecran qui le sert n'existe pas encore.
#: **Une touche qui ne fait rien et ne dit rien est indistinguable d'un clavier
#: casse** : la garde structurelle des rappels
#: (`tests/unit/tui/test_rappels_cables.py`) existe pour attraper un
#: `if ... is not None` sans branche `else`.
CE_QUI_MANQUE_APRES_LES_REGLAGES = "Confirmer et composer les planches"
QUAND_LA_CONFIRMATION = "la confirmation de l'atelier Pdf"

# ---------------------------------------------------------------------------
# La grille des maquettes. Ces colonnes sont celles du DESSIN valide.
# ---------------------------------------------------------------------------

#: Indentation des lignes de formulaire et des entrees de la liste.
_INDENT = 5
#: Colonne des valeurs -- la meme pour les trois champs **et pour le bouton**,
#: qui se dessine comme un champ.
_COLONNE_DE_LA_VALEUR = 26
#: Colonne de la mention qui suit la valeur de la marge (`0 · 2 · 5 mm`).
_COLONNE_DE_LA_MENTION = 39
#: Le blanc qui separe les deux orientations sur leur ligne.
_ECART_ENTRE_ORIENTATIONS = 6
#: Retrait de la seconde ligne du conseil, sous la premiere.
_INDENT_DU_CONSEIL = 7

#: L'ordre des deux orientations **sur la ligne**, celui des maquettes. Ce n'est
#: pas l'ordre de `page_templates.ORIENTATIONS` (portrait d'abord), et c'est
#: assume : le dessin est valide. Un test mesure que l'**ensemble** affiche est
#: exactement `set(page_templates.ORIENTATIONS)`, ce qui attrape un oubli sans
#: figer l'ordre du coeur.
ORDRE_DES_ORIENTATIONS = (page_templates.ORIENTATION_PAYSAGE,
                          page_templates.ORIENTATION_PORTRAIT)

#: Le separateur des presets de marge, dans la mention de droite.
_SEPARATEUR_DES_MARGES = " · "
#: L'unite de la mention des marges.
_UNITE_DES_MARGES = " mm"
#: Le separateur des lots en ligne d'etat.
_SEPARATEUR_DES_LOTS = " · "

# ---------------------------------------------------------------------------
# Les champs, et l'ordre ou `Tab` les parcourt
# ---------------------------------------------------------------------------

CHAMP_ORIENTATION = "orientation"
CHAMP_MARGE = "marge"
CHAMP_CARDINAL = "cardinal"
CHAMP_VALIDER = "valider"

#: **`Format · DPI` n'est PAS un champ.** `page_templates.PAGE_FORMATS` n'en
#: porte qu'un seul, et un champ dont une seule valeur existe n'est pas un
#: reglage -- c'est exactement l'argument par lequel le champ de gamut est
#: tombe (AC 5.9). La ligne reste **affichee**, parce que ce qu'un tirage
#: portera se lit ici avant la confirmation.
CHAMPS = (CHAMP_ORIENTATION, CHAMP_MARGE, CHAMP_CARDINAL, CHAMP_VALIDER)

#: Les champs ou `⏎` retient une valeur puis saute sur le bouton.
CHAMPS_DE_CHOIX = (CHAMP_ORIENTATION, CHAMP_MARGE, CHAMP_CARDINAL)


def _replie(texte: str, ascii_seul: bool = False) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_la_colonne(tete: str, colonne: int) -> str:
    """Completer ``tete`` de blancs jusqu'a ``colonne``, mesuree en COLONNES.

    Jamais `len()` : un ideogramme occupe deux colonnes, et toute la grille
    partirait avec lui.
    """
    return tete + " " * max(1, colonne - jetons.colonnes(tete))


def _tete_de_champ(libelle: str, au_focus: bool, ascii_seul: bool) -> str:
    """Le libelle d'un champ, suivi du glyphe `>` **quand il a le focus**.

    `DESIGN.md` §7.3, verbatim : « Le champ au focus porte `>` ; les autres, un
    espace. » La regle est **generale au formulaire** -- son propre exemple la
    montre sur un champ a puces (`Profondeur  (•) 16 bits  ( ) 8 bits`), pas
    seulement sur une saisie libre.

    **Elle est ecrite ICI et une seule fois**, pour les quatre champs de
    l'ecran. C'est ce qui manquait : le glyphe etait pose a la main dans
    :meth:`ligne_du_bouton` et nulle part ailleurs, si bien que deux champs sur
    quatre ne montraient RIEN. Un operateur au clavier ne pouvait alors pas
    distinguer « je regle l'orientation » de « je regle la marge » -- les deux
    ecrans etaient identiques au caractere pres, mesure le 2026-09-06, et `↑`
    n'y disait pas ce qu'il allait changer.

    **Aucun arbitrage n'est pris ici, et c'est voulu** : la regle existe deja a
    la charte et six des sept formulaires du produit l'appliquent -- celui-ci
    etait le seul a ne l'appliquer qu'a son bouton. Il n'y avait donc rien a
    decider, seulement un manque a combler.

    Le glyphe **ouvre sa colonne** : la tete non focalisee est completee de
    blancs jusqu'a la meme colonne, pour que les valeurs restent alignees quand
    le focus se deplace. Meme geste que
    `atelier_exports_reglages.ligne_de_champ`, qui est le voisin correct.
    """
    tete = " " * _INDENT + _replie(libelle, ascii_seul) if libelle else ""
    if not au_focus:
        return _a_la_colonne(tete, _COLONNE_DE_LA_VALEUR)
    glyphe = jetons.glyphes(ascii_seul)["invite"]
    return _a_la_colonne(tete, _COLONNE_DE_LA_VALEUR - 2) + f"{glyphe} "


# ---------------------------------------------------------------------------
# Les lots de la passe
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LotAPlanches:
    """Un lot coche a `E5-1`, tel que les reglages ont besoin de le connaitre.

    Deux champs et pas un de plus : son identifiant, que la ligne d'etat nomme,
    et son cardinal de frames, qui pagine. Rien de ce que cet ecran affiche ne
    demande davantage, et un champ que personne ne lit est une surface morte.
    """

    lot_id: str
    frames: int


# ---------------------------------------------------------------------------
# Le modele -- pur, sans `textual`, sans ecriture
# ---------------------------------------------------------------------------

@dataclass
class ReglagesDesPlanches:
    """Le modele de `E5-2` : une orientation, une marge, un cardinal.

    **Modele pur**, comme `panneau.py` et `explorateur.py` : aucune dependance a
    `textual`, aucune ecriture. C'est ce qui rend mesurables sans terminal les
    deux appariements a risque de cet ecran -- la ligne rendue contre la mise en
    page qu'elle decrit, et le cardinal retenu apres un basculement contre celui
    que le coeur offre.

    **L'etat d'ouverture est celui du COEUR, jamais un nombre recopie** (AC
    5.1) : `pdf_composition.resolve_orientation(None)` pour l'orientation,
    `page_templates.DEFAULT_FRAMES_PER_PAGE` pour le cardinal,
    `page_templates.DEFAULT_MARGIN_PRESET` pour la marge. Les maquettes
    dessinent un etat **apres reglage** (`paysage / 6 f` et `portrait / 8 f`),
    pas l'etat d'ouverture ; c'est un instant, pas un defaut.
    """

    #: Les lots coches, dans l'ordre du plan. Le cardinal de chacun pagine
    #: **separement** : le papier ne se partage pas entre deux lots.
    lots: tuple[LotAPlanches, ...] = ()
    orientation: str = field(
        default_factory=lambda: pdf_composition.resolve_orientation(None))
    frames_par_page: int = page_templates.DEFAULT_FRAMES_PER_PAGE
    marge: str = page_templates.DEFAULT_MARGIN_PRESET
    champ: str = CHAMP_ORIENTATION
    #: Le dernier repli de cardinal, tant qu'il n'a pas ete oublie. `None`
    #: quand le basculement n'a rien eu a replier -- et il ne se DEDUIT pas
    #: d'une comparaison faite ici : c'est le coeur qui repond.
    repli: page_templates.RepliDeCardinal | None = None

    # -- ce que le coeur mesure ---------------------------------------------

    def bilan(self) -> page_templates.BilanDeDomination:
        """Le produit des deux orientations, mesure et compare par le COEUR.

        Recalcule a chaque appel plutot que mis en cache : la marge en fait
        partie, et un cache invalide au mauvais moment afficherait les surfaces
        d'une autre marge. La mesure est pure et ne touche aucun disque.
        """
        return page_templates.bilan_de_domination(
            self.frames_par_lot(), margin_preset=self.marge)

    def frames_par_lot(self) -> tuple[int, ...]:
        return tuple(lot.frames for lot in self.lots)

    def mises_en_page(self) -> tuple[page_templates.MiseEnPageMesuree, ...]:
        """La liste de l'ecran : **le vocabulaire ENTIER** de l'orientation.

        `EPIC11-ARB-154` tient a l'identique -- « on guide, on n'interdit pas ».
        Aucun cardinal n'est retire de la liste ; le glyphe dit la domination,
        il ne la sanctionne pas.
        """
        return self.bilan().de_l_orientation(self.orientation)

    def cardinaux(self) -> tuple[int, ...]:
        return tuple(mise.frames_per_page for mise in self.mises_en_page())

    def retenue(self) -> page_templates.MiseEnPageMesuree:
        """La mise en page retenue, mesuree."""
        return self.bilan().de(self.orientation, self.frames_par_page)

    def est_optimale(self, cardinal: int) -> bool:
        """Cette mise en page porte-t-elle le glyphe ? **Le coeur repond.**"""
        return not self.bilan().est_dominee(self.orientation, cardinal)

    def meilleure_que_la_retenue(self
                                 ) -> page_templates.MiseEnPageMesuree | None:
        """La dominante a conseiller, ou ``None`` quand il n'y en a aucune.

        **Ce n'est pas un calcul de domination** : les dominantes sont celles
        que le coeur a rendues, et cette methode n'en retient qu'**une** -- « on
        affiche UNIQUEMENT le conseil le plus optimal » (Egan). Le depart se
        fait a la plus grande surface, puis au moins de pages.
        """
        dominantes = self.bilan().dominants_de(
            self.orientation, self.frames_par_page)
        if not dominantes:
            return None
        return max(dominantes, key=lambda mise: (mise.surface_mm2, -mise.pages))

    # -- le rang du curseur --------------------------------------------------

    def rang_du_cardinal(self) -> int:
        """Le rang du cardinal retenu dans la liste.

        **Le curseur et la selection ne font qu'un** sur cet ecran, et les deux
        maquettes le montrent : `E5-2b` pose `▸` et `(•)` sur la meme ligne. Une
        selection differee -- un curseur qu'on deplace sans retenir -- serait un
        etat que le dessin ne sait pas montrer, donc un etat invisible.
        """
        cardinaux = self.cardinaux()
        return cardinaux.index(self.frames_par_page)

    # -- ecriture ------------------------------------------------------------

    def oublier_le_repli(self) -> None:
        """Le constat de repli ne survit pas au geste SUIVANT.

        Il survit en revanche a tous les redessins qui les separent : c'est la
        difference entre un `poser_etat` isole -- que le dessin suivant efface
        -- et un etat porte par le modele.
        """
        self.repli = None

    def poser_l_orientation(self, orientation: str) -> bool:
        """Basculer, et **replier le cardinal par le coeur** si besoin.

        C'est le **seul** declencheur de repli du produit (`EPIC11-ARB-179`) :
        par la ligne de commande, orientation et cardinal arrivent ensemble, et
        un couple hors vocabulaire y est refuse.
        """
        if orientation == self.orientation:
            return False
        self.orientation = orientation
        repli = page_templates.replier_le_cardinal(
            orientation, self.frames_par_page)
        self.frames_par_page = repli.retenu
        self.repli = repli if repli.a_replie else None
        return True

    def poser_le_cardinal(self, cardinal: int) -> bool:
        """Retenir une mise en page de la liste courante.

        Un cardinal hors du vocabulaire de l'orientation n'entre pas : l'ecran
        « ne laisse jamais a l'ecran un couple que le coeur refuserait »
        (`EPIC11-ARB-17`).
        """
        if cardinal not in self.cardinaux() or cardinal == self.frames_par_page:
            return False
        self.frames_par_page = cardinal
        return True

    def poser_la_marge(self, marge: str) -> bool:
        if marge not in page_templates.MARGIN_PRESETS_MM or marge == self.marge:
            return False
        self.marge = marge
        return True

    def choisir(self, pas: int) -> bool:
        """`↑` / `↓` dans le champ au focus : la valeur voisine, **retenue**.

        Bornee et non circulaire pour la liste des cardinaux : elle porte de
        cinq a six entrees et un enroulement y ferait passer de `1` a `8` par
        une seule pression, c'est-a-dire du plus de papier au moins de papier
        sans que rien ne l'ait montre.
        """
        if self.champ == CHAMP_ORIENTATION:
            return self._voisin(ORDRE_DES_ORIENTATIONS, self.orientation, pas,
                                self.poser_l_orientation)
        if self.champ == CHAMP_MARGE:
            return self._voisin(tuple(page_templates.MARGIN_PRESETS_MM),
                                self.marge, pas, self.poser_la_marge)
        if self.champ == CHAMP_CARDINAL:
            return self._voisin(self.cardinaux(), self.frames_par_page, pas,
                                self.poser_le_cardinal)
        return self.avancer(pas)

    @staticmethod
    def _voisin(valeurs: Sequence, courante, pas: int,
                poser: Callable[..., bool]) -> bool:
        rang = valeurs.index(courante)
        vise = rang + pas
        if not 0 <= vise < len(valeurs):
            return False
        return poser(valeurs[vise])

    def avancer(self, pas: int = 1) -> bool:
        """Le champ suivant, en boucle. C'est `Tab`, et `↑↓` sur le bouton."""
        self.champ = CHAMPS[(CHAMPS.index(self.champ) + pas) % len(CHAMPS)]
        return True

    def entrer(self) -> bool:
        """`⏎` : dans un choix, **retenir puis sauter sur `Valider`**.

        Egan, 2026-09-02, verbatim : « appuyer sur Entree "saute" ensuite en
        dehors du choix pour valider ». La valeur est deja retenue -- les
        fleches la retiennent -- donc `⏎` ne fait ici que la **confirmer** et
        deplacer le focus. Sur le bouton, il valide : c'est le seul endroit.

        Rend ``True`` quand le formulaire est valide, ``False`` sinon.
        """
        if self.champ == CHAMP_VALIDER:
            return True
        self.champ = CHAMP_VALIDER
        return False

    # -- rendu ---------------------------------------------------------------

    def raccourcis(self) -> str:
        """La ligne de raccourcis, **contextuelle** (`DESIGN.md` §4)."""
        return (RACCOURCIS_VALIDER if self.champ == CHAMP_VALIDER
                else RACCOURCIS_CHOIX)

    def ligne_de_l_orientation(self, ascii_seul: bool = False) -> str:
        glyphes = jetons.glyphes(ascii_seul)
        puces = []
        for orientation in ORDRE_DES_ORIENTATIONS:
            puce = glyphes["exclusif-retenu" if orientation == self.orientation
                           else "exclusif-libre"]
            puces.append(f"{puce} {orientation}")
        tete = _tete_de_champ(LIBELLE_ORIENTATION,
                              self.champ == CHAMP_ORIENTATION, ascii_seul)
        return tete + (" " * _ECART_ENTRE_ORIENTATIONS).join(puces)

    def ligne_du_format(self, ascii_seul: bool = False) -> str:
        """`A4 · 600` -- le format et le dpi, **lus des constantes du coeur**."""
        valeur = (f"{page_templates.DEFAULT_PAGE_FORMAT} · "
                  f"{pdf_composition.RENDER_DPI_DEFAULT}")
        tete = _a_la_colonne(" " * _INDENT + _replie(LIBELLE_FORMAT_DPI,
                                                    ascii_seul),
                             _COLONNE_DE_LA_VALEUR)
        return tete + _replie(valeur, ascii_seul)

    def ligne_de_la_marge(self, ascii_seul: bool = False) -> str:
        """La marge retenue, et les presets **lus de `MARGIN_PRESETS_MM`**."""
        mention = (_SEPARATEUR_DES_MARGES.join(page_templates.MARGIN_PRESETS_MM)
                   + _UNITE_DES_MARGES)
        tete = _tete_de_champ(LIBELLE_MARGE, self.champ == CHAMP_MARGE,
                              ascii_seul)
        return _replie(_a_la_colonne(tete + self.marge, _COLONNE_DE_LA_MENTION)
                       + mention, ascii_seul)

    def ligne_de_cardinal(self, mise: page_templates.MiseEnPageMesuree,
                          ascii_seul: bool = False) -> str:
        """Une ENTREE de la liste unique.

        Elle porte les deux criteres de la domination cote a cote -- surface par
        frame et pages -- pour que le glyphe se LISE au lieu de se croire : un
        operateur qui voit `311,5 cm² · 164 pages` en face de `43,9 cm² ·
        28 pages` n'a pas besoin qu'on lui dise laquelle domine l'autre.
        """
        glyphes = jetons.glyphes(ascii_seul)
        curseur = (self.champ == CHAMP_CARDINAL
                   and mise.frames_per_page == self.frames_par_page)
        tete = (f"   {glyphes['curseur']} " if curseur else " " * _INDENT)
        puce = glyphes["exclusif-retenu"
                       if mise.frames_per_page == self.frames_par_page
                       else "exclusif-libre"]
        marque = (glyphes[ETAT_CHOIX_OPTIMAL]
                  if self.est_optimale(mise.frames_per_page) else " ")
        dimensions = (f"{mise.largeur_mm:5.1f} × {mise.hauteur_mm:5.1f} mm"
                      .replace(".", ","))
        surface = f"{mise.surface_cm2:5.1f}".replace(".", ",") + " cm²"
        pages = f"{mise.pages:3d} pages"
        return _replie(f"{tete}{puce} {mise.frames_per_page}{marque}   "
                       f"{dimensions}   {surface}   {pages}", ascii_seul)

    def lignes_de_la_liste(self, ascii_seul: bool = False) -> list[str]:
        return [self.ligne_de_cardinal(mise, ascii_seul)
                for mise in self.mises_en_page()]

    def etats_de_la_liste(self) -> dict[int, str]:
        """L'etat DONNE de chaque entree, rang par rang (`EPIC11-ARB-71`).

        Le glyphe etant colle au chiffre, il n'ouvre pas de colonne et la
        reconnaissance par motif de `jetons.peindre` ne peut pas le voir. C'est
        le regime normal d'un etat connu du seul ecran.
        """
        return {rang: ETAT_CHOIX_OPTIMAL
                for rang, mise in enumerate(self.mises_en_page())
                if self.est_optimale(mise.frames_per_page)}

    def ligne_de_la_legende(self, ascii_seul: bool = False) -> str:
        glyphe = jetons.glyphes(ascii_seul)[ETAT_CHOIX_OPTIMAL]
        return " " * _INDENT + _replie(f"{glyphe} {LEGENDE_CHOIX_OPTIMAL}",
                                       ascii_seul)

    def lignes_du_conseil(self, utile: int,
                          ascii_seul: bool = False) -> list[str]:
        """Les deux lignes du conseil, la mesure calee a droite de la grille.

        Vide quand la mise en page retenue n'est dominee par personne : il n'y a
        alors **rien** a conseiller, et un ecran qui conseillerait quand meme
        serait un ecran qui meuble.
        """
        meilleure = self.meilleure_que_la_retenue()
        if meilleure is None:
            return []
        glyphes = jetons.glyphes(ascii_seul)
        tete = MOTIF_DU_CONSEIL.format(
            glyphe=glyphes[ETAT_DU_REPLI],
            cardinal=meilleure.frames_per_page,
            orientation=meilleure.orientation)
        motif = MOTIF_SURFACE_SUPERIEURE
        if meilleure.pages < self.retenue().pages:
            motif += MENTION_GAIN_DE_PAGES
        mesure = (f"{meilleure.surface_cm2:.1f}".replace(".", ",")
                  + f" cm² · {meilleure.pages} pages")
        creux = (utile - _INDENT_DU_CONSEIL
                 - jetons.colonnes(motif) - jetons.colonnes(mesure))
        return [_replie(" " * _INDENT + tete, ascii_seul),
                _replie(" " * _INDENT_DU_CONSEIL + motif
                        + " " * max(1, creux) + mesure, ascii_seul)]

    def ligne_du_bouton(self, ascii_seul: bool = False) -> str:
        """Le bouton, dessine **comme un champ** (`DESIGN.md` §7.3)."""
        tete = _tete_de_champ("", self.champ == CHAMP_VALIDER, ascii_seul)
        return tete + _replie(LIBELLE_VALIDER, ascii_seul)

    # -- la ligne d'etat -----------------------------------------------------

    def emplacements(self) -> int:
        """Les emplacements que la passe imprimerait : pages x cardinal."""
        return self.retenue().pages * self.frames_par_page

    def mesure(self, ascii_seul: bool = False) -> str:
        """Ce que la ligne d'etat dit quand il n'y a pas de constat a dire."""
        retenue = self.retenue()
        par_lot = _SEPARATEUR_DES_LOTS.join(
            f"{lot.lot_id} {pages}"
            for lot, pages in zip(self.lots, retenue.pages_par_lot))
        return _replie(MOTIF_DE_LA_MESURE.format(
            pages=retenue.pages,
            par_lot=par_lot,
            frames=sum(self.frames_par_lot()),
            emplacements=self.emplacements()), ascii_seul)

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        if self.repli is None:
            return self.mesure(ascii_seul)
        glyphe = jetons.glyphes(ascii_seul)[ETAT_DU_REPLI]
        constat = MOTIF_DU_REPLI.format(demande=self.repli.demande,
                                        orientation=self.repli.orientation,
                                        retenu=self.repli.retenu)
        return _replie(f"{glyphe}  {constat}", ascii_seul)


# ---------------------------------------------------------------------------
# `E5-2` / `E5-2b` -- l'ecran
# ---------------------------------------------------------------------------

class EcranReglagesDesPlanches(ObjetTravaille, Palier):
    """`E5-2` -- les reglages des planches.

    L'ecran ne mesure rien, ne compare rien et ne replie rien : il branche le
    modele ci-dessus sur le clavier et sur la seule issue de l'ecran, le bouton
    `Valider`. **Il n'importe jamais `cli.py`** (`EPIC11-ARB-67`).
    """

    titre = projet_lecture.PDF
    #: La ligne de raccourcis d'ouverture -- le focus part sur un champ de
    #: choix. Elle est **reassignee a chaque dessin** par
    #: :meth:`poser_les_raccourcis`, l'idiome du depot pour une ligne
    #: contextuelle (`atelier_extraction`, `atelier_scan`, `ecran_projet`).
    #: Une `property` aurait fait la meme chose et **casse le balayage du
    #: paquet** : `test_majuscules_des_raccourcis` lit cet attribut de CLASSE et
    #: attend une chaine.
    raccourcis = RACCOURCIS_CHOIX
    #: Une station du parcours : on y revient depuis la confirmation, et
    #: `Échap` ramene a la selection des lots.
    TRANSITOIRE = False
    ID_DU_CORPS = "corps-reglages-pdf"

    def __init__(self, reglages: ReglagesDesPlanches,
                 continuer: Callable[[ReglagesDesPlanches], None] | None = None
                 ) -> None:
        super().__init__()
        self.reglages = reglages
        self._continuer = continuer

    # -- lecture --------------------------------------------------------------

    def poser_les_raccourcis(self) -> str:
        """Contextuelle : `⏎ valider` sur le bouton, `⏎ sélectionner` ailleurs.

        Mesurable sans monter l'ecran, comme tout le reste de ce module.
        """
        self.raccourcis = self.reglages.raccourcis()
        return self.raccourcis

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E5-2`, **sous la hauteur de la zone centrale**."""
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_DES_REGLAGES, ascii_seul))
        composition.respirer()
        composition.poser(self.reglages.ligne_de_l_orientation(ascii_seul))
        composition.poser(self.reglages.ligne_du_format(ascii_seul))
        composition.poser(self.reglages.ligne_de_la_marge(ascii_seul))
        composition.respirer()
        composition.poser(filet_titre(FILET_DES_CARDINAUX, utile, ascii_seul))
        composition.bloc(self.reglages.lignes_de_la_liste(ascii_seul),
                         etats=self.reglages.etats_de_la_liste())
        composition.poser(self.reglages.ligne_de_la_legende(ascii_seul))
        for ligne in self.reglages.lignes_du_conseil(utile, ascii_seul):
            composition.poser(ligne)
        composition.poser(self.reglages.ligne_du_bouton(ascii_seul))
        return composition.rendu()

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.reglages.ligne_d_etat(self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """Le bandeau reste NU : on regle une passe, pas un lot en particulier."""
        return ""

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [Vertical(self._corps, id=f"centre-{self.ID_DU_CORPS}")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self.poser_les_raccourcis()
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
        self.rafraichir()

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        if touche in ("up", "down"):
            self.reglages.oublier_le_repli()
            self.reglages.choisir(-1 if touche == "up" else 1)
            return True
        if touche in ("tab", "shift+tab"):
            self.reglages.oublier_le_repli()
            self.reglages.avancer(-1 if touche == "shift+tab" else 1)
            return True
        if touche == "enter":
            self.reglages.oublier_le_repli()
            if not self.reglages.entrer():
                return True
            if self._continuer is not None:
                self._continuer(self.reglages)
            else:
                self._pas_encore()
            return True
        return False

    def _pas_encore(self) -> None:
        """`Valider` sans appelant : l'ecran suivant n'existe pas encore, et on
        le DIT.

        `E5-3` -- la confirmation -- est livree par le lot F de cette story, et
        le parcours qui relie les deux par le lot C. D'ici la, l'absence **ne se
        tait pas** : c'est la consigne d'Egan du 2026-08-28, « quitte a ne mener
        nulle part [...] comme ca on sait que c'est temporaire et que ce n'est
        pas un bug ».
        """
        application = _application_montee(self)
        if application is None:
            # Un ecran construit a nu par un banc n'a pas d'application ou
            # descendre : il n'y a rien a montrer, et rien a taire non plus.
            return
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_APRES_LES_REGLAGES,
                                             QUAND_LA_CONFIRMATION))


__all__ = [
    "CE_QUI_MANQUE_APRES_LES_REGLAGES",
    "CHAMPS",
    "CHAMPS_DE_CHOIX",
    "CHAMP_CARDINAL",
    "CHAMP_MARGE",
    "CHAMP_ORIENTATION",
    "CHAMP_VALIDER",
    "ETAT_CHOIX_OPTIMAL",
    "ETAT_DU_REPLI",
    "EcranReglagesDesPlanches",
    "FILET_DES_CARDINAUX",
    "LEGENDE_CHOIX_OPTIMAL",
    "LIBELLE_FORMAT_DPI",
    "LIBELLE_MARGE",
    "LIBELLE_ORIENTATION",
    "LIBELLE_VALIDER",
    "LotAPlanches",
    "MOTIF_DE_LA_MESURE",
    "MOTIF_DU_CONSEIL",
    "MOTIF_DU_REPLI",
    "ORDRE_DES_ORIENTATIONS",
    "QUAND_LA_CONFIRMATION",
    "RACCOURCIS_CHOIX",
    "RACCOURCIS_VALIDER",
    "ReglagesDesPlanches",
    "TITRE_DES_REGLAGES",
]
