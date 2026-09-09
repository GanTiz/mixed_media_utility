# -*- coding: utf-8 -*-
"""Le PARCOURS de l'atelier Pdf : ce qui relie les huit modules d'ecran.

Story 11.7, lot de cablage. Les sept modules `atelier_pdf_*` ont ete ecrits par
sept lots differents, chacun avec **interdiction de toucher a `atelier_pdf.py`**
-- c'etait le decoupage, et il ferme le point de contention que `CLAUDE.md`
demande de fermer « par le decoupage plutot que par la procedure de commit ».
Le prix de ce decoupage est qu'aucun des sept ecrans n'etait joignable : chacun
declarait son rappel manquant plutot que de le taire, et le registre
`tests/unit/tui/test_rappels_cables.py` en portait quatre. Ce module est
l'endroit unique ou ces quatre rappels s'injectent.

**L'ordre du parcours n'est pas un choix de ce module, il est impose** :

* `EPIC11-ARB-172` -- le conflit de tirage se monte **AVANT** la confirmation.
  Verbatim d'Egan : « comment sait-on deja que cela va etre le lot 4 si on n'a
  pas tranche pour l'ecrasement ou le versionnage ? Ce choix arrive avant non ? »
  Le numero entre dans le nom du fichier, dans l'etiquette imprimee et dans le
  code-barres : quand la confirmation s'affiche, il doit etre un **fait** ;
* `EPIC11-ARB-177` -- l'ecran de conflit se monte **par lot**, dans l'ordre
  **par lot** (reponse d'Egan du 2026-09-02, mot pour mot : « Par lot »).
  L'issue de masse emporte les suivants et **saute les tirages scannes en le
  disant** ;
* `EPIC11-ARB-28` -- l'atelier a deux entrees, donc il commence par son menu.

**Ce que ce module ne fait pas, et c'est structurel :**

* il **n'importe jamais `cli`** (frontiere de la story 11.4b) : le point
  d'entree de coeur est `mixed_media_utility.makepdf` ;
* il **ne calcule aucun numero de tirage** et n'en lit aucun du disque. Les deux
  nombres qu'un ecran de conflit affiche viennent de `makepdf.etat_des_tirages`,
  **deja resolus**, et la frontiere
  `test_aucun_module_de_la_TUI_ne_CALCULE_un_rang` compte a zero les noms des
  fonctions de `pdf_composition` qui les produisent ;
* il **ne pagine pas** et ne compose aucun nom de fichier : les pages viennent
  de `page_templates.MiseEnPageMesuree`, les noms de `io.naming`.

**La boucle multi-lots vit ici** (tache I2 de la fiche), sur le patron exact
d'`atelier_extraction_ecriture.executer_le_plan` et de
`atelier_scan_ecriture.ecrire_les_lots` : un appel du coeur par lot, un echec
qui n'annule pas les lots deja ecrits, et une interruption consultee **entre
deux lots**. C'est :func:`executer_les_lots`, et elle est pure -- elle ne monte
aucun ecran, ce qui la rend mesurable sans application.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .. import makepdf, page_templates, pdf_composition
from ..io import extraction_manifest, naming, pdf_manifest, project_layout
from . import atelier_pdf, projet_lecture
from .atelier_extraction_ecriture import (
    _lancer_apres_le_dessin,
    journal_du_produit,
)
from .atelier_pdf import EcranPdfMenu
from .atelier_pdf_calibration import (
    FormulaireDeLaMire,
    ISSUE_ANNULER as MIRE_ANNULER,
    ISSUE_AUTRE_CHAINE as MIRE_AUTRE_CHAINE,
    ISSUE_GENERER as MIRE_GENERER,
    ISSUE_MODIFIER as MIRE_MODIFIER,
    ISSUE_REMPLACER as MIRE_REMPLACER,
    SUITE_AUTRE_MIRE,
    SUITE_DOSSIER as MIRE_SUITE_DOSSIER,
    SUITE_PLANCHES,
    chemin_de_la_mire,
    mire_presente,
    nom_de_la_mire,
    ouvrir_la_confirmation as ouvrir_la_confirmation_de_la_mire,
    ouvrir_la_generation as ouvrir_la_generation_de_la_mire,
    ouvrir_le_conflit as ouvrir_le_conflit_de_la_mire,
    ouvrir_le_resultat as ouvrir_le_resultat_de_la_mire,
    ouvrir_les_reglages as ouvrir_les_reglages_de_la_mire,
)
from .atelier_pdf_confirmation import (
    ISSUE_ANNULER,
    ISSUE_GENERER,
    ISSUE_MODIFIER,
    EcranPdfConfirmation,
    LotAImprimer,
    PlanMalForme,
    bandeau_du_plan,
    preparer_le_plan,
)
from .atelier_pdf_execution import (
    UNITE,
    EcranGenerationDesPlanches,
    LotEnGeneration,
    PasseDeGeneration,
    en_tete_de_lot,
    horodater,
    ligne_de_page,
    ouvrir_la_generation,
)
from .atelier_pdf_lots import (
    EcranLotsAPlanches,
    ListeDeLots,
    LotsMalFormes,
    Validation,
)
from .atelier_pdf_reglages import (
    EcranReglagesDesPlanches,
    LotAPlanches,
    ReglagesDesPlanches,
)
from .atelier_pdf_resultat import (
    LIBELLE_EMPLACEMENT,
    LIBELLE_GABARIT,
    LIBELLE_MANIFEST,
    SUITE_AUTRES_LOTS,
    SUITE_CALIBRATION,
    SUITE_DOSSIER,
    PlancheEcrite,
    TableDesEcrits,
    ouvrir_le_dossier_des_planches,
    ouvrir_le_resultat,
)
from .atelier_pdf_versions import (
    CLE_ANNULER,
    CLE_MASSE,
    CLE_REMPLACER,
    CLE_RETIRER_DE_LA_PASSE,
    EcranConflitDeTirage,
    EcranRangsEpuises,
    PasseDeConflits,
    TirageEnConflit,
    conflit_du_tirage,
    ordonner_par_lot,
)
from .coque import EcranPasEncore
from .execution import EcranRefus, SurfaceExecution
from .panneau import Issue

# ===========================================================================
# Les deux decisions qu'un ecran de conflit rend, et rien de plus
# ===========================================================================

#: Ecrire a cote de ce qui existe. C'est la sortie **non destructive**, et c'est
#: elle que `ChoixExclusif` met sous le curseur au montage.
DECISION_ECRIRE_A_COTE = "a-cote"

#: Ecraser ce qui existe -- l'ecriture destructive **consciente**
#: d'`EPIC11-ARB-89`. Elle n'est jamais retenue pour un tirage scanne : l'ecran
#: ne l'offre pas, et l'issue de masse le **saute en le disant**.
DECISION_ECRASER = "ecraser"

#: Ce que le refus d'un projet sans lot dit. **Ce n'est pas un refus du coeur**
#: -- `EPIC11-ARB-30` gouverne ceux-la, et la TUI n'y ajoute rien --, c'est un
#: invariant du modele de la liste, dont la phrase est celle que
#: `atelier_pdf_lots` a redigee. La recomposer ici en ferait une seconde
#: redaction du meme constat.
CODE_AUCUN_LOT = "AUCUN_LOT_A_METTRE_EN_PLANCHES"

#: Le code du refus d'un libelle de chaine que le coeur ne sait pas nommer
#: (finding `C2-2`). Il ne nomme pas un refus **du coeur** -- ceux-la portent
#: leur propre motif et `EPIC11-ARB-30` interdit d'y ajouter quoi que ce soit --
#: mais l'endroit ou la TUI a rattrape une exception qui, sans lui, sortait de
#: la boucle `textual`. Le message affiche, lui, est bien celui du coeur.
CODE_CHAINE_INNOMMABLE = "LIBELLE_DE_CHAINE_INUTILISABLE"

#: La ligne de journal d'un lot que le coeur a refuse (finding `C2-3`). Elle
#: **nomme le lot** comme l'en-tete le fait, et pour la meme raison : le journal
#: n'est pas remis a zero entre deux lots (`EPIC11-ARB-93`), donc une ligne qui
#: ne se lit qu'en remontant a l'en-tete precedent se lit mal. Le message est
#: celui du coeur et voyage **verbatim** (`EPIC11-ARB-30`) : la TUI n'ajoute
#: rien a un refus et n'en reformule aucun.
#:
#: **Elle vit ici et non dans `atelier_pdf_execution`**, ou vivent
#: `EN_TETE_DE_LOT` et `LIGNE_DE_PAGE` : celles-la rendent un `LotEnGeneration`,
#: qui est le modele de l'ecran ; celle-ci rend un :class:`RefusDuLot`, qui est
#: le modele de cette boucle-ci. La ligne suit son objet.
LIGNE_DE_REFUS = "{lot} : refusé — {message}"


def ligne_de_refus(refus: "RefusDuLot") -> str:
    """`plan-04_25 : refusé — le lot n'est pas conforme`.

    Le motif n'y figure pas : c'est un **code** destine au code (il choisit
    l'ecran de refus), et le message du coeur porte deja la phrase lisible.
    """
    return LIGNE_DE_REFUS.format(lot=refus.lot_id, message=refus.message)


# ===========================================================================
# La boucle multi-lots -- tache I2, patron d'`executer_le_plan`
# ===========================================================================

@dataclasses.dataclass(frozen=True)
class LotAGenerer:
    """Un lot de la passe, tel que la boucle a besoin de le connaitre.

    Tout y est **deja tranche** : le fichier vise, la mise en page, et si cette
    passe ecrase ou ecrit a cote. La boucle ne decide rien -- elle appelle le
    coeur, collecte, et continue.
    """

    lot_id: str
    rush_id: str
    frames: int
    #: Les pages de ce lot, **mesurees par le coeur** a l'ecran de reglages.
    pages: int
    #: Le `template_id` du produit, pour l'en-tete de journal du lot.
    gabarit: str
    #: Le nom du PDF, derive par `io.naming.build_sheets_pdf_filename`.
    nom: str
    #: Le numero de tirage **affiche**. `None` vaut l'origine, qui n'ecrit aucun
    #: fragment de nom (`EPIC11-ARB-91`) -- c'est la convention du nom, relayee.
    rang: int | None = None
    #: Vrai quand l'operateur a retenu l'ecrasement a l'ecran de conflit.
    ecraser: bool = False


@dataclasses.dataclass(frozen=True)
class RefusDuLot:
    """Un lot que le coeur a refuse, **nomme** et rattache a son lot.

    Le motif et le message viennent du coeur et ne sont pas reformules
    (`EPIC11-ARB-30`). Le motif vaut `None` pour une exception du coeur qui n'en
    porte pas -- ce module ne lui en invente pas un.
    """

    lot_id: str
    message: str
    motif: str | None = None


@dataclasses.dataclass(frozen=True)
class RapportDesPlanches:
    """Ce que la passe a produit : ce qui est ecrit, ce qui est refuse.

    Les deux coexistent, et c'est la propriete que la boucle tient : « un echec
    sur le lot k n'annule pas les lots < k ».
    """

    ecrites: tuple[PlancheEcrite, ...] = ()
    refus: tuple[RefusDuLot, ...] = ()
    interrompu: bool = False
    #: Le `template_id` de la passe, lu de la mise en page retenue.
    gabarit: str = ""
    #: Les frames reellement placees, sommees sur les lots ecrits.
    frames: int = 0


def canal_de_progression(surface: SurfaceExecution, total: int):
    """Le **seul** canal par lequel un jalon du coeur atteint l'ecran.

    Meme fonction, meme motif et meme forme que celle de l'atelier Extraction,
    et les deux faits qui l'expliquent sont mesures la-bas :

    * `SurfaceExecution.emetteur(total)` est le seul appel qui remette a zero le
      compte et l'estimateur -- le sauter ferait afficher au lot suivant les
      jalons du precedent, donc un compte qui recule ;
    * le coeur attend un **appelable a deux arguments** `(faites, total)`, alors
      que l'objet rendu par `emetteur()` n'est pas appelable : le passer tel quel
      eteindrait le canal EN SILENCE.

    **Ce que `EPIC11-ARB-134` changera ici, et ce qu'il ne changera pas.**
    Aujourd'hui `emetteur()` remet `faites` a zero a chaque lot, donc `faites`
    est le compte du **lot courant** -- exactement ce que
    `EcranGenerationDesPlanches.sur_jalon` attend, et exactement ce que
    `PasseDeGeneration` agrege sur la passe entiere. Le cablage est donc **deja
    juste** : la barre montre `86 %` des 28 pages de la passe et non `43 %` des 7
    du lot. Ce qu'`ARB-134` retirera est la remise a zero, et la seule ligne a
    reprendre ce jour-la est celle de `sur_jalon` -- ni ce module, ni le modele,
    ni leurs bancs.
    """
    emetteur = surface.emetteur(total)
    return lambda faites, _total: emetteur.emettre(faites)


def executer_les_lots(lots: Sequence[LotAGenerer], passe: PasseDeGeneration,
                      surface: SurfaceExecution, *, dossier_projet,
                      reglages: Mapping[str, Any], gabarit: str = "",
                      logger=None,
                      hote: Callable[..., Any] | None = None,
                      interrompu: Callable[[], bool] | None = None,
                      generer: Callable[..., Any] | None = None,
                      horloge: Callable[[], datetime] | None = None
                      ) -> RapportDesPlanches:
    """Ecrire les planches des lots, **un appel du coeur par lot** (tache I2).

    `hote` est `CoqueTui.executer_en_processus` : le coeur est **heberge**, pas
    relance (`EPIC11-ARB-1`). Il vaut l'appel direct par defaut, pour que la
    passe se mesure sans monter d'application.

    **Un lot refuse n'annule pas les suivants**, et c'est la propriete de cette
    boucle qu'un `continue` devenu `break` detruirait *sans un mot* : sur trois
    lots dont le deuxieme est refuse, un `break` ferait disparaitre le
    troisieme, et le rapport ne porterait ni son ecriture ni son refus. Le
    mutant est celui de la 11.4b, paye trois fois sur ce depot. Le refus est
    **collecte**, nomme, et l'ecriture continue -- ce qui est aussi la seule
    lecture juste du metier : deux lots sont deux documents independants.

    **Le manifest est ecrit PAR LOT**, non en une passe : c'est le coeur qui le
    declare, apres chaque ecriture reussie. Une interruption laisse donc un
    manifest coherent avec ce qui est sur le disque.

    `interrompu` est consulte **entre deux lots**. Le canal de progression du
    coeur est observationnel par contrat (`EPIC7-ARB-79`) : il ne peut rien
    arreter, et promettre une interruption a la page serait promettre ce que le
    coeur n'offre pas.

    **Un lot refuse laisse une trace, et c'est le finding `C2-3`.** Le refus
    etait collecte dans le rapport mais n'inscrivait aucune ligne au journal :
    sur trois lots dont celui du milieu est refuse, le journal portait l'en-tete
    du lot refuse puis passait au suivant sans un mot. Le refus est desormais
    **nomme a l'endroit ou il se produit**, en plus d'etre collecte.

    Les erreurs **hors table** traversent : deguiser une panne inconnue en refus
    metier ferait lire un motif rassurant sur un bug.
    """
    hote = hote or (lambda fonction, *args, **kwargs: fonction(*args, **kwargs))
    generer = generer or makepdf.generer_les_planches_du_lot
    horloge = horloge or datetime.now
    ecrites: list[PlancheEcrite] = []
    refuses: list[RefusDuLot] = []
    frames = 0

    for rang, lot in enumerate(lots):
        if interrompu is not None and interrompu():
            return RapportDesPlanches(tuple(ecrites), tuple(refuses),
                                      interrompu=True, gabarit=gabarit,
                                      frames=frames)
        # L'etat de la passe avance AVANT l'appel : c'est ce que le corps de
        # `E5-4` affiche pendant que le coeur travaille -- le titre porte le
        # rang du lot, et la liste dit lequel est en cours.
        passe.rang_du_lot_courant = rang
        passe.pages_du_lot_courant = 0
        # **La ligne qui NOMME le lot**, et c'est elle qui rend
        # `EPIC11-ARB-93` tenable : le journal n'etant plus remis a zero entre
        # deux lots, `21/21` suivi de `1/7` se lirait comme un compte qui
        # recule. Nommee, la rupture se lit pour ce qu'elle est.
        surface.journal.inscrire(
            horodater(horloge(), en_tete_de_lot(passe.lot_courant)))
        rappel = canal_de_progression(surface, lot.pages)
        try:
            issue = hote(
                generer,
                dossier_projet,
                lot=lot.lot_id,
                overwrite=lot.ecraser,
                logger=logger,
                rappel_progression=rappel,
                **dict(reglages),
            )
        except makepdf.REFUS_NOMMES as refus:      # noqa: BLE001 -- table close
            refuse = RefusDuLot(lot_id=lot.lot_id, message=str(refus),
                                motif=getattr(refus, "motif", None))
            refuses.append(refuse)
            # **LA LIGNE QUI DIT LE REFUS** (finding `C2-3`). Sans elle, le
            # journal portait l'en-tete du lot puis plus rien : le lot etait
            # nomme, puis la rupture etait muette, ce qui se lit comme une passe
            # qui s'arrete plutot que comme un lot ecarte. C'est la classe de
            # decision cachee qu'`EPIC11-ARB-177` proscrit ailleurs dans cette
            # meme story -- « un lot ecarte sans que l'ecran le nomme serait une
            # decision cachee » --, appliquee ici au refus du coeur.
            surface.journal.inscrire(
                horodater(horloge(), ligne_de_refus(refuse)))
            # **LE `continue`.** Il ne se remplace pas par un `break` : les lots
            # suivants sont des documents independants.
            continue

        for ligne in lignes_du_journal_du_lot(issue, horloge()):
            surface.journal.inscrire(ligne)
        ecrites.append(planche_ecrite(lot, issue))
        frames += lot.frames
    return RapportDesPlanches(tuple(ecrites), tuple(refuses), gabarit=gabarit,
                              frames=frames)


def lignes_du_journal_du_lot(issue, instant: datetime) -> list[str]:
    """Les lignes de journal des pages d'un lot, **lues du plan rendu**.

    Les trois valeurs de chaque ligne viennent du plan du coeur -- le cardinal
    d'emplacements se lit **page par page**, la derniere page d'un lot mal
    rempli n'ayant pas celui des autres.

    **Un ecart nomme plutot que tu** : ces lignes sont inscrites quand le lot est
    fini, pas au fil des pages. Le plan n'existe qu'apres le retour du coeur --
    `generer_les_planches_du_lot` compose puis rend --, et l'inventer avant
    demanderait a la TUI de paginer, ce que la frontiere de l'AC 2.8 interdit.
    Les jalons chiffres, eux, arrivent bien un par page : c'est eux qui font
    avancer la barre pendant le travail. L'ecart est route en dette.
    """
    plan = getattr(issue, "plan", None)
    pages = list(getattr(plan, "pages", ()) or ())
    return [horodater(instant, ligne_de_page(page, rang, len(pages)))
            for rang, page in enumerate(pages, start=1)]


def rang_d_origine(objet=None) -> int:
    """Le rang du tirage d'origine, **lu de ce que le coeur rend** (`EPIC11-ARB-181`).

    Ce module ecrivait ce nombre **quatre fois en litteral**. Les deux
    frontieres qui devraient attraper une recopie comptent des **noms** : un `1`
    leur est structurellement invisible, et c'est exactement pourquoi personne
    ne l'avait vu. Le geste evident -- nommer la constante du coeur -- est
    interdit a ce paquet par la frontiere de la story 11.6, si bien que les deux
    regles du depot se contredisaient sur ce point precis.

    `EPIC11-ARB-181` les reconcilie **sans en amender aucune** : le coeur
    **transporte** la valeur sur les objets qu'il rend deja a un ecran, et la
    TUI l'affiche. Elle ne la nomme pas, elle ne la recopie pas -- c'est ce
    qu'`EPIC11-ARB-92` exige deja du rang d'un tirage existant.

    `objet` est l'un de ces objets du coeur, ou `None` quand l'appelant n'en a
    pas encore. Le repli n'est pas un litteral non plus : c'est le **defaut
    declare par le coeur lui-meme** sur son propre type, donc la meme valeur
    lue au meme endroit.
    """
    porte = getattr(objet, "rang_origine", None)
    return porte if isinstance(porte, int) else makepdf.TirageDejaLa.rang_origine


def planche_ecrite(lot: LotAGenerer, issue) -> PlancheEcrite:
    """Projeter ce que le coeur vient d'ecrire sur la ligne du compte rendu.

    Les champs sont **lus du rapport du coeur** et jamais rederives : le nom est
    celui du fichier reellement ecrit (`EPIC11-ARB-90`), le cardinal de pages
    celui du plan qui l'a produit -- « le compte reel, jamais le compte
    attendu ». Le numero de tirage est **relaye** ; l'absence vaut l'origine, et
    c'est la convention du nom, pas une deduction.
    """
    plan = getattr(issue, "plan", None)
    chemin = getattr(issue, "output_path", None)
    nom = Path(chemin).name if chemin else lot.nom
    return PlancheEcrite(
        nom=nom,
        pages=getattr(plan, "page_count", None) or lot.pages,
        rang=getattr(issue, "version_rank", None) or rang_d_origine(issue),
        fragment=naming.sheets_layout_fragment(
            getattr(plan, "template_id", None) or lot.gabarit))


# ===========================================================================
# Les deux depilements -- ce qu'une suite doit faire AVANT de recommencer
# ===========================================================================

def remonter_a_l_ouverture_de_l_atelier(app) -> None:
    """Depiler jusqu'a la **page d'ouverture** de l'atelier Pdf (`E5-0`).

    **Meme fonction, meme nom et meme motif que celle du Scan**
    (`atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier`), et c'est le
    finding `F3` : les suites qui « recommencent » -- `Mettre d'autres lots en
    planches`, `Générer une planche de calibration`, `Générer une autre mire` --
    **empilaient** une passe entiere par-dessus la precedente. Mesure de la
    couche 1 : `7 -> 12` ecrans en deux passes, **cinq de plus a chaque fois**,
    sans borne.

    Trois consequences, et la troisieme est la plus couteuse : les `E5-4` morts
    ne sont jamais demontes, donc leur `set_interval` de rotor continue de
    reveiller un ecran que personne ne regarde, **et** leur `on_mount` differe
    repose `app.tache_en_cours`. Le drapeau que plus personne n'eteint est ce
    qui fait qu'`Échap` cesse de depiler -- la classe de defaut de la regle
    5 bis de `CLAUDE.md`, prise par l'autre bout.

    **On depile jusqu'a l'ECRAN vise, et non jusqu'a un rang** -- c'est le
    seul ecart avec le Scan, et il est du a la forme de cet atelier-ci. Le Scan
    n'a qu'une station sous ses passages, donc `RANG_DES_ATELIERS + 1` la
    designe sans ambiguite. L'atelier Pdf en empile **trois** -- `E5-0` le
    menu, `E5-1` les lots, `E5-2` les reglages, toutes `TRANSITOIRE = False` --,
    si bien que la meme regle s'arreterait sur `E5-1`, c'est-a-dire sur la
    liste de lots de la passe qui vient de finir, ses cases encore cochees.
    L'atelier connait son propre ecran d'ouverture ; il n'a pas a en deviner la
    profondeur.

    **On ne remonte pas plus haut** (`EPIC11-ARB-13`) : cette suite s'arrete un
    cran EN DESSOUS du menu des ateliers, dans l'atelier ou l'operateur
    travaille. C'est le retour, et lui seul, qui remonte au menu.

    **Et on ne depile pas a l'aveugle** : si aucun `E5-0` n'est dans la pile --
    un appelant qui aurait monte le parcours autrement --, la fonction ne fait
    rien plutot que de vider la pile jusqu'a la racine. Un depilement qui ne
    sait pas ou il va est pire que pas de depilement.
    """
    if not any(isinstance(ecran, EcranPdfMenu) for ecran in app.screen_stack):
        return
    while (len(app.screen_stack) > 1
           and not isinstance(app.screen, EcranPdfMenu)):
        app.pop_screen()


def remonter_aux_reglages(app) -> None:
    """Depiler les **passages** jusqu'au premier palier de station.

    C'est ce que `Modifier les réglages` doit faire, et le finding `F4` dit
    pourquoi il ne le faisait pas : `action_remonter` depile **un** palier, or
    l'inversion d'`EPIC11-ARB-172` a glisse les ecrans de conflit **entre**
    `E5-2` et `E5-3`. L'issue atterrissait donc sur le dernier conflit -- deja
    tranche -- et non sur les reglages que son libelle annonce. Sans conflit
    elle tombait bien sur `E5-2` : le comportement dependait de la presence de
    conflits, ce qu'aucune ligne de l'ecran ne dit.

    Les deux ecrans intercales -- conflit et confirmation -- sont declares
    `TRANSITOIRE`, et `E5-2` ne l'est pas : le depilement se lit donc de la
    **declaration des ecrans** plutot que d'un compte de paliers ecrit ici, qui
    serait faux au premier ecran insere. C'est aussi ce qui fait que `Annuler`
    y mene : un passage n'est pas une destination, et les deux issues non
    ecrivantes de `E5-3` sortent du meme passage.
    """
    while app.passages_empiles and len(app.screen_stack) > 1:
        app.pop_screen()


# ===========================================================================
# Le parcours
# ===========================================================================

class ParcoursPdf:
    """Les huit ecrans de l'atelier Pdf, cables les uns aux autres.

    Meme forme que `ParcoursScan` et `ParcoursExtraction`, et pour le meme
    motif : chaque rappel a besoin de ce que le precedent a produit -- les lots
    coches, la mise en page retenue, les conflits tranches --, et les methodes
    liees le portent sans rendre l'etat implicite.

    **Ce parcours n'ecrit qu'a un seul endroit** : :meth:`generer`, par la boucle
    ci-dessus. Tout ce qui precede -- menu, lots, reglages, conflit,
    confirmation -- lit le manifeste et le disque, et rien d'autre. C'est
    l'invariant qui fait tenir `EPIC11-ARB-92` cote parcours : afficher un numero
    de tirage ne le consomme pas.
    """

    def __init__(self, app, dossier_projet, *,
                 generer: Callable[..., Any] | None = None,
                 calibrer: Callable[..., Any] | None = None,
                 logger: Any = None,
                 horloge: Callable[[], datetime] | None = None) -> None:
        self.app = app
        self.dossier_projet = Path(dossier_projet)
        #: Les doubles de banc des deux points d'entree du coeur. Leur defaut est
        #: le **vrai** point d'entree (`makepdf.generer_les_planches_du_lot`,
        #: `makepdf.generer_la_page_de_calibration`) : c'est le double qui est
        #: l'exception, pas le defaut.
        self._generer = generer
        self._calibrer = calibrer
        #: **Jamais `None` au moment d'appeler le coeur** : c'est le finding
        #: `I0`, qui faisait tomber TOUTE extraction lancee depuis `mmu-tui`.
        #: Le journal se construit ici quand personne n'en donne, et non au point
        #: d'appel -- un futur appelant ne peut donc pas rouvrir le trou en
        #: oubliant un mot-cle.
        if logger is None:
            self._logger, self._relais = journal_du_produit()
        else:
            self._logger, self._relais = logger, None
        self._horloge = horloge
        #: Le manifeste **relu a chaque entree dans le parcours**. Une seule
        #: lecture alimente la liste des lots, les conflits et la confirmation :
        #: juger sur un document et en afficher un autre est la classe de defaut
        #: que cette relecture unique ferme.
        self.manifeste: Mapping[str, Any] | None = None
        #: Les lots coches a `E5-1`, dans l'ordre de la liste.
        self.coches: tuple[Any, ...] = ()
        #: Les reglages retenus a `E5-2`.
        self.reglages: ReglagesDesPlanches | None = None
        #: La mise en page **mesuree** que `E5-2` a retenue.
        self.mise_en_page: page_templates.MiseEnPageMesuree | None = None
        #: Les conflits de la passe, ou `None` quand aucun lot n'en a.
        self.conflits: PasseDeConflits | None = None
        #: Ce que l'operateur a retenu, `lot_id -> decision`. Vide tant qu'aucun
        #: ecran de conflit n'a ete franchi ; un lot absent de cette table n'a
        #: **pas** de tirage anterieur, et ecrit donc a cote de rien.
        self.decisions: dict[str, str] = {}
        #: L'etat des tirages, `lot_id -> makepdf.TirageDejaLa`. Lu **une fois**
        #: par passe, avant le premier ecran de conflit.
        self.etats: dict[str, Any] = {}
        #: Le plan montre a `E5-3`.
        self.plan: Any = None
        #: L'etat de la passe d'ecriture, ou `None` avant `E5-4`.
        self.passe: PasseDeGeneration | None = None
        #: Le formulaire de la mire, ou `None` tant que `E5-6` n'est pas franchi.
        self.formulaire: FormulaireDeLaMire | None = None

    # -- lecture -------------------------------------------------------------

    def charger(self) -> Mapping[str, Any] | None:
        """Relire le manifeste. **Une seule lecture pour tout le parcours.**"""
        self.manifeste = projet_lecture.lire_manifeste(self.dossier_projet)
        return self.manifeste

    @property
    def project_id(self) -> str:
        """L'identifiant du projet, **lu du manifeste** et jamais du chemin.

        Le nom du dossier peut avoir ete renomme a la main ; le manifeste, lui,
        porte l'identifiant qui a servi a nommer les fichiers deja ecrits. Le
        repli sur le nom du dossier n'existe que pour un projet sans manifeste,
        ou plus rien n'a ete ecrit.
        """
        declare = (self.manifeste or {}).get("project_id")
        return declare if isinstance(declare, str) and declare \
            else self.dossier_projet.name

    def _lot_du_manifeste(self, lot_id: str) -> Mapping[str, Any]:
        for lot in projet_lecture._lots(
                self.manifeste if isinstance(self.manifeste, dict) else None):
            if lot.get("lot_id") == lot_id:
                return lot
        return {}

    def rush_du_lot(self, lot_id: str) -> str:
        """Le rush d'un lot, **lu du manifeste**.

        Il n'entre pas dans le nom du PDF (`EPIC7-ARB-91`) mais
        `build_sheets_pdf_filename` le prend a sa signature, et tous les
        appelants l'ont sous la main. La boucle cherche **jusqu'au bout** : un
        `find` qui rendrait le premier lot ecrirait le nom d'un rush sur un
        autre, et c'est le mutant `M25` de la story 5.7.
        """
        declare = self._lot_du_manifeste(lot_id).get("rush_id")
        return declare if isinstance(declare, str) else ""

    # -- etape 1 : le menu des ateliers -> `E5-0` ----------------------------

    def ouvrir(self) -> EcranPdfMenu:
        """`E5-0`, le menu de l'atelier. **Il y en a un, et c'est une regle.**

        `EPIC11-ARB-28`, verbatim : « Tout atelier qui a plus d'une entree
        commence par un menu d'atelier ». Le Pdf en a deux -- composer des
        planches, generer la mire --, exactement comme le Scan.
        """
        ecran = EcranPdfMenu(self.dossier_projet, entrer=self.entrer)
        self.app.descendre(ecran)
        return ecran

    def entrer(self, entree) -> None:
        """`⏎` sur une entree du menu. **Les deux menent quelque part.**

        Une entree inconnue reste une **erreur de cablage** plutot qu'un etat du
        produit, et elle mene quand meme quelque part : l'ecran qui nomme
        l'absence, avec l'echeance que l'entree porte.
        """
        if entree.cle == atelier_pdf.CLE_DE_LA_COMPOSITION:
            self.choisir_les_lots()
            return
        if entree.cle == atelier_pdf.CLE_DE_LA_MIRE:
            self.regler_la_mire()
            return
        self.app.descendre(EcranPasEncore(entree.nom,
                                          getattr(entree, "quand", "")))

    # -- etape 2 : `E5-1`, cocher des lots ------------------------------------

    def choisir_les_lots(self):
        """`E5-1`. Le manifeste est relu ici, et une seule fois pour la passe.

        Un projet **sans aucun lot** n'ouvre pas une liste vide : le modele leve
        -- « une liste vide n'est pas un choix, c'est un ecran sans objet » --,
        et le parcours le **dit** plutot que de tomber. La phrase affichee est
        celle du modele, jamais une seconde redaction du meme constat.
        """
        self.charger()
        self.decisions = {}
        self.etats = {}
        try:
            liste = ListeDeLots.depuis_le_manifeste(self.manifeste)
        except LotsMalFormes as vide:
            ecran = EcranRefus(CODE_AUCUN_LOT, str(vide))
            self.app.descendre(ecran)
            return ecran
        ecran = EcranLotsAPlanches(liste, continuer=self.regler)
        self.app.descendre(ecran)
        return ecran

    # -- etape 3 : `E5-2` / `E5-2b`, les reglages -----------------------------

    def regler(self, validation: Validation) -> EcranReglagesDesPlanches:
        """`E5-2`, sur les lots coches. **L'ordre des lots est celui de `E5-1`.**

        Il n'est jamais retrie : c'est sur lui que `MiseEnPageMesuree.pages_par_lot`
        s'apparie positionnellement, et une permutation ecrirait les pages d'un
        lot sur un autre sans que rien ne le dise.
        """
        self.coches = tuple(validation.coches)
        reglages = ReglagesDesPlanches(lots=tuple(
            LotAPlanches(lot_id=lot.lot_id, frames=lot.frames)
            for lot in self.coches))
        ecran = EcranReglagesDesPlanches(reglages,
                                         continuer=self.trancher_les_conflits)
        self.app.descendre(ecran)
        return ecran

    # -- etape 4 : le conflit, AVANT la confirmation (`EPIC11-ARB-172`) -------

    def trancher_les_conflits(self, reglages: ReglagesDesPlanches):
        """`Valider` a `E5-2` : le conflit **d'abord**, la confirmation ensuite.

        `EPIC11-ARB-172` inverse l'ordre que la fiche portait d'abord, et
        l'inversion **coute zero ecran** : quand aucun tirage n'existe, aucun
        ecran de conflit ne se monte et la confirmation dit ce qu'elle a a dire
        sans rien supposer.
        """
        self.reglages = reglages
        # **Aucune mise en page n'est retenue ICI** (finding `F10`, mutant
        # `C1-M9`, survivant) : `confirmer` la remesure **toujours**, sur les
        # lots qui restent apres les retraits de la passe, et le docstring de
        # `confirmer` dit pourquoi. Une seconde mesure ici etait morte -- et
        # pire que morte : elle laissait croire qu'un lecteur pouvait s'y fier.
        conflits = self.conflits_de_la_passe()
        if not conflits:
            self.conflits = None
            return self.confirmer()
        self.conflits = PasseDeConflits(conflits)
        return self.montrer_le_conflit()

    def conflits_de_la_passe(self) -> tuple[TirageEnConflit, ...]:
        """Les tirages deja presents des lots coches, **dans l'ordre par lot**.

        `EPIC11-ARB-177`, reponse d'Egan du 2026-09-02 : « Par lot ». Sans
        `ordonner_par_lot`, l'ordre serait celui de `lots[]` -- l'ordre de
        premiere creation, qui ne veut rien dire pour qui tranche des conflits.

        Les deux nombres de chaque conflit viennent de `makepdf.etat_des_tirages`,
        **deja resolus** : ce module n'en calcule aucun, et la frontiere de
        l'AC 7.3 le mesure a l'AST.

        La boucle va **jusqu'au bout** des lots coches : une sortie anticipee
        ferait disparaitre les conflits des lots suivants en silence.
        """
        etats = makepdf.etat_des_tirages(
            self.dossier_projet,
            lot_ids=[lot.lot_id for lot in self.coches],
            manifest=self.manifeste
            if isinstance(self.manifeste, dict) else None)
        self.etats = {etat.lot_id: etat for etat in etats}
        conflits: list[TirageEnConflit] = []
        for etat in etats:
            if not etat.deja_imprime:
                continue
            conflits.append(conflit_du_tirage(
                self.manifeste, self._lot_du_manifeste(etat.lot_id),
                etat.entree or {},
                rang=etat.present, rang_propose=etat.a_ecrire,
                dossier=self.dossier_projet))
        return ordonner_par_lot(conflits)

    def refus_des_rangs(self, lot_id: str) -> str | None:
        """Le refus des rangs epuises de ce lot, ou `None` -- **une seule lecture**.

        Deux chemins la consultent : celui qui monte l'ecran et celui qui decide
        si la masse a le droit d'emporter le lot. Les lire chacun de son cote
        etait exactement le finding `C2-4` : la masse ne savait pas ce que
        l'ecran refusait.

        Le texte vient du coeur et voyage **tel quel** ; ce module ne le
        reformule pas.
        """
        return getattr(self.etats.get(lot_id), "refus", None)

    def montrer_le_conflit(self):
        """Monter l'ecran du conflit courant -- ou le refus des tirages epuises.

        Le refus du coeur est affiche **tel quel** : le reformuler en ferait une
        seconde redaction qui divergerait au premier ajustement.
        """
        passe = self.conflits
        courant = passe.courant
        refus = self.refus_des_rangs(courant.lot_id)
        # **L'ecran emporte SA passe, et son issue la rapporte** (finding `F1`).
        # `descendre` empile : un `Annuler` depile et **revele l'ecran d'un
        # conflit deja tranche**, encore monte et encore navigable. Il rend une
        # issue qui portait, elle, sur la file du parcours -- donc sur un AUTRE
        # lot que celui dont l'operateur lit la fiche.
        retenir = partial(self.retenir_le_conflit, passe)
        if refus:
            ecran = EcranRangsEpuises(courant, refus, retenir=retenir)
        else:
            ecran = EcranConflitDeTirage(passe, retenir=retenir)
        self.app.descendre(ecran)
        return ecran

    def retenir_le_conflit(self, passe: PasseDeConflits, issue: Issue):
        """Ce qu'une issue d'ecran de conflit produit. **Quatre branches.**

        **`passe` est celle de l'ECRAN qui parle, jamais celle du parcours**
        (finding `F1`, couche 1 du 2026-09-02, et c'est le defaut le plus grave
        des trois couches). `montrer_le_conflit` **empile** un ecran par lot et
        `Annuler` **depile** : l'ecran ainsi revele est celui d'un conflit deja
        tranche, encore monte et encore navigable. Cette methode lisait
        `self.conflits.courant` -- la file du parcours -- et jamais le tirage de
        l'ecran qui produit l'issue.

        Ce que ca produisait, mesure a la sonde : `Remplacer ce tirage` sur
        l'ecran revele posait `DECISION_ECRASER` sur le lot **scanne** de la
        file, dont l'ecran ne porte pourtant pas cette issue. `lots_a_imprimer`
        reprenait alors `numero = present` et `lots_a_generer` passait
        `overwrite=True` au coeur : **la planche imprimee et scannee etait
        detruite**. `EPIC11-ARB-174`/`-176` (un tirage scanne ne s'ecrase pas)
        et `EPIC11-ARB-89` (l'ecriture destructive est *consciente*) tombaient
        ensemble -- le cartouche lu, les megaoctets annonces et la ligne d'etat
        etant ceux d'un autre tirage.

        La reprise ne consiste pas a interdire le retour en arriere : revenir
        sur un conflit deja tranche est legitime, et c'est ce que le docstring
        d'`Annuler` promet. Elle consiste a faire que **la file suive l'ecran**
        -- l'ecran qui parle redevient le courant, avec ses restants a lui --,
        plutot que l'inverse.

        * `Annuler` remonte d'un palier -- on revient sur ce qu'on vient de
          quitter, pas au menu ;
        * `Creer` et `Remplacer` tranchent **ce lot-la** et passent au conflit
          suivant, ou a la confirmation quand il n'y en a plus ;
        * `Appliquer ce choix aux N restants` tranche le courant **et** tous les
          suivants d'un coup. Le choix applique est celui que l'ecran offrait :
          destructif quand le tirage courant est ecrasable, non destructif
          sinon -- c'est exactement ce que `emport_de_la_masse` chiffre sous
          l'issue, et les deux lectures ne peuvent donc pas diverger.

        **La masse SAUTE les tirages scannes**, et l'ecran l'a dit avant qu'on
        la retienne (`EPIC11-ARB-174` / `-176`, `EPIC11-ARB-177` contrainte 2) :
        un tirage scanne recoit la version a cote, jamais l'ecrasement.

        **Et elle n'emporte PAS un lot dont les rangs sont epuises** (finding
        `C2-4`). Elle rendait la confirmation directement, court-circuitant
        `montrer_le_conflit` -- donc `EcranRangsEpuises` ne se montait jamais
        pour un lot restant, et son refus etait emporte en silence. Ce que ca
        produisait ensuite est pire que l'ecran manquant : `_etat_d_un_lot` pose
        `a_ecrire = present` quand le coeur refuse, si bien que `E5-3` annoncait
        comme numero a ecrire **celui du tirage qui existe deja** -- exactement
        le fait qu'`EPIC11-ARB-172` fait remonter le conflit avant la
        confirmation pour rendre vrai. C'est le meme principe qu'`EPIC11-ARB-177`
        pose pour le tirage scanne : une issue de masse saute ce qu'elle ne peut
        pas emporter **en le disant**, et le dire ici c'est monter l'ecran du
        refus au lieu de l'escamoter.
        """
        # La file **revient a l'ecran qui parle**. `PasseDeConflits` est gele :
        # l'instance que l'ecran porte est celle qui existait a son montage,
        # donc son `courant` et ses `restants` sont bien ceux que l'operateur a
        # lus -- ce n'est pas une reconstruction, c'est l'objet lui-meme.
        self.conflits = passe
        courant = passe.courant
        if issue.cle == CLE_ANNULER:
            self.app.action_remonter()
            return None
        if issue.cle == CLE_RETIRER_DE_LA_PASSE:
            # Le refus des numeros epuises offre de **sortir ce lot-la** plutot
            # que d'abandonner la passe entiere. Le lot quitte la selection ;
            # les autres restent, et c'est la seule lecture qui respecte
            # `EPIC11-ARB-89` -- perdre les N-1 autres pour un seul serait le
            # blocage sec qu'il proscrit.
            self.coches = tuple(lot for lot in self.coches
                                if lot.lot_id != courant.lot_id)
            self.decisions.pop(courant.lot_id, None)
            return self.conflit_suivant()
        if issue.cle == CLE_MASSE:
            destructif = courant.ecrasable
            for tirage in (courant,) + passe.restants:
                if self.refus_des_rangs(tirage.lot_id):
                    # Le lot garde son conflit **non tranche** : c'est ce qui
                    # fait que `conflit_suivant` s'arretera dessus et montrera
                    # son refus au lieu de l'emporter.
                    continue
                self.decisions[tirage.lot_id] = (
                    DECISION_ECRASER if destructif and tirage.ecrasable
                    else DECISION_ECRIRE_A_COTE)
            return self.conflit_suivant()
        self.decisions[courant.lot_id] = (
            DECISION_ECRASER if issue.cle == CLE_REMPLACER
            else DECISION_ECRIRE_A_COTE)
        return self.conflit_suivant()

    def conflit_suivant(self):
        """Le conflit qui suit, ou la confirmation quand il n'y en a plus.

        **La file avance d'un cran, jamais de deux et jamais de zero** : c'est
        elle qui tient `EPIC11-ARB-177` (« l'ecran se monte PAR LOT »), et un
        parcours qui monterait l'ecran une seule fois pour toute la passe
        trancherait le premier lot puis ecrirait les autres sans les avoir
        montres.

        Une passe **vidée** de tous ses lots -- le refus des numeros epuises
        ayant retire le dernier -- ne va pas confirmer une passe sans objet :
        elle ramene aux ateliers.

        **Elle saute ce qui est deja tranche, et jamais rien d'autre** (finding
        `C2-4`). Une issue de masse tranche plusieurs lots d'un coup, mais elle
        laisse intacts ceux qu'elle ne peut pas emporter : reprendre au conflit
        **suivant** montrerait alors un ecran a un lot deja decide, et reprendre
        a la confirmation escamoterait celui qui ne l'est pas. La file avance
        donc jusqu'au premier conflit **sans decision** -- ce qui, hors masse,
        est exactement le conflit suivant, un lot n'etant tranche qu'a l'ecran
        qui le montre.
        """
        passe = self.conflits
        for suivant in range(passe.rang_courant + 1, len(passe.conflits)):
            if passe.conflits[suivant].lot_id in self.decisions:
                continue
            self.conflits = dataclasses.replace(passe, rang_courant=suivant)
            return self.montrer_le_conflit()
        if not self.coches:
            self.app.revenir_aux_ateliers()
            return None
        return self.confirmer()

    # -- etape 5 : `E5-3`, la confirmation ------------------------------------

    def lots_a_imprimer(self) -> tuple[LotAImprimer, ...]:
        """Les lots coches tels que la confirmation les attend, **tout tranche**.

        Le numero de tirage affiche est celui que la decision de l'ecran de
        conflit implique, et il est **relaye** : ecrire a cote emploie celui que
        le coeur a rendu, ecraser reprend celui du tirage present. Le tirage
        d'origine n'ecrit aucun fragment de nom, et c'est `None` qui le dit --
        la convention du nom, jamais une traduction faite ici.

        **`scanne` se lit sur le tirage PRESENT, jamais sur le numero a
        ecrire**, et c'est le finding `C2-6` de la couche 2. Le champ dit « ce
        tirage **anterieur** a ete scanne » -- il departe `E5-3b` de `E5-3c`,
        donc il porte sur l'objet dont l'ecran de conflit a parle, c'est-a-dire
        celui qui existe deja. Le lire sur le numero **neuf** le rendait
        toujours faux en production : un tirage scanne n'est jamais ecrasable
        (`EPIC11-ARB-176`), donc il recoit toujours `ECRIRE_A_COTE`, donc le
        numero est le rang suivant -- qu'aucun scan n'a jamais vu passer, par
        construction. Mesure de bout en bout avant correction : trois
        `tirage_anterieur=True` et **zero** `scanne=True`, dont le lot dont le
        rang present est bel et bien dans `scanned_version_ranks`.
        `conflit_du_tirage` lit deja `rang` -- le present -- pour la meme
        raison ; les deux lectures sont maintenant la meme.
        """
        lots = []
        for lot in self.coches:
            etat = self.etats.get(lot.lot_id)
            decision = self.decisions.get(lot.lot_id)
            origine = rang_d_origine(etat)
            a_ecrire = getattr(etat, "a_ecrire", None) or origine
            present = getattr(etat, "present", 0) or 0
            numero = present if decision == DECISION_ECRASER else a_ecrire
            lots.append(LotAImprimer(
                lot_id=lot.lot_id,
                rush_id=self.rush_du_lot(lot.lot_id),
                frames=lot.frames,
                rang=numero if numero > origine else None,
                tirage_anterieur=bool(getattr(etat, "deja_imprime", False)),
                scanne=present in getattr(etat, "scannes", ())))
        return tuple(lots)

    def confirmer(self) -> EcranPdfConfirmation:
        """`E5-3`. **Le numero de tirage y est un FAIT**, pas une hypothese.

        C'est tout l'objet d'`EPIC11-ARB-172` : le conflit a ete tranche juste
        avant, donc « tirage 4 » est deja vrai au moment ou l'ecran l'ecrit, et
        il le sera encore sur la feuille imprimee.

        **La mise en page est remesuree ICI, sur les lots qui restent.** Elle ne
        se recopie pas de `E5-2` : le refus des numeros epuises peut avoir retire
        un lot de la passe entre-temps, et `pages_par_lot` s'apparie
        **positionnellement** aux lots -- une liste plus courte d'un cote
        ecrirait les pages d'un lot sur un autre. Le desaccord de cardinal est
        d'ailleurs refuse nommement par `preparer_le_plan` ; le remesurer est ce
        qui fait qu'il n'a pas a l'etre.
        """
        self.reglages.lots = tuple(
            LotAPlanches(lot_id=lot.lot_id, frames=lot.frames)
            for lot in self.coches)
        self.mise_en_page = self.reglages.retenue()
        self.plan = preparer_le_plan(
            self.dossier_projet, project_id=self.project_id,
            lots=self.lots_a_imprimer(), mise_en_page=self.mise_en_page,
            marge=self.reglages.marge)
        ecran = EcranPdfConfirmation(self.plan,
                                     sur_issue=self.trancher_la_confirmation)
        self.app.descendre(ecran)
        return ecran

    def trancher_la_confirmation(self, issue: Issue):
        """Les trois issues de `E5-3`. Une seule ecrit.

        `Modifier les réglages` et `Annuler` ramenent aux **reglages**, et pas
        « d'un palier » (finding `F4`). `action_remonter` depile un ecran, or
        l'inversion d'`EPIC11-ARB-172` a glisse les ecrans de conflit entre
        `E5-2` et `E5-3` : l'issue atterrissait sur le dernier conflit -- deja
        tranche --, c'est-a-dire ailleurs que la ou son libelle l'annonce, et
        seulement quand un conflit existait. Un comportement qui depend d'un
        etat qu'aucune ligne de l'ecran ne dit est un piege, pas une variante.

        Elles ne se distinguent toujours pas l'une de l'autre, et pour la raison
        d'avant : les deux ramenent l'operateur la ou il reglait, sans que rien
        ne soit ecrit. Ce qui change est **ou cela se trouve**.
        """
        if issue.cle == ISSUE_GENERER:
            return self.generer()
        if issue.cle in (ISSUE_MODIFIER, ISSUE_ANNULER):
            remonter_aux_reglages(self.app)
            return None
        return None

    # -- etape 6 : `E5-4`, la generation --------------------------------------

    def lots_a_generer(self) -> tuple[LotAGenerer, ...]:
        """Ce que la boucle recoit : un lot par planche a ecrire.

        Les pages viennent du plan de `E5-3`, qui les tient de la mise en page
        mesuree par le coeur. Rien n'est repagine ici.

        **L'appariement se fait PAR IDENTIFIANT, jamais par position** (finding
        `F7`). Un `zip` silencieux vivait ici, et une permutation totale du plan
        y survivait a 590 tests : chaque lot recevait le nom de fichier et le
        cardinal de pages d'un autre. C'est la classe payee trois fois par ce
        depot -- `M33` de la 5.6, `M25` de la 5.7, cinq survivants de la 5.8 --,
        et `preparer_le_plan`, dix lignes plus haut dans le meme parcours, la
        borde nommement (« un desaccord de cardinal est refuse plutot que
        tronque par un `zip` silencieux »). Ce qu'elle produisait a l'ecran :
        l'en-tete de journal de `E5-4` nommant un lot avec la pagination d'un
        autre, un total d'emetteur faux donc un pourcentage faux, et le nom d'un
        autre lot au compte rendu.

        `PlancheAEcrire` porte son `lot_id` : l'appariement par identifiant
        n'est donc pas une garde ajoutee mais la lecture juste, et « deux listes
        qui doivent rester en correspondance sont deux occasions de les
        desapparier » cesse de s'appliquer. Un lot que le plan ne porte pas est
        **refuse nommement** -- il n'y a pas de repli raisonnable, et une
        `KeyError` nue ne dirait pas ce qui manque.
        """
        planches = {planche.lot_id: planche for planche in self.plan.planches}
        lots = []
        for lot in self.lots_a_imprimer():
            planche = planches.get(lot.lot_id)
            if planche is None:
                raise PlanMalForme(
                    f"Le plan ne porte aucune planche pour le lot "
                    f"{lot.lot_id!r}. L'appariement se fait par identifiant : "
                    "un lot sans planche n'a ni nom de fichier ni pagination, "
                    "et en inventer serait ecrire sous le nom d'un autre."
                )
            lots.append(LotAGenerer(
                lot_id=lot.lot_id, rush_id=lot.rush_id, frames=lot.frames,
                pages=planche.pages, gabarit=self.mise_en_page.template_id,
                nom=planche.nom, rang=lot.rang,
                ecraser=self.decisions.get(lot.lot_id) == DECISION_ECRASER))
        return tuple(lots)

    def reglages_du_coeur(self) -> dict[str, Any]:
        """Ce qui part au coeur : trois reglages regles, et **un impose**.

        `EPIC11-ARB-36` : « tout champ d'un formulaire TUI nomme l'argument de
        coeur qu'il alimente ». Passes en `**kwargs`, une cle absente de la
        signature de `generer_les_planches_du_lot` leverait a l'appel au lieu
        d'etre ignoree -- c'est ce qui rend cette table mesurable.

        **La compression de gamut n'est pas un reglage, et elle part quand meme**
        (AC 5.9a, finding `C3-3`). L'ecran n'en porte aucun champ -- retour v5
        d'Egan, « on enleve compression de gamut » --, et le motif est du coeur :
        « la compression reelle s'active explicitement, la decompression `G^-1`
        est post-MVP », donc **la seule valeur sure est le defaut**, et un champ
        dont une seule valeur est sure n'est pas un reglage. L'absence du champ
        etait mesuree ; le passage de la constante ne l'etait pas, et n'avait
        lieu nulle part : la valeur venait du defaut du coeur.

        **La constante se NOMME, elle ne se recopie pas.** L'observable ne change
        pas aujourd'hui -- le coeur applique le meme defaut --, mais une valeur
        recopiee ici coinciderait le jour ou elle est ecrite et divergerait en
        silence le jour ou le coeur change la sienne. C'est la regle que ce
        depot applique deja a la borne d'identifiant (« la TUI lit la borne du
        coeur, elle ne la recopie pas »), et une frontiere AST mesure qu'aucun
        litteral de ce module ne porte la valeur.
        """
        return {"orientation": self.reglages.orientation,
                "frames_per_page": self.reglages.frames_par_page,
                "margin_preset": self.reglages.marge,
                "gamut_map_id": pdf_composition.DEFAULT_GAMUT_MAP}

    def generer(self) -> EcranGenerationDesPlanches:
        """Monter `E5-4` **avant** d'appeler le coeur, puis lancer la passe.

        L'ordre n'est pas cosmetique : le montage est ce qui abonne l'ecran aux
        jalons de la surface, et appeler le coeur d'abord ferait ecrire les
        jalons dans une surface que personne n'ecoute -- la barre partirait de la
        fin.
        """
        lots = self.lots_a_generer()
        surface = SurfaceExecution(unite=UNITE)
        self.passe = PasseDeGeneration(lots=tuple(
            LotEnGeneration(nom=lot.nom, pages=lot.pages, gabarit=lot.gabarit,
                            rang=lot.rang or rang_d_origine(
                                self.etats.get(lot.lot_id)),
                            libelle=lot.lot_id)
            for lot in lots))
        ecran = ouvrir_la_generation(
            self.app, surface, self.passe,
            sur_issue=self.interrompre,
            # La droite du bandeau est **composee du plan**, comme celle de
            # `E5-3` : les deux ecrans disent `2 lots · 164 frames` parce qu'ils
            # lisent le meme plan, et non parce qu'on a recopie la phrase.
            objet=bandeau_du_plan(self.plan))
        # **L'abonnement est pose ICI et pas seulement au montage de l'ecran**,
        # et ce n'est pas une ceinture de plus. `descendre` empile l'ecran, mais
        # `on_mount` est distribue par la boucle d'evenements -- or la passe qui
        # suit est **synchrone** et occupe cette boucle du premier au dernier
        # jalon. Sans cette ligne, l'ecran s'abonnerait apres que tous les
        # jalons sont tombes, et la barre passerait de rien a tout. `abonner`
        # ignore un rappel deja inscrit : le montage n'en pose pas un second.
        surface.abonner(ecran.sur_jalon)
        if self._relais is not None:
            self._relais.viser(surface.journal)
        # **`finally`, et il ferme un atelier mort pour la session.** Une erreur
        # hors de `REFUS_NOMMES` -- que la boucle laisse **volontairement**
        # traverser, « deguiser une panne inconnue en refus metier ferait lire
        # un motif rassurant sur un bug » -- sautait `oublier_la_tache()`. Le
        # drapeau `tache_en_cours` restait alors allume : `Échap` cesse de
        # depiler, `Q` ne quitte plus, et rien ne les rallume. Le filet de
        # demontage pose par le lot d'execution ne rattrape ce cas que si
        # l'ecran est **depile**, ce qui est precisement ce que ce chemin ne
        # fait pas. Le drapeau s'eteint donc ici, quoi qu'il arrive, et
        # l'exception continue son chemin -- elle n'est pas avalee.
        #
        # **La passe part au FIL depuis le 2026-09-06**, et le `finally` que ce
        # commentaire defend n'a pas disparu : il est reparti en deux moities.
        # L'ordre reste celui d'origine -- oublier, puis conclure.
        def passe() -> None:
            try:
                rapport = executer_les_lots(
                    lots, self.passe, surface,
                    dossier_projet=self.dossier_projet,
                    reglages=self.reglages_du_coeur(),
                    gabarit=self.mise_en_page.template_id,
                    logger=self._logger,
                    hote=self.app.executer_en_processus,
                    interrompu=lambda: bool(self.app.interruption_demandee),
                    generer=self._generer, horloge=self._horloge)
            except BaseException:
                # La moitie du `finally` qui reste necessaire : le coeur a
                # leve, `_conclure_la_generation` ne sera pas atteinte, et le
                # drapeau doit tomber quand meme -- sans quoi l'atelier est
                # mort pour la session, ce que le commentaire ci-dessus decrit.
                # L'exception continue son chemin, elle n'est pas avalee.
                self.app.call_from_thread(self.app.oublier_la_tache)
                raise
            self.app.call_from_thread(self._conclure_la_generation, rapport)

        # **Le fil ne part qu'APRES le dessin, et ce n'est pas une ceinture.**
        # Mesure du 2026-09-06 : `descendre` empile l'ecran mais `Mount` est
        # distribue par la boucle, et `EcranExecution.on_mount` y RALLUME
        # `tache_en_cours`. Un fil parti avant ce montage pouvait donc eteindre
        # le drapeau avant qu'`on_mount` le rallume -- ordre mesure a la sonde :
        # fil, puis `on_mount`, drapeau final a VRAI. L'atelier restait mort
        # pour la session sur une panne, ce que le commentaire d'
        # `ouvrir_la_generation` annoncait deja (« se rallume apres elle sans
        # que rien ne l'eteigne »).
        #
        # Le rendez-vous ordonne les deux **et** tient l'AC d'origine : l'ecran
        # est monte ET PEINT avant que le coeur parte, donc la progression se
        # voit au lieu de sauter de la confirmation au succes.
        _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(
            passe, thread=True, name="pdf-generer",
            description="generer les planches d'un plan"))
        return ecran

    def _conclure_la_generation(self, rapport) -> None:
        """Oublier la tache PUIS conclure, **en un seul passage par la boucle**.

        L'ordre est celui d'origine -- le `finally` tombait avant l'appel a
        :meth:`conclure` -- et il est conserve tel quel : ce lot deplace la
        passe sur un fil, il ne rearbitre pas le cycle de vie du drapeau.

        Ce qui change, c'est que les deux gestes sont dans la MEME fonction.
        Deux `call_from_thread` successifs laisseraient la boucle libre entre
        eux, avec `tache_en_cours` a faux et l'ecran de passe encore monte :
        c'est le finding `F1` de la vague 4, ferme ici par construction plutot
        que par attention.
        """
        self.app.oublier_la_tache()
        self.conclure(rapport)

    def interrompre(self, issue: Issue) -> None:
        """Les issues de `T6-1` qui arretent la passe.

        L'interruption est **demandee** ; elle est constatee entre deux lots par
        :func:`executer_les_lots`, dont le docstring dit pourquoi la granularite
        est celle-la. « Reprendre » ne vient jamais ici.
        """
        self.app.interruption_demandee = True

    # -- etape 7 : `E5-5`, le compte rendu ------------------------------------

    def conclure(self, rapport: RapportDesPlanches):
        """Monter `E5-5`, ou le refus quand **rien** n'a ete ecrit.

        Trois conclusions, et chacune a sa destination :

        * **rien d'ecrit et un refus** -- l'ecran de refus, avec le message du
          coeur et rien d'ajoute ;
        * **rien d'ecrit et une interruption** -- retour au menu des ateliers du
          projet ouvert (`EPIC11-ARB-13`) ;
        * **au moins une planche ecrite** -- le compte rendu, y compris quand un
          autre lot a ete refuse ou que la passe a ete interrompue : ce qui est
          ecrit se montre.
        """
        if not rapport.ecrites and rapport.refus:
            premier = rapport.refus[0]
            ecran = EcranRefus(premier.motif or premier.lot_id,
                               premier.message)
            self.app.descendre(ecran)
            return ecran
        if not rapport.ecrites:
            self.app.revenir_aux_ateliers()
            return None
        table = TableDesEcrits(planches=rapport.ecrites, frames=rapport.frames)
        return ouvrir_le_resultat(
            self.app, table, sur_suite=self.suivre,
            informations=self.informations_du_rapport(rapport),
            refus=len(rapport.refus))

    def informations_du_rapport(self, rapport: RapportDesPlanches):
        """Les trois lignes du bas du cartouche de `E5-5`, verbatim de la maquette.

        L'emplacement et le manifest sont **derives des constantes du produit**
        (`project_layout.dossier_de_planches`,
        `extraction_manifest.MANIFEST_FILENAME`) et non recopies : un dossier
        renomme au coeur renommerait la ligne avec lui.

        **Le dossier est RESOLU, pas nomme** (`EPIC11-ARB-225`) : sur un projet
        ancien les planches viennent d'etre ecrites sous le nom d'avant, et
        annoncer `planches/` enverrait l'operateur dans le dossier vide que
        `ensure_project_layout` vient de creer a cote.
        """
        return ((LIBELLE_GABARIT, rapport.gabarit),
                (LIBELLE_EMPLACEMENT,
                 f"{self.project_id}/"
                 f"{project_layout.dossier_de_planches(self.dossier_projet).name}/"),
                (LIBELLE_MANIFEST,
                 f"{self.project_id}/{extraction_manifest.MANIFEST_FILENAME}"))

    def suivre(self, suite: str) -> None:
        """Les suites de `E5-5`, et **chacune mene ailleurs**.

        `Ouvrir le dossier` remet le dossier au bureau et ne change pas d'ecran ;
        `Générer une planche de calibration` bascule sur l'autre entree de
        l'atelier -- proposee ici parce que c'est le moment ou elle sert, on
        imprime les deux ensemble ; `Mettre d'autres lots en planches` recommence
        une passe. Une suite inconnue ne consomme pas la touche en silence.

        **Les deux suites qui recommencent DEPILENT d'abord** (finding `F3`) :
        sans cela chacune empile une passe entiere sur la precedente -- cinq
        ecrans de plus a chaque fois, sans borne, rotors et drapeau de tache
        compris. Le geste est celui du Scan, nommement.
        """
        if suite == SUITE_DOSSIER:
            ouvrir_le_dossier_des_planches(
                self.app,
                project_layout.dossier_de_planches(self.dossier_projet))
            return
        if suite == SUITE_CALIBRATION:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            self.regler_la_mire()
            return
        if suite == SUITE_AUTRES_LOTS:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            self.choisir_les_lots()
            return
        self.app.descendre(EcranPasEncore(suite,
                                          atelier_pdf.QUAND_L_ATELIER_PDF))

    # -- l'autre entree du menu : la mire de calibration ----------------------

    def regler_la_mire(self):
        """`E5-6`, le temps 1 de la mire : deux champs, et rien d'autre.

        **Il n'y a plus de parametre `formulaire`, et c'est le finding `F5`.**
        Le docstring affirmait qu'il etait « repasse quand on revient de l'ecran
        de conflit par *Changer le nom de la chaîne* » ; cette branche fait un
        `action_remonter()` et ne rappelle jamais cette methode. Les trois sites
        d'appel le laissaient a `None`, et le mutant qui l'y forcait survivait :
        un mecanisme documente qui n'existe pas.

        Ce qui preserve reellement la saisie est le **depilement** -- l'ecran de
        formulaire est encore monte dessous, avec ce qu'on y a tape. C'est
        mesure, plutot que promis par un parametre mort : le jour ou ce chemin
        cesserait de depiler, un test rougirait au lieu d'un parametre a `None`
        qui n'aurait jamais rien porte.
        """
        return ouvrir_les_reglages_de_la_mire(
            self.app, self.project_id, self.dossier_projet,
            sur_continuer=self.confirmer_la_mire)

    def confirmer_la_mire(self, formulaire: FormulaireDeLaMire):
        """`E5-6d` si une mire du meme nom existe, `E5-6b` sinon.

        **Le conflit precede la confirmation**, ici comme pour les planches : la
        symetrie n'est pas cosmetique, c'est ce qu'`EPIC11-ARB-172` a tranche --
        on ne confirme pas ce qu'on va ecrire avant de savoir *ou* on l'ecrit.
        La difference avec les planches est qu'ici aucun numero n'est en jeu : la
        mire ne declare ni rush, ni lot, ni cadence (`EPIC5-ARB-82`), et
        `E5-6d` le **dit** en ligne d'etat.
        """
        self.formulaire = formulaire
        chaine = formulaire.saisie("chaine")
        presente = mire_presente(self.dossier_projet, self.project_id, chaine)
        if presente is not None:
            return ouvrir_le_conflit_de_la_mire(
                self.app, presente, chaine,
                sur_issue=self.trancher_le_conflit_de_la_mire)
        return ouvrir_la_confirmation_de_la_mire(
            self.app, formulaire, self.project_id,
            sur_issue=self.trancher_la_mire)

    def trancher_le_conflit_de_la_mire(self, issue: Issue):
        """Les trois issues de `E5-6d`. **Jamais une seule, jamais zero.**

        `Changer le nom de la chaîne` est la sortie non destructive : elle
        ramene au formulaire, ou le libelle entre dans le nom du fichier.
        `Remplacer cette mire` est l'ecriture destructive consciente
        d'`EPIC11-ARB-89`, et elle passe par la confirmation comme l'autre --
        une ecriture qui sauterait le point de jugement parce qu'elle a deja
        traverse un avertissement en ferait deux, pas un.
        """
        if issue.cle == MIRE_AUTRE_CHAINE:
            self.app.action_remonter()
            return None
        if issue.cle == MIRE_REMPLACER:
            return ouvrir_la_confirmation_de_la_mire(
                self.app, self.formulaire, self.project_id,
                sur_issue=self.trancher_la_mire)
        self.app.action_remonter()
        return None

    def trancher_la_mire(self, issue: Issue):
        """Les trois issues de `E5-6b`. Une seule ecrit."""
        if issue.cle == MIRE_GENERER:
            return self.generer_la_mire()
        if issue.cle in (MIRE_MODIFIER, MIRE_ANNULER):
            self.app.action_remonter()
            return None
        return None

    def generer_la_mire(self):
        """`E5-6c` puis `E5-6e` -- **aucune barre**, et c'est une mesure.

        Le canal du coeur emet un jalon **par page**, et une mire fait une page :
        il n'y en a donc qu'un, et il tombe a la fin. Ce qui reste est une
        attente honnete -- un rotor, la ligne du fichier, et une ligne d'etat qui
        ne dit que ce qui est su.

        `--overwrite` est **toujours** passe : le seul chemin qui arrive ici en
        presence d'un fichier du meme nom est celui ou l'operateur a retenu
        `Remplacer cette mire`, et le refus du coeur y serait alors un blocage
        sec apres un consentement -- exactement ce qu'`EPIC11-ARB-89` proscrit.
        Quand aucun fichier n'existe, le drapeau n'ecrase rien.

        **Le filet du libelle innommable** (finding `C2-2`). `E5-6` refuse
        desormais de continuer sur un libelle que le coeur ne sait pas nommer,
        et c'est la que l'operateur le voit -- sur le champ, avec une issue,
        c'est-a-dire ce qu'`EPIC11-ARB-89` demande. Ce filet-ci ferme l'autre
        moitie : un appelant qui monterait `E5-6c` sans passer par le
        formulaire ferait **traverser un `NamingError` hors de la boucle
        `textual`**, et l'application tombait -- ni un blocage, ni une issue :
        une chute. Le refus du coeur est relaye **tel quel**, comme partout
        (`EPIC11-ARB-30`), sur l'ecran qui sait les afficher.
        """
        chaine = self.formulaire.saisie("chaine")
        try:
            nom = nom_de_la_mire(self.project_id, chaine)
        except naming.NamingError as refus:
            ecran = EcranRefus(CODE_CHAINE_INNOMMABLE, str(refus))
            self.app.descendre(ecran)
            return ecran
        ecran = ouvrir_la_generation_de_la_mire(
            self.app, nom, chaine, sur_interruption=self.interrompre_la_mire)
        calibrer = self._calibrer or makepdf.generer_la_page_de_calibration
        # Meme `finally` et meme motif que pour la passe de planches : le coeur
        # de la mire leve lui aussi, et un drapeau reste allume tue l'atelier
        # pour la session entiere. Meme decoupe, aussi, depuis le 2026-09-06.
        def passe() -> None:
            try:
                issue = self.app.executer_en_processus(
                    calibrer, self.dossier_projet, overwrite=True,
                    logger=self._logger,
                    **self.formulaire.arguments_du_coeur())
            except BaseException:
                self.app.call_from_thread(self.app.oublier_la_tache)
                raise
            self.app.call_from_thread(self._conclure_la_mire, issue, chaine)

        # **Le rotor de `E5-6c` ne tournait PAS**, et c'est ce que ce fil
        # repare. Il est mene par un `set_interval`, c'est-a-dire par un
        # minuteur de la boucle : un appel synchrone au coeur la gardait du
        # debut a la fin de la generation, et « le seul signe honnete que la
        # machine travaille » -- ce que l'en-tete du module de calibration dit
        # du rotor -- restait fige sur son premier dessin.
        # Meme rendez-vous, et meme motif, que la passe de planches : le fil ne
        # part qu'une fois l'ecran monte et peint. `E5-6c` n'est pas un
        # `EcranExecution` -- il ne rallume donc pas le drapeau, et la course
        # mesuree sur `generer` ne l'atteint pas --, mais la seconde moitie du
        # motif vaut pour lui aussi : un rotor ne tourne que si la boucle a
        # dessine avant que le coeur parte.
        #
        # **EQUIVALENT MESURE (campagne du 2026-09-06, mutant `M1`).** Retirer
        # ce rendez-vous ne change AUCUN comportement mesurable : les 81 tests
        # du banc restent verts, `E5-6c` compris son banc de bout en bout qui
        # compte les tours de boucle et les pas du rotor pendant la passe. Le
        # motif est celui que les deux phrases ci-dessus disent deja -- pas de
        # drapeau a rallumer ici, et le fil rend la boucle de toute facon, donc
        # le dessin arrive avec ou sans rendez-vous. Il est **conserve pour
        # l'uniformite** des quatre departs de fil du paquet : la seule facon
        # de le rendre portant serait de mesurer l'instant du premier dessin a
        # la microseconde, ce qui mesurerait l'ordonnanceur et non le produit.
        _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(
            passe, thread=True, name="pdf-mire",
            description="generer une mire de calibration"))
        return ecran

    def interrompre_la_mire(self) -> None:
        """`Échap` pendant la mire. Une page ne s'interrompt pas en deux."""
        self.app.interruption_demandee = True

    def _conclure_la_mire(self, issue, chaine: str) -> None:
        """Oublier la tache PUIS conclure, en un seul passage par la boucle.

        Le chemin se derive **ici** et non dans le fil : `chemin_de_la_mire` ne
        touche rien de `textual`, mais le garder avec sa conclusion evite de
        faire traverser au fil une valeur que seul l'ecran consomme.
        """
        self.app.oublier_la_tache()
        chemin = getattr(issue, "output_path", None) or chemin_de_la_mire(
            self.dossier_projet, self.project_id, chaine)
        self.conclure_la_mire(chemin, chaine)

    def conclure_la_mire(self, chemin, chaine: str):
        """`E5-6e`, et ses deux suites contextuelles."""
        return ouvrir_le_resultat_de_la_mire(
            self.app, chemin, chaine, self.project_id,
            sur_suite=self.suivre_apres_la_mire)

    def suivre_apres_la_mire(self, suite: str) -> None:
        """Les suites de `E5-6e`. **Chacune mene ailleurs, aucune n'est morte.**

        Les deux qui recommencent depilent d'abord, comme celles de `E5-5` et
        pour le meme motif (finding `F3`).
        """
        if suite == MIRE_SUITE_DOSSIER:
            ouvrir_le_dossier_des_planches(
                self.app,
                project_layout.dossier_de_planches(self.dossier_projet))
            return
        if suite == SUITE_AUTRE_MIRE:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            self.regler_la_mire()
            return
        if suite == SUITE_PLANCHES:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            self.choisir_les_lots()
            return
        self.app.descendre(EcranPasEncore(suite,
                                          atelier_pdf.QUAND_L_ATELIER_PDF))


# **Il n'y a PAS de `ouvrir_l_atelier_pdf` ici, et c'est le finding `F10`.**
# Ce module en exportait un, exporte dans `__all__` et appele par **personne** :
# le produit cable celui d'`atelier_pdf.py`, que `ChaineReelle` injecte. Deux
# fonctions publiques du meme nom, dont l'une morte, est une bombe a retardement
# -- le jour ou les deux divergent, rien ne le dit, et la moitie des lecteurs
# lit la mauvaise. Le point d'entree unique vit dans `atelier_pdf.py`, ou le
# menu vit, et il monte `ParcoursPdf` par un import differe.


__all__ = [
    "CODE_AUCUN_LOT",
    "CODE_CHAINE_INNOMMABLE",
    "DECISION_ECRASER",
    "DECISION_ECRIRE_A_COTE",
    "LotAGenerer",
    "ParcoursPdf",
    "RapportDesPlanches",
    "RefusDuLot",
    "canal_de_progression",
    "executer_les_lots",
    "ligne_de_refus",
    "lignes_du_journal_du_lot",
    "planche_ecrite",
    "rang_d_origine",
    "remonter_a_l_ouverture_de_l_atelier",
    "remonter_aux_reglages",
]
