# -*- coding: utf-8 -*-
"""`EPIC11-ARB-264` -- supprimer un GROUPE : N appels, au mieux, ligne par ligne.

Constat de terrain d'Egan du 2026-09-06 : « planches (l'ensemble) et masters
(l'ensemble d'un lot) ne sont pas selectionnables ». Un groupe n'existe pas au
coeur -- c'est l'ecran qui le fabrique --, donc le supprimer est **N appels** a
`remove_project_element`, la boucle au-dessus et jamais dedans.

La semantique d'echec partiel a ete tranchee par Egan par invite le 2026-09-07,
verbatim de l'option choisie : « Au mieux, avec un compte rendu ligne par ligne.
Le projet peut rester a moitie supprime, et il faut relancer en sachant ce qui
reste. » Le document d'arbitrage est
`_bmad-output/implementation-artifacts/decisions-2026-09-07-epic11-arb-264.md`.

**Regle des fabriques du CLAUDE.md, et elle mord ici directement.** Une
operation de groupe se casse a un rang precis : le banc joue donc la panne en
TETE, au MILIEU et en QUEUE. Un balayage qui s'arreterait au premier refus est
vert sur « une ligne du milieu refuse » si on ne regarde que le cardinal des
partis ; il ne l'est pas sur « la DERNIERE refuse », et il ne l'est pas sur
« ce qui suit le refus est quand meme tente ».
"""
from __future__ import annotations

import json

import pytest

from mixed_media_utility.io import project_layout
from mixed_media_utility.project_maintenance import (
    LigneDeGroupe,
    ProjectMaintenanceError,
    RapportSuppression,
    remove_project_group,
)

RACINE = project_layout.EXTRACT_FRAMES_DIRNAME


# ---------------------------------------------------------------------------
# Un coeur DOUBLE : il rend ce qu'on lui dit, et il ENREGISTRE l'ordre.
# ---------------------------------------------------------------------------


class _CoeurDouble:
    """Un double de `remove_project_element` qui refuse les cibles nommees.

    Il enregistre chaque appel dans l'ORDRE, ce qui est la seule facon de
    mesurer qu'une ligne posterieure a un refus est bien tentee : le cardinal
    des lignes rendues ne le dit pas, un arret precoce pouvant rendre autant de
    lignes qu'il en a traitees.
    """

    def __init__(self, refuse: set[str] | None = None,
                 partielles: set[str] | None = None):
        self.refuse = refuse or set()
        self.partielles = partielles or set()
        self.appels: list[dict] = []

    def __call__(self, project_dir, *, dry_run=True, **cible):
        self.appels.append({"dry_run": dry_run, **cible})
        marque = _marque(cible)
        if marque in self.refuse:
            raise ProjectMaintenanceError(
                f"Refus propre a {marque}: la raison REELLE, pas une phrase "
                "generique.")
        return RapportSuppression(
            cible=marque,
            # Chaque ligne rend un cardinal DIFFERENT : une concatenation
            # fautive (ou une deduplication) se voit alors, ce qu'un
            # remplissage uniforme cacherait.
            fichiers_a_supprimer=tuple(
                f"{marque}/f{n}.tiff" for n in range(_cardinal(marque))),
            dry_run=dry_run,
            supprime=not dry_run and marque not in self.partielles,
            fichiers_non_supprimes=(
                (f"{marque}/f0.tiff",)
                if not dry_run and marque in self.partielles else ()),
        )


def _marque(cible: dict) -> str:
    """Le nom court d'une cible, pour les assertions du banc."""
    return f"{cible.get('lot_id')}#{cible.get('version', 1)}"


def _cardinal(marque: str) -> int:
    """Un cardinal DISTINCT par rang : 1, 2, 3..."""
    return int(marque.rsplit("#", 1)[1])


def _cibles(*rangs: int, lot: str = "L") -> list[tuple[str, dict]]:
    """La fabrique de collection : N cibles DISTINGUABLES, jamais uniformes."""
    return [
        (f"master v{rang} du lot {lot}",
         {"lot_id": lot, "master": True, "profile": "prores_422",
          "version": rang})
        for rang in rangs
    ]


# ---------------------------------------------------------------------------
# Le geste nominal : N appels, dans l'ORDRE donne.
# ---------------------------------------------------------------------------


def test_les_N_cibles_sont_toutes_appelees_dans_l_ordre_donne(tmp_path):
    """L'ordre n'est PAS trie : celui de l'arbre porte celui du manifeste.

    `EPIC11-ARB-109`. Les rangs sont donnes a l'envers exprès : un tri pose ici
    les remettrait a l'endroit, et le banc le verrait.
    """
    coeur = _CoeurDouble()
    rapport = remove_project_group(
        tmp_path, _cibles(3, 1, 2), dry_run=False, retirer=coeur)
    assert [_marque(a) for a in coeur.appels] == ["L#3", "L#1", "L#2"]
    assert [l.libelle for l in rapport.lignes] == [
        "master v3 du lot L", "master v1 du lot L", "master v2 du lot L"]
    assert len(rapport.passees) == 3
    assert rapport.refusees == ()


