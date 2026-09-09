# -*- coding: utf-8 -*-
"""Story 11.4, lot `K1` -- les deux defauts qu'Egan a trouves A LA MAIN.

Les deux datent du 2026-08-30, tous deux trouves en **utilisant** le produit,
et tous deux invisibles pour les 1 619 bancs de `tests/unit/tui` :

* **`K1.1`** -- `Ajouter un rush` ouvrait l'explorateur, on designait une vraie
  video, et **rien** ne se passait : ni ajout, ni message, ni refus. Le rappel
  `EcranRushes(..., ajouter=...)` n'etait injecte **nulle part** dans le
  produit (`grep -rn "ajouter=" src/mixed_media_utility/tui/` rendait zero), et
  le `if ... is not None` qui le gardait transformait ce manque en **no-op
  silencieux**. Quatrieme occurrence dans cet epic du meme mode de panne -- un
  composant livre, teste, et cable nulle part -- et la pire des quatre : les
  trois autres se voyaient a l'ecran ;
* **`K1.2`** -- `⏎` sur `E2-2` ouvrait la fenetre de previz **immediatement**,
  et l'ecran d'instructions de la TUI n'apparaissait qu'**apres** sa fermeture,
  ou il annoncait au passe (« une fenetre s'est ouverte ») ce qui venait de se
  terminer. `EcranPreviz.demarrer()` -- donc le montage -- appelait le joueur,
  et le joueur BLOQUE.

**Pourquoi ce fichier plutot qu'un ajout aux bancs existants.** Le banc qui
aurait vu `K1.1` doit exercer le chemin **du produit**, pas un ecran construit
a la main avec son rappel injecte : c'est exactement le piege que
`test_journal_du_produit.py` raconte -- « le banc mesurait un parcours qui
n'est pas celui du produit, sur le seul point ou les deux different ». Ici,
la moitie `K1.1` part donc de :func:`atelier.chaine_du_produit`, jamais d'un
`ChaineReelle(...)` assemble pour le test, et jamais d'un `EcranRushes(...)`
construit a la main.

**Regle des fabriques**, point 2 bis compris : trois rushes au manifeste avec
le vise au **milieu**, trois videos dans le dossier avec la cible au
**milieu**, trois cadences aux trois comptes distincts avec l'echec en
troisieme. Un `find` qui rendrait le premier element et une boucle qui
s'arreterait au premier echec se demasquent tous deux.
"""
import ast
import inspect
import json
import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from textual.css.query import NoMatches
from textual.widgets import Static

from mixed_media_utility import cadence_previz, frame_selection
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.tui import atelier_extraction as amont
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui import cadences, jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, EcranPasEncore
from mixed_media_utility.tui.coque import PalierTemoin

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]


# ===========================================================================
# `K1.1` -- « Ajouter un rush », par le chemin DU PRODUIT
# ===========================================================================

#: Trois rushes au manifeste, le vise **au milieu** (regle des fabriques,
#: point 2 et point 2 bis) : ni premier -- un `find` fautif le rendrait --, ni
#: dernier -- une boucle qui s'arreterait trop tot le rendrait aussi.
RUSHES = ("rush_00_avant", "rush_01_vise", "rush_02_apres")
RUSH_VISE = RUSHES[1]

#: Trois videos dans le dossier de l'explorateur, la cible **au milieu**.
#: Les noms sont ordonnes : l'explorateur trie, et une cible en tete ou en
#: queue laisserait passer un curseur qui ne bouge pas.
VIDEOS = ("a_premiere.mov", "b_cible.mov", "c_derniere.mov")
VIDEO_CIBLE = VIDEOS[1]


def projet_reel(tmp_path) -> Path:
    """Un projet reel, ses trois rushes lies a trois fichiers distincts."""
    dossier = creer_projet(tmp_path, "projet_demo").chemin
    sources = tmp_path / "sources"
    sources.mkdir()
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    entrees = []
    for rang, rush_id in enumerate(RUSHES):
        # Des tailles DIFFERENTES : un appariement positionnel entre l'entree
        # du manifeste et le fichier se verrait.
        chemin = sources / f"{rush_id}.mov"
        chemin.write_bytes(b"x" * (10 + rang))
        entrees.append({"rush_id": rush_id, "source_path": str(chemin)})
    document["rushes"] = entrees
    (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                             encoding="utf-8")
    return dossier


def dossier_des_videos(tmp_path) -> Path:
    """Les trois videos que l'explorateur listera, la cible au milieu."""
    dossier = tmp_path / "rushes_a_ajouter"
    dossier.mkdir()
    for rang, nom in enumerate(VIDEOS):
        (dossier / nom).write_bytes(b"y" * (20 + rang))
    return dossier


