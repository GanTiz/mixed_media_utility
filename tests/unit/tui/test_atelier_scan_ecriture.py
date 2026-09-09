# -*- coding: utf-8 -*-
"""Story 11.6, lot E -- `E3-7` et `T6-1`, l'ecriture du Scan (AC 5, AC 6).

**Le nom du fichier est verifie globalement unique** : aucun des trois dossiers
de tests n'a d'`__init__.py`, donc deux fichiers homonymes rendent le meme nom
de module et pytest interrompt la collecte de la suite ENTIERE -- une panne
invisible quand on ne lance qu'un sous-dossier. `test_atelier_scan_ecriture.py`
n'existe nulle part ailleurs dans `tests/` au moment ou ce banc est ecrit, et
`test_frontiere_gui_tui.py::test_aucun_nom_de_FICHIER_de_test_n_est_en_double`
le mesure en continu.

Sept choses y sont mesurees, une par tache du lot :

* **E1** l'appel **heberge**, la progression **en frames** sur un total connu
  d'avance, et les **deux regimes** du rappel (`AR3`) ;
* **E2** « **aucune redetection** » (`EPIC11-ARB-6`), comptage a zero a l'AST,
  avec son volet symetrique ;
* **E3** « **aucun jalon avant la premiere ecriture** » (`EPIC7-ARB-79`),
  mesure sur un refus **REEL** du coeur et en ensemble de jalons **exactement
  vide** -- « une assertion positive laisse passer toute divergence
  supplementaire » ;
* **E4** le document de detection **intact** apres une ecriture reelle, mesure
  aux **inodes**, au **`st_mtime_ns`** et par un **temoin** depose dans le
  dossier vise. **Jamais par condensat** : sur une fixture deterministe, une
  reecriture rend exactement les memes octets -- c'est ce qui rendait vert a
  tort le banc d'`EPIC11-ARB-83` (`CLAUDE.md`, 2026-08-30). Un test de ce
  fichier le **demontre** plutot que de le citer ;
* **E5** `EcranInterruptionDeLEcriture` : **sous-classe**, **trois** issues
  chiffrees, et le module **partage** qui ne connait aucun atelier. La garde
  d'origine s'appelait « `execution.py` n'est PAS modifie » et ne mesurait que
  trois tuples, alors que le fichier EST modifie dans la vague (par la 11.5,
  AC 7.7) : finding `A3` de la couche 3, ferme ici ;
* **E6** le compte annonce est celui du **disque**, pas du dernier jalon ;
* **E7** trois lots, celui qui echoue **au milieu**.

**Regle des fabriques, appliquee sur la liste que le code PARCOURT** et non sur
celle que la fabrique ecrit :

* :func:`ecrire_les_lots` **boucle** sur `plan.lots` : le plan porte **trois**
  lots distinguables (noms, comptes de frames, dossiers), et celui qui echoue
  est **au milieu**. Un `continue` devenu `break` ferait disparaitre le
  troisieme sans un mot -- c'est le mutant de la 11.4b, paye trois fois ;
* :func:`frames_sur_le_disque` **boucle** sur la meme liste : les trois lots
  portent des comptes **differents** sur le disque, et le lot vise est au
  milieu -- un remplissage uniforme cacherait une permutation ;
* la table des refus du coeur est **parcourue** par
  `scan_write.correspondance_de_sortie` : la classe visee est prise **au
  milieu** de cette table, et deux autres l'encadrent.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path

import pytest

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

from mixed_media_utility import cli, scan_output_frames, scan_write  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.io.naming import EXTRACTED_FRAME_SUFFIX  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_extraction_ecriture as atelier_extraction,
    atelier_scan_ecriture as atelier,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin  # noqa: E402
from mixed_media_utility.tui.execution import (  # noqa: E402
    EcranInterruption,
    SurfaceExecution,
)
from mixed_media_utility.tui.panneau import MENTION_MAJORANT  # noqa: E402

from outils_frontiere import chaines_de_code, identifiants  # noqa: E402

import test_scan_calibration_application as planches  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def coque(**kwargs) -> CoqueTui:
    """Une coque a deux paliers temoins : l'ecran projet et le menu ateliers.

    Deux et non un : le retour au menu des ateliers (`EPIC11-ARB-13`) ne se
    distingue d'un retour a la racine que si la racine existe a cote.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   Q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   Q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


#: **Le rang de la cible dans la liste que le code parcourt.** Ni le premier
#: (ce qui masquerait un `find` fautif) ni le dernier (ce qui masquerait une
#: terminaison de boucle fautive) -- `CLAUDE.md`, points 2 et 2 bis.
RANG_DE_LA_CIBLE = 1

#: **Trois lots distinguables**, par leur nom, par leur compte de frames
#: promis, et par ce qu'ils posent sur le disque. Un remplissage uniforme
#: rendrait toute permutation invisible.
LOTS = (
    ("lot_a_12p5", 4),
    ("lot_b_25", 6),
    ("lot_c_50", 5),
)

#: Le lot **du milieu** : c'est lui qui echoue en E7, et lui qu'on compte en E6.
LOT_CIBLE = LOTS[RANG_DE_LA_CIBLE][0]


def plan_de_trois_lots(tmp_path: Path, *, frames_sur_le_disque=(0, 0, 0)
                       ) -> atelier.PlanDEcriture:
    """Un plan a trois lots, chacun avec son dossier de sortie **peuple**.

    `frames_sur_le_disque` pose un nombre **different** de fichiers par lot :
    le comptage du disque boucle sur les lots, et trois comptes egaux
    laisseraient passer un comptage qui ne lirait que le premier dossier.
    """
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    lots = []
    for rang, (nom, frames) in enumerate(LOTS):
        dossier = project_layout.scan_frames_dir_from_slug(projet, nom)
        dossier.mkdir(parents=True, exist_ok=True)
        for index in range(frames_sur_le_disque[rang]):
            (dossier / f"scan_{nom}_{index:06d}{EXTRACTED_FRAME_SUFFIX}"
             ).write_bytes(f"frame {index} du {nom}".encode("utf-8"))
        lots.append(atelier.LotAEcrire(
            document=projet / "scans" / nom / "detections" / "d.json",
            lot_id=nom, frames=frames, dossier=dossier))
    return atelier.PlanDEcriture(dossier_projet=projet, lots=tuple(lots))


def rapport_de_sortie(lot_id: str, *, ecrites: int, dossier: str
                      ) -> scan_output_frames.LotOutputReport:
    """Un **vrai** `LotOutputReport`, pas un double a attributs libres.

    Le construire pour de bon est ce qui garantit que la projection de la TUI
    lit des champs qui existent : un double a attributs libres rendrait vert un
    accesseur mal nomme.
    """
    return scan_output_frames.LotOutputReport(
        lot_id=lot_id, rush_id="rush-001", fps_target=25.0,
        project_id="projet_demo", template_id="t", gamut_map_id="g",
        target_colorspace="c", patch_preset_id="p",
        color_calibration_status="not_applied", output_dir=dossier,
        page_count=1, expected_frame_count=ecrites, written_frame_count=ecrites,
        synthetic_frame_count=0, observed_frame_count=ecrites, complete=True)


def ecriture_du_lot(lot_id: str, *, ecrites: int, dossier: str,
                    correction_appliquee: bool = False
                    ) -> scan_write.EcritureDuLot:
    """Un **vrai** `EcritureDuLot`, meme motif que ci-dessus."""
    return scan_write.EcritureDuLot(
        persisted=None,
        output=rapport_de_sortie(lot_id, ecrites=ecrites, dossier=dossier),
        lot_correction=None, correction_appliquee=correction_appliquee,
        profil_de_chaine_utilise=False)


class EcritureFactice:
    """Un `ecrire_depuis_le_document` de banc : il emet des jalons, et rend.

    Il porte la **meme signature** que le point d'entree du coeur, mots-cles
    compris. Un faux qui accepterait `**kwargs` laisserait passer un appel dont
    un mot-cle est mal nomme, c'est-a-dire exactement la panne que le lot `H1`
    de la 11.4 a payee (`logger` non passe, `AttributeError` a la premiere
    ligne du coeur).
    """

    def __init__(self, *, jalons_par_lot=None, leve_pour=None,
                 pendant=None) -> None:
        #: `lot_id -> suite de jalons emis`, ou `None` pour n'en emettre aucun.
        self.jalons_par_lot = dict(jalons_par_lot or {})
        #: `lot_id -> exception a lever`.
        self.leve_pour = dict(leve_pour or {})
        #: Appele pendant l'appel, une fois par lot.
        self.pendant = pendant
        self.appels: list[dict] = []

    def __call__(self, project_dir, document_path, *, overwrite=False,
                 logger=None, appliquer_la_correction=True, livrer_brut=False,
                 divergence_bypass=False, profil_designe=None,
                 origine_du_profil=None, nouvelle_version=False,
                 manifest_du_projet=None, rappel_progression=None,
                 annoncer_la_completude=None,
                 demander_l_application_de_la_correction=None,
                 confirmer_l_ecrasement=None):
        lot_id = Path(document_path).parent.parent.name
        self.appels.append({
            "project_dir": project_dir, "document_path": document_path,
            "overwrite": overwrite, "logger": logger,
            "nouvelle_version": nouvelle_version,
            "manifest_du_projet": manifest_du_projet,
            "rappel_progression": rappel_progression, "lot_id": lot_id,
        })
        if self.pendant is not None:
            self.pendant(lot_id)
        for faites, total in self.jalons_par_lot.get(lot_id, ()):
            # Le coeur ouvre le rappel dans SON emetteur : le faux fait de
            # meme, sans quoi il mesurerait un canal que le produit n'emploie
            # pas.
            if rappel_progression is not None:
                rappel_progression(faites, total)
        if lot_id in self.leve_pour:
            raise self.leve_pour[lot_id]
        return ecriture_du_lot(
            lot_id, ecrites=self.jalons_par_lot.get(lot_id, ((0, 0),))[-1][0],
            dossier=f"{project_layout.SCAN_FRAMES_DIRNAME}/{lot_id}")


