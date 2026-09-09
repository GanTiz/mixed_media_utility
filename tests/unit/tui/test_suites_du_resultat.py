# -*- coding: utf-8 -*-
"""Story 11.4, lot `K3` -- les suites de `E2-5` menaient nulle part.

**Ce banc existe parce qu'aucun autre ne pouvait voir la panne**, et il est la
troisieme occurrence du meme mode de defaut dans cet epic : un composant livre,
teste, et **cable nulle part** (lot `E9` pour les paliers du produit, finding
`I3` pour `bandeau_de_relink`, finding `I0` pour le journal). Ici :

* `execution.EcranResultat` accepte `sur_suite` et sait s'en servir ; il a son
  banc, et il est vert ;
* `ouvrir_le_resultat` accepte `sur_suite: Callable[[str], None] | None = None`
  et le transmet ; il a son banc, et il est vert ;
* et l'**unique** point d'appel du produit vers cet ecran --
  `executer_et_conclure`, dans `atelier_extraction_ecriture.py` -- ne le passait
  pas. Les quatre suites de l'ecran de fin etaient donc navigables au clavier et
  **decoratives**. Egan l'a trouve a la main le 2026-08-30 : « quatre suites
  sont proposees, une seule marche ».

Le `| None = None` est ce qui rend le defaut **silencieux** : rien ne leve, rien
ne rougit, et `EcranResultat` se replie sur son ecran « pas encore », qui a
l'air d'un choix.

**Le banc qui aurait vu ca est celui qui exerce le chemin DU PRODUIT**, pas un
ecran construit a la main avec son rappel injecte -- exactement la lecon de
`test_journal_du_produit.py` : « le banc mesurait un parcours qui n'est pas
celui du produit, sur le seul point ou les deux different ». Les tests de bout
en bout de ce fichier partent donc du **menu des ateliers** et descendent au
clavier jusqu'a `E2-5`, sans jamais appeler `ouvrir_le_resultat`.

**Regle des fabriques** (`CLAUDE.md`, point 2 bis compris) :

* **trois** rushes au manifeste, le rush vise **au milieu** -- ni premier (un
  `find` fautif rendrait le premier) ni dernier (une boucle qui ne s'arrete
  jamais rendrait le dernier) ;
* **deux** cadences cochees, aux comptes differents, aux rangs 1 et 2 ;
* **quatre** suites a l'ecran de fin, et celle qu'on exerce d'abord --
  « Extraire un autre rush » -- est au rang 2 sur 4 : ni premiere ni derniere.
  Les quatre sont ensuite exercees une a une, et leurs destinations sont
  confrontees deux a deux : une dispatch qui rendrait toujours la meme ne
  passerait pas.
"""
import ast
import inspect
import json
import sys
import textwrap
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import (
    extraction,
    frame_selection,
    progression,
    video_metadata,
)
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.io.naming import build_lot_id
from mixed_media_utility.io.project_layout import (EXTRACT_FRAMES_DIRNAME,
                                                   extract_frames_dir)
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    Palier,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import EcranResultat

#: La source du banc : 25 im/s, 124 frames. Les cadences remarquables en tirent
#: quatre comptes distincts, donc deux lots distinguables.
FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124
LARGEUR, HAUTEUR = 1920, 1080

#: Les cadences cochees, **aux rangs 1 et 2** : jamais la premiere.
RANGS_COCHES = (1, 2)
VALEURS_COCHEES = (Fraction(25, 2), Fraction(25, 3))

#: Trois rushes, et le vise est **AU MILIEU** (`CLAUDE.md`, point 2 bis) : une
#: fabrique a deux elements dont la cible est en second la place aussi en
#: dernier, et les deux fautes -- « rend toujours le premier » et « rend le
#: dernier parce que la boucle ne s'arrete pas » -- y sont indiscernables.
RUSH_AVANT = "rush_00_avant"
RUSH_VISE = "rush_01_vise"
RUSH_APRES = "rush_02_apres"