def produit(tmp_path):
    """La chaine **DU PRODUIT**, sur un projet reel. Aucun rappel de test.

    C'est le point de tout ce bloc : `chaine_du_produit` est « ici, et nulle
    part ailleurs » l'endroit ou le produit cable ses rappels. Un banc qui
    construirait `ChaineReelle(...)` avec les siens ne pourrait pas voir qu'un
    rappel manque -- il l'aurait fourni.
    """
    lien = atelier.chaine_du_produit()
    lien.menu.dossier = lien.palier_projet.dossier = projet_reel(tmp_path)
    lien.menu.charger()
    return lien


async def jusqu_a_E2_1(pilote, lien):
    """Descendre au menu, entrer dans l'atelier Extraction. Rien de plus."""
    pilote.app.descendre()
    await pilote.pause()
    lien.menu.traiter("enter")               # Extraction, en tete de liste
    await pilote.pause()
    return pilote.app.screen


async def designer_la_video(pilote, ecran):
    """`Tab`, puis descendre sur la video du MILIEU, puis `⏎`.

    Le curseur est deplace jusqu'a la cible, et la cible est **verifiee** avant
    la validation : sans ce controle, un test qui validerait la premiere entree
    de la liste passerait tout aussi bien et ne mesurerait plus le geste.
    """
    ecran.traiter("tab")
    await pilote.pause()
    assert ecran.zone == amont.ZONE_EXPLORATEUR
    for _ in range(len(ecran.explorateur.entrees)):
        cible = ecran.explorateur.cible_de_validation()
        if cible is not None and cible.name == VIDEO_CIBLE:
            break
        ecran.traiter("down")
    cible = ecran.explorateur.cible_de_validation()
    assert cible is not None and cible.name == VIDEO_CIBLE, cible
    ecran.traiter("enter")
    await pilote.pause()
    return cible


def test_le_PRODUIT_ne_reste_PAS_MUET_quand_on_ajoute_un_rush(
        tmp_path, banc, monkeypatch):
    """**Le banc qui aurait vu le defaut**, et il part du produit.

    Egan choisit `Ajouter un rush`, designe une vraie video, et **rien** ne se
    passe. Ce qui est mesure ici n'est pas « le rush est ajoute » -- le coeur
    n'a aujourd'hui aucun point d'entree pour declarer un rush sans l'extraire
    -- mais que le produit **dise ce qui manque** au lieu de se taire.

    La mesure porte sur l'ecran du sommet de la pile : un no-op silencieux
    laisse `E2-1` en place, et c'est exactement ce que l'operateur a vu.

    **CE QUI A CHANGE le 2026-09-05, et la mesure avec** (lot des ecrans de
    declaration, `EPIC11-ARB-226`). La phrase ci-dessus -- « le coeur n'a
    aujourd'hui aucun point d'entree pour declarer un rush sans l'extraire » --
    n'est plus vraie : `preparer_une_declaration` et `ecrire_la_declaration`
    existent, `ChaineReelle.atelier_extraction` les injecte, et le produit va
    donc **jusqu'au coeur**. Ce que ce banc designe est une video de SYNTHESE
    -- trois octets nommes `.mov` -- que `ffprobe` ne sait pas lire : le coeur
    la refuse par `source_non_qualifiee`, et c'est ce refus qui monte ici.

    **Ce que le test mesure n'a pas bouge d'un mot** : le produit ne reste pas
    muet, il ne reste pas sur `E2-1`, et il NOMME le fichier designe. Ce qui a
    bouge, c'est la phrase -- `ce_qui_manque_pour_refuser` au lieu de
    `ce_qui_manque_pour_ajouter` --, et il fallait choisir entre l'ajuster ici
    ou donner une vraie video a ce banc. La premiere garde ce banc pur
    (aucun `ffprobe` reel a payer, aucun objet LFS a resoudre) ; le chemin
    NOMINAL, celui ou le panneau chiffre monte pour de bon, est mesure sur le
    rush reel du depot par `test_ecrans_declaration_de_rush.py`.
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    lien = produit(tmp_path)

    async def scenario(pilote):
        ecran = await jusqu_a_E2_1(pilote, lien)
        assert isinstance(ecran, amont.EcranRushes), ecran
        cible = await designer_la_video(pilote, ecran)
        return pilote.app.screen, cible

    sommet, cible = banc(lien.app, scenario)

    assert not isinstance(sommet, amont.EcranRushes), (
        "le produit est reste sur E2-1 sans rien dire : c'est LE defaut K1.1, "
        "un `if ... is not None` qui rend None et transforme un rappel absent "
        "en no-op silencieux")
    assert isinstance(sommet, EcranPasEncore), sommet
    rendu = "\n".join(sommet.lignes())
    assert cible.name in rendu, (
        "l'ecran ne nomme pas le fichier designe : l'operateur ne peut pas "
        "savoir que son geste a ete recu")
    assert amont.ce_qui_manque_pour_refuser(
        "source_non_qualifiee", cible.name) in rendu, rendu


def test_AUCUNE_ECHEANCE_n_est_inventee_pour_ce_qui_n_est_pas_arbitre(
        tmp_path, banc, monkeypatch):
    """Volet symetrique : nommer ce qui manque, sans promettre de date.

    Ce que `Ajouter un rush` attend est un point d'entree de coeur qui n'existe
    pas et n'est pas encore arbitre -- lui coller `QUAND_ARRIVENT_LES_ATELIERS`
    ferait attendre une vague qui ne le porte pas.

    **Le principe tient, sa formulation d'origine non**, et la reference est
    corrigee ici plutot que recopiee : ce docstring citait
    `ChaineReelle.entrer_commande`, « sans annoncer d'echeance, faute d'en
    connaitre une : une date inventee vaudrait moins que pas de date ». Cette
    phrase n'existe plus (`MQ-8`, 2026-09-06) : le palier Projet annonce
    desormais `QUAND_LA_PORTE_VERS_UN_FICHIER`, une echeance **vraie** qui ne
    promet ni date ni vague. Ce qui est interdit est d'inventer un calendrier,
    pas de nommer ce qui manque -- et ici, contrairement au palier Projet,
    personne ne sait encore **quoi** nommer, donc le silence reste juste.
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    lien = produit(tmp_path)

    async def scenario(pilote):
        ecran = await jusqu_a_E2_1(pilote, lien)
        await designer_la_video(pilote, ecran)
        return pilote.app.screen

    sommet = banc(lien.app, scenario)
    assert sommet.quand == ""
    assert "arrive" not in "\n".join(sommet.lignes()).lower()


