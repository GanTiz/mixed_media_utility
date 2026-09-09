# -*- coding: utf-8 -*-
"""Monter POUR DE VRAI les 69 ecrans du paquet TUI, dans TROIS regimes.

**Le trou que ce banc ferme, et le banc qui l'a nomme lui-meme.**
`test_atteignabilite_des_ecrans.py` mesure, en test executable, ce qu'il NE
mesure pas : « elle mesure une reference, pas une execution. Un
`if False: EcranX()` -- ou une branche morte, ou un rappel jamais appele --
suffit a rendre un ecran "atteint" ». Ses dix montees reelles couvrent les
**portes** et le disent ; elles ne couvrent pas le fond des ateliers.
`test_plancher_80x24.py` monte quatorze ecrans et nomme les trente-neuf autres
dans :data:`SANS_FABRIQUE`, « qu'il ne sait pas construire faute de donnee de
terrain ».

Ce fichier construit ces donnees. **Soixante-sept classes d'ecran sur
soixante-neuf sont montees ici**, et les deux qui ne le sont pas sont des bases
d'heritage dont la montee LEVE -- ce qui est mesure plutot que declare, de
sorte que la liste se perime bruyamment le jour ou l'une devient montable.

Ce que ce banc mesure, en cinq volets
-------------------------------------
1. **la montee ne plante pas** -- l'ecran est construit sur des donnees du
   produit et empile par `CoqueTui.descendre`, c'est-a-dire par la route que
   les ateliers empruntent, jamais par un `paliers=[...]` de banc ;
2. **le chrome n'est ni ampute ni deborde** au plancher -- bandeau, ligne
   d'etat et ligne de raccourcis, dans les quatre combinaisons de
   `--ascii` x `--sans-couleur` ;
3. **le centre tient dans ses dix-sept lignes** -- ce qui depasse n'est jamais
   dessine, et `textual` ne signale rien ;
4. **le bandeau garde sa DROITE** : l'ecran qui declare un objet travaille le
   voit en queue de son bandeau, dans les deux modes de repli. C'est la
   regression du 2026-09-06 mesuree sur soixante-sept ecrans au lieu de
   quatorze ;
5. **aucune touche annoncee ne fait planter l'ecran**, et `Tab journal` n'est
   annonce que la ou un journal existe.

**Les TROIS drapeaux varient, et dans les deux sens.** `ascii_seul` a mordu le
2026-09-06 sur onze ecrans montables sur quatorze ; `sans_couleur` etait
mesure « sans effet sur aucune largeur » sur **trois** ecrans et quatre
combinaisons, et ce banc porte cette mesure a soixante-sept ; la taille varie
entre le plancher `80x24` et une fenetre confortable `100x30`, un ecran qui
tient a l'une pouvant deborder l'autre.

**Ce banc ne recopie AUCUN litteral de maquette**, et c'est delibere plutot
que fortuit : tout ce qu'il asserte est **geometrique** -- des largeurs, des
hauteurs, une marque d'abregement en queue de ligne, une egalite entre deux
rendus du meme ecran. Un texte de maquette recopie ici serait un litteral de
plus a confronter a sa source ; il n'y en a pas un seul, et la seule chaine
que le banc reconnaisse est la marque d'abregement, qu'il ecrit lui-meme
(`…` / `...`) pour ne pas la relire de la surface mesuree.

**Ce que ce banc NE mesure PAS, dit plutot que tu** (mesure executable en fin
de fichier) :

* il ne mesure pas qu'une touche annoncee FASSE ce qu'elle annonce. Il mesure
  qu'elle ne plante pas. La difference a ete payee pendant l'ecriture : la
  plupart des touches d'un ecran passent par un rappel **injecte a la
  construction** (`sur_issue`, `sur_suite`, `continuer`, `retenir`), et un banc
  qui injecte un rappel muet mesure alors son propre rappel, pas l'ecran.
  Seule `Tab journal` est mesuree sur son effet, parce qu'elle est le seul
  geste dont la reponse est **interne** a l'ecran
  (`EcranResultat.basculer_le_journal`) ;
* il ne mesure pas les etats d'un ecran autres que celui de sa fabrique. Un
  ecran a des modes -- un refus d'affichage, une saisie en cours, un nom
  refuse -- que ce banc ne parcourt pas ; ceux-la vivent dans le banc propre
  a chaque ecran ;
* il ne mesure pas le regime SOUS le plancher, qui a son propre banc.

**Le terrain est un projet REEL, ecrit sur disque** (`_projet_montable` de
`test_atteignabilite_des_ecrans.py`, meme geste) : deux rushes et deux lots
**distinguables** -- deux geometries, deux cadences, quatre poids de fichier
tous differents. La regle des fabriques vaut ici comme ailleurs : un
remplissage uniforme rendrait toute permutation invisible.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import json
import pkgutil
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import project_maintenance                # noqa: E402
from mixed_media_utility.io import project_layout                  # noqa: E402
from mixed_media_utility.tui import rushes as rushes_mod           # noqa: E402
from mixed_media_utility.tui import (                              # noqa: E402
    coque, jetons, noms as noms_mod, panneau as panneau_mod, execution,
    atelier_exports_confirmation as exp_conf,
    atelier_exports_execution as exp_exec,
    atelier_exports_lot as exp_lot,
    atelier_exports_reglages as exp_regl,
    atelier_exports_resultat as exp_res,
    atelier_exports_versions as exp_vers,
    atelier_extraction as extr,
    atelier_extraction_ecriture as extr_ecr,
    atelier_pdf_calibration as pdf_cal,
    atelier_pdf_confirmation as pdf_conf,
    atelier_pdf_execution as pdf_exec,
    atelier_pdf_lots as pdf_lots,
    atelier_pdf_reglages as pdf_regl,
    atelier_pdf_resultat as pdf_res,
    atelier_pdf_versions as pdf_vers,
    atelier_scan as scan,
    atelier_scan_calibrate as scan_cal,
    atelier_scan_completion as scan_comp,
    atelier_scan_confirmation as scan_conf,
    atelier_scan_detection as scan_det,
    atelier_scan_rapport as scan_rap,
    atelier_scan_resultat as scan_res,
    projet_suppression as suppr,
    cadences, manuel, palier_profil_defaut, palier_projet,
    projet_inventaire, projets,
)

# ---------------------------------------------------------------------------
# Les bornes, ECRITES EN CLAIR -- meme motif que `test_plancher_80x24.py` : les
# relire du module mesure ferait de tout ce fichier une tautologie.
# ---------------------------------------------------------------------------

#: Le plancher de `EPIC11-ARB-21`, et une fenetre confortable au-dessus.
PLANCHER = (80, 24)
CONFORTABLE = (100, 30)

#: Colonnes ecrivables au plancher, une fois le cadre (1+1) et les marges (1+1)
#: retires ; et lignes de centre une fois le cadre, les deux filets, le
#: bandeau, la ligne d'etat et la ligne de raccourcis retires.
COLONNES_UTILES = {80: 76, 100: 96}
LIGNES_DE_CENTRE = {24: 17, 30: 23}

# ---------------------------------------------------------------------------
# Les textes que le PRODUIT publie -- jamais recopies d'un dessin
# ---------------------------------------------------------------------------
#
# `test_frontiere_des_maquettes_recopiees.py` mesure une propriete que ce banc
# doit tenir plus que tout autre : une fabrique alimentee par un texte recopie
# d'une maquette mesure **la recopie**, pas le produit. Un libelle renomme dans
# le paquet laisserait alors soixante-sept ecrans verts sur l'ancien mot.
#
# Le geste est donc le meme partout ici : la valeur est celle du **module qui
# la publie**, et elle suit un renommage sans qu'on y pense. Ce banc n'ouvre
# aucun dessin -- il n'en a pas besoin, et le rester le laisse MESURE par la
# frontiere plutot qu'exempte par elle.


def annonce_de(jeton: str, ligne: str) -> str:
    """`Tab journal` -- le jeton et son libelle, LUS d'une vraie ligne.

    Extraire plutot que recopier : le libelle qui suit un jeton est ce que la
    ligne de raccourcis du produit ecrit, et l'extraction le suit s'il change.
    """
    mots = ligne.split()
    return f"{jeton} {mots[mots.index(jeton) + 1]}"


#: L'annonce du journal, telle que la ligne de raccourcis d'un resultat qui en
#: porte un l'ecrit. C'est par elle que le volet `Q21` reconnait un ecran qui
#: promet un journal -- et il doit la reconnaitre au mot du produit.
ANNONCE_DU_JOURNAL = annonce_de("Tab",
                                execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL)

#: La seconde issue des ecrans de resultat. Elle n'est publiee par aucun
#: module -- chaque ecran la redit --, donc elle est ecrite ici une fois, et
#: aucun dessin ne la porte : la frontiere le mesure.
SUITE_ATELIERS = "Revenir aux ateliers"

#: Les deux lots que `terrain` ecrit dans le projet. Une fabrique qui parle
#: d'un lot emploie CEUX-LA : nommer un lot que le projet n'a pas, c'est
#: montrer un ecran dans un etat que le produit ne produit pas.
LOT_PREMIER = "a-premier_25"
LOT_SECOND = "z-second_8"

#: Les deux marques d'abregement. **Ecrites ici**, jamais relues de `jetons` :
#: c'est par elles qu'on reconnait une ligne amputee, donc les relire de la
#: surface mesuree rendrait la detection aveugle a son propre deplacement.
MARQUE = {False: "…", True: "..."}


# ---------------------------------------------------------------------------
# LES FABRIQUES -- une par classe d'ecran, sur des donnees du PRODUIT
# ---------------------------------------------------------------------------

RIEN = lambda *a, **k: None

# --- briques communes -------------------------------------------------------

def panneau_a_trois_lignes():
    return panneau_mod.Panneau("A ecrire", [
        panneau_mod.LigneChiffree("Lots crees", 2, "lots"),
        panneau_mod.LigneChiffree("Frames ecrites", 186, "frames"),
        panneau_mod.LigneChiffree("Espace disque", "~ 3,1", "Go", majorant=True),
    ])


def panneau_mesure():
    """Un panneau SANS majorant : ce qu'un ecran de RESULTAT accepte."""
    return panneau_mod.Panneau("Ecrit", [
        panneau_mod.LigneChiffree("Lots ecrits", 2, "lots"),
        panneau_mod.LigneChiffree("Frames ecrites", 186, "frames"),
        panneau_mod.LigneChiffree("Espace occupe", "3,08", "Go"),
    ])

def choix_a_trois_issues():
    return panneau_mod.ChoixExclusif([
        panneau_mod.Issue("ecrire", "Ecrire les frames", ecrit=True),
        panneau_mod.Issue("modifier", "Modifier les reglages"),
        panneau_mod.Issue("annuler", "Annuler"),
    ])

def modele_de_noms():
    return noms_mod.ModeleNoms([noms_mod.NomEditable("projet_demo_plan-04_25"),
                                noms_mod.NomEditable("projet_demo_plan-04_12p5")])

def surface(unite="frames"):
    s = execution.SurfaceExecution(unite)
    s.declarer_la_passe("Extraction", [("plan-04_25", 124), ("plan-04_12p5", 41)])
    return s

# --- fabriques --------------------------------------------------------------

#: **La table des fabriques**, une entree par classe d'ecran. Chaque fabrique
#: recoit `(classe, terrain)` et rend une instance construite sur des DONNEES
#: DU PRODUIT -- dataclasses du paquet, inventaire lu du coeur, projet ecrit
#: sur disque --, jamais sur un etat que le produit ne produit pas.
FABRIQUES: dict[tuple[str, str], object] = {}

# coque
FABRIQUES[("coque", "EcranPasEncore")] = lambda cls, t: cls(
    "la designation d'un fichier", quand="story 11.11")
FABRIQUES[("coque", "PalierTemoin")] = lambda cls, t: cls("Ateliers", "Q quitter")

# execution.py -- la famille partagee
FABRIQUES[("execution", "EcranChiffre")] = lambda cls, t: cls(
    panneau_a_trois_lignes(), choix_a_trois_issues(), modele_de_noms(),
    objet="plan-04 · 2 lots")
FABRIQUES[("execution", "PanneauConfirmation")] = FABRIQUES[("execution", "EcranChiffre")]
FABRIQUES[("execution", "EcranEcrasement")] = FABRIQUES[("execution", "EcranChiffre")]
FABRIQUES[("execution", "EcranInterruption")] = lambda cls, t: cls(
    panneau_a_trois_lignes())
FABRIQUES[("execution", "EcranExecution")] = lambda cls, t: cls(
    surface(), "Extraction", objet="plan-04 · lot 1 sur 2")
#: L'ecran de passe de la calibration : une SOUS-CLASSE d'`EcranExecution`
#: construite a la demande par `atelier_scan_calibrate` (voir
#: `_forcer_les_classes_PARESSEUSES`). Meme constructeur que sa base, donc la
#: meme fabrique -- ce qu'elle ajoute est son cycle de vie (`on_mount` /
#: `on_unmount`), c'est-a-dire justement ce que le montage reel mesure.
FABRIQUES[("atelier_scan_calibrate", "_CLASSE_DE_L_ECRAN_DE_PASSE")] = (
    lambda cls, t: cls(surface(), "Calibration", objet="mire · 1 page"))

FABRIQUES[("execution", "EcranResultat")] = lambda cls, t: cls(
    panneau_mesure(),
    suites=[exp_res.SUITE_DOSSIER, SUITE_ATELIERS],
    sur_suite=RIEN, objet="plan-04 · 2 lots")
FABRIQUES[("execution", "EcranRefus")] = lambda cls, t: cls(
    "REFUS_SOURCE_ABSENTE",
    "Le rush designe n'existe plus a l'emplacement enregistre.",
    conserve=[f"le lot {LOT_PREMIER}", "les frames deja extraites"],
    non_ecrit=["le master mp4", "les planches a imprimer"],
    suites=["Revoir la source", "Abandonner l'extraction"])

# --- atelier Exports --------------------------------------------------------

def master_a_ecrire():
    return exp_conf.MasterAEcrire(
        nom="projet_demo_plan-04_25.mov", lot_id="plan-04_25",
        lot_state="frames_written", profil="prores_hq", conteneur="mov",
        colorimetrie="rec709", geometrie=(1920, 1080), source=(1920, 1080),
        cadence="25", echantillons=124, frames=124, attendues=124,
        octets_majorants=470_000_000, timecode="01:00:00:00")

FABRIQUES[("atelier_exports_confirmation", "EcranExportsConfirmation")] = \
    lambda cls, t: cls(master_a_ecrire(), sur_issue=RIEN)

def passage_de_l_encodage():
    return exp_exec.PassageDeLEncodage(
        lot_id="plan-04_25", frames=124,
        nom_du_master="projet_demo_plan-04_25.mov",
        dossier="output-masters", etape="encodage", jalon=(41, 124), pas=3,
        mesure=exp_exec.MesureDuMaster(echantillons=41, duree_s=1.64,
                                       poids_octets=137_000_000))

