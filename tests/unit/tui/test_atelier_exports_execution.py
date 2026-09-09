# -*- coding: utf-8 -*-
"""`E4-4` / `E4-4b` et `T6-1` -- l'execution de l'encodage (11.8, lot F, AC 9).

**L'AC 9.3 EST TOMBEE, et ce banc le dit plutot que de le taire.** Elle
conditionnait une barre chiffree sur la pre-verification au lot `B3` ; ce lot a
quitte le perimetre avec `EPIC11-ARB-184` et est devenu la story 6.7,
developpee ailleurs. Rien ici ne mesure une barre, et
:func:`test_AC_9_3_est_TOMBEE_aucune_etape_ne_porte_de_barre` en fait une
**frontiere negative** plutot qu'un silence : le jour ou une barre reviendrait
sans la story 6.7, elle rougirait.

**Le coeur de ce banc est l'AC 9.2, et elle est negative.** Une frontiere
negative est le seul moyen d'attraper la reintroduction d'un defaut : aucun
test positif ne verrait revenir le « ▓▓▓ 64 % · 79/124 frames · reste ~ 22 s »
de la maquette d'origine. Le detecteur est donc **double** -- il rougit sur la
ligne fabriquee que la maquette portait, et il reste muet sur tout ce que
l'ecran rend --, et l'invariant se mesure par une **egalite d'ensemble** :
« l'ensemble des etats de l'ecran qui portent un chiffre d'avancement est
exactement vide », jamais « cette etape porte un rotor ».

**Regle des fabriques.** Les quatre etapes sont une suite ordonnee, et les
fabriques placent la cible **au milieu** : `encodage` est la deuxieme des
quatre, `verification` la troisieme, et aucun test de parcours ne se contente
de la premiere -- un `find` fautif qui rend toujours le premier element ne se
demasque pas autrement. Les deux cardinaux du passage sont **distinguables**
(124 frames pour 125 echantillons sur le lot 12p5), sans quoi rendre les
frames et rendre les echantillons seraient indiscernables.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re
import sys
import textwrap
import types

import pytest

_RACINE = pathlib.Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import codec_profiles, encode, encode_master  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.tui import jetons  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_exports_execution as execution_exports,
    execution as execution_partagee,
)
from mixed_media_utility.tui.atelier_pdf_calibration import (  # noqa: E402
    RACCOURCIS_MIRE_EN_COURS,
)
from mixed_media_utility.tui.panneau import ChoixExclusif  # noqa: E402

MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
SOURCE_DU_MODULE = pathlib.Path(execution_exports.__file__)

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]


# ===========================================================================
# Les fabriques
# ===========================================================================

def passage_nominal(**champs) -> execution_exports.PassageDeLEncodage:
    """Le passage de `E4-4` : un lot 25p, ou frames et echantillons coincident."""
    champs.setdefault("lot_id", "plan-04_25")
    champs.setdefault("frames", 124)
    champs.setdefault("nom_du_master", "plan-04_25_mmu_prores_hq.mov")
    champs.setdefault("dossier", "projet_demo/outputs/")
    champs.setdefault("mesure", execution_exports.MesureDuMaster(
        echantillons=124, poids_octets=int(1.4 * 1024 ** 3)))
    return execution_exports.PassageDeLEncodage(**champs)


def passage_decime(**champs) -> execution_exports.PassageDeLEncodage:
    """Le lot 12p5 ne d'un rushe 25p : **63 frames pour 125 echantillons**.

    C'est la fabrique qui rend les deux cardinaux distinguables. Sur le lot de
    demonstration ils valent tous deux 124, et un banc qui n'aurait que celui-la
    ne verrait pas la difference entre « les frames a ouvrir » et « les
    echantillons a monter » -- exactement le defaut d'appariement que la regle
    des fabriques vise.
    """
    champs.setdefault("lot_id", "plan-04_12p5")
    champs.setdefault("frames", 63)
    champs.setdefault("nom_du_master", "plan-04_12p5_mmu_prores_hq.mov")
    champs.setdefault("dossier", "projet_demo/outputs/")
    champs.setdefault("mesure", execution_exports.MesureDuMaster(
        echantillons=125, poids_octets=int(2.7 * 1024 ** 3)))
    return execution_exports.PassageDeLEncodage(**champs)


def plan_temoin(tmp_path, *, overwrite: bool = False):
    """Un `encode.EncodePlan` **reel**, assez peuple pour `execute_plan`.

    Les trois objets composites (`resolution`, `timecode`, `verdict`) sont des
    doubles : `execute_plan` ne lit d'eux que `size` et `emitted` avant
    d'appeler la fabrique, et la fabrique est doublee ici. Ce qui compte est
    que le PLAN soit celui du produit -- c'est lui qui porte `output_path`,
    donc la reservation atomique que l'AC 9.6 mesure.
    """
    projet = tmp_path / "projet_demo"
    (projet / project_layout.OUTPUTS_DIRNAME).mkdir(parents=True)
    frames = tuple(projet / f"frame_{rang:03d}.tiff" for rang in range(3))
    return encode.EncodePlan(
        project_dir=projet,
        lot_id="plan-04_25",
        lot_state="reconstruction",
        profile_id=codec_profiles.DEFAULT_PROFILE_ID,
        container="mov",
        resolution=types.SimpleNamespace(size=(1920, 1080)),
        source_size=(1920, 1080),
        frame_paths=frames,
        frame_rate=25.0,
        exact_frame_rate="25/1",
        timecode=types.SimpleNamespace(emitted="00:00:00:00"),
        verdict=types.SimpleNamespace(),
        container_tags={},
        output_path=(projet / project_layout.OUTPUTS_DIRNAME
                     / "plan-04_25_mmu_prores_hq.mov"),
        overwrite=overwrite,
        muxed_frame_paths=frames,
    )


def _cadre(nom: str) -> list[str]:
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")[:24]
    return [ligne for ligne in lignes if ligne.startswith("│")]


def centre_de_la_maquette(nom: str) -> list[str]:
    """Les lignes de la zone centrale d'une maquette, marge de gauche retiree."""
    centre = [ligne[2:-1].rstrip() for ligne in _cadre(nom)[1:-2]]
    while centre and not centre[-1]:
        centre.pop()
    return centre


