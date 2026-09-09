# -*- coding: utf-8 -*-
"""Story 11.8, lot E -- `E4-3b`, le master qui existe deja (AC 8).

Ce banc mesure `tui/atelier_exports_versions.py`, et **lui seul** : l'ecran de
confirmation `E4-3` a le sien (`test_atelier_exports_confirmation.py`).

Les quatre regles de mesure heritees, et ce qu'elles commandent ici
-------------------------------------------------------------------
1. **toute fabrique de collection produit au moins deux elements
   distinguables**, et **trois avec la cible au milieu des qu'une boucle
   compte**. Les deux boucles de ce module sont **les issues** (trois, cible
   `Remplacer ce master`, **deuxieme**, celle qui n'est ni la premiere ni la
   derniere, donc la seule qu'un parcours fautif ne peut pas attraper par
   hasard) et **les lignes du cartouche** (huit, aux valeurs toutes
   differentes). :func:`test_le_curseur_pose_AU_MILIEU_se_rend_au_MILIEU` est
   la mesure que la regle exige ;
2. **la position se verifie sur la liste que le code PARCOURT** -- ici
   `choix.issues` et les lignes rendues, jamais l'ordre que la fabrique croit
   ecrire ;
3. **une assertion positive laisse passer toute divergence supplementaire.**
   « `Annuler` est sous le curseur » ne mesure rien ; « l'ensemble des issues
   que le curseur peut viser au montage est **exactement** `{Annuler}` »
   mesure l'invariant ET son unicite. Toutes les mesures d'ensemble de ce banc
   sont a l'egalite ;
4. **une frontiere negative porte toujours son volet symetrique.** Les trois de
   ce banc -- pas d'issue de suppression, pas de recalcul de rang, message
   d'usage retire -- portent chacune la mesure qui prouve que le detecteur
   voit quelque chose.

Ce que ce banc EPINGLE sans le corriger, et pourquoi
-----------------------------------------------------
* **le poids** : la maquette a `1,38 Go` ecrit a la main, le produit rend
  `1,4 Go` -- le format de taille du depot (`explorateur.taille_lisible`), qui
  est le seul. Un quatrieme format de taille pour coller a un dessin serait la
  faute ; la maquette ne se change pas non plus (consigne de lot). L'ecart est
  donc **mesure** par
  :func:`test_le_POIDS_suit_le_format_du_depot_et_l_ecart_a_la_maquette_est_CONSTATE` ;
* **la lecture de `Issue.ecrit`** : cet ecran la lit **litteralement** (« cette
  issue provoque une ecriture »), la ou `atelier_pdf_versions` et
  `atelier_scan_calibrate` la lisent « cette issue **detruit** quelque chose ».
  Les deux lectures posent le curseur ailleurs, et c'est `EPIC11-ARB-188`
  (« Ok sur annuler ») qui tranche celle-ci. L'ecart entre les trois ecrans de
  conflit du produit est **mesure** par
  :func:`test_les_TROIS_ecrans_de_conflit_du_produit_DIVERGENT_sur_la_lecture_de_ecrit`,
  pas tu -- son harmonisation n'appartient pas a ce lot.
"""
from __future__ import annotations

import ast
import datetime
import inspect
import os
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from outils_frontiere import chaines_de_code, identifiants

from mixed_media_utility import encode, project_maintenance
from mixed_media_utility.io import naming, version_ranks
from mixed_media_utility.tui import atelier_exports_versions as versions
from mixed_media_utility.tui import (atelier_pdf_versions,
                                     atelier_scan_calibrate, jetons)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.panneau import Issue

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

SOURCE_DU_PRODUIT = Path(versions.__file__)
PAQUET_TUI = SOURCE_DU_PRODUIT.parent
MAQUETTE = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
            / "ux-tui-2026-08-27" / "maquettes"
            / "E4-3b-exports-master-existe.txt")


# ===========================================================================
# Les fabriques -- aucune ne produit un element unique ni un remplissage
# uniforme, et la cible n'est jamais en premiere position.
# ===========================================================================

PROJET = "projet_demo"
LOT = "plan-04_25"
PROFIL = "prores_hq"
CONTENEUR = "mov"
NOM_PRESENT = "plan-04_25_mmu_prores_hq.mov"
#: Les octets de la maquette, a la virgule pres : `1,38 Go` y est ecrit a la
#: main, le format du depot en rend `1,4 Go`. L'ecart est epingle plus bas.
OCTETS = 1_480_000_000
QUAND = datetime.datetime(2026, 8, 26, 16, 22)
#: **Trois** rangs distincts traversent ce banc : celui du master present
#: (`None`, le rang d'origine), celui que le coeur propose (2), et un troisieme
#: (7) qui prouve que rien n'est derive du premier. Une fabrique a un seul rang
#: rendrait indiscernables « affiche le rang recu » et « affiche 2 ».
RANG_PROPOSE = 2
RANG_TIERS = 7


def fichier_present(dossier: Path, nom: str = NOM_PRESENT,
                    octets: int = OCTETS,
                    quand: datetime.datetime = QUAND) -> Path:
    """Un master sur le DISQUE : c'est de lui que viennent poids et date.

    Le fichier est creux (`truncate`) : le banc mesure une taille declaree par
    le systeme de fichiers, il n'a pas a ecrire un gigaoctet et demi.
    """
    chemin = dossier / nom
    chemin.write_bytes(b"")
    os.truncate(chemin, octets)
    horodate = quand.timestamp()
    os.utime(chemin, (horodate, horodate))
    return chemin


