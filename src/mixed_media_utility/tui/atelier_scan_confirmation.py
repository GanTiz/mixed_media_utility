# -*- coding: utf-8 -*-
"""`E3-6` -- la confirmation du temps 2 du Scan (story 11.6, lot D, AC 4).

**C'est le point de jugement de l'ecriture des frames**, et rien n'y est encore
ecrit. `EPIC11-ARB-4`, verbatim : le panneau chiffre « est **obligatoire pour
toute commande qui ecrit**, et il porte au minimum : ce qui sera produit (noms
de fichiers ou de lots), en quelle quantite (frames, pages), et ce que cela
coute (espace disque, majorant assume comme tel) ».

**Aucun ecran neuf n'est ecrit ici.** `E3-6` **est** un
:class:`~mixed_media_utility.tui.execution.EcranChiffre` (AC 4.1) : le
cartouche, le `ChoixExclusif` et la navigation y sont deja, livres par la story
11.1 et mesures par elle. Ce module **alimente** cet ecran.

**Il n'y a plus de nom editable ici** (`EPIC11-ARB-141`, story 11.4e lot G). Le
mode d'edition de la classe de base -- `Tab`, `Ctrl+R`, le compteur vivant --
existe encore dans `execution.py`, mais cet ecran ne lui donne **aucun** nom :
`EcranChiffre` pose un modele vide, `Tab` n'a donc aucune destination et
`traiter` le rend inerte de lui-meme. Ce n'est pas une garde ajoutee ici, c'est
la consequence de ne pas donner de noms editables.

**Aucun chiffre n'est rederive.** Les deux lignes de frames sont celles que
`atelier_scan_rapport.PanneauDeLot` porte deja (`frames`, `frames_attendues`,
AC 4.2), le majorant d'espace disque passe par
`atelier_extraction_ecriture.octets_par_frame` (AC 4.7), la profondeur est lue
de `constants.OUTPUT_BIT_DEPTH`, et la limite d'un nom est `noms.LIMITE`,
c'est-a-dire **identiquement** `io.naming.CANONICAL_ID_MAX_LENGTH` (AC 4.6).
Aucun nombre de caracteres n'est ecrit dans ce module, et une frontiere du banc
le mesure a zero.

**Les deux listes que ce module parcourt sont les lots et les zones de
decoupe.** L'ordre des lots est celui du rapport -- lui-meme celui des
documents recus, c'est-a-dire celui du tri du coeur -- et il n'est **jamais**
retrie ici : c'est ce qui permet a un banc de verifier le rang d'une cible sur
la liste que ce code parcourt, et non sur celle que sa fabrique croit ecrire
(`CLAUDE.md`, points 2 et 2 bis).

**Le slug MONTRE est apparie par `lot_id`, jamais par rang.** Un appariement
positionnel entre les lots du rapport et les slugs lus des documents montrerait
le nom d'un lot sur un autre : c'est le mutant `M25` de la story 5.7, ou 257
tests restaient verts pendant que les cardinaux du scan etaient ecrits sur le
mauvais lot -- litteralement le risque `R12`. L'appariement est fait une fois,
par :func:`slugs_par_lot`, et le plan le porte.

Ce que ce module ne fait pas, et c'est structurel
-------------------------------------------------
* il **n'ecrit aucune frame** et ne touche a aucun fichier : c'est un point de
  jugement, et rien n'y est ecrit ;
* il **ne lit aucun document sur le disque** : il recoit des
  :class:`~mixed_media_utility.scan_previz.ScanPreviz` **deja relus**, comme
  `atelier_scan_rapport` (AC 2.8 -- la TUI ne redige aucune troisieme lecture
  de document) ;
* il **n'importe jamais `cli`** (`EPIC11-ARB-67`) ;
* il **ne se cable pas lui-meme** : le cablage `E3-5` -> `E3-6` -> `E3-7` est
  le lot H de cette story.

Un ecart MESURE, et TRANCHE depuis (`EPIC11-ARB-141`)
-----------------------------------------------------
`scan_write.ecrire_depuis_le_document` **n'a aucun argument de slug d'ingest**
ni de nom de lot : le dossier de sortie se derive du QR
(`scan_output_frames.derive_lot_dir_slug`), et le slug d'ingest est fige depuis
le temps 1. Un nom edite ici n'atteignait donc pas le coeur -- comme un nom
edite de `E2-3` n'atteignait pas `run_extraction`.

Egan a tranche le 2026-09-01, verbatim : « On retire l'edition des noms PARTOUT
ou elle ne peut pas etre effective. On la laisse uniquement la ou on sait la
cabler. » L'edition **est donc retiree**, ici comme cote Extraction, et
`EPIC11-ARB-8` (« pre-rempli, et toujours editable ») en est **borne** plutot
que contredit : l'operateur disposera la ou le coeur sait recevoir.

Le retrait ne se relit pas, il se mesure :
`tests/unit/tui/test_aucun_nom_editable.py` tient l'implication -- aucun mot-cle
de nom au point d'entree de coeur, donc aucun champ a l'ecran -- et **rougit le
jour ou le coeur gagnera le parametre**, ce qui force la reprise du champ plutot
que son oubli. La capacite de renommer est portee a `deferred-work.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..constants import OUTPUT_BIT_DEPTH
from . import jetons
from .atelier_extraction_ecriture import (
    INDENT_DES_NOMS,
    LIBELLE_ESPACE,
    PREFIXE_APPROCHE,
    TITRE_A_ECRIRE,
    octets_par_frame,
    taille_lisible,
)
from .atelier_scan_rapport import RapportDeDetection
from .execution import EcranChiffre, bloc_peint
from .panneau import RIEN_ECRIT, ChoixExclusif, Issue, LigneChiffree, Panneau

# ---------------------------------------------------------------------------
# Textes d'ecran. En constantes, comme partout dans le paquet : un texte ecrit
# deux fois divergerait, et les frontieres negatives les balayent.
# ---------------------------------------------------------------------------

#: Les libelles des lignes du cartouche, verbatim de la maquette `E3-6`. Ils
#: nomment ce qu'ils comptent.
#:
#: `LIBELLE_ESPACE` n'est **pas** redige ici : il est importe de
#: `atelier_extraction_ecriture`, ou il vit deja. Deux confirmations qui
#: nommeraient differemment la meme ligne feraient lire deux couts a
#: l'operateur.
LIBELLE_LOTS = "Lots écrits"
LIBELLE_FRAMES_ATTENDUES = "Frames attendues"
LIBELLE_FRAMES_OBTENUES = "Frames obtenues"
LIBELLE_PROFONDEUR = "Profondeur"
LIBELLE_CALIBRATION = "Calibration"

#: L'unite de la profondeur. Le chiffre, lui, vient de
#: `constants.OUTPUT_BIT_DEPTH` : `LigneChiffree` refuse a la construction un
#: nombre sans unite, et un `16` ecrit ici serait une seconde redaction de la
#: profondeur de sortie du depot.
UNITE_PROFONDEUR = "bits"

#: L'unite des deux lignes de frames.
UNITE_FRAMES = "frames"

#: Ce que la ligne « Frames attendues » dit quand le manifest ne les declare
#: pas (AC 4.2). Elle le **dit** plutot que de replier les obtenues sur les
#: attendues : deux fois le meme chiffre se lirait comme une egalite mesuree,
#: c'est-a-dire l'inverse de ce qui est su.
#:
#: `atelier_scan_rapport._frames_attendues` est la seule derivation de cet
#: attendu dans la TUI, et elle rend `None` des que le manifest ne porte pas le
#: lot : ce texte est le rendu de ce `None`, jamais une seconde regle.
FRAMES_ATTENDUES_INCONNUES = "non déclaré par le manifest"

#: Ce que la ligne « Calibration » dit quand l'operateur a retenu « aucune » --
#: le lot est livre **brut** (`livrer_brut=True`, AC 3.3). C'est un fait sur ce
#: qui sera ecrit, jamais un manque.
CALIBRATION_AUCUNE = "aucune — lot livré brut"

#: Ce que la ligne d'espace disque dit quand une dimension de decoupe manque.
#: Elle ne porte alors **pas** la mention `(majorant)` : `(majorant)` sur
#: « inconnu » laisserait croire qu'un chiffre a ete calcule. Meme redaction
#: que `atelier_extraction_ecriture._ligne_de_l_espace`, et meme motif -- « une
#: ligne d'espace disque fausse est pire qu'une ligne d'espace disque absente ».
ESPACE_INCONNU = "inconnu — dimensions de découpe non portées par le document"

#: Ce que la ligne « Frames obtenues » ajoute quand les deux comptes coincident,
#: verbatim de la maquette `E3-6` (`● toutes`). Le glyphe est pose par
#: :func:`jetons.marque`, jamais dessine ici.
MENTION_TOUTES = "toutes"

#: Les deux redactions du desaccord (AC 4.3). Le manque est **dit**, chiffre :
#: « attendues != obtenues » sans le compte du manque laisserait l'operateur
#: soustraire lui-meme deux nombres cales a des colonnes differentes.
GABARIT_MANQUE = "{compte} manquante{s}"
GABARIT_EN_TROP = "{compte} en trop"

#: Les cles des issues de `E3-6`. Elles ne sont **jamais** affichees : le
#: libelle l'est. Une cle est ce par quoi un test et un ecran se designent la
#: meme issue sans recopier une chaine francaise.
ISSUE_ECRIRE = "ecrire"
ISSUE_MODIFIER = "modifier"
ISSUE_ANNULER = "annuler"

#: La **seconde issue d'`EPIC11-ARB-89`**, cablee ici par `EPIC11-ARB-133`.
#:
#: Le fait qui l'a fait naitre, mesure par la revue de la vague 4 :
#: `nouvelle_version=` existait au coeur, etait relaye jusqu'a
#: `atelier_scan_ecriture.LotAEcrire` et jusqu'a
#: `scan_write.ecrire_depuis_le_document`, et **aucun chemin de TUI ne le
#: posait jamais a `True`**. Un lot deja ecrit ne recevait donc, depuis
#: l'interface, qu'un `EcranRefus` -- c'est-a-dire le blocage sec
#: qu'`EPIC11-ARB-89` interdit nommement (« toujours permettre une reecriture
#: plutot qu'un blocage sec »).
ISSUE_NOUVELLE_VERSION = "nouvelle-version"

#: Les trois libelles, verbatim de la maquette `E3-6` (l. 17 a 19).
LIBELLE_ECRIRE = "Écrire les TIFF"
LIBELLE_MODIFIER = "Modifier"
LIBELLE_ANNULER = "Annuler"

#: Le libelle de l'issue de versionnage. Il nomme ce qui sera ecrit -- **un jeu
#: VOISIN** -- et ce qui ne le sera pas : l'existant. Le mot « version » est
#: celui d'`EPIC11-ARB-104` (« Tout doit etre versionnable OU ecrase ») ; le
#: **rang** n'est pas annonce ici, et c'est delibere : il se resout au coeur
#: (`scan_output_frames`, qui appelle `io.version_ranks`), et l'annoncer avant
#: l'appel serait une seconde regle de rang en TUI -- exactement ce
#: qu'`EPIC11-ARB-108` interdit (« il n'y a pas de mecanisme different par
#: objet »). Le nom de la fonction de resolution n'est pas ecrit ici non plus :
#: la frontiere negative du versionnage balaye ce paquet **prose comprise**,
#: et une reference citee est la premiere chose qu'une relecture prend pour la
#: reference.
LIBELLE_NOUVELLE_VERSION = "Écrire une nouvelle version, sans toucher à l'existant"

#: Le libelle de la ligne de cartouche qui **explique** la quatrieme issue. Sans
#: elle, une issue apparaitrait sur un ecran sans qu'aucun chiffre ne dise
#: pourquoi -- et `EPIC11-ARB-4` veut qu'un panneau chiffre dise ce qui sera
#: produit ET ce que cela coute.
LIBELLE_DEJA_ECRITES = "Déjà sur le disque"

#: Le libelle que la premiere issue prend quand les comptes ne coincident pas
#: (AC 4.3) : **le compte reel**, jamais le compte attendu. Ecrire « les 186
#: frames » sur un lot qui n'en a que 183 serait promettre trois frames que le
#: document ne porte pas.
GABARIT_ECRIRE_LES_OBTENUES = "Écrire les {frames} frames obtenues"

#: La DROITE du bandeau, verbatim de la maquette `E3-6` (l. 2).
#:
#: **Elle est ecrite ici plutot que laissee a l'appelant.** `ObjetTravaille`
#: existe parce que les ecrans partages de `execution.py` ne peuvent pas savoir
#: sur quoi on travaille -- ce vocabulaire est celui de l'atelier. Mais cet
#: ecran-ci **est** celui du Scan, et son objet ne varie pas d'un montage a
#: l'autre : le laisser vide par defaut ferait recopier la phrase au cablage,
#: donc la ferait diverger de la maquette au premier ajustement. C'est le
#: defaut `I3` pris par l'autre bout -- « un composant que rien ne cable est un
#: composant que le produit n'a pas », et une phrase que deux modules ecrivent
#: est une phrase que le produit dit deux fois.
OBJET_DU_BANDEAU = "temps 2 sur 2 · écrire"

#: Le separateur des mesures de la ligne d'etat, verbatim de la maquette.
#:
#: **Il est redige ici plutot qu'importe**, et c'est un choix de dependance :
#: `atelier_scan_parcours` porte la meme constante, mais c'est lui qui
#: importera ce module au cablage (lot H). L'importer en retour fabriquerait un
#: cycle. `atelier_scan_completion` a tranche pareil, pour la meme raison.
SEPARATEUR_DE_MESURE = " · "

#: Ce que la ligne d'etat dit en fin de mesure, verbatim de la maquette `E3-6`
#: (l. 22 : « ... — rien n'a encore été écrit »).
#:
#: **Derivee de `panneau.RIEN_ECRIT`, jamais recopiee.** La phrase existe une
#: fois dans le depot ; ce qui change ici est sa place dans la ligne -- elle est
#: en queue d'une mesure, donc sans majuscule ni point final. Une seconde
#: redaction divergerait de la premiere au premier ajustement d'accent, et
#: c'est exactement le defaut `I6` (une phrase desaccentuee a la source rendait
#: le repli ASCII indistinguable du nominal).
QUEUE_RIEN_ECRIT = RIEN_ECRIT[0].lower() + RIEN_ECRIT[1:].rstrip(".")

#: Le lien entre la mesure et sa queue, verbatim de la maquette.
LIAISON_DE_LA_MESURE = " — "

#: La ligne de raccourcis de `E3-6`.
#:
#: **Elle n'est plus `execution.RACCOURCIS_CONFIRMATION`** (`EPIC11-ARB-141`).
#: Elle l'etait, et c'etait juste tant que l'ecran avait un mode d'edition : la
#: constante commune porte `Tab` et sa destination. Cet ecran n'a plus de mode,
#: donc l'annoncer promettrait une touche qui ne fait rien -- ce que `coque.py`
#: documente comme un defaut a part entiere, et ce que le meme arbitrage a deja
#: fait retirer aux ateliers Pdf et Exports. Corriger la constante partagee
#: toucherait `execution.py`, que ce lot n'a pas le droit d'ouvrir : c'est donc
#: une ligne propre, et l'ecart sur la constante partagee reste ouvert.
#:
#: **Le repli ASCII l'ALLONGE de cinq colonnes** (`Entree` pour `⏎`), et c'est
#: le regime qui commande le budget : la zone utile est de 76 colonnes.
#: MESURE: 44/49
RACCOURCIS_SCAN_CONFIRMATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"


def _accorder(valeur: int, singulier: str, pluriel: str) -> str:
    """« 1 lot », « 2 lots ». Le pluriel suit le compte, jamais un `+ "s"`."""
    return f"{valeur} {singulier if abs(valeur) <= 1 else pluriel}"


# ---------------------------------------------------------------------------
# Le plan : ce qui SERA ecrit, avant que quoi que ce soit le soit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LotAEcrire:
    """Un lot que le temps 2 ecrira, avec son slug d'ingest editable.

    `frames` et `frames_attendues` sont **repris tels quels** de
    :class:`~mixed_media_utility.tui.atelier_scan_rapport.PanneauDeLot`
    (AC 4.2) : les rederiver ici ferait deux comptes du meme lot, et l'ecran de
    confirmation contredirait le rapport qui vient de les montrer.
    """

    lot_id: str
    #: Le slug d'ingest **lu du document de ce lot**, jamais recompose. C'est
    #: la valeur conventionnelle que `EPIC11-ARB-8` prerempli et que
    #: l'operateur peut modifier.
    slug: str
    frames: int
    frames_attendues: int | None
    #: Les frames que ce lot a **deja** sur le disque, comptees par
    #: `atelier_scan_ecriture.frames_du_dossier` et **donnees** par l'atelier
    #: (`EPIC11-ARB-133`). Zero veut dire « rien de deja ecrit, ou je ne sais
    #: pas ou ce lot ecrit » -- les deux se valent ici, c'est un renseignement
    #: et jamais une regle : voir :func:`issues_de_la_confirmation`.
    #:
    #: **Ce module ne compte rien lui-meme**, et c'est son invariant : un
    #: second comptage divergerait de celui que `T6-1` fait deja.
    frames_deja_ecrites: int = 0


@dataclass(frozen=True)
class PlanDEcriture:
    """Ce que `E3-6` montre : les lots, leur cout, et la calibration retenue.

    **L'ordre des lots est celui du rapport**, c'est-a-dire celui du tri du
    coeur. Il n'est jamais retrie ici, et c'est sur lui qu'un banc verifie le
    rang d'une cible.
    """

    lots: tuple[LotAEcrire, ...] = ()
    #: Le majorant d'espace disque en octets, ou `None` quand une dimension de
    #: decoupe manque -- « une dimension inconnue traverse en `None` » (AC 4.7).
    octets_majorants: int | None = None
    #: Le profil de chaine retenu en `E3-5`, ou `None` pour « aucune » (le lot
    #: est livre brut). C'est l'atelier qui le **donne** : le retrouver ici
    #: serait une seconde lecture de la designation du projet (AC 3.1).
    calibration: str | None = None

    # -- lecture ------------------------------------------------------------

    @property
    def frames_obtenues(self) -> int:
        """Le total des frames **reelles** : ce qui sera ecrit."""
        return sum(lot.frames for lot in self.lots)

    @property
    def frames_attendues(self) -> int | None:
        """Le total attendu, ou `None` **des qu'un seul lot ne le porte pas**.

        Et non « on somme ce qu'on a » : un total partiel se lirait comme un
        total, et c'est precisement la valeur devinee que `DESIGN.md`
        section 3 interdit. Meme regle, meme forme, que
        `EcranRapportDeDetection._somme`.

        Un plan **sans aucun lot** rend `None` lui aussi : `sum(())` vaut zero,
        et « zero frame attendue » se lirait comme une mesure alors que rien
        n'a ete mesure.
        """
        attendues = [lot.frames_attendues for lot in self.lots]
        if not attendues or any(valeur is None for valeur in attendues):
            return None
        return sum(attendues)

    @property
    def manque(self) -> int | None:
        """`attendues - obtenues`, ou `None` quand l'attendu n'existe pas.

        Positif : il manque des frames. Negatif : le document en porte plus que
        le manifest n'en declarait. Les deux se disent
        (:func:`mention_des_obtenues`) -- un surplus tu serait un ecart entre le
        manifest et le document que personne ne verrait passer.
        """
        attendues = self.frames_attendues
        if attendues is None:
            return None
        return attendues - self.frames_obtenues

    @property
    def toutes_les_frames_attendues(self) -> bool:
        """Vrai quand les deux comptes coincident. `None` attendu rend faux."""
        return self.manque == 0

    @property
    def slugs_conventionnels(self) -> tuple[str, ...]:
        """Les slugs proposes, **dans l'ordre des lots**."""
        return tuple(lot.slug for lot in self.lots)

    @property
    def frames_deja_ecrites(self) -> int:
        """Les frames deja sur le disque, tous lots du plan confondus.

        C'est la somme de ce que l'atelier a **donne**, jamais un comptage fait
        ici. Elle vaut zero sur un projet neuf, et c'est le regime nominal.
        """
        return sum(lot.frames_deja_ecrites for lot in self.lots)


