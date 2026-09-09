# -*- coding: utf-8 -*-
"""Story 11.5, lot D -- le rapport de detection et ses issues (AC 6).

Ce banc mesure `tui/atelier_scan_rapport.py`, et **lui seul**. Les autres lots
du Scan ont chacun le leur : « aucun lot ne partage un fichier de banc avec un
autre » -- ni `git add -N` ni `git commit -- <chemins>` ne protegent a
l'interieur d'un fichier partage, defaut paye trois fois sur ce depot.

**Trois regles de mesure heritees, et elles commandent la forme des fabriques :**

1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte** (CLAUDE.md, point 2 bis). Les deux boucles de ce module sont **les
   lots** et **les pages** : les deux fabriques placent donc leur cible en
   deuxieme position sur trois ;
2. **la position se verifie sur la liste que le code PARCOURT**, jamais sur
   celle que la fabrique croit ecrire. C'est le finding le plus grave de la
   revue de la vague 3 -- sur la 11.4b, une fixture croyait respecter le point
   2 bis alors que l'ordre de la liste iteree n'etait pas celui des
   `page_index`, et trois mutants `continue` -> `break` y ont survecu. Le banc
   assert donc d'abord sur `_grouper_par_lot(...)` et sur `document.pages` ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « Cette issue est presente » ne mesure rien ; « l'ensemble des issues est
   **exactement** {...} » mesure l'ensemble ET son unicite.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import (
    qr_codes,
    scan_detect,
    scan_detection,
    scan_previz,
    scan_sorting,
)
from mixed_media_utility.tui import atelier_scan_rapport as rapport_scan
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.panneau import PanneauMalForme

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le paquet mesure, pour les frontieres negatives.
DOSSIER_TUI = Path(_SRC) / "mixed_media_utility" / "tui"

# ---------------------------------------------------------------------------
# Fabriques. Aucune ne produit un element unique, aucune ne remplit une
# collection d'une valeur uniforme.
# ---------------------------------------------------------------------------


def zone(slot_index: int, *, mire: bool = False) -> scan_previz.PrevizFrameZone:
    """Une zone de decoupe. Ses mesures **different** d'une zone a l'autre.

    Un remplissage uniforme rendrait invisible toute permutation : c'est le
    mutant `M33` de la story 5.6, ou l'appariement positionnel entre les
    emplacements d'une page et ses frames etait inverse pendant que 165 tests
    restaient verts.

    Une **mire** ne se rencontre que sur un document deja reconstruit : le
    drapeau `synthetic` accompagne un chemin de frame, « ni plus ni moins »
    (`scan_previz.PrevizFrameZone`), et son motif appartient au vocabulaire
    ferme de 5.6.
    """
    decalage = float(slot_index)
    supplement = {}
    if mire:
        supplement = {
            "frame_path_relative": f"output-frames/lot/frame_{slot_index:03d}.tiff",
            "synthetic": True,
            "synthetic_reason": "frame_crop_failed",
        }
    return scan_previz.PrevizFrameZone(
        slot_index=slot_index,
        frame_timecode=f"00:00:0{slot_index % 10}:00",
        zone_name=f"zone_{slot_index}",
        zone_x_mm=10.0 + decalage, zone_y_mm=20.0 + decalage,
        zone_w_mm=30.0 + decalage, zone_h_mm=40.0 + decalage,
        crop_x_mm=11.0 + decalage, crop_y_mm=21.0 + decalage,
        crop_w_mm=29.0 + decalage, crop_h_mm=39.0 + decalage,
        crop_x_px=100 + slot_index, crop_y_px=200 + slot_index,
        crop_w_px=300 + slot_index, crop_h_px=400 + slot_index,
        **supplement,
    )


def page(read_rank: int, *, page_index: int | None, page_count: int | None,
         lot_id: str = "lot_25fps", fichier: str | None = None,
         qr_status: str = qr_codes.DECODE_OK, muette: bool = False,
         frames: int = 2, mires: int = 0,
         refusal_code: str | None = None) -> scan_previz.ScanPrevizPage:
    """Une page de document. **Muette** = lue, mais dont le QR n'a rien livre.

    Une page muette n'a ni payload, ni zone de decoupe : `scan_detect` n'y
    construit aucun plan, elle « sort du document sans zone ». Ne pas lui en
    donner est ce qui fait que le compte de frames du panneau est le compte
    **reel** -- celui qui sera ecrit -- et non un attendu.
    """
    fichier = fichier or f"scans/pile/planche_{read_rank:02d}.tiff"
    if muette:
        frames, page_index = 0, None
    zones = tuple(
        zone(rang, mire=rang < mires) for rang in range(frames))
    payload = None if muette else {
        "project_id": "projet_demo", "rush_id": "rush_a", "lot_id": lot_id,
        "page_index": page_index, "page_count": page_count,
        "template_id": "T1", "gamut_map_id": "G1",
    }
    return scan_previz.ScanPrevizPage(
        read_rank=read_rank,
        page_index=page_index,
        page_count=page_count,
        status=scan_detection.PAGE_OK,
        qr_status=qr_status,
        refusal_reason=None,
        source_path_relative=fichier,
        source_page_index=None,
        scan_input_format="tiff",
        source_bit_depth=16,
        width_px=4960 + read_rank,
        height_px=7016 + read_rank,
        channels=3,
        decoded_project_id=None if muette else "projet_demo",
        decoded_rush_id=None if muette else "rush_a",
        decoded_lot_id=None if muette else lot_id,
        decoded_gamut_map_id=None if muette else "G1",
        template_id=None if muette else "T1",
        template_source=None if muette else "qr",
        page_size_px=None,
        homography=None,
        scale=None,
        corner_markers=(),
        foreign_markers=(),
        frame_zones=zones,
        calibration=None,
        warnings=(),
        payload=payload,
        source_digest=f"digest-{read_rank}",
        refusal_code=refusal_code,
    )


def document(lot_id: str, pages, *,
             pages_expected: int | None = None) -> scan_previz.ScanPreviz:
    """Un document de detection, en regime `detected`.

    Les cardinaux de frames y valent `None` **par contrat du coeur** :
    `scan_previz._state_counters` les refuse en regime `detected`, « aucune
    frame n'est encore ecrite ». C'est ce qui oblige le panneau a lire son
    attendu de frames ailleurs -- au manifeste -- ou a ne rien montrer.
    """
    return scan_previz.ScanPreviz(
        previz_schema_version="1.0",
        kind=scan_previz.SCAN_PREVIZ_KIND,
        state=scan_previz.SCAN_PREVIZ_STATE_DETECTED,
        generated_at_utc="2026-08-31T15:02:00Z",
        subject=scan_previz.ScanPrevizSubject(
            project_id="projet_demo",
            rush_id="rush_a",
            lot_id=lot_id,
            ingest_slug=f"slug_{lot_id}",
            template_id="T1",
            gamut_map_id="G1",
            fps_target_exact="25",
            target_colorspace=None,
            patch_preset_id=None,
            scan_dpi_declared=600,
            scan_dpi_detection=600,
            scans_dir_relative=f"scans/slug_{lot_id}",
            output_dir_relative=None,
        ),
        counters=scan_previz.ScanPrevizCounters(
            pages_present=len(pages),
            pages_expected=pages_expected,
            frames_written=None,
            frames_expected=None,
            synthetic_frame_count=None,
        ),
        pages=tuple(pages),
        warnings=scan_previz.ScanPrevizWarnings(),
        fingerprints=scan_previz.ScanPrevizFingerprints(
            detection=f"empreinte-{lot_id}"),
    )


#: Les trois lots de la fabrique principale. **L'incomplet est au MILIEU**, et
#: les trois se distinguent par leur nom ET par leurs comptes.
LOT_PREMIER = "lot_25fps"
LOT_INCOMPLET = "lot_12p5"
LOT_DERNIER = "lot_48fps"


def documents_a_trois_lots():
    """Trois lots, l'incomplet **au milieu**, tous distinguables par leurs comptes.

    * `lot_25fps` -- 2 planches sur 2, 5 frames ;
    * `lot_12p5` -- 2 planches sur 3, 3 frames, **et une planche muette** ;
    * `lot_48fps` -- 3 planches sur 3, 9 frames.

    Trois cardinaux differents, trois comptes de frames differents : une
    permutation de deux lots ne peut pas passer inapercue, et un `break` sur le
    lot du milieu ferait disparaitre le troisieme.
    """
    return [
        document(LOT_PREMIER, [
            page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=2),
            page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=3),
        ], pages_expected=2),
        document(LOT_INCOMPLET, [
            page(11, page_index=0, page_count=3, lot_id=LOT_INCOMPLET, frames=2),
            page(12, lot_id=LOT_INCOMPLET, muette=True,
                 qr_status=qr_codes.DECODE_UNREADABLE,
                 fichier="scans/pile/planche_03.tiff",
                 refusal_code="QR_NON_DECODE", page_index=None, page_count=None),
            page(13, page_index=2, page_count=3, lot_id=LOT_INCOMPLET, frames=1),
        ], pages_expected=3),
        document(LOT_DERNIER, [
            page(21, page_index=0, page_count=3, lot_id=LOT_DERNIER, frames=3),
            page(22, page_index=1, page_count=3, lot_id=LOT_DERNIER, frames=3),
            page(23, page_index=2, page_count=3, lot_id=LOT_DERNIER, frames=3),
        ], pages_expected=3),
    ]


def localisateur(nom: str, page_index=None) -> scan_sorting.Localisateur:
    return scan_sorting.Localisateur(source_path=nom, page_index=page_index)


def partition_a_trois_entrees():
    """Trois pages non rattachees, la **completable au milieu**.

    Deux classes disjointes du coeur y sont representees, et c'est voulu : le
    reliquat (« je n'ai pas su te rattacher ») et le hors-perimetre (« tu n'es
    pas ici chez toi »), qui seul porte le projet a utiliser.
    """
    return scan_sorting.PartitionDeVrac(
        lots=(),
        reliquat=(
            scan_sorting.EntreeDeReliquat(
                read_rank=31,
                locator=localisateur("scans/pile/feuille_a.tiff"),
                motif=scan_sorting.RELIQUAT_LOT_INCONNU),
            scan_sorting.EntreeDeReliquat(
                read_rank=32,
                locator=localisateur("scans/pile/planche_07.tiff"),
                motif=scan_sorting.RELIQUAT_QR_MUET),
        ),
        hors_perimetre=(
            scan_sorting.EntreeHorsPerimetre(
                read_rank=33,
                locator=localisateur("scans/pile/etranger.pdf", 4),
                motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
                projet_a_utiliser="autre_projet"),
        ),
    )


def manifeste_a_trois_lots():
    """Un manifeste ou les trois lots portent des attendus **differents**.

    Un manifeste qui donnerait le meme `expected_frame_count` a tous les lots
    rendrait invisible un panneau qui lirait l'attendu du mauvais lot -- c'est
    le mutant `M25` de la story 5.7 sous une autre forme.
    """
    return {"lots": [
        {"lot_id": LOT_PREMIER, "expected_frame_count": 5},
        {"lot_id": LOT_INCOMPLET, "expected_frame_count": 62},
        {"lot_id": LOT_DERNIER, "expected_frame_count": 9},
    ]}


@pytest.fixture
def rapport():
    return rapport_scan.projeter(
        documents_a_trois_lots(),
        partition=partition_a_trois_entrees(),
        manifeste=manifeste_a_trois_lots(),
    )


# ---------------------------------------------------------------------------
# D1 -- la projection, et la position verifiee sur la liste PARCOURUE
# ---------------------------------------------------------------------------


def test_la_fabrique_place_la_cible_au_milieu_de_la_LISTE_QUE_LE_CODE_PARCOURT():
    """La garde de la fabrique elle-meme, et elle vient en premier.

    Le module groupe les documents par lot dans l'ordre de leur venue : la
    liste que ses boucles parcourent est celle que `_grouper_par_lot` rend.
    Verifier le rang de la cible sur la liste ecrite par la fabrique ne
    suffirait pas -- une liste reconstruite ou triee peut placer la cible
    ailleurs, et c'est exactement ce qui a laisse trois mutants survivre sur la
    11.4b.
    """
    documents = documents_a_trois_lots()
    parcourue = [lot_id for lot_id, _ in rapport_scan._grouper_par_lot(documents)]
    assert parcourue == [LOT_PREMIER, LOT_INCOMPLET, LOT_DERNIER]
    assert parcourue[1] == LOT_INCOMPLET, "la cible doit etre au MILIEU"
    assert len(parcourue) == 3, "ni la premiere ni la derniere position"


def test_un_panneau_par_lot_reconnu_dans_l_ordre_des_documents(rapport):
    assert tuple(lot.lot_id for lot in rapport.lots) == (
        LOT_PREMIER, LOT_INCOMPLET, LOT_DERNIER)


def test_les_trois_lots_sont_distinguables_par_leurs_comptes(rapport):
    """Pages trouvees SUR pages attendues, frames SUR frames attendues (AC 6.1).

    L'assertion est une **egalite d'ensemble** : un panneau qui lirait les
    comptes du mauvais lot changerait ce tuple, ce qu'une assertion positive
    sur un seul lot ne verrait pas.
    """
    mesures = tuple(
        (lot.lot_id, lot.pages_trouvees, lot.pages_attendues,
         lot.frames, lot.frames_attendues)
        for lot in rapport.lots)
    assert mesures == (
        (LOT_PREMIER, 2, 2, 5, 5),
        (LOT_INCOMPLET, 2, 3, 3, 62),
        (LOT_DERNIER, 3, 3, 9, 9),
    )


def test_le_lot_DU_MILIEU_est_le_SEUL_incomplet(rapport):
    assert tuple(lot.lot_id for lot in rapport.lots_incomplets) == (LOT_INCOMPLET,)
    assert rapport.complet is False


def test_la_planche_absente_du_lot_du_milieu_est_NOMMEE(rapport):
    """`completude_des_planches` rend les planches manquantes ; on les montre.

    L'ensemble est exact : nommer une planche de plus enverrait l'operateur
    chercher une feuille qui n'a jamais existe.
    """
    incomplet = rapport.lots[1]
    assert incomplet.planches_manquantes == (1,)


def test_les_completudes_des_trois_lots_sont_LUES_du_coeur(rapport):
    assert tuple(lot.completude for lot in rapport.lots) == (
        scan_detect.COMPLETUDE_COMPLET,
        scan_detect.COMPLETUDE_INCOMPLET,
        scan_detect.COMPLETUDE_COMPLET,
    )


def test_le_glyphe_de_chaque_lot_vient_de_la_TABLE_par_sa_cle(rapport):
    """Aucun dessin en dur : la cle, puis la table de `DESIGN.md` section 6."""
    assert tuple(lot.glyphe for lot in rapport.lots) == (
        "complete", "absent", "complete")
    for cle in rapport_scan.GLYPHE_PAR_COMPLETUDE.values():
        assert cle in jetons.GLYPHES and cle in jetons.GLYPHES_ASCII


def test_les_trois_completudes_du_coeur_ont_TOUTES_un_glyphe():
    """Volet symetrique : la table couvre le vocabulaire ferme, exactement."""
    assert set(rapport_scan.GLYPHE_PAR_COMPLETUDE) == set(scan_detect.COMPLETUDES)


def test_deux_documents_du_MEME_lot_font_UN_seul_panneau():
    """Contrat de 5.25 : plusieurs scans de la meme planche s'additionnent.

    Le lot garde le rang de son **premier** document -- il ne remonte pas en
    tete parce qu'il a recu un second scan.
    """
    documents = documents_a_trois_lots()
    documents.append(document(LOT_INCOMPLET, [
        page(14, page_index=1, page_count=3, lot_id=LOT_INCOMPLET, frames=4),
    ], pages_expected=3))
    projete = rapport_scan.projeter(documents, manifeste=manifeste_a_trois_lots())
    assert tuple(lot.lot_id for lot in projete.lots) == (
        LOT_PREMIER, LOT_INCOMPLET, LOT_DERNIER)
    complete = projete.lots[1]
    assert (complete.pages_trouvees, complete.pages_attendues) == (3, 3)
    assert complete.completude == scan_detect.COMPLETUDE_COMPLET
    assert complete.frames == 7


def test_un_attendu_INDETERMINABLE_ne_montre_RIEN_a_sa_place():
    """Jamais `0`, jamais `--`, jamais une valeur devinee (`DESIGN.md` s3).

    Deux sources manquent ensemble ici : le document ne publie aucun cardinal
    de planches et aucune page n'en declare, et le manifeste ne connait pas le
    lot. Les deux attendus valent `None`, et **aucun des deux** ne se replie
    sur un chiffre.
    """
    muet = document("lot_inconnu", [
        page(41, page_index=None, page_count=None, lot_id="lot_inconnu", frames=2),
        page(42, page_index=None, page_count=None, lot_id="lot_inconnu", frames=1),
    ])
    projete = rapport_scan.projeter([muet], manifeste=manifeste_a_trois_lots())
    (lot,) = projete.lots
    assert lot.pages_attendues is None
    assert lot.frames_attendues is None
    assert lot.frames == 3
    assert lot.completude == scan_detect.COMPLETUDE_INCOMPLET


def test_deux_documents_du_meme_lot_qui_se_CONTREDISENT_ne_rendent_aucun_attendu():
    """« Une contradiction ne se lit jamais comme une garantie » (`EPIC5-ARB-32`)."""
    projete = rapport_scan.projeter([
        document(LOT_PREMIER, [
            page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER)],
            pages_expected=2),
        document(LOT_PREMIER, [
            page(2, page_index=1, page_count=4, lot_id=LOT_PREMIER)],
            pages_expected=4),
    ])
    (lot,) = projete.lots
    assert lot.pages_attendues is None


def test_le_manifeste_donne_l_attendu_de_frames_DU_BON_LOT():
    """Un attendu lu sur le premier lot venu serait invisible a fabrique uniforme.

    Les trois lots portent ici trois attendus differents, et la cible est celle
    du milieu : c'est le mutant `M25` de la 5.7 (`_find_lot` rendant le premier
    lot) transpose a la lecture du manifeste.
    """
    projete = rapport_scan.projeter(
        documents_a_trois_lots(), manifeste=manifeste_a_trois_lots())
    assert projete.lots[1].frames_attendues == 62


def test_sans_manifeste_l_attendu_de_frames_est_ABSENT_pas_zero():
    projete = rapport_scan.projeter(documents_a_trois_lots())
    assert [lot.frames_attendues for lot in projete.lots] == [None, None, None]


# ---------------------------------------------------------------------------
# D2 -- les trois issues, le curseur, et le mot retire
# ---------------------------------------------------------------------------


def test_les_issues_d_un_rapport_INCOMPLET_sont_EXACTEMENT_ces_trois(rapport):
    issues = rapport_scan.issues_du_rapport(rapport)
    assert tuple(i.cle for i in issues.choix.issues) == (
        rapport_scan.ISSUE_ECRIRE,
        rapport_scan.ISSUE_COMPLETER,
        rapport_scan.ISSUE_ANNULER,
    )
    assert tuple(i.libelle for i in issues.choix.issues) == (
        "Écrire quand même", "Compléter le QR", "Annuler")


def test_la_SECONDE_issue_est_COMPLETER_LE_QR_et_non_le_mot_retire(rapport):
    """`EPIC11-ARB-29`, verbatim : « Ce n'est plus "rescanner" »."""
    issues = rapport_scan.issues_du_rapport(rapport)
    assert issues.choix.issues[1].libelle == rapport_scan.LIBELLE_COMPLETER_LE_QR