def conflit(dossier: Path, **champs) -> versions.MasterEnConflit:
    """Le conflit de la maquette, sauf mention contraire."""
    chemin = champs.pop("chemin", None) or fichier_present(dossier)
    defauts = dict(lot_id=LOT, profile_id=PROFIL, container=CONTENEUR,
                   rang=None, rang_propose=RANG_PROPOSE,
                   geometrie=(1920, 1080), echantillons=124, cadence="25",
                   duree_s=4.96)
    defauts.update(champs)
    return versions.conflit_du_master(chemin, **defauts)


def ecran(dossier: Path, **champs) -> versions.EcranMasterExistant:
    """L'ecran, avec un `retenir` qui **collecte** -- jamais un `None`."""
    retenues: list[Issue] = []
    monte = versions.EcranMasterExistant(conflit(dossier, **champs),
                                         retenir=retenues.append)
    monte.retenues = retenues                                  # type: ignore[attr-defined]
    return monte


def lignes_de_maquette(*rangs: int) -> list[str]:
    """Les lignes de la maquette, **par leur numero**, cadre retire.

    La maquette est la reference de forme ; ce qui en est lu est toujours
    borne a des lignes nommees, jamais un `in` sur le fichier entier -- une
    appartenance ne dirait pas OU la ligne est tombee.
    """
    brut = MAQUETTE.read_text(encoding="utf-8").splitlines()
    return [brut[rang - 1] for rang in rangs]


def dedans(ligne: str, cadres: int = 1) -> str:
    """Le contenu d'une ligne de maquette, `cadres` bordures retirees.

    **L'indentation de gauche est CONSERVEE** -- un `strip()` la mangerait, et
    c'est elle qui porte le retrait du curseur et celui d'une continuation
    d'avertissement. Seule la colonne de blanc qui suit chaque bordure, posee
    par la grille et non par le contenu, est retiree.
    """
    for _ in range(cadres):
        ligne = ligne.strip()
        assert ligne.startswith("│") and ligne.endswith("│"), ligne
        ligne = ligne[1:-1]
        assert ligne[:1] == " ", ligne
        ligne = ligne[1:]
    return ligne.rstrip()


# ===========================================================================
# Famille 0 -- les fabriques tiennent la regle des collections
# ===========================================================================

def test_la_fabrique_rend_TROIS_issues_TOUTES_DISTINCTES(tmp_path):
    """Une collection de trois, aux libelles et aux cles tous differents.

    Un remplissage uniforme rendrait invisible toute permutation : c'est le
    defaut `M33` de la story 5.6, trouve par mutation et par aucun test.
    """
    issues = versions.issues_du_conflit(conflit(tmp_path))
    assert len(issues) == 3
    assert len({issue.cle for issue in issues}) == 3
    assert len({issue.libelle for issue in issues}) == 3


def test_la_fabrique_rend_HUIT_lignes_de_cartouche_TOUTES_DISTINCTES(tmp_path):
    """Cinq de fiche, une vide, deux d'avertissement -- et aucune repetition.

    La ligne vide est la seule qui se repete... et elle n'apparait qu'une fois.
    """
    lignes = versions.lignes_du_cartouche(conflit(tmp_path), 70)
    assert len(lignes) == 8
    assert len(set(lignes)) == 8


def test_le_curseur_pose_AU_MILIEU_se_rend_au_MILIEU(tmp_path):
    """La regle des fabriques, sur la boucle que le code PARCOURT.

    L'issue visee est la **deuxieme** des trois : ni la premiere, qu'un `find`
    fautif rendrait toujours, ni la derniere, ou le curseur part deja. Le rang
    rendu se compte en LIGNES et non en issues -- deux d'entre elles portent
    une ligne de consequence --, et c'est precisement l'appariement qu'une
    permutation casserait.
    """
    monte = ecran(tmp_path)
    monte.choix.curseur = 1
    lignes, rang = monte.lignes_des_issues()
    # `Créer la v2` + sa consequence, puis `Remplacer ce master` : rang 2.
    assert rang == 2
    assert lignes[rang].strip().startswith(jetons.GLYPHES["curseur"])
    assert versions.LIBELLE_REMPLACER in lignes[rang]
    # Et AUCUNE autre ligne ne porte le curseur -- une mesure d'ensemble.
    porteuses = {position for position, ligne in enumerate(lignes)
                 if jetons.GLYPHES["curseur"] in ligne}
    assert porteuses == {rang}


def test_les_TROIS_rangs_du_banc_sont_DISTINCTS():
    """Le garde-fou de la fabrique elle-meme : sans trois rangs distincts,
    « affiche le rang recu » et « affiche 2 » sont indiscernables."""
    assert len({versions_rang_origine(), RANG_PROPOSE, RANG_TIERS}) == 3


def versions_rang_origine() -> int:
    """Le rang d'origine, **lu du coeur** et jamais retape ici."""
    return version_ranks.RANG_ORIGINE


# ===========================================================================
# Famille 1 -- AC 8.1 : au moins deux issues, jamais un blocage sec
# ===========================================================================

def test_AC_8_1_l_ensemble_des_issues_est_EXACTEMENT_les_trois_de_ARB_188(tmp_path):
    """`EPIC11-ARB-188` : creer la version voisine, remplacer, annuler.

    L'ensemble se mesure **a l'egalite**. « Les trois sont presentes »
    laisserait passer une quatrieme, et c'est exactement la quatrieme --
    la suppression -- que l'arbitrage refuse.
    """
    cles = [issue.cle for issue in versions.issues_du_conflit(conflit(tmp_path))]
    assert cles == [versions.CLE_CREER, versions.CLE_REMPLACER,
                    versions.CLE_ANNULER]


