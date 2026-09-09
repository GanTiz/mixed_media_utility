"""La mesure brute a brute de la story 5.23 (AC 2, `EPIC5-ARB-82` decision 2).

**Pourquoi un fichier a part, et pourquoi il est rapide.** L'AC 9 de la story exige que
le lot de tests tourne en moins de dix secondes: une propriete fine vit dans la suite
unitaire de son module, jamais dans un fichier d'integration. Tout ce qui est verifie
ici l'est sur des mappings ecrits a la main -- aucun scan, aucun PDF, aucune image.

**Ce que ce fichier chasse en priorite.** L'appariement de deux jeux de mesures est
*exactement* la famille de defaut `M33` / `M25`, sept fois payee dans ce depot et jamais
trouvee autrement que par mutation. Les fabriques ci-dessous produisent donc au moins
six valeurs **distinguables**, dans des **ordres differents** entre les deux feuilles,
et la valeur visee n'est jamais en premiere position.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402

from mixed_media_utility import (  # noqa: E402
    color_calibration, color_metrics, patch_presets, patch_values)
from mixed_media_utility.io import calibration_profile  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques: au moins deux elements, TOUS distinguables (regle du depot)
# ---------------------------------------------------------------------------


#: Six valeurs distinguables, en sRGB encode [0, 1] ordre **BGR**. Aucune n'est egale a
#: une autre, et aucune n'est un remplissage uniforme: une permutation ne se voit que si
#: les elements different. Les identifiants sont ceux du vrai jeu temoin, pour que le
#: test parle du meme vocabulaire que la production.
_FEUILLE_DE_REFERENCE: dict[str, tuple[float, float, float]] = {
    "primary-red": (0.18, 0.17, 0.74),
    "primary-green": (0.27, 0.58, 0.21),
    "primary-blue": (0.62, 0.29, 0.17),
    "neutral-065": (0.25, 0.25, 0.26),
    "secondary-cyan": (0.68, 0.64, 0.23),
    "secondary-magenta": (0.58, 0.23, 0.68),
}


def _decalee(source, *, value_id: str, delta: float):
    """Meme feuille, une seule valeur deplacee. Le reste est identique **au bit pres**."""
    copie = dict(source)
    b, g, r = copie[value_id]
    copie[value_id] = (min(1.0, b + delta), g, min(1.0, r + delta))
    return copie


def _dans_un_autre_ordre(mapping):
    """Le meme mapping, insere dans un ordre **inverse**.

    Un `dict` Python conserve son ordre d'insertion, donc deux feuilles construites dans
    deux ordres differents sont le regime reel: la planche pose ses temoins en colonnes
    laterales, la page de calibration les lit apres son treillis. Rien ne garantit que
    les deux listes sortent dans le meme ordre.
    """
    return {key: mapping[key] for key in reversed(list(mapping))}


# ---------------------------------------------------------------------------
# AC 2 -- appariement par identifiant, jamais par position
# ---------------------------------------------------------------------------


def test_l_appariement_se_fait_par_identifiant_et_pas_par_position() -> None:
    """Deux feuilles dans des ordres differents rendent le meme ecart. Sinon, faux.

    Le volet decisif n'est pas que le resultat soit juste: c'est que le resultat d'un
    appariement **positionnel** soit different, et donc qu'un mutant qui zippe les deux
    sequences soit tue. Un test ou les deux calculs coincident ne prouverait rien.
    """
    planche = dict(_FEUILLE_DE_REFERENCE)
    # La valeur qui diverge est `secondary-cyan`, en **cinquieme** position sur la
    # planche et en **deuxieme** sur la page: elle n'est premiere nulle part.
    page = _dans_un_autre_ordre(_decalee(planche, value_id="secondary-cyan", delta=0.12))
    assert list(page)[0] != "secondary-cyan"
    assert list(planche)[0] != "secondary-cyan"

    mesure = color_metrics.raw_divergence_de76(sheet_raw=planche, calibration_raw=page)
    assert mesure.paired_count == 6
    assert mesure.excluded == ()

    # Verite de reference, calculee **par identifiant** et a la main.
    attendu = sum(
        float(color_metrics.delta_e76_srgb_d65(planche[key], page[key]))
        for key in planche
    ) / len(planche)
    assert mesure.mean_delta_e76 == pytest.approx(attendu)

    # Et le volet qui tue le mutant positionnel: apparier dans l'ordre d'insertion
    # rendrait un ecart tres different, et tout aussi credible.
    positionnel = sum(
        float(color_metrics.delta_e76_srgb_d65(gauche, droite))
        for gauche, droite in zip(planche.values(), page.values())
    ) / len(planche)
    assert positionnel != pytest.approx(attendu, abs=1.0), (
        "les deux appariements rendent le meme chiffre: le test ne peut pas voir la "
        "difference, donc il ne prouve rien")


def test_deux_feuilles_identiques_rendent_un_ecart_nul_quel_que_soit_l_ordre() -> None:
    """Zero est la lecture de deux feuilles identiques -- et de rien d'autre.

    C'est le pendant du test d'exclusion ci-dessous: si une valeur manquante etait
    remplacee par zero, elle serait indiscernable de ce regime-ci.
    """
    mesure = color_metrics.raw_divergence_de76(
        sheet_raw=dict(_FEUILLE_DE_REFERENCE),
        calibration_raw=_dans_un_autre_ordre(_FEUILLE_DE_REFERENCE),
    )
    assert mesure.mean_delta_e76 == pytest.approx(0.0)
    assert mesure.paired_count == 6


def test_la_valeur_visee_ailleurs_qu_en_premiere_position_est_bien_celle_qui_pese() -> None:
    """Un `find` fautif qui rend toujours le premier element ne se demasque pas autrement.

    Deux mesures, une divergence sur la **derniere** valeur puis sur la **premiere**: les
    deux doivent rendre le meme ecart moyen, et un appariement qui privilegie une
    position rendrait deux chiffres differents.
    """
    ids = list(_FEUILLE_DE_REFERENCE)
    premiere, derniere = ids[0], ids[-1]
    sur_la_derniere = color_metrics.raw_divergence_de76(
        sheet_raw=dict(_FEUILLE_DE_REFERENCE),
        calibration_raw=_decalee(_FEUILLE_DE_REFERENCE, value_id=derniere, delta=0.2),
    )
    sur_la_premiere = color_metrics.raw_divergence_de76(
        sheet_raw=dict(_FEUILLE_DE_REFERENCE),
        calibration_raw=_decalee(_FEUILLE_DE_REFERENCE, value_id=premiere, delta=0.2),
    )
    assert sur_la_derniere.mean_delta_e76 > 0.0
    # Les deux valeurs deplacees ne sont pas la meme couleur, donc les deux moyennes ne
    # sont pas egales; ce qui doit l'etre, c'est le **nombre de paires**, et le fait que
    # la divergence soit vue dans les deux cas.
    assert sur_la_premiere.mean_delta_e76 > 0.0
    assert sur_la_derniere.paired_count == sur_la_premiere.paired_count == 6


# ---------------------------------------------------------------------------
# AC 2 -- une valeur absente ou illisible est exclue ET declaree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "illisible",
    [None, float("nan"), (0.1, 0.2), "gris", (0.1, float("inf"), 0.3)],
    ids=["none", "nan-scalaire", "paire", "chaine", "non-fini"],
)
def test_une_valeur_illisible_est_exclue_de_la_moyenne_et_declaree(illisible) -> None:
    planche = dict(_FEUILLE_DE_REFERENCE)
    planche["secondary-magenta"] = illisible
    mesure = color_metrics.raw_divergence_de76(
        sheet_raw=planche, calibration_raw=dict(_FEUILLE_DE_REFERENCE))

    assert "secondary-magenta" not in mesure.paired_value_ids
    assert mesure.paired_count == 5
    assert mesure.excluded == (
        color_metrics.ExcludedWitness(
            "secondary-magenta", color_metrics.RAW_EXCLUSION_UNREADABLE_SHEET),
    )
    # Exclue, **pas remplacee par zero**: les cinq valeurs restantes sont identiques
    # entre les deux feuilles, donc la moyenne vaut zero -- et c'est exactement pourquoi
    # un remplissage a zero serait indetectable. Ce qui distingue les deux regimes est la
    # declaration, pas le chiffre.
    assert mesure.mean_delta_e76 == pytest.approx(0.0)
    assert mesure.paired_count < len(_FEUILLE_DE_REFERENCE)


def test_une_valeur_absente_d_un_seul_cote_est_declaree_du_bon_cote() -> None:
    """Les deux sens sont testes: balayer les cles d'une seule feuille en manquerait un."""
    planche = dict(_FEUILLE_DE_REFERENCE)
    page = dict(_FEUILLE_DE_REFERENCE)
    del planche["primary-blue"]
    del page["secondary-cyan"]
    mesure = color_metrics.raw_divergence_de76(sheet_raw=planche, calibration_raw=page)

    assert mesure.paired_value_ids == (
        "neutral-065", "primary-green", "primary-red", "secondary-magenta")
    assert mesure.excluded == (
        color_metrics.ExcludedWitness(
            "primary-blue", color_metrics.RAW_EXCLUSION_ABSENT_SHEET),
        color_metrics.ExcludedWitness(
            "secondary-cyan", color_metrics.RAW_EXCLUSION_ABSENT_CALIBRATION),
    )