class JournalMuet:
    """Un logger minimal : le coeur en exige un, on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def probe_de_la_source() -> dict:
    """Une sortie ffprobe complete, telle que `probe_media` la rend."""
    return {
        "streams": [
            {"codec_type": "video", "codec_name": "prores",
             "r_frame_rate": f"{FPS_SOURCE.numerator}/{FPS_SOURCE.denominator}",
             "avg_frame_rate":
                 f"{FPS_SOURCE.numerator}/{FPS_SOURCE.denominator}",
             "nb_frames": str(FRAMES_SOURCE),
             "duration": str(FRAMES_SOURCE / float(FPS_SOURCE)),
             "width": LARGEUR, "height": HAUTEUR,
             "tags": {"timecode": "01:00:00:00"}},
        ],
        "format": {"duration": str(FRAMES_SOURCE / float(FPS_SOURCE))},
    }


@pytest.fixture
def sonde(monkeypatch):
    """Le probe du coeur, remplace la ou les trois consommateurs le lisent."""
    monkeypatch.setattr(video_metadata, "probe_media",
                        lambda chemin, **kwargs: probe_de_la_source())


def projet(tmp_path) -> tuple[Path, Path]:
    """Un projet reel dont le rush vise est le **deuxieme de trois**."""
    dossier = creer_projet(tmp_path, "projet_demo").chemin
    entrees = []
    for nom in (RUSH_AVANT, RUSH_VISE, RUSH_APRES):
        chemin = tmp_path / f"{nom}.mov"
        chemin.write_bytes(f"pas une vraie video : {nom}".encode("utf-8"))
        entrees.append({"rush_id": nom, "source_path": str(chemin)})
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    document["rushes"] = entrees
    (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                             encoding="utf-8")
    return dossier, tmp_path / f"{RUSH_VISE}.mov"


def compte_du_coeur(valeur: Fraction) -> int:
    """Le cardinal que `select_source_frames` rend, calcule A PART du module."""
    return frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=valeur,
        source_frame_count=FRAMES_SOURCE,
        source_start_timecode="01:00:00:00").expected_frame_count


def extracteur(dossier_projet: Path):
    """Un double de `run_extraction` qui ecrit de VRAIS dossiers de lot.

    Deux lots aux comptes differents et aux poids differents : un rapport qui
    n'en montrerait qu'un, ou qui recopierait le meme chiffre, se verrait.
    """
    def faux(**kwargs):
        cible = kwargs["fps_target"]
        frames = _frames_attendues(cible)
        dossier = extract_frames_dir(Path(dossier_projet), RUSH_VISE, cible)
        dossier.mkdir(parents=True, exist_ok=True)
        for rang in range(2):
            (dossier / f"{rang:04d}.tiff").write_bytes(b"x" * (10 + rang))
        emetteur = progression.EmetteurProgression(
            kwargs.get("rappel_progression"), frames)
        emetteur.emettre(frames)
        return extraction.ExtractionOutcome(
            granted=True, message=f"{frames} frame(s)",
            lot_id=build_lot_id(RUSH_VISE, cible),
            frames_dir=dossier, written_frame_count=frames)

    return faux


def _frames_attendues(fps_target: float) -> int:
    for valeur in VALEURS_COCHEES:
        if abs(float(valeur) - fps_target) < 1e-9:
            return compte_du_coeur(valeur)
    raise AssertionError(f"cadence inattendue au coeur : {fps_target!r}")


def chaine(tmp_path):
    """La chaine REELLE du produit, avec le parcours REEL cable.

    Les seuls doubles entrent par les portes que le parcours expose -- le
    sondage et l'appel du coeur. **Aucun ecran n'est remplace, aucun
    enchainement n'est court-circuite**, et surtout pas celui qui monte `E2-5` :
    c'est lui qu'on mesure.
    """
    dossier, _video = projet(tmp_path)

    def rappel(app, dossier_du_menu, rush_id):
        return atelier.ouvrir_les_cadences(
            app, dossier_du_menu, rush_id,
            extraire=extracteur(dossier), logger=JournalMuet(),
            verifier_l_affichage=lambda: None)

    lien = atelier.ChaineReelle(ouvrir_les_cadences=rappel)
    lien.menu.dossier = lien.palier_projet.dossier = dossier
    lien.menu.charger()
    lien.dossier = dossier
    return lien


async def jusqu_au_resultat(pilote, lien):
    """Le parcours COMPLET au clavier : menu -> `E2-1` -> ... -> `E2-5`.

    Rend `(ecran des rushes, ecran de resultat)` : le premier est la cible de
    la suite « Extraire un autre rush », et le mesurer par **identite** vaut
    mieux que par classe -- deux `EcranRushes` differents seraient deux etats
    differents de la liste.
    """
    pilote.app.descendre()
    await pilote.pause()
    lien.menu.traiter("enter")                   # Extraction, en tete de liste
    await pilote.pause()
    rushes = pilote.app.screen
    rushes.liste.viser(RUSH_VISE)
    rushes.traiter("enter")
    await pilote.pause()
    cadences = pilote.app.screen
    for rang in RANGS_COCHES:
        cadences.liste.curseur = rang
        cadences.liste.basculer()
    cadences.traiter(None, "x")                  # droit au point de jugement
    await pilote.pause()
    panneau = pilote.app.screen
    panneau.choix.viser(atelier.ISSUE_EXTRAIRE)
    panneau.traiter("enter")
    await pilote.pause()
    await pilote.pause()
    return rushes, pilote.app.screen


def choisir(ecran: EcranResultat, suite: str) -> None:
    """Poser le curseur SUR la suite nommee, puis valider -- comme au clavier."""
    ecran.curseur = ecran.suites.index(suite)
    ecran.choisir()


# ===========================================================================
# LE DEFAUT : le rappel n'etait pas injecte par le produit
# ===========================================================================

def test_le_PRODUIT_injecte_le_rappel_des_suites_de_E2_5(tmp_path, banc, sonde):
    """La panne elle-meme, prise par le chemin du produit et par lui seul.

    Sans injection, `EcranResultat._sur_suite` vaut `None` et **toute** suite
    autre que le retour tombe sur l'ecran « pas encore ». C'est ce qu'Egan a
    vu : « Retour aux ateliers marche, les trois autres ne font rien. »
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        rushes, resultat = await jusqu_au_resultat(pilote, lien)
        return resultat, resultat.suites

    resultat, suites = banc(lien.app, scenario)
    assert isinstance(resultat, EcranResultat), type(resultat).__name__
    assert resultat._sur_suite is not None, (
        "le produit n'injecte pas le rappel des suites : les quatre suites de "
        "E2-5 sont navigables et ne menent nulle part, ce qui est le defaut "
        "que le lot K3 ferme")
    # La suite qu'on exerce en premier est au rang 2 sur 4 : ni la premiere,
    # ni la derniere (`CLAUDE.md`, regle des fabriques, points 2 et 2 bis).
    assert suites == [atelier.SUITE_DOSSIER, atelier.SUITE_PDF,
                      atelier.SUITE_AUTRE_RUSH, EcranResultat.RETOUR]
    assert suites.index(atelier.SUITE_AUTRE_RUSH) == 2


