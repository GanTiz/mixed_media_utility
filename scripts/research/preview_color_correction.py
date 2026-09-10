"""Voir la correction couleur avant de juger de son utilite.

Deux questions d'Egan du 2026-08-10, et ce banc y repond separement:

1. « **puis-je voir le resultat de la correction avant de juger de l'utilite** [d'une
   LUT] ? » -> le mode `--images` ajuste `C = M o A` sur les pastilles reellement
   imprimees et rescannees de chaque page, l'applique aux **zones de frames** de la
   meme page, et ecrit un avant/apres cote a cote.
2. « **peut-on tout de suite lancer la creation d'une LUT ?** » -> le mode `--models`
   compare plusieurs formes de correction **en validation croisee**. Un modele plus
   riche *baisse toujours* son residu d'ajustement, et un residu qui baisse ne dit
   rien: seul un point laisse hors de l'ajustement dit si le modele a appris la
   transformation ou appris les points.

   **La reponse mesuree est non, et la validation croisee ne suffisait pas a la
   donner** (2026-08-10): le modele riche gagne d'un facteur deux en croise et rend
   une image visiblement fausse. Ce que la croisee ne voit pas est
   l'**extrapolation** -- les pastilles sont dans le domaine d'ajustement par
   construction, 8,3 % des pixels d'une frame ne le sont pas. D'ou l'utilite de
   lancer les deux modes ensemble, jamais `--models` seul.

Banc de recherche, hors production. Il ne remplace pas la story 5.4b: il ne persiste
rien, n'ecrit aucun manifest, et ajuste sur des pages entieres sans mode degrade.
Ce qu'il partage avec elle est l'essentiel a verifier tot -- la forme de `C`, son
ordre (`EPIC5-ARB-26`) et son exclusion des sentinelles (`patch-values-2`).

    PYTHONPATH=src:scripts/research python3 scripts/research/preview_color_correction.py \\
        --scan srcs/2026-08-10_141012_Patches_Saturation.pdf --pages 7 \\
        --preset patches-18-v2 --images --models
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/research")

import cv2  # noqa: E402

from mixed_media_utility import (  # noqa: E402
    patch_presets,
    patch_values,
    scan_crop,
    scan_detection,
    scan_ingest,
)
from patch_delta_e_field_measurement import (  # noqa: E402
    DPI,
    PROJ,
    TEMPLATE,
    apply_affine,
    de76,
    eotf,
    fit_affine,
    fit_row_sum_one_matrix,
    oetf,
    sample_page,
)


# ---------------------------------------------------------------------------
# Les modeles compares. Chacun rend une fonction `lineaire -> lineaire`.
# ---------------------------------------------------------------------------

def _model_a(src_lin, dst_lin, neutral_mask):
    """Etage A seul: affine par canal, ajuste sur l'axe neutre en lumiere lineaire."""
    params = fit_affine(src_lin[neutral_mask], dst_lin[neutral_mask])
    return lambda x: apply_affine(params, x)


def _model_ma(src_lin, dst_lin, neutral_mask):
    """`C = M o A`, la forme specifiee par EPIC5-ARB-26."""
    stage_a = _model_a(src_lin, dst_lin, neutral_mask)
    matrix = fit_row_sum_one_matrix(stage_a(src_lin), dst_lin)
    return lambda x: stage_a(x) @ matrix.T


def _quadratic_design(x, cross_terms: bool):
    """Termes lineaires, carres et -- au choix -- croises.

    Six colonnes sans les croises (R, V, B, R^2, V^2, B^2), neuf avec (+ RV, RB,
    VB). Pas de constante: l'etage A porte deja le decalage, et l'ajouter ici le
    rendrait indetermine.

    Le nombre de colonnes se rapporte au cardinal reel des observations, qui n'est
    pas celui des valeurs: `patches-18-v2` porte 10 valeurs d'ajustement **repetees
    deux fois**, donc **20 observations par page**. A neuf colonnes plus les deux de
    l'etage A, la determination garde donc de la marge -- constat mesure, apres
    avoir ecrit ici l'inverse.
    """
    r, g, b = x[:, 0], x[:, 1], x[:, 2]
    columns = [r, g, b, r * r, g * g, b * b]
    if cross_terms:
        columns += [r * g, r * b, g * b]
    return np.stack(columns, axis=1)


def _make_quadratic_model(cross_terms: bool):
    """`A` puis une forme quadratique par canal.

    Equivalent polynomial global d'une LUT 3D, qui est une interpolation locale.

    **La comparaison s'arrete a l'interpolation, et l'assimilation serait fausse
    au-dela** (mesure du 2026-08-10): une LUT **clampe** a sa frontiere, un polynome
    **extrapole**. Sur les 8,3 % de pixels d'une frame hors du domaine d'ajustement,
    ce modele sort a 1,59 -- 59 % au-dessus du blanc -- la ou `C = M o A` sort a
    0,88. Il gagne donc en validation croisee et perd sur l'image. Ne pas conclure
    de son echec que la voie LUT est fermee: ce qui la conditionne est une regle de
    bord, pas de la precision.
    """

    def build(src_lin, dst_lin, neutral_mask):
        stage_a = _model_a(src_lin, dst_lin, neutral_mask)
        design = _quadratic_design(stage_a(src_lin), cross_terms)
        coefficients = np.stack(
            [np.linalg.lstsq(design, dst_lin[:, c], rcond=None)[0] for c in range(3)], axis=1)
        return lambda x: _quadratic_design(stage_a(x), cross_terms) @ coefficients

    return build


