# -*- coding: utf-8 -*-
"""Story 11.6, lot G -- `E3-9`, calibrer une chaine (AC 8).

**Ce banc et lui seul mesure le lot G.** La regle de decoupage de la fiche est
stricte, et elle a ete payee trois fois sur ce depot : « aucun lot ne partage un
fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier.

**Le nom du fichier est un piege de collecte, pas un detail.** Aucun des trois
dossiers de tests n'a d'`__init__.py` : deux fichiers homonymes rendent le meme
nom de module et pytest **interrompt la collecte de la suite entiere**.
`tests/unit/test_scan_calibrate_command.py` existe deja et mesure la voie CLI ;
celui-ci porte un nom different, verifie globalement unique.

**Le coeur n'est pas simule.** Les passes de ce banc appellent le vrai
`scan_calibrate.calibrer_la_chaine` sur un vrai projet, avec de vrais fichiers
de profil ecrits par `io.calibration_profile.write_profile`. Le **seul** point
substitue est `scan_calibrate._fit_lot_correction` -- le point de substitution
que le module de coeur nomme lui-meme dans sa docstring, l'ajustement etant
eprouve contre les vrais producteurs dans les fichiers de la moitie couleur. Un
banc qui simulerait `write_profile` ne mesurerait **rien** de l'AC 8 : la regle
de collision vit dedans, et c'est elle que cet ecran a interdiction de
reecrire.

**Regle des fabriques** (`CLAUDE.md`), appliquee ici a ses trois points :

1. **au moins deux elements DISTINGUABLES** -- les trois profils poses different
   par leur etiquette, leur nom de fichier, leur `chain_id` et leur cardinal de
   pastilles. Un remplissage uniforme rendrait toute permutation invisible
   (mutant `M33`, story 5.6) ;
2. **la cible n'est pas en premiere position** -- un `find` fautif qui rend le
   premier profil se demasque (mutant `M25`, story 5.7) ;
3. **trois elements et la cible AU MILIEU** -- la collision porte sur
   `beta.json`, deuxieme des trois (mutant `continue` -> `break` de la 11.4b,
   paye trois fois).

**Et la position se verifie sur la liste que le CODE parcourt.** Ce piege a ete
paye deux fois. La liste que le code de ce lot parcourt est celle de
`profils_du_projet`, c'est-a-dire un `sorted(dossier.iterdir())` :
:func:`test_G6_la_cible_est_au_MILIEU_de_la_liste_que_le_code_parcourt` la
mesure **sur cette liste-la** et non sur l'ordre ou la fabrique ecrit.

**Et le test mesure QUEL fichier a ete ecrit**, jamais qu'un fichier l'a ete :
une empreinte posee sur le mauvais radical reussit aussi. Les trois issues de la
collision se distinguent par le fichier qu'elles produisent et par ceux qu'elles
laissent intacts -- mesures aux **inodes** et au `st_mtime_ns`, parce qu'« un
condensat ne prouve pas qu'un fichier n'a pas ete touche » quand la fixture est
deterministe.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

_RACINE = Path(__file__).resolve().parents[3]
for _chemin in (str(_RACINE / "src"), str(_RACINE / "tests" / "unit")):
    if _chemin not in sys.path:
        sys.path.insert(0, _chemin)

from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility import scan_calibrate  # noqa: E402
from mixed_media_utility.io import calibration_profile  # noqa: E402
from mixed_media_utility.gui.depot_projets import creer_projet  # noqa: E402
from mixed_media_utility.io import profile_designation  # noqa: E402
from mixed_media_utility.tui import atelier_scan, jetons  # noqa: E402
from mixed_media_utility.tui import atelier_scan_calibrate as cal  # noqa: E402
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin  # noqa: E402
from mixed_media_utility.tui.ecran_projet import CoutureExplorateur  # noqa: E402
from mixed_media_utility.tui.panneau import (ChoixExclusif, Issue,  # noqa: E402
                                             PanneauMalForme)

import test_calibration_page_source as couleur  # noqa: E402

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Les trois profils deja poses dans le projet, **distinguables sur quatre
#: axes** et ranges ici dans l'ordre ou le dossier les listera. La cible est le
#: **second** des trois : ni le premier, ni le dernier.
PROFILS_POSES = (
    {"etiquette": "alpha", "chain_id": "300-tiff-aaaaaaaaaaaa", "patchs": 12},
    {"etiquette": "beta", "chain_id": "300-tiff-bbbbbbbbbbbb", "patchs": 24},
    {"etiquette": "gamma", "chain_id": "900-png-cccccccccccc", "patchs": 18},
)

#: Le rang de la cible : **le second des trois**.
RANG_DE_LA_CIBLE = 1

#: L'etiquette que l'operateur saisit sur `E3-9`. Elle vise le radical du profil
#: du **milieu**, donc elle entre en collision avec lui -- et avec lui seul.
ETIQUETTE_EN_COLLISION = PROFILS_POSES[RANG_DE_LA_CIBLE]["etiquette"]

#: Le dpi declare des passes de ce banc.
DPI = 600


# ===========================================================================
# Fabriques -- de vrais artefacts, jamais des mocks
# ===========================================================================

def _page_de_scan(tmp_path: Path, nom: str = "scan-calibration") -> Path:
    """Un dossier de scan ingerable : une page synthetique, sans QR ni marqueur.

    Meme fabrique que le banc CLI de `calibrate` (`_write_scan_folder`) : c'est
    ce qui garantit que les deux voies -- terminal et TUI -- calibrent **la meme
    chose**, et donc que l'AC 10.2 (« la TUI est un appelant de plus ») se
    mesure sur des entrees identiques.
    """
    dossier = tmp_path / nom
    dossier.mkdir()
    assert cv2.imwrite(str(dossier / "page.tif"),
                       np.full((400, 600, 3), 200, dtype=np.uint8))
    return dossier


def _correction():
    """Une correction **ajustee par le vrai producteur**, sur un raster synthetique.

    La forme du lot est celle du profil : une fixture ou les deux divergeraient
    serait precisement l'incoherence que le point d'entree a pour tache
    d'eviter.
    """
    profil = couleur._calibration_profile()
    return cc.LotCorrection(
        source_page_id="calibration-0",
        template_id=couleur.TEMPLATE,
        profile=profil,
        correction_form_id=profil.correction_id,
        read_patch_count=26,
        retained_patch_count=24,
    )


@pytest.fixture
def coeur_ajuste(monkeypatch):
    """Substituer le **seul** point que ce banc n'exerce pas : l'ajustement.

    `scan_calibrate._fit_lot_correction` est nomme comme point de substitution
    des bancs par la docstring du module de coeur lui-meme. Tout le reste --
    ingestion, detection, derive d'identite, composition du document, ecriture
    atomique et **regle de collision** -- est le vrai code.
    """
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: _correction())


def _document(chain_id: str, *, etiquette: str, patchs: int) -> dict:
    """Un document de profil **valide au sens du coeur**, jamais un mock.

    Il passe par `validate_profile_document` a l'ecriture : un document
    fabrique a la main qui ne passerait pas cette porte mesurerait un ecran qui
    ne verra jamais ce document en production.
    """
    return {
        "schema_version": calibration_profile.PROFILE_SCHEMA_VERSION,
        "chain_id": chain_id,
        "correction_form_id": calibration_profile.CORRECTION_FORM_AFFINE_ID,
        "coefficients": {
            "stage_a": [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
            "stage_m": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "read_patch_count": patchs + 2,
        "retained_patch_count": patchs,
        "ink_floor_excluded": True,
        "source_page_id": f"page-{chain_id}",
        "template_id": "tpl-de-banc",
        "label": etiquette,
        "acceptance": {},
    }


def _projet(tmp_path: Path, *, profils=PROFILS_POSES, nom="projet") -> Path:
    """Un projet reel **persiste**, avec ses trois profils ecrits par le coeur.

    `creer_projet` et non `ensure_project_layout` seul : un projet sans
    `project.json` n'a pas de section `color` a ecrire, si bien que
    `record_designated_profile` y est un no-op silencieux
    (`_rewrite_color_section` rend `False`). C'est le regime d'un projet que la
    TUI n'a pas encore persiste, et ce n'est pas celui d'un atelier -- on
    n'ouvre un atelier que sur un projet ouvert.

    `write_profile` et non un `json.dump` : le radical de chaque fichier est
    celui que le coeur compose depuis l'etiquette, et l'ecrire a la main
    fixerait un nom que la production ne produirait pas.
    """
    projet = creer_projet(tmp_path, nom).chemin
    for profil in profils:
        calibration_profile.write_profile(
            projet, _document(profil["chain_id"],
                              etiquette=profil["etiquette"],
                              patchs=profil["patchs"]))
    return projet


def _formulaire(dossier_de_scan: Path, *, etiquette: str = "",
                commentaire: str = "", defaut: bool = False
                ) -> cal.FormulaireDeCalibration:
    """Le formulaire de `E3-9`, rempli comme l'operateur le remplirait.

    Le scan passe par `atelier_scan.designer`, donc par
    `scan_ingest.mesurer_la_source` : c'est le meme geste que l'explorateur
    declenche sur `E3-1` et sur ce sixieme site.
    """
    return cal.FormulaireDeCalibration(
        scan=atelier_scan.designer(dossier_de_scan), dpi=str(DPI),
        etiquette=etiquette, commentaire=commentaire,
        devient_le_defaut=defaut)


class Interrogateur:
    """Le `poser_la_collision` du banc : il compte, et il repond ce qu'on lui dit.

    Il porte son compte d'appels parce que **l'absence d'appel est un signal**
    (AC 8.1) : le coeur dit « recalibration » en ne posant aucune question.
    """

    def __init__(self, reponse: str = cal.CLE_NOM_DIFFERENCIE) -> None:
        self.reponse = reponse
        self.collisions: list[cal.CollisionDeProfil] = []

    def __call__(self, collision: cal.CollisionDeProfil) -> str:
        self.collisions.append(collision)
        return self.reponse


def _releve(projet: Path) -> dict[str, tuple[int, int, bytes]]:
    """Nom de fichier -> (inode, `st_mtime_ns`, octets) de chaque profil.

    **Aux inodes et au `st_mtime_ns`, jamais au seul condensat** : la fixture
    est deterministe, donc une reecriture rend exactement les memes octets, et
    un condensat egal ne prouve **pas** qu'un fichier n'a pas ete touche
    (`CLAUDE.md`, vague 3). Les octets restent mesures en plus, parce qu'un
    contenu change est l'autre moitie de la question.
    """
    dossier = cal.dossier_des_profils(projet)
    return {chemin.name: (chemin.stat().st_ino, chemin.stat().st_mtime_ns,
                          chemin.read_bytes())
            for chemin in sorted(dossier.iterdir())}


#: Les valeurs que `E3-1` et `E3-9` DESSINENT, nommees ici une seule fois.
#: Elles etaient tapees en clair, donc recopiees d'un dessin que ce banc
#: citait sans jamais l'ouvrir. Confrontees a leur source en fin de fichier.
PIED_DU_PALIER = "Q quitter"
PREFIXE_DU_BANDEAU = "mmu · projet_demo · "


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", PIED_DU_PALIER), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _sans_retours(texte: str) -> str:
    """Le texte, blancs replies -- pour comparer a une phrase du coeur.

    `jetons.envelopper` coupe une phrase longue sur plusieurs lignes : la
    comparer telle quelle a la phrase levee ferait rougir une mise en forme
    correcte. Ce qui doit etre mesure est que **rien n'a ete reformule**, pas
    que rien n'a ete replie -- le repli est precisement le travail de l'ecran.
    """
    return " ".join(texte.split())


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees."""
    return jetons.texte_affiche(str(ecran._corps.content))