def etat_de_la_maquette(nom: str) -> str:
    return _cadre(nom)[-2][2:-1].rstrip()


def raccourcis_de_la_maquette(nom: str) -> str:
    return _cadre(nom)[-1][2:-1].rstrip()


def bandeau_de_la_maquette(nom: str) -> str:
    return _cadre(nom)[0][2:-1].rstrip()


def corps(passage, ascii_seul: bool = False) -> list[str]:
    """Les lignes du corps, telles que le rendu les peindrait."""
    ecran = execution_exports.EcranEncodageEnCours(passage)
    return [ligne.rstrip()
            for ligne in ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0]]


def tout_ce_qui_s_affiche(passage, ascii_seul: bool = False) -> list[str]:
    """**Tout** ce que l'operateur lit : corps, ligne d'etat, raccourcis, bandeau.

    Une frontiere posee sur le seul corps laisserait passer un pourcentage en
    ligne d'etat -- qui est justement l'endroit ou la maquette d'origine
    l'ecrivait.
    """
    return [*corps(passage, ascii_seul),
            passage.ligne_d_etat(ascii_seul),
            passage.objet_du_bandeau(ascii_seul),
            (jetons.replier_ascii(execution_exports.RACCOURCIS_ENCODAGE_EN_COURS)
             if ascii_seul
             else execution_exports.RACCOURCIS_ENCODAGE_EN_COURS)]


def tous_les_etats(fabrique=passage_nominal):
    """Le passage dans **chacune** de ses quatre etapes, dans l'ordre.

    Quatre et non une : une frontiere posee sur le seul etat d'ouverture ne
    verrait pas un chiffre qui n'apparaitrait qu'a la troisieme etape.
    """
    for etape in execution_exports.ETAPES:
        yield etape.cle, fabrique(etape=etape.cle)


def corps_de_classe(nom: str) -> set[str]:
    """Les noms que le CORPS de `nom` pose, lus sur l'arbre syntaxique.

    Ni `vars()` ni `dir()` : `textual` injecte une trentaine de membres a la
    definition d'une classe d'ecran, et ils noieraient toute egalite. Ce qui se
    mesure ici est ce que **ce module** a ecrit.
    """
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ClassDef) and noeud.name == nom:
            poses = set()
            for enfant in noeud.body:
                if isinstance(enfant, ast.Assign):
                    poses |= {cible.id for cible in enfant.targets
                              if isinstance(cible, ast.Name)}
                elif isinstance(enfant, ast.AnnAssign) and isinstance(
                        enfant.target, ast.Name):
                    poses.add(enfant.target.id)
                elif isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    poses.add(enfant.name)
            return poses
    raise AssertionError(f"classe introuvable dans le module : {nom}")


# ===========================================================================
# Le detecteur de chiffre d'avancement, et son TEMOIN
# ===========================================================================

#: Ce qu'un chiffre d'avancement ressemble, dans les quatre formes que la
#: maquette d'origine portait et que l'AC 9.2 interdit.
#:
#: * un **pourcentage** : `64 %` ;
#: * un **`n/N`** : `79/124` ;
#: * une **estimation de temps restant** : `reste ~ 22 s` -- le mot suffit, la
#:   grammaire du `DESIGN.md` section 8 n'en connait pas d'autre ;
#: * une **barre**, dans ses deux dessins et leurs deux replis ASCII. Elle est
#:   lue de `jetons.GLYPHES`, jamais recopiee : une barre qui changerait de
#:   dessin echapperait sinon a la mesure sans que rien ne rougisse.
_BARRES = "".join(
    jetons.GLYPHES[nom] + jetons.GLYPHES_ASCII[nom]
    for nom in ("barre-pleine", "barre-vide"))

MOTIFS_D_AVANCEMENT = (
    re.compile(r"\d\s*%"),
    re.compile(r"\d\s*/\s*\d"),
    re.compile(r"\breste\b", re.IGNORECASE),
    re.compile(f"[{re.escape(_BARRES)}]{{2,}}"),
)


def chiffres_d_avancement(texte: str) -> list[str]:
    """Ce que `texte` porte de compte d'avancement. Vide quand il n'en porte pas."""
    trouves = []
    for motif in MOTIFS_D_AVANCEMENT:
        trouves.extend(motif.findall(texte))
    return trouves


#: **La ligne exacte que la maquette d'origine portait**, et que la mesure a
#: fait retirer. Elle est le temoin du detecteur : sans elle, une frontiere qui
#: aurait cesse de mesurer resterait verte pour rien.
LIGNE_FABRIQUEE = "▓▓▓ 64 % · 79/124 frames · reste ~ 22 s"


def test_le_detecteur_de_chiffres_ROUGIT_sur_la_ligne_que_la_mesure_a_retiree():
    """Volet positif de l'AC 9.2, et il est litteral.

    Les quatre motifs sont confrontes **un par un** : un detecteur qui n'en
    tiendrait plus qu'un resterait vert sur cette ligne-la, donc paraitrait
    mesurer alors qu'il ne verrait qu'un quart du defaut.
    """
    assert chiffres_d_avancement(LIGNE_FABRIQUEE)
    muets = [motif.pattern for motif in MOTIFS_D_AVANCEMENT
             if not motif.search(LIGNE_FABRIQUEE)]
    assert muets == [], muets


