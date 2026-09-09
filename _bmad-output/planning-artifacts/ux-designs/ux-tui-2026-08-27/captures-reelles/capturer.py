# -*- coding: utf-8 -*-
"""Captures du VRAI rendu de la TUI, par le pilote headless de `textual`.

Ce ne sont pas des maquettes : chaque fichier est ce que le terminal dessine,
couleurs comprises. Une capture qu'on ne sait pas rejouer n'est pas une mesure,
c'est une image -- d'ou ce script, livre a cote des captures.

Lancer :  python capturer.py [dossier_de_sortie]
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE / "tests" / "unit"))
# Le dossier parent, pour importer `demo_vague_3` -- la demo de recette est la
# source des fixtures d'atelier, voir plus bas.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mixed_media_utility import cadence_previz, extraction  # noqa: E402

from mixed_media_utility.tui import (atelier_extraction,  # noqa: E402
                                     ecran_projet, noms, projets)
from mixed_media_utility.tui import (  # noqa: E402
    atelier_extraction_ecriture as ecriture)
from mixed_media_utility.tui.atelier_extraction_ecriture import (  # noqa: E402
    construire_l_application)
from mixed_media_utility.tui.coque import (CoqueTui, Contexte,  # noqa: E402
                                           PalierTemoin)
from mixed_media_utility.tui.execution import (EcranRefus,  # noqa: E402
                                               EcranResultat,
                                               PanneauConfirmation)
from mixed_media_utility.tui.noms import ModeleNoms, NomEditable  # noqa: E402
from mixed_media_utility.tui.panneau import (ChoixExclusif,  # noqa: E402
                                             Issue, LigneChiffree, Panneau)

SORTIE = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent)
DEMO = Path("/tmp/demo_tui_captures")


def poser_l_arborescence() -> Path:
    """Une arborescence de demonstration, et DEUX projets pour que le marqueur
    `● projet` ait de quoi se distinguer -- une fixture a un seul projet ne
    demasquerait pas un marquage qui suit le rang au lieu du contenu."""
    shutil.rmtree(DEMO, ignore_errors=True)
    mmu = DEMO / "HOKO" / "Documents" / "mmu"
    for nom, combien in (("archives", 0), ("projects", 0),
                         ("rushes_2026", 27), ("scans", 3)):
        (mmu / nom).mkdir(parents=True)
        for n in range(combien):
            (mmu / nom / f"{n:02d}_sous_dossier").mkdir()
    for nom in ("chendj_mat", "essais_papier", "planche_hiver_2026",
                "projet_demo", "rebuts"):
        (mmu / "projects" / nom).mkdir(exist_ok=True)

    # **Les deux projets de demonstration sont de VRAIS manifestes**, copies
    # depuis `projects/`, et non un JSON ecrit a la main.
    #
    # Motif, et il a ete paye : la premiere version de ce script ecrivait un
    # `project.json` reduit a `rushes` et `lots`. Le schema du coeur le refusait
    # -- il lui manque `schema_version`, `project_id` et le reste --, donc
    # `diagnostiquer()` rendait « illisible », donc AUCUN dossier ne portait
    # `● projet`. La capture s'appelait « les projets se voient au passage » et
    # ne montrait aucun projet. Egan l'a vu avant moi : « chendj mat n'apparait
    # pas en vert. Contient-il un fichier de projet ? »
    for nom, source in (("chendj_mat", "chendj-mat"),
                        ("projet_demo", "projet_demo")):
        origine = RACINE / "projects" / source / "project.json"
        shutil.copyfile(origine, mmu / "projects" / nom / "project.json")

    # **Et on le VERIFIE, bruyamment.** Une capture qui illustre une phrase sans
    # la demontrer est pire qu'une capture absente : elle se lit comme une
    # preuve. Le script echoue plutot que de produire une image muette.
    for nom in ("chendj_mat", "projet_demo"):
        diagnostic = projets.diagnostiquer(mmu / "projects" / nom)
        if diagnostic.etat != projets.PROJET_LISIBLE:
            raise SystemExit(
                f"Fixture cassee : {nom} n'est pas un projet lisible "
                f"({diagnostic.etat}). La capture montrerait un ecran sans "
                f"aucun marqueur `projet`. Motif du coeur : {diagnostic.motif}")
    return mmu


def coque(ecran) -> CoqueTui:
    return CoqueTui(paliers=[ecran, PalierTemoin("Ateliers", "q quitter")],
                    contexte=Contexte("projet_demo"))


PANNEAU = Panneau("A ecrire", [
    LigneChiffree("Lots crees", 2, "lots"),
    LigneChiffree("Frames ecrites", 186, "frames"),
    LigneChiffree("Espace disque", "~ 3,1", "Go", majorant=True),
])
ISSUES = ChoixExclusif([Issue("ecrire", "Extraire", ecrit=True),
                        Issue("modifier", "Modifier les reglages"),
                        Issue("annuler", "Annuler")])


async def capturer(nom: str, ecran, preparer=None) -> None:
    app = coque(ecran)
    async with app.run_test(size=(80, 24)) as pilote:
        if preparer is not None:
            preparer(app.screen)
        app.screen.rafraichir()
        await pilote.pause()
        app.save_screenshot(str(SORTIE / f"{nom}.svg"))
    print(f"  {nom}.svg")


def ecran_de_projet(mmu, recents=()):
    fichier = DEMO / "recents.json"
    liste = projets.Recents(fichier)
    for chemin in recents:
        liste.noter_ouverture(chemin)
    return ecran_projet.EcranProjet(recents=liste)


async def principal() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    mmu = poser_l_arborescence()
    projects = mmu / "projects"

    def dans(dossier, pas=0, saisie=None):
        def preparer(ecran):
            # `traiter("tab")` et non `ecran.zone = ...` : c'est le geste que
            # l'operateur fait, et c'est lui qui repose la ligne de raccourcis.
            # L'affectation directe laissait les captures d'explorateur porter
            # la ligne des RECENTS -- l'image disait le contraire de sa legende.
            if ecran.zone != ecran_projet.ZONE_CHEMIN:
                ecran.traiter("tab")
            exp = ecran.explorateur
            exp.dossier = dossier
            exp.relire()
            for _ in range(pas):
                exp.deplacer(1)
            if saisie is not None:
                exp.basculer_la_saisie()
                exp.saisie, exp.caret = saisie, len(saisie)
                exp._suivre_la_saisie()
        return preparer

    await capturer("01-recents-cinq-compteurs",
                   ecran_de_projet(mmu, [projects / "chendj_mat",
                                         projects / "projet_demo"]))
    await capturer("02-explorateur-depart", ecran_de_projet(mmu),
                   dans(mmu, pas=1))
    await capturer("03-explorateur-projets-visibles", ecran_de_projet(mmu),
                   dans(projects))
    await capturer("04-explorateur-liste-longue", ecran_de_projet(mmu),
                   dans(mmu / "rushes_2026"))
    await capturer("05-explorateur-defilement", ecran_de_projet(mmu),
                   dans(mmu / "rushes_2026", pas=16))
    await capturer("06-explorateur-saisie-au-focus", ecran_de_projet(mmu),
                   dans(mmu, saisie=str(projects)))
    await capturer("07-explorateur-adresse-inexistante", ecran_de_projet(mmu),
                   dans(mmu, saisie=str(mmu / "projest")))
    await capturer("08-confirmation-chiffree",
                   PanneauConfirmation(PANNEAU, ISSUES, ModeleNoms([
                       NomEditable("projet_demo_rush_01_25fps"),
                       NomEditable("projet_demo_rush_01_12p5")])),
                   lambda e: e.choix.deplacer(1))
    await capturer("09-resultat",
                   EcranResultat(Panneau("Resultat", [
                       LigneChiffree("Lots crees", 2, "lots"),
                       LigneChiffree("Frames ecrites", 186, "frames")]),
                       suites=["Voir le lot", "Revenir aux ateliers"]),
                   lambda e: setattr(e, "curseur", 1))
    await capturer("10-refus",
                   EcranRefus("scan_hors_perimetre",
                              "La planche scannee n'appartient a aucun lot du "
                              "projet ouvert."))

    # ------------------------------------------- l'atelier Extraction (E2-*) --
    # Les douze ecrans `E2-*` ne sont PAS captures ici : ils le sont par
    # `promener_l_atelier`, qui monte le vrai point d'entree et pilote au
    # clavier. Voir le grand commentaire de cette section, plus bas.
    await promener_l_atelier(ascii_seul=False)
    await promener_l_atelier(ascii_seul=True)


# ===========================================================================
# L'atelier Extraction (`E2-*`) -- capture PAR LE CLAVIER, sur le vrai produit
# ===========================================================================
#
# **Pourquoi cette section ne ressemble pas a celle du dessus.** Les captures
# `01` a `10` instancient un ecran et le posent sur une coque de circonstance.
# C'est tenable pour un ecran de la vague 1, qui n'a ni amont ni aval. Ca ne
# l'est plus pour un atelier : un ecran instancie a la main ne mesure que
# lui-meme, et le defaut le plus cher de la vague 3 etait justement un
# CABLAGE -- `mmu-tui` montait trois ecrans temoins, et l'atelier Extraction
# etait injoignable par le produit lui-meme, ce qu'aucun banc n'a vu pendant
# deux vagues parce que `demo_vague_2.py` assemblait la chaine a la main.
#
# Les captures de cette section partent donc de `construire_l_application()`,
# le meme point d'entree que `python -m mixed_media_utility.tui`, et se
# deplacent **a la touche**, comme un operateur. Si un ecran manque ici, il
# manque aussi a l'operateur.
#
# **Les deux seules substitutions, et ce qu'elles coutent.** Elles sont nommees
# ici plutot que decouvertes en revue :
#
# 1. `jouer=` -- la previz du produit ouvre une VRAIE fenetre OpenCV et attend
#    une touche a la fin de chaque passe (`play_cadences` -> `wait_for_key`).
#    Sans humain devant l'ecran, elle ne rend jamais la main : `E2-2b` et
#    `E2-2c` seraient inatteignables. On remplace donc le seul `sink` par
#    `cadence_previz.NullSink`, qui est du COEUR -- c'est le chemin de
#    `--no-display` : il cadence reellement, il mesure reellement le temps
#    reel, il ne montre rien. Les chiffres du rapport sont donc mesures, pas
#    fabriques ; ce qui est faux, et le reste, c'est qu'aucune fenetre ne
#    s'ouvre a cote du terminal alors que l'ecran l'annonce.
# 2. `logger=` -- **et cette substitution-la est un DEFAUT du produit, pas une
#    commodite de capture.** Voir `_JOURNAL_DE_CAPTURE` ci-dessous.
#
# Tout le reste -- les paliers, les ecrans, le clavier, les modeles, le coeur,
# ffmpeg, les TIFF ecrits sur le disque -- est le code de production.

#: Les touches que `textual` ne nomme pas par leur caractere.
_NOMS_DE_TOUCHES = {"/": "slash", "_": "underscore", ".": "full_stop",
                    "-": "minus", " ": "space", ",": "comma"}

#: **Le logger que le produit ne fournit pas.** `extraction.run_extraction`
#: declare `logger: logging.Logger` en mot-cle SANS defaut et l'appelle sans
#: garde (`extraction.py:853`, `logger.info(...)`) ; or `ParcoursExtraction`
#: le laisse a `None` et `ouvrir_les_cadences` -- le rappel que
#: `chaine_du_produit` injecte -- n'en passe aucun. La premiere extraction
#: lancee depuis `mmu-tui` leve donc `AttributeError: 'NoneType' object has no
#: attribute 'info'` et l'application tombe. Aucun banc ne le voit : ils
#: passent tous un logger.
#:
#: Ce journal existe pour que `E2-4` et `E2-5` puissent etre PHOTOGRAPHIES
#: malgre ce defaut. Il ne le repare pas -- la reparation est du cote de
#: `src/`, hors du perimetre de ce lot.
_JOURNAL_DE_CAPTURE = logging.getLogger("mmu.captures")
_JOURNAL_DE_CAPTURE.addHandler(logging.NullHandler())


def _jouer_sans_fenetre(session, *, logger=None):
    """La lecture comparee, sur le sink SANS FENETRE du coeur.

    `cadence_previz.NullSink` est le sink de `--no-display` : il dort jusqu'a
    chaque echeance, donc il mesure le temps reel pour de vrai, et il rend la
    main sans attendre de touche. C'est la seule facon d'atteindre `E2-2b` et
    `E2-2c` sans quelqu'un devant l'ecran -- voir la substitution 1.
    """
    return cadence_previz.play_cadences(
        session, sink=cadence_previz.NullSink(), logger=logger)


def _affichage_disponible() -> str | None:
    """Le motif du refus d'affichage, ou `None` si un affichage repond."""
    try:
        cadence_previz.ensure_display_available()
    except cadence_previz.DisplayUnavailableError as refus:
        return refus.motif
    return None


