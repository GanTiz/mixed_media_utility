# -*- coding: utf-8 -*-
"""`E4-2` / `E4-2b` -- les reglages de l'encodage (story 11.8, lot D, AC 6).

Ce banc mesure les sept points de l'AC 6, **frontieres negatives comprises** :
les sept profils lus de `codec_profiles.PROFILES` sans jamais leur categorie
(`EPIC11-ARB-187`), le vocabulaire de resolution lu du coeur avec sa forme
personnalisee joignable, le retrait du nom de master (`EPIC11-ARB-141`),
l'interdit de la lettre nue a cote d'un champ de saisie (`EPIC11-ARB-68`), la
cadence du **rushe source** qui n'est jamais `fps_target` (`EPIC11-ARB-192`) et
la ligne d'etat sans touche (`EPIC11-ARB-56`).

**La regle des fabriques y est appliquee dans sa forme complete.** Les
collections de cet ecran sont reelles -- sept profils, trois champs, trois
resolutions -- et les cibles sont **au milieu** : `dnxhr_hq` est le quatrieme
des sept profils, `Résolution` le deuxieme des trois champs, `uhd2160` la
deuxieme des trois entrees de resolution. Ni premiere, ni derniere : c'est ce
qui separe une faute de `find` d'une faute de terminaison de boucle. Les
fabriques de maintiens portent **deux valeurs distinguables**, sans quoi rendre
le premier maintien et rendre l'ensemble seraient indiscernables.

**Aucune assertion positive seule** sur ce qui a une exception : l'ensemble des
profils qui portent une mention, l'ensemble des champs qui portent le glyphe
d'invite et l'ensemble des situations qui affichent un cartouche sont mesures
**exactement**, jamais par appartenance.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
from fractions import Fraction

import pytest

_RACINE = pathlib.Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import codec_profiles, encode, encode_master  # noqa: E402
from mixed_media_utility.tui import cadences, jetons  # noqa: E402
from mixed_media_utility.tui.coque import (Contexte, CoqueTui,  # noqa: E402
                                           PalierTemoin)
from mixed_media_utility.tui import atelier_exports_reglages as reglages_exports  # noqa: E402

# La table des glyphes fermee du lot G de la 11.4, LUE et non recopiee.
from test_sobriete_et_grille_extraction import glyphes_hors_table  # noqa: E402

MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
SOURCE_DU_MODULE = pathlib.Path(reglages_exports.__file__)
DOSSIER_TUI = SOURCE_DU_MODULE.parent

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]


# ===========================================================================
# Les fabriques
# ===========================================================================

def lot_nominal() -> reglages_exports.LotAEncoder:
    """Le lot de `E4-2` : **il declare sa cadence source, et elle vaut 25**.

    Ses deux cadences **different**, et c'est toute la mesure de l'AC 6.6 :
    `fps_target` vaut 12,5 -- la decimation de l'extraction -- et
    `timecode_base_fps` vaut 25 -- la seule cadence qui mux. Une fabrique ou
    les deux coincideraient rendrait les deux lectures indiscernables.
    """
    return reglages_exports.LotAEncoder.du_manifest(
        {"lot_id": "plan-04_25", "fps_target": 12.5, "timecode_base_fps": 25},
        124)


def lot_sans_cadence() -> reglages_exports.LotAEncoder:
    """Le lot de `E4-2b` : une planche 2.0, qui n'imprimait pas la cadence.

    Il porte quand meme son `fps_target` : c'est le piege exact
    d'`EPIC11-ARB-192`, ou un ecran qui replierait sur la decimation
    afficherait `12,5` la ou le lot ne declare **rien**.
    """
    return reglages_exports.LotAEncoder.du_manifest(
        {"lot_id": "plan-04_12p5", "fps_target": 12.5}, 63)


def mesure_de_e4_2() -> reglages_exports.MesureDuMaster:
    """Ce que le coeur mesure du master de `E4-2`. ~1,4 Go, 124 echantillons."""
    return reglages_exports.MesureDuMaster(
        echantillons=124, maintiens=(1, 1, 1),
        duree_s=4.96, poids_octets=int(1.4 * 1024 ** 3))


def mesure_de_e4_2b() -> reglages_exports.MesureDuMaster:
    """Ce que le coeur mesure du master de `E4-2b` : maintiens de 2, 5 s 00."""
    return reglages_exports.MesureDuMaster(
        echantillons=125, maintiens=(2, 2, 2), duree_s=5.0)


def reglages(**champs) -> reglages_exports.ReglagesDeL_encodage:
    champs.setdefault("lot", lot_nominal())
    return reglages_exports.ReglagesDeL_encodage(**champs)


def corps(modele, ascii_seul: bool = False) -> list[str]:
    """Les lignes du corps, telles que le rendu les peindrait."""
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    return [ligne.rstrip()
            for ligne in ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0]]


def _cadre(nom: str) -> list[str]:
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
    return [ligne for ligne in lignes if ligne.startswith("│")]


def centre_de_la_maquette(nom: str) -> list[str]:
    """Les lignes de la zone centrale d'une maquette, marge de gauche retiree."""
    centre = [ligne[2:-1].rstrip() for ligne in _cadre(nom)[1:-2]]
    # `textual` ne remplit pas la zone : la composition s'arrete a sa derniere
    # ligne de texte, la maquette continue jusqu'au filet.
    while centre and not centre[-1]:
        centre.pop()
    return centre


def etat_de_la_maquette(nom: str) -> str:
    return _cadre(nom)[-2][2:-1].rstrip()


def raccourcis_de_la_maquette(nom: str) -> str:
    return _cadre(nom)[-1][2:-1].rstrip()


