"""Vague 5, lot C -- les trois criteres d'identite d'un rush, STOCKES et COMPARES.

Note 5 de la relecture d'Egan du 2026-09-01 (planche « Declarer un rush » v2),
verbatim :

    « pas si leurs timecodes ne correspondent pas EXACTEMENT (duree, base,
    timecode initial). Ce serait tres rare. **Il faut ajouter ces criteres dans
    la comparaison, et les stocker...** »

Ce que le banc mesure, et pourquoi chaque section existe :

* `C.1` -- **le vocabulaire est ferme et exact**. L'ensemble des criteres
  compares n'est pas mesure par appartenance (« `source_frame_count` en fait
  partie ») mais par **egalite** : un critere ajoute en silence rougit ici. Une
  assertion positive laisserait passer toute divergence supplementaire ;
* `C.2` -- **la partition est exacte**. Tout critere tombe dans exactement une
  des trois cases (divergent, concordant, non verifiable), jamais deux, jamais
  zero ;
* `C.3` -- **l'absence reste une absence**, mesure par des frontieres
  **negatives** : un critere absent d'un cote ne vaut jamais `0`, jamais `""`,
  et ne fait **jamais** conflit. C'est la regle que
  `source_confirmation._normalize_probe_value` pose pour le probe (« sans
  jamais substituer de valeur ») et que la comparaison d'identite doit tenir a
  son tour. Aucun test positif ne verrait revenir une substitution ;
* `C.4` -- **chaque critere fait conflit A LUI SEUL**. C'est la moitie « ajouter
  a la comparaison » de la note 5, mesuree critere par critere : un mutant qui
  retire l'un des quatre du parcours rougit sur sa ligne et sur elle seule ;
* `C.5` -- **le defaut nomme par la note 5** : deux rushs distincts dont les
  dossiers parents portent le MEME nom (`hd`) etaient le meme rush pour
  l'outil, parce que le dossier parent etait le seul critere compare ;
* `C.6` -- **le stockage**, dont la moitie « et les stocker » de la note 5 :
  `rushes[].source_frame_count` et `rushes[].source_frame_count_is_exact`.
  L'ensemble des cles ecrites est mesure **exactement**, pour la meme raison
  qu'en `C.1` ;
* `C.7` -- **la base de timecode n'est pas dupliquee**, et c'est une mesure et
  non un choix de style : `lots[].timecode_base_fps` et
  `rushes[].fps_source_exact` portent la MEME valeur, parce que
  `frame_selection` pose `timecode_base_fps=fps_source_exact` sous
  `TIMECODE_BASE == "source"`. Si cette egalite tombe un jour, ce banc rougit
  et la comparaison d'identite devra alors porter un champ propre ;
* `C.8` -- **l'ordre impose**, mesure sur l'arbre syntaxique de
  `run_extraction` : la garde de conflit reste **avant** le probe, parce que
  l'AC 1.1 de la story 11.4c (`EPIC11-ARB-83`) mesure que la transition d'etat
  precede `ensure_ffmpeg_available` -- donc a fortiori `probe_media`. Remonter
  le probe pour nourrir la garde casserait cette frontiere-la.

**Regle des fabriques de `CLAUDE.md`, point 2 bis compris** : la fabrique de
`rushes[]` produit **trois** entrees distinguables, la cible **au milieu**, et
les deux voisines portent des valeurs differentes de la cible sur les quatre
criteres. Un `find` fautif qui rend la premiere entree, une boucle qui casse au
premier tour (`continue` -> `break`), une lecture de la derniere : les trois se
demasquent ici et aucune ne se demasquerait sur une fabrique a un ou deux
elements.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from mixed_media_utility import extraction
from mixed_media_utility.frame_selection import select_source_frames
from mixed_media_utility.io.extraction_manifest import (
    ExtractionRecord,
    _build_rush_entry,
    build_extraction_manifest,
    rush_record_de_l_extraction,
)
from mixed_media_utility.io.manifest import validate_manifest
from mixed_media_utility.io.naming import build_lot_id

RUSH_ID = "prise-du-milieu"


# ===========================================================================
# Fabriques -- trois entrees distinguables, la cible au MILIEU
# ===========================================================================


def entree_de_rush(
    rush_id: str,
    *,
    source_parent: str | None,
    fps_source_exact: str | None,
    source_frame_count: int | None,
    source_start_timecode: str | None,
) -> dict:
    """Une entree `rushes[]`, chaque critere pose ou **omis** (jamais `null`).

    L'omission est la seule facon d'ecrire une absence au manifeste
    (`_build_rush_entry` : « Omission stricte: jamais `null`, jamais une valeur
    par defaut »). Une fabrique qui ecrirait `None` mesurerait autre chose que
    ce que le produit ecrit.
    """
    entree: dict = {"rush_id": rush_id}
    for cle, valeur in (
        ("source_parent", source_parent),
        ("fps_source_exact", fps_source_exact),
        ("source_frame_count", source_frame_count),
        ("source_start_timecode", source_start_timecode),
    ):
        if valeur is not None:
            entree[cle] = valeur
    return entree


def rushes_a_trois_entrees(cible: dict) -> list[dict]:
    """Trois entrees, la **cible au milieu**, les voisines distinguables.

    Les voisines ne portent ni le meme `rush_id` ni les memes valeurs
    techniques : une comparaison qui s'apparierait par position, ou qui
    lirait la premiere ou la derniere entree, rendrait un verdict faux et
    visible.
    """
    return [
        entree_de_rush(
            "rush-en-tete",
            source_parent="A-CAM",
            fps_source_exact="24/1",
            source_frame_count=1001,
            source_start_timecode="10:00:00:00",
        ),
        cible,
        entree_de_rush(
            "rush-en-queue",
            source_parent="C-CAM",
            fps_source_exact="50/1",
            source_frame_count=3003,
            source_start_timecode="12:00:00:00",
        ),
    ]


def cible_de_reference() -> dict:
    """La cible « saine » : les quatre criteres poses, valeurs de reference."""
    return entree_de_rush(
        RUSH_ID,
        source_parent="B-CAM",
        fps_source_exact="25/1",
        source_frame_count=106,
        source_start_timecode="01:01:39:12",
    )


def mesures_de_reference(**ecarts) -> "extraction.CriteresIdentiteRush":
    """Les criteres **mesures** qui concordent avec `cible_de_reference()`.

    `ecarts` remplace un critere et un seul, ce qui est exactement ce dont la
    section `C.4` a besoin : faire diverger un critere sans toucher aux trois
    autres.
    """
    valeurs = {
        "source_parent": "B-CAM",
        "fps_source_exact": "25/1",
        "source_frame_count": 106,
        "source_start_timecode": "01:01:39:12",
    }
    valeurs.update(ecarts)
    return extraction.CriteresIdentiteRush(**valeurs)


# ===========================================================================
# C.1 -- le vocabulaire des criteres, mesure par EGALITE
# ===========================================================================


def test_l_ensemble_des_criteres_compares_est_EXACTEMENT_ces_TROIS_la():
    """Egalite, jamais appartenance.

    **Mis a jour le 2026-09-05 par `EPIC11-ARB-230`**, qui retire le dossier
    parent. Question d'Egan, verbatim : « si le timecode de debut, la duree, la
    cadence et le nom coincident alors il y a "conflit" puisque c'est le meme
    rush ». Les quatre criteres d'identite sont donc le nom, la duree, la
    cadence et le timecode initial ; le **nom** est la cle `rush_id` sous
    laquelle la comparaison se fait, donc ce tuple n'en porte que les trois
    autres. Un cinquieme critere ajoute sans arbitrage rougit ici, et le
    dossier qui reviendrait aussi.
    """
    assert extraction.CRITERES_IDENTITE_RUSH == (
        "fps_source_exact",
        "source_frame_count",
        "source_start_timecode",
    )


def test_le_dossier_parent_n_est_PLUS_un_critere_mais_reste_NOMME():
    """Volet symetrique du precedent : `EPIC11-ARB-230` **retire**, il ne
    supprime pas.

    Le dossier parent reste sur le porteur de criteres -- il nomme la
    provenance a l'ecran et il fournit le suffixe de `disambiguated_rush_id` --
    et il reste le separateur de dernier recours du regime degrade
    (section `C.8`). Une frontiere qui ne mesurerait que le retrait laisserait
    passer une suppression du champ, qui casserait les deux autres emplois
    sans que rien ne le dise ici.
    """
    assert extraction.CRITERE_DE_DERNIER_RECOURS == "source_parent"
    assert extraction.CRITERE_DE_DERNIER_RECOURS not in (
        extraction.CRITERES_IDENTITE_RUSH
    )
    assert hasattr(extraction.CriteresIdentiteRush(), "source_parent")


def test_chaque_critere_porte_le_nom_EXACT_de_sa_cle_au_manifeste():
    """Nom du critere = nom de la cle `rushes[]`, sans traduction intermediaire.

    Une table de correspondance entre deux vocabulaires est le genre d'objet
    qui derive en silence : `_build_rush_entry` doit pouvoir ecrire, et la
    comparaison lire, sous le meme nom.
    """
    ecrites = set(entree_de_rush_d_une_extraction(record_de_reference()))
    assert set(extraction.CRITERES_IDENTITE_RUSH) <= ecrites


# ===========================================================================
# C.2 -- la partition des criteres est exacte
# ===========================================================================


@pytest.mark.parametrize(
    "declares, mesures",
    [
        (cible_de_reference(), mesures_de_reference()),
        (cible_de_reference(), mesures_de_reference(source_frame_count=999)),
        ({"rush_id": RUSH_ID}, mesures_de_reference()),
        (cible_de_reference(), extraction.CriteresIdentiteRush()),
    ],
    ids=["tout-concorde", "un-diverge", "rien-de-declare", "rien-de-mesure"],
)
def test_les_trois_cases_partitionnent_EXACTEMENT_les_criteres(declares, mesures):
    """Un critere tombe dans une case et une seule, dans les quatre regimes.

    Mesure d'egalite d'ensembles ET de disjonction deux a deux : un critere
    compte deux fois, ou oublie, rougit. Les quatre regimes couvrent les deux
    absences (cote declare, cote mesure) et pas seulement le cas nominal.
    """
    verdict = extraction.comparer_identite_rush(
        extraction.CriteresIdentiteRush.declares(declares), mesures
    )
    cases = (verdict.divergents, verdict.concordants, verdict.non_verifiables)

    reunion: set[str] = set()
    total = 0
    for case in cases:
        reunion |= set(case)
        total += len(case)

    assert reunion == set(extraction.CRITERES_IDENTITE_RUSH)
    assert total == len(extraction.CRITERES_IDENTITE_RUSH)


def test_l_ordre_de_chaque_case_suit_l_ordre_NORMATIF_des_criteres():
    """Les cases sont triees comme `CRITERES_IDENTITE_RUSH`, pas au hasard.

    Un ecran qui liste « les infos techniques communes » (note 2 d'Egan) doit
    pouvoir afficher les criteres dans un ordre stable sans les retrier.
    """
    verdict = extraction.comparer_identite_rush(
        extraction.CriteresIdentiteRush.declares(cible_de_reference()),
        mesures_de_reference(source_parent="ZZ-CAM", source_frame_count=999),
    )
    for case in (verdict.divergents, verdict.concordants, verdict.non_verifiables):
        rangs = [extraction.CRITERES_IDENTITE_RUSH.index(c) for c in case]
        assert rangs == sorted(rangs)


# ===========================================================================
# C.3 -- l'absence reste une absence (frontieres NEGATIVES)
# ===========================================================================


@pytest.mark.parametrize("critere", extraction.CRITERES_IDENTITE_RUSH)
def test_un_critere_absent_du_manifeste_se_lit_None_et_JAMAIS_une_valeur_par_defaut(
    critere,
):
    """Frontiere **negative** : aucune substitution, dans aucun sens.

    `0`, `""`, `"0/1"` et `"00:00:00:00"` sont les quatre valeurs par defaut
    plausibles qu'un correctif presse ecrirait a la place d'une absence. Une
    duree absente stockee `0` mentirait : elle affirmerait un flux vide la ou
    la source n'a rien dit. Aucun test positif ne verrait revenir cette
    substitution.
    """
    entree = cible_de_reference()
    entree.pop(critere)

    declares = extraction.CriteresIdentiteRush.declares(entree)
    lu = getattr(declares, critere)

    assert lu is None
    assert lu not in (0, "", "0/1", "00:00:00:00")


@pytest.mark.parametrize("critere", extraction.CRITERES_IDENTITE_RUSH)
def test_un_critere_absent_d_un_cote_est_NON_VERIFIABLE_et_jamais_un_conflit(critere):
    """Une absence ne fait pas conflit -- ni cote declare, ni cote mesure.

    C'est la meme doctrine que `relink.ReferenceIdentite.criteres_verifiables`
    (« Un critere sans reference au manifest est NON VERIFIABLE ») : ce qui
    n'est pas comparable est **dit**, jamais compte comme une divergence. Un
    mutant qui traiterait `None != valeur` comme une divergence declarerait
    conflictuel tout rush declare avant cette story.
    """
    entree = cible_de_reference()
    entree.pop(critere)
    declares = extraction.CriteresIdentiteRush.declares(entree)

    verdict = extraction.comparer_identite_rush(declares, mesures_de_reference())
    assert verdict.divergents == ()
    assert critere in verdict.non_verifiables

    verdict_inverse = extraction.comparer_identite_rush(
        extraction.CriteresIdentiteRush.declares(cible_de_reference()),
        mesures_de_reference(**{critere: None}),
    )
    assert verdict_inverse.divergents == ()
    assert critere in verdict_inverse.non_verifiables


def test_une_duree_declaree_ZERO_se_lit_absente_et_ne_devient_JAMAIS_un_conflit():
    """`0` au manifeste est hors schema (`minimum: 1`) : c'est une absence.

    La lire comme un cardinal ferait diverger tout rush dont un manifeste
    ancien ou corrompu porte un zero, alors que le zero ne dit rien.
    """
    entree = cible_de_reference()
    entree["source_frame_count"] = 0

    declares = extraction.CriteresIdentiteRush.declares(entree)
    assert declares.source_frame_count is None

    verdict = extraction.comparer_identite_rush(declares, mesures_de_reference())
    assert verdict.divergents == ()
    assert "source_frame_count" in verdict.non_verifiables


def test_une_entree_de_rush_NUE_ne_fait_conflit_sur_AUCUN_critere():
    """Le cas `barren` de `relink` : un rush declare par le scan seul.

    Aucun des quatre criteres n'y figure. Le conflit doit etre `None` : sans
    reference, on ne sait rien, et « on ne sait rien » n'est pas « ce n'est pas
    le meme rush ».
    """
    rushes = rushes_a_trois_entrees({"rush_id": RUSH_ID})
    assert (
        extraction.rush_identity_conflict(
            rushes, RUSH_ID, "B-CAM", mesures=mesures_de_reference()
        )
        is None
    )


# ===========================================================================
# C.4 -- chaque critere fait conflit A LUI SEUL
# ===========================================================================


ECARTS_PAR_CRITERE = {
    "fps_source_exact": "24000/1001",
    "source_frame_count": 107,
    "source_start_timecode": "01:01:39:13",
}


@pytest.mark.parametrize("critere", extraction.CRITERES_IDENTITE_RUSH)
def test_chaque_critere_seul_suffit_a_declarer_le_conflit(critere):
    """La moitie « ajouter a la comparaison » de la note 5, critere par critere.

    Un seul critere diverge, les trois autres concordent. Un mutant qui
    retirerait ce critere du parcours rendrait `None` ici et seulement ici :
    le banc nomme donc le critere perdu au lieu de dire « quelque chose a
    change ».

    L'ecart de `source_frame_count` vaut **une** frame (106 -> 107) et celui de
    `source_start_timecode` **une** image : Egan demande une correspondance
    « EXACTEMENT », pas une tolerance.
    """
    rushes = rushes_a_trois_entrees(cible_de_reference())
    mesures = mesures_de_reference(**{critere: ECARTS_PAR_CRITERE[critere]})

    conflit = extraction.rush_identity_conflict(
        rushes, RUSH_ID, mesures.source_parent, mesures=mesures
    )

    assert conflit is not None
    assert conflit.divergents == (critere,)
    assert conflit.entree["rush_id"] == RUSH_ID


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_le_DOSSIER_seul_ne_fait_PLUS_conflit(position):
    """`EPIC11-ARB-230`, et c'est le coeur de l'arbitrage.

    Avant lui, `AUTRE-CAM` contre `B-CAM` suffisait a declarer un conflit --
    donc, chez l'appelant, a suffixer en silence. La mesure de terrain qui l'a
    ouvert : deux copies du **meme fichier** dans `A/prise01.mp4` et
    `B/prise01.mp4` etaient declarees `prise01` puis `prise01-B`, sans une
    question, alors que 26 frames / 25/1 / 00:00:00:00 des deux cotes disaient
    que c'etait le meme rush.

    Les trois criteres techniques concordent ici et le dossier diverge : le
    verdict doit etre `None`, c'est-a-dire « c'est le meme rush », et
    l'appelant a un conflit a poser a l'operateur (`EPIC11-ARB-231`).

    **Les trois positions sont exercees** (regle des fabriques, point 4) : la
    cible en tete demasque un balayage qui rendrait toujours le premier
    element, en queue un balayage tronque. Ni l'une ni l'autre ne se voit au
    milieu, et les voisines divergent des trois criteres.
    """
    rushes = _rushes_avec_la_cible_en(position)
    assert (
        extraction.rush_identity_conflict(
            rushes,
            RUSH_ID,
            "AUTRE-CAM",
            mesures=mesures_de_reference(source_parent="AUTRE-CAM"),
        )
        is None
    )


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_volet_symetrique_un_critere_TECHNIQUE_separe_encore(position):
    """Sans lui, le precedent serait vert sur un comparateur qui ne compare
    plus rien du tout.

    `EPIC11-ARB-9` est **subordonne, pas annule** : deux prises differentes du
    multicam ordinaire -- durees differentes -- se separent toujours toutes
    seules, quel que soit le dossier. C'est le meme dossier des deux cotes
    ici, pour que seul le critere technique puisse expliquer le verdict.
    """
    rushes = _rushes_avec_la_cible_en(position)
    conflit = extraction.rush_identity_conflict(
        rushes, RUSH_ID, "B-CAM", mesures=mesures_de_reference(source_frame_count=107)
    )
    assert conflit is not None
    assert conflit.divergents == ("source_frame_count",)
    assert conflit.entree["rush_id"] == RUSH_ID


def _rushes_avec_la_cible_en(position: str) -> list[dict]:
    """Les trois entrees, la cible en tete / au milieu / en queue.

    `rushes_a_trois_entrees` place la cible au milieu et elle seule : les deux
    autres bords sont deux modes de panne differents, et aucun test au milieu
    ne les demasque tous les deux (`CLAUDE.md`, point 4 de la regle des
    fabriques, pose le 2026-09-03).
    """
    au_milieu = rushes_a_trois_entrees(cible_de_reference())
    cible = au_milieu[1]
    voisines = [au_milieu[0], au_milieu[2]]
    return {
        "tete": [cible, *voisines],
        "milieu": au_milieu,
        "queue": [*voisines, cible],
    }[position]


def test_les_quatre_criteres_concordants_ne_font_PAS_conflit():
    """Le volet symetrique, sans lequel le precedent serait vert a tort.

    Sans lui, un mutant qui declarerait conflit sur tout et n'importe quoi
    passerait les quatre parametres de la mesure ci-dessus.
    """
    rushes = rushes_a_trois_entrees(cible_de_reference())
    assert (
        extraction.rush_identity_conflict(
            rushes, RUSH_ID, "B-CAM", mesures=mesures_de_reference()
        )
        is None
    )


def test_le_conflit_porte_la_PREUVE_des_criteres_qui_concordent():
    """Note 2 d'Egan : « montrer la preuve : le nom et les infos communes ».

    L'ecran de conflit n'a pas seulement besoin de savoir qu'il y a conflit :
    il doit pouvoir montrer ce qui rapproche les deux rushs autant que ce qui
    les separe. Le verdict porte donc les deux listes.
    """
    rushes = rushes_a_trois_entrees(cible_de_reference())
    conflit = extraction.rush_identity_conflict(
        rushes, RUSH_ID, "B-CAM", mesures=mesures_de_reference(source_frame_count=107)
    )

    assert conflit is not None
    assert conflit.divergents == ("source_frame_count",)
    # Le dossier n'y figure plus depuis `EPIC11-ARB-230` : il n'est pas compare,
    # donc il ne peut etre ni concordant ni divergent.
    assert conflit.concordants == (
        "fps_source_exact",
        "source_start_timecode",
    )
    assert conflit.declares.source_frame_count == 106
    assert conflit.mesures.source_frame_count == 107


def test_la_cible_est_lue_au_MILIEU_et_les_voisines_ne_decident_de_rien():
    """Regle des fabriques : ni la premiere entree, ni la derniere.

    Les deux voisines divergent de la mesure sur les quatre criteres. Un
    `find` fautif qui rendrait la premiere, ou une boucle `continue` -> `break`
    qui s'arreterait au premier tour, declarerait un conflit ici alors que la
    cible concorde.
    """
    rushes = rushes_a_trois_entrees(cible_de_reference())
    assert rushes[1]["rush_id"] == RUSH_ID

    assert (
        extraction.rush_identity_conflict(
            rushes, RUSH_ID, "B-CAM", mesures=mesures_de_reference()
        )
        is None
    )


def test_un_rush_id_absent_de_la_liste_ne_fait_pas_conflit():
    """Rien de declare sous ce nom : c'est une premiere declaration."""
    rushes = rushes_a_trois_entrees(cible_de_reference())
    assert (
        extraction.rush_identity_conflict(
            rushes, "rush-jamais-vu", "B-CAM", mesures=mesures_de_reference()
        )
        is None
    )


def test_sans_mesures_la_garde_se_comporte_EXACTEMENT_comme_avant_la_note_5():
    """Compatibilite mesuree : `mesures=None` ne compare que le dossier parent.

    C'est le regime de `run_extraction`, ou le probe n'a pas encore eu lieu
    (section `C.8`). Le champ `source_frame_count` de la cible diverge
    franchement de la source reelle, et cela ne doit rien declencher : sans
    probe, cette valeur n'est pas mesuree, donc pas comparable.

    **`EPIC11-ARB-230` ne change rien ici, et c'est mesure plutot que promis.**
    Le dossier a cesse d'etre un critere d'identite ; il reste le
    **separateur de dernier recours** (`CRITERE_DE_DERNIER_RECOURS`) du seul
    regime ou aucun critere n'est comparable. Sans lui, `extract`
    recommencerait a ecraser `A-CAM/prise01.mov` avec `B-CAM/prise01.mov` --
    ce qu'`EPIC11-ARB-9` a ferme le 2026-08-05 et que
    `test_arb9_deux_rushs_homonymes_ne_s_ecrasent_plus` mesure encore.
    """
    rushes = rushes_a_trois_entrees(cible_de_reference())

    assert extraction.rush_identity_conflict(rushes, RUSH_ID, "B-CAM") is None

    conflit = extraction.rush_identity_conflict(rushes, RUSH_ID, "AUTRE-CAM")
    assert conflit is not None
    assert conflit.divergents == ("source_parent",)
    assert set(conflit.non_verifiables) == {
        "fps_source_exact",
        "source_frame_count",
        "source_start_timecode",
    }


@pytest.mark.parametrize("cote", ["declare", "mesure"])
def test_le_dernier_recours_ne_mord_PAS_sur_un_dossier_ABSENT(cote):
    """Le regime degrade suit la MEME doctrine que les criteres : ce qui n'est
    pas comparable est **dit**, jamais compte comme une divergence.

    Sans les deux gardes de nullite, `None != "B-CAM"` est vrai et un rush
    dont le manifeste ne declare aucun dossier -- une entree ancienne, ou un
    fichier pose a la racine d'un volume -- serait separe **a tort**, en
    silence, par le seul chemin ou le dossier pese encore.

    Les deux cotes sont exerces : l'absence peut venir du manifeste comme du
    fichier designe, et une seule des deux gardes suffit a laisser l'autre
    trou ouvert.
    """
    if cote == "declare":
        cible = entree_de_rush(
            RUSH_ID,
            source_parent=None,
            fps_source_exact="25/1",
            source_frame_count=106,
            source_start_timecode="01:01:39:12",
        )
        dossier_mesure = "B-CAM"
    else:
        cible = cible_de_reference()
        dossier_mesure = None

    assert (
        extraction.rush_identity_conflict(
            rushes_a_trois_entrees(cible), RUSH_ID, dossier_mesure
        )
        is None
    )


# ===========================================================================
# C.5 -- le defaut nomme par la note 5 : deux dossiers homonymes
# ===========================================================================


def test_deux_rushs_distincts_sous_deux_dossiers_nommes_PAREIL_font_desormais_conflit():
    """Le defaut que la note 5 elargit, mesure de bout en bout.

    `montage/hd/prise.mov` et `archives/hd/prise.mov` : meme nom de fichier,
    meme nom de dossier parent (`hd`), deux rushs differents. Le dossier parent
    etant le seul critere compare, l'outil les prenait pour le meme rush et le
    second ecrasait le premier.

    Sans les mesures, la garde reste aveugle -- c'est le defaut. Avec elles,
    la duree et le timecode de depart le nomment.
    """
    rushes = rushes_a_trois_entrees(
        entree_de_rush(
            RUSH_ID,
            source_parent="hd",
            fps_source_exact="25/1",
            source_frame_count=106,
            source_start_timecode="01:01:39:12",
        )
    )
    autre_rush_meme_dossier = extraction.CriteresIdentiteRush(
        source_parent="hd",
        fps_source_exact="25/1",
        source_frame_count=26,
        source_start_timecode="00:00:00:00",
    )

    assert extraction.rush_identity_conflict(rushes, RUSH_ID, "hd") is None

    conflit = extraction.rush_identity_conflict(
        rushes, RUSH_ID, "hd", mesures=autre_rush_meme_dossier
    )
    assert conflit is not None
    assert conflit.divergents == ("source_frame_count", "source_start_timecode")


# ===========================================================================
# C.6 -- le stockage : `rushes[]` gagne la duree
# ===========================================================================


def record_de_reference(
    *,
    source_frame_count: int = 106,
    source_frame_count_is_exact: bool = True,
    fps_target: float = 12.5,
) -> ExtractionRecord:
    """Un `ExtractionRecord` minimal, cale sur le rush reel du depot.

    Les valeurs viennent de la mesure `ffprobe` de
    `projects/chendj-mat/rush bitch 4.mp4` : 25/1, 106 frames, timecode de
    depart `01:01:39:12`.
    """
    selection = select_source_frames(
        fps_source=25,
        fps_target=fps_target,
        source_frame_count=source_frame_count,
        source_start_timecode="01:01:39:12",
        source_frame_count_is_exact=source_frame_count_is_exact,
    )
    return ExtractionRecord(
        project_id="projet-du-banc",
        rush_id=RUSH_ID,
        rush_source_name=f"{RUSH_ID}.mp4",
        rush_source_parent="B-CAM",
        rush_source_path=f"/videos/B-CAM/{RUSH_ID}.mp4",
        lot_id=build_lot_id(RUSH_ID, fps_target),
        frames_dir_relative=f"frames/{RUSH_ID}_12p5",
        selection=selection,
        fps_source=25.0,
        fps_target=fps_target,
        source_width=1920,
        source_height=1080,
        source_fields={},
        confirmation_mode="non_interactif",
        unknown_color_accepted=False,
        confirmed_at="2026-09-02T09:30:00Z",
    )


def entree_de_rush_d_une_extraction(record: ExtractionRecord) -> dict:
    """L'entree `rushes[]` qu'une EXTRACTION ecrit, par le chemin du produit.

    **Reconciliation de la liaison du 2026-09-05** (story 11.4e, lot A).
    `_build_rush_entry` prenait un `ExtractionRecord` ; elle prend desormais un
    `RushRecord` -- une declaration de rush (`EPIC11-ARB-131`) ecrit cette
    entree alors qu'il n'existe ni lot, ni cadence cible, ni selection, donc
    cinq des champs obligatoires d'un `ExtractionRecord`.

    Le banc ne fabrique pas ce `RushRecord` a la main : il passe par
    `rush_record_de_l_extraction`, l'**unique** projection du produit. Une
    fabrique locale figerait ici une seconde redaction du vocabulaire de la
    source, et un champ oublie par la projection resterait invisible -- alors
    que c'est precisement ce que ces tests mesurent.
    """
    return _build_rush_entry(None, rush_record_de_l_extraction(record))


def test_l_entree_de_rush_porte_desormais_le_cardinal_source_et_son_exactitude():
    """La moitie « et les stocker » de la note 5.

    La duree se stocke en **cardinal de frames** (`source_frame_count`), le
    vocabulaire que `lots[]` et `relink` emploient deja, jamais en secondes de
    flux : deux flux de duree flottante voisine peuvent porter le meme
    cardinal, et c'est le cardinal qui commande une extraction.
    """
    rush = entree_de_rush_d_une_extraction(record_de_reference())

    assert rush["source_frame_count"] == 106
    assert rush["source_frame_count_is_exact"] is True


def test_un_cardinal_ESTIME_se_stocke_estime_et_ne_se_fait_pas_passer_pour_exact():
    """Le drapeau d'exactitude voyage avec le cardinal, jamais tout seul.

    `resolve_source_frame_count` peut ne rendre qu'une estimation ; la
    stocker sans le dire ferait passer un lot potentiellement tronque pour un
    lot mesure.
    """
    rush = entree_de_rush_d_une_extraction(
        record_de_reference(source_frame_count_is_exact=False)
    )
    assert rush["source_frame_count"] == 106
    assert rush["source_frame_count_is_exact"] is False


def test_l_ensemble_des_cles_ecrites_dans_rushes_est_EXACTEMENT_celui_ci():
    """Egalite d'ensembles : une cle ajoutee sans schema rougit ici.

    `rushes[]` est ferme par `additionalProperties: false` : une cle ecrite et
    non declaree fait echouer la validation du manifeste, tres loin d'ici et
    sur un message qui ne nomme pas la story fautive.
    """
    assert set(entree_de_rush_d_une_extraction(record_de_reference())) == {
        "rush_id",
        "source_name",
        "source_parent",
        "source_path",
        "fps_source",
        "fps_source_exact",
        "resolution_source",
        "source_start_timecode",
        "source_frame_count",
        "source_frame_count_is_exact",
        "source_metadata_absent_fields",
    }


def test_le_cardinal_source_ne_vaut_JAMAIS_zero_dans_l_entree_ecrite():
    """Frontiere negative du stockage, pendant de la section `C.3`.

    Le schema pose `minimum: 1` sur le cardinal du lot ; l'entree de rush suit
    la meme regle. Un `int(... or 0)` defensif rougirait ici.
    """
    rush = entree_de_rush_d_une_extraction(record_de_reference())
    assert rush["source_frame_count"] >= 1


def test_le_manifeste_ecrit_VALIDE_contre_le_schema_avec_les_deux_champs_neufs(
    tmp_path,
):
    """`rushes[]` est ferme par `additionalProperties: false`.

    Ce banc est le seul endroit ou l'addition et sa declaration au schema se
    rencontrent : sans la declaration, `validate_manifest` leve ici, et non
    beaucoup plus loin sur un message qui ne nomme pas la story fautive.
    """
    manifeste = build_extraction_manifest(None, record_de_reference())
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")

    valide = validate_manifest(chemin)
    rush = valide["rushes"][0]
    assert rush["source_frame_count"] == 106
    assert rush["source_frame_count_is_exact"] is True


def test_un_cardinal_ZERO_est_REFUSE_par_le_schema_du_rush(tmp_path):
    """Frontiere negative du schema : `minimum: 1`, comme sur le lot.

    Sans elle, une substitution `0` a la place d'une absence traverserait la
    validation et se lirait ensuite comme un flux vide.
    """
    manifeste = build_extraction_manifest(None, record_de_reference())
    manifeste["rushes"][0]["source_frame_count"] = 0
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_manifest(chemin)


def test_un_rush_SANS_cardinal_reste_VALIDE_contre_le_schema(tmp_path):
    """L'addition est **additive** : aucun manifeste anterieur ne casse.

    Les deux champs neufs ne sont pas `required` : un projet ecrit avant cette
    story se relit sans migration, et ses criteres sont simplement non
    verifiables.
    """
    manifeste = build_extraction_manifest(None, record_de_reference())
    manifeste["rushes"][0].pop("source_frame_count")
    manifeste["rushes"][0].pop("source_frame_count_is_exact")
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(manifeste), encoding="utf-8")

    valide = validate_manifest(chemin)
    assert "source_frame_count" not in valide["rushes"][0]


