"""Tri par QR d'un vrac de pages scannees (story 5.24).

Ce que ce module est, et ce qu'il n'est pas
-------------------------------------------
C'est **une fonction du coeur**, arbitree le 2026-08-17 : « le tri par QR devient
une fonction du coeur ; la GUI ne fait que l'exposer, et la CLI en beneficie
aussi ». Le module est donc **pur** au sens strict : il n'ouvre aucun fichier,
n'ecrit rien, ne journalise rien, et n'importe ni `cli`, ni `argparse`, ni aucun
module de previz. Un module de tri qui importerait la CLI ne serait pas
reutilisable par la GUI, ce qui est litteralement l'objet de l'arbitrage.

Il ne connait pas non plus **l'argument de slug de lot** de la CLI (AC 13), et
son nom exact n'apparait nulle part dans ce fichier -- la frontiere est mesuree
par un balayage litteral, docstrings comprises. Le regime -- « une pile, un lot
promis » contre « range-moi ce vrac » -- se decide chez l'**appelant**, qui
choisit d'appeler ce module ou pas. Le tri, lui, ne sait pas qu'un tel argument
existe : sans cette frontiere, la fonction du coeur redeviendrait un geste de
CLI.

La partition, en quatre classes disjointes
------------------------------------------
Toute page ingeree appartient a **exactement une** classe. Rien ne disparait,
rien n'est compte deux fois :

1. **un lot** -- la page porte une identite de lot complete, du projet courant ;
2. **la calibration** -- la page declare le role `c`. Elle n'appartient a aucun
   lot, et le tri ne lui en invente pas un ;
3. **le reliquat** -- « je n'ai pas su te rattacher ». QR muet, payload refuse,
   identite de lot incomplete. C'est ce que la zone tampon de l'Epic 7 « garde
   visible » ;
4. **le hors-perimetre** -- « tu n'es pas ici chez toi ». La planche porte un
   `project_id` etranger au projet courant. Le vrac est **au sein d'un meme
   projet** (`EPIC5-ARB-105`) : cette page n'est pas un reliquat a trier, elle
   est refusee **page par page** -- un vrac de 300 pages dont 2 sont etrangeres
   range les 298 autres --, avec son motif **et le projet a utiliser**.

Les deux dernieres ne se melangent jamais, et le module le rend verifiable : les
deux vocabulaires de motif sont **disjoints par construction**, garde posee a
l'import. Les confondre ferait chercher l'operateur au mauvais endroit.

Rien ne bouge sur le disque
---------------------------
`EPIC5-ARB-108`. Un scan est souvent un PDF de cinquante pages : si la page 37 ne
se rattache a aucun lot, elle **n'est pas un fichier**, c'est une page a
l'interieur d'un fichier. La deplacer voudrait dire **en fabriquer un**. Le
reliquat est donc une **liste** -- « document X, page 37, motif » --, et le
hors-perimetre aussi.

Le rang de lecture n'apparie jamais
-----------------------------------
Regle des fabriques du depot, et terrain exact des defauts `M33` (5.6), `M25`
(5.7) et des cinq survivants de 5.8 : **le role se lit dans le payload,
l'appartenance se lit dans le payload**, jamais au rang ni a la position dans la
pile. L'ordre d'arrivee n'a aucun effet sur la partition -- l'ordre de sortie est
derive du **contenu** (identite de lot, puis localisateur), jamais de l'ordre
d'entree.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Protocol

from . import page_roles
from .io import reconstruction

# ---------------------------------------------------------------------------
# Vocabulaires fermes de motif -- deux familles, jamais confondues (AC 4)
# ---------------------------------------------------------------------------

#: Le QR n'a rien livre : symbole absent, illisible, ou plusieurs symboles. La
#: page est presente sur la vitre, son identite est inconnue. C'est le cas exact
#: de la zone tampon : une **absence visible**, jamais un echec de passe.
RELIQUAT_QR_MUET = "reliquat-qr-absent-ou-illisible"

#: Le QR a livre quelque chose que `io.payload.validate_payload` a refuse --
#: planche perimee (`1.0`), page de calibration imprimee avant la story 5.23,
#: champ abime. Le motif de refus voyage dans le `detail` de l'entree : c'est lui
#: qui porte deja la phrase actionnable (reimprimer, rescanner).
RELIQUAT_PAYLOAD_REFUSE = "reliquat-payload-refuse"

#: Le payload a ete lu, la page n'est pas une page de calibration, et pourtant
#: elle ne porte pas l'identite de lot complete que
#: `io.reconstruction._LOT_LEVEL_FIELDS` exige. Aucun lot du projet courant ne
#: peut donc la reclamer : c'est le « lot inconnu du projet courant » de
#: l'AC 4.
RELIQUAT_LOT_INCONNU = "reliquat-lot-inconnu-du-projet-courant"

#: Une page de calibration lue mais **inexploitable** : monochrome, non
#: redressable, ajustement en echec. Elle ne produit aucun profil, elle va au
#: reliquat avec son motif, et **elle ne contamine le verdict d'aucun lot de la
#: passe** (AC 7). Ce motif-la n'est pas pose par le tri lui-meme -- qui ne lit
#: aucun pixel -- mais par l'appelant, apres la consignation, via
#: :func:`avec_entrees_de_reliquat`.
RELIQUAT_CALIBRATION_INEXPLOITABLE = "reliquat-page-de-calibration-inexploitable"

#: Deux pages de calibration de la **meme passe** portent le **meme libelle de
#: chaine**. Le nom du profil vient du libelle, donc les deux viseraient le
#: **meme fichier** : consigner la seconde detruirait la premiere, en silence,
#: et le rapport annoncerait deux profils la ou un seul existerait -- ce que
#: l'AC 10 interdit nommement (« ce nom est celui du fichier reellement ecrit
#: sur le disque »).
#:
#: Trouve par la revue de vague (couche 2). La redaction d'origine affirmait
#: « le libelle, lui, vient de la feuille et les distingue » -- vrai quand les
#: libelles different, et rien ne le verifiait. Une meme feuille scannee deux
#: fois, ou une chaine dont l'etiquette a ete reimprimee, suffit.
#:
#: La reponse est celle que l'AC 7 prescrit deja pour une page qu'on ne peut
#: pas consigner : **la premiere est consignee, la seconde va au reliquat avec
#: ce motif**, et le verdict des lots de la passe n'en depend pas. On ne
#: renomme pas d'office (inventer un suffixe fabriquerait une chaine qui
#: n'existe pas) et on ne refuse pas la passe entiere (l'echec d'une feuille
#: reste local, AC 7).
RELIQUAT_CALIBRATION_LIBELLE_EN_DOUBLE = (
    "reliquat-page-de-calibration-libelle-en-double")

#: Vocabulaire **ferme** du reliquat.
MOTIFS_DE_RELIQUAT: tuple[str, ...] = (
    RELIQUAT_QR_MUET,
    RELIQUAT_PAYLOAD_REFUSE,
    RELIQUAT_LOT_INCONNU,
    RELIQUAT_CALIBRATION_INEXPLOITABLE,
    RELIQUAT_CALIBRATION_LIBELLE_EN_DOUBLE,
)

#: La planche porte un `project_id` etranger au projet courant. Elle n'est pas
#: un reliquat a trier : elle n'a rien a faire dans cette passe.
HORS_PERIMETRE_PROJET_ETRANGER = "hors-perimetre-projet-etranger"

#: Vocabulaire **ferme** du hors-perimetre.
MOTIFS_HORS_PERIMETRE: tuple[str, ...] = (HORS_PERIMETRE_PROJET_ETRANGER,)

# **Garde a l'import, et elle n'est pas decorative** (`EPIC5-ARB-105`, frontiere
# negative de l'AC 4) : les deux familles ne partagent aucun code. Un code de
# reliquat porte par une entree hors perimetre -- ou l'inverse -- ferait chercher
# l'operateur au mauvais endroit, defaut deja paye trois fois dans ce depot. La
# garde est ici plutot que dans un test parce qu'un vocabulaire qui se recouvre
# ne doit pas pouvoir seulement etre importe.
if set(MOTIFS_DE_RELIQUAT) & set(MOTIFS_HORS_PERIMETRE):  # pragma: no cover
    raise RuntimeError(
        "scan_sorting: les vocabulaires du reliquat et du hors-perimetre se "
        "recouvrent. Ce sont deux choses differentes dites a l'operateur, et "
        "les confondre l'enverrait chercher au mauvais endroit."
    )


class ScanSortingError(RuntimeError):
    """Base attrapable des refus du tri."""


# ---------------------------------------------------------------------------
# Ce que le tri consomme, et ce qu'il rend
# ---------------------------------------------------------------------------


class PageDetecteeLike(Protocol):
    """Les cinq attributs que le tri lit d'une page detectee.

    Un **protocole** plutot qu'un import de `scan_detection` : le tri n'a besoin
    ni de cv2, ni de numpy, ni d'une geometrie : cinq champs suffisent. Un
    `scan_detection.DetectedPage` les porte tous et passe donc tel quel ; une GUI
    ou un test peuvent passer :class:`PageAtrier`.
    """

    read_rank: int
    locator_source: str
    locator_page_index: int | None
    payload: dict | None
    refusal_reason: str | None


@dataclass(frozen=True)
class PageAtrier:
    """Une page a trier, reduite a ce que le tri lit d'elle.

    Utile aux tests et a tout appelant qui n'a pas de `DetectedPage` sous la
    main -- le tri s'appelle alors sans projet, sans disque et sans CLI.
    """

    read_rank: int
    locator_source: str
    locator_page_index: int | None = None
    payload: dict | None = None
    refusal_reason: str | None = None


@dataclass(frozen=True)
class Localisateur:
    """Ou retrouver une page, sans supposer qu'elle existe comme fichier.

    **Le meme couple que celui du rapport d'ingestion** (`scan_ingest.PageLocator`)
    -- `(chemin relatif de la source, index de page)`, l'index valant `None` pour
    une page-fichier --, jamais un second identifiant invente : c'est exactement
    l'identifiant dont le reliquat a besoin pour nommer une page qui n'existe
    comme fichier nulle part.

    Redeclare ici plutot qu'importe pour garder le module libre de tout import
    lourd ; la **forme de document** est identique, ce qui est ce qui compte pour
    un consommateur.
    """

    source_path: str
    page_index: int | None = None

    def as_document(self) -> dict:
        return {"source_path": self.source_path, "page_index": self.page_index}

    @classmethod
    def from_document(cls, document: dict) -> "Localisateur":
        return cls(
            source_path=str(document["source_path"]),
            page_index=document.get("page_index"),
        )


@dataclass(frozen=True)
class PageRangee:
    """Une page que le tri a su placer -- dans un lot ou dans la calibration."""

    read_rank: int
    locator: Localisateur
    payload: dict

    @property
    def page_index(self) -> int | None:
        return self.payload.get("page_index")

    @property
    def scan_chain_label(self) -> str | None:
        """Le libelle de chaine, porte par les seules pages de calibration."""
        return self.payload.get("scan_chain_label")


@dataclass(frozen=True)
class LotTrie:
    """Un lot reconstitue par le tri, avec **ses propres** pages."""

    project_id: str
    rush_id: str
    lot_id: str
    pages: tuple[PageRangee, ...]

    @property
    def identite(self) -> tuple[str, str, str]:
        return (self.project_id, self.rush_id, self.lot_id)


@dataclass(frozen=True)
class EntreeDeReliquat:
    """« Je n'ai pas su te rattacher » -- avec son localisateur et son motif."""

    read_rank: int
    locator: Localisateur
    motif: str
    detail: str | None = None


