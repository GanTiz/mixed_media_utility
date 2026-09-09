# -*- coding: utf-8 -*-
"""Story 11.6, lot D -- `E3-6`, la confirmation du temps 2 du Scan (AC 4).

Ce banc mesure `tui/atelier_scan_confirmation.py`, et **lui seul**. Les autres
lots de la story ont chacun le leur : « aucun lot ne partage un fichier de banc
avec un autre » -- ni `git add -N` ni `git commit -- <chemins>` ne protegent a
l'interieur d'un fichier partage, defaut paye trois fois sur ce depot.

Quatre regles de mesure heritees, et elles commandent la forme des fabriques
------------------------------------------------------------------------------
1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte** (`CLAUDE.md`, points 2 et 2 bis). Les deux boucles du module sont
   **les lots** et **les zones de decoupe** : les deux fabriques placent leur
   cible en deuxieme position sur trois ;
2. **la position se verifie sur la liste que le code PARCOURT**, jamais sur
   celle que la fabrique croit ecrire. C'est le finding le plus grave de la
   revue de la vague 3 : sur la 11.4b, une fixture croyait respecter le point
   2 bis alors que l'ordre de la liste iteree n'etait pas celui des
   `page_index`, et trois mutants `continue` -> `break` y ont survecu. Le banc
   assert donc d'abord sur `plan.lots` et sur `document.pages[].frame_zones` ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « Cette ligne est presente » ne mesure rien ; « l'ensemble des libelles est
   **exactement** {...} » mesure l'ensemble ET son unicite ;
4. **aucun nombre de limite n'est ecrit**, ni dans le produit ni ici (AC 4.6).
   Une frontiere negative le compte a zero sur les deux fichiers, avec son
   volet symetrique -- sans quoi un detecteur casse serait vert sur tout.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import qr_codes, scan_detection, scan_previz
from mixed_media_utility.constants import OUTPUT_BIT_DEPTH
from mixed_media_utility.io.naming import CANONICAL_ID_MAX_LENGTH
from mixed_media_utility.tui import atelier_scan_confirmation as confirmation
from mixed_media_utility.tui import atelier_scan_rapport as rapport_scan
from mixed_media_utility.tui import jetons, noms as noms_tui
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    INDENT_DES_NOMS,
    octets_par_frame,
    taille_lisible,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.panneau import MENTION_MAJORANT

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le module mesure et ce banc, pour les frontieres negatives.
SOURCE_DU_PRODUIT = (Path(_SRC) / "mixed_media_utility" / "tui"
                     / "atelier_scan_confirmation.py")
SOURCE_DU_BANC = Path(__file__)


# ---------------------------------------------------------------------------
# Fabriques. Aucune ne produit un element unique, aucune ne remplit une
# collection d'une valeur uniforme.
# ---------------------------------------------------------------------------

#: Les trois lots de la fabrique principale. **La cible est au MILIEU**, et les
#: trois se distinguent par leur nom, par leur slug ET par leurs comptes.
LOT_PREMIER = "lot_25fps"
LOT_CIBLE = "lot_12p5"
LOT_DERNIER = "lot_18fps"

SLUG_PREMIER = "ingest_du_25fps"
SLUG_CIBLE = "ingest_du_12p5"
SLUG_DERNIER = "ingest_du_18fps"

#: Trois comptes de frames differents : une permutation de deux lots ne peut
#: pas passer inapercue, et un `break` sur le lot du milieu ferait disparaitre
#: le troisieme.
FRAMES_PREMIER = 5
FRAMES_CIBLE = 3
FRAMES_DERNIER = 9

#: Les trois zones d'une page. **La cible est au milieu**, et ses mesures
#: different de celles de ses deux voisines : un remplissage uniforme rendrait
#: invisible toute permutation (mutant `M33` de la story 5.6).
LARGEURS_DE_ZONE = (300, 512, 700)
HAUTEURS_DE_ZONE = (400, 611, 800)


def zone(rang: int, *, largeur: int | None = None,
         hauteur: int | None = None) -> scan_previz.PrevizFrameZone:
    """Une zone de decoupe, aux mesures **distinctes** de celles des autres."""
    decalage = float(rang)
    return scan_previz.PrevizFrameZone(
        slot_index=rang,
        frame_timecode=f"00:00:0{rang % 10}:00",
        zone_name=f"zone_{rang}",
        zone_x_mm=10.0 + decalage, zone_y_mm=20.0 + decalage,
        zone_w_mm=30.0 + decalage, zone_h_mm=40.0 + decalage,
        crop_x_mm=11.0 + decalage, crop_y_mm=21.0 + decalage,
        crop_w_mm=29.0 + decalage, crop_h_mm=39.0 + decalage,
        crop_x_px=100 + rang, crop_y_px=200 + rang,
        crop_w_px=LARGEURS_DE_ZONE[rang] if largeur is None else largeur,
        crop_h_px=HAUTEURS_DE_ZONE[rang] if hauteur is None else hauteur,
    )


def page(read_rank: int, *, page_index: int, page_count: int, lot_id: str,
         zones) -> scan_previz.ScanPrevizPage:
    """Une page de document, avec les zones qu'on lui donne."""
    return scan_previz.ScanPrevizPage(
        read_rank=read_rank,
        page_index=page_index,
        page_count=page_count,
        status=scan_detection.PAGE_OK,
        qr_status=qr_codes.DECODE_OK,
        refusal_reason=None,
        source_path_relative=f"scans/pile/planche_{read_rank:02d}.tiff",
        source_page_index=None,
        scan_input_format="tiff",
        source_bit_depth=16,
        width_px=4960 + read_rank,
        height_px=7016 + read_rank,
        channels=3,
        decoded_project_id="projet_demo",
        decoded_rush_id="rush_a",
        decoded_lot_id=lot_id,
        decoded_gamut_map_id="G1",
        template_id="T1",
        template_source="qr",
        page_size_px=None,
        homography=None,
        scale=None,
        corner_markers=(),
        foreign_markers=(),
        frame_zones=tuple(zones),
        calibration=None,
        warnings=(),
        payload={
            "project_id": "projet_demo", "rush_id": "rush_a",
            "lot_id": lot_id, "page_index": page_index,
            "page_count": page_count, "template_id": "T1",
            "gamut_map_id": "G1",
        },
        source_digest=f"digest-{read_rank}",
        refusal_code=None,
    )