def chaines_du_code(chemin: pathlib.Path) -> list[str]:
    """Les chaines litterales du CODE, docstrings exclus.

    On lit l'arbre syntaxique et jamais le texte : les docstrings de ce module
    nomment `fps_target` et `secondary` pour dire ce qu'il n'affiche pas, et un
    grep y mordrait -- il se ferait affaiblir a la premiere prose.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docstrings = set()
    porteurs = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, porteurs):
            continue
        corps_ = getattr(noeud, "body", [])
        if (corps_ and isinstance(corps_[0], ast.Expr)
                and isinstance(corps_[0].value, ast.Constant)
                and isinstance(corps_[0].value.value, str)):
            docstrings.add(id(corps_[0].value))
    return [noeud.value for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, str)
            and id(noeud) not in docstrings]


# ===========================================================================
# La fabrique elle-meme -- sans quoi tout ce qui suit mesure du vide
# ===========================================================================

def test_les_fabriques_portent_des_valeurs_DISTINGUABLES():
    """Regle des fabriques, point 2 : deux cadences egales ne mesureraient rien.

    Le lot nominal porte `fps_target = 12,5` et `timecode_base_fps = 25`. Si
    les deux coincidaient, l'AC 6.6 serait verte quelle que soit la valeur lue,
    et le mutant « afficher `fps_target` » survivrait a toute la suite.
    """
    lot = lot_nominal().lot
    assert lot["fps_target"] != lot["timecode_base_fps"]
    assert lot_sans_cadence().lot.get("timecode_base_fps") is None
    assert lot_sans_cadence().lot["fps_target"] == 12.5
    # Et les deux lots sont distinguables l'un de l'autre sur les DEUX champs
    # que l'ecran affiche : l'identite et le cardinal de frames.
    assert lot_nominal().lot_id != lot_sans_cadence().lot_id
    assert lot_nominal().frames != lot_sans_cadence().frames


def test_le_corpus_des_profils_porte_SEPT_entrees_et_la_cible_est_AU_MILIEU():
    """Regle des fabriques, point 1 : la cible n'est ni premiere ni derniere.

    `dnxhr_hq` est le quatrieme des sept. Une cible en premiere position
    laisserait vivre un `find` qui rend toujours le premier element ; en
    derniere, un `continue` -> `break`.
    """
    profils = tuple(codec_profiles.PROFILES)
    assert len(profils) == 7, profils
    assert profils.index(PROFIL_CIBLE) == 3
    assert PROFIL_CIBLE not in (profils[0], profils[-1])
    # Les sept identifiants sont distincts, et deux conteneurs au moins
    # existent -- sans quoi l'AC 6.2 ne mesurerait rien.
    assert len(set(profils)) == 7
    assert len({profil.container
                for profil in codec_profiles.PROFILES.values()}) >= 2


#: La cible des mesures de profil : **au milieu** des sept, et en `.mov`.
PROFIL_CIBLE = "dnxhr_hq"
#: Le premier profil `.mp4` -- celui qui fait basculer le conteneur (AC 6.2).
PROFIL_MP4 = "h264_delivery"


# ===========================================================================
# E1 -- l'etat d'ouverture vient des constantes du COEUR (AC 6.1, 6.3)
# ===========================================================================

def test_l_etat_d_ouverture_est_celui_du_coeur():
    depart = reglages()
    assert depart.profil == codec_profiles.DEFAULT_PROFILE_ID
    assert depart.resolution == encode.DEFAULT_RESOLUTION_ID


def test_aucune_constante_d_ouverture_n_est_ecrite_en_litteral():
    """Frontiere negative : les defauts NOMMENT la constante du coeur.

    Un test qui comparerait seulement les valeurs resterait vert si quelqu'un
    ecrivait `profil: str = "prores_hq"` -- il mesurerait alors que
    `"prores_hq" == "prores_hq"`. Celui-ci lit la source et exige la reference.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "codec_profiles.DEFAULT_PROFILE_ID" in source
    assert "encode.DEFAULT_RESOLUTION_ID" in source
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert codec_profiles.DEFAULT_PROFILE_ID not in litteraux
    assert encode.DEFAULT_RESOLUTION_ID not in litteraux


def test_le_curseur_s_ouvre_LA_OU_il_y_a_quelque_chose_a_faire():
    """Les deux situations, et elles different -- une seule ne mesurerait rien."""
    assert reglages().champ == reglages_exports.CHAMP_PROFIL
    assert reglages(lot=lot_sans_cadence()).champ == (
        reglages_exports.CHAMP_CADENCE)


def test_la_cadence_est_PREREMPLIE_par_la_valeur_du_lot():
    """`EPIC11-ARB-185` : le champ est reglable, **prerempli** par le lot."""
    assert reglages().cadence == "25"
    assert reglages(lot=lot_sans_cadence()).cadence == ""
    # Et une saisie donnee n'est pas ecrasee par le preremplissage.
    assert reglages(cadence="30").cadence == "30"


# ===========================================================================
# E2 -- AC 6.1 : les sept profils, leur conteneur, et AUCUNE categorie
# ===========================================================================

def test_la_liste_est_EXACTEMENT_les_sept_profils_du_coeur_dans_son_ordre():
    """Ensemble **et** ordre : un sous-ensemble passerait une appartenance."""
    modele = reglages()
    assert modele.profils() == tuple(codec_profiles.PROFILES)
    lignes = modele.lignes_de_la_liste()
    assert len(lignes) == len(codec_profiles.PROFILES)
    for ligne, identifiant in zip(lignes, codec_profiles.PROFILES):
        assert identifiant in ligne


def test_chaque_ligne_porte_le_conteneur_LU_de_la_table_du_coeur():
    """AC 6.1 : le conteneur reste (seule la categorie tombe avec `-187`)."""
    modele = reglages()
    for ligne, (identifiant, profil) in zip(modele.lignes_de_la_liste(),
                                            codec_profiles.PROFILES.items()):
        assert f".{profil.container}" in ligne, (identifiant, ligne)
    assert "codec_profiles.PROFILES" in SOURCE_DU_MODULE.read_text(
        encoding="utf-8")


def test_l_ensemble_des_profils_qui_portent_une_MENTION_est_EXACTEMENT_le_defaut():
    """`EPIC11-ARB-187` : « Juste `défaut` sur le profil par defaut. »

    Ensemble exact, et non appartenance : une assertion positive laisserait
    passer une mention de trop, qui est precisement ce que l'arbitrage retire.
    """
    modele = reglages()
    marques = {identifiant
               for identifiant, ligne in zip(codec_profiles.PROFILES,
                                             modele.lignes_de_la_liste())
               if reglages_exports.MENTION_DU_DEFAUT.strip() in ligne}
    assert marques == {codec_profiles.DEFAULT_PROFILE_ID}


def test_le_defaut_se_lit_a_DEFAULT_PROFILE_ID_et_non_a_la_categorie(
        monkeypatch):
    """Volet **positif** de la frontiere : on deplace le defaut du coeur, et
    l'ecran doit suivre.

    Un ecran qui devinerait le defaut a la categorie (`primary`) ignorerait
    cette substitution et resterait vert -- c'est exactement ce que ce test
    attrape, et c'est le seul moyen de prouver que la categorie n'est pas lue
    par la fenetre apres avoir ete retiree par la porte.
    """
    monkeypatch.setattr(codec_profiles, "DEFAULT_PROFILE_ID", PROFIL_CIBLE)
    modele = reglages(profil=PROFIL_CIBLE)
    marques = {identifiant
               for identifiant, ligne in zip(codec_profiles.PROFILES,
                                             modele.lignes_de_la_liste())
               if reglages_exports.MENTION_DU_DEFAUT.strip() in ligne}
    assert marques == {PROFIL_CIBLE}
    assert modele.est_le_defaut(PROFIL_CIBLE) is True
    assert modele.est_le_defaut("prores_hq") is False


def test_AUCUN_libelle_de_categorie_n_est_un_litteral_du_module():
    """Frontiere negative de l'AC 6.1, **resserree par `EPIC11-ARB-187`**.

    La categorie n'est plus seulement « jamais recopiee » : elle n'est plus
    **affichee du tout**. Ni `primary`/`secondary` -- deux mots anglais qui
    n'apprennent rien --, ni une traduction, qui serait un mot de plus a
    l'ecran pouvant diverger de l'outil.
    """
    interdits = {profil.category for profil in codec_profiles.PROFILES.values()}
    interdits |= {"mezzanine", "diffusion", "principal", "secondaire"}
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert litteraux & interdits == set(), litteraux & interdits
    # Le volet symetrique : la frontiere mesure quelque chose de reel -- le
    # coeur porte bien au moins deux categories distinctes, donc il y avait
    # bien quelque chose a ne pas afficher.
    assert len({profil.category
                for profil in codec_profiles.PROFILES.values()}) >= 2


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_liste_ne_s_ouvre_QUE_sous_le_champ_qui_a_le_focus(ascii_seul):
    """`E4-2` la dessine ouverte, `E4-2b` fermee : c'est le meme ecran."""
    ouverte = corps(reglages(champ=reglages_exports.CHAMP_PROFIL), ascii_seul)
    fermee = corps(reglages(champ=reglages_exports.CHAMP_CADENCE), ascii_seul)
    assert sum(PROFIL_MP4 in ligne for ligne in ouverte) == 1
    assert sum(PROFIL_MP4 in ligne for ligne in fermee) == 0