def test_AUCUNE_issue_n_est_preselectionnee(rapport):
    """`EPIC11-ARB-7`, et cela ne se reecrit pas : c'est un invariant du type."""
    issues = rapport_scan.issues_du_rapport(rapport)
    assert issues.choix.retenue is None


def test_le_curseur_AU_MONTAGE_est_sur_une_issue_QUI_N_ECRIT_PAS(rapport):
    """AC 6.4. Le rang n'est pas recopie : il est confronte a l'issue elle-meme."""
    issues = rapport_scan.issues_du_rapport(rapport)
    sous_le_curseur = issues.choix.issues[issues.choix.curseur]
    assert sous_le_curseur.ecrit is False
    assert sous_le_curseur.cle == rapport_scan.ISSUE_COMPLETER
    assert issues.choix.action_qui_ecrit.cle == rapport_scan.ISSUE_ECRIRE


def test_UNE_SEULE_issue_ecrit_sur_un_rapport_incomplet(rapport):
    issues = rapport_scan.issues_du_rapport(rapport)
    assert [i.cle for i in issues.choix.issues if i.ecrit] == [
        rapport_scan.ISSUE_ECRIRE]


def test_aucune_frappe_UNIQUE_depuis_le_montage_ne_declenche_une_ECRITURE(rapport):
    """`EPIC11-ARB-45`, forme reduite de `ARB-7` : valider retient le curseur."""
    issues = rapport_scan.issues_du_rapport(rapport)
    retenue = issues.choix.valider()
    assert retenue.ecrit is False


