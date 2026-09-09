"""Recadrage des frames par la marge encodee (story 5.3).

Cette story est la **symetrie exacte** de la pose d'image de la story 4.1. A
l'impression, `pdf_composition` calcule
`image_rect_mm = page_templates.frame_image_rect_mm(zone, spec.margin_mm)` et
`pdf_render` y dessine l'image. Au scan, ce module decoupe **le meme
rectangle**, resolu par la **meme fonction**, depuis le meme `template_id`.
Toute geometrie recalculee ici plutot que reprise serait une divergence en
puissance.

Pourquoi decouper `image_rect_mm` et non `zone_rect_mm`
--------------------------------------------------------
Deux rectangles distincts coexistent pour chaque zone. `zone_rect_mm` est la
zone du template: c'est ce que `pdf_render` **trace en contour**.
`image_rect_mm` est le rectangle ou l'image est reellement posee: c'est ce que
`pdf_render` **remplit**. Decouper `zone_rect_mm` ferait donc entrer le trait de
contour dans la frame, en plus de la marge.

Le defaut est **invisible au preset de marge `"0"`**: toutes les zones du
registre sont deja 16:9 par construction, donc a marge nulle les deux
rectangles coincident exactement -- verifie sur les 33 gabarits. Il ne se voit
que sur les presets `"2"` et `"5"`.

La marge est encodee, elle ne voyage pas
-----------------------------------------
Le QR ne porte **aucune** valeur de marge: la matrice de responsabilite pose les
parametres de layout comme portes « sous forme d'ID de preset ». La chaine est
donc `template_id` (payload QR) -> `page_templates.get_template` ->
`spec.margin_mm` -> `frame_image_rect_mm`. Ce module ne lit jamais une marge
ailleurs que dans le `TemplateSpec` et n'en accepte aucune en parametre: une
marge passee a l'appel pourrait contredire le template, et la contradiction
serait silencieuse.

Ce que ce module ne fait pas
-----------------------------
Il ne detecte rien (5.2 lui fournit la page redressee et le `template_id`), ne
nomme rien, n'ecrit aucun fichier, ne convertit aucune profondeur de bits, ne
corrige aucune couleur et ne touche pas au manifest. Il ne « nettoie » pas non
plus les bandes de letterbox: elles ont ete posees a l'impression **a
l'interieur** de `image_rect_mm`, elles font partie de l'image, et un rush
2.35:1 doit ressortir 2.35:1 dans une zone 16:9 (EPIC5-ARB-1). Attention au
temoin: `drawImage` n'ecrit aucun fond, donc ces bandes ressortent au **blanc de
la page**, pas en noir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import page_templates, scan_detection, scan_ingest
from .detection import aruco as aruco_detection
from .extraction_previz import FINGERPRINT_PREFIX, canonical_json, fingerprint_of
from .numeric_guards import is_strict_int

#: Debordement hors page tolere, en pixels, **pose a zero et documente comme
#: tel** (question ouverte 2 de la story, option « a »).
#:
#: Une homographie parfaite n'existe pas sur un scan reel: le rectangle
#: theorique peut mordre d'un pixel sur le bord de la page redressee. Cette
#: constante dit **de combien de pixels un rectangle a le droit de sortir**
#: avant d'etre refuse; a zero, la decoupe doit tenir strictement dans la page.
#: L'augmenter elargit donc l'acceptation, elle ne la resserre pas -- le
#: contraire, ecrit dans la premiere version, rendait la constante non
#: seulement inerte mais nuisible: a 500, neuf gabarits sur trente-trois
#: etaient refuses alors qu'ils sont parfaitement interieurs.
#:
#: Elle existe pour que le pilote papier la calibre sans changer de structure,
#: pas pour rester a zero par oubli. Sous-decouper « par precaution » rognerait
#: l'image sur une intuition, et aucune mesure terrain n'existe encore.
CROP_TOLERANCE_PX = 0

#: Vocabulaire **ferme** des avertissements de recadrage. Distinct de ceux de
#: l'ingestion (5.1) et de la detection (5.2): trois vocabulaires voisins
#: fusionnes seraient trois contrats melanges.
SCAN_CROP_WARNING_CODES: tuple[str, ...] = ("ZONE_LEFT_UNUSED",)


class ScanCropError(RuntimeError):
    """Base attrapable des echecs propres au recadrage.

    Elle ne couvre **pas** tout ce qui peut sortir de `build_page_crop_plan`:
    la resolution de geometrie est deleguee a `scan_detection`, qui leve
    `ScanDetectionError` (DPI invalide) et `page_templates.UnknownTemplateError`
    (gabarit inconnu). C'est voulu -- reprendre la garde plutot que la recopier
    veut dire en heriter les exceptions -- mais un appelant qui veut tout
    rattraper doit citer les trois. La premiere version se declarait « base de
    tous les echecs durs », ce qui etait faux et aurait fait passer un refus de
    gabarit pour un plantage.
    """


class CropOutOfPageError(ScanCropError):
    """Le rectangle de decoupe ne tient pas entierement dans la page redressee.

    Le decoupage numpy **tronque silencieusement** hors bornes: `array[y0:y1,
    x0:x1]` avec des bornes hors tableau ne leve rien, il rend un tableau plus
    petit -- ou vide. Un crop partiellement hors page n'est pas vide, il est
    *faux*, ce qu'aucune garde « crop vide » n'attrape. La verification precede
    donc la decoupe.
    """


class SlotPlanError(ScanCropError):
    """Les slots de la page ne peuvent pas etre poses sur les zones du template."""


def validate_warning_code(code: str) -> str:
    if code not in SCAN_CROP_WARNING_CODES:
        raise ValueError(
            f"Code d'avertissement de recadrage inconnu: {code!r}. Vocabulaire "
            f"ferme: {', '.join(SCAN_CROP_WARNING_CODES)}."
        )
    return code


@dataclass(frozen=True)
class FrameCropPlan:
    """Ou decouper une frame, en millimetres et en pixels.

    `slot_index` est **lu dans le payload de la page**, jamais recalcule en
    `index_de_zone + 1`: il est continu a l'echelle du lot et n'est pas remis a
    zero par page, si bien que la forme recalculee est juste sur la page 0 et
    fausse sur toutes les suivantes.
    """

    slot_index: int
    frame_timecode: str | None
    zone_name: str
    zone_rect_mm: tuple[float, float, float, float]
    image_rect_mm: tuple[float, float, float, float]
    crop_x_px: int
    crop_y_px: int
    width_px: int
    height_px: int

    def as_document(self) -> dict:
        return {
            "slot_index": self.slot_index,
            "frame_timecode": self.frame_timecode,
            "zone_name": self.zone_name,
            "zone_rect_mm": [round(v, 6) for v in self.zone_rect_mm],
            "image_rect_mm": [round(v, 6) for v in self.image_rect_mm],
            "crop_x_px": self.crop_x_px,
            "crop_y_px": self.crop_y_px,
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


@dataclass(frozen=True)
class PageCropPlan:
    """Plan de decoupe d'une page. Aucun pixel: il se calcule sans image."""

    template_id: str
    dpi: int
    page_size_px: tuple[int, int]
    frames: tuple[FrameCropPlan, ...]
    unused_zones: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_document(self) -> dict:
        return {
            "template_id": self.template_id,
            "dpi": self.dpi,
            "page_size_px": list(self.page_size_px),
            "frame_count": len(self.frames),
            "unused_zones": list(self.unused_zones),
            "warnings": list(self.warnings),
            "frames": [frame.as_document() for frame in self.frames],
        }


