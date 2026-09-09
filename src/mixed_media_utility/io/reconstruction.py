"""Project reconstruction helpers (Story 2.6).

Given a set of decoded page payloads (see ARCHITECTURE_DETAILED.md section 3
"Contrat minimal de reconstruction" and section 6 for the recommended QR
payload) and, optionally, a partial local manifest, rebuild a coherent v2
project manifest without requiring access to the original source machine, its
file paths, or its local project state.

QR decoding itself is not yet integrated in this codebase, so callers provide
already-decoded payload dictionaries (loaded from JSON, e.g. synthetic
fixtures in tests today, and eventually a real QR decoder later).

Page indexes follow the base-zero convention made normative in
ARCHITECTURE_DETAILED.md section 3.1: a lot's first page is `page_index = 0`
and the invariant is `0 <= page_index < page_count`, matching what
`io/payload.py` produces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker

from jsonschema.exceptions import ValidationError

from ..page_roles import (
    CALIBRATION_PAGE_INDEX,
    MAX_CALIBRATION_PAGES_PER_LOT,
    PAGE_ROLE_CALIBRATION,
    PAGE_ROLE_IMAGES,
    PAGE_ROLES,
    UnknownPageRoleError,
    page_role_label,
    validate_page_role,
)
from .manifest import CURRENT_SCHEMA_VERSION, LOT_STATES, validate_lot_state_transition
from .payload import (
    CALIBRATION_ABSENT_FIELDS,
    PAYLOAD_SCHEMA_VERSION,
    REREAD_DEFAULTS,
    SCAN_CHAIN_LABEL_FIELD,
)

#: Meme resolution que `io/manifest.py`, et pour la meme raison mesuree le
#: 2026-09-07 : une donnee du paquet, jamais un chemin depuis la racine du
#: depot. Voir le commentaire de `io/manifest.py`.
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "specs" / "project.schema.json"

# Minimal set of fields a decoded page payload must carry to take part in a
# reconstruction (ARCHITECTURE_DETAILED.md section 3). Must stay a subset of
# what `io/payload.py` guarantees: any field required here that
# `build_page_payload` does not emit would make the QR chain unusable.
REQUIRED_PAGE_FIELDS = (
    "schema_version",
    "project_id",
    "rush_id",
    "lot_id",
    "page_index",
    "page_count",
    "fps_target",
    # Story 2.7 (payload 2.1, EPIC7-ARB-56): la cadence SOURCE du rush, meme
    # regime que sa voisine `fps_target` -- absente sous CALIBRATION_ABSENT_FIELDS,
    # requise sur une planche d'images.
    "timecode_base_fps",
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
    "target_colorspace",
    "slots",
)

# --- `page_role`: **optionnel a la relecture**, avec defaut au role d'images -------
#
# Story 5.16, corrige a sa passe de correction (couche 3, majeur M3). Le champ etait
# **requis** ici et dans `io.payload`, ajoute sous la **meme** chaine de version de
# schema `2.0` que 5.17 venait de poser: une planche imprimee avant lui levait donc un
# refus, en violation de la regle du depot qui veut qu'une planche imprimee reste
# relisible. Le risque pratique etait nul -- 5.16 et 5.17 ont atterri le meme jour et
# rien n'avait ete imprime sous `2.0` sans le champ -- mais la regle, elle, etait violee.
#
# Le defaut est celui du contrat d'ecriture (`io.payload.REREAD_DEFAULTS`), **relu** et
# non recopie: une seconde valeur ici divergerait en silence a l'ecriture et fatalement a
# la relecture, ce qui est le motif meme du module `page_roles`. Il ne s'applique qu'a
# l'**absence complete** du champ: une valeur presente et hors vocabulaire, vide ou nulle
# reste un refus -- c'est alors un champ abime, pas une feuille ancienne.
PAGE_ROLE_DEFAULT_AT_REREAD = REREAD_DEFAULTS["page_role"]

# Fields that must be identical across every page payload belonging to the same lot.
_LOT_LEVEL_FIELDS = (
    "schema_version",
    "project_id",
    "rush_id",
    "lot_id",
    "page_count",
    "fps_target",
    # Story 2.7: onzieme champ de niveau lot. Deux pages du meme lot qui
    # declareraient deux cadences source sont un conflit d'identite de lot,
    # exactement comme pour `fps_target` -- c'est le terrain du risque R12
    # (deux lots du meme rush a deux cadences est le cas nominal v2.1; deux
    # PAGES du MEME lot a deux cadences, lui, reste un conflit).
    "timecode_base_fps",
    "template_id",
    "patch_preset_id",
    "gamut_map_id",
    "target_colorspace",
)

REQUIRED_SLOT_FIELDS = ("slot_index", "frame_timecode")

# Story 2.8 (AC 1): `_ABSOLUTE_PATH_PATTERN` vivait ici pour refuser un
# `source_path` absolu venu du manifest local -- la garde qu'EPIC7-ARB-41
# renverse (voir plus bas, `_existing_source_path`). Retiree: elle n'a plus
# d'appelant, et io/manifest.py reste la seule source de verite sur la forme
# d'un chemin absolu.

# Two distinct versioned artifacts, deliberately not conflated:
#   - the QR page payload contract (story 2.3), owned by `io/payload.py`;
#   - the project manifest schema (story 2.1), whose `const` lives in
#     `src/mixed_media_utility/specs/project.schema.json`.
# A payload declares the former; reconstruction emits the latter. Reading the
# manifest version straight out of the payload would tie the two release
# cycles together and silently break as soon as either one moves.
# Story 5.17: cette garde **suit** le contrat au lieu de le recopier, et c'est ce qui
# lui a evite d'etre fausse quand la version est passee de `1.0` a `2.0`
# (`EPIC5-ARB-60`). Elle n'est atteinte que par la sous-commande
# `reconstruct-project`, qui recoit des payloads JSON deja parses: la chaine de scan,
# elle, refuse une planche perimee bien plus tot, dans `parse_payload`.
# **Corrige apres la revue de 5.17 (bloquant B2)**: les deux appelants du depot passent
# desormais par `parse_payload` -- `reconstruct-project` lit le texte du QR comme le
# scan --, donc aucun des deux n'atteint plus cette garde. Elle reste, et elle n'est pas
# morte pour autant: `reconstruct_project_manifest` est une fonction **publique** qui
# accepte des dictionnaires, et un appelant qui en fabrique un a la main n'a traverse
# aucun parseur. La garde est sa derniere ligne, pas la premiere.
SUPPORTED_PAYLOAD_SCHEMA_VERSION = PAYLOAD_SCHEMA_VERSION
# v2.1 depuis le 2026-08-04 (`decisions-2026-08-04.md`): la cadence cible est
# une propriete du lot, pas du projet. Un manifest reconstruit la porte donc
# dans `lots[].fps_target` et laisse `video` vide.
MANIFEST_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

# --- Story 5.7 -------------------------------------------------------------
# Ces trois constantes sont **partagees** par les deux chemins qui appellent
# `reconstruct_project_manifest`: la sous-commande `reconstruct-project` (des
# payloads JSON, aucune planche) et la chaine de scan (des planches
# numerisees). Les defauts ci-dessous sont ceux de la premiere, pour qu'elle
# reste inchangee a l'octet pres; la seconde passe explicitement les siens.

#: Etat de lot pose par defaut, c'est-a-dire par `reconstruct-project`.
#: EPIC5-ARB-7 a tranche le sens des deux etats: `reconstruction` = « ce lot a
#: ete recree dans un projet vierge depuis des payloads », `scan` = « les
#: planches de ce lot ont ete scannees et ses frames reconstruites ».
DEFAULT_LOT_STATE = "reconstruction"

#: Valeurs fermes de `reconstruction.origin` (EPIC5-ARB-9). L'**absence** du
#: champ n'est jamais « inconnu »: elle signifie « manifest d'origine »,
#: l'extraction ecrivant une section `reconstruction` vide sans jamais passer
#: par ici.
ORIGIN_PAYLOADS = "payloads"
ORIGIN_SCAN = "scan"
RECONSTRUCTION_ORIGINS: tuple[str, ...] = (ORIGIN_PAYLOADS, ORIGIN_SCAN)


class ReconstructionError(RuntimeError):
    """Raised when a project cannot be safely reconstructed from the given inputs.

    Always favor raising this over producing a manifest that looks valid but
    hides missing or conflicting data (AC2: no false success).
    """


def _require_fields(payload: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ReconstructionError(
            f"Payload de reconstruction incomplet ({context}): champ(s) manquant(s) {missing}."
        )


def _page_role(payload: dict[str, Any]) -> str:
    """Role declare par ce payload, defaut de relecture compris.

    **Un seul point de lecture** pour les trois consommateurs de ce module -- la garde
    d'emplacements, la garde de placement de la page de calibration et la persistance --
    parce que trois `payload.get("page_role")` disperses, c'est trois occasions d'oublier
    le defaut, donc trois branches qui divergent. Le refus d'une valeur presente et
    invalide reste a `_validate_page_payload`, qui passe avant tout le reste.
    """
    return str(payload.get("page_role", PAGE_ROLE_DEFAULT_AT_REREAD))


def _validate_page_payload(payload: dict[str, Any]) -> None:
    # **Les champs exiges dependent du role** (story 5.23, 2026-08-18; story 2.7 y
    # ajoute `timecode_base_fps`). Une page de calibration ne declare ni projet, ni
    # rush, ni lot, ni cadence (cible ou source): elle sert toute une chaine de scan,
    # et les cinq champs sont retires de son payload par le contrat
    # 2.3/2.1 (`io.payload.CALIBRATION_ABSENT_FIELDS`). Les exiger ici rendait **illisible a
    # la relecture toute feuille produite depuis l'AC 8bis**, avec un motif qui parle de
    # payload incomplet -- c'est-a-dire qui accuse la feuille d'etre abimee alors qu'elle
    # est conforme.
    #
    # Le defaut etait deja livre au 2026-08-17 (l'AC 8bis a retire trois champs sans
    # toucher a cette liste) et l'elargissement de la liste au `project_id` l'a rendu
    # total. Il se ferme ici, du seul cote ou il peut l'etre: la liste reste **entiere**
    # pour une planche d'images, ou l'absence d'un de ces champs est une vraie
    # corruption.
    #
    # La liste est **derivee** de celle du contrat d'ecriture et non recopiee amputee:
    # deux listes divergeraient au prochain champ, et la divergence serait silencieuse a
    # l'ecriture et fatale a la relecture -- exactement le defaut que la table de cles
    # courtes existe pour interdire.
    if _page_role(payload) == PAGE_ROLE_CALIBRATION:
        exiges = tuple(champ for champ in REQUIRED_PAGE_FIELDS
                       if champ not in CALIBRATION_ABSENT_FIELDS)
    else:
        exiges = REQUIRED_PAGE_FIELDS
    _require_fields(payload, exiges, f"page_index={payload.get('page_index')!r}")
    # Garde d'emplacements **conditionnelle au role** (story 5.16, AC 3). Seconde
    # implementation, independante de celle de `io.payload.validate_payload`, et
    # les deux mordent: cette fonction relit un document qui n'a traverse aucun
    # parseur quand `reconstruct_project_manifest` est appelee directement.
    # Conditionnelle dans les **deux** sens, meme motif qu'a l'ecriture: une
    # planche d'images sans emplacement reste refusee (un QR dont les
    # emplacements ont ete perdus est un mode d'echec reel du chemin de scan), et
    # une page de calibration qui en porterait est refusee aussi.
    # Le role est **resolu contre le vocabulaire ferme avant** la garde d'emplacements,
    # exactement comme `io.payload.validate_payload` le fait a l'ecriture (finding F2 de
    # la couche 2). Sans cela, un role hors vocabulaire tombait dans la branche `elif` des
    # planches d'images: une page declarant `'x'` **avec** des emplacements etait acceptee,
    # et la meme page **sans** emplacement recevait un refus qui attribuait le role `'i'`
    # -- un message qui nomme le mauvais role envoie diagnostiquer la mauvaise chose. Le
    # commentaire jumeau d'`io.payload` avait nomme ce piege d'avance; c'est la seconde
    # implementation qui ne portait pas le volet.
    try:
        page_role = validate_page_role(_page_role(payload))
    except UnknownPageRoleError as error:
        raise ReconstructionError(
            f"Payload de reconstruction invalide (page_index="
            f"{payload.get('page_index')!r}): {error}"
        ) from error
    slots = payload.get("slots")
    if not isinstance(slots, list):
        raise ReconstructionError(
            f"Payload de reconstruction invalide (page_index={payload.get('page_index')!r}): "
            "'slots' doit etre une liste."
        )
    if page_role == PAGE_ROLE_CALIBRATION:
        if slots:
            raise ReconstructionError(
                f"Payload de reconstruction invalide (page_index="
                f"{payload.get('page_index')!r}): la page declare le role "
                f"{PAGE_ROLE_CALIBRATION!r} ({page_role_label(PAGE_ROLE_CALIBRATION)}) "
                f"et porte pourtant {len(slots)} emplacement(s). Une page de "
                "calibration ne porte aucune frame."
            )
    elif not slots:
        raise ReconstructionError(
            f"Payload de reconstruction invalide (page_index={payload.get('page_index')!r}): "
            f"'slots' doit etre une liste non vide pour le role {PAGE_ROLE_IMAGES!r} "
            f"({page_role_label(PAGE_ROLE_IMAGES)}); seule une page de calibration "
            f"(role {PAGE_ROLE_CALIBRATION!r}) en est dispensee."
        )
    for slot in slots:
        if not isinstance(slot, dict):
            raise ReconstructionError(
                f"Payload de reconstruction invalide (page_index={payload.get('page_index')!r}): "
                "chaque slot doit etre un objet."
            )
        _require_fields(slot, REQUIRED_SLOT_FIELDS, f"slot dans page_index={payload.get('page_index')!r}")


def _check_calibration_page_placement(
    pages_by_index: dict[Any, dict[str, Any]],
    *,
    page_count: int,
    missing_indexes: list[Any],
) -> None:
    """Un lot porte **au plus une** page de calibration, et elle est a l'index zero.

    Finding F1 de la couche 2 de la revue de 5.16, mesure et non suppose. `page_role`
    n'est pas de niveau lot -- deliberement, et c'est juste: c'est ce qui permet a deux
    pages du meme lot d'avoir des roles differents. Mais rien a la relecture ne verifiait
    l'unicite ni la position, et les trois formes suivantes se reconstruisaient toutes en
    `status = complete`:

    * deux pages de calibration (index 0 et 2): deux emplacements perdus en silence;
    * une page de calibration seule a l'index 2: la premiere page du lot n'en est plus une;
    * **un lot entierement en role calibration**: `status = complete`, zero emplacement,
      aucun `missing_pages`. Une page presente mais vide sort du seul mecanisme qui
      declare un trou -- c'est le faux succes de R12 dans sa forme la plus complete.

    Aucune de ces formes n'est produite par `pdf_composition`, qui insere exactement une
    page a l'index zero. Mais le depot pose partout que le lecteur est une implementation
    **independante** du producteur -- c'est l'argument ecrit de la garde d'emplacements
    dupliquee entre `io.payload` et ce module -- et sur ce point precis l'independance
    voulait dire qu'aucun des deux ne verifiait.

    Le refus **nomme les index en cause**: un operateur qui rescanne doit savoir quelle
    feuille reprendre, jamais « le lot ».
    """
    calibration = sorted(
        index for index, payload in pages_by_index.items()
        if _page_role(payload) == PAGE_ROLE_CALIBRATION
    )
    if len(calibration) > MAX_CALIBRATION_PAGES_PER_LOT:
        raise ReconstructionError(
            f"Conflit de reconstruction: {len(calibration)} pages declarent le role "
            f"{PAGE_ROLE_CALIBRATION!r} ({page_role_label(PAGE_ROLE_CALIBRATION)}) aux "
            f"index {calibration}, alors qu'un lot n'en porte qu'une "
            f"({MAX_CALIBRATION_PAGES_PER_LOT}). Chaque page de calibration "
            "supplementaire est une planche d'images dont les emplacements seraient "
            "perdus en silence, et le lot se declarerait complet sans elles."
        )
    if calibration and calibration[0] != CALIBRATION_PAGE_INDEX:
        raise ReconstructionError(
            f"Conflit de reconstruction: la page de calibration est declaree a l'index "
            f"{calibration[0]} alors que sa place est l'index "
            f"{CALIBRATION_PAGE_INDEX}. Cet index n'est pas un choix: `page_count` est "
            "de niveau lot et compte la page de calibration, donc la lire ailleurs "
            "revient a declarer une planche d'images de moins que le lot n'en porte."
        )
    # Troisieme volet, et c'est le plus grave des trois: un lot dont **toutes** les pages
    # ont ete lues et dont aucune ne porte de planche d'images. Les deux gardes ci-dessus
    # ne l'attrapent pas au cardinal 1 (une seule page, de role calibration, a l'index
    # zero: les deux sont satisfaites), et le lot sortait alors `complete` avec zero
    # emplacement et sans `missing_pages` -- un lot sans une seule frame declare fini. La
    # garde ne mord que sur un lot **completement lu**: un lot dont on n'a scanne que la
    # page de calibration est `partial`, ce qui est le verdict juste et non un echec.
    if not missing_indexes and not any(
        _page_role(payload) == PAGE_ROLE_IMAGES
        for payload in pages_by_index.values()
    ):
        raise ReconstructionError(
            f"Conflit de reconstruction: les {page_count} page(s) du lot ont ete lues et "
            f"aucune ne porte le role {PAGE_ROLE_IMAGES!r} "
            f"({page_role_label(PAGE_ROLE_IMAGES)}). Un lot sans planche d'images ne "
            "porte aucune frame: le declarer complet serait le faux succes que le "
            "cardinal attendu existe pour empecher."
        )


#: Motif du refus d'une pile qui **mele** une page de calibration a des planches
#: d'images (story 5.23, AC 10, `EPIC5-ARB-85`). C'est un **code**, pas un message: le
#: message parle a l'operateur et se reecrira, le code sert a distinguer les deux refus
#: de pile l'un de l'autre sans qu'un test ait a reconnaitre une phrase.
REFUS_PILE_MIXTE = "pile-mixte-calibration-et-planches"

#: Motif du refus d'une pile qui ne porte **aucune** planche d'images. Distinct du
#: precedent, et il doit le rester: la pile mixte est un geste a corriger (deux passes
#: separees, `EPIC5-ARB-86`), la pile sans planche est une passe qui n'avait rien a
#: reconstruire. Les confondre enverrait l'operateur separer une pile qui l'est deja.
REFUS_PILE_SANS_PLANCHE = "pile-sans-planche-d-images"


def _refus_de_pile(code: str, message: str) -> ReconstructionError:
    """Construire un refus de pile en lui attachant son **code**.

    Le code voyage sur l'exception (`.reason`) et non dans le texte: un appelant qui
    voudrait distinguer les deux refus n'a pas a analyser une phrase francaise, et le
    message reste libre d'etre reecrit pour l'operateur sans casser personne.
    """
    erreur = ReconstructionError(message)
    erreur.reason = code
    return erreur


def _nommer_page_sans_identite_de_lot(payload: dict[str, Any]) -> str:
    """Nommer **la** feuille en cause, jamais « la pile ».

    Un operateur qui recoit un refus doit savoir quelle feuille retirer du bac. Une page
    de calibration ne porte ni projet, ni rush, ni lot: les deux seules choses qui la
    designent sont son rang de page -- qu'elle garde -- et le libelle de sa chaine de
    scan, qui est justement ce qu'elle est seule a porter
    (`io.payload.CALIBRATION_ONLY_FIELDS`).
    """
    role = _page_role(payload)
    designation = f"page_index={payload.get('page_index')!r} (role {role!r}"
    libelle = payload.get(SCAN_CHAIN_LABEL_FIELD)
    if libelle:
        designation += f", chaine de scan {libelle!r}"
    return designation + ")"


def _partition_de_la_pile(
    payloads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separer la pile en `(pages sans identite de lot, planches qui en portent une)`.

    Extraite de `_check_pile_homogene` par `EPIC5-ARB-92`, et pour une raison qui est
    tout l'objet de l'extraction: la CLI doit desormais **reconnaitre** la pile qui ne
    porte que des pages de calibration -- pour proposer la bascule en mode calibration
    au lieu de refuser -- et une seconde redaction de la partition, ecrite dans
    `cli.py`, divergerait de celle qui decide le refus. Deux partitions, ce sont deux
    verites sur la meme pile: la bascule mordrait alors sur une pile que le refus ne
    reconnait pas, ou l'inverse.

    La partition se lit **sur les champs, pas sur le role** -- voir
    `_check_pile_homogene`, qui porte le motif de ce choix et ses deux consequences
    voulues.
    """
    sans_identite: list[dict[str, Any]] = []
    porteuses: list[dict[str, Any]] = []
    for payload in payloads:
        cible = (sans_identite
                 if any(champ not in payload for champ in _LOT_LEVEL_FIELDS)
                 else porteuses)
        cible.append(payload)
    return sans_identite, porteuses


