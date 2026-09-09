# -*- coding: utf-8 -*-
"""Story 11.4b, lot S3 -- la couche `manual_corrections` est CONSOMMEE (AC 4).

Ce que ce banc mesure, et ce qu'aucun autre ne mesurait avant lui. La story 7.5
a livre `scan_corrections` entier -- deux listes, leurs lecteurs, leurs
ecrivains, `payload_depuis_l_identite` et `homographie_depuis_les_coins` -- et
son propre banc en compte 72, tous verts. Et **aucun appelant du coeur ne
l'importait** : une correction posee etait ecrite au document de detection puis
ignoree. L'operatrice voyait un succes et n'obtenait pas ses frames. C'est le
risque R12 a la lettre, et c'est ce que ce banc ferme.

**Toutes les assertions portent sur les FRAMES PRODUITES** (AC 4.3), jamais sur
le document ni sur l'objet de retour. Le motif est mesure et non suppose : une
correction appliquee a la mauvaise planche produit exactement le meme succes
apparent au niveau du document -- meme cardinal, meme statut, meme entree de
lot. Seuls les TIFF distinguent.

**Regle des fabriques, ses trois points a la fois** :

1. la pile porte **trois** planches, et elles sont **distinguables** : trois
   presses de tirage franchement differentes, donc leurs frames n'ont pas la
   meme couleur au centre et leurs octets different ;
2. la planche corrigee est la **deuxieme des trois** -- ni la premiere ni la
   derniere. Ce n'est pas de la surenchere : le lot S2 de cette meme story a
   mesure le 2026-08-30 qu'un mutant `continue` -> `break` **survit** a une
   fabrique ou la cible est en second de deux, donc aussi en dernier -- les
   deux formes y sont indiscernables. Il faut une planche saine **de chaque
   cote** de la corrigee ;
3. l'assertion ne constate pas une existence : elle compare les douze frames a
   celles d'une passe de **reference**, condensat par condensat, et nomme
   exactement lesquelles ont change.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import cv2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import (  # noqa: E402
    cli, layout, page_templates, patch_presets, qr_codes, scan_corrections,
    scan_detection, scan_ingest, scan_write,
)
from mixed_media_utility.detection import aruco as aruco_detection  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402

import test_scan_calibration_application as app  # noqa: E402
import test_calibration_page_source as couleur  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

#: **Trois** feuilles franchement distinguables, et non trois variations d'un
#: meme tirage. Les presses de `app.PRESSES_DU_TIRAGE` ne different que de
#: quelques millièmes -- c'est ce qu'il faut pour mesurer un transport de
#: correction, et c'est trop peu ici : une permutation de planches doit se voir
#: **au centre d'une frame ecrite**, a l'oeil comme au condensat. Les gains
#: s'etagent donc de 0,95 a 0,28.
#:
#: Le QR et les marqueurs ArUco ne passent PAS par la presse (`app.build_page`
#: les peint en noir et blanc francs) : une presse sombre n'empeche donc ni le
#: decodage ni la detection de geometrie, et la fabrique reste realiste.
PRESSES_DISTINCTES = (
    couleur._press(0.95, (0.0250, 0.0240, 0.0260)),
    couleur._press(0.55, (0.0257, 0.0233, 0.0264)),
    couleur._press(0.28, (0.0244, 0.0248, 0.0251)),
)

#: Le rang de lecture de la planche **corrigee** : la deuxieme des trois.
#: Ni la premiere (mutant « rendre le premier element »), ni la derniere
#: (mutant `continue` -> `break`, mesure du lot S2 le 2026-08-30).
RANG_CORRIGE = 1


def _effacer_le_qr(page, payload: dict):
    """Rendre une planche **muette** : son QR est efface, tout le reste reste.

    C'est la panne de terrain que `EPIC7-ARB-103` adresse -- une planche pliee,
    tachee, mal imprimee, dont le symbole ne decode plus alors que la feuille,
    elle, est parfaitement exploitable. La zone effacee est celle que le gabarit
    **resout pour le role de cette page**, jamais une constante recopiee : poser
    le QR ou l'effacer ailleurs qu'a sa place ne mesurerait pas la meme chose.
    """
    zone = next(
        z for z in patch_presets.resolve_page_layout(
            payload["template_id"], payload["page_role"]).reserved_zones_mm
        if z["name"] == "qr_zone")
    cote = int(round(qr_codes.QR_PRINT_SIZE_TARGET_MM / 25.4 * app.DPI))
    x, y = page_templates.mm_to_px(zone["x"], zone["y"], app.DPI)
    page[y:y + cote, x:x + cote] = 255
    return page


def pile_de_trois(dossier: Path, payloads, *, rang_muet: int | None = None) -> Path:
    """Trois planches d'un meme lot, posees dans l'ordre de leur `page_index`.

    `rang_muet` est le rang de lecture (a partir de zero) dont le QR est efface.
    `None` donne la pile de **reference** : les trois QR decodent, aucune
    correction n'est necessaire, et c'est a elle que tout se compare.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    for rang, (payload, presse) in enumerate(zip(payloads, PRESSES_DISTINCTES)):
        page = app.build_page(payload, press=presse)
        if rang == rang_muet:
            page = _effacer_le_qr(page, payload)
        cv2.imwrite(str(dossier / f"page_{rang + 1:02d}.tiff"), page)
    return dossier


