# -*- coding: utf-8 -*-
"""Fermeture des findings CRITIQUES de la revue de la vague 4 (cote TUI).

**Un fichier de banc a part, et c'est un choix de decoupage, pas de confort.**
`CLAUDE.md` le dit dans les deux sens : « aucun lot ne partage un fichier de
banc avec un autre », et « quand un decoupage fait converger deux agents vers
un meme banc, c'est le decoupage qu'il faut changer ». Trois findings sont
fermes ici, chacun sur un module different, pendant que d'autres agents
travaillent les bancs de ces modules -- `git add -N` et `git commit -- <chemins>`
ne protegent pas **a l'interieur** d'un fichier partage, defaut paye trois fois
sur ce depot.

Les fabriques ne sont pas recopiees : elles sont **importees** des bancs qui les
possedent, comme le depot le fait deja (`import test_atelier_scan_confirmation
as fabriques_de_confirmation`). Une seconde redaction divergerait de la
premiere, et c'est la divergence qui rend une fabrique inerte.

Les trois findings, et la mesure d'origine de chacun :

* **`_payload_du_lot` apparie par `lot_id`, et rien ne le mesurait**
  (`tui/atelier_scan_parcours.py`). Mutant `payload.get("lot_id") == lot_id`
  -> `payload` : survivant sur 281 puis 345 tests. C'est le mutant `M25` de la
  story 5.7 a l'identique, **troisieme occurrence** de la famille. Aucune
  fabrique de document du depot ne portait deux `lot_id` distincts dans le
  **meme** document : la cible y etait premiere ET derniere a la fois, la forme
  degeneree du point 2 bis de la regle des fabriques ;
* **`rapport.refus[0]`** (`tui/atelier_scan_ecriture.py`). Mutant `[0]` ->
  `[-1]` : survivant sur 242 tests, parce que les deux seuls bancs qui
  atteignent la ligne remplissent leur collection du **meme** refus
  (`{nom: refus for nom, _ in LOTS}`) -- remplissage uniforme, point 1 de la
  regle des fabriques ;
* **`Échap` pendant la calibration faisait tomber l'application.** Personne ne
  posait `app.tache_en_cours` sur le chemin de `E3-9`, qui est un `Palier` et
  non un `EcranExecution` : `Échap` depilait l'ecran pendant que le fil
  tournait, et `annoncer_la_passe` levait `NoMatches('#etat')` dans
  `call_from_thread` -> `textual.worker.WorkerFailed`. Son voisin du meme cycle
  de vie -- **deux `⏎` = deux passes concurrentes** -- est ferme avec lui.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
import threading
from pathlib import Path

import pytest

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

from mixed_media_utility import (  # noqa: E402
    page_roles,
    scan_calibrate,
    scan_previz,
    scan_write,
)
from mixed_media_utility.io import payload as payload_io  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.io.naming import EXTRACTED_FRAME_SUFFIX  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_scan,
    atelier_scan_calibrate,
    atelier_scan_confirmation,
    atelier_scan_ecriture,
    atelier_scan_parcours,
    jetons,
)

import test_atelier_scan_calibrate_tui as fabriques_de_calibrate  # noqa: E402
import test_atelier_scan_ecriture as fabriques_d_ecriture  # noqa: E402
import test_atelier_scan_rapport as fabriques_du_rapport  # noqa: E402
import test_frontieres_et_grille_scan as fabriques_du_temps_1  # noqa: E402
import test_frontieres_et_grille_scan_temps_2 as fabriques_du_temps_2  # noqa: E402


# ===========================================================================
# Finding 1 -- `_payload_du_lot` apparie par `lot_id`, jamais par rang
# ===========================================================================

#: **Les trois lots de la pile mixte, tous distinguables.** Leur forme n'est pas
#: libre : `scan_output_frames.derive_lot_dir_slug` refuse un `lot_id` qui ne
#: porte ni le rush ni la cadence de son payload, donc chaque nom est celui que
#: le coeur recalculerait -- une fabrique qui inventerait un nom mesurerait le
#: refus du coeur et non l'appariement.
LOT_PREMIER = ("rush_a", 25.0, "rush_a_25")
LOT_CIBLE = ("rush_b", 12.5, "rush_b_12p5")
LOT_DERNIER = ("rush_c", 50.0, "rush_c_50")

#: Le rang de la cible dans la liste que le code PARCOURT -- `brut["pages"]`.
#: Ni le premier (ce qui masquerait un `find` fautif), ni le dernier (ce qui
#: masquerait une terminaison de boucle fautive) : `CLAUDE.md`, points 2 et
#: 2 bis.
RANG_DE_LA_CIBLE = 1

#: Le libelle de la chaine porte par la page de calibration de la pile mixte.
LIBELLE_DE_LA_CHAINE = "banc-de-fermeture"


def _payload_de_lot(rush_id: str, fps_target: float, lot_id: str,
                    page_index: int, page_count: int) -> dict:
    """Un payload de planche d'images, **par son vrai producteur**.

    `payload_io.build_page_payload` valide ce qu'il construit : un dictionnaire
    ecrit a la main ici porterait des champs que le contrat interdit, et le
    regime mesure ne serait plus celui du produit.
    """
    return payload_io.build_page_payload(
        project_id="projet_demo", rush_id=rush_id, lot_id=lot_id,
        page_index=page_index, page_count=page_count,
        fps_target=fps_target, timecode_base_fps="25/1",
        template_id="tpl-a4-portrait-4f-v2", patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY,
        slots=[{"slot_index": page_index,
                "frame_timecode": f"00:00:0{page_index}:00"}],
        page_role=page_roles.PAGE_ROLE_IMAGES)


def _payload_de_calibration(page_index: int, page_count: int) -> dict:
    """Le payload d'une page de calibration, **par son vrai producteur**.

    C'est le producteur qui retire les cinq champs de niveau lot -- `rush_id`,
    `lot_id`, `fps_target` compris. Un dictionnaire ecrit a la main pourrait les
    porter par distraction, et le regime qui fait mordre le finding
    disparaitrait : ce payload est **vrai au sens booleen** tout en ne designant
    aucun lot, ce qui est exactement ce que le mutant `if payload:` prend pour
    une reponse.
    """
    return payload_io.build_page_payload(
        project_id=None, rush_id=None, lot_id=None,
        page_index=page_index, page_count=page_count,
        fps_target=None, timecode_base_fps=None,
        template_id="tpl-a4-portrait-4f-v2", patch_preset_id="patches-14-v3",
        target_colorspace="rec709",
        gamut_map_id=payload_io.GAMUT_MAP_IDENTITY, slots=[],
        page_role=page_roles.PAGE_ROLE_CALIBRATION,
        scan_chain_label=LIBELLE_DE_LA_CHAINE)


def _document_de_pile_mixte(*, calibration_en_tete: bool = True):
    """Un document de **pile mixte** a trois pages, la cible au MILIEU.

    Les deux formes que la fabrique rend, et chacune ferme une moitie du
    finding :

    * `calibration_en_tete=True` -- la premiere page est une page de
      **calibration**. C'est le regime nominal d'une pile mixte, et c'est celui
      ou le finding mord le plus fort : le mutant rend un payload qui ne
      designe aucun lot, `dossier_de_sortie` le **refuse nommement**,
      `_dossier_du_lot` rend `None`, et `T6-1` annonce « 0 frames ecrites » sur
      un disque qui en porte -- en proposant de les effacer ;
    * `calibration_en_tete=False` -- la premiere page est celle d'un **autre
      lot**. Le mutant rend alors un payload parfaitement valide, mais du
      mauvais lot : les frames seraient comptees dans le dossier du voisin.
      C'est litteralement le risque `R12`.

    Le document est rendu **relisible par le coeur** : `scan_previz` le relit,
    donc la fabrique ne s'ecarte pas du contrat qu'elle pretend exercer.
    """
    tete = (_payload_de_calibration(0, 3) if calibration_en_tete
            else _payload_de_lot(*LOT_PREMIER, 0, 3))
    charges = [tete,
               _payload_de_lot(*LOT_CIBLE, 1, 3),
               _payload_de_lot(*LOT_DERNIER, 2, 3)]
    pages = [
        dataclasses.replace(
            fabriques_du_rapport.page(41 + rang, page_index=rang,
                                      page_count=3, frames=rang + 1),
            payload=charge)
        for rang, charge in enumerate(charges)]
    return fabriques_du_temps_1._document_relisible(
        fabriques_du_rapport.document(LOT_CIBLE[2], pages, pages_expected=3))


def _brut_de_pile_mixte(**reglages) -> dict:
    return scan_previz.scan_previz_to_json_dict(
        _document_de_pile_mixte(**reglages))


def _lot_id_des_pages(brut: dict) -> list[str | None]:
    """Les `lot_id` de la liste que le CODE parcourt -- `brut["pages"]`.

    Jamais celle que la fabrique croit ecrire : c'est le finding le plus grave
    de la revue de la vague 3, ou une fixture croyait respecter le point 2 bis
    alors que l'ordre de la liste iteree n'etait pas le sien.
    """
    return [(page.get("payload") or {}).get("lot_id")
            for page in brut["pages"]]


@pytest.mark.parametrize("calibration_en_tete", [True, False],
                         ids=["calibration-en-tete", "autre-lot-en-tete"])
def test_la_fabrique_de_pile_mixte_place_la_cible_AU_MILIEU_de_la_liste_PARCOURUE(
        calibration_en_tete) -> None:
    """Volet symetrique des mesures qui suivent, et il vient **avant** elles.

    Une fabrique dont la cible serait premiere rendrait les tests suivants verts
    sous le mutant, sans que rien ne le dise -- c'est exactement l'etat dans
    lequel le depot etait : toutes ses fabriques de document ne portaient qu'un
    seul `lot_id`, si bien que la cible y etait premiere ET derniere a la fois.
    """
    brut = _brut_de_pile_mixte(calibration_en_tete=calibration_en_tete)
    lots = _lot_id_des_pages(brut)
    assert len(lots) == 3, lots
    assert lots[RANG_DE_LA_CIBLE] == LOT_CIBLE[2], lots
    # Trois valeurs **distinguables** : un remplissage uniforme rendrait toute
    # permutation invisible.
    assert len(set(map(str, lots))) == 3, lots
    assert lots[0] == (None if calibration_en_tete else LOT_PREMIER[2]), lots
    # Et le document reste **relisible par le coeur** : une fabrique que
    # `scan_previz` refuserait mesurerait autre chose que ce qu'elle annonce.
    assert scan_previz.scan_previz_from_json_dict(brut).subject.lot_id \
        == LOT_CIBLE[2]


@pytest.mark.parametrize("calibration_en_tete", [True, False],
                         ids=["calibration-en-tete", "autre-lot-en-tete"])
def test_le_payload_est_apparie_par_LOT_ID_et_jamais_par_RANG(
        calibration_en_tete) -> None:
    """Le mutant `M25`, troisieme occurrence -- et il n'etait mesure par rien.

    `_payload_du_lot` cherche **le payload de ce lot-la**. « Le premier payload
    du document » designe le mauvais lot des que la pile en porte deux, ce qui
    est litteralement le risque `R12`.

    Les **trois** lots sont interroges, pas seulement la cible : un appariement
    fautif qui rendrait toujours le premier reste demasque quel que soit le lot
    demande, et demander les trois mesure aussi que la fonction ne rend pas
    toujours le meme.
    """
    brut = _brut_de_pile_mixte(calibration_en_tete=calibration_en_tete)
    attendus = ([None] if calibration_en_tete else [LOT_PREMIER[2]]) \
        + [LOT_CIBLE[2], LOT_DERNIER[2]]
    for lot_id in (LOT_CIBLE[2], LOT_DERNIER[2]):
        trouve = atelier_scan_parcours._payload_du_lot(brut, lot_id)
        assert trouve is not None, (lot_id, attendus)
        assert trouve["lot_id"] == lot_id, (lot_id, trouve["lot_id"])
    if not calibration_en_tete:
        trouve = atelier_scan_parcours._payload_du_lot(brut, LOT_PREMIER[2])
        assert trouve["lot_id"] == LOT_PREMIER[2]
    # `None` est un regime nominal et non un manque : aucune page ne porte ce
    # lot-la. C'est le volet symetrique -- sans lui, une fonction qui rendrait
    # toujours un payload passerait la moitie positive ci-dessus.
    assert atelier_scan_parcours._payload_du_lot(
        brut, "rush_z_99") is None


class _AppFeinte:
    """Le strict minimum de `CoqueTui` que `plan_d_ecriture` touche.

    Aucun ecran n'est monte ici : la mesure porte sur ce que le plan **porte**,
    et monter `textual` pour lire un chemin melangerait deux mesures.
    """

    ascii_seul = False
    sans_couleur = False
    interruption_demandee = False
    tache_en_cours = False

    def descendre(self, ecran=None) -> None:
        pass


def _parcours_sur_la_pile_mixte(tmp_path: Path, *, calibration_en_tete: bool):
    """Un `ParcoursScan` dont l'unique document est la pile mixte.

    Le triplet est pose **tel que `documents_relus` le rend** -- chemin, JSON
    brut, objet relu --, et les trois membres sont vrais : le JSON est celui que
    la fabrique serialise, et l'objet est celui que le lecteur du coeur en
    relit.
    """
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    brut = _brut_de_pile_mixte(calibration_en_tete=calibration_en_tete)
    chemin = projet / "versions" / "detection" / f"{LOT_CIBLE[2]}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    import json

    chemin.write_text(json.dumps(brut), encoding="utf-8")
    parcours = atelier_scan_parcours.ParcoursScan(_AppFeinte(), projet)
    parcours.documents = atelier_scan_parcours.documents_relus([chemin])
    assert len(parcours.documents) == 1, "le document n'est pas relisible"
    return parcours, projet


#: Combien de frames le disque porte pour le lot cible dans la mesure
#: d'integration. **Different de zero et different du compte des autres lots**,
#: sans quoi « 0 frames comptees » ne se distinguerait pas d'un comptage juste.
FRAMES_SUR_LE_DISQUE = 7


@pytest.mark.parametrize("calibration_en_tete", [True, False],
                         ids=["calibration-en-tete", "autre-lot-en-tete"])
def test_le_plan_d_ecriture_compte_les_frames_DU_BON_LOT_sur_une_pile_mixte(
        tmp_path, calibration_en_tete) -> None:
    """Le regime ou le finding **mord**, mesure de bout en bout.

    Avec un appariement par rang et une page de calibration en tete :
    `dossier_de_sortie` refuse nommement (« ce payload ne designe aucun lot »),
    `_dossier_du_lot` rend `None`, `frames_du_dossier(None)` rend zero, et
    `T6-1` annonce « 0 frames ecrites » sur un disque qui en porte -- en
    proposant de les effacer. Avec un autre lot en tete, le compte est celui du
    **voisin**.

    La mesure porte donc sur le **compte du disque**, pas seulement sur le
    chemin : c'est ce que l'operateur lit, et c'est ce qu'un effacement
    emporterait.
    """
    parcours, projet = _parcours_sur_la_pile_mixte(
        tmp_path, calibration_en_tete=calibration_en_tete)
    # Le dossier de la cible est peuple ; ceux des deux autres lots le sont
    # d'un nombre DIFFERENT -- un comptage qui lirait le mauvais dossier rendrait
    # un autre chiffre, et jamais le bon par accident.
    for rang, (_rush, _fps, lot_id) in enumerate(
            (LOT_PREMIER, LOT_CIBLE, LOT_DERNIER)):
        dossier = project_layout.scan_frames_dir_from_slug(projet, lot_id)
        dossier.mkdir(parents=True, exist_ok=True)
        combien = (FRAMES_SUR_LE_DISQUE if lot_id == LOT_CIBLE[2]
                   else rang + 1)
        for index in range(combien):
            (dossier / f"scan_{lot_id}_{index:06d}{EXTRACTED_FRAME_SUFFIX}"
             ).write_bytes(b"frame")

    confirme = atelier_scan_confirmation.PlanDEcriture(lots=(
        atelier_scan_confirmation.LotAEcrire(
            lot_id=LOT_CIBLE[2], slug=f"slug_{LOT_CIBLE[2]}", frames=3,
            frames_attendues=3),))
    plan = parcours.plan_d_ecriture(confirme)

    assert [lot.lot_id for lot in plan.lots] == [LOT_CIBLE[2]], plan
    assert plan.lots[0].dossier == project_layout.scan_frames_dir_from_slug(
        projet, LOT_CIBLE[2]), plan.lots[0].dossier
    assert atelier_scan_ecriture.frames_sur_le_disque(plan) \
        == FRAMES_SUR_LE_DISQUE


# ===========================================================================
# Finding 2 -- `rapport.refus[0]` : l'ecran nomme le PREMIER refus
# ===========================================================================

#: **Trois refus DISTINCTS**, un par lot, chacun avec son motif et sa phrase.
#: Les deux bancs qui atteignaient cette ligne remplissaient leur collection du
#: **meme** refus (`{nom: refus for nom, _ in LOTS}`) : un remplissage uniforme
#: rend `refus[0]` et `refus[-1]` indiscernables -- point 1 de la regle des
#: fabriques. Les motifs sont **lus** dans la table publiee du coeur, jamais
#: recopies.
MOTIFS_DISTINCTS = scan_write.MOTIFS_DE_REFUS_DU_DOCUMENT[:3]


def _trois_refus_distincts() -> dict:
    """`lot_id -> refus`, trois refus **distinguables par leur phrase**."""
    return {
        nom: scan_write.RefusDuDocumentDeDetection(
            f"refus du lot {nom} : {motif}", motif=motif)
        for (nom, _frames), motif in zip(fabriques_d_ecriture.LOTS,
                                         MOTIFS_DISTINCTS)}


def test_l_ecran_de_REFUS_nomme_le_PREMIER_refus_de_la_passe(banc, tmp_path
                                                             ) -> None:
    """`rapport.refus[0]`, et la mesure exige **trois refus distincts**.

    Sans eux, `[0]` et `[-1]` rendent la meme chose et le mutant survit : c'est
    ce qui s'est passe sur 242 tests. Avec eux, l'ecran doit nommer le refus du
    **premier** lot de la passe -- celui que l'operateur a vu partir en
    premier --, et pas celui du dernier.

    La mesure porte sur les **trois** champs que l'ecran relaie du coeur : le
    code, la phrase verbatim, et le fait que les trois refus sont bien remontes
    au rapport. Un ecran qui n'en montrerait qu'un sans que le rapport les porte
    tous serait une perte d'information silencieuse.
    """
    plan = fabriques_d_ecriture.plan_de_trois_lots(tmp_path)
    refus_par_lot = _trois_refus_distincts()
    # Volet symetrique de la fabrique : trois phrases DIFFERENTES. Un
    # remplissage uniforme rendrait cette mesure verte quoi qu'il arrive.
    assert len({str(refus) for refus in refus_par_lot.values()}) == 3
    factice = fabriques_d_ecriture.EcritureFactice(leve_pour=refus_par_lot)
    premier_lot = fabriques_d_ecriture.LOTS[0][0]
    dernier_lot = fabriques_d_ecriture.LOTS[-1][0]

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier_scan_ecriture.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        rapport = atelier_scan_ecriture.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=lambda _r: pytest.fail(
                "un refus sans rien d'ecrit ne monte pas le resultat"))
        await pilote.pause()
        return app.screen, rapport

    ecran, rapport = banc(fabriques_d_ecriture.coque(), scenario)
    assert type(ecran).__name__ == "EcranRefus"
    assert ecran.message == str(refus_par_lot[premier_lot]), ecran.message
    assert ecran.message != str(refus_par_lot[dernier_lot]), (
        "l'ecran nomme le DERNIER refus : `refus[0]` s'est mis a lire "
        "`refus[-1]`")
    # Et les trois refus sont bien **tous** au rapport : l'ecran en nomme un,
    # il n'en efface pas deux.
    assert len(rapport.refus) == 3 and rapport.ecrits == ()
    assert [refus.message for refus in rapport.refus] == [
        str(refus_par_lot[nom]) for nom, _frames in fabriques_d_ecriture.LOTS]
    # L'ORDRE du rapport est celui de la passe, et il est mesure : sans lui,
    # « le premier refus » n'aurait pas de referent stable.
    assert [refus.lot_id for refus in rapport.refus] == [
        nom for nom, _frames in fabriques_d_ecriture.LOTS]


# ===========================================================================
# Finding 4 -- le CYCLE DE VIE de la passe de calibration (`E3-9`)
# ===========================================================================

class CalibrationQuiAttend:
    """Un `calibrer_la_chaine` de banc qui **s'arrete au milieu de la passe**.

    C'est la seule forme qui rende le finding mesurable : la panne n'existe que
    **pendant** que le fil de travail tourne, et le double du banc voisin
    (`CalibrationFeinte`) rend trop vite pour qu'une touche tombe dedans.

    Il porte la **meme signature** que le point d'entree du coeur, mots-cles
    compris et sans `**kwargs` -- un faux permissif laisserait passer un appel
    dont un mot-cle est mal nomme.
    """

    CHAINE = "600-tiff-dddddddddddd"

    def __init__(self) -> None:
        #: Pose des que la passe est entree dans le coeur.
        self.entree = threading.Event()
        #: A poser pour la laisser finir.
        self.reprise = threading.Event()
        #: **Le compte des passes reellement lancees**, et c'est la mesure de
        #: la re-entrance. Protege : deux passes concurrentes ecriraient ce
        #: compteur depuis deux fils.
        self._verrou = threading.Lock()
        self.appels = 0

    def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                 demander_le_nom_et_le_commentaire=None,
                 confirmer_l_ecrasement=None, rappel_progression=None):
        # **Le double suit le contrat du COEUR**, mot-cle pour mot-cle : le lot
        # J1 a ajoute `rappel_progression` a `calibrer_la_chaine`, et un double
        # qui ne l'accepte pas leve DANS le fil de travail -- le banc mesure
        # alors son propre double plutot que le produit.
        with self._verrou:
            self.appels += 1
        self.entree.set()
        assert self.reprise.wait(20), "la passe n'a jamais ete liberee"
        chemin = (Path(project_dir) / "versions" / "calibration"
                  / "profil-de-banc.json")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{}", encoding="utf-8")
        return scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id=self.CHAINE, etiquette="beta",
            commentaire="", lot_correction=None, document={})


def _ouvrir_E3_9_avec_une_passe_qui_attend(tmp_path, app):
    feinte = CalibrationQuiAttend()
    parcours, projet = fabriques_du_temps_2._ouvrir_E3_9(tmp_path, app, feinte)
    return parcours, feinte, projet


async def _descendre_jusqu_a_E3_9(pilote, parcours):
    """La pile du PRODUIT : l'atelier se monte sur le menu des ateliers."""
    pilote.app.descendre()
    await pilote.pause()
    parcours.ouvrir()
    await pilote.pause()
    parcours.entrer({entree.cle: entree
                     for entree in atelier_scan.ENTREES_DU_MENU}["calibrer"])
    await pilote.pause()
    assert type(pilote.app.screen).__name__ == "EcranCalibrerLaChaine"


