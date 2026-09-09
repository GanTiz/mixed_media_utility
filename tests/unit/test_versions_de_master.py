"""Versionnage des MASTERS video -- `EPIC11-ARB-91` (Egan, 2026-08-31).

Ce que cette frontiere mesure, et pourquoi elle est distincte de
`test_versions_de_lot.py` : **le rang d'un master n'est pas le rang de son
lot**. Un lot versionne porte deja `_v2` dans son `lot_id`, donc dans le nom
de son master, sans qu'aucun code neuf existe. Le rang mesure ici s'applique
au cas different et frequent -- re-encoder le MEME lot au MEME profil apres un
reglage change.

La confusion entre les deux est le defaut principal que ces tests guettent :
elle ferait qu'un lot `_v2` verrait son premier master numerote `_v2` a son
tour, ou qu'un master ordinaire d'un lot versionne serait pris pour une
version.
"""

from __future__ import annotations

import contextlib
import io
import json
import re

import pytest
from jsonschema.exceptions import ValidationError

from mixed_media_utility.io import (
    encode_manifest,
    manifest as io_manifest,
    naming,
)
from mixed_media_utility.io.encode_manifest import EncodedMaster
from mixed_media_utility.encode import (
    EncodeDecisionError,
    masters_version_watermark,
    resolve_master_version_rank,
)


# ---------------------------------------------------------------------------
# Le NOM : le rang vient en dernier, apres profil et resolution.
# ---------------------------------------------------------------------------


def test_le_rang_vient_APRES_le_profil_et_la_resolution():
    """Ordre des fragments, meme convention que pour un lot (cadence, bornes,
    puis version). Ce n'est pas une preference d'ecriture : profil et
    resolution sont ce qui DISTINGUE deux masters d'un meme lot, et un rang
    glisse entre eux ferait varier le prefixe commun de deux sorties du meme
    profil."""
    assert naming.build_master_filename(
        lot_id="L_24", profile_id="prores_hq", container="mov",
        resolution_segment="uhd", version_rank=2,
    ) == "L_24_mmu_prores_hq_uhd_v2.mov"


def test_le_rang_1_ne_porte_AUCUN_fragment():
    """`EPIC11-ARB-88` : l'origine ne porte pas de suffixe. Sans cette regle,
    tous les masters deja ecrits porteraient un nom que le code ne produit
    plus."""
    sans = naming.build_master_filename(
        lot_id="L_24", profile_id="prores_422", container="mov")
    avec_none = naming.build_master_filename(
        lot_id="L_24", profile_id="prores_422", container="mov", version_rank=None)
    assert sans == avec_none == "L_24_mmu_prores_422.mov"
    assert "_v" not in sans.replace("_mmu_", "")


def test_le_rang_du_LOT_et_le_rang_du_MASTER_ne_se_confondent_pas():
    """Le defaut central que cette story guette.

    Un lot de rang 2 dont le master est de rang 1, et un lot de rang 1 dont
    le master est de rang 2, doivent produire des noms DIFFERENTS -- sans
    quoi deux fichiers distincts se marcheraient dessus.
    """
    lot_v2_master_v1 = naming.build_master_filename(
        lot_id="L_24_v2", profile_id="prores_422", container="mov")
    lot_v1_master_v2 = naming.build_master_filename(
        lot_id="L_24", profile_id="prores_422", container="mov", version_rank=2)
    assert lot_v2_master_v1 == "L_24_v2_mmu_prores_422.mov"
    assert lot_v1_master_v2 == "L_24_mmu_prores_422_v2.mov"
    assert lot_v2_master_v1 != lot_v1_master_v2
    # Et les deux rangs se COMPOSENT sans s'ecraser.
    les_deux = naming.build_master_filename(
        lot_id="L_24_v2", profile_id="prores_422", container="mov", version_rank=3)
    assert les_deux == "L_24_v2_mmu_prores_422_v3.mov"


@pytest.mark.parametrize("rang_refuse", [0, 1, 100, -1, 2.0, True, "2"])
def test_un_rang_hors_bornes_est_refuse_NOMMEMENT(rang_refuse):
    """Meme borne et meme refus que pour un lot : une seule convention pour le
    meme fait, sinon deux verites (`EPIC5-ARB-78`)."""
    with pytest.raises(naming.NamingError):
        naming.build_master_filename(
            lot_id="L_24", profile_id="prores_422", container="mov",
            version_rank=rang_refuse,
        )


# ---------------------------------------------------------------------------
# Le RANG LIBRE : lu au manifeste, jamais au nom ; le trou, jamais max + 1.
# ---------------------------------------------------------------------------


#: Les trois places ou la cible peut se trouver dans `lots[]`. Point 4 de la
#: regle des fabriques (`CLAUDE.md`, pose le 2026-09-03) : la cible au MILIEU
#: demasque un `find` fautif, elle ne demasque PAS un balayage tronque, qui
#: est un autre mode de panne. Les deux bords s'ajoutent au milieu, ils ne le
#: remplacent pas.
POSITIONS_DE_LA_CIBLE = ("tete", "milieu", "queue")


def _voisin(lot_id: str) -> dict:
    """Un lot voisin DISTINGUABLE : son propre identifiant, son propre master.

    Distinguable et non un remplissage uniforme (point 1 de la regle) : deux
    voisins portant le meme `lot_id` rendraient invisible une permutation.
    """
    return {
        "lot_id": lot_id, "rush_id": "R",
        "encoded_masters": [{"path": f"outputs/{lot_id}_mmu_prores_422.mov",
                             "profile_id": "prores_422",
                             "frame_count": 1, "incomplete": False}],
    }


def _lot_avec_masters(*entrees, position: str = "milieu") -> dict:
    """Fabrique conforme a la regle du depot, appliquee a la liste que le code
    PARCOURT : plusieurs entrees DISTINGUABLES, et la cible placable aux TROIS
    places -- tete, milieu, queue (point 4 de la regle des fabriques).

    Le defaut par defaut reste le MILIEU, qui est ce que les bancs d'avant
    mesuraient : un `find` fautif rendant toujours le premier lot s'y demasque.
    Les deux bords sont l'ajout du lot B0 : un balayage tronque d'un cote ou de
    l'autre survivait a la place mediane seule, et rien dans ce banc ne l'aurait
    vu.
    """
    cible = {"lot_id": "L_24", "rush_id": "R", "encoded_masters": list(entrees)}
    tete, queue = _voisin("AUTRE_24"), _voisin("ENCORE_5")
    if position == "tete":
        lots = [cible, tete, queue]
    elif position == "queue":
        lots = [tete, queue, cible]
    elif position == "milieu":
        lots = [tete, cible, queue]
    else:  # pragma: no cover - garde de fabrique, jamais atteinte en vert
        raise AssertionError(f"position inconnue: {position!r}")
    return {
        "schema_version": "2.1",
        "project_id": "projet",
        "created": "2026-08-31T00:00:00Z",
        "rushes": [{"rush_id": "R"}],
        "lots": lots,
        "artifacts": {}, "color": {}, "video": {}, "reconstruction": {},
    }


def _master(nom, profil="prores_422", rang=None) -> dict:
    entree = {"path": f"outputs/{nom}", "profile_id": profil,
              "frame_count": 1, "incomplete": False}
    if rang is not None:
        entree["version_rank"] = rang
    return entree


