# -*- coding: utf-8 -*-
"""Story 11.8, lot E -- `E4-3`, la confirmation de l'atelier Exports (AC 7).

Ce banc mesure `tui/atelier_exports_confirmation.py`, et **lui seul** : l'ecran
de conflit `E4-3b` a le sien (`test_atelier_exports_versions.py`). « Aucun lot
ne partage un fichier de banc avec un autre », et deux ecrans d'un meme lot n'y
gagneraient rien a se melanger -- ni `git add -N` ni `git commit -- <chemins>`
ne protegent a l'interieur d'un fichier partage.

Les quatre regles de mesure heritees, et elles commandent la forme des fabriques
--------------------------------------------------------------------------------
1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte**. Les deux boucles de ce module sont **les lignes du cartouche**
   (dix lignes, cible `Cadence du rushe`, sixieme) et **les issues** (trois,
   cible `Modifier les réglages`, deuxieme, celle que le curseur vise). Les
   valeurs des dix lignes sont **toutes differentes** : un remplissage uniforme
   rendrait invisible toute permutation d'appariement ;
2. **la position se verifie sur la liste que le code PARCOURT**, jamais sur
   celle que la fabrique croit ecrire ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « Cette issue est presente » ne mesure rien ; « l'ensemble des issues que le
   curseur peut viser au montage est **exactement** {Modifier} » mesure
   l'invariant ET son unicite ;
4. **une frontiere negative porte toujours son volet symetrique**, sans quoi un
   detecteur casse serait vert sur tout.

Ce que ce banc EPINGLE sans le corriger, et pourquoi
-----------------------------------------------------
`panneau.LigneChiffree.rendu` cale le chiffre **a DROITE**, quand la maquette
cale les valeurs **a gauche**, a une colonne fixe. C'est « l'ecart de tous les
`E*-3` du depot », deja epingle par le lot F de la story 11.7 : le corriger
toucherait `panneau.py`, partage par les quatre ateliers, et cette story ne le
modifie pas. :func:`test_le_cartouche_cale_le_chiffre_A_DROITE_et_l_ecart_est_CONSTATE`
le mesure au lieu de le taire.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from outils_frontiere import chaines_de_code

from mixed_media_utility import codec_profiles, encode, encode_master
from mixed_media_utility.io import naming
from mixed_media_utility.io.project_layout import OUTPUTS_DIRNAME
from mixed_media_utility.tui import atelier_exports_confirmation as confirmation
from mixed_media_utility.tui import execution, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.panneau import MENTION_MAJORANT, RIEN_ECRIT

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

SOURCE_DU_PRODUIT = Path(confirmation.__file__)
PAQUET_TUI = SOURCE_DU_PRODUIT.parent
MAQUETTE = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
            / "ux-tui-2026-08-27" / "maquettes"
            / "E4-3-exports-confirmation.txt")


# ===========================================================================
# Les fabriques -- aucune ne produit un element unique ni un remplissage
# uniforme, et la cible n'est jamais en premiere position.
# ===========================================================================

PROJET = "projet_demo"
LOT = "plan-04_25"
#: Les deux cadences du lot **different**, comme sur le lot de demonstration :
#: `fps_target` vaut 12,5 (la decimation) et la cadence source 25. Une fabrique
#: ou les deux coincideraient rendrait les deux lectures indiscernables.
CADENCE_SOURCE = "25"
FRAMES = 124
#: Les echantillons muxes **different** des frames distinctes sur la seconde
#: fabrique : c'est le nominal d'`EPIC11-ARB-192` (frames tenues deux fois), et
#: c'est ce qui empeche un test de confondre `frame_paths` et
#: `muxed_frame_paths` -- deux comptes que `render_summary` affiche cote a cote.
FRAMES_DECIMEES = 63
ECHANTILLONS_DECIMES = 125


def plan_de_coeur(dossier: Path, **champs) -> encode.EncodePlan:
    """Un `encode.EncodePlan` reel -- **l'objet que `render_summary` lit**.

    Il est construit a la main plutot que par `plan_encode` : la decision du
    coeur sonde des frames sur le disque et paie `ffprobe`, ce qu'un banc
    d'ecran n'a pas a faire. Ce qui compte pour l'AC 7.1 est que ce soit le
    **meme type d'objet** que le recapitulatif met en forme, et il l'est --
    les deux redactions lisent alors les memes attributs, et le banc les
    confronte.
    """
    frames = champs.pop("frames", FRAMES)
    echantillons = champs.pop("echantillons", frames)
    defauts = dict(
        project_dir=dossier,
        lot_id=LOT,
        lot_state="reconstruction",
        profile_id=codec_profiles.DEFAULT_PROFILE_ID,
        container=codec_profiles.PROFILES[codec_profiles.DEFAULT_PROFILE_ID].container,
        resolution=encode.resolve_output_resolution(None),
        source_size=(1920, 1080),
        frame_paths=tuple(Path(f"f{rang:04d}.tiff") for rang in range(frames)),
        muxed_frame_paths=tuple(Path(f"f{rang:04d}.tiff")
                                for rang in range(echantillons)),
        frame_rate=25.0,
        exact_frame_rate=CADENCE_SOURCE,
        timecode=encode.TimecodePlan(emitted="00:00:04:12",
                                     manifest_value="00:00:04:12",
                                     base_rate=CADENCE_SOURCE),
        verdict=encode.CompletenessVerdict(
            expected=frames, found=frames, synthetic_present=(),
            synthetic_missing=(), missing_pages=(), complete=True),
        container_tags={},
        output_path=(dossier / OUTPUTS_DIRNAME / naming.build_master_filename(
            lot_id=LOT,
            profile_id=codec_profiles.DEFAULT_PROFILE_ID,
            container=codec_profiles.PROFILES[
                codec_profiles.DEFAULT_PROFILE_ID].container)),
        overwrite=False,
    )
    defauts.update(champs)
    plan = encode.EncodePlan(**defauts)
    # La resolution du defaut n'a pas de geometrie tant qu'elle n'est pas
    # settlee : le plan reel arrive ici deja resolu, donc la fabrique aussi.
    if plan.resolution.size is None:
        plan = encode.EncodePlan(**{**defauts, "resolution": encode.TargetResolution(
            plan.resolution.requested, plan.resolution.origin,
            plan.resolution.resolution_id, (1920, 1080))})
    return plan


#: La ligne de reconstruction (`EPIC11-ARB-190`) : **donnee**, faute de
#: producteur de coeur au 2026-09-03. Voir le test qui nomme cet ecart.
RECONSTRUCTION = "v2 · 8 planches scannées le 02/09"


def master(dossier: Path, *, reconstruction: str | None = RECONSTRUCTION,
           **champs) -> confirmation.MasterAEcrire:
    return confirmation.plan_du_master(plan_de_coeur(dossier, **champs),
                                       reconstruction=reconstruction)


def lignes_de_la_maquette() -> list[str]:
    """Les lignes de la zone centrale de `E4-3`, marge de gauche retiree."""
    brut = MAQUETTE.read_text(encoding="utf-8").split("\n")[:24]
    return [ligne[2:-1].rstrip() for ligne in brut if ligne.startswith("│")]


def etat_de_la_maquette() -> str:
    return lignes_de_la_maquette()[-2]


def raccourcis_de_la_maquette() -> str:
    return lignes_de_la_maquette()[-1]


def issues_de_la_maquette() -> list[str]:
    """Les trois lignes d'issue de la maquette, curseur compris."""
    lignes = lignes_de_la_maquette()
    depart = next(rang for rang, ligne in enumerate(lignes)
                  if ligne.strip().startswith("└"))
    return [ligne for ligne in lignes[depart + 1:-2] if ligne.strip()]


