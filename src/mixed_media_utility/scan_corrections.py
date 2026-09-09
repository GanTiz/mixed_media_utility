# -*- coding: utf-8 -*-
"""Couche de correction manuelle du document de detection (story 7.5).

`EPIC7-ARB-95`, regime **A** : la correction que l'operatrice porte a la main
est une **couche additive** du document de detection. Elle vit sous une cle
neuve, :data:`CLE_DOCUMENT`, et ne touche ni les pages, ni les compteurs, ni
``fingerprints.detection``.

**Pourquoi l'empreinte ne bouge pas, et ce n'est pas une commodite.**
``fingerprints.detection`` n'est pas une somme de controle : c'est une
**identite**. ``gui.coquille._document_de_detection`` retrouve un document par
elle, et ``gui.modele_chutier`` la met dans l'identifiant de **chaque noeud du
chutier** (``{lot_id}#{empreinte}#rang-{read_rank}``). La re-signer
renommerait tous les noeuds du lot a la premiere correction.

L'empreinte continue donc de signer **ce que la machine a lu**. Ce que
l'operatrice a corrige vit a cote, et les deux restent distinguables --
c'est ce qu'une reecriture complete aurait perdu.

**Mesure qui fonde le regime** : ``scan_previz.scan_previz_from_json_dict``
relit un document portant cette cle et rend un objet **egal** a celui d'avant
(banc ``test_scan_corrections.py``). La couche est donc invisible pour tout
lecteur d'aujourd'hui, y compris la GUI de 7.4.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import layout, page_templates, previz_common, scan_detect

#: La cle additive, au sommet du document. Nom **anglais**, comme tout le
#: vocabulaire de ce document (`frame_zones_px`, `refusal_code`) : le fichier
#: est un artefact de coeur, pas une surface d'interface.
CLE_DOCUMENT = "manual_corrections"

#: Version de la couche, pour qu'un lecteur futur sache ce qu'il lit sans
#: deviner. Elle est **independante** de `previz_schema_version` : la couche
#: peut evoluer sans toucher a l'enveloppe du document.
#: Version **1**, celle du levier par ZONES (`crop_rect_px`). **Le levier
#: n'existe plus** -- `EPIC7-ARB-102` l'a retire, lecteur et ecrivain compris --
#: mais la constante reste, et c'est deliberé : des documents portant cette
#: couche ont pu etre ecrits par la vague 4 avant l'arbitrage. Sans elle,
#: `lire_les_coins` les refuserait sur un `schema` inconnu et l'operatrice
#: lirait un message qui ne dit pas ce qui s'est passe. Avec elle, le refus
#: NOMME l'arbitrage et dit quoi refaire.
SCHEMA_DE_CORRECTION_V1 = "manual-corrections-v1"

#: Version **2**, celle du levier par COINS ArUco (`EPIC7-ARB-102`).
SCHEMA_DE_CORRECTION = "manual-corrections-v2"

def _entier(valeur: object, cle: str) -> int:
    """Un entier, et **pas un booleen**.

    ``bool`` est un ``int`` en Python : le laisser passer ecrirait un rang de
    lecture 1 pour ``True``, silencieusement.
    """
    if not isinstance(valeur, int) or isinstance(valeur, bool):
        raise CorrectionInvalide(
            f"le champ {cle!r} d'une correction est un entier, recu {valeur!r}"
        )
    return valeur


class CorrectionInvalide(ValueError):
    """Une couche de correction que ce lecteur refuse de lire.

    Refusee, jamais reparee ni devinee : c'est la meme doctrine que
    `scan_previz_from_json_dict`. Une correction alteree qu'on rattraperait en
    silence decouperait des pixels ailleurs que la ou l'operatrice a montre.
    """


def ecrire(chemin: Path | str, document: dict) -> None:
    """Ecrire le document, **canoniquement** et **atomiquement**.

    Deux reutilisations, pas une seule, et c'est la seconde qui portait le vrai
    risque :

    1. **le serialiseur** est `previz_common.canonical_json`, le point unique
       de canonicalisation du depot (`separators=(",",":")`,
       `ensure_ascii=True`, `sort_keys=True`, `allow_nan=False`, aucune
       indentation, aucun saut de ligne final). C'est **exactement** ce que le
       producteur ecrit dans ce meme fichier (`scan_detect`, deux sites). En
       poser un second ici -- un `json.dumps` indente -- ferait deux recettes
       de la meme garantie **sur le meme fichier** : un document jamais
       corrige ressortait a 189 octets la ou le coeur en avait ecrit 125, ce
       qui viole verbatim l'interdit de `EPIC7-ARB-95` (« aucune reecriture
       gratuite ») et fait mentir l'unicite que
       `previz_common.canonical_json` revendique dans sa propre docstring.
       Effet de bord ferme au passage : sans saut de ligne final, la traduction
       `\\n` -> `\\r\\n` du mode texte de l'ecrivain n'a plus de prise sous
       Windows ;
    2. **l'ecrivain atomique** est celui du depot
       (`scan_detect.ecrire_document_json_atomiquement`, temporaire dans le
       meme dossier puis `os.replace`). C'est le seul fichier qui porte le
       travail de jugement de l'operatrice : une interruption ne doit jamais le
       laisser tronque.
    """
    texte = previz_common.canonical_json(document)
    scan_detect.ecrire_document_json_atomiquement(Path(chemin), texte)


# ---------------------------------------------------------------------------
# EPIC7-ARB-102 -- les coins corriges, seconde cle de la meme couche
# ---------------------------------------------------------------------------
#
# La couche `manual_corrections` portait des RECTANGLES (`crop_rect_px`). Ce
# levier est retire : les rectangles viennent du gabarit, jamais de la detection,
# donc les corriger ne redressait rien (demonstration et mesure dans
# `gui/reparation.py`, section `EPIC7-ARB-102`).
#
# Ce qu'elle porte desormais : les **quatre centres de marqueurs ArUco** que
# l'operatrice a repositionnes. C'est d'eux que l'homographie se deduit, donc le
# redressement, donc le contenu de chaque rectangle.
#
# **Le regime additif de `EPIC7-ARB-95` ne bouge pas d'un pouce** : la couche
# reste au sommet du document, `fingerprints.detection` continue de signer ce que
# la MACHINE a lu, et un document jamais corrige ressort octet pour octet comme
# il est entre.

#: Les CONTOURS corriges, dans le dialecte du document : une liste d'objets
#: `{marker_id, quad}`, ou `quad` porte quatre `[x, y]`. C'est la meme forme que
#: `scan_previz` publie pour `corner_quad_px` -- deux orthographes du meme
#: contour dans un meme fichier est precisement ce qui fait diverger deux
#: lecteurs.
CLE_COINS = "corner_quads_px"
CHAMPS_DE_COIN = ("marker_id", "quad")

#: Nombre de sommets d'un contour de marqueur. Ce n'est pas un reglage : ArUco
#: rend quatre coins, et trois n'en definissent pas un.
SOMMETS_PAR_CARRE = 4


def centre_du_carre(sommets) -> tuple[float, float]:
    """Le centre d'un marqueur, **deduit** de son contour : la moyenne.

    **Definition unique du depot**, et c'est tout l'interet de la poser ici :
    `detection.aruco.build_markers_document` calcule deja le centre ainsi
    (``points.mean(axis=0)``), l'interface l'affiche ainsi, et `scan-write`
    redresse avec. Une seconde definition -- centre du rectangle englobant,
    intersection des diagonales -- donnerait des centres legerement differents
    sur un marqueur vu de biais, et l'ecart ne se verrait que sur les pixels
    produits.

    Consequence voulue, et elle se mesure : un contour laisse intact redonne
    exactement le centre que la machine avait publie, donc ouvrir la reparation
    sans rien toucher ne deplace pas la page d'un pixel.
    """
    sommets = tuple(sommets)
    if len(sommets) != SOMMETS_PAR_CARRE:
        raise CorrectionInvalide(
            f"un contour de marqueur a {SOMMETS_PAR_CARRE} sommets, recu "
            f"{len(sommets)}"
        )
    return (
        sum(float(x) for x, _y in sommets) / SOMMETS_PAR_CARRE,
        sum(float(y) for _x, y in sommets) / SOMMETS_PAR_CARRE,
    )


def _nombre(valeur: object, cle: str) -> float:
    """Un nombre fini, et **pas un booleen**.

    Meme doctrine que `_entier` ci-dessus, et meme piege : `True` passerait pour
    l'abscisse 1. Les centres sont des flottants -- un centre de marqueur est un
    barycentre, il tombe entre deux pixels -- donc `int` est accepte et promu.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise CorrectionInvalide(
            f"le champ {cle!r} d'un coin corrige est un nombre, recu {valeur!r}"
        )
    valeur = float(valeur)
    if valeur != valeur or valeur in (float("inf"), float("-inf")):
        raise CorrectionInvalide(
            f"le champ {cle!r} d'un coin corrige est fini, recu {valeur!r}"
        )
    return valeur


