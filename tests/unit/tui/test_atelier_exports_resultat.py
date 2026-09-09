# -*- coding: utf-8 -*-
"""`E4-5` -- le resultat de l'encodage (story 11.8, lot G, AC 10).

**C'est le seul ecran du produit qui affirme ce qui existe sur le disque**, et
c'est ce qui commande la forme de ce banc : chaque chiffre affiche est mesure
en **faisant bouger le coeur**, jamais en le comparant a un litteral egal des
deux cotes. Une assertion `« 124 échantillons » in rendu` avec 124 ecrit dans
la fabrique est tautologique -- c'est le defaut qui a fait rougir la constante
centrale de la calibration sur la story 5.9 --, si bien que tous les tests
d'AC 10.1 comparent **deux masters qui ne different que par le champ vise** et
verifient que le rendu suit.

Ce que ce banc mesure, et que le produit ne dit pas tout seul
--------------------------------------------------------------

* **AC 10.1** : les sept valeurs du panneau viennent de `EncodeOutcome` ou de
  `PersistedEncode`. Les deux qui n'en viennent pas -- le **poids** et la
  **duree** -- sont mesurees pour ce qu'elles sont : un `stat` du fichier ecrit
  d'un cote, une valeur **donnee** de l'autre. La duree est mesuree
  **contradictoire** avec `frame_count / frame_rate` : si l'ecran la derivait,
  ce test rougirait ;
* **AC 10.2** : les quatre suites sont mesurees par **egalite d'ensemble** --
  la liste ET son exclusivite --, chacune est atteinte **aux fleches seules**,
  et leurs quatre destinations sont confrontees deux a deux : une dispatch qui
  rendrait toujours la meme ne passerait pas. Les deux ouvertures sont
  **servables**, mesure faite sur l'argv reel que le produit passerait ;
* **AC 10.3** : la ligne d'etat porte une mesure, et les trois frontieres
  negatives sont doublees de leur temoin -- aucune touche, aucun conseil
  d'usage, aucun motif de conception (`EPIC11-ARB-56`).

Regle des fabriques
--------------------

* les **quatre** suites sont une collection ordonnee, et chaque test de
  destination vise une cible **au milieu** avant de les exercer toutes : ni la
  premiere (qu'une dispatch fautive rendrait toujours) ni la derniere (qu'une
  boucle sans arret rendrait) ;
* les deux cardinaux sont **distinguables** : la fabrique decimee reprend le
  couple **63 frames / 125 echantillons** du lot F plutot que d'en ecrire un
  troisieme -- sur un lot 25p les deux valent 124 et les confondre ne se verrait
  pas ;
* les etats de lot sont **lus** de `io.manifest.LOT_STATES`, et la cible n'est
  jamais le premier de la liste.
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import sys

import pytest

from outils_frontiere import chaines_de_code

_RACINE = pathlib.Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import codec_profiles, encode, encode_master  # noqa: E402
from mixed_media_utility.io import encode_manifest  # noqa: E402
from mixed_media_utility.io.manifest import LOT_STATES  # noqa: E402
from mixed_media_utility.tui import jetons, projet_lecture  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_exports_execution as execution_exports,
    atelier_exports_resultat as resultat,
    execution as execution_partagee,
)
from mixed_media_utility.tui.execution import (  # noqa: E402
    RACCOURCIS_RESULTAT, RACCOURCIS_RESULTAT_AVEC_JOURNAL,
)

# **La fabrique de plan du lot F est REUTILISEE, pas reecrite** : c'est elle
# qui pose un `encode.EncodePlan` reel, avec son `output_path` dans
# `outputs/`. Ce banc n'en change que les deux cardinaux.
from test_atelier_exports_execution import plan_temoin  # noqa: E402

MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")
MAQUETTE = "E4-5-exports-resultat.txt"
SOURCE_DU_MODULE = pathlib.Path(resultat.__file__)

#: Les deux regimes, portes par tout test qui touche au rendu.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le poids du master de demonstration, en octets. La maquette ecrit
#: `1,38 Go` ; le depot n'a **qu'une** redaction de taille lisible
#: (`explorateur.taille_lisible`) et elle rend une decimale -- voir
#: :func:`test_la_taille_de_la_maquette_n_est_PAS_RENDABLE_par_le_produit`,
#: qui mesure l'ecart plutot que de le taire.
OCTETS_DEMO = int(1.38 * 1024 ** 3)

#: Le rapport de `verify_technical_metadata`, dans la forme que le coeur rend :
#: un dictionnaire par champ. Trois champs **distinguables**, et celui que les
#: tests visent est au milieu.
RAPPORT = {
    "codec": {"ok": True, "expected": "prores", "actual": "prores"},
    "resolution": {"ok": True, "expected": "1920x1080", "actual": "1920x1080"},
    "frame_rate": {"ok": True, "expected": "25/1", "actual": "25/1"},
}


# ===========================================================================
# Les fabriques
# ===========================================================================

def _plan(tmp_path, *, frames: int = 124, echantillons: int = 124,
          lot_id: str = "plan-04_25", nom: str | None = None):
    """Un `encode.EncodePlan` REEL, aux deux cardinaux voulus.

    `frame_paths` porte les frames **distinctes** retenues, `muxed_frame_paths`
    les **echantillons** montes : les confondre est exactement le defaut que la
    fabrique decimee existe pour demasquer.
    """
    base = plan_temoin(tmp_path)
    dossier = base.output_path.parent
    distinctes = tuple(dossier.parent / f"frame_{rang:04d}.tiff"
                       for rang in range(frames))
    muxees = tuple(distinctes[rang % max(frames, 1)]
                   for rang in range(echantillons))
    sortie = dossier / (nom or f"{lot_id}_mmu_prores_hq.mov")
    return dataclasses.replace(base, lot_id=lot_id, frame_paths=distinctes,
                               muxed_frame_paths=muxees, output_path=sortie)


def _issue(plan, *, echantillons: int, cadence: str = "25/1",
           timecode: str | None = "00:00:04:12"):
    """Un `codec_profiles.EncodeOutcome` REEL, celui que `execute_plan` rend.

    `frame_count` y vaut `len(plan.muxed_frame_paths)` -- mesure faite sur
    `run_encode`, qui recoit la sequence **muxee** et rend `len(frames)`.
    """
    return codec_profiles.EncodeOutcome(
        profile_id=codec_profiles.DEFAULT_PROFILE_ID,
        output_path=str(plan.output_path),
        frame_count=echantillons,
        frame_rate=cadence,
        source_size=(1920, 1080),
        target_size=None,
        encoded_size=(1920, 1080),
        filter_chain="",
        pix_fmt="yuv422p10le",
        timecode=timecode,
        timecode_base=None if timecode is None else cadence,
    )


def master_du_lot(tmp_path, *, frames: int = 124, echantillons: int = 124,
                  lot_id: str = "plan-04_25", nom: str | None = None,
                  cadence: str = "25/1", timecode: str | None = "00:00:04:12",
                  etat: str | None = None, octets: int = OCTETS_DEMO,
                  constats: tuple[str, ...] = (),
                  constats_du_manifest: tuple[str, ...] = (),
                  rapport=None, ecrire: bool = True):
    """Un `encode_master.MasterDuLot` REEL -- les trois objets du coeur.

    Le fichier master est **reellement ecrit**, a la taille demandee -- c'est le
    seul moyen de mesurer que l'ecran lit le disque et non un champ du plan --,
    et il l'est **creux** (`truncate`) : `stat().st_size` rend la taille voulue
    sans qu'un master de demonstration de 1,4 Go touche le disque.
    """
    plan = _plan(tmp_path, frames=frames, echantillons=echantillons,
                 lot_id=lot_id, nom=nom)
    if ecrire:
        with plan.output_path.open("wb") as fichier:
            fichier.truncate(octets)
    outcome = _issue(plan, echantillons=echantillons, cadence=cadence,
                     timecode=timecode)
    resultat_de_commande = encode.EncodeCommandResult(
        plan=plan, outcome=outcome, manifest_fields={},
        verification=dict(RAPPORT if rapport is None else rapport),
        findings=constats)
    persiste = encode_manifest.PersistedEncode(
        manifest_path=plan.project_dir / "project.json",
        lot_id=plan.lot_id,
        manifest={},
        # **L'etat est LU du vocabulaire du coeur**, jamais ecrit : un litteral
        # d'etat dans un banc de l'atelier vieillirait avec le vocabulaire.
        state_written=LOT_STATES[-1] if etat is None else etat,
        master_path=f"outputs/{plan.output_path.name}",
        findings=constats_du_manifest)
    return encode_master.MasterDuLot(resultat=resultat_de_commande,
                                     persisted=persiste, recapitulatif="")


def ecrit(tmp_path, **champs) -> resultat.MasterEcrit:
    """Le modele de `E4-5`, lu du coeur par le chemin du produit."""
    mesure = champs.pop("mesure", None)
    duree = champs.pop("duree_d_encodage_s", 64.0)
    return resultat.MasterEcrit.du_master(master_du_lot(tmp_path, **champs),
                                          mesure=mesure,
                                          duree_d_encodage_s=duree)


class _Mesure:
    """Le double de `MesureDuMaster` : seul `duree_s` est lu par cet ecran."""

    def __init__(self, duree_s):
        self.duree_s = duree_s


def panneau(master, ascii_seul: bool = False) -> list[str]:
    return [ligne.rstrip()
            for ligne in resultat.panneau_du_master(master, ascii_seul).rendu(
                jetons.LARGEUR_PLANCHER, ascii_seul)]


def tout_ce_qui_s_affiche(master, ascii_seul: bool = False) -> list[str]:
    """**Tout** ce que l'operateur lit : panneau, suites, etat, bandeau, pied.

    Une frontiere posee sur le seul panneau laisserait passer une touche en
    ligne d'etat, qui est justement l'endroit ou `EPIC11-ARB-56` l'interdit.
    """
    journal = resultat.journal_de_la_verification(master)
    ligne = (RACCOURCIS_RESULTAT_AVEC_JOURNAL if journal is not None
             else RACCOURCIS_RESULTAT)
    return [*panneau(master, ascii_seul),
            *resultat.suites_du_resultat(master),
            resultat.ligne_d_etat(master, ascii_seul),
            master.objet_du_bandeau(ascii_seul),
            jetons.replier_ascii(ligne) if ascii_seul else ligne,
            *(journal.lignes if journal is not None else [])]


# ===========================================================================
# L'application factice et l'ecran sous banc
# ===========================================================================

class _Taille:
    def __init__(self, largeur=80, hauteur=24):
        self.width, self.height = largeur, hauteur


class _PalierFactice:
    def __init__(self):
        self.etat = None

    def poser_etat(self, texte):
        self.etat = texte


class _AppFactice:
    """Le strict necessaire : une taille, deux modes, et une pile d'ecrans."""

    QUAND_ARRIVENT_LES_ATELIERS = "les ateliers de la vague 3"

    def __init__(self, largeur=80, hauteur=24, ascii_seul=False, passages=0):
        self.size = _Taille(largeur, hauteur)
        self.ascii_seul = ascii_seul
        self.sans_couleur = True
        self.ateliers = 0
        self.descendus = []
        self.palier_courant = _PalierFactice()
        #: La pile : un palier non transitoire, puis `passages` passages.
        self.screen_stack = ["palier"] + ["passage"] * passages
        self.depiles = 0

    @property
    def passages_empiles(self):
        return sum(1 for ecran in self.screen_stack if ecran == "passage")

    def pop_screen(self):
        self.depiles += 1
        self.screen_stack.pop()

    def revenir_aux_ateliers(self):
        self.ateliers += 1

    def descendre(self, ecran):
        self.descendus.append(ecran)


