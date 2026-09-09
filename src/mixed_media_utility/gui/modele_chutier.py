# -*- coding: utf-8 -*-
"""Modele d'arbre du chutier (story 7.2, AC 2) -- pur, sans Qt.

L'arbre se construit de **deux sources et d'elles seules** :

* le **manifest du projet ouvert** (`rushes[]`, `lots[]` et leurs champs
  d'etat), lu tel quel ;
* les **documents de detection** de la story 5.25, relus par
  :func:`scan_previz.scan_previz_from_json_dict` -- jamais par une seconde
  lecture ad hoc de leurs champs : un renommage chez le producteur doit
  lever, pas vider une famille en silence (lecon de la revue de 5.8).

Rien d'un etat de session, rien d'un parcours de dossier
(``EXPERIENCE.md``, Reprise : « Rien d'affiche ne depend d'un etat de
session »). Ce module ne touche jamais le disque, a une exception injectee :
le predicat d'existence que :func:`relink.statut_de_liaison` utilise pour
dire si le fichier source d'un rush est encore la.

**Trois invariants que ce module tient, et qui sont l'AC 2 elle-meme.**

1. **L'ordre d'affichage est l'ordre des sources.** Les rushes dans l'ordre
   de ``rushes[]``, les lots d'un rush dans l'ordre de ``lots[]``, les pages
   dans l'ordre que la detection a consigne. **Aucun tri local** -- ni
   alphabetique, ni chronologique, ni par ``page_index``. Le contrat de
   module de ``scan_previz`` l'ecrit apres trois defauts payes : « c'est la
   detection qui donne l'ordre, jamais re-triees ». Une frontiere negative
   le mesure (zero ``sorted`` / ``sort`` dans ce fichier).
2. **L'appariement se fait par identifiant** (``lot_id``, ``rush_id``),
   jamais par position. C'est nommement 5.7/`M25` (`_find_lot` rendait le
   premier lot, 257 tests verts) et 5.6/`M33`.
3. **`read_rank` et `page_index` ne se deduisent jamais l'un de l'autre**
   (``scan_previz.PAGE_ADDRESS_FIELDS``) : le noeud de scan porte les deux,
   pour qu'une interface puisse dire « le 3e fichier du dossier declare etre
   la page 1 ».

**Ce que ce module ne re-derive pas.** La completude d'un lot reconstruit se
lit des **trois entiers du manifest** selon la regle ecrite au schema
(complet = ``reconstructed_frame_count == expected_frame_count`` ET
``synthetic_frame_count == 0``) ; celle d'un lot seulement detecte se **lit du
coeur** (:func:`scan_detect.completude_des_planches`, `EPIC7-ARB-73`) et ne
se re-derive plus ici ; l'etat de liaison d'un rush se lit de
:func:`relink.statut_de_liaison`. Toute re-implementation de ces regles ici
serait une divergence en attente -- et le 2026-08-25 elle en a ete une, tres
exactement : deux surfaces, deux derivations, deux verdicts sur le meme
document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from .. import relink, scan_detect, scan_previz

# ---------------------------------------------------------------------------
# Vocabulaire ferme des types de noeud, dans l'ordre d'affichage de la spine
# (correction A1 : rush > lot > planche > scan, JAMAIS inverse).
# ---------------------------------------------------------------------------

TYPE_RUSH = "rush"
TYPE_RUSH_ENCODE = "rush-encode"
TYPE_LOT = "lot"
TYPE_LOT_RECONSTRUIT = "lot-reconstruit"
TYPE_PLANCHE = "planche"
TYPE_SCAN = "scan"

#: Les six types, dans l'ordre de la chaine. Collection ORDONNEE d'elements
#: distinguables : c'est elle qui sert de reference aux cartes du module.
TYPES_DE_NOEUD = (
    TYPE_RUSH,
    TYPE_RUSH_ENCODE,
    TYPE_LOT,
    TYPE_LOT_RECONSTRUIT,
    TYPE_PLANCHE,
    TYPE_SCAN,
)

# ---------------------------------------------------------------------------
# FAMILLE 1 -- completude d'un lot. « Que manque-t-il dans ce lot ? »
# Rendue par le composant `badge-state` (disque plein / anneau creux /
# disque hachure). Ne se confond JAMAIS avec la famille 2 (DESIGN.md,
# correction du 2026-08-23).
# ---------------------------------------------------------------------------

# Les trois noms sont ceux du COEUR (`scan_detect.COMPLETUDES`,
# `EPIC7-ARB-73`), re-exposes ici sous le nom que la surface leur donne. Deux
# listes de litteraux a tenir a jour, c'est deja une divergence en attente :
# la vue du chutier et celle du jugement lisaient le meme mot et le
# derivaient chacune a sa facon (mesure du 2026-08-25).
BADGE_COMPLET = scan_detect.COMPLETUDE_COMPLET
BADGE_COMPLET_AVEC_MIRES = scan_detect.COMPLETUDE_COMPLET_AVEC_MIRES
BADGE_INCOMPLET = scan_detect.COMPLETUDE_INCOMPLET

BADGES_DE_COMPLETUDE = scan_detect.COMPLETUDES

# ---------------------------------------------------------------------------
# FAMILLE 2 -- rattachement d'un objet. « Que dois-je faire de cet objet ? »
# Rendue par le composant `state-glyph` (EPIC7-ARB-5, cas d'usage ARB-12).
# Chaque glyphe appelle un geste : retrouver / identifier / completer.
# ---------------------------------------------------------------------------

GLYPHE_DELIE = "delie"
GLYPHE_NON_RATTACHE = "non-rattache"
GLYPHE_INCOMPLET = "incomplet"

GLYPHES_DE_RATTACHEMENT = (GLYPHE_DELIE, GLYPHE_NON_RATTACHE, GLYPHE_INCOMPLET)

#: Correspondance entre le statut de liaison du coeur et le glyphe de la
#: famille rattachement. Le statut est **lu** de `relink.statut_de_liaison`,
#: jamais recalcule ici (le critere chemin mort / champ absent appartient au
#: coeur). `LIE` n'a pas de glyphe : un objet en ordre ne porte aucun signe.
GLYPHE_PAR_STATUT_DE_LIAISON = MappingProxyType(
    {
        relink.DELINKE_CHEMIN_MORT: GLYPHE_DELIE,
        relink.DELINKE_CHEMIN_ABSENT: GLYPHE_NON_RATTACHE,
    }
)


# ---------------------------------------------------------------------------
# Carte des destinations du double-clic (`EPIC7-ARB-11`, fixee par Egan).
#
# Le principe qui les unifie : **on atterrit sur l'atelier ou l'objet est en
# jeu** -- celui qui le consomme s'il en reste un, celui qui l'a produit
# sinon. La planche et le rush encode sont les deux objets sans consommateur
# dans l'outil (l'impression et la diffusion se passent dehors), d'ou leur
# retour vers l'atelier producteur.
#
# Cette table est le point ou une lecture perimee de la spine se voit : les
# deux cas « planche -> Pdf » et « rush encode -> Exports » sont precisement
# ceux qu'une spine d'avant correction enverrait ailleurs.
# ---------------------------------------------------------------------------

ATELIER_PAR_TYPE = MappingProxyType(
    {
        TYPE_RUSH: "atelier-extraction",
        TYPE_LOT: "atelier-pdf",
        TYPE_PLANCHE: "atelier-pdf",
        TYPE_SCAN: "atelier-scan",
        TYPE_LOT_RECONSTRUIT: "atelier-exports",
        TYPE_RUSH_ENCODE: "atelier-exports",
    }
)


class ChutierError(ValueError):
    """Source inexploitable pour construire l'arbre du chutier.

    Derive de `ValueError` pour rester capturable par un appelant generique.
    Elle signale une **source** que l'arbre ne peut pas lire (document qui
    n'est pas une previz de scan, manifest dont les collections ne sont pas
    des listes), jamais un cas degrade du projet : un rush delie, un lot
    incomplet, une page non identifiee construisent un arbre valide et
    partiel, porte par les badges et les glyphes.
    """


@dataclass(frozen=True)
class Noeud:
    """Un noeud de l'arbre du chutier.

    `identifiant` est **stable** et sert de cle d'appariement (jamais la
    position). `libelle` n'est pas porte ici : les libelles visibles se
    composent au catalogue de chaines, ce module ne rend que des codes du
    coeur et des donnees.

    `read_rank` et `page_index` sont portes **tous les deux** sur les noeuds
    de planche et de scan, et ne se deduisent jamais l'un de l'autre.
    """

    type: str
    identifiant: str
    enfants: tuple["Noeud", ...] = ()
    badge: str | None = None
    glyphe: str | None = None
    read_rank: int | None = None
    page_index: int | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lecture des sources
# ---------------------------------------------------------------------------


def _sequence(valeur: Any, etiquette: str) -> tuple:
    """Rendre une collection du manifest en tuple, ou refuser nommement."""
    if valeur is None:
        return ()
    if isinstance(valeur, Mapping) or not isinstance(valeur, Sequence):
        raise ChutierError(
            f"{etiquette} doit etre une liste, recu {type(valeur).__name__}"
        )
    return tuple(valeur)


def _relire_documents(documents: Any) -> tuple:
    """Relire chaque document de detection par le lecteur normatif de 5.26.

    Le lecteur valide types, vocabulaires, invariants d'etat et coherence des
    adresses. On ne relit **aucun** champ a la main : un renommage chez le
    producteur leve ici plutot que de vider une famille en silence.
    """
    relus = []
    for indice, document in enumerate(_sequence(documents, "documents_de_detection")):
        if isinstance(document, scan_previz.ScanPreviz):
            relus.append(document)
            continue
        try:
            relus.append(scan_previz.scan_previz_from_json_dict(document))
        except scan_previz.ScanPrevizError as erreur:
            raise ChutierError(
                f"documents_de_detection[{indice}] n'est pas un document de "
                f"detection lisible: {erreur}"
            ) from erreur
    return tuple(relus)


def _documents_par_lot(documents: Sequence) -> dict[str, list]:
    """Indexer les documents **par `lot_id`** -- l'appariement est un contrat.

    L'ordre de rencontre est conserve dans chaque liste : c'est l'ordre des
    sources, et il n'est jamais re-trie.
    """
    index: dict[str, list] = {}
    for document in documents:
        index.setdefault(document.subject.lot_id, []).append(document)
    return index


# ---------------------------------------------------------------------------
# Completude : deux sources, deux regles, aucune re-derivation
# ---------------------------------------------------------------------------


def _est_reconstruit(lot: Mapping[str, Any]) -> bool:
    """Un lot est *extrait d'un scan* des que le manifest porte sa sortie.

    Deux marques equivalentes et posees ensemble par 5.7 : le dossier des
    frames rescannees et le cardinal reconstruit. L'une ou l'autre suffit --
    ce module ne choisit pas laquelle 5.7 doit ecrire.
    """
    return (
        lot.get("output_frames_dir") is not None
        or lot.get("reconstructed_frame_count") is not None
    )


def _badge_des_trois_entiers(lot: Mapping[str, Any]) -> str:
    """Completude d'un lot reconstruit, **regle du schema mot pour mot**.

    « complet = ``reconstructed_frame_count == expected_frame_count`` ET
    ``synthetic_frame_count == 0`` ; aucun booleen "complete" n'est ajoute a
    ``lots[]`` ». Le cas intermediaire -- toutes les pages sont la mais des
    frames sont des mires -- est `complet-avec-mires`, **jamais confondu avec
    complet** (``EXPERIENCE.md``, Etats).
    """
    attendu = lot.get("expected_frame_count")
    ecrites = lot.get("reconstructed_frame_count")
    mires = lot.get("synthetic_frame_count") or 0
    if attendu is None or ecrites is None:
        # Cardinal attendu indeterminable : un lot dont l'attendu est inconnu
        # n'est jamais declare complet (EPIC5-ARB-32).
        return BADGE_INCOMPLET
    if ecrites != attendu:
        return BADGE_INCOMPLET
    return BADGE_COMPLET if mires == 0 else BADGE_COMPLET_AVEC_MIRES


def _completude_du_document(documents: Sequence) -> tuple[str | None, tuple[int, ...]]:
    """Completude d'un lot **detecte**, LUE du coeur et jamais recalculee ici.

    `EPIC7-ARB-73` : la completude a **une seule derivation**, et elle vit au
    coeur (:func:`scan_detect.completude_des_planches`). Cette fonction reste
    le nom sous lequel la surface du chutier la demande -- rien de plus.

    Ce qui vivait ici jusqu'au 2026-08-25 en etait la **seconde** redaction :
    elle lisait `counters.pages_expected` quand la surface du jugement lisait
    `max(page_count)`, et les deux rendaient deux verdicts differents sur le
    meme document reel. Ce sont les deux comportements pinnes par les tests
    de ce module -- contradiction de cardinaux, et absence de document -- qui
    sont desormais tenus par le coeur, pour tout le monde a la fois.
    """
    return scan_detect.completude_des_planches(documents)


# ---------------------------------------------------------------------------
# Construction des enfants d'un lot : planches et scans
# ---------------------------------------------------------------------------


def _noeud_de_scan(document, page) -> Noeud:
    """Le scan d'une page : son rang de lecture ET son numero de planche.

    Le glyphe `non-rattache` (U+003F, « identifier ») marque la page dont le
    QR n'a pas livre de numero : l'objet existe, on ignore de quelle planche
    il s'agit (`EPIC7-ARB-12`).
    """
    empreinte = document.fingerprints.detection
    return Noeud(
        type=TYPE_SCAN,
        identifiant=f"{document.subject.lot_id}#{empreinte}#rang-{page.read_rank}",
        read_rank=page.read_rank,
        page_index=page.page_index,
        glyphe=None if page.page_index is not None else GLYPHE_NON_RATTACHE,
        detail={
            "lot_id": document.subject.lot_id,
            "rush_id": document.subject.rush_id,
            "ingest_slug": document.subject.ingest_slug,
            "source_path_relative": page.source_path_relative,
            "status": page.status,
            "qr_status": page.qr_status,
            "empreinte_detection": empreinte,
        },
    )


def _enfants_du_lot(lot_id: str, documents: Sequence) -> tuple[Noeud, ...]:
    """Planches et scans d'un lot, **dans l'ordre des documents**.

    Une seule passe, sans reordonnancement : un noeud de planche nait a la
    **premiere rencontre** de son `page_index`, les scans suivants du meme
    index viennent s'y ranger (story 5.14). Une page sans `page_index` reste
    un scan a la racine du lot, en place -- l'ordre de la source est l'ordre
    affiche, y compris pour ce qui n'est pas rattache.
    """
    enfants: list[Noeud] = []
    scans_par_planche: dict[int, list[Noeud]] = {}
    position_de_planche: dict[int, int] = {}

    for document in documents:
        for page in document.pages:
            scan = _noeud_de_scan(document, page)
            if page.page_index is None:
                enfants.append(scan)
                continue
            if page.page_index not in position_de_planche:
                position_de_planche[page.page_index] = len(enfants)
                scans_par_planche[page.page_index] = []
                enfants.append(
                    Noeud(
                        type=TYPE_PLANCHE,
                        identifiant=f"{lot_id}#planche-{page.page_index}",
                        page_index=page.page_index,
                        detail={"lot_id": lot_id},
                    )
                )
            scans_par_planche[page.page_index].append(scan)

    # Poser les scans sous leur planche, par identifiant d'index, jamais par
    # position dans la liste (`M25` : un `find` positionnel rend le premier).
    for index, position in position_de_planche.items():
        planche = enfants[position]
        enfants[position] = Noeud(
            type=planche.type,
            identifiant=planche.identifiant,
            enfants=tuple(scans_par_planche[index]),
            page_index=planche.page_index,
            detail=planche.detail,
        )
    return tuple(enfants)


def _noeud_de_lot(
    lot_id: str,
    rush_id: str,
    entree: Mapping[str, Any] | None,
    documents: Sequence,
) -> Noeud:
    """Un lot : son type, sa completude, ses planches et ses scans."""
    entree = entree or {}
    reconstruit = _est_reconstruit(entree)
    manquantes: tuple[int, ...] = ()
    if reconstruit:
        badge = _badge_des_trois_entiers(entree)
    else:
        badge, manquantes = _completude_du_document(documents)

    detail = {
        "lot_id": lot_id,
        "rush_id": rush_id,
        "state": entree.get("state"),
        "fps_target_exact": entree.get("fps_target_exact"),
        "expected_frame_count": entree.get("expected_frame_count"),
        "reconstructed_frame_count": entree.get("reconstructed_frame_count"),
        "synthetic_frame_count": entree.get("synthetic_frame_count"),
        "planches_manquantes": manquantes,
        "vient_du_manifest": bool(entree),
    }
    return Noeud(
        type=TYPE_LOT_RECONSTRUIT if reconstruit else TYPE_LOT,
        identifiant=lot_id,
        enfants=_enfants_du_lot(lot_id, documents),
        badge=badge,
        # Un lot incomplet appelle un geste -- completer : c'est le glyphe
        # `incomplet` (U+26A0). Il coexiste avec le badge de completude sans
        # jamais fusionner avec lui (DESIGN.md, deux familles de signes).
        glyphe=GLYPHE_INCOMPLET if badge == BADGE_INCOMPLET else None,
        detail=detail,
    )


def _est_encode(lots: Sequence[Mapping[str, Any]]) -> bool:
    """Un rush est *encode* des qu'un de ses lots porte un master video.

    ``lots[].encoded_masters`` est l'inventaire ecrit par 6.5. Un rush
    encode n'a plus de consommateur dans l'outil : son double-clic renvoie a
    l'atelier qui l'a produit (`EPIC7-ARB-11`).
    """
    for lot in lots:
        if lot.get("encoded_masters"):
            return True
    return False


# ---------------------------------------------------------------------------
# Construction de l'arbre
# ---------------------------------------------------------------------------


def construire_arbre(
    manifest: Mapping[str, Any] | None,
    documents_de_detection: Any = (),
    *,
    existe: Callable[[str], bool] | None = None,
) -> tuple[Noeud, ...]:
    """Construire l'arbre du chutier depuis le manifest et les detections.

    :param manifest: le manifest du projet ouvert (`project.json` relu).
    :param documents_de_detection: documents `scan_previz` en etat
        `detected`, sous leur forme JSON ou deja relus.
    :param existe: predicat d'existence de fichier passe a
        :func:`relink.statut_de_liaison` -- **le seul acces au disque** de ce
        module, et il est injectable pour que le banc n'en fasse aucun.

    Rend les racines dans l'ordre de ``rushes[]``, suivies des branches
    reconstruites depuis un scan seul (role 3), dans leur ordre de rencontre.
    Une branche reconstruite peuple l'arbre **comme les autres** : aucun
    badge de deduction (`EPIC7-ARB-14`), aucun affichage retourne
    (correction A1).
    """
    manifest = manifest or {}
    documents = _relire_documents(documents_de_detection)
    par_lot = _documents_par_lot(documents)

    entrees_de_rush = _sequence(manifest.get("rushes"), "manifest['rushes']")
    entrees_de_lot = _sequence(manifest.get("lots"), "manifest['lots']")

    # Appariement par identifiant, dans l'ordre du manifest.
    lots_par_rush: dict[str, list] = {}
    entree_par_lot: dict[str, Mapping[str, Any]] = {}
    for lot in entrees_de_lot:
        lot_id = lot.get("lot_id")
        if lot_id is None:
            raise ChutierError("un lot du manifest n'a pas de lot_id")
        entree_par_lot[lot_id] = lot
        lots_par_rush.setdefault(lot.get("rush_id"), []).append(lot)

    racines: list[Noeud] = []
    lots_vus: set[str] = set()

    for entree in entrees_de_rush:
        rush_id = entree.get("rush_id")
        lots = lots_par_rush.get(rush_id, [])
        enfants = []
        for lot in lots:
            lot_id = lot["lot_id"]
            lots_vus.add(lot_id)
            enfants.append(
                _noeud_de_lot(lot_id, rush_id, lot, par_lot.get(lot_id, []))
            )
        racines.append(
            Noeud(
                type=TYPE_RUSH_ENCODE if _est_encode(lots) else TYPE_RUSH,
                identifiant=rush_id,
                enfants=tuple(enfants),
                glyphe=GLYPHE_PAR_STATUT_DE_LIAISON.get(
                    relink.statut_de_liaison(entree, existe=existe)
                ),
                detail={
                    "rush_id": rush_id,
                    "source_path": entree.get("source_path"),
                    "source_name": entree.get("source_name"),
                    "statut_de_liaison": relink.statut_de_liaison(entree, existe=existe),
                    "vient_du_manifest": True,
                },
            )
        )

    # Role 3 -- la branche que seul un document de detection declare. Elle se
    # range dans l'ordre habituel rush > lot > planche > scan, apres ce que le
    # manifest porte : l'affichage n'est jamais retourne (correction A1).
    for lot_id, documents_du_lot in par_lot.items():
        if lot_id in lots_vus:
            continue
        rush_id = documents_du_lot[0].subject.rush_id
        noeud_de_lot = _noeud_de_lot(
            lot_id, rush_id, entree_par_lot.get(lot_id), documents_du_lot
        )
        # Recherche par identifiant ET par POSITION reelle : `list.index`
        # compare par egalite structurelle (dataclass gelee) et rendrait le
        # premier noeud equivalent, pas celui qu'on a trouve -- c'est
        # exactement le mode de panne de 5.7/`M25`.
        position_existante = None
        for position, racine in enumerate(racines):
            if racine.identifiant == rush_id:
                position_existante = position
                break
        if position_existante is None:
            racines.append(
                Noeud(
                    type=TYPE_RUSH,
                    identifiant=rush_id,
                    enfants=(noeud_de_lot,),
                    glyphe=GLYPHE_PAR_STATUT_DE_LIAISON.get(
                        relink.statut_de_liaison(None, existe=existe)
                    ),
                    detail={
                        "rush_id": rush_id,
                        "source_path": None,
                        "statut_de_liaison": relink.statut_de_liaison(
                            None, existe=existe
                        ),
                        "vient_du_manifest": False,
                    },
                )
            )
        else:
            existante = racines[position_existante]
            racines[position_existante] = Noeud(
                type=existante.type,
                identifiant=existante.identifiant,
                enfants=existante.enfants + (noeud_de_lot,),
                badge=existante.badge,
                glyphe=existante.glyphe,
                detail=existante.detail,
            )

    return tuple(racines)


# ---------------------------------------------------------------------------
# Parcours
# ---------------------------------------------------------------------------


def parcourir(noeuds: Sequence[Noeud]):
    """Parcours prefixe de l'arbre, dans l'ordre d'affichage."""
    for noeud in noeuds:
        yield noeud
        yield from parcourir(noeud.enfants)


