# -*- coding: utf-8 -*-
"""Story 5.29 (`EPIC11-ARB-89`), operation « supprimer » -- AC 9 a AC 11.

Motif reel: le nettoyage manuel du 2026-08-27 a detruit au `git rm -r` des
frames non commitees de `chendj-mat`, irrecuperables faute d'outil. Ce fichier
mesure `project_maintenance.remove_project_element`.
"""
from __future__ import annotations

import json
import shutil

import pytest

from mixed_media_utility.io import project_layout, version_ranks
from mixed_media_utility.project_maintenance import (
    LastLotRefusedError,
    ProjectMaintenanceError,
    remove_project_element,
)


def _lot(lot_id: str, rush_id: str, frames_dirname: str) -> dict:
    return {
        "lot_id": lot_id,
        "rush_id": rush_id,
        "state": "extraction",
        "frames_dir": f"frames/{frames_dirname}",
    }


def _manifeste_a_trois_lots() -> dict:
    """Regle des fabriques: trois lots distinguables, la cible AU MILIEU,
    d'au moins deux rushs differents."""
    return {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": [
            _lot("rush-a_24", "rush-a", "rush-a_24"),
            _lot("rush-b_12", "rush-b", "rush-b_12"),  # <- la cible, au milieu
            _lot("rush-a_5", "rush-a", "rush-a_5"),
        ],
    }


def _ecrire_projet(tmp_path, manifest: dict) -> "Path":  # noqa: F821
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return projet


# ---------------------------------------------------------------------------
# AC 9 -- ce que le rapport NOMME, et le dry-run par defaut.
#
# La « distinction des trois natures » que cette section mesurait (pointeur
# Git LFS / fichier local suivi par git / donnees non suivies) a ete retiree
# par `EPIC11-ARB-199` (Egan, 2026-09-03) : « l'utilitaire n'a pas vocation a
# traiter des fichiers au sein de depots git ». Le rapport perd la
# classification, jamais l'information -- il nomme desormais TOUS les fichiers
# vises, a plat, dans l'ordre ou ils ont ete construits.
# ---------------------------------------------------------------------------


def test_dry_run_par_defaut_ne_supprime_rien(tmp_path):
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12"
    dossier.mkdir(parents=True)
    (dossier / "frame_00.tiff").write_bytes(b"contenu reel")

    rapport = remove_project_element(projet, lot_id="rush-b_12")

    assert rapport.dry_run is True
    assert rapport.supprime is False
    assert (dossier / "frame_00.tiff").exists()
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert len(manifest_relu["lots"]) == 3, "le manifeste n'est pas touche en dry-run"


def test_le_rapport_NOMME_tous_les_fichiers_a_plat_premier_et_dernier_compris(tmp_path):
    """AC 2.1 (amendee par `EPIC11-ARB-243`) et regle des fabriques : trois
    frames distinguables + une annexe + un tirage, dans TROIS dossiers parents,
    avec egalite sur le premier ET sur le dernier.

    **L'ordre mesure est celui du chemin POSIX complet** depuis
    `EPIC11-ARB-243` (Egan, 2026-09-05) : l'apercu d'une destruction doit etre
    parcourable et comparable ligne a ligne entre deux executions. Avant cet
    arbitrage, l'AC 2.1 promettait « l'ordre d'entree » -- en pratique celui de
    `os.scandir` -- et ce banc ne pouvait epingler que le DOSSIER du premier
    element.

    **Ou ca mord, et ce n'est pas au meme endroit que d'habitude.** Une cible
    au milieu demasque un `find` fautif ; elle ne demasque pas un balayage
    TRONQUE, qui est un autre mode de panne (mutant du lot A de la 11.11). Et
    le classement retire regroupait PAR DOSSIER PARENT avant de parcourir : une
    troncature n'y perdait pas « le dernier fichier » mais « le dernier de
    CHAQUE dossier ». Un seul dossier peuple ne peut pas voir cette panne-la,
    d'ou l'annexe dans `planches/`.
    """
    manifest = _manifeste_a_trois_lots()
    # Le master est declare sous `aaa_annexes/`, qui trie AVANT `frames/` :
    # le coeur ASSEMBLE sa liste dans l'ordre `frames + annexes + tirages`, si
    # bien que l'ordre d'assemblage diverge de l'ordre trie. C'est cet ecart
    # qui rend le tri d'`EPIC11-ARB-243` MESURABLE : retirer le `sorted()` de
    # `_chemins_a_supprimer` remet `aaa_annexes/` en troisieme position et
    # rougit l'egalite ci-dessous.
    manifest["lots"][1]["encoded_masters"] = [{"path": "aaa_annexes/master.mov"}]
    projet = _ecrire_projet(tmp_path, manifest)
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12"
    dossier.mkdir(parents=True)
    for nom in ("aaa_premiere.tiff", "mmm_milieu.tiff", "zzz_derniere.tiff"):
        (dossier / nom).write_bytes(f"contenu de {nom}".encode("utf-8"))
    annexes = projet / "aaa_annexes"
    annexes.mkdir()
    (annexes / "master.mov").write_bytes(b"master encode")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()
    (patches / "projet_rush-b_12_planches.pdf").write_bytes(b"pdf de planches")

    rapport = remove_project_element(projet, lot_id="rush-b_12")

    # Le TUPLE entier, dans l'ordre : depuis `EPIC11-ARB-243` l'ordre est celui
    # du chemin POSIX complet, donc il est ecrivable a la main sans epingler le
    # systeme de fichiers -- ce qu'une assertion d'appartenance ne permettait
    # pas, et c'est tout le gain de l'arbitrage porte cote banc.
    assert rapport.fichiers_a_supprimer == (
        "aaa_annexes/master.mov",
        "frames/rush-b_12/aaa_premiere.tiff",
        "frames/rush-b_12/mmm_milieu.tiff",
        "frames/rush-b_12/zzz_derniere.tiff",
        "planches/projet_rush-b_12_planches.pdf",
    ), rapport.fichiers_a_supprimer
    # Cette egalite de cardinal borne la FABRIQUE (cinq entrees ecrites, cinq
    # rendues), elle ne mesure PAS la deduplication : le point 1 de la regle
    # des fabriques exige des elements distinguables, si bien qu'aucune
    # fabrique canonique ne peut faire repeter une valeur. Le mutant `M4`
    # (`dict.fromkeys` dans `_chemins_a_supprimer`) survivait ici, et la
    # mention « un doublon s'est glisse » cochait donc une case sur un defaut
    # vivant. Ce qui mesure reellement la deduplication est le test suivant,
    # `test__chemins_a_supprimer_est_une_projection_FIDELE_sans_deduplication`
    # (revue 11.13, couche 2, F7).
    assert len(rapport.fichiers_a_supprimer) == 5, rapport.fichiers_a_supprimer
    # **Les deux bords, en EGALITE** (`EPIC11-ARB-243`, finding `c3 F5`).
    # L'assertion de tete etait un `startswith` sur le dossier -- le plus fort
    # que l'on pouvait ecrire tant que l'ordre des frames entre elles etait
    # celui de `rglob`. Un ordre determine la rend epinglable, et une
    # permutation devient mortelle la ou elle survivait.
    #
    # Les deux bords appartiennent maintenant a DEUX dossiers differents de
    # celui du milieu : une troncature en tete perd l'annexe, une troncature en
    # queue perd le tirage, une permutation deplace les deux (point 4 de la
    # regle des fabriques).
    assert rapport.fichiers_a_supprimer[0] == "aaa_annexes/master.mov", (
        "l'ordre est celui du chemin POSIX complet (`EPIC11-ARB-243`) : "
        "`aaa_annexes/` trie AVANT `frames/`, quel que soit l'ordre "
        "d'assemblage de la liste par le coeur")
    assert rapport.fichiers_a_supprimer[-1] == "planches/projet_rush-b_12_planches.pdf"


def test__chemins_a_supprimer_est_une_projection_FIDELE_sans_deduplication(tmp_path):
    """AC 2.1 -- `_chemins_a_supprimer` rend UN chemin par entree recue.

    **Pourquoi ce test existe et pourquoi il est direct** (revue 11.13,
    couche 2, F7). La garde `len(...) == 5` du banc voisin PRETEND attraper un
    doublon ; elle ne le peut pas. Le point 1 de la regle des fabriques exige
    des elements distinguables, donc aucune fabrique canonique du depot ne
    produit deux fois la meme valeur -- or c'est la seule condition qui franchit
    une garde de deduplication. Mesure : le mutant `M4`
    (`tuple(dict.fromkeys(...))` dans `_chemins_a_supprimer`) SURVIVAIT au banc
    entier. C'est le cas remarquable ou la regle des fabriques rend
    structurellement inatteignable la garde qu'elle etait censee armer, et la
    sortie est de mesurer la fonction sur une entree que la fabrique de haut
    niveau ne sait pas produire.

    **Et ce n'est pas une commodite de test : c'est le contrat.** La fonction
    est documentee « lieu UNIQUE du calcul `relative_to(...).as_posix()` », une
    projection un-pour-un. Y glisser une deduplication serait un correctif
    d'AFFICHAGE : l'apercu cesserait de montrer le doublon pendant que la
    boucle `unlink()` continuerait de passer deux fois sur le meme chemin --
    donc `FileNotFoundError`, `supprime=False`, et le manifeste restaure sur un
    lot dont tous les fichiers sont detruits. Le rapport mentirait mieux. Le
    doublon se ferme la ou il nait -- la construction de `fichiers` --, et cet
    arbitrage produit est verse en dette (`deferred-work.md`, entree
    « lot fantome », revue 11.13 couche 2 F7).

    Quatre entrees dont la repetee est AU MILIEU (point 2 bis de la regle) et
    deux dossiers parents.

    **Depuis `EPIC11-ARB-243` la projection TRIE** : elle reste fidele au
    CARDINAL, jamais a l'ordre d'entree. Le doublon ressort donc toujours deux
    fois, desormais cote a cote -- ce qui ne change rien a ce que ce banc
    mesure, une deduplication faisant tomber le cardinal de 4 a 3 quel que soit
    l'ordre.
    """
    from mixed_media_utility.project_maintenance import _chemins_a_supprimer

    projet = tmp_path / "projet"
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / "aaa_annexes").mkdir()
    repete = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "master.mov"
    entrees = [
        projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "zzz_frame.tiff",
        repete,
        projet / "aaa_annexes" / "mmm_annexe.pdf",
        repete,
    ]

    rendu = _chemins_a_supprimer(projet, entrees)

    assert rendu == (
        "aaa_annexes/mmm_annexe.pdf",
        "frames/rush-b_12/master.mov",
        "frames/rush-b_12/master.mov",
        "frames/rush-b_12/zzz_frame.tiff",
    ), rendu
    assert len(rendu) == len(entrees), (
        "`_chemins_a_supprimer` a deduplique : ce serait un correctif "
        "d'AFFICHAGE qui masquerait le doublon sans empecher le second "
        "`unlink()` -- voir la dette « lot fantome »")
    assert rendu.count("frames/rush-b_12/master.mov") == 2, (
        "l'entree repetee doit ressortir DEUX fois : le rapport dit ce que la "
        "boucle de suppression va reellement parcourir, pas une version "
        "assainie de cette liste")


def test__fichiers_du_lot_ORDONNE_chaque_dossier_par_chemin_posix(tmp_path):
    """`EPIC11-ARB-243`, volet SOURCE : la liste que la boucle `unlink()`
    parcourt ne depend plus du systeme de fichiers.

    **Pourquoi un banc DIRECT, et pourquoi il ne fait pas double emploi avec
    celui du rapport.** Le rapport est trie TOTALEMENT par
    `_chemins_a_supprimer`, un cran plus bas. Un tri total en aval rend toute
    permutation amont invisible : mesurer l'ordre de `_fichiers_du_lot` a
    travers le rapport reviendrait a mesurer le tri d'en bas deux fois, et le
    mutant `M22` de la couche 3 de la revue 11.13
    (`sorted(dossier.rglob("*"), reverse=True)`) resterait EQUIVALENT. C'est
    exactement la methode « descendre d'un cran » que le registre de findings
    de la 11.13 formule en section 5 : la propriete se mesure sur la fonction
    qui la porte.

    **Ce que la promesse dit, exactement.** Chaque dossier declare est
    parcouru par chemin POSIX croissant ; les DOSSIERS, eux, restent dans
    l'ordre du manifeste (`frames_dir` puis `output_frames_dir`). La fabrique
    declare donc `zzz_frames/` en `frames_dir` et `aaa_rescans/` en
    `output_frames_dir` : l'ordre rendu n'est PAS l'ordre trie global, et
    c'est voulu -- si la liste sortait globalement triee, ce banc mesurerait
    le tri du rapport au lieu du sien.

    **Regle des fabriques.** Cinq fichiers distinguables, deux dossiers, un
    SOUS-dossier (`rglob` descend), et des noms crees dans un ordre
    volontairement non alphabetique. Les cibles sont a chaque BORD -- la tete
    (`aaa_extraite.tiff`) et la queue (`zzz_rescan.tiff`) -- et au milieu :
    une egalite de liste entiere attrape la permutation, la troncature de tete
    et la troncature de queue par la meme assertion.
    """
    from mixed_media_utility.project_maintenance import _fichiers_du_lot

    projet = tmp_path / "projet"
    extraites = projet / "zzz_frames" / "rush-b_12"
    rescannees = projet / "aaa_rescans" / "rush-b_12"
    (extraites / "sous").mkdir(parents=True)
    rescannees.mkdir(parents=True)
    # Ordre de CREATION volontairement non alphabetique : ni lui ni celui de
    # `os.scandir` ne doit transparaitre dans le rendu.
    for chemin in (
        extraites / "mmm_milieu.tiff",
        extraites / "zzz_derniere.tiff",
        extraites / "sous" / "nnn_profonde.tiff",
        extraites / "aaa_premiere.tiff",
        rescannees / "zzz_rescan.tiff",
        rescannees / "aaa_rescan.tiff",
    ):
        chemin.write_bytes(f"contenu de {chemin.name}".encode("utf-8"))

    lot = {
        "lot_id": "rush-b_12",
        "frames_dir": "zzz_frames/rush-b_12",
        "output_frames_dir": "aaa_rescans/rush-b_12",
    }

    rendu = [c.relative_to(projet).as_posix() for c in _fichiers_du_lot(projet, lot, [])]

    assert rendu == [
        "zzz_frames/rush-b_12/aaa_premiere.tiff",
        "zzz_frames/rush-b_12/mmm_milieu.tiff",
        "zzz_frames/rush-b_12/sous/nnn_profonde.tiff",
        "zzz_frames/rush-b_12/zzz_derniere.tiff",
        "aaa_rescans/rush-b_12/aaa_rescan.tiff",
        "aaa_rescans/rush-b_12/zzz_rescan.tiff",
    ], rendu
    # Nomme separement ce que l'egalite ci-dessus contient deja, parce que ce
    # sont deux promesses differentes et qu'une regression sur l'une doit se
    # lire sans decoder une liste de six lignes.
    assert rendu[0] == "zzz_frames/rush-b_12/aaa_premiere.tiff", (
        "le premier dossier declare vient en tete, et il est parcouru trie -- "
        "`EPIC11-ARB-243`")
    assert rendu[-1] == "aaa_rescans/rush-b_12/zzz_rescan.tiff", (
        "la queue est le dernier chemin du SECOND dossier declare : l'ordre "
        "des dossiers est celui du manifeste, pas l'ordre alphabetique")


#: Les champs de `RapportSuppression` AU TERME de la story 11.13 -- la borne
#: HAUTE de la garde de poids ci-dessous (couche 1, finding F6).
#:
#: Ecrit A LA MAIN et non derive de `fields(RapportSuppression)` : une borne
#: qui se recalcule depuis ce qu'elle mesure est le test tautologique que la
#: campagne de la 5.9 a trouve sur la constante centrale de la calibration
#: (CLAUDE.md, regle 5). Elle serait verte quoi qu'on ajoute.
CHAMPS_DU_RAPPORT_AU_TERME_DE_LA_11_13 = frozenset({
    "cible",
    "fichiers_a_supprimer",
    "dry_run",
    "supprime",
    "fichiers_non_supprimes",
    "fichiers_attendus_absents",
    "dossiers_de_scan",
    "scan_inclus",
    "tirage_en_queue",
    "rangs_liberables",
    "rang_libere",
    "rang_vise",
    # **Ajoute le 2026-09-07, AVEC SA RAISON**, comme la clause « quoi faire »
    # de la garde l'exige. Le retrait d'un jeu de frames extraites seul (retour
    # de terrain d'Egan du 2026-09-06) est le premier objet de cette commande
    # sans rang PROPRE : son dossier porte le rang du LOT. Sans ce champ, la
    # CLI retombait sur sa branche « le rang reste CONSOMME: un objet
    # posterieur existe », phrase FAUSSE de bout en bout la ou aucun rang n'est
    # en jeu, et rien ne permettait de la distinguer -- un objet en queue qui
    # ne libere aucun rang presente exactement les memes `tirage_en_queue` et
    # `rangs_liberables`. Ce n'est donc pas un champ de confort : c'est le seul
    # discriminant du cas.
    "rang_independant",
})


def test_le_rapport_ne_porte_AUCUN_champ_de_poids(tmp_path):
    """AC 2.3, test NEGATIF : la borne qui empeche la story de grandir.

    Le poids que la confirmation annonce sans que rien ne le calcule est
    l'arbitrage `B1`, tranche « En effet » par Egan le meme jour, et il
    appartient a la story de l'ecran d'inventaire. Une frontiere negative est
    le seul moyen d'attraper l'elargissement : aucun test positif ne verrait
    apparaitre un champ de trop.
    """
    from dataclasses import MISSING, fields

    from mixed_media_utility.project_maintenance import RapportSuppression

    noms = {champ.name for champ in fields(RapportSuppression)}
    interdits = {n for n in noms
                 if "poids" in n or "octets" in n or "taille" in n or "bytes" in n}
    assert interdits == set(), (
        f"champ(s) de poids dans RapportSuppression: {sorted(interdits)} -- c'est "
        "l'arbitrage B1, une AUTRE story")
    assert "fichiers_a_supprimer" in noms, (
        "le champ plat a disparu : ce test negatif mesurerait alors le vide")
    # AC 2.2, ajoutee en fermeture de la revue 11.13 (couche 3, F2). Les lignes
    # ci-dessus mesuraient les champs EN TROP ; elles ne mesuraient jamais
    # qu'un champ REQUIS le reste. Le mutant `M8` -- champ deplace apres
    # `dry_run` et pourvu de `= ()` -- laissait le banc entierement vert.
    # Les DEUX champs que la couche 3 a mesures nus : `fichiers_a_supprimer`
    # (le mutant `M8` de l'AC 2.2) et son TEMOIN `dry_run` (le mutant `M7`),
    # dont la survie prouvait que RIEN ne mesurait la signature de ce
    # dataclass. Un defaut sur `dry_run` vaudrait « suppression reelle » par
    # omission, sur un rapport qui existe pour dire ce qui a ete detruit.
    for nom in ("fichiers_a_supprimer", "dry_run"):
        champ = next(c for c in fields(RapportSuppression) if c.name == nom)
        assert champ.default is MISSING and champ.default_factory is MISSING, (
            f"AC 2.2 : `{nom}` ne prend PAS de valeur par defaut -- un rapport de "
            "suppression qui ne dirait pas ce qu'il supprime, ni s'il l'a "
            "reellement supprime, serait pire que le classement qu'on retire")

    # --- la BORNE HAUTE de cette garde -----------------------------------
    # Couche 1, finding F6 : la garde ci-dessus perit le jour ou l'arbitrage
    # `B1` est implemente, et c'est voulu -- mais rien ne l'ecrivait, et une
    # garde sans peremption ecrite se fait AFFAIBLIR plutot que retirer. Le
    # precedent est `_BORNE_HAUTE_DE_LA_STORY` de la 5.19
    # (`test_calibration_page_geometry.py:1721`) : une frontiere de perimetre
    # se borne des DEUX cotes, faute de quoi elle mesure « tout ce que le
    # depot fera » au lieu de « ce que cette story a fait ».
    #
    # Ce que la borne ajoute, et ce n'est pas cosmetique : les quatre
    # sous-chaines ci-dessus sont une HEURISTIQUE, et le mutant `M26` --
    # `encombrement_en_ko: int = 0` -- lui echappait en restant vert sur
    # 362 tests. L'ensemble EXACT n'a pas d'angle mort : tout champ neuf,
    # quel que soit son nom, fait rougir ici et nulle part ailleurs.
    assert noms == CHAMPS_DU_RAPPORT_AU_TERME_DE_LA_11_13, {
        "en trop": sorted(noms - CHAMPS_DU_RAPPORT_AU_TERME_DE_LA_11_13),
        "annonces et disparus": sorted(
            CHAMPS_DU_RAPPORT_AU_TERME_DE_LA_11_13 - noms),
        "quoi faire": "si le champ en trop est le POIDS de l'arbitrage B1, "
                      "cette garde a atteint sa borne : on la RETIRE avec son "
                      "litteral, on ne l'affaiblit pas. Si c'est autre chose, "
                      "l'inscrire ici AVEC SA RAISON en fait une decision "
                      "lisible plutot qu'un accident (precedent 5.19).",
    }


# ---------------------------------------------------------------------------
# AC 10 -- suppression effective: manifeste D'ABORD, puis fichiers.
# ---------------------------------------------------------------------------


def test_suppression_effective_retire_le_lot_du_manifeste_et_ses_fichiers(tmp_path):
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)

    dossiers = {}
    for lot in manifest["lots"]:
        dossier = projet / lot["frames_dir"]
        dossier.mkdir(parents=True)
        (dossier / "frame.tiff").write_bytes(f"contenu-{lot['lot_id']}".encode())
        dossiers[lot["lot_id"]] = dossier

    # Temoins: inode et mtime des DEUX AUTRES lots, pour prouver qu'ils sont
    # intacts -- un condensat ne prouverait rien sur une fixture deterministe.
    autres = [lid for lid in dossiers if lid != "rush-b_12"]
    # Les DEUX temoins que le commentaire annonce. La premiere redaction ne
    # relevait que `st_ino` alors qu'elle disait « inode et mtime » : une
    # reecriture a l'identique du contenu (fixture deterministe) aurait
    # conserve l'inode et serait passee inapercue. Mesure de l'auditeur
    # Opus -- une affirmation de commentaire non tenue par le code.
    def _empreinte(chemin):
        etat = chemin.stat()
        return (etat.st_ino, etat.st_mtime_ns, etat.st_size)

    empreintes_avant = {
        lid: _empreinte(dossiers[lid] / "frame.tiff") for lid in autres
    }

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.supprime is True
    manifest_relu = json.loads((projet / "project.json").read_text())
    lot_ids_restants = {l["lot_id"] for l in manifest_relu["lots"]}
    assert lot_ids_restants == {"rush-a_24", "rush-a_5"}
    assert not dossiers["rush-b_12"].exists()

    for lid in autres:
        assert (dossiers[lid] / "frame.tiff").exists()
        assert _empreinte(dossiers[lid] / "frame.tiff") == empreintes_avant[lid], (
            "un lot NON vise a ete touche (inode, st_mtime_ns ou taille)"
        )


def test_lot_inconnu_est_refuse_nommement(tmp_path):
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="lot-qui-n-existe-pas")
    assert "lot-qui-n-existe-pas" in str(refus.value)


# ---------------------------------------------------------------------------
# AC 11 -- refus de vider le dernier lot / rush sans confirmation explicite.
# ---------------------------------------------------------------------------


def test_le_dernier_lot_du_projet_est_refuse_sans_confirmation(tmp_path):
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}],
        "lots": [_lot("rush-a_24", "rush-a", "rush-a_24")],
    }
    projet = _ecrire_projet(tmp_path, manifest)

    with pytest.raises(LastLotRefusedError):
        remove_project_element(projet, lot_id="rush-a_24", dry_run=False)

    # rien n'a ete supprime
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert len(manifest_relu["lots"]) == 1


def test_le_dernier_lot_avec_confirmation_explicite_est_supprime(tmp_path):
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}],
        "lots": [_lot("rush-a_24", "rush-a", "rush-a_24")],
    }
    projet = _ecrire_projet(tmp_path, manifest)

    rapport = remove_project_element(
        projet, lot_id="rush-a_24", dry_run=False, confirmation_dernier_lot=True
    )
    assert rapport.supprime is True
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert manifest_relu["lots"] == []


def test_un_rush_qui_porte_encore_des_lots_est_refuse(tmp_path):
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, rush_id="rush-a", dry_run=False)
    message = str(refus.value)
    assert "rush-a_24" in message
    assert "rush-a_5" in message


def test_un_rush_sans_lot_restant_se_supprime(tmp_path):
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": [_lot("rush-b_12", "rush-b", "rush-b_12")],
    }
    projet = _ecrire_projet(tmp_path, manifest)

    rapport = remove_project_element(projet, rush_id="rush-a", dry_run=False)

    assert rapport.supprime is True
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert {r["rush_id"] for r in manifest_relu["rushes"]} == {"rush-b"}


def test_le_dernier_rush_est_refuse_sans_confirmation(tmp_path):
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}],
        "lots": [],
    }
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(LastLotRefusedError):
        remove_project_element(projet, rush_id="rush-a", dry_run=False)


# ---------------------------------------------------------------------------
# Frontiere d'appel : exactement un des deux mots-cles.
# ---------------------------------------------------------------------------


def test_ni_lot_id_ni_rush_id_est_refuse(tmp_path):
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(projet)


def test_lot_id_et_rush_id_ensemble_est_refuse(tmp_path):
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(projet, lot_id="rush-b_12", rush_id="rush-a")


# ---------------------------------------------------------------------------
# Findings de la revue en trois couches (Blind Hunter, 2026-08-30) : fermes
# ici, avec le mutant qui les reinjecte pour preuve.
# ---------------------------------------------------------------------------


def test_un_manifeste_corrompu_est_refuse_nommement_pas_un_JSONDecodeError_brut(tmp_path):
    """Un `project.json` illisible levait le JSONDecodeError BRUT de
    load_manifest, pas l'erreur de domaine que ce module declare."""
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text("{ceci n'est pas du JSON", encoding="utf-8")

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="peu-importe")
    assert "project.json" in str(refus.value)


def test_un_frames_dir_absolu_dans_le_manifeste_est_refuse(tmp_path):
    """`Path(project_dir) / "/absolu"` rend `/absolu`, PAS
    `project_dir/absolu` : sans garde, un manifeste corrompu ferait supprimer
    des fichiers HORS du dossier projet."""
    manifest = _manifeste_a_trois_lots()
    manifest["lots"][1]["frames_dir"] = "/etc/quelque_chose"  # la cible, rush-b_12
    projet = _ecrire_projet(tmp_path, manifest)
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="rush-b_12")
    assert "absolu" in str(refus.value).lower()


def test_manifeste_ecrit_de_facon_ATOMIQUE_le_projet_survit_a_une_panne(tmp_path, monkeypatch):
    """**Ce test etait TAUTOLOGIQUE et l'auditeur l'a mesure** : sa premiere
    redaction verifiait l'absence de `.tmp` et la relecture du resultat, deux
    choses vraies AUSSI d'un `write_text()` direct -- ramener
    `_ecrire_manifeste` a une ecriture non atomique le laissait vert.

    La propriete a mesurer n'est pas « pas de residu », c'est : **une panne en
    pleine ecriture ne laisse jamais un `project.json` tronque**. On la
    mesure en faisant echouer l'ecriture au milieu, puis en relisant le
    manifeste : il doit etre l'ANCIEN, intact et valide, jamais un fragment.
    """
    import mixed_media_utility.project_maintenance as pm

    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    avant = (projet / "project.json").read_text(encoding="utf-8")

    vrai_replace = pm.os.replace

    def replace_qui_echoue(src, dst):
        raise OSError("panne simulee juste avant la bascule atomique")

    monkeypatch.setattr(pm.os, "replace", replace_qui_echoue)
    with pytest.raises(OSError):
        remove_project_element(projet, lot_id="rush-b_12", dry_run=False)
    monkeypatch.setattr(pm.os, "replace", vrai_replace)

    # L'ancien manifeste est INTACT, octet pour octet : c'est ce que
    # l'ecriture atomique garantit et qu'un write_text() direct ne garantit
    # pas (il aurait laisse un fichier vide ou partiel).
    assert (projet / "project.json").read_text(encoding="utf-8") == avant
    assert len(json.loads(avant)["lots"]) == 3
    # et aucun temporaire ne traine derriere la panne
    assert list(projet.glob(".project.json.*.tmp")) == []


def test_un_echec_de_suppression_de_fichier_se_VOIT_dans_le_rapport(tmp_path, monkeypatch):
    """Trouve en revue : `unlink()` qui echoue etait avale en silence, et le
    rapport rendait `supprime=True` alors qu'un fichier restait sur le
    disque -- exactement la fuite de disque que cette story existe pour
    fermer."""
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12"
    dossier.mkdir(parents=True)
    (dossier / "frame.tiff").write_bytes(b"contenu")

    import pathlib

    original_unlink = pathlib.Path.unlink

    def unlink_qui_echoue(self, *a, **k):
        if self.name == "frame.tiff":
            raise OSError("permission refusee (simulee)")
        return original_unlink(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "unlink", unlink_qui_echoue)

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.supprime is False
    assert rapport.fichiers_non_supprimes == ("frames/rush-b_12/frame.tiff",)
    # **Le lot RESTE au manifeste**, et c'est un changement voulu (revue Opus
    # finale). Retirer l'entree alors que les fichiers survivent rendait le lot
    # INTROUVABLE : la cible se resout par `lot_id`, donc un second essai
    # rendait « Lot inconnu du manifeste ». Zero issue -- l'operateur retombait
    # sur le `rm -rf` manuel, la fuite meme que cette commande existe pour
    # fermer. Des lors que des fichiers restent, le lot existe : le manifeste
    # doit le declarer, et le geste redevient rejouable.
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert "rush-b_12" in {l["lot_id"] for l in manifest_relu["lots"]}, (
        "le lot est devenu introuvable alors que ses fichiers survivent"
    )


# ---------------------------------------------------------------------------
# Revue Opus du 2026-08-30 -- TROIS evasions hors du dossier projet, chacune
# mesuree sur un fichier REELLEMENT detruit avant correctif.
# ---------------------------------------------------------------------------


def _projet_a_deux_lots_dont_la_cible(tmp_path, frames_dir_de_la_cible):
    """La cible n'est ni premiere ni derniere : trois lots, cible au milieu."""
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": [
            _lot("rush-a_24", "rush-a", "rush-a_24"),
            {
                "lot_id": "cible",
                "rush_id": "rush-b",
                "state": "extraction",
                "frames_dir": frames_dir_de_la_cible,
            },
            _lot("rush-a_5", "rush-a", "rush-a_5"),
        ],
    }
    return _ecrire_projet(tmp_path, manifest)


def test_un_frames_dir_REMONTANT_ne_detruit_rien_hors_du_projet(tmp_path):
    """`Path('/proj') / '../../x'` RESOUT hors du projet : `is_absolute()`
    rendait False, la garde de forme ne mordait pas."""
    precieux = tmp_path / "precieux"
    precieux.mkdir()
    (precieux / "irremplacable.tiff").write_bytes(b"donnees non commitees")

    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "../precieux")

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="cible", dry_run=False)
    assert "STRICTEMENT" in str(refus.value)
    assert (precieux / "irremplacable.tiff").exists(), "un fichier hors projet a ete detruit"


def test_un_frames_dir_qui_est_un_LIEN_SYMBOLIQUE_ne_detruit_rien_dehors(tmp_path):
    """Aucun composant du chemin declare n'est suspect, mais `rglob` traverse
    le lien et `unlink()` supprime les fichiers reels a l'autre bout."""
    precieux = tmp_path / "precieux"
    precieux.mkdir()
    (precieux / "irremplacable.tiff").write_bytes(b"donnees non commitees")

    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "frames/par_lien")
    (projet / project_layout.LEGACY_FRAMES_DIRNAME).mkdir(parents=True, exist_ok=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "par_lien").symlink_to(precieux, target_is_directory=True)

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="cible", dry_run=False)
    assert "STRICTEMENT" in str(refus.value)
    assert (precieux / "irremplacable.tiff").exists(), "un fichier hors projet a ete detruit"