def test_ECHAP_pendant_la_calibration_ne_DEPILE_pas_E3_9_et_l_annonce_ARRIVE(
        tmp_path, banc) -> None:
    """La panne mesuree : **le profil ETAIT ecrit, et l'operateur ne le voyait pas**.

    `E3-9` est un `Palier` et non un `EcranExecution` : personne ne posait
    `app.tache_en_cours` sur ce chemin, donc `Échap` depilait l'ecran pendant
    que le fil tournait. `annoncer_la_passe` levait alors `NoMatches('#etat')`
    dans `call_from_thread`, ce qui remonte en `textual.worker.WorkerFailed` --
    l'application tombe, sur une passe qui avait **reussi**.

    Trois choses sont mesurees, et la troisieme est celle qui manquait a la
    revue :

    1. `Échap` **ne fait pas disparaitre** `E3-9` de la pile pendant la passe.
       Depuis le lot J2, `E3-9` n'est plus le sommet : l'ecran d'execution y
       est monte par-dessus (AC 9.4), et c'est meme une garantie de plus --
       l'ecran que `Échap` atteint est celui qui sait quoi en faire ;
    2. la passe finit et son annonce arrive ;
    3. la ligne d'etat porte **ce que la passe a produit** -- « profil ecrit le
       … · profil-de-banc.json ». C'est la mesure que l'operateur ne voyait
       jamais.
    """
    app = fabriques_du_temps_2._coque()
    parcours, feinte, _projet = _ouvrir_E3_9_avec_une_passe_qui_attend(
        tmp_path, app)
    vus = {}

    async def scenario(pilote):
        await _descendre_jusqu_a_E3_9(pilote, parcours)
        ecran_de_calibration = pilote.app.screen
        fabriques_du_temps_2._lancer_la_calibration(pilote, parcours, tmp_path)
        assert await fabriques_du_temps_2._tant_que(
            pilote, feinte.entree.is_set), "la passe n'est jamais partie"
        # **La tache est declaree**, et c'est ce qui protege la suite.
        vus["tache_pendant"] = pilote.app.tache_en_cours

        await pilote.press("escape")
        await pilote.pause()
        # **`E3-9` est desormais SOUS l'ecran d'execution**, que le lot J2
        # monte par-dessus lui pendant la passe (AC 9.4). La propriete que ce
        # banc mesure ne change pas -- `Échap` ne doit pas faire disparaitre
        # `E3-9` de la pile, sans quoi l'annonce arrive sur un ecran demonte --
        # mais elle se mesure sur la PILE et non sur son sommet.
        vus["ecran_apres_echap"] = ecran_de_calibration in pilote.app.screen_stack

        feinte.reprise.set()
        assert await fabriques_du_temps_2._tant_que(
            pilote,
            lambda: parcours.ecran_de_calibration.passe is not None), \
            "la passe n'a jamais ete annoncee"
        await pilote.pause()
        vus["ecran_final"] = type(pilote.app.screen).__name__
        vus["E3-9 dans la pile"] = ecran_de_calibration in pilote.app.screen_stack
        # **La ligne d'etat se lit sur `E3-9`, et non sur le sommet**, depuis
        # que la passe qui aboutit monte un ecran de succes par-dessus lui
        # (2026-09-06). Ce que ce banc mesure est l'ANNOTATION de `E3-9` -- le
        # chemin du profil que l'operateur ne voyait jamais --, et elle se pose
        # toujours au meme endroit ; la lire au sommet mesurerait desormais un
        # autre ecran.
        vus["etat"] = jetons.texte_affiche(
            str(ecran_de_calibration.query_one("#etat").content))
        # La tache est **oubliee** a la fin : un drapeau reste a vrai ferait
        # d'`Échap` une interruption bien apres la fin de la passe, et
        # interdirait toute passe suivante.
        vus["tache_apres"] = pilote.app.tache_en_cours
        return vus

    vus = banc(app, scenario)
    assert vus["tache_pendant"] is True
    assert vus["ecran_apres_echap"] is True, (
        "`Échap` a depile `E3-9` pendant que le fil de travail tournait : "
        "l'annonce de la passe va lever NoMatches('#etat')")
    # **Une passe qui ECRIT finit sur son ecran de succes** (retour terrain
    # d'Egan, 2026-09-06 : « pas d'ecran de succes et on revient directement a
    # la page pour lancer une calibration. Incoherent avec le reste »), et
    # `E3-9` reste dessous, annote. Les deux assertions ensemble distinguent
    # « monte par-dessus » -- la correction -- de « a remplace », qui serait le
    # defaut d'origine sous un autre nom.
    assert vus["ecran_final"] == "EcranCalibrationEcrite"
    assert vus["E3-9 dans la pile"] is True
    assert vus["tache_apres"] is False
    # **Ce que l'operateur ne voyait jamais**, et c'est la mesure du finding.
    assert "profil-de-banc.json" in vus["etat"], vus["etat"]
    assert parcours.ecran_de_calibration.passe.a_ecrit is True


