"""Story 6.7 -- le chemin d'encodage EMET son avancement.

Ce banc mesure le canal de progression sur les trois sites de
`codec_profiles`, et la traversee des trois signatures qui le portent
jusqu'au point d'entree de coeur.

**Pourquoi les fabriques de ce banc portent TROIS frames et non deux.** La
regle des fabriques de `CLAUDE.md` l'exige des qu'une boucle COMPTE : une
fabrique a deux elements place la cible en seconde ET en derniere position,
ou un `find` fautif et un `break` premature sont indiscernables. La moitie
bon marche de cette story boucle sur les frames, donc c'est ce regime-la qui
s'applique -- trois frames, la divergente AU MILIEU, des formes
DISTINGUABLES et jamais un remplissage uniforme.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from mixed_media_utility import codec_profiles, encode, encode_master, progression


# ===========================================================================
# Fabriques -- trois elements, formes distinguables, cible au MILIEU
# ===========================================================================

#: Trois formes DISTINCTES. Un remplissage uniforme rendrait invisible toute
#: erreur d'appariement entre une frame et la forme qu'on lui attribue.
FORMES_DISTINGUABLES = ((320, 180), (321, 181), (322, 182))


def fabrique_de_frames(tmp_path: Path, cardinal: int = 3) -> list[Path]:
    """`cardinal` chemins de frames aux noms DISTINGUABLES.

    Les noms portent leur rang, si bien qu'une permutation se voit. Les
    fichiers sont crees vides : la sonde est doublee dans les tests, jamais
    executee pour de vrai.
    """
    chemins = []
    for rang in range(1, cardinal + 1):
        chemin = tmp_path / f"frame_{rang:03d}.tiff"
        chemin.write_bytes(b"")
        chemins.append(chemin)
    return chemins


def sonde_uniforme(forme=(320, 180)):
    """Une sonde qui rend TOUJOURS la meme forme -- le cas nominal."""
    def _sonde(frame_path, *, ffprobe_bin="ffprobe"):
        return forme
    return _sonde


def sonde_divergente_au_milieu(cardinal: int = 3):
    """Une sonde dont la frame DIVERGENTE est au MILIEU, jamais aux bords.

    C'est le point 2 bis de la regle des fabriques : une cible en derniere
    position ne distingue pas un `break` premature d'un parcours complet.
    """
    milieu = cardinal // 2
    def _sonde(frame_path, *, ffprobe_bin="ffprobe"):
        rang = int(Path(frame_path).stem.split("_")[1]) - 1
        return FORMES_DISTINGUABLES[1] if rang == milieu else FORMES_DISTINGUABLES[0]
    return _sonde


class RappelEspion:
    """Un rappel qui enregistre la SUITE EXACTE des jalons recus.

    On compare des suites, jamais un cardinal : « un jalon est emis » ne
    mesure rien, « l'ensemble des jalons est EXACTEMENT [...] » mesure
    l'emission ET son unicite.
    """

    def __init__(self) -> None:
        self.jalons: list[tuple[int, int]] = []

    def __call__(self, faites, total):
        self.jalons.append((faites, total))


# ===========================================================================
# AC 1, 2, 4 -- ensure_uniform_frame_shapes emet un jalon par frame SONDEE
# ===========================================================================

def test_AC_1_la_sonde_de_formes_emet_un_jalon_par_frame(tmp_path, monkeypatch):
    """La suite des jalons est EXACTEMENT celle des frames sondees."""
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme())
    espion = RappelEspion()

    codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=espion)

    assert espion.jalons == [(1, 3), (2, 3), (3, 3)]


def test_AC_2_le_numerateur_est_le_cardinal_REEL_des_frames_sondees(tmp_path, monkeypatch):
    """Le jalon compte ce qui a ete sonde, jamais un compteur independant.

    Mesure sur SEPT frames : un `enumerate` decale d'un rendrait `(0, 7)` en
    premier jalon ou `(7, 7)` absent, et un compteur de boucle separe
    divergerait du cardinal reel.
    """
    frames = fabrique_de_frames(tmp_path, 7)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme())
    espion = RappelEspion()

    codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=espion)

    assert espion.jalons == [(n, 7) for n in range(1, 8)]


def test_AC_4_sans_rappel_le_comportement_est_RIGOUREUSEMENT_inchange(tmp_path, monkeypatch):
    """Repli `AR3` : aucun rappel, aucune difference observable."""
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme((640, 360)))

    sans_mot_cle = codec_profiles.ensure_uniform_frame_shapes(frames)
    avec_none = codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=None)

    assert sans_mot_cle == avec_none == (640, 360)


def test_AC_4_bis_le_mot_cle_est_OPTIONNEL_dans_la_signature():
    """Il s'ajoute, il ne renomme rien -- les appelants existants tiennent."""
    parametres = inspect.signature(codec_profiles.ensure_uniform_frame_shapes).parameters
    assert "rappel_progression" in parametres
    assert parametres["rappel_progression"].default is None
    # Les deux parametres d'origine sont intacts, dans le meme ordre.
    assert list(parametres)[:2] == ["frame_paths", "ffprobe_bin"]


# ===========================================================================
# AC 3 -- aucune frame ne cesse d'etre sondee
# ===========================================================================

def test_AC_3_toutes_les_frames_sont_sondees_MEME_quand_les_formes_divergent(tmp_path, monkeypatch):
    """Le refus arrive APRES le parcours complet, et le message le prouve.

    La frame divergente est au MILIEU des trois : un `break` au premier ecart
    ne sonderait que deux frames sur trois, et le message perdrait la
    troisieme.
    """
    frames = fabrique_de_frames(tmp_path, 3)
    sondees: list[str] = []

    def sonde_tracante(frame_path, *, ffprobe_bin="ffprobe"):
        sondees.append(Path(frame_path).name)
        return sonde_divergente_au_milieu(3)(frame_path, ffprobe_bin=ffprobe_bin)

    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_tracante)

    with pytest.raises(codec_profiles.EncodeConfigurationError) as refus:
        codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=RappelEspion())

    assert sondees == ["frame_001.tiff", "frame_002.tiff", "frame_003.tiff"]
    # Les DEUX formes figurent au message : la garde n'a rien tronque.
    assert "320x180" in str(refus.value) and "321x181" in str(refus.value)


def test_AC_3_bis_les_jalons_du_parcours_refuse_vont_JUSQU_AU_BOUT(tmp_path, monkeypatch):
    """Un refus de forme n'ecourte pas la progression : 3 frames, 3 jalons."""
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_divergente_au_milieu(3))
    espion = RappelEspion()

    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=espion)

    assert espion.jalons == [(1, 3), (2, 3), (3, 3)]


def test_AC_3_ter_une_sequence_VIDE_refuse_sans_ouvrir_le_canal(tmp_path):
    """Le canal ne s'ouvre qu'apres les refus durs.

    Motif de `write_lot_output_frames:1896` : un lot refuse ne doit produire
    AUCUN jalon, sans quoi l'ecran afficherait une tache qui a commence alors
    que rien n'a ete fait.
    """
    espion = RappelEspion()

    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.ensure_uniform_frame_shapes([], rappel_progression=espion)

    assert espion.jalons == []


# ===========================================================================
# AC 12, 13 -- l'observation ne casse jamais l'observe, et RECIPROQUEMENT
# ===========================================================================

def test_AC_12_un_rappel_qui_LEVE_n_empeche_pas_la_sonde_d_aboutir(tmp_path, monkeypatch):
    """`EPIC7-ARB-79` : l'observation ne casse jamais l'observe."""
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme((800, 600)))

    def rappel_hostile(faites, total):
        raise RuntimeError("le rappel est casse")

    forme = codec_profiles.ensure_uniform_frame_shapes(
        frames, rappel_progression=rappel_hostile)

    assert forme == (800, 600)


def test_AC_12_bis_la_defaillance_du_rappel_n_est_journalisee_QU_UNE_FOIS(
        tmp_path, monkeypatch, caplog):
    """Trois frames, trois levees, UN SEUL avertissement.

    Un avertissement par frame noierait le journal d'un lot de 300 frames.
    C'est le drapeau `_defaillance_journalisee` de l'emetteur qui le tient --
    la story ne le reimplemente pas.
    """
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme())

    def rappel_hostile(faites, total):
        raise RuntimeError("le rappel est casse")

    with caplog.at_level("WARNING", logger=progression._JOURNAL.name):
        codec_profiles.ensure_uniform_frame_shapes(
            frames, rappel_progression=rappel_hostile)

    avertissements = [e for e in caplog.records if e.levelname == "WARNING"]
    assert len(avertissements) == 1


def test_AC_13_une_exception_du_TRAVAIL_traverse_INTACTE(tmp_path, monkeypatch):
    """Le symetrique, et c'est l'interdit le plus facile a violer.

    L'absorption ne couvre QUE le canal. Une panne de sonde garde son type ET
    son texte -- un `try/except Exception` large autour de la boucle les
    avalerait tous les deux.
    """
    frames = fabrique_de_frames(tmp_path, 3)

    def sonde_en_panne(frame_path, *, ffprobe_bin="ffprobe"):
        raise codec_profiles.ProbeUnavailableError("ffprobe introuvable: PATH vide")

    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_en_panne)

    with pytest.raises(codec_profiles.ProbeUnavailableError) as panne:
        codec_profiles.ensure_uniform_frame_shapes(
            frames, rappel_progression=RappelEspion())

    assert "ffprobe introuvable: PATH vide" in str(panne.value)


# ===========================================================================
# AC 14 -- monotone, borne, et JAMAIS force a total
# ===========================================================================

def test_AC_14_les_jalons_sont_STRICTEMENT_croissants(tmp_path, monkeypatch):
    """Monotonie : la suite des numerateurs croit d'un en un, sans doublon."""
    frames = fabrique_de_frames(tmp_path, 5)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme())
    espion = RappelEspion()

    codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=espion)

    numerateurs = [faites for faites, _ in espion.jalons]
    assert numerateurs == sorted(set(numerateurs)) == [1, 2, 3, 4, 5]


def test_AC_14_bis_le_total_est_le_MEME_sur_tous_les_jalons(tmp_path, monkeypatch):
    """Le denominateur ne bouge pas en cours de route."""
    frames = fabrique_de_frames(tmp_path, 4)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme())
    espion = RappelEspion()

    codec_profiles.ensure_uniform_frame_shapes(frames, rappel_progression=espion)

    assert {total for _, total in espion.jalons} == {4}


def test_AC_14_ter_un_rappel_NON_CALLABLE_est_neutralise_sans_lever(tmp_path, monkeypatch):
    """L'emetteur neutralise ce qui n'est pas appelable -- pas la story."""
    frames = fabrique_de_frames(tmp_path, 3)
    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_uniforme((100, 50)))

    assert codec_profiles.ensure_uniform_frame_shapes(
        frames, rappel_progression="je ne suis pas appelable") == (100, 50)


# ===========================================================================
# AC 7, 8 -- la traversee des TROIS signatures
# ===========================================================================