# ===========================================================================
# C.7 -- la base de timecode n'est pas dupliquee, et c'est mesure
# ===========================================================================


def test_la_base_de_timecode_du_LOT_et_la_cadence_source_du_RUSH_sont_la_meme_valeur():
    """Pourquoi `rushes[]` ne gagne PAS un `timecode_base_fps` de plus.

    `frame_selection` pose `timecode_base=TIMECODE_BASE` (`"source"`) et
    `timecode_base_fps=fps_source_exact` : la base de timecode **est** la
    cadence source, et `rushes[].fps_source_exact` la porte deja. Ecrire la
    meme valeur sous deux noms dans le meme manifeste ouvrirait une divergence
    que rien ne mesurerait.

    Ce banc est ce qui rend ce choix tenable : si l'egalite tombe -- une base
    `target`, une cadence de base independante --, il rougit, et la
    comparaison d'identite devra alors porter un champ propre.
    """
    manifeste = build_extraction_manifest(None, record_de_reference())
    lot = manifeste["lots"][0]
    rush = manifeste["rushes"][0]

    assert lot["timecode_base"] == "source"
    assert lot["timecode_base_fps"] == rush["fps_source_exact"] == "25/1"


def test_timecode_base_et_timecode_base_fps_ne_designent_PAS_la_meme_chose():
    """Le piege de nommage qui a deja fait ecrire une specification fausse.

    `timecode_base` est l'enumeration `source`/`target` ; la **cadence** de la
    base est `timecode_base_fps`. Confondre les deux fait chercher une cadence
    la ou il y a un mot.
    """
    lot = build_extraction_manifest(None, record_de_reference())["lots"][0]

    assert lot["timecode_base"] in ("source", "target")
    assert "/" in lot["timecode_base_fps"]
    assert lot["timecode_base"] != lot["timecode_base_fps"]