def _rendu(ecran, banc, app=None, **kwargs) -> str:
    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return _texte(ecran)

    return banc(app or _app(ecran, **kwargs), scenario)


def _ecran(**kwargs) -> cal.EcranCalibrerLaChaine:
    """`E3-9`, avec son rappel de calibration **requis** (finding `K3`)."""
    kwargs.setdefault("calibrer", lambda formulaire: None)
    return cal.EcranCalibrerLaChaine(**kwargs)


# ===========================================================================
# G1 -- les DEUX situations de l'AC 8.1, mesurees separement
# ===========================================================================

def test_G1_une_RECALIBRATION_ne_pose_AUCUNE_question(tmp_path, coeur_ajuste):
    """AC 8.1, premiere situation : meme chaine, meme radical.

    Le coeur ne pose **aucune** question a une recalibration -- « poser la
    question a chaque recalibration serait une invite qui apprend a repondre
    oui sans lire » (`EPIC5-ARB-99`) --, et c'est exactement ce que l'ecran lit
    pour distinguer les deux situations : le relais n'est pas appele.

    La passe est jouee **deux fois** sur le meme scan et le meme projet : la
    seconde ecrit par-dessus la premiere.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    interroge = Interrogateur()

    premiere = cal.consigner(projet, _formulaire(scan),
                             poser_la_collision=interroge)
    seconde = cal.consigner(projet, _formulaire(scan),
                            poser_la_collision=interroge)

    assert premiere.a_ecrit and seconde.a_ecrit
    assert interroge.collisions == [], (
        "une recalibration de la MEME chaine n'est pas une collision : le "
        "coeur ne pose pas la question, et l'ecran n'en invente pas une")
    # Le meme fichier, les deux fois : c'est ce qui fait la recalibration.
    assert premiere.chemin == seconde.chemin
    assert premiere.recalibration is False, (
        "la premiere passe ecrit un profil NEUF : rien n'est remplace")
    assert seconde.recalibration is True
    assert seconde.date_precedente and seconde.date_ecrite


def test_G1_la_recalibration_se_DIT_sans_triangle_et_sans_question(
        tmp_path, coeur_ajuste, banc):
    """AC 8.1 : « L'ecran le **dit** [...] sans `▲`, sans question ».

    L'ecart `H9` de la fiche : la maquette annoncait `▲ écrasement` la ou le
    coeur voit un remplacement voulu. La mesure porte donc sur les **deux**
    moities -- ce que la ligne dit, et le glyphe qu'elle ne porte pas.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    interroge = Interrogateur()
    cal.consigner(projet, _formulaire(scan), poser_la_collision=interroge)
    passe = cal.consigner(projet, _formulaire(scan),
                          poser_la_collision=interroge)

    ecran = _ecran(dossier=projet)
    ecran.annoncer(passe)
    rendu = _rendu(ecran, banc)

    assert cal.LIBELLE_REMPLACE in rendu
    assert cal.PHRASE_RECALIBRATION.format(date=passe.date_precedente) in rendu
    # **La chaine est NOMMEE** (AC 8.1), et elle vient du coeur : elle a
    # traverse par le rappel de nommage, elle n'est pas recomposee ici.
    assert passe.chaine and f"{cal.LIBELLE_CHAINE}" in rendu
    assert passe.chaine in rendu
    assert passe.chaine == passe.profil.chain_id
    table = jetons.glyphes(False)
    assert table["substitute"] not in rendu, rendu
    # La ligne d'etat porte **les deux dates**, et aucun avertissement.
    etat = _etat(ecran, banc)
    assert etat == cal.ETAT_RECALIBRATION.format(
        ancienne=passe.date_precedente, nouvelle=passe.date_ecrite)
    assert table["substitute"] not in etat