@dataclass(frozen=True)
class CoinsCorriges:
    """Les quatre CARRES de marqueurs qu'une main a reposes, pour UNE planche.

    Ce qui est persiste est le **contour**, jamais le centre : c'est le contour
    que l'operatrice a pose -- « un humain ne sait pas viser le centre »
    (`EPIC7-ARB-102`) --, et le centre s'en deduit a chaque lecture. Ecrire le
    centre a la place perdrait le geste : on ne pourrait plus rouvrir la
    correction pour la retoucher, seulement la refaire.

    L'adresse est le seul `read_rank` : le redressement est une propriete de la
    **planche entiere**, pas d'un emplacement. C'est la difference d'adressage
    avec les zones d'avant, et elle est structurelle -- une planche a un
    redressement, pas un par frame.
    """

    read_rank: int
    carres: tuple[tuple[int, tuple[tuple[float, float], ...]], ...]

    def __post_init__(self) -> None:
        identifiants = sorted(marqueur for marqueur, _sommets in self.carres)
        if identifiants != sorted(layout.CORNER_MARKER_IDS):
            raise CorrectionInvalide(
                f"une planche se redresse sur exactement les quatre marqueurs "
                f"{sorted(layout.CORNER_MARKER_IDS)}, recu {identifiants}"
            )
        for _marqueur, sommets in self.carres:
            # `centre_du_carre` porte deja la garde de cardinal : on l'APPELLE
            # plutot que de la recopier, et le refus tombe a la construction --
            # jamais a la relecture, une session plus tard.
            centre_du_carre(sommets)

    @property
    def centres(self) -> tuple[tuple[int, float, float], ...]:
        """Les quatre centres **deduits**, dans la forme que le coeur attend."""
        return tuple(
            (marqueur,) + centre_du_carre(sommets)
            for marqueur, sommets in self.carres
        )

    def as_document(self) -> dict:
        return {
            "read_rank": self.read_rank,
            CLE_COINS: [
                {"marker_id": marqueur, "quad": [[x, y] for x, y in sommets]}
                # Ordre stable par identifiant de marqueur : deux ecritures des
                # memes carres rendent le meme texte.
                for marqueur, sommets in sorted(self.carres)
            ],
        }

    @classmethod
    def depuis_document(cls, brut: object) -> "CoinsCorriges":
        if not isinstance(brut, dict):
            raise CorrectionInvalide(
                f"un coin corrige est un objet JSON, recu {type(brut).__name__}"
            )
        bruts = brut.get(CLE_COINS)
        if not isinstance(bruts, list):
            raise CorrectionInvalide(
                f"une planche corrigee porte une liste {CLE_COINS!r}, recu "
                f"{type(bruts).__name__}"
            )
        lus: list[tuple[int, tuple[tuple[float, float], ...]]] = []
        for carre in bruts:
            if not isinstance(carre, dict):
                raise CorrectionInvalide(
                    f"un carre corrige est un objet JSON, recu "
                    f"{type(carre).__name__}"
                )
            manquants = [cle for cle in CHAMPS_DE_COIN if cle not in carre]
            if manquants:
                raise CorrectionInvalide(
                    f"carre corrige incomplet, champs manquants: {manquants}"
                )
            sommets = carre["quad"]
            if not isinstance(sommets, list):
                raise CorrectionInvalide(
                    f"le contour d'un marqueur est une liste, recu "
                    f"{type(sommets).__name__}"
                )
            points: list[tuple[float, float]] = []
            for sommet in sommets:
                if not isinstance(sommet, (list, tuple)) or len(sommet) != 2:
                    raise CorrectionInvalide(
                        f"un sommet de contour porte (x, y), recu {sommet!r}"
                    )
                points.append((_nombre(sommet[0], "x"), _nombre(sommet[1], "y")))
            lus.append((_entier(carre["marker_id"], "marker_id"), tuple(points)))
        return cls(
            read_rank=_entier(brut.get("read_rank"), "read_rank"),
            carres=tuple(lus),
        )


