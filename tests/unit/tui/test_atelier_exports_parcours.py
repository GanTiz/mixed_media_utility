# -*- coding: utf-8 -*-
"""Story 11.8, lot B5 -- le PARCOURS de l'atelier Exports, de bout en bout.

**Ce banc et lui seul mesure le cablage.** Les six bancs d'ecran de cet
atelier mesurent chacun leur ecran monte a la main, avec un rappel que le banc
fournit lui-meme. Le cablage est precisement ce qui manque quand tous ces
bancs sont verts -- c'est le motif d'existence de `test_rappels_cables.py`, et
ce banc-ci en est le pendant positif : la garde structurelle dit qu'un rappel
**est** injecte, celui-ci dit **ou il mene**.

Ce qu'aucun banc d'ecran ne peut voir, et que celui-ci mesure :

* l'**ordre** des ecrans, en ensemble exact et ordonne -- « la confirmation se
  monte » reste vrai qu'elle vienne avant ou apres le conflit de version, et
  c'est precisement ce qu'`EPIC11-ARB-172` tranche ;
* l'ensemble **exact** des situations qui descendent sur `E4-3b`, dans les deux
  sens : un refus de plus qui y menerait et le refus attendu qui n'y menerait
  plus font rougir tous les deux ;
* l'ensemble **exact** des mots-cles transmis au coeur (AC 2.4), lu de
  `encode_master.MOTS_CLES_DE_LA_DECISION` et jamais recopie ;
* l'AC 4.4 **a travers le parcours** : trois montages du conflit annules ne
  consomment aucun rang ;
* `T6-1` : une interruption retenue n'appelle pas le coeur, ne monte pas
  `E4-5`, et laisse le manifeste **octet pour octet** tel qu'il etait ;
* les deux issues de `E4-5` -- `Encoder un autre lot` et `Retour aux ateliers`
  -- qui etaient **indiscernables** tant que `E4-1` n'etait pas branche.

**Regle des fabriques** (`CLAUDE.md`), et c'est le lot ou elle mord le plus :
un parcours EST une suite ordonnee d'ecrans, et un lot de trois ecrans dont la
cible est en second la place aussi en dernier.

1. **trois lots, la cible AU MILIEU** -- ni en tete, ce qui laisserait vivre un
   `lots[0]`, ni en queue, ce qui laisserait vivre un `continue` -> `break` ;
2. **des valeurs distinguables** -- trois cardinaux de frames differents, trois
   identifiants differents, et **un seul** des trois porte un master deja
   ecrit : un remplissage uniforme rendrait toute permutation invisible ;
3. **l'ordre du manifeste n'est pas l'ordre alphabetique** -- `E4-1` rend les
   lots dans l'ordre de `lots[]` (AC 5.1, « ne filtre pas, n'ajoute pas et ne
   retrie pas »), et une fabrique deja triee ne verrait pas la difference.

**Aucun test de ce banc ne mesure une horloge** : `horloge` est donnee, et la
duree d'encodage affichee par `E4-5` est un ecart de deux valeurs fournies.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import codec_profiles, encode, encode_master
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import encode_manifest, naming
from mixed_media_utility.tui import (
    atelier_exports_confirmation as confirmation,
    atelier_exports_execution as execution_exports,
    atelier_exports_lot as lots_exports,
    atelier_exports_parcours as parcours_exports,
    atelier_exports_reglages as reglages_exports,
    atelier_exports_resultat as resultat_exports,
    atelier_exports_versions as versions,
    projet_lecture,
)
from mixed_media_utility.tui.atelier_extraction_ecriture import chaine_du_produit
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import EcranRefus

PROJET = "projet_demo"
RUSH = "plan-04"
LARGEUR, HAUTEUR = 1920, 1080
CADENCE_EXACTE = "25/1"

#: **TROIS lots, et la cible est AU MILIEU.** Les noms sont choisis pour que
#: l'ordre du manifeste ne soit PAS l'ordre alphabetique -- sans quoi « l'ordre
#: est celui du manifest » et « l'ordre est trie » seraient indiscernables, et
#: un `sorted` gliss dans le rendu resterait invisible.
#:
#: Et ils sont choisis plus finement que ca : un tri ne se contente pas de
#: reordonner la liste, il **deplace la cible** (index 1 au manifeste, index 2
#: une fois triee). Une fabrique ou le tri laisse la cible en place mesurerait
#: bien moins, puisque tous les tests qui visent la cible par sa position
#: passeraient encore.
#:
#:   manifeste : mm-premier_5, plan-04_12p5, aa-dernier_2   (cible en 1)
#:   triee     : aa-dernier_2, mm-premier_5, plan-04_12p5   (cible en 2)
LOT_PREMIER = "mm-premier_5"
LOT_CIBLE = "plan-04_12p5"
LOT_DERNIER = "aa-dernier_2"

#: L'ordre dans lequel `E4-1` doit les rendre : celui de `lots[]`.
ORDRE_DU_MANIFESTE = (LOT_PREMIER, LOT_CIBLE, LOT_DERNIER)

#: Trois cardinaux **tous differents**. Un remplissage uniforme rendrait toute
#: permutation invisible -- c'est le mutant `M33` de la story 5.6.
FRAMES = {LOT_PREMIER: 40, LOT_CIBLE: 63, LOT_DERNIER: 124}

#: **Un seul lot porte un master deja ecrit, et c'est la cible.** Deux lots qui
#: en porteraient un rendraient « le conflit du lot designe » et « le conflit du
#: premier lot qui en a un » indiscernables.
LIGNE_D_EAU_DE_LA_CIBLE = 2

#: La phrase du refus de conflit. Elle voyage **verbatim** jusqu'a l'operateur
#: (`EPIC11-ARB-30`), et un test la compare a ce que l'ecran affiche.
MESSAGE_DU_CONFLIT = "Le master existe deja : le remplacer ou en versionner un autre."
MESSAGE_DU_LOT_INCOMPLET = "Le lot est incomplet : 60 frames sur 63 attendues."


# ---------------------------------------------------------------------------
# Fabriques -- le projet, son manifeste, ses frames, son master present
# ---------------------------------------------------------------------------

def _lot(lot_id: str) -> dict:
    return {
        "lot_id": lot_id,
        "rush_id": RUSH,
        # Lu du coeur, jamais recopie : c'est l'etat minimum admis.
        "state": encode.MINIMUM_LOT_STATE,
        "fps_target": 12.5,
        "timecode_base_fps": CADENCE_EXACTE,
        "expected_frame_count": FRAMES[lot_id],
        "output_frames_dir": f"output-frames/{lot_id}",
        "output_bit_depth": 16,
    }


def _manifeste() -> dict:
    return {
        "schema_version": "2.1",
        "project_id": PROJET,
        "rushes": [{"rush_id": RUSH,
                    "resolution_source": {"width": LARGEUR,
                                          "height": HAUTEUR}}],
        # **L'ordre du manifeste n'est pas l'ordre alphabetique.**
        "lots": [_lot(LOT_PREMIER), _lot(LOT_CIBLE), _lot(LOT_DERNIER)],
    }


def nom_du_master(lot_id: str, rang: int | None = None) -> str:
    """Le nom que la convention du depot donne. **Jamais tape a la main.**"""
    return naming.build_master_filename(
        lot_id=lot_id, profile_id=codec_profiles.DEFAULT_PROFILE_ID,
        container=codec_profiles.PROFILES[
            codec_profiles.DEFAULT_PROFILE_ID].container,
        version_rank=rang)


def _poser_le_master_present(dossier: Path, manifeste: dict) -> dict:
    """Declarer un master deja ecrit sur la CIBLE, et lui seul.

    L'inventaire et la **ligne d'eau** partent ensemble : un rang consomme sans
    ligne d'eau posee est la surface morte que la revue du 2026-08-31 a
    trouvee sur quatre champs sur cinq.
    """
    for lot in manifeste["lots"]:
        if lot["lot_id"] != LOT_CIBLE:
            continue
        inventaire = []
        for rang in [None] + list(range(2, LIGNE_D_EAU_DE_LA_CIBLE + 1)):
            nom = nom_du_master(LOT_CIBLE, rang)
            entree = {encode_manifest.MASTER_INVENTORY_KEY: f"masters/{nom}",
                      "frame_count": FRAMES[LOT_CIBLE]}
            if rang is not None:
                entree[encode_manifest.MASTER_VERSION_RANK_FIELD] = rang
            inventaire.append(entree)
            (dossier / "masters" / nom).write_bytes(b"\0" * 4096)
        lot[encode_manifest.MASTER_INVENTORY_FIELD] = inventaire
        lot[encode_manifest.MASTERS_WATERMARK_FIELD] = {
            encode.cle_de_famille_de_master(
                codec_profiles.DEFAULT_PROFILE_ID, None):
            LIGNE_D_EAU_DE_LA_CIBLE}
    return manifeste


def projet(tmp_path, *, avec_master: bool = False,
           lots: tuple[str, ...] = ORDRE_DU_MANIFESTE) -> Path:
    """Un projet reel : ses dossiers de frames sur le disque, son manifeste.

    Les frames sont **posees**, parce que `encode.check_lot_admission` -- que
    `E4-1` appelle par `list_encodable_lots` -- exige le dossier present. Un
    lot dont le dossier manque est saute, et la liste serait alors plus courte
    que la fabrique ne le croit.
    """
    chemin = creer_projet(tmp_path, PROJET).chemin
    (chemin / "masters").mkdir(parents=True, exist_ok=True)
    manifeste = _manifeste()
    manifeste["lots"] = [lot for lot in manifeste["lots"]
                         if lot["lot_id"] in lots]
    for lot in manifeste["lots"]:
        dossier = chemin / lot["output_frames_dir"]
        dossier.mkdir(parents=True, exist_ok=True)
        for rang in range(FRAMES[lot["lot_id"]]):
            (dossier / f"frame_{RUSH}_12p5_{rang:08d}.tiff").write_bytes(b"II*\0")
    if avec_master:
        _poser_le_master_present(chemin, manifeste)
    (chemin / "project.json").write_text(json.dumps(manifeste),
                                         encoding="utf-8")
    return chemin


def projet_sans_lot(tmp_path) -> Path:
    chemin = creer_projet(tmp_path, PROJET).chemin
    manifeste = _manifeste()
    manifeste["lots"] = []
    (chemin / "project.json").write_text(json.dumps(manifeste),
                                         encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# Les doubles du coeur -- ils TRACENT, et c'est ce qui rend l'ordre mesurable
# ---------------------------------------------------------------------------

def plan_de(dossier_projet: Path, *, lot_id: str, profile_id: str,
            resolution: str, nouvelle_version: bool, overwrite: bool,
            **_reste) -> encode.EncodePlan:
    """Un `encode.EncodePlan` **reel**, construit par son constructeur.

    Pas une classe de circonstance : `plan_du_master` et
    `PassageDeLEncodage.du_plan` lisent une quinzaine de ses champs, et un
    faux objet qui n'en porterait que douze ferait passer ce banc au vert sur
    un parcours qui casserait en production au treizieme.
    """
    cible = encode.resolve_output_resolution(resolution)
    cible = encode.TargetResolution(
        requested=cible.requested, origin=cible.origin,
        resolution_id=cible.resolution_id,
        size=cible.size or (LARGEUR, HAUTEUR))
    rang = (LIGNE_D_EAU_DE_LA_CIBLE + 1) if nouvelle_version else None
    if overwrite and lot_id == LOT_CIBLE:
        # L'ecrasement vise le master **present**, c'est-a-dire le dernier
        # rang consomme -- pas un rang neuf.
        rang = LIGNE_D_EAU_DE_LA_CIBLE
    nom = nom_du_master(lot_id, rang)
    frames = tuple(Path(f"f{rang_de_frame}.tiff")
                   for rang_de_frame in range(FRAMES[lot_id]))
    return encode.EncodePlan(
        project_dir=Path(dossier_projet), lot_id=lot_id,
        lot_state=encode.MINIMUM_LOT_STATE, profile_id=profile_id,
        container=codec_profiles.PROFILES[profile_id].container,
        resolution=cible, source_size=(LARGEUR, HAUTEUR),
        frame_paths=frames, frame_rate=12.5, exact_frame_rate="25/2",
        timecode=encode.TimecodePlan(emitted="00:00:00:00"),
        verdict=encode.CompletenessVerdict(
            expected=FRAMES[lot_id], found=FRAMES[lot_id],
            synthetic_present=(), synthetic_missing=(), missing_pages=(),
            complete=True),
        container_tags={}, output_path=Path(dossier_projet) / "masters" / nom,
        overwrite=overwrite, muxed_frame_paths=frames * 2,
        master_version_rank=rang)


class PlanificateurDouble:
    """Double de `encode.plan_encode` qui **trace ses decisions**.

    Il tient lieu de la seule redaction du depot de « la destination est-elle
    libre ? » : le vrai `plan_encode` sonde chaque frame par `ffprobe`, ce
    qu'un banc TUI n'a pas a payer. Ce qui est mesure ici n'est pas sa
    decision -- elle est mesuree au coeur -- mais **ce que le parcours en
    fait**, et c'est pourquoi le refus qu'il leve est parametrable.

    **Il n'ecrit rien, et c'est le point de l'AC 4.4** : trois montages de
    `E4-3b` l'appellent jusqu'a sept fois sans que la ligne d'eau bouge.
    """

    def __init__(self, *, avec_master: frozenset[str] = frozenset(),
                 refus: tuple[str, str] | None = None) -> None:
        self.avec_master = set(avec_master)
        self.refus = refus
        self.appels: list[dict] = []

    def __call__(self, dossier_projet, manifeste, **decision):
        self.appels.append(dict(decision))
        if (self.refus is not None
                and not decision["nouvelle_version"]
                and not decision["overwrite"]):
            # Le refus parametrable porte sur la DECISION NUE, pas sur les
            # variantes.
            #
            # **Un double qui refuse tout, refuse aussi les sondes.** Devant
            # `MASTER_DEJA_PRESENT`, le parcours n'affiche pas le conflit sur
            # le seul code : il redemande au planificateur ce que donneraient
            # `nouvelle_version` et `overwrite`, parce que les issues offertes
            # doivent etre celles que le coeur sait servir (AC 8.2). Un
            # `raise` inconditionnel faisait donc echouer ces deux sondes, et
            # le parcours retombait sur l'ecran de refus -- ce qui rendait
            # l'ensemble des refus menant a `E4-3b` VIDE, alors que le
            # routage etait bon.
            #
            # Refuser la seule decision nue est aussi le comportement du vrai
            # `plan_encode` : chacun des trois codes mesures ici refuse la
            # decision nue, et deux d'entre eux ne disent rien des variantes.
            raise encode.EncodeDecisionError(*self.refus)
        if (decision["lot_id"] in self.avec_master
                and not decision["nouvelle_version"]
                and not decision["overwrite"]):
            raise encode.EncodeDecisionError(
                encode.ENCODE_MASTER_ALREADY_PRESENT, MESSAGE_DU_CONFLIT)
        return plan_de(dossier_projet, **decision)


@dataclass
class _Issue:
    output_path: Path
    frame_count: int
    frame_rate: float
    timecode: str | None


@dataclass
class _Resultat:
    plan: Any
    outcome: _Issue
    findings: tuple = ()
    verification: dict = field(default_factory=dict)


@dataclass
class _Persisted:
    lot_id: str
    state_written: str
    findings: tuple = ()


class CoeurDouble:
    """Double de `encode_master.encoder_le_master_du_lot`, qui **trace**.

    Sa signature ne porte **aucun** `rappel_progression` : c'est celle du
    coeur d'aujourd'hui, et c'est ce qui fait que `raccord_de_progression`
    rend `{}`. Le double symetrique -- celui qui l'accepte -- est
    :class:`CoeurQuiCompte`, et les deux ensemble mesurent la jonction
    d'`EPIC11-ARB-184` dans ses **deux** etats.
    """

    def __init__(self, *, leve: BaseException | None = None) -> None:
        self.leve = leve
        self.appels: list[dict] = []

    def __call__(self, dossier_projet, *, logger=None, **decision):
        self.appels.append(dict(decision))
        if self.leve is not None:
            raise self.leve
        plan = plan_de(Path(dossier_projet), **decision)
        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        plan.output_path.write_bytes(b"\0" * 2048)
        if logger is not None:
            logger.info("master ecrit : %s", plan.output_path.name)
        return encode_master.MasterDuLot(
            resultat=_Resultat(plan=plan, outcome=_Issue(
                output_path=plan.output_path,
                frame_count=len(plan.muxed_frame_paths),
                frame_rate=plan.frame_rate,
                timecode=plan.timecode.emitted)),
            persisted=_Persisted(lot_id=decision["lot_id"],
                                 state_written="encode"),
            recapitulatif="")


class CoeurQuiCompte(CoeurDouble):
    """Le meme, mais sa signature **accepte** le rappel de progression.

    Il joue le coeur du jour ou la story 6.7 posera le mot-cle. Rien de `tui/`
    ne doit changer ce jour-la, et c'est cela qui se mesure : le meme parcours,
    inchange, doit alors **poser** le mot-cle et le compteur avancer.
    """

    def __call__(self, dossier_projet, *, logger=None,
                 rappel_progression=None, **decision):
        self.progression: list[tuple[int, int]] = getattr(
            self, "progression", [])
        if rappel_progression is not None:
            for rang in range(1, 4):
                rappel_progression(rang, 3)
                self.progression.append((rang, 3))
        return super().__call__(dossier_projet, logger=logger, **decision)


# ---------------------------------------------------------------------------
# Le banc : une application montee, et un espion sur les ecrans empiles
# ---------------------------------------------------------------------------

def _app(**kwargs) -> CoqueTui:
    """La coque du banc, avec la pile de paliers que le PRODUIT construit.

    **Deux paliers et non un, et ce n'est pas une fabrique plus riche pour le
    plaisir.** `CoqueTui.rang` compte les paliers non transitoires de la pile,
    et `RANG_DES_ATELIERS` vaut 1 : le menu des ateliers est le palier 1, et
    `E4-1` se monte AU-DESSUS de lui. Avec un palier unique, `E4-1` arrivait
    au rang 1 lui-meme, si bien que `revenir_aux_ateliers()` -- qui depile
    tant que `rang > RANG_DES_ATELIERS` -- s'arretait sur la liste des lots.
    Les deux issues de `E4-5` devenaient alors indiscernables **par la forme
    de la pile du banc**, pas par un defaut du produit : c'est la mesure qui
    etait fausse, et elle accusait le code.

    Le cran qui manquait est le meme que celui des bancs de l'atelier Scan
    (`test_frontieres_et_grille_scan_temps_2.py`) : le `descendre()` de
    `_jusqu_aux_reglages`, qui monte le menu avant que l'atelier s'ouvre.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir  Q quitter"),
                             PalierTemoin("Ateliers",
                                          "⏎ entrer  Échap projet  Q quitter")],
                    contexte=Contexte(projet=PROJET), **kwargs)


