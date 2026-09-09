"""Story 5.16, moitie couleur: page de calibration dediee et seconde forme.

Ce fichier couvre les taches 1, 4, 5, 6, 7 et 8 de la story -- la seconde forme de
correction et ses gardes de cardinalite, la source d'ajustement **externe** a la page
et son filtre de saturation, la completude des chaines de sentinelles, la provenance de
la correction, le cout du transport, et la garde de divergence d'`EPIC5-ARB-57`.

Ce qu'il **ne** couvre pas, et pourquoi: les taches 2 et 3 (preset temoin,
`patch_presets`; type de page et payload, `page_templates` / `pdf_composition` / `cli`)
sont hors du perimetre de ce lot. Les AC qui en dependent sont donc verifiees au niveau
ou elles sont observables **sans** preset temoin -- la table de valeurs, les chaines de
sentinelles, les fonctions d'ajustement -- et jamais simulees par une fabrique qui
prendrait la place du producteur reel.

Trois conventions de ce fichier, chacune tiree d'une regle du depot:

* **la fabrique de page est importee, pas recopiee.** `_synthetic_rectified_page` de
  `test_color_calibration` porte trois proprietes durement acquises (couronne de
  contraste sur le retrait, repliques a offsets opposes, positions et valeurs des vrais
  producteurs) et une seconde copie divergerait;
* **toute collection de ce fichier porte au moins deux elements distinguables**, et au
  moins un test vise un element qui n'est **pas** le premier. Le depot s'est fait
  mordre quatre fois par une fabrique mono-element ou uniforme;
* **aucun nombre de la story n'est recopie sans etre derive ou mesure ici.** Les
  cardinaux du treillis se derivent de ses niveaux, le seuil de divergence se lit au
  registre, et les residus se mesurent.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import math
import pathlib
import re
from types import MappingProxyType

import numpy as np
import pytest

from mixed_media_utility import color_calibration as cc
from mixed_media_utility import color_metrics, color_pipeline, patch_values
from mixed_media_utility.color_metrics import delta_e76_srgb_d65 as de76

# La fabrique de page reelle, importee et non recopiee (voir le docstring de module).
from test_color_calibration import _synthetic_rectified_page

TEMPLATE = "tpl-a4-portrait-2f-v1"
PRESET = "patches-18-v2"

#: Diaphonie inter-canaux du scanner, reprise du banc de production: c'est elle qui
#: rend la distorsion **non diagonale**, donc capable de deplacer une teinte. Une
#: distorsion diagonale rendrait les deux formes de correction indistinguables.
_CROSSTALK = np.array([[0.95, 0.03, 0.02],
                       [0.02, 0.96, 0.02],
                       [0.03, 0.02, 0.95]])


def _press(gain: float, tint, *, chroma_limit: float | None = None):
    """Fabriquer un couple imprimante+scanner de synthese, en sRGB encode BGR.

    `chroma_limit` modelise la **compression de gamut** de la conversion CMJN: au-dela
    d'une amplitude de chroma, l'imprimante ne distingue plus et ecrase. C'est le
    mecanisme exact qui rend le filtre de saturation utile -- sans lui, un treillis
    entier serait un jeu d'ajustement plus riche et non un jeu contradictoire.
    """

    def apply(encoded_bgr):
        linear = np.asarray(cc.eotf(encoded_bgr)) @ _CROSSTALK.T
        linear = linear * gain + np.asarray(tint, dtype=np.float64)
        if chroma_limit is not None:
            grey = linear.mean(axis=-1, keepdims=True)
            chroma = linear - grey
            amplitude = np.abs(chroma).max(axis=-1, keepdims=True)
            scale = np.where(amplitude > chroma_limit,
                             chroma_limit / np.maximum(amplitude, 1e-12), 1.0)
            linear = grey + chroma * scale
        return cc.oetf(np.clip(linear, 0.0, 1.0))

    return apply


#: Quatre feuilles d'un **meme tirage**: meme gain nominal et meme teinte nominale, a
#: une variation de tirage pres. Elles sont **distinguables** -- aucune paire n'est
#: identique -- ce qui est la condition pour que le transport entre elles coute quelque
#: chose de non nul et donc soit mesurable.
_SAME_RUN_SHEETS = (
    ("feuille-a", 0.930, (0.0250, 0.0240, 0.0260)),
    ("feuille-b", 0.928, (0.0252, 0.0238, 0.0261)),
    ("feuille-c", 0.932, (0.0248, 0.0243, 0.0258)),
    ("feuille-d", 0.929, (0.0251, 0.0241, 0.0259)),
)


def _lattice_measurement(press, *, offset_codes: float = 1.0, interleave: bool = False):
    """Mesurer le treillis entier, **dans les deux ordres inverses**, une page.

    Les deux ordres sont ceux de la cible v3: la meme valeur est lue a deux endroits
    eloignes de la page, ce qui est ce que la repetition existe pour produire. Les deux
    repliques recoivent des offsets **opposes**, donc leur moyenne est exactement la
    valeur mesuree nominale (l'agregation H4 est verifiable) et le bruit par paires
    n'est pas nul.

    Regle des fabriques, appliquee deux fois: la collection porte 250 elements
    distinguables, et l'ordre inverse garantit qu'une valeur donnee n'occupe **pas** le
    meme rang dans les deux moities -- un appariement positionnel faux entre
    identifiants et mesures ne peut donc pas passer.

    ``interleave`` **entrelace** les deux repliques au lieu de les poser en deux blocs, et
    c'est la variante multi-elements que la regle des fabriques exige d'ecrire dans la meme
    story que le defaut qu'elle demasque. Motif mesure (mutant `R05`): en deux blocs, les 65
    premieres pastilles **retenues** sont exactement les 65 valeurs distinctes dans l'ordre
    trie, donc une troncature `retenues[:65]` **coincide** avec le jeu agrege et un
    appariement `valeur agregee -> reference` rompu reste invisible. Entrelacees, les 65
    premieres retenues portent des doublons et s'arretent au milieu du treillis: la
    troncature cesse de coincider et la permutation se voit.

    L'entrelacement ne change ni le cardinal, ni l'agregation, ni le bruit: chaque valeur
    garde ses deux repliques a offsets **opposes**, donc leur moyenne reste la mesure
    nominale exacte. Seul l'**ordre de lecture** change, ce qui est precisement la variable
    dont l'appariement ne doit pas dependre.
    """
    lattice = patch_values.calibration_lattice_values()
    forward = tuple(lattice)
    backward = tuple(reversed(lattice))
    if interleave:
        ordered = tuple(value for paire in zip(forward, backward) for value in paire)
        signs = np.array([1.0 if rang % 2 == 0 else -1.0
                          for rang in range(len(ordered))], dtype=np.float64)
    else:
        ordered = forward + backward
        signs = np.concatenate([np.full(len(forward), 1.0), np.full(len(backward), -1.0)])
    ids = tuple(value.value_id for value in ordered)
    reference = np.asarray(
        [np.asarray(value.rgb[::-1], dtype=np.float64) / 255.0
         for value in ordered], dtype=np.float64)
    measured = press(reference) + signs[:, None] * offset_codes / 255.0
    return np.clip(measured, 0.0, 1.0), ids


def _witness_measurement(press, table_version: str = "patch-values-3",
                         *, offset_codes: float = 1.0, drop: str | None = None):
    """Mesurer le jeu **temoin** d'une planche d'images: toutes les valeurs, x2.

    Rend (mesures BGR, identifiants). `drop` retire une valeur de la mesure -- c'est le
    temoin negatif de l'AC 9: sans lui, un test qui n'observe jamais
    `REASON_VALUES_ABSENT` ne prouve pas qu'il saurait le voir.
    """
    table = patch_values.get_patch_values_table(table_version)
    values = [value for value in table.values if value.value_id != drop]
    reference = np.asarray(
        [np.asarray(value.rgb[::-1], dtype=np.float64) / 255.0 for value in values],
        dtype=np.float64)
    first = np.clip(press(reference) + offset_codes / 255.0, 0.0, 1.0)
    second = np.clip(press(reference) - offset_codes / 255.0, 0.0, 1.0)
    # Les deux repliques sont **entrelacees** et non concatenees: une agregation qui
    # grouperait par rang plutot que par identifiant s'en tirerait sur des blocs.
    measured = np.empty((2 * len(values), 3), dtype=np.float64)
    measured[0::2] = first
    measured[1::2] = second
    ids = tuple(value.value_id for value in values for _ in range(2))
    return measured, ids


def _adjustment_arrays(table_version: str, press):
    """(mesures, references, masque neutre) du jeu d'**ajustement** d'une table."""
    table = patch_values.get_patch_values_table(table_version)
    values = table.adjustment_values()
    reference = np.asarray(
        [np.asarray(value.rgb[::-1], dtype=np.float64) / 255.0 for value in values],
        dtype=np.float64)
    neutral = np.asarray(
        [value.role == patch_values.ROLE_NEUTRAL for value in values], dtype=bool)
    return press(reference), reference, neutral


# ---------------------------------------------------------------------------
# AC 1 : la seconde forme est ajoutee, la premiere est intacte
# ---------------------------------------------------------------------------

def test_les_trois_formes_sont_enregistrees_et_le_defaut_est_la_forme_active():
    """AC 1 de 5.16 (« a cote de », jamais « a la place de ») **et AC 1 de 5.21**.

    Le defaut compte autant que la presence: une story qui ajoute une forme **et**
    change ce qui se passe quand personne ne choisit a change la correction de tout le
    depot sans le dire.

    **Le registre porte trois formes depuis la story 5.20**, et c'est la meme regle qui
    s'applique une seconde fois: la troisieme est ajoutee et les deux premieres restent
    les memes objets. L'assertion enumere donc les trois plutot que de compter -- un
    cardinal laisserait passer un remplacement.

    **Ce que la story 5.21 change, et c'est la seule chose qu'elle change ici**: le
    defaut de `calibrate_page` n'est plus la forme affine mais
    `ACTIVE_CORRECTION_FORM_ID`. La regle de 5.16 n'est pas abandonnee, elle est
    honoree autrement: le changement de defaut est **dit**, tranche sur mesure (`H9`) et
    epingle ici. Ce que 5.16 protegeait -- qu'une forme ne soit jamais remplacee par une
    autre sous le meme identifiant -- reste verifie ligne par ligne ci-dessous, y compris
    l'identite de la classe de profil affine, que la bascule ne touche pas.
    """
    assert set(cc.CORRECTION_FORMS) == {cc.CORRECTION_FORM_ID, cc.CORRECTION_FORM_LAB_ID,
                                        cc.CORRECTION_FORM_TONE_CHROMA_ID}
    assert cc.CORRECTION_FORM_ID != cc.CORRECTION_FORM_LAB_ID
    assert cc.CORRECTION_FORM_ID == "color-correction-affine-matrix-1"
    assert cc.CORRECTION_FORM_LAB_ID == "color-correction-lab-lightness-chroma-1"
    assert cc.CORRECTION_FORM_TONE_CHROMA_ID == "color-correction-tone-curve-chroma-1"
    # La forme en vigueur reste **le meme objet** que la fonction historique: le
    # registre resout, il ne reimplemente pas.
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_ID] is cc.fit_correction
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_LAB_ID] is cc.fit_correction_lab
    assert cc.CORRECTION_FORMS[cc.CORRECTION_FORM_TONE_CHROMA_ID] is \
        cc.fit_correction_tone_chroma
    # **La constante de forme active est distincte de l'identifiant de la forme affine**
    # (AC 1 de 5.21): deux noms, deux roles, et c'est ce qui permet a l'un de bouger sans
    # l'autre. L'egalite est verifiee **contre la valeur litterale** et pas seulement
    # contre `CORRECTION_FORM_TONE_CHROMA_ID`: un renommage de la troisieme forme ne doit
    # pas emporter silencieusement le choix de production.
    assert cc.ACTIVE_CORRECTION_FORM_ID == "color-correction-tone-curve-chroma-1"
    assert cc.ACTIVE_CORRECTION_FORM_ID == cc.CORRECTION_FORM_TONE_CHROMA_ID
    assert cc.ACTIVE_CORRECTION_FORM_ID != cc.CORRECTION_FORM_ID
    assert cc.ACTIVE_CORRECTION_FORM_ID in cc.CORRECTION_FORMS
    # Le defaut de `calibrate_page` **a bascule** (AC 2 de 5.21), celui de la dataclasse
    # de profil affine **non**: `CorrectionProfile.correction_id` est l'identite de cette
    # classe, pas une decision de forme active. Les deux assertions se lisent ensemble --
    # c'est leur ecart qui porte le sens de la story.
    signature = inspect.signature(cc.calibrate_page)
    assert signature.parameters["correction_form_id"].default == \
        cc.ACTIVE_CORRECTION_FORM_ID
    assert cc.CorrectionProfile.correction_id == cc.CORRECTION_FORM_ID


def test_la_forme_affine_nommee_rend_des_resultats_inchanges_au_bit_pres():
    """AC 1 de 5.16, **reancre sur la forme nommee** par la story 5.21.

    Compare **octet a octet** (`tobytes`) le profil obtenu en demandant explicitement la
    forme affine et celui de la fonction historique appelee a la main, et epingle les
    agregats de la metrique a l'egalite exacte -- pas a `approx`. Une egalite approchee
    laisserait passer une correction deplacee d'un 1e-12, ce qui est exactement ce qu'un
    changement d'ordre d'operations produit.

    **Ce que la story 5.21 deplace, et pourquoi ce n'est pas un relachement**: le verrou
    portait sur « sans rien demander == en demandant la forme affine », c'est-a-dire sur
    deux choses a la fois -- que la forme affine n'a pas bouge, et que c'est elle qu'on
    obtient par defaut. Le second membre est precisement ce que cette story change, sur
    mesure et par decision produit. Le premier, lui, est intact et reste verifie ici a
    l'octet. La contrepartie du second est epinglee par le test suivant, qui **exige**
    que le defaut ne soit plus l'affine: sans lui, la bascule pourrait etre annulee sans
    qu'aucun test ne rougisse.
    """
    page = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET,
        distort=_press(0.93, (0.025, 0.024, 0.026)))
    explicit = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                                 dpi=600, correction_form_id=cc.CORRECTION_FORM_ID)
    assert explicit.status == "applied"
    assert explicit.correction_form_id == cc.CORRECTION_FORM_ID
    # Un second appel nommant la meme forme rend le meme profil a l'octet: la
    # reproductibilite de la forme affine ne depend d'aucun etat de module.
    encore = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600, correction_form_id=cc.CORRECTION_FORM_ID)
    assert explicit.profile.stage_a.tobytes() == encore.profile.stage_a.tobytes()
    assert explicit.profile.stage_m.tobytes() == encore.profile.stage_m.tobytes()
    assert explicit.acceptance.mean_delta_e == encore.acceptance.mean_delta_e
    assert explicit.acceptance.max_delta_e == encore.acceptance.max_delta_e
    # Et le profil est bien celui qu'ajuste la fonction historique, appelee a la main
    # sur le meme jeu: le detour par le registre n'a rien deplace.
    measured, reference, neutral = _adjustment_arrays(
        PRESET.replace("patches-18-v2", "patch-values-2"),
        _press(0.93, (0.025, 0.024, 0.026)))
    direct = cc.fit_correction(measured, reference, neutral)
    through = cc.get_correction_form(cc.CORRECTION_FORM_ID)(measured, reference, neutral)
    assert direct.stage_a.tobytes() == through.stage_a.tobytes()
    assert direct.stage_m.tobytes() == through.stage_m.tobytes()


def test_calibrer_sans_nommer_de_forme_ajuste_la_forme_active_et_non_l_affine():
    """AC 2 de 5.21: le **silence** de l'appelant demande desormais la forme active.

    Trois volets, et aucun ne suffit seul:

    1. le resultat du silence est **identique a l'octet** a celui de la forme active
       nommee -- le defaut ne fait pas autre chose qu'elle;
    2. il est **different** de celui de la forme affine nommee, et pas seulement par son
       identifiant: les pixels corriges different. Sans ce volet, un defaut reste sur
       l'affine mais dont le champ `correction_form_id` mentirait passerait le premier;
    3. l'identifiant ecrit sur le resultat est celui de la forme active. C'est ce que le
       manifest relira.

    Les deux profils compares sont de **familles differentes** (`ToneCurveCorrectionProfile`
    contre `CorrectionProfile`), donc la comparaison ne peut pas passer par des champs
    communs: elle passe par ce que les deux savent faire -- corriger une image lineaire --
    et c'est aussi la seule grandeur qui compte pour l'operateur.
    """
    page = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET,
        distort=_press(0.93, (0.025, 0.024, 0.026)))
    tacite = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600)
    active = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600,
                               correction_form_id=cc.ACTIVE_CORRECTION_FORM_ID)
    affine = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600, correction_form_id=cc.CORRECTION_FORM_ID)
    assert tacite.status == active.status == affine.status == "applied"
    assert tacite.correction_form_id == cc.ACTIVE_CORRECTION_FORM_ID
    assert affine.correction_form_id == cc.CORRECTION_FORM_ID
    assert type(tacite.profile) is type(active.profile)
    assert type(tacite.profile) is not type(affine.profile)

    # Une rampe qui couvre l'etendue utile, et non un pixel: deux formes peuvent
    # coincider sur une valeur isolee sans coincider nulle part ailleurs.
    rampe = np.stack([np.linspace(0.02, 0.98, 32)] * 3, axis=1)
    par_defaut = tacite.profile.apply_linear(rampe)
    par_la_forme_active = active.profile.apply_linear(rampe)
    par_l_affine = affine.profile.apply_linear(rampe)
    assert par_defaut.tobytes() == par_la_forme_active.tobytes()
    assert np.abs(par_defaut - par_l_affine).max() > 1e-6, (
        "le defaut et la forme affine rendent les memes pixels: la bascule ne mord pas")
    assert tacite.acceptance.mean_delta_e == active.acceptance.mean_delta_e


def test_une_forme_inconnue_est_refusee_et_jamais_repliee_sur_la_forme_active():
    """Un repli rendrait le manifest menteur sur ce qui a ete applique (AC 10)."""
    with pytest.raises(cc.UnknownCorrectionFormError) as refus:
        cc.get_correction_form("color-correction-affine-matrix-2")
    assert "color-correction-affine-matrix-1" in str(refus.value)
    assert "color-correction-lab-lightness-chroma-1" in str(refus.value)
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET)
    with pytest.raises(cc.UnknownCorrectionFormError):
        cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
                          correction_form_id="color-correction-inventee-1")


@pytest.mark.parametrize("axis, moving", [(0, "clarte"), (1, "chroma")])
def test_les_deux_etages_lab_sont_orthogonaux_par_construction(axis, moving):
    """AC 1: corriger `L*` ne deplace ni `a*` ni `b*`, et reciproquement.

    C'est **la** propriete qui distingue cette forme de la forme en vigueur, et elle se
    verifie a l'exact: un etage neutralise doit laisser ses composantes rigoureusement
    inchangees, pas approximativement. La tolerance de 1e-9 ci-dessous est celle de
    l'aller-retour Lab, pas une marge de comportement.
    """
    colours = np.array([[0.20, 0.50, 0.80], [0.10, 0.10, 0.10],
                        [0.90, 0.85, 0.30], [0.45, 0.20, 0.60]])
    linear = cc.eotf(colours)
    before = cc.lab_from_linear_bgr(linear)
    if moving == "clarte":
        profile = cc.LabCorrectionProfile(
            lightness_slope=1.15, lightness_offset=-4.0,
            chroma_matrix=np.eye(2), chroma_offset=np.zeros(2))
    else:
        profile = cc.LabCorrectionProfile(
            lightness_slope=1.0, lightness_offset=0.0,
            chroma_matrix=np.array([[1.2, -0.05], [0.04, 1.25]]),
            chroma_offset=np.array([0.4, -0.3]))
    after = cc.lab_from_linear_bgr(profile.apply_linear(linear))
    if moving == "clarte":
        assert np.abs(after[:, 1:3] - before[:, 1:3]).max() < 1e-9
        assert np.abs(after[:, 0] - before[:, 0]).max() > 1.0
    else:
        assert np.abs(after[:, 0] - before[:, 0]).max() < 1e-9
        assert np.abs(after[:, 1:3] - before[:, 1:3]).max() > 0.1
    assert axis in (0, 1)  # le parametre nomme l'axe fixe, pour la lisibilite du rapport


def test_la_2x2_de_chroma_s_applique_dans_le_sens_declare_et_avec_son_decalage():
    """Le mapping de chroma, epingle **valeur par valeur** et calcule a la main.

    Trouve par la campagne de mutation (`B02`, `B03`): appliquer la 2x2 sans
    transposition, ou perdre le decalage, laissait tous les autres tests verts -- ils ne
    verifiaient que « la chroma a bouge » et « le residu a baisse », deux proprietes
    qu'une matrice transposee possede aussi. Une correction de chroma appliquee dans le
    mauvais sens est le cas d'ecole du resultat **plausible**: les couleurs bougent, dans
    la mauvaise direction.

    La matrice est volontairement **asymetrique** et le decalage non nul: avec une
    matrice symetrique, la transposition serait un equivalent et le mutant
    indetectable -- c'est la meme raison qui fait que la regle des fabriques exige des
    elements distinguables.
    """
    matrix = np.array([[1.2, -0.05], [0.04, 1.25]])
    offset = np.array([0.4, -0.3])
    assert not np.allclose(matrix, matrix.T)
    profile = cc.LabCorrectionProfile(
        lightness_slope=1.0, lightness_offset=0.0,
        chroma_matrix=matrix, chroma_offset=offset)
    lab_in = np.array([[50.0, 20.0, -10.0]])
    out = cc.lab_from_linear_bgr(profile.apply_linear(cc.linear_bgr_from_lab(lab_in)))
    # a' = 1,2 x 20 + (-0,05) x (-10) + 0,4 = 24,9
    # b' = 0,04 x 20 + 1,25 x (-10) + (-0,3) = -12,0
    assert out[0, 1] == pytest.approx(24.9, abs=1e-9)
    assert out[0, 2] == pytest.approx(-12.0, abs=1e-9)
    assert out[0, 0] == pytest.approx(50.0, abs=1e-9)


def test_le_decalage_de_chroma_est_ajuste_et_non_suppose_nul():
    """Une derive de chroma **constante** ne se corrige que par le decalage.

    Trouve par la campagne (`B04`): supprimer le decalage a l'ajustement laissait la
    matrice absorber une partie de la derive, donc le residu baissait quand meme et
    aucun test ne rougissait. Le cas est realiste: un voile de papier deplace `(a*, b*)`
    d'une constante, pas d'un facteur.
    """
    reference = np.array([[30.0, -18.0, 6.0], [55.0, 24.0, -12.0],
                          [70.0, 4.0, 30.0], [45.0, 0.0, 0.0]])
    drift = np.array([3.0, -2.0])
    measured = reference.copy()
    measured[:, 1:3] += drift
    neutral = np.array([False, False, False, True])
    matrix, offset = cc.fit_lab_chroma(measured, reference, neutral)
    assert np.abs(matrix - np.eye(2)).max() < 1e-9
    assert offset == pytest.approx(-drift, abs=1e-9)


def test_la_clarte_est_ajustee_sur_le_seul_axe_neutre_et_pas_sur_tous_les_points():
    """AC 1: `L*` affine sur le **seul** axe neutre, et le jeu le rend verifiable.

    Trouve par la campagne (`B05`): ajuster la clarte sur tous les points laissait le
    residu baisser, donc survivait. Le jeu de ce test est construit pour que les deux
    regressions soient **incompatibles** -- les neutres impliquent une pente, les
    couleurs une autre --, ce qui est exactement la situation mesuree le 2026-08-10 ou
    ajuster sur tous les points sur-corrigeait la peau de ~3 unites de `L*`.
    """
    measured = np.array([[20.0, 0.3, -0.2], [80.0, 0.1, 0.4],
                         [40.0, 25.0, -15.0], [60.0, -20.0, 18.0]])
    reference = np.array([[25.0, 0.0, 0.0], [90.0, 0.0, 0.0],
                          [10.0, 22.0, -13.0], [95.0, -18.0, 16.0]])
    neutral = np.array([True, True, False, False])
    slope, offset = cc.fit_lab_lightness(measured, reference, neutral)
    # Les deux neutres determinent exactement la droite: (20 -> 25) et (80 -> 90).
    expected_slope = (90.0 - 25.0) / (80.0 - 20.0)
    assert slope == pytest.approx(expected_slope, abs=1e-9)
    assert offset == pytest.approx(25.0 - expected_slope * 20.0, abs=1e-9)
    # Et la droite des quatre points predit franchement autre chose: le jeu discrimine.
    # La comparaison porte sur la **prediction** et non sur la pente, parce que c'est la
    # prediction qui corrige un pixel -- et 10 unites de `L*` sur l'ancre sombre est un
    # ecart largement perceptible, la ou une difference de pente ne dit pas encore ou.
    all_points = np.polyfit(measured[:, 0], reference[:, 0], 1)
    assert abs(np.polyval(all_points, 20.0) - (slope * 20.0 + offset)) > 5.0


def test_l_etage_a_de_la_forme_en_vigueur_deplace_la_teinte_lui():
    """Le motif de l'AC 1, verifie et non recopie de la story.

    L'etage `A` applique des gains **par canal RGB** ajustes sur les gris: neutraliser
    un gris de cette facon change les rapports entre canaux de toute couleur non
    neutre, donc sa teinte. Si ce test devenait vert a l'envers -- `A` laissant la
    chroma tranquille --, la seconde forme n'aurait plus de motif.
    """
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    stage_a = cc.fit_stage_a(cc.eotf(measured[neutral]), cc.eotf(reference[neutral]))
    saturated = ~neutral
    before = cc.lab_from_linear_bgr(cc.eotf(measured[saturated]))
    after = cc.lab_from_linear_bgr(cc.apply_stage_a(stage_a, cc.eotf(measured[saturated])))
    chroma_shift = np.hypot(*(after[:, 1:3] - before[:, 1:3]).T)
    assert chroma_shift.max() > 1.0, (
        "l'etage A ne deplace plus la chroma: le motif de la seconde forme a disparu")


# ---------------------------------------------------------------------------
# AC 2 : les cardinaux gardes et nommes
# ---------------------------------------------------------------------------

def test_les_cardinaux_minimaux_sont_nommes_et_valent_deux_et_trois():
    assert cc.MIN_DISTINCT_NEUTRALS_FOR_LIGHTNESS == 2
    assert cc.MIN_DISTINCT_CHROMA_POINTS == 3


def test_les_deux_motifs_de_refus_sont_epingles_valeur_par_valeur():
    """Sans cet epinglage, une **permutation** des deux motifs est invisible.

    Mesure de la campagne de mutation de cette story (`A08`): echanger les valeurs des
    deux constantes laisse les 268 tests verts, parce que chaque assertion compare la
    constante a elle-meme. Un motif nomme qui nomme l'autre defaut est pire qu'un motif
    absent -- il envoie relire la mauvaise garde. C'est litteralement le mutant `M33` de
    la story 5.6 et `A01` de la 5.17: un appariement faux ne se voit que si quelqu'un
    regarde les valeurs une par une.
    """
    assert cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS == (
        "lightness_needs_two_distinct_neutrals")
    assert cc.REFUSAL_CHROMA_NEEDS_THREE_POINTS == "chroma_needs_three_distinct_points"


def test_l_affine_de_clarte_refuse_un_seul_neutre_avec_un_motif_nomme():
    """AC 2: refuse **et** nomme. Un refus muet ne se distingue pas d'un plantage."""
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    lab_measured = cc.lab_from_linear_bgr(cc.eotf(measured))
    lab_reference = cc.lab_from_linear_bgr(cc.eotf(reference))
    # Un seul neutre retenu, et ce n'est **pas** le premier du jeu: un comptage qui
    # regarderait le rang au lieu du masque passerait sur le premier.
    single = np.zeros(len(neutral), dtype=bool)
    single[np.flatnonzero(neutral)[-1]] = True
    assert np.flatnonzero(single)[0] != 0
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as refus:
        cc.fit_lab_lightness(lab_measured, lab_reference, single)
    assert refus.value.reason == cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS
    assert cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS in str(refus.value)
    assert "1 trouvee(s)" in str(refus.value) or "1 trouvee" in str(refus.value)


def test_deux_neutres_lus_identiquement_ne_font_pas_deux_neutres_distincts():
    """La distinction porte sur la **mesure**, pas sur le cardinal du masque.

    Deux references distinctes lues identiquement -- scan sature, plancher d'encrage --
    laissent l'affine indeterminee tout autant qu'un point unique, et `lstsq` rendrait
    alors une pente proche de zero: « ecraser toute la page sur une seule clarte », un
    resultat plausible donc non detecte. Un comptage sur `neutral_mask.sum()` passerait
    ce cas, et c'est pourquoi le test existe.
    """
    lab_measured = np.array([[50.0, 0.0, 0.0], [50.0, 0.1, -0.1], [60.0, 12.0, -8.0]])
    lab_reference = np.array([[42.0, 0.0, 0.0], [58.0, 0.0, 0.0], [61.0, 10.0, -7.0]])
    both_neutral = np.array([True, True, False])
    assert both_neutral.sum() == 2
    assert cc.distinct_neutral_lightness_count(lab_measured, both_neutral) == 1
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as refus:
        cc.fit_lab_lightness(lab_measured, lab_reference, both_neutral)
    assert refus.value.reason == cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS


def test_la_2x2_de_chroma_refuse_deux_points_et_la_resolution_nue_ne_dirait_rien():
    """AC 2: sous le cardinal, `lstsq` rend une matrice **valide** sans rien signaler.

    L'assertion la plus importante n'est pas le refus, c'est la seconde moitie: sur le
    meme jeu, la resolution **non gardee** ne leve rien et rend des coefficients finis.
    Le probleme n'est donc pas detectable en aval -- une matrice de norme minimale
    determinee par moins de points qu'elle n'a de parametres est une correction
    plausible, pas une erreur. C'est le defaut exact corrige sur `fit_stage_m` le
    2026-08-11, ou la solution de norme minimale valait litteralement l'identite: la
    forme change, la nature du piege non. Sans cette demonstration, le refus pourrait
    etre supprime en revue au motif que « lstsq gere le cas degenere ».
    """
    # Deux points de chroma seulement: un neutre (qui compte pour un) et une couleur.
    lab_measured = np.array([[50.0, 0.5, -0.5], [61.0, 24.0, -18.0]])
    lab_reference = np.array([[50.0, 0.0, 0.0], [60.0, 22.0, -16.0]])
    neutral = np.array([True, False])
    assert cc.distinct_chroma_point_count(lab_measured, neutral) == 2
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as refus:
        cc.fit_lab_chroma(lab_measured, lab_reference, neutral)
    assert refus.value.reason == cc.REFUSAL_CHROMA_NEEDS_THREE_POINTS
    assert "3 points de chroma distincts" in str(refus.value)

    design = np.stack([lab_measured[:, 1], lab_measured[:, 2], np.ones(2)], axis=1)
    assert np.linalg.matrix_rank(design) < design.shape[1], (
        "le jeu n'est plus sous-determine: la demonstration ne demontre rien")
    solved = np.linalg.lstsq(design, lab_reference[:, 1:3], rcond=None)[0]
    assert np.isfinite(solved).all(), (
        "lstsq a cesse de rendre une solution plausible sur un jeu degenere: le motif "
        "de la garde a change, la garde doit etre relue")


def test_les_neutres_comptent_pour_un_seul_point_de_chroma():
    """La regle de comptage de l'AC 2, mot pour mot, et elle est conservatrice.

    Quatre neutres et deux couleurs font **trois** points, pas six: c'est ce qui fait
    qu'un jeu presque entierement neutre est refuse au lieu de produire une 2x2 tenue
    par des gris. Le sens de l'erreur est le bon: sous-compter refuse davantage.
    """
    lab = np.array([[20.0, 0.4, -0.2], [40.0, 0.3, -0.1], [60.0, 0.5, 0.2],
                    [80.0, 0.1, 0.3], [55.0, 30.0, 12.0], [48.0, -20.0, 25.0]])
    neutral = np.array([True, True, True, True, False, False])
    assert cc.distinct_chroma_point_count(lab, neutral) == 3
    only_neutrals = np.array([True, True, True, True, True, True])
    assert cc.distinct_chroma_point_count(lab, only_neutrals) == 1


def test_le_cardinal_de_chroma_se_compte_sur_a_et_b_et_jamais_sur_la_clarte():
    """Deux couleurs de **meme chroma** a deux clartes ne font qu'un point de chroma.

    Trouve par la campagne de mutation (`A11`): compter sur les colonnes `(L*, a*)` au
    lieu de `(a*, b*)` laissait tous les autres tests verts, parce qu'aucun de leurs jeux
    ne portait deux points de meme chroma. Or c'est un cas parfaitement realiste -- deux
    pastilles de la meme teinte a deux niveaux --, et sous la confusion la 2x2 serait
    ajustee sur deux contraintes identiques en se croyant determinee.
    """
    same_chroma = np.array([[30.0, 18.0, -9.0], [70.0, 18.0, -9.0], [50.0, 0.2, 0.1]])
    neutral = np.array([False, False, True])
    assert cc.distinct_chroma_point_count(same_chroma, neutral) == 2
    with pytest.raises(cc.UnderdeterminedAdjustmentSet) as refus:
        cc.fit_lab_chroma(same_chroma, same_chroma, neutral)
    assert refus.value.reason == cc.REFUSAL_CHROMA_NEEDS_THREE_POINTS


def test_un_jeu_sous_determine_reste_dans_le_vocabulaire_ferme_de_l_ac_8():
    """`UnderdeterminedAdjustmentSet` est une `ValueError`: le motif de page ne change pas.

    Sans cet heritage, la nouvelle forme ouvrirait un second vocabulaire d'echec a cote
    de celui de l'AC 8 de 5.4b, et une page non corrigeable remonterait une exception au
    lieu de se declarer.
    """
    assert issubclass(cc.UnderdeterminedAdjustmentSet, ValueError)
    assert cc.FAILURE_UNDERDETERMINED_ADJUSTMENT == "adjustment_set_underdetermined"


def test_la_forme_lab_s_ajuste_sur_le_jeu_de_production_et_corrige(  # noqa: D103
):
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    profile = cc.fit_correction_lab(measured, reference, neutral)
    assert profile.correction_id == cc.CORRECTION_FORM_LAB_ID
    before = float(de76(measured, reference).mean())
    after = cc.residual_de76(profile, measured, reference)
    assert after < before, (before, after)


def test_la_2x2_de_chroma_est_rendue_transposee_pour_son_application():
    """**Mutant `V07`**, dette heritee de la revue de 5.16 et fermee par la story 5.19.

    `fit_lab_chroma` resout `design @ X = reference` par `lstsq`, donc `X[i][j]` est le
    coefficient de l'**entree** `i` vers la **sortie** `j`. L'application, elle, est
    `ab @ matrice.T + decalage`, donc la matrice rendue doit etre `X.T`. Retirer cette
    transposition **transpose la correction de chroma**: `a*` recoit le coefficient croise
    de `b*` et reciproquement.

    Pourquoi le mutant survivait a 184 tests des trois suites couleur, alors que la
    propriete est centrale: **toutes** les 2x2 que les jeux existants produisent sont
    quasi symetriques. Une presse de synthese applique un crosstalk symetrique et un gain
    par canal, donc ses deux coefficients croises coincident a 1e-2 pres, et une matrice
    symetrique est **egale a sa transposee**. Le mutant ne change alors rien de mesurable:
    c'est la meme famille que « deux valeurs qui coincident sur toutes les fixtures cachent
    une derivation fausse », deja payee sur les campagnes 5.7 et 5.8.

    Le jeu de ce test est donc construit pour que la 2x2 exacte soit **franchement
    asymetrique** -- ses deux croises valent +0,30 et -0,05, soit six fois l'un l'autre et
    de signe contraire --, et l'assertion porte sur les coefficients eux-memes plus sur
    l'application. Les deux volets sont necessaires: la premiere seule serait tenue par une
    convention de stockage differente mais coherente, la seconde seule le serait par une
    matrice symetrique.
    """
    # Verite terrain: une affine asymetrique sur (a*, b*), et **rien** sur L*.
    exacte = np.array([[1.10, 0.30], [-0.05, 0.90]], dtype=np.float64)
    decalage_exact = np.array([2.0, -1.0], dtype=np.float64)
    # Cinq points de chroma distincts, largement au-dela des trois exiges, et aucun
    # colineaire: la resolution est alors exacte et le test mesure la convention de
    # stockage, pas le conditionnement.
    chroma = np.array([[18.0, -9.0], [-14.0, 21.0], [6.0, 30.0], [-25.0, -4.0],
                       [0.0, 0.0]], dtype=np.float64)
    clartes = np.array([[40.0], [55.0], [62.0], [31.0], [50.0]], dtype=np.float64)
    mesure = np.hstack([clartes, chroma])
    reference = np.hstack([clartes, chroma @ exacte.T + decalage_exact])
    neutre = np.array([False, False, False, False, True])

    matrice, decalage = cc.fit_lab_chroma(mesure, reference, neutre)

    # 1. La convention de stockage: la matrice rendue est `X.T`, donc **elle-meme** la
    #    matrice exacte. Sans la transposition, on obtiendrait sa transposee -- que
    #    l'asymetrie rend distinguable.
    assert np.allclose(matrice, exacte, atol=1e-9), matrice
    assert not np.allclose(matrice, exacte.T, atol=1e-3), (
        "le jeu doit etre asymetrique, sinon le mutant est indistinguable")
    assert np.allclose(decalage, decalage_exact, atol=1e-9), decalage

    # 2. L'application, dans la forme exacte que `LabCorrectionProfile.apply_linear`
    #    emploie: `ab @ matrice.T + decalage` doit rendre la reference.
    assert np.allclose(chroma @ matrice.T + decalage, reference[:, 1:3], atol=1e-9)

    # 3. Et le meme volet a travers le profil complet, sur la chroma d'un point: c'est
    #    l'appelant reel, et il est le seul a etablir que la convention de stockage et
    #    celle de l'application s'accordent.
    profil = cc.LabCorrectionProfile(
        lightness_slope=1.0, lightness_offset=0.0,
        chroma_matrix=matrice, chroma_offset=decalage)
    lab = cc.lab_from_linear_bgr(cc.eotf(np.array([[0.35, 0.55, 0.70]])))
    attendu = lab[:, 1:3] @ exacte.T + decalage_exact
    obtenu = cc.lab_from_linear_bgr(profil.apply_linear(cc.eotf(
        np.array([[0.35, 0.55, 0.70]]))))
    assert np.allclose(obtenu[:, 1:3], attendu, atol=1e-6), (obtenu, attendu)


# ---------------------------------------------------------------------------
# AC 4 : la source externe, et le filtre de saturation
# ---------------------------------------------------------------------------

def test_l_identifiant_de_treillis_fait_coincider_ordre_lexicographique_et_balayage():
    """**Mutant `R06`**: les zeros de tete de l'identifiant n'etaient asseres nulle part.

    `_lattice_value_id` formate ses trois champs sur **trois chiffres a zeros de tete**, et
    sa docstring dit pourquoi: « l'ordre lexicographique des identifiants coincide alors
    avec l'ordre du balayage, ce dont `aggregate_by_value` a besoin pour rendre deux fois le
    meme tableau sur les memes donnees ». Cette propriete etait **enoncee et jamais
    verifiee**: le mutant qui retire le formatage (`{red}` au lieu de `{red:03d}`) laissait
    la suite verte.

    Mesure de ce qu'il casse, avec les niveaux livres `(8, 68, 128, 188, 245)`: sans zeros
    de tete, `'lattice-128-128-128'` passe **avant** `'lattice-8-8-8'` en ordre
    lexicographique, puisque `'1' < '8'`. L'ordre trie cesse donc d'etre l'ordre du
    balayage, et le determinisme que `aggregate_by_value` doit rendre repose sur une
    coincidence rompue -- deux executions sur les memes donnees pourraient rendre deux
    tableaux ordonnes differemment selon la voie qui les a produits.

    Les deux volets sont necessaires: le premier constate la coincidence, le second constate
    qu'elle **depend du formatage** et n'est pas vraie de n'importe quel identifiant. Sans
    le second, un mutant qui changerait le formatage sans casser l'ordre passerait -- et
    surtout, le test ne dirait pas *pourquoi* les zeros sont la.
    """
    identifiants = [value.value_id for value in patch_values.calibration_lattice_values()]
    # 1. L'ordre du balayage **est** l'ordre lexicographique.
    assert identifiants == sorted(identifiants)
    # Et le balayage est bien R puis G puis B, sur les 125 valeurs (temoin de non-vacuite).
    assert len(identifiants) == 125
    assert identifiants[0] == "lattice-008-008-008"
    assert identifiants[-1] == "lattice-245-245-245"

    # 2. La coincidence **depend des zeros de tete**: sans eux elle tombe. C'est ce volet
    #    qui rend le premier load-bearing plutot que decoratif.
    niveaux = patch_values.CALIBRATION_LATTICE_LEVELS
    sans_remplissage = [f"lattice-{red}-{green}-{blue}"
                        for red in niveaux for green in niveaux for blue in niveaux]
    assert sans_remplissage != sorted(sans_remplissage), (
        "les niveaux livres ne discriminent plus le formatage: le test ne prouve plus "
        "que les zeros de tete portent l'ordre")
    # La cause exacte, epinglee pour qu'un lecteur n'ait pas a la redecouvrir.
    assert sorted(sans_remplissage)[0] == "lattice-128-128-128"

    # 3. Le formatage est celui que l'identifiant **derive** de son triplet, jamais un
    #    litteral: un identifiant desynchronise de sa couleur est la faute que ce format
    #    existe pour rendre impossible.
    for value in patch_values.calibration_lattice_values():
        red, green, blue = value.rgb
        assert value.value_id == f"lattice-{red:03d}-{green:03d}-{blue:03d}"


def test_le_treillis_et_son_filtre_ont_des_cardinaux_derives_de_leurs_niveaux():
    """AC 4: le compte retenu et le seuil, epingles -- mais **derives**, pas recopies.

    **Ecart mesure le 2026-08-12 avec le chiffre de la story, a porter au Dev Agent
    Record.** L'AC 4 annonce « 106 pastilles sur 250 ». Le descripteur de la cible v3
    (`cible_lut_v3.json`, `lattice_levels = [8, 68, 128, 188, 245]`) porte bien **250**
    pastilles de treillis, mais **130** d'entre elles ont une saturation de reference
    `<= 120`, soit 65 couleurs en double replicat. Les 106 du banc sont donc un compte
    **de lecture** -- 24 pastilles dont le carre echantillonne tombait hors du raster
    redresse de ce scan-la -- et non une propriete du treillis et de son seuil. C'est
    exactement pourquoi ce test **derive** le compte au lieu de recopier un litteral:
    un compte de lecture depend du scan, et la page de calibration doit porter ce que
    le filtre retient.

    La conclusion de dimensionnement de la story tient: 130 pastilles de 12 mm tiennent
    dans les 141 cellules du portrait comme dans les 135 du paysage, et 14 mm reste
    hors d'atteinte (103 cellules en paysage).
    """
    levels = patch_values.CALIBRATION_LATTICE_LEVELS
    lattice = patch_values.calibration_lattice_values()
    retained = patch_values.calibration_lattice_adjustment_values()
    assert len(lattice) == len(levels) ** 3 == 125
    # Le compte retenu est celui du filtre, derive niveau par niveau.
    expected = [(red, green, blue) for red in levels for green in levels
                for blue in levels
                if max(red, green, blue) - min(red, green, blue)
                <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT]
    assert len(retained) == len(expected) == 65
    assert 2 * len(retained) == 130
    assert patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT == 120
    # Le filtre est **exclusif dans les deux sens**: rien de retenu au-dessus du seuil,
    # rien d'ecarte en dessous. Une garde qui ne ferait que la premiere moitie laisserait
    # jeter des couleurs parfaitement atteignables.
    kept_ids = {value.value_id for value in retained}
    for value in lattice:
        saturation = patch_values.lattice_saturation_8bit(value.rgb)
        assert (value.value_id in kept_ids) is (
            saturation <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT)


def _retenues_au_seuil(seuil: int) -> frozenset[str]:
    """Identifiants retenus si le seuil valait `seuil`. **Independant de la constante.**

    Le calcul ne lit pas `CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT`, et c'est tout
    l'interet: une derivation qui le lirait rendrait le meme jeu pour n'importe quelle
    valeur, ce qui est exactement la tautologie que le test ci-dessous ferme.
    """
    return frozenset(
        value.value_id for value in patch_values.calibration_lattice_values()
        if patch_values.lattice_saturation_8bit(value.rgb) <= seuil
    )


def test_le_seuil_de_saturation_est_pose_sur_une_classe_ATTEINTE_et_au_bas_de_son_plateau():
    """**Majeur M5 de la couche 1**: le seuil etait verrouille par une tautologie.

    Le seul verrou du seuil etait `... == 120`, et toutes les autres assertions du test
    voisin **derivent du seuil lui-meme** (`... <= LIMIT`), donc sont vraies pour n'importe
    quelle valeur. Mesure qui l'a montre: les etendues **atteintes** par les 125 couleurs
    du treillis sont `{0, 57, 60, 117, 120, 177, 180, 237}`, donc **tout seuil de 120 a
    176 rend le meme jeu de 65 couleurs**, soit les memes 130 pastilles. Aucun cardinal,
    aucun placement, aucun residu ne peut distinguer 120 de 130: le mutant `C01` de la
    campagne couleur (`120 -> 130`) est un **equivalent semantique**, et le declarer tue
    faisait surestimer son « zero survivant » d'un.

    Ce test remplace le litteral par les trois proprietes qui **mordent**, et qui disent
    ensemble ce que « c'est une regle, pas un reglage » (AC 4) veut dire:

    1. **la classe frontiere est atteinte** -- 24 des 125 couleurs ont une etendue de
       **exactement** 120 et sont retenues. C'est elle qui rend l'inclusivite du `<=`
       load-bearing, et c'est la vraie raison pour laquelle les mutants `C02` / `C03`
       (`<=` -> `<`) meurent: sans une seule couleur sur la frontiere, les deux
       comparateurs seraient indistinguables et leur mort serait, elle aussi, un accident;
    2. **le plateau est explicite** -- le jeu retenu est le meme pour tout seuil de 120 a
       176 inclus. C'est une bonne nouvelle sur le fond, et elle rend la these de l'AC 4
       **plus** solide que le code ne le disait: le choix est insensible sur 57 codes.
       Ecrite ici, elle permet a un lecteur de distinguer « 120 a ete regle » de « 120 est
       au milieu d'un plateau », distinction que l'AC 4 revendique;
    3. **les deux bords du plateau mordent** -- 119 fait tomber le jeu de 65 a 41 (il perd
       exactement les 24 couleurs de la classe frontiere), 177 le fait monter a 83. Le
       seuil n'est donc pas pose dans un vide, et le voisinage ou il est insensible est
       **borne des deux cotes**, mesure et non suppose.

    Et 120 n'est pas un membre quelconque du plateau: c'est son **plus petit** element,
    donc le seuil le plus serre qui admette encore les 65 couleurs. C'est la propriete que
    l'epinglage nu ne disait pas, et elle suffit a tuer un mutant qui poserait 130 -- pour
    un motif enonce (« 130 n'est pas le bas du plateau ») et non par comparaison a soi.
    """
    lattice = patch_values.calibration_lattice_values()
    seuil = patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT
    etendues = {patch_values.lattice_saturation_8bit(value.rgb) for value in lattice}
    assert sorted(etendues) == [0, 57, 60, 117, 120, 177, 180, 237], sorted(etendues)

    # 1. La classe frontiere est **atteinte**, et retenue. Sans ce volet, `<=` et `<`
    #    seraient le meme filtre et la mort de `C02` / `C03` ne prouverait rien.
    sur_la_frontiere = [value for value in lattice
                        if patch_values.lattice_saturation_8bit(value.rgb) == seuil]
    assert len(sur_la_frontiere) == 24, len(sur_la_frontiere)
    retenues = _retenues_au_seuil(seuil)
    assert len(retenues) == 65
    # ... et c'est le **vrai producteur** qui doit les retenir, jamais la derivation de ce
    # test. Mesure qui a impose ce volet: ecrite contre `_retenues_au_seuil` seule, la
    # frontiere ne mordait pas -- le mutant `C02` (`<=` -> `<` dans `patch_values`) laissait
    # ce test **vert**, parce que les deux cotes de l'assertion tombaient d'accord sans
    # jamais consulter le filtre livre. C'est litteralement le motif `EPIC5-ARB-39`: un
    # test contre le vrai producteur ne suffit pas s'il n'assert pas sur la famille de
    # valeurs qui distingue.
    produites = {value.value_id
                 for value in patch_values.calibration_lattice_adjustment_values()}
    assert produites == retenues, sorted(produites ^ retenues)[:5]
    assert {value.value_id for value in sur_la_frontiere} <= produites

    # 2. Le plateau: 57 codes consecutifs donnent le **meme** jeu, a l'identifiant pres.
    for candidat in range(120, 177):
        assert _retenues_au_seuil(candidat) == retenues, candidat

    # 3. Les deux bords mordent, et le bord bas perd exactement la classe frontiere.
    en_dessous = _retenues_au_seuil(119)
    assert len(en_dessous) == 41, len(en_dessous)
    assert retenues - en_dessous == {value.value_id for value in sur_la_frontiere}
    au_dessus = _retenues_au_seuil(177)
    assert len(au_dessus) == 83, len(au_dessus)
    assert en_dessous < retenues < au_dessus

    # Et le seuil en vigueur est le **bas** du plateau, jamais un point quelconque dedans.
    assert seuil == min(candidat for candidat in range(0, 238)
                        if _retenues_au_seuil(candidat) == retenues)


def test_le_descripteur_de_la_cible_confirme_les_niveaux_et_le_cardinal_lu():
    """Contre le **vrai** descripteur du depot, pas contre une constante recopiee.

    C'est la seule facon de savoir que les niveaux du module sont ceux qui ont produit
    le 4,66 dE76: une constante egale a elle-meme ne prouve rien.
    """
    descriptor = pathlib.Path(
        "_bmad-output/test-artifacts/cible-de-mesure/cible_lut_v3.json")
    assert descriptor.exists(), (
        "descripteur de la cible v3 absent: la provenance des niveaux du treillis "
        "n'est plus verifiable, et une fixture manquante bloque au lieu de se "
        "substituer")
    spec = json.loads(descriptor.read_text(encoding="utf-8"))
    assert tuple(spec["lattice_levels"]) == patch_values.CALIBRATION_LATTICE_LEVELS
    patches = [element for page in spec["pages"] for element in page["elements"]
               if element["kind"] == "lattice_patch"]
    assert len(patches) == 250
    under = [element for element in patches
             if patch_values.lattice_saturation_8bit(element["reference_rgb"])
             <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT]
    assert len(under) == 130, (
        "le descripteur reel ne rend plus 130 pastilles sous le seuil: le chiffre de "
        "106 de l'AC 4 est un compte de lecture, celui-ci est une propriete du treillis")


def test_la_source_externe_agrege_ses_deux_ordres_et_porte_ses_trois_cardinaux():
    """AC 4: trois nombres differents, et aucun ne se deduit des autres.

    La fabrique lit les 250 pastilles dans les deux ordres inverses, donc une valeur
    donnee n'a pas le meme rang dans les deux moities: un appariement positionnel entre
    identifiants et mesures ne survit pas a ce test (regle des fabriques, mutant `M33`).
    """
    press = _press(0.93, (0.025, 0.024, 0.026), chroma_limit=0.20)
    measured, ids = _lattice_measurement(press)
    # **La forme est nommee** (story 5.21): les cardinaux asserts ci-dessous sont ceux
    # de la politique de plancher de la forme affine (`EPIC5-ARB-77`), pas ceux du
    # defaut de production, qui depuis 5.21 est la forme active et **garde** le
    # plancher. La politique de l'autre forme a son propre test parametre
    # (`test_le_jeu_du_treillis_suit_la_politique_de_plancher_de_sa_forme`).
    source = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0",
                                          correction_form_id=cc.CORRECTION_FORM_ID)
    assert source.read_patch_count == 250
    # **128 et non 130 depuis l'AC 7 de la story 5.20**: les deux repliques de
    # `lattice-008-008-008` sortent du jeu d'ajustement, le plancher d'encrage rendant
    # ce niveau indiscernable de ses voisins sur l'imprimante d'Egan. Le cardinal est
    # **derive** de la garde et non recopie -- recopier 128 ferait de ce test une
    # constante a maintenir a chaque revision du plancher.
    exclues = set(patch_values.ink_floor_lattice_value_ids())
    assert source.retained_patch_count == 130 - 2 * len(exclues)
    assert len(source.value_ids) == 65 - len(exclues)
    assert not exclues & set(source.value_ids)
    assert source.source_page_id == "calibration-0"
    # L'ordre de sortie est lexicographique, comme `aggregate_by_value` le garantit.
    assert list(source.value_ids) == sorted(source.value_ids)
    # L'agregation H4 est verifiable: les offsets opposes s'annulent, donc la mesure
    # agregee est exactement la mesure nominale.
    lattice = {value.value_id: value for value in patch_values.calibration_lattice_values()}
    nominal = press(np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in source.value_ids]))
    assert np.abs(source.measured_bgr - nominal).max() < 1e-12
    # Et les references sont bien celles du treillis, en **BGR**: une inversion R/B ne
    # casserait rien de visible, elle ferait converger la correction sur les mauvaises
    # couleurs. Une valeur non symetrique le voit, une valeur grise non.
    asymmetric = next(value_id for value_id in source.value_ids
                      if len(set(lattice[value_id].rgb)) == 3)
    index = source.value_ids.index(asymmetric)
    assert asymmetric != source.value_ids[0]
    assert tuple(np.round(source.reference_bgr[index] * 255.0).astype(int)) == tuple(
        reversed(lattice[asymmetric].rgb))

    # **Et l'appariement est verifie sur les 65 lignes, pas sur une seule.**
    #
    # Mutant `R05` de la campagne de la couche 1, mesure pour la premiere fois a la passe
    # de correction du 2026-08-12: il lit la reference sur `kept_ids[:len(aggregated_ids)]`
    # -- les 65 **premieres pastilles retenues** -- au lieu des 65 **valeurs agregees**. Les
    # 130 pastilles retenues etant en double replicat, la troncature rend un jeu qui contient
    # des doublons et s'arrete au milieu du treillis: chaque ligne de `reference_bgr` designe
    # alors une autre couleur que celle que `value_ids` annonce.
    #
    # Il **survivait** a l'assertion ci-dessus, qui ne regarde qu'une ligne: c'est
    # exactement le motif `EPIC5-ARB-39` -- un test contre le vrai producteur ne suffit pas
    # s'il n'assert pas sur chaque famille de valeurs projetee. Et c'est la famille `M33` /
    # `M25`, celle qui a coute cinq regressions a ce depot, appliquee ici a l'appariement
    # `valeur agregee -> reference`.
    attendues = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in source.value_ids], dtype=np.float64)
    assert source.reference_bgr.shape == (65 - len(exclues), 3)
    assert np.abs(source.reference_bgr - attendues).max() < 1e-12, (
        "l'appariement valeur agregee -> reference est rompu")
    # **Mais cette fabrique-ci ne suffit pas a tuer `R05`, et c'est un defaut de fabrique
    # et non de test.** Ses deux repliques sont deux **blocs** consecutifs (ordre direct
    # puis ordre inverse), donc les 65 premieres pastilles retenues sont exactement les 65
    # valeurs distinctes, dans l'ordre trie -- le jeu tronque que le mutant lirait
    # **coincide** avec le bon. C'est litteralement la regle des fabriques du depot: un
    # remplissage dont l'ordre est trop regulier rend une permutation invisible.
    #
    # Le constat est donc ecrit ici plutot que suppose, et la variante qui discrimine est
    # dans `test_la_reference_de_la_source_externe_suit_la_valeur_agregee_et_non_le_rang`.
    # Le miroir local du filtre de production porte ses **deux** clauses depuis l'AC 7
    # de la story 5.20: la saturation **et** le plancher d'encrage. N'en garder qu'une
    # ferait de ce volet une comparaison a un jeu que la production ne construit plus.
    retenus_avec_doublons = [value_id for value_id in ids
                             if patch_values.lattice_saturation_8bit(lattice[value_id].rgb)
                             <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT
                             and not patch_values.is_below_ink_floor(lattice[value_id].rgb)]
    assert len(retenus_avec_doublons) == 130 - 2 * len(exclues)
    assert retenus_avec_doublons[:len(source.value_ids)] == list(source.value_ids), (
        "si ceci cesse d'etre vrai, la fabrique a change et le test voisin doit etre relu")


