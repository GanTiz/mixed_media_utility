"""La correction s'applique par defaut, la divergence avertit. Story 5.23, taches 4 a 7.

`EPIC5-ARB-82`. Ce fichier porte le niveau **unitaire** des fonctions neuves de la
bascule de politique -- le cablage de la mesure brute a brute sur le chemin reel, les deux
avertissements chiffres, et le geste explicite de refus.

**Pourquoi il est rapide, et pourquoi c'est une AC et non un confort** (AC 9). Le lot
complet ci-dessous tourne en moins de dix secondes parce que rien n'y scanne, n'y compose
et n'y ecrit de PDF: les objets manipules sont des mappings, des verdicts construits a la
main et un seul raster de synthese. Ce qui exige un scan de bout en bout vit dans
`test_scan_calibration_application.py`, ou il existait deja -- l'AC 3 s'y verifie sur les
octets des frames, pas ici.

**Ce que ce fichier chasse en priorite**, dans l'ordre des pieges deja payes:

1. la **frontiere stricte** du seuil (`>` contre `>=`), verifiee par injection reelle du
   mutant dans une copie jetable du module et non par relecture -- c'est le defaut trouve
   sur 5.22, ou le test neuf survivait au mutant que l'ancien tuait;
2. l'**appariement par identifiant**, avec des fabriques a six valeurs distinguables et la
   valeur visee jamais en premiere position;
3. les **domaines d'activation**: chaque garde est epinglee par ses deux bouts -- inerte
   sur ce que le depot livre, mordante sur un regime construit pour elle.
"""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

# La regle de regime -- « une reference de perimetre inatteignable est-elle un
# historique tronque, ou un AUTRE depot ? » -- vit dans `tests/_regime_du_depot.py`,
# ecrite une fois pour ses sept appelants.
sys.path.insert(0, str(SRC.parent / "tests"))
from _regime_du_depot import echoue_ou_saute  # noqa: E402
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mixed_media_utility import (  # noqa: E402
    cli,
    color_calibration as cc,
    color_metrics,
    page_templates,
    patch_presets,
)


# ---------------------------------------------------------------------------
# Fabriques: au moins deux elements, TOUS distinguables (regle du depot)
# ---------------------------------------------------------------------------


#: Six valeurs **distinguables**, en sRGB encode [0, 1], ordre BGR. Aucune n'est egale a
#: une autre et aucune n'est un remplissage uniforme: une permutation d'appariement ne se
#: voit que si les elements different. Les identifiants sont ceux du vrai jeu temoin.
_FEUILLE_CALIBRATION: dict[str, tuple[float, float, float]] = {
    "primary-red": (0.19, 0.18, 0.73),
    "primary-green": (0.28, 0.57, 0.22),
    "primary-blue": (0.61, 0.30, 0.18),
    "neutral-065": (0.26, 0.26, 0.27),
    "secondary-cyan": (0.67, 0.63, 0.24),
    "secondary-magenta": (0.57, 0.24, 0.67),
}


def _feuille_decalee(*, value_id: str, delta: float) -> dict:
    """La meme feuille, **une seule** valeur deplacee, le reste identique au bit pres.

    La valeur visee par defaut n'est jamais la premiere du jeu: un appariement positionnel
    fautif qui rendrait toujours le premier element ne se demasque pas autrement.
    """
    copie = dict(_FEUILLE_CALIBRATION)
    bleu, vert, rouge = copie[value_id]
    copie[value_id] = (min(1.0, bleu + delta), vert, min(1.0, rouge + delta))
    return copie


def _dans_un_autre_ordre(mapping: dict) -> dict:
    """Le meme jeu, dans un ordre d'insertion **different**. Deux feuilles n'ont aucune
    raison de presenter leurs pastilles dans le meme ordre, et un appariement positionnel
    rendrait ici un ecart parfaitement credible entre des couleurs differentes."""
    cles = list(mapping)
    return {cle: mapping[cle] for cle in reversed(cles)}


def _verdict(*, max_degradation: float, pire_pastille: str = "lattice-188-128-188",
             mean_degradation: float = -3.88) -> cc.AcceptanceVerdict:
    """Un verdict d'acceptation portant son `detail`, donc le nom de la pastille.

    Le `detail` n'est pas decoratif: c'est lui qui porte `worst_degradation_value_id`,
    c'est-a-dire ce que l'AC 7 exige que l'avertissement nomme.
    """
    detail = color_metrics.PageAcceptanceResult(
        mean_delta_e=11.54, max_delta_e=31.70, worst_value_id=pire_pastille,
        per_value=(), sample_count=65, values_version="patch-values-4",
        acceptance_id=color_metrics.ACTIVE_COLOR_ACCEPTANCE_ID,
        channel_relative_deviation_before_correction=(0.0, 0.0, 0.0),
        channel_relative_deviation_before_correction_per_value=(),
        passed=True, mean_degradation_de76=mean_degradation,
        max_degradation_de76=max_degradation,
        worst_degradation_value_id=pire_pastille)
    return cc.AcceptanceVerdict(
        status="applied", mean_delta_e=11.54, max_delta_e=31.70,
        mean_delta_e_before=15.42,
        acceptance_id=color_metrics.ACTIVE_COLOR_ACCEPTANCE_ID,
        mean_degradation_de76=mean_degradation,
        max_degradation_de76=max_degradation, detail=detail)


# ---------------------------------------------------------------------------
# AC 2 -- le cablage: la page de calibration echantillonne enfin ses temoins
# ---------------------------------------------------------------------------


def test_la_page_de_calibration_ne_porte_le_bandeau_que_depuis_le_preset_qui_l_a_ajoute():
    """Le gate de lecture est **versionne**, et il refuse dans le bon sens.

    `patches-17-v4` est le premier preset dont les tirages portent le bandeau sur la page
    de calibration; toutes les feuilles anterieures ont des colonnes laterales de papier
    nu. Un identifiant **inconnu** leve au lieu de rendre `False`: « je ne connais pas ce
    preset » et « ce preset n'a pas de bandeau » sont deux faits differents, et les
    confondre ferait taire la mesure de divergence sur une faute de frappe.
    """
    assert patch_presets.calibration_page_carries_witness_band("patches-17-v4") is True
    # Le temoin negatif porte sur **plusieurs** presets anterieurs et non sur un seul:
    # une table reduite a une exception unique se lit comme une particularite.
    for ancien in ("patches-14-v3", "patches-9-v1", "patches-12-v1", "patches-18-v2"):
        assert patch_presets.calibration_page_carries_witness_band(ancien) is False, ancien
    with pytest.raises(patch_presets.UnknownPatchPresetError):
        patch_presets.calibration_page_carries_witness_band("patches-inexistant-0")