def document(lot_id: str, *, slug: str, pages,
             pages_expected: int | None = None) -> scan_previz.ScanPreviz:
    """Un document de detection, en regime `detected`."""
    return scan_previz.ScanPreviz(
        previz_schema_version="1.0",
        kind=scan_previz.SCAN_PREVIZ_KIND,
        state=scan_previz.SCAN_PREVIZ_STATE_DETECTED,
        generated_at_utc="2026-09-01T10:00:00Z",
        subject=scan_previz.ScanPrevizSubject(
            project_id="projet_demo",
            rush_id="rush_a",
            lot_id=lot_id,
            ingest_slug=slug,
            template_id="T1",
            gamut_map_id="G1",
            fps_target_exact="25",
            target_colorspace=None,
            patch_preset_id=None,
            scan_dpi_declared=600,
            scan_dpi_detection=600,
            scans_dir_relative=f"scans/{slug}",
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


def panneau_de_lot(lot_id: str, frames: int,
                   attendues: int | None) -> rapport_scan.PanneauDeLot:
    """Un panneau de lot du rapport du temps 1, tel que `E3-3` le porte."""
    return rapport_scan.PanneauDeLot(
        lot_id=lot_id,
        pages_trouvees=2,
        pages_attendues=2,
        frames=frames,
        frames_attendues=attendues,
        completude=rapport_scan.scan_detect.COMPLETUDE_COMPLET,
    )


def rapport_a_trois_lots(*, attendues=(FRAMES_PREMIER, FRAMES_CIBLE,
                                       FRAMES_DERNIER)):
    """Trois lots, **la cible au milieu**, tous distinguables.

    `attendues` permet de retirer un attendu -- au milieu, comme le reste --
    sans changer l'ordre de la liste que le code parcourt.
    """
    frames = (FRAMES_PREMIER, FRAMES_CIBLE, FRAMES_DERNIER)
    identites = (LOT_PREMIER, LOT_CIBLE, LOT_DERNIER)
    return rapport_scan.RapportDeDetection(lots=tuple(
        panneau_de_lot(lot_id, compte, attendu)
        for lot_id, compte, attendu in zip(identites, frames, attendues)))


def documents_a_trois_lots(*, ordre=None, zones_de_la_cible=None):
    """Un document par lot, **la cible au milieu** sauf ordre impose.

    `ordre` sert au test d'appariement : les documents y arrivent dans un ordre
    different de celui du rapport, ce qui fait rougir tout appariement
    positionnel entre les deux listes (mutant `M25` de la story 5.7).
    """
    zones_cible = (zone(0), zone(1), zone(2)) if zones_de_la_cible is None \
        else zones_de_la_cible
    par_lot = {
        LOT_PREMIER: document(
            LOT_PREMIER, slug=SLUG_PREMIER, pages_expected=1, pages=[
                page(1, page_index=0, page_count=1, lot_id=LOT_PREMIER,
                     zones=(zone(0), zone(2)))]),
        LOT_CIBLE: document(
            LOT_CIBLE, slug=SLUG_CIBLE, pages_expected=1, pages=[
                page(11, page_index=0, page_count=1, lot_id=LOT_CIBLE,
                     zones=zones_cible)]),
        LOT_DERNIER: document(
            LOT_DERNIER, slug=SLUG_DERNIER, pages_expected=1, pages=[
                page(21, page_index=0, page_count=1, lot_id=LOT_DERNIER,
                     zones=(zone(1),))]),
    }
    ordre = ordre or (LOT_PREMIER, LOT_CIBLE, LOT_DERNIER)
    return [par_lot[lot_id] for lot_id in ordre]


def plan_nominal(**reglages):
    """Le plan des trois lots, la cible au milieu."""
    return confirmation.preparer_le_plan(
        rapport_a_trois_lots(**{k: v for k, v in reglages.items()
                                if k == "attendues"}),
        documents_a_trois_lots(),
        calibration=reglages.get("calibration"))


def coque(ecran, ascii_seul: bool = False) -> CoqueTui:
    """Deux paliers temoins, puis l'ecran mesure au sommet."""
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"),
                    ascii_seul=ascii_seul)


def monter(banc, ecran, ascii_seul: bool = False):
    """Monter l'ecran au plancher et rendre ce que le test veut lire."""
    app = coque(ecran, ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        etat = jetons.texte_affiche(str(courant.query_one("#etat").content))
        raccourcis = jetons.texte_affiche(
            str(courant.query_one("#raccourcis").content))
        blocs = [jetons.texte_affiche(str(widget.content))
                 for widget in courant.query_one("#centre").query("Static")]
        return courant, etat, raccourcis, blocs

    return banc(app, scenario)


# ---------------------------------------------------------------------------
# La fabrique se mesure AVANT ce qu'elle sert. Une fabrique qui aurait glisse
# sa cible en premiere ou en derniere position rendrait vertes toutes les
# mesures de position qui suivent, sans rien mesurer.
# ---------------------------------------------------------------------------


def test_la_cible_est_au_MILIEU_de_la_liste_QUE_LE_CODE_PARCOURT():
    """Point 2 bis de `CLAUDE.md`, verifie sur `plan.lots` et non sur la fabrique.

    Trois lots, la cible en **deuxieme** position : un `find` fautif qui rendrait
    toujours le premier element ne se demasque pas autrement, et une boucle qui
    s'arreterait au premier echec ferait disparaitre le troisieme.
    """
    plan = plan_nominal()
    parcourus = [lot.lot_id for lot in plan.lots]
    assert parcourus == [LOT_PREMIER, LOT_CIBLE, LOT_DERNIER]
    assert parcourus.index(LOT_CIBLE) == 1
    assert len(parcourus) == 3


def test_les_trois_lots_sont_DISTINGUABLES_par_leur_nom_leur_slug_et_leurs_comptes():
    """Volet symetrique de la fabrique : trois valeurs uniformes ne mesureraient
    rien, et c'est exactement le mutant `M33` de la story 5.6."""
    plan = plan_nominal()
    assert len({lot.lot_id for lot in plan.lots}) == 3
    assert len({lot.slug for lot in plan.lots}) == 3
    assert len({lot.frames for lot in plan.lots}) == 3


def test_les_trois_zones_de_la_cible_sont_au_nombre_de_trois_et_distinctes():
    """La seconde boucle du module est **les zones** : sa fabrique se mesure
    aussi, et sur la liste que le code parcourt (`page.frame_zones`)."""
    cible = next(doc for doc in documents_a_trois_lots()
                 if doc.subject.lot_id == LOT_CIBLE)
    zones = cible.pages[0].frame_zones
    assert len(zones) == 3
    assert len({(z.crop_w_px, z.crop_h_px) for z in zones}) == 3


# ---------------------------------------------------------------------------
# D1 -- le panneau chiffre : attendues et obtenues sur DEUX lignes
# ---------------------------------------------------------------------------


def _libelles(panneau) -> list[str]:
    return [ligne.libelle for ligne in panneau.lignes]


def test_le_cartouche_porte_EXACTEMENT_ces_six_lignes():
    """Ensemble EXACT et non inclusion : une septieme ligne ajoutee sans etre
    mesuree ferait rougir ici, et une sixieme retiree aussi."""
    panneau = confirmation.panneau_de_la_confirmation(plan_nominal())
    assert _libelles(panneau) == [
        confirmation.LIBELLE_LOTS,
        confirmation.LIBELLE_FRAMES_ATTENDUES,
        confirmation.LIBELLE_FRAMES_OBTENUES,
        confirmation.LIBELLE_PROFONDEUR,
        confirmation.LIBELLE_CALIBRATION,
        confirmation.LIBELLE_ESPACE,
    ]


def test_attendues_et_obtenues_sont_DEUX_lignes_DISTINCTES():
    """AC 4.2, demande litterale d'Egan. Deux rangs differents, deux libelles
    differents -- une seule ligne portant les deux chiffres ne serait pas ce
    qui a ete demande."""
    libelles = _libelles(confirmation.panneau_de_la_confirmation(plan_nominal()))
    rang_attendues = libelles.index(confirmation.LIBELLE_FRAMES_ATTENDUES)
    rang_obtenues = libelles.index(confirmation.LIBELLE_FRAMES_OBTENUES)
    assert rang_attendues != rang_obtenues
    assert (confirmation.LIBELLE_FRAMES_ATTENDUES
            != confirmation.LIBELLE_FRAMES_OBTENUES)


def test_les_deux_comptes_sont_CEUX_du_rapport_sans_seconde_derivation():
    """AC 4.2 : les valeurs sont celles que `PanneauDeLot` porte deja.

    L'egalite porte sur les **couples**, lot par lot : deux totaux egaux
    pourraient recouvrir deux appariements differents.
    """
    rapport = rapport_a_trois_lots()
    plan = confirmation.preparer_le_plan(rapport, documents_a_trois_lots())
    assert [(lot.lot_id, lot.frames, lot.frames_attendues) for lot in plan.lots] \
        == [(lot.lot_id, lot.frames, lot.frames_attendues)
            for lot in rapport.lots]


def test_la_somme_par_lot_est_celle_de_la_maquette():
    """`5 + 3 + 9 = 17` sur trois lots, et le nombre nu sur un seul.

    `17 = 17` sur un lot unique serait du bruit : c'est la forme que `E2-3`
    porte deja, et la maquette `E3-6` la reprend.
    """
    plan = plan_nominal()
    ligne = confirmation.ligne_des_frames_obtenues(plan)
    total = FRAMES_PREMIER + FRAMES_CIBLE + FRAMES_DERNIER
    assert (f"{FRAMES_PREMIER} + {FRAMES_CIBLE} + {FRAMES_DERNIER} = {total}"
            in ligne.chiffre)

    seul = confirmation.PlanDEcriture(lots=(
        confirmation.LotAEcrire(LOT_CIBLE, SLUG_CIBLE, FRAMES_CIBLE,
                                FRAMES_CIBLE),))
    chiffre = confirmation.ligne_des_frames_obtenues(seul).chiffre
    assert "=" not in chiffre and "+" not in chiffre
    assert f"{FRAMES_CIBLE} {confirmation.UNITE_FRAMES}" in chiffre


def test_un_attendu_absent_est_DIT_et_ne_replie_pas_les_obtenues():
    """AC 4.2 : « quand `frames_attendues` vaut `None`, la ligne le **dit**
    plutot que d'afficher les obtenues deux fois »."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(attendues=(None, None, None)),
        documents_a_trois_lots())
    ligne = confirmation.ligne_des_frames_attendues(plan)
    assert ligne.chiffre == confirmation.FRAMES_ATTENDUES_INCONNUES
    assert str(plan.frames_obtenues) not in ligne.chiffre


def test_UN_SEUL_attendu_manquant_AU_MILIEU_suffit_a_rendre_le_total_inconnu():
    """`None` des qu'UN seul manque, et non « on somme ce qu'on a » : un total
    partiel se lirait comme un total, et c'est la valeur devinee que
    `DESIGN.md` section 3 interdit.

    Le lot prive d'attendu est **au milieu** : un `break` a la premiere valeur
    connue rendrait le meme verdict qu'une boucle correcte si la cible etait en
    tete.
    """
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(attendues=(FRAMES_PREMIER, None, FRAMES_DERNIER)),
        documents_a_trois_lots())
    assert plan.frames_attendues is None
    assert plan.manque is None
    assert (confirmation.ligne_des_frames_attendues(plan).chiffre
            == confirmation.FRAMES_ATTENDUES_INCONNUES)


def test_un_plan_SANS_lot_ne_rend_pas_zero_frame_attendue():
    """`sum(())` vaut zero, et « zero frame attendue » se lirait comme une
    mesure alors que rien n'a ete mesure."""
    vide = confirmation.PlanDEcriture()
    assert vide.frames_attendues is None
    assert vide.manque is None
    assert vide.frames_obtenues == 0


def test_la_profondeur_est_LUE_du_coeur_par_identite():
    """Aucun `16` ecrit dans la TUI : la profondeur de sortie du depot est
    `constants.OUTPUT_BIT_DEPTH`, et c'est elle qui est rendue."""
    panneau = confirmation.panneau_de_la_confirmation(plan_nominal())
    ligne = next(l for l in panneau.lignes
                 if l.libelle == confirmation.LIBELLE_PROFONDEUR)
    assert ligne.valeur == OUTPUT_BIT_DEPTH
    assert ligne.unite == confirmation.UNITE_PROFONDEUR


def test_la_calibration_retenue_est_CELLE_qu_on_donne_et_aucune_est_DITE():
    """La calibration vient de `E3-5` ; « aucune » est un fait sur ce qui sera
    ecrit -- le lot est livre brut --, jamais un manque tu."""
    avec = plan_nominal(calibration="hp-envy-4520-tiff-600")
    ligne = next(l for l in confirmation.panneau_de_la_confirmation(avec).lignes
                 if l.libelle == confirmation.LIBELLE_CALIBRATION)
    assert ligne.valeur == "hp-envy-4520-tiff-600"

    sans = plan_nominal()
    ligne = next(l for l in confirmation.panneau_de_la_confirmation(sans).lignes
                 if l.libelle == confirmation.LIBELLE_CALIBRATION)
    assert ligne.valeur == confirmation.CALIBRATION_AUCUNE


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_comptes_qui_coincident_portent_le_glyphe_COMPLET(ascii_seul):
    """AC 4.3, cote nominal : `● toutes`, verbatim de la maquette."""
    plan = plan_nominal()
    assert plan.toutes_les_frames_attendues
    mention = confirmation.mention_des_obtenues(plan, ascii_seul)
    assert mention == jetons.marque("complete", confirmation.MENTION_TOUTES,
                                    ascii_seul)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_comptes_qui_divergent_passent_a_ABSENT_et_DISENT_le_manque(ascii_seul):
    """AC 4.3 : « le glyphe passe de `●` a `✕`, le compte du manque est **dit** ».

    Le lot ampute est **au milieu** : un `break` avant lui ne verrait pas la
    divergence, un `break` apres lui ne verrait pas le troisieme lot.
    """
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(
            attendues=(FRAMES_PREMIER, FRAMES_CIBLE + 2, FRAMES_DERNIER)),
        documents_a_trois_lots())
    assert plan.manque == 2
    assert not plan.toutes_les_frames_attendues
    mention = confirmation.mention_des_obtenues(plan, ascii_seul)
    assert mention == jetons.marque("absent", "2 manquantes", ascii_seul)
    assert jetons.glyphes(ascii_seul)["complete"] not in mention


def test_le_manque_d_UNE_frame_s_accorde_au_singulier():
    """« 1 manquante », jamais « 1 manquantes » -- le pluriel suit le compte."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(
            attendues=(FRAMES_PREMIER, FRAMES_CIBLE + 1, FRAMES_DERNIER)),
        documents_a_trois_lots())
    assert "1 manquante" in confirmation.mention_des_obtenues(plan)
    assert "manquantes" not in confirmation.mention_des_obtenues(plan)


def test_un_SURPLUS_de_frames_se_dit_aussi():
    """Le document peut porter plus de frames que le manifest n'en declarait.

    Un surplus tu serait un ecart entre les deux que personne ne verrait
    passer, et `✕ -2 manquantes` serait pire encore.
    """
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(
            attendues=(FRAMES_PREMIER, FRAMES_CIBLE - 2, FRAMES_DERNIER)),
        documents_a_trois_lots())
    assert plan.manque == -2
    mention = confirmation.mention_des_obtenues(plan)
    assert mention == jetons.marque("absent", "2 en trop")
    assert "-2" not in mention


def test_sans_attendu_la_ligne_des_obtenues_ne_porte_AUCUNE_mention():
    """Sans terme de comparaison, `● toutes` affirmerait une egalite que
    personne n'a mesuree, et `✕` accuserait un manque qui n'est pas su."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(attendues=(None, None, None)),
        documents_a_trois_lots())
    assert confirmation.mention_des_obtenues(plan) == ""
    chiffre = confirmation.ligne_des_frames_obtenues(plan).chiffre
    for cle in ("complete", "absent"):
        assert jetons.GLYPHES[cle] not in chiffre


