"""Story 5.30 -- l'ingestion accepte un scan a CANAL ALPHA, et lit le dpi d'un TIFF.

Ces bancs viennent d'un retour de TERRAIN, pas d'une relecture : la monteuse a
scanne une page de calibration sur macOS avec l'utilitaire natif, et l'outil a
refuse le fichier sur `page_not_three_channels`. La signature mesuree sur le
fichier reel, et que les fabriques d'ici reproduisent :

    BitsPerSample     = (8, 8, 8, 8)
    SamplesPerPixel   = 4              <- l'unique difference avec l'imprimante
    ExtraSamples      = (1,)           <- alpha ASSOCIE (premultiplie)
    Software          = Apple Image Capture
    XResolution       = 600.0 (LZW, Predictor 2, profil ICC `appl`)

et **l'alpha ne porte rien** : une seule valeur distincte, 255, sur 35,8
millions de pixels.

**Ce que ces fabriques NE prouvent pas, dit plutot que tu.** Le fichier de
terrain n'est pas verse au depot (consigne d'Egan du 2026-09-09), donc l'encodage
d'ici n'est pas celui d'Apple -- Pillow ecrit `ExtraSamples = (2,)` (alpha non
associe) la ou Apple ecrit `(1,)`. Aucun chemin du produit ne lit ce tag, et
c'est justement ce que la frontiere `test_le_retrait_ne_lit_AUCUN_tag_d_alpha`
mesure : si un jour il le lisait, ces bancs cesseraient de mesurer le terrain
sans le dire.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, TiffImagePlugin

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import (  # noqa: E402
    color_calibration,
    color_pipeline,
    numeric_guards,
    scan_ingest,
    scan_output_frames,
)

MODULE_INGEST = REPO_ROOT / "src" / "mixed_media_utility" / "scan_ingest.py"

#: Un triplet ASYMETRIQUE, et c'est le point : un remplissage uniforme ne
#: montrerait ni une permutation de canaux ni un decalage d'un cran. En BGR,
#: `cv2` relit exactement `(10, 120, 240)` de ce RGB-la.
RGB_TEMOIN = (240, 120, 10)
BGR_TEMOIN = (10, 120, 240)


def _code_sans_prose(chemin: Path) -> str:
    """Le source d'un module, **commentaires et chaines retires**.

    Une frontiere negative qui `grep` le fichier entier mesure la PROSE autant
    que le code : le premier commentaire qui explique pourquoi un tag n'est pas
    lu la fait rougir. Elle deviendrait alors une frontiere qu'on desarme en
    reecrivant une phrase, c'est-a-dire une frontiere fausse.

    Les jetons `COMMENT` et `STRING` couvrent aussi les docstrings, qui sont
    des expressions-chaines.
    """
    import io
    import tokenize

    with chemin.open("rb") as flux:
        jetons = list(tokenize.tokenize(flux.readline))
    return "\n".join(
        jeton.string for jeton in jetons
        if jeton.type not in (tokenize.COMMENT, tokenize.STRING)
    )


# --- fabriques -------------------------------------------------------------


def ecrire_tiff_rgba(chemin: Path, *, alpha=255, dpi=(600, 600),
                     rgb=RGB_TEMOIN, taille=(24, 32)) -> Path:
    """Un TIFF a QUATRE canaux, avec la signature de tags du terrain.

    `alpha` accepte un scalaire (canal uniforme) ou un tableau, pour jouer le
    regime NON opaque sans changer de fabrique.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    hauteur, largeur = taille
    canaux = [np.full((hauteur, largeur), valeur, np.uint8) for valeur in rgb]
    if np.isscalar(alpha):
        canaux.append(np.full((hauteur, largeur), int(alpha), np.uint8))
    else:
        canaux.append(np.asarray(alpha, dtype=np.uint8))
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[305] = "Apple Image Capture"
    tags[272] = "Smart Tank 5100 series"
    Image.fromarray(np.dstack(canaux), mode="RGBA").save(
        chemin, tiffinfo=tags, dpi=dpi, compression="tiff_lzw")
    return chemin