@dataclass(frozen=True)
class EntreeHorsPerimetre:
    """« Tu n'es pas ici chez toi » -- avec son motif **et le projet a utiliser**.

    La seconde moitie est la moitie decisive (`EPIC5-ARB-105`) : le projet a
    utiliser est lu dans le `project_id` du QR de la page, **qui le porte**.
    L'operateur ne doit pas avoir a le deviner, et ce n'est jamais une constante.
    """

    read_rank: int
    locator: Localisateur
    motif: str
    projet_a_utiliser: str | None


@dataclass(frozen=True)
class PartitionDeVrac:
    """La partition, en quatre classes totales et disjointes."""

    lots: tuple[LotTrie, ...] = ()
    pages_de_calibration: tuple[PageRangee, ...] = ()
    reliquat: tuple[EntreeDeReliquat, ...] = ()
    hors_perimetre: tuple[EntreeHorsPerimetre, ...] = ()

    @property
    def cardinal_des_pages_de_lot(self) -> int:
        return sum(len(lot.pages) for lot in self.lots)

    @property
    def cardinal_total(self) -> int:
        """Le nombre de pages ingerees que cette partition porte.

        La somme des **quatre** classes, et c'est l'AC 4 : elle doit egaler le
        nombre de pages ingerees. Un cardinal juste ne suffit pourtant pas --
        deux pages echangees entre deux classes le laisseraient juste --, d'ou
        :meth:`localisateurs_par_classe`, qui rend l'inventaire nominatif.
        """
        return (
            self.cardinal_des_pages_de_lot
            + len(self.pages_de_calibration)
            + len(self.reliquat)
            + len(self.hors_perimetre)
        )

    def localisateurs_par_classe(self) -> dict[str, tuple[Localisateur, ...]]:
        """L'inventaire **nominatif** des quatre classes.

        Ce que le cardinal ne dit pas : quelle page est ou. C'est par lui que se
        verifie la disjonction, jamais par un compte.
        """
        return {
            "lots": tuple(
                page.locator for lot in self.lots for page in lot.pages
            ),
            "calibration": tuple(page.locator for page in self.pages_de_calibration),
            "reliquat": tuple(entree.locator for entree in self.reliquat),
            "hors_perimetre": tuple(entree.locator for entree in self.hors_perimetre),
        }