@pytest.mark.parametrize("fonction, module", [
    (codec_profiles.run_encode, "codec_profiles.run_encode"),
    (encode.execute_plan, "encode.execute_plan"),
    (encode_master.encoder_le_master_du_lot, "encode_master.encoder_le_master_du_lot"),
])
def test_AC_7_les_TROIS_signatures_de_la_chaine_portent_le_rappel(fonction, module):
    """Le canal traverse la chaine entiere, sinon il ne sort jamais du coeur.

    `encoder_le_master_du_lot` n'appelle JAMAIS `run_encode` directement :
    elle passe par `encode.execute_plan`. Un maillon sans le mot-cle rompt le
    canal en silence.
    """
    parametres = inspect.signature(fonction).parameters
    assert "rappel_progression" in parametres, module
    assert parametres["rappel_progression"].default is None, module


def test_AC_8_le_nom_du_mot_cle_est_celui_QUE_LA_TUI_INTROSPECTE():
    """La jonction est SILENCIEUSE par construction, donc elle se mesure ici.

    `tui/atelier_exports_execution` compose son mot-cle depuis la SIGNATURE
    du point d'entree. Un nom different -- `progress_callback`, `on_progress`
    -- laisserait la TUI figee sur `{}` et le rotor muet, SANS QU'AUCUN TEST
    NE ROUGISSE. C'est pourquoi le nom se mesure au lieu de se supposer.
    """
    from mixed_media_utility.tui import atelier_exports_execution

    attendu = atelier_exports_execution.NOM_DU_RAPPEL_DE_PROGRESSION
    parametres = inspect.signature(encode_master.encoder_le_master_du_lot).parameters
    assert attendu in parametres


def test_AC_8_bis_le_rappel_n_est_PAS_absorbe_par_un_kwargs():
    """Un `**kwargs` accepterait le nom sans l'EXPOSER a l'introspection."""
    parametres = inspect.signature(encode_master.encoder_le_master_du_lot).parameters
    assert parametres["rappel_progression"].kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


class _ArretDansLeMaillon(Exception):
    """Sentinelle de CONTROLE : elle arrete `execute_plan` dans le maillon vise.

    Ce n'est pas une panne simulee. `execute_plan` verifie les metadonnees puis
    bascule le fichier ; rien de tout cela n'appartient a ce que ce test mesure,
    et le laisser tourner mesurerait autre chose que le maillon. La levee se
    fait APRES la capture, donc elle n'enleve rien a l'observation.
    """


def _plan_temoin(tmp_path):
    """Un `encode.EncodePlan` REEL, assez peuple pour entrer dans `execute_plan`.

    Recopie de la fabrique du banc de l'atelier Exports plutot qu'importee : ce
    banc-ci ne doit dependre d'aucun module de `tui/` (AC 24). Les trois objets
    composites sont des doubles -- `execute_plan` n'en lit que `size` et
    `emitted` avant l'appel mesure --, mais le PLAN, lui, est celui du produit :
    c'est lui qui porte `output_path`, donc la reservation atomique traversee
    avant le maillon.
    """
    import types as _types

    from mixed_media_utility.io import project_layout

    projet = tmp_path / "projet_temoin"
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir(parents=True)
    frames = tuple(projet / f"frame_{rang:03d}.tiff" for rang in range(3))
    for frame in frames:
        frame.write_bytes(b"")
    return encode.EncodePlan(
        project_dir=projet,
        lot_id="temoin-04_25",
        lot_state="reconstruction",
        profile_id=codec_profiles.DEFAULT_PROFILE_ID,
        container="mov",
        resolution=_types.SimpleNamespace(size=(1920, 1080)),
        source_size=(1920, 1080),
        frame_paths=frames,
        frame_rate=25.0,
        exact_frame_rate="25/1",
        timecode=_types.SimpleNamespace(emitted="00:00:00:00"),
        verdict=_types.SimpleNamespace(),
        container_tags={},
        output_path=(projet / project_layout.OUTPUTS_DIRNAME
                     / "temoin-04_25_mmu_prores_hq.mov"),
        overwrite=False,
        muxed_frame_paths=frames,
    )


#: Le marqueur d'un mot-cle ABSENT, distinct de `None` qui est une valeur licite.
_ABSENT = object()


def test_P2_le_maillon_du_MILIEU_transmet_la_VALEUR_et_pas_le_NOM(
        tmp_path, monkeypatch):
    """**Le maillon du milieu peut garder sa signature et jeter la valeur.**

    Finding `P2` de la revue (couches 2 et 3), et c'est mot pour mot le risque
    que l'AC 7 dit ecarter : `execute_plan` porte `rappel_progression` dans sa
    signature -- ce que `test_AC_7` mesure -- et rien ne mesurait qu'elle le
    **transmette**. Remplacer la transmission par `rappel_progression=None`
    laissait **778 tests verts** sur le perimetre declare. La panne : la TUI
    passe son rappel, le coeur le jette, la barre reste figee -- c'est-a-dire
    exactement ce que cette story existe pour supprimer.

    **Trois rappels distinguables, et la cible n'est jamais en premiere
    position** (regle des fabriques, points 1 et 2). Comparer la SUITE des objets
    recus a la suite des objets donnes mesure trois choses qu'une assertion
    "n'est pas `None`" ne mesure pas : que la valeur traverse, que ce soit LA
    bonne -- un maillon qui capturerait le premier rappel et le rejouerait
    ensuite est tue --, et que l'ordre soit tenu.

    L'identite (`is`) plutot que l'egalite : deux `RappelEspion` neufs sont
    egaux par defaut, si bien qu'une comparaison par valeur laisserait passer
    la substitution qu'on veut precisement attraper.
    """
    donnes = [RappelEspion(), RappelEspion(), RappelEspion()]
    recus = []

    def faux_run_encode(*_args, **kwargs):
        recus.append(kwargs.get("rappel_progression", _ABSENT))
        raise _ArretDansLeMaillon

    monkeypatch.setattr(codec_profiles, "run_encode", faux_run_encode)

    for rang, rappel in enumerate(donnes):
        plan = _plan_temoin(tmp_path / f"passage_{rang}")
        with pytest.raises(_ArretDansLeMaillon):
            encode.execute_plan(plan, rappel_progression=rappel)

    assert len(recus) == len(donnes), recus
    for rang, (recu, donne) in enumerate(zip(recus, donnes)):
        assert recu is donne, (rang, recu, donne)


def test_P2_bis_sans_rappel_le_maillon_transmet_None_et_pas_AUTRE_CHOSE(
        tmp_path, monkeypatch):
    """Le volet symetrique, sans lequel le precedent est vert pour rien.

    Un maillon qui fabriquerait un rappel de son cru quand l'appelant n'en
    donne pas armerait le canal sans que personne l'ait demande -- c'est le
    repli `AR3` retourne, et l'argv de production cesserait d'etre celui d'avant
    la story. Le mot-cle doit donc arriver, et valoir `None` : `_ABSENT` et
    `None` sont deux verdicts differents, et seul le second est licite.
    """
    recus = []

    def faux_run_encode(*_args, **kwargs):
        recus.append(kwargs.get("rappel_progression", _ABSENT))
        raise _ArretDansLeMaillon

    monkeypatch.setattr(codec_profiles, "run_encode", faux_run_encode)

    plan = _plan_temoin(tmp_path)
    with pytest.raises(_ArretDansLeMaillon):
        encode.execute_plan(plan)

    assert recus == [None], recus


def test_AC_8_ter_la_TUI_compose_desormais_le_mot_cle_CONTRE_LE_VRAI_COEUR():
    """La jonction, mesuree de bout en bout et non sur un double.

    C'est le retournement de `test_le_raccord_est_VIDE_...` : ce banc-la
    mesurait que le coeur ne savait pas compter. Il sait.
    """
    from mixed_media_utility.tui import atelier_exports_execution

    assert atelier_exports_execution.le_coeur_sait_compter() is True


# ===========================================================================
# Lot C -- le flux `-progress` de ffmpeg (AC 5, 6, 10 ter, 15-21 ter)
# ===========================================================================

#: Un faux ffmpeg, lance par `sys.executable` : la couture est appelable seule,
#: donc mesurable sans vrai binaire. Motif litteral de
#: `test_ffmpeg_utils.FAUX_FFMPEG`.
#:
#: Il prend, dans l'ordre : le texte a ecrire sur sa sortie standard (blocs
#: `-progress`), le nombre d'octets a ecrire sur `stderr`, le code de retour,
#: et une pause entre deux lignes de sortie standard.
FAUX_FFMPEG = """
import sys, time
sortie, octets_stderr, code, pause = sys.argv[1:5]
sys.stderr.write("x" * int(octets_stderr))
sys.stderr.flush()
for ligne in sortie.split("|"):
    if ligne:
        sys.stdout.write(ligne + "\\n")
        sys.stdout.flush()
        time.sleep(float(pause))
sys.exit(int(code))
"""


def commande_factice(*, sortie="", octets_stderr=0, code=0, pause=0.0):
    """L'argv d'un faux ffmpeg, prete a passer a la couture."""
    return [sys.executable, "-c", FAUX_FFMPEG,
            sortie, str(octets_stderr), str(code), str(pause)]


def bloc_de_progression(frame, fin=False):
    """Un bloc `-progress` tel que ffmpeg 6.1.1 l'ecrit, mesure le 2026-09-03.

    `frame=` vient en tete, suivi de onze autres cles dont plusieurs portent
    `N/A` dans le premier bloc. Le bloc est recopie du vrai binaire,
    `out_time=N/A` compris : une fabrique qui n'ecrirait que `frame=N`
    mesurerait un flux plus propre que celui du terrain, et laisserait donc
    passer une couture qui trebucherait sur les dix autres lignes.
    """
    return "|".join([
        f"frame={frame}",
        "fps=0.00",
        "stream_0_0_q=0.0",
        "bitrate=N/A",
        "total_size=0",
        "out_time_us=N/A",
        "out_time_ms=N/A",
        "out_time=N/A",
        "dup_frames=0",
        "drop_frames=0",
        "speed=N/A",
        "progress=end" if fin else "progress=continue",
    ])


def flux_mesure(*frames):
    """Le flux complet pour la suite de comptes `frames`, dernier bloc clos."""
    dernier = len(frames) - 1
    return "|".join(bloc_de_progression(frame, fin=(rang == dernier))
                    for rang, frame in enumerate(frames))


# ---------------------------------------------------------------------------
# AC 5 -- `-progress` en option GLOBALE, sans deplacer aucun element
# ---------------------------------------------------------------------------

