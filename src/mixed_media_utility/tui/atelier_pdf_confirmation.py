# -*- coding: utf-8 -*-
"""`E5-3` -- la confirmation de l'atelier Pdf (story 11.7, lot F, AC 6).

**C'est le dernier ecran ou rien n'est ecrit sur le disque**, et la ligne d'etat
le dit : elle porte les chiffres de ce qui **va** s'ecrire, suivis de « rien n'a
encore été écrit ». `EPIC11-ARB-4`, verbatim : le panneau chiffre « est
**obligatoire pour toute commande qui ecrit**, et il porte au minimum : ce qui
sera produit (noms de fichiers ou de lots), en quelle quantite (frames, pages),
et ce que cela coute (espace disque, majorant assume comme tel) ».

Cet ecran arrive APRES le conflit de tirage, et ce n'est pas un detail
-----------------------------------------------------------------------
`EPIC11-ARB-172` a **inverse** l'ordre des ecrans, sur la question d'Egan :
« comment sait-on deja que cela va etre le lot 4 si on n'a pas tranche pour
l'ecrasement ou le versionnage ? Ce choix arrive avant non ? »

```
E5-2 reglages -> E5-3b/E5-3c conflit (SI un tirage existe) -> E5-3 -> E5-4
```

**Consequence directe sur ce module** : quand cet ecran se monte, le tirage est
un **fait acquis**, jamais une supposition. Il n'y a donc ici ni resolution, ni
consommation, ni comparaison de tirages : le plan recoit ce que l'ecran
precedent a tranche, et cet ecran l'affiche. :func:`ecrans_du_parcours` dit
l'enchainement, elle ne le decide pas.

Aucun ecran neuf n'est ecrit ici
---------------------------------
`E5-3` **est** un :class:`~mixed_media_utility.tui.execution.EcranChiffre`
(AC 6.1) : le cartouche, le `ChoixExclusif`, la navigation et la ligne d'etat y
sont deja, livres par la story 11.1. Ce module **alimente** cet ecran.
`execution.py` n'est pas modifie -- c'est le module partage par les quatre
ateliers --, et il est **absent de la liste de fichiers de la story**, ce qu'un
test mesure ainsi plutot que par un condensat : la fixture etant deterministe,
une reecriture rendrait exactement les memes octets.

Aucun chiffre n'est rederive
-----------------------------
* les **pages par lot** viennent de
  `page_templates.MiseEnPageMesuree.pages_par_lot`, c'est-a-dire de
  `pdf_composition.page_count_du_lot` (AC 5.10) -- jamais un `glob`, jamais un
  `expected_frame_count`, jamais un `ceil` refait ici ;
* le **format** et le **dpi** sont `page_templates.DEFAULT_PAGE_FORMAT` et
  `pdf_composition.RENDER_DPI_DEFAULT`, comme a l'ecran de reglages ;
* les **noms** sortent de `io.naming.build_sheets_pdf_filename`, seule redaction
  de la convention ;
* la **taille** est un majorant **donne** par l'atelier : c'est un ordre de
  grandeur assume, marque `(majorant)` par le type lui-meme, jamais une
  promesse.

Ce que ce module ne fait pas, et c'est structurel
--------------------------------------------------
* il **n'ecrit rien** et ne touche a aucun fichier : c'est un point de jugement,
  et l'AC 6.7 le mesure aux inodes, au `st_mtime_ns` et par un temoin depose
  dans `planches/` ;
* il **ne resout, ne calcule et ne consomme aucun tirage** (`EPIC11-ARB-92`,
  verbatim d'Egan : « **Il ne faut pas rendre le rang.** ») : le champ
  :attr:`LotAImprimer.rang` traverse **verbatim** jusqu'a `build_sheets_pdf_filename`,
  et une frontiere a l'AST mesure que l'argument de `version_rank=` est cet
  attribut et rien d'autre -- pas une expression, pas une comparaison, pas un
  repli. Le module ne porte pas non plus un mot du vocabulaire des tirages, pas
  meme en prose : la frontiere de la story 11.6 le compte a zero sur tout
  `tui/`, docstrings comprises, et elle a raison de le faire au texte -- un
  ecran qui connaitrait la borne ou la valeur d'origine aurait, de fait, de quoi
  la recalculer ;
* il **n'ouvre aucun champ de saisie** (`EPIC11-ARB-141`) : les noms de planche
  sont **derives et montres**, jamais edites. `E5-3` est le troisieme site
  inerte du depot, apres `E2-3` et `E3-6`, et il l'est ici par **absence** de
  champ plutot que par une edition qui n'atteindrait pas le coeur ;
* il **ne se cable pas lui-meme** : le parcours de l'atelier est monte en un
  seul endroit, par le lot I.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .. import page_templates, pdf_composition
from ..io import naming
from ..io.project_layout import dossier_de_planches
from . import jetons, projet_lecture
from .atelier_extraction_ecriture import (
    LIBELLE_DESTINATION,
    PREFIXE_APPROCHE,
    TITRE_A_ECRIRE,
    taille_lisible,
)
from .atelier_pdf_versions import ordonner_par_lot
from .execution import EcranChiffre
from .noms import ModeleNoms
from .panneau import RIEN_ECRIT, ChoixExclusif, Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Textes d'ecran. En constantes, comme partout dans le paquet : un texte ecrit
# deux fois divergerait, et les frontieres negatives les balayent.
# ---------------------------------------------------------------------------

#: Les libelles des lignes du cartouche, verbatim de la maquette `E5-3`.
#: `LIBELLE_DESTINATION` n'est **pas** redige ici : il est importe de
#: `atelier_extraction_ecriture`, ou il vit deja. Deux confirmations qui
#: nommeraient differemment la meme ligne feraient lire deux choses a
#: l'operateur.
LIBELLE_PLANCHES = "Planches"
LIBELLE_MISE_EN_PAGE = "Mise en page"
LIBELLE_TAILLE = "Taille"

#: Le libelle de la ligne des emplacements (AC 6.6). Elle ne parait que quand
#: une derniere page est partiellement remplie -- voir
#: :func:`ligne_des_emplacements`.
LIBELLE_EMPLACEMENTS = "Emplacements"

#: L'unite des PDF produits. Invariable : « 1 PDF », « 2 PDF ».
UNITE_DES_PDF = "PDF"

#: Les pluriels des cardinaux de cet ecran. Le pluriel suit le compte, jamais un
#: `+ "s"` pose au hasard.
PLURIEL_DES_PAGES = {False: "page", True: "pages"}
PLURIEL_DES_FRAMES = {False: "frame", True: "frames"}
PLURIEL_DES_LOTS = {False: "lot", True: "lots"}
PLURIEL_DES_EMPLACEMENTS = {False: "emplacement", True: "emplacements"}
PLURIEL_DES_VIDES = {False: "vide", True: "vides"}

#: Le separateur des mesures d'une meme ligne : `2 PDF · 28 pages`.
#:
#: **Il est redige ici plutot qu'importe**, et c'est un choix de dependance :
#: `atelier_pdf_versions` porte la meme constante, mais les deux modules sont
#: des ecrans voisins du meme atelier et rien ne doit les faire dependre l'un de
#: l'autre -- c'est le parcours, monte ailleurs, qui les enchaine.
#: `atelier_scan_confirmation` a tranche pareil, pour la meme raison.
SEPARATEUR = " · "

#: Le mot qui nomme le cardinal de la mise en page : `6 f/page`. Verbatim de la
#: maquette, et de l'ecran de reglages qui le montre deja.
UNITE_DU_CARDINAL = "f/page"

#: Le mot qui nomme le dpi dans la ligne de mise en page : `600 dpi`.
UNITE_DU_DPI = "dpi"

#: Le mot qui nomme la marge dans la ligne de mise en page : `marge 0`.
#:
#: **C'est la tete du libelle d'`EPIC11-ARB-34`** -- « Marge de travail », le
#: libelle que `atelier_pdf_reglages.LIBELLE_MARGE` porte a l'ecran de reglages
#: --, reduite parce qu'elle vit ici **au milieu d'une mesure** et non en tete
#: d'une ligne. L'arbitrage impose ce mot-ci et en ecarte un autre, que
#: l'AC 11.3 compte a zero sur tout `tui/`, prose comprise -- il n'est donc pas
#: cite ici. Un banc mesure que les deux redactions ne peuvent pas diverger : le
#: libelle de l'ecran de reglages commence par cette mention.
MENTION_DE_LA_MARGE = "marge"

#: L'indentation des noms de planches sous le cartouche, verbatim de la
#: maquette.
INDENT_DES_NOMS = "  "

#: Les cles des trois issues. Elles ne sont **jamais** affichees : le libelle
#: l'est. Une cle est ce par quoi un test et un ecran se designent la meme issue
#: sans recopier une chaine francaise.
ISSUE_GENERER = "generer"
ISSUE_MODIFIER = "modifier"
ISSUE_ANNULER = "annuler"

#: Les trois libelles, verbatim de la maquette `E5-3` (l. 16 a 18).
LIBELLE_GENERER = "Générer"
LIBELLE_MODIFIER = "Modifier les réglages"
LIBELLE_ANNULER = "Annuler"

#: La DROITE du bandeau se **compose** (`2 lots · 164 frames`) : voir
#: :meth:`EcranPdfConfirmation.objet_du_bandeau`. Elle n'est donc pas une
#: constante, contrairement a celle de `E3-6` -- ici elle depend du plan.

#: La ligne de raccourcis de `E5-3`, verbatim de la maquette (l. 23).
#:
#: **Elle n'est PAS `execution.RACCOURCIS_CONFIRMATION`** (AC 6.3a), et c'est le
#: seul point ou cet ecran s'ecarte de l'ecran partage : la constante commune
#: porte `Tab éditer les noms`, or `EPIC11-ARB-141` a retire l'edition des noms
#: de cet ecran. L'annoncer promettrait une touche qui ne fait rien -- ce que
#: `coque.py:510` documente comme un defaut a part entiere. Les deux issues
#: etaient de poser une ligne propre ou de corriger la constante partagee ;
#: corriger la constante toucherait `execution.py`, que cette story ne modifie
#: pas. C'est donc une ligne propre, et l'ecart sur la constante partagee reste
#: ouvert.
#:
#: **Elle est la grammaire des ecrans de jugement de cet atelier** : `E5-3b`,
#: `E5-3c` et le jugement de la mire portent la meme. Un banc mesure qu'elles ne
#: divergent pas -- deux confirmations du meme atelier qui n'annoncent pas les
#: memes touches sont un defaut, et c'est precisement ce qu'une revue par vague
#: existe pour trouver.
#:
#: **Le repli ASCII l'ALLONGE de cinq colonnes** (`Entree` pour `⏎`), et c'est
#: le regime qui commande le budget : 49 colonnes pour une zone utile de 76.
#: MESURE: 44/49
RACCOURCIS_PDF_CONFIRMATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Ce que la ligne d'etat dit en fin de mesure, verbatim de la maquette `E5-3`
#: (l. 22 : « ... — rien n'a encore été écrit »).
#:
#: **Derivee de `panneau.RIEN_ECRIT`, jamais recopiee.** La phrase existe une
#: fois dans le depot ; ce qui change ici est sa place dans la ligne -- elle est
#: en queue d'une mesure, donc sans majuscule ni point final. Une seconde
#: redaction divergerait de la premiere au premier ajustement d'accent, et une
#: phrase desaccentuee a la source rendrait le repli ASCII indistinguable du
#: nominal.
QUEUE_RIEN_ECRIT = RIEN_ECRIT[0].lower() + RIEN_ECRIT[1:].rstrip(".")

#: Le lien entre la mesure et sa queue, verbatim de la maquette.
LIAISON_DE_LA_MESURE = " — "

#: Les cles des ecrans que la validation des reglages peut monter (AC 6.8).
#: Ce sont les identifiants des maquettes, et ils servent a mesurer un
#: **enchainement** sans monter quoi que ce soit -- le cablage est ailleurs.
ECRAN_DU_CONFLIT = "E5-3b"
ECRAN_DU_TIRAGE_SCANNE = "E5-3c"
ECRAN_DE_LA_CONFIRMATION = "E5-3"


class PlanMalForme(ValueError):
    """Le plan viole un contrat que la revue ne devrait pas avoir a trouver."""


def _accorder(valeur: int, pluriels: dict) -> str:
    """« 1 lot », « 2 lots ». Le pluriel suit le compte."""
    return f"{valeur} {pluriels[abs(valeur) > 1]}"


# ---------------------------------------------------------------------------
# Le plan : ce qui SERA ecrit, avant que quoi que ce soit le soit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LotAImprimer:
    """Un lot coche a `E5-1`, tel que la confirmation a besoin de le connaitre.

    Tout y est **donne** : cet ecran arrive apres le conflit, donc il n'a rien a
    resoudre. Les quatre derniers champs sont des faits acquis a l'ecran
    precedent, et non des etats a deduire ici.
    """

    lot_id: str
    #: Le rush du lot. Il n'entre pas dans le nom du PDF (`EPIC7-ARB-91`), mais
    #: `build_sheets_pdf_filename` le prend a sa signature et tous les appelants
    #: l'ont sous la main.
    rush_id: str
    #: Le cardinal de frames du lot, celui que `E5-1` a compte.
    frames: int
    #: Ce que le nom du PDF portera, **deja resolu par le coeur** et transmis
    #: verbatim a `build_sheets_pdf_filename`. `None` est la valeur du tirage
    #: d'origine : c'est la convention du **nom**, celle qu'`io.naming` pose, et
    #: cet ecran ne la traduit pas -- il la relaie.
    #:
    #: **Aucune valeur par defaut n'aurait de sens ici** au-dela de celle-la :
    #: un defaut ferait de l'oubli de cablage un silence, et un ecran qui
    #: inventerait un numero de tirage est le pire mode de panne du produit --
    #: deux feuilles de papier differentes portant le meme numero, et une fois
    #: l'encre seche aucun fichier ne rattrape cela.
    rang: int | None = None
    #: Vrai quand un tirage de ce lot existait deja, c'est-a-dire quand l'ecran
    #: de conflit s'est monte pour lui. **Un fait donne**, jamais deduit du
    #: champ ci-dessus.
    tirage_anterieur: bool = False
    #: Vrai quand ce tirage anterieur a ete scanne (`EPIC11-ARB-176`). Il
    #: departage `E5-3b` et `E5-3c` dans :func:`ecrans_du_parcours`, et rien
    #: d'autre : sur cet ecran-ci, le tirage est deja tranche.
    scanne: bool = False


@dataclass(frozen=True)
class PlancheAEcrire:
    """Un PDF que la passe ecrira, avec son compte de pages et son nom.

    `pages` vient de la mise en page **mesuree par le coeur**, jamais d'un
    arrondi refait ici : le papier ne se partage pas entre deux lots, et c'est
    `page_templates` qui le sait.
    """

    lot_id: str
    #: Le nom du fichier, derive par `io.naming.build_sheets_pdf_filename`.
    nom: str
    pages: int
    frames: int
    #: Les emplacements de la derniere page qui resteront vides (AC 6.6). Zero
    #: quand le lot remplit ses pages exactement.
    vides: int

    @property
    def emplacements(self) -> int:
        """Les emplacements que ce PDF ouvre, vides compris."""
        return self.frames + self.vides


@dataclass(frozen=True)
class PlanDesPlanches:
    """Ce que `E5-3` montre : les planches, leur mise en page, leur cout.

    **L'ordre des planches est celui des lots coches**, c'est-a-dire celui que
    `E5-1` a rendu. Il n'est jamais retrie ici, et c'est sur lui qu'un banc
    verifie le rang d'une cible -- sur la liste que le code **parcourt**, jamais
    sur celle qu'une fabrique croit ecrire.
    """

    planches: tuple[PlancheAEcrire, ...] = ()
    #: La mise en page retenue a `E5-2`, **mesuree par le coeur**. Elle porte
    #: son orientation, son cardinal, son `template_id` et ses pages par lot.
    mise_en_page: page_templates.MiseEnPageMesuree | None = None
    #: Le preset de marge retenu a `E5-2`, tel que `page_templates` le nomme.
    marge: str = page_templates.DEFAULT_MARGIN_PRESET
    #: Le dossier du projet, dont seul le **nom** est affiche.
    dossier_projet: Path | None = None
    #: Le majorant de poids des PDF, en octets, ou `None` quand il n'est pas su.
    #: C'est un **ordre de grandeur** assume comme tel -- la ligne le marque
    #: `(majorant)` --, jamais une promesse, et il est **donne** : ce module ne
    #: pese rien.
    octets_majorants: int | None = None

    # -- lecture ------------------------------------------------------------

    @property
    def pdf(self) -> int:
        """Le nombre de fichiers PDF : un par lot coche."""
        return len(self.planches)

    @property
    def pages(self) -> int:
        """Le total des planches, **somme des comptes par lot**."""
        return sum(planche.pages for planche in self.planches)

    @property
    def frames(self) -> int:
        """Le total des frames imprimees."""
        return sum(planche.frames for planche in self.planches)

    @property
    def emplacements(self) -> int:
        """Le total des emplacements ouverts, vides compris."""
        return sum(planche.emplacements for planche in self.planches)

    @property
    def vides(self) -> int:
        """Le total des emplacements qui resteront vides."""
        return sum(planche.vides for planche in self.planches)

    @property
    def vides_par_planche(self) -> tuple[int, ...]:
        """Les vides **dans l'ordre des planches** (AC 6.6).

        C'est la repartition, et c'est elle qui compte : un total juste avec une
        repartition fausse est le defaut exact que cette AC existe pour
        attraper. Quatre vides peuvent tomber deux par deux dans deux PDF, ou
        tous les quatre dans un seul, et l'operateur qui va imprimer n'a pas la
        meme feuille a jeter dans les deux cas.
        """
        return tuple(planche.vides for planche in self.planches)

    @property
    def noms(self) -> tuple[str, ...]:
        """Les noms des fichiers, dans l'ordre des planches."""
        return tuple(planche.nom for planche in self.planches)

    @property
    def destination(self) -> str:
        """Le dossier des tirages, relatif au projet -- `projet_demo/planches/`.

        Vide quand aucun projet n'est donne : un chemin devine serait pire
        qu'une ligne absente, puisque c'est la seule chose qui dit ou
        l'operateur ira chercher ses fichiers.

        **RESOLU par le coeur** (`EPIC11-ARB-225`), pas nomme : un projet
        ancien porte ses planches sous le dossier d'avant, et cet ecran est
        precisement celui ou l'operateur lit ou ses fichiers vont atterrir.
        """
        if self.dossier_projet is None:
            return ""
        dossier = dossier_de_planches(self.dossier_projet)
        return f"{Path(self.dossier_projet).name}/{dossier.name}/"