class _EcranSousBanc(resultat.EcranResultatDuMaster):
    """La sous-classe qui porte l'application factice.

    `textual` fait de `Screen.app` une **propriete**, donc une affectation sur
    l'instance ne la masque pas ; et redefinir la propriete sur la classe de
    PRODUCTION la muterait pour tous les bancs collectes ensuite -- defaut paye
    par le lot I de la 11.7. Une sous-classe porte la meme propriete sans
    toucher a ce que le produit livre.
    """

    @property
    def app(self):
        return self._app_factice


class _Evenement:
    def __init__(self, touche):
        self.key = touche
        self.arrete = False

    def stop(self):
        self.arrete = True


class _CorpsFactice:
    """La zone de texte, remplacee par ce qu'elle recoit.

    **Le rendu n'est pas court-circuite** : `EcranResultat.rafraichir` compose
    ses lignes, les peint et les pose ici pour de vrai. C'est ce qui fait que
    les tests de clavier exercent le chemin du produit -- un `rafraichir`
    neutralise laisserait passer une composition qui leve.
    """

    def __init__(self):
        self.dernier = None

    def update(self, texte):
        self.dernier = texte


def ecran(master, *, sur_suite=None, app=None) -> _EcranSousBanc:
    objet = _EcranSousBanc(master, sur_suite=sur_suite)
    objet._app_factice = app if app is not None else _AppFactice()
    objet._corps = _CorpsFactice()
    return objet


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
# La maquette
# ===========================================================================

def _cadre() -> list[str]:
    lignes = (MAQUETTES / MAQUETTE).read_text(encoding="utf-8").split("\n")[:24]
    return [ligne for ligne in lignes if ligne.startswith("│")]


def centre_de_la_maquette() -> list[str]:
    centre = [ligne[2:-1].rstrip() for ligne in _cadre()[1:-2]]
    while centre and not centre[-1]:
        centre.pop()
    return centre