def test_la_reference_de_la_source_externe_suit_la_valeur_agregee_et_non_le_rang():
    """**Mutant `R05`**: la reference etait lue sur un **rang** et non sur la valeur.

    Le mutant remplace `for value_id in aggregated_ids` par
    `for value_id in kept_ids[:len(aggregated_ids)]` -- les 65 **premieres pastilles
    retenues** au lieu des 65 **valeurs agregees**. Les 130 pastilles retenues etant en
    double replicat, la troncature rend un jeu qui contient des doublons et s'arrete au
    milieu du treillis: chaque ligne de `reference_bgr` designerait alors une autre couleur
    que celle que `value_ids` annonce. Symptome reel: la correction converge sur les
    mauvaises couleurs, sans qu'aucun cardinal ni aucun residu ne bouge de facon suspecte.

    **Pourquoi il fallait une fabrique de plus, et c'est le fond du test.** Le mutant
    survivait a la fabrique par defaut, et pas parce que l'assertion manquait: parce que
    l'ordre de cette fabrique fait **coincider** les deux jeux. Ses deux repliques sont deux
    blocs consecutifs, donc les 65 premieres retenues sont exactement les 65 valeurs
    distinctes triees. La fabrique entrelacee casse cette coincidence -- c'est la regle des
    fabriques du depot, dans sa forme la plus litterale: un remplissage dont l'ordre est trop
    regulier rend une permutation invisible, et cela ne se decouvre que par mutation.

    L'appariement est verifie sur les **65 lignes** et non sur une, ce qui est l'autre moitie
    de la lecon (`EPIC5-ARB-39`): un test contre le vrai producteur ne suffit pas s'il
    n'assert pas sur chaque famille de valeurs projetee.
    """
    press = _press(0.93, (0.025, 0.024, 0.026), chroma_limit=0.20)
    measured, ids = _lattice_measurement(press, interleave=True)
    # Forme nommee, meme raison qu'au test precedent (story 5.21).
    source = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0",
                                          correction_form_id=cc.CORRECTION_FORM_ID)
    lattice = {value.value_id: value for value in patch_values.calibration_lattice_values()}

    # La fabrique rend les memes cardinaux: seul l'ordre de lecture change.
    assert source.read_patch_count == 250
    # **128 et non 130 depuis l'AC 7 de la story 5.20**: les deux repliques de
    # `lattice-008-008-008` sortent du jeu d'ajustement, le plancher d'encrage rendant
    # ce niveau indiscernable de ses voisins sur l'imprimante d'Egan. Le cardinal est
    # **derive** de la garde et non recopie -- recopier 128 ferait de ce test une
    # constante a maintenir a chaque revision du plancher.
    exclues = set(patch_values.ink_floor_lattice_value_ids())
    assert source.retained_patch_count == 130 - 2 * len(exclues)
    assert len(source.value_ids) == 65 - len(exclues)
    assert not exclues & set(source.value_ids)
    assert list(source.value_ids) == sorted(source.value_ids)

    # **La frontiere qui rend ce test discriminant**: le jeu tronque que le mutant lirait
    # est reellement different du jeu agrege. Sans ce volet, le test constaterait une egalite
    # vraie des deux facons -- exactement ce qui laissait `R05` en vie.
    retenues_dans_l_ordre_de_lecture = [
        value_id for value_id in ids
        if patch_values.lattice_saturation_8bit(lattice[value_id].rgb)
        <= patch_values.CALIBRATION_LATTICE_SATURATION_LIMIT_8BIT
        and not patch_values.is_below_ink_floor(lattice[value_id].rgb)]
    assert len(retenues_dans_l_ordre_de_lecture) == 130 - 2 * len(exclues)
    assert retenues_dans_l_ordre_de_lecture[:len(source.value_ids)] != \
        list(source.value_ids)

    # L'appariement valeur agregee -> reference, sur les 65 lignes.
    attendues = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in source.value_ids], dtype=np.float64)
    assert source.reference_bgr.shape == (65 - len(exclues), 3)
    assert np.abs(source.reference_bgr - attendues).max() < 1e-12

    # Et l'agregation reste juste sous cet ordre: les offsets opposes s'annulent toujours,
    # donc la mesure agregee est la mesure nominale. Sans ce volet, une fabrique entrelacee
    # qui aurait casse l'appariement des **signes** rendrait le test vert pour une mauvaise
    # raison.
    nominal = press(attendues)
    assert np.abs(source.measured_bgr - nominal).max() < 1e-12

    # Le masque neutre suit la meme voie, et il est non trivial: cinq neutres sur 65.
    assert list(source.neutral_mask) == [
        len(set(lattice[value_id].rgb)) == 1 for value_id in source.value_ids]
    assert int(source.neutral_mask.sum()) == (
        len(patch_values.CALIBRATION_LATTICE_LEVELS)
        - len(patch_values.ink_floor_lattice_value_ids())), (
        "un niveau neutre par niveau du treillis, moins ceux que le plancher d'encrage "
        "exclut du jeu d'ajustement depuis l'AC 7 de la story 5.20")