# ---------------------------------------------------------------------------
# Le tri
# ---------------------------------------------------------------------------


def _localisateur(page: PageDetecteeLike) -> Localisateur:
    return Localisateur(
        source_path=page.locator_source,
        page_index=page.locator_page_index,
    )


def porte_une_identite_de_lot(payload: dict[str, Any]) -> bool:
    """Ce payload porte-t-il l'identite de lot complete ?

    **La partition n'est pas redigee ici** : elle est celle de
    `io.reconstruction._partition_de_la_pile`, qui la **possede** depuis
    `EPIC5-ARB-92` (« deux partitions, ce sont deux verites sur la meme pile »).
    On l'appelle page par page -- une pile d'un seul element --, ce qui a un
    avantage propre au terrain de cette story : aucun appariement positionnel
    entre une entree et une sortie de liste, donc aucune prise pour la famille de
    defauts `M33`/`M25`.
    """
    sans_identite, porteuses = reconstruction._partition_de_la_pile([payload])
    return bool(porteuses) and not sans_identite


def est_une_page_de_calibration(payload: dict[str, Any]) -> bool:
    """Le role se lit **dans le payload**, jamais au rang (AC 3).

    Lecture directe du champ, sans defaut de relecture : une page dont le role
    n'est pas declare `c` est une planche d'images pour tout le reste du depot
    (`io.reconstruction.PAGE_ROLE_DEFAULT_AT_REREAD`), et la deduire de l'absence
    des champs de lot ferait passer un payload **tronque** de planche pour une
    page de calibration -- c'est-a-dire transformer une corruption en regime
    nominal (`io.payload._is_calibration_page` dit exactement cela).
    """
    return payload.get("page_role") == page_roles.PAGE_ROLE_CALIBRATION