def test_un_rang_de_master_CONSOMME_ne_se_reutilise_JAMAIS():
    """**Ce test mesurait l'inverse, et l'arbitrage l'a retourne**
    (`EPIC11-ARB-92`, Egan 2026-08-31, etendu aux trois objets versionnables).

    Il verifiait que le resolveur rendait le TROU -- 1, 2 et 4 pris donnant 3.
    Un rang se CONSOMME : le trou reste un trou, le prochain master est le 5.

    Le motif, etendu depuis les planches : un master livre a un client a quitte
    le disque comme une planche quitte l'imprimante, et un rang qui ressort
    ment sur ce qu'il designe. La crainte que ce test portait -- « chaque cycle
    produire/supprimer ferait deriver l'inventaire jusqu'a epuiser les 98
    rangs » -- est reelle, et c'est la LIBERATION EN QUEUE qui y repond, pas la
    reutilisation des trous.
    """
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov"),                    # rang 1
        _master("L_24_mmu_prores_422_v2.mov", rang=2),
        _master("L_24_mmu_prores_422_v4.mov", rang=4),
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 5


def test_la_ligne_d_eau_d_un_master_SURVIT_au_retrait_de_son_entree():
    """Le point que l'inventaire seul ne peut pas tenir, mesure ici pour les
    masters comme pour les planches : la famille ne declare plus que le rang 1,
    et la ligne d'eau se souvient que le 3 a servi."""
    m = _lot_avec_masters(_master("L_24_mmu_prores_422.mov"))
    m["lots"][1]["masters_version_watermark"] = {"prores_422": 3}
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 4
    # Et la ligne d'eau est par FAMILLE: un autre profil n'en herite pas.
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_hq", container="mov") == 1


def test_la_ligne_d_eau_distingue_la_RESOLUTION_dans_sa_cle():
    """Deux masters du meme profil a deux resolutions sont deux sorties
    VOULUES (story 6.1), donc deux familles, donc deux lignes d'eau."""
    m = _lot_avec_masters(_master("L_24_mmu_prores_422.mov"))
    m["lots"][1]["masters_version_watermark"] = {"prores_422|uhd": 5}
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov",
        resolution_segment="uhd") == 6
    # La resolution par defaut ne porte, elle, que son rang 1 declare.
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 2


def test_un_lot_sans_aucun_master_rend_le_rang_1():
    """Controle negatif : sans lui, un resolveur qui rendrait toujours 2
    passerait le test du trou."""
    m = _lot_avec_masters()
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 1


def test_un_PROFIL_different_n_est_PAS_une_version():
    """Deux masters d'un lot qui different par le profil sont deux sorties
    VOULUES (story 6.1), pas deux versions l'une de l'autre. Les confondre
    ferait numeroter `_v2` un premier encodage en ProRes HQ au motif qu'un
    ProRes 422 existe -- un nom qui mentirait sur ce qu'il designe."""
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov", "prores_422"),
        _master("L_24_mmu_prores_422_v2.mov", "prores_422", rang=2),
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_hq", container="mov") == 1


def test_une_RESOLUTION_differente_n_est_PAS_une_version():
    """Meme motif : la story 6.1 produit deux masters du MEME profil, l'un a
    la resolution par defaut, l'autre en natif."""
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov"),
        _master("L_24_mmu_prores_422_v2.mov", rang=2),
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov",
        resolution_segment="3307x1860") == 1


def test_le_rang_est_lu_au_MANIFESTE_et_pas_au_NOM():
    """`EPIC5-ARB-3` : le nom ne doit jamais devenir la source de verite d'un
    fait que le manifeste declare.

    Une entree dont le NOM porte `_v7` mais dont le manifeste ne declare
    aucun rang vaut rang 1 -- et son nom ne correspond alors plus a ce que
    `build_master_filename` produirait, donc elle ne prend aucun rang. Le
    resolveur rend 2, pas 8 : il n'a pas lu le nom.
    """
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov"),                # rang 1, coherent
        _master("L_24_mmu_prores_422_v7.mov"),             # nom v7, manifeste muet
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 2


def test_le_MANIFESTE_tranche_quand_il_diverge_du_nom():
    """**Le test qui manquait, trouve par mutation.**

    `test_le_rang_est_lu_au_MANIFESTE_et_pas_au_NOM` ci-dessus etait une
    tautologie deguisee : sur sa fixture, lire le rang au manifeste et le lire
    au nom rendaient LA MEME reponse (2), si bien qu'un mutant qui lisait le
    nom survivait a tout le banc.

    Le cas qui les separe vraiment est celui-ci : une entree dont le manifeste
    declare le rang 2 mais dont le NOM ne porte pas `_v2`. Le rang 2 est alors
    PRIS -- le manifeste le dit --, et le resolveur doit rendre 3.

    Ce que la lecture par le nom aurait fait, et pourquoi c'est grave : elle
    aurait lu « rang 1 » sur ce nom, donc considere le rang 2 comme LIBRE,
    donc fait ecrire le master suivant par-dessus une entree existante. Une
    destruction silencieuse, produite par un mecanisme dont c'est precisement
    l'objet d'empecher (`EPIC11-ARB-89`).
    """
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov"),                       # rang 1
        _master("L_24_mmu_prores_422.mov", rang=2),               # rang 2, nom sans `_v2`
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 3


@pytest.mark.parametrize("position", POSITIONS_DE_LA_CIBLE)
def test_la_famille_visee_se_lit_a_CHAQUE_BORD_de_la_liste_des_lots(position):
    """Point 4 de la regle des fabriques, sur la liste `lots[]` du manifeste.

    **Le trou que ce banc ferme, et il etait entier.** Toutes les fixtures de
    ce fichier placaient `L_24` en position MEDIANE de trois lots. La place
    mediane demasque un `find` fautif -- celui qui rend toujours le premier --
    et c'est ce que la regle demandait jusqu'au 2026-09-03. Elle ne demasque
    PAS un balayage tronque : `lots[:-1]` et `lots[1:]` rendaient tous deux la
    bonne reponse sur une cible au milieu, et les deux resolveurs de ce module
    (`resolve_master_version_rank` et `masters_version_watermark`) balaient
    cette liste.

    Ce qu'un balayage tronque ferait, et c'est le meme dommage des deux cotes :
    la famille visee n'etant pas trouvee, le resolveur rend l'ORIGINE -- donc
    le rang 1, donc le nom ordinaire -- pour un lot qui porte deja quatre
    masters. C'est-a-dire l'ecrasement silencieux que `EPIC11-ARB-104` existe
    pour ecarter, atteint par le chemin qui devait le prevenir.

    Les deux fonctions publiques sont mesurees ensemble parce qu'elles lisent
    la MEME liste par deux chemins distincts : une seule des deux corrigee
    laisserait l'autre mentir.
    """
    m = _lot_avec_masters(
        _master("L_24_mmu_prores_422.mov"),                    # rang 1
        _master("L_24_mmu_prores_422_v2.mov", rang=2),
        _master("L_24_mmu_prores_422_v4.mov", rang=4),
        position=position,
    )
    assert resolve_master_version_rank(
        m, "L_24", profile_id="prores_422", container="mov") == 5, position
    assert masters_version_watermark(
        m, "L_24", profile_id="prores_422", container="mov") == 4, position
    # Le volet POSITIF de la meme mesure : les voisins ne sont pas confondus
    # avec la cible, quelle que soit la place de celle-ci. Sans lui, un
    # resolveur qui rendrait 5 pour n'importe quel `lot_id` passerait.
    for voisin in ("AUTRE_24", "ENCORE_5"):
        assert resolve_master_version_rank(
            m, voisin, profile_id="prores_422", container="mov") == 2, voisin


