# -*- coding: utf-8 -*-
"""`EPIC11-ARB-133` -- la seconde issue d'`EPIC11-ARB-89`, cablee dans la TUI.

Ce banc mesure **un cablage**, et il a un banc a lui : « quand un decoupage en
lots fait converger deux agents vers un meme banc, c'est le decoupage qu'il
faut changer » (`CLAUDE.md`). Les bancs de `E3-6` et du parcours du temps 2
existent deja et appartiennent a d'autres lots.

Le fait qu'il ferme, mesure par la revue de la vague 4
------------------------------------------------------
`nouvelle_version=` existait au coeur, etait relaye jusqu'a
`atelier_scan_ecriture.LotAEcrire` et jusqu'a
`scan_write.ecrire_depuis_le_document` -- et **aucun chemin de TUI ne le posait
jamais a `True`** : le seul `=True` du depot vivait dans un test. Un lot deja
ecrit ne recevait donc, depuis l'interface, qu'un `EcranRefus` a une seule
issue, c'est-a-dire le blocage sec qu'`EPIC11-ARB-89` interdit nommement.

Les quatre familles mesurees ici
--------------------------------
1. **la quatrieme issue apparait quand le lot est deja ecrit**, et son volet
   symetrique : elle n'apparait PAS sur un projet vierge. Une mesure qui ne
   ferait que la premiere serait verte sur une issue posee inconditionnellement
   -- c'est-a-dire sur du bruit permanent au regime nominal ;
2. **le drapeau atteint le plan d'ecriture**, sur TOUS les lots, et son volet
   symetrique : l'issue nominale le laisse a faux. Les deux ensemble mesurent
   que c'est bien l'issue qui le pose et non une valeur cablee en dur ;
3. **aucune regle de rang n'est ecrite en TUI** -- comptage a zero sur le
   paquet entier, avec son volet symetrique : le vocabulaire cherche existe
   bien au coeur, sans quoi la frontiere serait verte pour la mauvaise raison ;
4. **le comptage du disque vise le bon lot**, cible au **milieu** de trois.

Les fabriques sont celles du banc de `E3-6` (`test_atelier_scan_confirmation`),
important comme module : elles portent deja trois lots distinguables, la cible
en seconde position sur trois, et leur ordre est celui de la liste que le code
parcourt.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
_ICI = str(Path(__file__).resolve().parent)
if _ICI not in sys.path:
    sys.path.insert(0, _ICI)

import pytest

import test_atelier_scan_confirmation as fabriques
from mixed_media_utility import scan_output_frames
from mixed_media_utility.io import naming, version_ranks
from mixed_media_utility.tui import atelier_scan_confirmation as confirmation
from mixed_media_utility.tui import atelier_scan_ecriture, atelier_scan_parcours

#: Le paquet mesure par la frontiere negative de la famille 3.
PAQUET_TUI = Path(_SRC) / "mixed_media_utility" / "tui"

#: Le lot que les fabriques placent **au milieu** des trois.
LOT_CIBLE = fabriques.LOT_CIBLE

#: Un compte de frames deja ecrites qui n'est **aucun** des trois comptes de la
#: fabrique : un cablage qui rendrait « les frames du lot » au lieu de « les
#: frames deja sur le disque » se verrait.
DEJA_ECRITES = 7


# ---------------------------------------------------------------------------
# Fabriques locales -- des plans, jamais un seul lot
# ---------------------------------------------------------------------------

def plan(**deja):
    """Le plan des trois lots, avec le comptage de disque demande.

    Sans argument, il rend le **projet vierge** : aucun lot n'a rien d'ecrit.
    C'est le regime nominal, et c'est le volet symetrique de chaque mesure.
    """
    return confirmation.preparer_le_plan(
        fabriques.rapport_a_trois_lots(),
        fabriques.documents_a_trois_lots(),
        frames_deja_ecrites=deja or None)


def cles(choix) -> list[str]:
    return [issue.cle for issue in choix.issues]


# ===========================================================================
# Famille 1 -- la quatrieme issue, et son volet symetrique
# ===========================================================================

def test_un_lot_DEJA_ECRIT_recoit_l_issue_de_VERSIONNAGE():
    """Le regime ou le coeur refuserait : l'interface offre une seconde issue.

    L'ensemble des cles est mesure **exactement**, jamais par appartenance :
    « la cle est presente » laisserait passer une cinquieme issue apparue sans
    qu'on la voie, et l'ORDRE est celui de la deliberation -- ecrire,
    versionner, revenir, renoncer.
    """
    choix = confirmation.issues_de_la_confirmation(
        plan(**{LOT_CIBLE: DEJA_ECRITES}))
    assert cles(choix) == [confirmation.ISSUE_ECRIRE,
                           confirmation.ISSUE_NOUVELLE_VERSION,
                           confirmation.ISSUE_MODIFIER,
                           confirmation.ISSUE_ANNULER]


def test_un_projet_VIERGE_ne_recoit_PAS_l_issue_de_versionnage():
    """Le volet symetrique, et il vaut autant que l'autre moitie.

    Sans lui, une issue posee **inconditionnellement** rendrait le test
    precedent vert tout en mettant une ligne de bruit permanent sur le seul
    chemin que l'operateur emprunte tous les jours.
    """
    choix = confirmation.issues_de_la_confirmation(plan())
    assert cles(choix) == [confirmation.ISSUE_ECRIRE,
                           confirmation.ISSUE_MODIFIER,
                           confirmation.ISSUE_ANNULER]


def test_l_issue_de_versionnage_n_est_JAMAIS_visee_par_le_curseur():
    """`EPIC11-ARB-45` : aucune ecriture atteignable en UNE frappe.

    L'issue de versionnage **ecrit** -- elle ne detruit rien, mais elle pose
    des fichiers --, donc elle porte `ecrit=True` et le curseur ne peut pas s'y
    poser au montage. La marquer `ecrit=False` la mettrait sous `Entree` des le
    montage, ce qui est exactement l'accident que l'arbitrage ferme.
    """
    choix = confirmation.issues_de_la_confirmation(
        plan(**{LOT_CIBLE: DEJA_ECRITES}))
    assert choix.issue(confirmation.ISSUE_NOUVELLE_VERSION).ecrit is True
    assert not choix.issues[choix.curseur].ecrit
    assert choix.issues[choix.curseur].cle == confirmation.ISSUE_MODIFIER


def test_le_cartouche_CHIFFRE_ce_qui_est_deja_ecrit_et_se_tait_sinon():
    """`EPIC11-ARB-4` : une issue neuve sans chiffre qui l'explique n'en est pas.

    Les deux volets dans un seul test, et c'est delibere : la ligne n'a de sens
    que par contraste -- elle apparait dans un regime et **pas** dans l'autre.
    """
    avec = confirmation.panneau_de_la_confirmation(
        plan(**{LOT_CIBLE: DEJA_ECRITES}))
    sans = confirmation.panneau_de_la_confirmation(plan())
    libelles_avec = [ligne.libelle for ligne in avec.lignes]
    libelles_sans = [ligne.libelle for ligne in sans.lignes]
    assert libelles_avec[-1] == confirmation.LIBELLE_DEJA_ECRITES
    assert confirmation.LIBELLE_DEJA_ECRITES not in libelles_sans
    # Le chiffre est celui du disque, jamais celui des frames a ecrire.
    assert avec.lignes[-1].valeur == DEJA_ECRITES


def test_le_comptage_du_disque_se_pose_sur_le_lot_VISE_et_sur_lui_seul():
    """La cible est au **milieu** des trois, et la mesure porte sur les trois.

    Un cablage qui poserait le compte sur « le premier lot » ou sur « tous les
    lots » rendrait le meme total et la meme quatrieme issue : c'est
    l'appariement par `lot_id` qui se mesure ici, pas le total.
    """
    projete = plan(**{LOT_CIBLE: DEJA_ECRITES})
    par_lot = {lot.lot_id: lot.frames_deja_ecrites for lot in projete.lots}
    assert par_lot == {fabriques.LOT_PREMIER: 0,
                       LOT_CIBLE: DEJA_ECRITES,
                       fabriques.LOT_DERNIER: 0}
    # Et le rang de la cible est bien le rang **du milieu** sur la liste que le
    # code parcourt -- pas sur celle que la fabrique croit ecrire.
    assert [lot.lot_id for lot in projete.lots].index(LOT_CIBLE) == 1


# ===========================================================================
# Famille 2 -- le drapeau atteint le plan d'ecriture, et son volet symetrique
# ===========================================================================

class _AppMuette:
    """Le strict minimum qu'un parcours touche quand on ne monte rien."""

    ascii_seul = False
    sans_couleur = False
    interruption_demandee = False

    def __init__(self) -> None:
        self.montes: list = []

    def descendre(self, ecran=None) -> None:
        self.montes.append(ecran)

    def revenir_aux_ateliers(self) -> None:
        self.montes.append("ateliers")