def _couche_lisible(document: object) -> dict | None:
    """La couche de correction d'un document, verifiee. ``None`` s'il n'y en a pas.

    **Un seul lieu de verification pour les deux listes** (`EPIC7-ARB-103`) :
    les coins et les identites vivent sous la meme cle et partagent donc
    exactement les memes refus -- document qui n'est pas un objet, couche qui
    n'en est pas un, schema d'un autre levier. Les ecrire deux fois donnerait
    deux redactions du meme refus, et le jour ou l'une des deux changerait, un
    document refuse par un lecteur serait accepte par l'autre.

    Une couche **`v1`** -- celle qui portait des rectangles -- leve avec un
    message qui NOMME le changement plutot qu'un desaccord de version opaque.
    Motif : le levier des rectangles a ete retire par `EPIC7-ARB-102` parce
    qu'il ne redressait rien ; relire ces valeurs comme des coins produirait une
    geometrie fausse d'apparence valide, et les ignorer en silence effacerait un
    travail que l'operatrice croit avoir fait.
    """
    if not isinstance(document, dict):
        raise CorrectionInvalide(
            f"le document doit etre un objet JSON, recu {type(document).__name__}"
        )
    couche = document.get(CLE_DOCUMENT)
    if couche is None:
        return None
    if not isinstance(couche, dict):
        raise CorrectionInvalide(
            f"la couche {CLE_DOCUMENT!r} est un objet JSON, recu "
            f"{type(couche).__name__}"
        )
    schema = couche.get("schema")
    if schema == SCHEMA_DE_CORRECTION_V1:
        raise CorrectionInvalide(
            "ce document porte une couche de correction par ZONES "
            f"({SCHEMA_DE_CORRECTION_V1!r}). Ce levier a ete retire par "
            "EPIC7-ARB-102: les rectangles de decoupe viennent du gabarit, pas "
            "de la detection, donc les corriger ne redressait rien. La "
            "correction se refait sur les quatre coins ArUco de la planche."
        )
    if schema != SCHEMA_DE_CORRECTION:
        raise CorrectionInvalide(
            f"couche de correction non lisible par ce lecteur: {schema!r} "
            f"(attendu {SCHEMA_DE_CORRECTION!r})"
        )
    return couche


#: Cle de la SAISIE d'identite de lot dans la couche `manual_corrections`.
#: Nom anglais, comme tout le vocabulaire de ce document.
CLE_SAISIE_DU_LOT = "lot_identity"


def lire_la_saisie_du_lot(document: object) -> dict | None:
    """La saisie manuelle d'identite de lot portee par le document, ou `None`.

    `EPIC11-ARB-106` : « si le lot n'est pas au manifeste il faut rentrer tous
    les champs manuellement ». C'est la TROISIEME source du modele de
    completion, apres les planches lues du meme lot et le manifeste.

    **Elle voyage dans la couche `manual_corrections` et non dans un drapeau de
    ligne de commande** (trouve en revue de la vague 3 : le refus promettait
    « ou fournir ces valeurs a la main » sans qu'aucun chemin de production ne
    sache le faire). Le motif est celui que `cli.py` ecrit deja pour les coins :
    aucune commande de la CLI ne sait POSER une correction -- c'est
    l'interface qui les pose --, et cette saisie est de la meme nature. La
    mettre ailleurs aurait cree un second canal pour un meme geste.

    Un document sans couche, ou une couche sans saisie, rend `None` : la couche
    est additive, son absence n'est pas une anomalie.
    """
    couche = _couche_lisible(document)
    if couche is None:
        return None
    saisie = couche.get(CLE_SAISIE_DU_LOT)
    if saisie is None:
        return None
    if not isinstance(saisie, dict):
        raise CorrectionInvalide(
            f"la saisie {CLE_SAISIE_DU_LOT!r} est un objet JSON, recu "
            f"{type(saisie).__name__}"
        )
    return saisie


def lire_les_coins(document: object) -> dict[int, CoinsCorriges]:
    """Les coins corriges d'un document, par `read_rank`.

    Un document **sans** couche rend un dictionnaire vide : la couche est
    additive, son absence n'est pas une anomalie et ne se signale pas. Les refus
    communs aux deux listes vivent dans :func:`_couche_lisible`.
    """
    couche = _couche_lisible(document)
    if couche is None:
        return {}
    brutes = couche.get("pages", [])
    if not isinstance(brutes, list):
        raise CorrectionInvalide(
            f"les planches corrigees forment une liste, recu {type(brutes).__name__}"
        )
    planches: dict[int, CoinsCorriges] = {}
    for brute in brutes:
        coins = CoinsCorriges.depuis_document(brute)
        if coins.read_rank in planches:
            raise CorrectionInvalide(
                f"deux corrections pour la planche {coins.read_rank}: "
                f"laquelle des deux vaut ne se devine pas"
            )
        planches[coins.read_rank] = coins
    return planches


def poser_les_coins(document: dict, planches) -> dict:
    """Un document NEUF portant cette couche de coins corriges.

    Le document d'origine n'est pas mute, et tout ce qui n'est pas la couche est
    recopie tel quel -- pages, compteurs et `fingerprints` sortent bit pour bit
    comme ils sont entres.

    Une liste **vide** retire la couche plutot que d'ecrire une couche vide :
    « annuler toutes ses corrections » doit redonner exactement le document
    d'avant, sinon l'annulation laisserait une trace.
    """
    if not isinstance(document, dict):
        raise CorrectionInvalide(
            f"le document doit etre un objet JSON, recu {type(document).__name__}"
        )
    planches = tuple(planches)
    rangs = set()
    for coins in planches:
        if coins.read_rank in rangs:
            raise CorrectionInvalide(
                f"deux corrections pour la planche {coins.read_rank}"
            )
        rangs.add(coins.read_rank)
    neuf = dict(document)
    # **Les identites saisies deja ecrites sont conservees** (`EPIC7-ARB-103`).
    # Les deux listes vivent sous la meme cle de document : reecrire la couche
    # entiere -- ce que cette fonction faisait tant qu'elle etait seule --
    # effacerait l'autre liste sans un mot. Corriger la geometrie d'une planche
    # apres avoir saisi son identite ne doit pas perdre l'identite.
    couche = dict(neuf.get(CLE_DOCUMENT) or {})
    if planches:
        couche["schema"] = SCHEMA_DE_CORRECTION
        couche["pages"] = [
            coins.as_document()
            for coins in sorted(planches, key=lambda c: c.read_rank)
        ]
    else:
        couche.pop("pages", None)
    # Une couche qui ne porte plus que son numero de schema n'est pas une
    # couche : elle disparait, sans quoi « tout annuler » laisserait une trace.
    if not couche.get("pages") and not couche.get(CLE_IDENTITES):
        neuf.pop(CLE_DOCUMENT, None)
    else:
        neuf[CLE_DOCUMENT] = couche
    return neuf


# ---------------------------------------------------------------------------
# EPIC7-ARB-103 -- l'identite saisie a la main, seconde liste de la meme couche
# ---------------------------------------------------------------------------
#
# **Le constat qui rend cette section necessaire** (`EPIC7-ARB-100`, constat
# n0 3) : jusqu'ici le formulaire de completion de QR ne persistait RIEN. Ses
# champs vivaient dans `gui/reparation_vue.py` et n'etaient ecrits nulle part.
# Le remplir faisait basculer l'etat de reparation le temps de la session, et
# c'est tout -- ni le document, ni `scan-write`, ni l'extraction n'apprenaient
# l'identite saisie. La correction manuelle du QR etait « inatteignable la ou
# elle sert, et sans effet la ou elle est atteignable ».
#
# Elle s'ecrit ici, sous la **meme cle de document** que les coins et a cote
# d'eux, parce que c'est la seule reponse compatible avec `EPIC7-ARB-95` :
# `fingerprints.detection` continue de signer ce que la MACHINE a lu, un seul
# fichier porte tout ce que la main a pose, et `scan_previz` continue de relire
# le document sans rien apprendre de neuf.