def test_les_rangs_epuises_rendent_un_refus_a_ISSUES_NOMMEES():
    """`EPIC11-ARB-89` : jamais un blocage sec. Sans cette borne, le rang 100
    partait vers `format_version_suffix` et en revenait sous un « rang hors
    bornes » qui ne dit rien de la situation et n'offre aucune sortie."""
    entrees = [_master("L_24_mmu_prores_422.mov")]
    for rang in range(2, 100):
        entrees.append(_master(f"L_24_mmu_prores_422_v{rang}.mov", rang=rang))
    m = _lot_avec_masters(*entrees)
    with pytest.raises(EncodeDecisionError) as refus:
        resolve_master_version_rank(m, "L_24", profile_id="prores_422", container="mov")
    texte = str(refus.value)
    assert "project remove" in texte, "le refus n'offre pas la suppression"
    assert "--overwrite" in texte, "le refus n'offre pas l'ecrasement conscient"


# ---------------------------------------------------------------------------
# La PERSISTANCE : champ additif, omission stricte au rang 1.
# ---------------------------------------------------------------------------


def test_un_master_de_rang_1_n_ECRIT_PAS_le_champ():
    """Omission stricte, jamais `null` ni `1`. Le schema pose
    `additionalProperties: false` avec `minimum: 2` : ecrire l'un ou l'autre
    ferait echouer la validation de tout master ordinaire."""
    entree = EncodedMaster(
        path="outputs/L_24_mmu_prores_422.mov", profile_id="prores_422",
        frame_count=10, incomplete=False,
    ).to_entry()
    assert "version_rank" not in entree
    assert set(entree) == set(encode_manifest.ENCODE_MASTER_FIELDS)


def test_un_master_versionne_ECRIT_le_champ():
    entree = EncodedMaster(
        path="outputs/L_24_mmu_prores_422_v2.mov", profile_id="prores_422",
        frame_count=10, incomplete=False, version_rank=2,
    ).to_entry()
    assert entree["version_rank"] == 2


def _manifeste_validable(entrees) -> dict:
    return {
        "schema_version": "2.1", "project_id": "projet",
        "created": "2026-08-31T00:00:00Z",
        "rushes": [{"rush_id": "R"}],
        "lots": [{"lot_id": "L_24", "rush_id": "R", "encoded_masters": entrees}],
        "artifacts": {}, "color": {}, "video": {}, "reconstruction": {},
    }


def test_le_schema_ACCEPTE_un_inventaire_versionne(tmp_path):
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(_manifeste_validable([
        _master("L_24_mmu_prores_422.mov"),
        _master("L_24_mmu_prores_422_v2.mov", rang=2),
        _master("L_24_mmu_prores_422_v99.mov", rang=99),
    ])), encoding="utf-8")
    io_manifest.validate_manifest(chemin)


@pytest.mark.parametrize("rang_refuse", [0, 1, 100, 9999])
def test_le_schema_REFUSE_un_rang_de_master_hors_bornes(tmp_path, rang_refuse):
    """Meme famille que les bornes de `lots[].version_rank`: un chiffre que le
    code porte mais que le banc ne tient pas est un chiffre libre de deriver."""
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(_manifeste_validable([
        _master("L_24_mmu_prores_422_vX.mov", rang=rang_refuse),
    ])), encoding="utf-8")
    with pytest.raises(ValidationError):
        io_manifest.validate_manifest(chemin)