#: **La cible de progression, ECRITE ICI et jamais importee** (finding `P1` de
#: la revue, convergence des couches 1 et 2).
#:
#: Le banc comparait auparavant `codec_profiles.PROGRESS_TARGET_STDOUT` a
#: lui-meme, aux deux seuls endroits qui touchent la cible : passee en entree
#: puis relue en sortie, la constante est vraie par construction quelle que
#: soit sa valeur. Mesure : `"pipe:1"` -> `"pipe:2"` survit a **272 tests**
#: (couche 2) et le litteral n'existait dans `tests/` qu'en docstring.
#:
#: Le cout de la corruption a ete mesure sur le VRAI ffmpeg 6.1.1, et il est
#: double : `pipe:2` est `stderr`, donc **zero octet** n'arrive au canal de
#: progression -- la barre reste figee -- **et** les blocs de progression
#: noient le diagnostic d'`EncodeRunError`, dont la fenetre est `[-600:]`.
#: C'est une constante centrale d'un calcul au sens de la politique : zero
#: survivant.
#:
#: Elle est recopiee plutot que lue parce qu'un test qui importe la constante
#: qu'il mesure ne mesure rien. Le prix est connu et assume : un changement
#: DELIBERE de cible fait rougir ce banc, ce qui est exactement le service
#: rendu.
CIBLE_DE_PROGRESSION_ATTENDUE = "pipe:1"


def test_AC_5_progress_est_une_option_GLOBALE_en_index_2():
    """Et les QUATRE contraintes d'argv deja mesurees restent vraies.

    Elles sont recopiees ici depuis `test_codec_profiles.py` (`:379`, `:380`,
    `:537`, `:556`) parce que c'est leur violation qui est le risque : une
    option globale posee au mauvais endroit deplace `-r`, `-f concat` ou le
    `-f <muxer>` final, et chacun de ces trois a une panne mesuree derriere
    lui.
    """
    argv = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 25, "o.mov",
        progress_target=CIBLE_DE_PROGRESSION_ATTENDUE)

    assert argv[:2] == ["ffmpeg", "-n"]
    assert argv[2:4] == ["-progress", CIBLE_DE_PROGRESSION_ATTENDUE]
    # L'option est bien AVANT le premier `-i`.
    assert argv.index("-progress") < argv.index("-i")
    # Les trois contraintes de position, inchangees.
    assert argv[argv.index("-i") - 3:argv.index("-i")] == ["concat", "-safe", "0"]
    assert argv[-3:-1] == ["-f", "mov"]
    rates = [argv[i + 1] for i, jeton in enumerate(argv) if jeton == "-r"]
    assert rates == ["25/1", "25/1"], rates


def test_AC_5_bis_sans_cible_l_argv_est_RIGOUREUSEMENT_celui_d_avant():
    """Le repli `AR3` ne se contente pas d'"a peu pres pareil".

    L'egalite porte sur la LISTE entiere, jamais sur l'absence du seul mot
    `-progress` : une option globale ajoutee par megarde ailleurs passerait
    une assertion d'absence.
    """
    nu = codec_profiles.build_encode_command("prores_hq", "l.concat", 25, "o.mov")
    defaut = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 25, "o.mov", progress_target=None)
    assert defaut == nu
    assert "-progress" not in nu


# ---------------------------------------------------------------------------
# AC 6 -- la couture lit le flux et emet des jalons
# ---------------------------------------------------------------------------

def test_AC_6_la_couture_emet_la_SUITE_EXACTE_des_comptes_du_flux():
    """Trois blocs distinguables, et le compte vise est AU MILIEU.

    Ni le premier ni le dernier : une couture qui ne lirait que le premier
    bloc, ou qui n'emettrait qu'au bloc `progress=end`, resterait verte sur
    une fabrique a deux blocs.
    """
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 1, 2, 3)), emetteur=emetteur)

    assert rc == 0
    assert stderr == ""
    # `frame=0` n'est PAS un jalon : le travail n'a pas avance.
    assert espion.jalons == [(1, 3), (2, 3), (3, 3)], espion.jalons


def test_AC_6_bis_le_denominateur_est_CONSTANT_et_vaut_le_cardinal_des_frames():
    """Un total qui bougerait ferait sauter la barre a l'ecran."""
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 7)
    codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 2, 5, 7)), emetteur=emetteur)
    assert espion.jalons == [(2, 7), (5, 7), (7, 7)], espion.jalons
    assert {total for _faites, total in espion.jalons} == {7}


def test_AC_6_ter_le_code_de_retour_et_stderr_TRAVERSENT_la_couture():
    """La couture rend `(returncode, stderr)`, et les deux servent a lever."""
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 3), octets_stderr=12, code=187),
        emetteur=emetteur)
    assert rc == 187
    assert stderr == "x" * 12


# ---------------------------------------------------------------------------
# AC 21 bis -- la degradation, jamais l'evitement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sortie,motif", [
    ("", "flux totalement muet"),
    ("frame=N/A|progress=end", "valeur non entiere"),
    ("frame|progress=end", "ligne sans separateur"),
    ("images_encodees=2|progress=end", "cle inconnue -- un format futur"),
    ("frame=|progress=end", "valeur vide"),
])
def test_AC_21_bis_un_flux_ILLISIBLE_ne_produit_aucun_jalon_et_ne_leve_pas(
        sortie, motif):
    """Cinq formes de flux qu'aucun `frame=<entier>` ne traverse.

    L'ensemble des jalons est EXACTEMENT vide, et l'encodage rend son code de
    retour normalement : c'est la degradation qu'exige l'AC 21 bis, et c'est
    ce qui autorise ce module a dependre d'un format que
    `ffmpeg_utils.py` s'interdit.
    """
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=sortie), emetteur=emetteur)
    assert rc == 0, motif
    assert espion.jalons == [], (motif, espion.jalons)


@pytest.mark.parametrize("ligne_fautive,motif", [
    ("frame=N/A", "valeur non entiere"),
    ("frame", "ligne sans separateur"),
    ("images_encodees=2", "cle inconnue -- un format futur"),
    ("frame=", "valeur vide"),
])
def test_P5_une_ligne_illisible_AU_MILIEU_n_ARRETE_pas_le_comptage(
        ligne_fautive, motif):
    """**La meme tolerance, mais la ligne fautive n'est plus en tete.**

    Finding `P5` de la revue (couches 1, 2 **et** 3), et sa cause de banc est
    nommee : les cinq cas d'`test_AC_21_bis` ci-dessus placent tous la ligne
    fautive **en premiere position, sans aucun `frame=` valide derriere**. Ils
    mesurent donc "aucun jalon" -- ce qui reste vrai qu'on ait *saute* la ligne
    ou qu'on se soit *arrete* dessus. Trois mutants y survivaient, dont un
    `return` qui fait que l'encodage **ne rend jamais la main** : 45 s de sonde
    contre 0,03 s sain, sans plafond pour l'en sortir.

    Points 2 bis et 4 de la regle des fabriques : la cible est **au milieu**, et
    il y a **un element valide APRES elle**. Sans ce dernier, la difference
    entre "sauter" et "arreter" reste litteralement invisible.

    L'ensemble des jalons est mesure comme EXACTEMENT `[(1, 3), (2, 3)]` : le
    premier prouve que la lecture avait commence, le second qu'elle a repris.

    *La ligne VIDE ne figure pas dans ce jeu : le faux ffmpeg saute les
    fragments vides (`if ligne:`), donc elle n'atteint jamais la couture. Elle
    est mesuree la ou elle existe, au niveau du flux, par
    `test_P3_site_2_...`.*
    """
    sortie = "|".join(["frame=1", ligne_fautive, "frame=2", "progress=end"])
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)

    rc, _stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=sortie), emetteur=emetteur)

    assert rc == 0, motif
    assert espion.jalons == [(1, 3), (2, 3)], (motif, espion.jalons)


#: **Un faux ffmpeg qui fabrique son VOLUME lui-meme**, et il le faut.
#:
#: `FAUX_FFMPEG` recoit sa sortie par l'argv, et un seul element d'argv est
#: plafonne a 128 Kio par le noyau (`MAX_ARG_STRLEN`) -- une premiere ecriture
#: de ce test a rendu `OSError: [Errno 7] Argument list too long` avant meme
#: d'atteindre la couture. La garniture est donc engendree DANS le fils.
#:
#: Il prend, dans l'ordre : le nombre de jalons a emettre et le nombre de
#: lignes de garniture entre deux jalons.
FAUX_FFMPEG_VOLUMINEUX = """
import sys
jalons, garniture = int(sys.argv[1]), int(sys.argv[2])
remplissage = "remplissage=" + "x" * 200
for compte in range(1, jalons + 1):
    sys.stdout.write("frame=%d\\n" % compte)
    for _ in range(garniture):
        sys.stdout.write(remplissage + "\\n")
    sys.stdout.flush()
sys.exit(0)
"""


def test_P5_bis_la_LECTURE_precede_l_attente_meme_tube_SATURE():
    """**L'ordre lecture-puis-attente, mesure plutot que commente.**

    Second mutant survivant de `P5` : un `processus.wait()` place **avant**
    `_compter_sur_le_flux` survit au banc entier alors qu'il bloque dur des que
    la sortie depasse le tampon du tube -- le fils attend qu'on lise, le pere
    attend qu'il finisse. La sonde de la revue l'a mesure : 1 172 Kio ->
    `EXIT=124`.

    Le meme piege que `test_AC_17` mesure sur `stderr`, du cote `stdout` cette
    fois : plus de 256 Kio, quatre fois la borne de 64 Kio, donc au-dela de
    toute taille de tampon plausible.

    **La panne est bornee ICI plutot que laissee suspendre.** Une couture qui
    bloque ne rougit pas, elle emporte la course entiere -- c'est le motif
    d'existence de `scripts/mesure/mesure.py`. La couture tourne donc dans un
    fil dont on constate la fin : sur le code sain elle rend en une fraction de
    seconde, et l'echec est une ASSERTION et non un plafond de suite.

    **Trois jalons, et la garniture est INTERCALEE** (regle des fabriques,
    point 2 bis) : une garniture mise en queue laisserait les trois jalons
    arriver avant toute saturation, et le mutant passerait.

    *Reserve, dite plutot que tue : en regime mute, le faux ffmpeg reste bloque
    a l'ecriture apres que le fil a ete abandonne. C'est sans consequence dans
    une campagne de mutation -- l'arbre est jetable -- et c'est le prix d'une
    panne qui, autrement, ne se manifeste que par une suspension.*
    """
    import threading

    # 3 jalons x 420 lignes de 213 octets = plus de 256 Kio.
    commande = [sys.executable, "-c", FAUX_FFMPEG_VOLUMINEUX, "3", "420"]
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    verdict: dict[str, object] = {}

    def couture():
        verdict["rc"], _ = codec_profiles._executer_ffmpeg_en_comptant(
            commande, emetteur=emetteur)

    fil = threading.Thread(target=couture, daemon=True)
    fil.start()
    fil.join(timeout=30.0)

    assert not fil.is_alive(), (
        "la couture n'a pas rendu la main sur 256 Kio de sortie standard : "
        "l'attente du processus precede la lecture du tube")
    assert verdict["rc"] == 0, verdict
    assert espion.jalons == [(1, 3), (2, 3), (3, 3)], espion.jalons


