# -*- coding: utf-8 -*-
"""Le banc du lot C de la story 11.11 : `E6-2`, `E6-2b`, `E6-2c` et `E6-3`.

**Ce banc mesure une SUPPRESSION**, et deux de ses cas -- `C3` et `C5` -- sont
les plus importants de la story.

* « rien n'est ecrit » se mesure aux **inodes**, au **`st_mtime_ns`** et par
  **temoin**, jamais par un condensat : une fixture deterministe reecrite rend
  exactement les memes octets, donc un `md5` identique ne prouve rien du tout ;
* **`fichiers_non_supprimes` non vide n'est PAS un succes** : c'est la fuite de
  disque que la story existe pour fermer, et un ecran qui annoncerait la
  suppression dans ce cas serait le defaut lui-meme.

**La regle des fabriques s'applique ici plus qu'ailleurs.** Une liste de
suppression est exactement l'endroit ou un balayage tronque detruit sans le
dire : sauter la derniere entree d'une liste de fichiers a supprimer donne un
panneau plausible et une suppression partielle. Les fabriques produisent donc
au moins DEUX elements distinguables -- des tailles toutes differentes, jamais
un remplissage uniforme --, et les cibles sont posees en **tete**, au
**milieu** et en **queue**.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui.depot_projets import creer_projet

# ---------------------------------------------------------------------------
# Les valeurs que les maquettes E6-2* et E6-3b DESSINENT
# ---------------------------------------------------------------------------
#
# Elles sont declarees ICI et non en fin de fichier parce que `_plan` les
# prend en valeur par DEFAUT, et qu'un defaut s'evalue a la definition.
# Chacune est confrontee a sa source dans la derniere section du fichier.

#: Le libelle du lot, dessine par `E6-2` (titre du panneau), `E6-2c` (ligne
#: de travail) et `E6-3b` (premiere ligne du panneau).
LIBELLE_DESSINE_DU_LOT = "tout le lot plan-04_12p5"

#: Son prefixe seul, quand l'identifiant qui suit vient du banc.
PREFIXE_DESSINE_DU_LIBELLE = "tout le lot "

#: L'accord au singulier, dessine par `E6-2` et `E6-3b`.
SINGULIER_DESSINE = "1 fichier ·"

#: Son pluriel. **Il n'est PAS dessine tel quel** : les dessins ne portent
#: que « 62 fichiers · », dont c'est une sous-chaine a cheval sur le nombre.
#: La confrontation nomme la coincidence plutot que de la laisser passer
#: pour une recopie.
PLURIEL_DESSINE = "2 fichiers ·"

#: Le rang rendu, dessine dans la ligne d'etat de `E6-3b`.
RANG_RENDU_DESSINE = "rang v2 rendu"

from mixed_media_utility import codec_profiles
from mixed_media_utility.io import naming, project_layout
from mixed_media_utility.project_inventory import (ETAT_NON_DECLARE,
                                                   NATURE_FRAMES_EXTRAITES,
                                                   NATURE_FRAMES_SCANNEES,
                                                   NATURE_LOT,
                                                   NATURE_LOT_SCANNE,
                                                   NATURE_MASTER,
                                                   NATURE_PLANCHE, NATURE_RUSH,
                                                   NATURE_SCAN,
                                                   InventaireDuProjet,
                                                   InventaireError,
                                                   ManifesteIllisible,
                                                   ManifesteIncoherent,
                                                   ManifesteIntrouvable,
                                                   ObjetInventorie,
                                                   ProjetIntrouvable,
                                                   inventorier_le_projet)
from mixed_media_utility.project_maintenance import (LastLotRefusedError,
                                                     ProjectMaintenanceError,
                                                     RapportSuppression,
                                                     remove_project_element)
from mixed_media_utility.tui import execution, jetons, panneau as mod_panneau
from mixed_media_utility.tui.execution import EcranRefus
from mixed_media_utility.tui import projet_inventaire as pi
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui.coque import (Contexte, CoqueTui, EcranPasEncore,
                                           PalierTemoin)
from mixed_media_utility.tui.execution import EcranRefus

MODULE = Path(ps.__file__)


# ---------------------------------------------------------------------------
# Fabriques -- au moins DEUX elements, tous DISTINGUABLES
# ---------------------------------------------------------------------------


def _rapport(fichiers=("a/f0.tiff", "a/f1.tiff", "b/m.mov", "c/s0.tiff"),
             **kwargs) -> RapportSuppression:
    """Un rapport de dry-run. **Quatre fichiers dans TROIS dossiers.**

    Un rapport a un seul fichier rendrait invisible un balayage tronque : la
    seule entree serait a la fois la premiere et la derniere. Les trois
    dossiers ont des cardinaux differents (2, 1, 1) pour que le regroupement ne
    puisse pas etre confondu avec un comptage plat.
    """
    defauts = dict(cible="plan-04_12p5", fichiers_a_supprimer=tuple(fichiers),
                   dry_run=True)
    defauts.update(kwargs)
    return RapportSuppression(**defauts)


def _projet_a_supprimer(tmp_path) -> Path:
    """Un projet REEL, avec des octets **tous differents** d'un fichier a l'autre.

    Un poids agrege qui prendrait le premier fichier au lieu de la somme
    rendrait un nombre plausible sur une fabrique a fichiers identiques. Les
    tailles sont donc premieres entre elles a l'oeil : 11, 101, 202, 4004, 55,
    707, 33.

    **Trois rushes**, et le rush vise est au MILIEU : un `_find` fautif qui
    rendrait toujours le premier ne se demasque pas autrement (mutant `M25` de
    la story 5.7). Chaque rush porte un lot, et les cibles des tests sont
    posees en tete (`a-premier`), au milieu (`plan-04`) et en queue
    (`z-dernier`).
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "plan-04"},
                          {"rush_id": "z-dernier"}]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25"},
        {"lot_id": "plan-04_12p5", "rush_id": "plan-04",
         "frames_dir": "extract-frames/plan-04_12p5",
         "encoded_masters": [
             {"path": "outputs/plan-04_12p5_mmu_prores_hq.mov"}]},
        {"lot_id": "z-dernier_8", "rush_id": "z-dernier",
         "frames_dir": "extract-frames/z-dernier_8"},
    ]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    tailles = {
        "extract-frames/a-premier_25/f0.tiff": 11,
        "extract-frames/plan-04_12p5/f0.tiff": 101,
        "extract-frames/plan-04_12p5/f1.tiff": 202,
        "outputs/plan-04_12p5_mmu_prores_hq.mov": 4004,
        "extract-frames/z-dernier_8/f0.tiff": 33,
    }
    for relatif, octets in tailles.items():
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def _plan(tmp_path, cible=None, libelle=LIBELLE_DESSINE_DU_LOT, **kwargs):
    chemin = _projet_a_supprimer(tmp_path)
    return ps.preparer_la_suppression(
        chemin, cible or {"lot_id": "plan-04_12p5"}, libelle, **kwargs)


def _plan_de_synthese(rapport=None, projet=Path("."), **kwargs):
    """Un plan bati sur un rapport DONNE, sans coeur ni disque.

    C'est ce qui permet de mesurer la mise en page contre un rapport dont on
    choisit chaque champ -- et donc de verifier que le panneau LIT le rapport
    plutot que de recalculer quoi que ce soit.
    """
    rapport = rapport or _rapport()
    defauts = dict(projet=projet, cible={"lot_id": "plan-04_12p5"},
                   libelle=LIBELLE_DESSINE_DU_LOT, rapport=rapport,
                   poids=1_500_000_000,
                   groupes=(ps.GroupeEmporte("a/", 2, 770_000_000),
                            ps.GroupeEmporte("m.mov", 1, 206_000_000),
                            ps.GroupeEmporte("c/", 1, 550_000_000)))
    defauts.update(kwargs)
    return ps.PlanDeSuppression(**defauts)


def _noeud(nature, nom, rang=1, profondeur=3, etat="present",
           **kwargs):
    """Un noeud d'arbre bati par le VRAI constructeur de l'ecran d'inventaire.

    `pi._objet_affiche` plutot qu'un `NoeudAffiche(...)` a la main : c'est le
    chemin que l'ecran emprunte, donc c'est celui que le banc doit mesurer. Un
    noeud fabrique de toutes pieces divergerait du jour ou le constructeur
    poserait un champ de plus.
    """
    objet = ObjetInventorie(nature=nature, nom=nom, chemin=None,
                            etat=etat, rang=rang, **kwargs)
    return pi._objet_affiche(objet, profondeur)


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _empreinte(dossier: Path) -> dict[str, tuple[int, int, int]]:
    """L'etat du disque : **inode, `st_mtime_ns`, taille**, jamais un condensat.

    Un condensat ne distingue pas un fichier intact d'un fichier reecrit a
    l'identique -- et une fixture deterministe reecrite rend exactement les
    memes octets. L'inode distingue une reecriture en place d'un remplacement,
    et `st_mtime_ns` distingue une reecriture du meme contenu d'une absence
    d'ecriture. Les trois ensemble ne laissent aucune de ces trois pannes
    passer.
    """
    empreinte = {}
    for fichier in sorted(dossier.rglob("*")):
        if fichier.is_file():
            etat = fichier.lstat()
            empreinte[str(fichier.relative_to(dossier))] = (
                etat.st_ino, etat.st_mtime_ns, etat.st_size)
    return empreinte


# ---------------------------------------------------------------------------
# C1 -- `EcranChiffre` reutilise, `execution.py` intact
# ---------------------------------------------------------------------------


def test_C1_la_confirmation_HERITE_du_patron_et_n_en_reecrit_aucune_piece():
    """AC 3.1 : le point de jugement est le patron deja livre, pas un second.

    Les quatre pieces du patron -- la navigation clavier, la validation, le
    rendu des issues, la ligne de raccourcis en edition -- sont mesurees par
    IDENTITE avec celles d'`EcranChiffre` : une redefinition, meme correcte,
    serait la seconde implementation que ce patron existe pour eviter.
    """
    assert issubclass(ps.EcranSuppressionConfirmation, execution.EcranChiffre)
    for methode in ("traiter", "valider", "rendu_des_issues",
                    "_appliquer_les_raccourcis", "on_key"):
        assert (ps.EcranSuppressionConfirmation.__dict__.get(methode) is None), (
            f"{methode} est redefinie : le patron de la story 11.1 est "
            "reecrit au lieu d'etre consomme")


# La frontiere negative d'AC 3.1 a ete RETIREE le 2026-09-07, sur arbitrage
# d'Egan, et le dire ici vaut mieux que de la laisser reapparaitre.
#
# Elle mesurait, sur `git diff origin/oc/epic-11-TUI...HEAD`, que la story
# n'avait modifie ni `execution.py`, ni `panneau.py`, ni
# `project_maintenance.py`. Elle etait fausse **des deux cotes**, et une
# session voisine (branche `claude/epic-8-packaging`) en a mesure la moitie
# que nous ne pouvions pas voir :
#
# * HORS de cette branche, un diff a TROIS POINTS rend tout ce que HEAD porte
#   depuis la base commune, c'est-a-dire la divergence ENTIERE et non le diff
#   d'une story : les trois fichiers interdits y figurent forcement, et la
#   garde rougissait sur toute branche qui n'etait pas la notre. Elle mesurait
#   donc « je suis sur oc/epic-11-TUI » autant que l'AC ;
# * SUR cette branche, une fois les commits pousses, ce meme diff est VIDE :
#   la garde passait sans rien mesurer. C'est le defaut le plus grave des
#   deux, et il etait invisible parce qu'un test vert ne se relit pas.
#
# **Pourquoi elle n'a pas ete reparee mais retiree.** Le module de l'ecran
# IMPORTE `execution.py` et `panneau.py` (l. 70-72 de `projet_suppression.py`)
# -- c'est la reutilisation que l'AC 3.1 veut. Ce que l'AC interdit est de les
# MODIFIER, ce qui ne s'exprime que sur un diff ; et un diff n'a plus de base
# stable une fois la story fusionnee. La garde verifiait un fait de
# DEVELOPPEMENT, pas un comportement du produit : ce fait a ete verifie quand
# il comptait, il est dans l'historique, et la politique de revue du depot
# prevoit ce cas (section 7, duree de vie d'une garde de non-regression au
# source).
#
# Ce qui la remplace, et c'est deja la : le test ci-dessus mesure par IDENTITE
# que les quatre pieces du patron ne sont pas redefinies. C'est la moitie
# positive de l'AC, et elle, elle est durable.
#
# Ce qui n'est PAS couvert, dit plutot que tu : plus rien n'attrapera
# quelqu'un qui ajouterait demain, dans `execution.py`, une ligne propre a la
# suppression. Une mesure structurelle a ete envisagee et chiffree -- elle
# serait LEXICALE (chercher « supprim » dans les deux modules partages) et
# demanderait deux exemptions des le premier jour, sur deux phrases sans
# rapport. Elle rougirait un jour sur un mot plutot que sur un defaut ; c'est
# ce qui l'a fait ecarter.


def test_C1_l_ecran_n_ouvre_AUCUN_champ_de_nom(banc):
    """AC 5.1 / `EPIC11-ARB-141` : par ABSENCE de champ, pas par une garde.

    Le volet symetrique est le point : `Tab` est mesure INERTE. Une garde qui
    rendrait `Tab` inerte tout en gardant un `ModeleNoms` peuple laisserait le
    champ atteignable par un autre chemin.
    """
    ecran = ps.EcranSuppressionConfirmation(_plan_de_synthese(),
                                            sur_issue=lambda issue: None)
    assert len(ecran.noms) == 0
    assert ecran.traiter("tab") is False
    assert "éditer" not in ps.RACCOURCIS_CONFIRMATION


# ---------------------------------------------------------------------------
# C2 -- le panneau porte le rapport du dry-run, jamais un recalcul
# ---------------------------------------------------------------------------


def test_C2_la_preparation_appelle_le_coeur_en_DRY_RUN_et_rien_d_autre():
    """AC 3.3 : le premier appel du chemin est un dry-run, par construction.

    L'ensemble EXACT des mots-cles est mesure (AC 5.2) : ce test rougira le
    jour ou un parametre s'ajoutera a `remove_project_element` sans etre cable,
    ce qu'un test « il n'y a pas de `dry_run=False` » ne ferait pas.
    """
    appels = []

    def faux_remove(projet, **mots):
        appels.append((projet, mots))
        return _rapport()

    ps.preparer_la_suppression(Path("/nulle-part"), {"lot_id": "L"}, "le lot L",
                               retirer_du_projet=faux_remove)
    assert len(appels) == 1
    _projet, mots = appels[0]
    assert mots == {"lot_id": "L", "dry_run": True, "avec_scans": False}


def test_C2_le_panneau_LIT_le_rapport_et_ne_recalcule_AUCUN_cardinal():
    """AC 3.2 : chaque chiffre du cartouche vient du rapport.

    Le rapport est fabrique avec des cardinaux **impossibles a deviner** : cinq
    fichiers dont deux annexes absentes, et deux rangs liberables non
    contigus. Un panneau qui recalculerait a partir du disque -- vide ici --
    rendrait zero partout.
    """
    rapport = _rapport(
        fichiers=("a/f0.tiff", "a/f1.tiff", "a/f2.tiff", "b/m.mov", "c/s.tiff"),
        fichiers_attendus_absents=("planches/p1.pdf", "planches/p2.pdf"),
        rangs_liberables=(2, 5))
    plan = _plan_de_synthese(rapport=rapport,
                             groupes=ps.groupes_emportes(Path("/nulle-part"),
                                                         rapport))
    lignes = ps.panneau_de_la_confirmation(plan).rendu(80)
    texte = "\n".join(lignes)
    assert f"{ps.LIBELLE_FICHIERS}" in texte and "5 fichiers" in texte
    # Trois dossiers plus DEUX annexes absentes : cinq groupes, et le compte
    # est celui du rapport, pas celui des fichiers.
    assert "5 groupes d'objets" in texte
    assert "v2 · v5" in texte


def test_C2_le_poids_est_MESURE_sur_le_disque_fichier_par_fichier(tmp_path):
    """L'ecart 1 du lot D, et la seule mesure qui le comble sans mentir.

    `RapportSuppression` ne porte **aucun octet**. Le poids est donc `lstat`e
    sur chacun des chemins que le rapport nomme -- et le test le confronte a la
    SOMME reellement ecrite, avec des tailles toutes differentes : une somme
    qui prendrait le premier fichier, ou le dernier, ou la moyenne, rendrait
    ici trois nombres distincts et tous faux.
    """
    for relatif, octets in (("a/f0", 11), ("a/f1", 101), ("b/m", 4004)):
        cible = tmp_path / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    assert ps.poids_des_fichiers(tmp_path, ("a/f0", "a/f1", "b/m")) == 4116
    # Un chemin absent ne fait pas echouer le panneau entier : un point de
    # jugement qui leve au lieu de s'afficher est un blocage sec.
    assert ps.poids_des_fichiers(tmp_path, ("a/f0", "nulle-part")) == 11


def test_C2_le_regroupement_n_OUBLIE_NI_la_premiere_NI_la_derniere_entree():
    """Le mutant de bord de la regle des fabriques, pose des DEUX cotes.

    Un balayage tronque d'un cote ou de l'autre reste invisible si toutes les
    cibles sont au milieu -- c'est le mutant survivant du lot A de la 11.11.
    Les deux bords portent donc ici un dossier a UN seul fichier, que la
    troncature ferait disparaitre entierement.
    """
    rapport = _rapport(fichiers=("tete/seul.tiff", "milieu/a.tiff",
                                 "milieu/b.tiff", "queue/seul.mov"))
    groupes = ps.groupes_emportes(Path("/nulle-part"), rapport)
    assert [g.libelle for g in groupes] == ["seul.tiff", "milieu/", "seul.mov"]
    assert [g.fichiers for g in groupes] == [1, 2, 1]


def test_C2_l_ordre_du_RAPPORT_est_preserve_et_non_trie():
    """« dans l'ordre ou l'appelant les a construits » -- et cet ordre INFORME.

    `E6-2` dessine les frames, puis le master, puis le scan : c'est l'ordre du
    coeur. Un tri alphabetique le detruirait sans rien lever, et le panneau
    resterait plausible.
    """
    rapport = _rapport(fichiers=("zzz/frames.tiff", "aaa/master.mov"))
    groupes = ps.groupes_emportes(Path("/nulle-part"), rapport)
    assert [g.libelle for g in groupes] == ["frames.tiff", "master.mov"]


def test_C2_une_annexe_ABSENTE_ne_porte_ni_cardinal_ni_poids():
    """Elle n'occupe rien : lui preter un poids serait un chiffre faux.

    Et elle porte le glyphe d'absence, jamais la couleur seule -- `DESIGN.md`
    section 5 veut les deux canaux.
    """
    absente = ps.GroupeEmporte("planches.pdf", 0, 0, absent=True)
    rendu = absente.rendu()
    assert rendu.startswith(jetons.GLYPHES["absent"])
    assert ps.ETAT_ANNEXE_ABSENTE in rendu
    assert "0 fichier" not in rendu


# ---------------------------------------------------------------------------
# C3 -- RIEN n'est ecrit : inodes, `st_mtime_ns`, temoin
# ---------------------------------------------------------------------------


def test_C3_monter_le_point_de_jugement_n_ECRIT_RIEN(tmp_path, banc):
    """AC 3.3, et c'est le cas le plus important de la story avec `C5`.

    Le parcours entier est joue -- preparation, montage, parcours des issues
    aux deux bouts, validation sur `Annuler` -- puis le disque est confronte
    **inode par inode** a ce qu'il etait, `st_mtime_ns` compris. Un temoin est
    depose dans le dossier vise : un `rmtree` du dossier l'emporterait sans
    toucher a un seul des fichiers que le rapport nomme, et une empreinte
    limitee a ces fichiers-la ne le verrait pas.
    """
    chemin = _projet_a_supprimer(tmp_path)
    # Le nom du dossier est **lu** de `io/project_layout` et jamais compose
    # ici : c'est le seul lieu du depot qui connaisse la cohabitation du nom
    # neuf et de celui d'avant (`EPIC11-ARB-222`).
    temoin = (project_layout.extract_frames_dir_from_slug(chemin, "plan-04_12p5")
              / "TEMOIN.txt")
    temoin.write_text("je ne dois pas bouger", encoding="utf-8")
    avant = _empreinte(chemin)
    inode_du_temoin = temoin.lstat().st_ino

    plan = ps.preparer_la_suppression(chemin, {"lot_id": "plan-04_12p5"},
                                      LIBELLE_DESSINE_DU_LOT)
    retenue = []
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=retenue.append)

    async def scenario(pilote):
        ecran.rafraichir()
        for _ in range(len(ecran.choix.issues) + 2):
            ecran.traiter("down")
        for _ in range(len(ecran.choix.issues) + 2):
            ecran.traiter("up")
        ecran.choix.viser(ps.CLE_ANNULER)
        ecran.traiter("enter")
        return ecran.lignes_du_panneau(), ecran.etat()

    lignes, etat = _monte(_app(ecran), scenario, banc)

    assert _empreinte(chemin) == avant
    assert temoin.exists() and temoin.lstat().st_ino == inode_du_temoin
    assert retenue and retenue[-1].cle == ps.CLE_ANNULER
    assert retenue[-1].ecrit is False
    assert ps.PHRASE_RIEN_ECRIT in etat
    assert any(ps.LIBELLE_POIDS in ligne for ligne in lignes)


