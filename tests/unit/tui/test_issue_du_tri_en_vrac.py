# -*- coding: utf-8 -*-
"""`EPIC11-ARB-266`, moitie TUI : le refus de pile mixte porte une TROISIEME issue.

Retour d'Egan du 2026-09-07, verbatim : « moi c'est la TUI qui m'interesse :
pas de refus sec sans issue ». Le refus n'etait pas sec -- `E3-9` en offrait
deux --, mais elles ne repondaient pas a CE refus : renommer l'etiquette ne
change rien a une pile qui porte des planches, et le message renvoyait vers une
commande de terminal. L'operateur au clavier lisait donc une sortie qu'il ne
pouvait pas prendre, ce qui est le meme defaut qu'une impasse.

**Aucun parcours neuf n'est ecrit, et c'est ce qui rend l'issue bon marche.**
Le tri en vrac de la story 5.24 est deja le regime PAR DEFAUT de
`ParcoursScan.detecter` : `DemandeDeDetection` laisse `ingest_slug` a `None`,
ce qui declenche le tri par QR (`EPIC5-ARB-106`). L'issue ne fait que rendre au
scan la pile que la calibration vient de refuser.

REGLE DES DRAPEAUX. Le **motif** varie dans les deux sens, sur les cinq motifs
que la table publie : la troisieme issue doit apparaitre sur un seul et sur
aucun autre. Une garde qui ne jouerait que le motif de la pile mixte
mesurerait la moitie du produit -- c'est exactement la famille de defaut posee
dans `CLAUDE.md` le 2026-09-06. `ascii_seul` varie aussi.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate
from mixed_media_utility.tui import atelier_scan_calibrate as cal
from mixed_media_utility.tui import atelier_scan_parcours as parc
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

class _Source:
    """Une source designee **minimale**, au seul contrat que l'issue lit."""

    def __init__(self, chemin):
        self.chemin = chemin


def _formulaire(chemin, dpi: str = "300"):
    formulaire = cal.FormulaireDeCalibration()
    formulaire.scan = _Source(chemin)
    formulaire.dpi = dpi
    return formulaire


class _Passe:
    """Une passe REFUSEE, au seul contrat que l'ecran de refus lit."""

    def __init__(self, motif: str):
        self.refus = scan_calibrate.RefusDeCalibration("pile mixte", motif=motif)
        self.motif = motif


class _ParcoursSansEcran(parc.ParcoursScan):
    """Le parcours, avec `detecter` INTERCEPTE et la pile d'ecrans neutralisee.

    Ce banc mesure **l'aiguillage**, pas le montage d'un ecran de detection :
    monter la detection demanderait un raster reel, et le defaut mesure ici est
    en amont -- l'issue rend-elle la pile au scan, avec la bonne source et le
    bon dpi ?
    """

    def __init__(self, app, projet):
        super().__init__(app, projet)
        self.detections: list[tuple] = []
        self.remontees = 0

    def detecter(self, source, dpi: int):
        self.detections.append((source, dpi))
        return None


def _parcours(tmp_path, monkeypatch):
    app = CoqueTui([PalierTemoin("Ateliers", "Q quitter")],
                   Contexte(projet="projet_demo", palier="Scan"))
    parcours = _ParcoursSansEcran(app, tmp_path / "projet")
    def compter_la_remontee(_app):
        parcours.remontees += 1

    monkeypatch.setattr(
        parc.atelier_scan_resultat, "remonter_a_l_ouverture_de_l_atelier",
        compter_la_remontee)
    return parcours


# ---------------------------------------------------------------------------
# Les issues offertes -- le MOTIF varie dans les deux sens
# ---------------------------------------------------------------------------