def test_un_LIEN_pose_A_L_INTERIEUR_du_dossier_de_lot_ne_detruit_rien_dehors(tmp_path):
    """Un lien pose DANS le dossier de lot : la cible externe survit.

    **La revue annoncait ce cas comme « verifie : rglob traverse le lien » ;
    la mesure dit le contraire, et c'est la mesure qui tranche.** Deux faits
    mesures en Python 3.11 :

    * un lien vers un DOSSIER n'est pas releve du tout (`is_file()` rend
      `False` sur le lien, et `rglob` n'y descend pas) ;
    * un lien vers un FICHIER est bien releve, mais `Path.unlink()` retire
      **le lien**, jamais sa cible.

    La cible externe est donc intacte dans les deux cas, et refuser la
    suppression du lot pour autant serait un blocage sec sur un cas
    inoffensif. Ce test fige les deux comportements : le lot se supprime, et
    ce qu'il designe dehors survit.
    """
    precieux = tmp_path / "precieux"
    precieux.mkdir()
    (precieux / "irremplacable.tiff").write_bytes(b"donnees non commitees")

    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "frames/cible")
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "cible"
    dossier.mkdir(parents=True)
    (dossier / "vraie_frame.tiff").write_bytes(b"legitime")
    (dossier / "lien_vers_dossier").symlink_to(precieux, target_is_directory=True)
    (dossier / "lien_vers_fichier.tiff").symlink_to(precieux / "irremplacable.tiff")

    rapport = remove_project_element(projet, lot_id="cible", dry_run=False)

    assert rapport.supprime is True
    assert (precieux / "irremplacable.tiff").exists(), (
        "la cible externe d'un lien pose dans le lot a ete detruite"
    )
    assert precieux.is_dir(), "le dossier externe designe par un lien a ete detruit"


def test_un_chemin_absolu_reste_refuse(tmp_path):
    """Le cas que la premiere garde couvrait deja : il ne regresse pas."""
    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "/etc")
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="cible", dry_run=False)
    assert "STRICTEMENT" in str(refus.value)


def test_un_dossier_de_lot_LEGITIME_passe_toujours(tmp_path):
    """La garde ne doit pas refuser le cas nominal -- sans ce test, une garde
    qui refuserait TOUT serait verte sur les quatre tests ci-dessus."""
    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "frames/cible")
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "cible"
    dossier.mkdir(parents=True)
    (dossier / "frame.tiff").write_bytes(b"legitime")

    rapport = remove_project_element(projet, lot_id="cible", dry_run=False)
    assert rapport.supprime is True
    assert not (dossier / "frame.tiff").exists()


# ---------------------------------------------------------------------------
# Vague B (arbitrage d'Egan du 2026-08-30) -- la commande `mmu project remove`.
#
# Le mecanisme etait ecrit et teste mais INATTEIGNABLE : aucune commande ne
# l'appelait, donc l'operateur restait devant le `git rm -r` a la main qui a
# detruit des frames non commitees le 2026-08-27. Or l'arbitrage dit que sans
# la suppression, le versionnage n'est qu'une fuite.
# ---------------------------------------------------------------------------


def _cli(*args):
    from mixed_media_utility import cli

    return cli.main(["project", "remove", *args])


def _lignes_de_la_liste_plate(sortie: str) -> list[str]:
    """Le BLOC de liste plate de `project remove`, tel que l'operateur le lit.

    L'entete, puis les lignes indentees de quatre espaces qui la suivent
    IMMEDIATEMENT. Ne pas filtrer sur les chemins attendus : un filtre par
    appartenance rendrait invisible exactement ce que ce banc mesure -- une
    troncature (`[:1]`, `[:-1]`) et un reordonnancement.
    """
    lignes = sortie.splitlines()
    depart = next(i for i, ligne in enumerate(lignes)
                  if ligne.startswith(("Apercu:", "Supprime:")))
    bloc = []
    for ligne in lignes[depart + 1:]:
        if not ligne.startswith("    ") or ligne.startswith("     "):
            break
        bloc.append(ligne.strip())
    return bloc


def test_cli_apercu_par_defaut_n_ecrit_rien(tmp_path, capsys):
    """AC 3.1 -- le rendu plat, mesure sur TROIS fichiers dans DEUX dossiers.

    **Ce que la fabrique mono-fichier laissait passer** (revue 11.13, couche 1
    F1 et couche 2 F6, deux chemins independants). Cet apercu est la seule
    chose que l'operateur lit avant `--confirmer` : sous un cardinal fige a `1`
    (`M14`) ou une liste tronquee au premier chemin (`M15`), la commande
    annonce « 1 fichier(s) », en liste un, et en detruit trois mille.

    **La paire qui vaut demonstration, et elle est dans la fabrique, pas dans
    le code** : sur l'ancienne fabrique, `M16` (`[:-1]`) MOURAIT et `M15`
    (`[:1]`) SURVIVAIT, sur la meme boucle -- a un seul element, `[:-1]`
    n'imprime rien et se fait voir, `[:1]` imprime tout et ne se fait pas voir.
    C'est le point 4 de la regle des fabriques (CLAUDE.md, 2026-09-03) porte
    sur le chemin destructif : les deux BORDS, pas seulement le milieu.

    **Ce que `EPIC11-ARB-243` change ici, et ce qu'il retire.** Le coeur trie
    desormais par chemin POSIX complet : la comparaison de bloc continue de
    porter sur la liste que le COEUR a construite, jamais sur un ordre fige en
    dur, et elle rougit toujours sur une troncature (`[:1]`, `[:-1]`) ou une
    permutation (`reversed`) posee au rendu. Ce qu'elle ne peut PLUS attraper
    est le mutant `M17` -- `sorted(rapport.fichiers_a_supprimer)` a
    l'affichage --, devenu EQUIVALENT : trier une liste deja triee ne change
    rien. Ce n'est pas une perte de mesure, c'est la disparition du defaut que
    `M17` denoncait : il n'y a plus d'ordre du coeur qu'un tri de la CLI
    pourrait trahir. Le dire ici plutot que de laisser croire que la borne
    tient encore.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["lots"][1]["encoded_masters"] = [{"path": "aaa_annexes/master.mov"}]
    projet = _ecrire_projet(tmp_path, manifest)
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12"
    dossier.mkdir(parents=True)
    for nom in ("aaa_premiere.tiff", "zzz_derniere.tiff"):
        (dossier / nom).write_bytes(f"donnees non commitees -- {nom}".encode("utf-8"))
    annexes = projet / "aaa_annexes"
    annexes.mkdir()
    (annexes / "master.mov").write_bytes(b"master encode")

    # L'ordre de reference vient du COEUR, en dry-run (il n'ecrit rien) : ce
    # banc mesure que la CLI rend le bloc du coeur ENTIER et dans son ordre, il
    # ne redit pas quel est cet ordre -- c'est le banc de coeur qui le fait.
    attendu = list(remove_project_element(projet, lot_id="rush-b_12").fichiers_a_supprimer)
    assert len(attendu) == 3, attendu

    code = _cli("--project", str(projet), "--lot", "rush-b_12")

    assert code == 0
    sortie = capsys.readouterr().out
    assert "Apercu" in sortie
    # `EPIC11-ARB-199` : liste PLATE, sans en-tete de nature et sans
    # avertissement sur le suivi par git. La commande ne perd que la
    # classification -- le cardinal et les chemins restent lisibles.
    assert "3 fichier(s)" in sortie, sortie
    assert "suivi par git" not in sortie
    assert "IRRECUPERABLES" not in sortie
    # Le bloc ENTIER, dans l'ordre : cardinal complet, les deux bords presents,
    # et l'ordre du coeur transmis tel quel.
    assert _lignes_de_la_liste_plate(sortie) == attendu, sortie
    # Les deux bords, en EGALITE (`EPIC11-ARB-243`) : `aaa_annexes/` trie AVANT
    # `frames/`, alors que le coeur ASSEMBLE `frames + annexes`. La tete et la
    # queue viennent donc de deux dossiers differents, et l'ordre d'assemblage
    # n'est plus celui du rendu -- c'est ce qui rend le tri mesurable ici aussi.
    assert attendu[0] == "aaa_annexes/master.mov", attendu
    assert attendu[-1] == "frames/rush-b_12/zzz_derniere.tiff", attendu
    for nom in ("aaa_premiere.tiff", "zzz_derniere.tiff"):
        assert (dossier / nom).exists(), "l'apercu a supprime quelque chose"
    assert (annexes / "master.mov").exists(), "l'apercu a supprime quelque chose"
    assert len(json.loads((projet / "project.json").read_text())["lots"]) == 3


def test_cli_confirmer_supprime_reellement(tmp_path, capsys):
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    for lot in manifest["lots"]:
        dossier = projet / lot["frames_dir"]
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(f"c-{lot['lot_id']}".encode())

    code = _cli("--project", str(projet), "--lot", "rush-b_12", "--confirmer")

    assert code == 0
    assert not (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").exists()
    restants = {l["lot_id"] for l in json.loads((projet / "project.json").read_text())["lots"]}
    assert restants == {"rush-a_24", "rush-a_5"}
    # les deux autres lots sont intacts, contenu compris
    assert (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24" / "f.tiff").read_bytes() == b"c-rush-a_24"
    assert (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_5" / "f.tiff").read_bytes() == b"c-rush-a_5"


def test_cli_le_dernier_lot_exige_le_SECOND_consentement(tmp_path, capsys):
    """`--confirmer` seul ne suffit pas : deux consentements empiles (AC 11)."""
    manifest = {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}],
        "lots": [_lot("rush-a_24", "rush-a", "rush-a_24")],
    }
    projet = _ecrire_projet(tmp_path, manifest)

    assert _cli("--project", str(projet), "--lot", "rush-a_24", "--confirmer") == 1
    assert len(json.loads((projet / "project.json").read_text())["lots"]) == 1

    code = _cli("--project", str(projet), "--lot", "rush-a_24",
                "--confirmer", "--confirmer-dernier-lot")
    assert code == 0
    assert json.loads((projet / "project.json").read_text())["lots"] == []


def test_cli_un_lot_inconnu_rend_1_sans_trace_python(tmp_path, capsys):
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    code = _cli("--project", str(projet), "--lot", "nexiste-pas")
    assert code == 1
    erreur = capsys.readouterr().err
    assert "Traceback" not in erreur
    assert "nexiste-pas" in erreur


def test_cli_un_chemin_sortant_du_projet_rend_1_sans_trace_python(tmp_path, capsys):
    """La garde de coeur remonte bien jusqu'a la surface, en code de sortie."""
    precieux = tmp_path / "precieux"
    precieux.mkdir()
    (precieux / "irremplacable.tiff").write_bytes(b"donnees")
    projet = _projet_a_deux_lots_dont_la_cible(tmp_path, "../precieux")

    code = _cli("--project", str(projet), "--lot", "cible", "--confirmer")

    assert code == 1
    assert "Traceback" not in capsys.readouterr().err
    assert (precieux / "irremplacable.tiff").exists()


def test_cli_lot_et_rush_ensemble_sont_refuses_par_argparse(tmp_path):
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    with pytest.raises(SystemExit):
        _cli("--project", str(projet), "--lot", "rush-b_12", "--rush", "rush-a")


# ---------------------------------------------------------------------------
# Revue Opus FINALE : deux destructions totales mesurees, et un blocage sec.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chemin_piege", [".", "frames/..", ""])
def test_un_frames_dir_qui_designe_la_RACINE_ne_detruit_pas_le_projet(tmp_path, chemin_piege):
    """**Pire que le defaut d'origine : il emporte le manifeste lui-meme.**

    La garde ecrivait `reel != racine and racine not in reel.parents`, donc
    elle ACCEPTAIT explicitement la racine. Mesure avant correctif : un
    `frames_dir` valant `"."` faisait supprimer `project.json`, les journaux
    et les frames de tous les autres lots, en rapportant `supprime=True` --
    la catastrophe du 2026-08-27 reproduite par l'outil cense la remplacer, et
    sans meme laisser le manifeste qui aurait dit ce qui a ete perdu.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["lots"][1]["frames_dir"] = chemin_piege
    projet = _ecrire_projet(tmp_path, manifest)
    voisin = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24"
    voisin.mkdir(parents=True)
    (voisin / "f.tiff").write_bytes(b"frame d'un lot voisin")

    if chemin_piege == "":
        # chaine vide : le champ est ignore, aucun fichier n'est vise
        rapport = remove_project_element(projet, lot_id="rush-b_12")
        assert rapport.fichiers_a_supprimer == ()
    else:
        with pytest.raises(ProjectMaintenanceError) as refus:
            remove_project_element(projet, lot_id="rush-b_12", dry_run=False)
        assert "STRICTEMENT" in str(refus.value)

    assert (projet / "project.json").exists(), "le manifeste a ete detruit"
    assert (voisin / "f.tiff").exists(), "les frames d'un lot voisin ont ete detruites"


def test_un_frames_dir_qui_CONTIENT_un_autre_lot_est_refuse(tmp_path):
    """`frames_dir: "frames"` -- l'ancetre commun -- est bien sous le projet,
    et `rglob` y ramasse les frames de TOUS les lots. Mesure avant correctif :
    le lot voisin restait declare au manifeste, ses images etaient mortes."""
    manifest = _manifeste_a_trois_lots()
    manifest["lots"][1]["frames_dir"] = "frames"
    projet = _ecrire_projet(tmp_path, manifest)
    voisin = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24"
    voisin.mkdir(parents=True)
    (voisin / "f.tiff").write_bytes(b"frame d'un lot voisin")

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="rush-b_12", dry_run=False)
    assert "contient" in str(refus.value)
    assert (voisin / "f.tiff").exists()
    manifest_relu = json.loads((projet / "project.json").read_text())
    assert len(manifest_relu["lots"]) == 3


def test_apres_un_echec_partiel_le_geste_reste_REJOUABLE(tmp_path, monkeypatch):
    """**Blocage sec cree par la story elle-meme**, mesure par la revue.

    L'ordre « manifeste d'abord » plus la resolution par `lot_id` faisaient
    que le seul index des fichiers a supprimer disparaissait au moment ou la
    suppression echouait : le second essai rendait « Lot inconnu ». Zero
    issue, l'operateur retombait sur le `rm -rf` manuel -- la fuite que cette
    commande existe pour fermer.
    """
    import pathlib

    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12"
    dossier.mkdir(parents=True)
    (dossier / "frame.tiff").write_bytes(b"contenu")

    original_unlink = pathlib.Path.unlink
    verrouille = {"actif": True}

    def unlink_verrouille(self, *a, **k):
        if verrouille["actif"] and self.name == "frame.tiff":
            raise PermissionError("fichier verrouille (simule)")
        return original_unlink(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "unlink", unlink_verrouille)
    premier = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)
    assert premier.supprime is False

    # Le verrou tombe : le geste doit pouvoir etre REJOUE.
    verrouille["actif"] = False
    second = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)
    assert second.supprime is True, "le lot etait devenu introuvable : blocage sec"
    assert not (dossier / "frame.tiff").exists()
    restants = {l["lot_id"] for l in json.loads((projet / "project.json").read_text())["lots"]}
    assert restants == {"rush-a_24", "rush-a_5"}


# ---------------------------------------------------------------------------
# Les ANNEXES LOURDES -- masters encodes et PDF de planches (Egan, 2026-08-31).
#
# Motif, et il est chiffre : la premiere redaction ne supprimait que les deux
# dossiers de frames du lot. Un master ProRes et une planche imprimee restaient
# sur le disque, c'est-a-dire la moitie LOURDE de ce qu'un lot occupe -- si
# bien que le versionnage, seul, ne faisait qu'aggraver l'occupation qu'il
# etait cense rendre supportable. Mesure de bout en bout sur un projet jetable :
# 2,5 Mo avant, 20 Ko apres.
#
# Les deux filiations sont de NATURE differente, et les tests le mesurent
# separement : le master porte son `path` AU MANIFESTE (filiation ecrite), la
# planche se retrouve par RECALCUL de son nom (filiation deduite). La seconde
# est structurellement plus fragile -- un fichier renomme a la main lui echappe
# -- et c'est pourquoi l'absence est rapportee plutot que tue.
# ---------------------------------------------------------------------------


def _manifeste_a_trois_lots_avec_annexes() -> dict:
    """Regle des fabriques, appliquee a la liste que le code PARCOURT.

    Trois lots distinguables, cible AU MILIEU -- mais surtout : le lot cible
    porte **trois masters distincts** (profils et resolutions differents,
    cas nominal de la story 6.1), la ou une fabrique mono-master laisserait
    vert un `break` premature dans la boucle de collecte. Et les deux autres
    lots portent chacun leur propre master dans le MEME dossier partage
    `outputs/`, ce qu'aucune fabrique a un seul lot ne peut mesurer.
    """
    return {
        "schema_version": "2.1",
        "project_id": "projet",
        "rushes": [{"rush_id": "rush-a"}, {"rush_id": "rush-b"}],
        "lots": [
            {
                "lot_id": "rush-a_24", "rush_id": "rush-a", "frames_dir": "frames/rush-a_24",
                "encoded_masters": [{"path": "outputs/rush-a_24_mmu_prores_422.mov"}],
            },
            {   # <- la cible, au MILIEU, et porteuse de TROIS masters
                "lot_id": "rush-b_12", "rush_id": "rush-b", "frames_dir": "frames/rush-b_12",
                "encoded_masters": [
                    {"path": "outputs/rush-b_12_mmu_prores_422.mov"},
                    {"path": "outputs/rush-b_12_mmu_prores_hq.mov"},
                    {"path": "outputs/rush-b_12_mmu_prores_hq_uhd.mov"},
                ],
            },
            {
                "lot_id": "rush-a_5", "rush_id": "rush-a", "frames_dir": "frames/rush-a_5",
                "encoded_masters": [{"path": "outputs/rush-a_5_mmu_prores_422.mov"}],
            },
        ],
    }


def _peupler_annexes(projet, manifest, avec_planches=True):
    """Deposer sur le disque tout ce que le manifeste declare, plus les
    planches recalculees. Contenus DISTINCTS par fichier: un remplissage
    uniforme rendrait invisible toute erreur d'appariement."""
    from mixed_media_utility.io import naming

    (projet / project_layout.OUTPUTS_DIRNAME).mkdir(exist_ok=True)
    (projet / project_layout.PLANCHES_DIRNAME).mkdir(exist_ok=True)
    for lot in manifest["lots"]:
        dossier = projet / lot["frames_dir"]
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "frame.tiff").write_bytes(f"frames-{lot['lot_id']}".encode())
        for entree in lot.get("encoded_masters", []):
            # Une entree malformee (sans `path`, ou vide) ne depose rien:
            # la fabrique reproduit le manifeste tel qu'il est, elle ne le
            # repare pas -- sans quoi le test de la malformation mesurerait
            # une fixture reparee au lieu du code.
            relatif = entree.get("path")
            if not relatif or relatif.startswith(("/", "..")) or ".." in relatif:
                continue
            chemin = projet / relatif
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(f"master-{relatif}".encode())
        if avec_planches:
            nom = naming.legacy_sheets_pdf_filename(
                manifest["project_id"], lot["rush_id"], lot["lot_id"])
            (projet / project_layout.PLANCHES_DIRNAME / nom).write_bytes(f"pdf-{lot['lot_id']}".encode())


def _empreinte(chemin):
    etat = chemin.stat()
    return (etat.st_ino, etat.st_mtime_ns, etat.st_size)


def test_les_TROIS_masters_du_lot_partent_avec_lui(tmp_path):
    """La filiation ECRITE : `encoded_masters[].path`, lu au manifeste.

    Les trois masters de la cible partent, et **les masters des deux autres
    lots survivent bien qu'ils vivent dans le meme dossier** `outputs/` --
    c'est le point que la nature partagee du dossier rend non trivial, et
    qu'une fabrique a un seul lot ne pourrait pas voir.
    """
    manifest = _manifeste_a_trois_lots_avec_annexes()
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest)

    temoins = {
        chemin: _empreinte(projet / chemin)
        for lot in manifest["lots"] if lot["lot_id"] != "rush-b_12"
        for chemin in (e["path"] for e in lot["encoded_masters"])
    }

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.supprime is True
    for entree in manifest["lots"][1]["encoded_masters"]:
        assert not (projet / entree["path"]).exists(), (
            f"le master {entree['path']} du lot supprime occupe toujours le disque"
        )
    for chemin, avant in temoins.items():
        assert (projet / chemin).exists(), f"le master {chemin} d'un AUTRE lot a ete detruit"
        assert _empreinte(projet / chemin) == avant, f"le master {chemin} a ete touche"
    # Le dossier PARTAGE survit: il porte encore les masters des autres lots.
    assert (projet / project_layout.OUTPUTS_DIRNAME).is_dir()


def test_la_planche_PDF_part_avec_le_lot_par_recalcul_de_son_nom(tmp_path):
    """La filiation DEDUITE : le manifeste ne persiste pas le chemin du PDF,
    seul son nom est reconstructible.

    **La forme reconstruite est l'ANCIENNE** (`legacy_sheets_pdf_filename`,
    `<projet>_<lot>_planches.pdf`) depuis `EPIC11-ARB-171`, et ce n'est pas un
    detail de fixture : on n'atteint ce repli que si le lot ne declare aucun
    `sheets_pdfs`, champ pose par `EPIC11-ARB-90` -- donc que si le manifeste
    est anterieur a l'arbitrage sur le nom, donc que si ses fichiers portent
    l'ancienne convention."""
    from mixed_media_utility.io import naming

    manifest = _manifeste_a_trois_lots_avec_annexes()
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest)

    vise = projet / project_layout.PLANCHES_DIRNAME / naming.legacy_sheets_pdf_filename(
        "projet", "rush-b", "rush-b_12")
    autres = {
        lot["lot_id"]: projet / project_layout.PLANCHES_DIRNAME / naming.legacy_sheets_pdf_filename(
            "projet", lot["rush_id"], lot["lot_id"])
        for lot in manifest["lots"] if lot["lot_id"] != "rush-b_12"
    }
    temoins = {lid: _empreinte(c) for lid, c in autres.items()}
    assert vise.is_file()

    remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert not vise.exists(), "la planche du lot supprime occupe toujours le disque"
    for lid, chemin in autres.items():
        assert _empreinte(chemin) == temoins[lid], f"la planche du lot {lid} a ete touchee"


def test_une_annexe_ABSENTE_est_rapportee_et_non_tue(tmp_path):
    """Un PDF renomme a la main echappe au recalcul de nom -- structurellement.
    Le taire ferait croire a l'operateur qu'il a tout libere ; le rapport le
    NOMME, ce qui est la seule chose que ce mecanisme puisse faire."""
    manifest = _manifeste_a_trois_lots_avec_annexes()
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest, avec_planches=False)

    rapport = remove_project_element(projet, lot_id="rush-b_12")

    assert "planches/projet_rush-b_12_planches.pdf" in rapport.fichiers_attendus_absents
    # Controle negatif : ce qui EST la n'est pas rapporte comme absent.
    for entree in manifest["lots"][1]["encoded_masters"]:
        assert entree["path"] not in rapport.fichiers_attendus_absents


def test_un_master_partage_par_DEUX_lots_est_refuse(tmp_path):
    """Incoherence de manifeste : deux lots declarant le meme `path`.

    Supprimer pour l'un detruirait la sortie de l'autre, sans trace. C'est
    le pendant, au niveau FICHIER, du refus de chevauchement de dossiers --
    necessaire ici precisement parce que `outputs/` est PARTAGE."""
    manifest = _manifeste_a_trois_lots_avec_annexes()
    partage = "outputs/rush-a_24_mmu_prores_422.mov"
    manifest["lots"][1]["encoded_masters"] = [{"path": partage}]
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest)
    avant = _empreinte(projet / partage)

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert "rush-a_24" in str(refus.value), "le refus ne NOMME pas le lot qui partage"
    assert _empreinte(projet / partage) == avant, (
        "le master partage a ete detruit malgre le refus"
    )
    # Le manifeste n'a pas bouge non plus: un refus ne laisse pas d'etat.
    relu = json.loads((projet / "project.json").read_text())
    assert {l["lot_id"] for l in relu["lots"]} == {"rush-a_24", "rush-b_12", "rush-a_5"}


@pytest.mark.parametrize("chemin_hostile", [
    "../../evasion.mov",
    "/etc/evasion.mov",
    "outputs/../../evasion.mov",
])
def test_un_master_declare_HORS_du_projet_est_refuse(tmp_path, chemin_hostile):
    """Meme garde que pour `frames_dir` : un manifeste altere ne doit pas
    pouvoir faire supprimer un fichier hors du dossier projet."""
    manifest = _manifeste_a_trois_lots_avec_annexes()
    manifest["lots"][1]["encoded_masters"] = [{"path": chemin_hostile}]
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest)
    dehors = tmp_path / "evasion.mov"
    dehors.write_bytes(b"fichier hors projet")
    avant = _empreinte(dehors)

    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert dehors.exists() and _empreinte(dehors) == avant, (
        "un fichier HORS du dossier projet a ete touche"
    )


def test_une_entree_de_master_sans_path_ne_fait_rien_deviner(tmp_path):
    """L'inventaire declare ce qui a ete PRODUIT, pas ce qui est PRESENT : une
    entree malformee est ignoree, jamais completee par une supposition."""
    manifest = _manifeste_a_trois_lots_avec_annexes()
    manifest["lots"][1]["encoded_masters"] = [
        {"profile_id": "prores_422"},          # pas de `path`
        {"path": ""},                          # `path` vide
        {"path": "outputs/rush-b_12_mmu_prores_hq.mov"},   # le seul exploitable
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    _peupler_annexes(projet, manifest)

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.supprime is True
    assert not (projet / "outputs/rush-b_12_mmu_prores_hq.mov").exists()
    # Les masters des autres lots n'ont pas ete pris pour cible par defaut.
    assert (projet / "outputs/rush-a_24_mmu_prores_422.mov").exists()
    assert (projet / "outputs/rush-a_5_mmu_prores_422.mov").exists()


# ---------------------------------------------------------------------------
# Les SCANS -- filiation INVERSE et DIFFEREE (`EPIC11-ARB-90`).
#
# Troisieme nature de filiation de ce module, et la plus fragile. A
# l'ingestion le lot n'est PAS connu : le nom du dossier est un slug operateur
# et l'identite du lot voyage dans le QR imprime, decode a l'etape suivante.
# Le lien n'existe donc qu'apres reconstruction, a
# `reconstruction.scan.ingest_slug` en face de `reconstruction.lot_id`.
#
# D'ou un consentement SEPARE : tout le reste que supprime ce module se
# refabrique par calcul depuis le rush source ; un scan porte des planches
# PAPIER numerisees, et les refaire demande de retrouver les feuilles.
# ---------------------------------------------------------------------------


def _manifeste_avec_scan(lot_lie="rush-b_12", slug="scan-WIN") -> dict:
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["reconstruction"] = {
        "lot_id": lot_lie,
        "scan": {"ingest_slug": slug, "scan_dpi": 600},
    }
    return manifest


def _poser_scan(projet, slug="scan-WIN", pages=("p1", "p2")):
    dossier = projet / project_layout.SCANS_DIRNAME / slug
    dossier.mkdir(parents=True)
    for nom in pages:
        (dossier / f"{nom}.tiff").write_bytes(f"scan-{nom}".encode())
    return dossier


def test_le_scan_est_NOMME_dans_l_apercu_mais_PAS_supprime(tmp_path):
    """Le consentement doit etre ECLAIRE : taire l'existence du dossier
    reviendrait a demander `--avec-scans` a l'aveugle."""
    manifest = _manifeste_avec_scan()
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    dossier = _poser_scan(projet)

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.dossier_de_scan == "scans/scan-WIN"
    assert rapport.scan_inclus is False
    assert dossier.is_dir() and len(list(dossier.iterdir())) == 2, (
        "le scan a ete supprime SANS son consentement propre"
    )


def test_avec_scans_inclut_le_dossier(tmp_path):
    manifest = _manifeste_avec_scan()
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    dossier = _poser_scan(projet)

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False, avec_scans=True)

    assert rapport.scan_inclus is True
    assert not dossier.exists(), "le dossier de scan occupe toujours le disque"


def test_avec_scans_en_APERCU_n_ecrit_toujours_RIEN(tmp_path):
    """Les deux consentements sont ORTHOGONAUX: `avec_scans` dit QUOI
    supprimer, `dry_run` dit SI on supprime. Les confondre ferait d'un apercu
    une destruction."""
    manifest = _manifeste_avec_scan()
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    dossier = _poser_scan(projet)
    empreintes = {c.name: _empreinte(c) for c in dossier.iterdir()}

    rapport = remove_project_element(projet, lot_id="rush-b_12", avec_scans=True)

    assert rapport.dry_run is True
    for nom, avant in empreintes.items():
        assert _empreinte(dossier / nom) == avant, "un apercu a touche le scan"
    # Le manifeste non plus n'a pas bouge.
    relu = json.loads((projet / "project.json").read_text())
    assert len(relu["lots"]) == 3


def test_le_scan_d_un_AUTRE_lot_n_est_ni_nomme_ni_supprime(tmp_path):
    """La section `reconstruction` designe UN lot. Supprimer un lot different
    ne doit toucher a rien -- deviner un dossier de scan par ressemblance de
    nom serait le `rm -rf` a l'aveugle que ce module remplace."""
    manifest = _manifeste_avec_scan(lot_lie="rush-a_24")
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    dossier = _poser_scan(projet)

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False, avec_scans=True)

    assert rapport.dossier_de_scan is None
    assert rapport.scan_inclus is False
    assert dossier.is_dir() and len(list(dossier.iterdir())) == 2


def test_un_slug_d_ingestion_SORTANT_du_projet_est_refuse(tmp_path):
    """Meme garde que pour `frames_dir` et les annexes: un manifeste altere ne
    doit pas pouvoir faire supprimer hors du dossier projet."""
    manifest = _manifeste_avec_scan(slug="../../evasion")
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    dehors = tmp_path / "evasion"
    dehors.mkdir()
    (dehors / "precieux.tiff").write_bytes(b"hors projet")
    avant = _empreinte(dehors / "precieux.tiff")

    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(
            projet, lot_id="rush-b_12", dry_run=False, avec_scans=True)

    assert _empreinte(dehors / "precieux.tiff") == avant


def test_un_manifeste_SANS_reconstruction_ne_signale_aucun_scan(tmp_path):
    """Controle negatif: sans lui, un code qui nommerait toujours un dossier
    de scan passerait les tests ci-dessus."""
    manifest = _manifeste_a_trois_lots()
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    _poser_scan(projet)

    rapport = remove_project_element(projet, lot_id="rush-b_12")
    assert rapport.dossier_de_scan is None


def test_TOUS_les_tirages_versionnes_partent_avec_le_lot(tmp_path):
    """**Fuite trouvee en revue.** `_planche_pdf_declaree` ne visait que le
    rang 1, alors que la meme vague permet 99 tirages par lot : supprimer un
    lot laissait ses versions orphelines avec `supprime=True`, et l'entree du
    lot disparaissant du manifeste, plus AUCUNE commande ne pouvait ensuite
    les atteindre. Aggravation : le message de refus de `makepdf` prescrit
    `project remove --lot` en promettant qu'il « retire le lot et ses
    planches ». La promesse etait fausse des que le versionnage avait servi.
    """
    from mixed_media_utility.io import naming

    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()

    # Trois tirages de la CIBLE, et deux d'un AUTRE lot qui doivent survivre.
    vises = [
        naming.legacy_sheets_pdf_filename("projet", "rush-b", "rush-b_12",
                                         version_rank=r)
        for r in (None, 2, 5)
    ]
    epargnes = [
        naming.legacy_sheets_pdf_filename("projet", "rush-a", "rush-a_24",
                                         version_rank=r)
        for r in (None, 3)
    ]
    for nom in vises + epargnes:
        (patches / nom).write_bytes(f"pdf-{nom}".encode())
    temoins = {nom: _empreinte(patches / nom) for nom in epargnes}

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert rapport.supprime is True
    for nom in vises:
        assert not (patches / nom).exists(), (
            f"le tirage {nom} survit au lot: orphelin definitif, plus aucune "
            "commande ne peut l'atteindre"
        )
    for nom, avant in temoins.items():
        assert _empreinte(patches / nom) == avant, (
            f"le tirage {nom} d'un AUTRE lot a ete touche"
        )


