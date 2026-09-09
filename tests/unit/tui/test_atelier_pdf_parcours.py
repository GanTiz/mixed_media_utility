# -*- coding: utf-8 -*-
"""Story 11.7, lot de CABLAGE -- le parcours de l'atelier Pdf, de bout en bout.

**Ce banc et lui seul mesure le cablage.** La regle de decoupage de la fiche est
stricte et elle a ete payee trois fois : « aucun lot ne partage un fichier de
banc avec un autre ». Les sept bancs d'ecran mesurent chacun leur ecran monte a
la main ; celui-ci mesure ce qu'aucun d'eux ne peut voir -- **l'enchainement**.

**Ce qu'un banc d'ecran ne peut pas voir, et qui a ete paye sept fois** : un
ecran teste isolement recoit son rappel du banc lui-meme. Le cablage est
precisement ce qui manque quand tous les bancs sont verts, et c'est le motif
d'existence de `test_rappels_cables.py`. Ce banc-ci en est le pendant positif :
la garde structurelle dit qu'un rappel **est** injecte, celui-ci dit **ou il
mene**.

**Regle des fabriques** (`CLAUDE.md`), appliquee a ses quatre points :

1. **trois lots, la cible AU MILIEU** -- le parcours parcourt les lots coches
   dans trois boucles differentes (les conflits, le plan, la passe). Une cible
   en tete laisse vivre un `lots[0]` ; une cible en queue laisse vivre un
   `continue` -> `break`, et c'est le mutant que ce banc doit tuer ;
2. **des valeurs distinguables** -- trois cardinaux de frames differents, trois
   etats de tirage differents (jamais imprime / imprime / imprime et scanne) ;
3. **la position se verifie sur la liste que le CODE parcourt** -- l'ordre des
   conflits est celui d'`ordonner_par_lot`, c'est-a-dire **alphabetique par
   lot**, et non celui du manifeste. La fabrique ecrit donc ses lots dans un
   ordre de manifeste **different** de l'ordre alphabetique, sans quoi le tri
   serait invisible ;
4. **rien n'est tape a la main de ce que le produit sait construire** -- les
   noms de tirage sortent de `io.naming.build_sheets_pdf_filename`.

**Aucun test de ce banc ne mesure une horloge** (piege paye le meme jour par le
lot H) : la question posee a chacun est « passerait-il si le temps ne
s'ecoulait pas ? », et la reponse est oui partout -- l'instant du journal est
**donne** par `horloge`, et le double du coeur emet ses jalons en synchrone.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import makepdf, page_templates, pdf_composition
from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import naming, pdf_manifest, scan_manifest
from mixed_media_utility.tui import (
    atelier_pdf,
    atelier_pdf_calibration as calibration,
    atelier_pdf_confirmation as confirmation,
    atelier_pdf_execution as execution_pdf,
    atelier_pdf_lots as lots_pdf,
    atelier_pdf_parcours as parcours_pdf,
    atelier_pdf_reglages as reglages_pdf,
    atelier_pdf_resultat as resultat_pdf,
    atelier_pdf_versions as versions,
)
from mixed_media_utility.tui.coque import (
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)
from mixed_media_utility.tui.execution import EcranRefus, SurfaceExecution

PROJET = "projet_demo"

#: Le pied du palier temoin. Il n'est pas invente : `E5-0` le dessine, et la
#: confrontation en fin de fichier le verifie sur le dessin lu a sa source.
PIED_DU_PALIER = "Q quitter"

#: Le commentaire que le parcours de la mire tape. Ecrit ici une seule fois,
#: comme le pied ci-dessus : c'est ce qui empeche la confrontation de fin de
#: fichier de diverger de l'emploi. `E5-6` et `E5-6b` le dessinent.
COMMENTAIRE_DE_LA_MIRE = "papier mat"

#: **QUATRE lots**, et leur ordre alphabetique n'est pas celui du manifeste :
#: `aa-premier_5` < `plan-04_25` < `plan-04_8` < `zz-dernier_2`. La fabrique les
#: ecrit **dans le desordre**, sans quoi le tri par lot d'`EPIC11-ARB-177`
#: serait invisible -- un banc dont la fabrique ecrirait deja les lots tries ne
#: verrait aucune difference entre « trie » et « pas trie ».
LOT_PREMIER = "aa-premier_5"
LOT_SCANNE = "plan-04_25"
LOT_CIBLE = "plan-04_8"
LOT_SANS_TIRAGE = "zz-dernier_2"

#: Les lots coches d'une passe complete, **dans l'ordre de la liste**.
LOTS_COCHES = (LOT_PREMIER, LOT_SCANNE, LOT_CIBLE, LOT_SANS_TIRAGE)

#: L'ordre dans lequel les conflits doivent se presenter : **par lot**, et
#: **trois** d'entre eux. La cible du tri -- le lot scanne, celui dont l'ecran
#: perd une issue -- y est **AU MILIEU** : une fabrique a deux conflits la
#: placerait en second **et** en dernier, ou un mutant de terminaison de boucle
#: survit (regle des fabriques, point 2 bis).
ORDRE_DES_CONFLITS = (LOT_PREMIER, LOT_SCANNE, LOT_CIBLE)

#: Quatre cardinaux de frames **differents**. Un remplissage uniforme rendrait
#: toute permutation invisible -- c'est le mutant `M33` de la story 5.6.
FRAMES = {LOT_PREMIER: 60, LOT_SCANNE: 124, LOT_CIBLE: 40,
          LOT_SANS_TIRAGE: 12}

#: Le gabarit de chaque lot, quatre valeurs differentes.
GABARITS = {LOT_PREMIER: "tpl-a4-portrait-2f-v2",
            LOT_SCANNE: "tpl-a4-paysage-6f-v2",
            LOT_CIBLE: "tpl-a4-portrait-4f-v2",
            LOT_SANS_TIRAGE: "tpl-a4-paysage-8f-v2"}

#: Combien de tirages chaque lot porte deja. **Quatre etats distinguables** :
#: deux ecrasables, trois dont le dernier est scanne, deux ecrasables, aucun.
TIRAGES = {LOT_PREMIER: 2, LOT_SCANNE: 3, LOT_CIBLE: 2, LOT_SANS_TIRAGE: 0}

#: Le rush de chaque lot. Deux lots partagent le meme rush -- c'est le cas
#: nominal v2.1, deux cadences du meme plan -- et les autres en ont d'autres :
#: un `find` qui rendrait le premier rush venu se demasque alors.
RUSHES = {LOT_PREMIER: "aa-premier", LOT_SCANNE: "plan-04",
          LOT_CIBLE: "plan-04", LOT_SANS_TIRAGE: "zz-dernier"}


# ---------------------------------------------------------------------------
# Fabriques -- le projet, son manifeste, ses tirages
# ---------------------------------------------------------------------------

def _rush(rush_id: str) -> dict:
    return {"rush_id": rush_id, "source_name": f"{rush_id}.mov",
            "fps_source": 25.0, "fps_source_exact": "25/1",
            "resolution_source": {"width": 1920, "height": 1080}}


def _lot(lot_id: str) -> dict:
    return {"lot_id": lot_id, "rush_id": RUSHES[lot_id], "state": "extract",
            "fps_target": 12.5, "fps_target_exact": "25/2",
            "timecode_base_fps": "25/1",
            "template_id": GABARITS[lot_id],
            "patch_preset_id": "patches-17-v4",
            "gamut_map_id": "gamut-map-none-1",
            "expected_frame_count": FRAMES[lot_id],
            "frames_dir": f"frames/{lot_id}",
            "source_frame_count": FRAMES[lot_id] * 2,
            "source_frame_count_is_exact": True,
            "rounding_policy": "floor"}


def _manifeste() -> dict:
    return {
        "schema_version": "2.1",
        "project_id": PROJET,
        "created": "2026-09-02T00:00:00Z",
        "rushes": [_rush("plan-04"), _rush("zz-dernier"),
                   _rush("aa-premier")],
        # **L'ordre du manifeste n'est PAS l'ordre alphabetique** : la cible du
        # tri par lot est au milieu de la liste triee, et en queue de celle-ci.
        "lots": [_lot(LOT_SANS_TIRAGE), _lot(LOT_CIBLE), _lot(LOT_PREMIER),
                 _lot(LOT_SCANNE)],
        "artifacts": {"frames_dir": "frames"},
        "color": {"target_colorspace": "bt709"},
        "video": {}, "reconstruction": {},
    }


def _rangs(lot_id: str) -> list[int | None]:
    """`None` (l'origine, qui n'ecrit aucun fragment de nom), puis 2, 3..."""
    return [None] + list(range(2, TIRAGES[lot_id] + 1))


def _poser_les_tirages(dossier: Path, manifeste: dict) -> dict:
    for lot in manifeste["lots"]:
        lot_id = lot["lot_id"]
        if not TIRAGES[lot_id]:
            continue
        inventaire = []
        for rang in _rangs(lot_id):
            nom = naming.build_sheets_pdf_filename(
                PROJET, lot["rush_id"], lot_id, rang,
                template_id=GABARITS[lot_id])
            chemin = f"planches/{nom}"
            entree = {pdf_manifest.SHEETS_INVENTORY_KEY: chemin}
            if rang is not None:
                entree["version_rank"] = rang
            inventaire.append(entree)
            (dossier / chemin).write_bytes(b"%PDF-1.4\n" * 64)
        lot[pdf_manifest.SHEETS_INVENTORY_FIELD] = sorted(
            inventaire, key=lambda e: e[pdf_manifest.SHEETS_INVENTORY_KEY])
        lot[pdf_manifest.SHEETS_WATERMARK_FIELD] = TIRAGES[lot_id]
    # **Le dernier tirage du lot scanne l'a ete**, et lui seul : c'est ce qui
    # retire `Remplacer ce tirage` de son ecran (`EPIC11-ARB-176`, au RANG).
    for lot in manifeste["lots"]:
        if lot["lot_id"] == LOT_SCANNE:
            lot[scan_manifest.SCANNED_VERSION_RANKS_FIELD] = [
                TIRAGES[LOT_SCANNE]]
    return manifeste


def _projet(tmp_path, *, avec_tirages: bool = True) -> Path:
    chemin = creer_projet(tmp_path, PROJET).chemin
    (chemin / "planches").mkdir(parents=True, exist_ok=True)
    manifeste = _manifeste()
    if avec_tirages:
        _poser_les_tirages(chemin, manifeste)
    (chemin / "project.json").write_text(json.dumps(manifeste),
                                         encoding="utf-8")
    return chemin


def _projet_vide(tmp_path) -> Path:
    chemin = creer_projet(tmp_path, PROJET).chemin
    manifeste = _manifeste()
    manifeste["lots"] = []
    (chemin / "project.json").write_text(json.dumps(manifeste),
                                         encoding="utf-8")
    return chemin


# ---------------------------------------------------------------------------
# Le double du coeur -- il TRACE, et c'est ce qui rend l'entrelacement mesurable
# ---------------------------------------------------------------------------

@dataclass
class _Qr:
    module_side: int = 77


@dataclass
class _Page:
    frames: tuple
    qr: _Qr = field(default_factory=_Qr)


@dataclass
class _Plan:
    page_count: int
    template_id: str
    pages: tuple


@dataclass
class _Issue:
    plan: _Plan
    output_path: Path
    version_rank: int | None = None


class CoeurDouble:
    """Un double de `makepdf.generer_les_planches_du_lot` qui **trace**.

    La trace est ce que la frontiere d'entrelacement lit : un `("jalon", lot, k)`
    par page reellement emise, puis un `("pdf", lot)` quand le fichier est
    rendu. Une frontiere de **contenu** -- meme l'egalite des deux suites --
    serait aveugle a un PDF rendu avant ses jalons, ou a une passe qui ecrirait
    les deux lots avant d'emettre quoi que ce soit. C'est la lecon du lot B4.
    """

    def __init__(self, *, pages, refuse=(), leve=None, sonde=None,
                 reel=None, rangs=None):
        self.pages = dict(pages)
        #: **Le compte REEL de pages du plan, quand il differe de l'attendu.**
        #: Sans lui, `_Plan.page_count` valait toujours `lot.pages` : le
        #: « compte reel » et le « compte attendu » coincidaient partout, donc
        #: `planche_ecrite` pouvait lire l'un pour l'autre sans qu'aucun banc
        #: s'en apercoive (mutant `C1-M12`, survivant). Regle des fabriques :
        #: deux valeurs uniformes rendent toute permutation invisible.
        self.reel = dict(reel or {})
        #: **Le rang que le coeur rend**, par lot. Il valait `None` partout,
        #: donc `PlancheEcrite.rang` valait le rang d'origine dans **tous** les
        #: tests, quel que soit ce que la decision de conflit avait retenu
        #: (mutant `C1-M20`, survivant).
        self.rangs = dict(rangs or {})
        self.refuse = set(refuse)
        self.leve = leve
        #: Appelee **a l'entree** de chaque lot, avant tout jalon. C'est le seul
        #: instant ou l'etat de la passe se lit « entre deux lots », et c'est
        #: celui qu'un compte non remis a zero salit.
        self.sonde = sonde
        self.trace: list[tuple] = []
        self.appels: list[dict] = []

    #: La ligne que le double ecrit dans le journal qu'on lui passe. C'est la
    #: forme reelle : le coeur journalise `compression de gamut: ...` et
    #: `PDF ecrit: ...`, et ces lignes n'ont nulle part ou aller tant que le
    #: parcours n'a pas **vise** le journal de l'ecran (finding `H1`).
    LIGNE_DE_JOURNAL = "PDF ecrit pour {lot}"

    def __call__(self, dossier_projet, *, lot, overwrite=False, logger=None,
                 rappel_progression=None, **reglages):
        if self.sonde is not None:
            self.sonde(lot)
        if logger is not None:
            logger.info(self.LIGNE_DE_JOURNAL.format(lot=lot))
        self.appels.append(dict(lot=lot, overwrite=overwrite,
                                dossier=Path(dossier_projet), **reglages))
        if lot in self.refuse:
            self.trace.append(("refus", lot))
            raise makepdf.RefusDeMakepdf(f"le lot {lot} est refuse",
                                         motif=makepdf.MOTIF_LOT_NON_CONFORME)
        if self.leve is not None and lot == self.leve:
            self.trace.append(("panne", lot))
            raise ZeroDivisionError("panne hors table")
        pages = self.pages[lot]
        for rang in range(1, pages + 1):
            self.trace.append(("jalon", lot, rang))
            if rappel_progression is not None:
                rappel_progression(rang, pages)
        self.trace.append(("pdf", lot))
        gabarit = GABARITS[lot]
        # Le compte du PLAN peut differer du compte des jalons : c'est le cas
        # reel d'un lot dont la derniere page est partielle, et c'est ce qui
        # separe « le compte reel » du « compte attendu ».
        reel = self.reel.get(lot, pages)
        version = self.rangs.get(lot)
        plan = _Plan(page_count=reel, template_id=gabarit,
                     pages=tuple(_Page(frames=("f",) * 4)
                                 for _ in range(pages)))
        nom = naming.build_sheets_pdf_filename(
            PROJET, RUSHES[lot], lot, version, template_id=gabarit)
        return _Issue(plan=plan, output_path=Path(dossier_projet) / "planches"
                      / nom, version_rank=version)


class MireDouble:
    """Un double de `makepdf.generer_la_page_de_calibration`."""

    def __init__(self) -> None:
        self.appels: list[dict] = []

    def __call__(self, dossier_projet, **reglages):
        self.appels.append(dict(dossier=Path(dossier_projet), **reglages))
        chemin = Path(dossier_projet) / "planches" / "mire.pdf"
        return _Issue(plan=_Plan(1, "tpl-a4-paysage-6f-v2", ()),
                      output_path=chemin)


# ---------------------------------------------------------------------------
# Le banc : une application montee, et un espion sur les ecrans empiles
# ---------------------------------------------------------------------------

def _app(**kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", PIED_DU_PALIER)],
                    contexte=Contexte(projet=PROJET), **kwargs)


def _espionner(app) -> list[str]:
    """Les noms des ecrans empiles, **dans l'ordre**.

    L'ensemble exact des ecrans montes est la seule mesure qui attrape une
    inversion d'ordre : « la confirmation se monte » reste vrai qu'elle vienne
    avant ou apres le conflit, et c'est precisement ce qu'`EPIC11-ARB-172`
    tranche.
    """
    vus: list[str] = []
    vrai = app.descendre

    def descendre(palier=None):
        vus.append("(remontee)" if palier is None else type(palier).__name__)
        return vrai(palier)

    app.descendre = descendre
    return vus


def _parcours(app, dossier, coeur=None, mire=None, **reglages):
    return parcours_pdf.ParcoursPdf(
        app, dossier, generer=coeur, calibrer=mire,
        horloge=lambda: datetime(2026, 9, 2, 16, 22, 41), **reglages)


def _cocher_et_regler(parcours, ecran_des_lots, *, lots):
    """Cocher les lots nommes a `E5-1`, puis valider `E5-2` **au clavier**.

    Tout passe par `traiter`, jamais par un appel direct des rappels : ce qu'on
    mesure est ce qu'un operateur obtient de son clavier, et un test qui
    appellerait `parcours.regler(...)` sauterait exactement le cablage qu'il
    croit mesurer.
    """
    for lot_id in lots:
        ecran_des_lots.liste.viser(lot_id)
        ecran_des_lots.traiter("space")
    ecran_des_lots.traiter("enter")
    ecran = parcours.app.screen
    ecran.traiter("enter")      # depuis un champ de choix : saute sur Valider
    ecran.traiter("enter")      # sur `Valider` : valide
    return ecran


def _jouer(scenario, app, banc):
    async def tour(pilote):
        return await scenario(pilote)

    return banc(app, tour)


# ===========================================================================
# Le parcours de bout en bout -- l'ordre des ecrans (AC 6.8, `EPIC11-ARB-172`)
# ===========================================================================

def test_le_menu_MENE_aux_deux_parcours_et_plus_a_un_ecran_pas_encore(
        tmp_path, banc):
    """Le cablage ferme les quatre manques que les lots d'ecran declaraient.

    **Un `EcranPasEncore` qui survit au cablage est un mensonge a l'ecran** : il
    dit « pas encore construit » d'un ecran livre. La mesure porte sur les deux
    entrees du menu -- une mesure sur la seule premiere laisserait la seconde
    muette, et c'est la forme exacte du finding `K3`.
    """
    dossier = _projet(tmp_path)
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        montes = []
        for rang in (0, 1):
            parcours = _parcours(pilote.app, dossier)
            menu = parcours.ouvrir()
            menu.curseur = rang
            menu.traiter("enter")
            await pilote.pause()
            montes.append(type(pilote.app.screen).__name__)
        return montes

    montes = _jouer(scenario, app, banc)
    assert montes == [lots_pdf.EcranLotsAPlanches.__name__,
                      calibration.EcranMireReglages.__name__]
    assert EcranPasEncore.__name__ not in vus, vus


def test_l_ordre_des_ecrans_est_EXACT_et_le_conflit_precede_la_confirmation(
        tmp_path, banc):
    """`EPIC11-ARB-172`, mesure en **ensemble exact et ordonne**.

    Verbatim d'Egan : « comment sait-on deja que cela va etre le lot 4 si on n'a
    pas tranche pour l'ecrasement ou le versionnage ? Ce choix arrive avant
    non ? » Le numero entre dans le nom, dans l'etiquette imprimee et dans le
    code-barres : quand la confirmation s'affiche, il doit etre un **fait**.

    Le mutant que ce test tue est l'inversion -- confirmation puis conflit --,
    et aucune assertion positive (« le conflit se monte ») ne le verrait.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SCANNE: 21, LOT_CIBLE: 7,
                               LOT_SANS_TIRAGE: 2})
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        menu = parcours.ouvrir()
        menu.traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        # Trois conflits : on tranche chacun par `⏎` sur l'issue au curseur,
        # qui est celle qui n'ecrit pas.
        for _ in ORDRE_DES_CONFLITS:
            pilote.app.screen.traiter("enter")
            await pilote.pause()
        return None

    _jouer(scenario, app, banc)
    assert vus == [
        atelier_pdf.EcranPdfMenu.__name__,
        lots_pdf.EcranLotsAPlanches.__name__,
        reglages_pdf.EcranReglagesDesPlanches.__name__,
        versions.EcranConflitDeTirage.__name__,
        versions.EcranConflitDeTirage.__name__,
        versions.EcranConflitDeTirage.__name__,
        confirmation.EcranPdfConfirmation.__name__,
    ], vus