# ---------------------------------------------------------------------------
# Le projet REELLEMENT detecte -- monte UNE fois, copie par test
#
# La detection reelle coute une dizaine de secondes ; les mesures qui la
# demandent (E1 regime AR3, E3 sur un refus reel, E4 sur le document intact)
# sont trois. Le modele est donc monte une seule fois par module et **copie**
# pour chaque test -- une copie donne des inodes neufs, ce qui est exactement
# ce que la photographie de E4 mesure, et aucun test ne partage l'etat d'un
# autre.
# ---------------------------------------------------------------------------

def _lot_de_trois_planches(racine: Path, nom: str) -> Path:
    """Trois planches DISTINGUABLES, la cible en position du milieu.

    Meme fabrique que celle du lot B (`test_scan_write_noyau.py`) : le code
    parcourt `document.pages`, ordonne par **rang de lecture**, et les
    `page_index` sont volontairement dissocies de cet ordre pour qu'un
    appariement par position se voie.
    """
    payloads = planches.lot_payloads(sheet_count=3, with_calibration=False)
    return planches.write_scan_folder(
        racine / nom,
        [(payloads[2], planches.PRESSES_DU_TIRAGE[0]),
         (payloads[0], planches.PRESSES_DU_TIRAGE[1]),
         (payloads[1], planches.PRESSES_DU_TIRAGE[0])])


@pytest.fixture(scope="module")
def modele_detecte(tmp_path_factory) -> Path:
    """Un projet dont la detection est **persistee**, monte une seule fois."""
    racine = tmp_path_factory.mktemp("modele")
    dossier = _lot_de_trois_planches(racine, "scan")
    projet = racine / "projet"
    assert cli.main([
        "scan", "--project", str(projet), "--scan", str(dossier),
        "--dpi", str(planches.DPI), "--lot-slug", "lot",
        cli.SCAN_DETECT_SUBCOMMAND]) == 0
    documents = sorted((projet / "scans" / "lot" / "detections").glob("*.json"))
    assert len(documents) == 1, documents
    return projet


@pytest.fixture
def projet_detecte(modele_detecte, tmp_path) -> tuple[Path, Path]:
    """Une copie fraiche du modele : `(dossier du projet, document)`."""
    projet = tmp_path / "projet"
    shutil.copytree(modele_detecte, projet)
    (document,) = sorted((projet / "scans" / "lot" / "detections")
                         .glob("*.json"))
    return projet, document


def photographie(racine: Path) -> dict[str, tuple]:
    """L'etat du sous-arbre, **aux inodes et au `st_mtime_ns`**.

    **Jamais un condensat** : une reecriture d'un contenu deterministe rend les
    memes octets, donc le meme condensat, et la mesure serait verte a tort. Ce
    qui distingue une reecriture d'une absence d'ecriture est l'**inode** (un
    remplacement atomique en cree un neuf) et l'**horodatage** (une reecriture
    en place le bouge). La taille est retenue en plus, parce qu'elle est le seul
    des trois qu'aucun systeme de fichiers ne peut rendre grossier.

    `lstat` et non `stat` : un lien symbolique substitue a un fichier est une
    ecriture, et la suivre la rendrait invisible.
    """
    photo: dict[str, tuple] = {}
    for chemin in [racine] + sorted(racine.rglob("*")):
        etat = chemin.lstat()
        cle = "." if chemin == racine else str(chemin.relative_to(racine))
        photo[cle] = (chemin.is_dir(), etat.st_ino, etat.st_mtime_ns,
                      etat.st_size)
    return photo


def divergences(avant: dict[str, tuple], apres: dict[str, tuple]) -> set[str]:
    """L'ensemble **exact** des chemins qui ont bouge -- ajouts et retraits compris.

    Rendre un ensemble plutot qu'un booleen n'est pas une commodite : « ce
    chemin diverge » ne mesure rien, « l'ensemble des chemins qui divergent est
    **exactement** {X} » mesure l'exception ET son unicite (`CLAUDE.md`).
    """
    return {cle for cle in set(avant) | set(apres)
            if avant.get(cle) != apres.get(cle)}


def condensat(chemin: Path) -> str:
    """Ce qu'une mesure **par condensat** aurait vu. Elle n'est la que pour
    etre prise en defaut : aucun test ne s'en sert pour conclure."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def lot_reel(projet: Path, document: Path, *, frames: int = 12
             ) -> atelier.PlanDEcriture:
    """Le plan d'un seul lot **reel**, avec son dossier de sortie derive."""
    brut = json.loads(document.read_text(encoding="utf-8"))
    payload = next(page["payload"] for page in brut["pages"]
                   if page.get("payload"))
    dossier = atelier.dossier_de_sortie(projet, payload)
    return atelier.PlanDEcriture(
        dossier_projet=projet,
        lots=(atelier.LotAEcrire(document=document, lot_id=payload["lot_id"],
                                 frames=frames, dossier=dossier),))


# ===========================================================================
# E1 -- l'appel heberge, la progression en frames, les deux regimes du rappel
# ===========================================================================

def test_le_coeur_est_HEBERGE_et_l_ecran_est_monte_pendant_l_appel(banc,
                                                                   tmp_path):
    """AC 5.1 : `executer_en_processus`, et la TUI est **vivante** pendant l'appel.

    Deux moities, et il faut les deux : le coeur passe par l'hote de la coque
    (`EPIC11-ARB-1` -- « le coeur est heberge, pas relance »), et l'assertion
    sur l'arbre de widgets est prise **pendant** l'appel. Apres, l'ecran serait
    monte de toute facon et la mesure ne dirait rien.
    """
    plan = plan_de_trois_lots(tmp_path)
    vu: dict = {}
    heberges: list = []
    factice = EcritureFactice()

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()

        vrai_hote = app.executer_en_processus

        def hote_espionne(fonction, *args, **kwargs):
            heberges.append(fonction)
            return vrai_hote(fonction, *args, **kwargs)

        app.executer_en_processus = hote_espionne
        factice.pendant = lambda _lot: vu.update(
            ecran=type(app.screen).__name__, tache_en_cours=app.tache_en_cours)
        atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=lambda _r: None)
        return vu

    vu = banc(coque(), scenario)
    assert heberges == [factice] * len(LOTS), (
        "le coeur doit passer par `executer_en_processus`, une fois par lot")
    assert vu["ecran"] == "EcranEcritureDuScan"
    assert vu["tache_en_cours"] is True, (
        "le coeur doit tourner avec la tache DECLAREE en cours : sinon `Echap` "
        "depile l'ecran au lieu d'ouvrir l'interruption")


def test_la_progression_est_en_FRAMES_et_son_total_est_CONNU_D_AVANCE(tmp_path):
    """AC 5.3 : l'unite, et le total pose **avant** le premier jalon.

    C'est la difference avec le temps 1, dont le cardinal n'est connu qu'apres
    l'ingestion : ici `SurfaceExecution.emetteur(total)` s'emploie, et le total
    est celui que le document promet.
    """
    assert atelier.UNITE == "frames"
    plan = plan_de_trois_lots(tmp_path)
    surface = SurfaceExecution(unite=atelier.UNITE)
    totaux: list[tuple[int, int]] = []
    surface.abonner(lambda a: totaux.append((a.faites, a.total)))

    canal = atelier.canal_de_progression(surface, plan.lots[0].frames)
    # Le total est pose par la fabrique de l'emetteur, AVANT tout jalon.
    assert surface.avancement.total == plan.lots[0].frames
    assert surface.avancement.faites == 0
    assert totaux == [], "fabriquer un emetteur n'est pas emettre un jalon"

    canal(1, plan.lots[0].frames)
    canal(4, plan.lots[0].frames)
    assert totaux == [(1, 4), (4, 4)]


def test_le_canal_est_celui_de_la_surface_et_PAS_un_second_mecanisme(tmp_path):
    """`AR3` : le canal doit etre **appelable a deux arguments**.

    L'objet rendu par `SurfaceExecution.emetteur` ne l'est pas -- il n'expose
    que `emettre(faites)` --, donc le passer tel quel au coeur eteindrait le
    canal EN SILENCE : `callable(...)` y rend faux et l'emetteur du coeur se
    declare inactif sans rien lever. La mesure porte donc sur l'arite ET sur la
    suite exacte des jalons recus, pas seulement sur l'absence de plantage.

    **Les couples attendus ont change avec la 11.4e** (AC 8.1) : la surface
    agrege desormais la PASSE. Le total vaut `4 + 6 + 5 = 15` des le premier
    jalon, et les comptes des trois lots s'additionnent -- `4`, puis `4 + 3`,
    puis `10 + 5`. Ce que la retouche ne change pas : l'arite du canal, et le
    fait que les trois lots emettent.
    """
    plan = plan_de_trois_lots(tmp_path)
    surface = SurfaceExecution(unite=atelier.UNITE)
    factice = EcritureFactice(jalons_par_lot={
        LOTS[0][0]: ((1, 4), (2, 4), (4, 4)),
        LOT_CIBLE: ((3, 6), (6, 6)),
        LOTS[2][0]: ((5, 5),)})
    recus: list[tuple[int, int, str]] = []
    surface.abonner(lambda a: recus.append((a.faites, a.total, a.unite)))

    atelier.ecrire_les_lots(plan, surface, logger=logging.getLogger("banc"),
                            ecrire=factice)

    assert [callable(appel["rappel_progression"]) for appel in factice.appels] \
        == [True] * len(LOTS)
    assert recus == [(1, 15, "frames"), (2, 15, "frames"), (4, 15, "frames"),
                     (7, 15, "frames"), (10, 15, "frames"),
                     (15, 15, "frames")]