def slugs_par_lot(documents: Sequence[Any]) -> dict[str, str]:
    """`lot_id -> ingest_slug`, lu des documents **deja relus**.

    Le **premier** document d'un lot fait foi, comme
    `atelier_scan_rapport._grouper_par_lot` donne au lot le rang de son premier
    document : plusieurs documents du meme lot s'additionnent (contrat de 5.25,
    plusieurs scans de la meme planche), mais ils portent le meme sujet.

    L'appariement se fait **par `lot_id`**, jamais par rang : c'est ce qui
    empeche le slug d'un lot d'atterrir sur un autre quand le rapport et les
    documents n'ont pas le meme ordre.
    """
    slugs: dict[str, str] = {}
    for document in documents:
        lot_id = document.subject.lot_id
        if lot_id not in slugs:
            slugs[lot_id] = document.subject.ingest_slug
    return slugs


def majorant_du_document(documents: Sequence[Any]) -> int | None:
    """Le majorant d'espace disque des frames que ces documents produiront.

    Le poids d'une frame est celui de
    `atelier_extraction_ecriture.octets_par_frame` -- **aucune seconde
    formule** : c'est celle de `source_confirmation`, aux memes constantes de
    canaux et de profondeur. Ce qui change ici est la dimension : le scan
    decoupe des rectangles de tailles differentes, donc chaque zone porte la
    sienne (`crop_w_px` / `crop_h_px`, `scan_previz.PrevizFrameZone`).

    **Une dimension inconnue traverse en `None`** (AC 4.7) : le total entier
    devient inconnu, et la ligne dira qu'elle ne sait pas. Sommer ce qu'on sait
    rendrait un majorant qui n'en est plus un, c'est-a-dire un chiffre faux la
    ou l'operateur decide.

    Les trois boucles -- documents, pages, zones -- vont **jusqu'au bout** :
    aucune sortie anticipee ne peut faire disparaitre des zones en silence, et
    un banc le mesure sur trois zones dont la cible est au milieu.
    """
    total = 0
    connu = False
    for document in documents:
        for page in document.pages:
            for zone in page.frame_zones:
                octets = octets_par_frame(zone.crop_w_px, zone.crop_h_px)
                if octets is None:
                    return None
                total += octets
                connu = True
    return total if connu else None