def noeud_par_identifiant(noeuds: Sequence[Noeud], identifiant: str) -> Noeud | None:
    """Retrouver un noeud **par son identifiant**, jamais par sa position."""
    for noeud in parcourir(noeuds):
        if noeud.identifiant == identifiant:
            return noeud
    return None


# ---------------------------------------------------------------------------
# Selection a trois etats (`EPIC7-ARB-10`)
# ---------------------------------------------------------------------------

SELECTION_VIDE = "vide"
SELECTION_PARTIELLE = "partielle"
SELECTION_PLEINE = "pleine"

ETATS_DE_SELECTION = (SELECTION_VIDE, SELECTION_PARTIELLE, SELECTION_PLEINE)

#: Ce qui est ACTIONNABLE dans chaque atelier. « Selectionner un parent vaut
#: selectionner ses **enfants actionnables** dans l'atelier courant, pas tous
#: ses descendants » : sur la page Pdf, selectionner un rush selectionne tous
#: ses lots -- « c'est ce qui construit une planche » --, et non ses planches
#: ni ses scans.
TYPES_ACTIONNABLES_PAR_ATELIER = MappingProxyType(
    {
        "atelier-extraction": (TYPE_RUSH, TYPE_RUSH_ENCODE),
        "atelier-pdf": (TYPE_LOT,),
        "atelier-scan": (TYPE_SCAN,),
        "atelier-exports": (TYPE_LOT_RECONSTRUIT, TYPE_RUSH_ENCODE),
    }
)