def test_le_journal_NOMME_chaque_lot_et_ne_recule_donc_jamais(tmp_path):
    """`EPIC11-ARB-93` : le journal n'est plus remis a zero entre deux lots.

    Sans en-tete, `4/4` puis `3/6` se lirait comme un compte qui recule. Nommee,
    la rupture se lit pour ce qu'elle est : un changement de lot. La ligne est
    celle de l'atelier Extraction, **importee** et non reecrite -- deux
    redactions du meme en-tete divergeraient.
    """
    plan = plan_de_trois_lots(tmp_path)
    surface = SurfaceExecution(unite=atelier.UNITE)
    factice = EcritureFactice(jalons_par_lot={
        LOTS[0][0]: ((4, 4),), LOT_CIBLE: ((6, 6),), LOTS[2][0]: ((5, 5),)})

    atelier.ecrire_les_lots(plan, surface, logger=logging.getLogger("banc"),
                            ecrire=factice)

    lignes = list(surface.journal.dernieres(100))
    en_tetes = [ligne for ligne in lignes if ligne.startswith("-- lot ")]
    assert en_tetes == [f"-- lot {rang + 1}/3 : {nom}"
                        for rang, (nom, _frames) in enumerate(LOTS)]
    # Le journal du premier lot survit au second : c'est `ARB-93`.
    assert "4/4 frames" in lignes and "6/6 frames" in lignes


def test_les_DEUX_regimes_du_rappel_donnent_les_MEMES_frames(projet_detecte,
                                                             tmp_path):
    """`AR3`, sur le **vrai** point d'entree : optionnel, et actif.

    « Il est OPTIONNEL et son absence ne change RIEN a l'observable [...] un
    rappel qui s'eteint en silence quand on lui passe le mauvais type n'est pas
    optionnel, il est casse. » Les deux regimes sont donc mesures, et le second
    mesure que le canal est **actif** -- la suite des jalons est non vide,
    monotone, et finit sur le compte reellement ecrit.
    """
    projet_muet, document_muet = projet_detecte
    projet_dit = tmp_path / "projet-dit"
    shutil.copytree(projet_muet, projet_dit)
    (document_dit,) = sorted((projet_dit / "scans" / "lot" / "detections")
                             .glob("*.json"))

    surface_muette = SurfaceExecution(unite=atelier.UNITE)
    sans = atelier.ecrire_les_lots(
        lot_reel(projet_muet, document_muet), surface_muette,
        logger=logging.getLogger("banc"),
        # Regime 1 : le rappel n'atteint jamais le coeur.
        ecrire=lambda projet, doc, **kw: scan_write.ecrire_depuis_le_document(
            projet, doc, **{**kw, "rappel_progression": None}))

    surface_dite = SurfaceExecution(unite=atelier.UNITE)
    jalons: list[tuple[int, int]] = []
    surface_dite.abonner(lambda a: jalons.append((a.faites, a.total)))
    avec = atelier.ecrire_les_lots(
        lot_reel(projet_dit, document_dit), surface_dite,
        logger=logging.getLogger("banc"))

    assert sans.refus == () and avec.refus == (), (sans.refus, avec.refus)
    assert [lot.frames for lot in sans.ecrits] == [12]
    # L'observable ne change pas d'un octet entre les deux regimes.
    assert _frames_ecrites(projet_dit) == _frames_ecrites(projet_muet)
    # Et le canal est ACTIF : un jalon par frame ecrite, jamais zero.
    assert jalons == [(rang + 1, 12) for rang in range(12)], jalons


def _frames_ecrites(projet: Path) -> dict[str, str]:
    """Les frames du projet, **par nom relatif et par condensat des octets**.

    Ni une liste de noms ni un cardinal : deux lots dont les frames seraient
    permutees porteraient les memes noms et le meme compte. Ce sont les octets
    qui distinguent.
    """
    racine = projet / project_layout.SCAN_FRAMES_DIRNAME
    return {str(chemin.relative_to(racine)): condensat(chemin)
            for chemin in sorted(racine.rglob(f"*{EXTRACTED_FRAME_SUFFIX}"))}


# ===========================================================================
# E2 -- aucune redetection, et le volet symetrique
# ===========================================================================

#: **Les trois points d'entree que le temps 2 ne doit JAMAIS appeler**
#: (`EPIC11-ARB-6`) : « la detection ne declenche jamais l'ecriture toute
#: seule », et sa reciproque -- l'ecriture ne redetecte pas.
POINTS_D_ENTREE_DE_DETECTION = ("run_scan_detect", "detect_lot_pages",
                                "ingest_scan_lot")


def _references(chemin: Path) -> set[str]:
    """Tout nom **reellement reference** par le code, lu a l'AST.

    La mesure d'origine ne regardait que les `ast.Call`, et elle etait trop
    etroite : dans ce module meme, le point d'entree du coeur est reference
    comme **valeur par defaut** (`ecrire=scan_write.ecrire_depuis_le_document`)
    et appele par un nom local. Une garde qui ne verrait que les appels
    laisserait donc passer un `rappel=scan_detect.run_scan_detect` -- une
    redetection posee en un mot-cle. La mesure d'`outils_frontiere` est celle
    qui convient, et elle est **importee** plutot que reecrite.

    Elle lit du **code**, jamais du texte : un docstring qui cite
    `run_scan_detect` ne redetecte rien, c'est la lecon du finding `I3`.
    """
    return identifiants(chemin)


def test_le_temps_2_ne_reference_AUCUN_point_d_entree_de_DETECTION():
    """AC 5.2 : comptage a **zero**, a l'AST, sur le module du temps 2."""
    vus = _references(Path(atelier.__file__))
    assert vus & set(POINTS_D_ENTREE_DE_DETECTION) == set(), sorted(vus)


def test_la_mesure_de_NON_REDETECTION_mord_bien(tmp_path):
    """Volet symetrique : sans lui, un comptage a zero sur une mesure aveugle
    serait vert et ne mesurerait rien.

    On donne a la meme mesure un module qui, lui, appelle bien les trois points
    d'entree : elle doit les trouver **tous les trois**.
    """
    faux = tmp_path / "faux.py"
    faux.write_text(
        "from mixed_media_utility import scan_detect\n"
        "def passe(rappel=scan_detect.run_scan_detect):\n"
        "    detect_lot_pages()\n"
        "    scan_ingest.ingest_scan_lot()\n", encoding="utf-8")
    # Les trois formes sont vues : un appel, un attribut, et une reference
    # posee en **valeur par defaut** -- la forme qu'une mesure sur les seuls
    # `ast.Call` laisserait passer.
    assert _references(faux) & set(POINTS_D_ENTREE_DE_DETECTION) == set(
        POINTS_D_ENTREE_DE_DETECTION)
    # ... et le module du temps 2 est bien lu par la meme mesure, non vide.
    assert "ecrire_depuis_le_document" in _references(Path(atelier.__file__)), (
        "volet symetrique : la mesure lit bien le code du module vise")


def test_le_module_du_temps_2_n_importe_PAS_cli():
    """AC 9.1, verifie explicitement sur le module neuf plutot que suppose."""
    source = Path(atelier.__file__)
    arbre = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    importes: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            importes.add(noeud.module or "")
            importes.update(alias.name for alias in noeud.names)

    assert not any(nom == "cli" or nom.endswith(".cli") for nom in importes), (
        sorted(importes))
    assert "scan_write" in importes, (
        "volet symetrique : la mesure lit bien les imports du module")


def test_le_module_du_temps_2_ne_relit_AUCUN_document_de_detection():
    """AC 2.8, cote consommateur : `gui/` en porte deja deux redactions.

    Une troisieme dans `tui/` serait la faute qu'`EPIC11-ARB-108` nomme -- « un
    mecanisme, un lieu ». Le module recoit des **chemins** et laisse le coeur
    relire.
    """
    vus = _references(Path(atelier.__file__))
    assert "scan_previz_from_json_dict" not in vus
    assert "loads" not in vus, (
        "aucun `json.loads` : ce module ne decode aucun document")
    assert "scan_previz" not in vus, (
        "le module ne connait meme pas le lecteur de previz")


def test_aucun_terme_de_nos_documents_de_decision_a_l_ecran():
    """`EPIC11-ARB-28` : ces mots ne s'affichent jamais, comptage a zero.

    La mesure porte sur les **chaines de code**, docstrings exclus : un
    commentaire qui explique pourquoi le mot est proscrit le porte, et un grep
    de texte s'y ferait affaiblir.
    """
    textes = chaines_de_code(Path(atelier.__file__))
    for mot in ("palier", "parcours a part", "feuille cli",
                "point de jugement"):
        assert [t for t in textes if mot in t.lower()] == [], mot
    assert "palier" in "Remonter au palier 0".lower(), (
        "volet symetrique : la mesure de vocabulaire mord")


def test_aucun_texte_du_module_ne_dit_ECHEC():
    """`DESIGN.md` §9 : un refus se nomme par son code et par son motif.

    « Echec » ne dit ni ce qui a ete refuse ni ce qui reste a faire. Le module
    ne redige aucune phrase de refus -- il relaie celle du coeur --, et cette
    mesure garde la porte fermee.
    """
    textes = chaines_de_code(Path(atelier.__file__))
    fautives = [t for t in textes
                if "echec" in t.lower() or "échec" in t.lower()]
    assert fautives == [], fautives
    assert "echec" in "un echec de plus".lower(), (
        "volet symetrique : la mesure mord")


