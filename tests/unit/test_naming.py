from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility.io.naming import (
    BOUNDS_SUFFIX_LENGTH,
    CANONICAL_ID_MAX_LENGTH,
    SCAN_CHAIN_SLUG_MAX_LENGTH,
    NamingError,
    build_calibration_pdf_filename,
    build_extracted_frame_filename,
    build_frame_filename,
    build_lot_id,
    derive_short_id,
    format_fps_short,
    read_extracted_frame_timecode,
    sanitize_timecode,
    scan_chain_suffix,
    valider_nom_court_de_cadence,
)


def test_derive_short_id_returns_value_unchanged_when_within_limit() -> None:
    assert derive_short_id("rush-001") == "rush-001"


def test_derive_short_id_derives_short_form_for_long_value() -> None:
    long_id = "p" * (CANONICAL_ID_MAX_LENGTH + 20)

    short_id = derive_short_id(long_id)

    assert len(short_id) <= CANONICAL_ID_MAX_LENGTH


def test_derive_short_id_is_deterministic_across_calls() -> None:
    long_id = "project-" + "x" * 60

    first = derive_short_id(long_id)
    second = derive_short_id(long_id)

    assert first == second


def test_derive_short_id_differs_for_different_long_inputs() -> None:
    long_a = "project-" + "a" * 60
    long_b = "project-" + "b" * 60

    assert derive_short_id(long_a) != derive_short_id(long_b)


def test_derive_short_id_rejects_empty_value() -> None:
    with pytest.raises(NamingError, match="empty"):
        derive_short_id("")


def test_format_fps_short_drops_trailing_zero_decimal() -> None:
    assert format_fps_short(24.0) == "24"


def test_format_fps_short_keeps_fractional_part_readable() -> None:
    assert format_fps_short(23.976) == "23p976"


def test_sanitize_timecode_replaces_colons_and_semicolons() -> None:
    assert sanitize_timecode("01:00:03:12") == "01-00-03-12"
    assert sanitize_timecode("01;00;03;12") == "01-00-03-12"


def test_sanitize_timecode_rejects_path_separators() -> None:
    with pytest.raises(NamingError, match="timecode"):
        sanitize_timecode("01/00/03/12")

    with pytest.raises(NamingError, match="timecode"):
        sanitize_timecode("01\\00\\03\\12")


def test_build_frame_filename_uses_zero_padded_page_index() -> None:
    name = build_frame_filename(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=3,
        frame_timecode="00:00:01:12",
        fps_target=24.0,
    )

    assert name == "example-001_lot-001_p004_tc00-00-01-12.png"


def test_build_frame_filename_supports_custom_suffix_and_slot_index() -> None:
    name = build_frame_filename(
        project_id="example-001",
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        frame_timecode="00:00:00:00",
        fps_target=23.976,
        slot_index=1,
        suffix=".tif",
    )

    assert name == "example-001_lot-001_p001_s01_tc00-00-00-00.tif"


def test_build_frame_filename_derives_short_id_for_long_project_id() -> None:
    long_project_id = "p" * (CANONICAL_ID_MAX_LENGTH + 20)

    name = build_frame_filename(
        project_id=long_project_id,
        rush_id="rush-001",
        lot_id="lot-001",
        page_index=0,
        frame_timecode="00:00:00:00",
        fps_target=24.0,
    )

    short_project_id = derive_short_id(long_project_id)
    assert name.startswith(f"{short_project_id}_lot-001_")
    assert len(short_project_id) <= CANONICAL_ID_MAX_LENGTH


# --------------------------------------------------------------------------
# Lecture d'un nom de frame extraite (revue du 2026-08-05, AC 15 de la 3.4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rush_id,fps_target,timecode",
    [
        ("rush-001", 24, "00:00:00:00"),
        ("rush-001", 12.5, "00:00:03:07"),
        ("rush-001", 3, "12:34:56:23"),
        ("a" * 80, 30, "00:01:02:03"),
        ("rush_avec_underscores", 5, "00:00:10:00"),
    ],
)
def test_read_extracted_frame_timecode_est_l_inverse_du_constructeur(
    rush_id, fps_target, timecode
) -> None:
    name = build_extracted_frame_filename(rush_id, fps_target, timecode)

    assert read_extracted_frame_timecode(name) == timecode