def pile_sans_planche_d_images(payloads: list[dict[str, Any]]) -> bool:
    """La pile ne porte-t-elle **que** des pages sans identite de lot ? (`EPIC5-ARB-92`)

    C'est exactement la condition sous laquelle `_check_pile_homogene` leve
    `REFUS_PILE_SANS_PLANCHE`, et c'est litteralement la meme partition qui la calcule:
    `cli.scan_command` s'en sert pour proposer la bascule en mode calibration plutot que
    d'opposer ce refus (`EPIC5-ARB-92`, « refuser cette pile revient a refuser le regime
    nominal du livrable de la story »).

    **Une pile vide rend `False`**, et ce n'est pas un detail de bord: `scan` n'atteint
    ce predicat que sur des pages identifiees, mais un predicat qui rendrait `True` sur
    rien du tout ferait basculer en calibration une passe qui n'a rien lu -- une bascule
    sur une pile vide serait un `calibrate` sans page de calibration, donc un echec
    deguise en geste utile.

    **Elle ne dit rien de la pile mixte**, qui reste refusee (`EPIC5-ARB-86`, deux
    passes separees): une pile qui porte au moins une planche d'images rend `False`.
    """
    sans_identite, porteuses = _partition_de_la_pile(payloads)
    return bool(sans_identite) and not porteuses