def test_aucune_paire_lisible_leve_au_lieu_de_rendre_une_moyenne_sur_rien() -> None:
    with pytest.raises(color_metrics.ColorMetricError) as excinfo:
        color_metrics.raw_divergence_de76(
            sheet_raw={"primary-red": (0.1, 0.2, 0.3), "primary-green": None},
            calibration_raw={"primary-green": (0.1, 0.2, 0.3), "primary-blue": None},
        )
    message = str(excinfo.value)
    # Le message nomme **chaque** valeur ecartee et son motif: un « aucune paire » nu
    # laisserait chercher laquelle des deux feuilles est en cause.
    for value_id in ("primary-red", "primary-green", "primary-blue"):
        assert value_id in message


def test_un_mapping_qui_n_en_est_pas_un_est_refuse() -> None:
    with pytest.raises(color_metrics.ColorMetricError):
        color_metrics.raw_divergence_de76(
            sheet_raw=[("primary-red", (0.1, 0.2, 0.3))],
            calibration_raw=dict(_FEUILLE_DE_REFERENCE),
        )


# ---------------------------------------------------------------------------
# AC 2 -- frontiere negative: aucun profil de correction sur ce chemin
# ---------------------------------------------------------------------------


def _fonctions_du_chemin(depart) -> set[str]:
    """Cloture transitive des fonctions de `color_metrics` appelees depuis `depart`.

    Un grep sur la seule fonction ne prouverait rien: elle pourrait appeler une
    helper qui, elle, consomme un profil. La cloture est donc calculee sur l'AST.
    """
    module = sys.modules[color_metrics.__name__]
    vues: set[str] = set()
    a_voir = [depart.__name__]
    while a_voir:
        nom = a_voir.pop()
        if nom in vues:
            continue
        vues.add(nom)
        cible = getattr(module, nom, None)
        if not callable(cible):
            continue
        try:
            source = textwrap.dedent(inspect.getsource(cible))
        except (OSError, TypeError):  # pragma: no cover - defensif
            continue
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
                a_voir.append(noeud.func.id)
    return vues


