# -*- coding: utf-8 -*-
"""Fabriques de fixtures de l'atelier Scan (story 7.3, Task 9).

**Regle des fabriques du depot, appliquee sans exception** (CLAUDE.md, posee
apres 5.6/`M33`, 5.7/`M25` et les cinq survivants de 5.8, puis re-mordue en
5.16). Cette story expose **trois** collections au meme defaut d'appariement :
les entrees de la zone tampon, les cartes de tache, et les documents de
detection par lot. Donc, ici et pas en revue :

1. la fabrique d'entrees produit **trois** entrees distinguables -- noms,
   natures, formes et issues differentes, jamais un remplissage uniforme ;
2. la fabrique de documents produit **deux** lot aux completudes
   **differentes** (l'un complet, l'autre incomplet, cardinaux differents) ;
3. **la cible naturelle des assertions est la SECONDE** de chaque collection :
   un `find` fautif qui rendrait toujours le premier element ne se demasque
   pas autrement.

Les documents produits sont des documents `scan_previz` **reels** : ils
passent par `scan_previz.scan_previz_from_json_dict`, qui les refuse s'ils ne
sont pas complets. Une fixture qui deriverait de la forme normative echoue
donc bruyamment, jamais en silence. Ce sont des fixtures **de contrat** : on
n'en tire aucune conclusion sur la qualite de detection.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Les payloads QR REELS vivent deja dans le banc du coeur : on les APPELLE
# plutot que d'en bricoler une seconde redaction ici -- un payload fabrique a
# la main passerait des gardes que le vrai ne passe pas, ou l'inverse.
_BANC_DU_COEUR = Path(__file__).resolve().parents[1]
if str(_BANC_DU_COEUR) not in sys.path:
    sys.path.insert(0, str(_BANC_DU_COEUR))

import fabriques_chutier as fab
import test_scan_manifest as _payloads
from mixed_media_utility import previz_common, scan_detect, scan_previz, scan_sorting
from mixed_media_utility.gui import modele_zone_tampon as modele_tampon

#: Les deux lot de reference de cette story, distinguables en TOUT : nom,
#: cardinal de pages attendu, cadence, et completude.
LOT_COMPLET = "lot-scan-24"
LOT_INCOMPLET = "lot-scan-18"

PROJET = "proj-demo"
RUSH = "rush-alpha"
INGEST_SLUG = "vrac-du-jour"


# ---------------------------------------------------------------------------
# Les chemins deposables : trois entrees distinguables, cible en SECONDE
# ---------------------------------------------------------------------------


def trois_chemins_distinguables(racine: Path) -> tuple[Path, Path, Path]:
    """Trois chemins reels, de **trois natures differentes**.

    Dans l'ordre : un dossier (`pile-alpha`), un **PDF** (`planche-beta.pdf`)
    -- la cible, en SECONDE position --, puis une image seule
    (`feuille-gamma.tiff`).

    Les trois donnent trois natures et trois issues distinctes : un
    remplissage uniforme cacherait un appariement inverse entre une entree et
    sa ligne, sa carte, ou son motif.

    Note `EPIC7-ARB-89` : la SECONDE etait la cible parce qu'un PDF etait le
    seul chemin dont la « forme » etait ambigue (`EPIC7-ARB-13`, clos sans
    objet). Elle le reste pour une autre raison, tout aussi valable -- c'est
    la seule des trois qui ne soit ni la premiere ni la derniere.
    """
    racine = Path(racine)
    dossier = racine / "pile-alpha"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "page_01.tiff").write_bytes(b"alpha-1")
    (dossier / "page_02.tiff").write_bytes(b"alpha-2")

    pdf = racine / "planche-beta.pdf"
    pdf.write_bytes(b"%PDF-beta")

    image = racine / "feuille-gamma.tiff"
    image.write_bytes(b"gamma")
    return dossier, pdf, image


#: Le dossier qui porte la selection multiple ci-dessous. C'est aussi le slug
#: que le coeur retiendra pour ce lot (`scan_ingest._slug_par_defaut_d_une_
#: selection` : le nom du dossier parent commun), et le banc ne le recopie
#: donc jamais a la main -- il le compare a ce que le coeur rend.
SELECTION_DOSSIER = "selection-multi"


def quatre_images_d_une_selection(racine: Path) -> tuple[Path, ...]:
    """Quatre images d'un MEME dossier, rendues dans un ordre NON trie.

    Regle des fabriques, deux fois plutot qu'une (`EPIC7-ARB-88` expose une
    collection neuve -- les chemins d'une entree) :

    1. **quatre elements distinguables** : quatre noms differents et quatre
       contenus differents. « Une selection dont tous les fichiers
       porteraient le meme nom rendrait invisible toute erreur d'ordre » --
       et un contenu uniforme cacherait une copie qui ecrase ;
    2. **la cible est en SECONDE position** (`page_01_alpha.tiff`), donc ni
       la premiere ni la derniere : un regroupement qui rendrait toujours le
       premier chemin ne se demasque pas autrement ;
    3. **l'ordre rendu n'est PAS l'ordre de lecture du coeur.** Rendus :
       charlie, alpha, delta, bravo ; le coeur, lui, ordonne par nom
       normalise (alpha, bravo, charlie, delta). Les deux ordres sont donc
       differents SUR CHAQUE POSITION, ce qui rend visible aussi bien une
       GUI qui trierait a la place du coeur (elle n'a pas a le faire :
       `EPIC7-ARB-64`) qu'une GUI qui perdrait l'ordre du geste.
    """
    racine = Path(racine)
    dossier = racine / SELECTION_DOSSIER
    dossier.mkdir(parents=True, exist_ok=True)
    noms = {
        "page_01_alpha.tiff": b"alpha",
        "page_02_bravo.tiff": b"bravo-bravo",
        "page_03_charlie.tiff": b"charlie-charlie-charlie",
        "page_04_delta.tiff": b"delta-delta-delta-delta",
    }
    for nom, contenu in noms.items():
        (dossier / nom).write_bytes(contenu)
    return (
        dossier / "page_03_charlie.tiff",
        dossier / "page_01_alpha.tiff",
        dossier / "page_04_delta.tiff",
        dossier / "page_02_bravo.tiff",
    )


def modele_a_trois_entrees(racine: Path):
    """Un modele de file portant les trois entrees ci-dessus, cible SECONDE.

    Rend `(modele, chemins)`. Aucun dpi n'est pose : c'est l'etat neuf, celui
    ou `Detecter` doit etre inactif ET dire pourquoi (`EPIC7-ARB-44`).
    """
    chemins = trois_chemins_distinguables(racine)
    modele = modele_tampon.ModeleDeZoneTampon()
    modele.deposer(list(chemins))
    return modele, chemins


# ---------------------------------------------------------------------------
# Les documents de detection : deux lot aux completudes DIFFERENTES
# ---------------------------------------------------------------------------


def document_du_lot_complet(*, ingest_slug=INGEST_SLUG):
    """`lot-scan-24` : **2 planches attendues, 2 presentes** -- complet.

    `read_rank` et `page_index` different sur la seconde page : un champ
    confondu avec l'autre se voit.
    """
    return fab.document_de_detection(
        lot_id=LOT_COMPLET,
        rush_id=RUSH,
        project_id=PROJET,
        fps_target_exact="24000/1001",
        pages=[
            fab.page_detectee(0, 0, page_count=2, lot_id=LOT_COMPLET,
                              rush_id=RUSH, project_id=PROJET, largeur_px=101),
            fab.page_detectee(3, 1, page_count=2, lot_id=LOT_COMPLET,
                              rush_id=RUSH, project_id=PROJET, largeur_px=157),
        ],
        pages_expected=2,
        empreinte=fab.EMPREINTES[0],
        ingest_slug=ingest_slug,
    )


def document_du_lot_incomplet(*, ingest_slug=INGEST_SLUG):
    """`lot-scan-18` : **3 planches attendues, 2 presentes** -- il manque la 1.

    C'est la CIBLE des assertions de completude, et elle est **seconde** dans
    toutes les collections de ce module. La planche manquante est l'index `1`,
    donc ni la premiere ni la derniere : un calcul qui prendrait un bord se
    verrait.
    """
    return fab.document_de_detection(
        lot_id=LOT_INCOMPLET,
        rush_id=RUSH,
        project_id=PROJET,
        fps_target_exact="18/1",
        pages=[
            fab.page_detectee(1, 0, page_count=3, lot_id=LOT_INCOMPLET,
                              rush_id=RUSH, project_id=PROJET, largeur_px=123),
            fab.page_detectee(2, 2, page_count=3, lot_id=LOT_INCOMPLET,
                              rush_id=RUSH, project_id=PROJET, largeur_px=189),
        ],
        pages_expected=3,
        empreinte=fab.EMPREINTES[1],
        ingest_slug=ingest_slug,
    )


def deux_documents_aux_completudes_differentes(*, ingest_slug=INGEST_SLUG):
    """Les deux documents, dans l'ordre : complet PUIS incomplet (cible seconde)."""
    return (
        document_du_lot_complet(ingest_slug=ingest_slug),
        document_du_lot_incomplet(ingest_slug=ingest_slug),
    )