#: Les identites saisies, liste soeur de `pages` sous la meme couche. Deux
#: listes, pas deux couches : une planche peut avoir l'une, l'autre, ou les
#: deux, et un seul passage les lit et les ecrit.
CLE_IDENTITES = "identities"

#: La provenance, **ecrite dans le document** (`EPIC7-ARB-103`, tranche par
#: Egan) : « une frame extraite sur une identite affirmee par un humain n'est
#: pas la meme preuve qu'une frame extraite sur un QR ; le jour ou un timecode
#: est faux, il faut savoir qui l'a dit ». C'est une constante et non un champ
#: libre : tout ce qui se lit dans cette liste vient de la main par
#: construction, et le jour ou une autre provenance existera elle aura son nom.
PROVENANCE_MANUELLE = "manual"

#: Les champs d'une identite saisie. Le vocabulaire est celui du **payload**
#: (`page_payload`), jamais celui de l'interface : ce document est un artefact
#: de coeur, et deux orthographes du meme champ dans un meme fichier est ce qui
#: fait diverger deux lecteurs.
CHAMPS_D_IDENTITE = (
    "lot_id",
    "template_id",
    "frames_per_page",
    "page_index",
    "first_frame_timecode",
    "last_frame_timecode",
)


def _texte(valeur: object, cle: str) -> str:
    """Une chaine non blanche.

    Un identifiant vide se lirait comme un identifiant -- meme doctrine que le
    plancher de plausibilite du formulaire (`gui.reparation._PLANCHERS`), pose
    ici aussi parce que le coeur ne fait jamais confiance a son appelant.
    """
    if not isinstance(valeur, str) or not valeur.strip():
        raise CorrectionInvalide(
            f"le champ {cle!r} d'une identite saisie est un texte non vide, "
            f"recu {valeur!r}"
        )
    return valeur


@dataclass(frozen=True)
class IdentiteManuelle:
    """Ce qu'une operatrice a lu SUR LE PAPIER et saisi, pour UNE planche.

    Ce n'est **pas** un payload : c'est ce qui manque a une planche muette pour
    qu'un payload puisse etre compose. Les valeurs neutres en projet -- cadence
    cible, base de timecode, preset de pastilles, espace de sortie -- n'y sont
    pas, et c'est deliberé : l'operatrice ne les lit pas sur la planche. Elles se
    completent en aval, depuis le lot, et l'appelant refuse nommement quand rien
    sur la machine ne les porte plutot que d'en inventer.

    `template_id` est le sixieme champ de `EPIC7-ARB-100`, et le seul de la
    liste qui ne se lise pas litteralement sur la planche : il se **choisit**
    dans le registre. Cette nuance est l'arbitrage entier -- « un gabarit choisi
    par l'operatrice n'est pas un gabarit devine par la machine » --, et c'est
    ce qui rend ce champ compatible avec l'interdit de 5.2 plutot que contraire
    a lui.
    """

    read_rank: int
    lot_id: str
    template_id: str
    frames_per_page: int
    page_index: int
    first_frame_timecode: str
    last_frame_timecode: str

    def __post_init__(self) -> None:
        if self.frames_per_page <= 0:
            raise CorrectionInvalide(
                "une planche porte au moins une frame, recu "
                f"{self.frames_per_page}"
            )
        # **A partir de zero**, comme tout le depot numerote ses planches
        # (`scan_detect.ORIGINE_DES_PAGE_INDEX`). Refuser zero refuserait la
        # premiere planche de tout lot.
        if self.page_index < 0:
            raise CorrectionInvalide(
                f"un numero de planche part de zero, recu {self.page_index}"
            )

    @property
    def provenance(self) -> str:
        """Toujours :data:`PROVENANCE_MANUELLE`. Publie pour se lire, pas pour varier."""
        return PROVENANCE_MANUELLE

    def as_document(self) -> dict:
        return {
            "read_rank": self.read_rank,
            "source": PROVENANCE_MANUELLE,
            "lot_id": self.lot_id,
            "template_id": self.template_id,
            "frames_per_page": self.frames_per_page,
            "page_index": self.page_index,
            "first_frame_timecode": self.first_frame_timecode,
            "last_frame_timecode": self.last_frame_timecode,
        }

    @classmethod
    def depuis_document(cls, brut: object) -> "IdentiteManuelle":
        if not isinstance(brut, dict):
            raise CorrectionInvalide(
                f"une identite saisie est un objet JSON, recu "
                f"{type(brut).__name__}"
            )
        # **La provenance est verifiee, pas supposee.** Une entree qui ne dit
        # pas d'ou elle vient n'est pas une identite manuelle : la lire comme
        # telle ferait passer pour « affirmee par un humain » quelque chose que
        # personne n'a affirme, ce qui est l'inverse exact de ce que
        # `EPIC7-ARB-103` demande a ce champ.
        source = brut.get("source")
        if source != PROVENANCE_MANUELLE:
            raise CorrectionInvalide(
                f"identite saisie de provenance {source!r}, attendu "
                f"{PROVENANCE_MANUELLE!r}: une identite dont la provenance n'est "
                "pas ecrite ne se devine pas"
            )
        for cle in CHAMPS_D_IDENTITE:
            if cle not in brut:
                raise CorrectionInvalide(f"identite saisie sans champ {cle!r}")
        return cls(
            read_rank=_entier(brut.get("read_rank"), "read_rank"),
            lot_id=_texte(brut["lot_id"], "lot_id"),
            template_id=_texte(brut["template_id"], "template_id"),
            frames_per_page=_entier(brut["frames_per_page"], "frames_per_page"),
            page_index=_entier(brut["page_index"], "page_index"),
            first_frame_timecode=_texte(
                brut["first_frame_timecode"], "first_frame_timecode"),
            last_frame_timecode=_texte(
                brut["last_frame_timecode"], "last_frame_timecode"),
        )