def test_le_detecteur_reste_MUET_sur_une_ligne_d_etape_ordinaire():
    """Volet symetrique : un detecteur qui rougirait sur tout n'attraperait rien.

    La ligne choisie porte deux nombres -- `124 frames sur 124` -- et ce n'est
    pas un `n/N` : c'est le constat d'une etape qui a ouvert tout ce qu'elle
    avait a ouvrir, et le mot `sur` n'est pas une barre de fraction.
    """
    assert chiffres_d_avancement(
        "     ● Pré-vérification    124 frames sur 124            conforme") == []


# ===========================================================================
# AC 9.1 -- le rotor est present sur l'etape qui attend
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_AC_9_1_l_etape_en_cours_porte_le_ROTOR_dans_les_quatre_etats(ascii_seul):
    """Le glyphe est celui de `jetons`, jamais un caractere ecrit en dur."""
    for cle, passage in tous_les_etats():
        attendu = jetons.rotor(passage.pas, ascii_seul)
        ligne = passage.ligne_de_l_etape(passage.etape_courante, ascii_seul)
        assert attendu in ligne, (cle, ligne)


def test_AC_9_1_l_ensemble_des_etapes_AU_ROTOR_est_EXACTEMENT_celle_en_cours():
    """L'invariant ET son unicite. « Cette phase porte un rotor » est faible.

    La cible est **au milieu** : `verification` est la troisieme des quatre, ni
    premiere ni derniere -- un rotor pose sur la premiere etape quoi qu'il
    arrive resterait vert sur un test qui n'ouvrirait que `E4-4b`.
    """
    passage = passage_nominal(etape=execution_exports.ETAPE_VERIFICATION)
    dessins = set(jetons.ROTOR)
    portent = {etape.cle for etape in execution_exports.ETAPES
               if set(passage.ligne_de_l_etape(etape)) & dessins}
    assert portent == {execution_exports.ETAPE_VERIFICATION}, sorted(portent)


def test_AC_9_1_le_rotor_TOURNE_et_ne_leve_pas_au_quatrieme_tour():
    """Le modulo est fait par `jetons.rotor` : un ecran qui compterait ses
    propres pas rendrait un `IndexError` apres quelques secondes reelles."""
    passage = passage_nominal()
    dessins = []
    for _ in range(len(jetons.ROTOR) * 2 + 1):
        dessins.append(passage.glyphe_du_rotor())
        passage.avancer_le_rotor()
    assert len(set(dessins)) == len(jetons.ROTOR), dessins
    assert dessins[0] == dessins[len(jetons.ROTOR)]


def test_les_quatre_dessins_du_rotor_ONT_leur_repli_ASCII():
    """Le defaut paye par le signe multiplier le 2026-08-29, et par `▾` le
    2026-09-03 : un dessin hors table sort en `?` sous `--ascii`."""
    manquants = [dessin for dessin in jetons.ROTOR
                 if jetons.replier_ascii(dessin) == "?"]
    assert manquants == [], manquants


@pytest.mark.parametrize("ascii_seul", MODES)
def test_AUCUN_glyphe_de_cet_ecran_ne_sort_en_POINT_D_INTERROGATION(ascii_seul):
    """La mesure qui compte pour de vrai : le repli du rendu ENTIER.

    Elle couvre le rotor, les glyphes d'etat, le `·` des separateurs et les
    accents -- c'est-a-dire tout ce que le lot D a paye sur `▾`.
    """
    for _cle, passage in tous_les_etats():
        for ligne in tout_ce_qui_s_affiche(passage, ascii_seul):
            replie = jetons.replier_ascii(ligne)
            assert "?" not in replie, (ligne, replie)


# ===========================================================================
# AC 9.2 -- la frontiere NEGATIVE, et c'est le coeur de ce lot
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("fabrique", [passage_nominal, passage_decime],
                         ids=["25p", "12p5"])
def test_AC_9_2_l_ensemble_des_LIGNES_qui_portent_un_chiffre_d_avancement_est_VIDE(
        fabrique, ascii_seul):
    """Une egalite d'ensemble sur **tout** ce que l'ecran affiche.

    Corps, ligne d'etat, bandeau et ligne de raccourcis, dans les quatre etapes
    et les deux regimes de rendu. Un chiffre invente est un mensonge
    d'interface, et il n'a pas besoin d'etre au centre pour l'etre.
    """
    fautives = {}
    for cle, passage in tous_les_etats(fabrique):
        for ligne in tout_ce_qui_s_affiche(passage, ascii_seul):
            trouves = chiffres_d_avancement(ligne)
            if trouves:
                fautives[f"{cle} :: {ligne}"] = trouves
    assert fautives == {}, fautives


def test_AC_9_2_l_ensemble_des_ETAPES_qui_portent_un_chiffre_est_EXACTEMENT_vide():
    """L'invariant du modele, mesure par egalite et non par appartenance."""
    for _cle, passage in tous_les_etats():
        assert passage.etapes_chiffrees() == (), passage.etape


def test_AC_9_2_un_JALON_du_coeur_ne_fait_apparaitre_AUCUN_chiffre():
    """Le cas le plus dur : le coeur a parle, et l'ecran se tait quand meme.

    C'est la moitie que la story 6.7 renversera. Aujourd'hui le jalon est
    **retenu** -- c'est le terrain prepare par `EPIC11-ARB-184` -- et il
    n'atteint aucune ligne. Les deux moities sont mesurees ensemble : un jalon
    perdu ne preparerait rien, un jalon rendu serait le mensonge de l'AC 9.2.
    """
    passage = passage_nominal(etape=execution_exports.ETAPE_ENCODAGE)
    avant = tout_ce_qui_s_affiche(passage)
    passage.noter(79, 124)
    assert passage.jalon == (79, 124)
    assert tout_ce_qui_s_affiche(passage) == avant