def test_le_point_d_appel_DU_PRODUIT_passe_sur_suite(tmp_path):
    """Le defaut lu **a la source**, la ou il a vecu.

    Meme geste que `test_journal_du_produit.py` sur `ChaineReelle.extraire` :
    la seconde moitie d'une panne de cablage se lit au point d'appel, et un
    banc de comportement seul laisserait passer un correctif qui rebranche
    ailleurs. Les deux maillons sont mesures : `_ecrire` -> mot-cle
    `sur_suite`, puis `conclure_l_extraction` -> `ouvrir_le_resultat`.

    **Les deux maillons ont change de nom le 2026-09-06, pas de nature.** Le
    passage de la passe au fil de travail a scinde `executer_et_conclure` :
    le travail de coeur part au fil (`lancer_l_extraction`), et le toucher de
    l'arbre de widgets -- dont `ouvrir_le_resultat`, qui porte le rappel --
    reste sur la boucle (`conclure_l_extraction`). La chaine mesuree est la
    meme, maillon pour maillon ; c'est la premiere fonction de chaque paire
    qui a bouge.
    """
    def mots_cles(fonction, appelee: str) -> set[str]:
        arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
        appels = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, "attr", getattr(n.func, "id", None))
                  == appelee]
        assert len(appels) == 1, (
            f"{appelee} doit avoir UN point d'appel ici, vu {len(appels)}")
        return {mot.arg for mot in appels[0].keywords}

    assert "sur_suite" in mots_cles(atelier.ParcoursExtraction._ecrire,
                                    "lancer_l_extraction"), (
        "le parcours du produit n'injecte pas `sur_suite` : c'est LA panne")
    assert "sur_suite" in mots_cles(atelier.lancer_l_extraction,
                                    "conclure_l_extraction"), (
        "le rappel s'arrete au lanceur : la conclusion ne le recoit pas")
    assert "sur_suite" in mots_cles(atelier.conclure_l_extraction,
                                    "ouvrir_le_resultat"), (
        "le rappel s'arrete a `conclure_l_extraction` : `E2-5` le recoit "
        "`None` et se replie sur l'ecran « pas encore »")
    # Le chemin SYNCHRONE porte la meme chaine : il reste le seul que les
    # bancs empruntent, et un `sur_suite` perdu la ferait mentir sur ce que le
    # produit fait.
    assert "sur_suite" in mots_cles(atelier.executer_et_conclure,
                                    "conclure_l_extraction"), (
        "`executer_et_conclure` ne transporte plus `sur_suite`")