class Promenade:
    """Un operateur qui marche l'atelier au clavier, et photographie en route.

    **Rien ici ne touche a l'etat d'un ecran.** Les seules lectures faites sur
    le modele servent a savoir quand s'arreter (combien d'effacements pour
    vider un champ) ou a VERIFIER qu'on est bien la ou l'on croit ; aucune
    n'ecrit. Une capture obtenue en posant un attribut ne mesurerait que la
    pose.
    """

    def __init__(self, app, pilote, suffixe: str = "") -> None:
        self.app = app
        self.pilote = pilote
        #: `-ascii` pour le regime de repli, vide pour l'UTF-8. Les deux
        #: regimes sont captures parce que le repli **allonge** certaines
        #: lignes : une capture qui n'en montre qu'un ne dit rien de l'autre.
        self.suffixe = suffixe
        self.prises: list[str] = []

    async def frapper(self, *touches: str) -> None:
        for touche in touches:
            await self.pilote.press(_NOMS_DE_TOUCHES.get(touche, touche))

    async def taper(self, texte: str) -> None:
        await self.frapper(*texte)

    async def vider_la_saisie(self, lire) -> None:
        """`Retour arriere` jusqu'a ce que le champ soit vide.

        Le nombre d'effacements est LU du champ et non compte a l'avance : le
        chemin de depart de l'explorateur est le dossier courant, dont la
        longueur depend de la machine qui lance la capture.
        """
        for _ in range(400):
            if not lire():
                return
            await self.frapper("backspace")
        raise SystemExit("Le champ ne se vide pas : la promenade a derive.")

    def photographier(self, nom: str, attendu=None) -> None:
        """Poser la photo. Synchrone : appelable depuis un rappel du coeur.

        `attendu` est la CLASSE d'ecran ou l'on croit etre. La verifier n'est
        pas une precaution de style : une promenade qui derive d'une frappe
        produit une planche entiere de captures plausibles et fausses, et
        c'est exactement ce qu'une capture est censee empecher.
        """
        ecran = self.app.screen
        if attendu is not None and not isinstance(ecran, attendu):
            raise SystemExit(
                f"Promenade derivee : {nom} devait etre {attendu.__name__}, "
                f"l'application montre {type(ecran).__name__}. La capture "
                "serait une image plausible et fausse.")
        rafraichir = getattr(ecran, "rafraichir", None)
        if rafraichir is not None:
            rafraichir()
        fichier = f"{nom}{self.suffixe}.svg"
        self.app.save_screenshot(str(SORTIE / fichier))
        self.prises.append(fichier)
        print(f"  {fichier}")

    async def prendre(self, nom: str, attendu=None) -> None:
        """Laisser l'ecran se dessiner, puis photographier."""
        await self.pilote.pause()
        self.photographier(nom, attendu)