def test_la_mesure_brute_ne_consomme_aucun_profil_de_correction() -> None:
    """Frontiere negative de l'AC 2, verifiee sur le **chemin** et non sur un fichier.

    Trois volets, et les trois sont necessaires: le module n'importe pas la chaine de
    correction (donc le vocabulaire du profil est hors de portee), aucune fonction du
    chemin ne **nomme** un profil, et le chemin n'est pas vide -- sans ce dernier volet,
    une cloture qui rendrait l'ensemble vide ferait passer le test pour une raison
    fausse.

    Le balayage porte sur les **identifiants de l'AST**, jamais sur le texte source: un
    grep textuel se declencherait sur la prose des commentaires, qui a justement le droit
    de nommer ce qu'elle exclut.
    """
    source_module = Path(inspect.getfile(color_metrics)).read_text(encoding="utf-8")
    arbre_module = ast.parse(source_module)
    importes = {
        alias.name.split(".")[0]
        for noeud in ast.walk(arbre_module)
        if isinstance(noeud, ast.Import)
        for alias in noeud.names
    } | {
        noeud.module.split(".")[-1]
        for noeud in ast.walk(arbre_module)
        if isinstance(noeud, ast.ImportFrom) and noeud.module
    }
    assert "color_calibration" not in importes, importes
    assert "color_pipeline" not in importes, importes

    chemin = _fonctions_du_chemin(color_metrics.raw_divergence_de76)
    assert {"raw_divergence_de76", "_readable_triplet", "delta_e76_srgb_d65"} <= chemin
    interdits = {"apply_linear", "CorrectionProfile", "imported_profile",
                 "calibrate_page", "apply_active_calibration"}
    module = sys.modules[color_metrics.__name__]
    for nom in sorted(chemin):
        cible = getattr(module, nom, None)
        if not callable(cible):
            continue
        try:
            source = textwrap.dedent(inspect.getsource(cible))
        except (OSError, TypeError):  # pragma: no cover - defensif
            continue
        identifiants = set()
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Name):
                identifiants.add(noeud.id)
            elif isinstance(noeud, ast.Attribute):
                identifiants.add(noeud.attr)
        assert not (identifiants & interdits), (nom, identifiants & interdits)


