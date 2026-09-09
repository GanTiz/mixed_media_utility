# -*- coding: utf-8 -*-
"""L'atelier Pdf, LA GENERATION : `E5-4` et `T6-1` (story 11.7, AC 9).

Deux ecrans : la passe qui ecrit, et la question qu'on lui pose en
l'interrompant. Ils sont livres **montables et mesures** ; leur enchainement
avec les ecrans amont se pose ailleurs et plus tard, comme pour les cinq
ecrans de la mire -- quatre lots de la meme story travaillent en parallele sur
`atelier_pdf.py`, et un point d'appel unique vaut mieux que quatre.

Ce que la mesure a etabli, et qui commande tout ce module
---------------------------------------------------------

**1. Le coeur n'emet AUCUNE ligne de journal pendant le rendu.** Mesure du
2026-09-02 sur le chemin de production, `makepdf.generer_les_planches_du_lot`
appele sur un projet reel : trois lignes en tout pour une passe d'un lot --
une reserve informative, `compression de gamut: ...`, puis
`PDF ecrit: ... (5 page(s))` --, et **zero** entre les deux, alors que cinq
jalons de progression tombent dans cet intervalle. `pdf_render.py`,
`pdf_composition.py` et `page_templates.py` ne portent pas un seul appel de
journalisation. C'est **le meme fait** que la mire a paye (`E5-6c`) : les
quatre lignes que la maquette montrait etaient **dessinees**.

La consequence n'est pas la meme ici, et c'est ce qui separe les deux ecrans.
Sur la mire il n'y avait **rien** a dire, donc le journal est parti et un rotor
l'a remplace. Ici les trois valeurs de la maquette existent, **dans le plan** :
le gabarit est `LotComposition.template_id`, le cardinal d'emplacements est
`len(PagePlan.frames)`, et la version du symbole se lit de
`qr_codes.symbol_version(PagePlan.qr.module_side)`. Le journal de `E5-4` est
donc **compose par la TUI a partir de valeurs du produit**, exactement comme
`atelier_extraction_ecriture.en_tete_de_lot` compose la sienne -- et **jamais**
relaye du coeur, qui n'en emet aucune. Les fonctions qui le composent sont
pures et se mesurent sans monter d'ecran.

**2. Le total de la passe n'est PAS toujours connu, et c'est la que le glyphe
de chargement se pose.** Le cardinal de pages d'un lot vient de
`pdf_composition.compose_lot_plan`, appele **par lot** a l'interieur de
`generer_les_planches_du_lot`. Tant qu'un lot de la passe n'a pas ete compose,
son cardinal est inconnu, donc la somme l'est aussi : il n'existe alors aucun
pourcentage a afficher, et `avancement.barre(0, 0)` rend une barre
**entierement vide** -- c'est-a-dire un dessin qui occupe 36 colonnes pour ne
rien dire.

Egan l'a releve, verbatim et avec son reproche : « **Oui on attend. Mais il
faudrait un glyphe de chargement. Pas la premiere fois que je le demande.** »
Le reproche est fonde et il est mesure : le rotor avait ete pose sur la mire --
la ou la demande etait ecrite -- et pas ici, ni sur la barre a `0/0` de
l'ingestion de scan. **Le perimetre reel d'une demande de FORME est tout ecran
qui porte la meme forme**, pas l'ecran ou elle a ete ecrite.

Ici, la forme est *attendre sans savoir compter*. Le rotor remplace donc la
barre **exactement quand le total est inconnu**, et lui rend la place des que
la passe sait compter. `DESIGN.md` section 9 n'est pas contredit -- l'interdit
porte sur une animation « **a la place d'un compte reel** », et il n'y a ici
aucun compte reel a remplacer.

**3. Aucune duree n'est inventee.** `reste ~ 8 s` est une **forme** de la
maquette, pas une promesse : personne n'a chronometre une generation de
planches. Le champ est rendu quand -- et seulement quand --
`EstimateurTempsRestant` en donne un, ce que `Avancement.ligne_d_etat` fait
deja (`EPIC7-ARB-67`). Ce module n'ecrit aucun nombre de secondes.

Ce que ce module NE fait PAS, et il faut le lire avant de le relire
-------------------------------------------------------------------

**`EPIC11-ARB-134` point 2 n'est pas livre au moment ou ces lignes sont
ecrites** : `execution.SurfaceExecution.emetteur` remet toujours
`avancement.faites` a zero a chaque lot. La consequence est bornee, et elle
est **une ligne** : :meth:`EcranGenerationDesPlanches.sur_jalon`, qui traduit
un jalon du socle en avancement de la passe. Le modele
(:class:`PasseDeGeneration`), le rendu et **tous** leurs bancs portent
l'agregation sur la passe entiere, celle qu'`ARB-134` veut : aucun test de ce
lot n'affirme qu'un compte repart a zero au second lot, donc aucun ne devient
un obstacle a la correction. C'est la seule facon de livrer l'ecran sans
livrer le defaut avec lui.

**Ce module ne modifie pas `execution.py`** (AC 9.5) : `T6-1` s'obtient par
sous-classement d'`EcranInterruption`, dont il ne redonne que les chiffres.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Sequence

from textual.widget import Widget
from textual.widgets import Static

from .. import qr_codes
from . import avancement as modele_avancement
from . import jetons
from .atelier_extraction import Composition, filet_titre, ligne_de_titre
from .avancement import Avancement, Journal
from .execution import (ETAT_DU_LOT_ECRIT, INDENT_DES_LIGNES, MENTION_ECRIT,
                        MENTION_EN_ATTENTE, MENTION_EN_COURS,
                        MENTIONS_DES_LOTS, TITRE_DE_LA_PASSE, EcranExecution,
                        EcranInterruption, SurfaceExecution, bloc_peint,
                        ligne_du_lot, mention_du_lot)
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

# ===========================================================================
# Le bandeau et la ligne de raccourcis
# ===========================================================================

#: Le segment du milieu du bandeau, `mmu · projet_demo · **Pdf**`. Il nomme
#: l'atelier et rien de plus : `EPIC11-ARB-28` interdit qu'un terme de nos
#: documents de decision s'affiche a l'ecran, et une frontiere negative le
#: mesure sur ce fichier.
PALIER_DE_LA_GENERATION = "Pdf"

#: `E5-4`, verbatim de la maquette (l. 23). `Tab` deplie le journal complet --
#: la promesse est **tenue** (`EcranExecution.on_key` traite `tab`), et c'est
#: ce qui la distingue de la mire, ou elle a ete retiree faute de journal.
#: `Échap` interrompt et ne remonte pas.
#:
#: **Le mot « complet » est PARTI** (`EPIC11-ARB-246`, Egan le 2026-09-06, par
#: invite, verbatim : « Tab journal partout »). Cette ligne etait le **seul**
#: site du code a porter `Tab journal complet` : les quatre autres ecrans
#: « en cours » du produit heritent d'`execution.EcranExecution`, qui rend
#: `Tab journal` depuis toujours. Le jeton est desormais UNIQUE dans tout le
#: produit, et `test_vocabulaire_de_la_tui.py` le mesure par une frontiere
#: **negative** : un grep de la forme longue doit rendre zero, dans `src/`
#: comme dans les maquettes. Ce qui est retire n'etait pas une promesse
#: differente -- `Tab` deplie ici le meme journal qu'ailleurs.
#:
#: MESURE: 39/39
RACCOURCIS_GENERATION = "Tab journal  Échap interrompre  F1 aide"

# ===========================================================================
# Le corps de `E5-4` (AC 9.2)
# ===========================================================================

#: Le verbe de la passe, verbatim de la maquette (l. 5). Il porte le **rang du
#: lot** : c'est le point 3 d'`EPIC11-ARB-134`, et sans lui l'ecran ne dit pas
#: ou l'on en est d'une passe a plusieurs lots.
#:
#: **La FORME du titre est hissee** dans `execution.TITRE_DE_LA_PASSE`
#: (11.4e, AC 8.6) : les trois maquettes d'execution du depot la partagent, et
#: seul le verbe change d'un atelier a l'autre. Ce module garde donc son verbe
#: et lit la forme.
LIBELLE_DE_LA_PASSE = "Génération en cours"
TITRE_DE_LA_GENERATION = TITRE_DE_LA_PASSE.replace("{libelle}",
                                                   LIBELLE_DE_LA_PASSE)

#: Le titre du filet du journal, verbatim de la maquette (l. 10).
TITRE_DU_JOURNAL = "Journal"

# Les trois etats d'un lot, leur jeu ferme, l'etat de peinture d'un lot ecrit
# et l'indentation des lignes sont **HISSES** dans `execution` (11.4e, AC 8.6),
# et importes ci-dessus. Ils vivaient ici les premiers ; l'AC 8 en a eu besoin
# pour `E2-4` et `E3-7`, et un comptage a zero d'une seconde redaction dans
# `tui/` interdit de les reecrire de ce cote. Ils restent references par leur
# nom d'origine dans tout ce module, et l'import les rend toujours lisibles en
# `generation.MENTION_ECRIT` -- ce que deux bancs font nommement
# (`test_atelier_pdf_execution.py:239`). Aucun appelant ne change.

#: Le pluriel des pages, comme partout dans cet atelier. Le singulier vaut
#: aussi pour zero.
PLURIEL_DES_PAGES = {False: "page", True: "pages"}

#: Le separateur du detail de la ligne d'etat (`lot 2/2 · page 3/7`), verbatim
#: de la maquette : un point median entoure d'espaces.
SEPARATEUR = " · "

#: Le detail de la ligne d'etat, verbatim de la maquette (l. 22). Il
#: **remplace** le compte simple dans `Avancement.ligne_d_etat` -- c'est le
#: contrat du champ `detail`, pas une seconde redaction.
DETAIL_DE_LA_PASSE = "lot {lot}/{lots}{separateur}page {page}/{pages}"

#: Le meme detail quand le cardinal de pages du lot courant n'est pas encore
#: connu : on dit le lot, on ne feint pas de compter ses pages.
DETAIL_SANS_PAGES = "lot {lot}/{lots}"

#: L'unite comptee par la passe. Le canal du coeur emet un jalon **par page**
#: (`pdf_render.render_lot_pdf`), donc l'unite vient de ce qui est compte.
UNITE = "pages"

#: La periode du rotor, en secondes -- la meme que celle de la mire. Quatre
#: dessins : le cycle complet dure quatre fois cette valeur.
PERIODE_DU_ROTOR = 0.25

# ===========================================================================
# Le journal, COMPOSE par la TUI (AC 9.3)
# ===========================================================================

#: L'en-tete d'un lot, verbatim de la maquette (l. 12). Elle **nomme le lot**,
#: et c'est elle qui rend `EPIC11-ARB-93` tenable : le journal n'etant plus
#: remis a zero entre deux lots, `21/21` suivi de `1/7` se lirait comme un
#: compte qui recule. Nommee, la rupture se lit pour ce qu'elle est.
EN_TETE_DE_LOT = "{lot} : {gabarit}, tirage {rang}"

#: La ligne d'une page, verbatim de la maquette (l. 13-15). Ses trois valeurs
#: sont **lues du plan**, jamais recomposees ici -- voir le docstring de
#: module, point 1.
LIGNE_DE_PAGE = ("page {page}/{pages} : {emplacements} emplacements, "
                 "QR version {version}")

#: Le format de l'horodatage des lignes de journal, verbatim de la maquette
#: (`16:22:41`). Il est compose ici parce que `avancement.Journal` n'horodate
#: pas -- il conserve des lignes, il n'en fabrique aucune.
FORMAT_DE_L_HORODATAGE = "%H:%M:%S"

#: Le creux entre l'horodatage et le texte de la ligne, verbatim de la maquette
#: (deux espaces).
CREUX_DE_L_HORODATAGE = "  "


def horodater(instant: datetime, texte: str) -> str:
    """`16:22:41  page 1/7 : ...` -- une ligne de journal de `E5-4`.

    L'instant est **donne**, jamais lu ici : c'est la regle d'`EPIC4-ARB-8`
    pour la date imprimee sur une planche, et elle vaut pour la meme raison --
    une horloge lue au fond d'une fonction rend le rendu immesurable.
    """
    return f"{instant.strftime(FORMAT_DE_L_HORODATAGE)}{CREUX_DE_L_HORODATAGE}{texte}"


def version_du_qr(page) -> int:
    """La version ISO du symbole de cette page, **lue du produit**.

    `qr_codes.symbol_version` est la seule redaction de la relation
    `4V + 17` du depot ; la recopier ici en ferait une seconde qui divergerait.
    Le cote de module vient du plan (`PagePlan.qr.module_side`), donc de ce qui
    va reellement etre imprime.
    """
    return qr_codes.symbol_version(page.qr.module_side)


def ligne_de_page(page, rang: int, pages: int) -> str:
    """La ligne de journal d'une page composee, depuis son `PagePlan`.

    Les trois valeurs sont lues du plan : le cardinal d'emplacements est
    `len(page.frames)` -- il **differe** sur la derniere page d'un lot mal
    rempli, et c'est precisement pour cela qu'il se lit page par page au lieu
    de se recopier du `frames_per_page` du lot.
    """
    return LIGNE_DE_PAGE.format(page=rang, pages=pages,
                                emplacements=len(page.frames),
                                version=version_du_qr(page))


def en_tete_de_lot(lot: "LotEnGeneration") -> str:
    """`plan-04_8 : tpl-a4-paysage-6f-v2, tirage 1`.

    Le rang est **affiche**, jamais recalcule (`EPIC11-ARB-92`) : il vient de
    la passe, qui le tient de la resolution faite en amont.
    """
    return EN_TETE_DE_LOT.format(lot=lot.libelle, gabarit=lot.gabarit,
                                 rang=lot.rang)


# ===========================================================================
# Le modele de la passe -- pur, mesurable sans monter d'ecran
# ===========================================================================

@dataclass(frozen=True)
class LotEnGeneration:
    """Un lot de la passe, tel que l'ecran de generation le montre.

    `pages` vaut `None` tant que le lot n'a **pas ete compose** : son cardinal
    vient de `pdf_composition.compose_lot_plan`, appele lot par lot a
    l'interieur du coeur. C'est cette absence -- et rien d'autre -- qui rend le
    total de la passe inconnu, donc le pourcentage incalculable et le rotor
    legitime.
    """

    #: Le nom du PDF, tel qu'il sera ecrit. Il vient de `io.naming`, jamais
    #: recompose ici.
    nom: str
    #: Le cardinal de pages du lot, ou `None` s'il n'est pas encore compose.
    pages: int | None = None
    #: Le `template_id` du produit, pour l'en-tete de journal du lot.
    gabarit: str = ""
    #: Le rang de tirage, **affiche** et jamais recalcule (`EPIC11-ARB-92`).
    rang: int = 1
    #: Le libelle court du lot au journal (`plan-04_8`). Le nom du PDF y serait
    #: illisible : la maquette porte l'un dans le corps et l'autre au journal.
    libelle: str = ""


@dataclass
class PasseDeGeneration:
    """Ce que `E5-4` affiche a un instant : l'etat de la passe entiere.

    **L'agregation porte sur la passe, pas sur le lot** (`EPIC11-ARB-134`
    point 2). C'est ce modele qui la tient, parce que c'est lui qui connait la
    liste des lots -- le socle d'execution n'a jamais qu'un couple
    `(faites, total)` a la fois, et un couple ne sait pas ce qu'il y a autour.
    """

    lots: tuple[LotEnGeneration, ...]
    #: Le rang, 0-fonde, du lot en cours d'ecriture.
    rang_du_lot_courant: int = 0
    #: Les pages **deja ecrites du lot courant**. C'est le seul champ que le
    #: canal du coeur alimente ; tout le reste se derive.
    pages_du_lot_courant: int = 0
    #: Rendu par `EstimateurTempsRestant`, ou `None`. **Jamais fabrique ici**
    #: (`EPIC7-ARB-67`).
    temps_restant: float | None = None

    def __post_init__(self) -> None:
        if not self.lots:
            raise ValueError(
                "Une passe de generation porte au moins un lot : un ecran de "
                "generation sans rien a generer n'a pas d'etat a montrer.")

    # -- les cardinaux -------------------------------------------------------

    @property
    def total_connu(self) -> bool:
        """Vrai quand **tous** les lots ont ete composes.

        « Tous », et non « celui-ci » : la barre agrege la passe entiere, donc
        un seul lot non compose suffit a rendre la somme inconnue. C'est le cas
        nominal d'une passe a deux lots dont le second n'est pas commence.
        """
        return all(lot.pages is not None for lot in self.lots)

    @property
    def pages_de_la_passe(self) -> int:
        """La somme des pages de **tous** les lots, ou `0` si elle est inconnue.

        `0` est ce que `avancement.barre` et `avancement.pourcentage` traitent
        deja comme « le total ne veut rien dire » ; rendre autre chose
        obligerait chaque appelant a refaire la garde.
        """
        if not self.total_connu:
            return 0
        return sum(lot.pages or 0 for lot in self.lots)

    @property
    def pages_ecrites(self) -> int:
        """Les pages ecrites depuis le debut de la PASSE.

        Les lots **strictement avant** le lot courant, plus ce qui est ecrit du
        lot courant. Un `sum` sur toute la liste compterait les lots a venir ;
        un `sum` qui inclurait le lot courant le compterait deux fois.
        """
        deja = sum(lot.pages or 0
                   for lot in self.lots[:self.rang_du_lot_courant])
        return deja + self.pages_du_lot_courant

    @property
    def lot_courant(self) -> LotEnGeneration:
        return self.lots[self.rang_du_lot_courant]

    @property
    def pages_du_lot(self) -> int | None:
        return self.lot_courant.pages

    # -- les etats -----------------------------------------------------------

    def mention_du_lot(self, rang: int) -> str:
        """L'etat du lot de `rang` : ecrit, en cours, ou en attente.

        La derivation est **hissee** dans `execution.mention_du_lot` (11.4e,
        AC 8.6) : `E2-4` et `E3-7` la partagent depuis. Son motif reste le
        meme -- la comparaison porte sur le rang courant dans les **deux**
        sens, un seul cote rendant « en attente » pour tout ce qui n'est pas le
        lot courant, y compris ce qui est deja sur le disque.
        """
        return mention_du_lot(rang, self.rang_du_lot_courant)

    def etats_des_lots(self) -> dict[int, str]:
        """Les etats de peinture, en rangs RELATIFS au bloc des lots.

        Seuls les lots ecrits en portent un : la maquette pose `●` sur eux et
        rien sur les autres.
        """
        return {rang: ETAT_DU_LOT_ECRIT
                for rang in range(len(self.lots))
                if self.mention_du_lot(rang) == MENTION_ECRIT}

    # -- le rendu ------------------------------------------------------------

    def titre(self) -> str:
        """`Génération en cours — lot 2 sur 3`. Le rang est rendu 1-fonde."""
        return TITRE_DE_LA_GENERATION.format(rang=self.rang_du_lot_courant + 1,
                                             total=len(self.lots))

    def ligne_du_lot(self, rang: int, utile: int,
                     ascii_seul: bool = False) -> str:
        """`● nom.pdf                21 pages  écrit`.

        La colonne des mentions est calee sur le **jeu complet** des trois
        mentions, pas sur celles qui sont affichees : voir
        :data:`MENTIONS_DES_LOTS`.
        """
        table = jetons.glyphes(ascii_seul)
        lot = self.lots[rang]
        mention = self.mention_du_lot(rang)
        if ascii_seul:
            mention = jetons.replier_ascii(mention)
        glyphe = (table[ETAT_DU_LOT_ECRIT] if mention == MENTION_ECRIT
                  else " " * jetons.colonnes(table[ETAT_DU_LOT_ECRIT]))
        compte = ("" if lot.pages is None
                  else f"{lot.pages} "
                       f"{PLURIEL_DES_PAGES[lot.pages > 1]}")
        # **Le rendu est HISSE** dans `execution.ligne_du_lot` (11.4e, AC 8.6),
        # avec son budget de colonnes et son abregement de nom : ce module lui
        # passe ce que SA maquette montre en plus, un glyphe et un compte de
        # pages, que `E2-4` et `E3-7` ne posent pas.
        return ligne_du_lot(lot.nom, mention, utile, ascii_seul,
                            compte=compte, glyphe=glyphe)

    def lignes_des_lots(self, utile: int,
                        ascii_seul: bool = False) -> list[str]:
        return [self.ligne_du_lot(rang, utile, ascii_seul)
                for rang in range(len(self.lots))]

    # -- la ligne d'etat -----------------------------------------------------

    def detail(self) -> str:
        """`lot 2/2 · page 3/7` -- le second niveau de la ligne d'etat."""
        if self.pages_du_lot is None:
            return DETAIL_SANS_PAGES.format(lot=self.rang_du_lot_courant + 1,
                                            lots=len(self.lots))
        return DETAIL_DE_LA_PASSE.format(
            lot=self.rang_du_lot_courant + 1, lots=len(self.lots),
            separateur=SEPARATEUR,
            page=self.pages_du_lot_courant, pages=self.pages_du_lot)

    def avancement(self) -> Avancement:
        """L'avancement de la PASSE, pret pour `Avancement.ligne_d_etat`.

        Le socle porte deja la barre, le pourcentage, le compte et le temps
        restant, avec leur ordre de sacrifice quand la ligne deborde. Les
        recomposer ici serait une seconde redaction de la meme ligne.
        """
        return Avancement(unite=UNITE, faites=self.pages_ecrites,
                          total=self.pages_de_la_passe, detail=self.detail(),
                          temps_restant=self.temps_restant)

    def ligne_d_etat(self, pas: int, largeur: int | None = None,
                     ascii_seul: bool = False) -> str:
        """La ligne d'etat, **avec un rotor a la place de la barre** quand le
        total de la passe est inconnu.

        C'est ici que se pose le glyphe de chargement qu'Egan reclamait, et le
        critere est mesurable plutot que d'appreciation : `total_connu`. Tant
        qu'il est faux, `avancement.barre(0, 0)` rendrait 36 colonnes de vide et
        `pourcentage(0, 0)` la chaine vide -- un dessin qui occupe la place
        d'une information sans en porter aucune. Le rotor, lui, dit la seule
        chose vraie a cet instant : ca travaille.

        Des que le total est connu, la barre reprend sa place : le rotor ne
        remplace **jamais** un compte reel (`DESIGN.md` section 9).
        """
        largeur = jetons.largeur_utile() if largeur is None else largeur
        if self.total_connu:
            return self.avancement().ligne_d_etat(largeur, ascii_seul)
        champs = [jetons.rotor(pas, ascii_seul), self.detail()]
        if self.temps_restant is not None:
            champs.append(
                "reste ~ "
                f"{modele_avancement.duree_lisible(self.temps_restant)}")
        return modele_avancement.SEPARATEUR.join(champs)