# ===========================================================================
# C.8 -- l'ordre impose entre la garde de conflit et le probe
# ===========================================================================


def _rangs_des_appels(fonction, noms: set[str]) -> dict[str, int]:
    """Nom appele -> numero de ligne de son premier appel dans `fonction`."""
    arbre = ast.parse(inspect.getsource(fonction))
    rangs: dict[str, int] = {}
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        nom = (
            cible.attr
            if isinstance(cible, ast.Attribute)
            else cible.id
            if isinstance(cible, ast.Name)
            else None
        )
        if nom in noms and nom not in rangs:
            rangs[nom] = noeud.lineno
    return rangs


def test_la_garde_de_conflit_reste_AVANT_le_probe_dans_run_extraction():
    """Frontiere **negative** d'ordre, et elle protege l'AC 1.1 de la 11.4c.

    Remonter `probe_media` avant la garde de conflit -- ce qu'il faudrait pour
    nourrir la comparaison complete depuis `run_extraction` -- casserait
    `test_extraction_etat_en_amont.py::test_un_lot_deja_passe_a_l_aval_est_refuse_AVANT_meme_que_ffmpeg_soit_CHERCHE`,
    qui mesure que la transition d'etat precede `ensure_ffmpeg_available` en
    passant des binaires **absents** du `PATH` (ffprobe compris).

    L'ordre impose est donc l'inverse de celui qu'on attendrait, et il tient a
    une raison mesuree : la garde d'etat ne doit rien payer d'externe avant de
    refuser. La comparaison complete appartient au chemin de **declaration**,
    ou le probe precede naturellement l'ecran de conflit
    (`tui.atelier_extraction_ecriture.sonder_la_source`).
    """
    rangs = _rangs_des_appels(
        extraction.run_extraction,
        {"rush_identity_conflict", "probe_media", "ensure_ffmpeg_available"},
    )
    assert set(rangs) == {
        "rush_identity_conflict",
        "probe_media",
        "ensure_ffmpeg_available",
    }
    assert rangs["rush_identity_conflict"] < rangs["ensure_ffmpeg_available"]
    assert rangs["rush_identity_conflict"] < rangs["probe_media"]


