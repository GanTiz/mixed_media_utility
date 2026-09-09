# -*- coding: utf-8 -*-
"""Story 5.29 (`EPIC11-ARB-89`) -- le mecanisme de coeur des sorties nommees.

Trois operations d'une meme fonction: versionner (AC 1 a AC 5), ecraser
sciemment (AC 6 a AC 8), supprimer (couvert par
``test_suppression_element_de_projet.py``). Ce fichier porte les six premieres
AC de la fiche ``5-29-mecanisme-de-coeur-sorties-nommees.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mixed_media_utility import extraction, ffmpeg_utils
from mixed_media_utility.frame_selection import select_source_frames
from jsonschema.exceptions import ValidationError

from mixed_media_utility.io import extraction_manifest, manifest as io_manifest, naming, project_layout
from mixed_media_utility.io.extraction_manifest import (
    ExtractionRecord,
    LotIdentityMismatchError,
    LotStateConflictError,
    build_extraction_manifest,
)

RUSH_ID = "rush-amont-529"
CADENCE_VISEE = 12.0

#: Binaires qui n'existent pas: force toute execution qui depasse l'etape 1 de
#: `run_extraction` (le jugement de transition d'etat, AVANT ffmpeg) a lever
#: `ffmpeg_utils.FfmpegNotFoundError` plutot que d'aller plus loin -- ce qui
#: prouve qu'un contournement a bien atteint l'etape 2 sans avoir a executer
#: ffmpeg pour de vrai.
FFMPEG_ABSENT = "mmu-ffmpeg-inexistant-529"
FFPROBE_ABSENT = "mmu-ffprobe-inexistant-529"


class _JournalMuet:
    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


def _video_factice(dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{RUSH_ID}.mp4"
    chemin.write_bytes(b"pas une vraie video")
    return chemin


def _projet_avec_lot_en_etat_aval(base: Path, etat: str) -> tuple[Path, Path]:
    """Un projet a la main dont le lot vise est deja passe a `etat`.

    Meme esprit que `test_extraction_etat_en_amont.projet_a_la_main`, mais
    autonome plutot que de dependre d'un module de test voisin.
    """
    projet = base / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    lot_id = naming.build_lot_id(RUSH_ID, CADENCE_VISEE)
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "lots": [{"lot_id": lot_id, "rush_id": RUSH_ID, "state": etat}],
    }
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    return projet, _video_factice(base / "rushes")


def _run_a_l_etape_1(projet: Path, rush: Path, **kwargs):
    return extraction.run_extraction(
        project_dir=projet,
        video_path=rush,
        fps_target=CADENCE_VISEE,
        consent_granted=kwargs.pop("consent_granted", True),
        unknown_color_accepted=True,
        logger=_JournalMuet(),
        ffmpeg_binary=FFMPEG_ABSENT,
        ffprobe_binary=FFPROBE_ABSENT,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# AC 5 -- nouvelle_version, et l'exclusion mutuelle avec ecrasement_conscient.
# ---------------------------------------------------------------------------


def test_sans_aucun_mot_cle_le_refus_nomme_les_deux_issues_de_la_story(tmp_path):
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "pdf")
    with pytest.raises(LotStateConflictError) as refus:
        _run_a_l_etape_1(projet, rush)
    message = str(refus.value)
    assert "nouvelle version" in message
    assert "ecrasement" in message.lower()
    # Les deux issues d'AVANT cette story restent mot pour mot (AC 2.1 de la
    # story 11.4c: "c'est V3 qui en ajoutera une troisieme").
    assert "extraire vers une autre cadence cible" in message
    assert "nettoyer ce lot a la main" in message


def test_nouvelle_version_contourne_le_refus_et_atteint_ffmpeg(tmp_path):
    """Le lot vise est neuf (lot_id distinct): aucun conflit d'etat possible.

    **La forme de l'assertion est le sujet** (revue Opus) : un
    `assert not isinstance(exc, LotStateConflictError)` est vert pour
    N'IMPORTE quelle autre exception -- y compris les `ExtractionInputError`
    d'exclusion mutuelle ajoutes par ce meme diff, ou une `NamingError` de
    rang hors bornes. Il ne mesurait pas que l'appel avait DEPASSE l'etape 1,
    seulement qu'il n'avait pas echoue de cette facon-la. Nommer l'exception
    attendue -- ffmpeg est absent du PATH, donc c'est elle qui doit venir --
    mesure vraiment la traversee.
    """
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "pdf")
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        _run_a_l_etape_1(projet, rush, nouvelle_version=True)


def test_nouvelle_version_et_ecrasement_conscient_ensemble_sont_refuses(tmp_path):
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "pdf")
    with pytest.raises(extraction.ExtractionInputError) as refus:
        _run_a_l_etape_1(
            projet, rush, nouvelle_version=True, ecrasement_conscient=True
        )
    message = str(refus.value)
    assert "nouvelle-version" in message or "nouvelle_version" in message
    assert "ecrasement" in message.lower()


# ---------------------------------------------------------------------------
# AC 6, AC 7 -- ecrasement conscient : deux issues, jamais l'une sans l'autre.
# ---------------------------------------------------------------------------


def test_ecrasement_conscient_seul_sans_consentement_refuse_encore(tmp_path):
    """`ecrasement_conscient=True` sans `consent_granted=True` ne suffit pas."""
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "scan")
    with pytest.raises(LotStateConflictError):
        _run_a_l_etape_1(
            projet, rush, ecrasement_conscient=True, consent_granted=False
        )


def test_ecrasement_conscient_avec_consentement_contourne_le_refus(tmp_path):
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "scan")
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        _run_a_l_etape_1(
            projet, rush, ecrasement_conscient=True, consent_granted=True
        )


@pytest.mark.parametrize("etat_aval", ["pdf", "scan", "reconstruction", "encode"])
def test_ecrasement_conscient_contourne_TOUS_les_etats_aval(tmp_path, etat_aval):
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, etat_aval)
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        _run_a_l_etape_1(
            projet, rush, ecrasement_conscient=True, consent_granted=True
        )


# ---------------------------------------------------------------------------
# AC 8 -- frontiere : aucun fichier de tui/ dans ce depot (absent de main).
# ---------------------------------------------------------------------------


def test_la_garde_de_la_TUI_est_TOUJOURS_LA_et_TOUJOURS_APPELEE():
    """`refus_d_etat_de_lot` ne se retire pas (`EPIC11-ARB-86`).

    **Ce test etait un jeton d'attente, et la liaison l'a echu.** Sur `main`,
    ou il a ete ecrit, il posait `find_spec("mixed_media_utility.tui") is None`
    -- « cette story ne peut par construction rien retirer a la TUI tant que le
    paquet n'existe pas ». Le paquet existe ici. Un jeton d'attente qui survit
    a son echeance ne mesure plus rien : il devient une assertion qui rougit au
    moment ou la chose qu'elle attendait arrive. Il est donc remplace par **la
    mesure dont il tenait la place**.

    Deux moities, et la seconde est celle qui compte :

    1. la garde **existe** ;
    2. elle est **appelee** par le chemin d'ecriture. `EPIC11-ARB-83` la
       declare *load-bearing* -- « la retirer au motif que "le coeur refuse de
       toute facon" detruirait des frames livrees ». Une garde presente mais
       plus appelee serait exactement ce retrait, sous une forme qu'aucun
       `find_spec` ne verrait. La mesure porte donc sur l'ARBRE du module, pas
       sur un `hasattr`.
    """
    import ast
    import importlib.util

    assert importlib.util.find_spec("mixed_media_utility.tui") is not None, (
        "le paquet `tui/` a disparu de cette branche : ce n'est pas ce test "
        "qu'il faut ajuster, c'est la disparition qu'il faut expliquer")

    from mixed_media_utility.tui import atelier_extraction_ecriture as atelier

    assert callable(atelier.refus_d_etat_de_lot)

    source = Path(atelier.__file__).read_text(encoding="utf-8")
    appels = [
        noeud for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "refus_d_etat_de_lot"
    ]
    assert appels, (
        "`refus_d_etat_de_lot` n'est plus appelee dans son propre module : "
        "la garde est devenue morte, ce qu'`EPIC11-ARB-83` interdit "
        "nommement -- « elle est ce qui tient l'AC 7.5, pas une ceinture "
        "par-dessus une bretelle du coeur »")


# ---------------------------------------------------------------------------
# AC 1 -- le fragment `_v<NN>`, calcule une fois, transporte aux deux
# producteurs.
# ---------------------------------------------------------------------------


def test_format_version_suffix_rend_le_fragment_sans_zero_de_tete():
    assert naming.format_version_suffix(2) == "_v2"
    assert naming.format_version_suffix(10) == "_v10"
    assert naming.format_version_suffix(99) == "_v99"


def test_format_version_suffix_refuse_hors_bornes():
    with pytest.raises(naming.NamingError):
        naming.format_version_suffix(1)
    with pytest.raises(naming.NamingError):
        naming.format_version_suffix(0)
    with pytest.raises(naming.NamingError):
        naming.format_version_suffix(100)


def test_build_lot_id_absent_de_version_rank_est_inchange():
    """Le defaut `None` reprend le chemin d'avant cette story, au caractere pres."""
    avant = naming.build_lot_id("rush-001", 24.0)
    apres = naming.build_lot_id("rush-001", 24.0, version_rank=None)
    assert avant == apres == "rush-001_24"