def detecter(projet: Path, dossier: Path):
    """Ingerer et detecter, puis rendre ce que la moitie AVAL consomme.

    C'est exactement la sequence que `scan_command` pose avant d'appeler
    l'ecriture : le banc appelle donc le point d'entree **comme la 11.6
    l'appellera**, et non comme le module se mesurerait a lui-meme.
    """
    project_layout.ensure_project_layout(projet)
    report = scan_ingest.ingest_scan_lot(projet, dossier, dpi=app.DPI,
                                         ingest_slug=None)
    scan_ingest.ecrire_le_rapport(projet, report)
    scan_dpi, pages = scan_detection.detect_pages(projet, report, dpi=app.DPI)
    detection = scan_detection.build_lot_report(
        pages,
        ingest_slug=report.ingest_slug,
        scan_dpi=scan_dpi,
        ingest_declared_dpi=report.declared_dpi,
        ingested_count=len(report.pages),
    )
    payloads = tuple(page.payload for page in detection.pages
                     if page.payload is not None)
    return report, detection, payloads


def coins_reels(projet: Path, page, *, decalage=(0.0, 0.0)) -> scan_corrections.CoinsCorriges:
    """Les quatre contours ArUco **reellement lus** sur cette planche.

    C'est le geste de l'operatrice, et non une fabrique de synthese : la vue de
    reparation lui montre les contours que le detecteur a trouves, et elle les
    repose. Les contours viennent donc du **vrai** detecteur du depot
    (`detection.aruco`), et les pixels du point d'entree publie par l'ingestion
    (`load_page_array`), jamais d'un `cv2.imread` local.

    `decalage` translate les quatre contours ensemble : c'est ce qui rend la
    correction **visible sur les octets produits**. Reposer les contours a leur
    place exacte redonne la geometrie que la machine aurait calculee -- ce que
    `scan_corrections.centre_du_carre` promet en toutes lettres (« un contour
    laisse intact redonne exactement le centre que la machine avait publie ») --
    et c'est precisement ce qui rend une correction juste indiscernable d'une
    correction absente. Une correction posee AILLEURS, elle, se voit.
    """
    dx, dy = decalage
    image = scan_ingest.load_page_array(
        projet,
        scan_ingest.PageLocator(source_path=page.locator_source,
                                page_index=page.locator_page_index),
        dpi=app.DPI)
    contours, identifiants = aruco_detection.detect_markers(image, dpi=app.DPI)
    marqueurs = aruco_detection.build_markers_document(
        "page", contours, identifiants)["images"][0]["markers"]
    carres = tuple(
        (marqueur["id"],
         tuple((float(x) + dx, float(y) + dy) for x, y in marqueur["corners"]))
        for marqueur in marqueurs
        if marqueur["id"] in layout.CORNER_MARKER_IDS)
    return scan_corrections.CoinsCorriges(read_rank=page.read_rank, carres=carres)


def identite_de_la_planche(payload: dict, *, read_rank: int,
                           **surcharges) -> scan_corrections.IdentiteManuelle:
    """L'identite que l'operatrice **lit sur le papier** de cette planche.

    Elle est derivee du payload que le QR aurait livre, champ par champ : c'est
    ce que le pied technique de la planche imprime et ce que l'operatrice
    recopie. Les huit valeurs neutres du lot (`CHAMPS_NEUTRES_DU_LOT`) n'y sont
    volontairement pas -- elles ne sont pas sur le papier, et c'est tout le
    point de `payload_depuis_l_identite`.
    """
    emplacements = payload["slots"]
    defauts = dict(
        read_rank=read_rank,
        lot_id=payload["lot_id"],
        template_id=payload["template_id"],
        frames_per_page=len(emplacements),
        page_index=payload["page_index"],
        first_frame_timecode=emplacements[0]["frame_timecode"],
        last_frame_timecode=emplacements[-1]["frame_timecode"],
    )
    defauts.update(surcharges)
    return scan_corrections.IdentiteManuelle(**defauts)


def ecrire(projet: Path, report, detection, payloads, **surcharges):
    return scan_write.ecrire_le_lot_detecte(
        projet, report, detection, payloads,
        dpi_geometrie=app.DPI, dpi_manifest=app.DPI, **surcharges)