#: Le cran d'entree du banc -- le `descendre()` sans argument qui monte le menu
#: des ateliers sous l'atelier (voir `_app`). Il est ENREGISTRE par l'espion
#: plutot que filtre : un filtre laisserait passer une descente a l'aveugle du
#: parcours lui-meme, qui est justement ce qu'une liste exacte doit attraper.
#: Il ouvre donc les deux sequences attendues, nomme.
CRAN_DU_MENU = "(remontee)"


def _espionner(app) -> list[str]:
    """Les noms des ecrans empiles, **dans l'ordre**.

    L'ensemble ordonne est la seule mesure qui attrape une inversion : « la
    confirmation se monte » reste vrai qu'elle vienne avant ou apres le
    conflit, et c'est ce qu'`EPIC11-ARB-172` tranche.
    """
    vus: list[str] = []
    vrai = app.descendre

    def descendre(palier=None):
        vus.append(CRAN_DU_MENU if palier is None
                   else type(palier).__name__)
        return vrai(palier)

    app.descendre = descendre
    return vus


#: Le depart et la duree de la passe, pour l'horloge du banc. Nommes plutot
#: qu'ecrits en litteral : la duree attendue se lit ici ET a l'assertion, si
#: bien qu'aucun des deux ne peut deriver sans l'autre.
DEPART_DE_LA_PASSE = 100.0
DUREE_DE_LA_PASSE = 42.5