def test_build_lot_id_et_rush_dir_slug_produisent_le_meme_fragment_de_version():
    """ARB-3: le nom de dossier de lot et l'identifiant de lot ne divergent jamais.

    Mesure sur les DEUX chaines produites, jamais sur le fait qu'elles
    appellent la meme fonction: un cablage identique peut produire deux noms
    differents.
    """
    lot_id = naming.build_lot_id("rush-001", 24.0, version_rank=2)
    slug = project_layout.rush_dir_slug("rush-001", 24.0, version_rank=2)
    assert lot_id == "rush-001_24_v2"
    assert slug == "rush-001_24_v2"
    assert lot_id == slug


def test_le_fragment_de_version_suit_le_suffixe_de_bornes_dans_cet_ordre():
    """Ordre fixe: cadence, puis bornes, puis version."""
    lot_id = naming.build_lot_id(
        "rush-001",
        24.0,
        source_in_timecode="00:00:00:00",
        source_out_timecode="00:00:10:00",
        version_rank=3,
    )
    suffixe = naming.bounds_suffix("00:00:00:00", "00:00:10:00")
    assert lot_id == f"rush-001_24-{suffixe}_v3"


# ---------------------------------------------------------------------------
# AC 2 -- le rang de version se lit au MANIFESTE, jamais au nom.
# ---------------------------------------------------------------------------


def _manifeste_a_trois_versions_et_un_trou():
    """Fabrique: trois versions distinguables du meme lot de base (rangs 2, 4,
    5 -- un trou en 3), la cible du test placee au MILIEU de la liste
    parcourue, plus un lot d'un AUTRE rush au meme manifeste.

    Piege deja paye sur ce depot: le point se verifie sur la liste que le
    code PARCOURT (`manifest["lots"]`, dans cet ordre), jamais sur celle que
    la fabrique ECRIT dans son intention.
    """
    base_id = naming.build_lot_id("rush-001", 24.0)
    return {
        "schema_version": "2.1",
        "project_id": "projet-test",
        "lots": [
            {
                "lot_id": naming.build_lot_id("rush-001", 24.0, version_rank=2),
                "rush_id": "rush-001",
                "base_lot_id": base_id,
                "version_rank": 2,
            },
            # La cible: rang 4, ni premiere ni derniere position de la liste.
            {
                "lot_id": naming.build_lot_id("rush-001", 24.0, version_rank=4),
                "rush_id": "rush-001",
                "base_lot_id": base_id,
                "version_rank": 4,
            },
            {
                "lot_id": naming.build_lot_id("rush-001", 24.0, version_rank=5),
                "rush_id": "rush-001",
                "base_lot_id": base_id,
                "version_rank": 5,
            },
            # Un lot d'un AUTRE rush: la resolution ne doit pas s'y egarer.
            {
                "lot_id": naming.build_lot_id("rush-002", 24.0),
                "rush_id": "rush-002",
            },
        ],
    }


def test_un_rang_de_lot_CONSOMME_ne_se_reutilise_JAMAIS():
    """**Ce test mesurait l'inverse, et l'arbitrage l'a retourne**
    (`EPIC11-ARB-92`, Egan 2026-08-31, etendu aux TROIS objets versionnables).

    Il verifiait que le resolveur rendait le trou de la sequence. Un rang se
    CONSOMME desormais : la famille porte les rangs 2, 4 et 5, la ligne d'eau
    est donc a 5 et le prochain lot est le 6 -- le 3 reste un trou.

    Ce que la reutilisation des trous evitait -- epuiser les 98 rangs a force
    de produire et supprimer -- est desormais couvert par la LIBERATION EN
    QUEUE, qui rend d'un coup tous les rangs devenus derniers.
    """
    manifest = _manifeste_a_trois_versions_et_un_trou()
    rang = extraction_manifest.resolve_version_rank(manifest, "rush-001", 24.0)
    assert rang == 6