def test_le_bandeau_de_la_page_de_calibration_est_echantillonne_et_apparie_par_identifiant(
        tmp_path):
    """**Le trou que cette tache comble**: rien n'echantillonnait ces 34 pastilles.

    Le raster est une page de calibration de synthese ou chaque pastille du bandeau est
    peinte a sa valeur de reference. Ce que le test etablit est la chaine complete:
    `fit_lot_correction_from_page` -> `witness_raw_bgr` -> `raw_divergence_de76`, avec un
    appariement **par identifiant**.

    Les deux bouts sont epingles: sous `patches-17-v4` le bandeau est lu et porte ses 17
    valeurs; sous `patches-14-v3` -- meme raster, meme geometrie -- il ne l'est pas, parce
    que la feuille est declaree anterieure au bandeau.
    """
    from mixed_media_utility import page_templates

    template_id = "tpl-a4-portrait-8f-v2"
    dpi = 300
    spec = page_templates.get_template(template_id)
    largeur, hauteur = page_templates.page_size_px(spec, dpi)
    page = np.full((hauteur, largeur, 3), 255, np.uint8)
    bandeau = patch_presets.resolve_calibration_page_witnesses(
        template_id, "patches-17-v4")
    for pastille in bandeau:
        x0 = int(round(pastille.x_mm / 25.4 * dpi))
        y0 = int(round(pastille.y_mm / 25.4 * dpi))
        cote = int(round(pastille.size_mm / 25.4 * dpi))
        page[y0:y0 + cote, x0:x0 + cote] = np.asarray(
            pastille.rgb[::-1], dtype=np.uint8)

    lu, motif = cc._sample_calibration_witness_band(
        page, template_id=template_id, patch_preset_id="patches-17-v4", dpi=dpi)
    # Le motif est vide **si et seulement si** la mesure existe (`EPIC5-ARB-104`).
    assert motif == ""
    identifiants = tuple(value_id for value_id, _ in lu)
    # Dix-sept valeurs distinctes, triees, et les trois secondaires en font partie: c'est
    # le jeu que l'AC 1 a ajoute, et c'est lui qui rend la comparaison utile sur une
    # imprimante CMJN.
    assert len(identifiants) == 17
    assert identifiants == tuple(sorted(set(identifiants)))
    assert {"secondary-cyan", "secondary-magenta", "secondary-yellow"} <= set(identifiants)
    # La mesure est **brute** et fidele: la pastille peinte a sa reference se relit a sa
    # reference. Sans ce volet, un bandeau lu au mauvais endroit passerait.
    table = cc.patch_values.get_patch_values_table("patch-values-4")
    references = {valeur.value_id: valeur.rgb for valeur in table.values}
    for value_id, triplet in lu:
        attendu = np.asarray(references[value_id][::-1], dtype=float) / 255.0
        assert np.allclose(triplet, attendu, atol=0.02), value_id

    # Frontiere: le meme raster declare sous un preset anterieur ne rend **rien**, et le
    # dit sous son nom -- « papier nu », qui est vrai de celui-la seulement.
    assert cc._sample_calibration_witness_band(
        page, template_id=template_id, patch_preset_id="patches-14-v3", dpi=dpi) == (
            (), cc.RAW_DIVERGENCE_BAND_NOT_PRINTED)
    # Et un preset absent ne rend rien non plus, sans lever: l'appelant n'a pas su dire.
    assert cc._sample_calibration_witness_band(
        page, template_id=template_id, patch_preset_id=None, dpi=dpi) == (
            (), cc.RAW_DIVERGENCE_BAND_NO_PRESET)


def _page_de_calibration_peinte(template_id: str, preset_id: str, dpi: int):
    """Raster de synthese d'une page de calibration, bandeau peint a ses references."""
    from mixed_media_utility import page_templates

    spec = page_templates.get_template(template_id)
    largeur, hauteur = page_templates.page_size_px(spec, dpi)
    page = np.full((hauteur, largeur, 3), 255, np.uint8)
    for pastille in patch_presets.resolve_calibration_page_witnesses(
            template_id, preset_id):
        x0 = int(round(pastille.x_mm / 25.4 * dpi))
        y0 = int(round(pastille.y_mm / 25.4 * dpi))
        cote = int(round(pastille.size_mm / 25.4 * dpi))
        page[y0:y0 + cote, x0:x0 + cote] = np.asarray(
            pastille.rgb[::-1], dtype=np.uint8)
    return page


def test_les_cinq_regimes_du_bandeau_sortent_chacun_sous_son_nom():
    """`EPIC5-ARB-104`: cinq regimes physiquement distincts, cinq motifs distincts.

    Le defaut corrige: la fonction rendait `()` dans les cinq, son propre docstring prenant
    soin de les nommer un a un -- mais **la valeur de retour ne portait pas le nom**, donc
    l'appelant ne pouvait pas les distinguer. Deux d'entre eux rendaient le manifest faux
    (bandeau ampute et preset inconnu: il y a de l'encre, et le manifest declarait « papier
    nu »).

    Les cinq sont pris **par le chemin de production** -- la fonction que
    `fit_lot_correction_from_page` appelle --, jamais par les gardes unitaires en dessous:
    c'est la difference qui a laisse passer le finding 10 du triage, ou le mutant qui retire
    la garde de `calibration_page_carries_witness_band` etait tue par un test appelant cette
    garde en direct et par rien d'autre.
    """
    template_id, dpi = "tpl-a4-portrait-8f-v2", 300
    page = _page_de_calibration_peinte(template_id, "patches-17-v4", dpi)
    v1 = next(
        identifiant for identifiant in page_templates.known_template_ids()
        if patch_presets.calibration_page_refusal(identifiant) is not None)

    # Le raster ampute: la moitie droite de la page manque, donc les 17 temoins de la
    # colonne de droite tombent hors page. Il y a bel et bien de l'encre sur la feuille.
    largeur_amputee = page.shape[1] // 2
    ampute = np.ascontiguousarray(page[:, :largeur_amputee])

    regimes = {
        cc.RAW_DIVERGENCE_BAND_NO_PRESET: cc._sample_calibration_witness_band(
            page, template_id=template_id, patch_preset_id=None, dpi=dpi),
        cc.RAW_DIVERGENCE_BAND_NOT_PRINTED: cc._sample_calibration_witness_band(
            page, template_id=template_id, patch_preset_id="patches-14-v3", dpi=dpi),
        cc.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN: cc._sample_calibration_witness_band(
            page, template_id=template_id, patch_preset_id="patches-17-v4-typo",
            dpi=dpi),
        cc.RAW_DIVERGENCE_BAND_PLACEMENT_UNDEFINED: cc._sample_calibration_witness_band(
            page, template_id=v1, patch_preset_id="patches-17-v4", dpi=dpi),
        cc.RAW_DIVERGENCE_BAND_CROPPED: cc._sample_calibration_witness_band(
            ampute, template_id=template_id, patch_preset_id="patches-17-v4", dpi=dpi),
    }
    for attendu, (temoins, motif) in regimes.items():
        assert temoins == (), attendu
        assert motif == attendu, (attendu, motif)
    # Cinq motifs deux a deux distincts, et le vocabulaire les enumere tous: une addition
    # muette au manifest ne peut pas passer par la.
    assert len(set(regimes)) == 5
    assert set(regimes) == set(cc.RAW_DIVERGENCE_BAND_REASONS)
    assert len(cc.RAW_DIVERGENCE_BAND_REASONS) == 5
    # Aucun d'eux n'est le motif d'une feuille absente: la feuille, elle, a ete lue.
    assert cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET not in regimes


def test_le_preset_inconnu_ne_fait_plus_taire_la_mesure_en_silence():
    """Finding 10 du triage: la garde levee **expres** etait avalee par son appelant.

    `calibration_page_carries_witness_band` passe par `get_patch_preset` dans le seul but
    de lever sur un identifiant inconnu -- son commentaire dit « les confondre ferait taire
    la mesure sur une faute de frappe, sans un mot ». L'unique appelant de production
    rangeait `UnknownPatchPresetError` avec les refus de pose et rendait `()`: la faute de
    frappe redevenait exactement le silence que la garde existe pour empecher, et
    l'asymetrie etait entiere -- cote planche d'images, le meme preset inconnu donne
    `FAILURE_PLACEMENT_UNDEFINED`.

    Le volet qui mord: le preset inconnu et le preset **sans bandeau** ne sortent pas sous
    le meme motif. Retirer la garde de `calibration_page_carries_witness_band` fait tomber
    le premier sur le second, et ce test rougit -- ce qu'aucun test du chemin de production
    ne faisait.
    """
    template_id, dpi = "tpl-a4-portrait-8f-v2", 300
    page = _page_de_calibration_peinte(template_id, "patches-17-v4", dpi)

    _rien, inconnu = cc._sample_calibration_witness_band(
        page, template_id=template_id, patch_preset_id="patches-17-v4-typo", dpi=dpi)
    _rien, sans_bandeau = cc._sample_calibration_witness_band(
        page, template_id=template_id, patch_preset_id="patches-14-v3", dpi=dpi)

    assert inconnu == cc.RAW_DIVERGENCE_BAND_PRESET_UNKNOWN
    assert sans_bandeau == cc.RAW_DIVERGENCE_BAND_NOT_PRINTED
    assert inconnu != sans_bandeau
    # Et la garde elle-meme leve toujours: le motif est une **traduction** du refus au
    # niveau ou il ne peut pas couter la correction du lot, jamais sa suppression.
    with pytest.raises(patch_presets.UnknownPatchPresetError):
        patch_presets.calibration_page_carries_witness_band("patches-17-v4-typo")