def _horloge_de_la_passe():
    """Une horloge a DEUX temps : le depart, puis tout l'apres.

    Elle rend `DEPART_DE_LA_PASSE` a son PREMIER appel -- celui que
    `chronometre` fait a son montage -- puis l'arrivee a tous les suivants.

    **Une liste d'instants ne tenait pas, et le defaut etait vif** : elle
    depend du NOMBRE d'appels, et le `100.0` ecrit deux fois en tete faisait
    lire le depart aux deux appels du chronometre (montage puis lecture), donc
    une duree de **0,0 s** sur une passe qui avait dure. Symetriquement, une
    liste trop courte se tarit des qu'un chemin lit le chronometre une fois de
    plus, et la duree devient fausse dans l'autre sens. Deux temps nommes ne
    dependent d'aucun compte d'appels.
    """
    depart = iter([DEPART_DE_LA_PASSE])
    arrivee = DEPART_DE_LA_PASSE + DUREE_DE_LA_PASSE
    return lambda: next(depart, arrivee)


def _parcours(app, dossier, *, coeur=None, planificateur=None, **reglages):
    return parcours_exports.ParcoursExports(
        app, dossier, encoder=coeur,
        planifier=planificateur if planificateur is not None
        else PlanificateurDouble(),
        horloge=_horloge_de_la_passe(), **reglages)


def _viser(choix, cle: str) -> None:
    """Amener le curseur du choix exclusif sur une issue, **au clavier**.

    Jamais par un `curseur = k` ecrit ici : ce qu'on mesure est ce qu'un
    operateur obtient de ses fleches, et poser l'indice sauterait la
    navigation qu'on croit mesurer.

    **Le pas se choisit dans la direction de la cible, et ce n'est pas un
    detail de confort.** `panneau.ChoixExclusif.deplacer` BORNE le curseur
    (`min(max(...), len-1)`) au lieu de l'enrouler -- c'est voulu, une fleche
    qui repasse par le debut ferait d'un maintien de touche une roulette. Un
    balayage en `+1` seul ne peut donc jamais REMONTER, et comme
    `EPIC11-ARB-7` pose le curseur d'arrivee sur la seule issue qui n'ecrit
    rien -- la DERNIERE de ces trois ecrans -- il n'atteignait aucune des
    issues ecrivantes. C'est ce qui rendait quatorze bancs rouges sur un
    message qui disait « issue absente » en affichant une liste qui la
    contenait.
    """
    cles = [issue.cle for issue in choix.issues]
    if cle not in cles:
        raise AssertionError(f"issue {cle!r} absente : {cles}")
    pas = 1 if cles.index(cle) > choix.curseur else -1
    for _ in range(len(cles)):
        if choix.issues[choix.curseur].cle == cle:
            return
        choix.deplacer(pas)
    raise AssertionError(
        f"le curseur n'a pas atteint {cle!r} en {len(cles)} pas depuis "
        f"{choix.issues[choix.curseur].cle!r} : {cles}")


class _Touche:
    """Evenement de touche minimal, sur le modele du banc du lot G."""

    def __init__(self, touche: str) -> None:
        self.key = touche
        self.arrete = False

    def stop(self) -> None:
        self.arrete = True


def _viser_la_suite(ecran, suite: str | None) -> None:
    """Amener le curseur de `E4-5` sur une suite, **aux fleches seules**.

    `E4-5` n'est pas un `ChoixExclusif` et n'a donc pas de `.choix` : il porte
    ses quatre suites en `.suites` (des chaines) avec son propre `.curseur`,
    et il se pilote par `on_key`. C'est le sous-classement d'`EcranResultat`
    que le lot G a livre, et c'est ce que son banc emprunte -- ce banc-ci
    supposait la forme des deux ecrans de conflit, qui n'est pas la sienne.

    `suite=None` designe `Retour aux ateliers`, l'issue qu'`EcranResultat`
    ajoute lui-meme **en dernier** : on ne la recopie pas ici, on la vise par
    sa position de queue.

    On remonte d'abord en tete plutot que de partir du curseur d'ouverture :
    la mesure ne doit pas dependre de l'endroit ou l'ecran s'ouvre, sans quoi
    un changement de curseur d'arrivee deplacerait toutes les cibles en
    silence.
    """
    suites = list(ecran.suites)
    cible = len(suites) - 1 if suite is None else suites.index(suite)
    for _ in range(len(suites)):
        ecran.on_key(_Touche("up"))
    for _ in range(cible):
        ecran.on_key(_Touche("down"))
    assert ecran.curseur == cible, (ecran.curseur, cible, suites)


async def _jusqu_aux_reglages(pilote, parcours, lot_id: str):
    """`E4-1` ouvert, un lot designe, `E4-2` monte -- **au clavier**.

    Le `descendre()` d'entree monte le **menu des ateliers**, palier 1, sous
    l'atelier : c'est la pile du produit. Sans lui, `E4-1` occuperait le rang
    des ateliers et le retour du resultat y atterrirait -- voir `_app`.
    """
    pilote.app.descendre()
    await pilote.pause()
    ecran = parcours.ouvrir()
    await pilote.pause()
    ecran.liste.viser(lot_id)
    ecran.traiter("enter")
    await pilote.pause()
    return pilote.app.screen


async def _valider_les_reglages(pilote):
    """`⏎` sur `E4-2`. Les reglages d'ouverture sont ceux du coeur."""
    ecran = pilote.app.screen
    ecran.traiter("enter")
    await pilote.pause()
    return pilote.app.screen


# ===========================================================================
# La fabrique tient-elle ce que la regle exige ?
# ===========================================================================

def test_la_fabrique_place_la_cible_AU_MILIEU_et_distingue_ses_trois_lots(
        tmp_path):
    """Mesuree, pas promise -- c'est le point 3 de la regle des fabriques.

    La position se verifie **sur la liste que le code parcourt**, c'est-a-dire
    celle que `ListeDesLotsAEncoder.depuis_le_coeur` rend, et non sur la
    constante ecrite plus haut.
    """
    dossier = projet(tmp_path, avec_master=True)
    manifeste = projet_lecture.lire_manifeste(dossier)
    liste = lots_exports.ListeDesLotsAEncoder.depuis_le_coeur(manifeste,
                                                              dossier)
    noms = [lot.lot_id for lot in liste.lots]
    assert len(noms) == 3, noms
    assert noms.index(LOT_CIBLE) == 1, noms
    assert noms != sorted(noms), (
        "l'ordre du manifeste doit differer de l'ordre alphabetique, sans quoi "
        f"« ordre du manifest » et « ordre trie » sont indiscernables : {noms}")
    assert len(set(FRAMES.values())) == 3, FRAMES
    porteurs = [lot["lot_id"] for lot in manifeste["lots"]
                if lot.get(encode_manifest.MASTER_INVENTORY_FIELD)]
    assert porteurs == [LOT_CIBLE], porteurs


# ===========================================================================
# La porte : le menu des ateliers mene a `E4-1`, et plus a « pas encore »
# ===========================================================================

def test_le_menu_des_ateliers_MENE_a_E4_1_et_plus_a_un_ecran_pas_encore(
        tmp_path, banc):
    """AC 5.1 et `EPIC11-ARB-28` : **aucun menu d'atelier ne s'intercale**.

    **Un `EcranPasEncore` qui survit au cablage est un mensonge a l'ecran** :
    il dit « pas encore construit » d'un atelier livre.
    """
    dossier = projet(tmp_path)
    chaine = chaine_du_produit()
    vus = _espionner(chaine.app)

    async def scenario(pilote):
        chaine.ouvrir(dossier)
        await pilote.pause()
        entrees = {entree.nom: entree for entree in chaine.menu.entrees}
        chaine.menu.entrer(entrees[projet_lecture.EXPORTS])
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(chaine.app, scenario)
    assert isinstance(ecran, lots_exports.EcranDesLotsAEncoder), type(ecran)
    assert EcranPasEncore.__name__ not in vus, vus


def test_l_atelier_Exports_est_INJECTE_par_la_chaine_du_PRODUIT():
    """L'autre moitie : le produit n'a **pas** de version degradee.

    `ChaineReelle` accepte l'atelier en rappel -- c'est ce qui la rend
    mesurable sans disque --, mais `chaine_du_produit` l'injecte **toujours**.
    Les deux branches doivent rester distinguables.
    """
    assert (chaine_du_produit()._ouvrir_l_atelier_exports
            is parcours_exports.ouvrir_l_atelier_exports)


def test_un_projet_SANS_lot_encodable_est_DIT_et_ne_tombe_pas(tmp_path, banc):
    """Le cas rare mais atteignable : plus aucun lot au moment du `⏎`.

    La phrase affichee est **celle du modele**, jamais une seconde redaction
    du meme constat.
    """
    dossier = projet_sans_lot(tmp_path)
    app = _app()

    async def scenario(pilote):
        _parcours(pilote.app, dossier).ouvrir()
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert ecran.code == parcours_exports.CODE_AUCUN_LOT
    with pytest.raises(lots_exports.LotsMalFormes) as leve:
        lots_exports.ListeDesLotsAEncoder(lots=[])
    assert ecran.message == str(leve.value)


# ===========================================================================
# L'ordre des ecrans -- ensemble EXACT et ORDONNE (`EPIC11-ARB-172`)
# ===========================================================================