def _etat(ecran, banc) -> str:
    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return ecran.etat()

    return banc(_app(ecran), scenario)


def test_G1_une_COLLISION_est_POSEE_par_le_coeur_et_pas_par_l_ecran(
        tmp_path, coeur_ajuste):
    """AC 8.1, seconde situation : une autre chaine sous le meme radical.

    L'etiquette `beta` vise le radical du profil du **milieu**, qui porte une
    autre identite de chaine. Le coeur appelle alors `confirm_overwrite`, et
    c'est **le seul signal** : l'ecran ne compare aucune identite lui-meme.

    L'occupant et le radical voyagent **verbatim** (`EPIC11-ARB-30`).
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    interroge = Interrogateur(cal.CLE_NOM_DIFFERENCIE)

    passe = cal.consigner(projet,
                          _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
                          poser_la_collision=interroge)

    assert len(interroge.collisions) == 1, interroge.collisions
    collision = interroge.collisions[0]
    assert collision.radical == ETIQUETTE_EN_COLLISION
    assert collision.occupant == PROFILS_POSES[RANG_DE_LA_CIBLE]["chain_id"]
    assert passe.collision == collision
    # **Les deux situations ne se confondent pas** : une collision n'est pas
    # une recalibration, et c'est le volet symetrique du test precedent.
    assert passe.recalibration is False


# ===========================================================================
# G2 -- les TROIS issues de la vraie collision
# ===========================================================================

def test_G2_la_collision_ouvre_EXACTEMENT_trois_issues():
    """AC 8.1 : « un `ChoixExclusif` a **trois** issues ».

    L'ensemble est mesure **exactement** : « une assertion positive laisse
    passer toute divergence supplementaire ». Une quatrieme issue -- ou une
    disparue -- ferait rougir ici, ce qu'un `in` n'aurait pas fait.
    """
    choix = cal.choix_de_la_collision(
        cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb", radical="beta"))

    assert [issue.cle for issue in choix.issues] == [
        cal.CLE_NOM_DIFFERENCIE, cal.CLE_ECRASER, cal.CLE_ANNULER]


def test_G2_aucune_issue_n_est_preselectionnee_et_une_SEULE_ecrase():
    """AC 8.1 et `EPIC11-ARB-7` : « aucune n'est preselectionnee ».

    Et le curseur part sur **celle qui n'ecrase pas** -- l'empreinte
    differenciante, qui est le defaut du coeur (`EPIC5-ARB-99` : « Hors
    terminal, le defaut est l'empreinte, jamais l'ecrasement »). Un curseur pose
    sur l'ecrasement rendrait la destruction atteignable en une frappe.
    """
    choix = cal.choix_de_la_collision(
        cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb", radical="beta"))

    assert choix.retenue is None
    assert choix.issues[choix.curseur].cle == cal.CLE_NOM_DIFFERENCIE
    assert {issue.cle for issue in choix.issues if issue.ecrit} == {
        cal.CLE_ECRASER}, [(i.cle, i.ecrit) for i in choix.issues]
    assert choix.action_qui_ecrit.cle == cal.CLE_ECRASER


def test_G2_l_issue_qui_ecrase_NOMME_ce_qu_elle_ecrase():
    """`EPIC11-ARB-89` : l'ecriture destructive est **consciente**.

    Un consentement qui ne nomme pas ce qu'il detruit ne porte sur rien. Et le
    cas ou le coeur n'a pas su lire l'identite est **distinct** : annoncer une
    chaine qu'on n'a pas lue serait pire que de dire qu'on ne l'a pas lue.
    """
    nommee = cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb",
                                   radical="beta")
    illisible = cal.CollisionDeProfil(occupant=None, radical="beta")

    assert "300-tiff-bbbbbbbbbbbb" in cal.libelle_de_l_ecrasement(nommee)
    assert cal.libelle_de_l_ecrasement(illisible) == (
        cal.LIBELLE_ECRASER_ILLISIBLE)
    assert cal.libelle_de_l_ecrasement(illisible) != (
        cal.libelle_de_l_ecrasement(nommee))


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G2_l_ecran_de_collision_rend_UNE_LIGNE_par_issue_avec_la_fleche_seule(
        banc, ascii_seul):
    """`EPIC11-ARB-126` : « **Flèche seule !** »

    Une liste d'issues n'est pas une liste a cocher : aucun des quatre glyphes
    de retenue n'y a sa place. Le rendu vient de `ChoixExclusif.rendu()`, qui ne
    pose que la fleche depuis `EPIC11-ARB-45` -- il n'est pas reecrit ici.
    """
    collision = cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb",
                                      radical="beta")
    ecran = cal.EcranCollisionDeProfil(collision, retenir=lambda issue: None)
    rendu = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))

    table = jetons.glyphes(ascii_seul)
    assert rendu.count(table["curseur"]) == 1, rendu
    for retenue in ("coche", "decoche", "exclusif-retenu", "exclusif-libre"):
        assert table[retenue] not in rendu, (retenue, rendu)
    for issue in ecran.choix.issues:
        attendu = (jetons.replier_ascii(issue.libelle) if ascii_seul
                   else issue.libelle)
        assert attendu in rendu, (issue.cle, rendu)
    # Le radical et l'occupant, **verbatim**.
    assert "beta" in rendu and "300-tiff-bbbbbbbbbbbb" in rendu


def test_G2_le_curseur_peint_la_ligne_de_l_issue_qu_il_designe(banc):
    """Le curseur **rendu** et le curseur du modele designent la meme issue.

    `rang_du_curseur` est derive du nombre de lignes de tete et non compte a la
    main : deux comptes divergeraient a la premiere ligne inseree, et le curseur
    se peindrait sur une autre issue sans que rien ne le dise. La cible est
    posee **au milieu** des trois -- ni la premiere, ni la derniere.
    """
    collision = cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb",
                                      radical="beta")
    ecran = cal.EcranCollisionDeProfil(collision, retenir=lambda issue: None)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran.traiter("down")
        ecran.rafraichir()
        lignes = _texte(ecran).splitlines()
        return lignes, ecran.rang_du_curseur()

    lignes, rang = banc(_app(ecran), scenario)
    assert ecran.choix.curseur == 1
    assert jetons.glyphes(False)["curseur"] in lignes[rang]
    assert cal.LIBELLE_ECRASER_CHAINE.format(
        occupant="300-tiff-bbbbbbbbbbbb") in lignes[rang]


# ===========================================================================
# G3 -- le troisieme chemin du coeur n'aboutit JAMAIS a un ecran sans issue
# ===========================================================================

def _empreinte_du_projet(projet: Path) -> Path:
    """Le fichier `beta-<empreinte>.json` produit par une premiere passe."""
    trouves = sorted(cal.dossier_des_profils(projet).glob(
        f"{ETIQUETTE_EN_COLLISION}-*.json"))
    assert len(trouves) == 1, trouves
    return trouves[0]


def test_G3_le_chemin_SANS_ISSUE_du_coeur_est_ferme_par_deux_issues(
        tmp_path, coeur_ajuste, banc):
    """AC 8.3 -- le refus qui n'offre rien est ferme, et il est ATTEINT.

    Le coeur porte un troisieme chemin : « l'empreinte differenciante n'a pas
    separe les deux ; ecraser ferait perdre un profil qu'aucune autre trace ne
    porte » (`io/calibration_profile.py:998-1002`). C'est un
    `ProfileValidationError` **sans issue**.

    Il est atteint pour de vrai ici : une premiere passe pose
    `beta-<empreinte>.json`, dont on remplace ensuite l'identite de chaine par
    une troisieme. La passe suivante voit alors ses **deux** chemins occupes.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    cal.consigner(projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
                  poser_la_collision=Interrogateur(cal.CLE_NOM_DIFFERENCIE))
    empreinte = _empreinte_du_projet(projet)
    document = json.loads(empreinte.read_text(encoding="utf-8"))
    document["chain_id"] = "1200-tiff-dddddddddddd"
    empreinte.write_text(
        calibration_profile.serialize_profile(document), encoding="utf-8")
    avant = _releve(projet)

    passe = cal.consigner(
        projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
        poser_la_collision=Interrogateur(cal.CLE_NOM_DIFFERENCIE))

    assert passe.refus is not None and not passe.a_ecrit
    assert passe.motif == scan_calibrate.REFUS_PROFIL_NON_ECRIT
    # **Aucun profil n'a ete ecrit** : ni octets, ni inode, ni mtime ne bougent.
    assert _releve(projet) == avant

    ecran = cal.EcranRefusDeCalibration(passe, retenir=lambda issue: None)
    rendu = _rendu(ecran, banc)
    assert len(ecran.choix.issues) >= 2
    assert [issue.cle for issue in ecran.choix.issues] == [
        cal.CLE_RENOMMER, cal.CLE_ABANDONNER]
    assert cal.LIBELLE_RENOMMER in rendu
    # Le message du coeur, **verbatim** : le rendu en est une sur-chaine, aux
    # seuls retours a la ligne pres (`EPIC11-ARB-30` -- la TUI met en forme,
    # elle n'interprete pas, ne resume pas, ne requalifie pas).
    assert _sans_retours(str(passe.refus)) in _sans_retours(rendu)