def test_les_bornes_du_schema_de_master_et_celles_du_code_sont_les_MEMES():
    """Deux emplacements pour le meme fait sont deux verites
    (`EPIC5-ARB-78`)."""
    schema = json.loads(io_manifest.DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    champ = (schema["properties"]["lots"]["items"]["properties"]
             ["encoded_masters"]["items"]["properties"]["version_rank"])
    assert champ["minimum"] == naming.VERSION_RANK_MIN
    assert champ["maximum"] == naming.VERSION_RANK_MAX


def test_un_manifeste_ANTERIEUR_sans_le_champ_reste_valide(tmp_path):
    """Additif : le parc de manifestes deja ecrits doit rester lisible."""
    chemin = tmp_path / "project.json"
    chemin.write_text(json.dumps(_manifeste_validable([
        {"path": "outputs/L_24_mmu_prores_422.mov", "profile_id": "prores_422",
         "frame_count": 10, "incomplete": False},
    ])), encoding="utf-8")
    io_manifest.validate_manifest(chemin)


# ---------------------------------------------------------------------------
# Le REFUS d'encode : trois issues, jamais une seule (`EPIC11-ARB-89`).
# ---------------------------------------------------------------------------


def test_le_refus_de_master_present_offre_TROIS_issues(tmp_path):
    """La redaction d'origine ne proposait que `--overwrite`, c'est-a-dire la
    destruction comme unique sortie. C'est exactement ce que l'arbitrage
    interdit, et c'etait la dette recensee pour `encode`."""
    from mixed_media_utility import encode

    master = tmp_path / "L_24_mmu_prores_422.mov"
    master.write_bytes(b"un master deja present")
    with pytest.raises(encode.EncodeDecisionError) as refus:
        encode.check_output_destination(master, overwrite=False)
    texte = str(refus.value)
    for issue in ("--nouvelle-version", "--overwrite", "project remove"):
        assert issue in texte, f"le refus n'offre pas l'issue {issue!r}"


# ===========================================================================
# Story 11.8, AC 4 -- LE BRANCHEMENT. Tout ce qui precede mesurait des pieces
# qui existaient ; ce qui suit mesure qu'elles sont RELIEES.
#
# Etat mesure au 2026-09-02, et c'est ce que ces bancs ferment : zero site
# d'appel en production pour `resolve_master_version_rank`, pour
# `masters_version_watermark` et pour `cle_de_famille_de_master` ;
# `build_master_output_path` n'a jamais passe `version_rank` ; le champ
# `EncodedMaster.version_rank` n'etait renseigne par aucun producteur ; et
# `--nouvelle-version`, que le refus de `check_output_destination` conseille
# verbatim, n'existait pas au parser.
# ===========================================================================

import argparse
import ast
import re
import types
from pathlib import Path

from mixed_media_utility import cli, codec_profiles, encode as encode_module
from mixed_media_utility.io import encode_manifest as em, project_layout
from mixed_media_utility.io.manifest import validate_manifest


# ---------------------------------------------------------------------------
# AC 4.6 -- LA FRONTIERE NEGATIVE : un refus ne nomme que des options qui
# existent. Aucun test positif ne verrait revenir le defaut ; celui-ci si.
# ---------------------------------------------------------------------------

#: Une option longue citee dans une prose. Ancree a gauche sur un non-mot pour
#: ne pas couper `--nouvelle-version` en `-version` au detour d'un tiret.
MOTIF_OPTION = re.compile(r"(?<![\w-])--[a-z0-9][a-z0-9-]*")

#: `mmu <commande>[ <sous-commande>]`, tel qu'un message de refus l'ecrit. La
#: capture s'arrete d'elle-meme au premier `--`, qui n'est pas un mot.
MOTIF_COMMANDE = re.compile(r"mmu ((?:[a-z][a-z0-9-]*)(?: [a-z][a-z0-9-]*)*)")


class _ParserCapture(Exception):
    """Signal interne : le parser est construit, on n'ira pas plus loin."""


def _parser_racine() -> argparse.ArgumentParser:
    """Le VRAI parser de la CLI, pas une relecture de son source.

    `cli.main` construit son parser dans son propre corps : il n'existe aucun
    `build_parser()` a appeler. Plutot que de relire `cli.py` a l'AST -- ce qui
    mesurerait ce que le test croit du source, et non ce qu'argparse declare --
    on intercepte `parse_args` pour recuperer l'objet lui-meme. La lecture qui
    suit porte alors sur `option_strings`, donc sur les options DECLAREES, et
    jamais sur la prose des `help=` (qui en cite plusieurs, et qui rendrait la
    frontiere trop permissive).
    """
    capture: dict[str, argparse.ArgumentParser] = {}
    vrai = argparse.ArgumentParser.parse_args

    def espion(self, *args, **kwargs):
        capture.setdefault("parser", self)
        raise _ParserCapture()

    argparse.ArgumentParser.parse_args = espion
    try:
        cli.main([])
    except _ParserCapture:
        pass
    finally:
        argparse.ArgumentParser.parse_args = vrai
    return capture["parser"]


def _options_par_commande(parser, prefixe=()) -> dict[tuple[str, ...], set[str]]:
    """Toutes les options longues declarees, indexees par chemin de commande."""
    table = {
        prefixe: {
            option
            for action in parser._actions
            for option in action.option_strings
            if option.startswith("--")
        }
    }
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for nom, sous in action.choices.items():
                table.update(_options_par_commande(sous, prefixe + (nom,)))
    return table


def _citations_de_refus(source: str) -> list[tuple[int, str]]:
    """Les litteraux de chaine portes par un `raise`, avec leur ligne.

    Le perimetre est celui de l'AC : « les options citees dans les messages de
    refus ». Les docstrings et les commentaires en citent d'autres, en prose,
    et un operateur ne les lit jamais au moment ou une commande echoue.

    **Un `f"..."` est RECOLLE, ses interpolations rendues comme un gabarit**
    (fermeture de `C1-02`, 2026-09-05). La redaction d'avant ne relevait que
    les morceaux CONSTANTS : une citation qui enjambe une interpolation
    arrivait ici coupee en deux, si bien que la moitie portant
    `mmu project remove` ne portait plus `--liberer-le-rang` et que ce banc
    rougissait sur des options parfaitement declarees -- ailleurs. Le defaut
    est le meme que celui des litteraux adjacents, un cran plus loin, et il
    mord des qu'un refus nomme une valeur reelle plutot qu'un gabarit.
    """
    def _rendu(noeud: ast.JoinedStr) -> str:
        return "".join(
            valeur.value if isinstance(valeur, ast.Constant)
            and isinstance(valeur.value, str) else "<...>"
            for valeur in noeud.values)

    citations: list[tuple[int, str]] = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Raise):
            continue
        pile = [noeud]
        while pile:
            sous = pile.pop()
            if isinstance(sous, ast.JoinedStr):
                # On ne redescend PAS : sinon les morceaux constants seraient
                # comptes une seconde fois, tronques.
                citations.append((noeud.lineno, _rendu(sous)))
                continue
            if isinstance(sous, ast.Constant) and isinstance(sous.value, str):
                citations.append((noeud.lineno, sous.value))
            pile.extend(ast.iter_child_nodes(sous))
    return citations


def _ecarts(source: str, table: dict[tuple[str, ...], set[str]]) -> list[str]:
    """Les options citees par un refus que le parser ne declare PAS.

    Une citation est confrontee aux options de `encode` -- la commande dont ce
    module est le coeur -- augmentees de celles des commandes qu'elle NOMME
    explicitement (`mmu project remove ...`). Sans cette seconde source, le
    refus de rangs epuises rougirait sur `--liberer-le-rang`, qui existe
    parfaitement mais ailleurs ; sans la premiere, `--nouvelle-version` serait
    accepte au seul motif qu'une autre commande le declare.
    """
    ecarts: list[str] = []
    for ligne, texte in _citations_de_refus(source):
        citees = set(MOTIF_OPTION.findall(texte))
        if not citees:
            continue
        permises = set(table[("encode",)])
        for nom in MOTIF_COMMANDE.findall(texte):
            chemin = tuple(nom.split())
            while chemin and chemin not in table:
                chemin = chemin[:-1]
            if not chemin:
                ecarts.append(f"ligne {ligne}: la commande `mmu {nom}` n'existe pas")
                continue
            permises |= table[chemin]
        for option in sorted(citees - permises):
            ecarts.append(f"ligne {ligne}: {option} n'est declaree par aucun parser")
    return ecarts


def test_aucun_refus_d_encode_ne_NOMME_une_option_qui_n_existe_pas():
    """AC 4.6, et c'est la forme qui attrape la reintroduction du defaut.

    Ce que la frontiere rendait AVANT le branchement : un ecart, et c'etait le
    pire mode de panne d'`EPIC11-ARB-89`. `check_output_destination` refusait
    un master present en conseillant, verbatim, « relancer avec
    --nouvelle-version pour ecrire une version voisine sans toucher a
    celle-ci » -- et `mmu encode --nouvelle-version` rendait `unrecognized
    arguments`. Le refus nommait une issue que la machine n'offrait pas :
    trois issues affichees, deux reelles, dont une seule non destructive.

    Aucun test positif ne verrait ce defaut revenir. Un banc qui mesure que
    `--nouvelle-version` marche reste vert si quelqu'un ajoute demain un refus
    qui conseille `--forcer-le-rang` ; celui-ci rougit.
    """
    source = Path(encode_module.__file__).read_text(encoding="utf-8")
    ecarts = _ecarts(source, _options_par_commande(_parser_racine()))
    assert ecarts == [], "\n".join(ecarts)


def test_la_frontiere_des_options_MORD_vraiment():
    """Controle negatif : sans lui, l'AC 4.6 pourrait etre verte et vide.

    C'est le piege que ce depot a deja paye deux fois -- un banc d'atomicite
    vert pour une ecriture non atomique, un motif de refus qui ne reconnaissait
    pas la forme inversee. Une frontiere qui ne mord sur rien ne mesure rien.
    """
    table = _options_par_commande(_parser_racine())
    fantome = 'raise EncodeDecisionError(CODE, "Relancer avec --nouvelle-lune.")'
    assert _ecarts(fantome, table) == [
        "ligne 1: --nouvelle-lune n'est declaree par aucun parser"
    ]
    # Et une commande inventee est vue elle aussi.
    inconnue = 'raise EncodeDecisionError(CODE, "Voir `mmu projet retirer --lot`.")'
    assert _ecarts(inconnue, table) == [
        "ligne 1: la commande `mmu projet retirer` n'existe pas"
    ]
    # Symetrique : une citation licite ne rougit pas, sans quoi la frontiere
    # rougirait sur tout et ne dirait plus rien.
    licite = 'raise EncodeDecisionError(CODE, "Relancer avec --overwrite.")'
    assert _ecarts(licite, table) == []


