# -*- coding: utf-8 -*-
"""Story 11.4 -- le PARCOURS de l'atelier Extraction, de « quel rush » a « ecrit ».

Les deux moities existaient et ne se touchaient pas : `atelier_extraction.py`
porte les ecrans amont (`E2-1`, `E2-2`, `E2-2b`, `E2-2c`),
`atelier_extraction_ecriture.py` porte le jugement, l'execution et le resultat
(`E2-3`, `E2-4`, `E2-5`). Ce banc mesure le **raccord** : ce qui passe d'un
ecran a l'autre, et ce qui ne passe surtout pas.

**Le parcours est joue AU CLAVIER, ecran par ecran**, et jamais en appelant les
rappels a la main : c'est precisement une chaine assemblee a la main dans une
demo qui a masque pendant deux vagues que le produit n'ouvrait que des paliers
temoins (lot `E9`). Un banc qui appellerait `confirmer(lots)` lui-meme
reproduirait ce mode de panne.

**Regle des fabriques** (`CLAUDE.md`) : les cadences cochees sont les rangs 1 et
2 -- jamais la premiere --, leurs comptes different (62 et 42), le rush vise
est le **deuxieme** du manifeste, et deux lots sont produits a chaque ecriture.
Un appariement positionnel entre « cadence cochee » et « lot produit » ne se
verrait, sinon, que sur les TIFF.
"""
import json
import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest
from textual.widgets import Static

from mixed_media_utility import (
    cadence_previz,
    extraction,
    frame_selection,
    progression,
    source_confirmation,
    video_metadata,
)
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import MANIFEST_FILENAME
from mixed_media_utility.io.naming import build_lot_id
from mixed_media_utility.tui import atelier_extraction as amont
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui import rushes as modele_des_rushes
from mixed_media_utility.tui.coque import EcranPasEncore
from mixed_media_utility.tui.execution import (
    EcranExecution,
    EcranResultat,
    PanneauConfirmation,
)

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: La source du banc : 25 im/s, 124 frames, 1920x1080. Les quatre cadences
#: remarquables en tirent 124, 62, 42 et 31 -- QUATRE comptes distincts.
FPS_SOURCE = Fraction(25)
FRAMES_SOURCE = 124
LARGEUR, HAUTEUR = 1920, 1080

#: Les deux cadences cochees, **aux rangs 1 et 2** de la liste remarquable :
#: jamais la premiere, et leurs comptes different.
RANGS_COCHES = (1, 2)
VALEURS_COCHEES = (Fraction(25, 2), Fraction(25, 3))

#: Le rush vise est le **deuxieme** du manifeste. Un `find` fautif qui rendrait
#: toujours la premiere entree ne se demasque pas autrement.
RUSH_LEURRE = "rush_00_leurre"
RUSH_VISE = "rush_01"