def test_un_scan_ARBORESCENT_ne_laisse_pas_de_coquille_vide(tmp_path):
    """Le nettoyage ne connaissait que le dossier PARENT des fichiers
    supprimes, en une passe. Jusqu'ici le mecanisme ne visait que des dossiers
    PLATS (`frames/<lot>/`) ; un scan peut etre arborescent, et il le restait
    avec `supprime=True`."""
    manifest = _manifeste_avec_scan()
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    # **Fixture affinee apres mesure.** La premiere posait un fichier a CHAQUE
    # niveau, si bien que chaque dossier etait le parent direct d'un fichier
    # supprime : le nettoyage generique suffisait, et le mutant qui retirait le
    # balayage du sous-arbre SURVIVAIT. Le cas qui mord est un dossier qui ne
    # contient QUE des sous-dossiers -- il n'est parent d'aucun fichier, donc
    # il n'entre jamais dans `dossiers_touches`.
    racine = projet / project_layout.SCANS_DIRNAME / "scan-WIN"
    (racine / "pages" / "recto").mkdir(parents=True)
    (racine / "pages" / "recto" / "p1.tiff").write_bytes(b"p1")
    (racine / "pages" / "recto" / "p2.tiff").write_bytes(b"p2")
    # Et un dossier entierement VIDE, qui n'a jamais aucun fichier a supprimer.
    (racine / "rebuts").mkdir()

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False, avec_scans=True)

    assert rapport.supprime is True
    assert not racine.exists(), (
        f"le sous-arbre du scan survit: {sorted(p.relative_to(projet).as_posix() for p in racine.rglob('*'))}"
    )


@pytest.mark.parametrize("slug_rentrant", [
    ".", "scan-WIN/..", "../frames/rush-a_24", "a/b", "scans/x",
])
def test_un_slug_qui_RENTRE_dans_le_projet_est_refuse(tmp_path, slug_rentrant):
    """**Le critique de la revue, et l'incident du 2026-08-27 reproduit par
    l'outil cense l'empecher.** Le banc ne couvrait que la variante SORTANTE
    (`../../evasion`), c'est-a-dire exactement le cas que la garde attrapait
    deja : une moitie du domaine. Un slug qui reste SOUS le projet passait
    `_sous_le_projet` et faisait supprimer les frames d'un autre lot -- ou,
    avec `.`, TOUS les dossiers de scan -- avec `supprime=True` et sans un
    mot, pendant que le manifeste continuait de declarer ces lots."""
    manifest = _manifeste_avec_scan(slug=slug_rentrant)
    projet = _ecrire_projet(tmp_path, manifest)
    for lot in ("rush-a_24", "rush-b_12"):
        (projet / project_layout.LEGACY_FRAMES_DIRNAME / lot).mkdir(parents=True)
        (projet / project_layout.LEGACY_FRAMES_DIRNAME / lot / "f.tiff").write_bytes(f"f-{lot}".encode())
    autre_scan = _poser_scan(projet, slug="scan-AUTRE")
    temoin_lot = _empreinte(projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24" / "f.tiff")
    temoins_scan = {c.name: _empreinte(c) for c in autre_scan.iterdir()}

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(
            projet, lot_id="rush-b_12", dry_run=False, avec_scans=True)

    assert "slug" in str(refus.value).lower()
    assert _empreinte(projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24" / "f.tiff") == temoin_lot, (
        "les frames d'un AUTRE lot ont ete detruites"
    )
    for nom, avant in temoins_scan.items():
        assert _empreinte(autre_scan / nom) == avant, (
            "le scan d'un AUTRE lot a ete detruit"
        )
    # Et le manifeste n'a pas bouge: un refus ne laisse pas d'etat.
    relu = json.loads((projet / "project.json").read_text())
    assert len(relu["lots"]) == 3


def test_un_tirage_DECLARE_mais_absent_du_disque_est_SIGNALE(tmp_path):
    """`EPIC11-ARB-90` : un chemin DECLARE au manifeste est une promesse ; son
    absence a l'emplacement promis doit se voir.

    C'est la difference de nature que l'inventaire introduit. Un nom RECALCULE
    et absent est le cas ordinaire (tirage jamais imprime) et se taire est
    juste -- sinon chaque suppression rapporterait 98 absences. Un chemin
    declare et absent, lui, dit qu'un fichier a ete deplace ou renomme, donc
    qu'il occupe toujours le disque quelque part.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["lots"][1]["sheets_pdfs"] = [
        {"path": "planches/projet_rush-b_12_planches.pdf"},
        {"path": "planches/projet_rush-b_12_planches_v2.pdf", "version_rank": 2},
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()
    # Le rang 1 est la ; le rang 2 a ete renomme a la main.
    (patches / "projet_rush-b_12_planches.pdf").write_bytes(b"pdf")
    (patches / "JE-RENOMME-A-LA-MAIN.pdf").write_bytes(b"pdf")

    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    tous = rapport.fichiers_a_supprimer
    assert "planches/projet_rush-b_12_planches.pdf" in tous
    assert "planches/projet_rush-b_12_planches_v2.pdf" in rapport.fichiers_attendus_absents, (
        "un tirage DECLARE et absent n'est pas signale: l'operateur croit "
        "avoir tout libere alors qu'un fichier renomme occupe le disque"
    )
    # Le fichier renomme n'est pas supprime -- on ne peut pas le reconnaitre --
    # mais il n'est plus INVISIBLE, et c'est tout ce que ce mecanisme peut.
    assert (patches / "JE-RENOMME-A-LA-MAIN.pdf").is_file()


def test_l_inventaire_PRIME_sur_le_recalcul_de_nom(tmp_path):
    """Quand le manifeste declare, on ne recalcule plus : un tirage ecrit sous
    un nom que la recette ne produirait pas (projet renomme depuis) reste
    atteignable par sa declaration."""
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet-renomme-depuis"
    manifest["lots"][1]["sheets_pdfs"] = [
        {"path": "planches/ancien-nom-de-projet_rush-b_12_planches.pdf"},
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()
    vise = patches / "ancien-nom-de-projet_rush-b_12_planches.pdf"
    vise.write_bytes(b"pdf")

    remove_project_element(projet, lot_id="rush-b_12", dry_run=False)

    assert not vise.exists(), (
        "le tirage declare n'a pas ete supprime: le recalcul de nom l'aurait "
        "manque, et c'est precisement ce que l'inventaire ferme"
    )


# ---------------------------------------------------------------------------
# DELIER un tirage -- `--tirage` (question d'Egan du 2026-08-31).
#
# « On ne peut pas supprimer le fichier renomme, mais on peut toujours
# supprimer son entree dans la liste ? Il apparaitrait alors comme delie et on
# supprime cette entree comme les autres ? »
#
# Oui, et c'est la dissociation que ce module tenait DEJA pour les rushs :
# l'entree au manifeste et le fichier sur le disque sont deux choses
# differentes. Un rush dont le fichier source vit sur un disque debranche se
# retire quand meme. Sans ce geste, un tirage renomme occupait son rang
# DEFINITIVEMENT -- aucune commande ne pouvait retirer son entree.
# ---------------------------------------------------------------------------


def _projet_a_trois_tirages(tmp_path, presents=("v1", "v2", "v3")):
    """Trois tirages DISTINGUABLES, la cible (rang 2) AU MILIEU de la liste
    que le code parcourt -- un `find` fautif rendant le premier ne se
    demasquerait pas autrement."""
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["lots"][1]["sheets_pdfs"] = [
        {"path": "planches/projet_rush-b_12_planches.pdf"},
        {"path": "planches/projet_rush-b_12_planches_v2.pdf", "version_rank": 2},
        {"path": "planches/projet_rush-b_12_planches_v3.pdf", "version_rank": 3},
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()
    noms = {"v1": "projet_rush-b_12_planches.pdf",
            "v2": "projet_rush-b_12_planches_v2.pdf",
            "v3": "projet_rush-b_12_planches_v3.pdf"}
    for cle in presents:
        (patches / noms[cle]).write_bytes(f"pdf-{cle}".encode())
    return projet, patches


def test_delier_un_tirage_RENOMME_retire_son_entree_SANS_rendre_son_rang(tmp_path):
    """Le cas exact d'Egan. Le fichier du tirage 2 a ete renomme : l'outil ne
    peut pas le reconnaitre, donc il ne le supprime pas -- mais il DELIE son
    entree.

    **Le nom et la docstring affirmaient l'inverse de l'arbitrage** (trouve en
    revue, couche 3) : ils disaient « et le rang 2 redevient disponible »,
    alors que depuis `EPIC11-ARB-92` un rang reste CONSOMME tant qu'un tirage
    posterieur existe -- et le 3 existe ici. L'assertion, elle, ne portait que
    sur les rangs restants, si bien que le test survivait a son propre
    renversement. L'assertion sur le rang est ajoutee avec le nom corrige."""
    projet, patches = _projet_a_trois_tirages(tmp_path, presents=("v1", "v3"))
    (patches / "AILLEURS.pdf").write_bytes(b"le tirage 2, renomme a la main")

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)

    assert rapport.supprime is True
    assert rapport.fichiers_attendus_absents == (
        "planches/projet_rush-b_12_planches_v2.pdf",)
    lot = next(l for l in json.loads((projet / "project.json").read_text())["lots"]
               if l["lot_id"] == "rush-b_12")
    rangs = [e.get("version_rank", 1) for e in lot["sheets_pdfs"]]
    assert rangs == [1, 3], f"le rang 2 n'a pas ete delie: {rangs}"
    # Et le rang 2 reste CONSOMME : le 3 existe, donc le prochain est le 4.
    # C'est ce que le nom de ce test affirmait a l'envers.
    assert rapport.objet_en_queue is False
    assert rapport.rangs_liberables == ()
    assert _prochain_rang(projet) == 4
    # Le fichier renomme n'a pas ete touche -- on ne peut pas le reconnaitre.
    assert (patches / "AILLEURS.pdf").is_file()


def test_delier_ne_touche_NI_les_autres_tirages_NI_les_autres_lots(tmp_path):
    """Controle de portee : la cible est au milieu, ses deux voisins et les
    deux autres lots doivent sortir intacts, mesures a l'inode."""
    projet, patches = _projet_a_trois_tirages(tmp_path)
    voisins = ["projet_rush-b_12_planches.pdf", "projet_rush-b_12_planches_v3.pdf"]
    temoins = {n: _empreinte(patches / n) for n in voisins}
    manifest_avant = json.loads((projet / "project.json").read_text())

    remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)

    for nom, avant in temoins.items():
        assert _empreinte(patches / nom) == avant, f"le tirage {nom} a ete touche"
    manifest_apres = json.loads((projet / "project.json").read_text())
    assert [l["lot_id"] for l in manifest_apres["lots"]] == \
        [l["lot_id"] for l in manifest_avant["lots"]], "un lot a disparu"
    for lot in manifest_apres["lots"]:
        if lot["lot_id"] != "rush-b_12":
            assert "sheets_pdfs" not in lot or lot["sheets_pdfs"] == \
                next(l for l in manifest_avant["lots"]
                     if l["lot_id"] == lot["lot_id"]).get("sheets_pdfs")


def test_delier_supprime_AUSSI_le_fichier_quand_il_est_la(tmp_path):
    """Controle negatif du test du renommage : dans le cas ordinaire, delier
    emporte bien le fichier. Sans lui, un code qui ne supprimerait JAMAIS rien
    passerait le test precedent."""
    projet, patches = _projet_a_trois_tirages(tmp_path)
    vise = patches / "projet_rush-b_12_planches_v2.pdf"
    assert vise.is_file()

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)

    assert not vise.exists()
    assert rapport.fichiers_attendus_absents == ()


def test_delier_en_APERCU_n_ecrit_rien(tmp_path):
    projet, patches = _projet_a_trois_tirages(tmp_path)
    avant = _empreinte(patches / "projet_rush-b_12_planches_v2.pdf")
    manifest_avant = (projet / "project.json").read_text()

    rapport = remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2)

    assert rapport.dry_run is True and rapport.supprime is False
    assert _empreinte(patches / "projet_rush-b_12_planches_v2.pdf") == avant
    assert (projet / "project.json").read_text() == manifest_avant


def test_un_rang_INCONNU_est_refuse_en_nommant_les_rangs_declares(tmp_path):
    """Un refus qui n'aide pas est un refus a moitie : il dit ce qui EXISTE."""
    projet, _ = _projet_a_trois_tirages(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="rush-b_12", planche=True, version=7, dry_run=False)
    assert "[1, 2, 3]" in str(refus.value)


def test_tirage_SANS_lot_est_refuse(tmp_path):
    """Un rush ne porte pas de tirage: viser l'un par l'autre est une erreur
    d'appel, pas une devinette a faire."""
    projet, _ = _projet_a_trois_tirages(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, rush_id="rush-a", planche=True, version=2, dry_run=False)
    assert "lot_id" in str(refus.value)


def test_delier_le_DERNIER_tirage_retire_la_cle_plutot_qu_une_liste_vide(tmp_path):
    """Une liste vide et une cle absente disent la meme chose ; en garder deux
    formes ferait diverger les lecteurs. Le manifeste reste minimal, comme
    pour l'omission stricte des rangs."""
    projet, _ = _projet_a_trois_tirages(tmp_path)
    for rang in (1, 2, 3):
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=rang, dry_run=False)
    lot = next(l for l in json.loads((projet / "project.json").read_text())["lots"]
               if l["lot_id"] == "rush-b_12")
    assert "sheets_pdfs" not in lot, lot.get("sheets_pdfs")


# ---------------------------------------------------------------------------
# UN RANG SE CONSOMME -- `EPIC11-ARB-92` (Egan, 2026-08-31).
#
# « Il ne faut pas rendre le rang. La v2 a ete consommee par la v3 qui se
# trouve apres. » Le motif est PHYSIQUE et il ne vaut que pour les planches :
# reutiliser un rang ferait porter le meme numero a deux feuilles sorties de
# l'imprimante, et une fois l'encre seche aucun fichier ne rattrape cela.
#
# Les trois cas de l'arbitrage, mesures un par un.
# ---------------------------------------------------------------------------


def _lot_avec_tirages(tmp_path, rangs, ligne_d_eau=None):
    """Un lot dont l'inventaire porte les rangs donnes, cible AU MILIEU des
    trois lots du projet."""
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    lot = manifest["lots"][1]
    lot["sheets_pdfs"] = [
        {"path": f"planches/projet_rush-b_12_planches{'' if r == 1 else f'_v{r}'}.pdf",
         **({} if r == 1 else {"version_rank": r})}
        for r in rangs
    ]
    if ligne_d_eau is not None:
        lot["sheets_version_watermark"] = ligne_d_eau
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12" / "f.tiff").write_bytes(b"f")
    patches = projet / project_layout.PLANCHES_DIRNAME
    patches.mkdir()
    for entree in lot["sheets_pdfs"]:
        (projet / entree["path"]).write_bytes(b"pdf")
    return projet


def _prochain_rang(projet):
    import mixed_media_utility.pdf_composition as pdf_composition

    manifest = json.loads((projet / "project.json").read_text())
    return pdf_composition.resolve_sheets_version_rank(
        projet, project_id="projet", rush_id="rush-b", lot_id="rush-b_12",
        manifest=manifest)


def test_CAS_1_retirer_un_tirage_qui_N_EST_PAS_le_dernier_ne_rend_pas_son_rang(tmp_path):
    """« Si la v3 existe et que je supprime la v2, le prochain rang dispo reste
    la v4. On ne libere pas le rang 2 ni le 3. »"""
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    assert _prochain_rang(projet) == 4

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)

    assert rapport.tirage_en_queue is False
    assert rapport.rangs_liberables == ()
    assert _prochain_rang(projet) == 4, "le rang 2 a ete rendu a tort"


def test_CAS_1bis_demander_de_liberer_un_rang_CONSOMME_est_refuse_nommement(tmp_path):
    """Une demande dont l'operateur attend un effet ne se tait pas : la refuser
    en disant pourquoi vaut mieux que l'ignorer, ce qui lui ferait croire le
    rang disponible."""
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False,
            liberer_le_rang=True)
    texte = str(refus.value)
    assert "CONSOMME" in texte and "3" in texte
    # Un refus ne laisse pas d'etat : le tirage est toujours la.
    assert (projet / "planches/projet_rush-b_12_planches_v2.pdf").is_file()


def test_CAS_2_retirer_le_DERNIER_tirage_ouvre_le_CHOIX(tmp_path):
    """« Si v3 n'existe pas et que je supprime v2 : on me demande alors
    confirmation -- liberer le rang 2 (prochaine version = v2) ou le garder
    (prochaine version = v3). »"""
    projet = _lot_avec_tirages(tmp_path, [1, 2])
    apercu = remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2)
    assert apercu.tirage_en_queue is True
    assert apercu.rangs_liberables == (2,), "le choix n'est pas propose"

    # Le DEFAUT garde le rang : ne rien demander ne libere rien.
    remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)
    assert _prochain_rang(projet) == 3


def test_CAS_2bis_liberer_explicitement_rend_le_rang(tmp_path):
    """Controle negatif du precedent : sans lui, un code qui ne libererait
    JAMAIS rien passerait le test du defaut."""
    projet = _lot_avec_tirages(tmp_path, [1, 2])
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False, liberer_le_rang=True)
    assert rapport.rang_libere is True
    assert _prochain_rang(projet) == 2


def test_CAS_3_retirer_la_queue_libere_PLUSIEURS_rangs_d_un_coup(tmp_path):
    """« Je ne libere pas le rang 2 en supprimant v2 car v3 existait. Puis je
    choisis de supprimer v3. On peut alors liberer d'un seul coup v2 et v3, car
    les deux deviennent disponibles. »

    C'est le cas qui exige une MEMOIRE distincte des entrees restantes : apres
    le retrait du v2, plus aucune entree ne porte le rang 2, et pourtant il est
    consomme. Seule la ligne d'eau le sait.
    """
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)
    assert _prochain_rang(projet) == 4, "le rang 2 devait rester consomme"

    apercu = remove_project_element(projet, lot_id="rush-b_12", planche=True, version=3)
    assert apercu.rangs_liberables == (2, 3), (
        f"les deux rangs devenus libres ne sont pas proposes: {apercu.rangs_liberables}"
    )

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=3, dry_run=False, liberer_le_rang=True)
    assert rapport.rang_libere is True
    assert _prochain_rang(projet) == 2, "les deux rangs n'ont pas ete rendus ensemble"


def test_la_ligne_d_eau_SURVIT_au_retrait_de_toutes_les_entrees(tmp_path):
    """Le point que l'inventaire seul ne pouvait pas tenir : un lot dont TOUS
    les tirages ont ete retires sans liberation garde sa ligne d'eau, donc son
    prochain rang. Sans elle, le lot repartirait au rang 1 et reimprimerait un
    numero deja sorti de l'imprimante."""
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    for rang in (2, 3, 1):
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=rang, dry_run=False)
    lot = next(l for l in json.loads((projet / "project.json").read_text())["lots"]
               if l["lot_id"] == "rush-b_12")
    assert "sheets_pdfs" not in lot
    assert lot["sheets_version_watermark"] == 3
    assert _prochain_rang(projet) == 4


# ---------------------------------------------------------------------------
# Corrections de la revue de la vague 2 (2026-08-31). Chaque test nomme le
# defaut qu'il ferme et le regime ou il mord.
# ---------------------------------------------------------------------------


def test_liberer_un_rang_CONSOMME_dont_l_entree_est_DEJA_partie(tmp_path):
    """Les deux issues du refus d'epuisement ne peuvent plus etre refusees ensemble.

    Trouve en revue (couche 2). Retirer le dernier tirage avec le DEFAUT laisse
    la ligne d'eau haute et plus aucune entree qui porte ce rang. Le refus
    d'epuisement proposait alors « retirer le dernier tirage en liberant son
    rang », et ce geste se heurtait a « aucun tirage de rang N ». Les deux
    issues nommees etaient inatteignables, et il ne restait que l'ecrasement
    destructeur -- le mur exact qu'`EPIC11-ARB-89` interdit.
    """
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    # Le tirage 3 part avec le defaut : son rang reste CONSOMME.
    remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=3, dry_run=False)
    manifest = json.loads((projet / "project.json").read_text())
    assert manifest["lots"][1]["sheets_version_watermark"] == 3
    assert _prochain_rang(projet) == 4

    # Le geste que le refus d'epuisement nomme : liberer le rang SEUL.
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=3, dry_run=False, liberer_le_rang=True)
    assert rapport.rang_libere is True
    assert rapport.rangs_liberables == (3,)
    # Le rang 3 est rendu, et le 2 reste consomme puisqu'il est encore declare.
    assert _prochain_rang(projet) == 3


def test_liberer_un_rang_deja_parti_reste_soumis_a_la_condition_de_QUEUE(tmp_path):
    """Le controle negatif du test precedent : la porte neuve n'ouvre pas le milieu."""
    projet = _lot_avec_tirages(tmp_path, [1, 3], ligne_d_eau=3)
    # Le rang 2 a servi (ligne d'eau 3) et son entree est partie -- mais le 3
    # existe encore, donc le 2 n'est PAS en queue.
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False,
            liberer_le_rang=True)
    assert "CONSOMME" in str(erreur.value)
    assert _prochain_rang(projet) == 4


def test_le_refus_d_un_rang_inconnu_NOMME_l_issue_quand_le_rang_a_servi(tmp_path):
    """Un refus qui ne dit pas par ou sortir est un blocage sec (`EPIC11-ARB-89`)."""
    projet = _lot_avec_tirages(tmp_path, [1, 2], ligne_d_eau=5)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=5, dry_run=False)
    message = str(erreur.value)
    assert "--liberer-le-rang" in message
    assert "CONSOMME" in message
    # Controle negatif : un rang JAMAIS employe n'a pas d'issue a proposer,
    # et le message ne doit donc pas la nommer.
    with pytest.raises(ProjectMaintenanceError) as jamais:
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=9, dry_run=False)
    assert "--liberer-le-rang" not in str(jamais.value)


def test_rendre_jusqu_a_l_ORIGINE_RETIRE_la_cle_au_lieu_de_l_ecrire_a_1(tmp_path):
    """Ecrire la ligne d'eau a 1 n'est pas la meme chose que l'absence.

    Trouve en revue (couche 2). `max([...] or [1])` ecrivait
    `sheets_version_watermark: 1`, que la garde du resolveur prenait pour une
    ligne DECLAREE : le prochain tirage repartait a 2 alors que la CLI venait
    d'annoncer que le rang etait rendu. L'omission stricte est ce qui dit
    l'origine (`EPIC11-ARB-88`).
    """
    projet = _lot_avec_tirages(tmp_path, [1])
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=1, dry_run=False, liberer_le_rang=True)
    assert rapport.rang_libere is True
    manifest = json.loads((projet / "project.json").read_text())
    # La CLE EST ABSENTE -- pas presente a 1.
    assert "sheets_version_watermark" not in manifest["lots"][1]
    # Toute la famille est partie : la prochaine planche EST l'origine, qui ne
    # porte aucun fragment de version.
    assert _prochain_rang(projet) == version_ranks.RANG_ORIGINE

    # Controle negatif, et c'est lui qui fait mordre le test : ECRIRE la ligne
    # d'eau a 1 -- ce que faisait `max([...] or [1])` -- donne un resultat
    # DIFFERENT de son absence. Sans ce controle, les deux redactions seraient
    # indiscernables sur ce banc.
    manifest["lots"][1]["sheets_version_watermark"] = 1
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert _prochain_rang(projet) == 2


def test_la_ligne_d_eau_redescend_au_plus_haut_rang_RESTANT_pas_a_1(tmp_path):
    """Ferme le mutant `nouvelle = 1`, survivant faute d'une fabrique distinguable.

    Trouve en revue (couche 3, M3). Les trois tests de liberation existants
    laissaient tous soit rien, soit le seul rang 1 declare : `max(restant)` et
    `1` y etaient indiscernables. Ici la famille garde un rang >= 2 apres le
    retrait, donc les deux valeurs different.
    """
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3, 5])
    rapport = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=5, dry_run=False, liberer_le_rang=True)
    assert rapport.rangs_liberables == (4, 5)
    manifest = json.loads((projet / "project.json").read_text())
    # 3 est le plus haut rang ENCORE declare -- surtout pas 1, qui rendrait
    # les rangs 2 et 3, deja imprimes.
    assert manifest["lots"][1]["sheets_version_watermark"] == 3
    assert _prochain_rang(projet) == 4


def test_un_tirage_qui_designe_la_sortie_d_un_AUTRE_lot_est_REFUSE(tmp_path):
    """La garde du chemin « lot entier », portee au chemin « un tirage ».

    Trouve en revue (couche 1). Ce chemin-ci ne l'avait pas : un
    `sheets_pdfs[].path` designant la sortie d'un autre lot etait supprime, le
    rapport annoncait `supprime=True`, et le manifeste continuait de declarer
    l'autre lot -- une destruction sans trace.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    partage = "planches/partage.pdf"
    manifest["lots"][1]["sheets_pdfs"] = [
        {"path": "planches/projet_rush-b_12_planches.pdf"},
        {"path": partage, "version_rank": 2},
    ]
    # L'AUTRE lot declare le meme fichier.
    manifest["lots"][2]["sheets_pdfs"] = [{"path": partage}]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.PLANCHES_DIRNAME).mkdir()
    for entree in manifest["lots"][1]["sheets_pdfs"]:
        (projet / entree["path"]).write_bytes(b"pdf")

    with pytest.raises(ProjectMaintenanceError):
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)
    # Le fichier de l'autre lot est INTACT.
    assert (projet / partage).is_file()


def test_une_ligne_d_eau_ABIMEE_ne_desactive_pas_le_refus_hors_queue(tmp_path):
    """La copie inline lisait la valeur declaree telle quelle ; le module la borne.

    Trouve en revue (couches 1 et 2). Sur une ligne d'eau booleenne, nulle ou
    plus basse qu'un rang declare, la copie rendait tout rang « en queue » et
    desactivait le refus. `version_ranks.ligne_d_eau` la borne par `max()`.
    """
    for indice, abimee in enumerate((True, 0, -3, 2, "deux")):
        racine = tmp_path / f"cas{indice}"
        racine.mkdir()
        projet = _lot_avec_tirages(racine, [1, 2, 3], ligne_d_eau=abimee)
        with pytest.raises(ProjectMaintenanceError):
            remove_project_element(
                projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False,
                liberer_le_rang=True)


def test_l_apercu_RENSEIGNE_rang_libere_comme_la_suppression_reelle(tmp_path):
    """Sans lui, la CLI proposait un drapeau que l'operateur venait de passer."""
    projet = _lot_avec_tirages(tmp_path, [1, 2])
    apercu = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=True, liberer_le_rang=True)
    assert apercu.rang_libere is True
    # Controle negatif : sans le drapeau, l'apercu ne l'invente pas.
    sans = remove_project_element(
        projet, lot_id="rush-b_12", planche=True, version=2, dry_run=True)
    assert sans.rang_libere is False


# ---------------------------------------------------------------------------
# Le TEXTE que l'operateur lit. Les tests ci-dessus mesurent des attributs
# Python ; la revue (couche 3) a montre que cela laissait passer deux mutants
# qui supprimaient tout l'affichage du rang -- « le CHOIX est pose » n'etait
# mesure nulle part sur ce qui sort reellement.
# ---------------------------------------------------------------------------


def _remove_en_ligne_de_commande(projet, *arguments):
    from mixed_media_utility import cli

    return cli.main(["project", "remove", "--project", str(projet), *arguments])


def test_le_CHOIX_du_rang_est_IMPRIME_quand_le_tirage_est_le_dernier(tmp_path, capsys):
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    _remove_en_ligne_de_commande(projet, "--lot", "rush-b_12", "--planche", "--version", "3")
    rendu = capsys.readouterr().out
    assert "DERNIER a date" in rendu
    assert "--liberer-le-rang" in rendu
    assert "v4" in rendu and "v3" in rendu


def test_un_rang_CONSOMME_est_IMPRIME_comme_tel(tmp_path, capsys):
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    _remove_en_ligne_de_commande(projet, "--lot", "rush-b_12", "--planche", "--version", "2")
    rendu = capsys.readouterr().out
    assert "reste CONSOMME" in rendu
    # Controle negatif : on ne propose pas un drapeau qui serait refuse.
    assert "--liberer-le-rang" not in rendu


def test_le_rang_RENDU_est_IMPRIME_et_jamais_comme_une_liste_VIDE(tmp_path, capsys):
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    _remove_en_ligne_de_commande(
        projet, "--lot", "rush-b_12", "--planche", "--version", "3", "--liberer-le-rang",
        "--confirmer")
    rendu = capsys.readouterr().out
    assert "Rang(s) RENDU(S): 3." in rendu
    # Le defaut ferme : jamais « RENDU(S): » suivi de rien.
    assert "RENDU(S): ." not in rendu
    assert "RENDU(S):\n" not in rendu


def test_rendre_jusqu_a_l_ORIGINE_le_DIT_au_lieu_d_annoncer_le_rang_1(tmp_path, capsys):
    """Le rang 1 n'est pas un rang de VERSION (`VERSION_RANK_MIN` vaut 2)."""
    projet = _lot_avec_tirages(tmp_path, [1])
    _remove_en_ligne_de_commande(
        projet, "--lot", "rush-b_12", "--planche", "--version", "1", "--liberer-le-rang",
        "--confirmer")
    rendu = capsys.readouterr().out
    assert "ORIGINE" in rendu
    assert "aucun fragment de version" in rendu
    assert "RENDU(S): 1" not in rendu


def test_le_message_de_DELIEMENT_ne_contredit_plus_celui_du_rang(tmp_path, capsys):
    """Deux phrases contradictoires sur le meme rang sortaient ensemble."""
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    # Le tirage 2 est renomme a la main : son entree reste, son fichier part.
    (projet / project_layout.PLANCHES_DIRNAME / "projet_rush-b_12_planches_v2.pdf").rename(
        projet / project_layout.PLANCHES_DIRNAME / "autre-nom.pdf")
    _remove_en_ligne_de_commande(
        projet, "--lot", "rush-b_12", "--planche", "--version", "2", "--confirmer")
    rendu = capsys.readouterr().out
    assert "DELIEE" in rendu
    assert "reste CONSOMME" in rendu
    # LE defaut : les deux phrases coexistaient sur le meme rang.
    assert "redevient disponible" not in rendu


def test_le_CHOIX_du_rang_est_IMPRIME_pour_un_LOT_aussi(tmp_path, capsys):
    """`EPIC11-ARB-108` : le meme choix, pose sur le meme texte, pour un lot."""
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["lots"].append({
        "lot_id": "rush-b_12_v2", "rush_id": "rush-b", "fps_target": 12.0,
        "version_rank": 2, "base_lot_id": "rush-b_12",
    })
    projet = _ecrire_projet(tmp_path, manifest)
    for lot in manifest["lots"]:
        dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / lot["lot_id"]
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(b"f")
    _remove_en_ligne_de_commande(projet, "--lot", "rush-b_12_v2")
    rendu = capsys.readouterr().out
    assert "DERNIER a date" in rendu
    assert "lot" in rendu
    assert "--liberer-le-rang" in rendu


# ---------------------------------------------------------------------------
# `EPIC11-ARB-109` -- l'historique de reconstruction PAR LOT.
#
# Choix d'Egan du 2026-08-31 : « un historique par lot ». Il ferme le defaut
# que la section `reconstruction` de tete, SINGULIERE et reecrite a chaque
# passe, faisait porter a la suppression par filiation : un lot reconstruit
# puis suivi d'un AUTRE perdait la trace de son scan, et la commande ne pouvait
# plus retrouver le dossier -- l'operateur retombait sur le `rm -rf` manuel,
# c'est-a-dire la fuite meme que `project remove` existe pour fermer.
# ---------------------------------------------------------------------------