# ===========================================================================
# E3 -- aucun jalon avant la premiere ecriture, sur un refus REEL
# ===========================================================================

def test_un_refus_REEL_ne_produit_AUCUN_jalon(projet_detecte):
    """AC 5.4 (`EPIC7-ARB-79`) : l'ensemble des jalons est **exactement vide**.

    **Un refus reel, jamais un double** : c'est le coeur qui doit refuser avant
    la boucle d'ecriture, et un faux qui « n'emet rien » mesurerait le faux. Le
    document vise n'existe pas -- premier des huit motifs de la table publiee --,
    donc `lire_le_document_de_detection` refuse a sa premiere garde.

    **Et l'ensemble est mesure vide, pas « sans le jalon X »** : « une assertion
    positive laisse passer toute divergence supplementaire ».
    """
    projet, document = projet_detecte
    plan = atelier.PlanDEcriture(
        dossier_projet=projet,
        lots=(atelier.LotAEcrire(document=projet / "aucun-document.json",
                                 lot_id="lot", frames=12),))
    surface = SurfaceExecution(unite=atelier.UNITE)
    jalons: list[tuple[int, int]] = []
    surface.abonner(lambda a: jalons.append((a.faites, a.total)))

    rapport = atelier.ecrire_les_lots(plan, surface,
                                      logger=logging.getLogger("banc"))

    assert jalons == [], jalons
    assert rapport.ecrits == ()
    (refus,) = rapport.refus
    assert refus.motif == scan_write.REFUS_DOCUMENT_INTROUVABLE
    assert refus.code == "RefusDuDocumentDeDetection"
    assert refus.lot_id == "lot"
    assert "Aucune frame n'a ete ecrite." in refus.message
    assert list((projet / project_layout.SCAN_FRAMES_DIRNAME)
                .rglob(f"*{EXTRACTED_FRAME_SUFFIX}")) == []
    # Volet symetrique : la sonde a jalons FONCTIONNE -- sans lui, un abonnement
    # casse rendrait ce test vert quoi qu'il arrive.
    surface.noter(1, 12)
    assert jalons == [(1, 12)]


def test_un_refus_PLUS_PROFOND_ne_produit_pas_davantage_de_jalon(projet_detecte):
    """Le meme invariant, une garde plus loin dans l'ordre d'`EPIC5-ARB-34`.

    Le condensat d'une source diverge : la lecture du document a **abouti**, et
    c'est la verification des octets qui refuse. Un jalon emis ici voudrait dire
    que l'ecriture a commence avant que les sources ne soient verifiees.
    """
    projet, document = projet_detecte
    pages = sorted((projet / "scans" / "lot").glob("page_*.tiff"))
    assert len(pages) == 3, pages
    # La page **du milieu** est celle qu'on remplace : ni la premiere ni la
    # derniere de la liste que la verification parcourt.
    pages[RANG_DE_LA_CIBLE].write_bytes(pages[0].read_bytes())

    surface = SurfaceExecution(unite=atelier.UNITE)
    jalons: list = []
    surface.abonner(jalons.append)
    rapport = atelier.ecrire_les_lots(
        lot_reel(projet, document), surface, logger=logging.getLogger("banc"))

    assert jalons == []
    (refus,) = rapport.refus
    assert refus.motif == scan_write.REFUS_SOURCE_CONDENSAT_DIVERGENT


def test_une_exception_HORS_TABLE_traverse(tmp_path):
    """Deguiser une panne inconnue en refus metier ferait lire un motif
    rassurant sur un bug. La table nomme, ou l'on relaie."""
    plan = plan_de_trois_lots(tmp_path)
    factice = EcritureFactice(leve_pour={LOTS[0][0]: ZeroDivisionError("bug")})
    with pytest.raises(ZeroDivisionError):
        atelier.ecrire_les_lots(plan, SurfaceExecution(unite=atelier.UNITE),
                                logger=logging.getLogger("banc"),
                                ecrire=factice)


def test_refus_de_reconnait_la_classe_du_MILIEU_de_la_table():
    """Regle des fabriques, sur la table que le code **parcourt**.

    `scan_write.correspondance_de_sortie` boucle sur `CODES_DE_SORTIE` et rend
    la premiere entree qui correspond. Une cible en premiere position
    laisserait passer une recherche qui rendrait toujours la premiere ; en
    derniere, une boucle qui s'arreterait trop tot. On la prend donc au milieu,
    et deux autres l'encadrent.
    """
    table = atelier.CODES_DE_SORTIE
    assert len(table) >= 3, table
    assert table is scan_write.CODES_DE_SORTIE, (
        "la table est LUE du coeur, par identite : une copie divergerait")
    milieu = len(table) // 2
    classe, code = table[milieu]
    refus = atelier.refus_de(classe("un motif du coeur"))
    assert refus is not None
    assert refus.code == classe.__name__
    assert refus.message == "un motif du coeur"
    assert refus.code_retour == code
    # Les deux voisines existent : la cible est bien encadree.
    assert table[milieu - 1][0] is not classe
    assert table[milieu + 1][0] is not classe
    # Et ce que la table ne nomme pas ne devient jamais un refus metier.
    assert atelier.refus_de(ZeroDivisionError("bug")) is None


# ===========================================================================
# E4 -- le document de detection reste INTACT
# ===========================================================================

def test_une_ecriture_REELLE_laisse_le_document_INTACT(projet_detecte):
    """AC 5.5 : ni modifie, ni supprime, ni double.

    **Aux inodes, au `st_mtime_ns` et par un temoin** : un condensat ne
    prouverait rien ici, la fixture etant deterministe. Le temoin est depose
    **dans le dossier des detections** -- un dossier reecrit le perdrait, quel
    que soit le contenu des fichiers qu'il porte --, et la divergence est
    mesuree en ensemble **exactement vide**.
    """
    projet, document = projet_detecte
    temoin = document.parent / "temoin.txt"
    temoin.write_text("depose avant l'ecriture", encoding="utf-8")
    avant = photographie(document.parent)

    rapport = atelier.ecrire_les_lots(
        lot_reel(projet, document), SurfaceExecution(unite=atelier.UNITE),
        logger=logging.getLogger("banc"))

    assert rapport.refus == () and len(rapport.ecrits) == 1
    assert rapport.ecrits[0].frames == 12
    assert divergences(avant, photographie(document.parent)) == set(), (
        "le dossier des detections doit etre inchange, en ensemble EXACT")
    assert temoin.read_text(encoding="utf-8") == "depose avant l'ecriture"
    # Volet symetrique : la passe a bel et bien ecrit ailleurs. Sans lui, un
    # appel qui n'aurait rien fait passerait la mesure ci-dessus.
    assert len(_frames_ecrites(projet)) == 12


def test_la_mesure_du_document_INTACT_mord_sur_une_reecriture_a_octets_egaux(
        projet_detecte):
    """La demonstration que le condensat ne prouve rien, plutot que sa citation.

    On reecrit le document avec **exactement les memes octets** : le condensat
    ne bouge pas, l'inode ou l'horodatage, si. C'est le defaut qui rendait vert
    a tort le banc d'`EPIC11-ARB-83`.
    """
    _projet, document = projet_detecte
    octets = document.read_bytes()
    empreinte = condensat(document)
    avant = photographie(document.parent)

    document.write_bytes(octets)

    assert condensat(document) == empreinte, (
        "les octets sont identiques : un condensat ne verrait rien")
    assert divergences(avant, photographie(document.parent)) == {document.name}


# ===========================================================================
# E5 -- `T6-1` : trois issues chiffrees, et `execution.py` non modifie
# ===========================================================================

def test_l_interruption_de_l_ecriture_porte_TROIS_issues_chiffrees():
    """AC 6.2 et AC 6.4 : les trois issues, avec le compte **reel**.

    Contrairement au temps 1 -- qui n'en garde que deux, une detection
    n'ecrivant rien --, `T6-1` est le cas nominal pour lequel les trois ont ete
    ecrites. Les libelles sont ceux de la maquette, verbatim.
    """
    issues = atelier.issues_de_l_interruption(40)
    assert [(issue.cle, issue.libelle, issue.ecrit) for issue in issues] == [
        ("garder", "Interrompre et garder les 40 frames", False),
        ("effacer", "Interrompre et effacer les 40 frames", True),
        ("reprendre", "Reprendre l'écriture", False),
    ]
    assert issues[2].cle == EcranInterruption.REPRENDRE, (
        "la cle de reprise est celle de l'ecran d'execution : une seconde "
        "chaine divergerait et `Echap` cesserait de reprendre")


@pytest.mark.parametrize("frames, attendu", [
    (40, "les 40 frames"),
    (2, "les 2 frames"),
    (1, "la frame déjà écrite"),
    (0, "ce qui est déjà écrit"),
])
def test_le_compte_des_issues_reste_DICIBLE_a_tout_regime(frames, attendu):
    """« Les 0 frames » serait du charabia, « la 1 frames » aussi.

    A zero il n'y a pas de compte a donner, et la phrase retombe sur celle
    qu'`EcranInterruption` porte deja. Ce n'est pas une exception a l'AC 6.4 :
    le compte reel de zero frame n'est pas un nombre a afficher.
    """
    assert atelier.compte_de_frames(frames) == attendu
    for issue in atelier.issues_de_l_interruption(frames)[:2]:
        assert issue.libelle.endswith(attendu)