class JournalMuet:
    """Un logger minimal : le coeur en exige un, on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def probe_de_la_source(largeur: int = LARGEUR, hauteur: int = HAUTEUR) -> dict:
    """Une sortie ffprobe **complete**, telle que `probe_media` la rend.

    `nb_frames` et `duration` se recoupent a la frame pres : c'est la condition
    qui fait rendre `resolve_source_frame_count` sans payer de comptage exact,
    donc sans autre acces au binaire que celui du sondage lui-meme.
    """
    return {
        "streams": [
            {"codec_type": "audio", "codec_name": "pcm_s16le"},
            {"codec_type": "video", "codec_name": "prores",
             "r_frame_rate": f"{FPS_SOURCE.numerator}/{FPS_SOURCE.denominator}",
             "avg_frame_rate": f"{FPS_SOURCE.numerator}/{FPS_SOURCE.denominator}",
             "nb_frames": str(FRAMES_SOURCE),
             "duration": str(FRAMES_SOURCE / float(FPS_SOURCE)),
             "width": largeur, "height": hauteur,
             "tags": {"timecode": "01:00:00:00"}},
        ],
        "format": {"duration": str(FRAMES_SOURCE / float(FPS_SOURCE))},
    }


class SondeComptee:
    """Un double de `video_metadata.probe_media` qui COMPTE ses appels.

    C'est la seule facon de mesurer « le probe est paye une seule fois » : le
    compte, et non la forme du code. Un `prepare_previz` appele sans son
    argument `probe` reprobe -- silencieusement, et sans autre symptome qu'une
    attente de plus sur un rush long.
    """

    def __init__(self, probe: dict | None = None) -> None:
        self.appels: list[str] = []
        self._probe = probe_de_la_source() if probe is None else probe

    def __call__(self, chemin, **kwargs) -> dict:
        self.appels.append(str(chemin))
        return dict(self._probe)


@pytest.fixture
def sonde(monkeypatch) -> SondeComptee:
    """Le probe du coeur, remplace par un double COMPTE, partout a la fois.

    Le remplacement porte sur l'attribut de module `video_metadata.probe_media`
    et non sur un import local : `extraction`, `cadence_previz` et la TUI le
    lisent tous les trois par ce chemin, donc un seul remplacement les couvre
    -- et une seconde porte de sondage se verrait au compte.
    """
    double = SondeComptee()
    monkeypatch.setattr(video_metadata, "probe_media", double)
    return double


def rush_sur_le_disque(tmp_path) -> Path:
    """Le fichier source. Il doit EXISTER : `prepare_previz` le verifie."""
    chemin = tmp_path / f"{RUSH_VISE}.mov"
    chemin.write_bytes(b"pas une vraie video, le probe est double")
    return chemin


def projet(tmp_path, video: Path | None = None, lie: bool = True) -> Path:
    """Un projet reel, dont le rush vise est en DEUXIEME position.

    Le leurre porte un `source_path` different et existant : un appariement par
    position rendrait son chemin, et le sondage porterait alors sur le mauvais
    fichier -- c'est le mutant `M25` de la story 5.7, transpose ici.
    """
    dossier = creer_projet(tmp_path, "projet_demo").chemin
    leurre = tmp_path / f"{RUSH_LEURRE}.mov"
    leurre.write_bytes(b"le leurre")
    entree_visee = {"rush_id": RUSH_VISE}
    if lie and video is not None:
        entree_visee["source_path"] = str(video)
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    document["rushes"] = [
        {"rush_id": RUSH_LEURRE, "source_path": str(leurre)},
        entree_visee,
    ]
    (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                             encoding="utf-8")
    return dossier


def compte_du_coeur(valeur: Fraction) -> int:
    """Le cardinal que `select_source_frames` rend, calcule A PART du module."""
    return frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=valeur,
        source_frame_count=FRAMES_SOURCE,
        source_start_timecode="01:00:00:00").expected_frame_count


def issue_reussie(dossier_projet: Path, lot_id: str, fps_target: float,
                  frames: int, fichiers: int = 2):
    """Un `ExtractionOutcome` reussi, avec un dossier de lot reellement peuple.

    Le dossier est celui que le coeur choisirait (`project_layout.extract_frames_dir`),
    et les fichiers ont des tailles DIFFERENTES : un poids mesure par somme se
    distingue ainsi d'un compte multiplie.
    """
    from mixed_media_utility.io.project_layout import extract_frames_dir

    dossier = extract_frames_dir(Path(dossier_projet), RUSH_VISE, fps_target)
    dossier.mkdir(parents=True, exist_ok=True)
    for rang in range(fichiers):
        (dossier / f"{rang:04d}.tiff").write_bytes(b"x" * (10 + rang))
    return extraction.ExtractionOutcome(
        granted=True, message=f"{frames} frame(s)", lot_id=lot_id,
        frames_dir=dossier, written_frame_count=frames)


class ExtracteurCompte:
    """Un double de `run_extraction` qui enregistre CE QUE LE COEUR A RECU.

    **Il emet ses jalons par le VRAI emetteur du coeur**, construit comme
    `ffmpeg_utils` le construit : `EmetteurProgression(rappel_progression,
    total)`. C'est ce qui rend la mesure honnete -- un rappel non appelable y
    est absorbe en silence (`_rappel = ... if callable(...) else None`, l'emetteur
    se declare inactif et ne leve rien), exactement comme dans le coeur. Un
    double qui appellerait `rappel(faites, total)` a la main leverait, et
    transformerait une extinction silencieuse en erreur bruyante -- c'est-a-dire
    mesurerait le contraire du defaut cherche.
    """

    def __init__(self, dossier_projet: Path) -> None:
        self.dossier = Path(dossier_projet)
        self.appels: list[dict] = []
        self.jalons: list[int] = []
        self.taches_en_cours: list[bool] = []
        self.app = None

    def __call__(self, **kwargs):
        self.appels.append(kwargs)
        if self.app is not None:
            self.taches_en_cours.append(bool(self.app.tache_en_cours))
        cible = kwargs["fps_target"]
        frames = self.frames_attendues(cible)
        emetteur = progression.EmetteurProgression(
            kwargs.get("rappel_progression"), frames)
        for faites in (frames // 2, frames):
            self.jalons.append(faites)
            emetteur.emettre(faites)
        return issue_reussie(self.dossier, build_lot_id(RUSH_VISE, cible),
                             cible, frames)

    @staticmethod
    def frames_attendues(fps_target: float) -> int:
        for valeur in VALEURS_COCHEES:
            if abs(float(valeur) - fps_target) < 1e-9:
                return compte_du_coeur(valeur)
        raise AssertionError(f"cadence inattendue au coeur : {fps_target!r}")


def rapport_de_previz(valeur: Fraction):
    """Un `PlaybackReport` du VRAI producteur, jamais un double."""
    attendues = compte_du_coeur(valeur)
    pas = 1.0 / float(valeur)
    observations = [
        cadence_previz.FrameObservation(
            output_rank=rang + 1, source_index=rang, t_theo_s=rang * pas,
            t_real_s=rang * pas)
        for rang in range(attendues)]
    return cadence_previz.build_playback_report(
        observations, fps_target=float(valeur), frames_attendues=attendues,
        duree_nominale_s=max(attendues - 1, 0) * pas, frames_omises=0,
        partiel=False)


class JoueurCompte:
    """Un double de `play_cadences`. Il rend un resultat sur LA session recue.

    Les rapports sont produits pour les cadences EXACTES correspondantes, et
    non pour les flottants de la session : c'est `rapport_de_la_cadence` qui
    apparie ensuite, et l'apparier sur un arrondi ferait disparaitre `25/3` de
    `E2-2c` sans que rien ne le dise.
    """

    def __init__(self) -> None:
        self.appels: list = []

    def __call__(self, session, **kwargs):
        self.appels.append(session)
        exactes = [_exacte(cible) for cible in session.fps_targets]
        return cadence_previz.PrevizResult(
            session=session,
            reports=tuple(rapport_de_previz(valeur) for valeur in exactes),
            interrupted=False, decoded_frames=0, cache_hits=0, cache_misses=0)


def _exacte(cible: float) -> Fraction:
    """Retrouver la `Fraction` exacte d'une cadence rendue en flottant."""
    for valeur in (FPS_SOURCE / diviseur for diviseur in (1, 2, 3, 4)):
        if abs(float(valeur) - cible) < 1e-9:
            return valeur
    raise AssertionError(f"cadence inattendue dans la session : {cible!r}")