def test_C3_la_ligne_d_etat_DIT_que_rien_n_est_ecrit_et_reste_RIEN_ECRIT():
    """La phrase est epinglee PAR REFERENCE a `panneau.RIEN_ECRIT`.

    Les maquettes l'ecrivent en bas de casse et sans point final ; la constante
    du depot la porte en phrase. Deux redactions divergeraient au premier
    ajustement, et la ligne d'etat de cet ecran cesserait de dire ce que les
    quatre ateliers disent. La frontiere compare a la casse et au point pres.
    """
    assert (ps.PHRASE_RIEN_ECRIT.lower()
            == mod_panneau.RIEN_ECRIT.rstrip(".").lower())
    plan = _plan_de_synthese()
    assert ps.ligne_d_etat_de_la_confirmation(plan).endswith(
        ps.PHRASE_RIEN_ECRIT)


def test_C3_le_curseur_se_pose_sur_l_issue_qui_ne_DETRUIT_PAS(tmp_path):
    """AC 3.4, et il est tenu par le PATRON, pas par une ligne ajoutee ici.

    `ChoixExclusif` pose le curseur sur la premiere issue qui n'ecrit pas. Le
    test le mesure sur les deux formes du choix -- avec et sans rang liberable
    -- parce qu'une issue de plus decale les rangs et qu'un curseur ecrit en
    dur passerait le premier cas tout seul.
    """
    for rangs in ((), (2, 3)):
        plan = _plan_de_synthese(rapport=_rapport(rangs_liberables=rangs))
        choix = ps.issues_de_la_suppression(plan)
        assert choix.issues[choix.curseur].ecrit is False
        assert choix.issues[choix.curseur].cle == ps.CLE_ANNULER


def test_C3_annuler_n_appelle_PAS_le_coeur_du_tout():
    """L'issue qui n'ecrit pas ne produit aucun appel -- pas meme un dry-run.

    Un `remove(..., dry_run=True)` de plus serait inoffensif et **c'est le
    piege** : il resterait vert dans un test qui ne compte pas les appels, et
    il ferait ecrire le jour ou un mutant retire le `dry_run`.
    """
    appels = []
    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_ANNULER)
    assert ps.mots_cles_de_l_issue(plan, issue) is None
    assert ps.executer_la_suppression(
        plan, issue,
        retirer_du_projet=lambda *a, **k: appels.append(k)) is None
    assert appels == []


# ---------------------------------------------------------------------------
# C4 -- le dernier lot et sa confirmation supplementaire
# ---------------------------------------------------------------------------


def test_C4_le_refus_du_dernier_lot_est_CONSTATE_puis_le_rapport_est_obtenu():
    """AC 3.5 : le plan ne PREDIT pas le dernier lot, il constate le refus.

    Compter les lots ici serait une seconde redaction de la garde du coeur, et
    elle divergerait -- c'est l'ecart 2 du lot D, mesure. Le second appel est
    verifie **encore en dry-run** : obtenir le rapport ne doit rien ecrire.
    """
    appels = []

    def faux_remove(projet, **mots):
        appels.append(mots)
        if not mots.get("confirmation_dernier_lot"):
            raise LastLotRefusedError("dernier lot")
        return _rapport()

    plan = ps.preparer_la_suppression(Path("/nulle-part"), {"lot_id": "L"},
                                      "le lot L", retirer_du_projet=faux_remove)
    assert plan.dernier_lot is True
    assert len(appels) == 2
    assert all(mots["dry_run"] is True for mots in appels)
    assert appels[1]["confirmation_dernier_lot"] is True


def test_C4_le_panneau_DIT_pourquoi_la_confirmation_supplementaire_existe():
    """AC 3.5 : le panneau dit pourquoi, il ne se contente pas d'exiger.

    Le volet symetrique est le point : la phrase est **absente** quand le lot
    n'est pas le dernier. Une phrase toujours presente informerait autant
    qu'une phrase jamais presente.
    """
    dernier = _plan_de_synthese(dernier_lot=True)
    ordinaire = _plan_de_synthese(dernier_lot=False)
    assert ps.PHRASE_DERNIER_LOT in ps.lignes_des_emportes(dernier)
    assert ps.PHRASE_DERNIER_LOT not in ps.lignes_des_emportes(ordinaire)


def test_C4_le_consentement_supplementaire_est_un_mot_cle_DISTINCT():
    """« deux consentements empiles, jamais un seul qui couvre les deux ».

    `dry_run=False` et `confirmation_dernier_lot=True` sont deux mots-cles, et
    le second n'est leve que lorsque le coeur a refuse sans lui.
    """
    plan = _plan_de_synthese(dernier_lot=True)
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    mots = ps.mots_cles_de_l_issue(plan, issue)
    assert mots["dry_run"] is False
    assert mots["confirmation_dernier_lot"] is True
    ordinaire = _plan_de_synthese(dernier_lot=False)
    assert "confirmation_dernier_lot" not in ps.mots_cles_de_l_issue(
        ordinaire, issue)


def test_C4_le_troisieme_consentement_des_SCANS_a_son_issue_propre():
    """`EPIC11-ARB-90` : un dossier de scan ne se refabrique pas par calcul.

    L'issue n'existe que lorsque le coeur NOMME un scan sans l'inclure -- une
    issue sans objet serait une promesse cassee --, et elle leve `avec_scans`
    et rien d'autre.
    """
    sans = _plan_de_synthese(rapport=_rapport())
    assert ps.CLE_SUPPRIMER_AVEC_SCANS not in [
        i.cle for i in ps.issues_de_la_suppression(sans).issues]
    avec = _plan_de_synthese(
        rapport=_rapport(dossiers_de_scan=("scans/plan-04_12p5",),
                         scan_inclus=False))
    choix = ps.issues_de_la_suppression(avec)
    issue = choix.issue(ps.CLE_SUPPRIMER_AVEC_SCANS)
    assert issue.ecrit is True
    assert ps.mots_cles_de_l_issue(avec, issue)["avec_scans"] is True
    assert "avec_scans" not in ps.mots_cles_de_l_issue(
        avec, choix.issue(ps.CLE_SUPPRIMER))


def test_C4_ARB89_le_choix_porte_TOUJOURS_une_issue_qui_n_ecrit_pas():
    """`EPIC11-ARB-89` : jamais une seule issue, jamais un blocage sec.

    Mesure sur les HUIT formes du rapport que ce module sait rendre -- la
    combinatoire des rangs liberables, des scans nommes et du dernier lot.
    Chacune porte au moins deux issues, et au moins une qui n'ecrit pas.
    """
    for rangs in ((), (2,)):
        for scans in ((), ("scans/plan-04_12p5",)):
            for dernier in (False, True):
                plan = _plan_de_synthese(
                    rapport=_rapport(rangs_liberables=rangs,
                                     dossiers_de_scan=scans),
                    dernier_lot=dernier)
                choix = ps.issues_de_la_suppression(plan)
                assert len(choix.issues) >= 2, (rangs, scans, dernier)
                assert choix.sortie_sans_ecriture is not None


def test_C4_liberer_le_rang_n_est_propose_QUE_si_un_rang_est_liberable():
    """`EPIC11-ARB-108` : la ligne d'eau se pose au retrait, par le COEUR.

    L'ecran ne calcule aucun rang : il propose l'issue quand le rapport en
    declare un liberable, et leve `liberer_le_rang`. Le volet symetrique --
    aucun rang, aucune issue -- est ce qui empeche une issue sans effet.
    """
    sans = _plan_de_synthese(rapport=_rapport(rangs_liberables=()))
    assert ps.CLE_SUPPRIMER_ET_LIBERER not in [
        i.cle for i in ps.issues_de_la_suppression(sans).issues]
    avec = _plan_de_synthese(rapport=_rapport(rangs_liberables=(2, 3)))
    choix = ps.issues_de_la_suppression(avec)
    issue = choix.issue(ps.CLE_SUPPRIMER_ET_LIBERER)
    assert "v2 · v3" in issue.libelle
    assert ps.mots_cles_de_l_issue(avec, issue)["liberer_le_rang"] is True
    assert "liberer_le_rang" not in ps.mots_cles_de_l_issue(
        avec, choix.issue(ps.CLE_SUPPRIMER))


# ---------------------------------------------------------------------------
# C5 -- `fichiers_non_supprimes` non vide n'est PAS un succes
# ---------------------------------------------------------------------------


def test_C5_le_resultat_N_ANNONCE_PAS_la_suppression_quand_il_reste(banc):
    """AC 4.2, et c'est la fuite que la story existe pour fermer.

    Trois volets, et il en faut trois : le titre porte le mot `INCOMPLÈTE`, les
    chemins restes sont NOMMES un par un -- un cardinal seul ne permettrait pas
    d'aller les chercher --, et la ligne d'etat dit le glyphe d'absence.
    """
    restes = ("outputs/plan-04_12p5_mmu_prores_hq.mov",
              "extract-frames/plan-04_12p5/f0.tiff",
              "extract-frames/plan-04_12p5/f1.tiff")
    rapport = _rapport(fichiers_non_supprimes=restes, supprime=False,
                       dry_run=False)
    plan = _plan_de_synthese()
    ecran = ps.EcranResultatDeSuppression(plan, rapport)

    async def scenario(pilote):
        ecran.rafraichir()
        return ecran.lignes(), ecran.etat(), ecran.rang_du_curseur()

    lignes, etat, rang = _monte(_app(ecran), scenario, banc)
    texte = "\n".join(lignes)
    assert ps.TITRE_INCOMPLETE in "\n".join(
        ps.panneau_du_resultat(plan, rapport).rendu(80) + [ecran.panneau.titre])
    for chemin in restes:
        assert chemin in texte, chemin
    # **Le glyphe OUVRE la ligne**, il n'y flotte pas : `jetons.jeton_d_etat`
    # exige qu'il ouvre une colonne pour teindre la ligne, et `DESIGN.md`
    # section 5 veut les deux canaux, jamais la couleur seule.
    assert etat.startswith(jetons.GLYPHES["absent"])
    # **Le volet negatif, et il porte sur un VOCABULAIRE de succes.** Dire
    # « supprimé n'apparait pas » serait faux -- la ligne dit precisement
    # « n'ont pas pu être supprimés », qui est une NEGATION. Ce qui ne doit
    # jamais apparaitre, c'est un mot qui annonce l'aboutissement.
    for mot in ("réussi", "terminé", "succès", "complet", "effectué"):
        assert mot not in etat.lower(), mot
        assert mot not in texte.lower(), mot
    # Le curseur DESIGNE une suite, jamais un chemin reste.
    assert lignes[rang].lstrip().lstrip(
        jetons.GLYPHES["curseur"]).strip() == ps.SUITE_REESSAYER


def test_C5_supprime_reste_FAUX_tant_qu_un_fichier_reste(tmp_path):
    """Le contrat du coeur, confronte au VRAI coeur et non a une fabrique.

    « `supprime` ne vaut `True` que si cette liste est vide. » Un ecran qui
    lirait `supprime` sans regarder `fichiers_non_supprimes` serait juste
    aujourd'hui et faux le jour ou le coeur change ; un ecran qui lit la liste
    est juste dans les deux cas. Ce test mesure les DEUX ensemble.
    """
    chemin = _projet_a_supprimer(tmp_path)
    rapport = remove_project_element(chemin, lot_id="plan-04_12p5",
                                     dry_run=False)
    assert rapport.fichiers_non_supprimes == ()
    assert rapport.supprime is True
    # Le symetrique, sur une fabrique : la seule facon d'obtenir un reste sans
    # casser les droits du conteneur, ou `root` supprime tout.
    reste = _rapport(fichiers_non_supprimes=("a/f0.tiff",), supprime=False)
    assert reste.supprime is False


def test_C5_les_poids_du_resultat_sont_MESURES_et_non_soustraits_a_l_aveugle(
        tmp_path):
    """Ce qui reste occupe encore le disque, donc il se `lstat`.

    Les tailles sont toutes differentes : une soustraction qui prendrait le
    mauvais fichier rendrait un nombre plausible. `Supprimés` vaut le poids
    d'avant moins ce qui reste, et le test le confronte aux octets ecrits.
    """
    for relatif, octets in (("reste/a", 101), ("reste/b", 202)):
        cible = tmp_path / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    plan = _plan_de_synthese(projet=tmp_path, poids=4307,
                             rapport=_rapport(fichiers=("reste/a", "reste/b",
                                                        "parti/c")))
    rapport = _rapport(fichiers=("reste/a", "reste/b", "parti/c"),
                       fichiers_non_supprimes=("reste/a", "reste/b"),
                       dry_run=False)
    texte = "\n".join(ps.panneau_du_resultat(plan, rapport).rendu(80))
    assert ps.MANIFESTE_A_JOUR in texte
    # 4307 - 303 = 4004 octets partis, soit `3,9 ko`, et 303 restes.
    assert pi.poids_lisible(4307 - 303) in texte
    assert pi.poids_lisible(303) in texte
    assert SINGULIER_DESSINE in texte and PLURIEL_DESSINE in texte


def test_C5_le_MOTIF_est_generique_et_le_coeur_n_en_rend_aucun():
    """Le coeur nomme les chemins, jamais la raison -- dit plutot que tu.

    Un diagnostic par chemin (« droits refusés » contre « fichier verrouillé »)
    serait une mesure inventee. La frontiere mesure que le rapport ne porte
    aucun champ de motif : elle rougira le jour ou le coeur en gagnera un, ce
    qui est exactement le moment ou cette phrase devra disparaitre.
    """
    import dataclasses
    champs = {f.name for f in dataclasses.fields(RapportSuppression)}
    assert not {"motif", "motifs", "raison", "raisons"} & champs
    assert ps.MOTIF_DES_RESTES in "\n".join(ps.lignes_des_restes(
        _rapport(fichiers_non_supprimes=("a/f0.tiff",))))


def test_C5_aucune_ligne_de_reste_quand_TOUT_est_parti():
    """Le volet symetrique : `E6-3` ne se monte que s'il RESTE quelque chose.

    Sans lui, un rendu qui poserait toujours la tete `✕ 0 fichier occupe
    toujours le disque` passerait le test precedent et annoncerait une fuite
    inexistante.
    """
    assert ps.lignes_des_restes(_rapport(fichiers_non_supprimes=())) == []


# ---------------------------------------------------------------------------
# C6 -- la frontiere AST, NEGATIVE
# ---------------------------------------------------------------------------


#: Ce qu'aucun ecran de suppression n'appelle. Le nom est celui de l'ATTRIBUT
#: ou de la fonction appelee, jamais une sous-chaine : `remove_project_element`
#: contient `remove` et doit passer, ce qu'un `grep` ne saurait pas distinguer.
APPELS_DESTRUCTEURS = {"unlink", "rmtree", "remove", "rmdir", "removedirs",
                       "replace", "rename", "truncate", "write_text",
                       "write_bytes"}


def _appels_destructeurs(source: str) -> list[tuple[str, int]]:
    """Les destructeurs appeles dans cette source : `(nom, ligne)`.

    La LIGNE est rendue avec le nom parce que c'est elle qui rend le rouge
    actionnable : « ce module appelle rmtree » sans dire ou fait relire deux
    mille lignes.

    **UNE seule redaction, partagee par la frontiere et par son volet
    symetrique** (finding `T-5` de la couche 3). Les deux la recopiaient : le
    volet prouvait donc que SA COPIE attrape `rmtree`, jamais que celle de la
    frontiere le ferait si elle divergeait. C'est la faiblesse structurelle
    exacte de `C-2`, ou une frontiere promettait de voir une classe qu'elle ne
    voyait pas et ou son volet symetrique filtrait un tuple litteral -- en
    beaucoup moins grave ici, les deux copies etant adjacentes et courtes, mais
    c'est un patron a ne pas propager.

    Le nom lu est celui de l'ATTRIBUT ou de la fonction appelee, jamais une
    sous-chaine : `remove_project_element` contient `remove` et doit passer.
    """
    trouves = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        nom = (fonction.attr if isinstance(fonction, ast.Attribute)
               else fonction.id if isinstance(fonction, ast.Name) else None)
        if nom in APPELS_DESTRUCTEURS:
            trouves.append((nom, noeud.lineno))
    return trouves


def test_C6_aucun_appel_DESTRUCTEUR_dans_le_module_d_ecran():
    """AC 4.1, et c'est une frontiere NEGATIVE -- la seule qui attrape un retour.

    Aucun test positif ne verrait revenir un `shutil.rmtree` glisse dans une
    branche d'erreur : le chemin nominal resterait vert. Un `grep` ne
    conviendrait pas non plus -- il rougirait sur `remove_project_element`,
    qui est precisement l'appel qu'on VEUT. L'AST distingue le nom appele de la
    chaine qui le contient.
    """
    trouves = _appels_destructeurs(MODULE.read_text(encoding="utf-8"))
    assert trouves == [], (
        f"{MODULE.name} appelle un destructeur : {trouves}. La TUI ne supprime "
        "aucun fichier elle-meme (AC 4.1).")
    # **Cette frontiere a deja mordu, des sa premiere execution** : le mot-cle
    # injectable du module s'appelait `remove`, donc `remove(projet, ...)`
    # etait litteralement un appel a `remove`. Le renommer en
    # `retirer_du_projet` n'est pas une concession a la frontiere : un
    # parametre nomme `remove` masquerait un `os.remove` reintroduit un jour au
    # meme nom, et la frontiere ne pourrait plus les distinguer.
    assert "retirer_du_projet" in MODULE.read_text(encoding="utf-8")


def test_C6_la_frontiere_ATTRAPE_bien_ce_qu_elle_pretend_attraper():
    """Le volet symetrique : une frontiere negative se **prouve** sur un cas.

    Une frontiere qui ne rougit sur rien est indistinguable d'une frontiere
    cassee. Le mutant est injecte ici, dans une source de synthese, plutot que
    dans le module -- ce qui la rend mesurable sans jamais toucher au fichier.

    **Et il passe par la MEME fonction que la frontiere** depuis le
    2026-09-06 : il recopiait sa boucle `ast.walk`, donc il prouvait que cette
    COPIE attrape `rmtree` et rien de plus (finding `T-5`).
    """
    source = "import shutil\ndef f(p):\n    shutil.rmtree(p)\n    p.unlink()\n"
    assert sorted(nom for nom, _ in _appels_destructeurs(source)) == [
        "rmtree", "unlink"]
    # Et la ligne remonte avec le nom : c'est ce qui rend le rouge actionnable.
    assert dict(_appels_destructeurs(source)) == {"rmtree": 3, "unlink": 4}
    # Et le nom qu'elle doit LAISSER passer.
    passe = ast.parse("remove_project_element(p, dry_run=False)")
    appel = passe.body[0].value
    assert appel.func.id == "remove_project_element"
    assert appel.func.id not in APPELS_DESTRUCTEURS