# ---------------------------------------------------------------------------
# AC 1 -- les secondaires servent vraiment: elles font basculer un verdict
# ---------------------------------------------------------------------------


def _mesures_du_preset(preset_id: str, *, decalage_sur=(), delta: float = 0.0):
    """Deux feuilles identiques sur toutes les valeurs d'un preset, sauf une.

    Les triplets sont ceux de la **vraie** table de valeurs du preset, normalises en
    [0, 1]: un jeu invente ici ne dirait rien de ce qui s'imprime.
    """
    preset = patch_presets.get_patch_preset(preset_id)
    table = patch_values.get_patch_values_table(preset.values_version)
    planche, page = {}, {}
    for value_id in preset.value_ids:
        red, green, blue = table.get(value_id).rgb
        bgr = (blue / 255.0, green / 255.0, red / 255.0)
        planche[value_id] = bgr
        if value_id in decalage_sur:
            page[value_id] = (min(1.0, bgr[0] + delta), bgr[1],
                              max(0.0, bgr[2] - delta))
        else:
            page[value_id] = bgr
    return planche, page


def test_une_derive_qui_ne_touche_qu_une_secondaire_est_vue_par_le_nouveau_jeu() -> None:
    """AC 1 (b): une valeur ajoutee dont aucun test ne montre qu'elle change un verdict
    n'a pas ete justifiee.

    Le scenario est celui qu'`EPIC5-ARB-82` decrit: une imprimante depose du CMJN, donc
    une derive d'encre magenta se voit sur une pastille magenta. Le jeu de 5.16
    (`patches-14-v3`, RVB + neutres + sentinelles) ne porte **aucune** secondaire: la
    meme derive y est litteralement invisible, l'ecart brut y vaut zero.
    """
    # Une derive d'encre ne touche pas une pastille isolee: elle touche **toutes**
    # celles qui portent cette encre. Le scenario deplace donc les trois secondaires,
    # qui sont les seules pastilles du jeu ou une encre CMJ domine.
    secondaires = ("secondary-cyan", "secondary-magenta", "secondary-yellow")
    delta = 0.25
    planche_v4, page_v4 = _mesures_du_preset(
        "patches-17-v4", decalage_sur=secondaires, delta=delta)
    vu = color_metrics.raw_divergence_de76(
        sheet_raw=planche_v4, calibration_raw=page_v4)
    assert vu.mean_delta_e76 > 0.0
    assert vu.paired_count == 17
    assert vu.excluded == ()

    # Le meme scenario sur l'ancien jeu: la valeur qui derive n'y est pas, donc les deux
    # feuilles sont identiques et l'ecart est **nul**. C'est la capacite que la story
    # achete, mesuree plutot que revendiquee.
    ancien = patch_presets.get_patch_preset("patches-14-v3")
    assert not set(secondaires) & set(ancien.value_ids)
    planche_v3, page_v3 = _mesures_du_preset(
        "patches-14-v3", decalage_sur=secondaires, delta=delta)
    aveugle = color_metrics.raw_divergence_de76(
        sheet_raw=planche_v3, calibration_raw=page_v3)
    assert aveugle.mean_delta_e76 == pytest.approx(0.0)

    # Et le verdict bascule vraiment: avec un decalage porte a la derive d'encre franche,
    # le nouveau jeu passe au-dessus du seuil de registre quand l'ancien reste muet.
    planche_fort, page_fort = _mesures_du_preset(
        "patches-17-v4", decalage_sur=secondaires, delta=0.95)
    fort = color_metrics.raw_divergence_de76(
        sheet_raw=planche_fort, calibration_raw=page_fort)
    assert color_metrics.raw_divergence_exceeds(fort.mean_delta_e76)
    assert not color_metrics.raw_divergence_exceeds(aveugle.mean_delta_e76)