def _cle_de_page(locator: Localisateur, page_index: object) -> tuple:
    """La cle d'ordre d'une page, derivee de son **contenu**.

    Elle ne contient ni le rang de lecture ni la position d'arrivee : c'est ce
    qui rend la partition identique sous permutation du vrac (AC 3). Le couple
    `(chemin, index dans la source)` est unique par page ingeree, donc la cle est
    un ordre total.
    """
    index = page_index if isinstance(page_index, int) else -1
    dans_la_source = locator.page_index if locator.page_index is not None else -1
    return (index, locator.source_path, dans_la_source)


def lots_adoptes_du_manifest(manifest) -> dict[str, str]:
    """Les lots **adoptes** d'un manifest, par `lot_id` -> projet d'origine.

    `EPIC7-ARB-101`. Un manifest sans lot adopte -- c'est-a-dire tout manifest
    d'avant cet arbitrage, et la grande majorite des autres -- rend un
    dictionnaire vide : le champ est additif, son absence est le cas nominal.

    **Lu ici et pas dans le tri** pour que le tri reste ce qu'il est : une
    fonction qui n'ouvre aucun fichier et ne connait aucun format de manifest
    (`EPIC5-ARB-108`). Elle recoit une correspondance deja resolue, comme elle
    recoit deja `project_id_courant`.
    """
    if not isinstance(manifest, Mapping):
        return {}
    adoptes: dict[str, str] = {}
    for lot in manifest.get("lots") or ():
        if not isinstance(lot, Mapping):
            continue
        lot_id = lot.get("lot_id")
        origine = lot.get(reconstruction.CHAMP_ORIGINE_ADOPTEE)
        if isinstance(lot_id, str) and isinstance(origine, str) and origine:
            adoptes[lot_id] = origine
    return adoptes


