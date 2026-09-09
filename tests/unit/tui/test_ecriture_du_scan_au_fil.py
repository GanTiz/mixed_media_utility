# -*- coding: utf-8 -*-
"""`E3-7` au fil de travail -- le troisieme et dernier lanceur gele du depot.

**Ce que ce banc mesure, et pourquoi il existe** (2026-09-06). Le 2026-09-06,
Egan a constate sur le terrain que la barre de progression « saute de 0 a 100 »
et que « le glyphe d'attente est immobile ». Trois chemins portaient le meme
defaut : l'extraction, l'encodage, et l'ecriture du Scan. Les deux premiers
sont partis au fil dans la journee ; le troisieme -- celui-ci -- etait la
derniere ligne du registre d'exceptions de
`tests/unit/tui/test_frontiere_du_dessin_avant_le_coeur.py`.

**Le defaut n'est PAS un ecran absent, c'est un ecran fige.** Un
`call_after_refresh` seul DIFFERE d'une image : il fait apparaitre `E3-7` une
fois, puis rend la boucle a un appel synchrone qui la garde jusqu'a la derniere
frame. L'operateur lit `0 %  0/6300` immobile, ce qui est indiscernable d'un
coeur en panne -- la forme la plus couteuse du defaut.

**Il faut donc DEUX gestes, et ce banc fait varier chacun des deux** : le fil,
qui garde la boucle vivante pendant la passe, et le rendez-vous de dessin, qui
le fait partir apres le montage. Un banc qui ne jouerait que l'ordre nominal
mesurerait la moitie du produit et l'annoncerait vert.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mixed_media_utility.io import project_layout
from mixed_media_utility.tui import atelier_scan_ecriture as atelier
from mixed_media_utility.tui import execution

# ---------------------------------------------------------------------------
# Les fabriques. Trois lots DISTINGUABLES, jamais un seul et jamais uniformes.
# ---------------------------------------------------------------------------

#: Trois lots aux cardinaux **differents**. Trois comptes egaux laisseraient
#: passer une boucle qui ne lirait que le premier lot -- c'est le mutant `M25`
#: de la story 5.7, paye trois fois dans ce depot.
LOTS = (("lot_a_12p5", 4), ("lot_b_25", 6), ("lot_c_50", 5))


def plan_de_trois_lots(tmp_path: Path) -> atelier.PlanDEcriture:
    """Le plan du banc : trois lots, trois cardinaux, trois identifiants."""
    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    lots = tuple(
        atelier.LotAEcrire(
            document=(project_layout.scan_lot_dir(projet, nom)
                      / "detections" / "d.json"),
            lot_id=nom, frames=frames)
        for nom, frames in LOTS)
    return atelier.PlanDEcriture(dossier_projet=projet, lots=lots)


class EcranDeBanc:
    """Ce que :func:`lancer_l_ecriture` lit de son ecran, et rien de plus.

    Une **vraie** :class:`~mixed_media_utility.tui.execution.SurfaceExecution`,
    pas un double a attributs libres : c'est elle qui recoit les jalons et le
    journal, et un double laisserait passer un canal debranche.
    """

    def __init__(self) -> None:
        self.surface = execution.SurfaceExecution(unite=atelier.UNITE)
        self.issue_retenue = None


class AppDeBanc:
    """La coque, reduite a ce que le lanceur touche -- et qui **note l'ordre**.

    `rendez_vous=False` retire `call_after_refresh` : c'est le repli que
    `_lancer_apres_le_dessin` prend pour les appelants qui ne montent aucune
    application, et il sert ici a faire **varier le drapeau** dont la regle des
    gardes parle -- un banc qui ne jouerait que le regime nominal ne verrait
    jamais que l'ordre est ce qui compte.
    """

    def __init__(self, *, rendez_vous: bool = True) -> None:
        self.ordre: list[str] = []
        self.tache_en_cours = False
        self.interruption_demandee = False
        self.empiles: list[object] = []
        self.aux_ateliers = 0
        self.fil = None
        if not rendez_vous:
            self.call_after_refresh = None

    # -- ce que la boucle offre ---------------------------------------------

    def call_after_refresh(self, action) -> None:
        # Le drapeau est lu **au moment du rendez-vous**, pas apres : c'est la
        # seule facon de mesurer qu'il a ete pose AVANT et non pendant.
        self.ordre.append(f"dessin(tache={self.tache_en_cours})")
        action()

    def run_worker(self, fonction, *, thread=False, name="", description=""):
        self.ordre.append(f"fil(nom={name},thread={thread})")
        self.fil = fonction
        return f"ouvrier:{name}"

    def call_from_thread(self, fonction, *args, **kwargs):
        self.ordre.append("boucle")
        return fonction(*args, **kwargs)

    def executer_en_processus(self, fonction, *args, **kwargs):
        return fonction(*args, **kwargs)

    # -- ce que la conclusion touche ----------------------------------------

    def oublier_la_tache(self) -> None:
        self.ordre.append("oubli")
        self.tache_en_cours = False

    def descendre(self, ecran) -> None:
        self.ordre.append(f"descendre({type(ecran).__name__})")
        self.empiles.append(ecran)

    def revenir_aux_ateliers(self) -> None:
        self.ordre.append("ateliers")
        self.aux_ateliers += 1


def lancer(app, plan, *, ecrire, rapports=None):
    """Lancer la passe et rendre l'ecran, sans jouer le fil."""
    ecran = EcranDeBanc()
    rendu = atelier.lancer_l_ecriture(
        app, ecran, plan, logger=None,
        sur_rapport=(rapports.append if rapports is not None
                     else (lambda rapport: None)),
        ecrire=ecrire)
    return ecran, rendu