def test_AC_21_bis_un_compte_SUPERIEUR_au_total_est_borne_et_non_refuse():
    """ffmpeg peut annoncer plus de frames que la liste n'en porte.

    Mesure : `-r` different des deux cotes rend `nb_frames` faux (docstring de
    `build_encode_command`). La borne est celle de `EmetteurProgression`, et
    l'ecran ne doit jamais lire `130/124`.
    """
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 2, 9)), emetteur=emetteur)
    assert espion.jalons == [(2, 3), (3, 3)], espion.jalons


# ---------------------------------------------------------------------------
# P16, P17, P23 -- trois revendications de la fiche que rien ne mesurait
#
# Toutes trois SURVIVAIENT a une injection ciblee des couches 2 et 3, et le
# comportement livre est bon dans les trois cas : ce qui manquait etait la
# mesure, pas le code. Elles sont regroupees parce qu'elles tiennent le meme
# contrat -- la couture rend le meme couple `(rc, stderr)` que le repli `AR3`,
# quoi qu'il arrive au processus ou aux octets.
# ---------------------------------------------------------------------------

#: Un faux ffmpeg qui ecrit des octets NON-UTF-8 sur `stderr` et sur le flux.
#:
#: `0xff` n'est une sequence UTF-8 valide dans aucun contexte. Le cas reel n'est
#: pas theorique : `stderr` porte les CHEMINS DE FICHIERS que ffmpeg journalise,
#: et un nom de frame portant un octet non-UTF-8 suffit.
FAUX_FFMPEG_NON_UTF8 = """
import sys
sys.stderr.buffer.write(b"erreur sur \\xff/frame.tiff")
sys.stderr.buffer.flush()
sys.stdout.buffer.write(b"frame=1\\n")
sys.stdout.buffer.write(b"chemin=\\xff\\n")
sys.stdout.buffer.write(b"frame=2\\n")
sys.stdout.buffer.flush()
sys.exit(0)
"""


def test_P16_un_octet_NON_UTF8_ne_fait_echouer_ni_la_relecture_ni_le_flux():
    """**Un encodage REUSSI ne doit pas echouer a la relecture de son journal.**

    Finding `P16` (couche 2, mutants `M38` et `M39`, tous deux survivants) et
    `M34` de `P23`. Aucun test ne faisait passer d'octet non-UTF-8 par la
    couture : `errors="replace"` pouvait donc devenir `errors="strict"` sans
    qu'un test le voie.

    `M39` est le plus genant des deux, et il ne l'est pas pour une raison de
    style : `stderr` porte les **chemins de fichiers** que ffmpeg journalise. Un
    chemin de frame a octet non-UTF-8 ferait lever `UnicodeDecodeError` **hors
    de toute absorption** -- l'encodage a reussi, et c'est sa RELECTURE qui
    echoue --, et la promesse explicite de la docstring tomberait : "le texte
    relu est identique au caractere pres a celui que `capture_output=True`
    rend sur l'autre branche", cette autre branche gardant `errors="replace"`.

    **Les deux flux portent l'octet, et le jalon d'apres est mesure** : une
    ligne indechiffrable au milieu ne doit pas arreter le comptage, ce qui
    distingue "remplace" de "s'arrete la".
    """
    commande = [sys.executable, "-c", FAUX_FFMPEG_NON_UTF8]
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)

    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande, emetteur=emetteur)

    assert rc == 0
    # Le caractere de remplacement est present, et rien n'a leve.
    assert "\ufffd" in stderr, repr(stderr)
    assert stderr.startswith("erreur sur "), repr(stderr)
    # Et le comptage a repris APRES la ligne indechiffrable.
    assert espion.jalons == [(1, 3), (2, 3)], espion.jalons


def test_P23_le_repli_AR3_relit_lui_aussi_en_REMPLACANT(monkeypatch):
    """`M34` de `P23` : "au caractere pres" portait sur les DEUX branches.

    La fiche revendique que le repli `AR3` "reprend le geste d'avant la story au
    caractere pres", en citant ses mots-cles. Aucune mesure ne portait sur eux.
    Celle-ci porte sur le seul qui ait une consequence observable : sans
    `errors="replace"`, un `stderr` non-UTF-8 ferait lever `subprocess.run`
    lui-meme.

    La branche est prise **sans emetteur actif** -- c'est le seul chemin de
    production d'aujourd'hui -- et le verdict est le meme que celui de la
    couture ci-dessus : c'est ce que "identique au caractere pres" veut dire.
    """
    commande = [sys.executable, "-c", FAUX_FFMPEG_NON_UTF8]

    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(commande, emetteur=None)

    assert rc == 0
    assert "\ufffd" in stderr, repr(stderr)
    assert stderr.startswith("erreur sur "), repr(stderr)


#: Un faux ffmpeg qui FERME sa sortie standard puis survit un moment.
#:
#: C'est le regime qui separe "on attend le processus" de "on rend la main des
#: que le tube est clos" : l'EOF arrive tot, le code de retour tard.
FAUX_FFMPEG_QUI_SURVIT_A_SON_TUBE = """
import os, sys, time
sys.stdout.write("frame=1\\n")
sys.stdout.write("frame=2\\n")
sys.stdout.write("frame=3\\n")
sys.stdout.flush()
os.close(sys.stdout.fileno())
time.sleep(float(sys.argv[1]))
sys.exit(int(sys.argv[2]))
"""


def test_P17_le_processus_est_ATTENDU_et_son_code_de_retour_est_le_VRAI():
    """`P17` / `M19` : sans `processus.wait()`, le code de retour vaut `None`.

    Le faux binaire **ferme sa sortie standard** puis vit encore une demi-seconde
    avant de sortir en `187`. La lecture rend donc la main bien avant la fin du
    processus, et c'est exactement le regime ou l'attente se mesure : sans elle,
    `processus.returncode` est `None` -- ni un entier, ni le code du fils -- et
    la couture rendrait un couple que personne ne sait interpreter.

    Le verdict porte sur le code EXACT, jamais sur "un entier" : `187` est
    distinguable de `0`, ce qu'un `isinstance` ne dirait pas.
    """
    commande = [sys.executable, "-c", FAUX_FFMPEG_QUI_SURVIT_A_SON_TUBE, "0.5", "187"]
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)

    rc, _stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande, emetteur=emetteur)

    assert rc == 187, rc
    assert espion.jalons == [(1, 3), (2, 3), (3, 3)], espion.jalons


def test_P17_bis_aucun_processus_ne_SURVIT_a_l_appel(monkeypatch):
    """`P17` / `M20` et `M33` de `P23` : "aucun process laisse vivant".

    Le `finally` tue un processus qui aurait survecu a la boucle. La
    revendication etait au lot C de la fiche ; rien ne la mesurait.

    Le geste : on retient le `Popen` cree par la couture, et on interrompt la
    lecture par une exception. Sans le `kill()` du `finally`, le faux binaire --
    qui dort une seconde -- serait encore vivant au retour ; avec lui,
    `poll()` rend un code.

    **L'interruption est un ARRET DEMANDE**, donc elle traverse (voir plus haut)
    : c'est le regime le plus severe pour le `finally`, puisque la couture est
    quittee par une exception et non par la sortie normale de la boucle.
    """
    processus_vus = []
    vrai_popen = codec_profiles.subprocess.Popen

    def popen_espion(*args, **kwargs):
        processus = vrai_popen(*args, **kwargs)
        processus_vus.append(processus)
        return processus

    monkeypatch.setattr(codec_profiles.subprocess, "Popen", popen_espion)

    def rappel_qui_recoit_le_signal(faites, total):
        raise encode_master.TerminaisonDemandee("signal 15")

    emetteur = progression.EmetteurProgression(rappel_qui_recoit_le_signal, 3)
    commande = [sys.executable, "-c", FAUX_FFMPEG_QUI_SURVIT_A_SON_TUBE, "1.0", "0"]

    with pytest.raises(encode_master.TerminaisonDemandee):
        codec_profiles._executer_ffmpeg_en_comptant(commande, emetteur=emetteur)

    assert len(processus_vus) == 1, processus_vus
    assert processus_vus[0].poll() is not None, "un processus a survecu a l'appel"


# ---------------------------------------------------------------------------
# AC 18 / P6 -- le journal ffmpeg n'est PAS une persistance
#
# Finding `P6` (couche 3) : l'AC 18 n'avait aucun test, et tout son argument
# repose sur un seul geste -- le `os.unlink(stderr_path)` du `finally`. Une AC
# sans mutant nommable est une AC non couverte (regle 4.0(d)) ; celle-ci
# n'avait pas de test du tout, alors qu'elle porte un arbitrage
# (`EPIC11-ARB-189` : Egan a ECARTE l'ecriture sur disque).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,motif", [
    (0, "encodage reussi"),
    (187, "encodage en echec -- c'est le `finally` qui repond"),
])
def test_AC_18_le_journal_ffmpeg_ne_SURVIT_pas_a_l_appel(
        code, motif, tmp_path, monkeypatch):
    """**Le temporaire existe pendant, et il n'existe plus apres.**

    Les deux moities comptent, et la seconde seule serait verte pour rien : un
    appel qui n'aurait jamais cree de fichier -- la branche `AR3`, par exemple,
    qui prend `capture_output=True` -- n'en laisserait aucun non plus. La
    premiere moitie est donc mesuree par le CONTENU relu : `stderr` revient au
    caractere pres, ce qui ne peut arriver que si le fichier a bien porte le
    journal.

    Les deux regimes de sortie sont joues, et le second est le seul qui mesure
    le `finally` : un `os.unlink` place apres le `return` serait vert sur un
    encodage reussi et laisserait un fichier par ECHEC.

    **Le temporaire est REDIRIGE dans `tmp_path`, et ce n'est pas du confort**
    (finding `EC-2` de la couche de reprise). La premiere ecriture de ce test
    comparait un `glob` du repertoire temporaire **systeme**, partage par tous
    les workers : mesure, **10 courses `-n 4` sur 10 rouges**, alors que le
    parallelisme est le regime par defaut du depot depuis le 2026-09-01. Un
    autre worker qui encode au meme instant y pose son propre `.stderr`, et le
    test l'accusait. L'espace observe est desormais celui du test seul.

    *Reserve qui reste, dite plutot que tue : `codec_profiles.tempfile` **est**
    le module `tempfile` global, donc l'espion porte pendant ce test sur tout le
    processus. `monkeypatch` le retire a la sortie ; ce qui n'est pas mesure est
    ce qu'un autre appelant du meme worker verrait pendant.*
    """
    import tempfile as _tempfile

    abri = tmp_path / "temporaires"
    abri.mkdir()
    crees: list[str] = []
    vrai_mkstemp = _tempfile.mkstemp

    def mkstemp_espion(*args, **kwargs):
        kwargs.setdefault("dir", str(abri))
        descripteur, chemin = vrai_mkstemp(*args, **kwargs)
        crees.append(chemin)
        return descripteur, chemin

    monkeypatch.setattr(codec_profiles.tempfile, "mkstemp", mkstemp_espion)

    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(1, 2, 3), octets_stderr=64, code=code),
        emetteur=emetteur)

    # Le fichier a REELLEMENT servi : sans lui, ce texte ne reviendrait pas.
    assert rc == code, motif
    assert stderr == "x" * 64, motif
    assert len(crees) == 1, crees

    # Et il ne survit pas -- ni sous son nom, ni comme residu dans l'abri, qui
    # n'appartient qu'a ce test et se compare donc comme un ensemble EXACT.
    assert not Path(crees[0]).exists(), (motif, crees[0])
    assert list(abri.iterdir()) == [], sorted(abri.iterdir())