def test_la_ligne_d_eau_d_un_lot_est_de_niveau_PROJET():
    """Elle ne peut pas vivre dans l'entree d'origine : les versions d'un lot
    sont des entrees SOEURS, et l'origine peut etre supprimee alors que ses
    versions restent. Un manifeste sans aucun lot mais portant la ligne d'eau
    doit encore savoir ou il en est."""
    base = naming.build_lot_id("rush-001", 24.0)
    manifest = {
        "schema_version": "2.1",
        "lots": [],
        extraction_manifest.LOT_WATERMARKS_FIELD: {base: 4},
    }
    assert extraction_manifest.resolve_version_rank(
        manifest, "rush-001", 24.0) == 5
    # Et elle est par FAMILLE: un autre rush n'en herite pas.
    assert extraction_manifest.resolve_version_rank(
        manifest, "rush-002", 24.0) == 2


def test_resolve_version_rank_sans_version_existante_rend_2():
    manifest = {"schema_version": "2.1", "lots": []}
    rang = extraction_manifest.resolve_version_rank(manifest, "rush-001", 24.0)
    assert rang == 2


def test_resolve_version_rank_ignore_un_lot_d_un_autre_rush():
    """Un manifeste ne portant QUE le lot d'un autre rush ne fait pas croire
    a une version existante du rush vise."""
    manifest = {
        "schema_version": "2.1",
        "lots": [{"lot_id": naming.build_lot_id("rush-002", 24.0), "rush_id": "rush-002"}],
    }
    rang = extraction_manifest.resolve_version_rank(manifest, "rush-001", 24.0)
    assert rang == 2


def test_resolve_version_rank_apres_maximum_sans_trou_rend_maximum_plus_1():
    manifest = _manifeste_a_trois_versions_et_un_trou()
    # Combler le trou en 3 avant de re-resoudre: le prochain rang libre doit
    # alors devenir 6 (maximum + 1), pas re-rendre 3.
    manifest["lots"].append(
        {
            "lot_id": naming.build_lot_id("rush-001", 24.0, version_rank=3),
            "rush_id": "rush-001",
            "base_lot_id": naming.build_lot_id("rush-001", 24.0),
            "version_rank": 3,
        }
    )
    rang = extraction_manifest.resolve_version_rank(manifest, "rush-001", 24.0)
    assert rang == 6


# ---------------------------------------------------------------------------
# AC 3 -- refus NOMME et CHIFFRE au-dela de CANONICAL_ID_MAX_LENGTH (64).
# ---------------------------------------------------------------------------


def test_build_lot_id_refuse_nommement_au_dela_de_64_avec_version():
    # `rush_id` de 62 caracteres + "_v99" (4) = 66 > 64.
    rush_id = "R" * 62
    with pytest.raises(naming.NamingError) as excinfo:
        naming.build_lot_id(rush_id, 24.0, version_rank=99)
    message = str(excinfo.value)
    assert "trop long" in message
    assert "nouvelle version" in message
    assert "99" in message


def test_un_rush_id_COURT_passe_avec_ET_sans_version(tmp_path):
    """Controle negatif de l'AC 3 : la garde ne refuse pas tout.

    **Sa premiere redaction affirmait une chose fausse**, mesuree par
    l'auditeur : elle prenait un `rush_id` de 62 caracteres et disait « le
    meme sans version passe, la marge existe grace au fragment absent ».
    Or `"R"*62 + "_24"` fait 65 caracteres -- il n'y a aucune marge. Il
    « passait » parce qu'aucun refus n'existe sur le chemin NON versionne,
    et `build_lot_id` rendait alors un condensat court DIVERGENT du slug
    (une violation d'ARB-3, pas une reussite). L'assertion
    `startswith("R")` etait vraie des deux facons : elle ne mesurait rien.

    Le controle negatif se fait donc sur un nom court, ou les deux chemins
    passent VRAIMENT et sans condensat.
    """
    lot_court = naming.build_lot_id("rush-001", 24.0)
    lot_versionne = naming.build_lot_id("rush-001", 24.0, version_rank=2)
    assert lot_court == "rush-001_24"
    assert lot_versionne == "rush-001_24_v2"
    # aucun condensat : le nom est rendu entier, donc il egale son slug
    assert lot_versionne == project_layout.rush_dir_slug("rush-001", 24.0, version_rank=2)


def test_le_refus_de_longueur_encadre_la_borne_COURANTE():
    """La borne se lit a sa SOURCE, elle ne se chiffre plus en dur.

    **Ce test s'appelait `..._contre_64_ET_PAS_48` et figeait 64.** Il avait
    ete ecrit pour fermer un vrai defaut -- un mutant qui remplacait 64 par 48
    survivait a toute la suite, rien ne mesurait le chiffre. Mais il l'a ferme
    de la mauvaise facon : en figeant une VALEUR au lieu d'une PROPRIETE.

    Le 2026-08-31, `EPIC11-ARB-110` a ramene la borne a 48 sur mesure -- la
    falaise QR est a 58 caracteres, et 64 la franchissait. Ce test a alors
    rougi en accusant le correctif (« la borne de main a bouge »), alors que
    c'est lui qui portait la valeur perimee. Un test qui fige un chiffre
    devient l'obstacle au prochain arbitrage sur ce chiffre.

    Ce qu'il mesure desormais est la propriete, et elle mord autant : la borne
    est lue au module, et le seuil est encadre des DEUX cotes -- juste en
    dessous ca passe, juste au-dessus ca refuse. Un mutant qui change la borne
    du module sans changer la garde fait toujours rougir ; un arbitrage qui la
    change des deux cotes passe, ce qui est le comportement voulu.
    """
    borne = naming.CANONICAL_ID_MAX_LENGTH
    assert borne >= 8, "une borne aussi basse ne laisserait pas un identifiant lisible"

    fragment = "_24_v2"  # 6 caracteres
    # Le plus long rush_id qui tient EXACTEMENT sous la borne.
    rush_ok = "R" * (borne - len(fragment))
    lot = naming.build_lot_id(rush_ok, 24.0, version_rank=2)
    assert len(lot) == borne
    assert lot == f"{rush_ok}{fragment}", "un condensat s'est glisse sous la borne"

    # Un seul caractere de plus, et le refus mord -- nomme et chiffre.
    with pytest.raises(naming.NamingError) as refus:
        naming.build_lot_id(rush_ok + "R", 24.0, version_rank=2)
    message = str(refus.value)
    assert str(borne) in message, "le refus ne CHIFFRE pas la borne"
    assert "nouvelle version" in message


