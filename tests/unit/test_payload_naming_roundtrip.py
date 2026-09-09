"""Integration tests for story 2.3: payload <-> parse <-> naming roundtrip.

These exercise the full reconstruction chain end to end: build a page
payload, check its QR budget, serialize/parse it as if read back from a
scanned QR code, and derive the frame filenames for every slot straight from
the parsed payload (AC 1, 3, 4).
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io.naming import (
    CANONICAL_ID_MAX_LENGTH,
    build_frame_filename,
    build_sheets_pdf_filename,
    derive_short_id,
)
from mixed_media_utility.io.payload import (
    PayloadBudgetExceeded,
    build_page_payload,
    check_payload_budget,
    parse_payload,
    serialize_payload,
)


def test_payload_roundtrip_drives_deterministic_frame_filenames() -> None:
    slots = [
        {"slot_index": 0, "frame_timecode": "00:00:00:00"},
        {"slot_index": 1, "frame_timecode": "00:00:01:12"},
    ]
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=slots,
    )

    budget_report = check_payload_budget(payload)
    assert budget_report.within_nominal is True

    qr_text = serialize_payload(payload)
    reconstructed = parse_payload(qr_text)
    assert reconstructed == payload

    filenames = [
        build_frame_filename(
            project_id=reconstructed["project_id"],
            rush_id=reconstructed["rush_id"],
            lot_id=reconstructed["lot_id"],
            page_index=reconstructed["page_index"],
            frame_timecode=slot["frame_timecode"],
            fps_target=reconstructed["fps_target"],
            slot_index=slot["slot_index"],
        )
        for slot in reconstructed["slots"]
    ]

    # `EPIC7-ARB-91` : ni le rush ni la cadence n'entrent dans le nom -- le
    # `lot_id` porte les deux par construction (`build_lot_id` vaut
    # `<rush_id>_<cadence-courte>`), et le nom les repetait donc chacun deux
    # fois. Le contrat de reconstruction de la story 2.3 tient : projet, rush,
    # lot, page et emplacement restent tous lisibles du seul nom.
    assert filenames == [
        "example-001_lot-001_p001_s00_tc00-00-00-00.png",
        "example-001_lot-001_p001_s01_tc00-00-01-12.png",
    ]
    # Ce que le roundtrip garantit desormais : le LOT est lisible du nom, et
    # c'est par lui que le rush et la cadence se retrouvent sur un lot reel
    # (`build_lot_id` vaut `<rush_id>_<cadence>`). La fixture de ce test emploie
    # des identifiants synthetiques (`rush-001` / `lot-001`) qui ne suivent pas
    # cette construction : le lien lot -> rush est donc mesure la ou il vaut,
    # sur des lots produits par `build_lot_id`
    # (`tests/unit/test_retours_terrain_2026_08_27.py`).
    #
    # Une assertion « `_<lot_id>_` est dans le nom » vivait ici et a ete
    # RETIREE (revue du 2026-08-27) : l'egalite exacte ci-dessus l'implique,
    # donc elle ne pouvait pas rougir. Une assertion inerte ressemble a de la
    # couverture sans en etre.
    # Every slot on the page yields a distinct, stable filename.
    assert len(set(filenames)) == len(filenames)


def test_payload_roundtrip_with_long_ids_derives_short_stable_filenames() -> None:
    long_project_id = "atelier-tournage-exterieur-episode-quatre-vingt-douze"
    long_rush_id = "cam-b-plan-large-matinee-brumeuse-take-zero-neuf"
    slots = [{"slot_index": 0, "frame_timecode": "00:00:00:00"}]

    payload = build_page_payload(
        project_id=long_project_id,
        rush_id=long_rush_id,
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        fps_target=23.976,
        timecode_base_fps="25/1",
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=slots,
    )

    qr_text = serialize_payload(payload)
    reconstructed = parse_payload(qr_text)

    filename = build_frame_filename(
        project_id=reconstructed["project_id"],
        rush_id=reconstructed["rush_id"],
        lot_id=reconstructed["lot_id"],
        page_index=reconstructed["page_index"],
        frame_timecode=reconstructed["slots"][0]["frame_timecode"],
        fps_target=reconstructed["fps_target"],
        slot_index=reconstructed["slots"][0]["slot_index"],
    )

    expected_project = derive_short_id(long_project_id)
    expected_rush = derive_short_id(long_rush_id)
    assert len(expected_project) <= CANONICAL_ID_MAX_LENGTH
    assert len(expected_rush) <= CANONICAL_ID_MAX_LENGTH
    # `EPIC7-ARB-91` : le rush ne figure plus **en propre** dans le nom. Le
    # raccourcissement du projet, lui, est inchange -- c'est ce que ce cas
    # existe pour mesurer, et le retrait du rush ne doit pas l'emporter avec
    # lui.
    assert filename == f"{expected_project}_lot-001_p001_s00_tc00-00-00-00.png"
    assert expected_rush not in filename

    # Deterministic: rebuilding the same filename twice yields the same result.
    filename_again = build_frame_filename(
        project_id=reconstructed["project_id"],
        rush_id=reconstructed["rush_id"],
        lot_id=reconstructed["lot_id"],
        page_index=reconstructed["page_index"],
        frame_timecode=reconstructed["slots"][0]["frame_timecode"],
        fps_target=reconstructed["fps_target"],
        slot_index=reconstructed["slots"][0]["slot_index"],
    )
    assert filename == filename_again


def test_payload_budget_ceiling_is_enforced_before_naming_stage() -> None:
    slots = [
        {"slot_index": index, "frame_timecode": "00:00:00:00"} for index in range(200)
    ]
    payload = build_page_payload(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        page_count=1,
        fps_target=24.0,
        timecode_base_fps="25/1",
        template_id="template-a4-16x9",
        patch_preset_id="patch-preset-mvp",
        target_colorspace="rec709",
        gamut_map_id="gamut-map-none-1",
        slots=slots,
    )

    with pytest.raises(PayloadBudgetExceeded):
        check_payload_budget(payload)


# --------------------------------------------------------------------------
# `EPIC11-ARB-178` -- reconstruire le NOM DU TIRAGE depuis une planche scannee
# --------------------------------------------------------------------------
#
# Demande d'Egan, verbatim (2026-09-02) : « la fonction qui decode a toutes les
# cles pour savoir le nom de la planche dont est issu un scan ? En utilisant les
# memes infos et le meme systeme de nommage ? »
#
# Reponse mesuree ici : oui aux deux, et le second « oui » est le difficile --
# « le meme systeme de nommage » veut dire UNE fonction, pas deux redactions.

import inspect  # noqa: E402

from mixed_media_utility.io import naming, payload as payload_io  # noqa: E402
from mixed_media_utility.io.payload import (  # noqa: E402
    PayloadValidationError,
    sheets_pdf_filename_from_payload,
)

#: Un gabarit REEL du registre : `sheets_layout_fragment` derive le fragment de
#: mise en page du `template_id` et refuse un identifiant que `page_templates`
#: ne resout pas. Un gabarit invente mesurerait la garde, pas le nom.
GABARIT = "tpl-a4-paysage-4f-v1"


def payload_de_planche(
    *,
    project_id: str = "projet_demo",
    rush_id: str = "planche_4f_heteroclite",
    lot_id: str = "planche_4f_heteroclite_4",
    template_id: str = GABARIT,
    version_rank: int | None = None,
) -> dict:
    """Une charge utile de planche d'images, par le **vrai** constructeur."""
    return payload_io.build_page_payload(
        project_id=project_id,
        rush_id=rush_id,
        lot_id=lot_id,
        page_index=0,
        page_count=1,
        fps_target=4.0,
        timecode_base_fps="25/1",
        template_id=template_id,
        patch_preset_id="patches-18-v2",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
        version_rank=version_rank,
    )