def enfants_actionnables(noeud: Noeud, atelier: str) -> tuple[Noeud, ...]:
    """Les objets sur lesquels l'action de `atelier` porterait, sous `noeud`.

    La descente **s'arrete au premier niveau actionnable** : ce sont les
    *enfants actionnables*, pas tous les descendants. Un noeud qui est
    lui-meme du type actionnable se rend lui-meme.
    """
    types = TYPES_ACTIONNABLES_PAR_ATELIER.get(atelier, ())
    if noeud.type in types:
        return (noeud,)
    trouves: list[Noeud] = []
    for enfant in noeud.enfants:
        trouves.extend(enfants_actionnables(enfant, atelier))
    return tuple(trouves)


class Selection:
    """La selection du chutier, a **trois** etats -- vide, partielle, pleine.

    Elle ne retient que des **objets actionnables** : cocher un parent coche
    ses enfants actionnables, et decocher un seul de ces enfants rend le
    parent *partiel*. L'etat d'un parent est donc toujours **derive** de ses
    enfants, jamais memorise a part -- deux memoires divergeraient.
    """

    def __init__(self, racines: Sequence[Noeud], atelier: str):
        self._racines = tuple(racines)
        self._atelier = atelier
        self._cochees: set[str] = set()

    @property
    def atelier(self) -> str:
        """L'atelier dont l'inventaire d'actionnables fait foi."""
        return self._atelier

    def _noeud(self, identifiant: str) -> Noeud | None:
        return noeud_par_identifiant(self._racines, identifiant)

    def actionnables(self, identifiant: str) -> tuple[Noeud, ...]:
        """Les enfants actionnables d'un identifiant, dans l'ordre de l'arbre."""
        noeud = self._noeud(identifiant)
        if noeud is None:
            return ()
        return enfants_actionnables(noeud, self._atelier)

    def selectionner(self, identifiant: str) -> None:
        """Cocher un noeud, c'est cocher ses enfants actionnables."""
        for noeud in self.actionnables(identifiant):
            self._cochees.add(noeud.identifiant)

    def deselectionner(self, identifiant: str) -> None:
        """Decocher un noeud, c'est decocher ses enfants actionnables."""
        for noeud in self.actionnables(identifiant):
            self._cochees.discard(noeud.identifiant)

    def basculer(self, identifiant: str) -> str:
        """Basculer un noeud : plein -> vide, vide ou partiel -> plein."""
        if self.etat(identifiant) == SELECTION_PLEINE:
            self.deselectionner(identifiant)
        else:
            self.selectionner(identifiant)
        return self.etat(identifiant)

    def etat(self, identifiant: str) -> str:
        """L'etat a trois valeurs d'un noeud, DERIVE de ses actionnables."""
        actionnables = self.actionnables(identifiant)
        if not actionnables:
            return SELECTION_VIDE
        cochees = [
            noeud for noeud in actionnables if noeud.identifiant in self._cochees
        ]
        if not cochees:
            return SELECTION_VIDE
        if len(cochees) == len(actionnables):
            return SELECTION_PLEINE
        return SELECTION_PARTIELLE

    def identifiants(self) -> tuple[str, ...]:
        """Les actionnables coches, **dans l'ordre de l'arbre** (jamais trie)."""
        return tuple(
            noeud.identifiant
            for noeud in parcourir(self._racines)
            if noeud.identifiant in self._cochees
            and noeud.type in TYPES_ACTIONNABLES_PAR_ATELIER.get(self._atelier, ())
        )

    def cardinal(self) -> int:
        """Le cardinal de la selection -- ce que l'action doit dire."""
        return len(self.identifiants())

    def est_active(self) -> bool:
        """A zero objet, l'action est INACTIVE (et son libelle le dit)."""
        return self.cardinal() > 0