def test_AC_8_1_l_ecrasement_reste_offert_MEME_quand_le_disque_ne_repond_pas(
        tmp_path):
    """`EPIC11-ARB-89` : « toujours permettre une reecriture plutot qu'un
    blocage sec ».

    Le fichier a disparu : ni poids ni date, donc ni avertissement ni ligne de
    consequence. L'**issue**, elle, ne bouge pas -- « un refus qui n'offre
    aucune issue est aussi fautif qu'une destruction silencieuse ».
    """
    absent = conflit(tmp_path, chemin=tmp_path / "jamais_ecrit.mov")
    assert absent.poids is None and absent.quand is None
    cles = [issue.cle for issue in versions.issues_du_conflit(absent)]
    assert cles == [versions.CLE_CREER, versions.CLE_REMPLACER,
                    versions.CLE_ANNULER]
    assert versions.texte_de_l_avertissement(absent) == ""
    assert versions.CLE_REMPLACER not in versions.consequences_des_issues(absent)


def test_AC_8_1_le_choix_exige_DEUX_issues_et_l_invariant_vient_du_PARTAGE(
        tmp_path):
    """La borne d'`EPIC11-ARB-89` n'est pas reecrite ici : elle vit dans
    `ChoixExclusif.__post_init__`, et ce test mesure qu'elle mord."""
    assert len(versions.choix_du_conflit(conflit(tmp_path)).issues) >= 2
    with pytest.raises(ValueError):
        versions.ChoixExclusif([Issue("seule", "Seule issue")])  \
            if hasattr(versions, "ChoixExclusif") else _un_choix_a_une_issue()


def _un_choix_a_une_issue():
    from mixed_media_utility.tui.panneau import ChoixExclusif
    return ChoixExclusif([Issue("seule", "Seule issue")])


# ===========================================================================
# Famille 2 -- AC 8.2 : les issues sont celles que le coeur peut servir,
# et la suppression n'en est PAS une
# ===========================================================================

#: Les mots par lesquels une issue de suppression se nommerait. Le balayage
#: porte sur les **libelles rendus** et sur les chaines de code du module.
MOTS_DE_LA_SUPPRESSION = ("supprim", "effacer ce master", "detruire",
                          "détruire", "retirer ce master")


def test_AC_8_2_AUCUNE_issue_ne_propose_la_SUPPRESSION(tmp_path):
    """Frontiere negative d'`EPIC11-ARB-188` : le menu Projet sert ce geste.

    « Pas de quatrieme issue de suppression » -- une issue qui appellerait un
    chemin que cet ecran ne cable pas serait **inerte**, c'est-a-dire pire
    qu'absente.
    """
    for issue in versions.issues_du_conflit(conflit(tmp_path)):
        replie = issue.libelle.lower()
        for mot in MOTS_DE_LA_SUPPRESSION:
            assert mot not in replie, (issue.cle, mot)


def test_AC_8_2_le_MODULE_ne_nomme_NULLE_PART_un_geste_de_suppression():
    """Le meme balayage, sur les chaines de code -- pas seulement les issues.

    Un libelle propre n'empeche pas une ligne d'etat ou une consequence de
    promettre le geste ailleurs.
    """
    for texte in chaines_de_code(SOURCE_DU_PRODUIT):
        for mot in MOTS_DE_LA_SUPPRESSION:
            assert mot not in texte.lower(), (mot, texte)


def test_AC_8_2_le_VOLET_SYMETRIQUE_le_coeur_SAIT_supprimer():
    """Sans lui, la frontiere negative ci-dessus serait verte sur un depot
    ou la suppression n'existerait pas -- elle ne mesurerait rien.

    Le geste existe, il est **public**, et c'est le menu Projet qui l'appelle.
    """
    assert callable(project_maintenance.remove_project_element)


def test_AC_8_2_la_MAQUETTE_VALIDEE_ne_nomme_pas_davantage_la_suppression():
    """Constat, pas approbation -- et il est remonte plutot que tranche.

    L'AC 8.2 demande de « nommer la suppression sans en faire une issue
    inerte ». `EPIC11-ARB-188` tranche les **trois** issues et renvoie le geste
    au menu Projet ; la maquette validee, elle, ne porte aucune mention. Ce
    test mesure ce que le dessin dit, pour que l'ecart soit **visible** au lieu
    d'etre comble a la main par cet ecran.
    """
    corps = MAQUETTE.read_text(encoding="utf-8").lower()
    assert not any(mot in corps for mot in MOTS_DE_LA_SUPPRESSION), corps


#: Le message RETIRE par `EPIC11-ARB-188`, dans ses deux orthographes. Le
#: dossier le cite verbatim ; il ne doit reparaitre nulle part.
CONSEIL_RETIRE = ("si ce master a déjà été livré", "si ce master a deja ete livre",
                  "ne l'écrasez pas", "ne l'ecrasez pas")


def test_AC_8_2_le_CONSEIL_D_USAGE_retire_par_ARB_188_est_ABSENT_du_module():
    """`EPIC11-ARB-188` + `EPIC11-ARB-56` : l'ecran annonce un FAIT.

    « Si ce master a deja ete livre, ne l'ecrasez pas » est **retire** : l'ecran
    dit ce qui sera detruit et cesse de conseiller un usage qu'il ne peut pas
    connaitre.

    Le balayage porte sur les **chaines de code** -- ce que l'ecran peut
    rendre --, docstrings exclus. Le module CITE le message retire dans sa
    prose, pour dire qu'il l'est : une frontiere qui interdirait aussi de
    nommer ce qu'elle interdit rendrait la regle indocumentable, ce qui est le
    contraire du geste du depot. La mesure de ce qui atteint l'operateur est
    complete quand meme -- rien ne s'affiche qui ne soit une chaine de code.
    """
    for texte in chaines_de_code(SOURCE_DU_PRODUIT):
        for interdit in CONSEIL_RETIRE:
            assert interdit.lower() not in texte.lower(), (interdit, texte)