def preparer_le_plan(rapport: RapportDeDetection, documents: Sequence[Any], *,
                     calibration: str | None = None,
                     frames_deja_ecrites: Mapping[str, int] | None = None
                     ) -> PlanDEcriture:
    """Assembler le plan de `E3-6` depuis le rapport du temps 1.

    :param rapport: le :class:`RapportDeDetection` que `E3-3` / `E3-4` viennent
        de montrer. Ses deux cardinaux de frames sont repris **tels quels**.
    :param documents: les :class:`~mixed_media_utility.scan_previz.ScanPreviz`
        de la passe, **deja relus** -- les memes objets que la projection du
        rapport a consommes. Ils portent le slug d'ingest et les dimensions de
        decoupe, qui ne sont ni l'un ni l'autre dans le rapport.
    :param calibration: le profil retenu en `E3-5`, ou `None` pour « aucune ».
    :param frames_deja_ecrites: `lot_id -> cardinal des frames deja presentes
        sur le disque`, **compte par l'atelier** et jamais ici
        (`EPIC11-ARB-133`). Un lot absent de la table vaut zero : c'est le
        regime nominal -- un projet neuf n'a rien d'ecrit --, et un `None`
        entier est le regime d'un banc qui monte `E3-6` seul.

    **Un lot du rapport dont aucun document ne porte le slug garde son
    `lot_id`** comme valeur proposee. C'est le seul repli honnete : inventer un
    slug ferait proposer un nom que rien n'a produit, et laisser le nom vide
    ferait echouer la validation sur un lot que l'operateur n'a pas touche.
    Le cas ne se rencontre pas en regime nominal -- le rapport est projete des
    memes documents -- et il est mesure pour qu'il ne devienne pas un plantage.
    """
    slugs = slugs_par_lot(documents)
    deja = frames_deja_ecrites or {}
    lots = tuple(
        LotAEcrire(lot_id=lot.lot_id,
                   slug=slugs.get(lot.lot_id, lot.lot_id),
                   frames=lot.frames,
                   frames_attendues=lot.frames_attendues,
                   # `int(...)` et non la valeur brute : la table vient d'un
                   # comptage de disque, et un comptage rate y vaut zero -- le
                   # meme repli que `frames_du_dossier`, qui rend zero sur
                   # toute panne de lecture plutot que de lever.
                   frames_deja_ecrites=int(deja.get(lot.lot_id, 0) or 0))
        for lot in rapport.lots)
    return PlanDEcriture(lots=lots,
                         octets_majorants=majorant_du_document(documents),
                         calibration=calibration)