def preparer_le_plan(dossier_projet: Path | str | None, *, project_id: str,
                     lots: Sequence[LotAImprimer],
                     mise_en_page: page_templates.MiseEnPageMesuree,
                     marge: str = page_templates.DEFAULT_MARGIN_PRESET,
                     octets_majorants: int | None = None) -> PlanDesPlanches:
    """Assembler le plan de `E5-3` depuis les lots coches et la mise en page.

    :param dossier_projet: le dossier du projet ouvert. Seul son **nom** est
        affiche, et rien n'y est lu : ce module ne touche a aucun fichier.
    :param project_id: l'identifiant du projet, tel que `build_sheets_pdf_filename`
        l'abrege.
    :param lots: les lots coches a `E5-1`, **dans leur ordre**, chacun portant
        ce que l'ecran de conflit a deja tranche.
    :param mise_en_page: la mise en page retenue a `E5-2`, **mesuree** : elle
        porte les pages par lot (AC 5.10), le cardinal, l'orientation et le
        `template_id` qui nomme les fichiers.
    :param marge: le preset de marge retenu a `E5-2`.
    :param octets_majorants: le majorant de poids, **donne**.

    **L'appariement lots / pages est POSITIONNEL, et c'est le seul de ce
    module.** `MiseEnPageMesuree.pages_par_lot` est rendu « dans l'ordre des
    lots recus » par `page_templates.bilan_de_domination`, c'est-a-dire dans
    l'ordre de la sequence que l'ecran de reglages lui a passee -- la meme que
    celle-ci. Un appariement positionnel est exactement la classe de defaut
    payee trois fois par ce depot (mutants `M33` de la 5.6, `M25` de la 5.7,
    cinq survivants de la 5.8), et une permutation y ecrirait les pages d'un lot
    sur un autre **sans que rien ne le dise**. Deux gestes le bornent :

    * un desaccord de **cardinal** est refuse nommement plutot que tronque par
      un `zip` silencieux -- c'est le seul desaccord qu'on puisse voir d'ici ;
    * un banc mesure la correspondance sur **trois** lots aux pages distinctes,
      la cible au milieu, sur la liste que ce code parcourt.
    """
    pages_par_lot = mise_en_page.pages_par_lot
    if len(pages_par_lot) != len(lots):
        raise PlanMalForme(
            f"La mise en page mesure {len(pages_par_lot)} lot(s) quand la passe "
            f"en porte {len(lots)}. L'appariement des pages aux lots est "
            "positionnel : un cardinal different ecrirait les pages d'un lot "
            "sur un autre."
        )
    cardinal = mise_en_page.frames_per_page
    planches = []
    for lot, pages in zip(lots, pages_par_lot):
        # `vides` se derive des deux comptes que le coeur a rendus, et non d'un
        # second arrondi : `pages` vient de `page_count_du_lot`, `frames` du
        # comptage de `E5-1`. Un `max(0, ...)` plutot qu'une soustraction nue --
        # un lot dont on aurait recu plus de frames que d'emplacements est un
        # etat que ce module ne sait pas commenter, et « -3 vides » serait pire
        # que rien.
        vides = max(0, pages * cardinal - lot.frames)
        planches.append(PlancheAEcrire(
            lot_id=lot.lot_id,
            nom=naming.build_sheets_pdf_filename(
                project_id, lot.rush_id, lot.lot_id,
                # **Le tirage traverse VERBATIM** (`EPIC11-ARB-92`). Une
                # frontiere a l'AST mesure que cet argument est cet attribut et
                # rien d'autre : ni une comparaison, ni un repli, ni un calcul.
                version_rank=lot.rang,
                # Le `template_id` DEJA mesure par le coeur, jamais un second
                # calcul : le nom suit le gabarit qui a produit les pages
                # (`EPIC11-ARB-171`).
                template_id=mise_en_page.template_id),
            pages=pages,
            frames=lot.frames,
            vides=vides))
    return PlanDesPlanches(
        planches=tuple(planches),
        mise_en_page=mise_en_page,
        marge=marge,
        dossier_projet=None if dossier_projet is None else Path(dossier_projet),
        octets_majorants=octets_majorants)