def test_un_profil_de_chaine_qui_porte_un_motif_a_bien_vu_sa_page_de_calibration():
    """Second etage d'`EPIC5-ARB-104`: le profil cessait de dire que sa page a ete lue.

    `profile_to_document` omet le champ vide, la relecture rend une suite vide, et la chaine
    sortait ensuite `raw_divergence_no_calibration_sheet` -- « aucune feuille de calibration
    dans ce scan » -- alors que sa page **a bien ete lue** et que sa correction vient
    d'elle. Le profil persistait la faussete, ce que le commentaire voisin revendique
    fermer (`EPIC5-ARB-70`).

    Depuis, `None` ne reste vrai que d'un profil qui ne dit **rien** du bandeau -- ecrit
    avant que la mesure existe. Un profil qui porte un motif rend une mesure vide **avec**
    son motif, et le manifest nomme le vrai regime.
    """
    muet = cc.LotCorrection(
        source_page_id="p0", template_id="tpl-a4-portrait-8f-v2",
        correction_form_id=cc.ACTIVE_CORRECTION_FORM_ID)
    rogne = cc.LotCorrection(
        source_page_id="p0", template_id="tpl-a4-portrait-8f-v2",
        correction_form_id=cc.ACTIVE_CORRECTION_FORM_ID,
        witness_band_reason=cc.RAW_DIVERGENCE_BAND_CROPPED)

    assert cc.calibration_witness_raw_for_lot(muet, from_chain_profile=True) is None
    porte = cc.calibration_witness_raw_for_lot(rogne, from_chain_profile=True)
    assert porte is not None and not porte
    assert cc.witness_band_reason_of(porte) == cc.RAW_DIVERGENCE_BAND_CROPPED

    # Et le motif atteint le manifest: « feuille lue, bandeau rogne », jamais « aucune
    # feuille de calibration ».
    verdict = cc.assess_raw_divergence(
        sheet_raw=_FEUILLE_CALIBRATION, calibration_raw=dict(porte),
        calibration_band_reason=cc.witness_band_reason_of(porte),
        page_id="lot-p1", source_page_id="lot-p0")
    assert verdict.reason == cc.RAW_DIVERGENCE_BAND_CROPPED
    assert verdict.reason != cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET
    assert verdict.mean_raw_de76 is None and verdict.exceeds is None

    # La feuille lue **dans cette passe** garde son regime: motif porte, jamais `None`.
    dans_la_passe = cc.calibration_witness_raw_for_lot(muet, from_chain_profile=False)
    assert dans_la_passe is not None and not dans_la_passe
    assert cc.witness_band_reason_of(dans_la_passe) == cc.RAW_DIVERGENCE_BAND_NOT_PRINTED


def test_l_ecart_brut_s_apparie_par_identifiant_et_non_par_position():
    """Famille `M33` / `M25`, septieme occurrence evitee: six valeurs, ordres differents.

    Les deux feuilles portent les **memes** valeurs dans des ordres d'insertion opposes, et
    une seule d'entre elles est deplacee -- jamais la premiere. Un appariement positionnel
    comparerait `primary-red` a `secondary-magenta` et rendrait un ecart enorme sur les six
    valeurs; l'appariement par identifiant rend l'ecart d'une seule, divise par six.
    """
    deplacee = "neutral-065"
    assert list(_FEUILLE_CALIBRATION)[0] != deplacee, (
        "la valeur visee est en premiere position: un `find` fautif ne se demasquerait pas")
    planche = _feuille_decalee(value_id=deplacee, delta=0.20)
    mesure = cc.assess_raw_divergence(
        sheet_raw=planche,
        calibration_raw=_dans_un_autre_ordre(_FEUILLE_CALIBRATION),
        page_id="lot-p1", source_page_id="lot-p0")
    assert mesure.paired_value_ids == tuple(sorted(_FEUILLE_CALIBRATION))
    assert mesure.excluded == ()
    # Le meme ecart, calcule sur la seule valeur deplacee et divise par six: c'est la
    # signature numerique de l'appariement correct, et elle est **derivee** plutot que
    # recopiee -- un attendu en dur suivrait n'importe quelle permutation.
    seule = color_metrics.raw_divergence_de76(
        sheet_raw={deplacee: planche[deplacee]},
        calibration_raw={deplacee: _FEUILLE_CALIBRATION[deplacee]})
    assert mesure.mean_raw_de76 == pytest.approx(
        seule.mean_delta_e76 / len(_FEUILLE_CALIBRATION), rel=1e-9)


def test_les_trois_regimes_sans_mesure_ne_se_confondent_pas_et_ne_valent_pas_zero():
    """`None`, `{}` et « aucune paire lisible » sont trois faits, jamais un ecart nul.

    Un zero est la lecture de **deux feuilles identiques**, pas celle d'une mesure qui n'a
    pas eu lieu. Le booleen `exceeds` reste `None` dans les trois cas: un verdict pose sur
    une grandeur qu'on n'a pas mesuree est le defaut d'`EPIC5-ARB-52`.
    """
    commun = dict(sheet_raw=_FEUILLE_CALIBRATION, page_id="lot-p1",
                  source_page_id="lot-p0")
    absente = cc.assess_raw_divergence(calibration_raw=None, **commun)
    vide = cc.assess_raw_divergence(calibration_raw={}, **commun)
    # Aucune valeur commune: la matiere etait la, la lecture n'a rien apparie.
    disjointe = cc.assess_raw_divergence(
        calibration_raw={"lattice-128-128-128": (0.5, 0.5, 0.5)}, **commun)

    assert absente.reason == cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET
    assert vide.reason == cc.RAW_DIVERGENCE_BAND_NOT_PRINTED
    assert disjointe.reason == cc.RAW_DIVERGENCE_NO_PAIR
    assert len({absente.reason, vide.reason, disjointe.reason}) == 3
    for sans_mesure in (absente, vide, disjointe):
        assert sans_mesure.mean_raw_de76 is None
        assert sans_mesure.exceeds is None
        # Le seuil, lui, est **toujours** porte: il vient du registre et ne depend pas de
        # la reussite de la mesure.
        assert sans_mesure.divergence_id == color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID
        assert sans_mesure.threshold_de76 == color_metrics.get_raw_divergence_guard(
            color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID).max_mean_raw_de76


def test_une_valeur_illisible_est_ecartee_et_declaree_jamais_remplacee_par_zero():
    """AC 2: une moyenne calculee sur un sous-ensemble silencieux est un faux succes."""
    planche = dict(_FEUILLE_CALIBRATION)
    planche["secondary-cyan"] = None
    del planche["primary-blue"]
    mesure = cc.assess_raw_divergence(
        sheet_raw=planche, calibration_raw=_FEUILLE_CALIBRATION,
        page_id="lot-p1", source_page_id="lot-p0")
    ecartees = dict(mesure.excluded)
    assert ecartees == {
        "secondary-cyan": color_metrics.RAW_EXCLUSION_UNREADABLE_SHEET,
        "primary-blue": color_metrics.RAW_EXCLUSION_ABSENT_SHEET,
    }
    assert set(mesure.paired_value_ids) == set(_FEUILLE_CALIBRATION) - set(ecartees)
    # Les quatre restantes sont identiques d'une feuille a l'autre, donc l'ecart vaut
    # zero -- et ce zero-la est une **mesure**, ce qui est exactement ce qui le distingue
    # des trois regimes du test precedent.
    assert mesure.mean_raw_de76 == pytest.approx(0.0, abs=1e-9)
    assert mesure.exceeds is False