# ===========================================================================
# Famille 0 -- les fabriques elles-memes, sans quoi tout ce qui suit mesure
# du vide
# ===========================================================================

def test_la_fabrique_du_cartouche_porte_DIX_lignes_toutes_DISTINGUABLES(tmp_path):
    """Regle des fabriques, points 1 et 2 : dix lignes, dix valeurs distinctes.

    Un cartouche dont deux lignes porteraient la meme valeur laisserait vivre
    une permutation d'appariement -- la classe de defaut que ce depot a payee
    trois fois (mutants `M33` de 5.6, `M25` de 5.7, cinq survivants de 5.8).
    """
    lignes = confirmation.lignes_du_cartouche(master(tmp_path))
    assert len(lignes) == 10, [ligne.libelle for ligne in lignes]
    valeurs = [ligne.chiffre for ligne in lignes]
    assert len(set(valeurs)) == len(valeurs), valeurs
    libelles = [ligne.libelle for ligne in lignes]
    assert len(set(libelles)) == len(libelles), libelles


def test_la_cible_des_mesures_de_ligne_est_AU_MILIEU_du_cartouche(tmp_path):
    """La cadence est la sixieme des dix : ni premiere, ni derniere.

    Une cible en premiere position laisserait vivre un `find` qui rend toujours
    le premier element ; en derniere, un `continue` -> `break`.
    """
    libelles = [ligne.libelle
                for ligne in confirmation.lignes_du_cartouche(master(tmp_path))]
    rang = libelles.index(confirmation.LIBELLE_CADENCE)
    assert rang == 5, libelles
    assert confirmation.LIBELLE_CADENCE not in (libelles[0], libelles[-1])


def test_les_deux_COMPTES_de_la_fabrique_decimee_different(tmp_path):
    """Sans cette difference, `frame_paths` et `muxed_frame_paths` seraient
    indiscernables et l'AC 7.1 serait verte quelle que soit la lecture."""
    plan = plan_de_coeur(tmp_path, frames=FRAMES_DECIMEES,
                         echantillons=ECHANTILLONS_DECIMES)
    assert plan.frame_count != len(plan.muxed_frame_paths)


# ===========================================================================
# Famille 1 -- AC 7.1 : le cartouche est DERIVE de `render_summary`
# ===========================================================================

def test_chaque_famille_du_cartouche_se_retrouve_dans_render_summary(tmp_path):
    """AC 7.1, dans sa forme la plus dure : la confrontation au coeur.

    Chaque valeur affichee est cherchee dans le recapitulatif que le coeur
    emet **sur le meme plan**. Un ecran qui rederiverait un chiffre le
    passerait un jour et le raterait le lendemain, ce qui est exactement le
    but : la mesure ne compare pas deux textes, elle compare deux **lectures
    du meme objet**.
    """
    plan = plan_de_coeur(tmp_path)
    fiche = confirmation.plan_du_master(plan)
    recapitulatif = encode.render_summary(plan)
    for valeur in (fiche.nom, fiche.lot_id, fiche.lot_state, fiche.profil,
                   fiche.conteneur, fiche.cadence, fiche.colorimetrie,
                   fiche.timecode):
        assert str(valeur) in recapitulatif, valeur
    for compte in (fiche.frames, fiche.attendues, fiche.echantillons,
                   fiche.mires):
        assert str(compte) in recapitulatif, compte
    for taille in (fiche.geometrie, fiche.source):
        assert f"{taille[0]}x{taille[1]}" in recapitulatif, taille