def manifest_des_deux_lot():
    """Un manifest qui declare les deux lot detectes, sans aucune sortie.

    Aucun `output_frames_dir`, aucun cardinal reconstruit : la completude ne
    peut donc venir que des documents de detection -- c'est ce qui rend le
    banc capable de mesurer que l'annonce vient bien de la, et de nulle part
    ailleurs.
    """
    return {
        "schema_version": "2.1",
        "project_id": PROJET,
        "rushes": [{"rush_id": RUSH, "source_path": "medias/alpha.mov"}],
        "lots": [
            {"lot_id": LOT_COMPLET, "rush_id": RUSH, "state": "scan",
             "fps_target_exact": "24000/1001", "expected_frame_count": 8},
            {"lot_id": LOT_INCOMPLET, "rush_id": RUSH, "state": "scan",
             "fps_target_exact": "18/1", "expected_frame_count": 12},
        ],
    }


# ---------------------------------------------------------------------------
# Ecriture sur disque : le banc lit ce que le coeur ecrirait, jamais moins
# ---------------------------------------------------------------------------


def ecrire_les_documents(project_dir: Path, documents, *,
                         ingest_slug=INGEST_SLUG, noms=None) -> tuple[Path, ...]:
    """Ecrire des documents de detection la ou le coeur les ecrit.

    `scans/<ingest_slug>/detections/<nom>.json`, en forme canonique -- la meme
    que `previz_common.canonical_json` pose. Les noms sont donnes pour que
    l'ordre de lecture soit une propriete du test et non du hasard du systeme
    de fichiers.
    """
    project_dir = Path(project_dir)
    dossier = (project_dir / "scans" / ingest_slug
               / scan_detect.DETECTIONS_DIRNAME)
    dossier.mkdir(parents=True, exist_ok=True)
    if noms is None:
        noms = [f"detect-2026082512000{indice}Z" for indice in range(len(documents))]
    chemins = []
    for nom, document in zip(noms, documents):
        chemin = dossier / f"{nom}.json"
        chemin.write_text(
            previz_common.canonical_json(document), encoding="utf-8")
        chemins.append(chemin)
    return tuple(chemins)