# ---------------------------------------------------------------------------
# Determinisme de l'ordre rendu: six valeurs, deux graines de hachage
# ---------------------------------------------------------------------------


_SCRIPT_ORDRE = """
import sys
sys.path.insert(0, {src!r})
from mixed_media_utility import color_metrics

planche = {{
    "sentinel-white-1": None,
    "primary-red": (0.2, 0.2, 0.7),
    "secondary-yellow": (0.2, 0.8, 0.9),
    "neutral-020": (0.08, 0.08, 0.08),
    "sentinel-black-1": (0.02, 0.02, 0.02),
    "secondary-cyan": (0.7, 0.6, 0.2),
    "primary-blue": (0.6, 0.3, 0.2),
}}
page = {{cle: valeur for cle, valeur in reversed(list(planche.items()))}}
page["secondary-magenta"] = (0.6, 0.2, 0.7)
del page["primary-blue"]
mesure = color_metrics.raw_divergence_de76(sheet_raw=planche, calibration_raw=page)
print(",".join(mesure.paired_value_ids))
print(",".join(f"{{item.value_id}}|{{item.reason}}" for item in mesure.excluded))
"""


@pytest.mark.parametrize("graine", ["3", "7"])
def test_l_ordre_rendu_ne_depend_pas_de_la_graine_de_hachage(graine, tmp_path) -> None:
    """Sept valeurs, deux graines: un ensemble de deux elements ne prouve jamais un tri.

    L'union des deux feuilles passe par un `set`, dont l'ordre d'iteration depend de la
    graine de hachage du processus. Ces deux sequences partent au journal et au manifest:
    un ordre instable rendrait deux traces differentes pour le meme scan.
    """
    script = tmp_path / "ordre.py"
    script.write_text(_SCRIPT_ORDRE.format(src=str(SRC)), encoding="utf-8")
    sortie = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, check=True,
        env={"PYTHONHASHSEED": graine, "PATH": "/usr/bin:/bin"},
    )
    appariees, ecartees = sortie.stdout.strip().splitlines()
    assert appariees == ",".join([
        "neutral-020", "primary-red", "secondary-cyan", "secondary-yellow",
        "sentinel-black-1",
    ])
    assert ecartees == "|".join([
        "primary-blue", color_metrics.RAW_EXCLUSION_ABSENT_CALIBRATION,
    ]) + "," + "|".join([
        "secondary-magenta", color_metrics.RAW_EXCLUSION_ABSENT_SHEET,
    ]) + "," + "|".join([
        "sentinel-white-1", color_metrics.RAW_EXCLUSION_UNREADABLE_SHEET,
    ])


# ---------------------------------------------------------------------------
# Correction du 2026-08-18 : la divergence brute consomme le PROFIL, plus la passe
# ---------------------------------------------------------------------------
#
# Ce que la chaine complete a rendu sur les vrais scans d'Egan (HP Envy 4520, 300 dpi):
# page de calibration lue, profil ecrit, planches corrigees -- et
# `raw_divergence = {"reason": "raw_divergence_no_calibration_sheet",
# "mean_raw_de76": null, "paired_value_ids": []}`. La mesure d'`EPIC5-ARB-82` ne se
# faisait que si les deux feuilles etaient dans la **meme passe de scan**, c'est-a-dire
# jamais dans le regime que la calibration par chaine (`EPIC5-ARB-80`) installe: la page
# de calibration se scanne une fois, les planches ensuite.
#
# Les tests ci-dessous portent sur le **transport**: le profil ecrit puis relu doit
# rendre exactement les temoins qu'il a mesures, appariables par identifiant, et le motif
# « pas de feuille de calibration » ne doit subsister que la ou il reste vrai.

_CHAINE = "300-tiff-abcdef012345"


def _profil_minimal():
    """Un profil de la forme affine, le moins couteux a construire. Sa valeur n'importe
    pas ici: ces tests portent sur les **temoins** que le document transporte a cote."""
    return color_calibration.CorrectionProfile(
        stage_a=np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]),
        stage_m=np.eye(3))


def _profil_ecrit(tmp_path, temoins, motif: str = ""):
    """Le document tel qu'il est **ecrit**, avant relecture. Pour epingler ses cles."""
    document = color_calibration.profile_to_document(
        _profil_minimal(), chain_id=_CHAINE, source_page_id="calibration-0",
        template_id="patches-18-v2", read_patch_count=130, retained_patch_count=128,
        ink_floor_excluded=False, witness_raw_bgr=temoins,
        witness_band_reason=motif)
    calibration_profile.write_profile(tmp_path, document)
    return document