def test_l_ordre_des_ecrans_est_EXACT_quand_aucun_master_n_existe(
        tmp_path, banc):
    """`E4-1` -> `E4-2` -> `E4-3` -> `E4-4` -> `E4-5`. **Aucun `E4-3b`.**

    Le volet negatif compte autant que le positif : un conflit monte alors
    qu'aucun master n'existe ferait franchir a l'operateur un ecran qui ne
    tranche rien.
    """
    dossier = projet(tmp_path)
    app = _app()
    vus = _espionner(app)
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert vus == [
        CRAN_DU_MENU,
        lots_exports.EcranDesLotsAEncoder.__name__,
        reglages_exports.EcranReglagesDeL_encodage.__name__,
        confirmation.EcranExportsConfirmation.__name__,
        execution_exports.EcranEncodageEnCours.__name__,
        resultat_exports.EcranResultatDuMaster.__name__,
    ], vus
    assert versions.EcranMasterExistant.__name__ not in vus, vus
    assert isinstance(ecran, resultat_exports.EcranResultatDuMaster)


def test_l_ordre_des_ecrans_est_EXACT_et_le_conflit_PRECEDE_la_confirmation(
        tmp_path, banc):
    """`EPIC11-ARB-172` : le rang entre dans le nom que `E4-3` affiche.

    Quand la confirmation s'affiche, `..._v3.mov` doit etre un **fait** -- et
    c'est la seconde assertion qui le dit, pas seulement la position.
    """
    dossier = projet(tmp_path, avec_master=True)
    app = _app()
    vus = _espionner(app)
    coeur = CoeurDouble()
    planificateur = PlanificateurDouble(avec_master=frozenset({LOT_CIBLE}))

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur,
                             planificateur=planificateur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        conflit = await _valider_les_reglages(pilote)
        _viser(conflit.choix, versions.CLE_CREER)
        conflit.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert vus == [
        CRAN_DU_MENU,
        lots_exports.EcranDesLotsAEncoder.__name__,
        reglages_exports.EcranReglagesDeL_encodage.__name__,
        versions.EcranMasterExistant.__name__,
        confirmation.EcranExportsConfirmation.__name__,
    ], vus
    attendu = nom_du_master(LOT_CIBLE, LIGNE_D_EAU_DE_LA_CIBLE + 1)
    assert ecran.master.nom == attendu, ecran.master.nom


def test_l_ensemble_des_refus_qui_MENENT_a_E4_3b_est_EXACT(tmp_path, banc):
    """Dans les **deux sens**, et c'est tout l'objet de ce test.

    A gauche : un refus du coeur qui menerait au conflit alors qu'il dit autre
    chose ferait proposer « remplacer ce master » sur un lot troue. A droite :
    le refus de conflit qui cesserait d'y mener ferait rendre `EPIC11-ARB-89`
    inoperant -- un blocage sec, exactement ce qu'il interdit.

    **Le code se lit du coeur** (`encode.ENCODE_*`), jamais recopie : c'est la
    frontiere de vocabulaire de l'AC 11.2.
    """
    dossier = projet(tmp_path, avec_master=True)
    codes = (encode.ENCODE_MASTER_ALREADY_PRESENT,
             encode.ENCODE_LOT_INCOMPLETE,
             encode.ENCODE_VERSION_AND_OVERWRITE)

    def ou_mene(code: str) -> str:
        app = _app()

        async def scenario(pilote):
            parcours = _parcours(
                pilote.app, dossier,
                planificateur=PlanificateurDouble(
                    refus=(code, MESSAGE_DU_LOT_INCOMPLET)))
            await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
            await _valider_les_reglages(pilote)
            return type(pilote.app.screen).__name__

        return banc(app, scenario)

    au_conflit = {code for code in codes
                  if ou_mene(code) == versions.EcranMasterExistant.__name__}
    assert au_conflit == {encode.ENCODE_MASTER_ALREADY_PRESENT}, au_conflit
    autres = {code for code in codes
              if code != encode.ENCODE_MASTER_ALREADY_PRESENT}
    assert {ou_mene(code) for code in autres} == {EcranRefus.__name__}


def test_le_refus_du_coeur_voyage_VERBATIM_jusqu_a_l_operateur(tmp_path, banc):
    """`EPIC11-ARB-30` : la TUI met en forme, elle ne requalifie pas."""
    dossier = projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(
            pilote.app, dossier,
            planificateur=PlanificateurDouble(
                refus=(encode.ENCODE_LOT_INCOMPLETE,
                       MESSAGE_DU_LOT_INCOMPLET)))
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        await _valider_les_reglages(pilote)
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert ecran.code == encode.ENCODE_LOT_INCOMPLETE
    assert ecran.message == MESSAGE_DU_LOT_INCOMPLET


# ===========================================================================
# `E4-3b` -- trois issues, et chacune mene AILLEURS (`EPIC11-ARB-89`)
# ===========================================================================

@pytest.mark.parametrize("cle,attendu", [
    (versions.CLE_CREER, dict(nouvelle_version=True, overwrite=False)),
    (versions.CLE_REMPLACER, dict(nouvelle_version=False, overwrite=True)),
])
def test_les_deux_issues_ECRIVANTES_de_E4_3b_passent_par_la_confirmation(
        tmp_path, banc, cle, attendu):
    """Aucune des deux ne saute le point de jugement.

    Une ecriture qui sauterait `E4-3` parce qu'elle a deja traverse un
    avertissement ferait **deux** points de jugement, pas un -- et les deux
    drapeaux sont poses **exclusivement**, `plan_encode` refusant nommement
    leur combinaison.
    """
    dossier = projet(tmp_path, avec_master=True)
    app = _app()
    planificateur = PlanificateurDouble(avec_master=frozenset({LOT_CIBLE}))

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier,
                             planificateur=planificateur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        conflit = await _valider_les_reglages(pilote)
        _viser(conflit.choix, cle)
        conflit.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, confirmation.EcranExportsConfirmation), type(ecran)
    dernier = planificateur.appels[-1]
    assert {mot: dernier[mot] for mot in attendu} == attendu, dernier


def test_ANNULER_a_E4_3b_revient_aux_REGLAGES_et_n_ecrit_rien(tmp_path, banc):
    """La troisieme issue -- celle que le curseur vise a l'ouverture.

    `EPIC11-ARB-7`, verbatim d'Egan : « Ok sur annuler ». L'invariant est leve
    par `ChoixExclusif`, il n'est pas repose ici ; ce qui se mesure est **ou
    l'annulation ramene**, et qu'aucun octet n'a bouge.
    """
    dossier = projet(tmp_path, avec_master=True)
    avant = (dossier / "project.json").read_bytes()
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(
            pilote.app, dossier,
            planificateur=PlanificateurDouble(
                avec_master=frozenset({LOT_CIBLE})))
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        conflit = await _valider_les_reglages(pilote)
        # Le curseur part deja sur l'issue qui n'ecrit pas : on le verifie
        # plutot que de le deplacer.
        assert conflit.choix.issues[conflit.choix.curseur].cle \
            == versions.CLE_ANNULER
        conflit.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, reglages_exports.EcranReglagesDeL_encodage)
    assert (dossier / "project.json").read_bytes() == avant


def test_AC4_4_trois_montages_ANNULES_ne_consomment_AUCUN_rang(tmp_path, banc):
    """« Trois montages annules ne font pas monter la ligne d'eau. »

    Mesure **a travers le parcours**, et non au coeur : le banc du lot B0 bis
    la fait deja au coeur. Ce qui reste a prouver ici est que le parcours
    n'ecrit rien entre les deux -- la ligne d'eau se lit par le **resolveur du
    coeur** sur le manifeste **relu du disque**, jamais par un compteur du
    banc.
    """
    dossier = projet(tmp_path, avec_master=True)

    def rang_propose() -> int:
        return encode.resolve_master_version_rank(
            projet_lecture.lire_manifeste(dossier), LOT_CIBLE,
            profile_id=codec_profiles.DEFAULT_PROFILE_ID,
            container=codec_profiles.PROFILES[
                codec_profiles.DEFAULT_PROFILE_ID].container)

    avant = rang_propose()
    assert avant == LIGNE_D_EAU_DE_LA_CIBLE + 1, avant
    octets = (dossier / "project.json").read_bytes()
    rangs_annonces = []

    for _ in range(3):
        app = _app()

        async def scenario(pilote):
            parcours = _parcours(
                pilote.app, dossier,
                planificateur=PlanificateurDouble(
                    avec_master=frozenset({LOT_CIBLE})))
            await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
            conflit = await _valider_les_reglages(pilote)
            rangs_annonces.append(conflit.conflit.rang_propose)
            _viser(conflit.choix, versions.CLE_ANNULER)
            conflit.traiter("enter")
            await pilote.pause()

        banc(app, scenario)

    assert rangs_annonces == [avant] * 3, rangs_annonces
    assert rang_propose() == avant
    assert (dossier / "project.json").read_bytes() == octets


# ===========================================================================
# `E4-3` -- ce que ses trois issues font
# ===========================================================================

@pytest.mark.parametrize("cle", [confirmation.ISSUE_MODIFIER,
                                 confirmation.ISSUE_ANNULER])
def test_les_deux_issues_NON_ECRIVANTES_de_E4_3_reviennent_aux_REGLAGES(
        tmp_path, banc, cle):
    """Aux **reglages**, pas « d'un palier » -- finding `F4` pris a la source.

    Un ecran de conflit a pu se glisser entre les deux (`EPIC11-ARB-172`), et
    une remontee d'un cran atterrirait alors sur un conflit deja tranche,
    **seulement** quand un master existait. Ce test le mesure sur le regime
    qui porte le piege : celui ou le conflit a eu lieu.
    """
    dossier = projet(tmp_path, avec_master=True)
    app = _app()
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(
            pilote.app, dossier, coeur=coeur,
            planificateur=PlanificateurDouble(
                avec_master=frozenset({LOT_CIBLE})))
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        conflit = await _valider_les_reglages(pilote)
        _viser(conflit.choix, versions.CLE_CREER)
        conflit.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        _viser(ecran.choix, cle)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, reglages_exports.EcranReglagesDeL_encodage)
    assert coeur.appels == []