def test_la_TROISIEME_issue_n_apparait_que_sur_la_pile_mixte():
    """Un motif la porte, les quatre autres non. **Balayage EXHAUSTIF.**

    Ecrit comme un balayage de la table publiee et non comme deux exemples :
    un motif ajoute demain a `MOTIFS_DE_REFUS_DE_CALIBRATION` entre
    automatiquement dans la mesure, et personne n'a a penser a l'y mettre.
    """
    portent = {motif for motif in scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION
               if cal.CLE_TRIER_EN_VRAC in
               [issue.cle for issue in cal.issues_de_l_impasse(motif)]}

    assert portent == {scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION}, portent
    assert len(scan_calibrate.MOTIFS_DE_REFUS_DE_CALIBRATION) >= 5, (
        "temoin de cardinal : la table ne s'est pas videe sous la mesure")


def test_SANS_motif_les_deux_issues_d_avant_et_rien_de_plus():
    """Le defaut ne fabrique jamais la troisieme issue par accident."""
    assert [issue.cle for issue in cal.issues_de_l_impasse()] == [
        cal.CLE_RENOMMER, cal.CLE_ABANDONNER]


def test_AUCUNE_des_trois_issues_n_ecrit():
    """`EPIC11-ARB-7` : une issue qui ecrit doit l'avoir dit.

    Trier relance une passe qui n'a encore rien pose sur le disque -- le refus
    est tombe AVANT toute ecriture. Marquer cette issue `ecrit=True` ferait
    lire un avertissement pour une passe qui ne detruit rien.
    """
    issues = cal.issues_de_l_impasse(
        scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION)
    assert [issue.cle for issue in issues if issue.ecrit] == []


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_de_refus_PORTE_la_troisieme_issue(ascii_seul):
    """Le motif voyage jusqu'a l'ecran, pas seulement jusqu'a la fonction.

    Sans ce test, `choix_de_l_impasse(passe.motif)` pourrait redevenir
    `choix_de_l_impasse()` sans qu'aucune mesure ne bouge : les trois tests du
    dessus resteraient verts, puisqu'ils appellent la fonction directement.
    """
    ecran = cal.EcranRefusDeCalibration(
        _Passe(scan_calibrate.REFUS_PILE_MIXTE_EN_CALIBRATION),
        retenir=lambda _issue: None)

    assert cal.CLE_TRIER_EN_VRAC in [issue.cle for issue in ecran.choix.issues]

    autre = cal.EcranRefusDeCalibration(
        _Passe(scan_calibrate.REFUS_PAGE_INEXPLOITABLE),
        retenir=lambda _issue: None)
    assert cal.CLE_TRIER_EN_VRAC not in [
        issue.cle for issue in autre.choix.issues]


# ---------------------------------------------------------------------------
# L'aiguillage
# ---------------------------------------------------------------------------

def test_l_issue_REND_LA_PILE_au_scan_avec_sa_source_et_son_dpi(tmp_path,
                                                                monkeypatch):
    """Le coeur de l'issue : la meme pile, le meme dpi, sans lot impose.

    Le dpi arrive en CHAINE du formulaire et doit ressortir en ENTIER : c'est
    `dpi_valide` qui porte la regle, et la lire plutot que la reecrire est ce
    qui garantit que les deux chemins voient le meme nombre.
    """
    parcours = _parcours(tmp_path, monkeypatch)
    pile = tmp_path / "pile_melangee"
    parcours._formulaire_de_la_passe = _formulaire(pile, "600")

    parcours.sortir_du_refus(
        type("I", (), {"cle": cal.CLE_TRIER_EN_VRAC})())

    assert parcours.detections == [(pile, 600)], parcours.detections
    assert parcours.remontees == 0, (
        "l'issue a remonte au menu au lieu de trier : elle ne fait pas ce "
        "qu'elle annonce")