def chaine(tmp_path, *, lie: bool = True, extracteur=None, joueur=None,
           affichage=None, **kwargs):
    """La chaine reelle, posee sur un projet reel, avec le parcours REEL cable.

    Les doubles n'entrent que par les portes que le parcours expose : ils ne
    remplacent aucun ecran, aucun modele et aucun enchainement.
    """
    video = rush_sur_le_disque(tmp_path)
    dossier = projet(tmp_path, video, lie=lie)
    extracteur = ExtracteurCompte(dossier) if extracteur is None else extracteur
    joueur = JoueurCompte() if joueur is None else joueur

    def rappel(app, dossier_du_menu, rush_id):
        return atelier.ouvrir_les_cadences(
            app, dossier_du_menu, rush_id,
            jouer=joueur, extraire=extracteur, logger=JournalMuet(),
            verifier_l_affichage=affichage or (lambda: None), **kwargs)

    lien = atelier.ChaineReelle(ouvrir_les_cadences=rappel)
    lien.menu.dossier = lien.palier_projet.dossier = dossier
    lien.menu.charger()
    lien.extracteur = extracteur
    lien.joueur = joueur
    lien.video = video
    if isinstance(extracteur, ExtracteurCompte):
        extracteur.app = lien.app
    return lien


async def jusqu_aux_cadences(pilote, lien):
    """Descendre au menu, entrer dans l'atelier, choisir le rush VISE."""
    pilote.app.descendre()
    await pilote.pause()
    lien.menu.traiter("enter")               # Extraction, en tete de liste
    await pilote.pause()
    ecran = pilote.app.screen
    ecran.liste.viser(RUSH_VISE)
    ecran.traiter("enter")
    await pilote.pause()
    return pilote.app.screen


def cocher_les_deux(ecran) -> None:
    """Cocher les rangs 1 et 2 -- jamais le rang 0."""
    for rang in RANGS_COCHES:
        ecran.liste.curseur = rang
        ecran.liste.basculer()


async def franchir_la_previz(pilote):
    """`E2-2b` demande DEUX `⏎` depuis `K1.2` : ouvrir, puis choisir.

    La fenetre ne s'ouvre plus au montage -- l'ecran d'instructions se peint
    d'abord, au futur, et invite a `⏎`. Un banc qui n'en taperait qu'un
    resterait sur `E2-2b` : le second `⏎` n'a rien a choisir tant que rien
    n'a ete lu, et c'est cet ordre-la que le correctif pose.
    """
    previz = pilote.app.screen
    previz.traiter("enter")                  # `⏎` 1 : ouvrir la fenetre
    await pilote.pause()
    previz.traiter("enter")                  # `⏎` 2 : choisir quoi extraire
    await pilote.pause()
    return pilote.app.screen


async def jusqu_au_panneau(pilote, lien, *, par_la_previz: bool):
    """Le parcours complet jusqu'au point de jugement, par l'un des deux temps."""
    cadences = await jusqu_aux_cadences(pilote, lien)
    cocher_les_deux(cadences)
    if not par_la_previz:
        cadences.traiter(None, "x")
        await pilote.pause()
        return pilote.app.screen
    cadences.traiter("enter")
    await pilote.pause()
    choix = await franchir_la_previz(pilote)
    for rang in range(len(choix.liste.cadences)):
        choix.liste.curseur = rang
        choix.liste.basculer()
    choix.traiter("enter")
    await pilote.pause()
    return pilote.app.screen