def ecrire_tiff_rgb(chemin: Path, *, dpi=(600, 600), rgb=RGB_TEMOIN,
                    taille=(24, 32)) -> Path:
    """Le meme TIFF, a TROIS canaux -- le temoin de ce qui marchait deja."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    hauteur, largeur = taille
    tableau = np.dstack([np.full((hauteur, largeur), valeur, np.uint8)
                         for valeur in rgb])
    Image.fromarray(tableau, mode="RGB").save(chemin, dpi=dpi,
                                              compression="tiff_lzw")
    return chemin


def ecrire_tiff_gris(chemin: Path, *, dpi=(600, 600), taille=(24, 32)) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full(taille, 128, np.uint8), mode="L").save(
        chemin, dpi=dpi, compression="tiff_lzw")
    return chemin


def ecrire_tiff_resolution_degeneree(chemin: Path, taille=(24, 32)) -> Path:
    """Un TIFF dont la resolution vaut `0/0`, c'est-a-dire **nan**.

    Ce n'est pas une curiosite : `float(IFDRational(0, 0))` ne leve pas, il rend
    `nan`, et un `nan` traverse la comparaison de tolerance de `_dpi_warnings`
    en rendant `False` -- c'est-a-dire en ANNONCANT un accord.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[282] = TiffImagePlugin.IFDRational(0, 0)
    tags[283] = TiffImagePlugin.IFDRational(0, 0)
    tags[296] = 2
    Image.fromarray(np.zeros((*taille, 3), np.uint8)).save(chemin, tiffinfo=tags)
    return chemin


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    dossier = tmp_path / "projet"
    dossier.mkdir()
    return dossier


# --- AC1 / AC2 : l'alpha opaque se retire, au point de lecture UNIQUE -------


def test_un_alpha_opaque_ne_fait_plus_rendre_quatre_canaux(tmp_path: Path) -> None:
    """AC1. Le regime exact du fichier de terrain, lu par le point d'entree."""
    page = ecrire_tiff_rgba(tmp_path / "page.tiff")
    tableau = scan_ingest.read_image_page(page)
    assert tableau.ndim == 3
    assert tableau.shape[2] == 3, (
        "un alpha uniformement opaque ne porte aucune information : le retirer "
        f"ne perd rien, forme rendue {tableau.shape}")


def test_le_retrait_ne_permute_ni_ne_decale_les_canaux(tmp_path: Path) -> None:
    """AC1, non-vacuite. Un temoin ASYMETRIQUE, sinon le test est creux."""
    page = ecrire_tiff_rgba(tmp_path / "page.tiff")
    tableau = scan_ingest.read_image_page(page)
    assert tuple(int(v) for v in tableau[0, 0]) == BGR_TEMOIN


def test_le_tableau_rendu_est_CONTIGU(tmp_path: Path) -> None:
    """AC1 (T1). `array[:, :, :3]` est une VUE non contigue.

    `cv2` et une partie de `numpy` supposent la contiguite plus loin dans la
    chaine, et le defaut ne se voit pas ici : il se voit a l'ecriture.
    """
    page = ecrire_tiff_rgba(tmp_path / "page.tiff")
    tableau = scan_ingest.read_image_page(page)
    assert tableau.flags["C_CONTIGUOUS"]


def test_une_page_a_TROIS_canaux_ne_change_pas(tmp_path: Path) -> None:
    """AC1, symetrique. Ce qui marchait doit continuer a marcher a l'identique."""
    page = ecrire_tiff_rgb(tmp_path / "page.tiff")
    tableau = scan_ingest.read_image_page(page)
    assert tableau.shape[2] == 3
    assert tuple(int(v) for v in tableau[0, 0]) == BGR_TEMOIN


def test_le_retrait_vit_au_point_de_lecture_et_load_page_array_en_HERITE(
    projet: Path, tmp_path: Path
) -> None:
    """AC2. `load_page_array` est le contrat de jonction des stories aval.

    S'il fallait retirer l'alpha chez chaque appelant, c'est ici que ca se
    verrait -- et c'est la deuxieme redaction que le depot paie a chaque fois.
    """
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    tableau = scan_ingest.load_page_array(projet, rapport.pages[0].locator, dpi=600)
    assert tableau.shape[2] == 3