# ---------------------------------------------------------------------------
# Correction separant clarte et chroma (piste du 2026-08-10)
# ---------------------------------------------------------------------------

#: Matrice sRGB lineaire -> XYZ et son inverse, plus le blanc D65. Recopiees de la
#: meme source que `lab()` du banc de production, dont ce module est l'inverse: deux
#: definitions qui divergeraient rendraient l'aller-retour non neutre, et le symptome
#: serait une correction qui derive sans qu'aucun ajustement soit en cause.
_RGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                        [0.2126729, 0.7151522, 0.0721750],
                        [0.0193339, 0.1191920, 0.9503041]])
_XYZ_TO_RGB = np.linalg.inv(_RGB_TO_XYZ)
_WHITE_D65 = np.array([0.95047, 1.0, 1.08883])
_EPS, _KAPPA = 216 / 24389, 24389 / 27


def lab_of_linear(lin: np.ndarray) -> np.ndarray:
    """L*a*b* depuis du sRGB **lineaire** (et non encode, contrairement a `lab()`)."""
    ratio = (np.asarray(lin, float) @ _RGB_TO_XYZ.T) / _WHITE_D65
    f = np.where(ratio > _EPS, np.cbrt(np.maximum(ratio, 0.0)), (_KAPPA * ratio + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def linear_of_lab(values: np.ndarray) -> np.ndarray:
    """Inverse exact de `lab_of_linear`, verifie par aller-retour dans les tests."""
    values = np.asarray(values, float)
    fy = (values[..., 0] + 16) / 116
    fx = fy + values[..., 1] / 500
    fz = fy - values[..., 2] / 200
    f = np.stack([fx, fy, fz], axis=-1)
    cubed = f ** 3
    ratio = np.where(cubed > _EPS, cubed, (116 * f - 16) / _KAPPA)
    return (ratio * _WHITE_D65) @ _XYZ_TO_RGB.T


def _fit_chroma_only(measured, reference):
    """Ajuster la seule 2x2 de chroma, pour pouvoir la composer avec une autre clarte."""
    src_lab = lab_of_linear(eotf(measured))
    dst_lab = lab_of_linear(eotf(reference))
    plan = np.stack([src_lab[:, 1], src_lab[:, 2], np.ones(len(src_lab))], axis=1)
    solved = np.linalg.lstsq(plan, dst_lab[:, 1:3], rcond=None)[0]
    matrix, offset = solved[:2].T, solved[2]
    return lambda ab: ab @ matrix.T + offset


def _make_lab_model(correct_chroma: bool, with_offset: bool = True,
                    lightness_on_neutrals: bool = True, lightness_degree: int = 1):
    """Corriger **L\* seul**, ou L\* puis (a\*, b\*) par une 2x2, jamais par canal RGB.

    Piste ouverte par la mesure du 2026-08-10, et c'est un changement de **famille**
    et non de reglage: l'etage `A` specifie applique des gains **par canal RGB**
    ajustes sur les gris. Neutraliser les gris de cette facon change par construction
    les **rapports entre canaux** de toute couleur non neutre, donc sa teinte -- mesure
    a l'appui, `A` seule laisse 3,37 dE76 de biais de chroma sur la peau la ou le scan
    brut n'en a que 0,94.

    Ici la clarte et la chroma sont **orthogonales par construction**: corriger `L*`
    ne deplace ni `a*` ni `b*`. La variante `correct_chroma=False` est le temoin qui
    tranche -- si elle rend la clarte en gardant la chroma du scan brut, alors les deux
    sont bien decouplables et la forme specifiee est ce qui les couplait.
    """

    def build(src_lin, dst_lin, neutral_mask):
        src_lab, dst_lab = lab_of_linear(src_lin), lab_of_linear(dst_lin)
        # L*: par defaut une affine sur le seul axe neutre, comme l'etage A. Deux
        # relachements mesures utiles le 2026-08-10, l'affine sur quatre neutres
        # sur-corrigeant la peau de ~3 unites de L*: ajuster sur **tous** les points
        # (L* est defini pour toute couleur, pas seulement pour un gris) et monter au
        # degre 2 (la reponse du couple imprimante+scanner n'est pas affine en L*).
        rows = neutral_mask if lightness_on_neutrals else np.ones(len(src_lab), bool)
        lightness = src_lab[rows, 0]
        design = np.stack([lightness ** power for power in range(lightness_degree, -1, -1)],
                          axis=1)
        coefficients = np.linalg.lstsq(design, dst_lab[rows, 0], rcond=None)[0]

        chroma_matrix = np.eye(2)
        chroma_offset = np.zeros(2)
        if correct_chroma:
            # (a*, b*): 2x2 ajustee sur TOUS les points d'ajustement. Un neutre y
            # contribue legitimement -- sa chroma cible est nulle, donc il tire la
            # correction vers "ne pas colorer un gris", ce qui est voulu.
            columns = [src_lab[:, 1], src_lab[:, 2]]
            if with_offset:
                columns.append(np.ones(len(src_lab)))
            plan = np.stack(columns, axis=1)
            solved = np.linalg.lstsq(plan, dst_lab[:, 1:3], rcond=None)[0]
            chroma_matrix = solved[:2].T
            if with_offset:
                chroma_offset = solved[2]

        def apply(lin):
            values = lab_of_linear(lin)
            out = np.empty_like(values)
            out[..., 0] = np.polyval(coefficients, values[..., 0])
            out[..., 1:3] = values[..., 1:3] @ chroma_matrix.T + chroma_offset
            return linear_of_lab(out)

        return apply

    return build


MODELS = {
    "A seule (affine/canal)": _model_a,
    "C = M o A (specifie)": _model_ma,
    "A + quadratique 6 termes": _make_quadratic_model(cross_terms=False),
    "A + quadratique 9 termes": _make_quadratic_model(cross_terms=True),
    "Lab: L* seul (temoin)": _make_lab_model(correct_chroma=False),
    "Lab: L* + chroma 2x2": _make_lab_model(correct_chroma=True),
    "Lab: L* deg2 tous + chroma": _make_lab_model(
        correct_chroma=True, lightness_on_neutrals=False, lightness_degree=2),
    "Lab: L* deg2 tous seul": _make_lab_model(
        correct_chroma=False, lightness_on_neutrals=False, lightness_degree=2),
    # Affine sur tous les points: le degre 2 gagne dans la plage mesuree et perd
    # au-dela -- mesure du 2026-08-10, il degrade les noirs d'une frame de 1,98 a
    # 3,66 dE76 parce qu'un polynome extrapole la ou une affine se prolonge.
    "Lab: L* deg1 tous seul": _make_lab_model(
        correct_chroma=False, lightness_on_neutrals=False, lightness_degree=1),
}

#: Nombre de colonnes de conception par canal, pour rapporter la marge de
#: determination a cote du resultat: un modele qui gagne sans marge ne se
#: transporte pas a un autre jeu de valeurs.
MODEL_PARAMETERS = {
    "A seule (affine/canal)": 2,
    "C = M o A (specifie)": 4,
    "A + quadratique 6 termes": 8,
    "A + quadratique 9 termes": 11,
    "Lab: L* seul (temoin)": 2,
    "Lab: L* + chroma 2x2": 8,
    "Lab: L* deg2 tous + chroma": 9,
    "Lab: L* deg2 tous seul": 3,
    "Lab: L* deg1 tous seul": 2,
}


# ---------------------------------------------------------------------------
# Ajustement d'une page
# ---------------------------------------------------------------------------

def _adjustment_set(preset_id: str):
    preset = patch_presets.get_patch_preset(preset_id)
    table = patch_values.get_patch_values_table(preset.values_version)
    adjustment = {v.value_id for v in table.adjustment_values()}
    neutral = {v.value_id for v in table.adjustment_values()
               if v.role == patch_values.ROLE_NEUTRAL}
    return adjustment, neutral


def read_page(path: str, rank: int, layout, adjustment_ids, neutral_ids,
              template: str = TEMPLATE):
    """Rendre les mesures d'ajustement d'une page, en lumiere lineaire.

    Les sentinelles sont exclues **par l'API de la table**, jamais par un filtre
    local: un point ecrete par construction tirerait toute la correction, et le
    symptome serait une correction plausible.
    """
    measured, reference, ids = sample_page(path, rank, layout, template)
    ids = np.array(ids)
    keep = np.isin(ids, list(adjustment_ids))
    src, dst, kept = measured[keep], reference[keep], ids[keep]
    return eotf(src), eotf(dst), dst, np.isin(kept, list(neutral_ids)), kept


def correction_for_page(src_lin, dst_lin, neutral_mask, model_name="C = M o A (specifie)"):
    return MODELS[model_name](src_lin, dst_lin, neutral_mask)


# ---------------------------------------------------------------------------
# Mode --models : validation croisee leave-one-out
# ---------------------------------------------------------------------------

def compare_models(pages) -> None:
    """Comparer les formes de correction en ajustement **et** en validation croisee.

    Le residu d'ajustement est rapporte a titre de repere, jamais comme verdict:
    il decroit mecaniquement avec le nombre de parametres. La colonne qui decide
    est celle du point **laisse dehors**.

    Chaque valeur d'ajustement est retiree a son tour, le modele est ajuste sur les
    autres, et son erreur est mesuree sur celle qui manquait. Un modele qui apprend
    la transformation garde une erreur voisine de son residu; un modele qui apprend
    les points la voit exploser.
    """
    values = len(pages[0][0])
    print("\nFORMES DE CORRECTION -- ajustement contre validation croisee (dE76)")
    print(f"  jeu d'ajustement: {values} valeurs par page, "
          f"{len(pages)} pages, retrait d'un point a la fois")
    print(f"  {'modele':28s} {'par.':>5s} {'residu ajuste':>14s} "
          f"{'valide croise':>14s}  verdict")
    rows = []
    for name in MODELS:
        fitted, held_out = [], []
        for src_lin, dst_lin, dst_enc, neutral_mask, _ids in pages:
            model = MODELS[name](src_lin, dst_lin, neutral_mask)
            fitted.append(de76(oetf(np.clip(model(src_lin), 0, 1)), dst_enc))

            for index in range(len(src_lin)):
                keep = np.ones(len(src_lin), bool)
                keep[index] = False
                # L'axe neutre doit rester ajustable: retirer un neutre laisse
                # trois points a l'etage A, ce qui suffit a une affine par canal.
                if neutral_mask[keep].sum() < 2:
                    continue
                partial = MODELS[name](src_lin[keep], dst_lin[keep], neutral_mask[keep])
                predicted = oetf(np.clip(partial(src_lin[index:index + 1]), 0, 1))
                held_out.append(float(de76(predicted, dst_enc[index:index + 1])[0]))

        fit_mean = float(np.mean([a.mean() for a in fitted]))
        cv_mean = float(np.mean(held_out))
        rows.append((name, fit_mean, cv_mean))

    best_cv = min(r[2] for r in rows)
    for name, fit_mean, cv_mean in rows:
        parameters = MODEL_PARAMETERS[name]
        verdict = "MEILLEUR en croise" if cv_mean == best_cv else ""
        # Un modele dont le nombre de parametres approche le cardinal du jeu
        # d'ajustement peut gagner ici et ne pas se transporter: l'ajustement y
        # devient une interpolation, et la marge de determination est nulle.
        if parameters >= values - 1:
            verdict = (verdict + " -- sans marge" if verdict else "sans marge").strip()
        print(f"  {name:28s} {parameters:5d} {fit_mean:14.2f} {cv_mean:14.2f}  {verdict}")
    print("\n  Lecture: le residu ajuste decroit toujours avec le nombre de parametres.")
    print("  Seule la colonne croisee dit si un modele plus riche interpole mieux.")
    print("  Elle ne dit RIEN de l'extrapolation, et c'est la que tout se joue:")
    print("  8,3 % des pixels d'une frame reelle sont hors du domaine d'ajustement,")
    print("  ou un quadratique depasse de 59 % au-dessus du blanc quand une affine")
    print("  depasse de 11 %. Voir --images, et l'analyse du 2026-08-10.")


# ---------------------------------------------------------------------------
# Mode --images : avant / apres sur les vraies zones de frames
# ---------------------------------------------------------------------------

def _apply_to_image(bgr: np.ndarray, model) -> np.ndarray:
    """Appliquer une correction ajustee en RGB lineaire a une image BGR.

    Le contrat de canaux est celui de `color_pipeline`: **BGR**. Les valeurs de
    reference des pastilles sont declarees en **RGB**. L'inversion se fait ici, une
    seule fois, et c'est le piege que la story 5.4b nomme: une inversion R/B ne
    produit pas une image cassee mais une correction qui converge sur les mauvaises
    couleurs.
    """
    rgb = bgr[:, :, ::-1].astype(np.float64) / 255.0
    flat = eotf(rgb.reshape(-1, 3))
    corrected = oetf(np.clip(model(flat), 0.0, 1.0)).reshape(rgb.shape)
    return (np.clip(corrected, 0.0, 1.0) * 255.0).round().astype(np.uint8)[:, :, ::-1]


#: Les formes montrees cote a cote dans l'apercu. La question d'Egan porte sur
#: l'utilite d'un modele plus riche: la comparer a l'oeil demande les deux dans la
#: meme image, sur la meme page, sous le meme eclairage de scan.
PREVIEW_MODELS = ("C = M o A (specifie)", "A + quadratique 9 termes")

#: Les formes montrees dans le volet de verite: la specifiee, et celle qui gagne
#: sur le **contenu** des quatre frames reelles (mesure du 2026-08-11). La premiere
#: de la liste est celle dont le residu de pastilles est rapporte.
TRUTH_PREVIEW_MODELS = ("C = M o A (specifie)", "Lab: L* + chroma 2x2")


def _label(image: np.ndarray, text: str) -> np.ndarray:
    """Graver le nom du volet: trois images cote a cote sans etiquette sont illisibles."""
    banner = np.full((34, image.shape[1], 3), 255, np.uint8)
    cv2.putText(banner, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    return np.vstack([banner, image])


def write_previews(path: str, rank, layout, sets, out_dir: Path, label: int = 1,
                   template: str = TEMPLATE) -> list[Path]:
    adjustment_ids, neutral_ids = sets
    src_lin, dst_lin, dst_enc, neutral_mask, _ids = read_page(
        path, rank, layout, adjustment_ids, neutral_ids, template)
    models, residuals = [], []
    for name in PREVIEW_MODELS:
        model = MODELS[name](src_lin, dst_lin, neutral_mask)
        models.append((name, model))
        residuals.append(float(de76(oetf(np.clip(model(src_lin), 0, 1)), dst_enc).mean()))

    geometry = scan_detection.resolve_page_geometry(template, DPI)
    image = scan_ingest.load_page_array(PROJ, scan_ingest.PageLocator(path, rank), dpi=DPI)
    markers = scan_detection._detect_markers_document(image, DPI)["images"][0]["markers"]
    homography, _scale = scan_detection.compute_template_homography(markers, geometry, DPI)
    page = scan_crop.warp_detected_page(image, homography, geometry["page_size_px"])
    if page.dtype == np.uint16:
        page = (page >> 8).astype(np.uint8)

    written = []
    for zone in geometry["frame_zones_px"]:
        y0, y1 = zone["y"], zone["y"] + zone["height"]
        x0, x1 = zone["x"], zone["x"] + zone["width"]
        before = page[y0:y1, x0:x1]
        if before.size == 0:
            continue
        panels = [("scan brut", before)]
        for (name, model), residual in zip(models, residuals):
            panels.append((f"{name} -- {residual:.1f} dE76", _apply_to_image(before, model)))
        # Reduit pour etre regardable: le jugement porte sur la couleur, pas sur
        # le grain, et trois volets de 3307 px de large ne s'ouvrent pas.
        scale = 900 / before.shape[1]
        rendered = [
            _label(cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), text)
            for text, img in panels
        ]
        separator = np.full((rendered[0].shape[0], 8, 3), 255, np.uint8)
        strip = [rendered[0]]
        for panel in rendered[1:]:
            strip += [separator, panel]
        destination = out_dir / f"page{label}_{zone['name']}_comparaison.png"
        cv2.imwrite(str(destination), np.hstack(strip))
        written.append(destination)
    residual_text = ", ".join(
        f"{name.split(' (')[0]} {value:.2f}" for name, value in zip(PREVIEW_MODELS, residuals))
    print(f"  page {label}: {residual_text} dE76 -- {len(written)} zone(s)")
    return written


# ---------------------------------------------------------------------------
# Mode --truth : comparer a la frame source, qui est la seule reference
# ---------------------------------------------------------------------------

#: Facteur de sous-echantillonnage de la mesure de contenu. La frame redressee et la
#: frame source ne sont **pas** alignees au pixel -- l'homographie laisse un residu de
#: quelques pixels -- si bien qu'un dE76 pixel a pixel mesurerait surtout le
#: desalignement sur les contours. On mesure donc sur une version reduite, ou un
#: residu de quelques pixels devient sous-pixellaire, et le facteur est declare avec
#: le resultat plutot que tu.
TRUTH_MEASURE_SCALE = 8
#: Bordure ecartee, en fraction de cote: le bord de la zone porte l'encrage de la
#: decoupe et le residu d'homographie est maximal la.
TRUTH_MEASURE_BORDER = 0.04


def _page_slots(path: str, rank) -> list[str]:
    """Rendre les timecodes de frame de la page, lus **au payload QR**.

    Jamais deduits d'un ordre suppose: c'est le payload qui dit quelle frame occupe
    quel emplacement, et une correspondance devinee comparerait une frame a une
    autre en rendant un dE76 plausible.
    """
    image = scan_ingest.load_page_array(PROJ, scan_ingest.PageLocator(path, rank), dpi=DPI)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if grey.dtype == np.uint16:
        grey = (grey >> 8).astype(np.uint8)
    ok, texts, _points, _ = cv2.QRCodeDetectorAruco().detectAndDecodeMulti(grey)
    if not ok:
        return []
    for text in texts:
        if not text:
            continue
        payload = json.loads(text)
        slots = sorted(payload.get("slots", []), key=lambda s: s["slot_index"])
        return [s["frame_timecode"].replace(":", "-") for s in slots]
    return []


def _source_frame(lot: str, timecode: str) -> np.ndarray | None:
    path = PROJ / "frames" / lot / f"{lot}_{timecode}.tiff"
    if not path.exists():
        return None
    frame = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if frame is None:
        return None
    if frame.dtype == np.uint16:
        frame = (frame >> 8).astype(np.uint8)
    return frame


def _content_de76(reference: np.ndarray, candidate: np.ndarray) -> float:
    """dE76 moyen entre deux images, sur une version reduite et sans les bords."""
    height, width = reference.shape[:2]
    margin_y, margin_x = int(height * TRUTH_MEASURE_BORDER), int(width * TRUTH_MEASURE_BORDER)
    pair = []
    for image in (reference, candidate):
        cropped = image[margin_y:height - margin_y, margin_x:width - margin_x]
        small = cv2.resize(
            cropped, (cropped.shape[1] // TRUTH_MEASURE_SCALE,
                      cropped.shape[0] // TRUTH_MEASURE_SCALE),
            interpolation=cv2.INTER_AREA)
        pair.append(small[:, :, ::-1].astype(np.float64) / 255.0)  # BGR -> RGB
    return float(de76(pair[0], pair[1]).mean())


def truth_model_table(path: str, rank, layout, sets, lot: str,
                      label: int = 1, template: str = TEMPLATE) -> dict:
    """Chaque forme de correction, jugee sur le **contenu** des frames.

    C'est la mesure qui tranche, et le banc ne la faisait pas: le mode `--truth`
    n'evaluait que `C = M o A`, et le mode `--models` ne compare les formes qu'en
    validation croisee **sur les pastilles**.

    Or la lecon du 2026-08-10 est precisement que la croisee sur les pastilles ne
    suffit pas: le modele riche y gagnait d'un facteur deux et rendait une image
    visiblement fausse, parce que les pastilles sont dans le domaine d'ajustement par
    construction et que 8,3 % des pixels d'une frame n'y sont pas. Classer les formes
    par leur residu de pastilles, c'est donc les classer sur le seul critere dont on
    sait qu'il ment.

    Ici chaque forme est ajustee sur les pastilles de la page -- comme en production
    -- puis appliquee au contenu des frames, et notee contre la **frame source**, qui
    est la seule reference vraie. Le residu de pastilles est rendu a cote, pour que
    l'ecart entre les deux classements se lise au lieu d'etre suppose.
    """
    adjustment_ids, neutral_ids = sets
    src_lin, dst_lin, dst_enc, neutral_mask, _ids = read_page(
        path, rank, layout, adjustment_ids, neutral_ids, template)

    geometry = scan_detection.resolve_page_geometry(template, DPI)
    image = scan_ingest.load_page_array(PROJ, scan_ingest.PageLocator(path, rank), dpi=DPI)
    markers = scan_detection._detect_markers_document(image, DPI)["images"][0]["markers"]
    homography, _scale = scan_detection.compute_template_homography(markers, geometry, DPI)
    page = scan_crop.warp_detected_page(image, homography, geometry["page_size_px"])
    if page.dtype == np.uint16:
        page = (page >> 8).astype(np.uint8)

    timecodes = _page_slots(path, rank)
    zones = []
    for index, zone in enumerate(geometry["frame_zones_px"]):
        if index >= len(timecodes):
            continue
        source = _source_frame(lot, timecodes[index])
        if source is None:
            continue
        raw = page[zone["y"]:zone["y"] + zone["height"],
                   zone["x"]:zone["x"] + zone["width"]]
        if raw.size == 0:
            continue
        truth = cv2.resize(source, (raw.shape[1], raw.shape[0]), interpolation=cv2.INTER_AREA)
        zones.append((zone["name"], timecodes[index], raw, truth))

    if not zones:
        print(f"  page {label}: aucune zone confrontable, table de modeles impossible")
        return {}

    # Ligne de base: le scan sans aucune correction. Sans elle, une forme qui degrade
    # se lit comme la moins bonne du tableau au lieu de se lire comme nuisible.
    rows = {"scan brut (aucune correction)": {
        "patchs": float(de76(oetf(np.clip(src_lin, 0, 1)), dst_enc).mean()),
        "contenu": [_content_de76(truth, raw) for _n, _t, raw, truth in zones],
    }}

    for name, build in MODELS.items():
        model = build(src_lin, dst_lin, neutral_mask)
        rows[name] = {
            "patchs": float(de76(oetf(np.clip(model(src_lin), 0, 1)), dst_enc).mean()),
            "contenu": [_content_de76(truth, _apply_to_image(raw, model))
                        for _n, _t, raw, truth in zones],
        }

    names = [name for name, _t, _r, _v in zones]
    print(f"\n  CHAQUE FORME JUGEE SUR LE CONTENU, page {label} "
          f"({len(zones)} zones: {', '.join(names)})")
    print(f"  {'forme':<32} {'pastilles':>10} {'contenu moyen':>14} {'pire zone':>10}  par zone")
    ranked = sorted(rows.items(), key=lambda kv: float(np.mean(kv[1]["contenu"])))
    for name, data in ranked:
        content = np.array(data["contenu"])
        detail = " ".join(f"{value:5.2f}" for value in content)
        print(f"  {name:<32} {data['patchs']:>10.2f} {content.mean():>14.2f} "
              f"{content.max():>10.2f}  {detail}")
    best_patches = min(rows.items(), key=lambda kv: kv[1]["patchs"])[0]
    best_content = ranked[0][0]
    if best_patches != best_content:
        print(f"  /!\\ le classement diverge: meilleur sur pastilles = {best_patches}, "
              f"meilleur sur contenu = {best_content}")
    return rows


def write_truth_previews(path: str, rank, layout, sets, out_dir: Path, lot: str,
                         label: int = 1, template: str = TEMPLATE) -> None:
    adjustment_ids, neutral_ids = sets
    src_lin, dst_lin, dst_enc, neutral_mask, _ids = read_page(
        path, rank, layout, adjustment_ids, neutral_ids, template)
    # Deux formes cote a cote et non une seule: la forme specifiee retrouve la densite
    # de l'image mais la fait virer au chaud, et un volet unique ne permet pas de voir
    # que le defaut est une **teinte** et non un manque de correction. Le 2026-08-11,
    # la forme Lab gagne 6,05 -> 4,93 dE76 de moyenne sur les quatre frames.
    models = [(name, MODELS[name](src_lin, dst_lin, neutral_mask))
              for name in TRUTH_PREVIEW_MODELS]
    patch_residual = float(
        de76(oetf(np.clip(models[0][1](src_lin), 0, 1)), dst_enc).mean())

    geometry = scan_detection.resolve_page_geometry(template, DPI)
    image = scan_ingest.load_page_array(PROJ, scan_ingest.PageLocator(path, rank), dpi=DPI)
    markers = scan_detection._detect_markers_document(image, DPI)["images"][0]["markers"]
    homography, _scale = scan_detection.compute_template_homography(markers, geometry, DPI)
    page = scan_crop.warp_detected_page(image, homography, geometry["page_size_px"])
    if page.dtype == np.uint16:
        page = (page >> 8).astype(np.uint8)

    timecodes = _page_slots(path, rank)
    for index, zone in enumerate(geometry["frame_zones_px"]):
        if index >= len(timecodes):
            continue
        source = _source_frame(lot, timecodes[index])
        if source is None:
            print(f"  page {label} {zone['name']}: frame source absente "
                  f"({timecodes[index]}), volet de verite impossible -- ignoree")
            continue
        raw = page[zone["y"]:zone["y"] + zone["height"],
                   zone["x"]:zone["x"] + zone["width"]]
        if raw.size == 0:
            continue
        truth = cv2.resize(source, (raw.shape[1], raw.shape[0]),
                           interpolation=cv2.INTER_AREA)
        before = _content_de76(truth, raw)
        panels = [
            (f"frame source (verite) -- {timecodes[index]}", truth),
            (f"scan brut -- {before:.1f} dE76 a la source", raw),
        ]
        scores = []
        for name, model in models:
            corrected = _apply_to_image(raw, model)
            after = _content_de76(truth, corrected)
            scores.append((name, after))
            panels.append((f"{name} -- {after:.1f} dE76 a la source", corrected))
        scale = 760 / raw.shape[1]
        rendered = [
            _label(cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), text)
            for text, img in panels
        ]
        separator = np.full((rendered[0].shape[0], 8, 3), 255, np.uint8)
        strip = [rendered[0]]
        for panel in rendered[1:]:
            strip += [separator, panel]
        destination = out_dir / f"verite_page{label}_{zone['name']}.png"
        cv2.imwrite(str(destination), np.hstack(strip))
        detail = " | ".join(
            f"{name.split(' (')[0]} {value:5.2f} "
            f"({'AMELIORE' if value < before else 'DEGRADE'})"
            for name, value in scores)
        print(f"  page {label} {zone['name']}: brut {before:5.2f} -> {detail} "
              f"| pastilles {patch_residual:5.2f}")


def compare_pages(pages) -> None:
    """Une planche de patchs peut-elle calibrer tout un lot ? (question d'Egan)

    Deux mesures, et seule la seconde repond.

    **La dispersion des mesures** dit si les pages se ressemblent. Utile, mais pas
    suffisant: deux pages peuvent differer sensiblement et demander la *meme*
    correction, ou se ressembler et en demander deux differentes.

    **Le transfert de correction** repond: on ajuste `C` sur la page `i`, on
    l'applique aux pastilles de la page `j`, et on compare au `C` ajuste sur `j`
    lui-meme. Si le cout du transfert est petit devant le residu propre, alors une
    seule planche de patchs suffit au lot -- et toute la surface des pastilles est
    liberee sur les autres planches.
    """
    print("\nUNE SEULE PLANCHE DE PATCHS SUFFIT-ELLE AU LOT ?")

    # 1. Dispersion des mesures brutes d'une page a l'autre, valeur par valeur.
    by_value: dict[str, list[np.ndarray]] = {}
    for _src, _dst, dst_enc, _neutral, ids in pages:
        for value_id, encoded in zip(ids, dst_enc):
            by_value.setdefault(value_id, [])
    for src_lin, _dst, _dst_enc, _neutral, ids in pages:
        for value_id, linear in zip(ids, src_lin):
            by_value[value_id].append(linear)
    print("\n  1. DISPERSION DES MESURES entre pages (dE76 a la moyenne inter-pages)")
    worst = []
    for value_id, rows in sorted(by_value.items()):
        stack = np.array(rows)
        centre = stack.mean(axis=0)
        spread = de76(oetf(np.clip(stack, 0, 1)), oetf(np.clip(centre, 0, 1)))
        worst.append((float(spread.max()), float(spread.mean()), value_id, len(rows)))
    for maximum, mean, value_id, count in sorted(worst, reverse=True):
        print(f"     {value_id:22s} n={count:3d}  moyenne {mean:5.2f}  max {maximum:5.2f}")

    # 2. Transfert: ajuster sur une page, appliquer a une autre.
    models = [MODELS["C = M o A (specifie)"](src, dst, neutral)
              for src, dst, _enc, neutral, _ids in pages]
    count = len(pages)
    matrix = np.full((count, count), np.nan)
    for source in range(count):
        for target in range(count):
            src_lin, _dst, dst_enc, _neutral, _ids = pages[target]
            predicted = oetf(np.clip(models[source](src_lin), 0, 1))
            matrix[source, target] = float(de76(predicted, dst_enc).mean())

    print("\n  2. TRANSFERT DE CORRECTION -- ligne = page qui ajuste, "
          "colonne = page corrigee (dE76 moyen)")
    header = "        " + " ".join(f"p{j + 1:<5d}" for j in range(count))
    print(header)
    for source in range(count):
        cells = " ".join(f"{matrix[source, target]:6.2f}" for target in range(count))
        print(f"     p{source + 1}  {cells}")

    diagonal = np.array([matrix[k, k] for k in range(count)])
    off = matrix[~np.eye(count, dtype=bool)]
    print(f"\n     correction propre a chaque page : {diagonal.mean():.2f} dE76 "
          f"(de {diagonal.min():.2f} a {diagonal.max():.2f})")
    print(f"     correction d'une autre page      : {off.mean():.2f} dE76 "
          f"(de {off.min():.2f} a {off.max():.2f})")
    print(f"     COUT DU TRANSFERT               : {off.mean() - diagonal.mean():+.2f} dE76")
    # La reference n'est pas zero mais le seuil de la metrique d'acceptation:
    # un transfert qui coute moins que la marge disponible sous 8,0 est gratuit
    # en pratique, meme s'il est mesurable.
    print(f"     marge restante sous le seuil de 8,0 : {8.0 - off.max():+.2f} dE76 "
          f"au pire transfert")

    # 3. Le transfert est-il gratuit parce que les pages se ressemblent, ou parce que
    # `C = M o A` est trop pauvre pour differer d'une page a l'autre ? Un modele plus
    # riche a plus de latitude pour surajuster sa page: s'il transfere aussi bien, la
    # coherence est une propriete des pages et non une limite du modele. Sans ce
    # controle, « transfert gratuit » et « modele aveugle » sont indiscernables.
    print("\n  3. CONTROLE -- le transfert est-il gratuit pour toutes les formes ?")
    print(f"     {'modele':28s} {'propre':>8s} {'transfere':>10s} {'cout':>7s}")
    for name, build in MODELS.items():
        fitted = [build(src, dst, neutral) for src, dst, _enc, neutral, _ids in pages]
        self_cost, cross_cost = [], []
        for source in range(count):
            for target in range(count):
                src_lin, _dst, dst_enc, _neutral, _ids = pages[target]
                value = float(de76(
                    oetf(np.clip(fitted[source](src_lin), 0, 1)), dst_enc).mean())
                (self_cost if source == target else cross_cost).append(value)
        own, transferred = float(np.mean(self_cost)), float(np.mean(cross_cost))
        print(f"     {name:28s} {own:8.2f} {transferred:10.2f} {transferred - own:+7.2f}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--scan", help="Scan PDF multipage de la planche, relatif au projet")
    source.add_argument("--scan-pages", nargs="+",
                        help="Une page-fichier image par page, dans l'ordre des pages")
    parser.add_argument("--pages", type=int, default=None,
                        help="Nombre de pages du scan; requis avec --scan")
    parser.add_argument("--preset", default="patches-18-v2", help="Preset de patchs")
    parser.add_argument("--template", default=TEMPLATE,
                        help="Gabarit de la planche; a declarer pour toute planche qui "
                             f"n'est pas un {TEMPLATE}")
    parser.add_argument("--images", action="store_true", help="Ecrire les avant/apres")
    parser.add_argument("--models", action="store_true",
                        help="Comparer les formes de correction en validation croisee")
    parser.add_argument("--cross-pages", action="store_true",
                        help="Une seule planche de patchs suffit-elle au lot ?")
    parser.add_argument("--truth", metavar="LOT_ID", default=None,
                        help="Comparer a la frame source du lot: seule reference vraie")
    parser.add_argument("--truth-models", action="store_true",
                        help="Juger CHAQUE forme de correction sur le contenu des frames, "
                             "et non sur les pastilles; demande --truth")
    parser.add_argument("--out", default=None, help="Dossier de sortie des images")
    args = parser.parse_args(argv)

    if not (args.images or args.models or args.cross_pages or args.truth):
        parser.error("choisir au moins --images, --models, --cross-pages ou --truth")
    if args.truth_models and not args.truth:
        parser.error("--truth-models demande --truth: le lot est la reference vraie")

    if args.scan and args.pages is None:
        parser.error("--pages est requis avec --scan")
    # Une page-fichier porte `page_index = None`; l'ordre des chemins fait foi.
    locators = ([(args.scan, rank) for rank in range(args.pages)] if args.scan
                else [(path, None) for path in args.scan_pages])

    layout = patch_presets.resolve_patch_layout(args.template, args.preset)
    sets = _adjustment_set(args.preset)
    print(f"preset {args.preset}: {len(layout)} pastilles, "
          f"{len(sets[0])} valeurs d'ajustement dont {len(sets[1])} neutres")

    if args.models or args.cross_pages:
        pages = [read_page(path, rank, layout, *sets, template=args.template)
                 for path, rank in locators]
        if args.models:
            compare_models(pages)
        if args.cross_pages:
            compare_pages(pages)

    if args.truth:
        out_dir = Path(args.out) if args.out else Path("_bmad-output/test-artifacts/apercu-correction")
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nFRAME SOURCE / SCAN BRUT / CORRIGE -> {out_dir}")
        for index, (path, rank) in enumerate(locators):
            write_truth_previews(path, rank, layout, sets, out_dir, args.truth,
                                 label=index + 1, template=args.template)
            if args.truth_models:
                truth_model_table(path, rank, layout, sets, args.truth,
                                  label=index + 1, template=args.template)

    if args.images:
        out_dir = Path(args.out) if args.out else Path("_bmad-output/test-artifacts/apercu-correction")
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nAVANT / APRES sur les zones de frames -> {out_dir}")
        for index, (path, rank) in enumerate(locators):
            write_previews(path, rank, layout, sets, out_dir, label=index + 1,
                           template=args.template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