# ---------------------------------------------------------------------------
# L'enchainement des ecrans (AC 6.8)
# ---------------------------------------------------------------------------


def ecrans_du_parcours(lots: Sequence[LotAImprimer]) -> tuple[str, ...]:
    """Les ecrans que la validation de `E5-2` monte, **dans l'ordre**.

    `EPIC11-ARB-172` : le conflit se tranche **avant** la confirmation, et il se
    tranche **par lot** -- `resolve_sheets_version_rank` prend un `lot_id`, donc
    une passe ou trois lots ont deja des tirages montre l'ecran de conflit trois
    fois (AC 7.13). Quand aucun lot n'en a, aucun ecran de conflit ne se monte
    et la confirmation dit ce qu'elle a a dire sans rien supposer.

    Le depart entre `E5-3b` et `E5-3c` se lit sur le seul champ qui le porte :
    un tirage scanne ne peut plus etre ecrase du tout (`EPIC11-ARB-176`), donc
    il ne montre pas le meme ecran.

    **L'ordre est celui du PRODUIT, et il n'est pas celui de l'argument**
    (finding `C2-6`, second ordre, couche 2 du 2026-09-02). Les lots arrivent
    ici dans l'ordre de `E5-1` -- l'ordre du manifeste, c'est-a-dire celui de
    premiere creation --, alors que le parcours monte les ecrans de conflit dans
    l'ordre **par lot** qu'`EPIC11-ARB-177` a tranche. Deux redactions du meme
    enchainement rendaient donc deux ordres, et celle-ci etait la seule mesuree.
    Le tri se lit de `atelier_pdf_versions.ordonner_par_lot`, l'unique redaction
    de la regle : la recopier ici en ferait une seconde, qui divergerait le jour
    ou l'ordre change.

    **Cette fonction ne monte rien.** Elle dit l'enchainement, pour qu'il se
    mesure en ensemble exact sans que le parcours ait a etre cable -- le cablage
    se fait en un seul endroit, ailleurs. La boucle va **jusqu'au bout** : une
    sortie anticipee ferait disparaitre les conflits des lots suivants en
    silence, et c'est la classe de defaut qu'un mutant `continue` -> `break`
    produit.
    """
    ecrans = []
    for lot in ordonner_par_lot(lots):
        if not lot.tirage_anterieur:
            continue
        ecrans.append(ECRAN_DU_TIRAGE_SCANNE if lot.scanne
                      else ECRAN_DU_CONFLIT)
    ecrans.append(ECRAN_DE_LA_CONFIRMATION)
    return tuple(ecrans)