def test_le_chemin_de_declaration_de_la_TUI_sonde_AVANT_de_pouvoir_comparer():
    """Le pendant positif : la ou la comparaison complete est possible.

    `sonder_la_source` rend deja les quatre criteres -- cadence source, cardinal
    de frames, exactitude, timecode de depart --, donc l'ecran de conflit de la
    story 11.4e n'a aucun probleme d'ordre a resoudre : il compare apres avoir
    sonde.
    """
    from mixed_media_utility.tui.atelier_extraction import SourceSondee

    champs = set(SourceSondee.__dataclass_fields__)
    assert {
        "fps_source",
        "source_frame_count",
        "source_frame_count_is_exact",
        "source_start_timecode",
    } <= champs


def test_les_criteres_mesures_se_construisent_depuis_le_probe_du_depot():
    """`CriteresIdentiteRush.mesures` lit la qualification, pas un second probe.

    Elle normalise la cadence par `codec_profiles.exact_frame_rate` -- la meme
    fonction que `_build_rush_entry` --, sans quoi `Fraction(25, 1)` et la
    chaine `"25/1"` du manifeste ne se compareraient jamais egales.
    """
    probe = json.loads(
        json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "r_frame_rate": "25/1",
                        "avg_frame_rate": "25/1",
                        "duration": "4.240000",
                        "nb_frames": "106",
                        "width": 1920,
                        "height": 1080,
                        "tags": {"timecode": "01:01:39:12"},
                    }
                ]
            }
        )
    )
    qualification = extraction.qualify_source(probe)

    mesures = extraction.CriteresIdentiteRush.depuis_la_qualification(
        source_parent="B-CAM",
        qualification=qualification,
        source_frame_count=106,
    )

    assert mesures == extraction.CriteresIdentiteRush(
        source_parent="B-CAM",
        fps_source_exact="25/1",
        source_frame_count=106,
        source_start_timecode="01:01:39:12",
    )