def test_le_curseur_et_la_puce_designent_la_MEME_ligne_au_milieu_des_sept():
    """`EPIC11-ARB-180` : la fleche dit ou est le curseur, la puce ce qui est
    retenu, et un champ exclusif **qui a le focus** porte les deux.

    La cible est le quatrieme des sept : un `find` qui rendrait le premier
    profil serait vert sur une fabrique mono-element.
    """
    modele = reglages(profil=PROFIL_CIBLE)
    lignes = modele.lignes_de_la_liste()
    curseur = jetons.GLYPHES["curseur"]
    retenu = jetons.GLYPHES["exclusif-retenu"]
    portant_le_curseur = {rang for rang, ligne in enumerate(lignes)
                          if curseur in ligne}
    portant_la_puce = {rang for rang, ligne in enumerate(lignes)
                       if retenu in ligne}
    assert portant_le_curseur == portant_la_puce == {3}
    assert PROFIL_CIBLE in lignes[3]


# ===========================================================================
# E3 -- AC 6.2 : le bloc propre au profil se REMPLACE entierement
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_apres_bascule_vers_un_profil_mp4_AUCUN_champ_du_mov_ne_reste(
        ascii_seul):
    """AC 6.2, **frontiere negative**, mesuree hors liste deroulee.

    La liste des sept montre tous les conteneurs par construction ; ce que l'AC
    vise est ce que le profil RETENU fait afficher. On mesure donc l'ecran dont
    le deroulant est ferme -- le champ, la ligne de colorimetrie, la ligne
    d'etat -- et l'ensemble des conteneurs qui y apparaissent est **exactement**
    celui du profil retenu.
    """
    modele = reglages(champ=reglages_exports.CHAMP_RESOLUTION)
    avant = "\n".join(corps(modele, ascii_seul)) + modele.ligne_d_etat(ascii_seul)
    # Volet symetrique : avant la bascule, le conteneur `.mov` EST la.
    assert ".mov" in avant and ".mp4" not in avant
    assert modele.poser_le_profil(PROFIL_MP4) is True
    apres = "\n".join(corps(modele, ascii_seul)) + modele.ligne_d_etat(ascii_seul)
    assert ".mp4" in apres
    assert ".mov" not in apres


def test_un_profil_HORS_de_la_table_du_coeur_n_entre_pas():
    """`EPIC11-ARB-17` : l'ecran ne laisse jamais a l'ecran un couple que le
    coeur refuserait."""
    modele = reglages()
    assert modele.poser_le_profil("prores_4444_xq") is False
    assert modele.profil == codec_profiles.DEFAULT_PROFILE_ID


def test_la_colorimetrie_est_portee_par_le_PROFIL_et_non_par_le_manifest():
    """Le dessin d'origine disait « reinjecte depuis le manifest » : c'etait la
    mauvaise source."""
    modele = reglages()
    assert modele.colorimetrie() == (
        codec_profiles.PROFILES[codec_profiles.DEFAULT_PROFILE_ID].colorspace)
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert modele.colorimetrie() not in litteraux


# ===========================================================================
# E4 -- AC 6.3 : le vocabulaire de resolution est LU du coeur
# ===========================================================================

def test_la_glose_de_resolution_est_EXACTEMENT_le_vocabulaire_du_coeur():
    """Egalite d'ensemble ET d'ordre, plus la forme personnalisee.

    Une appartenance laisserait passer un identifiant oublie -- le cas exact
    d'une resolution ajoutee au registre du coeur et jamais offerte par
    l'ecran, qui est ce que la frontiere de `EPIC11-ARB-159` a paye sur les
    formats de scan.
    """
    modele = reglages()
    attendu = (*encode.known_resolution_ids(),
               encode.NATIVE_RESOLUTION_KEYWORD,
               reglages_exports.FORME_PERSONNALISEE)
    assert tuple(modele.glose_de_resolution().split(
        reglages_exports.SEPARATEUR)) == attendu


def test_AUCUN_identifiant_de_resolution_n_est_un_litteral_du_module():
    """Frontiere negative de l'AC 6.3."""
    interdits = {*encode.known_resolution_ids(),
                 encode.NATIVE_RESOLUTION_KEYWORD}
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert litteraux & interdits == set(), litteraux & interdits
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "encode.known_resolution_ids()" in source
    assert "encode.NATIVE_RESOLUTION_KEYWORD" in source


def test_le_vocabulaire_suit_le_REGISTRE_du_coeur_et_ne_le_rejoue_pas(
        monkeypatch):
    """Volet **positif** de la frontiere : on ajoute une entree au registre du
    coeur, et l'ecran doit l'offrir sans qu'une ligne change ici.

    C'est le critere d'`EPIC6-ARB-5` -- « ajouter une resolution ne coute
    qu'une ligne » -- mesure depuis la TUI. La cible est **au milieu** du
    vocabulaire enrichi.
    """
    registre = dict(encode.RESOLUTION_REGISTRY)
    registre["dci4k"] = encode.OutputResolution("dci4k", 4096, 2160)
    monkeypatch.setattr(encode, "RESOLUTION_REGISTRY", registre)
    modele = reglages()
    assert "dci4k" in modele.vocabulaire_de_resolution()
    assert "dci4k" in modele.glose_de_resolution()


def test_la_forme_personnalisee_est_JOIGNABLE_et_resolue_par_le_coeur():
    """AC 6.3 : `<l>x<h>` est offerte, donc elle doit marcher.

    Elle est **tapee**, pas choisie : c'est un champ de saisie, et c'est ce qui
    la rend joignable sans que l'ecran ait a enumerer l'infini.
    """
    modele = reglages(champ=reglages_exports.CHAMP_RESOLUTION, resolution="")
    for caractere in "1440x1080":
        assert modele.frapper(caractere) is True
    assert modele.resolution == "1440x1080"
    assert modele.geometrie() == (1440, 1080)
    assert modele.peut_encoder is True


def test_une_resolution_que_le_coeur_REFUSE_ferme_l_issue_sans_planter():
    """Une saisie en cours n'est pas une faute : elle n'est pas encore valide."""
    modele = reglages(resolution="1440x")
    assert modele.geometrie() is None
    assert modele.peut_encoder is False


def test_native_est_VALIDE_et_sans_geometrie_connue():
    """Les deux `None` de `geometrie()` ne disent pas la meme chose, et c'est
    `peut_encoder` qui les separe."""
    modele = reglages(resolution=encode.NATIVE_RESOLUTION_KEYWORD)
    assert modele.geometrie() is None
    assert modele.peut_encoder is True


def test_les_fleches_parcourent_le_vocabulaire_et_la_cible_est_AU_MILIEU():
    """`uhd2160` est la deuxieme des trois entrees : ni premiere, ni derniere."""
    vocabulaire = reglages().vocabulaire_de_resolution()
    assert len(vocabulaire) == 3, vocabulaire
    modele = reglages(champ=reglages_exports.CHAMP_RESOLUTION)
    assert modele.resolution == vocabulaire[0]
    modele.choisir(1)
    assert modele.resolution == vocabulaire[1]
    modele.choisir(1)
    assert modele.resolution == vocabulaire[2]
    # Bornee, jamais circulaire : une seule pression ne saute pas du bout de la
    # liste a son autre bout.
    assert modele.choisir(1) is False
    assert modele.resolution == vocabulaire[-1]