# ---------------------------------------------------------------------------
# `E5-3` -- le cartouche, ses noms, ses issues
# ---------------------------------------------------------------------------


def _repartition(valeurs: Sequence[int], total: int) -> str:
    """`2 + 2`, ou `4` quand il n'y a qu'un seul terme.

    Un seul terme n'a pas de repartition a montrer -- `4 (4)` serait du bruit
    --, exactement comme `atelier_scan_confirmation._somme_par_lot` le fait pour
    `E3-6`.
    """
    if len(valeurs) <= 1:
        return f"{total}"
    return " + ".join(str(valeur) for valeur in valeurs)


def ligne_des_planches(plan: PlanDesPlanches) -> LigneChiffree:
    """`Planches   2 PDF · 28 pages` -- verbatim de la maquette."""
    return LigneChiffree(
        LIBELLE_PLANCHES,
        f"{plan.pdf} {UNITE_DES_PDF}{SEPARATEUR}"
        f"{_accorder(plan.pages, PLURIEL_DES_PAGES)}")


def ligne_des_emplacements(plan: PlanDesPlanches) -> LigneChiffree | None:
    """`168 emplacements · 4 vides (2 + 2)`, ou `None` quand tout est plein.

    **Une derniere page partiellement remplie est dite, pas cachee** (AC 6.6),
    et ce qui se dit est la **repartition** autant que le total : `4 vides`
    tombant deux par deux dans deux PDF n'est pas la meme chose que quatre vides
    dans un seul.

    **Elle n'est posee que si des vides existent**, et jamais a zero : « 0 vide »
    sur une passe qui remplit exactement ses pages serait du bruit sur le regime
    nominal, et le cartouche de la maquette est plein a la ligne pres. C'est la
    meme discipline que `atelier_scan_confirmation.ligne_des_deja_ecrites`.
    """
    vides = plan.vides
    if vides <= 0:
        return None
    return LigneChiffree(
        LIBELLE_EMPLACEMENTS,
        f"{_accorder(plan.emplacements, PLURIEL_DES_EMPLACEMENTS)}{SEPARATEUR}"
        f"{_accorder(vides, PLURIEL_DES_VIDES)}"
        f" ({_repartition(plan.vides_par_planche, vides)})")