def test_les_suites_d_un_rapport_COMPLET_sont_EXACTEMENT_ces_trois():
    """`EPIC11-ARB-101` note 9 : « Voir le detail d'un lot » est **retiree**.

    Verbatim d'Egan : « Que se passe-t-il quand on regarde le detail d'un lot ?
    Si rien n'existe on retire cette option. » Mesure faite le 2026-08-31 :
    aucun ecran de detail de lot n'existe dans les maquettes du temps 1.
    """
    documents = [document(LOT_PREMIER, [
        page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=2),
        page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=3),
    ], pages_expected=2), document(LOT_DERNIER, [
        page(21, page_index=0, page_count=1, lot_id=LOT_DERNIER, frames=4),
    ], pages_expected=1)]
    complet = rapport_scan.projeter(documents)
    assert complet.complet is True
    issues = rapport_scan.issues_du_rapport(complet)
    assert tuple(i.cle for i in issues.choix.issues) == (
        rapport_scan.ISSUE_ECRIRE,
        rapport_scan.ISSUE_REPRENDRE,
        rapport_scan.ISSUE_ANNULER,
    )
    assert issues.choix.issues[0].libelle == "Écrire les frames de ces 2 lots"
    assert issues.choix.issues[issues.choix.curseur].ecrit is False