def test_C6_le_module_n_importe_JAMAIS_cli():
    """`EPIC11-ARB-67` : la TUI ne passe pas par la ligne de commande."""
    arbre = ast.parse(MODULE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            assert (noeud.module or "").split(".")[-1] != "cli"
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                assert alias.name.split(".")[-1] != "cli"


def test_C6_l_ecriture_passe_par_le_point_d_entree_du_COEUR(tmp_path):
    """Le volet positif de `C6` : la suppression marche, et c'est le coeur.

    Sans lui, un module qui n'appellerait rien du tout passerait la frontiere
    negative avec les honneurs.
    """
    chemin = _projet_a_supprimer(tmp_path)
    plan = ps.preparer_la_suppression(chemin, {"lot_id": "plan-04_12p5"},
                                      LIBELLE_DESSINE_DU_LOT)
    avant = _empreinte(chemin)
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    rapport = ps.executer_la_suppression(plan, issue)
    assert rapport.supprime is True
    assert rapport.fichiers_non_supprimes == ()
    apres = _empreinte(chemin)
    partis = set(avant) - set(apres)
    assert partis == set(plan.rapport.fichiers_a_supprimer)
    # Les lots des DEUX bords sont intacts : une suppression qui deborderait
    # sur ses voisins ne se voit pas sur le lot vise.
    assert "extract-frames/a-premier_25/f0.tiff" in apres
    assert "extract-frames/z-dernier_8/f0.tiff" in apres


# ---------------------------------------------------------------------------
# Designer la cible : le profil du master, relu du nom (Egan, 2026-09-05)
# ---------------------------------------------------------------------------


def test_le_profil_du_master_se_relit_du_nom_pour_CHAQUE_profil_du_registre():
    """Egan, 2026-09-05 : « Il est contenu dans le nom du master ».

    **Les SEPT profils du registre sont essayes**, pas un echantillon : le
    registre est ce qui rend la lecture exacte, donc c'est lui qui doit etre
    balaye. Une reconnaissance ecrite pour `prores_hq` seul passerait un test
    a un profil et laisserait les six autres muets.
    """
    from mixed_media_utility import codec_profiles

    assert len(codec_profiles.PROFILES) >= 7
    for profil, entree in sorted(codec_profiles.PROFILES.items()):
        nom = f"plan-04_25{naming.MASTER_FILENAME_MARKER}{profil}.mov"
        lu = ps.profil_du_master(nom, "plan-04_25")
        assert lu is not None and lu.profil == profil, nom
        assert lu.resolution is None and lu.rang == 1


def test_le_profil_le_plus_LONG_gagne_et_sur_une_FRONTIERE():
    """`dnxhr_hq` est un prefixe STRICT de `dnxhr_hqx`, et c'est le piege.

    Un `startswith` naif, ou un balayage dans l'ordre du dictionnaire, lirait
    `dnxhr_hq` dans `dnxhr_hqx` -- et supprimerait le master d'un AUTRE profil,
    sans rien lever. C'est exactement la classe de defaut que la regle des
    fabriques vise : la cible n'est pas en premiere position dans l'ensemble
    des candidats, et seul un ordre par longueur decroissante la trouve.

    Les deux sens sont mesures : le court ne doit pas manger le long, et le
    long ne doit pas manger le court.
    """
    court = ps.profil_du_master("L_mmu_dnxhr_hq.mov", "L")
    long_ = ps.profil_du_master("L_mmu_dnxhr_hqx.mov", "L")
    assert court is not None and court.profil == "dnxhr_hq"
    assert long_ is not None and long_.profil == "dnxhr_hqx"
    # Et la frontiere du separateur : `dnxhr_hqx_uhd` est le profil LONG plus
    # une resolution, pas le profil court plus `x_uhd`.
    avec_resolution = ps.profil_du_master("L_mmu_dnxhr_hqx_uhd.mov", "L")
    assert avec_resolution.profil == "dnxhr_hqx"
    assert avec_resolution.resolution == "uhd"


def test_le_prefixe_du_lot_se_retire_par_EGALITE_jamais_par_ressemblance():
    """Le `lot_id` est CONNU : il vient du noeud parent, il n'est pas devine.

    C'est ce qui separe cette lecture de la filiation devinee que le depot
    refuse partout ailleurs. Le volet negatif le mesure : un nom qui porte un
    AUTRE lot ne rend rien, meme quand il porte un profil parfaitement valide
    -- un `split('_mmu_')` le lirait quand meme et supprimerait le master d'un
    autre lot.
    """
    assert ps.profil_du_master("autre-lot_mmu_prores_hq.mov", "plan-04_25") is None
    assert ps.profil_du_master("plan-04_2_mmu_prores_hq.mov", "plan-04_25") is None
    assert ps.profil_du_master("plan-04_25_mmu_prores_hq.mov",
                               "plan-04_25") is not None


def test_un_profil_INCONNU_du_registre_ne_rend_RIEN_plutot_qu_une_valeur():
    """La sortie honnete : un nom qu'on ne sait pas lire ne se devine pas.

    Un master renomme a la main, ou produit par une version anterieure de
    l'outil, tombe ici. Rendre `inconnu` comme profil ferait appeler le coeur
    avec une valeur qu'il refuserait -- ou pire, qu'il accepterait.
    """
    assert ps.profil_du_master("L_mmu_inconnu.mov", "L") is None
    assert ps.profil_du_master("L_mmu_.mov", "L") is None
    assert ps.profil_du_master("L_sans_marqueur.mov", "L") is None


def test_le_RANG_du_master_est_lu_par_la_fonction_du_depot_et_pas_recopie():
    """`EPIC11-ARB-91` : le rang du MASTER est distinct du rang du LOT.

    Il est lu par `naming.rang_du_fragment_de_version`, la fonction qui ecrit
    la regle, et la resolution qui le PRECEDE ne doit pas l'avaler -- l'ordre
    d'ecriture est `profil`, puis `resolution`, puis `version`.
    """
    for rang in (2, 9, 42):
        nom = (f"L{naming.MASTER_FILENAME_MARKER}prores_hq"
               f"{naming.format_version_suffix(rang)}.mov")
        assert ps.profil_du_master(nom, "L").rang == rang
    complet = ps.profil_du_master("L_mmu_prores_hq_1920x1080_v2.mov", "L")
    assert complet.profil == "prores_hq"
    assert complet.resolution == "1920x1080"
    assert complet.rang == 2


def test_le_rang_LU_DU_NOM_egale_celui_que_le_COEUR_inventorie(tmp_path):
    """Frontiere PAR REFERENCE entre deux lectures du meme rang.

    L'ecran transmet `version=` depuis `ObjetInventorie.rang`, que le coeur
    remplit ; `profil_du_master` le relit du nom. Les deux s'accordent
    aujourd'hui -- mesure : `_v2` rend 2 des deux cotes -- et rien ne les tient
    ensemble. Cette frontiere les tient : le jour ou l'une des deux lectures
    change, elle rougit au lieu de faire supprimer la mauvaise version.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}]
    document["lots"] = [{
        "lot_id": "plan-04_25", "rush_id": "plan-04",
        "frames_dir": "extract-frames/plan-04_25",
        "encoded_masters": [
            {"path": "outputs/plan-04_25_mmu_prores_hq.mov",
             "profile_id": "prores_hq"},
            {"path": "outputs/plan-04_25_mmu_prores_hq_v2.mov",
             "profile_id": "prores_hq", "version_rank": 2},
            {"path": "outputs/plan-04_25_mmu_dnxhr_hqx.mov",
             "profile_id": "dnxhr_hqx"}]}]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (("extract-frames/plan-04_25/f0.tiff", 11),
                            ("outputs/plan-04_25_mmu_prores_hq.mov", 101),
                            ("outputs/plan-04_25_mmu_prores_hq_v2.mov", 202),
                            ("outputs/plan-04_25_mmu_dnxhr_hqx.mov", 303)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)

    lot = inventorier_le_projet(chemin).rushes[0].enfants[0]
    masters = [e for e in lot.enfants if e.nature == NATURE_MASTER]
    # TROIS masters, deux profils, deux rangs : aucune valeur uniforme, et la
    # version visee n'est ni la premiere ni la derniere de la liste.
    assert len(masters) == 3
    for master in masters:
        lu = ps.profil_du_master(master.nom, lot.nom)
        assert lu is not None, master.nom
        assert lu.rang == master.rang, master.nom


def test_la_cible_d_un_MASTER_porte_le_profil_et_le_rang(tmp_path):
    """`EPIC11-ARB-224` : on designe un objet par les arguments qui l'ont produit.

    La cible fine porte le `lot_id` en CONTEXTE, `master=True`, le `profile=`
    d'`encode`, et `version=` seulement au-dela du rang d'origine -- son
    absence designe le rang 1 (`EPIC11-ARB-88`), donc le transmettre a 1 dirait
    deux fois la meme chose.
    """
    origine = _noeud(NATURE_MASTER, "plan-04_25_mmu_prores_hq.mov", rang=1)
    assert ps.cible_du_noeud(origine, "plan-04_25") == {
        "lot_id": "plan-04_25", "master": True, "profile": "prores_hq"}
    version = _noeud(NATURE_MASTER, "plan-04_25_mmu_prores_hq_v2.mov", rang=2)
    assert ps.cible_du_noeud(version, "plan-04_25") == {
        "lot_id": "plan-04_25", "master": True, "profile": "prores_hq",
        "version": 2}
    illisible = _noeud(NATURE_MASTER, "renomme-a-la-main.mov", rang=1)
    assert ps.cible_du_noeud(illisible, "plan-04_25") is None


def test_supprimer_un_MASTER_de_bout_en_bout_n_emporte_QUE_LUI(tmp_path):
    """Le volet de bout en bout de la demande d'Egan, contre le VRAI coeur.

    Trois masters, deux profils, deux rangs, et des octets tous differents. Le
    master vise est **au milieu** -- un `find` fautif qui rendrait le premier
    ne se demasque pas autrement (mutant `M25` de la 5.7) --, et les deux
    bords sont assertes intacts : une suppression qui deborderait sur ses
    voisins ne se voit pas sur l'objet vise.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}]
    document["lots"] = [{
        "lot_id": "plan-04_25", "rush_id": "plan-04",
        "frames_dir": "extract-frames/plan-04_25",
        "encoded_masters": [
            {"path": "outputs/plan-04_25_mmu_prores_hq.mov",
             "profile_id": "prores_hq"},
            {"path": "outputs/plan-04_25_mmu_prores_hq_v2.mov",
             "profile_id": "prores_hq", "version_rank": 2},
            {"path": "outputs/plan-04_25_mmu_dnxhr_hqx.mov",
             "profile_id": "dnxhr_hqx"}]}]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (("extract-frames/plan-04_25/f0.tiff", 11),
                            ("outputs/plan-04_25_mmu_prores_hq.mov", 101),
                            ("outputs/plan-04_25_mmu_prores_hq_v2.mov", 202),
                            ("outputs/plan-04_25_mmu_dnxhr_hqx.mov", 303)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)

    lot = inventorier_le_projet(chemin).rushes[0].enfants[0]
    vise = next(e for e in lot.enfants
                if e.nom == "plan-04_25_mmu_prores_hq_v2.mov")
    noeud = pi._objet_affiche(vise, pi.PROFONDEUR_OBJET)
    cible = ps.cible_du_noeud(noeud, lot.nom)
    assert cible == {"lot_id": "plan-04_25", "master": True,
                     "profile": "prores_hq", "version": 2}

    avant = _empreinte(chemin)
    plan = ps.preparer_la_suppression(chemin, cible, vise.nom)
    # Le poids MESURE est celui du seul master vise, pas celui du lot.
    assert plan.poids == 202
    assert _empreinte(chemin) == avant, "le dry-run a ecrit"

    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    rapport = ps.executer_la_suppression(plan, issue)
    assert rapport.supprime is True
    apres = _empreinte(chemin)
    assert set(avant) - set(apres) == {
        "outputs/plan-04_25_mmu_prores_hq_v2.mov"}
    assert "outputs/plan-04_25_mmu_prores_hq.mov" in apres
    assert "outputs/plan-04_25_mmu_dnxhr_hqx.mov" in apres


def test_quand_le_NOM_et_le_MANIFESTE_divergent_le_COEUR_arbitre_et_REFUSE(
        tmp_path):
    """La mesure qui manquait, et c'est elle qui rend la lecture du nom sure.

    **Le coeur n'apparie pas les masters par leur nom de fichier.** Mesure du
    2026-09-05, sur `project_maintenance` : il filtre les entrees de
    `encoded_masters` sur le champ `profile_id`, puis sur `version_rank`, tous
    deux **au manifeste**. Le nom du fichier n'entre nulle part dans cet
    appariement.

    Consequence, et c'est le cas destructeur : un master RENOMME a la main
    porterait dans son nom un profil ou un rang que le manifeste dementirait.
    Si l'ecran envoyait cette lecture sans filet, le coeur supprimerait
    **l'entree qui correspond a ces mots-cles-la**, c'est-a-dire un AUTRE
    master -- et sans rien lever, puisque les mots-cles sont valides.

    Ce que ce test etablit : le coeur **refuse** au lieu de choisir, et le
    parcours montre ce refus. Aucun fichier ne bouge. C'est la garantie qui
    permet a `profil_du_master` de lire le nom sans etre une devinette
    dangereuse -- elle propose, le manifeste dispose.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "plan-04"}]
    document["lots"] = [{
        "lot_id": "plan-04_25", "rush_id": "plan-04",
        "frames_dir": "extract-frames/plan-04_25",
        # Le manifeste dit rang 1 ; le NOM dit `_v2`. Ils divergent.
        "encoded_masters": [{"path": "outputs/plan-04_25_mmu_prores_hq_v2.mov",
                             "profile_id": "prores_hq"}]}]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (("extract-frames/plan-04_25/f0.tiff", 11),
                            ("outputs/plan-04_25_mmu_prores_hq_v2.mov", 202)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)

    avant = _empreinte(chemin)
    lu = ps.profil_du_master("plan-04_25_mmu_prores_hq_v2.mov", "plan-04_25")
    assert lu.rang == 2, "le NOM dit bien 2"
    with pytest.raises(ProjectMaintenanceError):
        ps.preparer_la_suppression(
            chemin, {"lot_id": "plan-04_25", "master": True,
                     "profile": "prores_hq", "version": 2}, "le master")
    assert _empreinte(chemin) == avant, "un refus a quand meme ecrit"


def test_le_refus_du_coeur_MONTE_un_ecran_de_REFUS_et_pas_un_PAS_ENCORE(
        tmp_path, banc):
    """`EPIC11-ARB-260` : un refus de DOMAINE n'est pas un ecran qui manque.

    **Ce que ce test affirmait avant le 2026-09-06, garde plutot qu'efface** :
    « `isinstance(descendus[-1], EcranPasEncore)` ». C'etait le mur qu'Egan a
    rencontre -- un refus legitime, motive et definitif s'affichait sous le
    titre « Cet ecran n'existe pas encore » avec une echeance qui n'arrivera
    jamais. Les deux volets sont mesures parce que c'est leur DIFFERENCE qui
    compte : le refus est bien monte, et il ne l'est **pas** sous l'ecran de
    manque.

    Le message du coeur reste **transporte** et non remplace par une phrase
    generique (`EPIC11-ARB-30`) : c'est lui qui nomme les profils reellement
    declares, donc c'est lui qui permet de comprendre. Ce qui s'ajoute est le
    CODE, derive du nom de la classe levee -- le seul obstacle que le registre
    des filets nommait a ce routage.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    noeud = _noeud(NATURE_MASTER, "plan-04_25_mmu_prores_hq.mov")
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())
    app = _app(temoin)

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        rendu = ps.ouvrir_la_suppression(temoin, noeud, projet=chemin,
                                         lot_id="plan-04_25")
        return rendu, pilote.app.descendus

    rendu, descendus = _monte(app, scenario, banc)
    assert rendu is True
    assert descendus and isinstance(descendus[-1], EcranRefus)
    assert not isinstance(descendus[-1], EcranPasEncore)
    assert descendus[-1].code == "PROJECT_MAINTENANCE_ERROR"
    # Le message est celui du COEUR, mot pour mot : une sur-chaine exacte, la
    # meme mesure que `refus_de_l_inventaire` (`EPIC11-ARB-30`).
    with pytest.raises(ProjectMaintenanceError) as leve:
        ps.preparer_la_suppression(
            chemin, ps.cible_du_noeud(noeud, "plan-04_25"), "le master")
    assert descendus[-1].message == str(leve.value)


async def _attendre_l_ecriture(pilote):
    """Attendre le fil de `suite_de_la_suppression`, sans mesurer l'attente.

    Depuis le 2026-09-06 l'ecriture part au FIL, derriere un rendez-vous de
    dessin : le compte rendu n'est donc plus empile quand la fonction rend la
    main. Un banc qui asserterait dans la foulee mesurerait une course, et il
    la mesurerait differemment selon la charge de la machine.

    **On attend le DRAPEAU, pas l'ouvrier**, et la premiere redaction de ce
    helper attendait l'ouvrier : elle rougissait avec « aucun ouvrier
    `projet-suppression` » sur une ecriture qui avait pourtant abouti. Motif
    mesure : `textual` retire un ouvrier fini de `app.workers`, et le double
    de coeur de ce banc rend en quelques microsecondes -- l'ouvrier naissait
    et mourait entre deux `pause`, si bien que le sondage ne le voyait
    jamais. Un banc qui attend un objet transitoire mesure la vitesse du
    double.

    `tache_en_cours` n'a pas ce defaut : le produit le pose AVANT le fil et
    ne l'eteint que dans `conclure`, donc il est vrai pendant toute
    l'ecriture et faux apres -- c'est un etat, pas un evenement.
    """
    assert pilote.app.tache_en_cours, (
        "le drapeau n'est pas pose : l'ecriture n'est pas partie au fil,"
        " ou elle a ete appelee synchroniquement")
    for _ in range(60):
        await pilote.pause()
        if not pilote.app.tache_en_cours:
            break
    assert not pilote.app.tache_en_cours, (
        "l'ecriture ne finit pas, ou elle laisse le drapeau allume --"
        " l'atelier serait mort pour la session")
    await pilote.pause()


def _capture(app):
    """Remplacer `descendre` par un enregistreur, sans monter les ecrans.

    Monter reellement l'ecran suivant ferait mesurer `EcranPasEncore` et non le
    fait qu'on y descend ; et une descente reelle dans un banc de 24 lignes
    changerait la geometrie sous le test.
    """
    app.descendus = []
    return app.descendus.append


#: La nature de SYNTHESE des deux tests ci-dessous. Elle n'existe dans aucun
#: inventaire : c'est exactement ce qu'on veut mesurer, puisque
#: `NATURES_SANS_CIBLE_FINE` est VIDE depuis le 2026-09-07 et qu'aucune nature
#: livree n'atteint plus ce chemin. Le mecanisme, lui, doit rester mesure --
#: sinon la prochaine nature sans cible fine tomberait sur un mur.
_NATURE_INVENTEE = "nature_que_le_coeur_ne_vise_pas"
_LIBELLE_INVENTE = "objet d'une nature inventee"


def test_toute_nature_de_la_TABLE_mene_a_un_ecran_qui_la_NOMME(
        tmp_path, banc, monkeypatch):
    """Le mecanisme du filet, mesure sur une nature de SYNTHESE.

    **Supprimer le lot entier a la place serait pire qu'un refus** : c'est une
    destruction PLUS LARGE que celle demandee. L'issue est donc un ecran qui
    nomme ce qui manque, et le volet negatif du test le dit -- aucun appel au
    coeur n'a lieu.

    **Ce test portait sur `frames_extraites`, et il n'y porte plus** : le coeur
    a gagne la cible le 2026-09-07 (retour de terrain d'Egan du 2026-09-06),
    la nature est sortie de la table, et le volet symetrique ci-dessous mesure
    qu'elle atteint desormais le coeur. Le mecanisme reste cable pour la
    prochaine nature sans cible fine, et c'est ce que la table -- devenue le
    seul chemin vers ce filet -- fait varier ici dans les deux sens : peuplee
    ici, vide dans `test_la_TABLE_des_natures_sans_cible_fine_est_VIDE`.
    """
    appels = []
    monkeypatch.setitem(ps.NATURES_SANS_CIBLE_FINE, _NATURE_INVENTEE,
                        _LIBELLE_INVENTE)
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    noeud = _noeud(_NATURE_INVENTEE, "plan-04_25")
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        rendu = ps.ouvrir_la_suppression(
            temoin, noeud, projet=chemin, lot_id="plan-04_25",
            retirer_du_projet=lambda *a, **k: appels.append(k))
        return rendu, pilote.app.descendus

    rendu, descendus = _monte(_app(temoin), scenario, banc)
    assert rendu is True
    assert appels == [], "le coeur a ete appele sur une nature sans cible"
    assert isinstance(descendus[-1], EcranPasEncore)
    assert _LIBELLE_INVENTE in str(descendus[-1].ce_qui_manque)