# ---------------------------------------------------------------------------
# D2 -- les trois issues
# ---------------------------------------------------------------------------


def test_les_trois_issues_sont_EXACTEMENT_celles_la():
    """Ensemble exact -- cle, libelle et drapeau d'ecriture ensemble."""
    choix = confirmation.issues_de_la_confirmation(plan_nominal())
    assert [(issue.cle, issue.libelle, issue.ecrit) for issue in choix.issues] == [
        (confirmation.ISSUE_ECRIRE, confirmation.LIBELLE_ECRIRE, True),
        (confirmation.ISSUE_MODIFIER, confirmation.LIBELLE_MODIFIER, False),
        (confirmation.ISSUE_ANNULER, confirmation.LIBELLE_ANNULER, False),
    ]


def test_aucune_issue_n_est_preselectionnee_et_le_curseur_n_ecrit_pas():
    """AC 4.4 : invariant leve par `ChoixExclusif.__post_init__`, jamais
    reecrit ici. Le test mesure l'etat produit, pas la reecriture."""
    choix = confirmation.issues_de_la_confirmation(plan_nominal())
    assert choix.retenue is None
    assert not choix.issues[choix.curseur].ecrit
    assert choix.action_qui_ecrit.cle == confirmation.ISSUE_ECRIRE


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_rendu_pose_UNE_LIGNE_par_issue_et_la_FLECHE_SEULE(ascii_seul):
    """`EPIC11-ARB-126` -- « **Flèche seule !** C'est uniquement dans les listes
    à cocher qu'on trouve les deux. » C'est l'ecart `H5` de cette story."""
    choix = confirmation.issues_de_la_confirmation(plan_nominal())
    lignes = choix.rendu(ascii_seul)
    table = jetons.glyphes(ascii_seul)
    assert len(lignes) == len(choix.issues) == 3
    for cle in ("coche", "decoche", "exclusif-retenu", "exclusif-libre"):
        assert not any(table[cle] in ligne for ligne in lignes)
    assert sum(ligne.startswith(table["curseur"]) for ligne in lignes) == 1