def test_AC_9_2_le_module_ne_NOMME_aucune_mecanique_de_progression():
    """Frontiere syntaxique, doublee de son volet symetrique.

    `Avancement`, `EstimateurTempsRestant`, `EmetteurProgression` et
    `SurfaceExecution` sont les quatre redactions du depot d'un compte qui
    avance. Aucune n'est nommee ici -- et le volet symetrique verifie qu'elles
    existent bien, sans quoi la frontiere serait verte parce qu'elle chercherait
    des noms disparus.
    """
    from mixed_media_utility import progression
    from mixed_media_utility.tui import avancement as module_avancement

    interdits = ("Avancement", "EstimateurTempsRestant", "EmetteurProgression",
                 "SurfaceExecution", "barre", "pourcentage")
    #: **Le volet symetrique** : chaque nom interdit doit exister quelque part
    #: dans le produit. Une frontiere qui chercherait des noms disparus serait
    #: verte parce qu'elle ne mesure plus rien.
    porteurs = {"Avancement": module_avancement,
                "barre": module_avancement,
                "pourcentage": module_avancement,
                "EstimateurTempsRestant": progression,
                "EmetteurProgression": progression,
                "SurfaceExecution": execution_partagee}
    assert set(porteurs) == set(interdits), sorted(set(porteurs) ^ set(interdits))
    absents = [nom for nom, porteur in porteurs.items()
               if not hasattr(porteur, nom)]
    assert absents == [], absents

    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    identifiants = {noeud.id for noeud in ast.walk(arbre)
                    if isinstance(noeud, ast.Name)}
    identifiants |= {noeud.attr for noeud in ast.walk(arbre)
                     if isinstance(noeud, ast.Attribute)}
    fautifs = sorted(set(interdits) & identifiants)
    assert fautifs == [], fautifs


def test_AC_9_3_est_TOMBEE_aucune_etape_ne_porte_de_barre():
    """`EPIC11-ARB-184` : le lot `B3` a quitte le perimetre, l'AC 9.3 avec lui.

    Elle n'est donc pas mesuree ici -- elle est **niee** : la pre-verification,
    seule des quatre a boucler sur un cardinal connu, ne porte pas plus de barre
    que les trois autres. Une barre qui reviendrait sans la story 6.7 rougirait
    ici.
    """
    barres = set(jetons.GLYPHES["barre-pleine"] + jetons.GLYPHES["barre-vide"])
    for cle, passage in tous_les_etats():
        for ligne in tout_ce_qui_s_affiche(passage):
            assert not (set(ligne) & barres), (cle, ligne)


# ===========================================================================
# AC 9.4 -- rien qui ne vienne du produit
# ===========================================================================

def test_AC_9_4_l_ecran_ne_porte_AUCUNE_zone_de_journal():
    """Le journal part, et la mesure le commande.

    `run_encode` capture la sortie de ffmpeg puis la **jette en cas de
    succes** : entre le recapitulatif emis avant et le rapport `ffprobe` emis
    apres, rien n'est ecrit. Annoncer `Tab journal` ouvrirait une page vide,
    donc ni la ligne de raccourcis ni l'ecran ne le nomment.
    """
    assert "journal" not in execution_exports.RACCOURCIS_ENCODAGE_EN_COURS.lower()
    assert "Tab" not in execution_exports.RACCOURCIS_ENCODAGE_EN_COURS
    membres = dir(execution_exports.EcranEncodageEnCours)
    assert [nom for nom in membres if "journal" in nom.lower()] == []


def test_AC_9_4_la_mesure_qui_le_JUSTIFIE_a_BASCULE_et_le_rotor_reste():
    """**Retourne par la story 6.7, lot C -- et c'est le signal annonce.**

    Ce banc asserait l'inverse : `run_encode` faisait **un seul**
    `subprocess.run` bloquant et `build_encode_command` ne portait **aucun**
    `-progress`. Sa docstring programmait sa propre bascule mot pour mot :
    "C'est la mesure qui fonde le rotor. Si elle changeait -- si ffmpeg se
    mettait a rendre la main -- ce banc rougirait, et c'est exactement le
    signal qu'il faut : l'ecran pourrait alors compter."

    **Ce que 6.7 rend POSSIBLE n'est pas ce qu'elle REND, et c'est tout
    l'objet de ce banc retourne.** ffmpeg rend desormais la main : l'argv
    porte `-progress` en option globale, `run_encode` ne lance plus rien
    lui-meme -- une couture porte les deux branches -- et le coeur emet des
    jalons. L'ecran POURRAIT donc compter. Il ne compte pas : rendre une barre
    demanderait de modifier `tui/`, ce que l'AC 9 de la story 6.7 interdit et
    ce que l'AC 9.2 de CETTE story-ci ferait rougir. **Le rotor reste**, et la
    story qui rendra la barre est la suivante.

    Les deux moities sont donc mesurees ensemble, et c'est ce qui fait la
    valeur du banc : la mecanique a bascule ET l'ecran est reste muet. Une
    seule des deux serait un demi-mensonge.
    """
    lances = [f"{noeud.func.value.id}.{noeud.func.attr}"
              for noeud in ast.walk(
                  ast.parse(textwrap.dedent(
                      inspect.getsource(codec_profiles.run_encode))))
              if isinstance(noeud, ast.Call)
              and isinstance(noeud.func, ast.Attribute)
              and isinstance(noeud.func.value, ast.Name)
              and noeud.func.value.id == "subprocess"]
    assert lances == [], lances

    argv = codec_profiles.build_encode_command(
        "prores_hq", "l.concat", 25, "o.mov",
        progress_target=codec_profiles.PROGRESS_TARGET_STDOUT)
    assert "-progress" in argv

    # **Et l'ecran est reste muet.** Le jalon arrive, aucune ligne ne bouge.
    passage = passage_nominal(etape=execution_exports.ETAPE_ENCODAGE)
    avant = tout_ce_qui_s_affiche(passage)
    passage.noter(79, 124)
    assert passage.jalon == (79, 124)
    assert tout_ce_qui_s_affiche(passage) == avant
    assert passage.etapes_chiffrees() == ()