# --- la recette de conversion, une seule fois -------------------------------


def crop_rect_px(image_rect_mm: tuple[float, float, float, float], dpi: int) -> tuple[int, int, int, int]:
    """Convertir un rectangle en millimetres en `(x, y, largeur, hauteur)` pixels.

    **Politique d'arrondi**: celle de la recette unique de la story 5.2
    (`page_templates.mm_to_px`, soit `int(round(mm * dpi / 25.4))`), appelee et
    jamais recopiee. L'impression consomme la meme: un arrondi qui divergerait
    entre les deux decalerait chaque crop d'un pixel a chaque bord sans jamais
    lever d'erreur.

    **Convention de bornes**: l'origine et la **taille** sont quantifiees
    separement -- `x0 = round(x*k)` puis `width = round(w*k)` -- et la tranche
    est **semi-ouverte**, `[y0:y0+height, x0:x0+width]`, comme toute tranche
    numpy. Ce n'est pas le seul choix coherent: on pourrait arrondir les deux
    bords et prendre la difference. Mesure faite avant de trancher, a 600 ppp:

    | Gabarit | bords arrondis separement | origine + taille (retenu) |
    | --- | --- | --- |
    | `tpl-a4-portrait-8f-m5-v1` | **4** tailles: 1023/1024 x 575/576 | **1**: 1024x576 |
    | `tpl-a4-paysage-8f-m2-v1` | **2** tailles | **1**: 842x474 |
    | `tpl-a4-paysage-4f-v1` | **2** tailles | **1**: 1638x921 |

    Toutes les frames d'un meme gabarit doivent avoir **exactement** les memes
    dimensions: une sequence d'images de tailles variables est un echec
    d'encodage cote Epic 6. La contrepartie assumee est qu'un bord recalcule
    depuis les millimetres peut differer d'un pixel du bord publie ici; le
    consommateur ne doit donc pas le recalculer.
    """
    scan_ingest.validate_scan_dpi(dpi)
    if len(image_rect_mm) != 4 or not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in image_rect_mm
    ):
        raise ScanCropError(
            f"Rectangle en millimetres invalide: {image_rect_mm!r}. Quatre "
            "valeurs finies sont attendues."
        )
    x_mm, y_mm, width_mm, height_mm = image_rect_mm
    x_px, y_px = page_templates.mm_to_px(x_mm, y_mm, dpi)
    width_px, _ = page_templates.mm_to_px(width_mm, 0, dpi)
    _, height_px = page_templates.mm_to_px(0, height_mm, dpi)
    return (x_px, y_px, width_px, height_px)