def test_les_fleches_ENTRENT_dans_le_vocabulaire_depuis_une_valeur_libre():
    """Une touche annoncee qui reste inerte est indistinguable d'un clavier
    casse : depuis une resolution personnalisee, les fleches entrent par le
    bord vers lequel elles vont."""
    vocabulaire = reglages().vocabulaire_de_resolution()
    vers_le_bas = reglages(champ=reglages_exports.CHAMP_RESOLUTION,
                           resolution="1440x1080")
    assert vers_le_bas.choisir(1) is True
    assert vers_le_bas.resolution == vocabulaire[0]
    vers_le_haut = reglages(champ=reglages_exports.CHAMP_RESOLUTION,
                            resolution="1440x1080")
    assert vers_le_haut.choisir(-1) is True
    assert vers_le_haut.resolution == vocabulaire[-1]


# ===========================================================================
# E5 -- AC 6.4 : le champ « Nom du master » est RETIRE
# ===========================================================================

#: Les modules de l'atelier Exports au lot D. La liste est nommee plutot que
#: devinee : une frontiere de paquet reste verte le jour ou un module sort du
#: paquet, et celle-ci dit lequel elle mesure.
MODULES_DE_L_ATELIER = ("atelier_exports_reglages.py",)


def test_AUCUN_module_de_cet_atelier_ne_parle_d_editer_un_nom():
    """AC 6.4, **frontiere negative** : le grep rend zero.

    `EPIC11-ARB-141` : « On retire l'edition des noms PARTOUT ou elle ne peut
    pas etre effective. » La mesure porte sur le texte entier -- prose
    comprise -- parce que ce qui est interdit ici est d'**annoncer** le geste,
    et qu'une ligne de raccourcis est du texte.
    """
    interdits = ("éditer le nom", "editer le nom", "Nom du master",
                 "nom_du_master", "éditer les noms")
    fautifs = []
    for nom in MODULES_DE_L_ATELIER:
        texte = (DOSSIER_TUI / nom).read_text(encoding="utf-8")
        fautifs += [(nom, interdit) for interdit in interdits
                    if interdit in texte]
    assert fautifs == [], fautifs


def test_le_volet_SYMETRIQUE_le_coeur_ne_porte_aucun_parametre_de_nom():
    """Le retrait est **reversible et mesure** (AC 2.4).

    `encode_master.MOTS_CLES_DE_LA_DECISION` gele l'ensemble des mots-cles que
    la TUI transmet au coeur : aucun n'est un nom de master. Le jour ou le
    point d'entree en gagnerait un, cette assertion rougirait la premiere, et
    la frontiere ci-dessus deviendrait discutable au lieu de rester muette.
    """
    mots = encode_master.MOTS_CLES_DE_LA_DECISION
    assert not any("nom" in mot or "name" in mot for mot in mots), mots
    # Le mot-cle de cadence, lui, EXISTE -- c'est par la que ce champ passe.
    assert "cadence_source_override" in mots


def test_aucun_glyphe_de_deroulant_n_est_ecrit_SANS_son_repli():
    """Le marqueur `▾` est le seul dessin hors `GLYPHES` de ce module.

    Il est admis parce qu'il a un repli (`jetons.REPLIS_DE_TEXTE`) : sans lui,
    `--ascii` en ferait un `?`, exactement le defaut que `×` a paye le
    2026-08-29. La mesure porte donc sur le repli, pas sur l'interdit.
    """
    assert reglages_exports.MARQUE_DEROULANT in jetons.REPLIS_DE_TEXTE
    replie = jetons.replier_ascii(reglages_exports.MARQUE_DEROULANT)
    assert replie.isascii() and replie != "?"


# ===========================================================================
# E6 -- AC 6.5 : aucune lettre n'est un raccourci, `Tab` nomme sa destination
# ===========================================================================

#: Les touches que les deux lignes de cet ecran ont le droit d'annoncer. Toutes
#: sont des touches **nommees** ou des glyphes : pas une lettre nue.
TOUCHES_ANNONCABLES = ("⏎", "Tab", "↑↓", "Échap", "F1")


@pytest.mark.parametrize("ligne", [reglages_exports.RACCOURCIS_CHOIX,
                                   reglages_exports.RACCOURCIS_SAISIE])
def test_AUCUNE_lettre_nue_n_est_annoncee_en_raccourci(ligne):
    """`EPIC11-ARB-68` : « aucune lettre n'est un raccourci dans un champ de
    saisie, sans exception et sans ordre de priorite a maintenir ».

    L'ecran porte deux champs de saisie : la regle s'y applique entiere. La
    mesure porte sur la **tete** de chaque entree -- ce qui est annonce comme
    touche --, jamais sur le libelle qui la suit.
    """
    entrees = [entree for entree in ligne.split("  ") if entree]
    tetes = [entree.split(" ", 1)[0] for entree in entrees]
    assert set(tetes) <= set(TOUCHES_ANNONCABLES), tetes
    assert not any(re.fullmatch(r"[A-Za-zÀ-ÿ]", tete) for tete in tetes), tetes


@pytest.mark.parametrize("ligne", [reglages_exports.RACCOURCIS_CHOIX,
                                   reglages_exports.RACCOURCIS_SAISIE])
def test_Tab_nomme_sa_DESTINATION_et_pas_l_objet_qu_il_quitte(ligne):
    """`EPIC11-ARB-68`, second volet. « Tab champ » nomme l'objet ; « Tab champ
    suivant » nomme la destination -- et dans un cycle de trois champs, c'est
    la seule destination vraie."""
    assert "Tab champ suivant" in ligne


def test_Tab_FAIT_ce_que_la_ligne_annonce_et_parcourt_les_trois_champs():
    """La moitie executable de l'annonce : trois champs, en boucle.

    Une ligne qui annonce une destination que la touche ne rejoint pas est
    exactement le mensonge d'interface que l'arbitrage ferme.
    """
    assert reglages_exports.CHAMPS == ("profil", "resolution", "cadence")
    modele = reglages()
    vus = [modele.champ]
    for _ in range(len(reglages_exports.CHAMPS)):
        modele.avancer()
        vus.append(modele.champ)
    assert vus == list(reglages_exports.CHAMPS) + [
        reglages_exports.CHAMP_PROFIL]


@pytest.mark.parametrize("lettre", ["q", "e", "o", "n", "a"])
def test_toute_LETTRE_frappee_s_ecrit_dans_le_champ_de_saisie(lettre):
    """Les cinq lettres choisies sont des raccourcis **ailleurs** dans le
    produit (`q` quitter, `e` editer, `o` ouvrir) : c'est ce qui rend la mesure
    non triviale."""
    modele = reglages(lot=lot_sans_cadence(),
                      champ=reglages_exports.CHAMP_CADENCE)
    assert modele.cadence == "", "le champ doit partir vide pour cette mesure"
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    assert ecran.traiter(lettre, lettre) is True
    assert modele.cadence == lettre


def test_une_lettre_sur_un_champ_de_CHOIX_ne_declenche_rien():
    """Elle ne s'ecrit pas -- ce n'est pas un champ de saisie -- et elle
    n'ouvre rien non plus : une lettre n'est un raccourci nulle part ici."""
    modele = reglages(champ=reglages_exports.CHAMP_PROFIL)
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    avant = (modele.profil, modele.resolution, modele.cadence, modele.champ)
    assert ecran.traiter("e", "e") is False
    assert (modele.profil, modele.resolution, modele.cadence,
            modele.champ) == avant


def test_l_effacement_ne_mord_que_sur_les_champs_de_SAISIE():
    modele = reglages(champ=reglages_exports.CHAMP_CADENCE)
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    assert ecran.traiter("backspace") is True
    assert modele.cadence == "2"
    modele.champ = reglages_exports.CHAMP_PROFIL
    assert ecran.traiter("backspace") is False
    assert modele.profil == codec_profiles.DEFAULT_PROFILE_ID


