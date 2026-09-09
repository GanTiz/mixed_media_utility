"""Versionnage des SCANS -- `EPIC11-ARB-104` (Egan, 2026-08-31).

« Tout doit etre versionnable OU ecrase. » Le scan etait le dernier objet du
circuit a ne pas l'etre, et le scenario qui l'a montre est celui d'Egan :

    « J'ai fait une planche, je l'ai imprimee, je l'ai scannee et je l'ai
    extraite. Sur une frame je me dis que j'aurais pu ajouter un petit point
    rouge dans un coin. Je reprends la planche imprimee, je rajoute le point et
    je rescanne le lot. On me dit que le scan existe deja ! Pourtant j'ai
    modifie quelque chose. »

Un objet dont le CONTENU change sans que son IDENTITE change n'est ni un
doublon ni une erreur : c'est une version.

Difference de nature avec les trois autres objets versionnables, et elle
commande la conception : la famille d'un scan est indexee par son SLUG et non
par un lot, parce qu'a l'ingestion le lot n'est pas connu -- il est porte par
le QR, decode a l'etape suivante.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from mixed_media_utility import scan_ingest
from mixed_media_utility.io import naming, project_layout, version_ranks


def _page(couleur=240, point_rouge=False):
    image = np.full((400, 300, 3), couleur, np.uint8)
    if point_rouge:
        cv2.circle(image, (280, 20), 8, (0, 0, 255), -1)
    return image


@pytest.fixture()
def projet_et_source(tmp_path):
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    source = tmp_path / "scan-WIN"
    source.mkdir()
    cv2.imwrite(str(source / "p1.tiff"), _page())
    return projet, source


# ---------------------------------------------------------------------------
# Le NOM du dossier.
# ---------------------------------------------------------------------------


def test_le_rang_entre_dans_le_nom_du_dossier_de_scan():
    assert project_layout.scan_lot_dir("/p", "scan-WIN").name == "scan-WIN"
    assert project_layout.scan_lot_dir(
        "/p", "scan-WIN", version_rank=2).name == "scan-WIN_v2"


def test_le_rang_1_ne_porte_AUCUN_fragment():
    """`EPIC11-ARB-88` : l'origine ne porte pas de suffixe -- sans quoi tous les
    dossiers de scan deja ingeres porteraient un nom que le code ne produit
    plus."""
    sans = project_layout.scan_lot_dir("/p", "scan-WIN")
    avec_none = project_layout.scan_lot_dir("/p", "scan-WIN", version_rank=None)
    assert sans == avec_none and "_v" not in sans.name


# ---------------------------------------------------------------------------
# Le SCENARIO D'EGAN, de bout en bout.
# ---------------------------------------------------------------------------


def test_le_POINT_ROUGE_le_scenario_qui_a_fonde_l_arbitrage(projet_et_source):
    """Trois temps : j'ingere, je retouche la planche, je rescanne."""
    projet, source = projet_et_source
    scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")

    # La retouche : meme planche, meme identite, contenu different.
    cv2.imwrite(str(source / "p1.tiff"), _page(point_rouge=True))

    with pytest.raises(scan_ingest.ScanIngestError) as refus:
        scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")
    # Le refus par defaut TIENT -- la copie fait foi -- mais il offre desormais
    # une issue automatique et NON destructive.
    assert "--nouvelle-version" in str(refus.value)

    scan_ingest.ingest_scan_lot(
        projet, source, dpi=600, ingest_slug="scan-WIN", nouvelle_version=True)

    dossiers = sorted(p.name for p in (projet / project_layout.SCANS_DIRNAME).iterdir() if p.is_dir())
    assert dossiers == ["scan-WIN", "scan-WIN_v2"]
    # Et la version SANS le point rouge est intacte : c'est tout l'objet.
    original = cv2.imread(str(projet / "scans/scan-WIN/p1.tiff"))
    assert original is not None
    assert (original == _page()).all(), "la version d'avant la retouche a ete perdue"


def test_le_refus_par_defaut_offre_TROIS_issues(projet_et_source):
    """`EPIC11-ARB-89`. Les deux issues d'origine etaient des corvees
    MANUELLES -- inventer un slug, ou vider le dossier -- et la seconde
    detruit. Aucune n'etait le versionnage."""
    projet, source = projet_et_source
    scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")
    cv2.imwrite(str(source / "p1.tiff"), _page(point_rouge=True))
    with pytest.raises(scan_ingest.ScanIngestError) as refus:
        scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")
    texte = str(refus.value)
    for issue in ("--nouvelle-version", "--lot-slug", "vider"):
        assert issue in texte, f"le refus n'offre pas l'issue {issue!r}: {texte}"


def test_re_ingerer_le_MEME_scan_reste_idempotent(projet_et_source):
    """Controle negatif : la garde ne mord que sur un contenu DIFFERENT. Un
    operateur qui relance apres une coupure ne doit pas avoir a inventer quoi
    que ce soit."""
    projet, source = projet_et_source
    scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")
    scan_ingest.ingest_scan_lot(projet, source, dpi=600, ingest_slug="scan-WIN")
    dossiers = sorted(p.name for p in (projet / project_layout.SCANS_DIRNAME).iterdir() if p.is_dir())
    assert dossiers == ["scan-WIN"], "une re-ingestion identique a cree une version"