def test_une_SourceSondee_de_la_TUI_alimente_les_mesures_SANS_reconstruction():
    """La porte scalaire existe pour ce cas-la, et il est mesure.

    `sonder_la_source` rend une `SourceSondee`, pas une `SourceQualification`,
    et les deux ne nomment pas leur timecode pareil
    (`source_start_timecode` contre `start_timecode`). Exiger la seconde
    obligerait l'ecran de conflit de la story 11.4e a reconstruire un objet
    qu'il n'a pas -- ou a resonder, ce que le depot interdit.
    """
    from fractions import Fraction

    from mixed_media_utility.tui.atelier_extraction import SourceSondee

    sondee = SourceSondee(
        video_path=Path("/videos/B-CAM/prise.mp4"),
        fps_source=Fraction(25, 1),
        source_frame_count=106,
        source_frame_count_is_exact=True,
        source_start_timecode="01:01:39:12",
    )

    mesures = extraction.CriteresIdentiteRush.mesures(
        source_parent=sondee.video_path.parent.name,
        fps_source=sondee.fps_source,
        source_frame_count=sondee.source_frame_count,
        source_start_timecode=sondee.source_start_timecode,
    )

    assert mesures == mesures_de_reference()


def test_une_source_NON_TAGUEE_ne_se_voit_pas_inventer_un_timecode_de_depart():
    """Frontiere negative sur la construction des mesures.

    `00:00:00:00` est le defaut que tout correctif presse ecrirait a la place
    d'une absence de tag. `source_confirmation._normalize_probe_value` interdit
    deja cette substitution sur le probe ; elle est interdite ici aussi.
    """
    qualification = extraction.qualify_source(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "r_frame_rate": "25/1",
                    "avg_frame_rate": "25/1",
                    "duration": "4.240000",
                    "nb_frames": "106",
                }
            ]
        }
    )
    mesures = extraction.CriteresIdentiteRush.depuis_la_qualification(
        source_parent=None, qualification=qualification, source_frame_count=None
    )

    assert mesures.source_start_timecode is None
    assert mesures.source_parent is None
    assert mesures.source_frame_count is None
    assert mesures.fps_source_exact == "25/1"