def test_DEUX_entrees_ne_lancent_PAS_deux_passes_concurrentes(tmp_path, banc
                                                              ) -> None:
    """Le voisin du meme cycle de vie : « la seconde ecriture que personne n'a
    demandee ».

    Aucune garde de re-entrance n'existait, et `run_worker` etait appele sans
    exclusivite : deux `⏎` lancaient **deux ingestions du meme scan** et deux
    ecritures de profil. C'est exactement ce que le docstring de
    `QuestionDeCollision` ecarte -- et la collision, elle, n'aurait meme pas ete
    posee, les deux passes visant le meme radical.

    La mesure est le **compte d'appels du coeur**, jamais un etat d'ecran : un
    ecran peut avoir l'air identique pendant que deux fils ecrivent.
    """
    app = fabriques_du_temps_2._coque()
    parcours, feinte, _projet = _ouvrir_E3_9_avec_une_passe_qui_attend(
        tmp_path, app)
    vus = {}

    async def scenario(pilote):
        await _descendre_jusqu_a_E3_9(pilote, parcours)
        ecran = fabriques_du_temps_2._lancer_la_calibration(
            pilote, parcours, tmp_path)
        assert await fabriques_du_temps_2._tant_que(
            pilote, feinte.entree.is_set), "la premiere passe n'est pas partie"

        # Le SECOND `⏎`, sur le meme formulaire, pendant que la premiere passe
        # tourne. `traiter` rend `True` dans les deux cas -- la touche est
        # consommee --, donc c'est bien le coeur qu'il faut compter.
        assert ecran.traiter("enter") is True
        await pilote.pause()
        vus["appels_pendant"] = feinte.appels

        feinte.reprise.set()
        assert await fabriques_du_temps_2._tant_que(
            pilote,
            lambda: parcours.ecran_de_calibration.passe is not None), \
            "la passe n'a jamais ete annoncee"
        await pilote.pause()
        vus["appels_apres"] = feinte.appels
        vus["tache_apres"] = pilote.app.tache_en_cours
        return vus

    vus = banc(app, scenario)
    assert vus["appels_pendant"] == 1, (
        f"deux passes de calibration concurrentes ({vus['appels_pendant']} "
        "appels du coeur) : deux ingestions du meme scan, et une seconde "
        "ecriture que personne n'a demandee")
    assert vus["appels_apres"] == 1, vus
    # Et la passe suivante reste possible : la garde ferme la re-entrance,
    # elle ne condamne pas l'ecran.
    assert vus["tache_apres"] is False