def trier_les_pages(
    pages: Iterable[PageDetecteeLike],
    *,
    project_id_courant: str,
    lots_adoptes: Mapping[str, str] | None = None,
) -> PartitionDeVrac:
    """Ranger un vrac de pages detectees en quatre classes disjointes.

    Aucun fichier n'est ouvert, aucun n'est cree, deplace, copie ou efface
    (`EPIC5-ARB-108`). Aucun projet n'est requis : `project_id_courant` est
    l'identifiant lu **au manifest du projet**, jamais derive d'un nom de dossier
    ni d'un slug operateur.

    `lots_adoptes` associe un `lot_id` a son projet d'origine, tel que
    :func:`lots_adoptes_du_manifest` le rend. C'est la seconde moitie
    d'`EPIC7-ARB-101` : « le papier continue de dire son projet d'origine, et il
    le dira toujours -- l'encre ne se met pas a jour ». Sans cette
    correspondance, chaque nouvelle feuille d'un lot deja adopte repartirait
    hors perimetre et il faudrait re-adopter a chaque passe. Elle est
    **etroite** a dessein : c'est le couple `(lot_id, projet d'origine)` qui
    ouvre le perimetre, pas le projet d'origine tout seul -- adopter un lot de
    `projet_demo` ne fait pas entrer toutes les autres feuilles de `projet_demo`
    dans ce projet.

    L'ordre de classement, et il est l'ossature de la fonction :

    0. la page n'a livre **aucun** payload -> reliquat (`RELIQUAT_QR_MUET` si le
       QR n'a rien rendu, `RELIQUAT_PAYLOAD_REFUSE` quand un motif de refus est
       porte) ;
    1. le payload declare le role `c` -> classe **calibration**. Ce test passe
       **avant** le controle de projet, et ce n'est pas un ordre commode : une
       page de calibration ne porte **aucun** `project_id`
       (`io.payload.CALIBRATION_ABSENT_FIELDS`, 2026-08-18) et « aucune machine
       n'a le droit de lire celui-la pour decider ». Une garde qui chercherait un
       projet sur cette feuille serait exactement la garde que ce retrait existe
       pour interdire ;
    2. la planche declare un `project_id` etranger -> **hors-perimetre**, avec le
       projet a utiliser lu sur son propre QR -- **sauf** si son lot a ete
       ADOPTE par ce projet et vient bien de ce projet-la (`EPIC7-ARB-101`) ;
    3. la planche porte l'identite de lot complete -> **son** lot ;
    4. sinon -> reliquat (`RELIQUAT_LOT_INCONNU`).
    """
    if not isinstance(project_id_courant, str) or not project_id_courant.strip():
        raise ScanSortingError(
            "Le tri par QR a besoin de l'identifiant du projet courant, lu au "
            "manifest du projet. Sans lui, aucune page ne peut etre declaree "
            "hors perimetre, et le vrac cesserait d'etre borne a un projet "
            "(EPIC5-ARB-105)."
        )

    adoptes = dict(lots_adoptes or {})
    pages_par_lot: dict[tuple[str, str, str], list[tuple[tuple, PageRangee]]] = {}
    calibration: list[tuple[tuple, PageRangee]] = []
    reliquat: list[tuple[tuple, EntreeDeReliquat]] = []
    hors_perimetre: list[tuple[tuple, EntreeHorsPerimetre]] = []

    for page in pages:
        locator = _localisateur(page)
        payload = page.payload

        if payload is None:
            motif = (
                RELIQUAT_PAYLOAD_REFUSE
                if getattr(page, "refusal_reason", None)
                else RELIQUAT_QR_MUET
            )
            reliquat.append((
                _cle_de_page(locator, None),
                EntreeDeReliquat(
                    read_rank=page.read_rank,
                    locator=locator,
                    motif=motif,
                    detail=getattr(page, "refusal_reason", None),
                ),
            ))
            continue

        cle = _cle_de_page(locator, payload.get("page_index"))
        rangee = PageRangee(
            read_rank=page.read_rank, locator=locator, payload=payload
        )

        if est_une_page_de_calibration(payload):
            calibration.append((cle, rangee))
            continue

        projet_de_la_page = payload.get("project_id")
        # **Un lot ADOPTE n'est plus hors perimetre** (`EPIC7-ARB-101`), a la
        # condition stricte qu'il vienne du projet que l'adoption a enregistre.
        # Comparer le seul `lot_id` suffirait a faire entrer une feuille d'un
        # troisieme projet qui porterait par hasard le meme identifiant de lot :
        # c'est le couple qui ouvre le perimetre.
        deja_adopte = (
            adoptes.get(payload.get("lot_id")) == projet_de_la_page
            and projet_de_la_page is not None
        )
        if projet_de_la_page != project_id_courant and not deja_adopte:
            hors_perimetre.append((
                cle,
                EntreeHorsPerimetre(
                    read_rank=page.read_rank,
                    locator=locator,
                    motif=HORS_PERIMETRE_PROJET_ETRANGER,
                    projet_a_utiliser=projet_de_la_page,
                ),
            ))
            continue

        if not porte_une_identite_de_lot(payload):
            reliquat.append((
                cle,
                EntreeDeReliquat(
                    read_rank=page.read_rank,
                    locator=locator,
                    motif=RELIQUAT_LOT_INCONNU,
                    detail=getattr(page, "refusal_reason", None),
                ),
            ))
            continue

        # **`.get()` et non un acces indexe nu**, exactement pour le motif que
        # `scan_detection._detect_one_page` a ecrit avant nous : la garde qui
        # precede (`porte_une_identite_de_lot`) garantit deja les onze champs de
        # niveau lot, donc ce `.get()` ne peut pas masquer un payload tronque --
        # il aurait ete ecarte au reliquat une ligne plus haut. Un acces nu ici
        # serait le septieme de la famille que `test_pile_mixte_refus` balaie.
        # **Le projet d'une page adoptee est celui d'ACCUEIL**, pas celui que
        # son papier declare (`EPIC7-ARB-101`). Garder l'origine ici rangerait
        # la feuille sous une identite de lot differente de celle des feuilles
        # du meme lot arrivees par une autre passe : deux lots du meme nom dans
        # la meme partition, ce que rien en aval ne saurait reconcilier.
        identite = (
            project_id_courant if deja_adopte else payload.get("project_id"),
            payload.get("rush_id"),
            payload.get("lot_id"),
        )
        pages_par_lot.setdefault(identite, []).append((cle, rangee))

    lots = tuple(
        LotTrie(
            project_id=identite[0],
            rush_id=identite[1],
            lot_id=identite[2],
            pages=tuple(page for _, page in sorted(entrees, key=lambda e: e[0])),
        )
        for identite, entrees in sorted(pages_par_lot.items(), key=lambda e: e[0])
    )
    return PartitionDeVrac(
        lots=lots,
        pages_de_calibration=tuple(
            page for _, page in sorted(calibration, key=lambda e: e[0])),
        reliquat=tuple(
            entree for _, entree in sorted(reliquat, key=lambda e: e[0])),
        hors_perimetre=tuple(
            entree for _, entree in sorted(hors_perimetre, key=lambda e: e[0])),
    )