async def ecrire(pilote, panneau):
    """Viser l'issue qui ecrit, valider, laisser l'ecran d'execution se monter."""
    panneau.choix.viser(atelier.ISSUE_EXTRAIRE)
    panneau.traiter("enter")
    await pilote.pause()
    await pilote.pause()
    return pilote.app.screen


# ===========================================================================
# Etape 1 -- le rush choisi : un sondage, et un seul
# ===========================================================================

def test_choisir_un_rush_OUVRE_les_cadences_du_rush_VISE(tmp_path, banc, sonde):
    """Etape 1. Le rush vise est le DEUXIEME du manifeste, et c'est SON
    fichier qui est sonde -- pas celui du leurre en premiere position."""
    lien = chaine(tmp_path)

    def scenario(pilote):
        return jusqu_aux_cadences(pilote, lien)

    ecran = banc(lien.app, scenario)
    assert isinstance(ecran, amont.EcranCadences)
    assert sonde.appels == [str(lien.video)], sonde.appels
    assert ecran.source.fps_source == FPS_SOURCE
    assert ecran.source.source_frame_count == FRAMES_SOURCE


def test_les_COMPTES_de_E2_2_viennent_du_coeur_sur_la_source_sondee(
        tmp_path, banc, sonde):
    """AC 3.2 / `EPIC11-ARB-79` : le compte vient de `select_source_frames`,
    appele avec la `Fraction` EXACTE et le cardinal deja sonde -- jamais d'un
    produit duree x cadence, jamais par `prepare_previz`."""
    lien = chaine(tmp_path)
    ecran = banc(lien.app, lambda pilote: jusqu_aux_cadences(pilote, lien))
    comptes = [cadence.compte for cadence in ecran.liste.cadences]
    assert comptes == [compte_du_coeur(FPS_SOURCE / d) for d in (1, 2, 3, 4)]
    assert len(set(comptes)) == len(comptes), "quatre comptes DISTINCTS"


def test_le_SONDAGE_passe_par_la_frontiere_executer_en_processus(
        tmp_path, banc, sonde):
    """`EPIC11-ARB-1` : le coeur est heberge, pas relance -- et le sondage est
    long. Il ne tourne donc jamais dans la boucle d'evenements sans passer par
    la frontiere qui NOMME l'appel du coeur."""
    lien = chaine(tmp_path)
    passages = []
    vrai = lien.app.executer_en_processus

    def espion(fonction, *args, **kwargs):
        passages.append(getattr(fonction, "__name__", type(fonction).__name__))
        return vrai(fonction, *args, **kwargs)

    lien.app.executer_en_processus = espion
    banc(lien.app, lambda pilote: jusqu_aux_cadences(pilote, lien))
    assert atelier.sonder_la_source.__name__ in passages, passages


def test_E2_1_n_offre_PAS_d_extraire_un_rush_delinke(tmp_path, banc, sonde):
    """AC 2.4 : « le choisir n'extrait rien » -- il ouvre le relink. C'est la
    premiere des deux gardes, et celle que l'operateur rencontre."""
    lien = chaine(tmp_path, lie=False)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        lien.menu.traiter("enter")
        await pilote.pause()
        rushes = pilote.app.screen
        rushes.liste.viser(RUSH_VISE)
        return rushes.liste.action_du_choix()

    assert banc(lien.app, scenario) == modele_des_rushes.ACTION_RELINK
    assert sonde.appels == [], "aucun sondage sur un rush delinke"


def test_un_rush_DELINKE_est_refuse_PAR_LE_CODE_du_coeur(tmp_path, banc, sonde):
    """La seconde garde, **defensive**, et elle a une raison d'exister : entre
    la lecture du manifeste qui a dessine `E2-1` et la frappe qui choisit, le
    fichier peut avoir disparu -- un volume reseau demonte suffit.

    Le refus porte alors le **code du coeur**, jamais une phrase inventee, et
    l'ecran est celui du refus de relink : ses trois suites menent a la
    reparation. Un ecran « pas encore » serait faux -- rien ne manque au
    produit, c'est le fichier qui manque.
    """
    lien = chaine(tmp_path, lie=False)

    async def scenario(pilote):
        lien.extraire(RUSH_VISE)
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(lien.app, scenario)
    assert isinstance(ecran, amont.EcranRefusRelink)
    assert ecran.refus.code in modele_des_rushes.CODES_DE_REFUS_DU_COEUR
    assert RUSH_VISE in ecran.refus.message
    assert sonde.appels == [], "aucun sondage sur un rush delinke"


# ===========================================================================
# Etape 2 -- previsualiser : le probe est REPASSE, jamais repaye
# ===========================================================================