#: Les trois cadences de la fabrique « avec dossier de sortie ». Elles sont
#: **differentes** : trois cadences egales donneraient trois dossiers egaux, et
#: un comptage pose sur le mauvais lot y serait indiscernable du bon.
CADENCES = (25.0, 12.5, 48.0)


def _documents_avec_dossier_de_sortie():
    """Trois documents dont le `lot_id` est CONSISTANT avec sa cadence.

    `scan_output_frames.derive_lot_dir_slug` refuse un `lot_id` qui ne se
    recompose pas de son rush et de sa cadence -- c'est la garde qui empeche
    d'ecrire les frames d'un lot dans le dossier d'un autre. Les fabriques du
    rapport portent des `lot_id` lisibles (`lot_25fps`) que cette garde refuse,
    donc leur dossier de sortie vaut `None` : une mesure du comptage de disque
    posee dessus serait verte en ne comptant rien.

    Les identifiants sont donc **derives par le coeur** (`naming.build_lot_id`)
    et jamais ecrits a la main : une seconde redaction de la convention
    divergerait de la garde qu'elle est censee satisfaire.

    Trois lots, trois cadences, trois dossiers -- et la cible **au milieu**.
    """
    import dataclasses

    documents = []
    for rang, fps in enumerate(CADENCES):
        lot_id = naming.build_lot_id("rush_a", fps)
        page = fabriques.page(rang * 10 + 1, page_index=0, page_count=1,
                              lot_id=lot_id,
                              zones=(fabriques.zone(0), fabriques.zone(1)))
        # `fps_target` est un **nombre**, comme `io.payload.validate_payload`
        # l'exige (« must be a number > 0 ») : une chaine ferait mesurer une
        # forme que le produit ne rencontre jamais.
        charge = dict(page.payload)
        charge["fps_target"] = fps
        page = dataclasses.replace(page, payload=charge)
        documents.append(fabriques.document(
            lot_id, slug=f"ingest_{rang}", pages_expected=1, pages=[page]))
    return documents