def lire_les_identites(document: object) -> dict[int, IdentiteManuelle]:
    """Les identites saisies d'un document, par `read_rank`.

    Meme repli permanent que :func:`lire_les_coins` : un document sans couche,
    ou une couche sans liste `identities`, rend un dictionnaire vide. Les deux
    listes sont **independantes** -- une planche dont on n'a corrige que la
    geometrie n'a pas d'identite saisie, et reciproquement.
    """
    couche = _couche_lisible(document)
    if couche is None:
        return {}
    brutes = couche.get(CLE_IDENTITES, [])
    if not isinstance(brutes, list):
        raise CorrectionInvalide(
            f"les identites saisies forment une liste, recu "
            f"{type(brutes).__name__}"
        )
    identites: dict[int, IdentiteManuelle] = {}
    for brute in brutes:
        identite = IdentiteManuelle.depuis_document(brute)
        if identite.read_rank in identites:
            raise CorrectionInvalide(
                f"deux identites saisies pour la planche {identite.read_rank}: "
                f"laquelle des deux vaut ne se devine pas"
            )
        identites[identite.read_rank] = identite
    return identites


def poser_les_identites(document: dict, identites) -> dict:
    """Un document NEUF portant ces identites saisies.

    **Les coins deja ecrits sont conserves**, et c'est la propriete qui compte :
    les deux listes vivent sous la meme cle de document, si bien qu'un ecrivain
    naif qui reecrirait la couche entiere effacerait l'autre liste sans un mot.
    Saisir l'identite d'une planche apres en avoir corrige la geometrie ne doit
    pas perdre la geometrie -- ni l'inverse.

    Une liste **vide** retire la seule liste `identities` ; la couche entiere ne
    disparait que s'il n'y a plus de coins non plus, pour que « tout annuler »
    redonne exactement le document d'avant.
    """
    if not isinstance(document, dict):
        raise CorrectionInvalide(
            f"le document doit etre un objet JSON, recu {type(document).__name__}"
        )
    identites = tuple(identites)
    rangs = set()
    for identite in identites:
        if identite.read_rank in rangs:
            raise CorrectionInvalide(
                f"deux identites saisies pour la planche {identite.read_rank}"
            )
        rangs.add(identite.read_rank)
    neuf = dict(document)
    couche = dict(neuf.get(CLE_DOCUMENT) or {})
    if identites:
        couche["schema"] = SCHEMA_DE_CORRECTION
        couche[CLE_IDENTITES] = [
            identite.as_document()
            for identite in sorted(identites, key=lambda i: i.read_rank)
        ]
    else:
        couche.pop(CLE_IDENTITES, None)
    if not couche.get("pages") and not couche.get(CLE_IDENTITES):
        neuf.pop(CLE_DOCUMENT, None)
    else:
        neuf[CLE_DOCUMENT] = couche
    return neuf


#: Les champs qu'une identite saisie ne porte PAS, et que le lot seul peut
#: donner. Ils sont neutres vis-a-vis de la planche -- l'operatrice ne les lit
#: pas dessus -- et l'un d'eux, `fps_target`, est l'interdit central de 6.6
#: (`EPIC6-ARB-6`) : deviner une cadence est precisement ce que le depot refuse.
CHAMPS_NEUTRES_DU_LOT = (
    "project_id",
    "rush_id",
    "fps_target",
    "timecode_base_fps",
    "patch_preset_id",
    "target_colorspace",
    "gamut_map_id",
    "page_count",
)


class IdentiteIncompletable(CorrectionInvalide):
    """Une identite saisie que rien sur la machine ne permet de completer.

    Refus **nomme**, jamais un repli : les valeurs manquantes sont la cadence
    cible, la base de timecode et le preset de pastilles du lot. Les inventer
    produirait des TIFF d'apparence valide au mauvais timecode, c'est-a-dire la
    faute exacte que `scan_detection.resolve_page_identity` refuse depuis 5.2.
    """


#: Les champs neutres qui NE SE LISENT PAS au pied de la planche, et qu'une
#: saisie doit donc prendre ailleurs sur la feuille.
#:
#: `project_id` et `rush_id` sont au bloc d'identite, `fps_target` a l'en-tete
#: (« 5 im/s ») : tous les huit sont donc atteignables a l'oeil sur une planche
#: imprimee. C'est ce qui rend la completion manuelle possible **sans rien
#: deviner**, et c'est pourquoi ce mecanisme peut exister.
#:
#: L'exception a connaitre, dite plutot que subie : le pied imprime aussi
#: `dict=` (le dictionnaire ArUco). Ce n'est PAS un champ de payload -- il est
#: la pour le diagnostic, pas pour etre retape dans un formulaire.
CHAMPS_NEUTRES_HORS_DU_PIED = ("project_id", "rush_id", "fps_target")


def modele_saisi(valeurs: dict) -> dict:
    """Un modele de completion CONSTRUIT depuis une saisie, et non LU.

    `EPIC11-ARB-106` (Egan, 2026-08-31) : « si le lot n'est pas au manifeste il
    faut rentrer tous les champs manuellement ».

    **Le trou que cela ferme.** `payload_depuis_l_identite` exige un modele --
    les huit champs neutres du lot -- et le depot n'avait que DEUX sources pour
    lui : une autre planche lue de la meme pile, ou le manifeste du projet.
    Quand les deux manquent (manifeste perdu, projet reconstruit, pile d'une
    seule planche muette), le refus etait juste mais n'offrait RIEN. C'est un
    blocage sec, ce qu'`EPIC11-ARB-89` interdit -- et il etait d'autant plus
    dur que la feuille, elle, PORTE l'information : les huit champs sont
    imprimes ou lisibles dessus.

    **Ce que cette fonction ne fait pas, et c'est l'essentiel.** Elle ne devine
    rien. Un champ absent de la saisie est un refus nomme, jamais un defaut :
    deviner une cadence est l'interdit central d'`EPIC6-ARB-6`, et le tort
    qu'il decrit -- « des TIFF d'apparence valide au mauvais timecode » -- ne
    devient pas acceptable parce que c'est un humain qui a laisse le champ
    vide.

    Elle ne fait donc qu'une chose : accepter que la source du modele soit
    l'operateur plutot que la machine, avec la meme exigence de completude.
    """
    if not isinstance(valeurs, Mapping):
        raise IdentiteIncompletable(
            f"une saisie de completion est un dictionnaire de champs, recu "
            f"{type(valeurs).__name__}"
        )
    manquants = [cle for cle in CHAMPS_NEUTRES_DU_LOT if not valeurs.get(cle)]
    if manquants:
        raise IdentiteIncompletable(
            f"la saisie ne porte pas {', '.join(manquants)}. Ces valeurs ne se "
            "devinent pas -- les inventer produirait des TIFF d'apparence "
            "valide au mauvais timecode. Elles sont TOUTES lisibles sur la "
            "planche imprimee: le pied technique porte "
            f"{', '.join(c for c in CHAMPS_NEUTRES_DU_LOT if c not in CHAMPS_NEUTRES_HORS_DU_PIED)}, "
            "le bloc d'identite porte project_id et rush_id, et l'en-tete la "
            "cadence."
        )
    # Le modele ne porte QUE les champs neutres, plus le `lot_id` qui sert a
    # l'appariement. Y laisser passer un champ de plus ferait entrer par cette
    # porte une valeur que `build_page_payload` refuserait plus loin, ou pire
    # qu'il accepterait sans qu'elle vienne d'une planche.
    modele = {cle: valeurs[cle] for cle in CHAMPS_NEUTRES_DU_LOT}
    if valeurs.get("lot_id"):
        modele["lot_id"] = valeurs["lot_id"]
    return modele