def etat_de_la_maquette() -> str:
    return _cadre()[-2][2:-1].rstrip()


def raccourcis_de_la_maquette() -> str:
    return _cadre()[-1][2:-1].rstrip()


def bandeau_de_la_maquette() -> str:
    return _cadre()[0][2:-1].rstrip()


def lignes_du_cartouche() -> list[str]:
    """Les lignes de CORPS du cartouche `Écrit`, cadre retire."""
    dedans = [ligne for ligne in centre_de_la_maquette()
              if ligne.startswith("│") or ligne.startswith("  │")]
    return [ligne.strip("│ ").rstrip() for ligne in dedans
            if not set(ligne.strip("│ ")) <= {"─", ""}]


def test_la_maquette_lue_par_ce_banc_est_bien_CELLE_de_E4_5():
    """Temoin du lecteur : sans lui, une maquette renommee rendrait un banc
    vert sur zero ligne."""
    assert (MAQUETTES / MAQUETTE).is_file()
    assert len(_cadre()) >= 20
    assert resultat.TITRE_DU_CARTOUCHE in centre_de_la_maquette()[1]


# ===========================================================================
# AC 10.1 -- ce que le panneau porte VIENT du coeur, et il le SUIT
# ===========================================================================

def test_AC_10_1_le_NOM_suit_outcome_output_path(tmp_path):
    """Le nom du master est celui qu'`io.naming` a decide, jamais recompose."""
    un = ecrit(tmp_path / "a", nom="plan-04_25_mmu_prores_hq.mov")
    autre = ecrit(tmp_path / "b", nom="plan-99_8_mmu_dnxhr_hqx_v7.mov")
    assert un.nom == "plan-04_25_mmu_prores_hq.mov"
    assert autre.nom == "plan-99_8_mmu_dnxhr_hqx_v7.mov"
    assert any(autre.nom in ligne for ligne in panneau(autre))
    assert not any(un.nom in ligne for ligne in panneau(autre))


def test_AC_10_1_les_ECHANTILLONS_suivent_outcome_frame_count(tmp_path):
    """Le coeur bouge, l'ecran suit -- 124 contre 125, et jamais un litteral.

    La fabrique decimee reprend le couple **63 / 125** du lot F : `frame_count`
    de l'issue compte la sequence **muxee**, pas les frames distinctes.
    """
    nominal = ecrit(tmp_path / "a", frames=124, echantillons=124)
    decime = ecrit(tmp_path / "b", frames=63, echantillons=125)
    assert nominal.echantillons == 124 and decime.echantillons == 125
    assert f"125 {execution_exports.UNITE_DES_ECHANTILLONS}" in "".join(
        panneau(decime))
    assert f"124 {execution_exports.UNITE_DES_ECHANTILLONS}" not in "".join(
        panneau(decime))


def test_AC_10_1_les_deux_CARDINAUX_ne_sont_pas_le_meme_champ(tmp_path):
    """`63 f` au bandeau, `125 échantillons` au panneau : le meme master.

    Les confondre ferait dire « 63 échantillons » d'un master qui en porte 125,
    ou « 125 f » d'un lot qui n'a que 63 frames distinctes.
    """
    decime = ecrit(tmp_path, frames=63, echantillons=125)
    assert decime.frames == 63
    assert decime.echantillons == 125
    assert "63 f" in decime.objet_du_bandeau()
    assert "125" not in decime.objet_du_bandeau()


@pytest.mark.parametrize("exacte,attendu", [
    ("25/1", "25 fps"),
    ("24000/1001", "23,976 fps"),
    ("25/2", "12,5 fps"),
])
def test_AC_10_1_la_CADENCE_suit_outcome_frame_rate(tmp_path, exacte, attendu):
    """Trois valeurs, dont une NTSC : un rendu code en dur ne passerait pas."""
    master = ecrit(tmp_path, cadence=exacte)
    assert master.cadence == exacte
    assert attendu in "".join(panneau(master))


def test_AC_10_1_le_TIMECODE_suit_outcome_timecode(tmp_path):
    """Et son absence RETIRE la ligne : le coeur s'abstient en le motivant, et
    une etiquette inventee designerait une autre image."""
    avec = ecrit(tmp_path / "a", timecode="00:00:04:12")
    sans = ecrit(tmp_path / "b", timecode=None)
    assert any("00:00:04:12" in ligne for ligne in panneau(avec))
    assert any(ligne.startswith(resultat.LIBELLE_TIMECODE)
               for ligne in panneau(avec))
    assert not any(ligne.startswith(resultat.LIBELLE_TIMECODE)
                   for ligne in panneau(sans))


def test_AC_10_1_l_ETAT_DU_LOT_suit_persisted_state_written(tmp_path):
    """Deux etats **lus** de `LOT_STATES`, et la cible n'est pas le premier.

    Un ecran qui recopierait un etat, ou qui rendrait toujours le premier du
    vocabulaire, ne passerait pas ce test.
    """
    vise, autre = LOT_STATES[-1], LOT_STATES[-2]
    assert vise != autre
    un = ecrit(tmp_path / "a", etat=vise)
    deux = ecrit(tmp_path / "b", etat=autre)
    assert un.texte_de_l_etat_du_lot().startswith(vise)
    assert deux.texte_de_l_etat_du_lot().startswith(autre)
    assert resultat.MENTION_DECLARE in un.texte_de_l_etat_du_lot()


def test_AC_10_1_la_TAILLE_est_celle_du_FICHIER_et_jamais_le_MAJORANT(tmp_path):
    """Le poids affiche est mesure sur le disque, pas lu du plan.

    `EncodePlan.estimated_bytes` est un **majorant** -- il vaut ici plusieurs
    ordres de grandeur de plus que le fichier ecrit --, et un ecran de resultat
    qui l'afficherait mentirait sur sa propre precision. Le test le mesure par
    l'ecart plutot que par une declaration.
    """
    from mixed_media_utility.tui.explorateur import taille_lisible
    master = ecrit(tmp_path, octets=4096)
    plan = master_du_lot(tmp_path / "bis", octets=4096).resultat.plan
    assert plan.estimated_bytes != 4096
    assert master.taille == taille_lisible(4096)
    assert master.taille != taille_lisible(plan.estimated_bytes)


def test_AC_10_1_un_master_INTROUVABLE_retire_la_ligne_au_lieu_de_dire_zero(
        tmp_path):
    """`None` et non zero : un master de zero octet n'existe pas."""
    master = ecrit(tmp_path, ecrire=False)
    assert master.octets is None
    assert master.taille is None
    assert not any(ligne.startswith(resultat.LIBELLE_TAILLE)
                   for ligne in panneau(master))