def test_AC_9_4_les_deux_seuls_CARDINAUX_affiches_viennent_du_PLAN(tmp_path):
    """Le nom du master, le dossier, les frames et les echantillons sont **lus**.

    Aucun n'est recompose : `du_plan` les prend du plan que le coeur a decide,
    et les deux cardinaux restent **distincts** -- confondre `frame_count` et
    `muxed_frame_paths` ferait dire « encodage des 63 echantillons » sur un
    master qui en porte 125.
    """
    plan = plan_temoin(tmp_path)
    passage = execution_exports.PassageDeLEncodage.du_plan(plan)
    assert passage.lot_id == plan.lot_id
    assert passage.frames == plan.frame_count
    assert passage.echantillons == len(plan.muxed_frame_paths)
    assert passage.nom_du_master == plan.output_path.name
    assert passage.dossier == (f"{plan.project_dir.name}/"
                               f"{project_layout.OUTPUTS_DIRNAME}/")
    assert passage.mesure.poids_octets == plan.estimated_bytes


def test_AC_9_4_les_deux_cardinaux_ne_sont_PAS_le_meme_champ():
    """Volet symetrique du test ci-dessus, sur le lot qui les separe.

    Sur un lot 25p les deux valent 124 : un banc qui n'aurait que celui-la
    resterait vert si les deux lectures etaient echangees.
    """
    passage = passage_decime(etape=execution_exports.ETAPE_PREVERIFICATION)
    assert "63 frames" in passage.ligne_d_etat()
    passage.avancer_a(execution_exports.ETAPE_ENCODAGE)
    assert "125 échantillons" in passage.ligne_d_etat()


def test_un_segment_que_PERSONNE_n_a_mesure_disparait_au_lieu_de_sortir_a_zero():
    """Meme regle que la ligne d'etat de `E4-2`, et meme motif.

    Un poids inconnu ne s'ecrit pas `0 Go`, et « encodage des None
    echantillons » serait un chiffre invente par l'autre bout.
    """
    sans = passage_nominal(mesure=None,
                           etape=execution_exports.ETAPE_ENCODAGE)
    ligne = sans.ligne_d_etat()
    assert ligne == "Étape 2 sur 4", ligne
    partielle = passage_nominal(
        mesure=execution_exports.MesureDuMaster(echantillons=124),
        etape=execution_exports.ETAPE_ENCODAGE)
    assert partielle.ligne_d_etat() == (
        "Étape 2 sur 4 · encodage des 124 échantillons")


def test_le_dossier_de_bascule_est_COMPOSE_du_coeur_et_jamais_ecrit(tmp_path):
    """`io.project_layout.OUTPUTS_DIRNAME` est la seule redaction du depot."""
    assert execution_exports.dossier_de_sortie(tmp_path / "mon_projet") == (
        f"mon_projet/{project_layout.OUTPUTS_DIRNAME}/")
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    litteraux = {noeud.value for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Constant)
                 and isinstance(noeud.value, str)}
    assert project_layout.OUTPUTS_DIRNAME not in litteraux


# ===========================================================================
# AC 9.5 -- `T6-1` par SOUS-CLASSEMENT, et `execution.py` intact
# ===========================================================================

def test_AC_9_5_T6_1_est_une_SOUS_CLASSE_d_EcranInterruption():
    assert issubclass(execution_exports.EcranInterruptionDeLEncodage,
                      execution_partagee.EcranInterruption)


def test_AC_9_5_la_sous_classe_ne_substitue_QUE_ce_que_l_encodage_contredit():
    """Le patron de `EcranInterruptionDeDetection`, mesure et non suppose.

    Deux attributs propres et pas un de plus : les issues, et le titre de
    l'atelier au bandeau. Tout le reste -- le clavier, le rendu, l'`Echap` qui
    reprend au lieu de remonter, les invariants du choix -- est **herite**. Une
    sous-classe qui reecrirait `traiter` ou `valider` refabriquerait ce que
    `execution.py` tient deja pour trois ateliers.
    """
    # **La mesure est SYNTAXIQUE** : `vars()` d'une classe `textual` porte une
    # trentaine de membres injectes a la definition, qui noieraient l'egalite.
    # Le corps de classe ecrit dans ce module, lui, ne porte que ce que le lot
    # a substitue.
    ecrits = corps_de_classe("EcranInterruptionDeLEncodage")
    assert ecrits == {"ISSUES", "titre"}, sorted(ecrits)
    # Volet symetrique : la mesure sait bien LIRE un corps de classe, sans quoi
    # un ensemble vide passerait pour une sous-classe exemplaire.
    assert corps_de_classe("EcranEncodageEnCours") >= {"titre", "raccourcis"}
    assert execution_exports.EcranInterruptionDeLEncodage.titre \
        != execution_partagee.EcranInterruption.titre, (
            "le bandeau nomme bien l'ATELIER, pas la classe d'ecran")


def test_AC_9_5_les_TROIS_issues_generiques_d_EcranInterruption_sont_INTACTES():
    """Volet symetrique : ce lot ne touche pas `execution.py`.

    « Un autre lot y travaille peut-etre » -- et une sous-classe qui aurait
    modifie la classe mere au lieu d'en heriter se verrait ici.
    """
    generiques = [(issue.cle, issue.libelle, issue.ecrit)
                  for issue in execution_partagee.EcranInterruption.ISSUES]
    assert generiques == [
        ("garder", "Interrompre et garder ce qui est deja ecrit", False),
        ("effacer", "Interrompre et effacer ce qui est deja ecrit", True),
        ("reprendre", "Reprendre l'execution", False),
    ], generiques