def test_le_masque_neutre_de_la_source_externe_est_derive_des_references():
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _lattice_measurement(press)
    # Forme nommee, meme raison (story 5.21): le cardinal du masque neutre attendu
    # ci-dessous retranche le plancher, ce que seule la politique affine fait.
    source = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0",
                                          correction_form_id=cc.CORRECTION_FORM_ID)
    lattice = {value.value_id: value for value in patch_values.calibration_lattice_values()}
    expected = [len(set(lattice[value_id].rgb)) == 1 for value_id in source.value_ids]
    assert list(source.neutral_mask) == expected
    # Le treillis contient exactement un neutre par niveau: cinq, dont aucun n'est
    # premier ni dernier par hasard -- la collection est distinguable.
    assert int(source.neutral_mask.sum()) == (
        len(patch_values.CALIBRATION_LATTICE_LEVELS)
        - len(patch_values.ink_floor_lattice_value_ids())), (
        "un niveau neutre par niveau du treillis, moins ceux que le plancher d'encrage "
        "exclut du jeu d'ajustement depuis l'AC 7 de la story 5.20")


def test_une_mesure_de_treillis_inconnue_est_refusee_et_jamais_ignoree():
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _lattice_measurement(press)
    # L'identifiant fautif est place **au milieu**: un refus qui ne regarderait que la
    # premiere mesure passerait.
    broken = list(ids)
    broken[len(broken) // 2] = "lattice-999-999-999"
    with pytest.raises(cc.UnknownLatticeValueError) as refus:
        cc.lattice_adjustment_source(measured, tuple(broken),
                                     source_page_id="calibration-0")
    assert "lattice-999-999-999" in str(refus.value)


def test_un_cardinal_incoherent_entre_identifiants_et_mesures_est_refuse():
    """La garde est une **egalite**, et elle est eprouvee dans les **deux** sens.

    **Mutant `R04`** de la campagne de la couche 1, mesure pour la premiere fois a la passe
    de correction du 2026-08-12: il remplace `len(ids) != len(measured)` par
    `len(ids) > len(measured)` et **survivait**. Le seul cas exerce etait `measured[:-1]`,
    donc *plus d'identifiants que de mesures* -- que l'inegalite stricte attrape encore.
    Le sens manquant est *plus de mesures que d'identifiants*, et c'est celui ou le mutant
    laisse passer.

    Ce que le sens manquant coute reellement, et c'est ce qui en fait une garde et non une
    verification de politesse: avec plus de mesures que d'identifiants, `zip(ids, retained)`
    tronque **en silence** sur le plus court. Les mesures excedentaires seraient donc
    ignorees sans un mot, et l'ajustement se ferait sur un sous-ensemble arbitraire de la
    page -- exactement la famille d'appariement silencieux que ce depot a payee cinq fois.
    """
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _lattice_measurement(press)

    # Sens 1: plus d'identifiants que de mesures.
    with pytest.raises(color_metrics.ColorMetricError) as trop_d_ids:
        cc.lattice_adjustment_source(measured[:-1], ids, source_page_id="calibration-0")
    assert "cardinalites incoherentes" in str(trop_d_ids.value)

    # Sens 2: plus de mesures que d'identifiants -- le sens que `R04` laissait passer.
    with pytest.raises(color_metrics.ColorMetricError) as trop_de_mesures:
        cc.lattice_adjustment_source(measured, tuple(ids)[:-1],
                                     source_page_id="calibration-0")
    message = str(trop_de_mesures.value)
    assert "cardinalites incoherentes" in message
    # Le refus **nomme les deux cardinaux**, sans quoi il ne dirait pas de quel cote
    # l'ecart se trouve -- et c'est la seule information qui aide a le corriger.
    assert str(len(ids) - 1) in message and str(len(measured)) in message, message
    assert "calibration-0" in message, message

    # Temoin positif: le couple coherent passe. Sans lui, une garde qui refuserait **tout**
    # cardinal satisferait les deux volets ci-dessus.
    cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0")


@pytest.mark.parametrize("form", [cc.CORRECTION_FORM_ID, cc.CORRECTION_FORM_LAB_ID])
def test_le_filtre_de_saturation_ameliore_la_correction_pour_les_deux_formes(form):
    """AC 4: le filtre est une **regle**, et voici son effet mesure.

    Le mecanisme reproduit ici est celui du terrain: la conversion CMJN **ecrase** au
    dela d'une amplitude de chroma, donc les sommets du treillis demandent a la
    correction de mapper des mesures confondues sur des references distinctes. Le
    residu mesure sur les pastilles temoins d'une planche d'images est le critere
    commun -- le residu sur le jeu d'ajustement lui-meme est structurellement
    incomparable entre deux jeux de cardinaux differents.
    """
    press = _press(0.93, (0.025, 0.024, 0.026), chroma_limit=0.20)
    measured, ids = _lattice_measurement(press)
    # Le jeu est construit **pour la forme qui l'ajustera** (`EPIC5-ARB-77`): sans cela
    # les deux defauts, celui de cette fonction et le `form` du parametrage, ne
    # s'accorderaient plus depuis la bascule de 5.21.
    filtered = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0",
                                            correction_form_id=form)
    lattice = {value.value_id: value for value in patch_values.calibration_lattice_values()}
    whole_ids, whole = cc.aggregate_by_value(measured, ids)
    whole_reference = np.asarray(
        [np.asarray(lattice[value_id].rgb[::-1], dtype=np.float64) / 255.0
         for value_id in whole_ids])
    whole_neutral = np.asarray([len(set(lattice[value_id].rgb)) == 1
                                for value_id in whole_ids], dtype=bool)

    witness_measured, witness_reference, _neutral = _adjustment_arrays(
        "patch-values-3", press)
    fit = cc.get_correction_form(form)
    with_filter = cc.residual_de76(
        cc.fit_from_external_source(filtered, correction_form_id=form),
        witness_measured, witness_reference)
    without = cc.residual_de76(fit(whole, whole_reference, whole_neutral),
                               witness_measured, witness_reference)
    assert with_filter < without, (form, with_filter, without)
    # Le gain n'est pas marginal: le filtre est ce qui empeche la correction d'etre
    # tiree par des couleurs inatteignables, pas un reglage fin.
    assert without - with_filter > 1.0, (form, with_filter, without)