def _parcours(tmp_path, *, avec_cadence: bool = False):
    """Un parcours dont les trois documents sont **relus du disque**."""
    import test_frontieres_et_grille_scan as fabriques_du_temps_1

    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    documents = (_documents_avec_dossier_de_sortie()
                 if avec_cadence else None)
    chemins = fabriques_du_temps_1._ecrire_les_documents(projet, documents)
    parcours = atelier_scan_parcours.ParcoursScan(_AppMuette(), projet)
    parcours.documents = atelier_scan_parcours.documents_relus(chemins)
    # Le rapport se **projette**, il ne se fabrique pas ici : c'est lui que le
    # parcours parcourt, et une liste de lots ecrite a la main pourrait ne pas
    # etre dans l'ordre du tri du coeur.
    parcours.montrer_le_rapport()
    return parcours


@pytest.mark.parametrize("demande,attendu", [
    pytest.param(True, True, id="nouvelle-version"),
    pytest.param(False, False, id="ecrire"),
])
def test_le_drapeau_de_versionnage_atteint_TOUS_les_lots_du_plan(
        tmp_path, demande, attendu):
    """Les deux volets d'un seul mecanisme, mesures sur la MEME fabrique.

    Le drapeau part sur **tous** les lots et non sur le premier : le plan du
    temps 2 est une boucle, et un drapeau pose hors de la boucle donnerait un
    premier lot versionne et deux lots ecrases.
    """
    parcours = _parcours(tmp_path)
    confirme = confirmation.preparer_le_plan(
        parcours.rapport, [objet for _c, _b, objet in parcours.documents])
    plan_ecriture = parcours.plan_d_ecriture(confirme,
                                             nouvelle_version=demande)
    assert len(plan_ecriture.lots) == 3
    assert [lot.nouvelle_version for lot in plan_ecriture.lots] == \
        [attendu] * 3