def test_le_nom_du_tirage_se_reconstruit_apres_un_ALLER_RETOUR_par_le_QR() -> None:
    """La chaine entiere : construire, imprimer, relire, **nommer**.

    Le nom n'est pas compare a un litteral seul mais a ce que `makepdf`
    aurait ecrit -- `build_sheets_pdf_filename` appele avec les memes valeurs.
    Le litteral est la en second, pour que le test dise aussi a quoi le nom
    ressemble.
    """
    original = payload_de_planche(version_rank=3)
    relu = parse_payload(serialize_payload(original))
    assert relu == original

    reconstruit = sheets_pdf_filename_from_payload(relu)

    assert reconstruit == build_sheets_pdf_filename(
        relu["project_id"], relu["rush_id"], relu["lot_id"],
        version_rank=3, template_id=relu["template_id"])
    assert reconstruit == "projet_demo_planche_4f_heteroclite_4_4f-pay_v3.pdf"


def test_le_rang_D_ORIGINE_ne_porte_aucun_fragment_de_version() -> None:
    """Deux omissions du meme fait, dont les representations different.

    Le payload OMET le rang 1 (`EPIC11-ARB-91`) et `payload_version_rank` le
    relit `1` ; le NOM omet le rang 1 aussi, mais son constructeur exige `None`
    -- `format_version_suffix` refuse nommement un rang 1. La bascule entre les
    deux conventions se fait a ce site et nulle part ailleurs.
    """
    origine = payload_de_planche(version_rank=None)
    assert payload_io.VERSION_RANK_FIELD not in origine

    assert sheets_pdf_filename_from_payload(origine) == (
        "projet_demo_planche_4f_heteroclite_4_4f-pay.pdf")
    # Le temoin qui donne son sens au precedent : passer `1` tel quel au
    # constructeur serait un refus, pas un nom sans suffixe.
    with pytest.raises(naming.NamingError):
        naming.format_version_suffix(1)