# ---------------------------------------------------------------------------
# `E3-6` -- le cartouche, ses noms, ses issues
# ---------------------------------------------------------------------------


def _somme_par_lot(valeurs: Iterable[int], total: int) -> str:
    """`124 + 62 = 186`, ou `124` quand il n'y a qu'un lot.

    Un seul lot n'a pas de total a montrer -- `124 = 124` serait du bruit --,
    exactement comme `atelier_extraction_ecriture._ligne_des_frames` le fait
    pour `E2-3`. La forme somme est celle de la maquette `E3-6`.
    """
    valeurs = list(valeurs)
    if len(valeurs) == 1:
        return f"{valeurs[0]}"
    return f"{' + '.join(str(valeur) for valeur in valeurs)} = {total}"


def ligne_des_frames_attendues(plan: PlanDEcriture) -> LigneChiffree:
    """« Frames attendues », **sa propre ligne** (AC 4.2, demande d'Egan).

    Quand le manifest ne declare l'attendu d'aucun lot -- ou d'un seul --, la
    ligne le **dit** : elle ne replie pas les obtenues sur les attendues, ce
    qui ferait lire une egalite mesuree la ou rien n'a ete mesure.
    """
    attendues = plan.frames_attendues
    if attendues is None:
        return LigneChiffree(LIBELLE_FRAMES_ATTENDUES,
                             FRAMES_ATTENDUES_INCONNUES)
    valeurs = [lot.frames_attendues for lot in plan.lots]
    return LigneChiffree(
        LIBELLE_FRAMES_ATTENDUES,
        f"{_somme_par_lot(valeurs, attendues)} {UNITE_FRAMES}")