def test_AC_9_5_les_DEUX_issues_de_l_encodage_n_ECRIVENT_ni_l_une_ni_l_autre():
    """Et c'est plus fort que l'invariant du choix exclusif, pas plus faible.

    Proposer d'effacer ce qu'on n'a pas ecrit serait un choix qui ment sur
    l'etat du disque : tant que `E4-4` est a l'ecran, aucun master n'est pose
    (AC 9.6, mesure plus bas).
    """
    issues = execution_exports.ISSUES_DE_L_INTERRUPTION
    assert [issue.cle for issue in issues] == [
        execution_exports.CLE_INTERROMPRE,
        execution_partagee.EcranInterruption.REPRENDRE]
    ecrivent = {issue.cle for issue in issues if issue.ecrit}
    assert ecrivent == set(), sorted(ecrivent)


def test_AC_9_5_la_cle_de_REPRISE_est_LUE_de_la_classe_mere():
    """Par identite, jamais recopiee : c'est la mere qui la compare dans
    `traiter` et dans `issue_d_interruption`, et deux chaines egales
    aujourd'hui divergeraient a la premiere correction faite d'un seul cote."""
    reprise = execution_exports.ISSUES_DE_L_INTERRUPTION[-1]
    assert reprise.cle is execution_partagee.EcranInterruption.REPRENDRE


def test_le_choix_de_T6_1_leve_ses_invariants_sans_qu_on_les_reecrive():
    """Deux issues actionnables, aucune preselectionnee qui ecrive
    (`EPIC11-ARB-7`). L'invariant est celui de `ChoixExclusif`, pose une fois
    pour tout le depot."""
    choix = ChoixExclusif(list(execution_exports.ISSUES_DE_L_INTERRUPTION))
    assert choix.retenue is None
    assert choix.issues[choix.curseur].ecrit is False


# ===========================================================================
# AC 9.6 -- ce que l'interruption laisse, MESURE sur le coeur
# ===========================================================================

def test_AC_9_6_une_interruption_RETIRE_la_reservation_atomique(tmp_path,
                                                                monkeypatch):
    """Mesure, jamais supposition : le `finally` d'`execute_plan` fait le geste.

    La reservation est un fichier **vide** pose la ou il n'y avait rien ; le
    laisser bloquerait la relance sous `MASTER_DEJA_PRESENT`, et c'est
    exactement ce que la ligne « aucun master ne sera ecrit » de `T6-1`
    promet. On interrompt la ou le produit peut l'etre -- pendant l'encodage.
    """
    plan = plan_temoin(tmp_path)
    vues: list[bool] = []

    def encodeur_interrompu(*_args, **_kwargs):
        # La reservation EXISTE au moment ou l'encodeur travaille : sans ce
        # releve, un `finally` qui ne retirerait rien serait indiscernable
        # d'une reservation jamais posee.
        vues.append(plan.output_path.exists())
        raise KeyboardInterrupt

    monkeypatch.setattr(codec_profiles, "run_encode", encodeur_interrompu)
    with pytest.raises(KeyboardInterrupt):
        encode.execute_plan(plan)

    assert vues == [True], vues
    assert not plan.output_path.exists(), sorted(
        p.name for p in plan.output_path.parent.iterdir())