def test_un_rapport_complet_a_UN_seul_lot_dit_ce_lot_au_singulier():
    complet = rapport_scan.projeter([document(LOT_PREMIER, [
        page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=2),
        page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=3),
    ], pages_expected=2)])
    issues = rapport_scan.issues_du_rapport(complet)
    assert issues.choix.issues[0].libelle == "Écrire les frames de ce lot"


def test_chaque_issue_porte_A_COTE_ce_qu_elle_fait_avec_son_chiffre_REEL(rapport):
    """AC 6.5 : « le compte reel, jamais le compte attendu ».

    Le lot du milieu porte 3 frames reelles pour 62 attendues au manifeste :
    l'a-cote doit dire 3, et le banc mesure aussi que 62 **n'y est pas**.
    """
    issues = rapport_scan.issues_du_rapport(rapport)
    assert issues.a_cote[rapport_scan.ISSUE_ECRIRE] == (
        f"{LOT_INCOMPLET} sera écrit incomplet, 3 frames")
    assert "62" not in issues.a_cote[rapport_scan.ISSUE_ECRIRE]
    assert issues.a_cote[rapport_scan.ISSUE_COMPLETER] == (
        "saisir ce que planche_03 n'a pas livré")
    assert issues.a_cote[rapport_scan.ISSUE_ANNULER] == "ne rien écrire"


def test_l_ensemble_des_a_cote_couvre_EXACTEMENT_les_issues(rapport):
    """Aucune issue muette, aucun a-cote orphelin -- dans les deux regimes."""
    for construit in (rapport, rapport_scan.projeter(
            [documents_a_trois_lots()[0]])):
        issues = rapport_scan.issues_du_rapport(construit)
        assert set(issues.a_cote) == {i.cle for i in issues.choix.issues}


def test_l_a_cote_est_indexe_PAR_CLE_donc_une_permutation_ne_le_deplace_pas(rapport):
    """« Deux listes qui doivent rester en correspondance » -- il n'y en a qu'une.

    Le curseur est deplace, l'ordre de lecture change : les a-cote suivent leur
    issue, jamais un rang.
    """
    issues = rapport_scan.issues_du_rapport(rapport)
    avant = dict(issues.a_cote)
    issues.choix.viser(rapport_scan.ISSUE_ANNULER)
    lignes = issues.lignes()
    assert lignes[2].endswith("Annuler  ne rien écrire")
    assert dict(issues.a_cote) == avant