# --- AC4 : le rapport dit ce que LE FICHIER portait -------------------------


def test_le_rapport_declare_QUATRE_canaux_et_la_chaine_en_rend_TROIS(
    projet: Path, tmp_path: Path
) -> None:
    """AC4, et les deux moities dans le MEME test.

    Separer les deux assertions en deux bancs laisserait passer la redaction ou
    l'un est vrai et l'autre faux : c'est le constat ET le resultat qui doivent
    diverger, et c'est cette divergence qui est le contrat.
    """
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    page = rapport.pages[0]
    assert page.channels == 4, (
        "le rapport est un CONSTAT de ce que le fichier porte, pas un compte "
        "rendu de ce que la chaine a garde")
    assert scan_ingest.load_page_array(
        projet, page.locator, dpi=600).shape[2] == 3


# --- AC3 : un alpha NON opaque se retire en s'annoncant ---------------------


def test_un_alpha_NON_opaque_ne_fait_pas_refuser(tmp_path: Path) -> None:
    """AC3, `EPIC11-ARB-89` : jamais un blocage sec."""
    alpha = np.full((24, 32), 255, np.uint8)
    alpha[0, 0] = 7
    page = ecrire_tiff_rgba(tmp_path / "page.tiff", alpha=alpha)
    tableau = scan_ingest.read_image_page(page)
    assert tableau.shape[2] == 3


def test_un_alpha_NON_opaque_S_ANNONCE_au_rapport(
    projet: Path, tmp_path: Path
) -> None:
    """AC3. Le retrait est licite ; le taire ne l'est pas."""
    alpha = np.full((24, 32), 255, np.uint8)
    alpha[0, 0] = 7
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff", alpha=alpha)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE in rapport.pages[0].warnings


def test_un_alpha_OPAQUE_ne_declenche_AUCUN_avertissement(
    projet: Path, tmp_path: Path
) -> None:
    """AC3, non-vacuite. Un avertissement pose partout n'avertit de rien.

    C'est la moitie qui manque le plus souvent : sans elle, un code emis
    inconditionnellement passerait le banc precedent.
    """
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE not in rapport.pages[0].warnings


def test_le_code_d_avertissement_est_DANS_le_vocabulaire_ferme() -> None:
    """AC3. `validate_warning_code` refuse tout code hors liste a la
    construction : un code neuf qui n'y entrerait pas ferait lever
    l'ingestion au lieu d'avertir."""
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE in scan_ingest.SCAN_INGEST_WARNING_CODES
    assert scan_ingest.validate_warning_code(
        scan_ingest.ALPHA_NON_OPAQUE_RETIRE) == scan_ingest.ALPHA_NON_OPAQUE_RETIRE


def test_le_retrait_ne_lit_AUCUN_tag_d_alpha() -> None:
    """AC3, frontiere NEGATIVE et garde de ces bancs eux-memes.

    `ExtraSamples` distingue l'alpha ASSOCIE (`1`, ce qu'Apple ecrit) du non
    associe (`2`, ce que Pillow ecrit ici). Sur un alpha opaque les deux sont
    l'identite. Si le produit se mettait a lire ce tag, les fabriques de ce
    fichier cesseraient de mesurer le terrain **sans le dire**.
    """
    code = _code_sans_prose(MODULE_INGEST)
    # **`338` est dans la liste, et son absence etait un TROU MESURE** (finding
    # `C3-1` de la couche 3). Cette frontiere n'interdisait que les NOMS ; or la
    # voie canonique de Pillow adresse un tag par son NUMERO -- `tag_v2[338]`.
    # Sous ce mutant, les 26 bancs restaient verts ET le regime exact du terrain
    # (`ExtraSamples = (1,)`) rendait a nouveau quatre canaux : le
    # `page_not_three_channels` de la monteuse, rouvert et invisible.
    #
    # Ce que ca coute de ne pas pouvoir le mesurer autrement : **Pillow refuse
    # d'ecrire `ExtraSamples = 1`**, donc aucune fabrique de ce fichier ne peut
    # jouer le regime du terrain -- il a fallu une edition binaire de l'IFD pour
    # le demontrer. C'est precisement pourquoi la frontiere porte sur le code.
    for interdit in ("ExtraSamples", "extra_samples", "338"):
        assert interdit not in code, (
            f"`{interdit}` dans le CODE de scan_ingest : le retrait d'alpha "
            "deciderait alors d'apres un tag que les fabriques de ce banc "
            "n'ecrivent pas comme le terrain")