def mention_des_obtenues(plan: PlanDEcriture,
                         ascii_seul: bool = False) -> str:
    """`● toutes`, `✕ 3 manquantes`, `✕ 2 en trop` -- ou rien (AC 4.3).

    **Rien quand l'attendu n'existe pas** : sans terme de comparaison, `● toutes`
    affirmerait une egalite que personne n'a mesuree, et `✕` accuserait un
    manque qui n'est pas su. Un champ que la source ne porte pas est **omis**,
    jamais rendu `0` ni `--` (`DESIGN.md` section 3).

    Le glyphe est pose par :func:`jetons.marque`, qui le lit de la table de
    `DESIGN.md` section 6 par sa **cle** : le dessiner ici en ferait une
    seconde table, et le repli ASCII lui echapperait.
    """
    manque = plan.manque
    if manque is None:
        return ""
    if manque == 0:
        return jetons.marque("complete", MENTION_TOUTES, ascii_seul)
    if manque > 0:
        libelle = GABARIT_MANQUE.format(compte=manque,
                                        s="" if manque == 1 else "s")
    else:
        libelle = GABARIT_EN_TROP.format(compte=-manque)
    return jetons.marque("absent", libelle, ascii_seul)


def ligne_des_frames_obtenues(plan: PlanDEcriture,
                              ascii_seul: bool = False) -> LigneChiffree:
    """« Frames obtenues », sa mention d'etat comprise (AC 4.2 et AC 4.3)."""
    valeur = _somme_par_lot([lot.frames for lot in plan.lots],
                            plan.frames_obtenues)
    mention = mention_des_obtenues(plan, ascii_seul)
    texte = f"{valeur} {UNITE_FRAMES}"
    return LigneChiffree(LIBELLE_FRAMES_OBTENUES,
                         f"{texte}   {mention}" if mention else texte)


def ligne_de_l_espace(plan: PlanDEcriture) -> LigneChiffree:
    """« Espace disque », **toujours** marquee majorant quand elle chiffre.

    Meme forme que `atelier_extraction_ecriture._ligne_de_l_espace`, et le
    rendu de taille est celui que l'explorateur porte deja : deux formats du
    meme chiffre dans la meme interface divergeraient au premier ajustement.
    """
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is None:
        return LigneChiffree(LIBELLE_ESPACE, ESPACE_INCONNU)
    valeur, _, unite = lisible.partition(" ")
    return LigneChiffree(LIBELLE_ESPACE, PREFIXE_APPROCHE + valeur, unite,
                         majorant=True)


def ligne_des_deja_ecrites(plan: PlanDEcriture) -> LigneChiffree | None:
    """`Déjà sur le disque   124 frames`, ou `None` quand il n'y a rien.

    **Elle n'est posee que si le compte est non nul**, et jamais a zero : une
    ligne « 0 frame deja ecrite » sur un projet neuf serait du bruit sur le
    regime nominal, et le cartouche de la maquette `E3-6` porte six lignes.
    Quand elle apparait, elle est la seule chose qui explique la quatrieme
    issue -- et `EPIC11-ARB-4` veut qu'un panneau chiffre porte ce que la
    passe va produire ET ce qu'elle rencontre.

    Le chiffre est **donne** par l'atelier, jamais compte ici : voir
    :attr:`LotAEcrire.frames_deja_ecrites`.
    """
    deja = plan.frames_deja_ecrites
    if deja <= 0:
        return None
    return LigneChiffree(LIBELLE_DEJA_ECRITES, deja, UNITE_FRAMES)