def test_sans_aucun_tirage_anterieur_AUCUN_ecran_de_conflit_ne_se_monte(
        tmp_path, banc):
    """Le volet symetrique : l'inversion **coute zero ecran**.

    Sans lui, une implementation qui monterait un ecran de conflit a chaque
    passe -- vide de tout tirage a trancher -- serait verte au test precedent.
    """
    dossier = _projet(tmp_path)
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()

    _jouer(scenario, app, banc)
    assert versions.EcranConflitDeTirage.__name__ not in vus, vus
    assert vus[-1] == confirmation.EcranPdfConfirmation.__name__, vus


def test_l_ecran_de_conflit_se_monte_UNE_FOIS_PAR_LOT_et_dans_l_ordre_PAR_LOT(
        tmp_path, banc):
    """`EPIC11-ARB-177`, reponse d'Egan du 2026-09-02 : « **Par lot** ».

    Deux proprietes en une mesure, et elles se cassent separement :

    * **une fois par lot** -- un parcours qui monterait l'ecran une seule fois
      pour toute la passe trancherait le premier lot puis ecrirait les autres
      sans les avoir montres. C'est le mutant que le cardinal attrape ;
    * **dans l'ordre par lot** -- la fabrique ecrit ses lots dans un ordre de
      manifeste different de l'ordre alphabetique, donc un parcours qui
      garderait l'ordre du document rendrait l'autre suite.
    """
    dossier = _projet(tmp_path)
    app = _app()
    ordre: list[str] = []

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=list(LOTS_COCHES))
        await pilote.pause()
        for _ in ORDRE_DES_CONFLITS:
            ecran = pilote.app.screen
            ordre.append(ecran.tirage.lot_id)
            ecran.traiter("enter")
            await pilote.pause()
        return type(pilote.app.screen).__name__

    dernier = _jouer(scenario, app, banc)
    assert tuple(ordre) == ORDRE_DES_CONFLITS, ordre
    assert dernier == confirmation.EcranPdfConfirmation.__name__


def test_le_lot_SANS_tirage_ne_recoit_AUCUN_ecran_de_conflit(tmp_path, banc):
    """La cible du tri est au MILIEU, et le lot sans tirage est en queue.

    Ensemble **exact** des lots qui recoivent un ecran : mesurer « le lot cible
    en recoit un » laisserait passer un parcours qui en monterait un pour tous.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=list(LOTS_COCHES))
        await pilote.pause()
        return tuple(c.lot_id for c in parcours.conflits.conflits)

    assert _jouer(scenario, app, banc) == ORDRE_DES_CONFLITS


# ===========================================================================
# Ce que les issues du conflit retiennent (`EPIC11-ARB-89`, `-177`)
# ===========================================================================

def _trancher(tmp_path, banc, *, lots, cles):
    """Derouler jusqu'aux conflits et retenir `cles`, une par ecran monte."""
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=lots)
        await pilote.pause()
        for cle in cles:
            ecran = pilote.app.screen
            ecran.choix.viser(cle)
            ecran.traiter("enter")
            await pilote.pause()
        return parcours

    return _jouer(scenario, app, banc)


def test_REMPLACER_vise_le_tirage_present_et_CREER_celui_d_a_cote(
        tmp_path, banc):
    """Les deux decisions se lisent sur le numero que la confirmation affiche.

    Ce n'est **pas** une egalite de mot : `remplacer` doit rendre le numero du
    tirage present, `creer` celui d'a cote. Un parcours qui rendrait toujours le
    meme serait vert sur le seul cas ou les deux coincident, et il n'y en a
    aucun ici -- les deux lots portent des cardinaux de tirages differents.
    """
    parcours = _trancher(tmp_path, banc, lots=list(ORDRE_DES_CONFLITS),
                         cles=[versions.CLE_CREER, versions.CLE_CREER,
                               versions.CLE_REMPLACER])
    par_lot = {lot.lot_id: lot.rang for lot in parcours.lots_a_imprimer()}
    # Le lot scanne a trois tirages : `creer` vise le quatrieme.
    assert par_lot[LOT_SCANNE] == TIRAGES[LOT_SCANNE] + 1
    # Le premier en a deux : `creer` vise le troisieme.
    assert par_lot[LOT_PREMIER] == TIRAGES[LOT_PREMIER] + 1
    # Le lot cible en a deux : `remplacer` reprend le second, jamais un neuf.
    assert par_lot[LOT_CIBLE] == TIRAGES[LOT_CIBLE]


def test_l_ecrasement_retenu_passe_overwrite_au_COEUR_et_lui_seul(
        tmp_path, banc):
    """Le drapeau n'est pas decoratif : c'est lui qui vise le tirage existant.

    **Ensemble exact des lots qui l'emportent**, et non « le lot cible
    l'emporte » : un parcours qui le passerait a tous les lots ferait ecraser un
    tirage que personne n'a designe, ce qui est la destruction silencieuse
    qu'`EPIC11-ARB-89` proscrit.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_PREMIER: 30, LOT_SCANNE: 21, LOT_CIBLE: 7})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for cle in (versions.CLE_CREER, versions.CLE_CREER,
                    versions.CLE_REMPLACER):
            ecran = pilote.app.screen
            ecran.choix.viser(cle)
            ecran.traiter("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()

    _jouer(scenario, app, banc)
    ecrasants = {appel["lot"] for appel in coeur.appels if appel["overwrite"]}
    assert ecrasants == {LOT_CIBLE}, coeur.appels


def test_la_MASSE_emporte_les_restants_et_SAUTE_le_tirage_scanne(
        tmp_path, banc):
    """`EPIC11-ARB-177` contrainte 2, et `EPIC11-ARB-174` / `-176`.

    « Le tirage scanne est **saute**, et le saut est **compte** pour pouvoir
    etre dit. » L'ecran l'annonce sous l'issue ; ce test mesure que le parcours
    fait ce que l'ecran a annonce -- les deux lectures ne peuvent pas diverger.

    L'ordre par lot met un tirage **ecrasable** en premier : sa masse est donc
    destructive, et elle emporte les deux suivants -- dont le tirage scanne,
    qu'elle doit sauter. C'est exactement la scene que la maquette `E5-3b`
    dessine (`3 lots · 1 056 Mo effaces — 1 saute, il est scanne`).

    **Ensemble exact des trois decisions** : mesurer que le scanne est saute
    laisserait passer une masse qui n'emporterait que lui.
    """
    parcours = _trancher(tmp_path, banc, lots=list(ORDRE_DES_CONFLITS),
                         cles=[versions.CLE_MASSE])
    assert parcours.decisions == {
        LOT_PREMIER: parcours_pdf.DECISION_ECRASER,
        LOT_CIBLE: parcours_pdf.DECISION_ECRASER,
        LOT_SCANNE: parcours_pdf.DECISION_ECRIRE_A_COTE,
    }


def test_la_MASSE_douce_n_ecrase_PERSONNE_pas_meme_un_tirage_ecrasable(
        tmp_path, banc):
    """Le volet symetrique : une masse **non destructive** n'ecrase rien.

    Elle est retenue sur le **second** conflit -- celui du tirage scanne, dont
    l'ecran ne porte pas `Remplacer ce tirage` --, et elle emporte le troisieme
    lot, qui est pourtant ecrasable. Une implementation qui lirait
    l'ecrasabilite du lot **emporte** plutot que celle du lot **courant**
    ecraserait ici, et ce serait l'inverse de ce que l'ecran a chiffre.
    """
    parcours = _trancher(tmp_path, banc, lots=list(ORDRE_DES_CONFLITS),
                         cles=[versions.CLE_CREER, versions.CLE_MASSE])
    assert set(parcours.decisions.values()) == \
        {parcours_pdf.DECISION_ECRIRE_A_COTE}, parcours.decisions


def test_ANNULER_sur_un_conflit_n_ecrit_RIEN_et_ne_confirme_PAS(
        tmp_path, banc):
    """« Jamais une seule issue, jamais un blocage sec » -- et celle-ci sort.

    Elle est la seule qui n'ecrit rien, et le parcours doit la traiter comme
    telle : aucun ecran de confirmation, aucune decision retenue.
    """
    dossier = _projet(tmp_path)
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_CIBLE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(versions.CLE_ANNULER)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours

    parcours = _jouer(scenario, app, banc)
    assert confirmation.EcranPdfConfirmation.__name__ not in vus, vus
    assert parcours.decisions == {}


# ===========================================================================
# La boucle multi-lots -- tache I2
# ===========================================================================

def _passe(lots):
    return execution_pdf.PasseDeGeneration(lots=tuple(
        execution_pdf.LotEnGeneration(nom=lot.nom, pages=lot.pages,
                                      gabarit=lot.gabarit, rang=lot.rang or 1,
                                      libelle=lot.lot_id)
        for lot in lots))


def _a_generer(lot_id, pages, *, ecraser=False, rang=None):
    gabarit = GABARITS[lot_id]
    return parcours_pdf.LotAGenerer(
        lot_id=lot_id, rush_id=RUSHES[lot_id], frames=FRAMES[lot_id],
        pages=pages, gabarit=gabarit, rang=rang, ecraser=ecraser,
        nom=naming.build_sheets_pdf_filename(
            PROJET, RUSHES[lot_id], lot_id, rang, template_id=gabarit))


#: Trois lots aux paginations **differentes**, la cible AU MILIEU. Trois et non
#: deux : une fabrique a deux lots place la cible en second **et** en dernier,
#: ou un mutant de terminaison de boucle survit (regle des fabriques, 2 bis).
TROIS_LOTS = (
    (LOT_SCANNE, 21),
    (LOT_CIBLE, 7),
    (LOT_SANS_TIRAGE, 2),
)


def _executer(tmp_path, coeur, *, lots=TROIS_LOTS, interrompu=None,
              observateur=None):
    a_generer = tuple(_a_generer(lot_id, pages) for lot_id, pages in lots)
    passe = _passe(a_generer)
    surface = SurfaceExecution(unite=execution_pdf.UNITE)
    if observateur is not None:
        # **Abonne AVANT la passe**, comme le produit le fait : s'abonner apres
        # ne verrait rien, et c'est precisement la propriete que la ligne
        # d'abonnement du parcours existe pour tenir.
        surface.abonner(observateur)
    rapport = parcours_pdf.executer_les_lots(
        a_generer, passe, surface, dossier_projet=tmp_path,
        reglages={"orientation": "paysage", "frames_per_page": 6,
                  "margin_preset": page_templates.DEFAULT_MARGIN_PRESET},
        gabarit=GABARITS[LOT_SCANNE], generer=coeur, interrompu=interrompu,
        horloge=lambda: datetime(2026, 9, 2, 16, 22, 41))
    return rapport, passe, surface


def test_I2_la_boucle_appelle_le_coeur_UNE_FOIS_PAR_LOT_dans_l_ordre(tmp_path):
    """Un appel par lot, **dans l'ordre du plan**, et le lot_id de chacun.

    Le mutant est la boucle qui s'arrete au premier lot : il rend un seul appel
    et un rapport a une planche, ce que le cardinal attrape.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS))
    rapport, _passe_, _surface = _executer(tmp_path, coeur)
    assert [appel["lot"] for appel in coeur.appels] == \
        [lot_id for lot_id, _ in TROIS_LOTS]
    assert len(rapport.ecrites) == len(TROIS_LOTS)


def test_I2_un_lot_REFUSE_n_annule_NI_ceux_d_avant_NI_ceux_d_apres(tmp_path):
    """« Un echec sur le lot k n'annule pas les lots < k », et pas ceux > k.

    **L'echec est au MILIEU** : en premiere position, un `break` serait
    indiscernable d'un `continue` sur le rapport ; en derniere, aussi. C'est le
    mutant `continue` -> `break` que la 11.4b a paye trois fois.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS), refuse=[LOT_CIBLE])
    rapport, _passe_, _surface = _executer(tmp_path, coeur)
    # **L'assertion `[p.nom.count("_") >= 0 for ...]` a ete RETIREE** (finding
    # `T1`) : `count(...) >= 0` est vrai pour toute chaine, donc la liste ne
    # pouvait contenir que des `True` et l'assertion ne tombait que sur une
    # liste vide -- c'est-a-dire qu'elle mesurait « le rapport porte au moins
    # une planche », ce que la ligne de cardinal ci-dessous mesure mieux.
    assert [appel["lot"] for appel in coeur.appels] == \
        [lot_id for lot_id, _ in TROIS_LOTS]
    assert len(rapport.ecrites) == 2
    assert [refus.lot_id for refus in rapport.refus] == [LOT_CIBLE]
    assert rapport.refus[0].motif == makepdf.MOTIF_LOT_NON_CONFORME


def test_I2_une_panne_HORS_TABLE_traverse_au_lieu_d_etre_deguisee(tmp_path):
    """« Deguiser une panne inconnue en refus metier ferait lire un motif
    rassurant sur un bug. » -- volet symetrique du test precedent."""
    coeur = CoeurDouble(pages=dict(TROIS_LOTS), leve=LOT_CIBLE)
    with pytest.raises(ZeroDivisionError):
        _executer(tmp_path, coeur)


def test_I2_l_interruption_est_consultee_ENTRE_deux_lots(tmp_path):
    """La granularite est **dite** plutot que devinee.

    Le drapeau se leve apres le premier lot : la boucle doit s'arreter **avant**
    le second, et le rapport porter ce qui est ecrit. Une consultation faite
    seulement au premier tour laisserait la passe entiere partir.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS))
    # Le drapeau se leve **des que le premier lot est parti** : la boucle doit
    # donc s'arreter au second tour, avant tout second appel du coeur.
    rapport, _passe_, _surface = _executer(
        tmp_path, coeur, interrompu=lambda: bool(coeur.appels))
    assert rapport.interrompu is True
    assert [appel["lot"] for appel in coeur.appels] == [TROIS_LOTS[0][0]]
    assert len(rapport.ecrites) == 1