def test_la_TABLE_des_natures_sans_cible_fine_est_VIDE():
    """La frontiere soeur que le registre des filets NOMME (`mesuree_par`).

    L'entree `ouvrir_la_suppression(CE_QUI_MANQUE_A_LA_CIBLE_FINE...)` du
    registre est passee en `hors-produit:cle` le 2026-09-07 : le site vit dans
    `src/` mais aucune nature LIVREE ne l'atteint plus. Cette revendication ne
    vaut que si quelque chose la mesure, et c'est ici.

    Frontiere NEGATIVE des deux cotes : une nature remise dans la table sans
    que sa cible fine manque REELLEMENT ferait rougir, et la table qui se
    repeuple sans motif aussi.
    """
    assert ps.NATURES_SANS_CIBLE_FINE == {}, (
        "une nature a ete remise dans la table : le filet redevient "
        "`atteignable:absence` et son entree au registre doit repasser dans "
        "cette famille, avec un temoin si l'absence porte un nom")


def test_les_frames_extraites_atteignent_desormais_le_COEUR(tmp_path, banc):
    """Le volet symetrique : ce que le retour de terrain d'Egan a ferme.

    « On ne peut pas retirer d'un projet un jeu de frames extraites sans
    emporter autre chose » (2026-09-06). La cible existe depuis le 2026-09-07,
    et le drapeau est NU -- aucun `version=` ne l'accompagne, le dossier de
    frames extraites portant le rang du LOT et non le sien.
    """
    appels = []
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    noeud = _noeud(NATURE_FRAMES_EXTRAITES, "plan-04_25", rang=2)
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    cible = ps.cible_du_noeud(noeud, "plan-04_25")
    assert cible == {"lot_id": "plan-04_25", "frames_extraites": True}, cible
    assert "version" not in cible, (
        "le rang lu de l'arbre designerait le dossier d'un AUTRE lot")

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(
            temoin, noeud, projet=chemin, lot_id="plan-04_25",
            retirer_du_projet=lambda *a, **k: appels.append(k) or _rapport_vide())
        return pilote.app.descendus

    descendus = _monte(_app(temoin), scenario, banc)
    assert not any(isinstance(e, EcranPasEncore) for e in descendus), (
        "« Cet ecran n'existe pas encore » sur une cible que le coeur vise")
    assert appels and appels[0].get("frames_extraites") is True, appels


def _rapport_vide():
    """Le rapport minimal qu'un double de coeur doit rendre pour que l'ecran
    de confirmation se monte -- il en lit le cardinal et les chemins."""
    from mixed_media_utility.project_maintenance import RapportSuppression

    return RapportSuppression(
        cible="plan-04_25 (frames extraites)", fichiers_a_supprimer=(),
        dry_run=True, rang_independant=False)


# ---------------------------------------------------------------------------
# Le cablage : la filiation est LUE de l'arbre, jamais decoupee d'un nom
# ---------------------------------------------------------------------------