def relire(documents):
    """Relire des documents par le lecteur NORMATIF de 5.26.

    Une fixture qui ne serait pas un document complet echoue ici, bruyamment.
    """
    return tuple(scan_previz.scan_previz_from_json_dict(d) for d in documents)


# ---------------------------------------------------------------------------
# Le rapport de tri : le reliquat se LIT, il ne se recompose jamais
# ---------------------------------------------------------------------------


def rapport_de_tri_avec_reliquat(*, ingest_slug=INGEST_SLUG):
    """Un rapport de tri REEL : un lot range, **une** page au reliquat.

    La page au reliquat est la **troisieme** lue (`read_rank=2`) et porte le
    motif `RELIQUAT_QR_MUET` du vocabulaire ferme de 5.24 -- lu de la, jamais
    recompose ici.
    """
    payload_une = {"project_id": PROJET, "rush_id": RUSH, "lot_id": LOT_COMPLET,
                   "page_index": 0, "page_count": 2}
    payload_deux = {"project_id": PROJET, "rush_id": RUSH, "lot_id": LOT_COMPLET,
                    "page_index": 1, "page_count": 2}
    lot = scan_sorting.LotTrie(
        project_id=PROJET, rush_id=RUSH, lot_id=LOT_COMPLET,
        pages=(
            scan_sorting.PageRangee(
                read_rank=0,
                locator=scan_sorting.Localisateur("scans/vrac/page_01.tiff"),
                payload=payload_une),
            scan_sorting.PageRangee(
                read_rank=1,
                locator=scan_sorting.Localisateur("scans/vrac/page_02.tiff"),
                payload=payload_deux),
        ),
    )
    partition = scan_sorting.PartitionDeVrac(
        lots=(lot,),
        reliquat=(
            scan_sorting.EntreeDeReliquat(
                read_rank=2,
                locator=scan_sorting.Localisateur("scans/vrac/page_03.tiff"),
                motif=scan_sorting.RELIQUAT_QR_MUET,
                detail=None),
        ),
    )
    return scan_sorting.RapportDeTri(
        ingest_slug=ingest_slug, project_id=PROJET, partition=partition)


def ecrire_le_rapport_de_tri(project_dir: Path, rapport) -> Path:
    """Ecrire un rapport de tri la ou 5.24 l'ecrit : `scans/<slug>/tri.json`.

    **Ecriture ATOMIQUE, et c'est la moitie (b) du finding F13** (revue de
    vague 3). Cette fabrique ecrivait par `write_text` nu. Un `write_text`
    tronque le fichier avant de le remplir : un lecteur qui tombe dans cette
    fenetre lit **zero octet**, et c'est exactement le symptome que la couche 1
    a reproduit -- `json.decoder.JSONDecodeError: Expecting value: line 1
    column 1 (char 0)` sur `charger_le_rapport_de_tri`, a 7-10 % des suites GUI
    completes.

    On emploie donc la fonction du module de production
    (`scan_detect.ecrire_document_json_atomiquement`) plutot qu'une seconde
    ecriture maison : une fabrique qui ecrit autrement que la production
    fabrique un regime que la production ne connait pas, et c'est ce regime-la
    qui a fait rougir un banc.
    """
    chemin = (Path(project_dir) / "scans" / rapport.ingest_slug
              / scan_detect.TRI_DOCUMENT_FILENAME)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    scan_detect.ecrire_document_json_atomiquement(
        chemin,
        previz_common.canonical_json(scan_sorting.rapport_to_json_dict(rapport)))
    return chemin