@pytest.mark.parametrize("frames_reelles, accord", [
    (0, "0 frame"),
    (1, "1 frame"),
    (2, "2 frames"),
])
def test_l_a_cote_ACCORDE_frame_des_la_PREMIERE(frames_reelles, accord):
    """La bascule singulier/pluriel de `_accorder`, et aucun test ne la jouait.

    Les quatre valeurs que les bancs faisaient passer par cette fonction etaient
    **3, 5, 9 et 17** : la branche du singulier -- sa seule raison d'etre --
    n'etait jouee par aucun des 3298 tests de `tests/unit/tui/`. Un banc qui ne
    mesure que le pluriel mesure une concatenation, pas un accord, et le mutant
    `valeur <= 1` -> `valeur < 1` y survit.

    **`1` n'est pas un cardinal invente pour le test** :
    `page_templates.known_template_ids()` rend les cardinaux composables
    `[1, 2, 3, 4, 6, 8]`, et `1` en fait partie. Un lot d'une planche a une
    image, incomplet, fait rendre `1 frame` a l'a-cote de « Écrire quand même »
    -- sur l'ecran de jugement le plus lu de l'atelier.

    Les trois valeurs encadrent la bascule **des deux cotes** : `0` et `1` au
    singulier (l'accord francais compte `0` comme un singulier), `2` au pluriel.

    La forme des documents ne change pas pour autant : **trois lots, le seul
    incomplet au MILIEU**, et trois comptes de planches distincts. C'est sur
    `rapport.lots_incomplets` -- la liste que `_issues_du_rapport_incomplet`
    parcourt -- que le rang de la cible est verifie, jamais sur celle que cette
    fabrique croit ecrire.
    """
    documents = [
        document(LOT_PREMIER, [
            page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=2),
            page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=3),
        ], pages_expected=2),
        # Le lot du MILIEU, et le seul incomplet : une planche sur deux, et
        # `frames_reelles` image(s) dessus.
        document(LOT_INCOMPLET, [
            page(11, page_index=0, page_count=2, lot_id=LOT_INCOMPLET,
                 frames=frames_reelles),
        ], pages_expected=2),
        document(LOT_DERNIER, [
            page(21, page_index=0, page_count=3, lot_id=LOT_DERNIER, frames=3),
            page(22, page_index=1, page_count=3, lot_id=LOT_DERNIER, frames=3),
            page(23, page_index=2, page_count=3, lot_id=LOT_DERNIER, frames=3),
        ], pages_expected=3),
    ]
    projete = rapport_scan.projeter(documents)
    incomplets = projete.lots_incomplets
    assert [lot.lot_id for lot in incomplets] == [LOT_INCOMPLET]
    assert [lot.lot_id for lot in projete.lots].index(LOT_INCOMPLET) == 1
    assert incomplets[0].frames == frames_reelles

    issues = rapport_scan.issues_du_rapport(projete)
    assert issues.a_cote[rapport_scan.ISSUE_ECRIRE] == (
        f"{LOT_INCOMPLET} sera écrit incomplet, {accord}")


def test_plusieurs_lots_incomplets_additionnent_leurs_frames_REELLES():
    """« Tous les lots incomplets : l'intitule dit "les 2 lots incomplets" »."""
    documents = [
        document(LOT_PREMIER, [
            page(1, page_index=0, page_count=3, lot_id=LOT_PREMIER, frames=2)],
            pages_expected=3),
        document(LOT_INCOMPLET, [
            page(11, page_index=0, page_count=4, lot_id=LOT_INCOMPLET, frames=3),
            page(12, lot_id=LOT_INCOMPLET, muette=True, page_index=None,
                 page_count=None, qr_status=qr_codes.DECODE_NO_SYMBOL)],
            pages_expected=4),
    ]
    projete = rapport_scan.projeter(documents)
    issues = rapport_scan.issues_du_rapport(projete)
    assert issues.a_cote[rapport_scan.ISSUE_ECRIRE] == (
        "2 lots seront écrits incomplets, 5 frames")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_lignes_passent_par_le_rendu_de_ChoixExclusif(ascii_seul, rapport):
    """Un seul curseur a l'ecran, et il est pose par le modele, pas par ce module."""
    issues = rapport_scan.issues_du_rapport(rapport)
    lignes = issues.lignes(ascii_seul)
    marque = jetons.glyphes(ascii_seul)["curseur"]
    portees = [ligne for ligne in lignes if ligne.startswith(marque)]
    assert len(portees) == 1
    assert portees[0].startswith(f"{marque} {rapport_scan.LIBELLE_COMPLETER_LE_QR}")
    assert len(lignes) == len(issues.choix.issues)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_d_issue_ne_porte_de_GLYPHE_DE_RADIO(ascii_seul, rapport):
    """`EPIC11-ARB-45` : « les glyphes de radio disparaissent du rendu ».

    Le rendu est celui de `ChoixExclusif`, et ce banc mesure qu'aucune chaine
    de ce module ne les y remet.
    """
    table = jetons.glyphes(ascii_seul)
    issues = rapport_scan.issues_du_rapport(rapport)
    for ligne in issues.lignes(ascii_seul):
        assert table["exclusif-libre"] not in ligne
        assert table["exclusif-retenu"] not in ligne


# ---------------------------------------------------------------------------
# D2 -- la frontiere negative du mot retire, et son volet symetrique
# ---------------------------------------------------------------------------


def modules_du_scan() -> list[Path]:
    """Les modules TUI de l'atelier Scan, tels qu'ils existent au moment du banc.

    Le motif est large a dessein : les autres lots de la 11.5 posent leurs
    propres modules, et la frontiere doit les couvrir sans qu'on ait a la
    reecrire a chaque arrivee.
    """
    return sorted(DOSSIER_TUI.glob("*scan*.py"))


def test_le_mot_retire_par_ARB_29_ne_parait_NULLE_PART_dans_les_modules_du_scan():
    """Comptage a **zero** (AC 6.3).

    Le mot est construit ici plutot qu'ecrit, pour que ce banc lui-meme ne soit
    pas la seule occurrence du depot a le porter.
    """
    retire = "re" + "scann"
    fautifs = {
        chemin.name: len(re.findall(retire, chemin.read_text(encoding="utf-8"),
                                    flags=re.IGNORECASE))
        for chemin in modules_du_scan()
    }
    assert {nom: compte for nom, compte in fautifs.items() if compte} == {}