# ===========================================================================
# Ce qui part au coeur -- l'ensemble EXACT des mots-cles (AC 2.4)
# ===========================================================================

def test_les_mots_cles_passes_au_coeur_sont_l_ensemble_EXACT_de_la_decision(
        tmp_path, banc):
    """AC 2.4, et la frontiere mord des **deux** cotes.

    L'ensemble attendu est lu de `encode_master.MOTS_CLES_DE_LA_DECISION`,
    jamais recopie : un mot-cle qui apparait et un mot-cle qui disparait font
    rougir tous les deux, et le jour ou le coeur en gagne un, ce banc dit ou
    le cablage doit suivre.

    `logger` n'est pas une decision : il est passe **en plus**, et le test le
    nomme plutot que de l'englober -- le coeur retomberait sinon sur un
    journal qui propage vers la racine et ecrirait sur `stdout` par-dessus
    l'interface.
    """
    dossier = projet(tmp_path)
    app = _app()
    coeur = CoeurDouble()
    planificateur = PlanificateurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur,
                             planificateur=planificateur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()

    banc(app, scenario)
    assert len(coeur.appels) == 1, coeur.appels
    assert set(coeur.appels[0]) == set(encode_master.MOTS_CLES_DE_LA_DECISION)
    # La decision affichee et la decision executee sont la **meme**.
    assert planificateur.appels[-1] == coeur.appels[0]
    assert coeur.appels[0]["lot_id"] == LOT_CIBLE


def test_le_consentement_au_lot_INCOMPLET_n_est_JAMAIS_donne_par_la_TUI(
        tmp_path, banc):
    """Ecart signale et non tranche : aucun arbitrage ne fait d'un `⏎` un
    consentement.

    `--accept-incomplete-lot` est un mot de la ligne de commande, pas un geste
    de la TUI. Tant qu'Egan n'a pas tranche, le parcours **ne donne pas** ce
    consentement, et la constante nommee est le seul endroit ou cela change.
    """
    dossier = projet(tmp_path)
    app = _app()
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()

    banc(app, scenario)
    assert coeur.appels[0]["accept_incomplete"] is False
    assert parcours_exports.CONSENTEMENT_AU_LOT_INCOMPLET is False


# ===========================================================================
# Le raccord de progression -- `EPIC11-ARB-184`, dans ses DEUX etats
# ===========================================================================

def test_le_parcours_ne_POSE_pas_le_mot_cle_avec_le_coeur_D_AUJOURD_HUI(
        tmp_path, banc):
    """`{}` aujourd'hui, et **le parcours n'ecrit le mot-cle nulle part**.

    Le volet negatif est structurel : un `rappel_progression=` ecrit en dur
    dans le module leverait sur le coeur d'aujourd'hui, qui ne l'accepte pas.
    On le mesure **sur le source**, parce qu'un mot-cle pose derriere une
    condition ne se verrait pas a l'execution du seul chemin nominal.
    """
    dossier = projet(tmp_path)
    app = _app()
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()

    banc(app, scenario)
    assert execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION not in coeur.appels[0]
    source = Path(parcours_exports.__file__).read_text(encoding="utf-8")
    lignes = [ligne for ligne in source.splitlines()
              if f"{execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION}=" in ligne]
    assert lignes == [], lignes
    # JONCTION FRANCHIE le 2026-09-07 : cette ligne assertait que le coeur
    # n'accepte PAS encore le mot-cle. La story 6.7 -- « le canal de
    # progression de l'encodage », liee depuis `claude/epic6_6-7_6-8` -- le lui
    # a donne. L'assertion d'origine mesurait donc une DATE, pas un invariant,
    # et elle est ici retournee plutot que retiree : le second etat de la
    # jonction (`test_le_MEME_parcours_pose_le_mot_cle_le_jour_ou_le_coeur_l_accepte`)
    # devient jouable contre le vrai coeur, et non plus seulement contre un
    # double. Ce que ce test-ci continue de mesurer, et qui reste un invariant :
    # le parcours n'ecrit le mot-cle NULLE PART dans son source, et ne le passe
    # pas a un coeur qui ne sait pas compter.
    assert execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION in \
        inspect.signature(encode_master.encoder_le_master_du_lot).parameters


def test_le_MEME_parcours_pose_le_mot_cle_le_jour_ou_le_coeur_l_accepte(
        tmp_path, banc):
    """La jonction d'`EPIC11-ARB-184`, mesuree dans son **second** etat.

    Le parcours ne change pas d'une ligne ; seul le point d'entree change. Si
    ce test etait vert avec un seul coeur, la frontiere serait verte sans rien
    prouver -- c'est exactement ce que le double de `le_coeur_sait_compter`
    existe pour eviter.
    """
    dossier = projet(tmp_path)
    app = _app()
    coeur = CoeurQuiCompte()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours.passage

    passage = banc(app, scenario)
    assert coeur.progression == [(1, 3), (2, 3), (3, 3)], coeur.progression
    assert passage is not None


# ===========================================================================
# `T6-1` -- ce qu'une interruption laisse (AC 9.6)
# ===========================================================================

def test_T6_1_une_interruption_retenue_n_encode_RIEN_et_laisse_le_manifeste(
        tmp_path, banc):
    """« Aucun master ne sera écrit », et c'est **tenu**.

    La fenetre est reelle et unique : entre le dessin de `E4-4` et l'appel du
    coeur, la boucle d'evenements tourne -- c'est le seul instant ou `T6-1`
    est atteignable, puisque la passe du coeur est synchrone. Le test la joue
    telle quelle, au clavier, sans poser le drapeau lui-meme.

    Quatre choses sont mesurees, et la derniere est celle qui compte : le
    parcours **ne sort pas** dans un etat ou le passage suivant croirait
    l'encodage fini -- aucun `E4-5` n'est monte.
    """
    dossier = projet(tmp_path)
    avant = (dossier / "project.json").read_bytes()
    masters_avant = sorted(p.name for p in (dossier / "masters").iterdir())
    app = _app()
    vus = _espionner(app)
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        # **Sans `pause`** : le rendez-vous `call_after_refresh` n'a pas encore
        # rendu la main au parcours, et c'est exactement la fenetre de `T6-1`.
        interruption = pilote.app.screen.ouvrir_l_interruption()
        _viser(interruption.choix, execution_exports.CLE_INTERROMPRE)
        interruption.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert coeur.appels == [], coeur.appels
    assert resultat_exports.EcranResultatDuMaster.__name__ not in vus, vus
    assert (dossier / "project.json").read_bytes() == avant
    assert sorted(p.name for p in (dossier / "masters").iterdir()) \
        == masters_avant
    assert not isinstance(ecran, resultat_exports.EcranResultatDuMaster)


def test_REPRENDRE_a_T6_1_ne_touche_PAS_au_parcours_et_l_encodage_va_au_bout(
        tmp_path, banc):
    """L'autre issue de `T6-1` est de la **navigation**, et rien d'autre.

    Sans ce volet, « l'interruption arrete tout » et « toute issue de `T6-1`
    arrete tout » seraient indiscernables.
    """
    dossier = projet(tmp_path)
    app = _app()
    coeur = CoeurDouble()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        interruption = pilote.app.screen.ouvrir_l_interruption()
        _viser(interruption.choix,
               execution_exports.EcranInterruption.REPRENDRE)
        interruption.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert len(coeur.appels) == 1, coeur.appels
    assert isinstance(ecran, resultat_exports.EcranResultatDuMaster)


# ===========================================================================
# `E4-5` -- deux suites qui n'etaient PAS discernables
# ===========================================================================

def test_ENCODER_UN_AUTRE_LOT_et_RETOUR_menent_a_des_ecrans_DIFFERENTS(
        tmp_path, banc):
    """Le lot G les avait signalees indiscernables. Elles ne le sont plus.

    `Encoder un autre lot` depile jusqu'a `E4-1` -- l'ouverture de l'atelier,
    un cran **en dessous** du menu (`EPIC11-ARB-13`) --, `Retour aux ateliers`
    remonte au menu. Le test compare les **deux** arrivees plutot que
    d'asserter sur une seule : c'est la seule mesure qui attrape leur
    confusion.
    """
    dossier = projet(tmp_path)

    def ou_mene(suite: str | None) -> str:
        app = _app()

        async def scenario(pilote):
            parcours = _parcours(pilote.app, dossier, coeur=CoeurDouble())
            await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
            ecran = await _valider_les_reglages(pilote)
            _viser(ecran.choix, confirmation.ISSUE_ENCODER)
            ecran.traiter("enter")
            await pilote.pause()
            resultat = pilote.app.screen
            _viser_la_suite(resultat, suite)
            resultat.on_key(_Touche("enter"))
            await pilote.pause()
            return type(pilote.app.screen).__name__

        return banc(app, scenario)

    autre_lot = ou_mene(resultat_exports.SUITE_AUTRE_LOT)
    retour = ou_mene(None)
    assert autre_lot == lots_exports.EcranDesLotsAEncoder.__name__, autre_lot
    assert autre_lot != retour, (autre_lot, retour)
    assert retour != resultat_exports.EcranResultatDuMaster.__name__, retour


def test_une_suite_INCONNUE_de_E4_5_ne_consomme_pas_la_touche_en_silence(
        tmp_path, banc):
    """Le filet du finding `K3` : une suite sans destination le **DIT**."""
    dossier = projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=CoeurDouble())
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()
        parcours.suivre("une suite que personne n'a cablee")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)
    assert isinstance(ecran, EcranPasEncore), type(ecran)