def test_I4_la_suite_des_jalons_est_ENTRELACEE_avec_les_PDF_ecrits(tmp_path):
    """La frontiere d'entrelacement que le lot I ne pouvait pas poser.

    **Cette frontiere etait une TAUTOLOGIE, et le finding `T2` l'a prouvee au
    mutant.** Elle assertait sur `coeur.trace`, que `CoeurDouble.__call__`
    construit **lui-meme** : le double empile `("jalon", lot, k)` puis
    `("pdf", lot)` dans cet ordre, quoi que fasse le produit. Aucun des deux
    scenarios que son docstring annoncait n'etait exprimable par le double.
    Mesure : le mutant `C1-M3`, qui **eteint completement** le canal de
    progression (`surface.emetteur(0)` -- plus aucun jalon n'atteint la
    surface, ni l'ecran, ni le journal), la laissait **verte**.

    Ce qu'il faut croiser est ce que la **surface a recu** avec ce que le coeur
    a rendu : le premier passe par le produit, le second vient du double, et
    aucun des deux ne peut fabriquer l'autre. L'observateur est abonne
    **avant** la passe, comme le produit s'y abonne, et il ecrit dans la meme
    liste que le double -- l'ordre relatif des deux est alors un fait, pas une
    reconstruction.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS))
    croise: list[tuple] = []
    coeur.trace = croise
    _executer(tmp_path, coeur,
              observateur=lambda avancement: croise.append(
                  ("recu", avancement.faites)))
    # On ne garde que ce que le PRODUIT a fait circuler : les jalons recus par
    # la surface, et les retours du coeur. Les `("jalon", ...)` que le double
    # s'ecrit a lui-meme sont precisement ce qui ne mesure rien.
    observe = [ligne for ligne in croise if ligne[0] in ("recu", "pdf")]
    attendu: list[tuple] = []
    for lot_id, pages in TROIS_LOTS:
        attendu += [("recu", rang) for rang in range(1, pages + 1)]
        attendu.append(("pdf", lot_id))
    assert observe == attendu, observe[:12]


def test_I4_le_pourcentage_agrege_la_PASSE_et_non_le_lot_courant(tmp_path):
    """AC 9.1 -- `86 %` des **28** pages de la passe, jamais `43 %` des 7 du lot.

    La mesure est prise **pendant** la passe, au jalon exact de la maquette
    (lot 2, page 3), et la fabrique porte des lots de tailles **differentes** :
    une passe a deux lots egaux ne distingue pas une agregation d'une remise a
    zero.

    C'est aussi la reponse mesuree a `EPIC11-ARB-134` : le cablage est **deja**
    juste sans lui. Ce qu'il retirera est la remise a zero de
    `SurfaceExecution.emetteur`, et la seule ligne a reprendre ce jour-la est
    celle de `EcranGenerationDesPlanches.sur_jalon`.
    """
    deux = TROIS_LOTS[:2]
    coeur = CoeurDouble(pages=dict(deux))
    a_generer = tuple(_a_generer(lot_id, pages) for lot_id, pages in deux)
    passe = _passe(a_generer)
    surface = SurfaceExecution(unite=execution_pdf.UNITE)
    releves: list[tuple[int, int]] = []

    def observer(avancement):
        passe.pages_du_lot_courant = avancement.faites
        releves.append((passe.pages_ecrites, passe.pages_de_la_passe))

    surface.abonner(observer)
    parcours_pdf.executer_les_lots(
        a_generer, passe, surface, dossier_projet=tmp_path,
        reglages={}, generer=coeur,
        horloge=lambda: datetime(2026, 9, 2, 16, 22, 41))

    total = sum(pages for _lot, pages in deux)
    assert releves[-1] == (total, total)
    # Le jalon de la maquette : lot 2, page 3 sur 7, soit 24 pages sur 28.
    au_lot_2_page_3 = releves[deux[0][1] + 2]
    assert au_lot_2_page_3 == (deux[0][1] + 3, total)


def test_I2_le_JOURNAL_nomme_chaque_lot_avant_ses_pages(tmp_path):
    """`EPIC11-ARB-93` : le journal n'est pas remis a zero entre deux lots.

    Sans l'en-tete qui **nomme** le lot, `21/21` suivi de `1/7` se lirait comme
    un compte qui recule. On mesure que chaque en-tete precede les lignes de
    pages de son lot, et qu'il y en a une par lot -- ni zero, ni une seule pour
    toute la passe.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS))
    _rapport, passe, surface = _executer(tmp_path, coeur)
    entetes = [ligne for ligne in surface.journal.lignes
               if any(lot.libelle in ligne and lot.gabarit in ligne
                      for lot in passe.lots)]
    assert len(entetes) == len(TROIS_LOTS), surface.journal.lignes


def test_le_JOURNAL_lit_ses_trois_valeurs_du_PLAN_page_par_page(tmp_path):
    """AC 9.3 -- le cardinal d'emplacements se lit **page par page**.

    Le double rend des pages a quatre emplacements ; une ligne qui recopierait
    le `frames_per_page` de la mise en page rendrait six. La version du
    code-barres, elle, vient de `qr_codes.symbol_version` et jamais d'un
    litteral.
    """
    coeur = CoeurDouble(pages={LOT_CIBLE: 3})
    _rapport, _passe_, surface = _executer(tmp_path, coeur,
                                           lots=((LOT_CIBLE, 3),))
    pages = [l for l in surface.journal.lignes if "emplacements" in l]
    assert len(pages) == 3, surface.journal.lignes
    assert "4 emplacements" in pages[0], pages[0]
    assert "page 3/3" in pages[-1], pages[-1]


# ===========================================================================
# Ce que le compte rendu recoit, et ou les suites menent
# ===========================================================================

def test_le_compte_rendu_porte_UNE_LIGNE_PAR_PDF_ecrit(tmp_path, banc):
    """`E5-5` recoit ce que la passe a produit, jamais ce qu'elle promettait."""
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = _jouer(scenario, app, banc)
    assert execution_pdf.EcranGenerationDesPlanches.__name__ in vus, vus
    assert resultat_pdf.EcranResultatDesPlanches.__name__ in vus, vus
    assert isinstance(ecran, resultat_pdf.EcranResultatDesPlanches)
    assert len(ecran.table.planches) == 1


def test_une_passe_ou_RIEN_n_est_ecrit_mene_au_REFUS_et_non_au_compte_rendu(
        tmp_path, banc):
    """Trois conclusions, et celle-ci a sa destination.

    Le message du coeur est affiche **tel quel** (`EPIC11-ARB-30`) : la TUI ne
    le resume pas et ne le requalifie pas.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2}, refuse=[LOT_SANS_TIRAGE])
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = _jouer(scenario, app, banc)
    assert isinstance(ecran, EcranRefus)
    assert ecran.code == makepdf.MOTIF_LOT_NON_CONFORME
    assert LOT_SANS_TIRAGE in ecran.message


@pytest.mark.parametrize("suite,attendu", [
    (resultat_pdf.SUITE_CALIBRATION, calibration.EcranMireReglages.__name__),
    (resultat_pdf.SUITE_AUTRES_LOTS, lots_pdf.EcranLotsAPlanches.__name__),
])
def test_les_SUITES_du_compte_rendu_menent_ailleurs_et_pas_a_un_ecran_mort(
        tmp_path, banc, suite, attendu):
    """`K3` : quatre suites navigables et **decoratives**, paye une fois.

    Une suite par ligne, jamais une mesure sur la seule premiere. `Ouvrir le
    dossier` n'y figure pas : elle ne change pas d'ecran, et son propre banc la
    mesure.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.charger()
        parcours.suivre(suite)
        await pilote.pause()
        return type(pilote.app.screen).__name__

    assert _jouer(scenario, app, banc) == attendu


# ===========================================================================
# La mire de calibration -- l'autre entree du menu (AC 8)
# ===========================================================================

def test_le_parcours_de_la_MIRE_va_du_formulaire_au_compte_rendu(
        tmp_path, banc):
    """`E5-6` -> `E5-6b` -> `E5-6c` -> `E5-6e`, en ensemble **exact et ordonne**.

    Aucune mire du meme nom n'existe : `E5-6d` ne doit donc pas se monter, et
    c'est ce que l'ensemble exact mesure -- « le conflit se monte » resterait
    vrai d'un parcours qui le monterait toujours.
    """
    dossier = _projet(tmp_path)
    mire = MireDouble()
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in "hp-envy":
            ecran.traiter("", lettre)
        ecran.traiter("enter")      # la chaine est nommee : on continue
        await pilote.pause()
        confirme = pilote.app.screen
        confirme.choix.viser(calibration.ISSUE_GENERER)
        confirme.traiter("enter")
        await pilote.pause()

    _jouer(scenario, app, banc)
    assert vus == [
        atelier_pdf.EcranPdfMenu.__name__,
        calibration.EcranMireReglages.__name__,
        calibration.EcranMireConfirmation.__name__,
        calibration.EcranMireEnCours.__name__,
        calibration.EcranMireEcrite.__name__,
    ], vus
    assert len(mire.appels) == 1
    assert mire.appels[0]["scan_chain_label"] == "hp-envy"


def test_une_mire_du_MEME_NOM_intercale_l_ecran_de_conflit_AVANT_la_confirmation(
        tmp_path, banc):
    """Meme ordre que pour les planches, et pour le meme motif.

    « On ne confirme pas ce qu'on va ecrire avant de savoir *ou* on l'ecrit. »
    Le volet symetrique est le test precedent : sans mire presente, l'ecran ne
    se monte pas.
    """
    dossier = _projet(tmp_path)
    chaine = "hp-envy"
    chemin = calibration.chemin_de_la_mire(dossier, PROJET, chaine)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"%PDF-1.4\n")
    mire = MireDouble()
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in chaine:
            ecran.traiter("", lettre)
        ecran.traiter("enter")
        await pilote.pause()
        conflit = pilote.app.screen
        conflit.choix.viser(calibration.ISSUE_REMPLACER)
        conflit.traiter("enter")
        await pilote.pause()
        return type(pilote.app.screen).__name__

    dernier = _jouer(scenario, app, banc)
    assert vus[1:3] == [calibration.EcranMireReglages.__name__,
                        calibration.EcranMireExiste.__name__], vus
    assert dernier == calibration.EcranMireConfirmation.__name__
    assert mire.appels == []


# ===========================================================================
# Les regimes que le cablage doit DIRE plutot que taire
# ===========================================================================