def ecriture_qui_reussit(dossier_projet, document, **kwargs):
    """Un double du coeur qui rend un objet **sans** `output`.

    `_lot_ecrit` lit alors le `lot_id` du plan et un cardinal a zero -- ce qui
    suffit ici : ce banc mesure le LANCEMENT, pas la projection du rapport,
    dont `test_atelier_scan_ecriture.py` porte deja la mesure.
    """
    return object()


# ---------------------------------------------------------------------------
# Volet 1 -- les DEUX gestes, et l'ordre entre eux
# ---------------------------------------------------------------------------


def test_D4_le_fil_part_APRES_le_dessin(tmp_path):
    """`dessin` puis `fil`, jamais l'inverse, et le fil est un VRAI fil.

    L'ordre n'est pas cosmetique : `EcranEcritureDuScan` est un
    `EcranExecution`, dont l'`on_mount` abonne l'ecran aux jalons **et rallume**
    `tache_en_cours`. `Mount` etant distribue par la boucle, un fil parti dans
    la foulee de `descendre` peut eteindre le drapeau AVANT ce montage, qui le
    rallume ensuite : drapeau final a vrai sur une passe morte.
    """
    app = AppDeBanc()
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecriture_qui_reussit)
    assert app.ordre == ["dessin(tache=True)",
                         "fil(nom=scan-ecrire,thread=True)"], app.ordre


def test_D4_le_drapeau_de_tache_est_pose_AVANT_le_fil(tmp_path):
    """Entre le `run_worker` et la premiere ligne du fil, la boucle tourne.

    Un `Echap` qui y tomberait depilerait `E3-7` sous la passe. Le drapeau se
    lit donc **au rendez-vous**, qui precede le `run_worker`.
    """
    app = AppDeBanc()
    assert app.tache_en_cours is False
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecriture_qui_reussit)
    assert "dessin(tache=True)" in app.ordre
    assert app.tache_en_cours is True


def test_D4_le_lanceur_ne_rend_PAS_le_rapport(tmp_path):
    """Il n'existe pas encore quand la fonction rend la main.

    C'est exactement ce que le passage au fil change, et le dire par un banc
    empeche un appelant de recabler un `rapport = lancer_l_ecriture(...)` qui
    vaudrait `None` en silence.
    """
    app = AppDeBanc()
    _, rendu = lancer(app, plan_de_trois_lots(tmp_path),
                      ecrire=ecriture_qui_reussit)
    assert rendu is None


def test_D4_SANS_rendez_vous_le_fil_part_quand_meme(tmp_path):
    """Le repli de `_lancer_apres_le_dessin`, joue dans l'autre sens.

    Une coque sans `call_after_refresh` -- un banc qui ne monte aucune
    application -- ne doit pas perdre le fil au passage : le rendez-vous est un
    ordre, pas une condition d'existence. C'est la variation du drapeau que la
    regle des gardes exige : le regime nominal seul mesurerait la moitie.
    """
    app = AppDeBanc(rendez_vous=False)
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecriture_qui_reussit)
    assert app.ordre == ["fil(nom=scan-ecrire,thread=True)"], app.ordre
    assert app.tache_en_cours is True