def test_l_issue_de_versionnage_est_le_SEUL_chemin_qui_pose_le_drapeau(
        tmp_path, monkeypatch):
    """`trancher` traduit l'issue en drapeau, et rien d'autre ne le pose.

    Le parcours est interroge par son point d'entree reel -- l'issue --, pas en
    appelant `ecrire(nouvelle_version=True)` soi-meme : « un cablage mesure en
    appelant soi-meme la methode cablee ne mesure que la methode ».
    """
    parcours = _parcours(tmp_path)
    parcours.confirmation = type("_Feinte", (), {
        "plan": confirmation.preparer_le_plan(
            parcours.rapport, [o for _c, _b, o in parcours.documents]),
        "slugs_retenus": {},
    })()
    vus: list[bool] = []
    monkeypatch.setattr(parcours, "ecrire",
                        lambda **kw: vus.append(kw.get("nouvelle_version",
                                                       False)))
    choix = confirmation.issues_de_la_confirmation(
        plan(**{LOT_CIBLE: DEJA_ECRITES}))
    parcours.trancher(choix.issue(confirmation.ISSUE_NOUVELLE_VERSION))
    parcours.trancher(choix.issue(confirmation.ISSUE_ECRIRE))
    assert vus == [True, False]


def test_la_LIGNE_D_EAU_du_projet_part_au_plan_meme_sans_versionnage(tmp_path):
    """`EPIC11-ARB-92` : un rang retire ne se rend qu'en queue, sur demande.

    Le manifeste porte cette ligne d'eau, et il part **toujours** -- pas
    seulement quand `nouvelle_version` est pose. Deux regimes de resolution du
    meme rang selon le chemin d'appel est exactement ce
    qu'`EPIC11-ARB-108` interdit.
    """
    parcours = _parcours(tmp_path)
    (parcours.dossier_projet / "project.json").write_text(
        '{"project_id": "projet_demo", "lots": []}', encoding="utf-8")
    confirme = confirmation.preparer_le_plan(
        parcours.rapport, [o for _c, _b, o in parcours.documents])
    for demande in (False, True):
        plan_ecriture = parcours.plan_d_ecriture(confirme,
                                                 nouvelle_version=demande)
        assert plan_ecriture.manifest_du_projet == {
            "project_id": "projet_demo", "lots": []}


def test_le_comptage_du_disque_du_parcours_LIT_le_dossier_du_lot(tmp_path):
    """La table `lot_id -> frames` que `E3-6` recoit, mesuree sur le disque.

    Trois lots, la cible au **milieu**, et un dossier peuple pour elle seule :
    un comptage qui viserait le premier dossier, ou qui sommerait les trois,
    rendrait une table differente.
    """
    parcours = _parcours(tmp_path, avec_cadence=True)
    lots = [lot.lot_id for lot in parcours.rapport.lots]
    assert len(lots) == 3, lots
    cible = lots[1]
    entree = parcours._document_du_lot(cible)
    assert entree is not None
    dossier = parcours._dossier_du_lot(
        atelier_scan_parcours._payload_du_lot(entree[1], cible))
    assert dossier is not None
    dossier.mkdir(parents=True, exist_ok=True)
    for rang in range(DEJA_ECRITES):
        (dossier / f"frame_{rang:03d}{naming.EXTRACTED_FRAME_SUFFIX}").write_bytes(b"x")
    comptes = parcours.frames_deja_ecrites()
    assert comptes == {lots[0]: 0, cible: DEJA_ECRITES, lots[2]: 0}


# ===========================================================================
# Famille 3 -- AUCUNE regle de rang en TUI, et son volet symetrique
# ===========================================================================

#: Le vocabulaire du versionnage, tel que le coeur le redige. Aucun de ces noms
#: n'a le droit d'apparaitre dans `tui/` : le paquet **appelle** la regle, il ne
#: la reecrit pas (`EPIC11-ARB-108`, « il n'y a pas de mecanisme different par
#: objet »).
VOCABULAIRE_DES_RANGS = (
    "resolve_output_frames_version_rank",
    "resolve_scan_version_rank",
    "format_version_suffix",
    "prochain_rang",
    "ligne_d_eau",
    "RANG_ORIGINE",
    "VERSION_RANK_MIN",
    "VERSION_RANK_MAX",
)


def test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG():
    """Comptage a **zero** sur le paquet entier, prose comprise.

    Une frontiere negative est le seul moyen d'attraper la reintroduction d'un
    defaut : aucun test positif ne verrait revenir un `_v2` compose a la main
    dans un ecran.
    """
    trouves = []
    for source in sorted(PAQUET_TUI.rglob("*.py")):
        texte = source.read_text(encoding="utf-8")
        for mot in VOCABULAIRE_DES_RANGS:
            if mot in texte:
                trouves.append(f"{source.name}: {mot}")
    assert trouves == [], trouves