def _arbre_a_quatre_niveaux(tmp_path):
    """Un arbre REEL a quatre niveaux : rushe, lot, scan, lot scanne.

    `EPIC11-ARB-210` : l'arbre descend jusqu'a l'objet. La profondeur est ce
    qui rend `lot_ancetre` faillible -- un balayage qui rendrait le PREMIER lot
    rencontre serait juste par accident sur trois niveaux et faux sur quatre.

    Deux rushes et **deux lots par rushe**, tous distinguables : une fabrique a
    un seul lot rendrait invisible un `find` fautif.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "z-dernier"}]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25"},
        {"lot_id": "a-premier_12p5", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_12p5",
         "encoded_masters": [
             {"path": "outputs/a-premier_12p5_mmu_prores_hq.mov",
              "profile_id": "prores_hq"}]},
        {"lot_id": "z-dernier_8", "rush_id": "z-dernier",
         "frames_dir": "extract-frames/z-dernier_8",
         "output_frames_dir": "frames-scannees/z-dernier_8"},
    ]
    (chemin / "project.json").write_text(json.dumps(document),
                                         encoding="utf-8")
    for relatif, octets in (
            ("extract-frames/a-premier_25/f0.tiff", 11),
            ("extract-frames/a-premier_12p5/f0.tiff", 101),
            ("outputs/a-premier_12p5_mmu_prores_hq.mov", 4004),
            ("extract-frames/z-dernier_8/f0.tiff", 33),
            ("frames-scannees/z-dernier_8/s0.tiff", 55)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin, pi.ArbreDuProjet.depuis_l_inventaire(
        inventorier_le_projet(chemin))


def test_le_lot_ANCETRE_est_le_plus_PROCHE_et_pas_le_premier_rencontre(
        tmp_path):
    """La filiation est LUE de l'arbre, jamais decoupee d'un nom d'objet.

    Retrouver `a-premier_12p5` en decoupant
    `a-premier_12p5_mmu_prores_hq.mov` marcherait sur cet exemple et casserait
    des que le `lot_id` serait condense par `derive_short_id`. L'arbre porte la
    filiation, donc c'est lui qu'on lit.

    Les cibles sont posees au MILIEU (le second lot du premier rushe) et en
    QUEUE (le lot scanne du dernier rushe) : un balayage qui rendrait le
    premier lot croise passerait un test pose sur le premier.
    """
    _chemin, arbre = _arbre_a_quatre_niveaux(tmp_path)
    for noeud in arbre.tous():
        noeud.deplie = True

    tous = list(arbre.tous())
    master = next(n for n in tous if n.nature == NATURE_MASTER
                  and not n.groupe)
    assert ps.lot_ancetre(arbre, master) == "a-premier_12p5"
    lot_scanne = next(n for n in tous if n.nature == NATURE_LOT_SCANNE
                      and not n.groupe)
    assert ps.lot_ancetre(arbre, lot_scanne) == "z-dernier_8"
    # Un LOT n'est pas son propre contexte : `lot_id=X` sur X viserait un objet
    # DANS X, pas X lui-meme.
    lot = next(n for n in tous if n.nature == NATURE_LOT and not n.groupe)
    assert ps.lot_ancetre(arbre, lot) is None
    # Un rushe non plus, et un noeud etranger a l'arbre rend `None` plutot que
    # le dernier lot visite.
    rush = next(n for n in tous if n.nature == NATURE_RUSH)
    assert ps.lot_ancetre(arbre, rush) is None
    assert ps.lot_ancetre(arbre, _noeud(NATURE_MASTER, "etranger.mov")) is None


def test_le_cablage_de_Suppr_MONTE_la_confirmation_sur_le_bon_lot(tmp_path,
                                                                  banc):
    """De `Suppr` dans l'inventaire jusqu'au point de jugement, sans raccourci.

    C'est le test de COUTURE que la retrospective de l'Epic 7 instruit : deux
    cotes corrects, testes isolement, et aucun test capable de constater
    l'appel manquant entre eux. Ici l'appel est constate -- l'inventaire monte
    bien une confirmation, et cette confirmation porte la cible du lot juste.
    """
    chemin, arbre = _arbre_a_quatre_niveaux(tmp_path)
    for noeud in arbre.tous():
        noeud.deplie = True
    master = next(n for n in arbre.tous() if n.nature == NATURE_MASTER
                  and not n.groupe)
    arbre.viser(master.nom)
    inventaire = pi.EcranInventaireDuProjet(arbre)
    inventaire._supprimer = ps.cabler_la_suppression(inventaire, arbre, chemin)
    avant = _empreinte(chemin)

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        inventaire.traiter("delete")
        return pilote.app.descendus

    descendus = _monte(_app(inventaire), scenario, banc)
    assert descendus, "Suppr n'a rien monte"
    confirmation = descendus[-1]
    assert isinstance(confirmation, ps.EcranSuppressionConfirmation)
    assert confirmation.plan.cible == {
        "lot_id": "a-premier_12p5", "master": True, "profile": "prores_hq"}
    assert _empreinte(chemin) == avant, "monter la confirmation a ecrit"


def test_l_issue_qui_n_ECRIT_PAS_remonte_et_n_appelle_RIEN(tmp_path, banc):
    """`sur_issue` n'est pas un cul-de-sac (finding `K3`), et `Annuler` remonte.

    Le volet negatif est le point : un `suite_de_la_suppression` qui appellerait
    le coeur avant de regarder `issue.ecrit` supprimerait sur `Annuler`, et le
    test de remontee resterait vert.
    """
    appels = []
    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_ANNULER)
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda i: None)

    async def scenario(pilote):
        remontees = []
        pilote.app.action_remonter = lambda: remontees.append(True)
        ecrit = ps.suite_de_la_suppression(
            ecran, plan, issue,
            retirer_du_projet=lambda *a, **k: appels.append(k))
        return ecrit, remontees

    ecrit, remontees = _monte(_app(ecran), scenario, banc)
    assert ecrit is False
    assert appels == []
    assert remontees == [True]


def test_une_suppression_COMPLETE_remonte_et_ne_dessine_AUCUN_ecran_de_succes(
        banc):
    """`E6-3b` monte, et il CONFIRME le poids libere (AC 4.2, volet reussite).

    **Ce test disait l'inverse jusqu'au 2026-09-05**, et il avait raison de le
    dire : aucune maquette ne dessinait la reussite, donc `EPIC11-ARB-144`
    interdisait de la coder et le parcours remontait a l'inventaire. Egan a
    tranche -- « Maquette a dessiner depuis le meme modele que les autres
    ecrans de reussite » --, la maquette existe (`E6-3b`), et le comportement
    change avec elle. L'ancien enonce n'est pas efface en silence : il est ici,
    dans cette phrase.

    Ce que ce test mesure maintenant, et qui ne se lit nulle part ailleurs : le
    poids libere n'etait annonce par AUCUN ecran une fois l'ecriture faite. La
    confirmation ne peut que le promettre.

    Le volet symetrique est le test suivant : quand il RESTE quelque chose,
    c'est `E6-3` qui monte. Les deux ensemble sont ce qui empeche « on monte
    toujours la reussite » et « on montre toujours E6-3 » de passer.
    """
    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda i: None)

    async def scenario(pilote):
        remontees = []
        pilote.app.action_remonter = lambda: remontees.append(True)
        pilote.app.descendre = _capture(pilote.app)
        ecrit = ps.suite_de_la_suppression(
            ecran, plan, issue,
            retirer_du_projet=lambda *a, **k: _rapport(
                dry_run=False, supprime=True))
        await _attendre_l_ecriture(pilote)
        return ecrit, remontees, pilote.app.descendus

    ecrit, remontees, descendus = _monte(_app(ecran), scenario, banc)
    assert ecrit is True
    # On ne remonte PAS : on descend sur le compte rendu de reussite.
    assert remontees == []
    # **DEUX ecrans depuis le 2026-09-06, et l'ordre est la mesure neuve.**
    # `E6-2c` se monte d'abord -- il etait ecrit, valide et pourtant jamais
    # monte, si bien que l'operateur passait de la confirmation au resultat
    # sans rien voir pendant l'ecriture. Le compte rendu vient PAR-DESSUS lui,
    # comme `E5-5` par-dessus `E5-4`.
    assert [type(e).__name__ for e in descendus] == [
        "EcranSuppressionEnCours", "EcranReussiteDeSuppression"], descendus
    assert isinstance(descendus[-1], ps.EcranReussiteDeSuppression)
    # Et il porte le poids libere, qui est la raison d'etre de cet ecran.
    assert descendus[-1].plan.poids == plan.poids


#: La duree du faux coeur de la mesure de bout en bout ci-dessous. Assez longue
#: pour que la boucle ait plusieurs tours a rendre -- la periode du rotor vaut
#: 0,25 s --, assez courte pour ne pas peser sur la suite.
DUREE_DE_L_ECRITURE_LENTE = 0.6


def test_E6_2c_est_AU_SOMMET_et_son_rotor_TOURNE_pendant_l_ecriture(banc):
    """La mesure de bout en bout : l'ecran de progression **marche**.

    Les autres tests de ce banc mesurent qu'`E6-2c` est *monte* -- c'est-a-dire
    qu'il apparait dans la liste des ecrans empiles. Ce n'est pas la meme chose
    que *marcher*, et la difference est exactement le defaut qu'Egan a signale
    sur les autres ateliers : « on passe de la confirmation au succes sans voir
    la progression, l'interface se fige ».

    Deux mesures, et elles se cassent separement :

    1. **l'ecran est au SOMMET pendant que le coeur travaille**, sur plusieurs
       tours de boucle. Un coeur appele synchroniquement rendrait zero tour --
       la boucle serait occupee du premier au dernier octet, et le compte rendu
       serait deja empile quand elle reprendrait la main ;
    2. **le rotor AVANCE**, c'est-a-dire prend au moins deux valeurs
       distinctes. Un ecran monte dont le rotor est fige est un ecran qui ment :
       le rotor est « le seul signe honnete que la machine travaille », et
       `E6-2c` n'avait aucun minuteur avant le 2026-09-06.

    Le coeur est **lent par construction** ici, et c'est ce qui rend la mesure
    possible : un double qui rend en quelques microsecondes ne laisserait
    aucun tour de boucle a observer, et le test serait vert sans rien mesurer.

    **La fenetre de comptage est celle du COEUR**, delimitee par deux drapeaux
    qu'il pose lui-meme. Compter sur une fenetre ouverte apres le retour de
    `suite_de_la_suppression` laisserait passer un chemin synchrone partout ou
    l'ecran d'ecriture reste au sommet apres coup -- c'est le mutant qui a
    SURVECU sur le banc jumeau de l'atelier Scan avant que sa fenetre soit
    resserree. Les trois bancs de bout en bout du depot mesurent donc la meme
    chose de la meme facon.
    """
    import threading
    import time

    demarre, fini = threading.Event(), threading.Event()
    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda i: None)

    def coeur_lent(*args, **kwargs):
        demarre.set()
        time.sleep(DUREE_DE_L_ECRITURE_LENTE)
        fini.set()
        return _rapport(dry_run=False, supprime=True)

    async def scenario(pilote):
        ps.suite_de_la_suppression(ecran, plan, issue,
                                   retirer_du_projet=coeur_lent)
        tours_au_sommet, pas_vus = 0, []
        debut = time.time()
        while time.time() - debut < DUREE_DE_L_ECRITURE_LENTE + 0.4:
            await pilote.pause()
            if not (demarre.is_set() and not fini.is_set()):
                continue
            sommet = pilote.app.screen
            if isinstance(sommet, ps.EcranSuppressionEnCours):
                tours_au_sommet += 1
                pas_vus.append(sommet.pas_du_rotor)
        return tours_au_sommet, pas_vus, demarre.is_set(), fini.is_set()

    tours, pas_vus, a_demarre, a_fini = _monte(_app(ecran), scenario, banc)
    assert a_demarre and a_fini, (
        f"le coeur n'a pas joue de bout en bout (demarre={a_demarre},"
        f" fini={a_fini}) : le test ne mesure pas ce qu'il annonce")
    assert tours >= 2, (
        f"`E6-2c` n'a ete au sommet que {tours} tour(s) de boucle pendant"
        " l'ecriture : le coeur occupe la boucle, donc rien n'est peint --"
        " c'est le gel exactement")
    assert len(set(pas_vus)) >= 2, (
        f"le rotor n'a pris qu'une valeur ({sorted(set(pas_vus))}) : il est"
        " FIGE. Un ecran de progression dont rien ne bouge est indistinguable"
        " d'une interface bloquee")


def test_une_panne_du_COEUR_de_suppression_n_ATTACHE_PAS_l_atelier(banc):
    """La porte de l'exception sur le chemin neuf, et elle ferme un survivant.

    **Le mutant « la suppression avale sa panne » a SURVECU** a toute la suite
    le 2026-09-06 : rien ne mesurait ce chemin. C'est le meme defaut, et le
    meme cout, que sur les deux entrees de l'atelier PDF -- un drapeau reste
    allume rend l'atelier mort pour la session : `Échap` cesse de depiler, `q`
    ne quitte plus, et rien ne les rallume.

    `E6-2c` est un `Palier` : il n'a **pas** le filet d'`on_unmount`
    d'`EcranExecution`, donc personne n'eteindrait le drapeau a la place de ce
    chemin-la.

    Deux mesures, et elles se cassent separement : le drapeau est **eteint**,
    et l'exception **traverse quand meme** -- un `except` qui l'avalerait
    eteindrait le drapeau tout en cachant le bug.
    """
    from textual.worker import WorkerFailed

    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda i: None)

    def coeur_qui_leve(*args, **kwargs):
        raise ZeroDivisionError("panne hors table")

    mesure: dict = {}

    async def scenario(pilote):
        ps.suite_de_la_suppression(ecran, plan, issue,
                                   retirer_du_projet=coeur_qui_leve)
        try:
            for _ in range(60):
                await pilote.pause()
                if not pilote.app.tache_en_cours:
                    break
        finally:
            # Lu AVANT le demontage : ici rien ne l'eteindrait apres coup,
            # mais le geste reste celui des bancs jumeaux -- une mesure prise
            # apres `banc` mesurerait le demontage.
            mesure["tache"] = pilote.app.tache_en_cours

    leve = None
    try:
        _monte(_app(ecran), scenario, banc)
    except WorkerFailed as emballee:
        leve = emballee.error
    except ZeroDivisionError as nue:
        leve = nue
    assert isinstance(leve, ZeroDivisionError), (
        f"la panne n'a pas traverse ({leve!r}) : soit le double ne leve plus,"
        " soit le produit l'avale -- et dans les deux cas ce test ne mesure"
        " plus rien")
    assert mesure["tache"] is False, (
        "le drapeau est reste allume sur le chemin d'exception : l'atelier est"
        " mort pour la session")


def test_le_minuteur_du_rotor_S_ARRETE_au_demontage_de_E6_2c(banc):
    """Un minuteur qui survit a son ecran redessine un arbre detruit.

    **Il ferme un survivant de campagne** : le mutant qui vide `on_unmount` a
    SURVECU le 2026-09-06. Le banc mesurait que le rotor TOURNE, jamais qu'il
    s'ARRETE -- c'est la moitie symetrique, et c'est celle qui fuit.

    La garde fait varier l'etat dont elle depend, dans les deux sens : le
    minuteur existe une fois monte, et il est rendu une fois demonte. Mesurer
    le seul second etat laisserait passer un `on_mount` qui n'en pose aucun.
    """
    plan = _plan_de_synthese()
    ecran = ps.EcranSuppressionEnCours(plan)
    mesure: dict = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        mesure["monte"] = ecran.minuteur
        pilote.app.pop_screen()
        await pilote.pause()
        mesure["demonte"] = ecran.minuteur

    _monte(_app(ps.EcranSuppressionConfirmation(
        plan, sur_issue=lambda i: None)), scenario, banc)
    assert mesure["monte"] is not None, (
        "aucun minuteur au montage : le rotor ne peut pas tourner, et le"
        " volet symetrique de ce test serait vert pour la mauvaise raison")
    assert mesure["demonte"] is None, (
        "le minuteur survit au demontage : il continue d'appeler"
        " `avancer_le_rotor` sur un ecran detruit")


def test_une_suppression_INCOMPLETE_monte_E6_3_qui_NOMME_les_restes(banc):
    """AC 4.2, par le chemin du parcours et non par un appel direct au rendu.

    Sans ce volet, un parcours qui remonterait TOUJOURS ferait disparaitre la
    fuite de l'ecran : le rapport la porterait, et personne ne la verrait.
    """
    plan = _plan_de_synthese()
    issue = ps.issues_de_la_suppression(plan).issue(ps.CLE_SUPPRIMER)
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda i: None)
    restes = ("a/f0.tiff", "c/s0.tiff")

    async def scenario(pilote):
        remontees = []
        pilote.app.action_remonter = lambda: remontees.append(True)
        pilote.app.descendre = _capture(pilote.app)
        ps.suite_de_la_suppression(
            ecran, plan, issue,
            retirer_du_projet=lambda *a, **k: _rapport(
                dry_run=False, supprime=False, fichiers_non_supprimes=restes))
        return remontees, pilote.app.descendus

    remontees, descendus = _monte(_app(ecran), scenario, banc)
    assert remontees == []
    assert descendus and isinstance(descendus[-1],
                                    ps.EcranResultatDeSuppression)
    assert descendus[-1].rapport.fichiers_non_supprimes == restes


# ---------------------------------------------------------------------------
# `E6-2c` et la grille : AC 5.3, et les deux regimes
# ---------------------------------------------------------------------------


def test_E6_2c_montre_un_ROTOR_et_AUCUNE_barre(banc):
    """Le coeur ne publie aucun canal de progression -- mesure sur sa signature.

    Une barre chiffree exigerait un total et un compte, donc elle serait
    fabriquee ici : « un champ non mesure est omis, jamais rendu faux ». La
    maquette valide exactement ca -- `E6-2c` dessine un rotor et aucune barre.

    La frontiere porte sur la SIGNATURE du coeur : elle rougira le jour ou un
    canal apparaitra, ce qui est precisement le jour ou cet ecran devra en
    porter un.
    """
    import inspect
    parametres = set(inspect.signature(remove_project_element).parameters)
    assert not ({"emetteur", "progression", "sur_jalon", "callback"}
                & parametres)

    plan = _plan_de_synthese()
    ecran = ps.EcranSuppressionEnCours(plan)

    async def scenario(pilote):
        ecran.rafraichir()
        return ecran.lignes(), ecran.etat(), ecran.objet_du_bandeau()

    lignes, etat, bandeau = _monte(_app(ecran), scenario, banc)
    texte = "\n".join(lignes)
    # **La PHASE du rotor n'est pas mesurable, seule sa PRESENCE l'est**
    # (2026-09-07). Ce banc posait `jetons.ROTOR[0]`, c'est-a-dire la premiere
    # image : il supposait qu'entre le montage et la lecture, le rotor avait
    # tourne un nombre connu de fois. Sous `-n 4` sur une machine chargee, il
    # en tourne un de plus et le banc rend `◓` la ou il attendait `◐` --
    # un rouge qui ne dit rien du produit. Ce que la maquette `E6-2c` promet
    # est qu'un rotor est DESSINE, jamais qu'il est arrete sur une image.
    #
    # L'exigence reste etroite dans les deux sens : au moins un glyphe du
    # rotor, et **un seul** -- deux glyphes differents diraient deux rotors ou
    # un rendu bave, et c'est un vrai defaut que cette ligne continue
    # d'attraper.
    assert jetons.ROTOR, "le rotor est vide : ce banc ne mesurerait rien"
    vus = {glyphe for glyphe in jetons.ROTOR if glyphe in texte}
    assert len(vus) == 1, (
        f"un seul glyphe de rotor est attendu a l'ecran, vus : {sorted(vus)}")
    assert ps.TITRE_EN_COURS in texte
    assert plan.libelle in texte
    assert ps.PHRASE_ECRITURE_EN_COURS in etat
    assert ps.MOT_DE_LA_SUPPRESSION in bandeau
    # Aucun glyphe de barre : `E6-2c` n'en dessine pas, et une barre inventee
    # annoncerait une avance que rien ne mesure.
    assert jetons.GLYPHES["barre-pleine"] not in texte


def test_E6_2c_n_annonce_QUE_F1_et_AUCUNE_touche_n_agit():
    """Le symetrique du finding `I8`, pris par les deux bouts.

    `E6-2c` n'annonce aucune interruption -- et pour cause : interrompre une
    suppression a mi-course laisserait un manifeste a jour et des fichiers sur
    le disque, la fuite exacte de l'AC 4.2. Ce que la ligne ne dit pas, aucune
    touche ne le fait.
    """
    ecran = ps.EcranSuppressionEnCours(_plan_de_synthese())
    assert ps.RACCOURCIS_EN_COURS == "F1 aide"
    for touche in ("up", "down", "enter", "escape", "tab", "delete", "space",
                   "q", "ctrl+c"):
        assert ecran.traiter(touche) is False, touche


def test_la_zone_centrale_de_E6_2c_TIENT_sa_hauteur(banc):
    """`textual` coupe par le bas, en silence -- et `Composition` le ferme.

    La zone est epelee ligne a ligne : un cardinal seul survivrait a une
    respiration de trop compensee par une ligne de moins.
    """
    ecran = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        return ecran.composer(80, False)

    lignes = _monte(_app(ecran), scenario, banc)
    assert len(lignes) == jetons.hauteur_centrale()
    assert lignes[1].strip() == ps.TITRE_EN_COURS
    # Meme correction que sur `test_E6_2c_montre_un_ROTOR_et_AUCUNE_barre`, et
    # meme motif : la PHASE du rotor depend du nombre de tours ecoules entre le
    # montage et la lecture, donc de la charge de la machine. Ce qui est
    # mesurable est qu'un glyphe de rotor -- **un seul** -- occupe cette
    # ligne-la.
    assert len({glyphe for glyphe in jetons.ROTOR
                if glyphe in lignes[3]}) == 1, lignes[3]
    # Le complement est en QUEUE : les lignes de contenu ne bougent pas.
    assert all(ligne == "" for ligne in lignes[4:])


@pytest.mark.parametrize("ligne, nom", [
    (ps.RACCOURCIS_CONFIRMATION, "RACCOURCIS_CONFIRMATION"),
    (ps.RACCOURCIS_EN_COURS, "RACCOURCIS_EN_COURS"),
    (ps.RACCOURCIS_RESULTAT, "RACCOURCIS_RESULTAT"),
])
def test_AC_5_3_le_budget_de_colonnes_TIENT_dans_les_DEUX_regimes(ligne, nom):
    """AC 5.3, et le repli ASCII peut **ALLONGER** une ligne.

    `⏎` rend `Entree`, `Échap` rend `Echap` : la ligne repliee n'est pas plus
    courte, elle est souvent plus longue. Mesurer un seul regime laisserait
    passer une ligne qui deborde precisement sur le terminal qui a le moins de
    moyens de le montrer.

    La mesure est en **colonnes**, pas en `len` : `jetons.colonnes` compte la
    double chasse, et un `len` rendrait 44 pour une ligne qui en occupe 60.
    """
    utile = jetons.largeur_utile()
    assert jetons.colonnes(ligne) <= utile, f"{nom} deborde en UTF-8"
    replie = jetons.replier_ascii(ligne)
    assert jetons.colonnes(replie) <= utile, f"{nom} deborde replie"
    assert replie.isascii(), f"{nom} garde du non-ASCII apres repli"


def test_AC_5_3_le_commentaire_de_MESURE_dit_le_VRAI_nombre():
    """Un commentaire de budget faux est pire qu'aucun commentaire.

    Le lot J de la 11.7 a mesure que **cinq des neuf** commentaires de budget
    du paquet etaient faux. Celui-ci est donc confronte a la mesure plutot que
    relu : la source est lue, le `MESURE: <utf8>/<ascii>` est extrait, et les
    deux nombres sont recalcules.

    **Le cardinal est passe de TROIS a QUATRE le 2026-09-06** : la quatrieme
    ligne mesuree n'est pas une ligne de raccourcis mais
    `PHRASE_DES_LOTS_D_ABORD`, l'issue nommee d'`EPIC11-ARB-260`. Elle est
    portee ici pour la meme raison que les trois autres -- elle est la seule
    ligne de l'ecran de refus a ne pas venir du coeur, donc la seule dont le
    budget soit a nous.
    """
    import re
    source = MODULE.read_text(encoding="utf-8").splitlines()
    trouves = 0
    for rang, ligne in enumerate(source):
        marque = re.search(r"MESURE:\s*(\d+)/(\d+)", ligne)
        if not marque:
            continue
        declare = (int(marque.group(1)), int(marque.group(2)))
        # **Le nom est lu de la source, la VALEUR du module.** Evaluer le texte
        # qui suit le commentaire echouait sur une constante ecrite sur deux
        # lignes -- et une frontiere qui echoue pour une raison etrangere a ce
        # qu'elle mesure est une frontiere qu'on finit par retirer.
        declaration = next(l for l in source[rang + 1:]
                           if l and not l.startswith("#"))
        nom = declaration.split("=", 1)[0].strip()
        valeur = getattr(ps, nom)
        mesure = (jetons.colonnes(valeur),
                  jetons.colonnes(jetons.replier_ascii(valeur)))
        assert mesure == declare, f"{nom} : declare {declare}, mesure {mesure}"
        trouves += 1
    assert trouves == 4, f"{trouves} lignes mesurees, attendu 4"


def test_le_repli_ASCII_ne_laisse_AUCUN_caractere_non_ASCII(banc):
    """La garde d'epic, appliquee aux quatre rendus de ce module.

    `--ascii` sert un terminal qui ne dessine pas l'UTF-8 : un seul glyphe
    oublie y rend un `?`, et le `?` est indistinguable d'une donnee manquante.
    """
    rapport = _rapport(rangs_liberables=(2,),
                       fichiers_non_supprimes=("a/f.tiff",))
    # **Les deux valeurs de `dernier_lot`, et c'est le finding `C2-4`.** Ce
    # test passait sur la seule valeur `False` que la fabrique pose par
    # defaut, et `PHRASE_DERNIER_LOT` -- la seule ligne du module qui ne
    # passait pas par `_replie` -- ne pouvait donc jamais l'atteindre. Regle
    # des fabriques, point 1, sur un booleen : une fabrique mono-valeur rend
    # invisible tout ce qui depend de l'autre valeur.
    for dernier_lot in (False, True):
        plan = _plan_de_synthese(rapport=rapport, dernier_lot=dernier_lot)
        rendus = [
            "\n".join(ps.panneau_de_la_confirmation(plan, True).rendu(80, True)),
            "\n".join(ps.lignes_des_emportes(plan, True)),
            ps.ligne_d_etat_de_la_confirmation(plan, True),
            "\n".join(ps.lignes_des_restes(plan.rapport, True)),
            ps.ligne_d_etat_du_resultat(plan.rapport, 3, True),
        ]
        for rendu in rendus:
            assert rendu.isascii(), (dernier_lot, repr(rendu))
            # **Et aucun `?` NEUF**, ce que le docstring ci-dessus reclame et
            # qu'`isascii` seul ne dit pas : `replier_ascii` replie TOUT, un
            # glyphe qu'il ignore compris, qu'il rend en `?`. Un rendu ASCII
            # peut donc etre ASCII et illisible.
            assert "?" not in rendu, (dernier_lot, repr(rendu))


def test_aucune_ligne_de_cartouche_ne_DEBORDE_sur_un_nom_a_la_borne(banc):
    """La borne est LUE du code, jamais recopiee.

    `CANONICAL_ID_MAX_LENGTH` a ete citee de memoire et fausse trois fois dans
    ce depot -- 64, puis 48. Elle se lit ici a sa source, et le test fabrique
    un `lot_id` exactement a la borne.
    """
    from mixed_media_utility.io.naming import CANONICAL_ID_MAX_LENGTH

    nom = "L" * CANONICAL_ID_MAX_LENGTH
    plan = _plan_de_synthese(libelle=f"{PREFIXE_DESSINE_DU_LIBELLE}{nom}")
    for ascii_seul in (False, True):
        for ligne in ps.panneau_de_la_confirmation(plan, ascii_seul).rendu(
                80, ascii_seul):
            assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(80), (
                ascii_seul, ligne)


# ---------------------------------------------------------------------------
# Ce que la campagne de mutation du 2026-09-05 a trouve, et qui manquait
# ---------------------------------------------------------------------------


def test_MUTANT_le_prefixe_du_lot_est_verifie_AVANT_de_trancher_le_nom():
    """Mutant `C-profil-prefixe-lot`, survivant de la premiere campagne.

    Le test d'egalite existant passait **par accident** : `autre-lot_mmu_...`
    tronque a la longueur du prefixe de `plan-04_25` rendait `ores_hq`, qui ne
    nomme aucun profil, donc `None` sortait quand meme. La garde etait donc
    verte sans etre mesuree.

    Le cas qui la mesure vraiment : un lot COURT, dont le prefixe tronque un nom
    etranger **exactement** sur un profil valide. Sans la garde, cet appel
    rendrait `prores_hq` pour un fichier qui n'appartient pas au lot -- et le
    coeur supprimerait le master DU LOT VISE, pas celui qu'on regarde.
    """
    lot = "AB"
    prefixe = f"{lot}{naming.MASTER_FILENAME_MARKER}"
    #: Un nom etranger, de meme longueur de tete que le prefixe, dont la coupe
    #: aveugle tomberait pile sur un profil du registre.
    etranger = f"{'Z' * len(prefixe)}prores_hq.mov"
    assert etranger[len(prefixe):] == "prores_hq.mov", "le piege est bien pose"
    assert ps.profil_du_master(etranger, lot) is None
    # Et le volet positif, avec le MEME lot : la garde ne bloque pas le cas juste.
    assert ps.profil_du_master(f"{prefixe}prores_hq.mov", lot).profil == (
        "prores_hq")


def test_MUTANT_le_poids_se_mesure_au_LIEN_et_non_a_sa_CIBLE(tmp_path):
    """Mutant `C-poids-lstat` : `os.stat` a la place d'`os.lstat`.

    Ils ne different que sur un lien symbolique -- et c'est exactement la ou
    la difference compte : supprimer un lien libere la taille du LIEN, pas
    celle du fichier vise. Annoncer « 4 Ko liberes » pour un lien de 20 octets
    est un chiffre faux sur l'ecran qui existe pour dire ce qu'on va perdre.
    """
    (tmp_path / "gros").write_bytes(b"o" * 4004)
    (tmp_path / "lien").symlink_to(tmp_path / "gros")
    mesure = ps.poids_des_fichiers(tmp_path, ("lien",))
    assert mesure == (tmp_path / "lien").lstat().st_size
    assert mesure != 4004, "le poids de la CIBLE est annonce a la place du lien"


@pytest.mark.parametrize("nature, attendu", [
    (NATURE_PLANCHE, {"planche": True}),
    (NATURE_LOT_SCANNE, {"lot_scanne": True}),
    (NATURE_SCAN, {"scan": "plan-04_25_scan"}),
])
def test_MUTANT_CHAQUE_cible_fine_porte_SON_mot_cle_et_pas_un_autre(nature,
                                                                    attendu):
    """Mutants `C-cible-lot-scanne` et `C-cible-scan-tige`, survivants.

    Le banc ne mesurait que les cibles `lot`, `rush` et `master` : echanger le
    mot-cle d'une planche contre celui d'un lot scanne passait inapercu, et
    c'est une suppression qui vise **un autre objet du meme lot**. Les quatre
    cibles fines sont donc mesurees une par une, chacune contre SON mot-cle.

    La table est ecrite en ATTENDU EXACT et non en « contient » : une assertion
    positive laisserait passer un mot-cle supplementaire, qui est precisement
    la forme que prend un echange rate.
    """
    noeud = _noeud(nature, "plan-04_25_scan" if nature == NATURE_SCAN
                   else "objet-quelconque.pdf")
    assert ps.cible_du_noeud(noeud, "plan-04_25") == dict(
        {"lot_id": "plan-04_25"}, **attendu)


def test_MUTANT_le_slug_de_SCAN_est_la_TIGE_pas_le_nom_du_dossier():
    """Mutant `C-cible-scan-tige` : `scan=` prend un slug de FAMILLE.

    « le nom du dossier prive de son fragment `_vN` », verbatim du coeur.
    Passer le nom entier viserait une famille qui n'existe pas -- et le coeur
    refuserait, ce qui est un blocage la ou l'operateur a designe un objet
    reel. Le rang, lui, part separement dans `version=`.
    """
    v2 = _noeud(NATURE_SCAN, "plan-04_25_scan_v2", rang=2)
    assert ps.cible_du_noeud(v2, "plan-04_25") == {
        "lot_id": "plan-04_25", "scan": "plan-04_25_scan", "version": 2}
    origine = _noeud(NATURE_SCAN, "plan-04_25_scan", rang=1)
    assert ps.cible_du_noeud(origine, "plan-04_25") == {
        "lot_id": "plan-04_25", "scan": "plan-04_25_scan"}


# ---------------------------------------------------------------------------
# `E6-3b` -- la suppression REUSSIE, dessinee le 2026-09-05
# ---------------------------------------------------------------------------
#
# **Ce que cette section mesure et qui n'existait pas.** Le chemin nominal
# n'avait aucun ecran : le parcours remontait a l'inventaire sans un mot, si
# bien que le POIDS LIBERE -- la seule chose qu'une suppression produise --
# n'etait annonce nulle part une fois l'ecriture faite. La confirmation ne peut
# que le promettre ; entre les deux, il y a eu une ecriture.


def _reussite(**kwargs):
    """Un rapport de suppression ABOUTIE : rien ne reste."""
    defauts = dict(dry_run=False, supprime=True, fichiers_non_supprimes=())
    defauts.update(kwargs)
    return _rapport(**defauts)


def test_E6_3b_le_cartouche_porte_le_glyphe_PLEIN_et_l_objet_supprime():
    """La tete de `E6-3b`, sur le modele des quatre autres comptes rendus.

    Le glyphe est celui de la completude et non de l'absence : c'est ce qui
    distingue cet ecran de `E6-3` d'un coup d'oeil, avant meme d'avoir lu le
    titre. Le mesurer ici plutot qu'a l'oeil ferme le mode de panne ou les deux
    ecrans se ressembleraient.
    """
    plan = _plan_de_synthese()
    lignes = ps.lignes_de_la_reussite(plan)
    assert lignes[0].startswith(jetons.GLYPHES["complete"])
    assert plan.libelle in lignes[0]
    assert jetons.GLYPHES["absent"] not in lignes[0]
    # Une respiration separe la tete des chiffres, comme la maquette la pose.
    assert lignes[1] == ""


def test_E6_3b_la_ligne_du_RANG_ne_parait_QUE_si_un_rang_a_ETE_rendu():
    """`EPIC11-ARB-92` point 3 : un rang se consomme et ne se rend QUE sur demande.

    Les deux regimes, parce qu'un seul ne mesure rien : une ligne
    inconditionnelle passerait le test « elle est la quand on libere », et
    annoncerait a l'operateur qui a retenu `Supprimer` un rang qu'il n'a pas
    demande. C'est la meme famille de defaut que la ligne d'eau ecrite par
    aucun chemin -- une surface qui retourne l'arbitrage en silence.
    """
    plan = _plan_de_synthese()
    sans = ps.panneau_de_la_reussite(plan, _reussite(rang_libere=False))
    avec = ps.panneau_de_la_reussite(plan, _reussite(rang_libere=True,
                                                     rang_vise=3))
    libelles_sans = [ligne.libelle for ligne in sans.lignes]
    libelles_avec = [ligne.libelle for ligne in avec.lignes]
    assert ps.LIBELLE_RANG_LIBERE not in libelles_sans
    assert ps.LIBELLE_RANG_LIBERE in libelles_avec
    # Et il porte le rang du RAPPORT, jamais un rang recalcule ici.
    ligne = next(l for l in avec.lignes if l.libelle == ps.LIBELLE_RANG_LIBERE)
    assert "v3" in ligne.chiffre


def test_E6_3b_le_panneau_LIT_le_plan_et_ne_remesure_RIEN():
    """Le poids libere est celui que la confirmation a promis, au chiffre pres.

    Le remesurer sur le disque rendrait ZERO -- les fichiers n'y sont plus.
    C'est le piege exact de cet ecran, et il ne se voit qu'ici : sur `E6-3` la
    mesure est juste, parce que ce qui reste existe encore.
    """
    plan = _plan_de_synthese(poids=1_500_000_000, projet=Path("/nulle-part"))
    panneau = ps.panneau_de_la_reussite(plan, _reussite())
    chiffres = " ".join(ligne.chiffre for ligne in panneau.lignes)
    assert ps.poids_lisible(1_500_000_000) in chiffres
    assert "0 o" not in chiffres


@pytest.mark.parametrize("rang_libere, rang_vise, attendu", [
    (False, 1, ps.PHRASE_AUCUN_RESTE),
    (True, 2, RANG_RENDU_DESSINE),
])
def test_E6_3b_la_ligne_d_etat_dit_ce_qui_RESTE_ou_le_rang_rendu(
        rang_libere, rang_vise, attendu):
    """Le volet symetrique de la ligne d'etat de `E6-3`.

    La ou l'ecran incomplet nomme ce qui reste, celui-ci dit qu'il ne reste
    rien. Un compte rendu muet sur ce point laisserait ouverte exactement la
    question que la story existe pour fermer.
    """
    plan = _plan_de_synthese()
    etat = ps.ligne_d_etat_de_la_reussite(
        plan, _reussite(rang_libere=rang_libere, rang_vise=rang_vise))
    assert etat.startswith(jetons.GLYPHES["complete"])
    assert attendu in etat
    assert ps.PHRASE_MANIFESTE_EN_ETAT in etat
    assert ps.poids_lisible(plan.poids) in etat


def test_E6_3b_les_groupes_emportes_sont_TOUS_rendus_TETE_et_QUEUE(banc):
    """Regle des fabriques, point 4 : une cible a CHAQUE bord.

    Un balayage tronque -- qui sauterait le premier ou le dernier groupe --
    reste vert tant que les temoins sont au milieu. Les trois groupes portent
    ici des cardinaux et des poids DIFFERENTS, sans quoi une permutation ne se
    verrait pas non plus.
    """
    plan = _plan_de_synthese(groupes=(
        ps.GroupeEmporte("tete/", 62, 770_000_000),
        ps.GroupeEmporte("milieu.mov", 1, 206_000_000),
        ps.GroupeEmporte("queue/", 4, 550_000_000)))
    ecran = ps.EcranReussiteDeSuppression(plan, _reussite())

    async def scenario(pilote):
        return ecran.lignes()

    texte = "\n".join(_monte(_app(ecran), scenario, banc))
    for marque in ("tete/", "milieu.mov", "queue/"):
        assert marque in texte, marque


def test_E6_3b_le_curseur_designe_une_SUITE_et_JAMAIS_un_groupe(banc):
    """Le rang du curseur est compte sur les lignes RENDUES.

    Un rang herite d'`EcranResultat` ne planterait pas : il colorerait la
    ligne d'un groupe emporte au lieu d'une suite. Une panne qui ne leve pas
    est celle qui survit a la relecture, donc c'est celle qu'on mesure.
    """
    plan = _plan_de_synthese()
    ecran = ps.EcranReussiteDeSuppression(plan, _reussite())
    # DEUX suites : « Ouvrir le dossier du projet » et le retour.
    assert ecran.suites == [ps.SUITE_OUVRIR_PROJET, ps.SUITE_RETOUR]

    async def scenario(pilote):
        rangs = []
        for _ in range(len(ecran.suites)):
            rangs.append((ecran.rang_du_curseur(), ecran.lignes()))
            ecran.curseur += 1
        return rangs

    for rang, lignes in _monte(_app(ecran), scenario, banc):
        assert rang is not None
        designee = lignes[rang]
        assert any(suite in designee for suite in ecran.suites), designee


def test_E6_3b_et_E6_3_s_EXCLUENT_et_la_condition_n_est_ecrite_QU_UNE_fois():
    """Deux comptes rendus qui se croiraient tous deux legitimes en empileraient deux.

    La condition vit en **un seul** endroit et nulle part ailleurs : aucun des
    deux ecrans ne la redige. On le mesure a l'AST plutot qu'a l'oeil -- une
    seconde redaction est precisement ce qui se lit mal.

    **Le porteur a change de nom le 2026-09-06, pas de nature.** Le lot des
    suites de la suppression a deplace la condition de
    `suite_de_la_suppression` vers `monter_le_compte_rendu`, qui construit
    l'ecran **et** pose son rappel de suites -- parce que le reessai a besoin
    du meme montage, et qu'un second site de construction aurait reecrit la
    condition, ce que ce test existe justement pour empecher. La mesure reste
    l'egalite a UN porteur, et c'est elle qui compte.
    """
    source = Path(ps.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    porteurs = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.ClassDef)):
            continue
        corps = ast.get_source_segment(source, noeud) or ""
        if "fichiers_non_supprimes:" in corps or (
                "if rapport.fichiers_non_supprimes" in corps):
            porteurs.append(noeud.name)
    assert porteurs == ["monter_le_compte_rendu"], porteurs


def test_E6_3b_se_replie_en_ASCII_sans_QU_UN_glyphe_echappe(banc):
    """Le repli porte sur TOUTES les lignes, cartouche et groupes compris.

    Le defaut deja paye sur `GroupeEmporte.rendu` : un `—`, un `·` ou le
    glyphe neutre d'un poids echappait a `--ascii` parce que la fonction
    repliait son enveloppe et pas son contenu.
    """
    for dernier_lot in (False, True):
        plan = _plan_de_synthese(dernier_lot=dernier_lot)
        ecran = ps.EcranReussiteDeSuppression(
            plan, _reussite(rang_libere=True, rang_vise=2))

        async def scenario(pilote):
            pilote.app.ascii_seul = True
            return ecran.lignes(), ecran.etat()

        lignes, etat = _monte(_app(ecran, ascii_seul=True), scenario, banc)
        assert lignes, "temoin de vitalite : l'ecran n'a rendu aucune ligne"
        for ligne in lignes + [etat]:
            assert ligne.isascii(), (dernier_lot, ligne)
            assert "?" not in ligne, (dernier_lot, ligne)


# ---------------------------------------------------------------------------
# L'OUVREUR -- le seul chemin par lequel le produit atteint `E6-1`
# ---------------------------------------------------------------------------
#
# **Pourquoi ces tests sont dans CE banc et non dans celui de l'inventaire.**
# L'ouvreur n'ouvre pas seulement un ecran : il CABLE sa suppression. Ce que
# les tests ci-dessous mesurent d'essentiel -- qu'un `Suppr` depuis l'ecran
# ouvert monte `E6-2` et non l'ecran « pas encore » -- est une propriete de ce
# module-ci, et il porte deja le projet reel et les helpers pour la mesurer.


def _ouvre(tmp_path, banc, dossier=None, lire=None, **kwargs):
    """Monter l'ouvreur sur une coque reelle et rendre l'ecran obtenu.

    `lire` est applique a l'ecran **pendant** que l'application est montee, et
    son resultat voyage a cote de l'ecran dans un couple. Ce n'est pas du
    confort : le rendu d'un ecran passe par `self.app` -- `EcranRefus.lignes`
    y lit le jeu de glyphes --, et `self.app` LEVE une fois le gestionnaire de
    contexte referme, ce que le conftest dit deja. Sans lui, une assertion sur
    le texte affiche mesure une exception au lieu d'un ecran.
    """
    chemin = _projet_a_supprimer(tmp_path) if dossier is None else dossier
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin, **kwargs)
        await pilote.pause()
        ecran = pilote.app.screen
        return ecran if lire is None else (ecran, lire(ecran))

    return banc(app, tour), chemin


def test_l_ouvreur_monte_E6_1_sur_le_VRAI_coeur_et_pas_un_ecran_de_manque(
        tmp_path, banc):
    """Le cablage qui manquait : `Gestion des medias` -> `E6-1`, sur disque.

    **La panne que ce test ferme a un nom dans ce depot** : « un composant
    livre, teste, et cable nulle part dans l'application est un composant que
    le produit n'a pas » (lot `E9`, cite par `chaine_du_produit`).
    `EcranInventaireDuProjet` etait exactement dans cet etat -- deux bancs,
    129 tests, et aucun chemin depuis le produit.

    Il passe par le VRAI `inventorier_le_projet` sur un VRAI projet : une
    fabrique d'inventaire mesurerait l'ouvreur contre elle-meme.
    """
    ecran, chemin = _ouvre(tmp_path, banc)

    assert isinstance(ecran, pi.EcranInventaireDuProjet), type(ecran)
    assert not isinstance(ecran, EcranPasEncore)
    # L'arbre est POSE : l'ecran n'est pas en `E6-1a`, il a deja son inventaire.
    assert ecran.en_lecture is False
    assert ecran.arbre is not None
    # Et c'est bien CE projet : les trois rushes de la fabrique, dans l'ordre.
    racines = [noeud.nom for noeud in ecran.arbre.racines]
    assert racines == ["a-premier", "plan-04", "z-dernier"], racines


def test_l_ouvreur_CABLE_la_suppression_et_Suppr_monte_E6_2(tmp_path, banc):
    """La moitie de l'ouvreur qui n'est pas l'ouverture.

    Sans cablage, `Suppr` tombe sur `CE_QUI_MANQUE_A_LA_SUPPRESSION` -- une
    touche annoncee qui dit ce qui manque, ce qui est le bon repli mais pas le
    produit. Ce test vise le lot du MILIEU (`plan-04_12p5`) : une cible en
    premiere position ne demasquerait pas un cablage qui viserait toujours le
    premier noeud.
    """
    chemin = _projet_a_supprimer(tmp_path)
    socle = PalierTemoin("Projet", "q quitter")
    app = CoqueTui(paliers=[socle], contexte=Contexte(projet="projet_demo"))

    async def tour(pilote):
        pi.ouvrir_l_inventaire_du_projet(socle, chemin)
        await pilote.pause()
        inventaire = pilote.app.screen
        # La cible est celle du MILIEU : un cablage qui viserait toujours le
        # premier noeud ne se demasque pas autrement (mutant `M25` de la 5.7).
        inventaire.arbre.viser("plan-04_12p5")
        inventaire.traiter("delete")
        await pilote.pause()
        return inventaire, pilote.app.screen

    inventaire, monte = banc(app, tour)

    assert inventaire._supprimer is not None
    assert isinstance(monte, ps.EcranSuppressionConfirmation), type(monte)
    # Le plan est un APERCU : le coeur a ete appele en `dry_run`, rien n'est
    # ecrit tant que l'issue n'est pas validee.
    assert monte.plan.rapport.dry_run is True
    assert "plan-04_12p5" in monte.plan.libelle, monte.plan.libelle
    # Et le disque est INTACT : ouvrir puis viser ne supprime rien.
    assert (chemin / "extract-frames/plan-04_12p5/f1.tiff").exists()


def test_l_ouvreur_SANS_projet_NOMME_ce_qui_manque_et_ne_bloque_pas(
        tmp_path, banc):
    """`EPIC11-ARB-89` : jamais un blocage sec, jamais une touche muette."""
    ecran, _ = _ouvre(tmp_path, banc, dossier="")

    assert isinstance(ecran, EcranPasEncore), type(ecran)
    assert pi.CE_QUI_MANQUE_SANS_PROJET in "\n".join(ecran.lignes())


def test_l_ouvreur_sur_un_dossier_SANS_manifeste_porte_le_message_du_COEUR(
        tmp_path, banc):
    """Le refus AFFICHE est celui du coeur, jamais une phrase reecrite ici.

    Le distinguo se mesure : une redaction locale resterait verte si le coeur
    changeait son message, et l'utilisateur lirait alors deux verites.
    """
    vide = tmp_path / "pas-un-projet"
    vide.mkdir()
    attendu = ""
    try:
        inventorier_le_projet(vide)
    except Exception as refus:      # noqa: BLE001 -- on veut le message exact
        attendu = str(refus)
    assert attendu, "temoin : le coeur DOIT refuser ce dossier"

    (ecran, lignes), _ = _ouvre(tmp_path, banc, dossier=vide,
                                lire=lambda e: "\n".join(e.lignes()))
    # **`EcranRefus` et non `EcranPasEncore` depuis le 2026-09-06**, en
    # reconciliant les deux ouvreurs du palier Projet : un manifeste qui ne se
    # lit pas n'annonce rien a venir, donc ce n'est pas un « pas encore ». Le
    # refus du coeur se relaie mot pour mot AVEC SON CODE (`EPIC11-ARB-30`),
    # sur un ecran deja valide (`EPIC11-ARB-144`).
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert attendu in lignes


def test_l_ouvreur_sans_application_montee_ne_monte_RIEN_et_le_DIT():
    """Faux plutot qu'une exception : l'appelant sait que rien n'a bouge."""
    class SansApp:
        app = None

    assert pi.ouvrir_l_inventaire_du_projet(SansApp(), "/nulle-part") is False