def test_ECHAP_sur_la_COLLISION_repond_toujours_ANNULER_sous_la_garde(
        tmp_path, banc) -> None:
    """Le filet du demontage **survit** a la garde de `tache_en_cours`.

    C'est la moitie qu'une fermeture etourdie aurait cassee : des lors que la
    passe pose `app.tache_en_cours`, `CoqueTui.action_remonter` cesse de
    depiler -- elle pose `interruption_demandee` et rend. L'ecran de collision
    ne se serait donc plus jamais demonte, son filet n'aurait plus jamais
    repondu, et le fil de travail aurait attendu pour toujours : la panne exacte
    que ce filet existe pour ecarter, reintroduite par le correctif de la panne
    voisine.

    `EcranCollisionDuScan` se depile donc **lui-meme** sur `Échap`. Ce test est
    le volet croise des deux precedents, et il vaut mieux ici que dans le banc
    du temps 2 : la garde qu'il protege est posee par cette fermeture-ci.
    """
    app = fabriques_du_temps_2._coque()
    feinte = fabriques_du_temps_2.CalibrationFeinte(
        collision=("900-png-cccccccccccc", "beta"))
    parcours, _projet = fabriques_du_temps_2._ouvrir_E3_9(tmp_path, app, feinte)

    async def scenario(pilote):
        await _descendre_jusqu_a_E3_9(pilote, parcours)
        fabriques_du_temps_2._lancer_la_calibration(pilote, parcours, tmp_path)
        assert await fabriques_du_temps_2._tant_que(pilote, lambda: isinstance(
            pilote.app.screen, atelier_scan_parcours.EcranCollisionDuScan)), \
            "l'ecran de collision n'est jamais monte"
        # La tache est declaree **pendant** que la collision est posee : c'est
        # le regime ou l'ancien chemin de depilement ne marcherait plus.
        assert pilote.app.tache_en_cours is True
        await pilote.press("escape")
        assert await fabriques_du_temps_2._tant_que(
            pilote,
            lambda: parcours.ecran_de_calibration.passe is not None), \
            "le fil de travail attend encore : le filet du demontage manque"
        return parcours.ecran_de_calibration.passe

    passe = banc(app, scenario)
    assert passe.a_ecrit is False
    assert isinstance(passe.refus, atelier_scan_calibrate.CalibrationAnnulee)
    assert passe.issue == atelier_scan_calibrate.CLE_ANNULER
    # **Le coeur n'a jamais recu de « oui »** : le relais a leve avant.
    assert feinte.ecrase is None
