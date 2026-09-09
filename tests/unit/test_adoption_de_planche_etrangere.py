"""Story 11.4b, lot S2 (AC 3) -- l'adoption d'une planche etrangere, rapatriee.

Ce banc mesure le **portage** d'`EPIC7-ARB-101` depuis `origin/claude/epic-7`,
et il le mesure la ou la story 11.5 le consommera : sur le point d'entree de
coeur `scan_detect.run_scan_detect(..., adopter=True)`, jamais sur `cli.py`,
qui n'expose aucune adoption ni ici ni sur la branche source.

Deux regimes de mesure, deliberement melanges :

* les **fonctions pures** (`scan_sorting.trier_les_pages`,
  `reconstruction.reconstruct_project_manifest`) sont mesurees sans projet et
  sans pixel, sur les fabriques multi-elements du depot (`fabriques_vrac`) ;
* le chemin **entier** est mesure sur des planches **reellement peintes** puis
  relues, et l'assertion porte sur l'**artefact produit** -- le `project.json`
  du projet d'accueil et les documents de detection --, jamais sur le seul objet
  de retour. « Un test qui n'interroge que le modele ne voit aucune permutation
  de l'ecriture » (notes de la story 11.4b).

**Regle des fabriques** (CLAUDE.md), appliquee ici sur les deux collections a
risque de l'AC 3 :

1. la pile porte **deux projets etrangers distincts**, et aucun des deux n'est
   en premiere position -- un refus qui ne nommerait que le premier passerait
   tous les bancs ou le premier est le seul (AC 3.5) ;
2. le lot **non adoptable** de l'AC 3.6 est le **second** dans l'ordre ou la
   boucle d'adoption les prend (`sorted(par_lot.items())`) : un `continue` qui
   serait un `break` resterait vert si l'echec etait premier.
"""

from __future__ import annotations

import json
import logging
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(pathlib.Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).parent))

import fabriques_vrac as fab  # noqa: E402
import test_scan_calibration_application as app  # noqa: E402
import test_scan_manifest as scan_fixtures  # noqa: E402

from mixed_media_utility import (  # noqa: E402
    page_roles,
    scan_detect,
    scan_sorting,
)
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.io import reconstruction  # noqa: E402
from mixed_media_utility.io import scan_manifest  # noqa: E402

#: **Le code que rend une passe de ce banc DEPUIS la story 11.4c** (lot V2,
#: AC 9.3), et il ne vaut plus zero. Les planches de ces fixtures portent moins
#: d'emplacements que leur gabarit, donc le lot ecrit est declare
#: `LOT_INCOMPLET` par la persistance -- le journal le disait deja -- et
#: l'inventaire atteint desormais le code de sortie.
#:
#: **Ce n'est pas un refus** (`1`) : les frames sont ecrites, le manifest est
#: ecrit, et l'adoption mesuree par ce banc a bien lieu. Les assertions qui
#: portent sur l'artefact -- entree de lot, champ d'origine adoptee, frames
#: presentes sur le disque -- sont inchangees.
#:
#: Valeur ecrite en clair, jamais lue de `scan_write.CODE_SUCCES_PARTIEL`: lire
#: la constante que l'on mesure serait le test tautologique de la story 5.9.
LOT_INCOMPLET_MAIS_ECRIT = 4

#: Le projet d'accueil des piles peintes : celui que la fabrique de payloads du
#: depot declare, et donc celui que le manifest du projet portera.
PROJET_D_ACCUEIL = scan_fixtures.PROJECT

#: **Deux** projets etrangers distincts, avec leurs rushs propres. Les deux
#: `lot_id` qui en decoulent -- `rush-face_12p5` et `rush-voisin_8` -- sont
#: ordonnes `face` < `voisin`, ce qui fixe l'ordre de la boucle d'adoption et
#: permet de placer sciemment l'echec de l'AC 3.6 en **seconde** position.
VOISIN = ("projet-du-voisin", "rush-voisin", 8.0)
D_EN_FACE = ("projet-d-en-face", "rush-face", 12.5)

#: Un **troisieme** projet etranger, dont le `lot_id` (`rush-zenith_10`) vient
#: APRES celui de `VOISIN` dans l'ordre de la boucle d'adoption. Il n'est utile
#: qu'a l'AC 3.6, et il y est indispensable : avec deux lots seulement, l'echec
#: place en second est aussi le dernier, et un `break` y est indiscernable d'un
#: `continue`. Mesure : ce mutant-la SURVIVAIT a la premiere redaction du banc.
D_EN_DESSOUS = ("projet-d-en-dessous", "rush-zenith", 10.0)


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _planche(projet: str, rush: str, fps: float, page_index: int, *,
             page_count: int = 1, slot_count: int = 2,
             timecode_base_fps: str | None = None) -> dict:
    """Une planche d'images, par le vrai producteur de payloads du depot."""
    return scan_fixtures.make_payload(
        page_index=page_index,
        page_count=page_count,
        first_slot=page_index * slot_count,
        slot_count=slot_count,
        template_id=app.TEMPLATE,
        patch_preset_id=app.PRESET,
        project_id=projet,
        rush_id=rush,
        fps_target=fps,
        timecode_base_fps=timecode_base_fps,
        page_role=page_roles.PAGE_ROLE_IMAGES,
    )