def test_nouvelle_version_sur_un_slug_JAMAIS_ingere_rend_l_ORIGINE(projet_et_source):
    """Sans effet plutot que refuse : refuser serait un blocage sec sur une
    intention realisable, et produire un `_v2` serait une « version 2 de
    rien »."""
    projet, source = projet_et_source
    scan_ingest.ingest_scan_lot(
        projet, source, dpi=600, ingest_slug="scan-NEUF", nouvelle_version=True)
    dossiers = sorted(p.name for p in (projet / project_layout.SCANS_DIRNAME).iterdir() if p.is_dir())
    assert dossiers == ["scan-NEUF"]


# ---------------------------------------------------------------------------
# Le RANG : meme regle que les trois autres objets (`io.version_ranks`).
# ---------------------------------------------------------------------------


def _scans(tmp_path, noms):
    racine = tmp_path / project_layout.SCANS_DIRNAME
    racine.mkdir(exist_ok=True)
    for nom in noms:
        (racine / nom).mkdir()
    return tmp_path


def test_un_rang_de_scan_CONSOMME_ne_se_reutilise_JAMAIS(tmp_path):
    """`EPIC11-ARB-92`, applique aux scans comme aux trois autres : le trou
    reste un trou. 1 et 3 employes -> le prochain est le 4, pas le 2."""
    projet = _scans(tmp_path, ["scan-WIN", "scan-WIN_v3"])
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-WIN") == 4


def test_la_ligne_d_eau_du_scan_SURVIT_au_retrait_des_dossiers(tmp_path):
    """La memoire est de niveau PROJET et distincte des dossiers presents :
    sans elle, effacer les dossiers ferait repartir au rang 1 et reingerer
    sous un nom deja employe."""
    projet = _scans(tmp_path, [])
    manifest = {scan_ingest.SCAN_WATERMARKS_FIELD: {"scan-WIN": 5}}
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-WIN", manifest) == 6


def test_la_ligne_d_eau_est_par_SLUG_et_non_par_projet(tmp_path):
    """Regle des fabriques appliquee a la table que le code parcourt : trois
    slugs distinguables, la cible AU MILIEU. Un resolveur qui lirait la
    premiere entree ferait deriver le rang d'un slug au rythme des autres."""
    projet = _scans(tmp_path, [])
    manifest = {scan_ingest.SCAN_WATERMARKS_FIELD: {
        "scan-AVANT": 9, "scan-WIN": 5, "scan-APRES": 7,
    }}
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-WIN", manifest) == 6
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-INCONNU", manifest) == 1


def test_le_DISQUE_est_consulte_EN_PLUS_du_manifeste(tmp_path):
    """Un dossier present que le manifeste ignore -- ingere avant cet
    arbitrage, ou depose a la main -- a bel et bien consomme son rang."""
    projet = _scans(tmp_path, ["scan-WIN", "scan-WIN_v7"])
    manifest = {scan_ingest.SCAN_WATERMARKS_FIELD: {"scan-WIN": 3}}
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-WIN", manifest) == 8


def test_les_scans_d_un_AUTRE_slug_ne_prennent_aucun_rang(tmp_path):
    """`scans/` est un dossier PARTAGE, comme `planches/` et `outputs/`."""
    projet = _scans(tmp_path, ["scan-AUTRE", "scan-AUTRE_v4", "scan-ENCORE"])
    assert scan_ingest.resolve_scan_version_rank(projet, "scan-WIN") == 1


def test_le_calcul_du_rang_vient_du_module_PARTAGE():
    """Cinquieme objet versionnable, meme module : trois copies de la regle
    seraient trois verites (`EPIC5-ARB-78`), et ce module en porte cinq."""
    import ast

    arbre = ast.parse(Path(scan_ingest.__file__).read_text(encoding="utf-8"))
    importes = {
        alias.name
        for noeud in ast.walk(arbre) if isinstance(noeud, ast.ImportFrom)
        for alias in noeud.names
    }
    assert "version_ranks" in importes, (
        "le resolveur de rang de scan recopie la regle au lieu de l'appeler"
    )


# ---------------------------------------------------------------------------
# Les deux COLLISIONS DE CLE DE FAMILLE, trouvees en revue (couche 2) sur le
# chemin NOMINAL -- pas sur un slug tordu.
# ---------------------------------------------------------------------------


def test_un_slug_de_scan_ne_peut_pas_se_terminer_comme_un_RANG(tmp_path):
    """`scans/scan-WIN_v2` serait deux familles a la fois.

    Il etait simultanement l'origine de la famille `scan-WIN_v2` et le rang 2
    de la famille `scan-WIN`, si bien que le prochain rang de la premiere
    devenait `scan-WIN_v2_v2`.
    """
    from mixed_media_utility import scan_ingest

    with pytest.raises(scan_ingest.UnsupportedScanInputError) as erreur:
        scan_ingest.validate_ingest_slug("scan-WIN_v2")
    message = str(erreur.value)
    assert "RESERVE" in message
    # `EPIC11-ARB-89` : un refus offre toujours au moins deux issues.
    assert "Deux issues" in message
    assert "--nouvelle-version" in message


@pytest.mark.parametrize("slug", ["scan-WIN_v2", "scan-WIN_v99", "a_v2"])
def test_les_formes_RESERVEES_sont_refusees(slug):
    from mixed_media_utility import scan_ingest

    with pytest.raises(scan_ingest.UnsupportedScanInputError):
        scan_ingest.validate_ingest_slug(slug)