# ---------------------------------------------------------------------------
# AC 4.1 -- l'option existe, et elle est EXCLUSIVE de `--overwrite`
# ---------------------------------------------------------------------------


def test_encode_DECLARE_bien_nouvelle_version():
    """L'option que le refus conseillait sans qu'elle existe."""
    options = _options_par_commande(_parser_racine())[("encode",)]
    assert "--nouvelle-version" in options
    assert "--overwrite" in options


def test_les_deux_issues_du_meme_conflit_ne_se_COMBINENT_pas(tmp_path):
    """Modele litteral d'`extract` : le refus est nomme, et il vient du COEUR.

    Il n'est pas rendu par un `add_mutually_exclusive_group` d'argparse, et
    c'est deliberement le meme choix que pour `extract` : la TUI n'a pas le
    droit d'importer `cli` (frontiere de la 11.4b), donc un refus qui vivrait
    dans le parser ne l'atteindrait jamais.

    Le refus est aussi le TOUT PREMIER geste de `plan_encode` : ce projet-ci
    n'a ni manifeste utilisable ni lot, et le refus tombe quand meme -- preuve
    qu'aucune lecture de disque n'est payee avant lui.
    """
    with pytest.raises(EncodeDecisionError) as refus:
        encode_module.plan_encode(
            tmp_path, {"lots": []}, lot_id="peu importe",
            overwrite=True, nouvelle_version=True,
        )
    assert refus.value.code == encode_module.ENCODE_VERSION_AND_OVERWRITE
    texte = str(refus.value)
    assert "--nouvelle-version" in texte and "--overwrite" in texte
    assert "Rien n'a ete encode" in texte


def test_le_code_de_ce_refus_est_du_VOCABULAIRE_ferme():
    """Un code hors table est une faute de programmation, pas une prose."""
    assert (
        encode_module.ENCODE_VERSION_AND_OVERWRITE
        in encode_module.ENCODE_REFUSAL_CODES
    )


# ---------------------------------------------------------------------------
# AC 4.2 -- le rang atteint le NOM du fichier
# ---------------------------------------------------------------------------


def test_build_master_output_path_PASSE_le_rang_au_nom():
    """Le chainon manquant mesure le 2026-09-02 : la fabrique de nom acceptait
    `version_rank` et son unique appelant ne le passait jamais. Un rang 2
    resolu se serait donc ecrit sous le nom du rang 1 -- c'est-a-dire par-dessus
    le master existant, la destruction exacte que l'option evite."""
    profil = codec_profiles.get_profile("prores_422")
    cible = encode_module.resolve_output_resolution(None)
    sans = encode_module.build_master_output_path(
        Path("/tmp/projet"), "L_24", profil, cible)
    avec = encode_module.build_master_output_path(
        Path("/tmp/projet"), "L_24", profil, cible, version_rank=3)
    assert sans.name.endswith(".mov") and "_v3" not in sans.name
    assert avec.name == sans.name.replace(".mov", "_v3.mov")
    assert avec.parent == sans.parent == project_layout.outputs_dir(Path("/tmp/projet"))


def test_le_plan_porte_la_CLE_DE_FAMILLE_et_ne_la_fait_pas_recalculer():
    """`EncodePlan.masters_family_key` est ce que la persistance LIT.

    Le profil ET la resolution : deux masters d'un lot qui different par l'un
    ou l'autre ne sont pas deux versions l'un de l'autre, et les confondre
    ferait numeroter `_v2` un premier encodage en ProRes HQ au motif qu'un
    ProRes 422 existe.
    """
    faux = types.SimpleNamespace(
        profile_id="prores_hq",
        resolution=encode_module.resolve_output_resolution("uhd2160"),
    )
    cle = encode_module.EncodePlan.masters_family_key.fget(faux)
    assert cle == encode_module.cle_de_famille_de_master(
        "prores_hq", encode_module.resolution_name_segment(faux.resolution))
    assert cle.startswith("prores_hq|")
    defaut = types.SimpleNamespace(
        profile_id="prores_hq",
        resolution=encode_module.resolve_output_resolution(None),
    )
    assert encode_module.EncodePlan.masters_family_key.fget(defaut) == "prores_hq"


# ---------------------------------------------------------------------------
# AC 4.7 -- la reservation atomique offre DEUX issues, dont une non destructive
# ---------------------------------------------------------------------------


def test_la_reservation_du_master_offre_DEUX_issues(tmp_path):
    """`EPIC11-ARB-107` n'interdisait pas la seconde issue, il la DICTAIT.

    Son motif : la commande a deja propose ses issues a son entree, et ce
    refus-ci ne se declenche que si le fichier est apparu DEPUIS. Ce qui etait
    ecarte est de proposer un RANG calcule ici -- il pourrait etre pris a son
    tour. Relancer la commande, elle, reresout le rang contre le manifeste
    desormais a jour : c'est une issue, et elle ne detruit rien.

    Le plan est un substitut minimal, et il est honnete : `reserve_master_path`
    ne lit que ces deux attributs, et un `EncodePlan` complet exigerait un
    encodage reel pour mesurer une phrase.
    """
    cible = tmp_path / "L_24_mmu_prores_422.mov"
    cible.write_bytes(b"pose entre la decision et l'ecriture")
    plan = types.SimpleNamespace(output_path=cible, overwrite=False)
    with pytest.raises(EncodeDecisionError) as refus:
        encode_module.reserve_master_path(plan)
    texte = str(refus.value)
    assert "--overwrite" in texte, "l'issue destructive a disparu"
    assert "relancer la commande" in texte.lower(), "aucune issue NON destructive"
    assert "Rien n'a ete encode" in texte


# ---------------------------------------------------------------------------
# AC 4.8 -- un rang epuise nomme les DEUX issues d'`EPIC11-ARB-111`, dont la
# suppression d'un MASTER SEUL
# ---------------------------------------------------------------------------


def test_le_refus_de_rangs_epuises_nomme_la_suppression_d_un_MASTER_SEUL():
    """La redaction d'avant `EPIC11-ARB-111` envoyait detruire un lot entier
    de plusieurs Go pour liberer un rang de master. Les deux issues doivent
    donc etre nommees telles qu'elles existent : `--master` designe le master,
    `--liberer-le-rang` rend le rang, et les deux se lisent au parser.

    **CE TEST REVENDIQUAIT PLUS QU'IL NE MESURAIT**, et le finding qu'il a
    laisse passer est le seul que les trois couches de revue d'`EPIC11-ARB-224`
    ont trouve independamment (`C1-02`, `C2-10`, `F1`). Sa docstring promettait
    << les deux se lisent au parser >> ; ses deux assertions verifiaient la
    PRESENCE du drapeau dans le texte et son EXISTENCE sur la commande. Les
    deux etaient vraies de la chaine cassee -- `mmu project remove ... --master
    <chemin de famille> ...`, ou `--master`, devenu drapeau nu dans le meme
    diff, faisait rendre `unrecognized arguments` (code 2) a argparse.

    Les deux assertions d'origine restent : elles sont bon marche et elles
    nomment ce qui manque quand ce qui manque est un mot. Ce qui les suit est
    la mesure que la docstring promettait, et elle vit dans
    `test_l_issue_du_refus_de_rangs_epuises_est_JOUABLE_de_bout_en_bout`.
    """
    entrees = [_master("L_24_mmu_prores_422.mov")]
    for rang in range(2, 100):
        entrees.append(_master(f"L_24_mmu_prores_422_v{rang}.mov", rang=rang))
    with pytest.raises(EncodeDecisionError) as refus:
        resolve_master_version_rank(
            _lot_avec_masters(*entrees), "L_24",
            profile_id="prores_422", container="mov")
    texte = str(refus.value)
    for fragment in ("--master", "--liberer-le-rang", "--overwrite"):
        assert fragment in texte, f"issue incomplete: {fragment!r} absent"
    options = _options_par_commande(_parser_racine())[("project", "remove")]
    assert {"--master", "--liberer-le-rang", "--lot", "--confirmer"} <= options
    # **AUCUN CHEMIN, JAMAIS** -- la clause centrale du contrat, dans la ligne
    # meme qui l'avait perdue. Le refus designe par les arguments producteurs.
    assert "--profile" in texte, (
        "l'issue ne nomme plus le profil : le coeur exige `--profile` avec "
        "`--master`, une issue sans lui est refusee avant d'avoir rien lu.")
    assert "chemin" not in texte.lower(), texte