def test_les_deux_COMPTES_de_la_cadence_ne_se_confondent_pas(tmp_path):
    """`render_summary` affiche les echantillons **et** les frames distinctes.

    C'est le nominal d'`EPIC11-ARB-192` -- un lot 12p5 ne d'un rushe 25p tient
    chaque frame deux fois --, et un ecran qui n'afficherait qu'un des deux
    comptes mentirait sur la moitie du travail. La fabrique decimee les rend
    differents, donc l'inversion se voit.
    """
    plan = plan_de_coeur(tmp_path, frames=FRAMES_DECIMEES,
                         echantillons=ECHANTILLONS_DECIMES)
    fiche = confirmation.plan_du_master(plan)
    assert fiche.frames == FRAMES_DECIMEES
    assert fiche.echantillons == ECHANTILLONS_DECIMES
    ligne = confirmation.ligne_de_la_cadence(fiche).chiffre
    assert f"{ECHANTILLONS_DECIMES} échantillons" in ligne
    assert f"{FRAMES_DECIMEES} frames" in ligne


def test_le_POIDS_est_celui_du_plan_et_jamais_une_seconde_estimation(tmp_path):
    """`EncodePlan.estimated_bytes` est un **majorant** que le coeur calcule.

    Le recalculer ici en ferait une seconde verite, et l'ecart ne se verrait
    que sur un disque plein. On mesure donc que le chiffre suit le plan quand
    le plan change -- une constante recopiee ne suivrait pas.
    """
    petit = confirmation.plan_du_master(plan_de_coeur(tmp_path, frames=10,
                                                      echantillons=10))
    grand = confirmation.plan_du_master(plan_de_coeur(tmp_path))
    assert petit.octets_majorants < grand.octets_majorants
    assert grand.octets_majorants == plan_de_coeur(tmp_path).estimated_bytes


def test_la_ligne_de_poids_porte_le_TILDE_et_la_mention_de_MAJORANT(tmp_path):
    """`EPIC11-ARB-4` : ce qui est estime se distingue de ce qui est mesure.

    Les deux canaux cohabitent, et c'est voulu -- le tilde se lit dans le
    chiffre, la mention se lit dans la colonne. La mention est posee par
    `LigneChiffree` elle-meme, jamais ecrite ici.
    """
    ligne = confirmation.ligne_du_poids(master(tmp_path))
    assert ligne.majorant is True
    assert ligne.valeur.startswith("~")
    assert MENTION_MAJORANT in ligne.chiffre
    assert MENTION_MAJORANT not in set(chaines_de_code(SOURCE_DU_PRODUIT))


def test_un_poids_INCONNU_fait_disparaitre_la_ligne_au_lieu_de_rendre_zero(
        tmp_path):
    """« Un champ que la source ne porte pas est omis » (`DESIGN.md` §3).

    Annoncer `0 Go` serait affirmer qu'on a pese.
    """
    sans = confirmation.MasterAEcrire(
        nom="m.mov", lot_id=LOT, lot_state="scan", profil="p", conteneur="c",
        colorimetrie="bt709", geometrie=None, source=None, cadence="25")
    assert confirmation.ligne_du_poids(sans) is None
    libelles = [ligne.libelle for ligne in confirmation.lignes_du_cartouche(sans)]
    assert confirmation.LIBELLE_POIDS not in libelles


def test_un_timecode_ABSENT_ne_s_invente_pas(tmp_path):
    """Le coeur rend `None` sur une planche 2.0 : la ligne disparait.

    Afficher `00:00:00:00` designerait une **autre image** que celle du lot --
    c'est le motif exact pour lequel `plan_timecode` refuse de deviner.
    """
    plan = plan_de_coeur(tmp_path, timecode=encode.TimecodePlan(emitted=None))
    fiche = confirmation.plan_du_master(plan)
    assert confirmation.ligne_du_timecode(fiche) is None
    libelles = [ligne.libelle
                for ligne in confirmation.lignes_du_cartouche(fiche)]
    assert confirmation.LIBELLE_TIMECODE not in libelles


def test_l_ordre_EXACT_des_libelles_du_cartouche(tmp_path):
    """L'egalite est une **liste ordonnee**, jamais un ensemble.

    L'ordre du cartouche est celui de la maquette -- ce qui sera produit, d'ou
    ca vient, comment c'est encode, ce que ca contient, ce que ca coute, ou ca
    va --, et une ligne qui remonterait changerait la lecture sans rien casser
    d'autre.
    """
    libelles = [ligne.libelle
                for ligne in confirmation.lignes_du_cartouche(master(tmp_path))]
    assert libelles == [
        confirmation.LIBELLE_MASTER,
        confirmation.LIBELLE_LOT,
        confirmation.LIBELLE_RECONSTRUCTION,
        confirmation.LIBELLE_PROFIL,
        confirmation.LIBELLE_RESOLUTION,
        confirmation.LIBELLE_CADENCE,
        confirmation.LIBELLE_FRAMES,
        confirmation.LIBELLE_TIMECODE,
        confirmation.LIBELLE_POIDS,
        "Destination",
    ]


def test_les_libelles_du_cartouche_sont_ceux_de_la_MAQUETTE_verbatim():
    """Les dix libelles se lisent dans la maquette validee, mot pour mot."""
    maquette = MAQUETTE.read_text(encoding="utf-8")
    for libelle in (confirmation.LIBELLE_MASTER, confirmation.LIBELLE_LOT,
                    confirmation.LIBELLE_RECONSTRUCTION,
                    confirmation.LIBELLE_PROFIL,
                    confirmation.LIBELLE_RESOLUTION,
                    confirmation.LIBELLE_CADENCE,
                    confirmation.LIBELLE_FRAMES,
                    confirmation.LIBELLE_TIMECODE,
                    confirmation.LIBELLE_POIDS):
        assert libelle in maquette, libelle