FABRIQUES[("atelier_exports_execution", "EcranEncodageEnCours")] = \
    lambda cls, t: cls(passage_de_l_encodage(), RIEN)
FABRIQUES[("atelier_exports_execution", "EcranInterruptionDeLEncodage")] = \
    lambda cls, t: cls(panneau_a_trois_lignes(), RIEN)

def liste_des_lots_a_encoder(t):
    lots = [
        exp_lot.LotAListe({"lot_id": "a-premier_25", "rush_id": "a-premier",
                           "fps_target": 25, "expected_frame_count": 124,
                           "output_frames_dir": "output-frames/a-premier_25",
                           "state": "frames_written"}, t.projet),
        exp_lot.LotAListe({"lot_id": "m-milieu_12p5", "rush_id": "m-milieu",
                           "fps_target": 12.5, "expected_frame_count": 41,
                           "output_frames_dir": "output-frames/m-milieu_12p5",
                           "state": "frames_written"}, t.projet),
        exp_lot.LotAListe({"lot_id": "z-dernier_8", "rush_id": "z-dernier",
                           "fps_target": 8, "expected_frame_count": 60,
                           "output_frames_dir": "output-frames/z-dernier_8",
                           "state": "frames_written"}, t.projet),
    ]
    return exp_lot.ListeDesLotsAEncoder(lots, manifeste={}, project_dir=t.projet,
                                        curseur=1)

FABRIQUES[("atelier_exports_lot", "EcranDesLotsAEncoder")] = \
    lambda cls, t: cls(liste_des_lots_a_encoder(t), continuer=RIEN)

FABRIQUES[("atelier_exports_reglages", "EcranReglagesDeL_encodage")] = \
    lambda cls, t: cls(exp_regl.ReglagesDeL_encodage(
        exp_regl.LotAEncoder("plan-04_25", 124,
                             {"lot_id": "plan-04_25", "fps_target": 25}),
        mesure=exp_regl.MesureDuMaster(echantillons=41, duree_s=1.64,
                                       poids_octets=137_000_000)),
        continuer=RIEN)

def master_ecrit(t):
    return exp_res.MasterEcrit(
        nom="projet_demo_plan-04_25.mov", chemin=t.projet / "output-masters"
        / "projet_demo_plan-04_25.mov", dossier="output-masters",
        octets=137_000_000, echantillons=124, cadence="25", duree_s=4.96,
        timecode="01:00:00:00", etat_du_lot="master_written",
        duree_d_encodage_s=12.5, frames=124, lot_id="plan-04_25")

FABRIQUES[("atelier_exports_resultat", "EcranResultatDuMaster")] = \
    lambda cls, t: cls(master_ecrit(t),
                       suites=[exp_res.SUITE_DOSSIER, SUITE_ATELIERS],
                       sur_suite=RIEN)

FABRIQUES[("atelier_exports_versions", "EcranMasterExistant")] = \
    lambda cls, t: cls(exp_vers.MasterEnConflit(
        nom="projet_demo_plan-04_25.mov",
        nom_propose="projet_demo_plan-04_25_v2.mov",
        lot_id="plan-04_25", rang=1, rang_propose=2, profil="prores_hq",
        geometrie=(1920, 1080), echantillons=124, cadence="25",
        duree_s=4.96, poids_octets=137_000_000,
        quand="2026-09-05 14:32", quand_court="05/09 14:32"),
        retenir=RIEN)

# --- atelier Extraction -----------------------------------------------------

def source_sondee(t):
    return extr.SourceSondee(video_path=t.projet / "rushes" / "plan-04.mov",
                             fps_source=Fraction(25, 1),
                             source_frame_count=1240,
                             source_start_timecode="01:00:00:00")

def trois_cadences():
    return (cadences.Cadence(Fraction(25, 1), "25 im/s", compte=124),
            cadences.Cadence(Fraction(25, 2), "12,5 im/s", compte=62),
            cadences.Cadence(Fraction(8, 1), "8 im/s", compte=40))

FABRIQUES[("atelier_extraction", "EcranCadences")] = lambda cls, t: cls(
    source_sondee(t), previsualiser=RIEN, extraire=RIEN,
    verifier_l_affichage=lambda: None)
FABRIQUES[("atelier_extraction", "EcranChoixDesCadences")] = lambda cls, t: cls(
    trois_cadences(), cadences.Validation(cochees=trois_cadences()[1:]),
    nommer=lambda c: "projet_demo_plan-04_" + c.libelle.split()[0],
    confirmer=RIEN, octets_par_frame=6_220_800)
FABRIQUES[("atelier_extraction", "EcranDeclaration")] = lambda cls, t: cls(
    declaration_preparee(t), rang=2, sur_issue=RIEN)
FABRIQUES[("atelier_extraction", "EcranRefusDeConflit")] = lambda cls, t: cls(
    rushes_mod.Refus("REFUS_RUSH_DEJA_DECLARE",
                 "Ce fichier est deja declare sous le rush plan-04."),
    t.projet / "rushes" / "plan-04.mov", sur_issue=RIEN)
FABRIQUES[("atelier_extraction", "EcranRefusRelink")] = lambda cls, t: cls(
    rushes_mod.Refus("REFUS_RELINK_TAILLE",
                 "Le fichier designe n'a pas la meme taille que l'original."),
    rush_id="plan-04", mode="retrouver", reprendre=RIEN)
FABRIQUES[("atelier_extraction", "EcranRushes")] = lambda cls, t: cls(t.projet)

def declaration_preparee(t):
    from mixed_media_utility.declaration_de_rush import DeclarationPreparee
    from mixed_media_utility.io.extraction_manifest import RushRecord
    champs = {"source_codec": "prores_ks", "source_pix_fmt": "yuv422p10le",
              "source_color_primaries": "bt709", "source_color_trc": "bt709",
              "source_colorspace": "bt709", "source_color_range": None}
    record = RushRecord(
        rush_id="plan-04", source_name="plan-04.mov", fps_source=25.0,
        source_width=1920, source_height=1080, source_fields=champs,
        source_start_timecode="01:00:00:00", source_parent="hd",
        source_path=str(t.projet / "rushes" / "plan-04.mov"),
        source_frame_count=6300, source_frame_count_is_exact=True)
    return DeclarationPreparee(
        project_dir=t.projet, manifest_path=t.projet / "project.json",
        project_id="projet_demo", rush_id="plan-04", rush_id_derive="plan-04",
        homonymie_levee=False, source_parent="hd", source_name="plan-04.mov",
        source_path=str(t.projet / "rushes" / "plan-04.mov"),
        fps_source=25.0, source_width=1920, source_height=1080,
        source_start_timecode="01:00:00:00", cardinal_de_frames=6300,
        duree_source_secondes=252.0, separation_forcee=False, record=record)

def plan_d_extraction(t):
    return extr_ecr.PlanExtraction(
        dossier_projet=t.projet, rush_id="plan-04",
        video_path=t.projet / "rushes" / "plan-04.mov",
        lots=(extr_ecr.LotPrevu(25.0, 124, "plan-04_25",
                                t.projet / project_layout.EXTRACT_FRAMES_DIRNAME / "plan-04_25"),
              extr_ecr.LotPrevu(12.5, 41, "plan-04_12p5",
                                t.projet / project_layout.EXTRACT_FRAMES_DIRNAME / "plan-04_12p5",
                                deja_present=True)),
        source_in_timecode="01:00:00:00", source_out_timecode="01:00:04:23",
        octets_par_frame=6_220_800)

FABRIQUES[("atelier_extraction_ecriture", "EcranExtractionConfirmation")] = \
    lambda cls, t: cls(panneau_a_trois_lignes(), choix_a_trois_issues(),
                       sur_issue=RIEN, plan=plan_d_extraction(t),
                       objet="plan-04 · 2 lots")
FABRIQUES[("atelier_extraction_ecriture", "EcranExtractionEcrasement")] = \
    FABRIQUES[("atelier_extraction_ecriture", "EcranExtractionConfirmation")]

# --- atelier PDF ------------------------------------------------------------

def donnees_de_la_mire():
    return pdf_cal.donnees_imposees()

FABRIQUES[("atelier_pdf_calibration", "EcranMireConfirmation")] = lambda cls, t: cls(
    pdf_cal.FormulaireDeLaMire(chaine="epson-v850", commentaire="banc du studio"),
    "projet_demo", donnees_de_la_mire(), RIEN)
FABRIQUES[("atelier_pdf_calibration", "EcranMireExiste")] = lambda cls, t: cls(
    pdf_cal.MirePresente(t.projet / "mires" / "mire_epson-v850.pdf",
                         quand=1_757_000_000.0),
    "epson-v850", donnees_de_la_mire(), RIEN)
FABRIQUES[("atelier_pdf_calibration", "EcranMireEcrite")] = lambda cls, t: cls(
    panneau_mesure(),
    suites=[pdf_cal.SUITE_DOSSIER, SUITE_ATELIERS], sur_suite=RIEN)

def plan_des_planches(t):
    from mixed_media_utility import page_templates
    return pdf_conf.PlanDesPlanches(
        planches=(pdf_conf.PlancheAEcrire("a-premier_25", "projet_demo_a-premier_25_planches.pdf", 21, 124, 2),
                  pdf_conf.PlancheAEcrire("m-milieu_12p5", "projet_demo_m-milieu_12p5_planches.pdf", 7, 41, 1),
                  pdf_conf.PlancheAEcrire("z-dernier_8", "projet_demo_z-dernier_8_planches.pdf", 10, 60, 0)),
        marge=page_templates.DEFAULT_MARGIN_PRESET,
        dossier_projet=t.projet, octets_majorants=470_000_000)

FABRIQUES[("atelier_pdf_confirmation", "EcranPdfConfirmation")] = lambda cls, t: cls(
    plan_des_planches(t), sur_issue=RIEN)

def passe_de_generation():
    return pdf_exec.PasseDeGeneration(
        lots=(pdf_exec.LotEnGeneration("a-premier_25", 21, "A4-2f", 1),
              pdf_exec.LotEnGeneration("m-milieu_12p5", 7, "A4-2f", 2),
              pdf_exec.LotEnGeneration("z-dernier_8", 10, "A4-2f", 3)),
        rang_du_lot_courant=1, pages_du_lot_courant=3, temps_restant=42.0)

FABRIQUES[("atelier_pdf_execution", "EcranGenerationDesPlanches")] = lambda cls, t: cls(
    surface("pages"), passe_de_generation(), RIEN, objet="3 lots · 38 pages")
FABRIQUES[("atelier_pdf_execution", "EcranInterruptionDeLaGeneration")] = lambda cls, t: cls(
    passe_de_generation(), RIEN)

def liste_de_lots_a_planches():
    return pdf_lots.ListeDeLots([
        pdf_lots.Lot("a-premier_25", 124, "2026-09-01"),
        pdf_lots.Lot("m-milieu_12p5", 41, "2026-09-03", coche=True),
        pdf_lots.Lot("z-dernier_8", 60, "2026-09-05"),
    ], curseur=1)

FABRIQUES[("atelier_pdf_lots", "EcranLotsAPlanches")] = lambda cls, t: cls(
    liste_de_lots_a_planches(), continuer=RIEN)

#: **Deux lots aux identifiants de la maquette, et l'ecran mord quand meme en
#: ASCII.** Sa ligne d'etat enumere un segment PAR LOT et croit sans borne :
#: 76 colonnes en UTF-8 -- la borne exacte, elle tient au caractere pres -- et
#: 77 une fois repliee, donc amputee. C'est un defaut du PRODUIT, porte en
#: dette sous `MONTEE-2`, et il est **tolere nommement** dans
#: :data:`AMPUTATIONS_TOLEREES` plutot qu'evite en montant un seul lot : une
#: fabrique qui contournerait le defaut ne le mesurerait plus, et la regle des
#: fabriques veut de toute facon deux elements distinguables.
FABRIQUES[("atelier_pdf_reglages", "EcranReglagesDesPlanches")] = lambda cls, t: cls(
    pdf_regl.ReglagesDesPlanches(
        lots=(pdf_regl.LotAPlanches("plan-04_25", 124),
              pdf_regl.LotAPlanches("plan-04_12p5", 41))),
    continuer=RIEN)

def table_des_ecrits():
    return pdf_res.TableDesEcrits(
        planches=(pdf_res.PlancheEcrite("projet_demo_a-premier_25_planches.pdf", 21, 1),
                  pdf_res.PlancheEcrite("projet_demo_m-milieu_12p5_planches.pdf", 7, 2, "_v2"),
                  pdf_res.PlancheEcrite("projet_demo_z-dernier_8_planches.pdf", 10, 3)),
        frames=225, curseur=1)

FABRIQUES[("atelier_pdf_resultat", "EcranResultatDesPlanches")] = lambda cls, t: cls(
    table_des_ecrits(), informations=(("Dossier", "sheets"),),
    suites=[pdf_res.SUITE_DOSSIER, SUITE_ATELIERS], sur_suite=RIEN)

def tirages_en_conflit():
    return (pdf_vers.TirageEnConflit("projet_demo_a-premier_25_planches.pdf",
                                     "a-premier_25", 1, 2, pages=21, frames=124,
                                     poids_mo=12, quand="2026-09-01 10:02",
                                     quand_court="01/09 10:02"),
            pdf_vers.TirageEnConflit("projet_demo_m-milieu_12p5_planches.pdf",
                                     "m-milieu_12p5", 2, 3, pages=7, frames=41,
                                     poids_mo=4, quand="2026-09-03 18:41",
                                     quand_court="03/09 18:41", scanne=True,
                                     quand_scanne="04/09 09:15"))

FABRIQUES[("atelier_pdf_versions", "EcranConflitDeTirage")] = lambda cls, t: cls(
    pdf_vers.PasseDeConflits(tirages_en_conflit(), rang_courant=1), retenir=RIEN)
FABRIQUES[("atelier_pdf_versions", "EcranRangsEpuises")] = lambda cls, t: cls(
    tirages_en_conflit()[1], "REFUS_RANGS_EPUISES", retenir=RIEN)

# --- atelier Scan -----------------------------------------------------------

def source_designee(t):
    from mixed_media_utility import scan_ingest
    return scan.SourceDesignee(
        chemin=t.projet / project_layout.SCANS_DIRNAME / "planche-04.pdf",
        mesure=scan_ingest.SourceMesuree(forme="pdf", cardinal=6, octets=8_400_000,
                                         dpi=300.0, fichiers=1))

def formulaire_de_calibration(t):
    return scan_cal.FormulaireDeCalibration(
        scan=source_designee(t), dpi="300", etiquette="epson-v850",
        commentaire="banc du studio")

