"""Tagage colorimetrique a l'encodage: le maillon `setparams` et le releve de version.

Ce banc existe pour une regression de terrain du 2026-09-06. Un master
ProRes/DNxHD/H.264 produit sous **FFmpeg 8** sortait en `color_space=bt709`
avec `color_primaries` et `color_transfer` **non renseignes**, et la garde
`verify_technical_metadata` le refusait en `VERIFICATION_TECHNIQUE_EN_ECHEC`.

**La garde avait raison** -- le fichier etait reellement mal tague. La cause
n'etait ni la lecture ni la garde, mais un renversement de comportement de
ffmpeg entre les versions 6 et 8: `-color_primaries` et `-color_trc`
n'atteignent plus l'encodeur, seul le cote **frame** du filtergraph compte.
Mesure complete: `codec_profiles.FFMPEG_COLOR_TAGGING_MEASUREMENT`.

CE QUE CE BANC PEUT ET NE PEUT PAS, DIT PLUTOT QUE TU
=====================================================

Le drapeau dont depend la panne est **la version de ffmpeg**, et aucun banc
ordinaire ne peut le faire varier: le conteneur porte un binaire, un seul. Sous
6.1.1, la **verification technique** rend le meme verdict avec et sans le
maillon `setparams` -- mesure du 2026-09-06, les 7 profils verts des deux cotes
-- parce que les options CLI suffisent a taguer le conteneur sur cette
version-la.

Donc: **aucune assertion portant sur ce que `read_technical_metadata` relit ne
peut distinguer le code d'avant du code d'apres sous 6.1.1.** Les bancs de
`test_video_metadata.py` restent verts sur le code d'avant, verifie en le
mutant; le pretendre autrement serait faux.

Ce banc tient donc deux choses:

* des **frontieres sur l'argv et sur la chaine de filtres**, qui rougissent si
  le maillon disparait, quelle que soit la version installee. C'est le pendant
  de la regle du depot « une garde qui ne fait varier aucun de ses drapeaux ne
  mesure qu'un seul chemin »: le drapeau etant hors d'atteinte, on mesure la
  **cause** au lieu de l'effet;
* **une frontiere sur un fichier reellement encode qui, elle, mord des
  6.1.1**: l'en-tete de frame ProRes. Elle a ete trouvee en cherchant a prouver
  que le maillon ne degradait rien, et elle etablit l'inverse de ce qu'on
  cherchait -- voir `test_l_entete_de_frame_prores_porte_les_trois_champs`.

La mesure sous FFmpeg 8.1.2 est reportee en toutes lettres dans
`FFMPEG_COLOR_TAGGING_MEASUREMENT` avec ses cardinaux.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mixed_media_utility import codec_profiles

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="binaire ffmpeg absent du PATH"
)

TOUS_LES_PROFILS = sorted(codec_profiles.PROFILES)


# --------------------------------------------------------------------------
# Le maillon dans la chaine de filtres
# --------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", TOUS_LES_PROFILS)
def test_la_chaine_porte_le_maillon_setparams_sur_les_sept_profils(profile_id) -> None:
    """Frontiere **negative**: retirer le maillon fait rougir ce banc.

    C'est la seule facon d'attraper la reintroduction du defaut: aucun banc
    positif joue sous 6.1.1 ne verrait revenir une chaine sans `setparams`,
    puisque le fichier produit resterait conforme sous cette version.
    """
    profile = codec_profiles.get_profile(profile_id)
    chaine = codec_profiles.build_filter_chain(profile)
    assert "setparams=" in chaine, chaine
    # Et il vient **apres** le scale: `setparams` marque la frame telle qu'elle
    # sort de la conversion, pas telle qu'elle y entre.
    assert chaine.index("scale=") < chaine.index("setparams="), chaine


@pytest.mark.parametrize("profile_id", TOUS_LES_PROFILS)
def test_le_maillon_porte_les_trois_proprietes_et_la_plage(profile_id) -> None:
    """Les trois champs qui cassent, plus la plage, tous nommes explicitement.

    Poser deux des trois suffirait a laisser passer exactement la panne du
    terrain -- elle portait sur deux champs sur trois.
    """
    profile = codec_profiles.get_profile(profile_id)
    chaine = codec_profiles.build_filter_chain(profile)
    maillon = chaine.split("setparams=", 1)[1]
    options = dict(paire.split("=", 1) for paire in maillon.split(":"))
    assert options == {
        "color_primaries": profile.colorspace,
        "color_trc": profile.colorspace,
        "colorspace": profile.colorspace,
        "range": codec_profiles.OUTPUT_COLOR_RANGE,
    }, chaine


def test_le_maillon_suit_le_profil_et_ne_code_aucune_valeur_en_dur() -> None:
    """Une valeur en dur ferait diverger le tag de la matrice reellement
    appliquee -- c'est-a-dire un master **tague `bt709` sans avoir subi la
    conversion `bt709`**, exactement le defaut a 40,33/255 que la story 6.0
    existe pour supprimer, mais retourne cote tag.

    Le drapeau varie ici: deux valeurs distinctes de `colorspace`, et le
    maillon doit suivre les deux (regle des fabriques -- une garde qui ne fait
    varier aucun de ses drapeaux ne mesure qu'un seul chemin).
    """
    assert codec_profiles.build_setparams_link("smpte170m") == (
        "setparams=color_primaries=smpte170m:color_trc=smpte170m"
        ":colorspace=smpte170m:range=tv"
    )
    assert codec_profiles.build_setparams_link("smpte240m") == (
        "setparams=color_primaries=smpte240m:color_trc=smpte240m"
        ":colorspace=smpte240m:range=tv"
    )


def test_le_redimensionnement_ne_chasse_pas_le_maillon() -> None:
    """`target_size` empruntait une branche de retour **distincte**, qui rendait
    la chaine sans passer par la fin de la fonction.

    C'est le chemin de la story 6.1, donc celui de tout master redimensionne:
    un maillon pose seulement sur la branche sans redimensionnement aurait
    laisse les masters mis a l'echelle -- le cas nominal -- non tagues sous
    FFmpeg 8.
    """
    profile = codec_profiles.get_profile("prores_hq")
    avec = codec_profiles.build_filter_chain(profile, (1920, 1080))
    assert avec.startswith("scale=1920:1080:")
    assert avec.endswith(codec_profiles.build_setparams_link(profile.colorspace))
    # Les deux branches ne different que par la geometrie.
    sans = codec_profiles.build_filter_chain(profile)
    assert avec.replace("1920:1080:", "") == sans


@pytest.mark.parametrize("profile_id", TOUS_LES_PROFILS)
def test_l_argv_reellement_construit_porte_le_maillon(profile_id, tmp_path) -> None:
    """La chaine est une chose, l'argv en est une autre.

    `_FACTORY_OWNED_OPTIONS` interdit `-vf` dans les `extra_args` d'un profil,
    donc le maillon **doit** venir de `build_filter_chain`. Ce banc verifie
    qu'il arrive bien jusqu'a la ligne de commande, et qu'il y arrive une seule
    fois: un doublon de `-vf` ferait gagner le dernier en silence.
    """
    profile = codec_profiles.get_profile(profile_id)
    liste = tmp_path / "frames.concat"
    liste.write_text("file 'a.tiff'\n", encoding="utf-8")
    argv = codec_profiles.build_encode_command(
        profile_id, str(liste), 24.0, str(tmp_path / f"m.{profile.container}")
    )
    assert argv.count("-vf") == 1, argv
    chaine = argv[argv.index("-vf") + 1]
    assert "setparams=" in chaine, argv
    # Les trois options CLI restent posees: elles sont necessaires sous
    # FFmpeg <= 7 et ne contredisent jamais le maillon, puisque les deux
    # gestes derivent du meme champ de profil.
    for option in ("-colorspace", "-color_primaries", "-color_trc"):
        assert argv[argv.index(option) + 1] == profile.colorspace, argv


# --------------------------------------------------------------------------
# Le cinquieme vocabulaire
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_usable_color_matrices_est_accepte_par_le_vocabulaire_setparams() -> None:
    """`setparams` est le **cinquieme** consommateur du champ `colorspace`.

    Les quatre precedents (`out_color_matrix`, `-colorspace`,
    `-color_primaries`, `-color_trc`) ont ete mesures le 2026-08-10 et leur
    intersection **est** `USABLE_COLOR_MATRICES`. Les vocabulaires ne
    coincidant pas d'un consommateur a l'autre, un cinquieme ne peut pas etre
    suppose compatible: il se mesure.

    Mesure ici contre le binaire installe plutot que contre une liste recopiee,
    de sorte qu'une version future qui **retirerait** une valeur fasse rougir
    ce banc au lieu de casser un encodage chez l'operateur.
    """
    aide = subprocess.run(
        ["ffmpeg", "-hide_banner", "-h", "filter=setparams"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert aide.returncode == 0, aide.stderr

    # La sortie est un bloc par option: `   <nom>  <type>  ...` puis ses valeurs
    # indentees plus profond. On decoupe sur les trois options qui nous servent.
    vocabulaires: dict[str, set[str]] = {}
    option_courante: str | None = None
    for ligne in (aide.stdout or "").splitlines():
        nu = ligne.strip()
        if not nu:
            continue
        tete = nu.split()[0]
        if tete in ("color_primaries", "color_trc", "colorspace", "range", "field_mode"):
            option_courante = tete
            vocabulaires.setdefault(tete, set())
        elif option_courante is not None and ligne.startswith("     "):
            vocabulaires[option_courante].add(tete)

    trois = ("color_primaries", "color_trc", "colorspace")
    for nom in trois:
        assert vocabulaires.get(nom), f"vocabulaire {nom} illisible dans -h filter=setparams"

    intersection = set.intersection(*(vocabulaires[nom] for nom in trois))
    manquantes = codec_profiles.USABLE_COLOR_MATRICES - intersection
    assert not manquantes, (
        f"{sorted(manquantes)} n'est plus accepte par les trois options de setparams "
        f"sur ce ffmpeg. Intersection mesuree: {sorted(intersection)}"
    )
    # La plage posee par la chaine doit l'etre aussi -- elle passe par le meme
    # maillon et echouerait de la meme facon.
    assert codec_profiles.OUTPUT_COLOR_RANGE in vocabulaires["range"]


@requires_ffmpeg
@pytest.mark.parametrize("valeur", sorted(codec_profiles.USABLE_COLOR_MATRICES))
def test_le_maillon_est_reellement_accepte_a_l_encodage(valeur, tmp_path) -> None:
    """Frontiere positive, et elle ne fait pas double emploi avec la precedente.

    `-h filter=setparams` est une **declaration**; un encodage est une mesure.
    Le depot a deja paye la difference: `scale=out_color_matrix` accepte les 15
    candidats a l'analyse et en refuse 12 a l'encodage.
    """
    sortie = tmp_path / "essai.mp4"
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=160x90:rate=5:duration=0.4",
         "-vf", f"scale=out_color_matrix={valeur}:out_range=tv,"
                + codec_profiles.build_setparams_link(valeur),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "40", str(sortie)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert resultat.returncode == 0, resultat.stderr
    assert sortie.stat().st_size > 0


@requires_ffmpeg
@pytest.mark.parametrize("valeur", ["bt2020nc", "bt601", "linear", "iec61966-2-1"])
def test_setparams_refuse_franchement_hors_de_son_vocabulaire(valeur, tmp_path) -> None:
    """Ce qui distingue `setparams` de `scale`, et pourquoi le cinquieme
    vocabulaire est une garde plutot qu'une declaration.

    `scale=out_color_matrix=bt2020nc` rend `rc=0` en ignorant la valeur en
    silence -- c'est le defaut qui avait laisse passer `bt2020nc` dans une
    version precedente de `USABLE_COLOR_MATRICES`. `setparams`, lui, echoue.

    Les quatre valeurs choisies sont exactement celles que la mesure du
    2026-08-10 avait piegees: chacune est acceptee par **au moins un** des
    quatre premiers vocabulaires, et par aucun des trois de `setparams`.
    """
    assert valeur not in codec_profiles.USABLE_COLOR_MATRICES
    resultat = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=160x90:rate=5:duration=0.4",
         "-vf", codec_profiles.build_setparams_link(valeur),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "40",
         str(tmp_path / "refus.mp4")],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert resultat.returncode != 0, "setparams a accepte une valeur hors vocabulaire"


# --------------------------------------------------------------------------
# Le releve de version
# --------------------------------------------------------------------------


@requires_ffmpeg
def test_la_version_relevee_nomme_le_binaire_et_ses_bibliotheques() -> None:
    """Le releve doit etre **comparable a l'oeil** entre deux machines.

    Egan a rapporte sa version en `Lavf62.6.103 / Lavc62.19.100`: c'est dans ce
    vocabulaire qu'une version de ffmpeg se nomme sur le terrain, et c'est ce
    qui a permis de dater son binaire. Un releve qui ne porterait que `8.1.2`
    perdrait la moitie de l'information.
    """
    releve = codec_profiles.probe_tool_version("ffmpeg")
    assert releve != codec_profiles.TOOL_VERSION_UNKNOWN
    for bibliotheque in ("libavcodec", "libavformat", "libavutil"):
        assert bibliotheque in releve, releve


def test_le_releve_de_version_ne_leve_jamais() -> None:
    """Frontiere **negative**, et elle porte le motif entier de ce choix.

    Ce releve est lu depuis un chemin d'erreur -- le rapport de
    `VERIFICATION_TECHNIQUE_EN_ECHEC`. Une sonde qui leverait y remplacerait
    l'erreur en cours par la sienne, c'est-a-dire ferait disparaitre la panne
    qu'elle etait censee documenter. C'est la lecon du `finally` de
    `run_encode`, appliquee a un temoin.

    Trois regimes de panne, et aucun ne doit lever: binaire absent du PATH,
    binaire qui rend un code non nul, binaire qui rend 0 sans ligne de version.
    """
    assert (
        codec_profiles.probe_tool_version("ffmpeg-qui-n-existe-pas-du-tout")
        == codec_profiles.TOOL_VERSION_UNKNOWN
    )
    if shutil.which("false"):
        assert (
            codec_profiles.probe_tool_version("false")
            == codec_profiles.TOOL_VERSION_UNKNOWN
        )
    if shutil.which("true"):
        # rc=0, sortie vide: nommer une version inventee serait pire que le trou.
        assert (
            codec_profiles.probe_tool_version("true")
            == codec_profiles.TOOL_VERSION_UNKNOWN
        )


def test_un_binaire_QUI_SUSPEND_ne_suspend_pas_le_releve() -> None:
    """Quatrieme regime de panne, et c'est le seul qui ne rend jamais la main.

    Pose le 2026-09-07 sur le finding T6 de la couche 3. Les trois regimes du
    banc ci-dessus rendent tous **quelque chose**, meme mauvais ; un binaire qui
    suspend ne rend rien du tout, et sans plafond il emporte l'encodage entier
    avec lui. Le regime exact ou ca mord est le pire possible : `probe_tool_version`
    est lu depuis le **chemin de refus**, donc une suspension y gele le message
    qui devait decrire la panne -- c'est-a-dire exactement le symptome
    « l'encodage ne s'acheve jamais » que le terrain a remonte le 2026-09-06,
    reintroduit par la sonde censee le diagnostiquer.

    **Frontiere de DUREE, pas seulement de valeur.** Verifier que la fonction
    rend `TOOL_VERSION_UNKNOWN` ne suffirait pas : sans plafond, elle ne rend
    rien et le test suspendrait au lieu de rougir -- une suite qui suspend ne
    nomme aucun coupable. Le banc mesure donc le **temps ecoule**, borne bien
    au-dessus du plafond de 5 s pour ne pas devenir sensible a la charge de la
    machine, et bien en dessous de l'infini qu'un defaut produirait.
    """
    faux_binaire = shutil.which("sleep")
    if faux_binaire is None:
        pytest.skip("pas de `sleep` dans ce conteneur")

    # `sleep -version` n'est pas une option connue de `sleep`, mais peu importe :
    # ce qui compte est qu'il ne rende pas la main tout de suite. GNU sleep sans
    # operande valide sort immediatement, donc on passe par un shell qui dort.
    shell = shutil.which("sh")
    if shell is None:
        pytest.skip("pas de `sh` dans ce conteneur")

    with tempfile.TemporaryDirectory() as dossier:
        dormeur = Path(dossier) / "ffmpeg-qui-suspend"
        dormeur.write_text("#!/bin/sh\nsleep 300\n", encoding="utf-8")
        dormeur.chmod(0o755)

        # Le cache est clef sur le nom du binaire : un chemin neuf a chaque
        # course, donc aucune valeur de la course precedente ne peut repondre.
        depart = time.monotonic()
        verdict = codec_profiles.probe_tool_version(str(dormeur))
        ecoule = time.monotonic() - depart

    assert verdict == codec_profiles.TOOL_VERSION_UNKNOWN, (
        "un binaire qui suspend doit rendre le temoin d'inconnu, comme les "
        "trois autres regimes de panne"
    )
    assert ecoule < 60, (
        f"le releve a mis {ecoule:.1f} s : le plafond de `subprocess.run` ne "
        f"joue pas, et un ffmpeg qui suspend gelerait l'encodage entier"
    )


def test_un_ECHEC_de_releve_n_est_PAS_memorise_pour_la_vie_du_processus() -> None:
    """Le drapeau qu'aucun banc ne faisait varier : le binaire apparait ENTRE deux appels.

    Le premier jet posait un `lru_cache` sur cette sonde. Comme elle **rend**
    un temoin d'echec au lieu de lever, l'echec etait memorise -- et le module
    explique trente lignes plus haut, sur mesure d'un incident reel
    (`available_encoders`), pourquoi c'est faux : « lever plutot que rendre est
    aussi ce qui protege le cache ».

    Le regime ou ca mord est celui de l'Epic 11, et il n'est pas theorique : la
    TUI est un processus **long**. `PATH` incomplet au demarrage, `ffmpeg`
    installe ensuite, binaire remplace -- et toute la session estampille
    « version indeterminee » sur des masters produits par un ffmpeg
    parfaitement identifiable. Le temoin que ce releve existe pour poser
    s'eteint alors en silence, ce qui est pire que de ne pas l'avoir.

    Le banc fait donc varier l'existence du binaire **dans les deux sens**,
    entre deux appels, ce qu'aucun banc ne faisait -- c'est la regle du
    2026-09-06 sur les gardes qui ne jouent qu'un seul cote de leur drapeau.
    """
    with tempfile.TemporaryDirectory() as dossier:
        faux = Path(dossier) / "ffmpeg-qui-arrive-en-retard"

        # 1. Absent : la sonde rend le temoin d'inconnu.
        assert codec_profiles.probe_tool_version(str(faux)) == \
            codec_profiles.TOOL_VERSION_UNKNOWN

        # 2. Il apparait. Un echec memorise rendrait encore « indetermine ».
        faux.write_text(
            "#!/bin/sh\n"
            "echo 'ffmpeg version 9.9.9-arrive-en-retard Copyright (c) the FFmpeg developers'\n",
            encoding="utf-8")
        faux.chmod(0o755)

        second = codec_profiles.probe_tool_version(str(faux))

    assert second != codec_profiles.TOOL_VERSION_UNKNOWN, (
        "l'echec du premier appel a ete memorise : toute la session portera"
        " « version indeterminee » sur des masters dont le ffmpeg est pourtant"
        " parfaitement identifiable")
    assert "9.9.9" in second, second


def test_un_binaire_qui_rend_un_CODE_NON_NUL_avec_une_sortie_LISIBLE() -> None:
    """La garde de code de retour, qu'aucun banc n'exercait reellement.

    `test_le_releve_de_version_ne_leve_jamais` annonce trois regimes de panne,
    dont « binaire qui rend un code non nul ». Il le joue avec `false` -- dont
    la sortie est **vide**. Les deux derniers regimes rendaient donc le temoin
    par le MEME chemin (« pas de ligne de version »), et la garde de code de
    retour n'etait jamais atteinte : l'assertion etait verte pour la mauvaise
    raison. C'est la tautologie que la politique du depot nomme endemique -- un
    test ecrit expres pour fermer un regime, qui ne le mesure pas.

    Le regime discriminant est donc : sortie **lisible** ET code **non nul**.
    """
    with tempfile.TemporaryDirectory() as dossier:
        menteur = Path(dossier) / "ffmpeg-qui-echoue-en-parlant"
        menteur.write_text(
            "#!/bin/sh\n"
            "echo 'ffmpeg version 7.7.7 Copyright (c) the FFmpeg developers'\n"
            "exit 1\n",
            encoding="utf-8")
        menteur.chmod(0o755)
        verdict = codec_profiles.probe_tool_version(str(menteur))

    assert verdict == codec_profiles.TOOL_VERSION_UNKNOWN, (
        "un binaire qui echoue en imprimant quand meme une ligne de version"
        f" a ete cru sur parole -- {verdict!r}")


def test_le_formatage_de_version_tient_les_trois_lignes_de_ffmpeg_mesurees() -> None:
    """Les trois sorties reellement rencontrees le 2026-09-06, verbatim.

    Le nombre d'espaces apres les points de version **varie** avec la largeur
    des champs (`58. 29.100` en 6.1.1, `61.  7.100` sur une version master):
    une analyse qui les compterait echouerait sur l'une des deux. Les deux sont
    donc jouees, plus la forme `n8.1.2-...` du numero de version, qui n'a pas
    la meme tete que `6.1.1-3ubuntu5`.
    """
    formate = codec_profiles._format_tool_version

    assert formate(
        "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers\n"
        "libavutil      58. 29.100 / 58. 29.100\n"
        "libavcodec     60. 31.102 / 60. 31.102\n"
        "libavformat    60. 16.100 / 60. 16.100\n"
    ) == (
        "6.1.1-3ubuntu5 (libavcodec 60.31.102, libavformat 60.16.100, "
        "libavutil 58.29.100)"
    )

    # FFmpeg 8.1.2 -- la ligne d'Egan.
    assert formate(
        "ffmpeg version n8.1.2-50-g1a748fe2cd-20260906 Copyright (c) 2000-2026\n"
        "libavutil      60. 26.102 / 60. 26.102\n"
        "libavcodec     62. 28.102 / 62. 28.102\n"
        "libavformat    62. 12.102 / 62. 12.102\n"
    ) == (
        "n8.1.2-50-g1a748fe2cd-20260906 (libavcodec 62.28.102, "
        "libavformat 62.12.102, libavutil 60.26.102)"
    )

    # Version master: deux espaces avant le 7.
    assert "libavutil 61.7.100" in formate(
        "ffmpeg version N-126435-gf93cd72dde-20260906 Copyright (c) 2000-2026\n"
        "libavutil      61.  7.100 / 61.  7.100\n"
    )

    # Sortie sans ligne de version: aucun numero invente.
    assert formate("libavutil 58. 29.100\n") == codec_profiles.TOOL_VERSION_UNKNOWN


def test_l_ordre_des_bibliotheques_ne_depend_pas_du_binaire() -> None:
    """Deux releves pris sur deux machines doivent se comparer a l'oeil.

    `ffmpeg -version` n'ordonne pas ses lignes de la meme facon d'une
    compilation a l'autre; le releve, lui, les rend toujours dans le meme
    ordre. Le drapeau varie: la meme information, presentee dans les deux
    ordres possibles, doit rendre exactement la meme chaine.
    """
    formate = codec_profiles._format_tool_version
    entete = "ffmpeg version 1.2.3 Copyright\n"
    avutil = "libavutil      58. 29.100 / 58. 29.100\n"
    avcodec = "libavcodec     60. 31.102 / 60. 31.102\n"
    assert formate(entete + avutil + avcodec) == formate(entete + avcodec + avutil)
    assert formate(entete + avcodec + avutil).index("libavcodec") < formate(
        entete + avcodec + avutil
    ).index("libavutil")


# --------------------------------------------------------------------------
# L'en-tete de frame ProRes -- la seule frontiere de ce lot qui morde sous 6.1.1
# --------------------------------------------------------------------------


@requires_ffmpeg
@pytest.mark.parametrize("profile_id", ["prores_hq", "prores_422", "prores_lt"])
def test_l_entete_de_frame_prores_porte_les_trois_champs(profile_id, tmp_path) -> None:
    """Le **bitstream** ProRes tague ses couleurs, pas seulement le conteneur.

    Trouve le 2026-09-06 en cherchant a prouver que le maillon `setparams` ne
    degradait rien sous 6.1.1. La mesure a etabli l'inverse de ce qu'elle
    cherchait: sur les trois profils ProRes, le fichier d'avant et celui
    d'apres different de **9 octets exactement** -- 3 frames x 3 champs --, tous
    de la valeur 2 (`UNSPECIFIED`) a la valeur 1 (`BT709`).

    Autrement dit, **avant ce correctif et deja sous 6.1.1**, l'atome `colr` du
    conteneur etait juste mais l'en-tete de chaque frame ProRes se declarait
    non tague. `ffprobe` lit l'atome, donc la verification technique du depot
    n'a jamais pu le voir; un logiciel de montage qui lit l'en-tete de frame,
    lui, recevait « non specifie ». C'est un defaut anterieur a la regression
    de FFmpeg 8, que le correctif ferme au passage.

    Ce banc est le **seul** de ce lot a distinguer le code d'avant du code
    d'apres sur un fichier reellement encode sous 6.1.1. Il est donc la seule
    protection locale contre le retrait du maillon.

    Disposition lue a partir de la signature `icpf`, verifiee par la geometrie
    relue au meme endroit (offsets +12/+14), ce qui interdit un faux positif
    sur un octet qui vaudrait 1 par hasard.
    """
    profile = codec_profiles.get_profile(profile_id)
    # Un dossier de travail pour la sortie de ffmpeg, et rien d'autre : il ne
    # designe AUCUN dossier de l'arborescence de projet. Il s'appelait `frames`,
    # ce qui le faisait passer pour tel -- aux yeux d'un lecteur comme a ceux de
    # la frontiere qui interdit de composer ces noms a la main.
    frames_dir = tmp_path / "rendu-ffmpeg"
    frames_dir.mkdir()
    rendu = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=320x180:rate=5:duration=0.4",
         "-pix_fmt", "rgb24", str(frames_dir / "f_%03d.tiff")],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert rendu.returncode == 0, rendu.stderr
    frames = sorted(frames_dir.glob("*.tiff"))
    assert len(frames) > 1, frames

    sortie = tmp_path / f"{profile_id}.mov"
    codec_profiles.run_encode(profile_id, frames, 5, sortie)
    octets = sortie.read_bytes()

    signature = octets.find(b"icpf")
    assert signature > 0, "aucune frame ProRes trouvee dans le fichier"
    largeur = int.from_bytes(octets[signature + 12:signature + 14], "big")
    hauteur = int.from_bytes(octets[signature + 14:signature + 16], "big")
    assert (largeur, hauteur) == (320, 180), (
        "la disposition de l'en-tete ne s'aligne pas: les offsets couleur lus "
        "plus bas ne designeraient pas ce qu'on croit"
    )

    # 1 == AVCOL_*_BT709, 2 == UNSPECIFIED. Le profil ne porte que `bt709`
    # aujourd'hui; l'assertion est ecrite sur la valeur du profil pour rougir
    # si le catalogue change, pas sur la constante 1.
    attendu = {"bt709": 1, "smpte170m": 6, "smpte240m": 7}[profile.colorspace]
    releve = {
        "color_primaries": octets[signature + 18],
        "transfer_characteristic": octets[signature + 19],
        "matrix_coefficients": octets[signature + 20],
    }
    assert releve == dict.fromkeys(releve, attendu), (
        f"en-tete de frame ProRes non tague: {releve} "
        f"(2 == UNSPECIFIED, attendu {attendu} pour {profile.colorspace})"
    )