def test_G3_un_point_de_jugement_a_ZERO_issue_est_IMPOSSIBLE():
    """Le volet symetrique : la mesure precedente regarde bien quelque chose.

    Sans lui, « au moins deux issues » serait une declaration. L'invariant est
    leve par `ChoixExclusif.__post_init__` et n'est pas reecrit ici -- ni une
    liste vide, ni une liste a une seule issue ne se construisent.
    """
    with pytest.raises(PanneauMalForme):
        ChoixExclusif([])
    with pytest.raises(PanneauMalForme):
        ChoixExclusif(cal.issues_de_l_impasse()[:1])
    assert len(cal.issues_de_l_impasse()) >= 2


def test_G3_le_refus_ne_dit_JAMAIS_echec(tmp_path, monkeypatch, banc):
    """`DESIGN.md` section 9 : un refus se nomme, il ne dit pas « echec ».

    Le cas mesure est celui de l'AC 8.7 : une page qui n'est **pas** une page de
    calibration. `calibrate` « ne se replie pas sur un profil vide » -- aucun
    profil n'est ecrit, et le refus porte son motif nomme.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    avant = _releve(projet)

    # Aucune page de calibration lue : c'est le regime de l'AC 8.7.
    monkeypatch.setattr(scan_calibrate, "_fit_lot_correction",
                        lambda *a, **k: None)
    passe = cal.consigner(projet, _formulaire(scan),
                          poser_la_collision=Interrogateur())

    assert passe.motif == scan_calibrate.REFUS_AUCUNE_PAGE_DE_CALIBRATION
    assert not passe.a_ecrit
    assert _releve(projet) == avant

    ecran = cal.EcranRefusDeCalibration(passe, retenir=lambda issue: None)
    rendu = _rendu(ecran, banc)
    assert "echec" not in rendu.lower() and "échec" not in rendu.lower()
    assert cal.TITRE_DU_REFUS in rendu


def test_G3_annuler_devant_la_collision_n_ecrit_RIEN(tmp_path, coeur_ajuste):
    """L'issue « Annuler » traverse **avant** toute ecriture.

    `EPIC5-ARB-34` : « un refus qui arrive apres une destruction n'est pas un
    refus ». `write_profile` appelle son rappel avant le `mkdir` et avant
    l'ecriture atomique, donc l'annulation ne laisse aucune trace -- mesure aux
    inodes et au `st_mtime_ns`, pas au seul contenu.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    avant = _releve(projet)

    passe = cal.consigner(
        projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
        poser_la_collision=Interrogateur(cal.CLE_ANNULER))

    assert not passe.a_ecrit
    assert isinstance(passe.refus, cal.CalibrationAnnulee)
    assert passe.issue == cal.CLE_ANNULER
    assert _releve(projet) == avant


# ===========================================================================
# G4 -- aucune regle de collision recalculee en TUI, comptage a zero
# ===========================================================================

#: Les modules du **temps 2** du Scan, ceux que l'AC 8.2 vise. Ils sont nommes
#: plutot que balayes : un balayage du paquet entier ferait rougir ce banc au
#: premier module d'un autre atelier, et la mesure porte sur le temps 2.
MODULES_DU_TEMPS_2 = ("atelier_scan_calibration", "atelier_scan_confirmation",
                      "atelier_scan_ecriture", "atelier_scan_calibrate")

#: Les ingredients de la regle de collision du coeur, **nommes un par un**.
#: `write_profile` les compose ; les composer une seconde fois en TUI ferait
#: deux regles, et l'ecart ne se verrait que sur les profils ecrits.
INGREDIENTS_DE_LA_COLLISION = frozenset({
    "profile_file_stem", "profile_path_for_document",
    "profile_collision_suffix", "slugify_label", "write_profile",
    "_chain_id_du_fichier", "_stem_avec_empreinte",
})


def _appels(chemin: Path) -> set[str]:
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        nom = (cible.attr if isinstance(cible, ast.Attribute)
               else getattr(cible, "id", None))
        if nom:
            noms.add(nom)
    return noms