# ===========================================================================
# `T6-1` -- l'interruption de la generation (AC 9.5 a 9.9)
# ===========================================================================

#: Les deux libelles chiffres du panneau de `T6-1`. Ils nomment ce qu'ils
#: comptent, et le mot est celui de l'unite de la passe.
LIBELLE_PAGES_ECRITES = "Pages écrites"
LIBELLE_PAGES_RESTANTES = "Pages restantes"

#: Ce que la ligne des pages restantes porte quand le total de la passe est
#: inconnu. **Une absence dite**, pas un zero : afficher `0 pages restantes`
#: sur une passe dont on ne connait pas le total dirait que tout est fini.
RESTANTES_INCONNUES = "inconnu tant qu'un lot n'est pas composé"

#: Le titre du cartouche de `T6-1`, celui du patron partage.
TITRE_DE_L_INTERRUPTION = "Déjà écrit"


class EcranInterruptionDeLaGeneration(EcranInterruption):
    """`T6-1` -- ce qu'on laisse en interrompant la generation des planches.

    **Obtenu par sous-classement** (AC 9.5), sur le patron que
    `atelier_scan_detection.EcranInterruptionDeDetection` a pose : on herite du
    clavier, du rendu, de `Échap reprendre` et de l'ensemble **exact** des trois
    issues, et l'on ne redonne que les chiffres. Reecrire les issues ici les
    ferait diverger de `EcranInterruption.ISSUES` a la premiere retouche, et
    l'AC 9.9 mesure justement leur egalite.

    **Le chiffre evolue pendant que l'ecran est monte** (AC 9.7,
    `EPIC11-ARB-134` point 5) : l'ecriture continue derriere tant qu'aucune
    issue n'est validee, donc un chiffre lu au montage et jamais rafraichi
    vieillirait pendant qu'on lit la question. Le panneau est donc **recompose
    a chaque jalon**, et non fige a la construction.
    """

    titre = PALIER_DE_LA_GENERATION

    def __init__(self, passe: PasseDeGeneration,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        self.passe = passe
        # **Les issues sont posees AVANT `super()`**, qui lit `self.ISSUES`
        # pour construire le choix. Poser un attribut d'instance du meme nom
        # laisse la liste heritee intacte pour tous les autres ecrans -- c'est
        # ce que l'AC 9.9 mesure, et une reecriture de classe l'aurait rompu.
        self.ISSUES = issues_chiffrees(passe)
        super().__init__(panneau_de_la_passe(passe), sur_issue=sur_issue)

    def rafraichir_les_chiffres(self) -> None:
        """Relire la passe, rechiffrer les issues, redessiner (AC 9.7).

        **Le curseur est reporte**, jamais remis a zero : le rafraichissement
        tombe pendant qu'on lit la question, et voir la fleche sauter sous ses
        yeux serait pire que de ne pas rafraichir du tout.

        Elle est **publique et appelable a la main** : c'est ce qui rend
        l'AC 9.7 mesurable sans horloge et sans terminal.
        """
        curseur = self.choix.curseur
        self.panneau = panneau_de_la_passe(self.passe)
        self.ISSUES = issues_chiffrees(self.passe)
        self.choix = ChoixExclusif(list(self.ISSUES))
        self.choix.curseur = curseur
        self.rafraichir()

    def etat(self) -> str:
        """Une **mesure** de l'etat de la passe, jamais un motif de conception.

        `EcranInterruption.etat` rend « L'execution continue tant qu'aucune
        issue n'est validee. », qui explique un mecanisme -- exactement ce que
        `EPIC11-ARB-56` retire de cette zone. Ce qui la remplace se compte.
        """
        if self._refus_annonce is not None:
            return self._refus_annonce
        return ligne_d_etat_de_l_interruption(self.passe)


#: Ce que les libelles herites disent de ce qui est ecrit, **verbatim**
#: d'`execution.EcranInterruption.ISSUES`. C'est le seul segment substitue, et
#: il est ecrit ici une fois : le chercher a la volee dans le libelle rendrait
#: la substitution muette le jour ou le patron le reformule -- une issue
#: resterait alors « ce qui est deja ecrit » sans que rien ne rougisse.
TOURNURE_SANS_CHIFFRE = "ce qui est deja ecrit"

#: Ce qui la remplace, avec le chiffre reel (AC 9.6). `Interrompre et garder
#: **les 12 pages**`.
TOURNURE_CHIFFREE = "les {pages} {unite}"


def libelle_chiffre_de_l_issue(issue: Issue, passe: PasseDeGeneration) -> str:
    """`Interrompre et garder les 12 pages` (AC 9.6).

    **Le libelle herite n'est pas reecrit, il est SUBSTITUE** : ce qui entoure
    le chiffre reste mot pour mot celui d'`EcranInterruption.ISSUES`, et une
    issue qui ne parle pas de ce qui est ecrit -- « Reprendre l'execution » --
    traverse sans changer d'un caractere.

    C'est ce qui permet de tenir l'AC 9.6 et l'AC 9.9 ensemble : l'ensemble des
    cles reste **exactement** celui du patron, et le seul ecart de libelle est
    la tournure nommee ci-dessus, mesurable comme telle.
    """
    if TOURNURE_SANS_CHIFFRE not in issue.libelle:
        return issue.libelle
    ecrites = passe.pages_ecrites
    return issue.libelle.replace(
        TOURNURE_SANS_CHIFFRE,
        TOURNURE_CHIFFREE.format(pages=ecrites,
                                 unite=PLURIEL_DES_PAGES[ecrites > 1]))


def issues_chiffrees(passe: PasseDeGeneration) -> tuple[Issue, ...]:
    """Les trois issues du patron, leur chiffre pose (AC 9.6, AC 9.9).

    L'ordre, les cles et le drapeau `ecrit` de chacune sont **repris tels
    quels** : ce sont eux que l'ensemble exact de l'AC 9.9 mesure, et les
    reecrire ici les ferait diverger du patron a la premiere retouche.
    """
    return tuple(
        Issue(issue.cle, libelle_chiffre_de_l_issue(issue, passe),
              ecrit=issue.ecrit)
        for issue in EcranInterruption.ISSUES)


def panneau_de_la_passe(passe: PasseDeGeneration) -> Panneau:
    """Ce qui est deja ecrit, et ce qui reste -- **mesure**, jamais estime.

    Aucune des deux lignes ne porte la mention de majorant : les deux viennent
    des jalons du coeur. La seconde dit son **absence** quand le total de la
    passe n'est pas connu, plutot que de rendre un zero qui se lirait « fini ».
    """
    ecrites = passe.pages_ecrites
    if passe.total_connu:
        restantes = LigneChiffree(LIBELLE_PAGES_RESTANTES,
                                  max(passe.pages_de_la_passe - ecrites, 0),
                                  UNITE)
    else:
        restantes = LigneChiffree(LIBELLE_PAGES_RESTANTES,
                                  RESTANTES_INCONNUES)
    return Panneau(TITRE_DE_L_INTERRUPTION,
                   [LigneChiffree(LIBELLE_PAGES_ECRITES, ecrites, UNITE),
                    restantes])


#: La ligne d'etat de `T6-1` : **une mesure de la passe**. Le lot courant et ce
#: qui en est ecrit, ce qui est le seul fait que l'ecran connaisse et que le
#: panneau ne dise pas deja.
ETAT_DE_L_INTERRUPTION = "{titre}{separateur}{detail}"


def ligne_d_etat_de_l_interruption(passe: PasseDeGeneration) -> str:
    """`Génération en cours — lot 2 sur 3 · lot 2/3 · page 3/7`."""
    return ETAT_DE_L_INTERRUPTION.format(titre=passe.titre(),
                                         separateur=SEPARATEUR,
                                         detail=passe.detail())


# ===========================================================================
# La composition de `E5-4` -- pure, mesurable sans monter d'application
# ===========================================================================

#: Ce que le corps occupe **hors** journal et hors liste des lots : le titre,
#: le filet, et les trois respirations qui les separent. Derive une seule fois,
#: parce que deux fonctions le lisent.
LIGNES_HORS_JOURNAL = 4


def hauteur_centrale(hauteur_fenetre: int) -> int:
    """La zone centrale a la hauteur COURANTE de la fenetre.

    Derivee de la fenetre et non du plancher : au-dela de 24 lignes, la place
    gagnee va entierement a la zone centrale (`DESIGN.md` section 1). La
    calculer sur le plancher revenait a ignorer un terminal plein ecran.

    **La soustraction elle-meme est remontee dans `jetons`** (2026-09-04) :
    c'etait la quatrieme copie du meme calcul dans le paquet.
    """
    return jetons.hauteur_centrale(hauteur_fenetre)


def lignes_de_journal_visibles(hauteur_centre: int, lots: int,
                               journal_deplie: bool = False) -> int:
    """Combien de lignes de journal tiennent.

    **Deplie, le journal prend la place de la liste des lots** : c'est ce que
    `Tab journal` promet, et le seul moyen de tenir la promesse dans une zone
    centrale de 17 lignes. Le jeton a perdu son mot « complet »
    (`EPIC11-ARB-246`) ; la promesse, elle, est la meme.
    """
    if journal_deplie:
        return max(hauteur_centre - LIGNES_HORS_JOURNAL, 0)
    return max(hauteur_centre - LIGNES_HORS_JOURNAL - lots, 0)


def corps_de_la_generation(passe: PasseDeGeneration, journal: Journal,
                           largeur: int, hauteur: int,
                           ascii_seul: bool = False,
                           journal_deplie: bool = False
                           ) -> tuple[list[str], int | None, dict[int, str]]:
    """Le corps de `E5-4`, sous la hauteur de la zone centrale.

    **La liste des lots tombe quand le journal est deplie**, et rien d'autre :
    `Composition` sacrifie d'abord ses respirations, mais elle ne retire jamais
    une ligne de texte -- c'est ce qui fait qu'un debordement se voit au banc
    au lieu d'etre tronque en silence par `textual`.
    """
    utile = jetons.largeur_utile(largeur)
    combien = lignes_de_journal_visibles(hauteur, len(passe.lots),
                                         journal_deplie)
    composition = Composition()
    composition.respirer()
    composition.poser(ligne_de_titre(passe.titre(), ascii_seul))
    composition.respirer()
    if not journal_deplie:
        composition.bloc(passe.lignes_des_lots(utile, ascii_seul),
                         etats=passe.etats_des_lots())
        composition.respirer()
    composition.poser(filet_titre(TITRE_DU_JOURNAL, utile, ascii_seul))
    composition.respirer()
    composition.bloc([INDENT_DES_LIGNES + ligne
                      for ligne in journal.dernieres(combien)])
    return composition.rendu(hauteur)


# ===========================================================================
# `E5-4` -- l'ecran de generation
# ===========================================================================

#: L'attribut par lequel l'application retient **l'ecran de la passe en
#: cours**. Il ne sert qu'a une chose : distinguer, au demontage, l'ecran de la
#: tache courante de celui d'une tache deja finie. Un booleen ne le pourrait
#: pas -- deux passes d'une meme session portent deux ecrans, et c'est leur
#: identite qui departage, jamais leur type.
ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE = "_ecran_de_la_passe"


class EcranGenerationDesPlanches(EcranExecution):
    """`E5-4` -- la passe qui ecrit, agregee sur ses lots.

    **Elle sous-classe `EcranExecution`** parce qu'elle en garde les trois
    proprietes qui ont ete payees : `Tab` deplie le journal complet, `Échap`
    ouvre l'interruption **sans depiler**, et l'abonnement au canal se defait
    au demontage. Ce qu'elle redonne est le corps -- un titre qui porte le rang
    du lot, la liste des lots avec leur etat -- et la ligne d'etat, qui agrege
    la passe au lieu de compter un lot.
    """

    #: Reassignee a chaque dessin par :meth:`poser_les_raccourcis` -- l'idiome
    #: du depot pour une ligne contextuelle. Une `property` casserait le
    #: balayage du paquet : `test_majuscules_des_raccourcis` lit cet attribut
    #: de CLASSE et attend une chaine.
    raccourcis = RACCOURCIS_GENERATION
    titre = PALIER_DE_LA_GENERATION

    #: Un passage : la duree d'une tache, pas une station.
    TRANSITOIRE = True

    ID_DU_CORPS = "corps-generation-pdf"

    def __init__(self, surface: SurfaceExecution, passe: PasseDeGeneration,
                 sur_issue: Callable[[Issue], None] | None = None,
                 objet: str = "") -> None:
        super().__init__(surface, titre_tache="", sur_issue=sur_issue,
                         objet=objet)
        self.passe = passe
        #: Le pas du rotor. Il ne se remet **jamais** a zero : le modulo est
        #: fait par `jetons.rotor`, precisement pour qu'un ecran qui compte ses
        #: propres pas ne rende pas un `IndexError` au quatrieme tour.
        self.pas = 0
        #: L'ecran d'interruption tant qu'il est monte, pour que les jalons le
        #: rafraichissent (AC 9.7).
        self._interruption: EcranInterruptionDeLaGeneration | None = None
        #: Le minuteur du rotor, **retenu** et non oublie -- meme geste que
        #: `atelier_pdf_calibration.EcranMireEnCours`, et meme motif : un
        #: minuteur qu'on ne tient pas ne s'arrete pas. Il continue d'appeler
        #: :meth:`avancer_le_rotor` sur l'ecran d'une passe finie, donc de
        #: faire tourner un rotor que plus rien n'alimente. La poignee permet
        #: aussi de **figer** le mecanisme en banc, plutot que d'attendre
        #: l'horloge -- ce qui mesurerait l'attente.
        self.minuteur = None

    # -- le rotor ------------------------------------------------------------

    def glyphe_du_rotor(self, ascii_seul: bool | None = None) -> str:
        """Le dessin courant, **lu de `jetons`** et jamais recompose ici."""
        if ascii_seul is None:
            ascii_seul = getattr(self.app, "ascii_seul", False)
        return jetons.rotor(self.pas, ascii_seul)

    def avancer_le_rotor(self) -> None:
        """Un pas de plus, et on redessine.

        Elle est appelable a la main : c'est ce qui rend le mouvement mesurable
        sans terminal et sans horloge.
        """
        self.pas += 1
        self.rafraichir()

    def poser_les_raccourcis(self) -> str:
        self.raccourcis = RACCOURCIS_GENERATION
        return self.raccourcis

    # -- le corps ------------------------------------------------------------

    def composer(self, largeur: int, ascii_seul: bool = False,
                 hauteur: int | None = None
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E5-4`. **Pur des le second argument.**

        Il ne lit `self.app` que pour les valeurs par defaut : c'est ce qui
        permet de mesurer la composition entiere sans monter d'application,
        comme le reste de cet atelier.
        """
        if hauteur is None:
            hauteur = self.hauteur_centrale()
        return corps_de_la_generation(
            self.passe, self.surface.journal, largeur, hauteur, ascii_seul,
            journal_deplie=self.journal_deplie)

    def lignes_du_journal(self) -> list[str]:
        """Les dernieres lignes du journal de la passe.

        Le journal **n'est pas remis a zero entre deux lots**
        (`EPIC11-ARB-93`) : c'est l'en-tete qui nomme le lot qui rend la
        rupture lisible.
        """
        return self.surface.journal.dernieres(
            self.lignes_de_journal_visibles())

    def hauteur_centrale(self) -> int:
        return hauteur_centrale(self.app.size.height)

    # -- le cablage du canal -------------------------------------------------

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [self._corps]

    def on_mount(self) -> None:
        """**Le drapeau de tache n'est PAS pose ici**, et c'est un correctif.

        `EcranExecution.on_mount` le pose ; cette classe ne l'appelle pas et ne
        le refait pas. Le motif est mesure : `descendre` DIFFERE le message
        `Mount`, et la passe des planches est appelee **synchroniquement** dans
        la foulee -- elle occupe la boucle d'evenements du premier au dernier
        jalon. L'ordre observe etait donc

            False <- oublier_la_tache        (fin de passe, cote parcours)
            True  <- on_mount                et plus personne ne l'eteignait

        c'est-a-dire un `Échap` qui ne depile plus et un `q` qui ne quitte plus,
        pour le reste de la session. C'est le defaut deja paye par
        `atelier_scan_calibrate.py`, a l'identique.

        Poser le drapeau **au depart de la passe** plutot qu'au montage est ce
        qui ferme les deux sens a la fois : il protege pendant que le coeur
        travaille -- ou aucun `Mount` n'a encore ete distribue --, et il tombe
        avec la passe. Voir :func:`ouvrir_la_generation`.

        **Ne pas le poser ici ne suffit pas**, et c'est la mesure qui l'a dit :
        `textual` distribue TOUS les gestionnaires `on_mount` de la MRO, du plus
        SPECIFIQUE au plus general. Celui d'`EcranExecution` s'execute donc
        APRES celui-ci et repose le drapeau -- que cette classe le redefinisse
        n'y change rien, et une correction ecrite en ligne ici serait ecrasee
        une microseconde plus tard. Mesure faite, pas deduite.

        La correction est donc **differee d'un message** :
        :meth:`rendre_ce_que_la_passe_conclue_retient` passe par `call_next`,
        le rendez-vous que `textual` offre juste apres le traitement du message
        courant -- c'est-a-dire apres le gestionnaire du parent. C'est aussi ce
        qui evite de patcher `execution.py`, que l'AC 9.5 reserve a son lot.
        """
        self.call_next(self.rendre_ce_que_la_passe_conclue_retient)
        self.surface.abonner(self.sur_jalon)
        self.minuteur = self.set_interval(PERIODE_DU_ROTOR,
                                          self.avancer_le_rotor)
        self.rafraichir()

    def arreter_le_rotor(self) -> None:
        """Arreter le minuteur, une fois, sans se soucier d'avoir deja arrete."""
        if self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None

    def rendre_ce_que_la_passe_conclue_retient(self) -> None:
        """Rendre le drapeau que le montage vient de reposer, et le rotor avec.

        Le critere est un fait, pas une intention : un ecran dont le `Mount`
        arrive alors qu'un AUTRE ecran est deja pose au-dessus de lui annonce
        une passe **deja conclue** -- le parcours a monte son compte rendu, ou
        son refus, pendant que le message attendait dans la file. Tant que cet
        ecran est le sommet de la pile, la passe est la sienne, le drapeau reste
        et le rotor tourne : c'est le sens qui protege, et il se mesure aussi.

        **Le rotor part avec le drapeau**, et pas seulement au demontage. Le
        parcours monte `E5-5` PAR-DESSUS `E5-4`, qui n'est donc jamais demonte :
        un `on_unmount` seul laisserait chaque passe derriere elle un minuteur
        qui redessine un ecran que plus personne ne regarde et qu'aucun jalon
        n'alimente. Ce que cette methode ne peut pas faire, c'est depiler --
        le depilage des passes enchainees appartient au parcours, qui n'a pas
        d'equivalent de `atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier`.

        Publique et non privee : c'est ce qui permet de la jouer sans horloge
        ni terminal, comme :meth:`avancer_le_rotor`.
        """
        if self.app.screen is not self:
            self.app.oublier_la_tache()
            self.arreter_le_rotor()

    def on_unmount(self) -> None:
        """Le filet : ce que le depart de la passe a pose, le demontage le rend.

        Il ne sert pas au chemin nominal -- le parcours eteint le drapeau
        lui-meme, et `E5-5` se monte PAR-DESSUS `E5-4`, qui reste donc dans la
        pile. Il sert aux chemins qui **depilent** au lieu de conclure : un ecran
        retire pendant qu'un drapeau protege laisserait la coque muette a
        `Échap` et a `q`, ce qu'`atelier_scan_parcours` a paye sur son ecran de
        collision (« le fil de travail aurait attendu pour toujours »).

        **L'extinction est CONDITIONNELLE**, et c'est la lecon d'ailleurs :
        demonter l'ecran d'une passe finie APRES qu'une passe suivante est
        partie ferait tomber le drapeau de la passe neuve. On n'eteint donc que
        si l'ecran demonte est encore celui de la tache. Eteindre deux fois ne
        coute rien -- c'est le laisser allume qui coute.
        """
        super().on_unmount()
        self.arreter_le_rotor()
        if getattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None) is self:
            setattr(self.app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, None)
            self.app.oublier_la_tache()

    def rafraichir(self) -> None:
        """Le dessin, **et la traduction du jalon** qui vivait au-dessus.

        **Pourquoi cette classe ne surcharge plus `sur_jalon`, et c'est le
        correctif du 2026-09-06.** Elle le surchargeait, et cette surcharge
        avait emporte avec elle la garde de fil que `EcranExecution.sur_jalon`
        porte -- celle dont le docstring dit qu'elle est placee la « pour une
        raison simple : un atelier qui partirait au fil demain oublierait de la
        reposer ». C'est arrive le jour meme ou l'atelier PDF est parti au fil,
        et par la seule voie que cette formule ne couvrait pas : non pas un
        atelier qui **oublie** de poser la garde, mais un ecran qui la
        **remplace**. Sonde a l'execution sur le parcours reel, trois pages :
        **3 rafraichissements sur 7 hors de la boucle**, un par jalon, chacun
        mutant l'arbre de widgets depuis le fil de `pdf-generer`.

        Le correctif n'ajoute pas une seconde garde -- il **supprime la
        surcharge**, si bien que le jalon passe desormais par celle de la base
        et qu'il n'y a plus rien a oublier. C'est ce que la base offrait deja :
        son `sur_jalon` ignore son argument et rappelle `self.rafraichir()`,
        l'avancement etant lisible sur la surface. `SurfaceExecution` notifie
        ses observateurs avec **son propre** `self.avancement` : l'objet lu ici
        est celui que le jalon portait, et non une copie qui pourrait diverger.

        **La traduction est AU-DESSUS de la garde de taille, et ce n'est pas un
        detail de mise en page.** Le corps qui suit rend la main quand la
        fenetre est trop petite ; y laisser tomber l'etat de la passe le
        figerait sous le plancher 80x24, alors que l'ancienne surcharge l'ecrivait
        quoi qu'il arrive. La regle qui vivait dans `sur_jalon` vit donc ici,
        avec le meme moment.

        **`EPIC11-ARB-134` point 2 reste ou il etait** : `SurfaceExecution`
        remet `faites` a zero a chaque lot, donc c'est le compte du **lot
        courant** -- ce que la passe attend. Quand la remise a zero tombera,
        cette traduction se simplifiera d'autant.
        """
        avancement = self.surface.avancement
        self.passe.pages_du_lot_courant = avancement.faites
        self.passe.temps_restant = avancement.temps_restant
        if self._interruption is not None:
            self._interruption.rafraichir_les_chiffres()
        if not self._assez_grand_au_dernier_dessin:
            return
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = jetons.largeur_utile(self.app.size.width)
        self.poser_les_raccourcis()
        lignes, rang, etats = self.composer(self.app.size.width, ascii_seul)
        self._corps.update(bloc_peint(lignes, largeur, self.app, rang=rang,
                                      etats=etats))
        self.poser_etat(self.passe.ligne_d_etat(self.pas, largeur, ascii_seul))
        # **Deux sauts au-dessus de `EcranExecution.rafraichir`**, et c'est
        # voulu : le sien pose la ligne d'etat du LOT et redessine un widget de
        # journal que cet ecran n'a pas. Appeler `super()` ecraserait la ligne
        # agregee par la ligne du lot, a chaque jalon.
        super(EcranExecution, self).rafraichir()

    def lignes_de_journal_visibles(self) -> int:
        """Combien de lignes de journal tiennent, a la hauteur COURANTE."""
        return lignes_de_journal_visibles(self.hauteur_centrale(),
                                          len(self.passe.lots),
                                          self.journal_deplie)

    # -- l'interruption ------------------------------------------------------

    def ouvrir_l_interruption(self) -> EcranInterruptionDeLaGeneration:
        """Monte `T6-1` PAR-DESSUS. La generation continue derriere.

        L'ecran monte est **retenu** pour que les jalons suivants le
        rafraichissent : c'est ce qui tient l'AC 9.7 (« le chiffre evolue
        pendant que l'ecran est monte »).
        """
        ecran = EcranInterruptionDeLaGeneration(
            self.passe, sur_issue=self.issue_d_interruption)
        self._interruption = ecran
        self.app.descendre(ecran)
        return ecran

    def issue_d_interruption(self, issue: Issue) -> None:
        """La meme repartition que le patron, l'ecran retenu en moins."""
        self._interruption = None
        super().issue_d_interruption(issue)

    def panneau_de_ce_qui_est_ecrit(self) -> Panneau:
        """Les chiffres de la PASSE, pas ceux du lot courant."""
        return panneau_de_la_passe(self.passe)


def ouvrir_la_generation(app, surface: SurfaceExecution,
                         passe: PasseDeGeneration, *,
                         sur_issue: Callable[[Issue], None],
                         objet: str = "") -> EcranGenerationDesPlanches:
    """Monter `E5-4`. `sur_issue` est **requis**.

    Requis, et non `None` par defaut : c'est le finding `K3`, ou des issues
    navigables etaient decoratives parce qu'un point d'appel avait oublie de
    passer son rappel, sans que rien ne le dise.
    """
    ecran = EcranGenerationDesPlanches(surface, passe, sur_issue=sur_issue,
                                       objet=objet)
    # **Le drapeau est pose ICI, et pas au montage de l'ecran.** Ce n'est pas
    # une ceinture de plus : l'appelant enchaine sur le coeur sans rendre la
    # main a la boucle d'evenements, donc `Mount` n'arrive qu'APRES la fin de
    # la passe. Un drapeau pose au montage ne protege donc rien pendant la
    # passe, et se rallume apres elle sans que rien ne l'eteigne.
    setattr(app, ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE, ecran)
    app.tache_en_cours = True
    app.descendre(ecran)
    return ecran