def test_la_ligne_de_raccourcis_est_CONTEXTUELLE_dans_les_deux_etats():
    """Une AC qui n'en mesurerait qu'un laisserait passer une ligne figee."""
    sur_un_choix = reglages(champ=reglages_exports.CHAMP_PROFIL).raccourcis()
    sur_une_saisie = reglages(champ=reglages_exports.CHAMP_CADENCE).raccourcis()
    assert sur_un_choix != sur_une_saisie
    assert "↑↓ choisir" in sur_un_choix
    assert "↑↓" not in sur_une_saisie
    # La resolution offre les deux : les fleches y choisissent, la frappe y
    # ecrit -- la ligne annonce donc bien `↑↓`.
    assert reglages(champ=reglages_exports.CHAMP_RESOLUTION).raccourcis() == (
        sur_un_choix)


def test_les_fleches_ne_font_RIEN_sur_le_champ_qui_ne_les_annonce_pas():
    """Le symetrique du test precedent : la ligne ne ment pas par omission."""
    modele = reglages(champ=reglages_exports.CHAMP_CADENCE)
    avant = modele.cadence
    assert modele.choisir(1) is False
    assert modele.choisir(-1) is False
    assert modele.cadence == avant


def test_l_ecran_POSE_sa_ligne_de_raccourcis_a_chaque_dessin():
    """L'idiome du depot, et le motif de ne pas en faire une `property` :
    `test_majuscules_des_raccourcis` lit l'attribut de CLASSE et attend une
    chaine."""
    assert isinstance(
        reglages_exports.EcranReglagesDeL_encodage.raccourcis, str)
    modele = reglages(champ=reglages_exports.CHAMP_PROFIL)
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    assert ecran.poser_les_raccourcis() == reglages_exports.RACCOURCIS_CHOIX
    ecran.traiter("tab")
    ecran.traiter("tab")
    assert ecran.poser_les_raccourcis() == reglages_exports.RACCOURCIS_SAISIE
    assert ecran.raccourcis == reglages_exports.RACCOURCIS_SAISIE


# ===========================================================================
# E7 -- AC 6.6 : la cadence du RUSHE SOURCE, jamais `fps_target`
# ===========================================================================

def test_la_cadence_affichee_est_la_cadence_SOURCE_et_jamais_fps_target():
    """`EPIC11-ARB-192`, et c'est la mesure centrale de cet ecran.

    Le lot porte `fps_target = 12,5` **et** `timecode_base_fps = 25`. Un ecran
    qui lirait la decimation afficherait `12,5` ; celui-ci affiche `25`, et
    `12,5` n'apparait nulle part -- ni au champ, ni en ligne d'etat.
    """
    modele = reglages(mesure=mesure_de_e4_2())
    assert modele.lot.cadence_source == "25/1"
    assert modele.valeur_de_la_cadence() == "25 fps"
    ecrit = "\n".join(corps(modele)) + modele.ligne_d_etat()
    assert "25" in ecrit
    assert "12,5" not in ecrit and "12.5" not in ecrit


def test_le_module_ne_NOMME_jamais_fps_target():
    """Frontiere negative de l'AC 6.6, mesuree a l'arbre syntaxique.

    Le texte du module parle de `fps_target` pour dire qu'il ne l'affiche pas :
    un grep y mordrait et se ferait affaiblir a la premiere prose. On lit donc
    les chaines du **code** et les noms reellement references.
    """
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert "fps_target" not in litteraux
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    noms = {noeud.attr for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Attribute)}
    noms |= {noeud.id for noeud in ast.walk(arbre)
             if isinstance(noeud, ast.Name)}
    assert "fps_target" not in noms
    assert "resolve_frame_rate" not in noms


def test_la_cadence_source_est_LUE_du_coeur_et_ne_le_rejoue_pas(monkeypatch):
    """Volet **positif** de la frontiere : on remplace la reponse du coeur, et
    l'ecran doit changer d'avis.

    Un ecran qui lirait `timecode_base_fps` lui-meme ignorerait cette
    substitution et resterait vert.
    """
    monkeypatch.setattr(encode, "resolve_source_rate",
                        lambda lot, **kw: (30.0, "30/1", None))
    assert lot_nominal().cadence_source == "30/1"
    assert reglages().valeur_de_la_cadence() == "30 fps"


def test_un_lot_SANS_cadence_source_est_un_ETAT_et_non_un_plantage():
    """AC 6.6 / `E4-2b` : le refus nomme du coeur s'affiche comme un etat.

    Le code est **lu du coeur** et non recopie : c'est lui qui dit quel refus
    se traduit en `E4-2b` et quel refus doit remonter.
    """
    assert encode.ENCODE_SOURCE_RATE_MISSING == "CADENCE_SOURCE_MANQUANTE"
    lot = lot_sans_cadence()
    assert lot.cadence_source is None
    assert lot.declare_sa_cadence is False
    assert reglages_exports.cadence_source_du_lot(lot.lot) is None


def test_une_cadence_source_INEXPLOITABLE_remonte_au_lieu_d_etre_avalee():
    """Deux etats differents, deux traitements : « absente » et « presente mais
    fausse » ne se disent pas de la meme facon.

    Un `except EncodeDecisionError` nu afficherait « le lot n'en declare
    aucune » sur un lot qui en declare une, et l'operateur corrigerait un
    manque au lieu d'une faute.
    """
    with pytest.raises(encode.EncodeDecisionError) as refus:
        reglages_exports.cadence_source_du_lot(
            {"lot_id": "plan-04_25", "timecode_base_fps": "vingt-cinq"})
    assert refus.value.code != encode.ENCODE_SOURCE_RATE_MISSING


def test_le_cas_NOMINAL_ne_transmet_RIEN_au_coeur_et_n_avertit_de_rien():
    """`EPIC11-ARB-192` point 2 : « aucun avertissement dans le cas nominal ».

    `resolve_source_rate` emet sa note d'ecrasement des que l'option est
    fournie, **meme identique** a la valeur du lot -- defaut du coeur mesure le
    2026-09-03. Ne rien transmettre quand rien ne diverge est ce qui empeche
    l'ecran de le declencher.
    """
    modele = reglages()
    assert modele.cadence_source_transmise() is None
    assert modele.note_du_coeur() is None
    assert modele.lignes_du_cartouche(jetons.largeur_utile()) == []


@pytest.mark.parametrize("saisie", ["25", "25,0", "25/1"])
def test_trois_ECRITURES_de_la_meme_cadence_ne_divergent_pas(saisie):
    """La comparaison se fait sur la cadence EXACTE du coeur, jamais sur le
    texte : `25`, `25,0` et `25/1` sont la meme cadence, et trois textes.

    C'est le mutant le plus discret de ce champ -- comparer `self.cadence` a la
    valeur du lot survit a une fabrique qui n'emploie qu'une seule ecriture.
    """
    assert reglages(cadence=saisie).cadence_source_transmise() is None