# ---------------------------------------------------------------------------
# AC 5 : les sondes de luminance ne sont pas versees au jeu d'ajustement
# ---------------------------------------------------------------------------

def test_aucun_identifiant_de_sonde_d_ombre_dans_un_jeu_d_ajustement():
    """AC 5, frontiere **negative**: le grep doit rendre zero.

    Balaye les trois endroits ou un jeu d'ajustement se constitue: le treillis filtre,
    le jeu d'ajustement de chaque table enregistree, et la source externe construite
    par le module. Un seul de ces trois oublie suffirait a degrader la correction de
    4,66 a 4,81 dE76.
    """
    prefix = patch_values.SHADOW_PROBE_ID_PREFIX
    assert prefix and prefix != ""
    probes = patch_values.shadow_probe_value_ids()
    assert len(probes) == len(patch_values.SHADOW_PROBE_LEVELS_8BIT) == 8

    lattice_ids = [value.value_id
                   for value in patch_values.calibration_lattice_adjustment_values()]
    assert [value_id for value_id in lattice_ids if value_id.startswith(prefix)] == []
    for version in patch_values.known_versions():
        table = patch_values.get_patch_values_table(version)
        assert [value.value_id for value in table.adjustment_values()
                if value.value_id.startswith(prefix)] == [], version

    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _lattice_measurement(press)
    source = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0")
    assert [value_id for value_id in source.value_ids
            if value_id.startswith(prefix)] == []