def test_E4_5_montre_ce_que_la_PASSE_a_ecrit_et_sa_duree_d_encodage(
        tmp_path, banc):
    """Le compte rendu porte le master **de la passe**, pas celui de l'ecran.

    Le master est retenu **sur le parcours** : le lire sur `app.screen` le
    ferait chercher au sommet de la pile, ou un filet a pu se glisser.
    """
    dossier = projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=CoeurDouble())
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen, parcours.ecrit

    ecran, ecrit = banc(app, scenario)
    assert ecran.master is ecrit
    assert ecrit.nom == nom_du_master(LOT_CIBLE)
    assert ecrit.lot_id == LOT_CIBLE
    assert ecrit.duree_d_encodage_s == pytest.approx(DUREE_DE_LA_PASSE)


# ===========================================================================
# Le drapeau de tache -- finding C1-1 de la revue du 2026-09-03
# ===========================================================================
#
# Le defaut ferme ici : `ParcoursExports.encoder` montait `E4-4` sans jamais
# poser `app.tache_en_cours`, et `EcranEncodageEnCours` -- qui ne sous-classe
# pas `execution.EcranExecution` -- ne le posait pas non plus a son montage.
# L'extincteur existait pourtant deja, dans le `finally` de `lancer`.
#
# Ce que ca laissait, mesure par la couche 1 en montant l'ecran : pendant
# l'encodage, `q` traversait `CoqueTui.action_quitter` sans rencontrer sa porte
# de confirmation et **quittait la TUI en une frappe**. `Echap` n'etait pas
# touche, `EcranEncodageEnCours.on_key` l'interceptant lui-meme pour `T6-1`.
#
# C'est la TROISIEME occurrence de cette classe dans l'epic -- les deux
# precedentes sont relatees a `test_atelier_pdf_execution.py:735` --, et le
# correctif a deux volets n'avait jamais ete porte a cet atelier.


def test_le_drapeau_de_tache_PROTEGE_des_que_la_passe_PART(tmp_path, banc):
    """`q` demande confirmation au lieu de quitter, **avant tout dessin**.

    **L'absence de `pause` EST la mesure**, et c'est ce qui distingue ce test
    d'une verification de facade : `_lancer_apres_le_dessin` differe l'appel du
    coeur, donc a l'instruction qui suit `traiter("enter")` la passe n'a pas
    commence et `on_mount` n'a pas tourne. Un drapeau pose au montage de
    l'ecran serait donc encore a faux ici -- c'est precisement pourquoi le
    volet d'allumage vit au point d'appel et pas dans `on_mount`.

    Les deux valeurs sont rendues ensemble parce qu'aucune ne suffit :
    `tache_en_cours` seul dirait que le drapeau est pose sans dire ce qu'il
    protege, et `confirmation_de_sortie_demandee` seul ne dirait pas d'ou vient
    la porte.

    **`app.is_running` a ete essaye comme troisieme valeur et RETIRE, parce
    qu'il ne discrimine pas** : sous le mutant, le releve vaut
    `(False, False, True)` -- l'extinction que `exit()` demande est
    asynchrone, donc la coque est encore vivante a l'instruction suivante,
    mutant ou pas. Une troisieme assertion qui rend la meme valeur des deux
    cotes n'ajoute pas de garantie, elle ajoute l'apparence d'une garantie.
    C'est la famille de la tautologie que la politique du depot nomme, et elle
    ne s'est vue qu'a la reinjection.
    """
    dossier = projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=CoeurDouble())
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        pendant = pilote.app.tache_en_cours
        pilote.app.action_quitter()
        releve = (pendant, pilote.app.confirmation_de_sortie_demandee)
        # **Le verdict se rend ICI, dans le scenario, et pas seulement au
        # retour.** Sans le drapeau, `action_quitter` appelle `exit()` : la
        # coque part en extinction et le rotor de `E4-4` redessine un ecran
        # dont les noeuds n'existent plus. Le banc rougissait alors sur un
        # `NoMatches: No nodes match '#etat'` -- c'est-a-dire sur la
        # DECONSTRUCTION, jamais sur l'assertion, et la valeur relevee etait
        # perdue avec le retour. Un mutant tue par un incident de teardown est
        # un tue qu'on ne peut pas lire : il rougirait pareil pour dix autres
        # causes. Asserter avant que la coque se demonte fait atterrir le rouge
        # sur la phrase qu'on mesure.
        assert releve == (True, True), releve
        return releve

    assert banc(app, scenario) == (True, True)


def test_la_passe_FINIE_rend_le_drapeau_et_q_quitte_de_nouveau(tmp_path, banc):
    """Le second sens, sans lequel le premier ferait un atelier MORT.

    Un drapeau qui protege sans se rendre est pire que pas de drapeau : `Echap`
    cesse de depiler et `q` de quitter pour la session entiere. C'est le defaut
    jumeau, paye deux fois ailleurs dans cet epic.

    Ici la `pause` laisse la passe aller au bout, `finally` comprise.
    """
    dossier = projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=CoeurDouble())
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        ecran.traiter("enter")
        await pilote.pause()
        apres = pilote.app.tache_en_cours
        pilote.app.action_quitter()
        return apres, pilote.app.confirmation_de_sortie_demandee

    apres, demande = banc(app, scenario)
    assert apres is False
    assert demande is False


def _passage_temoin():
    """Un passage minimal, pour monter `E4-4` sans passer par le parcours.

    Les deux tests du filet de demontage mesurent l'ECRAN, pas le cablage :
    les faire passer par le parcours ferait tomber le `finally` de `lancer`
    dans la mesure, et l'extinction observee ne dirait plus lequel des deux
    chemins l'a produite.
    """
    return execution_exports.PassageDeLEncodage.du_plan(
        plan_de(Path("/projet-temoin"), lot_id=LOT_CIBLE,
                profile_id=codec_profiles.DEFAULT_PROFILE_ID,
                resolution=encode.DEFAULT_RESOLUTION_ID,
                nouvelle_version=False, overwrite=False))


def test_le_DEMONTAGE_de_l_ecran_de_la_passe_REND_le_drapeau(banc):
    """Le filet des chemins qui DEPILENT au lieu de conclure.

    Le `finally` de `ParcoursExports.lancer` couvre la passe qui va au bout,
    refus compris. Il ne couvre pas un ecran retire **avant** que la passe ne
    parte -- et un drapeau qui protege sans se rendre est un atelier mort pour
    la session entiere : `Echap` cesse de depiler, `q` de quitter. C'est le
    defaut jumeau, paye par `atelier_scan_parcours.EcranCollisionDeLaPasse`.
    """
    app = _app()

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = execution_exports.EcranEncodageEnCours(
            _passage_temoin(), sur_issue=lambda _issue: None)
        setattr(pilote.app, execution_exports.ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE,
                ecran)
        pilote.app.tache_en_cours = True
        pilote.app.descendre(ecran)
        await pilote.pause()
        pendant = pilote.app.tache_en_cours
        pilote.app.pop_screen()
        await pilote.pause()
        return pendant, pilote.app.tache_en_cours

    assert banc(app, scenario) == (True, False)


def test_le_demontage_d_un_ecran_PRECEDENT_n_eteint_PAS_la_passe_SUIVANTE(banc):
    """L'extinction est CONDITIONNELLE, et voici ce que la condition tient.

    **Ce test a ete ecrit apres une reinjection qui l'exigeait** : remplacer la
    garde par `if True:` -- c'est-a-dire eteindre au demontage de n'importe
    quel ecran de passe -- **survivait aux 78 tests** des deux bancs. La garde
    etait une surface posee sans frontiere, exactement ce que la politique du
    depot refuse.

    Ce qu'elle ecarte : demonter l'ecran d'une passe FINIE alors que la
    suivante est deja partie ferait tomber le drapeau de la passe **neuve** --
    fil vivant, garde de re-entrance desarmee. C'est l'ecart
    qu'`atelier_scan_calibrate` a impose au second tour.
    """
    app = _app()

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ancien = execution_exports.EcranEncodageEnCours(
            _passage_temoin(), sur_issue=lambda _issue: None)
        pilote.app.descendre(ancien)
        await pilote.pause()
        # La passe SUIVANTE part : c'est elle que l'application retient
        # desormais, et c'est son drapeau qui est allume.
        neuf = execution_exports.EcranEncodageEnCours(
            _passage_temoin(), sur_issue=lambda _issue: None)
        setattr(pilote.app, execution_exports.ATTRIBUT_DE_L_ECRAN_DE_LA_PASSE,
                neuf)
        pilote.app.tache_en_cours = True
        # ... et l'ecran de la passe PRECEDENTE se demonte.
        pilote.app.pop_screen()
        await pilote.pause()
        return pilote.app.tache_en_cours

    assert banc(app, scenario) is True


# ===========================================================================
# LE CUL-DE-SAC du 2026-09-06 -- le seul defaut BLOQUANT du retour terrain
#
# Egan, verbatim, sur l'ecran d'echec de verification technique : « Aucune
# issue sur cet ecran. Pas d'interruption possible ... » et, sur l'ecran
# d'interruption : « Echap pendant un rendu mene a l'ecran d'interruption mais
# l'interruption ne donne rien. Oblige de quitter ».
#
# La boucle etait fermee, et aucune de ses cinq marches n'etait fautive seule :
#
#   1. `refuser` empilait `EcranRefus` PAR-DESSUS `E4-4`, qui restait dessous ;
#   2. `Echap` sur le refus depile -> on retombe sur `E4-4`, l'ecran d'un
#      encodage qui n'a plus lieu ;
#   3. son `on_key` intercepte `escape` et monte `T6-1` ;
#   4. « Interrompre » posait un drapeau que plus personne ne lit et ne
#      depilait rien ;
#   5. `Echap` sur `T6-1` vaut « Reprendre » et redescend sur l'ecran mort.
#
# **L'angle mort qui a laisse passer ce piege est nommable en une phrase :
# aucun banc du depot ne mesurait l'etat de la PILE apres un refus.** Les bancs
# d'ordre ci-dessus lisent la suite des `descendre` -- ce qui a ete MONTE --,
# et un ecran mort laisse dessous ne se voit pas dans cette suite. Les quatre
# volets qui suivent mesurent donc la pile elle-meme, et la navigation reelle
# au clavier par-dessus.
# ===========================================================================