def test_G4_aucun_module_du_temps_2_ne_recalcule_la_regle_de_COLLISION(
        paquet_tui):
    """AC 8.2, comptage a **zero**, a l'AST.

    « L'ecrasement conscient se demande par `confirm_overwrite`, **jamais** par
    une reimplementation de la regle de collision cote TUI. » Les sept
    ingredients de cette regle sont nommes un par un plutot que devines : un
    ensemble vague laisserait passer celui qu'on n'aurait pas pense a ecrire.
    """
    presents = [paquet_tui / f"{nom}.py" for nom in MODULES_DU_TEMPS_2]
    mesures = [chemin for chemin in presents if chemin.is_file()]
    assert mesures, (
        "aucun module du temps 2 n'est mesure : une frontiere posee sur un "
        "ensemble vide serait verte sans rien mesurer")

    fautifs = {chemin.stem: sorted(_appels(chemin) & INGREDIENTS_DE_LA_COLLISION)
               for chemin in mesures}
    assert {stem: appels for stem, appels in fautifs.items() if appels} == {}, (
        fautifs)


def test_G4_la_frontiere_precedente_mesure_bien_QUELQUE_CHOSE(paquet_tui):
    """Le volet symetrique, sans lequel le comptage a zero ne prouve rien.

    Deux moities :

    * les sept ingredients **existent** au coeur. Une frontiere qui garderait
      des noms disparus serait verte pour toujours, et c'est le mode de panne
      exact d'un comptage a zero ;
    * l'ecran passe bien `confirmer_l_ecrasement` au coeur -- c'est l'unique
      chemin que l'AC 8.2 laisse ouvert, et une frontiere qui interdirait tout
      sans qu'aucun chemin ne reste serait un blocage sec.
    """
    manquants = sorted(nom for nom in INGREDIENTS_DE_LA_COLLISION
                       if not hasattr(calibration_profile, nom))
    assert manquants == [], (
        "ces noms ne sont plus au coeur : la frontiere garde des fantomes "
        f"{manquants}")

    arbre = ast.parse(
        (paquet_tui / "atelier_scan_calibrate.py").read_text(encoding="utf-8"))
    mots_cles = {mc.arg for noeud in ast.walk(arbre)
                 if isinstance(noeud, ast.Call) for mc in noeud.keywords}
    assert {"confirmer_l_ecrasement",
            "demander_le_nom_et_le_commentaire"} <= mots_cles, sorted(mots_cles)


def test_G4_le_paquet_TUI_n_importe_JAMAIS_cli(paquet_tui):
    """AC 9.1 verifiee **explicitement** sur le module neuf (`EPIC11-ARB-67`).

    Elle est deja mesuree a l'echelle du paquet ; la reverifier ici est ce que
    l'AC demande -- « verifiee explicitement sur les modules neufs plutot que
    supposee ».
    """
    arbre = ast.parse(
        (paquet_tui / "atelier_scan_calibrate.py").read_text(encoding="utf-8"))
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            importes.add(noeud.module or "")
            importes.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.Import):
            importes.update(alias.name for alias in noeud.names)
    assert not {nom for nom in importes if nom and nom.split(".")[-1] == "cli"}