# ---------------------------------------------------------------------------
# Volet 2 -- ce que le FIL a le droit de faire, et ce qu'il n'a pas le droit
# ---------------------------------------------------------------------------


def test_D4_la_conclusion_repasse_par_la_BOUCLE(tmp_path):
    """Le fil ne touche jamais l'arbre de widgets : un `call_from_thread`.

    Et **un seul** : entre deux passages par la boucle, l'interface serait
    rendue a l'operateur avec `tache_en_cours` deja eteint et rien de monte.
    """
    app = AppDeBanc()
    rapports: list = []
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecriture_qui_reussit,
           rapports=rapports)
    app.fil()
    assert app.ordre.count("boucle") == 1
    assert app.ordre.index("boucle") < app.ordre.index("oubli")
    assert app.tache_en_cours is False
    assert len(rapports) == 1
    assert [lot.lot_id for lot in rapports[0].ecrits] == [
        nom for nom, _ in LOTS]


@pytest.mark.parametrize("rang", (0, 1, 2), ids=("tete", "milieu", "queue"))
def test_D4_un_lot_REFUSE_ne_fige_pas_la_passe(tmp_path, rang):
    """Le refus est collecte, la passe continue, et la conclusion arrive.

    La cible est jouee **a chaque bord** et au milieu : au milieu elle demasque
    un `find` fautif, en queue elle demasque un balayage tronque, en tete un
    balayage qui saute son premier element. Trois modes de panne distincts.
    """
    from mixed_media_utility import scan_write

    vise = LOTS[rang][0]

    def ecrire(dossier_projet, document, **kwargs):
        if Path(document).parent.parent.name == vise:
            raise scan_write.RefusDuDocumentDeDetection(
                f"refus de {vise}", motif="document_illisible")
        return object()

    app = AppDeBanc()
    rapports: list = []
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecrire,
           rapports=rapports)
    app.fil()
    assert len(rapports) == 1
    assert [lot.lot_id for lot in rapports[0].ecrits] == [
        nom for nom, _ in LOTS if nom != vise]
    assert [refus.lot_id for refus in rapports[0].refus] == [vise]
    assert app.tache_en_cours is False


def test_D4_un_coeur_qui_LEVE_eteint_le_drapeau_par_la_boucle_et_RELAIE(
        tmp_path):
    """Une panne hors table traverse -- mais pas sans eteindre le drapeau.

    `conclure_l_ecriture` n'est pas atteinte dans ce cas : c'est la moitie du
    `finally` d'origine qui reste necessaire. Un drapeau reste a vrai fait de
    `Echap` une interruption longtemps apres la fin de la passe, et l'atelier
    est mort pour la session.
    """
    def ecrire(dossier_projet, document, **kwargs):
        raise ZeroDivisionError("hors table")

    app = AppDeBanc()
    rapports: list = []
    lancer(app, plan_de_trois_lots(tmp_path), ecrire=ecrire,
           rapports=rapports)
    with pytest.raises(ZeroDivisionError):
        app.fil()
    assert app.tache_en_cours is False
    assert app.ordre[-2:] == ["boucle", "oubli"]
    assert rapports == []


# ---------------------------------------------------------------------------
# Volet 3 -- le chemin SYNCHRONE reste, et les deux partagent leur conclusion
# ---------------------------------------------------------------------------


def test_D4_executer_et_conclure_reste_et_rend_le_rapport(tmp_path):
    """Les bancs veulent le rapport tout de suite ; un operateur, jamais.

    La retirer casserait une trentaine de mesures qui n'ont aucune boucle a
    faire vivre. Ce qui ne doit pas exister, c'est **deux** redactions des
    trois issues : elles vivent dans `conclure_l_ecriture`, appelee par les
    deux chemins.
    """
    app = AppDeBanc()
    ecran = EcranDeBanc()
    rapports: list = []
    rapport = atelier.executer_et_conclure(
        app, ecran, plan_de_trois_lots(tmp_path), logger=None,
        sur_rapport=rapports.append, ecrire=ecriture_qui_reussit)
    assert rapport is rapports[0]
    assert [lot.lot_id for lot in rapport.ecrits] == [nom for nom, _ in LOTS]
    # Aucun fil, aucun rendez-vous : ce chemin appelle le coeur sur place.
    assert app.ordre == ["oubli"], app.ordre