# --- plan de decoupe: arithmetique pure, testable sans pixel ----------------


def build_page_crop_plan(*, template_id: str, slots: list[dict], dpi: int) -> PageCropPlan:
    """Construire le plan de decoupe d'une page depuis son `template_id` et ses slots.

    Aucune marge en parametre, par contrat (AC 4): elle est resolue depuis le
    `TemplateSpec`, et elle seule. La geometrie de page vient de
    `scan_detection.resolve_page_geometry`, qui valide deja le DPI et refuse un
    `template_id` inconnu -- reprise, pas seconde implementation.

    Le plan se construit sur les **slots du payload**, jamais sur
    `len(spec.frame_zones_mm)`: sur la derniere page d'un lot dont le cardinal
    de frames n'est pas un multiple de `frames_per_page`, les zones
    excedentaires sont vides -- ni image, ni contour, du blanc de page. Les
    decouper fabriquerait des frames blanches sans slot correspondant. Elles
    sont nommees dans `unused_zones`.
    """
    geometry = scan_detection.resolve_page_geometry(template_id, dpi)
    spec = geometry["spec"]
    zones = spec.frame_zones_mm
    page_width_px, page_height_px = geometry["page_size_px"]

    _assert_slot_sequence(slots, zones=zones, template_id=template_id)

    frames: list[FrameCropPlan] = []
    for zone, slot in zip(zones, slots):
        slot_index = slot["slot_index"]
        image_rect = page_templates.frame_image_rect_mm(zone, spec.margin_mm)
        x_px, y_px, width_px, height_px = crop_rect_px(image_rect, dpi)
        _assert_inside_page(
            zone_name=zone["name"],
            rect_px=(x_px, y_px, width_px, height_px),
            page_size_px=(page_width_px, page_height_px),
            template_id=template_id,
        )
        frames.append(
            FrameCropPlan(
                slot_index=slot_index,
                frame_timecode=slot.get("frame_timecode"),
                zone_name=zone["name"],
                zone_rect_mm=(zone["x"], zone["y"], zone["width"], zone["height"]),
                image_rect_mm=image_rect,
                crop_x_px=x_px,
                crop_y_px=y_px,
                width_px=width_px,
                height_px=height_px,
            )
        )

    unused = tuple(zone["name"] for zone in zones[len(slots):])
    warnings = ["ZONE_LEFT_UNUSED"] if unused else []
    return PageCropPlan(
        template_id=template_id,
        dpi=dpi,
        page_size_px=(page_width_px, page_height_px),
        frames=tuple(frames),
        unused_zones=unused,
        warnings=tuple(validate_warning_code(code) for code in warnings),
    )