@pytest.mark.parametrize("slug", [
    "scan-WIN",       # sans fragment
    "scan-WIN_v1",    # le rang 1 ne s'ecrit JAMAIS (omission stricte)
    "scan-WIN_v02",   # zero de tete: hors convention
    "scan-WIN_v100",  # hors bornes
    "scan_v2x",       # le fragment n'est pas terminal
    "v2",             # pas de `_` : ce n'est la version de rien
])
def test_les_formes_VOISINES_restent_acceptees(slug):
    """Controle negatif : la garde ne mord QUE sur la forme reservee.

    Sans lui, une garde trop large serait indiscernable d'une garde juste --
    et elle interdirait des slugs operateur parfaitement legitimes.
    """
    from mixed_media_utility import scan_ingest

    assert scan_ingest.validate_ingest_slug(slug) == slug


def test_le_dossier_de_frames_d_un_AUTRE_lot_ne_prend_aucun_rang(tmp_path):
    """La collision du chemin nominal, cote frames rescannees.

    Le slug des frames d'un lot est son `lot_id`, et un lot versionne porte
    deja son rang dans son identifiant : `frames-scannees/rush-001_12p5_v2` est
    le dossier du LOT v2, pas le rescan v2 du lot d'origine. Le balayage de
    noms les confondait, si bien qu'un lot d'origine JAMAIS rescanne partait
    au rang 3.
    """
    from mixed_media_utility import scan_output_frames

    base = "rush-001_12p5"
    manifest = {"lots": [
        {"lot_id": base},
        {"lot_id": f"{base}_v2", "version_rank": 2, "base_lot_id": base},
    ]}
    (tmp_path / project_layout.SCAN_FRAMES_DIRNAME / f"{base}_v2").mkdir(parents=True)

    # Le lot d'ORIGINE n'a jamais ete rescanne : son prochain jeu est l'origine.
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, base, base, manifest) == 1
    # Le lot v2, lui, a bien son dossier d'origine : son prochain jeu est le 2.
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, f"{base}_v2", f"{base}_v2", manifest) == 2


def test_un_VRAI_rescan_du_meme_lot_prend_bien_le_rang_suivant(tmp_path):
    """Controle negatif du precedent : la garde ne doit pas tout neutraliser."""
    from mixed_media_utility import scan_output_frames

    base = "rush-001_12p5"
    manifest = {"lots": [{"lot_id": base}]}
    for nom in (base, f"{base}_v2"):
        (tmp_path / project_layout.SCAN_FRAMES_DIRNAME / nom).mkdir(parents=True)
    # Les deux dossiers appartiennent a la MEME famille (aucun autre lot ne les
    # declare) : le prochain rescan est le 3.
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, base, base, manifest) == 3


def test_un_projet_D_AVANT_a_deja_CONSOMME_ses_rangs_et_on_ne_les_ECRASE_pas(
        tmp_path):
    """Finding `E2-1` de la revue : la racine d'AVANT compte, ou on ecrase.

    Le regime exact ou le defaut mordait, et il faut le garder parce qu'il ne
    se voit pas en relecture : `OUTPUT_FRAMES_DIRNAME` est devenu un ALIAS de
    `SCAN_FRAMES_DIRNAME` a la story 11.14. Un lecteur qui composait cette
    seule racine ne voyait donc plus **que** le nom neuf, et les rangs
    consommes sous `output-frames/` d'un projet d'avant devenaient invisibles.

    La consequence n'est pas cosmetique : la fonction rendait un rang **deja
    pris**, et le rescan suivant ecrasait des frames existantes **sans le
    dire** -- un ecrasement NON CONSCIENT, que `EPIC11-ARB-104` et
    `EPIC11-ARB-105` interdisent l'un comme l'autre.

    Deux lots distinguables, et la cible a CHAQUE BORD : un balayage qui
    sauterait la premiere ou la derniere racine rougit ici.
    """
    from mixed_media_utility import scan_output_frames

    base = "rush-001_12p5"
    autre = "rush-002_25"
    manifest = {"lots": [{"lot_id": base}, {"lot_id": autre}]}

    # Le projet est d'AVANT : ses deux jeux vivent sous l'ancienne racine.
    for nom in (base, f"{base}_v2"):
        (tmp_path / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME
         / nom).mkdir(parents=True)
    # Un voisin, pour qu'aucune fabrique ne soit mono-element : il a consomme
    # UN rang de plus, donc les deux lots ne rendent pas la meme reponse.
    for nom in (autre, f"{autre}_v2", f"{autre}_v3"):
        (tmp_path / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME
         / nom).mkdir(parents=True)

    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, base, base, manifest) == 3
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, autre, autre, manifest) == 4