def test_la_reconstruction_APPELLE_le_constructeur_et_ne_recompose_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """« Le meme systeme de nommage » : UNE fonction, pas deux redactions.

    C'est le point qu'Egan a nomme, et c'est celui qu'un test de valeur ne
    mesure pas : deux redactions qui rendent aujourd'hui la meme chaine passent
    toutes les assertions de valeur, et divergent au premier changement de
    convention. On mesure donc la **dependance**, pas la sortie : changer le
    constructeur change la reconstruction, parce qu'il n'y a qu'une sortie a
    changer.
    """
    vus: dict = {}

    def constructeur_temoin(*args, **kwargs):
        vus["args"] = args
        vus["kwargs"] = kwargs
        return "CONVENTION-CHANGEE.pdf"

    monkeypatch.setattr(naming, "build_sheets_pdf_filename", constructeur_temoin)

    assert sheets_pdf_filename_from_payload(
        payload_de_planche(version_rank=7)) == "CONVENTION-CHANGEE.pdf"
    # Et il est appele avec les valeurs DECODEES, pas avec des valeurs de
    # repli : un appel correct portant de mauvais arguments serait le meme
    # defaut sous une autre forme.
    assert vus["args"] == (
        "projet_demo", "planche_4f_heteroclite", "planche_4f_heteroclite_4")
    assert vus["kwargs"] == {"version_rank": 7, "template_id": GABARIT}


def test_aucun_fragment_de_nom_n_est_ECRIT_dans_la_reconstruction() -> None:
    """Frontiere NEGATIVE, la seule qui voie revenir une seconde redaction.

    Un test positif ne verrait pas un `f"{projet}_{lot}_...pdf"` reintroduit a
    cote de l'appel : la sortie resterait juste. Le corps de la fonction ne
    porte donc **aucune** chaine qui ressemble a un fragment de nom de fichier.
    """
    source = inspect.getsource(sheets_pdf_filename_from_payload)
    corps = ast.parse(textwrap.dedent(source)).body[0]
    litteraux = [
        noeud.value for noeud in ast.walk(corps)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
    ]
    # La docstring est le premier litteral et elle a le droit de citer les
    # conventions ; ce sont les AUTRES qu'on interdit.
    assert litteraux[0] is corps.body[0].value.value
    for texte in litteraux[1:]:
        assert ".pdf" not in texte, texte
        assert "_v" not in texte, texte
    # Et il n'y a qu'UN appel de constructeur de nom dans le corps.
    appels = [
        noeud.func.attr for noeud in ast.walk(corps)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
    ]
    assert appels.count("build_sheets_pdf_filename") == 1, appels
    # Le volet qui ferme vraiment la porte : la fonction n'a qu'UNE sortie, et
    # cette sortie EST l'appel. Compter les appels ne suffirait pas -- un `f"..."`
    # rendu a cote d'un appel inutilise passerait.
    retours = [n for n in ast.walk(corps) if isinstance(n, ast.Return)]
    assert len(retours) == 1, ast.dump(corps)
    rendu = retours[0].value
    assert isinstance(rendu, ast.Call) and isinstance(rendu.func, ast.Attribute)
    assert rendu.func.attr == "build_sheets_pdf_filename"


def test_la_table_des_champs_consommes_est_EXACTEMENT_celle_du_constructeur() -> None:
    """L'ensemble EXACT, jamais une appartenance.

    « Le payload porte-t-il ce qu'il faut ? » se mesure en confrontant deux
    ensembles : les parametres du constructeur de noms d'un cote, ce que la
    reconstruction lit dans la charge utile de l'autre. « Au moins ceux-la »
    laisserait passer un parametre neuf que personne n'alimenterait.
    """
    parametres = set(inspect.signature(build_sheets_pdf_filename).parameters)
    lus = set(payload_io._SHEETS_NAME_PAYLOAD_FIELDS) | {
        payload_io.VERSION_RANK_FIELD}

    assert parametres == lus, parametres ^ lus
    # Et chacun de ces champs est reellement porte par une planche d'images.
    planche = payload_de_planche(version_rank=2)
    for champ in payload_io._SHEETS_NAME_PAYLOAD_FIELDS:
        assert champ in planche, champ
    assert payload_io.VERSION_RANK_FIELD in planche