# --- AC5 : les deux gardes qui refusaient RESTENT ---------------------------


@pytest.mark.parametrize("page, attendu", [
    (np.zeros((8, 8, 3), np.uint8), True),
    (np.zeros((8, 8, 4), np.uint8), False),
    (np.zeros((8, 8, 1), np.uint8), False),
    (np.zeros((8, 8), np.uint8), False),
])
def test_la_garde_de_calibration_a_trois_canaux_reste(page, attendu) -> None:
    """AC5, frontiere NEGATIVE, mesuree par APPEL et non par egalite de constante.

    **La premiere redaction de ce banc etait CREUSE** (finding `C3-2` de la
    couche 3) : elle comparait `FAILURE_NOT_THREE_CHANNELS` a son propre
    litteral, ce qu'aucun mutant de la garde ne pouvait faire rougir. Trois
    mutants -- garde contournee, assouplie a quatre canaux, ouverte au gris --
    survivaient aux 26 bancs. La propriete tenait quand meme, par un banc
    PREEXISTANT que la fiche ne nommait pas (`test_scan_calibration_application.py`) :
    couverture reelle, temoin faux.

    La garde n'est pas la cause du defaut de la monteuse. Elle est ce qui l'a
    rendu VISIBLE au lieu de le laisser produire des triplets melanges --
    `sample_patches` fait `window.reshape(-1, 3)`, qui REUSSIT des que l'aire du
    carre echantillonne multipliee par 4 est divisible par 3, et rend alors des
    gris parfaitement plausibles a la place de couleurs saturees.
    """
    assert color_calibration.FAILURE_NOT_THREE_CHANNELS == "page_not_three_channels"
    assert color_calibration.page_has_three_channels(page) is attendu


def test_la_garde_d_ecriture_de_frames_refuse_toujours_quatre_canaux() -> None:
    """AC5, frontiere NEGATIVE, mesuree par APPEL et non par grep."""
    frame = np.zeros((8, 8, 4), np.uint8)
    with pytest.raises(scan_output_frames.ScanOutputError) as refus:
        scan_output_frames._corrected_frame(
            frame, object(), page_index=0, slot_index=0)
    assert "trois canaux" in str(refus.value)


def test_validate_bgr_input_accepte_TOUJOURS_quatre_canaux() -> None:
    """AC5. `validate_bgr_input` valide, il ne normalise pas.

    Son acceptation des quatre canaux est deliberee et d'autres chemins en
    dependent : la normalisation est ailleurs, et l'y deplacer serait la
    seconde redaction que ce depot paie a chaque fois.
    """
    quatre = np.zeros((4, 4, 4), np.uint8)
    assert color_pipeline.validate_bgr_input(quatre).shape[2] == 4


# --- AC6 : le gris reste refuse, et la difference est ECRITE ----------------


def test_une_page_en_NIVEAUX_DE_GRIS_reste_a_un_canal(tmp_path: Path) -> None:
    """AC6. Retirer un alpha opaque ne perd rien ; convertir du gris en BGR
    fabriquerait une couleur que le scan ne porte pas."""
    page = ecrire_tiff_gris(tmp_path / "page.tiff")
    tableau = scan_ingest.read_image_page(page)
    assert tableau.ndim == 2 or tableau.shape[2] == 1