def test_le_PROBE_est_paye_UNE_SEULE_FOIS_sur_tout_le_parcours(
        tmp_path, banc, sonde):
    """`EPIC11-ARB-79` : « Le probe reste paye **une seule fois** : c'est son
    resultat qu'on repasse. » La mesure est un COMPTE, pas une relecture."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(lien.app, scenario)
    assert isinstance(ecran, amont.EcranPreviz)
    assert sonde.appels == [str(lien.video)], sonde.appels


def test_previsualiser_MONTE_E2_2b_sur_les_seules_cadences_cochees(
        tmp_path, banc, sonde):
    """Etape 2. La session est preparee sur les cochees, et sur elles seules."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        previz = pilote.app.screen
        # **Le joueur n'est PAS appele au montage** (`K1.2`) : la mesure qui
        # suit porte sur ce que `⏎` ouvre, et sur rien d'autre.
        assert lien.joueur.appels == []
        previz.traiter("enter")
        await pilote.pause()
        return previz

    ecran = banc(lien.app, scenario)
    assert [c.valeur for c in ecran.regardees] == list(VALEURS_COCHEES)
    assert lien.joueur.appels == [ecran.session]
    assert tuple(ecran.session.fps_targets) == tuple(
        float(valeur) for valeur in VALEURS_COCHEES)


# ===========================================================================
# Etape 3 -- `x` va DROIT au point de jugement
# ===========================================================================

def test_la_touche_x_va_DROIT_au_point_de_jugement_sans_previz(
        tmp_path, banc, sonde):
    """AC 5.1 : « `x` extrait sans previz ». Aucun ecran de lecture comparee
    n'est monte, et le joueur n'est jamais appele."""
    lien = chaine(tmp_path)

    def scenario(pilote):
        return jusqu_au_panneau(pilote, lien, par_la_previz=False)

    ecran = banc(lien.app, scenario)
    assert isinstance(ecran, PanneauConfirmation)
    assert lien.joueur.appels == []
    assert lien.extracteur.appels == [], "rien n'est ecrit au jugement"


# ===========================================================================
# Etape 4 et 5 -- le temps 2, et le consentement qu'il N'HERITE PAS
# ===========================================================================

def test_le_temps_2_REPASSE_par_le_panneau_de_confirmation(
        tmp_path, banc, sonde):
    """`EPIC11-ARB-24`, verbatim : « une previz n'autorise rien » -- « elle ne
    cree ni lot, ni entree de manifest, ni consentement reutilisable », et « Le
    temps 2 repasse donc par le panneau de confirmation ; il ne herite d'aucun
    consentement du temps 1. »"""
    lien = chaine(tmp_path)

    def scenario(pilote):
        return jusqu_au_panneau(pilote, lien, par_la_previz=True)

    ecran = banc(lien.app, scenario)
    assert isinstance(ecran, PanneauConfirmation)
    assert lien.extracteur.appels == []
    assert ecran.choix.retenue is None, "aucune issue n'est preretenue"


def test_le_temps_2_arrive_ENTIEREMENT_DECOCHE(tmp_path, banc, sonde):
    """AC 5.5, volet symetrique : quoi qu'on ait coche au temps 1, `E2-2c`
    n'herite d'aucune case."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        return await franchir_la_previz(pilote)

    choix = banc(lien.app, scenario)
    assert isinstance(choix, amont.EcranChoixDesCadences)
    assert [c.cochee for c in choix.liste.cadences] == [False, False]
    assert choix.lots() == ()


def test_les_NOMS_montres_au_temps_2_sont_ceux_que_le_PLAN_ecrira(
        tmp_path, banc, sonde):
    """`EPIC11-ARB-46` : « l'apercu ne peut jamais mentir. » Le nom vient de
    `build_lot_id` des deux cotes ; deux redactions divergeraient."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        choix = await franchir_la_previz(pilote)
        for rang in range(len(choix.liste.cadences)):
            choix.liste.curseur = rang
            choix.liste.basculer()
        montres = [lot.nom for lot in choix.lots()]
        choix.traiter("enter")
        await pilote.pause()
        return montres, pilote.app.screen

    montres, panneau = banc(lien.app, scenario)
    attendus = [build_lot_id(RUSH_VISE, float(valeur))
                for valeur in VALEURS_COCHEES]
    assert montres == attendus
    # **Les noms ne sont plus un modele d'edition mais du texte de cartouche**
    # (`EPIC11-ARB-141`, story 11.4e lot G) : ils se lisent sur `Panneau.noms`
    # et non sur `ecran.noms.valeurs`, qui est desormais vide par construction.
    # La mesure ne bouge pas -- c'est toujours l'apercu confronte a ce que le
    # plan ecrira --, seul l'endroit ou le nom vit a change.
    assert panneau.panneau.noms == [
        atelier.INDENT_DES_NOMS + attendu for attendu in attendus]
    assert list(panneau.noms.valeurs) == [], (
        "aucun nom n'est editable : le modele de l'ecran doit rester VIDE")


# ===========================================================================
# L'APPARIEMENT cadence -> lot, qui ne se verrait sinon que sur les TIFF
# ===========================================================================