def test_le_dry_run_se_PROPAGE_a_chaque_appel(tmp_path):
    """Un apercu de groupe est un apercu, pas N suppressions.

    Le drapeau varie dans les DEUX sens : sans le volet `False`, une valeur
    cablee en dur passerait le volet `True`.
    """
    for mode in (True, False):
        coeur = _CoeurDouble()
        rapport = remove_project_group(
            tmp_path, _cibles(1, 2), dry_run=mode, retirer=coeur)
        assert {a["dry_run"] for a in coeur.appels} == {mode}
        assert rapport.dry_run is mode


def test_les_chemins_sont_CONCATENES_dans_l_ordre_des_lignes(tmp_path):
    """Jamais fusionnes ni retries : on doit savoir quel fichier part avec
    quelle ligne."""
    coeur = _CoeurDouble()
    rapport = remove_project_group(
        tmp_path, _cibles(2, 1), dry_run=True, retirer=coeur)
    assert rapport.fichiers_a_supprimer == (
        "L#2/f0.tiff", "L#2/f1.tiff", "L#1/f0.tiff")


def test_les_mots_cles_sont_transmis_VERBATIM(tmp_path):
    """Cette fonction ne compose aucune cible et n'en juge aucune."""
    coeur = _CoeurDouble()
    remove_project_group(
        tmp_path,
        [("le scan S", {"lot_id": "L", "scan": "S", "version": 4})],
        dry_run=True, retirer=coeur)
    assert coeur.appels == [
        {"dry_run": True, "lot_id": "L", "scan": "S", "version": 4}]


# ---------------------------------------------------------------------------
# L'echec partiel -- le coeur de l'arbitrage, joue aux TROIS positions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fautive,rangs", [
    (1, (1, 2, 3)),   # en TETE
    (2, (1, 2, 3)),   # au MILIEU
    (3, (1, 2, 3)),   # en QUEUE
])
def test_un_refus_n_arrete_PAS_les_lignes_suivantes(tmp_path, fautive, rangs):
    """« Au mieux » : chaque ligne est tentee, quelle que soit la position du
    refus.

    Les trois positions comptent et ne se remplacent pas. Un balayage qui
    s'arrete au premier refus passe le cas de la QUEUE -- il n'y a rien apres
    --, et un balayage qui saute la derniere entree passe les deux autres. Ce
    sont deux modes de panne differents, et le point 4 de la regle des
    fabriques les a payes en mutants survivants.
    """
    coeur = _CoeurDouble(refuse={f"L#{fautive}"})
    rapport = remove_project_group(
        tmp_path, _cibles(*rangs), dry_run=False, retirer=coeur)
    assert [_marque(a) for a in coeur.appels] == [f"L#{r}" for r in rangs], (
        "toutes les lignes doivent etre TENTEES, y compris apres un refus")
    assert len(rapport.lignes) == 3
    assert [l.libelle for l in rapport.refusees] == [
        f"master v{fautive} du lot L"]
    assert {l.libelle for l in rapport.passees} == {
        f"master v{r} du lot L" for r in rangs if r != fautive}


def test_le_refus_porte_la_raison_REELLE_et_pas_une_phrase_generique(tmp_path):
    """`EPIC11-ARB-258` : un refus se prononce, et il dit POURQUOI."""
    coeur = _CoeurDouble(refuse={"L#2"})
    rapport = remove_project_group(
        tmp_path, _cibles(1, 2), dry_run=False, retirer=coeur)
    (refusee,) = rapport.refusees
    assert refusee.refus == (
        "Refus propre a L#2: la raison REELLE, pas une phrase generique.")
    assert refusee.rapport is None


def test_TOUTES_les_lignes_peuvent_refuser_sans_que_rien_ne_leve(tmp_path):
    """Le cas degenere : le groupe entier refuse. C'est un compte rendu, pas
    une exception -- l'operateur doit lire les N raisons d'un coup."""
    coeur = _CoeurDouble(refuse={"L#1", "L#2", "L#3"})
    rapport = remove_project_group(
        tmp_path, _cibles(1, 2, 3), dry_run=False, retirer=coeur)
    assert len(rapport.refusees) == 3
    assert rapport.passees == ()
    assert rapport.fichiers_a_supprimer == ()