def ligne_de_la_mise_en_page(plan: PlanDesPlanches) -> LigneChiffree:
    """`6 f/page · paysage · A4 · 600 dpi · marge 0` -- cinq faits, cinq sources.

    Les deux premiers sont ceux de la mise en page **mesuree** par le coeur, les
    deux suivants les constantes que l'ecran de reglages lit deja
    (`page_templates.DEFAULT_PAGE_FORMAT`, `pdf_composition.RENDER_DPI_DEFAULT`),
    le dernier le preset retenu. **Aucun n'est recopie**, et c'est ce qui
    distingue cette ligne d'un rappel decoratif : le gabarit d'un ancien tirage
    ne se deduit pas de son nom -- le fragment que le nom porte ne dit ni la
    marge ni la version de geometrie --, donc ce que cette ligne decrit est le
    plan **courant** et rien d'autre.
    """
    mise = plan.mise_en_page
    if mise is None:
        return LigneChiffree(LIBELLE_MISE_EN_PAGE, "")
    return LigneChiffree(LIBELLE_MISE_EN_PAGE, SEPARATEUR.join([
        f"{mise.frames_per_page} {UNITE_DU_CARDINAL}",
        mise.orientation,
        page_templates.DEFAULT_PAGE_FORMAT,
        f"{pdf_composition.RENDER_DPI_DEFAULT} {UNITE_DU_DPI}",
        f"{MENTION_DE_LA_MARGE} {plan.marge}",
    ]))