def test_aucune_conversion_de_gris_vers_BGR_dans_l_ingestion() -> None:
    """AC6, frontiere NEGATIVE. Aucun test positif ne verrait revenir un
    `GRAY2BGR` ajoute par reflexe."""
    code = _code_sans_prose(MODULE_INGEST)
    for interdit in ("GRAY2BGR", "GRAY2RGB", "COLOR_GRAY"):
        assert interdit not in code


# --- AC7 / AC8 / AC9 : le dpi d'un TIFF -------------------------------------


def test_le_dpi_d_un_TIFF_est_enfin_LU(tmp_path: Path) -> None:
    """AC7. Il rendait `None` sur TOUT TIFF -- pas seulement ceux d'Apple."""
    page = ecrire_tiff_rgba(tmp_path / "page.tiff", dpi=(600, 600))
    assert scan_ingest._measure_file_dpi(page) == pytest.approx(600.0)


def test_le_dpi_d_un_TIFF_ecrit_par_PILLOW_est_lu_aussi(tmp_path: Path) -> None:
    """AC7, contre-mesure. La cause n'est pas Apple, c'est le TYPE que Pillow
    rend pour toute resolution TIFF (`IFDRational`)."""
    page = ecrire_tiff_rgb(tmp_path / "page.tiff", dpi=(300, 300))
    assert scan_ingest._measure_file_dpi(page) == pytest.approx(300.0)


def test_is_strict_number_ne_change_PAS(tmp_path: Path) -> None:
    """AC8, frontiere NEGATIVE.

    D'autres appelants l'emploient sur des cadences et des millimetres, ou son
    refus des types exotiques est voulu. Elargir la garde partagee pour
    reparer UN appelant est le remede qui casse les autres en silence.
    """
    assert not numeric_guards.is_strict_number(TiffImagePlugin.IFDRational(600, 1))
    assert numeric_guards.is_strict_number(600)
    assert numeric_guards.is_strict_number(600.0)
    assert not numeric_guards.is_strict_number(True)


def test_une_resolution_DEGENEREE_rend_None_et_non_un_nan(tmp_path: Path) -> None:
    """AC7 (T3). `float(IFDRational(0, 0))` vaut `nan`, et il ne leve pas.

    Un `nan` rendu ici traverserait `_dpi_warnings` sans declencher
    `DPI_DECLARED_DIFFERS_FROM_FILE` -- la comparaison `abs(nan - d) > d * t`
    rend `False`. Un dpi illisible passerait donc pour un dpi CONFORME.
    """
    page = ecrire_tiff_resolution_degeneree(tmp_path / "page.tiff")
    assert scan_ingest._measure_file_dpi(page) is None


def test_DPI_NOT_MEASURABLE_ne_se_leve_plus_sur_un_TIFF_qui_declare(
    projet: Path, tmp_path: Path
) -> None:
    """AC9. C'est le message que la monteuse a vu sur un fichier a 600 ppp."""
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff", dpi=(600, 600))
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert "DPI_NOT_MEASURABLE" not in rapport.warnings
    assert rapport.measured_dpi == pytest.approx(600.0)


def test_DPI_DECLARED_DIFFERS_FROM_FILE_devient_ATTEIGNABLE_sur_un_TIFF(
    projet: Path, tmp_path: Path
) -> None:
    """AC9, et c'est la seule AC de la story qui rend un avertissement PLUS
    frequent. C'est voulu : l'AC 7 de la 5.1 -- posee contre le scanner en
    auto-fit, risque R8 -- commence enfin a jouer sur le format recommande."""
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff", dpi=(600, 600))
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=300)
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in rapport.warnings