def test_le_jeton_de_completude_couvre_EXACTEMENT_les_trois_etats_de_l_AC_5_2(
        tmp_path):
    """Ensemble exact des trois verdicts, et **l'ordre compte**.

    « Si c'est complet on n'a pas de mires » (Egan, 2026-09-03) : tester la
    completude d'abord ne masque donc rien, alors que tester les mires d'abord
    ferait rendre `▲` a un lot complet dont le registre de mires serait perime.
    """
    complet = master(tmp_path)
    mires = confirmation.plan_du_master(plan_de_coeur(
        tmp_path, verdict=encode.CompletenessVerdict(
            expected=FRAMES, found=FRAMES - 2,
            synthetic_present=("a.tiff", "b.tiff"), synthetic_missing=(),
            missing_pages=(), complete=False)))
    incomplet = confirmation.plan_du_master(plan_de_coeur(
        tmp_path, verdict=encode.CompletenessVerdict(
            expected=FRAMES, found=FRAMES - 1, synthetic_present=(),
            synthetic_missing=(), missing_pages=(3,), complete=False)))
    table = jetons.GLYPHES
    assert confirmation.jeton_de_completude(complet) == (
        f"{table['complete']} {confirmation.ETAT_COMPLET}")
    assert confirmation.jeton_de_completude(mires) == (
        f"{table['substitute']} 2 mires")
    assert confirmation.jeton_de_completude(incomplet) == (
        f"{table['absent']} {confirmation.ETAT_INCOMPLET}")
    # Les trois verdicts rendent trois jetons DISTINCTS : deux egaux
    # rendraient la mesure inutile.
    rendus = {confirmation.jeton_de_completude(fiche)
              for fiche in (complet, mires, incomplet)}
    assert len(rendus) == 3


def test_le_pluriel_des_mires_suit_le_COMPTE(tmp_path):
    """« 1 mire », « 2 mires ». Le pluriel suit le compte, jamais un `+ "s"`."""
    une = confirmation.plan_du_master(plan_de_coeur(
        tmp_path, verdict=encode.CompletenessVerdict(
            expected=FRAMES, found=FRAMES - 1, synthetic_present=("a.tiff",),
            synthetic_missing=(), missing_pages=(), complete=False)))
    assert confirmation.jeton_de_completude(une).endswith("1 mire")
    assert "0 mire" in confirmation.ligne_des_frames(master(tmp_path)).chiffre


def test_un_lot_SANS_cardinal_attendu_ne_compare_pas_a_zero(tmp_path):
    """`render_summary` ecrit « cardinal inconnu » ; ici la comparaison
    disparait plutot que de rendre un « sur 0 » qui serait faux."""
    fiche = confirmation.plan_du_master(plan_de_coeur(
        tmp_path, verdict=encode.CompletenessVerdict(
            expected=None, found=FRAMES, synthetic_present=(),
            synthetic_missing=(), missing_pages=(), complete=False)))
    ligne = confirmation.ligne_des_frames(fiche).chiffre
    assert " sur " not in ligne
    assert f"{FRAMES} conformes" in ligne


# ===========================================================================
# Famille 2 -- l'avertissement du coeur sur la cadence source (ARB-185)
# ===========================================================================

def test_la_note_de_cadence_est_celle_du_COEUR_et_n_est_pas_paraphrasee(
        tmp_path):
    """`EPIC11-ARB-185` : « l'avertissement se lit la ou le coeur le rend ».

    La note vit sur le plan (`source_rate_override_note`) et traverse verbatim.
    Le test la compare **mot pour mot** : une paraphrase serait exactement ce
    que l'arbitrage interdit.
    """
    _brute, _exacte, note = encode.resolve_source_rate(
        {"lot_id": LOT, "timecode_base_fps": 25}, cadence_source_override="30")
    fiche = confirmation.plan_du_master(
        plan_de_coeur(tmp_path, source_rate_override_note=note))
    ligne = confirmation.ligne_de_la_note_de_cadence(fiche)
    assert ligne is not None
    assert ligne.chiffre == note


def test_sans_divergence_AUCUNE_ligne_de_note_ne_parait(tmp_path):
    """Le cas nominal ne signale rien : le plan ne porte pas de note."""
    fiche = master(tmp_path)
    assert fiche.note_de_cadence == ""
    assert confirmation.ligne_de_la_note_de_cadence(fiche) is None
    libelles = [ligne.libelle
                for ligne in confirmation.lignes_du_cartouche(fiche)]
    assert confirmation.LIBELLE_NOTE_DE_CADENCE not in libelles


def test_le_DEFAUT_DE_COEUR_de_la_note_redondante_ATTEINT_cet_ecran():
    """**Signalement, pas correction** (lot D, signalement 4).

    `resolve_source_rate` emet sa note d'ecrasement **meme quand la valeur
    fournie EGALE celle du lot** : elle annonce alors une divergence qui
    n'existe pas, sur le cas le plus frequent qui soit. Le lot D l'a contourne
    en amont, en ne transmettant l'option que sur divergence reelle ; ce
    lot-ci **ne recopie pas le contournement** -- il mesure que le defaut
    l'atteint, ce qui rend la correction de coeur opposable.

    Le jour ou le coeur est corrige, ce test rougit **dans le sens de la
    reparation**, et c'est ce qu'on veut d'une dette mesuree.
    """
    _brute, _exacte, note = encode.resolve_source_rate(
        {"lot_id": LOT, "timecode_base_fps": 25}, cadence_source_override="25")
    assert note is not None, (
        "defaut de coeur ferme : retirer ce test et la ligne de note "
        "redondante qu'il justifie")
    assert "25" in note