def test_AC_8_2_le_VOLET_SYMETRIQUE_le_message_retire_est_bien_DETECTABLE():
    """Sans lui, le test precedent serait vert sur un detecteur casse.

    Le dossier d'arbitrage, lui, cite le message : le meme balayage l'y trouve.
    """
    dossier = (_RACINE / "_bmad-output" / "implementation-artifacts"
               / "decisions-2026-09-03-epic11-arb-186-192-notes-planche-exports.md")
    corps = dossier.read_text(encoding="utf-8").lower()
    assert any(interdit.lower() in corps for interdit in CONSEIL_RETIRE), \
        "le detecteur ne voit rien, meme la ou le message EST"


def test_AC_8_2_le_VOLET_SYMETRIQUE_l_avertissement_annonce_bien_LA_DESTRUCTION(
        tmp_path):
    """Sans lui, le test precedent serait vert sur un ecran muet.

    L'avertissement nomme les trois faits que l'arbitrage exige : ce qui sera
    efface, son poids, sa date -- et il **cite l'issue par son verbe**, lu de
    son libelle.
    """
    fiche = conflit(tmp_path)
    texte = versions.texte_de_l_avertissement(fiche)
    assert texte.startswith(versions.verbe_de_l_ecrasement())
    assert versions.verbe_de_l_ecrasement() in versions.LIBELLE_REMPLACER
    assert fiche.poids in texte
    assert fiche.quand_court in texte


def test_AC_8_2_la_LIGNE_D_ETAT_est_un_CONSTAT_sans_touche_ni_conseil(tmp_path):
    """`EPIC11-ARB-56` : trois faits, aucune touche, aucun motif de conception."""
    ligne = versions.ligne_d_etat(conflit(tmp_path))
    assert ligne == dedans(lignes_de_maquette(22)[0]).replace(
        "1,38 Go", "1,4 Go")
    for touche in ("⏎", "Échap", "F1", "↑↓", "Tab"):
        assert touche not in ligne, touche


# ===========================================================================
# Famille 3 -- AC 8.3 : l'avertissement est colorise ENTIEREMENT, et en ORANGE
# ===========================================================================

def test_AC_8_3_TOUTES_les_lignes_de_l_avertissement_portent_l_etat(tmp_path):
    """`EPIC11-ARB-71` : « un avertissement multiligne est un seul objet ».

    L'avertissement de la maquette tient sur **deux** lignes, et la seconde ne
    porte aucun glyphe : la reconnaissance par motif de `jetons.peindre` ne
    verrait que la premiere. L'ecran donne donc l'etat de chacune, et
    l'ensemble des rangs teintes se mesure **a l'egalite**.
    """
    monte = ecran(tmp_path)
    lignes = monte.lignes_du_corps()
    mention = versions.lignes_de_l_avertissement(
        monte.conflit, monte.largeur_du_cartouche())
    assert len(mention) >= 2, mention
    etats = monte.etats_du_cartouche()
    attendus = {0} | {rang for rang in
                      range(len(lignes) - len(mention), len(lignes))}
    assert set(etats) == attendus
    assert set(etats.values()) == {versions.ETAT_DE_L_AVERTISSEMENT}


def test_AC_8_3_l_etat_de_l_avertissement_est_l_ORANGE_du_depot_jamais_LE_VERT():
    """La couleur n'est pas dessinee ici : c'est un NOM de la table de `jetons`.

    La mesure porte sur les deux bouts -- le nom que le module emploie, et la
    couleur que ce nom rend. `state-complete` (le vert) sur une destruction
    dirait exactement le contraire de ce qui va se passer.
    """
    assert versions.ETAT_DE_L_AVERTISSEMENT == "substitute"
    orange = jetons.COULEURS["state-substitute"]
    assert orange != jetons.COULEURS["state-complete"]
    assert orange.lower() == "#f5a623"
    # Et le vert n'est nomme NULLE PART dans le module.
    for texte in chaines_de_code(SOURCE_DU_PRODUIT):
        assert "complete" not in texte, texte


def test_AC_8_3_seule_la_consequence_DESTRUCTRICE_est_teintee(tmp_path):
    """Une mesure d'ensemble a l'egalite, sur les deux tables a la fois.

    `Créer la vN` n'efface rien : sa consequence porte le glyphe **neutre**.
    Teinter les deux ferait de l'avertissement un decor.
    """
    monte = ecran(tmp_path)
    # La table dit le GLYPHE de chaque consequence -- deux glyphes distincts.
    assert versions.GLYPHE_DES_CONSEQUENCES == {
        versions.CLE_CREER: "neutre",
        versions.CLE_REMPLACER: versions.ETAT_DE_L_AVERTISSEMENT}
    # L'etat, lui, ne retient que les noms que `jetons.peindre` accepte : la
    # creation porte son glyphe et n'est PAS teintee.
    etats = monte.etats_des_issues()
    assert set(etats.values()) == {versions.ETAT_DE_L_AVERTISSEMENT}
    assert set(etats.values()) <= set(jetons.NOMS_D_ETAT)
    lignes, _rang = monte.lignes_des_issues()
    assert len(etats) == 1
    teinte = next(iter(etats))
    assert versions.consequences_des_issues(monte.conflit)[
        versions.CLE_REMPLACER] in lignes[teinte]
    # Et la consequence de la creation, elle, porte le glyphe neutre.
    assert jetons.GLYPHES["neutre"] in lignes[teinte - 2]