def test_une_resolution_degeneree_rend_TOUJOURS_DPI_NOT_MEASURABLE(
    projet: Path, tmp_path: Path
) -> None:
    """AC9, symetrique du precedent : le refus qui reste juste ne bouge pas."""
    ecrire_tiff_resolution_degeneree(tmp_path / "scan" / "page.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert "DPI_NOT_MEASURABLE" in rapport.warnings


# --- AC10 : la regle des fabriques ------------------------------------------


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_la_page_a_alpha_est_lue_ou_qu_elle_soit_dans_le_dossier(
    projet: Path, tmp_path: Path, position: str
) -> None:
    """AC10. La cible au MILIEU demasque un `find` fautif ; elle ne demasque
    pas un balayage tronque, qui est un autre mode de panne (`CLAUDE.md`,
    2026-09-03). Les trois positions, donc, et des pages DISTINGUABLES."""
    dossier = tmp_path / "scan"
    rangs = {"tete": 0, "milieu": 1, "queue": 2}
    for index, nom in enumerate(("page_01.tiff", "page_02.tiff", "page_03.tiff")):
        # Des valeurs DIFFERENTES : un remplissage uniforme ne montrerait pas
        # une permutation de pages.
        rgb = (240 - 30 * index, 120, 10 + 5 * index)
        if index == rangs[position]:
            ecrire_tiff_rgba(dossier / nom, rgb=rgb)
        else:
            ecrire_tiff_rgb(dossier / nom, rgb=rgb)

    rapport = scan_ingest.ingest_scan_lot(projet, dossier, dpi=600)
    assert len(rapport.pages) == 3
    cible = rapport.pages[rangs[position]]
    assert cible.channels == 4
    tableau = scan_ingest.load_page_array(projet, cible.locator, dpi=600)
    assert tableau.shape[2] == 3
    rgb_attendu = (240 - 30 * rangs[position], 120, 10 + 5 * rangs[position])
    assert tuple(int(v) for v in tableau[0, 0]) == tuple(reversed(rgb_attendu)), (
        "la page relue n'est pas celle que le rang designe")


# --- findings de la revue en trois couches du 2026-09-09 --------------------


def ecrire_tiff_rgba_16bits(chemin: Path, *, alpha=65535, taille=(24, 32),
                            bgr=(2600, 30000, 61000)) -> Path:
    """Un TIFF RGBA **16 bits**, ecrit par `cv2` -- Pillow ne sait pas.

    Mesure : `Image.fromarray(<uint16 a 4 canaux>)` leve
    `TypeError: Cannot handle this data type: (1, 1, 4), <u2`. C'est la raison
    pour laquelle aucune des cinq fabriques d'origine ne jouait le 16 bits, et
    c'est ce qui a laisse passer le finding.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    hauteur, largeur = taille
    canaux = [np.full((hauteur, largeur), v, np.uint16) for v in bgr]
    if np.isscalar(alpha):
        canaux.append(np.full((hauteur, largeur), int(alpha), np.uint16))
    else:
        canaux.append(np.asarray(alpha, dtype=np.uint16))
    assert cv2.imwrite(str(chemin), np.dstack(canaux))
    return chemin


def test_un_alpha_16_bits_PLEINEMENT_OPAQUE_ne_declenche_aucun_avertissement(
    projet: Path, tmp_path: Path
) -> None:
    """AC3, regime 16 bits (findings `C2` de la couche 1 et `C2-1` de la
    couche 2, trouves INDEPENDAMMENT).

    La borne d'opacite est `np.iinfo(alpha.dtype).max` : c'est la seule
    decision de `_sans_canal_alpha`, et aucune fabrique ne la jouait ailleurs
    qu'en 8 bits. Sous le mutant qui la fige a `255`, chaque page 16 bits RGBA
    pleinement opaque emet un faux `ALPHA_CHANNEL_DROPPED` -- sur la profondeur
    autour de laquelle TOUTE la chaine est batie.

    C'est la regle du 2026-09-06 -- « une garde qui ne fait varier AUCUN de ses
    drapeaux ne mesure qu'un seul chemin » -- appliquee au **dtype** plutot
    qu'a `ascii_seul`.
    """
    ecrire_tiff_rgba_16bits(tmp_path / "scan" / "page.tiff")
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    page = rapport.pages[0]
    assert page.source_bit_depth == 16
    assert page.channels == 4
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE not in page.warnings
    tableau = scan_ingest.load_page_array(projet, page.locator, dpi=600)
    assert tableau.shape[2] == 3 and tableau.dtype == np.uint16


def test_un_alpha_16_bits_CREVE_s_annonce(projet: Path, tmp_path: Path) -> None:
    """AC3, symetrique du precedent en 16 bits : sans lui, le banc ci-dessus
    passerait avec une garde qui declare tout opaque."""
    alpha = np.full((24, 32), 65535, np.uint16)
    alpha[12, 16] = 7
    ecrire_tiff_rgba_16bits(tmp_path / "scan" / "page.tiff", alpha=alpha)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE in rapport.pages[0].warnings


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_le_pixel_d_alpha_CREVE_est_vu_a_CHAQUE_BORD(
    projet: Path, tmp_path: Path, position: str
) -> None:
    """AC3 et AC10 (finding `C2-2` de la couche 2).

    **Les pixels de l'alpha sont une collection**, et `.all()` les balaie : la
    regle des fabriques s'y applique comme aux fichiers d'un dossier. Le banc
    d'origine crevait toujours le pixel `(0, 0)`, si bien que `alpha.flat[0]`
    et `alpha[:-1]` -- deux balayages tronques, l'un en tete l'autre en queue --
    survivaient tous les deux.
    """
    hauteur, largeur = 24, 32
    alpha = np.full((hauteur, largeur), 255, np.uint8)
    alpha[{"tete": (0, 0), "milieu": (12, 16),
           "queue": (hauteur - 1, largeur - 1)}[position]] = 7
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff", alpha=alpha)
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert scan_ingest.ALPHA_NON_OPAQUE_RETIRE in rapport.pages[0].warnings


@pytest.mark.parametrize("declare", [(600, 150), (150, 600)])
def test_les_DEUX_AXES_de_la_resolution_sont_lus_et_le_PLUS_BAS_gagne(
    tmp_path: Path, declare
) -> None:
    """AC7 (findings `C1` de la couche 1 et `C2-4` de la couche 2).

    Regime mesure avant correctif : un TIFF declarant `(600, 150)` rendait
    `600.0` et AUCUN avertissement, sur une page dont un axe est au quart de la
    resolution annoncee. Or l'auto-fit -- le risque R8 contre lequel l'AC 7 de
    la 5.1 est posee -- est precisement ce qui produit deux resolutions
    differentes sur les deux axes.

    **L'asymetrie se joue dans les DEUX SENS, et sa premiere redaction n'en
    jouait qu'un.** Avec `(600, 150)` seul, lire le PLUS BAS et lire l'axe
    VERTICAL rendent tous deux `150` : le mutant « axe vertical seul »
    survivait. C'est la regle des fabriques -- deux elements DISTINGUABLES,
    la cible ailleurs qu'en premiere position -- appliquee aux deux axes d'une
    resolution plutot qu'aux elements d'une collection.
    """
    page = ecrire_tiff_rgb(tmp_path / "page.tiff", dpi=declare)
    assert Image.open(page).info["dpi"] == tuple(
        float(v) for v in declare), "fabrique invalide"
    assert scan_ingest._measure_file_dpi(page) == pytest.approx(150.0)


def test_une_resolution_ANISOTROPE_leve_l_avertissement_de_l_AC7(
    projet: Path, tmp_path: Path
) -> None:
    """AC7 et AC9, mesurees par EFFET et non sur la fonction seule."""
    ecrire_tiff_rgb(tmp_path / "scan" / "page.tiff", dpi=(600, 150))
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" in rapport.warnings


def test_une_resolution_CARREE_ne_leve_toujours_rien(
    projet: Path, tmp_path: Path
) -> None:
    """AC7, non-vacuite du precedent : une mesure qui crie sur tout ne mesure
    rien."""
    ecrire_tiff_rgb(tmp_path / "scan" / "page.tiff", dpi=(600, 600))
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert "DPI_DECLARED_DIFFERS_FROM_FILE" not in rapport.warnings


def ecrire_tiff_resolution_infinie(chemin: Path) -> Path:
    """Un TIFF dont `XResolution` est de type DOUBLE et vaut l'infini."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[282] = float("inf")
    tags[283] = float("inf")
    tags[296] = 2
    tags.tagtype[282] = 12
    tags.tagtype[283] = 12
    Image.fromarray(np.zeros((24, 32, 3), np.uint8)).save(chemin, tiffinfo=tags)
    return chemin


def test_une_resolution_INFINIE_est_refusee_et_le_LOT_SURVIT(
    projet: Path, tmp_path: Path
) -> None:
    """AC7 (finding `C2-3` de la couche 2, qui a **renverse** le `T2` de la
    couche 1).

    La couche 1 a classe la clause `mesure == float("inf")` en garde
    inatteignable, au motif qu'un denominateur nul rend `nan`. La couche 2 a
    mesure le contraire : une `XResolution` de type TIFF `DOUBLE` (12) porte
    l'infini, et Pillow le relit tel quel -- `info["dpi"]` rend `(inf, inf)` en
    flottants ordinaires. Verifie ici de troisieme main.

    Et la clause est **porteuse** : sans elle, `report_json` leve
    `Out of range float values are not JSON compliant`, et **le lot entier est
    perdu a l'ecriture du rapport**. Une garde retiree pour inatteignabilite
    aurait coute un lot.
    """
    page = ecrire_tiff_resolution_infinie(tmp_path / "scan" / "page.tiff")
    lu = Image.open(page).info.get("dpi")
    assert lu is not None and math.isinf(float(lu[0])), "fabrique invalide"
    assert scan_ingest._measure_file_dpi(page) is None
    rapport = scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
    assert "DPI_NOT_MEASURABLE" in rapport.warnings
    # Le lot s'ecrit : c'est la moitie porteuse de la garde.
    json.loads(scan_ingest.report_json(rapport))


@pytest.mark.parametrize("valeur, attendu", [
    (600, 600.0),
    (600.5, 600.5),
    (TiffImagePlugin.IFDRational(600, 1), 600.0),
    (TiffImagePlugin.IFDRational(0, 0), None),   # nan
    (float("inf"), None),
    (float("nan"), None),
    (0, None),
    (-600, None),
    (True, None),                                 # un booleen n'est pas un dpi
    ("600", None),
    (None, None),
])
def test_la_conversion_de_resolution_refuse_ce_qu_elle_doit(valeur, attendu) -> None:
    """AC7 et AC8. Les gardes que les couches 1 et 3 ont crues inatteignables
    sont mesurees ICI, directement, plutot que retirees ou laissees muettes."""
    rendu = scan_ingest._resolution_lisible(valeur)
    if attendu is None:
        assert rendu is None
    else:
        assert rendu == pytest.approx(attendu)


def test_un_code_hors_VOCABULAIRE_ne_peut_pas_atteindre_le_rapport(
    projet: Path, tmp_path: Path, monkeypatch
) -> None:
    """Findings `T1` de la couche 1 et `C2-5` de la couche 2, trouves deux fois.

    La branche image etait la SEULE des quatre constructions d'`IngestedPage` a
    ne pas passer par `validate_warning_code`. Mesure par greffon : un code hors
    du vocabulaire ferme atterrissait dans `ingest.json` **sans une levee** --
    ce que le vocabulaire existe precisement pour empecher, et ce que le
    docstring du banc affirmait deja tenu.
    """
    vrai = scan_ingest.lire_une_page_image

    def _code_invente(chemin, page_index=None):
        lu = vrai(chemin, page_index)
        return scan_ingest.PageImageLue(lu.tableau, lu.canaux_du_fichier,
                                        ("CODE_QUI_N_EXISTE_PAS",))

    monkeypatch.setattr(scan_ingest, "lire_une_page_image", _code_invente)
    ecrire_tiff_rgba(tmp_path / "scan" / "page.tiff")
    with pytest.raises(ValueError):
        scan_ingest.ingest_scan_lot(projet, tmp_path / "scan", dpi=600)