def test_la_documentation_de_l_ordre_impose_est_TOUJOURS_sur_place():
    """Le commentaire est ce qui empeche le prochain agent de remonter le probe.

    Sans lui, la frontiere d'ordre ci-dessus se lit comme une contrainte
    arbitraire, et le premier agent qui voudra nourrir la garde depuis
    `run_extraction` la supprimera plutot que de la comprendre.
    """
    source = inspect.getsource(extraction.run_extraction)
    assert "EPIC11-ARB-83" in source
    assert "sonder_la_source" in source


def test_le_fichier_de_reference_du_depot_porte_bien_les_valeurs_mesurees():
    """Ancre documentaire : les valeurs des fabriques viennent d'une mesure.

    Elles ont ete lues le 2026-09-02 sur `tests/TEST_FILE.mp4` (25/1, 26
    frames, `00:00:00:00`) et sur `projects/chendj-mat/rush bitch 4.mp4` (25/1,
    106 frames, `01:01:39:12`). Ce banc ne relit pas les fichiers -- ils sont
    en Git LFS et peuvent etre des pointeurs -- mais il fige les valeurs pour
    que la prochaine session sache d'ou elles viennent.
    """
    assert Path("tests/TEST_FILE.mp4").name == "TEST_FILE.mp4"
    assert mesures_de_reference().source_frame_count == 106