# ===========================================================================
# « Extraire un autre rush » -> la page d'ouverture de l'atelier
# ===========================================================================

def test_extraire_un_autre_rush_REMONTE_A_LA_LISTE_DES_RUSHES(
        tmp_path, banc, sonde):
    """Egan, 2026-08-30 : « ca doit mener a la page d'ouverture de l'atelier,
    c'est-a-dire la liste des rushes ».

    La cible est mesuree **par identite** : c'est l'ecran `E2-1` par lequel on
    est descendu qui doit revenir, pas un homonyme reconstruit.
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        rushes, resultat = await jusqu_au_resultat(pilote, lien)
        choisir(resultat, atelier.SUITE_AUTRE_RUSH)
        await pilote.pause()
        return (rushes, pilote.app.screen, pilote.app.rang,
                pilote.app.passages_empiles)

    rushes, ecran, rang, passages = banc(lien.app, scenario)
    assert ecran is rushes, (
        f"« {atelier.SUITE_AUTRE_RUSH} » mene a {type(ecran).__name__} et non "
        "a la liste des rushes")
    assert passages == 0, (
        "des passages restent empiles au-dessus de E2-1 : Echap y "
        "redescendrait, ce qui est le defaut `V2-M1`")
    # **`EPIC11-ARB-13`, verbatim** : « La fin d'une execution ramene au **menu
    # des ateliers du projet ouvert** [...], jamais a l'ecran projet. » Cette
    # suite-ci s'arrete un cran EN DESSOUS du menu -- dans l'atelier.
    assert rang > lien.app.RANG_DES_ATELIERS, (
        f"on est remonte jusqu'au rang {rang} : la suite « extraire un autre "
        "rush » quitte l'atelier au lieu d'y revenir")


def test_le_RETOUR_reste_le_RETOUR_meme_avec_le_rappel_injecte(
        tmp_path, banc, sonde):
    """Volet symetrique, et il n'est pas decoratif : le rappel injecte ne doit
    pas capturer « Retour aux ateliers ».

    `EcranResultat.choisir` traite le retour **avant** de consulter le rappel ;
    un rappel qui l'attraperait ferait rester dans l'atelier une fin
    d'execution qu'`EPIC11-ARB-13` renvoie au menu -- verbatim : « La fin d'une
    execution ramene au **menu des ateliers du projet ouvert** [...], jamais a
    l'ecran projet. »
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        _rushes, resultat = await jusqu_au_resultat(pilote, lien)
        choisir(resultat, EcranResultat.RETOUR)
        await pilote.pause()
        return pilote.app.screen, pilote.app.rang, pilote.app.tache_en_cours

    ecran, rang, tache = banc(lien.app, scenario)
    assert ecran is lien.menu, type(ecran).__name__
    assert rang == lien.app.RANG_DES_ATELIERS
    assert tache is False