def ligne_de_la_taille(plan: PlanDesPlanches) -> LigneChiffree | None:
    """`Taille   ~ 470 Mo   (majorant)`, ou `None` quand le poids n'est pas su.

    **Un ordre de grandeur, jamais une promesse.** Le prefixe `~` et la mention
    `(majorant)` -- posee par `LigneChiffree` elle-meme, pas ecrite ici -- sont
    les deux canaux qui le disent, et le rendu de taille est celui que
    l'explorateur porte deja : deux formats du meme chiffre dans la meme
    interface divergeraient au premier ajustement.

    Un poids inconnu fait **disparaitre** la ligne plutot que de rendre `0 Mo` :
    annoncer zero serait affirmer qu'on a pese.
    """
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is None:
        return None
    valeur, _, unite = lisible.partition(" ")
    return LigneChiffree(LIBELLE_TAILLE, PREFIXE_APPROCHE + valeur, unite,
                         majorant=True)


def ligne_de_la_destination(plan: PlanDesPlanches) -> LigneChiffree | None:
    """`Destination   projet_demo/planches/`, ou `None` sans projet."""
    destination = plan.destination
    if not destination:
        return None
    return LigneChiffree(LIBELLE_DESTINATION, destination)


def lignes_du_cartouche(plan: PlanDesPlanches) -> list[LigneChiffree]:
    """Les lignes chiffrees de `E5-3`, dans l'ordre de la maquette.

    Ce qui sera produit, puis ce que cela remplit, puis ce que cela coute, puis
    ou ca va. Les lignes conditionnelles disparaissent au lieu de rendre un
    zero : « un champ que la source ne porte pas est **omis** » (`DESIGN.md`
    section 3).
    """
    lignes = [ligne_des_planches(plan)]
    for ligne in (ligne_des_emplacements(plan), ligne_de_la_mise_en_page(plan),
                  ligne_de_la_taille(plan), ligne_de_la_destination(plan)):
        if ligne is not None:
            lignes.append(ligne)
    return lignes