FABRIQUES[("atelier_scan_calibrate", "EcranCalibrerLaChaine")] = lambda cls, t: cls(
    t.projet, calibrer=RIEN)
FABRIQUES[("atelier_scan_calibrate", "EcranDeJugement")] = lambda cls, t: cls(
    "Profil deja present", "Un profil porte deja ce radical.",
    choix_a_trois_issues(), retenir=RIEN)
FABRIQUES[("atelier_scan_calibrate", "EcranCalibrationAConfirmer")] = lambda cls, t: cls(
    formulaire_de_calibration(t), sur_issue=RIEN, objet="epson-v850 · 300 dpi")
FABRIQUES[("atelier_scan_calibrate", "EcranCollisionDeProfil")] = lambda cls, t: cls(
    scan_cal.CollisionDeProfil("epson-v850", "epson-v850"), retenir=RIEN)
FABRIQUES[("atelier_scan_calibrate", "EcranRefusDeCalibration")] = lambda cls, t: cls(
    scan_cal.PasseDeCalibration(motif="La mire n'a pas ete reconnue.",
                                chaine="epson-v850"), retenir=RIEN)
FABRIQUES[("atelier_scan_calibration", "EcranChoixDeCalibration")] = lambda cls, t: cls(
    t.projet, retenir=RIEN, lots=3, dpi_du_scan=300)

def page_muette():
    return scan_rap.PageMuette(read_rank=2, fichier="page-0002.tiff",
                               code="QR_ILLISIBLE")

FABRIQUES[("atelier_scan_completion", "EcranCompletionQr")] = lambda cls, t: cls(
    page_muette(), {"project_id": "projet_demo", "lots": []}, poser=RIEN,
    pages_lues=(scan_comp.PageLue(1, 1, 6, "page-0001.tiff"),
                scan_comp.PageLue(3, 3, 6, "page-0003.tiff")),
    chemin_du_scan=t.projet / project_layout.SCANS_DIRNAME / "planche-04.pdf")

def plan_d_ecriture_confirmation():
    return scan_conf.PlanDEcriture(
        lots=(scan_conf.LotAEcrire("a-premier_25", "ingest_du_25", 5, 5),
              scan_conf.LotAEcrire("m-milieu_12p5", "ingest_du_12p5", 3, 4),
              scan_conf.LotAEcrire("z-dernier_8", "ingest_du_8", 9, 9)),
        octets_majorants=470_000_000, calibration="epson-v850")

FABRIQUES[("atelier_scan_confirmation", "EcranScanConfirmation")] = lambda cls, t: cls(
    plan_d_ecriture_confirmation(), sur_issue=RIEN)

FABRIQUES[("atelier_scan_detection", "EcranConflitDeDetection")] = lambda cls, t: cls(
    scan_det.ConflitDeDetection("ingest_du_25", 6),
    scan_det.RefusDeDetection("REFUS_SLUG_DEJA_PRESENT",
                              "Un scan porte deja ce slug."), retenir=RIEN)
FABRIQUES[("atelier_scan_detection", "EcranDetectionEnCours")] = lambda cls, t: cls(
    surface("pages"), "Detection", RIEN, objet="planche-04 · 6 pages")
FABRIQUES[("atelier_scan_detection", "EcranInterruptionDeDetection")] = lambda cls, t: cls(
    panneau_a_trois_lignes(), RIEN)

FABRIQUES[("atelier_scan_ecriture", "EcranEcritureDuScan")] = lambda cls, t: cls(
    surface("frames"), "Ecriture", RIEN, objet="3 lots · 17 frames",
    compter_le_disque=lambda: 8, frames_du_plan=17)
FABRIQUES[("atelier_scan_ecriture", "EcranInterruptionDeLEcriture")] = lambda cls, t: cls(
    panneau_a_trois_lignes(), 8, RIEN)

FABRIQUES[("atelier_scan_parcours", "EcranCollisionDuScan")] = lambda cls, t: cls(
    scan_cal.CollisionDeProfil("epson-v850", "epson-v850"),
    retenir=RIEN, abandonner=RIEN)
FABRIQUES[("atelier_scan_parcours", "EcranRapportDeDetection")] = lambda cls, t: cls(
    rapport_de_detection(), sur_issue=RIEN, document="planche-04.pdf")

def passe_de_calibration(t):
    """Une passe de calibration REUSSIE, avec ses cardinaux.

    Le profil est le vrai `ProfilDeChaineConsigne` du coeur ; ses deux champs
    opaques (`lot_correction`, `document`) sont typés `object` par la classe
    elle-meme, donc les porter en objets nus n'est pas une doublure -- c'est
    exactement ce que le contrat annonce. Les valeurs sont **longues et
    distinguables** : un cartouche mesure sur des valeurs courtes ne pourrait
    pas deborder, donc ne mesurerait rien.
    """
    from types import SimpleNamespace

    from mixed_media_utility.scan_calibrate import ProfilDeChaineConsigne

    profil = ProfilDeChaineConsigne(
        profile_path=(t.projet / project_layout.VERSIONS_DIRNAME
                      / "calibration" / "epson-v850-papier-mat-310g.json"),
        chain_id="epson-v850_papier-mat-310g_2026-08",
        etiquette="epson v850 · papier mat 310 g",
        commentaire="banc du studio, lampe eteinte, vitre nettoyee",
        lot_correction=SimpleNamespace(read_patch_count=164,
                                       retained_patch_count=161),
        document={"acceptance": {"mean_delta_e_before": 4.27}})
    return scan_cal.PasseDeCalibration(
        profil=profil, chaine="epson-v850_papier-mat-310g_2026-08",
        recalibration=True, date_precedente="28/08", date_ecrite="06/09")


FABRIQUES[("atelier_scan_calibrate", "EcranCalibrationEcrite")] = lambda cls, t: cls(
    scan_cal.panneau_du_resultat(passe_de_calibration(t), t.projet),
    scan_cal.suites_du_resultat(), sur_suite=RIEN)


def autres_profils_de_la_chaine(t):
    """DEUX profils anciens, distinguables -- le regime que l'ecran nomme.

    La regle des fabriques appliquee au point de jugement d'`EPIC11-ARB-261` :
    :func:`phrase_de_la_chaine_deja_calibree` a **deux redactions**, singulier
    et pluriel, et une fabrique mono-element ne monterait jamais la seconde.
    Deux noms differents, donc, et non deux fois le meme -- une jointure qui
    perdrait un element se verrait.
    """
    calibration = (t.projet / project_layout.VERSIONS_DIRNAME / "calibration")
    return [calibration / "epson-v850-papier-mat-310g.json",
            calibration / "epson-v850-papier-brillant-250g.json"]


FABRIQUES[("atelier_scan_calibrate", "EcranChaineDejaCalibree")] = \
    lambda cls, t: cls(passe_de_calibration(t),
                       autres_profils_de_la_chaine(t), retenir=RIEN)
FABRIQUES[("atelier_scan_parcours", "EcranChaineDejaCalibreeDuScan")] = \
    lambda cls, t: cls(passe_de_calibration(t),
                       autres_profils_de_la_chaine(t), retenir=RIEN,
                       poursuivre=RIEN)

#: `EPIC11-ARB-267`. Les planches etrangeres portent DEUX projets
#: distinguables et TROIS pages : une fabrique mono-element ne demasquerait ni
#: le dedoublonnage ni le pluriel du cartouche.
FABRIQUES[("atelier_scan_detection", "EcranAdoptionDeLaPlanche")] = \
    lambda cls, t: cls(
        scan_det.PlanchesEtrangeres(projets=("aa_voisin", "zz_ailleurs"),
                                    pages=3),
        retenir=RIEN)

FABRIQUES[("atelier_scan_resultat", "EcranResultatDuScan")] = lambda cls, t: cls(
    panneau_mesure(),
    suites=[scan_res.SUITE_DOSSIER, SUITE_ATELIERS], sur_suite=RIEN)

# --- projet / suppression ---------------------------------------------------

def rapport_de_suppression():
    return project_maintenance.RapportSuppression(
        cible="lot:a-premier_25",
        fichiers_a_supprimer=("extract-frames/a-premier_25/f0.tiff",
                              "extract-frames/a-premier_25/f1.tiff"),
        dry_run=True, rangs_liberables=(2, 3), rang_vise=2)

def plan_de_suppression(t):
    return suppr.PlanDeSuppression(
        projet=t.projet,
        cible={"kind": "lot", "lot_id": "a-premier_25"},
        libelle="le lot a-premier_25",
        rapport=rapport_de_suppression(), poids=470_000_000,
        groupes=(suppr.GroupeEmporte("frames extraites", 124, 320_000_000),
                 suppr.GroupeEmporte("planches", 3, 12_000_000)))

FABRIQUES[("projet_suppression", "EcranSuppressionConfirmation")] = lambda cls, t: cls(
    plan_de_suppression(t), sur_issue=RIEN)
FABRIQUES[("projet_suppression", "EcranSuppressionEnCours")] = lambda cls, t: cls(
    plan_de_suppression(t), 3)
FABRIQUES[("projet_suppression", "EcranReussiteDeSuppression")] = lambda cls, t: cls(
    plan_de_suppression(t),
    project_maintenance.RapportSuppression(
        cible="lot:a-premier_25",
        fichiers_a_supprimer=("extract-frames/a-premier_25/f0.tiff",
                              "extract-frames/a-premier_25/f1.tiff"),
        dry_run=False, supprime=True, rang_libere=True, rang_vise=2),
    sur_suite=RIEN)
FABRIQUES[("projet_suppression", "EcranResultatDeSuppression")] = lambda cls, t: cls(
    plan_de_suppression(t),
    project_maintenance.RapportSuppression(
        cible="lot:a-premier_25",
        fichiers_a_supprimer=("extract-frames/a-premier_25/f0.tiff",
                              "extract-frames/a-premier_25/f1.tiff"),
        dry_run=False, supprime=False,
        fichiers_non_supprimes=("extract-frames/a-premier_25/f1.tiff",),
        rang_vise=2),
    sur_suite=RIEN)

# --- rattrapages ------------------------------------------------------------

def rapport_de_detection():
    from mixed_media_utility import scan_detect
    return scan_rap.RapportDeDetection(
        lots=(scan_rap.PanneauDeLot("a-premier_25", 3, 3, 124, 124,
                                    scan_detect.COMPLETUDE_COMPLET),
              scan_rap.PanneauDeLot("m-milieu_12p5", 2, 3, 41, 62,
                                    scan_detect.COMPLETUDE_INCOMPLET,
                                    planches_manquantes=(2,),
                                    pages_muettes=(page_muette(),)),
              scan_rap.PanneauDeLot("z-dernier_8", 1, 1, 60, 60,
                                    scan_detect.COMPLETUDE_COMPLET_AVEC_MIRES,
                                    mires=1)),
        en_attente=(scan_rap.EnAttenteDeLecture("page-0009.tiff",
                                                "QR_ILLISIBLE", read_rank=9),))


def session_de_previz():
    from mixed_media_utility import cadence_previz, frame_selection
    fps_source = Fraction(25, 1)
    frames = 124
    valeurs = (Fraction(25, 1), Fraction(25, 2), Fraction(25, 3))
    selections = tuple(frame_selection.select_source_frames(
        fps_source=fps_source, fps_target=v, source_frame_count=frames)
        for v in valeurs)
    return cadence_previz.PrevizSession(
        video_path=Path("/rushes/plan-04.mov"), fps_source=fps_source,
        source_frame_count=frames, source_frame_count_is_exact=True,
        start_timecode=None, stream_duration_seconds=None,
        fps_targets=tuple(float(v) for v in valeurs), selections=selections,
        schedules=tuple(cadence_previz.build_schedule(s, fps_source)
                        for s in selections))


def _rapport_de_passe(valeur, attendues, presentees=None, omises=0):
    from mixed_media_utility import cadence_previz
    presentees = attendues if presentees is None else presentees
    return cadence_previz.PlaybackReport(
        fps_target=float(valeur), frames_presentees=presentees,
        frames_attendues=attendues, frames_omises=omises,
        retard_max_s=0.012, retard_median_s=0.004, retard_p95_s=0.010,
        derive_finale_s=0.02, duree_nominale_s=4.96, duree_reelle_s=4.98,
        amorcage_s=0.12, cadence_effective=float(valeur),
        taux_frames_en_retard=0.01, temps_reel_tenu=True,
        partiel=False, warnings=())


def resultat_de_previz():
    from mixed_media_utility import cadence_previz
    valeurs = (Fraction(25, 1), Fraction(25, 2), Fraction(25, 3))
    return cadence_previz.PrevizResult(
        session=session_de_previz(),
        reports=(_rapport_de_passe(valeurs[0], 124),
                 _rapport_de_passe(valeurs[1], 62),
                 _rapport_de_passe(valeurs[2], 42, presentees=32, omises=10)),
        interrupted=False, decoded_frames=0, cache_hits=0, cache_misses=0)


def cadences_regardees():
    return (cadences.Cadence(Fraction(25, 1), "25 im/s", compte=124),
            cadences.Cadence(Fraction(25, 2), "12,5 im/s", compte=62),
            cadences.Cadence(Fraction(25, 3), "8,33 im/s", compte=42))


FABRIQUES[("atelier_extraction", "EcranChoixDesCadences")] = lambda cls, t: cls(
    cadences_regardees(), resultat_de_previz(),
    nommer=lambda c: "projet_demo_plan-04_" + c.libelle.split()[0].replace(",", "p"),
    confirmer=RIEN, octets_par_frame=6_220_800)
FABRIQUES[("atelier_extraction", "EcranPreviz")] = lambda cls, t: cls(
    cadences_regardees(), session_de_previz(), jouer=RIEN,
    verifier_l_affichage=lambda: None, choisir=RIEN)


# --- les paliers et les menus, sur le projet REEL du terrain ----------------

FABRIQUES[("ecran_ateliers", "EcranAteliers")] = lambda cls, t: cls(t.projet, RIEN)
FABRIQUES[("palier_projet", "EcranPalierProjet")] = lambda cls, t: cls(t.projet, RIEN)

# Le profil de calibration par defaut du palier Projet. La liste se monte sur
# le projet REEL du terrain, qui n'a **aucun** profil au registre : elle
# dessine alors sa seule porte « autre fichier… ». C'est deliberement l'etat
# le plus pauvre -- celui dont Egan dit qu'il ne doit jamais rendre un ecran
# vide --, et c'est celui que le terrain partage sait produire sans ecriture.
FABRIQUES[("palier_profil_defaut", "EcranProfilParDefaut")] = lambda cls, t: cls(
    t.projet, confirmer=RIEN)