def test_l_ecran_d_interruption_est_une_SOUS_CLASSE_et_n_a_rien_redonne():
    """AC 6.3 : on herite du clavier, du rendu et du `Echap`.

    La mesure porte sur ce que la sous-classe **ne** redefinit pas : redonner
    `traiter` ou `etat` serait une seconde redaction du comportement partage,
    exactement ce que le patron d'`EcranInterruptionDeDetection` evite.
    """
    assert issubclass(atelier.EcranInterruptionDeLEcriture, EcranInterruption)
    propres = set(vars(atelier.EcranInterruptionDeLEcriture))
    assert propres & {"traiter", "etat", "valider", "contenu", "rafraichir"} \
        == set(), sorted(propres)
    assert "ISSUES" in propres, (
        "volet symetrique : la sous-classe substitue bien ses issues")


#: Le module PARTAGE avec l'atelier Extraction, celui que l'AC 6.3 protege.
SOURCE_PARTAGEE = (Path(__file__).resolve().parents[3] / "src"
                   / "mixed_media_utility" / "tui" / "execution.py")


def _mots_qui_NOMMENT_un_atelier(paquet_tui) -> set[str]:
    """Les mots qui designent un atelier, lus sur le PAQUET et non ecrits ici.

    Les deriver du paquet plutot que de les recopier evite la seconde redaction
    qu'un troisieme atelier rendrait fausse en silence : le jour ou
    `atelier_montage.py` arrive, la frontiere le connait sans qu'on la touche.
    """
    mots = {"atelier"}
    for chemin in paquet_tui.glob("atelier_*.py"):
        mots.add(chemin.stem.split("_")[1])
    assert len(mots) >= 3, (
        "une frontiere posee sur un paquet sans atelier serait verte sans rien "
        f"mesurer (trouve {sorted(mots)})")
    return mots


def _noms_definis_au_niveau_module(arbre: ast.Module) -> list[str]:
    """Ce que le module EXPOSE : classes, fonctions, constantes.

    `outils_frontiere.identifiants` ne suffit pas ici : il lit les noms
    **references** (`ast.Name`, attributs, alias d'import) et ne voit ni un
    `def` ni une `class`, c'est-a-dire exactement la forme qu'aurait une
    fonction du Scan ajoutee au module partage.
    """
    noms = []
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.append(noeud.name)
        elif isinstance(noeud, ast.Assign):
            noms += [c.id for c in noeud.targets if isinstance(c, ast.Name)]
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target,
                                                             ast.Name):
            noms.append(noeud.target.id)
    return noms


def _ce_que_le_module_partage_SAIT_des_ateliers(source: str,
                                                mots: set[str]) -> list[str]:
    """Les endroits ou `source` nomme un atelier -- en CODE, jamais en prose.

    La distinction n'est pas un detail : `execution.py` parle du scan d'une
    planche dans deux commentaires, et c'est legitime -- un module generique a
    le droit d'expliquer a quoi il sert. Ce qu'il n'a pas le droit de faire,
    c'est d'en **dependre** ou d'en **exposer** quelque chose. Un grep de texte
    confondrait les deux et se ferait affaiblir a la premiere prose (c'est le
    motif fondateur d'`outils_frontiere`).
    """
    arbre = ast.parse(source)
    fautes = []

    def _mord(texte: str) -> bool:
        return any(mot in texte.lower() for mot in mots)

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            if _mord(noeud.module or ""):
                fautes.append(f"import du module `{noeud.module}`")
            fautes += [f"import du nom `{a.name}`" for a in noeud.names
                       if _mord(a.name)]
        elif isinstance(noeud, ast.Import):
            fautes += [f"import du module `{a.name}`" for a in noeud.names
                       if _mord(a.name)]
    fautes += [f"nom expose `{nom}`"
               for nom in _noms_definis_au_niveau_module(arbre) if _mord(nom)]
    return fautes


def test_les_TROIS_issues_generiques_d_EcranInterruption_sont_INTACTES():
    """AC 6.3 : les trois issues du module partage, telles quelles.

    **Ce test s'appelait `test_execution_py_n_est_PAS_modifie_par_ce_lot`, et
    il ne mesurait pas cela** -- finding `A3` de la couche 3 de la vague 4. Il
    n'asserte que trois tuples : une fonction ajoutee, un rendu change ou une
    constante retiree ailleurs dans `execution.py` le laissaient vert. Pire, le
    fichier **est** modifie dans le perimetre de la vague (`+63 / -5`, commit
    `db595ee`), par la story 11.5 et son AC 7.7 : le nom du test affirmait donc
    le contraire de ce que le depot montre. Une garde qui porte un nom qu'elle
    ne tient pas est pire qu'une garde absente, parce qu'elle rassure.

    Il porte desormais le nom de ce qu'il mesure. La propriete « ce lot ne
    touche pas ce fichier » est une propriete du **diff**, pas de l'execution :
    elle se releve a la relecture. Ce qui reste mesurable a l'execution --
    l'invariant que l'AC 6.3 vise vraiment -- se partage en deux : les trois
    issues generiques intactes (ici), et le module partage qui ne connait aucun
    atelier (test suivant).

    (La docstring d'origine disait « AC 6.5 » la ou la clause est en AC 6.3.)
    """
    assert [(issue.cle, issue.libelle, issue.ecrit)
            for issue in EcranInterruption.ISSUES] == [
        ("garder", "Interrompre et garder ce qui est deja ecrit", False),
        ("effacer", "Interrompre et effacer ce qui est deja ecrit", True),
        ("reprendre", "Reprendre l'execution", False),
    ]


def test_le_module_PARTAGE_ne_connait_AUCUN_atelier(paquet_tui):
    """AC 6.3, le versant que le nom d'avant promettait sans le tenir.

    Ce que « ne pas toucher `execution.py` » protege n'est pas l'horodatage du
    fichier -- la 11.5 l'a legitimement edite pour y ajouter un ouvreur
    **generique** --, c'est que le module partage ne se **specialise** pour
    aucun atelier. C'est cela qui serait la contention que la regle de
    decoupage interdit, et c'est cela qui se mesure : aucune dependance vers un
    module d'atelier, aucun nom d'atelier expose.

    La sous-classe `EcranInterruptionDeLEcriture` existe justement pour que
    cette frontiere puisse rester a zero.
    """
    fautes = _ce_que_le_module_partage_SAIT_des_ateliers(
        SOURCE_PARTAGEE.read_text(encoding="utf-8"),
        _mots_qui_NOMMENT_un_atelier(paquet_tui))
    assert fautes == [], f"{SOURCE_PARTAGEE.name} : {fautes}"


def test_le_detecteur_de_SPECIALISATION_trouve_les_formes_plantees(paquet_tui):
    """Volet symetrique : un detecteur casse serait vert sur tout.

    Les trois formes sont celles qu'une specialisation prendrait reellement :
    un import de module d'atelier, un import d'un nom d'atelier, et une
    fonction du Scan posee dans le module partage. La troisieme est exactement
    le mutant que le test d'avant laissait passer.
    """
    mots = _mots_qui_NOMMENT_un_atelier(paquet_tui)
    assert _ce_que_le_module_partage_SAIT_des_ateliers(
        "from .panneau import Issue\n\n\nclass EcranInterruption:\n    pass\n",
        mots) == [], "la forme generique doit passer"
    for plante in (
        "from .atelier_scan_ecriture import UNITE\n",
        "from . import atelier_extraction\n",
        "def issues_de_l_interruption_du_scan():\n    return ()\n",
        "CLE_DU_SCAN = 'scan'\n",
    ):
        assert _ce_que_le_module_partage_SAIT_des_ateliers(plante, mots), (
            f"specialisation non vue : {plante!r}")
    # ... et la PROSE ne mord pas : c'est ce qui distingue cette frontiere d'un
    # grep, et `execution.py` porte deja deux commentaires qui disent `scan`.
    assert _ce_que_le_module_partage_SAIT_des_ateliers(
        '"""Le scan de la planche muette est ouvert ici."""\n'
        "# c'est ce que le scan attend\n"
        "MOTIF = 'Ce fichier n est plus la'\n", mots) == []


def test_l_issue_qui_EFFACE_n_est_jamais_celle_du_curseur_au_montage(tmp_path):
    """AC 6.5 : invariant leve par `ChoixExclusif`, jamais reecrit ici.

    Depuis `EPIC11-ARB-45` la validation suit le CURSEUR : un curseur pose au
    montage sur l'issue qui ecrit rendrait la destruction atteignable en UNE
    frappe.
    """
    ecran = atelier.EcranInterruptionDeLEcriture(
        atelier.EcranEcritureDuScan(
            SurfaceExecution(unite=atelier.UNITE),
            compter_le_disque=lambda: 40, frames_du_plan=186
        ).panneau_de_ce_qui_est_ecrit(), 40)
    assert ecran.choix.retenue is None
    assert ecran.choix.action_qui_ecrit.cle == atelier.CLE_EFFACER
    assert ecran.choix.issues[ecran.choix.curseur].ecrit is False
    assert ecran.choix.issues[ecran.choix.curseur].cle == atelier.CLE_GARDER


def test_echap_pendant_l_ecriture_ouvre_NOTRE_interruption(banc, tmp_path):
    """`Echap` empile, il ne remonte pas -- et il monte NOTRE ecran."""
    plan = plan_de_trois_lots(tmp_path, frames_sur_le_disque=(2, 7, 3))

    async def scenario(pilote):
        app = pilote.app
        atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        app.tache_en_cours = True
        avant = (app.passages_empiles, app.rang)
        await pilote.press("escape")
        await pilote.pause()
        return avant, (app.passages_empiles, app.rang), app.screen

    avant, apres, ecran = banc(coque(), scenario)
    assert apres[0] == avant[0] + 1, "on a empile, on n'a pas depile"
    assert apres[1] == avant[1], "une interruption ne change pas de palier"
    assert type(ecran) is atelier.EcranInterruptionDeLEcriture
    assert type(ecran) is not EcranInterruption