def test_une_sonde_d_ombre_presentee_comme_ajustement_est_refusee():
    """Une garde qui **refuse**, pas un filtre que l'appelant doit se rappeler.

    La sonde fautive est placee ailleurs qu'en premiere position: une garde qui ne
    regarderait que le premier identifiant laisserait passer tous les autres cas.
    """
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _lattice_measurement(press)
    probe = patch_values.shadow_probe_value_ids()[3]
    contaminated = list(ids)
    contaminated[7] = probe
    with pytest.raises(patch_values.ShadowProbeInAdjustmentSetError) as refus:
        cc.lattice_adjustment_source(measured, tuple(contaminated),
                                     source_page_id="calibration-0")
    assert probe in str(refus.value)
    assert "4,66" in str(refus.value) or "4.66" in str(refus.value)


def test_le_plancher_d_ombre_est_mesure_et_laisse_deux_niveaux_exploitables():
    """Les 12 sondes retirees de l'AC 5, derivees et non recopiees.

    Huit niveaux, dont six a `<= 20` -- le plancher mesure --, donc 12 sondes sur 16 en
    double replicat: c'est exactement le compte que l'AC 5 annonce, et il se derive.
    """
    levels = patch_values.SHADOW_PROBE_LEVELS_8BIT
    floor = patch_values.SHADOW_FLOOR_8BIT
    below = [level for level in levels if level <= floor]
    above = [level for level in levels if level > floor]
    assert len(below) * 2 == 12
    assert above == [28, 36]


# ---------------------------------------------------------------------------
# AC 6 : patch-values-3, par reference et sans toucher aux deux premieres
# ---------------------------------------------------------------------------

def test_patch_values_3_porte_le_jeu_temoin_complet_et_rien_d_autre():
    table = patch_values.get_patch_values_table("patch-values-3")
    assert table.version == "patch-values-3"
    assert (table.color_space, table.white_point, table.bits_per_channel) == (
        "sRGB", "D65", 8)
    assert len(table.values) == 14
    assert [value.value_id for value in table.adjustment_values()] == [
        "neutral-020", "neutral-245", "neutral-065",
        "primary-red", "primary-green", "primary-blue"]
    assert [value.value_id for value in table.sentinel_values()] == [
        "sentinel-red-1", "sentinel-red-2", "sentinel-green-1", "sentinel-green-2",
        "sentinel-blue-1", "sentinel-blue-2", "sentinel-black-1", "sentinel-white-1"]
    # 14 valeurs en double replicat = 28 pastilles, soit 14 par cote.
    assert 2 * len(table.values) == 28


def test_aucune_secondaire_dans_le_jeu_temoin_de_la_v3():
    """AC 7, frontiere negative, dans la partie qui est **dans** ce perimetre.

    Les trois secondaires ne servaient qu'au re-ajustement d'une page deviante, que
    `EPIC5-ARB-57` supprime. Le preset temoin qui consomme cette table appartient a la
    tache 2 (`patch_presets`), hors de ce lot: ce test verrouille la **table**, et la
    frontiere sur le preset reste a poser par cette tache.
    """
    table = patch_values.get_patch_values_table("patch-values-3")
    roles = {value.role for value in table.values}
    assert patch_values.ROLE_SECONDARY not in roles
    assert not [value.value_id for value in table.values
                if value.value_id.startswith("secondary-")]


def test_neutral_065_est_repris_par_reference_et_jamais_recopie():
    """AC 6: **le meme objet**, pas le meme triplet.

    Recopier les triplets recreerait la double source de verite que les stories 4.7 et
    4.8 ont paye deux fois a eviter. `is` est donc l'assertion juste ici, et une
    egalite de valeur ne dirait rien.
    """
    v1 = patch_values.get_patch_values_table("patch-values-1")
    v2 = patch_values.get_patch_values_table("patch-values-2")
    v3 = patch_values.get_patch_values_table("patch-values-3")
    assert v3.get("neutral-065") is v1.get("neutral-065")
    assert "neutral-065" not in v2.value_ids()
    for value_id in ("neutral-020", "neutral-245", "primary-red", "primary-green",
                     "primary-blue"):
        assert v3.get(value_id) is v1.get(value_id), value_id
    for value in v3.sentinel_values():
        assert value is v2.get(value.value_id), value.value_id


def test_les_deux_premieres_versions_sont_intactes():
    """AC 6: les v1 et v2 restent **intactes**, cardinal et contenu.

    `test_patch_values.py` epingle deja la v1 valeur par valeur; ce test-ci verrouille
    ce que l'ajout d'une v3 pourrait deplacer sans que ce fichier-la le voie: les
    cardinaux et l'alias actif.
    """
    assert len(patch_values.get_patch_values_table("patch-values-1").values) == 12
    assert len(patch_values.get_patch_values_table("patch-values-2").values) == 18
    assert patch_values.ACTIVE_PATCH_VALUES_VERSION == "patch-values-2"
    assert patch_values.active_table() is patch_values.get_patch_values_table(
        "patch-values-2")


def test_une_table_ne_peut_pas_porter_une_valeur_de_treillis():
    lattice = patch_values.calibration_lattice_values()[0]
    with pytest.raises(patch_values.PatchValuesIntegrityError) as refus:
        patch_values.PatchValuesTable("patch-values-99", "sRGB", "D65", 8, (lattice,))
    assert patch_values.ROLE_CALIBRATION_LATTICE in str(refus.value)


# ---------------------------------------------------------------------------
# AC 8 : la garde de dispersion reste calculable -- **verifiee**, pas reecrite
# ---------------------------------------------------------------------------

def test_le_jeu_temoin_en_double_replicat_rend_une_dispersion_mesuree():
    """AC 8, verrou de non-regression. Le comportement est **deja** livre par 5.4b.

    Deux assertions, et la seconde est celle qui compte: un replicat unique rend `None`
    et **non** `0,0`. Zero est la valeur d'une page parfaite, donc l'afficher la ou rien
    n'a ete lu publie la meilleure lecture possible -- bloquant de la revue de 5.4b.
    """
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _witness_measurement(press)
    dispersion, detail = cc.replicate_dispersion(measured, ids)
    assert dispersion is not None and dispersion > 0.0
    assert len(detail) == 14

    single = measured[0::2]
    single_ids = ids[0::2]
    lonely, lonely_detail = cc.replicate_dispersion(single, single_ids)
    assert lonely is None
    assert lonely_detail == {}


# ---------------------------------------------------------------------------
# AC 9 : les chaines de sentinelles restent completes sur une planche d'images
# ---------------------------------------------------------------------------

def _witness_chains():
    return cc.sentinel_chains(patch_values.get_patch_values_table("patch-values-3"))


def test_le_jeu_temoin_porte_cinq_chaines_completes_avec_leurs_tetes():
    chains = _witness_chains()
    assert set(chains) == {"neutral-020", "neutral-245", "primary-red",
                           "primary-green", "primary-blue"}
    for head, chain in chains.items():
        assert chain[0] == head
        assert len(chain) >= 2, head


@pytest.mark.parametrize("axis", ["neutral-020", "neutral-245", "primary-red",
                                  "primary-green", "primary-blue"])
def test_aucun_axe_ne_rend_values_absent_sur_une_planche_d_images(axis):
    """AC 9, frontiere: **aucune** planche d'images ne perd un axe pour tete manquante.

    C'est le trou que la verification prealable de la story a trouve: les tetes des
    chaines noire et blanche sont `neutral-020` et `neutral-245`, les deux valeurs que
    `EPIC5-ARB-50` ecartait du jeu d'ajustement. Sans elles, `clipping_verdict` rend
    `REASON_VALUES_ABSENT` sur ces deux axes -- une valeur peut etre inutile pour un
    role et indispensable pour un autre.
    """
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _witness_measurement(press)
    noise = cc.measurement_noise_de76(measured, ids)
    assert np.isfinite(noise) and noise > 0.0
    verdicts = cc.clipping_verdict(measured, ids, _witness_chains(), noise)
    assert axis in verdicts
    assert verdicts[axis].get("reason") != cc.REASON_VALUES_ABSENT
    assert verdicts[axis]["clipped"] is not None


@pytest.mark.parametrize("head", ["neutral-020", "neutral-245", "primary-red",
                                  "primary-green", "primary-blue"])
def test_retirer_une_tete_rend_bien_values_absent_sur_son_axe(head):
    """Temoin negatif du test precedent: sans lui, il ne prouve rien.

    Un test qui n'observe jamais le motif qu'il exclut ne sait pas le reconnaitre. Ici
    la tete est retiree de la **mesure**, ce qui est exactement le cas d'une planche
    dont le preset ne la porte pas.
    """
    press = _press(0.93, (0.025, 0.024, 0.026))
    measured, ids = _witness_measurement(press, drop=head)
    noise = cc.measurement_noise_de76(measured, ids)
    verdicts = cc.clipping_verdict(measured, ids, _witness_chains(), noise)
    assert verdicts[head]["clipped"] is None
    assert verdicts[head]["reason"] == cc.REASON_VALUES_ABSENT


# ---------------------------------------------------------------------------
# AC 10 : la correction porte l'identifiant de sa source
# ---------------------------------------------------------------------------

#: La feuille de reference du tirage: c'est **le meme** couple imprimante+scanner qui
#: imprime la page de calibration et les planches d'images d'un lot. Un test qui
#: ajusterait la page de calibration sous une presse et les planches sous une autre
#: mesurerait une divergence qu'il a fabriquee lui-meme -- et c'est exactement l'erreur
#: qu'une premiere ecriture de ce fichier a commise.
_NOMINAL_GAIN, _NOMINAL_TINT = 0.930, (0.0250, 0.0240, 0.0260)
_NOMINAL_PRESS = _press(_NOMINAL_GAIN, _NOMINAL_TINT)

#: Une feuille qui **derive**: gain et teinte franchement autres. Choisie pour tomber
#: dans la fenetre utile de la garde -- son exces depasse le seuil enregistre alors que
#: son residu reste sous le plafond d'acceptation --, ce qui est la seule facon
#: d'observer un contournement qui produise une page exploitable.
#:
#: **Ce que cette fixture confirme, et ce qu'elle ne confirme pas** (majeur M4 de la
#: couche 1 de la revue, corrige a la passe de correction). Mesure de ce qu'elle produit
#: reellement: residu importe 3,77, residu **propre** 0,41, exces +3,36. Son residu propre
#: vaut donc 0,41 dE76 la ou la troisieme reserve du registre chiffre la fenetre sur un
#: residu propre de **~7,1** -- dix-sept fois plus. Elle confirme donc une fenetre
#: **large** (un exces de 3,36 laisse le residu importe a 3,77, loin du plafond de 8,0), et
#: l'annotation d'origine pretendait qu'elle confirmait l'etroite. Un banc de synthese ne
#: peut pas confirmer une mesure de terrain qu'il n'atteint pas.
#:
#: L'etroitesse de la fenetre est mesuree a part, sur un domaine **construit** dont le
#: residu propre est celui du terrain: voir
#: `test_la_fenetre_du_contournement_se_ferme_au_regime_de_residu_du_terrain`. Cette
#: fixture-ci garde son role, qui est d'observer un contournement exploitable -- il faut
#: bien un regime ou il en existe un.
_DEVIANT_PRESS = _press(0.900, (0.0300, 0.0200, 0.0200))

#: Regime de **terrain** de la troisieme reserve du registre de divergence: une page dont
#: le residu propre vaut ~7,1 dE76. Il ne s'obtient pas par une presse seule -- une presse
#: est une deformation systematique, que la correction propre de la page rattrape presque
#: entierement -- mais par une presse deviante **plus du bruit de mesure**, ce qui est
#: precisement ce qu'un tirage reel porte.
#:
#: Les trois nombres sont figes par la graine: c'est ce qui rend le regime **reproductible**
#: plutot qu'approche. Ils sont mesures dans le test qui les consomme, jamais recopies
#: ici -- un chiffre de commentaire est faux au premier changement de fabrique.
_FIELD_NOISE_SCALE = 0.028
_FIELD_NOISE_SEED = 3
_FIELD_PRESS = _press(0.900, (0.0300, 0.0200, 0.0200))


def _calibration_profile(press=_NOMINAL_PRESS, form: str = cc.CORRECTION_FORM_ID):
    """Ajuster la correction du lot sur la page de calibration, comme en production.

    La presse est un **parametre**: c'est ce qui garantit que la page de calibration et
    les planches du meme lot passent par la meme, et donc que toute divergence mesuree
    par un test vient de ce que le test a voulu faire diverger.

    **`form` gouverne les deux appels et non plus le seul ajustement** (story 5.21). Le
    jeu doit etre construit pour la forme qui l'ajustera (`EPIC5-ARB-77`), et depuis que
    les deux defauts ne pointent plus sur la meme forme, ne threader `form` que sur le
    second des deux appels leve `InkFloorPolicyMismatchError` -- ce que la bascule a
    effectivement produit sur quatorze tests de ce fichier, tous verts la veille.

    Le defaut reste la **forme affine nommee**: les regimes de divergence de ce fichier
    (seuils, residus de terrain, fenetre de contournement) sont mesures sous cette forme,
    et les redater sous la forme active serait une story de mesure, pas la bascule d'un
    defaut. La forme active a ses propres tests de bout en bout sur captures reelles.
    """
    measured, ids = _lattice_measurement(press)
    source = cc.lattice_adjustment_source(measured, ids, source_page_id="calibration-0",
                                          correction_form_id=form)
    return cc.fit_from_external_source(source, correction_form_id=form)


def test_les_deux_regimes_de_provenance_ecrivent_des_valeurs_differentes():
    """AC 10: distinguables au manifest, et le champ est present dans les **deux** cas.

    Un champ present d'un seul cote ne distingue rien: il faudrait deviner de l'autre,
    et deviner sur un manifest est ce que ce projet refuse partout ailleurs.
    """
    profile = _calibration_profile()
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_NOMINAL_PRESS)
    own = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
                            page_id="page-3")
    transported = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-3",
        imported_profile=profile, imported_source_page_id="calibration-0")

    assert own.correction_source == cc.CORRECTION_SOURCE_OWN_SHEET
    assert transported.correction_source == cc.CORRECTION_SOURCE_CALIBRATION_PAGE
    assert own.correction_source != transported.correction_source
    assert own.correction_source_page_id == "page-3"
    assert transported.correction_source_page_id == "calibration-0"

    for result in (own, transported):
        entry = cc.correction_provenance_summary(result)
        assert entry["correction_source"] in (cc.CORRECTION_SOURCE_OWN_SHEET,
                                              cc.CORRECTION_SOURCE_CALIBRATION_PAGE)
        assert entry["correction_source_page_id"]
        assert entry["correction_form_id"] in cc.CORRECTION_FORMS
    assert (cc.correction_provenance_summary(own)["correction_source"]
            != cc.correction_provenance_summary(transported)["correction_source"])


def test_la_provenance_survit_a_un_echec():
    """Un echec dont on ne sait pas d'ou venait la correction n'est pas relisable.

    Meme motif que la forme de correction et l'entree de seuils, portees sur un echec
    depuis la revue de 5.4a: c'est **precisement** sur un echec qu'on relit.
    """
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET)
    profile = _calibration_profile()
    failed = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600.5, page_id="page-3",
                               imported_profile=profile,
                               imported_source_page_id="calibration-0")
    assert failed.status == "failed"
    assert failed.failure_reason == cc.FAILURE_INVALID_DPI
    assert failed.correction_source == cc.CORRECTION_SOURCE_CALIBRATION_PAGE
    assert failed.correction_source_page_id == "calibration-0"