def test_une_ligne_ACCEPTEE_dont_les_fichiers_resistent_n_est_pas_PASSEE(
        tmp_path):
    """Un refus et un echec partiel ne sont pas la meme chose.

    Le refus n'a rien detruit ; l'echec partiel a mis le manifeste a jour puis
    l'a restaure, et des fichiers occupent toujours le disque. Les confondre
    ferait annoncer « rien n'a bouge » sur un groupe a moitie parti.
    """
    coeur = _CoeurDouble(partielles={"L#2"})
    rapport = remove_project_group(
        tmp_path, _cibles(1, 2, 3), dry_run=False, retirer=coeur)
    assert rapport.refusees == (), "aucune ligne n'a ete REFUSEE"
    assert [l.libelle for l in rapport.partiellement_supprimees] == [
        "master v2 du lot L"]
    assert {l.libelle for l in rapport.passees} == {
        "master v1 du lot L", "master v3 du lot L"}


def test_en_APERCU_une_ligne_est_passee_meme_sans_suppression(tmp_path):
    """L'autre sens du meme drapeau : `supprime` vaut faux pour tout le monde
    en apercu, et lire ce champ seul rendrait l'apercu entierement « rate »."""
    coeur = _CoeurDouble()
    rapport = remove_project_group(
        tmp_path, _cibles(1, 2), dry_run=True, retirer=coeur)
    assert len(rapport.passees) == 2
    assert rapport.partiellement_supprimees == ()


def test_une_liste_de_cibles_VIDE_est_refusee_nommement(tmp_path):
    """Un succes a zero ligne cacherait a l'appelant qu'il s'est trompe de
    noeud, et l'ecran annoncerait « 0 fichier supprime » comme un travail
    accompli."""
    with pytest.raises(ProjectMaintenanceError) as erreur:
        remove_project_group(tmp_path, [], dry_run=True)
    assert "la liste de cibles est vide" in str(erreur.value)


# ---------------------------------------------------------------------------
# La ligne de compte rendu, mesuree pour elle-meme.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", [
    {},  # ni rapport ni refus
    {"rapport": RapportSuppression(cible="x", fichiers_a_supprimer=(),
                                   dry_run=True),
     "refus": "et un refus"},  # les deux
])
def test_une_ligne_INCOHERENTE_leve_au_lieu_de_mentir(kwargs):
    """Frontiere NEGATIVE : une ligne qui ne dit ni « parti » ni « refuse » ne
    dit rien de ce que le rapport existe pour dire."""
    with pytest.raises(ProjectMaintenanceError) as erreur:
        LigneDeGroupe(cible={}, libelle="une cible", **kwargs)
    assert "SOIT un rapport, SOIT un refus" in str(erreur.value)


def test_le_rapport_de_groupe_ne_porte_AUCUN_verdict_global():
    """`EPIC11-ARB-264` admet le succes PARTIEL : un booleen global mentirait
    dans les deux sens.

    Frontiere negative -- aucun test positif ne verrait apparaitre un
    `reussi` / `supprime` / `ok` de confort, et c'est exactement ce qu'un
    appelant presse ajouterait pour ecrire `if rapport.reussi:`.
    """
    from dataclasses import fields

    from mixed_media_utility.project_maintenance import RapportDeGroupe

    noms = {c.name for c in fields(RapportDeGroupe)}
    assert noms == {"lignes", "dry_run"}, sorted(noms)
    for interdit in ("reussi", "supprime", "ok", "succes", "echec"):
        assert not hasattr(RapportDeGroupe, interdit), (
            f"`{interdit}` est un verdict GLOBAL sur une operation qui admet "
            "le succes partiel : il mentirait sur un groupe a moitie parti")


# ---------------------------------------------------------------------------
# Le VRAI coeur, sur un vrai projet -- le double ne mesure pas l'appariement.
# ---------------------------------------------------------------------------