def test_l_ordre_des_fragments_tient_AUSSI_avec_des_bornes():
    """ARB-3 sur le cas COMPOSE, que le seul test croise ne couvrait pas.

    **Un mutant qui posait le fragment de version AVANT le suffixe de bornes
    dans `rush_dir_slug` survivait** (mesure de l'auditeur) : le test croise
    existant comparait les deux chaines SANS bornes, ou l'ordre ne se voit
    pas. L'identifiant (`rush_24-<sfx>_v2`) et le dossier
    (`rush_24_v2-<sfx>`) divergeaient sans que rien ne le voie.
    """
    bornes = {"source_in_timecode": "00:00:01:00", "source_out_timecode": "00:00:02:00"}
    lot_id = naming.build_lot_id("rush-001", 24.0, version_rank=2, **bornes)
    slug = project_layout.rush_dir_slug("rush-001", 24.0, version_rank=2, **bornes)

    assert lot_id == slug, "identifiant et nom de dossier divergent (ARB-3)"
    # et l'ordre est bien cadence, PUIS bornes, PUIS version
    suffixe = naming.bounds_suffix(**bornes)
    assert lot_id == f"rush-001_24-{suffixe}_v2"
    assert lot_id.index(suffixe) < lot_id.index("_v2")


# ---------------------------------------------------------------------------
# AC 4 -- champs de schema `version_rank` et `base_lot_id`, additifs.
# ---------------------------------------------------------------------------


def test_le_schema_valide_un_manifeste_a_trois_versions(tmp_path):
    manifest = _manifeste_a_trois_versions_et_un_trou()
    manifest["created"] = "2026-08-30T00:00:00Z"
    manifest["artifacts"] = {}
    manifest["color"] = {}
    manifest["video"] = {}
    manifest["reconstruction"] = {}
    manifest["rushes"] = [
        {"rush_id": "rush-001"},
        {"rush_id": "rush-002"},
    ]
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    io_manifest.validate_manifest(chemin)


def test_un_manifeste_anterieur_sans_les_deux_champs_reste_valide(tmp_path):
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet-test",
        "created": "2026-08-30T00:00:00Z",
        "rushes": [{"rush_id": "rush-001"}],
        "lots": [{"lot_id": "rush-001_24", "rush_id": "rush-001"}],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    io_manifest.validate_manifest(chemin)


def _manifeste_minimal_avec_rang(rang):
    """Manifeste v2.1 minimal portant UN lot versionne au rang donne.

    Sert aux deux bornes du schema : c'est le plus petit manifeste que
    `validate_manifest` accepte, pour que le seul motif de refus possible
    soit la valeur de `version_rank` elle-meme.
    """
    return {
        "schema_version": "2.1",
        "project_id": "projet-test",
        "created": "2026-08-30T00:00:00Z",
        "rushes": [{"rush_id": "rush-001"}],
        "lots": [
            {
                "lot_id": "rush-001_24",
                "rush_id": "rush-001",
                "version_rank": rang,
                "base_lot_id": "rush-001_24",
            }
        ],
        "artifacts": {},
        "color": {},
        "video": {},
        "reconstruction": {},
    }


@pytest.mark.parametrize("rang_hors_bornes", [0, 1, 100, 9999, -1])
def test_le_schema_REFUSE_un_rang_hors_des_bornes_2_a_99(tmp_path, rang_hors_bornes):
    """AC 4, **mutant survivant** trouve par l'Acceptance Auditor Opus.

    `minimum: 2` / `maximum: 99` etaient poses au schema et mesures par
    RIEN : les relacher en `0` / `9999` ne faisait rougir aucun des 196
    tests. Meme famille exacte que le mutant `64 -> 48` ferme sur
    `CANONICAL_ID_MAX_LENGTH` -- un chiffre que le code porte mais que le
    banc ne tient pas est un chiffre libre de deriver.

    Les deux bornes comptent pour une raison differente. En bas : le rang 1
    est l'ORIGINE, qui ne porte AUCUN fragment de nom (`EPIC11-ARB-88`) --
    un lot ecrit avec `version_rank: 1` porterait donc un rang que son
    `lot_id` ne dit pas, soit la divergence nom/manifeste qu'`EPIC5-ARB-3`
    interdit ; et le rang 0 n'a pas de sens du tout. En haut : `_v100` est
    deux caracteres de plus que ce que `format_version_suffix` sait
    produire, donc un rang au-dela de 99 serait ecrit au manifeste sans que
    le nom puisse jamais le porter.
    """
    chemin = tmp_path / "project.json"
    chemin.write_text(
        json.dumps(_manifeste_minimal_avec_rang(rang_hors_bornes)), encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        io_manifest.validate_manifest(chemin)


@pytest.mark.parametrize("rang_admis", [2, 3, 98, 99])
def test_le_schema_ADMET_les_deux_bornes_exactes_et_leurs_voisins(tmp_path, rang_admis):
    """Controle negatif du test ci-dessus : sans lui, un schema qui
    refuserait TOUT rang le rendrait vert. Les bornes exactes 2 et 99
    passent, ainsi que leurs voisins interieurs -- l'encadrement est donc
    ferme des deux cotes, comme pour la borne de longueur de l'AC 3."""
    chemin = tmp_path / "project.json"
    chemin.write_text(
        json.dumps(_manifeste_minimal_avec_rang(rang_admis)), encoding="utf-8"
    )
    io_manifest.validate_manifest(chemin)


def test_les_bornes_du_schema_et_celles_du_code_sont_les_MEMES(tmp_path):
    """Deux emplacements pour le meme fait, ce sont deux verites
    (`EPIC5-ARB-78`). Le schema dit `2..99`, `naming` dit
    `VERSION_RANK_MIN..VERSION_RANK_MAX` : ils se lisent l'un contre
    l'autre, sinon un rang accepte par l'un serait refuse par l'autre --
    et le manifeste porterait un lot que le nommage ne sait pas ecrire."""
    schema = json.loads(
        (io_manifest.DEFAULT_SCHEMA_PATH).read_text(encoding="utf-8")
    )
    champ = schema["properties"]["lots"]["items"]["properties"]["version_rank"]
    assert champ["minimum"] == naming.VERSION_RANK_MIN
    assert champ["maximum"] == naming.VERSION_RANK_MAX


# ---------------------------------------------------------------------------
# AC 4/AC 5 (suite) -- ExtractionRecord.version_rank/base_lot_id atteignent
# VRAIMENT la persistance.
# ---------------------------------------------------------------------------


def _record_de_version(fps_target: float = 24.0, version_rank: int | None = 2) -> ExtractionRecord:
    rush_id = "rush-persistance"
    selection = select_source_frames(fps_source=30, fps_target=fps_target, source_frame_count=100)
    lot_id = naming.build_lot_id(rush_id, fps_target, version_rank=version_rank)
    base_lot_id = naming.build_lot_id(rush_id, fps_target) if version_rank is not None else None
    return ExtractionRecord(
        project_id="projet",
        rush_id=rush_id,
        rush_source_name=f"{rush_id}.mp4",
        lot_id=lot_id,
        frames_dir_relative=f"{project_layout.EXTRACT_FRAMES_DIRNAME}/{project_layout.rush_dir_slug(rush_id, fps_target, version_rank=version_rank)}",
        selection=selection,
        fps_source=30.0,
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-08-30T09:30:00Z",
        version_rank=version_rank,
        base_lot_id=base_lot_id,
    )


def test_un_lot_de_version_passe_la_garde_d_entree_de_la_persistance():
    """Piege identifie au developpement: `_check_record` recalculait le
    lot_id SANS `version_rank`, donc tout lot versionne echouait sa propre
    garde d'identite (AC 5) avant meme d'atteindre l'ecriture."""
    record = _record_de_version()
    manifest = build_extraction_manifest(None, record)
    lot = manifest["lots"][0]
    assert lot["version_rank"] == 2
    assert lot["base_lot_id"] == naming.build_lot_id("rush-persistance", 24.0)


def test_un_lot_de_rang_1_ne_porte_ni_version_rank_ni_base_lot_id():
    record = _record_de_version(version_rank=None)
    manifest = build_extraction_manifest(None, record)
    lot = manifest["lots"][0]
    assert "version_rank" not in lot
    assert "base_lot_id" not in lot


def test_base_lot_id_incoherent_est_refuse():
    import dataclasses

    record = _record_de_version()
    incoherent = dataclasses.replace(
        record, base_lot_id="un-lot-qui-n-est-pas-le-vrai-lot-d-origine"
    )
    with pytest.raises(LotIdentityMismatchError):
        build_extraction_manifest(None, incoherent)


def test_version_rank_sans_base_lot_id_est_refuse():
    import dataclasses

    record = _record_de_version()
    moitie = dataclasses.replace(record, base_lot_id=None)
    with pytest.raises(extraction_manifest.ExtractionPersistenceError):
        build_extraction_manifest(None, moitie)


# ---------------------------------------------------------------------------
# Findings de la revue en trois couches (Blind Hunter + Acceptance Auditor,
# 2026-08-30) : fermes ici, avec le mutant qui les reinjecte pour preuve.
# ---------------------------------------------------------------------------


def test_nouvelle_version_et_overwrite_ne_sont_PAS_exclusifs(tmp_path):
    """`--nouvelle-version` et `--overwrite` sont ORTHOGONAUX, et les rendre
    exclusifs produisait un BLOCAGE SEC (revue Opus du 2026-08-30, trouve
    independamment par deux couches).

    Le regime : `nouvelle_version` choisit QUEL lot est vise, `overwrite` dit
    quoi faire si le dossier de ce lot est deja peuple. L'exclusion posee par
    la premiere passe de revue reposait sur « le dossier de la nouvelle
    version est neuf » -- premisse fausse des qu'un dossier de version
    orphelin traine, ce que produit toute panne de persistance apres ffmpeg.
    L'operateur se retrouvait alors devant un refus qui prescrivait
    `--overwrite`, un second refus qui l'interdisait, et un troisieme sur
    `--ecrasement-conscient` : zero issue, la forme meme qu'`EPIC11-ARB-89`
    interdit.
    """
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "pdf")
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        _run_a_l_etape_1(projet, rush, nouvelle_version=True, overwrite=True)