# ===========================================================================
# « Ouvrir le dossier des lots » -> l'explorateur du bureau (`EPIC11-ARB-85`)
# ===========================================================================

def test_ouvrir_le_dossier_REMET_LE_PARENT_COMMUN_des_DEUX_lots(
        tmp_path, banc, sonde, monkeypatch):
    """La suite ouvre un dossier **mesure**, pas recompose.

    Deux lots sont ecrits, dans deux dossiers **distincts** : ce qui part a
    l'explorateur est leur **parent commun**, faute de quoi il faudrait elire
    un lot et cacher l'autre derriere un libelle qui les annonce au pluriel.

    L'attendu est epingle sur `project_layout.EXTRACT_FRAMES_DIRNAME`, **jamais derive
    de `dossier_a_ouvrir` elle-meme** : un banc qui deriverait son attendu de la
    fonction mesuree serait tautologique -- c'est le mutant `M20` du lot `J`,
    ou muter la fonction changeait les deux cotes de l'egalite a la fois.
    """
    lien = chaine(tmp_path)
    vus = []
    monkeypatch.setattr(atelier, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier, **kwargs: vus.append(Path(dossier))
                        or "ouvert")

    async def scenario(pilote):
        _rushes, resultat = await jusqu_au_resultat(pilote, lien)
        choisir(resultat, atelier.SUITE_DOSSIER)
        await pilote.pause()
        return pilote.app.screen, resultat

    ecran, resultat = banc(lien.app, scenario)
    lots = [extract_frames_dir(lien.dossier, RUSH_VISE, float(valeur))
            for valeur in VALEURS_COCHEES]
    assert len(set(lots)) == 2 and all(d.is_dir() for d in lots), lots
    assert vus == [lien.dossier / EXTRACT_FRAMES_DIRNAME], (
        f"ce qui part a l'explorateur est {vus}, et non le parent commun des "
        f"deux lots {lots}")
    # **L'ecran ne change pas** : le compte rendu reste lisible pendant qu'on
    # regarde le dossier. Descendre d'un palier le ferait perdre.
    assert ecran is resultat, type(ecran).__name__