def test_AC_8_3_une_consequence_qui_DISPARAIT_emporte_son_etat(tmp_path):
    """Un rang teinte qui survivrait a sa ligne peindrait la ligne suivante."""
    monte = ecran(tmp_path, chemin=tmp_path / "jamais_ecrit.mov")
    lignes, _rang = monte.lignes_des_issues()
    etats = monte.etats_des_issues()
    assert etats == {}
    assert all(rang < len(lignes) for rang in etats)
    # Le volet symetrique : avec le fichier, il y a bien un rang teinte, et il
    # est DANS le bloc. Sans lui, `{} == {}` serait vert sur un ecran muet.
    avec = ecran(tmp_path)
    teintes = avec.etats_des_issues()
    assert len(teintes) == 1
    assert all(rang < len(avec.lignes_des_issues()[0]) for rang in teintes)


# ===========================================================================
# Famille 4 -- AC 8.4 : le rang est DONNE par le coeur, jamais recalcule
# ===========================================================================

#: Ce qu'un ecran qui recalculerait un rang nommerait forcement. Le balayage
#: porte sur les **identifiants** du module autant que sur ses chaines.
NOMS_DU_CALCUL_DE_RANG = ("resolve_master_version_rank", "version_ranks",
                          "prochain_rang", "ligne_d_eau",
                          "masters_version_watermark", "VERSION_RANK_MAX",
                          "RANG_ORIGINE")


def test_AC_8_4_le_module_ne_nomme_AUCUNE_fonction_de_calcul_de_rang():
    """Frontiere negative : le rang arrive **deja resolu**.

    « Il ne faut pas rendre le rang » (`EPIC11-ARB-92`) : un ecran qui le
    calculerait pourrait le faire diverger de celui que le coeur a consomme,
    et deux fichiers differents porteraient alors le meme nom.
    """
    vus = identifiants(SOURCE_DU_PRODUIT) | set(chaines_de_code(SOURCE_DU_PRODUIT))
    for nom in NOMS_DU_CALCUL_DE_RANG:
        assert nom not in vus, nom
        # Et rien ne le nomme non plus DEDANS une chaine de code : un
        # `getattr(encode, "resolve_master_version_rank")` passerait sinon.
        for texte in chaines_de_code(SOURCE_DU_PRODUIT):
            assert nom not in texte, (nom, texte)


def test_AC_8_4_le_VOLET_SYMETRIQUE_ces_noms_existent_bien_au_COEUR():
    """Sans lui, la frontiere serait verte sur des noms mal orthographies."""
    assert callable(encode.resolve_master_version_rank)
    assert callable(version_ranks.prochain_rang)
    assert callable(version_ranks.ligne_d_eau)
    assert isinstance(version_ranks.RANG_ORIGINE, int)


@pytest.mark.parametrize("rang_propose", [RANG_PROPOSE, RANG_TIERS, 42])
def test_AC_8_4_le_rang_DONNE_traverse_VERBATIM_jusqu_a_l_ecran(tmp_path,
                                                               rang_propose):
    """Trois rangs distincts : le libelle, le nom propose, la ligne d'etat et
    le bandeau portent **celui qu'on a donne**, jamais un voisin."""
    fiche = conflit(tmp_path, rang_propose=rang_propose)
    assert fiche.rang_propose == rang_propose
    assert versions.libelle_de_la_creation(rang_propose) == \
        versions.issues_du_conflit(fiche)[0].libelle
    assert f"v{rang_propose}" in versions.issues_du_conflit(fiche)[0].libelle
    assert f"_v{rang_propose}." in fiche.nom_propose
    assert str(rang_propose) in versions.ligne_d_etat(fiche)
    assert str(rang_propose) in versions.bandeau_du_conflit(fiche)


def test_AC_8_4_le_NOM_PROPOSE_est_celui_de_io_naming_VERBATIM(tmp_path):
    """La convention de nom a **une** redaction, et ce n'est pas celle-ci."""
    fiche = conflit(tmp_path, rang_propose=RANG_TIERS)
    assert fiche.nom_propose == naming.build_master_filename(
        lot_id=LOT, profile_id=PROFIL, container=CONTENEUR,
        resolution_segment=None, version_rank=RANG_TIERS)


def test_AC_8_4_rang_et_rang_propose_n_ont_AUCUNE_valeur_par_defaut():
    """Un defaut ferait de l'oubli de cablage un **silence**, et un ecran qui
    inventerait un numero de version est le pire mode de panne du versionnage.
    """
    signature = inspect.signature(versions.conflit_du_master)
    for nom in ("rang", "rang_propose"):
        assert signature.parameters[nom].default is inspect.Parameter.empty, nom
    champs = versions.MasterEnConflit.__dataclass_fields__
    import dataclasses
    assert champs["rang_propose"].default is dataclasses.MISSING
    assert champs["rang"].default is dataclasses.MISSING


# ===========================================================================
# Famille 5 -- le curseur : `EPIC11-ARB-188`, « Ok sur annuler »
# ===========================================================================

def test_le_curseur_au_montage_vise_EXACTEMENT_Annuler(tmp_path):
    """`EPIC11-ARB-188`, verbatim d'Egan : « Ok sur annuler ».

    Mesure d'ensemble : « l'ensemble des issues que le curseur peut viser au
    montage est **exactement** `{Annuler}` ». Une assertion positive
    (« `Annuler` est sous le curseur ») laisserait passer un second candidat.
    """
    vises = set()
    for rang_propose in (RANG_PROPOSE, RANG_TIERS):
        for present in (None, tmp_path / "jamais_ecrit.mov"):
            fiche = conflit(tmp_path, rang_propose=rang_propose,
                            **({} if present is None else {"chemin": present}))
            choix = versions.choix_du_conflit(fiche)
            vises.add(choix.issues[choix.curseur].cle)
    assert vises == {versions.CLE_ANNULER}