def test_AC_10_1_la_DUREE_est_DONNEE_et_JAMAIS_derivee(tmp_path):
    """La mesure qui distingue « donnee » de « recalculee ».

    La duree donnee **contredit** `frame_count / frame_rate` : 124 echantillons
    a 25 fps font 4,96 s, et la mesure passee en dit 40. Un ecran qui derivait
    la duree afficherait `4 s 96` et rougirait ici.
    """
    master = ecrit(tmp_path, mesure=_Mesure(40.0))
    ligne = master.texte_de_la_duree()
    assert "40 s 00" in ligne
    assert "4 s 96" not in ligne


def test_AC_10_1_sans_MESURE_la_duree_disparait_et_le_reste_TIENT(tmp_path):
    """Le volet symetrique : la ligne garde ses deux autres segments."""
    master = ecrit(tmp_path, mesure=None)
    ligne = master.texte_de_la_duree()
    assert execution_exports.UNITE_DES_ECHANTILLONS in ligne
    assert resultat.UNITE_DE_CADENCE in ligne
    assert " s " not in ligne


def test_AC_10_1_le_panneau_ne_porte_AUCUN_majorant(tmp_path):
    """`EcranResultat` leve a la construction sur un panneau qui en porte un.

    Le test mesure les deux moities : le panneau n'en porte pas, **et**
    l'ecran se construit -- une garde qui ne serait jamais franchie ne
    prouverait rien.
    """
    master = ecrit(tmp_path)
    assert not resultat.panneau_du_master(master).porte_un_majorant
    assert ecran(master).suites


def test_AC_10_1_les_CONSTATS_sont_ceux_du_coeur_des_DEUX_objets(tmp_path):
    """`EncodeCommandResult.findings` **et** `PersistedEncode.findings`.

    Les deux, et dans cet ordre : un ecran qui n'en lirait qu'un tairait la
    moitie de ce que la passe a constate. Les codes sortent **verbatim**.
    """
    master = ecrit(tmp_path, constats=("A", "B"),
                   constats_du_manifest=("C",))
    assert master.constats == ("A", "B", "C")


def test_AC_10_1_la_provenance_de_RECONSTRUCTION_n_est_PAS_devinee():
    """`EPIC11-ARB-193` : rien au manifeste ne dit de quelle passe un master sort.

    Frontiere **negative**, et c'est la seule forme qui attrape une devinette
    ajoutee demain : le module ne nomme aucune des trois surfaces par
    lesquelles la provenance se devinerait -- l'historique du lot, le dossier
    de frames, ou la designation portee par le plan.
    """
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    attributs = {noeud.attr for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Attribute)}
    interdits = {"reconstructions", "reconstruction_designee",
                 "output_frames_dir", "ingest_slug"}
    assert attributs & interdits == set()


def test_AC_10_1_le_panneau_porte_EXACTEMENT_les_libelles_servables(tmp_path):
    """Egalite d'ensemble, et l'ordre avec : « cette ligne est presente » est
    faible.

    Les six libelles sont ceux de la maquette **moins `Reconstruction`**, que
    l'arbitrage rend inservable. Une ligne ajoutee ou retiree demain fait
    rougir.
    """
    master = ecrit(tmp_path, mesure=_Mesure(4.96))
    attendus = [resultat.LIBELLE_TAILLE, resultat.LIBELLE_DUREE,
                resultat.LIBELLE_TIMECODE, resultat.LIBELLE_EMPLACEMENT,
                resultat.LIBELLE_ETAT_DU_LOT,
                resultat.LIBELLE_DUREE_D_ENCODAGE]
    poses = [ligne.libelle for ligne
             in resultat.panneau_du_master(master).lignes
             if ligne.libelle and not ligne.libelle.startswith(
                 jetons.GLYPHES["complete"])]
    assert poses == attendus


def test_AC_10_1_les_six_libelles_sont_ceux_DE_LA_MAQUETTE(tmp_path):
    """Volet positif du precedent : les libelles ne sont pas inventes ici.

    Chacun ouvre une ligne du cartouche dessine ; et `Reconstruction`, qui en
    ouvre une septieme, est **absent du module** -- c'est l'ecart que le lot
    signale plutot que de le combler par une devinette.
    """
    dessinees = lignes_du_cartouche()
    for libelle in (resultat.LIBELLE_TAILLE, resultat.LIBELLE_DUREE,
                    resultat.LIBELLE_TIMECODE, resultat.LIBELLE_EMPLACEMENT,
                    resultat.LIBELLE_ETAT_DU_LOT,
                    resultat.LIBELLE_DUREE_D_ENCODAGE):
        assert any(ligne.startswith(libelle) for ligne in dessinees), libelle
    assert any(ligne.startswith("Reconstruction") for ligne in dessinees)
    # **La prose a le droit de dire pourquoi la ligne manque** ; le CODE n'a
    # pas le droit de la poser. La mesure porte donc sur les chaines
    # litterales, docstrings exclus -- meme outil que les frontieres du lot B4.
    assert not [chaine for chaine in chaines_de_code(SOURCE_DU_MODULE)
                if "Reconstruction" in chaine]


def test_AC_10_1_l_EMPLACEMENT_est_compose_par_la_redaction_de_E4_4(tmp_path):
    """Une seconde redaction de « ou vivent les masters » divergerait."""
    master = ecrit(tmp_path)
    projet = master.chemin.parent.parent
    assert master.dossier == execution_exports.dossier_de_sortie(projet)
    assert any(master.dossier in ligne for ligne in panneau(master))


def test_la_DUREE_D_ENCODAGE_est_donnee_et_son_absence_retire_la_ligne(tmp_path):
    """Elle mesure la PASSE, pas le master : le coeur n'en rend aucune."""
    avec = ecrit(tmp_path / "a", duree_d_encodage_s=64.0)
    sans = ecrit(tmp_path / "b", duree_d_encodage_s=None)
    assert any(ligne.startswith(resultat.LIBELLE_DUREE_D_ENCODAGE)
               and "1 min 04" in ligne for ligne in panneau(avec))
    assert not any(ligne.startswith(resultat.LIBELLE_DUREE_D_ENCODAGE)
                   for ligne in panneau(sans))


def test_le_module_ne_RECALCULE_aucune_duree(tmp_path):
    """Frontiere negative doublee de son temoin.

    Le module ne porte **aucune division** : c'est la seule facon de deriver
    une duree de `frame_count` et `frame_rate`, et une frontiere syntaxique est
    ce qui attrape sa reintroduction. Le temoin est le test de duree
    contradictoire ci-dessus, qui rougirait si la division revenait.
    """
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    divisions = [noeud for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.BinOp)
                 and isinstance(noeud.op, (ast.Div, ast.FloorDiv))]
    assert divisions == []


# ===========================================================================
# AC 10.2 -- les quatre suites, au CLAVIER SEUL
# ===========================================================================

def toutes_les_suites(master) -> list[str]:
    return list(ecran(master).suites)