def noms_des_planches(plan: PlanDesPlanches,
                      largeur: int = jetons.LARGEUR_PLANCHER,
                      ascii_seul: bool = False) -> list[str]:
    """**La liste PLATE des fichiers produits**, un par ligne.

    Egan, 2026-09-02, verbatim : « mets juste la liste de toutes les planches
    produites. Ne regroupe pas par lot et tirage, c'est trop lourd a lire. » Le
    regroupement precedent posait deux lignes et trois colonnes par lot pour
    dire un nom ; il est parti, et rien ne le remplace -- ce qu'il annoncait se
    relit **dans le nom**, qui est de toute facon le seul endroit ou il se
    relira apres coup, sur le disque.

    **Aucun de ces noms n'est editable** (`EPIC11-ARB-141`) : ce sont des lignes
    de texte, pas des champs. C'est pour cela qu'ils vivent dans `Panneau.noms`
    et non dans un `ModeleNoms` -- le second est le modele de l'edition, et
    l'ecran en recoit un **vide**.

    L'abregement passe par `jetons.abreger_nom`, qui coupe **au milieu** : un
    nom coupe par la fin perdrait sa queue, c'est-a-dire exactement la partie
    qui distingue deux tirages du meme lot.
    """
    budget = jetons.largeur_de_cartouche(largeur) - len(INDENT_DES_NOMS)
    return [INDENT_DES_NOMS + jetons.abreger_nom(nom, budget, ascii_seul)
            for nom in plan.noms]