async def _ouvrir_l_atelier(promenade: Promenade, projet: str) -> None:
    """Des recents jusqu'a `E2-1`, par le clavier et par lui seul.

    **Le curseur descend jusqu'au projet VISE, il ne compte pas les crans.**
    `Recents` trie par horodatage a la SECONDE et les deux projets du bac sont
    notes dans la meme seconde : leur ordre depend alors de la stabilite du tri
    et du moment ou le bac est pose, pas d'une regle. Un nombre de `↓` ecrit en
    dur ouvrirait donc le mauvais projet un lancement sur N -- et toutes les
    captures suivantes seraient plausibles et fausses.
    """
    ecran = promenade.app.screen
    for _ in range(len(ecran.entrees)):
        if ecran.entrees[ecran.curseur].chemin.name == projet:
            break
        await promenade.frapper("down")
    else:
        raise SystemExit(f"Le projet {projet} n'est pas dans les recents du bac.")
    await promenade.frapper("enter")
    await promenade.frapper("enter")          # `Extraction`, entree en tete


async def promener_les_rushes(bac, ascii_seul: bool) -> list[str]:
    """`E2-1`, `E2-1b`, `E2-1c`, `E2-1d` -- et AUCUNE substitution.

    Ce parcours-ci passe par `construire_l_application()` tel quel : la liste
    des rushes, les deux explorateurs et le refus de relink n'ont besoin ni de
    fenetre ni de journal.
    """
    suffixe = "-ascii" if ascii_seul else ""
    app = construire_l_application(recents=bac["recents"],
                                   ascii_seul=ascii_seul)
    async with app.run_test(size=(80, 24)) as pilote:
        p = Promenade(app, pilote, suffixe)
        await _ouvrir_l_atelier(p, "projet_demo")
        # `rush_hiver`, l'absent, est en TROISIEME position -- jamais en
        # premiere : un ecran qui viserait toujours le premier rush ne se
        # demasquerait pas autrement.
        await p.frapper("down", "down")
        await p.prendre("11-E2-1-rushes", atelier_extraction.EcranRushes)

        await p.frapper("r")
        await p.prendre("13-E2-1b-relink-retrouver",
                        atelier_extraction.EcranRushes)
        await p.frapper("escape", "d")
        await p.prendre("14-E2-1c-relink-designer",
                        atelier_extraction.EcranRushes)

        # `E2-1d` : on cherche pour de vrai, dans l'aire de recherche du bac
        # qui porte DEUX copies conformes de `rush_hiver.mp4`. Le coeur refuse
        # donc sur `candidats-multiples` -- un refus REEL, rendu par son code,
        # et c'est celui que la section B.5 du plan de test annonce.
        #
        # **Cette capture montrait `aucun-candidat` jusqu'au 2026-08-30**, sur
        # le dossier `rushes/` du bac : aucun fichier n'y portait le nom de
        # base de `rush_hiver`, la recherche ne pouvait donc rien trouver. Le
        # coeur disait vrai ; c'est le bac qui ne permettait pas de montrer ce
        # que le plan promettait (meme famille que l'ecart `J4`).
        if bac["retrouvailles"] is None:
            raise SystemExit(
                "Aire de recherche absente du bac (ffmpeg introuvable ?) : la "
                "capture 15 montrerait `aucun-candidat` au lieu du refus que "
                "la section B.5 du plan de test annonce.")
        await p.frapper("escape", "r", "tab")
        explorateur = app.screen.explorateur
        await p.vider_la_saisie(lambda: explorateur.saisie)
        await p.taper(str(bac["retrouvailles"]["deux"]))
        await p.frapper("enter")
        await p.prendre("15-E2-1d-relink-refus",
                        atelier_extraction.EcranRefusRelink)
        prises = list(p.prises)

    # Le second projet : DEUX absents, la cible en SECONDE position parmi eux.
    app = construire_l_application(recents=bac["recents"],
                                   ascii_seul=ascii_seul)
    async with app.run_test(size=(80, 24)) as pilote:
        p = Promenade(app, pilote, suffixe)
        await _ouvrir_l_atelier(p, "projet_deux_absents")
        await p.frapper("down", "down")
        await p.prendre("12-E2-1-deux-absents",
                        atelier_extraction.EcranRushes)
        return prises + p.prises


