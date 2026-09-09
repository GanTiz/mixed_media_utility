# -*- coding: utf-8 -*-
"""Couche 3 : ce que l'operateur LIT apres la suppression d'un groupe.

`EPIC11-ARB-264`, option (A) retenue par Egan le 2026-09-07, verbatim : « Au
mieux, avec un compte rendu ligne par ligne. Le projet peut rester a moitie
supprime, et il faut relancer en sachant ce qui reste. » Et la decision ajoute
ce qu'elle entraine : « le refus de chaque ligne se prononce
(`EPIC11-ARB-258`) et il porte la raison reelle ».

Ces bancs ne mesurent pas le coeur -- `remove_project_group` porte bien ses
refus, ligne par ligne, avec leur phrase verbatim. Ils mesurent la SORTIE : ce
qui atteint l'oeil.

Le refus joue ici est REEL, jamais un double : un second lot declare le meme
master, et le coeur refuse l'annexe partagee. Un double de banc mesurerait le
banc.

`reprendre` est neutralise dans tous les cas -- c'est `C3-1`, un autre finding,
et le laisser jouer ferait echouer ces bancs-ci pour une raison qui n'est pas
la leur.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import project_layout
from mixed_media_utility.tui import projet_inventaire as pi
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

M1 = "outputs/plan-04_12p5_mmu_prores_hq.mov"
M2 = "outputs/plan-04_12p5_mmu_dnxhr_hqx.mov"
#: Un master RENOMME a la main : son nom ne nomme aucun profil du registre,
#: donc `cible_du_noeud` ne sait pas le viser.
M3 = "outputs/plan-04_12p5_mmu_renomme_a_la_main.mov"


@pytest.fixture(autouse=True)
def _sans_relecture_d_arbre(monkeypatch):
    """`C3-1` neutralise : ces bancs mesurent le compte rendu, pas le cablage."""
    monkeypatch.setattr(pi.EcranInventaireDuProjet, "reprendre",
                        lambda self: None)


def _projet(tmp_path: Path, *, partage=False, renomme=False) -> Path:
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}, {"rush_id": "plan-09"}]
    masters = [{"path": M1, "profile_id": "prores_hq"},
               {"path": M2, "profile_id": "dnxhr_hqx"}]
    if renomme:
        # Au MILIEU : un balayage qui sauterait la premiere ou la derniere
        # entree ne se demasquerait pas autrement.
        masters.insert(1, {"path": M3, "profile_id": "prores_hq"})
    lots = [{"lot_id": "plan-04_12p5", "rush_id": "plan-04",
             "frames_dir": "extract-frames/plan-04_12p5",
             "encoded_masters": masters}]
    if partage:
        # Le MEME master declare par un second lot : le coeur refuse de
        # supprimer une annexe partagee, et c'est un refus de terrain.
        lots.append({"lot_id": "plan-09_25", "rush_id": "plan-09",
                     "frames_dir": "extract-frames/plan-09_25",
                     "encoded_masters": [{"path": M2,
                                          "profile_id": "dnxhr_hqx"}]})
    document["lots"] = lots
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for relatif, octets in [(M1, 4004), (M2, 5005), (M3, 6006),
                            ("extract-frames/plan-04_12p5/f0.tiff", 101),
                            ("extract-frames/plan-09_25/f0.tiff", 55)]:
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _supprimer_le_groupe(banc, chemin: Path, fragment: str):
    """Le parcours clavier complet ; rend `(confirmation, compte rendu)`."""
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin)
        await pilote.pause()
        inventaire = pilote.app.screen
        for _ in range(6):
            for _ in range(40):
                inventaire.traiter("up")
            for _ in range(len(inventaire.arbre.lignes_visibles())):
                inventaire.traiter("right")
                inventaire.traiter("down")
        for _ in range(60):
            inventaire.traiter("up")
        noms = [n.nom for n in inventaire.arbre.lignes_visibles()]
        rangs = [r for r, nom in enumerate(noms) if fragment in nom]
        assert rangs, (fragment, noms)
        for _ in range(rangs[0]):
            inventaire.traiter("down")
        inventaire.traiter("space", " ")
        inventaire.traiter("delete")
        await pilote.pause()
        confirmation = pilote.app.screen
        assert isinstance(confirmation, ps.EcranSuppressionConfirmation), \
            type(confirmation).__name__
        lu_avant = confirmation.lignes_du_panneau()
        issues = [issue.cle for issue in confirmation.choix.issues]
        rang = issues.index(ps.CLE_SUPPRIMER)
        while confirmation.choix.curseur != rang:
            confirmation.traiter(
                "down" if confirmation.choix.curseur < rang else "up")
        confirmation.traiter("enter")
        # **On attend la CONDITION, jamais un nombre de tours de boucle.**
        # L'ecriture part dans un fil (`E6-2c` se monte pendant), et un compte
        # fixe de `pause()` mesure la vitesse du conteneur plutot que le
        # produit : a six tours, le groupe entierement refuse -- qui n'ecrit
        # rien -- etait conclu, et le groupe a MOITIE refuse -- qui detruit un
        # fichier pour de vrai -- ne l'etait pas encore, si bien que le banc
        # lisait `E6-2c` et accusait le compte rendu de taire ce qu'il n'avait
        # pas encore eu a dire. La borne reste, elle : sans elle, un compte
        # rendu qui ne viendrait jamais suspendrait le banc au lieu de le faire
        # rougir.
        for _ in range(200):
            if not isinstance(pilote.app.screen, ps.EcranSuppressionEnCours):
                break
            await pilote.pause()
        final = pilote.app.screen
        assert not isinstance(final, ps.EcranSuppressionEnCours), \
            "l'ecriture n'a pas rendu la main : aucun compte rendu a lire"
        return {"plan": confirmation.plan, "avant": lu_avant,
                "issues": issues, "final": type(final).__name__,
                "lu": final.lignes()}

    return banc(app, tour)


# ---------------------------------------------------------------------------
# `C3-2` -- le POURQUOI de chaque refus n'atteint jamais l'oeil.
# ---------------------------------------------------------------------------


def test_C3_2_un_groupe_a_MOITIE_refuse_ne_s_annonce_pas_REUSSI(tmp_path, banc):
    """ROUGE A DESSEIN. Deux masters, un refus reel, un fichier reste.

    Le coeur a raison de refuser et il dit pourquoi. Ce que le produit montre :
    « Supprimés 1 fichier », « Manifeste à jour · l'entrée est retirée » -- le
    compte rendu de la REUSSITE, pas un mot du refus ni de sa raison, alors
    qu'un master sur deux occupe toujours le disque et reste declare.
    """
    chemin = _projet(tmp_path, partage=True)
    vu = _supprimer_le_groupe(banc, chemin, "masters —")

    reste = chemin / M2
    assert reste.is_file(), "le banc doit mesurer un groupe A MOITIE parti"
    refusees = vu["plan"].apercu_du_groupe.refusees
    assert refusees, "le coeur doit avoir refuse une ligne"
    raison = refusees[0].refus
    texte = "\n".join(vu["lu"])
    assert vu["final"] != "EcranReussiteDeSuppression", (
        "un groupe dont une ligne a refuse s'annonce REUSSI : " + texte)
    assert Path(M2).name in texte, (
        "le compte rendu ne NOMME pas ce qui reste : " + texte)
    assert raison.split(".")[0] in texte, (
        "le compte rendu ne dit pas POURQUOI la ligne a refuse ; la raison du "
        f"coeur etait : {raison!r}")


def test_C3_2b_un_groupe_ENTIEREMENT_refuse_ne_s_annonce_pas_REUSSI(
        tmp_path, banc):
    """ROUGE A DESSEIN. Le meme defaut a son bord : plus rien ne part.

    L'autre bord du meme drapeau -- un refus sur UNE ligne, un refus sur
    TOUTES. Sans ce volet, une correction qui ne traiterait que le cas partiel
    passerait pour complete.
    """
    chemin = _projet(tmp_path)
    # Les deux masters de ce lot sont aussi declares par un second lot : les
    # deux lignes refusent donc, et le groupe ne perd rien.
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["lots"].append({
        "lot_id": "plan-09_25", "rush_id": "plan-09",
        "frames_dir": "extract-frames/plan-09_25",
        "encoded_masters": [{"path": M1, "profile_id": "prores_hq"},
                            {"path": M2, "profile_id": "dnxhr_hqx"}]})
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")

    vu = _supprimer_le_groupe(banc, chemin, "masters —")

    assert (chemin / M1).is_file() and (chemin / M2).is_file()
    texte = "\n".join(vu["lu"])
    assert vu["final"] != "EcranReussiteDeSuppression", (
        "aucune ligne n'est partie et l'ecran annonce la reussite : " + texte)


# ---------------------------------------------------------------------------
# `C3-3` -- un membre que rien ne sait viser part du groupe SANS UN MOT.
# ---------------------------------------------------------------------------


def test_C3_3_un_membre_NON_VISABLE_est_NOMME_et_pas_seulement_decompte(
        tmp_path, banc):
    """ROUGE A DESSEIN. Trois masters, un renomme a la main.

    `cibles_du_groupe` rend bien le nom du membre qu'elle ne sait pas viser --
    son propre docstring dit « son nom part dans la seconde moitie, et
    l'appelant le DIT (`EPIC11-ARB-258`). Le taire ferait supprimer "le
    groupe" en en laissant une partie, sans un mot. » L'appelant ne le dit que
    lorsqu'AUCUN membre n'est visable ; sur un groupe a moitie visable, le seul
    indice est l'ecart entre « les 2 elements » et « masters — 3 masters ».
    """
    chemin = _projet(tmp_path, renomme=True)
    vu = _supprimer_le_groupe(banc, chemin, "masters —")

    assert len(vu["plan"].cibles_du_groupe) == 2, vu["plan"].cibles_du_groupe
    assert (chemin / M3).is_file(), "le membre non visable doit rester"
    lu = "\n".join(vu["avant"]) + "\n" + "\n".join(vu["lu"])
    assert Path(M3).name in lu, (
        "ni la confirmation ni le compte rendu ne NOMMENT le membre laisse "
        "de cote : " + lu)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-265` -- le groupe des SCANS : le consentement ORDINAIRE suffit.
# ---------------------------------------------------------------------------


def test_ARB265_le_groupe_des_SCANS_part_sous_le_consentement_ORDINAIRE(
        tmp_path, banc):
    """La frontiere d'`EPIC11-ARB-265`, tranche par Egan le 2026-09-07.

    **Ce test a change de sens, pas de mesure.** Sa premiere redaction -- celle
    de la couche 3 de la revue, sous le nom `C3-4` -- etait ROUGE A DESSEIN :
    elle exigeait `CLE_SUPPRIMER_AVEC_SCANS` parmi les issues, parce
    qu'`EPIC11-ARB-264` declarait le point NON tranche, verbatim : « elle ne
    dit rien du GROUPE DES SCANS. Un scan porte son propre consentement
    (`EPIC11-ARB-90`) parce qu'il coute un passage au scanner a refaire ;
    empiler N suppressions de scans sous un seul geste de groupe est une
    question de consentement [...] et elle n'a pas ete posee. »

    **Elle a ete posee, et tranchee** : le consentement ordinaire suffit. Ce
    banc tient donc desormais la decision au lieu de reclamer la question, et
    son assertion est retournee -- l'issue propre aux scans ne doit **PAS**
    apparaitre. Une issue offerte ici serait un mensonge doublement mesure :
    `rapport_agrege_du_groupe` force `scan_inclus=False` et les cinq cibles
    fines rendent `dossiers_de_scan=()`, donc `executer_la_suppression`
    l'ignorerait -- c'est-a-dire « un drapeau sans effet », ce que ce module
    refuse par ailleurs.

    La mesure du parcours, elle, est **inchangee** : les deux dossiers de scan
    partent sous l'issue « Supprimer » ordinaire. C'est le meme fait ; seule
    sa lecture a change de statut, de defaut a decision.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}]
    document["lots"] = [{
        "lot_id": "plan-04_12p5", "rush_id": "plan-04",
        "frames_dir": "extract-frames/plan-04_12p5",
        "reconstructions": [{"ingest_slug": "scan-du-lundi"},
                            {"ingest_slug": "scan-du-mardi"}]}]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for relatif, octets in [("extract-frames/plan-04_12p5/f0.tiff", 101),
                            ("scans/scan-du-lundi/p001.tiff", 1111),
                            ("scans/scan-du-lundi/p002.tiff", 2222),
                            ("scans/scan-du-mardi/p001.tiff", 3333)]:
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)

    vu = _supprimer_le_groupe(banc, chemin, "scans —")

    partis = sorted(str(f.relative_to(chemin))
                    for f in (chemin / project_layout.SCANS_DIRNAME).rglob("*")) \
        if (chemin / project_layout.SCANS_DIRNAME).exists() else []
    assert partis == [], (
        "les deux scans doivent partir sous le consentement ordinaire "
        f"(`EPIC11-ARB-265`). Reste : {partis}")
    assert ps.CLE_SUPPRIMER_AVEC_SCANS not in vu["issues"], (
        "`EPIC11-ARB-265` tranche que le groupe des scans n'a PAS d'issue de "
        "consentement propre. En offrir une serait un drapeau sans effet : "
        "`scan_inclus` est force a faux sur un plan de groupe et les cibles "
        f"fines rendent `dossiers_de_scan=()`. Issues = {vu['issues']}")
    # **Le volet POSITIF, sans lequel l'assertion ci-dessus est tautologique.**
    # Une liste d'issues vide, ou un ecran qui n'aurait rien offert du tout,
    # satisferait un `not in`. On exige donc que le consentement ORDINAIRE soit
    # bien la -- c'est lui qui porte la decision.
    assert ps.CLE_SUPPRIMER in vu["issues"], (
        f"l'issue ordinaire doit etre offerte ; issues = {vu['issues']}")