def test_AC_10_2_l_ensemble_des_suites_est_EXACTEMENT_les_quatre(tmp_path):
    """La liste **et** son exclusivite : « cette suite est offerte » est faible.

    La quatrieme -- `Retour aux ateliers` -- est posee par `EcranResultat`, et
    l'ecran ne la reecrit pas : ce test mesure du meme coup qu'elle n'apparait
    **pas deux fois**.
    """
    suites = toutes_les_suites(ecrit(tmp_path))
    assert suites == [resultat.SUITE_DOSSIER, resultat.SUITE_FICHIER,
                      resultat.SUITE_AUTRE_LOT,
                      resultat.EcranResultatDuMaster.RETOUR]
    assert len(set(suites)) == 4


def test_AC_10_2_les_quatre_suites_sont_celles_DE_LA_MAQUETTE(tmp_path):
    """Volet positif : les libelles sont ceux du dessin valide, verbatim."""
    dessinees = [ligne.lstrip("▸ ").strip()
                 for ligne in centre_de_la_maquette()
                 if ligne.strip() and not ligne.strip().startswith("│")
                 and not ligne.strip().startswith("┌")
                 and not ligne.strip().startswith("└")]
    assert toutes_les_suites(ecrit(tmp_path)) == dessinees


@pytest.mark.parametrize("rang", [0, 1, 2, 3])
def test_AC_10_2_chaque_suite_est_ATTEIGNABLE_aux_FLECHES_seules(tmp_path, rang):
    """`EPIC11-ARB-11` : rien n'est atteignable seulement a la souris.

    Le parcours part du curseur d'ouverture et **n'emploie que `down`** : une
    cible qu'un seul `down` atteindrait ne prouverait rien pour la quatrieme.
    """
    objet = ecran(ecrit(tmp_path))
    for _ in range(rang):
        objet.on_key(_Evenement("down"))
    assert objet.curseur == rang
    assert objet.suites[objet.curseur] == objet.suites[rang]


def test_AC_10_2_les_fleches_REMONTENT_aussi_et_ne_debordent_pas(tmp_path):
    """Le volet symetrique, et les deux butees."""
    objet = ecran(ecrit(tmp_path))
    for _ in range(10):
        objet.on_key(_Evenement("down"))
    assert objet.curseur == len(objet.suites) - 1
    for _ in range(10):
        objet.on_key(_Evenement("up"))
    assert objet.curseur == 0


@pytest.mark.parametrize("suite", list(resultat.SUITES)
                         + [resultat.EcranResultatDuMaster.RETOUR])
def test_AC_10_2_ENTREE_declenche_la_suite_sous_le_curseur(tmp_path, suite):
    """Les quatre, une a une, et **la cible est atteinte aux fleches**.

    Une dispatch qui rendrait toujours la premiere ne passerait pas : la
    troisieme et la quatrieme sont visees comme les deux premieres.
    """
    choisies = []
    objet = ecran(ecrit(tmp_path), sur_suite=choisies.append)
    rang = list(objet.suites).index(suite)
    for _ in range(rang):
        objet.on_key(_Evenement("down"))
    evenement = _Evenement("enter")
    objet.on_key(evenement)
    assert evenement.arrete
    if suite == resultat.EcranResultatDuMaster.RETOUR:
        # Le retour est traite par `EcranResultat` lui-meme : il ne passe pas
        # par le rappel, il remonte au menu des ateliers (`EPIC11-ARB-13`).
        assert objet.app.ateliers == 1
        assert choisies == []
    else:
        assert choisies == [suite]


def test_AC_10_2_les_quatre_destinations_sont_DEUX_A_DEUX_distinctes(tmp_path):
    """Une dispatch qui rendrait toujours la meme chose ne passerait pas.

    Les trois suites de ce module sont confrontees sur leur **effet** -- ce que
    l'ouverture a recu, ce que le depilement a fait --, jamais sur leur libelle.
    """
    master = ecrit(tmp_path)
    vus = []

    app = _AppFactice(passages=2)
    resultat.suivre(app, master, resultat.SUITE_DOSSIER)
    vus.append(("dossier", app.palier_courant.etat, app.depiles,
                len(app.descendus)))

    app = _AppFactice(passages=2)
    resultat.suivre(app, master, resultat.SUITE_FICHIER)
    vus.append(("fichier", app.palier_courant.etat, app.depiles,
                len(app.descendus)))

    app = _AppFactice(passages=2)
    resultat.suivre(app, master, resultat.SUITE_AUTRE_LOT)
    vus.append(("autre", app.palier_courant.etat, app.depiles,
                len(app.descendus)))

    app = _AppFactice(passages=2)
    resultat.suivre(app, master, "Une suite que personne n'a ecrite")
    vus.append(("inconnue", app.palier_courant.etat, app.depiles,
                len(app.descendus)))

    effets = [effet[1:] for effet in vus]
    assert len(set(map(str, effets))) == 4, vus


def test_AC_10_2_SUITE_AUTRE_LOT_remonte_a_l_ouverture_et_PAS_plus_haut(
        tmp_path):
    """`EPIC11-ARB-13` : jamais a l'ecran projet. Le depilement s'arrete au
    premier palier non transitoire, c'est-a-dire a la page d'ouverture."""
    app = _AppFactice(passages=3)
    resultat.suivre(app, ecrit(tmp_path), resultat.SUITE_AUTRE_LOT)
    assert app.depiles == 3
    assert app.screen_stack == ["palier"]
    assert app.ateliers == 0


def test_AC_10_2_une_suite_INCONNUE_nomme_l_absence_au_lieu_de_se_taire(
        tmp_path):
    """« Une suite sans destination doit le DIRE, pas ne rien faire » (`K3`)."""
    app = _AppFactice()
    resultat.suivre(app, ecrit(tmp_path), "Publier sur la lune")
    assert len(app.descendus) == 1
    assert "Publier sur la lune" in str(app.descendus[0].__dict__.values())


def test_AC_10_2_les_deux_OUVERTURES_visent_le_bon_objet(tmp_path, monkeypatch):
    """Le dossier recoit le **parent**, le fichier recoit **le master**.

    Les deux se confondraient sans ce test, et la confusion ne se verrait qu'a
    l'usage : `xdg-open` ouvre indifferemment l'un et l'autre.
    """
    vus = {}
    monkeypatch.setattr(resultat, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda chemin: vus.setdefault("dossier", chemin) or "d")
    monkeypatch.setattr(resultat, "ouvrir_dans_la_visionneuse_du_systeme",
                        lambda chemin: vus.setdefault("fichier", chemin) or "f")
    master = ecrit(tmp_path)
    app = _AppFactice()
    resultat.ouvrir_le_dossier_du_master(app, master)
    resultat.ouvrir_le_fichier_du_master(app, master)
    assert vus["fichier"] == master.chemin
    assert vus["dossier"] == master.chemin.parent


