# -*- coding: utf-8 -*-
"""Story 11.4d (absorbee comme lot F de la 11.4e) -- la TROISIEME issue.

Le point de jugement d'un conflit d'ecriture de l'atelier Extraction ne portait
qu'**une** issue qui ecrit, et cette issue detruit. `EPIC11-ARB-89`, verbatim
d'Egan : « au lieu d'un overwrite destructif, toujours proposer un versionnage
avec un suffixe [...] Mais toujours permettre une reecriture plutot qu'un
blocage sec. » Ce banc mesure les deux moities de cette phrase, sur les **deux**
chemins de conflit de l'atelier.

Trois regles de mesure, heritees de l'epic et rappelees parce qu'elles ont
chacune ete payees :

* **les fabriques produisent au moins TROIS elements distinguables**, et la
  cible se place au **milieu** autant qu'a **chaque bord** -- au milieu pour
  demasquer un `find` fautif, aux bords pour demasquer un balayage tronque
  (`CLAUDE.md`, regle des fabriques, point 4) ;
* **la position se verifie sur la liste que le CODE PARCOURT**, jamais sur
  celle que la fabrique ecrit. Trois collections sont en cause ici et elles ne
  sont pas la meme : `plan.lots`, `manifest["lots"]` et `ChoixExclusif.issues` ;
* **aucun litteral de longueur ni de rang** : la borne se lit dans
  `io.naming.CANONICAL_ID_MAX_LENGTH` et les bornes de rang dans
  `VERSION_RANK_MIN` / `VERSION_RANK_MAX`. Ce banc ne porte ni `48`, ni `64`,
  ni `99`.
"""
import ast
import json
import re
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility import extraction
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io.extraction_manifest import (
    LOT_WATERMARKS_FIELD,
    MANIFEST_FILENAME,
    LotStateConflictError,
    resolve_version_rank,
)
from mixed_media_utility.io.naming import (
    CANONICAL_ID_MAX_LENGTH,
    VERSION_RANK_MAX,
    VERSION_RANK_MIN,
    NamingError,
    build_lot_id,
)
from mixed_media_utility.io.project_layout import EXTRACT_FRAMES_DIRNAME
from mixed_media_utility.tui import atelier_extraction_ecriture as atelier
from mixed_media_utility.tui import execution
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import EcranEcrasement, EcranRefus
from mixed_media_utility.tui.panneau import ChoixExclusif, Issue

MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: **TROIS cadences a comptes DIFFERENTS**, jamais un remplissage uniforme :
#: une inversion d'appariement entre une cadence et son compte ne se voit
#: qu'a des valeurs distinctes.
TROIS_CADENCES = ((25.0, 124), (12.5, 42), (5.0, 17))

RUSH = "rush_01"
#: Un SECOND rush, pour que la fabrique de versions du manifeste porte un
#: `base_lot_id` **etranger** a la famille visee (AC 10.4). Sans lui, un
#: `resolve_version_rank` qui ignorerait `base_lot_id` rendrait le meme rang et
#: resterait vert.
AUTRE_RUSH = "rush_02"


class JournalMuet:
    """`run_extraction` en exige un ; on n'en lit rien."""

    def info(self, *args, **kwargs) -> None:
        pass

    warning = error = debug = info


# ===========================================================================
# Fabriques
# ===========================================================================

def entree_de_lot(lot_id: str, *, base: str | None = None,
                  rang: int | None = None, etat: str = "extraction") -> dict:
    """Une entree de `manifest["lots"]`, telle que le coeur la lit.

    Le rang vit dans `version_rank` et **jamais dans le nom** (`EPIC5-ARB-3`,
    relu par `rangs_employes_de_la_famille`) : une fabrique qui le deduirait du
    `lot_id` mesurerait sa propre convention au lieu de celle du coeur.
    """
    entree = {"lot_id": lot_id, "state": etat}
    if base is not None:
        entree["base_lot_id"] = base
    if rang is not None:
        entree["version_rank"] = rang
    return entree