def panneau_de_la_confirmation(plan: PlanDesPlanches,
                               largeur: int = jetons.LARGEUR_PLANCHER,
                               ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E5-3` : ses lignes chiffrees, puis la liste des noms."""
    return Panneau(TITRE_A_ECRIRE, lignes_du_cartouche(plan),
                   noms=noms_des_planches(plan, largeur, ascii_seul))


def issues_de_la_confirmation(plan: PlanDesPlanches) -> ChoixExclusif:
    """Les trois issues de `E5-3`. Une seule ecrit, et le curseur ne la vise pas.

    **La fleche se pose sur « Modifier les réglages », jamais sur « Générer »**,
    et cela ne se reecrit pas ici : c'est un invariant leve a la construction par
    :class:`panneau.ChoixExclusif` (`EPIC11-ARB-7` puis `EPIC11-ARB-45`), qui
    **place** le curseur sur la premiere issue qui n'ecrit pas. On ne declenche
    pas une ecriture par reflexe, et depuis que la validation retient en un seul
    geste, un curseur pose au montage sur « Générer » rendrait l'ecriture
    atteignable en **une** frappe.

    Le rendu est **une ligne par issue, la fleche seule** (`EPIC11-ARB-45`,
    `EPIC11-ARB-126` : « Flèche seule ! C'est uniquement dans les listes à
    cocher qu'on trouve les deux »), ce que `ChoixExclusif.rendu` fait deja.

    L'ordre est celui de la deliberation, et il ne se reordonne pas quand le
    curseur se deplace : generer, revenir aux reglages, renoncer.

    Le plan n'entre dans aucun libelle : les trois sont ceux de la maquette, et
    l'argument est pris pour que la signature ne change pas le jour ou l'un
    d'eux porterait un chiffre -- comme `E3-6` le fait deja de sa premiere
    issue.
    """
    return ChoixExclusif([
        Issue(ISSUE_GENERER, LIBELLE_GENERER, ecrit=True),
        Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER),
        Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
    ])


def mesure_de_la_confirmation(plan: PlanDesPlanches) -> str:
    """La ligne d'etat de `E5-3` : **une mesure**, verbatim de la maquette.

    `2 PDF · 28 pages · ~ 470 Mo — rien n'a encore été écrit` (l. 22).

    **C'est le dernier ecran ou rien n'est ecrit**, et la queue de cette ligne
    est le seul endroit qui le dit a l'operateur au moment ou il decide. Elle
    n'est jamais omise : le majorant, lui, disparait quand il n'est pas su --
    le cartouche le dit deja, et la ligne d'etat ne porte que ce qu'elle mesure.

    `EPIC11-ARB-56` : aucune touche, aucun motif de conception, aucun nombre de
    limite. Un constat, et rien d'autre.
    """
    parts = [f"{plan.pdf} {UNITE_DES_PDF}",
             _accorder(plan.pages, PLURIEL_DES_PAGES)]
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is not None:
        parts.append(PREFIXE_APPROCHE + lisible)
    return SEPARATEUR.join(parts) + LIAISON_DE_LA_MESURE + QUEUE_RIEN_ECRIT


def bandeau_du_plan(plan: PlanDesPlanches) -> str:
    """La DROITE du bandeau : `2 lots · 164 frames`, verbatim de la maquette.

    Elle compte les **lots** et les **frames** la ou la ligne d'etat compte les
    PDF et les pages : le bandeau dit ce qu'on travaille, la ligne d'etat ce
    qu'on va produire. Les deux se lisent du meme plan.
    """
    return (f"{_accorder(plan.pdf, PLURIEL_DES_LOTS)}{SEPARATEUR}"
            f"{_accorder(plan.frames, PLURIEL_DES_FRAMES)}")


# ---------------------------------------------------------------------------
# L'ecran
# ---------------------------------------------------------------------------


class EcranPdfConfirmation(EcranChiffre):
    """`E5-3` -- le point de jugement de l'atelier Pdf. **Rien n'est ecrit.**

    Elle herite d'`EcranChiffre` et n'ecrit **pas** un second point de jugement
    (AC 6.1). Ce qu'elle ajoute lui est propre : la liste plate des noms **dans**
    le cartouche, sa ligne d'etat mesuree, sa ligne de raccourcis sans `Tab`, et
    la droite de son bandeau.

    **Aucun nom n'est editable** : le `ModeleNoms` est **vide**, donc `Tab` n'a
    aucune destination et `EcranChiffre.traiter` le rend inerte de lui-meme --
    ce n'est pas une garde ajoutee ici, c'est la consequence de ne pas donner de
    noms editables. La ligne de raccourcis ne l'annonce pas non plus, et les
    deux vont ensemble : une touche annoncee et inerte est le defaut que
    `coque.py:510` documente.
    """

    titre = projet_lecture.PDF

    #: **Un ATTRIBUT de classe, jamais une `@property`.** La garde de paquet de
    #: `test_repli_ascii.py` balaye les sous-classes de `Palier` et lit
    #: `classe.raccourcis` **au niveau de la classe** : une propriete y rendrait
    #: l'objet `property` et ferait echapper l'ecran a la mesure. Meme forme, et
    #: meme motif, que les dix ecrans `atelier_scan_*`.
    raccourcis = RACCOURCIS_PDF_CONFIRMATION

    #: **Un passage, pas une station** : un point de jugement franchi ne doit
    #: pas rester sur le chemin du retour. C'est deja la valeur qu'`EcranChiffre`
    #: pose ; elle est redite parce que c'est une propriete du parcours et non
    #: un detail d'implementation.
    TRANSITOIRE = True

    def __init__(self, plan: PlanDesPlanches, *,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        super().__init__(panneau_de_la_confirmation(plan),
                         issues_de_la_confirmation(plan),
                         # **Vide, et c'est le sujet d'`EPIC11-ARB-141`** : les
                         # noms de planche ne sont pas des champs. Ils vivent
                         # dans le cartouche, par `Panneau.noms`.
                         noms=ModeleNoms(),
                         sur_issue=sur_issue)
        #: Le plan montre. C'est lui qui porte les chiffres ; l'ecran n'en
        #: recalcule aucun.
        self.plan = plan

    # -- rendu ---------------------------------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche **avec sa liste de noms**, a la largeur courante.

        `EcranChiffre` rend un panneau **sans** ses noms -- chez lui les noms
        sont des widgets a part, pour qu'un nom refuse puisse porter sa propre
        couleur. Ici aucun nom n'est editable, donc aucun ne peut etre refuse :
        la liste redevient du texte de cartouche, et c'est `Panneau.rendu` qui
        la pose apres une ligne vide, comme la maquette la dessine.

        Le panneau est recompose a la largeur courante plutot que garde tel
        quel : c'est cette largeur qui borne l'abregement des noms, et
        `ascii_seul` **precede la mesure** -- `…` vaut une colonne, `...` en vaut
        trois.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = self.app.size.width
        return panneau_de_la_confirmation(
            self.plan, largeur, ascii_seul).rendu(largeur, ascii_seul)

    def objet_du_bandeau(self) -> str:
        """`2 lots · 164 frames` -- compose du plan, jamais recu.

        Cet ecran **est** celui de l'atelier Pdf et son objet varie avec la
        passe : le recevoir a la construction ferait recopier la composition au
        cablage, donc diverger de la maquette au premier ajustement.
        """
        return bandeau_du_plan(self.plan)

    def etat(self) -> str:
        """La ligne d'etat : la mesure de la passe, et « rien n'a encore été écrit ».

        Le regime de refus de la classe de base passe en premier -- c'est le
        moment ou l'operateur a besoin d'autre chose que le total. Le regime
        d'edition, lui, ne peut pas se presenter : il n'y a aucun nom a editer.
        """
        if self._refus_annonce is not None:
            return super().etat()
        return mesure_de_la_confirmation(self.plan)


__all__ = [
    "ECRAN_DE_LA_CONFIRMATION",
    "ECRAN_DU_CONFLIT",
    "ECRAN_DU_TIRAGE_SCANNE",
    "INDENT_DES_NOMS",
    "ISSUE_ANNULER",
    "ISSUE_GENERER",
    "ISSUE_MODIFIER",
    "LIAISON_DE_LA_MESURE",
    "LIBELLE_ANNULER",
    "LIBELLE_EMPLACEMENTS",
    "LIBELLE_GENERER",
    "LIBELLE_MISE_EN_PAGE",
    "LIBELLE_MODIFIER",
    "LIBELLE_PLANCHES",
    "LIBELLE_TAILLE",
    "MENTION_DE_LA_MARGE",
    "PLURIEL_DES_EMPLACEMENTS",
    "PLURIEL_DES_FRAMES",
    "PLURIEL_DES_LOTS",
    "PLURIEL_DES_PAGES",
    "PLURIEL_DES_VIDES",
    "QUEUE_RIEN_ECRIT",
    "RACCOURCIS_PDF_CONFIRMATION",
    "SEPARATEUR",
    "UNITE_DES_PDF",
    "UNITE_DU_CARDINAL",
    "UNITE_DU_DPI",
    "EcranPdfConfirmation",
    "LotAImprimer",
    "PlanDesPlanches",
    "PlanMalForme",
    "PlancheAEcrire",
    "bandeau_du_plan",
    "ecrans_du_parcours",
    "issues_de_la_confirmation",
    "ligne_de_la_destination",
    "ligne_de_la_mise_en_page",
    "ligne_de_la_taille",
    "ligne_des_emplacements",
    "ligne_des_planches",
    "lignes_du_cartouche",
    "mesure_de_la_confirmation",
    "noms_des_planches",
    "panneau_de_la_confirmation",
    "preparer_le_plan",
]
