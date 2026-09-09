"""Rendu reportlab du plan de composition (story 4.1).

Ce module consomme le plan produit par ``pdf_composition`` **sans rien
recalculer**: aucune position, aucune taille, aucun contenu n'est decide ici.
Il ne contient que la traduction plan -> dessin (conversion de repere, rasters,
polices) et l'ecriture atomique du fichier.

Rasters intermediaires testables (AC 9)
---------------------------------------
``build_page_qr_raster`` produit exactement le raster QR insere dans le PDF:
c'est sur lui que les tests decodent le payload (pypdf / pdf2image sont
absents du depot -- limite documentee de la story: la rasterisation du PDF
lui-meme releve du roundtrip d'impression, Epic 5).

TIFF 16 bits -> 8 bits (piege 5, fait documente)
------------------------------------------------
reportlab passe par PIL, qui ne transporte pas le RVB 16 bits par canal: les
TIFF 16 bits du lot sont convertis en 8 bits par canal **avant** insertion --
la meme image d'entree produit strictement le meme raster a chaque rendu. C'est
un support d'impression, pas une copie d'archivage: la profondeur du lot sur
disque reste intacte. Ce plafond 8 bits est une contrainte **externe**, sans
rapport avec la precondition 16 bits de la story 5.0, qui porte sur le chemin
scan.

Depuis la story 5.10, la regle de quantification depend de la compression de
gamut appliquee: troncature ``>> 8`` conservee **bit pour bit** sur le chemin
identite (le defaut du MVP), arrondi au plus proche sur un chemin comprime, ou
une troncature ajouterait un demi-code de biais que ``1/k`` amplifierait au
retour. L'asymetrie est declaree dans ``gamut_map`` et testee des deux cotes.

Date-heure imprimee (EPIC4-ARB-8)
---------------------------------
``generated_at`` est une **entree** de ce module, jamais lue ici ni presente
dans le plan: le PDF n'est pas reproductible octet pour octet (decision
explicite d'Egan), le determinisme contractuel porte sur le plan et le
contenu.

Ecriture atomique (AC 8)
------------------------
Le PDF est rendu dans un fichier temporaire du meme dossier puis renomme;
en cas d'echec ou d'interruption a mi-rendu, aucun PDF partiel ne reste en
place et aucun fichier temporaire ne survit (``finally``, motif 3.6).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path, PurePosixPath

import cv2
import numpy as np
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from . import gamut_map, layout, page_templates, progression, qr_codes
from .pdf_composition import (
    BODY_FONT_MIN_PT,
    TEXT_FONT_NAME,
    LotComposition,
    PagePlan,
    fit_text,
    line_leading_mm,
)


class PdfRenderError(RuntimeError):
    """Raised when a frame raster cannot be loaded or rendered."""


def build_page_qr_raster(page: PagePlan, dpi: int) -> np.ndarray:
    """Raster QR de la page tel qu'insere dans le PDF (symbole + silence ISO).

    Encode ``payload_text`` du plan et rend a ``print_size_mm`` / ``dpi`` via
    ``qr_codes.render_for_print``. La coherence avec le plan est controlee:
    un raster dont le cardinal de modules divergerait du plan signalerait une
    composition perimee.
    """
    native = qr_codes.encode_qr_image(page.qr.payload_text)
    if int(native.shape[0]) != page.qr.module_side:
        raise PdfRenderError(
            f"Raster QR incoherent avec le plan: {native.shape[0]} modules "
            f"encodes, {page.qr.module_side} planifies. Recomposer avant de "
            "rendre."
        )
    return qr_codes.render_for_print(native, page.qr.print_size_mm, dpi)


def draw_patch(canvas, patch, page_height_mm: float) -> None:
    """Tracer une pastille de calibration et, s'il y a lieu, son cadre.

    Extraite du corps de rendu **pour etre appelable par un test**: le depot ne
    rasterise pas ses PDF, donc la seule facon de prouver qu'une instruction de
    trace part vraiment est de l'observer sur un canvas espion. Le cadre de la
    sentinelle blanche est justement l'element dont l'absence ne se verrait
    nulle part ailleurs -- une pastille (255,255,255) sans cadre est
    indiscernable du papier, sur la planche comme dans les tests.
    """
    red, green, blue = patch.rgb
    canvas.setFillColorRGB(red / 255.0, green / 255.0, blue / 255.0)
    x_pt, y_pt = _to_pdf_point(patch.x_mm, patch.y_mm + patch.size_mm, page_height_mm)
    canvas.rect(x_pt, y_pt, patch.size_mm * mm, patch.size_mm * mm, stroke=0, fill=1)
    if not patch.frame_mm:
        return
    frame_x_mm, frame_y_mm, frame_side_mm = patch_frame_path_mm(patch)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(patch.frame_mm * mm)
    frame_x_pt, frame_y_pt = _to_pdf_point(
        frame_x_mm, frame_y_mm + frame_side_mm, page_height_mm
    )
    canvas.rect(
        frame_x_pt, frame_y_pt, frame_side_mm * mm, frame_side_mm * mm, stroke=1, fill=0
    )


def patch_frame_path_mm(patch) -> tuple[float, float, float]:
    """Rectangle du **chemin** de trace du cadre d'une pastille, en mm.

    Rend ``(x_mm, y_mm, side_mm)`` dans le repere haut-gauche du template.

    Le cadre de la sentinelle blanche (story 5.9, AC 5) doit etre **interieur**
    a l'emprise: un cadre exterieur mangerait ``PATCH_SPACING_MM`` et ferait
    tomber la garantie d'espacement d'impression. Or reportlab centre le trait
    sur le chemin, donc un rectangle trace sur l'emprise deborderait d'une
    demi-epaisseur de chaque cote. Le chemin est donc rentre d'une demi-
    epaisseur, et le trait occupe alors exactement ``[0, frame_mm]`` depuis
    chaque bord du patch.

    Fonction pure et separee du rendu **pour etre testable**: le depot ne
    rasterise pas ses PDF (ni pypdf ni pdf2image), donc un cadre trace au
    mauvais endroit ne serait visible dans aucun test s'il restait enfoui dans
    l'appel a reportlab.
    """
    half = patch.frame_mm / 2.0
    return (patch.x_mm + half, patch.y_mm + half, patch.size_mm - patch.frame_mm)


def load_frame_image_for_print(path: str | Path, gamut_map_id: str) -> Image.Image:
    """Charger une frame du lot en RVB 8 bits par canal, deterministe.

    Seul point du depot ou des pixels de frame entrent dans le PDF, et donc
    seul point ou la compression de gamut `G` peut s'appliquer (story 5.10).

    **Ordre interne, et pourquoi il compte** (story 5.10, AC 4): lecture ->
    normalisation de canaux **a la profondeur native** -> application de `G` ->
    **une seule** quantification vers 8 bits. Appliquer `G` apres une reduction
    prealable comprimerait une donnee dont la quantification est deja prise, et
    `1/k` amplifierait au retour une perte inutile. Consequence directe: sur un
    `uint16` a quatre canaux, `G` ne s'applique **jamais** au canal alpha --
    la normalisation, qui l'elimine, precede l'application, precisement pour que
    la question ne se pose pas.

    La permutation de la reduction et de la conversion de canaux est **neutre a
    l'identite**: verifie sur les trois conversions du module (`GRAY2RGB`,
    `BGR2RGB`, `BGRA2RGB`), egalite exacte sur tableaux `uint16` aleatoires.
    Sous `gamut-map-none-1`, la fonction produit donc exactement les memes
    octets qu'avant la story 5.10 -- ancrage de non-regression fige par test.

    `gamut_map_id` est **obligatoire et sans valeur par defaut**: un defaut
    laisserait un appelant sauter `G` en silence tout en imprimant l'identifiant
    dans le QR, c'est-a-dire produire une planche dont la declaration ment. La
    valeur vient du plan (`LotComposition.gamut_map_id`), jamais d'une decision
    du rendu -- ce module ne decide ni position, ni taille, ni contenu.

    Toute profondeur autre que 8/16 bits et tout cardinal de canaux autre que
    1/3/4 sont refuses plutot que convertis en silence.
    """
    try:
        transform = gamut_map.get_gamut_map(gamut_map_id)
    except gamut_map.GamutMapError as error:
        # `GamutMapError` derive de `ValueError`, `PdfRenderError` de
        # `RuntimeError`: aucune des clauses `except` de la commande `makepdf`
        # ne nommait la premiere, si bien qu'un identifiant inconnu remontait
        # en trace brute au lieu du refus nomme du module.
        raise PdfRenderError(str(error)) from error
    array = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if array is None:
        raise PdfRenderError(
            f"Frame illisible: {path}. Le lot a ete verifie avant composition; "
            "un fichier devenu illisible entre-temps doit etre re-extrait."
        )
    if array.dtype not in (np.uint8, np.uint16):
        raise PdfRenderError(
            f"Profondeur de pixel non geree pour l'impression: {array.dtype} "
            f"({path}). Attendu: 8 ou 16 bits par canal."
        )
    if array.ndim == 2:
        array = cv2.cvtColor(array, cv2.COLOR_GRAY2RGB)
    elif array.shape[2] == 4:
        array = cv2.cvtColor(array, cv2.COLOR_BGRA2RGB)
    elif array.shape[2] == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
    else:
        # Gris+alpha (2 canaux) ou tout autre cardinal: refus explicite plutot
        # qu'un `cv2.error` nu -- la regle du module est "refusee plutot que
        # convertie en silence" (revue 4.1 du 2026-08-06).
        raise PdfRenderError(
            f"Nombre de canaux non gere pour l'impression: {array.shape[2]} "
            f"({path}). Attendu: 1 (gris), 3 (BGR) ou 4 (BGRA)."
        )
    return Image.fromarray(transform.to_print_8bit(array))


def _to_pdf_point(x_mm: float, y_mm: float, page_height_mm: float) -> tuple[float, float]:
    """Repere page (origine haut-gauche, y vers le bas) -> points reportlab."""
    return x_mm * mm, (page_height_mm - y_mm) * mm


def _draw_rect_image(canvas, image: ImageReader, rect_mm, page_height_mm, **kwargs) -> None:
    x_mm_, y_mm_, w_mm, h_mm = rect_mm
    x_pt, y_pt = _to_pdf_point(x_mm_, y_mm_ + h_mm, page_height_mm)
    canvas.drawImage(image, x_pt, y_pt, width=w_mm * mm, height=h_mm * mm, **kwargs)


def _draw_text_lines(canvas, rect_mm, lines, page_height_mm, font_size=BODY_FONT_MIN_PT) -> None:
    x_mm_, y_mm_, _, _ = rect_mm
    canvas.setFont(TEXT_FONT_NAME, font_size)
    leading_mm = font_size * 0.42 + 1.2
    baseline = y_mm_ + leading_mm
    for line in lines:
        x_pt, y_pt = _to_pdf_point(x_mm_, baseline, page_height_mm)
        canvas.drawString(x_pt, y_pt, line)
        baseline += leading_mm


def marker_raster_px(size_mm: float, render_dpi: int) -> int:
    """Cote (px) du raster ArUco embarque, derive du DPI de rendu du plan.

    Le contrat de `--dpi` couvre tous les elements embarques: rasteriser les
    marqueurs a un cote fixe (400 px, ~339 dpi pour 30 mm) contredisait ce
    contrat des que l'operateur demandait un autre DPI (revue 4.1 du
    2026-08-06).
    """
    return layout.mm_to_px(size_mm, size_mm, render_dpi)[0]


def _render_page(canvas, plan: LotComposition, page: PagePlan, frames_dir: Path,
                 page_height_mm: float, generated_line: str) -> None:
    # --- frames: letterbox deterministe, jamais d'etirement anisotrope ------
    for slot in page.frames:
        frame_path = frames_dir / slot.frame_filename
        # L'identifiant vient du plan, jamais d'une decision du rendu: c'est
        # la regle fondatrice de ce module, et c'est aussi ce qui garantit que
        # la `G` appliquee est celle que le QR declare (story 5.10, AC 7).
        image = ImageReader(
            load_frame_image_for_print(frame_path, plan.gamut_map_id)
        )
        _draw_rect_image(
            canvas,
            image,
            slot.image_rect_mm,
            page_height_mm,
            preserveAspectRatio=True,
            anchor="c",
        )
        # Contour fin de la zone (repere de decoupe / controle visuel).
        zx, zy, zw, zh = slot.zone_rect_mm
        x_pt, y_pt = _to_pdf_point(zx, zy + zh, page_height_mm)
        canvas.setLineWidth(0.3)
        canvas.rect(x_pt, y_pt, zw * mm, zh * mm)

    # --- marqueurs ArUco (politique layout.PRINTED_MARKER_IDS, via le plan) --
    for marker in page.markers:
        raster = layout.generate_aruco_marker_image(
            marker.marker_id,
            size_px=marker_raster_px(marker.size_mm, plan.render_dpi),
        )
        half = marker.size_mm / 2
        _draw_rect_image(
            canvas,
            ImageReader(Image.fromarray(raster)),
            (marker.center_x_mm - half, marker.center_y_mm - half, marker.size_mm, marker.size_mm),
            page_height_mm,
        )

    # --- QR (raster identique a celui que les tests decodent) ---------------
    qr_raster = build_page_qr_raster(page, plan.render_dpi)
    _draw_rect_image(
        canvas,
        ImageReader(Image.fromarray(qr_raster)),
        page.qr.footprint_rect_mm,
        page_height_mm,
    )

    # --- patchs de calibration (valeurs resolues par 4.7/4.8 dans le plan) --
    for patch in page.patches:
        draw_patch(canvas, patch, page_height_mm)
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(1)

    # --- textes (contrat 4.2 / EPIC4-ARB-8): blocs du plan, rien d'autre ----
    # Les lignes imprimees sont exactement celles des blocs; la seule ligne
    # ajoutee au rendu est la date-heure de generation (EPIC4-ARB-8), dans le
    # bloc d'identite, hors du plan pour preserver son determinisme.
    text = page.text
    # La place de la date-heure est **lue sur le plan** et non decidee ici (story 5.18):
    # ce module ne decide ni position, ni taille, ni contenu, et il decidait pourtant
    # celle-la en la posant apres `FOOTER_IDENTITY_LINE_COUNT` lignes du bloc de pied.
    # Sous une disposition ou l'identite n'est plus dans le pied, la meme constante
    # aurait glisse la date au milieu des lignes techniques sans qu'aucune etape
    # n'echoue -- et la reservation de tenue verticale, elle, aurait compte la ligne
    # ailleurs.
    date_block, date_index = text.date_line_slot
    for block in text.blocks:
        lines = block.lines
        if block.name == date_block:
            lines = block.lines[:date_index] + (generated_line,) + block.lines[date_index:]
        _draw_text_lines(canvas, block.rect_mm, lines, page_height_mm, font_size=block.font_pt)
    canvas.setFont(TEXT_FONT_NAME, BODY_FONT_MIN_PT)
    for label in text.slot_labels:
        x_pt, y_pt = _to_pdf_point(
            label.rect_mm[0], label.rect_mm[1] + label.rect_mm[3] - 0.5, page_height_mm
        )
        canvas.drawString(x_pt, y_pt, label.text)


def _assert_declared_gamut_map_matches(plan: LotComposition) -> None:
    """Refuser un plan dont le QR d'une page ne declare pas la `G` du plan."""
    for page in plan.pages:
        declared = page.qr.payload.get("gamut_map_id")
        if declared != plan.gamut_map_id:
            raise PdfRenderError(
                f"Page {page.page_index}: le QR declare la compression de gamut "
                f"{declared!r} alors que le plan applique {plan.gamut_map_id!r}. "
                "Imprimer produirait une planche dont la declaration ment sur "
                "la transformation appliquee, et le defaut ne se verrait qu'a "
                "l'expansion, au scan. Recomposer le plan."
            )