def _profil_relu(tmp_path, temoins, motif: str = ""):
    """Ecrire puis relire un profil de chaine portant (ou non) ses temoins bruts.

    L'aller-retour passe par le **fichier**, pas par le dictionnaire en memoire: c'est le
    trajet reel -- `scan calibrate` ecrit un jour, `scan` relit un autre jour -- et c'est
    lui qui perdait la mesure.

    ``motif`` porte le second etage d'`EPIC5-ARB-104`: pourquoi le bandeau n'a rien rendu.
    Son defaut vide reproduit **exactement** le document d'avant cette story, ce qui est la
    forme sous laquelle la retrocompatibilite se verifie plutot que se declare.
    """
    _profil_ecrit(tmp_path, temoins, motif)
    return calibration_profile.read_profile(tmp_path, _CHAINE)


def test_les_temoins_portes_par_le_profil_rendent_la_divergence_mesurable(
    tmp_path,
) -> None:
    """Le livrable de la correction: un ecart chiffre et des paires, hors de la passe.

    La page de calibration n'est **pas** dans ce scan: seul son profil l'est. Le motif
    `raw_divergence_no_calibration_sheet`, qui etait la sortie permanente de ce regime,
    ne doit plus apparaitre.
    """
    correction = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, _FEUILLE_DE_REFERENCE))
    temoins = color_calibration.calibration_witness_raw_for_lot(
        correction, from_chain_profile=True)
    assert temoins is not None

    planche = _decalee(_FEUILLE_DE_REFERENCE, value_id="secondary-cyan", delta=0.05)
    verdict = color_calibration.assess_raw_divergence(
        sheet_raw=planche, calibration_raw=temoins,
        page_id="planche-1", source_page_id="calibration-0")

    assert verdict.reason is None
    assert verdict.mean_raw_de76 is not None and verdict.mean_raw_de76 > 0.0
    assert verdict.paired_value_ids == tuple(sorted(_FEUILLE_DE_REFERENCE))
    assert verdict.excluded == ()
    # Et l'ecart est bien celui d'une seule valeur deplacee sur six: la moyenne vaut le
    # sixieme de la distance de cette valeur, jamais la distance elle-meme.
    seule = color_metrics.raw_divergence_de76(
        sheet_raw={"secondary-cyan": planche["secondary-cyan"]},
        calibration_raw={"secondary-cyan": _FEUILLE_DE_REFERENCE["secondary-cyan"]})
    assert verdict.mean_raw_de76 == pytest.approx(
        seule.mean_delta_e76 / len(_FEUILLE_DE_REFERENCE), rel=1e-9)


def test_le_motif_du_bandeau_survit_a_l_aller_retour_par_le_fichier(tmp_path) -> None:
    """Second etage d'`EPIC5-ARB-104`, ferme **jusqu'au document relu**.

    C'est le trajet qui perdait le fait, et c'est le seul niveau ou la preuve compte:
    `scan calibrate` ecrit le profil un jour, `scan` le relit un autre, et entre les deux
    il n'y a que le fichier. Le champ pose cote persistance ne prouve rien tant que la
    chaine complete -- `profile_to_document` -> `write_profile` -> `read_profile` ->
    `chain_correction_from_document` -> `calibration_witness_raw_for_lot` ->
    `assess_raw_divergence` -- n'a pas ete parcourue.

    Ce que le manifest disait avant: `raw_divergence_no_calibration_sheet`, « aucune
    feuille de calibration dans ce scan », d'une chaine dont la page **a ete lue** et dont
    la correction vient d'elle. Le profil persistait la faussete a chaque scan suivant.

    Meme patron que les temoins bruts, epingle par ses deux bouts: un motif se relit
    **identique**, et un profil qui n'en porte pas n'ecrit **pas la cle** -- une cle
    presente-mais-vide dirait « un motif, mais lequel », et le module de persistance la
    refuse pour cette raison.
    """
    motif = color_calibration.RAW_DIVERGENCE_BAND_CROPPED

    # Bout 1: le document ecrit porte la cle, et une seule fois -- pas de temoins avec.
    ecrit = _profil_ecrit(tmp_path, (), motif)
    assert ecrit[calibration_profile.WITNESS_BAND_REASON_FIELD] == motif
    assert calibration_profile.WITNESS_RAW_FIELD not in ecrit
    # Bout 2: sans motif, la cle est **absente**, et le document est celui d'avant.
    muet = _profil_ecrit(tmp_path, ())
    assert calibration_profile.WITNESS_BAND_REASON_FIELD not in muet

    correction = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, (), motif))
    assert correction.witness_band_reason == motif
    assert correction.witness_raw_bgr == ()

    # La feuille a ete lue: la mesure existe et elle est vide, jamais `None`.
    temoins = color_calibration.calibration_witness_raw_for_lot(
        correction, from_chain_profile=True)
    assert temoins is not None and not temoins
    assert color_calibration.witness_band_reason_of(temoins) == motif

    verdict = color_calibration.assess_raw_divergence(
        sheet_raw=_FEUILLE_DE_REFERENCE, calibration_raw=dict(temoins),
        calibration_band_reason=color_calibration.witness_band_reason_of(temoins),
        page_id="planche-1", source_page_id="calibration-0")
    assert verdict.reason == motif
    assert verdict.reason != color_calibration.RAW_DIVERGENCE_NO_CALIBRATION_SHEET
    assert verdict.mean_raw_de76 is None and verdict.exceeds is None

    # Et le motif relu n'est pas un defaut deguise: un **autre** motif se relit autre.
    autre = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, (),
                     color_calibration.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN))
    assert autre.witness_band_reason == (
        color_calibration.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN)
    assert autre.witness_band_reason != correction.witness_band_reason