def test_l_issue_visee_par_le_curseur_est_la_SEULE_qui_n_ecrit_pas(tmp_path):
    """L'invariant n'est pas pose a la main : il est **structurel**.

    `ChoixExclusif.__post_init__` place le curseur sur la premiere issue qui
    n'ecrit pas ; ce module se contente de n'en donner qu'une. La mesure porte
    donc sur l'ensemble des `ecrit`, a l'egalite -- si `Créer la vN` cessait
    d'ecrire, le curseur partirait sur elle sans qu'aucun test ne le dise.
    """
    issues = versions.issues_du_conflit(conflit(tmp_path))
    assert {issue.cle for issue in issues if issue.ecrit} == {
        versions.CLE_CREER, versions.CLE_REMPLACER}
    assert {issue.cle for issue in issues if not issue.ecrit} == {
        versions.CLE_ANNULER}


def test_le_module_n_ASSIGNE_JAMAIS_le_curseur(tmp_path):
    """Frontiere negative : `EPIC11-ARB-7` interdit toute preselection posee.

    Le seul `self.choix.curseur = ...` d'un module d'ecran serait une
    preselection, c'est-a-dire ce que l'arbitrage refuse.
    """
    arbre = ast.parse(SOURCE_DU_PRODUIT.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                assert not (isinstance(cible, ast.Attribute)
                            and cible.attr == "curseur"), ast.dump(cible)


def test_les_TROIS_ecrans_de_conflit_du_produit_DIVERGENT_sur_la_lecture_de_ecrit():
    """L'ecart est MESURE plutot que tu -- la consigne du lot l'exige.

    `atelier_pdf_versions` et `atelier_scan_calibrate` marquent `ecrit=True` la
    **seule** issue destructrice, ce qui pose leur curseur sur l'issue non
    destructrice. Cet ecran-ci le lit litteralement (« provoque une ecriture »),
    ce qui pose le sien sur `Annuler` -- l'invariant qu'`EPIC11-ARB-188`
    demande. Les trois ecrans du produit ne s'accordent donc pas, et
    l'harmonisation n'appartient pas a ce lot.
    """
    # Ici : DEUX issues portent `ecrit=True`, dont la creation, qui ne detruit
    # rien -- c'est la lecture litterale, et elle pose le curseur sur `Annuler`.
    assert _issues_ecrivantes(SOURCE_DU_PRODUIT) == {
        "CLE_CREER": True, "CLE_REMPLACER": True, "CLE_ANNULER": False}
    # Chez eux : la seule issue marquee est la DESTRUCTRICE, et la creation,
    # qui ecrit pourtant un fichier, ne l'est pas.
    ailleurs = _issues_ecrivantes(Path(atelier_pdf_versions.__file__))
    assert ailleurs["CLE_CREER"] is False
    assert ailleurs["CLE_REMPLACER"] is True
    chez_scan = _issues_ecrivantes(Path(atelier_scan_calibrate.__file__))
    assert chez_scan["CLE_NOM_DIFFERENCIE"] is False
    assert chez_scan["CLE_ECRASER"] is True


def _issues_ecrivantes(chemin: Path) -> dict[str, bool]:
    """Pour chaque `Issue(<CLE>, ...)` du module, si elle porte `ecrit=True`.

    Mesure sur l'arbre syntaxique et non au grep : `ici.count("ecrit=True")`
    comptait aussi l'occurrence de la **prose** qui documente le choix, et une
    mesure qui bouge quand on la commente ne mesure pas le code.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    vues: dict[str, bool] = {}
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "Issue" and noeud.args):
            continue
        premier = noeud.args[0]
        if not isinstance(premier, ast.Name):
            continue
        ecrit = any(mot.arg == "ecrit"
                    and isinstance(mot.value, ast.Constant)
                    and mot.value.value is True
                    for mot in noeud.keywords)
        vues[premier.id] = vues.get(premier.id, False) or ecrit
    return vues


# ===========================================================================
# Famille 6 -- la maquette, ligne a ligne
# ===========================================================================

def test_le_CARTOUCHE_reproduit_la_maquette_ligne_a_ligne(tmp_path):
    """La FICHE du cartouche, aux numeros de la maquette (6 a 11).

    Six lignes verbatim, la ligne vide comprise -- elle separe la fiche de
    l'avertissement, et un cartouche qui la perdrait collerait les deux. Le
    seul ecart est le **poids** (`1,38 Go` a la main contre `1,4 Go` du format
    du depot), epingle plus bas plutot que comble ici.

    L'avertissement, lui, est mesure par le test suivant : le poids plus court
    de deux colonnes deplace son point de repli, et comparer des lignes
    **repliees** ferait rougir une mesure de mise en page pour un ecart de
    format de taille.
    """
    largeur = jetons.largeur_de_cartouche(jetons.LARGEUR_PLANCHER)
    rendues = versions.lignes_du_cartouche(conflit(tmp_path), largeur)
    dessinees = [dedans(ligne, cadres=2).replace("1,38 Go", "1,4 Go")
                 for ligne in lignes_de_maquette(6, 7, 8, 9, 10, 11)]
    assert rendues[:6] == dessinees
    assert rendues[5] == ""


def test_l_AVERTISSEMENT_reproduit_le_TEXTE_de_la_maquette(tmp_path):
    """Les deux lignes 12-13, comparees **une fois rejointes**.

    Le point de repli differe de la maquette, et **seulement** parce que
    `1,4 Go` est deux colonnes plus court que le `1,38 Go` dessine a la main :
    `jetons.envelopper` remplit alors une colonne de plus avant de rompre.
    Comparer le texte plutot que les lignes mesure ce qui est dit ; le retrait
    et le repli, eux, sont mesures juste apres.
    """
    largeur = jetons.largeur_de_cartouche(jetons.LARGEUR_PLANCHER)
    rendues = versions.lignes_du_cartouche(conflit(tmp_path), largeur)
    mention = rendues[6:]
    assert len(mention) == 2
    rejointe = " ".join(ligne.strip() for ligne in mention)
    dessinee = " ".join(
        dedans(ligne, cadres=2).strip()
        for ligne in lignes_de_maquette(12, 13)).replace("1,38 Go", "1,4 Go")
    assert rejointe == dessinee
    # Le glyphe ouvre la premiere ligne, et la continuation se cale SOUS lui.
    assert mention[0].startswith(jetons.GLYPHES[versions.ETAT_DE_L_AVERTISSEMENT])
    assert mention[1].startswith(versions.INDENT_SOUS_LE_GLYPHE)
    assert not mention[1].startswith(versions.INDENT_SOUS_LE_GLYPHE + " ")
    assert len(versions.INDENT_SOUS_LE_GLYPHE) == len(
        f"{jetons.GLYPHES[versions.ETAT_DE_L_AVERTISSEMENT]} ")


def test_le_TITRE_du_cartouche_nomme_un_FAIT_verbatim_de_la_maquette(tmp_path):
    """`DESIGN.md` §9 : un cartouche nomme un fait, jamais un echec."""
    assert versions.TITRE_DU_CONFLIT == "Ce master existe déjà"
    assert versions.TITRE_DU_CONFLIT in lignes_de_maquette(5)[0]
    assert ecran(tmp_path).titre_du_cartouche() == versions.TITRE_DU_CONFLIT


def test_le_BLOC_DES_ISSUES_reproduit_la_maquette_ligne_a_ligne(tmp_path):
    """Cinq lignes : trois issues et deux consequences, dans l'ordre du dessin."""
    lignes, rang = ecran(tmp_path).lignes_des_issues()
    dessinees = [dedans(ligne).replace("1,38 Go", "1,4 Go")
                 for ligne in lignes_de_maquette(16, 17, 18, 19, 20)]
    assert lignes == dessinees
    assert rang == 4


def test_le_BANDEAU_reproduit_la_DROITE_de_la_maquette(tmp_path):
    assert versions.bandeau_du_conflit(conflit(tmp_path)) == "master présent · rang 2 libre"
    assert versions.bandeau_du_conflit(conflit(tmp_path)) in lignes_de_maquette(2)[0]


def test_la_ligne_de_RACCOURCIS_est_verbatim_celle_de_la_maquette():
    assert versions.RACCOURCIS_DU_CONFLIT == dedans(lignes_de_maquette(23)[0])
    assert versions.EcranMasterExistant.raccourcis == versions.RACCOURCIS_DU_CONFLIT


def test_les_raccourcis_sont_un_ATTRIBUT_DE_CLASSE_jamais_une_propriete():
    """`test_repli_ascii.py` lit `classe.raccourcis` **au niveau de la classe** :
    une `@property` y rendrait un objet `property`, et la garde d'epic serait
    verte sans avoir rien lu."""
    brut = vars(versions.EcranMasterExistant)["raccourcis"]
    assert isinstance(brut, str)


def test_le_POIDS_suit_le_format_du_depot_et_l_ecart_a_la_maquette_est_CONSTATE(
        tmp_path):
    """L'ecart est EPINGLE, ni comble ni tu (consigne du lot).

    La maquette porte `1,38 Go`, ecrit a la main. Le depot n'a **qu'un** format
    de taille, celui de l'explorateur, et il rend `1,4 Go`. En inventer un
    quatrieme pour coller a un dessin serait la faute ; changer la maquette est
    interdit par la consigne du lot.
    """
    from mixed_media_utility.tui.explorateur import taille_lisible
    fiche = conflit(tmp_path)
    assert fiche.poids == taille_lisible(OCTETS)
    assert fiche.poids == "1,4 Go"
    assert "1,38 Go" in MAQUETTE.read_text(encoding="utf-8")


# ===========================================================================
# Famille 7 -- la grille, les deux regimes, les frontieres de paquet
# ===========================================================================

def test_la_MESURE_declaree_de_la_ligne_de_raccourcis_est_EXACTE():
    """Un chiffre ecrit a la main perime en silence : on le recalcule."""
    ligne = versions.RACCOURCIS_DU_CONFLIT
    utf8 = jetons.colonnes(ligne)
    ascii_ = jetons.colonnes(jetons.replier_ascii(ligne))
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert f"MESURE: {utf8}/{ascii_}" in source, (utf8, ascii_)
    assert ascii_ <= jetons.largeur_utile(jetons.LARGEUR_PLANCHER)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_du_cartouche_ne_deborde_de_la_grille(tmp_path, ascii_seul):
    largeur = jetons.LARGEUR_PLANCHER
    cartouche = jetons.largeur_de_cartouche(largeur)
    for ligne in versions.lignes_du_cartouche(conflit(tmp_path), cartouche,
                                              ascii_seul):
        assert jetons.colonnes(ligne) <= cartouche, ligne


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_d_issue_ni_d_etat_ne_deborde_de_la_zone_utile(tmp_path,
                                                                    ascii_seul):
    monte = ecran(tmp_path)
    utile = jetons.largeur_utile(jetons.LARGEUR_PLANCHER)
    lignes, _rang = monte.lignes_des_issues(ascii_seul)
    for ligne in lignes + [monte.etat(ascii_seul)]:
        assert jetons.colonnes(ligne) <= utile, ligne


def test_en_repli_ASCII_tout_ce_que_l_ecran_rend_est_de_l_ASCII_PUR(tmp_path):
    """Un terminal qui ne rend pas `▲` ne rend pas davantage `⏎` ni `×`.

    Le `?` est traque autant que le non-ASCII : `replier_ascii` remplace ce
    qu'aucune table ne connait, et un caractere remplace est **perdu**. C'est
    le defaut `1920×1080` -> `1920?1080`, et cet ecran porte ce `×`.
    """
    monte = ecran(tmp_path)
    largeur = jetons.largeur_de_cartouche(jetons.LARGEUR_PLANCHER)
    lignes = [
        *versions.lignes_du_cartouche(monte.conflit, largeur, True),
        *monte.lignes_des_issues(True)[0],
        monte.etat(True),
        monte.titre_du_cartouche(True),
        jetons.replier_ascii(versions.RACCOURCIS_DU_CONFLIT),
        jetons.replier_ascii(versions.bandeau_du_conflit(monte.conflit)),
    ]
    assert all(ligne.isascii() for ligne in lignes), [
        ligne for ligne in lignes if not ligne.isascii()]
    assert all("?" not in ligne for ligne in lignes), [
        ligne for ligne in lignes if "?" in ligne]


def test_tous_les_GLYPHES_employes_sont_dans_une_table_FERMEE():
    """Le signalement 1 du lot D : `▾` ne vivait dans aucune table et
    `replier_ascii` en rendait `?`. Cet ecran porte `▲`, `▸`, `·` et `×` --
    ce test mesure que chacun a son repli."""
    connus = set(jetons.GLYPHES.values()) | set(jetons.REPLIS_DE_TEXTE)
    for glyphe in ("▲", "▸", "·", "×"):
        assert glyphe in connus, glyphe
        assert jetons.replier_ascii(glyphe).isascii()
        assert jetons.replier_ascii(glyphe) != "?", glyphe


def test_le_module_n_importe_PAS_cli():
    """`EPIC11-ARB-67` : la TUI ne nomme jamais `cli`."""
    source = SOURCE_DU_PRODUIT.read_text(encoding="utf-8")
    assert "import cli" not in source
    assert "from ..cli" not in source
    assert " cli." not in source


# ===========================================================================
# Famille 8 -- l'ecran monte
# ===========================================================================

def test_l_ecran_MONTE_rend_son_cartouche_ses_issues_et_sa_mesure(tmp_path,
                                                                  banc):
    """Le banc headless : l'ecran se monte, et ce qu'il dessine se lit."""
    monte = ecran(tmp_path)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), monte],
                   contexte=Contexte(projet=PROJET))

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        return (courant,
                jetons.texte_affiche(str(courant.query_one("#etat").content)),
                jetons.texte_affiche(str(courant.query_one("#bandeau").content)),
                jetons.texte_affiche(
                    str(courant.query_one("#raccourcis").content)),
                jetons.texte_affiche(str(courant.query_one(
                    f"#{versions.EcranMasterExistant.ID_DU_CARTOUCHE}").content)),
                jetons.texte_affiche(str(courant.query_one(
                    f"#{versions.EcranMasterExistant.ID_DES_ISSUES}").content)))

    courant, etat, bandeau, raccourcis, cartouche, issues = banc(app, scenario)
    assert courant is monte
    assert etat == versions.ligne_d_etat(monte.conflit)
    assert versions.bandeau_du_conflit(monte.conflit) in bandeau
    assert raccourcis == versions.RACCOURCIS_DU_CONFLIT
    assert versions.TITRE_DU_CONFLIT in courant._corps.border_title
    assert monte.conflit.nom in cartouche
    for issue in versions.issues_du_conflit(monte.conflit):
        assert issue.libelle in issues


