# -*- coding: utf-8 -*-
"""Story 11.5, lot C -- `E3-2`, la detection en cours (AC 5).

**Le suffixe `_tui` du nom de fichier n'est pas decoratif** : la GUI porte deja
`tests/unit/gui/test_atelier_scan_detection.py`, et sans `__init__.py` deux
fichiers de meme nom donnent le **meme** nom de module -- pytest interrompt
alors la collecte de la suite ENTIERE, et la panne ne se voit pas en lancant
`tests/unit/tui` seul. La frontiere qui la mesure est
`test_frontiere_gui_tui.py::test_aucun_nom_de_FICHIER_de_test_n_est_en_double`,
et la convention du depot est ce suffixe (`test_jetons_tui.py` la porte deja).
La fiche 11.5 nommait ce banc sans le suffixe : c'est un ecart de la fiche.

Quatre choses y sont mesurees, et une seule est le coeur du lot :

* **C1** l'appel de `run_scan_detect` **heberge**, la progression **en pages**
  et le journal du coeur au fil de l'eau ;
* **C2** « **aucune frame ecrite** », et c'est le coeur. La mesure se fait sur
  le **disque** -- aux **inodes**, au **`st_mtime_ns`** et par des **temoins**
  deposes dans le dossier vise --, **jamais par condensat** : sur une fixture
  deterministe, une reecriture rend exactement les memes octets, et c'est ce
  qui rendait vert a tort le banc d'`EPIC11-ARB-83` (`CLAUDE.md`, 2026-08-30).
  Un test de ce fichier le **demontre** plutot que de le citer : il mesure que
  le condensat ne bouge pas la ou l'inode bouge ;
* **C3** les deux regimes du rappel de progression (`AR3`) ;
* **C4** l'interruption, avec la reponse retenue pour la `Q4` de la fiche.

**Regle des fabriques, appliquee sur la liste que le code PARCOURT** et non sur
celle que la fabrique ecrit :

* la photographie de `output-frames/` **boucle** sur les entrees du dossier :
  il y a donc **trois** temoins distinguables, et celui qu'on touche est
  **au milieu** de l'ordre parcouru -- un `break` fautif ne verrait ni lui ni
  le suivant ;
* :func:`refus_de` **boucle** sur la table des refus du coeur : la classe visee
  est prise **au milieu** de cette table, et deux autres l'encadrent ;
* la detection **boucle** sur les pages : le lot en porte **trois**,
  distinguables, et la suite des jalons est mesuree **exactement**.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import os
import sys
from pathlib import Path

import pytest

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

from mixed_media_utility import cli, scan_detect, scan_ingest  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.progression import EmetteurProgression  # noqa: E402
from mixed_media_utility.tui import atelier_scan_detection as atelier  # noqa: E402
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin  # noqa: E402
from mixed_media_utility.tui.execution import (  # noqa: E402
    EcranInterruption,
    SurfaceExecution,
)
from mixed_media_utility.tui.panneau import MENTION_MAJORANT, Panneau  # noqa: E402

from outils_frontiere import chaines_de_code  # noqa: E402

import test_scan_calibration_application as planches  # noqa: E402


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

#: **Trois** temoins deposes dans `output-frames/`, distinguables par leur nom
#: ET par leur contenu (regle des fabriques : un remplissage uniforme cacherait
#: une permutation). Celui du **milieu** est la cible : c'est lui que le volet
#: symetrique reecrit, et une boucle de mesure qui s'arreterait au premier ne
#: le verrait pas.
TEMOINS = (
    ("lot_a_12p5", b"temoin du lot a -- 12,5 im/s\n"),
    ("lot_b_25", b"temoin du lot b -- 25 im/s, et c'est la cible\n"),
    ("lot_c_50", b"temoin du lot c -- 50 im/s\n"),
)

#: Le temoin **au milieu** de l'ordre parcouru. Il n'est ni le premier (ce qui
#: masquerait un `find` fautif) ni le dernier (ce qui masquerait une
#: terminaison de boucle fautive) -- `CLAUDE.md`, point 2 bis.
TEMOIN_CIBLE = TEMOINS[1][0]


def coque(**kwargs) -> CoqueTui:
    """Une coque a deux paliers temoins : l'ecran projet et le menu ateliers.

    Deux et non un : le retour au menu des ateliers (`EPIC11-ARB-13`) ne se
    distingue d'un retour a la racine que si la racine existe a cote.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   Q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   Q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def nom_du_temoin(lot: str) -> str:
    """Le fichier depose dans `output-frames/<lot>/`, nomme comme une frame."""
    return f"{lot}_000001.tiff"


def projet_avec_temoins(tmp_path: Path, nom: str) -> tuple[Path, Path]:
    """Un projet reel, et `output-frames/` **peuple de trois temoins**.

    Le dossier est peuple **avant** la passe : mesurer l'absence d'ecriture
    dans un dossier vide ne mesure presque rien -- un dossier vide reste vide
    par accident aussi bien que par contrat. Trois fichiers deja en place
    rendent une reecriture, un remplacement ou un ajout visibles.
    """
    projet = tmp_path / nom
    project_layout.ensure_project_layout(projet)
    sortie = projet / project_layout.SCAN_FRAMES_DIRNAME
    for lot, contenu in TEMOINS:
        (sortie / lot).mkdir(parents=True, exist_ok=True)
        (sortie / lot / nom_du_temoin(lot)).write_bytes(contenu)
    return projet, sortie


def lot_de_trois_planches(tmp_path: Path, nom: str) -> Path:
    """Trois planches **distinguables**, sans page de calibration.

    Trois et non deux : la detection **boucle** sur les pages, et une cible en
    seconde position d'une liste de deux est aussi en derniere -- les deux
    formes y sont indiscernables (`CLAUDE.md`, point 2 bis). Les payloads
    portent des `page_index` differents et les presses alternent : un
    appariement permute se voit, un remplissage uniforme le cacherait.
    """
    payloads = planches.lot_payloads(sheet_count=3, with_calibration=False)
    return planches.write_scan_folder(
        tmp_path / nom,
        [(payload, planches.PRESSES_DU_TIRAGE[rang % 2])
         for rang, payload in enumerate(payloads)],
    )


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