def test_les_DEUX_racines_se_CUMULENT_sur_un_projet_MIXTE(tmp_path):
    """Volet symetrique : un projet peut porter les deux racines a la fois.

    Rien ne l'ecrit -- `EPIC11-ARB-222` dit qu'on n'ecrit que le nom neuf --,
    mais une main peut le fabriquer, et c'est le bord le moins couvert. Le rang
    se compte alors sur l'UNION : lire une seule des deux racines, quelle
    qu'elle soit, rend un rang deja pris.
    """
    from mixed_media_utility import scan_output_frames

    base = "rush-001_12p5"
    manifest = {"lots": [{"lot_id": base}]}
    # **Le rang le PLUS HAUT vit sous l'ancienne racine**, et c'est ce qui rend
    # ce test discriminant : place a l'inverse, il rendrait la meme reponse
    # avec une racine ou avec deux, et ne prouverait donc rien. Mesure : la
    # premiere redaction de ce test mettait `_v2` sous la racine NEUVE et
    # restait verte sous le mutant a racine unique.
    (tmp_path / project_layout.SCAN_FRAMES_DIRNAME
     / base).mkdir(parents=True)
    (tmp_path / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME
     / f"{base}_v3").mkdir(parents=True)

    # Union des deux racines : rangs {1, 3} consommes, le prochain est le 4.
    # Racine neuve seule : rang {1}, le prochain serait le 2 -- deja pris.
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, base, base, manifest) == 4


# ---------------------------------------------------------------------------
# Ce que le rang PRODUIT, et non ce qu'il VAUT.
#
# Les trois bancs ci-dessus mesurent le NOMBRE que rend le resolveur. Les trois
# suivants mesurent ce qui atterrit sur le disque, en appelant deux fois le
# vrai `write_lot_output_frames`. La distinction a ete payee (revue 11.14,
# couche 1) : la dette `E2-1` decrivait la consequence du defaut comme un
# ECRASEMENT, et la mesure bout en bout a montre que ce n'en etait pas un --
# `_assert_writable` ne compare que les NOMS DE FICHIERS vises, si bien que
# deux passes aux timecodes differents ne se refusent pas : elles FUSIONNENT,
# sans un mot, dans un seul dossier. Une dette qui decrit mal son defaut est
# une dette qui sera mal fermee ; un banc qui ne mesure que le rang ne pouvait
# pas la corriger.
# ---------------------------------------------------------------------------


def _pages_de_lot(lot_id, timecodes):
    """Deux frames reelles d'un lot, par les fabriques du banc de la 5.6.

    Les fabriques du depot sont empruntees plutot que recopiees : elles
    passent par `io.payload` et par le vrai plan de decoupe, donc un payload
    invalide ne peut pas se glisser ici.
    """
    import test_scan_output_frames as fabriques

    payload = fabriques.make_payload(
        page_index=0, page_count=1, first_slot=0, slot_count=2,
        lot_id=lot_id, timecodes=list(timecodes))
    return [fabriques.full_page(payload)]


def _contenu_des_racines(projet):
    """`{ "<racine>/<dossier>": [noms de fichiers] }`, les DEUX racines."""
    trouve = {}
    for racine in (project_layout.SCAN_FRAMES_DIRNAME,
                   project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME):
        if not (projet / racine).is_dir():
            continue
        for dossier in sorted((projet / racine).iterdir()):
            trouve[f"{racine}/{dossier.name}"] = sorted(
                chemin.name for chemin in dossier.iterdir())
    return trouve


def test_sur_un_projet_D_AVANT_deux_passes_ne_FUSIONNENT_pas_dans_un_dossier(
        tmp_path):
    """Le regime REEL du finding `E2-1`, mesure de bout en bout.

    Le cas nominal d'un rescan apres recadrage de la planche : les timecodes
    lus a la seconde passe **different** de ceux de la premiere. Aucun nom de
    fichier ne se recouvre, donc la garde de reecriture ne se declenche pas --
    et sous le defaut a racine unique les quatre frames atterrissaient dans le
    MEME dossier, ni la v1 ni la v2 mais les deux. `encode.py` lit ce dossier
    tel quel (`sorted(lot_dir.iterdir())`) : le master se fabriquait alors sur
    deux passes entrelacees, resultat plausible et faux -- la classe R12.

    Ce banc mord la ou celui du rang ne mordait pas : il ne demande pas
    « quel nombre ? » mais « qu'est-ce qui est sur le disque ? ».
    """
    from mixed_media_utility import scan_output_frames

    projet = tmp_path / "projet"
    lot_id = naming.build_lot_id("rush-001", 5.0)
    manifeste = {"lots": [{"lot_id": lot_id}]}

    scan_output_frames.write_lot_output_frames(
        projet, _pages_de_lot(lot_id, ["00:00:00:00", "00:00:01:00"]))
    # Le projet est d'AVANT : ses frames vivent sous l'ancienne racine.
    ancienne = projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME
    ancienne.mkdir(parents=True)
    neuve = projet / project_layout.SCAN_FRAMES_DIRNAME
    for enfant in list(neuve.iterdir()):
        enfant.rename(ancienne / enfant.name)
    neuve.rmdir()

    # SECONDE PASSE : la planche a ete recadree, les timecodes lus different.
    scan_output_frames.write_lot_output_frames(
        projet, _pages_de_lot(lot_id, ["00:00:02:00", "00:00:03:00"]),
        nouvelle_version=True, manifest=manifeste)

    contenu = _contenu_des_racines(projet)
    assert contenu == {
        f"{project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME}/{lot_id}": [
            "scan_rush-001_5_00-00-00-00.tiff",
            "scan_rush-001_5_00-00-01-00.tiff"],
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{lot_id}_v2": [
            "scan_rush-001_5_00-00-02-00.tiff",
            "scan_rush-001_5_00-00-03-00.tiff"],
    }, contenu