def _projet_a_deux_lots_scannes(tmp_path, *, avec_historique):
    """Deux lots scannes, la section de tete ne parlant QUE du second.

    C'est le regime exact du defaut : le lot vise n'est PAS le dernier
    reconstruit. Une fabrique qui placerait la cible en derniere position ne
    distinguerait pas le registre de la section de tete.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    premier, second = manifest["lots"][0], manifest["lots"][1]
    if avec_historique:
        premier["reconstructions"] = [
            {"ingest_slug": "scan-A", "origin": "scan", "status": "complete"},
            {"ingest_slug": "scan-A-bis", "origin": "scan", "status": "partial"},
        ]
        second["reconstructions"] = [{"ingest_slug": "scan-B", "origin": "scan"}]
    # La section de TETE ne decrit que le DERNIER lot reconstruit.
    manifest["reconstruction"] = {
        "lot_id": second["lot_id"], "scan": {"ingest_slug": "scan-B"},
    }
    projet = _ecrire_projet(tmp_path, manifest)
    for lot in manifest["lots"]:
        dossier = projet / project_layout.LEGACY_FRAMES_DIRNAME / lot["lot_id"]
        dossier.mkdir(parents=True)
        (dossier / "f.tiff").write_bytes(b"f")
    for slug in ("scan-A", "scan-A-bis", "scan-B"):
        pages = projet / project_layout.SCANS_DIRNAME / slug / "pages"
        pages.mkdir(parents=True)
        (pages / "p1.tiff").write_bytes(b"page")
    return projet


def test_le_scan_d_un_lot_qui_n_est_PAS_le_dernier_reconstruit_est_RETROUVE(tmp_path):
    """Le defaut d'origine : la section de tete parlait d'un autre lot."""
    projet = _projet_a_deux_lots_scannes(tmp_path, avec_historique=True)
    rapport = remove_project_element(projet, lot_id="rush-a_24", dry_run=True)
    assert rapport.dossiers_de_scan == ("scans/scan-A", "scans/scan-A-bis")


def test_sans_historique_le_lot_hors_section_de_tete_ne_devine_RIEN(tmp_path):
    """Controle negatif, et il mesure le defaut lui-meme.

    Sur un manifeste anterieur au registre, la trace est perdue : la commande
    ne nomme aucun dossier plutot que d'en deviner un par ressemblance de nom
    -- ce serait le `rm -rf` a l'aveugle que ce module remplace.
    """
    projet = _projet_a_deux_lots_scannes(tmp_path, avec_historique=False)
    rapport = remove_project_element(projet, lot_id="rush-a_24", dry_run=True)
    assert rapport.dossiers_de_scan == ()


def test_le_REPLI_sur_la_section_de_tete_est_conserve(tmp_path):
    """Sans lui, la suppression des scans regresserait sur tout projet existant."""
    projet = _projet_a_deux_lots_scannes(tmp_path, avec_historique=False)
    rapport = remove_project_element(projet, lot_id="rush-b_12", dry_run=True)
    assert rapport.dossiers_de_scan == ("scans/scan-B",)


def test_TOUS_les_dossiers_de_scan_du_lot_sont_supprimes(tmp_path):
    """N'en supprimer qu'un laisserait des images derriere en disant `supprime`."""
    projet = _projet_a_deux_lots_scannes(tmp_path, avec_historique=True)
    rapport = remove_project_element(
        projet, lot_id="rush-a_24", dry_run=False, avec_scans=True)
    assert rapport.supprime is True
    assert not (projet / project_layout.SCANS_DIRNAME / "scan-A").exists()
    assert not (projet / project_layout.SCANS_DIRNAME / "scan-A-bis").exists()
    # Le scan de l'AUTRE lot est intact.
    assert (projet / project_layout.SCANS_DIRNAME / "scan-B" / "pages" / "p1.tiff").is_file()


def test_les_deux_dossiers_sont_NOMMES_avant_le_consentement(tmp_path, capsys):
    """Un consentement demande a l'aveugle sur la moitie n'est pas eclaire."""
    projet = _projet_a_deux_lots_scannes(tmp_path, avec_historique=True)
    _remove_en_ligne_de_commande(projet, "--lot", "rush-a_24")
    rendu = capsys.readouterr().out
    assert "scans/scan-A" in rendu and "scans/scan-A-bis" in rendu
    assert "--avec-scans" in rendu


def test_un_slug_d_historique_qui_REMONTE_est_refuse(tmp_path):
    """La garde de segment vaut pour le registre comme pour la section de tete."""
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["lots"][0]["reconstructions"] = [
        {"ingest_slug": "../frames/rush-b_12"},
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-a_24").mkdir(parents=True)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="rush-a_24", dry_run=True)
    assert "SEGMENT" in str(erreur.value)


def test_la_garde_d_annexe_partagee_MORD_aussi_par_RECALCUL_de_nom(tmp_path):
    """Le repli de la garde etait inerte, et son faux `project_id` le masquait.

    Trouve en revue (couche 1). `_refuser_l_annexe_partagee` interrogeait
    l'autre lot avec `{"project_id": "x"}` : les noms recalcules ne pouvaient
    JAMAIS egaler un chemin reel du projet, donc la garde ne fonctionnait que
    par l'inventaire `sheets_pdfs`. Sur un lot anterieur a l'inventaire -- le
    cas de tout projet existant -- elle ne protegeait rien.

    Ici l'AUTRE lot ne declare AUCUN inventaire : seul le recalcul de nom peut
    le voir.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    autre = manifest["lots"][2]
    # Le nom que `legacy_sheets_pdf_filename` produirait pour l'AUTRE lot.
    nom_recalcule = (f"planches/projet_{autre['lot_id']}_planches.pdf")
    # Le lot VISE declare ce meme fichier dans son inventaire.
    manifest["lots"][1]["sheets_pdfs"] = [
        {"path": "planches/projet_rush-b_12_planches.pdf"},
        {"path": nom_recalcule, "version_rank": 2},
    ]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.PLANCHES_DIRNAME).mkdir()
    for entree in manifest["lots"][1]["sheets_pdfs"]:
        (projet / entree["path"]).write_bytes(b"pdf")

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="rush-b_12", planche=True, version=2, dry_run=False)
    assert autre["lot_id"] in str(erreur.value)
    # La sortie de l'autre lot est INTACTE.
    assert (projet / nom_recalcule).is_file()


# ---------------------------------------------------------------------------
# `EPIC11-ARB-111` -- retirer un master, un scan ou un jeu de frames SEUL.
#
# La lacune que la revue avait nommee : quatre refus d'epuisement de rang
# proposaient de « supprimer le DERNIER master / scan / jeu en liberant son
# rang », et aucune commande ne savait le faire -- seul `--lot` existait, et il
# emporte le lot entier.
#
# Les trois cibles passent par LA MEME fonction que les lots et les tirages
# (`_retirer_un_objet_versionne`) : elles ne fournissent qu'un descripteur de
# famille. C'est ce que ces tests mesurent -- pas trois comportements, un seul.
# ---------------------------------------------------------------------------


def _projet_a_trois_de_chaque(tmp_path):
    """Un lot portant trois masters, trois scans et trois jeux de frames.

    La cible n'est jamais en premiere position et un SECOND lot existe, comme
    l'exige la regle des fabriques du CLAUDE.md.
    """
    lot = {
        "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
        "encoded_masters": [
            {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
            {"path": "outputs/L_mmu_prores_422_v2.mov", "profile_id": "prores_422",
             "version_rank": 2},
            {"path": "outputs/L_mmu_prores_422_v3.mov", "profile_id": "prores_422",
             "version_rank": 3},
            # Un master d'un AUTRE profil : il n'est PAS de cette famille.
            {"path": "outputs/L_mmu_dnxhr_hq.mov", "profile_id": "dnxhr_hq"},
        ],
        "reconstructions": [
            {"ingest_slug": "S"}, {"ingest_slug": "S_v2"}, {"ingest_slug": "S_v3"},
        ],
    }
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
        "lots": [lot, {"lot_id": "AUTRE", "rush_id": "R2"}],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in lot["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")
    for slug in ("S", "S_v2", "S_v3"):
        (projet / project_layout.SCANS_DIRNAME / slug).mkdir(parents=True)
        (projet / project_layout.SCANS_DIRNAME / slug / "p.tiff").write_bytes(b"page")
    for nom in ("L", "L_v2", "L_v3"):
        (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom).mkdir(parents=True)
        (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom / "f.tiff").write_bytes(b"frame")
    return projet


CIBLES = [
    ("master", {"master": True, "profile": "prores_422", "version": 3},
     {"master": True, "profile": "prores_422", "version": 2}),
    ("scan", {"scan": "S", "version": 3}, {"scan": "S", "version": 2}),
    ("lot-scanne", {"lot_scanne": True, "version": 3},
     {"lot_scanne": True, "version": 2}),
]


@pytest.mark.parametrize("nom, queue, milieu", CIBLES)
def test_le_DEFAUT_garde_le_rang_consomme(tmp_path, nom, queue, milieu):
    """Le point 3 d'`EPIC11-ARB-92`, pour les trois cibles neuves."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    rapport = remove_project_element(projet, lot_id="L", dry_run=False, **queue)
    assert rapport.objet_en_queue is True
    assert rapport.rangs_liberables == (3,)
    assert rapport.rang_libere is False


@pytest.mark.parametrize("nom, queue, milieu", CIBLES)
def test_la_LIBERATION_explicite_rend_le_rang(tmp_path, nom, queue, milieu):
    projet = _projet_a_trois_de_chaque(tmp_path)
    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, liberer_le_rang=True, **queue)
    assert rapport.rang_libere is True
    assert rapport.rangs_liberables == (3,)


@pytest.mark.parametrize("nom, queue, milieu", CIBLES)
def test_liberer_un_rang_du_MILIEU_est_refuse(tmp_path, nom, queue, milieu):
    """Le controle negatif : sans lui, une famille mal enumeree passerait.

    C'est exactement le defaut que ma premiere redaction portait sur les
    scans -- elle excluait de la famille ses propres versions, si bien que le
    rang du milieu devenait liberable.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="L", dry_run=False, liberer_le_rang=True, **milieu)
    assert "CONSOMME" in str(erreur.value)


@pytest.mark.parametrize("nom, queue, milieu", CIBLES)
def test_l_APERCU_n_ecrit_rien(tmp_path, nom, queue, milieu):
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant = (projet / "project.json").read_bytes()
    rapport = remove_project_element(
        projet, lot_id="L", dry_run=True, liberer_le_rang=True, **queue)
    assert rapport.dry_run is True
    assert rapport.rangs_liberables == (3,)
    assert (projet / "project.json").read_bytes() == avant


def test_retirer_un_master_ne_touche_ni_les_AUTRES_profils_ni_l_AUTRE_lot(tmp_path):
    """Deux masters d'un lot qui different par le PROFIL ne sont pas deux
    versions l'un de l'autre (`cle_de_famille_de_master`)."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422", version=3)
    assert not (projet / project_layout.OUTPUTS_DIRNAME / "L_mmu_prores_422_v3.mov").exists()
    # Le master de l'autre profil est intact, et son entree aussi.
    assert (projet / project_layout.OUTPUTS_DIRNAME / "L_mmu_dnxhr_hq.mov").is_file()
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    chemins = [e["path"] for e in lot["encoded_masters"]]
    assert "outputs/L_mmu_dnxhr_hq.mov" in chemins
    assert "outputs/L_mmu_prores_422_v3.mov" not in chemins
    # Et la ligne d'eau du profil vise est posee, pas celle de l'autre.
    assert lot["masters_version_watermark"] == {"prores_422": 3}


def test_retirer_un_scan_SEUL_laisse_le_lot_en_place(tmp_path):
    """La difference avec `--avec-scans`, qui accompagne la suppression du lot."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    remove_project_element(projet, lot_id="L", dry_run=False, scan="S", version=3)
    assert not (projet / project_layout.SCANS_DIRNAME / "S_v3").exists()
    assert (projet / project_layout.SCANS_DIRNAME / "S_v2" / "p.tiff").is_file()
    manifest = json.loads((projet / "project.json").read_text())
    lot = manifest["lots"][0]
    assert lot["lot_id"] == "L", "le lot ne doit PAS avoir ete supprime"
    # L'entree d'historique du scan retire part avec lui : la filiation ne doit
    # plus designer un dossier supprime.
    assert [e["ingest_slug"] for e in lot["reconstructions"]] == ["S", "S_v2"]
    assert manifest["scan_version_watermarks"] == {"S": 3}


def test_retirer_un_jeu_de_frames_SEUL_laisse_les_autres_et_le_lot(tmp_path):
    projet = _projet_a_trois_de_chaque(tmp_path)
    remove_project_element(projet, lot_id="L", dry_run=False, lot_scanne=True, version=3)
    assert not (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L_v3").exists()
    assert (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L_v2" / "f.tiff").is_file()
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    assert lot["output_frames_version_watermark"] == 3


def test_DEUX_cibles_fines_ensemble_sont_refusees(tmp_path):
    """Chacune vise un objet versionne different ; les combiner ne veut rien dire."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="L", dry_run=True, master=True, profile="prores_422",
            scan="S")
    assert "--master" in str(erreur.value) and "--scan" in str(erreur.value)


@pytest.mark.parametrize("cible", [
    {"master": True, "profile": "prores_422"}, {"scan": "S"},
    {"lot_scanne": True}])
def test_une_cible_fine_SANS_lot_est_refusee(tmp_path, cible):
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, rush_id="R2", dry_run=True, **cible)
    assert "exige lot_id" in str(erreur.value)


def test_un_master_INCONNU_est_refuse_en_NOMMANT_les_chemins_declares(tmp_path):
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="L", dry_run=True, master=True, profile="h264_delivery")
    message = str(erreur.value)
    # **Ce que le refus doit nommer a CHANGE avec le designateur**
    # (`EPIC11-ARB-224`) : ce n'est plus un chemin -- l'operateur n'en tape
    # plus -- mais les PROFILS declares, c'est-a-dire ce qu'il aurait a taper.
    assert "prores_422" in message, "le refus doit NOMMER ce qui existe"
    assert "dnxhr_hq" in message, "les DEUX profils declares, pas seulement un"


# ---------------------------------------------------------------------------
# Les mutants SURVIVANTS de la revue de la vague 3 (couches 1 et 3).
#
# Chacun de ces tests ferme un trou de banc mesure, pas soupconne : le code
# etait CORRECT, mais rien ne le mesurait, si bien qu'un mutant le detruisait
# sans un rouge.
# ---------------------------------------------------------------------------


def _projet_a_deux_lots_de_la_MEME_famille(tmp_path):
    """Un lot d'origine ET son lot `_v2`, tous deux avec leurs frames.

    Aucune fabrique du depot ne construisait cela -- c'est le remplissage
    uniforme que la regle des fabriques interdit --, et c'est precisement le
    regime ou `--lot-scanne` peut detruire les frames d'un AUTRE lot.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "fps_target": 12.5},
            {"lot_id": "L_v2", "rush_id": "R", "fps_target": 12.5,
             "version_rank": 2, "base_lot_id": "L"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    for nom in ("L", "L_v2"):
        (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom).mkdir(parents=True)
        (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / nom / "f.tiff").write_bytes(b"frame")
    return projet


def test_frames_2_ne_detruit_PAS_les_frames_du_lot_v2(tmp_path):
    """Mutant `M8` de la couche 1 : le seul rempart n'avait aucun test.

    `output-frames/L_v2` est le dossier du LOT v2, pas le rescan v2 du lot
    d'origine. Sans l'exclusion, `--lot L --lot-scanne --version 2` le
    detruisait.
    """
    projet = _projet_a_deux_lots_de_la_MEME_famille(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False,
                               lot_scanne=True, version=2)
    # Story 11.14 : le refus nomme l'objet du vocabulaire (`NATURE_LOT_SCANNE`),
    # la ou il disait « jeu de frames rescannees ».
    assert "aucun lot scanne de rang 2" in str(erreur.value)
    # Les frames du lot v2 sont INTACTES.
    assert (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L_v2" / "f.tiff").is_file()
    # Controle negatif : le lot v2 peut retirer SON propre jeu d'origine.
    rapport = remove_project_element(projet, lot_id="L_v2", dry_run=False,
                                     lot_scanne=True, version=1)
    assert rapport.supprime is True
    assert not (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L_v2").exists()


def test_la_famille_d_un_master_est_bornee_a_SON_profil(tmp_path):
    """Mutant `M9` de la couche 1 : aucune fixture ne donnait deux rangs
    DIFFERENTS a deux profils, donc la portee par profil n'etait pas mesuree."""
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "encoded_masters": [
                {"path": "outputs/L_dnxhr_v5.mov", "profile_id": "dnxhr_hq",
                 "version_rank": 5},
                {"path": "outputs/L_prores.mov", "profile_id": "prores_422"},
                {"path": "outputs/L_prores_v2.mov", "profile_id": "prores_422",
                 "version_rank": 2},
            ]},
            {"lot_id": "AUTRE", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in manifest["lots"][0]["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")

    # Le rang 2 de `prores_422` EST en queue de SA famille, meme si un `dnxhr_hq` de
    # rang 5 existe. Confondre les deux ferait refuser a tort.
    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422", version=2,
        liberer_le_rang=True)
    assert rapport.rang_libere is True
    assert rapport.rangs_liberables == (2,)
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    # La ligne d'eau de `dnxhr_hq` n'a pas ete touchee, celle de `prores_422` est
    # retiree (retour a l'origine).
    assert lot.get("masters_version_watermark", {}).get("dnxhr_hq") is None
    assert "prores_422" not in lot.get("masters_version_watermark", {})
    assert (projet / project_layout.OUTPUTS_DIRNAME / "L_dnxhr_v5.mov").is_file()


def test_rendre_une_cible_FINE_a_l_origine_RETIRE_la_cle(tmp_path):
    """Mutant `M11` de la couche 1 : l'omission stricte etait mesuree pour les
    tirages et pour les lots, jamais pour les trois cibles neuves."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    # On vide la famille `prores_422` jusqu'a l'origine, en partant de la queue.
    # Le designateur ne bouge PAS d'un rang a l'autre depuis `EPIC11-ARB-224`:
    # c'est le meme chemin de famille, seul `version=` change. Une boucle sur
    # des CHEMINS differents ne pourrait plus s'ecrire, et c'est le propos.
    for rang in (3, 2):
        remove_project_element(
            projet, lot_id="L", dry_run=False,
            master=True, profile="prores_422", version=rang,
            liberer_le_rang=True)
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    lignes = lot.get("masters_version_watermark", {})
    assert "prores_422" not in lignes, (
        f"la ligne d'eau devrait etre RETIREE, pas ecrite: {lignes!r}. Un "
        "entier -- fut-il 0 ou 1 -- est une ligne DECLAREE que le resolveur "
        "prendrait pour telle."
    )


def test_liberer_un_rang_AU_DESSUS_de_la_ligne_d_eau_est_refuse(tmp_path):
    """Mutant `M12` de la couche 1 : le garde-fou du « rang seul » n'avait pas
    de controle negatif au-dessus de la ligne d'eau.

    Sans la condition `tirage <= ligne_actuelle`, la commande annoncait un
    succes sur un tirage qui n'a jamais existe.
    """
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="rush-b_12", planche=True, version=50, dry_run=False,
            liberer_le_rang=True)
    message = str(erreur.value)
    assert "aucune planche de rang 50" in message
    # Et le refus ne propose PAS l'issue du rang seul, qui ne s'applique pas.
    assert "--liberer-le-rang" not in message


@pytest.mark.parametrize("nom, cible, prealables", [
    ("master", {"master": True, "profile": "prores_422", "version": 5}, [4]),
])
def test_la_CASCADE_se_rend_d_un_bloc_sur_une_cible_FINE(
    tmp_path, nom, cible, prealables
):
    """Le cas 3 d'`EPIC11-ARB-92`, mesure sur une famille NEUVE.

    L'auditeur a montre que la redescente en cascade n'etait mesuree que sur
    les planches : le mutant `nouvelle = 1` survivait dans
    `_retirer_un_objet_versionne`. La fabrique doit donc laisser un rang >= 2
    apres le retrait, sans quoi `max(restants)` et `1` sont indiscernables.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "encoded_masters": [
                {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
                {"path": "outputs/L_mmu_prores_422_v2.mov", "profile_id": "prores_422",
                 "version_rank": 2},
                {"path": "outputs/L_mmu_prores_422_v3.mov", "profile_id": "prores_422",
                 "version_rank": 3},
                {"path": "outputs/L_mmu_prores_422_v4.mov", "profile_id": "prores_422",
                 "version_rank": 4},
                {"path": "outputs/L_mmu_prores_422_v5.mov", "profile_id": "prores_422",
                 "version_rank": 5},
            ]},
            {"lot_id": "AUTRE", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in manifest["lots"][0]["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")

    # Le rang 4 part SANS liberation : il reste consomme.
    for rang in prealables:
        remove_project_element(projet, lot_id="L", dry_run=False,
                               master=True, profile="prores_422", version=rang)
    # Puis la queue part EN liberant : le 4 et le 5 redeviennent libres
    # ensemble, et la ligne redescend au plus haut rang RESTANT (3), pas a 1.
    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, liberer_le_rang=True, **cible)
    assert rapport.rangs_liberables == (4, 5)
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    assert lot["masters_version_watermark"]["prores_422"] == 3, (
        "la ligne doit redescendre au plus haut rang RESTANT, surtout pas a 1 "
        "-- cela rendrait les rangs 2 et 3, encore declares."
    )


@pytest.mark.parametrize("drapeau", ["avec_scans", "confirmation_dernier_lot"])
@pytest.mark.parametrize("cible", [
    {"planche": True, "version": 2},
    {"master": True, "profile": "prores_422", "version": 2},
    {"scan": "S", "version": 2}, {"lot_scanne": True, "version": 2}])
def test_un_drapeau_de_LOT_sur_une_cible_FINE_est_refuse(tmp_path, drapeau, cible):
    """Trois drapeaux etaient ignores en silence (revue, couche 2).

    `--avec-scans` et `--confirmer-dernier-lot` accompagnent la suppression
    d'un LOT ; sur une cible fine ils n'etaient ni honores ni signales, et le
    dossier de scan n'etait meme pas nomme. L'operateur qui passe un drapeau en
    attend un effet.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    if "planche" in cible:
        pytest.skip("le lot de cette fabrique ne porte pas d'inventaire de tirages")
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(
            projet, lot_id="L", dry_run=True, **{drapeau: True}, **cible)
    assert "aucun sens" in str(erreur.value)


def test_le_message_du_rang_est_au_PLURIEL_correct(tmp_path, capsys):
    """« les jeu de framess posterieurs » est ce que produisait `objet + s`.

    **Ce test EPINGLAIT le mot faux, et c'est ce que F2 a corrige** (revue
    11.14, couche 3). Il assertait `"jeux de frames scannees posterieurs"`,
    c'est-a-dire un litteral fige sur le TROISIEME mot que `EPIC11-ARB-223`
    retire : la couverture existait, elle tenait la mauvaise valeur, et elle
    aurait rougi le jour ou `cli.py` aurait dit juste. Les deux mots sont
    desormais **derives** de la table publiee -- le meme geste que
    `test_le_MENU_nomme_le_lot_scanne_comme_le_coeur_et_comme_E3_8` cote TUI.
    """
    from mixed_media_utility import project_inventory

    singulier, pluriel = project_inventory.libelles_de_nature(
        project_inventory.NATURE_LOT_SCANNE)
    projet = _projet_a_trois_de_chaque(tmp_path)
    _remove_en_ligne_de_commande(projet, "--lot", "L", "--lot-scanne",
                                 "--version", "2")
    rendu = capsys.readouterr().out
    # Story 11.14 : le mot suit le vocabulaire (`EPIC11-ARB-214`). Le controle
    # negatif porte sur le pluriel FAUTIF du mot d'aujourd'hui, pas sur celui
    # d'hier -- sinon il resterait vert en cessant d'observer.
    assert f"{singulier}s" not in rendu
    assert f"{pluriel} posterieurs" in rendu


def test_une_entree_de_scan_ORPHELINE_se_DELIE(tmp_path):
    """MAJEUR 5 de la couche 2 : elle etait immortelle.

    `--tirage` traite ce cas depuis le debut -- l'entree part meme quand le
    fichier est introuvable -- et `--scan` refusait. L'entree ne pouvait plus
    partir qu'en supprimant le lot entier : un blocage sec au sens
    d'`EPIC11-ARB-89`.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    shutil.rmtree(projet / project_layout.SCANS_DIRNAME / "S_v3")
    rapport = remove_project_element(projet, lot_id="L", dry_run=False, scan="S", version=3)
    assert rapport.supprime is True
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    assert [e["ingest_slug"] for e in lot["reconstructions"]] == ["S", "S_v2"]
    # Et le rang reste CONSOMME : delier n'est pas liberer.
    assert lot is not None
    manifest = json.loads((projet / "project.json").read_text())
    assert manifest["scan_version_watermarks"] == {"S": 3}


def test_un_scan_ni_present_ni_DECLARE_est_refuse(tmp_path):
    """Controle negatif : delier ne doit pas devenir « supprimer n'importe quoi »."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, scan="S", version=9)
    message = str(erreur.value)
    # C'est la garde d'APPARTENANCE qui tombe la premiere, et c'est le bon
    # ordre : elle nomme ce que le lot declare, donc elle dit quoi taper.
    assert "ne declare aucun scan de famille" in message
    assert "S_v2" in message, "le refus doit NOMMER les scans du lot"


def test_un_slug_a_ZERO_de_tete_n_est_PAS_un_rang_de_version(tmp_path):
    """m2 de la couche 2 : deux verites portaient le meme nom.

    `validate_ingest_slug` autorise `S_v05` -- un slug operateur legitime, la
    convention n'ecrivant jamais de zero (`EPIC11-ARB-88`) -- pendant que la
    famille le lisait comme le rang 5 de `S`. Le dossier existait et la
    commande repondait « aucun dossier » : objet non supprimable.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["project_id"] = "projet"
    manifest["lots"][1]["reconstructions"] = [{"ingest_slug": "S_v05"}]
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.SCANS_DIRNAME / "S_v05").mkdir(parents=True)
    (projet / project_layout.SCANS_DIRNAME / "S_v05" / "p.tiff").write_bytes(b"x")

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False, scan="S_v05")
    assert rapport.supprime is True
    assert not (projet / project_layout.SCANS_DIRNAME / "S_v05").exists()
    # Il est sa PROPRE origine, donc aucune ligne d'eau de la famille `S`.
    manifest = json.loads((projet / "project.json").read_text())
    assert "S" not in (manifest.get("scan_version_watermarks") or {})


@pytest.mark.parametrize("cible", [{"planche": True}, {"lot_scanne": True}])
def test_un_BOOLEEN_n_est_pas_un_rang(tmp_path, cible):
    """m3 de la couche 2 : `--frames-scannees True` supprimait le jeu d'ORIGINE.

    **Depuis `EPIC11-ARB-224`, le booleen n'est plus sur la CIBLE mais sur le
    RANG** : les deux cibles nommees ici sont devenues des drapeaux nus, donc
    `True` y est la forme normale. Ce que ce test tient est inchange -- un
    booleen ne devient jamais le rang 1 en silence --, il le tient au bon
    endroit, sur `version=`.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=True,
                               version=True, **cible)
    assert "booleen" in str(erreur.value)
    assert (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L").is_dir()


def test_une_ligne_d_eau_BOOLEENNE_ne_devient_pas_un_rang(tmp_path):
    """Mutant `M2` de la couche 2 : le test existant etait tautologique.

    `test_une_ligne_d_eau_ABIMEE_...` parcourt `(True, 0, -3, 2, "deux")` mais
    n'assert que `pytest.raises` -- et sur `True` le refus tombe des DEUX cotes
    de la mutation. Ce qu'il faut mesurer est la valeur PERSISTEE : sans la
    garde `isinstance(bool)`, un `true` JSON peut atteindre la ligne d'eau,
    hors schema.
    """
    from mixed_media_utility.io import version_ranks

    # **Le regime qui MORD, et il est etroit.** `True == 1`, donc une assertion
    # de VALEUR passe des deux cotes de la mutation : c'est ce qui rendait le
    # test precedent tautologique. Le danger est que `max()` rende le BOOLEEN
    # lui-meme -- `max([True, 1, 1])` vaut `True`, pas `1`, parce que `max`
    # rend le premier element maximal --, et qu'il soit persiste tel quel,
    # hors schema. Il faut donc que la ligne declaree soit le maximum.
    ligne = version_ranks.ligne_d_eau(True, {1})
    assert ligne == version_ranks.RANG_ORIGINE
    assert not isinstance(ligne, bool), (
        f"`ligne_d_eau` rend un booleen: {ligne!r} -- il sera persiste tel quel"
    )

    # Puis sur le document, dans le meme regime : une famille sans rang
    # superieur, et une ligne declaree booleenne.
    projet = _lot_avec_tirages(tmp_path, [1], ligne_d_eau=True)
    remove_project_element(projet, lot_id="rush-b_12", planche=True, version=1, dry_run=False)
    lot = next(l for l in json.loads((projet / "project.json").read_text())["lots"]
               if l["lot_id"] == "rush-b_12")
    persistee = lot.get("sheets_version_watermark")
    assert not isinstance(persistee, bool), (
        f"un booleen a atteint la ligne d'eau persistee: {persistee!r}"
    )


def test_poser_une_ligne_d_eau_n_ecrit_QUE_dans_le_lot_vise(tmp_path):
    """Mutant `M5` de la couche 2 : les fermetures pouvaient ecrire partout.

    Cause du trou : dans la fabrique existante, le lot vise est `lots[0]` et
    l'autre n'est jamais relu -- la regle 2 des fabriques, appliquee au niveau
    du LOT et pas seulement de l'objet. Ici la cible est au MILIEU, et les
    deux voisins sont verifies.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "AVANT", "rush_id": "R"},
            {"lot_id": "L", "rush_id": "R", "encoded_masters": [
                {"path": "outputs/L_p.mov", "profile_id": "prores_422"},
                {"path": "outputs/L_p_v2.mov", "profile_id": "prores_422",
                 "version_rank": 2},
            ]},
            {"lot_id": "APRES", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in manifest["lots"][1]["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")

    remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422", version=2)
    lots = json.loads((projet / "project.json").read_text())["lots"]
    par_id = {l["lot_id"]: l for l in lots}
    assert par_id["L"]["masters_version_watermark"] == {"prores_422": 2}
    for voisin in ("AVANT", "APRES"):
        assert "masters_version_watermark" not in par_id[voisin], (
            f"la ligne d'eau a ete ecrite dans le lot {voisin!r}, qui n'etait "
            "pas vise"
        )


def test_un_ECHEC_partiel_n_annonce_PAS_un_rang_rendu(tmp_path, monkeypatch):
    """Mutant `M10` de la couche 2 : le rapport mentait sur l'echec.

    Un echec de suppression restaure le manifeste, donc la ligne d'eau n'a pas
    bouge : annoncer le rang rendu ferait croire a une liberation qui n'a pas
    eu lieu. Le chemin du lot entier tient deja cette regle.
    """
    from pathlib import Path as CheminSysteme

    projet = _projet_a_trois_de_chaque(tmp_path)
    vrai_unlink = CheminSysteme.unlink

    def refuse(self, *args, **kwargs):
        if self.name == "L_mmu_prores_422_v3.mov":
            raise OSError(13, "refuse")
        return vrai_unlink(self, *args, **kwargs)

    monkeypatch.setattr(CheminSysteme, "unlink", refuse)
    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422", version=3,
        liberer_le_rang=True)
    assert rapport.supprime is False
    assert rapport.rang_libere is False, (
        "le rapport annonce un rang RENDU alors que le manifeste a ete restaure"
    )
    # Et le manifeste porte bien encore le master : le geste est rejouable.
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    assert any(e["path"] == "outputs/L_mmu_prores_422_v3.mov"
               for e in lot["encoded_masters"])