def condensats(projet: Path) -> dict:
    """Les frames du projet, **par nom et par condensat des octets**.

    Ni une liste de noms ni un cardinal : deux planches dont les frames seraient
    permutees porteraient les memes noms et le meme compte. Ce sont les octets
    qui distinguent -- et les trois presses de la fabrique existent pour que la
    permutation les change.
    """
    racine = projet / project_layout.SCAN_FRAMES_DIRNAME
    return {
        chemin.name: hashlib.sha256(chemin.read_bytes()).hexdigest()
        for chemin in sorted(racine.rglob("*.tiff"))
    }


def empreinte_disque(racine: Path) -> dict:
    """L'identite ET la date de chaque fichier du projet, chemin par chemin.

    **Un condensat ne prouve pas qu'un fichier n'a pas ete touche** quand la
    fabrique est deterministe : reecrit a l'identique, il rend les memes octets
    -- le banc de la 11.4 l'a mesure le 2026-08-30 (`EPIC11-ARB-83`).

    Les deux champs sont necessaires, et c'est **mesure** sur ce depot, pas
    suppose. Les deux familles d'ecriture n'ont pas la meme trace :

    * le manifest, le rapport de tri, le profil designe passent par une ecriture
      **atomique** (temporaire puis `os.replace`) : le numero d'inode change ;
    * les frames, elles, sont ecrites par `cv2.imwrite` **en place** : le fichier
      est tronque et reecrit, donc l'inode SURVIT. Une mesure d'inodes seule
      serait verte apres une reecriture complete du lot -- exactement le faux
      negatif que ce banc existe pour eviter. C'est `st_mtime_ns` qui mord la.

    Le volet symetrique ci-dessous verifie que cette empreinte-la bouge sur une
    passe qui reecrit vraiment.
    """
    return {
        str(chemin.relative_to(racine)):
            (chemin.stat().st_ino, chemin.stat().st_mtime_ns,
             chemin.stat().st_size)
        for chemin in sorted(racine.rglob("*")) if chemin.is_file()}


@pytest.fixture(scope="module")
def payloads_du_lot():
    """Les trois payloads du lot, sans page de calibration.

    C'est le regime **nominal** du depot depuis `EPIC5-ARB-83` : la page de
    calibration se scanne dans une passe separee et l'operateur designe le
    profil. Les `slot_index` valent donc 0-3, 4-7, 8-11 -- exactement ce que
    `scan_corrections._slots_interpoles` recompose depuis `page_index * nominal`.
    """
    return app.lot_payloads(sheet_count=3, with_calibration=False)


@pytest.fixture(scope="module")
def reference(tmp_path_factory, payloads_du_lot) -> dict:
    """La passe de **reference** : trois QR lisibles, aucune correction.

    C'est la seule mesure a laquelle les passes corrigees se comparent. Sans
    elle, « la planche a produit ses frames » ne dit rien : une mire de
    remplacement porte le meme nom de fichier et le meme cardinal.
    """
    racine = tmp_path_factory.mktemp("reference")
    projet = racine / "projet"
    dossier = pile_de_trois(racine / "scan", payloads_du_lot)
    report, detection, payloads = detecter(projet, dossier)
    issue = ecrire(projet, report, detection, payloads)
    assert issue.output.synthetic_frame_count == 0
    return condensats(projet)


@pytest.fixture(scope="module")
def lot_nominal(tmp_path_factory, payloads_du_lot):
    """Un lot detecte, partage par les tests qui **n'ecrivent rien**.

    Les trois refus mesures plus bas tombent tous avant la premiere ecriture :
    ils peuvent donc partager une detection, et la partager est ce qui garde ce
    banc court. Aucun test qui ecrit ne touche a ce projet.
    """
    racine = tmp_path_factory.mktemp("nominal")
    projet = racine / "projet"
    dossier = pile_de_trois(racine / "scan", payloads_du_lot)
    report, detection, payloads = detecter(projet, dossier)
    return projet, report, detection, payloads


# ---------------------------------------------------------------------------
# AC 4.1 -- les identites completent les payloads AVANT l'ecriture
# ---------------------------------------------------------------------------