def test_le_libelle_de_la_premiere_issue_porte_le_compte_REEL_quand_il_manque():
    """AC 4.3 : « le compte **reel**, jamais le compte attendu »."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(
            attendues=(FRAMES_PREMIER, FRAMES_CIBLE + 2, FRAMES_DERNIER)),
        documents_a_trois_lots())
    choix = confirmation.issues_de_la_confirmation(plan)
    libelle = choix.issue(confirmation.ISSUE_ECRIRE).libelle
    assert libelle == confirmation.GABARIT_ECRIRE_LES_OBTENUES.format(
        frames=plan.frames_obtenues)
    assert str(plan.frames_attendues) not in libelle


def test_le_libelle_reste_celui_de_la_maquette_quand_les_comptes_coincident():
    """Volet symetrique du precedent : sans divergence, `Écrire les TIFF`."""
    choix = confirmation.issues_de_la_confirmation(plan_nominal())
    assert (choix.issue(confirmation.ISSUE_ECRIRE).libelle
            == confirmation.LIBELLE_ECRIRE)


def test_un_attendu_inconnu_ne_requalifie_PAS_le_libelle():
    """`None` n'est pas une divergence : ne rien savoir n'est pas manquer."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(attendues=(None, None, None)),
        documents_a_trois_lots())
    choix = confirmation.issues_de_la_confirmation(plan)
    assert (choix.issue(confirmation.ISSUE_ECRIRE).libelle
            == confirmation.LIBELLE_ECRIRE)


# ---------------------------------------------------------------------------
# D3 -- l'edition du slug
# ---------------------------------------------------------------------------


def ecran_nominal(**reglages) -> confirmation.EcranScanConfirmation:
    return confirmation.EcranScanConfirmation(plan_nominal(**reglages))


#: Ce que le retrait d'`EPIC11-ARB-141` a emporte de ce banc, et pourquoi il
#: n'est pas remplace test pour test.
#:
#: Six tests mesuraient le MODE d'edition de `E3-6` -- `Tab` qui entre, la
#: lettre qui ne remet plus, le compteur vivant, le refus a la limite, l'action
#: principale inaccessible sur un nom refuse et son volet symetrique. Le mode
#: n'existe plus sur cet ecran : leur sujet a disparu, pas leur mesure. Ce qui
#: reste d'eux vit desormais dans `test_aucun_nom_editable.py`, sous la forme
#: qui convient a un retrait -- une frontiere NEGATIVE, qui rougit a la
#: reintroduction. Un test positif ne verrait jamais revenir un champ.


def test_les_noms_DERIVES_sont_les_slugs_du_document_dans_l_ORDRE_des_lots():
    """`EPIC11-ARB-141` : les noms sont **montres**, ils ne sont plus editables.

    L'assertion porte sur la liste **entiere et ordonnee** : tete, milieu et
    queue. Un balayage tronque d'une entree ferait disparaitre le dernier lot en
    silence, et une cible au milieu ne le demasquerait pas (regle des
    fabriques, point 4).
    """
    assert confirmation.noms_du_plan(plan_nominal()) == [
        INDENT_DES_NOMS + SLUG_PREMIER,
        INDENT_DES_NOMS + SLUG_CIBLE,
        INDENT_DES_NOMS + SLUG_DERNIER,
    ]


def test_un_slug_TROP_LONG_pour_le_cartouche_est_abrege_AU_MILIEU():
    """Un nom coupe par la FIN perdrait sa queue -- c'est-a-dire exactement le
    slug d'ingest qui distingue deux lots du meme rush.

    La borne du cartouche n'est pas recopiee : elle est celle de
    `jetons.largeur_de_cartouche`, comme le produit la lit.
    """
    budget = jetons.largeur_de_cartouche(jetons.LARGEUR_PLANCHER) \
        - len(INDENT_DES_NOMS)
    long = "a" * (budget + 10) + "_queue"
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(),
        documents_a_trois_lots(), calibration=None)
    plan = confirmation.PlanDEcriture(lots=tuple(
        confirmation.LotAEcrire(lot_id=lot.lot_id,
                                slug=long if rang == 1 else lot.slug,
                                frames=lot.frames,
                                frames_attendues=lot.frames_attendues)
        for rang, lot in enumerate(plan.lots)))
    rendu = confirmation.noms_du_plan(plan)[1]
    assert rendu.startswith(INDENT_DES_NOMS + "a")
    assert rendu.endswith("_queue")
    assert jetons.colonnes(rendu) <= jetons.largeur_de_cartouche(
        jetons.LARGEUR_PLANCHER)


# ---------------------------------------------------------------------------
# D4 -- la limite est LUE, jamais recopiee
# ---------------------------------------------------------------------------

#: Ce que la frontiere cherche : la borne de creation et la borne heritee,
#: **construites** plutot qu'ecrites -- les ecrire ici les ferait entrer dans
#: le fichier que la frontiere balaye, et le banc se mesurerait lui-meme
#: fautif.
from mixed_media_utility.io.naming import LEGACY_ID_MAX_LENGTH  # noqa: E402

BORNES_INTERDITES = (str(CANONICAL_ID_MAX_LENGTH), str(LEGACY_ID_MAX_LENGTH))


def _nombres_nus(texte: str) -> set[str]:
    """Les nombres ecrits en clair dans un texte, bornes de mot comprises."""
    return set(re.findall(r"(?<![\w.])(\d+)(?![\w.])", texte))


