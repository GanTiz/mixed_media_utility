# -*- coding: utf-8 -*-
"""La frontiere de la FAMILLE des ecrans de conflit (`EPIC11-ARB-89` / `-104`).

**Ce que ce banc mesure, et pourquoi il n'existait pas.** Sept bancs mesurent
chacun leur ecran de conflit ; aucun ne mesure ce que les arbitrages exigent
de la **famille**. L'audit du parcours complet
(`audit-2026-09-06-parcours-complet-les-manques.md`) le nomme lui-meme comme
son plus gros trou : « les regimes de conflit et de versionnage n'ont pas ete
atteints au clavier [...] je ne l'ai pas joue ».

Trois exigences, et elles portent sur **tous** les ecrans a la fois :

* `EPIC11-ARB-89` -- au moins **deux** issues, jamais une seule, **jamais un
  blocage sec**. Verbatim d'Egan : « toujours permettre une reecriture plutot
  qu'un blocage sec » ;
* `EPIC11-ARB-104` -- tout objet produit par l'outil est **versionnable OU
  ecrasable** ;
* `EPIC11-ARB-108` -- le mecanisme de versionnage est le **meme partout** : la
  regle vit dans `io/version_ranks.py`, et aucun ecran ne la recopie.

**LA FAMILLE COMPTE SEPT ENTREES, PAS SIX -- et c'est la mesure qui l'a dit.**
La liste de l'audit en nomme six (`EcranConflitDeTirage`, `EcranRangsEpuises`,
`EcranMasterExistant`, `EcranMireExiste`, `EcranCollisionDuScan`,
`EcranConflitDeDetection`). La garde de completude ci-dessous, qui ne lit
aucune de ces listes mais **le vocabulaire d'ecrasement du produit**, en trouve
un septieme : `EcranExtractionEcrasement`. C'est exactement le motif pour
lequel une frontiere de famille se **parcourt** au lieu de s'enumerer -- une
liste ecrite a la main aurait reconduit l'oubli de l'audit.

`EcranConflitDeTirage` y figure **deux fois**, parce que c'est un ecran a deux
etats (`E5-3b` / `E5-3c`) et que le second en **perd une issue** : les mesurer
sous une seule entree ferait passer l'etat non mesure pour mesure.

**Regle des fabriques (`CLAUDE.md`), a ses QUATRE points.** La collection que
le code parcourt ici est :data:`FAMILLE` elle-meme :

1. **huit entrees distinguables** -- trois cardinaux d'issues differents et
   huit ensembles de cles differents ; aucune valeur uniforme, donc aucune
   permutation invisible ;
2. **la cible n'est pas en premiere position** -- l'issue d'ecrasement se
   trouve en tete sur deux ecrans (`EcranRangsEpuises`,
   `EcranExtractionEcrasement`) et en seconde position sur les quatre autres,
   la sortie qui n'ecrit rien etant toujours en **queue** ; les deux bords de
   la liste des issues sont donc charges ;
3. **la variante multi-elements est ecrite ici**, pas renvoyee a la revue : la
   passe de `E5-3b` porte **trois** conflits distinguables, jamais un seul, et
   :func:`test_la_masse_SAUTE_le_tirage_scanne_ou_qu_il_soit_dans_la_file`
   place la cible en tete, au milieu **et** en queue de cette file ;
4. **une cible a CHAQUE BORD de la famille** -- les deux ecrans qui n'offrent
   PAS l'ecrasement conscient sont poses l'un en **tete**
   (`EcranConflitDeDetection`) et l'autre en **queue**
   (`EcranConflitDeTirage` scanne). Un balayage tronque d'un bord ou de
   l'autre rend l'ensemble mesure plus petit que l'ensemble attendu, donc
   rouge. Le milieu est tenu a part, par la liste ORDONNEE des cardinaux.

**Ce que ce banc NE mesure PAS, dit plutot que tu :**

* la garde de completude reconnait un ecran de conflit **par le vocabulaire
  d'ecrasement qu'il emploie**. Un ecran de conflit qui n'offrirait AUCUNE
  issue d'ecrasement lui reste invisible -- et c'est precisement le cas
  d'`EcranConflitDeDetection`, qui est donc dans :data:`FAMILLE` par
  enumeration et non par decouverte. La garde reduit la fenetre, elle ne la
  ferme pas ;
* elle ne dit rien de l'**atteignabilite** des ecrans : c'est un fait de
  parcours, mesure par les bancs de cablage de chaque atelier, pas ici.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import project_maintenance
from mixed_media_utility.io import (
    encode_manifest,
    naming,
    pdf_manifest,
    scan_manifest,
    version_ranks,
)
from mixed_media_utility.tui import atelier_exports_versions as exports_versions
from mixed_media_utility.tui import atelier_extraction_ecriture as extraction
from mixed_media_utility.tui import atelier_pdf_calibration as calibration
from mixed_media_utility.tui import atelier_pdf_versions as pdf_versions
from mixed_media_utility.tui import atelier_scan_calibrate as scan_calibrate
from mixed_media_utility.tui import atelier_scan_detection as scan_detection
from mixed_media_utility.tui import atelier_scan_parcours as scan_parcours
from mixed_media_utility.tui.panneau import ChoixExclusif, Issue

#: Le paquet mesure. Il est lu du module plutot que recompose d'un chemin :
#: deux redactions du meme dossier divergent au premier deplacement.
PAQUET_TUI = Path(pdf_versions.__file__).parent

#: **Le vocabulaire de l'ecrasement conscient, LU du produit.** Ce sont les
#: deux seules cles d'issue par lesquelles le depot dit « ecrase ce qui est
#: la ». Elles ne sont pas retapees ici : une chaine recopiee coinciderait le
#: jour ou elle est ecrite et divergerait sans qu'aucune etape n'echoue.
VOCABULAIRE_DE_L_ECRASEMENT = frozenset({
    pdf_versions.CLE_REMPLACER,
    scan_calibrate.CLE_ECRASER,
})

#: Le projet des fabriques, et le rush de ses lots.
PROJET = "projet_demo"
RUSH = "plan-04"


# ===========================================================================
# Fabriques -- un ecran de conflit REEL par entree, jamais un double
# ===========================================================================

def _tirage(lot_id: str, *, poids: int, scanne: bool,
            rang: int = 3, rang_propose: int = 4
            ) -> pdf_versions.TirageEnConflit:
    """Un tirage en conflit **distinguable de tous les autres**.

    Le nom sort de `io.naming`, jamais tape : une convention recopiee
    coinciderait aujourd'hui et divergerait au premier ajustement du coeur.
    """
    return pdf_versions.TirageEnConflit(
        nom=naming.build_sheets_pdf_filename(
            PROJET, RUSH, lot_id, rang, template_id="tpl-a4-paysage-6f-v2"),
        lot_id=lot_id, rang=rang, rang_propose=rang_propose,
        pages=poids // 10, frames=poids, poids_mo=poids,
        quand=HORODATAGE_DESSINE, quand_court=JOUR_DESSINE,
        mise_en_page="tpl-a4-paysage-6f-v2", meme_mise_en_page=True,
        scanne=scanne, quand_scanne="27/08" if scanne else None)


def _passe(*, courant_scanne: bool) -> pdf_versions.PasseDeConflits:
    """**Trois** conflits distinguables, la cible au MILIEU (point 3).

    Trois lots, trois poids, deux etats de scan : un remplissage uniforme
    rendrait indiscernables « la masse a saute le scanne » et « la masse a tout
    emporte ». Le conflit **courant** est celui de rang 1, c'est-a-dire ni le
    premier ni le dernier de la file -- un `conflits[0]` fautif se demasque.
    """
    conflits = (
        _tirage("aa-premier_5", poids=111, scanne=False),
        _tirage("plan-04_25", poids=444, scanne=courant_scanne),
        _tirage("zz-dernier_2", poids=999, scanne=False),
    )
    return pdf_versions.PasseDeConflits(conflits, rang_courant=1)


def _ecran_du_tirage_ecrasable():
    return pdf_versions.EcranConflitDeTirage(
        _passe(courant_scanne=False), retenir=_journal.retenir)


def _ecran_du_tirage_scanne():
    return pdf_versions.EcranConflitDeTirage(
        _passe(courant_scanne=True), retenir=_journal.retenir)


def _ecran_des_rangs_epuises():
    """Le refus vient du COEUR et voyage tel quel (`EPIC11-ARB-30`)."""
    tirage = _tirage("plan-04_25", poids=444, scanne=False,
                     rang=naming.VERSION_RANK_MAX,
                     rang_propose=naming.VERSION_RANK_MAX)
    refus = version_ranks.refus_de_rangs_epuises(
        "tirage", tirage.lot_id, "retirer un tirage, ou en ecraser un")
    return pdf_versions.EcranRangsEpuises(tirage, refus,
                                          retenir=_journal.retenir)


def _ecran_du_master_existant():
    conflit = exports_versions.MasterEnConflit(
        nom="plan-04_25_mmu_prores_hq_v2.mov",
        nom_propose="plan-04_25_mmu_prores_hq_v3.mov",
        lot_id="plan-04_25", rang=2, rang_propose=3, profil="mmu_prores_hq",
        geometrie=(1920, 1080), echantillons=124, poids_octets=1_400_000_000,
        quand=HORODATAGE_DESSINE, quand_court=JOUR_DESSINE)
    return exports_versions.EcranMasterExistant(conflit,
                                                retenir=_journal.retenir)


def _ecran_de_la_mire_existante():
    presente = calibration.MirePresente(
        Path("/projet/planches/mire-hp-envy.pdf"), 1_756_000_000.0)
    return calibration.EcranMireExiste(presente, "hp-envy",
                                       sur_issue=_journal.retenir)


def _ecran_de_la_collision_du_scan():
    collision = scan_calibrate.CollisionDeProfil(
        occupant="beta", radical="900-png-cccccccccccc")
    return scan_parcours.EcranCollisionDuScan(
        collision, retenir=_journal.retenir, abandonner=lambda: None)


def _ecran_du_conflit_de_detection():
    conflit = scan_detection.ConflitDeDetection(slug="planches-b-cible",
                                                pages=3)
    refus = scan_detection.RefusDeDetection(
        code="UnsupportedScanInputError",
        message="Le lot 'planches-b-cible' contient deja 3 fichier(s) de "
                "meme nom mais de contenu different.")
    return scan_detection.EcranConflitDeDetection(conflit, refus,
                                                  retenir=_journal.retenir)


def _plan_d_extraction(*, rang: int | None):
    """Un plan a **deux** lots distinguables (regle des fabriques, point 1).

    Deux cadences du meme rush : c'est le cas nominal v2.1, et c'est ce qui
    rend `version_proposable` mesurable plutot que suppose.
    """
    lots = (
        extraction.LotPrevu(fps_target=12.5, frames=124, lot_id="plan-04_12p5",
                            dossier=Path("/projet/extract-frames/plan-04_12p5"),
                            deja_present=True, rang_de_version=rang),
        extraction.LotPrevu(fps_target=25.0, frames=248, lot_id="plan-04_25",
                            dossier=Path("/projet/extract-frames/plan-04_25"),
                            deja_present=True, rang_de_version=rang),
    )
    return extraction.PlanExtraction(
        dossier_projet=Path("/projet"), rush_id=RUSH,
        video_path=Path("/projet/rushes/plan-04.mov"), lots=lots,
        octets_par_frame=12_441_600)


def _ecran_de_l_ecrasement_d_extraction():
    plan = _plan_d_extraction(rang=2)
    return extraction.EcranExtractionEcrasement(
        extraction.panneau_de_l_ecrasement(plan),
        extraction.issues_de_l_ecrasement(plan),
        sur_issue=_journal.retenir, plan=plan)


class _Journal:
    """Le rappel que chaque ecran recoit : il **enregistre**, il ne juge pas.

    Un rappel muet (`lambda _: None`) rendrait indiscernables « l'issue atteint
    son rappel » et « l'issue est inerte » -- c'est le finding `K3`, paye
    quatre fois dans cet epic.
    """

    def __init__(self) -> None:
        self.retenues: list[Issue] = []

    def retenir(self, issue: Issue) -> None:
        self.retenues.append(issue)

    def vider(self) -> None:
        self.retenues.clear()


_journal = _Journal()


#: **La famille, dans l'ordre que le point 4 de la regle des fabriques exige.**
#:
#: Les deux entrees qui n'offrent PAS l'ecrasement conscient -- les cibles de
#: :func:`test_l_ecrasement_conscient_est_offert_PARTOUT_sauf_aux_deux_exceptions`
#: -- sont posees l'une en **TETE** et l'autre en **QUEUE**. Un balayage tronque
#: d'un bord ou de l'autre laisse alors l'ensemble mesure plus petit que
#: l'ensemble attendu, donc rouge ; « la cible au milieu » seule ne demasque
#: aucun des deux.
#:
#: Le milieu, lui, est tenu par
#: :func:`test_le_cardinal_des_issues_est_EXACT_et_ORDONNE`, qui compare la
#: **liste ordonnee** entiere : une entree sautee ou deplacee, ou qu'elle soit,
#: y rougit. Les deux mesures sont complementaires et se cassent separement.
FAMILLE = (
    ("EcranConflitDeDetection", _ecran_du_conflit_de_detection),
    ("EcranConflitDeTirage/ecrasable", _ecran_du_tirage_ecrasable),
    ("EcranRangsEpuises", _ecran_des_rangs_epuises),
    ("EcranMasterExistant", _ecran_du_master_existant),
    ("EcranMireExiste", _ecran_de_la_mire_existante),
    ("EcranCollisionDuScan", _ecran_de_la_collision_du_scan),
    ("EcranExtractionEcrasement", _ecran_de_l_ecrasement_d_extraction),
    ("EcranConflitDeTirage/scanne", _ecran_du_tirage_scanne),
)

#: Le cardinal d'issues **attendu de chaque entree, dans l'ordre**. C'est la
#: mesure qui attrape une entree sautee au MILIEU de la famille -- ni
#: l'ensemble des exceptions ni aucune assertion de vacuite ne la verrait.
CARDINAUX_ATTENDUS = (2, 4, 3, 3, 3, 3, 4, 3)

#: Les deux entrees qui n'offrent **pas** l'ecrasement conscient, et le motif
#: de chacune. La premiere est un arbitrage tranche, la seconde est un manque
#: ouvert -- les distinguer ici est ce qui empeche de les confondre demain.
SANS_ECRASEMENT_CONSCIENT = {
    # `EPIC11-ARB-174` / `-176`, tranches par Egan : « s'il est scanne on ne
    # peut de fait pas l'ecraser ». L'objet reste **versionnable**, donc
    # `EPIC11-ARB-104` tient : l'issue `Créer la vN` demeure.
    "EcranConflitDeTirage/scanne",
    # **Manque ouvert au 2026-09-06**, releve par ce lot : le scan est l'un des
    # cinq objets versionnables d'`EPIC11-ARB-104`, et cet ecran n'offre que la
    # version -- jamais l'ecrasement conscient. Le texte du coeur qu'il relaie
    # nomme pourtant trois issues, dont « vider ce dossier volontairement ».
    # Il n'est pas ferme ici : cet ecran n'a **aucune maquette validee**
    # (`T5-2` n'existe nulle part sous `ux-designs/`) et `EPIC11-ARB-144`
    # interdit de coder un ecran non valide.
    "EcranConflitDeDetection",
}


#: **Le seul ecran de conflit qui laisse encore `q` remonter a l'application**,
#: mesure le 2026-09-06 : `app.is_running` passe a faux, conflit non tranche,
#: sur une touche que sa ligne de raccourcis n'annonce pas. Les six autres la
#: consomment.
#:
#: Il n'est pas ferme ici : `atelier_extraction_ecriture.py` est edite par un
#: autre lot au moment ou ce banc est ecrit, et deux agents qui touchent le
#: meme fichier est exactement l'incident du 2026-08-08. La liste est une
#: **tolerance documentee**, pas une exception concedee : elle est ordonnee et
#: exacte, donc le jour ou la fuite est fermee, ce test rougit et vient
#: chercher un lecteur ici.
FUITE_DE_LA_FRAPPE = ("EcranExtractionEcrasement",)


def _choix(ecran) -> ChoixExclusif:
    """Le point de jugement de l'ecran, **quel que soit son patron**.

    Les huit entrees viennent de quatre patrons differents (`_EcranDeConflit`,
    `EcranChiffre`, `EcranDeJugement`, `Palier` nu) et portent toutes leur
    choix sous le meme nom -- ce que cette fonction mesure au passage.
    """
    choix = getattr(ecran, "choix", None)
    assert isinstance(choix, ChoixExclusif), (
        f"{type(ecran).__name__} ne porte pas de `ChoixExclusif` : un ecran de "
        "conflit qui n'est pas un point de jugement ne peut offrir aucune issue"
    )
    return choix


def _retenir_au_clavier(ecran, cle: str) -> None:
    """Amener le curseur sur une issue **aux fleches**, puis valider par `⏎`.

    Jamais par un appel direct du rappel : ce qu'on mesure est ce qu'un
    operateur obtient de son clavier, et poser l'indice a la main sauterait
    exactement la navigation qu'on croit mesurer. `ChoixExclusif.deplacer`
    **borne** le curseur au lieu de l'enrouler, donc le pas se choisit dans la
    direction de la cible.
    """
    choix = _choix(ecran)
    cles = [issue.cle for issue in choix.issues]
    assert cle in cles, f"issue {cle!r} absente : {cles}"
    pas = 1 if cles.index(cle) > choix.curseur else -1
    for _ in range(len(cles)):
        if choix.issues[choix.curseur].cle == cle:
            break
        assert ecran.traiter("down" if pas > 0 else "up"), (
            "la fleche doit etre consommee par l'ecran")
    assert choix.issues[choix.curseur].cle == cle, (cle, cles, choix.curseur)
    assert ecran.traiter("enter"), "`⏎` doit etre consomme par l'ecran"


@pytest.fixture(autouse=True)
def _journal_vierge():
    _journal.vider()
    yield
    _journal.vider()


# ===========================================================================
# La fabrique tient-elle ce que la regle exige ? (points 1 a 4)
# ===========================================================================

def test_la_famille_est_DISTINGUABLE_et_place_ses_cibles_aux_DEUX_BORDS():
    """Points 1, 2, 3 et 4 de la regle des fabriques, **mesures** ici meme.

    Sans cette mesure, la liste pourrait deriver vers un remplissage uniforme
    -- huit ecrans a trois issues, les deux exceptions cote a cote au milieu --
    et tous les balayages ci-dessous resteraient verts sur une collection qui
    ne demasque plus rien.
    """
    noms = [nom for nom, _ in FAMILLE]
    assert len(set(noms)) == len(noms), noms
    assert len(noms) >= 8, noms
    # Point 4 : une cible a CHAQUE bord.
    assert noms[0] in SANS_ECRASEMENT_CONSCIENT, noms
    assert noms[-1] in SANS_ECRASEMENT_CONSCIENT, noms
    # Point 1 : des cardinaux distinguables -- au moins trois valeurs.
    cardinaux = [len(_choix(fabrique()).issues) for _, fabrique in FAMILLE]
    assert len(set(cardinaux)) >= 3, cardinaux
    # Point 3 : la variante multi-elements est ecrite dans ce lot-ci.
    passe = _passe(courant_scanne=False)
    assert len(passe.conflits) >= 3, passe.conflits
    # Point 2 : le conflit courant n'est ni en tete ni en queue de la file.
    assert passe.rang_courant not in (0, len(passe.conflits) - 1)
    assert len({t.poids_mo for t in passe.conflits}) == len(passe.conflits)


def test_le_cardinal_des_issues_est_EXACT_et_ORDONNE():
    """La mesure qui attrape une entree sautee **au milieu** de la famille.

    Un ensemble ne le verrait pas, une assertion de vacuite non plus : seule
    une liste ordonnee compare position par position. C'est aussi elle qui
    rougit le jour ou un ecran gagne ou perd une issue sans qu'on l'ait
    voulu -- et une issue qui apparait en silence sur un ecran de conflit est
    exactement ce que `EPIC11-ARB-144` interdit de coder sans validation.
    """
    mesures = tuple(len(_choix(fabrique()).issues) for _, fabrique in FAMILLE)
    assert mesures == CARDINAUX_ATTENDUS, (
        list(zip((nom for nom, _ in FAMILLE), mesures, CARDINAUX_ATTENDUS)))


# ===========================================================================
# `EPIC11-ARB-89` -- deux issues au moins, jamais un blocage sec
# ===========================================================================

def test_aucun_ecran_de_conflit_n_offre_MOINS_de_deux_issues():
    """Le premier volet d'`EPIC11-ARB-89`, sur la famille entiere.

    L'invariant est leve par `ChoixExclusif.__post_init__` et **n'est pas
    reecrit ici** : ce test mesure qu'il s'applique a chacun des huit ecrans,
    c'est-a-dire qu'aucun ne construit son choix par un autre chemin.
    """
    cardinaux = {nom: len(_choix(fabrique()).issues)
                 for nom, fabrique in FAMILLE}
    maigres = {nom: n for nom, n in cardinaux.items() if n < 2}
    assert not maigres, maigres


def test_aucun_ecran_de_conflit_n_est_un_BLOCAGE_SEC():
    """Le second volet : **une sortie qui n'ecrit pas**, sur chaque ecran.

    « Un refus qui n'offre aucune issue est aussi fautif qu'une destruction
    silencieuse. » Un ecran dont toutes les issues ecrivent enferme l'operateur
    dans une ecriture -- c'est un blocage sec habille en choix.
    """
    sans_sortie = {}
    for nom, fabrique in FAMILLE:
        issues = _choix(fabrique()).issues
        if all(issue.ecrit for issue in issues):
            sans_sortie[nom] = [issue.cle for issue in issues]
    assert not sans_sortie, sans_sortie


def test_le_curseur_ne_se_pose_JAMAIS_sur_une_issue_qui_ECRIT():
    """`EPIC11-ARB-7` / `-45`, sur la famille : le `⏎` reflexe n'ecrit rien.

    C'est le corollaire du blocage sec pris par l'autre bout : une issue
    destructrice atteignable en une frappe transforme la validation en
    accident.
    """
    fautifs = {}
    for nom, fabrique in FAMILLE:
        choix = _choix(fabrique())
        if choix.issues[choix.curseur].ecrit:
            fautifs[nom] = choix.issues[choix.curseur].cle
    assert not fautifs, fautifs


# ===========================================================================
# `EPIC11-ARB-104` -- versionnable OU ecrasable
# ===========================================================================

#: **Ou le curseur se pose a l'ouverture, ecran par ecran et dans l'ordre.**
#: `EPIC11-ARB-7` exige seulement qu'il ne vise pas une issue qui ecrit ; cette
#: liste dit ou il se pose **vraiment**, ce qui est un fait de produit et non
#: une consequence de l'invariant.
#:
#: Le motif est mesure : un curseur qui sauterait sur la **derniere** issue non
#: ecrivante -- `Annuler` sur six ecrans sur huit -- respecterait l'invariant
#: mot pour mot et changerait pourtant le choix par defaut de la moitie de la
#: famille (mutant `M29`, survivant tant que cette liste n'existait pas).
#: `E5-3b` s'ouvre sur `Créer la vN`, la version a cote : c'est le geste que la
#: maquette recommande, et il ne doit pas deriver en silence vers `Annuler`.
CURSEUR_A_L_OUVERTURE = (
    ("EcranConflitDeDetection", scan_detection.ISSUE_RENONCER),
    ("EcranConflitDeTirage/ecrasable", pdf_versions.CLE_CREER),
    ("EcranRangsEpuises", pdf_versions.CLE_RETIRER_DE_LA_PASSE),
    ("EcranMasterExistant", exports_versions.CLE_ANNULER),
    ("EcranMireExiste", calibration.ISSUE_AUTRE_CHAINE),
    ("EcranCollisionDuScan", scan_calibrate.CLE_NOM_DIFFERENCIE),
    ("EcranExtractionEcrasement", extraction.ISSUE_MODIFIER),
    ("EcranConflitDeTirage/scanne", pdf_versions.CLE_CREER),
)


def test_le_curseur_se_pose_a_l_OUVERTURE_sur_une_issue_NOMMEE():
    """Ou le curseur atterrit, ecran par ecran -- le fait, pas l'invariant.

    « Le curseur n'est pas sur une issue qui ecrit » laisse encore huit places
    libres sur certains ecrans. Cette liste en nomme **une**, et elle nomme la
    bonne : sur `E5-3b`, le curseur ouvre sur `Créer la vN` -- la sortie qui
    n'efface rien --, jamais sur `Annuler`, qui ferait du geste par defaut un
    abandon.

    Les cles sont **lues des modules**, jamais recopiees : une cle renommee
    d'un cote seulement ferait diverger la mesure de ce qu'elle mesure.
    """
    mesure = tuple(
        (nom, _choix(fabrique()).issues[_choix(fabrique()).curseur].cle)
        for nom, fabrique in FAMILLE)
    assert mesure == CURSEUR_A_L_OUVERTURE, list(
        zip(mesure, CURSEUR_A_L_OUVERTURE))


def test_l_ecrasement_conscient_est_offert_PARTOUT_sauf_aux_deux_exceptions():
    """L'ensemble **EXACT** des ecrans qui n'offrent pas l'ecrasement.

    Mesure en ensemble exact et non en presence : « l'ecrasement est offert
    quelque part » resterait vrai si six ecrans sur huit le perdaient. Et
    l'exact attrape aussi le sens inverse -- une exception **fermee** doit
    faire rougir ce test, pour qu'on vienne la retirer de la liste plutot que
    de la laisser mentir.
    """
    sans = set()
    for nom, fabrique in FAMILLE:
        cles = {issue.cle for issue in _choix(fabrique()).issues}
        if not (cles & VOCABULAIRE_DE_L_ECRASEMENT):
            sans.add(nom)
    assert sans == SANS_ECRASEMENT_CONSCIENT, sans


def test_l_ecrasement_conscient_ECRIT_toujours_et_le_declare():
    """Une issue d'ecrasement qui ne se declare pas ecrivante est un piege.

    C'est `Issue.ecrit` qui place le curseur hors des issues destructrices : un
    ecrasement a `ecrit=False` serait atteignable en une frappe **et** compte
    comme sortie non ecrivante par le test du blocage sec, c'est-a-dire qu'il
    retournerait les deux gardes a la fois.
    """
    menteuses = {}
    for nom, fabrique in FAMILLE:
        for issue in _choix(fabrique()).issues:
            if issue.cle in VOCABULAIRE_DE_L_ECRASEMENT and not issue.ecrit:
                menteuses[nom] = issue.cle
    assert not menteuses, menteuses


def test_l_ecran_scanne_PERD_l_ecrasement_mais_GARDE_la_version():
    """`EPIC11-ARB-104` sur le seul ecran ou une issue tombe.

    « Tout doit etre versionnable OU ecrase » : quand l'ecrasement tombe
    (`EPIC11-ARB-176`, le tirage a ete scanne), la version doit rester -- sans
    quoi l'ecran devient le blocage sec qu'`ARB-89` interdit. Le volet
    symetrique est dans le meme test : l'ecran **ecrasable** porte les deux.
    """
    scanne = {issue.cle for issue in _choix(_ecran_du_tirage_scanne()).issues}
    ecrasable = {issue.cle
                 for issue in _choix(_ecran_du_tirage_ecrasable()).issues}
    assert pdf_versions.CLE_CREER in scanne, scanne
    assert pdf_versions.CLE_REMPLACER not in scanne, scanne
    assert {pdf_versions.CLE_CREER, pdf_versions.CLE_REMPLACER} <= ecrasable


# ===========================================================================
# La file des conflits -- la collection que le PRODUIT parcourt
# ===========================================================================

def test_la_masse_SAUTE_le_tirage_scanne_OU_QU_IL_SOIT_dans_la_file():
    """Point 4 de la regle des fabriques, applique a la boucle du PRODUIT.

    `emport_de_la_masse` parcourt `restants`. Une cible **au milieu** demasque
    un `restants[0]` fautif ; elle ne demasque **pas** un balayage tronque, qui
    est un autre mode de panne -- c'est le mutant survivant du lot A de la
    11.11, et la raison d'etre du quatrieme point. On place donc le tirage
    scanne successivement en **tete**, au **milieu** et en **queue** d'une file
    de trois, et on mesure les trois chiffres que l'ecran affiche sous l'issue
    de masse.

    Les poids sont **tous differents** : avec un remplissage uniforme, « la
    masse a saute le scanne » et « la masse a emporte un autre lot » rendraient
    le meme total, et la mesure serait verte a tort.
    """
    poids = {"tete": 111, "milieu": 444, "queue": 999}
    for position in ("tete", "milieu", "queue"):
        restants = tuple(
            _tirage(f"lot-{rang}_{p}", poids=p, scanne=(place == position))
            for rang, (place, p) in enumerate(poids.items()))
        emport = pdf_versions.emport_de_la_masse(restants, destructif=True)
        attendu = sum(v for k, v in poids.items() if k != position)
        assert emport.sautes == 1, (position, emport)
        assert emport.lots == 2, (position, emport)
        assert emport.poids_mo == attendu, (position, emport, attendu)


def test_la_masse_NON_destructive_ne_saute_PERSONNE_ou_que_soit_le_scanne():
    """Le volet symetrique, sans lequel le precedent est vrai par vacuite.

    `E5-3c` offre precisement de creer la vN d'un tirage scanne : une masse non
    destructive qui sauterait le scanne perdrait un lot en silence. Un saut
    inconditionnel serait vert au test precedent et faux ici.
    """
    for position in range(3):
        restants = tuple(
            _tirage(f"lot-{rang}_x", poids=100 * (rang + 1),
                    scanne=(rang == position))
            for rang in range(3))
        emport = pdf_versions.emport_de_la_masse(restants, destructif=False)
        assert emport.sautes == 0, (position, emport)
        assert emport.lots == 3, (position, emport)


# ===========================================================================
# Aucune issue inerte -- le finding `K3`, mesure sur la famille
# ===========================================================================

def test_CHAQUE_issue_de_CHAQUE_ecran_atteint_son_rappel_au_clavier():
    """« Une issue navigable qui n'appelle personne » -- paye quatre fois.

    On exerce **toutes** les issues de tous les ecrans, aux fleches et au `⏎`,
    et on mesure que le rappel recoit exactement l'issue visee. Une issue
    annoncee qui ne fait rien est un manque, et c'est celui que ce lot chasse.
    """
    inertes = {}
    mal_rendues = {}
    for nom, fabrique in FAMILLE:
        for cle in [issue.cle for issue in _choix(fabrique()).issues]:
            _journal.vider()
            _retenir_au_clavier(fabrique(), cle)
            if not _journal.retenues:
                inertes.setdefault(nom, []).append(cle)
            elif _journal.retenues[-1].cle != cle:
                mal_rendues[nom] = (cle, _journal.retenues[-1].cle)
    assert not inertes, inertes
    assert not mal_rendues, mal_rendues


#: **Les ecrans de conflit dont le rappel est FACULTATIF**, mesure le
#: 2026-09-06. C'est le finding `K3`, « paye quatre fois dans cet epic » :
#: « un `Callable | None = None` assorti d'un `if ... is not None` fait de
#: l'oubli de cablage un silence ». Sur ces deux ecrans, un montage sans
#: rappel rend TOUTES les issues inertes -- l'operateur valide, et rien
#: n'arrive, jamais.
#:
#: Le danger est **latent et non vivant** : le seul site de montage de
#: production de chacun exige le rappel. Il n'est pas ferme ici parce que le
#: rendre obligatoire touche la signature publique et une dizaine de sites de
#: banc dans deux fichiers qu'un autre lot edite. Liste **exacte et ordonnee**,
#: donc sa fermeture fait rougir ce test au lieu de passer inapercue.
RAPPEL_FACULTATIF = ("EcranMireExiste", "EcranExtractionEcrasement")


def test_le_rappel_d_un_ecran_de_conflit_est_REQUIS_sauf_ou_c_est_mesure():
    """Finding `K3`, mesure sur la famille : un cul-de-sac ne se declare pas.

    « Un point de jugement qui ne sait pas a qui rendre son issue est un
    cul-de-sac. » Cinq des sept ecrans exigent leur rappel a la construction ;
    les deux autres l'acceptent absent, et une instance ainsi montee offrirait
    trois issues dont aucune ne mene nulle part -- c'est-a-dire le blocage sec
    d'`EPIC11-ARB-89` sous l'apparence d'un choix.
    """
    import inspect
    facultatifs = []
    for nom, fabrique in FAMILLE:
        signature = inspect.signature(type(fabrique()).__init__)
        for cle in ("retenir", "sur_issue"):
            parametre = signature.parameters.get(cle)
            if parametre is not None and parametre.default is not inspect.Parameter.empty:
                facultatifs.append(type(fabrique()).__name__)
    # Les deux etats d'`EcranConflitDeTirage` partagent une classe : on compare
    # des noms de CLASSE distincts, jamais des entrees de famille.
    assert tuple(dict.fromkeys(facultatifs)) == RAPPEL_FACULTATIF, facultatifs


def test_une_frappe_IMPRIMABLE_est_consommee_par_chaque_ecran_de_conflit():
    """`EPIC11-ARB-45` : aucune lettre n'est un raccourci sur un conflit.

    Laisser remonter `q` fermerait l'application sur une touche que la ligne
    de raccourcis n'annonce pas -- devant un conflit non tranche, c'est un
    abandon silencieux du travail.
    """
    fuyants = [nom for nom, fabrique in FAMILLE
               if not fabrique().traiter("q", "q")]
    assert fuyants == list(FUITE_DE_LA_FRAPPE), fuyants


# ===========================================================================
# `EPIC11-ARB-108` -- le versionnage se calcule en UN seul endroit
# ===========================================================================

#: Les fonctions de `io/version_ranks.py` qui **calculent** un rang. Lues du
#: module, jamais recopiees : une fonction ajoutee la-bas entre d'elle-meme
#: dans la mesure.
CALCULS_DU_RANG = frozenset({
    "ligne_d_eau", "prochain_rang", "rangs_liberables", "est_en_queue",
})


def test_le_vocabulaire_du_CALCUL_de_rang_est_bien_celui_du_coeur():
    """Le volet qui empeche la frontiere negative d'etre vraie par vacuite.

    Une frontiere qui chercherait des noms de fonctions inexistants serait
    verte pour toujours. Celui-ci mesure que les quatre noms existent bel et
    bien dans `io/version_ranks.py`.
    """
    manquants = {nom for nom in CALCULS_DU_RANG
                 if not callable(getattr(version_ranks, nom, None))}
    assert not manquants, manquants


def test_AUCUN_module_de_la_TUI_ne_calcule_un_rang_de_version():
    """`EPIC11-ARB-108`, mesure a l'AST sur tout le paquet.

    « Le systeme de versionnage doit etre le meme PARTOUT [...] Il n'y a pas de
    mecanisme different par objet. » Un ecran qui recopierait le calcul est le
    defaut exact que l'arbitrage nomme -- et il ne se voit pas a la lecture,
    puisque l'ecran affiche alors un rang parfaitement plausible.

    On mesure les **appels**, pas les mentions : `atelier_pdf_versions` cite
    `version_ranks.refus_de_rangs_epuises`, qui rend une phrase et ne calcule
    aucun rang.
    """
    coupables: dict[str, list[str]] = {}
    for fichier in sorted(PAQUET_TUI.glob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"),
                          filename=str(fichier))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else cible.id if isinstance(cible, ast.Name) else None)
            if nom in CALCULS_DU_RANG:
                coupables.setdefault(fichier.name, []).append(
                    f"l.{noeud.lineno}: {nom}")
    assert not coupables, coupables


# ===========================================================================
# La garde de completude -- ce qui rougit quand un ecran de conflit NAIT
# ===========================================================================

def _modules_qui_offrent_un_ecrasement() -> set[str]:
    """Les modules de `tui/` qui construisent une `Issue` d'ecrasement conscient.

    Mesure **par la valeur** et non par le nom : on lit les deux cles du
    produit (:data:`VOCABULAIRE_DE_L_ECRASEMENT`), on repere les constantes de
    module qui les portent, puis les `Issue(...)` construits dessus. Une
    constante d'un autre role -- `atelier_pdf_parcours.DECISION_ECRASER`, qui
    est une decision de parcours et non une issue -- ne mord donc pas.
    """
    trouves: set[str] = set()
    for fichier in sorted(PAQUET_TUI.glob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"),
                          filename=str(fichier))
        porteuses = {
            cible.id
            for noeud in arbre.body if isinstance(noeud, ast.Assign)
            if isinstance(noeud.value, ast.Constant)
            and noeud.value.value in VOCABULAIRE_DE_L_ECRASEMENT
            for cible in noeud.targets if isinstance(cible, ast.Name)
        }
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == Issue.__name__ and noeud.args):
                continue
            premier = noeud.args[0]
            if ((isinstance(premier, ast.Name) and premier.id in porteuses)
                    or (isinstance(premier, ast.Constant)
                        and premier.value in VOCABULAIRE_DE_L_ECRASEMENT)):
                trouves.add(fichier.stem)
    return trouves


#: Les modules ou vivent les issues d'ecrasement de la famille, **derives des
#: fabriques** plutot que reecrits : ajouter une entree a `FAMILLE` etend la
#: garde sans qu'on ait a toucher a une seconde liste.
def _modules_de_la_famille() -> set[str]:
    """Les modules **de toute la lignee** de chaque ecran qui offre l'ecrasement.

    La lignee et non le seul module de la classe : `EcranCollisionDuScan` vit
    dans `atelier_scan_parcours` mais herite d'`EcranCollisionDeProfil`, ou
    l'issue d'ecrasement est **construite**. Ne compter que la classe finale
    laisserait `atelier_scan_calibrate` pour un module non couvert alors qu'il
    l'est -- une garde qui accuse a tort se fait desarmer.
    """
    modules = set()
    for _nom, fabrique in FAMILLE:
        ecran = fabrique()
        if not ({issue.cle for issue in _choix(ecran).issues}
                & VOCABULAIRE_DE_L_ECRASEMENT):
            continue
        for classe in type(ecran).__mro__:
            modules.add(classe.__module__.rsplit(".", 1)[-1])
    return modules


def test_la_FAMILLE_couvre_tout_module_de_la_TUI_qui_offre_un_ecrasement():
    """La garde qui rougit quand un ecran de conflit NEUF manque a la liste.

    Elle ne lit **aucune** des listes de ce fichier : elle part du vocabulaire
    d'ecrasement du produit et remonte aux modules qui l'emploient. C'est elle
    qui a trouve `EcranExtractionEcrasement`, absent de la liste de six que
    l'audit du parcours nommait.

    **Ce qu'elle ne voit pas est dit** : un ecran de conflit qui n'offrirait
    aucune issue d'ecrasement lui echappe (`EcranConflitDeDetection` est dans
    la famille par enumeration). La garde reduit la fenetre, elle ne la ferme
    pas -- seul un registre porte par le produit le ferait, et il n'y en a pas.
    """
    offrants = _modules_qui_offrent_un_ecrasement()
    assert offrants, (
        "aucun module de la TUI ne construit d'issue d'ecrasement : la mesure "
        "est vraie par vacuite, donc elle ne mesure rien")
    manquants = offrants - _modules_de_la_famille()
    assert not manquants, (
        "ces modules offrent un ecrasement conscient et ne sont couverts par "
        f"aucune entree de FAMILLE : {sorted(manquants)}")


# ===========================================================================
# Le chemin qui MENE a un conflit ne doit pas etre une CHUTE
# ===========================================================================

#: Le motif d'un TIFF a l'en-tete tronque : quatre octets, l'ordre des mots et
#: un numero magique volontairement faux. C'est ce que laisse un scan
#: interrompu ou un disque plein, et c'est le regime qui rendait
#: `EcranMasterExistant` inatteignable.
TIFF_TRONQUE = b"II*\0"


def test_ffprobe_rend_bien_rc0_sur_une_frame_TRONQUEE(tmp_path):
    """Le volet de vacuite, et il est indispensable.

    Sans lui, la mesure suivante serait verte pour la mauvaise raison sur toute
    machine ou ffprobe **refuserait** ce fichier par son code de retour : elle
    mesurerait alors la garde qui existait deja, jamais celle qui a ete posee.
    Ce test dit ce que la premiere ne peut pas dire d'elle-meme -- que ffprobe
    accepte, et que c'est bien la valeur qu'il rend qui devait etre refusee.
    """
    import subprocess
    frame = tmp_path / "tronquee.tiff"
    frame.write_bytes(TIFF_TRONQUE)
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         "--", str(frame)],
        capture_output=True, encoding="utf-8", errors="replace")
    assert sortie.returncode == 0, (
        "ffprobe refuse ce fichier par son code de retour : la garde de "
        "`probe_frame_size` mordait deja, et la mesure suivante ne mesure "
        f"plus rien (rc={sortie.returncode})")
    assert (sortie.stdout or "").strip() == "0,0", sortie.stdout


def test_une_frame_ILLISIBLE_est_un_REFUS_et_jamais_une_chute(tmp_path):
    """La precondition d'atteignabilite d'`EcranMasterExistant` (`E4-3b`).

    Mesure du 2026-09-06, sur le parcours reel de l'atelier Exports : une seule
    frame tronquee dans `output-frames/<lot>/` et l'application **tombait**.
    ffprobe rendant `0,0` en rc=0, la geometrie `(0, 0)` traversait
    `ensure_uniform_frame_shapes` jusqu'a `encode._same_aspect_ratio`, ou
    `Fraction(0, 0)` levait un `ZeroDivisionError` -- exception que
    `plan_encode` ne convertit pas en `EncodeDecisionError` et qui remonte donc
    nue dans la boucle textual. Ni un blocage, ni une issue : une chute, et
    l'ecran de conflit du master devenait inatteignable.

    Une dimension nulle n'est pas une geometrie : c'est une frame illisible, et
    le refus rejoint celui que `plan_encode` sait deja rendre a l'operateur.
    """
    from mixed_media_utility import codec_profiles
    frame = tmp_path / "tronquee.tiff"
    frame.write_bytes(TIFF_TRONQUE)
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.probe_frame_size(frame)
    # Le volet symetrique : la garde ne mord PAS une frame lisible, sans quoi
    # elle refuserait l'atelier entier au lieu de la seule frame abimee.
    from PIL import Image
    saine = tmp_path / "saine.tiff"
    Image.new("RGB", (1920, 1080), (12, 34, 56)).save(saine, format="TIFF")
    assert codec_profiles.probe_frame_size(saine) == (1920, 1080)


def test_le_refus_d_une_frame_illisible_ATTEINT_le_plan_du_coeur(tmp_path):
    """La moitie qui manque : le refus doit etre **converti**, pas seulement leve.

    `ensure_uniform_frame_shapes` est le seul appelant de `probe_frame_size`
    dans `plan_encode`, et c'est lui qui porte l'exception jusqu'a la conversion
    en `EncodeDecisionError`. Un refus leve mais non converti resterait une
    chute -- la mesure porte donc sur la classe que le parcours attrape, jamais
    sur celle que la sonde leve.
    """
    from mixed_media_utility import codec_profiles, encode
    frame = tmp_path / "tronquee.tiff"
    frame.write_bytes(TIFF_TRONQUE)
    with pytest.raises(codec_profiles.EncodeConfigurationError):
        codec_profiles.ensure_uniform_frame_shapes([frame])
    # Et le parcours, lui, n'attrape que celle-la : la mesurer nomme ce que la
    # conversion de `plan_encode` doit continuer de voir passer.
    assert issubclass(codec_profiles.EncodeConfigurationError, Exception)
    assert not issubclass(codec_profiles.EncodeConfigurationError,
                          encode.EncodeDecisionError)


# ===========================================================================
# Les CINQ lignes d'eau -- la surface morte du 2026-08-31, remesuree
# ===========================================================================

#: **Le SCHEMA du projet -- la source independante des cinq noms de champ.**
#: Elle n'est pas facultative : deriver les noms attendus des constantes du
#: code ferait de la mesure une tautologie. Un mutant qui renomme
#: `pdf_manifest.SHEETS_WATERMARK_FIELD` renomme du meme coup ce que
#: `project_maintenance` importe, donc les deux cotes coincident encore et la
#: mesure reste verte -- mesure le 2026-09-06, mutant `M25` survivant. Le
#: schema, lui, ne bouge pas avec le code : c'est le contrat des manifestes
#: **deja ecrits sur le disque des projets**, et un champ renomme sans
#: migration les rend illisibles.
# Meme deplacement que ci-dessus : le schema vit dans le paquet.
SCHEMA_DU_PROJET = (_RACINE / "src" / "mixed_media_utility"
                    / "specs" / "project.schema.json")

#: Les cinq champs de ligne d'eau du depot, **nommes ici et confrontes au
#: schema**. La revue du 2026-08-31 en avait trouve **quatre muets** : declares
#: au schema, lus par un resolveur, ecrits par aucun chemin. Un champ muet
#: retourne l'arbitrage en silence -- le rang libere redevient disponible par
#: defaut, l'inverse exact du point 3 d'`EPIC11-ARB-92`.
LIGNES_D_EAU = {
    "lot": "lot_version_watermarks",
    "masters": "masters_version_watermark",
    "scan": "scan_version_watermarks",
    "output_frames": "output_frames_version_watermark",
    "sheets": "sheets_version_watermark",
}

#: Ou chaque champ est **declare** dans le code. Le pont entre le schema et le
#: code est mesure a part : c'est lui qui rougit quand une constante derive.
CONSTANTES_DES_LIGNES_D_EAU = {
    "lot": project_maintenance.LOT_WATERMARKS_FIELD,
    "masters": encode_manifest.MASTERS_WATERMARK_FIELD,
    "scan": project_maintenance.SCAN_WATERMARKS_FIELD,
    "output_frames": project_maintenance.OUTPUT_FRAMES_WATERMARK_FIELD,
    "sheets": pdf_manifest.SHEETS_WATERMARK_FIELD,
}


def test_les_CINQ_champs_de_ligne_d_eau_sont_DISTINCTS_et_declares_au_SCHEMA():
    """Le volet de vacuite, et le pont avec la source independante.

    Deux champs qui porteraient le meme nom feraient passer la mesure suivante
    au vert sur quatre chemins au lieu de cinq. Et un champ que le schema ne
    declare pas ne serait pas une ligne d'eau : il serait une invention de
    banc.
    """
    assert len(set(LIGNES_D_EAU.values())) == 5, LIGNES_D_EAU
    schema = SCHEMA_DU_PROJET.read_text(encoding="utf-8")
    absents = {role: champ for role, champ in LIGNES_D_EAU.items()
               if f'"{champ}"' not in schema}
    assert not absents, (
        f"champs absents du schema {SCHEMA_DU_PROJET.name} : {absents}")


def test_les_CONSTANTES_du_code_portent_les_noms_du_SCHEMA():
    """Le pont, mesure dans le seul sens qui compte : code -> schema.

    Une constante renommee sans migration rend illisibles les manifestes deja
    ecrits -- la ligne d'eau du projet redevient absente, donc le resolveur la
    lit a l'origine, donc **un rang deja consomme est rendu disponible**. C'est
    le retournement silencieux d'`EPIC11-ARB-92` par un simple renommage.
    """
    derives = {role: (CONSTANTES_DES_LIGNES_D_EAU[role], attendu)
               for role, attendu in LIGNES_D_EAU.items()
               if CONSTANTES_DES_LIGNES_D_EAU[role] != attendu}
    assert not derives, derives


def test_les_CINQ_lignes_d_eau_sont_ECRITES_au_retrait_et_pas_seulement_LUES():
    """La surface morte du 2026-08-31, mesuree plutot que rappelee.

    Le geste d'`EPIC11-ARB-108` : « la ligne d'eau se pose au RETRAIT, pas
    seulement a la consommation ». On mesure donc, dans le module qui **libere**
    les rangs, qu'il existe pour chacun des cinq champs au moins une
    **affectation** -- une lecture (`manifest.get(...)`) ne suffit pas, et
    c'etait exactement la forme du defaut.

    **Ce que cette mesure ne voit PAS, dit plutot que tu** : elle est
    structurelle, donc elle repond « ce champ est-il ecrit quelque part ? » et
    non « ce champ est-il ecrit sur CE chemin de retrait ? ». Mesure le
    2026-09-06 : la ligne d'eau des scans porte **deux** sites d'ecriture, et
    en retirer un seul laisse ce test vert (mutants `M16d` / `M16e`,
    survivants et **tolerance documentee**). Ce que la mesure attrape est la
    muette COMPLETE, c'est-a-dire le defaut du 2026-08-31 lui-meme -- verifie
    par `M24`, qui retire l'unique site de la ligne d'eau des lots et meurt.
    La granularite par chemin est mesuree ailleurs, **au comportement**, par
    `tests/unit/test_suppression_element_de_projet.py`, qui compare les valeurs
    des cinq champs apres un vrai retrait.
    """
    source = Path(project_maintenance.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source, filename=project_maintenance.__file__)
    # Les noms de constantes qui portent chacun des cinq champs, DANS ce
    # module : le champ voyage par sa constante, jamais par sa chaine.
    par_valeur = {valeur: nom for nom, valeur in
                  ((n, getattr(project_maintenance, n))
                   for n in dir(project_maintenance)
                   if n.isupper() and isinstance(
                       getattr(project_maintenance, n), str))}
    ecrits: set[str] = set()
    for noeud in ast.walk(arbre):
        # `manifest[CHAMP] = ...` et `entree[CHAMP] = ...`
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if (isinstance(cible, ast.Subscript)
                        and isinstance(cible.slice, ast.Name)):
                    ecrits.add(cible.slice.id)
    muets = {}
    for role, champ in LIGNES_D_EAU.items():
        nom = par_valeur.get(champ)
        if nom is None or nom not in ecrits:
            muets[role] = champ
    assert not muets, (
        "ces lignes d'eau sont lues mais jamais ECRITES par le module qui "
        f"libere les rangs : {muets}")


def test_le_champ_de_ligne_d_eau_des_scans_est_bien_celui_du_manifeste():
    """Le pont entre les deux redactions du nom : elles doivent coincider.

    `project_maintenance` et `scan_ingest` declarent chacun leur constante ;
    deux redactions divergentes ecriraient la ligne d'eau dans deux champs
    differents, et le resolveur n'en lirait qu'un.
    """
    from mixed_media_utility import scan_ingest
    assert (project_maintenance.SCAN_WATERMARKS_FIELD
            == scan_ingest.SCAN_WATERMARKS_FIELD)
    assert scan_manifest.SCANNED_VERSION_RANKS_FIELD \
        != project_maintenance.SCAN_WATERMARKS_FIELD, (
            "les rangs SCANNES et la ligne d'eau des scans sont deux faits "
            "differents : les confondre ferait proteger un rang jamais lu")


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc monte les trois ecrans de
# conflit -- `E4-3b`, `E5-3b`, `E5-3c` -- et n'ouvrait aucun dessin :
# l'horodatage de la ligne « Écrit le » y etait recopie a la main, deux fois.
# Sa docstring dit pourtant, du NOM du tirage, qu'« une convention recopiee
# coinciderait aujourd'hui et divergerait au premier ajustement ». C'est
# exactement ce que l'horodatage faisait.

#: L'horodatage que les TROIS dessins portent sur leur ligne « Écrit le », et
#: son abrege. Confrontes a leur source ci-dessous.
HORODATAGE_DESSINE = "26/08 à 16:22"
JOUR_DESSINE = "26/08"

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


#: Les trois dessins de conflit, et la ligne qui les porte. Une fabrique de
#: collection produit au moins deux elements DISTINGUABLES : les trois codes
#: different, et la cible est mesuree en tete, au milieu et en queue.
DESSINS_DE_CONFLIT = (
    ("E4-3b", "E4-3b-exports-master-existe.txt"),
    ("E5-3b", "E5-3b-pdf-tirage-existe.txt"),
    ("E5-3c", "E5-3c-pdf-tirage-scanne.txt"),
)


@pytest.mark.parametrize("code,fichier", DESSINS_DE_CONFLIT,
                         ids=[c for c, _ in DESSINS_DE_CONFLIT])
def test_l_HORODATAGE_est_celui_que_CHAQUE_dessin_de_conflit_porte(code, fichier):
    """Les trois, un par un -- pas « au moins un des trois ».

    Les trois ecrans partagent la ligne « Écrit le », et c'est justement ce
    qui rend une mesure globale trompeuse : trouver l'horodatage « quelque
    part » resterait vert si un seul dessin l'avait. Le parametrage nomme
    chaque dessin, donc un dessin qui divergerait se designerait lui-meme.
    """
    dessin = dessin_de_la_maquette(fichier)
    assert "Écrit le " + HORODATAGE_DESSINE in dessin, code
    assert HORODATAGE_DESSINE.startswith(JOUR_DESSINE)


def test_les_TROIS_dessins_de_conflit_sont_DISTINGUABLES_entre_eux():
    """Volet symetrique : ils partagent la ligne, pas l'ecran.

    Sans lui, la mesure ci-dessus serait aussi vraie de trois copies du meme
    fichier -- et un appariement code/dessin permute passerait. Chaque code
    porte donc un texte que les deux autres n'ont pas.
    """
    par_code = {code: dessin_de_la_maquette(fichier)
                for code, fichier in DESSINS_DE_CONFLIT}
    assert len(set(par_code.values())) == 3

    propres = {"E4-3b": "master", "E5-3b": "tirage", "E5-3c": "scanné"}
    for code, mot in propres.items():
        assert mot in par_code[code].lower(), (code, mot)


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    for _, fichier in DESSINS_DE_CONFLIT:
        dessin = dessin_de_la_maquette(fichier)
        assert "26/08 à 16:23" not in dessin
        assert "Écrit le 27/08" not in dessin