def test_une_planche_MUETTE_completee_produit_EXACTEMENT_ses_frames(
    tmp_path, payloads_du_lot, reference,
) -> None:
    """AC 4.1, AC 4.3 et AC 4.4, ensemble et sur les octets.

    La deuxieme planche des trois est **muette** : son QR est efface, donc la
    detection la refuse et ne lui donne meme pas de geometrie
    (`qr-inexploitable-sans-manifest`, aucun gabarit connu, aucune homographie).
    L'operatrice saisit son identite et repose ses quatre coins ; les deux
    corrections sont posees par les VRAIES fonctions de `scan_corrections`,
    jamais par un dictionnaire ecrit a la main.

    Ce que le banc mesure ensuite n'est pas que « des frames existent » : c'est
    que **les douze frames sont, octet pour octet, celles de la passe de
    reference** -- celle ou le QR de cette planche decodait. Une planche
    completee produit donc exactement ce qu'elle aurait produit sans la panne.

    Sans la consommation, cette planche ne porte aucun payload : elle n'ecrit
    ni frame ni motif (« sans timecode il n'y a pas de frame a ecrire, mais un
    trou a declarer », `_scanned_pages_for_output`). Avec une consommation qui
    lui donne l'identite mais pas la geometrie, elle ecrit quatre **mires** de
    remplacement : memes noms, memes cardinaux, autres octets. Les deux faux
    succes sont fermes par la meme assertion.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot,
                            rang_muet=RANG_CORRIGE)
    report, detection, payloads = detecter(projet, dossier)

    # La detection ne sait RIEN de cette planche : c'est l'etat de depart, et il
    # est mesure plutot que suppose -- une fabrique dont le QR resterait lisible
    # rendrait tout le reste du test vrai par vacuite.
    muette = next(p for p in detection.pages if p.read_rank == RANG_CORRIGE)
    assert muette.payload is None and muette.homography is None
    assert len(payloads) == 2, "la pile ne doit porter que DEUX planches lues"

    document = scan_corrections.poser_les_identites(
        {}, [identite_de_la_planche(payloads_du_lot[RANG_CORRIGE],
                                    read_rank=RANG_CORRIGE)])
    document = scan_corrections.poser_les_coins(
        document, [coins_reels(projet, muette)])

    issue = ecrire(projet, report, detection, payloads,
                   corrections_manuelles=document)

    # Aucune mire : les frames de la planche completee sont de VRAIS pixels.
    assert issue.output.synthetic_frame_count == 0, issue.output.warnings
    assert issue.output.written_frame_count == 12
    # Et elles sont celles de la reference, nom pour nom et octet pour octet.
    assert condensats(projet) == reference


def test_le_manifest_declare_la_planche_completee_PRESENTE(
    tmp_path, payloads_du_lot,
) -> None:
    """AC 4.1, second volet : le lot redevient complet, et c'est verifiable.

    La planche muette manquait au lot -- son `page_index` etait absent des pages
    declarees. Une completion qui n'atteindrait que les frames sans atteindre le
    manifest laisserait un lot declare **incomplet** dont tous les fichiers sont
    pourtant la : deux verites pour le meme fait, ce que `EPIC5-ARB-78` refuse.

    **Trois emplacements du manifest, et il faut les trois** -- mesure de la
    campagne de mutation de ce lot, pas une precaution de style :

    * `reconstruction.page_roles` et `reconstruction.slots` viennent du **tuple de
      payloads**, tandis que les frames viennent des **pages de detection**. Un
      mutant qui ne rebatit pas le tuple ecrit donc les douze frames et n'en
      declare que huit : les fichiers sont la, le manifest ne les connait pas.
      Il **survivait** a la seule assertion sur les cardinaux du lot ;
    * `reconstruction.scan.pages` porte la provenance page par page, et c'est le
      seul endroit ou le `page_index` **de la page detectee** se relit. Un
      decalage d'un y designait la mauvaise feuille sans qu'aucune frame ne
      bouge -- il survivait lui aussi.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot,
                            rang_muet=RANG_CORRIGE)
    report, detection, payloads = detecter(projet, dossier)
    muette = next(p for p in detection.pages if p.read_rank == RANG_CORRIGE)
    document = scan_corrections.poser_les_identites(
        {}, [identite_de_la_planche(payloads_du_lot[RANG_CORRIGE],
                                    read_rank=RANG_CORRIGE)])
    document = scan_corrections.poser_les_coins(
        document, [coins_reels(projet, muette)])

    issue = ecrire(projet, report, detection, payloads,
                   corrections_manuelles=document)

    assert issue.persisted.lot_complete is True
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    (lot,) = manifest["lots"]
    assert lot["reconstructed_frame_count"] == 12
    assert lot["synthetic_frame_count"] == 0

    reconstruction = manifest["reconstruction"]
    # Les TROIS planches sont declarees, la completee comprise.
    assert [page["page_index"]
            for page in reconstruction["page_roles"]] == [0, 1, 2]
    assert len(reconstruction["slots"]) == 12
    # Et la provenance de scan nomme la planche corrigee a SON rang et a SON
    # index -- l'appariement `read_rank` <-> `page_index` transporte, jamais
    # deduit l'un de l'autre.
    provenance = {page["read_rank"]: page
                  for page in reconstruction["scan"]["pages"]}
    assert provenance[RANG_CORRIGE]["page_index"] == RANG_CORRIGE
    assert provenance[RANG_CORRIGE]["homography_status"] == "resolved"
    # Le QR n'a toujours rien livre, et le manifest continue de le dire: la
    # correction decide ce qui est ECRIT, elle ne reecrit pas ce que la machine
    # a lu (`EPIC7-ARB-95`, meme doctrine que l'empreinte non resignee).
    assert provenance[RANG_CORRIGE]["qr_status"] != "decoded"