def test_le_rappel_d_ajout_INJECTE_est_APPELE_avec_la_cible_exacte(
        tmp_path, banc, monkeypatch):
    """Volet symetrique du precedent : quand le rappel est la, il TRAVAILLE.

    Sans ce volet, un correctif qui montrerait « pas encore » **meme avec un
    rappel injecte** passerait le test d'au-dessus tout en rendant le cablage
    a venir inerte -- c'est-a-dire en rejouant la panne d'un cran plus loin.
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    ajoutes = []
    ecran = amont.EcranRushes(projet_reel(tmp_path), ajouter=ajoutes.append)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        cible = await designer_la_video(pilote, ecran)
        return pilote.app.screen, cible

    sommet, cible = banc(coque(ecran), scenario)

    assert ajoutes == [cible], ajoutes
    assert not isinstance(sommet, EcranPasEncore), (
        "un rappel injecte mene quand meme a « pas encore » : le cablage "
        "serait inerte")
    assert sommet is ecran
    assert ecran.zone == amont.ZONE_LISTE, "l'explorateur se referme"


def test_la_liste_est_RELUE_apres_un_ajout_sinon_l_ecriture_reste_INVISIBLE(
        tmp_path, banc, monkeypatch):
    """Le rappel ecrit au manifeste -- l'ecran doit le VOIR.

    Un rappel qui ecrirait sans que `E2-1` relise laisserait l'operateur devant
    une liste inchangee : du point de vue de l'ecran, c'est le meme silence que
    `K1.1`, une case plus loin. La mesure se fait donc sur la LISTE apres coup,
    pas sur l'appel du rappel.

    Le rush ajoute est nomme pour arriver **au milieu** du manifeste, jamais en
    tete ni en queue : une relecture qui ne rendrait qu'un prefixe ou qu'un
    suffixe de la liste se verrait.
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    dossier = projet_reel(tmp_path)
    ajoute = "rush_01a_ajoute"

    def ajouter_au_manifeste(cible: Path) -> None:
        """Un double d'ecriture : il ecrit VRAIMENT, au bon endroit."""
        document = json.loads(
            (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        entrees = list(document["rushes"])
        entrees.insert(2, {"rush_id": ajoute, "source_path": str(cible)})
        document["rushes"] = entrees
        (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                                 encoding="utf-8")

    ecran = amont.EcranRushes(dossier, ajouter=ajouter_au_manifeste)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        avant = [rush.rush_id for rush in ecran.liste.rushes]
        await designer_la_video(pilote, ecran)
        return avant, [rush.rush_id for rush in ecran.liste.rushes]

    avant, apres = banc(coque(ecran), scenario)
    assert avant == list(RUSHES)
    assert apres == [RUSHES[0], RUSHES[1], ajoute, RUSHES[2]], apres


def test_AUCUN_rappel_de_E2_1_ne_peut_rester_MUET(tmp_path, banc, monkeypatch):
    """La regle, prise sur **les deux** rappels de l'ecran, jamais sur un seul.

    `ajouter` est celui qu'Egan a rencontre ; `extraire` est l'autre
    `if ... is not None` du meme ecran. Mesurer le premier seul laisserait le
    second libre de rouvrir le trou -- et ce sont bien deux chemins clavier
    distincts (`Tab` puis `⏎` dans l'explorateur, contre `⏎` sur la liste).
    """
    monkeypatch.chdir(dossier_des_videos(tmp_path))
    dossier = projet_reel(tmp_path)

    async def par_l_ajout(pilote, ecran):
        await designer_la_video(pilote, ecran)

    async def par_le_choix(pilote, ecran):
        ecran.liste.viser(RUSH_VISE)
        ecran.traiter("enter")
        await pilote.pause()

    muets = []
    for nom, geste in (("ajouter", par_l_ajout), ("extraire", par_le_choix)):
        ecran = amont.EcranRushes(dossier)      # aucun rappel : les DEUX nus

        async def scenario(pilote, geste=geste, ecran=ecran):
            pilote.app.descendre(ecran)
            await pilote.pause()
            await geste(pilote, ecran)
            return pilote.app.screen

        sommet = banc(coque(ecran), scenario)
        if not isinstance(sommet, EcranPasEncore):
            muets.append(nom)

    assert muets == [], (
        f"ces rappels absents ne disent RIEN : {muets}. Une touche qui ne fait "
        "rien et ne dit rien est indistinguable d'un clavier casse")


def test_le_rush_NOMME_par_le_refus_est_celui_du_CURSEUR(tmp_path, banc):
    """Le rush du milieu, jamais « le premier de la liste ».

    Meme mode de panne que le mutant `M25` de la story 5.7 : un `find` qui
    rend toujours la premiere entree passe une fabrique a un seul element, et
    passe aussi une fabrique dont la cible est en tete.
    """
    ecran = amont.EcranRushes(projet_reel(tmp_path))

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.liste.viser(RUSH_VISE)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    sommet = banc(coque(ecran), scenario)
    rendu = "\n".join(sommet.lignes())
    assert RUSH_VISE in rendu, rendu
    assert RUSHES[0] not in rendu and RUSHES[2] not in rendu, rendu


# ===========================================================================
# `K1.2` -- l'ecran d'instructions se peint AVANT que la fenetre ne s'ouvre
# ===========================================================================

#: La source des trois cadences : 124 frames a 25 im/s.
FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124

#: Trois cadences aux trois comptes DISTINCTS (124, 62, 42), l'echec en
#: troisieme : un appariement ligne/rapport inverse se verrait.
VALEURS_LUES = (Fraction(25), Fraction(25, 2), Fraction(25, 3))


def coque(ecran) -> CoqueTui:
    """Deux paliers temoins puis l'ecran mesure : la pile du banc."""
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


def selection(valeur: Fraction):
    return frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=valeur,
        source_frame_count=FRAMES_SOURCE)


def regardees() -> tuple[cadences.Cadence, ...]:
    return tuple(
        cadences.Cadence(valeur=valeur,
                         libelle=cadences.libelle_remarquable(diviseur),
                         compte=selection(valeur).expected_frame_count)
        for diviseur, valeur in zip((1, 2, 3), VALEURS_LUES))


def session() -> cadence_previz.PrevizSession:
    selections = tuple(selection(valeur) for valeur in VALEURS_LUES)
    return cadence_previz.PrevizSession(
        video_path=Path("/rushes/rush_01.mov"),
        fps_source=FPS_SOURCE,
        source_frame_count=FRAMES_SOURCE,
        source_frame_count_is_exact=True,
        start_timecode=None,
        stream_duration_seconds=None,
        fps_targets=tuple(float(valeur) for valeur in VALEURS_LUES),
        selections=selections,
        schedules=tuple(cadence_previz.build_schedule(sel, FPS_SOURCE)
                        for sel in selections),
        cadence_corroboree=True)


def rapport(valeur: Fraction, *, attendues: int, presentees: int | None = None):
    """Un `PlaybackReport` du VRAI producteur, jamais un double."""
    presentees = attendues if presentees is None else presentees
    pas = 1.0 / float(valeur)
    observations = [
        cadence_previz.FrameObservation(
            output_rank=rang + 1, source_index=rang, t_theo_s=rang * pas,
            t_real_s=rang * pas)
        for rang in range(presentees)]
    return cadence_previz.build_playback_report(
        observations, fps_target=float(valeur), frames_attendues=attendues,
        duree_nominale_s=max(attendues - 1, 0) * pas,
        frames_omises=attendues - presentees, partiel=False)


def resultat() -> cadence_previz.PrevizResult:
    """Trois passes, la NON TENUE en troisieme position."""
    return cadence_previz.PrevizResult(
        session=session(),
        reports=(rapport(VALEURS_LUES[0], attendues=124),
                 rapport(VALEURS_LUES[1], attendues=62),
                 rapport(VALEURS_LUES[2], attendues=42, presentees=32)),
        interrupted=False, decoded_frames=0, cache_hits=0, cache_misses=0)


def corps_peint(ecran) -> str:
    """Ce que l'ecran AFFICHE **a cet instant**, ou rien s'il n'a rien peint.

    C'est la mesure du defaut `K1.2` : une fenetre ouverte au montage
    photographie un corps VIDE, parce que `textual` n'a pas encore peint --
    c'est precisement ce qu'Egan a vu, la fenetre d'abord et l'ecran ensuite.
    """
    try:
        # `.content` -- le meme accesseur que le reste des bancs TUI ; `str()`
        # d'un `Text` de `rich` rend son texte nu, sans les balises de couleur.
        return str(ecran.query_one(f"#{amont.EcranPreviz.ID_DU_CORPS}",
                                   Static).content)
    except NoMatches:
        # Le widget n'existe pas encore : `textual` n'a rien compose. C'est
        # l'etat exact du defaut d'origine, et il se mesure comme un corps vide.
        return ""


class JoueurPhotographe:
    """Le joueur qui PHOTOGRAPHIE l'ecran a l'instant ou la fenetre s'ouvre.

    C'est le seul moyen de mesurer un ORDRE : compter les appels dit qu'on a
    joue, jamais qu'on a joue trop tot. La fenetre reelle bloque ; ce double
    bloque symboliquement, le temps de la photographie.
    """

    def __init__(self) -> None:
        self.ecran = None
        self.appels: list[object] = []
        self.corps_a_l_ouverture: str | None = None
        self.raccourcis_a_l_ouverture: str | None = None

    def __call__(self, session_jouee):
        self.appels.append(session_jouee)
        self.corps_a_l_ouverture = corps_peint(self.ecran)
        self.raccourcis_a_l_ouverture = self.ecran.raccourcis
        return resultat()


def previz(**kwargs) -> amont.EcranPreviz:
    """`E2-2b` sur un affichage disponible : le banc n'en a pas."""
    kwargs.setdefault("regardees", regardees())
    kwargs.setdefault("session", session())
    kwargs.setdefault("verifier_l_affichage", lambda: None)
    return amont.EcranPreviz(**kwargs)


def test_l_ecran_d_INSTRUCTIONS_est_PEINT_AVANT_que_la_fenetre_ne_s_ouvre(
        banc):
    """**Le banc qui aurait vu `K1.2`**, et il mesure un ORDRE.

    Egan, verbatim : « la fenetre de previz s'ouvre immediatement, et l'ecran
    d'instructions de la TUI n'apparait qu'apres la fermeture de la fenetre ».
    La photographie est prise **par le joueur lui-meme**, a l'instant ou la
    fenetre s'ouvrirait : un corps vide a cet instant, c'est un operateur
    devant un terminal vierge.
    """
    joueur = JoueurPhotographe()
    ecran = previz(jouer=joueur)
    joueur.ecran = ecran

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        # Ce que l'operateur voit AVANT de taper quoi que ce soit.
        avant = corps_peint(ecran)
        ecran.traiter("enter")
        await pilote.pause()
        return avant, corps_peint(ecran)

    avant, apres = banc(coque(ecran), scenario)

    assert amont.TITRE_PREVIZ_AVANT in avant, (
        "E2-2b ne peint pas ses instructions avant d'ouvrir : c'est le defaut "
        f"K1.2. Corps peint au montage : {avant!r}")
    assert joueur.corps_a_l_ouverture, (
        "la fenetre s'est ouverte sur un ecran encore VIDE : `textual` n'avait "
        "pas peint, exactement la panne d'origine")
    assert amont.TITRE_PREVIZ_AVANT in joueur.corps_a_l_ouverture
    assert joueur.raccourcis_a_l_ouverture == amont.RACCOURCIS_PREVIZ_AVANT
    # ... et une fois la fenetre fermee, l'ecran CONSTATE.
    assert amont.TITRE_PREVIZ in apres
    assert amont.TITRE_PREVIZ_AVANT not in apres
    assert amont.FILET_RAPPORT in apres


def test_le_MONTAGE_n_ouvre_AUCUNE_fenetre(banc):
    """La moitie negative : `demarrer()` ne joue plus rien du tout.

    Le compte est a **zero**, et il est pris apres le montage complet : c'est
    la mesure qui rougit si la lecture repart dans `demarrer`.
    """
    joueur = JoueurPhotographe()
    ecran = previz(jouer=joueur)
    joueur.ecran = ecran

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return list(joueur.appels), ecran.resultat

    appels, resultat_au_montage = banc(coque(ecran), scenario)
    assert appels == [], (
        "la fenetre s'ouvre encore au montage : `textual` ne peindra jamais "
        "E2-2b avant, puisque le joueur BLOQUE")
    assert resultat_au_montage is None


def test_le_PREMIER_entree_OUVRE_et_ne_CHOISIT_PAS(banc):
    """L'ecran d'instructions ne se saute pas.

    Un `⏎` qui ferait les deux d'un coup -- ouvrir puis choisir -- rendrait
    l'ecran d'attente invisible a nouveau, et le correctif serait cosmetique.
    Deux frappes, deux sens, dans cet ordre.
    """
    joueur = JoueurPhotographe()
    ecran = previz(jouer=joueur)
    joueur.ecran = ecran
    choisis = []
    ecran._choisir = choisis.append

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("enter")
        await pilote.pause()
        apres_le_premier = list(choisis)
        ecran.traiter("enter")
        await pilote.pause()
        return apres_le_premier, list(choisis)

    apres_le_premier, apres_le_second = banc(coque(ecran), scenario)
    assert apres_le_premier == [], (
        "le premier `⏎` a choisi au lieu d'ouvrir : l'ecran d'instructions "
        "est saute")
    assert len(joueur.appels) == 1
    assert apres_le_second == [ecran.resultat]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_titre_est_au_FUTUR_avant_et_au_PASSE_apres(ascii_seul):
    """Les deux temps, et **aucun des deux ne dit ce que l'autre dit**.

    Une assertion positive seule (« le titre d'attente parle de fenetre »)
    laisserait passer un titre d'attente qui annoncerait encore au passe.
    L'ensemble des titres qui divergent est donc mesure **exactement**.
    """
    ecran = previz(jouer=lambda _s: resultat())
    ecran.demarrer()
    avant = "\n".join(ecran.composer(80, ascii_seul)[0])
    ecran.traiter("enter")
    apres = "\n".join(ecran.composer(80, ascii_seul)[0])

    attendu_avant = jetons.replier_ascii(amont.TITRE_PREVIZ_AVANT) \
        if ascii_seul else amont.TITRE_PREVIZ_AVANT
    attendu_apres = jetons.replier_ascii(amont.TITRE_PREVIZ) \
        if ascii_seul else amont.TITRE_PREVIZ
    assert attendu_avant in avant and attendu_apres not in avant
    assert attendu_apres in apres and attendu_avant not in apres

    # **L'ecran d'attente ne CADRE pas un rapport vide.** Le titre seul ne
    # suffit pas a le mesurer : un filet « Rapport, au fil de la lecture »
    # pose sur zero ligne, et ses trois en-tetes de colonnes, annoncent une
    # mesure qui n'a pas commence -- et l'ecran promettrait au futur tout en
    # montrant le decor du passe. Les quatre marqueurs sont mesures ensemble,
    # avant ET apres : une assertion positive seule laisserait passer un
    # rapport a moitie cadre.
    marqueurs = (amont.FILET_RAPPORT, amont.ENTETE_DE_LA_CADENCE,
                 amont.ENTETE_DES_RETENUES, amont.ENTETE_DES_PRESENTEES)
    for marqueur in marqueurs:
        attendu = jetons.replier_ascii(marqueur) if ascii_seul else marqueur
        assert attendu not in avant, (
            f"{marqueur!r} est cadre avant toute lecture : l'ecran d'attente "
            "montre le decor d'une mesure qui n'a pas commence")
        assert attendu in apres, marqueur
    # Les deux regimes tiennent la grille, et le repli PEUT allonger.
    for rendu in (avant, apres):
        for ligne in rendu.split("\n"):
            assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
            if ascii_seul:
                assert ligne.isascii(), ligne


def test_les_deux_titres_ne_sont_pas_LA_MEME_promesse():
    """Le futur promet, le passe constate : un grep croise rend ZERO."""
    assert VERBE_DU_FUTUR in amont.TITRE_PREVIZ_AVANT
    assert VERBE_DESSINE_DU_PASSE not in amont.TITRE_PREVIZ_AVANT
    assert VERBE_DESSINE_DU_PASSE in amont.TITRE_PREVIZ
    assert VERBE_DU_FUTUR not in amont.TITRE_PREVIZ


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_de_raccourcis_INVITE_a_ouvrir_avant_de_proposer_de_choisir(
        ascii_seul):
    """`⏎` nomme sa DESTINATION, et elle change entre les deux temps.

    Egan : « cet ecran invite a taper `⏎` une premiere fois pour ouvrir la
    previz ». L'invitation vit dans la ligne de raccourcis -- c'est la ligne
    faite pour porter des touches, et `EPIC11-ARB-56` interdit de la mettre
    dans la ligne d'etat.
    """
    ecran = previz(jouer=lambda _s: resultat())
    ecran.demarrer()
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ_AVANT
    ecran.traiter("enter")
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ
    for ligne in (amont.RACCOURCIS_PREVIZ_AVANT, amont.RACCOURCIS_PREVIZ):
        rendu = jetons.replier_ascii(ligne) if ascii_seul else ligne
        assert jetons.colonnes(rendu) <= jetons.largeur_utile(80), rendu
        if ascii_seul:
            assert rendu.isascii(), rendu


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_etat_de_L_ATTENTE_ne_porte_NI_touche_NI_conseil(
        ascii_seul):
    """`EPIC11-ARB-56`, recopie verbatim face au test.

    > « une remarque generale pour TOUS tes ecrans : tu es trop bavard dans les
    > bandeaux en bas. Contente toi de mettre les raccourcis et les infos
    > pertinentes mais pas une remarque d'aide ou, pire, de methode, a chaque
    > fois. [...] Sois sobre. »

    La regle verifiable qui en decoule : la ligne d'etat porte une **mesure de
    l'ecran courant**, et « aucune touche -- une touche va a la ligne des
    raccourcis », « aucun conseil d'usage », « aucun motif de conception ».
    L'ecran d'attente est le plus expose des trois etats de `E2-2b` : c'est
    celui ou l'on aurait envie d'ecrire « tapez Entree pour ouvrir ».
    """
    ecran = previz(jouer=lambda _s: resultat())
    ecran.demarrer()
    etat = ecran.ligne_d_etat(ascii_seul)

    attendu = amont.phrase_a_lire(3)
    if ascii_seul:
        attendu = jetons.replier_ascii(attendu)
    assert etat == attendu, (etat, attendu)
    for touche in ("⏎", "Entree", "Entrée", "Échap", "Echap", "F1", "Tab"):
        assert touche not in etat, (touche, etat)
    for conseil in ("tapez", "appuyez", "pour ouvrir", "vous pouvez"):
        assert conseil not in etat.lower(), (conseil, etat)


def test_la_mesure_de_l_attente_COMPTE_ce_qui_va_etre_lu():
    """Une mesure, et elle bouge avec ce qu'on lui donne.

    Deux cardinaux distinguables : une phrase figee passerait une mesure a un
    seul appel, comme une fabrique a un seul element passe un appariement
    inverse.
    """
    trois = previz(jouer=lambda _s: resultat())
    trois.demarrer()
    assert trois.ligne_d_etat(False) == "3 cadences à lire"

    une = previz(regardees=regardees()[1:2], jouer=lambda _s: resultat())
    une.demarrer()
    assert une.ligne_d_etat(False) == "1 cadence à lire"


def test_le_REFUS_D_AFFICHAGE_ferme_AUSSI_le_chemin_de_la_touche():
    """Sans affichage, ni le montage ni `⏎` n'ouvrent quoi que ce soit.

    AC 5.2 : « Un refus qui arrive apres coup vaut un plantage. » Le correctif
    `K1.2` deplace le lancement du montage vers la touche ; sans ce volet, il
    rouvrirait le trou que l'AC avait ferme.
    """
    joueur = JoueurPhotographe()

    def refuser():
        cadence_previz.ensure_display_available(environ={}, platform="linux")

    ecran = previz(jouer=joueur, verifier_l_affichage=refuser)
    joueur.ecran = ecran
    ecran.demarrer()
    assert ecran.refus
    assert ecran.raccourcis == amont.RACCOURCIS_PREVIZ_REFUSEE
    ecran.traiter("enter")
    assert joueur.appels == []
    assert ecran.resultat is None


def test_le_DIFFERE_est_celui_du_depot_et_PAS_une_seconde_redaction():
    """`_lancer_apres_le_dessin` est **importe**, jamais recopie.

    Deux redactions du meme rendez-vous divergeraient a la premiere retouche,
    et c'est ce rendez-vous qui porte la lecon : « `app.descendre(ecran)`
    empile l'ecran, mais son `on_mount` n'a pas encore tourne a l'instruction
    suivante ». La mesure est structurelle parce que la panne l'est.
    """
    source = inspect.getsource(amont.EcranPreviz._ouvrir_la_fenetre)
    import textwrap
    arbre = ast.parse(textwrap.dedent(source))
    importes = {alias.name
                for noeud in ast.walk(arbre)
                if isinstance(noeud, ast.ImportFrom)
                and noeud.module == "atelier_extraction_ecriture"
                for alias in noeud.names}
    assert "_lancer_apres_le_dessin" in importes, importes
    appels = [n.func.id for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "_lancer_apres_le_dessin" in appels, appels

    # ... et `demarrer` ne joue plus rien : la frontiere negative du meme
    # correctif, prise sur le CODE et non sur un compte d'appels.
    montage = inspect.getsource(amont.EcranPreviz.demarrer)
    assert "_jouer" not in montage, (
        "la lecture est repartie dans le montage : c'est le defaut K1.2 "
        "d'origine, et il ne se voit qu'a l'ecran")


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc ouvre sa docstring de module
# sur « il annoncait au passe (« une fenetre s'est ouverte ») ce qui venait
# de se produire » et n'ouvrait pas `E2-2b`. Le passe qu'il oppose au futur
# est justement celui que le dessin porte : c'est la moitie de l'argument.

#: Le verbe que `E2-2b` dessine (l. 5), et son symetrique qui n'est dessine
#: NULLE PART -- l'ecran d'avant-ouverture n'a pas de maquette. La
#: confrontation ci-dessous mesure les deux faits.
VERBE_DESSINE_DU_PASSE = "s'est ouverte"
VERBE_DU_FUTUR = "va s'ouvrir"

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


def test_le_TITRE_AU_PASSE_est_dessine_par_E2_2b_a_la_LETTRE():
    """Le titre entier, pas seulement son verbe : c'est la mesure forte.

    Confronter `s'est ouverte` seul serait vrai de n'importe quelle phrase
    qui le contient. C'est `TITRE_PREVIZ` en entier que le dessin porte, et
    c'est cette egalite-la qui rend le fragment interessant.
    """
    dessin = dessin_de_la_maquette("E2-2b-extraction-previz.txt")
    assert amont.TITRE_PREVIZ in dessin
    assert VERBE_DESSINE_DU_PASSE in amont.TITRE_PREVIZ


def test_le_TITRE_AU_FUTUR_n_est_dessine_NULLE_PART_et_c_est_dit():
    """L'ecran d'avant-ouverture n'a pas de maquette -- dit plutot que tu.

    `TITRE_PREVIZ_AVANT` est du texte produit, jamais approuve en dessin :
    `E2-2b` ne montre que l'apres. Le volet symetrique n'est donc pas une
    seconde confrontation mais une ABSENCE mesuree, et c'est ce qui empeche
    une relecture de chercher un dessin qui n'existe pas.

    L'absence est mesuree sur TOUS les dessins du dossier et non sur le seul
    `E2-2b` : « pas dans celui-ci » ne dit rien de « pas approuve ».
    """
    for chemin in sorted(MAQUETTES.glob("*.txt")):
        assert VERBE_DU_FUTUR not in dessin_de_la_maquette(chemin.name), chemin.name

    # Le temoin de morsure : le verbe du passe, lui, EST trouve par le meme
    # balayage. Sans lui, un balayage casse rendrait l'absence gratuite.
    trouves = [chemin.name for chemin in sorted(MAQUETTES.glob("*.txt"))
               if VERBE_DESSINE_DU_PASSE in dessin_de_la_maquette(chemin.name)]
    assert "E2-2b-extraction-previz.txt" in trouves


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    dessin = dessin_de_la_maquette("E2-2b-extraction-previz.txt")
    assert amont.TITRE_PREVIZ_AVANT not in dessin
    assert amont.TITRE_PREVIZ_REFUSEE not in dessin