# ---------------------------------------------------------------------------
# Volet 4 -- la COURSE de l'`on_mount`, mesuree par la structure
# ---------------------------------------------------------------------------

def _sites_de_fil(source: str) -> dict[str, bool]:
    """Pour chaque `run_worker` de `source` : est-il SOUS un rendez-vous ?

    Mesure **structurelle** et non comportementale, et c'est delibere : la
    course qu'elle attrape ne se reproduit pas a volonte dans un banc -- elle
    depend de l'ordre ou la boucle `textual` distribue `Mount` face a un fil
    qui a deja fini. Ce qui se mesure sans loterie, c'est que le
    `run_worker` soit **lexicalement** sous un `_lancer_apres_le_dessin`.

    Rend `{"<fonction>:<ligne>": <sous rendez-vous>}`, **une entree par SITE**.

    Deux defauts de la premiere redaction, tous deux trouves par la revue du
    2026-09-07 et tous deux invisibles a la relecture :

    * elle rendait `{"<fonction>": ...}` et **ecrasait** : une fonction portant
      deux fils, l'un ordonne et l'autre nu, ne rendait qu'un seul verdict --
      celui du dernier rencontre. Un fil nu y disparaissait donc derriere un
      fil ordonne ecrit apres lui, ce qui est exactement la forme que prend un
      correctif incomplet ;
    * elle prenait un **module** et balayait chaque fonction separement, si
      bien qu'un `run_worker` place dans une fonction imbriquee etait compte
      **deux fois** -- une fois pour l'englobante, une fois pour l'imbriquee.
      Le balayage part desormais des sites eux-memes, et remonte a leur
      fonction par une table de parents : chaque site est vu une fois.

    Elle prend une SOURCE et non un module pour que le volet symetrique
    ci-dessous puisse l'appeler sur un cas fabrique. Une mesure qu'un test ne
    peut pas appeler se fait recopier, et une recopie ne mesure plus rien --
    c'est le finding `C5`, et c'est la faute que ce parametre ferme.
    """
    import ast

    arbre = ast.parse(source)
    parent: dict[int, ast.AST] = {}
    for noeud in ast.walk(arbre):
        for fils in ast.iter_child_nodes(noeud):
            parent[id(fils)] = noeud

    couverts: set[int] = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call)
                and getattr(noeud.func, "id", None)
                == "_lancer_apres_le_dessin"):
            couverts.update(id(fils) for fils in ast.walk(noeud))

    def _nom_de_la_fonction(noeud: ast.AST) -> str:
        courant = parent.get(id(noeud))
        while courant is not None:
            if isinstance(courant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return courant.name
            courant = parent.get(id(courant))
        return "<module>"

    sites: dict[str, bool] = {}
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call)
                and getattr(noeud.func, "attr", None) == "run_worker"):
            cle = f"{_nom_de_la_fonction(noeud)}:{noeud.lineno}"
            sites[cle] = id(noeud) in couverts
    return sites


def _source_du_module(module) -> str:
    import inspect

    return inspect.getsource(module)


def test_D4_tout_run_worker_du_scan_est_SOUS_un_rendez_vous():
    """Aucun fil du parcours Scan ne part avant que son ecran soit monte.

    **La course, mesuree a la sonde par la session voisine le 2026-09-06**
    (`rapport-2026-09-06-a-l-agent-epic-11-gel-des-ecrans-de-progression.md`,
    section 10) : tout ecran qui herite d'`EcranExecution` RALLUME
    `tache_en_cours` dans son `on_mount`. `descendre` empile, mais `Mount` est
    distribue par la boucle -- un fil parti dans la foulee peut donc eteindre
    le drapeau AVANT ce montage, qui le rallume ensuite. Les deux regimes :

        sans rendez-vous : descendre(True) -> fil -> on_mount -> tache=True
        avec rendez-vous : descendre(True) -> on_mount -> fil -> tache=False

    Le premier laisse l'atelier **mort pour la session** sur une passe courte
    -- un refus d'ingestion, une mire deja calibree --, et rien ne le signale.

    `lancer_la_passe_de_calibration` portait cette course jusqu'au 2026-09-06 :
    son `run_worker` suivait `ouvrir_la_calibration_en_cours` sans rendez-vous.
    Le registre de `test_frontiere_du_dessin_avant_le_coeur.py` ne pouvait pas
    la voir -- sa regle stricte acquitte tout ce qui part au fil, quel que soit
    l'ordre.
    """
    from mixed_media_utility.tui import atelier_scan_parcours

    nus = {module.__name__.rsplit(".", 1)[-1] + "::" + cle
           for module in (atelier_scan_parcours, atelier)
           for cle, couvert in _sites_de_fil(
               _source_du_module(module)).items() if not couvert}
    assert not nus, (
        "ces fils partent SANS rendez-vous de dessin -- leur ecran peut voir"
        f" son `on_mount` rallumer un drapeau deja eteint : {sorted(nus)}")