def test_ouvrir_l_interruption_n_arrete_RIEN(banc, tmp_path):
    """AC 6.1 : la progression avance encore derriere l'ecran monte."""
    plan = plan_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        app.tache_en_cours = True
        ecran.ouvrir_l_interruption()
        await pilote.pause()
        ecran.surface.noter(7, 15)
        await pilote.pause()
        return (type(app.screen), ecran.surface.avancement.faites,
                app.interruption_demandee)

    classe, faites, demandee = banc(coque(), scenario)
    assert classe is atelier.EcranInterruptionDeLEcriture
    assert faites == 7, "le canal du coeur continue de noter derriere l'ecran"
    assert demandee is False, "ouvrir l'ecran ne demande rien"


def test_reprendre_depile_et_ne_demande_AUCUNE_interruption(banc, tmp_path):
    """« Reprendre » est de la navigation : la passe ne doit rien en savoir."""
    plan = plan_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        app.tache_en_cours = True
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        interruption.choix.viser(EcranInterruption.REPRENDRE)
        interruption.valider()
        await pilote.pause()
        return (type(app.screen), app.interruption_demandee,
                ecran.issue_retenue)

    classe, demandee, retenue = banc(coque(), scenario)
    assert classe is atelier.EcranEcritureDuScan, "on est revenu a `E3-7`"
    assert demandee is False
    assert retenue is None, "reprendre n'est pas une issue d'interruption"


@pytest.mark.parametrize("cle", [atelier.CLE_GARDER, atelier.CLE_EFFACER])
def test_les_deux_autres_issues_DEMANDENT_l_interruption_et_se_NOMMENT(
        banc, tmp_path, cle):
    """Le drapeau que la passe consulte, **et** la cle retenue.

    La cle est retenue parce que garder et effacer ne demandent pas la meme
    suite : le jour ou l'effacement existera (`EPIC11-ARB-89`, story 11.11), il
    se branchera sur ce fait plutot que sur une intention perdue.
    """
    plan = plan_de_trois_lots(tmp_path)

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        app.tache_en_cours = True
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        interruption.choix.viser(cle)
        interruption.valider()
        await pilote.pause()
        return app.interruption_demandee, ecran.issue_retenue

    demandee, retenue = banc(coque(), scenario)
    assert demandee is True
    assert retenue == cle


def test_une_interruption_demandee_ENTRE_deux_lots_arrete_la_passe(tmp_path):
    """La granularite est celle-la, et le dire vaut mieux que de la promettre.

    A l'interieur d'un lot, l'appel au coeur est synchrone et n'offre aucun
    point d'arret. Le lot en cours va donc a son terme, et c'est le **suivant**
    qui n'est pas ouvert.
    """
    plan = plan_de_trois_lots(tmp_path)
    demandee: list[bool] = [False]
    factice = EcritureFactice(
        jalons_par_lot={nom: ((frames, frames),) for nom, frames in LOTS},
        pendant=lambda lot: demandee.__setitem__(0, lot == LOTS[0][0]))

    rapport = atelier.ecrire_les_lots(
        plan, SurfaceExecution(unite=atelier.UNITE),
        logger=logging.getLogger("banc"), ecrire=factice,
        interrompu=lambda: demandee[0])

    assert rapport.interrompu is True
    assert [lot.lot_id for lot in rapport.ecrits] == [LOTS[0][0]], (
        "le lot en cours va a son terme ; le suivant n'est pas ouvert")
    assert [appel["lot_id"] for appel in factice.appels] == [LOTS[0][0]]


# ===========================================================================
# E6 -- le compte annonce est celui du DISQUE, jamais du dernier jalon
# ===========================================================================

def test_le_cartouche_compte_le_DISQUE_et_PAS_le_dernier_jalon(banc, tmp_path):
    """AC 6.6 : les deux comptes sont mesures, et refuses confondus.

    Annoncer « 40 frames » et en effacer 41 serait une destruction que l'ecran
    n'a pas annoncee. Le disque porte **12** frames (2 + 7 + 3), le dernier
    jalon en annonce **5** : c'est 12 qui doit s'afficher, au cartouche comme
    dans les issues.
    """
    plan = plan_de_trois_lots(tmp_path, frames_sur_le_disque=(2, 7, 3))
    assert atelier.frames_sur_le_disque(plan) == 12

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        # Le dernier jalon dit AUTRE CHOSE que le disque, delibérément.
        ecran.surface.noter(5, 15)
        app.tache_en_cours = True
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        return (ecran.panneau_de_ce_qui_est_ecrit(),
                ecran.surface.avancement.faites, interruption)

    panneau, dernier_jalon, interruption = banc(coque(), scenario)
    assert dernier_jalon == 5, "le jalon dit bien autre chose que le disque"
    assert panneau.titre == atelier.TITRE_DE_CE_QUI_EST_ECRIT
    assert [(ligne.libelle, ligne.valeur, ligne.unite)
            for ligne in panneau.lignes] == [
        ("Frames écrites", 12, "frames"),
        ("Frames restantes", 15 - 12, "frames"),
        (atelier.LIBELLE_DOCUMENT, atelier.PHRASE_DOCUMENT_VALIDE, None),
    ]
    # Aucun majorant : ces chiffres sont MESURES sur le disque.
    assert all(not ligne.majorant for ligne in panneau.lignes)
    assert MENTION_MAJORANT not in "".join(l.chiffre for l in panneau.lignes)
    # Et les issues portent le MEME chiffre que le cartouche, pas un second.
    assert interruption.frames == 12
    assert interruption.choix.issues[0].libelle.endswith("les 12 frames")


def test_le_comptage_du_disque_LIT_LES_TROIS_dossiers_du_plan(tmp_path):
    """Regle des fabriques : trois lots, comptes **differents**, cible au milieu.

    Trois comptes egaux laisseraient passer un comptage qui ne lirait que le
    premier dossier, ou qui s'arreterait au deuxieme. Le lot vise -- celui du
    milieu -- porte a lui seul la majorite des frames, donc un `break` sur la
    liste parcourue se verrait sur le total.
    """
    plan = plan_de_trois_lots(tmp_path, frames_sur_le_disque=(2, 7, 3))
    par_lot = [atelier.frames_du_dossier(lot.dossier) for lot in plan.lots]
    assert par_lot == [2, 7, 3]
    assert plan.lots[RANG_DE_LA_CIBLE].lot_id == LOT_CIBLE
    assert atelier.frames_sur_le_disque(plan) == 12
    # Un dossier absent vaut zero, il ne fait pas tomber l'ecran.
    assert atelier.frames_du_dossier(tmp_path / "nulle-part") == 0
    assert atelier.frames_du_dossier(None) == 0
    # Volet symetrique : seuls les fichiers de frames comptent.
    (plan.lots[0].dossier / "notes.txt").write_text("pas une frame",
                                                    encoding="utf-8")
    assert atelier.frames_du_dossier(plan.lots[0].dossier) == 2


def test_le_dossier_de_sortie_se_derive_par_les_fonctions_du_COEUR(
        projet_detecte):
    """Le document en regime `detected` ne porte PAS `output_dir_relative`.

    Le lecteur de `scan_previz` le refuse verbatim (« n'a pas de sens en regime
    'detected' »), et c'est pourquoi la derivation existe. Elle passe par
    `derive_lot_dir_slug` **et** `output_frames_dir_from_slug`, jamais par une
    recomposition de chemin.
    """
    projet, document = projet_detecte
    brut = json.loads(document.read_text(encoding="utf-8"))
    assert brut["state"] == "detected"
    assert brut["subject"].get("output_dir_relative") is None
    payload = next(page["payload"] for page in brut["pages"]
                   if page.get("payload"))

    dossier = atelier.dossier_de_sortie(projet, payload)

    assert dossier.parent == projet / project_layout.SCAN_FRAMES_DIRNAME
    assert dossier.name == scan_output_frames.derive_lot_dir_slug(
        rush_id=payload["rush_id"], fps_target=payload["fps_target"],
        lot_id=payload["lot_id"])
    # Et c'est bien la que le coeur ecrit : mesure sur une passe reelle.
    atelier.ecrire_les_lots(lot_reel(projet, document),
                            SurfaceExecution(unite=atelier.UNITE),
                            logger=logging.getLogger("banc"))
    assert atelier.frames_du_dossier(dossier) == 12


# ===========================================================================
# E7 -- trois lots, celui qui echoue AU MILIEU
# ===========================================================================