def test_le_vocabulaire_des_rangs_EXISTE_bien_au_coeur():
    """Le volet symetrique, sans quoi la frontiere ci-dessus ne mesure rien.

    Un nom renomme au coeur ferait passer la frontiere negative pour la
    mauvaise raison : elle compterait a zero un vocabulaire qui n'existe plus.
    """
    absents = [mot for mot, source in (
        ("resolve_output_frames_version_rank", scan_output_frames),
        ("resolve_scan_version_rank", scan_output_frames),
        ("format_version_suffix", naming),
        ("prochain_rang", version_ranks),
        ("ligne_d_eau", version_ranks),
        ("RANG_ORIGINE", version_ranks),
        ("VERSION_RANK_MIN", naming),
        ("VERSION_RANK_MAX", naming),
    ) if not hasattr(source, mot)]
    # `resolve_scan_version_rank` vit dans `scan_ingest`, pas dans
    # `scan_output_frames` : on le cherche la ou il est plutot que de le
    # declarer absent.
    if absents == ["resolve_scan_version_rank"]:
        from mixed_media_utility import scan_ingest
        absents = [] if hasattr(scan_ingest, "resolve_scan_version_rank") \
            else absents
    assert absents == [], absents


def test_le_drapeau_TRAVERSE_la_TUI_sans_etre_interprete():
    """`LotAEcrire.nouvelle_version` part au coeur **verbatim**.

    Mesure a l'AST plutot qu'au texte : ce qui compte est que le mot-cle
    `nouvelle_version=` de l'appel au coeur soit alimente par l'attribut du
    lot, et non par une expression qui le recalculerait.
    """
    source = (PAQUET_TUI / "atelier_scan_ecriture.py").read_text(
        encoding="utf-8")
    arbre = ast.parse(source)
    passages = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        for mot in noeud.keywords:
            if mot.arg == "nouvelle_version":
                passages.append(ast.dump(mot.value))
    assert passages == [ast.dump(ast.parse("lot.nouvelle_version",
                                           mode="eval").body)], passages


def test_la_TUI_ne_compose_AUCUN_suffixe_de_version_a_la_main():
    """Aucun `_v2` litteral, aucun `f"{slug}_v{...}"` dans le paquet.

    C'est le geste que `io/version_ranks.py` existe pour rendre inutile, et
    celui qu'une session pressee reecrit en trois caracteres.
    """
    motifs = ("_v{", '"_v"', "'_v'", "_v%")
    trouves = [f"{source.name}: {motif}"
               for source in sorted(PAQUET_TUI.rglob("*.py"))
               for motif in motifs
               if motif in source.read_text(encoding="utf-8")]
    assert trouves == [], trouves


# ===========================================================================
# Le raccord aval -- ce que le plan de la TUI promet au coeur
# ===========================================================================

def test_le_plan_du_temps_2_porte_les_DEUX_champs_que_le_coeur_attend():
    """`nouvelle_version` sur le lot, `manifest_du_projet` sur le plan.

    Les deux sont necessaires et aucun ne suffit : le drapeau dit « versionne »,
    la ligne d'eau dit **quel rang** est libre. Un plan qui porterait le premier
    sans la seconde resoudrait ses rangs sur le seul disque, donc rendrait un
    rang deja retire sans que personne ne l'ait demande.
    """
    champs = atelier_scan_ecriture.LotAEcrire.__dataclass_fields__
    assert "nouvelle_version" in champs
    assert champs["nouvelle_version"].default is False
    plan_champs = atelier_scan_ecriture.PlanDEcriture.__dataclass_fields__
    assert "manifest_du_projet" in plan_champs


# ===========================================================================
# Le refus du coeur sur un `lot_id` lu du PAPIER -- jamais une trace nue
# ===========================================================================