def test_la_provenance_tient_dans_le_schema_livre_par_5_7():
    """Les champs s'ajoutent sans revision de schema -- verifie, pas suppose.

    **Deux exceptions documentees** depuis la deuxieme passe de revue d'`EPIC5-ARB-78`
    (2026-08-14, finding basse priorite sur le schema): `not_applied_reason` et
    `distortion` sont desormais declares explicitement dans le schema, en plus d'etre
    couverts par `additionalProperties: true`. Ce n'est **pas** une collision de deux
    producteurs -- la these que la disjonction ci-dessous protege -- c'est le **meme**
    producteur (`correction_provenance_summary`) dont le schema documente enfin la
    forme, plutot que de laisser ces deux champs vivre uniquement sous
    `additionalProperties`. Les exclure explicitement de la disjonction, plutot que de
    retirer le test, garde la garantie pour tout champ **non** documente.
    """
    schema = json.loads(pathlib.Path(
        "src/mixed_media_utility/specs/project.schema.json").read_text(encoding="utf-8"))
    entry_schema = (schema["properties"]["reconstruction"]["properties"]
                    ["page_calibration_results"]["items"])
    assert entry_schema["additionalProperties"] is True
    declared = set(entry_schema["properties"])
    documente_par_provenance = {"not_applied_reason", "distortion"}
    assert documente_par_provenance <= declared, (
        "les deux exceptions doivent rester reellement declarees dans le schema, "
        "sinon cette liste devient perimee")
    profile = _calibration_profile()
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_NOMINAL_PRESS)
    result = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-3",
        imported_profile=profile, imported_source_page_id="calibration-0")
    entry = cc.correction_provenance_summary(result)
    # Aucun champ nouveau ne **redefinit** un champ declare par un AUTRE producteur:
    # une seconde definition de `status` ou de `clipping` serait deux verites. Les deux
    # exceptions ci-dessus sont retirees du test, pas le test lui-meme.
    assert declared.isdisjoint(set(entry) - documente_par_provenance)


# ---------------------------------------------------------------------------
# AC 11 et 12 : le cout du transport, et l'additivite
# ---------------------------------------------------------------------------

def _same_run_pages():
    """Les quatre feuilles du meme tirage, **et leur nom**, dans l'ordre declare."""
    return [(name, _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=_press(gain, tint)))
        for name, gain, tint in _SAME_RUN_SHEETS]


@pytest.mark.parametrize("form", [cc.CORRECTION_FORM_ID, cc.CORRECTION_FORM_LAB_ID])
def test_le_transport_entre_pages_du_meme_tirage_coute_peu_pour_les_deux_formes(form):
    """AC 11: test de **non-regression** sur le cout du transport.

    Ce que ce test peut mesurer et ce qu'il ne peut pas, dit franchement: les sept pages
    reelles du tirage a sentinelles **ne sont pas dans le depot** (le banc
    `divergence_threshold.py` les prend en argument, sous `srcs/`, hors du depot), donc
    les +0,01 et +0,02 dE76 publies ne sont pas re-mesurables ici. Ce qui l'est, et qui
    est la propriete dont la story a besoin: sur douze couples de feuilles d'un meme
    tirage, l'exces de residu reste **tres en dessous** du seuil enregistre pour les
    deux formes, et les deux formes sont du **meme ordre** -- donc aucune des deux ne
    rend le transport inexploitable, ce qui est ce que l'AC affirme.
    """
    pages = _same_run_pages()
    profiles = {}
    for name, page in pages:
        result = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                                   dpi=600, correction_form_id=form, page_id=name)
        assert result.status == "applied", (form, name)
        profiles[name] = result.profile

    guard = color_metrics.get_divergence_guard(color_metrics.ACTIVE_DIVERGENCE_GUARD_ID)
    excesses = []
    for source_name, _source_page in pages:
        for target_name, target_page in pages:
            if source_name == target_name:
                continue
            transported = cc.calibrate_page(
                target_page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
                correction_form_id=form, page_id=target_name,
                imported_profile=profiles[source_name],
                imported_source_page_id=source_name)
            assert transported.status == "applied", (form, source_name, target_name)
            excesses.append(transported.divergence.excess_residual_de76)
    assert len(excesses) == 12
    worst = max(excesses)
    assert worst < guard.max_excess_residual_de76, (form, worst)
    # Et l'exces reste du meme ordre que la distribution nulle enregistree: un exces
    # dix fois plus grand voudrait dire que la fabrique ne modelise plus un tirage.
    assert worst < 10.0 * guard.null_distribution_max_de76, (form, worst)


def test_la_page_de_calibration_transporte_sa_forme_aux_pages_du_lot():
    """La correction transportee est celle du lot, forme comprise.

    Verifie sur la forme Lab: une page corrigee depuis la page de calibration porte
    l'identifiant de la forme **du profil importe**, et non le defaut de la fonction.
    Sans cela, le manifest annoncerait la forme en vigueur pour une correction Lab.
    """
    profile = _calibration_profile(form=cc.CORRECTION_FORM_LAB_ID)
    assert profile.correction_id == cc.CORRECTION_FORM_LAB_ID
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_NOMINAL_PRESS)
    result = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-2",
        imported_profile=profile, imported_source_page_id="calibration-0",
        divergence_bypass=True)
    assert result.correction_form_id == cc.CORRECTION_FORM_LAB_ID
    assert cc.correction_provenance_summary(result)["correction_form_id"] == (
        cc.CORRECTION_FORM_LAB_ID)


def test_additivite_le_regime_en_vigueur_ne_gagne_aucun_champ_de_manifest():
    """AC 12: un lot sous la forme en vigueur, avec les pastilles de sa feuille.

    La forme executable de « manifest identique octet a octet »: le producteur reel des
    entrees de `page_calibration_results` rend **exactement** les deux memes cles
    qu'avant cette story tant qu'aucune provenance ne lui est passee. Le regime nouveau
    est donc **additif**: il ne s'obtient qu'en le demandant.
    """
    from mixed_media_utility.io import scan_manifest

    slots = [{"slot_index": 0, "synthetic": False}, {"slot_index": 1, "synthetic": False}]
    payloads = (
        {"page_index": 0, "slots": [{"slot_index": 0}]},
        {"page_index": 1, "slots": [{"slot_index": 1}]},
    )
    entries = scan_manifest._build_calibration_results(
        slots, page_payloads=payloads)
    assert [sorted(entry) for entry in entries] == [
        ["page_index", "status"], ["page_index", "status"]]
    assert [entry["page_index"] for entry in entries] == [0, 1]
    # `EPIC5-ARB-69`: sans resultat de calibration, une page se declare `not_applied` et
    # ne peut plus rien heriter -- la fonction ne recoit meme plus le statut du lot.
    assert [entry["status"] for entry in entries] == ["not_applied", "not_applied"]


# ---------------------------------------------------------------------------
# AC 13 a 16 : la garde de divergence
# ---------------------------------------------------------------------------

def test_le_seuil_est_enregistre_versionne_et_porte_ses_reserves():
    """AC 14: la constante porte un identifiant, sa mesure et ses deux reserves.

    Les reserves sont **dans le code** et pas seulement dans la story, parce qu'une
    reserve rangee dans un document se perd a la premiere reprise. Ce test est ce qui
    les y maintient.
    """
    guard = color_metrics.get_divergence_guard("color-divergence-1")
    assert color_metrics.ACTIVE_DIVERGENCE_GUARD_ID == "color-divergence-1"
    assert guard.max_excess_residual_de76 == 1.0
    assert guard.null_distribution_pairs == 42
    assert guard.null_distribution_max_de76 == 0.358
    assert guard.max_excess_residual_de76 > guard.null_distribution_max_de76
    joined = " ".join(guard.reservations).lower()
    assert "un seul tirage" in joined
    assert "aucune page divergente" in joined
    with pytest.raises(color_metrics.UnknownDivergenceGuardError):
        color_metrics.get_divergence_guard("color-divergence-2")


def test_un_seuil_sous_la_distribution_nulle_est_refuse_a_la_construction():
    """La seule facon de rendre la garde structurellement fausse, fermee a la source."""
    with pytest.raises(ValueError) as refus:
        color_metrics.DivergenceGuard(
            divergence_id="color-divergence-faux", max_excess_residual_de76=0.2,
            null_distribution_max_de76=0.358, null_distribution_pairs=42,
            reservations=("mesure sur un seul tirage",))
    assert "distribution nulle" in str(refus.value)
    with pytest.raises(ValueError):
        color_metrics.DivergenceGuard(
            divergence_id="color-divergence-muet", max_excess_residual_de76=1.0,
            null_distribution_max_de76=0.358, null_distribution_pairs=42,
            reservations=())


def test_le_seuil_est_lu_au_registre_et_non_pose_en_litteral(monkeypatch):
    """AC 14: interdiction du litteral, verifiee par le **comportement**.

    Un test textuel (« le mot 1.0 n'apparait pas ») serait contournable et fragile;
    celui-ci substitue une entree de registre plus permissive et exige que le verdict
    suive. Si la valeur etait ecrite au point d'usage, la substitution n'aurait aucun
    effet et le test tomberait.
    """
    profile = _calibration_profile()
    deviant = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=_DEVIANT_PRESS)
    refused = cc.calibrate_page(
        deviant, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id="page-7", imported_profile=profile,
        imported_source_page_id="calibration-0")
    # **AMENDE PAR LA STORY 5.23, et la propriete protegee est intacte.** Ce test verifie
    # que le seuil vient du **registre** et non d'un litteral -- une substitution de
    # registre doit changer le verdict. Ce qui a change est la **consequence** du verdict:
    # `EPIC5-ARB-82` decision 1 retire a la divergence tout pouvoir de refus, donc la page
    # est desormais corrigee dans les deux regimes et l'ancienne assertion
    # (`not_applied_reason == NOT_APPLIED_PAGE_DIVERGES`) n'a plus aucun domaine.
    #
    # L'assertion est deplacee sur `divergence.diverges`, qui est **la** grandeur que la
    # substitution de registre doit faire basculer. Elle est plus proche du fait mesure,
    # donc plus forte: l'ancienne pouvait rester verte si le refus venait d'ailleurs.
    assert refused.divergence.diverges is True
    assert refused.divergence.threshold_de76 == 1.0

    permissive = color_metrics.DivergenceGuard(
        divergence_id="color-divergence-1", max_excess_residual_de76=40.0,
        null_distribution_max_de76=0.358, null_distribution_pairs=42,
        reservations=("registre substitue par le test",))
    monkeypatch.setattr(color_metrics, "DIVERGENCE_REGISTRY",
                        MappingProxyType({"color-divergence-1": permissive}))
    tolerated = cc.calibrate_page(
        deviant, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id="page-7", imported_profile=profile,
        imported_source_page_id="calibration-0")
    assert tolerated.divergence.diverges is False
    assert tolerated.divergence.threshold_de76 == 40.0
    # Et dans les **deux** regimes la page est corrigee: c'est la bascule d'`EPIC5-ARB-82`,
    # epinglee ici parce que c'est le seul test du fichier qui tienne les deux cotes du
    # seuil sur la meme page. Sans cette paire, un retour au refus passerait.
    assert refused.status == "applied" and refused.profile is not None
    assert tolerated.status == "applied" and tolerated.profile is not None


def test_les_motifs_d_echec_de_la_couleur_sont_distincts_deux_a_deux():
    """Un motif nouveau qui reprend la valeur d'un motif existant est **pire** qu'absent.

    Trouve par la campagne de mutation (`F17`): donner a `FAILURE_PAGE_DIVERGES` la
    valeur de `FAILURE_PATCHES_NOT_FOUND` laissait les 273 tests verts -- chaque
    assertion comparait la constante a elle-meme. Un vocabulaire ferme dont deux mots
    sont le meme mot n'est pas ferme, il est ambigu: le manifest annoncerait « pastilles
    introuvables » pour une page qui derive, donc enverrait rescanner en croyant a un
    probleme de geometrie.
    """
    assert cc.FAILURE_PAGE_DIVERGES == "page_diverges_from_calibration_page"
    motifs = [
        cc.FAILURE_PATCHES_NOT_FOUND, cc.FAILURE_PATCHES_OUT_OF_RANGE,
        cc.FAILURE_REPLICATE_DISPERSION, cc.FAILURE_UNKNOWN_PATCH_PRESET,
        cc.FAILURE_UNKNOWN_VALUES_VERSION, cc.FAILURE_UNKNOWN_GAMUT_MAP,
        cc.FAILURE_PLACEMENT_UNDEFINED, cc.FAILURE_UNDERDETERMINED_ADJUSTMENT,
        cc.FAILURE_INVALID_DPI, cc.FAILURE_PAGE_DIVERGES,
        cc.FAILURE_NOT_THREE_CHANNELS,
    ]
    assert len(set(motifs)) == len(motifs), sorted(motifs)
    # Et les deux motifs de la garde de divergence ne se confondent pas non plus avec
    # les motifs de non-mesurabilite, qui ne sont pas des echecs.
    assert cc.REASON_DIVERGENCE_NOT_COMPUTABLE not in motifs
    assert cc.REASON_DIVERGENCE_NOT_COMPUTABLE == "divergence_excess_not_computable"


def test_les_deux_provenances_sont_epinglees_valeur_par_valeur():
    """Trouve par la campagne (`G01`): permuter les deux valeurs restait invisible.

    Une provenance permutee est le pire cas possible pour cette AC: le champ est present,
    il porte deux valeurs differentes dans les deux regimes, et il **dit le contraire de
    la verite**. Aucune assertion comparant la constante a elle-meme ne peut le voir.
    """
    assert cc.CORRECTION_SOURCE_OWN_SHEET == "own_sheet_patches"
    assert cc.CORRECTION_SOURCE_CALIBRATION_PAGE == "lot_calibration_page"


def test_le_residu_est_une_moyenne_ecretee_et_pas_autre_chose():
    """La grandeur de la statistique de divergence, epinglee par le calcul a la main.

    Trouve par la campagne (`F14`, `F15`): remplacer la moyenne par un maximum, ou
    supprimer l'ecretage a [0, 1], laissait tous les autres tests verts -- ils
    comparaient des residus entre eux, donc toute grandeur monotone passait. Or le seuil
    de divergence est **derive** d'une distribution de moyennes mesurees par le banc: le
    comparer a un maximum comparerait deux grandeurs differentes, ce qui est exactement le
    bloquant B2 de la revue du 2026-08-11 (dispersion contre bruit median).

    L'ecretage a [0, 1] est celui d'`EPIC5-ARB-30` et il est **avant** la mesure: un
    residu calcule sur des valeurs hors bornes mesurerait un pixel qui n'existe pas.
    """
    measured = np.array([[0.20, 0.50, 0.80], [0.10, 0.12, 0.11], [0.60, 0.30, 0.40]])
    reference = np.array([[0.22, 0.48, 0.79], [0.10, 0.12, 0.11], [0.50, 0.35, 0.45]])
    identity = cc.LabCorrectionProfile(
        lightness_slope=1.0, lightness_offset=0.0,
        chroma_matrix=np.eye(2), chroma_offset=np.zeros(2))
    per_value = de76(cc.oetf(np.clip(cc.eotf(measured), 0.0, 1.0)), reference)
    assert per_value.max() > 1.5 * per_value.mean(), (
        "le jeu ne discrimine plus moyenne et maximum")
    assert cc.residual_de76(identity, measured, reference) == pytest.approx(
        float(per_value.mean()), abs=1e-9)

    # Un profil qui pousse hors bornes: sans ecretage, le residu porterait sur des
    # valeurs impossibles. La clarte est poussee au-dela de 100, donc la lumiere
    # au-dela de 1.
    overshoot = cc.LabCorrectionProfile(
        lightness_slope=1.0, lightness_offset=40.0,
        chroma_matrix=np.eye(2), chroma_offset=np.zeros(2))
    clipped = cc.oetf(np.clip(overshoot.apply_linear(cc.eotf(measured)), 0.0, 1.0))
    unclipped = cc.oetf(overshoot.apply_linear(cc.eotf(measured)))
    assert np.abs(clipped - unclipped).max() > 1e-6, (
        "le profil ne pousse plus hors bornes: le jeu ne discrimine plus l'ecretage")
    assert cc.residual_de76(overshoot, measured, reference) == pytest.approx(
        float(de76(clipped, reference).mean()), abs=1e-9)


def test_la_frontiere_du_seuil_est_stricte(monkeypatch):
    """Un exces **exactement egal** a la valeur enregistree ne refuse pas la page.

    Trouve par la campagne (`F03`): remplacer `>` par `>=` n'etait distingue par aucun
    test, l'egalite exacte etant de mesure nulle sur des flottants. Ce test la construit:
    il mesure l'exces d'une page deviante, puis substitue une entree de registre dont la
    valeur enregistree **est** cet exces. Le sens de la frontiere n'est pas indifferent:
    la valeur retenue est pres de trois fois le pire exces observe, donc une page qui
    l'atteint exactement est deja tres loin dans la queue -- et la regle du depot est
    qu'un refus se declenche au **depassement**, comme la garde de dispersion
    (`dispersion > MAX_REPLICATE_DISPERSION_DE76`).
    """
    profile = _calibration_profile()
    deviant = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                        distort=_DEVIANT_PRESS)
    arguments = dict(template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
                     page_id="page-8", imported_profile=profile,
                     imported_source_page_id="calibration-0")
    refused = cc.calibrate_page(deviant, **arguments)
    excess = refused.divergence.excess_residual_de76
    # **AMENDE PAR LA STORY 5.23**: la frontiere stricte porte toujours, mais sur le
    # **verdict mesure** et non plus sur un refus qui n'existe plus (`EPIC5-ARB-82`
    # decision 1). Le mutant que ce test tue est inchange -- `>` en `>=` dans
    # `assess_divergence` -- et il est meme mieux cible qu'avant: l'ancienne assertion
    # passait par deux niveaux d'indirection (la garde, puis la branche de refus), donc un
    # mutant de la branche l'aurait tuee aussi.
    assert refused.divergence.diverges is True

    exact = color_metrics.DivergenceGuard(
        divergence_id="color-divergence-1", max_excess_residual_de76=excess,
        null_distribution_max_de76=0.358, null_distribution_pairs=42,
        reservations=("valeur posee a l'exces mesure, pour exercer la frontiere",))
    monkeypatch.setattr(color_metrics, "DIVERGENCE_REGISTRY",
                        MappingProxyType({"color-divergence-1": exact}))
    at_the_edge = cc.calibrate_page(deviant, **arguments)
    assert at_the_edge.divergence.threshold_de76 == excess
    assert at_the_edge.divergence.diverges is False