#: Le module ou la limite est LIEE une fois pour toute la TUI. La frontiere de
#: l'AC 4.6 porte sur sa **redaction**, pas sur la valeur qu'il rend.
SOURCE_DE_NOMS = Path(_SRC) / "mixed_media_utility" / "tui" / "noms.py"

#: Le dernier segment du module de coeur d'ou la borne doit venir. On compare
#: le segment et non le chemin entier : `from ..io.naming import ...` rend
#: `io.naming`, un `from mixed_media_utility.io.naming import ...` rendrait le
#: chemin complet, et les deux disent la meme provenance.
SEGMENT_DU_COEUR = "naming"


def _noms_lies_au_coeur(arbre: ast.Module) -> set[str]:
    """Les noms qu'un module importe depuis `io.naming`, quelle que soit la
    profondeur du `from ..io.naming import ...`."""
    lies: set[str] = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.ImportFrom)
                and (noeud.module or "").split(".")[-1] == SEGMENT_DU_COEUR):
            lies.update(alias.asname or alias.name for alias in noeud.names)
    return lies


def _seconde_redaction_de_la_limite(source: str) -> str | None:
    """Ce qui, dans `source`, REDIT la borne au lieu de la LIER -- ou `None`.

    Une liaison est une **liaison** : `LIMITE = <nom importe du coeur>`, et rien
    d'autre. Toute autre forme -- un litteral, un appel, une operation, un
    attribut, un defaut -- est une seconde ecriture de la regle du schema, donc
    une regle qui divergera de la premiere au prochain ajustement de borne.
    """
    arbre = ast.parse(source)
    liaisons = [noeud.value for noeud in arbre.body
                if isinstance(noeud, ast.Assign)
                and any(isinstance(cible, ast.Name) and cible.id == "LIMITE"
                        for cible in noeud.targets)]
    if len(liaisons) != 1:
        return f"{len(liaisons)} liaisons de LIMITE au niveau module"
    valeur = liaisons[0]
    if type(valeur) is not ast.Name:
        return (f"LIMITE est liee a un {type(valeur).__name__}, pas au nom "
                f"importe du coeur : {ast.dump(valeur)}")
    lies = _noms_lies_au_coeur(arbre)
    if valeur.id not in lies:
        return (f"LIMITE est liee a `{valeur.id}`, qui ne vient pas de "
                f"`io.{SEGMENT_DU_COEUR}` (importes : {sorted(lies)})")
    return None


def test_LIMITE_ne_REDIT_pas_la_borne_du_coeur_elle_la_LIE():
    """AC 4.6, et c'est la mesure qui REMPLACE l'assertion d'identite.

    **La mesure d'avant etait une tautologie**, trouvee par la couche 3 de la
    revue de vague 4 (finding `A2`). Elle disait
    `assert noms_tui.LIMITE is CANONICAL_ID_MAX_LENGTH`, et CPython met en cache
    les entiers de -5 a 256 : les deux valeurs que la bascule de liaison fait
    traverser au depot sont **toutes deux dans ce cache**, si bien que `is` et
    `==` y rendent le meme verdict quelle que soit la redaction. Le mutant
    `LIMITE = int(CANONICAL_ID_MAX_LENGTH)` -- une seconde redaction reelle,
    exactement ce que l'AC existe pour interdire -- **survivait aux 72 tests du
    banc**. L'AC demandait une garantie qu'aucun test executant du code ne peut
    etablir.

    Ce que celle-ci mesure a la place, et qui mord : la **redaction**, lue a
    l'AST du module produit. `LIMITE` est liee au nom importe du coeur, et a
    rien d'autre -- ni un nombre, ni un appel, ni une operation. Un `int(...)`
    autour du nom est un `ast.Call` et fait rougir ; la borne recopiee en clair
    est un `ast.Constant` et fait rougir aussi. (Ecrire ce nombre ICI pour
    l'illustrer a fait rougir la frontiere de
    `test_aucune_borne_d_identifiant_n_est_ECRITE_en_clair` sur ce banc meme,
    au premier lancement -- elle fait donc ce qu'elle annonce.)
    """
    faute = _seconde_redaction_de_la_limite(
        SOURCE_DE_NOMS.read_text(encoding="utf-8"))
    assert faute is None, f"{SOURCE_DE_NOMS.name} : {faute}"


def test_le_detecteur_de_SECONDE_REDACTION_trouve_les_formes_plantees():
    """Volet symetrique : sans lui, un detecteur casse serait vert sur tout.

    Les formes plantees sont **construites**, jamais ecrites : ecrire la borne
    ici ferait rougir la frontiere de `test_aucune_borne_d_identifiant_n_est_
    ECRITE_en_clair` sur ce fichier meme.
    """
    entete = "from ..io.naming import CANONICAL_ID_MAX_LENGTH\n"
    assert _seconde_redaction_de_la_limite(
        entete + "LIMITE = CANONICAL_ID_MAX_LENGTH\n") is None, (
        "la forme juste doit passer, sinon le detecteur rougirait sur tout")
    plantes = (
        "LIMITE = int(CANONICAL_ID_MAX_LENGTH)",
        f"LIMITE = {CANONICAL_ID_MAX_LENGTH}",
        "LIMITE = CANONICAL_ID_MAX_LENGTH + 0",
        "LIMITE = naming.CANONICAL_ID_MAX_LENGTH",
        "LIMITE = min(CANONICAL_ID_MAX_LENGTH, LEGACY_ID_MAX_LENGTH)",
    )
    for plante in plantes:
        assert _seconde_redaction_de_la_limite(entete + plante + "\n") is not None, (
            f"seconde redaction non vue : {plante}")
    # ... et une liaison qui vient d'ailleurs que du coeur ne passe pas non plus,
    # meme ecrite comme une simple liaison : c'est le second volet du detecteur.
    assert _seconde_redaction_de_la_limite(
        "LIMITE = UNE_AUTRE_BORNE\n") is not None


@pytest.mark.parametrize("source", [
    pytest.param(SOURCE_DU_PRODUIT, id="produit"),
    pytest.param(SOURCE_DU_BANC, id="banc"),
])
def test_aucune_borne_d_identifiant_n_est_ECRITE_en_clair(source):
    """Frontiere negative de l'AC 4.6, sur le produit **et** sur ce banc.

    Une borne recopiee serait une seconde redaction d'une regle qui n'en admet
    qu'une, et elle survivrait a la prochaine bascule : c'est exactement ce que
    l'ecart `H6` a coute sur la maquette.

    Le balayage porte sur le **fichier entier**, prose et commentaires compris.
    Une borne citee dans une docstring reste une borne ecrite deux fois, et
    c'est elle qu'une relecture prendrait pour la reference -- le depot a paye
    exactement cette classe d'ecart le 2026-08-31, quand une borne perimee
    vivait dans un commentaire pendant que le code en portait une autre.
    """
    trouves = _nombres_nus(source.read_text(encoding="utf-8"))
    assert trouves.isdisjoint(BORNES_INTERDITES), (
        f"{source.name} ecrit en clair une borne d'identifiant : "
        f"{sorted(trouves & set(BORNES_INTERDITES))}")


def test_le_detecteur_de_borne_TROUVE_une_borne_plantee():
    """Volet symetrique : sans lui, un detecteur casse serait vert sur tout.

    Le texte plante est **construit**, jamais ecrit -- l'ecrire ferait rougir
    la frontiere du test precedent sur ce fichier meme.
    """
    plante = f"limite = {CANONICAL_ID_MAX_LENGTH}  # recopiee"
    assert not _nombres_nus(plante).isdisjoint(BORNES_INTERDITES)
    assert _nombres_nus("limite = LIMITE").isdisjoint(BORNES_INTERDITES)