def test_aucune_impasse_sur_un_dossier_de_version_ORPHELIN(tmp_path):
    """Le scenario complet du blocage sec, mesure de bout en bout.

    Un dossier `_v2` peuple SANS entree manifeste correspondante (panne de
    persistance apres ffmpeg). Au moins une issue doit rester atteignable --
    c'est litteralement ce que la politique exige.
    """
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "pdf")
    orphelin = projet / project_layout.EXTRACT_FRAMES_DIRNAME / naming.build_lot_id(
        RUSH_ID, CADENCE_VISEE, version_rank=2)
    orphelin.mkdir(parents=True)
    (orphelin / "residu.tiff").write_bytes(b"residu d'une passe interrompue")

    # sans rien : refus AC 9, legitime -- mais il doit exister une issue
    with pytest.raises(extraction.ExtractionInputError):
        _run_a_l_etape_1(projet, rush, nouvelle_version=True)

    # l'issue : elle passe l'etape 1 au lieu d'etre refusee a son tour
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        _run_a_l_etape_1(projet, rush, nouvelle_version=True, overwrite=True)


def test_ecrasement_conscient_avertit_MEME_sans_conflit_d_etat(tmp_path):
    """AC 7 (Blind Hunter) : un lot encore en etat `extraction` (donc SANS
    LotStateConflictError) dont le dossier de frames porte deja des
    fichiers doit recevoir le MEME avertissement qu'un ecrasement qui
    traverse un refus d'etat -- sinon il est efface en silence."""
    projet, rush = _projet_avec_lot_en_etat_aval(tmp_path, "extraction")
    dossier = projet / project_layout.EXTRACT_FRAMES_DIRNAME / naming.build_lot_id(RUSH_ID, CADENCE_VISEE)
    dossier.mkdir(parents=True)
    (dossier / "frame_existante.tiff").write_bytes(b"deja la")

    journal = _JournalMuet()
    avertissements = []
    journal.warning = lambda *a, **k: avertissements.append((a, k))

    # `FfmpegNotFoundError` NOMME l'endroit atteint. Les deux
    # `assert not isinstance(...)` d'origine etaient verts pour toute
    # exception qui n'etait ni l'une ni l'autre -- y compris une panne
    # d'import : ils mesuraient l'absence de deux refus, jamais la
    # presence du passage (mesure de l'auditeur Opus, finding O7).
    with pytest.raises(ffmpeg_utils.FfmpegNotFoundError):
        extraction.run_extraction(
            project_dir=projet,
            video_path=rush,
            fps_target=CADENCE_VISEE,
            ecrasement_conscient=True,
            consent_granted=True,
            unknown_color_accepted=True,
            logger=journal,
            ffmpeg_binary=FFMPEG_ABSENT,
            ffprobe_binary=FFPROBE_ABSENT,
        )
    assert avertissements, "aucun avertissement AC 7 n'a ete emis"
    # **Le CONTENU, pas seulement la presence** : la premiere redaction
    # n'assertait que « la liste n'est pas vide », donc vider entierement le
    # message la laissait verte (mesure de l'auditeur Opus).
    rendu = " ".join(str(a) for args, _ in avertissements for a in args)
    # L'ETAT, et non le mot. `assert "extraction" in rendu` etait
    # TAUTOLOGIQUE : le gabarit fixe contient deja « Cette extraction a ete
    # demandee », si bien que retirer l'etat du message laissait ce test
    # vert (mutant O8 de l'auditeur Opus, mesure). L'etat est interpole en
    # `{current_state!r}` : c'est sa forme CITEE qui prouve qu'il est pose.
    assert repr("extraction") in rendu, (
        "l'avertissement ne NOMME pas l'etat courant du lot"
    )
    assert "PDF imprime" in rendu and "scans" in rendu, (
        "l'avertissement ne dit pas CE QUI sera perdu"
    )