def test_AC_9_6_une_interruption_ne_DECLARE_rien_au_manifest(tmp_path,
                                                             monkeypatch):
    """Le second bord de l'AC 9.6, et c'est celui qui compte pour le manifest.

    `encoder_le_master_du_lot` convertit l'interruption en `EncodageInterrompu`
    **portant sa phase**, et la declaration au manifest vit APRES : elle n'est
    donc jamais atteinte. On le mesure par le compteur d'appels de
    `persist_encode`, pas en relisant une prose.
    """
    projet = tmp_path / "projet_demo"
    projet.mkdir()
    (projet / "project.json").write_text("{}", encoding="utf-8")

    declarations: list[object] = []
    monkeypatch.setattr(encode_master.encode_manifest, "persist_encode",
                        lambda *a, **k: declarations.append(a))
    monkeypatch.setattr(encode_master, "validate_manifest",
                        lambda _chemin: {"lots": []})

    def decision_interrompue(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(encode_master.encode, "plan_encode", decision_interrompue)
    with pytest.raises(encode_master.EncodageInterrompu) as refus:
        encode_master.encoder_le_master_du_lot(projet, lot_id="plan-04_25")

    assert refus.value.phase == "decision"
    assert declarations == [], declarations


def test_AC_9_6_le_cartouche_de_T6_1_dit_l_INVARIANT_plutot_que_de_le_supposer():
    """« Masters ecrits 0 » -- meme geste que « Frames ecrites 0 » du temps 1.

    Le cartouche porte **trois** lignes distinguables et la cible -- les
    echantillons a monter -- est **au milieu** : ni premiere, ni derniere.
    """
    ecran = execution_exports.EcranEncodageEnCours(
        passage_nominal(etape=execution_exports.ETAPE_ENCODAGE))
    panneau = ecran.panneau_de_ce_qui_est_ecrit()
    assert [ligne.libelle for ligne in panneau.lignes] == [
        execution_exports.LIBELLE_DE_L_ETAPE,
        execution_exports.LIBELLE_DES_ECHANTILLONS,
        execution_exports.LIBELLE_DES_MASTERS]
    assert panneau.lignes[0].valeur == "Étape 2 sur 4"
    assert panneau.lignes[1].valeur == 124
    assert panneau.lignes[2].valeur == 0


def test_le_cartouche_LAISSE_TOMBER_la_ligne_que_personne_n_a_mesuree():
    """Un panneau ne sort pas `0 echantillons` quand rien n'a ete compte."""
    ecran = execution_exports.EcranEncodageEnCours(passage_nominal(mesure=None))
    libelles = [ligne.libelle
                for ligne in ecran.panneau_de_ce_qui_est_ecrit().lignes]
    assert execution_exports.LIBELLE_DES_ECHANTILLONS not in libelles


# ===========================================================================
# La JONCTION de la story 6.7 -- `EPIC11-ARB-184`, troisieme consequence
# ===========================================================================

def test_le_raccord_PORTE_le_rappel_DEPUIS_QUE_le_coeur_compte():
    """**Retourne par la story 6.7, et c'est le signal attendu, pas une regression.**

    Ce test asserait `le_coeur_sait_compter() is False` et un raccord vide,
    avec pour docstring « Aujourd'hui, et c'est pour ca que l'atelier se livre
    au rotor » : il etait pince sur l'etat d'avant 6.7, ou
    `encoder_le_master_du_lot` n'acceptait aucun rappel. La story 6.7 pose
    `rappel_progression` sur les trois signatures du chemin d'encodage --
    `codec_profiles.run_encode`, `encode.execute_plan`,
    `encode_master.encoder_le_master_du_lot` -- donc l'introspection de
    :func:`le_coeur_sait_compter` bascule **sans qu'une ligne de `tui/`
    change**, ce qui EST l'AC de frontiere de cette story-la.

    Ce qui se mesure est une egalite d'ensemble, jamais une appartenance : le
    raccord porte **exactement** le mot-cle de progression. Et le rappel cable
    est la methode liee du passage lui-meme -- pas un autre appelable de meme
    forme --, sans quoi le jalon du coeur irait ailleurs que dans l'ecran que
    l'operateur regarde.
    """
    passage = passage_nominal()
    assert execution_exports.le_coeur_sait_compter() is True
    raccord = execution_exports.raccord_de_progression(passage)
    assert set(raccord) == {execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION}
    assert (raccord[execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION]
            == passage.noter)


def test_le_raccord_reste_VIDE_pour_un_point_d_entree_qui_ne_compte_PAS():
    """**La moitie que le retournement ci-dessus aurait emportee en silence.**

    Avant 6.7, le raccord vide se mesurait sur la vraie fonction de
    production. Depuis, plus aucun point d'entree reel ne rend `{}` : retourner
    le test voisin sans ecrire celui-ci aurait SUPPRIME une mesure au lieu de
    la deplacer, et la frontiere serait devenue verte parce qu'elle ne connait
    plus qu'un seul des deux etats. C'est le motif exact du parametre
    `point_d_entree` de :func:`le_coeur_sait_compter`, employe ici dans l'autre
    sens que son voisin : un coeur qui n'accepte **pas** le mot-cle.

    Trois points d'entree distinguables, et celui qui compte est **au milieu**
    -- ni premier, ni dernier : un raccord fautif qui rendrait toujours le
    premier resultat, ou qui repondrait sur le premier parametre rencontre, ne
    se demasque pas autrement. Le troisieme mesure l'AC 8 de la story 6.7 : un
    `**kwargs` ABSORBE le mot-cle sans le declarer, donc
    `inspect.signature` ne le voit pas et le raccord doit rester vide.
    """
    passage = passage_nominal()

    def coeur_sans_rappel(project_dir, *, lot_id):
        """Le coeur d'avant 6.7."""

    def coeur_qui_compte(project_dir, *, lot_id, rappel_progression=None):
        """Le coeur d'apres 6.7 -- la cible, au milieu des trois."""

    def coeur_a_kwargs(project_dir, *, lot_id, **kwargs):
        """Accepte le mot-cle a l'appel, ne le DECLARE pas : AC 8."""

    attendus = [{},
                {execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION: passage.noter},
                {}]
    rendus = [execution_exports.raccord_de_progression(passage, point)
              for point in (coeur_sans_rappel, coeur_qui_compte,
                            coeur_a_kwargs)]
    assert rendus == attendus, rendus


def test_le_raccord_SE_FAIT_TOUT_SEUL_le_jour_ou_le_coeur_accepte_le_rappel():
    """**L'AC de frontiere de la story 6.7, verifiee du cote TUI.**

    Son diff de raccordement ne doit toucher aucun fichier de `tui/`. On le
    mesure en posant la question a un double qui, lui, accepte
    `rappel_progression` : le raccord le reconnait sur la **signature**, donc
    sans qu'une ligne d'ici change.

    Le rappel cable est bien celui du passage -- pas un autre appelable -- et
    il se comporte comme `EmetteurProgression` l'appellera.
    """
    passage = passage_nominal()

    def coeur_de_demain(project_dir, *, lot_id, rappel_progression=None):
        if rappel_progression is not None:
            rappel_progression(79, 124)

    assert execution_exports.le_coeur_sait_compter(coeur_de_demain) is True
    raccord = execution_exports.raccord_de_progression(passage, coeur_de_demain)
    assert set(raccord) == {execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION}
    coeur_de_demain("projet", lot_id="plan-04_25", **raccord)
    assert passage.jalon == (79, 124)


def test_le_nom_du_rappel_est_celui_QUE_LE_COEUR_EMPLOIE_DEJA():
    """Par confrontation, jamais par declaration.

    Cinq points d'entree de coeur portent ce mot-cle ; en inventer un sixieme
    ferait que le raccord ne reconnaitrait pas celui que la story 6.7 posera.
    """
    from mixed_media_utility import makepdf, scan_detect

    for point in (makepdf.generer_les_planches_du_lot,
                  scan_detect.run_scan_detect):
        assert (execution_exports.NOM_DU_RAPPEL_DE_PROGRESSION
                in inspect.signature(point).parameters), point


def test_avancer_a_est_la_JONCTION_des_etapes_et_refuse_une_cle_inconnue():
    """La cible est **au milieu** : `verification` est la troisieme des quatre."""
    passage = passage_nominal()
    assert passage.avancer_a(execution_exports.ETAPE_VERIFICATION) is True
    assert passage.rang == 3
    assert passage.avancer_a(execution_exports.ETAPE_VERIFICATION) is False
    assert passage.avancer_a("etape-qui-n-existe-pas") is False
    assert passage.etape == execution_exports.ETAPE_VERIFICATION


def test_une_etape_INCONNUE_ne_fait_pas_LEVER_l_ecran_en_plein_encodage():
    """Un `ValueError` au milieu d'un encodage d'une heure serait la pire des
    reponses : le rang retombe sur la premiere etape."""
    passage = passage_nominal(etape="rien-de-connu")
    assert passage.rang == 1
    assert passage.lignes_des_etapes()


# ===========================================================================
# Le produit contre le DESSIN valide, ligne par ligne
# ===========================================================================

MAQUETTE_E4_4 = "E4-4-exports-execution.txt"
MAQUETTE_E4_4B = "E4-4b-exports-preverification.txt"


def maquette_de_e4_4() -> execution_exports.PassageDeLEncodage:
    return passage_nominal(etape=execution_exports.ETAPE_ENCODAGE)


def maquette_de_e4_4b() -> execution_exports.PassageDeLEncodage:
    return passage_nominal(etape=execution_exports.ETAPE_PREVERIFICATION)


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_4, maquette_de_e4_4),
    (MAQUETTE_E4_4B, maquette_de_e4_4b),
])
def test_le_corps_rendu_est_celui_de_la_maquette(nom, fabrique):
    """Le produit contre le dessin, ligne par ligne.

    C'est la mesure la plus forte de cet ecran : elle attrape a la fois une
    colonne qui glisse, un glyphe qui se deplace et un chiffre qui change, et
    elle rougirait si une maquette etait regeneree sans que le produit suive.
    """
    assert corps(fabrique()) == centre_de_la_maquette(nom)


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_4, maquette_de_e4_4),
    (MAQUETTE_E4_4B, maquette_de_e4_4b),
])
def test_la_ligne_d_etat_est_celle_de_la_maquette(nom, fabrique):
    assert fabrique().ligne_d_etat() == etat_de_la_maquette(nom)