# ---------------------------------------------------------------------------
# AC 4 -- au-dela du seuil: avertir, chiffre, et appliquer quand meme
# ---------------------------------------------------------------------------


def test_l_avertissement_porte_l_ecart_le_seuil_et_l_identifiant_de_registre():
    """AC 4, les trois nombres. Et il **dit** que la correction a ete appliquee."""
    mesure = cc.assess_raw_divergence(
        sheet_raw=_feuille_decalee(value_id="neutral-065", delta=0.45),
        calibration_raw=_FEUILLE_CALIBRATION,
        page_id="lot-p1", source_page_id="lot-p0")
    assert mesure.exceeds is True, mesure.mean_raw_de76
    message = cc.raw_divergence_warning_message(mesure)
    assert f"{mesure.mean_raw_de76:.2f}" in message
    assert f"{mesure.threshold_de76:.2f}" in message
    assert mesure.divergence_id in message
    assert "lot-p1" in message and "lot-p0" in message
    assert "appliquee quand meme" in message


@pytest.mark.parametrize("interdit", ["refus", "rescann"])
def test_l_avertissement_ne_parle_ni_de_refus_ni_de_rescan(interdit):
    """AC 4, frontiere negative sur le **message complet** et non sur un fragment.

    Mesure du terrain, 2026-08-17: le message de 5.22 s'affichait sur une planche
    **effectivement livree** et disait « rescannez cette page ». L'operateur repartait
    reprendre une feuille qui venait d'etre ecrite sur le disque.
    """
    mesure = cc.assess_raw_divergence(
        sheet_raw=_feuille_decalee(value_id="neutral-065", delta=0.45),
        calibration_raw=_FEUILLE_CALIBRATION,
        page_id="lot-p1", source_page_id="lot-p0")
    assert interdit not in cc.raw_divergence_warning_message(mesure).lower()


def test_un_avertissement_chiffre_sans_chiffre_leve_au_lieu_d_ecrire_none():
    """Une divergence non mesuree n'a pas de message: la fonction refuse de l'inventer."""
    with pytest.raises(ValueError) as refus:
        cc.raw_divergence_warning_message(cc.RawDivergenceAssessment(
            page_id="lot-p1", source_page_id="lot-p0",
            divergence_id="color-divergence-2", threshold_de76=5.0,
            mean_raw_de76=None, reason=cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET))
    assert cc.RAW_DIVERGENCE_NO_CALIBRATION_SHEET in str(refus.value)


def test_la_frontiere_du_seuil_brut_est_stricte_et_le_mutant_meurt_par_injection():
    """AC 4: un ecart **exactement egal** au seuil n'avertit pas. Verifie par injection.

    **Pas par relecture, et c'est le defaut trouve sur 5.22**: le test neuf y survivait au
    mutant `>` / `>=` que l'ancien tuait. Le mutant est donc reellement injecte dans une
    copie jetable de `color_metrics`, et le sous-processus doit **echouer** -- s'il
    reussit, c'est que la frontiere n'est verifiee nulle part.

    Le seuil est lu au registre et jamais recopie: c'est lui, exactement, qui est confronte
    a la fonction, donc une revision de la valeur n'invalide pas ce test.
    """
    seuil = color_metrics.get_raw_divergence_guard(
        color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID).max_mean_raw_de76
    assert color_metrics.raw_divergence_exceeds(seuil) is False
    # `1e-12` et non l'ulp suivant: douze ordres de grandeur sous le seuil restent sa
    # frontiere, et une addition d'un ulp serait reabsorbee par la comparaison.
    assert color_metrics.raw_divergence_exceeds(seuil + 1e-12) is True
    assert color_metrics.raw_divergence_exceeds(seuil - 1e-12) is False