def test_volet_symetrique_la_frontiere_du_mot_retire_MESURE_bien_quelque_chose():
    """Un banc qui balaie zero fichier rend zero occurrence sans rien mesurer.

    Deux garanties : le balayage voit au moins un module, et il lit vraiment le
    texte de ces modules -- ce que prouve la presence du libelle de remplacement.
    """
    modules = modules_du_scan()
    assert modules, "aucun module de Scan balaye : la frontiere ne mesure rien"
    textes = [chemin.read_text(encoding="utf-8") for chemin in modules]
    assert any(rapport_scan.LIBELLE_COMPLETER_LE_QR in texte for texte in textes)


# ---------------------------------------------------------------------------
# D3 -- la file « en attente de lecture », nommee fichier par fichier
# ---------------------------------------------------------------------------


def test_la_file_nomme_CHAQUE_fichier_jamais_un_compte_seul(rapport):
    assert tuple(entree.fichier for entree in rapport.en_attente) == (
        "scans/pile/feuille_a.tiff",
        "scans/pile/planche_07.tiff",
        "scans/pile/etranger.pdf p.4",
    )
    assert len(rapport.lignes_en_attente()) == 3


def test_chaque_ligne_de_la_file_porte_son_MOTIF_verbatim_du_coeur(rapport):
    lignes = rapport.lignes_en_attente()
    assert lignes[0] == (
        f"scans/pile/feuille_a.tiff  {scan_sorting.RELIQUAT_LOT_INCONNU}")
    assert lignes[1] == (
        f"scans/pile/planche_07.tiff  {scan_sorting.RELIQUAT_QR_MUET}")


def test_seul_le_HORS_PERIMETRE_porte_le_projet_a_utiliser(rapport):
    """`EPIC5-ARB-105` : « l'operateur ne doit pas avoir a le deviner ».

    L'ensemble des entrees qui le portent est **exactement** celle du hors
    perimetre : une entree de reliquat qui en porterait un enverrait chercher
    au mauvais endroit.
    """
    portent = {entree.fichier for entree in rapport.en_attente
               if entree.projet_a_utiliser}
    assert portent == {"scans/pile/etranger.pdf p.4"}
    assert rapport.en_attente[2].projet_a_utiliser == "autre_projet"
    assert rapport.lignes_en_attente()[2].endswith("autre_projet")


def test_deux_pages_du_MEME_PDF_ne_portent_pas_le_meme_nom_dans_la_file():
    """Sans l'index de page, deux pages d'un PDF seraient indistinguables."""
    partition = scan_sorting.PartitionDeVrac(reliquat=(
        scan_sorting.EntreeDeReliquat(
            read_rank=1, locator=localisateur("scans/pile/pile.pdf", 2),
            motif=scan_sorting.RELIQUAT_QR_MUET),
        scan_sorting.EntreeDeReliquat(
            read_rank=2, locator=localisateur("scans/pile/pile.pdf", 5),
            motif=scan_sorting.RELIQUAT_QR_MUET),
    ))
    file = rapport_scan.file_en_attente(partition)
    assert {entree.fichier for entree in file} == {
        "scans/pile/pile.pdf p.2", "scans/pile/pile.pdf p.5"}


def test_une_file_VIDE_le_dit_plutot_que_de_rendre_une_ligne_vide():
    projete = rapport_scan.projeter(
        documents_a_trois_lots(), partition=scan_sorting.PartitionDeVrac())
    assert projete.en_attente == ()
    assert projete.lignes_en_attente() == [
        rapport_scan.AUCUN_FICHIER_EN_ATTENTE]


def test_sans_partition_la_file_est_vide_et_ne_leve_pas():
    """Regime `--lot-slug` : il n'y a pas de tri, donc pas de reliquat."""
    assert rapport_scan.file_en_attente(None) == ()


def test_la_cible_completable_de_la_file_est_AU_MILIEU_de_la_liste_parcourue():
    """Garde de la fabrique de file : trois entrees, la cible en deuxieme.

    `pages_completables` parcourt `en_attente` dans l'ordre : une cible en
    premiere ou en derniere position rendrait indiscernables un `find` fautif
    et une terminaison de boucle fautive.
    """
    file = rapport_scan.file_en_attente(partition_a_trois_entrees())
    completables = [rang for rang, entree in enumerate(file) if entree.completable]
    assert completables == [1]
    assert len(file) == 3


# ---------------------------------------------------------------------------
# D4 -- mires contre frames, page absente contre QR illisible
# ---------------------------------------------------------------------------


def test_un_lot_complet_PORTANT_DES_MIRES_est_le_triangle_et_non_le_rond():
    """AC 6.2. « Le fichier existe, l'image du film non » -- ce n'est pas complet."""
    avec_mires = document(LOT_PREMIER, [
        page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=3, mires=2),
        page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=4),
    ], pages_expected=2)
    (lot,) = rapport_scan.projeter([avec_mires]).lots
    assert lot.completude == scan_detect.COMPLETUDE_COMPLET_AVEC_MIRES
    assert lot.glyphe == "substitute"
    assert jetons.GLYPHES[lot.glyphe] == "▲"
    assert lot.porte_des_mires is True


def test_une_MIRE_n_est_pas_une_FRAME_et_le_compte_de_mires_est_dit():
    """Les deux comptes sont distincts, et le second ne se deduit pas du premier."""
    avec_mires = document(LOT_PREMIER, [
        page(1, page_index=0, page_count=2, lot_id=LOT_PREMIER, frames=3, mires=2),
        page(2, page_index=1, page_count=2, lot_id=LOT_PREMIER, frames=4, mires=1),
    ], pages_expected=2)
    (lot,) = rapport_scan.projeter([avec_mires]).lots
    assert (lot.frames, lot.mires) == (7, 3)


def test_un_lot_SANS_mire_en_compte_zero_et_reste_le_rond(rapport):
    """Volet symetrique : `synthetic` vaut `None` en regime detecte, pas `False`."""
    premier = rapport.lots[0]
    assert (premier.mires, premier.glyphe) == (0, "complete")
    assert premier.porte_des_mires is False


def test_COMPLETER_LE_QR_est_proposee_sur_une_page_LUE_dont_le_QR_a_echoue(rapport):
    """AC 6.7, premiere moitie."""
    issues = rapport_scan.issues_du_rapport(rapport)
    assert rapport_scan.ISSUE_COMPLETER in {
        i.cle for i in issues.choix.issues}
    # Les DEUX provenances, dans l'ordre : la muette rattachee au lot, puis
    # celle que le tri a laissee au reliquat.
    assert tuple(m.fichier for m in rapport.pages_completables) == (
        "scans/pile/planche_03.tiff", "scans/pile/planche_07.tiff")