def test_le_rescan_du_lot_d_ORIGINE_ne_vise_JAMAIS_le_dossier_du_LOT_v2(
        tmp_path):
    """Le rang se COMPTE dans une famille, mais son NOM se partage.

    Trouve en revue 11.14, couche 1, en cherchant si le regime de `E2-1`
    restait ouvert par un autre chemin -- il l'etait, et par le pire :
    `rush-001_5_v2` est simultanement le rang 2 de la famille `rush-001_5` et
    l'identifiant du LOT v2. L'exclusion des dossiers d'autres lots -- juste,
    et posee pour qu'un lot jamais rescanne ne parte pas au rang 3 -- rendait
    donc le rang 2 pour un nom qui appartenait deja a quelqu'un d'autre.

    Mesure du defaut, exactement cette fixture :

        rang rendu pour le lot d'origine : 2
        frames-scannees/rush-001_5_v2 -> 4 fichiers, LES DEUX LOTS MELANGES

    Sans le manifeste la meme passe rendait 3 et n'ecrasait rien : c'est
    l'exclusion seule qui produisait le defaut. Deux lots distinguables par
    leurs timecodes, comme l'exige la regle des fabriques -- un remplissage
    uniforme rendrait la fusion invisible.
    """
    from mixed_media_utility import scan_output_frames

    projet = tmp_path / "projet"
    origine = naming.build_lot_id("rush-001", 5.0)
    lot_v2 = naming.build_lot_id("rush-001", 5.0, version_rank=2)
    assert lot_v2 == f"{origine}_v2", (origine, lot_v2)
    manifeste = {"lots": [{"lot_id": origine}, {"lot_id": lot_v2}]}

    scan_output_frames.write_lot_output_frames(
        projet, _pages_de_lot(origine, ["00:00:00:00", "00:00:01:00"]))
    scan_output_frames.write_lot_output_frames(
        projet, _pages_de_lot(lot_v2, ["00:00:04:00", "00:00:05:00"]))

    scan_output_frames.write_lot_output_frames(
        projet, _pages_de_lot(origine, ["00:00:02:00", "00:00:03:00"]),
        nouvelle_version=True, manifest=manifeste)

    contenu = _contenu_des_racines(projet)
    assert contenu == {
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{origine}": [
            "scan_rush-001_5_00-00-00-00.tiff",
            "scan_rush-001_5_00-00-01-00.tiff"],
        # Le dossier du LOT v2 garde SES DEUX frames, et rien d'autre.
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{lot_v2}": [
            "scan_rush-001_5_00-00-04-00.tiff",
            "scan_rush-001_5_00-00-05-00.tiff"],
        # Le rescan du lot d'origine a saute le rang 2, dont le nom etait pris.
        f"{project_layout.SCAN_FRAMES_DIRNAME}/{origine}_v3": [
            "scan_rush-001_5_00-00-02-00.tiff",
            "scan_rush-001_5_00-00-03-00.tiff"],
    }, contenu


def test_le_SAUT_de_rang_ne_se_declenche_QUE_sur_un_nom_pris(tmp_path):
    """Volet symetrique : la correction ci-dessus ne doit RIEN changer ailleurs.

    C'est le cas exact qui a fait poser l'exclusion des autres lots (commit
    `4574300e7`, M1) : le LOT v2 a ete scanne une fois, le lot d'ORIGINE ne
    l'a jamais ete. Sa famille est vide, son prochain rescan est donc le rang
    1 -- dont le nom, `rush-001_12p5`, n'appartient a personne d'autre. Sans
    ce volet, une correction qui compterait betement le dossier du lot v2
    comme consomme ferait repartir ce lot au rang 3, et rien ne le dirait.
    """
    from mixed_media_utility import scan_output_frames

    base = "rush-001_12p5"
    lot_v2 = f"{base}_v2"
    manifeste = {"lots": [{"lot_id": base}, {"lot_id": lot_v2}]}
    # Seul le dossier du LOT v2 existe.
    (tmp_path / project_layout.SCAN_FRAMES_DIRNAME / lot_v2).mkdir(parents=True)

    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, base, base, manifeste) == version_ranks.RANG_ORIGINE
    # Et le lot v2, lui, compte bien SON propre dossier : rang 2 consomme.
    assert scan_output_frames.resolve_output_frames_version_rank(
        tmp_path, lot_v2, lot_v2, manifeste) == 2


# ---------------------------------------------------------------------------
# `EPIC11-ARB-105` -- la garde et l'ecriture doivent viser le MEME dossier.
#
# Trouve en revue (couche 3). `check_scan_conflicts` recalculait le dossier de
# sortie SANS le rang, alors que `--nouvelle-version` ecrit dans
# `output-frames/<slug>_vN` : la garde inspectait la passe PRECEDENTE. Une page
# qui echouait a la geometrie faisait lever une regression pour des frames que
# la passe n'allait pas toucher, et le refus ne proposait qu'une sortie --
# `--overwrite`, c'est-a-dire l'issue destructrice que cet arbitrage a ete pris
# pour supprimer.
# ---------------------------------------------------------------------------


def test_la_garde_de_degradation_EXPOSE_le_cas_de_la_cible_neuve():
    """Sans ce parametre, la garde ne peut pas savoir qu'elle vise un dossier neuf."""
    import inspect

    from mixed_media_utility.io import scan_manifest

    parametres = inspect.signature(scan_manifest.check_scan_conflicts).parameters
    assert "cible_neuve" in parametres
    # Le defaut doit etre le comportement HISTORIQUE : une passe ordinaire
    # garde sa protection contre le remplacement de vraies frames par des mires.
    assert parametres["cible_neuve"].default is False