def test_AC_10_2_les_deux_ouvertures_sont_SERVABLES_par_le_produit(tmp_path):
    """**Mesure de ce que le produit sait reellement faire**, pas une promesse.

    Une issue qui ne ferait rien serait un blocage sec deguise -- exactement ce
    qu'`EPIC11-ARB-89` ferme. On mesure donc l'argv REEL que le produit
    passerait au bureau, par les deux fonctions que ce module appelle.
    """
    master = ecrit(tmp_path)
    argv = []

    def lancer(commande, **_kwargs):
        argv.append(commande)
        return type("Issue", (), {"returncode": 0})()

    phrase = execution_partagee.ouvrir_dans_l_explorateur_du_systeme(
        master.chemin.parent, lancer=lancer, systeme="linux")
    autre = execution_partagee.ouvrir_dans_la_visionneuse_du_systeme(
        master.chemin, lancer=lancer, systeme="linux")
    assert argv[0][-1] == str(master.chemin.parent)
    assert argv[1][-1] == str(master.chemin)
    assert str(master.chemin.parent) in phrase and str(master.chemin) in autre


def test_AC_10_2_une_ouverture_qui_ECHOUE_dit_le_motif_au_lieu_de_lever(
        tmp_path):
    """Un conteneur sans bureau est le regime nominal des bancs -- et de la
    machine d'Egan quand il travaille en SSH. Le fait est **dit**."""
    master = ecrit(tmp_path)
    app = _AppFactice()

    def lancer(_commande, **_kwargs):
        raise FileNotFoundError("aucun xdg-open")

    phrase = execution_partagee.ouvrir_dans_l_explorateur_du_systeme(
        master.chemin.parent, lancer=lancer, systeme="linux")
    assert "xdg-open" in phrase
    assert app.palier_courant.etat is None


def test_AC_10_2_le_resultat_de_l_ouverture_est_POSE_en_ligne_d_etat(
        tmp_path, monkeypatch):
    """Un echec silencieux serait indistinguable d'une suite decorative."""
    monkeypatch.setattr(resultat, "ouvrir_dans_l_explorateur_du_systeme",
                        lambda _chemin: "Dossier ouvert : quelque part")
    app = _AppFactice()
    fait = resultat.ouvrir_le_dossier_du_master(app, ecrit(tmp_path))
    assert fait == "Dossier ouvert : quelque part"
    assert app.palier_courant.etat == fait


def test_AC_10_2_les_volets_symetriques_des_deux_ouvertures(tmp_path):
    """Elles ne sont pas proposees sans chemin ; ces phrases tiennent si un jour
    elles l'etaient."""
    master = dataclasses.replace(ecrit(tmp_path), chemin=None)
    assert resultat.suites_du_resultat(master) == [resultat.SUITE_AUTRE_LOT]
    app = _AppFactice()
    assert (resultat.ouvrir_le_dossier_du_master(app, master)
            == resultat.AUCUN_DOSSIER_A_OUVRIR)
    assert (resultat.ouvrir_le_fichier_du_master(app, master)
            == resultat.AUCUN_FICHIER_A_OUVRIR)


def test_AC_10_2_AUCUNE_lettre_n_est_un_raccourci_sur_cet_ecran(tmp_path):
    """`EPIC11-ARB-68` -- **verifie plutot que suppose**.

    La regle ne mord que sur un ecran portant un champ de saisie ; celui-ci
    n'en porte aucun (test suivant). La mesure est donc l'autre moitie : aucune
    lettre ne DECLENCHE quoi que ce soit, si bien qu'aucune n'aurait a etre
    disputee a un champ.
    """
    choisies = []
    objet = ecran(ecrit(tmp_path), sur_suite=choisies.append)
    for touche in ("o", "f", "e", "r", "d", "O", "R"):
        evenement = _Evenement(touche)
        objet.on_key(evenement)
        assert not evenement.arrete, touche
    assert choisies == []
    assert objet.curseur == 0
    assert objet.app.ateliers == 0


def test_AC_10_2_cet_ecran_ne_porte_AUCUN_champ_de_saisie(tmp_path):
    """La verification que la consigne demande de faire plutot que de supposer.

    Deux mesures : le module ne fabrique aucune saisie, et l'ecran ne traite
    aucune touche de caractere -- les cinq touches qu'il connait sont des
    touches de navigation.
    """
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    noms = {noeud.id for noeud in ast.walk(arbre) if isinstance(noeud, ast.Name)}
    assert noms & {"Input", "Saisie", "ChampDeSaisie"} == set()
    objet = ecran(ecrit(tmp_path))
    assert not hasattr(objet, "saisie")


def test_AC_10_2_le_rappel_de_suite_est_REQUIS_au_point_de_montage():
    """Finding `K3` : un defaut a `None` rendrait l'oubli silencieux.

    Quatre suites navigables et decoratives, c'est ce qu'Egan a trouve a la
    main le 2026-08-30 -- et le point d'appel etait le fautif, pas l'ecran.
    """
    import inspect
    signature = inspect.signature(resultat.ouvrir_le_resultat)
    assert signature.parameters["sur_suite"].default is inspect.Parameter.empty


def test_ouvrir_le_resultat_MONTE_l_ecran_et_pose_sa_ligne_d_etat(tmp_path):
    master = ecrit(tmp_path)
    app = _AppFactice()
    ecran_monte = resultat.ouvrir_le_resultat(app, master,
                                              sur_suite=lambda _s: None)
    assert app.descendus == [ecran_monte]
    # **Posee sur l'ECRAN et non sur l'application** : `push_screen` est
    # differe, donc une ligne ecrite via l'application viserait encore l'ecran
    # precedent (`coque.Palier.poser_etat`).
    assert ecran_monte._etat_courant == resultat.ligne_d_etat(master)


# ===========================================================================
# AC 10.3 -- la ligne d'etat porte une MESURE
# ===========================================================================

def test_AC_10_3_la_ligne_d_etat_porte_les_TROIS_mesures(tmp_path):
    master = ecrit(tmp_path)
    ligne = resultat.ligne_d_etat(master)
    assert master.taille in ligne
    assert resultat.MENTION_VERIFIEE in ligne
    assert resultat.AUCUN_REFUS in ligne


def test_AC_10_3_la_ligne_d_etat_SUIT_le_poids_mesure(tmp_path):
    """Elle bouge avec le disque : deux masters, deux lignes differentes."""
    petit = ecrit(tmp_path / "a", octets=4096)
    gros = ecrit(tmp_path / "b", octets=4096 * 4096)
    assert resultat.ligne_d_etat(petit) != resultat.ligne_d_etat(gros)
    assert petit.taille in resultat.ligne_d_etat(petit)


def test_AC_10_3_un_segment_que_PERSONNE_n_a_mesure_disparait(tmp_path):
    """Les deux moities, et aucune ne sort a zero."""
    sans_fichier = ecrit(tmp_path / "a", ecrire=False)
    sans_rapport = ecrit(tmp_path / "b", rapport={})
    assert "0 o" not in resultat.ligne_d_etat(sans_fichier)
    assert "écrits" not in resultat.ligne_d_etat(sans_fichier)
    assert resultat.MENTION_VERIFIEE not in resultat.ligne_d_etat(sans_rapport)
    assert resultat.MENTION_VERIFIEE in resultat.ligne_d_etat(ecrit(tmp_path / "c"))