def test_l_ecran_MONTE_rend_son_issue_a_qui_la_lui_demande(tmp_path):
    """`retenir` est **requis** (finding `K3`) : un point de jugement qui ne
    sait pas a qui rendre son issue est un cul-de-sac.

    Trois validations, trois issues distinctes, et la troisieme est prise au
    **milieu** -- ni la premiere de la liste ni celle ou le curseur part.
    """
    monte = ecran(tmp_path)
    assert monte.traiter("enter") is True
    monte.traiter("up")
    assert monte.traiter("enter") is True
    monte.traiter("up")
    assert monte.traiter("enter") is True
    assert [issue.cle for issue in monte.retenues] == [
        versions.CLE_ANNULER, versions.CLE_REMPLACER, versions.CLE_CREER]


def test_retenir_est_un_parametre_REQUIS_sans_valeur_par_defaut():
    """Un rappel optionnel qui n'est pas cable est un cul-de-sac muet, et il
    faudrait alors l'inscrire a `OPTIONNELS_ASSUMES`. Il est requis."""
    signature = inspect.signature(versions.EcranMasterExistant.__init__)
    assert signature.parameters["retenir"].default is inspect.Parameter.empty
    assert signature.parameters["retenir"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        versions.EcranMasterExistant(object())            # type: ignore[call-arg]


def test_AUCUNE_lettre_n_est_un_raccourci_de_cet_ecran(tmp_path):
    """`EPIC11-ARB-45` / `-126` : fleche seule hors des listes a cocher.

    La frappe imprimable est **consommee** : la ligne de raccourcis n'annonce
    aucune sortie par lettre, et laisser remonter un `q` fermerait
    l'application sur une touche que rien n'annonce.
    """
    monte = ecran(tmp_path)
    depart = monte.choix.curseur
    for lettre in ("q", "e", "r", "a", "V"):
        assert monte.traiter(lettre, lettre) is True
        assert monte.choix.curseur == depart, lettre
    assert monte.retenues == []
    assert monte.traiter("f5") is False