def payload_depuis_l_identite(identite: IdentiteManuelle, *, modele: dict) -> dict:
    """Le payload qu'une identite saisie devient, complete par son lot.

    **Ce que l'operatrice donne, et ce qu'elle ne donne pas.** Elle lit sur la
    planche ce qui y est imprime : le lot, le numero de planche, le nombre de
    frames, les timecodes de la premiere et de la derniere. Elle ne lit pas la
    cadence cible, la base de timecode, le preset de pastilles ni l'espace de
    sortie -- ils ne sont pas sur le papier. Ces huit champs neutres
    (:data:`CHAMPS_NEUTRES_DU_LOT`) viennent donc de `modele`, un payload
    **decode** d'une autre planche du MEME lot.

    C'est ce qui rend `EPIC7-ARB-103` realisable sans rien deviner : une pile
    mixte porte au moins une planche lue, et cette planche dit tout ce que la
    muette ne dit pas. Quand il n'y en a aucune, cette fonction n'est pas
    appelee -- l'appelant refuse nommement.

    **Les timecodes intermediaires sont interpoles, pas devines.** La spine ne
    demande que la premiere et la derniere (`EXPERIENCE.md:346`), et l'ecart se
    repartit uniformement : c'est ce que l'extraction produit, donc ce que la
    planche porte. Un ecart qui ne tombe pas juste est **refuse** plutot
    qu'arrondi -- arrondir decalerait un nom de TIFF d'une frame sans un mot.

    Le payload sort par `io.payload.build_page_payload`, point de contrat unique
    du depot : aucun dictionnaire n'est assemble a la main ici, si bien qu'un
    champ ajoute au contrat fait echouer cet appel au lieu de produire un
    payload silencieusement incomplet.
    """
    from .io.payload import build_page_payload

    if not isinstance(modele, dict):
        raise IdentiteIncompletable(
            f"le modele de completion est un payload decode, recu "
            f"{type(modele).__name__}"
        )
    if modele.get("lot_id") != identite.lot_id:
        raise IdentiteIncompletable(
            f"le modele de completion declare le lot {modele.get('lot_id')!r}, "
            f"l'identite saisie le lot {identite.lot_id!r}: completer l'une par "
            "l'autre melangerait deux lots"
        )
    manquants = [cle for cle in CHAMPS_NEUTRES_DU_LOT if cle not in modele]
    if manquants:
        raise IdentiteIncompletable(
            "le modele de completion ne porte pas "
            f"{', '.join(manquants)}: ces valeurs ne se devinent pas"
        )
    # **Le nombre d'emplacements d'une planche vient du GABARIT**, pas de la
    # saisie. Les deux ne disent pas la meme chose : le gabarit dit combien
    # d'emplacements la planche PORTE, la saisie combien sont REMPLIS -- une
    # derniere planche de lot incomplet en porte quatre et n'en remplit qu'un.
    # C'est le nominal du gabarit, et lui seul, qui donne le rang du premier
    # emplacement dans le lot.
    nominal = page_templates.get_template(identite.template_id).frames_per_page
    if identite.frames_per_page > nominal:
        raise IdentiteIncompletable(
            f"le gabarit {identite.template_id!r} porte {nominal} emplacement(s) "
            f"par planche, l'identite saisie en declare {identite.frames_per_page}: "
            "le gabarit choisi n'est pas celui de cette planche"
        )
    return build_page_payload(
        project_id=modele["project_id"],
        rush_id=modele["rush_id"],
        lot_id=identite.lot_id,
        page_index=identite.page_index,
        page_count=modele["page_count"],
        fps_target=modele["fps_target"],
        timecode_base_fps=modele["timecode_base_fps"],
        template_id=identite.template_id,
        patch_preset_id=modele["patch_preset_id"],
        target_colorspace=modele["target_colorspace"],
        gamut_map_id=modele["gamut_map_id"],
        slots=_slots_interpoles(
            identite, base=modele["timecode_base_fps"],
            premier_rang=identite.page_index * nominal),
    )


#: Ou chaque champ neutre du lot **se lit dans le manifeste du projet**, story
#: 11.4b (`EPIC11-ARB-64`). La table est indexee par la meme liste que
#: :data:`CHAMPS_NEUTRES_DU_LOT`, et :func:`modele_depuis_le_manifeste` refuse si
#: les deux cessent de coincider : un champ ajoute au contrat sans source ici
#: produirait un modele silencieusement incomplet, c'est-a-dire exactement le
#: faux succes que `payload_depuis_l_identite` refuse deja cote appelant.
#:
#: Trois sections, et ce n'est pas un detail de rangement : `project_id` est de
#: portee **projet**, `target_colorspace` de portee **projet** aussi mais sous
#: `color` (contrat 2.3), et les quatre autres sont de portee **lot** -- deux lots
#: d'un meme projet peuvent legitimement porter deux compressions de gamut
#: (`EPIC5-ARB-20`). Les lire au mauvais niveau melangerait deux lots.
_SOURCE_AU_MANIFESTE = {
    "project_id": ("projet", "project_id"),
    "rush_id": ("lot", "rush_id"),
    "fps_target": ("lot", "fps_target"),
    "timecode_base_fps": ("lot", "timecode_base_fps"),
    "patch_preset_id": ("lot", "patch_preset_id"),
    "gamut_map_id": ("lot", "gamut_map_id"),
    "target_colorspace": ("color", "target_colorspace"),
    # Le seul des huit qui ne soit pas ecrit tel quel : il se **deduit** de la
    # selection et du gabarit, par la formule de l'impression elle-meme.
    "page_count": ("deduit", None),
}