async def promener_sans_affichage(bac, ascii_seul: bool) -> list[str]:
    """`E2-2` quand aucun affichage ne repond -- l'entree previz INACTIVE.

    L'ecran est monte avec `DISPLAY` retire de l'environnement : c'est
    `ensure_display_available` qui refuse, au montage, et l'ecran porte alors
    le motif NU du coeur -- sans le conseil qui nomme `--no-display`, que la
    TUI n'expose pas. Aucune substitution ici non plus.
    """
    suffixe = "-ascii" if ascii_seul else ""
    garde = {nom: os.environ.pop(nom)
             for nom in ("DISPLAY", "WAYLAND_DISPLAY") if nom in os.environ}
    try:
        app = construire_l_application(recents=bac["recents"],
                                       ascii_seul=ascii_seul)
        async with app.run_test(size=(80, 24)) as pilote:
            p = Promenade(app, pilote, suffixe)
            await _ouvrir_l_atelier(p, "projet_demo")
            await p.frapper("enter")            # `rush_present`, deja lie
            await p.frapper("down", "space")    # la SECONDE cadence, cochee
            await p.prendre("17-E2-2-sans-affichage",
                            atelier_extraction.EcranCadences)
            return p.prises
    finally:
        os.environ.update(garde)


async def promener_le_parcours(bac, ascii_seul: bool,
                               avec_previz: bool) -> list[str]:
    """`E2-2` a `E2-5` : le parcours complet, cadences comprises et TIFF ecrits.

    C'est le seul parcours qui porte les deux substitutions, et c'est le seul
    qui ecrit sur le disque -- de vrais TIFF, par `run_extraction`, dans le bac
    jetable.
    """
    suffixe = "-ascii" if ascii_seul else ""
    photographe: dict[str, Promenade | None] = {"p": None}
    lots_vus: list[float] = []

    def extraire(**arguments):
        """`run_extraction`, photographie EN COURS DE ROUTE.

        `E2-4` ne se photographie pas depuis la promenade : l'appel du coeur
        est synchrone et occupe la boucle d'evenements du debut a la fin de
        l'extraction. La photo se prend donc depuis le canal de progression du
        DERNIER lot, au moment ou la barre a deja avance -- c'est-a-dire au
        seul instant ou l'ecran d'execution montre autre chose que zero.
        """
        lots_vus.append(arguments["fps_target"])
        if len(lots_vus) >= 2:
            rappel = arguments.get("rappel_progression")
            pris = []

            def surveiller(faites, total):
                issue = rappel(faites, total) if rappel is not None else None
                if not pris and total and faites * 2 >= total:
                    pris.append(True)
                    photographe["p"].photographier("23-E2-4-execution")
                return issue

            arguments["rappel_progression"] = surveiller
        return extraction.run_extraction(**arguments)

    chaine = ecriture.ChaineReelle(
        recents=bac["recents"], ascii_seul=ascii_seul,
        ouvrir_les_cadences=functools.partial(
            ecriture.ouvrir_les_cadences, logger=_JOURNAL_DE_CAPTURE,
            jouer=_jouer_sans_fenetre, extraire=extraire))
    # **La chaine reste celle du produit**, et on le verifie : les trois
    # paliers doivent etre exactement ceux que `construire_l_application`
    # monte. Sans ce controle, la substitution des deux rappels pourrait
    # devenir, un jour, une chaine assemblee a la main -- le defaut meme que
    # cette section existe pour ne pas reproduire.
    temoins = [type(palier) for palier
               in construire_l_application()._paliers]
    if [type(palier) for palier in chaine.app._paliers] != temoins:
        raise SystemExit("La chaine de capture a divergé de celle du produit.")

    app = chaine.app
    async with app.run_test(size=(80, 24)) as pilote:
        p = Promenade(app, pilote, suffixe)
        photographe["p"] = p
        await _ouvrir_l_atelier(p, "projet_demo")
        await p.frapper("enter")            # `rush_present`, deja lie
        # DEUX cadences a comptes DIFFERENTS, et la premiere cochee est la
        # SECONDE de la liste : une fabrique uniforme ne demasquerait aucun
        # appariement decale.
        await p.frapper("down", "space", "down", "space")
        await p.prendre("16-E2-2-cadences", atelier_extraction.EcranCadences)

        if avec_previz:
            await p.frapper("enter")
            # **`E2-2b` a DEUX temps depuis `K1.2`, et la promenade n'en
            # connaissait qu'un** : elle photographiait l'ecran d'attente sous
            # le nom du rapport, puis frappait un seul `⏎` -- qui OUVRE la
            # fenetre au lieu de descendre -- et derivait sur `19-E2-2c`. Le
            # defaut est anterieur au lot `N1` : il est reproduit a l'identique
            # sur le commit precedent. Une capture qu'on ne rejoue pas derive
            # de son ecran ; c'est ce que ce script existe pour empecher.
            await p.prendre("18-E2-2b-previz-attente",
                            atelier_extraction.EcranPreviz)
            await p.frapper("enter")        # ouvre la fenetre, et LIT
            await p.prendre("18-E2-2b-previz", atelier_extraction.EcranPreviz)
            # `o` relit **sur place** (lot `N1`) : on reste sur `E2-2b`, et le
            # rapport est celui de la nouvelle passe. La verification de classe
            # de `prendre` est ce qui mesure ici « on ne descend pas ».
            await p.frapper("o")
            await p.prendre("18-E2-2b-previz-revue",
                            atelier_extraction.EcranPreviz)
            await p.frapper("enter")        # descend au temps 2
            # Le temps 2 arrive ENTIEREMENT decoche : il n'herite d'aucun
            # consentement du temps 1. On recoche donc les deux.
            await p.frapper("space", "down", "space")
            await p.prendre("19-E2-2c-choix",
                            atelier_extraction.EcranChoixDesCadences)
            await p.frapper("enter")
        else:
            # Sans affichage, `⏎` est inactif : `x` extrait sans previz, et
            # c'est le chemin que l'AC 5.1 nomme.
            await p.frapper("x")

        await p.prendre("20-E2-3-confirmation", PanneauConfirmation)
        await p.frapper("tab")              # `Tab` entre dans les noms
        await p.vider_la_saisie(lambda: app.screen.noms.courant.valeur)
        await p.taper("rush_hiver")
        await p.prendre("21-E2-3b-edition-nom", PanneauConfirmation)
        # Au-dela de la limite, le nom est REFUSE, jamais tronque, et l'action
        # principale reste inaccessible. La longueur visee est LUE du modele.
        await p.taper("_" + "x" * (noms.LIMITE - len("rush_hiver")))
        await p.prendre("22-E2-3c-nom-refuse", PanneauConfirmation)

        await p.frapper("ctrl+r")           # remettre le nom propose
        await p.frapper("tab", "up")        # sortir vers les choix, `Extraire`
        await p.frapper("enter")            # `E2-4` puis `E2-5`
        await p.prendre("24-E2-5-resultat", EcranResultat)
        return p.prises