#: Les numeraux qu'un refus de ce depot emploie pour annoncer ses issues.
NUMERAUX = {"Une": 1, "Deux": 2, "Trois": 3, "Quatre": 4, "Cinq": 5}

#: `Deux issues:` / `Trois issues:` -- l'annonce, telle qu'un refus l'ecrit.
MOTIF_ARITE_DU_REFUS = re.compile(
    r"\b(Une|Deux|Trois|Quatre|Cinq) issues?\s*:")


def _arite_du_refus(texte: str) -> tuple[int, int]:
    """(ce que le refus ANNONCE, ce qu'il LISTE reellement).

    Les issues se separent comme un lecteur les separe : par `;` d'abord,
    par `, ou ` ensuite -- les deux formes que les trois refus de master
    emploient. La phrase de cloture (`Rien n'a ete encode`) n'en est pas une
    et se retire avant le decoupage.
    """
    annonce = MOTIF_ARITE_DU_REFUS.search(texte)
    assert annonce is not None, f"aucune arite annoncee: {texte}"
    clause = texte[annonce.end():].split("Rien n'a ete encode")[0]
    morceaux = [
        part
        for bloc in clause.split(";")
        for part in re.split(r",\s+ou\s+", bloc)
        if part.strip()
    ]
    return NUMERAUX[annonce.group(1)], len(morceaux)


def test_les_trois_refus_de_master_ANNONCENT_le_nombre_qu_ils_LISTENT(tmp_path):
    """**Trouve par mutation (M20), et aucun banc ne le voyait.**

    Remplacer `Deux issues:` par `Une issue:` dans le refus de rangs epuises
    survivait aux 42 tests du banc : les deux issues restaient ecrites, seul
    le nombre annonce devenait faux. Or c'est ce nombre que l'operateur lit
    en premier -- un refus qui annonce UNE issue et en offre deux fait
    prendre la destructive pour la seule, ce qui est le resultat exact
    qu'`EPIC11-ARB-89` interdit, obtenu sans retirer une seule issue.

    La frontiere ne compare pas deux chaines ecrites cote a cote : elle
    COMPTE ce que le refus liste et le confronte a ce qu'il annonce. Elle
    mord donc dans les deux sens -- une issue retiree sans corriger le
    numeral, un numeral change sans retirer d'issue -- et elle vaut pour les
    trois refus de master a la fois, la ou un test par phrase en aurait
    laisse deux derriere.
    """
    # 1. La destination deja occupee (`check_output_destination`).
    occupee = tmp_path / "L_24_mmu_prores_422.mov"
    occupee.write_bytes(b"master deja la")
    with pytest.raises(EncodeDecisionError) as destination:
        encode_module.check_output_destination(occupee, overwrite=False)

    # 2. La reservation atomique perdue (`reserve_master_path`).
    with pytest.raises(EncodeDecisionError) as reservation:
        encode_module.reserve_master_path(
            types.SimpleNamespace(output_path=occupee, overwrite=False))

    # 3. Les 98 rangs consommes (`resolve_master_version_rank`).
    entrees = [_master("L_24_mmu_prores_422.mov")]
    for rang in range(2, 100):
        entrees.append(_master(f"L_24_mmu_prores_422_v{rang}.mov", rang=rang))
    with pytest.raises(EncodeDecisionError) as epuises:
        resolve_master_version_rank(
            _lot_avec_masters(*entrees), "L_24",
            profile_id="prores_422", container="mov")

    for nom, refus in (("destination occupee", destination),
                       ("reservation perdue", reservation),
                       ("rangs epuises", epuises)):
        annoncee, listees = _arite_du_refus(str(refus.value))
        assert annoncee == listees, (
            f"{nom}: le refus annonce {annoncee} issue(s) et en liste "
            f"{listees} -- {refus.value}")
        # Le plancher d'`EPIC11-ARB-89` : jamais UNE seule, jamais un mur.
        assert listees >= 2, f"{nom}: une seule issue -- {refus.value}"


def _projet_aux_rangs_de_master_EPUISES(tmp_path):
    """Un projet REEL dont une famille de masters a consomme les 98 rangs.

    Trois lots DISTINGUABLES et la cible en position MEDIANE (regle des
    fabriques) : le coeur balaie `manifest["lots"]`, et un projet mono-lot
    rendrait invisible un appariement fautif. Le lot de queue porte lui aussi
    un master, pour qu'un balayage tronque ne passe pas inapercu.
    """
    projet = tmp_path / "projet"
    project_layout.outputs_dir(projet).mkdir(parents=True)

    def _pose(nom, rang=None):
        (project_layout.outputs_dir(projet) / nom).write_bytes(
            b"master de mesure")
        entree = {"path": f"outputs/{nom}", "profile_id": "prores_422",
                  "frame_count": 1, "incomplete": False}
        if rang is not None:
            entree["version_rank"] = rang
        return entree

    famille = [_pose("L_24_mmu_prores_422.mov")]
    for rang in range(2, 100):
        famille.append(_pose(f"L_24_mmu_prores_422_v{rang}.mov", rang=rang))
    manifeste = {
        "schema_version": "2.1", "project_id": "projet-de-mesure",
        "created": "2026-09-05T00:00:00Z", "rushes": [{"rush_id": "R"}],
        "lots": [
            {"lot_id": "AUTRE_24", "rush_id": "R",
             "encoded_masters": [_pose("AUTRE_24_mmu_prores_422.mov")]},
            {"lot_id": "L_24", "rush_id": "R", "encoded_masters": famille},
            {"lot_id": "ENCORE_5", "rush_id": "R",
             "encoded_masters": [_pose("ENCORE_5_mmu_prores_422.mov")]},
        ],
    }
    (projet / "project.json").write_text(
        json.dumps(manifeste), encoding="utf-8")
    return projet, manifeste