def test_une_nouvelle_version_de_frames_TRANSMET_la_cible_neuve():
    """La chaine complete, mesuree structurellement.

    Le parametre pourrait exister et n'etre jamais passe -- c'est exactement la
    forme du defaut d'`EPIC11-ARB-106` que la meme revue a trouve ailleurs.
    """
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
              / "scan_write.py").read_text(encoding="utf-8")
    appels = [
        noeud for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr == "check_scan_conflicts"
    ]
    assert appels, "aucun appel a `check_scan_conflicts` : la frontiere ne lit rien."
    for appel in appels:
        mots = {mot.arg: mot.value for mot in appel.keywords}
        assert "cible_neuve" in mots, (
            "l'appel a `check_scan_conflicts` ne transmet pas `cible_neuve`: "
            "sous --nouvelle-version, la garde inspecte la passe PRECEDENTE et "
            "peut refuser en ne proposant que --overwrite, l'issue destructrice "
            "qu'EPIC11-ARB-105 supprime."
        )
        # La valeur vient du drapeau, pas d'une constante qui neutraliserait
        # la garde pour TOUTES les passes -- ce qui serait bien pire que le
        # defaut d'origine.
        valeur = mots["cible_neuve"]
        source_valeur = ast.dump(valeur)
        assert "nouvelle_version" in source_valeur, (
            "`cible_neuve=` doit derive de `nouvelle_version`, jamais d'une "
            "constante : la poser vraie en dur desactiverait la garde de "
            "degradation sur toutes les passes."
        )


# ---------------------------------------------------------------------------
# `EPIC11-ARB-109` -- l'ECRITURE de l'historique par lot.
# ---------------------------------------------------------------------------


def _passe(lot_precedent, slug, dossier=None, statut="complete"):
    from mixed_media_utility.io import scan_manifest

    lot = {}
    section = {"origin": "scan", "status": statut}
    if slug is not None:
        section["scan"] = {"ingest_slug": slug}
    scan_manifest._fusionner_l_historique_de_reconstruction(
        lot, lot_precedent, section, dossier)
    return lot