def test_une_cadence_DIVERGENTE_transmet_et_porte_la_note_DU_COEUR():
    """`EPIC11-ARB-185` : « l'avertissement se lit la ou le coeur le rend. »

    La note est celle de `resolve_source_rate`, verbatim : elle nomme les deux
    valeurs et leur provenance. Aucune phrase de l'ecran ne la remplace.
    """
    modele = reglages(cadence="30")
    assert modele.cadence_source_transmise() == "30/1"
    attendue = encode.resolve_source_rate(
        modele.lot.lot, cadence_source_override="30/1")[2]
    assert attendue is not None
    assert modele.note_du_coeur() == attendue
    lignes = modele.lignes_du_cartouche(jetons.largeur_utile())
    assert lignes, lignes
    assert jetons.GLYPHES["substitute"] in lignes[0]
    # Rien n'est perdu du message du coeur : il est **enveloppe**, pas abrege.
    assert "30" in " ".join(lignes) and "25" in " ".join(lignes)


def test_l_ensemble_des_situations_qui_AVERTISSENT_est_exactement_celui_la():
    """Trois situations, et deux seulement portent un cartouche.

    Ensemble exact : une assertion positive sur les deux qui avertissent
    laisserait passer un `▲` sur le cas nominal -- c'est-a-dire exactement le
    defaut qu'Egan a trouve dans la maquette precedente.
    """
    situations = {
        "nominal": reglages(),
        "cadence corrigee": reglages(cadence="30"),
        "lot sans cadence": reglages(lot=lot_sans_cadence(), cadence="25"),
    }
    avertissantes = {nom for nom, modele in situations.items()
                     if modele.lignes_du_cartouche(jetons.largeur_utile())}
    assert avertissantes == {"cadence corrigee", "lot sans cadence"}


def test_le_cartouche_est_colorise_ENTIEREMENT_et_jamais_une_ligne_sur_deux():
    """`EPIC11-ARB-71` : ses deux lignes sont **un seul objet**."""
    modele = reglages(lot=lot_sans_cadence(), cadence="25")
    lignes = modele.lignes_du_cartouche(jetons.largeur_utile())
    assert len(lignes) == len(
        reglages_exports.AVERTISSEMENT_CADENCE_ABSENTE) == 2
    etats = modele.etats_du_cartouche(0, len(lignes))
    assert etats == {0: reglages_exports.ETAT_DE_L_AVERTISSEMENT,
                     1: reglages_exports.ETAT_DE_L_AVERTISSEMENT}


def test_la_saisie_de_cadence_est_REFUSEE_par_la_grammaire_du_depot():
    """La grammaire n'est pas reecrite ici : `cadences.analyser_la_saisie` est
    la seule redaction du depot de ce que l'operateur a le droit de taper."""
    modele = reglages(lot=lot_sans_cadence(), cadence="abc")
    assert modele.cadence_retenue is None
    assert modele.refus_de_la_cadence is not None
    assert modele.peut_encoder is False
    # Un champ VIDE n'est pas une faute de frappe : c'est l'etat d'ouverture de
    # `E4-2b`, et le cartouche le dit deja. Deux messages pour un seul manque
    # seraient un de trop.
    vide = reglages(lot=lot_sans_cadence())
    assert vide.refus_de_la_cadence is None
    assert vide.peut_encoder is False


# ===========================================================================
# E8 -- AC 6.7 : la ligne d'etat ne porte AUCUNE touche
# ===========================================================================

def lignes_d_etat_du_corpus() -> dict[str, str]:
    """Les quatre lignes d'etat atteignables de cet ecran.

    Un corpus de quatre plutot qu'une : une garde posee sur une seule ligne
    resterait verte sur les trois autres, et c'est la ligne de refus qui porte
    le texte le moins maitrise -- il vient d'un autre module.
    """
    return {
        "nominal": reglages(mesure=mesure_de_e4_2()).ligne_d_etat(),
        "sans mesure": reglages().ligne_d_etat(),
        "sans cadence": reglages(lot=lot_sans_cadence(), cadence="25",
                                 mesure=mesure_de_e4_2b()).ligne_d_etat(),
        "refus": reglages(cadence="abc").ligne_d_etat(),
    }


@pytest.mark.parametrize("nom", sorted(lignes_d_etat_du_corpus()))
def test_la_ligne_d_etat_ne_porte_AUCUNE_touche(nom):
    """`EPIC11-ARB-56` : « aucune touche -- une touche va a la ligne des
    raccourcis »."""
    ligne = lignes_d_etat_du_corpus()[nom]
    for touche in ("Tab", "Échap", "F1", "⏎", "↑↓", "Entrée", "Espace"):
        assert touche not in ligne, (nom, ligne)


@pytest.mark.parametrize("nom", sorted(lignes_d_etat_du_corpus()))
def test_la_ligne_d_etat_ne_porte_aucun_MOTIF_DE_CONCEPTION(nom):
    """`EPIC11-ARB-56`, second volet : « aucun conseil d'usage [...] aucun
    motif de conception »."""
    ligne = lignes_d_etat_du_corpus()[nom].lower()
    for interdit in ("écran cible", "ecran cible", "story", "pour choisir",
                     "appuyez", "vous pouvez", "il faut"):
        assert interdit not in ligne, (nom, ligne)


def test_la_ligne_d_etat_du_cas_nominal_dit_ce_qui_SERA_ECRIT():
    modele = reglages(mesure=mesure_de_e4_2())
    ligne = modele.ligne_d_etat()
    assert ligne.startswith(f"{codec_profiles.DEFAULT_PROFILE_ID} · .mov")
    assert "1920×1080" in ligne
    assert "124 échantillons" in ligne
    assert "~ 1,4 Go" in ligne


def test_les_segments_INCONNUS_disparaissent_au_lieu_de_sortir_a_zero():
    """Un poids inconnu ne s'ecrit pas `0 Go`, et une geometrie native ne
    s'invente pas avant d'avoir sonde les frames."""
    sans_mesure = reglages().ligne_d_etat()
    assert "échantillons" not in sans_mesure and "~" not in sans_mesure
    assert sans_mesure.endswith("à 25 fps")
    native = reglages(resolution=encode.NATIVE_RESOLUTION_KEYWORD,
                      mesure=mesure_de_e4_2()).ligne_d_etat()
    assert "×" not in native
    assert "à 25 fps" in native
    # Le poids seul, sans cardinal : les deux segments sont independants.
    poids_seul = reglages(
        mesure=reglages_exports.MesureDuMaster(poids_octets=1024 ** 3)
    ).ligne_d_etat()
    assert "échantillons" not in poids_seul and "1,0 Go" in poids_seul


def test_les_MAINTIENS_sont_rendus_en_ENSEMBLE_et_jamais_par_le_premier():
    """`encode._hold_counts` rend un maintien par frame : constants quand le
    rapport des cadences est entier, **alternants** sinon.

    La fabrique alternante porte ses deux valeurs **dans l'ordre 2, 1, 2** : la
    cible est au milieu, et rendre le premier maintien donnerait `2` la ou la
    sequence en tient aussi des `1`.
    """
    constants = reglages(
        mesure=reglages_exports.MesureDuMaster(maintiens=(2, 2, 2)))
    assert constants.texte_des_maintiens() == "2"
    alternants = reglages(
        mesure=reglages_exports.MesureDuMaster(maintiens=(2, 1, 2)))
    assert alternants.texte_des_maintiens() == "1 et 2"
    assert reglages().texte_des_maintiens() is None


@pytest.mark.parametrize("secondes,attendu", [
    (5.0, "5 s 00"),
    (4.96, "4 s 96"),
    (4.999, "5 s 00"),     # `4 s 100` n'existe pas
    (0.0, "0 s 00"),
])
def test_la_duree_s_ecrit_a_la_CENTIEME(secondes, attendu):
    """C'est une troisieme forme de duree, et elle n'est interchangeable avec
    aucune des deux autres : un master de cinq secondes se compare a la duree
    du rushe dont il vient, et la seconde entiere y perd ce qu'on verifie."""
    assert reglages_exports.texte_de_duree(secondes) == attendu