def test_frames_1_retire_la_passe_d_ORIGINE_et_le_manifeste_ne_ment_plus(tmp_path):
    """Le rang 1 est accepte, et c'est un choix (revue vague 3, couche 1, J4).

    L'aide disait « RESCANNEES » tout en acceptant le rang 1 : le texte et le
    comportement divergeaient. Refuser le rang 1 laisserait sans issue qui veut
    jeter un jeu d'origine -- un jeu de sortie est une sortie comme une autre.
    Ce qui devait etre corrige, et l'a ete, c'est que le manifeste continuait de
    designer le dossier disparu.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "output_frames_dir": "output-frames/L",
             "frame_count": 8, "reconstructed_frame_count": 8},
            {"lot_id": "AUTRE", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L").mkdir(parents=True)
    (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L" / "f.tiff").write_bytes(b"frame")

    rapport = remove_project_element(projet, lot_id="L", dry_run=False,
                                     lot_scanne=True, version=1)
    assert rapport.supprime is True
    assert not (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME / "L").exists()
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    for cle in ("output_frames_dir", "frame_count", "reconstructed_frame_count"):
        assert cle not in lot, (
            f"{cle} designe encore un dossier supprime: le manifeste ment, et "
            "toute etape aval mourra plus loin sur une erreur sans rapport"
        )


# ---------------------------------------------------------------------------
# Story 11.14, LOT C -- le vocabulaire cote CLI (`EPIC11-ARB-214`, `-220`)
#
# Ce que ce bloc mesure, et **pourquoi il est ecrit ici plutot qu'ailleurs** :
# `EPIC11-ARB-220` tranche le **retrait pur** des noms perimes -- « On retire
# personne ne connait l'outil, personne ne fera l'erreur. **Attention a bien
# modifier les aides !** ». Les deux moities de cette phrase sont deux mesures
# differentes, et aucune des deux ne se deduit de l'autre :
#
# 1. le nom retire n'est **plus accepte**, et le refus est celui d'`argparse`,
#    pas un refus special (`EPIC11-ARB-220` ecarte la derivation d'`ARB-89`
#    qu'avait faite l'AC 4.2 de la fiche : `ARB-89` porte sur une **ecriture
#    par-dessus une sortie existante**, pas sur une option renommee) ;
# 2. **aucune aide ne porte plus le nom retire** -- c'est une frontiere
#    NEGATIVE, et c'est le seul genre de test qui voie revenir un defaut :
#    aucune assertion positive ne verrait reapparaitre une aide perimee.
#
# **Le piege que ce bloc a trouve, et il n'etait pas dans la fiche.** Le nom
# neuf est une EXTENSION du nom retire (`--frames` -> `--frames-scannees`), or
# `argparse` accepte les abreviations non ambigues par defaut : sans
# `allow_abbrev=False` sur le sous-parseur, `mmu project remove --lot L
# --frames 2` continuait de **supprimer pour de vrai**, en silence. Le
# precedent ecrit en tete de `cli.py` (`--charger-profil-de-calibration`)
# affirme « `argparse` refuse l'ancien nom bruyamment, donc aucun script ne
# continue en silence avec un comportement change » : cette affirmation est
# FAUSSE des que le nom neuf prolonge l'ancien. C'est ce que
# `test_le_nom_RETIRE_de_l_option_ne_supprime_RIEN` mesure, et il le mesure sur
# l'etat du manifeste -- pas sur le code de sortie, qu'une abreviation acceptee
# laisserait a `0`.
# ---------------------------------------------------------------------------

import ast as _ast
import re as _re
from pathlib import Path as _Path

_CLI_PY = (_Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
           / "cli.py")

#: Les noms RETIRES des chaines visibles de la CLI, **une ligne par nom**
#: (AC 4.3 : « une frontiere par nom renomme, pas une seule pour l'ensemble --
#: un test global serait vert des que le premier nom est couvert »).
#:
#: Chaque ligne porte son **motif**, et le motif est borne par des frontieres
#: de token plutot que par une sous-chaine : `--frames` ne doit pas attraper
#: `--frames-scannees` ni `--frames-par-page`, et `frames/` ne doit attraper ni
#: `extract-frames/` ni `output-frames/`. C'est le defaut n°2 du lot A, paye
#: la-bas en 248 noms contre quelques dizaines.
#:
#: **Portee de TROIS a CINQ lignes le 2026-09-04, revue 11.14 couche 3, F3.**
#: La table jumelle de la TUI (`tests/unit/tui/test_vocabulaire_de_la_tui.py`,
#: :data:`NOMS_RETIRES_DES_ECRANS`) en portait cinq quand celle-ci en portait
#: trois, et c'est cette dissymetrie -- pas un oubli d'ecriture -- qui a laisse
#: deux `help=` visibles de `cli.py` dire encore « frames rescannees », contre
#: l'exigence verbatim d'Egan sur `EPIC11-ARB-220` (« Attention a bien modifier
#: les aides ! »). Une frontiere qui rend vert ce qu'elle ne tient pas est de la
#: meme famille que le « faux tue » de la section 4.1 de la politique.
#:
#: **Le cinquieme motif n'est PAS celui de la TUI, et c'est deliberé.** La TUI
#: porte `[Rr]escann` nu, ce qui lui va parce qu'aucun de ses ecrans n'emploie
#: le VERBE. `cli.py` l'emploie sept fois, et legitimement : `EPIC11-ARB-105`
#: fait de « rescanner » le geste qui produit une VERSION (« Rescannez les
#: feuilles muettes », « rescanner une feuille », « planche perdue, jamais
#: rescannee »). Un motif nu y rougirait quoi qu'on fasse, donc il serait
#: retire au premier faux positif -- c'est-a-dire desarme. Ce qui est retire
#: est le **nom d'objet**, dans ses DEUX formes du depot : la francaise
#: (« frames rescannees ») et l'anglaise (« rescanned frames », `cli.py:490`).
#: Le volet symetrique
#: :func:`test_le_balayage_ne_confond_PAS_un_nom_VOISIN_avec_un_nom_retire`
#: porte les formes VERBALES comme temoins : il rougit le jour ou un motif
#: d'ici se met a attraper le verbe.
NOMS_RETIRES_DES_AIDES = (
    # (nom retire, motif qui le reconnait, nom qui le remplace)
    ("--frames", r"--frames(?![-\w])", "--lot-scanne"),
    # **Le nom neuf du lot C est devenu un nom RETIRE le 2026-09-05**
    # (`EPIC11-ARB-224`). La chaine de renommages est reelle -- `--frames`,
    # puis `--frames-scannees`, puis `--lot-scanne` -- et chaque maillon doit
    # garder sa ligne : retirer celle de `--frames` au motif qu'un nom plus
    # recent existe rouvrirait le premier defaut. Le motif est borne au jeton
    # avec le `--` en tete, ce qui le distingue du DOSSIER `frames-scannees/`,
    # gele et hors perimetre (`SCAN_FRAMES_DIRNAME`) -- le volet symetrique
    # ci-dessous le mesure.
    ("--frames-scannees", r"--frames-scannees(?![-\w])", "--lot-scanne"),
    # **`EPIC11-ARB-224`, second temps.** Egan, verbatim : « "--tirage" n'est
    # pas un mot de vocabulaire. C'est "planche". » Le motif est borne au
    # jeton : `--planche` ne doit evidemment pas etre attrape, et le volet
    # symetrique le mesure.
    ("--tirage", r"--tirage(?![-\w])", "--planche"),
    ("output-frames", r"output-frames", "frames-scannees"),
    ("frames/", r"(?<![-\w])frames/", "extract-frames/"),
    ("frames rescannees", r"[Ff]rames\s+rescann", "frames scannees"),
    ("rescanned frames", r"[Rr]escann\w*\s+frames", "scanned frames"),
    # **Les deux derniers noms d'OBJET de la passe de scan** (`EPIC11-ARB-223`,
    # « Lot scanne, partout »), ajoutes le 2026-09-05 en fermant les residus
    # `C4` et `C5` de la couche 1. Ils ne sont pas de la meme famille que les
    # trois premiers -- ceux-la nomment un DOSSIER ou une OPTION, ceux-ci
    # nomment l'OBJET --, et c'est justement pourquoi ils avaient echappe :
    # `F3` avait porte la table au niveau de la TUI, dont la table ne connait
    # pas non plus ces deux-la.
    #
    # `lot rescanne` designe l'OBJET (« le lot rescanne a encoder ») la ou le
    # verbe designe l'ACTE (« on rescanne une feuille ») : le motif est donc
    # borne au groupe nominal `lot(s) rescanne(es)` et laisse passer toutes les
    # conjugaisons, ce que les temoins verbaux ci-dessous mesurent.
    ("lot rescanne", r"(?<![-\w])[Ll]ots?\s+rescann", "lot scanne"),
    ("jeu de frames scannees", r"[Jj]eux?\s+de\s+frames\s+scann", "lot scanne"),
)

#: Les OPTIONS retirees du parseur `project remove`, avec leur nom neuf. Table
#: distincte de la precedente : une option se mesure par le **comportement du
#: parseur**, un mot d'aide par un balayage de texte. Les confondre rendrait la
#: mesure d'aide verte pour une option qui marche encore.
#: `argv_retire` et `argv_neuf` sont l'invocation COMPLETE, valeur comprise :
#: depuis `EPIC11-ARB-224` un renommage peut changer la FORME de l'option en
#: meme temps que son nom (`--frames-scannees <rang>` devient le drapeau nu
#: `--lot-scanne` plus `--version <rang>`), et une table qui ne porterait que
#: les noms ferait exercer au test positif une forme qui n'existe plus.
OPTIONS_RETIREES_DE_PROJECT_REMOVE = (
    # (nom retire, argv retire, nom neuf, argv neuf)
    ("--frames", ("--frames", "3"),
     "--lot-scanne", ("--lot-scanne", "--version", "3")),
    ("--frames-scannees", ("--frames-scannees", "3"),
     "--lot-scanne", ("--lot-scanne", "--version", "3")),
)


def _chaines_visibles_de_la_cli(source: str) -> list[tuple[int, str]]:
    """Toute chaine litterale de `cli.py`, dans l'ordre des lignes.

    C'est un **sur-ensemble** des aides : `help=`, `description=`, les messages
    imprimes et les docstrings de commande y sont tous, parce que tous peuvent
    atteindre l'operateur. Un balayage restreint aux seuls `help=` laisserait
    passer un nom perime dans un message de refus, qui est precisement l'endroit
    ou l'operateur le lit.
    """
    return sorted(
        (noeud.lineno, noeud.value)
        for noeud in _ast.walk(_ast.parse(source))
        if isinstance(noeud, _ast.Constant) and isinstance(noeud.value, str)
    )


def _porteuses(chaines: list[tuple[int, str]], motif: str) -> list[tuple[int, str]]:
    """Les chaines du balayage qui portent le motif -- avec leur ligne."""
    compile_ = _re.compile(motif)
    return [(ligne, texte) for ligne, texte in chaines if compile_.search(texte)]


# --- AC 4.1 et 4.3 : le nom neuf fait le geste, le nom retire ne le fait plus -


@pytest.mark.parametrize("retire,argv_retire,neuf,argv_neuf",
                         OPTIONS_RETIREES_DE_PROJECT_REMOVE)
def test_le_nom_NEUF_de_l_option_fait_bien_le_geste(
    tmp_path, retire, argv_retire, neuf, argv_neuf
):
    """Sans cette moitie, le retrait serait satisfait en retirant l'option."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    code = _remove_en_ligne_de_commande(projet, "--lot", "L", *argv_neuf,
                                        "--confirmer")
    assert code == 0
    # Le geste a eu lieu : le jeu vise -- et lui seul -- a disparu du disque.
    restants = sorted(p.name for p in (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME).iterdir())
    assert restants == ["L", "L_v2"], restants


@pytest.mark.parametrize("retire,argv_retire,neuf,argv_neuf",
                         OPTIONS_RETIREES_DE_PROJECT_REMOVE)
def test_le_nom_RETIRE_de_l_option_ne_supprime_RIEN(
    tmp_path, retire, argv_retire, neuf, argv_neuf
):
    """Le coeur de `EPIC11-ARB-220`, et il se mesure sur l'ETAT, pas sur le code.

    Une abreviation acceptee par `argparse` rendrait `0` **et supprimerait** :
    un test qui n'observerait que le code de sortie le verrait passer. On
    compare donc le manifeste et l'arborescence avant/apres.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant_manifeste = (projet / "project.json").read_text()
    avant_arbre = sorted(p.name for p in (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME).iterdir())

    with pytest.raises(SystemExit) as sortie:
        _remove_en_ligne_de_commande(projet, "--lot", "L", *argv_retire,
                                     "--confirmer")

    assert sortie.value.code == 2, (
        f"{retire} n'a pas ete refuse par argparse: il est probablement accepte "
        f"comme ABREVIATION de {neuf} (allow_abbrev)."
    )
    assert (projet / "project.json").read_text() == avant_manifeste
    assert sorted(p.name for p in (projet / project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME).iterdir()) == avant_arbre


@pytest.mark.parametrize("retire,argv_retire,neuf,argv_neuf",
                         OPTIONS_RETIREES_DE_PROJECT_REMOVE)
def test_le_refus_du_nom_RETIRE_est_l_ORDINAIRE_et_ne_nomme_pas_le_neuf(
    tmp_path, retire, argv_retire, neuf, argv_neuf, capsys
):
    """`EPIC11-ARB-220` ecarte la derivation d'`ARB-89` faite par l'AC 4.2.

    Egan, 2026-09-04, verbatim : « On retire personne ne connait l'outil,
    personne ne fera l'erreur. » Donc pas de refus special, pas d'alias, pas de
    message qui nomme le nom neuf : le refus ordinaire d'`argparse` suffit. Ce
    test est la moitie qui empeche de le reintroduire « par prudence ».
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(SystemExit):
        _remove_en_ligne_de_commande(projet, "--lot", "L", *argv_retire)
    rendu = capsys.readouterr().err
    assert retire in rendu, "le refus doit au moins citer ce qui a ete tape"
    assert neuf not in rendu, (
        f"le refus nomme {neuf}: c'est un refus SPECIAL, ecarte par "
        "EPIC11-ARB-220 (retrait pur)."
    )


# --- AC 4.4 : le volet symetrique, sur un nom JAMAIS employe ----------------


def test_un_nom_JAMAIS_employe_rend_le_MEME_refus_ordinaire(tmp_path, capsys):
    """Sans lui, AC 4.3 serait satisfaite par un parseur qui refuse tout.

    `--frmes` n'a jamais existe dans ce depot -- le lot A le mesure de son cote
    (`test_la_mesure_du_cout_MORD_sur_une_option_qui_n_est_pas_du_vocabulaire`).
    Il doit rendre le **meme** genre de refus que le nom retire : c'est la forme
    exacte du retrait pur, ou rien ne distingue un nom perime d'une faute de
    frappe.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(SystemExit) as sortie:
        _remove_en_ligne_de_commande(projet, "--lot", "L", "--frmes", "3")
    assert sortie.value.code == 2
    inconnu = capsys.readouterr().err

    with pytest.raises(SystemExit):
        _remove_en_ligne_de_commande(projet, "--lot", "L", "--frames", "3")
    retire = capsys.readouterr().err

    # Le refus a la MEME forme des deux cotes -- seul le mot tape change.
    assert (inconnu.replace("--frmes", "X") == retire.replace("--frames", "X")), (
        "le nom retire et le nom jamais employe ne recoivent pas le meme refus:\n"
        f"  jamais employe: {inconnu!r}\n  retire        : {retire!r}"
    )


# --- Le meme retrait, sur la surface PYTHON et non sur la ligne de commande -


def test_la_SIGNATURE_du_coeur_ne_porte_AUCUN_mot_cle_RETIRE():
    """`EPIC11-ARB-220` vaut aussi pour l'API Python, et rien ne le mesurait.

    Les trois volets ci-dessus mesurent la LIGNE DE COMMANDE : `--frames` est
    refuse par argparse, comme une faute de frappe. La surface Python, elle, a
    garde `frames=` pendant toute la story sous un **raccord transitoire**
    dont le motif ecrit -- « `cli.py` passe encore l'ancien mot-cle » -- etait
    faux des le lot C : `cli.py` passait `frames_scannees=`. Un raccord sans
    appelant et sans motif est exactement l'alias que cet arbitrage ecarte,
    et il ne se voyait par aucune des trois mesures existantes.

    Frontiere NEGATIVE : aucune assertion positive ne verrait revenir le
    mot-cle. Elle est ancree sur la table `OPTIONS_RETIREES_DE_PROJECT_REMOVE`
    plutot que sur un litteral, pour que le retrait d'une option future soit
    mesure des deux cotes par le meme geste.
    """
    import inspect

    import mixed_media_utility.project_maintenance as pm

    parametres = inspect.signature(pm.remove_project_element).parameters
    # Garde-fou : une lecture cassee rendrait un vide, et « rien de retire »
    # serait vrai d'une signature vide.
    assert "lot_scanne" in parametres, sorted(parametres)
    for retire, _argv_retire, neuf, _argv_neuf in OPTIONS_RETIREES_DE_PROJECT_REMOVE:
        mot_cle = retire.lstrip("-").replace("-", "_")
        assert mot_cle not in parametres, (
            f"`remove_project_element` accepte encore `{mot_cle}=`, le mot-cle "
            f"RETIRE au profit de `{neuf.lstrip('-').replace('-', '_')}=`. "
            "EPIC11-ARB-220 : retrait PUR, ni alias ni refus special.")


# --- L'exigence d'Egan : « Attention a bien modifier les aides ! » ----------


@pytest.mark.parametrize("retire,motif,neuf", NOMS_RETIRES_DES_AIDES)
def test_aucune_chaine_visible_de_la_CLI_ne_porte_le_nom_RETIRE(
    retire, motif, neuf
):
    """Frontiere NEGATIVE, une par nom retire (AC 4.3).

    Elle est negative parce que c'est le seul genre de test qui attrape la
    REINTRODUCTION d'un defaut : aucune assertion positive ne verrait revenir
    une aide perimee.
    """
    chaines = _chaines_visibles_de_la_cli(_CLI_PY.read_text(encoding="utf-8"))
    porteuses = _porteuses(chaines, motif)
    assert porteuses == [], (
        f"{len(porteuses)} chaine(s) visible(s) de cli.py portent encore "
        f"{retire!r}, qui se dit desormais {neuf!r}:\n"
        + "\n".join(f"  cli.py:{ligne}: {texte[:100]!r}" for ligne, texte in porteuses)
    )


def test_le_balayage_des_aides_VOIT_bien_quelque_chose(tmp_path):
    """Volet symetrique du precedent : une frontiere negative sur un balayage
    VIDE serait verte pour rien.

    Deux temoins pris **aux deux bouts du fichier** -- le nom neuf de l'option
    (`cli.py:~4213`) et une option voisine qui, elle, ne se renomme pas
    (`--frames-par-page`, `cli.py:~4393`) -- plus une chaine du tout debut.
    """
    chaines = _chaines_visibles_de_la_cli(_CLI_PY.read_text(encoding="utf-8"))
    assert len(chaines) > 500, len(chaines)
    textes = [t for _, t in chaines]
    for temoin in ("--lot-scanne", "--frames-par-page"):
        assert any(temoin in t for t in textes), temoin


#: **Les formes VERBALES de « rescanner », qu'aucun motif ne doit attraper**
#: (revue 11.14, couche 3, F3). `EPIC11-ARB-105` : rescanner avec un profil
#: ameliore est une VERSION, donc le geste existe et se dit. Ce que la story
#: 11.14 retire est le NOM D'OBJET, jamais l'acte. Les cinq temoins ci-dessous
#: sont pris **verbatim dans `cli.py`** -- l. 869, 1460, 1701, 3814 et 3967 --
#: plutot qu'inventes : un temoin fabrique mesurerait ce que j'imagine du
#: fichier, pas ce qu'il porte.
FORMES_VERBALES_LEGITIMES = (
    "Rescannez les feuilles muettes, ou relancez",
    "renommez la chaine sur l'une des deux feuilles et rescannez",
    "rescanner une feuille.",
    "planche imprimee, on y ajoute une retouche, on rescanne -- le",
    "planche perdue, jamais rescannee",
)


@pytest.mark.parametrize("voisin", [
    # `--frames-scannees` a QUITTE cette liste le 2026-09-05 : ce n'est plus
    # un voisin legitime mais un nom retire, il a sa propre ligne ci-dessus.
    # Le DOSSIER `frames-scannees/`, lui, y reste -- il est gele
    # (`SCAN_FRAMES_DIRNAME`) et c'est ce qui distingue le motif au jeton d'un
    # motif par sous-chaine.
    "--lot-scanne", "--planche", "--frames-par-page", "frames-scannees/",
    "extract-frames/", "output_frames_dir",
    *FORMES_VERBALES_LEGITIMES,
])
def test_le_balayage_ne_confond_PAS_un_nom_VOISIN_avec_un_nom_retire(voisin):
    """Volet symetrique de la frontiere : un motif par sous-chaine rougirait ici.

    C'est le defaut n°2 du lot A, paye en 248 noms contre quelques dizaines :
    `lot` attrapait `slot`, `patch` attrapait `patch_preset_id`. Ici `--frames`
    attraperait `--frames-scannees` et `frames/` attraperait `extract-frames/`,
    si bien que la frontiere serait rouge **quoi qu'on fasse** -- donc inutile.

    **Depuis F3, les temoins portent aussi le VERBE.** Le cinquieme motif de la
    TUI (`[Rr]escann` nu) attraperait les cinq formes verbales ci-dessus, qui
    sont toutes legitimes (`EPIC11-ARB-105`) : le porter tel quel aurait rendu
    la frontiere CLI rouge quoi qu'on fasse, donc jetable. Ce test est ce qui
    empeche de la rendre jetable en la renforcant.
    """
    faux = [(1, f"une aide qui cite {voisin} et rien d'autre")]
    for retire, motif, _neuf in NOMS_RETIRES_DES_AIDES:
        assert _porteuses(faux, motif) == [], (
            f"le motif de {retire!r} attrape son voisin {voisin!r}"
        )


#: Un `cli.py` MINIATURE, cinq chaines litterales **distinguables**, dans
#: l'ordre du fichier. Pas un remplissage uniforme : une permutation ou une
#: troncature ne se voit pas autrement (regle des fabriques, points 1 et 4).
#:
#: C'est un **source Python**, pas une liste de chaines : le temoin doit
#: traverser `_chaines_visibles_de_la_cli` -- le collecteur --, et pas seulement
#: `_porteuses` -- l'appariement. Un collecteur tronque (« ne lire que les
#: `help=` », « sauter la derniere ») est un mode de panne que l'appariement ne
#: peut pas voir, et c'est exactement celui contre lequel la regle des
#: fabriques a ete posee le 2026-09-03.
_SOURCE_TEMOIN = [
    '"""Docstring alpha du module temoin."""',
    'DESCRIPTION = "aide bravo, qui parle de scans"',
    'def commande(args):\n    """Docstring charlie, qui parle de masters."""',
    'AIDE = "aide delta, qui parle de tirages"',
    'print("aide echo, qui parle de rushes")',
]


@pytest.mark.parametrize("retire,motif,neuf", NOMS_RETIRES_DES_AIDES)
@pytest.mark.parametrize("position", [0, 2, 4])
def test_le_balayage_des_aides_MORD_a_CHAQUE_BORD(retire, motif, neuf,
                                                  position):
    """Regle des fabriques, point 4 (2026-09-03) -- en TETE et en QUEUE.

    « La cible au milieu demasque un `find` fautif ; elle **ne demasque pas un
    balayage tronque**, qui est un autre mode de panne. » Et `cli.py` porte
    justement un nom retire tout en tete (`:332`, une valeur de dict), un au
    milieu (`:3822`, un `help=`) et un tout en queue (`:4213`, un nom
    d'option) : les trois formes, aux trois positions.

    Le temoin est un **source Python** traverse par le collecteur : un
    collecteur qui ne lirait que les `help=` raterait la valeur de dict de la
    ligne 332, et aucun test d'appariement ne le verrait.
    """
    lignes = [
        (ligne.replace("alpha", f"alpha {retire}")
              .replace("bravo", f"bravo {retire}")
              .replace("charlie", f"charlie {retire}")
              .replace("delta", f"delta {retire}")
              .replace("echo", f"echo {retire}"))
        if rang == position else ligne
        for rang, ligne in enumerate(_SOURCE_TEMOIN)
    ]
    chaines = _chaines_visibles_de_la_cli("\n".join(lignes) + "\n")
    assert len(chaines) == len(_SOURCE_TEMOIN), (
        f"le collecteur rend {len(chaines)} chaines pour "
        f"{len(_SOURCE_TEMOIN)} : il en saute")
    porteuses = _porteuses(chaines, motif)
    assert len(porteuses) == 1, (
        f"le balayage rate {retire!r} en position {position} sur "
        f"{len(_SOURCE_TEMOIN)} : {porteuses}")
    assert retire.rstrip("/") in porteuses[0][1]


# ---------------------------------------------------------------------------
# Story 11.14, LOT C -- l'ARBORESCENCE que la CLI cree et qu'elle MONTRE
#
# Elargissement demande par Egan le 2026-09-04, borne par `EPIC11-ARB-221` et
# `-222` : le regime est « surfaces seules ». Les VALEURS de chemin suivent le
# dossier reellement ecrit ; les NOMS DE CLES du manifeste ne bougent pas, et
# aucune commande de conversion n'existe -- les anciens dossiers restent
# reconnus en LECTURE indefiniment (patron `LEGACY_SOURCES_DIRNAME`).
#
# Le chemin POC (`PROJECT_SUBDIRS`, `_create_project_layout`,
# `_build_sheet_manifest`, `poc_build_sheet`) est le dernier de `cli.py` a
# composer un nom de dossier a la main. Il est mesure ici plutot qu'ailleurs
# parce que c'est `cli.py` qui l'ecrit, et que `cli.py` est le perimetre de ce
# lot.
# ---------------------------------------------------------------------------

def test_le_chemin_POC_cree_le_dossier_du_VOCABULAIRE_et_jamais_l_ancien(tmp_path):
    """`EPIC11-ARB-171` applique aux dossiers : ecrire le neuf, ne plus ecrire
    l'ancien. Le nom d'avant survit comme constante RECONNUE, jamais ecrite."""
    from mixed_media_utility import cli
    from mixed_media_utility.io import project_layout

    projet = tmp_path / "projet"
    cli._create_project_layout(projet)

    assert (projet / project_layout.EXTRACT_FRAMES_DIRNAME).is_dir()
    assert not (projet / project_layout.LEGACY_FRAMES_DIRNAME).exists(), (
        "le chemin POC cree encore le dossier a l'ancien nom : il est RECONNU, "
        "il n'est plus JAMAIS ecrit")


def test_PROJECT_SUBDIRS_ne_compose_AUCUN_nom_de_dossier_a_la_main():
    """Frontiere NEGATIVE : la constante d'arborescence est nommee une seule
    fois dans le depot (story 6.1, AC 12), et le POC ne la recopie pas.

    Le volet symetrique est juste apres l'assertion negative : sans lui, la
    frontiere serait verte pour une liste vide.
    """
    from mixed_media_utility import cli
    from mixed_media_utility.io import project_layout

    assert project_layout.LEGACY_FRAMES_DIRNAME not in cli.PROJECT_SUBDIRS
    assert project_layout.LEGACY_OUTPUT_FRAMES_DIRNAME not in cli.PROJECT_SUBDIRS
    # ... et la liste dit bien quelque chose : le nom NEUF y est.
    assert project_layout.EXTRACT_FRAMES_DIRNAME in cli.PROJECT_SUBDIRS


def test_le_manifeste_POC_garde_sa_CLE_et_ne_bouge_que_sa_VALEUR(tmp_path):
    """`EPIC11-ARB-221`, verbatim : « la cle `"frames"` NE BOUGE PAS ; seule la
    VALEUR suit le dossier reellement ecrit ».

    Les deux moities sont mesurees ensemble parce qu'elles se contredisent
    facilement : renommer la cle casserait la lecture des projets deja sur
    disque, et laisser la valeur designerait un dossier qui n'existe plus.

    La valeur est comparee au dossier **reellement cree**, jamais a un litteral
    recopie : un litteral ferait un second lieu ou le nom vivrait, et il
    resterait vert le jour ou les deux divergeraient.
    """
    import types

    from mixed_media_utility import cli
    from mixed_media_utility.io import project_layout

    projet = tmp_path / "projet"
    cli._create_project_layout(projet)
    frames = sorted(
        (projet / project_layout.EXTRACT_FRAMES_DIRNAME).parent.iterdir())
    assert (projet / project_layout.EXTRACT_FRAMES_DIRNAME) in frames

    manifeste = cli._build_sheet_manifest(
        projet,
        types.SimpleNamespace(dpi=600, fps=2.0),
        projet / project_layout.LEGACY_SOURCES_DIRNAME / "rush.mp4",
        [projet / project_layout.EXTRACT_FRAMES_DIRNAME / "a.tiff",
         projet / project_layout.EXTRACT_FRAMES_DIRNAME / "b.tiff"],
        1920, 1080, 25.0,
    )

    assert "frames" in manifeste["inputs"], (
        "la CLE du manifeste POC a ete renommee : EPIC11-ARB-221 l'interdit, "
        "cela casserait la lecture des projets deja sur disque")
    assert manifeste["inputs"]["frames"] == \
        f"{project_layout.EXTRACT_FRAMES_DIRNAME}/", manifeste["inputs"]


# ---------------------------------------------------------------------------
# `EPIC11-ARB-224` -- UNE SEULE syntaxe de designation
#
# Egan, 2026-09-05, verbatim : « il faut harmoniser : designer l'objet par son
# nom, ou par son chemin puis la version concernee. Mais il faut que ce soit la
# meme syntaxe pour tous les objets du projet. »
#
# La regle en une ligne : **le designateur nomme la FAMILLE, `--version` porte
# le rang.** Ce que ce bloc mesure, et pourquoi chaque moitie est necessaire :
#
# 1. la forme NEUVE fait le geste, sur les QUATRE cibles fines et a CHAQUE
#    BORD de la famille (regle des fabriques, point 4) -- sans cette moitie,
#    l'harmonisation serait satisfaite en cassant la commande ;
# 2. la forme ANCIENNE ne supprime RIEN, et ca se mesure sur l'ETAT du projet
#    plutot que sur un code de sortie -- une valeur avalee en silence rendrait
#    `0` **et** supprimerait, ce qui est exactement le piege paye par le lot C
#    avec l'abreviation `--frames` ;
# 3. sans `--version`, la cible est le rang d'ORIGINE (`EPIC11-ARB-88` : le
#    rang d'origine ne porte aucun fragment, et son absence le dit ici aussi) ;
# 4. `--lot` NE BOUGE PAS -- c'est la seule asymetrie, elle est deliberee, et
#    une frontiere la tient pour qu'aucune harmonisation ulterieure ne la
#    « corrige » : le `lot_id` est une cle de manifeste gelee par
#    `EPIC11-ARB-221`, et c'est le CONTEXTE des quatre cibles fines.
# ---------------------------------------------------------------------------


#: Les quatre cibles fines, avec ce qui les designe et ce qui les nomme sur le
#: disque. **Une ligne par cible, et les valeurs sont DISTINGUABLES** : un
#: appariement inverse entre la cible et son dossier ne se voit pas autrement
#: (regle des fabriques, point 1).
#:
#: `_designation(rang)` rend l'`argv` de la forme NEUVE ; `_ancienne(rang)`
#: celui de la forme retiree. Les deux vivent cote a cote parce que le test
#: negatif doit exercer exactement ce que le test positif remplace -- sinon il
#: mesurerait une autre panne que celle qu'on ferme.
CIBLES_DE_LA_DESIGNATION = (
    (
        "master",
        lambda rang: ["--master", "--profile", "prores_422"]
                     + ([] if rang == 1 else ["--version", str(rang)]),
        # L'ancienne forme est un CHEMIN, et le retrait est pur : depuis la
        # correction du 2026-09-05, aucun designateur de `remove` ne porte plus
        # d'emplacement -- il est au manifeste, c'est lui qui le sait.
        lambda rang: ["--master", "outputs/L_mmu_prores_422"
                      + ("" if rang == 1 else f"_v{rang}") + ".mov"],
        lambda rang: ("outputs", "L_mmu_prores_422"
                      + ("" if rang == 1 else f"_v{rang}") + ".mov"),
    ),
    (
        "scan",
        lambda rang: ["--scan", "S"]
                     + ([] if rang == 1 else ["--version", str(rang)]),
        lambda rang: ["--scan", "S" + ("" if rang == 1 else f"_v{rang}")]
                     if rang != 1 else None,
        lambda rang: ("scans", "S" + ("" if rang == 1 else f"_v{rang}")),
    ),
    (
        "lot-scanne",
        lambda rang: ["--lot-scanne"]
                     + ([] if rang == 1 else ["--version", str(rang)]),
        lambda rang: ["--frames-scannees", str(rang)],
        lambda rang: ("output-frames", "L" + ("" if rang == 1 else f"_v{rang}")),
    ),
)


@pytest.mark.parametrize("nom,neuve,_ancienne,sur_le_disque",
                         CIBLES_DE_LA_DESIGNATION)
@pytest.mark.parametrize("rang", (1, 2, 3), ids=("tete", "milieu", "queue"))
def test_ARB224_la_forme_NEUVE_retire_la_bonne_version_a_CHAQUE_BORD(
    tmp_path, nom, neuve, _ancienne, sur_le_disque, rang
):
    """La moitie positive, aux trois bords de la famille.

    **Le bord compte ici plus qu'ailleurs**, et c'est mesure plutot que
    suppose : le rang 1 est le seul qui ne porte AUCUN fragment, donc le seul
    ou le designateur de famille et le nom reel de l'objet coincident. Un
    resolveur qui recomposerait `<famille>_v<rang>` sans cas particulier
    chercherait `S_v1` et ne trouverait rien ; un resolveur qui rendrait
    toujours le premier element de la famille passerait le rang 1 et raterait
    les deux autres. Les trois bords separent ces deux modes de panne.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    dossier, cible = sur_le_disque(rang)
    assert (projet / dossier / cible).exists(), "la fabrique ne pose pas la cible"
    avant = sorted(p.name for p in (projet / dossier).iterdir())

    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", *neuve(rang), "--confirmer")

    assert code == 0
    apres = sorted(p.name for p in (projet / dossier).iterdir())
    assert apres == [n for n in avant if n != cible], (
        f"{nom} rang {rang} : le retrait n'a pas porte sur {cible!r}")


@pytest.mark.parametrize("nom,neuve,ancienne,sur_le_disque",
                         CIBLES_DE_LA_DESIGNATION)
@pytest.mark.parametrize("rang", (2, 3), ids=("milieu", "queue"))
def test_ARB224_la_forme_ANCIENNE_ne_supprime_RIEN(
    tmp_path, capsys, nom, neuve, ancienne, sur_le_disque, rang
):
    """Frontiere NEGATIVE, et elle se mesure sur l'ETAT, pas sur le code.

    Aucun test positif ne verrait revenir `--tirage 2`, `--frames-scannees 2`
    ou `--scan S_v3` : c'est la seule facon d'attraper une reintroduction. Et
    l'observation porte sur le manifeste et l'arborescence parce qu'une valeur
    avalee en silence -- une abreviation `argparse`, un fragment `_vN` relu
    comme une famille -- rendrait `0` **en supprimant**, ce qu'un test sur le
    code de sortie laisserait passer (piege paye par le lot C).
    """
    argv = ancienne(rang)
    if argv is None:
        pytest.skip("cette cible n'a pas d'ancienne forme a ce rang")
    projet = _projet_a_trois_de_chaque(tmp_path)
    dossier, _cible = sur_le_disque(rang)
    avant_manifeste = (projet / "project.json").read_bytes()
    avant_arbre = sorted(p.name for p in (projet / dossier).iterdir())

    try:
        code = _remove_en_ligne_de_commande(projet, "--lot", "L", *argv,
                                            "--confirmer")
    except SystemExit as sortie:      # le refus d'`argparse`, code 2
        code = sortie.code
    capsys.readouterr()

    assert code != 0, (
        f"la forme retiree {argv!r} a ete ACCEPTEE : elle est probablement "
        "relue comme la forme neuve, ce qui rend le retrait cosmetique")
    assert (projet / "project.json").read_bytes() == avant_manifeste
    assert sorted(p.name for p in (projet / dossier).iterdir()) == avant_arbre


def test_ARB224_la_planche_perd_sa_VALEUR_et_devient_un_drapeau_nu(tmp_path):
    """`--tirage 2` n'est plus une forme du langage, `--planche --version 2` l'est.

    **DEUX retraits dans une seule ligne de commande**, et c'est deliberement
    mesure ensemble : le nom (`--tirage` -> `--planche`, `EPIC11-ARB-224` sur
    renversement d'Egan -- « "--tirage" n'est pas un mot de vocabulaire. C'est
    "planche". ») ET la forme (la valeur passe dans `--version`). Un test qui
    ne verifierait que le nom laisserait passer `--planche 2`.

    Cette cible est traitee a part des trois autres parce que sa fabrique
    l'est : une planche vit dans `sheets_pdfs`, pas sous un dossier enumerable.
    """
    projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
    avant = (projet / "project.json").read_bytes()

    # Les TROIS formes retirees : l'ancien nom avec sa valeur, l'ancien nom
    # NU -- un retrait de nom qui laisserait le drapeau vivant serait un
    # retrait cosmetique --, et le nom neuf avec une valeur. Aucune des trois
    # ne doit rien ecrire.
    for argv in (("--tirage", "2"), ("--tirage",), ("--planche", "2")):
        with pytest.raises(SystemExit) as sortie:
            _remove_en_ligne_de_commande(projet, "--lot", "rush-b_12", *argv,
                                         "--confirmer")
        assert sortie.value.code == 2, argv
        assert (projet / "project.json").read_bytes() == avant, argv

    code = _remove_en_ligne_de_commande(
        projet, "--lot", "rush-b_12", "--planche", "--version", "2", "--confirmer")
    assert code == 0
    rangs = [e.get("version_rank", 1) for e in
             json.loads((projet / "project.json").read_text())["lots"][1]["sheets_pdfs"]]
    assert rangs == [1, 3], rangs


@pytest.mark.parametrize("cible,attendu", [
    (["--planche"], "sheets_pdfs"),
    (["--lot-scanne"], "output-frames"),
    (["--scan", "S"], "scans"),
    (["--master", "--profile", "prores_422"], "outputs"),
])
def test_ARB224_sans_version_la_cible_est_le_rang_d_ORIGINE(tmp_path, cible, attendu):
    """`EPIC11-ARB-88` : le rang d'origine ne porte AUCUN fragment.

    Son absence dans le designateur dit donc l'origine, et ce n'est pas une
    convention inventee ici -- c'est la lecture que `_rang_et_base_du_slug`
    fait deja d'un slug sans fragment.

    Le controle negatif est dans l'assertion : ce sont les rangs 2 et 3 qui
    doivent RESTER. Un resolveur qui viserait le dernier rang au lieu de
    l'origine passerait une assertion de simple presence.
    """
    if attendu == "sheets_pdfs":
        projet = _lot_avec_tirages(tmp_path, [1, 2, 3])
        assert _remove_en_ligne_de_commande(
            projet, "--lot", "rush-b_12", *cible, "--confirmer") == 0
        rangs = [e.get("version_rank", 1) for e in
                 json.loads((projet / "project.json").read_text())
                 ["lots"][1]["sheets_pdfs"]]
        assert rangs == [2, 3], rangs
        return
    projet = _projet_a_trois_de_chaque(tmp_path)
    assert _remove_en_ligne_de_commande(
        projet, "--lot", "L", *cible, "--confirmer") == 0
    restants = sorted(p.name for p in (projet / attendu).iterdir())
    origines = {"output-frames": "L", "scans": "S",
                "outputs": "L_mmu_prores_422.mov"}
    assert origines[attendu] not in restants, restants
    assert len(restants) >= 2, (
        "les rangs 2 et 3 doivent RESTER : sans eux l'assertion ci-dessus "
        "serait vraie d'un resolveur qui vide la famille")


def test_ARB224_version_SANS_cible_fine_est_refuse_nommement(tmp_path, capsys):
    """Le rang d'un LOT vit dans son `lot_id`, et il n'y a pas de second lieu.

    `--version` se lie comme `--liberer-le-rang` se lie deja : a la cible fine
    quand il y en a une, au lot sinon. Or le lot est designe par son `lot_id`
    COMPLET (`EPIC11-ARB-221` gele les cles de manifeste), fragment inclus :
    un `--version` qui se lierait au lot ferait une SECONDE lecture du rang du
    lot, c'est-a-dire deux verites pour un fait. Le refus est nomme et il porte
    l'issue -- jamais un blocage sec, jamais un drapeau sans effet
    (« un drapeau sans effet est un mensonge », deja paye deux fois ici).
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant = (projet / "project.json").read_bytes()

    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--version", "2", "--confirmer")

    assert code == 1
    erreur = capsys.readouterr().err
    assert "--version" in erreur and "lot_id" in erreur, erreur
    assert (projet / "project.json").read_bytes() == avant


def test_ARB224_le_lot_garde_son_identifiant_COMPLET(tmp_path):
    """La seule asymetrie, et elle se tient plutot qu'elle ne se rappelle.

    Une harmonisation ulterieure qui decouperait `--lot` en famille + rang
    ferait rougir ce test. C'est voulu : `EPIC11-ARB-221` gele les cles de
    manifeste, et `--lot` est le CONTEXTE des quatre cibles fines --
    `--lot rush-001_5 --version 2 --tirage` ne pourrait plus se lire.
    """
    manifest = _manifeste_a_trois_lots()
    manifest["lots"][1]["lot_id"] = "rush-b_12_v2"
    projet = _ecrire_projet(tmp_path, manifest)
    (projet / project_layout.LEGACY_FRAMES_DIRNAME / "rush-b_12").mkdir(parents=True)

    assert _remove_en_ligne_de_commande(
        projet, "--lot", "rush-b_12_v2", "--confirmer") == 0
    restants = [l["lot_id"] for l in
                json.loads((projet / "project.json").read_text())["lots"]]
    assert restants == ["rush-a_24", "rush-a_5"], restants


# --- La meme grammaire sur la surface PYTHON -------------------------------


@pytest.mark.parametrize("mot_cle", ("planche", "master", "lot_scanne"))
def test_ARB224_un_ENTIER_sur_un_drapeau_nu_est_refuse_nommement(tmp_path, mot_cle):
    """Le symetrique exact de l'ancien refus « un booleen n'est pas un rang ».

    Avant `EPIC11-ARB-224`, `planche=True` etait refuse parce qu'un booleen
    n'est pas un rang. Depuis, c'est l'inverse qui mord, et il mord PLUS FORT :
    `planche=2` est **vrai** au sens de Python, donc un appelant qui aurait
    garde l'ancien mot-cle verrait le drapeau leve et le rang retomber a
    l'ORIGINE -- il supprimerait le tirage 1 en croyant supprimer le 2. Une
    destruction silencieuse de la mauvaise version, sans un mot.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False,
                               **{mot_cle: 2})
    message = str(erreur.value)
    assert "drapeau" in message.lower() and "--version" in message, message