def apercu_de_pose(t):
    """L'apercu que rend `palier_projet.apercu_de_profil`, **sans le disque**.

    Le chemin n'est pas ecrit a la main : il est calcule par la fonction meme
    qui le calcule dans le produit, `profile_path_for_document`. Une seconde
    formule ici ferait de ce banc un temoin de sa propre invention -- et c'est
    exactement ce que `EPIC5-ARB-83` ferme du cote du coeur.
    """
    from mixed_media_utility.io import calibration_profile

    document = {"chain_id": "epson-v850_papier-mat-310g_2026-08",
                "correction_form_id": "affine-par-canal-v2",
                "label": "papier mat 310 g"}
    return palier_projet.ProfilPose(
        chaine=document["chain_id"], forme=document["correction_form_id"],
        chemin=calibration_profile.profile_path_for_document(t.projet,
                                                             document))


FABRIQUES[("palier_profil_defaut", "EcranPoseDuProfil")] = lambda cls, t: cls(
    apercu_de_pose(t), t.racine / "profil-designe.json", poser=RIEN,
    defaut_actuel="epson-v850_brouillon_2026-07.json")
FABRIQUES[("palier_profil_defaut", "EcranProfilPose")] = lambda cls, t: cls(
    palier_profil_defaut.panneau_du_profil_pose(apercu_de_pose(t)),
    objet=palier_profil_defaut.OBJET_DU_BANDEAU)
FABRIQUES[("atelier_pdf", "EcranPdfMenu")] = lambda cls, t: cls(t.projet, RIEN)
FABRIQUES[("atelier_scan", "EcranScanMenu")] = lambda cls, t: cls(t.projet, RIEN)
FABRIQUES[("atelier_scan", "EcranScanDepot")] = lambda cls, t: cls(t.projet, detecter=RIEN)
FABRIQUES[("atelier_pdf_calibration", "EcranMireReglages")] = lambda cls, t: cls(
    "projet_demo", t.projet, pdf_cal.FormulaireDeLaMire(chaine="epson-v850"),
    RIEN)
FABRIQUES[("atelier_pdf_calibration", "EcranMireEnCours")] = lambda cls, t: cls(
    "projet_demo_mire_epson-v850.pdf", "epson-v850", donnees_de_la_mire(), RIEN)
FABRIQUES[("ecran_manuel", "EcranManuel")] = lambda cls, t: cls(
    manuel.entrees_du_manuel())
FABRIQUES[("ecran_projet", "EcranCreation")] = lambda cls, t: cls(
    str(t.racine), "projet_neuf", RIEN)
FABRIQUES[("ecran_projet", "EcranProjet")] = lambda cls, t: cls(
    t.recents, ouvrir=RIEN, creer=RIEN)
FABRIQUES[("projet_inventaire", "EcranInventaireDuProjet")] = lambda cls, t: cls(
    projet_inventaire.ArbreDuProjet.depuis_l_inventaire(
        projet_inventaire.inventorier_le_projet(t.projet)),
    supprimer=RIEN)


# ---------------------------------------------------------------------------
# Le TERRAIN -- un projet reel, ecrit sur disque
# ---------------------------------------------------------------------------

@dataclass
class Terrain:
    """Ce qu'une fabrique recoit : la racine jetable, le projet, ses recents."""

    racine: Path
    projet: Path
    recents: object = None