def test_AC_18_bis_aucun_journal_n_est_pose_A_COTE_DU_MASTER(
        tmp_path, monkeypatch):
    """L'autre forme de persistance que l'AC 18 ecarte, et elle est distincte.

    Un temporaire retire n'est pas une persistance ; **un journal conserve a
    cote du master en serait une**, et c'est litteralement ce qu'`EPIC11-ARB-189`
    a ecarte. Le volet ci-dessus regarde le repertoire temporaire ; celui-ci
    regarde l'arborescence du projet, ou rien ne doit apparaitre.

    L'ensemble est mesure comme **exactement** celui d'avant l'encodage, jamais
    comme "aucun fichier `.stderr`" : un journal depose sous un autre nom --
    `ffmpeg.log`, `master.mov.log` -- passerait une frontiere par extension.
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    espion, _temoins = _cabler_un_faux_encodage(
        monkeypatch, tmp_path, frames, comptes=(0, 1, 2, 3))
    master = tmp_path / "master.mov"

    avant = {chemin for chemin in tmp_path.rglob("*") if chemin.is_file()}

    codec_profiles.run_encode("prores_hq", frames, 25, master,
                              rappel_progression=espion)

    apres = {chemin for chemin in tmp_path.rglob("*") if chemin.is_file()}
    neufs = apres - avant

    # Le `.sonde` est ecrit par le FAUX binaire de ce banc -- c'est lui qui
    # prouve que le fichier de liste `concat` etait vivant pendant l'encodage
    # (`test_AC_21`). Il est retire NOMMEMENT, et son absence ferait rougir :
    # sans lui, le faux ffmpeg n'aurait pas tourne et la mesure porterait a
    # cote, verte pour rien.
    sondes = {chemin for chemin in neufs if chemin.name.endswith(".sonde")}
    assert sondes, sorted(neufs)

    # Le master est alors le SEUL fichier neuf de l'arborescence.
    assert neufs - sondes == {master}, sorted(neufs - sondes)


# ---------------------------------------------------------------------------
# AC 15, 17 -- ni plafond, ni tube sur stderr
# ---------------------------------------------------------------------------

def test_AC_17_un_stderr_de_plus_de_64_Kio_ne_BLOQUE_pas_la_couture():
    """**Le piege deja paye du depot, mesure ici plutot que commente.**

    Un `Popen(stderr=PIPE)` suivi d'une boucle se bloque des que ffmpeg
    remplit le tampon du tube (64 Kio) : le processus attend qu'on lise, la
    boucle attend qu'il finisse. 256 Kio est quatre fois la borne, donc au-dela
    de toute taille de tampon plausible. Si la couture repassait au tube, ce
    test ne rougirait pas -- il SUSPENDRAIT --, et c'est pour ca que la suite
    se lance avec un plafond PAR TEST (`scripts/mesure/mesure.py`).
    """
    octets = 256 * 1024
    espion = RappelEspion()
    emetteur = progression.EmetteurProgression(espion, 3)
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 3), octets_stderr=octets),
        emetteur=emetteur)
    assert rc == 0
    assert len(stderr) == octets
    assert espion.jalons == [(3, 3)], espion.jalons


def _appels(fonction):
    """Les appels ecrits dans le CORPS de `fonction`, lus sur l'arbre.

    Ni un `grep`, ni un `count` de texte : une docstring qui NOMME la forme
    interdite -- et une bonne docstring la nomme, pour dire pourquoi elle est
    interdite -- ferait rougir un compteur de sous-chaines. C'est le motif de
    `corps_de_classe` dans le banc de l'atelier Exports, applique ici.
    """
    arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
    return [noeud for noeud in ast.walk(arbre) if isinstance(noeud, ast.Call)]


def _nom_pointe(noeud):
    """`subprocess.run` pour un `ast.Attribute`, `""` sinon."""
    if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
        return f"{noeud.value.id}.{noeud.attr}"
    return ""


def test_AC_15_la_couture_n_acquiert_AUCUN_plafond_de_duree():
    """Frontiere NEGATIVE : un master 4K prend legitimement des dizaines de
    minutes, et un plafond romprait un encodage valide.

    La mesure porte sur le mot-cle `timeout=` d'un APPEL, la seule forme par
    laquelle il atteindrait `Popen.wait` ou `subprocess.run` -- et sur l'arbre
    plutot que sur le texte, pour que la docstring puisse nommer ce qu'elle
    interdit. Aucun test positif ne verrait revenir un plafond.
    """
    plafonds = [f"{_nom_pointe(appel.func) or getattr(appel.func, 'id', '?')}"
                for appel in _appels(codec_profiles._executer_ffmpeg_en_comptant)
                if any(mot.arg == "timeout" for mot in appel.keywords)]
    assert plafonds == [], plafonds


def test_AC_17_bis_stderr_n_est_JAMAIS_un_TUBE_dans_la_couture():
    """Volet syntaxique du test de blocage ci-dessus.

    Le test de 256 Kio le mesure par le comportement ; celui-ci nomme la
    forme fautive, pour qu'un `stderr=subprocess.PIPE` reintroduit rougisse
    meme si personne ne relance la mesure longue.
    """
    source = inspect.getsource(codec_profiles._executer_ffmpeg_en_comptant)
    assert "stderr=subprocess.PIPE" not in source
    assert "stderr=PIPE" not in source


# ---------------------------------------------------------------------------
# AC 4 / AR3 -- sans rappel actif, le geste d'avant au caractere pres
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("emetteur,motif", [
    (None, "aucun emetteur"),
    (progression.EmetteurProgression(None, 3), "emetteur sans rappel"),
    (progression.EmetteurProgression(lambda f, t: None, 0), "total nul"),
])
def test_AR3_la_couture_sans_emetteur_ACTIF_rend_le_meme_couple(emetteur, motif):
    """Les trois manieres d'etre inactif, et la cible est AU MILIEU.

    Un `if emetteur is None` seul laisserait passer les deux autres, et le
    canal partirait observer avec un rappel qui n'existe pas.
    """
    rc, stderr = codec_profiles._executer_ffmpeg_en_comptant(
        commande_factice(sortie=flux_mesure(0, 3), octets_stderr=5, code=3),
        emetteur=emetteur)
    assert (rc, stderr) == (3, "xxxxx"), motif


def test_AR3_bis_le_repli_passe_par_subprocess_run_et_la_branche_observee_par_Popen():
    """Deux branches nommees, mesurees par egalite de cardinal.

    `run_encode` n'en porte plus aucune -- la couture les porte toutes les
    deux --, et c'est ce que l'AC 10 ter fait basculer cote `tui/`.
    """
    couture = [_nom_pointe(appel.func)
               for appel in _appels(codec_profiles._executer_ffmpeg_en_comptant)]
    assert couture.count("subprocess.run") == 1, couture
    assert couture.count("subprocess.Popen") == 1, couture

    encodeur = [_nom_pointe(appel.func)
                for appel in _appels(codec_profiles.run_encode)]
    lances = [nom for nom in encodeur if nom.startswith("subprocess.")]
    assert lances == [], lances


# ---------------------------------------------------------------------------
# AC 19, 21, 21 ter -- les DEUX phases, dans le vrai `run_encode`
# ---------------------------------------------------------------------------

#: Un faux ffmpeg qui, en plus d'ecrire son flux, **cree son fichier de sortie**
#: et **sonde** un chemin donne au moment ou il tourne. La sonde est ce qui
#: mesure l'AC 21 : le fichier de liste `concat` doit etre vivant pendant toute
#: la duree du processus, et non jusqu'a son lancement seulement.
FAUX_FFMPEG_QUI_PRODUIT = """
import os, sys
sortie, a_creer, a_sonder = sys.argv[1:4]
for ligne in sortie.split("|"):
    if ligne:
        sys.stdout.write(ligne + "\\n")
        sys.stdout.flush()
open(a_creer, "wb").write(b"master factice")
open(a_creer + ".sonde", "w").write(
    "present" if os.path.exists(a_sonder) else "absent")
sys.exit(0)
"""


def _cabler_un_faux_encodage(monkeypatch, tmp_path, frames, comptes):
    """Doubler tout ce qui touche a ffmpeg/ffprobe, et rendre l'espion.

    Rend `(espion, temoins)`, ou `temoins` recoit la cible `-progress` que la
    fabrique de commande a reellement vue et le chemin du fichier de liste.
    """
    espion = RappelEspion()
    temoins = {}

    monkeypatch.setattr(codec_profiles, "probe_frame_size",
                        sonde_uniforme((320, 180)))
    monkeypatch.setattr(codec_profiles, "ensure_encoder_available",
                        lambda profile, ffmpeg_bin="ffmpeg": None)
    monkeypatch.setattr(
        codec_profiles, "verify_encoded_output",
        lambda chemin, **kwargs: (320, 180, "yuv422p10le"))

    vraie_fabrique = codec_profiles.build_encode_command

    def fabrique(profile_id, list_path, fps, output_path, **kwargs):
        temoins["progress_target"] = kwargs.get("progress_target")
        temoins["list_path"] = list_path
        # La vraie fabrique est appelee pour ses refus (extension, dimensions,
        # chemin deja present) : la doubler entierement les court-circuiterait.
        vraie_fabrique(profile_id, list_path, fps, output_path, **kwargs)
        return [sys.executable, "-c", FAUX_FFMPEG_QUI_PRODUIT,
                flux_mesure(*comptes), str(output_path), str(list_path)]

    monkeypatch.setattr(codec_profiles, "build_encode_command", fabrique)
    return espion, temoins


def test_AC_21_ter_les_DEUX_phases_comptent_et_le_compteur_REPART(
        tmp_path, monkeypatch):
    """**La suite complete des jalons d'un `run_encode`, en entier.**

    Trois frames, donc deux phases de trois : la sonde de formes (lot A) monte
    de 1 a 3, puis l'encodage (lot C) **repart de 1**. C'est ce que le dessin
    de `E4-4` attend -- la barre est par etape --, et c'est ce qu'un emetteur
    unique partage aurait rendu impossible : les trois jalons de l'encodage
    auraient ete `<= dernier` et seraient tombes en SILENCE.

    La suite est comparee en entier, jamais par son cardinal : deux phases de
    trois et une phase de six ont le meme nombre de jalons.
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    espion, temoins = _cabler_un_faux_encodage(
        monkeypatch, tmp_path, frames, comptes=(0, 1, 2, 3))

    codec_profiles.run_encode(
        "prores_hq", frames, 25, tmp_path / "master.mov",
        rappel_progression=espion)

    assert espion.jalons == [(1, 3), (2, 3), (3, 3),
                             (1, 3), (2, 3), (3, 3)], espion.jalons
    # La rupture est CONSTATEE plutot que tue : c'est le seul endroit du
    # produit ou `faites` decroit d'un jalon au suivant.
    ruptures = [rang for rang in range(1, len(espion.jalons))
                if espion.jalons[rang][0] <= espion.jalons[rang - 1][0]]
    assert ruptures == [3], ruptures