@pytest.mark.parametrize("par_la_previz", [
    pytest.param(True, id="temps-2"), pytest.param(False, id="touche-x")])
def test_chaque_LOT_du_plan_porte_la_cadence_ET_le_compte_de_SA_cadence(
        tmp_path, banc, sonde, par_la_previz):
    """Les deux comptes DIFFERENT (62 et 42) et les rangs cochés ne sont pas
    les premiers : un appariement decale d'un rang inverserait les deux."""
    lien = chaine(tmp_path)

    def scenario(pilote):
        return jusqu_au_panneau(pilote, lien, par_la_previz=par_la_previz)

    panneau = banc(lien.app, scenario)
    # Le panneau est monte sur le plan ; on relit le plan par ses noms et ses
    # chiffres, qui sont ce que l'operateur voit.
    lignes = "\n".join(panneau.panneau.rendu(80))
    attendu = " + ".join(str(compte_du_coeur(v)) for v in VALEURS_COCHEES)
    assert attendu in lignes, lignes
    # Les noms sont dans le PANNEAU depuis `EPIC11-ARB-141`, plus dans un
    # modele d'edition. L'appariement mesure est le meme -- quel lot porte quel
    # nom -- et il se lit maintenant sur ce que le cartouche rend.
    assert panneau.panneau.noms == [
        atelier.INDENT_DES_NOMS + build_lot_id(RUSH_VISE, float(valeur))
        for valeur in VALEURS_COCHEES]


def test_le_COEUR_recoit_chaque_cadence_avec_SON_lot(tmp_path, banc, sonde):
    """Volet d'ecriture du meme appariement : `run_extraction` est appele une
    fois par cadence cochee, dans l'ordre du plan, et chaque appel porte la
    cadence de son lot."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        return await ecrire(pilote, panneau)

    banc(lien.app, scenario)
    recues = [appel["fps_target"] for appel in lien.extracteur.appels]
    assert recues == [float(valeur) for valeur in VALEURS_COCHEES]
    assert [appel["video_path"] for appel in lien.extracteur.appels] == [
        lien.video, lien.video]


# ===========================================================================
# Le MAJORANT d'espace disque : celui du coeur, jamais une seconde formule
# ===========================================================================

def majorant_du_coeur(frames: int) -> int:
    """Le majorant que `source_confirmation` calcule, sur le MEME probe.

    On ne recopie ni les canaux ni la profondeur : on appelle le producteur du
    coeur et on lui demande son chiffre. Une seconde formule cote TUI se
    verrait ici, meme si elle etait juste aujourd'hui.
    """
    selection = frame_selection.select_source_frames(
        fps_source=FPS_SOURCE, fps_target=VALEURS_COCHEES[0],
        source_frame_count=FRAMES_SOURCE, source_start_timecode="01:00:00:00")
    rapport = source_confirmation.build_source_report(
        probe_de_la_source(), fps_target=float(VALEURS_COCHEES[0]),
        selection=selection, batch_dir_relative="x")
    par_frame, reste = divmod(rapport.disk_upper_bound_bytes,
                              selection.expected_frame_count)
    assert reste == 0, "le majorant du coeur est un multiple du poids de frame"
    return par_frame * frames


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_MAJORANT_de_E2_2c_est_celui_du_COEUR(tmp_path, banc, sonde,
                                                 ascii_seul):
    """La maquette `E2-2c` porte « ~ 2,8 Go (majorant) », et `EcranChoixDesCadences`
    ne l'affiche que si on lui DONNE un poids de frame. Il vient de la
    resolution sondee et des constantes du coeur, jamais d'un litteral."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        choix = await franchir_la_previz(pilote)
        for rang in range(len(choix.liste.cadences)):
            choix.liste.curseur = rang
            choix.liste.basculer()
        return choix

    choix = banc(lien.app, scenario)
    frames = sum(compte_du_coeur(valeur) for valeur in VALEURS_COCHEES)
    attendu = atelier.taille_lisible(majorant_du_coeur(frames))
    mesure = choix.mesure(ascii_seul)
    assert attendu is not None
    if ascii_seul:
        from mixed_media_utility.tui import jetons
        attendu = jetons.replier_ascii(attendu)
    assert attendu in mesure, (attendu, mesure)


def test_le_majorant_DISPARAIT_quand_la_resolution_manque(tmp_path, banc,
                                                          monkeypatch):
    """Volet symetrique : une ligne d'espace disque fausse est pire qu'une
    ligne absente. Sans resolution, rien n'est chiffre."""
    sans_resolution = probe_de_la_source()
    flux = sans_resolution["streams"][1]
    flux.pop("width")
    flux.pop("height")
    monkeypatch.setattr(video_metadata, "probe_media",
                        SondeComptee(sans_resolution))
    lien = chaine(tmp_path)

    async def scenario(pilote):
        cadences = await jusqu_aux_cadences(pilote, lien)
        cocher_les_deux(cadences)
        cadences.traiter("enter")
        await pilote.pause()
        choix = await franchir_la_previz(pilote)
        choix.liste.curseur = 0
        choix.liste.basculer()
        return choix.mesure(False)

    mesure = banc(lien.app, scenario)
    from mixed_media_utility.tui.panneau import MENTION_MAJORANT
    assert MENTION_MAJORANT not in mesure, mesure