def test_un_profil_ecrit_avant_cette_mesure_declare_la_mesure_non_faite(tmp_path) -> None:
    """Le motif subsiste **la ou il reste vrai**: profil sans temoins, page sans bandeau.

    Et il ne se transforme surtout pas en ecart nul: un zero est la lecture de deux
    feuilles identiques, pas celle d'une mesure qui n'a pas eu lieu.
    """
    correction = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, ()))
    temoins = color_calibration.calibration_witness_raw_for_lot(
        correction, from_chain_profile=True)
    assert temoins is None

    verdict = color_calibration.assess_raw_divergence(
        sheet_raw=_FEUILLE_DE_REFERENCE, calibration_raw=temoins,
        page_id="planche-1", source_page_id="calibration-0")
    assert verdict.reason == color_calibration.RAW_DIVERGENCE_NO_CALIBRATION_SHEET
    assert verdict.mean_raw_de76 is None
    assert verdict.exceeds is None
    assert verdict.paired_value_ids == ()


def test_le_transport_par_le_profil_apparie_par_identifiant_et_pas_par_position(
    tmp_path,
) -> None:
    """Les deux feuilles dans des ordres **differents**, la cible en avant-derniere place.

    Le profil est ecrit depuis un jeu inverse, la planche est lue dans l'ordre direct: un
    appariement positionnel comparerait `primary-red` a `secondary-magenta` et rendrait un
    ecart parfaitement credible entre deux couleurs differentes.
    """
    correction = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, _dans_un_autre_ordre(_FEUILLE_DE_REFERENCE)))
    temoins = color_calibration.calibration_witness_raw_for_lot(
        correction, from_chain_profile=True)

    identiques = color_calibration.assess_raw_divergence(
        sheet_raw=_FEUILLE_DE_REFERENCE, calibration_raw=temoins,
        page_id="planche-1", source_page_id="calibration-0")
    assert identiques.mean_raw_de76 == pytest.approx(0.0, abs=1e-9)

    # La valeur visee n'est ni la premiere ni la derniere des deux jeux, et c'est elle
    # seule qui bouge: le resultat doit la suivre.
    planche = _decalee(_FEUILLE_DE_REFERENCE, value_id="neutral-065", delta=0.08)
    deplacee = color_calibration.assess_raw_divergence(
        sheet_raw=planche, calibration_raw=temoins,
        page_id="planche-1", source_page_id="calibration-0")
    assert deplacee.mean_raw_de76 > identiques.mean_raw_de76
    assert deplacee.paired_value_ids == tuple(sorted(_FEUILLE_DE_REFERENCE))

    # Un appariement positionnel sur ces deux ordres rendrait un ecart **non nul** sur
    # deux feuilles identiques: c'est le mutant que ce test tue.
    zippe = color_metrics.raw_divergence_de76(
        sheet_raw=_FEUILLE_DE_REFERENCE,
        calibration_raw={
            attendu: mesure
            for attendu, mesure in zip(_FEUILLE_DE_REFERENCE, dict(temoins).values())})
    assert zippe.mean_delta_e76 > 1.0