def panneau_de_la_confirmation(plan: PlanDEcriture,
                               ascii_seul: bool = False,
                               largeur: int = jetons.LARGEUR_PLANCHER) -> Panneau:
    """Le cartouche de `E3-6`. Six lignes, et chacune est exigee par `ARB-4`.

    Ce qui sera produit (les lots, et sous le cartouche leurs noms), en quelle
    quantite (les frames attendues **et** les frames obtenues, sur deux lignes
    distinctes), et ce que cela coute (l'espace disque, en majorant explicite).
    La profondeur et la calibration s'y ajoutent parce que la maquette les
    porte -- et la calibration parce que « trois semaines plus tard, c'est
    l'information qu'on cherche ».
    """
    lignes = [
        LigneChiffree(LIBELLE_LOTS, len(plan.lots), "lots"),
        ligne_des_frames_attendues(plan),
        ligne_des_frames_obtenues(plan, ascii_seul),
        LigneChiffree(LIBELLE_PROFONDEUR, OUTPUT_BIT_DEPTH, UNITE_PROFONDEUR),
        LigneChiffree(LIBELLE_CALIBRATION,
                      plan.calibration or CALIBRATION_AUCUNE),
        ligne_de_l_espace(plan),
    ]
    # En **queue** du cartouche, et seulement quand il y a quelque chose a
    # dire : les six lignes de la maquette gardent leur rang, et le rang de la
    # ligne des obtenues -- que `EcranScanConfirmation` cherche par son libelle
    # -- n'est de toute facon jamais calcule a la main.
    deja = ligne_des_deja_ecrites(plan)
    if deja is not None:
        lignes.append(deja)
    # **Les noms vivent DANS le panneau depuis `EPIC11-ARB-141`.** Ils etaient
    # des widgets a part, un par nom, pour qu'un nom refuse puisse porter sa
    # propre couleur ; aucun n'etant plus editable, aucun ne peut plus etre
    # refuse.
    return Panneau(TITRE_A_ECRIRE, lignes,
                   noms=noms_du_plan(plan, largeur, ascii_seul))


def noms_du_plan(plan: PlanDEcriture,
                 largeur: int = jetons.LARGEUR_PLANCHER,
                 ascii_seul: bool = False) -> list[str]:
    """Les slugs d'ingest, **derives de ce que le document porte**, un par ligne.

    La valeur est celle que le temps 1 a ecrite dans le document ; la recomposer
    ici ferait deux redactions du meme slug.

    **Aucun n'est editable** (`EPIC11-ARB-141`, verbatim d'Egan : « On retire
    l'edition des noms PARTOUT ou elle ne peut pas etre effective. On la laisse
    uniquement la ou on sait la cabler. »). Ce sont des lignes de texte, pas des
    champs -- c'est pour cela qu'ils vivent dans `Panneau.noms` et non dans un
    `ModeleNoms`, qui est le modele de l'edition.

    **Cet ecran editait de surcroit le mauvais objet**, et c'est un defaut
    independant du cablage : `ingest_slug` nomme le **seul** dossier
    `scans/<ingest_slug>/`, il n'entre ni dans un nom de lot ni dans un nom de
    frame -- le dossier de sortie du lot vient de `derive_lot_dir_slug`, dont
    les trois arguments sont lus au payload QR. L'ecran offrait donc *par lot*
    une valeur dont un scan n'a qu'un seul exemplaire, et en regime vrac les
    trois valeurs proposees etaient identiques.

    Les montrer reste **obligatoire** (`EPIC11-ARB-4`) : on retire a cet ecran
    un mode, pas sa raison d'etre -- c'est le point de jugement du temps 2, il
    dit ce qui sera ecrit.
    """
    budget = jetons.largeur_de_cartouche(largeur) - len(INDENT_DES_NOMS)
    return [INDENT_DES_NOMS + jetons.abreger_nom(lot.slug, budget, ascii_seul)
            for lot in plan.lots]