def _projet_a_trois_masters(tmp_path):
    """Un lot portant trois masters DISTINGUABLES du meme profil, et un SECOND
    lot qui n'est pas vise.

    Les tailles different d'un master a l'autre : un appariement inverse entre
    la cible et le fichier ne se voit qu'a ce prix.
    """
    lot = {
        "lot_id": "L", "rush_id": "R", "fps_target": 12.5,
        "encoded_masters": [
            {"path": "outputs/L_mmu_prores_422.mov", "profile_id": "prores_422"},
            {"path": "outputs/L_mmu_prores_422_v2.mov",
             "profile_id": "prores_422", "version_rank": 2},
            {"path": "outputs/L_mmu_prores_422_v3.mov",
             "profile_id": "prores_422", "version_rank": 3},
        ],
    }
    manifest = {
        "schema_version": "2.1", "project_id": "p",
        "rushes": [{"rush_id": "R"}, {"rush_id": "R2"}],
        "lots": [lot, {"lot_id": "AUTRE", "rush_id": "R2",
                       "encoded_masters": [
                           {"path": "outputs/AUTRE_mmu_prores_422.mov",
                            "profile_id": "prores_422"}]}],
    }
    projet = tmp_path / "projet"
    projet.mkdir()
    (projet / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    project_layout.outputs_dir(projet).mkdir()
    for rang, entree in enumerate(lot["encoded_masters"], start=1):
        (projet / entree["path"]).write_bytes(b"m" * rang)
    (project_layout.outputs_dir(projet)
     / "AUTRE_mmu_prores_422.mov").write_bytes(b"autre")
    return projet


def _masters_presents(projet) -> list[str]:
    """Les masters restants, lus du dossier que `project_layout` RESOUT.

    Le nom du dossier n'est pas ecrit ici -- il ne s'ecrit qu'a un seul endroit
    du depot (`EPIC11-ARB-222`), qui est aussi le seul a connaitre la
    cohabitation d'un nom neuf et de celui d'avant.

    **Les deux modes de panne d'un litteral ici sont mesures, et ils ne se
    valent pas** (2026-09-07). Un renommage SEC ferait lever `iterdir` en
    `FileNotFoundError` : bruyant, donc peu couteux. C'est la COHABITATION qui
    mord -- le regime exact que `EPIC11-ARB-225` a produit en renommant
    `patches/` en `planches/` sans casser les projets existants : l'ancien
    dossier survit, vide, la fabrique ecrit dans le neuf, et cette liste rend
    `[]` sans se plaindre. La garde comparerait alors `[]` a `[]` en restant
    verte, et c'est pour ce mode-la que le resolveur existe.
    """
    return sorted(c.name for c in project_layout.outputs_dir(projet).iterdir())


def test_le_GROUPE_des_masters_part_en_entier_sur_le_vrai_coeur(tmp_path):
    """Le double ci-dessus ne mesure pas l'appariement cible/fichier ; ici, si.

    Et il mesure la propriete qui fait tout l'interet de N appels : chaque
    appel RELIT le manifeste, donc les trois retraits successifs sont corrects
    plutot que trois vues d'un etat perime.
    """
    projet = _projet_a_trois_masters(tmp_path)
    cibles = [
        (f"master v{rang}",
         {"lot_id": "L", "master": True, "profile": "prores_422",
          **({"version": rang} if rang > 1 else {})})
        for rang in (3, 2, 1)
    ]
    rapport = remove_project_group(projet, cibles, dry_run=False)
    assert rapport.refusees == (), [l.refus for l in rapport.refusees]
    assert len(rapport.passees) == 3
    assert _masters_presents(projet) == ["AUTRE_mmu_prores_422.mov"], (
        "le master de l'AUTRE lot ne devait pas bouger")
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    # MESURE, et non supposition : le coeur RETIRE la cle plutot que de laisser
    # une liste vide -- l'omission stricte du depot (`EPIC11-ARB-88`). Le banc
    # dit ce que le coeur fait, il ne lui prescrit pas une autre forme.
    assert "encoded_masters" not in lot, lot.get("encoded_masters")


def test_une_cible_INEXISTANTE_du_groupe_refuse_et_les_autres_passent(tmp_path):
    """Le regime reel de l'echec partiel sur le vrai coeur : un master retire
    a la main entre l'apercu et la confirmation."""
    projet = _projet_a_trois_masters(tmp_path)
    cibles = [
        ("master v2", {"lot_id": "L", "master": True,
                       "profile": "prores_422", "version": 2}),
        ("master v9 (inexistant)", {"lot_id": "L", "master": True,
                                    "profile": "prores_422", "version": 9}),
        ("master v3", {"lot_id": "L", "master": True,
                       "profile": "prores_422", "version": 3}),
    ]
    rapport = remove_project_group(projet, cibles, dry_run=False)
    assert [l.libelle for l in rapport.refusees] == ["master v9 (inexistant)"]
    assert rapport.refusees[0].refus, "le refus doit porter une phrase"
    assert _masters_presents(projet) == [
        "AUTRE_mmu_prores_422.mov", "L_mmu_prores_422.mov"], (
        "la ligne posterieure au refus doit avoir ete tentee ET reussie")


def test_l_APERCU_du_groupe_n_ecrit_RIEN_sur_le_vrai_coeur(tmp_path):
    projet = _projet_a_trois_masters(tmp_path)
    cibles = [
        ("master v2", {"lot_id": "L", "master": True,
                       "profile": "prores_422", "version": 2}),
        ("master v3", {"lot_id": "L", "master": True,
                       "profile": "prores_422", "version": 3}),
    ]
    rapport = remove_project_group(projet, cibles, dry_run=True)
    assert rapport.fichiers_a_supprimer == (
        "outputs/L_mmu_prores_422_v2.mov", "outputs/L_mmu_prores_422_v3.mov")
    assert len(_masters_presents(projet)) == 4
    lot = json.loads((projet / "project.json").read_text())["lots"][0]
    assert len(lot["encoded_masters"]) == 3