@pytest.mark.parametrize("nom", [MAQUETTE_E4_4, MAQUETTE_E4_4B])
def test_la_ligne_de_raccourcis_est_celle_de_la_maquette(nom):
    assert (execution_exports.RACCOURCIS_ENCODAGE_EN_COURS
            == raccourcis_de_la_maquette(nom))


@pytest.mark.parametrize("nom,fabrique", [
    (MAQUETTE_E4_4, maquette_de_e4_4),
    (MAQUETTE_E4_4B, maquette_de_e4_4b),
])
def test_la_droite_du_bandeau_est_celle_de_la_maquette(nom, fabrique):
    assert fabrique().objet_du_bandeau() in bandeau_de_la_maquette(nom)


def test_les_deux_maquettes_dessinent_bien_DEUX_etats_differents():
    """Volet symetrique des trois mesures ci-dessus.

    Sans lui, deux maquettes identiques rendraient les comparaisons vertes pour
    rien -- et `E4-4` / `E4-4b` sont **le meme ecran a deux instants**, ce qui
    est exactement le cas ou la confusion coute.
    """
    assert corps(maquette_de_e4_4()) != corps(maquette_de_e4_4b())
    assert (maquette_de_e4_4().ligne_d_etat()
            != maquette_de_e4_4b().ligne_d_etat())
    assert maquette_de_e4_4().titre() != maquette_de_e4_4b().titre()


# ===========================================================================
# La grille, la ligne de raccourcis, et ce que le paquet exige d'un passage
# ===========================================================================

def test_la_ligne_de_raccourcis_est_celle_QUE_LE_PRODUIT_PORTE_DEJA():
    """Par egalite, comme `RACCOURCIS_RESULTAT == RACCOURCIS_RAPPORT`.

    `atelier_pdf_calibration.RACCOURCIS_MIRE_EN_COURS` porte la **meme
    promesse** sur le meme genre d'ecran -- un passage a rotor, sans journal :
    interrompre, et de l'aide. Deux redactions qui divergeraient donneraient
    deux rythmes a l'ecran pour un seul geste.
    """
    assert (execution_exports.RACCOURCIS_ENCODAGE_EN_COURS
            == RACCOURCIS_MIRE_EN_COURS)


def test_le_passage_annonce_F1_aide_et_JAMAIS_Q_quitter():
    """`EPIC11-ARB-140`, sur le huitieme ecran d'execution du depot."""
    ligne = execution_exports.EcranEncodageEnCours.raccourcis
    assert "F1 aide" in ligne
    assert "Q quitter" not in ligne
    assert execution_exports.EcranEncodageEnCours.TRANSITOIRE is True


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_ne_DEBORDE_de_la_grille_au_plancher(ascii_seul):
    """Le plancher d'`EPIC11-ARB-21` : un ecran qui tient a 100x30 et deborde a
    80x24 est un defaut que seule cette taille demasque."""
    utile = jetons.largeur_utile()
    for cle, passage in tous_les_etats(passage_decime):
        for ligne in tout_ce_qui_s_affiche(passage, ascii_seul):
            assert jetons.colonnes(ligne) <= utile, (cle, ligne)


def test_la_composition_TIENT_la_hauteur_de_la_zone_centrale():
    """Six lignes pour la zone du plancher : `textual` coupe par le bas et en
    silence, et c'est le defaut `I1` du 2026-08-30."""
    for _cle, passage in tous_les_etats():
        lignes = corps(passage)
        assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, lignes


def test_le_module_n_importe_JAMAIS_cli():
    """`EPIC11-ARB-67`, mesure sur l'arbre syntaxique et pas par un grep."""
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            noms |= {alias.name for alias in noeud.names}
        elif isinstance(noeud, ast.ImportFrom):
            noms.add(noeud.module or "")
            noms |= {alias.name for alias in noeud.names}
    assert not any(nom == "cli" or nom.endswith(".cli") for nom in noms), noms