def planches_d_images_de_la_pile(
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Les pages de la pile qui portent une identite de lot. `EPIC11-ARB-266`.

    Meme partition que :func:`pile_sans_planche_d_images` et que le refus de
    `_check_pile_homogene` -- **elle n'en ecrit pas une seconde**, et c'est le
    motif pour lequel `EPIC5-ARB-92` avait extrait
    :func:`_partition_de_la_pile` : deux partitions sont deux verites sur la
    meme pile, et l'une mordrait sur ce que l'autre accepte.

    Elle rend la LISTE plutot qu'un booleen parce que son appelant --
    `scan_calibrate`, qui refuse une pile mixte en calibration -- en nomme le
    cardinal a l'operateur. `pile_sans_planche_d_images` ne suffisait pas : elle
    rend `False` aussi bien sur une pile mixte que sur une pile de planches
    SEULES, deux regimes qui appellent deux refus differents.
    """
    _, porteuses = _partition_de_la_pile(payloads)
    return porteuses


def _check_pile_homogene(payloads: list[dict[str, Any]]) -> None:
    """Refuser **nommement** une pile dont une page ne decrit aucun lot (AC 10).

    Le defaut ferme ici, mesure au `baseline_commit` de l'amendement du 2026-08-18: 60
    `KeyError: 'project_id'` et 2 `KeyError: 'lot_id'` sur 42 tests, tous issus de
    `_check_lot_consistency`, qui lit les champs de niveau lot **en acces nu** sur la
    premiere page venue. Depuis l'AC 8bis (et la story 2.7 pour le cinquieme) une page
    de calibration ne porte plus aucun des cinq (`io.payload.CALIBRATION_ABSENT_FIELDS`):
    la poser sur la vitre avec des
    planches faisait donc tomber la passe entiere en traceback, sans qu'aucun message ne
    dise ce qu'il fallait faire. C'est le **sixieme** acces nu de cette famille, apres
    `scan_detection` (deux), `io/reconstruction._validate_page_payload`,
    `scan_output_frames._lot_identity` et `cli._page_identifier`.

    **Ce refus n'autorise rien** (`EPIC5-ARB-86`): deux passes separees restent le
    regime nominal, et la pile en vrac est reportee a sa propre story. Un plantage
    devient un refus, pas une fonctionnalite.

    **La partition se lit sur les champs, pas sur le role**, et c'est delibere. La
    question a laquelle cette garde repond est « cette page decrit-elle un lot ? », et
    c'est exactement la condition sous laquelle `_check_lot_consistency` s'ecroulait.
    Deux consequences, toutes deux voulues:

    * une page de calibration ecrite **avant** l'AC 8bis, qui declarait encore les
      quatre champs, traverse cette garde sans etre refusee -- elle est rangee en
      `porteuses`, comme une planche. **Mesure du 2026-08-19, et elle corrige ce que ce
      docstring affirmait**: on lisait ici « se comporte comme avant -- ce refus ne
      change pas le sort d'une feuille deja imprimee, ce que la regle du depot exige ».
      C'est vrai de cette fonction prise seule et **faux de la chaine**: une telle
      feuille n'atteint jamais cette garde, parce que `io.payload.validate_payload` la
      refuse en amont, au decodage du QR (`scan_chain_label` manquant, et les quatre
      champs presents). Ce refus amont est **voulu** -- `EPIC5-ARB-90`: « aucune
      compatibilite pour les feuilles imprimees avant le 17 aout », aucune tolerance de
      relecture ne sera ecrite. Ce qui a ete corrige le 2026-08-19 est le **motif
      annonce** de ce refus, qui accusait le payload sans nommer le tirage ni le geste,
      jamais la decision de refuser;
    * un payload de planche d'images tronque ne peut pas se faufiler ici pour autant:
      `_validate_page_payload` passe avant et refuse deja une planche a qui il manque
      l'un des cinq. La lecture par champs ne peut donc pas prendre une corruption
      pour une page de calibration, qui est le piege que `io.payload._is_calibration_page`
      nomme d'avance.
    """
    sans_identite, porteuses = _partition_de_la_pile(payloads)

    if not sans_identite:
        return

    nommees = ", ".join(_nommer_page_sans_identite_de_lot(p) for p in sans_identite)
    if porteuses:
        raise _refus_de_pile(
            REFUS_PILE_MIXTE,
            f"Conflit de reconstruction: {len(sans_identite)} page(s) de calibration "
            f"[{nommees}] ont ete lues dans la meme passe que {len(porteuses)} planche(s) "
            "d'images. Une page de calibration sert une chaine de scan entiere et non un "
            "lot: elle ne declare ni projet, ni rush, ni lot, ni cadence "
            "(io.payload.CALIBRATION_ABSENT_FIELDS), donc aucune identite de lot ne peut "
            "etre tiree de cette pile sans l'inventer. Scannez la page de calibration "
            "dans une passe separee (`scan ... calibrate`), puis les planches d'images "
            "dans une autre.",
        )
    raise _refus_de_pile(
        REFUS_PILE_SANS_PLANCHE,
        f"Conflit de reconstruction: la pile ne porte aucune planche d'images, seulement "
        f"{len(sans_identite)} page(s) de calibration [{nommees}]. Une page de "
        "calibration ne decrit aucun lot: il n'y a ni frame a ecrire, ni identite de lot "
        "a reconstruire. Pour consigner le profil de la chaine, la commande est "
        "`scan ... calibrate`.",
    )


# **Les acces nus de la fonction ci-dessous sont sous la garde de `_check_pile_homogene`**,
# appelee par chacun de ses deux appelants du depot juste avant elle (story 5.23, AC 10).
# Ils ne sont donc atteints que par des pages qui declarent les dix champs de niveau lot.
#
# La garde vit **hors** de cette fonction, et la raison qui subsiste est de fond: cette
# fonction repond a « ces pages declarent-elles le meme lot ? », pas a « cette pile
# decrit-elle un lot ? » -- ce sont deux questions, et la seconde se tranche avant la
# premiere.
#
# Une seconde raison a existe et n'existe plus: la story 5.16 tenait `_LOT_LEVEL_FIELDS`
# et cette fonction sous une garde d'**egalite au source**, ce qui interdisait d'y ecrire
# la garde de pile. Cette garde a ete **retiree** le 2026-08-18 (`EPIC5-ARB-95`: un
# garde-fou de non-regression meurt avec sa story), apres avoir mesure par injection
# ciblee ce qu'elle protegeait encore -- 17 mutants, tous tues par des tests de
# comportement, sauf `page_role` promu au niveau lot, dont le test manquant a ete ecrit
# avant le retrait. La forme actuelle n'est donc **pas** repliee dans cette fonction, et
# c'est un choix explicite du meme arbitrage: la remanier serait du remue-menage sans
# gain, l'ordre d'appel etant deja sous assertion.
#
# L'ordre d'appel n'est pas laisse a la discipline: il est **sous assertion** dans
# `tests/unit/test_pile_mixte_refus.py`, qui balaye les appels du depot.
def _check_lot_consistency(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the shared lot-level values, raising ReconstructionError on any conflict."""
    reference = {field: payloads[0][field] for field in _LOT_LEVEL_FIELDS}
    for payload in payloads[1:]:
        for field in _LOT_LEVEL_FIELDS:
            if payload[field] != reference[field]:
                raise ReconstructionError(
                    "Conflit de reconstruction: la page "
                    f"{payload.get('page_index')!r} declare {field}={payload[field]!r} mais une "
                    f"autre page declare {field}={reference[field]!r}. Toutes les pages d'un meme "
                    "lot doivent partager ces identifiants."
                )
    return reference


def _existing_lot_fps_target(
    existing_manifest: dict[str, Any], reference: dict[str, Any]
) -> tuple[str, Any] | None:
    """Cadence cible que le manifest local attribue **au lot reconstruit**.

    Depuis la v2.1, la cadence cible vit dans `lots[].fps_target`: c'est celle
    du lot portant le meme `lot_id` qui fait foi, et un autre lot du meme rush
    a une autre cadence n'est plus un conflit mais le cas nominal. Repli sur
    `video.fps_target` pour un manifest local encore en v2.0, ou cette valeur
    etait la seule disponible.
    """
    for lot in existing_manifest.get("lots", []) or []:
        if not isinstance(lot, dict) or lot.get("lot_id") != reference["lot_id"]:
            continue
        fps_target = lot.get("fps_target")
        if fps_target is not None:
            return f"lots[{reference['lot_id']}].fps_target", fps_target

    fps_target = (existing_manifest.get("video") or {}).get("fps_target")
    if fps_target is not None:
        return "video.fps_target", fps_target
    return None


def _existing_lot_timecode_base_fps(
    existing_manifest: dict[str, Any], reference: dict[str, Any]
) -> tuple[str, Any] | None:
    """Cadence SOURCE que le manifest local attribue **au lot reconstruit** (story 2.7).

    Meme famille que `_existing_lot_fps_target` juste au-dessus, sans repli:
    `timecode_base_fps` n'a jamais vecu ailleurs que sur `lots[]` (pas
    d'equivalent `video.*` d'une version anterieure a couvrir).
    """
    for lot in existing_manifest.get("lots", []) or []:
        if not isinstance(lot, dict) or lot.get("lot_id") != reference["lot_id"]:
            continue
        timecode_base_fps = lot.get("timecode_base_fps")
        if timecode_base_fps is not None:
            return f"lots[{reference['lot_id']}].timecode_base_fps", timecode_base_fps
    return None


#: L'origine d'un lot **adopte** (`EPIC7-ARB-101`), portee par son entree de
#: manifest. Champ additif : un lot ne le porte que s'il vient d'ailleurs, et
#: son absence est le cas nominal d'un lot ne dans ce projet.
#:
#: **Le motif est fonctionnel avant d'etre moral.** Le papier, lui, continue de
#: dire son projet d'origine, et il le dira toujours -- l'encre ne se met pas a
#: jour. Sans cette trace, chaque nouvelle feuille du meme lot rescannee plus
#: tard serait reclassee « hors perimetre » et il faudrait re-adopter a chaque
#: passe ; avec elle, le second scan atterrit silencieusement au bon endroit
#: (`scan_sorting.trier_les_pages`).
CHAMP_ORIGINE_ADOPTEE = "adopted_from_project_id"


def adopter_les_payloads(page_payloads, *, project_id_cible: str):
    """Substituer l'identite de projet AVANT reconstruction (`EPIC7-ARB-101`).

    « J'aimerais qu'on puisse effectivement ajouter un rush / planche / scan
    issu d'un autre projet **dans ce projet**. C'est comme si j'avais ajoute le
    rush dans le projet, extrait dans le projet, genere la planche dans le
    projet puis scanne. » (Egan, 2026-08-27.)

    **Ce que l'adoption est, structurellement.** `project_id` est un champ
    RACINE du manifest ; les entrees de `rushes[]` et de `lots[]` n'en portent
    aucun. Un lot est donc **neutre en projet** : il appartient au manifest qui
    le contient, pas a un projet ecrit dans ses champs. Adopter ne demande
    aucun changement de schema -- il suffit que la reconstruction lise
    l'identite du projet **courant** la ou le payload declare la sienne.

    **Ce que l'adoption n'est pas.** Elle ne desarme aucune garde : elle leur
    donne une entree deja resolue. `_check_manifest_conflicts` continue de
    refuser tout conflit **non decide** -- une cadence cible divergente, une
    cadence source contradictoire, un etat de lot impossible. Ce qui est decide
    ici, et seulement ici, c'est l'identite de projet.

    Rend le couple `(payloads_adoptes, origines_par_lot)`. `origines_par_lot`
    associe chaque `lot_id` au projet d'ou il vient, et vaut vide quand rien
    n'a ete adopte -- une passe dont tous les payloads declarent deja le projet
    cible traverse cette fonction sans rien changer.
    """
    if not isinstance(project_id_cible, str) or not project_id_cible.strip():
        raise ReconstructionError(
            "Adoption impossible: l'identite du projet d'accueil est vide. "
            "Elle se lit au manifest du projet cible, jamais d'un nom de "
            "dossier."
        )
    adoptes = []
    origines: dict[str, str] = {}
    for payload in page_payloads:
        origine = payload.get("project_id")
        if origine == project_id_cible:
            adoptes.append(payload)
            continue
        if not isinstance(origine, str) or not origine.strip():
            raise ReconstructionError(
                "Adoption impossible: une page ne declare aucun project_id. "
                "Adopter, c'est remplacer une origine connue par le projet "
                "d'accueil; une origine absente ne se remplace pas, elle se "
                "refuse."
            )
        adopte = dict(payload)
        adopte["project_id"] = project_id_cible
        adoptes.append(adopte)
        lot_id = payload.get("lot_id")
        if lot_id is not None:
            origines[lot_id] = origine
    return adoptes, origines



def origine_adoptee(existing_manifest: dict[str, Any] | None,
                    lot_id: object) -> str | None:
    """Le projet d'ou ce lot a ete adopte, ou ``None`` (`EPIC7-ARB-101`).

    **Point unique de lecture de l'adoption**, et c'est ce qui la rend
    transitive : une fois l'origine inscrite au manifest, toutes les gardes du
    depot la consultent -- la reconstruction ici, le tri par
    `scan_sorting.lots_adoptes_du_manifest`, et `check_scan_conflicts` par
    ricochet puisqu'il passe par la reconstruction. Personne n'a a se transmettre
    un drapeau de passe en passe : la decision vit dans le document, pas dans un
    appel.
    """
    if not isinstance(existing_manifest, dict):
        return None
    for lot in existing_manifest.get("lots") or ():
        if not isinstance(lot, dict) or lot.get("lot_id") != lot_id:
            continue
        origine = lot.get(CHAMP_ORIGINE_ADOPTEE)
        return origine if isinstance(origine, str) and origine else None
    return None


def _check_manifest_conflicts(existing_manifest: dict[str, Any] | None,
                              reference: dict[str, Any],
                              *, adoption: bool = False) -> None:
    if not existing_manifest:
        return

    existing_project_id = existing_manifest.get("project_id")
    # **Une adoption deja inscrite au manifest resout ce conflit** :
    # `adopted_from_project_id` dit, noir sur blanc, que l'operateur a decide
    # que les planches declarant CE projet-la appartiennent a celui-ci. Le
    # papier continue de declarer son origine et le declarera toujours ; sans
    # cette lecture, chaque nouvelle passe du meme lot rebuterait sur le meme
    # conflit deja tranche.
    if origine_adoptee(existing_manifest, reference["lot_id"]) == reference[
            "project_id"]:
        adoption = True
    if (not adoption and existing_project_id is not None
            and existing_project_id != reference["project_id"]):
        raise ReconstructionError(
            "Conflit de reconstruction: le manifest local declare project_id="
            f"{existing_project_id!r} mais les payloads embarques declarent "
            f"project_id={reference['project_id']!r}."
        )

    # Un projet porte plusieurs rushs (`decisions-2026-08-04.md`): la presence
    # d'un autre rush dans le manifest local n'est pas un conflit. Le conflit
    # est que le manifest local declare des rushs et qu'aucun ne soit celui
    # des pages recues.
    declared_rush_ids = [
        rush.get("rush_id")
        for rush in existing_manifest.get("rushes", []) or []
        if isinstance(rush, dict) and rush.get("rush_id") is not None
    ]
    # **Un rush ADOPTE est un rush neuf legitime** (`EPIC7-ARB-101`). Cette
    # garde refuse, a raison, qu'une passe fasse apparaitre un rush inconnu
    # dans un projet qui en declare deja : ce serait, presque toujours, un scan
    # arrive au mauvais endroit. L'adoption est precisement le cas ou ce n'est
    # pas une erreur mais une decision -- « c'est comme si j'avais ajoute le
    # rush dans le projet ». La garde n'est donc pas affaiblie : elle recoit une
    # entree deja resolue, et continue de refuser tout ce qui n'a pas ete
    # decide.
    if (not adoption and declared_rush_ids
            and reference["rush_id"] not in declared_rush_ids):
        raise ReconstructionError(
            "Conflit de reconstruction: le manifest local reference rush_id="
            f"{declared_rush_ids[0]!r} qui ne correspond a aucune page embarquee "
            f"(attendu rush_id={reference['rush_id']!r})."
        )

    declared = _existing_lot_fps_target(existing_manifest, reference)
    if declared is not None and declared[1] != reference["fps_target"]:
        location, existing_fps_target = declared
        raise ReconstructionError(
            f"Conflit de reconstruction: le manifest local declare {location}="
            f"{existing_fps_target!r} mais les payloads embarques declarent "
            f"fps_target={reference['fps_target']!r}."
        )

    # Story 2.7: meme confrontation, meme famille, pour la cadence SOURCE --
    # AVANT toute ecriture, jamais un ecrasement silencieux.
    declared_source = _existing_lot_timecode_base_fps(existing_manifest, reference)
    if declared_source is not None and declared_source[1] != reference["timecode_base_fps"]:
        location, existing_timecode_base_fps = declared_source
        raise ReconstructionError(
            f"Conflit de reconstruction: le manifest local declare {location}="
            f"{existing_timecode_base_fps!r} mais les payloads embarques declarent "
            f"timecode_base_fps={reference['timecode_base_fps']!r}."
        )


def _merge_entries(
    existing_manifest: dict[str, Any] | None,
    section: str,
    id_field: str,
    reconstructed: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fusionner l'entree reconstruite dans les entrees deja declarees localement.

    Un projet v2.1 porte plusieurs rushs et plusieurs lots
    (`decisions-2026-08-04.md`). Reconstruire **un** lot depuis des pages
    scannees ne dit rien des autres: les ecraser reviendrait a perdre, sans un
    mot, les empreintes de selection et les cardinaux attendus de tous les
    autres lots du projet, alors que `cli.py` reecrit `project.json` en place.

    L'entree de meme identifiant est **completee**, pas remplacee: ce que la
    reconstruction sait (statut, cadence cible, chemin source) prime, et ce
    qu'une extraction anterieure avait ecrit et que le scan ne peut pas
    retrouver est conserve.
    """
    merged: list[dict[str, Any]] = []
    replaced = False
    for entry in (existing_manifest or {}).get(section, []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get(id_field) == reconstructed.get(id_field):
            merged.append({**entry, **reconstructed})
            replaced = True
        else:
            merged.append(dict(entry))
    if not replaced:
        merged.append(reconstructed)
    return merged


def _existing_source_path(existing_manifest: dict[str, Any] | None, rush_id: str) -> str | None:
    if not existing_manifest:
        return None
    for rush in existing_manifest.get("rushes", []) or []:
        if rush.get("rush_id") == rush_id:
            source_path = rush.get("source_path")
            if isinstance(source_path, str) and source_path:
                return source_path
    return None


def _existing_lot_state(
    existing_manifest: dict[str, Any] | None, lot_id: Any
) -> str | None:
    """Etat courant du lot vise dans le manifest local, `None` s'il n'en a pas.

    `None` est une valeur **licite** et non un defaut de lecture: c'est celle
    d'un lot qui n'existe pas encore, et la garde de transition l'accepte sans
    condition.
    """
    for lot in (existing_manifest or {}).get("lots", []) or []:
        if isinstance(lot, dict) and lot.get("lot_id") == lot_id:
            state = lot.get("state")
            return state if isinstance(state, str) else None
    return None


def _resolve_lot_state(
    existing_manifest: dict[str, Any] | None, lot_id: Any, requested_state: str
) -> str:
    """Poser l'etat demande si la garde l'accepte, conserver l'etat en place sinon.

    `io.manifest.validate_lot_state_transition` est le **seul** juge de l'ordre
    des etats: aucune comparaison d'index n'est reecrite ici, et plus aucun
    etat n'est affecte en dur (AC 3). La garde est ordonnee -- `extraction`
    (0), `pdf` (1), `scan` (2), `reconstruction` (3), `encode` (4) -- et refuse
    tout retour en arriere.

    Un refus **n'est pas une erreur**: reconstruire ou rescanner un lot deja
    passe en `reconstruction` ou en `encode` est le scenario nominal « projet
    recree depuis des payloads, puis planches scannees ». La regle qui ferme le
    sujet: cette fonction **n'abaisse jamais** un etat, elle conserve celui en
    place et laisse l'appelant en informer l'operateur. Le seul echec dur reste
    le conflit de contenu, jamais l'ordre des etats.
    """
    # L'etat **demande** est verifie a part, et son refus est une erreur dure:
    # confondre « l'appelant demande un etat qui n'existe pas » avec « la garde
    # refuse un retour en arriere » ferait taire un defaut d'appel en
    # conservant silencieusement l'etat en place.
    try:
        validate_lot_state_transition(None, requested_state)
    except ValidationError as error:
        raise ReconstructionError(
            f"Etat de lot demande invalide pour la reconstruction: {error}"
        ) from error

    current = _existing_lot_state(existing_manifest, lot_id)
    if current is not None and current not in LOT_STATES:
        # Le refus est le bon, mais il arrivait par le schema, sur le manifest
        # **reconstruit**: le diagnostic accusait le document produit alors que
        # la valeur fautive vient du document **relu**, ce qui est le contraire
        # de ce que l'operateur doit corriger (revue couche 1, F9).
        raise ReconstructionError(
            f"Le manifest local declare lots[{lot_id!r}].state={current!r}, qui "
            f"n'appartient pas au vocabulaire ferme des etats de lot "
            f"({', '.join(LOT_STATES)}). La valeur fautive est dans le manifest "
            "relu, pas dans le document reconstruit."
        )
    try:
        validate_lot_state_transition(current, requested_state)
    except ValidationError:
        # `current` ne peut pas valoir `None` sur cette branche: la garde
        # accepte `None -> <etat connu>` sans condition. Un refus implique donc
        # un etat reellement pose, et le retour reste une chaine.
        return current
    return requested_state


def _validate_against_schema(manifest: dict[str, Any]) -> None:
    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        first_error = errors[0]
        location = ".".join(str(part) for part in first_error.path)
        detail = f" at '{location}'" if location else ""
        raise ReconstructionError(f"Manifest reconstruit invalide{detail}: {first_error.message}")


def reconstruct_project_manifest(
    page_payloads: list[dict[str, Any]],
    existing_manifest: dict[str, Any] | None = None,
    *,
    lot_state: str = DEFAULT_LOT_STATE,
    origin: str = ORIGIN_PAYLOADS,
    origines_adoptees: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Rebuild a coherent v2 project manifest from decoded page payloads.

    `page_payloads` mirrors the minimal reconstructive payload described in
    ARCHITECTURE_DETAILED.md sections 3 and 6, i.e. exactly what
    `io/payload.build_page_payload` emits: one dict per available/scanned
    page, with base-zero `page_index` (section 3.1). A partial set (fewer
    pages than the declared `page_count`) still produces a valid manifest
    flagged `reconstruction.status = "partial"`, with `missing_pages` listed
    in that same base-zero index space; missing critical fields or conflicting
    identifiers raise ReconstructionError instead of a silent/false success
    (AC2).

    Two independent calls with the same page payloads (regardless of order or
    exact duplicates) always return an identical manifest (AC3): the output
    never depends on input order, local paths, or the machine it runs on.

    Story 5.7 -- deux parametres, et deux seulement, parce que la fonction est
    **partagee** par deux chemins que rien d'autre ne distingue:

    * ``lot_state`` est l'etat que le lot reconstruit doit porter. Il n'est
      plus affecte en dur: il passe par ``validate_lot_state_transition``
      (``_resolve_lot_state``), qui conserve l'etat en place quand la garde
      refuse la transition. Le defaut ``"reconstruction"`` laisse
      ``reconstruct-project`` inchangee; la chaine de scan passe ``"scan"``
      (EPIC5-ARB-7).
    * ``origin`` declare **par quoi** le document a ete reconstruit
      (EPIC5-ARB-9). Defaut ``"payloads"``, la chaine de scan passant
      ``"scan"``. Effet additif assume sur ``reconstruct-project``: son
      manifest gagne ce champ, ce qui est precisement le point -- un manifest
      reconstruit se declare desormais a la lecture au lieu de se deviner a
      l'absence de ``fps_source``.

    ``origines_adoptees`` (`EPIC7-ARB-101`) associe un `lot_id` au projet d'ou
    il vient, tel que :func:`adopter_les_payloads` le rend. Un lot qui y figure
    porte :data:`CHAMP_ORIGINE_ADOPTEE` sur son entree de manifest, et sa
    presence relache les deux seules gardes que l'adoption decide -- identite de
    projet, et rush inconnu du manifest local. Toutes les autres continuent de
    refuser : adopter ne desarme rien, cela donne a la garde une entree deja
    resolue.
    """
    if origin not in RECONSTRUCTION_ORIGINS:
        raise ReconstructionError(
            f"Origine de reconstruction inconnue: {origin!r}. Valeurs "
            f"attendues: {', '.join(RECONSTRUCTION_ORIGINS)}."
        )
    if not page_payloads:
        raise ReconstructionError("Reconstruction impossible: aucun payload de page fourni.")

    for payload in page_payloads:
        _validate_page_payload(payload)

    _check_pile_homogene(page_payloads)
    reference = _check_lot_consistency(page_payloads)
    # L'origine du lot vient du parametre -- premiere adoption, decidee par
    # l'operateur -- OU du manifest, qui l'a deja enregistree. Un seul calcul,
    # parce que deux lectures divergeraient au premier changement de forme.
    origines_adoptees = dict(origines_adoptees or {})
    origine_du_lot = origines_adoptees.get(
        reference["lot_id"],
        origine_adoptee(existing_manifest, reference["lot_id"]))
    _check_manifest_conflicts(
        existing_manifest, reference,
        adoption=origine_du_lot is not None)

    if reference["schema_version"] != SUPPORTED_PAYLOAD_SCHEMA_VERSION:
        raise ReconstructionError(
            "Reconstruction impossible: schema_version de payload "
            f"{reference['schema_version']!r} non supportee (attendu "
            f"{SUPPORTED_PAYLOAD_SCHEMA_VERSION!r}). Cette version est celle du contrat "
            "de payload QR (story 2.3), a ne pas confondre avec la version du schema "
            f"de manifest ({MANIFEST_SCHEMA_VERSION!r})."
        )

    # Dedupe by page_index: identical duplicates are fine (idempotent rescans),
    # conflicting duplicates are an explicit failure.
    pages_by_index: dict[Any, dict[str, Any]] = {}
    for payload in page_payloads:
        page_index = payload["page_index"]
        if page_index in pages_by_index and pages_by_index[page_index] != payload:
            raise ReconstructionError(
                f"Conflit de reconstruction: deux payloads differents declarent le meme "
                f"page_index={page_index!r}."
            )
        pages_by_index[page_index] = payload

    page_count = reference["page_count"]
    # Base zero, per ARCHITECTURE_DETAILED.md section 3.1: valid indexes run
    # from 0 to page_count - 1, exactly the range `io/payload.py` accepts.
    expected_indexes = set(range(page_count))
    provided_indexes = set(pages_by_index.keys())
    unexpected_indexes = sorted(provided_indexes - expected_indexes)
    if unexpected_indexes:
        raise ReconstructionError(
            f"Reconstruction impossible: page_index hors bornes {unexpected_indexes} "
            f"(page_count declare={page_count}, indexes valides 0..{page_count - 1})."
        )
    missing_indexes = sorted(expected_indexes - provided_indexes)
    # Apres le bornage des index, pour que le refus d'un index hors bornes garde la
    # priorite: une page de calibration a l'index 7 d'un lot de 3 est d'abord un index
    # hors bornes, et c'est ce que l'operateur doit lire.
    _check_calibration_page_placement(
        pages_by_index, page_count=page_count, missing_indexes=missing_indexes)

    slots: list[dict[str, Any]] = []
    seen_slot_indexes: set[Any] = set()
    for page_index in sorted(provided_indexes):
        for slot in pages_by_index[page_index]["slots"]:
            slot_index = slot["slot_index"]
            if slot_index in seen_slot_indexes:
                raise ReconstructionError(
                    f"Conflit de reconstruction: slot_index {slot_index!r} declare plusieurs fois."
                )
            seen_slot_indexes.add(slot_index)
            slots.append({"slot_index": slot_index, "frame_timecode": slot["frame_timecode"]})
    slots.sort(key=lambda slot: slot["slot_index"])

    # Story 2.8 (AC 1, EPIC7-ARB-41): cette garde refusait jusqu'ici tout
    # `source_path` absolu -- exactement ce que la story persiste desormais
    # dans le manifest (io/manifest.CHAMPS_EXEMPTES_CHEMIN_ABSOLU). Le chemin
    # d'une autre machine est un chemin mort, donc un rush delinke (AC 3),
    # jamais un motif de refus de lecture: il est preserve verbatim, comme un
    # chemin relatif l'etait deja.
    source_path = _existing_source_path(existing_manifest, reference["rush_id"])

    rush_entry: dict[str, Any] = {"rush_id": reference["rush_id"]}
    if source_path:
        rush_entry["source_path"] = source_path

    is_partial = bool(missing_indexes)
    reconstruction_meta: dict[str, Any] = {
        "template_id": reference["template_id"],
        "patch_preset_id": reference["patch_preset_id"],
        "gamut_map_id": reference["gamut_map_id"],
        # Story 5.7: la section est unique par document et reecrite en entier a
        # chaque appel. Sans dire **quel lot** elle decrit ni **combien de
        # pages** ce lot annonce, son detail par frame n'est rattachable a rien
        # et la regle de cumul d'EPIC5-ARB-32 ne peut pas etablir la nature
        # anterieure d'un fichier ecrase.
        "lot_id": reference["lot_id"],
        "page_count": page_count,
        "origin": origin,
        "status": "partial" if is_partial else "complete",
        "slots": slots,
        # --- Le role de page **persiste** (passe de correction de 5.16) --------------
        #
        # Il etait exige a la relecture et ecrit nulle part: `reconstruction_meta` ne
        # portait que les champs de niveau lot plus `slots`, donc aucun consommateur du
        # document ne pouvait distinguer une page de calibration d'une planche d'images
        # **creuse ou manquante**. C'est la racine commune de trois findings de la revue
        # (couche 1 B1, couche 2 F1 et F2): les deux derivations de cardinal attendu de
        # `scan_output_frames` se trompaient non par erreur de formule mais parce
        # qu'**elles n'avaient pas l'information**.
        #
        # La forme porte l'index **a cote** du role et non son rang dans la liste: c'est
        # la meme regle que `page_calibrations` de `io/scan_manifest`, et pour la meme
        # raison -- un appariement positionnel est ce qui a coute cinq regressions a ce
        # depot (`M25`, `M33`). Trie par index, donc independant de l'ordre d'arrivee des
        # planches, ce que l'AC 3 de la story 2.6 exige du document entier.
        "page_roles": [
            {"page_index": page_index,
             "page_role": _page_role(pages_by_index[page_index])}
            for page_index in sorted(provided_indexes)
        ],
    }
    if is_partial:
        reconstruction_meta["missing_pages"] = missing_indexes

    reconstructed_lot: dict[str, Any] = {
        "lot_id": reference["lot_id"],
        "rush_id": reference["rush_id"],
        # Etat **resolu** par la garde de transition, jamais affecte en dur
        # (AC 3): un lot deja passe en `reconstruction` ou en `encode` conserve
        # son etat au lieu de redescendre.
        "state": _resolve_lot_state(existing_manifest, reference["lot_id"], lot_state),
        # v2.1: la cadence cible appartient au lot. Un projet peut porter
        # plusieurs lots du meme rush a des cadences differentes, et un
        # manifest reconstruit ne doit pas reintroduire la cadence unique par
        # projet de la v2.0.
        "fps_target": reference["fps_target"],
        # Story 2.7 (payload 2.1, EPIC7-ARB-56): la cadence SOURCE du rush,
        # ecrite sur le lot exactement comme le fait deja l'extraction
        # (`io/extraction_manifest.py`) -- c'est ce qui permet a `encode
        # resolve_source_rate` de la lire sans `--cadence-source` sur un lot
        # ne du scan seul, FR17 de l'Epic 7.
        "timecode_base_fps": reference["timecode_base_fps"],
    }
    # **L'origine est gardee sur le lot** (`EPIC7-ARB-101`), et le motif est
    # fonctionnel avant d'etre moral : le papier continue de dire son projet
    # d'origine et le dira toujours. Sans cette trace, chaque nouvelle feuille
    # du meme lot rescannee plus tard repartirait « hors perimetre ».
    #
    # Champ **additif**, pose seulement quand il y a quelque chose a dire : un
    # lot ne dans ce projet ne le porte pas, et un manifest d'avant cet
    # arbitrage se relit inchange.
    if origine_du_lot is not None:
        reconstructed_lot[CHAMP_ORIGINE_ADOPTEE] = origine_du_lot

    # **L'identite du projet est celle d'ACCUEIL des qu'un lot est adopte**
    # (`EPIC7-ARB-101`). La reference vient des payloads, donc du papier, donc du
    # projet d'origine : la recopier ici renommerait le projet d'accueil a la
    # premiere planche etrangere adoptee -- exactement l'inverse de l'adoption.
    identite_du_projet = reference["project_id"]
    if origine_du_lot is not None and existing_manifest:
        identite_du_projet = existing_manifest.get(
            "project_id") or identite_du_projet

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_id": identite_du_projet,
        "rushes": _merge_entries(existing_manifest, "rushes", "rush_id", rush_entry),
        "lots": _merge_entries(existing_manifest, "lots", "lot_id", reconstructed_lot),
        "artifacts": {},
        # `target_colorspace` is the one colorimetric field a third party can
        # recover without the source machine, so it travels in the QR payload
        # and must reach the manifest. The rest of `color` (and the rush's
        # resolution_source / fps_source, and video's codec_target) cannot be
        # recovered from a scan: their absence is an expected property of a
        # reconstructed manifest, not a defect.
        "color": {"target_colorspace": reference["target_colorspace"]},
        "video": {},
        "reconstruction": reconstruction_meta,
    }

    _validate_against_schema(manifest)
    return manifest