def _assert_slot_sequence(slots, *, zones, template_id: str) -> None:
    """Verifier que les slots peuvent etre poses sur les zones, **dans l'ordre**.

    L'appariement zone <-> slot est **positionnel**: la k-ieme zone recoit le
    k-ieme slot, parce que les deux listes derivent du meme `chunk` chez
    `pdf_composition` (`zip(spec.frame_zones_mm, chunk)` et le `slots[]` du
    payload). L'invariant d'ordre n'etait verifie nulle part, et
    `io.payload.validate_payload` controle bien l'unicite des `slot_index`
    mais **pas leur ordre**: un payload aux slots inverses est donc valide, et
    chaque decoupe recevait l'etiquette et le timecode d'une **autre** frame --
    sans exception, aux bonnes dimensions. C'est exactement le couple que 5.6
    grave dans le nom de fichier.

    L'invariant verifie est celui du producteur: `slot_index` vaut
    `frame.output_rank`, qui parcourt `range(expected_frame_count)`, et une page
    en prend une tranche contigue. Les index d'une page sont donc **consecutifs
    et croissants**. Ne verifier que la croissance laisserait passer un trou,
    qui signifierait une frame manquante entre deux zones voisines.
    """
    if not isinstance(slots, (list, tuple)):
        raise SlotPlanError(f"Slots de page invalides: {slots!r}. Une liste est attendue.")
    if not slots:
        raise SlotPlanError(
            f"La page ne declare aucun slot ({template_id}). Une planche sans "
            "frame n'est pas produite a l'impression: un plan vide signale un "
            "payload tronque, pas une page legitime."
        )
    if len(slots) > len(zones):
        raise SlotPlanError(
            f"La page declare {len(slots)} slots pour un gabarit qui n'a que "
            f"{len(zones)} zones ({template_id}). Le payload et le template ne "
            "decrivent pas la meme page."
        )

    previous: int | None = None
    for position, (zone, slot) in enumerate(zip(zones, slots)):
        if not isinstance(slot, dict) or "slot_index" not in slot:
            raise SlotPlanError(
                f"Slot mal forme pour la zone {zone['name']}: {slot!r}. La cle "
                "'slot_index' est attendue."
            )
        slot_index = slot["slot_index"]
        if not is_strict_int(slot_index) or slot_index < 0:
            raise SlotPlanError(
                f"Index de slot invalide pour la zone {zone['name']}: "
                f"{slot_index!r}. Un entier positif est attendu (`True` est un "
                "`int`)."
            )
        timecode = slot.get("frame_timecode")
        if timecode is not None and not isinstance(timecode, str):
            raise SlotPlanError(
                f"Timecode invalide pour la zone {zone['name']}: {timecode!r}. "
                "Une chaine est attendue -- il est grave dans le nom de fichier "
                "par 5.6."
            )
        if previous is not None and slot_index != previous + 1:
            raise SlotPlanError(
                f"Les slots de la page ne sont pas consecutifs et croissants: "
                f"{previous} puis {slot_index} en position {position} "
                f"({template_id}). L'appariement zone <-> slot est positionnel; "
                "un ordre different attribuerait chaque decoupe a une autre "
                "frame, aux bonnes dimensions et sans erreur."
            )
        previous = slot_index


def _assert_inside_page(
    *,
    zone_name: str,
    rect_px: tuple[int, int, int, int],
    page_size_px: tuple[int, int],
    template_id: str,
) -> None:
    x_px, y_px, width_px, height_px = rect_px
    page_width_px, page_height_px = page_size_px
    if width_px <= 0 or height_px <= 0:
        raise CropOutOfPageError(
            f"Rectangle de decoupe vide pour la zone {zone_name} de "
            f"{template_id}: {width_px}x{height_px} px."
        )
    slack = CROP_TOLERANCE_PX
    if (
        x_px + slack < 0
        or y_px + slack < 0
        or x_px + width_px - slack > page_width_px
        or y_px + height_px - slack > page_height_px
    ):
        raise CropOutOfPageError(
            f"Le rectangle de decoupe de la zone {zone_name} ({template_id}) sort "
            f"de la page: attendu ({x_px}, {y_px}, {width_px}, {height_px}) dans "
            f"une page de {page_width_px}x{page_height_px} px. Une decoupe "
            "partiellement hors page n'est pas vide, elle est fausse."
        )