def test_AC_21_le_fichier_de_liste_concat_est_VIVANT_pendant_tout_le_process(
        tmp_path, monkeypatch):
    """Le `Popen` est attendu DANS le `with concat_list_file(...)`.

    Le faux ffmpeg sonde le chemin de la liste **au moment ou il tourne** et
    ecrit son verdict a cote du master. Un `with` referme avant l'attente
    laisserait ffmpeg lire un fichier efface -- panne qui ne se voit sur aucun
    encodage assez court pour finir avant la sortie du bloc.
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    espion, temoins = _cabler_un_faux_encodage(
        monkeypatch, tmp_path, frames, comptes=(0, 3))
    master = tmp_path / "master.mov"

    codec_profiles.run_encode("prores_hq", frames, 25, master,
                              rappel_progression=espion)

    sondes = list(tmp_path.glob("*.sonde"))
    assert len(sondes) == 1, sondes
    assert sondes[0].read_text() == "present"


def test_AC_5_ter_l_argv_ne_porte_progress_QUE_si_quelqu_un_ecoute(
        tmp_path, monkeypatch):
    """Repli `AR3` mesure sur le VRAI chemin, pas sur la seule fabrique.

    Deux regimes distinguables : avec rappel, la fabrique voit `pipe:1` ; sans
    rappel, elle voit `None` -- donc l'argv de production reste celui d'avant
    la story, au jeton pres.
    """
    for rappel, attendu in ((RappelEspion(), CIBLE_DE_PROGRESSION_ATTENDUE),
                            (None, None)):
        with monkeypatch.context() as contexte:
            racine = tmp_path / ("avec" if rappel else "sans")
            racine.mkdir()
            frames = fabrique_de_frames(racine, cardinal=3)
            _espion, temoins = _cabler_un_faux_encodage(
                contexte, racine, frames, comptes=(0, 3))
            codec_profiles.run_encode(
                "prores_hq", frames, 25, racine / "master.mov",
                rappel_progression=rappel)
            assert temoins["progress_target"] == attendu, temoins


def test_P1_la_cible_de_progression_vaut_LITTERALEMENT_pipe_1():
    """La constante centrale, mesuree contre un litteral et non contre soi.

    `test_AC_5_ter` ci-dessus tue deja la corruption en la faisant traverser la
    production. Celui-ci existe pour une autre raison : dire **pourquoi** une
    autre valeur est fausse, et le dire la ou quelqu'un qui voudrait changer la
    cible viendra lire.

    Le volet **negatif** est le seul des deux qui attrape la panne reelle. La
    valeur fautive plausible n'est pas n'importe quelle chaine : c'est
    `"pipe:2"`, la voisine d'un caractere. Elle coute deux fois, mesure sur
    ffmpeg 6.1.1 : `pipe:2` est `stderr`, donc **aucun octet** n'arrive au canal
    -- la barre reste figee sans qu'aucune erreur ne soit levee -- **et** les
    blocs de progression noient le diagnostic d'`EncodeRunError`, dont la
    fenetre ne garde que `[-600:]`. Une panne muette des deux cotes.

    Le fichier est exclu au meme titre, et pour un motif different de la
    docstring de la constante : il imposerait une scrutation a intervalle.
    """
    assert codec_profiles.PROGRESS_TARGET_STDOUT == CIBLE_DE_PROGRESSION_ATTENDUE

    # Volet negatif : aucune designation de `stderr` n'est acceptable.
    assert codec_profiles.PROGRESS_TARGET_STDOUT != "pipe:2"
    assert not codec_profiles.PROGRESS_TARGET_STDOUT.endswith(":2")
    # Ni un fichier, ni le tube d'entree.
    assert codec_profiles.PROGRESS_TARGET_STDOUT.startswith("pipe:")


# ---------------------------------------------------------------------------
# P3 -- l'ENTRELACEMENT, sur les deux sites d'emission
#
# Finding CRITIQUE, convergence des trois couches. Un jalon pose AVANT le
# travail qu'il annonce laisse la suite emise **rigoureusement identique** :
# la garde de monotonie de `EmetteurProgression` avale le doublon qui suit,
# si bien que `test_AC_21_ter` -- la frontiere de CONTENU la plus soignee du
# banc, six jalons plus l'indice de rupture -- reste verte.
#
# C'est la section 6.1 bis de la politique, mot pour mot : une frontiere de
# contenu est STRUCTURELLEMENT aveugle a l'avance quand le canal porte une
# garde de monotonie. Elle voit le retard, elle voit le manque, jamais
# l'avance. Seul l'entrelacement la tue -- le travail observe et le jalon
# ecrivent dans le MEME journal, et c'est leur alternance qui est mesuree.
# ---------------------------------------------------------------------------

def test_P3_site_1_le_jalon_de_la_SONDE_arrive_APRES_la_sonde(
        tmp_path, monkeypatch):
    """Site 1 : `ensure_uniform_frame_shapes`, `codec_profiles.py:1116`.

    La sonde et le rappel ecrivent dans le meme journal. L'alternance attendue
    est stricte : sonder, annoncer, sonder, annoncer -- jamais annoncer avant
    d'avoir sonde.

    **Trois frames aux noms distinguables, et le journal les nomme** (regle des
    fabriques, point 1) : un jalon annonce sur la MAUVAISE frame -- un decalage
    d'un rang, un compteur de boucle a la place du cardinal reel -- se voit
    dans le couple, la ou deux listes separees le laisseraient passer.
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    journal: list[tuple[str, object]] = []

    def sonde_qui_se_note(frame_path, *, ffprobe_bin="ffprobe"):
        journal.append(("sonde", Path(frame_path).name))
        return (320, 180)

    def rappel_qui_se_note(faites, total):
        journal.append(("jalon", faites))

    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_qui_se_note)

    codec_profiles.ensure_uniform_frame_shapes(
        frames, rappel_progression=rappel_qui_se_note)

    assert journal == [
        ("sonde", frames[0].name), ("jalon", 1),
        ("sonde", frames[1].name), ("jalon", 2),
        ("sonde", frames[2].name), ("jalon", 3),
    ], journal


def test_P3_site_1_bis_une_sequence_REFUSEE_n_annonce_rien(
        tmp_path, monkeypatch):
    """Le volet d'ABSENCE, et il est deja tenu -- il est mesure pour le rester.

    Le canal ne s'ouvre qu'apres le refus de sequence vide. Un jalon pose avant
    ce refus afficherait une tache commencee alors que rien n'a ete sonde :
    c'est la meme faute que ci-dessus, dans sa forme la plus grossiere.
    """
    journal: list[tuple[int, int]] = []

    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.ensure_uniform_frame_shapes(
            [], rappel_progression=lambda faites, total: journal.append(
                (faites, total)))

    assert journal == [], journal


def test_P3_site_2_le_jalon_du_FLUX_arrive_APRES_la_lecture_de_sa_ligne():
    """Site 2 : `_compter_sur_le_flux`, `codec_profiles.py:1747`.

    Meme aveuglement, meme remede. Le flux est un generateur qui se note en
    rendant chaque ligne ; le rappel se note en recevant chaque jalon. Un jalon
    pose avant la boucle serait absorbe par la monotonie et ne changerait pas
    la suite des jalons -- il change en revanche l'entrelacement, qui est ce
    qu'on mesure ici.

    **Le flux porte des lignes que la boucle NE compte PAS** -- `speed=`,
    `progress=continue` -- et elles sont INTERCALEES, jamais mises en queue
    (regle des fabriques, point 2 bis) : un site d'emission deplace hors du
    `if` produirait un jalon sur ces lignes-la, et le journal le montre a sa
    place exacte.
    """
    lignes = ["frame=1", "speed=1.0x", "frame=2", "progress=continue", "frame=3"]
    journal: list[tuple[str, object]] = []

    def flux_qui_se_note():
        for ligne in lignes:
            journal.append(("lue", ligne))
            yield ligne

    def rappel_qui_se_note(faites, total):
        journal.append(("jalon", faites))

    emetteur = progression.EmetteurProgression(rappel_qui_se_note, 3)
    codec_profiles._compter_sur_le_flux(flux_qui_se_note(), emetteur)

    assert journal == [
        ("lue", "frame=1"), ("jalon", 1),
        ("lue", "speed=1.0x"),
        ("lue", "frame=2"), ("jalon", 2),
        ("lue", "progress=continue"),
        ("lue", "frame=3"), ("jalon", 3),
    ], journal


# ---------------------------------------------------------------------------
# AC 9 et AC 24 -- la frontiere de PERIMETRE, sur le diff lui-meme
# ---------------------------------------------------------------------------

#: Le `baseline_commit` de la story 6.7, tel qu'il est ecrit dans le
#: frontmatter de sa fiche. Il est recopie ici plutot que relu, et c'est
#: assume : un test qui irait chercher son propre critere dans un document
#: editable mesurerait le document, pas le code.
BASELINE_DE_LA_STORY = "77319c849e9bb4a4432d0ce1b54cfeff78f5bb28"

#: **La BORNE HAUTE, et sans elle cette frontiere mordrait autrui** (finding
#: `P10` de la revue, trouve par les couches 1 et 3 independamment ; politique,
#: section 7).
#:
#: Une garde bornee **en bas seulement** ne mesure plus le diff de sa story : elle
#: mesure l'histoire du depot a partir d'un point. Le cout a ete mesure en
#: worktree jetable pendant la revue -- **les deux frontieres rougissent des le
#: premier commit ulterieur touchant `tui/`**, et cette branche est coupee
#: d'`oc/epic-11-TUI`, ou c'est imminent. Le precedent est litteral : la story
#: 5.16 a legue une garde non bornee qui a fait echouer la premiere story
#: suivante touchant un module de production, et 5.19 a du lui poser une borne
#: haute pour la rendre inoffensive sans rien lui faire perdre.
#:
#: `b94ea5dd` est le dernier commit du DEVELOPPEMENT de la story. Les commits de
#: FERMETURE de sa revue lui sont donc posterieurs et **ne sont pas couverts par
#: cette frontiere** : c'est voulu et c'est dit -- ils forment un diff de reprise
#: distinct, que la section 6.2 bis de la politique fait revoir a part.
BORNE_HAUTE_DE_LA_STORY = "b94ea5dd66afaf4feffdd991d90d112791af2481"