def test_ouvrir_le_dossier_DIT_ce_qui_s_est_passe_sur_la_LIGNE_D_ETAT(
        tmp_path, banc, sonde):
    """Le resultat est DIT, et c'est la moitie du correctif.

    Un echec silencieux serait indistinguable de la suite decorative que ce lot
    corrige. Dans un conteneur sans bureau -- le regime nominal du banc et de
    la machine ou le defaut a ete trouve --, la phrase NOMME le motif et garde
    le chemin lisible : c'est ce qui reste utilisable a la main.

    **Une mesure, jamais une touche ni un conseil.** `EPIC11-ARB-56`,
    verbatim : la ligne d'etat « ne porte **aucune touche** [...] **aucun
    conseil d'usage** [...] **aucun motif de conception** ».
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        _rushes, resultat = await jusqu_au_resultat(pilote, lien)
        choisir(resultat, atelier.SUITE_DOSSIER)
        await pilote.pause()
        # La ligne d'etat est LUE SUR L'ECRAN, pas sur ce qu'on croit y avoir
        # pose : `poser_etat` memorise le texte brut sur le palier, et c'est ce
        # texte-la qui est redessine a chaque redimensionnement.
        return resultat._etat_courant

    etat = banc(lien.app, scenario)
    assert str(lien.dossier / EXTRACT_FRAMES_DIRNAME) in etat, etat
    for touche in ("Entree", "\u23ce", "\xc9chap", "Echap", "Tab", "F1",
                   "appuyez", "il faut", "pensez"):
        assert touche not in etat, (touche, etat)


def test_le_dossier_d_UN_SEUL_lot_est_LE_SIEN_et_pas_son_parent(tmp_path):
    """Second volet du parent commun, et il tient l'autre bout.

    Sans lui, un `dossier_a_ouvrir` qui rendrait TOUJOURS le parent ferait
    ouvrir le dossier de tous les lots du projet la ou un seul a ete ecrit.
    """
    seul = tmp_path / EXTRACT_FRAMES_DIRNAME / "rush_01_25"
    rapport = atelier.RapportExtraction(lots_ecrits=(
        atelier.LotEcrit("rush_01_25", 124, 25.0, 10, seul),))
    assert atelier.dossier_a_ouvrir(rapport) == seul


def test_un_rapport_SANS_lot_ecrit_le_DIT_au_lieu_d_OUVRIR_LE_PROJET(tmp_path):
    """Volet symetrique : il n'y a alors aucun dossier a ouvrir.

    Ouvrir celui du projet serait repondre a une autre question, et ouvrir
    silencieusement n'importe quoi est pire que de ne rien ouvrir.
    `suites_du_resultat` ne propose pas la suite dans ce cas ; ce volet tient si
    un jour elle la proposait.
    """
    vide = atelier.RapportExtraction()
    assert atelier.dossier_a_ouvrir(vide) is None
    assert atelier.SUITE_DOSSIER not in atelier.suites_du_resultat(vide)

    app = _AppEspionne()
    parcours = atelier.ParcoursExtraction(app, tmp_path, RUSH_VISE,
                                          logger=JournalMuet())
    parcours.suivre(atelier.SUITE_DOSSIER)
    assert app.faits == [("etat", atelier.AUCUN_LOT_A_OUVRIR)], app.faits


# ===========================================================================
# « Composer les planches » : la suite qui a cesse d'etre sans destination
# ===========================================================================

def test_composer_une_planche_N_EST_PLUS_UN_ECRAN_PAS_ENCORE(
        tmp_path, banc, sonde):
    """**Ce test disait l'inverse jusqu'au 2026-09-06, et il etait vert.**

    Il portait : « L'atelier Pdf n'existe pas : la suite NOMME l'absence et son
    echeance », sur la consigne d'Egan du point 4 du lot `K3` -- « composer une
    planche n'est pas prete, elle doit continuer de mener a l'ecran "pas
    encore" ». La consigne etait juste **le 2026-08-30** ; la story 11.7 a
    livre l'atelier Pdf le 2026-09-02, `ChaineReelle.atelier_pdf` le cable, et
    la condition a laquelle la consigne etait suspendue a cesse d'exister. Le
    filet, lui, continuait de fonctionner : c'est pourquoi rien n'a rougi, et
    pourquoi il aura fallu jouer le parcours au clavier pour le voir (`MQ-4`,
    audit du 2026-09-06).

    Ce banc garde ici le **volet negatif**, qui est ce qu'aucun test positif ne
    verrait revenir : la suite ne doit plus jamais retomber sur `EcranPasEncore`.
    Ou elle mene est mesure par
    `test_suites_qui_ouvrent_leur_atelier.py`, et le fait mecanique -- toute
    `SUITE_*` declaree porte une branche nommee -- par
    `test_couverture_des_suites.py`.
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        _rushes, resultat = await jusqu_au_resultat(pilote, lien)
        choisir(resultat, atelier.SUITE_PDF)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(lien.app, scenario)
    assert not isinstance(ecran, EcranPasEncore), (
        "« Composer les planches de ces lots » est retombee dans le filet "
        "alors que l'atelier Pdf est livre : c'est la rechute de `MQ-4`")