def test_l_issue_du_refus_de_rangs_epuises_est_JOUABLE_de_bout_en_bout(tmp_path):
    """La mesure que la docstring d'a cote promettait, et qui n'existait pas.

    **Le regime est celui ou l'issue vaut le plus cher** : un operateur bute
    sur le dernier rang d'une famille de masters, et la seule chose qui le
    sorte de la est ce message. `EPIC11-ARB-89` exige alors DEUX issues, dont
    une non destructive -- << la rigueur de l'outil ne doit pas empecher une
    ecriture destructive CONSCIENTE >>, mais elle ne doit pas non plus la
    rendre obligatoire.

    Le geste mesure ici est celui de l'operateur, litteralement : la commande
    est EXTRAITE du refus lui-meme, jamais recopiee ici. Une frontiere qui
    comparerait deux chaines ecrites cote a cote refabriquerait le defaut du
    jour a un cran de plus -- c'est le piege du banc de synthese que
    `CLAUDE.md` decrit, et la couche 1 s'y est fait prendre sur sa propre
    premiere redaction.

    Trois choses sont exigees, et ce sont les trois de la regle : la commande
    se TAPE (elle sort du message), elle PARSE (code de sortie 0, ni le 2
    d'argparse ni le 1 d'un refus du coeur), et elle CHANGE quelque chose --
    le master quitte le disque ET le manifeste, le rang est rendu, et le
    resolveur qui refusait ne refuse plus.
    """
    from mixed_media_utility import cli

    projet, manifeste = _projet_aux_rangs_de_master_EPUISES(tmp_path)
    with pytest.raises(EncodeDecisionError) as refus:
        resolve_master_version_rank(
            manifeste, "L_24", profile_id="prores_422", container="mov")

    citations = re.findall(r"`mmu ([^`]+)`", str(refus.value))
    assert citations, f"le refus ne cite plus aucune commande: {refus.value}"
    argv = [
        "L_24" if jeton == "<id>" else "99" if jeton == "<rang>" else jeton
        for jeton in citations[0].split()
    ] + ["--project", str(projet)]
    assert "<" not in " ".join(argv), (
        f"un gabarit non substitue reste dans {argv}: l'issue a change de "
        "forme, la substitution de ce test doit suivre.")

    cible = (project_layout.outputs_dir(projet)
             / "L_24_mmu_prores_422_v99.mov")
    assert cible.is_file()
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
        code = cli.main(argv)
    assert code == 0, f"l'issue nommee rend {code}: {sortie.getvalue()}"

    # CHANGE quelque chose -- relu du DISQUE, jamais du document en memoire.
    assert not cible.exists(), "le master vise est toujours la"
    document = json.loads(
        (projet / "project.json").read_text(encoding="utf-8"))
    lot = next(l for l in document["lots"] if l["lot_id"] == "L_24")
    assert len(lot["encoded_masters"]) == 98
    assert all(entree["path"] != "outputs/L_24_mmu_prores_422_v99.mov"
               for entree in lot["encoded_masters"])
    # Les DEUX voisins sont intacts : une suppression qui emporterait le lot
    # de tete ou celui de queue rendrait le meme cardinal ici.
    for autre in ("AUTRE_24_mmu_prores_422.mov", "ENCORE_5_mmu_prores_422.mov"):
        assert (project_layout.outputs_dir(projet) / autre).is_file(), autre

    # Et le refus qui envoyait ici ne se declenche plus : la boucle se ferme.
    assert resolve_master_version_rank(
        document, "L_24", profile_id="prores_422", container="mov") == 99


# ---------------------------------------------------------------------------
# AC 4.3 et AC 4.5 -- LA LIGNE D'EAU SE POSE A LA CONSOMMATION, et le rang est
# renseigne. Mesure de bout en bout, par RELECTURE DU MANIFESTE : jamais par
# lecture du nom de fichier, qui dirait seulement ce que la fabrique de nom a
# fait, pas ce que le projet a appris.
# ---------------------------------------------------------------------------


def _encoder(project_dir, lot, *, nouvelle_version=False, ecraser=False):
    """Chaine reelle : `plan_encode` -> `execute_plan` -> `persist_encode`.

    Le manifeste est relu du DISQUE a chaque passe, comme la commande le fait :
    passer en memoire le document de la passe precedente masquerait qu'une
    ligne d'eau ecrite n'a pas ete persistee.
    """
    manifeste = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    plan = encode_module.plan_encode(
        project_dir, manifeste, lot_id=lot, nouvelle_version=nouvelle_version,
        overwrite=ecraser)
    swept = encode_module.prepare_output_directory(plan)
    resultat = encode_module.execute_plan(plan, swept=swept)
    em.persist_encode(project_dir, em.EncodeRecord.from_command_result(resultat))
    return plan


def _lot_relu(project_dir, lot):
    """Le lot tel que le DISQUE le porte apres la passe."""
    document = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    return next(l for l in document["lots"] if l.get("lot_id") == lot)