# --- decoupe effective ------------------------------------------------------


def crop_frames(warped_page: np.ndarray, plan: PageCropPlan) -> list[np.ndarray]:
    """Decouper les frames d'une page redressee selon son plan.

    La taille de la page redressee est confrontee au plan **avant** de
    decouper: une page d'une autre taille rendrait des tranches tronquees
    sans lever, ce qui est le mode d'echec que l'AC 6 vise.

    Les tableaux rendus sont des **vues** sur la page redressee, pas des
    copies: un lot de huit frames a 1200 ppp pese une centaine de mega-octets,
    et 5.6 les ecrit sans les modifier. Le choix est donc volontaire, mais il
    a une consequence que l'appelant doit connaitre -- modifier un crop modifie
    la page, et garder un crop garde la page entiere en memoire. Copier est a
    la charge de qui veut muter.
    """
    if not isinstance(warped_page, np.ndarray) or warped_page.ndim < 2:
        raise ScanCropError(
            f"Page redressee invalide: {type(warped_page).__name__}. Un tableau "
            "d'au moins deux dimensions est attendu."
        )
    height_px, width_px = warped_page.shape[:2]
    if (width_px, height_px) != plan.page_size_px:
        raise CropOutOfPageError(
            f"La page redressee mesure {width_px}x{height_px} px, le plan en "
            f"attend {plan.page_size_px[0]}x{plan.page_size_px[1]}. Decouper "
            "quand meme rendrait des frames tronquees sans erreur."
        )
    crops = []
    for frame in plan.frames:
        crop = warped_page[
            frame.crop_y_px:frame.crop_y_px + frame.height_px,
            frame.crop_x_px:frame.crop_x_px + frame.width_px,
        ]
        # Ceinture et bretelles: la garde de plan a deja verifie les bornes, mais
        # une tranche numpy tronquee est indiscernable d'une tranche correcte.
        if crop.shape[:2] != (frame.height_px, frame.width_px):
            raise CropOutOfPageError(
                f"Decoupe tronquee pour la zone {frame.zone_name}: obtenu "
                f"{crop.shape[1]}x{crop.shape[0]} px pour "
                f"{frame.width_px}x{frame.height_px} attendus."
            )
        crops.append(crop)
    return crops


def warp_detected_page(
    image: np.ndarray, homography: np.ndarray, page_size_px: tuple[int, int]
) -> np.ndarray:
    """Redresser une page avec l'homographie que 5.2 a mesuree.

    Delegue a `detection.aruco.warp_page`, qui n'est qu'un
    `cv2.warpPerspective`: c'est la seule partie du chemin POC qui ne depend
    d'aucune geometrie de page fausse, et en ecrire une seconde ici serait la
    duplication que ces stories combattent. Le **format** de destination, lui,
    vient du template (`page_size_px` de 5.2) et non de `layout`.
    """
    width_px, height_px = page_size_px
    if not (is_strict_int(width_px) and is_strict_int(height_px)) or min(
        width_px, height_px
    ) <= 0:
        raise ScanCropError(
            f"Taille de page invalide: {page_size_px!r}. `cv2.warpPerspective` "
            "avec une taille nulle rend la taille de l'image source, ce qui "
            "produirait une page d'apparence valide."
        )
    return aruco_detection.warp_page(image, homography, width_px, height_px)


def plan_document(plan: PageCropPlan) -> dict:
    document = plan.as_document()
    document["fingerprint"] = fingerprint_of(document)
    return document


def plan_json(plan: PageCropPlan) -> str:
    """Serialisation canonique: deux constructions rendent le meme texte.

    Helpers de canonicalisation importes d'`extraction_previz`, jamais recopies.
    """
    return canonical_json(plan_document(plan))


__all__ = [
    "CROP_TOLERANCE_PX",
    "FINGERPRINT_PREFIX",
    "SCAN_CROP_WARNING_CODES",
    "CropOutOfPageError",
    "FrameCropPlan",
    "PageCropPlan",
    "ScanCropError",
    "SlotPlanError",
    "build_page_crop_plan",
    "crop_frames",
    "crop_rect_px",
    "plan_document",
    "plan_json",
    "validate_warning_code",
    "warp_detected_page",
]