# ===========================================================================
# La dispatch : TROIS suites, TROIS destinations deux a deux distinctes
# ===========================================================================

class _AppEspionne:
    """Une application qui NOTE ce qu'on lui demande, sans rien dessiner.

    Elle porte les trois surfaces que `suivre` touche -- descendre, depiler,
    poser un etat -- et rien d'autre : c'est ce qui rend les trois
    destinations comparables **par ce qu'elles font**, la ou un banc d'ecran
    les comparerait par le nom de la classe montee.
    """

    QUAND_ARRIVENT_LES_ATELIERS = CoqueTui.QUAND_ARRIVENT_LES_ATELIERS
    ascii_seul = False

    def __init__(self) -> None:
        self.faits: list[tuple] = []
        self.screen_stack = [object(), object()]
        self.passages_empiles = 1
        self.palier_courant = self

    def descendre(self, ecran) -> None:
        self.faits.append(("descendre", getattr(ecran, "ce_qui_manque", None)))

    def pop_screen(self) -> None:
        self.passages_empiles = 0
        self.faits.append(("depiler", None))

    def revenir_aux_ateliers(self) -> None:
        """La quatrieme surface, depuis `MQ-4` : une suite peut changer d'atelier.

        Elle est **distincte** de `pop_screen` a dessein : « remonter a la page
        d'ouverture de l'atelier » et « remonter au menu des ateliers » sont
        deux destinations differentes, et les confondre ici rendrait deux
        suites indiscernables dans les faits notes.
        """
        self.faits.append(("ateliers", None))

    def poser_etat(self, texte: str) -> None:
        self.faits.append(("etat", texte))


def test_les_TROIS_suites_menent_a_TROIS_endroits_DEUX_A_DEUX_DIFFERENTS(
        tmp_path, monkeypatch):
    """La frontiere qui ferme la dispatch.

    Une `suivre` qui rendrait toujours la meme destination passerait chacun des
    tests ci-dessus **pris a part** : chacun n'exerce qu'une suite. Ici les
    trois sont jouees, et leurs effets doivent etre deux a deux distincts.
    """
    monkeypatch.setattr(atelier, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda dossier, **kwargs: f"ouvert {dossier}")
    lot = tmp_path / EXTRACT_FRAMES_DIRNAME / "rush_01_25"
    lot.mkdir(parents=True)
    rapport = atelier.RapportExtraction(lots_ecrits=(
        atelier.LotEcrit("rush_01_25", 124, 25.0, 10, lot),))

    ou = {}
    for suite in (atelier.SUITE_DOSSIER, atelier.SUITE_PDF,
                  atelier.SUITE_AUTRE_RUSH):
        app = _AppEspionne()
        parcours = atelier.ParcoursExtraction(
            app, tmp_path, RUSH_VISE, logger=JournalMuet(),
            # **Le double du point d'entree Pdf, et rien de plus** : ce banc
            # mesure la DISPATCH, pas ou l'atelier Pdf mene -- cela vit dans
            # `test_suites_qui_ouvrent_leur_atelier.py`, sur le produit.
            composer_les_planches=lambda a, d: a.faits.append(("pdf", d)))
        parcours.rapport = rapport
        parcours.suivre(suite)
        ou[suite] = app.faits

    assert ou[atelier.SUITE_DOSSIER] == [("etat", f"ouvert {lot}")], ou
    # **Ce que cette ligne attendait jusqu'au 2026-09-06** :
    # `[("descendre", atelier.SUITE_PDF)]`, c'est-a-dire le filet
    # `EcranPasEncore`. C'etait `MQ-4` -- l'atelier Pdf etait livre depuis le
    # 2026-09-02 et la suite n'y menait pas.
    assert ou[atelier.SUITE_PDF] == [("ateliers", None), ("pdf", tmp_path)], ou
    assert ou[atelier.SUITE_AUTRE_RUSH] == [("depiler", None)], ou
    assert len({tuple(faits) for faits in ou.values()}) == 3, ou