def terrain(racine: Path) -> Terrain:
    """Un projet REEL, deux rushes et deux lots **tous distinguables**.

    Deux geometries, deux cadences, deux cardinaux de frames et quatre poids
    de fichier tous differents (11, 21, 31, 41 et 1001 octets). Jamais un
    remplissage uniforme : un desappariement entre un lot et ce qu'un ecran en
    dit ne se verrait pas sur des valeurs egales (regle des fabriques,
    point 1). Meme geste que `_projet_montable` de la frontiere
    d'atteignabilite, dont ce terrain est le prolongement.
    """
    from mixed_media_utility import encode
    from mixed_media_utility.gui.depot_projets import creer_projet

    chemin = creer_projet(racine, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [
        {"rush_id": "a-premier",
         "resolution_source": {"width": 1920, "height": 1080}},
        {"rush_id": "z-second",
         "resolution_source": {"width": 1280, "height": 720}},
    ]
    document["lots"] = [
        {"lot_id": LOT_PREMIER, "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25",
         "state": encode.MINIMUM_LOT_STATE, "fps_target": 25,
         "expected_frame_count": 2, "timecode_base_fps": "25/1",
         "output_frames_dir": "output-frames/a-premier_25",
         "output_bit_depth": 16},
        {"lot_id": LOT_SECOND, "rush_id": "z-second",
         "frames_dir": "extract-frames/z-second_8",
         "state": encode.MINIMUM_LOT_STATE, "fps_target": 8,
         "expected_frame_count": 1, "timecode_base_fps": "8/1",
         "output_frames_dir": "output-frames/z-second_8",
         "output_bit_depth": 16},
    ]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for relatif, octets in (("extract-frames/a-premier_25/f0.tiff", 11),
                            ("extract-frames/z-second_8/f0.tiff", 1001),
                            ("output-frames/a-premier_25/f0.tiff", 21),
                            ("output-frames/a-premier_25/f1.tiff", 31),
                            ("output-frames/z-second_8/f0.tiff", 41),
                            ("rushes/plan-04.mov", 51),
                            ("scans/planche-04.pdf", 61)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    recents = projets.Recents(racine / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    return Terrain(racine, chemin, recents)


@pytest.fixture(scope="module")
def sol(tmp_path_factory) -> Terrain:
    """Le terrain, construit UNE fois pour tout le fichier.

    Il est lu et jamais ecrit par les ecrans montes -- aucun d'eux n'a de
    rappel d'ecriture cable ici --, donc le partager entre 300 montees est sans
    risque et evite de recreer un projet a chaque parametre.
    """
    return terrain(tmp_path_factory.mktemp("montee"))


# ---------------------------------------------------------------------------
# Le RECENSEMENT -- parcouru, jamais enumere
# ---------------------------------------------------------------------------

def _forcer_les_classes_PARESSEUSES() -> None:
    """Construire les classes d'ecran que le produit ne cree qu'a la demande.

    **Le defaut que ce geste ferme, et il a mis onze heures a se montrer**
    (2026-09-07). `atelier_scan_calibrate._classe_de_l_ecran_de_passe()`
    SOUS-CLASSE `EcranExecution` a l'interieur d'une fonction et memorise le
    resultat dans un attribut de module -- l'import d'`execution` y est differe
    comme partout ailleurs dans ce module. La classe existe donc dans
    `vars(module)` **si et seulement si** quelque chose l'a deja demandee dans
    ce processus-la.

    Consequence : le recensement ci-dessous rendait un ensemble qui dependait
    de l'ORDRE des tests. En serie, la garde de couverture passait ; sous
    `-n 4`, le worker qui avait deja joue une passe de calibration la voyait et
    la declarait orpheline. Deux courses completes de `tests/unit` l'ont rendu,
    a 17 986 tests et un seul rouge -- c'est-a-dire de la pire facon, un rouge
    qu'on prend pour un alea.

    **Le forcage est la bonne moitie de la correction, pas un contournement** :
    il rend le recensement DETERMINISTE, et il le rend PLUS LARGE -- la classe
    entre dans la mesure a chaque course au lieu d'y entrer par hasard. L'autre
    moitie est sa fabrique, posee juste a cote des autres.

    Une classe paresseuse de plus se declare ici, et la garde de couverture
    dira d'elle-meme qu'elle manque.
    """
    from mixed_media_utility.tui import atelier_scan_calibrate

    atelier_scan_calibrate._classe_de_l_ecran_de_passe()


def paliers_du_paquet() -> list[tuple[str, str, type]]:
    """`(module, nom, classe)` de toute sous-classe de `coque.Palier`, triee.

    Parcourir le paquet plutot qu'ecrire une liste est ce qui fait de ce banc
    une frontiere : un ecran ajoute demain entre dans la mesure sans qu'on ait
    rien a poser -- et s'il n'a pas de fabrique, la garde de couverture rougit.
    """
    import mixed_media_utility.tui as paquet

    _forcer_les_classes_PARESSEUSES()
    trouves = []
    for info in pkgutil.iter_modules(paquet.__path__):
        if info.name.startswith("__"):
            continue
        module = importlib.import_module("mixed_media_utility.tui." + info.name)
        for nom, obj in vars(module).items():
            if (inspect.isclass(obj) and issubclass(obj, coque.Palier)
                    and obj is not coque.Palier
                    and obj.__module__ == module.__name__):
                trouves.append((info.name, nom, obj))
    return sorted(trouves, key=lambda t: (t[0], t[1]))


# ---------------------------------------------------------------------------
# La MONTEE -- par `descendre`, la route du produit
# ---------------------------------------------------------------------------

#: Les deux noms sous lesquels le paquet compte les pas de son rotor. Ecrits
#: ici plutot que devines : un troisieme nom ferait passer un rotor libre, et
#: c'est le banc de bord ci-dessous qui le dirait.
COMPTEURS_DE_ROTOR = ("pas", "pas_du_rotor")


class _MinuteurArrete:
    """Ce que `set_interval` rend quand le banc a coupe l'horloge.

    Il porte les trois gestes que le paquet lui demande -- `pause`, `stop`,
    `resume` --, de sorte qu'un `on_unmount` qui l'arrete ne casse pas.
    """

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...

    def reset(self) -> None: ...


@contextlib.contextmanager
def sans_horloge():
    """Couper `set_interval` sur les ecrans du paquet, le temps d'une montee.

    **Pourquoi la remise a zero des compteurs ne suffit pas.** Elle suppose que
    le seul effet d'un tour d'horloge est un GLYPHE. C'est faux :
    `EcranDesLotsAEncoder` compte « un lot par tour de rotor », si bien qu'un
    tick de plus rend `1 lot compté sur 3` la ou le precedent rendait `0`.
    Aucun compteur de rotor remis a zero ne defait ce comptage-la, et le volet
    de la couleur -- qui monte deux fois et compare -- redevient une mesure du
    temps qui passe. Mesure : la course de sante d'une campagne a rougi deux
    fois, sur deux ecrans differents, pour cette seule raison.

    **Le geste est donc de ne jamais laisser l'horloge partir**, plutot que de
    rattraper ses effets un par un -- ce qui demanderait de connaitre, ecran
    par ecran, tout ce qu'un tour fait avancer. La greffe est **en memoire**,
    sur la classe de base du paquet, et elle est rendue dans un `finally` :
    aucun fichier n'est touche.

    **Ce qu'elle ne couvre pas, dit plutot que tu** : un ecran qui prendrait
    son minuteur ailleurs que par `Palier.set_interval` -- sur l'application,
    par exemple -- y echapperait. Les quatre `set_interval` du paquet au
    2026-09-06 passent tous par un ecran ; `figer_le_rotor` reste en second
    filet, et sa frontiere negative dit qu'il ne redessine rien quand il n'a
    rien trouve.
    """
    def _pas_d_horloge(self, *_args, **_kwargs):
        return _MinuteurArrete()

    coque.Palier.set_interval = _pas_d_horloge
    try:
        yield
    finally:
        del coque.Palier.set_interval


def figer_le_rotor(monte) -> None:
    """Arreter le temps sur un ecran monte, pour ne mesurer que lui.

    **Pourquoi, et ce que ca a coute.** Plusieurs ecrans font tourner un rotor
    sur un minuteur (`set_interval`). Deux montees du meme ecran a deux
    instants rendent alors deux glyphes differents, et le volet de la couleur
    -- qui monte deux fois et compare -- mesure le temps qui passe plutot que
    la couleur. La panne est **fonction de la charge** : elle ne s'est pas
    montree en course seule, et elle a rendu rouge la course de sante d'une
    campagne de mutation lancee sur la meme machine.

    **Mettre en pause ne suffit pas** : entre le montage et la pause, l'horloge
    a pu avancer d'un cran. On remet donc le compteur a zero.

    **Et le compteur n'est pas toujours sur l'ECRAN.** C'est le second temps de
    la meme panne, et le plus cher : `EcranEncodageEnCours` delegue son pas a
    son `passage` (`SurfaceExecution.avancer_le_rotor`), si bien qu'une remise
    a zero qui ne regarde que l'ecran laisse le rotor libre en silence. On
    balaye donc l'ecran **et les objets qu'il tient**, plutot que de nommer un
    attribut de plus a chaque fois qu'un ecran deplace son compteur.

    **Et le redessin est CONDITIONNEL**, ce qui n'est pas un detail de cout :
    `Palier.rafraichir` reecrit le bandeau, la ligne d'etat et la ligne de
    raccourcis en les bornant lui-meme. Redessiner sans raison REPARE donc ce
    que `compose` aurait mal pose, et le banc lit alors le rattrapage au lieu
    de la faute. Mesure : les trois mutants qui retirent le bornage de
    `compose` SURVIVAIENT au banc entier tant que le redessin etait
    inconditionnel. On ne redessine que si l'on a bien fige quelque chose --
    c'est-a-dire sur les seuls ecrans dont le rendu bougerait sinon.
    """
    minuteur = getattr(monte, "minuteur", None)
    if minuteur is not None:
        minuteur.pause()
    remis = 0
    for porteur in [monte, *vars(monte).values()]:
        for compteur in COMPTEURS_DE_ROTOR:
            valeur = getattr(porteur, compteur, None)
            if not isinstance(valeur, int) or isinstance(valeur, bool):
                continue
            if valeur == 0:
                # Deja au repos : rien a remettre, donc AUCUNE raison de
                # redessiner -- voir le docstring, le redessin repare.
                continue
            try:
                setattr(porteur, compteur, 0)
            except Exception:          # attribut en lecture seule : on passe
                pass
            else:
                remis += 1
    if remis:
        monte.rafraichir()


def monter(ecran, ascii_seul: bool = False, sans_couleur: bool = False,
           taille: tuple[int, int] = PLANCHER, touche: str | None = None,
           projet: str = "projet_demo"):
    """Empiler `ecran` **par-dessus deux paliers** et lire ce qu'il rend.

    **Deux paliers en dessous, et ce n'est pas du confort.** `action_remonter`
    ne depile que si `rang > 0`, et le rang compte les PALIERS : un ecran
    transitoire pose sur le palier 0 voit donc son `Échap` rester sans effet,
    ce qui n'est pas le regime du produit -- ou tout passage est empile
    au-dessus du menu des ateliers, au rang 1. Mesure faite en ecrivant ce
    banc : trente ecrans passaient pour avoir un `Échap` inerte, et c'etait le
    banc qui les mettait dans un etat que le produit ne produit pas.

    Rend `({zone: texte}, lignes du centre, objet du bandeau lu SUR L'ECRAN
    MONTE)`. L'objet est lu apres montage et non avant, parce qu'un ecran peut
    le retirer a son demarrage -- `EcranCadences` le fait quand l'affichage
    manque --, et le lire avant mesurerait une promesse que l'ecran ne tient
    plus.

    **On lit ce que le widget PORTE, pas ce que le compositeur peint** : le
    compositeur coupe a la largeur du terminal par definition, donc une ligne
    trop large s'y verrait comme une ligne absente, ce qui ne se distingue pas
    d'un ecran vide.
    """
    app = coque.CoqueTui(
        paliers=[coque.PalierTemoin("Projet", "Q quitter"),
                 coque.PalierTemoin("Ateliers", "Q quitter")],
        contexte=coque.Contexte(projet),
        ascii_seul=ascii_seul, sans_couleur=sans_couleur)

    async def tour():
        async with app.run_test(size=taille) as pilote:
            pilote.app.descendre()
            await pilote.pause()
            pilote.app.descendre(ecran)
            await pilote.pause()
            if touche is not None:
                await pilote.press(touche)
                await pilote.pause()
            monte = pilote.app.screen
            # **Figer le rotor avant de lire.** Deux ecrans font tourner un
            # rotor sur un minuteur (`EcranMireEnCours`, et l'ecriture en cours
            # de la suppression) : deux montees du meme ecran a deux instants
            # rendraient deux glyphes differents, et le volet de la couleur
            # comparerait alors le temps qui passe plutot que la couleur. La
            # poignee `minuteur` existe precisement pour ca -- son docstring le
            # dit : « la poignee permet de figer le mecanisme et de mesurer ce
            # qui le fait avancer, plutot que le temps qui passe ».
            figer_le_rotor(monte)
            zones = {}
            for zone in ("bandeau", "etat", "raccourcis"):
                try:
                    widget = monte.query_one("#" + zone)
                except Exception:
                    continue
                zones[zone] = jetons.texte_affiche(str(widget.content))
            centre: list[str] = []
            try:
                for enfant in monte.query_one("#centre").walk_children():
                    contenu = getattr(enfant, "content", None)
                    if contenu is not None:
                        centre += jetons.texte_affiche(str(contenu)).split("\n")
            except Exception:
                pass
            objet = (monte.objet_du_bandeau()
                     if hasattr(monte, "objet_du_bandeau") else "")
            return zones, centre, objet

    with sans_horloge():
        return asyncio.run(tour())


# ---------------------------------------------------------------------------
# Ce qui n'est PAS monte, et POURQUOI -- executable, pour perimer bruyamment
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NonMontee:
    """Une classe d'ecran que ce banc ne monte pas, et **pourquoi**.

    Le motif est du texte parce qu'il s'adresse a un humain ; il est
    **obligatoire et non vide**, mesure comme tel. `leve` nomme l'exception que
    la montee doit lever : c'est ce qui rend l'entree **mesurable** plutot que
    declarative -- une base qui deviendrait montable ferait rougir, au lieu de
    rester exemptee en silence.
    """

    module: str
    classe: str
    motif: str
    leve: type

    @property
    def cle(self) -> tuple[str, str]:
        return (self.module, self.classe)

    def __str__(self) -> str:      # pragma: no cover - confort de lecture
        return f"{self.module}.{self.classe}"


#: **Les deux classes que ce banc ne monte pas.** Ce sont des BASES
#: d'heritage : elles portent le corps peint que leurs filles remplissent, et
#: leurs methodes de composition levent. Les monter ne mesurerait pas un ecran
#: du produit -- il n'y en a pas derriere --, ce serait mesurer un patron.
#:
#: `test_plancher_80x24.est_un_ecran_concret` les classe pourtant « concretes »
#: parce qu'elles redefinissent `raccourcis` ou `contenu` ; c'est le critere
#: qui est approximatif, pas ces deux entrees. La preuve est ci-dessous, et
#: elle est executable.
NON_MONTEES: tuple[NonMontee, ...] = (
    NonMontee(
        "atelier_extraction", "_EcranDeCadences",
        "Base des TROIS ecrans de cadence (`E2-2`, `E2-2b`, `E2-2c`). Elle "
        "porte le corps peint et rien d'autre : `composer` et `mesure` levent "
        "`NotImplementedError`, et ses trois filles sont montees ici. La "
        "monter mesurerait un patron, pas un ecran.",
        NotImplementedError),
    NonMontee(
        "atelier_pdf_versions", "_EcranDeConflit",
        "Base des deux ecrans de conflit de tirage (`E5-3b`, `E5-3c`). "
        "`titre_du_cartouche` et `lignes_du_corps` levent "
        "`NotImplementedError` ; ses deux filles sont montees ici.",
        NotImplementedError),
)


def test_toute_classe_d_ecran_est_MONTEE_ou_DECLAREE_non_montable(sol):
    """La garde de couverture, et elle mesure les DEUX sens.

    Sans elle, un ecran neuf pourrait sortir de la mesure en silence -- c'est
    exactement le mode de panne que `MQ-4`, `MQ-5` et `MQ-8` ont paye trois
    fois : le composant existait, ses tests passaient, et rien ne mesurait
    qu'on puisse y arriver. Ici, d'un cran plus loin : rien ne mesurerait
    qu'on puisse le DESSINER.

    Le second sens compte autant : une declaration qui ne designe plus aucune
    classe est une derogation perimee, et une derogation perimee **excuse
    d'avance le manque suivant**.
    """
    recensees = {(module, nom) for module, nom, _ in paliers_du_paquet()}
    montees = set(FABRIQUES)
    declarees = {entree.cle for entree in NON_MONTEES}

    orphelines = sorted(recensees - montees - declarees)
    assert not orphelines, (
        "ces classes d'ecran ne sont ni montees ni declarees non montables :\n"
        "  " + "\n  ".join(f"{m}.{n}" for m, n in orphelines))

    fantomes = sorted((montees | declarees) - recensees)
    assert not fantomes, (
        "ces entrees ne designent plus aucune classe d'ecran du paquet :\n"
        "  " + "\n  ".join(f"{m}.{n}" for m, n in fantomes))

    doublons = sorted(montees & declarees)
    assert not doublons, (
        f"ces classes sont a la fois montees et declarees non montables : "
        f"{doublons}")


def test_chaque_MOTIF_de_non_montee_est_ecrit(sol):
    """Une entree sans motif serait une derogation muette.

    C'est le meme volet que le registre de la frontiere d'atteignabilite :
    « une entree sans motif serait exactement le filet `EcranPasEncore` laisse
    en place que `MQ-4` a paye ».
    """
    muettes = [str(e) for e in NON_MONTEES if not e.motif.strip()]
    assert not muettes, muettes
    assert len(NON_MONTEES) <= 6, (
        f"trop de classes exemptees ({len(NON_MONTEES)}) : la liste "
        "n'exempte plus, elle couvre")


@pytest.mark.parametrize("entree", NON_MONTEES, ids=str)
def test_une_classe_declaree_non_montable_LEVE_VRAIMENT(sol, entree):
    """Le volet qui fait PERIMER la liste, et il est executable.

    Une liste d'exceptions declarative pourrit : le jour ou l'une de ces bases
    devient montable, rien ne le dirait. Ici, si la montee cesse de lever, ce
    test rougit et la liste doit etre revue -- c'est-a-dire que l'exemption ne
    survit pas a sa raison d'etre.
    """
    module = importlib.import_module(
        "mixed_media_utility.tui." + entree.module)
    classe = getattr(module, entree.classe)
    with pytest.raises(entree.leve):
        monter(BASES_NUES[entree.cle](classe))


#: **Comment on construit une base d'heritage pour la voir lever.** Les deux
#: ne se construisent pas pareil -- l'une sans argument, l'autre avec un choix
#: exclusif --, donc la construction est ecrite par entree plutot que devinee.
#: Ce qu'on mesure n'est PAS la construction (elle reussit des deux cotes) mais
#: la MONTEE, qui appelle `composer` ou `titre_du_cartouche`.
BASES_NUES = {
    ("atelier_extraction", "_EcranDeCadences"): lambda cls: cls(),
    ("atelier_pdf_versions", "_EcranDeConflit"):
        lambda cls: cls(choix_a_trois_issues(), retenir=RIEN),
}


# ---------------------------------------------------------------------------
# Les regimes -- les TROIS drapeaux, varies dans les DEUX sens
# ---------------------------------------------------------------------------

#: Les quatre combinaisons de repli et de couleur, au plancher.
MODES = [pytest.param(a, c, id=f"{'ascii' if a else 'utf8'}-"
                              f"{'monochrome' if c else 'couleur'}")
         for a in (False, True) for c in (False, True)]

#: Le recensement, fige une fois : `paliers_du_paquet()` importe tout le
#: paquet, et le rejouer par parametre coute sans rien mesurer.
ECRANS = [(module, nom, cls) for module, nom, cls in paliers_du_paquet()
          if (module, nom) in FABRIQUES]

CAS = [pytest.param(module, nom, cls, id=f"{module}.{nom}")
       for module, nom, cls in ECRANS]


def utile(taille: tuple[int, int]) -> int:
    return COLONNES_UTILES[taille[0]]


def lignes_du_centre(taille: tuple[int, int]) -> int:
    return LIGNES_DE_CENTRE[taille[1]]


#: **Les amputations TOLEREES, avec leur motif et leur regime.** Une entree ici
#: n'est pas une derogation muette : le volet symetrique ci-dessous exige que
#: l'amputation SOIT ENCORE LA, de sorte que l'entree se perime bruyamment le
#: jour ou le defaut est referme. La cle est `(module, classe, zone, ascii)` --
#: le regime en fait partie, parce que ce defaut-ci ne mord qu'en `--ascii` et
#: qu'une tolerance qui couvrirait les deux modes cacherait la moitie du fait.
AMPUTATIONS_TOLEREES = {
    ("atelier_pdf_reglages", "EcranReglagesDesPlanches", "etat", True):
        "`MONTEE-2` de `deferred-work.md` : la ligne d'etat de `E5-2` enumere "
        "un segment PAR LOT et croit sans borne. A deux lots elle fait 76 "
        "colonnes en UTF-8 -- la borne exacte -- et 77 une fois repliee, si "
        "bien que le repli ASCII lui coupe la queue : `165 frames sur 166 "
        "emplacements`, la seule grandeur que cet ecran ne redit nulle part "
        "ailleurs. Les deux issues coutent un texte que la maquette dessine, "
        "donc un arbitrage (`EPIC11-ARB-142`, `EPIC11-ARB-144`).",
}


def anomalies(zones, centre, ascii_seul: bool, taille,
              tolerees: frozenset = frozenset()) -> list[str]:
    """Les defauts de geometrie d'un ecran monte. **Fonction PURE.**

    Ecrite comme une fonction et non en ligne dans le test, pour qu'elle soit
    elle-meme mesurable : les tests de bord ci-dessous lui donnent un rendu
    dont ils savent ou est la cible, et verifient qu'elle la trouve. Un
    balayage tronque d'un bord ne se demasque pas autrement (regle des
    fabriques, point 4).
    """
    trouvees = []
    largeur_utile = utile(taille)
    for zone, texte in sorted(zones.items()):
        for ligne in texte.split("\n"):
            colonnes = jetons.colonnes(ligne)
            if colonnes > largeur_utile:
                trouvees.append(
                    f"{zone} DEBORDE : {colonnes} colonnes pour "
                    f"{largeur_utile} -- {ligne!r}")
            elif ligne.rstrip().endswith(MARQUE[ascii_seul]):
                if zone in tolerees:
                    continue
                trouvees.append(f"{zone} AMPUTE : {ligne!r}")
    for rang, ligne in enumerate(centre):
        colonnes = jetons.colonnes(ligne)
        if colonnes > largeur_utile:
            trouvees.append(
                f"centre[{rang}] DEBORDE : {colonnes} colonnes pour "
                f"{largeur_utile} -- {ligne!r}")
    hauteur = lignes_du_centre(taille)
    if len(centre) > hauteur:
        trouvees.append(
            f"centre TROP HAUT : {len(centre)} lignes pour {hauteur}")
    return trouvees


# ---------------------------------------------------------------------------
# Volet 1 et 2 -- la montee, et le chrome, dans les QUATRE combinaisons
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,nom,cls", CAS)
@pytest.mark.parametrize("ascii_seul,sans_couleur", MODES)
def test_l_ecran_SE_MONTE_et_son_chrome_TIENT_au_plancher(
        sol, module, nom, cls, ascii_seul, sans_couleur):
    """Le coeur de ce banc : on MONTE, on ne lit pas une reference.

    La montee elle-meme est la premiere assertion -- une exception ici est le
    defaut le plus grave que ce banc cherche, et il n'a pas besoin d'un
    `assert` pour se dire. Le reste mesure le chrome REELLEMENT rendu.
    """
    zones, centre, _ = monter(FABRIQUES[(module, nom)](cls, sol),
                              ascii_seul, sans_couleur, PLANCHER)
    assert zones, (
        f"{module}.{nom} ne rend aucune zone de chrome : l'ecran est monte "
        "mais rien n'est dessine")
    trouvees = anomalies(zones, centre, ascii_seul, PLANCHER,
                         zones_tolerees(module, nom, ascii_seul))
    assert not trouvees, (
        f"a {PLANCHER[0]}x{PLANCHER[1]}"
        f"{' en --ascii' if ascii_seul else ''}"
        f"{' en --sans-couleur' if sans_couleur else ''}, "
        f"{module}.{nom} :\n  " + "\n  ".join(trouvees))


@pytest.mark.parametrize("module,nom,cls", CAS)
def test_l_ecran_TIENT_AUSSI_dans_une_fenetre_confortable(sol, module, nom, cls):
    """La taille varie, et dans l'autre sens.

    Un ecran calibre au plancher peut deborder au-dessus : une ligne calee a
    droite sur une largeur relue, une fenetre de liste qui grandit avec la
    hauteur. Sans ce volet, le banc mesurerait UNE geometrie et l'annoncerait
    comme deux.
    """
    zones, centre, _ = monter(FABRIQUES[(module, nom)](cls, sol),
                              False, False, CONFORTABLE)
    trouvees = anomalies(zones, centre, False, CONFORTABLE)
    assert not trouvees, (
        f"a {CONFORTABLE[0]}x{CONFORTABLE[1]}, {module}.{nom} :\n  "
        + "\n  ".join(trouvees))


def zones_tolerees(module: str, nom: str, ascii_seul: bool) -> frozenset:
    """Les zones dont l'amputation est inscrite, POUR CE REGIME."""
    return frozenset(cle[2] for cle in AMPUTATIONS_TOLEREES
                     if cle[0] == module and cle[1] == nom
                     and cle[3] == ascii_seul)


def test_chaque_AMPUTATION_toleree_est_ENCORE_LA(sol):
    """Le volet symetrique, et il est ce qui distingue une inscription d'une
    derogation muette.

    Une tolerance qui survit a son defaut **excuse d'avance le manque
    suivant** : le jour ou `MONTEE-2` est referme, cette entree couvrirait en
    silence la prochaine ligne amputee du meme ecran. Elle doit donc rougir
    quand le defaut disparait.
    """
    for (module, nom, zone, ascii_seul), motif in AMPUTATIONS_TOLEREES.items():
        assert motif.strip(), f"{module}.{nom}/{zone} : tolerance sans motif"
        cible = next((c for m, n, c in ECRANS if (m, n) == (module, nom)), None)
        assert cible is not None, (
            f"{module}.{nom} n'est plus un ecran monte : tolerance perimee")
        zones, _, _ = monter(FABRIQUES[(module, nom)](cible, sol), ascii_seul)
        ligne = zones.get(zone, "")
        assert ligne.rstrip().endswith(MARQUE[ascii_seul]), (
            f"{module}.{nom} / {zone} n'est plus ampute en "
            f"{'ascii' if ascii_seul else 'utf8'} : retirer cette tolerance, "
            "et fermer l'entree de `deferred-work.md` qui la porte")


def test_les_tolerances_restent_PEU_NOMBREUSES():
    """Sans borne, la liste des tolerances finirait par exempter tout le
    produit sans que rien ne rougisse. Meme geste que
    `LIGNE_POSEE_A_LA_CONSTRUCTION` du banc du plancher."""
    assert len(AMPUTATIONS_TOLEREES) <= 3, sorted(AMPUTATIONS_TOLEREES)


# ---------------------------------------------------------------------------
# Volet 3 -- le drapeau `sans_couleur`, MESURE et non suppose
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,nom,cls", CAS)
@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_la_COULEUR_ne_change_AUCUN_texte(sol, module, nom, cls, ascii_seul):
    """`--sans-couleur` ne deplace pas une colonne, et c'est **mesure ici**.

    `test_plancher_80x24.py` le conclut de **trois** ecrans et quatre
    combinaisons, et pose lui-meme la condition de sa chute : « si un jour un
    ecran choisissait un GLYPHE selon la couleur, cette conclusion tomberait ».
    Ce banc porte la mesure a soixante-sept ecrans, ce qui est la seule facon
    de savoir que la condition n'est pas deja tombee quelque part.

    L'egalite porte sur le texte **balisage retire** : la couleur passe par du
    balisage, que `jetons.texte_affiche` enleve de toutes les mesures. Ce test
    dit donc « la couleur ne passe QUE par le balisage », ce qui est
    exactement la promesse.
    """
    couleur = monter(FABRIQUES[(module, nom)](cls, sol), ascii_seul, False)
    monochrome = monter(FABRIQUES[(module, nom)](cls, sol), ascii_seul, True)
    assert couleur == monochrome, (
        f"{module}.{nom} rend un TEXTE different sans couleur : un ecran qui "
        "choisit un glyphe ou une largeur selon la couleur perd son "
        "information sur un terminal monochrome")


# ---------------------------------------------------------------------------
# Volet 4 -- le bandeau garde sa DROITE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,nom,cls", CAS)
@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_le_bandeau_garde_sa_DROITE_sur_l_ecran_monte(
        sol, module, nom, cls, ascii_seul):
    """La regression du 2026-09-06, mesuree sur soixante-sept ecrans.

    Elle avait ete trouvee sur quatorze : `Palier.bandeau` et
    `ObjetTravaille.bandeau` composaient en geometrie UTF-8 et laissaient
    `compose` replier ensuite, si bien qu'en `--ascii` la ligne passait de 76 a
    78 colonnes et perdait sa DROITE -- c'est-a-dire l'objet travaille, les
    chiffres du parcours en cours, que rien d'autre ne reaffiche.

    Le test est **conditionnel a l'objet**, et c'est le point : un ecran qui
    n'en declare pas a un bandeau nu, ce qui est le cas nominal de plusieurs
    maquettes. On ne mesure que la promesse qui est faite.
    """
    zones, _, objet = monter(FABRIQUES[(module, nom)](cls, sol), ascii_seul)
    if not objet:
        pytest.skip(f"{module}.{nom} ne declare aucun objet travaille")
    attendu = jetons.replier_ascii(objet) if ascii_seul else objet
    bandeau = zones.get("bandeau", "")
    assert bandeau.rstrip().endswith(attendu), (
        f"{module}.{nom} a perdu la droite de son bandeau : {bandeau!r} ne "
        f"se termine pas par {attendu!r}")


def test_UNE_MAJORITE_des_ecrans_declare_un_objet_travaille(sol):
    """Le volet symetrique du precedent, et sans lui il ne mesurerait rien.

    Un `skip` conditionnel est un test qui peut disparaitre en silence : si un
    jour aucun ecran ne declarait plus d'objet, le volet 4 serait entierement
    saute et **vert**. On exige donc que la promesse soit faite par un nombre
    d'ecrans qu'une regression ne pourrait pas atteindre par accident.

    C'est le meme geste que `ObjetTravaille` decrit comme son propre defaut
    d'origine (`I3`) : « `Contexte.objet` existait, les maquettes le
    remplissaient sur onze ecrans sur douze, et AUCUN ecran de l'atelier ne le
    posait ».
    """
    avec = [f"{module}.{nom}" for module, nom, cls in ECRANS
            if monter(FABRIQUES[(module, nom)](cls, sol))[2]]
    assert len(avec) >= 30, (
        f"seuls {len(avec)} ecrans declarent un objet travaille : le volet 4 "
        f"ne mesure presque plus rien. {sorted(avec)}")


# ---------------------------------------------------------------------------
# Volet 5 -- le clavier annonce
# ---------------------------------------------------------------------------

#: Les jetons de touche que les lignes de raccourcis du paquet emploient, et
#: la ou les touches `textual` qu'ils designent. La table est **ecrite ici**
#: plutot que relue du produit : une touche renommee dans le produit doit faire
#: rougir la garde de couverture ci-dessous, pas suivre en silence.
TOUCHES = {
    "⏎": ("enter",), "↑↓": ("up", "down"), "↑": ("up",), "↓": ("down",),
    "←": ("left",), "→": ("right",), "⌫": ("backspace",),
    "Tab": ("tab",), "Échap": ("escape",), "Espace": ("space",),
    "Suppr": ("delete",), "F1": ("f1",),
    # **Les lettres sont annoncees en MAJUSCULE et frappees en MINUSCULE**, et
    # c'est la regle du depot, ecrite en entier dans `coque.py` : « la touche
    # liee ne change pas : c'est la lettre NUE, minuscule ». La table dit donc
    # les deux moities a la fois, et un banc qui frapperait `"Q"` mesurerait
    # une touche que rien ne cable.
    "Q": ("q",), "O": ("o",), "A": ("a",), "X": ("x",),
    "Ctrl+↓": ("ctrl+down",), "Ctrl+↑": ("ctrl+up",), "Ctrl+R": ("ctrl+r",),
    "Ctrl+H": ("ctrl+h",), "Ctrl+A": ("ctrl+a",), "Ctrl+D": ("ctrl+d",),
    # **`Ctrl+L` est entre ici le 2026-09-07**, et la garde de couverture l'a
    # exige d'elle-meme : la ligne `RACCOURCIS_INVENTAIRE_RELINKER` existait
    # depuis la story 11.11, mais aucun ecran monte par ce banc ne l'affichait
    # -- l'inventaire du projet temoin ne portait aucun objet declare absent.
    # Depuis que `ArbreDuProjet.raccourcis()` l'annonce aussi sur un RUSH
    # declare (lot H, le seul objet que le coeur sache relinker), elle est
    # rendue, et le jeton devait etre frappe comme les autres.
    "Ctrl+L": ("ctrl+l",),
}


def jetons_de_la_ligne(ligne: str) -> list[str]:
    """Les jetons de touche annonces, dans l'ordre de la ligne.

    Une ligne de raccourcis est une suite d'items separes par **deux espaces
    au moins** ; le jeton de touche est le premier mot de chaque item. La
    coupe est faite ici plutot que devinee mot a mot : `Tab journal`
    porte un seul jeton, pas deux.
    """
    trouves = []
    for item in re.split(r"\s{2,}", ligne.strip()):
        if item:
            trouves.append(item.split(" ")[0])
    return trouves


def touches_annoncees(ligne: str) -> list[tuple[str, str]]:
    """`(jeton, touche textual)` de tout ce que la ligne annonce et qu'on sait
    frapper. Un jeton inconnu est **ignore ici** et attrape par la garde de
    couverture, qui est le seul endroit ou il doit faire du bruit."""
    return [(jeton, touche) for jeton in jetons_de_la_ligne(ligne)
            for touche in TOUCHES.get(jeton, ())]


def test_la_table_des_touches_COUVRE_tout_jeton_annonce_par_le_produit(sol):
    """La garde sans laquelle le volet 5 pourrait ne rien mesurer.

    Un jeton que la table ignore est une touche qui sort de la mesure en
    silence -- et c'est le mode de panne le plus couteux d'une frontiere :
    rester verte en ne mesurant rien. On exige donc que **tout** premier mot
    d'item soit soit une touche connue, soit un mot qu'on reconnait comme
    n'etant pas une touche.
    """
    inconnus = {}
    for module, nom, cls in ECRANS:
        zones, _, _ = monter(FABRIQUES[(module, nom)](cls, sol))
        for jeton in jetons_de_la_ligne(zones.get("raccourcis", "")):
            if jeton not in TOUCHES:
                inconnus.setdefault(jeton, []).append(f"{module}.{nom}")
    assert not inconnus, (
        "ces jetons de touche sont annonces par le produit et absents de la "
        f"table du banc, donc jamais frappes : {inconnus}")


def test_le_volet_du_clavier_JOUE_un_nombre_de_touches_qui_MESURE(sol):
    """Regle des fabriques, point 1, appliquee au corpus de touches.

    Un volet qui ne frapperait qu'une touche, ou N fois la meme, resterait
    vert quelle que soit la panne. On exige plusieurs frappes ET plusieurs
    touches DIFFERENTES -- un remplissage uniforme ne mesure pas un parcours.
    """
    frappes, distinctes = 0, set()
    for module, nom, cls in ECRANS:
        zones, _, _ = monter(FABRIQUES[(module, nom)](cls, sol))
        for _, touche in touches_annoncees(zones.get("raccourcis", "")):
            frappes += 1
            distinctes.add(touche)
    assert frappes >= 200, frappes
    assert len(distinctes) >= 6, sorted(distinctes)


@pytest.mark.parametrize("module,nom,cls", CAS)
def test_aucune_touche_ANNONCEE_ne_fait_planter_l_ecran(sol, module, nom, cls):
    """Ce que ce volet mesure, et ce qu'il ne mesure pas.

    Il mesure qu'une touche que l'ecran **annonce** ne le casse pas. Il ne
    mesure PAS qu'elle fasse ce qu'elle annonce, et c'est une limite payee en
    ecrivant ce banc : la plupart des touches d'un ecran passent par un rappel
    injecte a la construction (`sur_issue`, `sur_suite`, `continuer`,
    `retenir`), si bien qu'un banc qui injecte un rappel muet mesure son
    propre rappel. Le seul geste dont la reponse soit interne a l'ecran est
    `Tab journal`, mesure separement ci-dessous.
    """
    zones, _, _ = monter(FABRIQUES[(module, nom)](cls, sol))
    ligne = zones.get("raccourcis", "")
    for jeton, touche in touches_annoncees(ligne):
        monter(FABRIQUES[(module, nom)](cls, sol), touche=touche)


#: `Q21` est **TRANCHE et FERME** (`EPIC11-ARB-246`, Egan le 2026-09-06, par
#: invite, verbatim : « Retirer le jeton de ces deux ecrans »).
#:
#: Cette table portait les deux ecrans de compte rendu de la suppression,
#: `E6-3` et `E6-3b`, qui annoncaient `Tab journal` sans avoir aucun journal a
#: ouvrir. Elle est **vide**, et c'est ce qui en fait une mesure plutot qu'une
#: ligne morte : la boucle ci-dessous rougit desormais des qu'UN ecran, quel
#: qu'il soit, annonce le jeton sans pouvoir le tenir. Une table de tolerance
#: vide est une frontiere negative -- la supprimer aurait rendu la
#: reintroduction invisible.
#:
#: Le retrait est structurel plutot que declaratif : les deux `__init__` de
#: `projet_suppression` n'acceptent plus de `journal`, donc leur ligne de
#: raccourcis ne peut plus etre remplacee par
#: `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` par un appelant distrait.
TAB_JOURNAL_SANS_JOURNAL: frozenset[tuple[str, str]] = frozenset()


def test_TAB_JOURNAL_n_est_annonce_que_la_ou_un_journal_existe(sol):
    """`EPIC11-ARB-58` : une touche annoncee qui ne fait rien se lit comme une
    panne. `EcranResultat.basculer_le_journal` le dit mot pour mot et rend
    faux quand il n'y a pas de journal -- l'ecran ne doit alors pas l'annoncer.

    Ce test a trouve `Q21` par un chemin independant de celui qui l'a inscrit
    au registre, et il mesure les **deux** sens : un ecran qui annonce sans
    journal fait rougir, et une inscription qui cesse d'etre vraie aussi.
    Depuis qu'`EPIC11-ARB-246` a ferme `Q21`, :data:`TAB_JOURNAL_SANS_JOURNAL`
    est **vide** -- la premiere moitie est donc devenue une frontiere sans
    aucune tolerance, et la seconde garde la table honnete si un ecran
    reprenait un jour le defaut.
    """
    sans_journal, avec_journal = set(), set()
    for module, nom, cls in ECRANS:
        ecran = FABRIQUES[(module, nom)](cls, sol)
        zones, _, _ = monter(ecran)
        if ANNONCE_DU_JOURNAL not in zones.get("raccourcis", ""):
            continue
        cible = avec_journal if _bascule_le_journal(
            FABRIQUES[(module, nom)](cls, sol)) else sans_journal
        cible.add((module, nom))

    assert avec_journal, (
        "aucun ecran n'annonce `Tab journal` avec un journal : ce test ne "
        "mesure plus rien")
    inattendus = sorted(sans_journal - TAB_JOURNAL_SANS_JOURNAL)
    assert not inattendus, (
        "ces ecrans annoncent `Tab journal` et n'ont aucun journal a ouvrir "
        f"-- meme famille que `Q21` : {inattendus}")
    perimees = sorted(TAB_JOURNAL_SANS_JOURNAL - sans_journal)
    assert not perimees, (
        f"`Q21` est ferme pour ces ecrans : retirer leur inscription "
        f"{perimees}")


def _bascule_le_journal(ecran) -> bool:
    """Vrai si `Tab` deplie effectivement un journal sur cet ecran monte.

    **On frappe la touche et on lit l'etat interne**, plutot que d'appeler une
    methode : les deux familles d'ecran qui annoncent `Tab journal` ne la
    traitent pas de la meme facon -- `EcranResultat` passe par
    `basculer_le_journal`, qui rend faux sans journal ; `EcranExecution`
    bascule `journal_deplie` dans son propre `on_key`. Le seul point commun
    est l'etat, et c'est donc lui qu'on mesure.

    `journal_deplie` est **interne a l'ecran** : c'est ce qui rend cette mesure
    sure, la ou le reste du clavier passe par un rappel injecte que ce banc
    fournit muet.
    """
    replie = {}
    app = coque.CoqueTui(paliers=[coque.PalierTemoin("Projet", "Q quitter"),
                                  coque.PalierTemoin("Ateliers", "Q quitter")],
                         contexte=coque.Contexte("projet_demo"))

    async def tour():
        async with app.run_test(size=PLANCHER) as pilote:
            pilote.app.descendre()
            await pilote.pause()
            pilote.app.descendre(ecran)
            await pilote.pause()
            avant = getattr(pilote.app.screen, "journal_deplie", None)
            await pilote.press("tab")
            await pilote.pause()
            apres = getattr(pilote.app.screen, "journal_deplie", None)
            replie["oui"] = bool(apres) and apres != avant

    asyncio.run(tour())
    return replie.get("oui", False)


# ---------------------------------------------------------------------------
# Volet 6 -- le repli ASCII est une PROMESSE, et le BORD est ou elle se paie
# ---------------------------------------------------------------------------
#
# Ces deux volets sont nes d'une campagne de mutation, pas d'une relecture :
# les cinq mutants qui coupent le repli ASCII (`Palier.bandeau` et
# `ObjetTravaille.bandeau` qui ne transmettent plus le mode, `compose` qui ne
# borne plus les trois zones) SURVIVAIENT aux cinq volets precedents. Le motif
# est le meme dans les deux cas et c'est celui de la regle des fabriques
# appliquee aux VALEURS : le banc ne montait qu'un projet nomme `projet_demo`,
# c'est-a-dire assez court pour qu'aucun bandeau n'approche jamais sa borne.
# Un repli qui ALLONGE ne se voit qu'au bord.

#: Un nom de projet du depot, choisi parce qu'il FORCE l'abregement du
#: bandeau. Ce n'est pas un etat de synthese : `planche_4f_heteroclite` est un
#: artefact reel du depot, et le docstring de `Contexte.rendu` cite ce nom-la
#: comme celui qui « faisait deja 85 colonnes pour 76 et emportait la cadence
#: avec lui ». Mesure faite ici : le bandeau tombe **exactement a 76** en
#: UTF-8 sur une vingtaine d'ecrans, avec la marque d'abregement -- donc a 78
#: une fois repliee, si le repli arrive apres la mesure.
PROJET_QUI_FORCE_L_ABREGEMENT = "projet_demo_planche_4f_heteroclite"


@pytest.mark.parametrize("module,nom,cls", CAS)
@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_au_BORD_le_bandeau_TIENT_et_garde_sa_droite(
        sol, module, nom, cls, ascii_seul):
    """La regression du 2026-09-06, mesuree la ou elle mord.

    Le volet 4 mesure la meme promesse sur un projet court : il dit que la
    droite du bandeau est la, il ne dit pas qu'elle y reste quand la ligne est
    pleine. C'est precisement l'ecart que le repli ASCII exploite -- `…` rend
    `...`, donc une ligne calee a 76 en UTF-8 en fait 78 une fois repliee, et
    ce qui saute est la DROITE, c'est-a-dire l'objet travaille.
    """
    zones, _, objet = monter(FABRIQUES[(module, nom)](cls, sol), ascii_seul,
                             projet=PROJET_QUI_FORCE_L_ABREGEMENT)
    bandeau = zones.get("bandeau", "")
    largeur = jetons.colonnes(bandeau)
    assert largeur <= COLONNES_UTILES[PLANCHER[0]], (
        f"{module}.{nom} : le bandeau fait {largeur} colonnes pour "
        f"{COLONNES_UTILES[PLANCHER[0]]} quand le nom du projet est long")
    if not objet:
        return
    attendu = jetons.replier_ascii(objet) if ascii_seul else objet
    assert bandeau.rstrip().endswith(attendu), (
        f"{module}.{nom} a perdu la droite de son bandeau AU BORD : "
        f"{bandeau!r} ne se termine pas par {attendu!r}")


def test_le_projet_du_volet_de_BORD_force_VRAIMENT_l_abregement(sol):
    """Le volet symetrique, sans lequel le precedent pourrait ne rien mesurer.

    Si le nom ci-dessus cessait un jour d'etre assez long -- ou si la geometrie
    s'elargissait --, aucun bandeau ne serait plus abrege et le volet de bord
    serait vert **sans avoir approche la borne**. On exige donc que la marque
    d'abregement soit bien la, sur un nombre d'ecrans qu'un accident
    n'atteindrait pas.
    """
    abreges = [f"{module}.{nom}" for module, nom, cls in ECRANS
               if MARQUE[False] in monter(
                   FABRIQUES[(module, nom)](cls, sol),
                   projet=PROJET_QUI_FORCE_L_ABREGEMENT)[0].get("bandeau", "")]
    # Mesure du jour : DIX-SEPT bandeaux portent la marque au bord. Le seuil
    # est pose deux crans en dessous -- assez bas pour qu'un ecran retire ne le
    # fasse pas rougir a tort, assez haut pour qu'une geometrie elargie ou un
    # nom raccourci le franchisse.
    assert len(abreges) >= 15, (
        f"seuls {len(abreges)} bandeaux sont abreges au bord : le volet de "
        f"bord ne mesure plus la borne. {sorted(abreges)}")


def hors_du_repertoire_ascii(texte: str) -> set[str]:
    """Les caracteres qu'un rendu `--ascii` ne devrait pas porter."""
    return {caractere for caractere in texte if ord(caractere) > 127}


@pytest.mark.parametrize("module,nom,cls", CAS)
def test_en_ASCII_aucune_zone_ne_garde_un_caractere_HORS_ASCII(
        sol, module, nom, cls):
    """Ce que `--ascii` promet, dit comme une frontiere plutot qu'une intention.

    Le drapeau existe pour les terminaux qui ne rendent pas l'UTF-8 ; une seule
    colonne qui y echappe est un carre blanc a l'ecran. Le produit tient cette
    promesse aujourd'hui sur les 67 ecrans, chrome ET centre -- c'est mesure,
    pas suppose --, et c'est ce que ce volet fige.

    Il attrape en outre une famille entiere de defauts de cablage que la seule
    mesure des LARGEURS laisse passer : un repli qui n'est pas transmis, ou un
    bornage saute, laisse d'abord un glyphe UTF-8 en place -- il ne fait
    deborder la ligne que si elle etait deja pleine.
    """
    zones, centre, _ = monter(FABRIQUES[(module, nom)](cls, sol),
                              ascii_seul=True)
    for zone, texte in sorted(zones.items()):
        restes = hors_du_repertoire_ascii(texte)
        assert not restes, (
            f"{module}.{nom} garde {sorted(restes)} dans sa zone {zone} en "
            f"`--ascii` : {texte!r}")
    for rang, ligne in enumerate(centre):
        restes = hors_du_repertoire_ascii(ligne)
        assert not restes, (
            f"{module}.{nom} garde {sorted(restes)} en centre[{rang}] en "
            f"`--ascii` : {ligne!r}")


def test_en_UTF8_le_produit_emploie_VRAIMENT_des_glyphes_hors_ASCII(sol):
    """Le volet symetrique du precedent, et il n'est pas decoratif.

    Un produit qui n'ecrirait que de l'ASCII rendrait le volet ci-dessus vert
    sans qu'il mesure quoi que ce soit -- et c'est exactement ce qui
    arriverait si un jour le repli etait applique en UTF-8 aussi. On exige donc
    que le mode nominal, lui, porte bien les glyphes que le repli remplace.
    """
    porteurs = [f"{module}.{nom}" for module, nom, cls in ECRANS
                if any(hors_du_repertoire_ascii(texte)
                       for texte in monter(
                           FABRIQUES[(module, nom)](cls, sol))[0].values())]
    assert len(porteurs) >= 30, (
        f"seuls {len(porteurs)} ecrans portent un glyphe hors ASCII en mode "
        f"nominal : le volet du repli ne mesure presque plus rien. "
        f"{sorted(porteurs)}")


# ---------------------------------------------------------------------------
# La mesure du banc lui-meme -- regle des fabriques, points 1, 2 et 4
# ---------------------------------------------------------------------------

def test_le_banc_monte_ASSEZ_d_ecrans_DISTINGUABLES():
    """Un balayage sur une collection uniforme reste vert quelle que soit la
    permutation. On exige donc plusieurs ecrans, plusieurs modules et
    plusieurs titres -- et un cardinal qu'une regression ne peut pas franchir
    par accident."""
    assert len(ECRANS) >= 60, len(ECRANS)
    modules = {module for module, _, _ in ECRANS}
    assert len(modules) >= 20, sorted(modules)
    titres = {cls.titre for _, _, cls in ECRANS if cls.titre}
    assert len(titres) >= 5, sorted(titres)


#: Un bandeau qui tient, **compose par le produit** plutot que dessine ici :
#: c'est `Contexte.rendu` qui le fabrique, a la geometrie du plancher. Un
#: bandeau recopie a la main mesurerait la recopie, et il derive -- c'est
#: exactement ce que la frontiere des maquettes recopiees existe pour dire.
BANDEAU_QUI_TIENT = coque.Contexte("projet_demo", "Pdf").rendu(
    PLANCHER[0]).rstrip()

#: Trois zones de chrome **distinguables** -- des longueurs differentes, des
#: mots differents --, toutes tenant au plancher. Un remplissage uniforme
#: rendrait toute permutation invisible (regle des fabriques, point 1).
ZONES_QUI_TIENNENT = (("bandeau", BANDEAU_QUI_TIENT),
                      ("etat", "9 PDF · 126 pages"),
                      ("raccourcis", "Q quitter"))

#: Une ligne qui NE tient pas au plancher : 96 colonnes en UTF-8.
ZONE_QUI_DEBORDE = ("⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  "
                    "Échap ateliers  F1 aide  Q quitter  Ctrl+H caches")


def rendu_avec_la_cible_en(position: int) -> dict[str, str]:
    """Un rendu de quatre zones, la debordante placee en `position`.

    Les cles sont numerotees dans l'ordre de placement, si bien que le tri par
    cle d'`anomalies` suit ce meme ordre : la cible est reellement en tete, au
    milieu ou en queue de ce que la boucle lit.
    """
    tenues = list(ZONES_QUI_TIENNENT)
    entrees = (tenues[:position] + [("debordante", ZONE_QUI_DEBORDE)]
               + tenues[position:])
    return {f"{rang}_{nom}": texte
            for rang, (nom, texte) in enumerate(entrees)}


def test_anomalies_trouve_la_cible_EN_TETE():
    """Regle des fabriques, point 4, bord de tete. Un balayage qui partirait
    du deuxieme element -- `entrees[1:]`, un `next()` consomme -- resterait
    vert avec une cible au milieu."""
    trouvees = anomalies(rendu_avec_la_cible_en(0), [], False, PLANCHER)
    assert len(trouvees) == 1 and trouvees[0].startswith("0_debordante")


def test_anomalies_trouve_la_cible_AU_MILIEU():
    """Regle des fabriques, point 2 : la cible ailleurs qu'en premiere
    position. Un balayage qui rendrait toujours le premier element ne se
    demasque pas autrement."""
    trouvees = anomalies(rendu_avec_la_cible_en(1), [], False, PLANCHER)
    assert len(trouvees) == 1 and trouvees[0].startswith("1_debordante")


def test_anomalies_trouve_la_cible_EN_QUEUE():
    """Regle des fabriques, point 4, bord de queue -- le mode de panne que
    « au milieu » ne demasque PAS : `entrees[:-1]`, un `range(len - 1)`."""
    trouvees = anomalies(rendu_avec_la_cible_en(len(ZONES_QUI_TIENNENT)),
                         [], False, PLANCHER)
    assert len(trouvees) == 1 and trouvees[0].startswith("3_debordante")


def test_anomalies_NE_CRIE_PAS_sur_un_rendu_sain():
    """Le volet symetrique : sans cible, aucune zone n'est rendue. Sans lui,
    une fonction qui rendrait TOUTE zone passerait les trois tests de bord
    ci-dessus sans rien mesurer."""
    sain = {f"{rang}_{nom}": texte
            for rang, (nom, texte) in enumerate(ZONES_QUI_TIENNENT)}
    assert anomalies(sain, [], False, PLANCHER) == []


def test_le_repli_ASCII_ALLONGE_et_c_est_pourquoi_les_deux_modes_sont_joues():
    """Pourquoi ce banc monte chaque ecran DEUX fois plutot qu'une.

    Le repli ASCII n'est pas une decoration retiree : il **allonge**. `⏎` rend
    `Entree`, `—` rend `--`, `·` rend `.`, `…` rend `...`. Une ligne calee a
    exactement 76 colonnes en UTF-8 en fait donc davantage une fois repliee, et
    c'est le regime exact ou le bandeau a mordu le 2026-09-06 -- comme la ligne
    d'etat de `E5-2` mord aujourd'hui (`MONTEE-2`).

    **La mesure porte sur `jetons` et non sur `anomalies`**, et la distinction
    compte : `anomalies` mesure ce qu'un ecran a DEJA rendu, dans le mode ou il
    l'a rendu -- ce n'est pas elle qui replie. Ce test dit donc pourquoi les
    deux modes existent ; les tests de bord ci-dessus disent qu'`anomalies`
    voit la cible.
    """
    ligne = ("⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  Échap ateliers  "
             "F1 aide  Q quit")
    assert jetons.colonnes(ligne) == COLONNES_UTILES[80]
    repliee = jetons.replier_ascii(ligne)
    assert jetons.colonnes(repliee) > COLONNES_UTILES[80], jetons.colonnes(repliee)
    # Et la consequence, sur `anomalies` : la meme ligne tient en UTF-8 et
    # deborde une fois repliee. Deux verdicts DIFFERENTS sur un seul texte.
    assert anomalies({"z": ligne}, [], False, PLANCHER) == []
    assert len(anomalies({"z": repliee}, [], True, PLANCHER)) == 1


def test_anomalies_voit_une_marque_d_ABREGEMENT_en_queue():
    """Une ligne qui TIENT peut quand meme avoir perdu sa droite : c'est
    exactement le defaut du bandeau ASCII, ou la ligne faisait 76 colonnes
    **parce qu'**on venait de lui couper l'objet. La largeur seule ne le voit
    pas ; la marque en queue, si.

    On tolere la marque AILLEURS dans la ligne -- un chemin abrege en son
    milieu est un abregement voulu, pas une amputation de bord --, et c'est
    mesure dans les deux sens.
    """
    en_queue = {"z": "un chemin qui perd sa fin…"}
    au_milieu = {"z": "un chemin…abrege en son milieu"}
    assert len(anomalies(en_queue, [], False, PLANCHER)) == 1
    assert anomalies(au_milieu, [], False, PLANCHER) == []
    assert len(anomalies({"z": "un chemin ascii tronque..."},
                         [], True, PLANCHER)) == 1
    assert anomalies({"z": "un chemin ascii tronque..."},
                     [], False, PLANCHER) == []


def test_anomalies_voit_un_centre_TROP_HAUT_et_TROP_LARGE():
    """Les deux mesures du centre, et elles sont independantes : un centre de
    la bonne hauteur peut porter une ligne trop large, et l'inverse."""
    trop_haut = ["ligne %d" % rang for rang in range(30)]
    assert any("TROP HAUT" in a
               for a in anomalies({}, trop_haut, False, PLANCHER))
    assert anomalies({}, ["court"], False, PLANCHER) == []
    trop_large = ["x" * 90]
    assert any("centre[0] DEBORDE" in a
               for a in anomalies({}, trop_large, False, PLANCHER))


#: Un centre de quatre lignes qui tiennent, **distinguables** -- des longueurs
#: et des mots differents, jamais un remplissage uniforme.
CENTRE_QUI_TIENT = ("Planches", "  projet_demo_plan-04_25_planches.pdf",
                    "", "  Generer")


def centre_avec_la_cible_en(position: int) -> list[str]:
    """Le meme centre, une ligne de 90 colonnes glissee en `position`."""
    lignes = list(CENTRE_QUI_TIENT)
    return lignes[:position] + ["x" * 90] + lignes[position:]


@pytest.mark.parametrize("position,rang", [
    pytest.param(0, 0, id="tete"),
    pytest.param(2, 2, id="milieu"),
    pytest.param(len(CENTRE_QUI_TIENT), len(CENTRE_QUI_TIENT), id="queue"),
])
def test_anomalies_trouve_une_ligne_de_CENTRE_a_chaque_bord(position, rang):
    """Regle des fabriques, point 4, sur la SECONDE collection que balaye
    `anomalies`.

    Le centre est une liste distincte des zones, parcourue par une seconde
    boucle : les trois tests de bord posés sur les zones ne disent **rien**
    d'elle. Une troncature `centre[1:]` ou `centre[:-1]` y resterait invisible
    a toute cible posee au milieu -- et une ligne de centre trop large est
    exactement ce qu'un cartouche mal calibre produit.
    """
    trouvees = anomalies({}, centre_avec_la_cible_en(position), False, PLANCHER)
    assert len(trouvees) == 1, trouvees
    assert trouvees[0].startswith(f"centre[{rang}] DEBORDE")


def test_anomalies_NE_CRIE_PAS_sur_un_centre_sain():
    """Le volet symetrique des trois bords : sans cible, aucune ligne n'est
    rendue. Sans lui, une fonction qui rendrait TOUTE ligne de centre passerait
    les trois."""
    assert anomalies({}, list(CENTRE_QUI_TIENT), False, PLANCHER) == []


class _PorteurDeCompteur:
    """Un objet que l'ecran TIENT, et qui porte le pas du rotor."""

    def __init__(self, pas: int) -> None:
        self.pas = pas


class _EcranDeSynthese:
    """Le strict necessaire pour que `figer_le_rotor` ait quelque chose a
    balayer : un minuteur qui note qu'on l'a mis en pause, des objets tenus, et
    un redessin qui note qu'on l'a demande."""

    def __init__(self, tenus: list) -> None:
        self.minuteur = _MinuteurDeSynthese()
        for rang, tenu in enumerate(tenus):
            setattr(self, f"tenu_{rang}", tenu)
        self.redessine = 0

    def rafraichir(self) -> None:
        self.redessine += 1


class _MinuteurDeSynthese:
    def __init__(self) -> None:
        self.en_pause = False

    def pause(self) -> None:
        self.en_pause = True


def tenus_avec_le_compteur_en(position: int, combien: int = 4) -> list:
    """Quatre objets tenus, dont UN SEUL porte un pas non nul, a `position`.

    Point 1 de la regle des fabriques : les elements sont **distinguables** --
    trois objets nus et un porteur --, faute de quoi une permutation ou un
    balayage tronque resterait invisible.
    """
    tenus = [object() for _ in range(combien)]
    tenus[position] = _PorteurDeCompteur(7)
    return tenus


@pytest.mark.parametrize("position", [
    pytest.param(0, id="tete"),
    pytest.param(2, id="milieu"),
    pytest.param(3, id="queue"),
])
def test_figer_le_rotor_trouve_un_compteur_TENU_a_chaque_bord(position):
    """Le compteur du rotor n'est pas toujours sur l'ecran, et le balayage qui
    le cherche est une COLLECTION -- donc il se mesure aux deux bords.

    C'est la panne exacte du 2026-09-06 sur ce banc : `EcranEncodageEnCours`
    delegue son pas a son `passage`, une remise a zero qui ne regardait que
    l'ecran laissait le rotor libre, et la course de sante d'une campagne de
    mutation est devenue rouge sur `◒` contre `◐`. Une seule cible, posee au
    milieu, ne demasquerait pas un balayage tronque a un bord.
    """
    tenus = tenus_avec_le_compteur_en(position)
    ecran = _EcranDeSynthese(tenus)
    figer_le_rotor(ecran)
    assert tenus[position].pas == 0, (
        f"le compteur tenu en position {position} n'a pas ete remis a zero : "
        "un balayage tronque a ce bord laisse le rotor libre")
    assert ecran.minuteur.en_pause, "le minuteur n'a pas ete mis en pause"
    assert ecran.redessine == 1, "l'ecran n'a pas ete redessine apres la remise"


def test_sans_horloge_COUPE_le_minuteur_puis_le_REND():
    """La greffe en memoire se defait, et c'est ce qui la rend sure.

    Une greffe qui survit a son bloc contamine tous les bancs de la session --
    c'est le defaut que le `finally` ferme, et qu'aucun test positif ne verrait
    revenir.
    """
    avant = coque.Palier.__dict__.get("set_interval")
    with sans_horloge():
        pendant = coque.Palier.set_interval(object(), 0.1, print)
        assert isinstance(pendant, _MinuteurArrete), (
            "l'horloge n'est pas coupee : les ecrans a rotor avancent encore")
        pendant.pause(), pendant.stop(), pendant.resume()
    assert coque.Palier.__dict__.get("set_interval") is avant, (
        "la greffe a survecu a son bloc : tous les ecrans du reste de la "
        "session monteraient sans horloge")


def test_un_ecran_qui_COMPTE_par_tour_rend_DEUX_FOIS_la_meme_chose(sol):
    """Le cas reel qui a fait ecrire `sans_horloge`, et il n'est pas un rotor.

    `EcranDesLotsAEncoder` compte « un lot par tour de rotor » : un tick de
    plus entre deux montees rend `1 lot compté sur 3` la ou la precedente
    rendait `0`. Aucune remise a zero d'un compteur de rotor ne defait ce
    comptage -- seule l'absence d'horloge le fait.
    """
    cls = exp_lot.EcranDesLotsAEncoder
    cle = ("atelier_exports_lot", "EcranDesLotsAEncoder")
    premier = monter(FABRIQUES[cle](cls, sol))
    second = monter(FABRIQUES[cle](cls, sol))
    assert premier == second, (
        "deux montees du meme ecran ne rendent pas la meme chose : le banc "
        "mesure le temps qui passe")


def test_figer_le_rotor_NE_REDESSINE_PAS_un_compteur_DEJA_a_zero():
    """Un compteur au repos n'est pas un compteur remis : le distinguer est ce
    qui garde `compose` observable quand l'horloge est deja coupee."""
    ecran = _EcranDeSynthese([_PorteurDeCompteur(0)])
    figer_le_rotor(ecran)
    assert ecran.redessine == 0, (
        "un ecran dont rien ne bougeait a ete redessine : `rafraichir` "
        "reborne les trois zones et masque ce que `compose` a pose")


def test_figer_le_rotor_NE_REDESSINE_PAS_un_ecran_SANS_rotor():
    """La frontiere negative du redessin, et elle porte tout le volet 1.

    `Palier.rafraichir` reecrit le bandeau, l'etat et les raccourcis **en les
    bornant lui-meme**. Un redessin systematique repare donc ce que `compose`
    aurait mal pose, et le banc mesure le rattrapage au lieu de la faute :
    mesure faite, les trois mutants qui retirent le bornage de `compose`
    survivaient au banc ENTIER tant que ce redessin etait inconditionnel.
    """
    ecran = _EcranDeSynthese([object(), object()])
    figer_le_rotor(ecran)
    assert ecran.redessine == 0, (
        "un ecran sans rotor a ete redessine : le banc lit desormais le "
        "rattrapage de `rafraichir` et non ce que `compose` a pose")
    assert ecran.minuteur.en_pause, (
        "le minuteur doit etre arrete meme quand il n'y a aucun pas a remettre")


def test_figer_le_rotor_remet_AUSSI_le_compteur_porte_par_l_ECRAN():
    """Le volet symetrique : sans lui, un balayage qui ne regarderait QUE les
    objets tenus passerait les trois bords ci-dessus."""
    ecran = _EcranDeSynthese([])
    ecran.pas = 9
    ecran.pas_du_rotor = 4
    figer_le_rotor(ecran)
    assert (ecran.pas, ecran.pas_du_rotor) == (0, 0)


def test_figer_le_rotor_NE_TOUCHE_PAS_ce_qui_n_est_pas_un_compteur():
    """La frontiere negative du balayage. Il cherche deux noms et des entiers ;
    un booleen homonyme n'est pas un pas de rotor, et un objet sans compteur ne
    doit pas en gagner un."""
    ecran = _EcranDeSynthese([_PorteurDeCompteur(3)])
    ecran.tenu_0.pas_du_rotor = True     # homonyme, et pas un compteur
    nu = object()
    ecran.tenu_1 = nu
    figer_le_rotor(ecran)
    assert ecran.tenu_0.pas == 0
    assert ecran.tenu_0.pas_du_rotor is True, (
        "un booleen a ete pris pour un pas de rotor")
    assert not hasattr(nu, "pas"), "un compteur a ete POSE sur un objet nu"


def test_le_rotor_d_un_ecran_du_produit_est_FIGE_a_zero(sol):
    """Les tests de synthese ci-dessus mesurent le balayage ; celui-ci mesure
    qu'il attrape le cas REEL qui l'a fait ecrire.

    On monte l'ecran dont le compteur vit sur son `passage` et on relit le
    glyphe que `jetons.rotor` rend au pas zero -- **lu du produit**, jamais
    recopie : le paquet interdit d'ecrire ce caractere en dur, et ce banc n'a
    pas plus le droit que lui.
    """
    cls = exp_exec.EcranEncodageEnCours
    ecran = FABRIQUES[("atelier_exports_execution",
                       "EcranEncodageEnCours")](cls, sol)
    _zones, centre, _objet = monter(ecran)
    au_repos = jetons.rotor(0, False)
    tournant = [ligne for ligne in centre if au_repos in ligne]
    assert tournant, (
        f"aucune ligne ne porte le glyphe du rotor au repos {au_repos!r} : "
        f"le rotor a avance entre le montage et la lecture. {centre}")


def test_les_bornes_ecrites_ici_sont_CELLES_du_produit():
    """Le SEUL point de contact entre ce banc et la geometrie du produit.

    Il est ecrit comme une egalite entre deux nombres rediges separement, et
    non comme une lecture : c'est ce qui empeche les volets ci-dessus d'etre
    tautologiques. Deplacer une borne dans `jetons` fait rougir ici, et la
    conversation a lieu -- au lieu que toutes les attentes du banc suivent
    silencieusement le deplacement.
    """
    assert jetons.LARGEUR_PLANCHER == PLANCHER[0]
    assert jetons.HAUTEUR_PLANCHER == PLANCHER[1]
    for largeur, attendu in COLONNES_UTILES.items():
        assert jetons.largeur_utile(largeur) == attendu
    assert jetons.HAUTEUR_CENTRE_AU_PLANCHER == LIGNES_DE_CENTRE[24]


def test_ce_que_ce_banc_ne_mesure_pas(sol):
    """Les limites connues, **mesurees** plutot que declarees en prose.

    1. **un rappel injecte muet rend le clavier inobservable.** Le banc passe
       `RIEN` a tous les rappels de construction ; un ecran dont `Échap` mene
       au parcours consomme donc la touche et ne bouge pas. Ce n'est pas un
       defaut du produit, c'est la limite du banc, et elle est demontree
       ci-dessous plutot que supposee ;
    2. **un ecran n'est monte que dans UN etat.** Ses autres modes -- un refus
       d'affichage, une saisie en cours, un nom refuse -- vivent dans son banc
       propre.
    """
    # 1. La limite est demontree sur les deux comptes rendus de la suppression,
    #    dont `Échap` passe par `_sur_suite` (`_echapper_par_le_parcours`) : le
    #    banc injecte un rappel muet, donc la touche est CONSOMMEE et rien ne
    #    bouge. Le meme `Échap` sur l'`EcranResultat` generique, lui, appelle
    #    `revenir_aux_ateliers` directement et se voit -- c'est la difference
    #    entre un geste interne et un geste cable, et c'est tout le propos.
    plan = plan_de_suppression(sol)
    rapport = rapport_de_suppression()
    avant, _, _ = monter(suppr.EcranReussiteDeSuppression(plan, rapport,
                                                          sur_suite=RIEN))
    apres, _, _ = monter(suppr.EcranReussiteDeSuppression(plan, rapport,
                                                          sur_suite=RIEN),
                         touche="escape")
    assert avant == apres, (
        "cette limite vient d'etre fermee : le banc voit desormais l'effet "
        "d'une touche cablee sur un rappel injecte. Mettre le docstring a "
        "jour plutot que de le laisser mentir")

    # Le volet symetrique, sans lequel le precedent ne mesurerait rien : une
    # touche dont l'effet est INTERNE, elle, se voit. Sans ce volet, un banc
    # qui ne verrait plus AUCUNE touche passerait le test ci-dessus.
    generique, _, _ = monter(execution.EcranResultat(
        panneau_mesure(), suites=["A", "B"], sur_suite=RIEN, objet="x"))
    remonte, _, _ = monter(execution.EcranResultat(
        panneau_mesure(), suites=["A", "B"], sur_suite=RIEN, objet="x"),
        touche="escape")
    assert generique != remonte, (
        "le banc ne voit plus l'effet d'une touche meme quand il est interne "
        "a l'ecran : le volet du clavier ne mesure plus rien")

    # 2. Un seul etat par ecran : la table des fabriques a exactement une
    #    entree par classe, et c'est ce qui le dit.
    assert len(FABRIQUES) == len(set(FABRIQUES)), "cle dupliquee"
