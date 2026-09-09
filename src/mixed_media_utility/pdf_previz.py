"""Contrat de donnees de previz PDF (story 4.9).

Jumelle de ``extraction_previz`` (story 3.5), qui l'annonce en toutes
lettres: l'enveloppe ``previz-1`` est reprise **telle quelle**
(``previz_schema_version``, ``kind``, ``state``, ``generated_at_utc``,
``subject``, ``warnings``, ``fingerprints``) avec ``kind = "makepdf"``.
Le livrable est le **contrat de donnees**, pas une interface, pas un rendu:
une GUI (Epic 7) ou les previz jumelles 5.8 / 6.4 consomment ce document pour
montrer "voici les planches que makepdf produira" sans rendre un seul PDF.

Purete
------
Meme standard que ``extraction_previz`` (verrouille par le meme motif de test
AST dans ``tests/unit/test_pdf_previz.py``): aucun ``subprocess``, ``cv2``,
``PIL``, ``numpy``, **reportlab**, aucune ecriture, aucun ``open`` /
``print`` / ``input`` / ``exec`` / ``eval``, aucune dependance nouvelle,
aucun import d'une bibliotheque d'interface. Consequence structurante: ce
module n'importe **pas** ``pdf_composition`` (qui tire cv2 via ``layout``);
le plan de page y entre en typage structurel (:class:`LotCompositionLike`),
exactement comme 3.5 consomme ``FrameSelection`` par protocole.

Reprise de 3.5: reprendre, ne pas copier
----------------------------------------
Les helpers de canonicalisation sont **importes**, jamais recopies: deux
recettes qui divergent sont exactement le defaut que 3.5 a corrige en revue.

**Depuis la story 5.8**, ils viennent de ``previz_common`` et non plus de
``extraction_previz``, et la validation d'horodatage aussi. La version
precedente de ce module la redeclarait inline, faute de pouvoir elargir la
liste blanche AST des tests de 3.5 (l'AC 7 de 4.9 interdisait de toucher a un
test existant); la dette avait ete consignee au ``deferred-work.md`` avec un
mandat nomme: extraire helpers, horodatage et socle d'enveloppe « quand une
troisieme previz jumelle (5.8 ou 6.4) arrive ». C'est fait, et la troisieme
copie de la regle d'horodatage n'a pas eu lieu.

L'enveloppe reste redeclaree localement, parce que les dataclasses de 3.5 sont
specifiques au kind ``extraction`` (familles selection / confirmation, rapport
source); seuls les champs de tete passent par ``previz_common.envelope_head``.

Projection, jamais calcul
-------------------------
``build_pdf_previz`` **projette** le plan de page de 4.1
(``pdf_composition.LotComposition``): chaque valeur -- zones, QR (taille et
classement ``check_print_geometry`` transportes verbatim), marqueurs, patchs,
blocs de texte, parametres -- provient litteralement du plan. Aucune
arithmetique de mise en page, aucun budget QR, aucune regle de capacite:
des sentinelles incoherentes ressortent incoherentes et verbatim (teste).
Seule exception, heritee de 3.5 post-ARB-13: ``LOT_INCOMPLETE`` est deduit
ici de la confrontation des compteurs attendu / present, et un compte
present superieur a l'attendu est refuse a la construction.

Etats
-----
``planned`` (plan calcule, PDF non rendu, ``output_pdf_path_relative`` a
``None``) / ``rendered`` (PDF rendu: chemin relatif et compteur present
**fournis par l'appelant**, jamais mesures ici). ``planned`` est la valeur de
l'enveloppe 3.5; ``extracted`` y etait deja specifique au kind extraction,
donc ``rendered`` est le pendant makepdf sans jonction a ouvrir.

Empreintes
----------
* ``fingerprints.composition`` -- les **entrees de decision de la
  composition** (:data:`COMPOSITION_FINGERPRINT_FIELDS`): parametres +
  identite du lot. Changer un parametre change l'empreinte; regenerer a
  l'identique ne la change pas; ajouter un avertissement ne la change pas.
* ``fingerprints.selection`` -- **transportee verbatim** depuis l'appelant, a
  la recette de 3.5 uniquement (forme complete exigee: prefixe
  ``sha256-v1:`` suivi de 64 hexadecimaux). Le ``frame_timecodes_digest`` de
  3.4 est une recette distincte, non comparable: ne jamais les melanger.

Contrat de lecture des empreintes (revue 4.9): la peremption d'une previz se
teste en comparant **les deux** champs. ``fingerprints.composition`` ne couvre
pas la selection (une re-selection a parametres identiques la laisse
inchangee): la selection perimee se detecte sur ``fingerprints.selection``,
transportee en champ frere precisement pour cela.

Une previz n'autorise rien (regle 3.5 / 3.6): aucun consentement, aucun
declencheur de rendu, aucune fonction qui lance ``makepdf``.

Convention d'ecriture: messages en francais **sans accents**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .previz_common import (
    FINGERPRINT_PREFIX,
    PREVIZ_SCHEMA_VERSION,
    PREVIZ_STATE_PLANNED,
    envelope_head,
    exact_rate as _common_exact_rate,
    fingerprint_of,
    is_complete_fingerprint,
    normalize_generated_at_utc,
    require_int as _common_require_int,
    require_known_codes,
    require_number as _common_require_number,
    require_relative_path as _common_relative_path,
    require_text as _common_require_text,
)

__all__ = [
    "PDF_PREVIZ_KIND",
    "PDF_PREVIZ_STATE_PLANNED",
    "PDF_PREVIZ_STATE_RENDERED",
    "PDF_PREVIZ_STATES",
    "GEOMETRY_DEGRADED",
    "LOT_INCOMPLETE",
    "OVER_NOMINAL_BUDGET",
    "PDF_PREVIZ_WARNING_CODES",
    "COMPOSITION_FINGERPRINT_FIELDS",
    "PdfPrevizError",
    "PdfPrevizSubject",
    "PdfPrevizParameters",
    "PrevizFrameZone",
    "PrevizQr",
    "PrevizMarker",
    "PrevizPatch",
    "PrevizSlotLabel",
    "PrevizTextBlock",
    "PdfPrevizPage",
    "PdfPrevizWarnings",
    "PdfPrevizFingerprints",
    "PdfPreviz",
    "build_pdf_previz",
    "pdf_previz_to_json_dict",
]


# --------------------------------------------------------------------------
# Vocabulaire fige
# --------------------------------------------------------------------------

#: ``kind`` de la charge specifique de ce module (enveloppe 3.5).
PDF_PREVIZ_KIND = "makepdf"

#: ``planned`` est la valeur generique de l'enveloppe 3.5; ``rendered`` est
#: le pendant makepdf de son ``extracted`` (etat specifique au kind).
PDF_PREVIZ_STATE_PLANNED = PREVIZ_STATE_PLANNED
PDF_PREVIZ_STATE_RENDERED = "rendered"
PDF_PREVIZ_STATES: tuple[str, ...] = (PDF_PREVIZ_STATE_PLANNED, PDF_PREVIZ_STATE_RENDERED)

# Vocabulaire FERME des avertissements de previz PDF. Nom de constante
# volontairement distinct de PREVIZ_WARNING_CODES (3.5): reproduire
# l'homonymie recreerait la divergence qu'ARB-14 a du resorber. Les codes
# sont transportes depuis l'appelant (qui les derive du plan reel: pages hors
# budget nominal, geometrie QR degradee), valides a la construction -- sauf
# LOT_INCOMPLETE, deduit ici de la confrontation des compteurs (ARB-13).
GEOMETRY_DEGRADED = "GEOMETRY_DEGRADED"
LOT_INCOMPLETE = "LOT_INCOMPLETE"
OVER_NOMINAL_BUDGET = "OVER_NOMINAL_BUDGET"

PDF_PREVIZ_WARNING_CODES: tuple[str, ...] = (
    GEOMETRY_DEGRADED,
    LOT_INCOMPLETE,
    OVER_NOMINAL_BUDGET,
)

#: Les **seules** entrees de decision de la composition qui entrent dans
#: ``fingerprints.composition`` (motif SELECTION_FINGERPRINT_FIELDS de 3.5).
#: Y ajouter un champ d'affichage rendrait l'empreinte sensible a ce qui ne
#: decide rien.
COMPOSITION_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "dpi",
    "format",
    "fps_target_exact",
    "frames_par_page",
    # `gamut_map_id` est une **entree de decision** de la composition: deux
    # plans identiques sauf `G` produisent des planches differentes. Sans lui
    # ici, changer `--gamut-map` laisserait l'empreinte inchangee et une
    # previz perimee deviendrait indetectable.
    "gamut_map_id",
    "lot_id",
    "marge",
    "orientation",
    "patch_preset_id",
    "project_id",
    "rush_id",
    "template_id",
)

# La regle d'horodatage et la forme complete d'empreinte vivent desormais dans
# `previz_common` (story 5.8): elles etaient ici la **seconde** copie, et la
# jonction consignee au backlog le 2026-08-06 existait pour empecher qu'une
# troisieme naisse cote scan.

#: Date d'exemple citee dans le refus d'horodatage de ce module. Elle n'a
#: d'effet que sur le texte du message: la conserver garde le refus
#: rigoureusement inchange apres l'extraction de la regle.
_GENERATED_AT_EXAMPLE = "2026-08-06T12:00:00Z"


class PdfPrevizError(ValueError):
    """Entree refusee a la construction du document (jamais un cas degrade:
    ceux-la produisent un document valide porte par ``warnings.previz``)."""


# --------------------------------------------------------------------------
# Contrat consomme du plan de 4.1, sans dependance de module (purete)
# --------------------------------------------------------------------------


class _FrameSlotLike(Protocol):
    # `zone_name` du plan n'est volontairement pas declare: ce module lit les
    # champs listes ici et aucun autre (revue 4.9: un champ declare mais
    # jamais lu trompe le fournisseur alternatif du protocole).
    slot_index: int
    frame_timecode: str
    frame_filename: str
    zone_rect_mm: tuple[float, float, float, float]
    image_rect_mm: tuple[float, float, float, float]
    letterbox_policy: str


class _QRLike(Protocol):
    budget: Any
    print_size_mm: float
    geometry_status: str
    footprint_rect_mm: tuple[float, float, float, float]


class _PageLike(Protocol):
    page_index: int
    frames: Sequence[_FrameSlotLike]
    qr: _QRLike
    markers: Sequence[Any]
    patches: Sequence[Any]
    text: Any


class LotCompositionLike(Protocol):
    """Sous-ensemble de ``pdf_composition.LotComposition`` reellement lu.

    Ce module lit ces champs et **aucun autre**; il ne recalcule rien.
    """

    project_id: str
    rush_id: str
    lot_id: str
    fps_target: Any
    page_format: str
    orientation: str
    frames_per_page: int
    margin_preset: str
    template_id: str
    patch_preset_id: str
    gamut_map_id: str
    render_dpi: int
    frames_dir: str
    pdf_filename: str
    page_count: int
    pages: Sequence[_PageLike]


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PdfPrevizSubject:
    """Ce sur quoi porte la previz. Toutes les valeurs sont transportees."""

    project_id: str
    rush_id: str
    lot_id: str
    fps_target_exact: str
    expected_frame_count: int
    frames_present_count: int | None


@dataclass(frozen=True)
class PdfPrevizParameters:
    """Parametres de composition, transportes verbatim du plan de 4.1."""

    template_id: str
    patch_preset_id: str
    gamut_map_id: str
    frames_par_page: int
    format: str
    orientation: str
    dpi: int
    marge: str


@dataclass(frozen=True)
class PrevizFrameZone:
    """Une zone de frame posee sur une page (positions en mm, plan de 4.1).

    ``x/y/w/h_mm`` est l'emprise imprimee de la zone (16:9 du template);
    ``image_x/y/w/h_mm`` le rectangle utile ou l'image est reellement posee
    selon ``letterbox_policy`` (revue 4.9: sans ces champs, une GUI dessinait
    la frame plein cadre la ou makepdf la letterbox -- l'apercu mentait).
    """

    slot_index: int
    frame_timecode: str
    frame_path_relative: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    image_x_mm: float
    image_y_mm: float
    image_w_mm: float
    image_h_mm: float
    letterbox_policy: str


@dataclass(frozen=True)
class PrevizQr:
    """Le QR de la page: emprise physique (silence compris), taille du
    symbole, classement ``check_print_geometry`` transporte verbatim."""

    x_mm: float
    y_mm: float
    size_mm: float
    symbol_size_mm: float
    geometry: str
    payload_bytes: int


@dataclass(frozen=True)
class PrevizMarker:
    """Un marqueur ArUco. ``center_x/y_mm`` sont des **centres** (le plan de
    4.1 pose les marqueurs par centre, le rendu convertit): les nommer
    ``x_mm``/``y_mm`` comme les coins haut-gauche du reste du document
    decalait chaque marqueur d'une demi-taille chez tout consommateur uniforme
    (revue 4.9)."""

    marker_id: int
    center_x_mm: float
    center_y_mm: float
    size_mm: float


@dataclass(frozen=True)
class PrevizPatch:
    """Un patch de calibration: valeur, couleur RVB resolue (table 4.8,
    transportee pour que la GUI n'ait pas a redupliquer la resolution
    ``value_id -> RGB`` -- motif ARB-14), position et taille."""

    value_id: str
    rgb: tuple[int, int, int]
    x_mm: float
    y_mm: float
    size_mm: float


@dataclass(frozen=True)
class PrevizSlotLabel:
    """Etiquette imprimee sous une zone de frame (rush + slot + timecode):
    la redondance de secours du mapping slot -> timecode selon 4.2, partie
    integrante de la planche que makepdf produira (revue 4.9)."""

    text: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float


@dataclass(frozen=True)
class PrevizTextBlock:
    """Un bloc de texte du plan: role (nom de zone 4.2), contenu exact."""

    role: str
    content: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    font_pt: float


@dataclass(frozen=True)
class PdfPrevizPage:
    page_index: int
    page_count: int
    frame_zones: tuple[PrevizFrameZone, ...]
    qr: PrevizQr
    aruco_markers: tuple[PrevizMarker, ...]
    patches: tuple[PrevizPatch, ...]
    text_blocks: tuple[PrevizTextBlock, ...]
    slot_labels: tuple[PrevizSlotLabel, ...]


@dataclass(frozen=True)
class PdfPrevizWarnings:
    """Une seule famille ici (``previz``): le plan de 4.1 n'expose pas de
    familles distinctes -- ses avertissements structurels sont derives en
    codes par l'appelant."""

    previz: tuple[str, ...] = ()


@dataclass(frozen=True)
class PdfPrevizFingerprints:
    composition: str
    selection: str


@dataclass(frozen=True)
class PdfPreviz:
    """Document de previz PDF, fige et comparable. La forme **normative** est
    le JSON rendu par ``pdf_previz_to_json_dict``."""

    previz_schema_version: str
    kind: str
    state: str
    generated_at_utc: str
    subject: PdfPrevizSubject
    parameters: PdfPrevizParameters
    pages: tuple[PdfPrevizPage, ...]
    #: Nom de fichier PDF **prevu** par le plan (convention EPIC4-ARB-3),
    #: transporte verbatim dans les deux regimes: c'est lui qui porte le
    #: "sera ecrit sous ..." d'un document ``planned`` (revue 4.9).
    pdf_filename: str
    output_pdf_path_relative: str | None
    warnings: PdfPrevizWarnings
    fingerprints: PdfPrevizFingerprints


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


# Les trois gardes de type et la garde de chemin relatif sont celles de
# `previz_common` depuis la story 5.8: elles etaient identiques mot pour mot
# chez 3.5. Ces enveloppes locales n'ajoutent que la hierarchie d'erreur de ce
# module, si bien que le texte des refus est inchange.


def _require_text(value: Any, label: str) -> str:
    return _common_require_text(value, label, error_type=PdfPrevizError)


def _require_int(value: Any, label: str) -> int:
    return _common_require_int(value, label, error_type=PdfPrevizError)


def _require_number(value: Any, label: str):
    """Nombre transporte verbatim (jamais converti), type controle."""
    return _common_require_number(value, label, error_type=PdfPrevizError)


def _require_rect(value: Any, label: str) -> tuple:
    """Rectangle (x, y, w, h) en mm: 4 nombres, transportes verbatim."""
    try:
        items = tuple(value)
    except TypeError as exc:
        raise PdfPrevizError(
            f"{label} doit etre un rectangle (x, y, w, h), recu {value!r}"
        ) from exc
    if len(items) != 4:
        raise PdfPrevizError(
            f"{label} doit porter exactement 4 composantes (x, y, w, h), "
            f"recu {value!r}"
        )
    return tuple(_require_number(item, f"{label}[{i}]") for i, item in enumerate(items))


def _relative_path(value: Any, label: str) -> str:
    """Chemin relatif au dossier projet, ou refus. Delegue au point unique de
    cette regle (``source_confirmation.normalize_relative_project_path``)."""
    return _common_relative_path(value, label, error_type=PdfPrevizError)


def _validate_generated_at(value: Any) -> str:
    return normalize_generated_at_utc(
        value, error_type=PdfPrevizError, example=_GENERATED_AT_EXAMPLE
    )


def _validate_codes(codes: Any) -> tuple[str, ...]:
    if codes is None:
        return ()
    if isinstance(codes, str):
        raise PdfPrevizError(
            f"previz_warnings doit etre une sequence de codes, pas une chaine: {codes!r}"
        )
    try:
        received = tuple(codes)
    except TypeError as exc:
        raise PdfPrevizError(
            f"previz_warnings doit etre une sequence de codes, recu {codes!r}"
        ) from exc
    validated = tuple(_require_text(code, "code d'avertissement") for code in received)
    require_known_codes(
        validated,
        PDF_PREVIZ_WARNING_CODES,
        label="Code d'avertissement de previz PDF inconnu",
        error_type=PdfPrevizError,
    )
    if len(set(validated)) != len(validated):
        raise PdfPrevizError(
            f"previz_warnings porte un code duplique: {validated!r}. Le "
            "vocabulaire est ferme et chaque code se declare au plus une fois "
            "(deux documents semantiquement identiques doivent produire le "
            "meme JSON canonique)"
        )
    if LOT_INCOMPLETE in validated:
        raise PdfPrevizError(
            f"{LOT_INCOMPLETE} ne se fournit jamais: il est deduit ici de la "
            "confrontation des compteurs attendu / present (ARB-13). Un code "
            "fourni pourrait contredire les compteurs du document"
        )
    return validated


def _exact_rate(fps: Any) -> str:
    return _common_exact_rate(fps, error_type=PdfPrevizError)


def build_pdf_previz(
    *,
    plan: LotCompositionLike,
    generated_at_utc: str,
    expected_frame_count: int,
    selection_fingerprint: str,
    state: str = PDF_PREVIZ_STATE_PLANNED,
    frames_present_count: int | None = None,
    output_pdf_path_relative: str | None = None,
    previz_warnings: Sequence[str] = (),
) -> PdfPreviz:
    """Projeter le plan de page de 4.1 en document de previz.

    **Projection stricte**: rien n'est recalcule, rien n'est recompte, rien
    n'est reconcilie -- des sentinelles incoherentes ressortent verbatim.

    Parameters
    ----------
    plan:
        ``pdf_composition.LotComposition`` (ou tout objet structurellement
        identique). Source unique de toutes les geometries et parametres.
    generated_at_utc:
        Horodatage UTC ISO 8601 suffixe ``Z``, **fourni par l'appelant**
        (l'horloge n'entre pas dans un module deterministe).
    expected_frame_count:
        Cardinal attendu du lot (selection 3.2 / manifest), transporte.
    selection_fingerprint:
        Empreinte de selection **a la recette de 3.5** (forme complete
        exigee: prefixe ``sha256-v1:`` suivi de 64 hexadecimaux),
        transportee verbatim. Jamais le ``frame_timecodes_digest`` de 3.4
        (recette non comparable).
    state:
        ``planned`` ou ``rendered``.
    frames_present_count:
        **Fourni par l'appelant** en regime ``rendered``, jamais compte ici.
        Interdit en ``planned``. Un compte superieur a l'attendu est refuse
        (ARB-13); un compte inferieur emet ``LOT_INCOMPLETE``.
    output_pdf_path_relative:
        Chemin relatif du PDF **rendu** (``rendered``); interdit en
        ``planned``. Le nom de fichier *prevu* est transporte dans les deux
        regimes via le champ ``pdf_filename`` du document, projete depuis
        ``plan.pdf_filename`` (revue 4.9: la premiere version renvoyait a un
        champ jamais transporte).
    previz_warnings:
        Codes **recus** de l'appelant, valides contre
        ``PDF_PREVIZ_WARNING_CODES``. ``LOT_INCOMPLETE`` est refuse ici: il
        est toujours deduit des compteurs (ARB-13). Doublons refuses; la
        famille ``warnings.previz`` du document est triee pour que deux
        documents semantiquement identiques aient le meme JSON canonique.
    """
    if state not in PDF_PREVIZ_STATES:
        raise PdfPrevizError(
            f"Etat de previz inconnu: {state!r}. Vocabulaire ferme: "
            f"{', '.join(PDF_PREVIZ_STATES)}"
        )
    generated = _validate_generated_at(generated_at_utc)
    expected = _require_int(expected_frame_count, "expected_frame_count")
    if expected < 0:
        raise PdfPrevizError(
            f"expected_frame_count doit etre positif ou nul, recu {expected!r}"
        )

    fingerprint = _require_text(selection_fingerprint, "selection_fingerprint")
    if not is_complete_fingerprint(fingerprint):
        raise PdfPrevizError(
            f"selection_fingerprint doit porter la recette de 3.5 sous forme "
            f"complete (prefixe '{FINGERPRINT_PREFIX}' suivi de 64 "
            f"hexadecimaux), recu {selection_fingerprint!r}. Le "
            "frame_timecodes_digest de 3.4 est une recette distincte, non "
            "comparable: ne pas le transporter ici."
        )

    if state == PDF_PREVIZ_STATE_RENDERED:
        if frames_present_count is None:
            raise PdfPrevizError(
                "frames_present_count est obligatoire en regime 'rendered' et "
                "doit etre fourni par l'appelant: ce module ne compte jamais "
                "les fichiers presents sur disque"
            )
        present: int | None = _require_int(frames_present_count, "frames_present_count")
        if present < 0:
            raise PdfPrevizError(
                f"frames_present_count doit etre positif ou nul, recu {present!r}"
            )
        if present > expected:
            raise PdfPrevizError(
                f"frames_present_count ({present}) depasse le cardinal attendu "
                f"({expected}): un lot ne peut pas porter plus d'images que la "
                "selection n'en retient. Ce document se contredirait lui-meme "
                "(ARB-13)"
            )
        if output_pdf_path_relative is None:
            raise PdfPrevizError(
                "output_pdf_path_relative est obligatoire en regime 'rendered': "
                "un PDF rendu se localise"
            )
        output_path: str | None = _relative_path(
            output_pdf_path_relative, "output_pdf_path_relative"
        )
    else:
        if frames_present_count is not None:
            raise PdfPrevizError(
                "frames_present_count n'a pas de sens en regime 'planned': "
                f"aucun PDF n'est encore rendu, recu {frames_present_count!r}"
            )
        if output_pdf_path_relative is not None:
            raise PdfPrevizError(
                "output_pdf_path_relative n'a pas de sens en regime 'planned': "
                f"le PDF n'existe pas encore, recu {output_pdf_path_relative!r}"
            )
        present = None
        output_path = None

    # Enveloppe structurelle (revue 4.9): un plan auquel il manque un attribut
    # ou une composante de rectangle levait AttributeError/IndexError/TypeError
    # brutes, hors de la hierarchie promise ("entree refusee a la
    # construction" = PdfPrevizError).
    caller_codes = _validate_codes(previz_warnings)

    try:
        frames_dir = _relative_path(plan.frames_dir, "plan.frames_dir")
        pages = _project_pages(plan, frames_dir)
        pdf_filename = _require_text(plan.pdf_filename, "plan.pdf_filename")
        fps_target_exact = _exact_rate(plan.fps_target)
        parameters = PdfPrevizParameters(
            template_id=_require_text(plan.template_id, "plan.template_id"),
            patch_preset_id=_require_text(plan.patch_preset_id, "plan.patch_preset_id"),
            gamut_map_id=_require_text(plan.gamut_map_id, "plan.gamut_map_id"),
            frames_par_page=_require_int(plan.frames_per_page, "plan.frames_per_page"),
            format=_require_text(plan.page_format, "plan.page_format"),
            orientation=_require_text(plan.orientation, "plan.orientation"),
            dpi=_require_int(plan.render_dpi, "plan.render_dpi"),
            marge=_require_text(plan.margin_preset, "plan.margin_preset"),
        )
        subject = PdfPrevizSubject(
            project_id=_require_text(plan.project_id, "plan.project_id"),
            rush_id=_require_text(plan.rush_id, "plan.rush_id"),
            lot_id=_require_text(plan.lot_id, "plan.lot_id"),
            fps_target_exact=fps_target_exact,
            expected_frame_count=expected,
            frames_present_count=present,
        )
    except PdfPrevizError:
        raise
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise PdfPrevizError(
            f"Plan structurellement incomplet ou malforme: {exc}"
        ) from exc

    # ARB-13: les compteurs sont confrontes, un lot tronque est declare.
    completude: tuple[str, ...] = ()
    if present is not None and present < expected:
        completude = (LOT_INCOMPLETE,)

    return PdfPreviz(
        previz_schema_version=PREVIZ_SCHEMA_VERSION,
        kind=PDF_PREVIZ_KIND,
        state=state,
        generated_at_utc=generated,
        subject=subject,
        parameters=parameters,
        pages=tuple(pages),
        pdf_filename=pdf_filename,
        output_pdf_path_relative=output_path,
        # Tri: forme canonique stable quel que soit l'ordre cote appelant
        # (revue 4.9). Aucun doublon possible: caller_codes est deduplique et
        # ne peut pas porter LOT_INCOMPLETE.
        warnings=PdfPrevizWarnings(previz=tuple(sorted(caller_codes + completude))),
        fingerprints=PdfPrevizFingerprints(
            composition=fingerprint_of(
                _composition_fingerprint_payload(subject, parameters)
            ),
            selection=fingerprint,
        ),
    )


def _project_pages(plan: LotCompositionLike, frames_dir: str) -> list[PdfPrevizPage]:
    """Projeter chaque page du plan, valeurs verbatim, types controles."""
    pages: list[PdfPrevizPage] = []
    for page in plan.pages:
        page_index = _require_int(page.page_index, "page.page_index")
        zones = []
        for slot in page.frames:
            zone_rect = _require_rect(
                slot.zone_rect_mm, f"pages[{page_index}].zone_rect_mm"
            )
            image_rect = _require_rect(
                slot.image_rect_mm, f"pages[{page_index}].image_rect_mm"
            )
            zones.append(
                PrevizFrameZone(
                    slot_index=_require_int(
                        slot.slot_index, f"pages[{page_index}].slot_index"
                    ),
                    frame_timecode=_require_text(
                        slot.frame_timecode, f"pages[{page_index}].frame_timecode"
                    ),
                    frame_path_relative=_relative_path(
                        f"{frames_dir}/"
                        f"{_require_text(slot.frame_filename, f'pages[{page_index}].frame_filename')}",
                        f"pages[{page_index}].frame_path",
                    ),
                    x_mm=zone_rect[0],
                    y_mm=zone_rect[1],
                    w_mm=zone_rect[2],
                    h_mm=zone_rect[3],
                    image_x_mm=image_rect[0],
                    image_y_mm=image_rect[1],
                    image_w_mm=image_rect[2],
                    image_h_mm=image_rect[3],
                    letterbox_policy=_require_text(
                        slot.letterbox_policy, f"pages[{page_index}].letterbox_policy"
                    ),
                )
            )
        footprint = _require_rect(
            page.qr.footprint_rect_mm, f"pages[{page_index}].qr.footprint_rect_mm"
        )
        if footprint[2] != footprint[3]:
            # Le schema (size_mm unique) ne peut pas representer un rect non
            # carre: le maquiller en carre cacherait un bug amont (revue 4.9,
            # "la hauteur etait silencieusement jetee").
            raise PdfPrevizError(
                f"pages[{page_index}].qr.footprint_rect_mm n'est pas carre "
                f"({footprint[2]} x {footprint[3]}): l'emprise QR (symbole + "
                "silence ISO) est un carre par construction, un rect non carre "
                "signale un plan corrompu"
            )
        qr = PrevizQr(
            x_mm=footprint[0],
            y_mm=footprint[1],
            size_mm=footprint[2],
            symbol_size_mm=_require_number(
                page.qr.print_size_mm, f"pages[{page_index}].qr.print_size_mm"
            ),
            geometry=_require_text(
                page.qr.geometry_status, f"pages[{page_index}].qr.geometry_status"
            ),
            payload_bytes=_require_int(
                page.qr.budget.size_bytes, f"pages[{page_index}].qr.budget.size_bytes"
            ),
        )
        markers = tuple(
            PrevizMarker(
                marker_id=_require_int(
                    marker.marker_id, f"pages[{page_index}].marker_id"
                ),
                center_x_mm=_require_number(
                    marker.center_x_mm, f"pages[{page_index}].center_x_mm"
                ),
                center_y_mm=_require_number(
                    marker.center_y_mm, f"pages[{page_index}].center_y_mm"
                ),
                size_mm=_require_number(
                    marker.size_mm, f"pages[{page_index}].marker.size_mm"
                ),
            )
            for marker in page.markers
        )
        patches = tuple(
            PrevizPatch(
                value_id=_require_text(
                    patch.value_id, f"pages[{page_index}].patch.value_id"
                ),
                rgb=_require_rgb(patch.rgb, f"pages[{page_index}].patch.rgb"),
                x_mm=_require_number(patch.x_mm, f"pages[{page_index}].patch.x_mm"),
                y_mm=_require_number(patch.y_mm, f"pages[{page_index}].patch.y_mm"),
                size_mm=_require_number(
                    patch.size_mm, f"pages[{page_index}].patch.size_mm"
                ),
            )
            for patch in page.patches
        )
        text_blocks = []
        for block in page.text.blocks:
            if isinstance(block.lines, str):
                # "abc" se decouperait caractere par caractere au join --
                # contenu mutile en silence (revue 4.9), meme motif de refus
                # que previz_warnings.
                raise PdfPrevizError(
                    f"pages[{page_index}]: block.lines doit etre une sequence "
                    f"de lignes, pas une chaine: {block.lines!r}"
                )
            block_rect = _require_rect(
                block.rect_mm, f"pages[{page_index}].block.rect_mm"
            )
            text_blocks.append(
                PrevizTextBlock(
                    role=_require_text(block.name, f"pages[{page_index}].block.name"),
                    content="\n".join(block.lines),
                    x_mm=block_rect[0],
                    y_mm=block_rect[1],
                    w_mm=block_rect[2],
                    h_mm=block_rect[3],
                    font_pt=_require_number(
                        block.font_pt, f"pages[{page_index}].block.font_pt"
                    ),
                )
            )
        slot_labels = []
        for label in page.text.slot_labels:
            label_rect = _require_rect(
                label.rect_mm, f"pages[{page_index}].slot_label.rect_mm"
            )
            slot_labels.append(
                PrevizSlotLabel(
                    text=_require_text(
                        label.text, f"pages[{page_index}].slot_label.text"
                    ),
                    x_mm=label_rect[0],
                    y_mm=label_rect[1],
                    w_mm=label_rect[2],
                    h_mm=label_rect[3],
                )
            )
        pages.append(
            PdfPrevizPage(
                page_index=page_index,
                page_count=_require_int(plan.page_count, "plan.page_count"),
                frame_zones=tuple(zones),
                qr=qr,
                aruco_markers=markers,
                patches=patches,
                text_blocks=tuple(text_blocks),
                slot_labels=tuple(slot_labels),
            )
        )
    return pages


def _require_rgb(value: Any, label: str) -> tuple[int, int, int]:
    """Triplet RVB 8 bits transporte verbatim (resolution de la table 4.8)."""
    try:
        items = tuple(value)
    except TypeError as exc:
        raise PdfPrevizError(
            f"{label} doit etre un triplet RVB, recu {value!r}"
        ) from exc
    if len(items) != 3:
        raise PdfPrevizError(f"{label} doit porter 3 canaux, recu {value!r}")
    return tuple(_require_int(item, f"{label}[{i}]") for i, item in enumerate(items))


def _composition_fingerprint_payload(
    subject: PdfPrevizSubject, parameters: PdfPrevizParameters
) -> dict[str, Any]:
    """Les entrees de decision de la composition, et rien d'autre (piege 4)."""
    payload = {
        "dpi": parameters.dpi,
        "format": parameters.format,
        "fps_target_exact": subject.fps_target_exact,
        "frames_par_page": parameters.frames_par_page,
        "lot_id": subject.lot_id,
        "marge": parameters.marge,
        "orientation": parameters.orientation,
        "patch_preset_id": parameters.patch_preset_id,
        "gamut_map_id": parameters.gamut_map_id,
        "project_id": subject.project_id,
        "rush_id": subject.rush_id,
        "template_id": parameters.template_id,
    }
    if tuple(sorted(payload)) != COMPOSITION_FINGERPRINT_FIELDS:
        raise PdfPrevizError(
            "Le payload d'empreinte de composition diverge de "
            "COMPOSITION_FINGERPRINT_FIELDS"
        )
    return payload


# --------------------------------------------------------------------------
# Serialisation
# --------------------------------------------------------------------------


def pdf_previz_to_json_dict(previz: PdfPreviz) -> dict[str, Any]:
    """Forme JSON **normative** du document, deterministe et serialisable.

    Aucun objet Python non JSON, aucun octet d'image, aucun base64. Passer le
    resultat a ``previz_common.canonical_json`` produit la meme chaine octet
    pour octet d'un processus a l'autre.

    Cette phrase disait « ``canonical_json`` (importe de 3.5) » jusqu'a la
    revue de 5.8 (couche 1 F6, couche 2 finding 12), et elle etait fausse sur
    ses deux points depuis la jonction: la fonction ne vient plus de 3.5 mais
    du socle commun, et ce module ne l'importe plus du tout -- il n'importe que
    ce qu'il utilise. Le re-export n'est pas retabli: `canonical_json` n'a
    jamais figure dans ``pdf_previz.__all__`` et aucun consommateur du depot ne
    l'atteint par ce module. C'est la docstring qui avait tort.
    """
    return {
        # Socle d'enveloppe partage (story 5.8): les quatre champs de tete sont
        # rendus par `previz_common.envelope_head`, une fois pour les trois
        # jumelles, et depuis les valeurs **du document** -- jamais depuis les
        # constantes relues.
        **envelope_head(
            schema_version=previz.previz_schema_version,
            kind=previz.kind,
            state=previz.state,
            generated_at_utc=previz.generated_at_utc,
        ),
        "subject": {
            "project_id": previz.subject.project_id,
            "rush_id": previz.subject.rush_id,
            "lot_id": previz.subject.lot_id,
            "fps_target_exact": previz.subject.fps_target_exact,
            "expected_frame_count": previz.subject.expected_frame_count,
            "frames_present_count": previz.subject.frames_present_count,
        },
        "parameters": {
            "template_id": previz.parameters.template_id,
            "patch_preset_id": previz.parameters.patch_preset_id,
            "gamut_map_id": previz.parameters.gamut_map_id,
            "frames_par_page": previz.parameters.frames_par_page,
            "format": previz.parameters.format,
            "orientation": previz.parameters.orientation,
            "dpi": previz.parameters.dpi,
            "marge": previz.parameters.marge,
        },
        "pages": [
            {
                "page_index": page.page_index,
                "page_count": page.page_count,
                "frame_zones": [
                    {
                        "slot_index": zone.slot_index,
                        "frame_timecode": zone.frame_timecode,
                        "frame_path_relative": zone.frame_path_relative,
                        "x_mm": zone.x_mm,
                        "y_mm": zone.y_mm,
                        "w_mm": zone.w_mm,
                        "h_mm": zone.h_mm,
                        "image_x_mm": zone.image_x_mm,
                        "image_y_mm": zone.image_y_mm,
                        "image_w_mm": zone.image_w_mm,
                        "image_h_mm": zone.image_h_mm,
                        "letterbox_policy": zone.letterbox_policy,
                    }
                    for zone in page.frame_zones
                ],
                "qr": {
                    "x_mm": page.qr.x_mm,
                    "y_mm": page.qr.y_mm,
                    "size_mm": page.qr.size_mm,
                    "symbol_size_mm": page.qr.symbol_size_mm,
                    "geometry": page.qr.geometry,
                    "payload_bytes": page.qr.payload_bytes,
                },
                "aruco_markers": [
                    {
                        "marker_id": marker.marker_id,
                        "center_x_mm": marker.center_x_mm,
                        "center_y_mm": marker.center_y_mm,
                        "size_mm": marker.size_mm,
                    }
                    for marker in page.aruco_markers
                ],
                "patches": [
                    {
                        "value_id": patch.value_id,
                        "rgb": list(patch.rgb),
                        "x_mm": patch.x_mm,
                        "y_mm": patch.y_mm,
                        "size_mm": patch.size_mm,
                    }
                    for patch in page.patches
                ],
                "text_blocks": [
                    {
                        "role": block.role,
                        "content": block.content,
                        "x_mm": block.x_mm,
                        "y_mm": block.y_mm,
                        "w_mm": block.w_mm,
                        "h_mm": block.h_mm,
                        "font_pt": block.font_pt,
                    }
                    for block in page.text_blocks
                ],
                "slot_labels": [
                    {
                        "text": label.text,
                        "x_mm": label.x_mm,
                        "y_mm": label.y_mm,
                        "w_mm": label.w_mm,
                        "h_mm": label.h_mm,
                    }
                    for label in page.slot_labels
                ],
            }
            for page in previz.pages
        ],
        "pdf_filename": previz.pdf_filename,
        "output_pdf_path_relative": previz.output_pdf_path_relative,
        "warnings": {"previz": list(previz.warnings.previz)},
        "fingerprints": {
            "composition": previz.fingerprints.composition,
            "selection": previz.fingerprints.selection,
        },
    }