def modele_depuis_le_manifeste(manifeste: object, *, lot_id: str) -> dict:
    """Le modele de completion d'un lot **du projet**, sans aucune planche lue.

    C'est la moitie qui manquait a `EPIC7-ARB-103`. `payload_depuis_l_identite`
    exige un `modele` -- un payload **decode** d'une autre planche du meme lot --
    pour les huit champs que l'operatrice ne lit pas sur le papier. Cette
    exigence vient de ce que la fonction a ete ecrite pour la GUI, ou le lot peut
    etre **etranger** au projet ouvert. Quand le lot est celui du projet, rien ne
    manque : sept des huit champs sont ecrits au manifeste et le huitieme,
    `page_count`, se deduit.

    **Deux regimes, et le second garde son refus** (`EPIC11-ARB-64`) :

    * **lot connu du projet** -> le modele vient d'ici, et une pile d'**une seule
      planche muette** devient completable. C'est le cas qu'Egan a nomme : une
      planche unique dont le QR echoue n'a aucune soeur a lire, donc aucune
      planche modele, et elle etait incompletable pour cette seule raison ;
    * **scan etranger, lot inconnu du manifeste** -> refus **nomme**. Verbatim de
      l'arbitrage : « il faut une planche lue, ou les champs imprimes ». Cette
      fonction n'invente **aucun** champ, et surtout pas `fps_target` -- deviner
      une cadence est l'interdit central de 6.6 (`EPIC6-ARB-6`).

    Le modele rendu porte les huit champs neutres **plus `lot_id`**, parce que
    c'est sur lui que `payload_depuis_l_identite` verifie que le modele et
    l'identite saisie parlent du meme lot. Un modele sans lui se ferait refuser
    par son unique consommateur.

    `page_count` passe par `pdf_composition.page_count_du_lot`, donc par la
    selection recalculee et par la formule de pagination de l'impression --
    **jamais** par une seconde redaction (voir `nombre_de_planches`).
    """
    from . import pdf_composition

    if not isinstance(manifeste, dict):
        raise IdentiteIncompletable(
            f"le manifeste du projet est un objet JSON, recu "
            f"{type(manifeste).__name__}"
        )
    if not isinstance(lot_id, str) or not lot_id.strip():
        raise IdentiteIncompletable(
            f"le lot a completer se nomme par un identifiant non vide, recu "
            f"{lot_id!r}"
        )
    lots = manifeste.get("lots")
    lot = None
    connus: list[str] = []
    for entree in lots if isinstance(lots, list) else []:
        if not isinstance(entree, dict):
            continue
        connus.append(str(entree.get("lot_id")))
        if entree.get("lot_id") == lot_id and lot is None:
            lot = entree
    if lot is None:
        # **Le refus nomme le lot cherche ET les lots connus.** Un refus qui ne
        # dit pas ce que le projet contient envoie l'operatrice verifier au
        # mauvais endroit : le cas reel est un scan de planches d'un AUTRE
        # projet, ou la reponse est « adopte ce lot », pas « corrige ta saisie ».
        raise IdentiteIncompletable(
            f"le lot {lot_id!r} est inconnu du manifeste de ce projet (lots "
            f"connus: {', '.join(connus) or '(aucun)'}): un scan etranger se "
            "complete depuis une planche lue de la meme pile, ou depuis les "
            "champs imprimes au pied de la planche -- jamais depuis des "
            "valeurs inventees"
        )

    # La table et le contrat se confrontent, ils ne se supposent pas egaux.
    sans_source = [cle for cle in CHAMPS_NEUTRES_DU_LOT
                   if cle not in _SOURCE_AU_MANIFESTE]
    if sans_source:
        raise IdentiteIncompletable(
            f"aucune source de manifeste n'est declaree pour "
            f"{', '.join(sans_source)}: le contrat de completion a gagne un "
            "champ que ce constructeur ne sait pas lire"
        )

    couleur = manifeste.get("color")
    sections = {
        "projet": manifeste,
        "lot": lot,
        "color": couleur if isinstance(couleur, dict) else {},
    }
    modele: dict = {"lot_id": lot_id}
    manquants: list[str] = []
    for champ in CHAMPS_NEUTRES_DU_LOT:
        section, cle = _SOURCE_AU_MANIFESTE[champ]
        if section == "deduit":
            continue
        valeur = sections[section].get(cle)
        # `None` **et** la chaine vide manquent tous les deux : le schema borne
        # ces champs a `minLength: 1`, et une chaine vide se lirait plus loin
        # comme un identifiant.
        if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
            manquants.append(f"{champ} ({section})")
            continue
        modele[champ] = valeur
    if manquants:
        raise IdentiteIncompletable(
            f"le manifeste du projet ne porte pas {', '.join(manquants)} pour le "
            f"lot {lot_id!r}: ces valeurs ne se devinent pas. Un lot imprime par "
            "makepdf les porte toutes (story 5.11) -- un lot reconstruit d'un "
            "scan anterieur peut ne pas les avoir, et il faut alors une planche "
            "lue ou les champs imprimes"
        )

    # `page_count` en dernier, parce qu'il est le seul a couter une lecture de
    # gabarit et un recalcul de selection : les sept refus ci-dessus sont plus
    # rapides et plus lisibles, et ils tombent avant.
    template_id = lot.get("template_id")
    if not isinstance(template_id, str) or not template_id.strip():
        raise IdentiteIncompletable(
            f"le lot {lot_id!r} ne declare pas lots[].template_id au manifeste: "
            "sans le gabarit avec lequel il a ete imprime, le nombre de "
            "planches ne se deduit pas -- il ne se devine pas non plus"
        )
    emplacements = page_templates.get_template(template_id).frames_per_page
    try:
        modele["page_count"] = pdf_composition.page_count_du_lot(
            manifeste, lot_id, frames_per_page=emplacements)
    except pdf_composition.CompositionError as exc:
        # Le motif du coeur d'impression est **transporte**, jamais remplace :
        # il nomme le champ de manifeste qui manque a la selection.
        raise IdentiteIncompletable(
            f"le nombre de planches du lot {lot_id!r} ne se deduit pas du "
            f"manifeste: {exc}"
        ) from exc
    return modele


def _slots_interpoles(identite: IdentiteManuelle, *, base,
                      premier_rang: int = 0) -> list:
    """Les `frames_per_page` emplacements, timecodes repartis uniformement.

    **`slot_index` est un rang dans le LOT, pas dans la planche.** Mesure sur le
    document que `scan detect` produit : la planche 0 porte les emplacements 0 a
    3, la planche 1 les emplacements 4 a 7. Repartir de zero a chaque planche
    ferait declarer deux fois le meme emplacement au manifest, et la
    reconstruction refuse -- « Conflit de reconstruction: slot_index 0 declare
    plusieurs fois ».

    L'arithmetique passe par `codec_profiles`, seul lieu du depot ou un timecode
    se convertit en index de frame et retour. Une seconde redaction diverge
    silencieusement, et l'ecart ne se voit que sur le nom des TIFF.

    Trois refus, et chacun ferme un faux succes :

    * une planche a **une seule** frame dont les deux timecodes different : on
      ne sait pas lequel des deux est celui de la frame ;
    * un ecart **negatif** : la derniere image precederait la premiere ;
    * un ecart qui **ne tombe pas juste** sur le nombre d'intervalles : arrondir
      decalerait les frames intermediaires d'une frame chacune, sans un mot.
    """
    from . import codec_profiles

    premier = codec_profiles.timecode_to_frame_index(
        identite.first_frame_timecode, base)
    dernier = codec_profiles.timecode_to_frame_index(
        identite.last_frame_timecode, base)
    intervalles = identite.frames_per_page - 1
    if intervalles == 0:
        if premier != dernier:
            raise IdentiteIncompletable(
                "une planche a une seule frame porte le meme timecode de "
                f"premiere et de derniere image, recu "
                f"{identite.first_frame_timecode!r} et "
                f"{identite.last_frame_timecode!r}"
            )
        return [{"slot_index": premier_rang,
                 "frame_timecode": identite.first_frame_timecode}]
    ecart = dernier - premier
    if ecart < 0:
        raise IdentiteIncompletable(
            f"la derniere image ({identite.last_frame_timecode}) precede la "
            f"premiere ({identite.first_frame_timecode})"
        )
    if ecart % intervalles:
        raise IdentiteIncompletable(
            f"l'ecart de {ecart} frames entre {identite.first_frame_timecode} "
            f"et {identite.last_frame_timecode} ne se repartit pas sur "
            f"{intervalles} intervalles: les timecodes intermediaires seraient "
            "arrondis, donc faux d'une frame"
        )
    pas = ecart // intervalles
    return [
        {
            "slot_index": premier_rang + rang,
            "frame_timecode": codec_profiles.frame_index_to_timecode(
                premier + rang * pas, base),
        }
        for rang in range(identite.frames_per_page)
    ]