def test_G4_le_relais_n_est_appele_QUE_quand_le_coeur_pose_la_question(
        tmp_path, coeur_ajuste):
    """Le volet **comportemental** de l'AC 8.2, et il a ses deux moities.

    Sans collision, la question n'est **jamais** posee -- zero appel. Avec
    collision, elle l'est **une** fois. Un relais qui repondrait de lui-meme,
    ou qui poserait la question a chaque ecriture, echouerait a l'une des deux.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)

    muet = Interrogateur()
    cal.consigner(projet, _formulaire(scan), poser_la_collision=muet)
    assert muet.collisions == []

    interroge = Interrogateur(cal.CLE_NOM_DIFFERENCIE)
    cal.consigner(projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
                  poser_la_collision=interroge)
    assert len(interroge.collisions) == 1


def test_G4_le_relais_exige_sa_question_et_ne_repond_jamais_seul():
    """Finding `K3` : un rappel optionnel fait de l'oubli de cablage un silence.

    `RelaisDeCollision` n'a **pas** de defaut : le construire sans question est
    une erreur d'appel, pas un ecrasement silencieux.
    """
    with pytest.raises(TypeError):
        cal.RelaisDeCollision()

    relais = cal.RelaisDeCollision(lambda collision: cal.CLE_ECRASER)
    assert relais.collision is None
    assert relais("300-tiff-bbbbbbbbbbbb", "beta") is True
    assert relais.collision == cal.CollisionDeProfil(
        occupant="300-tiff-bbbbbbbbbbbb", radical="beta")

    empreinte = cal.RelaisDeCollision(lambda c: cal.CLE_NOM_DIFFERENCIE)
    assert empreinte("300-tiff-bbbbbbbbbbbb", "beta") is False

    annule = cal.RelaisDeCollision(lambda c: cal.CLE_ANNULER)
    with pytest.raises(cal.CalibrationAnnulee):
        annule("300-tiff-bbbbbbbbbbbb", "beta")


# ===========================================================================
# G5 -- l'explorateur, le dpi vide et requis, la reprise sans lettre
# ===========================================================================

def test_G5_le_champ_de_scan_ouvre_l_EXPLORATEUR_et_non_un_champ_chemin():
    """AC 8.4, ecart `H11` : `E3-9` est le **sixieme site** d'`EPIC11-ARB-48`.

    « Un composant unique remplace le champ-chemin **partout ou la TUI demande
    un chemin** » : `E3-9` demande un chemin et n'etait dans la table d'aucun
    des cinq sites -- il a ete oublie, pas excepte.

    Le clavier passe par `CoutureExplorateur` : cet ecran ne recable aucune
    touche a la main, et la mesure porte sur l'**identite de fonction**.
    """
    ecran = _ecran()
    assert isinstance(ecran, CoutureExplorateur)
    assert (type(ecran)._traiter_l_explorateur
            is CoutureExplorateur._traiter_l_explorateur)
    assert ecran.explorateur.montrer_fichiers is True
    # **Une page, jamais une sequence** : `selection_multiple` n'a pas de sens
    # ici, et l'activer ferait entrer la quatrieme forme d'`EPIC7-ARB-88` dans
    # une commande qui calibre une seule page.
    assert ecran.explorateur.selection_multiple is False

    ecran.formulaire.champ = cal.CHAMP_SCAN
    assert ecran.traiter("enter") is True
    assert ecran.zone == cal.ZONE_EXPLORATEUR


def test_G5_le_dpi_part_VIDE_et_l_action_principale_reste_inaccessible(
        tmp_path, banc):
    """AC 8.5, `EPIC11-ARB-38`, ecart `H12` : « le champ reste requis, et vide ».

    Et l'action principale **dit pourquoi** elle ne part pas : une touche
    annoncee qui ne fait rien et ne dit rien est indistinguable d'un clavier
    casse.

    **Le volet symetrique a change de ligne le 2026-09-01, et pas d'intention.**
    Il posait `⏎` sur le champ de DPI et attendait la passe. `EPIC11-ARB-158`
    l'interdit : « la validation avec Entree n'est pas claire [...] il faut
    qu'il y ait un choix explicite en bas du formulaire : Valider ». `⏎` sur un
    champ de saisie DESCEND desormais, et seule la ligne `Valider` lance. Ce
    que le volet mesure -- « une resolution valide ouvre l'action » -- est
    inchange ; c'est l'endroit ou l'on appuie qui l'est.
    """
    scan = _page_de_scan(tmp_path)
    lances = []
    ecran = _ecran(calibrer=lances.append)
    ecran.formulaire.poser_le_scan(atelier_scan.designer(scan))

    assert ecran.formulaire.dpi == ""
    assert ecran.formulaire.peut_calibrer is False

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran.formulaire.champ = cal.CHAMP_DPI
        ecran.traiter("enter")
        ecran.rafraichir()
        return _texte(ecran), ecran.etat()

    rendu, etat = banc(_app(ecran), scenario)
    assert lances == [], "aucune passe ne part sans resolution declaree"
    assert cal.PHRASE_DPI_REQUIS in etat
    assert cal.MENTION_REQUIS_DPI in rendu

    # Volet symetrique : une resolution valide ouvre l'action -- depuis la
    # ligne `Valider`, qui est la seule a lancer (`EPIC11-ARB-158`).
    ecran.formulaire.dpi = str(DPI)
    assert ecran.formulaire.peut_calibrer is True
    ecran.formulaire.champ = cal.CHAMP_VALIDER
    ecran.traiter("enter")
    assert lances == [ecran.formulaire]


def test_G5_la_mesure_du_coeur_est_a_COTE_et_jamais_substituee(tmp_path, banc):
    """`EPIC11-ARB-38` : « confrontee au DPI declare, **jamais substituee** ».

    Poser la mesure dans le champ serait la substitution que l'arbitrage
    interdit, sous la forme la plus difficile a voir -- un champ qui se remplit
    tout seul et qu'on ne relit pas.
    """
    scan = _page_de_scan(tmp_path)
    ecran = _ecran()
    ecran.formulaire.poser_le_scan(atelier_scan.designer(scan))

    assert ecran.formulaire.dpi == ""
    # La mesure existe pourtant, et la ligne de reprise l'offre.
    assert cal.CHAMP_REPRISE in ecran.formulaire.champs()
    mesure = atelier_scan.mention_de_la_mesure(ecran.formulaire.scan)
    assert mesure

    # Et elle est **affichee a cote** : la ligne de reprise la porte, dans la
    # colonne de droite, a cote de la valeur qu'un `⏎` reprendrait.
    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return _texte(ecran)

    rendu = banc(_app(ecran), scenario)
    ligne = [l for l in rendu.splitlines() if cal.LIBELLE_REPRISE in l]
    assert len(ligne) == 1, rendu
    assert mesure in ligne[0]
    assert f"{atelier_scan.dpi_lisible(ecran.formulaire.scan.dpi)} " \
           f"{atelier_scan.UNITE_DPI}" in ligne[0]


def test_G5_la_reprise_de_la_mesure_n_est_PAS_une_lettre(tmp_path):
    """AC 8.5, `EPIC11-ARB-68` : « aucune lettre n'est un raccourci ».

    Le geste est celui que la 11.5 a retenu : une **ligne du formulaire**,
    atteinte par `Tab` et validee par `⏎`. Le volet symetrique est ce qui donne
    son sens a la mesure : une lettre frappee **s'ecrit** dans le champ de
    saisie au focus, elle n'y declenche rien.
    """
    scan = _page_de_scan(tmp_path)
    ecran = _ecran()
    ecran.formulaire.poser_le_scan(atelier_scan.designer(scan))

    # Aucune lettre isolee dans la ligne de raccourcis.
    mots = cal.RACCOURCIS_CALIBRATE.split()
    assert not [mot for mot in mots if len(mot) == 1 and mot.isalpha()], mots

    # `Tab` jusqu'a la reprise, puis `⏎` : la valeur mesuree entre d'un coup.
    #
    # **La boucle est BORNEE par le nombre de champs.** Non bornee, son mode
    # d'echec n'est pas un rouge mais une PENDAISON : mesure faite en injectant
    # `if touche == "tab" and False:`, le lot de 1465 tests ne rendait jamais la
    # main. C'est litteralement « un test qui suspend emporte les 7000 autres »,
    # le defaut que `scripts/mesure/mesure.py` existe pour contenir -- et qu'un
    # plafond par test masquerait au lieu de le nommer.
    for _ in range(len(ecran.formulaire.champs()) + 1):
        if ecran.formulaire.champ == cal.CHAMP_REPRISE:
            break
        ecran.traiter("tab")
    assert ecran.formulaire.champ == cal.CHAMP_REPRISE, (
        "`Tab` doit rester un synonyme fonctionnel de la navigation")
    ecran.traiter("enter")
    assert ecran.formulaire.dpi == atelier_scan.dpi_lisible(
        ecran.formulaire.scan.dpi)

    # Volet symetrique : sur un champ de saisie, la lettre s'ecrit.
    ecran.formulaire.champ = cal.CHAMP_ETIQUETTE
    for lettre in "beta":
        ecran.traiter("", lettre)
    assert ecran.formulaire.etiquette == "beta"
    assert ecran.traiter("backspace") is True
    assert ecran.formulaire.etiquette == "bet"


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G5_devient_le_defaut_est_un_CHAMP_de_formulaire_a_non(banc, ascii_seul):
    """AC 8.6 : « poser un defaut est une decision, pas un effet de bord ».

    Ce n'est **pas** une liste d'issues : `EPIC11-ARB-126` ne s'y applique pas,
    et `DESIGN.md` section 7.3 pose `(•) oui ( ) non` comme la forme d'un champ.
    C'est dit ici pour qu'une revue ne le corrige pas a tort.

    Les deux glyphes ont leur repli ASCII, donc le second canal survit au repli.

    **L'option retenue est en MAJUSCULES depuis `EPIC11-ARB-158`** (« avec oui
    surligne »), et le libelle attendu suit donc l'etat plutot que d'etre une
    constante. Le glyphe n'a pas bouge : le surlignage le DOUBLE, il ne le
    remplace pas -- meme regle que la couleur en section 5 de `DESIGN.md`.

    Le geste, lui, est desormais `Espace` : `⏎` bascule encore en synonyme (le
    champ garde son geste propre), mais c'est `Espace` que le pied annonce, et
    c'est lui que ce banc joue -- mesurer le synonyme laisserait le geste
    annonce sans mesure.
    """
    ecran = _ecran()
    assert ecran.formulaire.devient_le_defaut is False

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        ecran.formulaire.champ = cal.CHAMP_DEFAUT
        ecran.rafraichir()
        avant = _texte(ecran)
        ecran.traiter("space")
        ecran.rafraichir()
        return avant, _texte(ecran)

    avant, apres = banc(_app(ecran, ascii_seul=ascii_seul), scenario)
    table = jetons.glyphes(ascii_seul)
    brut = cal.CHOIX_NON.upper()
    non = jetons.replier_ascii(brut) if ascii_seul else brut
    assert f"{table['exclusif-retenu']} {non}" in avant
    assert ecran.formulaire.devient_le_defaut is True
    assert f"{table['exclusif-retenu']} {non}" not in apres


def test_G5_devient_le_defaut_a_oui_DESIGNE_le_profil_ecrit(tmp_path,
                                                            coeur_ajuste):
    """Le champ **agit**, et il n'agit que quand il vaut `oui`.

    A `non`, cette passe fait exactement ce que `mmu scan ... calibrate` fait :
    elle ecrit le profil et n'inscrit rien au manifeste (AC 10.2 -- la TUI est
    un appelant de plus, pas un appelant qui en fait plus).
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)

    cal.consigner(projet, _formulaire(scan), poser_la_collision=Interrogateur())
    assert profile_designation.default_profile_entry(projet) is None

    passe = cal.consigner(projet, _formulaire(scan, defaut=True),
                          poser_la_collision=Interrogateur())
    defaut = profile_designation.default_profile_entry(projet)
    assert defaut is not None
    assert profile_designation.designated_profile_path(projet, defaut) == (
        passe.chemin)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G5_les_trois_ecrans_tiennent_dans_la_grille_80_x_24(banc, ascii_seul):
    """La grille du plancher, sur les **trois** ecrans de ce lot, deux modes.

    Le repli ASCII peut **allonger** une ligne (`⏎` rend `Entree`), donc les
    deux modes sont mesures et non l'un des deux. La mesure est en **colonnes**
    et jamais en `len()` : un texte a double chasse rendrait une ligne calee
    juste pour vingt colonnes de trop.
    """
    collision = cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb",
                                      radical="beta")
    apres_une_passe = _ecran()
    apres_une_passe.annoncer(cal.PasseDeCalibration(
        profil=type("Consigne", (), {"profile_path": Path(
            "versions/calibration/hp-envy-4520-tiff-600.json"),
            "chain_id": "600-tiff-bbbbbbbbbbbb"})(),
        chaine="600-tiff-bbbbbbbbbbbb", recalibration=True,
        date_precedente="12/08", date_ecrite="26/08"))
    ecrans = [
        _ecran(),
        apres_une_passe,
        cal.EcranCollisionDeProfil(collision, retenir=lambda issue: None),
        cal.EcranRefusDeCalibration(
            cal.PasseDeCalibration(refus=ValueError("un refus du coeur")),
            retenir=lambda issue: None),
    ]
    utile = jetons.largeur_utile(80)
    for ecran in ecrans:
        rendu = _rendu(ecran, banc, app=_app(ecran, ascii_seul=ascii_seul))
        lignes = rendu.splitlines()
        assert len(lignes) <= 17, (type(ecran).__name__, len(lignes))
        for ligne in lignes:
            assert jetons.colonnes(ligne) <= utile, (
                type(ecran).__name__, ligne, jetons.colonnes(ligne))
        for texte in (ecran.raccourcis, ecran.etat()):
            replie = jetons.replier_ascii(texte) if ascii_seul else texte
            assert jetons.colonnes(replie) <= utile, (
                type(ecran).__name__, replie)