def test_une_page_qui_derive_est_corrigee_comme_les_autres_et_le_verdict_nomme_la_page():
    """AC 3 de 5.23: la divergence **mesure** la page, elle ne lui retire plus rien.

    La page deviante est placee **au milieu** de la collection: une garde qui jugerait le
    lot des la premiere page divergente, ou qui ne regarderait que la premiere page, ne
    survit pas a cet ordre. Cette propriete-la est celle de 5.16 et elle est intacte.

    **AMENDE PAR LA STORY 5.23, et c'est la bascule elle-meme** (`EPIC5-ARB-82`
    decision 1). La redaction precedente s'appelait `..._n_est_pas_corrigee_...` et
    exigeait `profile is None` sur la page deviante: c'etait la specification que cette
    story existe pour retirer. Mesure sur le lot reel `chendj-mat` le 2026-08-17: ce
    regime-la faisait sortir les deux planches d'Egan non corrigees pour un exces de
    +2,13 et +2,50 dE76, alors que la correction refusee divise par 2,7 a 3,3 l'ecart au
    rush d'origine.

    Ce qui est exige a la place n'est pas plus faible: la page deviante est **corrigee**
    comme les deux autres, son verdict de divergence est toujours mesure et publie, et il
    nomme toujours **cette** page et aucune autre. Le nom de la fonction suit, faute de
    quoi le fichier garderait un test dont le titre dit le contraire de ce qu'il verifie.
    """
    profile = _calibration_profile()
    lot = [
        ("page-1", _NOMINAL_PRESS),
        ("page-2", _DEVIANT_PRESS),
        ("page-3", _press(0.929, (0.0251, 0.0241, 0.0259))),
    ]
    results = {}
    for name, sheet in lot:
        page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                         distort=sheet)
        results[name] = cc.calibrate_page(
            page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id=name,
            imported_profile=profile, imported_source_page_id="calibration-0")

    # La page deviante l'est **reellement** -- sans cela le test confirmerait la bascule
    # sur une page qui ne diverge pas, c'est-a-dire sur rien.
    assert results["page-2"].divergence.diverges is True
    assert results["page-2"].divergence.excess_residual_de76 > (
        cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID).max_excess_residual_de76)
    # Et elle est corrigee quand meme: statut `applied`, profil retenu, aucun motif de
    # non-application. **La cle d'echec reste absente**, et pas seulement d'une autre
    # valeur: un lecteur qui filtre les pages en panne le fait sur la presence du champ.
    assert results["page-2"].status == "applied"
    assert results["page-2"].not_applied_reason is None
    assert results["page-2"].failure_reason is None
    assert results["page-2"].profile is not None
    # Le lot reste exploitable pour ses autres pages, avant **et** apres la deviante.
    assert results["page-1"].status == "applied"
    assert results["page-3"].status == "applied"
    assert results["page-1"].failure_reason is None
    assert results["page-3"].failure_reason is None
    # Le verdict porte toujours **la page** et jamais le lot (`EPIC5-ARB-57`): il est lu
    # sur l'objet de divergence, la ou il vivait auparavant dans un message de refus.
    assert results["page-2"].divergence.page_id == "page-2"
    assert results["page-1"].divergence.page_id == "page-1"


def test_la_divergence_ne_produit_plus_aucun_message_ni_aucun_refus():
    """**Ce test remplace `test_le_message_de_refus_porte_les_trois_nombres_et_les_deux_gestes`.**

    L'ancien exigeait que la branche de refus de divergence produise un message portant
    trois nombres et le geste de contournement. Cette branche n'existe plus
    (`EPIC5-ARB-82` decision 1) et `divergence_warning_message` a ete retiree avec elle:
    un message qu'aucun chemin ne produit ne se relit nulle part, il se maintient et
    vieillit pour rien.

    **La propriete n'est pas perdue, elle a demenage avec la grandeur.** Les trois nombres
    exiges par l'AC 4 de 5.23 -- ecart mesure, seuil, identifiant de registre -- sont
    desormais ceux de `raw_divergence_warning_message`, et ils sont epingles dans la suite
    du module qui la porte (`tests/unit/test_divergence_par_defaut.py`).

    Ce qui reste ici est la **frontiere negative**, qui ne peut vivre que dans ce fichier:
    une page qui diverge franchement ne porte plus ni motif de non-application, ni message,
    et la fonction retiree ne peut pas revenir sans que ce test le dise.
    """
    profile = _calibration_profile()
    deviant = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=_DEVIANT_PRESS)
    result = cc.calibrate_page(
        deviant, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id="page-5", imported_profile=profile,
        imported_source_page_id="calibration-0")
    # Le domaine d'activation est verifie avant la frontiere: sans lui, ce test serait
    # vert sur une page qui ne diverge pas, donc vert pour rien.
    assert result.divergence.diverges is True
    assert result.not_applied_reason is None
    assert result.failure_reason is None
    assert result.failure_message is None
    assert result.status == "applied"
    assert not hasattr(cc, "divergence_warning_message"), (
        "la fonction de message de refus de divergence est revenue: elle n'a aucun "
        "producteur, donc son message ne serait lu par personne")


@pytest.mark.parametrize("word", ["seuil", "tolerance", "--seuil", "tolérance"])
def test_aucun_message_ni_aucun_drapeau_de_divergence_n_invite_a_regler_un_nombre(word):
    """Frontiere negative de l'AC 16 de 5.16, **conservee et elargie** par l'AC 5 de 5.23.

    Ce test balayait le message de `divergence_warning_message`, retiree par cette story.
    Il est re-pointe sur le message qui l'a remplacee et sur les **deux** drapeaux que la
    commande expose desormais: une option qui s'appellerait `--seuil-de-divergence`
    reintroduirait exactement l'invitation que ces deux AC interdisent, quel que soit le
    message qu'elle accompagne.
    """
    assessment = cc.RawDivergenceAssessment(
        page_id="page-4", source_page_id="calibration-0",
        divergence_id="color-divergence-2", threshold_de76=5.0,
        mean_raw_de76=7.3, paired_value_ids=("primary-red", "primary-green"),
        exceeds=True)
    assert word not in cc.raw_divergence_warning_message(assessment).lower()
    assert word not in cc.DIVERGENCE_BYPASS_FLAG.lower()
    assert word not in cc.RAW_OUTPUT_FLAG.lower()


def test_le_contournement_est_explicite_et_inscrit_au_manifest():
    """AC 15: explicite, jamais un repli automatique, et **trace** au manifest.

    Sans la trace, une page corrigee apres contournement et une page corrigee
    normalement seraient indistinguables a posteriori -- c'est-a-dire exactement le
    defaut que la garde existe pour eviter.
    """
    profile = _calibration_profile()
    deviant = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=_DEVIANT_PRESS)
    arguments = dict(template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
                     page_id="page-6", imported_profile=profile,
                     imported_source_page_id="calibration-0")
    refused = cc.calibrate_page(deviant, **arguments)
    bypassed = cc.calibrate_page(deviant, divergence_bypass=True, **arguments)

    # **AMENDE PAR LA STORY 5.23**: les deux appels rendent desormais une page corrigee,
    # le drapeau n'ouvrant plus rien qui ne soit deja ouvert (`EPIC5-ARB-82` decision 1).
    # Ce qui subsiste -- et c'est ce que l'AC 15 de 5.16 exige encore -- est la **trace**:
    # une page corrigee apres un geste explicite et une page corrigee sans lui restent
    # distinguables a posteriori au manifest, sinon la garde d'`io/scan_manifest` qui
    # confronte le constat a la demande n'aurait plus rien a confronter.
    assert refused.not_applied_reason is None
    assert bypassed.not_applied_reason is None
    assert refused.status == "applied"
    assert refused.profile is profile
    assert bypassed.status == "applied"
    assert bypassed.profile is profile
    assert bypassed.divergence.bypassed is True
    assert refused.divergence.bypassed is False
    entry = cc.correction_provenance_summary(bypassed)["divergence"]
    assert entry["bypassed"] is True
    assert entry["diverges"] is True
    assert entry["excess_residual_de76"] == bypassed.divergence.excess_residual_de76
    assert entry["guard_id"] == "color-divergence-1"
    # Une page **non** deviante contournee n'est pas marquee contournee: le drapeau
    # decrit ce qui s'est passe, pas ce qui a ete demande.
    nominal = _synthetic_rectified_page(
        template_id=TEMPLATE, preset_id=PRESET, distort=_NOMINAL_PRESS)
    calm = cc.calibrate_page(nominal, divergence_bypass=True,
                             **{**arguments, "page_id": "page-1"})
    assert calm.divergence.bypassed is False


def test_une_page_contournee_n_est_jamais_re_ajustee_sur_ses_propres_pastilles():
    """`EPIC5-ARB-57`, le point dur: il n'y a **pas** de troisieme regime.

    La page contournee porte le meme identifiant de forme **et les memes parametres**
    que la page de calibration. Le test compare les tableaux octet a octet et verifie
    en plus que la correction propre de la page serait **differente** -- sans quoi
    l'egalite ci-dessus serait vraie par accident.
    """
    profile = _calibration_profile()
    deviant = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                        distort=_DEVIANT_PRESS)
    bypassed = cc.calibrate_page(
        deviant, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600,
        page_id="page-6", imported_profile=profile,
        imported_source_page_id="calibration-0", divergence_bypass=True)
    assert bypassed.profile is profile
    assert bypassed.correction_form_id == profile.correction_id

    # La correction propre est ajustee sous **la meme forme** que la correction importee
    # (story 5.21): comparer octet a octet une correction affine a une correction courbe
    # ne dirait rien -- les deux n'ont meme pas les memes champs -- et le contraste que ce
    # test cherche est celui des **parametres**, a forme constante.
    own = cc.calibrate_page(deviant, template_id=TEMPLATE, patch_preset_id=PRESET,
                            dpi=600, page_id="page-6",
                            correction_form_id=cc.CORRECTION_FORM_ID)
    assert own.profile.stage_a.tobytes() != profile.stage_a.tobytes(), (
        "la correction propre de la page deviante est identique a celle de la page de "
        "calibration: la fabrique ne fait plus diverger la page")


def test_la_statistique_est_l_exces_de_residu_et_non_le_residu_brut():
    """AC 14: la statistique est `importe - propre`, et le retrait n'est pas decoratif.

    Une page dont le papier est bruyant a un residu propre eleve: sans le retrait, elle
    depasserait n'importe quel seuil pour une raison qui n'est pas la divergence. Le
    test le montre en confrontant les trois nombres entre eux.
    """
    profile = _calibration_profile()
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_NOMINAL_PRESS)
    result = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-1",
        imported_profile=profile, imported_source_page_id="calibration-0")
    assessment = result.divergence
    assert assessment.excess_residual_de76 == pytest.approx(
        assessment.imported_residual_de76 - assessment.own_residual_de76, abs=1e-12)
    assert assessment.own_residual_de76 > 0.0
    assert assessment.page_id == "page-1"
    assert assessment.source_page_id == "calibration-0"


def test_le_seuil_de_divergence_est_mesure_a_sa_valeur_exacte(monkeypatch):
    """Le verdict est **strict**: egal au seuil ne diverge pas. Finding de la couche 2.

    Le seuil n'etait mesure nulle part pres de sa valeur -- la fixture de divergence porte
    un exces de plusieurs dE76 pour un seuil de 1,0 --, donc la mutation `>` en `>=`
    n'etait couverte par rien. Une garde dont on ne connait pas le comportement **a** sa
    frontiere est une garde dont la valeur est decorative.

    Le montage porte sur les **residus** et laisse le seuil du registre intact -- c'est le
    seuil livre, `1,0` dE76, qui est eprouve, et non une valeur de test. Les deux residus
    sont substitues pour que l'exces vaille exactement le seuil: un ecart flottant de
    l'ordre de `1e-16` suffirait a rendre la mesure sans rapport avec la frontiere.
    """
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    propre = cc.fit_correction(measured, reference, neutral)
    seuil = cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID
                                    ).max_excess_residual_de76

    def _verdict(exces: float):
        # Deux appels, dans cet ordre: le residu **importe** puis le residu **propre**.
        # La soustraction est exacte sur ces deux valeurs, donc l'exces obtenu est bien
        # celui qu'on demande et non celui qu'un arrondi produit.
        residus = iter([2.0 + exces, 2.0])
        monkeypatch.setattr(cc, "residual_de76", lambda *_a, **_k: next(residus))
        return cc.assess_divergence(
            measured, reference, neutral, propre,
            page_id="page-frontiere", source_page_id="calibration-0",
            correction_form_id=cc.CORRECTION_FORM_ID)

    egal = _verdict(seuil)
    assert egal.threshold_de76 == seuil
    assert egal.excess_residual_de76 == seuil, (
        "le montage doit produire une egalite exacte, sinon il ne mesure pas la frontiere")
    assert egal.diverges is False, "egal au seuil ne diverge pas: la comparaison est stricte"

    # L'autre bout, qui rend l'assertion precedente non vide: le plus petit ecart
    # representable au-dessus du seuil fait mordre la garde. Sans lui, une garde qui
    # rendrait toujours `False` passerait.
    # `1e-12` et non le plus petit flottant suivant: la somme `2.0 + seuil` reabsorberait
    # un ecart d'un ulp, et un test qui croit mesurer la frontiere sans la franchir ne
    # mesure rien. Douze ordres de grandeur sous le seuil restent sa frontiere.
    dessus = _verdict(seuil + 1e-12)
    assert dessus.excess_residual_de76 > seuil
    assert dessus.diverges is True


def test_le_silence_de_l_appelant_ajuste_le_profil_propre_a_la_forme_active():
    """AC 2 de la story 5.21, sur `assess_divergence` -- mesure, plus affirmee.

    Trou de couverture mesure le 2026-08-19 par injection ciblee (tache 7 de 5.21) : le
    mutant qui remet le defaut de `correction_form_id` sur `CORRECTION_FORM_ID`
    **survivait** au lot entier de la story. La cause est visible dans ce fichier meme :
    **tous** les appels existants a `assess_divergence` nomment la forme, aucun ne laisse
    le defaut decider -- donc aucun ne le mesure.

    Ce que le defaut decide ici n'est pas un enregistrement mais un **calcul** : la forme
    sous laquelle le profil *propre* de la page est ajuste, donc le troisieme nombre du
    refus et l'exces lui-meme. Les trois formes du registre rendent trois residus propres
    franchement distincts sur ce jeu (mesure du 2026-08-19, `patch-values-2`, presse
    0,93/(0,030, 0,020, 0,020)) : forme active 0,590 dE76, forme affine 4,9e-14 dE76,
    forme Lab 3,380 dE76. Un exces calcule contre un profil propre d'une autre famille que
    le profil importe ne mesure plus une divergence.
    """
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    importe = cc.fit_correction(measured, reference, neutral)

    def _verdict(**forme):
        return cc.assess_divergence(measured, reference, neutral, importe,
                                    page_id="page-muette", source_page_id="calibration-0",
                                    **forme)

    muet = _verdict()
    active = _verdict(correction_form_id=cc.ACTIVE_CORRECTION_FORM_ID)
    affine = _verdict(correction_form_id=cc.CORRECTION_FORM_ID)

    # Le temoin qui rend l'assertion suivante non vide : les deux formes ne rendent pas
    # le meme nombre sur ce jeu, donc « le silence suit la forme active » y a un domaine.
    assert affine.own_residual_de76 == pytest.approx(0.0, abs=1e-9)
    assert active.own_residual_de76 > 0.1, active.own_residual_de76

    assert muet.own_residual_de76 == pytest.approx(active.own_residual_de76, rel=1e-12)
    assert muet.excess_residual_de76 == pytest.approx(active.excess_residual_de76,
                                                     rel=1e-12)
    assert muet.own_residual_de76 != pytest.approx(affine.own_residual_de76, abs=1e-6)