# ---------------------------------------------------------------------------
# Les issues de detection : de VRAIS ScanDetectOutcome
# ---------------------------------------------------------------------------


class RapportD_IngestionFactice:
    """Le minimum qu'un `ScanDetectOutcome` porte de son rapport d'ingestion.

    Trois attributs seulement, ceux que les consommateurs de la GUI lisent.
    Ce n'est PAS une reimplementation de `scan_ingest.ScanIngestReport` : le
    banc de coeur (`tests/unit/test_scan_detect_noyau.py`) mesure le vrai
    producteur, celui-ci ne sert qu'a fabriquer une issue sans peindre de
    planche.
    """

    def __init__(self, ingest_slug=INGEST_SLUG, pages=(), scans_dir=None):
        self.ingest_slug = ingest_slug
        self.pages = tuple(pages)
        self.scans_dir = scans_dir or f"scans/{ingest_slug}"


def issue(documents=(), *, ingest_slug=INGEST_SLUG, pages_identifiees=0,
          motif_d_arret=None, partition=None, rapport_de_tri=None,
          rapport_d_ingestion=None):
    """Un vrai `ScanDetectOutcome`, celui que `run_scan_detect` rendrait."""
    return scan_detect.ScanDetectOutcome(
        report=RapportD_IngestionFactice(ingest_slug=ingest_slug),
        rapport_d_ingestion=rapport_d_ingestion or Path("ingest.json"),
        documents=tuple(documents),
        pages_identifiees=pages_identifiees,
        motif_d_arret=motif_d_arret,
        partition=partition,
        rapport_de_tri=rapport_de_tri,
    )


# ---------------------------------------------------------------------------
# Payloads QR reels : le conflit inter-projets se mesure sur le VRAI refus
# ---------------------------------------------------------------------------


def payload_de_planche(*, project_id=PROJET, page_index=0, **surcharges):
    """Un payload QR **reel**, valide par `io.payload`, jamais bricole.

    `project_id` est le seul champ qu'on fait varier pour l'AC 6 : une planche
    d'un AUTRE projet deposee dans le projet ouvert est le conflit reel que
    `check_scan_conflicts` refuse (`EPIC7-ARB-60`).
    """
    return _payloads.make_payload(
        page_index=page_index, project_id=project_id,
        rush_id=RUSH, lot_id=LOT_COMPLET, **surcharges)


# ---------------------------------------------------------------------------
# Fonctions de detection injectables : de VRAIS documents, de VRAIS refus
# ---------------------------------------------------------------------------


def detection_qui_ecrit(documents, *, rapport=None, noms=None,
                        ingest_slug=INGEST_SLUG):
    """Un appelable qui ecrit ces documents et rend l'issue correspondante.

    C'est la couture de l'atelier Scan : le defaut est la vraie fonction du
    coeur (`scan_detect.run_scan_detect`), et le banc y substitue ceci --
    lequel ecrit de VRAIS documents `scan_previz` a l'endroit ou le coeur les
    ecrit, puis rend un VRAI `ScanDetectOutcome`. Rien n'est simule du contrat.

    L'appelable rendu porte `appels` : la liste des couples
    `(scan_path, remplacer_les_detections)` recus, dans l'ordre. C'est ce qui
    rend `EPIC7-ARB-90` mesurable **au point d'appel du coeur** -- un test qui
    se contenterait de compter les cartes ne verrait pas si l'ecrasement a
    ete demande.
    """

    def detecter(project_dir, scan_path, dpi,
                 remplacer_les_detections=False):
        detecter.appels.append((scan_path, remplacer_les_detections))
        chemins = ecrire_les_documents(
            project_dir, documents, noms=noms, ingest_slug=ingest_slug)
        chemin_du_rapport = None
        if rapport is not None:
            chemin_du_rapport = ecrire_le_rapport_de_tri(project_dir, rapport)
        return issue(
            chemins,
            ingest_slug=ingest_slug,
            pages_identifiees=sum(len(d["pages"]) for d in documents),
            rapport_de_tri=chemin_du_rapport,
        )

    detecter.appels = []
    return detecter