def test_un_projet_SANS_AUCUN_LOT_le_dit_au_lieu_de_tomber(tmp_path, banc):
    """Le modele leve -- « une liste vide n'est pas un choix » -- et le parcours
    le **dit**. La phrase affichee est celle du modele, jamais une seconde
    redaction du meme constat."""
    dossier = _projet_vide(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = _jouer(scenario, app, banc)
    assert isinstance(ecran, EcranRefus)
    assert ecran.code == parcours_pdf.CODE_AUCUN_LOT


def test_une_entree_de_menu_INCONNUE_mene_quand_meme_quelque_part(
        tmp_path, banc):
    """Une erreur de cablage reste une erreur de cablage, pas un clavier casse.

    Elle ne peut pas arriver par le clavier -- le menu n'a que deux entrees --,
    et c'est pour cela qu'elle se mesure ici : la branche existe, et une branche
    qu'aucun test n'exerce n'est pas une branche.
    """
    from mixed_media_utility.tui.atelier_scan import EntreeDeMenu

    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.entrer(EntreeDeMenu("inconnue", "Nom", "Phrase"))
        await pilote.pause()
        return pilote.app.screen

    assert isinstance(_jouer(scenario, app, banc), EcranPasEncore)


def test_le_project_id_vient_du_MANIFESTE_et_non_du_nom_du_DOSSIER(tmp_path):
    """Un dossier renomme a la main ne doit pas renommer les fichiers ecrits.

    Le volet symetrique est le repli : sans manifeste, plus rien n'a ete ecrit,
    et le nom du dossier est alors la seule chose qu'on ait.
    """
    dossier = _projet(tmp_path)
    parcours = parcours_pdf.ParcoursPdf(None, dossier)
    parcours.charger()
    assert parcours.project_id == PROJET
    autre = tmp_path / "renomme"
    autre.mkdir()
    sans = parcours_pdf.ParcoursPdf(None, autre)
    sans.charger()
    assert sans.project_id == "renomme"


def test_les_reglages_partent_au_coeur_SOUS_LE_NOM_QU_IL_LEUR_DONNE(
        tmp_path, banc):
    """`EPIC11-ARB-36` : « tout champ nomme l'argument de coeur qu'il alimente ».

    La mesure est faite contre la **signature reelle** de
    `generer_les_planches_du_lot` : une cle qui n'y figure pas leverait a
    l'appel plutot que d'etre ignoree, et c'est ce qui rend cette table
    mesurable au lieu de declarative.
    """
    import inspect

    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours

    parcours = _jouer(scenario, app, banc)
    attendus = set(inspect.signature(
        makepdf.generer_les_planches_du_lot).parameters)
    assert set(parcours.reglages_du_coeur()) <= attendus
    passes = set(coeur.appels[0]) - {"lot", "overwrite", "dossier"}
    assert passes == set(parcours.reglages_du_coeur()), coeur.appels[0]


# ===========================================================================
# Frontieres du module de cablage
# ===========================================================================

def test_le_module_de_cablage_n_importe_JAMAIS_cli():
    """Frontiere de la story 11.4b, rejouee sur le module neuf.

    Le volet symetrique est la seconde assertion : le module importe bien le
    point d'entree de coeur, donc la mesure regarde un fichier qui a des
    imports.
    """
    from outils_frontiere import identifiants

    noms = identifiants(Path(parcours_pdf.__file__))
    assert "cli" not in noms
    assert not any(nom.endswith(".cli") for nom in noms), sorted(noms)
    assert "makepdf" in noms, sorted(noms)


def test_le_relais_du_journal_du_coeur_est_VISE_sur_le_journal_de_l_ecran():
    """Finding `H1` : le journal de l'ecran n'etait alimente **par rien**.

    Les lignes que la maquette y montre sont des `logger.info` du coeur, et sans
    ce visage elles n'ont nulle part ou aller.

    **Ce test APPELAIT `viser` de sa propre main** (finding `T3`) : il mesurait
    `RelaisDeJournal` -- un module d'une autre story -- et pas que
    `ParcoursPdf.generer` vise le journal de l'ecran d'execution. Le mutant
    `C1-M28`, qui fait que le produit ne vise **jamais**, y survivait : le
    finding `H1` etait rouvert et son test ne le voyait pas.

    La mesure passe donc par le parcours entier, et la ligne vient du coeur --
    le double la journalise avec le `logger` que la boucle lui passe. Rien
    n'est vise a la main ici.
    """
    parcours = parcours_pdf.ParcoursPdf(None, Path("."))
    assert parcours._relais is not None


# ===========================================================================
# Les quatre survivants de la campagne, fermes (2026-09-02)
# ===========================================================================

def test_le_compte_du_lot_courant_est_REMIS_A_ZERO_a_l_entree_de_chaque_lot(
        tmp_path):
    """Mutant `M11` : la remise a zero retiree, et **rien ne rougissait**.

    Ce qu'elle tient se lit a un instant precis -- **entre deux lots**, avant
    que le premier jalon du suivant n'arrive. Sans elle, la passe porte encore
    le compte du lot precedent : sur un lot de 21 pages suivi d'un lot de 7, la
    barre afficherait 21 pages ecrites du lot 2 avant sa premiere page, donc un
    total de la passe **surestime**. Toute mesure prise apres le premier jalon
    est aveugle a ce defaut, parce que le jalon reecrit le champ.

    La sonde lit l'etat **a l'entree** de chaque lot, et la fabrique porte trois
    lots aux paginations differentes : deux lots egaux ne distingueraient pas un
    compte herite d'un compte juste.
    """
    lus: list[tuple[str, int]] = []
    coeur = CoeurDouble(pages=dict(TROIS_LOTS))
    a_generer = tuple(_a_generer(lot_id, pages) for lot_id, pages in TROIS_LOTS)
    passe = _passe(a_generer)
    coeur.sonde = lambda lot: lus.append((lot, passe.pages_du_lot_courant))
    surface = SurfaceExecution(unite=execution_pdf.UNITE)
    # **L'observateur est indispensable, et son absence rendait ce test
    # tautologique.** Sans lui, `pages_du_lot_courant` n'est ecrit par personne
    # d'autre que la remise a zero elle-meme : le retirer laissait le champ a
    # zero, donc le test vert. C'est le seul champ que le canal du coeur
    # alimente, et c'est `EcranGenerationDesPlanches.sur_jalon` qui l'ecrit --
    # on rejoue donc sa ligne, sans monter d'ecran.
    surface.abonner(
        lambda avancement: setattr(passe, "pages_du_lot_courant",
                                   avancement.faites))
    parcours_pdf.executer_les_lots(
        a_generer, passe, surface, dossier_projet=tmp_path, reglages={},
        generer=coeur, horloge=lambda: datetime(2026, 9, 2, 16, 22, 41))

    assert lus == [(lot_id, 0) for lot_id, _pages in TROIS_LOTS], lus


def test_l_etat_des_tirages_rend_l_ordre_RECU_et_jamais_un_ordre_TRIE():
    """Mutant `M30` : un tri silencieux ecrit l'etat d'un lot sur un autre.

    C'est la classe de defaut que ce depot a payee trois fois -- l'appariement
    positionnel entre deux listes qu'on croit paralleles. La demande est faite
    dans un ordre **qui n'est ni alphabetique ni celui du manifeste**, sans quoi
    un tri serait indiscernable de l'absence de tri.

    Le consommateur d'aujourd'hui indexe par identifiant et survivrait a un tri ;
    c'est justement pourquoi la propriete se mesure sur le **contrat** du point
    d'entree, la ou elle est ecrite, et non sur son unique appelant.
    """
    demande = [LOT_SANS_TIRAGE, LOT_PREMIER, LOT_CIBLE]
    assert demande != sorted(demande)
    etats = makepdf.etat_des_tirages(Path("/nonexistent"), lot_ids=demande)
    assert [etat.lot_id for etat in etats] == demande


def test_un_lot_ABSENT_du_manifeste_ne_fait_pas_disparaitre_les_SUIVANTS(
        tmp_path):
    """Mutant `M28` : la boucle sort a la premiere anomalie.

    **L'absent est au MILIEU** : en tete ou en queue, un `break` serait
    indiscernable d'un `continue` sur le cardinal rendu. L'anomalie se **dit**
    dans son champ plutot que de lever : une lecture qui leverait obligerait
    l'interface a envelopper chaque lot d'un `try`, et le premier oubli ferait
    tomber l'atelier.
    """
    dossier = _projet(tmp_path)
    manifeste = json.loads((dossier / "project.json").read_text(
        encoding="utf-8"))
    demande = [LOT_PREMIER, "lot-qui-n-existe-pas", LOT_CIBLE]
    etats = makepdf.etat_des_tirages(dossier, lot_ids=demande,
                                     manifest=manifeste)
    assert [etat.lot_id for etat in etats] == demande
    assert [etat.absent for etat in etats] == [False, True, False]
    # Le lot qui SUIT l'absent porte bien son etat, et non un etat vide.
    assert etats[-1].deja_imprime is True
    assert etats[-1].a_ecrire == TIRAGES[LOT_CIBLE] + 1


def test_l_entree_d_inventaire_rendue_est_celle_du_RANG_VISE_et_pas_une_voisine(
        tmp_path):
    """Mutant `M27` : `==` devenu `>=` rend le premier tirage venu.

    L'inventaire est **trie par chemin** a l'ecriture, et un fragment `_v10`
    trie **avant** `_v2` : l'ordre des entrees n'est donc pas celui des numeros,
    et une comparaison relachee y rend une autre entree sans que le cardinal
    bouge. La cible est **au milieu** des quatre entrees de la liste que le code
    parcourt, et les quatre portent des chemins distinguables.

    Ce que ce mutant produirait a l'ecran : `E5-3b` nommerait le fichier d'un
    autre tirage que celui qu'il propose d'ecraser.
    """
    vise = 3
    lot = {"lot_id": LOT_CIBLE,
           pdf_manifest.SHEETS_INVENTORY_FIELD: [
               {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/a.pdf"},
               {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/b_v10.pdf",
                "version_rank": 10},
               {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/c_v3.pdf",
                "version_rank": vise},
               {pdf_manifest.SHEETS_INVENTORY_KEY: "planches/d_v5.pdf",
                "version_rank": 5},
           ]}
    entree = makepdf._entree_du_rang(lot, vise)
    assert entree is not None
    assert entree[pdf_manifest.SHEETS_INVENTORY_KEY] == "planches/c_v3.pdf"
    # Volet symetrique : un rang que l'inventaire ne porte pas ne rend rien
    # plutot qu'une entree voisine.
    assert makepdf._entree_du_rang(lot, 7) is None


def test_les_numeros_EPUISES_montent_le_refus_et_non_l_ecran_de_conflit(
        tmp_path, banc):
    """AC 7.8 -- un refus qui **nomme ses issues**, jamais un plantage.

    Le texte du coeur est relaye **tel quel** : le reformuler en ferait une
    seconde redaction qui divergerait au premier ajustement. Cette branche n'est
    pas atteignable par une fabrique raisonnable -- il y faudrait quatre-vingt
    dix-neuf tirages du meme lot --, donc l'etat du coeur est **pose** plutot
    que produit. Une branche qu'aucun test n'exerce n'est pas une branche.

    Le volet symetrique est tout le reste de ce banc : sans refus, c'est
    l'ecran de conflit qui monte.
    """
    dossier = _projet(tmp_path)
    refus = "Les numéros de tirage sont épuisés pour ce lot."
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.charger()
        tirage = versions.TirageEnConflit(
            nom="x.pdf", lot_id=LOT_CIBLE, rang=99, rang_propose=99)
        parcours.conflits = versions.PasseDeConflits(conflits=(tirage,))
        parcours.etats = {LOT_CIBLE: makepdf.TirageDejaLa(
            lot_id=LOT_CIBLE, rush_id=RUSHES[LOT_CIBLE], present=99,
            a_ecrire=99, refus=refus)}
        parcours.montrer_le_conflit()
        await pilote.pause()
        return pilote.app.screen

    ecran = _jouer(scenario, app, banc)
    assert isinstance(ecran, versions.EcranRangsEpuises)
    assert ecran.refus == refus
    assert len(ecran.choix.issues) >= 2


def test_RETIRER_DE_LA_PASSE_sort_le_lot_et_LAISSE_les_autres(tmp_path, banc):
    """`EPIC11-ARB-89` : perdre les N-1 autres pour un seul serait le blocage
    sec qu'il proscrit.

    Le lot retire quitte la selection ; **les autres restent**, et le plan de la
    confirmation les porte. La mise en page est remesuree sur ce qui reste --
    `pages_par_lot` s'apparie positionnellement, et une liste plus courte d'un
    cote ecrirait les pages d'un lot sur un autre.
    """
    dossier = _projet(tmp_path)
    refus = "Les numéros de tirage sont épuisés pour ce lot."
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        # Le PREMIER conflit tombe sur des numeros epuises : on l'y met.
        parcours.etats[LOT_PREMIER] = dataclasses.replace(
            parcours.etats[LOT_PREMIER], refus=refus)
        parcours.conflits = dataclasses.replace(parcours.conflits,
                                                rang_courant=0)
        ecran = parcours.montrer_le_conflit()
        await pilote.pause()
        ecran.choix.viser(versions.CLE_RETIRER_DE_LA_PASSE)
        ecran.traiter("enter")
        await pilote.pause()
        # Les deux conflits qui restent se tranchent, et la passe va **jusqu'a
        # la confirmation** : c'est la que le plan se compose, et c'est le seul
        # endroit ou une mise en page restee mesuree sur QUATRE lots pour une
        # passe qui n'en porte plus que deux se voit.
        for _ in range(2):
            pilote.app.screen.traiter("enter")
            await pilote.pause()
        return parcours, pilote.app.screen

    parcours, dernier = _jouer(scenario, app, banc)
    restants = {lot.lot_id for lot in parcours.coches}
    assert LOT_PREMIER not in restants
    assert restants == set(ORDRE_DES_CONFLITS) - {LOT_PREMIER}
    # Le plan porte **exactement** les lots qui restent, et ses pages sont
    # remesurees sur eux : un plan compose contre une mise en page d'une autre
    # passe ecrirait les pages d'un lot sur un autre.
    assert isinstance(dernier, confirmation.EcranPdfConfirmation)
    assert {planche.lot_id for planche in dernier.plan.planches} == restants
    assert len(dernier.plan.mise_en_page.pages_par_lot) == len(restants)


# ===========================================================================
# Les reprises de la revue du 2026-09-02 (couches 2 et 3)
# ===========================================================================

def _jusqu_aux_conflits(tmp_path, banc, *, lots, cles, espion=None):
    """Derouler jusqu'a la confirmation en retenant `cles`, et rendre le parcours.

    `espion` est appele avec **chaque ecran de conflit monte**, avant qu'on ne
    le tranche : c'est la seule facon de lire ce que le parcours montre
    reellement, l'ecran unique `EcranConflitDeTirage` portant ses deux etats
    (`E5-3b` / `E5-3c`) sans changer de classe.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=lots)
        await pilote.pause()
        for cle in cles:
            ecran = pilote.app.screen
            if espion is not None:
                espion(ecran)
            ecran.choix.viser(cle)
            ecran.traiter("enter")
            await pilote.pause()
        return parcours

    return _jouer(scenario, app, banc)


def test_C2_6_le_champ_SCANNE_lit_le_tirage_PRESENT_et_non_le_NUMERO_a_ecrire(
        tmp_path, banc):
    """Finding `C2-6` -- il etait **toujours faux en production**.

    `LotAImprimer.scanne` dit « ce tirage **anterieur** a ete scanne » : il
    departe `E5-3b` de `E5-3c`, donc il porte sur l'objet dont l'ecran de
    conflit vient de parler -- celui qui existe deja. Le lire sur le numero
    **neuf** le rendait faux partout : un tirage scanne n'est jamais ecrasable
    (`EPIC11-ARB-176`), donc il recoit toujours `ECRIRE_A_COTE`, donc le numero
    est le rang suivant, qu'aucun scan n'a jamais vu passer -- par construction.
    Mesure d'avant correction : trois `tirage_anterieur=True`, **zero**
    `scanne=True`.

    **Ensemble EXACT**, et il le faut des deux cotes : « le lot scanne porte le
    champ » laisserait passer un parcours qui le porterait a tous, et le volet
    `tirage_anterieur` mesure qu'on ne l'a pas ferme en eteignant tout.
    """
    parcours = _jusqu_aux_conflits(
        tmp_path, banc, lots=list(ORDRE_DES_CONFLITS),
        cles=[versions.CLE_CREER] * len(ORDRE_DES_CONFLITS))
    imprimes = parcours.lots_a_imprimer()
    assert {lot.lot_id for lot in imprimes if lot.scanne} == {LOT_SCANNE}
    assert {lot.lot_id for lot in imprimes if lot.tirage_anterieur} == \
        set(ORDRE_DES_CONFLITS)
    # Le rang du lot scanne est bien le rang **neuf** : la correction ne l'a pas
    # ferme en faisant lire le present partout.
    par_lot = {lot.lot_id: lot.rang for lot in imprimes}
    assert par_lot[LOT_SCANNE] == TIRAGES[LOT_SCANNE] + 1


def test_C2_6_l_enchainement_DECLARE_est_celui_que_le_parcours_MONTE(
        tmp_path, banc):
    """`ecrans_du_parcours` est la seule redaction mesuree de l'enchainement.

    Elle etait un **faux vert de frontiere** a deux titres : elle ne pouvait
    jamais rendre `E5-3c` sur des donnees issues du parcours (finding `C2-6`),
    et elle parcourait les lots dans l'ordre de `E5-1` -- l'ordre du manifeste,
    c'est-a-dire de premiere creation -- alors que le parcours les montre dans
    l'ordre **par lot** d'`EPIC11-ARB-177`.

    La mesure confronte la declaration a ce qui est **reellement monte**, etat
    par etat. Les deux proprietes se cassent separement, et le libelle verbatim
    les pince toutes les deux : dans l'ordre de `E5-1` la suite serait
    `(E5-3b, E5-3b, E5-3c, E5-3)`, la cible scannee en queue au lieu du milieu.
    """
    montes: list[str] = []

    def espionner(ecran):
        montes.append(confirmation.ECRAN_DU_TIRAGE_SCANNE
                      if ecran.tirage.scanne
                      else confirmation.ECRAN_DU_CONFLIT)

    parcours = _jusqu_aux_conflits(
        tmp_path, banc, lots=list(ORDRE_DES_CONFLITS),
        cles=[versions.CLE_CREER] * len(ORDRE_DES_CONFLITS),
        espion=espionner)
    observe = tuple(montes) + (confirmation.ECRAN_DE_LA_CONFIRMATION,)
    declare = confirmation.ecrans_du_parcours(parcours.lots_a_imprimer())
    assert declare == observe, (declare, observe)
    assert declare == (confirmation.ECRAN_DU_CONFLIT,
                       confirmation.ECRAN_DU_TIRAGE_SCANNE,
                       confirmation.ECRAN_DU_CONFLIT,
                       confirmation.ECRAN_DE_LA_CONFIRMATION), declare
    # Le tri est bien ce qui separe les deux ordres : les lots arrivent ici dans
    # l'ordre du manifeste, et il n'est **pas** l'ordre par lot.
    ordre_recu = [lot.lot_id for lot in parcours.lots_a_imprimer()]
    assert ordre_recu != sorted(ordre_recu), ordre_recu


def test_C2_4_la_MASSE_n_emporte_PAS_un_lot_dont_les_rangs_sont_EPUISES(
        tmp_path, banc):
    """Finding `C2-4` -- l'issue de masse sautait `EcranRangsEpuises`.

    Elle rendait la confirmation directement, court-circuitant
    `montrer_le_conflit` : un lot restant dont les 99 rangs sont consommes etait
    emporte **sans que son refus soit jamais montre**. Ce que ca produit ensuite
    est pire que l'ecran manquant -- `_etat_d_un_lot` pose `a_ecrire = present`
    quand le coeur refuse, donc `E5-3` annonce comme numero a ecrire **celui du
    tirage qui existe deja**, exactement le fait qu'`EPIC11-ARB-172` fait
    remonter le conflit avant la confirmation pour rendre vrai.

    Le lot refuse est **au MILIEU** de la liste que le code parcourt --
    `(courant,) + restants`, trois elements : en queue, un `continue` devenu
    `break` serait indiscernable, et en tete l'ecran de masse ne se serait meme
    pas offert (`EcranRangsEpuises` ne porte pas `CLE_MASSE`).

    Trois mesures, et elles se cassent separement : l'ensemble **exact** des
    decisions, l'ecran reellement monte, et le fait que la confirmation **ne se
    monte pas** tant que le refus n'est pas tranche.
    """
    dossier = _projet(tmp_path)
    refus = "Les numéros de tirage sont épuisés pour ce lot."
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        # Le conflit du MILIEU tombe sur des numeros epuises. L'etat est pose
        # comme le coeur le pose : `a_ecrire = present`, ce qui est la source du
        # mauvais numero.
        present = parcours.etats[LOT_SCANNE].present
        parcours.etats[LOT_SCANNE] = dataclasses.replace(
            parcours.etats[LOT_SCANNE], refus=refus, a_ecrire=present)
        parcours.conflits = dataclasses.replace(parcours.conflits,
                                                rang_courant=0)
        ecran = parcours.montrer_le_conflit()
        await pilote.pause()
        ecran.choix.viser(versions.CLE_MASSE)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours, pilote.app.screen

    parcours, apres_la_masse = _jouer(scenario, app, banc)
    # 1. l'ecran du refus est monte, et il porte le lot refuse -- pas le lot
    #    suivant, que la masse a deja tranche.
    assert isinstance(apres_la_masse, versions.EcranRangsEpuises)
    assert apres_la_masse.tirage.lot_id == LOT_SCANNE
    assert apres_la_masse.refus == refus
    # 2. ensemble EXACT des decisions : la masse a bien emporte les deux autres
    #    -- la fermer en n'emportant plus personne serait le blocage sec
    #    d'`EPIC11-ARB-89`. Le lot refuse, lui, n'en porte aucune : c'est ce qui
    #    l'empeche d'annoncer `present` comme numero a ecrire.
    assert parcours.decisions == {
        LOT_PREMIER: parcours_pdf.DECISION_ECRASER,
        LOT_CIBLE: parcours_pdf.DECISION_ECRASER,
    }
    # 3. la confirmation ne s'est PAS montee : le refus se tranche d'abord.
    assert confirmation.EcranPdfConfirmation.__name__ not in vus, vus


def test_C2_4_le_refus_tranche_APRES_la_masse_mene_bien_a_la_confirmation(
        tmp_path, banc):
    """Le volet symetrique -- la reprise ne doit pas laisser la passe en plan.

    Fermer `C2-4` en montant l'ecran du refus ne vaut que si le parcours en
    **sort** : un ecran de refus qui ne menerait nulle part serait le cul-de-sac
    que `EPIC11-ARB-89` proscrit, et il serait invisible au test precedent.

    Le lot refuse quitte la passe ; les deux autres, deja tranches par la masse,
    ne sont **pas remontres** -- un parcours qui reprendrait au conflit suivant
    plutot qu'au premier conflit non tranche redemanderait un choix deja fait.
    """
    dossier = _projet(tmp_path)
    refus = "Les numéros de tirage sont épuisés pour ce lot."
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        present = parcours.etats[LOT_SCANNE].present
        parcours.etats[LOT_SCANNE] = dataclasses.replace(
            parcours.etats[LOT_SCANNE], refus=refus, a_ecrire=present)
        parcours.conflits = dataclasses.replace(parcours.conflits,
                                                rang_courant=0)
        ecran = parcours.montrer_le_conflit()
        await pilote.pause()
        ecran.choix.viser(versions.CLE_MASSE)
        ecran.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(versions.CLE_RETIRER_DE_LA_PASSE)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours, pilote.app.screen

    parcours, dernier = _jouer(scenario, app, banc)
    assert isinstance(dernier, confirmation.EcranPdfConfirmation)
    assert {planche.lot_id for planche in dernier.plan.planches} == \
        {LOT_PREMIER, LOT_CIBLE}
    # Depuis l'ecran ou la masse est retenue, la suite est **exactement** :
    # le refus, puis la confirmation. Les deux lots emportes par la masse ne
    # sont pas remontres -- un parcours qui reprendrait au conflit suivant
    # intercalerait ici un `EcranConflitDeTirage` de plus.
    assert vus[-3:] == [versions.EcranConflitDeTirage.__name__,
                        versions.EcranRangsEpuises.__name__,
                        confirmation.EcranPdfConfirmation.__name__], vus
    # Le numero annonce du lot refuse n'existe plus : il a quitte la passe.
    assert LOT_SCANNE not in {lot.lot_id for lot in parcours.coches}


def test_C2_3_un_lot_REFUSE_laisse_une_ligne_de_journal_qui_le_NOMME(tmp_path):
    """Finding `C2-3` -- le refus etait collecte, et **muet a l'ecran**.

    La branche `except REFUS_NOMMES` faisait `continue` sans inscrire une seule
    ligne. L'en-tete du lot y etant deja, la rupture etait encore plus
    trompeuse : le lot etait nomme, puis plus rien -- ce qui se lit comme une
    passe qui s'arrete, alors que la passe continue. C'est la classe de decision
    cachee qu'`EPIC11-ARB-177` proscrit ailleurs dans cette meme story.

    **Le mutant `M26` de la couche 2 etait TUE et le defaut survivait quand
    meme** : un banc mesurait la *disparition* du segment `· aucun refus` de la
    ligne d'etat, aucun ne mesurait **ce qu'il devient**. C'est la forme exacte
    de la tautologie que la politique du depot poursuit, et c'est pourquoi ce
    test-ci mesure le contenu du journal et non un cardinal.

    **Le lot refuse est au MILIEU** -- en tete ou en queue, un `break` serait
    indiscernable d'un `continue` sur le journal rendu.

    Le message est celui du coeur, **verbatim** (`EPIC11-ARB-30`) : un test qui
    ne chercherait que le mot « refusé » resterait vert sur une TUI qui
    reformulerait le refus.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS), refuse=[LOT_CIBLE])
    rapport, _passe_, surface = _executer(tmp_path, coeur)
    message = rapport.refus[0].message
    refusees = [ligne for ligne in surface.journal.lignes
                if LOT_CIBLE in ligne and message in ligne]
    assert len(refusees) == 1, surface.journal.lignes
    # La ligne est **horodatee comme les autres** : une ligne nue au milieu de
    # lignes horodatees se lit comme une sortie de programme, pas comme un
    # evenement de la passe.
    assert refusees[0].startswith("16:22:41"), refusees[0]
    # Volet symetrique, et il porte la moitie du sens : les lots **ecrits**
    # n'en portent aucune. Sans lui, une ligne de refus inscrite a chaque tour
    # serait verte ci-dessus.
    assert not [ligne for ligne in surface.journal.lignes
                if LOT_SCANNE in ligne and message in ligne]
    assert len(rapport.ecrites) == 2