def test_la_geometrie_se_rejoue_au_DPI_DE_DETECTION_et_non_a_celui_du_manifest(
    tmp_path, payloads_du_lot, reference,
) -> None:
    """Les deux DPI ne sont pas le meme, et les coins se lisent dans le premier.

    Les contours sont poses en **pixels du scan**, lu au DPI qui a decide
    l'homographie et les zones (`scan_dpi_detection` d'un document de
    detection). Le manifest, lui, recoit `scan_dpi_declared`, et les deux
    divergent legitimement sur le chemin `scan write`. Redresser au second
    deplacerait la page entiere.

    Les deux valent `--dpi` sur le chemin `scan` d'un bloc : une passe ou ils
    coincident ne peut donc pas distinguer les deux lectures, et le mutant qui
    les echange y **survit** -- mesure de ce lot. Ce test les fait diverger.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot,
                            rang_muet=RANG_CORRIGE)
    report, detection, payloads = detecter(projet, dossier)
    muette = next(p for p in detection.pages if p.read_rank == RANG_CORRIGE)
    document = scan_corrections.poser_les_identites(
        {}, [identite_de_la_planche(payloads_du_lot[RANG_CORRIGE],
                                    read_rank=RANG_CORRIGE)])
    document = scan_corrections.poser_les_coins(
        document, [coins_reels(projet, muette)])

    scan_write.ecrire_le_lot_detecte(
        projet, report, detection, payloads,
        dpi_geometrie=app.DPI, dpi_manifest=2 * app.DPI,
        corrections_manuelles=document)

    # Les douze frames sont celles de la reference: le DPI du manifest n'a
    # aucune prise sur la geometrie.
    assert condensats(projet) == reference
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert manifest["reconstruction"]["scan"]["scan_dpi"] == 2 * app.DPI


# ---------------------------------------------------------------------------
# AC 4.2 -- les coins decident l'homographie de LEUR page
# ---------------------------------------------------------------------------


def test_les_coins_reposes_decident_l_homographie_de_LEUR_planche(
    tmp_path, payloads_du_lot, reference,
) -> None:
    """AC 4.2 et AC 4.4 : la correction change les frames de sa planche, et
    **d'aucune autre**.

    Verbatim de `scan_corrections.homographie_depuis_les_coins`, recopie ici
    face au test qui le mesure : « **Le point unique ou la correction devient de
    la geometrie** [...] l'interface la calcule pour montrer le resultat a
    l'ecran, `scan-write` la recalcule pour decouper les pixels. Deux redactions
    de cet ajustement divergeraient, et le desaccord ne se verrait que sur les
    TIFF produits -- c'est-a-dire trop tard. »

    Les trois QR sont lisibles ici : la geometrie de la planche du milieu est
    donc **deja resolue** par la detection, et la seule chose que la correction
    puisse changer est de la remplacer. Les contours sont reposes translates,
    ce qui rend l'ecart visible sur les octets. L'assertion nomme exactement les
    quatre frames qui changent : une correction appliquee a la mauvaise planche
    en ferait changer quatre autres -- et un test qui se contenterait de
    compter, ou de constater « quelque chose a change », ne verrait pas la
    difference. Verbatim de l'AC 4.4 : « Une correction appliquee a la mauvaise
    page produit exactement le meme succes apparent. »
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot)
    report, detection, payloads = detecter(projet, dossier)
    cible = next(p for p in detection.pages if p.read_rank == RANG_CORRIGE)
    assert cible.homography is not None, (
        "la planche visee doit avoir une geometrie AVANT la correction: sinon "
        "le test mesurerait une geometrie donnee, pas une geometrie remplacee")

    document = scan_corrections.poser_les_coins(
        {}, [coins_reels(projet, cible, decalage=(200.0, 140.0))])
    ecrire(projet, report, detection, payloads, corrections_manuelles=document)

    obtenus = condensats(projet)
    assert set(obtenus) == set(reference), "les noms de frames ne doivent pas bouger"
    changees = {nom for nom, valeur in obtenus.items() if valeur != reference[nom]}
    # Les quatre emplacements de la planche du milieu, et eux seuls: 4 a 7.
    attendues = {
        f"scan_rush-001_5_00-00-{rang:02d}-00.tiff" for rang in range(4, 8)}
    assert changees == attendues, sorted(changees)


# ---------------------------------------------------------------------------
# AC 4.5 -- une identite incompletable refuse AVANT toute ecriture
# ---------------------------------------------------------------------------