def avec_entrees_de_reliquat(
    partition: PartitionDeVrac,
    entrees: Iterable[EntreeDeReliquat],
) -> PartitionDeVrac:
    """Verser des entrees supplementaires au reliquat, **sans muter** la partition.

    Un seul appelant legitime, et il est nomme : la consignation d'une page de
    calibration (AC 7). Une feuille de calibration monochrome, illisible ou non
    redressable n'est reconnaissable qu'apres avoir lu ses pixels -- ce que le
    tri ne fait pas --, et elle doit alors quitter la classe calibration pour le
    reliquat, **avec son motif**, sans contaminer le verdict d'aucun lot.

    Les entrees versees restent triees sur la meme cle de contenu que le reste :
    l'ordre du reliquat ne depend jamais de l'ordre dans lequel on l'a rempli.
    """
    entrees = tuple(entrees)
    for entree in entrees:
        if entree.motif not in MOTIFS_DE_RELIQUAT:
            raise ScanSortingError(
                f"Motif de reliquat inconnu: {entree.motif!r}. Le vocabulaire "
                f"est ferme ({', '.join(MOTIFS_DE_RELIQUAT)})."
            )
    deplaces = {entree.locator for entree in entrees}
    calibration_restante = tuple(
        page for page in partition.pages_de_calibration
        if page.locator not in deplaces
    )
    fusion = sorted(
        (*partition.reliquat, *entrees),
        key=lambda entree: _cle_de_page(entree.locator, None),
    )
    return replace(
        partition,
        pages_de_calibration=calibration_restante,
        reliquat=tuple(fusion),
    )