def test_la_note_du_coeur_NOMME_une_option_de_LIGNE_DE_COMMANDE():
    """**Signalement, pas correction** (lot D, signalement 5).

    `EPIC11-ARB-185` impose d'afficher l'avertissement du coeur, pas de le
    paraphraser -- donc cet ecran affiche une phrase qui nomme
    `--cadence-source`, une option qui n'a **aucun sens** dans une TUI. Meme
    famille que le cul-de-sac `--nouvelle-version` que cette story ferme au
    refus de `check_output_destination`.

    Le test le **constate** : la correction est un travail de coeur, et la
    masquer ici ferait de cet ecran le seul endroit ou l'avertissement du
    produit ne se lit pas.
    """
    _b, _e, note = encode.resolve_source_rate(
        {"lot_id": LOT, "timecode_base_fps": 25}, cadence_source_override="30")
    assert "--cadence-source" in note
    # Et l'ecran ne la reecrit pas : aucun litteral d'option n'est d'ici.
    litteraux = " ".join(chaines_de_code(SOURCE_DU_PRODUIT))
    assert "--cadence-source" not in litteraux


# ===========================================================================
# Famille 3 -- AC 7.2 et AC 7.3 : les issues, et le curseur
# ===========================================================================

def test_les_TROIS_issues_sont_EXACTEMENT_celles_de_la_maquette(tmp_path):
    """Ensemble exact **et** ordre : l'ordre est celui de la deliberation."""
    choix = confirmation.issues_de_la_confirmation(master(tmp_path))
    assert [issue.cle for issue in choix.issues] == [
        confirmation.ISSUE_ENCODER, confirmation.ISSUE_MODIFIER,
        confirmation.ISSUE_ANNULER]
    assert [issue.libelle for issue in choix.issues] == [
        confirmation.LIBELLE_ENCODER, confirmation.LIBELLE_MODIFIER,
        confirmation.LIBELLE_ANNULER]


def test_les_issues_sont_celles_de_la_MAQUETTE_curseur_compris(tmp_path):
    """La comparaison porte sur les libelles **et** sur la ligne du curseur.

    Elle ne porte pas sur l'indentation : `execution.EcranChiffre` rend les
    issues sans marge, quand la maquette les indente de quatre colonnes. C'est
    l'ecart de l'ecran partage, deja epingle par `E5-3`, et cette story ne
    modifie pas `execution.py`.
    """
    choix = confirmation.issues_de_la_confirmation(master(tmp_path))
    dessinees = issues_de_la_maquette()
    curseur = jetons.GLYPHES["curseur"]
    assert [ligne.replace(curseur, "").strip() for ligne in dessinees] == [
        issue.libelle for issue in choix.issues]
    vise = [rang for rang, ligne in enumerate(dessinees) if curseur in ligne]
    assert vise == [choix.curseur], (dessinees, choix.curseur)


def test_l_ensemble_des_issues_qui_ECRIVENT_est_exactement_ENCODER(tmp_path):
    """Une assertion positive laisserait passer une issue qui ecrit de trop.

    C'est ce qui commande le curseur : `ChoixExclusif.__post_init__` le place
    sur la premiere issue qui n'ecrit pas, donc l'ensemble des issues qui
    ecrivent **est** la mesure de l'AC 7.3.
    """
    choix = confirmation.issues_de_la_confirmation(master(tmp_path))
    assert {issue.cle for issue in choix.issues if issue.ecrit} == {
        confirmation.ISSUE_ENCODER}


def test_au_montage_le_curseur_vise_EXACTEMENT_modifier(tmp_path):
    """AC 7.3, en ensemble exact plutot qu'en negation.

    « Le curseur ne vise pas Encoder » est faible : il laisserait passer un
    curseur pose sur `Annuler`, c'est-a-dire un ecran qui ne montre plus la
    sortie que l'operateur cherche. L'ensemble des issues visables au montage
    est **exactement** {Modifier}.
    """
    for _ in range(3):
        choix = confirmation.issues_de_la_confirmation(master(tmp_path))
        vises = {choix.issues[choix.curseur].cle}
        assert vises == {confirmation.ISSUE_MODIFIER}
        assert choix.issues[choix.curseur].ecrit is False
        assert choix.retenue is None


def test_le_deplacement_du_curseur_ne_RETIENT_rien(tmp_path):
    """`EPIC11-ARB-7` : parcourir n'est pas choisir."""
    choix = confirmation.issues_de_la_confirmation(master(tmp_path))
    choix.deplacer(-1)
    assert choix.issues[choix.curseur].cle == confirmation.ISSUE_ENCODER
    assert choix.retenue is None


def test_le_module_ne_POSE_pas_le_curseur_lui_meme():
    """Frontiere : l'invariant est **leve a la construction**, pas reecrit.

    Un ecran qui poserait `curseur = 1` a la main rendrait le meme dessin et
    cesserait de suivre `panneau.ChoixExclusif` le jour ou une issue s'ajoute.
    La mesure porte sur le texte du module : aucune affectation de curseur.
    """
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert "curseur =" not in source
    assert ".curseur" not in source
    # Volet symetrique : l'invariant existe bien et il est mesurable.
    assert "ecrit=True" in source


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_rendu_des_issues_porte_la_FLECHE_SEULE(tmp_path, ascii_seul):
    """`EPIC11-ARB-45` / `-126` : « Flèche seule ! C'est uniquement dans les
    listes à cocher qu'on trouve les deux »."""
    lignes = confirmation.issues_de_la_confirmation(
        master(tmp_path)).rendu(ascii_seul)
    table = jetons.glyphes(ascii_seul)
    for interdit in (table["coche"], table["decoche"],
                     table["exclusif-retenu"], table["exclusif-libre"]):
        assert all(interdit not in ligne for ligne in lignes), interdit
    assert sum(ligne.startswith(table["curseur"]) for ligne in lignes) == 1