# ---------------------------------------------------------------------------
# AC 12 -- frontieres de perimetre (Blind Hunter : seule l'AC 8 (tui/ absent)
# etait mesuree ; les autres greps de la story restaient de la prose).
# Gardes PERMANENTES, independantes de git (piege BH-9 de la story 5.27 :
# une frontiere fondee sur un intervalle de commits devient vacante des le
# premier squash-merge).
# ---------------------------------------------------------------------------

import mixed_media_utility.io.manifest as _io_manifest_module


def test_LOT_STATES_est_inchangee():
    """AC 12 : aucune modification de LOT_STATES -- la machine a etats n'est
    pas touchee, seul un contournement explicite et journalise existe."""
    assert _io_manifest_module.LOT_STATES == (
        "extraction", "pdf", "scan", "reconstruction", "encode",
    )


def test_la_suppression_est_ATTEIGNABLE_par_la_ligne_de_commande():
    """AC 12, **renversee par l'arbitrage d'Egan du 2026-08-30**.

    La premiere redaction de ce test verrouillait l'ABSENCE de commande
    (« la suppression est hors perimetre, elle vient avec une surface »).
    La revue Opus a mesure ce que cela signifiait : `remove_project_element`
    etait ecrite, testee, et **inatteignable** -- l'operateur restait devant
    le `git rm -r` a la main qui a detruit des frames non commitees le
    2026-08-27. Or la regle de `CLAUDE.md` posee par cette meme story
    declare la suppression indispensable (« sans laquelle les deux
    premieres sont une fuite »).

    Un test qui fige un etat que la politique condamne est pire qu'absent :
    il le fait passer pour voulu. Il mesure desormais l'inverse.
    """
    import mixed_media_utility.cli as cli_module

    source = Path(cli_module.__file__).read_text(encoding="utf-8")
    assert "project_maintenance" in source, (
        "la commande de suppression a disparu de la CLI : la troisieme "
        "operation d'EPIC11-ARB-89 redevient inatteignable"
    )
    assert callable(cli_module.project_remove_command)


def test_aucun_module_gui_ne_reference_project_maintenance():
    """AC 12 : aucun ecran, aucun cablage."""
    racine = Path(extraction.__file__).resolve().parent
    dossier_gui = racine / "gui"
    if not dossier_gui.is_dir():
        pytest.skip("gui/ absent de cette branche")
    for fichier in dossier_gui.rglob("*.py"):
        source = fichier.read_text(encoding="utf-8")
        assert "project_maintenance" not in source, f"{fichier} reference project_maintenance"
        assert "remove_project_element" not in source, f"{fichier} reference remove_project_element"


# ---------------------------------------------------------------------------
# Vague A (arbitrage d'Egan du 2026-08-30, « aller au bout ») -- le
# versionnage traverse TOUT le circuit, pas seulement l'extraction.
#
# Le defaut ferme ici, mesure par la revue Opus : `_v2` avait ete offert a
# `frames_dir` et a `build_lot_id`, mais ni au scan, ni au dossier des images
# rescannees, ni a la creation de l'arborescence. Une version 2 s'extrayait,
# s'imprimait, et se faisait refuser au scan -- apres que le travail physique
# (impression, passage scanner) etait engage.
# ---------------------------------------------------------------------------


def test_le_scan_RECONNAIT_un_lot_versionne(tmp_path):
    """`derive_lot_dir_slug` refusait `rush-001_4_v2` : circuit coupe."""
    from mixed_media_utility.scan_output_frames import derive_lot_dir_slug

    lot_id = naming.build_lot_id("rush-001", 4, version_rank=2)
    assert derive_lot_dir_slug(rush_id="rush-001", fps_target=4, lot_id=lot_id) == lot_id


def test_le_scan_reconnait_un_lot_BORNE_ET_versionne():
    """Les deux axes se composent : le cas le plus long doit passer aussi."""
    from mixed_media_utility.scan_output_frames import derive_lot_dir_slug

    bornes = {"source_in_timecode": "00:00:01:00", "source_out_timecode": "00:00:02:00"}
    lot_id = naming.build_lot_id("rush-001", 4, version_rank=3, **bornes)
    assert derive_lot_dir_slug(rush_id="rush-001", fps_target=4, lot_id=lot_id) == lot_id
    assert lot_id == project_layout.rush_dir_slug("rush-001", 4, version_rank=3, **bornes)


def test_le_scan_REFUSE_TOUJOURS_un_lot_etranger():
    """Controle negatif : sans lui, une garde qui accepterait TOUT serait
    verte sur les deux tests ci-dessus."""
    from mixed_media_utility.scan_output_frames import (
        LotInconsistencyError,
        derive_lot_dir_slug,
    )

    with pytest.raises(LotInconsistencyError):
        derive_lot_dir_slug(rush_id="rush-001", fps_target=4, lot_id="rush-002_9_v2")


def test_les_DEUX_moities_d_un_lot_versionne_portent_le_MEME_slug(tmp_path):
    """`extract-frames/` et `frames-scannees/` d'un meme lot ne divergent jamais (ARB-3).

    Mesure sur les DEUX chemins produits, jamais sur le cablage.
    """
    entree = project_layout.extract_frames_dir(tmp_path, "rush-001", 4, version_rank=2)
    sortie = project_layout.scan_frames_dir(tmp_path, "rush-001", 4, version_rank=2)
    assert entree.name == sortie.name == "rush-001_4_v2"
    # et le lot d'origine garde les siens, distincts
    assert project_layout.extract_frames_dir(tmp_path, "rush-001", 4).name == "rush-001_4"
    assert project_layout.scan_frames_dir(tmp_path, "rush-001", 4).name == "rush-001_4"