def _projet_d_accueil(tmp_path: pathlib.Path) -> pathlib.Path:
    """Un projet **deja constitue**, avec son manifest et son identite.

    L'adoption lit l'identite d'accueil **au manifest**, jamais au nom du
    dossier : sans ce premier scan, il n'y aurait rien a adopter *dans*.
    """
    amorce = app.write_scan_folder(tmp_path / "amorce", [
        (_planche(PROJET_D_ACCUEIL, scan_fixtures.RUSH, 5.0, 0, page_count=2),
         app.PRESSES_DU_TIRAGE[0]),
        (_planche(PROJET_D_ACCUEIL, scan_fixtures.RUSH, 5.0, 1, page_count=2),
         app.PRESSES_DU_TIRAGE[1]),
    ])
    projet = tmp_path / "projet"
    assert app.run_scan(projet, amorce) == LOT_INCOMPLET_MAIS_ECRIT
    return projet


def _pile_a_deux_projets_etrangers(tmp_path: pathlib.Path,
                                   nom: str = "vrac") -> pathlib.Path:
    """Une planche du projet, **puis** une etrangere, **puis** une autre.

    Les deux projets etrangers sont distincts et le second est en **troisieme**
    position : un code qui ne regarderait que `payloads[0]`, ou qui
    s'arreterait au premier etranger trouve, resterait vert sur une pile ou le
    premier est le seul (AC 3.5, regle des fabriques).
    """
    return app.write_scan_folder(tmp_path / nom, [
        (_planche(PROJET_D_ACCUEIL, scan_fixtures.RUSH, 5.0, 0, page_count=2),
         app.PRESSES_DU_TIRAGE[0]),
        (_planche(*VOISIN, 0), app.PRESSES_DU_TIRAGE[1]),
        (_planche(*D_EN_FACE, 0), app.PRESSES_DU_TIRAGE[0]),
    ])


def _manifest(projet: pathlib.Path) -> dict:
    return json.loads((projet / "project.json").read_text(encoding="utf-8"))


def _lots_par_id(projet: pathlib.Path) -> dict[str, dict]:
    return {lot["lot_id"]: lot for lot in _manifest(projet)["lots"]}


