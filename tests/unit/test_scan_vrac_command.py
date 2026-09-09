"""Story 5.24 -- le regime de vrac sur la commande `scan` (AC 2, 2bis, 5, 6, 7, 10).

Ce lot est de **bout en bout**: il imprime puis numerise des feuilles reelles,
et mesure sur ce que la commande **produit** -- frames ecrites, manifest, profils
sur le disque, rapport de tri -- jamais sur un seul code de retour. Un scan qui
rendrait `0` en ayant range ailleurs passerait un test de code de retour
(AC 2bis, mot pour mot).

Il n'y a pas deux commandes et il n'y a pas de « scan classique »: il y a **une**
commande `scan` et **deux regimes**, separes par la seule presence de
`--lot-slug` (`EPIC5-ARB-106`).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(pathlib.Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).parent))

import test_scan_calibration_application as app  # noqa: E402
import test_scan_manifest as scan_fixtures  # noqa: E402

from mixed_media_utility import (  # noqa: E402
    cli,
    page_roles,
    scan_detect,
    scan_sorting,
)
from mixed_media_utility.io import naming, reconstruction  # noqa: E402

#: **Le code que rend une passe de vrac de ce banc DEPUIS la story 11.4c**
#: (lot V2, AC 9.3), et il ne vaut plus zero. Les planches de ces fixtures
#: portent moins d'emplacements que leur gabarit
#: (`PAGE_SLOT_COUNT_BELOW_TEMPLATE`): chaque lot ecrit est donc declare
#: `LOT_INCOMPLET` par la persistance -- le journal le disait deja, le manifest
#: aussi -- et l'inventaire atteint desormais le code de sortie.
#:
#: **Ce n'est pas un refus** (`1`), et la distinction est tout l'objet de
#: l'AC 9.1: les frames sont ecrites, le manifest est ecrit, et ce qui a ete
#: ecrit n'est simplement pas ce qui etait promis. Les assertions de valeurs de
#: ce banc -- frames comparees octet a octet, entrees de manifest comparees
#: champ par champ -- sont **inchangees**: c'est le sens de « mesure sur les
#: valeurs produites, jamais sur le code » (AC 2bis).
#:
#: `mmu scan detect`, lui, garde son `0`: il ne produit aucune frame, donc
#: aucun inventaire d'ecriture (voir `_detecter` plus bas, laisse a `0`).
#:
#: La valeur est ecrite en clair et non lue de `scan_write.CODE_SUCCES_PARTIEL`:
#: lire la constante que l'on mesure ferait un test tautologique, le defaut
#: trouve par la campagne de la story 5.9 sur la constante centrale de la
#: calibration.
LOT_INCOMPLET_MAIS_ECRIT = 4

#: **Trois lots distinguables**, et le couple qui les definit n'est pas
#: decoratif: `RUSHES_ET_CADENCES[0]` et `[1]` sont **le meme rush a deux
#: cadences** -- le cas nominal v2.1, et le regime exact ou le mutant `M25`
#: avait mord (les cardinaux du scan ecrits sur le mauvais lot, 257 tests
#: verts). Le troisieme est un autre rush.
#:
#: Un `lot_id` ne s'ecrit **jamais a la main** dans ce depot: il se derive par
#: `naming.build_lot_id`, implementation unique (story 3.4, AC 5). Un
#: identifiant invente ici serait refuse par `scan_output_frames`, et pour une
#: bonne raison -- il ferait ecrire des frames dans le dossier d'un autre lot.
#: Les trois lots sont **du meme rush a trois cadences**, et pas de trois rushes
#: differents: un projet n'accepte un scan que d'un rush que son manifest declare
#: deja (`io.reconstruction._check_manifest_conflicts`, garde anterieure a cette
#: story), et c'est de toute facon le regime que l'AC 2 nomme -- « deux lots du
#: meme rush a deux cadences (le cas nominal v2.1) sont deux lots distincts et
#: non un lot fusionne ».
RUSHES_ET_CADENCES = (
    (scan_fixtures.RUSH, 5.0),
    (scan_fixtures.RUSH, 8.0),
    (scan_fixtures.RUSH, 12.5),
)
LOTS = tuple(naming.build_lot_id(rush, fps) for rush, fps in RUSHES_ET_CADENCES)


def _planche(indice_de_lot: int, page_index: int, *, page_count: int = 2,
             project_id: str = scan_fixtures.PROJECT) -> dict:
    rush, fps = RUSHES_ET_CADENCES[indice_de_lot]
    return scan_fixtures.make_payload(
        page_index=page_index,
        page_count=page_count,
        first_slot=2 * page_index,
        slot_count=2,
        template_id=app.TEMPLATE,
        patch_preset_id=app.PRESET,
        rush_id=rush,
        fps_target=fps,
        project_id=project_id,
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )


def _feuilles_de_lot(indice_de_lot: int, **surcharges) -> list[tuple[dict, object]]:
    """Deux planches du meme lot, imprimees sous **deux presses differentes**."""
    return [
        (_planche(indice_de_lot, 0, **surcharges), app.PRESSES_DU_TIRAGE[0]),
        (_planche(indice_de_lot, 1, **surcharges), app.PRESSES_DU_TIRAGE[1]),
    ]


def _lot_du_manifest(project_dir: pathlib.Path, lot_id: str) -> dict:
    manifest = json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8"))
    return next(lot for lot in manifest["lots"] if lot["lot_id"] == lot_id)


def _rapport_de_tri(project_dir: pathlib.Path, dossier: pathlib.Path) -> dict:
    chemins = list((project_dir / "scans").glob(f"*/{cli.TRI_DOCUMENT_FILENAME}"))
    assert len(chemins) == 1, chemins
    return json.loads(chemins[0].read_text(encoding="utf-8"))


def _frames(project_dir: pathlib.Path) -> dict[str, bytes]:
    racine = project_dir / "output-frames"
    return {
        chemin.relative_to(racine).as_posix(): chemin.read_bytes()
        for chemin in sorted(racine.rglob("*")) if chemin.is_file()
    }


# ---------------------------------------------------------------------------
# AC 2bis -- rien de ce qui marche aujourd'hui ne change
# ---------------------------------------------------------------------------


def test_une_pile_mono_lot_rend_le_meme_resultat_avec_et_sans_lot_slug(tmp_path):
    """AC 2bis, le coeur: mesure sur les **valeurs produites**, jamais sur le code.

    La meme pile, le meme dossier de scan, deux projets. A gauche l'operateur
    **promet** un lot unique (`--lot-slug`), a droite il ne promet rien et le
    tri decide. Frames ecrites, entree de manifest et cardinaux doivent etre
    identiques: c'est ce que « le tri ne change rien a ce qui marche » veut dire.
    """
    feuilles = _feuilles_de_lot(1)
    promis = app.write_scan_folder(tmp_path / "a" / "pile", feuilles)
    trie = app.write_scan_folder(tmp_path / "b" / "pile", feuilles)
    projet_promis = tmp_path / "projet-promis"
    projet_trie = tmp_path / "projet-trie"

    assert app.run_scan(projet_promis, promis, "--lot-slug", "pile") == LOT_INCOMPLET_MAIS_ECRIT
    assert app.run_scan(projet_trie, trie) == LOT_INCOMPLET_MAIS_ECRIT

    assert _frames(projet_trie) == _frames(projet_promis)
    gauche = _lot_du_manifest(projet_promis, LOTS[1])
    droite = _lot_du_manifest(projet_trie, LOTS[1])
    assert droite == gauche
    assert droite["lot_id"] == LOTS[1]


def test_avec_lot_slug_le_tri_n_est_pas_appele_du_tout(tmp_path, monkeypatch):
    """AC 2bis : le regime `--lot-slug` **n'emprunte pas** le chemin de tri.

    Un cablage qui trierait toujours -- y compris quand l'operateur a promis un
    lot unique -- passerait un test qui ne verifie que le sens « sans ».
    """
    appels: list[int] = []
    vrai_tri = scan_sorting.trier_les_pages

    def _espion(*args, **kwargs):
        appels.append(1)
        return vrai_tri(*args, **kwargs)

    monkeypatch.setattr(scan_sorting, "trier_les_pages", _espion)
    dossier = app.write_scan_folder(tmp_path / "pile", _feuilles_de_lot(0))
    assert app.run_scan(tmp_path / "projet", dossier, "--lot-slug", "pile") == LOT_INCOMPLET_MAIS_ECRIT
    assert appels == []


def test_une_pile_multi_lots_est_refusee_avec_lot_slug_et_triee_sans_lui(tmp_path):
    """AC 2 et 2bis, **dans les deux sens sur la meme fixture**.

    Un test qui ne verifierait que le sens « sans » laisserait passer un cablage
    qui trie toujours ; un test qui ne verifierait que le sens « avec »
    laisserait passer un tri qui n'a jamais lieu.
    """
    feuilles = _feuilles_de_lot(2) + _feuilles_de_lot(0)
    promis = app.write_scan_folder(tmp_path / "a" / "vrac", feuilles)
    trie = app.write_scan_folder(tmp_path / "b" / "vrac", feuilles)

    assert app.run_scan(tmp_path / "projet-promis", promis, "--lot-slug", "vrac") == 1
    projet = tmp_path / "projet-trie"
    assert app.run_scan(projet, trie) == LOT_INCOMPLET_MAIS_ECRIT

    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert sorted(lot["lot_id"] for lot in manifest["lots"]) == sorted(
        [LOTS[0], LOTS[2]])


def test_aucun_drapeau_neuf_n_est_ajoute_a_scan_pour_le_vrac(capsys):
    """Frontiere negative de l'AC 2bis, sur l'**aide entiere** de `scan`.

    Motif: le drapeau `--vrac` etait la recommandation ecartee, et un drapeau
    garde « au cas ou » recreerait deux gestes pour un seul comportement.
    """
    with pytest.raises(SystemExit):
        cli.main(["scan", "--help"])
    aide = capsys.readouterr().out
    for interdit in ("--vrac", "trier", "--tri"):
        assert interdit not in aide, interdit


# ---------------------------------------------------------------------------
# AC 5 -- la pile mixte est tranchee (report de `EPIC5-ARB-86`)
# ---------------------------------------------------------------------------


def _pile_mixte(dossier: pathlib.Path) -> pathlib.Path:
    """Une planche, **puis** la page de calibration, **puis** une planche.

    La cible n'est ni premiere ni derniere: une garde qui ne regarderait que
    `payloads[0]` resterait verte sur une fabrique mono-element placee en tete.
    """
    payloads = app.lot_payloads(sheet_count=2, with_calibration=True)
    return app.write_scan_folder(dossier, [
        (payloads[1], app.PRESSES_DU_TIRAGE[0]),
        (payloads[0], app.PRESSE_CALIBRATION),
        (payloads[2], app.PRESSES_DU_TIRAGE[1]),
    ])


def test_la_pile_mixte_reste_refusee_avec_lot_slug(tmp_path, capsys):
    """AC 5 : `REFUS_PILE_MIXTE` **garde** le regime `--lot-slug`."""
    dossier = _pile_mixte(tmp_path / "mixte")
    assert app.run_scan(tmp_path / "projet", dossier, "--lot-slug", "mixte") == 1
    erreur = capsys.readouterr().err
    assert "calibration" in erreur.lower(), erreur


def test_la_meme_pile_mixte_est_triee_sans_lot_slug(tmp_path):
    """AC 5 : sans `--lot-slug`, la meme pile produit **un lot et un profil**.

    Et `check_scan_conflicts` n'est atteint que sur une pile **deja homogene par
    lot**: la page de calibration a ete retiree du lot par le tri, avant toute
    lecture d'identite. Le refus ne disparait pas, il **cesse d'etre atteint**.
    """
    dossier = _pile_mixte(tmp_path / "mixte")
    projet = tmp_path / "projet"
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT

    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert len(manifest["lots"]) == 1
    lot = manifest["lots"][0]
    assert lot["lot_id"] == scan_fixtures.LOT

    rapport = _rapport_de_tri(projet, dossier)
    assert len(rapport["calibration"]) == 1
    assert len(rapport["lots"]) == 1
    # La page de calibration n'est comptee dans **aucun** lot.
    assert len(rapport["lots"][0]["pages"]) == 2
    assert len(rapport["profils_crees"]) == 1
    profil = projet / rapport["profils_crees"][0]["chemin_relatif"]
    assert profil.exists(), rapport["profils_crees"]


def test_les_deux_codes_de_refus_de_pile_existent_toujours():
    """Frontiere negative la plus importante de la story (AC 5 et 13).

    `REFUS_PILE_MIXTE` et `REFUS_PILE_SANS_PLANCHE` ne sont ni supprimes, ni
    elargis, ni affaiblis, et ils gardent le regime `--lot-slug`.
    """
    assert reconstruction.REFUS_PILE_MIXTE == "pile-mixte-calibration-et-planches"
    assert reconstruction.REFUS_PILE_SANS_PLANCHE == "pile-sans-planche-d-images"
    source = inspect.getsource(reconstruction)
    assert source.count("REFUS_PILE_MIXTE") >= 2
    assert source.count("REFUS_PILE_SANS_PLANCHE") >= 2
    # Le module de tri ne les connait pas: il ne les elargit donc pas.
    assert "REFUS_PILE" not in inspect.getsource(scan_sorting)


# ---------------------------------------------------------------------------
# AC 7 -- la page de calibration du vrac se consigne, elle ne s'applique pas
# ---------------------------------------------------------------------------


def test_deux_pages_de_calibration_dans_un_vrac_produisent_deux_profils_distincts(
        tmp_path):
    """AC 7 : **deux** profils, et non un profil ecrase par l'autre.

    C'est le sujet repris de
    `test_a_lot_carrying_two_calibration_pages_is_refused_at_reread` (classe B de
    l'AC 8), et c'est la fabrique multi-elements exigee par l'AC 3: les deux
    pages portent **deux libelles de chaine differents**, sans quoi « deux
    profils » n'est pas mesurable -- elles produiraient le meme nom de fichier.
    """
    libelles = ("hp envy 4520 tiff 300 dpi", "epson v600 tiff 300 dpi")
    calibrations = [
        (scan_fixtures.make_payload(
            page_index=0, page_count=3, template_id=app.TEMPLATE,
            patch_preset_id=app.PRESET,
            page_role=page_roles.PAGE_ROLE_CALIBRATION,
            scan_chain_label=libelle), presse)
        for libelle, presse in zip(libelles, app.PRESSES_DU_TIRAGE)
    ]
    feuilles = _feuilles_de_lot(1)
    dossier = app.write_scan_folder(tmp_path / "vrac", [
        feuilles[0], calibrations[0], feuilles[1], calibrations[1]])
    projet = tmp_path / "projet"
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT

    rapport = _rapport_de_tri(projet, dossier)
    assert len(rapport["calibration"]) == 2
    assert [entree["scan_chain_label"] for entree in rapport["calibration"]] == list(
        libelles)
    chemins = [profil["chemin_relatif"] for profil in rapport["profils_crees"]]
    assert len(chemins) == 2 and len(set(chemins)) == 2, chemins
    for chemin in chemins:
        assert (projet / chemin).exists(), chemin


def test_deux_pages_de_calibration_au_MEME_libelle_ne_s_ecrasent_pas(tmp_path):
    """Le rapport ne peut pas nommer deux profils la ou un seul fichier existe.

    Trouve par la couche 2 de la revue de vague. Le test voisin ci-dessus
    prouve « deux profils » avec deux libelles **differents** -- par
    construction, donc il ne pouvait pas voir le cas ou ils sont **egaux**.
    Or le nom du fichier vient du libelle : deux feuilles au meme libelle
    visent le meme fichier, la seconde ecrasait la premiere **en silence**, et
    le rapport declarait deux profils pointant tous deux vers l'unique fichier
    survivant. L'AC 10 l'interdit nommement -- « ce nom est celui du fichier
    reellement ecrit sur le disque ».

    Ce n'est pas un cas tordu : une meme feuille scannee deux fois dans la
    pile, ou une chaine dont l'etiquette a ete reimprimee, suffit.

    Comportement retenu, celui que l'AC 7 prescrit deja pour toute feuille
    qu'on ne peut pas consigner : la **premiere** est consignee, la **seconde**
    va au reliquat avec son motif, et le verdict des lots n'en depend pas.
    """
    libelle = "hp envy 4520 tiff 300 dpi"
    calibrations = [
        (scan_fixtures.make_payload(
            page_index=0, page_count=3, template_id=app.TEMPLATE,
            patch_preset_id=app.PRESET,
            page_role=page_roles.PAGE_ROLE_CALIBRATION,
            scan_chain_label=libelle), presse)
        for presse in app.PRESSES_DU_TIRAGE
    ]
    feuilles = _feuilles_de_lot(1)
    dossier = app.write_scan_folder(tmp_path / "vrac", [
        feuilles[0], calibrations[0], feuilles[1], calibrations[1]])
    projet = tmp_path / "projet"
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT

    rapport = _rapport_de_tri(projet, dossier)

    # UN seul profil declare, et il existe.
    chemins = [profil["chemin_relatif"] for profil in rapport["profils_crees"]]
    assert len(chemins) == 1, chemins
    assert (projet / chemins[0]).exists(), chemins[0]

    # Le rapport ne ment pas : autant de profils declares que de fichiers ecrits.
    ecrits = sorted(
        chemin.relative_to(projet).as_posix()
        for chemin in (projet / "versions" / "calibration").glob("*.json"))
    assert ecrits == chemins, (ecrits, chemins)

    # La seconde feuille est au reliquat, avec son motif nomme, et elle est
    # bien la SECONDE -- pas « une des deux », ce qui passerait aussi si la
    # premiere avait ete rejetee.
    doublons = [
        entree for entree in rapport["reliquat"]
        if entree["motif"] == scan_sorting.RELIQUAT_CALIBRATION_LIBELLE_EN_DOUBLE
    ]
    assert len(doublons) == 1, rapport["reliquat"]
    assert doublons[0]["read_rank"] == 3, doublons[0]

    # Et le lot de la passe n'en depend pas (AC 7 : l'echec reste local).
    assert len(rapport["lots"]) == 1
    assert rapport["lots"][0]["pages"], rapport["lots"][0]


def test_le_profil_cree_par_le_vrac_n_est_pose_en_defaut_d_aucun_projet(tmp_path):
    """AC 7 : **creer n'est pas designer** (`EPIC5-ARB-83`, `EPIC5-ARB-107`).

    Apres le tri, le defaut de profil du projet est inchange -- il n'y en avait
    pas, il n'y en a toujours pas. Mesure sur le **document du projet**, jamais
    sur un log.
    """
    dossier = _pile_mixte(tmp_path / "mixte")
    projet = tmp_path / "projet"
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    couleur = manifest.get("color") or {}
    assert not couleur.get("default_calibration_profile"), couleur
    # Et le lot n'a pas ete corrige par la feuille trouvee: aucun profil n'etait
    # designe, donc le lot sort brut et le declare. Mesure sur le **statut de
    # calibration de chaque frame**, la ou il est reellement ecrit.
    lot = manifest["lots"][0]
    statuts = {
        emplacement.get("color_calibration_status")
        for emplacement in lot.get("slots", [])
    }
    assert "applied" not in statuts, statuts


def test_aucun_chemin_du_vrac_n_ecrit_un_defaut_de_profil_au_projet():
    """Frontiere negative de l'AC 7, mesuree sur le **source** du chemin de vrac.

    Un profil cree par le vrac qui deviendrait le defaut du projet serait
    litteralement « un profil choisi a votre place » (`EPIC5-ARB-83`).
    """
    for fonction in (cli._scanner_le_vrac,
                     cli._consigner_les_pages_de_calibration_du_vrac,
                     cli._ecrire_le_rapport_de_tri):
        source = inspect.getsource(fonction)
        assert "set_default" not in source, fonction.__name__
        assert "default_calibration_profile" not in source, fonction.__name__
        assert "write_default_profile" not in source, fonction.__name__


# ---------------------------------------------------------------------------
# AC 10 -- le rapport de tri est un document, a cote du rapport d'ingestion
# ---------------------------------------------------------------------------


def test_le_rapport_de_tri_est_ecrit_a_cote_du_rapport_d_ingestion(tmp_path):
    """AC 10 : `ingest.json` de 5.1 n'est ni modifie ni remplace."""
    feuilles = _feuilles_de_lot(0) + _feuilles_de_lot(2)
    dossier = app.write_scan_folder(tmp_path / "vrac", feuilles)
    projet = tmp_path / "projet"
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT

    dossiers = list((projet / "scans").glob("*/"))
    assert len(dossiers) == 1
    scans = dossiers[0]
    assert (scans / "ingest.json").exists()
    assert (scans / cli.TRI_DOCUMENT_FILENAME).exists()
    ingest = json.loads((scans / "ingest.json").read_text(encoding="utf-8"))
    assert ingest["page_count"] == 4
    assert "lots" not in ingest and "reliquat" not in ingest

    rapport = json.loads(
        (scans / cli.TRI_DOCUMENT_FILENAME).read_text(encoding="utf-8"))
    assert rapport["version"] == scan_sorting.RAPPORT_DE_TRI_VERSION
    # Les **quatre** classes sont presentes, pas seulement les lots.
    for classe in ("lots", "calibration", "reliquat", "hors_perimetre"):
        assert classe in rapport, classe
    assert [lot["lot_id"] for lot in rapport["lots"]] == sorted([LOTS[0], LOTS[2]])
    assert all(len(lot["pages"]) == 2 for lot in rapport["lots"])
    # Il se relit par son propre lecteur, sans perte.
    relu = scan_sorting.rapport_from_json_dict(rapport)
    assert len(relu.partition.lots) == 2


def test_une_page_d_un_projet_etranger_est_refusee_page_par_page(tmp_path):
    """AC 4, de bout en bout : un vrac dont une page est etrangere range les autres.

    Le refus est **par page et jamais par passe**, et il nomme **le projet a
    utiliser**, lu dans le QR de la page.
    """
    etrangere = _planche(2, 0, page_count=1, project_id="projet_du_voisin")
    dossier = app.write_scan_folder(tmp_path / "vrac", [
        (etrangere, app.PRESSES_DU_TIRAGE[1]),
        *_feuilles_de_lot(1),
    ])
    projet = tmp_path / "projet"
    # Le projet existe deja et porte son identite: c'est elle que le controle
    # de perimetre compare, jamais le nom du dossier.
    assert app.run_scan(projet, app.write_scan_folder(
        tmp_path / "amorce", _feuilles_de_lot(0))) == LOT_INCOMPLET_MAIS_ECRIT
    assert app.run_scan(projet, dossier) == LOT_INCOMPLET_MAIS_ECRIT

    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert sorted(lot["lot_id"] for lot in manifest["lots"]) == sorted(
        [LOTS[0], LOTS[1]])
    rapport = json.loads(
        (projet / "scans" / "vrac" / cli.TRI_DOCUMENT_FILENAME).read_text(
            encoding="utf-8"))
    assert len(rapport["hors_perimetre"]) == 1
    assert rapport["hors_perimetre"][0]["projet_a_utiliser"] == "projet_du_voisin"
    assert rapport["hors_perimetre"][0]["motif"] == (
        scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER)


@dataclasses.dataclass(frozen=True)
class _PageDeclarante:
    """Le strict minimum que `cardinal_de_planches_attendu` lit d'une page.

    Deux champs, et c'est deliberement tout : la fonction accepte aussi bien
    une page de detection (5.2) qu'une page de document (`scan_previz`), et ce
    banc mesure le CONTRAT, pas l'une des deux implementations. Les payloads,
    eux, sont les vrais -- fabriques par le banc du coeur.
    """

    page_count: int | None
    payload: dict | None


def test_le_cardinal_attendu_d_un_lot_EXCLUT_la_page_de_calibration():
    """La regle du cardinal attendu, mesuree la ou elle est ecrite (F1/ARB-73).

    Une page de calibration n'appartient a aucun lot et son `page_count`
    compte la feuille de mires elle-meme : la laisser entrer dans le `max()`
    gonflerait le cardinal du lot d'une planche fantome, donc ferait declarer
    incomplet un lot complet. L'exclusion existait, mais **aucun test ne la
    mesurait** : le seul balayage qui tombait dessus comptait les occurrences
    du role dans les sources (test ci-dessous), ce qui la protege d'une
    suppression accidentelle et pas d'une inversion.

    La page de calibration est en position **mediane** : ni premiere ni
    derniere, et son cardinal declare (9) differe de celui des planches (2),
    sans quoi « elle est ecartee » ne serait pas mesurable.
    """
    planches = [_planche(1, 0), _planche(1, 1)]
    calibration = scan_fixtures.make_payload(
        page_index=0, page_count=9, template_id=app.TEMPLATE,
        patch_preset_id=app.PRESET,
        page_role=page_roles.PAGE_ROLE_CALIBRATION)
    pile = [
        _PageDeclarante(2, planches[0]),
        _PageDeclarante(9, calibration),
        _PageDeclarante(2, planches[1]),
    ]
    assert scan_detect.cardinal_de_planches_attendu(pile) == 2

    # Volet symetrique 1 : c'est bien le ROLE qui l'ecarte, pas la valeur --
    # une PLANCHE qui declarerait 9 emporterait le `max()`.
    planche_bavarde = list(pile)
    planche_bavarde[1] = _PageDeclarante(9, planches[0])
    assert scan_detect.cardinal_de_planches_attendu(planche_bavarde) == 9

    # Volet symetrique 2 : une page muette ne declare rien, et un lot ou
    # personne ne declare n'a pas de cardinal -- on n'en invente pas un.
    assert scan_detect.cardinal_de_planches_attendu(
        [_PageDeclarante(None, None)]) is None


def test_le_predicat_de_page_de_calibration_n_est_redige_qu_une_fois():
    """AC 1, 3e puce : la lecture du role ne se recopie pas dans `cli.py`.

    Trouve par la couche 3 de la revue de vague : la story avait fait passer
    `PAGE_ROLE_CALIBRATION` de quatre a **cinq** occurrences dans `cli.py`, le
    site neuf etant `_identite_du_projet_courant`, qui redigeait le predicat une
    seconde fois **en negatif**. Si celui du module de tri change -- par exemple
    pour traiter un payload sans role --, les deux divergent en silence. Aucun
    test ne balayait cette frontiere, ni avant ni apres.

    Le correctif ne supprime pas les quatre occurrences historiques : elles
    appartiennent a des chemins anterieurs a cette story, et les retirer
    elargirait le perimetre. Il empeche la **cinquieme**, celle que 5.24 a
    ajoutee, et pose le compteur comme garde.
    """
    # **Story 7.3 (AC 2a) : le balayage porte sur les DEUX fichiers.** Deux des
    # quatre occurrences historiques ont suivi l'orchestration de `scan detect`
    # dans le module de coeur `scan_detect`. Ne compter que `cli.py` ferait
    # tomber le compteur de 4 a 2 sans qu'une seule redaction n'ait disparu :
    # c'est l'erosion de garde deja payee en 5.24, pas un progres. Le total sur
    # les deux fichiers est donc l'invariant, et il vaut toujours 4.
    #
    # **Story 11.4b (lot S1) : un TROISIEME fichier.** Les deux occurrences
    # restees dans `cli.py` vivent dans la moitie aval du scan, deplacee dans
    # le module de coeur `scan_write` -- meme geste, meme motif. Le total sur
    # les trois fichiers est l'invariant, et il vaut toujours 4.
    from mixed_media_utility import scan_write

    source = (inspect.getsource(cli) + inspect.getsource(scan_detect)
              + inspect.getsource(scan_write))
    occurrences = source.count("PAGE_ROLE_CALIBRATION")
    assert occurrences == 4, (
        f"{occurrences} lectures du role de page dans cli.py + scan_detect.py. "
        "Le predicat vit dans scan_sorting.est_une_page_de_calibration : on "
        "l'APPELLE, on ne le recopie pas (AC 1). Les quatre restantes sont "
        "anterieures a 5.24.")

    # Volet positif : les fonctions de vrac passent bien par le predicat publie,
    # sans quoi le compteur ci-dessus serait tenu par un code qui ne lirait plus
    # le role du tout.
    assert "scan_sorting.est_une_page_de_calibration(" in inspect.getsource(
        cli._identite_du_projet_courant)


def test_une_pile_sans_planche_lisible_ecrit_quand_meme_son_rapport(tmp_path):
    """`EPIC5-ARB-112` : le refus ne bouge pas, mais on sait QUI a resiste.

    Trouve par la couche 3 de la revue de vague. La clause de l'AC 6 « les N
    planches muettes vont au reliquat » n'etait ni implementee ni testee : une
    pile « feuilles muettes + une page de calibration » sortait **avant** le
    tri, donc aucun `tri.json`. L'operateur savait que la passe avait echoue,
    mais pas **lesquelles** de ses feuilles avaient resiste -- au moment precis
    ou il en a le plus besoin, puisque tout a rate.

    Egan tranche le 2026-08-25 : le rapport s'ecrit quand meme. Le geste est
    **additif**, et le test le mesure comme tel -- meme code de sortie, refus
    inchange, rien de plus qu'un fichier en plus. C'est ce qui preserve l'AC
    2bis, qui exige que ce chemin ne bouge pas.
    """
    # Un projet qui a deja son manifest : sans identite de projet le tri ne
    # peut pas dire ce qui est hors perimetre, et le rapport n'est pas ecrit
    # (branche mesuree par le test suivant).
    projet, dossier_initial, _ = app.nominal_lot(tmp_path, name="socle")
    assert app.run_scan(projet, dossier_initial) == LOT_INCOMPLET_MAIS_ECRIT

    # La pile du refus : DEUX feuilles muettes -- jamais une seule, une garde
    # ecrite « == 1 » passerait -- et une page de calibration lue.
    dossier = tmp_path / "muettes"
    dossier.mkdir(parents=True, exist_ok=True)
    calibration = app.page_de_calibration_autonome(
        scan_chain_label=app.LIBELLES_DE_CHAINE[0])
    app.cv2.imwrite(str(dossier / "page_01.tiff"),
                    app.build_page(calibration, press=app.PRESSE_CALIBRATION))
    blanche = app.np.full_like(
        app.build_page(calibration, press=app.PRESSE_CALIBRATION), 255)
    for rang in (2, 3):
        app.cv2.imwrite(str(dossier / f"page_{rang:02d}.tiff"), blanche)

    code = app.run_scan(projet, dossier, "--garder-le-scan-brut")

    rapport_path = (projet / "scans" / dossier.name / cli.TRI_DOCUMENT_FILENAME)
    assert rapport_path.exists(), "le rapport de tri n'a pas ete ecrit"
    rapport = json.loads(rapport_path.read_text(encoding="utf-8"))

    # Les DEUX feuilles muettes sont nommees -- pas un cardinal, un
    # INVENTAIRE : c'est le « lesquelles » qui manquait. Le motif exact depend
    # de ce que la detection a pu dire (`qr-muet` quand aucun symbole n'est
    # trouve, `payload-refuse` quand le refus porte un motif nomme) ; les deux
    # appartiennent a la famille « la page n'a pas livre son payload », et
    # c'est cette famille que l'AC 6 promettait de rendre visible.
    sans_payload = {
        scan_sorting.RELIQUAT_QR_MUET, scan_sorting.RELIQUAT_PAYLOAD_REFUSE}
    muettes = [
        entree for entree in rapport["reliquat"]
        if entree["motif"] in sans_payload
    ]
    assert len(muettes) == 2, rapport["reliquat"]
    assert sorted(e["locator"]["source_path"].rsplit("/", 1)[-1] for e in muettes) == [
        "page_02.tiff", "page_03.tiff"]
    # Chacune porte un motif, jamais une entree muette d'elle-meme.
    assert all(entree["detail"] for entree in muettes), muettes

    # Volet symetrique, et il est le coeur de l'arbitrage : le refus n'a PAS
    # bouge. Sans lui, ce test passerait aussi sur un code qui aurait fait
    # basculer la pile dans le regime de vrac -- exactement ce que l'AC 2bis
    # interdit.
    assert code != 0, "le refus de pile sans planche d'images a disparu"
    assert not rapport["lots"], rapport["lots"]


# ---------------------------------------------------------------------------
# AC 13 -- l'ordre des pages du document est celui du SCANNER (finding F5)
# ---------------------------------------------------------------------------


def _detecter(project_dir: pathlib.Path, folder: pathlib.Path, *args: str) -> int:
    """`scan ... detect`: la detection seule, sans reconstruction ni ecriture."""
    return cli.main([
        "scan", "--project", str(project_dir), "--scan", str(folder),
        "--dpi", str(app.DPI), *args, "detect",
    ])


def _document_du_lot(project_dir: pathlib.Path, lot_id: str) -> dict:
    """Le document de detection **de ce lot-la**, cherche par son identifiant.

    Jamais `documents[0]`: c'est le `_find_lot` de 5.7 (`M25`), et le vrac en
    ecrit precisement plusieurs.
    """
    chemins = sorted((project_dir / "scans").glob(
        f"*/{scan_detect.DETECTIONS_DIRNAME}/*.json"))
    documents = [
        json.loads(chemin.read_text(encoding="utf-8")) for chemin in chemins]
    vises = [
        document for document in documents
        if document["subject"]["lot_id"] == lot_id
    ]
    assert len(vises) == 1, [
        document["subject"]["lot_id"] for document in documents]
    return vises[0]


def test_le_document_d_un_lot_du_vrac_RANGE_ses_pages_par_NUMERO_DE_PLANCHE(tmp_path):
    """`pages_du_lot` trie par `page_index`, l'ordre que le QR declare.

    `EPIC7-ARB-77`, tranche par Egan le 2026-08-26 : « on range les pages selon
    l'ordre indique dans le QR ». La regle vaut pour **toutes** les surfaces, et
    elle vit donc au coeur -- meme geste que `EPIC7-ARB-73` sur la completude.

    Ce que la revue de vague 3 avait mesure et qui a motive la regle : le
    chutier ne trie rien et affiche l'ordre du document, la galerie triait par
    numero de planche. Sur un lot de trois planches scanne a l'envers, le
    chutier montrait `[2, 1, 0]` et la galerie `[0, 1, 2]` -- deux surfaces, un
    lot, deux ordres.

    La pile de ce test separe les deux ordres possibles : le lot vise est le
    **SECOND** de la pile (jamais en tete), et ses deux planches sont posees **a
    l'envers** sous le scanner -- planche 1 d'abord, planche 0 ensuite. L'ordre
    par rang de lecture serait `[(2, 1), (3, 0)]` ; l'ordre par numero de
    planche est `[(3, 0), (2, 1)]`. C'est ce dernier qui est exige.

    **Ce que ce test tue, et ce qu'il ne peut pas tuer.** Il tue le mutant qui
    remet `key=lambda page: page.read_rank` -- c'est-a-dire l'annulation de
    l'arbitrage. Il **ne peut pas** tuer le retrait pur et simple du `sorted()`
    (`tuple(pages)`), et c'est un **mutant equivalent**, mesure comme tel : le
    tri du vrac ordonne `LotTrie.pages` par `_cle_de_page`, dont la premiere
    composante est deja le `page_index`. Depuis que le coeur trie par la meme
    grandeur, son `sorted()` ne permute plus rien sur ce chemin -- il **garantit**
    un ordre au lieu de le produire. Les pages ajoutees ensuite (la feuille
    muette d'un lot unique) n'ont pas de `page_index` et vont en queue dans les
    deux cas.

    C'est une consequence directe de l'arbitrage, et elle est ecrite ici plutot
    que laissee a decouvrir : sous `EPIC7-ARB-76`, quand le coeur triait par
    rang de lecture, ce mutant-la etait tuable et l'a ete (finding F5).
    """
    # Le projet doit deja porter son identite : sans manifest, le tri par QR
    # ne peut pas dire ce qui est hors perimetre et `detect` refuse.
    projet = tmp_path / "projet"
    assert app.run_scan(
        projet, app.write_scan_folder(tmp_path / "amorce", _feuilles_de_lot(0))) == LOT_INCOMPLET_MAIS_ECRIT

    a_l_envers = list(reversed(_feuilles_de_lot(1)))
    dossier = app.write_scan_folder(
        tmp_path / "vrac", _feuilles_de_lot(2) + a_l_envers)
    assert _detecter(projet, dossier) == 0

    document = _document_du_lot(projet, LOTS[1])
    adresses = [
        (page["read_rank"], page["page_index"]) for page in document["pages"]]
    # Par numero de planche : la planche 0 d'abord, bien qu'elle soit passee
    # SECONDE sous le scanner.
    assert adresses == [(3, 0), (2, 1)], adresses
    assert [page_index for _rang, page_index in adresses] == [0, 1]
    # Et le rang de lecture n'est pas perdu pour autant : il reste porte par
    # chaque page, simplement il n'ordonne plus la liste.
    assert sorted(rang for rang, _index in adresses) == [2, 3]
    # Dit autrement, et c'est la moitie qui mord : les numeros de planche
    # MONTENT, bien que la passe physique les ait rencontres a l'envers. Un
    # document range par rang de lecture les rendrait decroissants.
    assert [page["page_index"] for page in document["pages"]] == [0, 1]
    assert [page["read_rank"] for page in document["pages"]] == [3, 2]

    # Volet symetrique : le lot LEURRE, pose DANS l'ordre, rend la meme liste
    # sous les deux regles -- sans lui, on ne saurait pas si le test mesure
    # l'ordre des planches ou simplement une inversion appliquee partout.
    leurre = _document_du_lot(projet, LOTS[2])
    assert [
        (page["read_rank"], page["page_index"]) for page in leurre["pages"]
    ] == [(0, 0), (1, 1)]