def test_COMPLETER_LE_QR_n_est_PAS_proposee_quand_le_manque_est_une_page_ABSENTE():
    """AC 6.7, seconde moitie, et c'est `EPIC11-ARB-29` verbatim.

    « Une page **absente** (jamais scannee) ne se complete pas : il n'y a rien a
    lire. » Le lot est incomplet -- il lui manque la planche 2 --, aucune page
    lue n'a de QR muet, et l'ensemble des issues est **exactement** celui de la
    reprise. L'egalite est ce qui mesure l'absence : une assertion positive sur
    les deux autres issues laisserait passer « Compléter le QR » en plus.
    """
    absente = document(LOT_INCOMPLET, [
        page(11, page_index=0, page_count=3, lot_id=LOT_INCOMPLET, frames=2),
        page(12, page_index=1, page_count=3, lot_id=LOT_INCOMPLET, frames=3),
    ], pages_expected=3)
    projete = rapport_scan.projeter([absente])
    (lot,) = projete.lots
    assert lot.completude == scan_detect.COMPLETUDE_INCOMPLET
    assert lot.planches_manquantes == (2,)
    assert projete.pages_completables == ()

    issues = rapport_scan.issues_du_rapport(projete)
    assert tuple(i.cle for i in issues.choix.issues) == (
        rapport_scan.ISSUE_ECRIRE,
        rapport_scan.ISSUE_REPRENDRE,
        rapport_scan.ISSUE_ANNULER,
    )
    assert issues.choix.issues[issues.choix.curseur].ecrit is False


@pytest.mark.parametrize("qr_status", [
    pytest.param(qr_codes.DECODE_NO_SYMBOL, id="symbole-absent"),
    pytest.param(qr_codes.DECODE_UNREADABLE, id="symbole-illisible"),
    pytest.param(qr_codes.DECODE_MULTIPLE, id="plusieurs-symboles"),
])
def test_les_trois_QR_MUETS_rendent_la_page_completable(qr_status):
    projete = rapport_scan.projeter([document(LOT_INCOMPLET, [
        page(11, page_index=0, page_count=3, lot_id=LOT_INCOMPLET, frames=2),
        page(12, lot_id=LOT_INCOMPLET, muette=True, qr_status=qr_status,
             page_index=None, page_count=None),
        page(13, page_index=1, page_count=3, lot_id=LOT_INCOMPLET, frames=1),
    ], pages_expected=3)])
    assert len(projete.pages_completables) == 1


def test_une_page_refusee_AVANT_que_le_QR_soit_cherche_n_est_PAS_completable():
    """`QR_NOT_ATTEMPTED` : « un QR qui n'a jamais ete cherche ».

    Le fichier n'a pas su etre ouvert. Proposer d'y recopier ce qui est imprime
    sur la planche enverrait l'operateur lire une image que rien n'affiche.
    """
    projete = rapport_scan.projeter([document(LOT_INCOMPLET, [
        page(11, page_index=0, page_count=3, lot_id=LOT_INCOMPLET, frames=2),
        page(12, lot_id=LOT_INCOMPLET, muette=True, page_index=None,
             page_count=None, qr_status=scan_detection.QR_NOT_ATTEMPTED),
        page(13, page_index=1, page_count=3, lot_id=LOT_INCOMPLET, frames=1),
    ], pages_expected=3)])
    assert projete.pages_completables == ()
    assert scan_detection.QR_NOT_ATTEMPTED not in rapport_scan.QR_MUETS


def test_les_quatre_statuts_de_QR_du_coeur_sont_partages_SANS_reste():
    """Volet symetrique : la table des muets couvre le vocabulaire ferme.

    Un statut ajoute au coeur sans decision ici ferait rougir : c'est ce qui
    empeche `QR_MUETS` de devenir une liste que plus personne ne relit.
    """
    connus = set(scan_detection.PAGE_QR_STATUSES)
    assert set(rapport_scan.QR_MUETS) < connus
    assert connus - set(rapport_scan.QR_MUETS) == {
        qr_codes.DECODE_OK, scan_detection.QR_NOT_ATTEMPTED}


def test_SEUL_le_motif_de_reliquat_QR_MUET_est_completable():
    """Le vocabulaire ferme du reliquat est balaye **en entier**.

    Une assertion positive sur le seul motif retenu laisserait passer qu'un
    second le devienne. L'egalite mesure l'exception ET son unicite.
    """
    completables = set()
    for motif in scan_sorting.MOTIFS_DE_RELIQUAT + scan_sorting.MOTIFS_HORS_PERIMETRE:
        entree = rapport_scan.EnAttenteDeLecture(
            fichier="scans/pile/f.tiff", motif=motif)
        if entree.completable:
            completables.add(motif)
    assert completables == {scan_sorting.RELIQUAT_QR_MUET}


def test_la_page_muette_du_lot_est_NOMMEE_avec_son_code_verbatim(rapport):
    """Le code de refus enumere de 5.27, jamais « echec » (`DESIGN.md` s9)."""
    incomplet = rapport.lots[1]
    assert tuple((m.read_rank, m.fichier, m.code)
                 for m in incomplet.pages_muettes) == (
        (12, "scans/pile/planche_03.tiff", "QR_NON_DECODE"),)
    assert incomplet.pages_muettes[0].nom_court == "planche_03"
    assert incomplet.pages_muettes[0].lot_id == LOT_INCOMPLET


def test_la_page_muette_du_lot_est_AU_MILIEU_de_la_liste_que_le_code_parcourt():
    """La seconde boucle du module est **les pages d'un document**.

    Trois pages, la muette en deuxieme : une cible en derniere position rendrait
    indiscernable un `continue` -> `break`, qui ferait alors disparaitre la
    troisieme page -- et ses frames avec elle.
    """
    documents = documents_a_trois_lots()
    pages = documents[1].pages
    muettes = [rang for rang, p in enumerate(pages)
               if rapport_scan._est_muette(p)]
    assert muettes == [1]
    assert len(pages) == 3
    # Et le compte de frames du lot porte bien les DEUX autres pages : un
    # `break` sur la muette en perdrait une.
    assert rapport_scan.projeter([documents[1]]).lots[0].frames == 3


