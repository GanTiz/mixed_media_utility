# -*- coding: utf-8 -*-
"""Les deux gestes de media du palier Projet qui avaient DEJA un coeur.

**Le manque que ce module ferme, et c'est Egan qui l'a trouve sur le terrain**
(2026-09-06, verbatim de sa note de recette, section « Gestion des medias
(projet) ») :

* « Ajouter un media au projet depuis le disque : n'existe pas encore (normal ?
  ou non cable ?) » ;
* « Declarer au manifeste : "pas encore" -> inexistant ou non cable. »

La mesure repond **differemment** aux deux, et c'est tout l'objet de ce
module. `Ctrl+A` et `Ctrl+L` de `E6-1` avaient l'un et l'autre leur coeur
**et** leur ecran, cables nulle part ; `Ctrl+D` n'a pas de coeur du tout, et il
reste donc un filet -- mais un filet qui dit la verite (voir
`projet_inventaire.CE_QUI_MANQUE_A_LA_DECLARATION`).

Ce que la MESURE a trouve, et qui n'etait pas dans le brief
------------------------------------------------------------
Le brief de ce lot annoncait « le coeur existe, le dessin est a decliner » pour
`Ctrl+A`. C'est **moins** que ce qui existe : ce n'est pas seulement le coeur
(`declaration_de_rush.preparer_une_declaration` / `ecrire_la_declaration`,
derriere `mmu project add-rush`) qui est ecrit, c'est **tout le parcours
d'ecran** --

* :class:`~mixed_media_utility.tui.atelier_extraction.EcranRushes` ouvre
  l'explorateur sur un fichier video (`BUT_AJOUTER`, `MODE_DESIGNER`) ;
* :class:`~mixed_media_utility.tui.atelier_extraction.EcranDeclaration`
  (`E2-1e`) est le panneau chiffre d'`EPIC11-ARB-4`, dans ses quatre etats ;
* :class:`~mixed_media_utility.tui.atelier_extraction.EcranRefusDeConflit`
  (`E2-1f`) porte le cas des deux cameras jam-synchronisees
  (`EPIC11-ARB-232`) ;
* `phrase_de_declaration_reussie` dit que c'est ecrit.

Il n'y avait donc **aucun dessin a decliner** : il y avait une porte a ouvrir.
Ecrire ici un second ecran de designation, un second panneau chiffre et un
second compte rendu aurait produit la « seconde redaction » que ce depot paie
a chaque fois qu'il en fabrique une -- et celle-la aurait diverge sur le seul
chemin qu'un operateur emprunte apres un refus, c'est-a-dire celui qu'on
regarde le moins. **Ce module ne dessine rien.** Il monte l'ecran qui existe,
avec les rappels du produit, sur le geste demande.

Meme constat, en plus net encore, pour `Ctrl+L` : le relink complet vit dans
`EcranRushes` (ses deux modes de designation, `E2-1d` pour le refus,
`phrase_de_relink_reussi` pour la reussite) et dans `tui/rushes.py`
(`preparer_relink`, `ecrire_le_relink`). C'est litteralement le cas « si cela
existe : cabler » qu'Egan a nomme le 2026-09-06.

L'ECART qu'il faut nommer plutot que taire
-------------------------------------------
Le bandeau de `EcranRushes` porte `Extraction`, et il continue de le porter
quand on l'atteint depuis l'inventaire du palier Projet. C'est **vrai** -- le
relink et la declaration d'un rush sont des gestes de l'atelier Extraction, et
`E2-1` est l'ecran valide qui les porte -- mais l'operateur qui vient de
`E6-1` change de palier sans l'avoir demande. Le corriger demanderait soit un
second ecran (la seconde redaction ci-dessus), soit un titre parametrable sur
`EcranRushes`, qui est un dessin valide qu'aucune maquette ne montre sous un
autre titre (`EPIC11-ARB-144`). L'ecart est donc **porte au rapport** plutot
que corrige a la volee.

Ce que ce module N'EST PAS
---------------------------
Il n'ecrit **aucune ligne de coeur** et n'en recalcule aucune valeur : les
deux temps de la declaration sont ceux de `declaration_de_rush`, le relink est
celui de `tui/rushes.py`, et les cadences sont celles de
`atelier_extraction_ecriture.ouvrir_les_cadences`. Les trois adaptateurs de ce
module ne font que **transporter** le dossier du projet, que `EcranRushes`
n'inclut pas dans la signature de ses rappels.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jetons, rushes
from .atelier_extraction import (BUT_AJOUTER, BUT_RELINK, EcranRushes,
                                 _application_montee)

# ===========================================================================
# Ce que la ligne d'etat dit quand un geste demande d'ailleurs ne peut PAS
# aboutir. Aucun de ces cas n'est un blocage sec (`EPIC11-ARB-89`) : l'ecran
# monte quand meme, sur sa liste, et il DIT pourquoi le geste n'a pas ouvert
# l'explorateur (`EPIC11-ARB-258` -- un refus se dit).
# ===========================================================================

#: Le rush que l'inventaire designe n'est pas au manifeste des rushes.
#:
#: **Ce n'est pas un cas impossible**, et c'est ce qui le rend digne d'une
#: phrase : l'arbre de `E6-1` greffe des ORPHELINS -- des objets trouves sur le
#: disque et absents du manifeste --, et `project_inventory` en fabrique des
#: noeuds de nature `rush` qui n'ont aucune entree `rushes[]`. Relinker un
#: rush que le manifeste ne connait pas n'a pas de sens : il n'y a pas de lien
#: a refaire, il y a une declaration a faire, et c'est l'autre touche.
#:
#: MESURE: 63/76 sur un identifiant de dix caracteres.
MOTIF_RUSH_HORS_MANIFESTE = (
    "{rush_id} n'est pas au manifeste : c'est Ctrl+A qui le déclare.")

#: Le rush vise est LIE -- son fichier source est la, il n'y a rien a relinker.
#:
#: Il dit ce qui MARCHE plutot que seulement « non » : un refus sans issue est
#: aussi fautif qu'une destruction silencieuse (`EPIC11-ARB-89`).
#:
#: MESURE: 66/76 sur un identifiant de dix caracteres.
MOTIF_RUSH_DEJA_LIE = (
    "{rush_id} est lié : son fichier source est là, rien à relinker.")


# ===========================================================================
# Les TROIS adaptateurs du produit -- ils transportent, ils ne decident rien
# ===========================================================================

def preparer_la_declaration(dossier_projet, cible,
                            *, force_distinct: bool = False):
    """Temps 1 de la declaration : ce qui SERA ecrit, sans rien avoir ecrit.

    **`EPIC11-ARB-4`** : `preparer_une_declaration` ne touche **aucun octet**
    -- une frontiere du coeur le mesure --, et le panneau chiffre `E2-1e` se
    peint dessus. L'ecriture attend la validation de l'operateur.

    Le journal est celui du produit : le coeur y inscrit la qualification de la
    source, et un `getLogger` racine ecrirait par-dessus l'interface plein
    ecran.

    `force_distinct` est **transporte et jamais interprete** ici : c'est la
    deuxieme issue de `E2-1f` portee jusqu'au coeur (`EPIC11-ARB-232`,
    `--force-distinct` en ligne de commande), et la separation se decide au
    coeur.

    **Une DUPLICATION nommee plutot que tue.**
    `atelier_extraction_ecriture.ChaineReelle.preparer_la_declaration` fait
    exactement ce geste, a la lecture du dossier pres -- elle le prend sur son
    menu, celle-ci le recoit en argument. Ce module ne peut pas l'appeler : ce
    serait une methode d'une instance que l'inventaire n'a pas, et le module
    qui la porte n'appartient pas a ce lot. La reconciliation -- injecter les
    deux temps depuis `ChaineReelle` jusqu'a `ouvrir_l_inventaire_du_projet` --
    est portee au rapport de lot ; elle tient en un mot-cle de plus a deux
    endroits, et elle appartient a celui qui tient ce fichier-la.
    """
    from ..declaration_de_rush import preparer_une_declaration
    from .atelier_extraction_ecriture import journal_du_produit

    logger, _relais = journal_du_produit()
    return preparer_une_declaration(project_dir=Path(dossier_projet),
                                    video_path=Path(cible), logger=logger,
                                    force_distinct=force_distinct)


def ecrire_la_declaration(preparee) -> str:
    """Temps 2 : l'ecriture, et elle rend le `rush_id` REELLEMENT ecrit.

    C'est ce que `EcranRushes._viser_le_rush_declare` attend, et pas un
    identifiant rederive du nom de fichier : le coeur a pu lever une homonymie
    (`EPIC11-ARB-9`) et ecrire un `rush_id` suffixe. Le deriver une seconde
    fois viserait un rush qui n'existe pas, ou pire son homonyme --
    `EPIC11-ARB-146` pris a l'endroit.

    Meme duplication nommee que ci-dessus, et meme reconciliation proposee.
    """
    from ..declaration_de_rush import ecrire_la_declaration as ecrire_au_coeur
    from .atelier_extraction_ecriture import journal_du_produit

    logger, _relais = journal_du_produit()
    return ecrire_au_coeur(preparee, logger=logger).rush_id


def ouvrir_les_cadences(app, dossier_projet, rush_id: str) -> Any:
    """`⏎` sur un rush LIE : les cadences (`E2-2`), cablees jusqu'a « ecrit ».

    **Elle existe pour que rien ne se degrade en chemin.** `EcranRushes` monte
    depuis l'inventaire est le MEME ecran que celui de l'atelier Extraction :
    il annonce `⏎`, et un `⏎` qui repondrait « pas encore » ici alors qu'il
    extrait la-bas ferait de la porte un ecran de seconde classe. C'est le
    finding `I8` pris par le bout le plus couteux -- une touche qui marche la
    ou l'on n'est pas ne marche pas.

    L'import est **differe au corps** : `atelier_extraction_ecriture` importe
    `atelier_extraction`, que ce module importe en tete ; un import de tete
    refermerait le cycle. C'est l'idiome du depot.
    """
    from .atelier_extraction_ecriture import ouvrir_les_cadences as ouvrir

    return ouvrir(app, Path(dossier_projet), rush_id)


# ===========================================================================
# Le montage -- une seule redaction pour les deux gestes
# ===========================================================================

def monter_l_atelier_des_rushes(application, dossier_projet, *,
                                preparer=preparer_la_declaration,
                                ecrire=ecrire_la_declaration,
                                cadences=ouvrir_les_cadences) -> EcranRushes:
    """Construire `E2-1` avec **tous** ses rappels du produit, et l'empiler.

    Les trois rappels sont **injectes et ont pour defaut le vrai chemin** : ce
    sont des points d'injection de mesure, pas des versions degradees. C'est la
    forme exacte de `palier_profil_defaut.ouvrir_le_profil_par_defaut`, et le
    motif est le finding `K3`, paye quatre fois dans cet epic -- un
    `Callable | None = None` assorti d'un `if ... is not None` fait de l'oubli
    de cablage un silence.

    Les deux premiers sont **lies au dossier ici**, pendant qu'on le tient :
    `EcranRushes` appelle `preparer(cible)` et `ecrire(preparee)` sans dossier,
    et le relire ailleurs ferait dependre l'ecriture d'un menu que cet ecran-ci
    n'a pas.
    """
    dossier = Path(dossier_projet)
    ecran = EcranRushes(
        dossier,
        extraire=lambda rush_id: cadences(application, dossier, rush_id),
        preparer=lambda cible, **reste: preparer(dossier, cible, **reste),
        ecrire=ecrire)
    application.descendre(ecran)
    return ecran


def ouvrir_l_ajout_de_media(app, dossier_projet, **cablage) -> bool:
    """`Ctrl+A` de `E6-1` : designer un fichier video et le declarer.

    **Deux sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * aucune application montee -> faux, et l'appelant sait que rien n'a
      bouge ;
    * tout va bien -> `E2-1`, **explorateur deja ouvert** sur les fichiers.

    L'explorateur s'ouvre de lui-meme, et ce n'est pas du confort : la touche
    dit « ajouter un media depuis le disque », donc l'ecran qu'elle rend doit
    demander un chemin. Laisser l'operateur sur la liste des rushes lui
    demanderait de deviner `Tab`, ce qui est le defaut `MQ-1` deja paye sur cet
    ecran-la.

    **Le geste est demande APRES l'empilement** : `_ouvrir_l_explorateur` lit
    la memoire de session sur l'APPLICATION (`CoutureExplorateur`), et un
    ecran pas encore empile n'en a pas -- l'explorateur repartirait de
    `Path.cwd()` a chaque ajout, ce qu'`EPIC11-ARB-54` ferme.
    """
    application = _application_montee(app)
    if application is None:
        return False
    ecran = monter_l_atelier_des_rushes(application, dossier_projet, **cablage)
    ecran.ouvrir_le_geste(BUT_AJOUTER, rushes.MODE_DESIGNER)
    _redessiner(ecran)
    return True


def ouvrir_le_relink_du_rush(app, dossier_projet, rush_id: str,
                             **cablage) -> bool:
    """`Ctrl+L` de `E6-1` : repointer un rush declare dont le fichier a bouge.

    **Quatre sorties, aucune n'est un blocage sec** (`EPIC11-ARB-89`) :

    * aucune application montee -> faux, et l'appelant sait que rien n'a
      bouge ;
    * le rush n'est pas au manifeste des rushes -> `E2-1` monte quand meme, et
      la ligne d'etat DIT que c'est `Ctrl+A` qui declare
      (:data:`MOTIF_RUSH_HORS_MANIFESTE`) ;
    * le rush est LIE -> `E2-1` monte, curseur pose dessus, et la ligne d'etat
      DIT qu'il n'y a rien a relinker (:data:`MOTIF_RUSH_DEJA_LIE`) ;
    * le rush est declare et absent -> `E2-1` avec l'explorateur ouvert en mode
      **recherche**, exactement ou `⏎` sur un rush absent mene deja (AC 2.4).

    **Les deux refus sont DITS et non tus**, et ils ne referment pas l'ecran :
    la liste des rushes est precisement ou l'operateur peut corriger son tir --
    bouger d'une ligne, frapper `d` pour designer a la main. Un refus qui
    remonterait au palier lui ferait recommencer la navigation.

    **Le curseur est pose sur le rush AVANT d'ouvrir l'explorateur**, et c'est
    structurel : `EcranRushes._ouvrir_l_explorateur` memorise sa cible en
    demandant `liste.rush_a_relinker()`, c'est-a-dire **le rush sous le
    curseur**. Sans ce `viser`, un projet a deux rushes absents relinkerait le
    premier de la liste au lieu de celui que l'inventaire designe -- le mode de
    panne de `_find_lot` en 5.7, une fois de plus.
    """
    application = _application_montee(app)
    if application is None:
        return False
    ecran = monter_l_atelier_des_rushes(application, dossier_projet, **cablage)
    try:
        vise = ecran.liste.viser(rush_id)
    except KeyError:
        _dire(ecran, MOTIF_RUSH_HORS_MANIFESTE.format(rush_id=rush_id))
        _redessiner(ecran)
        return True
    if vise.lie:
        _dire(ecran, MOTIF_RUSH_DEJA_LIE.format(rush_id=rush_id))
        _redessiner(ecran)
        return True
    ecran.ouvrir_le_geste(BUT_RELINK, rushes.MODE_RETROUVER)
    _redessiner(ecran)
    return True


def _dire(ecran, phrase: str) -> None:
    """Poser un refus sur la ligne d'etat, **replie par le mode courant**.

    **Le repli est fait ICI et pas dans l'ecran**, et ce n'est pas un choix :
    `EcranRushes.etat()` rend `_etat_a_dire` **tel quel**, chacun de ses
    producteurs ayant deja replie (`jetons.marque(..., ascii_seul)`,
    `phrase_de_relink_reussi(..., ascii_seul)`). Une porte qui poserait sa
    phrase brute serait la seule ligne d'etat de cet ecran a ne pas se replier,
    et l'ecart ne se verrait qu'en `--ascii` -- c'est le defaut exact de
    `coque.Palier.bandeau`, paye le 2026-09-06 sur onze ecrans sur quatorze.

    Le drapeau se lit sur l'APPLICATION plutot que sur l'ecran : la porte le
    tient deja, et l'ecran n'est monte que depuis une ligne.
    """
    ascii_seul = getattr(_application_montee(ecran), "ascii_seul", False)
    ecran.dire(jetons.replier_ascii(phrase) if ascii_seul else phrase)


def _redessiner(ecran) -> None:
    """Redessiner un ecran qu'on vient d'empiler ET de modifier.

    **Le garde-fou n'est pas decoratif** : `on_mount` redessine de lui-meme, et
    l'ordre des deux n'est pas garanti -- un ecran deja monte quand on change
    sa zone garderait la liste peinte par-dessus l'explorateur qu'on vient
    d'ouvrir. Le meme garde-fou vit dans
    `projet_inventaire.relire_l_inventaire`, et pour la meme raison : un banc
    qui monte l'ecran hors application ne doit pas lever.
    """
    if getattr(ecran, "is_mounted", False):
        ecran.rafraichir()


__all__ = [
    "MOTIF_RUSH_DEJA_LIE",
    "MOTIF_RUSH_HORS_MANIFESTE",
    "ecrire_la_declaration",
    "monter_l_atelier_des_rushes",
    "ouvrir_l_ajout_de_media",
    "ouvrir_le_relink_du_rush",
    "ouvrir_les_cadences",
    "preparer_la_declaration",
]