# ===========================================================================
# G5 bis -- la DROITE du bandeau ne porte RIEN (Egan, 2026-09-01)
# ===========================================================================
#
# Correction tranchee sur la planche de relecture du temps 2. La droite portait
# « depuis le menu Scan » ; verbatim d'Egan : « Oui mais il y a écrit "depuis le
# menu scan". On met juste rien à cet endroit... » -- **rien**, et non une autre
# mention. `OBJET_DU_BANDEAU` disparait du module avec elle, et `Palier.bandeau`
# (la redaction unique du bandeau) reprend la main.


@pytest.mark.parametrize("ascii_seul", MODES)
def test_G5bis_la_DROITE_du_bandeau_de_E3_9_ne_porte_RIEN(banc, ascii_seul):
    """Mesure sur le bandeau **affiche**, pas sur une constante retiree.

    Une assertion du genre « `OBJET_DU_BANDEAU` n'existe plus » mesurerait le
    module et non l'ecran : la mention pourrait revenir par l'objet de session,
    par un `objet_du_bandeau()` ou par une seconde redaction, et le module
    resterait propre. C'est ce que ce test attrape, en lisant le widget.

    **L'ensemble est mesure EXACTEMENT** : le bandeau vaut la gauche, et rien
    d'autre. « Une assertion positive laisse passer toute divergence
    supplementaire » -- « il n'y a plus "depuis le menu Scan" » serait vert avec
    n'importe quelle autre glose posee a droite.
    """
    ecran = _ecran()
    app = _app(ecran, ascii_seul=ascii_seul)

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#bandeau").content))

    bandeau = banc(app, scenario).rstrip()
    gauche = f"{PREFIXE_DU_BANDEAU}{cal.PALIER_DE_L_ECRAN}"
    if ascii_seul:
        gauche = jetons.replier_ascii(gauche)
    assert bandeau == gauche, bandeau
    # Et la mention ne survit nulle part dans le module, sous aucune casse.
    assert "menu scan" not in bandeau.lower(), bandeau
    assert not hasattr(cal, "OBJET_DU_BANDEAU")


def test_G5bis_la_gauche_du_bandeau_reste_ENTIERE(banc):
    """Volet symetrique, sans lequel un bandeau **vide** passerait le test
    precedent : la provenance se lit desormais dans la structure -- `Scan ·
    Calibrer` --, et c'est elle qui a rendu la glose inutile.
    """
    ecran = _ecran()

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#bandeau").content))

    bandeau = banc(_app(ecran), scenario)
    for segment in ("mmu", "projet_demo", "Scan", "Calibrer"):
        assert segment in bandeau, (segment, bandeau)


def test_G3_la_ligne_d_etat_d_un_point_de_jugement_est_une_MESURE_accordee():
    """`EPIC11-ARB-56` : aucune touche, aucun conseil, aucun motif.

    Trois formes et non un pluriel pose sans condition : le cas a **un** et le
    cas a **zero** sont les seuls ou la faute d'accord se voie, et ils sont
    tous les deux atteints par le produit -- la collision ecrit une fois,
    l'impasse aucune.
    """
    collision = cal.choix_de_la_collision(
        cal.CollisionDeProfil(occupant="300-tiff-bbbbbbbbbbbb", radical="beta"))
    assert cal.etat_du_choix(collision) == "3 issues · 1 écrit"
    assert cal.etat_du_choix(cal.choix_de_l_impasse()) == (
        "2 issues · aucune n'écrit")
    # Le pluriel a une fabrique a lui : deux issues qui ecrivent, plus une qui
    # n'ecrit pas -- `ChoixExclusif` exige la troisieme.
    deux = ChoixExclusif([Issue("a", "A"), Issue("b", "B", ecrit=True),
                          Issue("c", "C", ecrit=True)])
    assert cal.etat_du_choix(deux) == "3 issues · 2 écrivent"
    # Aucune touche ne s'y glisse : ni `Tab`, ni `Echap`, ni une lettre seule.
    for texte in (cal.etat_du_choix(collision),
                  cal.etat_du_choix(cal.choix_de_l_impasse())):
        assert "Tab" not in texte and "Échap" not in texte and "⏎" not in texte


# ===========================================================================
# G6 -- la fabrique : trois profils, la collision AU MILIEU, QUEL fichier
# ===========================================================================

def test_G6_la_cible_est_au_MILIEU_de_la_liste_que_le_code_parcourt(tmp_path):
    """Regle des fabriques, points 2 et 2 bis, **sur la bonne liste**.

    La liste que ce lot parcourt est celle de `profils_du_projet`, c'est-a-dire
    un `sorted(dossier.iterdir())` -- et non l'ordre dans lequel la fabrique a
    ecrit. La cible y est **deuxieme sur trois** : ni la premiere (mutant
    « rendre le premier »), ni la derniere (mutant `continue` -> `break`).
    """
    projet = _projet(tmp_path)
    parcourue = [chemin.name for chemin in
                 sorted(cal.profils_du_projet(projet))]

    assert parcourue == ["alpha.json", "beta.json", "gamma.json"], parcourue
    assert parcourue[RANG_DE_LA_CIBLE] == f"{ETIQUETTE_EN_COLLISION}.json"
    assert 0 < RANG_DE_LA_CIBLE < len(parcourue) - 1
    # Les trois sont **distinguables** : trois contenus, trois cardinaux.
    contenus = {chemin.read_bytes() for chemin in
                cal.dossier_des_profils(projet).iterdir()}
    assert len(contenus) == 3