def test_les_trois_regimes_de_la_moitie_page_de_calibration_ne_se_confondent_pas(
    tmp_path,
) -> None:
    """`None`, mapping vide et mapping plein disent trois choses differentes.

    * feuille de calibration lue dans cette passe, bandeau inexploitable -> mapping
      **vide**, motif `raw_divergence_witness_band_not_printed`;
    * profil de chaine portant ses temoins -> mapping plein, mesure faite;
    * profil de chaine sans temoins -> `None`, motif
      `raw_divergence_no_calibration_sheet`.
    """
    sans = color_calibration.chain_correction_from_document(_profil_relu(tmp_path, ()))
    avec = color_calibration.chain_correction_from_document(
        _profil_relu(tmp_path, _FEUILLE_DE_REFERENCE))

    assert color_calibration.calibration_witness_raw_for_lot(
        sans, from_chain_profile=False) == {}
    assert color_calibration.calibration_witness_raw_for_lot(
        sans, from_chain_profile=True) is None
    assert color_calibration.calibration_witness_raw_for_lot(
        avec, from_chain_profile=True) == dict(
            calibration_profile.witness_raw_from_document(
                calibration_profile.witness_raw_to_document(_FEUILLE_DE_REFERENCE)))

    motifs = {
        regime: color_calibration.assess_raw_divergence(
            sheet_raw=_FEUILLE_DE_REFERENCE, calibration_raw=temoins,
            page_id="planche-1", source_page_id="calibration-0").reason
        for regime, temoins in (
            ("bandeau non imprime", {}),
            ("profil sans temoins", None),
            ("profil avec temoins", dict(avec.witness_raw_bgr)))
    }
    assert motifs == {
        "bandeau non imprime": color_calibration.RAW_DIVERGENCE_BAND_NOT_PRINTED,
        "profil sans temoins": color_calibration.RAW_DIVERGENCE_NO_CALIBRATION_SHEET,
        "profil avec temoins": None,
    }


def test_le_motif_du_bandeau_traverse_calibrate_page_jusqu_au_verdict() -> None:
    """`EPIC5-ARB-104`: le motif porte par la mesure atteint le manifest **entier**.

    Le relais qui manquait: `calibrate_page` normalise la mesure en `dict` avant de la
    confronter -- ce qui est voulu, la moitie qui sert au calcul restant un mapping
    ordinaire -- et cette normalisation **perd** l'attribut. Sans lecture du motif avant
    elle, les cinq regimes se remettaient a sortir sous le seul
    `raw_divergence_witness_band_not_printed`, donc « papier nu » sur une feuille rognee.

    Le volet de mordant est la comparaison des deux appels: le meme raster, la meme
    correction, **la seule difference etant le motif porte par la mesure**.
    """
    from test_color_calibration import _synthetic_rectified_page

    template_id, preset_id, dpi = "tpl-a4-portrait-2f-v1", "patches-18-v2", 600
    planche = _synthetic_rectified_page(
        template_id=template_id, preset_id=preset_id, dpi=dpi)

    def _motif(mesure) -> str | None:
        resultat = color_calibration.calibrate_page(
            planche, template_id=template_id, patch_preset_id=preset_id, dpi=dpi,
            page_id="planche-1", calibration_witness_raw=mesure)
        assert resultat.raw_divergence is not None
        return resultat.raw_divergence.reason

    rogne = _motif(color_calibration.WitnessBandRaw(
        (), reason=color_calibration.RAW_DIVERGENCE_BAND_CROPPED))
    inconnu = _motif(color_calibration.WitnessBandRaw(
        (), reason=color_calibration.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN))
    # Une mesure vide **sans** motif reste ce qu'elle etait: le regime nominal.
    muette = _motif({})
    absente = _motif(None)

    assert rogne == color_calibration.RAW_DIVERGENCE_BAND_CROPPED
    assert inconnu == color_calibration.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN
    assert muette == color_calibration.RAW_DIVERGENCE_BAND_NOT_PRINTED
    assert absente == color_calibration.RAW_DIVERGENCE_NO_CALIBRATION_SHEET
    assert len({rogne, inconnu, muette, absente}) == 4