def test_une_suite_INCONNUE_nomme_l_absence_au_lieu_de_NE_RIEN_FAIRE(tmp_path):
    """Le filet, et c'est lui qui empeche la rechute.

    Une suite ajoutee demain a `suites_du_resultat` et oubliee dans `suivre`
    doit **dire** qu'elle ne mene nulle part. Sans ce dernier `descendre`, elle
    redeviendrait exactement ce que ce lot corrige : muette.
    """
    app = _AppEspionne()
    parcours = atelier.ParcoursExtraction(app, tmp_path, RUSH_VISE,
                                          logger=JournalMuet())
    parcours.suivre("Une suite que personne n'a cablee")
    assert app.faits == [("descendre", "Une suite que personne n'a cablee")], (
        f"la suite inconnue a fait {app.faits} : elle doit NOMMER l'absence")


# ===========================================================================
# `remonter_a_l_ouverture_de_l_atelier` : ce qu'elle depile, et ce qu'elle garde
# ===========================================================================

class _Station(Palier):
    """Un palier qui n'est pas un passage -- la page d'ouverture d'un atelier."""

    TRANSITOIRE = False

    def __init__(self, nom: str) -> None:
        super().__init__()
        self.nom = nom


class _Passage(Palier):
    """Un ecran transitoire : formulaire, execution, resultat."""

    TRANSITOIRE = True

    def __init__(self, nom: str) -> None:
        super().__init__()
        self.nom = nom


def test_remonter_depile_LES_PASSAGES_et_s_arrete_a_LA_STATION(banc):
    """**Trois** passages empiles, et la station visee est celle du milieu de
    la pile -- ni le sommet, ni la racine.

    Une pile a un seul passage ne distingue pas « depile les passages » de
    « depile un ecran », et une pile dont la cible est la racine ne distingue
    pas « s'arrete a la station » de « depile tout ».
    """
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter")],
                   contexte=Contexte("projet_demo"))
    station = _Station("ouverture de l'atelier")

    async def scenario(pilote):
        pilote.app.descendre()                       # rang 1 : les ateliers
        await pilote.pause()
        pilote.app.descendre(station)                # rang 2 : la station
        await pilote.pause()
        for nom in ("formulaire", "execution", "resultat"):
            pilote.app.descendre(_Passage(nom))
            await pilote.pause()
        avant = (pilote.app.passages_empiles, len(pilote.app.screen_stack))
        atelier.remonter_a_l_ouverture_de_l_atelier(pilote.app)
        await pilote.pause()
        return avant, pilote.app.screen, pilote.app.passages_empiles

    avant, ecran, passages = banc(app, scenario)
    assert avant == (3, 6), f"la pile de depart ne mesure rien : {avant}"
    assert ecran is station, type(ecran).__name__
    assert passages == 0


def test_remonter_sur_une_pile_SANS_passage_ne_depile_RIEN(banc):
    """Volet symetrique : appelee depuis la station elle-meme, la fonction ne
    remonte pas d'un cran de plus -- sinon la suite quitterait l'atelier."""
    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                            PalierTemoin("Ateliers", "q quitter")],
                   contexte=Contexte("projet_demo"))
    station = _Station("ouverture de l'atelier")

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre(station)
        await pilote.pause()
        hauteur = len(pilote.app.screen_stack)
        atelier.remonter_a_l_ouverture_de_l_atelier(pilote.app)
        await pilote.pause()
        return hauteur, len(pilote.app.screen_stack), pilote.app.screen

    avant, apres, ecran = banc(app, scenario)
    assert (avant, apres) == (3, 3)
    assert ecran is station