# ---------------------------------------------------------------------------
# Le rapport de tri -- un document, consommable par la CLI comme par la GUI
# ---------------------------------------------------------------------------

#: Version du contrat du rapport de tri. Distincte de `PAYLOAD_SCHEMA_VERSION`
#: (le contrat du QR, que cette story ne touche pas) et du schema du manifest :
#: trois artefacts versionnes, deliberement pas confondus.
RAPPORT_DE_TRI_VERSION = "tri-1"


@dataclass(frozen=True)
class ProfilCree:
    """Un profil de calibration consigne par la passe de vrac (AC 7 et 10).

    **Il est cree, il n'est pas designe** (`EPIC5-ARB-107`) : aucun lot n'est
    corrige par lui du seul fait qu'il etait dans la pile, et il n'est pose en
    defaut d'aucun projet. Le rapport le **nomme** pour que l'operateur puisse
    le renommer ensuite -- c'est ce qui rend acceptable qu'une passe hors
    terminal ait choisi son nom toute seule.
    """

    chain_id: str
    etiquette: str
    #: Chemin **relatif au projet**, jamais absolu : un rapport qui porterait le
    #: chemin de la machine qui l'a produit ne se relit pas ailleurs (AC 10).
    chemin_relatif: str
    #: Le localisateur de la feuille qui a produit ce profil : c'est ce qui
    #: rattache un profil a une page du vrac, jamais un rang.
    locator: Localisateur


@dataclass(frozen=True)
class RapportDeTri:
    """Ce que la passe de vrac a range, motive et cree.

    **Un document separe** du rapport d'ingestion (`scans/<slug>/ingest.json`,
    story 5.1, ni modifie ni remplace) et du document de detection (contrat de
    5.25, auquel **aucun champ n'est ajoute** pour le vrac -- AC 13). Trois
    documents, trois sujets.

    Il porte les **quatre** classes, les motifs des deux dernieres, le projet a
    utiliser pour chaque entree hors perimetre, les localisateurs, et les profils
    crees par la passe avec leur nom.
    """

    ingest_slug: str
    project_id: str
    partition: PartitionDeVrac
    profils_crees: tuple[ProfilCree, ...] = ()
    version: str = RAPPORT_DE_TRI_VERSION


def rapport_to_json_dict(rapport: RapportDeTri) -> dict:
    """Le rapport, en structures JSON pures.

    Aucun type propre a la CLI n'y entre -- ni `Namespace`, ni `Path`, ni chemin
    absolu de la machine : la GUI de l'Epic 7 consomme le meme document que
    l'affichage de la CLI, et un document qui ne se relit que sur la machine qui
    l'a ecrit ne serait pas ce document-la.
    """
    return {
        "version": rapport.version,
        "ingest_slug": rapport.ingest_slug,
        "project_id": rapport.project_id,
        "lot_count": len(rapport.partition.lots),
        "page_count": rapport.partition.cardinal_total,
        "lots": [
            {
                "project_id": lot.project_id,
                "rush_id": lot.rush_id,
                "lot_id": lot.lot_id,
                "pages": [
                    {
                        "read_rank": page.read_rank,
                        "locator": page.locator.as_document(),
                        "page_index": page.page_index,
                    }
                    for page in lot.pages
                ],
            }
            for lot in rapport.partition.lots
        ],
        "calibration": [
            {
                "read_rank": page.read_rank,
                "locator": page.locator.as_document(),
                "scan_chain_label": page.scan_chain_label,
            }
            for page in rapport.partition.pages_de_calibration
        ],
        "reliquat": [
            {
                "read_rank": entree.read_rank,
                "locator": entree.locator.as_document(),
                "motif": entree.motif,
                "detail": entree.detail,
            }
            for entree in rapport.partition.reliquat
        ],
        "hors_perimetre": [
            {
                "read_rank": entree.read_rank,
                "locator": entree.locator.as_document(),
                "motif": entree.motif,
                "projet_a_utiliser": entree.projet_a_utiliser,
            }
            for entree in rapport.partition.hors_perimetre
        ],
        "profils_crees": [
            {
                "chain_id": profil.chain_id,
                "etiquette": profil.etiquette,
                "chemin_relatif": profil.chemin_relatif,
                "locator": profil.locator.as_document(),
            }
            for profil in rapport.profils_crees
        ],
        "vocabulaire_reliquat": list(MOTIFS_DE_RELIQUAT),
        "vocabulaire_hors_perimetre": list(MOTIFS_HORS_PERIMETRE),
    }