def projet(tmp_path, nom="projet_demo", lots=(), lignes_d_eau=None) -> Path:
    """Un projet reel, cree par le coeur, dont on complete le manifeste."""
    chemin = creer_projet(tmp_path, nom).chemin
    document = json.loads(
        (chemin / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    if lots:
        document["lots"] = list(lots)
    if lignes_d_eau:
        document[LOT_WATERMARKS_FIELD] = dict(lignes_d_eau)
    (chemin / MANIFEST_FILENAME).write_text(json.dumps(document),
                                            encoding="utf-8")
    return chemin


def famille_de_versions(rush=RUSH, cadence=25.0, rangs=(2, 3, 4)) -> list[dict]:
    """La famille de versions d'un lot, **dans le manifeste**, plus un intrus.

    C'est `manifest["lots"]` que `resolve_version_rank` **parcourt** : c'est
    donc la seule liste ou la position de la cible mesure quoi que ce soit pour
    l'AC 2. Une fabrique qui rangerait trois lots dans `plan.lots` en laissant
    le manifeste a une entree rendrait un test vert qui ne mesure rien.

    La cible -- la famille visee -- est en **milieu de liste** : un lot d'un
    autre rush l'encadre des deux cotes, en **tete** et en **queue**. Les trois
    positions sont couvertes d'un coup : un `find` qui rendrait le premier lot
    verrait l'intrus de tete, un balayage qui sauterait la derniere entree
    manquerait l'intrus de queue -- et les deux modes de panne rendent un rang
    faux.
    """
    base = build_lot_id(rush, cadence)
    etranger = build_lot_id(AUTRE_RUSH, cadence)
    entrees = [entree_de_lot(etranger)]
    entrees.append(entree_de_lot(base))
    for rang in rangs:
        entrees.append(entree_de_lot(build_lot_id(rush, cadence,
                                                  version_rank=rang),
                                     base=base, rang=rang))
    entrees.append(entree_de_lot(
        build_lot_id(AUTRE_RUSH, cadence, version_rank=VERSION_RANK_MIN),
        base=etranger, rang=VERSION_RANK_MIN))
    return entrees


def plan(tmp_path, cadences=TROIS_CADENCES, dossier=None, **kwargs):
    """Le plan nominal du banc : **TROIS lots**, trois comptes differents."""
    dossier = dossier if dossier is not None else projet(tmp_path)
    kwargs.setdefault("largeur", 1920)
    kwargs.setdefault("hauteur", 1080)
    return atelier.preparer_le_plan(
        dossier, rush_id=RUSH, video_path=tmp_path / f"{RUSH}.mov",
        cadences=cadences, **kwargs)


def peupler(lot) -> None:
    """Poser un fichier dans le dossier d'un lot : c'est ce que le coeur mesure."""
    lot.dossier.mkdir(parents=True, exist_ok=True)
    (lot.dossier / "0001.tiff").write_bytes(b"deja la")


def plan_en_conflit_de_dossier(tmp_path, rang_cible=1):
    """Un plan de trois lots dont le lot `rang_cible` est deja sur le disque."""
    dossier = projet(tmp_path)
    provisoire = plan(tmp_path, dossier=dossier)
    peupler(provisoire.lots[rang_cible])
    return plan(tmp_path, dossier=dossier)


def plan_en_conflit_d_etat(tmp_path, rang_cible=1, etat="pdf"):
    """Un plan de trois lots dont le lot `rang_cible` est deja passe a `pdf`."""
    cibles = [build_lot_id(RUSH, valeur) for valeur, _ in TROIS_CADENCES]
    lots = [entree_de_lot(lot_id,
                          etat=etat if rang == rang_cible else "extraction")
            for rang, lot_id in enumerate(cibles)]
    return plan(tmp_path, dossier=projet(tmp_path, lots=lots))


def coque(**kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def monter(banc, p, mesure=None, **kwargs):
    """Monter le point de jugement sur `p` et rendre `(ecran, ecrits, mesure)`.

    `mesure` est appelee **dans** le pilote, sur l'ecran monte : tout ce qui lit
    `self.app` -- la composition du cartouche, la largeur courante -- n'existe
    que le temps de l'application, et le mesurer apres coup leve.

    `ascii_seul` et `sans_couleur` vont a la **coque** et non a l'ouverture du
    point de jugement : c'est l'application qui porte le regime de repli, et
    tout ce qui compose lit `self.app.ascii_seul`. Les passer a
    `ouvrir_le_point_de_jugement` leverait sur un mot-cle inconnu -- ce qui est
    la bonne panne, mais pas celle qu'un appelant cherche.
    """
    ecrits = []
    boite = {}
    reglages = {cle: kwargs.pop(cle)
                for cle in ("ascii_seul", "sans_couleur") if cle in kwargs}
    #: La taille du banc va au PILOTE, pas a la coque : c'est elle qui donne
    #: `app.size`, dont toute la geometrie derive. La laisser au plancher est
    #: le defaut ; la faire varier est le seul moyen de mesurer qu'une hauteur
    #: est **derivee** de la fenetre et non ecrite quelque part.
    taille = kwargs.pop("taille", None)

    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_le_point_de_jugement(
            pilote.app, p, sur_ecriture=ecrits.append, **kwargs)
        boite["ecran"] = ecran
        await pilote.pause()
        boite["mesure"] = mesure(ecran) if mesure is not None else None
        return None

    if taille is None:
        banc(coque(**reglages), tour)
    else:
        banc(coque(**reglages), tour, taille)
    return boite["ecran"], ecrits, boite["mesure"]


def cartouche(banc, p):
    """Les lignes du cartouche de l'ecran monte, mesurees dans le pilote."""
    _, _, lignes = monter(banc, p, mesure=lambda e: list(e.lignes_du_panneau()))
    return "\n".join(lignes)


def extracteur(par_cadence):
    """Un double de `run_extraction` qui ENREGISTRE ce que le coeur recoit."""
    appels = []

    def faux(**kwargs):
        appels.append(kwargs)
        reponse = par_cadence[kwargs["fps_target"]]
        if isinstance(reponse, BaseException):
            raise reponse
        return reponse

    faux.appels = appels
    return faux


def issue_reussie(dossier_projet, lot_id, frames):
    dossier = Path(dossier_projet) / EXTRACT_FRAMES_DIRNAME / lot_id
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "0001.tiff").write_bytes(b"x")
    return extraction.ExtractionOutcome(
        granted=True, message=f"{frames} frame(s)", lot_id=lot_id,
        frames_dir=dossier, written_frame_count=frames)


def executer(p, faux):
    from mixed_media_utility.tui.execution import SurfaceExecution
    return atelier.executer_le_plan(
        p, SurfaceExecution(unite=atelier.UNITE), logger=JournalMuet(),
        extraire=faux)


#: Les deux chemins de conflit, parametres partout ou une AC dit « pour chacun
#: des deux chemins ». Les nommer ici plutot que de dupliquer chaque test est ce
#: qui garantit qu'aucun des deux n'est oublie a l'ajout d'une mesure.
CHEMINS = [
    pytest.param(plan_en_conflit_de_dossier, id="dossier-deja-peuple"),
    pytest.param(plan_en_conflit_d_etat, id="lot-deja-passe-a-pdf"),
]


# ===========================================================================
# AC 1 -- le panneau porte au moins DEUX issues qui ecrivent
# ===========================================================================

def test_le_panneau_de_conflit_porte_DEUX_issues_qui_ECRIVENT(tmp_path):
    """AC 1.1. La mesure porte sur le **cardinal**, jamais sur les libelles.

    Un test qui chercherait `LIBELLE_NOUVELLE_VERSION` dans la liste resterait
    vert si l'issue perdait son `ecrit=True` -- c'est-a-dire si elle cessait
    d'etre une issue qui ecrit tout en gardant son nom.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    choix = atelier.issues_de_l_ecrasement(p)
    assert len(choix.actions_qui_ecrivent) == len(
        (atelier.ISSUE_ECRASER, atelier.ISSUE_NOUVELLE_VERSION))
    assert choix.sortie_sans_ecriture is not None


def test_les_DEUX_issues_qui_ecrivent_sont_l_ECRASEMENT_et_la_VERSION(tmp_path):
    """AC 1.4, volet symetrique du cardinal : ce sont bien **ces** deux-la.

    Sans lui, deux issues quelconques marquees `ecrit=True` passeraient la
    mesure du cardinal.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    choix = atelier.issues_de_l_ecrasement(p)
    assert [i.cle for i in choix.actions_qui_ecrivent] == [
        atelier.ISSUE_ECRASER, atelier.ISSUE_NOUVELLE_VERSION]


def test_les_libelles_des_deux_issues_sont_des_CONSTANTES_de_module(tmp_path):
    """AC 1.4 : « jamais des litteraux au point d'appel ».

    L'un nomme la **destruction**, l'autre dit **ce qui sera cree** -- et le
    second se compose par `libelle_de_la_version`, seule redaction du rang a
    l'ecran.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    choix = atelier.issues_de_l_ecrasement(p)
    assert choix.issue(atelier.ISSUE_ECRASER).libelle == atelier.LIBELLE_ECRASER
    # **Pas de tautologie** : le rang attendu est celui que le COEUR rend pour
    # ce lot, pas celui que le plan a retenu. Comparer le libelle a
    # `libelle_de_la_version(p.rang_de_version)` seul resterait vert si les deux
    # cotes lisaient le meme rang faux.
    manifeste = json.loads(
        (p.dossier_projet / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    attendu = resolve_version_rank(manifeste, RUSH, p.lots[0].fps_target)
    assert choix.issue(atelier.ISSUE_NOUVELLE_VERSION).libelle == (
        atelier.LIBELLE_NOUVELLE_VERSION.format(rang=attendu))
    source = ast.parse(Path(atelier.__file__).read_text(encoding="utf-8"))
    dans_les_issues = [
        n for n in ast.walk(source)
        if isinstance(n, ast.FunctionDef)
        and n.name == "issues_de_l_ecrasement"]
    litteraux = [c.value for n in dans_les_issues for c in ast.walk(n)
                 if isinstance(c, ast.Constant) and isinstance(c.value, str)
                 and c is not n.body[0].value]
    assert litteraux == [], (
        f"un libelle litteral s'est glisse dans issues_de_l_ecrasement : "
        f"{litteraux}")


@pytest.mark.parametrize("fabrique", CHEMINS)
def test_le_curseur_au_montage_ne_vise_AUCUNE_des_deux_issues_qui_ecrivent(
        tmp_path, fabrique):
    """AC 1.2. `EPIC11-ARB-7` mesure **face a deux issues ecrivantes**.

    La garde de `panneau.py` cherche « la premiere qui n'ecrit pas » et reste
    correcte -- mais elle n'avait jamais ete mesuree sur un panneau qui en porte
    deux, ou une garde qui se contenterait de fuir `issues[0]` s'arreterait sur
    la seconde, c'est-a-dire sur une issue qui ecrit.
    """
    choix = atelier.issues_de_l_ecrasement(fabrique(tmp_path))
    assert choix.issue_sous_le_curseur is not None
    assert not choix.issue_sous_le_curseur.ecrit
    assert choix.retenue is None


@pytest.mark.parametrize("fabrique", CHEMINS)
def test_AUCUN_BLOCAGE_SEC_ne_subsiste_sur_les_deux_chemins_de_conflit(
        tmp_path, banc, fabrique):
    """AC 1.3 -- **la frontiere negative**, une mesure par chemin.

    Elle porte sur l'ecran **monte**, pas sur la fonction de fabrique : c'est
    `ouvrir_le_point_de_jugement` qui decide quel ecran repond a quel conflit,
    et c'est ce choix-la qui a laisse le second chemin sans issue pendant toute
    la vague.

    **Ce que cette frontiere ne mesure PAS** : le regime ou le coeur refuse la
    version -- rangs epuises, ou nom versionne trop long. Le panneau y garde
    `Écraser et réextraire` et le refus du coeur, qui nomme lui-meme sa seconde
    issue ; il n'est donc pas un blocage sec non plus, mais son cardinal d'issues
    ecrivantes vaut un. Ce regime a ses propres mesures plus bas.
    """
    ecran, _, _ = monter(banc, fabrique(tmp_path))
    assert isinstance(ecran, EcranEcrasement)
    assert len(ecran.choix.actions_qui_ecrivent) >= len(
        (atelier.ISSUE_ECRASER, atelier.ISSUE_NOUVELLE_VERSION))


def test_SANS_conflit_le_panneau_NOMINAL_garde_son_issue_UNIQUE(tmp_path, banc):
    """Volet symetrique : sans lui, un ecran d'ecrasement rendu **toujours**
    passerait la frontiere precedente.

    `E2-3` n'est pas un conflit : il n'a rien a versionner et rien a detruire.
    """
    ecran, _, _ = monter(banc, plan(tmp_path))
    assert not isinstance(ecran, EcranEcrasement)
    assert len(ecran.choix.actions_qui_ecrivent) == 1


# ===========================================================================
# AC 2 -- le rang est LU au manifeste, le nom MONTRE avant de valider
# ===========================================================================

def test_le_rang_vient_de_resolve_version_rank_et_de_NULLE_PART_AILLEURS(
        tmp_path):
    """AC 2.1. La cible est **au milieu** de `manifest["lots"]`, encadree par
    un lot d'un autre rush en tete **et** en queue.

    La valeur attendue est celle que le coeur rend, appelee avec les memes
    arguments : la recopier ici poserait une seconde redaction de la regle de
    rang -- celle-la meme qu'`EPIC11-ARB-92` a deja renversee une fois.
    """
    lots = famille_de_versions(rangs=(2, 3, 4))
    dossier = projet(tmp_path, lots=lots)
    p = plan(tmp_path, dossier=dossier)
    manifeste = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert p.lots[0].rang_de_version == resolve_version_rank(
        manifeste, RUSH, TROIS_CADENCES[0][0])


def test_un_TROU_dans_la_famille_ne_REND_PAS_le_rang(tmp_path):
    """`EPIC11-ARB-92` : « Il ne faut pas rendre le rang. »

    Le volet qui distingue « premier rang libre » de « ligne d'eau plus un ».
    Sans lui, la mesure precedente resterait verte sur les deux semantiques,
    puisqu'elles coincident sur une famille sans trou. La TUI n'en sait rien --
    et c'est le propos : elle montre ce que le coeur rend.
    """
    lots = famille_de_versions(rangs=(2, 4))
    p = plan(tmp_path, dossier=projet(tmp_path, lots=lots))
    assert p.lots[0].rang_de_version > max((2, 4))


def test_le_nom_versionne_MONTRE_est_celui_que_build_lot_id_RENDRAIT(tmp_path):
    """AC 2.2. `EPIC11-ARB-46` : « l'apercu ne peut jamais mentir. »

    L'apercu ne le peut que s'il appelle la **meme** fonction que l'ecriture,
    avec le meme rang. La mesure porte sur les **trois** lots du plan : un
    appariement positionnel entre un lot et son nom versionne ne se voit qu'a
    trois cadences distinctes.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    for lot in p.lots:
        assert lot.lot_id_versionne == build_lot_id(
            RUSH, lot.fps_target, version_rank=lot.rang_de_version)
        assert lot.lot_id_versionne != lot.lot_id


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_nom_versionne_est_VISIBLE_avant_toute_validation(tmp_path,
                                                             ascii_seul):
    """AC 2.3 : dans le cartouche, pas dans un ecran ulterieur.

    Les **trois** noms versionnes s'y lisent, et chacun a cote du nom que
    l'ecrasement reecrirait : les deux issues qui ecrivent nomment donc leur
    sortie avant que l'operateur retienne quoi que ce soit.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    rendu = atelier.panneau_de_l_ecrasement(
        p, jetons.LARGEUR_PLANCHER, ascii_seul).rendu(
            jetons.LARGEUR_PLANCHER, ascii_seul)
    texte = "\n".join(rendu)
    for lot in p.lots:
        assert lot.lot_id_versionne in texte
        assert lot.lot_id in texte


@pytest.mark.parametrize("fabrique,attendus,absents", [
    pytest.param(plan_en_conflit_de_dossier,
                 (atelier.LIBELLE_DEJA,),
                 (atelier.LIBELLE_ETAT_DEJA_AVANCE,), id="dossier-seul"),
    pytest.param(plan_en_conflit_d_etat,
                 (atelier.LIBELLE_ETAT_DEJA_AVANCE,),
                 (atelier.LIBELLE_DEJA,), id="etat-seul"),
])
def test_le_cartouche_n_ouvre_QUE_les_blocs_qui_COMPTENT(tmp_path, fabrique,
                                                         attendus, absents):
    """Chaque conflit ouvre son bloc, et **seulement** le sien.

    Un conflit d'etat seul -- le lot est passe a `pdf`, ses frames peuvent avoir
    ete supprimees -- montait « Déjà sur le disque   0 lots » : une ligne qui ne
    dit rien, sur l'ecran le plus charge de l'atelier. Le volet symetrique tient
    l'autre sens : un conflit de dossier seul ne doit pas annoncer un etat.
    """
    rendu = "\n".join(atelier.panneau_de_l_ecrasement(
        fabrique(tmp_path)).rendu())
    for libelle in attendus:
        assert libelle in rendu, rendu
    for libelle in absents:
        assert libelle not in rendu, rendu


def test_les_DEUX_blocs_s_ouvrent_quand_les_DEUX_conflits_sont_la(tmp_path):
    """Le troisieme regime : un lot deja sur le disque **et** un autre deja
    passe a `pdf`. Sans lui, un cartouche qui n'ouvrirait jamais qu'un bloc
    passerait les deux mesures precedentes.

    Les deux cibles sont **distinctes** et ni l'une ni l'autre en premiere
    position : le lot sur le disque est en queue, celui a `pdf` au milieu.
    """
    cibles = [build_lot_id(RUSH, valeur) for valeur, _ in TROIS_CADENCES]
    dossier = projet(tmp_path, lots=[
        entree_de_lot(cibles[1], etat="pdf")])
    provisoire = plan(tmp_path, dossier=dossier)
    peupler(provisoire.lots[-1])
    p = plan(tmp_path, dossier=dossier)
    assert p.ecrase and p.conflit_d_etat
    rendu = "\n".join(atelier.panneau_de_l_ecrasement(p).rendu())
    assert atelier.LIBELLE_DEJA in rendu
    assert atelier.LIBELLE_ETAT_DEJA_AVANCE in rendu


def test_les_noms_apparies_TIENNENT_la_grille_et_gardent_les_DEUX_cotes(
        tmp_path):
    """Le volet geometrique de l'appariement, sur un nom **long**.

    Le budget se partage ; les deux moities sont abregees **au milieu**, jamais
    par la fin -- un nom versionne coupe par la fin perdrait son rang,
    c'est-a-dire exactement ce qui le distingue de l'autre.
    """
    long = "r" * (CANONICAL_ID_MAX_LENGTH // len(("gauche", "droite")))
    dossier = projet(tmp_path)
    p = atelier.preparer_le_plan(
        dossier, rush_id=long, video_path=tmp_path / f"{long}.mov",
        cadences=TROIS_CADENCES, largeur=1920, hauteur=1080)
    lignes = atelier.noms_du_conflit(p, jetons.LARGEUR_PLANCHER, False)
    assert len(lignes) == len(p.lots)
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(
            jetons.LARGEUR_PLANCHER), (jetons.colonnes(ligne), ligne)
        gauche, _, droite = ligne.partition(atelier.SEPARATEUR_DES_NOMS)
        assert gauche.strip() and droite.strip(), ligne


#: Les noms qui designent un RANG DE VERSION, et eux seuls. `rang` tout court
#: est le mot du depot pour « index de ligne » -- il apparait dans une
#: quinzaine de modules de `tui/` sans jamais parler de version --, et une
#: frontiere qui l'attraperait serait affaiblie a la premiere relecture. La
#: liste est donc etroite et **nommee**.
NOMS_DE_RANG_DE_VERSION = ("version_rank", "rang_de_version", "rang_propose")

#: Une composition litterale du fragment de version. La mesure porte sur la
#: **valeur** de la chaine, pas sur sa graphie dans la source : `f"_v{n}"` se
#: lit a l'AST comme la constante `_v` suivie d'une interpolation, et
#: `"_v" + str(n)` comme la meme constante. La forme exacte -- `_v` seul, ou
#: `_v` suivi de chiffres -- exclut la prose : un docstring qui ecrit
#: « le fragment `_v<N>` » ne vaut ni l'un ni l'autre.
MOTIF_DU_SUFFIXE = re.compile(r"^_v\d*$")


def infractions_de_rang(source: str, nom: str = "<memoire>") -> list[str]:
    """Les trois interdits de l'AC 2.4, trouves a l'AST d'une source.

    **Une seule redaction, employee par la frontiere ET par son volet
    symetrique** : deux redactions permettraient au motif de se ramollir d'un
    cote sans que l'autre le voie -- c'est-a-dire une frontiere verte a vide,
    ce que ce depot a deja paye.
    """
    arbre = ast.parse(source, filename=nom)
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            if MOTIF_DU_SUFFIXE.match(noeud.value):
                trouves.append(f"suffixe compose : {noeud.value!r}")
        if isinstance(noeud, ast.BinOp) and isinstance(
                noeud.op, (ast.Add, ast.Sub)):
            # **Les operandes DIRECTS, jamais l'arbre entier.** Une
            # concatenation de trois textes dont le dernier mentionne un rang
            # -- `TITRE + SEPARATEUR + phrase.format(rang=...)` -- n'est pas une
            # arithmetique de rang, et l'attraper aurait fait rougir un autre
            # atelier sur du texte.
            directs = []
            for cote in (noeud.left, noeud.right):
                if isinstance(cote, ast.Name):
                    directs.append(cote.id)
                elif isinstance(cote, ast.Attribute):
                    directs.append(cote.attr)
            if any(mot in n for n in directs
                   for mot in NOMS_DE_RANG_DE_VERSION):
                trouves.append(f"arithmetique de rang : {ast.unparse(noeud)}")
        if isinstance(noeud, ast.FunctionDef) and "version_suffix" in noeud.name:
            trouves.append(f"redaction locale : {noeud.name}")
    return trouves


def test_AUCUN_calcul_de_rang_ni_composition_de_SUFFIXE_dans_la_TUI():
    """AC 2.4 -- **la frontiere negative de l'epic**, portee sur `tui/` entier.

    Trois interdits, mesures a l'AST du paquet : une composition litterale du
    fragment de version, une arithmetique sur une variable **nommee** rang de
    version, une redaction locale du formateur de suffixe.

    **Ce que ce motif ne peut PAS voir, dit plutot que tu** (meme honnetete que
    `test_conformite_sorties_nommees.py`) :

    * une composition passant par une variable intermediaire dont le nom ne
      figure pas dans :data:`NOMS_DE_RANG_DE_VERSION` -- l'AST voit les noms,
      pas les valeurs. `rang` tout court en est volontairement absent : c'est le
      mot du depot pour « index de ligne », present dans une quinzaine de
      modules sans jamais parler de version ;
    * une arithmetique faite dans un module hors `tui/` et importee ici ;
    * un `+ 1` ecrit `rang + un` avec `un = 1` pose ailleurs.

    Elle est le **complement** de
    `test_versionnage_du_scan_en_tui.test_AUCUN_module_de_la_TUI_ne_redige_une
    _regle_de_RANG`, qui compte a zero le vocabulaire du coeur dans `tui/` :
    celle-la interdit d'APPELER la regle, celle-ci d'en REECRIRE une.
    """
    paquet = Path(atelier.__file__).parent
    interdits = {}
    for module in sorted(paquet.glob("*.py")):
        trouves = infractions_de_rang(
            module.read_text(encoding="utf-8"), module.name)
        if trouves:
            interdits[module.name] = trouves
    assert interdits == {}, interdits


def test_la_frontiere_de_l_AC_2_4_MORD_bien_sur_une_composition_fabriquee():
    """Le volet symetrique, sans lequel la frontiere pourrait etre verte a vide.

    Un motif qui ne reconnaitrait plus rien passerait le test precedent sur un
    paquet entier. On lui donne donc une source qui porte les **trois** formes,
    et on mesure qu'il les voit toutes les trois.
    """
    faux = (
        'def format_version_suffix(version_rank):\n'
        '    return f"_v{version_rank}"\n'
        'suivant = version_rank + 1\n'
    )
    trouves = infractions_de_rang(faux, "faux.py")
    familles = {t.split(" :")[0] for t in trouves}
    assert familles == {"suffixe compose", "arithmetique de rang",
                        "redaction locale"}, trouves


def test_des_lots_a_RANGS_DIVERGENTS_ne_font_nommer_AUCUN_rang(tmp_path):
    """`EPIC11-ARB-46` : « l'apercu ne peut jamais mentir. »

    Chaque cadence est une famille de versions **distincte** -- le `base_lot_id`
    porte la cadence. Un rush deja versionne a 25 fps et vierge a 12,5 consomme
    donc deux rangs differents, et une issue qui en nommerait un annoncerait un
    nom faux pour deux lots sur trois.

    La famille versionnee est celle de la **premiere** cadence : c'est le cas ou
    « rendre le rang du premier lot » a l'air juste, et ou il ment le plus.
    """
    lots = famille_de_versions(cadence=TROIS_CADENCES[0][0], rangs=(2, 3, 4))
    p = plan(tmp_path, dossier=projet(tmp_path, lots=lots))
    assert len({lot.rang_de_version for lot in p.lots}) > 1
    assert p.version_proposable is True
    assert p.rang_de_version is None
    libelle = atelier.issues_de_l_ecrasement(p).issue(
        atelier.ISSUE_NOUVELLE_VERSION).libelle
    assert libelle == atelier.LIBELLE_NOUVELLES_VERSIONS
    assert not any(c.isdigit() for c in libelle), libelle


def test_des_lots_a_RANG_COMMUN_le_NOMMENT(tmp_path):
    """Le volet symetrique : sans lui, un libelle pluriel rendu **toujours**
    passerait le test precedent, et l'operateur ne saurait plus jamais quel rang
    il consomme.

    Un plan a une seule cadence a forcement un rang commun.
    """
    lots = famille_de_versions(cadence=TROIS_CADENCES[0][0], rangs=(2, 3, 4))
    p = plan(tmp_path, dossier=projet(tmp_path, lots=lots),
             cadences=(TROIS_CADENCES[0],))
    assert p.rang_de_version is not None
    libelle = atelier.issues_de_l_ecrasement(p).issue(
        atelier.ISSUE_NOUVELLE_VERSION).libelle
    assert libelle == atelier.LIBELLE_NOUVELLE_VERSION.format(
        rang=p.rang_de_version)


@pytest.mark.parametrize("interdit", ["premier rang libre", "le trou",
                                      "rang suivant", "maximum"])
def test_le_panneau_montre_le_NOM_et_n_explique_PAS_la_REGLE(tmp_path,
                                                             interdit):
    """AC 2.5. La semantique du rang a deja change une fois dans le coeur
    (`EPIC11-ARB-92`) : un ecran qui montre le nom rendu par le coeur survit aux
    deux lectures, un ecran qui explique la regle devra etre reecrit.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    textes = [
        "\n".join(atelier.panneau_de_l_ecrasement(p).rendu()),
        "\n".join(i.libelle for i in atelier.issues_de_l_ecrasement(p).issues),
        atelier.phrase_du_cout_de_la_version(p),
    ]
    for texte in textes:
        assert interdit not in texte.lower(), texte


# ===========================================================================
# AC 3 -- les deux issues appellent le coeur, chacune par son drapeau
# ===========================================================================

def choisir(banc, p, cle):
    """Retenir une issue au point de jugement et rendre le plan transmis."""
    ecrits = []
    boite = {}

    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_le_point_de_jugement(
            pilote.app, p, sur_ecriture=ecrits.append)
        boite["ecran"] = ecran
        await pilote.pause()
        ecran.choix.viser(cle)
        await pilote.press("enter")
        await pilote.pause()
        return None

    banc(coque(), tour)
    assert ecrits, f"l'issue {cle!r} n'a declenche aucune ecriture"
    return ecrits[0]


def test_CREER_LA_VERSION_appelle_le_coeur_avec_nouvelle_version_SEULE(
        tmp_path, banc):
    """AC 3.1 : `nouvelle_version=True`, **sans** `ecrasement_conscient` et
    **sans** `overwrite`.

    `overwrite` porte sur le dossier du lot d'ORIGINE ; le passer ferait ecraser
    ce que cette issue existe precisement pour ne pas toucher.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    retenu = choisir(banc, p, atelier.ISSUE_NOUVELLE_VERSION)
    faux = extracteur({valeur: issue_reussie(
        p.dossier_projet, build_lot_id(RUSH, valeur,
                                       version_rank=p.rang_de_version), compte)
        for valeur, compte in TROIS_CADENCES})
    executer(retenu, faux)
    assert faux.appels, "aucun appel au coeur"
    for appel in faux.appels:
        assert appel["nouvelle_version"] is True
        assert appel["ecrasement_conscient"] is False
        assert appel["overwrite"] is False


def test_ECRASER_SCIEMMENT_appelle_le_coeur_avec_les_DEUX_mots_cles(
        tmp_path, banc):
    """AC 3.2 : `ecrasement_conscient=True` **et** `consent_granted=True`.

    Le second n'est pas optionnel -- le coeur ne traite `ecrasement_conscient`
    que consenti, et l'envoyer seul serait une issue inerte.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    retenu = choisir(banc, p, atelier.ISSUE_ECRASER)
    faux = extracteur({valeur: issue_reussie(
        p.dossier_projet, build_lot_id(RUSH, valeur), compte)
        for valeur, compte in TROIS_CADENCES})
    executer(retenu, faux)
    for appel in faux.appels:
        assert appel["ecrasement_conscient"] is True
        assert appel["consent_granted"] is True
        assert appel["nouvelle_version"] is False


@pytest.mark.parametrize("conduite", atelier.CONDUITES)
def test_les_DEUX_drapeaux_ne_partent_JAMAIS_ensemble(tmp_path, conduite):
    """AC 3.3 : l'exclusivite est tenue **avant** l'appel, jamais rattrapee.

    Elle n'est pas verifiee, elle est **structurelle** : la conduite est un
    champ a trois valeurs et les deux drapeaux en sont derives. L'etat que le
    coeur refuse nommement -- « deux issues DISTINCTES du meme conflit
    d'ecriture et ne se combinent pas » -- n'est pas representable.

    La mesure balaie les **trois** conduites, pas seulement les deux
    interessantes : une quatrieme valeur ajoutee sans y penser ferait rougir ici
    avant de faire lever le coeur.
    """
    p = atelier.replace(plan(tmp_path), conduite=conduite)
    assert not (p.nouvelle_version and p.ecrasement_conscient)


def test_une_conduite_INCONNUE_est_REFUSEE_a_la_construction(tmp_path):
    """Le volet symetrique : sans lui, une conduite mal orthographiee vaudrait
    « nominale » en silence -- c'est-a-dire qu'un ecrasement conscient se
    degraderait en refus, et une version en ecrasement. Deux pannes muettes,
    chacune du cote destructif.
    """
    with pytest.raises(ValueError, match="Conduite d'ecriture inconnue"):
        atelier.replace(plan(tmp_path), conduite="ecrasement")


def test_le_rapport_porte_le_lot_id_RENDU_PAR_LE_COEUR_sur_un_lot_versionne(
        tmp_path, banc):
    """AC 3.4 : `issue.lot_id`, jamais celui du plan.

    Sur une nouvelle version les deux different -- c'est **le** cas ou
    `lot_id or lot.lot_id` doit prendre sa premiere branche, et le seul ou un
    mutant qui inverserait les deux mourrait.

    La cible est au **milieu** de `plan.lots` : le second des trois porte un
    nom rendu par le coeur qui differe de celui que le plan avait prevu.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    retenu = choisir(banc, p, atelier.ISSUE_NOUVELLE_VERSION)
    attendus = {valeur: build_lot_id(RUSH, valeur,
                                     version_rank=p.rang_de_version)
                for valeur, _ in TROIS_CADENCES}
    faux = extracteur({valeur: issue_reussie(p.dossier_projet,
                                             attendus[valeur], compte)
                       for valeur, compte in TROIS_CADENCES})
    rapport = executer(retenu, faux)
    assert [lot.lot_id for lot in rapport.lots_ecrits] == [
        attendus[valeur] for valeur, _ in TROIS_CADENCES]
    assert all(lot.lot_id not in p.noms_conventionnels
               for lot in rapport.lots_ecrits)


def test_la_DECLARATION_DE_PASSE_annonce_les_noms_VERSIONNES(tmp_path, banc):
    """`EPIC11-ARB-46`, volet execution : annoncer `rush_01_25` pendant qu'on
    ecrit `rush_01_25_v2` ferait chercher un dossier qui n'existe pas."""
    from mixed_media_utility.tui.execution import SurfaceExecution
    p = plan_en_conflit_de_dossier(tmp_path)
    retenu = choisir(banc, p, atelier.ISSUE_NOUVELLE_VERSION)
    surface = SurfaceExecution(unite=atelier.UNITE)
    faux = extracteur({valeur: issue_reussie(
        p.dossier_projet, build_lot_id(RUSH, valeur,
                                       version_rank=p.rang_de_version), compte)
        for valeur, compte in TROIS_CADENCES})
    atelier.executer_le_plan(retenu, surface, logger=JournalMuet(),
                             extraire=faux)
    annonces = [lot.nom for lot in surface.passe.lots]
    assert annonces == [lot.lot_id_versionne for lot in retenu.lots]


def test_en_conduite_NOMINALE_les_deux_drapeaux_restent_FAUX(tmp_path):
    """Volet symetrique des deux mesures d'appel : sans lui, un module qui
    poserait `nouvelle_version=True` en dur les passerait toutes les deux."""
    p = plan(tmp_path)
    faux = extracteur({valeur: issue_reussie(p.dossier_projet,
                                             build_lot_id(RUSH, valeur), compte)
                       for valeur, compte in TROIS_CADENCES})
    executer(p, faux)
    for appel in faux.appels:
        assert appel["nouvelle_version"] is False
        assert appel["ecrasement_conscient"] is False


# ===========================================================================
# AC 4 -- le lot deja passe a `pdf` cesse d'etre un cul-de-sac
# ===========================================================================

def test_un_lot_deja_a_PDF_ouvre_un_POINT_DE_JUGEMENT_et_non_un_ECRAN_DE_REFUS(
        tmp_path, banc):
    """AC 4.1. C'etait le blocage sec : `ouvrir_le_refus` montait un `EcranRefus`
    avec `non_ecrit=[]` et **aucune suite**.

    Le lot vise est le **second** des trois : une garde qui ne regarderait que
    `lots[0]` ne se demasque pas autrement.
    """
    ecran, _, _ = monter(banc, plan_en_conflit_d_etat(tmp_path, rang_cible=1))
    assert not isinstance(ecran, EcranRefus)
    assert isinstance(ecran, EcranEcrasement)
    assert len(ecran.choix.actions_qui_ecrivent) >= len(
        (atelier.ISSUE_ECRASER, atelier.ISSUE_NOUVELLE_VERSION))


@pytest.mark.parametrize("rang_cible", [0, 1, len(TROIS_CADENCES) - 1])
def test_le_conflit_d_etat_est_VU_a_CHAQUE_position_du_plan(tmp_path,
                                                            rang_cible):
    """La regle des fabriques, point 4 : la cible au milieu **et a chaque bord**.

    Au milieu, elle demasque un `find` fautif ; en queue, elle demasque un
    balayage tronque -- un `for lot in plan.lots[:-1]` resterait vert sur les
    deux autres positions.
    """
    p = plan_en_conflit_d_etat(tmp_path, rang_cible=rang_cible)
    assert p.conflit_d_etat is True
    assert [lot.lot_id for lot in p.lots_en_conflit_d_etat] == [
        p.lots[rang_cible].lot_id]


def test_un_plan_SANS_lot_avance_n_ouvre_PAS_le_point_de_jugement(tmp_path,
                                                                  banc):
    """Volet symetrique : sans lui, un `conflit_d_etat` toujours vrai passerait
    la mesure precedente, et l'atelier ne montrerait plus jamais `E2-3`."""
    p = plan_en_conflit_d_etat(tmp_path, rang_cible=1, etat="extraction")
    assert p.conflit_d_etat is False
    ecran, _, _ = monter(banc, p)
    assert not isinstance(ecran, EcranEcrasement)


def test_la_garde_refus_d_etat_de_lot_RESTE_et_refuse_TOUJOURS(tmp_path):
    """AC 4.2. `EPIC11-ARB-83` : la garde est **load-bearing**, et la story ne
    change que ce qui **suit** le refus.

    Deux volets : elle refuse toujours un lot avance, et elle laisse toujours
    passer un lot `extraction`.
    """
    avance = atelier.LotPrevu(12.5, 42, "l", tmp_path / "x", False, "pdf")
    nominal = atelier.LotPrevu(12.5, 42, "l", tmp_path / "x", False,
                               "extraction")
    assert atelier.refus_d_etat_de_lot(avance) is not None
    assert atelier.refus_d_etat_de_lot(avance).code == (
        LotStateConflictError.__name__)
    assert atelier.refus_d_etat_de_lot(nominal) is None


def test_le_plan_en_conflit_d_etat_N_ENTRE_PAS_dans_executer_le_plan(tmp_path,
                                                                     banc):
    """AC 4.3 : le conflit est connu **au plan**, donc juge avant la serie.

    La mesure est double : le point de jugement s'ouvre, et **aucun** appel au
    coeur n'a lieu tant qu'aucune issue n'est retenue.
    """
    p = plan_en_conflit_d_etat(tmp_path, rang_cible=1)
    ecran, ecrits, _ = monter(banc, p)
    assert isinstance(ecran, EcranEcrasement)
    assert ecrits == [], "aucune ecriture avant qu'une issue soit retenue"


def test_ECRASER_SCIEMMENT_franchit_la_garde_d_etat_au_lieu_d_etre_INERTE(
        tmp_path, banc):
    """Le volet sans lequel la seconde issue serait un decor.

    La garde de la TUI refusait le lot `pdf` **avant** l'appel : gardee telle
    quelle, elle aurait rendu « Écraser et réextraire » inatteignable sur ce
    chemin -- un blocage sec deguise en issue. Le coeur, lui, contourne son
    propre refus pour cet appel seul et journalise l'avertissement.
    """
    p = plan_en_conflit_d_etat(tmp_path, rang_cible=1)
    retenu = choisir(banc, p, atelier.ISSUE_ECRASER)
    faux = extracteur({valeur: issue_reussie(p.dossier_projet,
                                             build_lot_id(RUSH, valeur), compte)
                       for valeur, compte in TROIS_CADENCES})
    rapport = executer(retenu, faux)
    assert rapport.refus is None
    assert [a["fps_target"] for a in faux.appels] == [
        valeur for valeur, _ in TROIS_CADENCES]


def test_le_refus_EN_COURS_DE_SERIE_garde_son_message_et_son_CONSERVE(
        tmp_path):
    """AC 4.4 -- non-regression, sur **trois** lots, refus sur le **DEUXIEME**.

    C'est le filet du cas ou l'etat change entre le plan et l'execution. Ce qui
    precede reste ecrit et nomme ; le message du coeur voyage verbatim.
    """
    p = plan_en_conflit_d_etat(tmp_path, rang_cible=1)
    faux = extracteur({valeur: issue_reussie(p.dossier_projet,
                                             build_lot_id(RUSH, valeur), compte)
                       for valeur, compte in TROIS_CADENCES})
    rapport = executer(p, faux)
    assert [lot.lot_id for lot in rapport.lots_ecrits] == [p.lots[0].lot_id]
    assert rapport.refus.code == LotStateConflictError.__name__
    assert rapport.refus.message == atelier.refus_d_etat_de_lot(
        p.lots[1]).message
    assert [a["fps_target"] for a in faux.appels] == [TROIS_CADENCES[0][0]]


# ===========================================================================
# AC 5 -- `action_qui_ecrit` cesse d'etre un `find` fautif
# ===========================================================================

def trois_issues(cible_en_seconde=True) -> ChoixExclusif:
    """Trois issues **distinguables**, dont deux ecrivent, cible au MILIEU."""
    return ChoixExclusif([
        Issue("premiere", "Première action", ecrit=True),
        Issue("cible", "Action visée", ecrit=cible_en_seconde),
        Issue("sortie", "Annuler"),
    ])


def test_actions_qui_ecrivent_rend_TOUTES_les_issues_qui_ecrivent():
    """AC 5.1, la forme plurielle. `action_qui_ecrit` ne pouvait rendre qu'un
    cardinal de zero ou un ; une frontiere qui compte les issues ecrivantes ne
    peut pas s'ecrire avec elle."""
    choix = trois_issues()
    assert [i.cle for i in choix.actions_qui_ecrivent] == ["premiere", "cible"]
    assert choix.action_qui_ecrit.cle == "premiere"


def test_actions_qui_ecrivent_est_une_LISTE_relisible_deux_fois():
    """Un generateur epuise rendrait zero a la seconde lecture -- et une
    frontiere qui en prend le cardinal apres l'avoir parcouru serait verte a
    vide."""
    choix = trois_issues()
    assert len(choix.actions_qui_ecrivent) == len(choix.actions_qui_ecrivent)


def test_le_docstring_d_action_qui_ecrit_NE_MENT_PLUS():
    """AC 5.3 : « elle ne reste pas en place en mentant ».

    Elle disait « l'issue qui ecrit », au singulier defini. La mesure porte sur
    le texte parce que c'est exactement ce que l'AC exige de corriger -- une
    propriete qui survit en promettant l'unicite est pire qu'une propriete
    retiree.
    """
    doc = ChoixExclusif.action_qui_ecrit.__doc__ or ""
    assert "PREMIERE" in doc
    assert "plusieurs" in doc.lower()


def test_libelle_de_l_action_nomme_l_action_SOUS_LE_CURSEUR(banc):
    """AC 5.2. La cible est en **deuxieme position sur trois**, et le mutant
    « rendre la premiere » doit mourir.

    La ligne d'etat d'un nom refuse nomme ce qui devient inaccessible : avec
    deux issues ecrivantes, nommer la premiere alors que le curseur est sur la
    seconde annonce l'inaccessibilite d'une action que personne n'a demandee.
    """
    from mixed_media_utility.tui.execution import PanneauConfirmation
    from mixed_media_utility.tui.panneau import Panneau

    choix = trois_issues()
    ecran = PanneauConfirmation(Panneau(TITRE_DESSINE_DU_PANNEAU, []), choix)
    boite = {}

    async def tour(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.choix.viser("cible")
        boite["vise"] = ecran.libelle_de_l_action()
        ecran.choix.viser("premiere")
        boite["premiere"] = ecran.libelle_de_l_action()
        return None

    banc(coque(), tour)
    assert boite["vise"] == "Action visée"
    assert boite["premiere"] == "Première action"


def test_libelle_de_l_action_REFUSE_D_ELIRE_quand_le_curseur_n_ecrit_pas(banc):
    """Le troisieme cas, celui qui refuse de deviner.

    Curseur sur une issue qui n'ecrit pas et **deux** ecrivantes : rendre la
    premiere serait le `find` fautif que cette methode vient de perdre. On rend
    une chaine vide.
    """
    from mixed_media_utility.tui.execution import PanneauConfirmation
    from mixed_media_utility.tui.panneau import Panneau

    choix = trois_issues()
    ecran = PanneauConfirmation(Panneau(TITRE_DESSINE_DU_PANNEAU, []), choix)
    boite = {}

    async def tour(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.choix.viser("sortie")
        boite["vide"] = ecran.libelle_de_l_action()
        return None

    banc(coque(), tour)
    assert boite["vide"] == ""


def test_un_panneau_a_UNE_SEULE_issue_ecrivante_la_nomme_TOUJOURS(banc):
    """Volet symetrique, et c'est le regime de presque tous les ecrans du
    produit : une seule issue ecrivante, curseur sur `Annuler` au montage.

    Rendre vide ici aurait casse la ligne d'etat des trois autres ateliers.
    """
    from mixed_media_utility.tui.execution import PanneauConfirmation
    from mixed_media_utility.tui.panneau import Panneau

    choix = trois_issues(cible_en_seconde=False)
    ecran = PanneauConfirmation(Panneau(TITRE_DESSINE_DU_PANNEAU, []), choix)
    boite = {}

    async def tour(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        boite["nomme"] = ecran.libelle_de_l_action()
        return None

    banc(coque(), tour)
    assert boite["nomme"] == "Première action"


# ===========================================================================
# AC 6 -- ce que chaque issue COUTE
# ===========================================================================

def test_le_cartouche_garde_la_phrase_de_l_ECRASEMENT(tmp_path, banc):
    """AC 6.1 : ce qu'ecraser ne regenere pas reste affiche.

    **ECART AC/CODE, `EPIC11-ARB-245`.** L'AC nomme UNE phrase
    (`CE_QUE_CA_NE_FAIT_PAS`) ; l'arbitrage l'a dedoublee en deux lignes
    courtes, parce qu'a 96 colonnes elle ne tenait pas dans un cartouche de 72
    et sortait AMPUTEE -- `jetons.ajuster` abrege, il ne replie pas. Le texte
    de l'AC n'est pas reecrit ; l'ecart est nomme au registre de la 11.4e.
    """
    rendu = cartouche(banc, plan_en_conflit_de_dossier(tmp_path))
    assert EcranEcrasement.ECRASER_DETRUIT in rendu
    assert EcranEcrasement.NE_REGENERE_PAS in rendu


def test_le_cartouche_gagne_le_SYMETRIQUE_pour_la_VERSION(tmp_path, banc):
    """AC 6.2 : creer une version n'efface rien et occupe le disque **en plus**.

    Le chiffre est celui que le plan a deja calcule -- le majorant de la ligne
    « Espace disque » --, jamais un chiffre en dur. La mesure compare les deux
    a la source commune.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    phrase = atelier.phrase_du_cout_de_la_version(p)
    assert phrase in cartouche(banc, p)
    assert atelier.taille_lisible(p.octets_majorants) in phrase


def test_sans_MAJORANT_la_phrase_de_la_version_ne_CHIFFRE_RIEN(tmp_path):
    """Volet symetrique : un trou dans la phrase, ou pire un zero, annoncerait
    que la version ne coute rien."""
    dossier = projet(tmp_path)
    p = atelier.preparer_le_plan(
        dossier, rush_id=RUSH, video_path=tmp_path / f"{RUSH}.mov",
        cadences=TROIS_CADENCES)
    assert p.octets_majorants is None
    phrase = atelier.phrase_du_cout_de_la_version(p)
    assert phrase == atelier.CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE
    assert not any(c.isdigit() for c in phrase)


#: `Suppr` en tant que TOUCHE : le mot entier, jamais un prefixe.
#:
#: **La mesure etait une sous-chaine, et `EPIC11-ARB-245` l'a fait mordre a
#: faux.** La maquette `T4-2`, validee par Egan, ouvre le cartouche sur
#: « Écraser **supprime** le lot deja sur le disque » -- le verbe, pas la
#: touche. Une sous-chaine `suppr` y voit une promesse de raccourci ; ce que
#: l'AC 6.3 interdit est de nommer la TOUCHE avant que la story 11.11 la
#: livre, pas de dire ce qu'ecraser fait. La bordure de mot rend la
#: distinction, et le volet symetrique ci-dessous mesure qu'elle mord encore.
TOUCHE_SUPPR = re.compile(r"\bsuppr\b", re.IGNORECASE)


def test_AUCUNE_phrase_de_l_atelier_ne_promet_la_touche_SUPPR(tmp_path, banc):
    """AC 6.3 : la suppression d'un element de projet est la story 11.11.

    Tant qu'elle n'est pas livree, l'ecran ne dit pas `Suppr` et ne renvoie a
    aucun raccourci -- une issue inerte est pire qu'absente.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    ecran, _, lignes = monter(
        banc, p, mesure=lambda e: list(e.lignes_du_panneau()))
    texte = "\n".join(lignes + [i.libelle for i in ecran.choix.issues]
                      + [ecran.raccourcis])
    assert TOUCHE_SUPPR.search(texte) is None, texte


def test_la_frontiere_de_la_touche_SUPPR_MORD_ENCORE():
    """Volet symetrique : une bordure de mot qui n'attraperait plus rien.

    Elle doit rendre la TOUCHE dans les trois formes ou une ligne la nommerait
    -- ouvreur d'item, milieu de phrase, fin de ligne -- et laisser passer le
    VERBE, qui est ce que la maquette `T4-2` emploie.
    """
    for promesse in ("Suppr supprimer cette version",
                     "⏎ valider  Suppr retirer  Échap retour",
                     "la touche est Suppr"):
        assert TOUCHE_SUPPR.search(promesse) is not None, promesse
    for innocent in (EcranEcrasement.ECRASER_DETRUIT,
                     "Ecraser supprime puis reecrit",
                     "suppression du lot"):
        assert TOUCHE_SUPPR.search(innocent) is None, innocent


@pytest.mark.parametrize("touche", ["Ctrl", "F1", "Tab", "Échap", "Entrée"])
def test_les_phrases_de_COUT_ne_nomment_AUCUNE_touche(tmp_path, touche):
    """AC 6.4. `EPIC11-ARB-56` : « une MESURE, jamais une touche ni un conseil ».

    La ligne de raccourcis a le droit de nommer des touches ; les phrases de
    cout du cartouche, non.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    for phrase in (atelier.phrase_du_cout_de_la_version(p),
                   atelier.CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE,
                   EcranEcrasement.ECRASER_DETRUIT,
                   EcranEcrasement.NE_REGENERE_PAS):
        assert touche.lower() not in phrase.lower(), phrase


# ===========================================================================
# AC 7 -- la ligne de raccourcis, mesuree apres `EPIC11-ARB-122`
# ===========================================================================

def test_la_story_n_ajoute_AUCUN_jeton_pour_CHOISIR_une_issue(tmp_path, banc):
    """AC 7.1 : les deux issues se choisissent avec `↑↓` et se retiennent avec
    `⏎`, deja annonces. `EPIC11-ARB-45` : « le curseur EST la selection ».

    **ECART AC/CODE, `EPIC11-ARB-245`.** L'AC dit « aucun jeton de raccourci
    ajoute » ; l'arbitrage en ajoute un -- `Ctrl+↓ lire la suite` --, et il le
    fallait : un cartouche qui defile sans touche annoncee est un cartouche
    dont personne ne lit la suite. Ce que l'AC visait tient toujours, et c'est
    ce que ce test mesure desormais : **aucun jeton neuf pour CHOISIR une
    issue**. La ligne de l'ecran d'ecrasement est celle de la confirmation,
    plus la touche du pli et rien d'autre. Ecart nomme au registre de la 11.4e.
    """
    ecran, _, ligne = monter(banc, plan_en_conflit_de_dossier(tmp_path),
                             mesure=lambda e: e.raccourcis)
    assert ligne == atelier.RACCOURCIS_EXTRACTION_ECRASEMENT
    jetons_de_choix = set(atelier.RACCOURCIS_EXTRACTION_CONFIRMATION.split("  "))
    ajoutes = set(ligne.split("  ")) - jetons_de_choix
    assert ajoutes == {atelier.JETON_DU_PLI}, ajoutes


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_de_raccourcis_des_DEUX_ecrans_de_jugement_ne_DEBORDE_PAS(
        ascii_seul):
    """AC 7.2 : mesure en UTF-8 **et** en repli ASCII -- c'est l'ASCII qui
    contraint, `⏎` y valant six colonnes.

    Le budget se **lit** de la geometrie, il ne se recopie pas : `76` pose ici
    serait une seconde source de verite.
    """
    for ligne in (atelier.RACCOURCIS_EXTRACTION_CONFIRMATION,
                  atelier.RACCOURCIS_EXTRACTION_ECRASEMENT):
        if ascii_seul:
            ligne = jetons.replier_ascii(ligne)
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(), (
            jetons.colonnes(ligne), ligne)


# ===========================================================================
# AC 8 -- aucun nombre en dur, la borne se nomme
# ===========================================================================

def test_ce_BANC_ne_porte_AUCUN_litteral_de_longueur_canonique():
    """AC 8.1, volet banc : « aucun litteral de longueur [...] dans les bancs
    de cette story ».

    La borne a deja ete citee de memoire et fausse **trois** fois dans ce depot
    (`CLAUDE.md`) : elle se lit dans le code, jamais dans un document, et jamais
    dans un test.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source, filename=__file__)
    interdits = {CANONICAL_ID_MAX_LENGTH, VERSION_RANK_MAX}
    trouves = [n.value for n in ast.walk(arbre)
               if isinstance(n, ast.Constant) and isinstance(n.value, int)
               and not isinstance(n.value, bool) and n.value in interdits]
    assert trouves == [], (
        f"litteraux de borne recopies dans le banc : {trouves}")


def test_le_refus_de_LONGUEUR_du_coeur_est_relaye_VERBATIM(tmp_path, banc):
    """AC 8.2 : le nom versionne est plus long que le nom de base de la largeur
    du fragment `_v<N>`, donc le refus de `build_lot_id` devient atteignable par
    la version alors qu'il ne l'etait pas par le lot d'origine.

    L'identifiant est **calibre par rapport a la constante**, jamais par rapport
    a un nombre ecrit ici : `CANONICAL_ID_MAX_LENGTH` moins la place du
    fragment de cadence.
    """
    # Un rush juste assez long pour que le lot d'origine passe et que la
    # version ne passe pas. La marge se lit du coeur : on cherche la premiere
    # longueur qui fait lever `build_lot_id` avec un rang.
    long = None
    for taille in range(CANONICAL_ID_MAX_LENGTH, 0, -1):
        candidat = "r" * taille
        try:
            build_lot_id(candidat, 25.0)
        except NamingError:
            continue
        try:
            build_lot_id(candidat, 25.0, version_rank=VERSION_RANK_MIN)
        except NamingError:
            long = candidat
            break
    assert long is not None, (
        "aucune longueur ne separe le lot d'origine de sa version : l'AC 8.2 "
        "ne mesure plus rien")

    attendu = None
    try:
        build_lot_id(long, 25.0, version_rank=VERSION_RANK_MIN)
    except NamingError as refus:
        attendu = str(refus)

    dossier = projet(tmp_path)
    p = atelier.preparer_le_plan(
        dossier, rush_id=long, video_path=tmp_path / f"{long}.mov",
        cadences=TROIS_CADENCES, largeur=1920, hauteur=1080)
    peupler(p.lots[1])
    p = atelier.preparer_le_plan(
        dossier, rush_id=long, video_path=tmp_path / f"{long}.mov",
        cadences=TROIS_CADENCES, largeur=1920, hauteur=1080)

    assert p.version_proposable is False
    assert p.refus_de_version == attendu
    assert attendu in cartouche(banc, p)


def test_un_refus_de_VERSION_laisse_le_panneau_avec_une_issue_QUI_ECRIT(
        tmp_path, banc):
    """Le volet qui empeche ce regime d'etre un blocage sec.

    Le message du coeur nomme lui-meme sa seconde issue -- « ecraser sciemment
    la version existante plutot que d'en creer une nouvelle » --, et c'est
    exactement celle que le panneau garde.
    """
    long = None
    for taille in range(CANONICAL_ID_MAX_LENGTH, 0, -1):
        candidat = "r" * taille
        try:
            build_lot_id(candidat, 25.0)
        except NamingError:
            continue
        try:
            build_lot_id(candidat, 25.0, version_rank=VERSION_RANK_MIN)
        except NamingError:
            long = candidat
            break
    dossier = projet(tmp_path)
    p = atelier.preparer_le_plan(
        dossier, rush_id=long, video_path=tmp_path / f"{long}.mov",
        cadences=TROIS_CADENCES, largeur=1920, hauteur=1080)
    peupler(p.lots[1])
    p = atelier.preparer_le_plan(
        dossier, rush_id=long, video_path=tmp_path / f"{long}.mov",
        cadences=TROIS_CADENCES, largeur=1920, hauteur=1080)
    ecran, _, _ = monter(banc, p)
    cles = [i.cle for i in ecran.choix.actions_qui_ecrivent]
    assert cles == [atelier.ISSUE_ECRASER]
    assert ecran.choix.sortie_sans_ecriture is not None


def test_les_RANGS_EPUISES_relaient_le_refus_du_coeur_VERBATIM(tmp_path, banc):
    """L'autre refus du coeur, celui de `resolve_version_rank`.

    La famille porte **tous** les rangs de `VERSION_RANK_MIN` a
    `VERSION_RANK_MAX` : la borne se lit du coeur, elle ne s'ecrit pas ici.
    """
    cadence = TROIS_CADENCES[0][0]
    base = build_lot_id(RUSH, cadence)
    lots = [entree_de_lot(build_lot_id(AUTRE_RUSH, cadence))]
    lots.append(entree_de_lot(base))
    lots.extend(entree_de_lot(build_lot_id(RUSH, cadence, version_rank=rang),
                              base=base, rang=rang)
                for rang in range(VERSION_RANK_MIN, VERSION_RANK_MAX + 1))
    dossier = projet(tmp_path, lots=lots)
    p = plan(tmp_path, dossier=dossier, cadences=(TROIS_CADENCES[0],))
    assert p.version_proposable is False
    assert p.refus_de_version is not None
    assert str(VERSION_RANK_MAX) in p.refus_de_version


def famille_epuisee(cadence) -> list[dict]:
    """Une famille dont **tous** les rangs sont consommes, pour UNE cadence."""
    base = build_lot_id(RUSH, cadence)
    entrees = [entree_de_lot(base)]
    entrees.extend(
        entree_de_lot(build_lot_id(RUSH, cadence, version_rank=rang),
                      base=base, rang=rang)
        for rang in range(VERSION_RANK_MIN, VERSION_RANK_MAX + 1))
    return entrees


@pytest.mark.parametrize("rang_cible", [0, 1, len(TROIS_CADENCES) - 1])
def test_UN_SEUL_lot_sans_rang_SUFFIT_a_retirer_l_issue_de_version(tmp_path,
                                                                   rang_cible):
    """Le mutant `all` -> `any` de `version_proposable`, et il a SURVECU a la
    premiere campagne.

    Il survivait parce qu'aucune fabrique ne produisait un plan **mixte** : dans
    tous les cas mesures, ou bien les trois lots avaient un rang, ou bien aucun.
    Or c'est exactement le regime que la propriete existe pour couvrir -- chaque
    cadence est une famille de versions independante, donc l'une peut avoir
    epuise ses rangs pendant que les autres sont vierges.

    Ce que `any` produirait : l'issue offerte, le libelle pluriel (les rangs
    divergent), et `run_extraction(nouvelle_version=True)` appele pour les trois
    lots -- dont un que le coeur refusera **au milieu de la serie**, c'est-a-dire
    apres avoir ecrit les autres. C'est la panne que
    `EPIC11-ARB-89` interdit d'atteindre par une issue proposee.

    La cible passe aux **trois** positions : un balayage tronque
    (`self.lots[:-1]`) resterait vert sur les deux premieres.
    """
    cadence = TROIS_CADENCES[rang_cible][0]
    dossier = projet(tmp_path, lots=famille_epuisee(cadence))
    p = plan(tmp_path, dossier=dossier)

    sans_rang = [rang for rang, lot in enumerate(p.lots)
                 if lot.rang_de_version is None]
    assert sans_rang == [rang_cible], (
        "la fabrique doit produire un plan MIXTE : un seul lot sans rang")
    assert p.version_proposable is False
    assert p.rang_de_version is None

    cles = [i.cle for i in atelier.issues_de_l_ecrasement(p).issues]
    assert atelier.ISSUE_NOUVELLE_VERSION not in cles, cles
    assert atelier.ISSUE_ECRASER in cles, (
        "retirer la version ne doit jamais fermer le panneau")


def test_les_bornes_de_RANG_ne_sont_pas_RECOPIEES_dans_la_TUI():
    """AC 8.3 : lues au coeur si elles sont affichees, jamais recopiees."""
    paquet = Path(atelier.__file__).parent
    fautifs = {}
    for module in sorted(paquet.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        # **Scope assume** : seuls les modules qui PARLENT de version peuvent
        # confondre la borne de rang avec un autre nombre. `avancement.py`
        # porte un `99` qui est un pourcentage, et l'attraper ferait rougir une
        # frontiere de versionnage sur du code qui n'en fait pas.
        if "version" not in source:
            continue
        arbre = ast.parse(source, filename=str(module))
        valeurs = [n.value for n in ast.walk(arbre)
                   if isinstance(n, ast.Constant) and isinstance(n.value, int)
                   and not isinstance(n.value, bool)
                   and n.value == VERSION_RANK_MAX]
        if valeurs:
            fautifs[module.name] = valeurs
    assert fautifs == {}, fautifs


# ===========================================================================
# AC 9 -- la frontiere de surface
# ===========================================================================

def test_TOUT_point_de_jugement_de_l_atelier_qui_peut_ECRASER_porte_DEUX_issues(
        tmp_path, banc):
    """AC 9.2 -- le pendant TUI de `test_conformite_sorties_nommees.py`.

    Le corpus est l'ensemble **exact** des points de jugement de l'atelier
    Extraction, chacun monte, et la mesure ne porte que sur ceux qui peuvent
    ecraser une sortie existante.

    **Ce que cette frontiere ne mesure PAS**, dit plutot que tu :

    * les points de jugement des **autres** ateliers -- Scan, Pdf, Exports ont
      chacun leur propre banc, et un corpus transverse serait une seconde
      redaction de trois inventaires ;
    * un point de jugement qui serait ajoute **sans** passer par
      `ouvrir_le_point_de_jugement` : le corpus est nomme, pas decouvert. C'est
      la limite assumee, et c'est pourquoi le corpus est verifie non vide.
    """
    corpus = {
        "conflit de dossier": plan_en_conflit_de_dossier(tmp_path / "a"),
        "conflit d'etat": plan_en_conflit_d_etat(tmp_path / "b"),
        "nominal": plan(tmp_path / "c"),
    }
    assert corpus, "un corpus vide rendrait cette frontiere verte a vide"
    manquants = {}
    for nom, p in corpus.items():
        ecran, _, _ = monter(banc, p)
        if not p.en_conflit:
            continue
        if len(ecran.choix.actions_qui_ecrivent) < len(
                (atelier.ISSUE_ECRASER, atelier.ISSUE_NOUVELLE_VERSION)):
            manquants[nom] = [i.cle for i in ecran.choix.actions_qui_ecrivent]
    assert manquants == {}, manquants


# ===========================================================================
# AC 10 -- les fabriques, appliquees a CETTE story
# ===========================================================================

def test_les_fabriques_de_ce_BANC_produisent_TROIS_elements_DISTINGUABLES(
        tmp_path):
    """AC 10.1 et 10.3 : trois elements distincts dans **chacune** des trois
    collections que le code parcourt, et jamais un remplissage uniforme.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    assert len({lot.lot_id for lot in p.lots}) == len(TROIS_CADENCES)
    assert len({lot.frames for lot in p.lots}) == len(TROIS_CADENCES)

    lots = famille_de_versions()
    assert len({e["lot_id"] for e in lots}) == len(lots)
    bases = {e.get("base_lot_id") for e in lots if e.get("base_lot_id")}
    assert len(bases) > 1, (
        "le manifeste doit porter un lot d'un AUTRE rush, sans quoi un "
        "`base_lot_id` ignore ne se voit pas")

    choix = atelier.issues_de_l_ecrasement(p)
    assert len({i.cle for i in choix.issues}) == len(choix.issues)


def test_la_famille_de_versions_place_l_INTRUS_en_TETE_ET_en_QUEUE():
    """AC 10.4, et la regle des fabriques, point 4.

    La cible au milieu demasque un `find` fautif ; elle ne demasque **pas** un
    balayage tronque. Un intrus a chaque bord ferme les deux modes de panne.
    """
    lots = famille_de_versions()
    etranger = build_lot_id(AUTRE_RUSH, 25.0)
    assert lots[0]["lot_id"] == etranger
    assert lots[-1].get("base_lot_id") == etranger
    milieu = [e for e in lots[1:-1]]
    assert any(e.get("version_rank") for e in milieu)


# ===========================================================================
# `EPIC11-ARB-245` -- le cartouche DEFILE, et la ligne de pli NOMME
#
# Egan, par invite le 2026-09-05 : « Faire defiler le cartouche », puis devant
# la maquette `T4-2` : « super je valide ». Le defaut corrige est arithmetique
# et il PREEXISTAIT au lot F : ce cartouche rendait 22 lignes pour 17 a un lot,
# 24 aux deux chemins de conflit reunis, et sa phrase d'avertissement de 96
# colonnes sortait AMPUTEE -- `jetons.ajuster` abrege, il ne replie pas.
#
# La hauteur est mesuree par `test_sobriete_et_grille_extraction.py`, qui
# porte le corpus des ecrans a cartouche. Ce banc-ci mesure ce que le pli
# **dit** : ce qu'il garde visible, ce qu'il nomme, et ce qu'il ne vole pas
# aux issues.
# ===========================================================================

#: Un cartouche a DEUX lots en conflit de dossier, cible en TETE **et** en
#: QUEUE du plan. Le cas n'a pas de maquette -- le pli l'absorbe par
#: construction --, et c'est exactement pour cela qu'il doit se mesurer :
#: « le pli l'absorbe » est une affirmation tant que rien ne la joue.
def plan_a_deux_lots_en_conflit(tmp_path):
    dossier = projet(tmp_path)
    provisoire = plan(tmp_path, dossier=dossier)
    peupler(provisoire.lots[0])
    peupler(provisoire.lots[-1])
    return plan(tmp_path, dossier=dossier)


def plan_aux_DEUX_chemins_de_conflit(tmp_path):
    """Un lot en conflit de DOSSIER (en tete) et un autre d'ETAT (en queue).

    Le cartouche le plus charge que l'atelier sache produire : ses deux blocs
    s'ouvrent, et chacun porte une cible de bord.
    """
    cibles = [build_lot_id(RUSH, valeur) for valeur, _ in TROIS_CADENCES]
    lots = [entree_de_lot(lot_id,
                          etat="pdf" if rang == len(cibles) - 1
                          else "extraction")
            for rang, lot_id in enumerate(cibles)]
    dossier = projet(tmp_path, lots=lots)
    provisoire = plan(tmp_path, dossier=dossier)
    peupler(provisoire.lots[0])
    return plan(tmp_path, dossier=dossier)


#: Les QUATRE etats de conflit, parametres partout ou une mesure du pli doit
#: valoir pour tous. Le nominal a un lot est le cas de la maquette ; les trois
#: autres sont ceux qu'elle ne montre pas.
ETATS_DE_CONFLIT = [
    pytest.param(plan_en_conflit_de_dossier, id="un-lot-dossier"),
    pytest.param(plan_en_conflit_d_etat, id="un-lot-etat"),
    pytest.param(plan_a_deux_lots_en_conflit, id="deux-lots"),
    pytest.param(plan_aux_DEUX_chemins_de_conflit, id="dossier-ET-etat"),
]


def releve_du_pli(banc, p, gestes=(), **kwargs):
    """Ce que l'ecran d'ecrasement montre APRES `gestes`, et ce qu'il en dit.

    Les touches sont jouees **dans** le pilote, sur l'ecran monte : tout ce qui
    compose lit `self.app`, et le mesurer apres coup leve.
    """
    def mesure(ecran):
        for touche in gestes:
            # `traiter` PUIS `rafraichir`, comme `on_key` : c'est le dessin
            # qui pose la ligne d'eau de lecture, et un banc qui sauterait le
            # dessin mesurerait un ecran que personne n'a vu.
            ecran.traiter(touche)
            ecran.rafraichir()
        pli = ecran.pli()
        return {
            "affiche": list(ecran.lignes_du_cartouche()),
            "entier": list(ecran.lignes_du_panneau()),
            "lignes_defilantes": list(ecran.lignes_defilantes()),
            "defilantes": [ligne.texte for ligne in ecran.lignes_defilantes()],
            "noms": [ligne.nom for ligne in ecran.lignes_defilantes()],
            "consequences": list(ecran.phrases_de_consequence(
                getattr(ecran.app, "ascii_seul", False))),
            "premier": pli.premier,
            "dernier": pli.dernier,
            "lues": pli.lues,
            "total": pli.total,
            "replie": pli.replie,
            "raccourcis": ecran.raccourcis,
            "curseur": ecran.choix.curseur,
            "place": ecran.place_defilante(),
        }

    return monter(banc, p, mesure=mesure, **kwargs)[2]


def descendre_jusqu_en_bas(banc, p, **kwargs):
    """Tous les releves, du haut du cartouche jusqu'a la butee.

    Le nombre de gestes est **derive** de la course a faire, borne par le
    cardinal des lignes defilantes : une boucle qui compterait sur un nombre
    ecrit ici cesserait de descendre jusqu'en bas au premier etat plus charge.
    """
    premier = releve_du_pli(banc, p, **kwargs)
    releves = [premier]
    for pas in range(1, len(premier["defilantes"]) + 1):
        releves.append(releve_du_pli(banc, p, gestes=["ctrl+down"] * pas,
                                     **kwargs))
        if releves[-1]["dernier"] == len(premier["defilantes"]) - 1:
            break
    return releves


# -- ce qui ne defile JAMAIS -------------------------------------------------

@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_TROIS_phrases_de_consequence_OUVRENT_le_cartouche(
        tmp_path, banc, fabrique, ascii_seul):
    """`EPIC11-ARB-89` : l'avertissement precede l'ecriture destructive.

    Elles ne sont pas seulement PRESENTES : elles sont les **premieres**
    lignes affichees, et dans l'ordre. Une mesure d'appartenance resterait
    verte si elles retombaient en queue de cartouche -- c'est-a-dire a
    l'endroit exact ou le pli les cacherait en premier, qui est le defaut que
    cet arbitrage corrige.
    """
    releve = releve_du_pli(banc, fabrique(tmp_path), ascii_seul=ascii_seul)
    assert len(releve["consequences"]) == 3, releve["consequences"]
    assert releve["affiche"][:3] == releve["consequences"]
    assert releve["affiche"][3] == "", releve["affiche"][:5]


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_les_phrases_de_consequence_NE_PASSENT_JAMAIS_sous_le_pli(
        tmp_path, banc, fabrique):
    """Le mutant nomme : une phrase de consequence qui repasserait SOUS le pli.

    On descend jusqu'a la butee et on redemande a chaque pas : les trois
    phrases ouvrent encore le cartouche. Un pli qui les prendrait dans sa
    fenetre les ferait disparaitre au premier defilement, c'est-a-dire au
    moment ou l'operateur cherche justement autre chose.
    """
    p = fabrique(tmp_path)
    releves = descendre_jusqu_en_bas(banc, p)
    assert len(releves) >= 2, "le cartouche doit vraiment defiler"
    for rang, releve in enumerate(releves):
        assert releve["affiche"][:3] == releve["consequences"], (
            rang, releve["affiche"][:4])


# -- ce que la ligne de pli DIT ----------------------------------------------

@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_de_pli_NOMME_ce_qu_elle_cache(tmp_path, banc, fabrique,
                                                ascii_seul):
    """Le mutant nomme : une ligne de pli qui annoncerait un compte SANS NOMS.

    C'est la seule chose qui empeche de valider sans savoir ce qu'on n'a pas
    lu, et c'est ce qui a fait accepter le defilement sur un point de jugement
    destructif. Les noms attendus sont **derives du panneau** -- le libelle qui
    a produit chaque ligne cachee --, jamais des litteraux recopies ici.
    """
    releve = releve_du_pli(banc, fabrique(tmp_path), ascii_seul=ascii_seul)
    pli = releve["affiche"][-1]
    caches = [nom for nom in releve["noms"][releve["dernier"] + 1:]
              if nom is not None]
    assert caches, "l'etat mesure doit vraiment cacher des lignes nommees"
    premier_cache = caches[0]
    if ascii_seul:
        premier_cache = jetons.replier_ascii(premier_cache)
    assert premier_cache in pli, (premier_cache, pli)
    assert execution.PLI_VERS_LE_BAS in jetons.replier_ascii(pli) \
        if ascii_seul else execution.PLI_VERS_LE_BAS in pli


def test_la_ligne_de_pli_nomme_le_BLOC_DES_NOMS_par_son_CARDINAL(tmp_path,
                                                                 banc):
    """`3 noms appariés`, et non trois entrees separees.

    C'est l'etat de la maquette `T4-2` -- un lot en conflit de dossier --, et
    c'est ce qu'elle montre. Le groupe est ce qui rend la ligne de pli
    lisible : trois lignes de noms enumerees une par une rempliraient la ligne
    a elles seules et chasseraient « bornes » et « destination », qui sont ce
    que l'operateur cherche.

    Le cardinal est celui des lots du plan, **lu du plan** : un chiffre ecrit
    ici mesurerait la fabrique et non le code.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    releve = releve_du_pli(banc, p)
    attendu = atelier.EcranExtractionEcrasement.NOMS_APPARIES.format(
        compte=len(p.lots))
    assert attendu in releve["affiche"][-1], (attendu, releve["affiche"][-1])


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_l_ENUMERATION_du_pli_rend_compte_de_TOUS_les_groupes_caches(
        tmp_path, banc, fabrique):
    """Le volet qui vaut pour les etats ou l'enumeration NE TIENT PAS.

    Sur les deux cartouches les plus charges, la ligne de pli n'a pas la place
    d'ecrire les quatre groupes caches : elle en nomme deux et **compte** les
    autres (`+2 autres`). Ce qui doit tenir est que rien ne disparaisse -- noms
    ecrits plus noms comptes egale groupes caches --, et c'est ce mode-la que
    le mutant « un compte, mais plus les noms » attaque : il rendrait un compte
    juste et zero nom, ce que ce test refuse en exigeant au moins le premier.
    """
    p = fabrique(tmp_path)
    releve = releve_du_pli(banc, p)
    pli = releve["affiche"][-1]
    caches = releve["lignes_defilantes"][releve["dernier"] + 1:]
    groupes = execution._groupes_de_noms(caches)
    assert groupes, "l'etat mesure doit cacher des lignes nommees"
    ecrits = [groupe for groupe in groupes if groupe in pli]
    assert ecrits and ecrits[0] == groupes[0], (groupes, pli)
    manquants = len(groupes) - len(ecrits)
    if manquants:
        assert execution.MOTIF_DU_RESTE.format(compte=manquants) in pli, (
            manquants, groupes, pli)


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_le_COMPTE_de_la_ligne_de_pli_ne_ment_pas(tmp_path, banc, fabrique):
    """`{lues} sur {total}` : les deux se verifient sur le cartouche entier.

    `total` est le cardinal de `lignes_du_panneau`, `lues` le nombre de lignes
    du cartouche deja atteintes -- les fixes, plus la fenetre. Le mutant nomme
    « la fenetre decalee d'un » deplace exactement l'un de ces deux nombres.
    """
    p = fabrique(tmp_path)
    releve = releve_du_pli(banc, p)
    assert releve["total"] == len(releve["entier"])
    assert releve["lues"] == len(releve["consequences"]) + 1 \
        + releve["dernier"] + 1
    # La ligne de pli n'est PAS du contenu : elle s'ajoute a ce qui est lu.
    assert len(releve["affiche"]) == releve["lues"] + 1
    assert str(releve["lues"]) in releve["affiche"][-1]
    assert str(releve["total"]) in releve["affiche"][-1]


def test_la_ligne_de_pli_du_HAUT_apparait_et_nomme_ce_qui_a_DEFILE(
        tmp_path, banc):
    """Le pli du bas dit ce qui reste ; celui du haut dit ce qui est passe.

    Sans lui, un cartouche defile n'aurait plus aucune marque de ce qu'il a
    au-dessus : le detail chiffre disparaitrait en silence, ce qui est le
    contraire de ce que ce mecanisme promet.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    releve = releve_du_pli(banc, p, gestes=["ctrl+down"])
    assert releve["premier"] > 0, releve
    haut = releve["affiche"][len(releve["consequences"]) + 1]
    assert execution.PLI_VERS_LE_HAUT in haut, haut
    passes = [nom for nom in releve["noms"][:releve["premier"]]
              if nom is not None]
    assert passes and passes[0] in haut, (passes, haut)


# -- ce que la fenetre MONTRE ------------------------------------------------

@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_le_defilement_finit_par_montrer_la_DERNIERE_ligne(tmp_path, banc,
                                                           fabrique):
    """Le mutant nomme : la derniere ligne de la fenetre non rendue.

    Un balayage tronque est le mode de panne qui cache **la derniere** ligne --
    c'est-a-dire exactement ce que le pli est cense rendre lisible. La cible est
    donc en QUEUE, comme la regle des fabriques l'exige (point 4).
    """
    p = fabrique(tmp_path)
    releves = descendre_jusqu_en_bas(banc, p)
    dernier = releves[-1]
    assert dernier["dernier"] == len(dernier["defilantes"]) - 1
    assert dernier["defilantes"][-1] in dernier["affiche"]
    assert dernier["entier"][-1] in dernier["affiche"]
    assert dernier["lues"] == dernier["total"]


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_le_defilement_ne_SAUTE_aucune_ligne_du_cartouche(tmp_path, banc,
                                                          fabrique):
    """Le volet exhaustif : tout ce que le cartouche contient a ete montre.

    Il ferme les deux mutants de bornes d'un coup -- `+1` cache une ligne au
    passage, `-1` en montre une deux fois sans avancer --, la ou une mesure
    posee sur un seul releve ne verrait ni l'un ni l'autre.

    La comparaison porte sur les lignes DEFILANTES et non sur le rendu : les
    lignes de pli sont du chrome, elles ne font pas partie du contenu.
    """
    p = fabrique(tmp_path)
    releves = descendre_jusqu_en_bas(banc, p)
    vues = set()
    for releve in releves:
        vues.update(range(releve["premier"], releve["dernier"] + 1))
    assert vues == set(range(len(releves[0]["defilantes"]))), sorted(vues)


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_la_fenetre_AVANCE_a_chaque_geste_et_S_ARRETE_en_butee(
        tmp_path, banc, fabrique):
    """Elle ne piétine pas, et elle ne deborde pas.

    Un pas nul ferait un cartouche que l'on ne peut pas lire jusqu'au bout ; un
    pas non borne rendrait une fenetre vide au-dela de la derniere ligne.
    """
    p = fabrique(tmp_path)
    releves = descendre_jusqu_en_bas(banc, p)
    premiers = [releve["premier"] for releve in releves]
    assert premiers == sorted(premiers), premiers
    assert premiers[0] == 0 and premiers[-1] > 0, premiers
    # Une fois en butee, un geste de plus ne bouge plus rien.
    gestes = ["ctrl+down"] * (len(releves) + 2)
    en_butee = releve_du_pli(banc, p, gestes=gestes)
    assert en_butee["dernier"] == len(en_butee["defilantes"]) - 1
    assert en_butee["premier"] == releves[-1]["premier"]


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_le_pli_REMONTE_et_revient_au_HAUT_du_cartouche(tmp_path, banc,
                                                        fabrique):
    """`Ctrl+↑` rend ce que `Ctrl+↓` a pris. Sans lui, le pli est une impasse.

    **La reciproque n'est PAS un geste pour un geste**, et le banc le dit
    plutot que de le taire : la fenetre montre une ligne de plus tant qu'aucun
    pli n'occupe son haut, donc une page vers le bas et une page vers le haut
    ne couvrent pas la meme distance. Ce qui doit tenir est que la remontee
    aboutisse -- sur le haut exact du cartouche -- et qu'elle ne saute rien en
    chemin, ce que le balayage ci-dessous mesure.
    """
    p = fabrique(tmp_path)
    depart = releve_du_pli(banc, p)
    descendu = releve_du_pli(banc, p, gestes=["ctrl+down"])
    assert descendu["premier"] > depart["premier"]
    # La ligne d'eau ne redescend PAS : ce qui a ete affiche a ete lu.
    remonte = releve_du_pli(banc, p, gestes=["ctrl+down", "ctrl+up"])
    assert remonte["premier"] < descendu["premier"]
    assert remonte["lues"] == descendu["lues"] > depart["lues"]
    # Et la remontee aboutit : le haut du cartouche est de nouveau atteint.
    course = ["ctrl+down"] * len(depart["defilantes"]) \
        + ["ctrl+up"] * len(depart["defilantes"])
    au_sommet = releve_du_pli(banc, p, gestes=course)
    assert au_sommet["premier"] == 0
    assert au_sommet["affiche"][:len(depart["affiche"])] \
        == depart["affiche"][:len(depart["affiche"])] or \
        au_sommet["defilantes"][0] in au_sommet["affiche"]


@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
def test_la_REMONTEE_ne_saute_aucune_ligne_non_plus(tmp_path, banc, fabrique):
    """Le volet symetrique du balayage descendant.

    Un pas de remontee trop grand est le meme defaut que celui qui faisait
    sauter la ligne 6 en descendant, et il ne se voit pas davantage sur un
    releve unique.
    """
    p = fabrique(tmp_path)
    total = len(releve_du_pli(banc, p)["defilantes"])
    descente = ["ctrl+down"] * total
    vues = set()
    for pas in range(total + 1):
        releve = releve_du_pli(banc, p, gestes=descente + ["ctrl+up"] * pas)
        vues.update(range(releve["premier"], releve["dernier"] + 1))
        if releve["premier"] == 0:
            break
    assert vues == set(range(total)), sorted(vues)


# -- ce que le pli NE VOLE PAS aux issues ------------------------------------

def test_la_touche_du_pli_ne_DEPLACE_PAS_le_curseur_des_issues(tmp_path, banc):
    """Le mutant nomme : `Ctrl+↓` cable sur le meme geste que `↓`.

    Deux effets dont l'un engage une ecriture destructive ne partagent pas une
    touche : l'operateur qui croit lire la suite deplacerait son curseur sur
    `Écraser et réextraire`.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    avant = releve_du_pli(banc, p)
    apres = releve_du_pli(banc, p, gestes=["ctrl+down", "ctrl+down"])
    assert apres["curseur"] == avant["curseur"]
    assert apres["premier"] > avant["premier"]


def test_la_FLECHE_NUE_ne_fait_PAS_defiler_le_cartouche(tmp_path, banc):
    """Le volet symetrique du precedent, et il est le plus important des deux.

    Un `↓` qui ferait aussi defiler rendrait la mesure ci-dessus verte tout en
    laissant les deux gestes confondus.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    avant = releve_du_pli(banc, p)
    apres = releve_du_pli(banc, p, gestes=["down", "down"])
    assert apres["premier"] == avant["premier"]
    assert apres["affiche"] == avant["affiche"]
    assert apres["curseur"] != avant["curseur"]


def test_la_touche_du_pli_est_CONSOMMEE_meme_en_butee(tmp_path, banc):
    """Une touche rendue a l'application y rencontrerait un autre raccourci."""
    p = plan_en_conflit_de_dossier(tmp_path)

    def mesure(ecran):
        return [ecran.traiter(touche)
                for touche in ("ctrl+down",) * 20 + ("ctrl+up",) * 20]

    assert all(monter(banc, p, mesure=mesure)[2])


# -- le volet symetrique : un cartouche qui TIENT ----------------------------

def test_un_cartouche_qui_TIENT_ne_porte_NI_PLI_NI_TOUCHE_DE_PLI(tmp_path,
                                                                 banc):
    """La hauteur est **derivee de la fenetre**, pas ecrite quelque part.

    Sur une fenetre plus haute, le meme cartouche tient entier : aucune ligne
    de pli, et la ligne de raccourcis redevient celle de la confirmation --
    annoncer une touche qui ne fait rien est le defaut que `coque.py` documente.

    C'est aussi le seul volet qui rougirait si la hauteur du cartouche etait
    posee en dur : un `10` ecrit dans le code replierait ce cartouche-la aussi.
    """
    p = plan_en_conflit_de_dossier(tmp_path)
    au_plancher = releve_du_pli(banc, p)
    au_large = releve_du_pli(banc, p, taille=(jetons.LARGEUR_PLANCHER,
                                              2 * jetons.HAUTEUR_PLANCHER))
    assert au_plancher["replie"] and not au_large["replie"]
    assert au_large["affiche"] == au_large["entier"]
    assert au_large["raccourcis"] == atelier.RACCOURCIS_EXTRACTION_CONFIRMATION
    assert au_plancher["raccourcis"] == atelier.RACCOURCIS_EXTRACTION_ECRASEMENT


# -- le mecanisme a nu, sans monter d'application ----------------------------

def test_le_pli_rend_une_ENUMERATION_meme_quand_elle_NE_TIENT_PAS():
    """Ce qui ne tient pas se COMPTE, il ne disparait pas.

    Une enumeration coupee par `jetons.ajuster` perdrait ses derniers noms en
    silence -- et la promesse de la ligne de pli avec eux. La cible est en
    QUEUE : c'est elle que la troncature emporterait.
    """
    caches = [execution.LigneDefilante(f"ligne {rang}", f"nom-tres-long-{rang}")
              for rang in range(9)]
    ligne = execution.ligne_de_pli(execution.PLI_VERS_LE_BAS, caches, 4, 13,
                                   jetons.largeur_de_cartouche())
    assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(), ligne
    assert caches[0].nom in ligne
    reste = execution.MOTIF_DU_RESTE.format(
        compte=len(caches) - ligne.count("nom-tres-long-"))
    assert reste in ligne, (reste, ligne)


def test_le_pli_ne_GROUPE_que_des_noms_CONSECUTIFS():
    """Deux blocs de meme nom separes par autre chose sont DEUX blocs.

    Le groupement est ce qui rend `3 noms appariés` ; l'etendre a des lignes
    non consecutives ferait dire au pli que trois lignes se suivent alors
    qu'elles encadrent autre chose.
    """
    groupe = "{compte} noms"
    caches = [execution.LigneDefilante("a", "nom", groupe),
              execution.LigneDefilante("b", "autre"),
              execution.LigneDefilante("c", "nom", groupe),
              execution.LigneDefilante("d", "nom", groupe)]
    ligne = execution.ligne_de_pli(execution.PLI_VERS_LE_BAS, caches, 1, 5,
                                   jetons.largeur_de_cartouche())
    assert "nom, autre, 2 noms" in ligne, ligne


def test_le_pli_d_un_contenu_qui_TIENT_ne_rend_AUCUNE_ligne_de_pli():
    """Le mecanisme a nu : rien a cacher, rien a annoncer."""
    defilantes = [execution.LigneDefilante(f"l{rang}", f"n{rang}")
                  for rang in range(3)]
    replie = execution.plier_le_cartouche(["fixe"], defilantes, hauteur=10)
    assert replie.lignes == ["fixe", "l0", "l1", "l2"]
    assert not replie.replie and replie.lues == replie.total == 4


def test_le_pli_ne_perd_AUCUNE_ligne_meme_a_hauteur_UN():
    """La borne basse : une hauteur qui ne laisse la place a rien.

    Elle est atteignable -- une fenetre au plancher avec un ecran plus charge
    --, et elle ne doit ni lever ni rendre une fenetre incoherente.
    """
    defilantes = [execution.LigneDefilante(f"l{rang}", f"n{rang}")
                  for rang in range(5)]
    replie = execution.plier_le_cartouche(["fixe"], defilantes, hauteur=1)
    assert replie.total == 6
    assert replie.lignes[0] == "fixe"
    assert replie.premier == 0 and replie.dernier <= len(defilantes) - 1


def test_une_tranche_SANS_AUCUN_nom_s_annonce_QUAND_MEME():
    """La branche `NOMS_SANS_NOM` : ce qui est cache n'a pas toujours de nom.

    Une tranche de respirations ne rend aucun groupe. Sans cette branche la
    ligne de pli sortirait sur `— la suite : ` en l'air, c'est-a-dire une
    promesse ouverte et jamais tenue. Le geste est le meme que partout
    ailleurs ici : plutot que taire, dire ce qu'il y a.
    """
    caches = [execution.LigneDefilante(""), execution.LigneDefilante("  ")]
    ligne = execution.ligne_de_pli(execution.PLI_VERS_LE_BAS, caches, 4, 9,
                                   jetons.largeur_de_cartouche())
    assert ligne.endswith(execution.NOMS_SANS_NOM), ligne
    repliee = execution.ligne_de_pli(execution.PLI_VERS_LE_BAS, caches, 4, 9,
                                     jetons.largeur_de_cartouche(),
                                     ascii_seul=True)
    assert repliee.endswith(jetons.replier_ascii(execution.NOMS_SANS_NOM))


# -- l'appariement du NOM et de SA ligne, mesure hors de l'appariement -------
#
# **Le seul survivant de la campagne de mutation du lot, et il a survecu pour
# une raison de methode.** Le mutant `M10` decale les libelles d'un cran dans
# `EcranExtractionEcrasement.lignes_defilantes` -- chaque ligne recoit le nom
# de sa VOISINE --, et les onze mesures du pli restaient vertes : toutes
# derivent le nom attendu de `lignes_defilantes()` elle-meme, c'est-a-dire de
# la surface que le mutant deplace. Une mesure qui lit son attendu dans ce
# qu'elle mesure est tautologique, et c'est exactement le defaut que la
# politique du depot nomme sur la 5.9.
#
# La sortie n'est pas une mesure de plus du meme cote : c'est un attendu pris
# AILLEURS. Une ligne chiffree rend son libelle A GAUCHE (`LigneChiffree.rendu`)
# -- le TEXTE porte donc lui-meme, independamment, de quoi dire quel nom lui
# revient.

@pytest.mark.parametrize("fabrique", ETATS_DE_CONFLIT)
@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_NOM_d_une_ligne_defilante_est_celui_de_SA_PROPRE_ligne(
        tmp_path, banc, fabrique, ascii_seul):
    """Chaque nom se relit dans le TEXTE de sa ligne, pas dans son voisin.

    Trois familles, et chacune ferme un cran du decalage :

    * une ligne chiffree ouvre sur son libelle, donc son nom en est le debut ;
    * une respiration ne nomme RIEN -- un decalage lui donnerait le nom du
      bloc suivant, et la ligne de pli annoncerait un contenu la ou il n'y a
      qu'un blanc ;
    * un nom apparie porte la fleche de renommage et **jamais** un chiffre
      cale a droite.

    Les deux BORDS sont exiges nommes explicitement : un decalage d'un cran
    vide toujours l'un des deux, et une boucle qui se contenterait de la
    conjonction resterait verte si la collection etait vide.
    """
    releve = releve_du_pli(banc, fabrique(tmp_path), ascii_seul=ascii_seul)
    lignes = releve["lignes_defilantes"]
    for rang, ligne in enumerate(lignes):
        contexte = (rang, ligne.nom, ligne.texte)
        if not ligne.texte.strip():
            assert ligne.nom is None, contexte
            continue
        assert ligne.nom is not None, contexte
        if ligne.nom == atelier.EcranExtractionEcrasement.NOM_APPARIE:
            assert "->" in ligne.texte, contexte
            continue
        # Les DEUX cotes sont replies : le texte d'un ecran `--ascii` est deja
        # sans accent quand le nom, lui, porte les siens jusqu'au rendu de la
        # ligne de pli. Replier des deux cotes compare ce que l'operateur lit ;
        # ca ne compare toujours PAS l'appariement avec lui-meme.
        debut = jetons.replier_ascii(ligne.texte.strip()).lower()
        assert debut.startswith(jetons.replier_ascii(ligne.nom).lower()), (
            contexte)
    assert lignes[0].nom is not None, lignes[0]
    assert lignes[-1].nom is not None, lignes[-1]


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-1j`, `E2-3` et `T4-2`
# et n'ouvrait aucun dessin : le titre du panneau de confirmation etait
# recopie a la main, dans TROIS montages.

#: Le titre que `E2-3` dessine sur le cadre de son panneau (l. 5). Confronte
#: a sa source ci-dessous.
TITRE_DESSINE_DU_PANNEAU = "À écrire"

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


def test_le_TITRE_du_panneau_est_celui_que_E2_3_dessine():
    """Le titre, a sa source, et ce qu'il coiffe -- pas le mot tout seul.

    `À écrire` est court : l'y trouver ne prouve pas grand-chose. Ce qui le
    prouve, c'est qu'il coiffe le recapitulatif que le panneau montre --
    « Lots créés », « Frames écrites » -- et que ce recapitulatif est dans le
    meme dessin. Un titre juste sur un panneau vide serait une confrontation
    verte et vide.
    """
    dessin = dessin_de_la_maquette("E2-3-extraction-confirmation.txt")
    assert TITRE_DESSINE_DU_PANNEAU in dessin
    assert "Lots créés" in dessin
    assert "Frames écrites" in dessin


def test_le_titre_du_panneau_n_est_PAS_celui_de_l_ecran_d_execution():
    """Volet symetrique : `E2-4`, l'ecran d'a cote, porte un autre titre.

    Les deux ecrans se suivent dans le meme parcours. Si le meme titre les
    coiffait tous deux, mesurer l'appartenance ne distinguerait plus lequel
    des deux le banc monte -- et un montage permute resterait vert.
    """
    confirmation = dessin_de_la_maquette("E2-3-extraction-confirmation.txt")
    execution = dessin_de_la_maquette("E2-4-extraction-execution.txt")
    assert TITRE_DESSINE_DU_PANNEAU not in execution
    assert "Extraction en cours" in execution
    assert "Extraction en cours" not in confirmation


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    dessin = dessin_de_la_maquette("E2-3-extraction-confirmation.txt")
    assert "À écraser" not in dessin
    assert "Déjà écrit" not in dessin