@pytest.mark.parametrize(
    "name",
    [
        "rush-001_24_00-00-00-00.png",       # mauvais suffixe
        "rush-001_24_00-00-00-00",           # sans suffixe
        "rush-001-24-00-00-00-00.tiff",      # aucun separateur d'underscore
        "rush-001_24_00-00-00.tiff",         # timecode incomplet
        "rush-001_24_0-0-0-0.tiff",          # timecode non assaini
        "rush-001_24_00:00:00:00.tiff",      # separateurs interdits
        "capture-hors-lot.tiff",             # fichier etranger
        ".tiff",                             # nom vide
    ],
)
def test_read_extracted_frame_timecode_refuse_ce_qui_ne_suit_pas_la_convention(name) -> None:
    with pytest.raises(NamingError):
        read_extracted_frame_timecode(name)


# ---------------------------------------------------------------------------
# Story 5.23: le nom du PDF de page de calibration porte le projet ET la chaine
# ---------------------------------------------------------------------------


#: **Deux chaines distinguables**, regle des fabriques: une fabrique mono-chaine
#: rendrait invisible une recette qui ignorerait le libelle.
CHAINE_A = "hp envy 4520 tiff 600 dpi auto corr off"
CHAINE_B = "epson v600 tiff 48 bits 1200 dpi corr auto off"


def test_le_nom_de_page_de_calibration_porte_le_projet_et_la_chaine() -> None:
    """Un projet porte autant de pages de calibration que de chaines de scan.

    Le nom `<projet>_calibration.pdf` n'en autorisait qu'**une** (correction d'Egan du
    2026-08-18): calibrer une seconde chaine dans le meme projet aurait exige d'ecraser
    la premiere.
    """
    nom = build_calibration_pdf_filename("mon-projet", CHAINE_A)
    assert nom.startswith("mon-projet_")
    assert nom.endswith("_calibration.pdf")
    # Un fragment **lisible** du libelle, en plus du condensat: un condensat seul ne se
    # distingue de son voisin qu'en ouvrant les deux fichiers.
    assert "hp-envy-4520" in nom
    assert scan_chain_suffix(CHAINE_A) in nom
    # Ni rush ni lot: la feuille n'appartient a aucun des deux.
    assert "_planches" not in nom


def test_deux_libelles_differents_donnent_deux_fichiers_differents() -> None:
    """**La classe de defaut la plus payee du depot**: la collision d'identite.

    Trois couples, et le troisieme est celui qui tue une recette a slug seul:
    `normalize_identifier` est **non injective**, donc « hp envy » et « hp-envy »
    rendent le meme slug. C'est le condensat, calcule sur le libelle **brut**, qui les
    separe.
    """
    couples = [
        (CHAINE_A, CHAINE_B),
        (CHAINE_A, CHAINE_A + " v2"),
        ("hp envy 4520", "hp-envy 4520"),
    ]
    for gauche, droite in couples:
        assert gauche != droite
        assert (build_calibration_pdf_filename("p", gauche)
                != build_calibration_pdf_filename("p", droite)), (gauche, droite)
    # Et le meme libelle rend **toujours** le meme nom: le condensat est deterministe,
    # sans horodate ni `hash()` randomise -- deux generations de la meme page designent
    # la meme feuille.
    assert (build_calibration_pdf_filename("p", CHAINE_A)
            == build_calibration_pdf_filename("p", CHAINE_A))
    assert len(scan_chain_suffix(CHAINE_A)) == BOUNDS_SUFFIX_LENGTH
    assert set(scan_chain_suffix(CHAINE_A)) <= set("0123456789abcdef")


def test_le_nom_reste_borne_et_lisible_sur_un_libelle_verbeux() -> None:
    """Le fragment lisible est tronque, l'identite ne l'est pas.

    Tronquer le slug est sans danger **parce que** le condensat porte l'identite: c'est
    la seule raison pour laquelle les deux morceaux ne jouent pas le meme role.
    """
    verbeux = "epson perfection v600 photo tiff 48 bits 1200 dpi corrections auto off"
    nom = build_calibration_pdf_filename("p", verbeux)
    slug = nom[len("p_"):-len(f"-{scan_chain_suffix(verbeux)}_calibration.pdf")]
    assert len(slug) <= SCAN_CHAIN_SLUG_MAX_LENGTH, slug
    assert not slug.endswith("-"), slug
    # Deux libelles verbeux qui partagent leurs 40 premiers caracteres restent deux
    # fichiers: la troncature du slug ne peut pas fabriquer une collision.
    autre = verbeux.replace("auto off", "auto on")
    assert build_calibration_pdf_filename("p", verbeux) != build_calibration_pdf_filename(
        "p", autre)