def test_une_duree_inconnue_ne_s_ecrit_PAS_zero():
    assert reglages_exports.texte_de_duree(None) is None
    assert reglages_exports.texte_de_duree(-1.0) is None


# ===========================================================================
# E9 -- le produit contre le DESSIN valide, ligne par ligne
# ===========================================================================

MAQUETTE_E4_2 = "E4-2-exports-reglages.txt"
MAQUETTE_E4_2B = "E4-2b-exports-cadence-modifiee.txt"


def modele_de_e4_2() -> reglages_exports.ReglagesDeL_encodage:
    return reglages(mesure=mesure_de_e4_2())


def modele_de_e4_2b() -> reglages_exports.ReglagesDeL_encodage:
    return reglages(lot=lot_sans_cadence(), cadence="25",
                    mesure=mesure_de_e4_2b())


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_2, modele_de_e4_2),
    (MAQUETTE_E4_2B, modele_de_e4_2b),
])
def test_le_corps_rendu_est_celui_de_la_maquette(nom, fabrique):
    """Le produit contre le dessin **valide**, ligne par ligne.

    C'est la mesure la plus forte de cet ecran : elle attrape a la fois une
    colonne qui glisse, un chiffre qui change et un glyphe qui se deplace, et
    elle rougirait si une maquette etait regeneree sans que le produit suive.
    """
    assert corps(fabrique()) == centre_de_la_maquette(nom)


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_2, modele_de_e4_2),
    (MAQUETTE_E4_2B, modele_de_e4_2b),
])
def test_la_ligne_de_raccourcis_est_celle_de_la_maquette(nom, fabrique):
    assert fabrique().raccourcis() == raccourcis_de_la_maquette(nom)


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_2, modele_de_e4_2),
    (MAQUETTE_E4_2B, modele_de_e4_2b),
])
def test_la_ligne_d_etat_est_celle_de_la_maquette(nom, fabrique):
    assert fabrique().ligne_d_etat() == etat_de_la_maquette(nom)


def test_les_deux_maquettes_dessinent_bien_DEUX_etats_differents():
    """Volet symetrique des trois mesures ci-dessus.

    Sans lui, deux maquettes identiques rendraient les comparaisons vertes pour
    rien -- et c'est precisement ce qui vient de changer : `E4-2b` a change de
    nature deux fois en deux passes.
    """
    assert corps(modele_de_e4_2()) != corps(modele_de_e4_2b())
    assert modele_de_e4_2().raccourcis() != modele_de_e4_2b().raccourcis()
    assert modele_de_e4_2().ligne_d_etat() != modele_de_e4_2b().ligne_d_etat()


def test_le_bandeau_porte_le_lot_travaille():
    """`plan-04_25 · 124 f`, comme la droite du bandeau des deux maquettes."""
    assert modele_de_e4_2().objet_du_bandeau() == "plan-04_25 · 124 f"
    assert modele_de_e4_2b().objet_du_bandeau() == "plan-04_12p5 · 63 f"


# ===========================================================================
# E10 -- `⏎`, la seule issue de l'ecran
# ===========================================================================

def test_entree_valide_et_appelle_la_suite_avec_les_reglages():
    vus = []
    modele = modele_de_e4_2()
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele,
                                                       continuer=vus.append)
    assert ecran.traiter("enter") is True
    assert vus == [modele]


def test_entree_n_appelle_PAS_la_suite_quand_le_coeur_refuserait():
    """`EPIC11-ARB-17` : l'ecran ne mene jamais a un couple que le coeur
    refuse. Le refus **se dit** en ligne d'etat plutot que de laisser la touche
    muette."""
    vus = []
    modele = reglages(lot=lot_sans_cadence())
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele,
                                                       continuer=vus.append)
    assert ecran.traiter("enter") is True      # la touche est consommee
    assert vus == []                            # et rien n'est valide
    assert modele.lignes_du_cartouche(jetons.largeur_utile()), (
        "le manque doit etre dit quelque part")


def test_entree_SANS_appelant_nomme_ce_qui_manque_au_lieu_de_se_taire():
    """`K1.1a` : un `if ... is not None` sans branche `else` rend la touche
    indistinguable d'un clavier casse.

    La branche est un **filet**, pas une promesse : elle ne se retire pas le
    jour du cablage -- un futur appelant qui oublierait le mot-cle retomberait
    dessus.
    """
    modele = modele_de_e4_2()
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    assert reglages_exports.CE_QUI_MANQUE_APRES_LES_REGLAGES
    assert reglages_exports.QUAND_LA_CONFIRMATION
    appels = []
    ecran._pas_encore = lambda: appels.append(True)
    assert ecran.traiter("enter") is True
    assert appels == [True]


# ===========================================================================
# E11 -- la grille, le repli ASCII et la table des glyphes
# ===========================================================================

@pytest.mark.parametrize("ligne", [reglages_exports.RACCOURCIS_CHOIX,
                                   reglages_exports.RACCOURCIS_SAISIE])
def test_les_lignes_de_raccourcis_tiennent_la_grille_dans_les_DEUX_regimes(
        ligne):
    """`textual` REPLIE une ligne trop longue au lieu de la tronquer : sur une
    zone de hauteur 1, la fin disparait sans bruit."""
    assert jetons.colonnes(ligne) <= jetons.largeur_utile()
    replie = jetons.replier_ascii(ligne)
    assert replie.isascii(), replie
    assert jetons.colonnes(replie) <= jetons.largeur_utile()


@pytest.mark.parametrize("fabrique", [modele_de_e4_2, modele_de_e4_2b,
                                      lambda: reglages(cadence="30")])
@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_du_corps_ne_deborde_ni_ne_porte_de_glyphe_HORS_TABLE(
        fabrique, ascii_seul):
    modele = fabrique()
    lignes = corps(modele, ascii_seul) + [modele.ligne_d_etat(ascii_seul)]
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(), ligne
        assert glyphes_hors_table(ligne, ascii_seul) == set(), ligne


@pytest.mark.parametrize("fabrique", [modele_de_e4_2, modele_de_e4_2b,
                                      lambda: reglages(cadence="30")])
def test_en_repli_ASCII_tout_l_ecran_est_de_l_ASCII_PUR(fabrique):
    """Une table complete ne prouve pas un repli complet : c'est ce qui a
    laisse passer `1920×1080` -> `1920?1080` jusqu'au 2026-08-29, et c'est ce
    que le marqueur de deroulant aurait refait."""
    modele = fabrique()
    for ligne in corps(modele, True) + [modele.ligne_d_etat(True)]:
        assert ligne.isascii(), ligne
        assert "?" not in ligne, ligne


def test_le_corps_tient_la_HAUTEUR_de_la_zone_centrale():
    """Le cas le plus haut de cet ecran : la liste ouverte **et** un cartouche
    d'avertissement. `textual` coupe par le bas, en silence.

    C'est exactement le defaut `I1` que `Composition` ferme, et il ne se voit
    que sur la composition la plus chargee.
    """
    modele = reglages(cadence="30", champ=reglages_exports.CHAMP_PROFIL,
                      mesure=mesure_de_e4_2())
    assert modele.lignes_du_cartouche(jetons.largeur_utile()), "cas non atteint"
    assert len(corps(modele)) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER


# ===========================================================================
# E12 -- AC 11.2 : le module ne nomme jamais `cli`
# ===========================================================================