# ---------------------------------------------------------------------------
# F2 -- la mention d'AFFICHAGE ne part JAMAIS vers le coeur
# ---------------------------------------------------------------------------
#
# Trouve par la couche 1 de la revue, et par elle seule : aucune assertion du
# banc ne portait sur un noeud non declare. Le regime exact est `Suppr` sur un
# objet que le manifeste ignore -- c'est-a-dire sur precisement les objets que
# `E6-1` existe pour rendre visibles.


def _arbre_tout_non_declare():
    """Un arbre dont CHAQUE objet est non declare, deux de chaque nature.

    Regle des fabriques, points 1, 2 et 4 : deux elements distinguables par
    nature, la cible usuelle ailleurs qu'en premiere position, et une cible a
    CHAQUE BORD -- `a-premier` en tete, `z-dernier` en queue. Une fuite qui ne
    mordrait qu'au premier noeud, ou qu'au dernier, ne se demasque pas
    autrement.
    """
    def objet(nature, nom, **kwargs):
        return ObjetInventorie(nature=nature, nom=nom, chemin=None,
                               etat=ETAT_NON_DECLARE, **kwargs)

    def lot(lot_id, rang=1):
        return objet(NATURE_LOT, lot_id, rang=rang, enfants=(
            objet(NATURE_MASTER, f"{lot_id}_mmu_prores_hq.mov"),
            objet(NATURE_MASTER, f"{lot_id}_mmu_dnxhr_hqx.mov"),
            objet(NATURE_PLANCHE, f"demo_{lot_id}_6f-pay.pdf"),
            objet(NATURE_PLANCHE, f"demo_{lot_id}_6f-pay_v2.pdf", rang=2),
            objet(NATURE_SCAN, f"{lot_id}_scan", enfants=(
                objet(NATURE_LOT_SCANNE, lot_id, enfants=(
                    objet(NATURE_FRAMES_SCANNEES, lot_id),)),)),
            objet(NATURE_SCAN, f"{lot_id}_scan_v2", rang=2, enfants=(
                objet(NATURE_LOT_SCANNE, f"{lot_id}_v2", rang=2, enfants=(
                    objet(NATURE_FRAMES_SCANNEES, f"{lot_id}_v2", rang=2),)),)),
            objet(NATURE_FRAMES_EXTRAITES, lot_id),
        ))

    inventaire = InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(objet(NATURE_RUSH, "a-premier", enfants=(lot("a-premier_25"),)),
                objet(NATURE_RUSH, "plan-04", enfants=(lot("plan-04_25"),
                                                       lot("plan-04_25_v2", 2))),
                objet(NATURE_RUSH, "z-dernier", enfants=(lot("z-dernier_8"),))))
    return pi.ArbreDuProjet.depuis_l_inventaire(inventaire)


def _tous_les_noeuds(arbre):
    for racine in arbre.racines:
        yield from racine.parcourir()


def test_AUCUN_mot_cle_envoye_au_COEUR_ne_porte_la_mention_d_AFFICHAGE():
    """La frontiere de `F2`, et elle balaye TOUT l'arbre plutot qu'un cas.

    Un test qui viserait un seul noeud laisserait passer la meme fuite sur une
    nature voisine -- il y en avait QUATRE (`rush_id`, `lot_id`, `scan`, et le
    contexte propage par `lot_ancetre`). Le balayage exhaustif est ce qui
    attrape aussi celle qu'une nature ajoutee demain reintroduirait.
    """
    arbre = _arbre_tout_non_declare()
    vus = 0
    for noeud in _tous_les_noeuds(arbre):
        cible = ps.cible_du_noeud(noeud, ps.lot_ancetre(arbre, noeud))
        if cible is None:
            continue
        vus += 1
        for cle, valeur in cible.items():
            if isinstance(valeur, str):
                assert pi.MENTION_NON_DECLARE not in valeur, (noeud.nom, cle,
                                                              valeur)
                assert "·" not in valeur, (noeud.nom, cle, valeur)
    # Temoin de vitalite : sans lui, un `cible_du_noeud` qui rendrait toujours
    # `None` ferait passer ce test sans rien mesurer.
    assert vus >= 12, vus


def test_un_LOT_non_declare_est_vise_par_son_identifiant_de_COEUR():
    """Le cas nominal de `F2`, chiffre : ce que le coeur recevait, et recoit.

    Avant : `{"lot_id": "plan-04_25_v2 · non declare"}` -- un identifiant qui
    n'existe nulle part, refuse par le coeur, et le seul chemin de suppression
    d'un orphelin se fermait. La cible visee est le SECOND lot de son rush.
    """
    arbre = _arbre_tout_non_declare()
    lot = _par_nom_dans(arbre, "plan-04_25_v2 · " + pi.MENTION_NON_DECLARE)

    assert ps.cible_du_noeud(lot) == {"lot_id": "plan-04_25_v2"}
    # La ligne, elle, PORTE toujours la mention : c'est ce qu'`E6-1` dessine.
    assert pi.MENTION_NON_DECLARE in lot.nom


def test_lot_ancetre_rend_le_lot_id_du_COEUR_et_pas_la_ligne():
    """L'autre bout de `F2` : le CONTEXTE propage a tous les enfants.

    Une planche sous un lot non declare recevait `lot_id` pollue, donc les
    quatre cibles fines etaient touchees d'un coup. La cible visee est ici en
    QUEUE de son lot (`_v2` des deux planches).
    """
    arbre = _arbre_tout_non_declare()
    planche = _par_nom_dans(
        arbre, "demo_plan-04_25_v2_6f-pay_v2.pdf · " + pi.MENTION_NON_DECLARE)

    assert ps.lot_ancetre(arbre, planche) == "plan-04_25_v2"
    fine = ps.cible_du_noeud(planche, ps.lot_ancetre(arbre, planche))
    assert fine == {"lot_id": "plan-04_25_v2", "planche": True, "version": 2}


def test_un_SCAN_non_declare_rend_une_FAMILLE_propre(  # noqa: D103
        ):
    """La famille du scan se lit de la tige : la mention la polluait aussi.

    Cible aux DEUX BORDS : le scan du premier rush et celui du dernier.
    """
    arbre = _arbre_tout_non_declare()
    for lot_id in ("a-premier_25", "z-dernier_8"):
        nom = f"{lot_id}_scan_v2 · " + pi.MENTION_NON_DECLARE
        scan = _par_nom_dans(arbre, nom)
        fine = ps.cible_du_noeud(scan, ps.lot_ancetre(arbre, scan))
        assert fine == {"lot_id": lot_id, "scan": f"{lot_id}_scan",
                        "version": 2}, (lot_id, fine)


def test_identifiant_du_noeud_rend_None_sur_un_GROUPE_et_pas_son_libelle():
    """Un repli sur `noeud.nom` remettrait la mention par la petite porte.

    Un groupe porte `planches — 2 planches`, qui n'est l'identifiant de rien.
    """
    arbre = _arbre_tout_non_declare()
    groupes = [n for n in _tous_les_noeuds(arbre) if n.groupe]
    assert groupes, "temoin : la fabrique DOIT produire des groupes"
    for groupe in groupes:
        assert ps.identifiant_du_noeud(groupe) is None, groupe.nom


def _par_nom_dans(arbre, nom):
    trouves = [n for n in _tous_les_noeuds(arbre) if n.nom == nom]
    assert len(trouves) == 1, (nom, [n.nom for n in _tous_les_noeuds(arbre)])
    return trouves[0]


# ---------------------------------------------------------------------------
# Les branches GROSSIERES de `cible_du_noeud`, que rien ne mesurait
# ---------------------------------------------------------------------------
#
# Mutants `C01`, `C02` et `C07` de la couche 1 venaient tous d'un meme trou :
# les cinq assertions du banc visaient toutes une nature FINE -- master, scan,
# planche. Les deux branches grossieres ne l'etaient nulle part, et `C01` --
# un LOT vise par `rush_id` -- produit exactement « une destruction plus large
# que celle demandee », que ce module se donne pour interdite.


def test_un_LOT_est_vise_par_lot_id_et_JAMAIS_par_rush_id():
    """Mutant `C01` : la pire consequence que ce module puisse produire.

    Un lot vise par `rush_id` fait supprimer le RUSH ENTIER -- ses autres lots
    compris. Ce n'est pas une cible fausse, c'est une cible ELARGIE, et le
    coeur l'accepterait sans broncher puisque le mot-cle est valide.
    """
    lot = _noeud(NATURE_LOT, "plan-04_12p5", profondeur=1)
    assert ps.cible_du_noeud(lot) == {"lot_id": "plan-04_12p5"}


def test_un_RUSH_est_vise_par_rush_id_et_JAMAIS_par_lot_id():
    """Mutant `C01`, volet symetrique : l'echange est mesure dans les DEUX sens.

    Un seul des deux volets laisserait passer la permutation -- c'est la lecon
    du mutant `M33` de la 5.6, ou l'appariement etait inverse et 165 tests
    restaient verts.
    """
    rush = _noeud(NATURE_RUSH, "plan-04", profondeur=0)
    assert ps.cible_du_noeud(rush) == {"rush_id": "plan-04"}