def test_trois_planches_distinguables_rendent_chacune_SON_nom() -> None:
    """Regle des fabriques : trois elements, la cible au MILIEU.

    Une fonction qui rendrait le nom de la premiere planche venue -- ou qui
    apparierait par position -- est exactement le defaut que ce depot a paye
    trois fois (mutants `M33`, `M25`). Les trois planches different par le lot
    ET par le rang, et c'est la deuxieme qui est verifiee en premier.
    """
    planches = [
        payload_de_planche(lot_id="heteroclite_2", version_rank=None),
        payload_de_planche(lot_id="heteroclite_4", version_rank=5),
        payload_de_planche(lot_id="heteroclite_8", version_rank=9),
    ]
    noms = [sheets_pdf_filename_from_payload(p) for p in planches]

    assert noms[1] == "projet_demo_heteroclite_4_4f-pay_v5.pdf"
    assert noms == [
        "projet_demo_heteroclite_2_4f-pay.pdf",
        "projet_demo_heteroclite_4_4f-pay_v5.pdf",
        "projet_demo_heteroclite_8_4f-pay_v9.pdf",
    ]
    assert len(set(noms)) == 3


def test_la_mise_en_page_entre_dans_le_nom_reconstruit() -> None:
    """`EPIC11-ARB-171` : deux mises en page du MEME lot ne se confondent plus.

    C'est ce qui rendait le motif du conflit opaque -- « ce tirage existe
    deja » sans dire que c'est une autre forme. Le fragment vient du gabarit
    DECODE, jamais d'un defaut.
    """
    paysage = sheets_pdf_filename_from_payload(
        payload_de_planche(template_id="tpl-a4-paysage-4f-v1"))
    portrait = sheets_pdf_filename_from_payload(
        payload_de_planche(template_id="tpl-a4-portrait-2f-v1"))

    assert paysage.endswith("_4f-pay.pdf") and portrait.endswith("_2f-por.pdf")
    assert paysage != portrait


def test_une_page_de_CALIBRATION_n_est_le_tirage_d_aucun_lot() -> None:
    """Refus nomme, jamais un `KeyError` ni un nom invente.

    Une page de calibration ne declare ni projet, ni rush, ni lot
    (`CALIBRATION_ABSENT_FIELDS`) : le nom qu'on lui reconstruirait serait
    fabrique de rien. Le refus vient AVANT la garde des champs manquants, sans
    quoi le message parlerait d'un `project_id` absent au lieu de dire ce qui
    se passe.
    """
    calibration = payload_io.build_page_payload(
        project_id="", rush_id="", lot_id="",
        page_index=0, page_count=1, fps_target=0.0, timecode_base_fps="",
        template_id="tpl-a4-portrait-calibration-v1",
        patch_preset_id="patches-17-v4", target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY, slots=[],
        page_role=payload_io.PAGE_ROLE_CALIBRATION,
        scan_chain_label="hp envy 4520 tiff 600 dpi",
    )

    with pytest.raises(PayloadValidationError) as refus:
        sheets_pdf_filename_from_payload(calibration)
    assert "calibration" in str(refus.value)
    assert "project_id" in str(refus.value)


@pytest.mark.parametrize("champ", ["project_id", "rush_id", "lot_id", "template_id"])
@pytest.mark.parametrize("abimer", ["absent", "vide"])
def test_une_charge_utile_TRONQUEE_est_refusee_en_nommant_le_champ(
    champ: str, abimer: str,
) -> None:
    """Un QR abime ne rend pas un nom approximatif, il rend un refus qui dit ou.

    Chacun des quatre champs se mesure separement : une garde qui ne verifie
    que le premier laisserait les trois autres produire un nom ampute, et un
    nom ampute est une mauvaise association ecrite (risque R12).

    **Les deux formes d'abimage se mesurent, et ce n'est pas du zele** : un
    mutant qui remplace `not payload.get(champ)` par `champ not in payload`
    survit a la seule forme « absent ». La chaine VIDE traverse alors jusqu'a
    `naming`, dont la garde la refuse -- mais en `NamingError`, pas en
    `PayloadValidationError`. L'appelant qui n'attrape que la seconde voit
    remonter une exception d'une autre famille depuis une fonction qui declare
    la sienne, et c'est exactement la difference que le mutant produit.
    """
    tronque = payload_de_planche(version_rank=2)
    if abimer == "absent":
        del tronque[champ]
    else:
        tronque[champ] = ""

    with pytest.raises(PayloadValidationError) as refus:
        sheets_pdf_filename_from_payload(tronque)
    assert champ in str(refus.value)


def test_un_document_qui_n_est_pas_une_charge_utile_est_refuse_nommement() -> None:
    """Toute la raison d'etre de cette famille est de survivre a une relecture
    ABIMEE : lever `AttributeError` sur une liste serait la panne qu'elle
    existe pour eviter, exactement comme `payload_version_rank` le dit."""
    for document in ([], "pas un payload", None, 12):
        with pytest.raises(PayloadValidationError):
            sheets_pdf_filename_from_payload(document)  # type: ignore[arg-type]