def test_le_module_n_importe_PAS_cli():
    """`EPIC11-ARB-67`. Mesure a l'arbre syntaxique : la prose du module parle
    de la ligne de commande pour dire qu'elle ne l'appelle pas."""
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    modules = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            modules.add(noeud.module or "")
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Import, ast.ImportFrom)):
            modules.update(alias.name for alias in noeud.names)
    assert not any("cli" in nom.split(".") for nom in modules), modules
    # Le volet symetrique : il importe bien le coeur, sans quoi la frontiere
    # serait verte sur un module qui n'importerait rien du tout -- et une
    # frontiere qui ne mesure rien est le seul defaut qu'elle ne voit pas.
    assert {"codec_profiles", "encode"} <= modules, sorted(modules)


def test_le_module_ne_recopie_AUCUN_code_de_refus_du_coeur():
    """AC 11.2 : les codes du vocabulaire ferme se lisent, ils ne s'ecrivent
    pas. `CADENCE_SOURCE_MANQUANTE` est nomme par sa constante."""
    litteraux = set(chaines_du_code(SOURCE_DU_MODULE))
    assert encode.ENCODE_SOURCE_RATE_MISSING not in litteraux
    assert "encode.ENCODE_SOURCE_RATE_MISSING" in SOURCE_DU_MODULE.read_text(
        encoding="utf-8")


def test_la_fraction_du_lot_traverse_sans_perdre_son_exactitude():
    """Une cadence NTSC n'est pas un decimal, et l'ecran ne la degrade pas.

    `24000/1001` s'ecrit `23,976` a l'ecran et **reste** `24000/1001` pour le
    coeur : c'est la meme regle que `cadences.nom_court_de_cadence` -- le rendu
    ne remonte jamais dans le modele.
    """
    lot = reglages_exports.LotAEncoder.du_manifest(
        {"lot_id": "ntsc_24", "timecode_base_fps": "24000/1001"}, 48)
    modele = reglages(lot=lot)
    assert lot.cadence_source == "24000/1001"
    # **Le champ ne porte PAS `23,976`** : ce rendu se relit `2997/125`, et
    # preremplir avec lui ferait annoncer un ecrasement de cadence sur le seul
    # fait d'avoir ouvert un lot NTSC.
    assert cadences.texte_de_cadence(Fraction(24000, 1001)) == "23,976"
    assert modele.cadence == "24000/1001"
    assert modele.cadence_retenue == Fraction(24000, 1001)
    assert modele.cadence_source_transmise() is None
    assert modele.note_du_coeur() is None
    assert modele.lignes_du_cartouche(jetons.largeur_utile()) == []
    # Le volet symetrique : sur une cadence dont le decimal EST exact, c'est
    # bien le decimal qui entre -- sinon `E4-2` porterait `25/1`.
    assert reglages().cadence == "25"


# ===========================================================================
# E13 -- l'ecran MONTE, et il rend ce que le modele compose
#
# Tout ce qui precede mesure un modele pur. Un ecran qui composerait
# parfaitement et ne peindrait rien serait vert sur les quatre-vingt-dix-neuf
# mesures ci-dessus : c'est le mode de panne que seul le montage voit, et il a
# ete paye trois fois dans cet epic sous la forme d'un composant que rien ne
# cable.
# ===========================================================================

def coque(ecran, ascii_seul: bool = False) -> CoqueTui:
    """Deux paliers temoins, puis l'ecran mesure au sommet."""
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"),
                    ascii_seul=ascii_seul)


def monter(banc, ecran, ascii_seul: bool = False):
    """Monter l'ecran au plancher et rendre ce que le test veut lire."""
    app = coque(ecran, ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        courant = pilote.app.screen
        etat = jetons.texte_affiche(str(courant.query_one("#etat").content))
        raccourcis = jetons.texte_affiche(
            str(courant.query_one("#raccourcis").content))
        bandeau = jetons.texte_affiche(
            str(courant.query_one("#bandeau").content))
        blocs = [jetons.texte_affiche(str(widget.content))
                 for widget in courant.query_one("#centre").query("Static")]
        return etat, raccourcis, bandeau, blocs

    return banc(app, scenario)


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_2, modele_de_e4_2),
    (MAQUETTE_E4_2B, modele_de_e4_2b),
])
def test_l_ecran_MONTE_rend_les_trois_zones_de_la_maquette(banc, nom,
                                                           fabrique):
    """Les trois zones que la grille porte, lues sur l'ecran REEL.

    Le bandeau est la mesure qui compte le plus ici : `objet_du_bandeau` est
    servi par `ObjetTravaille`, et le defaut `I3` de cet epic est **exactement**
    un objet de bandeau livre, teste et jamais pose -- la droite du bandeau
    etait vide sur les douze ecrans, et aucun banc de modele ne le voyait.
    """
    modele = fabrique()
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    etat, raccourcis, bandeau, blocs = monter(banc, ecran)
    assert etat == modele.ligne_d_etat()
    assert raccourcis == modele.raccourcis()
    assert modele.objet_du_bandeau() in bandeau
    assert blocs, "la zone centrale doit porter le corps"
    assert blocs[0].split("\n")[:3] == corps(modele)[:3]


def test_l_ecran_MONTE_suit_le_clavier_jusqu_au_champ_de_cadence(banc):
    """`Tab` deux fois : la ligne de raccourcis et la ligne d'etat SUIVENT.

    C'est la moitie que le modele ne peut pas mesurer -- `poser_les_raccourcis`
    est appelee par `rafraichir`, pas par le modele, et une ligne contextuelle
    qui ne serait reassignee nulle part resterait figee a l'ecran.
    """
    modele = modele_de_e4_2()
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele)
    app = coque(ecran)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        avant = jetons.texte_affiche(
            str(pilote.app.screen.query_one("#raccourcis").content))
        await pilote.press("tab", "tab")
        await pilote.pause()
        apres = jetons.texte_affiche(
            str(pilote.app.screen.query_one("#raccourcis").content))
        await pilote.press("3", "0")
        await pilote.pause()
        return avant, apres, jetons.texte_affiche(
            str(pilote.app.screen.query_one("#etat").content))

    avant, apres, etat = banc(app, scenario)
    assert avant == reglages_exports.RACCOURCIS_CHOIX
    assert apres == reglages_exports.RACCOURCIS_SAISIE
    # Les deux chiffres sont entres dans le champ, et la ligne d'etat a suivi.
    assert modele.champ == reglages_exports.CHAMP_CADENCE
    assert modele.cadence == "2530"
    assert etat == modele.ligne_d_etat()


def test_le_bandeau_se_lit_SANS_application_montee():
    """Un ecran construit a nu par un banc n'a pas d'application ou lire le
    regime d'affichage : `textual` fait de `Screen.app` une propriete qui
    **leve** hors montage, y compris a travers `getattr(..., None)`."""
    ecran = reglages_exports.EcranReglagesDeL_encodage(modele_de_e4_2())
    assert ecran.objet_du_bandeau() == "plan-04_25 · 124 f"


def test_un_cartouche_qui_ne_TIENT_PAS_ne_pose_pas_son_glyphe_seul():
    """Un `▲` sans texte avertirait de rien, et c'est pire que rien.

    La largeur nulle est le cas limite d'`envelopper` : elle rend une liste
    vide, et une premiere redaction indexait `phrases[0]` juste apres.
    """
    modele = reglages(cadence="30")
    assert modele.lignes_du_cartouche(jetons.largeur_utile()), "cas non atteint"
    assert modele.lignes_du_cartouche(0) == []