def test_une_cible_FINE_sans_contexte_de_lot_rend_None_et_pas_une_cible_NUE():
    """Mutant `C02` : une cible fine batie sans `lot_id` viserait au hasard.

    `remove_project_element` prend le lot comme CONTEXTE des quatre cibles
    fines ; sans lui, `{"planche": True}` ne designe rien -- ou pire, designe
    ailleurs. Rendre `None` fait monter l'ecran qui NOMME ce qui manque.
    """
    planche = _noeud(NATURE_PLANCHE, "demo_plan-04_12p5_6f-pay.pdf")
    assert ps.cible_du_noeud(planche, None) is None
    assert ps.cible_du_noeud(planche, "plan-04_12p5") == {
        "lot_id": "plan-04_12p5", "planche": True}


def test_un_GROUPE_ne_produit_JAMAIS_de_cible_de_suppression():
    """Mutant `C07` : un groupe est un niveau d'AFFICHAGE, pas un objet.

    `remove_project_element` n'a aucune cible qui vise le dossier `planches/`
    d'un lot. En produire une promettrait une suppression que le coeur
    refuserait -- et l'ecran, lui, a deja sa reponse : il le dit sur sa ligne
    d'etat.
    """
    lot = _objet_de_lot_a_deux_planches()
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(ObjetInventorie(nature=NATURE_RUSH, nom="plan-04", chemin=None,
                                etat="present", enfants=(lot,)),)))
    groupes = [n for n in _tous_les_noeuds(arbre) if n.groupe]
    assert groupes, "temoin : la fabrique DOIT produire un groupe"
    for groupe in groupes:
        assert ps.cible_du_noeud(groupe, "plan-04_25") is None, groupe.nom


def _objet_de_lot_a_deux_planches() -> ObjetInventorie:
    def objet(nature, nom):
        return ObjetInventorie(nature=nature, nom=nom, chemin=None,
                               etat="present")
    return ObjetInventorie(
        nature=NATURE_LOT, nom="plan-04_25", chemin=None, etat="present",
        enfants=(objet(NATURE_PLANCHE, "demo_plan-04_25_6f-pay.pdf"),
                 objet(NATURE_PLANCHE, "demo_plan-04_25_8f-por.pdf")))


def test_les_libelles_de_LOT_et_de_RUSH_ne_sont_PAS_permutables():
    """Mutant `C25` : « tout le lot hiver » sur un rush, et l'inverse.

    Le panneau de confirmation est le point de jugement : un mot de nature
    faux y fait valider une suppression pour une autre. Les deux sens sont
    mesures, un seul laisserait passer la permutation.
    """
    lot = _noeud(NATURE_LOT, "plan-04_12p5", profondeur=1)
    rush = _noeud(NATURE_RUSH, "plan-04", profondeur=0)

    assert ps.libelle_de_la_cible(lot) == LIBELLE_DESSINE_DU_LOT
    assert ps.libelle_de_la_cible(rush) == "tout le rush plan-04"
    # Et un OBJET n'en recoit aucun : son nom se suffit.
    master = _noeud(NATURE_MASTER, "plan-04_12p5_mmu_prores_hq.mov")
    assert ps.libelle_de_la_cible(master) == "plan-04_12p5_mmu_prores_hq.mov"


def test_le_cardinal_des_PARTIS_ne_devient_JAMAIS_negatif():
    """Finding `F9` : `E6-3` aurait affiche « -3 fichiers » et « -3 retirés ».

    `plan.fichiers` vient du dry-run, `fichiers_non_supprimes` du run REEL.
    Rien ne garantit que le reel ne nomme pas plus de fichiers que le dry-run
    n'en prevoyait -- un fichier apparu entre les deux passes suffit. La ligne
    voisine bornait deja le POIDS a zero : le cas avait ete pense pour une
    grandeur et pas pour l'autre.
    """
    # `plan.fichiers` se DERIVE du rapport de dry-run : deux fichiers prevus.
    plan = _plan_de_synthese(rapport=_rapport(fichiers=("a", "b")), poids=10)
    assert plan.fichiers == 2, "temoin : le dry-run doit prevoir DEUX fichiers"
    # Le run reel en nomme CINQ non supprimes -- plus que prevu.
    rapport = _rapport(fichiers=("a", "b"), dry_run=False,
                       fichiers_non_supprimes=("a", "b", "c", "d", "e"))
    panneau = ps.panneau_du_resultat(plan, rapport)

    supprimes = [l for l in panneau.lignes
                 if l.libelle == ps.LIBELLE_SUPPRIMES][0]
    assert "-" not in str(supprimes.valeur), supprimes.valeur
    assert str(supprimes.valeur).startswith("0 "), supprimes.valeur
    # **Et la LIGNE D'ETAT aussi** : elle refaisait la soustraction pour son
    # compte, donc la borne du cartouche ne fermait que la moitie du defaut
    # (finding `C2-3` de la couche 2, mesure quelques heures apres `F9`).
    assert ps.partis_du_rapport(plan, rapport) == 0
    ecran = ps.EcranResultatDeSuppression(plan, rapport)
    etat = ps.ligne_d_etat_du_resultat(rapport,
                                       ps.partis_du_rapport(plan, rapport))
    assert "-" not in etat.replace("é", ""), etat
    # La surface reelle de l'ecran, pas seulement la fonction : c'est elle qui
    # atteint l'operateur.
    assert ecran._partis_a_dire() == 0


def test_AUCUN_profil_du_registre_n_est_PREFIXE_D_UN_AUTRE_au_separateur():
    """Finding `F8` : la lecture du profil est sure SOUS UNE HYPOTHESE, et elle
    n'etait mesuree nulle part.

    `naming.profil_du_master` cherchait autrefois le profil le plus LONG
    d'abord ; ce tri a ete retire parce que deux mutants se masquaient
    mutuellement, et sa docstring affirme que « la frontiere de separateur
    suffit, mesuree sur les sept profils du registre ». **C'est exact
    aujourd'hui**, et la couche 1 l'a verifie (0 ecart sur 21 noms).

    Ce que personne ne mesurait, c'est POURQUOI c'est exact : uniquement parce
    qu'aucun identifiant du registre n'est prefixe d'un autre **au
    separateur**. Le jour ou un `prores` generique rejoindrait le registre a
    cote de `prores_hq`, `prores_hq_uhd` se lirait `profil='prores'` +
    `resolution='hq_uhd'` -- et la suppression viserait le master d'un AUTRE
    profil, silencieusement.

    `dnxhr_hq` / `dnxhr_hqx` sont deja dans ce cas SANS le separateur, et c'est
    precisement ce qui montre que la propriete mesuree ici est la bonne : ces
    deux-la ne se confondent pas, parce que `dnxhr_hqx` ne commence pas par
    `dnxhr_hq` + `_`.

    Trois lignes qui rougissent le jour ou l'hypothese tombe, plutot qu'une
    suppression fausse ce jour-la.
    """
    profils = sorted(codec_profiles.PROFILES)
    assert len(profils) >= 7, profils      # temoin : le registre est non vide
    fautifs = _prefixes_au_separateur(profils)
    assert fautifs == [], (
        "Un profil est prefixe d'un autre AU SEPARATEUR : "
        f"{fautifs}. `naming.profil_du_master` lirait le plus COURT et "
        "rendrait le reste en resolution, donc la suppression viserait le "
        "master d'un autre profil. Retablir le tri par longueur decroissante "
        "dans `profil_du_master`, avec son banc.")


def _prefixes_au_separateur(profils):
    """Les couples `(court, long)` ou `long` commence par `court` + `_`."""
    return [(court, long) for court in profils for long in profils
            if court != long and long.startswith(f"{court}_")]


def test_la_frontiere_du_REGISTRE_mord_sur_un_registre_fautif():
    """Le volet symetrique : sans lui, la frontiere ci-dessus mesurerait le vide.

    Un registre sain rend une liste vide, et une frontiere qui ne rendrait
    JAMAIS rien passerait de la meme facon. Le cas fautif est celui que la
    couche 1 a chiffre : `prores` generique a cote de `prores_hq`.
    """
    assert _prefixes_au_separateur(["prores_hq", "prores", "dnxhr_hqx"]) == [
        ("prores", "prores_hq")]
    # Et `dnxhr_hq` / `dnxhr_hqx` -- deja dans le registre -- ne sont PAS
    # fautifs : c'est le separateur qui fait la difference, pas le prefixe.
    assert _prefixes_au_separateur(["dnxhr_hq", "dnxhr_hqx"]) == []


def test_le_registre_REEL_porte_bien_le_couple_qui_rend_la_mesure_utile():
    """`dnxhr_hq` est un prefixe strict de `dnxhr_hqx`, et ils coexistent.

    Sans ce temoin, la frontiere ci-dessus pourrait se lire comme une garde
    contre un cas theorique. Il est deja la, sans le separateur -- et c'est
    exactement cette nuance qui fait que la lecture du profil tient.
    """
    assert {"dnxhr_hq", "dnxhr_hqx"} <= set(codec_profiles.PROFILES)
    assert "dnxhr_hqx".startswith("dnxhr_hq")
    assert not "dnxhr_hqx".startswith("dnxhr_hq_")


def test_un_lot_id_VIDE_ne_laisse_lire_AUCUN_profil_de_master():
    """Finding `C2-10` de la couche 2 : une garde asymetrique, fermee.

    Le docstring de `profil_du_master` promet que « le `lot_id` est **connu**,
    il n'est pas devine » et que « le prefixe se retire par egalite, jamais par
    une expression reguliere qui trouverait un lot dans un nom ». Une chaine
    vide est precisement un lot qui n'est PAS connu -- et sans garde le prefixe
    `"" + "_mmu_"` matche, si bien que la fonction lisait un profil sans avoir
    retire quoi que ce soit :

        profil_du_master('_mmu_prores_hq.mov', '')
          -> ProfilDuMaster(profil='prores_hq', resolution=None, rang=1)

    `cible_du_noeud` ne repoussait que `lot_id is None`, jamais la chaine vide :
    la garde n'existait donc d'un seul cote. Non atteignable aujourd'hui --
    aucun lot ne se nomme « » --, ferme quand meme parce que la garde tient en
    une ligne et que la surface est celle d'une SUPPRESSION.
    """
    assert naming.profil_du_master("_mmu_prores_hq.mov", "") is None
    # Le volet de vitalite : le meme nom, avec son vrai lot, se lit toujours.
    lu = naming.profil_du_master("plan-04_25_mmu_prores_hq.mov", "plan-04_25")
    assert lu is not None and lu.profil == "prores_hq", lu


#: **Les QUATRE refus publies par le coeur, un par un.** `ProjetIntrouvable`,
#: `ManifesteIntrouvable`, `ManifesteIllisible` et `ManifesteIncoherent` --
#: quatre classes, quatre issues differentes, et le coeur les distingue
#: precisement parce qu'« un appelant qui ne peut pas les distinguer
#: proposerait la mauvaise » (docstring de `ManifesteIntrouvable`).
LES_QUATRE_REFUS = (
    (ProjetIntrouvable, "le dossier /nulle-part n'existe pas"),
    (ManifesteIntrouvable, "aucun manifeste dans ce dossier"),
    (ManifesteIllisible, "le manifeste ne se lit pas : JSON invalide"),
    (ManifesteIncoherent, "rushes n'est pas une liste"),
)


@pytest.mark.parametrize("refus,message", LES_QUATRE_REFUS,
                         ids=[r.__name__ for r, _ in LES_QUATRE_REFUS])
def test_CHACUN_des_quatre_refus_du_coeur_devient_un_ECRAN_et_pas_une_trace(
        tmp_path, banc, refus, message):
    """Signale par la session coordinatrice de l'Epic 11 le 2026-09-06.

    **Le fait mesure, et il est plus fin qu'il n'en a l'air.** Un recensement
    sur tout `src/` a rendu ZERO ligne hors `project_inventory.py` qui nomme
    `ProjetIntrouvable` ou `ManifesteIllisible` : les quatre refus sont
    exportes, documentes, et mesures par une frontiere qui interdit qu'il y en
    ait un cinquieme -- mais **la frontiere qui les COMPTE ne mesure pas qu'ils
    soient CONSOMMES**. Une couche d'audit qui confronte l'AC 1.6 (« le module
    ne leve QUE ses quatre refus propres ») verifie qu'ils sont quatre et
    conclut « conforme » sans voir qu'aucune surface ne les lit.

    Tant que rien ne montait l'inventaire, ca ne coutait rien. A la seconde ou
    la porte s'ouvre, ca change de nature : un `project.json` illisible ne
    rendrait pas un refus a deux issues, il rendrait une **trace de pile** a
    l'ecran -- soit exactement ce qu'`EPIC11-ARB-89` interdit, et un cran pire
    qu'un blocage sec.

    **Pourquoi les quatre et pas un seul.** L'ouvreur attrape la classe de
    BASE, `InventaireError`. Un test sur un seul refus resterait donc vert si
    l'un des trois autres cessait d'en heriter -- et c'est le seul changement
    qui casserait ce chemin. Point 1 de la regle des fabriques, sur une famille
    d'exceptions cette fois : une fabrique mono-element rend invisible toute
    erreur d'appariement.
    """
    def refuse(_dossier):
        raise refus(message)

    (ecran, lignes), _ = _ouvre(tmp_path, banc, inventorier=refuse,
                                lire=lambda e: "\n".join(e.lignes()))

    # **`EcranRefus`, pas `EcranPasEncore`** -- voir le commentaire du test du
    # dossier sans manifeste ci-dessus. Le CODE distingue en plus les quatre
    # refus les uns des autres, ce qu'un ecran « pas encore » ne portait pas.
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert ecran.code == pi.code_du_refus(refus("peu importe"))
    # Le message AFFICHE est celui du coeur, jamais une phrase reecrite ici :
    # une redaction locale resterait verte si le coeur changeait le sien.
    assert message in lignes, lignes


def test_le_refus_du_coeur_ne_REMONTE_pas_quand_il_sort_de_la_famille(
        tmp_path, banc):
    """Le volet symetrique, et il dit ce que le test ci-dessus NE dit pas.

    L'ouvreur attrape `InventaireError` et **rien d'autre** : ce n'est pas un
    `except Exception` qui avalerait un defaut de programmation en le
    deguisant en refus produit. Une panne qui n'est pas un refus du coeur
    remonte donc a l'appelant, ou elle se voit -- c'est voulu, et sans ce
    volet le test ci-dessus serait tout aussi vert sur un `except Exception`.
    """
    def casse(_dossier):
        raise ZeroDivisionError("un vrai defaut, pas un refus")

    with pytest.raises(ZeroDivisionError):
        _ouvre(tmp_path, banc, inventorier=casse)


def test_la_suppression_se_pose_par_une_methode_PUBLIQUE_et_se_retire(banc):
    """`poser_la_suppression`, demandee par la coordination de l'Epic 11.

    Sans elle, le seul cablage possible est `ecran._supprimer = ...` depuis
    l'exterieur : acceptable dans un banc, pas dans un PRODUIT. Poser un
    attribut prive depuis un autre module fait de la forme du champ une
    interface, si bien que le renommer casse un appelant qui n'etait cense
    connaitre que l'ecran.

    Les deux sens sont mesures. `None` **retire** le cablage plutot que d'etre
    refuse, et l'ecran retombe alors sur `CE_QUI_MANQUE_A_LA_SUPPRESSION` --
    une touche annoncee qui dit ce qui manque, jamais une touche muette. Un
    test qui ne mesurerait que la pose resterait vert sur une methode qui
    ignorerait `None`.
    """
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        InventaireDuProjet(dossier=Path("/nulle-part"), project_id="p",
                           rushes=(), orphelins=()))
    ecran = pi.EcranInventaireDuProjet(arbre)
    vus = []

    ecran.poser_la_suppression(vus.append)
    assert ecran._supprimer is not None
    ecran._supprimer("un-noeud")
    assert vus == ["un-noeud"], vus

    ecran.poser_la_suppression(None)
    assert ecran._supprimer is None


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc monte les quatre ecrans de la
# suppression et n'ouvrait aucun dessin : treize valeurs en etaient recopiees
# a la main, dont le libelle du lot dans cinq montages.
#
# Trois d'entre elles ne sont PAS des recopies, et la section les separe des
# dix autres au lieu de tout confronter d'un bloc -- une confrontation qui
# les melangerait serait verte et dirait faux.

#: Les dessins repris ici, a leur source. Quatre : une fabrique de collection
#: produit au moins deux elements distinguables, et la cible est mesuree en
#: tete, au milieu et en queue.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"

DESSINS_DE_LA_SUPPRESSION = (
    ("E6-2", "E6-2-projet-suppression-confirmation.txt"),
    ("E6-2b", "E6-2b-projet-suppression-dernier-lot.txt"),
    ("E6-2c", "E6-2c-projet-suppression-execution.txt"),
    ("E6-3b", "E6-3b-projet-suppression-reussie.txt"),
)


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


@pytest.mark.parametrize("code,fichier", [
    ("E6-2", "E6-2-projet-suppression-confirmation.txt"),
    ("E6-2c", "E6-2c-projet-suppression-execution.txt"),
    ("E6-3b", "E6-3b-projet-suppression-reussie.txt"),
], ids=["E6-2", "E6-2c", "E6-3b"])
def test_le_LIBELLE_du_lot_est_dessine_par_les_TROIS_ecrans_qui_le_montrent(
        code, fichier):
    """Le libelle, a sa source, dans chacun des trois ecrans du parcours.

    Un par un plutot que « quelque part » : les trois le portent, donc une
    mesure globale resterait verte si l'un d'eux le perdait. Et le libelle
    ENTIER plutot que son prefixe -- c'est l'identifiant qui distingue un
    ecran de suppression de l'autre.
    """
    dessin = dessin_de_la_maquette(fichier)
    assert LIBELLE_DESSINE_DU_LOT in dessin, code
    assert LIBELLE_DESSINE_DU_LOT.startswith(PREFIXE_DESSINE_DU_LIBELLE)


def test_le_QUATRIEME_ecran_porte_un_AUTRE_lot_et_c_est_ce_qui_le_distingue():
    """Volet symetrique : `E6-2b` ne parle pas du meme lot.

    Sans lui, la mesure ci-dessus serait aussi vraie de quatre copies du
    meme dessin. `E6-2b` est l'ecran du DERNIER lot d'un rush, et il est
    dessine sur `hiver_24` justement pour qu'on ne le confonde pas avec le
    cas nominal.
    """
    dernier = dessin_de_la_maquette("E6-2b-projet-suppression-dernier-lot.txt")
    assert LIBELLE_DESSINE_DU_LOT not in dernier
    assert PREFIXE_DESSINE_DU_LIBELLE + "hiver_24" in dernier


def test_le_RANG_RENDU_est_dessine_dans_la_ligne_d_etat_de_E6_3b_SEULEMENT():
    """Le rang rendu appartient a la reussite, pas a la confirmation.

    `E6-2` annonce au futur (« le prochain lot reprendrait le v2 ») ; seul
    `E6-3b` constate au passe. Mesurer la presence sans l'absence laisserait
    passer un rang rendu affiche trop tot -- exactement le defaut que
    `EPIC11-ARB-92` interdit.
    """
    reussi = dessin_de_la_maquette("E6-3b-projet-suppression-reussie.txt")
    confirmation = dessin_de_la_maquette(
        "E6-2-projet-suppression-confirmation.txt")
    assert RANG_RENDU_DESSINE in reussi
    assert RANG_RENDU_DESSINE not in confirmation
    assert "le prochain lot reprendrait le v2" in confirmation