def test_AC_10_3_les_CONSTATS_remplacent_aucun_refus_et_sortent_VERBATIM(
        tmp_path):
    """Les taire ferait de cette ligne une mesure fausse par omission ; les
    traduire serait un jugement que le coeur ne porte pas (`EPIC11-ARB-30`)."""
    code = encode.ENCODE_RESIDUES_SWEPT
    master = ecrit(tmp_path, constats=(code,))
    ligne = resultat.ligne_d_etat(master)
    assert code in ligne
    assert resultat.AUCUN_REFUS not in ligne
    assert resultat.AUCUN_REFUS in resultat.ligne_d_etat(ecrit(tmp_path / "b"))


#: Les jetons de touche du depot. Une ligne d'etat qui en porterait un
#: violerait `EPIC11-ARB-56` : « **aucune touche** -- une touche va a la ligne
#: des raccourcis ».
TOUCHES = ("⏎", "↑", "↓", "Tab", "Échap", "F1", "Ctrl", "Entree", "Echap")

#: Les tournures de conseil et de motif de conception. `EPIC11-ARB-56` :
#: « aucun conseil d'usage [...] aucun motif de conception ». C'est la meme
#: regle qui a fait retirer « si ce master a deja ete livre, ne l'ecrasez
#: pas » de l'ecran de conflit (`EPIC11-ARB-188`).
CONSEILS = ("vous pouvez", "n'oubliez", "pensez", "il faut", "afin de",
            "pour éviter", "parce que", "ne l'", "vérifiez", "appuyez")


def test_AC_10_3_la_ligne_d_etat_ne_porte_AUCUNE_touche(tmp_path):
    for master in (ecrit(tmp_path / "a"),
                   ecrit(tmp_path / "b", constats=("X",), ecrire=False)):
        ligne = resultat.ligne_d_etat(master)
        presents = [jeton for jeton in TOUCHES if jeton in ligne]
        assert presents == [], (ligne, presents)


def test_AC_10_3_la_ligne_d_etat_ne_CONSEILLE_aucun_usage(tmp_path):
    ligne = resultat.ligne_d_etat(ecrit(tmp_path)).lower()
    presents = [mot for mot in CONSEILS if mot in ligne]
    assert presents == [], (ligne, presents)


def test_le_detecteur_de_conseil_ROUGIT_sur_la_phrase_que_ARB_188_a_retiree():
    """Temoin des deux frontieres ci-dessus.

    Sans lui, un detecteur qui aurait cesse de mesurer resterait vert pour
    rien. La phrase est celle qu'Egan a fait retirer de l'ecran de conflit,
    verbatim.
    """
    retiree = "si ce master a déjà été livré, ne l'écrasez pas".lower()
    assert [mot for mot in CONSEILS if mot in retiree]
    assert [jeton for jeton in TOUCHES
            if jeton in "⏎ choisir  ↑↓ naviguer  Tab journal"]


def test_AC_10_3_la_ligne_d_etat_est_celle_DE_LA_MAQUETTE(tmp_path):
    """Aux deux ecarts que ce lot SIGNALE plutot que de les corriger en
    silence : le glyphe suivi d'UN espace (`jetons.marque`, redaction unique du
    depot, la ou le dessin en pose deux) et la taille a une decimale."""
    master = ecrit(tmp_path)
    dessinee = etat_de_la_maquette()
    rendue = resultat.ligne_d_etat(master)
    assert rendue.split(maxsplit=1)[0] == jetons.GLYPHES["complete"]
    assert dessinee.split(maxsplit=1)[0] == jetons.GLYPHES["complete"]
    assert (" ".join(rendue.split()[1:])
            == " ".join(dessinee.split()[1:]).replace("1,38", "1,4"))


def test_la_taille_de_la_maquette_n_est_PAS_RENDABLE_par_le_produit():
    """**L'ecart est mesure, pas suppose.**

    `explorateur.taille_lisible` est la **seule** redaction de taille du depot
    et rend une decimale sous 10 : aucun nombre d'octets ne rend `1,38 Go`. Le
    dessin demande donc une seconde redaction, que ce lot n'ecrit pas -- il le
    signale.
    """
    from mixed_media_utility.tui.explorateur import taille_lisible
    assert taille_lisible(OCTETS_DEMO) == "1,4 Go"
    assert "1,38 Go" in etat_de_la_maquette()
    assert all(taille_lisible(octets) != "1,38 Go"
               for octets in range(OCTETS_DEMO - 3, OCTETS_DEMO + 3))


# ===========================================================================
# La ligne de raccourcis, le journal, le bandeau
# ===========================================================================

def test_la_ligne_de_raccourcis_est_celle_DE_LA_MAQUETTE(tmp_path):
    """Et elle est **LUE du produit**, jamais recopiee : une seconde redaction
    divergerait au premier ajustement de libelle."""
    objet = ecran(ecrit(tmp_path))
    assert objet.raccourcis == RACCOURCIS_RESULTAT_AVEC_JOURNAL
    assert objet.raccourcis == raccourcis_de_la_maquette()
    assert RACCOURCIS_RESULTAT_AVEC_JOURNAL not in SOURCE_DU_MODULE.read_text(
        encoding="utf-8")


def test_l_ecran_annonce_F1_aide_et_JAMAIS_Q_quitter(tmp_path):
    """`EPIC11-ARB-140`, livre le 2026-09-02 : les ecrans de resultat portent
    `F1 aide`, aucun ne porte `Q quitter`."""
    objet = ecran(ecrit(tmp_path))
    assert "F1 aide" in objet.raccourcis
    assert "Q quitter" not in objet.raccourcis


def test_le_JOURNAL_porte_le_rapport_ffprobe_CHAMP_PAR_CHAMP(tmp_path):
    """`EPIC11-ARB-189` : il reste **en memoire**, montre puis perdu.

    Ce qu'il montre est ce que le coeur a **trouve** sur le fichier ecrit
    (`actual`), et l'ordre est celui du rapport -- trier serait un jugement.
    """
    master = ecrit(tmp_path)
    journal = resultat.journal_de_la_verification(master)
    assert [ligne.split(" : ")[0] for ligne in journal.lignes] == list(RAPPORT)
    assert "1920x1080" in journal.lignes[1]


def test_le_JOURNAL_porte_AUSSI_les_constats_du_coeur(tmp_path):
    """La commande les imprime (`  Constat: <code>`) ; les perdre a l'ecran
    ferait de la TUI une surface moins bavarde que la CLI sur la meme passe."""
    code = encode.ENCODE_RESIDUES_SWEPT
    journal = resultat.journal_de_la_verification(
        ecrit(tmp_path, constats=(code,)))
    assert journal.lignes[-1] == resultat.MOTIF_DU_CONSTAT.format(code=code)