def _pile(app) -> list[str]:
    """Les noms des ecrans EMPILES, du fond au sommet.

    C'est la mesure qui manquait : `_espionner` dit ce qui a ete monte, jamais
    ce qui est reste dessous. Un ecran d'execution mort n'apparait dans aucune
    des deux listes de `vus`, et c'est exactement la ou le piege s'est loge.
    """
    return [type(ecran).__name__ for ecran in app.screen_stack]


def _refus_de_verification(chemin_conserve: Path):
    """Le refus REEL qu'Egan a rencontre, avec son fichier conserve.

    Ce n'est pas une exception de circonstance : `EncodeVerificationRefused`
    est le refus que `encode.execute_plan` leve quand la relecture du fichier
    produit ne rend pas ce qu'elle devait, et il porte `staged_path` **en
    propre** -- le fichier d'attente est garde EXPRES pour diagnostic, la
    bascule n'ayant pas eu lieu. Un double qui leverait une autre famille ne
    mesurerait ni la rubrique `Conserve` ni le chemin qu'elle doit dire.
    """
    return encode.EncodeVerificationRefused(
        "Le fichier produit ne porte pas ce qu'il devait porter (color_primaries:"
        " obtenu 'bt709' au lieu de 'smpte170m'). La bascule n'a pas eu lieu :"
        " le master precedent est intact.",
        staged_path=chemin_conserve, report={})


async def _jusqu_au_bout_de_la_passe(pilote, parcours, coeur):
    """Aller de `E4-1` jusqu'a la conclusion de la passe, au clavier.

    La passe part **au fil de travail** depuis le 2026-09-06 : on attend donc
    que le coeur ait ete appele, et non un nombre fixe de `pause`. Une borne
    plutot qu'une attente nue -- un banc rouge ne doit pas suspendre la course.
    """
    await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
    ecran = await _valider_les_reglages(pilote)
    _viser(ecran.choix, confirmation.ISSUE_ENCODER)
    ecran.traiter("enter")
    limite = time.monotonic() + 8.0
    while time.monotonic() < limite:
        if coeur.appels and not isinstance(
                pilote.app.screen, execution_exports.EcranEncodageEnCours):
            break
        await pilote.pause()
        await asyncio.sleep(0.02)
    for _ in range(3):
        await pilote.pause()
    return pilote.app.screen


def test_un_REFUS_du_coeur_ne_laisse_PAS_l_ecran_d_encodage_sous_lui(
        tmp_path, banc):
    """Le cul-de-sac, mesure sur la PILE et non sur la suite des montages.

    Trois faits, et le troisieme est celui qui compte pour l'operateur :

    * le refus est bien a l'ecran -- sinon on mesurerait un autre chemin ;
    * `E4-4` **n'est plus dans la pile** : c'est la reparation ;
    * `Echap` depuis le refus atterrit sur un ecran qui **n'est pas** un ecran
      d'execution. Sans ce troisieme point, la pile pourrait etre propre et la
      navigation reelle mener ailleurs.
    """
    dossier = projet(tmp_path)
    conserve = tmp_path / "master.mov.2624-attente.mov"
    coeur = CoeurDouble(leve=_refus_de_verification(conserve))
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        ecran = await _jusqu_au_bout_de_la_passe(pilote, parcours, coeur)
        mesure["au_refus"] = type(ecran).__name__
        mesure["pile_au_refus"] = _pile(pilote.app)
        # Et la navigation REELLE : `Echap` est la touche qu'`EcranRefus`
        # annonce, et c'est par elle qu'Egan est tombe dans la boucle.
        pilote.app.action_remonter()
        await pilote.pause()
        mesure["apres_echap"] = type(pilote.app.screen).__name__
        mesure["pile_apres_echap"] = _pile(pilote.app)

    banc(app, scenario)

    assert mesure["au_refus"] == EcranRefus.__name__, mesure
    assert execution_exports.EcranEncodageEnCours.__name__ not in \
        mesure["pile_au_refus"], (
        "`E4-4` est reste sous le refus : `Echap` y retombera, son `on_key`"
        " montera `T6-1`, et l'operateur sera dans la boucle fermee du"
        f" 2026-09-06 -- pile : {mesure['pile_au_refus']}")
    assert mesure["apres_echap"] != \
        execution_exports.EcranEncodageEnCours.__name__, (
        "`Echap` depuis le refus retombe sur l'ecran d'un encodage qui n'a plus"
        " lieu : c'est litteralement « oblige de quitter »")
    assert execution_exports.EcranEncodageEnCours.__name__ not in \
        mesure["pile_apres_echap"], mesure["pile_apres_echap"]


async def _pendant_la_passe(pilote, parcours, coeur):
    """Aller jusqu'a `E4-4` et s'y arreter, le coeur retenu dans son fil."""
    await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
    ecran = await _valider_les_reglages(pilote)
    _viser(ecran.choix, confirmation.ISSUE_ENCODER)
    ecran.traiter("enter")
    limite = time.monotonic() + 8.0
    while time.monotonic() < limite and not coeur.arrive.is_set():
        await pilote.pause()
        await asyncio.sleep(0.02)
    assert coeur.arrive.is_set(), "le coeur n'a jamais demarre"
    await pilote.pause()


async def _laisser_conclure(pilote, coeur):
    coeur.reprendre.set()
    limite = time.monotonic() + 8.0
    while time.monotonic() < limite and isinstance(
            pilote.app.screen, execution_exports.EcranEncodageEnCours):
        await pilote.pause()
        await asyncio.sleep(0.02)
    for _ in range(3):
        await pilote.pause()


@pytest.mark.parametrize("refuse", [False, True], ids=["nominal", "refus"])
def test_un_ecran_TIERS_monte_pendant_la_passe_ne_rouvre_pas_le_cul_de_sac(
        tmp_path, banc, refuse):
    """Le regime que le PREMIER correctif ne fermait pas, mesure sur les deux branches.

    **Pourquoi ce banc existe, et il vaut d'etre lu avant d'y toucher.** Le
    correctif du 2026-09-06 depilait `E4-4` *seulement s'il etait au sommet* ::

        if self.app.screen is ecran: self.app.pop_screen()

    C'est vrai quand rien ne s'est passe pendant la passe -- et c'est
    exactement ce que mesuraient les deux bancs ecrits avec lui. Or `E4-4`
    n'est plus au sommet des que l'operateur a ouvert quoi que ce soit, et
    **les deux seules touches que cet ecran annonce** (`Echap` pour
    l'interruption, `F1` pour l'aide) en ouvrent une. La garde tombait donc en
    defaut precisement sur le geste d'Egan, et le cul-de-sac rouvrait entier :

        [..., EcranEncodageEnCours, EcranInterruptionDeLEncodage, EcranResultatDuMaster]

    Le drapeau varie dans les deux sens (`refuse`), parce que la lecon du
    premier correctif est justement qu'une branche reparee n'acquitte pas
    l'autre : Egan n'avait rencontre que le refus.

    Ce que le banc mesure, et le troisieme point est celui qui compte pour
    l'operateur : l'ecran tiers est bien monte pendant la passe (sinon on
    mesurerait le regime deja couvert) ; `E4-4` n'est plus dans la pile a la
    conclusion ; et `Echap` depuis la conclusion n'atterrit pas sur un ecran
    d'execution.
    """
    dossier = projet(tmp_path)
    conserve = tmp_path / "master.mov.2624-attente.mov"
    coeur = _CoeurRetenu(
        leve=_refus_de_verification(conserve) if refuse else None)
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _pendant_la_passe(pilote, parcours, coeur)
        mesure["pendant"] = type(pilote.app.screen).__name__
        # Le geste litteral d'Egan : `Echap` pendant le rendu. On passe par
        # l'`on_key` de l'ecran et non par `action_remonter` -- pendant une
        # tache, la coque se contente de poser un drapeau, et c'est `E4-4` qui
        # monte `T6-1`. On ne choisit AUCUNE issue : le coeur finit dessous.
        pilote.app.screen.on_key(_Touche("escape"))
        await pilote.pause()
        mesure["ecran_tiers"] = type(pilote.app.screen).__name__
        mesure["pile_avec_tiers"] = _pile(pilote.app)
        await _laisser_conclure(pilote, coeur)
        mesure["a_la_conclusion"] = type(pilote.app.screen).__name__
        mesure["pile_conclusion"] = _pile(pilote.app)
        pilote.app.action_remonter()
        await pilote.pause()
        mesure["apres_echap"] = type(pilote.app.screen).__name__
        mesure["pile_apres_echap"] = _pile(pilote.app)

    banc(app, scenario)

    mort = execution_exports.EcranEncodageEnCours.__name__

    assert mesure["ecran_tiers"] != mort, (
        "l'ecran tiers n'a pas ete monte : ce banc mesure alors le regime deja"
        f" couvert, pas celui qui manquait -- {mesure}")
    assert mort in mesure["pile_avec_tiers"], (
        "`E4-4` doit encore etre dans la pile a ce moment : la passe tourne."
        f" Sinon le banc ne prouve rien -- {mesure}")

    assert mort not in mesure["pile_conclusion"], (
        "`E4-4` est reste enterre sous la conclusion alors qu'un ecran tiers"
        " avait ete monte pendant la passe. C'est le cul-de-sac du 2026-09-06,"
        " rouvert par la garde « seulement si au sommet » --"
        f" pile : {mesure['pile_conclusion']}")
    assert mesure["apres_echap"] != mort, (
        "`Echap` depuis la conclusion retombe sur l'ecran d'un encodage qui"
        " n'a plus lieu : c'est litteralement « oblige de quitter »"
        f" -- {mesure}")
    assert mort not in mesure["pile_apres_echap"], mesure["pile_apres_echap"]