def _fichiers_du_diff(depuis: str, jusqu_a: str = BORNE_HAUTE_DE_LA_STORY) -> list[str]:
    """Les chemins modifies entre `depuis` et `jusqu_a`, ou un saut STRUCTUREL.

    Le saut n'est pas un drapeau qu'on oublierait de rallumer : sans git, ou
    sur un clone superficiel ou le commit de baseline est inconnu, il n'y a
    litteralement rien a comparer. C'est le motif exact que `CLAUDE.md` donne
    a la frontiere des politiques du depot.
    """
    racine = Path(__file__).resolve().parents[2]
    resultat = subprocess.run(
        ["git", "diff", "--name-only", f"{depuis}..{jusqu_a}"],
        cwd=racine, capture_output=True, text=True)
    if resultat.returncode != 0:
        pytest.skip(
            f"git indisponible, ou {depuis} / {jusqu_a} inconnu : {resultat.stderr}")
    return [ligne for ligne in resultat.stdout.splitlines() if ligne.strip()]


def test_AC_24_le_diff_de_la_story_ne_touche_AUCUN_fichier_de_tui():
    """**La frontiere de perimetre, et elle est negative par nature.**

    `EPIC11-ARB-184` a prepare la jonction pour qu'elle se fasse toute seule :
    `le_coeur_sait_compter` lit une SIGNATURE, si bien que le raccordement de
    cette story ne demande aucune ligne dans `tui/`. Une AC qui se contenterait
    de verifier que la jonction marche resterait verte si quelqu'un l'avait
    cablee a la main dans l'ecran -- ce qui casserait en meme temps l'AC 9.2 de
    la story 11.8, livree.

    L'ensemble des fichiers de `tui/` au diff est donc mesure comme
    **exactement vide**, jamais comme "peu nombreux".
    """
    touches = [chemin for chemin in _fichiers_du_diff(BASELINE_DE_LA_STORY)
               if chemin.startswith("src/mixed_media_utility/tui/")]
    assert touches == [], touches


def test_la_mesure_du_PERIMETRE_voit_bien_quelque_chose():
    """Volet symetrique, et il n'est pas de politesse.

    Si `git diff` ne rendait rien -- baseline egal a `HEAD`, arbre propre au
    mauvais endroit --, la frontiere ci-dessus serait verte sans rien observer.
    Les trois modules du canal DOIVENT sortir : ce sont eux que la story
    modifie, et leur absence signalerait que la mesure porte a cote.
    """
    modifies = set(_fichiers_du_diff(BASELINE_DE_LA_STORY))
    attendus = {"src/mixed_media_utility/codec_profiles.py",
                "src/mixed_media_utility/encode.py",
                "src/mixed_media_utility/encode_master.py"}
    assert attendus <= modifies, sorted(attendus - modifies)


#: Les deux SEULS bancs de `tui/` que cette story a le droit de toucher.
#:
#: `test_atelier_exports_execution.py` pour les deux frontieres retournees aux
#: AC 10 et 10 ter ; `test_coeur_en_processus.py` pour les motifs appendus a
#: `CHANGEMENTS_ACCEPTES`. Tout autre banc de `tui/` au diff signalerait que la
#: story a deborde sur un ecran.
BANCS_DE_TUI_AUTORISES = {
    "tests/unit/tui/test_atelier_exports_execution.py",
    "tests/unit/tui/test_coeur_en_processus.py",
}


def test_AC_24_bis_les_bancs_de_tui_touches_sont_EXACTEMENT_les_deux_attendus():
    """Le lot `B3` a quitte le perimetre avec `EPIC11-ARB-184`, et il y reste.

    **Corrige au finding `P19` de la revue.** Ce test mesurait auparavant
    `startswith("src/") and "/tui/" in c` -- c'est-a-dire **exactement le meme
    ensemble** que `test_AC_24` juste au-dessus, sous un autre nom et avec une
    docstring qui promettait autre chose. Un doublon strict n'ajoute aucune
    couverture : les deux rougissent et verdissent ensemble, et le second donne
    l'illusion d'une seconde mesure.

    La propriete qu'il annonce et qui, elle, est distincte : les bancs de `tui/`
    au diff sont **exactement** les deux attendus. `test_AC_24` interdit tout
    fichier de production de `tui/` ; celui-ci borne les **bancs**, que l'AC 24
    autorise sans les compter. Un banc d'ecran ajoute -- celui de `E4-4b`, par
    exemple -- passerait l'AC 24 et rougirait ici.

    L'ensemble est mesure comme **exact**, jamais comme une inclusion : c'est ce
    qui separe "je n'ai touche que ce qu'il fallait" de "j'ai touche au moins ce
    qu'il fallait".
    """
    bancs_de_tui = {chemin for chemin in _fichiers_du_diff(BASELINE_DE_LA_STORY)
                    if chemin.startswith("tests/") and "/tui/" in chemin}
    assert bancs_de_tui == BANCS_DE_TUI_AUTORISES, sorted(
        bancs_de_tui ^ BANCS_DE_TUI_AUTORISES)


# ---------------------------------------------------------------------------
# P4 / EC-1 / EC-4 -- l'absorption du canal s'arrete a l'ARRET DEMANDE
#
# Finding CRITIQUE de la couche 1 de la revue. `TerminaisonDemandee` derivait
# d'`Exception`, donc le `except Exception` de `_compter_sur_le_flux` l'avalait :
# canal actif, un `SIGTERM` rendait `rc=0` apres 6,0 s -- l'encodage allait au
# bout et la commande rendait un SUCCES -- la ou le repli `AR3` levait a 1,5 s.
# C'est la seconde moitie d'`EPIC7-ARB-79` : l'absorption ne couvre QUE le canal.
#
# **La premiere fermeture etait une garde LOCALE, et elle etait fausse deux
# fois** -- la couche de reprise (section 6.2 bis) l'a mesure :
#
# * `EC-1` : elle introduisait un `except ImportError: return False`, forme que
#   la frontiere de la story 8.4 interdit nommement au coeur. Mesure :
#   `test_contrat_de_dependances.py::test_le_coeur_ne_se_rabat_jamais_en_silence_sur_une_dependance_absente`
#   ROUGE des le premier commit de la reprise, et le seul verdict a differer sur
#   1 449 tests ;
# * `EC-4` : elle ne couvrait pas la fenetre du **rappel**. Le canal a un SECOND
#   absorbeur en amont -- `EmetteurProgression.emettre` --, si bien qu'un arret
#   tombant dans le rappel restait avale AUX DEUX SITES, le flux lu jusqu'au
#   bout et les trois frames sondees apres l'arret. Et le journal accusait le
#   rappel : le diagnostic exactement faux.
#
# Le remede est la CLASSE DE BASE, pas une garde par site : `TerminaisonDemandee`
# derive desormais de `BaseException` comme `KeyboardInterrupt`, donc aucun
# `except Exception` du depot ne la voit -- y compris celui de `progression.py`,
# que cette story n'a pas le droit de toucher.
# ---------------------------------------------------------------------------

def test_l_arret_demande_derive_de_BaseException_et_PAS_d_Exception():
    """La frontiere qui tient tout le reste, et son volet negatif.

    `EC-1` et `EC-4` sont fermes par une seule propriete : un arret demande
    n'est pas une `Exception`. Une regression qui la remettrait sous `Exception`
    -- par confort, ou parce que "toutes nos erreurs derivent d'`Exception`" --
    reouvrirait les deux d'un coup, et **sans faire rougir aucun des tests de
    traversee ci-dessous**, qui passeraient alors par la garde... qui n'existe
    plus. C'est pourquoi elle se mesure ici, en propre.

    Le volet negatif est mesure sur le **comportement**, pas seulement sur la
    hierarchie : un `except Exception` nu ne doit pas la voir passer. Une
    assertion de sous-typage seule laisserait croire que la propriete est tenue
    alors qu'elle porte sur ce que le code fait, pas sur ce qu'il declare.
    """
    assert issubclass(encode_master.TerminaisonDemandee, BaseException)
    assert not issubclass(encode_master.TerminaisonDemandee, Exception)

    vu = None
    try:
        try:
            raise encode_master.TerminaisonDemandee("signal 15")
        except Exception as erreur:  # noqa: BLE001 -- c'est LA mesure
            vu = erreur
    except encode_master.TerminaisonDemandee:
        pass
    assert vu is None, vu

    # `KeyboardInterrupt` a toujours eu ce regime : c'est le modele, et le
    # citer ici evite qu'on croie a une singularite de ce module.
    assert not issubclass(KeyboardInterrupt, Exception)


def test_EC_4_site_2_un_arret_demande_DANS_LE_RAPPEL_traverse_le_flux():
    """**La fenetre que la garde locale ne couvrait pas**, site du flux.

    Le signal est levee par un gestionnaire qui leve dans le fil principal : il
    peut donc tomber pendant le rappel aussi bien que pendant la lecture. Avant
    la classe de base, `EmetteurProgression.emettre` l'avalait, journalisait
    "le rappel de progression a leve" -- le diagnostic exactement faux -- et la
    lecture reprenait.

    **Le flux compte ses tours**, et c'est ce qui separe "traverse" de "traverse
    apres avoir tout lu" : trois lignes `frame=` sont disponibles, l'arret tombe
    sur la premiere, et le flux ne doit pas etre parcouru au-dela.
    """
    lignes = ["frame=1", "frame=2", "frame=3"]
    tours = []

    def flux_qui_compte():
        for ligne in lignes:
            tours.append(ligne)
            yield ligne

    def rappel_qui_recoit_le_signal(faites, total):
        raise encode_master.TerminaisonDemandee("signal 15")

    emetteur = progression.EmetteurProgression(rappel_qui_recoit_le_signal, 3)

    with pytest.raises(encode_master.TerminaisonDemandee):
        codec_profiles._compter_sur_le_flux(flux_qui_compte(), emetteur)

    assert tours == ["frame=1"], tours