def render_lot_pdf(
    plan: LotComposition,
    project_dir: str | Path,
    output_path: str | Path,
    *,
    generated_at: datetime,
    rappel_progression=None,
) -> Path:
    """Rendre le PDF multi-pages du plan, atomiquement, et rendre son chemin.

    ``project_dir`` resout ``plan.frames_dir`` (relatif au projet);
    ``generated_at`` est la date-heure imprimee sur chaque planche
    (EPIC4-ARB-8) -- fournie par l'appelant, jamais lue ici.

    **Garde de coherence avant tout rendu** (story 5.10, AC 7): l'identifiant
    de compression du plan et celui que chaque page declare dans son QR sont
    deux etats distincts une fois la composition faite. Rien ne les
    confrontait, si bien qu'un plan reconstruit a la main -- un
    `dataclasses.replace` suffit -- produisait un PDF parfaitement valide dont
    les frames etaient comprimees et dont le QR declarait l'identite. C'est le
    pire defaut de la chaine couleur: aucun symptome a l'impression, une
    expansion fausse au scan, et depuis EPIC5-ARB-20 un manifest qui
    contredirait le QR de la meme planche. La verification coute une boucle.

    ``rappel_progression`` est **optionnel** (``AR3``, story 5.28) : sans lui,
    rien ne change -- meme PDF, memes exceptions. Avec lui, il recoit un jalon
    ``(faites, total)`` **par page reellement ecrite**, ou ``total`` vaut
    ``plan.page_count``. C'est le contrat deja gele par
    ``scan_output_frames.write_lot_output_frames``, et il est ouvert par le
    **meme** mecanisme -- ``progression.EmetteurProgression`` -- plutot que par
    un compteur redige a cote : une seconde redaction divergerait a la premiere
    evolution du canal (story 11.7, tache B4, AC 2.6).

    **Aucun jalon avant la premiere page.** Le canal ne s'ouvre qu'apres les
    refus durs de cette sequence -- garde de coherence de la compression,
    creation du dossier de sortie, resolution du gabarit --, et chaque jalon est
    emis **apres** que sa page a ete dessinee, jamais avant. Un refus ne doit
    produire aucune progression, sans quoi l'ecran afficherait une tache qui a
    commence alors que rien n'a ete ecrit (`EPIC7-ARB-79`).

    Le canal est **observationnel** : un rappel qui leve est absorbe et
    journalise une seule fois par ``EmetteurProgression``, tandis que les refus
    durs du rendu -- y compris l'echec d'une page a mi-course -- traversent
    intacts, texte compris. La symetrie est l'interdit d'`EPIC7-ARB-79` :
    absorber le canal, jamais le travail observe.
    """
    _assert_declared_gamut_map_matches(plan)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = Path(project_dir) / PurePosixPath(plan.frames_dir)
    spec = page_templates.get_template(plan.template_id)
    page_height_mm = spec.page_height_mm
    generated_line = f"genere le {generated_at.strftime('%Y-%m-%d %H:%M %Z').strip()}"

    # Le canal ne s'ouvre qu'ICI, une fois tous les refus durs passes -- meme
    # geste et meme motif que `write_lot_output_frames`. `total` vaut
    # `plan.page_count` **verbatim**, jamais `len(plan.pages)` : c'est le
    # cardinal que le plan declare, celui que le manifest, le QR et la
    # pagination du produit portent tous les trois, et c'est lui que l'AC 2.6
    # nomme. Un plan dont les deux divergeraient est un plan fautif, et le
    # rendre visible vaut mieux que le maquiller dans la barre.
    emetteur = progression.EmetteurProgression(rappel_progression, plan.page_count)

    tmp_path = output_path.parent / f".{output_path.name}.tmp-{os.getpid()}"
    try:
        canvas = pdfcanvas.Canvas(
            str(tmp_path), pagesize=(spec.page_width_mm * mm, spec.page_height_mm * mm)
        )
        ecrites = 0
        for page in plan.pages:
            _render_page(canvas, plan, page, frames_dir, page_height_mm, generated_line)
            canvas.showPage()
            # Un jalon **apres** le dessin de la page, jamais avant : le
            # numerateur est litteralement le nombre de planches deja posees
            # dans le document. Une page dont `_render_page` leve n'est jamais
            # comptee.
            ecrites += 1
            emetteur.emettre(ecrites)
        canvas.save()
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return output_path