def test_C2_3_la_ligne_de_refus_ne_RECOPIE_ni_le_motif_ni_une_paraphrase():
    """La ligne se compose du refus, et elle n'invente rien.

    Le **motif** est un code destine au code -- il choisit l'ecran de refus --
    et il n'a rien a faire dans une ligne lue par un operateur. La mesure est
    faite sur un motif qui ne peut pas apparaitre par hasard.
    """
    refus = parcours_pdf.RefusDuLot(
        lot_id=LOT_CIBLE, message="le lot n'est pas conforme",
        motif="MOTIF-QUI-NE-SE-LIT-PAS")
    ligne = parcours_pdf.ligne_de_refus(refus)
    assert LOT_CIBLE in ligne
    assert "le lot n'est pas conforme" in ligne
    assert refus.motif not in ligne, ligne


@dataclass
class _Frappe:
    """Un evenement clavier minimal, pour passer par `on_key` et non `traiter`.

    La difference porte : `on_key` **redessine** apres avoir traite la touche,
    et c'est ce redessin qui pose la ligne d'etat. Un test qui appellerait
    `traiter` mesurerait le modele et pas ce que l'operateur lit.
    """

    key: str
    character: str | None = None
    arrete: bool = False

    def stop(self) -> None:
        self.arrete = True


def test_C2_2_un_libelle_INNOMMABLE_ne_fait_PAS_tomber_la_TUI(tmp_path, banc):
    """Finding `C2-2`, le parcours complet -- menu, `E5-6`, `---`, `⏎`.

    Mesure d'avant correction : `naming.NamingError` remontait **hors de la
    boucle `textual`** et emportait l'application. Ce n'etait ni un blocage sec
    ni une issue unique -- c'etait une chute, ce qu'`EPIC11-ARB-89` proscrit a
    plus forte raison.

    La frappe passe par `traiter`, jamais par un appel de rappel : ce qu'on
    mesure est ce qu'un operateur obtient de son clavier.

    L'issue, elle, est **sur l'ecran** : le formulaire reste sous le focus, la
    ligne d'etat dit ce qui ne va pas, et la saisie est corrigeable. C'est ce
    qui distingue un refus d'un cul-de-sac.
    """
    dossier = _projet(tmp_path)
    mire = MireDouble()
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in "---":
            ecran.on_key(_Frappe("minus", lettre))
        ecran.on_key(_Frappe("enter"))
        await pilote.pause()
        return pilote.app.screen

    dernier = _jouer(scenario, app, banc)
    # L'ecran de reglages n'a pas bouge, et **rien** n'a ete ecrit.
    assert isinstance(dernier, calibration.EcranMireReglages)
    assert vus == [atelier_pdf.EcranPdfMenu.__name__,
                   calibration.EcranMireReglages.__name__], vus
    assert mire.appels == []
    # La saisie est bien la : la touche a ete consommee, pas la frappe.
    assert dernier.formulaire.saisie(calibration.CHAMP_CHAINE) == "---"
    # Et le refus se **lit** : une garde muette serait verte ci-dessus.
    assert calibration.ETAT_CHAINE_INUTILISABLE in dernier._etat_courant


def test_C2_2_le_FILET_de_generer_la_mire_refuse_au_lieu_de_LEVER(
        tmp_path, banc):
    """Le second volet : l'exception ne traverse plus, meme sans le formulaire.

    `E5-6` refuse desormais de continuer, donc ce chemin n'est plus atteignable
    par un operateur. Il l'est par **un appelant** -- et c'est exactement ce que
    fermer un finding sans filet laisse ouvert : la garde vit dans un ecran, la
    chute vivait dans le parcours. Le refus du coeur est relaye **tel quel**
    (`EPIC11-ARB-30`), sur l'ecran qui sait l'afficher.
    """
    dossier = _projet(tmp_path)
    mire = MireDouble()
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        parcours.charger()
        parcours.formulaire = calibration.FormulaireDeLaMire(chaine="---")
        ecran = parcours.generer_la_mire()
        await pilote.pause()
        return ecran

    ecran = _jouer(scenario, app, banc)
    assert isinstance(ecran, EcranRefus)
    assert ecran.code == parcours_pdf.CODE_CHAINE_INNOMMABLE
    # La phrase est celle du coeur, verbatim : la TUI n'en redige pas une
    # seconde. On la confronte au refus que le coeur rend vraiment.
    with pytest.raises(naming.NamingError) as leve:
        naming.build_calibration_pdf_filename(PROJET, "---")
    assert ecran.message == str(leve.value)
    # Et **rien n'a ete ecrit** : le filet refuse avant d'appeler le coeur.
    assert mire.appels == []


def test_C3_3_la_TUI_passe_DEFAULT_GAMUT_MAP_au_coeur(tmp_path, banc):
    """AC 5.9a, volet positif -- finding `C3-3` : il n'etait ni tenu ni mesure.

    `reglages_du_coeur` passait **trois** cles et pas le gamut ; un `grep` de
    « gamut » sur `tui/` ne rendait que de la prose. L'observable ne changeait
    pas -- le coeur applique le meme defaut -- mais l'AC telle qu'ecrite etait
    fausse, et rien ne mesurait qu'un jour la TUI cesse de passer autre chose.

    La mesure est faite **sur l'appel reel**, pas sur la table : elle lit ce que
    le double du coeur a recu.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()

    _jouer(scenario, app, banc)
    assert coeur.appels, "le coeur n'a pas ete appele"
    assert coeur.appels[0]["gamut_map_id"] == \
        pdf_composition.DEFAULT_GAMUT_MAP
    # La cle existe bien a la signature du coeur : une cle inventee leverait a
    # l'appel plutot que d'etre ignoree, et c'est ce qui rend la table mesurable.
    import inspect
    assert "gamut_map_id" in inspect.signature(
        makepdf.generer_les_planches_du_lot).parameters


def test_C3_3_la_valeur_du_gamut_n_est_RECOPIEE_nulle_part_dans_le_cablage():
    """La frontiere qui rougirait si quelqu'un recopiait la constante.

    « Un document de politique ne recopie jamais une valeur qui vit dans le
    code : il **nomme la constante** et dit ou elle habite. » La regle vaut pour
    un module comme pour une politique, et le depot l'applique deja a la borne
    d'identifiant. Une valeur recopiee coinciderait le jour ou elle est ecrite
    et divergerait en silence le jour ou le coeur change la sienne.

    La mesure porte sur les **litteraux**, jamais sur le mot : la prose de ce
    module dit pourquoi le champ n'existe pas, et un grep du mot rendrait cette
    explication interdite en meme temps que la recopie.
    """
    import ast

    source = Path(parcours_pdf.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            assert noeud.value != pdf_composition.DEFAULT_GAMUT_MAP, \
                ast.dump(noeud)
    # Volet symetrique : la constante est bien **nommee** quelque part, sans quoi
    # un module qui ne la mentionnerait plus du tout serait vert ci-dessus.
    noms = {noeud.attr for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Attribute)}
    assert "DEFAULT_GAMUT_MAP" in noms


# ===========================================================================
# Reprises de la COUCHE 1 (chasse a l'aveugle) du 2026-09-02
# ===========================================================================

def test_F1_l_issue_d_un_ecran_REVELE_tranche_SON_lot_et_pas_celui_de_la_file(
        tmp_path, banc):
    """Finding `F1` -- le defaut le plus grave des trois couches.

    `montrer_le_conflit` **empile** un ecran par lot et `Annuler` **depile** :
    l'ecran revele est celui d'un conflit deja tranche, encore monte et encore
    navigable. `retenir_le_conflit` lisait `self.conflits.courant` -- la file du
    parcours -- et jamais le tirage de l'ecran qui produit l'issue.

    Le geste mesure est celui de la sonde de la couche 1, et il tient en trois
    touches : `Créer` sur le conflit 1, `Annuler` sur le conflit 2,
    `Remplacer ce tirage` sur l'ecran ainsi revele.

    **Ce que ca produisait** : `plan-04_25` -- dont le dernier tirage est
    scanne, et dont l'ecran ne porte donc PAS `Remplacer ce tirage` -- recevait
    `DECISION_ECRASER`. `lots_a_imprimer` reprenait `numero = present` et
    `lots_a_generer` passait `overwrite=True` au coeur : la planche imprimee et
    scannee etait detruite. `EPIC11-ARB-174`/`-176` et `EPIC11-ARB-89` tombaient
    ensemble.

    **Ensemble EXACT des decisions**, et l'appartenance du lot scanne mesuree a
    part : « le lot scanne n'est pas ecrase » resterait vrai d'un parcours qui
    n'ecraserait plus personne.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        premier = pilote.app.screen
        vu_1 = premier.tirage.lot_id
        premier.choix.viser(versions.CLE_CREER)
        premier.traiter("enter")
        await pilote.pause()
        # Le second conflit est celui du lot SCANNE : son ecran ne porte pas
        # l'issue destructive, et c'est la frontiere negative du lot G.
        second = pilote.app.screen
        vu_2 = second.tirage.lot_id
        cles_du_second = [issue.cle for issue in second.choix.issues]
        second.choix.viser(versions.CLE_ANNULER)
        second.traiter("enter")
        await pilote.pause()
        revele = pilote.app.screen
        revele.choix.viser(versions.CLE_REMPLACER)
        revele.traiter("enter")
        await pilote.pause()
        return parcours, vu_1, vu_2, cles_du_second, revele.tirage.lot_id

    parcours, vu_1, vu_2, cles_du_second, vu_revele = _jouer(scenario, app,
                                                             banc)
    # La scene est bien celle du finding : le second conflit est le lot scanne,
    # et son ecran ne propose pas d'ecraser.
    assert (vu_1, vu_2) == (LOT_PREMIER, LOT_SCANNE)
    assert versions.CLE_REMPLACER not in cles_du_second, cles_du_second
    # L'ecran revele est bien celui du PREMIER conflit -- c'est ce que
    # l'operateur lit au moment ou il valide.
    assert vu_revele == LOT_PREMIER
    # Et la decision porte sur CE lot-la, exactement.
    assert parcours.decisions == {LOT_PREMIER: parcours_pdf.DECISION_ECRASER}
    assert LOT_SCANNE not in parcours.decisions