def test_ARB224_un_BOOLEEN_n_est_pas_un_rang_de_version(tmp_path):
    """`version=True` vaudrait `1` en Python : le rang d'ORIGINE, en silence."""
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False,
                               lot_scanne=True, version=True)
    assert "booleen" in str(erreur.value).lower()


@pytest.mark.parametrize("mot_cle,valeur", [
    ("scan", "S_v3"),
])
def test_ARB224_un_designateur_qui_porte_un_fragment_est_refuse(
    tmp_path, mot_cle, valeur
):
    """Le designateur nomme la FAMILLE : un `_vN` dedans est deux rangs.

    Sans ce refus, `--scan S_v3` designerait la famille `S_v3` -- qui n'existe
    pas -- et le message d'erreur parlerait d'un scan inconnu, ce qui est vrai
    mais illisible. Le refus nomme la grammaire, et il est le seul endroit ou
    la moitie CLI de `Q12` se ferme : plus aucune chaine saisie par
    l'operateur ne porte de fragment de rang, donc plus aucune n'est ambigue.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=True,
                               **{mot_cle: valeur})
    message = str(erreur.value)
    assert "--version" in message and "famille" in message.lower(), message


# ---------------------------------------------------------------------------
# `EPIC11-ARB-224`, SECOND TEMPS -- on designe par les ARGUMENTS PRODUCTEURS
#
# Egan, 2026-09-05, verbatim : « pourquoi designer l'emplacement des masters ?
# [...] Avec le lot, le codec et la version l'outil sait retrouver le master
# precis. Son emplacement, de plus, est au manifeste non ? Idealement il
# faudrait aussi une coherence entre la commande remove et les commandes qui
# produisent les objets correspondants. Avec les memes arguments qui ont servi
# a les generer pour les identifier. »
#
# Ce bloc mesure les trois consequences que la premiere redaction n'avait pas :
#
# 1. `--master` est un DRAPEAU NU accompagne de `--profile` -- le parametre
#    d'`encode`, pas un vocabulaire neuf. La frontiere porte sur la SOURCE des
#    `choices`, pas sur leur contenu : une liste recopiee serait verte le jour
#    ou elle serait ecrite, et fausse le lendemain ;
# 2. `--resolution` n'est exige que lorsqu'il LEVE une ambiguite. Les deux
#    volets se mesurent -- exige quand il faut, facultatif sinon --, faute de
#    quoi « n'est exige que » serait satisfait par une option toujours exigee ;
# 3. le retrecissement du designateur rend l'ambiguite ATTEIGNABLE : le chemin
#    etait unique par construction, le couple (profil, rang) ne l'est pas. Le
#    refus nomme les entrees en conflit ; il ne prend plus la premiere.
# ---------------------------------------------------------------------------


class _ParseurCapture(Exception):
    """Le parseur construit par `main`, attrape avant toute execution."""

    def __init__(self, parseur):
        self.parseur = parseur


def _parseur_reel_de_la_cli():
    """Le parseur que `main` batit, capture sans executer une commande.

    Meme geste que `test_conformite_de_la_documentation._parseur_reel`, et
    pour le meme motif : `main` construit son parseur en local et ne l'expose
    pas. Relire la SOURCE perdrait les options posees par un auxiliaire -- et
    une frontiere sur les `choices` doit porter sur l'objet reellement
    construit, sinon elle mesure ce qu'on croit avoir ecrit.
    """
    import argparse as _argparse

    from mixed_media_utility import cli

    origine = _argparse.ArgumentParser.parse_args

    def _intercepter(self, *args, **kwargs):
        raise _ParseurCapture(self)

    _argparse.ArgumentParser.parse_args = _intercepter
    try:
        cli.main([])
    except _ParseurCapture as capture:
        return capture.parseur
    finally:
        _argparse.ArgumentParser.parse_args = origine
    raise AssertionError(
        "`cli.main` n'a appele aucun `parse_args` : la capture ne mesure plus "
        "rien.")


def _projet_a_deux_resolutions(tmp_path):
    """Un lot portant DEUX resolutions du meme profil, plus un autre profil.

    Regle des fabriques : quatre entrees distinguables, la cible ni en tete ni
    en queue de la liste, un SECOND lot, et **les deux resolutions au MEME
    rang** -- c'est la seule configuration ou `--resolution` a quelque chose a
    lever, donc la seule qui mesure ce que la regle annonce.
    """
    lot = {
        "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
        "encoded_masters": [
            # Le defaut (aucun segment de resolution) EN TETE.
            {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
            # La cible, AU MILIEU : `uhd2160` au meme rang que le defaut.
            {"path": "outputs/L_mmu_prores_422_uhd2160.mov",
             "profile_id": "prores_422"},
            # Un second rang du defaut, pour que la famille ne soit pas plate.
            {"path": "outputs/L_mmu_prores_422_v2.mov", "profile_id": "prores_422",
             "version_rank": 2},
            # Un autre PROFIL, en QUEUE : il ne doit jamais entrer dans le jeu.
            {"path": "outputs/L_mmu_dnxhr_hq.mov", "profile_id": "dnxhr_hq"},
        ],
    }
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
        "lots": [lot, {"lot_id": "AUTRE", "rush_id": "R2"}],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in lot["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")
    return projet


def test_ARB224b_le_master_se_retrouve_SANS_aucun_chemin(tmp_path):
    """Le coeur de la correction : lot + codec + version suffisent.

    L'emplacement est AU MANIFESTE. Le demander a l'operateur, c'est lui
    demander de recalculer ce que l'outil a ecrit -- et la premiere redaction
    l'a paye d'un exemple canonique incoherent, ou un chemin sans fragment
    `_vN` (donc la version 1) etait donne a cote d'un `--version 3`.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--master", "--profile", "prores_422",
        "--version", "3", "--confirmer")
    assert code == 0
    assert not (projet / project_layout.OUTPUTS_DIRNAME / "L_mmu_prores_422_v3.mov").exists()
    # Les deux autres rangs de la famille et l'autre PROFIL sont intacts.
    for intact in ("L_mmu_prores_422.mov", "L_mmu_prores_422_v2.mov",
                   "L_mmu_dnxhr_hq.mov"):
        assert (projet / project_layout.OUTPUTS_DIRNAME / intact).is_file(), intact


def test_ARB224b_un_CHEMIN_donne_a_master_ne_supprime_RIEN(tmp_path, capsys):
    """Frontiere NEGATIVE : le retrait du chemin est PUR.

    `--master <chemin>` etait la forme livree le matin meme. Elle doit
    desormais etre refusee par `argparse` comme n'importe quelle faute de
    frappe -- ni alias, ni message special (`EPIC11-ARB-220`) --, et sans que
    rien ne bouge sur le disque : `--master` etant devenu un drapeau, un
    parseur qui l'aurait laisse en `nargs='?'` accepterait la valeur en
    silence.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant_manifeste = (projet / "project.json").read_bytes()
    avant_arbre = sorted(p.name for p in (projet / project_layout.OUTPUTS_DIRNAME).iterdir())

    with pytest.raises(SystemExit) as sortie:
        _remove_en_ligne_de_commande(
            projet, "--lot", "L", "--master",
            "outputs/L_mmu_prores_422_v3.mov", "--confirmer")

    assert sortie.value.code == 2
    capsys.readouterr()
    assert (projet / "project.json").read_bytes() == avant_manifeste
    assert sorted(p.name for p in (projet / project_layout.OUTPUTS_DIRNAME).iterdir()) == avant_arbre


def test_ARB224b_les_choix_de_profile_sont_LUS_du_catalogue_et_pas_recopies():
    """La frontiere porte sur la SOURCE, jamais sur le contenu de la liste.

    « `--profile` est LE parametre d'`encode`, pas un `--type` neuf : memes
    `choices`, lus du meme `codec_profiles.PROFILES`. » Une liste recopiee
    serait verte le jour ou elle est ecrite et fausse au premier profil ajoute
    -- c'est le defaut exact que la story 11.14 ferme ailleurs, un vocabulaire
    derive a un endroit et recopie a l'autre.

    Elle se mesure sur les DEUX commandes ensemble, pas sur `remove` seul :
    c'est leur EGALITE qui est la promesse, et une assertion sur `remove` seul
    resterait vraie si `encode` divergeait.
    """
    from mixed_media_utility import codec_profiles

    parseur = _parseur_reel_de_la_cli()
    choix = {}
    for commande, chemin in (("encode", ["encode"]),
                             ("project remove", ["project", "remove"])):
        courant = parseur
        for mot in chemin:
            courant = next(
                action.choices[mot]
                for action in courant._actions
                if getattr(action, "choices", None) and mot in action.choices
                and hasattr(action.choices[mot], "_actions"))
        choix[commande] = next(
            action.choices for action in courant._actions
            if action.dest == "profile")

    assert choix["project remove"] == choix["encode"], choix
    assert sorted(choix["project remove"]) == sorted(codec_profiles.PROFILES)


def test_ARB224b_un_profil_HORS_catalogue_est_refuse_par_argparse(tmp_path):
    """Volet symetrique : sans lui, `choices` pourrait etre absent.

    Une egalite de listes reste vraie si aucune des deux n'est branchee sur le
    parseur. On exerce donc le refus lui-meme, sur un identifiant qui n'a
    jamais existe dans ce depot.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    with pytest.raises(SystemExit) as sortie:
        _remove_en_ligne_de_commande(
            projet, "--lot", "L", "--master", "--profile", "prorez_422")
    assert sortie.value.code == 2


def test_ARB224b_master_SANS_profile_est_refuse_nommement(tmp_path, capsys):
    """`--master` seul ne designe rien : le lot en porte plusieurs par nature.

    C'est la docstring de `_famille_de_master` qui le dit depuis la story
    6.5 -- « un lot porte legitimement plusieurs masters a des profils et des
    resolutions differents ». Deviner le profil serait le meme geste que
    deviner un chemin.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant = (projet / "project.json").read_bytes()
    code = _remove_en_ligne_de_commande(projet, "--lot", "L", "--master",
                                        "--confirmer")
    assert code == 1
    assert "--profile" in capsys.readouterr().err
    assert (projet / "project.json").read_bytes() == avant


@pytest.mark.parametrize("orphelin", (["--profile", "prores_422"],
                                      ["--resolution", "uhd2160"]))
def test_ARB224b_un_argument_producteur_SANS_master_est_refuse(
    tmp_path, capsys, orphelin
):
    """« Un drapeau sans effet est un mensonge », deja paye deux fois ici.

    `--profile` et `--resolution` n'ont de sens qu'avec `--master`. Les
    accepter en silence ferait croire a l'operateur qu'il a vise un master
    alors qu'il vient de demander la suppression du LOT ENTIER -- c'est-a-dire
    la destruction la plus large de cette commande, sur un malentendu.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)
    avant = (projet / "project.json").read_bytes()
    code = _remove_en_ligne_de_commande(projet, "--lot", "L", *orphelin,
                                        "--confirmer")
    assert code == 1
    assert "--master" in capsys.readouterr().err
    assert (projet / "project.json").read_bytes() == avant


# --- `--resolution` : exige quand il leve, facultatif sinon ----------------


def test_ARB224b_resolution_est_EXIGEE_quand_elle_leve_une_ambiguite(
    tmp_path, capsys
):
    """Le refus NOMME les resolutions declarees plutot que d'en deviner une.

    Ce n'est pas un blocage sec au sens d'`EPIC11-ARB-89` : il dit le geste
    qui manque. Et il ne peut pas etre remplace par « prendre la premiere » --
    la premiere entree est ici le defaut, donc un operateur visant l'UHD
    detruirait la mauvaise sortie sans un mot.
    """
    projet = _projet_a_deux_resolutions(tmp_path)
    avant = sorted(p.name for p in (projet / project_layout.OUTPUTS_DIRNAME).iterdir())

    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--master", "--profile", "prores_422",
        "--confirmer")

    assert code == 1
    erreur = capsys.readouterr().err
    assert "--resolution" in erreur, erreur
    assert "uhd2160" in erreur, "le refus doit NOMMER ce qui est declare"
    assert sorted(p.name for p in (projet / project_layout.OUTPUTS_DIRNAME).iterdir()) == avant


@pytest.mark.parametrize("resolution,cible", [
    ("uhd2160", "L_mmu_prores_422_uhd2160.mov"),
    # Le DEFAUT se designe par son identifiant, et il ne porte aucun segment :
    # c'est la meme convention que le rang d'origine, un pas de plus.
    ("hd1080", "L_mmu_prores_422.mov"),
])
def test_ARB224b_resolution_LEVE_l_ambiguite_aux_DEUX_bords(
    tmp_path, resolution, cible
):
    """Les deux bords de l'ambiguite, et ils ne traversent pas le meme code.

    `uhd2160` porte un segment dans le nom ; le defaut n'en porte AUCUN, et
    c'est `resolution_name_segment` qui en decide ainsi (« il n'apparait que
    hors defaut »). Un resolveur qui chercherait toujours un segment raterait
    le defaut ; un resolveur qui n'en chercherait jamais raterait l'UHD. Viser
    un seul des deux fermerait une branche et laisserait l'autre.
    """
    projet = _projet_a_deux_resolutions(tmp_path)
    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--master", "--profile", "prores_422",
        "--resolution", resolution, "--confirmer")

    assert code == 0
    assert not (projet / project_layout.OUTPUTS_DIRNAME / cible).exists()
    # L'autre resolution du meme profil est INTACTE : c'est ce qui distingue
    # une levee d'ambiguite d'une suppression de famille.
    autres = sorted(p.name for p in (projet / project_layout.OUTPUTS_DIRNAME).iterdir())
    assert len(autres) == 3, autres
    assert "L_mmu_dnxhr_hq.mov" in autres


def test_ARB224b_resolution_reste_FACULTATIVE_quand_rien_n_est_ambigu(tmp_path):
    """Sans ce volet, « n'est exige que lorsqu'il leve une ambiguite » serait
    satisfait par une option TOUJOURS exigee.

    C'est la moitie que la premiere redaction d'une regle conditionnelle oublie
    systematiquement : la condition ne se mesure que par ses deux faces.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)   # un seul profil sans variante
    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--master", "--profile", "prores_422",
        "--version", "2", "--confirmer")
    assert code == 0
    assert not (projet / project_layout.OUTPUTS_DIRNAME / "L_mmu_prores_422_v2.mov").exists()


def test_ARB224b_une_resolution_INCONNUE_du_lot_est_refusee_avec_la_liste(
    tmp_path, capsys
):
    """Un refus qui NOMME ce qui existe, jamais un « rien trouve » muet."""
    projet = _projet_a_deux_resolutions(tmp_path)
    code = _remove_en_ligne_de_commande(
        projet, "--lot", "L", "--master", "--profile", "prores_422",
        "--resolution", "hd720", "--confirmer")
    assert code == 1
    erreur = capsys.readouterr().err
    assert "uhd2160" in erreur, erreur


# --- L'ambiguite NON levable : le manifeste est abime, on ne devine pas ----


def test_ARB224b_DEUX_entrees_de_meme_famille_et_meme_rang_sont_REFUSEES(
    tmp_path
):
    """La trouvaille versee au contrat, et elle n'est plus optionnelle.

    Le chemin etait unique par construction ; le couple (profil, resolution,
    rang) ne l'est pas. `next()` prenait la premiere entree en SILENCE, ce qui
    fait detruire une sortie que l'operateur ne visait pas -- la meme famille
    de defaut que « le scan d'un AUTRE lot », mesuree ici avant qu'elle ne
    coute.

    Le refus NOMME les deux entrees en conflit : sans leurs chemins,
    l'operateur ne peut pas reparer son manifeste, et le refus serait le
    blocage sec qu'`EPIC11-ARB-89` interdit.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "encoded_masters": [
                {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
                # Le DOUBLON, et il est choisi pour ce qu'il montre : meme
                # profil, meme rang, meme resolution -- seul le CONTENEUR
                # differe. Or le conteneur est dans le chemin et **pas dans le
                # designateur** : c'est litteralement « le chemin etait unique
                # par construction, le couple ne l'est pas ». Un manifeste
                # ecrit a la main, ou par un producteur plus ancien, le
                # produit ; le retrecissement du designateur le rend
                # ATTEIGNABLE.
                {"path": "outputs/L_mmu_prores_422.mkv", "profile_id": "prores_422"},
            ]},
            {"lot_id": "AUTRE", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in manifest["lots"][0]["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=True,
                               master=True, profile="prores_422")

    message = str(erreur.value)
    assert "outputs/L_mmu_prores_422.mov" in message, message
    assert "outputs/L_mmu_prores_422.mkv" in message, message
    # Et rien n'a bouge -- un refus qui aurait deja supprime serait le pire cas.
    assert (projet / project_layout.OUTPUTS_DIRNAME / "L_mmu_prores_422.mkv").is_file()


def test_ARB224b_un_master_RENOMME_a_la_main_reste_supprimable(tmp_path):
    """Le corollaire a ne pas casser : jamais de blocage sec.

    Un master dont le fichier a ete renomme a la main garde une entree que le
    designateur ne peut plus reconnaitre PAR SON NOM -- la resolution ne s'en
    derive plus. Le manifeste, lui, porte toujours son `profile_id` et son
    rang : c'est de la DECLARATION que vient le droit de retirer, pas de la
    conformite du nom. Sans ce test, le retrecissement du designateur rendrait
    ces entrees immortelles, ce qui est exactement la fuite
    qu'`EPIC11-ARB-89` interdit.
    """
    manifest = {
        "schema_version": "2.1", "project_id": "p", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "L", "rush_id": "R", "encoded_masters": [
                {"path": "outputs/RENOMME-A-LA-MAIN.mov", "profile_id": "prores_422"},
            ]},
            {"lot_id": "AUTRE", "rush_id": "R"},
        ],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    (projet / project_layout.OUTPUTS_DIRNAME / "RENOMME-A-LA-MAIN.mov").write_bytes(b"master")

    rapport = remove_project_element(projet, lot_id="L", dry_run=False,
                                     master=True, profile="prores_422")

    assert rapport.supprime is True
    assert not (projet / project_layout.OUTPUTS_DIRNAME / "RENOMME-A-LA-MAIN.mov").exists()


def test_ARB224b_le_resolveur_par_CHEMIN_a_ete_RETIRE_et_non_laisse_sans_appelant():
    """Frontiere NEGATIVE sur le code MORT, et c'est `T1` qui l'a payee.

    Le 2026-09-04, un raccord `frames=` a survecu a son motif « le temps que
    `cli.py` passe au nom neuf » ; le lot C l'avait deja fait, si bien que le
    raccord vivait sans appelant et qu'aucune des trois mesures existantes ne
    le voyait. `_famille_du_chemin_de_master` est exactement dans ce cas
    depuis que le designateur ne porte plus de chemin : la laisser serait
    reproduire `T1` a une nuit d'intervalle.
    """
    import mixed_media_utility.project_maintenance as pm

    assert not hasattr(pm, "_famille_du_chemin_de_master"), (
        "`_famille_du_chemin_de_master` n'a plus d'appelant depuis "
        "`EPIC11-ARB-224` : retrait PUR, pas de fonction laissee derriere.")


# ---------------------------------------------------------------------------
# FERMETURE de la revue en trois couches d'`EPIC11-ARB-224` -- moitie
# « resolution et famille ».
#
# Six critiques, dont DEUX destructions silencieuses. Aucune ne se voyait par
# un test rouge : les six bancs du perimetre rendaient 392 PASSED avant comme
# apres chacun des correctifs. C'est le regime que la politique nomme -- la
# campagne vaut plus que la relecture --, et c'est pourquoi chaque fermeture
# ci-dessous porte la reinjection de son mutant au registre des findings.
# ---------------------------------------------------------------------------


def _segment_ecrit_par_le_PRODUCTEUR(demande: str, source: tuple[int, int]) -> str:
    """Le segment qu'`encode` mettrait REELLEMENT dans le nom du master.

    Le banc ne compose AUCUN nom : il le demande au producteur. Un banc qui
    composerait le segment lui-meme mesurerait sa propre recette -- c'est
    exactement la « seconde verite » que `C1-01` a payee, et l'ecrire ici la
    reintroduirait dans la mesure au lieu du code.
    """
    from mixed_media_utility import encode as _encode

    arretee = _encode.settle_resolution(
        _encode.resolve_output_resolution(demande), source)
    return _encode.resolution_name_segment(arretee) or ""


def _projet_a_resolutions(tmp_path, masters, lignes_d_eau=None, ordre=("L", "AUTRE")):
    """Un lot portant les masters demandes, avec un SECOND lot et l'ordre choisi.

    Regle des fabriques : les entrees sont distinguables (segments et rangs
    differents), un second lot existe, et `ordre` permet de placer le lot vise
    a CHAQUE BORD de `manifest["lots"]` -- la liste que le code parcourt.
    """
    from mixed_media_utility.io import encode_manifest, naming

    entrees = []
    for segment, rang in masters:
        entrees.append({
            "path": project_layout.OUTPUTS_DIRNAME + "/"
                    + naming.build_master_filename(
                        lot_id="L", profile_id="prores_422", container="mov",
                        resolution_segment=segment or None,
                        version_rank=None if rang == 1 else rang),
            "profile_id": "prores_422",
            **({} if rang == 1 else {"version_rank": rang}),
        })
    lot = {"lot_id": "L", "rush_id": "R", "encoded_masters": entrees}
    if lignes_d_eau:
        lot[encode_manifest.MASTERS_WATERMARK_FIELD] = dict(lignes_d_eau)
    par_id = {"L": lot, "AUTRE": {"lot_id": "AUTRE", "rush_id": "R2"}}
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
        "lots": [par_id[nom] for nom in ordre],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in entrees:
        (projet / entree["path"]).write_bytes(b"master")
    return projet


# --- `C1-01` : `--resolution` parle la langue d'`encode`, ou ne parle pas ----


@pytest.mark.parametrize("demande,source", [
    # Un identifiant du registre : le cas ou la regle est triviale, et le seul
    # que les six `test_ARB224b_resolution_*` exercaient.
    ("uhd2160", (3840, 2160)),
    # Le defaut par son identifiant.
    ("hd1080", (1920, 1080)),
    # Une geometrie personnalisee qui retombe sur le DEFAUT du registre.
    ("1920x1080", (1920, 1080)),
    # Une geometrie personnalisee qui retombe sur une entree NOMMEE.
    ("3840x2160", (3840, 2160)),
    # Une geometrie qu'aucune entree du registre ne nomme.
    ("1000x500", (1000, 500)),
])
def test_ARB224c_l_argument_qui_a_PRODUIT_le_master_le_DESIGNE(
    tmp_path, demande, source
):
    """`EPIC11-ARB-224` : « les memes arguments qui ont servi a les generer ».

    `C1-01`, critique. `_segment_de_resolution_demande` comparait la chaine
    BRUTE au defaut, la ou `encode` passe par `settle_resolution`, **qui
    normalise**. Mesure de la revue sur six formes : `native`, `1920x1080` et
    `3840x2160` ne designaient AUCUN master -- quatre sur six. Les six tests
    `test_ARB224b_resolution_*` n'employaient que des identifiants du registre,
    c'est-a-dire la moitie du domaine ou la regle est triviale.

    Le segment est demande au PRODUCTEUR, jamais compose ici.
    """
    segment = _segment_ecrit_par_le_PRODUCTEUR(demande, source)
    # Un SECOND master, d'un autre segment et d'un autre rang : sans lui,
    # l'unique entree serait retiree quelle que soit la resolution demandee et
    # le test serait vrai sans rien mesurer.
    autre = "uhd2160" if segment != "uhd2160" else "1000x500"
    projet = _projet_a_resolutions(tmp_path, [(segment, 1), (autre, 2)])
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    vise, epargne = (e["path"] for e in manifest["lots"][0]["encoded_masters"])

    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True,
        profile="prores_422", resolution=demande)

    assert rapport.supprime is True
    assert not (projet / vise).exists(), (
        f"l'argument {demande!r} qui a PRODUIT {vise!r} ne le designe pas")
    assert (projet / epargne).is_file(), "le voisin a ete emporte"


