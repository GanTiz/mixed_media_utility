# -*- coding: utf-8 -*-
"""`E3-8` -- le resultat de l'ecriture du Scan, et ou l'on retombe.

Story 11.6, lot F (AC 7). C'est le compte rendu de la passe que le lot E vient
de conduire : il consomme le
:class:`~mixed_media_utility.tui.atelier_scan_ecriture.RapportDEcriture` que
`executer_et_conclure` remet a son `sur_rapport`, et il n'appelle **jamais** le
coeur lui-meme. Quand cet ecran monte, l'ecriture est finie -- une suite est
une navigation, pas un second travail.

**Ce que ce module ne fait pas, et c'est structurel :**

* il **ne rederive aucun chiffre**. Les frames ecrites, la profondeur de
  sortie, la correction tranchee et l'inventaire de degradation sont **lus**
  du rapport du coeur (`EcritureDuLot`), jamais recomptes ici : une seconde
  redaction divergerait, et l'ecart ne se verrait que sur les TIFF ;
* il **ne redige aucun second ensemble ferme**. Ce qui degrade une passe est
  :data:`~mixed_media_utility.scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE`, lu par
  :func:`~mixed_media_utility.scan_write.motifs_de_degradation` ; le recopier
  ici ferait deux verites sur la meme question (AC 7.3, mesure en **egalite
  d'ensembles**) ;
* il **n'ouvre aucun second site d'appel systeme**. « Ouvrir le dossier des
  lots » passe par
  :func:`~mixed_media_utility.tui.execution.ouvrir_dans_l_explorateur_du_systeme`,
  l'unique lanceur de processus du paquet `tui/` (`EPIC11-ARB-85`, AC 7.5), et
  il **ne quitte pas la TUI** : l'ecran reste `E3-8`, dont les chiffres restent
  lisibles pendant qu'on regarde le dossier ;
* il **ne redonne pas d'ecran de resultat** : il *sous-classe*
  :class:`~mixed_media_utility.tui.execution.EcranResultat`, qui n'est **pas
  modifie** -- c'est un module partage avec l'atelier Extraction, et le toucher
  serait la contention que la regle de decoupage interdit.

**Trois renseignements que le rapport ne porte pas, et qui sont donc EXIGES a
l'appel** (`journal`, `duree`, `attendues`). Aucun n'a de defaut, et ce n'est
pas une rigueur d'humeur : un `... | None = None` assorti d'un `if` transforme
l'oubli du cablage en **silence**, sept fois paye dans cet epic (findings `I8`
et `K3`). Les rendre requis fait de l'oubli une **erreur d'appel** ; passer
`None` explicitement reste possible et veut dire « je ne sais pas », auquel cas
la ligne concernee est **omise** plutot que devinee (`DESIGN.md` section 3 :
ni `0`, ni `--`, ni chaine vide la ou une mesure est attendue).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from .. import scan_write
from . import jetons
from .atelier_extraction_ecriture import taille_lisible
# **Import du comptage d'octets plutot qu'une seconde redaction.** Le nom est
# prive a l'atelier Extraction, mais la fonction porte une garde que la revue de
# la vague 3 (couche 2, `T2`) a payee : `is_dir()` repond vrai sur un partage
# reseau demonte et `iterdir()` leve alors, une trace Python nue au moment ou
# l'ecriture vient de REUSSIR. Recopier six lignes ici recopierait la garde --
# ou, plus vraisemblablement, l'oublierait. Voir `frames_du_dossier` cote lot E,
# qui cite deja cette meme garde comme son modele.
from .atelier_extraction_ecriture import _octets_du_dossier as octets_du_dossier
from .atelier_scan_ecriture import (
    PALIER_DE_L_ATELIER,
    UNITE,
    LotEcrit,
    RapportDEcriture,
)
from .execution import EcranResultat, ouvrir_dans_l_explorateur_du_systeme
from .panneau import LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Le vocabulaire de l'ecran -- une seule redaction, celle-ci
# ---------------------------------------------------------------------------

#: Le titre du cartouche, verbatim de la maquette (`E3-8-scan-resultat.txt`,
#: l. 5). Il nomme un **etat du disque** : ce qui est ecrit l'est.
TITRE_ECRIT = "Écrit"

#: Les trois libelles du bas du cartouche (maquette, l. 9 a 11).
LIBELLE_CALIBRATION = "Calibration appliquée"
LIBELLE_MANIFESTE = "Manifest mis à jour"
LIBELLE_DUREE = "Durée"

#: Le libelle de la ligne qui **nomme** ce qui a degrade un lot (AC 7.3). Elle
#: est posee sous la ligne du lot concerne, indentee, et sa valeur est la suite
#: de motifs telle que le coeur la rend -- jamais une phrase traduite : un motif
#: se compare a une constante, une phrase se reformule.
LIBELLE_MOTIF = "Motif"

#: L'indentation de la ligne de motif, pour qu'elle se rattache visiblement au
#: lot qui la porte plutot que de flotter au meme niveau que les cardinaux.
INDENT_DU_MOTIF = "  "

#: Ce que la ligne de calibration dit quand la correction **n'a pas** ete
#: appliquee. C'est la valeur **tranchee** (`EcritureDuLot.correction_appliquee`),
#: jamais ce qui avait ete demande au depart (AC 7.2).
CALIBRATION_AUCUNE = "aucune"

#: Ce qu'elle dit quand la correction vient de la page de calibration du lot
#: lui-meme et non d'un profil de chaine. Le nom de la page n'y figure pas :
#: ce qui se cherche trois semaines plus tard est **d'ou** vient la correction,
#: et la page vit dans le manifeste du lot.
CALIBRATION_PAGE_DU_LOT = "page de calibration du lot"

#: Le repli quand un profil de chaine a servi sans que sa chaine soit nommee --
#: un objet fabrique a la main, jamais une passe reelle. On dit **ce qu'on
#: sait** plutot que de rendre une chaine vide.
CALIBRATION_PROFIL_DESIGNE = "profil désigné du projet"

#: Le mot d'unite de la profondeur de sortie. `None` **traverse** : une ligne
#: qui inventerait « 16 bits » sur une passe qui ne l'a pas mesuree serait pire
#: qu'une ligne sans profondeur.
UNITE_DE_PROFONDEUR = "bits"

#: Les trois suites qui precedent le retour (maquette, l. 14 a 16).
#: `EcranResultat` ajoute lui-meme « Retour aux ateliers » en dernier s'il
#: manque : on ne l'ecrit donc pas ici, sous peine de le voir deux fois.
#:
#: **Le mot « lot » y est QUALIFIE depuis la story 11.14** (`EPIC11-ARB-214`,
#: « un mot, un objet »), et ce n'est pas une retouche de style : la maquette
#: du 2026-08-27 ecrivait « Ouvrir le dossier des lots », **exactement la
#: meme chaine** que `atelier_extraction_ecriture.SUITE_DOSSIER`. Les deux
#: suites ouvrent pourtant deux dossiers differents -- `extract-frames/` pour
#: l'une, `frames-scannees/` pour l'autre -- et rien dans le libelle ne le
#: disait. C'est litteralement l'ambiguite qu'Egan a nommee le 2026-09-04 :
#: « ne plus avoir a deviner s'il s'agit des frames que `extract` a sorties du
#: rush ou de celles qu'un scan a rendues ».
#:
#: Le mot retenu est celui du coeur -- **lot scanne**
#: (`project_maintenance._FamilleVersionnee(nom="lot scanne")`,
#: `project_inventory.NATURE_LOT_SCANNE`) -- et non un troisieme mot invente
#: ici : « une interface le LIT, elle ne le REDIGE pas ».
SUITE_DOSSIER = "Ouvrir le dossier des lots scannés"
SUITE_EXPORTS = "Encoder un master depuis ces lots scannés"
SUITE_AUTRES_SCANS = "Détecter d'autres scans"

#: Ce que la ligne d'etat dit quand :data:`SUITE_DOSSIER` est choisie
#: sur un rapport qui n'en porte aucun. Ouvrir le dossier du projet a la place
#: repondrait a une autre question. :func:`suites_du_resultat` ne propose pas la
#: suite dans ce cas ; ce texte est le **volet symetrique**, celui qui tient si
#: un jour elle la proposait.
AUCUN_LOT_A_OUVRIR = (
    "Aucun lot scanné écrit : il n'y a aucun dossier à ouvrir.")

#: Ce que la ligne d'etat dit d'une passe sans refus (maquette, l. 22).
AUCUN_REFUS = "aucun refus"

#: Ce qu'elle ajoute quand la passe a ete **interrompue**. Un compte rendu qui
#: tairait l'interruption laisserait lire « voila tout ce qu'il y avait a
#: ecrire » sur une passe qu'on a arretee soi-meme.
PASSE_INTERROMPUE = "passe interrompue"


# ---------------------------------------------------------------------------
# La duree -- mesuree par l'appelant, jamais devinee ici
# ---------------------------------------------------------------------------

def chronometre(horloge: Callable[[], float] = time.monotonic
                ) -> Callable[[], float]:
    """Rend un appelable qui donne les **secondes ecoulees** depuis son montage.

    Il vit ici parce que c'est cet ecran qui affiche la duree, et il est monte
    par le cablage **avant** l'appel au coeur : le rapport d'ecriture ne porte
    aucun temps, et le deduire apres coup d'un nombre de frames serait une
    duree fausse.

    `horloge` est injectable pour que la mesure se teste sans attendre : c'est
    le double qui est l'exception, le defaut (`time.monotonic`) est le vrai
    chemin. **Monotone et non `time.time`** : une horloge murale qui recule --
    changement d'heure, resynchronisation NTP -- rendrait une duree negative
    sur une passe qui a bien dure.
    """
    depart = horloge()
    return lambda: horloge() - depart


def duree_lisible(secondes: float | None) -> str | None:
    """`6 min 12`, la grammaire de la section 8 du `DESIGN.md`.

    **Aucune seconde redaction** : `avancement.duree_lisible` porte deja cette
    grammaire, arrondi compris, et la revue de vague 1 l'a mesuree caractere
    par caractere. `None` traverse en `None` -- la ligne est alors **omise**,
    jamais rendue `0:00` ni `--:--`.
    """
    if secondes is None:
        return None
    # Import local : `avancement` est deja importe par `execution`, et le tirer
    # en tete de module n'ajouterait qu'un nom a la portee du fichier.
    from .avancement import duree_lisible as _duree
    return _duree(secondes)


# ---------------------------------------------------------------------------
# Ce qu'un lot ecrit vaut -- tout est LU du rapport du coeur
# ---------------------------------------------------------------------------

def dossier_du_projet(rapport: RapportDEcriture) -> Path | None:
    """La racine du projet, deduite du **manifeste** que la passe a mis a jour.

    Le rapport ne porte pas le dossier projet, mais il porte le chemin du
    manifeste, qui est `<projet>/project.json` par construction
    (`atelier_scan_ecriture.ecrire_les_lots`). `None` quand la passe n'a rien
    ecrit du tout.
    """
    return None if rapport.manifeste is None else Path(rapport.manifeste).parent


def chemin_du_lot(rapport: RapportDEcriture, lot: LotEcrit) -> Path | None:
    """Le dossier **absolu** d'un lot ecrit, ou `None` si on ne le sait pas.

    **Le chemin que le coeur rend est RELATIF au projet**, et c'est le piege
    que cette fonction existe pour fermer :
    `scan_output_frames` ecrit `output_dir` par `_project_relative_posix`
    (`scan_output_frames.py:2095`), et `atelier_scan_ecriture._lot_ecrit` le
    recopie tel quel dans `LotEcrit.dossier`. Le prendre pour un chemin absolu
    ferait mesurer **zero octet** et remettre au bureau un dossier inexistant,
    resolu sous le dossier courant du processus -- deux pannes muettes, sur les
    deux seules choses que cet ecran promet d'un lot.

    Un chemin deja absolu traverse tel quel : `LotAEcrire.dossier`, quand
    l'appelant le connait, en porte un.
    """
    if lot.dossier is None:
        return None
    dossier = Path(lot.dossier)
    if dossier.is_absolute():
        return dossier
    racine = dossier_du_projet(rapport)
    return dossier if racine is None else racine / dossier


def motifs_qui_degradent(lot: LotEcrit) -> tuple[str, ...]:
    """Ce qui degrade CE lot, **lu du coeur** et jamais recopie (AC 7.3).

    Deux fonctions du coeur, enchainees, et aucune troisieme redaction :
    :func:`~mixed_media_utility.scan_write.inventaire_de_l_ecriture` reunit les
    avertissements d'ecriture et les constats de persistance dans l'ordre ou la
    passe les annonce, et
    :func:`~mixed_media_utility.scan_write.motifs_de_degradation` retient ceux
    de :data:`~mixed_media_utility.scan_write.MOTIFS_QUI_DEGRADENT_LE_CODE`.

    L'ensemble est **ferme et lu**, jamais reecrit : un lot a mires
    (`SCAN_SYNTHETIC_FRAMES_PRESENT`) ou incomplet (`SCAN_LOT_INCOMPLETE`)
    n'est pas un succes plein, et le jour ou le coeur y ajoutera un motif, cet
    ecran le montrera sans qu'une ligne bouge ici. Un banc mesure l'**egalite
    d'ensembles** avec la constante du coeur -- une assertion positive laisserait
    passer toute divergence supplementaire.

    Rend un tuple vide pour un `LotEcrit` fabrique sans son rapport de coeur :
    c'est le seul regime ou l'inventaire n'existe pas, et il n'appartient qu'aux
    bancs. Un rapport **present mais mal forme** leve, plutot que de rendre
    « aucune degradation » sur une passe degradee.
    """
    if lot.ecriture is None:
        return ()
    return scan_write.motifs_de_degradation(
        scan_write.inventaire_de_l_ecriture(lot.ecriture))


def profondeur_du_lot(lot: LotEcrit) -> str | None:
    """`16 bits`, ou `None` quand la passe ne l'a pas mesuree.

    Lue sur `EcritureDuLot.output.output_bit_depth`, que
    `scan_output_frames` renseigne depuis l'export. **`None` traverse** : le
    morceau disparait de la ligne plutot que d'y annoncer une profondeur qui
    n'a pas ete mesuree.
    """
    sortie = getattr(lot.ecriture, "output", None)
    bits = getattr(sortie, "output_bit_depth", None)
    return None if not bits else f"{bits} {UNITE_DE_PROFONDEUR}"


def calibration_du_lot(lot: LotEcrit) -> str:
    """Ce qui a **reellement** corrige ce lot -- « la valeur telle qu'elle a ete
    tranchee, jamais ce qui avait ete demande au depart » (AC 7.2).

    Trois regimes, et ils ne se confondent pas :

    * la correction **n'a pas ete appliquee** -- quelle qu'en soit la cause,
      lot livre brut ou correction refusee a l'invite : `aucune` ;
    * elle vient d'un **profil de chaine designe** : la ligne porte le
      `chain_id`, c'est-a-dire exactement ce qu'on cherche trois semaines plus
      tard (« quelle calibration a produit ces TIFF ? ») ;
    * elle vient de la **page de calibration du lot** : la ligne le dit.

    Les deux drapeaux sont lus sur le `LotEcrit`, que le lot E a projetes de
    `EcritureDuLot.correction_appliquee` et `.profil_de_chaine_utilise` ; le
    nom de chaine est lu sur `lot_correction.chain_id`, que
    `scan_write` renseigne **seulement** quand le profil de chaine a gagne.
    """
    if not lot.correction_appliquee:
        return CALIBRATION_AUCUNE
    if not lot.profil_de_chaine_utilise:
        return CALIBRATION_PAGE_DU_LOT
    correction = getattr(lot.ecriture, "lot_correction", None)
    chaine = getattr(correction, "chain_id", None)
    return chaine or CALIBRATION_PROFIL_DESIGNE


# ---------------------------------------------------------------------------
# Le cartouche de `E3-8`
# ---------------------------------------------------------------------------

def ligne_du_lot(rapport: RapportDEcriture, lot: LotEcrit,
                 ascii_seul: bool = False) -> LigneChiffree:
    """Une ligne par lot ecrit : son glyphe d'etat, son nom, ses cardinaux.

    Le glyphe est `●` quand la passe a tenu sa promesse et `▲` des qu'un motif
    du coeur la degrade (AC 7.3) : « un lot a mires ou incomplet n'est pas un
    succes plein ». Le second canal du `DESIGN.md` section 6 passe donc **par
    le glyphe**, avant toute couleur, et il replie en ASCII avec le reste.

    La droite porte ce qui est **mesure**, dans l'ordre de la maquette (l. 6) :
    les frames ecrites, la profondeur de sortie, le poids du dossier. Les deux
    derniers **disparaissent** quand ils ne sont pas connus, au lieu d'annoncer
    zero.
    """
    table = jetons.glyphes(ascii_seul)
    etat = "substitute" if motifs_qui_degradent(lot) else "complete"
    poids = taille_lisible(_octets_du_lot(rapport, lot))
    droite = " · ".join(morceau for morceau in (
        f"{lot.frames} {UNITE}", profondeur_du_lot(lot), poids) if morceau)
    return LigneChiffree(f"{table[etat]} {lot.lot_id}", droite)


def _octets_du_lot(rapport: RapportDEcriture, lot: LotEcrit) -> int | None:
    """Le poids **mesure** du dossier du lot, ou `None` s'il n'est pas connu.

    `None` et non zero : « aucun dossier connu » et « un dossier vide » sont
    deux faits differents, et le second ne se produit pas apres une ecriture
    reussie. Rendre zero ferait afficher `0 o` sur un lot bien ecrit dont on a
    seulement perdu le chemin.
    """
    dossier = chemin_du_lot(rapport, lot)
    return None if dossier is None else octets_du_dossier(dossier)


def lignes_de_calibration(rapport: RapportDEcriture) -> list[LigneChiffree]:
    """La calibration appliquee -- **une** ligne, ou une par lot si elles
    divergent.

    La maquette montre une seule ligne parce que ses deux lots partagent le
    meme profil. Rien ne le garantit : chaque lot du plan porte son propre
    `profil_designe`, et deux documents de detection peuvent avoir ete
    calibres autrement. Replier deux valeurs differentes sur une seule ligne
    attribuerait a un lot la calibration de l'autre -- exactement le mode de
    panne que le mutant `M25` de la story 5.7 a paye (« les cardinaux du scan
    etaient ecrits sur le mauvais lot »).

    La liste parcourue est `rapport.ecrits`, dans son ordre : c'est sur elle
    que la regle des fabriques s'applique.
    """
    if not rapport.ecrits:
        return []
    valeurs = [calibration_du_lot(lot) for lot in rapport.ecrits]
    if len(set(valeurs)) == 1:
        return [LigneChiffree(LIBELLE_CALIBRATION, valeurs[0])]
    return [LigneChiffree(f"{LIBELLE_CALIBRATION} · {lot.lot_id}", valeur)
            for lot, valeur in zip(rapport.ecrits, valeurs)]


def panneau_du_resultat(rapport: RapportDEcriture, ascii_seul: bool = False, *,
                        duree: float | None = None) -> Panneau:
    """Le cartouche de `E3-8` : les lots, puis la calibration, le manifeste, la
    duree.

    **Aucun majorant** : `EcranResultat` leve a la construction sur un panneau
    qui en porte un (story 11.1, AC 8.2), et c'est juste -- le travail est
    fait, les chiffres sont mesures. C'est la difference de fond avec `E3-6`,
    dont l'espace disque est un majorant assume.

    Chaque ligne absente est **omise**, jamais remplie d'un `--` : un manifeste
    inconnu, une duree non mesuree et une passe sans lot ecrit se lisent a leur
    absence, pas a un tiret qui pourrait passer pour une mesure.
    """
    lignes: list[LigneChiffree] = []
    for lot in rapport.ecrits:
        lignes.append(ligne_du_lot(rapport, lot, ascii_seul))
        motifs = motifs_qui_degradent(lot)
        if motifs:
            # Le motif est **dit**, et il l'est avec les codes du coeur : c'est
            # ce qu'une interface compare a une constante, la ou une phrase
            # traduite se reformulerait et cesserait de correspondre.
            lignes.append(LigneChiffree(f"{INDENT_DU_MOTIF}{LIBELLE_MOTIF}",
                                        " · ".join(motifs)))
    lignes.extend(lignes_de_calibration(rapport))
    if rapport.manifeste is not None and rapport.ecrits:
        manifeste = Path(rapport.manifeste)
        lignes.append(LigneChiffree(LIBELLE_MANIFESTE,
                                    f"{manifeste.parent.name}/{manifeste.name}"))
    lisible = duree_lisible(duree)
    if lisible is not None:
        lignes.append(LigneChiffree(LIBELLE_DUREE, lisible))
    return Panneau(TITRE_ECRIT, lignes)


def objet_du_bandeau(rapport: RapportDEcriture) -> str:
    """La droite du bandeau : `2 lots · 186 frames` (maquette, l. 2).

    C'est une **mesure** de ce que la passe a produit, pas le rappel de ce
    qu'elle promettait : le bandeau de `E3-7` dit `temps 2 sur 2 · écrire`, et
    celui-ci dit ce qui en est sorti.

    Rendu en UTF-8 sans repli : `Contexte.rendu` replie lui-meme la droite du
    bandeau, et replier deux fois ne casserait rien mais ferait deux redactions
    du meme geste.
    """
    lots = len(rapport.ecrits)
    return f"{lots} {'lot' if lots == 1 else 'lots'} · {rapport.frames} {UNITE}"


def ligne_d_etat_du_resultat(rapport: RapportDEcriture,
                             attendues: int | None = None,
                             ascii_seul: bool = False) -> str:
    """Une **mesure**, jamais un nom de touche ni un conseil (`EPIC11-ARB-56`).

    Maquette (l. 22) : `● 186 frames écrites sur 186 attendues, aucun refus`.
    Le glyphe suit la meme regle que les lignes de lot -- `▲` des qu'un lot est
    degrade, `✕` des qu'un refus est tombe --, si bien que le second canal du
    `DESIGN.md` section 6 est tenu jusqu'en bas de l'ecran.

    `attendues` vaut `None` quand l'appelant ne le sait pas : le segment
    « sur N attendues » **disparait** alors, plutot que de recopier les frames
    ecrites a droite du « sur », ce qui ferait lire une passe complete a coup
    sur.
    """
    frames = rapport.frames
    mot = "frame écrite" if frames == 1 else "frames écrites"
    libelle = f"{frames} {mot}"
    if attendues is not None:
        libelle += f" sur {attendues} attendues"
    refus = rapport.refus
    if refus:
        libelle += (f", {len(refus)} refus : "
                    + ", ".join(r.code for r in refus))
    else:
        libelle += f", {AUCUN_REFUS}"
    if rapport.interrompu:
        libelle += f", {PASSE_INTERROMPUE}"
    if refus:
        etat = "absent"
    elif any(motifs_qui_degradent(lot) for lot in rapport.ecrits):
        etat = "substitute"
    else:
        etat = "complete"
    if ascii_seul:
        # **Le repli precede la mesure**, et il porte sur le libelle autant que
        # sur le glyphe : `jetons.marque` ne replie que le second, et
        # « frames écrites » sortait donc accentue en `--ascii`.
        libelle = jetons.replier_ascii(libelle)
    return jetons.marque(etat, libelle, ascii_seul)


# ---------------------------------------------------------------------------
# Les suites, et ou chacune mene
# ---------------------------------------------------------------------------

def suites_du_resultat(rapport: RapportDEcriture) -> list[str]:
    """Les suites de `E3-8`, et **chacune mene quelque part**.

    Les deux premieres ne sont offertes que si un lot a ete ecrit : proposer
    « ouvrir le dossier des lots » sur zero lot designerait un dossier qui
    n'existe pas, et « encoder un master depuis ces lots » une source vide.
    `EcranResultat` ajoute « Retour aux ateliers » en dernier de lui-meme
    (`EPIC11-ARB-13`).
    """
    suites = [SUITE_DOSSIER, SUITE_EXPORTS] if rapport.ecrits else []
    suites.append(SUITE_AUTRES_SCANS)
    return suites


def dossier_a_ouvrir(rapport: RapportDEcriture) -> Path | None:
    """Le dossier que « Ouvrir le dossier des lots » designe, ou `None`.

    C'est le **parent commun** des dossiers reellement ecrits : donc le dossier
    du lot quand il n'y en a qu'un, et le dossier qui les contient tous des
    qu'il y en a plusieurs. Il n'y a pas de raison d'elire un lot parmi
    plusieurs, et en ouvrir un seul cacherait les autres derriere un libelle qui
    les annonce au pluriel.

    Les chemins sont ceux que **le coeur a rendus**, resolus par
    :func:`chemin_du_lot` : aucune recomposition depuis un slug, ce qui
    ouvrirait un dossier ou l'ecriture n'a peut-etre pas eu lieu -- la
    divergence qu'`EPIC11-ARB-46` interdit (« l'apercu ne peut jamais
    mentir »).
    """
    dossiers = [str(chemin) for chemin in
                (chemin_du_lot(rapport, lot) for lot in rapport.ecrits)
                if chemin is not None]
    if not dossiers:
        return None
    try:
        commun = os.path.commonpath(dossiers)
    except ValueError:
        # Des chemins sans racine commune -- deux volumes sous Windows, un
        # relatif et un absolu. Aucun dossier ne les contient tous ; on ouvre
        # celui du premier lot ecrit, et le fait affiche NOMME le chemin
        # ouvert, si bien que l'operateur voit lequel.
        commun = dossiers[0]
    return Path(commun)


def remonter_a_l_ouverture_de_l_atelier(app) -> None:
    """Depiler jusqu'a la **page d'ouverture** de l'atelier Scan (`E3-0`).

    **Ce n'est pas le depilement de l'atelier Extraction, et l'ecart est
    mesure.** Cote Extraction, `remonter_a_l_ouverture_de_l_atelier` depile les
    **passages** et s'arrete au premier palier non transitoire, parce que cet
    atelier n'a qu'une seule station : `EcranRushes`. Le Scan en empile
    **quatre** -- `E3-0` (le menu), `E3-1` (le depot), `E3-3` / `E3-4` (le
    rapport) et `E3-5` (le choix de calibration), toutes `TRANSITOIRE = False`
    --, si bien que la meme regle s'arreterait sur `E3-5`, c'est-a-dire sur le
    choix de calibration de la passe qui vient de finir. « Detecter d'autres
    scans » y ramenerait l'operateur devant un profil a valider pour un lot
    deja ecrit.

    On depile donc **jusqu'a un rang**, comme `revenir_aux_ateliers` le fait un
    cran plus haut, et pour la meme raison : la profondeur d'un atelier n'est
    pas connue de celui qui remonte. Le rang vise est celui de la premiere
    station de l'atelier, `RANG_DES_ATELIERS + 1` -- deduit, jamais ecrit en
    dur, pour qu'un palier insere entre le projet et les ateliers ne le fausse
    pas.

    **On ne remonte pas plus haut** (`EPIC11-ARB-13`, verbatim : « la fin d'une
    execution ramene au menu des ateliers du projet ouvert [...], jamais a
    l'ecran projet ») : cette suite-ci s'arrete un cran EN DESSOUS du menu, dans
    l'atelier ou l'operateur travaille -- c'est le retour, et lui seul, qui
    remonte au menu.
    """
    vise = app.RANG_DES_ATELIERS + 1
    while len(app.screen_stack) > 1 and (app.rang > vise
                                         or app.passages_empiles):
        app.pop_screen()


def suivre(app, rapport: RapportDEcriture, suite: str, *,
           encoder_un_master: Callable[..., Any] | None = None) -> None:
    """Ce que `E3-8` fait d'une suite choisie. **Aucune n'est muette.**

    Quatre destinations, et la derniere est le filet :

    * :data:`SUITE_DOSSIER` remet le dossier des lots ecrits a l'explorateur du
      bureau et **dit** ce qui s'est passe -- y compris qu'aucun bureau n'est
      joignable ici, ce qui est le cas d'un conteneur sans affichage.
      Tolerance nommee d'`EPIC11-ARB-85`, et **la TUI ne se quitte pas** ;
    * :data:`SUITE_AUTRES_SCANS` remonte a la page d'ouverture de l'atelier ;
    * :data:`SUITE_EXPORTS` ouvre l'atelier Exports sur les lots scannes --
      voir :func:`encoder_un_master_depuis_ces_lots` ;
    * **tout libelle inconnu** mene a l'ecran qui **NOMME** l'absence. C'est la
      cinquieme consigne du lot `K3` : « une suite sans destination doit le
      DIRE, pas ne rien faire », et le filet est ce qui empeche qu'une suite
      ajoutee demain redevienne decorative en silence.

    **Le docstring de cette fonction a ete FAUX pendant quatre jours**, et
    c'est ce qui a rendu le manque invisible en relecture (`MQ-5`, audit du
    2026-09-06) : il ecrivait « :data:`SUITE_EXPORTS`, dont l'atelier n'existe
    pas » alors que la story 11.8 l'avait livre et que
    `ChaineReelle.atelier_exports` le cablait. Frere exact de `MQ-4`, cote
    Extraction. La frontiere qui mesure desormais ce fait vit dans
    `tests/unit/tui/test_couverture_des_suites.py`.

    **Ce que cette fonction ne fait jamais** : rien ecrire, rien effacer, rien
    relancer. Une suite est une navigation ; l'ecriture est finie quand `E3-8`
    monte.
    """
    if suite == SUITE_DOSSIER:
        ouvrir_le_dossier_des_lots(app, rapport)
        return
    if suite == SUITE_AUTRES_SCANS:
        remonter_a_l_ouverture_de_l_atelier(app)
        return
    if suite == SUITE_EXPORTS and dossier_du_projet(rapport) is not None:
        encoder_un_master_depuis_ces_lots(app, rapport,
                                          ouvrir=encoder_un_master)
        return
    # Import tardif : `coque` ne connait pas les ateliers, et l'inverse ne vaut
    # qu'au moment de l'appel.
    from .coque import EcranPasEncore
    app.descendre(EcranPasEncore(suite, app.QUAND_ARRIVENT_LES_ATELIERS))


def encoder_un_master_depuis_ces_lots(
        app, rapport: RapportDEcriture, *,
        ouvrir: Callable[..., Any] | None = None) -> None:
    """`MQ-5` : l'atelier Exports, ouvert sur les lots qui viennent d'etre ecrits.

    **On REMONTE AU MENU DES ATELIERS d'abord, et c'est la moitie du geste.**
    Cette suite change d'atelier, et le Scan empile **quatre** stations : sans
    depilement, `Echap` depuis `E4-1` ramenerait l'operateur sur le choix de
    calibration d'une passe deja ecrite. Meme finding `F3` que cote Pdf, et le
    meme remede. On remonte au menu et **pas plus haut** (`EPIC11-ARB-13`).

    **L'atelier Exports n'a pas de menu** (`EPIC11-ARB-28`, verbatim :
    « Extraction et Exports n'en ont pas ») : ce qui monte est donc `E4-1`, la
    designation du lot, et non une page d'ouverture qui n'existe pas.

    **Aucun lot n'est passe**, et c'est voulu : `E4-1` relit le manifeste, ou
    la passe d'ecriture vient d'inscrire ce qu'elle a ecrit. Lui remettre une
    liste calculee ici la ferait diverger de celle du disque -- « l'apercu ne
    peut jamais mentir » (`EPIC11-ARB-46`).

    **Le dossier projet est deduit du MANIFESTE que la passe a mis a jour**
    (:func:`dossier_du_projet`), jamais du dossier courant du processus : c'est
    la meme derivation que celle de « ouvrir le dossier des lots », et son
    absence est gardee **par l'appelant** -- un rapport sans manifeste retombe
    sur le filet, qui nomme, plutot que d'ouvrir un atelier n'importe ou.
    """
    from .atelier_exports_parcours import ouvrir_l_atelier_exports

    dossier = dossier_du_projet(rapport)
    # **`CoqueTui.revenir_aux_ateliers` possede la regle, et on l'APPELLE.**
    # Elle porte deux conditions, dont celle qui manquait a la troisieme
    # occurrence de `V2-M1` -- on depile tant qu'on est trop bas ET tant que le
    # sommet est un passage. Un repli « au cas ou l'application ne saurait pas »
    # a ete ecrit ici puis **retire** : le mutant qui inversait sa garde
    # survivait, ce qui mesure exactement ce qu'il etait -- une quatrieme
    # redaction de la meme regle, equivalente tant qu'elle l'est et muette le
    # jour ou elle cesserait de l'etre. On appelle donc, ou on tombe.
    app.revenir_aux_ateliers()
    (ouvrir or ouvrir_l_atelier_exports)(app, dossier)


def ouvrir_le_dossier_des_lots(app, rapport: RapportDEcriture) -> str:
    """Remettre le dossier des lots ecrits a l'explorateur du systeme (AC 7.5).

    **Le resultat est DIT, dans les deux cas**, et c'est la moitie du geste :
    un echec silencieux serait indistinguable de la suite decorative que le
    finding `K3` a payee. C'est pour cela que
    :func:`~mixed_media_utility.tui.execution.ouvrir_dans_l_explorateur_du_systeme`
    rend une phrase plutot qu'un booleen. La phrase est **une mesure** -- un
    chemin, ou un motif nomme -- et jamais une touche ni un conseil
    (`EPIC11-ARB-56`).

    **L'ecran ne change pas** : on reste sur `E3-8`, dont les chiffres restent
    lisibles. Descendre d'un palier pour annoncer qu'un dossier a ete ouvert
    ferait perdre le compte rendu au moment meme ou l'operateur va le comparer
    au contenu du dossier -- et ce serait quitter la TUI par la porte de
    derriere.

    Rend le fait affiche, pour qu'un banc le mesure sans relire l'ecran.
    """
    dossier = dossier_a_ouvrir(rapport)
    fait = (AUCUN_LOT_A_OUVRIR if dossier is None
            else ouvrir_dans_l_explorateur_du_systeme(dossier))
    if getattr(app, "ascii_seul", False):
        fait = jetons.replier_ascii(fait)
    app.palier_courant.poser_etat(fait)
    return fait


# ---------------------------------------------------------------------------
# L'ecran
# ---------------------------------------------------------------------------

class EcranResultatDuScan(EcranResultat):
    """`E3-8` -- l'`EcranResultat` livre, avec le **segment de bandeau du Scan**.

    Une sous-classe et **rien d'autre** : le cartouche, les suites navigables,
    la ligne de raccourcis contextuelle et `Tab journal` sont ceux de
    `execution.EcranResultat`, mesures par la story 11.1 et par le lot I de la
    11.4. `execution.py` n'est **pas modifie** -- c'est un module partage avec
    l'atelier Extraction, et le toucher serait la contention que la regle de
    decoupage interdit (meme geste que `EcranEcritureDuScan` au lot E).

    Ce qu'elle redonne tient en un attribut : le **titre**, qui est le segment
    du milieu du bandeau (`mmu · projet_demo · Scan`, maquette l. 2). La base
    porte `Resultat`, qui nommerait l'ecran au lieu de l'atelier -- l'operateur
    perdrait, sur le seul ecran ou il en a besoin, l'indication de l'atelier
    d'ou sortent ces TIFF.
    """

    titre = PALIER_DE_L_ATELIER


def ouvrir_le_resultat(app, rapport: RapportDEcriture, *,
                       journal, duree: float | None,
                       attendues: int | None,
                       sur_suite: Callable[[str], None],
                       objet: str | None = None) -> EcranResultatDuScan:
    """Monter `E3-8` sur les chiffres mesures, avec ses suites navigables.

    **Les quatre mots-cles sont REQUIS, et c'est structurel.** Un
    `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence** : c'est le finding `K3`, ou les quatre
    suites d'un ecran de resultat etaient navigables et decoratives, et le
    finding `I8`, ou `Tab journal` etait annonce par la maquette et traite par
    personne. Les rendre requis fait de l'oubli une **erreur d'appel** ; passer
    `None` reste possible et **dit** « je ne sais pas », auquel cas la ligne
    concernee est omise.

    ``journal`` est celui de l'execution qui vient de finir -- cote produit,
    `EcranEcritureDuScan.surface.journal`. Sans lui, `E3-8` n'annonce pas
    `Tab journal` et ne le traite pas : sa ligne de raccourcis est
    **contextuelle** (AC 7.1), et une touche annoncee qui ne fait rien se lit
    comme une panne.

    ``objet`` par defaut est la mesure de la passe (:func:`objet_du_bandeau`) ;
    le laisser a `None` est le cas nominal, le passer sert aux bancs qui
    veulent epingler la droite du bandeau.
    """
    ascii_seul = getattr(app, "ascii_seul", False)
    ecran = EcranResultatDuScan(
        panneau_du_resultat(rapport, ascii_seul, duree=duree),
        suites_du_resultat(rapport), sur_suite=sur_suite, journal=journal,
        objet=objet_du_bandeau(rapport) if objet is None else objet)
    app.descendre(ecran)
    # **`poser_etat` APRES le montage**, et jamais avant : la ligne d'etat est
    # posee sur l'ecran monte, et un ecran pas encore empile la perdrait au
    # premier dessin.
    ecran.poser_etat(ligne_d_etat_du_resultat(rapport, attendues, ascii_seul))
    return ecran


def conclure(app, rapport: RapportDEcriture, *, journal,
             duree: float | None, attendues: int | None,
             objet: str | None = None) -> EcranResultatDuScan:
    """Le point d'appel du **produit** : `E3-8`, avec son aiguillage deja cable.

    C'est ce que le cablage du temps 2 passe en `sur_rapport` a
    `atelier_scan_ecriture.executer_et_conclure`. Il existe pour que le rappel
    des suites n'ait pas a etre recompose au point d'appel : c'est exactement
    la ou le finding `K3` a mordu -- l'ecran savait s'en servir, la fonction
    savait le transmettre, et **le point d'appel ne le passait pas**.
    """
    return ouvrir_le_resultat(
        app, rapport, journal=journal, duree=duree, attendues=attendues,
        objet=objet, sur_suite=lambda suite: suivre(app, rapport, suite))


__all__ = [
    "AUCUN_LOT_A_OUVRIR",
    "AUCUN_REFUS",
    "CALIBRATION_AUCUNE",
    "CALIBRATION_PAGE_DU_LOT",
    "CALIBRATION_PROFIL_DESIGNE",
    "EcranResultatDuScan",
    "INDENT_DU_MOTIF",
    "LIBELLE_CALIBRATION",
    "LIBELLE_DUREE",
    "LIBELLE_MANIFESTE",
    "LIBELLE_MOTIF",
    "PASSE_INTERROMPUE",
    "SUITE_AUTRES_SCANS",
    "SUITE_DOSSIER",
    "SUITE_EXPORTS",
    "TITRE_ECRIT",
    "UNITE_DE_PROFONDEUR",
    "calibration_du_lot",
    "chemin_du_lot",
    "chronometre",
    "conclure",
    "dossier_a_ouvrir",
    "dossier_du_projet",
    "encoder_un_master_depuis_ces_lots",
    "duree_lisible",
    "ligne_d_etat_du_resultat",
    "ligne_du_lot",
    "lignes_de_calibration",
    "motifs_qui_degradent",
    "objet_du_bandeau",
    "octets_du_dossier",
    "ouvrir_le_dossier_des_lots",
    "ouvrir_le_resultat",
    "panneau_du_resultat",
    "profondeur_du_lot",
    "remonter_a_l_ouverture_de_l_atelier",
    "suites_du_resultat",
    "suivre",
]