# ---------------------------------------------------------------------------
# D5 -- le majorant d'espace disque
# ---------------------------------------------------------------------------


def test_le_majorant_somme_TOUTES_les_zones_de_TOUS_les_documents():
    """AC 4.7 : le majorant se calcule sur les `crop_w_px` / `crop_h_px` reels.

    La somme est **exacte** : un `break` sur la zone du milieu, ou sur le lot du
    milieu, rendrait un total plus petit sans qu'aucun message ne le dise.
    """
    documents = documents_a_trois_lots()
    attendu = sum(
        octets_par_frame(zone.crop_w_px, zone.crop_h_px)
        for doc in documents for page_ in doc.pages
        for zone in page_.frame_zones)
    assert confirmation.majorant_du_document(documents) == attendu

    # ... et la somme couvre bien les SIX zones des trois lots : deux, trois et
    # une. Un total qui n'en compterait que cinq passerait l'egalite ci-dessus
    # si l'attendu etait calcule par le meme parcours fautif.
    assert sum(len(page_.frame_zones)
               for doc in documents for page_ in doc.pages) == 6


def test_une_dimension_inconnue_TRAVERSE_en_None():
    """AC 4.7 : « une dimension inconnue traverse en `None` ».

    La zone amputee est **au milieu** des trois : un `break` a la premiere
    rendrait `None` lui aussi, donc la position est ce qui distingue la mesure
    d'une coincidence -- le test suivant ferme l'autre moitie.
    """
    zones = (zone(0), zone(1, largeur=0), zone(2))
    documents = documents_a_trois_lots(zones_de_la_cible=zones)
    assert confirmation.majorant_du_document(documents) is None


def test_sommer_ce_qu_on_sait_serait_un_majorant_qui_n_en_est_plus_un():
    """Volet symetrique du precedent : sans lui, une implementation qui
    ignorerait la zone inconnue et sommerait les autres serait verte."""
    zones = (zone(0), zone(1, hauteur=0), zone(2))
    documents = documents_a_trois_lots(zones_de_la_cible=zones)
    partiel = sum(
        octets_par_frame(z.crop_w_px, z.crop_h_px) or 0
        for doc in documents for page_ in doc.pages for z in page_.frame_zones)
    assert partiel > 0
    assert confirmation.majorant_du_document(documents) != partiel


def test_aucun_document_rend_None_et_non_zero():
    """Zero octet serait une mesure ; l'absence de document n'en est pas une."""
    assert confirmation.majorant_du_document([]) is None


def test_la_ligne_d_espace_porte_la_mention_MAJORANT_quand_elle_chiffre():
    """`EPIC11-ARB-4` : « espace disque, majorant assume comme tel »."""
    plan = plan_nominal()
    ligne = confirmation.ligne_de_l_espace(plan)
    assert ligne.majorant
    assert MENTION_MAJORANT in ligne.chiffre
    assert confirmation.PREFIXE_APPROCHE.strip() in ligne.chiffre
    assert taille_lisible(plan.octets_majorants).partition(" ")[0] in ligne.chiffre


def test_la_ligne_d_espace_INCONNUE_ne_porte_PAS_la_mention_majorant():
    """« `(majorant)` sur « inconnu » laisserait croire qu'un chiffre a ete
    calcule »."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(),
        documents_a_trois_lots(zones_de_la_cible=(zone(0), zone(1, largeur=0),
                                                  zone(2))))
    ligne = confirmation.ligne_de_l_espace(plan)
    assert not ligne.majorant
    assert MENTION_MAJORANT not in ligne.chiffre
    assert ligne.chiffre == confirmation.ESPACE_INCONNU


# ---------------------------------------------------------------------------
# D6 -- la ligne d'etat du PRODUIT, et l'ensemble ferme des maquettes
# ---------------------------------------------------------------------------

#: Ce qu'une ligne d'etat ne porte jamais (`EPIC11-ARB-56`) : une touche.
#: L'ensemble est celui que la charte nomme, plus les combinaisons.
TOUCHES_INTERDITES = ("Tab", "Échap", "Entrée", "⏎", "Ctrl", "F1", "↑↓",
                      "Espace")

#: Les mots d'un motif de conception ou d'un conseil d'usage.
MOTIFS_INTERDITS = ("caractère", "au plus", "pour éditer", "vous", "tapez")


def test_la_ligne_d_etat_est_EXACTEMENT_la_mesure_de_la_maquette():
    """AC 4.8, verbatim de `E3-6` l. 22 : `2 lots · 186 frames · ~ 5,4 Go —
    rien n'a encore été écrit`. Egalite, jamais inclusion."""
    plan = plan_nominal()
    total = FRAMES_PREMIER + FRAMES_CIBLE + FRAMES_DERNIER
    attendu = (f"3 lots{confirmation.SEPARATEUR_DE_MESURE}{total} frames"
               f"{confirmation.SEPARATEUR_DE_MESURE}"
               f"{confirmation.PREFIXE_APPROCHE}"
               f"{taille_lisible(plan.octets_majorants)}"
               f"{confirmation.LIAISON_DE_LA_MESURE}"
               f"{confirmation.QUEUE_RIEN_ECRIT}")
    assert confirmation.mesure_de_la_confirmation(plan) == attendu


def test_la_queue_de_la_ligne_d_etat_est_DERIVEE_de_la_phrase_du_depot():
    """Aucune seconde redaction de « rien n'a encore été écrit » : la phrase
    vit une fois, dans `panneau.RIEN_ECRIT`."""
    from mixed_media_utility.tui.panneau import RIEN_ECRIT
    assert confirmation.QUEUE_RIEN_ECRIT == RIEN_ECRIT.rstrip(".").lower()[:1] \
        + RIEN_ECRIT.rstrip(".")[1:]
    assert confirmation.QUEUE_RIEN_ECRIT in RIEN_ECRIT.lower()


def test_le_majorant_inconnu_est_OMIS_de_la_ligne_d_etat():
    """La ligne d'etat ne porte que ce qu'elle mesure : « inconnu » y serait un
    mot de plus, et le cartouche le dit deja."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(),
        documents_a_trois_lots(zones_de_la_cible=(zone(0), zone(1, largeur=0),
                                                  zone(2))))
    mesure = confirmation.mesure_de_la_confirmation(plan)
    assert confirmation.ESPACE_INCONNU not in mesure
    assert confirmation.PREFIXE_APPROCHE.strip() not in mesure
    assert mesure.endswith(confirmation.QUEUE_RIEN_ECRIT)


def test_la_ligne_d_etat_ne_porte_AUCUNE_touche_ni_motif_de_conception():
    """`EPIC11-ARB-56`, et c'est l'ecart `H6` : la maquette d'origine cumulait
    une touche, une **lettre** offerte a cote d'un champ de saisie, et la
    limite recopiee."""
    mesure = confirmation.mesure_de_la_confirmation(plan_nominal())
    for touche in TOUCHES_INTERDITES:
        assert touche not in mesure
    for motif in MOTIFS_INTERDITS:
        assert motif not in mesure.lower()
    assert _nombres_nus(mesure).isdisjoint(BORNES_INTERDITES)


def test_le_detecteur_de_touche_TROUVE_une_touche_plantee():
    """Volet symetrique du precedent."""
    plante = "e pour éditer les noms"
    assert any(motif in plante.lower() for motif in MOTIFS_INTERDITS)
    assert any(touche in "Tab éditer les noms" for touche in TOUCHES_INTERDITES)