def test_un_libelle_vide_est_refuse() -> None:
    """Une page de calibration anonyme ne se distinguerait pas d'une autre."""
    with pytest.raises(NamingError):
        build_calibration_pdf_filename("p", "")
    with pytest.raises(NamingError):
        scan_chain_suffix("")
    with pytest.raises(NamingError):
        build_calibration_pdf_filename("", CHAINE_A)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-62` -- le nom court de cadence, story 11.4 lot P
# ---------------------------------------------------------------------------

#: Les cadences que la CLI sait deja nommer, et le nom qu'elle leur donne
#: AUJOURD'HUI. La table est ecrite en dur volontairement : c'est le seul moyen
#: de mesurer qu'un appelant qui ne passe pas de nom court obtient exactement le
#: nom d'avant, sans dependre de `format_fps_short` -- qu'un mutant pourrait
#: casser des deux cotes de l'egalite a la fois.
NOMS_DE_LOT_D_AVANT = {
    24: "rush-001_24",
    24.0: "rush-001_24",
    25: "rush-001_25",
    12.5: "rush-001_12p5",
    6.25: "rush-001_6p25",
    23.976: "rush-001_23p976",
    8.333333333333334: "rush-001_8p333333333333334",
}


@pytest.mark.parametrize("fps_target,attendu", sorted(NOMS_DE_LOT_D_AVANT.items()))
def test_sans_nom_court_le_lot_id_est_EXACTEMENT_celui_d_avant(fps_target, attendu) -> None:
    """AUCUN comportement observable de la CLI ne change (story 11.4, lot P).

    Le mutant vise : le nom court applique meme quand il n'est pas fourni, ou
    la garde de longueur durcie sur le chemin ordinaire. Les sept cadences
    couvrent les trois familles, dont l'artefact a dix-sept chiffres qui a
    motive `EPIC11-ARB-62` -- il est ici pour rester tel quel sur ce chemin.
    """
    assert build_lot_id("rush-001", fps_target) == attendu


def test_le_nom_court_FOURNI_remplace_le_fragment_de_cadence() -> None:
    """`EPIC11-ARB-62`, verbatim : « Un lot a cadence fractionnaire s'appelle
    **`rush-001_25s3`** -- le `s` tient la place de la barre. Le nom dit ce que
    l'operateur a demande (« une image sur trois »), ce qu'un nom decimal
    perdrait. »

    Le mutant vise, et il est le plus vicieux du lot : le nom court **ignore**
    quand il est fourni. Sans cette mesure, `build_lot_id` rendrait toujours
    l'ancien nom et tout le lot P serait mort sans qu'un test rougisse.
    """
    assert build_lot_id("rush-001", 8.333333333333334,
                        fps_short_name="25s3") == "rush-001_25s3"
    # Un rush NTSC : les quatre remarquables, dont la ligne « (toutes) ».
    assert build_lot_id("rush_01", 23.976023976023978,
                        fps_short_name="24000s1001") == "rush_01_24000s1001"
    assert build_lot_id("rush_01", 7.992007992007992,
                        fps_short_name="8000s1001") == "rush_01_8000s1001"


def test_le_nom_court_voyage_JUSQU_AU_BOUT_avec_un_condensat_de_bornes() -> None:
    """Une extraction bornee garde son condensat, et le nom court le precede.

    Le mutant vise : le nom court pose APRES le condensat, ou perdu quand un
    condensat existe.
    """
    lot_id = build_lot_id("rush-001", 8.333333333333334, fps_short_name="25s3",
                          source_in_timecode="15:34:30:00")
    assert lot_id.startswith("rush-001_25s3-")
    assert len(lot_id.rsplit("-", 1)[1]) == BOUNDS_SUFFIX_LENGTH
    # Et deux extraits distincts restent distincts.
    autre = build_lot_id("rush-001", 8.333333333333334, fps_short_name="25s3",
                         source_in_timecode="15:34:40:00")
    assert autre != lot_id


@pytest.mark.parametrize("nom_court", [
    "25/3", "25.3", "25 3", "25s3!",
    # **Les deux fins de ligne, et elles ne sont pas decoratives** (revue de la
    # vague 3, couche 1, finding `T2`). Le motif est ancre `^...$`, et en
    # Python `$` accepte **un saut de ligne FINAL** : `.match()` acceptait donc
    # `'25s3\n'`, ce qui produisait un `lot_id` -- et surtout un COMPOSANT DE
    # CHEMIN, via `rush_dir_slug` -- porteur d'un `\n`. Le mutant vise est
    # exactement `fullmatch` -> `match`, et `'25s3\r'` est son volet : lui
    # etait deja refuse, donc seul le `\n` demasque la faute.
    "25s3\n", "25s3\r", "25\ns3",
])
def test_un_nom_court_NON_CANONIQUE_est_refuse_NOMMEMENT(nom_court) -> None:
    """Le pattern `^[A-Za-z0-9_-]+$` du schema v2 tient toujours.

    Le refus arrive **a l'entree** et non apres l'extraction : c'est le motif
    pour lequel `_MANIFEST_ID_PATTERN` vit deja dans ce module. Et il **cite la
    valeur fautive** : un refus qui ne dit pas ce qu'il a lu oblige a relire le
    code pour comprendre.
    """
    for appel in (lambda: valider_nom_court_de_cadence(nom_court),
                  lambda: build_lot_id("rush-001", 8.33,
                                       fps_short_name=nom_court)):
        with pytest.raises(NamingError) as refus:
            appel()
        assert repr(nom_court) in str(refus.value)
        assert "A-Za-z0-9_-" in str(refus.value)


def test_un_nom_court_VIDE_est_refuse_avec_SON_PROPRE_motif() -> None:
    """Le vide n'est pas « un caractere interdit », c'est « aucun caractere ».

    Le mutant vise, et il a SURVECU a la premiere campagne : la garde du vide
    retiree. Le refus arrivait quand meme -- `^[A-Za-z0-9_-]+$` exige au moins
    un caractere --, mais avec le message de l'autre garde, qui parle de
    caracteres autorises a quelqu'un qui n'en a fourni aucun. Un test qui
    n'assertait que le TYPE de l'exception ne voyait pas la difference.
    """
    for appel in (lambda: valider_nom_court_de_cadence(""),
                  lambda: build_lot_id("rush-001", 8.33, fps_short_name="")):
        with pytest.raises(NamingError) as refus:
            appel()
        assert "vide" in str(refus.value)
        assert "A-Za-z0-9_-" not in str(refus.value)


def test_un_nom_court_CANONIQUE_traverse_la_validation_inchange() -> None:
    """Le volet symetrique : la garde ne refuse pas tout."""
    for nom_court in ("25s3", "12p5", "24", "24000s1001", "6p25"):
        assert valider_nom_court_de_cadence(nom_court) == nom_court


def test_un_nom_court_TROP_LONG_est_REFUSE_et_jamais_TRONQUE() -> None:
    """`CANONICAL_ID_MAX_LENGTH` tient, et le depassement est refuse **nommement**.

    Le mutant vise : la troncature silencieuse par `derive_short_id`, qui
    remplacerait la queue du nom par un condensat -- donc effacerait `25s3` au
    moment precis ou il etait cense dire « une image sur trois ».
    """
    # **Le nom de rush est DERIVE de la borne, jamais ecrit a une longueur
    # choisie.** La premiere redaction posait un nom de camera reel de 44
    # caracteres, calibre pour depasser 48 -- et il est devenu trop COURT le
    # jour ou `main` a porte la borne a 64 (`EPIC5-ARB-106`, `ff57780`),
    # decouvert a la liaison du 2026-08-30. Un banc qui mesure une borne ne
    # doit pas coder sa valeur du moment : c'est la borne qui bouge, pas la
    # propriete. La forme reste celle d'un vrai nom de camera, allongee juste
    # ce qu'il faut pour depasser.
    rush_long = ("A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04_"
                 * 4)[:CANONICAL_ID_MAX_LENGTH]
    complet = f"{rush_long}_25s3"
    assert len(complet) > CANONICAL_ID_MAX_LENGTH

    with pytest.raises(NamingError) as refus:
        build_lot_id(rush_long, 8.333333333333334, fps_short_name="25s3")
    assert "25s3" in str(refus.value)
    assert str(CANONICAL_ID_MAX_LENGTH) in str(refus.value)

    # Volet symetrique : juste sous le plafond, le nom passe ENTIER, et sa
    # queue est bien le nom court plutot qu'un condensat.
    rush_juste = "r" * (CANONICAL_ID_MAX_LENGTH - len("_25s3"))
    lot_id = build_lot_id(rush_juste, 8.333333333333334, fps_short_name="25s3")
    assert lot_id == f"{rush_juste}_25s3"
    assert len(lot_id) == CANONICAL_ID_MAX_LENGTH


def test_le_chemin_ORDINAIRE_garde_son_raccourcissement_silencieux() -> None:
    """La garde de longueur ne vise **que** le chemin du nom court.

    Le seuil du chemin ordinaire preexiste a cette story ; le durcir changerait
    le nom d'extractions deja livrees. Le mesurer ici est ce qui empeche un
    correctif futur de le faire par megarde.
    """
    # Meme motif que le banc precedent : la longueur se DERIVE de la borne.
    rush_long = ("A005_C012_20260806_TOURNAGE_PLATEAU_PRISE_04_"
                 * 4)[:CANONICAL_ID_MAX_LENGTH]
    lot_id = build_lot_id(rush_long, 12.5)
    assert len(lot_id) == CANONICAL_ID_MAX_LENGTH
    assert not lot_id.endswith("_12p5")