@pytest.mark.parametrize("formulaire_pose,cas", [
    pytest.param(None, "aucune-passe", id="sans-formulaire"),
    pytest.param("sans-scan", "scan-absent", id="sans-scan"),
    pytest.param("dpi-vide", "dpi-illisible", id="dpi-vide"),
    pytest.param("dpi-mauvais", "dpi-illisible", id="dpi-non-numerique"),
])
def test_l_issue_REMONTE_AU_MENU_plutot_que_de_tomber(tmp_path, monkeypatch,
                                                      formulaire_pose, cas):
    """Les quatre etats ou la pile ne peut pas etre rendue.

    Aucun n'est atteignable aujourd'hui -- `peut_calibrer` interdit de lancer
    une passe sans scan ni dpi valide --, et c'est precisement pourquoi ils se
    mesurent : une garde ecrite pour un regime qu'aucun test ne joue est une
    garde dont personne ne sait si elle marche, et celle-ci tient une
    application qui tomberait sur le geste de sortie d'une impasse.
    """
    parcours = _parcours(tmp_path, monkeypatch)
    if formulaire_pose == "sans-scan":
        parcours._formulaire_de_la_passe = cal.FormulaireDeCalibration()
    elif formulaire_pose == "dpi-vide":
        parcours._formulaire_de_la_passe = _formulaire(tmp_path / "p", "")
    elif formulaire_pose == "dpi-mauvais":
        parcours._formulaire_de_la_passe = _formulaire(tmp_path / "p", "trois")

    parcours.sortir_du_refus(
        type("I", (), {"cle": cal.CLE_TRIER_EN_VRAC})())

    assert parcours.detections == [], cas
    assert parcours.remontees == 1, cas


def test_les_DEUX_AUTRES_issues_ne_declenchent_AUCUN_tri(tmp_path, monkeypatch):
    """Frontiere negative : l'aiguillage ne mord que sur SA cle.

    Un `if` qui tomberait dans la mauvaise branche renverrait au tri un
    operateur qui a demande a renommer son etiquette -- c'est-a-dire une passe
    entiere relancee sur un geste qui ne la demandait pas.
    """
    for cle in (cal.CLE_RENOMMER, cal.CLE_ABANDONNER):
        parcours = _parcours(tmp_path, monkeypatch)
        parcours._formulaire_de_la_passe = _formulaire(tmp_path / "pile")
        parcours.sortir_du_refus(type("I", (), {"cle": cle})())
        assert parcours.detections == [], cle


def test_le_parcours_RETIENT_le_formulaire_de_sa_passe(tmp_path, monkeypatch):
    """Frontiere negative, et elle tient tout le reste.

    `PasseDeCalibration` ne porte pas la source -- elle porte ce que la passe a
    PRODUIT. Si `lancer_la_passe_de_calibration` cessait de retenir le
    formulaire, l'issue remonterait au menu **en silence** : tous les tests
    d'issues ci-dessus resteraient verts, puisqu'ils posent le formulaire a la
    main. Celui-ci mesure le seul endroit qui le pose en production.
    """
    import inspect
    corps = inspect.getsource(parc.ParcoursScan.lancer_la_passe_de_calibration)
    assert "_formulaire_de_la_passe = formulaire" in corps, (
        "le parcours ne retient plus le formulaire de sa passe : l'issue de "
        "tri remontera au menu sans rien trier")


def test_le_tri_en_vrac_est_le_DEFAUT_de_detecter():
    """Ce sur quoi l'issue REPOSE, mesure plutot que suppose.

    L'issue ne trie pas elle-meme : elle appelle `detecter`, dont le tri par QR
    est le regime par defaut parce que `DemandeDeDetection.ingest_slug` vaut
    `None`. Le jour ou ce defaut changerait, l'issue enverrait la pile dans un
    lot unique -- c'est-a-dire exactement le regime que le refus interdit --
    et aucun autre test ne le verrait.
    """
    import inspect
    corps = inspect.getsource(parc.ParcoursScan.detecter)
    assert "ingest_slug" not in corps, (
        "`detecter` pose desormais un slug : le tri par QR n'est plus son "
        "regime par defaut, et l'issue de tri ne trie plus")
    champs = parc.DemandeDeDetection.__dataclass_fields__
    assert champs["ingest_slug"].default is None