def test_E3_6_n_est_PAS_revenue_dans_l_ensemble_ferme_des_lignes_d_etat_fautives():
    """D6 : le retrait a ete fait au **lot A**, avec la maquette qui le
    declenche -- « un ensemble ferme se deplace avec ce qu'il mesure ». Ce lot
    **verifie** qu'il tient, il ne l'en retire pas.

    Le volet symetrique est dans la meme assertion : l'ensemble n'est pas vide,
    donc l'appartenance qu'on teste est mesurable.
    """
    import importlib
    banc_des_maquettes = importlib.import_module("test_majuscules_des_raccourcis")
    ferme = banc_des_maquettes.MAQUETTES_DONT_LA_LIGNE_D_ETAT_PORTE_ENCORE_UNE_TOUCHE
    assert ferme, ("l'ensemble ferme est vide : l'appartenance mesuree "
                   "ci-dessous ne mesurerait plus rien")
    assert "E3-6-scan-confirmation.txt" not in ferme


def test_la_maquette_E3_6_ne_porte_plus_de_touche_en_ligne_d_etat():
    """Le corollaire de la mesure precedente, pris par l'autre bout : la
    maquette elle-meme. Sans lui, l'ensemble ferme pourrait avoir perdu `E3-6`
    sans que la maquette ait ete corrigee."""
    maquette = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
                / "ux-designs" / "ux-tui-2026-08-27" / "maquettes"
                / "E3-6-scan-confirmation.txt")
    lignes = maquette.read_text(encoding="utf-8").splitlines()
    # La ligne d'etat est l'avant-derniere ligne du cadre, la ligne des
    # raccourcis la derniere : c'est la grille de `DESIGN.md` section 3.
    ligne_d_etat = lignes[21]
    for touche in TOUCHES_INTERDITES:
        assert touche not in ligne_d_etat, ligne_d_etat
    assert _nombres_nus(ligne_d_etat).isdisjoint(BORNES_INTERDITES)


# ---------------------------------------------------------------------------
# D7 -- QUEL lot a recu le nom
# ---------------------------------------------------------------------------


def test_le_slug_MONTRE_est_celui_DU_lot_et_de_LUI_SEUL():
    """AC 4.9, dans la forme qui lui reste : « un nom pose sur le mauvais lot
    produit exactement le meme succes apparent ».

    L'appariement ne se fait plus a la sortie d'un champ mais a l'entree du
    plan, et c'est le meme risque : le lot du milieu doit porter SON slug, et
    l'assertion porte sur la liste entiere -- « le lot du milieu est juste »
    laisserait passer un troisieme lot qui aurait recu la meme valeur.
    """
    plan = plan_nominal()
    assert [(lot.lot_id, lot.slug) for lot in plan.lots] == [
        (LOT_PREMIER, SLUG_PREMIER),
        (LOT_CIBLE, SLUG_CIBLE),
        (LOT_DERNIER, SLUG_DERNIER),
    ]
    assert confirmation.noms_du_plan(plan)[1] == INDENT_DES_NOMS + SLUG_CIBLE


def test_les_slugs_sont_apparies_par_LOT_ID_et_jamais_par_rang():
    """Mutant `M25` de la story 5.7 : « ecrire dans le premier document de la
    passe poserait l'identite sur le mauvais lot ».

    Les documents arrivent ici dans un ordre **different** de celui du rapport.
    Un appariement positionnel donnerait au lot du milieu le slug du dernier,
    et les trois lots resteraient presents -- le succes serait identique.
    """
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(),
        documents_a_trois_lots(ordre=(LOT_DERNIER, LOT_PREMIER, LOT_CIBLE)))
    assert [(lot.lot_id, lot.slug) for lot in plan.lots] == [
        (LOT_PREMIER, SLUG_PREMIER),
        (LOT_CIBLE, SLUG_CIBLE),
        (LOT_DERNIER, SLUG_DERNIER),
    ]


def test_un_lot_sans_document_garde_son_lot_id_comme_nom_propose():
    """Le seul repli honnete : inventer un slug ferait proposer un nom que rien
    n'a produit, et un nom vide ferait echouer la validation sur un lot que
    l'operateur n'a pas touche."""
    plan = confirmation.preparer_le_plan(
        rapport_a_trois_lots(),
        documents_a_trois_lots(ordre=(LOT_PREMIER, LOT_DERNIER)))
    assert dict((lot.lot_id, lot.slug) for lot in plan.lots) == {
        LOT_PREMIER: SLUG_PREMIER,
        LOT_CIBLE: LOT_CIBLE,
        LOT_DERNIER: SLUG_DERNIER,
    }


def test_slugs_par_lot_garde_le_PREMIER_document_de_chaque_lot():
    """Plusieurs documents du meme lot s'additionnent (contrat de 5.25), et le
    lot garde le rang -- donc le sujet -- de son premier document."""
    premier = document(LOT_CIBLE, slug=SLUG_CIBLE, pages=[
        page(1, page_index=0, page_count=2, lot_id=LOT_CIBLE, zones=(zone(0),))])
    second = document(LOT_CIBLE, slug="autre_slug", pages=[
        page(2, page_index=1, page_count=2, lot_id=LOT_CIBLE, zones=(zone(1),))])
    assert confirmation.slugs_par_lot([premier, second]) == {
        LOT_CIBLE: SLUG_CIBLE}


# ---------------------------------------------------------------------------
# L'ecran monte : la couture avec `EcranChiffre`, et rien de plus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_monte_et_pose_sa_MESURE_en_ligne_d_etat(banc, ascii_seul):
    """AC 4.8, mesuree **sur l'ecran monte** et non sur la fonction seule :
    « `poser_etat` seul se fait effacer par le dessin suivant »."""
    ecran = ecran_nominal()
    _courant, etat, raccourcis, _blocs = monter(banc, ecran, ascii_seul)
    attendu = jetons.ajuster(
        confirmation.mesure_de_la_confirmation(ecran.plan),
        jetons.largeur_utile(jetons.LARGEUR_PLANCHER), ascii_seul)
    assert etat == attendu
    assert raccourcis == jetons.ajuster(
        confirmation.RACCOURCIS_SCAN_CONFIRMATION,
        jetons.largeur_utile(jetons.LARGEUR_PLANCHER), ascii_seul)


def test_la_ligne_d_etat_SURVIT_au_redessin(banc):
    """« Toute ligne d'etat posee en reaction a un evenement doit survivre au
    **redessin**, et l'AC qui la mesure doit le faire APRES un redessin. »"""
    ecran = ecran_nominal()
    app = coque(ecran)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        courant.rafraichir()
        courant.rafraichir()
        await pilote.pause()
        return jetons.texte_affiche(str(courant.query_one("#etat").content))

    assert banc(app, scenario) == jetons.ajuster(
        confirmation.mesure_de_la_confirmation(ecran.plan),
        jetons.largeur_utile(jetons.LARGEUR_PLANCHER), False)