def test_une_passe_REUSSIE_ne_laisse_PAS_non_plus_l_ecran_d_encodage_sous_elle(
        tmp_path, banc):
    """Le volet symetrique, et il n'est pas decoratif.

    Egan n'a rencontre que la branche de refus -- c'est celle qui lui est
    arrivee. Le chemin nominal empilait `E4-5` par-dessus le **meme** `E4-4`
    mort, et `Echap` depuis le compte rendu y retombait exactement pareil.
    Reparer la seule branche vue aurait laisse le piege entier sur l'autre :
    un banc qui ne mesurerait que le refus l'aurait acquittee.
    """
    dossier = projet(tmp_path)
    coeur = CoeurDouble()
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        ecran = await _jusqu_au_bout_de_la_passe(pilote, parcours, coeur)
        mesure["au_resultat"] = type(ecran).__name__
        mesure["pile"] = _pile(pilote.app)

    banc(app, scenario)

    assert mesure["au_resultat"] == \
        resultat_exports.EcranResultatDuMaster.__name__, mesure
    assert execution_exports.EcranEncodageEnCours.__name__ not in \
        mesure["pile"], (
        "`E4-4` est reste sous le compte rendu : meme piege que sur le refus,"
        f" sur l'autre branche -- pile : {mesure['pile']}")


def test_l_ecran_de_REFUS_DIT_le_fichier_conserve_et_le_master_non_ecrit(
        tmp_path, banc):
    """`EcranRefus` sait rendre trois listes ; ce point d'appel n'en remplissait
    aucune.

    **La consequence n'est pas cosmetique, elle a coute un fichier.** Quand la
    verification technique echoue, `encode` conserve le fichier d'attente
    **expres**, pour diagnostic, et la bascule n'a pas eu lieu -- le master
    precedent est intact octet a octet. C'est contractuel. Muet, ce fichier
    devient un residu anonyme : Egan l'a supprime a la main en le prenant pour
    une fuite.

    Le chemin est **lu sur l'exception** (`staged_path`), jamais devine d'un
    dossier de sortie, et le nom du master non ecrit est lu sur le passage --
    donc de `plan.output_path.name`, donc de ce qu'`io.naming` a decide.
    """
    dossier = projet(tmp_path)
    conserve = tmp_path / "master.mov.2624-attente.mov"
    coeur = CoeurDouble(leve=_refus_de_verification(conserve))
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        ecran = await _jusqu_au_bout_de_la_passe(pilote, parcours, coeur)
        mesure["ecran"] = ecran
        mesure["lignes"] = ecran.lignes()

    banc(app, scenario)

    ecran = mesure["ecran"]
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert ecran.conserve == [str(conserve)], (
        "le fichier conserve pour diagnostic n'est pas dit : l'operateur ne"
        " peut pas savoir ou regarder, ni que ce fichier est volontaire")
    assert ecran.non_ecrit == [nom_du_master(LOT_CIBLE, None)], ecran.non_ecrit
    assert ecran.suites, "aucune suite proposee : c'est le blocage sec"
    # **Et la suite du fichier conserve dit le VRAI mecanisme.** Le coeur
    # balaie ces residus de lui-meme (`prepare_output_directory` ->
    # `codec_profiles.sweep_encode_residues`, a chaque passe, passe 24 h) :
    # envoyer l'operateur les supprimer a la main serait une corvee inventee,
    # et c'est ce que la premiere redaction faisait.
    assert parcours_exports.PHRASE_DU_FICHIER_CONSERVE in ecran.suites, \
        ecran.suites
    # Et les trois rubriques atteignent bien le RENDU -- un champ rempli qu'on
    # n'afficherait pas serait la meme panne, un cran plus loin.
    rendu = "\n".join(mesure["lignes"])
    assert "Conserve" in rendu and str(conserve) in rendu, rendu
    assert "Non ecrit" in rendu, rendu
    assert "Suites" in rendu, rendu


def test_INTERROMPRE_depile_T6_1_et_l_ecran_DIT_que_la_passe_se_termine(
        tmp_path, banc):
    """`T6-1` ne devait pas survivre a son issue, et il survivait.

    « Interrompre » posait un drapeau et ne depilait rien : l'ecran restait
    monte, son `Echap` valant « Reprendre », et l'operateur tournait en rond.
    Deux mesures, et il faut les deux :

    * `T6-1` est **depile** -- le cul-de-sac est ferme ;
    * l'ecran retrouve **dit** que la passe engagee va a son terme. Depiler
      sans le dire laisserait l'operateur devant un rotor qui tourne en croyant
      avoir arrete la passe, c'est-a-dire un ecran qui ment -- pire qu'un ecran
      qui refuse.

    Le coeur est retenu dans son fil pendant toute la mesure : c'est le seul
    regime ou `T6-1` a un sens, et c'est celui d'Egan (« Echap **pendant un
    rendu** »).
    """
    dossier = projet(tmp_path)
    coeur = _CoeurRetenu()
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        await _jusqu_aux_reglages(pilote, parcours, LOT_CIBLE)
        ecran = await _valider_les_reglages(pilote)
        _viser(ecran.choix, confirmation.ISSUE_ENCODER)
        try:
            ecran.traiter("enter")
            limite = time.monotonic() + 8.0
            while time.monotonic() < limite and not coeur.arrive.is_set():
                await pilote.pause()
                await asyncio.sleep(0.02)
            assert coeur.arrive.is_set(), "le coeur n'a jamais demarre"
            # `Echap` PENDANT le rendu : c'est le geste d'Egan.
            en_cours = pilote.app.screen
            en_cours.on_key(_Touche("escape"))
            await pilote.pause()
            mesure["sur_T6_1"] = type(pilote.app.screen).__name__
            interruption = pilote.app.screen
            _viser(interruption.choix, execution_exports.CLE_INTERROMPRE)
            interruption.traiter("enter")
            await pilote.pause()
            mesure["apres_interrompre"] = type(pilote.app.screen).__name__
            mesure["etat"] = pilote.app.screen.etat()
        finally:
            coeur.reprendre.set()
        for _ in range(3):
            await pilote.pause()

    banc(app, scenario)

    assert mesure["sur_T6_1"] == \
        execution_exports.EcranInterruptionDeLEncodage.__name__, mesure
    assert mesure["apres_interrompre"] != \
        execution_exports.EcranInterruptionDeLEncodage.__name__, (
        "`T6-1` est reste monte apres « Interrompre » : son `Echap` vaut"
        " « Reprendre », donc l'operateur ne peut plus en sortir -- c'est"
        " « l'interruption ne donne rien. Oblige de quitter »")
    assert mesure["etat"] == \
        execution_exports.PHRASE_DE_L_INTERRUPTION_DEMANDEE, (
        "l'ecran ne dit pas ce qui arrive a la passe apres l'interruption :"
        f" {mesure['etat']!r}. Un rotor qui tourne sans un mot laisse croire"
        " que la passe s'est arretee.")


def test_un_refus_SANS_fichier_conserve_ne_parle_PAS_d_un_fichier(
        tmp_path, banc):
    """Le volet symetrique, et il n'est pas decoratif.

    Les autres refus de la table close ne portent aucun `staged_path` : leur
    annoncer « un fichier est conservé » enverrait l'operateur chercher ce qui
    n'existe pas, et la rubrique `Conserve` afficherait un titre sans ligne.
    Une suite conditionnelle qui ne le serait pas se verrait ici, et nulle part
    ailleurs.
    """
    dossier = projet(tmp_path)
    coeur = CoeurDouble(leve=encode.EncodeDecisionError(
        encode.ENCODE_LOT_INCOMPLETE, MESSAGE_DU_LOT_INCOMPLET))
    app = _app()
    mesure: dict = {}

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        ecran = await _jusqu_au_bout_de_la_passe(pilote, parcours, coeur)
        mesure["ecran"] = ecran
        # Le rendu se lit DANS le scenario : `lignes()` interroge
        # `self.app.ascii_seul`, donc il n'existe que sous une application
        # montee -- une lecture posee apres coup leve au lieu de mesurer.
        mesure["lignes"] = ecran.lignes()

    banc(app, scenario)

    ecran = mesure["ecran"]
    assert isinstance(ecran, EcranRefus), type(ecran)
    assert ecran.conserve == [], ecran.conserve
    assert parcours_exports.PHRASE_DU_FICHIER_CONSERVE not in ecran.suites, \
        ecran.suites
    assert ecran.suites, "un refus sans fichier conserve reste sans issue"
    assert "Conserve" not in "\n".join(mesure["lignes"]), (
        "la rubrique `Conserve` s'affiche sans une seule ligne")


class _CoeurRetenu(CoeurDouble):
    """Un coeur bloque DANS son fil, pour observer `E4-4` a loisir.

    Meme geste que les doubles de `test_ecrans_vivants_pendant_le_coeur.py` :
    au lieu d'attendre et d'esperer avoir regarde au bon moment, on retient le
    coeur et on mesure. La borne d'attente evite qu'un banc rouge suspende la
    suite entiere.
    """

    def __init__(self, *, leve: BaseException | None = None) -> None:
        # **`leve` traverse**, et ce n'est pas du confort : sans lui, ce double
        # ne sait jouer que la branche nominale, donc tout banc qui a besoin
        # d'un coeur RETENU sur la branche de refus doit en ecrire un second --
        # c'est-a-dire mesurer les deux branches avec deux instruments
        # differents. Le mot d'ordre du 2026-09-06 vaut ici : reparer une seule
        # branche laisse le piege entier sur l'autre.
        super().__init__(leve=leve)
        self.arrive = threading.Event()
        self.reprendre = threading.Event()

    def __call__(self, dossier_projet, **reste):
        self.arrive.set()
        self.reprendre.wait(timeout=16.0)
        return super().__call__(dossier_projet, **reste)