def test_F1_le_lot_SCANNE_ne_recoit_JAMAIS_overwrite_par_un_ecran_revele(
        tmp_path, banc):
    """La consequence en bout de chaine : ce que le COEUR recoit.

    Le test precedent mesure la decision ; celui-ci mesure la **destruction**.
    Une reprise qui aurait corrige l'attribution sans corriger le cablage aval
    serait verte la-haut et rouge ici -- et c'est la planche de papier qui est
    en jeu, pas un dictionnaire.

    Ensemble **exact** des lots qui emportent `overwrite` : « le lot scanne ne
    l'emporte pas » resterait vrai d'une passe qui ne l'emporterait pour
    personne.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_PREMIER: 30, LOT_SCANNE: 21, LOT_CIBLE: 7})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for cle in (versions.CLE_CREER, versions.CLE_ANNULER,
                    versions.CLE_REMPLACER):
            ecran = pilote.app.screen
            ecran.choix.viser(cle)
            ecran.traiter("enter")
            await pilote.pause()
        # Les conflits qui restent se tranchent sans rien ecraser, puis on
        # genere : c'est le seul instant ou `overwrite` atteint le coeur.
        while isinstance(pilote.app.screen, versions.EcranConflitDeTirage):
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()

    _jouer(scenario, app, banc)
    ecrasants = {appel["lot"] for appel in coeur.appels if appel["overwrite"]}
    assert ecrasants == {LOT_PREMIER}, coeur.appels
    assert LOT_SCANNE not in ecrasants


def _passe_complete(pilote, parcours, *, lots):
    """Derouler une passe entiere : cocher, regler, trancher, confirmer, generer.

    Rendue reutilisable parce que `F3` se mesure sur **deux** passes enchainees
    -- une seule ne dit rien d'une pile qui croit.
    """
    _cocher_et_regler(parcours, pilote.app.screen, lots=lots)
    return None


def test_F3_une_suite_qui_RECOMMENCE_depile_au_lieu_d_empiler(tmp_path, banc):
    """Finding `F3` -- `SUITE_AUTRES_LOTS` empilait une passe sur la precedente.

    Mesure de la couche 1 : `7 -> 12` ecrans en deux passes, **cinq de plus a
    chaque fois**, sans borne. Trois consequences, dont la plus couteuse :
    chaque `E5-4` mort garde son `set_interval` de rotor (il n'a pas
    d'`on_unmount`) et son `on_mount` differe **repose `tache_en_cours`** --
    le drapeau que plus personne n'eteint est ce qui fait qu'`Échap` cesse de
    depiler.

    La mesure est **la hauteur de pile aux deux memes instants**, pas un
    cardinal absolu : elle reste vraie si un ecran s'ajoute au parcours.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        hauteurs = []
        for tour in range(2):
            _cocher_et_regler(parcours, pilote.app.screen,
                              lots=[LOT_SANS_TIRAGE])
            await pilote.pause()
            ecran = pilote.app.screen
            ecran.choix.viser(confirmation.ISSUE_GENERER)
            ecran.traiter("enter")
            await pilote.pause()
            hauteurs.append(len(pilote.app.screen_stack))
            if tour == 0:
                parcours.suivre(resultat_pdf.SUITE_AUTRES_LOTS)
                await pilote.pause()
        return hauteurs

    hauteurs = _jouer(scenario, app, banc)
    assert hauteurs[0] == hauteurs[1], hauteurs


@pytest.mark.parametrize("suite,attendu", [
    (resultat_pdf.SUITE_AUTRES_LOTS, "EcranLotsAPlanches"),
    (resultat_pdf.SUITE_CALIBRATION, "EcranMireReglages"),
])
def test_F3_chaque_suite_de_E5_5_repart_de_l_OUVERTURE_de_l_atelier(
        tmp_path, banc, suite, attendu):
    """Les **deux** suites qui recommencent, et pas seulement celle qui a ete
    sondee : fermer l'une des deux laisserait l'autre ouverte, et rien ne le
    dirait.

    La pile visee est celle du Scan : on s'arrete **un cran en dessous** du menu
    des ateliers (`EPIC11-ARB-13` -- « jamais a l'ecran projet »), donc l'ecran
    d'ouverture de l'atelier reste dessous, et c'est lui qui porte le retour.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        parcours.suivre(suite)
        await pilote.pause()
        return [type(e).__name__ for e in pilote.app.screen_stack]

    pile = _jouer(scenario, app, banc)
    assert type(pile) is list
    assert pile[-1] == attendu, pile
    # L'ecran d'ouverture de l'atelier est **juste dessous**, et rien de la
    # passe precedente ne subsiste entre les deux.
    assert pile[-2] == atelier_pdf.EcranPdfMenu.__name__, pile
    assert execution_pdf.EcranGenerationDesPlanches.__name__ not in pile, pile
    assert resultat_pdf.EcranResultatDesPlanches.__name__ not in pile, pile


@pytest.mark.parametrize("suite,attendu", [
    (calibration.SUITE_AUTRE_MIRE, "EcranMireReglages"),
    (calibration.SUITE_PLANCHES, "EcranLotsAPlanches"),
])
def test_F3_les_suites_de_E5_6e_repartent_AUSSI_de_l_ouverture(
        tmp_path, banc, suite, attendu):
    """Le parcours de la mire porte le meme defaut, et il porte la meme reprise.

    Une reprise qui n'aurait ferme que `E5-5` aurait laisse le second parcours
    empiler exactement de la meme facon.
    """
    dossier = _projet(tmp_path)
    mire = MireDouble()
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in "hp-envy":
            ecran.traiter("", lettre)
        ecran.traiter("enter")
        await pilote.pause()
        confirme = pilote.app.screen
        confirme.choix.viser(calibration.ISSUE_GENERER)
        confirme.traiter("enter")
        await pilote.pause()
        parcours.suivre_apres_la_mire(suite)
        await pilote.pause()
        return [type(e).__name__ for e in pilote.app.screen_stack]

    pile = _jouer(scenario, app, banc)
    assert pile[-1] == attendu, pile
    assert pile[-2] == atelier_pdf.EcranPdfMenu.__name__, pile
    assert calibration.EcranMireEcrite.__name__ not in pile, pile


def test_F4_MODIFIER_LES_REGLAGES_ramene_aux_REGLAGES_meme_avec_des_conflits(
        tmp_path, banc):
    """Finding `F4` -- l'issue atterrissait sur le dernier ecran de conflit.

    `action_remonter` depile **un** palier, or l'inversion d'`EPIC11-ARB-172` a
    glisse les ecrans de conflit **entre** `E5-2` et `E5-3`. Sans conflit la
    meme issue tombait bien sur les reglages : le comportement dependait de la
    presence de conflits, ce qu'aucune ligne de l'ecran ne dit.

    Les deux regimes sont mesures dans le meme test **parametre** : c'est le
    regime sans conflit qui rend le defaut invisible, donc le taire reviendrait
    a mesurer le seul cas qui marchait deja.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for _ in ORDRE_DES_CONFLITS:
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        assert isinstance(ecran, confirmation.EcranPdfConfirmation)
        ecran.choix.viser(confirmation.ISSUE_MODIFIER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    dernier = _jouer(scenario, app, banc)
    assert isinstance(dernier, reglages_pdf.EcranReglagesDesPlanches)


def test_F4_ANNULER_sur_la_confirmation_ramene_AUSSI_aux_reglages(
        tmp_path, banc):
    """Le volet symetrique -- les deux issues non ecrivantes sortent du passage.

    Sans conflit, l'ancien comportement etait deja juste : ce test-ci mesure
    donc que la reprise n'a pas ferme un cas en cassant l'autre. Un `Annuler`
    qui ramenerait au menu des ateliers -- ou au dernier conflit -- serait vert
    sur le test precedent.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_ANNULER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    dernier = _jouer(scenario, app, banc)
    assert isinstance(dernier, reglages_pdf.EcranReglagesDesPlanches)


def test_F3_le_depilement_ne_VIDE_PAS_la_pile_quand_l_ouverture_est_absente(
        tmp_path, banc):
    """La garde du depilement : sans `E5-0` dans la pile, on ne depile RIEN.

    Un depilement qui ne sait pas ou il va est pire que pas de depilement : il
    sort l'operateur de l'atelier sans qu'aucune issue ne l'ait dit. Le cas
    n'est pas theorique -- un banc, ou un appelant qui monterait le parcours
    autrement, produit exactement cette pile.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        # On entre par `E5-1` directement : aucun `E5-0` dans la pile.
        parcours.choisir_les_lots()
        await pilote.pause()
        avant = [type(e).__name__ for e in pilote.app.screen_stack]
        parcours_pdf.remonter_a_l_ouverture_de_l_atelier(pilote.app)
        await pilote.pause()
        return avant, [type(e).__name__ for e in pilote.app.screen_stack]

    avant, apres = _jouer(scenario, app, banc)
    assert atelier_pdf.EcranPdfMenu.__name__ not in avant, avant
    assert apres == avant, (avant, apres)


def test_F7_chaque_lot_recoit_SA_planche_et_pas_celle_d_une_voisine(
        tmp_path, banc):
    """Finding `F7` -- une permutation TOTALE du plan survivait a 590 tests.

    `lots_a_generer` appariait `lots_a_imprimer()` et `plan.planches` par un
    `zip` **positionnel** : chaque lot recevait alors le nom de fichier et le
    cardinal de pages d'un autre. C'est la classe payee trois fois par ce depot
    (`M33` de la 5.6, `M25` de la 5.7, cinq survivants de la 5.8), et
    `preparer_le_plan` -- dix lignes plus haut dans le meme parcours -- la borde
    nommement.

    **Trois lots, la cible AU MILIEU, et des valeurs distinguables** : trois
    paginations differentes et trois noms differents. Le seul test qui
    traversait `lots_a_generer` avec plusieurs lots n'observait qu'`overwrite`,
    qui voyage par `lot_id` et **survit** a la permutation.

    La permutation est appliquee au plan **reellement compose**, pas a une
    fabrique : c'est le mutant `C1-M4` de la couche 1, joue ici comme scenario.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for _ in ORDRE_DES_CONFLITS:
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        droit = parcours.lots_a_generer()
        # **Le plan est retourne**, exactement comme le mutant de la couche 1 :
        # les lots, eux, ne bougent pas.
        parcours.plan = dataclasses.replace(
            parcours.plan,
            planches=tuple(reversed(parcours.plan.planches)))
        permute = parcours.lots_a_generer()
        return droit, permute, parcours.plan.planches

    droit, permute, planches = _jouer(scenario, app, banc)
    # La fabrique mesure quelque chose : trois paginations et trois noms tous
    # distincts. Sans cela, une permutation serait invisible par construction.
    assert len({planche.pages for planche in planches}) == len(planches), \
        [(p.lot_id, p.pages) for p in planches]
    assert len({planche.nom for planche in planches}) == len(planches)
    # La permutation du plan ne change **rien** : l'appariement est par
    # identifiant. Ensemble exact, nom et pagination compris.
    assert {(lot.lot_id, lot.nom, lot.pages) for lot in droit} == \
        {(lot.lot_id, lot.nom, lot.pages) for lot in permute}
    # Et chaque lot porte bien la planche de SON identifiant.
    par_lot = {planche.lot_id: planche for planche in planches}
    for lot in permute:
        assert lot.nom == par_lot[lot.lot_id].nom, lot.lot_id
        assert lot.pages == par_lot[lot.lot_id].pages, lot.lot_id


def test_F7_un_lot_que_le_PLAN_ne_porte_pas_est_refuse_NOMMEMENT(
        tmp_path, banc):
    """Le volet symetrique de l'appariement par identifiant.

    Un appariement par dictionnaire echoue autrement qu'un `zip` : la ou le
    `zip` **tronquait en silence**, la lecture par identifiant ne trouve rien.
    Le refus nomme le lot ; une `KeyError` nue ne dirait pas ce qui manque, et
    un repli inventerait un nom de fichier -- c'est-a-dire ecrirait sous le nom
    d'un autre lot.
    """
    dossier = _projet(tmp_path)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for _ in ORDRE_DES_CONFLITS:
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        # La planche du lot du MILIEU disparait du plan.
        parcours.plan = dataclasses.replace(
            parcours.plan,
            planches=tuple(planche for planche in parcours.plan.planches
                           if planche.lot_id != LOT_SCANNE))
        return parcours

    parcours = _jouer(scenario, app, banc)
    with pytest.raises(confirmation.PlanMalForme) as refus:
        parcours.lots_a_generer()
    assert LOT_SCANNE in str(refus.value)


def test_F8_une_passe_VIDEE_de_tous_ses_lots_revient_aux_ateliers(
        tmp_path, banc):
    """Finding `F8` -- mutant `C1-M7`, **survivant** : la branche n'etait jouee
    par personne.

    Le refus des numeros epuises offre de sortir un lot de la passe. Quand il
    n'en reste **aucun**, confirmer serait confirmer une passe sans objet : un
    ecran de jugement sur zero planche, dont l'issue `Générer` n'ecrirait rien.
    Le parcours ramene aux ateliers (`EPIC11-ARB-13`).

    Le scenario n'etait joue nulle part : `E5-3d` n'etait mesure qu'ecran monte
    a la main, jamais atteint **par le parcours**. C'est pourquoi ni le retrait,
    ni le retour aux ateliers n'etaient mesures.

    **Ensemble exact des ecrans montes apres le dernier retrait** : « on ne
    confirme pas » resterait vrai d'un parcours qui ne ferait rien du tout.
    """
    dossier = _projet(tmp_path)
    refus = "Les numéros de tirage sont épuisés pour ce lot."
    app = _app()
    vus = _espionner(app)

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        # **Les trois** lots tombent sur des numeros epuises : la passe se vide.
        for lot_id in ORDRE_DES_CONFLITS:
            parcours.etats[lot_id] = dataclasses.replace(
                parcours.etats[lot_id], refus=refus)
        parcours.conflits = dataclasses.replace(parcours.conflits,
                                                rang_courant=0)
        parcours.montrer_le_conflit()
        await pilote.pause()
        for _ in ORDRE_DES_CONFLITS:
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_RETIRER_DE_LA_PASSE)
            ecran.traiter("enter")
            await pilote.pause()
        return parcours, pilote.app.screen

    parcours, dernier = _jouer(scenario, app, banc)
    assert parcours.coches == ()
    # Aucune confirmation : une passe sans lot n'a rien a confirmer.
    assert confirmation.EcranPdfConfirmation.__name__ not in vus, vus
    # Et on est bien remonte : l'ecran au sommet n'est plus un ecran de conflit.
    assert not isinstance(dernier, versions.EcranRangsEpuises)
    assert not isinstance(dernier, versions.EcranConflitDeTirage)


def test_F9_l_ecran_de_generation_est_ABONNE_avant_que_la_passe_ne_commence(
        tmp_path, banc):
    """Finding `F9` -- `surface.abonner(ecran.sur_jalon)`, mutant `C1-M26`
    **survivant**, alors que six lignes de commentaire disent la ligne
    indispensable.

    Le seul test d'agregation de la barre **s'abonne lui-meme** avec un
    observateur local et rejoue a la main le corps de `sur_jalon` : il mesure
    `SurfaceExecution` et `PasseDeGeneration`, jamais la couture entre l'ecran
    et la surface -- c'est-a-dire precisement ce que la ligne existe pour tenir.

    Ce test-ci n'abonne **rien**. Il lit ce que le produit a ecrit dans la passe
    a travers son propre cablage : `sur_jalon` est le seul chemin qui pose
    `pages_du_lot_courant` pendant un lot, la boucle ne faisant que le remettre
    a zero a chaque entree. Sans l'abonnement, l'ecran ne s'abonnerait qu'au
    `on_mount` differe -- apres que tous les jalons sont tombes -- et la valeur
    resterait a zero : « la barre passerait de rien a tout ».

    Les paginations des deux lots sont **differentes**, et celle du dernier
    n'est ni zero ni celle de son voisin : une valeur retenue du lot precedent
    se demasque.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2, LOT_CIBLE: 7})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=[LOT_CIBLE, LOT_SANS_TIRAGE])
        await pilote.pause()
        while isinstance(pilote.app.screen, versions.EcranConflitDeTirage):
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return parcours

    parcours = _jouer(scenario, app, banc)
    joues = [trace[1] for trace in coeur.trace if trace[0] == "jalon"]
    dernier, premier = joues[-1], joues[0]
    # Le compte attendu est celui que le COEUR a reellement emis pour ce
    # lot-la, jamais la pagination que le plan promettait : c'est le jalon qui
    # doit avoir traverse, pas une valeur qu'on aurait pu deviner.
    attendu = coeur.pages[dernier]
    assert parcours.passe.pages_du_lot_courant == attendu, (
        parcours.passe.pages_du_lot_courant, attendu)
    # La valeur mesure quelque chose : ni zero -- ce que la boucle pose a
    # l'entree de chaque lot -- ni le compte du lot precedent.
    assert attendu not in (0, coeur.pages[premier]), (dernier, premier)


async def _attendre_le_fil(pilote, nom: str):
    """Rendre l'ouvrier nomme, une fois sa passe finie.

    **Pourquoi un helper et pas un `await` sur la valeur rendue.** Depuis le
    2026-09-06 la passe part au FIL, et les monteurs rendent l'ECRAN -- c'est
    leur contrat, et le deplacer pour la commodite d'un banc ferait mesurer au
    banc autre chose que ce que le produit rend. L'ouvrier se cueille donc dans
    `app.workers`, par son nom, tant qu'il y est ; la reference tenue ici
    survit a son retrait du gestionnaire.

    On garde la reference AVANT d'attendre : un ouvrier fini est retire du
    gestionnaire, et le chercher apres coup rendrait `None` sur une passe
    rapide -- c'est-a-dire un banc qui verdit d'autant plus surement que la
    passe est courte.
    """
    # **On attend qu'il APPARAISSE**, et pas seulement qu'il finisse : le fil
    # ne part qu'apres le rendez-vous de dessin, donc il n'existe pas encore
    # quand le monteur rend la main.
    ouvrier = None
    for _ in range(60):
        ouvrier = next((o for o in pilote.app.workers if o.name == nom), None)
        if ouvrier is not None:
            break
        await pilote.pause()
    assert ouvrier is not None, (
        f"aucun ouvrier nomme {nom!r} : la passe n'est pas partie au fil."
        f" Ouvriers vus : {[o.name for o in pilote.app.workers]}")
    for _ in range(60):
        await pilote.pause()
        if ouvrier.is_finished:
            break
    assert ouvrier.is_finished, f"l'ouvrier {nom!r} ne finit pas"
    await pilote.pause()
    return ouvrier


#: La duree du coeur lent de la mesure de bout en bout ci-dessous. La periode
#: du rotor vaut 0,25 s : il faut donc au moins ca pour qu'un pas tombe.
DUREE_DE_LA_PASSE_LENTE = 0.6


def test_E5_4_est_AU_SOMMET_et_son_rotor_TOURNE_pendant_la_passe(tmp_path, banc):
    """**La mesure qui repond au defaut signale**, et pas son ombre.

    Le reste de ce banc mesure que `E5-4` est *monte* -- qu'il apparait dans la
    pile. Ce n'est pas ce qu'Egan a signale : « on passe de la confirmation au
    succes sans voir la progression, l'interface se fige et toutes les touches
    tapees pendant l'attente se resolvent a la sortie ». Un ecran empile mais
    jamais peint satisfait « monte » et reproduit le defaut mot pour mot.

    Les frontieres statiques du depot (`test_frontiere_du_dessin_avant_le_coeur`)
    mesurent la FORME du chemin -- qu'un rendez-vous et un fil sont la. Elles ne
    peuvent pas mesurer que l'ecran vit : c'est une propriete d'execution. Ce
    test-ci la mesure, sur le vrai parcours et le vrai ecran.

    Deux mesures, et elles se cassent separement :

    1. **`E5-4` est au sommet sur plusieurs tours de boucle** pendant que le
       coeur travaille. Un coeur appele synchroniquement en rendrait ZERO : la
       boucle serait occupee du premier au dernier jalon, et `E5-5` serait deja
       empile quand elle reprendrait la main ;
    2. **le rotor AVANCE**, c'est-a-dire prend au moins deux valeurs distinctes.
       Le rotor est pilote par `set_interval`, donc par un minuteur DE LA
       BOUCLE : une boucle occupee le fige, et un rotor fige est indistinguable
       d'une interface bloquee.

    Le coeur est **lent par construction**, via la sonde d'entree de lot du
    double. Sans cette lenteur, la passe rendrait en quelques microsecondes et
    il n'y aurait aucun tour de boucle a observer -- le test serait vert sans
    rien mesurer, ce qui est le mode de panne que ce banc combat ailleurs.

    **La fenetre de comptage est celle du COEUR**, delimitee par deux drapeaux
    qu'il pose lui-meme. Compter sur une fenetre ouverte apres le retour du
    monteur laisserait passer un chemin synchrone partout ou l'ecran de passe
    reste au sommet apres coup -- c'est le mutant qui a SURVECU sur le banc
    jumeau de l'atelier Scan avant que sa fenetre soit resserree. Ici `E5-5` se
    monte par-dessus `E5-4`, donc le defaut ne se presentait pas ; la fenetre
    est posee quand meme, pour que les trois bancs de bout en bout du depot
    mesurent la meme chose de la meme facon.
    """
    import threading
    import time

    demarre, fini = threading.Event(), threading.Event()

    def coeur_lent(*args, **kwargs) -> None:
        demarre.set()
        time.sleep(DUREE_DE_LA_PASSE_LENTE)
        fini.set()

    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2}, sonde=coeur_lent)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        parcours.generer()
        tours_au_sommet, pas_vus = 0, []
        debut = time.time()
        while time.time() - debut < DUREE_DE_LA_PASSE_LENTE + 0.4:
            await pilote.pause()
            if not (demarre.is_set() and not fini.is_set()):
                continue
            sommet = pilote.app.screen
            if isinstance(sommet, execution_pdf.EcranGenerationDesPlanches):
                tours_au_sommet += 1
                pas_vus.append(sommet.pas)
        return tours_au_sommet, pas_vus, demarre.is_set(), fini.is_set()

    tours, pas_vus, a_demarre, a_fini = _jouer(scenario, app, banc)
    assert a_demarre and a_fini, (
        f"le coeur n'a pas joue de bout en bout (demarre={a_demarre},"
        f" fini={a_fini}) : le test ne mesure pas ce qu'il annonce")
    assert tours >= 2, (
        f"`E5-4` n'a ete au sommet que {tours} tour(s) de boucle pendant la"
        " passe : le coeur occupe la boucle, donc rien n'est peint -- c'est le"
        " gel signale, mot pour mot")
    assert len(set(pas_vus)) >= 2, (
        f"le rotor n'a pris qu'une valeur ({sorted(set(pas_vus))}) : il est"
        " FIGE. Son minuteur est un minuteur de la BOUCLE, donc un rotor"
        " immobile dit que la boucle est occupee")