def issues_de_la_confirmation(plan: PlanDEcriture) -> ChoixExclusif:
    """Les trois issues de `E3-6`. Une seule ecrit, et le curseur ne la vise pas.

    **Aucune n'est preselectionnee, et cela ne se reecrit pas ici** : c'est un
    invariant leve a la construction par :class:`panneau.ChoixExclusif`
    (`EPIC11-ARB-7`), qui refuse aussi qu'aucune issue n'ecrive et **place** le
    curseur, au montage, sur la premiere issue qui n'ecrit pas
    (`EPIC11-ARB-45`). Le rendu est **une ligne par issue, la fleche seule**
    (`EPIC11-ARB-126`), ce que `ChoixExclusif.rendu` fait deja.

    Le libelle de la premiere issue porte le **compte reel** des qu'il diverge
    de l'attendu (AC 4.3).

    **La quatrieme issue, et la condition exacte de sa presence**
    (`EPIC11-ARB-133`). « Écrire une nouvelle version » n'apparait que si le
    plan porte des frames **deja sur le disque**, c'est-a-dire exactement dans
    le regime ou le coeur refuserait l'ecriture
    (`scan_output_frames._assert_writable`) et ou l'interface ne savait, avant
    cet arbitrage, que rendre un `EcranRefus` sans issue.

    **La condition est un renseignement, jamais une regle de rang.** Ce module
    ne resout aucun rang, n'ecrit aucun `_vN` et ne consulte aucun dossier :
    il lit un cardinal que l'atelier lui a donne, et l'issue qu'il pose se
    contente de poser `nouvelle_version=True` au coeur, qui possede la regle
    une fois pour tous les objets (`io.version_ranks`, `EPIC11-ARB-108`). Un
    comptage a zero le mesure, avec son volet symetrique.

    **Ce que la condition peut manquer, dit plutot que tu.** Le compte porte
    sur le dossier de sortie du lot ; le coeur, lui, refuse sur les **fichiers
    precisement vises**. Les deux divergent sur un lot partiellement ecrit
    dont la seconde passe n'apporte que des pages neuves : l'issue est alors
    offerte alors que le coeur n'aurait pas refuse. C'est un excedent, pas un
    manque -- l'operateur qui la retient obtient ce qu'elle annonce, un jeu
    voisin -- et l'excedent est le bon sens du risque : offrir une issue de
    trop ne detruit rien, n'en offrir aucune est le blocage sec.

    **Pourquoi elle porte `ecrit=True`.** Sur cet ecran, `Issue.ecrit` marque
    l'issue qui **ecrit** -- c'est deja le cas de « Écrire les TIFF », qui ne
    detruit rien non plus. La marquer garde l'invariant d'`EPIC11-ARB-45` : le
    curseur part au montage sur la premiere issue qui n'ecrit pas, donc sur
    « Modifier », et aucune ecriture n'est atteignable en une seule frappe. La
    marquer `ecrit=False` ferait partir le curseur **sur elle**, c'est-a-dire
    poserait une ecriture sous `Entree` au montage.

    L'ordre est celui de la deliberation : ecrire, versionner, revenir,
    renoncer. Elle est **seconde** et non premiere -- l'issue nominale reste en
    tete, y compris quand le lot est deja ecrit.
    """
    libelle = LIBELLE_ECRIRE
    if plan.manque not in (None, 0):
        libelle = GABARIT_ECRIRE_LES_OBTENUES.format(
            frames=plan.frames_obtenues)
    issues = [Issue(ISSUE_ECRIRE, libelle, ecrit=True)]
    if plan.frames_deja_ecrites > 0:
        issues.append(Issue(ISSUE_NOUVELLE_VERSION, LIBELLE_NOUVELLE_VERSION,
                            ecrit=True))
    issues.append(Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER))
    issues.append(Issue(ISSUE_ANNULER, LIBELLE_ANNULER))
    return ChoixExclusif(issues)


def mesure_de_la_confirmation(plan: PlanDEcriture) -> str:
    """La ligne d'etat de `E3-6` : **une mesure**, verbatim de la maquette.

    `2 lots · 186 frames · ~ 5,4 Go — rien n'a encore été écrit` (l. 22).

    `EPIC11-ARB-56`, et c'est l'ecart `H6` de cette story : **aucune touche,
    aucun nombre de limite, aucun motif de conception**. Ce que la ligne portait
    dans la maquette d'origine -- la lettre `e`, le verbe « editer les noms », et
    la borne en caracteres ecrite en clair -- cumulait les trois fautes : une
    touche, une **lettre** offerte a cote d'un champ de saisie
    (`EPIC11-ARB-68`), et la limite **recopiee** la ou `noms.LIMITE` **est**
    `io.naming.CANONICAL_ID_MAX_LENGTH`.

    Le nombre lui-meme n'est pas recopie ici, pas meme en commentaire : la
    frontiere de l'AC 4.6 balaye le **fichier entier**, prose comprise. Une
    borne citee dans une docstring reste une borne ecrite deux fois, et c'est
    elle qu'une relecture prendrait pour la reference.

    Le majorant est **omis** quand il n'est pas su, plutot que rendu « inconnu »
    en ligne d'etat : le cartouche le dit deja, et la ligne d'etat ne porte que
    ce qu'elle mesure.
    """
    parts = [_accorder(len(plan.lots), "lot", "lots"),
             _accorder(plan.frames_obtenues, "frame", "frames")]
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is not None:
        parts.append(PREFIXE_APPROCHE + lisible)
    return (SEPARATEUR_DE_MESURE.join(parts) + LIAISON_DE_LA_MESURE
            + QUEUE_RIEN_ECRIT)


# ---------------------------------------------------------------------------
# L'ecran
# ---------------------------------------------------------------------------