def test_G6_le_NOM_DIFFERENCIE_ecrit_un_AUTRE_fichier_et_n_en_touche_aucun(
        tmp_path, coeur_ajuste):
    """AC 8.8 : le test mesure **quel** fichier a ete ecrit.

    L'empreinte differenciante est le defaut du coeur, celui qui n'ecrase rien.
    Deux moities, et la seconde est celle qui compte : le fichier neuf est bien
    celui qui derive du radical **vise**, et les trois profils poses sont
    **intacts** -- inode, `st_mtime_ns` et octets.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    avant = _releve(projet)

    passe = cal.consigner(
        projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
        poser_la_collision=Interrogateur(cal.CLE_NOM_DIFFERENCIE))

    apres = _releve(projet)
    neufs = set(apres) - set(avant)
    assert len(neufs) == 1, sorted(apres)
    neuf = neufs.pop()
    assert neuf.startswith(f"{ETIQUETTE_EN_COLLISION}-"), neuf
    assert passe.chemin.name == neuf
    # **Les trois poses sont intacts** : l'ensemble est mesure exactement, et
    # aux inodes -- une reecriture a l'identique rendrait les memes octets.
    assert {nom: etat for nom, etat in apres.items() if nom in avant} == avant


def test_G6_l_ECRASEMENT_conscient_ecrit_DANS_le_fichier_vise_et_pas_ailleurs(
        tmp_path, coeur_ajuste):
    """AC 8.2 et `EPIC11-ARB-89` : l'ecriture destructive **consciente**.

    Elle passe par `confirm_overwrite` et par lui seul. La mesure porte sur
    **quel** fichier a change : celui du milieu, et lui seul -- une empreinte
    posee sur le mauvais radical reussirait aussi, et un ecrasement pose sur le
    premier profil rendrait le meme succes apparent.
    """
    projet = _projet(tmp_path)
    scan = _page_de_scan(tmp_path)
    avant = _releve(projet)

    passe = cal.consigner(
        projet, _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
        poser_la_collision=Interrogateur(cal.CLE_ECRASER))

    apres = _releve(projet)
    assert set(apres) == set(avant), (
        "l'ecrasement n'ajoute aucun fichier : il remplace celui qui est vise")
    assert passe.chemin.name == f"{ETIQUETTE_EN_COLLISION}.json"
    # **Exactement un fichier a change**, et c'est celui du milieu.
    changes = {nom for nom in apres if apres[nom] != avant[nom]}
    assert changes == {f"{ETIQUETTE_EN_COLLISION}.json"}, sorted(changes)
    # Et son contenu porte desormais la chaine **derivee du scan**, pas l'autre.
    document = json.loads(
        (cal.dossier_des_profils(projet)
         / f"{ETIQUETTE_EN_COLLISION}.json").read_text(encoding="utf-8"))
    assert document["chain_id"] == passe.profil.chain_id
    assert document["chain_id"] != PROFILS_POSES[RANG_DE_LA_CIBLE]["chain_id"]


def test_G6_les_TROIS_issues_produisent_TROIS_etats_de_disque_distincts(
        tmp_path, coeur_ajuste):
    """Le volet qui ferme la famille : les trois issues ne se confondent pas.

    Mesurees sur trois projets identiques, elles rendent trois ensembles de
    fichiers distincts. Une issue qui ferait, en silence, ce qu'une autre fait
    -- l'ecrasement replie sur l'empreinte, l'annulation qui ecrit quand meme --
    passerait tous les tests positifs pris un a un.
    """
    scan = _page_de_scan(tmp_path)
    etats = {}
    for cle in (cal.CLE_NOM_DIFFERENCIE, cal.CLE_ECRASER, cal.CLE_ANNULER):
        projet = _projet(tmp_path, nom=f"projet-{cle}")
        cal.consigner(projet,
                      _formulaire(scan, etiquette=ETIQUETTE_EN_COLLISION),
                      poser_la_collision=Interrogateur(cle))
        etats[cle] = (
            sorted(_releve(projet)),
            (cal.dossier_des_profils(projet)
             / f"{ETIQUETTE_EN_COLLISION}.json").read_bytes())

    assert etats[cal.CLE_NOM_DIFFERENCIE] != etats[cal.CLE_ECRASER]
    assert etats[cal.CLE_ECRASER] != etats[cal.CLE_ANNULER]
    assert etats[cal.CLE_NOM_DIFFERENCIE] != etats[cal.CLE_ANNULER]
    # L'annulation laisse le disque **exactement** comme la fabrique l'a pose.
    assert etats[cal.CLE_ANNULER][0] == [
        "alpha.json", "beta.json", "gamma.json"]


# ===========================================================================
# Les deux maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-1` et `E3-9` et
# n'ouvrait aucun dessin : trois de ses valeurs en etaient recopiees -- le
# pied du palier temoin et le prefixe du bandeau, sur deux ecrans.

#: Les maquettes, a leur source.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

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


def test_le_BANDEAU_de_la_calibration_est_VERBATIM_de_E3_9():
    """Le bandeau que le banc attend est celui que `E3-9` dessine.

    La confrontation porte sur le PRODUIT (`cal.PALIER_DE_L_ECRAN`) et sur le
    prefixe, composes exactement comme le test du rendu les compose : c'est
    la ligne entiere du dessin qui est mesuree, pas deux morceaux.
    """
    dessin = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PREFIXE_DU_BANDEAU + cal.PALIER_DE_L_ECRAN in dessin
    assert cal.PALIER_DE_L_ECRAN == "Scan · Calibrer"


def test_le_PIED_du_palier_temoin_est_celui_que_E3_1_dessine():
    """Le double n'invente pas son pied : `E3-1` l'annonce.

    Un palier temoin dont le pied ne serait pas celui du dessin mesurerait un
    ecran que personne n'a approuve.
    """
    assert PIED_DU_PALIER in dessin_de_la_maquette("E3-1-scan-depot.txt")


def test_les_deux_dessins_se_DISTINGUENT_sur_le_PALIER():
    """Volet symetrique : `E3-1` est le Scan, `E3-9` le Scan CALIBRER.

    Si le palier de la calibration etait dans les deux dessins, la
    confrontation ci-dessus serait verte en confondant les deux ecrans --
    c'est-a-dire en ne mesurant rien de ce qui les distingue.
    """
    depot = dessin_de_la_maquette("E3-1-scan-depot.txt")
    calibrer = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert cal.PALIER_DE_L_ECRAN in calibrer
    assert cal.PALIER_DE_L_ECRAN not in depot
    assert PREFIXE_DU_BANDEAU + "Scan" in depot
    assert PIED_DU_PALIER in depot
    assert PIED_DU_PALIER not in calibrer


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Trois contre-exemples, dont deux a un mot pres.
    """
    calibrer = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PREFIXE_DU_BANDEAU + "Scan · Calibration" not in calibrer
    assert "mmu · projet_essai · " not in calibrer
    assert PIED_DU_PALIER + " et revenir" not in calibrer