def _premiere_passe(tmp_path, payloads_du_lot):
    """Un lot deja ecrit : frames sur le disque, manifest ecrit, temoin depose.

    C'est l'etat qu'un refus tardif detruirait -- et le seul etat ou « avant
    toute ecriture » se mesure autrement qu'en constatant une absence.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot)
    report, detection, payloads = detecter(projet, dossier)
    ecrire(projet, report, detection, payloads)
    temoin = projet / project_layout.SCAN_FRAMES_DIRNAME / "temoin-de-non-ecriture.txt"
    temoin.write_text("rien ne doit toucher ce dossier", encoding="utf-8")
    return projet, report, detection, payloads, temoin


def test_une_identite_INCOMPLETABLE_refuse_AVANT_toute_ecriture(
    tmp_path, payloads_du_lot,
) -> None:
    """AC 4.5, mesuree sur le DISQUE et non sur le seul type d'exception.

    Verbatim de `scan_corrections.IdentiteIncompletable`, recopie face au test
    qui le mesure : « Refus **nomme**, jamais un repli [...] Les inventer
    produirait des TIFF d'apparence valide au mauvais timecode. »

    Et verbatim d'`EPIC5-ARB-34`, qui donne sa forme a l'assertion : « un refus
    qui arrive apres une destruction n'est pas un refus ». La seconde passe
    demande `overwrite=True` **et** designe un profil de calibration : les deux
    ecritures que la sequence sait faire -- les frames du lot et le versement du
    profil designe au projet -- sont donc armees. Le refus doit tomber avant les
    deux.

    **Le condensat ne suffirait pas ici** : la fabrique est deterministe, donc
    un lot efface puis reecrit rend les memes octets. La mesure porte sur ce
    qu'une reecriture change quoi qu'elle rende -- le numero d'inode -- et sur
    la survie d'un temoin depose dans le dossier de lot.
    """
    projet, report, detection, payloads, temoin = _premiere_passe(
        tmp_path, payloads_du_lot)
    profil = app.consigner_le_profil_de_la_chaine(
        tmp_path / "projet-atelier", tmp_path, name="atelier")
    avant = empreinte_disque(projet)

    # Le gabarit de cette planche porte quatre emplacements; l'operatrice en
    # declare cinq. C'est une saisie plausible et fausse -- pas un cas de
    # laboratoire -- et le refus doit la NOMMER.
    faute = identite_de_la_planche(
        payloads_du_lot[RANG_CORRIGE], read_rank=RANG_CORRIGE,
        frames_per_page=5)
    document = scan_corrections.poser_les_identites({}, [faute])

    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        ecrire(projet, report, detection, payloads, overwrite=True,
               profil_designe=profil, origine_du_profil="test",
               corrections_manuelles=document)

    motif = str(refus.value)
    assert payloads_du_lot[RANG_CORRIGE]["template_id"] in motif, motif
    assert "5" in motif and "4" in motif, motif

    assert temoin.is_file(), (
        "le dossier de lot a ete vide: le refus est arrive APRES une ecriture")
    assert empreinte_disque(projet) == avant, (
        "des fichiers du projet ont ete reecrits avant le refus -- le contenu "
        "peut revenir identique, l'ecriture a bien eu lieu")


def test_la_mesure_d_inodes_MORD_sur_une_seconde_passe_qui_ecrit_vraiment(
    tmp_path, payloads_du_lot,
) -> None:
    """Volet symetrique du test ci-dessus, et il est indispensable.

    Sans lui, « les inodes n'ont pas bouge » serait vrai de toute passe qui
    n'ecrit rien -- y compris d'une passe que `overwrite=True` n'aurait en
    realite jamais fait reecrire. La meme seconde passe, **sans** la correction
    fautive, doit donc faire changer les inodes des frames.
    """
    projet, report, detection, payloads, _temoin = _premiere_passe(
        tmp_path, payloads_du_lot)
    avant = empreinte_disque(projet)

    ecrire(projet, report, detection, payloads, overwrite=True)

    apres = empreinte_disque(projet)
    # Les frames ECRITES, pas les copies ingerees du scan: celles-ci ne sont pas
    # reecrites par une seconde passe, et les inclure rendrait l'assertion
    # fausse pour une raison qui n'a rien a voir avec ce qu'elle mesure.
    frames = [nom for nom in avant
              if nom.startswith(f"{project_layout.SCAN_FRAMES_DIRNAME}/")
              and nom.endswith(".tiff")]
    assert frames, "la premiere passe doit avoir ecrit des frames"
    assert all(apres[nom] != avant[nom] for nom in frames), (
        "la seconde passe n'a rien reecrit: la mesure d'inodes du test "
        "precedent serait vraie sans rien prouver")


# ---------------------------------------------------------------------------
# AC 4.3 -- aucune correction posee ne peut etre silencieusement ignoree
# ---------------------------------------------------------------------------


def test_une_correction_posee_sur_une_planche_ABSENTE_est_REFUSEE(
    lot_nominal,
) -> None:
    """AC 4.3 : un rang de lecture qu'aucune planche de la pile ne porte.

    C'est le cas du document de correction et de la pile qui ne sont pas ceux du
    meme passage -- deux scans du meme lot, l'un a quatre feuilles, l'autre a
    trois. Ignorer la correction rendrait un succes complet dont l'operatrice ne
    verrait jamais qu'il lui manque son travail.

    Le rang fautif est **plus grand que tous** ceux de la pile : un refus ecrit
    « si le rang depasse le cardinal » et un refus ecrit « si le rang n'est pas
    dans la pile » sont indiscernables autrement -- mais le second est le seul
    juste, les rangs d'un lot trie n'etant pas contigus.
    """
    projet, report, detection, payloads = lot_nominal
    absent = max(page.read_rank for page in detection.pages) + 3
    document = scan_corrections.poser_les_identites(
        {}, [identite_de_la_planche(payloads[0], read_rank=absent)])

    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        ecrire(projet, report, detection, payloads,
               corrections_manuelles=document)
    assert str(absent) in str(refus.value), str(refus.value)


def test_des_coins_poses_sur_une_planche_SANS_GABARIT_sont_REFUSES(
    tmp_path, payloads_du_lot,
) -> None:
    """AC 4.3 : corriger la geometrie d'une planche dont on ignore le gabarit.

    Le redressement envoie les quatre coins lus vers les coins **nominaux du
    gabarit** : sans gabarit, il n'y a pas de destination. La reponse n'est ni
    un gabarit devine -- ce que 5.2 refuse depuis toujours -- ni un silence,
    mais un refus qui dit quoi faire d'abord.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot,
                            rang_muet=RANG_CORRIGE)
    report, detection, payloads = detecter(projet, dossier)
    muette = next(p for p in detection.pages if p.read_rank == RANG_CORRIGE)

    document = scan_corrections.poser_les_coins({}, [coins_reels(projet, muette)])

    with pytest.raises(scan_corrections.CorrectionInvalide) as refus:
        ecrire(projet, report, detection, payloads,
               corrections_manuelles=document)
    assert str(RANG_CORRIGE) in str(refus.value), str(refus.value)
    assert not list((projet / project_layout.SCAN_FRAMES_DIRNAME).rglob("*.tiff")), (
        "un refus de correction ne doit laisser aucune frame")