def test_l_arborescence_cree_le_dossier_de_LA_VERSION_pas_celui_de_l_original(tmp_path):
    """`ensure_project_layout` recreait le dossier NON versionne d'un lot
    versionne -- un dossier vide qui n'appartient a aucun lot, pendant que le
    vrai dossier du lot n'etait jamais cree. Le defaut etait deja decrit mot
    pour mot dans la docstring de `_iter_rush_fps_pairs`, pour les bornes.
    """
    projet = tmp_path / "projet"
    manifest = {
        "schema_version": "2.1",
        "lots": [
            {
                "lot_id": "rush-001_4_v2",
                "rush_id": "rush-001",
                "fps_target": 4,
                "version_rank": 2,
                "base_lot_id": "rush-001_4",
            }
        ],
    }
    project_layout.ensure_project_layout(projet, manifest)

    assert (projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_4_v2").is_dir(), "le dossier du lot manque"
    assert (projet / project_layout.SCAN_FRAMES_DIRNAME / "rush-001_4_v2").is_dir()
    assert not (projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_4").exists(), (
        "un dossier vide n'appartenant a aucun lot a ete cree"
    )


def test_l_arborescence_distingue_l_original_et_sa_version(tmp_path):
    """Fabrique a trois lots, la version au MILIEU : un `find` fautif ou une
    boucle qui s'arrete au premier tour se demasquent."""
    projet = tmp_path / "projet"
    manifest = {
        "schema_version": "2.1",
        "lots": [
            {"lot_id": "rush-002_5", "rush_id": "rush-002", "fps_target": 5},
            {
                "lot_id": "rush-001_4_v2", "rush_id": "rush-001", "fps_target": 4,
                "version_rank": 2, "base_lot_id": "rush-001_4",
            },
            {"lot_id": "rush-001_4", "rush_id": "rush-001", "fps_target": 4},
        ],
    }
    project_layout.ensure_project_layout(projet, manifest)

    crees = sorted(p.name for p in (projet / project_layout.EXTRACT_FRAMES_DIRNAME).iterdir())
    assert crees == ["rush-001_4", "rush-001_4_v2", "rush-002_5"]



def test_le_texte_d_avertissement_est_RENDU_pas_seulement_journalise():
    """AC 7 : le contrat que les trois surfaces consommeront.

    **La fiche promettait un texte « retourne, jamais imprime directement par
    le coeur », et le code n'en faisait qu'un `logger.warning`** (mesure de
    l'auditeur Opus) : inconsommable par un ecran, donc la TUI et la GUI
    auraient reformule le leur -- la divergence qu'`EPIC5-ARB-78` interdit.

    Il nomme l'etat courant : sans lui, l'operateur lit « ce lot va etre
    ecrase » sans savoir s'il ecrase un lot deja imprime ou deja scanne,
    c'est-a-dire precisement ce qui rend le consentement conscient.
    """
    texte = extraction_manifest.message_avertissement_ecrasement("rush-001_4", "scan")

    assert "rush-001_4" in texte
    assert "scan" in texte, "l'etat courant n'est pas nomme"
    assert "PDF imprime" in texte and "payloads QR" in texte
    # deux etats differents produisent deux textes differents : le message est
    # bien fonction de l'etat, pas une phrase fixe ou l'etat serait decoratif
    autre = extraction_manifest.message_avertissement_ecrasement("rush-001_4", "encode")
    assert texte != autre


def test_un_ecrasement_conscient_PURGE_l_aval_du_lot():
    """Le manifeste cesse de declarer des artefacts qui ne correspondent plus.

    **Mesure de la revue Opus finale** : `_build_lot` part de
    `dict(existing)`, donc un lot ramene de `encode` a `extraction` gardait
    `output_frames_dir`, `reconstructed_frame_count`, `synthetic_frames` et
    `encoded_masters` du cycle PRECEDENT. `encode` lit `output_frames_dir` et
    le cardinal : il aurait encode les images rescannees de l'ancien cycle
    comme master de la NOUVELLE extraction, sans rien detecter -- les
    cardinaux coincident par construction. L'avertissement AC 7 promet a
    l'operateur que les artefacts aval « ne correspondront plus » : le
    manifeste doit cesser de les declarer, sinon il ment juste apres.
    """
    import dataclasses

    record = _record_de_version(version_rank=None)
    existant = build_extraction_manifest(None, record)
    lot = existant["lots"][0]
    lot["state"] = "encode"
    lot["output_frames_dir"] = "output-frames/rush-persistance_24"
    lot["reconstructed_frame_count"] = 14
    lot["synthetic_frames"] = ["p01.tiff"]
    lot["encoded_masters"] = [{"path": "outputs/m.mov", "profile_id": "prores_hq"}]

    conscient = dataclasses.replace(record, ecrasement_conscient=True)
    apres = build_extraction_manifest(existant, conscient)["lots"][0]

    assert apres["state"] == "extraction"
    for champ in ("output_frames_dir", "reconstructed_frame_count",
                  "synthetic_frames", "encoded_masters"):
        assert champ not in apres, f"{champ} survit et fait mentir le manifeste"


def test_une_extraction_ORDINAIRE_ne_purge_RIEN():
    """Controle negatif : sans lui, une purge inconditionnelle serait verte
    sur le test ci-dessus tout en detruisant l'aval de chaque re-extraction
    idempotente."""
    record = _record_de_version(version_rank=None)
    existant = build_extraction_manifest(None, record)
    existant["lots"][0]["output_frames_dir"] = "output-frames/rush-persistance_24"
    existant["lots"][0]["reconstructed_frame_count"] = 14

    apres = build_extraction_manifest(existant, record)["lots"][0]

    assert apres["output_frames_dir"] == "output-frames/rush-persistance_24"
    assert apres["reconstructed_frame_count"] == 14


def test_resolve_version_rank_epuise_offre_une_ISSUE_nommee():
    """99 rangs pris : le refus doit nommer une sortie, pas dire « hors
    bornes ». Sans borne haute, l'erreur venait de `format_version_suffix`
    avec un message parlant du rang 1 -- un blocage sec."""
    base = naming.build_lot_id("rush-001", 24.0)
    manifest = {
        "schema_version": "2.1",
        "lots": [
            {"lot_id": f"rush-001_24_v{r}", "rush_id": "rush-001",
             "base_lot_id": base, "version_rank": r}
            for r in range(naming.VERSION_RANK_MIN, naming.VERSION_RANK_MAX + 1)
        ],
    }
    with pytest.raises(extraction_manifest.ExtractionPersistenceError) as refus:
        extraction_manifest.resolve_version_rank(manifest, "rush-001", 24.0)
    message = str(refus.value)
    assert "project remove" in message, "aucune issue nommee"
    assert "ecraser sciemment" in message, "la seconde issue manque"


# ---------------------------------------------------------------------------
# `EPIC11-ARB-108` -- la ligne d'eau des LOTS, ecrite au retrait.
#
# Les trois couches de la revue du 2026-08-31 ont mesure le meme defaut par
# trois chemins : `lot_version_watermarks` etait declare au schema et lu par le
# resolveur, mais AUCUN chemin ne l'ecrivait. Retirer la version 3 d'une
# famille faisait retomber le prochain rang a 3 -- rendre le rang PAR DEFAUT,
# l'inverse exact du point 3 d'`EPIC11-ARB-92`.
# ---------------------------------------------------------------------------


def _famille_de_lots(tmp_path, rangs=(1, 2, 3), ligne_declaree=None):
    """Une famille dont la cible n'est PAS en premiere position, et un SECOND
    rush dont les rangs ne doivent jamais se melanger aux siens."""
    base = "rush-001_12p5"
    lots = [{"lot_id": "rush-002_24", "rush_id": "rush-002", "fps_target": 24.0}]
    for rang in rangs:
        if rang == 1:
            lots.append({"lot_id": base, "rush_id": "rush-001", "fps_target": 12.5})
        else:
            lots.append({
                "lot_id": f"{base}_v{rang}", "rush_id": "rush-001",
                "fps_target": 12.5, "version_rank": rang, "base_lot_id": base,
            })
    lots.append({"lot_id": "rush-002_24_v7", "rush_id": "rush-002",
                 "fps_target": 24.0, "version_rank": 7,
                 "base_lot_id": "rush-002_24"})
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "rush-001"}, {"rush_id": "rush-002"}],
        "lots": lots,
    }
    if ligne_declaree is not None:
        manifest["lot_version_watermarks"] = {base: ligne_declaree}
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    for lot in lots:
        dossier = projet / project_layout.EXTRACT_FRAMES_DIRNAME / lot["lot_id"]
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(b"f")
    return projet