def test_un_lot_qui_ECHOUE_AU_MILIEU_n_emporte_pas_les_suivants(tmp_path):
    """AC 5.7 : le mutant `continue` -> `break`, paye trois fois par la 11.4b.

    Sur trois lots dont le **deuxieme** est refuse, un `break` ferait
    disparaitre le troisieme *sans un mot* : ni son ecriture, ni son refus. La
    position de la cible est verifiee **sur la liste que le code parcourt**
    (`plan.lots`), jamais sur celle que la fabrique ecrit -- c'est la cause
    instrumentee du mutant de la 11.4b.

    Trois lots et non deux : a deux, « au milieu » et « en dernier » sont
    indiscernables (`CLAUDE.md`, point 2 bis).
    """
    plan = plan_de_trois_lots(tmp_path)
    # La position, sur la liste PARCOURUE.
    assert len(plan.lots) == 3
    assert [lot.lot_id for lot in plan.lots] == [nom for nom, _f in LOTS]
    assert plan.lots[RANG_DE_LA_CIBLE].lot_id == LOT_CIBLE
    assert RANG_DE_LA_CIBLE not in (0, len(plan.lots) - 1)

    refus_du_coeur = scan_write.RefusDuDocumentDeDetection(
        "Document de detection perime. Aucune frame n'a ete ecrite.",
        motif=scan_write.REFUS_SOURCE_CONDENSAT_DIVERGENT)
    factice = EcritureFactice(
        jalons_par_lot={nom: ((frames, frames),) for nom, frames in LOTS},
        leve_pour={LOT_CIBLE: refus_du_coeur})

    rapport = atelier.ecrire_les_lots(
        plan, SurfaceExecution(unite=atelier.UNITE),
        logger=logging.getLogger("banc"), ecrire=factice)

    # Les trois lots ont ete OUVERTS : c'est ce qu'un `break` detruirait.
    assert [appel["lot_id"] for appel in factice.appels] == [
        nom for nom, _f in LOTS]
    # Le premier et le TROISIEME sont ecrits, le deuxieme est refuse.
    assert [(lot.lot_id, lot.frames) for lot in rapport.ecrits] == [
        (LOTS[0][0], LOTS[0][1]), (LOTS[2][0], LOTS[2][1])]
    (refus,) = rapport.refus
    assert refus.lot_id == LOT_CIBLE, (
        "le refus doit nommer le lot du MILIEU, pas le premier de la liste")
    assert refus.motif == scan_write.REFUS_SOURCE_CONDENSAT_DIVERGENT
    assert rapport.frames == LOTS[0][1] + LOTS[2][1]


def test_un_echec_du_PREMIER_lot_n_emporte_pas_les_deux_autres(tmp_path):
    """Le symetrique du precedent : sans lui, un `return` sur refus passerait.

    Le test ci-dessus mesure qu'un echec au milieu laisse passer le troisieme ;
    celui-ci mesure qu'un echec en tete laisse passer les **deux** suivants. Les
    deux ensemble excluent tout arret premature, ou qu'il tombe.
    """
    plan = plan_de_trois_lots(tmp_path)
    factice = EcritureFactice(
        jalons_par_lot={nom: ((frames, frames),) for nom, frames in LOTS},
        leve_pour={LOTS[0][0]: scan_write.RefusDuDocumentDeDetection(
            "introuvable", motif=scan_write.REFUS_DOCUMENT_INTROUVABLE)})

    rapport = atelier.ecrire_les_lots(
        plan, SurfaceExecution(unite=atelier.UNITE),
        logger=logging.getLogger("banc"), ecrire=factice)

    assert [lot.lot_id for lot in rapport.ecrits] == [LOTS[1][0], LOTS[2][0]]
    assert [refus.lot_id for refus in rapport.refus] == [LOTS[0][0]]


def test_les_options_du_lot_traversent_TELLES_QUELLES(tmp_path):
    """Chaque lot porte les siennes : les melanger ecrirait un lot avec les
    options d'un autre, et le succes apparent serait le meme.

    La cible est **au milieu**, et ses options different de celles de ses deux
    voisines sur **chaque** champ -- un remplissage uniforme cacherait une
    permutation.
    """
    plan = plan_de_trois_lots(tmp_path)
    lots = list(plan.lots)
    import dataclasses as _dc
    lots[RANG_DE_LA_CIBLE] = _dc.replace(
        lots[RANG_DE_LA_CIBLE], overwrite=True, nouvelle_version=True,
        livrer_brut=True, origine_du_profil="atelier")
    plan = _dc.replace(plan, lots=tuple(lots), manifest_du_projet={"lots": []})
    factice = EcritureFactice()

    atelier.ecrire_les_lots(plan, SurfaceExecution(unite=atelier.UNITE),
                            logger=logging.getLogger("banc"), ecrire=factice)

    assert [appel["overwrite"] for appel in factice.appels] == [
        False, True, False]
    assert [appel["nouvelle_version"] for appel in factice.appels] == [
        False, True, False]
    assert all(appel["manifest_du_projet"] == {"lots": []}
               for appel in factice.appels)
    assert all(appel["logger"] is not None for appel in factice.appels), (
        "le coeur declare `logger` obligatoire et le dereference sans garde")


# ===========================================================================
# Les trois conclusions de la passe
# ===========================================================================

def test_un_refus_SANS_rien_d_ecrit_monte_l_ecran_de_REFUS(banc, tmp_path):
    """AC 5.5 : le code et la phrase du coeur, et rien d'ajoute.

    Ce que l'ecran declare non ecrit est **mesure sur le disque**, jamais
    promis : les refus du document precedent toute ecriture, mais une panne
    attrapee par la meme table pourrait, elle, laisser des frames derriere.
    """
    plan = plan_de_trois_lots(tmp_path)
    refus = scan_write.RefusDuDocumentDeDetection(
        "Document de detection introuvable. Aucune frame n'a ete ecrite.",
        motif=scan_write.REFUS_DOCUMENT_INTROUVABLE)
    factice = EcritureFactice(
        leve_pour={nom: refus for nom, _frames in LOTS})

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        rapport = atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=lambda _r: pytest.fail(
                "un refus sans rien d'ecrit ne monte pas le resultat"))
        await pilote.pause()
        return app.screen, rapport, app.tache_en_cours

    ecran, rapport, en_cours = banc(coque(), scenario)
    assert type(ecran).__name__ == "EcranRefus"
    assert ecran.code == "RefusDuDocumentDeDetection"
    assert ecran.message == str(refus)
    assert ecran.non_ecrit == [atelier.NON_ECRIT_PAR_UN_REFUS]
    assert ecran.conserve == [atelier.CONSERVE_PAR_UN_REFUS]
    assert len(rapport.refus) == 3 and rapport.ecrits == ()
    assert en_cours is False, "`oublier_la_tache` est appele dans tous les cas"


def test_un_refus_qui_a_LAISSE_des_frames_ne_dit_PAS_aucune_frame(banc,
                                                                  tmp_path):
    """Volet symetrique du precedent : la phrase est une **mesure**.

    Le disque porte des frames ; annoncer « aucune frame » serait un mensonge,
    et c'est exactement le genre de phrase qu'un ecran de refus ne doit pas
    promettre sans avoir regarde.
    """
    plan = plan_de_trois_lots(tmp_path, frames_sur_le_disque=(0, 3, 0))
    factice = EcritureFactice(leve_pour={
        nom: scan_write.RefusDuDocumentDeDetection("perime", motif=None)
        for nom, _frames in LOTS})

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=lambda _r: None)
        await pilote.pause()
        return app.screen

    ecran = banc(coque(), scenario)
    assert ecran.non_ecrit == []
    assert ecran.conserve == [atelier.CONSERVE_PAR_UN_REFUS]


def test_une_passe_ABOUTIE_remet_le_rapport_a_la_SUITE(banc, tmp_path):
    """`sur_rapport` est requis : un `| None = None` ferait de l'oubli un
    silence, et c'est litteralement le finding `K3`."""
    plan = plan_de_trois_lots(tmp_path)
    factice = EcritureFactice(
        jalons_par_lot={nom: ((frames, frames),) for nom, frames in LOTS})
    recus: list = []

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        rapport = atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=recus.append)
        await pilote.pause()
        return rapport, app.tache_en_cours, app.interruption_demandee

    rapport, en_cours, demandee = banc(coque(), scenario)
    assert recus == [rapport]
    assert [lot.lot_id for lot in rapport.ecrits] == [nom for nom, _f in LOTS]
    assert rapport.frames == sum(frames for _nom, frames in LOTS)
    assert rapport.manifeste == plan.dossier_projet / "project.json"
    assert en_cours is False and demandee is False


def test_une_interruption_SANS_rien_d_ecrit_revient_aux_ATELIERS(banc,
                                                                 tmp_path):
    """`EPIC11-ARB-13` : la fin d'une execution ramene au menu des ateliers du
    projet ouvert, **jamais** a l'ecran projet."""
    plan = plan_de_trois_lots(tmp_path)
    factice = EcritureFactice()

    async def scenario(pilote):
        app = pilote.app
        # On part du menu des ateliers, comme le produit : mesurer le retour
        # depuis la racine ne distinguerait pas `revenir_aux_ateliers` d'un
        # simple depilement.
        app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        app.interruption_demandee = True
        ecran.issue_retenue = atelier.CLE_GARDER
        rapport = atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=lambda _r: pytest.fail(
                "rien n'a ete ecrit : il n'y a pas de resultat a montrer"))
        await pilote.pause()
        return (rapport, app.rang, app.screen.titre, app.passages_empiles)

    rapport, rang, titre, passages = banc(coque(), scenario)
    assert factice.appels == [], "aucun lot n'a ete ouvert"
    assert rapport.interrompu is True
    assert rapport.issue_d_interruption == atelier.CLE_GARDER, (
        "l'issue retenue voyage jusqu'au rapport")
    assert (rang, titre) == (CoqueTui.RANG_DES_ATELIERS, "Ateliers")
    assert passages == 0, "`E3-7` ne reste pas sur le chemin du retour"


def test_une_interruption_APRES_un_lot_ecrit_montre_quand_meme_le_RESULTAT(
        banc, tmp_path):
    """Ce qui est ecrit se montre : le cacher ferait croire a une passe blanche.

    Le rapport porte les deux faits -- ce qui a ete ecrit, et l'interruption --
    et c'est le resultat (`E3-8`) qui les met en forme.
    """
    plan = plan_de_trois_lots(tmp_path)
    demandee = [False]
    factice = EcritureFactice(
        jalons_par_lot={nom: ((frames, frames),) for nom, frames in LOTS},
        pendant=lambda lot: demandee.__setitem__(0, True))
    recus: list = []

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_l_ecriture(app, plan)
        await pilote.pause()
        factice.pendant = lambda lot: setattr(
            app, "interruption_demandee", True)
        ecran.issue_retenue = atelier.CLE_EFFACER
        return atelier.executer_et_conclure(
            app, ecran, plan, logger=logging.getLogger("banc"),
            ecrire=factice, sur_rapport=recus.append)

    rapport = banc(coque(), scenario)
    assert recus == [rapport]
    assert [lot.lot_id for lot in rapport.ecrits] == [LOTS[0][0]]
    assert rapport.interrompu is True
    assert rapport.issue_d_interruption == atelier.CLE_EFFACER