# ===========================================================================
# L'ecriture : les jalons ARRIVENT, et le retour est celui d'ARB-13
# ===========================================================================

def test_les_JALONS_du_coeur_ATTEIGNENT_l_ecran_d_execution(
        tmp_path, banc, sonde, monkeypatch):
    """`SurfaceExecution.emetteur()` rend un `EmetteurProgression` -- **non
    appelable** -- et `run_extraction` attend un appelable `(faites, total)`.
    Passe tel quel, le canal s'eteint EN SILENCE : `callable()` rend faux et
    l'emetteur du coeur se declare inactif sans rien lever.

    La mesure porte donc sur l'ARRIVEE des jalons a l'ecran, pas sur la forme
    du branchement : c'est le seul symptome qu'une extinction produit.
    """
    recus: list[tuple[int, int]] = []
    vrai = EcranExecution.sur_jalon

    def espion(self, avancement):
        recus.append((avancement.faites, avancement.total))
        return vrai(self, avancement)

    monkeypatch.setattr(EcranExecution, "sur_jalon", espion)
    lien = chaine(tmp_path)

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        return await ecrire(pilote, panneau)

    resultat = banc(lien.app, scenario)
    assert lien.extracteur.jalons, "le double doit avoir emis"
    assert recus, "aucun jalon n'a atteint l'ecran : le canal est eteint"
    # **Un SEUL total, celui de la passe entiere, et un compte qui ne recule
    # jamais** (11.4e, AC 8.1). Ce banc mesurait l'inverse -- un total par lot,
    # les deux differents -- parce que `emetteur()` remettait le compte a zero
    # a chaque lot ; c'est cette remise a zero qui tombe. Les deux cardinaux
    # restent DIFFERENTS, et c'est ce qui fait mordre la somme : deux lots
    # identiques rendraient la meme somme sous une permutation.
    cardinaux = [compte_du_coeur(valeur) for valeur in VALEURS_COCHEES]
    assert {total for _faites, total in recus} == {sum(cardinaux)}, recus
    assert [faites for faites, _t in recus] == sorted(
        faites for faites, _t in recus), recus
    assert isinstance(resultat, EcranResultat)


def test_l_ecran_d_EXECUTION_est_monte_AVANT_l_appel_du_coeur(
        tmp_path, banc, sonde):
    """Son `on_mount` est ce qui l'abonne aux jalons **et** ce qui pose
    `tache_en_cours`. Appeler le coeur dans la foulee de `descendre` ferait
    ecrire les jalons dans une surface que personne n'ecoute, et `Echap`
    depilerait l'ecran d'une tache qui tourne.

    La mesure est prise **dans le coeur lui-meme**, au moment de l'appel : un
    releve pris apres coup ne dirait rien de l'ordre.
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        return await ecrire(pilote, panneau)

    banc(lien.app, scenario)
    assert lien.extracteur.taches_en_cours == [True, True], (
        lien.extracteur.taches_en_cours)


def test_apres_l_ECRITURE_le_retour_mene_au_MENU_DES_ATELIERS(
        tmp_path, banc, sonde):
    """`EPIC11-ARB-13`, verbatim : « La fin d'une execution ramene au **menu des
    ateliers du projet ouvert** [...], jamais a l'ecran projet. »"""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        resultat = await ecrire(pilote, panneau)
        assert isinstance(resultat, EcranResultat), type(resultat).__name__
        resultat.curseur = resultat.suites.index(EcranResultat.RETOUR)
        resultat.choisir()
        await pilote.pause()
        return pilote.app.screen, pilote.app.rang

    ecran, rang = banc(lien.app, scenario)
    assert ecran is lien.menu and rang == lien.app.RANG_DES_ATELIERS


def test_le_RESULTAT_porte_les_DEUX_lots_ecrits_et_leurs_comptes(
        tmp_path, banc, sonde):
    """Deux lots, deux comptes distincts : un resultat qui n'en montrerait
    qu'un, ou qui repeterait le meme compte, se voit ici."""
    lien = chaine(tmp_path)

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        resultat = await ecrire(pilote, panneau)
        return "\n".join(resultat.lignes())

    rendu = banc(lien.app, scenario)
    for valeur in VALEURS_COCHEES:
        assert build_lot_id(RUSH_VISE, float(valeur)) in rendu, rendu
        assert str(compte_du_coeur(valeur)) in rendu, rendu


# ===========================================================================
# Le produit lui-meme : le parcours est cable au POINT D'ENTREE
# ===========================================================================