def test_EC_4_site_1_un_arret_demande_DANS_LE_RAPPEL_traverse_la_SONDE(
        tmp_path, monkeypatch):
    """Meme fenetre, site de la sonde de formes -- et il n'est pas redondant.

    `ensure_uniform_frame_shapes` a son propre emetteur, donc son propre
    absorbeur en amont. La mesure de la couche de reprise y etait la plus
    parlante : les **trois** frames etaient sondees APRES l'arret demande.

    **Trois frames aux noms distinguables, et l'arret tombe sur la premiere** :
    le journal des sondes dit exactement ou le parcours s'est arrete, la ou un
    simple `pytest.raises` ne dirait que "ca a leve".
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    sondees: list[str] = []

    def sonde_qui_se_note(frame_path, *, ffprobe_bin="ffprobe"):
        sondees.append(Path(frame_path).name)
        return (320, 180)

    def rappel_qui_recoit_le_signal(faites, total):
        raise encode_master.TerminaisonDemandee("signal 15")

    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_qui_se_note)

    with pytest.raises(encode_master.TerminaisonDemandee):
        codec_profiles.ensure_uniform_frame_shapes(
            frames, rappel_progression=rappel_qui_recoit_le_signal)

    assert sondees == [frames[0].name], sondees


def test_EC_4_ter_une_panne_ORDINAIRE_du_rappel_reste_absorbee(
        tmp_path, monkeypatch):
    """Le volet symetrique, et sans lui les deux precedents ne prouvent rien.

    Si `emettre` avait cesse d'absorber **quoi que ce soit**, les deux tests
    ci-dessus seraient verts pour la mauvaise raison -- et le canal cesserait
    d'etre observationnel, ce qu'`EPIC7-ARB-79` interdit dans son autre moitie.

    Un rappel qui leve une erreur ORDINAIRE ne casse donc rien : les trois
    frames sont sondees, et la fonction rend sa forme.
    """
    frames = fabrique_de_frames(tmp_path, cardinal=3)
    sondees: list[str] = []

    def sonde_qui_se_note(frame_path, *, ffprobe_bin="ffprobe"):
        sondees.append(Path(frame_path).name)
        return (320, 180)

    def rappel_qui_casse(faites, total):
        raise RuntimeError("panne ordinaire du consommateur")

    monkeypatch.setattr(codec_profiles, "probe_frame_size", sonde_qui_se_note)

    assert codec_profiles.ensure_uniform_frame_shapes(
        frames, rappel_progression=rappel_qui_casse) == (320, 180)
    assert sondees == [frame.name for frame in frames], sondees


# ---------------------------------------------------------------------------
# P4 -- l'absorption du canal s'arrete a l'ARRET DEMANDE
#
# Finding CRITIQUE de la couche 1 de la revue. `TerminaisonDemandee` derive
# d'`Exception`, donc le `except Exception` de `_compter_sur_le_flux` l'avalait :
# canal actif, un `SIGTERM` rendait `rc=0` apres 6,0 s -- l'encodage allait au
# bout et la commande rendait un SUCCES -- la ou le repli `AR3` levait a 1,5 s.
# C'est la seconde moitie d'`EPIC7-ARB-79` : l'absorption ne couvre QUE le canal.
# ---------------------------------------------------------------------------

class FluxQuiLeve:
    """Un flux qui rend `lignes_avant`, puis leve `erreur` -- puis `erreur_au_vidage`.

    Deux leviers distincts, parce que la garde a **deux** portes : celle du
    parcours, et celle du vidage qui suit l'absorption. Une garde posee sur la
    premiere seule serait contournable par la seconde -- il suffirait que le
    signal arrive quelques millisecondes plus tard.

    `tours` compte les iterations reellement demandees : c'est lui qui distingue
    "le vidage a eu lieu" de "le vidage a ete saute", que le seul verdict de
    l'exception ne dirait pas.

    **`videes` dit jusqu'ou le vidage est alle, et `tours` ne le disait pas**
    (finding `EC-3` de la couche de reprise). Un vidage qui s'arreterait a la
    premiere ligne incremente `tours` exactement comme un vidage complet -- et
    c'est la panne qui compte, puisqu'un tube qu'on cesse de lire bloque le
    producteur des 64 Kio, sans plafond pour l'en sortir. Le verdict porte donc
    sur la LISTE des lignes consommees au vidage, jamais sur un compteur.
    """

    def __init__(self, erreur, *, lignes_avant=(), erreur_au_vidage=None,
                 lignes_au_vidage=()):
        self.erreur = erreur
        self.lignes_avant = list(lignes_avant)
        self.erreur_au_vidage = erreur_au_vidage
        self.lignes_au_vidage = list(lignes_au_vidage)
        self.tours = 0
        self.videes: list[str] = []

    def __iter__(self):
        self.tours += 1
        premier = self.tours == 1
        for ligne in self.lignes_avant if premier else ():
            yield ligne
        if premier:
            raise self.erreur
        for ligne in self.lignes_au_vidage:
            self.videes.append(ligne)
            yield ligne
        if self.erreur_au_vidage is not None:
            raise self.erreur_au_vidage


def _emetteur_espion(total=3):
    espion = RappelEspion()
    return espion, progression.EmetteurProgression(espion, total)


def test_P4_un_ARRET_DEMANDE_pendant_la_lecture_TRAVERSE_le_canal():
    """`SIGTERM` n'est pas une panne du canal : il ne s'absorbe pas.

    Le gestionnaire de `encode_master.le_signal_tue_l_encodeur` leve
    `TerminaisonDemandee` **dans le fil principal**, donc au milieu de cette
    boucle, sans rien avoir a voir avec elle. L'absorber faisait rendre un
    succes a un encodage que l'operateur venait d'arreter.

    Le jalon deja emis avant l'arret est verifie present : la garde laisse
    passer l'exception, elle ne defait pas le travail deja observe.
    """
    espion, emetteur = _emetteur_espion()
    flux = FluxQuiLeve(encode_master.TerminaisonDemandee("signal 15"),
                       lignes_avant=["frame=1\n"])

    with pytest.raises(encode_master.TerminaisonDemandee):
        codec_profiles._compter_sur_le_flux(flux, emetteur)

    assert espion.jalons == [(1, 3)], espion.jalons
    assert flux.tours == 1, "le vidage ne doit PAS avoir eu lieu"


def test_P4_bis_un_ARRET_DEMANDE_pendant_le_VIDAGE_traverse_AUSSI():
    """La seconde porte, sans laquelle la premiere est contournable.

    Le canal absorbe une panne de lecture, puis vide le tube. Si le `SIGTERM`
    arrive **pendant** ce vidage, une garde posee sur le seul parcours le
    laisserait passer a la trappe -- et la fenetre serait d'autant plus large
    que le vidage dure autant que l'encodage restant.

    `tours == 2` etablit que le vidage a bien ete tente : sans lui, ce test
    serait vert pour la mauvaise raison.
    """
    espion, emetteur = _emetteur_espion()
    flux = FluxQuiLeve(
        RuntimeError("le tube a hoquete"),
        lignes_avant=["frame=1\n"],
        erreur_au_vidage=encode_master.TerminaisonDemandee("signal 15"))

    with pytest.raises(encode_master.TerminaisonDemandee):
        codec_profiles._compter_sur_le_flux(flux, emetteur)

    assert flux.tours == 2, "le vidage doit avoir ete tente"


def test_P4_ter_une_panne_du_CANAL_reste_absorbee_et_le_tube_est_VIDE(caplog):
    """Le volet symetrique, et il est la moitie qui compte.

    Sans lui, la fermeture de `P4` serait indiscernable d'un "on ne rattrape
    plus rien", qui casserait la PREMIERE moitie d'`EPIC7-ARB-79`. Une panne du
    canal -- ici un tube qui hoquete -- s'absorbe toujours, se journalise, et le
    vidage a lieu pour ne pas bloquer le producteur.
    """
    espion, emetteur = _emetteur_espion()
    flux = FluxQuiLeve(RuntimeError("le tube a hoquete"),
                       lignes_avant=["frame=1\n", "frame=2\n"])

    with caplog.at_level("WARNING", logger=codec_profiles.__name__):
        codec_profiles._compter_sur_le_flux(flux, emetteur)  # ne leve pas

    assert espion.jalons == [(1, 3), (2, 3)], espion.jalons
    assert flux.tours == 2, "le tube doit avoir ete vide"
    assert len(caplog.records) == 1, [r.message for r in caplog.records]


def test_EC_3_le_vidage_va_jusqu_au_BOUT_du_tube_et_pas_a_la_premiere_ligne():
    """**Le vidage est mesure sur ce qu'il consomme, plus sur un compteur.**

    Finding `EC-3` de la couche de reprise : `assert flux.tours == 2`
    n'etablissait que "le vidage a ete ENTAME". Un vidage qui s'arrete a la
    premiere ligne -- un `break`, un `next()` au lieu d'une boucle -- rend le
    meme compteur et rouvre exactement la panne que le vidage existe pour
    ecarter : ffmpeg se bloque en ecriture au 64e Kio, et la couture attend un
    processus qui n'avancera plus. **Elle ne rougit pas, elle suspend.**

    **Quatre lignes au vidage, distinguables et comparees en entier** (regle des
    fabriques, point 1) : deux lignes suffiraient a distinguer "une" de "toutes"
    mais pas a voir une lecture qui saute, et une liste comparee en entier voit
    aussi l'ordre.
    """
    espion, emetteur = _emetteur_espion()
    reste = ["frame=3\n", "speed=1.0x\n", "frame=4\n", "progress=end\n"]
    flux = FluxQuiLeve(RuntimeError("le tube a hoquete"),
                       lignes_avant=["frame=1\n", "frame=2\n"],
                       lignes_au_vidage=reste)

    codec_profiles._compter_sur_le_flux(flux, emetteur)  # ne leve pas

    assert flux.videes == reste, flux.videes
    # Et le vidage n'ANALYSE plus : aucune des lignes videes n'a produit de
    # jalon, alors que deux d'entre elles portent un `frame=` parfaitement
    # lisible. C'est ce qui separe "vider" de "reprendre le comptage".
    assert espion.jalons == [(1, 3), (2, 3)], espion.jalons


def test_EC_3_bis_une_panne_PENDANT_le_vidage_reste_absorbee():
    """L'autre mutant survivant d'`EC-3` : un vidage qui re-leverait tout.

    Le vidage s'exerce sur un tube deja casse -- c'est pour ca qu'il existe.
    S'il propageait ce qu'il rencontre, la premiere moitie d'`EPIC7-ARB-79`
    tomberait : l'observation casserait l'observe, et pour une panne du canal,
    pas pour un arret demande.

    La frontiere est etroite et c'est voulu : une erreur ORDINAIRE au vidage est
    absorbee, un ARRET DEMANDE au vidage traverse (`test_P4_bis`). Les deux
    ensemble disent ou passe la ligne ; l'un sans l'autre ne dit rien.
    """
    espion, emetteur = _emetteur_espion()
    flux = FluxQuiLeve(RuntimeError("le tube a hoquete"),
                       lignes_avant=["frame=1\n"],
                       lignes_au_vidage=["frame=2\n"],
                       erreur_au_vidage=RuntimeError("et le tube est rompu"))

    codec_profiles._compter_sur_le_flux(flux, emetteur)  # ne leve pas

    assert flux.videes == ["frame=2\n"], flux.videes
    assert espion.jalons == [(1, 3)], espion.jalons


def test_P4_quater_une_INTERRUPTION_CLAVIER_traverse_elle_aussi():
    """`KeyboardInterrupt` derive de `BaseException`, donc aucun `except
    Exception` ne la voit -- mais le mesurer plutot que le supposer est ce qui
    empeche qu'un elargissement futur du `except` la fasse disparaitre en
    silence. C'est une frontiere de non-regression, pas une redondance.
    """
    espion, emetteur = _emetteur_espion()
    flux = FluxQuiLeve(KeyboardInterrupt(), lignes_avant=["frame=1\n"])

    with pytest.raises(KeyboardInterrupt):
        codec_profiles._compter_sur_le_flux(flux, emetteur)

    assert flux.tours == 1, "le vidage ne doit PAS avoir eu lieu"