def test_le_modele_de_completion_est_celui_du_LOT_et_non_le_premier_venu() -> None:
    """AC 4.3, a l'unite : l'appariement identite <-> lot, jamais par position.

    C'est litteralement le mutant `M25` de la story 5.7 -- `_find_lot` rendait
    le **premier** lot au lieu du lot vise, et 257 tests restaient verts parce
    que toutes les fixtures multi-lots placaient le lot vise en premier. La
    consequence reelle etait d'ecrire les cardinaux sur le mauvais lot ; ici,
    elle serait d'ecrire les frames d'une planche a la **cadence d'un autre
    lot**, sans un mot.

    Trois lots, la cible au **milieu** : ni la premiere position (mutant
    « rendre le premier »), ni la derniere (mutant `break` a la premiere
    iteration, indiscernable sur deux elements).
    """
    lots = []
    for rang, (rush, fps) in enumerate(
            (("rush-alpha", 5.0), ("rush-beta", 12.5), ("rush-gamma", 25.0))):
        import test_scan_manifest as fixtures
        lots.append(fixtures.make_payload(
            page_index=0, page_count=1, slot_count=2, rush_id=rush,
            fps_target=fps, template_id=app.TEMPLATE,
            patch_preset_id=app.PRESET))
    vise = lots[1]

    modele = scan_write._modele_de_completion(tuple(lots), vise["lot_id"])

    assert modele is vise
    assert modele["fps_target"] == 12.5

    # Et le refus est NOMME quand aucune planche du lot vise n'a ete lue: c'est
    # le regime 2 d'`EPIC11-ARB-64` -- « il faut une planche lue, ou les champs
    # imprimes » --, jamais une invention.
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_write._modele_de_completion(tuple(lots), "rush-delta_50")
    assert "rush-delta_50" in str(refus.value)


# ---------------------------------------------------------------------------
# Frontieres negatives -- l'absence de correction ne change RIEN
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("couche", [
    pytest.param(None, id="aucun-document"),
    pytest.param({}, id="document-sans-couche"),
    pytest.param({"pages": [], "counters": {}}, id="document-etranger-sans-couche"),
])
def test_sans_correction_le_couple_rendu_est_le_MEME_objet(lot_nominal, couche) -> None:
    """`AR3` de la story 5.28, transpose : « sans lui, **rien ne change** ».

    L'assertion porte sur l'**identite** des objets et non sur leur egalite : un
    couple reconstruit a l'identique passerait une comparaison par valeur tout
    en ayant traverse une seconde redaction de l'appariement page <-> payload --
    exactement le chemin ou une permutation naitrait. Rien ne doit etre
    reconstruit quand rien n'est pose.
    """
    _projet, _report, detection, payloads = lot_nominal

    rendu_detection, rendu_payloads = scan_write.consommer_les_corrections_manuelles(
        detection, payloads, corrections=couche, dpi=app.DPI)

    assert rendu_detection is detection
    assert rendu_payloads is payloads