def test_SANS_rien_a_lire_le_journal_est_ABSENT_et_Tab_n_est_pas_annonce(
        tmp_path):
    """Une touche annoncee qui ne fait rien se lit comme une panne.

    C'est la moitie symetrique de ce que `E4-4` a tranche dans l'autre sens :
    la ou il n'y a rien a lire, on n'annonce pas `Tab journal`.
    """
    master = ecrit(tmp_path, rapport={}, constats=())
    assert resultat.journal_de_la_verification(master) is None
    objet = ecran(master)
    assert objet.raccourcis == RACCOURCIS_RESULTAT
    assert "journal" not in objet.raccourcis
    evenement = _Evenement("tab")
    objet.on_key(evenement)
    assert not evenement.arrete


def test_Tab_deplie_le_journal_quand_il_y_en_a_un(tmp_path):
    objet = ecran(ecrit(tmp_path))
    evenement = _Evenement("tab")
    objet.on_key(evenement)
    assert evenement.arrete
    assert objet.journal_deplie


def test_la_droite_du_bandeau_est_celle_DE_LA_MAQUETTE(tmp_path):
    master = ecrit(tmp_path, frames=124, echantillons=124)
    assert master.objet_du_bandeau() in bandeau_de_la_maquette()


def test_la_droite_du_bandeau_est_LA_MEME_que_celle_de_l_ecran_d_execution(
        tmp_path):
    """Deux compositions du meme bandeau divergeraient au premier ajustement :
    celle de `E4-4` est la seule redaction, et cet ecran la lit."""
    master = ecrit(tmp_path, frames=63, echantillons=125)
    passage = execution_exports.PassageDeLEncodage(lot_id=master.lot_id,
                                                   frames=master.frames)
    assert master.objet_du_bandeau() == passage.objet_du_bandeau()


def test_un_cardinal_INCONNU_ne_rend_pas_un_bandeau_qui_ment(tmp_path):
    master = dataclasses.replace(ecrit(tmp_path), frames=None)
    assert master.objet_du_bandeau() == master.lot_id


def test_le_titre_du_bandeau_est_celui_de_l_ATELIER(tmp_path):
    assert resultat.EcranResultatDuMaster.titre == projet_lecture.EXPORTS
    assert projet_lecture.EXPORTS in bandeau_de_la_maquette()


# ===========================================================================
# Les deux regimes, la grille, et les frontieres du paquet
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_AUCUN_glyphe_de_cet_ecran_ne_sort_en_POINT_D_INTERROGATION(
        tmp_path, ascii_seul):
    """Le defaut paye par le signe multiplier le 2026-08-29, et par `▾` le
    2026-09-03 : un dessin hors table sort en `?` sous `--ascii`."""
    for master in (ecrit(tmp_path / "a", mesure=_Mesure(4.96)),
                   ecrit(tmp_path / "b", frames=63, echantillons=125,
                         constats=("X",), timecode=None)):
        for ligne in tout_ce_qui_s_affiche(master, ascii_seul):
            assert "?" not in ligne, ligne


def test_chaque_GLYPHE_de_cet_ecran_a_son_repli_dans_la_table():
    """Mesure directe sur `jetons.REPLIS_DE_TEXTE` et la table de glyphes.

    Les trois signes que cet ecran pose -- le glyphe de complet, le curseur des
    suites, le separateur -- sont pris de `jetons` et confrontes un a un.
    """
    for signe in (jetons.GLYPHES["complete"], jetons.GLYPHES["curseur"],
                  "·"):
        assert jetons.replier_ascii(signe) != "?", signe


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_ne_DEBORDE_de_la_grille_au_plancher(tmp_path, ascii_seul):
    """Le plancher d'`EPIC11-ARB-21` : ce qui tient a 100x30 peut deborder a
    80x24, et seule cette taille le demasque."""
    utile = jetons.largeur_utile(jetons.LARGEUR_PLANCHER)
    master = ecrit(tmp_path, mesure=_Mesure(4.96))
    for ligne in tout_ce_qui_s_affiche(master, ascii_seul):
        assert jetons.colonnes(ligne) <= utile, (jetons.colonnes(ligne), ligne)


def test_un_nom_de_master_TRES_long_ne_fait_pas_deborder_le_cartouche(tmp_path):
    """Le panneau abrege plutot que de laisser `textual` replier la ligne."""
    nom = "plan-" + "0" * 90 + "_mmu_prores_hq.mov"
    master = ecrit(tmp_path, nom=nom)
    for ligne in panneau(master):
        assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(
            jetons.LARGEUR_PLANCHER)


def test_le_module_n_importe_JAMAIS_cli(tmp_path):
    """`EPIC11-ARB-67` et la frontiere de la 11.4b : la TUI n'importe pas `cli`."""
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            assert "cli" not in (noeud.module or "").split(".")
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                assert "cli" not in alias.name.split(".")


def test_le_module_ne_LANCE_aucun_processus_et_passe_par_execution():
    """Frontiere AST, pas textuelle : la PROSE a le droit de nommer
    `subprocess` pour dire ou il est tolere (`EPIC11-ARB-85`) ; le CODE n'a
    le droit ni de l'importer ni de l'appeler."""
    source = SOURCE_DU_MODULE.read_text(encoding="utf-8")
    assert "ouvrir_dans_l_explorateur_du_systeme" in source
    assert "ouvrir_dans_la_visionneuse_du_systeme" in source
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                assert alias.name.split(".")[0] not in ("subprocess", "os")
        elif isinstance(noeud, ast.ImportFrom):
            assert (noeud.module or "").split(".")[0] not in ("subprocess",
                                                              "os", "sys")
        elif isinstance(noeud, ast.Name):
            assert noeud.id not in ("subprocess", "print")


def test_le_module_ne_MODIFIE_pas_execution_py():
    """La story ne touche pas `execution.py` : `E4-5` s'obtient par
    **sous-classement**, comme `T6-1`."""
    assert issubclass(resultat.EcranResultatDuMaster,
                      execution_partagee.EcranResultat)
    assert corps_de_classe("EcranResultatDuMaster") == {
        "titre", "__init__", "objet_du_bandeau", "etat"}


def test_le_module_n_ECRIT_rien(tmp_path):
    """Quand `E4-5` monte, l'ecriture est finie. Une suite est une navigation."""
    arbre = ast.parse(SOURCE_DU_MODULE.read_text(encoding="utf-8"))
    appels = {ast.unparse(noeud.func).split(".")[-1] for noeud in ast.walk(arbre)
              if isinstance(noeud, ast.Call)}
    assert appels & {"write_text", "write_bytes", "mkdir", "unlink", "replace",
                     "rename", "open", "persist_encode"} == set()