# ===========================================================================
# Famille 4 -- AC 7.4 : afficher ne consomme rien, et rien n'est ecrit
# ===========================================================================

#: Les noms que le coeur emploie pour DECIDER d'un rang. Aucun n'a sa place
#: dans un ecran : `EPIC11-ARB-92`, « il ne faut pas rendre le rang ».
NOMS_DE_RANG = ("resolve_master_version_rank", "masters_version_watermark",
                "cle_de_famille_de_master", "prochain_rang", "ligne_d_eau",
                "version_ranks", "RANG_ORIGINE", "VERSION_RANK_MAX")


def test_le_module_ne_NOMME_aucune_fonction_de_rang_du_coeur():
    """Frontiere negative de l'AC 7.4, doublee de son volet symetrique.

    Un ecran qui connaitrait le vocabulaire du calcul aurait, de fait, de quoi
    le refaire. La frontiere porte sur le **texte** du module, prose comprise :
    c'est la forme la plus forte, et c'est celle que la story 11.6 a posee.
    """
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    trouves = [nom for nom in NOMS_DE_RANG if nom in source]
    assert trouves == [], trouves
    # Volet symetrique : ces noms EXISTENT bien au coeur, donc il y avait
    # quelque chose a ne pas nommer.
    assert hasattr(encode, "resolve_master_version_rank")
    assert hasattr(encode, "masters_version_watermark")


def test_composer_l_ecran_trois_fois_n_ECRIT_rien_sur_le_disque(tmp_path):
    """AC 7.4 au niveau de la TUI : la mesure est faite aux **inodes**.

    Le versant manifeste est mesure par le banc de coeur
    (`tests/unit/test_versions_de_master.py::test_afficher_un_rang_ne_le_CONSOMME_pas`) ;
    celui-ci mesure que l'ecran lui-meme ne touche a rien -- ni fichier neuf,
    ni horodatage bouge, ni inode change. Trois montages, comme l'AC 4.4 les
    demande.
    """
    projet = tmp_path / PROJET
    (projet / OUTPUTS_DIRNAME).mkdir(parents=True)
    temoin = projet / OUTPUTS_DIRNAME / "temoin.mov"
    temoin.write_bytes(b"master")
    avant = {chemin: chemin.stat() for chemin in sorted(projet.rglob("*"))}

    for _ in range(3):
        fiche = master(projet)
        confirmation.panneau_de_la_confirmation(fiche).rendu(80)
        confirmation.issues_de_la_confirmation(fiche)
        confirmation.mesure_de_la_confirmation(fiche)

    apres = {chemin: chemin.stat() for chemin in sorted(projet.rglob("*"))}
    assert set(apres) == set(avant)
    for chemin, etat in avant.items():
        assert apres[chemin].st_mtime_ns == etat.st_mtime_ns, chemin
        assert apres[chemin].st_ino == etat.st_ino, chemin


# ===========================================================================
# Famille 5 -- AC 7.5 : la ligne de raccourcis est LA SIENNE
# ===========================================================================

def test_la_ligne_de_raccourcis_n_est_PAS_celle_de_l_ecran_partage():
    """AC 7.5 : `RACCOURCIS_CONFIRMATION` promet une edition de nom retiree.

    `EPIC11-ARB-141` a retire l'edition des noms de cet atelier, et
    `encode_master.encoder_le_master_du_lot` n'a aucun parametre de nom --
    mesure, pas supposition. Annoncer `Tab éditer les noms` promettrait une
    touche qui ne fait rien.
    """
    assert (confirmation.RACCOURCIS_EXPORTS_CONFIRMATION
            != execution.RACCOURCIS_CONFIRMATION)
    assert "Tab" in execution.RACCOURCIS_CONFIRMATION
    assert "Tab" not in confirmation.RACCOURCIS_EXPORTS_CONFIRMATION
    assert (confirmation.EcranExportsConfirmation.raccourcis
            == confirmation.RACCOURCIS_EXPORTS_CONFIRMATION)


def test_la_ligne_de_raccourcis_est_celle_de_la_MAQUETTE_verbatim():
    assert (confirmation.RACCOURCIS_EXPORTS_CONFIRMATION
            == raccourcis_de_la_maquette())


def test_AUCUN_module_de_l_atelier_ne_promet_d_EDITER_LE_NOM():
    """Frontiere negative exigee par l'AC 6.4 et l'AC 7.5.

    Le grep porte sur **tous** les modules de l'atelier Exports, prose
    comprise, et sur les deux orthographes que le depot emploie. Son volet
    symetrique est le test precedent : la constante partagee, elle, la porte
    bien -- donc la frontiere mesure quelque chose de reel.
    """
    modules = sorted(PAQUET_TUI.glob("atelier_exports*.py"))
    assert len(modules) >= 3, modules
    for module in modules:
        texte = module.read_text(encoding="utf-8")
        for interdit in ("éditer le nom", "editer le nom", "éditer les noms"):
            assert interdit not in texte, (module.name, interdit)
    assert "éditer les noms" in execution.RACCOURCIS_CONFIRMATION