def test_le_SINGULIER_est_dessine_et_son_PLURIEL_est_une_COINCIDENCE():
    """Une appartenance vraie dont la conclusion serait fausse, mesuree.

    `1 fichier ·` est bien dessine, tel quel, dans `E6-2` et `E6-3b`.
    `2 fichiers ·` ne l'est PAS : les dessins ne portent que
    « 62 fichiers · », dont c'est une sous-chaine **a cheval sur le
    nombre**. Une confrontation par appartenance repond « oui » aux deux et
    conclut faux sur le second.

    La mesure qui tranche : le pluriel n'apparait jamais en DEBUT de mot.
    Chaque occurrence est precedee d'un chiffre, ce qui n'est pas le cas du
    singulier. C'est la troisieme famille de coincidence attrapee par cette
    campagne -- apres le prefixe (`scan requis`) et le message d'assertion
    (`la passe `), voici la sous-chaine a cheval sur un nombre.
    """
    for _, fichier in DESSINS_DE_LA_SUPPRESSION:
        dessin = dessin_de_la_maquette(fichier)
        depart = 0
        while (rang := dessin.find(PLURIEL_DESSINE, depart)) != -1:
            assert rang > 0 and dessin[rang - 1].isdigit(), (fichier, rang)
            depart = rang + 1

    # Et le singulier, lui, est bien un mot entier quelque part.
    confirmation = dessin_de_la_maquette(
        "E6-2-projet-suppression-confirmation.txt")
    rang = confirmation.find(SINGULIER_DESSINE)
    assert rang > 0 and not confirmation[rang - 1].isdigit()


def test_dernier_lot_est_un_message_d_EXCEPTION_et_non_une_recopie():
    """Le motif que le double leve n'est pas du texte d'ecran.

    `LastLotRefusedError("dernier lot")` est une chaine de DIAGNOSTIC levee
    par un double du coeur. `E6-2b` dessine bien « dernier lot du rush
    hiver », mais dans sa ligne d'etat, et l'un n'est pas repris de l'autre.
    La mesure : le fragment n'apparait dans le dessin que suivi de
    « du rush », jamais seul.
    """
    dernier = dessin_de_la_maquette("E6-2b-projet-suppression-dernier-lot.txt")
    assert "dernier lot du rush hiver" in dernier
    assert dernier.count("dernier lot") == dernier.count("dernier lot du rush")


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    for _, fichier in DESSINS_DE_LA_SUPPRESSION:
        dessin = dessin_de_la_maquette(fichier)
        assert "tout le rush plan-04" not in dessin
        assert "rang v3 rendu" not in dessin


# ---------------------------------------------------------------------------
# `EPIC11-ARB-260` -- le MUR d'Egan : un refus de domaine habille en « pas encore »
# ---------------------------------------------------------------------------
#
# **Le retour terrain du 2026-09-06, verbatim** :
#
#     Supprimer un rushe (alors qu'il ne reste qu'un lot) - l'ecran n'existe
#     pas encore :
#     > Le rush 'TEST_FILE' porte encore 1 lot(s) (TEST_FILE_7p5):
#     > remove_project_element ne supprime jamais un rush qui porte encore
#     > des l...
#     > Cet ecran n'existe pas encore.
#     > Il arrive avec les ecrans de gestion des medias du palier Projet.
#
# La garde du coeur a RAISON : une cascade ferait partir N lots -- frames,
# masters, planches, scans -- sur un geste qui n'en nommait qu'un. C'est son
# HABILLAGE qui mentait, et deux fois : le titre annonce un ecran a construire,
# et l'echeance promet une arrivee a un operateur qui est deja dans ces
# ecrans-la.
#
# **Le drapeau que ces tests font varier** : refus de DOMAINE (le coeur dit non)
# contre manque REEL (le produit ne sait pas). Un banc qui ne jouerait qu'un des
# deux ne verrait pas que les deux etaient habilles pareil.


def _projet_a_un_rush_et_un_lot(tmp_path) -> Path:
    """Le regime EXACT d'Egan : un rush, un lot dessous, et rien d'autre.

    **Un seul rush et un seul lot, et c'est le cas limite plutot qu'une
    fabrique paresseuse** : c'est la conjonction des deux gardes du coeur --
    « ce rush porte encore des lots » ET « ce serait le dernier rush » --, et
    c'est celle qu'Egan a rencontree. La fabrique a plusieurs lots
    (:func:`_arbre_a_quatre_niveaux`) sert les tests voisins ; celle-ci sert le
    cas que le produit refusait mal.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "TEST_FILE"}]
    document["lots"] = [{"lot_id": "TEST_FILE_7p5", "rush_id": "TEST_FILE",
                         "frames_dir": "extract-frames/TEST_FILE_7p5"}]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    cible = chemin / "extract-frames/TEST_FILE_7p5/f0.tiff"
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(b"o" * 77)
    return chemin


def _rush_de_l_arbre(arbre):
    return next(n for n in arbre.tous() if n.nature == NATURE_RUSH)


def test_ARB260_supprimer_un_RUSH_qui_porte_un_lot_monte_un_REFUS(tmp_path,
                                                                  banc):
    """Le mur d'Egan, joue de bout en bout sur le VRAI coeur.

    **Les deux volets, parce que c'est leur difference qui est le defaut** :
    l'ecran monte est bien un refus, et il n'est **pas** l'ecran de manque. Un
    test qui n'asserterait que « quelque chose est monte » serait reste vert
    tout du long -- quelque chose etait bien monte, et c'est ce quelque chose
    qui mentait.
    """
    chemin = _projet_a_un_rush_et_un_lot(tmp_path)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventorier_le_projet(chemin))
    rush = _rush_de_l_arbre(arbre)
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        rendu = ps.ouvrir_la_suppression(temoin, rush, projet=chemin)
        return rendu, pilote.app.descendus

    rendu, descendus = _monte(_app(temoin), scenario, banc)
    assert rendu is True
    ecran = descendus[-1]
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    assert not isinstance(ecran, EcranPasEncore), type(ecran).__name__
    # Le message du coeur, VERBATIM : il nomme le lot qui bloque.
    assert "TEST_FILE_7p5" in ecran.message
    assert ecran.code == "PROJECT_MAINTENANCE_ERROR"


def test_ARB260_le_refus_NOMME_son_issue_et_la_lit_de_l_ARBRE(tmp_path, banc):
    """`EPIC11-ARB-89` : « un refus qui n'offre aucune issue est aussi fautif
    qu'une destruction silencieuse ».

    L'issue est dans `Suites`, et **pas** dans le message : le message est
    tronque a 76 colonnes comme toute ligne de cet ecran -- c'est exactement ce
    qu'Egan a vu (« ne supprime jamais un rush qui porte encore des l... »).
    Une entree de `Suites` est une ligne a elle.

    Elle est **lue de l'arbre** : le cardinal vient des enfants du rushe, pas
    d'une relecture de la phrase du coeur, qui perimerait a la premiere
    reformulation.
    """
    chemin = _projet_a_un_rush_et_un_lot(tmp_path)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventorier_le_projet(chemin))
    rush = _rush_de_l_arbre(arbre)
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, rush, projet=chemin)
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert ecran.suites == [ps.PHRASE_DES_LOTS_D_ABORD.format(
        cardinal="1", mot=ps.MOT_DES_LOTS[0])]
    # Et les deux issues de l'ecran restent annoncees : jamais un blocage sec.
    assert "Échap" in ecran.raccourcis


def test_ARB260_la_suite_ACCORDE_son_cardinal_et_le_compte_JUSTE(tmp_path):
    """Le cardinal vient de l'arbre, et l'accord ne se calcule pas par `+ s`.

    Deux rushes de cardinaux **differents** -- un a deux lots, un a un seul --,
    et les deux sont mesures : une fabrique ou tous les rushes porteraient le
    meme nombre de lots rendrait invisible un cardinal cable en dur.
    """
    _chemin, arbre = _arbre_a_quatre_niveaux(tmp_path)
    par_nom = {n.nom: n for n in arbre.tous() if n.nature == NATURE_RUSH}

    assert ps.suites_du_refus(par_nom["a-premier"]) == [
        ps.PHRASE_DES_LOTS_D_ABORD.format(cardinal="2",
                                         mot=ps.MOT_DES_LOTS[1])]
    assert ps.suites_du_refus(par_nom["z-dernier"]) == [
        ps.PHRASE_DES_LOTS_D_ABORD.format(cardinal="1",
                                         mot=ps.MOT_DES_LOTS[0])]
    # Un noeud sans lot dessous n'invente aucune suite -- et `None` non plus.
    lot = next(n for n in arbre.tous() if n.nature == NATURE_LOT)
    assert ps.suites_du_refus(lot) == []
    assert ps.suites_du_refus(None) == []


def test_ARB260_la_nature_SANS_cible_fine_reste_un_PAS_ENCORE_sans_echeance(
        tmp_path, banc, monkeypatch):
    """Le volet SYMETRIQUE, et sans lui le reste ne dit rien.

    Quand une nature n'a REELLEMENT pas de cible dans le coeur, « pas encore »
    est vrai et l'ecran reste celui du manque -- ce qui tombe est l'ECHEANCE,
    qui promettait des ecrans de gestion des medias a un operateur deja dedans.

    **Il se joue sur une nature de SYNTHESE depuis le 2026-09-07** : les frames
    extraites etaient le seul manque reel de ce module, et le coeur les vise
    desormais. Mesurer `EPIC11-ARB-260` sur une cible livree ne mesurerait plus
    rien.
    """
    monkeypatch.setitem(ps.NATURES_SANS_CIBLE_FINE, _NATURE_INVENTEE,
                        _LIBELLE_INVENTE)
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    noeud = _noeud(_NATURE_INVENTEE, "plan-04_25")
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, noeud, projet=chemin,
                                 lot_id="plan-04_25")
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert ecran.quand == "", "l'echeance mensongere est revenue"
    assert "arrive avec" not in "\n".join(ecran.lignes())
    assert _LIBELLE_INVENTE in ecran.ce_qui_manque


# ---------------------------------------------------------------------------
# `EPIC11-ARB-260` -- le master ORPHELIN : le coeur sait, la TUI bloquait
# ---------------------------------------------------------------------------
#
# `cible_du_noeud` rend `None` quand `lot_id is None`, et l'ecran disait
# « Retirer un master seul du projet / Cet ecran n'existe pas encore ». Le coeur
# sait pourtant le faire (`master=True` + `profile=`) : le blocage etait en
# amont, dans la TUI.
#
# **Le drapeau que ces tests font varier** : objet GREFFE (l'arbre porte sa
# filiation) contre objet ORPHELIN (il vit a la racine).


def _projet_au_master_orphelin(tmp_path) -> tuple[Path, object]:
    """Un projet dont un master REEL ne se greffe sur aucun lot declare.

    **Le master orphelin est en QUEUE de l'arbre et son lot au MILIEU** des
    deux declares : un resolveur qui rendrait le premier lot connu passerait
    une fabrique a un seul lot, et un balayage tronque d'un bord manquerait
    celui-ci.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "z-dernier"}]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25"},
        {"lot_id": "z-dernier_8", "rush_id": "z-dernier",
         "frames_dir": "extract-frames/z-dernier_8"},
    ]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    for relatif, octets in (
            ("extract-frames/a-premier_25/f0.tiff", 11),
            ("extract-frames/z-dernier_8/f0.tiff", 101),
            # Le master n'est declare par AUCUN lot : il est orphelin, et son
            # nom nomme pourtant le SECOND lot declare.
            ("outputs/z-dernier_8_mmu_prores_hq.mov", 4004)):
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin, pi.ArbreDuProjet.depuis_l_inventaire(
        inventorier_le_projet(chemin))


def test_ARB260_un_master_ORPHELIN_retrouve_son_lot_par_EGALITE(tmp_path):
    """Le rattrapage de `lot_ancetre`, et les DEUX volets de sa garde.

    Le premier volet dit que la position de l'arbre ne suffit plus -- c'est le
    fait qui produisait le mur --, le second que le nom suffit, **par egalite**
    avec un lot declare et jamais par decoupage.
    """
    _chemin, arbre = _projet_au_master_orphelin(tmp_path)
    master = next(n for n in arbre.tous()
                  if n.nature == NATURE_MASTER and not n.groupe)

    assert ps.lot_ancetre(arbre, master) is None, (
        "l'orphelin s'est greffe : la fabrique ne mesure plus le regime")
    assert ps.lot_de_rattachement(arbre, master) == "z-dernier_8"
    assert ps.lots_declares(arbre) == ("a-premier_25", "z-dernier_8")


def test_ARB260_le_rattachement_REFUSE_ce_qu_il_ne_peut_pas_trancher(tmp_path):
    """Trois volets negatifs, chacun sur une cause differente.

    Une seule d'entre elles suffirait a faire viser un objet que l'operateur
    n'a pas designe -- le risque R12 --, et aucune n'est visible a la
    relecture : elles se ressemblent toutes trois par leur `None`.
    """
    _chemin, arbre = _projet_au_master_orphelin(tmp_path)

    # Un nom qui ne nomme AUCUN lot declare.
    etranger = _noeud(NATURE_MASTER, "inconnu_mmu_prores_hq.mov")
    assert ps.lot_de_rattachement(arbre, etranger) is None
    # Un nom qui nomme un lot declare mais AUCUN profil du registre.
    sans_profil = _noeud(NATURE_MASTER, "z-dernier_8_mmu_pas_un_profil.mov")
    assert ps.lot_de_rattachement(arbre, sans_profil) is None
    # Une nature qui n'est pas un master : aucun lecteur exact n'existe pour
    # son nom, et en ecrire un ici serait une regle de nommage logee loin de
    # sa fabrique.
    planche = _noeud(NATURE_PLANCHE, "projet_demo_z-dernier_8_6f-pay.pdf")
    assert ps.lot_de_rattachement(arbre, planche) is None


def test_ARB260_deux_lots_qui_lisent_le_MEME_nom_ne_se_departagent_PAS():
    """L'ambiguite se REFUSE plutot qu'elle ne s'arbitre.

    **La collision est CONSTRUITE, et elle est reelle plutot que decorative** :
    `naming.profil_du_master` lit `a_mmu_prores_hq_mmu_dnxhr_hqx.mov` de deux
    facons valides -- sous le lot `a` (profil `prores_hq`, resolution
    `mmu_dnxhr_hqx`) et sous le lot `a_mmu_prores_hq` (profil `dnxhr_hqx`).
    Les deux lectures passent la garde de frontiere de `io.naming` : aucune
    n'est fautive, elles sont simplement deux.

    En choisir une viserait un objet que l'operateur n'a pas designe -- le
    risque R12 --, et le depot refuse deja l'ambiguite au meme endroit pour la
    greffe des orphelins. Le volet POSITIF est dans le meme test : retirer un
    des deux lots rend la lecture unique, et le rattachement joue. Sans lui, un
    resolveur qui rendrait **toujours** `None` passerait le volet negatif.
    """
    def arbre_des_lots(*lots):
        return pi.ArbreDuProjet(racines=[
            _noeud(NATURE_LOT, lot, profondeur=0) for lot in lots])

    nom = "a_mmu_prores_hq_mmu_dnxhr_hqx.mov"
    master = _noeud(NATURE_MASTER, nom)
    assert naming.profil_du_master(nom, "a") is not None
    assert naming.profil_du_master(nom, "a_mmu_prores_hq") is not None

    ambigu = arbre_des_lots("a", "a_mmu_prores_hq")
    assert ps.lot_de_rattachement(ambigu, master) is None

    # Le volet POSITIF, un lot a la fois : chacun serait retenu SEUL.
    assert ps.lot_de_rattachement(arbre_des_lots("a"), master) == "a"
    assert ps.lot_de_rattachement(
        arbre_des_lots("a_mmu_prores_hq"), master) == "a_mmu_prores_hq"


def test_ARB260_Suppr_sur_un_master_ORPHELIN_atteint_le_COEUR_et_pas_le_mur(
        tmp_path, banc):
    """Le mur tombe, et ce qui le remplace est un refus VRAI du coeur.

    **Une instruction du brief est FAUSSE devant le code, et ce test la
    corrige plutot que de la suivre.** Le brief affirmait « le coeur sait
    pourtant le faire (`master=True` + `profile=`) ». C'est vrai d'un master
    DECLARE -- et un master declare est greffe sous son lot dans l'arbre, donc
    `lot_ancetre` le trouve et ce chemin-ci ne le voit jamais. Le seul master
    qui arrive ici est un ORPHELIN, c'est-a-dire precisement celui qu'aucun
    manifeste ne declare, et `_annexes_du_lot` resout la cible `master=` **par
    le manifeste** : mesure faite, le coeur rend « Le lot 'z-dernier_8' ne
    declare aucun master au profil 'prores_hq' ».

    **Ce que le lot livre est donc plus modeste que ce qu'il promettait, et
    c'est quand meme la fin du mur** : l'operateur lisait « Retirer un master
    seul du projet / Cet ecran n'existe pas encore / Il arrive avec les ecrans
    de gestion des medias », trois phrases fausses ; il lit desormais la raison
    reelle, qui nomme le lot et le profil. La cible d'un master NON DECLARE est
    une extension du coeur, et elle est portee a `deferred-work.md`.

    Les trois volets sont mesures ensemble parce que c'est leur conjonction qui
    dit la verite du chemin : le mur est parti, le coeur a bien ete atteint
    (son message le prouve), et rien n'a ete ecrit sur le disque.
    """
    chemin, arbre = _projet_au_master_orphelin(tmp_path)
    for noeud in arbre.tous():
        noeud.deplie = True
    master = next(n for n in arbre.tous()
                  if n.nature == NATURE_MASTER and not n.groupe)
    arbre.viser(master.nom)
    inventaire = pi.EcranInventaireDuProjet(arbre)
    inventaire._supprimer = ps.cabler_la_suppression(inventaire, arbre, chemin)
    avant = _empreinte(chemin)

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        inventaire.traiter("delete")
        return pilote.app.descendus

    ecran = _monte(_app(inventaire), scenario, banc)[-1]
    assert not isinstance(ecran, EcranPasEncore), (
        "le mur « cet ecran n\'existe pas encore » est revenu")
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    # Le refus vient du COEUR et non de la TUI : il nomme le lot RETROUVE par
    # egalite, ce qu'aucun refus de TUI ne saurait dire.
    assert ecran.code == "PROJECT_MAINTENANCE_ERROR"
    assert "z-dernier_8" in ecran.message and "prores_hq" in ecran.message
    assert ecran.code != ps.CODE_SANS_LOT, (
        "le rattachement n\'a pas joue : la TUI a refuse avant le coeur")
    assert _empreinte(chemin) == avant, "un refus a quand meme ecrit"


def test_ARB260_un_objet_SANS_lot_le_DIT_au_lieu_d_annoncer_un_ecran(tmp_path,
                                                                     banc):
    """Quand le rattachement echoue, le refus est VRAI plutot que faux.

    « Cet objet n'est rattache a aucun lot » est vrai ; « cet ecran n'existe
    pas encore » etait faux dans les deux sens -- l'ecran existe, et rien
    n'arrivera qui change ce fait-la.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    planche = _noeud(NATURE_PLANCHE, "orpheline.pdf")
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, planche, projet=chemin, lot_id=None)
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    assert not isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert ecran.code == ps.CODE_SANS_LOT
    assert "orpheline.pdf" in ecran.message


def test_ARB260_un_master_au_PROFIL_illisible_porte_son_PROPRE_code(tmp_path,
                                                                    banc):
    """Deux causes, deux codes : les fondre rendrait le refus inexploitable.

    Un master dont le nom ne nomme aucun profil du registre n'est pas « sans
    lot » -- son lot est connu. Le distinguer est ce qui permet a l'operateur
    de savoir s'il doit chercher un lot ou un nom.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    master = _noeud(NATURE_MASTER, "plan-04_25_mmu_pas_un_profil.mov")
    temoin = ps.EcranSuppressionEnCours(_plan_de_synthese())

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, master, projet=chemin,
                                 lot_id="plan-04_25")
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    assert ecran.code == ps.CODE_MASTER_ILLISIBLE
    assert ecran.code != ps.CODE_SANS_LOT
    assert "plan-04_25" in ecran.message


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_ARB260_les_phrases_du_refus_se_replient_en_ASCII_PUR(ascii_seul):
    """La garde d'epic, sur les trois textes que ce lot ajoute.

    Un glyphe oublie rend `?` en `--ascii`, et le `?` est indistinguable d'une
    donnee manquante.
    """
    textes = [ps.PHRASE_SANS_LOT.format(objet="o.mov"),
              ps.PHRASE_MASTER_ILLISIBLE.format(objet="o.mov", lot="l"),
              ps.PHRASE_DES_LOTS_D_ABORD.format(cardinal="12", mot="lots"),
              ps.CE_QUI_MANQUE_A_LA_CIBLE_FINE.format(nature="n")]
    for texte in textes:
        rendu = jetons.replier_ascii(texte) if ascii_seul else texte
        assert rendu.isascii() or not ascii_seul, rendu