def test_un_exces_non_calculable_ne_refuse_pas_et_le_dit():
    """`REASON_DIVERGENCE_NOT_COMPUTABLE`: pas un verdict de non-divergence.

    Meme regle que la garde de dispersion et que le verdict d'ecretage sans bruit
    estimable: la garde porte sur un exces **mesure et trop grand**, jamais sur
    l'absence de mesure. Poser `diverges = False` ici publierait la meilleure lecture
    possible la ou rien n'a ete mesure.
    """
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    profile = cc.fit_correction(measured, reference, neutral)
    # Un seul point: aucune forme ne peut ajuster la correction propre de la page. La
    # forme est **nommee** et suit celle du profil importe (story 5.21) -- le test resterait
    # vert sans cela, mais pour une raison qu'il n'a pas choisie: c'est la forme active qui
    # echouerait a s'ajuster, pas celle du profil qu'on lui donne.
    lonely = slice(1, 2)
    assessment = cc.assess_divergence(
        measured[lonely], reference[lonely], neutral[lonely], profile,
        page_id="page-9", source_page_id="calibration-0",
        correction_form_id=cc.CORRECTION_FORM_ID)
    assert assessment.diverges is None
    assert assessment.own_residual_de76 is None
    assert assessment.excess_residual_de76 is None
    assert assessment.reason == cc.REASON_DIVERGENCE_NOT_COMPUTABLE
    assert assessment.imported_residual_de76 > 0.0
    # **La derniere assertion, sur le message, a ete retiree par la story 5.23**: elle
    # portait sur `divergence_warning_message`, supprimee avec la branche de refus qui
    # etait son seul producteur. Ce qu'elle protegeait -- « non calculable » plutot qu'un
    # nombre invente -- vit desormais dans le type lui-meme, aux trois assertions
    # ci-dessus (`None` et non `0.0`), qui sont l'endroit ou la propriete est reellement
    # tenue: un message ne peut afficher que ce que l'objet porte.


def test_la_fenetre_du_contournement_se_ferme_au_regime_de_residu_du_terrain():
    """**Majeur M4**: la fenetre est mesuree la ou le terrain la place, pas la ou le banc.

    La troisieme reserve du registre enonce une borne **superieure** du domaine utile de la
    garde: « le residu propre d'une page vaut ~7,1 dE76 et le plafond d'acceptation 8,0,
    donc au-dela de ~0,9 dE76 d'exces une page echoue a l'acceptation pour son seul
    residu ». Aucun test ne l'eprouvait: la seule fixture de divergence a un residu propre
    de 0,41 dE76, donc elle confirme la fenetre **large** en pretendant confirmer
    l'etroite.

    Ce test construit le regime de la reserve -- presse deviante **plus** bruit de mesure,
    residu propre au niveau du terrain -- et mesure les deux bornes ensemble:

    * la borne **inferieure** mord: l'exces depasse le seuil enregistre, donc la garde
      refuse;
    * la borne **superieure** mord aussi: le residu importe passe **au-dessus** du plafond
      d'acceptation, donc le contournement ne produit pas une page exploitable. Le domaine
      utile est bien vide a ce regime, et c'est ce que la reserve annonce.

    Le contraste avec la fixture de synthese est verifie dans le meme test: c'est lui qui
    empeche de relire l'un des deux regimes comme l'autre.
    """
    imported = _calibration_profile()
    guard = cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID)
    plafond = color_metrics.get_color_acceptance(
        color_metrics.ACTIVE_COLOR_ACCEPTANCE_ID).max_mean_delta_e

    measured, reference, neutral = _adjustment_arrays("patch-values-2", _FIELD_PRESS)
    rng = np.random.default_rng(_FIELD_NOISE_SEED)
    bruite = np.clip(
        measured + rng.normal(0.0, _FIELD_NOISE_SCALE, measured.shape), 0.01, 1.0)
    # **La forme du profil propre suit celle du profil importe** (story 5.21): l'exces
    # est une soustraction entre deux residus, et la faire entre deux familles de
    # correction ne mesure plus une divergence mais l'ecart des deux formes. `imported`
    # vient de `_calibration_profile()`, donc de la forme affine.
    terrain = cc.assess_divergence(
        bruite, reference, neutral, imported, page_id="page-terrain",
        source_page_id="calibration-0",
        correction_form_id=cc.CORRECTION_FORM_ID)

    # Le regime **est** celui de la reserve: c'est cette assertion qui donne son sens aux
    # deux suivantes, et sans elle le test mesurerait un regime quelconque.
    assert 6.5 < terrain.own_residual_de76 < 7.8, terrain.own_residual_de76
    # Borne inferieure: la garde mord.
    assert terrain.excess_residual_de76 > guard.max_excess_residual_de76
    assert terrain.diverges is True
    # Borne superieure: le contournement ne rend pas une page exploitable a ce regime.
    assert terrain.imported_residual_de76 > plafond, terrain.imported_residual_de76

    # Contraste avec la fixture de synthese, au **meme** exces qualitatif: son residu
    # propre est dix fois plus bas, donc le contournement y produit une page acceptable.
    # Les deux regimes disent des choses differentes, et c'est le fond du majeur M4.
    synth_m, synth_r, synth_n = _adjustment_arrays("patch-values-2", _DEVIANT_PRESS)
    synthese = cc.assess_divergence(
        synth_m, synth_r, synth_n, imported, page_id="page-synthese",
        source_page_id="calibration-0",
        correction_form_id=cc.CORRECTION_FORM_ID)
    assert synthese.diverges is True
    assert synthese.own_residual_de76 < 1.0, synthese.own_residual_de76
    assert synthese.imported_residual_de76 < plafond
    assert terrain.own_residual_de76 > 10 * synthese.own_residual_de76


def test_le_registre_ne_garde_qu_une_borne_du_seuil_et_dit_laquelle():
    """**Mineur m4**: `__post_init__` verifie la borne inferieure, et elle seule.

    Ce n'est pas un oubli et le test le dit plutot que de le laisser deviner: la borne
    inferieure est **structurelle** -- un seuil sous la distribution nulle rend la garde
    fausse quelle que soit la page --, alors que la borne superieure depend du **residu
    propre de la page**, donc d'une grandeur qu'aucune construction de registre ne connait.
    Elle ne peut pas se verifier a la construction; elle se mesure, et c'est le test
    ci-dessus qui la mesure.

    Ce que ce test verrouille est l'asymetrie elle-meme, pour qu'elle cesse d'etre
    silencieuse: le seuil livre est **au-dessus** de la borne superieure que sa propre
    reserve calcule (1,0 > 0,9 sur une page a ~7,1 de residu propre), donc le domaine utile
    est vide a ce regime -- et non vide sur une page plus propre, ce qui est verifie aussi.
    """
    guard = cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID)
    plafond = color_metrics.get_color_acceptance(
        color_metrics.ACTIVE_COLOR_ACCEPTANCE_ID).max_mean_delta_e

    # Borne inferieure: gardee a la construction, et son refus est nomme.
    assert guard.max_excess_residual_de76 > guard.null_distribution_max_de76
    with pytest.raises(ValueError):
        dataclasses.replace(
            guard, max_excess_residual_de76=guard.null_distribution_max_de76 / 2.0)

    # Borne superieure: **calculee** et non gardee. Sur une page dont le residu propre est
    # celui du terrain, la marge avant le plafond d'acceptation est inferieure au seuil,
    # donc aucun exces ne peut declencher la garde sans que l'acceptation echoue.
    residu_terrain = 7.1
    assert plafond - residu_terrain < guard.max_excess_residual_de76
    # Et sur une page plus propre le domaine est bien non vide: la garde n'est pas inerte,
    # elle est bornee par la qualite de la page. Un test qui n'aurait mesure que le premier
    # cas aurait conclu trop large.
    residu_propre = 3.0
    assert plafond - residu_propre > guard.max_excess_residual_de76


# ---------------------------------------------------------------------------
# Bloquant B2 de la revue de 5.16: la garde ne se desarme plus en silence
# ---------------------------------------------------------------------------


def test_une_forme_importee_inconnue_refuse_la_page_au_lieu_de_desarmer_la_garde():
    """**Bloquant B2**, exerce dans le regime ou la garde etait muette: le transporte.

    `UnknownCorrectionFormError` **est** un `ValueError`, donc l'ancien `except ValueError`
    d'`assess_divergence` l'absorbait. Et en regime transporte l'identifiant de forme vient
    du **profil importe**, la validation prealable etant explicitement sautee: rien ne
    verifiait donc jamais cette valeur. Mesure d'avant correctif, meme profil, meme page,
    seul l'identifiant change: `status = applied`, `diverges = None`, `reason =
    divergence_excess_not_computable` -- sur un residu importe de 33 dE76. Une page fausse
    declaree bonne, sans le drapeau que l'AC 15 exige explicite.

    Le test porte sur **ce** regime et non sur le regime local: c'est celui pour lequel la
    garde existe, celui ou la correction vient d'ailleurs, et le seul ou la valeur fautive
    est une **donnee** plutot qu'un argument.
    """
    profile = _calibration_profile()
    inconnue = dataclasses.replace(profile, correction_id="color-correction-inexistante-9")
    assert inconnue.correction_id not in cc.CORRECTION_FORMS
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_DEVIANT_PRESS)

    refus = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-7",
        imported_profile=inconnue, imported_source_page_id="calibration-0")

    assert refus.status == "failed", refus.failure_reason
    assert refus.failure_reason == cc.FAILURE_UNKNOWN_CORRECTION_FORM
    assert refus.profile is None
    # La provenance survit au refus, comme pour toute autre cause: un echec dont on ne
    # sait pas quelle correction a ete tentee ni d'ou elle venait n'est pas relisable.
    assert refus.correction_source == cc.CORRECTION_SOURCE_CALIBRATION_PAGE
    assert refus.correction_source_page_id == "calibration-0"
    assert refus.correction_form_id == inconnue.correction_id
    # Et le refus est **anterieur a toute mesure**: aucun verdict de divergence n'est
    # publie, donc rien ne peut se lire comme « exces non calculable » -- le motif que la
    # garde desarmee empruntait.
    assert refus.divergence is None
    # Temoin positif: la **meme** page, avec la **meme** correction sous une forme connue,
    # est refusee pour divergence. C'est ce qui prouve que le premier refus a ferme un
    # contournement et non une page deja fautive pour une autre raison.
    connue = cc.calibrate_page(
        page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id="page-7",
        imported_profile=profile, imported_source_page_id="calibration-0")
    # **Le temoin positif, amende par la story 5.23**: la meme page sous une forme
    # **connue** est desormais **corrigee**, tout en divergeant franchement. Ce qui rend
    # le premier refus concluant est inchange et meme renforce -- une forme inconnue reste
    # le seul des deux a produire un `failed`, donc le refus ne peut pas etre attribue a
    # la divergence, qui ne refuse plus rien du tout.
    assert connue.status == "applied"
    assert connue.not_applied_reason is None
    assert connue.failure_reason is None
    assert connue.divergence.diverges is True
    assert connue.divergence.excess_residual_de76 > (
        cc.get_divergence_guard(cc.ACTIVE_DIVERGENCE_GUARD_ID).max_excess_residual_de76)


def test_assess_divergence_n_absorbe_plus_une_forme_inconnue():
    """La garde au niveau de la fonction, pour que le correctif ne tienne pas au seul appelant.

    `calibrate_page` resout desormais la forme avant `assess_divergence`, donc le chemin de
    production ne peut plus y arriver avec une forme inconnue. Ce test verrouille l'autre
    moitie: `assess_divergence` **leve** au lieu de classer « exces non calculable ». Sans
    lui, le correctif serait une propriete d'un appelant et le prochain appelant la
    reperdrait -- c'est exactement la forme du defaut d'origine.
    """
    press = _press(0.93, (0.030, 0.020, 0.020))
    measured, reference, neutral = _adjustment_arrays("patch-values-2", press)
    profile = cc.fit_correction(measured, reference, neutral)

    with pytest.raises(cc.UnknownCorrectionFormError):
        cc.assess_divergence(
            measured, reference, neutral, profile,
            page_id="page-9", source_page_id="calibration-0",
            correction_form_id="color-correction-inexistante-9")

    # Frontiere symetrique: la sous-determination, elle, reste absorbee et **dite**. Un
    # correctif qui aurait laisse passer les deux aurait fait echouer une page mesurable.
    lonely = slice(1, 2)
    assessment = cc.assess_divergence(
        measured[lonely], reference[lonely], neutral[lonely], profile,
        page_id="page-9", source_page_id="calibration-0",
        correction_form_id=cc.CORRECTION_FORM_ID)
    assert assessment.reason == cc.REASON_DIVERGENCE_NOT_COMPUTABLE
    assert assessment.diverges is None
    # Et le motif ne couvre plus qu'**une** cause: la page ne peut pas ajuster sa propre
    # correction. Les deux causes qu'il portait -- mesure insuffisante et faute de cablage
    # -- etaient de nature differente et indistinguables au manifest.
    assert cc.UnknownCorrectionFormError.__mro__[1] is ValueError, (
        "la sous-classe est deliberee: c'est elle qui rendait l'absorption possible, et "
        "ce test perdrait son sens si la hierarchie changeait")


def test_une_page_sans_correction_importee_n_a_pas_de_verdict_de_divergence():
    """Une page qui s'ajuste sur elle-meme ne peut pas diverger d'elle-meme."""
    page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                     distort=_press(0.93, (0.025, 0.024, 0.026)))
    result = cc.calibrate_page(page, template_id=TEMPLATE, patch_preset_id=PRESET,
                               dpi=600, page_id="page-1")
    assert result.divergence is None
    assert "divergence" not in cc.correction_provenance_summary(result)


def test_aucun_identifiant_de_cette_story_ne_contient_mire_ni_synthetic():
    """Frontiere de vocabulaire: `mires` est deja pris, et designe autre chose.

    Dans ce depot, `mires` sont les **frames de remplacement de synthese**
    (`lots[].synthetic_frames`, `EPIC5-ARB-33`). Un identifiant de cette story qui
    reprendrait le mot rendrait les deux registres indiscernables a la lecture.
    """
    introduced = [
        cc.CORRECTION_FORM_LAB_ID, cc.CORRECTION_SOURCE_OWN_SHEET,
        cc.CORRECTION_SOURCE_CALIBRATION_PAGE, cc.FAILURE_PAGE_DIVERGES,
        cc.REASON_DIVERGENCE_NOT_COMPUTABLE, cc.DIVERGENCE_BYPASS_FLAG,
        cc.REFUSAL_LIGHTNESS_NEEDS_TWO_NEUTRALS, cc.REFUSAL_CHROMA_NEEDS_THREE_POINTS,
        patch_values.ROLE_CALIBRATION_LATTICE, patch_values.SHADOW_PROBE_ID_PREFIX,
        "patch-values-3", "color-divergence-1",
        *(value.value_id for value in patch_values.calibration_lattice_values()[:5]),
        *patch_values.shadow_probe_value_ids(),
    ]
    for identifier in introduced:
        assert not re.search(r"mire|synthetic", identifier, re.IGNORECASE), identifier


def test_les_deux_formes_de_profil_satisfont_le_protocole_que_le_champ_annonce():
    """**Mineur m6 de la couche 1**: l'annotation de `PageCalibration.profile` etait fausse.

    Le champ etait declare `CorrectionProfile | None` alors qu'il recoit **aussi** un
    `LabCorrectionProfile` -- la story 5.16 rend explicitement les deux formes
    interchangeables partout ou une correction est **appliquee**. Aucun effet a
    l'execution, puisque rien ne verifie les types; mais c'etait la seule declaration du
    module qui contredisait le protocole que la story installe, et une annotation fausse
    se lit comme une intention.

    Le protocole est verifie **par ce test** et non par un lecteur, et il l'est dans les
    deux directions qui comptent:

    * les deux formes livrees le satisfont, sinon l'annotation serait fausse dans l'autre
      sens -- et une forme qui ne porte pas `apply_linear` ne peut pas etre appliquee;
    * un objet qui ne porte **pas** les deux membres ne le satisfait pas, sans quoi le
      protocole serait vide et sa satisfaction ne prouverait rien. C'est le temoin negatif
      que ce depot exige de toute garde: une garde dont le domaine d'activation est vide
      n'est pas une garde.

    Le protocole reste **structurel**: aucun `isinstance` n'est pose dans le code de
    production, ou une forme nouvelle doit passer sans qu'aucun point d'application la
    reconnaisse. C'est la raison pour laquelle il n'y a pas d'union ici -- une union se
    reecrirait a chaque forme nouvelle, dans les trois sites qui l'annoncent.
    """
    affine = cc.CorrectionProfile(
        stage_a=np.eye(3), stage_m=np.eye(3))
    lab = cc.LabCorrectionProfile(
        lightness_slope=1.0, lightness_offset=0.0,
        chroma_matrix=np.eye(2), chroma_offset=np.zeros(2))

    # Les deux formes satisfont le protocole, et portent des identifiants **differents**:
    # sans ce second volet, deux formes indistinguables passeraient le premier.
    for forme in (affine, lab):
        assert isinstance(forme, cc.AnyCorrectionProfile), type(forme).__name__
        assert isinstance(forme.correction_id, str) and forme.correction_id
        assert callable(forme.apply_linear)
    assert affine.correction_id != lab.correction_id

    # Temoin negatif: le protocole **discrimine**. Un objet qui porte l'un des deux
    # membres et pas l'autre ne le satisfait pas.
    class SansApplication:
        correction_id = "color-correction-sans-application"

    class SansIdentifiant:
        def apply_linear(self, linear):
            return linear

    assert not isinstance(SansApplication(), cc.AnyCorrectionProfile)
    assert not isinstance(SansIdentifiant(), cc.AnyCorrectionProfile)