def test_ARB224c_native_est_refuse_en_NOMMANT_ses_deux_issues(tmp_path):
    """`native` n'a pas de geometrie sans les frames : refus NOMME, pas devine.

    C'est l'issue qu'`EPIC11-ARB-89` exige a la place d'un silence : le refus
    dit pourquoi il ne peut pas trancher ET par quoi remplacer l'argument --
    l'identifiant de registre, ou la geometrie `<largeur>x<hauteur>`. Le faire
    retomber sur le defaut serait la destruction silencieuse de `C2-1`, un cran
    plus haut.
    """
    projet = _projet_a_resolutions(tmp_path, [("", 1), ("uhd2160", 1)])

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, master=True,
                               profile="prores_422", resolution="native")

    message = str(erreur.value)
    assert "native" in message, message
    assert "<largeur>x<hauteur>" in message, (
        f"le refus doit NOMMER la forme de remplacement: {message}")
    assert "registre" in message, message
    # Les DEUX masters sont intacts : un refus qui aurait deja supprime serait
    # strictement pire que le defaut qu'il ferme.
    for entree in json.loads(
            (projet / "project.json").read_text(encoding="utf-8")
    )["lots"][0]["encoded_masters"]:
        assert (projet / entree["path"]).is_file()


# --- `C2-1` / `F7` : la chaine VIDE ne designe pas le defaut ----------------


def test_ARB224c_une_resolution_VIDE_ne_designe_PAS_le_master_par_defaut(tmp_path):
    """`C2-1` / `F7`, critique -- DESTRUCTION SILENCIEUSE, code retour 0.

    Regime reel, et il n'a rien d'exotique : `--resolution "$RES"` dans un
    script, avec la variable non definie, sur un lot a deux resolutions. La
    garde d'ambiguite testait `resolution is None`, donc la chaine vide la
    desarmait ; et `_segment_de_resolution_demande("")` rendait `""`, qui est
    exactement le segment du nom par defaut. La chaine vide etait donc
    SYNONYME du defaut, et le master par defaut partait sans un mot.

    L'asymetrie se mesurait dans le meme ecran : `--profile ""` est refuse par
    ses `choices` argparse.
    """
    projet = _projet_a_resolutions(tmp_path, [("", 1), ("uhd2160", 1)])

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, master=True,
                               profile="prores_422", resolution="")

    assert "''" in str(erreur.value), (
        f"le refus doit NOMMER ce qui a ete recu: {erreur.value}")
    for entree in json.loads(
            (projet / "project.json").read_text(encoding="utf-8")
    )["lots"][0]["encoded_masters"]:
        assert (projet / entree["path"]).is_file(), (
            f"{entree['path']} a ete detruit par une resolution VIDE")


# --- `C2-2` / `C1-06` : un seul predicat, pour la garde ET la repartition ---


def _projet_a_planche_et_scan(tmp_path):
    """Un lot portant une planche ET des scans -- de quoi croiser deux cibles.

    Regle des fabriques : trois entrees distinguables par famille, et un
    SECOND lot. Sans la planche, la destruction que `C2-2` a mesuree n'a rien
    a detruire ; sans les scans, `--scan ""` n'a rien a ignorer.
    """
    lot = {
        "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
        "sheets_pdfs": [{"path": project_layout.PLANCHES_DIRNAME + "/L.pdf"}],
        "reconstructions": [
            {"ingest_slug": "S"}, {"ingest_slug": "S_v2"}, {"ingest_slug": "S_v3"},
        ],
    }
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
        "lots": [lot, {"lot_id": "AUTRE", "rush_id": "R2"}],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.PLANCHES_DIRNAME).mkdir()
    (projet / project_layout.PLANCHES_DIRNAME / "L.pdf").write_bytes(b"pdf")
    for slug in ("S", "S_v2", "S_v3"):
        (projet / project_layout.SCANS_DIRNAME / slug).mkdir(parents=True)
        (projet / project_layout.SCANS_DIRNAME / slug / "p.tiff").write_bytes(b"page")
    return projet


#: Les gardes que `--scan ""` desarmait toutes ensemble, avec ce que chacune
#: doit dire. **Une ligne par garde, et les fragments attendus DIFFERENT** : un
#: appariement inverse entre la garde et son message ne se verrait pas si elles
#: attendaient toutes le meme mot.
GARDES_DESARMEES_PAR_UN_SCAN_VIDE = (
    ("deux cibles fines", {"planche": True}, "seule cible fine"),
    ("avec-scans", {"avec_scans": True}, "--avec-scans"),
    ("dernier lot", {"confirmation_dernier_lot": True}, "--confirmer-dernier-lot"),
)


@pytest.mark.parametrize("nom,en_plus,attendu", GARDES_DESARMEES_PAR_UN_SCAN_VIDE,
                         ids=[g[0] for g in GARDES_DESARMEES_PAR_UN_SCAN_VIDE])
def test_ARB224c_un_scan_VIDE_reste_une_cible_fine_pour_les_gardes(
    tmp_path, nom, en_plus, attendu
):
    """`C2-2` / `C1-06`, critique -- DESTRUCTION SILENCIEUSE et REGRESSION.

    Le diff a remplace `if valeur is not None` par `if valeur` dans la liste
    des cibles fines -- motive, trois des quatre cibles etant devenues des
    drapeaux nus. Mais `scan` est reste une CHAINE : la chaine vide etait
    ABSENTE pour les six gardes et DONNEE pour la repartition, restee en
    `is not None`.

    Regression mesuree des deux cotes : `--scan "" --planche --confirmer`
    rendait « Une seule cible fine a la fois » sur `0a00c9b06` et detruisait la
    planche sans un mot, code retour 0, sur `89fbd1d31`.
    """
    projet = _projet_a_planche_et_scan(tmp_path)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, scan="",
                               **en_plus)

    assert attendu in str(erreur.value), str(erreur.value)
    assert (projet / project_layout.PLANCHES_DIRNAME / "L.pdf").is_file(), (
        "la planche a ete detruite par une cible fine que la garde n'a pas vue")


def test_ARB224c_un_scan_VIDE_SEUL_est_refuse_par_son_propre_resolveur(tmp_path):
    """Le symetrique : la garde ne doit pas masquer le refus du resolveur.

    Sans lui, on pourrait fermer `C2-2` en refusant la chaine vide TOUT EN
    HAUT, ce qui rendrait ce banc vert en cessant de mesurer que la chaine vide
    reste bien une cible fine -- une fermeture qui deplace le defaut au lieu de
    le fermer.
    """
    projet = _projet_a_planche_et_scan(tmp_path)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, scan="")

    assert "Slug de scan invalide" in str(erreur.value), str(erreur.value)


#: Tout parametre de `remove_project_element` qui porte une VALEUR, avec sa
#: valeur fausse-mais-non-`None` et le reste de l'invocation qui la rend
#: SIGNIFIANTE. C'est le domaine ou la divergence entre une lecture par
#: truthiness et une lecture par `is not None` peut vivre.
#:
#: `temoin_sans` dit ce que la MEME invocation fait quand le parametre est
#: ABSENT : c'est le controle de non-vacuite du banc ci-dessous. Sans lui, une
#: invocation refusee pour une tout autre raison rendrait la frontiere verte
#: sans rien mesurer -- la tautologie que la section 6.2 de la politique nomme.
PARAMETRES_PORTEURS_DE_VALEUR = (
    # `scan=""` avec une planche : la garde « une seule cible fine » doit voir
    # DEUX cibles. Absent, l'invocation retire la planche sans broncher.
    ("scan", "", {"planche": True}, "accepte", "_projet_a_planche_et_scan"),
    # `version=0` : hors des rangs possibles. Absente, la cible est l'origine.
    ("version", 0, {"planche": True}, "accepte", "_projet_a_planche_et_scan"),
    # `resolution=""` sur un lot AMBIGU : la chaine vide ne doit pas designer
    # le defaut. Absente, le refus d'ambiguite tombe -- donc l'invocation est
    # refusee dans les deux cas, mais pour des motifs DIFFERENTS, ce que la
    # seconde assertion mesure.
    ("resolution", "", {"master": True, "profile": "prores_422"}, "refus",
     "_projet_a_deux_resolutions"),
    # `profile=""` : aucun master ne porte ce profil. Absent, `--master` exige
    # `--profile` -- refus, la encore pour un motif different.
    ("profile", "", {"master": True}, "refus", "_projet_a_deux_resolutions"),
    # Les deux selecteurs de cible, pour l'exhaustivite du domaine.
    # Les deux SELECTEURS de cible, pour l'exhaustivite du domaine. Le temoin
    # y vaut « la meme invocation avec une valeur SAINE » plutot que « sans le
    # parametre » : l'un des deux est toujours exige, la garde « exactement un
    # lot ou un rush » ne laissant pas le choix.
    ("lot_id", "", {}, "accepte", "_projet_a_planche_et_scan"),
    ("rush_id", "", {}, "refus", "_projet_a_planche_et_scan"),
)


@pytest.mark.parametrize(
    "parametre,valeur_fausse,reste,temoin_sans,fabrique",
    PARAMETRES_PORTEURS_DE_VALEUR,
    ids=[p for p, _v, _r, _t, _f in PARAMETRES_PORTEURS_DE_VALEUR])
def test_ARB224c_aucune_valeur_FAUSSE_ne_passe_pour_une_ABSENCE(
    tmp_path, parametre, valeur_fausse, reste, temoin_sans, fabrique
):
    """La generalisation de `C2-1` et `C2-2`, et la reponse a « y en a-t-il une
    TROISIEME asymetrie ? ».

    Les deux critiques sont la MEME asymetrie a deux endroits : une valeur
    fausse mais non `None` que certaines lectures prennent pour une absence et
    d'autres pour une presence. Fermer les deux lignes nommees laisserait le
    GENRE ouvert -- ce banc le ferme pour TOUS les parametres porteurs de
    valeur, ceux d'aujourd'hui comme ceux qu'on ajoutera.

    Les drapeaux nus ne sont pas de ce domaine : la garde « un entier n'est pas
    un drapeau » les contraint deja a de VRAIS booleens, ou `False` EST leur
    facon d'etre absents.

    Deux mesures, et la seconde est ce qui empeche la premiere d'etre une
    tautologie : la valeur fausse est REFUSEE et rien n'est ecrit ; et le
    temoin dit ce que la meme invocation fait SANS le parametre -- si elle
    passe, le refus vient bien de la valeur fausse et de rien d'autre ; si elle
    echoue aussi, les deux refus doivent DIFFERER, faute de quoi la valeur
    fausse n'aurait rien change.
    """
    def _invoquer(**surcharge):
        racine = tmp_path / _jeton()
        racine.mkdir()
        projet = globals()[fabrique](racine)
        arguments = {"dry_run": False, **reste, **surcharge}
        if parametre != "rush_id":
            arguments.setdefault("lot_id", "L")
        avant = (projet / "project.json").read_bytes()
        try:
            rapport = remove_project_element(projet, **arguments)
        except ProjectMaintenanceError as erreur:
            assert (projet / "project.json").read_bytes() == avant
            return ("refus", str(erreur))
        return ("accepte", rapport.cible)

    verdict, motif = _invoquer(**{parametre: valeur_fausse})
    assert verdict == "refus", (
        f"{parametre}={valeur_fausse!r} a ete pris pour une ABSENCE et a "
        f"laisse l'operation aboutir sur {motif!r}")

    verdict_sans, motif_sans = _invoquer()
    assert verdict_sans == temoin_sans, (
        f"le temoin de non-vacuite a change: sans {parametre}, l'invocation "
        f"rend {verdict_sans!r} la ou le banc attend {temoin_sans!r} ({motif_sans})")
    if verdict_sans == "refus":
        assert motif != motif_sans, (
            f"le refus est le MEME avec et sans {parametre}={valeur_fausse!r}: "
            "la valeur fausse n'a donc rien change, et cette frontiere ne "
            f"mesure rien. {motif}")


_JETON = [0]


def _jeton() -> str:
    """Un sous-dossier neuf par invocation : deux appels dans un meme test ne
    doivent pas se partager un projet que le premier aurait modifie."""
    _JETON[0] += 1
    return f"invocation-{_JETON[0]}"


# --- `C2-3` : un rang se BORNE, et une issue nommee doit changer quelque chose


@pytest.mark.parametrize("rang", (0, -1, 999), ids=("zero", "negatif", "au-dela"))
def test_ARB224c_un_rang_hors_des_bornes_est_refuse_en_NOMMANT_les_bornes(
    tmp_path, rang
):
    """`C2-3`, critique. Le depot borne les rangs partout ailleurs.

    Le diff validait `--version` contre le booleen et contre le non-entier,
    jamais contre `VERSION_RANK_MIN`/`MAX`. Les trois rangs degeneres
    atteignaient donc les resolveurs.
    """
    from mixed_media_utility.io import naming

    projet = _projet_a_planche_et_scan(tmp_path)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=False, planche=True,
                               version=rang)

    message = str(erreur.value)
    assert str(naming.VERSION_RANK_MIN) in message, message
    assert str(naming.VERSION_RANK_MAX) in message, message
    assert str(version_ranks.RANG_ORIGINE) in message, message


def test_ARB224c_un_refus_ne_nomme_PAS_une_issue_qui_rend_le_MEME_refus(tmp_path):
    """`C2-3`, la moitie qui mord : le blocage sec DEGUISE.

    Sur `--planche --version 0`, le refus affirmait « le rang 0 a pourtant ete
    CONSOMME (ligne d'eau: 3) » -- faux, zero n'est pas un rang, la branche ne
    testant que `rang <= ligne_actuelle` -- et nommait `--liberer-le-rang`
    comme issue. En relancant avec ce drapeau, `est_en_queue(0, 3)` rend
    `False` et le MEME refus revenait mot pour mot. Les deux issues nommees
    etaient refusees ensemble, ce qu'`EPIC11-ARB-89` interdit : une issue
    nommee doit etre une commande qu'on peut taper et qui change quelque chose.

    La frontiere est ecrite sur la PROPRIETE, pas sur le message : elle tiendra
    si le texte du refus change, et elle mordra sur tout autre rang qui
    rentrerait un jour dans le meme tourniquet.
    """
    projet = _projet_a_planche_et_scan(tmp_path)

    with pytest.raises(ProjectMaintenanceError) as sans:
        remove_project_element(projet, lot_id="L", dry_run=True, planche=True,
                               version=0)
    with pytest.raises(ProjectMaintenanceError) as avec:
        remove_project_element(projet, lot_id="L", dry_run=True, planche=True,
                               version=0, liberer_le_rang=True)

    assert not ("--liberer-le-rang" in str(sans.value)
                and str(avec.value) == str(sans.value)), (
        "le refus nomme `--liberer-le-rang` comme issue et cette issue rend le "
        f"meme refus, mot pour mot: {sans.value}")


# --- `C1-03` / `F2` : la FAMILLE d'un master est (profil, resolution) -------


def test_ARB224c_la_QUEUE_d_une_famille_non_par_DEFAUT_se_LIBERE(tmp_path):
    """`C1-03` / `F2`, critique -- deux couches sur trois, par deux chemins.

    `encode.cle_de_famille_de_master` borne la famille par le profil ET la
    resolution, et dit pourquoi : « deux masters d'un lot qui different par
    l'un ou l'autre ne sont PAS deux versions l'un de l'autre ».
    `_famille_de_master` lisait et ecrivait sous le PROFIL seul, et composait
    `rangs_declares` de tous les masters du profil, resolutions confondues.

    Ici la famille `uhd2160` ne porte QUE le rang 1 : c'est SA queue. Le refus
    d'avant invoquait « un master posterieur » appartenant a la famille par
    defaut -- `EPIC11-ARB-92`, « un rang se rend en queue, sur demande »,
    retourne en silence pour toute famille non par defaut.
    """
    projet = _projet_a_resolutions(
        tmp_path, [("", 1), ("", 2), ("", 3), ("uhd2160", 1)])

    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422",
        resolution="uhd2160", liberer_le_rang=True)

    assert rapport.rang_libere is True, (
        "la queue de la famille uhd2160 doit se liberer : les rangs 2 et 3 "
        "sont ceux d'une AUTRE famille")
    # Et les trois masters de la famille par defaut sont intacts.
    lot = json.loads((projet / "project.json").read_text(encoding="utf-8"))["lots"][0]
    assert len(lot["encoded_masters"]) == 3


def test_ARB224c_la_LIGNE_D_EAU_est_posee_sur_la_cle_du_PRODUCTEUR(tmp_path):
    """La cle se LIT d'`encode`, elle ne se recompose pas.

    Regime B de `F2`, mesure : la liberation annoncait `rang_libere=True`,
    laissait INTACTE la ligne d'eau de la famille visee, et DETRUISAIT celle
    d'une autre famille. Deux mensonges dans une seule operation.

    Le banc lit la cle attendue de `cle_de_famille_de_master` plutot que de la
    composer : une assertion sur le litteral `"prores_422|uhd2160"` serait
    verte le jour ou le separateur change, et fausse ensuite.
    """
    from mixed_media_utility import encode as _encode
    from mixed_media_utility.io import encode_manifest

    cle_defaut = _encode.cle_de_famille_de_master("prores_422", None)
    cle_uhd = _encode.cle_de_famille_de_master("prores_422", "uhd2160")
    projet = _projet_a_resolutions(
        tmp_path,
        [("", 1), ("uhd2160", 1), ("uhd2160", 2), ("uhd2160", 3)],
        lignes_d_eau={cle_defaut: 1, cle_uhd: 3})

    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422",
        resolution="uhd2160", version=3, liberer_le_rang=True)

    assert rapport.rang_libere is True
    lot = json.loads((projet / "project.json").read_text(encoding="utf-8"))["lots"][0]
    apres = lot.get(encode_manifest.MASTERS_WATERMARK_FIELD) or {}
    assert apres.get(cle_defaut) == 1, (
        f"la ligne d'eau du DEFAUT a bouge alors que rien de sa famille n'a "
        f"ete retire: {apres}")
    assert apres.get(cle_uhd) == 2, (
        f"la ligne d'eau de la famille uhd2160 n'a pas descendu: {apres}")


def test_ARB224c_le_PRODUCTEUR_reprend_le_rang_LIBERE(tmp_path):
    """La mesure qui compte : ce que le prochain encodage fait du manifeste.

    Une frontiere sur le seul manifeste dirait « la cle a bouge » ; celle-ci
    dit ce que la liberation ACHETE, et c'est la promesse d'`EPIC11-ARB-92`.
    Mesure de la couche 1 sur le code d'avant : le prochain encodage par defaut
    sautait a `_v3` -- un rang qu'aucun de ses masters n'a jamais porte -- et
    la famille `uhd2160` repartait a `_v4` MALGRE la liberation explicite.
    """
    from mixed_media_utility import encode as _encode

    cle_defaut = _encode.cle_de_famille_de_master("prores_422", None)
    cle_uhd = _encode.cle_de_famille_de_master("prores_422", "uhd2160")
    projet = _projet_a_resolutions(
        tmp_path,
        [("", 1), ("uhd2160", 1), ("uhd2160", 2), ("uhd2160", 3)],
        lignes_d_eau={cle_defaut: 1, cle_uhd: 3})

    remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422",
        resolution="uhd2160", version=3, liberer_le_rang=True)

    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    assert _encode.resolve_master_version_rank(
        manifest, "L", profile_id="prores_422", container="mov",
        resolution_segment="uhd2160") == 3, "le rang libere doit se reprendre"
    assert _encode.resolve_master_version_rank(
        manifest, "L", profile_id="prores_422", container="mov",
        resolution_segment=None) == 2, (
        "le defaut ne doit pas SAUTER un rang qu'il n'a jamais porte")


def test_ARB224c_la_famille_d_un_master_ne_depend_pas_de_l_ORDRE_des_lots(tmp_path):
    """Point 2 et point 4 de la regle des fabriques, pour le LOT.

    Le lot vise etait TOUJOURS en premiere position de `manifest["lots"]` dans
    toutes les fabriques du bloc `EPIC11-ARB-224` -- c'est la cause directe de
    `C1-04`, restee invisible faute d'un banc qui deplace la cible.

    La mesure compare les DEUX ORDRES entre eux, et pas seulement chacun a une
    valeur attendue : une dependance a l'ordre d'iteration ne se voit par
    aucune position unique. Et elle porte en plus une assertion concrete, sans
    quoi deux resultats egalement faux se confirmeraient l'un l'autre.
    """
    from mixed_media_utility.io import encode_manifest

    resultats = {}
    for ordre in (("L", "AUTRE"), ("AUTRE", "L")):
        racine = tmp_path / ("-".join(ordre))
        racine.mkdir()
        projet = _projet_a_resolutions(
            racine, [("", 1), ("uhd2160", 1), ("uhd2160", 2)], ordre=ordre)
        remove_project_element(
            projet, lot_id="L", dry_run=False, master=True,
            profile="prores_422", resolution="uhd2160", version=2,
            liberer_le_rang=True)
        manifest = json.loads(
            (projet / "project.json").read_text(encoding="utf-8"))
        lot = next(l for l in manifest["lots"] if l["lot_id"] == "L")
        resultats[ordre] = (
            sorted(e["path"] for e in lot.get("encoded_masters") or []),
            lot.get(encode_manifest.MASTERS_WATERMARK_FIELD),
            sorted(str(c.relative_to(projet)) for c in
                   (projet / project_layout.OUTPUTS_DIRNAME).iterdir()),
        )

    en_tete, en_queue = resultats[("L", "AUTRE")], resultats[("AUTRE", "L")]
    assert en_tete == en_queue, (
        "le meme manifeste, la meme commande, et deux resultats differents "
        f"selon la POSITION du lot vise: {en_tete} contre {en_queue}")
    chemins, _ligne, sur_le_disque = en_tete
    assert len(chemins) == 2, chemins
    assert not any(chemin.endswith("_v2.mov") for chemin in chemins), chemins
    assert len(sur_le_disque) == 2, sur_le_disque


# --- `C1-04` : le verdict d'un `--scan` ne depend pas de l'ORDRE des lots ---


def _projet_a_scan_PARTAGE(tmp_path, position):
    """Un dossier de scan declare par DEUX lots, la cible a la position dite.

    Regle des fabriques, points 2, 2 bis et 4 : TROIS lots distinguables, et la
    cible placee successivement en TETE, au MILIEU et en QUEUE de
    `manifest["lots"]` -- la liste que `_famille_de_scan` parcourt. C'est le
    seul moyen de voir une dependance a l'ordre d'iteration : elle ne se voit
    par aucune position unique, et la cible au milieu seule ne demasque pas un
    balayage tronque.
    """
    autres = ["VOISIN-A", "VOISIN-B"]
    ordre = list(autres)
    ordre.insert({"tete": 0, "milieu": 1, "queue": 2}[position], "L")
    lots = []
    for lot_id in ordre:
        entree = {"lot_id": lot_id, "rush_id": "R"}
        # Le lot vise ET un SEUL des voisins declarent le meme slug : le
        # troisieme lot est le temoin qui distingue « partage » de « tout le
        # monde le declare ».
        if lot_id in ("L", "VOISIN-B"):
            entree["reconstructions"] = [{"ingest_slug": "S_v2"}]
        lots.append(entree)
    manifest = {"schema_version": "2.1", "project_id": "p",
                "rushes": [{"rush_id": "R"}], "lots": lots}
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    dossier = projet / project_layout.SCANS_DIRNAME / "S_v2"
    dossier.mkdir(parents=True)
    (dossier / "planche.tif").write_bytes(b"scan papier irremplacable")
    return projet


@pytest.mark.parametrize("position", ("tete", "milieu", "queue"))
def test_ARB224c_un_scan_declare_par_DEUX_lots_ne_se_supprime_PAS(
    tmp_path, position
):
    """`C1-04`, critique, classe « ordre d'iteration » -- zero survivant tolere.

    `_famille_de_scan` s'arretait au PREMIER lot qui declare le slug. Mesure :
    meme manifeste, meme commande, seul l'ORDRE change --

    * cible en TETE : le dossier etait DETRUIT alors qu'un autre lot le
      declare, dont la declaration restait pendante ;
    * cible en QUEUE : le refus se contredisait dans la meme phrase (« ne
      declare aucun scan... Scans declares par ce lot: ['S_v2'] »).

    `_famille_de_master` refuse deja ce cas par `_refuser_l_annexe_partagee` --
    le patron existe dans le meme fichier. La regle 4.0(c) de la politique dit
    par ailleurs que mutmut est structurellement aveugle a cette classe : elle
    ne se mesure que par une fabrique qui deplace la cible.

    Un dossier de scan porte des planches PAPIER numerisees : la seule famille
    d'objets que ce module declare lui-meme non recalculable.
    """
    projet = _projet_a_scan_PARTAGE(tmp_path, position)
    dossier = projet / project_layout.SCANS_DIRNAME / "S_v2"

    with pytest.raises(ProjectMaintenanceError) as refus:
        remove_project_element(projet, lot_id="L", dry_run=False, scan="S",
                               version=2)

    assert dossier.is_dir(), "le scan d'un lot TIERS a ete detruit"
    message = str(refus.value)
    assert "ne declare aucun scan" not in message, (
        "le refus affirme que le lot ne declare pas un scan qu'il declare, et "
        f"qu'il liste dans la meme phrase: {message}")
    # Le refus NOMME les lots en conflit : sans eux l'operateur ne peut pas
    # reparer son manifeste, et le refus serait le blocage sec interdit.
    assert "'L'" in message and "'VOISIN-B'" in message, message
    assert "'VOISIN-A'" not in message, (
        f"un lot qui ne declare PAS le scan est nomme comme conflictuel: {message}")


@pytest.mark.parametrize("position", ("tete", "milieu", "queue"))
def test_ARB224c_un_scan_NON_partage_se_supprime_a_CHAQUE_position(
    tmp_path, position
):
    """Le controle POSITIF, sans lequel le precedent se satisferait d'un refus
    systematique.

    Une frontiere qui n'exige qu'un refus est verte si l'on refuse TOUT : le
    banc doit donc montrer que la meme fabrique, privee du seul partage,
    supprime bien -- et a chacune des trois positions, la ou le defaut de
    balayage vivait.
    """
    projet = _projet_a_scan_PARTAGE(tmp_path, position)
    manifest = json.loads((projet / "project.json").read_text(encoding="utf-8"))
    for lot in manifest["lots"]:
        if lot["lot_id"] == "VOISIN-B":
            lot.pop("reconstructions")
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")

    rapport = remove_project_element(projet, lot_id="L", dry_run=False,
                                     scan="S", version=2)

    assert rapport.supprime is True
    assert not (projet / project_layout.SCANS_DIRNAME / "S_v2").exists()


# --- `M7` et `M13` : les deux mutants SURVIVANTS de la couche 2 -------------


def _projet_a_master_NON_CONFORME(tmp_path):
    """Un master conforme et un master renomme a la main, au MEME rang.

    C'est la forme que `test_ARB224b_un_master_RENOMME_a_la_main_reste_supprimable`
    n'exerce pas : il n'a le nom non conforme que SEUL a son rang, cas ou
    `None` et `""` sont indiscernables -- « seul a son rang » est precisement
    ce que le point 2 de la regle des fabriques interdit.
    """
    lot = {"lot_id": "L", "rush_id": "R", "encoded_masters": [
        {"path": project_layout.OUTPUTS_DIRNAME + "/L_mmu_prores_422.mov",
         "profile_id": "prores_422"},
        {"path": project_layout.OUTPUTS_DIRNAME + "/RENOMME-A-LA-MAIN.mov",
         "profile_id": "prores_422"},
    ]}
    manifest = {"schema_version": "2.1", "project_id": "p",
                "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
                "lots": [lot, {"lot_id": "AUTRE", "rush_id": "R2"}]}
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir()
    for entree in lot["encoded_masters"]:
        (projet / entree["path"]).write_bytes(b"master")
    return projet


def test_ARB224c_un_nom_NON_CONFORME_n_est_pas_lu_comme_le_DEFAUT(tmp_path):
    """Mutant `M7`, SURVIVANT de la campagne de la couche 2 -- classe critique.

    Le mutant remplace le dernier `return None` de
    `_segment_de_resolution_declare` par `return ""` : un master au nom non
    conforme est alors lu comme un master a la resolution PAR DEFAUT. La
    docstring de la fonction declare cette distinction « indispensable, sinon
    il serait apparie a l'aveugle avec la resolution par defaut » -- et rien ne
    la mesurait.

    C'est un defaut d'APPARIEMENT : il decide QUEL FICHIER part, pas un libelle.
    """
    projet = _projet_a_master_NON_CONFORME(tmp_path)

    rapport = remove_project_element(
        projet, lot_id="L", dry_run=False, master=True, profile="prores_422",
        resolution="hd1080")

    assert rapport.supprime is True
    assert not (projet / project_layout.OUTPUTS_DIRNAME
                / "L_mmu_prores_422.mov").exists()
    assert (projet / project_layout.OUTPUTS_DIRNAME
            / "RENOMME-A-LA-MAIN.mov").is_file(), (
        "le master au nom NON CONFORME a ete lu comme le defaut et emporte")


def test_ARB224c_le_refus_DISTINGUE_le_defaut_du_nom_non_conforme(tmp_path):
    """Le symetrique de `M7`, sur le REFUS plutot que sur l'appariement.

    Sans `--resolution`, les deux entrees sont ambigues et le refus doit les
    nommer SEPAREMENT -- `(defaut)` d'un cote, `(nom non conforme)` de l'autre,
    plus la limite : aucune `--resolution` n'atteint la seconde. Sous `M7` les
    deux se confondent en `(defaut)`, et le refus qui sort est un tout autre
    refus, celui des « entrees indiscernables ».
    """
    projet = _projet_a_master_NON_CONFORME(tmp_path)

    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_element(projet, lot_id="L", dry_run=True, master=True,
                               profile="prores_422")

    message = str(erreur.value)
    assert "(defaut)" in message, message
    assert "(nom non conforme)" in message, (
        f"le refus confond le nom non conforme avec le defaut: {message}")


def test_ARB224c_le_rapport_d_un_scan_nomme_la_VERSION_et_non_la_FAMILLE(tmp_path):
    """Mutant `M13`, SURVIVANT de la campagne de la couche 2 -- classe critique.

    Le mutant remplace le calcul du slug REEL par `slug = base`. La ligne
    d'apercu et la ligne de confirmation annoncent alors `element 'L (scan S)'`
    la ou l'outil detruit `scans/S_v3` : la sortie nomme la FAMILLE ENTIERE au
    moment ou l'operateur donne son consentement a la destruction d'UNE
    version.

    C'est la seule des quatre cibles dont l'etiquette ne porte pas le rang par
    construction -- `L (planche 3)`, `L (lot scanne v2)` et
    `L (master .../_v3.mov)` le portent tous.

    Le rang mesure est le 3, jamais l'origine : au rang 1 le mutant est
    indiscernable, ce qui est precisement pourquoi il faut mesurer ailleurs.
    """
    projet = _projet_a_trois_de_chaque(tmp_path)

    apercu = remove_project_element(projet, lot_id="L", dry_run=True,
                                    scan="S", version=3)
    assert apercu.cible.endswith("(scan S_v3)"), (
        f"l'apercu nomme la FAMILLE la ou la version 3 est visee: {apercu.cible!r}")

    rapport = remove_project_element(projet, lot_id="L", dry_run=False,
                                     scan="S", version=3)
    assert rapport.cible == apercu.cible, (
        "l'apercu et la confirmation ne nomment pas le meme objet")
    assert not (projet / project_layout.SCANS_DIRNAME / "S_v3").exists()
    assert (projet / project_layout.SCANS_DIRNAME / "S_v2").is_dir()