def _rapport_de_tri(projet: pathlib.Path, slug: str) -> dict:
    chemin = projet / project_layout.SCANS_DIRNAME / slug / scan_detect.TRI_DOCUMENT_FILENAME
    return json.loads(chemin.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AC 3.5 -- le refus nomme TOUS les projets etrangers de la pile
# ---------------------------------------------------------------------------


def test_le_refus_NOMME_TOUS_les_projets_etrangers_de_la_pile(caplog):
    """`EPIC7-ARB-106`, verbatim : « **une seule question**, meme quand
    plusieurs projets sont en cause, et **elle les nomme tous** ».

    C'est ce que la 11.5 consommera pour poser sa question : la partition doit
    porter **chaque** projet a utiliser, pas le premier rencontre. Le vrac de
    reference du depot porte deux projets etrangers distincts, et **aucun des
    deux n'est en premiere position** (rangs de lecture 6 et 9).
    """
    partition = scan_sorting.trier_les_pages(
        fab.vrac_de_reference(), project_id_courant=fab.PROJET_COURANT)

    projets = sorted({entree.projet_a_utiliser
                      for entree in partition.hors_perimetre})
    assert projets == sorted(fab.PROJETS_ETRANGERS)
    # Temoin de la fabrique : les deux projets sont bien DISTINCTS, et le
    # second n'est pas en tete de pile. Sans ce temoin, une fabrique qui
    # deviendrait mono-projet rendrait ce test vert et creux.
    assert len(set(fab.PROJETS_ETRANGERS)) == 2
    rangs = [entree.read_rank for entree in partition.hors_perimetre]
    assert min(rangs) > 0, rangs

    # Le document, ensuite : c'est lui que la 11.5 relira, et il porte le meme
    # cardinal de projets que la partition.
    document = scan_sorting.rapport_to_json_dict(scan_sorting.RapportDeTri(
        ingest_slug="vrac", project_id=fab.PROJET_COURANT,
        partition=partition))
    assert sorted({entree["projet_a_utiliser"]
                   for entree in document["hors_perimetre"]}) == projets

    # Le journal, enfin : une ligne PAR feuille, chacune nommant son projet.
    with caplog.at_level(logging.WARNING):
        scan_detect.journaliser_le_tri(
            logging.getLogger("test.adoption.tri"), partition)
    journal = caplog.text
    for projet in fab.PROJETS_ETRANGERS:
        assert projet in journal, journal


def test_un_lot_ADOPTE_entre_dans_le_projet_et_les_AUTRES_restent_dehors():
    """Le tri lit la correspondance `lot_id -> projet d'origine`, et **elle
    seule** ouvre le perimetre.

    Le lot adopte est `lot_du_voisin_0002`, porte par la feuille de **rang 9**
    du vrac de reference : ni la premiere page, ni la premiere etrangere. Une
    adoption qui rangerait « la premiere feuille etrangere venue » ferait
    entrer l'autre, et ce test rougirait.
    """
    partition = scan_sorting.trier_les_pages(
        fab.vrac_de_reference(),
        project_id_courant=fab.PROJET_COURANT,
        lots_adoptes={"lot_du_voisin_0002": fab.PROJETS_ETRANGERS[0]},
    )

    assert [lot.lot_id for lot in partition.lots] == [
        "lot_alpha_0001", "lot_beta_0002", "lot_du_voisin_0002",
        "lot_gamma_0003"]
    # **Le projet d'une page adoptee est celui d'ACCUEIL**, pas celui que son
    # papier declare : deux lots du meme nom sous deux identites dans la meme
    # partition ne se reconcilieraient nulle part en aval.
    adopte = next(lot for lot in partition.lots
                  if lot.lot_id == "lot_du_voisin_0002")
    assert adopte.project_id == fab.PROJET_COURANT
    # L'autre projet etranger, lui, reste dehors et garde son nom.
    assert [entree.projet_a_utiliser for entree in partition.hors_perimetre] \
        == [fab.PROJETS_ETRANGERS[1]]


def test_le_couple_lot_et_origine_ouvre_le_perimetre_JAMAIS_le_lot_seul():
    """Un troisieme projet portant **le meme `lot_id`** reste hors perimetre.

    Le commentaire du portage le dit : « Comparer le seul `lot_id` suffirait a
    faire entrer une feuille d'un troisieme projet qui porterait par hasard le
    meme identifiant de lot : c'est le couple qui ouvre le perimetre. »
    """
    intruse = fab.page(
        read_rank=12, source="intruse.tiff",
        payload=fab.planche(lot_id="lot_du_voisin_0002", page_index=0,
                            project_id="projet_d_un_tiers"))
    partition = scan_sorting.trier_les_pages(
        [*fab.vrac_de_reference(), intruse],
        project_id_courant=fab.PROJET_COURANT,
        lots_adoptes={"lot_du_voisin_0002": fab.PROJETS_ETRANGERS[0]},
    )

    dehors = {entree.projet_a_utiliser for entree in partition.hors_perimetre}
    assert dehors == {fab.PROJETS_ETRANGERS[1], "projet_d_un_tiers"}
    # ... et la feuille legitimement adoptee, elle, est bien entree : sans ce
    # temoin, un tri qui refuserait TOUT rendrait ce test vert.
    adopte = next(lot for lot in partition.lots
                  if lot.lot_id == "lot_du_voisin_0002")
    assert [page.locator.source_path for page in adopte.pages] \
        == ["etrangere_a.tiff"]


def test_les_lots_adoptes_se_LISENT_au_manifest_ailleurs_qu_en_PREMIERE_position():
    """`lots_adoptes_du_manifest` : trois lots, les deux adoptes en 2e et 3e.

    Un lecteur qui rendrait le premier lot, ou qui s'arreterait au premier,
    resterait vert sur un manifest a un seul lot adopte place en tete.
    """
    manifest = {"lots": [
        {"lot_id": "lot_du_projet"},
        {"lot_id": "lot_adopte_a",
         reconstruction.CHAMP_ORIGINE_ADOPTEE: "projet_du_voisin"},
        {"lot_id": "lot_adopte_b",
         reconstruction.CHAMP_ORIGINE_ADOPTEE: "projet_archives_2019"},
    ]}
    assert scan_sorting.lots_adoptes_du_manifest(manifest) == {
        "lot_adopte_a": "projet_du_voisin",
        "lot_adopte_b": "projet_archives_2019",
    }
    # Champ **additif** : un manifest d'avant cet arbitrage se relit inchange,
    # et rend un dictionnaire vide plutot qu'une erreur.
    assert scan_sorting.lots_adoptes_du_manifest(
        {"lots": [{"lot_id": "lot_du_projet"}]}) == {}
    assert scan_sorting.lots_adoptes_du_manifest({}) == {}
    assert scan_sorting.lots_adoptes_du_manifest(None) == {}


# ---------------------------------------------------------------------------
# AC 3.2 -- l'adoption ne desarme AUCUNE garde
# ---------------------------------------------------------------------------


def _payloads_du_lot(projet: str, rush: str, fps: float, **surcharges) -> list[dict]:
    return [
        _planche(projet, rush, fps, 0, page_count=2, **surcharges),
        _planche(projet, rush, fps, 1, page_count=2, **surcharges),
    ]


def test_un_conflit_NON_DECIDE_reste_REFUSE_apres_le_portage():
    """`EPIC7-ARB-101`, verbatim : « Elle n'est **pas affaiblie** : on ne la
    desarme pas, on lui donne une entree deja resolue. »

    Deux moities, et les deux comptent :

    1. **sans adoption**, une planche etrangere est toujours refusee -- la
       garde d'identite de projet n'a pas ete elargie « au cas ou » ;
    2. **avec adoption**, un conflit que l'adoption ne decide PAS -- ici une
       cadence cible divergente sur le meme lot -- reste refuse. L'adoption ne
       tranche que l'identite de projet et le rush inconnu, rien d'autre.
    """
    accueil = {
        "project_id": PROJET_D_ACCUEIL,
        "rushes": [{"rush_id": scan_fixtures.RUSH}],
        "lots": [{"lot_id": scan_fixtures.LOT, "rush_id": scan_fixtures.RUSH}],
    }
    etrangers = _payloads_du_lot(*VOISIN)

    with pytest.raises(reconstruction.ReconstructionError) as refus:
        reconstruction.reconstruct_project_manifest(etrangers, accueil)
    assert VOISIN[0] in str(refus.value)
    assert PROJET_D_ACCUEIL in str(refus.value)

    # La meme pile, adoptee : elle passe. C'est le temoin qui prouve que le
    # refus ci-dessus tient a la garde et non a la fabrique.
    adoptes, origines = reconstruction.adopter_les_payloads(
        etrangers, project_id_cible=PROJET_D_ACCUEIL)
    manifest = reconstruction.reconstruct_project_manifest(
        adoptes, accueil, origines_adoptees=origines)
    assert manifest["project_id"] == PROJET_D_ACCUEIL

    # ... et le conflit que l'adoption NE decide PAS reste un refus. Le manifest
    # d'accueil declare desormais ce lot a 8 im/s ; la meme feuille rescannee en
    # declarant 12,5 est un conflit de cadence, adoption ou pas.
    divergents, origines_divergentes = reconstruction.adopter_les_payloads(
        _payloads_du_lot(VOISIN[0], VOISIN[1], VOISIN[2]),
        project_id_cible=PROJET_D_ACCUEIL)
    for payload in divergents:
        payload["fps_target"] = 12.5
    with pytest.raises(reconstruction.ReconstructionError) as conflit:
        reconstruction.reconstruct_project_manifest(
            divergents, manifest, origines_adoptees=origines_divergentes)
    assert "fps_target" in str(conflit.value)


def test_check_scan_conflicts_REFUSE_TOUJOURS_une_planche_NON_ADOPTEE(tmp_path):
    """AC 3.2, sur la garde que la story nomme : « C'est `check_scan_conflicts`
    qui refusait la planche etrangere, bien avant le tri ».

    Ce banc existe parce que le precedent ne suffisait pas, et c'est une mesure :
    le mutant « `_check_manifest_conflicts(..., adoption=True)` par defaut » --
    c'est-a-dire la garde du chemin d'**ecriture** desarmee -- **survivait**.
    `reconstruct_project_manifest` passe toujours le mot-cle explicitement ;
    `check_scan_conflicts`, lui, ne le passe pas, et c'est donc lui, et lui
    seul, qui exerce le defaut de ce parametre.

    Second temps : la MEME pile, une fois l'adoption inscrite au manifest,
    traverse la garde. C'est la transitivite que `origine_adoptee` revendique --
    « toutes les gardes du depot la consultent [...] la decision vit dans le
    document, pas dans un appel » -- et c'est ce qui rend un second scan
    ecrivable sans re-adopter.
    """
    projet = _projet_d_accueil(tmp_path)
    etrangers = _payloads_du_lot(*VOISIN)

    with pytest.raises(reconstruction.ReconstructionError) as refus:
        scan_manifest.check_scan_conflicts(projet, etrangers)
    assert VOISIN[0] in str(refus.value)
    assert PROJET_D_ACCUEIL in str(refus.value)

    # L'adoption inscrite au manifest, exactement telle que la reconstruction
    # la pose : le lot etranger devient un lot de ce projet.
    adoptes, origines = reconstruction.adopter_les_payloads(
        etrangers, project_id_cible=PROJET_D_ACCUEIL)
    manifest = _manifest(projet)
    manifest["lots"].append({
        "lot_id": next(iter(origines)),
        "rush_id": VOISIN[1],
        reconstruction.CHAMP_ORIGINE_ADOPTEE: VOISIN[0],
    })
    manifest["rushes"].append({"rush_id": VOISIN[1]})
    (projet / "project.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    scan_manifest.check_scan_conflicts(projet, adoptes)


def test_l_origine_est_gardee_sur_le_LOT_et_le_projet_d_accueil_n_est_PAS_renomme():
    """AC 3.4, moitie document : le champ est **additif** et porte par le lot.

    « La reference vient des payloads, donc du papier, donc du projet d'origine :
    la recopier ici renommerait le projet d'accueil a la premiere planche
    etrangere adoptee -- exactement l'inverse de l'adoption. »
    """
    accueil = {
        "project_id": PROJET_D_ACCUEIL,
        "rushes": [{"rush_id": scan_fixtures.RUSH}],
        "lots": [{"lot_id": scan_fixtures.LOT, "rush_id": scan_fixtures.RUSH}],
    }
    adoptes, origines = reconstruction.adopter_les_payloads(
        _payloads_du_lot(*VOISIN), project_id_cible=PROJET_D_ACCUEIL)
    manifest = reconstruction.reconstruct_project_manifest(
        adoptes, accueil, origines_adoptees=origines)

    assert manifest["project_id"] == PROJET_D_ACCUEIL
    lots = {lot["lot_id"]: lot for lot in manifest["lots"]}
    adopte = lots[next(iter(origines))]
    assert adopte[reconstruction.CHAMP_ORIGINE_ADOPTEE] == VOISIN[0]
    # Le lot **ne** du projet, lui, ne porte pas le champ : son absence est le
    # cas nominal, et c'est ce qui rend le champ relisible par une version
    # anterieure du contrat.
    assert reconstruction.CHAMP_ORIGINE_ADOPTEE not in lots[scan_fixtures.LOT]
    # Point unique de lecture, et il rend bien ce que la reconstruction a pose.
    assert reconstruction.origine_adoptee(
        manifest, next(iter(origines))) == VOISIN[0]
    assert reconstruction.origine_adoptee(manifest, scan_fixtures.LOT) is None


def test_un_SECOND_scan_du_lot_adopte_ne_RENOMME_PAS_le_projet_d_accueil():
    """AC 3.4, moitie **ecriture**, et c'est la moitie qui manquait.

    A la seconde passe, plus personne n'appelle `adopter_les_payloads` : les
    payloads declarent encore le projet d'**origine** (« l'encre ne se met pas a
    jour »), et c'est le manifest qui dit que ce lot est d'ici. La reference
    passee a la reconstruction porte donc le projet d'origine -- « la recopier
    ici renommerait le projet d'accueil a la premiere planche etrangere
    adoptee, exactement l'inverse de l'adoption ».

    Ce banc existe parce que le mutant « le projet d'accueil est renomme par
    l'adoption » **survivait** aux onze premiers tests : tous passaient par
    `adopter_les_payloads`, qui avait deja substitue l'identite, si bien que la
    branche de secours n'etait exercee par aucun d'eux.

    **Fabrique** : le lot adopte est en **seconde** position des `lots[]` du
    manifest -- un `_find_lot` qui rendrait le premier ne le trouverait pas.
    """
    payloads = _payloads_du_lot(*VOISIN)
    lot_adopte = payloads[0]["lot_id"]
    accueil = {
        "project_id": PROJET_D_ACCUEIL,
        "rushes": [{"rush_id": scan_fixtures.RUSH}, {"rush_id": VOISIN[1]}],
        "lots": [
            {"lot_id": scan_fixtures.LOT, "rush_id": scan_fixtures.RUSH},
            {"lot_id": lot_adopte, "rush_id": VOISIN[1],
             reconstruction.CHAMP_ORIGINE_ADOPTEE: VOISIN[0]},
        ],
    }
    # Temoin de la fabrique : les payloads declarent bien l'autre projet.
    assert {payload["project_id"] for payload in payloads} == {VOISIN[0]}

    manifest = reconstruction.reconstruct_project_manifest(payloads, accueil)

    assert manifest["project_id"] == PROJET_D_ACCUEIL
    lots = {lot["lot_id"]: lot for lot in manifest["lots"]}
    # L'origine, relue au manifest, est **reconduite** : elle n'est pas a
    # redemander a chaque passe, et elle ne s'efface pas non plus.
    assert lots[lot_adopte][reconstruction.CHAMP_ORIGINE_ADOPTEE] == VOISIN[0]
    assert reconstruction.CHAMP_ORIGINE_ADOPTEE not in lots[scan_fixtures.LOT]


# ---------------------------------------------------------------------------
# AC 3.3 -- l'adoption a lieu AVANT le tri, et l'ordre est MESURE
# ---------------------------------------------------------------------------


def test_l_adoption_a_lieu_AVANT_le_tri_et_l_ORDRE_est_mesure(
        tmp_path, monkeypatch):
    """AC 3.3, et c'est le piege nomme du lot : « une adoption posee apres
    `check_scan_conflicts` ne serait jamais atteinte ».

    Le tri est ce qui range une planche etrangere **hors perimetre** ; une pile
    entierement etrangere ne produit alors aucun lot, donc aucun document, donc
    aucune garde plus loin ou se rattraper. Ce test n'observe donc pas
    seulement que l'adoption marche : il **instrumente les deux appels** et
    asserte leur sequence. Un deplacement futur de l'appel apres le tri le fait
    rougir, meme si l'adoption continuait de fonctionner sur une autre passe.
    """
    projet = _projet_d_accueil(tmp_path)
    vrac = _pile_a_deux_projets_etrangers(tmp_path)

    sequence: list[str] = []
    vraie_adoption = scan_detect._adopter_les_planches_etrangeres
    vrai_tri = scan_sorting.trier_les_pages

    def adoption_espionnee(*args, **kwargs):
        sequence.append("adoption")
        return vraie_adoption(*args, **kwargs)

    def tri_espionne(*args, **kwargs):
        sequence.append("tri")
        return vrai_tri(*args, **kwargs)

    monkeypatch.setattr(scan_detect, "_adopter_les_planches_etrangeres",
                        adoption_espionnee)
    monkeypatch.setattr(scan_sorting, "trier_les_pages", tri_espionne)

    scan_detect.run_scan_detect(projet, vrac, dpi=app.DPI, adopter=True)

    # L'egalite stricte porte les deux faits a la fois : l'ordre, et le fait
    # que chacun des deux appels a bien eu lieu **une** fois. Une sequence
    # vide, ou `["tri"]` seul, rougit.
    assert sequence == ["adoption", "tri"]


def test_sans_adopter_le_coeur_n_ADOPTE_RIEN(tmp_path):
    """Frontiere negative de l'AC 3.3 : `adopter` vaut `False` par defaut.

    Le portage est **additif** : sans le drapeau, la pile etrangere ressort
    hors perimetre exactement comme avant, et le manifest ne gagne aucun champ.
    """
    projet = _projet_d_accueil(tmp_path)
    vrac = _pile_a_deux_projets_etrangers(tmp_path)

    issue = scan_detect.run_scan_detect(projet, vrac, dpi=app.DPI)

    assert sorted(entree.projet_a_utiliser
                  for entree in issue.partition.hors_perimetre) == sorted(
        [VOISIN[0], D_EN_FACE[0]])
    assert all(reconstruction.CHAMP_ORIGINE_ADOPTEE not in lot
               for lot in _manifest(projet)["lots"])


# ---------------------------------------------------------------------------
# AC 3.5 / 3.7 -- l'adoption prend les DEUX lots, et le document reste verbatim
# ---------------------------------------------------------------------------


def test_l_adoption_prend_LES_DEUX_lots_etrangers_pas_seulement_le_premier(
        tmp_path):
    """AC 3.5, cote ecriture, et l'assertion porte sur l'**artefact produit**.

    Une adoption qui ne prendrait que le premier lot etranger de la pile
    laisserait le second hors perimetre : l'operateur aurait repondu « oui » a
    une question qui les nommait tous les deux et n'en aurait obtenu qu'un --
    le faux succes du risque R12.
    """
    projet = _projet_d_accueil(tmp_path)
    vrac = _pile_a_deux_projets_etrangers(tmp_path)

    issue = scan_detect.run_scan_detect(projet, vrac, dpi=app.DPI, adopter=True)

    lots = _lots_par_id(projet)
    origines = {lot_id: lot[reconstruction.CHAMP_ORIGINE_ADOPTEE]
                for lot_id, lot in lots.items()
                if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot}
    # Deux lots, deux origines DISTINCTES : un remplissage uniforme cacherait
    # une origine recopiee du premier lot sur le second.
    assert sorted(origines.values()) == sorted([D_EN_FACE[0], VOISIN[0]])
    assert len(origines) == 2
    # Le lot ne dans le projet ne porte pas le champ : le manifest reste
    # relisible par une version anterieure du contrat.
    assert reconstruction.CHAMP_ORIGINE_ADOPTEE not in lots[scan_fixtures.LOT]
    # Consequence du cote du tri : plus rien n'est hors perimetre, et les trois
    # lots sont ranges sous l'identite d'ACCUEIL.
    assert issue.partition.hors_perimetre == ()
    assert {lot.project_id for lot in issue.partition.lots} == {PROJET_D_ACCUEIL}
    assert len(issue.documents) == 3


def test_le_document_de_detection_garde_le_payload_VERBATIM(tmp_path):
    """AC 3.7 : « le document de detection garde le payload **verbatim**, y
    compris son projet d'origine : c'est le **manifest** qui porte la
    decision. »

    C'est ce qui rend l'adoption relisible : le papier dit ce que le papier
    dit, et la decision vit a un seul endroit.
    """
    projet = _projet_d_accueil(tmp_path)
    vrac = _pile_a_deux_projets_etrangers(tmp_path)

    issue = scan_detect.run_scan_detect(projet, vrac, dpi=app.DPI, adopter=True)

    projets_declares = set()
    for chemin in issue.documents:
        document = json.loads(chemin.read_text(encoding="utf-8"))
        for page in document["pages"]:
            identite = page.get("decoded_identity") or {}
            if identite.get("project_id"):
                projets_declares.add(identite["project_id"])
    # Les trois projets, dont les deux adoptes : aucune reecriture n'a eu lieu
    # dans les documents.
    assert projets_declares == {PROJET_D_ACCUEIL, VOISIN[0], D_EN_FACE[0]}
    # ... alors meme que le manifest, lui, a bien tranche.
    assert len([lot for lot in _manifest(projet)["lots"]
                if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot]) == 2


# ---------------------------------------------------------------------------
# AC 3.4 -- un SECOND scan du meme lot n'exige AUCUNE nouvelle adoption
# ---------------------------------------------------------------------------


def test_un_SECOND_scan_du_meme_lot_n_exige_AUCUNE_nouvelle_adoption(tmp_path):
    """`EPIC7-ARB-101`, verbatim : « sans cette trace, chaque nouvelle feuille
    du meme lot rescannee plus tard serait reclassee « hors perimetre » et il
    faudrait re-adopter a chaque passe ».

    La consequence **fonctionnelle** est mesuree, pas la seule presence du
    champ : la seconde passe part **sans** `adopter`, et sa feuille -- une
    autre feuille du meme lot -- atterrit dans le lot du projet.
    """
    projet = _projet_d_accueil(tmp_path)
    premiere = app.write_scan_folder(tmp_path / "passe-1", [
        (_planche(PROJET_D_ACCUEIL, scan_fixtures.RUSH, 5.0, 0, page_count=2),
         app.PRESSES_DU_TIRAGE[0]),
        (_planche(*VOISIN, 0, page_count=2), app.PRESSES_DU_TIRAGE[1]),
    ])
    scan_detect.run_scan_detect(projet, premiere, dpi=app.DPI, adopter=True)
    lot_adopte = next(
        lot_id for lot_id, lot in _lots_par_id(projet).items()
        if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot)

    # La SECONDE passe : l'autre feuille du meme lot, et **aucune adoption**.
    seconde = app.write_scan_folder(tmp_path / "passe-2", [
        (_planche(*VOISIN, 1, page_count=2), app.PRESSES_DU_TIRAGE[0]),
    ])
    issue = scan_detect.run_scan_detect(projet, seconde, dpi=app.DPI)

    assert issue.partition.hors_perimetre == ()
    assert [lot.lot_id for lot in issue.partition.lots] == [lot_adopte]
    assert [lot.project_id for lot in issue.partition.lots] == [
        PROJET_D_ACCUEIL]
    assert len(issue.documents) == 1
    # L'origine, elle, n'a pas bouge : la trace est ecrite une fois et relue.
    assert _lots_par_id(projet)[lot_adopte][
        reconstruction.CHAMP_ORIGINE_ADOPTEE] == VOISIN[0]


def test_un_SECOND_scan_du_lot_adopte_S_ECRIT_et_l_origine_SURVIT(tmp_path):
    """AC 3.4, jusqu'aux **frames**, et c'est le corollaire mesure de la story :
    « au moins un test confronte l'ARTEFACT PRODUIT ».

    Le test precedent s'arrete a la partition ; celui-ci va jusqu'a l'ecriture,
    par `mmu scan --lot-slug`, qui promet une pile mono-lot et va donc droit a
    `check_scan_conflicts` puis a l'ecriture. C'est le seul chemin de ce depot
    qui fasse **ecrire** des frames sur un lot adopte, et il traverse trois
    gardes de plus que la detection (`_check_lot_attachment`,
    `_check_printed_identifiers`, `_check_page_count`) -- aucune n'a ete
    desarmee par le portage.

    Deux faits sont mesures a l'arrivee : le lot garde son origine **apres**
    l'ecriture du manifest par `build_scan_manifest` (qui ne declare pas ce
    champ dans ses tables et ne doit donc pas l'effacer), et le projet
    d'accueil n'est pas renomme.
    """
    projet = _projet_d_accueil(tmp_path)
    premiere = app.write_scan_folder(tmp_path / "passe-1", [
        (_planche(*VOISIN, 0, page_count=2), app.PRESSES_DU_TIRAGE[0]),
    ])
    scan_detect.run_scan_detect(projet, premiere, dpi=app.DPI, adopter=True)
    lot_adopte = next(
        lot_id for lot_id, lot in _lots_par_id(projet).items()
        if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot)

    seconde = app.write_scan_folder(tmp_path / "passe-2", [
        (_planche(*VOISIN, 1, page_count=2), app.PRESSES_DU_TIRAGE[1]),
    ])
    assert app.run_scan(projet, seconde, "--lot-slug", "passe-2") == LOT_INCOMPLET_MAIS_ECRIT

    lot = _lots_par_id(projet)[lot_adopte]
    assert lot[reconstruction.CHAMP_ORIGINE_ADOPTEE] == VOISIN[0]
    assert _manifest(projet)["project_id"] == PROJET_D_ACCUEIL
    # L'artefact, enfin : des frames de ce lot existent sur le disque. Un
    # manifest juste et un dossier vide seraient le faux succes du risque R12.
    frames = sorted((projet / project_layout.SCAN_FRAMES_DIRNAME).rglob("*.tiff"))
    assert frames, sorted((projet / project_layout.SCAN_FRAMES_DIRNAME).rglob("*"))
    assert lot["output_frames_dir"]


# ---------------------------------------------------------------------------
# AC 3.6 -- un echec d'adoption n'arrete pas la passe
# ---------------------------------------------------------------------------


def test_un_lot_NON_ADOPTABLE_ne_perd_PAS_les_lots_adoptables(tmp_path, caplog):
    """`EPIC7-ARB-101` (docstring de `_adopter_les_planches_etrangeres`),
    verbatim : « **un echec n'arrete pas la passe.** Un lot qu'on ne peut pas
    adopter est journalise et laisse tel quel ».

    **Fabrique** : **trois** lots etrangers, et le non adoptable est **au
    milieu** de l'ordre ou la boucle les prend (`sorted(par_lot.items())` :
    `rush-face_12p5` < `rush-voisin_8` < `rush-zenith_10`). Deux lots ne
    suffisent pas, et c'est une mesure : avec l'echec en second et dernier, le
    mutant « `continue` devenu `break` » **survivait**. Il faut un lot
    adoptable **de chaque cote** de l'echec pour que les deux fautes -- ne
    prendre que le premier, et s'arreter au premier echec -- rougissent.

    Le lot fautif porte deux feuilles qui declarent **deux cadences source
    differentes** : c'est un conflit d'identite de lot, refuse par
    `_check_lot_consistency` -- le terrain exact du risque R12.
    """
    projet = _projet_d_accueil(tmp_path)
    vrac = app.write_scan_folder(tmp_path / "vrac", [
        (_planche(PROJET_D_ACCUEIL, scan_fixtures.RUSH, 5.0, 0, page_count=2),
         app.PRESSES_DU_TIRAGE[1]),
        (_planche(*D_EN_FACE, 0), app.PRESSES_DU_TIRAGE[0]),
        (_planche(*VOISIN, 0, page_count=2, timecode_base_fps="30/1"),
         app.PRESSES_DU_TIRAGE[1]),
        (_planche(*D_EN_DESSOUS, 0), app.PRESSES_DU_TIRAGE[0]),
        (_planche(*VOISIN, 1, page_count=2, timecode_base_fps="25/1"),
         app.PRESSES_DU_TIRAGE[0]),
    ])

    with caplog.at_level(logging.WARNING):
        issue = scan_detect.run_scan_detect(
            projet, vrac, dpi=app.DPI, adopter=True,
            logger=logging.getLogger("test.adoption.echec"))

    origines = {lot_id: lot[reconstruction.CHAMP_ORIGINE_ADOPTEE]
                for lot_id, lot in _lots_par_id(projet).items()
                if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot}
    # Les deux lots ADOPTABLES le sont, celui d'avant l'echec **et** celui
    # d'apres : c'est cette seconde moitie qui tue le `break`.
    assert origines == {"rush-face_12p5": D_EN_FACE[0],
                        "rush-zenith_10": D_EN_DESSOUS[0]}
    # Le lot fautif est reste dehors, et il est NOMME au journal avec son motif.
    assert "rush-voisin_8" in caplog.text
    assert "timecode_base_fps" in caplog.text
    assert sorted({entree.projet_a_utiliser
                   for entree in issue.partition.hors_perimetre}) == [
        VOISIN[0]]
    # La passe, elle, est allee au bout : le lot du projet et les deux lots
    # adoptes ont chacun leur document.
    assert len(issue.documents) == 3


# ---------------------------------------------------------------------------
# AC 3.8 -- le manifest d'accueil est ENRICHI, jamais reecrit
# ---------------------------------------------------------------------------


def test_l_adoption_PRESERVE_artifacts_color_video_et_created(tmp_path):
    """`EPIC7-ARB-101` (docstring), verbatim : « le manifest du projet est
    **ENRICHI, jamais reecrit** ».

    Ce sont « les mesures que le scan ne pourra jamais refaire, le rush n'etant
    pas sur cette machine ». Le banc pose donc des valeurs **distinguables**
    dans les quatre cles **avant** l'adoption et les relit apres : constater
    leur seule presence laisserait passer une section reecrite a vide par
    `reconstruct_project_manifest`, qui repose `artifacts` et `video` vides.

    Le manifest d'accueil vient du **vrai** producteur d'extraction : ecrire a
    la main celui d'un projet riche encoderait silencieusement une convention
    qui n'est pas la sienne.
    """
    accueil = scan_fixtures.rich_extraction_manifest()
    accueil["created"] = "2019-11-05T08:15:00Z"
    accueil["artifacts"] = {"frames_dir": "frames-du-montage",
                            "outputs_dir": "sorties-du-montage"}
    accueil["video"] = {"codec_target": "prores_422_hq"}
    accueil["color"] = {"target_colorspace": "rec709",
                        "color_calibration_status": "applied"}
    projet = tmp_path / "projet-riche"
    scan_fixtures.write_manifest(projet, accueil)

    vrac = app.write_scan_folder(tmp_path / "vrac", [
        (_planche(*VOISIN, 0), app.PRESSES_DU_TIRAGE[0]),
    ])
    scan_detect.run_scan_detect(projet, vrac, dpi=app.DPI, adopter=True)

    apres = _manifest(projet)
    assert apres["created"] == "2019-11-05T08:15:00Z"
    assert apres["artifacts"] == {"frames_dir": "frames-du-montage",
                                  "outputs_dir": "sorties-du-montage"}
    assert apres["video"] == {"codec_target": "prores_422_hq"}
    # `color.color_calibration_status` survit ; `target_colorspace` est la
    # **seule** cle de couleur que le scan connaisse, et l'asymetrie assumee de
    # `preserver_les_sections_de_tete` veut que ce qu'il apporte prime sur elle.
    assert apres["color"]["color_calibration_status"] == "applied"
    assert apres["color"]["target_colorspace"]
    # Temoin : l'adoption a bien eu lieu -- sinon les quatre cles seraient
    # intactes pour la mauvaise raison.
    assert [lot[reconstruction.CHAMP_ORIGINE_ADOPTEE]
            for lot in apres["lots"]
            if reconstruction.CHAMP_ORIGINE_ADOPTEE in lot] == [VOISIN[0]]
    # Le lot du montage, lui, n'a rien perdu de ce que le scan ne sait pas
    # refaire.
    lot_du_montage = next(lot for lot in apres["lots"]
                          if lot["lot_id"] == scan_fixtures.LOT)
    assert lot_du_montage["frame_timecodes_digest"]
    assert lot_du_montage["expected_frame_count"]


def test_la_preservation_des_sections_de_tete_est_PUBLIEE_et_unique():
    """AC 3.1 : la cinquieme surface du portage.

    `_adopter_les_planches_etrangeres` ecrit le manifest sans passer par
    `persist_scan` : il lui faut cette fonction, et **la meme**. L'ancien nom
    prive reste un alias -- « deux redactions de cette preservation
    divergeraient, et la divergence se paierait en mesures irrecuperables ».
    """
    assert scan_manifest.preserver_les_sections_de_tete is \
        scan_manifest._preserve_head_sections