def condensat(racine: Path) -> dict[str, str]:
    """Ce qu'une mesure **par condensat** aurait vu. Elle n'est la que pour etre
    prise en defaut : aucun test ne s'en sert pour conclure a l'absence d'ecriture."""
    return {str(chemin.relative_to(racine)):
            hashlib.sha256(chemin.read_bytes()).hexdigest()
            for chemin in sorted(racine.rglob("*")) if chemin.is_file()}


class DetectionFactice:
    """Un `run_scan_detect` de banc : il emet des jalons, journalise, et rend.

    Il porte la **meme signature** que le coeur -- mots-cles compris. Un faux
    qui accepterait `**kwargs` laisserait passer un appel dont un mot-cle est
    mal nomme, c'est-a-dire exactement la panne que le lot `H1` a payee
    (`logger` non passe, `AttributeError` a la premiere ligne du coeur).
    """

    def __init__(self, *, jalons=(), lignes=(), issue=None, leve=None,
                 pendant=None, sur_ligne=None) -> None:
        self.jalons = tuple(jalons)
        self.lignes = tuple(lignes)
        self.issue = issue
        self.leve = leve
        self.pendant = pendant
        #: Appele APRES chaque ligne journalisee, pendant que le coeur tourne.
        #: C'est le seul point d'observation qui distingue un journal alimente
        #: ligne a ligne d'un journal deverse d'un coup au retour.
        self.sur_ligne = sur_ligne
        self.appels: list[dict] = []

    def __call__(self, project_dir, scan_path, *, dpi, ingest_slug=None,
                 nouvelle_version=False, logger=None, rappel_progression=None,
                 remplacer_les_detections=False, adopter=False):
        self.appels.append({
            "project_dir": project_dir, "scan_path": scan_path, "dpi": dpi,
            "ingest_slug": ingest_slug, "logger": logger,
            # `nouvelle_version` est arrive avec le lot E de la 11.4e : le
            # temps 1 porte desormais la seconde issue d'`EPIC11-ARB-89`, et
            # le drapeau traverse la TUI jusqu'ici. Le double **suit la
            # signature du coeur** -- c'est tout son interet : un faux qui
            # accepterait `**kwargs` laisserait passer un mot-cle mal nomme.
            "nouvelle_version": nouvelle_version,
            "rappel_progression": rappel_progression,
        })
        if self.pendant is not None:
            self.pendant()
        # Le coeur ouvre le rappel dans SON emetteur : le faux fait de meme,
        # sans quoi il mesurerait un canal que le produit n'emploie pas.
        emetteur = EmetteurProgression(rappel_progression,
                                       self.jalons[-1][1] if self.jalons else 0)
        for faites, _total in self.jalons:
            emetteur.emettre(faites)
        for ligne in self.lignes:
            if logger is not None:
                logger.info(ligne)
            if self.sur_ligne is not None:
                # **La mesure est prise PENDANT l'appel** : une assertion posee
                # au retour ne distinguerait pas un journal alimente ligne a
                # ligne d'un journal deverse d'un coup a la fin.
                self.sur_ligne()
        if self.leve is not None:
            raise self.leve
        return self.issue


def issue_factice(documents=(), motif_d_arret=None, pages_identifiees=0):
    """Un `ScanDetectOutcome` **reel** -- le vrai objet du coeur, pas un double.

    Le construire pour de bon est ce qui garantit que le rapport de la TUI lit
    les champs qui existent : un double a attributs libres rendrait vert un
    accesseur mal nomme.
    """
    return scan_detect.ScanDetectOutcome(
        report=object(), rapport_d_ingestion=Path("ingest.json"),
        documents=tuple(documents), pages_identifiees=pages_identifiees,
        motif_d_arret=motif_d_arret)


def demande(projet: Path, source, *, dpi=planches.DPI, ingest_slug=None):
    return atelier.DemandeDeDetection(dossier_projet=projet, source=source,
                                      dpi=dpi, ingest_slug=ingest_slug)


# ===========================================================================
# C1 -- l'appel heberge, la progression en pages, le journal au fil de l'eau
# ===========================================================================