# ---------------------------------------------------------------------------
# Story 11.14, lot C -- reprise du 2026-09-05 : le retrait se mesure sur les
# TREIZE commandes, et sur le PARSEUR plutot que sur le texte
#
# **Ce qu'aucune des frontieres d'avant ne pouvait voir, et ce n'est pas un
# oubli d'ecriture.** Les trois volets du lot C mesurent `project remove` : le
# nom retire y est refuse, le nom neuf y fait le geste, le nom jamais employe y
# recoit le meme refus. Et `NOMS_RETIRES_DES_AIDES` balaie tout `cli.py`, donc
# il attraperait un `add_argument('--frames', ...)` reintroduit sur n'importe
# quelle commande -- c'est une chaine litterale.
#
# Ce qu'un balayage de TEXTE ne peut structurellement pas voir, c'est
# l'ABREVIATION. `argparse` accepte par defaut tout prefixe non ambigu :
# `mmu makepdf --frames 6` est reconnu comme `--frames-par-page 6` alors
# qu'aucun litteral `--frames` n'existe dans `cli.py`. Il faut interroger le
# PARSEUR. C'est le piege que le lot C a paye une fois sur `project remove`
# (d'ou son `allow_abbrev=False`) ; cette frontiere-ci le mesure sur les treize
# commandes plutot que sur la seule ou il avait mordu.
#
# **Mesure du 2026-09-05, exhaustive plutot qu'illustrative** : trois noms
# retires x **dix-huit** commandes = **54 paires**, **une seule fautive**
# (`makepdf`/`--frames`). Elle est inscrite en dette plutot que corrigee --
# voir :data:`ABREVIATIONS_TOLEREES`.
#
# **Le cardinal a ete faux une premiere fois, et c'est le banc qui l'a dit.**
# Un `grep add_parser` de `cli.py` rend treize commandes ; le parseur construit
# en connait dix-huit, parce que cinq sont des sous-parseurs imbriques (`scan
# detect`, `scan calibrate`, `poc build-sheet`, `poc process-scan`, `makepdf
# calibration-page`). Le balayage etait juste -- il lisait deja le parseur --,
# seul le chiffre que j'en avais tire etait faux. Un cardinal se lit ou il se
# calcule, jamais dans la prose qui le cite.
# ---------------------------------------------------------------------------

import argparse as _argparse_module  # noqa: E402

#: Les noms d'OPTION retires par la story 11.14, **toutes commandes
#: confondues**. Table distincte de :data:`NOMS_RETIRES_DES_AIDES`, qui balaie
#: du TEXTE : celle-ci se mesure sur le PARSEUR, seul endroit ou une
#: abreviation se voit.
#:
#: Les trois maillons de la chaine de renommages y sont, et chacun garde sa
#: ligne : `--frames` (`EPIC11-ARB-220`), `--frames-scannees` (`ARB-224`,
#: premier temps) et `--tirage` (`ARB-224`, second temps -- Egan, verbatim :
#: « "--tirage" n'est pas un mot de vocabulaire. C'est "planche". »). Retirer
#: un maillon au motif qu'un nom plus recent existe rouvrirait le premier
#: defaut.
#:
#: La liste a ete etablie par MESURE et non de memoire : difference des
#: litteraux `'--xxx'` de `cli.py` entre le `baseline_commit` (`e79eaf643`) et
#: la tete du lot. Deux options ont disparu (`--frames`, `--tirage`), une
#: troisieme n'a jamais quitte la branche (`--frames-scannees`), et **aucune
#: sous-commande n'a ete renommee** -- le releve `add_parser` est identique des
#: deux cotes, ce que :func:`test_AUCUNE_sous_commande_n_a_ete_renommee` fige.
NOMS_D_OPTION_RETIRES: tuple[str, ...] = (
    "--frames", "--frames-scannees", "--tirage",
)

#: La dette MESUREE, bornee a une PAIRE (commande, nom) et jamais a une
#: commande entiere -- une exception au fichier laisserait rentrer les deux
#: autres noms par la meme porte.
#:
#: Origine : finding `R2` de la couche 2 de la revue du 2026-09-04, remesure le
#: 2026-09-05 et reduit a **une seule paire sur cinquante-quatre**. Le remede
#: (`allow_abbrev=False` sur `makepdf`, comme `remove` et `add-rush` le portent
#: deja) retire TOUTES les abreviations de la commande d'un coup : c'est un
#: choix d'interface, pas un correctif de revue, et `deferred-work.md` le pose
#: avec les onze sous-parseurs concernes.
#:
#: **VIDE depuis le 2026-09-06** (`EPIC11-ARB-248`, Q18 : « Porter
#: `allow_abbrev=False` aux seize »). La seule paire qui y figurait --
#: `("makepdf", "--frames")`, qui abregeait `--frames-par-page` et rendait
#: donc un resultat plausible plutot qu'un refus -- est fermee par le drapeau
#: porte aux seize sous-parseurs restants. Le mecanisme reste en place,
#: `test_la_TOLERANCE_d_abreviation_est_encore_REELLE` avec lui : une dette
#: future s'y inscrit sans qu'on ait a le reconstruire, et
#: `test_AUCUNE_tolerance_d_abreviation_ne_SUBSISTE` rougit si une entree
#: revient sans qu'un arbitrage la porte.
ABREVIATIONS_TOLEREES: dict[tuple[str, str], str] = {}


def _ranger_les_commandes(parseur, prefixe: str, table: dict) -> None:
    """Chaque (sous-)commande, ses options ET son reglage d'abreviation.

    **Le second element n'est pas un ornement** : c'est lui qui distingue un
    nom refuse d'un nom silencieusement accepte. Un releve qui ne porterait que
    les options declarerait `makepdf` sain, puisque `--frames` n'y est pas
    declare -- et c'est pourtant la seule commande du depot qui l'accepte.
    """
    options = {
        chaine
        for action in parseur._actions
        for chaine in action.option_strings
        if chaine.startswith("--")
    }
    if prefixe:
        table[prefixe] = (options, bool(getattr(parseur, "allow_abbrev", True)))
    for action in parseur._actions:
        if isinstance(action, _argparse_module._SubParsersAction):
            for nom, sous in action.choices.items():
                _ranger_les_commandes(sous, f"{prefixe} {nom}".strip(), table)


def _commandes_du_depot() -> dict[str, tuple[set[str], bool]]:
    """Le releve complet, lu du parseur CONSTRUIT et jamais d'un grep."""
    table: dict[str, tuple[set[str], bool]] = {}
    _ranger_les_commandes(_parseur_reel_de_la_cli(), "", table)
    return table


def _accepte(drapeaux: set[str], abreviation_permise: bool,
             nom: str) -> str | None:
    """Le drapeau que `nom` atteindrait, ou `None` si la commande le refuse.

    Deux chemins d'acceptation, et le second est celui qu'un balayage de TEXTE
    ne peut pas voir :

    * le nom **existe** tel quel -- un alias reintroduit ;
    * le nom est un **prefixe non ambigu** d'un nom vivant, et la commande
      laisse `argparse` abreger. Un seul candidat rend l'abreviation
      acceptable ; deux la rendent `ambiguous option`, c'est-a-dire refusee --
      donc pas une acceptation silencieuse, donc pas ce qu'on cherche.
    """
    if nom in drapeaux:
        return nom
    if not abreviation_permise:
        return None
    candidats = [d for d in drapeaux if d.startswith(nom)]
    return candidats[0] if len(candidats) == 1 else None


@pytest.mark.parametrize("nom", NOMS_D_OPTION_RETIRES)
def test_aucune_COMMANDE_n_accepte_un_nom_d_option_RETIRE(nom):
    """Frontiere NEGATIVE sur le parseur, **une par nom retire** (AC 4.3).

    Elle balaie **toutes** les commandes plutot que `project remove` seule : un
    nom retire d'une commande et laisse vivant sur une autre n'est pas retire,
    il est deplace, et `EPIC11-ARB-220` tranche le retrait **PUR**.
    """
    fautives = {
        commande: cible
        for commande, (drapeaux, abrev) in _commandes_du_depot().items()
        if (cible := _accepte(drapeaux, abrev, nom))
        and (commande, nom) not in ABREVIATIONS_TOLEREES
    }
    assert fautives == {}, (
        f"{nom!r} est encore accepte par ces commandes:\n"
        + "\n".join(f"  mmu {commande} {nom}  ->  {cible}"
                    for commande, cible in sorted(fautives.items()))
        + "\nEPIC11-ARB-220 : retrait PUR, ni alias ni abreviation."
    )


def test_AUCUNE_tolerance_d_abreviation_ne_SUBSISTE():
    """La table est VIDE, et son vide se mesure (`EPIC11-ARB-248`).

    **Pourquoi ce test en plus du parametre ci-dessous.** Sur une table vide,
    `parametrize` ne rend aucun cas : le test d'a cote devient un `skip`, et
    une frontiere sautee n'affirme rien. Une entree reintroduite sans
    arbitrage rendrait alors le skip a la vie sans que personne ne l'ait
    decide -- c'est-a-dire qu'une dette pourrait rentrer par la porte qui
    servait a la faire sortir.

    Ce test-ci est l'inverse : il rougit a la REINTRODUCTION. Une tolerance
    neuve est un choix d'interface, donc elle se paie d'une ligne ici et d'un
    arbitrage ailleurs, jamais d'un ajout silencieux au dictionnaire.
    """
    assert ABREVIATIONS_TOLEREES == {}, (
        "une tolerance d'abreviation est revenue:\n"
        + "\n".join(f"  mmu {commande} {nom}  ({motif})"
                     for (commande, nom), motif
                     in sorted(ABREVIATIONS_TOLEREES.items()))
        + "\nEPIC11-ARB-248 a porte `allow_abbrev=False` aux seize : plus "
          "aucune commande n'abrege. Une exception neuve est un arbitrage "
          "produit, pas une entree de dictionnaire.")


@pytest.mark.parametrize("paire", sorted(ABREVIATIONS_TOLEREES))
def test_la_TOLERANCE_d_abreviation_est_encore_REELLE(paire):
    """Une dette qui se corrige doit ROUGIR, pas rester verte en silence.

    Mecanisme de l'`xfail(strict=True)` du lot A, deja transpose par la
    frontiere documentaire (`test_la_DETTE_est_encore_reelle`) : le jour ou
    `makepdf` recoit `allow_abbrev=False`, ce test rougit et force a retirer
    l'entree, au lieu de laisser une tolerance permanente deguisee en
    frontiere verte.
    """
    commande, nom = paire
    releve = _commandes_du_depot().get(commande)
    assert releve is not None, (
        f"la commande {commande!r} n'existe plus : retirer son entree de "
        "ABREVIATIONS_TOLEREES.")
    drapeaux, abrev = releve
    assert _accepte(drapeaux, abrev, nom) is not None, (
        f"`mmu {commande} {nom}` n'est plus accepte. La dette est FERMEE : "
        f"retirer son entree de ABREVIATIONS_TOLEREES.\n"
        f"Origine : {ABREVIATIONS_TOLEREES[paire]}")


def test_le_releve_des_COMMANDES_lit_bien_le_parseur_du_depot():
    """Garde-fou : un releve casse rendrait un vide, donc tout vert.

    Le mode de panne exact que `CLAUDE.md` nomme -- « un compteur qui court
    n'est pas un producteur vivant » -- transpose au balayage d'un parseur. Il
    mesure les deux moities du releve : les options **et** le reglage
    d'abreviation, faute de quoi ce dernier pourrait etre lu `True` partout
    sans que rien ne le dise.
    """
    table = _commandes_du_depot()
    assert len(table) >= 18, f"seules {sorted(table)} commandes sont lues"
    assert "--lot-scanne" in table["project remove"][0], sorted(table)
    assert "--frames-par-page" in table["makepdf"][0], sorted(table)
    assert table["project remove"][1] is False, (
        "`project remove` est lu comme acceptant les abreviations : le releve "
        "du reglage ne mesure plus rien.")
    # **Le temoin permissif est desormais SYNTHETIQUE, et il a change de nature
    # le 2026-09-06** (`EPIC11-ARB-248`). Il lisait `makepdf`, seule commande
    # du depot qui acceptait encore les abreviations ; le drapeau porte aux
    # seize l'a fermee, et avec elle le seul temoin `True` que le depot
    # offrait. Le lire sur un parseur bati pour l'occasion est plus juste, pas
    # seulement plus commode : ce garde-fou mesure le RELEVE, pas l'etat du
    # depot -- lier sa moitie `True` a un defaut du produit la ferait
    # disparaitre le jour ou le defaut se corrige, c'est-a-dire exactement
    # aujourd'hui.
    temoin = _argparse_module.ArgumentParser(prog="temoin")
    temoin.add_subparsers().add_parser("permissif", allow_abbrev=True)
    lu: dict[str, tuple[set[str], bool]] = {}
    _ranger_les_commandes(temoin, "", lu)
    assert lu["permissif"][1] is True, (
        "un parseur bati avec `allow_abbrev=True` est lu comme les refusant : "
        "le releve du reglage rend `False` partout, donc il ne mesure rien.")


@pytest.mark.parametrize("bord", ("tete", "milieu", "queue"))
def test_le_releve_des_COMMANDES_MORD_a_CHAQUE_BORD(bord):
    """Regle des fabriques, point 4 : une cible en TETE, au MILIEU, en QUEUE.

    **Le temoin traverse le RELEVE, pas la table qu'il mesure**, et c'est une
    correction deja payee deux fois dans cette story : par le lot C (« le
    temoin de bord ne mesurait que l'appariement, pas le collecteur ») puis par
    le lot E1 (mutant `M8`, temoin tautologique qui bouclait sur son propre
    tuple). Un `[:-1]` ou un `[1:]` sur le parcours des sous-commandes rougit
    donc ici.

    Les trois commandes du parseur miniature portent des drapeaux
    **distinguables** -- trois noms differents, pas un remplissage uniforme :
    une permutation ne se voit que si les elements different.
    """
    racine = _argparse_module.ArgumentParser(prog="temoin")
    sous = racine.add_subparsers()
    for nom, drapeau in (("a-tete", "--frames"),
                         ("m-milieu", "--frames-scannees"),
                         ("z-queue", "--tirage")):
        sous.add_parser(nom).add_argument(drapeau, dest=nom.replace("-", "_"))

    table: dict[str, tuple[set[str], bool]] = {}
    _ranger_les_commandes(racine, "", table)

    commande, drapeau = {"tete": ("a-tete", "--frames"),
                         "milieu": ("m-milieu", "--frames-scannees"),
                         "queue": ("z-queue", "--tirage")}[bord]
    assert commande in table, (
        f"la commande de {bord} manque au releve {sorted(table)} : le parcours "
        "des sous-commandes est TRONQUE, et une commande perdue en tete ou en "
        "queue emporte sa frontiere avec elle.")
    assert drapeau in table[commande][0], (
        f"{drapeau!r} manque a {commande!r} : le releve des options est "
        f"tronque ({sorted(table[commande][0])}).")


def test_le_releve_ne_confond_PAS_un_nom_VIVANT_avec_un_nom_retire():
    """Volet symetrique : sans lui, une lecture trop large serait verte partout.

    Trois moities, et la deuxieme est celle qui manque d'habitude :

    1. aucun nom VIVANT du parseur n'est reconnu comme retire -- `--planche`
       n'est pas `--tirage`, `--lot-scanne` n'est pas `--frames` ;
    2. la lecture MORD quand elle doit : `--frames` EST bien l'abreviation de
       `--frames-par-page`. Sans cette moitie, un :func:`_accepte` qui rendrait
       toujours `None` laisserait la frontiere principale verte sur un parseur
       entierement fautif ;
    3. deux candidats rendent l'option AMBIGUE, donc refusee par `argparse` :
       ce n'est pas une acceptation silencieuse, et la lecture ne doit pas la
       signaler.
    """
    vivants = ("--frames-par-page", "--planche", "--lot-scanne", "--lot-slug",
               "--version", "--avec-scans")
    for vivant in vivants:
        assert vivant not in NOMS_D_OPTION_RETIRES, (
            f"{vivant!r} est une option VIVANTE du depot et figure a la table "
            "des noms retires.")

    # (1) -- `--frames` est ecarte face a `--frames-par-page` : il EN est le
    # prefixe, c'est la dette `R2`, et la moitie (2) la mesure a part.
    for nom in NOMS_D_OPTION_RETIRES:
        for vivant in vivants:
            if vivant.startswith(nom):
                continue
            assert _accepte({vivant}, True, nom) is None, (
                f"{nom!r} attrape {vivant!r}, qui est une option VIVANTE.")

    # (2) -- la lecture n'est pas morte.
    assert _accepte({"--frames-par-page"}, True, "--frames") == \
        "--frames-par-page", (
            "la lecture des abreviations ne mord plus : la frontiere "
            "principale serait verte sur un parseur entierement fautif.")

    # (3) -- l'ambiguite est un refus, pas une acceptation.
    assert _accepte({"--frames-par-page", "--frames-scannees"}, True,
                    "--frames") is None

    # (4) -- et un parseur qui REFUSE les abreviations n'en accepte aucune.
    assert _accepte({"--frames-par-page"}, False, "--frames") is None


def test_AUCUNE_sous_commande_n_a_ete_renommee_par_la_story():
    """L'AC 4.3 vise « chaque option ET SOUS-COMMANDE renommee ». Le second
    ensemble est VIDE, et ca se mesure plutot que ca ne se suppose.

    Un ensemble vide non mesure est le pire cas d'une frontiere : elle est
    verte parce qu'elle ne porte sur rien, et personne ne le sait. Ici, le
    releve des sous-commandes est fige : le jour ou l'une est renommee, ce test
    rougit et force a lui donner sa ligne dans
    :data:`NOMS_D_OPTION_RETIRES` -- ou dans la table soeur qui n'existe pas
    encore, ce qui est precisement ce qu'il faut apprendre a ce moment-la.

    Le releve est celui du `baseline_commit` `e79eaf643`, plus `add-rush`
    (story 11.4e, une commande AJOUTEE et non renommee).
    """
    #: Les DIX-HUIT (sous-)commandes du parseur construit. **Ce releve a
    #: corrige une mesure fausse le 2026-09-05** : un `grep add_parser` de
    #: `cli.py` en rendait treize, parce qu'il ne voit pas les sous-parseurs
    #: imbriques (`scan detect`, `poc build-sheet`, `makepdf
    #: calibration-page`...). C'est exactement le motif pour lequel ce banc lit
    #: le parseur CONSTRUIT plutot qu'un grep -- et la premiere redaction de ce
    #: test etait elle-meme tombee dans le piege qu'il existe pour fermer.
    attendu = {
        "encode", "extract", "makepdf", "makepdf calibration-page", "poc",
        "poc build-sheet", "poc process-scan", "previz", "project",
        "project add-rush", "project remove", "reconstruct-project", "relink",
        "scan", "scan calibrate", "scan detect", "scan-write",
        "set-default-profile",
    }
    releve = set(_commandes_du_depot())
    assert releve == attendu, (
        "le releve des (sous-)commandes a change:\n"
        f"  apparues : {sorted(releve - attendu)}\n"
        f"  disparues: {sorted(attendu - releve)}\n"
        "Une commande DISPARUE est un renommage, et l'AC 4.3 exige alors une "
        "frontiere negative pour son ancien nom.")


# ---------------------------------------------------------------------------
# `EPIC11-ARB-248` -- **AUCUN parseur de la CLI n'accepte les abreviations**
# ---------------------------------------------------------------------------
#
# **La frontiere que la table d'au-dessus ne pouvait pas porter.** Les deux
# frontieres precedentes mesurent des NOMS : « aucune commande n'accepte
# `--frames` », « la tolerance est encore reelle ». Elles sont exhaustives sur
# les trois noms retires par la 11.14, et muettes sur tous les autres. Or ce
# que `EPIC11-ARB-248` tranche n'est pas un nom : c'est un REGLAGE. Un
# dix-septieme sous-parseur ajoute demain sans `allow_abbrev=False`
# n'accepterait aucun des trois noms retires -- donc ne ferait rougir aucune
# frontiere existante -- et rouvrirait pourtant la surface entiere, sur ses
# propres options.
#
# **Pourquoi negative, et pourquoi par INTROSPECTION.** Aucun test positif ne
# verrait revenir un parseur permissif : un test positif mesure ce qui est
# ecrit, pas ce qui manque. Et un grep de `cli.py` se contourne par une
# variable (`sub.add_parser(nom, **reglages)`) ou par un auxiliaire ; le
# parseur CONSTRUIT, lui, porte l'attribut reel.
#
# **Le recensement du 2026-09-06, mesure et non cite** : dix-neuf parseurs
# (racine + dix-huit sous-parseurs), trois portaient le drapeau, seize ne le
# portaient pas. Le chiffre du registre (`Q18`) est confirme au parseur pres.


def _reglages_d_abreviation_de_la_cli(racine=None) -> dict[str, bool]:
    """Le reglage d'abreviation de CHAQUE parseur, **racine comprise**.

    Distinct de :func:`_commandes_du_depot`, et la difference n'est pas de
    confort : ce releve-la saute la racine (`if prefixe:`), qui est pourtant un
    parseur comme les autres et le premier qu'un operateur rencontre. Un
    balayage qui la saute laisse `mmu --vers` hors de toute mesure.
    """
    reglages: dict[str, bool] = {}

    def _descendre(parseur, chemin: str) -> None:
        # **`parseur.allow_abbrev` NU, sans `getattr` de repli**, et c'est une
        # correction de campagne de mutation (2026-09-06, `EPIC11-ARB-248`).
        # Un repli `getattr(..., True)` a survecu a sa propre mutation en
        # `False` -- et il ne pouvait pas en etre autrement :
        # `ArgumentParser.__init__` pose TOUJOURS l'attribut, donc la branche
        # de repli est morte, donc sa valeur ne se mesure pas. Une branche que
        # rien ne peut atteindre n'est pas une precaution, c'est un mutant
        # equivalent qu'on s'installe. Un objet sans l'attribut n'est pas un
        # parseur : qu'il leve bruyamment.
        reglages[chemin] = bool(parseur.allow_abbrev)
        for action in parseur._actions:
            if isinstance(action, _argparse_module._SubParsersAction):
                for nom, sous in action.choices.items():
                    _descendre(sous, f"{chemin} {nom}".strip())

    _descendre(racine if racine is not None else _parseur_reel_de_la_cli(),
               NOM_DU_PARSEUR_RACINE)
    return reglages


def _parseur_au_chemin(racine, chemin: str):
    """Le parseur que `chemin` designe, ou `None`.

    Sert a GREFFER : le temoin de bord doit pouvoir rendre permissif un
    parseur precis de l'arbre reel, puis faire relire l'arbre par le
    collecteur de production -- pas par une copie du parcours ecrite dans le
    test, qui ne mesurerait qu'elle-meme.
    """
    courant = racine
    for segment in chemin.split()[1:]:      # le premier segment est la racine
        suivant = None
        for action in courant._actions:
            if isinstance(action, _argparse_module._SubParsersAction):
                suivant = action.choices.get(segment, suivant)
        if suivant is None:
            return None
        courant = suivant
    return courant


#: Le nom sous lequel la racine figure au releve. Un litteral plutot qu'une
#: chaine vide : une chaine vide se confondrait avec « pas de chemin » et
#: disparaitrait d'un message d'erreur au moment ou il faut la lire.
NOM_DU_PARSEUR_RACINE = "<racine>"

#: Le cardinal MESURE le 2026-09-06, fige pour qu'un parseur perdu par un
#: parcours tronque se voie. Il monte quand une commande s'ajoute -- c'est
#: alors la borne qu'on releve, apres avoir verifie que la commande neuve
#: porte le drapeau.
CARDINAL_DES_PARSEURS_DE_LA_CLI = 19


def test_TOUT_parseur_de_la_CLI_refuse_les_ABREVIATIONS():
    """Frontiere NEGATIVE de reglage (`EPIC11-ARB-248`, Q18).

    Elle porte sur les dix-neuf parseurs a la fois plutot que sur les trois
    qui portaient deja le drapeau : `EPIC11-ARB-108` interdit le mecanisme par
    objet, et un reglage tenu sur quinze parseurs sur seize n'est pas un
    reglage, c'est une exception qui s'ignore.
    """
    reglages = _reglages_d_abreviation_de_la_cli()
    permissifs = sorted(nom for nom, strict in reglages.items() if strict)
    assert permissifs == [], (
        "ces parseurs acceptent encore les abreviations d'option:\n"
        + "\n".join(f"  mmu {nom}" for nom in permissifs)
        + "\nEPIC11-ARB-248 : `allow_abbrev=False` sur TOUS, sans exception "
          "par commande. Un sous-parseur n'herite PAS du drapeau du parent.")


def test_le_releve_des_PARSEURS_couvre_bien_la_CLI_entiere():
    """Garde-fou du releve : un parcours casse rendrait un vide, donc vert.

    Meme mode de panne que pour la table des commandes -- « un compteur qui
    court n'est pas un producteur vivant ». La frontiere ci-dessus affirme
    « aucun permissif » ; sur un releve vide, elle l'affirmerait aussi.
    """
    reglages = _reglages_d_abreviation_de_la_cli()
    assert len(reglages) == CARDINAL_DES_PARSEURS_DE_LA_CLI, (
        f"{len(reglages)} parseurs lus au lieu de "
        f"{CARDINAL_DES_PARSEURS_DE_LA_CLI} : "
        f"{sorted(reglages)}.\nUn parseur perdu emporte sa frontiere avec lui ;"
        " une commande AJOUTEE releve la borne, apres verification qu'elle "
        "porte `allow_abbrev=False`.")
    assert NOM_DU_PARSEUR_RACINE in reglages, (
        "la racine manque au releve : `mmu --vers` echapperait a la mesure.")
    # Les deux moities de la profondeur : une commande de premier niveau et
    # une commande IMBRIQUEE. Un parcours qui ne descendrait pas rendrait la
    # premiere et pas la seconde.
    assert "<racine> encode" in reglages, sorted(reglages)
    assert "<racine> poc process-scan" in reglages, sorted(reglages)


#: Regle des fabriques, point 4, appliquee au parcours des parseurs : une
#: cible en TETE, au MILIEU et en QUEUE -- et deux positions de plus que le
#: strict minimum, parce que ce parcours-ci a deux dimensions.
#:
#: * la **racine** est la cible que `_ranger_les_commandes` saute par
#:   construction : c'est le defaut exact que ce releve-ci existe pour fermer,
#:   et aucun autre bord ne le demasque ;
#: * `encode` est la premiere sous-commande du parcours, `reconstruct-project`
#:   la derniere -- un balayage tronque d'un cote ou de l'autre les perd ;
#: * `project remove` est au MILIEU : elle demasque un `find` fautif, qui est
#:   un autre mode de panne que la troncature ;
#: * `poc process-scan` est IMBRIQUEE **et** en queue de son groupe : elle
#:   demasque une descente qui s'arrete au premier niveau, et une troncature
#:   qui ne mordrait qu'a l'interieur d'un groupe.
#:
#: Les cinq portent des chemins DISTINGUABLES -- cinq noms differents, jamais
#: un remplissage uniforme : une permutation ne se voit que si les elements
#: different.
POSITIONS_DE_GREFFE: tuple[tuple[str, str], ...] = (
    ("racine", "<racine>"),
    ("tete", "<racine> encode"),
    ("milieu", "<racine> project remove"),
    ("imbriquee-en-queue", "<racine> poc process-scan"),
    ("queue", "<racine> reconstruct-project"),
)


@pytest.mark.parametrize("position,chemin", POSITIONS_DE_GREFFE,
                         ids=[nom for nom, _ in POSITIONS_DE_GREFFE])
def test_la_frontiere_des_ABREVIATIONS_MORD_a_CHAQUE_position(position, chemin):
    """Le temoin qui prouve que la frontiere ci-dessus n'est pas tautologique.

    **Greffe en MEMOIRE sur le parseur reellement construit**, jamais une
    edition de `cli.py` : on rend un parseur permissif le temps d'un test et on
    verifie que le releve le NOMME. Une frontiere qui affirme « aucun
    permissif » sans jamais en voir un affirme surtout que son parcours ne
    trouve rien.

    Le parseur est rebati a chaque appel de :func:`_parseur_reel_de_la_cli`,
    donc la greffe ne survit pas au test -- il n'y a rien a restaurer, et rien
    a restaurer est plus sur que restaurer bien.
    """
    racine = _parseur_reel_de_la_cli()
    cible = _parseur_au_chemin(racine, chemin)
    assert cible is not None, (
        f"le parseur de {position} ({chemin!r}) est introuvable dans l'arbre "
        "reel : la table des positions de greffe est perimee.")

    # **La greffe, en memoire et sur l'arbre REEL** : ce parseur-la redevient
    # permissif, puis c'est le collecteur DE PRODUCTION qui relit l'arbre. Rien
    # a restaurer -- `_parseur_reel_de_la_cli` rebatit l'arbre a chaque appel,
    # et rien a restaurer est plus sur que restaurer bien.
    cible.allow_abbrev = True

    reglages = _reglages_d_abreviation_de_la_cli(racine)
    assert chemin in reglages, (
        f"le parseur de {position} ({chemin!r}) manque au releve "
        f"{sorted(reglages)} : le parcours est TRONQUE, et un parseur perdu "
        "en tete, en queue ou au fond d'un groupe emporte sa frontiere.")
    permissifs = sorted(nom for nom, strict in reglages.items() if strict)
    assert permissifs == [chemin], (
        f"la greffe de {position} devait rendre EXACTEMENT {chemin!r} "
        f"permissif ; le releve rend {permissifs}.")


# ---------------------------------------------------------------------------
# `EPIC11-ARB-225` -- le chemin de SUPPRESSION resout LES DEUX racines
#
# C'est le site le plus dangereux du renommage. `_planche_pdf_declaree`
# compose le chemin CANDIDAT A LA SUPPRESSION quand le manifeste ne declare
# aucun `sheets_pdfs` -- c'est-a-dire pour tout projet anterieur a
# `EPIC11-ARB-90`, donc exactement les projets qui portent `patches/`. Sous le
# nom neuf seul, supprimer un lot d'un projet ancien laisse son PDF EN PLACE,
# et le rapport annonce le lot libere : une fuite silencieuse.
#
# « Une garde de repli fait VARIER le drapeau dont elle depend » : les trois
# etats de l'arborescence sont joues -- ANCIEN, NEUF, MIXTE.
# ---------------------------------------------------------------------------

#: Le nom que la recette de nom RECALCULE pour le lot cible de la fabrique.
#: Ecrit en clair plutot que derive de `naming` : une cible derivee du module
#: mesure serait tautologique et suivrait un renommage au lieu de le
#: contredire.
PLANCHE_RECALCULEE = "projet_rush-b_12_planches.pdf"


@pytest.mark.parametrize("dossiers,ou,etat", (
    (("patches",), "patches", "projet ANCIEN"),
    (("planches",), "planches", "projet NEUF"),
    (("planches", "patches"), "patches", "projet MIXTE, le PDF sous l'ancien"),
    (("planches", "patches"), "planches", "projet MIXTE, le PDF sous le neuf"),
))
def test_le_PDF_recalcule_est_trouve_dans_les_DEUX_racines(
        tmp_path, dossiers, ou, etat):
    """Le tirage est VISE la ou il est reellement, et il est supprime.

    Le manifeste de la fabrique ne declare aucun `sheets_pdfs` : on est donc
    sur le chemin de RECALCUL, le seul des deux qui compose un dossier. Le
    chemin declare, lui, porte son propre prefixe et n'a rien a resoudre.
    """
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    for nom in dossiers:
        (projet / nom).mkdir()
    (projet / ou / PLANCHE_RECALCULEE).write_bytes(b"pdf de planches")

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False)

    assert f"{ou}/{PLANCHE_RECALCULEE}" in rapport.fichiers_a_supprimer, etat
    assert not (projet / ou / PLANCHE_RECALCULEE).exists(), etat


def test_sans_le_repli_le_PDF_d_un_projet_ANCIEN_survit_a_la_suppression(
        tmp_path):
    """Le volet qui chiffre ce que la racine unique COUTAIT.

    Ce banc ne mesure pas « le chemin est bon » mais « le fichier n'est plus
    la ». C'est la seule formulation qui attrape la panne : un chemin vise
    sous `planches/` alors que le PDF vit sous `patches/` produit un rapport
    parfaitement plausible -- il NOMME un fichier -- et laisse le PDF sur le
    disque. Le rapport ment sans qu'aucune exception ne soit levee.
    """
    projet = _ecrire_projet(tmp_path, _manifeste_a_trois_lots())
    (projet / project_layout.LEGACY_PATCHES_DIRNAME).mkdir()
    (projet / project_layout.LEGACY_PATCHES_DIRNAME / PLANCHE_RECALCULEE).write_bytes(b"pdf de planches")
    assert not (projet / "planches").exists()

    rapport = remove_project_element(
        projet, lot_id="rush-b_12", dry_run=False)

    assert not (projet / project_layout.LEGACY_PATCHES_DIRNAME / PLANCHE_RECALCULEE).exists()
    # ... et le rapport ne promet pas un fichier sous une racine ou il n'a
    # jamais ete : un chemin `planches/...` ici serait la promesse fausse.
    assert not any(chemin.startswith("planches/")
                   for chemin in rapport.fichiers_a_supprimer), (
        rapport.fichiers_a_supprimer)