def test_une_couche_VIDEE_de_ses_deux_listes_ne_change_rien(lot_nominal) -> None:
    """Meme frontiere, prise par le geste reel : « tout annuler ».

    `poser_les_identites(document, [])` sur un document qui n'a plus de coins
    **retire la couche entiere** plutot que d'ecrire une couche vide -- « annuler
    toutes ses corrections doit redonner exactement le document d'avant, sinon
    l'annulation laisserait une trace ». Le chemin d'ecriture doit lire ce
    document-la comme il lit un document jamais corrige.
    """
    _projet, _report, detection, payloads = lot_nominal
    document = scan_corrections.poser_les_identites(
        {}, [identite_de_la_planche(payloads[0], read_rank=0)])
    annule = scan_corrections.poser_les_identites(document, [])
    assert scan_corrections.CLE_DOCUMENT not in annule

    rendu_detection, rendu_payloads = scan_write.consommer_les_corrections_manuelles(
        detection, payloads, corrections=annule, dpi=app.DPI)

    assert rendu_detection is detection
    assert rendu_payloads is payloads


# ---------------------------------------------------------------------------
# La sortie du refus: code retour et motif, des deux cotes
# ---------------------------------------------------------------------------


def test_un_refus_de_correction_sort_en_code_1_et_non_en_trace_PYTHON() -> None:
    """AC 4.5, second volet : « refuse [...] **avec son motif** ».

    La table `CODES_DE_SORTIE` est le seul chemin par lequel un refus du coeur
    devient un code de sortie, et elle est lue par la CLI **et** par la TUI
    (`EPIC11-ARB-75` : dupliquer la table laisserait deux verites au meme
    moment). Sans l'entree `CorrectionInvalide`, une identite incompletable
    sortait de `mmu scan write` en trace Python nue.

    `IdentiteIncompletable` n'a **pas** d'entree a elle : elle est une
    sous-classe, et la recherche rend la premiere entree qui correspond. Le test
    mesure les deux, pour qu'une entree ajoutee plus haut ne puisse pas les
    separer.
    """
    for exception in (scan_corrections.CorrectionInvalide("motif"),
                      scan_corrections.IdentiteIncompletable("motif")):
        assert scan_write.code_de_sortie(exception) == scan_write.CODE_ERREUR
        famille, _code = scan_write.correspondance_de_sortie(exception)
        assert famille is scan_corrections.CorrectionInvalide


def test_la_CLI_de_scan_write_CONSOMME_la_couche_du_document(
    tmp_path, payloads_du_lot, reference, capsys,
) -> None:
    """La liaison bout en bout, par les deux commandes reelles.

    `scan detect` produit le document, l'operatrice y pose ses corrections avec
    `scan_corrections.ecrire` -- l'ecrivain canonique et atomique du depot --,
    puis `scan write` consomme ce document. C'est le seul chemin ou l'on mesure
    que le document **brut** atteint le coeur : le lecteur de `scan_previz` ne
    voit pas cette couche, et c'est meme la propriete qui la rend additive
    (`EPIC7-ARB-95`). Passer l'objet relu a la place du brut ferait tomber ce
    test et lui seul.

    La confrontation reste celle des octets, contre la passe de reference.
    """
    projet = tmp_path / "projet"
    dossier = pile_de_trois(tmp_path / "scan", payloads_du_lot,
                            rang_muet=RANG_CORRIGE)
    assert cli.main(["scan", "--project", str(projet), "--scan", str(dossier),
                     "--dpi", str(app.DPI), "--lot-slug", "lot-corrige",
                     "detect"]) == 0
    capsys.readouterr()
    (document_path,) = sorted(
        (projet / project_layout.SCANS_DIRNAME).rglob("detections/*.json"))
    brut = json.loads(document_path.read_text(encoding="utf-8"))

    # Le rang de lecture de la planche muette se lit DANS le document, jamais
    # par position: c'est l'adresse que la couche emploie.
    muette = next(page for page in brut["pages"] if "payload" not in page)
    coins = coins_reels(
        projet,
        _PageDuDocument(read_rank=muette["read_rank"],
                        locator_source=muette["source"]["path_relative"],
                        locator_page_index=muette["source"]["page_index"]))
    document = scan_corrections.poser_les_identites(
        brut, [identite_de_la_planche(payloads_du_lot[RANG_CORRIGE],
                                      read_rank=muette["read_rank"])])
    document = scan_corrections.poser_les_coins(document, [coins])
    scan_corrections.ecrire(document_path, document)

    assert cli.main([cli.SCAN_WRITE_COMMAND, "--project", str(projet),
                     "--detection", str(document_path)]) == 0
    assert condensats(projet) == reference


@dataclasses.dataclass(frozen=True)
class _PageDuDocument:
    """Les trois champs que `coins_reels` lit d'une page, tires du document.

    Adaptateur de banc, pas de production : la fabrique de coins prend une page
    detectee, et le test de bout en bout n'en a pas -- il n'a que le document
    persiste. Les trois champs sont transportes **nommement**, jamais deduits
    l'un de l'autre.
    """

    read_rank: int
    locator_source: str
    locator_page_index: int | None