def test_la_ligne_d_eau_d_un_master_se_pose_a_la_CONSOMMATION(tmp_path):
    """Le defaut central de la story 11.8, et il etait exactement inverse.

    `masters_version_watermark` n'etait ecrite que par `project_maintenance`,
    c'est-a-dire par le chemin de SUPPRESSION -- et par aucun chemin
    d'ecriture. C'etait un champ lu par un resolveur que personne n'appelait et
    ecrit par le seul chemin qui retire. `CLAUDE.md` demande l'inverse : « la
    ligne d'eau se pose au retrait, PAS SEULEMENT a la consommation ».

    Mesure ici sur les deux rangs successifs, par relecture du manifeste.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)

    premier = _encoder(project_dir, LOT)
    cle = premier.masters_family_key
    lot = _lot_relu(project_dir, LOT)
    assert lot[em.MASTERS_WATERMARK_FIELD] == {cle: 1}, (
        "le rang d'origine ne pose aucune ligne d'eau : une suppression du "
        "master v1 relancerait alors la famille au rang 1, sous un nom deja "
        "livre"
    )
    # AC 4.5, versant « omis au rang 1 » : le champ est absent de l'entree.
    entree = lot[em.MASTER_INVENTORY_FIELD][0]
    assert em.MASTER_VERSION_RANK_FIELD not in entree
    assert "_v" not in Path(entree["path"]).name.replace("_mmu_", "")

    second = _encoder(project_dir, LOT, nouvelle_version=True)
    assert second.master_version_rank == 2
    lot = _lot_relu(project_dir, LOT)
    assert lot[em.MASTERS_WATERMARK_FIELD] == {cle: 2}, (
        "apres une ecriture de rang 2, la ligne d'eau de la famille vaut 2"
    )
    # Le master d'origine est INTACT : c'est ce que `--nouvelle-version` achete.
    chemins = sorted(e["path"] for e in lot[em.MASTER_INVENTORY_FIELD])
    assert len(chemins) == 2
    for chemin in chemins:
        assert (project_dir / chemin).is_file()
    # AC 4.5, versant « renseigne a partir du rang 2 ».
    par_chemin = {e["path"]: e for e in lot[em.MASTER_INVENTORY_FIELD]}
    versionne = par_chemin[
        em.master_relative_path(project_dir, second.output_path)]
    assert versionne[em.MASTER_VERSION_RANK_FIELD] == 2
    assert versionne["path"].endswith("_v2.mov")
    validate_manifest(project_dir / "project.json")


def test_ECRASER_L_ORIGINE_ne_fait_pas_REDESCENDRE_la_ligne_d_eau(tmp_path):
    """Le plancher de `_poser_la_ligne_d_eau_des_masters`, et il est CHARGE.

    **Trouve par la couche 3 de la revue du 2026-09-03 comme un SURVIVANT** :
    remplacer `max(posee, rang_ecrit)` par la seule affectation `rang_ecrit`
    survivait aux sept fichiers de test qui touchent
    `masters_version_watermark`. Le champ etait ecrit, relu, compare -- et
    aucun banc ne distinguait le code du depot d'une version sans plancher.

    **Le regime ou il mord est atteignable, et il a ete mesure avant d'ecrire
    ce test** : `--overwrite` reecrit l'ORIGINE (rang rendu `None`, donc 1),
    pas le dernier rang. Apres deux `--nouvelle-version`, la ligne d'eau vaut
    donc 3 pendant qu'on ecrit un rang 1.

    Ce que le plancher retire ferait : la ligne d'eau retomberait a 1, la
    version suivante repartirait au rang 2 -- et `_v2.mov` existe deja sur le
    disque. C'est-a-dire un nom deja livre repris, donc l'ecrasement silencieux
    que le versionnage existe pour ecarter (`EPIC11-ARB-104`), atteint par le
    chemin meme qui devait le prevenir.

    **La consequence est mesuree, pas seulement le champ** : asserter la seule
    ligne d'eau dirait qu'un entier n'a pas bouge ; ce qui compte est que le
    rang PROPOSE ensuite ne collisionne avec aucun fichier existant.

    Meme famille que ce qu'`EPIC11-ARB-108` a fait fermer le 2026-08-31 sur
    `project_maintenance.py` -- **sur ce meme champ**, et par l'autre bout :
    la, un retrait rendait un rang sans qu'on le demande ; ici, une ecriture
    le rendrait.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)
    premier = _encoder(project_dir, LOT)
    cle = premier.masters_family_key
    _encoder(project_dir, LOT, nouvelle_version=True)
    _encoder(project_dir, LOT, nouvelle_version=True)
    assert _lot_relu(project_dir, LOT)[em.MASTERS_WATERMARK_FIELD] == {cle: 3}

    # `--overwrite` vise l'ORIGINE : le rang rendu est `None`, donc 1.
    ecrase = _encoder(project_dir, LOT, ecraser=True)
    assert ecrase.master_version_rank is None, (
        "le regime de ce test suppose que l'ecrasement vise l'origine ; s'il "
        "visait le dernier rang, la ligne d'eau ne pourrait pas redescendre "
        "et ce banc ne mesurerait plus rien")
    assert _lot_relu(project_dir, LOT)[em.MASTERS_WATERMARK_FIELD] == {cle: 3}, (
        "ecraser l'origine a fait REDESCENDRE la ligne d'eau de la famille")

    # La consequence, et c'est elle qui fait de ce test autre chose qu'une
    # comparaison d'entier : le rang suivant ne reprend AUCUN nom deja livre.
    manifeste = json.loads(
        (project_dir / "project.json").read_text(encoding="utf-8"))
    suivant = encode_module.plan_encode(
        project_dir, manifeste, lot_id=LOT, nouvelle_version=True)
    assert suivant.master_version_rank == 4, suivant.master_version_rank
    assert not Path(suivant.output_path).exists(), (
        f"le rang propose reprend un fichier existant : {suivant.output_path}")


def test_une_PREMIERE_version_demandee_sur_une_famille_VIERGE_reste_a_l_ORIGINE(
        tmp_path):
    """AC 4.5, le versant que rien ne mesurait -- **trouve par mutation** (M3).

    `plan_encode` porte, en toutes lettres, la garde
    `None if rang == RANG_ORIGINE else rang` et un commentaire qui la motive :
    << demander une nouvelle version d'une famille qui n'a encore aucun master
    n'est pas une erreur -- il n'y a simplement rien a versionner >>. Le
    remplacer par le seul `rang` survivait aux 42 tests de ce banc.

    **Le regime manquant est celui-ci, et il est ordinaire** : `--nouvelle-
    version` passe sur un lot qui n'a encore AUCUN master. Aucun des trois
    bancs de bout en bout ne le jouait -- tous encodaient d'abord une origine
    sans le drapeau, si bien que le rang resolu valait toujours 2 ou plus, et
    que la branche du rang 1 n'etait jamais prise.

    Ce que le mutant fait, mesure : le rang 1 part vers
    `format_version_suffix`, qui le refuse NOMMEMENT (le rang d'origine ne
    porte aucun fragment de nom, `EPIC11-ARB-88`), et la `ValueError` remonte
    nue -- une trace Python devant l'operateur sur un geste parfaitement
    legitime. Le drapeau qui existe pour eviter une destruction ferait planter
    la commande sur le cas ou il n'y a rien a detruire.

    Trois faits sont asserts, et pas seulement l'absence de plantage : le rang
    du plan, le NOM ecrit, et ce que le manifeste a appris.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)
    plan = _encoder(project_dir, LOT, nouvelle_version=True)

    assert plan.master_version_rank is None, (
        "une famille vierge n'a rien a versionner : le rang reste l'origine, "
        "et l'origine ne porte AUCUN fragment de nom")
    assert "_v" not in Path(plan.output_path).name.replace("_mmu_", ""), (
        f"le nom porte un fragment de rang : {plan.output_path}")

    lot = _lot_relu(project_dir, LOT)
    entree = lot[em.MASTER_INVENTORY_FIELD][0]
    assert em.MASTER_VERSION_RANK_FIELD not in entree, entree
    # Et la ligne d'eau monte quand meme a 1 : le premier master EMPLOIE un
    # rang, meme s'il ne l'ecrit pas. Sans cela, la version demandee apres une
    # suppression de cette origine repartirait au rang 1 sous un nom livre.
    assert lot[em.MASTERS_WATERMARK_FIELD] == {plan.masters_family_key: 1}
    validate_manifest(project_dir / "project.json")


def test_afficher_un_rang_ne_le_CONSOMME_pas(tmp_path):
    """AC 4.4, et sans elle ouvrir trois fois l'ecran de conflit ferait sauter
    de `v2` a `v5`.

    Trois montages, trois annulations : `plan_encode` decide tout et n'ecrit
    rien, donc la ligne d'eau reste ou elle etait ET le rang propose reste le
    MEME. Les deux assertions sont necessaires : une ligne d'eau figee sur un
    rang qui monterait quand meme dirait que le rang vient d'ailleurs.
    """
    from test_encode_command import LOT, scanned_project

    project_dir, _ = scanned_project(tmp_path)
    premier = _encoder(project_dir, LOT)
    avant = dict(_lot_relu(project_dir, LOT)[em.MASTERS_WATERMARK_FIELD])
    assert avant == {premier.masters_family_key: 1}

    rangs = []
    for _ in range(3):
        manifeste = json.loads(
            (project_dir / "project.json").read_text(encoding="utf-8"))
        # Monter l'ecran de conflit, c'est resoudre le rang -- puis annuler,
        # c'est jeter le plan sans jamais appeler `execute_plan`.
        plan = encode_module.plan_encode(
            project_dir, manifeste, lot_id=LOT, nouvelle_version=True)
        rangs.append(plan.master_version_rank)
        del plan

    assert rangs == [2, 2, 2], f"un rang a ete consomme par un affichage: {rangs}"
    assert _lot_relu(project_dir, LOT)[em.MASTERS_WATERMARK_FIELD] == avant
    assert not (project_dir / project_layout.OUTPUTS_DIRNAME
                / f"{LOT}_mmu_prores_422_v2.mov").exists()