def test_un_lot_sans_AUCUNE_page_muette_n_en_declare_aucune(rapport):
    assert rapport.lots[0].pages_muettes == ()
    assert rapport.lots[2].pages_muettes == ()


def test_une_page_qui_porte_un_payload_n_est_JAMAIS_muette_meme_QR_degrade():
    """Les deux conditions de `_est_muette` sont cumulatives, et aucune ne suffit.

    Une planche dont le template vient du manifeste porte un payload avec un
    statut de QR degrade : la completer n'aurait aucun sens, elle a parle.
    """
    lue = page(5, page_index=0, page_count=2, lot_id=LOT_PREMIER,
               qr_status=qr_codes.DECODE_UNREADABLE, frames=2)
    assert lue.payload is not None
    assert rapport_scan._est_muette(lue) is False


# ---------------------------------------------------------------------------
# Le rapport vide, et les invariants que le type leve
# ---------------------------------------------------------------------------


def test_un_rapport_SANS_AUCUN_LOT_n_est_pas_declare_complet():
    """« Aucun QR decode du tout » : zero lot, tout en attente. Pas un plantage.

    Mais pas davantage un rapport dont on peut ecrire les frames : le declarer
    complet ferait proposer une ecriture qui n'a rien a ecrire.
    """
    vide = rapport_scan.projeter([], partition=partition_a_trois_entrees())
    assert vide.lots == ()
    assert vide.complet is False
    assert len(vide.en_attente) == 3


def test_les_issues_d_un_rapport_vide_restent_un_point_de_jugement_valide():
    """`ChoixExclusif` leve a la construction si l'un de ses invariants tombe."""
    vide = rapport_scan.projeter([])
    issues = rapport_scan.issues_du_rapport(vide)
    assert len(issues.choix.issues) >= 2
    assert issues.choix.sortie_sans_ecriture is not None
    assert issues.choix.issues[issues.choix.curseur].ecrit is False


def test_le_total_de_frames_du_rapport_est_la_somme_des_TROIS_lots(rapport):
    assert rapport.frames == 5 + 3 + 9


def test_le_modele_ne_construit_jamais_un_choix_a_une_seule_issue():
    """Volet symetrique du type : le refus existe, et il est atteignable."""
    with pytest.raises(PanneauMalForme):
        rapport_scan.ChoixExclusif([rapport_scan.Issue("seule", "Seule")])


def test_ce_module_ne_propose_AUCUNE_suite_de_chemin_a_qui_tape():
    """La tension entre `EPIC11-ARB-29` et `EPIC11-ARB-48`, **tranchee depuis**.

    **Ce test mesurait la regle d'AVANT `EPIC11-ARB-127`**, et il est reecrit
    ici plutot que supprime, parce que sa premiere redaction est instructive.
    Elle faisait un grep LITTERAL du verbe sur tout le module et exigeait zero ;
    elle exigeait aussi que la cle d'issue ne le porte pas. Le lot D, faute
    d'arbitrage, avait donc renomme la CHOSE (`saisir-le-qr`) pour la faire
    passer sous la frontiere -- en refusant explicitement d'ajouter une
    tolerance en silence, ce qui etait le bon reflexe.

    `EPIC11-ARB-127` a tranche l'inverse : **quand une frontiere attrape un
    homonyme, on resserre la frontiere sur la chose, on ne renomme pas la chose
    pour la faire passer dessous.** Ce que `EPIC11-ARB-48` a retire est le geste
    de la barre d'adresse -- proposer la suite de ce qu'on tape --, pas le verbe
    francais. La cle a donc repris son nom.

    Ce que ce test mesure desormais : **le geste retire n'est pas revenu par la
    fenetre.** La garde reste rejouee ici, chez le lot qui porte l'issue, plutot
    qu'a l'autre bout de la suite.
    """
    source = (DOSSIER_TUI / "atelier_scan_rapport.py").read_text(encoding="utf-8")
    verbe = "complet" + "er"
    mots_de_chemin = ("chemin", "dossier", "barre d'adresse", "saisie de chemin")
    fautives = [f"{rang}: {ligne.strip()}"
                for rang, ligne in enumerate(source.splitlines(), 1)
                if verbe in ligne.lower()
                and any(mot in ligne.lower() for mot in mots_de_chemin)]
    assert fautives == [], (
        "ce module offrirait une suite de chemin a qui tape, ce que "
        "`EPIC11-ARB-48` a retire")

    # Le volet symetrique, sans lequel le precedent ne mesure rien : le
    # vocabulaire du Scan est bien PRESENT, libelle comme cle.
    assert rapport_scan.LIBELLE_COMPLETER_LE_QR in source
    assert verbe in rapport_scan.ISSUE_COMPLETER, (
        "la cle a repris son nom depuis `EPIC11-ARB-127` : la voir renommee "
        "signifierait qu'on est retombe dans le contournement")


#: Les deux maquettes du rapport, lues **a leur source** plutot que recopiees.
MAQUETTES = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
             / "ux-designs" / "ux-tui-2026-08-27" / "maquettes")


@pytest.mark.parametrize("nom", [
    pytest.param("E3-3-scan-rapport-complet.txt", id="E3-3"),
    pytest.param("E3-4-scan-rapport-incomplet.txt", id="E3-4"),
])
def test_les_titres_du_rapport_sont_VERBATIM_de_leur_maquette(nom):
    """Un texte recopie a la main derive ; celui-ci est confronte a sa source.

    Les deux ecrans du rapport portent le meme cartouche et la meme file : les
    titres vivent donc en constante, une fois, et le banc verifie qu'ils sont
    bien ceux que la maquette montre -- pas qu'ils leur ressemblent.
    """
    texte = (MAQUETTES / nom).read_text(encoding="utf-8")
    assert rapport_scan.TITRE_LOTS_RECONNUS in texte
    assert rapport_scan.TITRE_EN_ATTENTE in texte


def test_les_libelles_des_issues_incompletes_sont_VERBATIM_de_E3_4(rapport):
    """`E3-4` porte les trois libelles ; aucun ne se reformule ici."""
    texte = (MAQUETTES / "E3-4-scan-rapport-incomplet.txt").read_text(
        encoding="utf-8")
    for issue in rapport_scan.issues_du_rapport(rapport).choix.issues:
        assert issue.libelle in texte, issue.libelle