def test_D4_la_mesure_de_structure_sait_voir_un_fil_NU():
    """Le symetrique, sans lequel le banc precedent serait invisible.

    Une mesure qui ne rend jamais `False` acquitte tout, y compris la
    regression qu'elle existe pour attraper -- c'est le test tautologique que
    la campagne de la 5.9 a trouve sur la constante centrale de la calibration.

    **Ce banc RECOPIAIT la mesure** (finding `C5`, revue du 2026-09-07) : il
    reecrivait les onze lignes d'`ast` de `_sites_de_fil` dans une fonction
    locale, et mesurait donc sa propre copie. Muter `_sites_de_fil` le
    laissait vert -- c'est-a-dire que le volet symetrique ne protegeait pas la
    mesure qu'il pretendait proteger. Il l'APPELLE desormais.
    """
    nue = ("def lancer(app):\n"
           "    app.run_worker(passe, thread=True)\n")
    ordonnee = ("def lancer(app):\n"
                "    _lancer_apres_le_dessin(app, lambda: app.run_worker(\n"
                "        passe, thread=True))\n")

    assert list(_sites_de_fil(nue).values()) == [False]
    assert list(_sites_de_fil(ordonnee).values()) == [True]


def test_D4_un_fil_NU_ne_se_cache_pas_derriere_un_fil_ORDONNE():
    """Le defaut d'ECRASEMENT, et il ne se voit que sur DEUX sites.

    `_sites_de_fil` rendait un verdict PAR FONCTION : une fonction portant
    deux fils n'en rendait qu'un, celui du dernier rencontre. Un fil nu ecrit
    AVANT un fil ordonne disparaissait donc entierement de la mesure -- et
    c'est l'ordre le plus probable, puisqu'un correctif s'ajoute apres ce
    qu'il corrige.

    Le banc joue les deux ordres. Un seul aurait laisse vivre la moitie du
    defaut : c'est la regle des bords de la politique des fabriques, appliquee
    a un dictionnaire au lieu d'une liste.
    """
    nu_puis_ordonne = ("def lancer(app):\n"
                       "    app.run_worker(un, thread=True)\n"
                       "    _lancer_apres_le_dessin(app, lambda: "
                       "app.run_worker(deux, thread=True))\n")
    ordonne_puis_nu = ("def lancer(app):\n"
                       "    _lancer_apres_le_dessin(app, lambda: "
                       "app.run_worker(un, thread=True))\n"
                       "    app.run_worker(deux, thread=True)\n")

    for source in (nu_puis_ordonne, ordonne_puis_nu):
        sites = _sites_de_fil(source)
        assert len(sites) == 2, (
            f"les deux sites doivent etre releves, pas un : {sites}")
        assert sorted(sites.values()) == [False, True], sites


def test_D4_un_fil_IMBRIQUE_n_est_compte_qu_UNE_fois():
    """L'autre moitie du meme defaut de balayage.

    La premiere redaction balayait chaque fonction separement et prenait
    `ast.walk`, qui descend dans les fonctions imbriquees : un `run_worker`
    pose dans une fonction interne etait donc vu par elle ET par son
    englobante. Le dictionnaire par nom masquait le doublon ; un relevé par
    site l'aurait rendu visible, d'ou cette garde posee en meme temps.
    """
    imbrique = ("def lancer(app):\n"
                "    def interne():\n"
                "        app.run_worker(passe, thread=True)\n"
                "    _lancer_apres_le_dessin(app, interne)\n")
    sites = _sites_de_fil(imbrique)
    assert len(sites) == 1, sites
    # Et le verdict est bien `False` : le fil n'est pas LEXICALEMENT sous le
    # rendez-vous, il est seulement appele par lui. La mesure est structurelle
    # et le dit -- elle ne suit pas les appels.
    assert list(sites) == ["interne:3"]