class EcranScanConfirmation(EcranChiffre):
    """`E3-6` -- le point de jugement du temps 2. **Rien n'est encore ecrit.**

    Elle herite d'`EcranChiffre` et n'ecrit **pas** un second point de jugement
    (AC 4.1) : le cartouche, le bloc de noms, le mode d'edition, `Tab`,
    `Ctrl+R`, le compteur vivant, le refus a la limite et l'inaccessibilite de
    l'action principale y sont deja, mesures par la story 11.1. Ce que cette
    classe ajoute est ce qui lui est propre : sa ligne d'etat mesuree (AC 4.8),
    et la couleur du glyphe d'etat pose **dans** le cartouche.

    **Le glyphe du cartouche, et pourquoi il demande une ligne de plus.**
    `jetons.peindre` reconnait un etat par motif a deux conditions de mise en
    page -- le glyphe **ouvre une colonne** et porte son libelle a un blanc.
    Un glyphe pose au milieu d'une ligne chiffree ne remplit ni l'une ni
    l'autre : il resterait donc **incolore**, ce qui est exactement le defaut
    que la story 11.4 a trouve (« aucun glyphe d'etat pose dans un cartouche
    n'etait colore »). Le correctif livre alors est le parametre `etats` de
    `peindre` -- l'etat se **donne**, ligne par ligne --, et c'est lui que cet
    ecran emploie. `execution.py` n'est **pas** modifie pour autant : c'est un
    module partage avec l'Extraction, et le toucher serait la contention que la
    regle de decoupage interdit.
    """

    titre = "Scan"
    raccourcis = RACCOURCIS_SCAN_CONFIRMATION

    #: **Un passage, pas une station** : c'est la valeur qu'`EcranChiffre` pose
    #: deja pour tous les points de jugement. Elle est redite ici parce qu'un
    #: point de jugement franchi ne doit pas rester sur le chemin du retour.
    TRANSITOIRE = True

    def __init__(self, plan: PlanDEcriture, *,
                 sur_issue: Callable[[Issue], None] | None = None,
                 objet: str = OBJET_DU_BANDEAU) -> None:
        # **Aucun `noms=`**, et c'est le sujet d'`EPIC11-ARB-141` : le modele
        # d'edition n'est meme plus importe par ce module. `EcranChiffre` en
        # pose un vide de lui-meme, si bien que `Tab` n'a aucune destination et
        # que `traiter` le rend inerte -- ce n'est pas une garde ajoutee ici,
        # c'est la consequence de ne pas donner de noms editables.
        super().__init__(panneau_de_la_confirmation(plan),
                         issues_de_la_confirmation(plan),
                         sur_issue=sur_issue, objet=objet)
        #: Le plan montre. C'est lui qui porte les chiffres ; l'ecran n'en
        #: recalcule aucun.
        self.plan = plan

    # -- lecture ------------------------------------------------------------

    # -- rendu ---------------------------------------------------------------

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche, **recompose au mode d'affichage courant**.

        La mention d'etat de la ligne des frames obtenues porte un glyphe, et un
        glyphe se replie : le panneau construit a la creation de l'ecran ne peut
        donc pas servir tel quel en repli ASCII. On le refait au mode courant
        plutot que de replier une chaine deja assemblee -- `replier_ascii` sur
        du texte deja compose marche, mais faire dependre le rendu d'un aller
        et retour de repli est exactement ce que `jetons.abreger_nom` documente
        comme fragile (« `ascii_seul` precede la mesure »).
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = self.app.size.width
        # La largeur passe desormais au panneau : c'est elle qui borne
        # l'abregement des noms, qui sont du texte de cartouche depuis
        # `EPIC11-ARB-141`.
        panneau = panneau_de_la_confirmation(self.plan, ascii_seul, largeur)
        return panneau.rendu(largeur, ascii_seul)

    def etats_du_panneau(self) -> dict[int, str]:
        """L'etat de chaque ligne du cartouche, **donne** et non devine.

        Une seule ligne en porte un -- « Frames obtenues » --, et son rang se
        lit sur la liste des lignes du panneau, jamais sur un compte ecrit a la
        main : une ligne inseree plus haut deplacerait la couleur d'une ligne
        sans que rien ne le dise.
        """
        if self.plan.manque is None:
            return {}
        rang = self._rang_des_obtenues()
        if rang is None:
            return {}
        return {rang: "complete" if self.plan.manque == 0 else "absent"}

    def _rang_des_obtenues(self) -> int | None:
        """Le rang de la ligne « Frames obtenues » dans le cartouche.

        Cherche par son libelle sur les lignes **rendues**, c'est-a-dire sur
        celles que `peindre` recevra : un rang calcule sur une autre liste que
        celle qui est peinte est un appariement, donc une occasion de le rater.
        """
        for rang, ligne in enumerate(self.lignes_du_panneau()):
            if ligne.startswith(LIBELLE_FRAMES_OBTENUES):
                return rang
        return None

    def rafraichir(self) -> None:
        """Le rendu de la classe de base, **plus la couleur du cartouche**.

        La classe de base peint le cartouche sans lui donner d'etat ; on
        repasse dessus avec `etats=`, ce qui est la seule facon de teinter un
        glyphe qui n'ouvre pas de colonne. Rien d'autre n'est refait : les noms,
        le bloc de refus, les issues et la ligne d'etat restent ceux de la
        classe de base.
        """
        super().rafraichir()
        if not self._assez_grand_au_dernier_dessin:
            return
        etats = self.etats_du_panneau()
        if not etats:
            return
        self._chiffres.update(bloc_peint(
            self.lignes_du_panneau(),
            jetons.largeur_de_cartouche(self.app.size.width),
            self.app, etats=etats))

    def etat(self) -> str:
        """La ligne d'etat : **une mesure**, jamais une touche (`EPIC11-ARB-56`).

        Le regime de refus de la classe de base passe en premier -- c'est le
        moment ou l'operateur a besoin d'autre chose que le total de la passe.
        Hors de ce cas, la ligne porte la mesure de `E3-6` (AC 4.8), la ou la
        classe de base rendrait `panneau.RIEN_ECRIT` seul.

        **Le regime d'edition a disparu de cette condition** avec le champ qui
        le declenchait (`EPIC11-ARB-141`) : il ne peut plus se presenter, et le
        garder aurait laisse une branche que rien n'atteint.
        """
        if self._refus_annonce is not None:
            return super().etat()
        return mesure_de_la_confirmation(self.plan)


__all__ = [
    "CALIBRATION_AUCUNE",
    "ESPACE_INCONNU",
    "FRAMES_ATTENDUES_INCONNUES",
    "GABARIT_ECRIRE_LES_OBTENUES",
    "GABARIT_EN_TROP",
    "GABARIT_MANQUE",
    "ISSUE_ANNULER",
    "ISSUE_ECRIRE",
    "ISSUE_MODIFIER",
    "ISSUE_NOUVELLE_VERSION",
    "LIAISON_DE_LA_MESURE",
    "LIBELLE_ANNULER",
    "LIBELLE_CALIBRATION",
    "LIBELLE_DEJA_ECRITES",
    "LIBELLE_ECRIRE",
    "LIBELLE_FRAMES_ATTENDUES",
    "LIBELLE_FRAMES_OBTENUES",
    "LIBELLE_LOTS",
    "LIBELLE_MODIFIER",
    "LIBELLE_NOUVELLE_VERSION",
    "LIBELLE_PROFONDEUR",
    "MENTION_TOUTES",
    "OBJET_DU_BANDEAU",
    "QUEUE_RIEN_ECRIT",
    "RACCOURCIS_SCAN_CONFIRMATION",
    "SEPARATEUR_DE_MESURE",
    "UNITE_FRAMES",
    "UNITE_PROFONDEUR",
    "EcranScanConfirmation",
    "LotAEcrire",
    "PlanDEcriture",
    "issues_de_la_confirmation",
    "ligne_de_l_espace",
    "ligne_des_deja_ecrites",
    "ligne_des_frames_attendues",
    "ligne_des_frames_obtenues",
    "majorant_du_document",
    "mention_des_obtenues",
    "mesure_de_la_confirmation",
    "noms_du_plan",
    "panneau_de_la_confirmation",
    "preparer_le_plan",
    "slugs_par_lot",
]