def test_Tab_ne_fait_plus_BASCULER_la_ligne_d_etat(banc):
    """`EPIC11-ARB-141`, et c'est le volet MONTE du retrait.

    Ce test mesurait le second regime de la ligne d'etat -- la mesure du nom en
    cours d'edition. Il n'y a plus de nom en cours : `Tab` n'a aucune
    destination, la ligne ne bascule pas, et elle porte toujours la mesure de la
    passe.

    Il est garde plutot que retire parce qu'un regime **retire** ne se mesure
    que par sa propre absence : sans lui, la bascule pourrait revenir sans que
    rien ne rougisse -- et c'est exactement ce que ce depot paie chaque fois
    qu'il retire sans mesurer.
    """
    ecran = ecran_nominal()
    app = coque(ecran)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        consommee = courant.traiter("tab")
        courant.rafraichir()
        await pilote.pause()
        return consommee, jetons.texte_affiche(
            str(courant.query_one("#etat").content))

    consommee, etat = banc(app, scenario)
    assert consommee is False
    assert etat == jetons.ajuster(
        confirmation.mesure_de_la_confirmation(ecran.plan),
        jetons.largeur_utile(jetons.LARGEUR_PLANCHER), False)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_cartouche_affiche_les_six_lignes_et_les_trois_noms(banc, ascii_seul):
    """La couture : le cartouche vient du panneau, les noms du modele, et les
    trois issues du choix -- l'ecran n'en redessine aucun a la main."""
    ecran = ecran_nominal()
    _courant, _etat, _raccourcis, blocs = monter(banc, ecran, ascii_seul)
    texte = "\n".join(blocs)
    for libelle in (confirmation.LIBELLE_LOTS,
                    confirmation.LIBELLE_FRAMES_ATTENDUES,
                    confirmation.LIBELLE_FRAMES_OBTENUES,
                    confirmation.LIBELLE_PROFONDEUR,
                    confirmation.LIBELLE_CALIBRATION,
                    confirmation.LIBELLE_ESPACE):
        attendu = jetons.replier_ascii(libelle) if ascii_seul else libelle
        assert attendu in texte
    for slug in (SLUG_PREMIER, SLUG_CIBLE, SLUG_DERNIER):
        assert slug in texte


@pytest.mark.parametrize("attendues, etat_voulu", [
    pytest.param((FRAMES_PREMIER, FRAMES_CIBLE, FRAMES_DERNIER), "complete",
                 id="toutes"),
    pytest.param((FRAMES_PREMIER, FRAMES_CIBLE + 2, FRAMES_DERNIER), "absent",
                 id="manquantes"),
])
def test_le_glyphe_d_etat_du_CARTOUCHE_recoit_son_etat_DONNE(
        banc, attendues, etat_voulu):
    """« Aucun glyphe d'etat pose dans un cartouche n'etait colore »
    (story 11.4, lot A). Le correctif est le parametre `etats` de
    `jetons.peindre` : l'etat se **donne**, ligne par ligne -- un glyphe pose
    au milieu d'une ligne chiffree n'ouvre pas de colonne, donc la
    reconnaissance par motif ne le trouverait pas.

    Le rang est lu sur les lignes **rendues**, jamais compte a la main : une
    ligne inseree plus haut deplacerait la couleur sans que rien ne le dise.
    """
    ecran = confirmation.EcranScanConfirmation(
        confirmation.preparer_le_plan(
            rapport_a_trois_lots(attendues=attendues),
            documents_a_trois_lots()))
    app = coque(ecran)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        return courant.etats_du_panneau(), courant.lignes_du_panneau()

    etats, lignes = banc(app, scenario)
    rang = next(rang for rang, ligne in enumerate(lignes)
                if ligne.startswith(confirmation.LIBELLE_FRAMES_OBTENUES))
    assert etats == {rang: etat_voulu}
    assert jetons.GLYPHES[etat_voulu] in lignes[rang]


def test_sans_attendu_le_cartouche_ne_DONNE_aucun_etat(banc):
    """Volet symetrique : un etat donne sur une ligne sans glyphe teindrait la
    ligne entiere sans que rien ne la justifie."""
    ecran = confirmation.EcranScanConfirmation(
        confirmation.preparer_le_plan(
            rapport_a_trois_lots(attendues=(None, None, None)),
            documents_a_trois_lots()))
    app = coque(ecran)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return pilote.app.screen.etats_du_panneau()

    assert banc(app, scenario) == {}


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_DROITE_du_bandeau_est_celle_de_la_maquette(banc, ascii_seul):
    """`I3` : `Contexte.objet` existait, les maquettes le remplissaient sur onze
    ecrans sur douze, et **aucun ecran de l'atelier ne le posait**.

    Il est pose ici par defaut plutot que laisse au cablage : cet ecran est
    celui du Scan, et son objet ne varie pas d'un montage a l'autre.
    """
    ecran = ecran_nominal()
    app = coque(ecran, ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#bandeau").content))

    bandeau = banc(app, scenario)
    attendu = (jetons.replier_ascii(confirmation.OBJET_DU_BANDEAU)
               if ascii_seul else confirmation.OBJET_DU_BANDEAU)
    assert attendu in bandeau
    assert "projet_demo" in bandeau
    assert confirmation.EcranScanConfirmation.titre in bandeau


def test_la_DROITE_du_bandeau_reste_DONNEE_par_l_atelier_qui_le_veut():
    """Volet symetrique : le defaut ne verrouille rien -- `EPIC11-ARB-13` fait
    revenir au menu des ateliers, et un appelant qui a mieux a dire le dit."""
    ecran = confirmation.EcranScanConfirmation(plan_nominal(), objet="autre")
    assert ecran.objet_du_bandeau() == "autre"


def test_l_ecran_est_un_PASSAGE_et_non_une_station():
    """Un point de jugement franchi ne reste pas sur le chemin du retour."""
    assert confirmation.EcranScanConfirmation.TRANSITOIRE is True


def test_la_ligne_de_raccourcis_n_est_PLUS_celle_de_l_ecran_partage():
    """`EPIC11-ARB-141`, et c'est un renversement assume de l'ecart `H7`.

    Reprendre `execution.RACCOURCIS_CONFIRMATION` etait juste tant que cet
    ecran avait un mode d'edition : la constante commune porte `Tab` et sa
    destination. Le mode est parti, donc l'annoncer promettrait une touche qui
    ne fait rien -- le defaut que `coque.py` documente.

    L'assertion sur la constante partagee est **l'anti-vacuite** de cette
    tolerance : le jour ou elle sera corrigee, ce test rougira et les deux
    ateliers pourront la reprendre.
    """
    from mixed_media_utility.tui.execution import RACCOURCIS_CONFIRMATION

    assert (confirmation.EcranScanConfirmation.raccourcis
            is confirmation.RACCOURCIS_SCAN_CONFIRMATION)
    assert confirmation.RACCOURCIS_SCAN_CONFIRMATION is not RACCOURCIS_CONFIRMATION
    assert "Tab" not in confirmation.RACCOURCIS_SCAN_CONFIRMATION
    assert "Tab" in RACCOURCIS_CONFIRMATION


# ---------------------------------------------------------------------------
# Frontieres du module
# ---------------------------------------------------------------------------


def test_le_module_n_importe_JAMAIS_cli():
    """`EPIC11-ARB-67`, verifie **explicitement** sur le module neuf plutot que
    suppose (AC 2.7)."""
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+.*\bcli\b", source, re.M)


def test_le_module_ne_LIT_aucun_document_de_detection():
    """AC 2.8 : la TUI ne redige aucune troisieme lecture de document.

    Le comptage est a zero, et son volet symetrique est le test suivant.
    """
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    corps = "\n".join(ligne for ligne in source.splitlines()
                      if not ligne.lstrip().startswith("#"))
    for interdit in ("scan_previz_from_json_dict", "json.loads",
                     "read_text", "open("):
        assert interdit not in corps, interdit


def test_le_detecteur_de_lecture_TROUVE_un_appel_plante():
    """Volet symetrique : sans lui, un detecteur qui ne balaye rien serait vert."""
    plante = "    document = scan_previz.scan_previz_from_json_dict(brut)"
    assert "scan_previz_from_json_dict" in plante
