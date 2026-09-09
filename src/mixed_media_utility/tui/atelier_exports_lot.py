# -*- coding: utf-8 -*-
"""`E4-1` -- designer un lot a encoder (story 11.8, lot C, AC 5).

**Ce module ne juge aucun lot, et il n'en liste aucun de sa propre autorite.**
La liste est celle qu'`encode.list_encodable_lots` rend, et **rien d'autre**
(AC 5.1). Le defaut que cette regle ferme est mesure : « un lot reconstruit »
ne designait pas la meme chose des deux cotes, et les deux definitions se
**croisaient** -- un lot a l'etat `scan` portant ses frames est admis par le
coeur alors que `tui/projet_lecture.ETATS_RECONSTRUITS` fermait l'entree
dessus, et un lot recree depuis des payloads porte un etat superieur sans
porter la moindre frame, si bien que la TUI ouvrait et que le coeur refusait.
La table a disparu ; une frontiere AST interdit desormais au paquet `tui/`
entier toute collection litterale d'etats de lot et toute comparaison a un etat
litteral. **Ne pas la rouvrir en « simplifiant ».**

**Les pastilles de completude viennent du DISQUE** (`EPIC11-ARB-186`, Egan
verbatim : « **2.** Avec un glyphe de chargement le temps que tout soit scanne
sur le disque »). Le verdict de chaque lot liste sort d'un balayage reel --
`encode.plan_sequence` sur le dossier, puis `encode.assess_completeness` --,
donc un verdict **toujours exact**, au prix d'un balayage **par lot** a
l'ouverture de l'ecran. Le cout est assume et **rendu visible** : le rotor du
produit (`jetons.rotor`, jamais un caractere en dur) tourne tant qu'un lot
n'est pas compte.

**Consequence de conception, et c'est ce que le banc mesure deux fois : l'ecran
a DEUX etats.** Pendant le balayage et apres. **Aucun verdict n'est affiche
avant d'avoir ete compte** -- un verdict optimiste affiche puis corrige est un
mensonge d'interface, meme bref --, et c'est pourquoi
:class:`ListeDesLotsAEncoder` ne porte aucun verdict par defaut : une pastille
absente est un rotor, jamais un `● complet` provisoire.

**On n'encode pas un lot, on encode un lot RECONSTRUIT** (`EPIC11-ARB-190`,
story 6.8). Des qu'un lot porte plusieurs passes de scan, l'ecran les designe :
`encode.enumerer_les_reconstructions` les rend, **dans l'ordre du manifest**,
et ce module ne les retrie pas. Une passe dont le dossier a disparu du disque
est rendue avec `presente=False` plutot qu'omise, et la designer **refuse en la
nommant** (`encode.check_lot_admission(..., reconstruction_visee=)`), sans se
rabattre en silence sur une autre passe -- c'est la famille de defaut
qu'`EPIC11-ARB-89` ferme, et l'ecran rend ce refus lisible au lieu de le
masquer.

**Ce que cet ecran NE PEUT PAS dire, et il le dit plutot que de le deviner**
(`EPIC11-ARB-193`) : de quelle reconstruction un master deja ecrit est issu.
Rien au manifest ne le porte -- la cle de famille d'un master **ne gagne pas**
la reconstruction --, donc aucune provenance de master n'est affichee ici.

**Ce module n'importe jamais `cli`** (`EPIC11-ARB-67`) et n'ecrit rien : le
point d'entree de coeur de cet atelier est
`encode_master.encoder_le_master_du_lot`, tenu par le parcours.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import encode
from ..io.naming import CANONICAL_ID_MAX_LENGTH
from . import jetons, projet_lecture
from .atelier_exports_reglages import LIBELLE_CADENCE, UNITE_DE_CADENCE
from .atelier_extraction import (Composition, _application_montee,
                                 filet_titre, ligne_de_titre)
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .projet_lecture import accorder

# ---------------------------------------------------------------------------
# Les textes de `E4-1`, verbatim de la maquette validee
# ---------------------------------------------------------------------------

#: La question de l'ecran. Recopiee au caractere pres, accents compris.
TITRE_DES_LOTS = "Quel lot encoder ?"

#: Le titre du filet qui separe la liste des faits du lot **designe**. C'est la
#: forme d'origine -- un bloc de faits techniques SOUS filet, en bas de l'ecran
#: --, celle que `E5-1` a reprise ensuite pour son lot survole.
FILET_DU_LOT = "Le lot désigné"

#: Les quatre libelles de la carte. `LIBELLE_CADENCE` n'est **pas** ecrit ici :
#: il est lu de l'ecran des reglages, parce que « le meme champ porte le meme
#: nom sur les quatre ecrans qui l'affichent, sans quoi l'operateur croit en
#: voir deux » (`EPIC11-ARB-192`). Une seconde redaction du libelle d'Egan
#: divergerait a la premiere retouche.
LIBELLE_RECONSTRUCTION = "Reconstruction"
LIBELLE_FRAMES = "Frames retenues"
LIBELLE_GEOMETRIE = "Géométrie · bits"

#: Les trois mentions de completude, celles de l'AC 5.2. **Le glyphe n'est pas
#: ecrit ici** : chaque mention voyage avec un NOM d'etat de `jetons.GLYPHES`,
#: et c'est `jetons.marque` qui les assemble -- un `●` ecrit en dur serait
#: invisible en `--ascii`.
MENTION_COMPLET = "complet"
MENTION_MIRES = "{cardinal} mires"
MENTION_INCOMPLET = "incomplet"

#: Ce que la colonne de droite dit tant que le lot n'a **pas encore** ete
#: compte. Elle porte le rotor, qui n'est pas un etat : un verdict pas encore
#: rendu ne porte aucune couleur d'etat, ce qui est exactement ce qu'on veut.
MENTION_BALAYAGE = "balayage"

#: Ce que la COLONNE DE DROITE d'une ligne affiche quand le coeur a refuse ce
#: lot. **Le code, lui, ne tient pas dans cette colonne** : la maquette pose la
#: pastille apres un champ de nom de la longueur maximale du produit, ce qui
#: laisse vingt et une colonnes -- moins que `DOSSIER_DE_LOT_ABSENT`. Le
#: tronquer y ferait un refus a demi lisible, c'est-a-dire pire qu'un refus
#: court : le code entier est donc **nomme** la ou il tient, sur la carte du lot
#: designe et en ligne d'etat, et la liste porte le seul fait qui tient ici.
MENTION_REFUS = "refusé"

#: Ce qu'une passe de scan dont le dossier a disparu du disque affiche. Elle
#: reste **listee** (le coeur l'enumere plutot que de la sauter), et la
#: designer refuse en la nommant.
MENTION_PASSE_ABSENTE = "absente du disque"

#: Ce qu'une passe qui ne declare aucun dossier affiche. Le schema ne rend
#: `required` que `ingest_slug`, donc le cas est **legal** : il se dit.
MENTION_PASSE_SANS_DOSSIER = "aucun dossier déclaré"

#: Le prefixe de rang d'une passe. `v2` est ce que `E4-1` dessine, et le rang
#: vient d'`io.naming.rang_du_fragment_de_version` par l'intermediaire du
#: coeur : la forme `_v<rang>` a un seul proprietaire, et ce n'est pas cet
#: ecran.
PREFIXE_DE_RANG = "v{rang}"
#: Ce qu'une passe sans rang lisible affiche a la place. Elle n'a pas de rang
#: parce qu'elle n'a pas de dossier ; inventer `v1` la ferait passer pour
#: l'origine.
RANG_INCONNU = "v?"

#: `124 sur 124 attendues` -- la ligne de frames de la carte.
MOTIF_DES_FRAMES = "{trouvees} sur {attendues} attendues"
#: Ce qu'elle dit quand `expected_frame_count` n'est pas ecrit -- il ne l'est
#: pas quand la derniere page manque. Le cardinal trouve reste vrai ; c'est le
#: cardinal de reference qui n'existe pas, et on ne l'invente pas.
MOTIF_DES_FRAMES_SANS_REFERENCE = "{trouvees} trouvées"
#: Ce qu'elle dit tant que le balayage n'a pas eu lieu. **Aucun chiffre** : le
#: seul cardinal disponible avant le balayage serait celui du manifest, et
#: l'afficher puis le corriger serait le mensonge que ce rotor existe pour
#: eviter.
MOTIF_DES_FRAMES_EN_BALAYAGE = "comptage en cours"

#: `25 fps` -- la valeur de la cadence source, et son unite.
MOTIF_DE_LA_CADENCE = "{cadence} " + UNITE_DE_CADENCE

#: **La provenance affichee de la cadence source (AC 5.4).** Elle est exacte
#: dans TOUS les regimes : `encode.resolve_source_rate` lit
#: `lots[].timecode_base_fps`, c'est-a-dire le manifest, quelle que soit la
#: route par laquelle la valeur y est entree.
#:
#: **Le mot « QR » n'apparait nulle part, et c'est une decision mesuree.** Le
#: dessin d'origine disait `lue au QR (payload 2.1)` ; c'est faux dans le cas
#: courant -- un lot ne d'une extraction porte `timecode_base_fps` ecrit par
#: `io/extraction_manifest.py` **sans qu'aucun QR n'existe**. Le QR n'est que
#: l'une des deux routes, et **le manifest ne garde aucune trace de celle qui
#: a servi** : aucun champ ne distingue la valeur ecrite par l'extraction de
#: celle recopiee d'un payload. L'ecran ne peut donc pas dire « lue au QR »
#: sans le deviner, et il ne le devine pas. Un banc le tient en frontiere
#: negative, dans les deux regimes.
MENTION_PROVENANCE_DE_LA_CADENCE = "lue au manifest"

#: Ce que la carte affiche quand le lot ne porte aucune cadence source
#: (AC 5.3). Le refus `encode.ENCODE_SOURCE_RATE_MISSING` s'affiche comme un
#: **etat de la carte**, pas comme un plantage : le champ de l'ecran de
#: reglages est le seul endroit d'ou la declaration peut venir, et c'est la
#: qu'il faut aller.
MENTION_CADENCE_ABSENTE = "le lot n'en déclare aucune"

#: `1920×1080 · 16 bits` -- la geometrie du lot. **Chaque moitie a sa source et
#: peut manquer seule** : la geometrie vient de `rushes[].resolution_source`
#: (ecrite par l'extraction, et absente par construction d'un manifest
#: reconstruit depuis le scan seul), la profondeur de
#: `lots[].output_bit_depth`. Un segment inconnu **disparait** plutot que de
#: sortir a zero, et la ligne entiere disparait quand les deux manquent.
MOTIF_DE_LA_GEOMETRIE = "{largeur}×{hauteur}"
MOTIF_DES_BITS = "{profondeur} bits"

#: Les separateurs de la carte et de la ligne d'etat, tels que la maquette les
#: ecrit.
SEPARATEUR = " · "
SEPARATEUR_DU_LOT = " : "
SEPARATEUR_DES_PASSES = ", "

# ---------------------------------------------------------------------------
# La ligne d'etat -- une MESURE, jamais une touche (`EPIC11-ARB-56`, AC 5.5)
# ---------------------------------------------------------------------------
#
# **Le defaut a ne pas reproduire est nomme, et il etait dessine** : la ligne
# `Seuls les lots reconstruits sont listés — un lot extrait ne s'encode pas.`
# porte une mesure dans sa premiere moitie et un **motif de conception** dans
# la seconde. `EPIC11-ARB-56` interdit la seconde : la ligne d'etat dit ce que
# la machine a compte, elle n'explique pas pourquoi l'ecran est fait comme ca,
# et elle ne porte **aucune touche**.

#: Pendant le balayage : combien de lots sont comptes, sur combien.
MOTIF_DU_BALAYAGE = "{comptes} compté{accord} sur {total}"
#: Une fois le balayage fini. Le `sur N` tombe parce qu'il ne mesure plus rien.
MOTIF_DU_BALAYAGE_FINI = "{comptes} compté{accord}"
#: Ce que la ligne d'etat dit du lot designe, une fois qu'il est compte.
MOTIF_DE_L_ETAT_DU_LOT = "{trouvees} frames sur {attendues}"
MOTIF_DE_L_ETAT_DU_LOT_SANS_REFERENCE = "{trouvees} frames"
#: Le cardinal des passes de scan du lot designe, quand il en porte plusieurs.
MOTIF_DES_PASSES = "{cardinal} reconstruction{accord}"

# ---------------------------------------------------------------------------
# Les trois lignes de raccourcis, contextuelles
# ---------------------------------------------------------------------------
#
# **`Tab` nomme sa DESTINATION** (`EPIC11-ARB-68`), et il n'est annonce que
# quand il a une destination : un lot qui ne porte qu'une passe de scan n'ouvre
# aucun champ de reconstruction, et annoncer une touche qui ne fait rien est la
# meme faute -- en plus petit -- que le `--nouvelle-version` d'un refus de
# coeur qui ne l'offre pas.

#: Le focus sur la liste des lots, le lot designe portant plusieurs passes.
#: C'est la ligne de la maquette, au caractere pres.
#: MESURE: 67/72
RACCOURCIS_LOTS = ("⏎ choisir  ↑↓ naviguer  Tab reconstruction  "
                   "Échap ateliers  F1 aide")

#: Le focus sur la liste des lots, le lot designe ne portant qu'une passe (ou
#: aucune) : il n'y a rien a designer, donc rien a annoncer.
#: MESURE: 47/52
RACCOURCIS_LOTS_SANS_PASSES = "⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide"

#: Le focus sur le champ des reconstructions. Seul le segment `Tab` change :
#: sa destination est le retour a la liste des lots.
#: MESURE: 56/61
RACCOURCIS_RECONSTRUCTIONS = ("⏎ choisir  ↑↓ naviguer  Tab lot  "
                              "Échap ateliers  F1 aide")

#: Ce que `⏎ choisir` demande, quand l'ecran qui le sert n'existe pas encore.
#: **L'absence NE SE TAIT PAS** : un `if ... is not None` sans branche `else`
#: rendrait la touche indistinguable d'un clavier casse.
CE_QUI_MANQUE_APRES_LE_LOT = "Régler le profil et la résolution"
QUAND_LES_REGLAGES = "les reglages de l'atelier Exports"

# ---------------------------------------------------------------------------
# La grille, relevee sur la maquette validee
# ---------------------------------------------------------------------------

#: Hauteur FIXE de la zone de liste. **Derivee de la maquette et non choisie**
#: : `E4-1` pose le filet « Le lot désigné » a la ligne 12 de la fenetre, ce
#: qui laisse exactement cinq lignes a la liste une fois le blanc de tete, le
#: titre et le blanc qui le suit poses. Une hauteur variable ferait danser le
#: filet -- et la carte du lot avec lui -- a chaque projet.
HAUTEUR_LISTE = 5

#: Largeur de la colonne des noms de lot. **Elle se lit du coeur** : c'est la
#: borne du produit (`io.naming.CANONICAL_ID_MAX_LENGTH`), pas la longueur du
#: plus long nom de la demonstration -- une colonne calee sur la demonstration
#: retrecit des que la demonstration change (note 1 d'Egan du 2026-09-01).
LARGEUR_DU_NOM = CANONICAL_ID_MAX_LENGTH

#: Indentation des lignes de liste et des lignes de la carte.
_INDENT = 5
#: Deux colonnes de respiration au bord droit, comme partout ailleurs.
_MARGE_DROITE = 2

#: Largeur de la colonne des libelles de la carte. **Derivee du libelle le plus
#: long et jamais ecrite en chiffre** : c'est ce que le generateur des
#: maquettes fait lui-meme (`LIBELLE = len("Cadence du rushe source") + 4`), et
#: deux redactions de la meme colonne divergeraient a la premiere retouche du
#: libelle -- lequel EST la decision `EPIC11-ARB-192`.
_LARGEUR_DU_LIBELLE = len(LIBELLE_CADENCE) + 4
#: Largeur du champ de frames, mention d'etat a sa droite (colonne 58 de la
#: maquette, l'indentation et le libelle valant 32).
_LARGEUR_DES_FRAMES = 26
#: Largeur du champ de cadence, provenance a sa droite (colonne 46).
_LARGEUR_DE_LA_CADENCE = 14

# ---------------------------------------------------------------------------
# Les deux focus. **Aucun n'est un mot du coeur**, et c'est verifie : `tui/`
# n'a le droit ni de collectionner ni de comparer un etat de lot litteral, et
# `reconstruction` en est un.
# ---------------------------------------------------------------------------

FOCUS_LOTS = "liste-des-lots"
FOCUS_VERSIONS = "champ-des-versions"


class LotsMalFormes(ValueError):
    """Un invariant que la revue ne devrait pas avoir a trouver est viole."""


def _replie(texte: str, ascii_seul: bool = False) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_gauche(texte: str, largeur: int, ascii_seul: bool = False) -> str:
    """Un champ cale a gauche, mesure en **COLONNES** et jamais en `len()`.

    Un ideogramme occupe deux colonnes : `str.ljust` calerait un champ de dix
    caracteres sur vingt colonnes, et toutes les colonnes de droite partiraient
    avec.
    """
    texte = jetons.ajuster(texte, largeur, ascii_seul)
    return texte + " " * max(0, largeur - jetons.colonnes(texte))


# ---------------------------------------------------------------------------
# Le balayage du disque -- chaque JUGEMENT est celui du coeur (`EPIC11-ARB-186`)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Balayage:
    """Ce qu'un balayage rend : le verdict du coeur, **ou** son refus nomme.

    Les deux champs sont exclusifs, et la distinction n'est pas cosmetique :
    un lot dont le dossier a disparu entre l'enumeration et le balayage n'est
    pas « incomplet », il est injoignable. Les confondre afficherait `✕
    incomplet` sur un lot dont rien ne dit qu'il manque une frame.

    ``refus`` porte le **code** du coeur, jamais une phrase de l'ecran : c'est
    lui qui nomme, et le recopier en francais en ferait une seconde redaction
    qui divergerait au premier ajustement du coeur.
    """

    verdict: encode.CompletenessVerdict | None = None
    refus: str | None = None

    @property
    def compte(self) -> bool:
        """Vrai des que le balayage a eu lieu, **verdict ou refus**.

        Un refus est un resultat : le rotor s'arrete dessus. Le laisser tourner
        indefiniment ferait croire a un balayage sans fin, ce qui est
        exactement ce qu'il n'est pas.
        """
        return self.verdict is not None or self.refus is not None


def balayer_le_lot(lot: Mapping[str, Any], project_dir: Path,
                   manifeste: Mapping[str, Any],
                   reconstruction_visee: object = None) -> Balayage:
    """Le verdict de completude d'un lot, **lu sur le disque** (AC 5.2).

    Quatre appels au coeur, et **aucun jugement ecrit ici** :
    `check_lot_admission` resout le dossier -- celui de la passe designee quand
    il y en a une, le scalaire sinon --, `resolve_frame_rate` rend la cadence
    de selection qui nomme les frames, `plan_sequence` ordonne ce que le
    dossier porte, et `assess_completeness` rend le verdict.

    **Ce que cette fonction ecrit d'elle-meme se limite a la lecture du
    dossier** -- les noms de fichiers, tries, et ceux de taille nulle. C'est la
    seule chose que le coeur ne sait pas faire depuis une signature publique :
    aucune fonction d'`encode` ne rend un `CompletenessVerdict` a partir d'un
    chemin, et `plan_encode`, qui le ferait, exige un profil, une resolution,
    et **leve** sur un lot incomplet (`enforce_completeness`) -- c'est-a-dire
    precisement sur les lots que cet ecran doit pouvoir montrer. Le manque est
    **signale** plutot que masque : c'est un point d'entree de coeur qui
    manque, pas une regle que la TUI aurait le droit de reecrire.

    **Aucun refus ne fait tomber l'ecran** : un dossier disparu, une cadence
    inexploitable, un disque qui refuse la lecture rendent un
    :class:`Balayage` qui porte le motif. L'ecran d'une liste ne plante pas
    parce qu'un lot sur cinq est abime.
    """
    try:
        dossier = encode.check_lot_admission(
            lot, Path(project_dir), reconstruction_visee=reconstruction_visee)
        fps_target, _exact = encode.resolve_frame_rate(lot)
        entrees = sorted((entree for entree in dossier.iterdir()
                          if entree.is_file()), key=lambda e: e.name)
        noms = [entree.name for entree in entrees]
        # Un fichier de 0 octet sous un nom conforme est un artefact
        # d'ecriture interrompue, pas une frame : c'est le coeur qui le dit, et
        # c'est lui qui l'ecarte -- on ne fait que lui passer la liste.
        vides = [entree.name for entree in entrees
                 if entree.stat().st_size == 0]
        sequence = encode.plan_sequence(
            noms, rush_id=str(lot.get("rush_id") or ""),
            fps_target=fps_target, empty_names=vides)
    except encode.EncodeDecisionError as refus:
        return Balayage(refus=refus.code)
    except OSError as erreur:
        return Balayage(refus=type(erreur).__name__)
    reconstruction = encode.reconstruction_for_lot(
        manifeste, str(lot.get("lot_id") or ""))
    return Balayage(verdict=encode.assess_completeness(
        lot, sequence, reconstruction))


def jeton_du_verdict(verdict: encode.CompletenessVerdict,
                     ascii_seul: bool = False) -> str:
    """`● complet`, `▲ 3 mires` ou `✕ incomplet` -- AC 5.2, mot pour mot.

    **Le vocabulaire se lit du coeur, jamais recopie** : les trois branches
    sont celles de `CompletenessVerdict` -- `expected == found` (que le coeur
    porte lui-meme en `complete`), `synthetic_present` non vide, et le reste.
    Aucun etat de lot, aucun code de refus n'entre ici.

    **L'ordre des trois branches est celui de l'AC**, et il n'est pas
    interchangeable. `● complet` d'abord : un lot dont le cardinal est atteint
    est complet, mires comprises -- c'est ce qu'Egan dit du recapitulatif de
    `E4-3` (« si c'est complet on n'a pas de mires, si c'est incomplet on a des
    mires »). `▲ N mires` ensuite : un lot qui n'atteint pas son cardinal mais
    porte des substituts presents, ou le triangle dit qu'il reste de la matiere
    de remplacement. `✕ incomplet` en dernier, pour tout le reste.
    """
    if verdict.complete:
        return jetons.marque("complete", _replie(MENTION_COMPLET, ascii_seul),
                             ascii_seul)
    if verdict.synthetic_present:
        mention = MENTION_MIRES.format(cardinal=len(verdict.synthetic_present))
        return jetons.marque("substitute", _replie(mention, ascii_seul),
                             ascii_seul)
    return jetons.marque("absent", _replie(MENTION_INCOMPLET, ascii_seul),
                         ascii_seul)


def etat_du_verdict(verdict: encode.CompletenessVerdict) -> str:
    """Le NOM d'etat qui teinte la ligne, dans le meme ordre que le jeton.

    Il est **donne** a `jetons.peindre` (`EPIC11-ARB-71`) plutot que retrouve
    dans le texte : la reconnaissance par motif marcherait ici par accident, et
    cesserait de marcher au premier lot dont le nom vaudrait `x` en repli
    ASCII.
    """
    if verdict.complete:
        return "complete"
    if verdict.synthetic_present:
        return "substitute"
    return "absent"


# ---------------------------------------------------------------------------
# Le modele -- pur, sans `textual`, sans ecriture
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Designation:
    """Ce que `⏎` rend a l'appelant : un lot, un dossier, une passe.

    ``reconstruction_visee`` est le **dossier** de la passe designee, dans la
    forme que `encode.check_lot_admission` et `encode.plan_encode` acceptent
    telle quelle -- jamais un rang traduit ici. `None` quand le lot ne porte
    aucun historique de passes : c'est alors le comportement d'avant la story
    6.8, la derniere passe, et les messages du coeur avec lui.

    ``balayage`` peut valoir `None` : `⏎` n'attend pas la fin du balayage,
    parce que l'ecran des reglages n'a pas besoin du verdict pour s'ouvrir. Le
    verdict, lui, est ce que la confirmation exige -- et elle le redemandera au
    coeur, qui est le seul a le rendre.
    """

    lot: Mapping[str, Any]
    dossier: Path
    reconstruction_visee: object = None
    balayage: Balayage | None = None

    @property
    def lot_id(self) -> str:
        return str(self.lot.get("lot_id") or "")


@dataclass
class LotAListe:
    """Une ligne de la liste : le lot admis, et ses passes de scan.

    **Rien n'est recalcule ici.** ``lot`` et ``dossier`` viennent d'un
    `encode.EncodableLot` -- le dossier est rendu **avec** le lot par le coeur
    plutot que laisse a recomposer --, et ``passes`` d'
    `encode.enumerer_les_reconstructions`, **dans l'ordre du manifest**.
    """

    lot: Mapping[str, Any]
    dossier: Path
    passes: tuple[encode.ReconstructionDeLot, ...] = ()
    #: Le rang, dans :attr:`passes`, de la passe retenue. **Il est pose a la
    #: construction** par :meth:`_passe_par_defaut` et non recu : la passe
    #: retenue a l'ouverture est une propriete du lot, pas un choix de
    #: l'appelant, et la laisser donner ferait de chaque appelant une seconde
    #: redaction de la regle « celle que le lot declare ».
    passe: int = 0

    def __post_init__(self) -> None:
        if not self.lot_id:
            raise LotsMalFormes(
                "Un lot porte un identifiant : une ligne sans nom ne se "
                "designe pas, elle ne se lit meme pas.")
        self.passe = self._passe_par_defaut()

    @property
    def lot_id(self) -> str:
        return str(self.lot.get("lot_id") or "")

    def _passe_par_defaut(self) -> int:
        """La passe retenue a l'ouverture : **celle que le lot declare**.

        C'est l'entree dont le `output_frames_dir` est celui du champ
        **scalaire** du lot, c'est-a-dire celle que le coeur encoderait sans
        designation. Elle existe et son dossier est present par construction --
        c'est ce que la garde d'admission a verifie pour que ce lot soit
        liste --, si bien que l'ouverture de l'ecran ne peut pas tomber sur un
        refus.

        Repli quand aucune entree ne correspond (historique ecrit par une passe
        anterieure a l'arbitrage, scalaire reecrit ailleurs) : la **derniere**
        entree, l'historique etant chronologique. Le repli peut, lui, mener a
        un refus -- et il le dira.
        """
        if not self.passes:
            return 0
        declare = self.lot.get("output_frames_dir")
        for rang, passe in enumerate(self.passes):
            if declare and passe.output_frames_dir == declare:
                return rang
        return len(self.passes) - 1

    @property
    def porte_des_passes(self) -> bool:
        """Vrai quand il y a **plusieurs** passes, donc quelque chose a choisir.

        Une passe unique n'ouvre aucun champ : « on designe un lot PUIS sa
        reconstruction **des qu'il en porte plusieurs** ». Un champ a une seule
        valeur n'est pas un choix, et sa touche ne serait annoncee pour rien.
        """
        return len(self.passes) >= 2

    @property
    def passe_retenue(self) -> encode.ReconstructionDeLot | None:
        if not self.passes:
            return None
        return self.passes[self.passe]

    @property
    def reconstruction_visee(self) -> object:
        """Ce qui part au coeur : le **dossier** de la passe retenue, ou `None`.

        `None` quand le lot ne porte aucun historique : le coeur retombe alors
        sur le champ scalaire, c'est-a-dire sur le comportement d'avant la
        story 6.8, messages compris. Le lui passer explicitement quand il n'y a
        rien a designer ferait dire `RECONSTRUCTION_INCONNUE` a un lot qui n'a
        jamais ete scanne deux fois.
        """
        retenue = self.passe_retenue
        if retenue is None or not retenue.output_frames_dir:
            return None
        return retenue.output_frames_dir

    def deplacer_la_passe(self, pas: int) -> None:
        """`↑↓` dans le champ des passes. Le rang reste dans la liste."""
        if not self.passes:
            return
        self.passe = min(max(self.passe + pas, 0), len(self.passes) - 1)


@dataclass
class ListeDesLotsAEncoder:
    """La liste de `E4-1` : les lots encodables, un curseur, une fenetre.

    **Modele pur** -- aucune dependance a `textual`, aucune ecriture. C'est ce
    qui rend mesurables sans terminal les deux appariements a risque de cet
    ecran : la pastille rendue contre le lot qu'elle decrit, et le dossier qui
    part au coeur contre la passe que l'operateur a designee.
    """

    lots: list[LotAListe]
    manifeste: Mapping[str, Any] = field(default_factory=dict)
    project_dir: Path = field(default_factory=Path)
    curseur: int = 0
    premier_visible: int = 0
    focus: str = FOCUS_LOTS
    #: Le pas du rotor. Il ne se remet **jamais** a zero : le modulo est fait
    #: par `jetons.rotor`, precisement pour qu'un ecran qui compte ses propres
    #: pas ne rende pas un `IndexError` au quatrieme tour.
    pas: int = 0
    #: Les balayages faits, indexes par `(lot_id, dossier de la passe)` --
    #: **jamais par rang**. « Deux listes qui doivent rester en correspondance
    #: sont deux occasions de les desapparier » : un verdict pris au rang
    #: serait juste tant que l'ordre des deux collections coincide,
    #: c'est-a-dire jusqu'au premier lot filtre. C'est le mutant `M33`.
    balayages: dict[tuple[str, object], Balayage] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.lots:
            raise LotsMalFormes(
                "Une liste de lots encodables porte au moins un lot ; une "
                "liste vide n'est pas un choix, c'est un ecran sans objet -- "
                "le menu des ateliers conditionne deja l'entree Exports a "
                "l'existence d'un lot encodable.")
        noms = [lot.lot_id for lot in self.lots]
        if len(set(noms)) != len(noms):
            # Deux lignes du meme lot feraient compter deux fois le meme
            # balayage et designer un lot qu'on croirait distinct de l'autre.
            raise LotsMalFormes(f"Deux lots portent le meme identifiant : {noms}")

    # -- construction --------------------------------------------------------

    @classmethod
    def depuis_le_coeur(cls, manifeste: Mapping[str, Any] | None,
                        project_dir: Path | str) -> "ListeDesLotsAEncoder":
        """Les lots qu'`encode.list_encodable_lots` rend, **et rien d'autre**.

        AC 5.1, litteralement : l'ecran ne filtre pas, n'ajoute pas et ne
        retrie pas. L'ordre est celui du manifest -- `lots[]` porte l'ordre de
        **premiere creation**, et le reordonner ferait dire a l'ecran une
        anciennete que le document ne porte pas.
        """
        racine = Path(project_dir)
        document = manifeste if isinstance(manifeste, Mapping) else {}
        return cls(
            lots=[LotAListe(
                lot=encodable.lot,
                dossier=encodable.output_frames_dir,
                passes=tuple(encode.enumerer_les_reconstructions(
                    encodable.lot, racine)))
                for encodable in encode.list_encodable_lots(document, racine)],
            manifeste=document,
            project_dir=racine,
        )

    # -- lecture -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.lots)

    @property
    def courant(self) -> LotAListe:
        """Le lot **sous le curseur** -- celui que la carte decrit."""
        return self.lots[self.curseur]

    def rang(self, lot_id: str) -> int | None:
        for rang, lot in enumerate(self.lots):
            if lot.lot_id == lot_id:
                return rang
        return None

    def _cle(self, lot: LotAListe) -> tuple[str, object]:
        return (lot.lot_id, lot.reconstruction_visee)

    def balayage(self, lot: LotAListe) -> Balayage | None:
        """Le balayage de ce lot **pour la passe retenue**, ou `None`.

        `None` signifie « pas encore compte », et c'est la seule chose qui fait
        tourner le rotor. Aucun repli optimiste : un verdict par defaut ferait
        afficher une pastille avant tout comptage, ce que
        `EPIC11-ARB-186` interdit en substance.
        """
        return self.balayages.get(self._cle(lot))

    @property
    def comptes(self) -> int:
        return sum(1 for lot in self.lots if self.balayage(lot) is not None)

    @property
    def balayage_fini(self) -> bool:
        return self.comptes >= len(self.lots)

    def prochain_a_balayer(self) -> LotAListe | None:
        """Le premier lot **dans l'ordre de la liste** qui n'est pas compte.

        L'ordre est celui de l'ecran : l'operateur voit les pastilles tomber de
        haut en bas, ce qui est le seul ordre qui se lise.
        """
        for lot in self.lots:
            if self.balayage(lot) is None:
                return lot
        return None

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> None:
        """`↑↓` : dans la liste, ou dans le champ des passes selon le focus."""
        if self.focus == FOCUS_VERSIONS:
            self.courant.deplacer_la_passe(pas)
            return
        self.curseur = min(max(self.curseur + pas, 0), len(self.lots) - 1)
        self._recadrer()

    def viser(self, lot_id: str) -> LotAListe:
        """Placer le curseur sur un lot **nomme**.

        Un `next()` nu remonterait en `StopIteration`, qui ne nomme ni le lot
        demande ni ceux qui existent.
        """
        rang = self.rang(lot_id)
        if rang is None:
            raise LotsMalFormes(
                f"Aucun lot ne s'appelle {lot_id!r} ; connus : "
                f"{[lot.lot_id for lot in self.lots]}.")
        self.curseur = rang
        self._recadrer()
        return self.lots[rang]

    def basculer_le_focus(self) -> bool:
        """`Tab` : la liste des lots, le champ des passes, et retour.

        Rend `False` -- donc **ne fait rien et le dit** -- quand le lot designe
        ne porte pas plusieurs passes : la ligne de raccourcis n'annonce alors
        pas `Tab`, et une touche qui bougerait quand meme contredirait ce
        qu'elle annonce.
        """
        if self.focus == FOCUS_VERSIONS:
            self.focus = FOCUS_LOTS
            return True
        if not self.courant.porte_des_passes:
            return False
        self.focus = FOCUS_VERSIONS
        return True

    def _recadrer(self) -> None:
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.lots), HAUTEUR_LISTE)

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        Le calcul vit dans `jetons`, comme pour les listes qui defilent deja :
        une redaction de plus divergerait a la premiere retouche.
        """
        return jetons.fenetre_de_liste(len(self.lots), self.premier_visible,
                                       HAUTEUR_LISTE)

    # -- ce que `⏎` rend -----------------------------------------------------

    def designer(self) -> Designation:
        """Le lot sous le curseur, avec la passe retenue.

        **Aucun refus n'est possible ici** : le lot vient de l'enumeration du
        coeur, donc il est admis, et la passe retenue par defaut est celle que
        le lot declare. Une passe designee a la main **peut**, elle, etre
        injoignable -- et c'est le balayage qui le dit, en ligne d'etat, avant
        que `⏎` ne soit frappe.
        """
        lot = self.courant
        return Designation(lot=lot.lot, dossier=lot.dossier,
                           reconstruction_visee=lot.reconstruction_visee,
                           balayage=self.balayage(lot))

    # -- le balayage ---------------------------------------------------------

    def balayer_le_prochain(self, balayeur: "Balayeur" = balayer_le_lot
                            ) -> bool:
        """Compter **un** lot de plus. Rend `False` quand il n'en reste aucun.

        Un lot par tour de rotor, et pas la liste entiere d'un coup : c'est ce
        qui rend le glyphe honnete -- il tourne pendant qu'un balayage a
        vraiment lieu -- et ce qui rend l'ecran mesurable pas a pas, sans
        horloge.
        """
        lot = self.prochain_a_balayer()
        if lot is None:
            return False
        self.balayages[self._cle(lot)] = balayeur(
            lot.lot, self.project_dir, self.manifeste,
            lot.reconstruction_visee)
        return True

    def avancer_le_rotor(self) -> None:
        """Un pas de plus. C'est **tout** ce qui bouge quand rien n'est compte."""
        self.pas += 1

    # -- rendu de la liste ---------------------------------------------------

    def colonne_de_droite(self, lot: LotAListe,
                          ascii_seul: bool = False) -> str:
        """`● complet`, `▲ 3 mires`, `✕ incomplet`, `✕ <code>` -- ou le rotor.

        **Le rotor tant que rien n'est compte** : c'est le glyphe de chargement
        d'`EPIC11-ARB-186`, lu de `jetons.rotor` et jamais dessine ici. Il ne
        porte aucune couleur d'etat, ce qui est exactement ce qu'on veut d'un
        verdict PAS ENCORE RENDU.
        """
        balayage = self.balayage(lot)
        if balayage is None:
            return (f"{jetons.rotor(self.pas, ascii_seul)} "
                    f"{_replie(MENTION_BALAYAGE, ascii_seul)}")
        if balayage.verdict is not None:
            return jeton_du_verdict(balayage.verdict, ascii_seul)
        # Le refus du coeur. Le masquer derriere « incomplet » dirait qu'il
        # manque une frame la ou c'est le dossier qui manque ; le NOM du refus
        # ne tient pas dans cette colonne et se lit sur la carte.
        return jetons.marque("absent", _replie(MENTION_REFUS, ascii_seul),
                             ascii_seul)

    def etat_de_la_ligne(self, lot: LotAListe) -> str | None:
        """Le nom d'etat qui teinte la ligne, ou `None` tant qu'elle attend.

        `None` est ce qui empeche une ligne pas encore comptee d'etre peinte :
        une couleur d'etat est un verdict, et il n'y en a pas encore.
        """
        balayage = self.balayage(lot)
        if balayage is None:
            return None
        if balayage.verdict is None:
            return "absent"
        return etat_du_verdict(balayage.verdict)

    def ligne(self, rang: int, utile: int = jetons.largeur_utile(),
              ascii_seul: bool = False) -> str:
        """Une ligne de lot, aux colonnes de `E4-1`.

        **Le nom s'abrege AU MILIEU** (`jetons.abreger_nom`), jamais par la fin
        : les lots de ce depot se distinguent par leur SUFFIXE --
        `plan-04_25` contre `plan-04_12p5` --, et une elision par la queue
        rendrait deux lots du meme rush indiscernables a l'ecran, c'est-a-dire
        le risque R12 remonte au niveau de l'affichage.

        **La colonne du nom vaut :data:`LARGEUR_DU_NOM`, le nom vaut deux
        colonnes de moins** : la maquette pose la pastille immediatement apres
        un champ de nom de la longueur maximale du produit, si bien qu'un lot
        nomme sur exactement `CANONICAL_ID_MAX_LENGTH` caracteres y collerait
        son `● complet`. Le creux est pris sur le nom plutot que sur la
        colonne, ce qui garde les colonnes de la maquette au caractere pres.
        """
        table = jetons.glyphes(ascii_seul)
        lot = self.lots[rang]
        vise = rang == self.curseur and self.focus == FOCUS_LOTS
        tete = " " * (_INDENT - 2) + (table["curseur"] if vise else " ") + " "
        nom = jetons.abreger_nom(lot.lot_id,
                                 LARGEUR_DU_NOM - jetons.CREUX_MINIMAL,
                                 ascii_seul)
        gauche = tete + _a_gauche(nom, LARGEUR_DU_NOM, ascii_seul)
        place = utile - _MARGE_DROITE - jetons.colonnes(gauche)
        return (gauche + jetons.ajuster(
            self.colonne_de_droite(lot, ascii_seul), place,
            ascii_seul)).rstrip()

    def lignes_de_liste(self, utile: int = jetons.largeur_utile(),
                        ascii_seul: bool = False) -> list[str]:
        """Les :data:`HAUTEUR_LISTE` lignes de la zone, `…` compris.

        La zone est **completee par des lignes vides** quand les lots sont
        moins nombreux qu'elle : c'est ce qui tient le filet de la carte a la
        meme ligne d'un projet a l'autre.
        """
        total = len(self.lots)
        premier, dernier = self.fenetre()
        points = jetons.points_d_abregement(ascii_seul)
        rendues: list[str] = []
        if premier > 0:
            rendues.append(" " * _INDENT + points)
        for rang in range(premier, dernier + 1):
            rendues.append(self.ligne(rang, utile, ascii_seul))
        if dernier < total - 1:
            position = f"{premier + 1}-{dernier + 1} sur {total} lots"
            tete = " " * _INDENT + points
            creux = utile - _MARGE_DROITE - len(tete) - jetons.colonnes(position)
            rendues.append(tete + " " * max(jetons.CREUX_MINIMAL, creux)
                           + position)
        return rendues + [""] * (HAUTEUR_LISTE - len(rendues))

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans :meth:`lignes_de_liste`, de la ligne a accentuer.

        **Passe explicitement a `jetons.peindre`, jamais devine** : ces lignes
        sont indentees, et l'auto-detection teste `startswith` sur le glyphe de
        curseur -- elle ne trouverait rien, en silence. `None` quand le focus
        est sur le champ des passes : le curseur est ailleurs.
        """
        if self.focus != FOCUS_LOTS:
            return None
        premier, dernier = self.fenetre()
        if not premier <= self.curseur <= dernier:
            return None
        return (1 if premier > 0 else 0) + (self.curseur - premier)

    def etats_des_lignes(self) -> dict[int, str]:
        """L'etat de **chaque ligne comptee**, par rang dans la zone de liste.

        Une ligne pas encore comptee n'y figure pas : elle n'a pas d'etat, donc
        pas de couleur. C'est la moitie visuelle de « aucun verdict avant le
        comptage ».
        """
        premier, dernier = self.fenetre()
        decalage = 1 if premier > 0 else 0
        etats: dict[int, str] = {}
        for rang in range(premier, dernier + 1):
            nom = self.etat_de_la_ligne(self.lots[rang])
            if nom is not None:
                etats[decalage + (rang - premier)] = nom
        return etats

    # -- rendu de la carte ---------------------------------------------------

    def lignes_des_passes(self, ascii_seul: bool = False) -> list[str]:
        """Le champ exclusif des reconstructions, ou rien.

        **L'ordre est celui du manifest** (`encode.enumerer_les_reconstructions`
        ne trie jamais), et ce module ne le retrie pas : `lots[].reconstructions`
        est chronologique et porte l'information « quelle passe a suivi
        laquelle », que le tri detruirait.

        **Les deux glyphes ou un seul** (`EPIC11-ARB-180`) : la fleche dit ou
        est le curseur, la puce ce qui est retenu -- et la fleche n'apparait
        que quand ce champ **a le focus**. C'est un champ de formulaire, pas
        une liste d'issues : `EPIC11-ARB-126` (« Flèche seule ! ») ne le
        regit pas.
        """
        lot = self.courant
        if not lot.porte_des_passes:
            return []
        table = jetons.glyphes(ascii_seul)
        lignes = []
        for rang, passe in enumerate(lot.passes):
            retenue = rang == lot.passe
            vise = retenue and self.focus == FOCUS_VERSIONS
            tete = ((table["curseur"] if vise else " ") + " "
                    + table["exclusif-retenu" if retenue
                            else "exclusif-libre"] + " ")
            libelle = LIBELLE_RECONSTRUCTION if rang == 0 else ""
            lignes.append(
                " " * _INDENT
                + _a_gauche(_replie(libelle, ascii_seul), _LARGEUR_DU_LIBELLE - 2,
                            ascii_seul)
                + tete + self._detail_de_la_passe(passe, ascii_seul))
        return [ligne.rstrip() for ligne in lignes]

    def _detail_de_la_passe(self, passe: encode.ReconstructionDeLot,
                            ascii_seul: bool = False) -> str:
        """`v2  scan-2026-08-31_v2`, ou ce qui manque a cette passe.

        **Ce que la maquette dessine et que le produit NE PORTE PAS** : elle
        ecrit `v2  02/09 · 8 planches · 124 frames`. Aucun de ces trois faits
        n'existe au manifest -- une entree de `lots[].reconstructions` porte
        `ingest_slug`, `output_frames_dir`, `origin` et `status`, et **aucune
        horodate**, deliberement (l'idempotence octet a octet du document
        l'interdit). Ce qui est affiche est donc l'identite durable de la
        passe, la seule chose vraie ; l'ecart est **signale** plutot que
        comble par une valeur inventee.
        """
        rang = (RANG_INCONNU if passe.rang is None
                else PREFIXE_DE_RANG.format(rang=passe.rang))
        if not passe.output_frames_dir:
            reste = _replie(MENTION_PASSE_SANS_DOSSIER, ascii_seul)
        elif not passe.presente:
            reste = jetons.marque(
                "absent", _replie(MENTION_PASSE_ABSENTE, ascii_seul),
                ascii_seul)
        else:
            reste = _replie(passe.ingest_slug, ascii_seul)
        return f"{_a_gauche(rang, 4, ascii_seul)}{reste}".rstrip()

    def etats_des_passes(self) -> dict[int, str]:
        """L'etat des lignes de passes, pour la peinture. Seules les absentes
        en portent un : une passe presente n'est ni un avertissement ni un
        refus, c'est le cas nominal."""
        lot = self.courant
        if not lot.porte_des_passes:
            return {}
        return {rang: "absent" for rang, passe in enumerate(lot.passes)
                if passe.output_frames_dir and not passe.presente}

    def ligne_des_frames(self, ascii_seul: bool = False) -> str:
        """`Frames retenues   124 sur 124 attendues     ● complet`.

        **Une seule ligne, mires comprises** : c'est la correction de forme
        qu'Egan a demandee (« `Mires` est redondant avec `frames` : si c'est
        complet on n'a pas de mires, si c'est incomplet on a des mires.
        Lecture sur la meme ligne »). Le mot `mires` reste -- il est dans le
        jeton d'etat -- mais il ne double plus une ligne de frames.
        """
        balayage = self.balayage(self.courant)
        if balayage is None:
            valeur, jeton = _replie(MOTIF_DES_FRAMES_EN_BALAYAGE, ascii_seul), ""
        elif balayage.verdict is None:
            # **Le code du refus prend la colonne des VALEURS, pas celle des
            # pastilles** : `DOSSIER_DE_LOT_ABSENT` posé en colonne 58 sortirait
            # de la fenetre de cinq colonnes. Il tient a partir de la colonne
            # 32, ou il est de toute facon plus lisible -- c'est la valeur de
            # cette ligne, pas son verdict.
            valeur = jetons.marque("absent", str(balayage.refus or ""),
                                   ascii_seul)
            jeton = ""
        else:
            verdict = balayage.verdict
            motif = (MOTIF_DES_FRAMES if verdict.expected is not None
                     else MOTIF_DES_FRAMES_SANS_REFERENCE)
            valeur = _replie(motif.format(trouvees=verdict.found,
                                          attendues=verdict.expected),
                             ascii_seul)
            jeton = jeton_du_verdict(verdict, ascii_seul)
        return (" " * _INDENT
                + _a_gauche(_replie(LIBELLE_FRAMES, ascii_seul),
                            _LARGEUR_DU_LIBELLE, ascii_seul)
                + _a_gauche(valeur, _LARGEUR_DES_FRAMES, ascii_seul)
                + jeton).rstrip()

    def ligne_de_la_cadence(self, ascii_seul: bool = False) -> str:
        """`Cadence du rushe source   25 fps        lue au manifest` (AC 5.3).

        La valeur vient d'`encode.resolve_source_rate`, **la seule redaction du
        depot** de « quelle cadence mux le master ». Son refus nomme
        `ENCODE_SOURCE_RATE_MISSING` est traite comme un **etat de la carte** :
        le champ dit que le lot n'en declare aucune, et l'ecran des reglages
        est l'endroit d'ou la declaration peut venir.

        **Tout autre refus remonte** : une cadence presente mais inexploitable
        n'est pas une cadence absente, et l'avaler ici ferait dire « le lot
        n'en declare aucune » d'un lot qui en declare une, fausse. Deux etats
        differents, deux traitements -- meme geste que
        `atelier_exports_reglages.cadence_source_du_lot`.
        """
        try:
            _brute, exacte, _note = encode.resolve_source_rate(self.courant.lot)
        except encode.EncodeDecisionError as refus:
            if refus.code != encode.ENCODE_SOURCE_RATE_MISSING:
                raise
            valeur, mention = "", MENTION_CADENCE_ABSENTE
        else:
            valeur = MOTIF_DE_LA_CADENCE.format(
                cadence=_cadence_lisible(exacte))
            mention = MENTION_PROVENANCE_DE_LA_CADENCE
        return (" " * _INDENT
                + _a_gauche(_replie(LIBELLE_CADENCE, ascii_seul),
                            _LARGEUR_DU_LIBELLE, ascii_seul)
                + _a_gauche(_replie(valeur, ascii_seul),
                            _LARGEUR_DE_LA_CADENCE, ascii_seul)
                + _replie(mention, ascii_seul)).rstrip()

    def ligne_de_la_geometrie(self, ascii_seul: bool = False) -> str:
        """`Géométrie · bits   1920×1080 · 16 bits`, ou ce qu'on en sait.

        Deux sources, deux absences possibles, et **aucune valeur inventee** :
        la geometrie est `rushes[].resolution_source` du rush de ce lot, la
        profondeur `lots[].output_bit_depth`. Les deux sont ecrites par
        l'extraction ; un manifest reconstruit depuis le scan seul n'en porte
        aucune, « ce qui est une propriete attendue, pas un defaut ». La ligne
        entiere disparait alors -- une ligne vide dirait moins que rien.
        """
        segments = []
        geometrie = _resolution_du_rush(self.manifeste, self.courant.lot)
        if geometrie is not None:
            segments.append(MOTIF_DE_LA_GEOMETRIE.format(
                largeur=geometrie[0], hauteur=geometrie[1]))
        profondeur = _entier(self.courant.lot.get("output_bit_depth"))
        if profondeur is not None:
            segments.append(MOTIF_DES_BITS.format(profondeur=profondeur))
        if not segments:
            return ""
        return (" " * _INDENT
                + _a_gauche(_replie(LIBELLE_GEOMETRIE, ascii_seul),
                            _LARGEUR_DU_LIBELLE, ascii_seul)
                + _replie(SEPARATEUR.join(segments), ascii_seul)).rstrip()

    def lignes_de_la_carte(self, ascii_seul: bool = False) -> list[str]:
        """Les lignes du bloc « Le lot désigné », dans l'ordre de la maquette."""
        lignes = list(self.lignes_des_passes(ascii_seul))
        lignes.append(self.ligne_des_frames(ascii_seul))
        lignes.append(self.ligne_de_la_cadence(ascii_seul))
        geometrie = self.ligne_de_la_geometrie(ascii_seul)
        if geometrie:
            lignes.append(geometrie)
        return lignes

    def etats_de_la_carte(self) -> dict[int, str]:
        """Les etats des lignes de la carte, en rangs RELATIFS a ce bloc."""
        return dict(self.etats_des_passes())

    # -- la ligne d'etat et les raccourcis ------------------------------------

    def raccourcis(self) -> str:
        """La ligne contextuelle. `Tab` n'est annonce que s'il mene quelque part."""
        if self.focus == FOCUS_VERSIONS:
            return RACCOURCIS_RECONSTRUCTIONS
        if self.courant.porte_des_passes:
            return RACCOURCIS_LOTS
        return RACCOURCIS_LOTS_SANS_PASSES

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        """`2 lots comptés sur 5 · plan-04_25 : 124 frames sur 124, 2 …`.

        **Une mesure, et rien d'autre** (`EPIC11-ARB-56`, AC 5.5) : aucune
        touche, aucun conseil d'usage, aucun motif de conception. Le segment de
        frames n'apparait **qu'une fois le lot designe compte** -- afficher un
        cardinal avant de l'avoir mesure serait le verdict optimiste que le
        rotor existe pour eviter.
        """
        comptes = self.comptes
        motif = (MOTIF_DU_BALAYAGE_FINI if self.balayage_fini
                 else MOTIF_DU_BALAYAGE)
        tete = _replie(motif.format(comptes=accorder(comptes, "lot"),
                                    accord="s" if comptes > 1 else "",
                                    total=len(self.lots))
                       + SEPARATEUR, ascii_seul)
        # **Le repli precede la mesure**, et ce n'est pas un detail d'ordre :
        # `…` occupe une colonne et `...` en occupe trois. Un abregement decide
        # avant le repli ferait deborder la ligne de deux colonnes en
        # `--ascii`, et de la seule ligne que l'operateur lit quand il ne sait
        # plus ou il en est. C'est la regression payee sur le bandeau le
        # 2026-08-28.
        place = max(0, jetons.largeur_utile() - jetons.colonnes(tete))
        return tete + self._etat_du_lot_designe(place, ascii_seul)

    def _etat_du_lot_designe(self, place: int = jetons.largeur_utile(),
                             ascii_seul: bool = False) -> str:
        """`plan-04_25 : 124 frames sur 124, 2 reconstructions`.

        **Le nom du lot cede la place aux mesures, jamais l'inverse** : un
        identifiant de la longueur maximale du produit ferait deborder la ligne
        de huit colonnes, et c'est la mesure -- la seule chose que
        `EPIC11-ARB-56` exige d'une ligne d'etat -- qui partirait la premiere.
        Il s'abrege donc AU MILIEU (`jetons.abreger_nom`), comme dans la liste,
        parce que les lots de ce depot se distinguent par leur suffixe.
        """
        lot = self.courant
        queue = ""
        balayage = self.balayage(lot)
        if balayage is not None and balayage.verdict is not None:
            verdict = balayage.verdict
            motif = (MOTIF_DE_L_ETAT_DU_LOT if verdict.expected is not None
                     else MOTIF_DE_L_ETAT_DU_LOT_SANS_REFERENCE)
            queue += SEPARATEUR_DU_LOT + motif.format(
                trouvees=verdict.found, attendues=verdict.expected)
        elif balayage is not None:
            queue += SEPARATEUR_DU_LOT + str(balayage.refus or "")
        if lot.porte_des_passes:
            cardinal = len(lot.passes)
            queue += SEPARATEUR_DES_PASSES + MOTIF_DES_PASSES.format(
                cardinal=cardinal, accord="s" if cardinal > 1 else "")
        queue = _replie(queue, ascii_seul)
        return jetons.abreger_nom(
            lot.lot_id, max(0, place - jetons.colonnes(queue)),
            ascii_seul) + queue


#: Ce qu'un balayeur doit savoir faire. Il est **injectable** pour que le banc
#: mesure les deux etats de l'ecran sans toucher un disque ; son defaut est le
#: vrai balayage, jamais `None` -- « c'est le double qui est l'exception, pas
#: le defaut ».
Balayeur = Callable[[Mapping[str, Any], Path, Mapping[str, Any], object],
                    Balayage]


def _cadence_lisible(exacte: str) -> str:
    """`25/1` -> `25`, `24000/1001` -> `24000/1001`.

    La cadence exacte du coeur s'ecrit en fraction ; celle dont le
    denominateur vaut 1 se lit mieux en entier, et c'est ce que la maquette
    montre. Aucune autre reecriture : une cadence NTSC n'a pas d'ecriture
    decimale finie, et l'arrondir ici ferait afficher une valeur que le coeur
    ne connait pas.
    """
    numerateur, _, denominateur = str(exacte).partition("/")
    return numerateur if denominateur == "1" else str(exacte)


def _entier(valeur: object) -> int | None:
    """Un entier strict, ou `None`. **Le `bool` est exclu avant tout**.

    `True` est un `int` en Python : un `"output_bit_depth": true` dans un
    document abime rendrait « 1 bits », une valeur plausible donc invisible,
    ce qui est le pire des cas.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return None
    return valeur if valeur > 0 else None


def _resolution_du_rush(manifeste: Mapping[str, Any],
                        lot: Mapping[str, Any]) -> tuple[int, int] | None:
    """`(largeur, hauteur)` du rush **de ce lot**, ou `None`.

    L'appariement se fait **par `rush_id`**, jamais par rang : « deux listes
    qui doivent rester en correspondance sont deux occasions de les
    desapparier », et un `rushes[0]` serait juste tant qu'un seul rush existe
    -- c'est-a-dire jusqu'au premier projet a deux rushes, ou l'ecran
    afficherait la geometrie de l'autre.
    """
    rush_id = lot.get("rush_id")
    if not rush_id:
        return None
    rushes = manifeste.get("rushes")
    if not isinstance(rushes, Sequence) or isinstance(rushes, (str, bytes)):
        return None
    for rush in rushes:
        if not isinstance(rush, Mapping) or rush.get("rush_id") != rush_id:
            continue
        resolution = rush.get("resolution_source")
        if not isinstance(resolution, Mapping):
            return None
        largeur = _entier(resolution.get("width"))
        hauteur = _entier(resolution.get("height"))
        if largeur is None or hauteur is None:
            return None
        return (largeur, hauteur)
    return None


# ---------------------------------------------------------------------------
# `E4-1` -- l'ecran
# ---------------------------------------------------------------------------

#: La periode du rotor, en secondes. Quatre dessins : le cycle complet dure
#: quatre fois cette valeur. C'est celle des deux ecrans qui portent deja un
#: rotor -- une troisieme valeur ferait deux vitesses d'attente dans le meme
#: produit.
PERIODE_DU_ROTOR = 0.25


class EcranDesLotsAEncoder(ObjetTravaille, Palier):
    """`E4-1` -- quel lot encoder.

    L'ecran ne compte rien, ne nomme rien et ne juge rien : il branche le
    modele pur ci-dessus sur le clavier, sur le minuteur qui fait tourner le
    rotor et avancer le balayage, et sur la seule issue de l'ecran,
    `⏎ choisir`. **Il n'importe jamais `cli.py`** (`EPIC11-ARB-67`).
    """

    titre = projet_lecture.EXPORTS
    #: La ligne d'ouverture. Elle est **reassignee a chaque dessin** par
    #: :meth:`poser_les_raccourcis`, l'idiome du depot pour une ligne
    #: contextuelle. Une `property` aurait fait la meme chose et **casse le
    #: balayage du paquet** : `test_majuscules_des_raccourcis` lit cet attribut
    #: de CLASSE et attend une chaine.
    raccourcis = RACCOURCIS_LOTS
    #: Une station du parcours, pas un passage : on revient dessus depuis les
    #: reglages, et `Échap` ramene au menu des ateliers.
    TRANSITOIRE = False
    ID_DU_CORPS = "corps-lots-exports"

    def __init__(self, liste: ListeDesLotsAEncoder,
                 balayeur: Balayeur = balayer_le_lot,
                 continuer: Callable[[Designation], None] | None = None
                 ) -> None:
        super().__init__()
        self.liste = liste
        #: **Pas un `Callable | None`** : le defaut est le vrai balayage du
        #: disque, et un banc qui veut mesurer les deux etats de l'ecran passe
        #: le sien. C'est le double qui est l'exception.
        self.balayeur = balayeur
        self._continuer = continuer
        #: Le minuteur, **retenu** et non oublie : un minuteur qu'on ne tient
        #: pas continue d'ecrire dans un arbre de widgets detruit, et un banc
        #: qui ne peut pas le figer mesure l'horloge au lieu du produit.
        self.minuteur = None

    # -- lecture --------------------------------------------------------------

    def poser_les_raccourcis(self) -> str:
        self.raccourcis = self.liste.raccourcis()
        return self.raccourcis

    def composer(self, largeur: int, ascii_seul: bool = False
                 ) -> tuple[list[str], int | None, dict[int, str]]:
        """Le corps de `E4-1`, **sous la hauteur de la zone centrale**.

        Les respirations sont sacrifiables et tombent de haut en bas : c'est le
        budget de `Composition`, qui existe parce que `textual` coupe par le
        bas, en silence.
        """
        utile = jetons.largeur_utile(largeur)
        composition = Composition()
        composition.respirer()
        composition.poser(ligne_de_titre(TITRE_DES_LOTS, ascii_seul))
        composition.respirer()
        composition.bloc(self.liste.lignes_de_liste(utile, ascii_seul),
                         etats=self.liste.etats_des_lignes(),
                         curseur=self.liste.rang_du_curseur())
        composition.respirer()
        composition.poser(filet_titre(FILET_DU_LOT, utile, ascii_seul))
        composition.respirer()
        composition.bloc(self.liste.lignes_de_la_carte(ascii_seul),
                         etats=self.liste.etats_de_la_carte())
        return composition.rendu()

    def lignes(self) -> list[str]:
        return self.composer(self.app.size.width, self.app.ascii_seul)[0]

    def etat(self) -> str:
        return self.liste.ligne_d_etat(self.app.ascii_seul)

    def objet_du_bandeau(self) -> str:
        """`E4-1` porte un bandeau NU : on n'y travaille pas encore un lot en
        particulier, on choisit lequel. C'est ce que la maquette montre."""
        return ""

    # -- le balayage et le rotor ---------------------------------------------

    def tourner(self) -> None:
        """Un pas de rotor, **un** lot balaye, et on redessine.

        Appelee par un intervalle `textual` monte dans :meth:`on_mount`, et
        appelable a la main : c'est ce qui rend les deux etats de l'ecran
        mesurables sans terminal et sans horloge.

        Le minuteur s'arrete de lui-meme quand tout est compte : un rotor qui
        continuerait de tourner sur un ecran fini dirait qu'il travaille encore.
        """
        self.liste.avancer_le_rotor()
        self.liste.balayer_le_prochain(self.balayeur)
        if self.liste.balayage_fini and self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None
        self.rafraichir()

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
        self.minuteur = self.set_interval(PERIODE_DU_ROTOR, self.tourner)
        self.rafraichir()

    def on_unmount(self) -> None:
        """Arreter le minuteur. Un ecran demonte n'a plus rien a faire tourner."""
        if self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None

    # -- clavier --------------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        if touche in ("up", "down"):
            self.liste.deplacer(-1 if touche == "up" else 1)
            return True
        if touche in ("tab", "shift+tab"):
            return self.liste.basculer_le_focus()
        if touche == "enter":
            designation = self.liste.designer()
            if self._continuer is not None:
                self._continuer(designation)
            else:
                self._pas_encore()
            return True
        return False

    def _pas_encore(self) -> None:
        """`⏎` sans appelant : on le DIT plutot que de rendre la touche muette.

        **En production, cette branche n'est plus atteinte depuis le lot B5**
        (2026-09-03) : `ParcoursExports.ouvrir` injecte `continuer=`, et `⏎`
        monte `E4-2`. Elle reste parce qu'un banc construit cet ecran **a nu**,
        et qu'un `if ... is not None` sans branche `else` rendrait alors la
        touche indistinguable d'un clavier casse -- c'est litteralement le
        finding `K1.1a`, et la garde structurelle des rappels existe pour
        l'attraper.
        """
        application = _application_montee(self)
        if application is None:
            # Un ecran construit a nu par un banc n'a pas d'application ou
            # descendre : il n'y a rien a montrer, et rien a taire non plus.
            return
        application.descendre(EcranPasEncore(CE_QUI_MANQUE_APRES_LE_LOT,
                                             QUAND_LES_REGLAGES))


__all__ = [
    "Balayage",
    "Balayeur",
    "CE_QUI_MANQUE_APRES_LE_LOT",
    "Designation",
    "EcranDesLotsAEncoder",
    "FILET_DU_LOT",
    "FOCUS_LOTS",
    "FOCUS_VERSIONS",
    "HAUTEUR_LISTE",
    "LARGEUR_DU_NOM",
    "LIBELLE_FRAMES",
    "LIBELLE_GEOMETRIE",
    "LIBELLE_RECONSTRUCTION",
    "ListeDesLotsAEncoder",
    "LotAListe",
    "LotsMalFormes",
    "MENTION_BALAYAGE",
    "MENTION_CADENCE_ABSENTE",
    "MENTION_COMPLET",
    "MENTION_INCOMPLET",
    "MENTION_MIRES",
    "MENTION_PASSE_ABSENTE",
    "MENTION_PASSE_SANS_DOSSIER",
    "MENTION_PROVENANCE_DE_LA_CADENCE",
    "MENTION_REFUS",
    "PERIODE_DU_ROTOR",
    "QUAND_LES_REGLAGES",
    "RACCOURCIS_LOTS",
    "RACCOURCIS_LOTS_SANS_PASSES",
    "RACCOURCIS_RECONSTRUCTIONS",
    "TITRE_DES_LOTS",
    "balayer_le_lot",
    "etat_du_verdict",
    "jeton_du_verdict",
]