def rapport_from_json_dict(document: dict) -> RapportDeTri:
    """Relire un rapport de tri ecrit par :func:`rapport_to_json_dict`.

    L'aller-retour est sans perte **sur ce que le rapport porte** : les payloads
    complets des pages de lot n'y entrent pas -- ils vivent dans le document de
    detection, qui est leur sujet --, seuls leur localisateur et leur index de
    page y sont. Un rapport relu porte donc des `PageRangee` dont le payload est
    reduit a `page_index`, ce que la relecture declare plutot que de le laisser
    croire complet.
    """
    version = document.get("version")
    if version != RAPPORT_DE_TRI_VERSION:
        raise ScanSortingError(
            f"Rapport de tri de version {version!r}, attendue "
            f"{RAPPORT_DE_TRI_VERSION!r}. Il n'existe pas de lecteur bi-format."
        )
    lots = tuple(
        LotTrie(
            project_id=lot["project_id"],
            rush_id=lot["rush_id"],
            lot_id=lot["lot_id"],
            pages=tuple(
                PageRangee(
                    read_rank=page["read_rank"],
                    locator=Localisateur.from_document(page["locator"]),
                    payload={"page_index": page["page_index"]},
                )
                for page in lot["pages"]
            ),
        )
        for lot in document["lots"]
    )
    calibration = tuple(
        PageRangee(
            read_rank=page["read_rank"],
            locator=Localisateur.from_document(page["locator"]),
            payload={
                "page_role": page_roles.PAGE_ROLE_CALIBRATION,
                "scan_chain_label": page["scan_chain_label"],
            },
        )
        for page in document["calibration"]
    )
    reliquat = tuple(
        EntreeDeReliquat(
            read_rank=entree["read_rank"],
            locator=Localisateur.from_document(entree["locator"]),
            motif=entree["motif"],
            detail=entree.get("detail"),
        )
        for entree in document["reliquat"]
    )
    hors_perimetre = tuple(
        EntreeHorsPerimetre(
            read_rank=entree["read_rank"],
            locator=Localisateur.from_document(entree["locator"]),
            motif=entree["motif"],
            projet_a_utiliser=entree.get("projet_a_utiliser"),
        )
        for entree in document["hors_perimetre"]
    )
    return RapportDeTri(
        ingest_slug=document["ingest_slug"],
        project_id=document["project_id"],
        partition=PartitionDeVrac(
            lots=lots,
            pages_de_calibration=calibration,
            reliquat=reliquat,
            hors_perimetre=hors_perimetre,
        ),
        profils_crees=tuple(
            ProfilCree(
                chain_id=profil["chain_id"],
                etiquette=profil["etiquette"],
                chemin_relatif=profil["chemin_relatif"],
                locator=Localisateur.from_document(profil["locator"]),
            )
            for profil in document["profils_crees"]
        ),
        version=version,
    )


__all__ = [
    "EntreeDeReliquat",
    "EntreeHorsPerimetre",
    "HORS_PERIMETRE_PROJET_ETRANGER",
    "Localisateur",
    "LotTrie",
    "MOTIFS_DE_RELIQUAT",
    "MOTIFS_HORS_PERIMETRE",
    "PageAtrier",
    "PageRangee",
    "PartitionDeVrac",
    "ProfilCree",
    "RAPPORT_DE_TRI_VERSION",
    "RELIQUAT_CALIBRATION_INEXPLOITABLE",
    "RELIQUAT_CALIBRATION_LIBELLE_EN_DOUBLE",
    "est_une_page_de_calibration",
    "RELIQUAT_LOT_INCONNU",
    "RELIQUAT_PAYLOAD_REFUSE",
    "RELIQUAT_QR_MUET",
    "RapportDeTri",
    "ScanSortingError",
    "avec_entrees_de_reliquat",
    "porte_une_identite_de_lot",
    "rapport_from_json_dict",
    "rapport_to_json_dict",
    "lots_adoptes_du_manifest",
    "trier_les_pages",
]
