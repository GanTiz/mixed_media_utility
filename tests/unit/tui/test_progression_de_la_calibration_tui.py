# -*- coding: utf-8 -*-
"""Story 11.4e, lot J2 -- `E3-9` MONTRE sa passe (AC 9.4 a 9.6).

**Ce banc et lui seul mesure J2.** J1 (le coeur) a le sien.

Verbatim d'Egan, 2026-09-01, qui EST la specification :

> Pas de page de progression quand on lance une calibration. Cela prete a
> confusion. RIEN n'indique qu'on a lance le processus. Pas de page de
> validation avant, ce n'est pas conforme au reste des parcours.

Deux manques, et le second n'etait pas dans l'AC 9 : la page de **confirmation
avant** lancement. Elle suit la forme des autres parcours (`EcranChiffre`) --
elle chiffre ce qui va etre fait et dit que rien n'est encore ecrit.

**Ce banc porte aussi les findings F1 a F3** de la couche de reprise de la
vague 4 (rapport `review-vague-4-couche-de-reprise.md` sur `oc/epic-11-TUI`).
Ils vivent dans `consigner_le_profil`, c'est-a-dire dans la fonction que J2
reecrit : les traiter separement ferait deux passes sur le meme code.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.tui import atelier_scan_calibrate as calib
from mixed_media_utility.tui import atelier_scan_parcours as parcours
from mixed_media_utility.tui import execution
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin


class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 3, 1000, 300.0, 1


class _Source:
    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 3, 300.0, 1
    est_multiple = False

    def __init__(self, chemin):
        self.chemin = chemin


def _formulaire_pret(tmp_path: Path) -> calib.FormulaireDeCalibration:
    formulaire = calib.FormulaireDeCalibration()
    formulaire.poser_le_scan(_Source(tmp_path / "mire.pdf"))
    formulaire.dpi = "300"
    return formulaire


def _app(*ecrans) -> CoqueTui:
    return CoqueTui([PalierTemoin("Ateliers", "Q quitter"), *ecrans],
                    Contexte("projet", "Scan"))


# --- AC 9.4 : une SurfaceExecution et un EcranExecution, comme partout ------


def test_la_passe_monte_un_ECRAN_D_EXECUTION_et_pas_un_ecran_neuf(
    tmp_path: Path, banc
) -> None:
    """AC 9.4 : « comme partout ailleurs -- pas un ecran neuf ».

    Mesure de l'IDENTITE de classe et non d'un nom : un ecran neuf qui
    ressemblerait a `EcranExecution` serait vert sous une assertion de titre,
    et divergerait au premier ajustement de la barre.
    """
    # **Monte sous le pilote, et pas a nu.** `descendre` poste sur la boucle
    # de `textual` : hors boucle, l'appel passe tant qu'aucun autre banc n'en a
    # ouvert une, et leve « no running event loop » des qu'un autre l'a fait.
    # Le banc etait donc vert seul et rouge en suite -- l'ordre des fichiers
    # decidait du verdict.
    app = _app()

    async def scenario(pilote):
        return calib.ouvrir_la_calibration_en_cours(pilote.app)

    ecran = banc(app, scenario)
    assert isinstance(ecran, execution.EcranExecution)
    assert isinstance(ecran.surface, execution.SurfaceExecution)
    # Le total part a zero : il n'est connu qu'apres l'ingestion, et
    # l'inventer ici serait un chiffre faux presente comme une mesure.
    assert ecran.surface.avancement.total == 0


def test_le_TOTAL_et_les_JALONS_arrivent_du_coeur_jusqu_a_la_barre(
    tmp_path: Path, banc
) -> None:
    """Le canal de bout en bout : `consigner` -> surface -> barre.

    **Trois pages, et les jalons sont mesures un par un.** Une assertion sur le
    seul dernier jalon serait verte sur une barre qui saute de 0 a 3 -- ce qui
    est exactement l'ecran fige qu'Egan decrit.
    """
    vus = []

    async def scenario(pilote):
        return calib.ouvrir_la_calibration_en_cours(pilote.app)

    ecran = banc(_app(), scenario)
    ecran.surface.avancement.total = 3
    ecran.surface.abonner(lambda a: vus.append((a.faites, a.total)))

    # **Le double porte la signature du COEUR, sans `**kwargs`**, et le
    # docstring de `CalibrationFeinte` l'exige mot pour mot : « un faux
    # permissif laisserait passer un appel dont un mot-cle est mal nomme ».
    # Ces deux doubles employaient `**kwargs` et ne pouvaient donc pas
    # detecter un mot-cle renomme (tolerance `T-2`, revue de vague B).
    def _calibrer(dossier, scan, *, dpi, logger=None,
                  demander_le_nom_et_le_commentaire=None,
                  confirmer_l_ecrasement=None, rappel_progression=None):
        for faites in (1, 2, 3):
            rappel_progression(faites, 3)
        raise calib.scan_calibrate.RefusDeCalibration(
            "arret volontaire du banc", motif="PAS_DE_MIRE")

    calib.consigner(tmp_path, _formulaire_pret(tmp_path),
                    poser_la_collision=lambda c: "annuler",
                    calibrer=_calibrer,
                    rappel_progression=ecran.surface.noter)
    assert vus == [(1, 3), (2, 3), (3, 3)]


def test_SANS_surface_la_passe_fait_EXACTEMENT_la_meme_chose(
    tmp_path: Path
) -> None:
    """`AR3` cote TUI : le rappel reste OPTIONNEL a cette couche aussi.

    Les deux passes sont comparees sur ce qu'elles RENDENT. Deux passes qui ne
    levent ni l'une ni l'autre mais rendent des refus differents seraient un
    defaut pire, parce que muet.
    """
    # **Le double porte la signature du COEUR, sans `**kwargs`**, et le
    # docstring de `CalibrationFeinte` l'exige mot pour mot : « un faux
    # permissif laisserait passer un appel dont un mot-cle est mal nomme ».
    # Ces deux doubles employaient `**kwargs` et ne pouvaient donc pas
    # detecter un mot-cle renomme (tolerance `T-2`, revue de vague B).
    def _calibrer(dossier, scan, *, dpi, logger=None,
                  demander_le_nom_et_le_commentaire=None,
                  confirmer_l_ecrasement=None, rappel_progression=None):
        raise calib.scan_calibrate.RefusDeCalibration(
            "arret volontaire du banc", motif="PAS_DE_MIRE")

    sans = calib.consigner(tmp_path, _formulaire_pret(tmp_path),
                           poser_la_collision=lambda c: "annuler",
                           calibrer=_calibrer)
    avec = calib.consigner(tmp_path, _formulaire_pret(tmp_path),
                           poser_la_collision=lambda c: "annuler",
                           calibrer=_calibrer,
                           rappel_progression=lambda *_: None)
    assert sans.a_ecrit == avec.a_ecrit
    assert type(sans.refus) is type(avec.refus)
    assert sans.motif == avec.motif


# --- la page de CONFIRMATION avant lancement (Egan, 2026-09-01) ------------


def test_une_page_de_CONFIRMATION_chiffre_la_passe_et_dit_que_rien_n_est_ecrit(
    tmp_path: Path
) -> None:
    """« Pas de page de validation avant, ce n'est pas conforme au reste. »

    Elle suit la forme des autres parcours : un `EcranChiffre`, donc un
    cartouche chiffre **et** un choix d'issues. Le banc mesure les trois faits
    qui la rendent utile -- ce qui sera lu, avec quelle resolution, et si le
    profil deviendra le defaut -- par un ensemble EXACT de libelles : une
    assertion d'appartenance laisserait passer une ligne de moins.
    """
    formulaire = _formulaire_pret(tmp_path)
    ecran = calib.EcranCalibrationAConfirmer(formulaire,
                                             sur_issue=lambda issue: None)
    assert isinstance(ecran, execution.EcranChiffre)

    libelles = [ligne.libelle for ligne in ecran.panneau.lignes]
    assert libelles == [calib.LIBELLE_SCAN, calib.LIBELLE_DPI,
                        calib.LIBELLE_DEFAUT]

    # **L'ensemble EXACT des issues qui menent a une ecriture**, et son
    # unicite. `ecrit` marque l'issue qui MENE a l'ecriture, pas celle qui
    # ecrit dans la milliseconde -- `E3-6` le pose de meme sur un ecran qui n'a
    # encore rien mis sur le disque. La premiere redaction assertait
    # `== {False}` des deux cotes, et ce `False` **desarmait** le placement du
    # curseur d'`EPIC11-ARB-7` (revue de vague B, couche 2).
    ecrivent = {issue.cle for issue in ecran.choix.issues if issue.ecrit}
    assert ecrivent == {calib.ISSUE_LANCER}
    # Et le corollaire, qui est la protection elle-meme : le curseur ne se pose
    # PAS sur l'issue qui lance. Un `⏎` nu sur la page ajoutee pour empecher un
    # `⏎` reflexe partait dans une passe de plusieurs minutes.
    assert not ecran.choix.issues[ecran.choix.curseur].ecrit
    assert ecran.choix.issues[ecran.choix.curseur].cle == calib.ISSUE_REVENIR
    assert [issue.cle for issue in ecran.choix.issues] == [
        calib.ISSUE_LANCER, calib.ISSUE_REVENIR]


def test_le_formulaire_ouvre_la_CONFIRMATION_et_n_appelle_PAS_le_coeur(
    tmp_path: Path, monkeypatch
) -> None:
    """`Valider` mene au jugement, jamais directement a l'ecriture.

    C'est la moitie qui compte : une confirmation qu'on peut sauter n'en est
    pas une. Le banc mesure que le coeur n'est PAS appele -- par un temoin, pas
    par l'absence d'exception.
    """
    lances = []
    ecran = calib.EcranCalibrerLaChaine(tmp_path, calibrer=lambda f: None)
    app = _app(ecran)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran
    p.lancer_la_passe_de_calibration = lambda f: lances.append(f)
    ecran._calibrer = p.consigner_le_profil
    ecran.formulaire = _formulaire_pret(tmp_path)
    ecran.formulaire.champ = calib.CHAMP_VALIDER

    montes = []
    app.descendre = lambda palier=None: montes.append(palier)
    ecran.traiter("enter")

    # `Valider` monte la CONFIRMATION, et n'appelle pas la passe.
    assert len(montes) == 1
    assert isinstance(montes[0], calib.EcranCalibrationAConfirmer)
    assert lances == [], "une confirmation qu'on peut sauter n'en est pas une"

    # Et c'est l'issue « lancer », et elle seule, qui lance.
    p.trancher_la_confirmation(
        calib.issues_de_la_confirmation().issues[1], ecran.formulaire)
    assert lances == []
    p.trancher_la_confirmation(
        calib.issues_de_la_confirmation().issues[0], ecran.formulaire)
    assert lances == [ecran.formulaire]


# --- F1 : la fenetre entre le drapeau et l'annonce -------------------------


def test_F1_le_drapeau_tombe_APRES_l_annonce_et_jamais_avant(
    tmp_path: Path, monkeypatch
) -> None:
    """Finding `F1` de la couche de reprise, et c'est le plus grave des quatre.

    L'annonce etait **hors** du `try`, donc le drapeau tombait AVANT elle :
    entre les deux `call_from_thread`, la boucle etait libre avec
    `tache_en_cours` a faux, et un `Echap` y depilait `E3-9` sous une annonce
    qui arrivait alors sur un ecran demonte. Mesure de bout en bout par le
    rapporteur : le profil ETAIT ecrit, et l'operateur n'en savait rien.

    Le banc mesure l'ORDRE, sur l'etat du drapeau **au moment ou l'annonce
    commence**. Un mutant qui remettrait l'annonce apres l'oubli survivrait a
    toute mesure prise apres coup -- c'est ce que le rapport a constate : 483
    tests sur 483 le laissaient passer.
    """
    vu = {}
    ecran = calib.EcranCalibrerLaChaine(tmp_path, calibrer=lambda f: None)
    app = _app(ecran)
    p = parcours.ParcoursScan(app, tmp_path) if hasattr(parcours, "ParcoursScan") \
        else None
    assert p is not None, "le parcours doit exposer sa classe"
    p.ecran_de_calibration = ecran
    # Le drapeau est POSE, comme `consigner_le_profil` le pose avant le fil :
    # sans lui, ce banc mesurerait un ordre sur un drapeau deja tombe.
    app.tache_en_cours = True

    def _annoter(ecr, passe):
        vu["tache_a_l_entree_de_l_annotation"] = app.tache_en_cours

    def _ouvrir(passe):
        vu["tache_a_l_ouverture_du_refus"] = app.tache_en_cours
        return None

    monkeypatch.setattr(p, "annoter_la_passe", _annoter)
    # **La moitie NAVIGATION s'appelle `ouvrir_ce_que_la_passe_demande` depuis
    # le 2026-09-06**, et c'est elle qu'il faut doubler ici. Le refus n'est
    # plus la seule branche : une passe qui a ecrit monte desormais son ecran
    # de resultat (retour terrain d'Egan, « pas d'ecran de succes »). Ce que ce
    # banc mesure ne change pas d'un mot -- l'ORDRE entre l'annotation et la
    # navigation --, mais doubler l'ancienne moitie ne mesurerait plus rien :
    # `conclure_la_passe` ne l'appelle plus directement.
    monkeypatch.setattr(p, "ouvrir_ce_que_la_passe_demande", _ouvrir)
    p.conclure_la_passe(ecran, object())

    # `F1` : l'annotation se fait SOUS le drapeau -- `Echap` ne peut pas
    # depiler `E3-9` pendant qu'on ecrit dessus.
    assert vu["tache_a_l_entree_de_l_annotation"] is True
    # **Et la NAVIGATION se fait drapeau tombe**, ce qui est la moitie que la
    # premiere redaction de ce correctif avait manquee : `descendre` rend la
    # main a la boucle au montage, donc l'ecran de refus etait vivant avec
    # `tache_en_cours` encore a vrai -- et `sortir_du_refus` passe par
    # `action_remonter`, qui est gardee par ce drapeau. « Renommer l'etiquette
    # et reprendre » ne depilait rien. Mesure de bout en bout par
    # `test_les_DEUX_issues_de_l_impasse` sous `-n 4`.
    assert vu["tache_a_l_ouverture_du_refus"] is False
    assert app.tache_en_cours is False, "et il reste tombe"


def test_F2_le_drapeau_tombe_MEME_si_l_annonce_LEVE(tmp_path: Path,
                                                    monkeypatch) -> None:
    """Finding `F2`, second volet : « dans tous les cas, y compris si ca leve ».

    Sans le `finally`, `tache_en_cours` resterait a vrai pour la session :
    `Echap` ne depilerait plus, `q` ne quitterait plus, et la garde de
    re-entrance interdirait toute passe suivante -- le fil attend pour
    toujours, la panne exacte que le filet existe pour ecarter.
    """
    ecran = calib.EcranCalibrerLaChaine(tmp_path, calibrer=lambda f: None)
    app = _app(ecran)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran
    app.tache_en_cours = True

    def _qui_leve(ecr, passe):
        raise RuntimeError("l'annotation a leve")

    monkeypatch.setattr(p, "annoter_la_passe", _qui_leve)
    with pytest.raises(RuntimeError):
        p.conclure_la_passe(ecran, object())
    assert app.tache_en_cours is False


# --- F3 : la garde de re-entrance ne doit pas etre MUETTE ------------------


def test_F3_la_garde_de_re_entrance_DIT_pourquoi_elle_refuse(
    tmp_path: Path
) -> None:
    """Finding `F3` : « une touche qui ne fait rien et ne dit rien ».

    La garde est posee huit lignes sous un commentaire qui dit, verbatim,
    qu'une telle touche « est indistinguable d'un clavier casse ». `⏎` ne
    faisait rien et ne disait rien.
    """
    ecran = calib.EcranCalibrerLaChaine(tmp_path, calibrer=lambda f: None)
    app = _app(ecran)
    p = parcours.ParcoursScan(app, tmp_path)
    p.ecran_de_calibration = ecran
    app.tache_en_cours = True

    assert p.consigner_le_profil(_formulaire_pret(tmp_path)) is None
    assert ecran.etat(), "la garde doit DIRE, pas seulement refuser"