def test_rejouer_la_MEME_passe_ne_fait_pas_grossir_l_historique():
    """L'idempotence octet a octet est une contrainte DURE (story 5.7, AC 10).

    C'est elle qui interdit toute horodate dans une entree : une date rendrait
    deux passes identiques distinguables. La deduplication PAR CONTENU est ce
    qui tient l'idempotence a sa place.
    """
    premiere = _passe(None, "scan-A", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")
    assert premiere == _passe(premiere, "scan-A", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")


def test_un_rescan_depuis_un_AUTRE_slug_ajoute_une_entree():
    """Controle negatif : la deduplication ne doit pas tout confondre."""
    premiere = _passe(None, "scan-A", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")
    seconde = _passe(premiere, "scan-B", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot_v2")
    assert [e["ingest_slug"] for e in seconde["reconstructions"]] == ["scan-A", "scan-B"]


def test_l_ordre_de_l_historique_est_CHRONOLOGIQUE_et_jamais_trie():
    """Le tri detruirait l'information « quelle passe a suivi laquelle »."""
    etat = _passe(None, "scan-Z", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")
    etat = _passe(etat, "scan-A", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot_v2")
    # Revenir a la premiere ne la remonte pas : elle est deja la, a sa place.
    etat = _passe(etat, "scan-Z", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")
    assert [e["ingest_slug"] for e in etat["reconstructions"]] == ["scan-Z", "scan-A"]


def test_une_passe_SANS_slug_ne_detruit_pas_l_historique():
    """Perdre le passe serait le defaut meme que ce registre ferme."""
    etat = _passe(None, "scan-A", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot")
    etat = _passe(etat, "scan-B", f"{project_layout.SCAN_FRAMES_DIRNAME}/lot_v2")
    apres = _passe(etat, None)
    assert apres["reconstructions"] == etat["reconstructions"]


def test_l_historique_est_au_CONTRAT_des_champs_de_lot():
    """`SCAN_LOT_FIELDS` est le contrat, pas un resume du code."""
    from mixed_media_utility.io import scan_manifest

    assert "reconstructions" in scan_manifest.SCAN_LOT_FIELDS


def test_l_historique_est_au_SCHEMA_et_le_schema_le_borne():
    """Une entree sans `ingest_slug` n'a rien a offrir a la filiation."""
    import json
    from pathlib import Path

    import jsonschema

    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility" / "specs"
         / "project.schema.json").read_text(encoding="utf-8"))
    entree = schema["properties"]["lots"]["items"]["properties"]["reconstructions"]
    assert entree["items"]["required"] == ["ingest_slug"]
    # Le schema REFUSE un champ de plus : le registre est ferme, comme le lot.
    assert entree["items"]["additionalProperties"] is False
    validateur = jsonschema.Draft202012Validator(entree)
    assert validateur.is_valid([{"ingest_slug": "scan-A"}])
    assert not validateur.is_valid([{"origin": "scan"}])
    assert not validateur.is_valid([{"ingest_slug": "scan-A", "date": "2026-08-31"}])


# ---------------------------------------------------------------------------
# `EPIC11-ARB-110`, revue de la vague 3 : la borne de CREATION ne doit pas
# condamner ce qui est deja imprime.
# ---------------------------------------------------------------------------


def test_un_lot_id_ecrit_quand_la_borne_valait_64_se_RELIT_encore():
    """La regression qu'a introduite le retour a 48, trouvee en revue.

    La borne a valu 64 du 2026-08-28 au 2026-08-31 : des identifiants de 49 a
    64 caracteres ont pu etre ecrits, puis IMPRIMES dans le QR de planches
    papier. Leur appliquer la borne de creation rendait ces planches
    irrescannables, sans nommer d'issue -- une regression silencieuse sur des
    feuilles qu'aucun calcul ne refait.
    """
    from mixed_media_utility import scan_output_frames
    from mixed_media_utility.io import naming

    rush = "r" * 50
    ancien = naming.derive_short_id(
        f"{rush}_12p5", max_length=naming.LEGACY_ID_MAX_LENGTH)
    assert len(ancien) > naming.CANONICAL_ID_MAX_LENGTH, (
        "la fabrique doit produire un identifiant de l'EPOQUE, plus long que la "
        "borne d'aujourd'hui, sinon ce test ne mesure rien"
    )
    slug = scan_output_frames.derive_lot_dir_slug(
        rush_id=rush, fps_target=12.5, lot_id=ancien)
    assert slug


def test_la_borne_de_CREATION_reste_stricte():
    """Controle negatif : la tolerance de lecture ne doit pas rouvrir la falaise.

    Sans lui, assouplir la lecture pourrait passer pour assouplir tout le
    domaine -- et la falaise QU'`EPIC11-ARB-110` ferme se rouvrirait.
    """
    from mixed_media_utility.io import naming

    trop_long = "x" * (naming.CANONICAL_ID_MAX_LENGTH + 1)
    with pytest.raises(naming.NamingError):
        naming.validate_manifest_identifier(trop_long, label="lot_id")
    # La MEME valeur passe sous la borne tolerante, et c'est tout l'ecart.
    assert naming.validate_manifest_identifier(
        trop_long, label="lot_id",
        longueur_max=naming.LEGACY_ID_MAX_LENGTH) == trop_long
    # La tolerance ne va pas plus loin que ce que l'outil a pu produire.
    with pytest.raises(naming.NamingError):
        naming.validate_manifest_identifier(
            "x" * (naming.LEGACY_ID_MAX_LENGTH + 1), label="lot_id",
            longueur_max=naming.LEGACY_ID_MAX_LENGTH)


def test_composer_une_planche_refuse_TOUJOURS_un_identifiant_trop_long():
    """La tolerance appartient a la LECTURE, jamais a la composition.

    `plan_page_payload` fabrique une planche a imprimer : l'assouplir
    rouvrirait la falaise. Ma premiere correction l'avait fait, et ce test
    l'aurait attrapee.
    """
    from mixed_media_utility import page_payload
    from mixed_media_utility.io import naming, payload as payload_io

    trop_long = "x" * (naming.CANONICAL_ID_MAX_LENGTH + 1)
    with pytest.raises(page_payload.NonCanonicalIdentifierError):
        page_payload.plan_page_payload(
            project_id="p", rush_id="r", lot_id=trop_long, page_index=0,
            page_count=1, fps_target=24.0, timecode_base_fps="25/1",
            template_id="t", patch_preset_id="pp", target_colorspace="bt709",
            gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
            slots=[{"slot_index": 0, "frame_timecode": "00:00:00:00"}],
        )


# ---------------------------------------------------------------------------
# `EPIC11-ARB-222` -- « un projet existant ne se convertit pas »
#
# Le volet SYMETRIQUE du renommage, et sans lui le lot E2 livrerait une suite
# entierement verte sur la forme que la story POSE, sans jouer une seule fois
# celle qu'elle RETIRE. C'est exactement le defaut que le lot D1 a trouve, en
# sens inverse : une suite verte sur la forme retiree, qui ne mesurait plus
# rien de la neuve.
#
# Ce qui est mesure ici n'est donc pas « le nom neuf marche » -- 480 tests le
# disent deja -- mais **l'ancien est toujours LU**, et il l'est par le
# collecteur reel de l'inventaire, pas par le seul resolveur de chemin.
# ---------------------------------------------------------------------------

def _projet_a_deux_racines(tmp_path):
    """Un projet dont les frames scannees vivent des DEUX cotes.

    Regle des fabriques, les quatre points :

    1. **au moins deux elements distinguables** -- quatre lots, et chacun porte
       un nombre de fichiers DIFFERENT (1, 2, 3, 4). Un remplissage uniforme
       laisserait une permutation invisible ;
    2. **une cible ailleurs qu'en premiere position** -- `mmm_5` est au milieu
       de la racine d'avant ;
    3. la variante multi-elements est ecrite ICI, pas renvoyee a la revue ;
    4. **une cible a CHAQUE BORD** -- `aaa_5` en tete et `zzz_5` en queue de
       l'ordre de balayage. Une cible au milieu demasque un `find` fautif ;
       elle ne demasque PAS un balayage tronque, qui est l'autre mode de panne
       et celui qui mord ici, puisque l'inventaire PARCOURT des racines.
    """
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps({
        "schema_version": "2.1", "project_id": "p-222",
        "created": "2026-01-01T00:00:00Z",
        "rushes": [{"rush_id": "rush-001", "source_path": "inputs/r.mov"}],
        "lots": [], "artifacts": {}, "color": {}, "video": {},
        "reconstruction": {},
    }), encoding="utf-8")

    # Trois lots sous le nom d'AVANT -- tete, milieu, queue --, un sous le nom
    # NEUF. Aucun n'est declare au manifeste : ce sont donc des orphelins, et
    # c'est le listing d'orphelins qui est le collecteur balaye.
    anciens = ("aaa_5", "mmm_5", "zzz_5")
    for rang, nom in enumerate(anciens, start=1):
        dossier = projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom
        dossier.mkdir(parents=True)
        for index in range(rang):
            (dossier / f"scan_{index}.tiff").write_bytes(b"x" * (rang + index))
    neuf = projet / project_layout.SCAN_FRAMES_DIRNAME / "nnn_5"
    neuf.mkdir(parents=True)
    for index in range(4):
        (neuf / f"scan_{index}.tiff").write_bytes(b"y" * (10 + index))
    return projet, anciens


def test_les_frames_scannees_du_nom_D_AVANT_sont_TOUJOURS_LUES(tmp_path):
    """`EPIC11-ARB-222`, verbatim : « un projet existant ne se convertit pas ».

    Le contrat a deux moities et une seule est facile : ecrire le nom neuf se
    mesure partout, RECONNAITRE l'ancien ne se mesure qu'ici. Un projet scanne
    avant la story 11.14 porte ses frames sous `output-frames/` -- rien ne les
    a deplacees, et `EPIC11-ARB-171` interdit de le faire.

    La mesure porte sur le COLLECTEUR (`inventorier_le_projet`), pas sur le
    resolveur de chemin : un resolveur juste dont personne ne parcourt la
    seconde racine rendrait ce test vert tout en laissant l'inventaire aveugle
    -- c'est le defaut que le lot D2 a trouve dans `gui/atelier_scan.py`, ou un
    cardinal annoncait « aucune frame ecrite » juste apres une ecriture.
    """
    from mixed_media_utility import project_inventory

    projet, anciens = _projet_a_deux_racines(tmp_path)

    vus = {objet.nom: objet
           for objet in project_inventory.inventorier_le_projet(projet).orphelins
           if objet.nature == project_inventory.NATURE_FRAMES_SCANNEES}

    # LES TROIS BORDS, nommes un par un plutot que comptes : un cardinal de 3
    # serait vrai pour un balayage qui perd la queue et gagne un intrus.
    manquants = [nom for nom in anciens if nom not in vus]
    assert manquants == [], (
        f"un projet portant ses frames scannees sous "
        f"`{project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME}/` cesse d'etre lu : "
        f"{manquants}. EPIC11-ARB-222 l'interdit -- le nom d'avant n'est plus "
        "jamais ECRIT, il reste toujours RECONNU.")

    # Et ils sont lus SOUS LEUR VRAIE RACINE, jamais reecrits au nom neuf.
    for nom in anciens:
        assert vus[nom].chemin.startswith(
            f"{project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME}/"), (
            f"{nom} est rendu sous {vus[nom].chemin!r} : l'inventaire "
            "CONVERTIT un projet existant au lieu de le lire ou il est.")

    # Volet du volet : la racine NEUVE n'est pas masquee par l'ancienne. Sans
    # lui, un balayage qui s'arreterait a la premiere racine trouvee serait
    # vert sur tout ce qui precede.
    assert "nnn_5" in vus, (
        "la racine neuve disparait des qu'un projet porte aussi l'ancienne : "
        "les DEUX se parcourent, jamais la premiere seule.")

    # Les quatre lots sont DISTINGUABLES par leur contenu, pas seulement par
    # leur nom : c'est ce qui ferait rougir une permutation.
    assert sorted(objet.fichiers for objet in vus.values()) == [1, 2, 3, 4], {
        nom: objet.fichiers for nom, objet in vus.items()}


def test_un_lot_scanne_NEUF_prend_le_nom_NEUF_meme_dans_un_projet_D_AVANT(
        tmp_path):
    """L'autre moitie d'`EPIC11-ARB-171`, et elle n'est pas symetrique par
    politesse : « le nom d'avant n'est plus JAMAIS ecrit ».

    Sans ce controle, le test precedent serait satisfait par une resolution qui
    ecrirait TOUT sous le nom d'avant des qu'un projet en porte un -- ce qui
    lirait bien l'ancien, mais ne poserait jamais le neuf.

    La resolution est faite **par lot** et non par racine, et c'est la propriete
    qui compte : un lot deja sur disque garde son dossier, un lot neuf prend le
    dossier neuf, et aucun lot ne se retrouve scinde entre les deux.
    """
    projet, anciens = _projet_a_deux_racines(tmp_path)

    # Un lot DEJA ecrit sous le nom d'avant y reste -- on ne renomme rien.
    for nom in anciens:
        assert project_layout.scan_frames_dir_from_slug(projet, nom) == (
            projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom), nom

    # Un lot que rien n'a encore ecrit prend le nom NEUF, dans le meme projet.
    assert project_layout.scan_frames_dir_from_slug(projet, "qqq_5") == (
        projet / project_layout.SCAN_FRAMES_DIRNAME / "qqq_5"), (
        "un lot NEUF herite du nom d'avant parce qu'un lot ancien vit dans le "
        "meme projet : la resolution se fait par LOT, jamais par racine.")