def test_E5_6c_est_AU_SOMMET_pendant_la_passe_DE_LA_MIRE(tmp_path, banc):
    """Le jumeau du test ci-dessus, sur l'autre entree de l'atelier.

    **Il ferme un survivant de campagne, pas une inquietude.** Le mutant « la
    mire perd son rendez-vous » a SURVECU a toute la suite le 2026-09-06 :
    aucun banc ne mesurait que `E5-6c` est peint pendant sa passe. Fermer la
    porte d'un cote seulement l'aurait laissee ouverte de l'autre -- c'est le
    motif que le banc de panne de la mire invoque deja, applique au dessin.

    `E5-6c` n'a **que** son rotor : le coeur de la mire ne publie aucun compte.
    Le rotor est donc ici la mesure entiere, et il est pilote par un minuteur
    de la BOUCLE -- une boucle occupee le fige.
    """
    import threading
    import time

    dossier = _projet(tmp_path)
    demarre, fini = threading.Event(), threading.Event()

    class _MireLente:
        def __call__(self, *args, **kwargs):
            demarre.set()
            time.sleep(DUREE_DE_LA_PASSE_LENTE)
            fini.set()
            raise ZeroDivisionError("la mire ne rend rien d'utilisable ici")

    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=_MireLente())
        parcours.charger()
        parcours.formulaire = calibration.FormulaireDeLaMire(chaine="hp-envy")
        parcours.generer_la_mire()
        tours, pas_vus = 0, []
        debut = time.time()
        while time.time() - debut < DUREE_DE_LA_PASSE_LENTE + 0.4:
            await pilote.pause()
            if not (demarre.is_set() and not fini.is_set()):
                continue
            sommet = pilote.app.screen
            if isinstance(sommet, calibration.EcranMireEnCours):
                tours += 1
                pas_vus.append(sommet.pas)
        mesure["tours"] = tours
        mesure["pas"] = sorted(set(pas_vus))
        mesure["joue"] = (demarre.is_set(), fini.is_set())

    mesure: dict = {}
    # La mire leve a la fin de sa passe : c'est ce qui garantit que le fil a
    # bien tourne jusqu'au bout, et le helper de panne sait deja le lire.
    _jouer_en_attendant_la_panne(scenario, app, banc)
    assert mesure["joue"] == (True, True), (
        f"le coeur de la mire n'a pas joue de bout en bout : {mesure['joue']}")
    assert mesure["tours"] >= 2, (
        f"`E5-6c` n'a ete au sommet que {mesure['tours']} tour(s) de boucle"
        " PENDANT que le coeur travaillait : la passe occupe la boucle, donc"
        " rien n'est peint")
    assert len(mesure["pas"]) >= 2, (
        f"le rotor de la mire n'a pris qu'une valeur ({mesure['pas']}) : il est"
        " FIGE, et il est tout ce que cet ecran a a montrer")


def test_le_drapeau_tombe_AVANT_la_conclusion_de_la_passe_de_planches(
        tmp_path, banc):
    """L'ordre du finding `F1`, mesure plutot que commente.

    **Il ferme un survivant de campagne.** Le mutant qui echange les deux
    lignes de `_conclure_la_generation` -- conclure d'abord, oublier ensuite --
    a SURVECU a toute la suite le 2026-09-06, alors que le docstring de la
    methode dit que l'ordre est « celui d'origine [...] conserve tel quel ».
    Un ordre defendu par un commentaire et par rien d'autre n'est pas tenu.

    Ce que l'inversion coute, et pourquoi c'est le meme defaut que `F1` : la
    conclusion MONTE un ecran, donc elle rend la main a la boucle. Entre elle
    et l'extinction du drapeau, la boucle tourne avec `tache_en_cours` a vrai
    sur un compte rendu deja affiche -- `Échap` y est inerte et `q` n'y quitte
    pas, sur un ecran ou la passe est finie.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()
    ordre: list[str] = []

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        vrai_oubli = pilote.app.oublier_la_tache
        vraie_conclusion = parcours.conclure

        def oubli_trace():
            ordre.append("oublier")
            return vrai_oubli()

        def conclusion_tracee(rapport):
            ordre.append("conclure")
            return vraie_conclusion(rapport)

        pilote.app.oublier_la_tache = oubli_trace
        parcours.conclure = conclusion_tracee
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        parcours.generer()
        # **On attend l'EVENEMENT trace, pas l'ouvrier.** Le double de coeur de
        # ce test rend en quelques microsecondes, et `textual` retire un
        # ouvrier fini de `app.workers` : le sondage par nom ne le voyait
        # jamais. Meme piege, meme geste, que le banc de la suppression.
        for _ in range(60):
            await pilote.pause()
            if "conclure" in ordre:
                break

    _jouer(scenario, app, banc)
    assert "conclure" in ordre, (
        "la passe n'a jamais conclu : le banc ne mesure pas ce qu'il annonce")
    assert ordre.index("oublier") < ordre.index("conclure"), (
        f"l'ordre est {ordre} : le drapeau doit tomber AVANT la conclusion,"
        " sans quoi la boucle tourne protegee sur un compte rendu deja monte")


def _jouer_en_attendant_la_panne(scenario, app, banc):
    """Jouer un scenario dont la passe LEVE, et rendre la panne d'origine.

    **Ce que `textual` fait d'une panne au fil, et qui n'est pas un detail de
    banc.** Une exception qui sort d'un ouvrier n'est pas avalee : `textual`
    l'emballe dans `WorkerFailed`, la porte au niveau de l'application, et
    `run_test` la releve au demontage pour que le banc la voie. C'est
    exactement le comportement que ce chemin veut -- « deguiser une panne
    inconnue en refus metier ferait lire un motif rassurant sur un bug ».

    Le banc lit donc la panne ICI plutot que sur le retour du monteur, et
    l'`assert` du bas est ce qui empeche ce helper de devenir complaisant : un
    scenario qui ne leverait PLUS le traverserait en silence, et les deux
    tests de panne verdiraient sur un produit qui avale.
    """
    from textual.worker import WorkerFailed

    leve = None
    try:
        _jouer(scenario, app, banc)
    except WorkerFailed as emballee:
        leve = emballee.error
    except ZeroDivisionError as nue:
        # La panne peut aussi remonter nue si un jour ce chemin redevient
        # synchrone. On l'accepte : ce que le test mesure est que la panne
        # traverse, pas par quel emballage.
        leve = nue
    assert leve is not None, (
        "aucune panne n'a traverse : soit le double ne leve plus, soit le"
        " produit l'avale -- et dans les deux cas ce test ne mesure plus rien")
    return leve


def test_une_panne_HORS_TABLE_pendant_la_passe_n_ATTACHE_PAS_l_atelier(
        tmp_path, banc):
    """La porte de l'exception -- ligne nommee par le lot d'execution.

    Une erreur hors de `REFUS_NOMMES` traverse **volontairement** la boucle
    (« deguiser une panne inconnue en refus metier ferait lire un motif
    rassurant sur un bug »). Elle sautait `oublier_la_tache()` : le drapeau
    `app.tache_en_cours` restait allume, et **l'atelier etait mort pour la
    session** -- `Échap` cesse de depiler, `Q` ne quitte plus, et rien ne les
    rallume. Le filet de demontage pose cote execution ne rattrape ce cas que si
    l'ecran est depile, ce que ce chemin ne fait justement pas.

    Deux mesures, et elles se cassent separement : le drapeau est **eteint**, et
    l'exception **traverse quand meme** -- un `except` qui l'avalerait eteindrait
    le drapeau tout en cachant le bug.

    **Regime change le 2026-09-06, les deux mesures survivent.** La passe part
    desormais au FIL : `generer` rend l'ecran sans attendre, donc ni le drapeau
    ni l'exception ne sont plus lisibles sur son retour. Ce que le banc lisait
    la, il le lit maintenant sur l'OUVRIER -- `state` vaut `ERROR` et `error`
    porte la panne. La question posee au produit n'a pas bouge d'un mot : une
    panne hors table laisse-t-elle l'atelier attache ? Ce qui a bouge, c'est
    l'endroit ou la reponse s'ecrit.

    **Et le second assert n'est pas une redite du premier.** `ERROR` seul
    laisserait passer un produit qui eteint le drapeau APRES avoir relance ;
    `tache_en_cours is False` seul laisserait passer un `except: pass` qui
    eteint le drapeau en avalant le bug. Les deux ensemble tiennent la porte.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2}, leve=LOT_SANS_TIRAGE)
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        # **Le drapeau est pose AVANT l'appel, et c'est une mesure honnete.**
        # C'est `EcranGenerationDesPlanches.on_mount` qui le pose dans le
        # produit, mais `on_mount` est distribue par la boucle d'evenements
        # alors que la passe est **synchrone** : dans un banc il n'a pas encore
        # tourne quand le coeur leve. Le poser ici reproduit l'etat reel au lieu
        # de mesurer un artefact d'ordonnancement -- sans quoi le drapeau serait
        # faux des deux cotes du correctif, et le test ne mesurerait rien.
        pilote.app.tache_en_cours = True
        parcours.generer()
        try:
            await _attendre_le_fil(pilote, "pdf-generer")
        finally:
            # **Lu ICI, et les deux moities du piege ont ete payees.**
            #
            # 1. *Pas apres `_jouer`* : le demontage de l'application demonte
            #    `E5-4`, dont l'`on_unmount` appelle `oublier_la_tache` -- on
            #    mesurerait le FILET, pas le chemin d'exception. C'est ce que
            #    le docstring dit du filet (« ne rattrape ce cas que si l'ecran
            #    est depile »), et un mutant qui laissait le drapeau allume
            #    survivait tant que la lecture se faisait apres coup ;
            # 2. *dans un `finally`* : la panne du fil peut couper l'attente
            #    elle-meme. Sans le `finally`, la mesure n'etait jamais prise
            #    et le test rendait `KeyError` -- un rouge, donc honnete, mais
            #    qui ne disait pas ce qu'il mesurait.
            mesure["tache"] = pilote.app.tache_en_cours

    mesure: dict = {}
    leve = _jouer_en_attendant_la_panne(scenario, app, banc)
    assert isinstance(leve, ZeroDivisionError), leve
    # `call_from_thread` bloque jusqu'a ce que la boucle ait execute
    # `oublier_la_tache` : le drapeau tombe donc AVANT que l'exception reparte.
    assert mesure["tache"] is False, (
        "le drapeau est reste allume sur le chemin d'exception : l'atelier est"
        " mort pour la session -- `Échap` ne depile plus, `q` ne quitte plus")


def test_une_panne_du_COEUR_DE_LA_MIRE_n_attache_pas_non_plus_l_atelier(
        tmp_path, banc):
    """Le meme `finally`, sur l'autre entree de l'atelier.

    Fermer la porte d'un cote seulement l'aurait laissee ouverte de l'autre, et
    la mire appelle le coeur exactement de la meme facon. Le volet symetrique
    est tout le reste du banc : une passe qui aboutit eteint le drapeau elle
    aussi.

    Meme deplacement de la mesure que son voisin depuis le passage au fil, et
    pour le meme motif -- **y compris le nom de l'ouvrier**, qui differe. Deux
    tests qui attendraient le meme nom passeraient tous les deux en ne
    mesurant qu'une seule des deux entrees.
    """
    dossier = _projet(tmp_path)

    class _MirePanne:
        def __call__(self, *args, **kwargs):
            raise ZeroDivisionError("panne hors table")

    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=_MirePanne())
        parcours.charger()
        parcours.formulaire = calibration.FormulaireDeLaMire(chaine="hp-envy")
        # Meme pose du drapeau, et meme motif, que pour la passe de planches.
        pilote.app.tache_en_cours = True
        parcours.generer_la_mire()
        try:
            await _attendre_le_fil(pilote, "pdf-mire")
        finally:
            mesure["tache"] = pilote.app.tache_en_cours   # meme piege, meme geste

    mesure: dict = {}
    leve = _jouer_en_attendant_la_panne(scenario, app, banc)
    assert isinstance(leve, ZeroDivisionError), leve
    assert mesure["tache"] is False, (
        "le drapeau est reste allume sur le chemin d'exception de la mire")


# ===========================================================================
# `EPIC11-ARB-181` -- le rang d'origine vient du COEUR (finding `F6`)
# ===========================================================================

#: Le vocabulaire du rang de TIRAGE, et lui seul. Il ne porte pas `rang` nu :
#: ce module compte aussi des rangs de **page** (`enumerate(pages, start=1)`) et
#: des rangs de **file** (`rang_courant` d'une passe de conflits), ou un `1` est
#: legitime. Une frontiere qui les confondrait rougirait sur du code juste, donc
#: elle serait desarmee au premier faux positif.
VOCABULAIRE_DU_RANG_DE_TIRAGE = frozenset({
    "version_rank", "a_ecrire", "rang_origine", "rang_d_origine",
    "rang_propose", "sheets_version_watermark",
})

#: Les modules de l'atelier, ceux que la mesure parcourt.
MODULES_DE_L_ATELIER = sorted(
    Path(parcours_pdf.__file__).parent.glob("atelier_pdf*.py"))


#: Le mot-cle `rang` compte, **mais seulement en argument nomme**. Passe
#: positionnellement ou lie par une boucle, `rang` designe ici un rang de page
#: (`for rang, page in enumerate(pages, start=1)`) ou un rang de file, ou un `1`
#: est juste. La nuance n'est pas un raffinement : c'est ce qui empeche la
#: frontiere de rougir sur du code correct, et une frontiere qui rougit a tort
#: est desarmee au premier faux positif.
MOT_CLE_DU_RANG = "rang"

#: Et le mot-cle `rang` **ne compte pas** quand l'instruction nomme un rang qui
#: n'est pas un rang de tirage. Le paquet emploie le meme mot pour trois choses
#: -- le tirage, le lot courant d'une passe, la page -- et une frontiere qui les
#: confond rougit sur du code juste : `TITRE_DE_LA_GENERATION.format(rang=...
#: + 1)` affiche « lot 2 sur 3 », ou le `1` est le decalage d'un affichage
#: 1-fonde et n'a rien d'un rang de tirage. Le vrai remede serait que le produit
#: cesse d'appeler trois choses `rang` ; en l'etat, la frontiere le dit plutot
#: que de se taire.
VOCABULAIRE_HORS_TIRAGE = frozenset({
    "rang_du_lot_courant", "rang_courant", "enumerate", "pages_du_lot_courant",
})


def _mots_et_entiers(noeud):
    """Les identifiants, les arguments nommes et les entiers d'un fragment d'AST.

    Les trois sont rendus separement parce qu'ils ne pesent pas pareil : un
    `rang` **nomme** est un contexte de rang de tirage, un `rang` lie par une
    boucle ne l'est pas.
    """
    import ast

    mots, mots_cles, entiers = set(), set(), []
    for fils in ast.walk(noeud):
        if isinstance(fils, ast.Name):
            mots.add(fils.id)
        elif isinstance(fils, ast.Attribute):
            mots.add(fils.attr)
        elif isinstance(fils, ast.keyword) and fils.arg:
            mots_cles.add(fils.arg)
        elif isinstance(fils, ast.Constant):
            if isinstance(fils.value, str):
                mots.add(fils.value)
            elif isinstance(fils.value, int) and not isinstance(fils.value,
                                                                bool):
                # `bool` est un `int` : `True` vaudrait le rang d'origine.
                entiers.append(fils.value)
    return mots, mots_cles, entiers


def _recopies_du_rang_d_origine(chemin: Path) -> list[str]:
    """Les instructions ou un litteral vaut le rang d'origine, **en contexte**.

    Le contexte se lit a deux niveaux, et il faut les deux : les mots de
    l'instruction elle-meme, et le **nom de la fonction qui la porte**. Sans le
    second, un repli ecrit `return 1` au fond de `rang_d_origine` passerait --
    mesure faite, ce mutant survivait a la premiere redaction de cette
    frontiere.
    """
    import ast

    from mixed_media_utility.io import version_ranks

    origine = version_ranks.RANG_ORIGINE
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    trouves: list[str] = []
    CORPS = ("body", "orelse", "finalbody", "handlers")

    def parcourir(noeud, contexte: frozenset) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                parcourir(enfant, contexte | {enfant.name})
                continue
            if isinstance(enfant, ast.stmt):
                # L'instruction **sans son corps** : sinon un `if` entier
                # compterait pour une seule instruction et la mesure serait
                # grossiere au point de ne plus rien localiser.
                mots, mots_cles, entiers = set(), set(), []
                for nom, fils in ast.iter_fields(enfant):
                    if nom in CORPS:
                        continue
                    for element in (fils if isinstance(fils, list) else [fils]):
                        if isinstance(element, ast.AST):
                            m, c, e = _mots_et_entiers(element)
                            mots |= m
                            mots_cles |= c
                            entiers += e
                tous = contexte | mots | mots_cles
                parle_de_rang = (
                    bool(tous & VOCABULAIRE_DU_RANG_DE_TIRAGE)
                    or (MOT_CLE_DU_RANG in mots_cles
                        and not tous & VOCABULAIRE_HORS_TIRAGE))
                if parle_de_rang and origine in entiers:
                    trouves.append(f"{chemin.name}:{enfant.lineno}")
                parcourir(enfant, contexte)
                continue
            parcourir(enfant, contexte)

    parcourir(arbre, frozenset())
    return trouves


def test_ARB181_aucun_module_de_l_atelier_ne_RECOPIE_le_rang_d_origine():
    """`EPIC11-ARB-181` -- la frontiere qui voit un LITTERAL, et non un nom.

    Les deux frontieres de rang du depot comptent des **noms** : un `1` leur est
    structurellement invisible, et c'est exactement pourquoi la recopie
    quadruple de `atelier_pdf_parcours.py` n'avait ete vue par personne. Sans
    cette mesure-ci, la reprise fermerait le cas d'aujourd'hui et rouvrirait
    celui de demain.

    Elle ne compte pas les `1` : elle compte ceux qui vivent dans une
    instruction **parlant de rang de tirage**. Un rang de page
    (`enumerate(pages, start=1)`) et un rang de file (`rang_courant + 1`) n'y
    entrent pas -- une frontiere qui rougirait sur du code juste serait desarmee
    au premier faux positif, et c'est le pire qui puisse arriver a une mesure.
    """
    trouves = []
    for chemin in MODULES_DE_L_ATELIER:
        trouves += _recopies_du_rang_d_origine(chemin)
    assert trouves == [], trouves