def test_le_mutant_de_la_frontiere_stricte_est_effectivement_tue(tmp_path):
    """Le volet **injection** du test precedent, isole pour qu'il soit lisible seul.

    Une copie du module recoit `>=` a la place de `>` dans `raw_divergence_exceeds`, et on
    verifie que l'assertion d'egalite tombe. Sans ce sous-processus, « le test tue le
    mutant » resterait une affirmation.
    """
    source = (SRC / "mixed_media_utility" / "color_metrics.py").read_text(encoding="utf-8")
    ancien = ("    return float(mean_raw_de76) > "
              "get_raw_divergence_guard(divergence_id).max_mean_raw_de76")
    assert source.count(ancien) == 1, (
        "la ligne de frontiere a change de redaction: le mutant ne s'injecte plus au bon "
        "endroit, donc ce test ne mesurerait plus rien")
    mute = tmp_path / "mixed_media_utility"
    mute.mkdir()
    paquet = SRC / "mixed_media_utility"
    for fichier in paquet.glob("*.py"):
        (mute / fichier.name).write_text(fichier.read_text(encoding="utf-8"),
                                         encoding="utf-8")
    (mute / "io").mkdir()
    for fichier in (paquet / "io").glob("*.py"):
        (mute / "io" / fichier.name).write_text(fichier.read_text(encoding="utf-8"),
                                                encoding="utf-8")
    (mute / "color_metrics.py").write_text(
        source.replace(ancien, ancien.replace(" > ", " >= ")), encoding="utf-8")

    script = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, sys.argv[1])
        from mixed_media_utility import color_metrics as cm
        seuil = cm.get_raw_divergence_guard(
            cm.ACTIVE_RAW_DIVERGENCE_GUARD_ID).max_mean_raw_de76
        assert cm.raw_divergence_exceeds(seuil) is False, "mutant survivant"
        """
    )
    resultat = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True, text=True, timeout=120)
    assert resultat.returncode != 0, (
        "le mutant `>=` survit: l'egalite au seuil n'est verifiee par aucune assertion")
    assert "mutant survivant" in resultat.stderr


# ---------------------------------------------------------------------------
# AC 7 -- la garde de degradation maximale, et la pastille coupable
# ---------------------------------------------------------------------------


def test_la_garde_de_degradation_est_inerte_sur_le_lot_de_reference_et_mordante_au_dela():
    """AC 7, epinglage **par les deux bouts**.

    Une garde annoncee sans son domaine d'activation n'est pas une garantie. Les deux
    bouts sont donc mesures ensemble:

    * **inerte** sur le profil reellement ajuste au lot de reference `chendj-mat`, dont la
      degradation maximale vaut `+15,798` dE76 (mesure du 2026-08-17, verdict consigne dans
      `versions/calibration/600-tiff-41f9fa6c9e08.json`). Cette valeur est reprise ici
      telle quelle parce qu'elle est un **fait de terrain** et non un attendu de code;
    * **mordante** sur un profil construit pour la declencher, au-dela du plafond
      enregistre.
    """
    plafond = color_metrics.get_max_degradation_guard(
        color_metrics.ACTIVE_MAX_DEGRADATION_GUARD_ID).max_degradation_de76
    lot_de_reference = 15.798197008324976
    assert lot_de_reference < plafond, (
        "le plafond est passe sous la degradation du lot que le depot livre: la garde "
        "avertirait sur la correction de reference, donc en permanence")
    assert color_metrics.max_degradation_exceeds(lot_de_reference) is False
    assert color_metrics.max_degradation_exceeds(plafond) is False
    assert color_metrics.max_degradation_exceeds(plafond + 1e-12) is True
    # Une mesure absente rend `False` **et le dit**: avertir sur une grandeur non mesuree
    # serait inventer un chiffre.
    assert color_metrics.max_degradation_exceeds(None) is False


def test_l_avertissement_de_degradation_nomme_la_pastille_coupable():
    """AC 7: « une pastille est degradee de 18 dE76 » n'est pas actionnable, son nom l'est.

    La pastille nommee est celle que la mesure du 2026-08-17 designe sur le lot reel --
    `lattice-188-128-188`, un magenta clair --, ce qui rend le test lisible a cote du
    compte rendu de la story.
    """
    plafond = color_metrics.get_max_degradation_guard(
        color_metrics.ACTIVE_MAX_DEGRADATION_GUARD_ID).max_degradation_de76
    verdict = _verdict(max_degradation=plafond + 8.0)
    message = cc.max_degradation_warning_message(verdict, page_id="lot-p1")
    assert "lattice-188-128-188" in message
    assert f"{verdict.max_degradation_de76:+.2f}" in message
    assert f"{plafond:.2f}" in message
    assert color_metrics.ACTIVE_MAX_DEGRADATION_GUARD_ID in message
    assert "lot-p1" in message
    # Un verdict **sans detail** ne peut pas nommer de pastille: il le dit au lieu
    # d'inventer un identifiant, ce qui serait pire qu'un silence.
    plat = cc.AcceptanceVerdict(
        status="applied", mean_delta_e=1.0, max_delta_e=2.0, mean_delta_e_before=3.0,
        acceptance_id=color_metrics.ACTIVE_COLOR_ACCEPTANCE_ID,
        max_degradation_de76=plafond + 8.0)
    assert "non identifiee" in cc.max_degradation_warning_message(plat, page_id="lot-p1")


# ---------------------------------------------------------------------------
# AC 5 -- le refus est le geste explicite, et il ne bloque jamais un script
# ---------------------------------------------------------------------------


class _Flux:
    """Une entree standard dont on choisit la nature et le contenu."""

    def __init__(self, tty: bool, lignes: tuple[str, ...] = ()) -> None:
        self._tty = tty
        self._lignes = list(lignes)

    def isatty(self) -> bool:
        return self._tty


def test_hors_terminal_aucune_invite_n_est_posee(monkeypatch):
    """AC 5: une invite qui bloque un script est une panne, pas une precaution.

    Les trois formes de « pas de terminal » sont couvertes, et pas seulement le pipe: un
    `sys.stdin` a `None` (service, interpreteur sans entree) et un flux dont `isatty` leve
    (descripteur ferme) valent tous les deux « je ne sais pas si quelqu'un est la », et la
    seule reponse sure a cette question est de ne pas attendre de reponse.
    """
    monkeypatch.setattr(sys, "stdin", _Flux(tty=False))
    assert cli._stdin_is_interactive() is False
    monkeypatch.setattr(sys, "stdin", None)
    assert cli._stdin_is_interactive() is False

    class _Ferme:
        def isatty(self):
            raise ValueError("I/O operation on closed file")

    monkeypatch.setattr(sys, "stdin", _Ferme())
    assert cli._stdin_is_interactive() is False
    # Et le temoin positif, sans lequel les trois lignes ci-dessus seraient tenues par une
    # fonction qui rend toujours `False`.
    monkeypatch.setattr(sys, "stdin", _Flux(tty=True))
    assert cli._stdin_is_interactive() is True


@pytest.mark.parametrize(
    "reponse, applique",
    [("y", True), ("Y", True), ("o", True), ("", True), ("oui", True),
     ("n", False), ("N", False), ("non", False), ("  n  ", False)],
)
def test_l_invite_applique_par_defaut_et_seul_un_non_garde_le_brut(
        monkeypatch, reponse, applique):
    """AC 5: `Y` applique, `N` livre le brut, et **le defaut est appliquer**.

    La ligne vide -- l'operateur qui frappe Entree -- applique: `EPIC5-ARB-82` decision 6,
    « le geste par defaut est celui qui sert l'utilisateur ». Une reponse incomprise
    applique aussi, et on ne boucle pas: une invite qui insiste est un cran de plus vers
    l'invite qui bloque.
    """
    monkeypatch.setattr("builtins.input", lambda: reponse)
    assert cli._ask_apply_correction(logging.getLogger("test-invite")) is applique


def test_une_fin_de_flux_sur_l_invite_applique_au_lieu_de_tomber(monkeypatch):
    """Un `Ctrl-D` ou un terminal qui se ferme ne doit pas faire tomber la commande."""
    def _eof():
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    assert cli._ask_apply_correction(logging.getLogger("test-invite")) is True


def test_l_invite_n_est_posee_que_lorsqu_une_correction_existe_reellement(monkeypatch):
    """AC 5, et le piege que l'ordre des lignes ferme.

    L'invite est posee **apres** la resolution de la correction du lot, jamais avant.
    Posee avant, la commande demanderait a un humain de trancher sur une correction que le
    lot n'a pas -- une question dont aucune reponse ne change rien, et qui apprend a
    repondre sans lire.

    La mesure est faite sur le **texte source** parce que le fait est un ordre de lignes:
    l'appel a `_ask_apply_correction` doit venir apres la resolution de `lot_correction`,
    et il doit etre garde par la disponibilite de cette correction. Un test d'execution
    demanderait un scan complet, ce que l'AC 9 exclut de ce fichier.
    """
    # **Story 11.4b (lot S1): la mesure suit le corps.** La sequence d'ecriture
    # vit dans le module de coeur `scan_write`, qui n'a pas le droit de lire
    # `stdin` (sous une boucle d'evenements, un appel bloquant y gele
    # l'interface entiere, `EPIC7-ARB-106`). L'invite `Y/N` elle-meme est
    # restee chez la CLI et entre par un rappel nomme ; ce que ce test mesure
    # -- elle n'est ATTEINTE qu'une fois la disponibilite de la correction
    # connue -- est inchange, et il est meme plus fort : le rappel n'est appele
    # que dans la branche `elif lot_correction.available:`, donc aucun autre
    # chemin ne peut plus le poser.
    source = (SRC / "mixed_media_utility" / "scan_write.py").read_text(
        encoding="utf-8")
    invite = source.index(
        "apply_correction = bool(demander_l_application_de_la_correction())")
    # **Le nom de la resolution a change avec l'AC 12** (`EPIC5-ARB-83`): la correction
    # ne vient plus du profil apparie a une chaine derivee, mais du profil que
    # l'operateur **designe**. L'ordre que ce test mesure, lui, est inchange -- l'invite
    # se pose apres que la disponibilite de la correction est connue.
    resolution = source.index("lot_correction = _resolve_designated_correction(")
    disponible = source.index("elif lot_correction.available:")
    assert resolution < disponible < invite, (
        "l'invite est posee avant que la disponibilite de la correction soit connue")
    # Et le refus redescend dans l'objet de correction, sinon le manifest perdrait le
    # motif: les frames sortiraient brutes sans que le document dise pourquoi.
    assert "lot_correction, correction_requested=False" in source
    # Volet symetrique de la frontiere `stdin` (story 11.4b, AC 2.1): l'invite
    # est bien restee du cote qui a le droit de la poser.
    assert "_ask_apply_correction" not in source
    assert "_ask_apply_correction(logger)" in (
        SRC / "mixed_media_utility" / "cli.py").read_text(encoding="utf-8")


def test_le_drapeau_de_repli_est_nomme_par_le_module_qui_possede_la_decision():
    """AC 5: jamais un litteral recopie dans `cli.py`, et aucun reglage numerique expose.

    La frontiere negative porte sur le **texte source** de `cli.py`: le nom du drapeau ne
    doit y figurer qu'a travers la constante. Un litteral recopie serait invisible a
    l'execution et divergerait a la premiere revision du nom.
    """
    source = (SRC / "mixed_media_utility" / "cli.py").read_text(encoding="utf-8")
    assert f'"{cc.RAW_OUTPUT_FLAG}"' not in source
    assert f"'{cc.RAW_OUTPUT_FLAG}'" not in source
    assert "color_calibration.RAW_OUTPUT_FLAG" in source
    # Aucun reglage numerique, frontiere existante conservee: on refuse une correction, on
    # ne choisit pas un seuil.
    # Frontiere negative sur les **noms d'options reellement declares**, et non sur le
    # texte brut du fichier: la prose des commentaires cite `--seuil` et `--tolerance`
    # precisement pour dire qu'ils sont interdits, et un balayage textuel se declencherait
    # dessus -- c'est le meme piege que la frontiere de l'AC 2, deja paye a la tache 2.
    declares = {noeud.value for noeud in ast.walk(ast.parse(source))
                if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and noeud.value.startswith("--")}
    for interdit in ("--seuil", "--tolerance", "--tolerance-de-divergence"):
        assert interdit not in declares, interdit
    assert any(nom.startswith("--") for nom in declares), (
        "aucune option litterale trouvee: le balayage ne mesure plus rien")


def test_les_deux_drapeaux_de_la_commande_scan_sont_reconnus_et_distincts(tmp_path,
                                                                          capsys):
    """Le drapeau neuf est **branche**, et il ne remplace pas celui de 5.22.

    Un script ecrit sous 5.22 passe `--appliquer-la-correction-de-calibration-telle-quelle`:
    la commande doit continuer de l'accepter, sans quoi la story casserait un script pour
    une option devenue sans effet.

    La reconnaissance se mesure par le **code de sortie d'argparse**: un drapeau inconnu
    sort en `SystemExit(2)`, un drapeau connu poursuit et echoue plus loin sur le projet
    inexistant. Le temoin negatif est ce qui rend l'assertion concluante -- sans lui, elle
    serait tenue par une commande qui accepte n'importe quoi.
    """
    argv = ["scan", "--project", str(tmp_path / "absent"), "--scan",
            str(tmp_path / "absent"), "--dpi", "600"]
    with pytest.raises(SystemExit) as inconnu:
        cli.main([*argv, "--drapeau-qui-n-existe-pas"])
    assert inconnu.value.code == 2
    capsys.readouterr()
    for drapeau in (cc.RAW_OUTPUT_FLAG, cc.DIVERGENCE_BYPASS_FLAG):
        code = cli.main([*argv, drapeau])
        assert code != 2, drapeau
        capsys.readouterr()
    assert cc.RAW_OUTPUT_FLAG != cc.DIVERGENCE_BYPASS_FLAG


# ---------------------------------------------------------------------------
# AC 3 -- frontiere negative: plus aucun chemin ne refuse pour divergence
# ---------------------------------------------------------------------------


def test_au_dela_du_seuil_brut_la_correction_bouge_reellement_les_pixels():
    """AC 3 **sur les pixels, dans le regime divergent**, qui n'etait mesure nulle part.

    Trou trouve par l'injection par AC de l'AC 9 (`EPIC5-ARB-100`, 2026-08-19). Deux
    mutants distincts de l'AC 3 vivaient dans la meme zone, et le lot n'en tuait qu'un:

    * substituer un **refus** (`_not_applied_page(NOT_APPLIED_PAGE_DIVERGES, ...)`) au-dela
      du seuil brut etait tue -- mais par la frontiere **textuelle** ci-dessous seulement,
      qui cherche le nom de la constante dans `src/`;
    * substituer un **profil identite** au meme endroit, sans citer aucune constante,
      **survivait a tout**: aux dix fichiers du lot de la story, et jusqu'aux substituts
      d'octets de l'AC 11. Une sonde posee au meme endroit (`raise` inconditionnel) l'a
      confirme: aucun test du depot n'atteignait `calibrate_page` avec
      `raw_divergence.exceeds` vrai. La bascule de 5.23 -- « la correction s'applique
      **quel que soit** l'ecart mesure » -- n'etait donc pas mesuree dans le seul regime
      ou elle change quelque chose.

    Ce que ce test exige, et pourquoi chaque assertion est necessaire: la planche diverge
    **reellement** en brut (sinon le test confirmerait la bascule sur une page qui ne
    l'exerce pas), elle sort `applied`, et le profil retenu **transforme un triplet
    connu** -- egal a ce que le profil importe en fait, et different de l'entree. Un
    profil identite passerait les deux premieres et tombe sur la troisieme.

    La planche visee est en **deuxieme** position des trois (regle des fabriques): une
    garde qui ne regarderait que la premiere page ne survit pas a cet ordre.
    """
    from test_calibration_page_source import (  # noqa: E402
        PRESET, TEMPLATE, _DEVIANT_PRESS, _NOMINAL_PRESS, _calibration_profile, _press)
    from test_color_calibration import _synthetic_rectified_page  # noqa: E402

    profil = _calibration_profile()
    # Les temoins de la page de calibration, deliberement **loin** de ceux de la planche:
    # +0,20 en sRGB encode sur chaque canal, soit tres au-dela des 5,0 dE76 du registre.
    table = cc.patch_values.get_patch_values_table(
        patch_presets.get_patch_preset(PRESET).values_version)
    temoins_calibration = {
        valeur.value_id: tuple(min(1.0, composante / 255.0 + 0.20)
                               for composante in valeur.rgb[::-1])
        for valeur in table.values
    }

    lot = [
        ("page-1", _NOMINAL_PRESS),
        ("page-2", _DEVIANT_PRESS),
        ("page-3", _press(0.929, (0.0251, 0.0241, 0.0259))),
    ]
    resultats = {}
    for nom, presse in lot:
        page = _synthetic_rectified_page(template_id=TEMPLATE, preset_id=PRESET,
                                         distort=presse)
        resultats[nom] = cc.calibrate_page(
            page, template_id=TEMPLATE, patch_preset_id=PRESET, dpi=600, page_id=nom,
            imported_profile=profil, imported_source_page_id="calibration-0",
            calibration_witness_raw=temoins_calibration)

    vise = resultats["page-2"]
    seuil = color_metrics.get_raw_divergence_guard(
        color_metrics.ACTIVE_RAW_DIVERGENCE_GUARD_ID).max_mean_raw_de76
    # 1. Le regime divergent est **reellement** atteint, et il l'est sur les trois pages:
    #    sans cela le test mesurerait le chemin nominal sous un autre nom.
    for nom in ("page-1", "page-2", "page-3"):
        assert resultats[nom].raw_divergence.exceeds is True, nom
        assert resultats[nom].raw_divergence.mean_raw_de76 > seuil, nom
    # 2. La correction s'applique quand meme -- le champ, et l'absence des deux motifs.
    assert vise.status == "applied"
    assert vise.not_applied_reason is None
    assert vise.failure_reason is None
    assert vise.profile is not None
    # 3. **Les pixels.** Le profil retenu est celui qui a ete importe et il transforme:
    #    un profil identite glisse au-dela du seuil tombe ici et nulle part ailleurs.
    lineaire = np.array([[0.30, 0.45, 0.60]], dtype=float)
    obtenu = np.asarray(vise.profile.apply_linear(lineaire), dtype=float)
    attendu = np.asarray(profil.apply_linear(lineaire), dtype=float)
    assert np.allclose(obtenu, attendu, atol=1e-12), (obtenu, attendu)
    assert not np.allclose(obtenu, lineaire, atol=1e-3), (
        "le profil retenu ne bouge aucun pixel: une identite a ete substituee au-dela "
        "du seuil brut, ce que l'AC 3 interdit")



def test_aucun_chemin_de_production_ne_rend_not_applied_pour_divergence():
    """AC 3, frontiere negative, verifiee sur le **texte source** de la production.

    Deux volets, et le second est celui qui compte: le motif `NOT_APPLIED_PAGE_DIVERGES`
    reste **enregistre** -- c'est le vocabulaire des manifests deja ecrits sur le disque
    d'Egan, et le relire doit rester possible -- mais il n'est plus **produit** par aucune
    ligne de `src/`. Une constante conservee et une constante encore posee sont deux
    choses, et seule la seconde ferait revenir le refus.
    """
    assert cc.NOT_APPLIED_PAGE_DIVERGES == "page_diverges_without_explicit_apply"
    producteurs = []
    for fichier in sorted((SRC / "mixed_media_utility").rglob("*.py")):
        for numero, ligne in enumerate(
                fichier.read_text(encoding="utf-8").splitlines(), start=1):
            nu = ligne.strip()
            if nu.startswith("#") or "NOT_APPLIED_PAGE_DIVERGES" not in nu:
                continue
            # La definition elle-meme n'est pas un producteur.
            if nu.startswith("NOT_APPLIED_PAGE_DIVERGES ="):
                continue
            producteurs.append(f"{fichier.name}:{numero}: {nu}")
    assert producteurs == [], producteurs
    # Le regime `not_applied` subsiste pour ses **autres** motifs, et le verifier ici est
    # ce qui empeche de lire la frontiere ci-dessus comme « plus rien n'est jamais
    # `not_applied` » -- ce qui serait une autre regression.
    assert cc.NOT_APPLIED_OPERATOR_OPT_OUT == "correction_declined_by_operator"


# ---------------------------------------------------------------------------
# AC 8 -- non-regression et frontiere de perimetre de la story
# ---------------------------------------------------------------------------

#: **Borne basse du perimetre de production de la story 5.23**: le `baseline_commit` que
#: le frontmatter de la story porte.
_BASELINE_5_23 = "ae6ac2f"

#: **Borne haute, epinglee le 2026-08-19** -- geste de cloture de la story, meme patron
#: que `test_chain_profile_scan._FIN_5_22` et que `_BORNE_HAUTE_DE_LA_STORY` de 5.19.
#:
#: Elle valait l'**arbre de travail** jusqu'ici, ce qui etait juste **pendant que la story
#: etait ouverte**: la frontiere mordait alors sur un fichier touche et non commite,
#: exactement celui qu'une revue de fin de story ne verrait pas. Cette redaction cesse
#: d'etre juste le jour ou la story se clot, et son cout est connu par deux precedents du
#: depot, pas par une crainte:
#:
#: * 5.16, bornee en bas seulement, mesurait « tout ce que le depot a touche depuis 5.16 »
#:   au lieu de « ce que 5.16 a touche »; la premiere story suivante qui a modifie un
#:   module de production l'a fait echouer, et 5.19 lui a ajoute sa borne haute
#:   (`_BORNE_HAUTE_DE_LA_STORY = "9b47f95"`), apres quoi elle est redevenue inoffensive
#:   sans rien perdre;
#: * 5.22, borne haute a `HEAD`, est devenue un faux positif permanent des le premier
#:   commit de 5.23 -- elle accusait `patch_presets.py`, `patch_values.py`,
#:   `page_templates.py` et `color_metrics.py` d'etre « en trop » dans le perimetre de
#:   5.22 alors qu'ils sont exactement dans celui de 5.23. Sa borne est epinglee depuis.
#:
#: Sans borne haute ici, **5.24 rougirait a son premier commit de production** pour un
#: perimetre qui n'est pas le sien (politique de revue, section 7, `EPIC5-ARB-95`): une
#: frontiere qui echoue pour le perimetre d'une autre story ne mesure plus rien, elle se
#: desapprend.
#:
#: `64d1299` est le **dernier commit de 5.23 qui touche `src/`** (`56a86ae`, le suivant,
#: ne touche que `tests/`), donc `ae6ac2f..64d1299` est, au caractere pres, le diff de
#: production que l'enumeration ci-dessous decrit. **Si un correctif de revue ulterieur de
#: 5.23 touche encore la production, c'est cette borne qu'on avance** -- avec le fichier
#: concerne et sa raison dans l'enumeration --, jamais la borne qu'on retire.
_FIN_5_23 = "64d1299"

#: Chacun porte sa raison, parce qu'une enumeration sans motif redevient une liste de
#: souhaits:
#:
#: * `patch_values.py`, `patch_presets.py`, `page_templates.py`, `pdf_composition.py` --
#:   taches 1 a 3: la table `patch-values-4`, le preset `patches-17-v4`, le bandeau de
#:   temoins porte par la bordure aussi sur la page de calibration, et le gate de lecture
#:   versionne qui dit quelles feuilles le portent reellement;
#: * `color_metrics.py` -- la mesure brute a brute et les deux registres neufs;
#: * `color_calibration.py` -- l'echantillonnage du bandeau de la page de calibration, la
#:   bascule de politique (plus aucun refus pour divergence) et les deux avertissements;
#: * `cli.py` -- le cablage des deux moities de la mesure, l'invite `Y/N`, le drapeau de
#:   repli et les deux avertissements au journal;
#: * `io/scan_manifest.py` -- l'enumeration du typage structurel, qui doit connaitre le
#:   bloc `raw_divergence` que la projection lit.
#:
#: **Elargissement declare le 2026-08-17 (AC 8bis) et le 2026-08-18 (mentions imprimees,
#: libelle de chaine au QR).** Six fichiers de plus, chacun avec son motif -- « un
#: elargissement doit se declarer, pas se glisser », et c'est ici qu'on le declare:
#:
#: * `io/payload.py` -- le contrat 2.3 lui-meme: les quatre champs que le role `c` ne
#:   porte plus (`CALIBRATION_ABSENT_FIELDS`, `project_id` compris depuis le 2026-08-18)
#:   et le champ qu'il est seul a porter (`scan_chain_label`). Il n'y avait pas
#:   d'alternative: une page qui declare une identite de lot est fausse au sens propre,
#:   et le contrat est le seul endroit qui puisse le dire une fois pour tous les
#:   lecteurs;
#: * `io/naming.py` -- le nom du PDF, qui portait le rush et le lot. Un projet porte
#:   desormais **autant de pages que de chaines de scan**, donc le nom porte le projet et
#:   la chaine, et le condensat qui les separe reprend la recette de `bounds_suffix`;
#: * `page_payload.py` -- le transport du libelle a travers la jonction. Aucune logique:
#:   un parametre de plus, non interprete;
#: * `scan_detection.py` -- deux acces nus (`payload["project_id"]`, et
#:   `IDENTITY_FIELDS` sur un payload refuse) qui levaient une `KeyError` **hors du bloc
#:   de capture** des qu'une page de calibration d'apres 5.23 etait lue: la feuille
#:   qu'Egan doit pouvoir scanner faisait tomber la detection entiere;
#: * `io/reconstruction.py` -- meme famille, cote relecture: les champs exiges d'un
#:   payload dependent desormais du role. La liste reste **entiere** pour une planche
#:   d'images. `_LOT_LEVEL_FIELDS` et `_check_lot_consistency` sont restes, eux, intacts
#:   au caractere -- ils etaient alors sous garde d'egalite au source depuis 5.16. Cette
#:   garde a ete **retiree** le 2026-08-19 (`EPIC5-ARB-95`): l'immobilite de ces deux
#:   definitions reste un fait de l'histoire de 5.23, elle n'est plus une contrainte
#:   opposable aux stories suivantes;
#: * `scan_output_frames.py` -- meme famille encore: `_lot_identity` lisait les quatre
#:   champs sur **toutes** les pages de la pile, page de calibration comprise. Elle ne
#:   les lit plus que sur les pages qui les declarent.
#:
#: Les quatre derniers ne sont pas des ajouts de fonctionnalite mais des **consequences
#: mecaniques** du retrait des champs: sans eux, la feuille se genere et ne se lit pas.
#:
#: **`color_pipeline.py` y est entre le 2026-08-18, et pas avant**: jusqu'a l'AC 13, la
#: bascule de politique n'avait effectivement demande aucune ligne a
#: `derive_lot_calibration_status` -- le refus par operateur passait par le chemin
#: `--cc off` qui existait deja, et l'enumeration etant **exacte**, l'y laisser par
#: prudence aurait fait echouer ce test. L'AC 13 (`EPIC5-ARB-88`) l'y fait entrer pour la
#: raison inverse: la garde qui ne servait qu'au refus pour divergence y est devenue
#: morte, et une garde morte se retire.
#: **Deux entrees ajoutees le 2026-08-18**, et l'enumeration etant exacte, elles se
#: declarent ici plutot que de faire rougir la frontiere:
#:
#: * `io/calibration_profile.py` -- le profil de chaine porte desormais la mesure
#:   **brute** de ses pastilles temoins (`witness_raw_bgr`). Sans ce champ, la
#:   comparaison brute a brute d'`EPIC5-ARB-82` n'etait calculable que si les deux
#:   feuilles se trouvaient dans la meme passe de scan, c'est-a-dire jamais dans le
#:   regime nominal de la calibration par chaine: mesure sur les vrais scans d'Egan le
#:   2026-08-18, le manifeste rendait `raw_divergence_no_calibration_sheet` sur une
#:   chaine pourtant calibree, sans aucune paire appariee;
#: * `qr_codes.py` -- second repli par reechantillonnage a la lecture du QR, ajoute le
#:   meme jour pour rattraper une feuille scannee a 300 dpi. Sans lui, la page de
#:   calibration reelle ne se decode pas et rien de ce qui precede ne s'observe.
#:
#: **Deux entrees ajoutees par l'AC 13** (`EPIC5-ARB-88`, retrait des deux restes
#: inertes), chacune avec son motif:
#:
#: * `color_pipeline.py` -- le cardinal des planches refusees et la garde qu'il
#:   nourrissait, tous deux morts depuis que l'AC 3 a supprime le refus pour divergence
#:   (voir le paragraphe ci-dessus, qui expliquait jusque-la son **absence**);
#: * `scan_chain.py` -- une seule docstring: la derivation de l'identite de chaine
#:   annoncait « surchargeable par le drapeau de l'operateur », et ce drapeau n'existe
#:   plus. Aucune ligne de code touchee, mais une documentation qui nomme une option
#:   retiree est exactement ce qui la fait chercher (meme regle que la frontiere du mot
#:   « seuil » de 5.16, qui porte sur le texte lu et non sur l'intention).
_FICHIERS_DE_PRODUCTION_5_23 = frozenset({
    "src/mixed_media_utility/cli.py",
    "src/mixed_media_utility/color_calibration.py",
    "src/mixed_media_utility/color_metrics.py",
    "src/mixed_media_utility/color_pipeline.py",
    "src/mixed_media_utility/io/calibration_profile.py",
    "src/mixed_media_utility/io/naming.py",
    # Module **neuf**, ajoute par l'AC 12 (`EPIC5-ARB-83`): la designation de profil par
    # l'operateur. Il est declare ici plutot que glisse, ce qui est exactement l'office
    # de cette frontiere -- un elargissement se declare. Il porte ce que `cli.py` faisait
    # par appariement de `chain_id` avant qu'`EPIC5-ARB-83` ne supprime l'appariement.
    "src/mixed_media_utility/io/profile_designation.py",
    "src/mixed_media_utility/io/payload.py",
    "src/mixed_media_utility/io/reconstruction.py",
    "src/mixed_media_utility/io/scan_manifest.py",
    "src/mixed_media_utility/page_payload.py",
    "src/mixed_media_utility/scan_detection.py",
    "src/mixed_media_utility/scan_output_frames.py",
    "src/mixed_media_utility/page_templates.py",
    "src/mixed_media_utility/patch_presets.py",
    "src/mixed_media_utility/patch_values.py",
    "src/mixed_media_utility/pdf_composition.py",
    "src/mixed_media_utility/qr_codes.py",
    "src/mixed_media_utility/scan_chain.py",
})


def _diff_de_production_5_23() -> list[str]:
    """Fichiers de production touches par la story, ou **echec nomme**, jamais un skip.

    Le diff est borne **des deux cotes** (`_BASELINE_5_23`..`_FIN_5_23`) depuis le
    2026-08-19: borne en bas seulement, il mesurait « tout ce que le depot a touche depuis
    le baseline de 5.23 » et non « ce que 5.23 a touche », donc la premiere story suivante
    qui modifie un module de production le ferait echouer sans qu'aucune frontiere de 5.23
    ne soit franchie. Motif complet sous `_FIN_5_23`.
    """
    import shutil

    if shutil.which("git") is None:
        pytest.fail(
            "git absent: la frontiere de perimetre ne s'evalue pas, et un skip se "
            "lirait comme un vert dans le total")
    try:
        return subprocess.run(
            ["git", "diff", "--name-only", _BASELINE_5_23, _FIN_5_23, "--", "src"],
            cwd=SRC.parent, capture_output=True, text=True, check=True, timeout=60,
        ).stdout.split()
    except (subprocess.SubprocessError, OSError) as error:
        echoue_ou_saute(
            SRC.parent, _BASELINE_5_23,
            f"commit de reference {_BASELINE_5_23} ou borne haute {_FIN_5_23} "
            f"inatteignable ({error}): la "
            "frontiere de perimetre ne s'evalue pas, et un skip se lirait comme un vert. "
            "Arbre exporte, historique tronque ou clone superficiel "
            "(`git fetch --unshallow`)")


def test_la_story_ne_touche_aucun_module_de_production_hors_de_son_perimetre():
    """AC 8, frontiere de perimetre. Un elargissement doit se declarer, pas se glisser.

    L'enumeration est **exacte** et non une inclusion: un fichier qu'on cesserait de
    toucher doit en sortir, faute de quoi elle deviendrait une liste de souhaits. Elle est
    confrontee au diff **isole** de la story (`_BASELINE_5_23`..`_FIN_5_23`), et elle est
    le pendant executable de la liste que les Dev Notes de la story declarent -- les deux
    ont ete remises d'accord le 2026-08-19: les Dev Notes en annoncaient **7** quand la
    story en touche **19**, tous deja enumeres ici avec leur raison.
    """
    touches = _diff_de_production_5_23()
    assert touches, (
        "aucun fichier de production modifie depuis le baseline: la frontiere ne "
        "mesurerait rien")
    assert set(touches) == set(_FICHIERS_DE_PRODUCTION_5_23), {
        "en trop": sorted(set(touches) - _FICHIERS_DE_PRODUCTION_5_23),
        "annonces et non touches": sorted(_FICHIERS_DE_PRODUCTION_5_23 - set(touches)),
    }


def test_la_frontiere_de_perimetre_mord_dans_les_deux_sens():
    """Une egalite devenue inclusion, ou un membre gauche vide, passerait le test seul.

    Les deux directions sont exercees, parce qu'une egalite remplacee par une inclusion ne
    se voit que d'un cote a la fois.
    """
    declares = set(_FICHIERS_DE_PRODUCTION_5_23)
    assert declares | {"src/mixed_media_utility/encode.py"} != declares
    assert declares - {"src/mixed_media_utility/color_metrics.py"} != declares
    touches = _diff_de_production_5_23()
    assert touches and all(chemin.startswith("src/") for chemin in touches), touches


def test_le_registre_color_divergence_1_reste_lisible_et_ne_decide_plus_rien():
    """AC 6, frontiere de non-confusion: conserve, lisible, sans pouvoir.

    Les deux registres coexistent et portent des grandeurs **differentes**. Ce test
    verifie les trois faits qui les separent, parce que les confondre serait relire le 5,0
    comme « le 1,0 releve » -- ce que la reserve de `color-divergence-2` interdit mot pour
    mot.
    """
    ancien = color_metrics.get_divergence_guard("color-divergence-1")
    neuf = color_metrics.get_raw_divergence_guard("color-divergence-2")
    assert ancien.max_excess_residual_de76 == 1.0
    assert neuf.max_mean_raw_de76 == 5.0
    # Deux registres distincts, et l'un ne resout pas l'entree de l'autre: sans ce volet,
    # un registre fusionne passerait les deux lignes ci-dessus.
    with pytest.raises(color_metrics.UnknownDivergenceGuardError):
        color_metrics.get_divergence_guard("color-divergence-2")
    with pytest.raises(color_metrics.UnknownRawDivergenceGuardError):
        color_metrics.get_raw_divergence_guard("color-divergence-1")
    # Et la reserve qui dit la non-confusion existe **dans le code**, pas seulement dans
    # la story: une reserve rangee dans un document se perd a la premiere reprise.
    reserves = " ".join(neuf.reservations).lower()
    assert "grandeur differente" in reserves
    assert "color-divergence-1" in reserves