def test_l_ecran_n_ouvre_AUCUN_champ_de_nom(tmp_path):
    """`EPIC11-ARB-141` par **absence** de champ, pas par une garde ajoutee.

    Le `ModeleNoms` est vide, donc `Tab` n'a aucune destination et
    `EcranChiffre.traiter` le rend inerte de lui-meme.
    """
    ecran = confirmation.EcranExportsConfirmation(master(tmp_path),
                                                  sur_issue=lambda issue: None)
    assert len(ecran.noms) == 0
    assert ecran.traiter("tab") is False
    assert ecran.noms.en_edition is False


def test_le_point_d_entree_de_coeur_n_a_AUCUN_parametre_de_nom():
    """Le fait qui rend le retrait **mesure** plutot que suppose (AC 2.4).

    Si `encoder_le_master_du_lot` gagnait un jour un parametre de nom, cette
    frontiere rougirait et le retrait redeviendrait discutable -- ce qui est
    exactement ce qu'`EPIC11-ARB-141` demande d'un retrait reversible.
    """
    mots = encode_master.MOTS_CLES_DE_LA_DECISION
    assert not any("nom" in mot or "name" in mot for mot in mots), mots


# ===========================================================================
# Famille 6 -- la ligne d'etat et le bandeau : des MESURES
# ===========================================================================

def test_la_ligne_d_etat_est_celle_de_la_maquette_DANS_SA_FORME(tmp_path):
    """`124 frames · ~ <poids> — rien n'a encore été écrit`.

    Le poids differe de celui de la maquette -- elle a ecrit `1,4 Go` a la
    main pour un lot de demonstration, le produit pese le plan --, donc la
    comparaison porte sur la **forme** : le compte de frames, le tilde, et la
    queue verbatim.
    """
    ligne = confirmation.mesure_de_la_confirmation(master(tmp_path))
    dessinee = etat_de_la_maquette()
    assert ligne.startswith(f"{FRAMES} frames")
    assert confirmation.SEPARATEUR + "~ " in ligne
    assert ligne.endswith(confirmation.LIAISON_DE_LA_MESURE
                          + confirmation.QUEUE_RIEN_ECRIT)
    assert dessinee.endswith(confirmation.LIAISON_DE_LA_MESURE
                             + confirmation.QUEUE_RIEN_ECRIT)


def test_la_queue_est_DERIVEE_de_panneau_RIEN_ECRIT_et_jamais_recopiee():
    """Une seconde redaction divergerait au premier ajustement d'accent -- et
    une phrase desaccentuee a la source rendrait le repli ASCII indistinguable
    du nominal, defaut paye par le finding `I6`."""
    assert confirmation.QUEUE_RIEN_ECRIT == (
        RIEN_ECRIT[0].lower() + RIEN_ECRIT[1:].rstrip("."))
    assert confirmation.QUEUE_RIEN_ECRIT not in set(
        chaines_de_code(SOURCE_DU_PRODUIT))


def test_la_ligne_d_etat_ne_porte_AUCUNE_touche(tmp_path):
    """`EPIC11-ARB-56` : aucune touche, aucun conseil, aucun motif."""
    ligne = confirmation.mesure_de_la_confirmation(master(tmp_path))
    for touche in ("⏎", "Tab", "Échap", "F1", "↑", "↓", "Entree"):
        assert touche not in ligne, touche


def test_une_mesure_INCONNUE_ne_laisse_pas_un_separateur_de_TETE():
    """Le module retire partout les segments qu'il ne sait pas remplir ; le
    separateur de tete en serait la seule exception, et il annoncerait une
    mesure qui n'existe pas."""
    nue = confirmation.MasterAEcrire(
        nom="m.mov", lot_id=LOT, lot_state="scan", profil="p", conteneur="c",
        colorimetrie="bt709", geometrie=None, source=None, cadence="25",
        frames=None)
    assert confirmation.mesure_de_la_confirmation(nue) == (
        confirmation.QUEUE_RIEN_ECRIT)


def test_le_bandeau_porte_le_lot_travaille(tmp_path):
    """`plan-04_25 · 124 f`, comme `E4-2` le porte deja : le bandeau ne bouge
    pas quand on passe des reglages a la confirmation."""
    assert confirmation.bandeau_du_master(master(tmp_path)) == (
        f"{LOT}{confirmation.SEPARATEUR}{FRAMES} f")
    assert confirmation.bandeau_du_master(master(tmp_path)) in (
        MAQUETTE.read_text(encoding="utf-8"))


# ===========================================================================
# Famille 7 -- ce que ce lot EPINGLE au lieu de le corriger
# ===========================================================================

def test_le_cartouche_cale_le_chiffre_A_DROITE_et_l_ecart_est_CONSTATE(tmp_path):
    """L'ecart de grille de tous les `E*-3` du depot, mesure plutot que tu.

    `LigneChiffree.rendu` cale a droite ; la maquette cale a gauche, a une
    colonne fixe. Le corriger toucherait `panneau.py`, partage par les quatre
    ateliers. Le jour ou il sera corrige, ce test rougira -- dans le sens de la
    reparation.
    """
    rendu = confirmation.panneau_de_la_confirmation(master(tmp_path)).rendu(80)
    premiere = rendu[0]
    assert premiere.startswith(confirmation.LIBELLE_MASTER)
    assert premiere.rstrip() == premiere, "le chiffre est cale a droite"
    # Et la maquette, elle, cale a gauche a une colonne fixe.
    dessinee = next(ligne for ligne in lignes_de_la_maquette()
                    if confirmation.LIBELLE_MASTER in ligne)
    assert dessinee.rstrip() != dessinee.strip()