def test_le_refus_de_lot_id_INCONSISTANT_est_JOUE_et_pas_seulement_nomme(
        tmp_path):
    """Finding `F4` de la couche de reprise de la vague 4 : le banc voisin
    ne joue **jamais** le regime qu'il nomme.

    Sonde posee sur sa fabrique exacte : ses trois lots levent `ValueError`
    (payload sans lot), **jamais** la `LotInconsistencyError` annoncee. Le
    correctif de `_dossier_du_lot` -- rattraper `RuntimeError` et pas seulement
    `ValueError` -- est juste, et le vrai regime a bien ete reproduit ; c'est
    sa MESURE qui etait fausse. Revenir a `except ValueError` survivait
    (mutant `M3-RUNTIMEERROR`).

    Ce banc-ci joue le regime. Le payload porte ses trois champs -- sans quoi
    `dossier_de_sortie` refuse plus tot, par `ValueError`, et l'on mesurerait
    de nouveau l'autre branche -- et son `lot_id` ne se recompose ni de son
    rush ni de sa cadence.

    **Le volet symetrique n'est pas decoratif** : un `lot_id` qui SE recompose
    doit rendre un dossier. Sans lui, un `_dossier_du_lot` qui rendrait `None`
    pour tout serait vert, et il n'y aurait plus de mesure du tout.
    """
    parcours = _parcours(tmp_path)

    inconsistant = {"rush_id": "monrush", "fps_target": 25,
                    "lot_id": "ceci-ne-se-recompose-pas"}
    # Le refus qu'on veut voir traverser est bien celui-la, et il herite de
    # `RuntimeError` : le banc le VERIFIE plutot que de le supposer, sans quoi
    # un changement de hierarchie le rendrait muet.
    with pytest.raises(scan_output_frames.LotInconsistencyError):
        scan_output_frames.derive_lot_dir_slug(**inconsistant)
    assert issubclass(scan_output_frames.LotInconsistencyError, RuntimeError)
    assert not issubclass(scan_output_frames.LotInconsistencyError, ValueError)

    # Et le point de jugement ne tombe pas : il rend `None`, ce qui se lit
    # « je ne sais pas ou ce lot ecrit ».
    assert parcours._dossier_du_lot(inconsistant) is None

    # Volet symetrique : un `lot_id` qui se recompose rend un dossier.
    coherent = {"rush_id": "monrush", "fps_target": 25,
                "lot_id": "monrush_25"}
    assert parcours._dossier_du_lot(coherent) is not None


def test_un_lot_id_INCONSISTANT_ne_fait_pas_tomber_le_point_de_jugement(
        tmp_path):
    """Trouve en cablant `EPIC11-ARB-133`, et corrige dans le meme mouvement.

    `_dossier_du_lot` ne rattrapait que `ValueError`. Mais
    `scan_output_frames.derive_lot_dir_slug` refuse aussi un `lot_id` qui ne se
    recompose pas de son rush et de sa cadence, par une
    `LotInconsistencyError` qui herite de **`RuntimeError`** -- et ce `lot_id`
    est lu **sur du papier scanne**, donc il arrive de l'exterieur. Le refus
    traversait jusqu'a l'ecran en trace Python nue.

    **Ce que ce banc mesure REELLEMENT, dit plutot que tu** (finding `F4`).
    Sa fabrique ne joue PAS la `LotInconsistencyError` que le paragraphe
    ci-dessus decrit : ses trois lots n'ont pas de payload de lot du tout, donc
    ils partent par `ValueError`. Revenir a `except ValueError` seul le laisse
    vert. Ce qu'il mesure vraiment, et qui vaut d'etre garde, c'est que les
    deux chemins de derivation -- le comptage et le plan -- rendent `None`
    plutot que de faire tomber `E3-6`, et qu'aucune issue de versionnage n'est
    offerte sans dossier.

    Le regime nomme est joue par le banc juste au-dessus.
    """
    parcours = _parcours(tmp_path)
    # Les deux chemins qui derivent un dossier de sortie, mesures ensemble :
    # celui du comptage (neuf) et celui du plan (deja la).
    comptes = parcours.frames_deja_ecrites()
    assert set(comptes.values()) == {0}
    confirme = confirmation.preparer_le_plan(
        parcours.rapport, [o for _c, _b, o in parcours.documents])
    plan_ecriture = parcours.plan_d_ecriture(confirme)
    assert [lot.dossier for lot in plan_ecriture.lots] == [None, None, None]
    # Et rien n'a ete offert a versionner : sans dossier, rien n'est deja ecrit.
    assert confirmation.ISSUE_NOUVELLE_VERSION not in [
        issue.cle for issue in
        confirmation.issues_de_la_confirmation(
            confirmation.preparer_le_plan(
                parcours.rapport,
                [o for _c, _b, o in parcours.documents],
                frames_deja_ecrites=comptes)).issues]