async def promener_l_atelier(*, ascii_seul: bool) -> list[str]:
    """Les trois promenades d'un regime, chacune sur un bac NEUF.

    Un bac neuf par promenade, et ce n'est pas de la prudence : la derniere
    promenade ECRIT des lots, et un second passage sur le meme bac ouvrirait
    l'ecran d'ecrasement au lieu du panneau nominal.
    """
    import demo_vague_3  # noqa: E402  (le dossier parent est sur le chemin)

    regime = "repli ASCII" if ascii_seul else "UTF-8"
    print(f"  -- atelier Extraction, regime {regime} --")
    refus = _affichage_disponible()
    if refus is not None:
        print("  ATTENTION : aucun affichage ne repond, donc `E2-2b` et "
              "`E2-2c` ne seront PAS captures.")
        print(f"    motif du coeur : {refus}")
        print("    relancer sous  xvfb-run -a python capturer.py")

    prises: list[str] = []
    bac = demo_vague_3.poser_le_bac(DEMO / "atelier")
    prises += await promener_les_rushes(bac, ascii_seul)
    bac = demo_vague_3.poser_le_bac(DEMO / "atelier")
    prises += await promener_sans_affichage(bac, ascii_seul)
    bac = demo_vague_3.poser_le_bac(DEMO / "atelier")
    prises += await promener_le_parcours(bac, ascii_seul,
                                         avec_previz=refus is None)
    return prises


if __name__ == "__main__":
    asyncio.run(principal())