def test_la_ligne_de_RECONSTRUCTION_n_a_aucun_producteur_de_coeur(tmp_path):
    """**Signalement** : `EPIC11-ARB-190` dessine une ligne que rien ne sert.

    Le coeur qui la rend est la story 6.8, lancee en parallele. Elle est donc
    **donnee** et facultative : sans elle, la ligne disparait plutot que
    d'annoncer une version inventee -- « deux passes differentes portant le
    meme numero » est le pire mode de panne du versionnage.

    Le jour ou la 6.8 livre, `plan_du_master` la lira du coeur et ce test
    changera de camp.
    """
    sans = confirmation.plan_du_master(plan_de_coeur(tmp_path))
    assert sans.reconstruction is None
    assert confirmation.ligne_de_la_reconstruction(sans) is None
    avec = master(tmp_path)
    assert confirmation.ligne_de_la_reconstruction(avec).chiffre == RECONSTRUCTION
    # Et la maquette validee, elle, la dessine : l'ecart est bien reel.
    assert confirmation.LIBELLE_RECONSTRUCTION in MAQUETTE.read_text(
        encoding="utf-8")


# ===========================================================================
# Famille 8 -- la grille, les deux regimes, et les frontieres de paquet
# ===========================================================================

def test_la_MESURE_declaree_de_la_ligne_de_raccourcis_est_EXACTE():
    """Un chiffre ecrit a la main perime en silence : on le recalcule.

    Cinq des neuf commentaires `MESURE:` de l'atelier Pdf etaient faux au
    2026-09-02, sans que rien ne l'ait jamais signale.
    """
    ligne = confirmation.RACCOURCIS_EXPORTS_CONFIRMATION
    utf8 = jetons.colonnes(ligne)
    ascii_ = jetons.colonnes(jetons.replier_ascii(ligne))
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert f"MESURE: {utf8}/{ascii_}" in source, (utf8, ascii_)
    # Et elle tient la zone utile dans le regime DANGEREUX -- le repli ASCII
    # est le seul endroit du depot ou une ligne s'ALLONGE.
    assert ascii_ <= jetons.largeur_utile(jetons.LARGEUR_PLANCHER)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_du_cartouche_ne_deborde_de_la_grille(tmp_path, ascii_seul):
    largeur = jetons.LARGEUR_PLANCHER
    lignes = confirmation.panneau_de_la_confirmation(
        master(tmp_path), ascii_seul).rendu(largeur, ascii_seul)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(largeur), (
            ligne)


def test_en_repli_ASCII_tout_ce_que_l_ecran_rend_est_de_l_ASCII_PUR(tmp_path):
    """Un terminal qui ne rend pas `▓` ne rend pas davantage `⏎` ni `×`."""
    fiche = master(tmp_path)
    lignes = [
        *confirmation.panneau_de_la_confirmation(fiche, True).rendu(80, True),
        *[jetons.replier_ascii(ligne)
          for ligne in confirmation.issues_de_la_confirmation(fiche).rendu(True)],
        jetons.replier_ascii(confirmation.mesure_de_la_confirmation(fiche)),
        jetons.replier_ascii(confirmation.RACCOURCIS_EXPORTS_CONFIRMATION),
    ]
    assert all(ligne.isascii() for ligne in lignes), [
        ligne for ligne in lignes if not ligne.isascii()]
    # Un caractere remplace par `?` est PERDU, pas replie : c'est le defaut
    # `1920×1080` -> `1920?1080` que le banc de `E4-2` mesure aussi.
    assert all("?" not in ligne for ligne in lignes), [
        ligne for ligne in lignes if "?" in ligne]


def test_le_module_n_importe_PAS_cli():
    """`EPIC11-ARB-67` : la TUI ne nomme jamais `cli`."""
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert "import cli" not in source
    assert "from ..cli" not in source
    assert " cli." not in source


def test_l_ecran_MONTE_rend_les_trois_zones_de_la_maquette(tmp_path):
    """Le banc headless : l'ecran se monte, et ce qu'il dessine se lit."""
    from conftest import piloter

    fiche = master(tmp_path)
    ecran = confirmation.EcranExportsConfirmation(fiche,
                                                  sur_issue=lambda issue: None)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                   contexte=Contexte())

    async def scenario(pilote):
        # `descendre` est le geste de la coque : l'ecran est le palier du haut,
        # comme dans tous les bancs `E*-3` du depot.
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        etat = jetons.texte_affiche(str(courant.query_one("#etat").content))
        bandeau = jetons.texte_affiche(str(courant.query_one("#bandeau").content))
        raccourcis = jetons.texte_affiche(
            str(courant.query_one("#raccourcis").content))
        return (courant, bandeau, etat, raccourcis,
                courant.lignes_du_panneau(), courant.rendu_des_issues())

    courant, bandeau, etat, raccourcis, panneau, issues = piloter(app, scenario)
    assert courant is ecran
    assert confirmation.bandeau_du_master(fiche) in bandeau
    assert etat == confirmation.mesure_de_la_confirmation(fiche)
    assert raccourcis == confirmation.RACCOURCIS_EXPORTS_CONFIRMATION
    assert len(panneau) == 10
    assert len(issues) == 3


def test_l_ecran_MONTE_rend_son_issue_a_qui_la_lui_demande(tmp_path):
    """`sur_issue` est **requis** (finding `K3`) : un point de jugement qui ne
    sait pas a qui rendre son issue est un cul-de-sac."""
    retenues = []
    ecran = confirmation.EcranExportsConfirmation(
        master(tmp_path), sur_issue=retenues.append)
    assert ecran.traiter("enter") is True
    assert [issue.cle for issue in retenues] == [confirmation.ISSUE_MODIFIER]
    ecran.traiter("up")
    ecran.traiter("enter")
    assert [issue.cle for issue in retenues] == [
        confirmation.ISSUE_MODIFIER, confirmation.ISSUE_ENCODER]