def test_le_coeur_est_HEBERGE_et_l_ecran_est_monte_pendant_l_appel(banc, tmp_path):
    """AC 5.1 : `executer_en_processus`, et la TUI est **vivante** pendant l'appel.

    Deux moities, et il faut les deux : le coeur passe par l'hote de la coque
    (`EPIC11-ARB-1` -- « le coeur est heberge, pas relance »), et l'assertion
    sur l'arbre de widgets est prise **pendant** l'appel. Apres, l'ecran serait
    monte de toute facon et la mesure ne dirait rien.
    """
    vu: dict = {}
    heberges: list = []
    factice = DetectionFactice(issue=issue_factice())

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()

        vrai_hote = app.executer_en_processus

        def hote_espionne(fonction, *args, **kwargs):
            heberges.append(fonction)
            return vrai_hote(fonction, *args, **kwargs)

        app.executer_en_processus = hote_espionne
        factice.pendant = lambda: vu.update(
            ecran=type(app.screen).__name__, tache_en_cours=app.tache_en_cours)
        atelier.executer_et_conclure(
            app, ecran, demande(tmp_path / "projet", tmp_path / "source"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=lambda _r: None)
        return vu

    vu = banc(coque(), scenario)
    assert heberges == [factice], (
        "le coeur doit passer par `executer_en_processus`, et une seule fois")
    assert vu["ecran"] == "EcranDetectionEnCours"
    assert vu["tache_en_cours"] is True, (
        "le coeur doit tourner avec la tache DECLAREE en cours : sinon `Echap` "
        "depile l'ecran au lieu d'ouvrir l'interruption")
    assert factice.appels, "le coeur n'a pas ete appele"


def test_la_source_et_le_dpi_traversent_TELS_QUELS(banc, tmp_path):
    """`EPIC7-ARB-88` et `EPIC7-ARB-44` : aucune coercition, aucun dpi invente.

    La source est une **sequence de chemins** -- la quatrieme forme d'entree --,
    et c'est le cas ou une coercition en `Path` leve un `TypeError` nu.
    """
    factice = DetectionFactice(issue=issue_factice())
    source = (tmp_path / "a.tiff", tmp_path / "b.tiff", tmp_path / "c.tiff")
    projet = tmp_path / "projet"

    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        atelier.executer_et_conclure(
            pilote.app, ecran, demande(projet, source, dpi=1200,
                                       ingest_slug="lot_promis"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=lambda _r: None)

    banc(coque(), scenario)
    appel = factice.appels[0]
    assert appel["scan_path"] is source, "la sequence a ete coercee"
    assert appel["project_dir"] is projet
    assert appel["dpi"] == 1200
    assert appel["ingest_slug"] == "lot_promis"
    assert appel["logger"] is not None, (
        "`run_scan_detect` dereference `logger` sans garde : le laisser a None "
        "est la panne du lot H1")


def test_la_progression_est_en_PAGES_et_son_total_vient_DU_COEUR():
    """AC 5.4 : l'unite est la page, et le total n'est jamais devine.

    La source designe **cinq** fichiers et le coeur n'emet que **trois** pages :
    un total devine sur le nombre de fichiers designes serait faux des qu'une
    page est illisible et sautee, ou des que le lot entre par un PDF. L'ecart
    entre 5 et 3 est exactement ce que la mesure doit voir.
    """
    surface = SurfaceExecution(unite=atelier.UNITE)
    factice = DetectionFactice(jalons=((1, 3), (2, 3), (3, 3)),
                               issue=issue_factice())
    cinq_fichiers = tuple(Path(f"page_{rang}.tiff") for rang in range(5))

    atelier.detecter(demande(Path("projet"), cinq_fichiers), surface,
                     logger=logging.getLogger("banc"), detection=factice)

    assert atelier.UNITE == "pages"
    assert surface.avancement.unite == "pages"
    assert (surface.avancement.faites, surface.avancement.total) == (3, 3)
    assert surface.journal.lignes == ["1/3 pages", "2/3 pages", "3/3 pages"], (
        "les jalons doivent arriver un par un, dans l'ordre, et tous")


def test_le_canal_est_celui_de_la_surface_et_PAS_un_second_mecanisme():
    """AC 5.4 : aucun second mecanisme, et le canal est **actif**.

    Un rappel non appelable part `actif is False` **sans lever et sans trace**,
    barre figee a `0/N` -- le defaut paye cote extraction le 2026-08-30. Le
    mesurer avec l'emetteur du depot est la seule facon de le voir.
    """
    surface = SurfaceExecution(unite=atelier.UNITE)
    canal = atelier.canal_de_progression(surface)

    assert canal == surface.noter, (
        "le canal doit etre le point de note de la surface livree")
    assert EmetteurProgression(canal, 3).actif is True


#: La duree du coeur lent de la mesure de bout en bout ci-dessous.
DUREE_DE_LA_PASSE_LENTE = 0.6


def test_E3_2_est_AU_SOMMET_sur_PLUSIEURS_TOURS_pendant_la_passe(banc, tmp_path):
    """**La mesure qui repond au defaut signale**, sur le parcours reel.

    Les autres tests de ce banc mesurent que `E3-2` est *monte* pendant
    l'appel. Ce n'est pas la meme chose que *peint* : `descendre` EMPILE, et le
    dessin est un evenement de la boucle. Un ecran empile pendant qu'un coeur
    synchrone occupe la boucle satisfait « monte » et reproduit exactement le
    defaut signale -- « on passe de la confirmation au succes sans voir la
    progression ».

    La mesure est le nombre de TOURS DE BOUCLE ou `E3-2` est au sommet
    **PENDANT que le coeur travaille**, et la fenetre est delimitee par deux
    drapeaux poses par le coeur lui-meme.

    **Delimiter la fenetre n'est pas un raffinement, c'est ce qui rend la
    mesure portante.** Une premiere redaction comptait les tours sur une
    fenetre ouverte APRES le retour de `lancer_la_detection` : avec le chemin
    synchrone d'avant la reparation, la passe etait deja finie a cet instant,
    `E3-2` restait au sommet (rien ne le depile ici, `sur_rapport` est inerte),
    et les tours s'accumulaient quand meme. Le mutant « remets
    `executer_et_conclure` » SURVIVAIT. Avec la fenetre du coeur, il meurt : un
    coeur synchrone occupe la boucle pendant toute sa duree, donc la boucle de
    comptage ne tourne pas une seule fois.

    Le coeur est **lent par construction**, via le crochet `pendant` du double.
    Sans cette lenteur il n'y aurait aucun tour a observer, et le test serait
    vert sans rien mesurer.
    """
    import threading
    import time

    demarre, fini = threading.Event(), threading.Event()

    def coeur_lent() -> None:
        demarre.set()
        time.sleep(DUREE_DE_LA_PASSE_LENTE)
        fini.set()

    factice = DetectionFactice(issue=issue_factice(), pendant=coeur_lent)

    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        atelier.lancer_la_detection(
            pilote.app, ecran, demande(tmp_path / "projet", tmp_path / "src"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=lambda _r: None)
        tours_pendant_le_coeur = 0
        debut = time.time()
        while time.time() - debut < DUREE_DE_LA_PASSE_LENTE + 0.4:
            await pilote.pause()
            if demarre.is_set() and not fini.is_set():
                if pilote.app.screen is ecran:
                    tours_pendant_le_coeur += 1
        return tours_pendant_le_coeur, demarre.is_set(), fini.is_set()

    tours, a_demarre, a_fini = banc(coque(), scenario)
    # Sans ces deux-la, un coeur jamais appele rendrait zero tour et le test
    # rougirait pour la mauvaise raison -- ou pire, un coeur jamais fini
    # rendrait beaucoup de tours sans que rien n'aboutisse.
    assert a_demarre and a_fini, (
        f"le coeur n'a pas joue de bout en bout (demarre={a_demarre},"
        f" fini={a_fini}) : le test ne mesure pas ce qu'il annonce")
    assert tours >= 2, (
        f"`E3-2` n'a ete au sommet que {tours} tour(s) de boucle PENDANT que le"
        " coeur travaillait : le coeur occupe la boucle, donc rien n'est peint"
        " -- c'est le gel signale, mot pour mot")


def test_le_journal_du_coeur_arrive_AU_FIL_DE_L_EAU(banc, tmp_path):
    """AC 5.1 : le journal se remplit **pendant** la passe, pas a la fin.

    Le compte de lignes est releve apres chaque `logger.info` du coeur, pendant
    que la passe tourne : il doit croitre de un a chaque fois. Un relais qui
    accumulerait pour tout deverser au retour passerait une assertion posee
    apres l'appel, et rougit ici.
    """
    lignes = ("3 page(s) ingeree(s) dans scans/lot_b",
              "Rapport d'ingestion ecrit",
              "Document de detection ecrit")
    comptes: list[int] = []
    factice = DetectionFactice(lignes=lignes, issue=issue_factice())

    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        logger, relais = atelier.journal_du_produit()
        relais.viser(ecran.surface.journal)
        factice.sur_ligne = lambda: comptes.append(len(ecran.surface.journal))
        atelier.executer_et_conclure(
            pilote.app, ecran, demande(tmp_path / "projet", tmp_path / "src"),
            logger=logger, detection=factice, sur_rapport=lambda _r: None)
        return list(ecran.surface.journal.lignes)

    journal = banc(coque(), scenario)
    assert comptes == [1, 2, 3], (
        "le journal doit croitre d'une ligne a chaque ligne du coeur")
    assert journal == list(lignes), (
        "les lignes du coeur arrivent dans l'ordre, toutes, et sans qu'aucune "
        "ligne etrangere ne s'y glisse")


def test_le_relais_de_journal_ne_S_EMPILE_PAS_entre_deux_detections():
    """Deux passes dans la meme session ne doublent pas chaque ligne.

    Le logger est un singleton par nom : sans retrait de l'ancien relais, la
    seconde detection inscrirait chaque ligne deux fois.
    """
    logger, _ = atelier.journal_du_produit()
    logger, relais = atelier.journal_du_produit()
    poses = [h for h in logger.handlers if isinstance(h, type(relais))]
    assert len(poses) == 1, poses


def test_le_journal_du_SCAN_n_est_pas_celui_de_l_extraction():
    """Deux ateliers, deux noms : sinon les lignes de l'un tombent chez l'autre."""
    from mixed_media_utility.tui import atelier_extraction_ecriture as ecriture

    assert atelier.NOM_DU_JOURNAL != ecriture.NOM_DU_JOURNAL
    logger, _ = atelier.journal_du_produit()
    assert logger.propagate is False, (
        "un handler herite du racine ecrirait sur stdout PAR-DESSUS la TUI")


def test_l_ecran_porte_le_titre_de_tache_et_le_bandeau_de_la_maquette(banc):
    """`E3-2`, verbatim : l'en-tete de tache, l'atelier et le temps travaille."""
    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        return ecran.titre_tache, ecran.objet_du_bandeau(), ecran.bandeau()

    titre, objet, bandeau = banc(coque(), scenario)
    assert titre == TITRE_DE_LA_TACHE
    assert objet == OBJET_DU_BANDEAU
    assert "Scan" in bandeau and "projet_demo" in bandeau
    assert "Execution" not in bandeau, (
        "le bandeau nomme l'atelier, jamais la classe d'ecran")


# ===========================================================================
# C2 -- LE COEUR DU LOT : aucune frame ecrite, mesure sur le disque
# ===========================================================================

def test_un_parcours_complet_du_temps_1_ne_touche_pas_output_frames(banc,
                                                                   tmp_path):
    """AC 5.2, et c'est le coeur du lot.

    Parcours **complet** et **reel** : trois planches peintes, le vrai
    `run_scan_detect`, heberge par la coque, ecran monte. La mesure est prise
    sur le disque avant et apres, aux inodes et au `st_mtime_ns`, sur les trois
    temoins deja en place -- **jamais par condensat**.

    Deux temoins de vitalite sont indispensables, sans quoi ce test serait vert
    et creux : la passe a bien produit un document, et le sous-arbre `scans/`
    a bien bouge. Un test qui ne mesure « rien n'a change » que sur une passe
    qui n'a rien fait ne mesure rien du tout.
    """
    projet, sortie = projet_avec_temoins(tmp_path, "projet-temps-1")
    dossier = lot_de_trois_planches(tmp_path, "pile")
    rapports: list = []

    avant = photographie(sortie)
    avant_scans = photographie(projet / project_layout.SCANS_DIRNAME)

    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        return atelier.executer_et_conclure(
            pilote.app, ecran, demande(projet, dossier),
            logger=logging.getLogger("banc-scan-detect"),
            sur_rapport=rapports.append)

    rapport = banc(coque(), scenario)
    apres = photographie(sortie)

    assert rapport.refus is None, rapport.refus
    assert rapport.documents, "temoin de vitalite : la passe n'a rien produit"
    assert rapports == [rapport], "le rapport doit etre remis a la suite"
    assert divergences(avant_scans,
                       photographie(projet / project_layout.SCANS_DIRNAME)), (
        "temoin de vitalite : `scans/` doit avoir bouge, sinon la mesure de "
        "`output-frames` ne prouve rien")

    assert divergences(avant, apres) == set(), (
        "le temps 1 n'ecrit AUCUNE frame : `output-frames/` doit etre "
        "identique aux inodes et au st_mtime_ns")
    assert set(avant) == {"."} | {
        cle for lot, _ in TEMOINS
        for cle in (lot, f"{lot}/{nom_du_temoin(lot)}")}, (
        "volet symetrique : la photographie doit porter les trois temoins ET "
        "la racine, sinon elle mesurerait un dossier vide")


def test_la_mesure_MORD_sur_une_reecriture_a_octets_identiques(tmp_path):
    """Volet symetrique de l'AC 5.2, et il est le vrai enjeu du lot.

    On reecrit **le temoin du milieu** avec **exactement les memes octets**,
    par remplacement atomique -- le geste que le coeur emploie lui-meme
    (`ecrire_document_json_atomiquement`). Le condensat ne bouge pas d'un bit ;
    l'inode, si. Une mesure par condensat serait donc verte a tort, et c'est
    litteralement le defaut d'`EPIC11-ARB-83`.

    La cible est **au milieu** de l'ordre parcouru : une boucle de mesure qui
    s'arreterait au premier element ne la verrait pas.
    """
    _projet, sortie = projet_avec_temoins(tmp_path, "projet-volet")
    cible = sortie / TEMOIN_CIBLE / nom_du_temoin(TEMOIN_CIBLE)

    avant, avant_condensat = photographie(sortie), condensat(sortie)
    octets = cible.read_bytes()
    provisoire = cible.with_suffix(".tiff.tmp")
    provisoire.write_bytes(octets)
    os.replace(provisoire, cible)
    apres, apres_condensat = photographie(sortie), condensat(sortie)

    assert apres_condensat == avant_condensat, (
        "les octets sont identiques : c'est la premisse du piege")
    assert cible.read_bytes() == octets
    assert divergences(avant, apres) == {
        f"{TEMOIN_CIBLE}/{nom_du_temoin(TEMOIN_CIBLE)}", TEMOIN_CIBLE}, (
        "la mesure doit voir la reecriture -- le fichier ET le dossier qui le "
        "porte, dont l'entree a ete remplacee")


def test_la_mesure_MORD_sur_un_fichier_AJOUTE(tmp_path):
    """Une frame ecrite est un fichier de plus, et aucun inode existant ne bouge.

    C'est le mode de panne qu'une mesure fichier par fichier laisserait passer :
    comparer les fichiers connus ne dit rien de ceux qui apparaissent. La
    comparaison porte donc sur l'**ensemble des cles**, pas seulement sur les
    valeurs.
    """
    _projet, sortie = projet_avec_temoins(tmp_path, "projet-ajout")
    avant = photographie(sortie)
    (sortie / TEMOIN_CIBLE / "lot_b_25_000002.tiff").write_bytes(b"une frame\n")

    assert divergences(avant, photographie(sortie)) == {
        f"{TEMOIN_CIBLE}/lot_b_25_000002.tiff", TEMOIN_CIBLE}


def test_le_document_de_detection_est_ECRIT_et_son_chemin_est_rendu(banc,
                                                                    tmp_path):
    """AC 5.3 : c'est ce qui permet de quitter ici et de reprendre plus tard.

    Le chemin est **lu du `ScanDetectOutcome`**, jamais reconstruit depuis un
    slug : les deux divergent des qu'un fichier deja sous `scans/` est ingere
    en place.
    """
    projet, _sortie = projet_avec_temoins(tmp_path, "projet-document")
    dossier = lot_de_trois_planches(tmp_path, "pile-document")

    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        return atelier.executer_et_conclure(
            pilote.app, ecran, demande(projet, dossier),
            logger=logging.getLogger("banc-scan-detect"),
            sur_rapport=lambda _r: None)

    rapport = banc(coque(), scenario)
    attendus = sorted((projet / project_layout.SCANS_DIRNAME).glob(
        f"*/{scan_detect.DETECTIONS_DIRNAME}/*.json"))
    assert sorted(rapport.documents) == attendus
    assert attendus, "aucun document de detection n'a ete ecrit"
    assert all(chemin.exists() for chemin in rapport.documents)
    assert rapport.motif_d_arret is None


# ===========================================================================
# C3 -- les deux regimes du rappel (`AR3`)
# ===========================================================================

def test_les_deux_regimes_du_rappel_donnent_le_MEME_document(tmp_path):
    """AC 5.4 / `AR3` : le rappel est optionnel et ne change **rien** a l'observable.

    Deux projets, la meme pile peinte : l'un detecte par le chemin de la TUI
    (canal branche), l'autre par le coeur nu (`rappel_progression=None`). Les
    documents sont compares **champ par champ**, hors horodatage -- pas
    seulement leur existence : c'est la difference exacte entre le test qui a
    survecu aux trois mutations de 5.8 et celui qui les aurait attrapees.
    """
    import json

    dossier = lot_de_trois_planches(tmp_path, "pile-ar3")
    avec, sans = tmp_path / "projet-avec", tmp_path / "projet-sans"
    surface = SurfaceExecution(unite=atelier.UNITE)
    jalons: list[tuple[int, int]] = []
    surface.abonner(lambda a: jalons.append((a.faites, a.total)))

    rapport = atelier.detecter(demande(avec, dossier), surface,
                               logger=logging.getLogger("banc-avec"))
    issue_sans = scan_detect.run_scan_detect(
        sans, dossier, dpi=planches.DPI, rappel_progression=None)

    def sans_volatiles(chemin: Path) -> dict:
        document = json.loads(chemin.read_text(encoding="utf-8"))
        for champ in ("generated_at_utc", "fingerprints"):
            document.pop(champ, None)
        return document

    gauche = [sans_volatiles(c) for c in rapport.documents]
    droite = [sans_volatiles(c) for c in issue_sans.documents]
    assert gauche == droite, "le rappel a change l'observable"
    assert gauche and gauche[0]["pages"], (
        "temoin : les documents compares portent de la matiere")
    assert len(gauche[0]["pages"]) == 3

    # Le regime AVEC rappel : la suite EXACTE des jalons, dans l'ordre.
    assert jalons == [(1, 3), (2, 3), (3, 3)], jalons


def test_l_absence_de_rappel_ne_change_NI_les_refus_NI_le_journal(tmp_path):
    """`AR3`, second volet : memes exceptions, meme journal, des deux cotes."""
    inexistant = tmp_path / "nulle-part"
    surface = SurfaceExecution(unite=atelier.UNITE)

    with pytest.raises(scan_ingest.ScanIngestError) as sans:
        scan_detect.run_scan_detect(tmp_path / "p-sans", inexistant,
                                    dpi=planches.DPI, rappel_progression=None)
    with pytest.raises(scan_ingest.ScanIngestError) as avec:
        scan_detect.run_scan_detect(
            tmp_path / "p-avec", inexistant, dpi=planches.DPI,
            rappel_progression=atelier.canal_de_progression(surface))

    assert str(avec.value) == str(sans.value)
    assert type(avec.value) is type(sans.value)
    assert surface.journal.lignes == [], (
        "aucun jalon n'a lieu d'etre : l'ingestion n'a pas abouti")


# ===========================================================================
# C4 -- l'interruption (reponse retenue pour la Q4)
# ===========================================================================

def test_l_interruption_d_une_detection_porte_DEUX_issues_et_aucune_n_ecrit():
    """Q4, reponse retenue : deux issues, et les invariants les acceptent.

    `ChoixExclusif` exige au moins deux issues actionnables, aucune
    preselectionnee, au moins une qui n'ecrit pas. Ici **aucune** des deux
    n'ecrit -- c'est la propriete du temps 1, plus forte que l'invariant.
    """
    ecran = atelier.EcranInterruptionDeDetection(Panneau("Déjà lu", []))

    assert [i.cle for i in ecran.choix.issues] == ["interrompre", "reprendre"]
    assert ecran.choix.retenue is None
    assert ecran.choix.issues[ecran.choix.curseur].ecrit is False
    assert [i.cle for i in ecran.choix.issues if i.ecrit] == [], (
        "une detection n'ecrit rien : aucune issue ne peut porter ecrit=True")
    assert ecran.choix.action_qui_ecrit is None


def test_aucune_issue_de_la_detection_ne_parle_de_ce_qui_est_DEJA_ECRIT():
    """Q4, le motif : les trois issues heritees parlent d'ecriture, pas nous.

    Volet symetrique explicite : les libelles de `EcranInterruption` portent
    bien les mots que ceux-ci n'ont pas. Sans lui, la mesure serait verte sur
    n'importe quel vocabulaire.
    """
    interdits = ("garder", "effacer", "écrit", "ecrit")
    nos_libelles = [i.libelle.lower() for i in atelier.ISSUES_DE_L_INTERRUPTION]
    herites = [i.libelle.lower() for i in EcranInterruption.ISSUES]

    assert [libelle for libelle in nos_libelles
            if any(mot in libelle for mot in interdits)] == []
    assert [libelle for libelle in herites
            if any(mot in libelle for mot in interdits)] == herites[:2], (
        "volet symetrique : les deux premieres issues heritees parlent bien "
        "d'ecriture, sinon la mesure ci-dessus ne mesure rien")
    assert [i.cle for i in atelier.ISSUES_DE_L_INTERRUPTION][1] == (
        EcranInterruption.REPRENDRE), (
        "la cle de reprise est celle de l'ecran d'execution : une seconde "
        "chaine divergerait et `Echap` cesserait de reprendre")


def test_echap_pendant_la_detection_ouvre_L_INTERRUPTION_DE_LA_DETECTION(banc):
    """`Echap` empile, il ne remonte pas -- et il monte NOTRE ecran, pas l'herite."""
    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        app.tache_en_cours = True
        avant = (app.passages_empiles, app.rang)
        await pilote.press("escape")
        await pilote.pause()
        return avant, (app.passages_empiles, app.rang), type(app.screen), ecran

    avant, apres, classe, _ecran = banc(coque(), scenario)
    assert apres[0] == avant[0] + 1, "on a empile, on n'a pas depile"
    assert apres[1] == avant[1], "une interruption ne change pas de palier"
    assert classe is atelier.EcranInterruptionDeDetection
    assert classe is not EcranInterruption


def test_le_cartouche_de_l_interruption_compte_des_pages_LUES_et_zero_frame(banc):
    """Le cartouche herite compte des unites ecrites ; ici rien n'est ecrit.

    Les deux premiers chiffres sont **mesures** (ils viennent des jalons), donc
    aucun ne porte la mention de majorant ; le troisieme est l'invariant du
    temps 1, dit a l'ecran plutot que suppose.
    """
    async def scenario(pilote):
        ecran = atelier.ouvrir_la_detection(pilote.app)
        await pilote.pause()
        ecran.surface.noter(2, 3)
        return ecran.panneau_de_ce_qui_est_ecrit()

    panneau = banc(coque(), scenario)
    assert panneau.titre == "Déjà lu"
    assert [(l.libelle, l.valeur, l.unite) for l in panneau.lignes] == [
        ("Pages lues", 2, "pages"),
        ("Pages restantes", 1, "pages"),
        ("Frames écrites", 0, "frames"),
    ]
    assert all(not ligne.majorant for ligne in panneau.lignes)
    assert MENTION_MAJORANT not in "".join(l.chiffre for l in panneau.lignes)


def test_reprendre_depile_et_ne_demande_AUCUNE_interruption(banc):
    """« Reprendre » est de la navigation : la passe ne doit rien en savoir."""
    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        app.tache_en_cours = True
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        interruption.choix.viser(EcranInterruption.REPRENDRE)
        interruption.valider()
        await pilote.pause()
        return type(app.screen), app.interruption_demandee

    classe, demandee = banc(coque(), scenario)
    assert classe is atelier.EcranDetectionEnCours, "on est revenu a `E3-2`"
    assert demandee is False


def test_interrompre_DEMANDE_l_interruption(banc):
    """L'issue qui arrete pose le drapeau que la passe consulte, et rien d'autre."""
    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        app.tache_en_cours = True
        interruption = ecran.ouvrir_l_interruption()
        await pilote.pause()
        interruption.choix.viser(atelier.INTERROMPRE)
        interruption.valider()
        await pilote.pause()
        return app.interruption_demandee

    assert banc(coque(), scenario) is True


def test_une_interruption_demandee_AVANT_l_appel_n_appelle_pas_le_coeur(tmp_path):
    """Le seul regime ou « ne rien poser » est vrai a la lettre.

    Rien n'a ete appele, donc ni frame, ni manifeste, ni document. Le rapport
    le dit **sans document** : une passe interrompue avant l'appel ne peut pas
    en porter un.
    """
    factice = DetectionFactice(issue=issue_factice(documents=(Path("d.json"),)))
    surface = SurfaceExecution(unite=atelier.UNITE)

    rapport = atelier.detecter(
        demande(tmp_path / "projet", tmp_path / "src"), surface,
        logger=logging.getLogger("banc"), detection=factice,
        interrompu=lambda: True)

    assert factice.appels == [], "le coeur a ete appele malgre l'interruption"
    assert rapport.interrompu is True
    assert rapport.documents == ()
    assert rapport.refus is None
    assert surface.journal.lignes == []


def test_une_interruption_arrivee_PENDANT_l_appel_ne_cache_pas_le_document(
        tmp_path):
    """La granularite est dite plutot que maquillee.

    `run_scan_detect` est un appel synchrone sans point d'arret, et le canal de
    progression est observationnel par contrat : une interruption qui arrive
    pendant arrive **apres**. Le document produit est alors **porte** par le
    rapport, jamais tu -- le taire ferait croire a une passe sans effet et
    ferait redetecter pour rien.
    """
    demandee = {"vrai": False}
    document = Path("scans/lot/detections/2026.json")
    factice = DetectionFactice(issue=issue_factice(documents=(document,)),
                               pendant=lambda: demandee.update(vrai=True))
    surface = SurfaceExecution(unite=atelier.UNITE)

    rapport = atelier.detecter(
        demande(tmp_path / "projet", tmp_path / "src"), surface,
        logger=logging.getLogger("banc"), detection=factice,
        interrompu=lambda: demandee["vrai"])

    assert factice.appels, "le coeur devait avoir ete appele"
    assert rapport.interrompu is True
    assert rapport.documents == (document,)


def test_une_interruption_ne_monte_pas_le_rapport_et_revient_aux_ateliers(
        banc, tmp_path):
    """`EPIC11-ARB-13` : la fin d'une execution ramene au menu des ateliers.

    Le rapport n'est pas remis a la suite : l'operateur a demande a s'arreter
    la. Et les trois drapeaux de tache sont eteints -- sinon `Echap` resterait
    une interruption bien apres la fin.
    """
    factice = DetectionFactice(issue=issue_factice())
    remis: list = []

    async def scenario(pilote):
        app = pilote.app
        # On part du menu des ateliers, comme le produit : mesurer le retour
        # depuis la racine ne distinguerait pas `revenir_aux_ateliers` d'un
        # simple depilement.
        app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        app.interruption_demandee = True
        rapport = atelier.executer_et_conclure(
            app, ecran, demande(tmp_path / "projet", tmp_path / "src"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=remis.append)
        await pilote.pause()
        return (rapport, app.rang, app.screen.titre, app.passages_empiles,
                app.tache_en_cours, app.interruption_demandee)

    rapport, rang, titre, passages, en_cours, demandee = banc(coque(), scenario)
    assert factice.appels == []
    assert rapport.interrompu is True
    assert remis == [], "un rapport interrompu ne monte pas `E3-3`"
    assert (rang, titre) == (CoqueTui.RANG_DES_ATELIERS, "Ateliers")
    assert passages == 0, "`E3-2` ne reste pas sur le chemin du retour"
    assert (en_cours, demandee) == (False, False)


# ===========================================================================
# AC 5.5 -- un refus se nomme par son code, jamais « echec »
# ===========================================================================

def test_un_refus_du_coeur_est_rendu_par_son_CODE_et_par_sa_phrase(banc,
                                                                   tmp_path):
    """AC 5.5 et `DESIGN.md` §9 : le code ET la phrase viennent du coeur."""
    motif = "Aucun fichier lisible dans la pile deposee"
    factice = DetectionFactice(leve=scan_ingest.ScanIngestError(motif))

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        rapport = atelier.executer_et_conclure(
            app, ecran, demande(tmp_path / "projet", tmp_path / "src"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=lambda _r: None)
        await pilote.pause()
        # Les lignes se lisent **pendant** que l'ecran est monte : une fois le
        # gestionnaire de contexte referme, l'arbre de widgets n'existe plus.
        return rapport, type(app.screen).__name__, "\n".join(app.screen.lignes())

    rapport, nom_de_l_ecran, lignes = banc(coque(), scenario)
    assert rapport.refus.code == "ScanIngestError"
    assert rapport.refus.message == motif
    assert nom_de_l_ecran == "EcranRefus"
    assert "ScanIngestError" in lignes and motif in lignes
    assert "echec" not in lignes.lower() and "échec" not in lignes.lower()
    assert atelier.NON_ECRIT_PAR_LE_TEMPS_1 in lignes


def test_une_exception_HORS_TABLE_traverse(tmp_path):
    """Deguiser une panne de programmation en refus metier est l'interdit."""
    factice = DetectionFactice(leve=RuntimeError("un bug, pas un refus"))
    surface = SurfaceExecution(unite=atelier.UNITE)

    with pytest.raises(RuntimeError, match="un bug, pas un refus"):
        atelier.detecter(demande(tmp_path / "projet", tmp_path / "src"),
                         surface, logger=logging.getLogger("banc"),
                         detection=factice)


def test_refus_de_reconnait_la_classe_du_MILIEU_de_la_table():
    """Regle des fabriques sur la liste que :func:`refus_de` **parcourt**.

    Trois classes mesurees : la premiere, **celle du milieu**, la derniere. Un
    `break` premature ne verrait ni le milieu ni la fin ; un `find` qui rendrait
    toujours la premiere entree se demasque sur le milieu.
    """
    table = atelier.REFUS_DU_COEUR
    assert len(table) >= 3, table
    milieu = table[len(table) // 2]

    for classe in (table[0], milieu, table[-1]):
        try:
            exception = classe("motif du refus")
        except TypeError:      # certaines exceptions du coeur exigent plus
            exception = classe.__new__(classe)
            BaseException.__init__(exception, "motif du refus")
        refus = atelier.refus_de(exception)
        assert refus is not None, classe
        assert refus.code == classe.__name__

    assert atelier.refus_de(ZeroDivisionError("hors table")) is None


class RefusDerive(scan_ingest.ScanIngestError):
    """Une exception du coeur qui **herite** d'une entree de la table.

    Le cas n'est pas theorique : `IdentiteIncompletable` est une sous-classe de
    `CorrectionInvalide` et n'a pas d'entree a elle. C'est ce cas-la, et lui
    seul, qui distingue « le code nomme la classe LEVEE » de « le code nomme
    l'entree de la table qui a repondu ».
    """


def test_le_code_du_refus_nomme_la_classe_LEVEE_et_pas_l_entree_de_la_table():
    """AC 5.5 : deux lectures possibles, une seule designe la panne."""
    refus = atelier.refus_de(RefusDerive("une identite incompletable"))

    assert refus is not None
    assert refus.code == "RefusDerive", (
        "le code doit nommer la classe levee ; `ScanIngestError` serait le nom "
        "de l'entree de la table qui l'a attrapee, pas celui de la panne")
    assert refus.code not in [classe.__name__ for classe in atelier.REFUS_DU_COEUR]
    assert refus.message == "une identite incompletable"


def test_une_passe_ABOUTIE_eteint_les_drapeaux_de_tache(banc, tmp_path):
    """Sans quoi `Echap` resterait une interruption bien apres la fin.

    La mesure porte sur la conclusion **nominale** : sur le chemin interrompu,
    `revenir_aux_ateliers` eteint les drapeaux au passage, si bien qu'un oubli
    d'`oublier_la_tache` y resterait invisible.
    """
    factice = DetectionFactice(issue=issue_factice())

    async def scenario(pilote):
        app = pilote.app
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        pendant = {}
        factice.pendant = lambda: pendant.update(en_cours=app.tache_en_cours)
        atelier.executer_et_conclure(
            app, ecran, demande(tmp_path / "projet", tmp_path / "src"),
            logger=logging.getLogger("banc"), detection=factice,
            sur_rapport=lambda _r: None)
        return pendant["en_cours"], app.tache_en_cours, app.interruption_demandee

    assert banc(coque(), scenario) == (True, False, False)


def test_un_ARRET_non_fautif_n_est_PAS_un_refus(tmp_path):
    """Une pile dont aucune planche n'a livre son QR a bel et bien ete ingeree.

    Le motif d'arret **traverse** jusqu'au rapport, et le rapport ne porte
    aucun refus : les confondre ferait monter un ecran de refus la ou le coeur
    rend un succes, et ferait recommencer une ingestion qui a eu lieu.
    """
    factice = DetectionFactice(issue=issue_factice(
        motif_d_arret=scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE))

    rapport = atelier.detecter(
        demande(tmp_path / "projet", tmp_path / "src"),
        SurfaceExecution(unite=atelier.UNITE),
        logger=logging.getLogger("banc"), detection=factice)

    assert rapport.motif_d_arret == scan_detect.ARRET_AUCUNE_PLANCHE_IDENTIFIEE
    assert rapport.motif_d_arret in scan_detect.MOTIFS_D_ARRET
    assert rapport.refus is None and rapport.interrompu is False
    assert rapport.documents == ()


def test_la_table_des_refus_est_EXACTEMENT_celle_du_chemin_scan_detect():
    """Deux redactions du meme vocabulaire divergent : on les confronte.

    `scan_detect` ne publie aucune table de refus, la ou `scan_write` publie sa
    `CODES_DE_SORTIE`. La TUI n'importe pas `cli` (AC 8.1) et redige donc la
    sienne depuis les modules du coeur ; ce banc, lui, a le droit de lire les
    deux et mesure leur egalite d'ensembles. Le jour ou l'une bouge sans
    l'autre, c'est ici que ca rougit.
    """
    assert set(atelier.REFUS_DU_COEUR) == set(cli._REFUS_DU_COEUR_SUR_DETECT)
    assert atelier.REFUS_DU_COEUR, "volet symetrique : la table n'est pas vide"


# ===========================================================================
# Frontieres du module livre par ce lot
# ===========================================================================

def test_le_module_n_importe_PAS_cli():
    """AC 8.1, verifie explicitement sur le module neuf plutot que suppose."""
    source = Path(atelier.__file__)
    arbre = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            importes.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            importes.add(noeud.module or "")
            importes.update(alias.name for alias in noeud.names)

    assert not any(nom == "cli" or nom.endswith(".cli") for nom in importes), (
        sorted(importes))
    assert "scan_detect" in importes, (
        "volet symetrique : la mesure lit bien les imports du module")


def test_aucun_terme_interdit_dans_le_module_de_la_detection():
    """`EPIC11-ARB-28`, `-29` et `-48`, sur le module que ce lot livre.

    Les trois interdits ne sont pas de meme nature et la mesure les traite
    differemment : `palier` et `rescanner` sont du **vocabulaire d'ecran**, donc
    mesures sur les chaines de code ; `completer` est une frontiere posee sur le
    **texte entier** du paquet (`EPIC11-ARB-48`), commentaires compris.
    """
    source = Path(atelier.__file__)
    textes = chaines_de_code(source)
    for mot in ("palier", "rescanner"):
        assert [t for t in textes if mot in t.lower()] == [], mot
    assert "palier" in "Remonter au palier 0".lower(), (
        "volet symetrique : la mesure de vocabulaire mord")
    assert "completer" not in source.read_text(encoding="utf-8").lower()


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc annonce « `E3-2`, verbatim »
# et n'ouvrait aucun dessin : les deux valeurs etaient recopiees a la main.
# « Verbatim » est precisement la promesse qu'une recopie ne peut pas tenir --
# elle tient au moment ou on l'ecrit, puis le dessin bouge sans elle.

#: Le titre de tache et l'objet du bandeau, dessines par `E3-2` (l. 5 et l. 2).
#: Ils ne sont pas inventes : la confrontation en fin de fichier les verifie a
#: leur source, et c'est ce qui donne son sens au mot « verbatim » ci-dessus.
TITRE_DE_LA_TACHE = "Détection en cours — aucune frame n'est écrite"
OBJET_DU_BANDEAU = "temps 1 sur 2 · détecter"

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


def test_le_TITRE_et_l_OBJET_sont_ceux_que_E3_2_dessine():
    """Les deux valeurs, a leur source, et le voisin qui les distingue.

    `E3-7` -- l'autre temps du meme atelier -- porte la meme STRUCTURE de
    bandeau et des valeurs differentes. Le confronter aussi est ce qui
    distingue « le dessin porte ce texte » de « les deux temps se
    ressemblent » : un appariement inverse entre les deux temps serait vert
    si l'on ne mesurait qu'un dessin.
    """
    detecter = dessin_de_la_maquette("E3-2-scan-detection-en-cours.txt")
    ecrire = dessin_de_la_maquette("E3-7-scan-ecriture-en-cours.txt")

    assert TITRE_DE_LA_TACHE in detecter
    assert OBJET_DU_BANDEAU in detecter

    assert TITRE_DE_LA_TACHE not in ecrire
    assert OBJET_DU_BANDEAU not in ecrire
    assert "temps 2 sur 2 · écrire" in ecrire


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    detecter = dessin_de_la_maquette("E3-2-scan-detection-en-cours.txt")
    assert "Détection terminée" not in detecter
    assert "temps 1 sur 3 · détecter" not in detecter


def test_le_PIED_de_E3_2_est_CELUI_du_rendu_et_l_ecart_est_FERME():
    """`E3-2` dessinait `Tab journal complet` ; il dessine `Tab journal`.

    **L'epingle est RETOURNEE, pas retiree** (`EPIC11-ARB-246`, Egan le
    2026-09-06, par invite : « Tab journal partout »). Elle mesurait un ecart
    assume entre le dessin et le rendu ; elle mesure desormais leur egalite.
    La supprimer aurait rendu la reintroduction invisible -- une frontiere
    supprimee ne rougit plus jamais.

    La correction est venue du **dessin** : c'est `_gen_b.py` qui a perdu le
    mot, puis `regenerer.py` qui l'a fait descendre dans le `.txt`
    (`EPIC11-ARB-142` : jamais un rendu edite a la main). La chaine du produit,
    elle, est PARTAGEE par quatre ecrans et n'a pas bouge.
    """
    from mixed_media_utility.tui.execution import EcranExecution

    detecter = dessin_de_la_maquette("E3-2-scan-detection-en-cours.txt")
    assert "Tab journal complet" not in detecter
    # `dessin_de_la_maquette` replie les espaces : la comparaison se fait donc
    # sur la ligne du produit repliee du meme geste, sans quoi elle mesurerait
    # la mise en page du dessin plutot que ses mots.
    assert " ".join(EcranExecution.raccourcis.split()) in detecter
    assert EcranExecution.raccourcis.startswith("Tab journal ")