def test_le_PRODUIT_cable_le_parcours_reel_et_non_l_ecran_PAS_ENCORE(tmp_path):
    """Lot `E9`, meme motif : un composant livre, teste, et cable nulle part
    dans l'application est un composant que le produit n'a pas."""
    app = atelier.construire_l_application()
    menu = app._paliers[1]
    lien = menu._entrer.__self__
    assert lien._ouvrir_les_cadences is atelier.ouvrir_les_cadences


def test_une_CHAINE_SANS_rappel_injecte_nomme_toujours_ce_qui_manque(
        tmp_path, banc):
    """Volet symetrique, et il garde le contrat d'injection : sans rappel, on
    NOMME ce qui manque plutot que de laisser la touche muette."""
    lien = atelier.ChaineReelle()
    lien.menu.dossier = lien.palier_projet.dossier = tmp_path

    async def scenario(pilote):
        lien.extraire(RUSH_VISE)
        await pilote.pause()
        return pilote.app.screen

    assert lien._ouvrir_les_cadences is None
    assert isinstance(banc(lien.app, scenario), EcranPasEncore)


# ===========================================================================
# `J3` -- l'objet du bandeau est CABLE, pas seulement acceptable
# ===========================================================================
#
# **Le mode de panne que ce banc-ci vise**, et c'est le troisieme du depot :
# `execution.py` sait desormais porter un objet, mais un ecran qui accepte un
# objet que personne ne lui donne est un ecran a bandeau nu. C'est exactement
# `E9` (le parcours cable nulle part), `I3` (`bandeau_de_relink` exporte et
# appele nulle part), et ce que le banc de `test_ecrans_execution.py` ne peut
# pas voir : il construit les ecrans lui-meme.
#
# Il faut donc mesurer sur le parcours REEL, celui que `construire_l_application`
# monte.

def objet_attendu_du_rush() -> str:
    """Ce que la maquette porte, **derive du modele et non recopie**.

    Les deux mesures viennent de ce que la sonde a rendu, et leur mise en forme
    de `rushes.bandeau_du_rush`. Recopier `rush_01 · 25 fps · 4:12` en litteral
    ici ferait une seconde redaction du rendu : le banc resterait vert le jour
    ou la fonction changerait de forme, et l'ecran afficherait autre chose que
    ce que la colonne technique de `E2-1` affiche pour le meme rush.
    """
    return modele_des_rushes.bandeau_du_rush(
        RUSH_VISE, float(FPS_SOURCE), FRAMES_SOURCE)


@pytest.mark.parametrize("par_la_previz", [False, True])
def test_le_parcours_DONNE_son_objet_au_point_de_jugement(
        tmp_path, banc, sonde, par_la_previz):
    """`J3` : `E2-3` porte `rush_01 · 25 fps · 4:12`, par les DEUX chemins.

    Les deux temps y menent -- `x` sans previz et `⏎` avec --, et ils passent
    par deux appels distincts de `_juger`. Un seul des deux mesure ne dirait
    rien de l'autre.
    """
    lien = chaine(tmp_path)

    async def scenario(pilote):
        ecran = await jusqu_au_panneau(pilote, lien,
                                       par_la_previz=par_la_previz)
        # **Le bandeau DESSINE, lu sur le widget monte.** Le lire hors du
        # montage passerait a cote du seul endroit ou le defaut vivait : les
        # ecrans savaient deja rendre un objet, personne ne leur en donnait.
        return ecran, jetons.texte_affiche(
            pilote.app.screen.query_one("#bandeau", Static).content)

    ecran, bandeau = banc(lien.app, scenario)
    assert isinstance(ecran, PanneauConfirmation)
    assert ecran.objet == objet_attendu_du_rush(), ecran.objet
    assert bandeau.rstrip().endswith(objet_attendu_du_rush()), bandeau


def test_l_objet_TRAVERSE_l_execution_et_le_resultat(tmp_path, banc, sonde):
    """`E2-4` et `E2-5` portent le MEME objet que `E2-3`.

    C'est le meme rush du debut a la fin du parcours, et les trois maquettes le
    portent identique. `E2-5` le lit sur l'ecran d'execution plutot que de le
    recevoir en argument : l'ecran qui l'a affiche pendant toute la tache le
    porte deja, et un second argument qui dirait la meme chose pourrait dire
    autre chose.
    """
    lien = chaine(tmp_path)
    vus = {}

    async def scenario(pilote):
        panneau = await jusqu_au_panneau(pilote, lien, par_la_previz=False)
        vus["E2-3"] = panneau.objet
        panneau.traiter("up")            # remonter sur `Extraire`
        panneau.traiter("enter")
        await pilote.pause()
        await pilote.pause()
        vus["final"] = pilote.app.screen.objet
        return pilote.app.screen

    final = banc(lien.app, scenario)
    assert isinstance(final, EcranResultat), final
    attendu = objet_attendu_du_rush()
    assert vus["E2-3"] == attendu, vus
    assert vus["final"] == attendu, vus