def _prochain_rang_de_lot(projet, rush_id="rush-001", fps=12.5):
    manifest = json.loads((projet / "project.json").read_text())
    return extraction_manifest.resolve_version_rank(manifest, rush_id, fps)


def test_retirer_la_DERNIERE_version_ne_rend_PAS_son_rang_par_defaut(tmp_path):
    """Le defaut garde le rang consomme (`EPIC11-ARB-92`, point 3)."""
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    assert _prochain_rang_de_lot(projet) == 4
    project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v3", dry_run=False)
    # La revue mesurait 3 ici : le rang venait d'etre rendu sans qu'on le demande.
    assert _prochain_rang_de_lot(projet) == 4
    manifest = json.loads((projet / "project.json").read_text())
    assert manifest["lot_version_watermarks"]["rush-001_12p5"] == 3
    # L'autre famille n'a pas bouge -- son rang 7 reste le sien.
    assert _prochain_rang_de_lot(projet, "rush-002", 24.0) == 8


def test_liberer_explicitement_le_rang_du_DERNIER_lot_le_rend(tmp_path):
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    rapport = project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v3", dry_run=False, liberer_le_rang=True)
    assert rapport.rang_libere is True
    assert rapport.rangs_liberables == (3,)
    assert _prochain_rang_de_lot(projet) == 3


def test_liberer_le_rang_d_un_lot_du_MILIEU_est_refuse_nommement(tmp_path):
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    with pytest.raises(project_maintenance.ProjectMaintenanceError) as erreur:
        project_maintenance.remove_project_element(
            projet, lot_id="rush-001_12p5_v2", dry_run=False, liberer_le_rang=True)
    assert "CONSOMME" in str(erreur.value)
    # Rien n'a ete supprime : le refus tombe AVANT toute ecriture.
    assert (projet / project_layout.EXTRACT_FRAMES_DIRNAME / "rush-001_12p5_v2").is_dir()
    assert _prochain_rang_de_lot(projet) == 4


def test_la_queue_des_lots_se_rend_D_UN_BLOC_comme_pour_les_planches(tmp_path):
    """Le scenario d'Egan, verbatim : « si la v3 existe et que je supprime la
    v2 le prochain rang dispo reste la v4 ... puis je choisis de supprimer v3.
    On peut alors liberer d'un seul coup v2 et v3 »."""
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v2", dry_run=False)
    assert _prochain_rang_de_lot(projet) == 4
    rapport = project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v3", dry_run=False, liberer_le_rang=True)
    assert rapport.rangs_liberables == (2, 3)
    assert _prochain_rang_de_lot(projet) == 2


def test_rendre_la_famille_de_lots_a_l_ORIGINE_RETIRE_la_cle(tmp_path):
    """L'omission stricte dit l'origine ; ecrire 1 serait une ligne DECLAREE."""
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path, rangs=(1, 2))
    project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v2", dry_run=False, liberer_le_rang=True)
    manifest = json.loads((projet / "project.json").read_text())
    assert "rush-001_12p5" not in manifest.get("lot_version_watermarks", {})
    assert _prochain_rang_de_lot(projet) == 2


def test_liberer_le_rang_d_un_RUSH_est_refuse_au_lieu_d_etre_ignore(tmp_path):
    """Un drapeau sans effet est un mensonge (revue, couches 2 et 3)."""
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    with pytest.raises(project_maintenance.ProjectMaintenanceError) as erreur:
        project_maintenance.remove_project_element(
            projet, rush_id="rush-002", dry_run=False, liberer_le_rang=True)
    assert "rang de version" in str(erreur.value)


def test_l_apercu_du_retrait_d_un_lot_ANNONCE_ce_que_la_confirmation_ferait(tmp_path):
    from mixed_media_utility import project_maintenance

    projet = _famille_de_lots(tmp_path)
    apercu = project_maintenance.remove_project_element(
        projet, lot_id="rush-001_12p5_v3", dry_run=True, liberer_le_rang=True)
    assert apercu.rangs_liberables == (3,)
    assert apercu.objet_en_queue is True
    assert apercu.rang_libere is True
    # Et l'apercu n'a RIEN ecrit.
    manifest = json.loads((projet / "project.json").read_text())
    assert "lot_version_watermarks" not in manifest


def test_la_ligne_d_eau_est_bornee_par_le_HAUT_autant_que_par_le_BAS():
    """Trouve en revue (couche 2, vague 3) : elle ne l'etait que par le bas.

    Rien ne valide `lots[].version_rank` a la LECTURE. Un seul rang hors bornes
    dans un manifeste abime ou edite faisait rendre a `rangs_liberables` la
    queue entiere : mesure, `9 999 999` produisait 9 999 998 rangs et 400 Mo,
    que la CLI joignait ensuite pour les imprimer. `VERSION_RANK_MAX` est la
    borne du domaine -- au-dela, la valeur ne designe aucun objet nommable.
    """
    from mixed_media_utility.io import version_ranks

    ligne = version_ranks.ligne_d_eau(9_999_999, {1})
    assert ligne == naming.VERSION_RANK_MAX
    assert len(version_ranks.rangs_liberables(ligne, {1})) < 100

    # Bornee par le bas AUSSI, et le cas nominal reste intact -- sans ces deux
    # controles, un `return VERSION_RANK_MAX` constant passerait le test.
    assert version_ranks.ligne_d_eau(-3, {1}) == version_ranks.RANG_ORIGINE
    assert version_ranks.ligne_d_eau(None, {1, 2, 3}) == 3
    assert version_ranks.rangs_liberables(3, {1}) == (2, 3)