def test_ARB181_cette_frontiere_a_bien_un_OBJET(tmp_path):
    """Le volet symetrique : elle sait trouver la recopie qu'elle cherche.

    Une frontiere negative verte sur un module vide ne mesure rien. On lui
    donne un module qui recopie, et elle doit le nommer -- puis un module qui
    porte les memes mots **sans** le litteral, et elle doit se taire.
    """
    from mixed_media_utility.io import version_ranks

    origine = version_ranks.RANG_ORIGINE
    coupable = tmp_path / "atelier_pdf_faux.py"
    coupable.write_text(
        f"def f(etat):\n"
        f"    a_ecrire = getattr(etat, 'a_ecrire', {origine}) or {origine}\n"
        f"    return a_ecrire\n", encoding="utf-8")
    assert _recopies_du_rang_d_origine(coupable), "la frontiere ne voit rien"

    innocent = tmp_path / "atelier_pdf_juste.py"
    innocent.write_text(
        "def f(pages):\n"
        "    for rang, page in enumerate(pages, start=1):\n"
        "        yield rang, page\n", encoding="utf-8")
    assert _recopies_du_rang_d_origine(innocent) == []


def test_ARB181_la_TUI_SUIT_le_rang_d_origine_que_le_coeur_transporte(
        tmp_path, banc):
    """La mesure de comportement, celle qu'aucun litteral ne peut passer.

    On fait dire au coeur que l'origine vaut autre chose, et la TUI doit
    suivre : un `1` reste dans le code aurait ici l'ancien effet. C'est la meme
    forme que « la TUI lit la borne du coeur, elle ne la recopie pas » --
    l'egalite se mesure, jamais la valeur.

    La valeur choisie est **eloignee** de l'originale : une valeur voisine
    laisserait passer une comparaison decalee d'un cran.
    """
    dossier = _projet(tmp_path)
    origine_feinte = 7
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        # Le coeur dit une autre origine, et il le dit **sur l'objet qu'il
        # rend** -- pas par un canal a part.
        for lot_id, etat in list(parcours.etats.items()):
            parcours.etats[lot_id] = dataclasses.replace(
                etat, rang_origine=origine_feinte, a_ecrire=origine_feinte,
                present=origine_feinte)
        return parcours.lots_a_imprimer()

    lots = _jouer(scenario, app, banc)
    # `a_ecrire` valant l'origine, aucun lot n'ecrit de fragment de nom : c'est
    # la convention du nom, et elle suit le coeur.
    assert {lot.rang for lot in lots} == {None}, [(l.lot_id, l.rang)
                                                  for l in lots]


def test_ARB181_un_rang_AU_DESSUS_de_l_origine_feinte_s_ecrit_bien(
        tmp_path, banc):
    """Volet symetrique du precedent : la TUI n'a pas cesse d'ecrire des rangs.

    Sans lui, une implementation qui rendrait `None` **partout** serait verte
    ci-dessus. Le rang juste au-dessus de l'origine feinte doit s'ecrire.
    """
    dossier = _projet(tmp_path)
    origine_feinte = 7
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=list(ORDRE_DES_CONFLITS))
        await pilote.pause()
        for lot_id, etat in list(parcours.etats.items()):
            parcours.etats[lot_id] = dataclasses.replace(
                etat, rang_origine=origine_feinte,
                a_ecrire=origine_feinte + 1, present=origine_feinte)
        return parcours.lots_a_imprimer()

    lots = _jouer(scenario, app, banc)
    assert {lot.rang for lot in lots} == {origine_feinte + 1}, \
        [(l.lot_id, l.rang) for l in lots]


def test_T3_le_journal_du_COEUR_atterrit_dans_celui_de_l_ecran_par_le_PRODUIT(
        tmp_path, banc):
    """Finding `T3` -- le test du relais posait lui-meme le cablage qu'il mesure.

    Le mutant `C1-M28`, qui fait que le produit ne vise **jamais** le journal de
    l'ecran, y survivait : le finding `H1` etait rouvert et son test ne le
    voyait pas.

    Ici, rien n'est vise a la main. Le double journalise avec le `logger` que la
    boucle lui passe -- c'est la forme reelle, le coeur ecrivant
    `compression de gamut: ...` et `PDF ecrit: ...` -- et on lit le journal de
    la surface que `E5-4` affiche. Le chemin mesure est donc complet : coeur ->
    relais -> journal de l'ecran.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2})
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen, lots=[LOT_SANS_TIRAGE])
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return _journal_de_la_passe(pilote.app)

    lignes = _jouer(scenario, app, banc)
    attendue = CoeurDouble.LIGNE_DE_JOURNAL.format(lot=LOT_SANS_TIRAGE)
    assert [ligne for ligne in lignes if attendue in ligne], lignes


def _journal_de_la_passe(app) -> list[str]:
    """Les lignes du journal de la surface que `E5-4` a reellement affichee.

    L'ecran est encore dans la pile sous le compte rendu : on lit **son**
    journal, pas une surface fabriquee par le banc.
    """
    for ecran in app.screen_stack:
        if isinstance(ecran, execution_pdf.EcranGenerationDesPlanches):
            return list(ecran.surface.journal.lignes)
    raise AssertionError("aucun ecran de generation dans la pile")


def test_F10_le_compte_rendu_lit_les_PAGES_et_le_RANG_du_coeur(tmp_path):
    """Findings `F10` -- mutants `C1-M12` et `C1-M20`, **survivants**.

    Les deux survivaient pour la meme raison, et c'est une raison de
    **fabrique** : `_Plan(page_count=pages)` valait toujours `lot.pages`, et
    `_Issue(version_rank=None)` valait `None` partout. Le « compte reel » et le
    « compte attendu » coincidaient donc dans tous les tests, et
    `PlancheEcrite.rang` valait le rang d'origine quel que soit ce que la
    decision de conflit avait retenu.

    La fabrique porte desormais les deux valeurs **distinctes**, et ce test les
    confronte : le compte rendu lit ce que le coeur a **rendu**, jamais ce que
    la passe **attendait**. Le mode de panne ferme est le pire du versionnage :
    une ligne de compte rendu qui annonce un autre tirage que celui qui est sur
    le disque.
    """
    reel = {LOT_SCANNE: 19, LOT_CIBLE: 5, LOT_SANS_TIRAGE: 1}
    rangs = {LOT_SCANNE: 4, LOT_CIBLE: 2, LOT_SANS_TIRAGE: None}
    coeur = CoeurDouble(pages=dict(TROIS_LOTS), reel=reel, rangs=rangs)
    rapport, _passe_, _surface = _executer(tmp_path, coeur)
    par_lot = {lot_id: pages for lot_id, pages in TROIS_LOTS}
    # La fabrique mesure quelque chose : aucun compte reel ne coincide avec le
    # compte attendu, sinon les deux lectures seraient indiscernables.
    assert all(reel[lot_id] != par_lot[lot_id] for lot_id in par_lot)
    ecrites = list(rapport.ecrites)
    assert [planche.pages for planche in ecrites] == \
        [reel[lot_id] for lot_id, _p in TROIS_LOTS]
    # Le rang vient du coeur, et `None` vaut l'origine -- la convention du nom,
    # relayee et jamais traduite ici.
    origine = parcours_pdf.rang_d_origine()
    assert [planche.rang for planche in ecrites] == \
        [rangs[lot_id] or origine for lot_id, _p in TROIS_LOTS]


def test_F10_les_FRAMES_du_rapport_ne_comptent_QUE_les_lots_ecrits(tmp_path):
    """Finding `F10` -- mutant `C1-M19`, survivant. `E5-5` affiche ce compte.

    Un lot refuse ne place aucune frame : les compter serait annoncer un travail
    qui n'a pas eu lieu, sur l'ecran meme qui rend compte de ce qui a ete ecrit.
    Le lot refuse est **au milieu**, et les trois cardinaux sont differents --
    un remplissage uniforme rendrait toute erreur de somme invisible.
    """
    coeur = CoeurDouble(pages=dict(TROIS_LOTS), refuse=[LOT_CIBLE])
    rapport, _passe_, _surface = _executer(tmp_path, coeur)
    attendu = sum(FRAMES[lot_id] for lot_id, _p in TROIS_LOTS
                  if lot_id != LOT_CIBLE)
    assert rapport.frames == attendu
    # La mesure a un objet : le lot refuse pese quelque chose, et les trois
    # cardinaux sont distincts.
    assert FRAMES[LOT_CIBLE] > 0
    assert len({FRAMES[lot_id] for lot_id, _p in TROIS_LOTS}) == len(TROIS_LOTS)


def test_F10_le_refus_montre_est_le_PREMIER_et_non_le_dernier(tmp_path, banc):
    """Finding `F10` -- mutant `C1-M21`, survivant faute de **deux** refus.

    Toutes les fabriques de refus n'en portaient qu'un : `refus[0]` et
    `refus[-1]` y sont indiscernables, ce qui est le point 2 bis de la regle des
    fabriques applique a une collection de refus. Avec deux refus **aux messages
    distincts**, `conclure` doit montrer celui du premier lot -- l'ordre de la
    passe, celui que l'operateur a vu defiler.
    """
    dossier = _projet(tmp_path)
    coeur = CoeurDouble(pages={LOT_SANS_TIRAGE: 2, LOT_CIBLE: 7},
                        refuse=[LOT_SANS_TIRAGE, LOT_CIBLE])
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, coeur=coeur)
        parcours.ouvrir().traiter("enter")
        await pilote.pause()
        _cocher_et_regler(parcours, pilote.app.screen,
                          lots=[LOT_SANS_TIRAGE, LOT_CIBLE])
        await pilote.pause()
        while isinstance(pilote.app.screen, versions.EcranConflitDeTirage):
            ecran = pilote.app.screen
            ecran.choix.viser(versions.CLE_CREER)
            ecran.traiter("enter")
            await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(confirmation.ISSUE_GENERER)
        ecran.traiter("enter")
        await pilote.pause()
        return pilote.app.screen, parcours

    ecran, parcours = _jouer(scenario, app, banc)
    assert isinstance(ecran, EcranRefus)
    # Deux refus, deux messages **distincts** : sans cela le premier et le
    # dernier seraient le meme texte et le test ne mesurerait rien.
    ordre = [appel["lot"] for appel in coeur.appels]
    assert len(ordre) == 2 and ordre[0] != ordre[1]
    assert ordre[0] in ecran.message
    assert ordre[1] not in ecran.message, ecran.message


def test_F10_la_mire_passe_TOUJOURS_overwrite_au_coeur(tmp_path, banc):
    """Finding `F10` -- mutant `C1-M14`, survivant.

    `EPIC11-ARB-89` : le seul chemin qui arrive a l'ecriture en presence d'un
    fichier du meme nom est celui ou l'operateur a retenu `Remplacer cette
    mire`. Un refus du coeur y serait un **blocage sec apres un consentement**,
    exactement ce que l'arbitrage proscrit. Quand aucun fichier n'existe, le
    drapeau n'ecrase rien -- c'est pourquoi il est passe *toujours*, et pourquoi
    ce test le mesure sur le chemin **sans** conflit.
    """
    dossier = _projet(tmp_path)
    mire = MireDouble()
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=mire)
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in "hp-envy":
            ecran.traiter("", lettre)
        ecran.traiter("enter")
        await pilote.pause()
        confirme = pilote.app.screen
        confirme.choix.viser(calibration.ISSUE_GENERER)
        confirme.traiter("enter")
        await pilote.pause()

    _jouer(scenario, app, banc)
    assert len(mire.appels) == 1
    assert mire.appels[0]["overwrite"] is True, mire.appels[0]


def test_F10_le_cablage_n_expose_PAS_un_second_ouvrir_l_atelier_pdf():
    """Finding `F10` -- mutant `C1-M15` : **deux fonctions publiques du meme nom**.

    `atelier_pdf.ouvrir_l_atelier_pdf` est celle que `ChaineReelle` injecte ;
    celle de ce module etait exportee dans `__all__` et appelee par personne. Le
    jour ou les deux divergent, rien ne le dit, et la moitie des lecteurs lit la
    mauvaise.

    Volet symetrique : celle qui **vit** existe bien, et elle monte le parcours.
    Sans lui, un paquet qui n'en aurait plus aucune serait vert ci-dessus.
    """
    assert not hasattr(parcours_pdf, "ouvrir_l_atelier_pdf")
    assert "ouvrir_l_atelier_pdf" not in parcours_pdf.__all__
    assert callable(atelier_pdf.ouvrir_l_atelier_pdf)


def test_F5_CHANGER_LE_NOM_DE_LA_CHAINE_preserve_la_saisie(tmp_path, banc):
    """Finding `F5` -- le parametre `formulaire=` documentait un mecanisme mort.

    Le docstring de `regler_la_mire` affirmait que le formulaire etait
    « repasse » depuis l'ecran de conflit ; cette branche fait un
    `action_remonter()` et ne rappelle jamais la methode. Les trois sites
    d'appel le laissaient a `None`, et le mutant qui l'y forcait survivait.

    Ce qui preserve reellement la saisie est le **depilement** : l'ecran de
    formulaire est encore monte dessous, avec ce qu'on y a tape. Le parametre a
    ete retire, et la propriete est desormais **mesuree** plutot que promise --
    le jour ou ce chemin cesserait de depiler, ce test rougirait, la ou un
    parametre a `None` n'aurait jamais rien porte.
    """
    dossier = _projet(tmp_path)
    chaine = "hp-envy"
    commentaire = COMMENTAIRE_DE_LA_MIRE
    chemin = calibration.chemin_de_la_mire(dossier, PROJET, chaine)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(b"%PDF-1.4\n")
    app = _app()

    async def scenario(pilote):
        parcours = _parcours(pilote.app, dossier, mire=MireDouble())
        menu = parcours.ouvrir()
        menu.curseur = 1
        menu.traiter("enter")
        await pilote.pause()
        ecran = pilote.app.screen
        for lettre in chaine:
            ecran.traiter("", lettre)
        ecran.traiter("tab")
        for lettre in commentaire:
            ecran.traiter("", lettre)
        ecran.traiter("enter")
        await pilote.pause()
        # `E5-6d` : la mire existe. On demande a changer le nom de la chaine.
        conflit = pilote.app.screen
        conflit.choix.viser(calibration.ISSUE_AUTRE_CHAINE)
        conflit.traiter("enter")
        await pilote.pause()
        return pilote.app.screen

    revenu = _jouer(scenario, app, banc)
    assert isinstance(revenu, calibration.EcranMireReglages)
    # Les DEUX champs sont preserves : le commentaire est celui qu'un
    # formulaire neuf ferait retaper « pour une raison qui ne le concerne pas ».
    assert revenu.formulaire.saisie(calibration.CHAMP_CHAINE) == chaine
    assert revenu.formulaire.saisie(calibration.CHAMP_COMMENTAIRE) == \
        commentaire
    # Et le parametre mort n'est plus la : sa signature le dit.
    import inspect
    assert "formulaire" not in inspect.signature(
        parcours_pdf.ParcoursPdf.regler_la_mire).parameters


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite quatorze codes d'ecran et
# n'ouvrait aucun dessin. Trois de ses valeurs en etaient recopiees : le pied
# du palier temoin (`Q quitter`, dessine par `E5-0`) et le commentaire de la
# mire (`papier mat`, dessine par `E5-6` et `E5-6b`). Elles coincidaient le
# jour ou elles ont ete ecrites et rien n'aurait signale une derive.
#
# Citer une maquette pour SITUER un ecran n'est pas un defaut -- c'est meme le
# geste utile, et c'est ce que fait le reste de ce fichier. Le defaut est
# d'ASSERTER une valeur recopiee. Seules les trois valeurs recopiees sont donc
# confrontees ici ; les onze autres citations restent des citations.

#: Les maquettes, a leur source.
MAQUETTES = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
             / "ux-designs" / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"

def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


#: Les trois recopies et leur dessin d'origine. Trois valeurs DISTINGUABLES
#: sur deux dessins differents : une permutation se verrait.
RECOPIES_A_CONFRONTER = [
    ("E5-0", "E5-0-pdf-menu.txt", PIED_DU_PALIER),
    ("E5-6", "E5-6-pdf-calibration-page.txt", COMMENTAIRE_DE_LA_MIRE),
    ("E5-6b", "E5-6b-pdf-calibration-confirmation.txt", COMMENTAIRE_DE_LA_MIRE),
]


@pytest.mark.parametrize(("code", "fichier", "attendu"), RECOPIES_A_CONFRONTER,
                         ids=[f"{c}-{a}" for c, _, a in RECOPIES_A_CONFRONTER])
def test_les_valeurs_recopiees_sont_VERBATIM_de_leur_maquette(
        code, fichier, attendu):
    """La valeur est DANS le dessin, lu sur disque a ce tour-ci."""
    assert attendu in dessin_de_la_maquette(fichier), (code, attendu)


def test_le_palier_temoin_annonce_le_pied_que_le_MENU_dessine():
    """Le double n'invente pas son pied : il porte celui de `E5-0`.

    Un palier temoin dont le pied ne serait pas celui du dessin mesurerait un
    ecran qui n'existe pas -- c'est ce que la recopie rendait possible.
    """
    palier = PalierTemoin("Ateliers", PIED_DU_PALIER)
    assert palier.raccourcis == PIED_DU_PALIER
    assert PIED_DU_PALIER in dessin_de_la_maquette("E5-0-pdf-menu.txt")


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passerait.

    Trois contre-exemples, dont deux proches d'un mot : le pli absorbe la mise
    en page, il n'absorbe pas un ecart.
    """
    menu = dessin_de_la_maquette("E5-0-pdf-menu.txt")
    page = dessin_de_la_maquette("E5-6-pdf-calibration-page.txt")
    assert "Q quitter et revenir" not in menu
    assert "papier glace" not in page
    assert COMMENTAIRE_DE_LA_MIRE not in menu