def test_le_titre_de_tache_et_le_bandeau_sont_ceux_de_la_MAQUETTE(banc,
                                                                  tmp_path):
    """`E3-7`, l. 2 et l. 5 : la droite du bandeau distingue les deux temps."""
    plan = plan_de_trois_lots(tmp_path)

    async def scenario(pilote):
        ecran = atelier.ouvrir_l_ecriture(pilote.app, plan)
        await pilote.pause()
        return ecran.titre_tache, ecran.objet, ecran.titre

    titre_tache, objet, titre = banc(coque(), scenario)
    assert titre_tache == "Écriture des TIFF — 3 lots"
    assert objet == atelier.OBJET_DU_BANDEAU == OBJET_DU_BANDEAU_DESSINE
    assert titre == atelier.PALIER_DE_L_ATELIER == "Scan"
    # Un seul lot : l'accord suit, il ne se fige pas au pluriel.
    un_lot = atelier.PlanDEcriture(dossier_projet=plan.dossier_projet,
                                   lots=plan.lots[:1])
    assert atelier.titre_de_la_tache(un_lot) == "Écriture des TIFF — 1 lot"


def test_le_journal_du_temps_2_n_est_pas_celui_de_la_DETECTION():
    """Deux passes qui partageraient un nom de logger verraient leurs lignes
    tomber dans le journal de l'autre."""
    from mixed_media_utility.tui import atelier_scan_detection

    assert atelier.NOM_DU_JOURNAL != atelier_scan_detection.NOM_DU_JOURNAL
    logger, relais = atelier.journal_du_produit()
    assert logger.name == atelier.NOM_DU_JOURNAL
    assert logger.propagate is False
    # Deux passes successives n'empilent pas deux relais.
    _logger2, _relais2 = atelier.journal_du_produit()
    assert len([h for h in logger.handlers if type(h) is type(relais)]) == 1


# ===========================================================================
# AC 5.6 -- le journal vient du COEUR, jamais de phrases redigees en TUI
# ===========================================================================

def test_le_journal_du_COEUR_alimente_celui_de_l_ecran(projet_detecte):
    """AC 5.6 : la correction retenue, la passe de sortie, au fil de l'eau.

    Le relais est celui de l'atelier Extraction (`RelaisDeJournal`), **importe**
    et non reecrit : deux redactions du meme handler divergeraient. Seul le nom
    du logger change, et c'est ce qui empeche les lignes d'une detection
    d'atterrir dans le journal de l'ecriture.

    **La mesure est une PARTITION exacte du journal**, pas la presence d'une
    phrase : « ce journal porte la ligne X » ne dirait rien de ce qu'il porte
    en plus. Trois familles seulement ont le droit d'y etre -- les lignes du
    coeur, les jalons chiffres de la surface, et l'en-tete qui NOMME le lot
    (`EPIC11-ARB-93`). Toute autre ligne serait une phrase redigee en TUI.
    """
    projet, document = projet_detecte
    plan = lot_reel(projet, document)
    surface = SurfaceExecution(unite=atelier.UNITE)
    logger, relais = atelier.journal_du_produit()
    relais.viser(surface.journal)
    du_coeur: list[str] = []
    logger.addHandler(_Sonde(du_coeur))

    atelier.ecrire_les_lots(plan, surface, logger=logger)

    lignes = list(surface.journal.dernieres(500))
    assert du_coeur, "le coeur doit avoir journalise quelque chose"
    # Ce que le coeur a dit est arrive, mot pour mot.
    assert set(du_coeur) <= set(lignes), sorted(set(du_coeur) - set(lignes))
    assert any("Completude du lot" in ligne for ligne in du_coeur)
    assert any("Passe de sortie" in ligne for ligne in du_coeur)
    # Et le journal ne porte RIEN d'autre que les trois familles admises.
    jalons = {f"{rang}/12 frames" for rang in range(1, 13)}
    en_tete = {atelier_extraction.en_tete_de_lot(0, 1, plan.lots[0].lot_id)}
    etrangeres = set(lignes) - set(du_coeur) - jalons - en_tete
    assert etrangeres == set(), sorted(etrangeres)


class _Sonde(logging.Handler):
    """Un second handler sur le meme logger : il dit ce que le COEUR a emis.

    Sans lui, la mesure ci-dessus comparerait le journal a lui-meme.
    """

    def __init__(self, recu: list) -> None:
        super().__init__(level=logging.INFO)
        self.setFormatter(logging.Formatter("%(message)s"))
        self._recu = recu

    def emit(self, record: logging.LogRecord) -> None:
        self._recu.append(self.format(record))


def test_la_table_des_refus_du_SCAN_n_a_qu_UN_lecteur_dans_la_TUI(paquet_tui):
    """Symetrique de la garde d'`EPIC11-ARB-75` cote extraction.

    Le coeur porte **deux** tables de codes de sortie, une par chaine. Celle du
    scan doit avoir, elle aussi, un seul lecteur dans la TUI : deux redactions
    du meme vocabulaire de refus divergent au premier ajustement, et ce depot
    en a deja mesure trois dans `project_maintenance`.

    La mesure est faite a l'arbre et non par un grep -- un commentaire qui
    nomme la fonction ne lit aucune table.
    """
    lecteurs = sorted(
        chemin.name for chemin in paquet_tui.rglob("*.py")
        if _lit_la_table_du_scan(chemin.read_text(encoding="utf-8")))
    assert lecteurs == ["atelier_scan_ecriture.py"], lecteurs
    # Volet symetrique : la mesure tranche bien les trois formes.
    assert _lit_la_table_du_scan("scan_write.correspondance_de_sortie(e)")
    assert not _lit_la_table_du_scan("extraction.correspondance_de_sortie(e)")
    assert not _lit_la_table_du_scan(
        "# scan_write.correspondance_de_sortie fait ca")


def _lit_la_table_du_scan(source: str) -> bool:
    """`scan_write.correspondance_de_sortie` reference **par le code**."""
    for noeud in ast.walk(ast.parse(source)):
        if (isinstance(noeud, ast.Attribute)
                and noeud.attr == "correspondance_de_sortie"
                and isinstance(noeud.value, ast.Name)
                and noeud.value.id == "scan_write"):
            return True
        if (isinstance(noeud, ast.ImportFrom)
                and (noeud.module or "").split(".")[-1] == "scan_write"
                and any(alias.name == "correspondance_de_sortie"
                        for alias in noeud.names)):
            return True
    return False


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite « `E3-7`, l. 2 et l. 5 »
# jusqu'au numero de ligne et n'ouvrait aucun dessin. Citer une ligne d'un
# fichier qu'on n'ouvre pas est la forme la plus trompeuse de la recopie :
# elle a l'air d'une reference.

#: L'objet du bandeau, dessine par `E3-7` a droite de sa l. 2. Il n'est pas
#: invente : la confrontation ci-dessous le verifie a sa source.
OBJET_DU_BANDEAU_DESSINE = "temps 2 sur 2 · écrire"

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_l_OBJET_du_bandeau_est_celui_que_E3_7_dessine():
    """L'objet, a sa source, et le temps voisin qui l'empeche d'etre muet.

    `E3-2` est l'autre temps du meme atelier : meme structure de bandeau,
    valeur differente. Sans lui, une permutation des deux temps -- exactement
    la famille de defaut que la regle des fabriques vise -- resterait verte.
    """
    ecrire = dessin_de_la_maquette("E3-7-scan-ecriture-en-cours.txt")
    detecter = dessin_de_la_maquette("E3-2-scan-detection-en-cours.txt")

    assert OBJET_DU_BANDEAU_DESSINE in ecrire
    assert OBJET_DU_BANDEAU_DESSINE not in detecter
    assert "temps 1 sur 2 · détecter" in detecter
    assert "temps 1 sur 2 · détecter" not in ecrire


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    ecrire = dessin_de_la_maquette("E3-7-scan-ecriture-en-cours.txt")
    assert "temps 2 sur 3 · écrire" not in ecrire
    assert "Écriture terminée" not in ecrire


def test_le_TITRE_de_tache_DIVERGE_du_dessin_et_l_ecart_est_NOMME():
    """`E3-7` titre par RANG de lot, l'outil titre par CARDINAL.

    Le dessin porte « Écriture des TIFF — lot 1 sur 2 » ; l'outil rend
    « Écriture des TIFF — 3 lots ». Ce n'est pas un ecart de redaction, c'est
    un ecart de MODELE : le dessin situe la passe dans sa progression, l'outil
    en annonce la taille.

    **Il n'est pas corrige ici, il est NOMME.** Il est deja en dette au point
    3 de l'entree `E3-7` de `deferred-work.md` (« ni la liste ni le titre
    "lot 1 sur 2" n'existent »), avec l'agregation de la barre qui va avec.
    Le confronter en silence l'aurait efface ; l'ecrire ici le tient visible
    tant qu'il dure.

    La tete commune est mesuree des deux cotes, ce qui est ce qui rend
    l'ecart lisible plutot que total.
    """
    ecrire = dessin_de_la_maquette("E3-7-scan-ecriture-en-cours.txt")
    tete = "Écriture des TIFF — "

    assert tete + "lot 1 sur 2" in ecrire
    assert tete + "3 lots" not in ecrire

    plan_a_trois = "3 lots"
    assert plan_a_trois not in ecrire