def homographie_depuis_les_coins(coins: "CoinsCorriges | tuple", *,
                                 template_id: str, dpi: int):
    """L'homographie que ces quatre coins corriges produisent, et son echelle.

    **Le point unique ou la correction devient de la geometrie**, et il vit dans
    le coeur precisement pour n'exister qu'une fois : l'interface la calcule pour
    montrer le resultat a l'ecran, `scan-write` la recalcule pour decouper les
    pixels. Deux redactions de cet ajustement divergeraient, et le desaccord ne
    se verrait que sur les TIFF produits -- c'est-a-dire trop tard.

    C'est aussi ce qui garde `gui/reparation.py` a l'ecart du module de
    detection : la vue appelle cette fonction-ci, jamais `findHomography`.

    `resolve_page_geometry` puis `compute_template_homography` sont exactement
    les deux fonctions que la detection emploie (`scan_detection._page_geometry`)
    -- reprises, jamais reecrites. Leurs refus (coins degeneres, gabarit inconnu)
    **remontent** tels quels : cette fonction n'en met aucun en forme.
    """
    from . import scan_detection

    centres = getattr(coins, "centres", coins)
    geometrie = scan_detection.resolve_page_geometry(template_id, dpi)
    marqueurs = [
        {"id": identifiant, "center": (x, y)} for identifiant, x, y in centres
    ]
    return scan_detection.compute_template_homography(marqueurs, geometrie, dpi)


class GeometrieInexploitable(CorrectionInvalide):
    """L'homographie fournie ne se renverse pas. Refus nomme, jamais un silence."""


def quadrilatere_dans_le_scan(rect_px, homographie):
    """Le rectangle d'une zone, ramene du repere REDRESSE au repere du SCAN.

    **Ce que cette fonction repare, et pourquoi elle existe.** Le document porte
    deux geometries qui ne vivent pas dans le meme repere : les zones d'image en
    pixels de page *redressee* (`crop_rect_px`, une conversion mm x dpi pure) et
    les marqueurs ArUco en pixels du *scan* (`corner_quad_px`, ce que le
    detecteur a lu sur le papier). Les peindre toutes deux sur le raster source
    superposait deux systemes de coordonnees : sur une planche posee de travers
    de 0,6 degre -- l'ordinaire d'un scanner a plat --, l'ecart atteint une
    cinquantaine de pixels au bas de la page et grandit vers le bas.

    Retour de terrain d'Egan du 2026-08-28, mesure sur son propre scan :
    « les zones sont mal alignees alors que les ArUco sont censes avoir ete lus.
    Il y a un decalage sur les deux marqueurs du bas ». Les marqueurs etaient
    justes, les zones aussi ; c'est leur cohabitation qui ne l'etait pas.

    Consequence qui compte autant : sans ce passage, corriger un coin ArUco ne
    pouvait RIEN changer a l'ecran. La correction refait l'homographie, mais les
    rectangles affiches ne la consultaient jamais -- « si je clique sur terminer
    la correction rien ne se passe [...] je devrais voir les rectangles
    s'ajuster non ? ». Oui.

    ``homographie`` est la matrice du document, celle que `warp_page` consomme :
    elle envoie le SCAN vers la page redressee. Ramener une zone a l'ecran
    demande donc son **inverse**, et c'est le seul endroit du depot ou cette
    inversion s'ecrit.

    Rend les quatre sommets dans l'ordre haut-gauche, haut-droit, bas-droit,
    bas-gauche -- l'ordre du contour d'un marqueur, pour qu'un consommateur
    n'ait pas deux conventions a retenir.
    """
    import numpy as np

    x, y, largeur, hauteur = (float(v) for v in rect_px)
    matrice = np.asarray(homographie, dtype=float).reshape(3, 3)
    try:
        inverse = np.linalg.inv(matrice)
    except np.linalg.LinAlgError as erreur:
        raise GeometrieInexploitable(
            f"homographie non inversible ({erreur}) : la zone ne peut pas etre "
            "ramenee dans le repere du scan. Aucune position approchee n'est "
            "dessinee -- une geometrie fausse d'apparence valide est pire que "
            "pas de geometrie."
        ) from erreur

    sommets = np.array(
        [[x, y, 1.0],
         [x + largeur, y, 1.0],
         [x + largeur, y + hauteur, 1.0],
         [x, y + hauteur, 1.0]],
        dtype=float,
    )
    projetes = sommets @ inverse.T
    poids = projetes[:, 2]
    if not np.all(np.isfinite(poids)) or np.any(np.abs(poids) < 1e-12):
        raise GeometrieInexploitable(
            "un sommet de la zone part a l'infini une fois ramene dans le "
            "repere du scan : l'homographie envoie ce coin sur la ligne de "
            "fuite, et le quadrilatere n'a pas de sens."
        )
    return tuple(
        (float(px / w), float(py / w))
        for px, py, w in zip(projetes[:, 0], projetes[:, 1], poids)
    )


__all__ = [
    "CHAMPS_D_IDENTITE",
    "CHAMPS_NEUTRES_DU_LOT",
    "CLE_COINS",
    "CLE_IDENTITES",
    "CLE_DOCUMENT",
    "SCHEMA_DE_CORRECTION_V1",
    "CoinsCorriges",
    "IdentiteIncompletable",
    "IdentiteManuelle",
    "PROVENANCE_MANUELLE",
    "lire_les_coins",
    "lire_les_identites",
    "payload_depuis_l_identite",
    "poser_les_coins",
    "poser_les_identites",
    "SCHEMA_DE_CORRECTION",
    "CorrectionInvalide",
    "ecrire",
    "GeometrieInexploitable",
    "homographie_depuis_les_coins",
    "quadrilatere_dans_le_scan",
]
